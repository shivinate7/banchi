## D135 — Codex reads the same rules as Claude

**Settled 2026-09-11.** OpenAI Codex was installed in this repository on 2026-09-09 and left three untracked paths in the main checkout. The first is a 117 KB `AGENTS.md`. It is `sed 's/AGENTS\.md/CLAUDE.md/g' AGENTS.md | diff - CLAUDE.md` away from `CLAUDE.md`: 139 lines of drift, missing `make reap`, the eight-key storage roster and D132. The second is a byte-identical copy of `.claude/skills/tcgplayer-csv/SKILL.md` at the equivalent path under a separate, untracked `.agents/skills/` directory. The third is `.codex/`. It holds `config.toml` (a shell-environment policy, machine-local) and `hooks.json`. `hooks.json` holds the hooks `.claude/settings.json` runs, by the same scripts, plus the two named in `CODEX_ONLY`. None of the three was tracked. So none of it reached a clone, a worktree, or a PR. Every Codex session anywhere but that one Mac read stale prose, a stale skill, or no hooks at all.

**A copy is a fork with a diff nobody watches. A symlink has no diff to drift.** The fix is not a sync script. This repo already argued that case for the eval-image mirror and lost it (D47). The fix is to point Codex at the files Claude Code already reads, so one edit reaches both readers by construction:

- **`AGENTS.md -> CLAUDE.md`**, at the root. A relative link, same directory, committed.
- **`code-card-fork/AGENTS.md -> CLAUDE.md`**, inside that directory. The reason is the codex-track auto-load that `CLAUDE.md` itself documents (`code-card-fork/CLAUDE.md`, "auto-loaded in that directory"). It needs the same door for Codex that the root file gets. Without it, a session working the code-card track reads the singles rules and nothing about codes.
- **`.agents/skills -> ../.claude/skills`**, a directory link. Every skill added under `.claude/skills/` from now on is a skill Codex can load too. There is no second copy and no second place to remember it.

**Both are D47's allowed shape and neither is its refused one.** All three are relative and resolve inside the repository. `python3 -c "os.path.realpath(...)"` was run against each before committing. That is the check this entry's own mechanism performs at every commit thereafter. The pre-commit hook reads mode `120000` out of the index (D47). It is what makes that durable rather than a one-time check. A future session cannot silently turn one of these into an absolute path or a copy without the hook refusing it.

**This retires the allowlist line that predicted it.** `scripts/docs-audit-allow.txt` carried `code-card-fork/AGENTS.md` from 2026-09-09, on the owner's instruction, with its own reason stating the condition for its removal: *"Delete this line if a tracked AGENTS.md is ever adopted here, at which point the pointer should be fixed rather than excused."* That day is this one. The line is deleted, not edited — the entry it named now exists and the audit confirms it rather than excusing its absence.

### The hook roster is reconciled, mechanically, in both directions

**`.codex/hooks.json` and `.claude/settings.json`'s `hooks` block disagreed on arrival.** Codex's file was written 2026-09-09. `.claude/settings.json` gained a `Bash`-matched `scripts/reap.py --hook` PreToolUse entry the next day (D127, for the pkill/lsof incidents). It has always carried `scripts/session-teardown.sh` on `WorktreeRemove` (claude-settings decisions/the-janitor-is-one-machine-wide-sweep.md, "The janitor is one machine-wide sweep"). `.codex/hooks.json` had neither of them. A Codex session could have run an unrestricted `pkill` that a Claude Code session in this repo cannot run. A worktree it removed would never notify a supervisor to stop. Both are added to `.codex/hooks.json` in the same change that adds the guard below. So the row starts green rather than starts by reporting the gap.

**One divergence is declared, on the owner's word.** The shared layer's guard owns the pkill rule for Claude Code, so `.claude/settings.json` no longer runs `scripts/reap.py --hook`, and it runs `scripts/guard-shell.py` with `GUARD_SHELL_SKIP=checkout,stash,reset`. Every other guard-shell entry sets `GUARD_SHELL_SKIP=` empty, so an inherited value never narrows Codex. Codex runs no shared guard and keeps all of them in full. `CODEX_ONLY` in `check_codex_hooks` names the one hook only Codex runs, and the row fails when Claude Code runs it again or Codex loses it. The row compares commands exactly, so the `GUARD_SHELL_SKIP` value on each entry is pinned.
Claude Code runs `BANCHI_SILENT_WRITE_ONLY=file,bash-c scripts/silent-write-guard.py --hook`.
That runs only the unread-file clause and the `bash -c` clause. The shared silent-write rule
(claude-settings PR 257 and PR 264) covers the rest. Codex keeps the full hook. The row pins the
prefix on the Claude entry and its absence on the Codex entry. It is a variable, not a flag.
An older branch's copy ignores a variable and runs the full check. An unknown flag exits 2 and
blocks every Bash call. Both clauses are reviewed against their refusal-log counts with
claude-settings (D171).

**`scripts/docs_audit/env_map.py:check_codex_hooks` reads both files as `(event, matcher, command)` triples and reports whichever side is missing what the other runs**. Plus any command that names a script no longer in the tree. It is MECHANICAL. A hook roster is a literal, checkable the same way `check_hook_roster` already checks `scripts/githooks/` against `docs/map.py`. The row is a `ROWS` entry and is covered by `--self-test`. That `--self-test` drives the extractor on synthetic dicts. So the mutation this row exists to catch is provable: one hook removed from one file. That needs no touch of either real file. Then it asserts the two real files agree.

**What this is not.** `.codex/config.toml` stays untracked, gitignored beside `.claude/settings.local.json`, with a comment saying why. A shell-environment policy is machine-local the same way a local Claude Code settings override is. Neither belongs in the tree that ships to every checkout. Nothing about any value in it is asserted here.

### What is BUILT, RECORDED, NEITHER

**BUILT**: the three symlinks, committed and verified to resolve inside the repository. `.codex/hooks.json` tracked and brought to parity with `.claude/settings.json`'s hook roster. The `codex hooks` mechanical row in `scripts/docs-audit.py`, a `ROWS` entry and covered by `--self-test`. The stale allowlist line was removed. The `.gitignore` line for `.codex/config.toml` was added. `docs/map.py`'s `governed_by` for `docs-audit.py` was extended with D127 and this entry.

**RECORDED**: this entry, and the CLAUDE.md paragraph naming it.

**NEITHER, left for the owner**: the three untracked copies in the main checkout are deleted only after this change is merged and pulled there. They are `~/Developer/banchi/AGENTS.md`, its `.agents/skills/` mirror, and `.codex/`. Deleting them from a worktree would not remove the main checkout's own untracked files. Doing it before the merge would leave that Mac's Codex session with nothing to read meanwhile. `.codex/config.toml` is kept regardless. It was never one of the three copies.
