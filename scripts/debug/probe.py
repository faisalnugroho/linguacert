#!/usr/bin/env python3
"""One-shot debug probe: deploy LinguaDebug, run ONE full-consensus probe
against the v1.1 examples, print the RAW model output. Diagnostic tool."""
import hashlib
import json
from pathlib import Path

from genlayer_py import create_client, create_account
from genlayer_py.chains import studionet
from genlayer_py.types import TransactionStatus

COMMIT = "9a6ac230cc9660d8ed31ce32fcc68d7c9550738e"
KEYFILE = Path("scripts/smoke_deployer.json")
RAW = ("https://raw.githubusercontent.com/faisalnugroho/linguacert/"
       "{commit}/examples/")

data = json.loads(KEYFILE.read_text())
account = create_account(account_private_key=data["private_key"])
client = create_client(chain=studionet, account=account)
print("deployer:", account.address)

code = Path("scripts/debug/linguadebug.py").read_text()
tx = client.deploy_contract(code=code, account=client.local_account,
                            args=[], leader_only=True)
receipt = client.wait_for_transaction_receipt(
    transaction_hash=tx, status=TransactionStatus.FINALIZED,
    retries=100, interval=3000)
addr = (receipt.get("data") or {}).get("contract_address")
print("debug contract:", addr)

criteria = [
    "The translation preserves every quantity, date and technical number "
    "from the source.",
    "The translation keeps all URLs, code identifiers and placeholders "
    "such as {machine_id} unchanged.",
    "The translation reads as natural, grammatically correct Indonesian "
    "with correct domain terminology.",
]
base = RAW.format(commit=COMMIT)
tx = client.write_contract(
    address=addr, function_name="probe",
    args=["p1", json.dumps(criteria), base + "source-en.md",
          base + "translation-id-good.md", "index"],
    account=client.local_account)
receipt = client.wait_for_transaction_receipt(
    transaction_hash=tx, status=TransactionStatus.FINALIZED,
    retries=100, interval=3000)
print("probe vote:", receipt.get("result_name"),
      "exec:", receipt.get("tx_execution_result_name"))

raw = client.read_contract(address=addr, function_name="get", args=["p1"])
out = json.loads(raw)
print("docs_len:", out.get("docs_len"))
print("=== RAW MODEL OUTPUT ===")
print(out.get("raw"))
