## DEBT-escape-runner-red — the assertion after Escape goes red on the CI runner, and the cause is unread

**What.** A `design-check` shard fails on the assertion right after `keyboard.press('Escape')` in `capture-claims.spec.ts`, `live-reconcile.spec.ts` or `markdown.spec.ts`, and it does so on the CI runner.

- **Moved from.** DEBT8 (an entry that says no work is proposed). This item carries an owner and a fix-by date, so it lives here.
- **Rate.** The rate DEBT8 once gave, about one job in thirteen, is not borne out. In the 100 most recent completed main check runs (window run numbers 2489 to 3148) there were 19 first-attempt reds, and none of the 19 shows an Escape failure.
- **Cause.** Cause unread. The same sequence passed 555 of 555 times outside the suite, so the suite around it is part of the mechanism.
- **Tried.** The count of main runs above. Trace read: no, because no Escape failure appears in the window to read.
- **Trace.** `app/playwright.config.ts` keeps a trace on failure under `CI`. The first trace should show whether the track is open at the Escape.
- **Workaround.** `gh run rerun <id> --failed`. A retry in the spec would hide the mechanism.
- **Owner.** shivinate7. **Fix by.** 2026-12-01 (D308, a deadline date is allowed).
- **Outcome at risk.** A check that goes red on a runner and clears on rerun costs a run, and a rerun can hide a real defect behind it.
- **Closes when.** The cause is written here, from a trace, or the assertion is shown not to race the Escape.
