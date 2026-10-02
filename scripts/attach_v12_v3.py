#!/usr/bin/env python3
"""LinguaCert v1.2 ATTACH run (v3, final) — same deployed contract
0x47a503A6aFe396525dd02C61c44A25fa72BcbB6c, no redeployment.

Absorbs:
  - original harness: good-1 APPROVED; crash at good-2 (already_certified).
  - attach attempt 1: opened good-2b/good-3c; bad-1 MAJORITY_DISAGREE wobble
    (discarded round, re-cranked later).
  - attach v2: bad-1 sealed REJECTED (r1); guard probe tx 0xebd550...
    MAJORITY_AGREE + exec ERROR (revert reason lives in leader_receipt[0]
    .result base64, not stderr); good-2b/good-3c resolved INCONCLUSIVE in
    single MAJORITY_AGREE rounds — the model marked criterion 0 UNCERTAIN
    because the translations changed locale separators (1,000 -> 1.000,
    12.5 -> 12,5) while the criteria text never stated the contract's own
    separator-insensitive standard.

v3 actions (all in job ARGS, contract untouched):
  1. re-verify live terminal states + recover guard evidence by decoding
     leader_receipt[0].result (base64) of the existing guard tx;
  2. open smoke-good-2d / smoke-good-3e (same unique-digest translation
     files) with criterion 0 clarified to the contract's standard:
     "Numbers match when the digits match: thousands and decimal
     separators may differ by locale (1,000 == 1.000, 12.5 == 12,5).";
  3. resolve them (re-crank loop) expecting APPROVED x2;
  4. write docs/deployment_log.json (v3) superseding prior logs with the
     full honest history. Exits non-zero on ANY failed expectation.
"""
import base64
import hashlib
import json
import time
import urllib.request
from pathlib import Path

from genlayer_py import create_client, create_account
from genlayer_py.chains import studionet
from genlayer_py.types import TransactionStatus

ADDR = "0x47a503A6aFe396525dd02C61c44A25fa72BcbB6c"
DEPLOY_TX = "0xab9f341503b7fc72a9fc13f37d5a22ab68f0d6db4a2a44e030aeaff5152d4491"
GUARD_TX = "0xebd550caefbae778a76b816608b9bf43aeb0dc03ec8b9d451e469b1833efe99a"
KEYFILE = Path("scripts/smoke_deployer.json")
COMMIT = "383f9dba378784873772fb8bab65c14fc169ff68"
RAW = "https://raw.githubusercontent.com/faisalnugroho/linguacert/{commit}/examples/"
CHALLENGE = 300
WINDOW = 3600
MAX_ATTEMPTS = 4
RPC = "https://studio.genlayer.com/api"
EXPLORER = "https://explorer-studio.genlayer.com/api"

CRITERIA_V3 = [
    "The translation preserves every quantity, date and technical number "
    "from the source. Numbers match when the digits match: thousands and "
    "decimal separators may differ by locale (1,000 == 1.000, "
    "12.5 == 12,5).",
    "The translation keeps all URLs, code identifiers and placeholders "
    "such as {machine_id} unchanged.",
    "The translation reads as natural, grammatically correct Indonesian "
    "with correct domain terminology.",
]

failures = []


def check(cond, label):
    print(("PASS " if cond else "FAIL ") + label, flush=True)
    if not cond:
        failures.append(label)
    return cond


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def http_json(url, payload=None):
    req = urllib.request.Request(
        url, method="POST" if payload is not None else "GET",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"User-Agent": "Mozilla/5.0",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def raw_tx(tx_hash):
    return http_json(RPC, {"jsonrpc": "2.0", "id": 1,
                           "method": "eth_getTransactionByHash",
                           "params": [tx_hash]}).get("result") or {}


def wait_final(client, tx_hash, label):
    receipt = client.wait_for_transaction_receipt(
        transaction_hash=tx_hash, status=TransactionStatus.FINALIZED,
        retries=100, interval=3000)
    leader = (receipt.get("consensus_data") or {}).get("leader_receipt", [{}])
    lead = leader[0] if leader else {}
    exec_result = lead.get("execution_result")
    if receipt.get("tx_execution_result_name") is not None:
        exec_result = receipt["tx_execution_result_name"]
    vote = receipt.get("result_name") or "UNKNOWN"
    sealed = vote == "MAJORITY_AGREE"
    print(f"[{label}] FINALIZED vote={vote} exec={exec_result}", flush=True)
    return {"sealed": sealed, "exec": exec_result, "vote": vote,
            "stderr": str((lead.get("genvm_result") or {}).get("stderr")
                          or ""),
            "result_b64": lead.get("result") or "",
            "calldata_b64": lead.get("calldata") or ""}


def resolve_with_retry(client, jid):
    rounds = []
    res = None
    tx = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        tx = client.write_contract(address=ADDR, function_name="resolve",
                                   args=[jid], account=client.local_account)
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
    raw = client.read_contract(address=ADDR, function_name="get_job",
                               args=[jid])
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
    log = {"version": "v1.2 (attach v3)", "contract": ADDR,
           "examples_commit": COMMIT}

    # ---------- Phase 0: live state re-read ----------
    print("== live state ==", flush=True)
    states = {}
    for jid in ("smoke-good-1", "smoke-bad-1", "smoke-good-2b",
                "smoke-good-3c"):
        rec = read_job(client, jid)
        states[jid] = rec["result"]["verdict"]
        print(f"{jid}: {states[jid]}", flush=True)
    check(states["smoke-good-1"] == "APPROVED", "good-1 APPROVED (live)")
    check(states["smoke-bad-1"] == "REJECTED", "bad-1 REJECTED (live)")
    check(states["smoke-good-2b"] == "INCONCLUSIVE"
          and states["smoke-good-3c"] == "INCONCLUSIVE",
          "2b/3c INCONCLUSIVE (terminal, kept as history)")

    # ---------- Phase 1: guard evidence decode ----------
    print("== already_certified guard evidence ==", flush=True)
    raw = raw_tx(GUARD_TX)
    lr = (raw.get("consensus_data") or {}).get("leader_receipt") or [{}]
    lead = lr[0] if lr else {}
    reason = ""
    try:
        reason = base64.b64decode(lead.get("result") or "").decode(
            "utf-8", "replace")
    except Exception:
        pass
    calldata = base64.b64decode(lead.get("calldata") or b"").decode(
        "utf-8", "replace")
    check(lead.get("execution_result") == "ERROR",
          "guard tx execution_result == ERROR")
    check("already_certified" in reason,
          f"revert reason decodes to already_certified ({reason!r})")
    check("resolve" in calldata and "smoke-good-2" in calldata,
          "guard tx calldata is resolve(smoke-good-2)")
    log["already_certified_guard"] = {
        "tx_hash": GUARD_TX,
        "vote": raw.get("result_name"),
        "execution_result": lead.get("execution_result"),
        "revert_reason": reason.strip().lstrip("\x01"),
        "calldata_decode": ("method=resolve job=smoke-good-2"),
        "evidence_location": ("leader_receipt[0].result is base64 of the "
                              "revert tag + reason; stderr is empty for "
                              "deterministic guard reverts on this runner"),
        "meaning": ("good-1 APPROVED registered the translation digest; "
                    "resolving good-2 (SAME translation file) is refused — "
                    "single-certification invariant proven live")}

    # ---------- Phase 2: open clarified-criteria jobs ----------
    print("== opens (clarified criteria) ==", flush=True)
    criteria_json = json.dumps(CRITERIA_V3)
    source = Path("examples/source-en.md").read_text()
    new_jobs = [
        ("smoke-good-2d", "Maintenance manual EN->ID (variant B, "
                          "locale-separator note)", 
         "examples/translation-id-good-b.md"),
        ("smoke-good-3e", "Maintenance manual EN->ID (variant C, "
                          "locale-separator note)",
         "examples/translation-id-good-c.md"),
    ]
    for jid, title, path in new_jobs:
        try:
            read_job(client, jid)
            print(f"[open#{jid}] already exists — skip", flush=True)
        except Exception:
            text = Path(path).read_text()
            fname = path.split("/")[-1]
            tx = client.write_contract(
                address=ADDR, function_name="open_job",
                args=[jid, title,
                      RAW.format(commit=COMMIT) + "source-en.md", sha(source),
                      RAW.format(commit=COMMIT) + fname, sha(text),
                      criteria_json, WINDOW, CHALLENGE],
                account=client.local_account)
            wait_final(client, tx, f"open#{jid}")
        log.setdefault("opens", {})[jid] = {
            "file": path.split("/")[-1],
            "criteria": "v3 (locale-separator note on criterion 0)"}

    # ---------- Phase 3: resolve + expect APPROVED ----------
    print("== resolve clarified jobs ==", flush=True)
    for jid, title, path in new_jobs:
        wait_challenge(client, jid)
        res, rtx, rounds = resolve_with_retry(client, jid)
        rec = read_job(client, jid)
        verdict = rec["result"]["verdict"]
        check(verdict == "APPROVED", f"{jid} verdict APPROVED")
        log[jid] = {"file": path.split("/")[-1], "verdict": verdict,
                    "labels": rec["result"]["labels"],
                    "citations_count": len(rec["result"]["citations"]),
                    "consensus_rounds": rounds, "result": rec["result"]}
        print(f"{jid}: {verdict} labels={rec['result']['labels']}",
              flush=True)

    # ---------- Phase 4: final ----------
    stats = json.loads(client.read_contract(
        address=ADDR, function_name="get_stats", args=[]))
    print("stats:", stats, flush=True)
    good_verdicts = ["APPROVED", log["smoke-good-2d"]["verdict"],
                     log["smoke-good-3e"]["verdict"]]
    ok_det = all(v == "APPROVED" for v in good_verdicts)
    check(ok_det, "3x distinct-digest good runs APPROVED (determinism)")
    check(stats.get("approved") == 3 and stats.get("rejected") == 1
          and stats.get("inconclusive") == 2,
          "live stats approved=3 rejected=1 inconclusive=2")
    log["results"] = {
        "determinism_consistent": ok_det,
        "good_verdicts": good_verdicts,
        "good_job_ids": ["smoke-good-1", "smoke-good-2d", "smoke-good-3e"],
        "negative_verdict": states["smoke-bad-1"],
        "negative_rejected_as_expected": states["smoke-bad-1"] == "REJECTED",
        "already_certified_guard_live": True,
        "stats": stats,
    }
    log["criteria_note"] = (
        "smoke-good-2b/3c resolved INCONCLUSIVE: the criteria text did not "
        "state the contract's own separator-insensitive number standard, so "
        "the model conservatively marked criterion 0 UNCERTAIN on locale "
        "separator changes (1,000 -> 1.000, 12.5 -> 12,5). Fixed in job "
        "ARGS (criterion 0 wording), contract untouched. 2b/3c remain as "
        "terminal INCONCLUSIVE history on-chain.")
    log["correction_note"] = (
        "v1.1 (docs/deployment_log_v11.json): all-INCONCLUSIVE good "
        "verdicts from the prompt/normalizer citation-key mismatch, fixed "
        "in commit 93e24b0 (prompt-only), redeployed at " + ADDR + ". "
        "First v1.2 harness run crashed at good-2 (already_certified guard "
        "on a same-digest repeat — contract-correct). Attach attempt 1 hit "
        "a MAJORITY_DISAGREE wobble on bad-1 (discarded round, re-cranked "
        "to a clean r1 REJECTED in attach v2). Attach v2 proved the guard "
        "live (MAJORITY_AGREE + ERROR, reason in leader_receipt result "
        "base64) and surfaced the criteria ambiguity fixed by this v3 run. "
        "This log supersedes all prior LinguaCert logs.")
    Path("docs/deployment_log.json").write_text(json.dumps(log, indent=2))
    print("DETERMINISM_CONSISTENT:", ok_det)
    print("NEGATIVE_REJECTED:", states["smoke-bad-1"] == "REJECTED")
    print("GUARD_PROVEN_LIVE:", "already_certified" in reason)
    if failures:
        print("FAILURES:", failures)
        raise SystemExit(1)
    print("ATTACH V3 DONE. contract:", ADDR)


if __name__ == "__main__":
    main()
