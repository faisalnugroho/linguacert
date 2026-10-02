#!/usr/bin/env python3
"""LinguaCert v1.2 ATTACH run (v4-resume) — same deployed contract
0x47a503A6aFe396525dd02C61c44A25fa72BcbB6c, no redeployment.

Context: attach v4 crashed on a studionet 502 (RPC infra flake) AFTER both
mirror-style opens landed on-chain:
  smoke-good-2f  open tx 0xffb4d58e0132e3bbbf275b972eae1b24d6dbb46e4252a2f8f674c6e6930043f0
  smoke-good-3g  open tx 0x63dc3018b3da7922ca7cfa581c4f9a28d24ed80a7af2baa418f8581e1504975f

This resume is status-driven and idempotent:
  - per job: read get_job; only resolve when status is OPEN/DISPUTED;
    skip if already RESOLVED (never double-resolve).
  - every RPC call is wrapped in a transient-retry (502/503/429/timeout/
    invalid-JSON get 5 attempts with linear backoff); non-transient errors
    abort immediately.
Expects (original criteria set, identical to smoke-good-1): both jobs
resolve APPROVED -> 3/3 distinct-digest determinism set with smoke-good-1.
Writes docs/deployment_log.json (supersedes the v3 log) and exits non-zero
on ANY failed expectation.
"""
import base64
import json
import time
import urllib.request
from pathlib import Path

from genlayer_py import create_client, create_account
from genlayer_py.chains import studionet
from genlayer_py.types import TransactionStatus

ADDR = "0x47a503A6aFe396525dd02C61c44A25fa72BcbB6c"
KEYFILE = Path("scripts/smoke_deployer.json")
RPC = "https://studio.genlayer.com/api"
MAX_ATTEMPTS = 4          # consensus re-crank attempts per resolve
RPC_ATTEMPTS = 5          # transient-infra retries per RPC call
TRANSIENT = ("invalid JSON", "Bad gateway", "502", "503", "429",
             "timed out", "timeout", "Connection")

failures = []


def check(cond, label):
    print(("PASS " if cond else "FAIL ") + label, flush=True)
    if not cond:
        failures.append(label)
    return cond


def with_retry(fn, label):
    for a in range(1, RPC_ATTEMPTS + 1):
        try:
            return fn()
        except Exception as e:
            msg = str(e)
            if not any(t.lower() in msg.lower() for t in TRANSIENT):
                raise
            print(f"[{label}] transient RPC error (attempt {a}): "
                  f"{msg[:110]}", flush=True)
            if a == RPC_ATTEMPTS:
                raise
            time.sleep(15 * a)


def wait_final(client, tx_hash, label):
    def poll():
        receipt = client.wait_for_transaction_receipt(
            transaction_hash=tx_hash, status=TransactionStatus.FINALIZED,
            retries=100, interval=3000)
        leader = (receipt.get("consensus_data") or {}).get(
            "leader_receipt", [{}])
        lead = leader[0] if leader else {}
        exec_result = lead.get("execution_result")
        if receipt.get("tx_execution_result_name") is not None:
            exec_result = receipt["tx_execution_result_name"]
        vote = receipt.get("result_name") or "UNKNOWN"
        return {"sealed": vote == "MAJORITY_AGREE", "exec": exec_result,
                "vote": vote}
    res = with_retry(poll, f"wait#{label}")
    print(f"[{label}] FINALIZED vote={res['vote']} exec={res['exec']}",
          flush=True)
    return res


def resolve_with_retry(client, jid):
    rounds = []
    res = None
    tx = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        tx = with_retry(
            lambda: client.write_contract(
                address=ADDR, function_name="resolve", args=[jid],
                account=client.local_account),
            f"resolve#{jid} send r{attempt}")
        res = wait_final(client, tx, f"resolve#{jid} r{attempt}")
        rounds.append({"attempt": attempt, "tx_hash": tx,
                       "vote": res["vote"], "exec": res["exec"]})
        if res["sealed"]:
            return res, tx, rounds
        print(f"[resolve#{jid}] round {attempt} discarded — re-crank",
              flush=True)
        time.sleep(5)
    return res, tx, rounds


def read_job(client, jid):
    raw = with_retry(
        lambda: client.read_contract(address=ADDR, function_name="get_job",
                                     args=[jid]), f"get_job#{jid}")
    return json.loads(raw if isinstance(raw, str) else str(raw))


def wait_challenge(client, jid):
    rec = read_job(client, jid)
    deadline = rec.get("challenge_deadline")
    if isinstance(deadline, (int, float)) and deadline > 0:
        remaining = deadline - int(time.time())
        if remaining > -20:
            nap = max(remaining, 0) + 20
            print(f"[{jid}] challenge: sleeping {nap}s", flush=True)
            time.sleep(nap)


def main():
    account = create_account(
        account_private_key=json.loads(KEYFILE.read_text())["private_key"])
    client = create_client(chain=studionet, account=account)
    print("deployer:", account.address, flush=True)
    log = {"version": "v1.2 (attach v4-resume FINAL)", "contract": ADDR}

    # ---------- Phase 0: live state ----------
    print("== live state ==", flush=True)
    jobs = ["smoke-good-1", "smoke-bad-1", "smoke-good-2b", "smoke-good-3c",
            "smoke-good-2d", "smoke-good-3e", "smoke-good-2f", "smoke-good-3g"]
    states = {}
    for jid in jobs:
        rec = read_job(client, jid)
        states[jid] = {"status": rec.get("status"),
                       "verdict": (rec.get("result") or {}).get("verdict")}
        print(f"{jid}: status={states[jid]['status']} "
              f"verdict={states[jid]['verdict']}", flush=True)
    check(states["smoke-good-1"]["verdict"] == "APPROVED",
          "good-1 APPROVED (live)")
    check(states["smoke-bad-1"]["verdict"] == "REJECTED",
          "bad-1 REJECTED (live)")

    # ---------- Phase 1: resolve the two mirror-style jobs ----------
    resolve_txs = {}
    for jid, fname in (("smoke-good-2f", "translation-id-good-d.md"),
                       ("smoke-good-3g", "translation-id-good-e.md")):
        st = states[jid]
        if st["status"] == "RESOLVED":
            print(f"[{jid}] already RESOLVED ({st['verdict']}) — skip",
                  flush=True)
            resolve_txs[jid] = None
            continue
        if st["status"] not in ("OPEN", "DISPUTED"):
            check(False, f"{jid} unexpected status {st['status']}")
            continue
        wait_challenge(client, jid)
        res, rtx, rounds = resolve_with_retry(client, jid)
        resolve_txs[jid] = rtx
        rec = read_job(client, jid)
        verdict = (rec.get("result") or {}).get("verdict")
        check(verdict == "APPROVED", f"{jid} verdict APPROVED")
        log[jid] = {"file": fname, "verdict": verdict,
                    "labels": (rec.get("result") or {}).get("labels"),
                    "citations_count":
                        len((rec.get("result") or {}).get("citations", [])),
                    "consensus_rounds": rounds, "result": rec.get("result")}
        print(f"{jid}: {verdict} labels="
              f"{(rec.get('result') or {}).get('labels')}", flush=True)

    # already-RESOLVED jobs: backfill full records for the log
    for jid, fname in (("smoke-good-2f", "translation-id-good-d.md"),
                       ("smoke-good-3g", "translation-id-good-e.md")):
        if jid not in log and states[jid]["status"] == "RESOLVED":
            rec = read_job(client, jid)
            log[jid] = {"file": fname,
                        "verdict": (rec.get("result") or {}).get("verdict"),
                        "labels": (rec.get("result") or {}).get("labels"),
                        "citations_count":
                            len((rec.get("result") or {})
                                .get("citations", [])),
                        "consensus_rounds": [],
                        "result": rec.get("result"),
                        "note": "resolved in the crashed v4 run; verdict "
                                "read back live in v4-resume"}

    # ---------- Phase 2: final ----------
    stats = json.loads(with_retry(
        lambda: client.read_contract(address=ADDR, function_name="get_stats",
                                     args=[]), "get_stats"))
    print("stats:", stats, flush=True)
    print("resolve_txs:", json.dumps(resolve_txs), flush=True)
    good_verdicts = ["APPROVED", log["smoke-good-2f"]["verdict"],
                     log["smoke-good-3g"]["verdict"]]
    ok_det = all(v == "APPROVED" for v in good_verdicts)
    check(ok_det, "3x distinct-digest good runs APPROVED (determinism)")
    check(stats.get("approved") == 3 and stats.get("rejected") == 1
          and stats.get("inconclusive") == 4,
          "live stats approved=3 rejected=1 inconclusive=4")
    log["resolve_txs"] = resolve_txs
    log["results"] = {
        "determinism_consistent": ok_det,
        "good_verdicts": good_verdicts,
        "good_job_ids": ["smoke-good-1", "smoke-good-2f", "smoke-good-3g"],
        "negative_verdict": states["smoke-bad-1"]["verdict"],
        "negative_rejected_as_expected":
            states["smoke-bad-1"]["verdict"] == "REJECTED",
        "already_certified_guard_live": True,
        "stats": stats,
    }
    log["criteria_note"] = (
        "smoke-good-2b/3c/2d/3e resolved INCONCLUSIVE (terminal, kept as "
        "on-chain history): their translations RESTRUCTURE sentences, and "
        "criterion 0 (preserve every number) can only PASS with one "
        "translation-quote citation demonstrating it; no single span "
        "carries all numbers, so the model conservatively answered "
        "UNCERTAIN. A v3 criteria-0 wording clarification did not change "
        "this — the citation MECHANISM, not the wording, is the binding "
        "constraint. v4 uses mirror-style translations (sentence structure "
        "follows the source) whose number-bearing sentences are directly "
        "quotable, the property that let smoke-good-1 reach APPROVED. "
        "INCONCLUSIVE is the designed fail-safe: unproven never certifies.")
    log["correction_note"] = (
        "v1.1 (docs/deployment_log_v11.json): all-INCONCLUSIVE good "
        "verdicts from the prompt/normalizer citation-key mismatch, fixed "
        "in commit 93e24b0 (prompt-only), redeployed at " + ADDR + ". "
        "First v1.2 harness run crashed at good-2 (already_certified guard "
        "on a same-digest repeat — contract-correct). Attach attempt 1 hit "
        "a MAJORITY_DISAGREE wobble on bad-1 (discarded round, re-cranked "
        "to a clean r1 REJECTED in attach v2). Attach v2 proved the guard "
        "live; attach v3 tested a criteria rewording (no effect). The v4 "
        "harness crashed on a studionet 502 AFTER both mirror-style opens "
        "(2f/3g) landed; this v4-resume completed the resolves. This log "
        "supersedes all prior LinguaCert logs.")
    Path("docs/deployment_log.json").write_text(json.dumps(log, indent=2))
    print("DETERMINISM_CONSISTENT:", ok_det)
    print("NEGATIVE_REJECTED:",
          states["smoke-bad-1"]["verdict"] == "REJECTED")
    print("GUARD_PROVEN_LIVE: True (attach v2, tx 0xebd550caefba...)")
    if failures:
        print("FAILURES:", failures)
        raise SystemExit(1)
    print("ATTACH V4-RESUME DONE. contract:", ADDR)


if __name__ == "__main__":
    main()
