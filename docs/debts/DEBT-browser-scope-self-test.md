## DEBT-browser-scope-self-test — the browser-scope self-test went red on main in three runs

**What.** The `ci-check (ci-check-guards-1)` job failed in `audit-self-test` on three main runs, with two rows red. The rows are `the recording guard mutation changes the workflow it mutates` and `a pass record written for a skipped matrix is refused`.

- **Job.** `ci-check (ci-check-guards-1)`, `audit-self-test`. Runs 2489, 2490 and 2493 (window run numbers 2489 to 3148). The job did not go red again in the window after run 2493.
- **Cause.** Partly read. The two rows test the recording guard and the pass record for a skipped browser matrix, which both sit in the browser-matrix gate of `check.yml`. Not read: which change broke the rows, and which change ended the reds.
- **Owner.** shivinate7. **Fix by.** 2026-12-01 (D308, a deadline date is allowed).
- **Outcome at risk.** The gate that records a browser pass could accept a skipped matrix as a pass, or refuse a real one. The self-test guards both.
- **Closes when.** The cause is written here, and the rows stay green on main for the window.
