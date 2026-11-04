# D135 — Banchi has no Codex setup

Banchi has no Codex setup. The owner ruled it on 2026-11-04 07:56 CST (Cockpit item 214 a): "Delete all of banchi's Codex setup".

Kind: process
Home: CLAUDE.md

**What the ruling removed.**

- The root `AGENTS.md` link to `CLAUDE.md`, and each folder's `AGENTS.md` link to its rule file in `.claude/rules/`: `app/`, `server/`, `pipeline/`, `cli/`, `identify/`, `store/`, `codes/` and `code-card-fork/`.
- The `.agents/skills` link to `.claude/skills`.
- `.codex/hooks.json`, the `.codex/config.toml` lines in `.gitignore` and `.worktreeinclude`, and the `agent links` and `codex hooks` rows of `make docs-audit`.
- The two `scripts/guard-shell.py` clauses that only Codex ran: `checkout` and `stash`. Claude Code skipped both, because the shared layer's guard owns them (D179). The two hatches of those clauses went with them. The `reset` clause stays for now: it also refuses `git reset --merge` and `--keep`, which the shared guard does not yet. A later change deletes it.

**What stays, because Claude Code reads it.**

- `code-card-fork/CLAUDE.md -> ../CLAUDE.md`, so Claude Code's auto-load in that directory reads the root rules. The `fork claude link` row of `make docs-audit` checks it.
- The hook checks that guarded `.claude/settings.json` alone. The `claude hooks` row keeps three of them: every hook command names a file in the tree, each `scripts/guard-shell.py` entry pins its `GUARD_SHELL_SKIP` value, and the silent-write hook keeps its `BANCHI_SILENT_WRITE_ONLY` prefix (D171).
- A path-scoped rule may use any glob in its `paths:` list. The folder-only glob shape and the one-rule-per-folder limit existed only so each folder could hold an `AGENTS.md` link.

**Also removed, on the coordinator's ruling of 2026-11-04 08:40 CST under item 214 a.** The `--hook` mode of `scripts/reap.py` (D127). Only `.codex/hooks.json` armed it. The shared layer's machine-wide-kill rule owns that guard for Claude Code. Every mode `make reap` uses stays.

The owner deletes the untracked Codex files in the main checkout by hand: `~/Developer/banchi/AGENTS.md`, its `.agents/skills/` mirror, and `.codex/`.
