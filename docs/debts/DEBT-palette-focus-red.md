## DEBT-palette-focus-red — the palette input's focus check goes red on design-check shard 8

**What.** `tests/nav.spec.ts` (`ux-wave1: the palette input shows a focus indicator when focused`) goes red on `design-check (8)` when the focused palette input shows no outline and no box-shadow change.

- **Test and job.** `design-check (8)`, `nav.spec.ts` (line 1048 in run 2503 and run 2569, line 1055 in run 2832; same test). The message: `focused palette input has no outline or box-shadow change`.
- **Measured.** Red on the first attempt in 3 of the 100 most recent completed main check runs (run numbers 2503, 2569 and 2832; window run numbers 2489 to 3148). No retry is set.
- **Cause.** Cause unread. The read is taken after focus. The log has no timing data for it. Not read: the trace. Not done: a local run of shard 8.
- **Owner.** shivinate7. **Fix by.** 2026-12-01 (D308, a deadline date is allowed).
- **Outcome at risk.** Keyboard focus on the palette input is a floor the product states. A red can mean a missing focus ring, or a read taken before the ring draws. The log cannot tell which.
- **Closes when.** The cause is written here. Then the read waits for the ring, or the missing ring is fixed.
