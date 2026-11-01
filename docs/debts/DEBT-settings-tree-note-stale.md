## DEBT-settings-tree-note-stale — the settings note says the Write|Edit guard entry runs the tree clause

**What.** The `_PreToolUse_guard_shell_note` key in `.claude/settings.json` says "The Write|Edit entry runs the tree clause alone", but that entry sets `GUARD_SHELL_SKIP=tree`, so it runs no clause.

- **Ruled behaviour:** the owner ruled that Claude Code skips Banchi's tree clause, because the shared guard's other-checkout rule covers a write into another checkout of this clone (owner, 2026-10-28 12:49 CDT, waiting page item 41 a). An entry that runs no clause is that ruling, not a defect.
- **Not fixed because** agents may not edit `.claude/settings.json`. Only the owner edits it.
- **Closes when** the owner's next edit of that file drops the Write|Edit `guard-shell.py` entry, or rewrites the sentence to say the entry is kept as a no-op.
- **Points to** D179 (shell mistakes are refused by resolving), D135 (Codex reads the same rules).

**Outcome at risk.** A reader of the note believes Write and Edit calls pass through Banchi's tree clause. They pass through the shared guard alone.
