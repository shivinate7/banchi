## DEBT-settings-tree-note-stale — the settings note says the Write|Edit guard entry runs the tree clause

**What.** The `_PreToolUse_guard_shell_note` key in `.claude/settings.json` says "The Write|Edit entry runs the tree clause alone", but that entry sets `GUARD_SHELL_SKIP=tree`, so it runs no clause.

- **Same note, second sentence:** it says the shared layer "owns clauses 1, 2, 7 and 8". It owns 1, 7 and 8, and only the part of 2 that refuses a write naming a path in another checkout (D179).
- **Ruled behavior:** the owner ruled that Claude Code skips Banchi's tree clause, because the shared guard's other-checkout rule covers a write into another checkout of this clone (owner, 2026-10-28 12:49 CDT, waiting page item 41 a). An entry that runs no clause is that ruling, not a defect.
- **Not fixed because** agents may not edit `.claude/settings.json`. Only the owner edits it.
- **Closes when** the owner's next edit of that file drops the Write|Edit `guard-shell.py` entry, or rewrites the sentence to say the entry is a no-op. That edit also narrows the clause-2 claim.
- **Points to** D179 (shell mistakes are refused by resolving), D135 (Codex reads the same rules).

**Outcome at risk.** A reader of the note believes Write and Edit calls pass through Banchi's tree clause. They pass through the shared guard alone.
