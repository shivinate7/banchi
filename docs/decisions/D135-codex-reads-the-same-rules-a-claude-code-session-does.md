## D135 — Codex reads the same rules a Claude Code session does, through three symlinks and one reconciled hook roster

**Settled 2026-09-11.** OpenAI Codex was installed in this repository on 2026-09-09 and left
three untracked paths in the main checkout: a 117 KB `AGENTS.md` that is `sed
's/AGENTS\.md/CLAUDE.md/g' AGENTS.md | diff - CLAUDE.md` away from `CLAUDE.md` — 139 lines of
drift, missing `make reap`, D129, the eight-key storage roster and D132 — a byte-identical copy
of `.claude/skills/tcgplayer-csv/SKILL.md` at the equivalent path under a separate,
untracked `.agents/skills/` directory, and
`.codex/` holding `config.toml` (a shell-environment policy, machine-local) and `hooks.json`
(the same six-then-eight hooks `.claude/settings.json` runs, by the same scripts). None of the
three was tracked, so none of it reached a clone, a worktree, or a PR — every Codex session
anywhere but that one Mac read stale prose, a stale skill, or no hooks at all.

**A copy is a fork with a diff nobody watches. A symlink has no diff to drift.** The fix is not
a sync script — this repo already argued that case for the eval-image mirror and lost it (D47)
— it is to point Codex at the files Claude Code already reads, so one edit reaches both readers
by construction:

- **`AGENTS.md -> CLAUDE.md`**, at the root. A relative link, same directory, committed.
- **`code-card-fork/AGENTS.md -> CLAUDE.md`**, inside that directory — because the codex-track
  auto-load `CLAUDE.md` itself documents (`code-card-fork/CLAUDE.md`, "auto-loaded in that
  directory") needs the same door for Codex that the root file gets, or a session working the
  code-card track reads the singles rules and nothing about codes.
- **`.agents/skills -> ../.claude/skills`**, a directory link. Every skill added under
  `.claude/skills/` from now on is a skill Codex can load too, with no second copy and no
  second place to remember it.

**Both are D47's allowed shape and neither is its refused one.** All three are relative and
resolve inside the repository — `python3 -c "os.path.realpath(...)"` was run against each
before committing, the check this entry's own mechanism performs at every commit thereafter.
The pre-commit hook that reads mode `120000` out of the index (D47) is what makes that
durable rather than a one-time check: a future session cannot silently turn one of these into
an absolute path or a copy without the hook refusing it.

**This retires the allowlist line that predicted it.** `scripts/docs-audit-allow.txt` carried
`code-card-fork/AGENTS.md` from 2026-09-09, on the owner's instruction, with its own reason
stating the condition for its removal: *"Delete this line if a tracked AGENTS.md is ever
adopted here, at which point the pointer should be fixed rather than excused."* That day is
this one. The line is deleted, not edited — the entry it named now exists and the audit
confirms it rather than excusing its absence.

### The hook roster is reconciled, mechanically, in both directions

**`.codex/hooks.json` and `.claude/settings.json`'s `hooks` block disagreed on arrival.**
Codex's file was written 2026-09-09; `.claude/settings.json` gained a `Bash`-matched
`scripts/reap.py --hook` PreToolUse entry the next day (D127, for the pkill/lsof incidents)
and has always carried `scripts/session-teardown.sh` on `WorktreeRemove` (D111's sweep),
neither of which `.codex/hooks.json` had. A Codex session could have run an unrestricted
`pkill` a Claude Code session in this repo cannot, and a worktree it removed would never
notify a supervisor to stop. Both are added to `.codex/hooks.json` in the same change that
adds the guard below, so the row starts green rather than starts by reporting the gap.

**`scripts/docs-audit.py:check_codex_hooks` reads both files as `(event, matcher, command)` triples and reports whichever side is missing what the other runs**, plus any command that
names a script no longer in the tree. It is MECHANICAL — a hook roster is a literal, checkable
the same way `check_hook_roster` already checks `scripts/githooks/` against `docs/map.py` — and
it is registered in `audit()` and covered by `--self-test`, which drives the extractor on
synthetic dicts (so the mutation this row exists to catch — one hook removed from one file —
is provable without touching either real file) and then asserts the two real files agree.

**What this is not.** `.codex/config.toml` stays untracked, gitignored beside
`.claude/settings.local.json` with a comment saying why: a shell-environment policy is
machine-local the same way a local Claude Code settings override is, and neither belongs in
the tree that ships to every checkout. Nothing about `PKMNSCAN_GATE` or any other value in it
is asserted here.

### What is BUILT, RECORDED, NEITHER

**BUILT**: the three symlinks, committed and verified to resolve inside the repository;
`.codex/hooks.json` tracked and brought to parity with `.claude/settings.json`'s hook roster;
the `codex hooks` mechanical row in `scripts/docs-audit.py`, registered in `audit()` and
covered by `--self-test`; the stale allowlist line removed; the `.gitignore` line for
`.codex/config.toml`; `docs/map.py`'s `governed_by` for `docs-audit.py` extended with D111,
D127 and this entry.

**RECORDED**: this entry, and the CLAUDE.md paragraph naming it.

**NEITHER, left for the owner**: the three untracked copies in the main checkout
(`~/Developer/pkmnscan/AGENTS.md`, its `.agents/skills/` mirror, and `.codex/`) are deleted
only after this change is merged and pulled there — deleting them from a worktree
would not remove the main checkout's own untracked files, and doing it before the merge would
leave that Mac's Codex session with nothing to read in between. `.codex/config.toml` is kept
regardless; it was never one of the three copies.
