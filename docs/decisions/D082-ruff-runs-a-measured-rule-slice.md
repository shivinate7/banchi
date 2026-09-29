## D82 — Ruff runs a measured rule slice

**`ruff.toml` pins `target-version = "py39"` and selects exactly `E4`, `E7`, `E9`, `F`, `B` and `SIM`, never ruff's defaults.** `--fix` is never run on this codebase without a harness run after, and it is wired nowhere (D18: nothing that writes runs on the path that decides a commit). `make lint` runs ruff behind `RUFF_GUARD`, so a missing dependency fails loudly.

- **The version must be told the truth.** The venv is Python 3.9.6, and `X | None` outside a deferred annotation is a runtime `TypeError`. Zero-config ruff found 2,131 things, and 79% were pyupgrade rewriting `Dict`, `List` and `Optional` to newer syntax. Told `py39`, ruff itself stops trusting those rewrites.
- **The tool pattern-matches syntax and has no types.** `SIM118` rewrote `for game in games.keys()` in `cli/resolve.py`, where `games` is the `pipeline.games` module, into a `TypeError`. It was caught by the harness, not by ruff, so those sites carry `# noqa: SIM118`. `SIM115` flags deliberately long-lived handles (the `flock` handle in `store/files.py`, the log handle of a detached `Popen`) and `B023` flags a closure consumed within its loop iteration. Each carries a `# noqa` naming the invariant.
- **The other ~890 default rules stay off.** Widening the slice repeats the process: run it, read every finding by hand, and record what is real before it gates anything.
