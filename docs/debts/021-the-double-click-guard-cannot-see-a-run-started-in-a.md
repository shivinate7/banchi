## 21 — The double-click guard cannot see a run started in a terminal

**Found 2026-09-11 while building D33's amendment, and older than it.**
`server/pipeline_routes.py:_run_box` argues at length that the guard must read the box out of the
capture path as well as the scope, *"or the screen could start a second batch over a box an agent
is already identifying"* — and `check_pipeline_routes` asserts that flow. But **`_spawn` is the
only writer of `running.pid` in the tree.** A run started by typing `pkmnscan identify` has no
marker, `_live_pid` returns `None` for it, and `_busy_run` skips it at the loop head. The T7 case
poses the pid by hand, so what it proves is `_run_box`'s path-reading, not the claim above it.

Unaffected by D33's amendment either way — a terminal run has no handle *and* no marker. The fix
is one line in `cli/cmd_identify.py`: write the marker there too, which would make the guard true
and put every terminal run in the fallback case. Not taken here because it widens a change that
is about a different defect, and because it wants its own T7 case.
