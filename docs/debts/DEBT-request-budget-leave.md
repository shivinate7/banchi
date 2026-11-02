## DEBT-request-budget-leave — the Capture screen's sweep read is counted as still asking after the screen is left

**What.** The test `a screen that is left stops asking, and what it had open is aborted` in `tests/request-budget.spec.ts` goes red on `design-check (11)` when a `GET /pipeline/match/sweep` read, sent by the Capture screen, is still open or is sent after the screen is left.

- **Test and job.** `design-check (11)`, `request-budget.spec.ts`, chromium. The message: `leave:#/capture: 1 paths keep asking after leaving (GET /pipeline/match/sweep), limit 0`.
- **Measured.** Red on the first attempt in 5 of the 100 most recent completed main check runs (run numbers 2561, 2636, 2781, 2852 and 3110, the window being run numbers 2489 to 3148). Run 3110 (id 40942631828) passed on its second attempt. No Playwright retry is set, so each red was a real assertion failure.
- **Cause.** Cause unread. The test counts two lists as one: reads still open when the screen was left (`kept`), and any path asked after leaving (`stale`). The log does not say which list held the sweep read.
- **Tried.** Read the `leave` case in `request-budget.spec.ts`. The Capture screen reads the sweep through `usePoll` (`CaptureScreen.tsx`, `fn: () => getMatchSweep()`). `usePoll` clears its timer on unmount, but its `fn` gets no abort signal, and `getMatchSweep` (`server.ts`) takes none. So the poll cannot abort a read that is in flight at unmount. Not read: whether the open-read scope abort in `server.ts` (the `OpenRead` controller) covers this read. Not done: the failing trace, and a local run of shard 11.
- **Lane.** The sweep path is in the photo lane (DEBT11, a parked writer still holds a request slot). The gap may sit in that lane's abort path, not in the poll.
- **Owner.** shivinate7. **Fix by.** 2026-12-01 (D308, a deadline date is allowed).
- **Outcome at risk.** A screen that keeps a read after it is left spends requests the budget does not allow. The check guards that budget, and a timing race can hide a real leak behind a red that clears on rerun.
- **Closes when.** The cause is written here, from the trace or a local run. Then either the leak is fixed, or the check is split so a read sent before the leave is not counted.
