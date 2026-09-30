## 2 — The map's reach

- **The orphan rule cannot see an extensionless file.** `scripts/docs_audit/env_map.py:scan_plan` rejects any `source_suffixes` member that does not start with a dot. `check_hook_roster` covers `scripts/githooks/` only. An extensionless enforcement seam anywhere else needs no map entry and the row stays green.
- **An entry proves a file is described, never that the description is true.** A `does` sentence about the wrong file passes. A stale cross-reference in prose is invisible to every row. `.json` is outside `app/`'s suffixes (it would conscript `app/package-lock.json`), so `app/package.json` has no entry.

`scripts/githooks/pre-commit` also compares its armed copy against main and refuses when the copy is behind main and this tree matches main. Its bypass is `PKMNSCAN_HOOKS=off`.

**Outcome at risk.** A new enforcement seam ships with no map entry, or a map entry describes the wrong file, with every row green.

**Closes when.** `source_suffixes` accepts a whole filename (`code_haystack()` already reaches an extensionless file that way). The description half has no mechanical close.
