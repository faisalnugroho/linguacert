#!/usr/bin/env python3
"""Deploy LinguaCert to Studionet + live consensus smoke test.

Built from the known-good deploy_smoke_studionet template (Aug 2026).
Usage:
  ~/genlayer-env/bin/python scripts/deploy_smoke.py > smoke.log 2>&1
Requires a gitignored keyfile scripts/smoke_deployer.json with
{"address": ..., "private_key": "0x..."}.
"""
import hashlib
import json
import time
from pathlib import Path

from genlayer_py import create_client, create_account
from genlayer_py.chains import studionet
from genlayer_py.types import TransactionStatus

# ---------------- CONFIG ----------------
CODE_PATH = Path("contracts/linguacert.py")
KEYFILE = Path("scripts/smoke_deployer.json")   # gitignored!
COMMIT = "3928ad0477bf5abf33596e81455dba04884289c0"  # linguacert examples commit
RAW = "https://raw.githubusercontent.com/faisalnugroho/linguacert/{commit}/examples/"
DETERMINISM_RUNS = 3
CHALLENGE = 300      # 5 min challenge window for the smoke (min allowed)
WINDOW = 3600
CHALLENGE_WAIT = 320  # seconds to sleep after opens before resolving
# ----------------------------------------

log = {}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pinned(commit, name):
    url = RAW.format(commit=commit) + name
    assert len(url) <= 400
    return url


def load_account():
    data = json.loads(KEYFILE.read_text())
    return create_account(account_private_key=data["private_key"])


def wait_final(client, tx_hash, label, strict=True):
    """FINALIZED wait gating on BOTH consensus vote and leader execution.

    `result_name` is the consensus VOTE, never the exec result. A
    DISAGREE/NO_MAJORITY round finalizes but DISCARDS the state change —
    with strict=False the caller may re-crank the SAME job id.
    """
    receipt = client.wait_for_transaction_receipt(
        transaction_hash=tx_hash,
        status=TransactionStatus.FINALIZED,
        retries=100,
        interval=3000,
    )
    if isinstance(receipt, dict):
        data = receipt.get("data") or {}
        addr = (data.get("contract_address")
                if isinstance(data, dict) else None)
        if addr is None:
            addr = receipt.get("to_address")
        leader = (receipt.get("consensus_data") or {}).get(
            "leader_receipt", [{}])
        lead = leader[0] if leader else {}
        exec_result = lead.get("execution_result")
        vote_result = receipt.get("result_name") or "UNKNOWN"
        if receipt.get("tx_execution_result_name") is not None:
            exec_result = receipt["tx_execution_result_name"]
        stderr = str((lead.get("genvm_result") or {}).get("stderr") or "")
    else:
        addr = getattr(receipt, "contract_address", None)
        exec_result = None
        vote_result = "UNKNOWN"
        stderr = ""
    ok = (exec_result in (None, "SUCCESS", "FINISHED_WITH_RETURN")
          and vote_result in ("MAJORITY_AGREE", None))
    print(f"[{label}] FINALIZED vote={vote_result} exec={exec_result}"
          " ok={ok}".format(ok=ok), flush=True)
    if not ok:
        print("CONSENSUS/EXECUTION FAILED:")
        print(json.dumps(receipt.get("consensus_data"), default=str)[:2000])
        if stderr:
            print("STDERR tail:", stderr[-1500:])
        if strict:
            raise RuntimeError(
                f"{label} failed: vote={vote_result} exec={exec_result}")
        print(f"[{label}] state change discarded — record remains unresolved")
    return {"execution_result": exec_result or "SUCCESS",
            "vote_result": vote_result, "ok": ok,
            "contract_address": addr, "stderr_tail": stderr[-1500:]}


def main():
    account = load_account()
    client = create_client(chain=studionet, account=account)
    print("deployer:", account.address, flush=True)

    if not COMMIT:
        raise SystemExit("Set COMMIT in scripts/deploy_smoke.py to the full "
                         "40-hex commit of the pushed examples first.")
    commit = COMMIT
    code = CODE_PATH.read_text()
    tx = client.deploy_contract(code=code, account=client.local_account,
                                args=[], leader_only=True)
    res = wait_final(client, tx, "deploy")
    addr = res["contract_address"]
    log["deploy"] = {"tx_hash": tx, "address": addr}
    print("CONTRACT:", addr)
    print("explorer: https://explorer-studio.genlayer.com/address/" + addr)

    good = Path("examples/translation-id-good.md").read_text()
    dropped = Path("examples/translation-id-dropped-values.md").read_text()
    source = Path("examples/source-en.md").read_text()
    criteria_json = json.dumps([
        "The translation preserves every quantity, date and technical "
        "number from the source.",
        "The translation keeps all URLs, code identifiers and placeholders "
        "such as {machine_id} unchanged.",
        "The translation reads as natural, grammatically correct Indonesian "
        "with correct domain terminology.",
    ])
    jobs = [
        ("smoke-good-1", "Maintenance manual EN->ID", good,
         "translation-id-good.md"),
        ("smoke-good-2", "Maintenance manual EN->ID", good,
         "translation-id-good.md"),
        ("smoke-good-3", "Maintenance manual EN->ID", good,
         "translation-id-good.md"),
        ("smoke-bad-1", "Maintenance manual EN->ID (dropped values)",
         dropped, "translation-id-dropped-values.md"),
    ]

    # Phase 1: open every job; the challenge clocks run in parallel.
    for jid, title, translation, fname in jobs:
        tx = client.write_contract(
            address=addr, function_name="open_job",
            args=[jid, title,
                  pinned(commit, "source-en.md"), sha(source),
                  pinned(commit, fname), sha(translation),
                  criteria_json, WINDOW, CHALLENGE],
            account=client.local_account)
        wait_final(client, tx, f"open#{jid}")
        log.setdefault("opens", {})[jid] = fname

    print(f"challenge window: sleeping {CHALLENGE_WAIT}s ...", flush=True)
    time.sleep(CHALLENGE_WAIT)

    # Phase 2: resolve every job, read verdicts.
    verdicts = {}
    for jid, title, translation, fname in jobs:
        t0 = time.time()
        tx = client.write_contract(
            address=addr, function_name="resolve",
            args=[jid], account=client.local_account)
        wait_final(client, tx, f"resolve#{jid}")
        raw = client.read_contract(address=addr, function_name="get_job",
                                   args=[jid])
        record = json.loads(raw if isinstance(raw, str) else str(raw))
        verdict = record["result"].get("verdict")
        secs = round(time.time() - t0, 1)
        print(f"{jid}: {verdict} [{secs}s]", flush=True)
        verdicts[jid] = verdict
        log[jid] = {"file": fname, "verdict": verdict, "secs": secs,
                    "result": record["result"]}

    good_results = [verdicts[j[0]] for j in jobs
                    if j[0].startswith("smoke-good")]
    ok_det = len(set(good_results)) == 1 and good_results[0] == "APPROVED"
    neg_verdict = verdicts["smoke-bad-1"]

    log["results"] = {
        "determinism_consistent": ok_det,
        "good_verdicts": good_results,
        "negative_verdict": neg_verdict,
        "negative_rejected_as_expected": neg_verdict == "REJECTED",
    }
    Path("docs/deployment_log.json").write_text(json.dumps(log, indent=2))
    print("DETERMINISM_CONSISTENT:", ok_det)
    print("NEGATIVE_REJECTED:", neg_verdict == "REJECTED")
    print("DONE. contract:", addr)


if __name__ == "__main__":
    main()
