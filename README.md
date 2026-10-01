# LinguaCert — Trustless Translation Certification

GenLayer Intelligent Contract that certifies translations by consensus:
a client commits a hash-pinned **source text** and a candidate
**translation** (plus natural-language acceptance criteria), and the
network adjudicates whether the translation is faithful.

**Verdicts:** `APPROVED` (certified, digest registered) /
`REJECTED` / `INCONCLUSIVE`.

Certification is a quality opinion by validator consensus — it is NOT a
substitute for sworn or human certified translation.

## Why this needs GenLayer (and not just an LLM API)

A translation quality decision determines whether work gets accepted —
the client and the translator are adversaries, so a single LLM API call
from either side proves nothing. LinguaCert puts the decision where
independent validators re-execute the same evaluation and only converge
on stable, evidence-backed substance.

## Two independent decision layers

1. **Deterministic forensics (contract-computed, model-independent).**
   Every numeral, URL and `{placeholder}`/`%s` marker in the source must
   be preserved in the translation (separator-insensitive: `1,000` ==
   `1.000`; markdown enumerators excluded). Any violation forces
   `REJECTED` **regardless of what the model says**.
2. **LLM judgment with verifiable citations.** Per-criterion
   `PASS/FAIL/UNCERTAIN` labels; every `PASS` must stand on a verbatim
   quote of the translation itself, every `FAIL` must cite evidence
   (any document), and every quote is re-validated on-chain against the
   fetched, hash-pinned bytes. A fooled model can at worst mis-tag a
   real quote — it cannot fabricate evidence. Any unproven label yields
   `INCONCLUSIVE`.

The verdict is always derived by the contract from labels + gates —
never chosen by the model. Every LLM failure mode (exception, non-JSON,
wrong shape, dead fetch, tampered digest, oversized/thin documents)
degrades to a well-formed `INCONCLUSIVE` that never registers a
certification.

## Additional guarantees

- **Hash-pinned evidence**: all documents are committed by sha256 and
  fetched from an immutable `raw.githubusercontent.com/<user>/<repo>/<full-commit>/…`
  URL; a digest mismatch or oversize fails closed (never audited as a
  prefix).
- **Challenge period**: no job reaches terminal certification before its
  immutable, node-clock-enforced deadline.
- **Dispute path**: anyone may dispute an unresolved job; a dispute buys
  a full fresh response window and up to 3 rebuttal evidence documents;
  resolution before the deadline reverts.
- **Fair fetch budgets**: per-category character budgets split evenly
  across evidence items, capped by a hard total.
- **Single certification**: an `APPROVED` translation digest is
  registered; a second job with the same digest can never resolve.
- **Prompt-injection resistance**: fetched texts are framed as DATA; the
  deterministic forensics gate holds even when the model is fooled.

## Layout

```
contracts/linguacert.py     # the Intelligent Contract (540 lines)
tests/direct/test_linguacert.py  # 73 direct-mode tests (real GenVM)
scripts/deploy_smoke.py     # Studionet deploy + live consensus smoke
examples/                   # hash-pinned smoke fixtures (EN source, ID translations)
docs/                       # deployment log + verification notes
```

## Testing

```bash
pip install -r requirements-dev.txt
pytest tests/direct/ -q        # 73 passed
```

Lint (Python 3.12 venv):

```bash
GENVMROOT=/tmp/genvmroot genvm-lint check contracts/linguacert.py
# 3 checks passed, contract valid: 9 methods (4 view, 5 write)
```

## Live evidence

See `docs/SUBMISSION_DRAFT.md` (contract address, tx hashes, explorer
links) — every claim is one click away on the Studionet explorer.

## Scope note (honest limits)

- Consensus-stable LLM labels require criteria phrased so independent
  validators can reach the same conclusion; criteria are client-authored
  and not validated for fairness.
- Forensics cover numbers/URLs/placeholders and length metadata — not
  full semantic fidelity (that is the LLM layer's job).
- `INCONCLUSIVE` is a first-class outcome by design: the contract never
  guesses.
