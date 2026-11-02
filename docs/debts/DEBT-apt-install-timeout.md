## DEBT-apt-install-timeout — a package install in design-check can fail a shard on a mirror stall

**What.** The install step in `design-check`, which installs the build tools and fonts, runs `apt-get` under two 60 s timeouts, and when both expire it exits 124 and fails the shard before any test runs.

- **Job.** `design-check (8)`, run 2668 (id 39706607546). The step took two minutes and exited 124. No test ran. The `check` job also went red, as the rollup of this shard.
- **Measured.** 1 of the 100 most recent completed main check runs (window run numbers 2489 to 3148). The step carries `Acquire::Retries=3` and its own retry (`install || install`), and the check still ran out.
- **Cause.** Found in part. The step's own timeouts expired, so the package mirror did not answer in time. The log does not say why the mirror stalled. Not read: other runs of the same step, which passed.
- **Owner.** shivinate7. **Fix by.** 2026-12-01 (D308, a deadline date is allowed).
- **Outcome at risk.** A clean tree shows red on main, and the next real red is harder to see. The rerun is the only cure, and it costs a full matrix.
- **Closes when.** A mirror stall cannot fail a shard alone. The step either caches its packages or retries on a longer clock, and a red from it is named as one in the run log.
