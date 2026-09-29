## 43 — the merge-speed guard counts SQLite ticks only, and a pure-Python loop is invisible to it

**The limit.** `harness/tests/t7_box_map.py:check_merge_speed` asserts a 500-into-500 box
merge does linear work. It counts `sqlite3.Connection.set_progress_handler` ticks on the
write's own connection, against a `30 * moved` ceiling. Wall time stays only as a loose 10 s
backstop. The tick count is proportional to rows SQLite itself scans. A regression that adds
a pure-Python `O(n^2)` loop over the merged cards would add no query and no extra row scan.
That regression would not move the tick count at all.

**Measured, 2026-09-26.** A pure-Python `O(n^2)` scan over the fixture's 500 cards is
invisible to the guard. It adds no SQLite work, so the tick count stays unchanged. It also
costs too little wall time to trip the backstop. At `n=2000`, four times the fixture, the
same shape of loop measured 3.9 s. That is still under the 10 s backstop. The fixture's own
`n=500` is nowhere near the size a quadratic Python loop needs to reach ten seconds.

**Why it is not fixed.** The tick-count design in T7 review item 4 is deliberate. It is
correct for the defect it was built to catch. That defect was the pre-R3 regression, where
`move_card` recomputed `next_index`/`next_key` per card. That work is SQL work, so it does
move the tick count (measured 17x). The design was never meant to catch every possible
quadratic regression, only that one. Closing this gap needs one of two things. Either a
fixture large enough that a Python `O(n^2)` loop trips the wall-time backstop on its own. Or
a second signal that counts Python-side work, such as a call count on the merge's own hot
function. The choice is the owner's.

**The fix, not built.** Raise the fixture's `n` until a synthetic `O(n^2)` Python loop
reliably trips the 10 s backstop, measured rather than guessed. Or add a call-count assertion
on the merge's own per-card function, beside the tick count rather than replacing it.

Cites the T7 review's ruling, "Timing guards must count work, not wall time alone", and `harness/tests/t7_box_map.py:check_merge_speed`.
