## DEBT-capture-freeze-timing — two capture timing checks go red on design-check shard 4

**What.** Two timing checks in `tests/capture-freeze.spec.ts` go red on `design-check (4)`. One times out. The other fails when the median blocked time per capture grows past its limit.

- **Tests and job.** `design-check (4)`, `capture-freeze.spec.ts:292` (`50 captures while the dispenser deals`, run 2499, `Test timeout of 180000ms exceeded`) and `capture-freeze.spec.ts:297` (`hand-fed, captures 51 to 60 cost no more than captures 21 to 30`, run 2831, the median grew from 1052 ms to 1530 ms, against a limit of 1.4 times plus 30 ms).
- **Measured.** 2 of the 100 most recent completed main check runs (window run numbers 2489 to 3148). Both were red on the first attempt. No retry is set. Both shards ran with 2 workers.
- **Cause.** Cause unread. Both checks read timing across the captures of one run, so runner load moves them. The logs show the same drift on a loaded shard: the timed-out run measured a first-10 median of 4400 ms. Not reproduced. Not read: the load on the runner at the time.
- **Owner.** shivinate7. **Fix by.** 2026-12-01 (D308, a deadline date is allowed).
- **Outcome at risk.** A capture screen that slows as cards arrive would freeze the operator's sitting. These checks guard that. A red from runner load alone wastes the guard.
- **Closes when.** The cause is written here. Then each limit is set from a measured spread, or the check reads load alongside the timing.
