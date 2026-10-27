## 4 — Criteria and evidence: three ways a row goes quiet

**What.** Three checks of a gate's evidence go quiet without a finding: a renamed evidence source, a score file the glob does not match, and a partial history replay that exits 0.

- **`EVIDENCE_SOURCES` is three unvalidated path literals** (`harness/tests/t1_id_eval.py`, `harness/eval/fixtures.py`, `identify/prompt.py`). Nothing resolves them, so renaming one silently retires the `evidence freshness` row.
- **The evidence glob assumes one convention.** `check_criteria_evidence` globs `t1*.json`. A score file named otherwise is invisible rather than a finding, while the summary claims coverage of every registered test.
- **A partial `make audit-history` replay exits 0.** Its summary counts carry no mark that some trees did not run.

**Outcome at risk.** A gate reads as evidenced when its evidence went unread.

**Closes when.** Both read from the registered tests (`harness/run.py:TESTS`) instead of a literal, and a path that does not resolve is a finding.
