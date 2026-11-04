## DEBT-commit-hook-skips-map-check — a new code file with no map line passes the commit and fails only in make check and CI

**What.** The pre-commit hook does not run `make map-check`, so a code file added under `map.config.json`'s `mapPaths` with no `docs/map/` line commits clean and goes red only in `make check` and CI. Main's orphan row refused it at commit.

- **Result:** a session that adds a file in normal work learns of the missing map line late, after the commit and often after the push.
- **Not fixed because** the hook runs a bare python3 with no node and no claude-settings checkout, and `make map-check` needs both. It takes 5.7 s.
- **Closes when** `scripts/githooks/pre-commit` runs `make map-check` where node and a claude-settings checkout exist, and skips with a loud warning where they do not. The `map-check` row in `scripts/checks.py` then sets `commit_path`, and `make githooks-selftest` covers both arms.
- **Points to** D18 (the commit path runs nothing that needs a toolchain).

**Outcome at risk.** An unmapped code file reaches a pull request, where the map is the only record of what the file is for.
