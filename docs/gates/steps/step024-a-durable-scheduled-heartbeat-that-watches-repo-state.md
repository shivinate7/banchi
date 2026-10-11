24. ~~**A durable scheduled heartbeat that watches repo state across
    sessions**~~ — **done.** `scripts/heartbeat.py` is a thin caller of what already existed. It is not a fourth reader of the same facts.

    It reads `scripts/coordinator.py --json` for open PRs pinned to their head SHA, `id claims`, dirty worktrees and live sessions. It also reads two things coordinator does not answer. The first is whether MAIN's own last push is green. Coordinator's `block_main` compares local main only against origin/main, never CI. The second is `make janitor`'s own preview, with `--confirm` never passed.

    It writes `.serve/heartbeat/latest.json` and appends `.serve/heartbeat/history.jsonl`. This is the durable state that a fresh, context-free run needs. The item's own note sets two binding constraints: never a daemon, and each run remembers nothing on its own. So anything that needs memory of a PREVIOUS run must live in a file.

    `new_since_last_run` diffs this run's open PRs and worktrees against the previous `latest.json`. That answers the bullet "a pull request now conflicting with a live session that has not been told". Whether a session has been told is exactly whether its PR was already in the last report.

    Read-and-report authority only. It never merges. The underlying `janitor.py` and `coordinator.py` calls carry nothing that presses anything.
