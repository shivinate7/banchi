## 2 — The map's reach

**What.** The file map cannot see an extensionless file, and a map entry proves a file is described, never that the description is true.

- **The coverage rule cannot see an extensionless file.** `make map-check`'s MAP1 counts only files whose extension is in `codeExtensions` (`map.config.json`), so an extensionless file needs no `docs/map/` line and the check stays green. `scripts/docs_audit/env_map.py:check_hook_roster` (the `hook roster` row) covers `scripts/githooks/` only. An extensionless enforcement seam anywhere else needs no map line, and no check fails.
- **An entry proves a file is described, never that the description is true.** A `does` sentence about the wrong file passes. A stale cross-reference in prose is invisible to every row. `.json` is outside `codeExtensions` (adding it would conscript `app/package-lock.json`), so `app/package.json` has no `docs/map/` line.

`scripts/githooks/pre-commit` also compares its armed copy against main and refuses when the copy is behind main and this tree matches main. Its bypass is `BANCHI_HOOKS=off`.

**Outcome at risk.** A new enforcement seam ships with no map entry, or a map entry describes the wrong file, with every row green.

**Closes when.** MAP1 can name a whole filename. Its reader is claude-settings' shared check, not this repo. `code_haystack()` in `scripts/docs_audit/core.py` already reaches an extensionless file that way. The description half has no mechanical close.
