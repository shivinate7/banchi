## DEBT56 — the worktree-provision selftest's race case fails

**Symptom.** `make worktree-provision-selftest`, the case "two concurrent runs launch only one
npm ci", reports `FAIL neither concurrent run reported an already-running install`. The case
launches two `scripts/worktree-provision.sh` runs together over a stub `npm`. It expects the
losing run to print "already running".

**Measured.** It fails on `origin/main`'s own script and on the branch that added
`--foreground`, so this branch did not cause it. Three runs out of three failed. It stayed red
after the stub's sleep went from 1s to 4s. In one run the case also counted two `npm ci`
launches, where it expects one. Both measurements came from the builder and from the
reviewer. The other 21 cases pass once the fixture carries `scripts/reap_mark.py` and
`scripts/reap.py`.

**Likely cause, not proved.** The loser reads the lock before the winner has written its
pidfile. `serve.live_pid` then answers "dead", and the loser reclaims the lock instead of
reporting an install already running. That also explains a second launch. Unmeasured: no run
captured the interleaving.

**Left unfixed on purpose.** The race is older than the branch that found it. The fix belongs
in the lock handshake of `scripts/worktree-provision.sh`, not in the selftest's stub.
