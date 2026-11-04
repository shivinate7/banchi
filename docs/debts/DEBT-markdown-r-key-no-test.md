## DEBT-markdown-r-key-no-test — The markdown sheet's R-key stand-down has no test

**What.** In the markdown sheet, a bare `R` typed into the "Cut, percent" field still calls `load()`, which re-reads the worklist and the corpus and discards an in-flight survey. No test in `app/tests/pricing-markdown.spec.ts` presses that key. The case lived in `app/tests/markdown.spec.ts` and was deleted with the sheet's spec. It was not ported.

**Outcome at risk.** An in-flight survey is discarded while the operator types a percentage (D105, markdowns live where prices are decided).

**Closes when.** `app/tests/pricing-markdown.spec.ts` presses `R` in the sheet's field and asserts that no reload runs and the survey is kept. The test goes red on a build that drops the stand-down, and green on the current code.
