## 20 — Two liveness oracles read a pid, and a recycled one lies to both

**Recorded 2026-09-11 with D33's amendment**, which made the capture server hold the `Popen` of
each identify child it spawns and reap it by polling. That closes the zombie — an unwaited child
holding a pid `os.kill(pid, 0)` accepts — for every run *this* server started. Two gaps are left,
and neither is closed:

- **A run orphaned across a restart.** With no handle, `_live_pid` falls back to signal 0 over
  `running.pid` with the run's own `identifications.json` as the floor. That narrows a reused pid
  to one case — a run killed mid-batch, which never writes the record — but does not remove it.
  The closer is in the tree already and is not wired here: `scripts/serve.py:live_pid` reads
  `ps -p <pid> -o command=` and requires a distinguishing absolute path in the argv. It was
  declined because it forks `ps` inside a path polled every four seconds, it fixes nothing about
  the root cause, and it would break T7's own `os.getpid()` gestures, whose argv names
  `harness/run.py` rather than a run directory.
- **A recycled pid in `.serve/*.pid` widens what `reap` will not touch.** `scripts/reap.py`'s
  `protected_pids` takes signal 0 at face value, so a stale record whose pid now belongs to
  something else protects that process and its descendants. This is the SAFE direction and
  matches that file's stated default — *"a pid with no readable evidence is UNKNOWN and
  therefore refused"* — and a corpse already has a designed verdict there, `GONE`. It is recorded
  because it is the same call with the same blind spot, not because it is the same defect.

**What is measured:** the zombie, by hand, and the fix against it — seven mutation arms over
T7's block, all red. **What is not:** either row above, and the two lines `_child_of`'s docstring
argues against the CPython source rather than asserts — the eviction guard, which cannot be posed
without sixty-four spawns, and the false-alive answer the lock prevents, which is a race that
cannot be produced on demand.
