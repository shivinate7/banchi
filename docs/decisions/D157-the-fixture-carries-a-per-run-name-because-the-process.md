## D157 — The fixture carries a per-run name, because the process table is the one thing a run cannot have its own of

**Built 2026-09-12, after `make reap-selftest` went red four times over a `scripts/reap.py` and a `scripts/reap-selftest.sh` byte-identical to `origin/main`.** The failing arm was the one this file may never fail — `KILLING ITS OWN PROCESS IS ALLOWED`:

```
FAIL   a session was refused its own process — the constraint this must not break
BLOCKED: this would signal a process this session did not start.
  pid NNNNN — outside this checkout
  resolved: pgrep -f mine.py -> NNNNN, MMMMM
```

**The guard was right every one of those four times, and so was the diff.** `scripts/reap.py --hook` resolves a kill's real targets by running `pgrep -f` itself, across the whole machine — that is D127's entire design, and the reason `pkill -f capture_server.py` can be allowed on Monday and refused on Tuesday. The fixture spawned its process from the fixed script name `mine.py` into a per-run `mktemp -d`. So a SECOND live `mine.py` anywhere on the machine sat in a different, often already-deleted checkout, was correctly judged outside this one, and reddened the commit path over a process in nobody's diff.

**Two things put a second one there, and neither is exotic on this machine.** A concurrent `make check` from another of this clone's ~30 worktrees, and a `time.sleep(300)` left behind by a run that never reached its `EXIT` trap. The leak is structural rather than careless: `spawn` starts every child with `start_new_session=True` precisely so a `killpg` inside the suite can never reach the suite, which also means the SIGINT that stops a `make check` never reaches the children, and a `-9` runs no trap at all.

### This is D122's shape one register down, and it takes the opposite answer

**D122 is the precedent and it is about the same kind of resource**: a per-checkout fixture over something the machine has only one of. There the resource is the CPU, and the answer is a machine-wide `flock` that REFUSES rather than queues, exiting 75 so a refusal can never read as a failing suite.

**A lock is the wrong answer here, for a reason D122 itself supplies.** That target is deliberately not on the commit path; `make reap-selftest` is in `make check`, which every branch runs. A machine-wide lock over a `make check` member makes one tree's suite block or refuse because another tree is committing, which is a worse failure than the one being fixed. And the resource in question is not scarce: **a process NAME costs nothing, so the fixture is made unable to collide instead of being made to take turns.** Every script it starts is `<role>-<mktemp suffix>-<pid>.py` — the suffix is unique among the temp directories alive at the moment it was made, and the pid distinguishes a run that inherits a suffix `mktemp` has since freed.

**The same ambiguity was in the port and it is fixed the same way.** The suite walked 53900–53960 for a port nothing answered on and took the first, which is a reading and not a reservation: two runs probing together both find one free because neither has bound it yet. The loser's client then connects to the winner's listener, three pids hold one port, and the reproduction case fails with every case under it vacuous by this file's own admission. The listener now binds port 0 and reports what the kernel gave it. **The kernel cannot hand one port to two processes, which is exactly the property the probe did not have.**

### The arm reproduces it rather than asserting about it

**A rival fixture is built by the same naming rule and left running while this run asks the guard to kill its own process.** It gets its own `mktemp -d`, its own tag, its own `mine`. With the tag the two names cannot collide and the kill is allowed; spell a fixed name in the rule and the rival gets the same fixed name, `pgrep` returns both, and the arm goes red. **Naming the decoy by hand would have been the wrong construction** — a hand-written decoy survives the very mutation this arm exists to catch, and would have passed straight over the bug.

**It is two cases and not one**, because a case that passes when `pgrep` finds nothing is worth nothing: the rival's OWN name is then judged from this checkout and must still be refused for living elsewhere. Together they say the names are unique, not that the guard stopped looking. Measured: reverting the naming rule alone turns exactly that arm red, 1 FAILED and 32 passed.

**And two runs now pass together, which they could not before.** Three rounds of two concurrent `make reap-selftest`, 33 of 33 each.

### What is fixed, and what is only made harmless

**A leftover is now harmless rather than absent, and those are different claims.** The tag means a survivor from an earlier or concurrent run cannot be resolved by this run's command, which is the whole defect. Beside it, each sleeper watches its own script file and exits when it is deleted, so `cleanup`'s `rm -rf` ends this run's processes instead of only signalling them, and the trap waits for them to be GONE before giving up and sending `-9`. **What is NOT claimed is that nothing ever survives**: a run killed with `-9` deletes nothing and runs no trap, and its sleepers stand until their own deadline. That case is covered by the tag and by nothing else, which is the right division — the deadline is a backstop, and an arm whose subject died early fails for the wrong reason.

**`pgrep -fc` is not a count on BSD.** It returns 0 and reads as "no orphans", which is how a leftover measurement can come back clean on this machine. Count with `pgrep -f ... | wc -l`.
---
