## 43 — the merge-speed guard counts SQLite ticks only, and a pure-Python loop is invisible to it

`harness/tests/t7_box_map.py:check_merge_speed` asserts a 500-into-500 box merge does linear work. It counts `sqlite3.Connection.set_progress_handler` ticks on the write's own connection against a `30 * moved` ceiling, with wall time only as a loose 10s backstop. A pure-Python `O(n^2)` loop over the merged cards adds no query and no row scan, so it does not move the tick count. Measured: at `n=2000`, four times the fixture, such a loop took 3.9s, under the backstop. The tick design is deliberate. It catches the defect it was built for, `move_card` recomputing `next_index` and `next_key` per card (SQL work, measured 17x), and was never meant to catch every quadratic regression.

**Outcome at risk.** A quadratic Python regression in the merge ships with the guard green.

**Closes when.** Either the fixture's `n` rises until a synthetic `O(n^2)` Python loop trips the 10s backstop, measured and not guessed, or a call-count assertion on the merge's own per-card function joins the tick count. The choice is the owner's.
