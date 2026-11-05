# Harness

T1-T9. The Stop hook runs it at every turn end; the pre-commit hook does not.

## Code files

- `harness/run.py` — The explicit ordered TESTS registry — no discovery magic.
  - Decisions: `D1`
