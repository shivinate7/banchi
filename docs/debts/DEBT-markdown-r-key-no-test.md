## DEBT-markdown-r-key-no-test — The markdown sheet's R-key stand-down has no test

**What.** The live code already stands down for a bare `R`. `ReloadButton` in `app/src/kit/index.tsx` ignores `R` in an input and while `[aria-modal="true"]` is open. The percent field strips all but digits and `.`. The gap is that no test in `app/tests/pricing-markdown.spec.ts` presses `R`. The case lived in `app/tests/markdown.spec.ts`. Commit 91792271, which deleted that spec, did not port it.

**Outcome at risk.** An in-flight survey is discarded while the operator types a percentage (D105, markdowns live where prices are decided).

**Closes when.** `app/tests/pricing-markdown.spec.ts` presses `R` in the sheet's field and asserts that no reload runs and the survey is kept. The test goes red on a build that drops the stand-down, and green on the current code.
