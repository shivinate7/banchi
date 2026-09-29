## DEBT54 — the 13th-row undo walk times out under load

**Deferred by the owner, 2026-09-28**, until the other capture-spec flake fixes land. Open.

`app/tests/capture-undo.spec.ts`, test "the stack is the whole sitting, newest first, and
reaches the 13th row". It shoots 36 cards, then clicks row 13 to undo back to card 24.

**Measured, 2026-09-28:**

- 7 of 10 failed alone, with other Playwright runs loading the machine. 5 failed inside
  `shoot()`, because a row's `aria-label` read "". 2 timed out on `keyboard.press('c')`.
- 4 of 10 failed in a whole-file `--repeat-each 10 --workers 8` run. The row count expected
  23 and read 26. It was still falling (35, 34, 33, 31, 29) when the 30s test timeout hit.

**Cause: unknown.** Two readings fit, and no run has told them apart. The product's undo walk
of 13 deletes may be slow. Or the test may only need more time for 36 shots and 13 deletes. The first is a product defect. The second is a budget.

**What a fix must keep:** every assertion the test makes, including 36 rows, 13 deletes in
order, and "23 recent". No retries and no loosened expectation.
