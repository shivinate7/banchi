## D-worktreeinclude-carries-env — `.worktreeinclude` copies `.env` and two local configs into each Claude Code worktree

**Settled 2026-09-28, on the owner's ruling.** Amends the Makefile's old `worktree-setup` argument that `.env` is deliberately not copied (a secret copied around a disk ends up somewhere nobody tracks, and T1 does not need it once the cache is warm).

**What it does.** `.worktreeinclude` at the root lists three paths: `.env`, `.claude/settings.local.json`, `.codex/config.toml`. Claude Code copies a file into each new worktree only when it matches that list AND is gitignored. All three are gitignored, and the list itself is tracked. `make worktree-setup` still copies no secret. Only Claude Code's own worktree creation reaches these files. `.env.local` is not in the list, by the owner's ruling.

**Why the owner chose it.**
- A worktree session can run paid identify runs. Without `.env` it cannot, and the owner wants it to.
- A copied `.claude/settings.local.json` may carry a subagent-cap raise. The owner's config watch still sees it, because the watch reads the file's expiry (`_subagentCapUntil`), not the tree it sits in.

**What protects the old argument's outcome now.** The copy is one owner-named list, tracked and reviewable. A session never reads, prints or copies these files' contents. `.env` stays ignored, so it cannot be committed.
