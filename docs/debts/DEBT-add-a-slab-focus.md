## DEBT-add-a-slab-focus — focus does not land on Add a Slab after Remove on an empty list

**What.** `tests/slabs.spec.ts:1093` goes red on `design-check (10)` when focus does not land on Add a Slab after Remove, with the list read quickly and the list empty.

- **Test and job.** `design-check (10)`, `slabs.spec.ts:1093` (`after Remove by a click that focuses Remove and a quick list read, focus lands on Add a Slab`). The message: `focus did not land on Add a Slab when the list is empty`.
- **Measured.** Red on the first attempt in 3 of the 100 most recent completed main check runs (run numbers 2798, 2812 and 2813). Same test and message in all three. No retry is set.
- **Cause.** Cause unread. The title names a quick list read after the click, which suggests a race between the read and the focus move. Not verified. Not read: the trace.
- **Owner.** shivinate7. **Fix by.** 2026-12-01 (D308, a deadline date is allowed).
- **Outcome at risk.** After a keyboard user removes the last slab, focus lands nowhere, and the user loses their place.
- **Closes when.** The cause is written here, and the test stays green on main for the window.
