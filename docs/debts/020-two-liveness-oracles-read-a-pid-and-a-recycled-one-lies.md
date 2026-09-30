## 20 — Two liveness oracles read a pid, and a recycled one lies to both

- **A run orphaned across a server restart.** With no `Popen` handle, `server/pipeline_routes.py:_live_pid` falls back to signal 0 over `running.pid`, floored by the run's own `identifications.json`. A reused pid still reads as live for a run killed mid-batch, which never writes that record. `scripts/serve.py:live_pid` reads `ps -p <pid> -o command=` and closes it. It was declined because it forks `ps` inside a path polled every four seconds and would break T7's `os.getpid()` gestures.
- **A recycled pid in `.serve/*.pid`.** `scripts/reap.py:protected_pids` takes signal 0 at face value, so a stale record whose pid now belongs to another process protects that process. This is the safe direction, since `reap` refuses a pid with no readable evidence, and a corpse has a designed verdict, `GONE`.

**Outcome at risk.** A run reads `identifying` after a restart for as long as its pid is reused, and `reap` spares a process it should stop.

**Closes when.** `_live_pid` checks the argv the way `serve.live_pid` does, with a T7 case that poses a recycled pid. Unmeasured: `_child_of`'s eviction guard, which needs sixty-four spawns, and the false-alive race its lock prevents.
