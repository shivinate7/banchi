24. ~~**A durable scheduled heartbeat that watches repo state across
    sessions**~~ — **done 2026-09-13.** `D200`. `scripts/heartbeat.py` —
    a thin caller of what already existed rather than a fourth reader of the same facts:
    `scripts/coordinator.py --json` for open PRs pinned to their head SHA, `id claims`, dirty
    worktrees and live sessions, plus two things coordinator does not answer — whether MAIN'S
    OWN last push is green (coordinator's `block_main` only compares local main against
    origin/main, never CI) and `make janitor`'s own preview, `--confirm` never passed. Writes
    `.serve/heartbeat/latest.json` and appends `.serve/heartbeat/history.jsonl` — the durable
    state a fresh, context-free run needs, since the two binding constraints from this item's
    own note (never a daemon; each run remembers nothing on its own) mean anything needing
    memory of a PREVIOUS run has to live in a file. `new_since_last_run` diffs this run's open
    PRs and worktrees against the previous `latest.json`, which is the "a pull request now
    conflicting with a live session that has not been told" bullet answered mechanically:
    whether it has been told is exactly whether it was already in the last report.
    Read-and-report authority only, never merge — the underlying `janitor.py` and
    `coordinator.py` calls carry nothing that presses anything.
