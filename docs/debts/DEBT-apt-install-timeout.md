## DEBT-apt-install-timeout — a package install in design-check can fail a shard on a mirror stall

**What.** The `Install make and DejaVu` step in `design-check` runs `apt-get update` and `apt-get install` under a 60 s `timeout` each, twice. When both runs of the step expire, it exits 124 and fails the shard without any test running.

- **Job.** `design-check (8)`, run 2668 (id 39706607546). The step took two minutes and exited 124. No test ran. The shard that failed was the only red job of that run.
- **Measured.** 1 of the 100 most recent completed main check runs (window run numbers 2489 to 3148). The step carries `Acquire::Retries=3` and its own retry (`install || install`), and the check still ran out.
- **Cause.** Found in part. The step's own timeouts expired, so the package mirror did not answer in time. The log does not say why the mirror stalled. Not read: other runs of the same step, which passed.
- **Owner.** shivinate7. **Fix by.** 2026-12-01 (D308, a deadline date is allowed).
- **Outcome at risk.** A clean tree shows red on main, and the next real red is harder to see. The rerun is the only cure, and it costs a full matrix.
- **Closes when.** A mirror stall cannot fail a shard alone. The step either caches its packages or retries on a longer clock, and a red from it is named as one in the run log.
