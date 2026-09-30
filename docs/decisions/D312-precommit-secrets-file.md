## D312 — The pre-commit hook refuses a secrets file

**The repo pre-commit hook refuses a staged path whose basename is `.env` or starts with `.env.`.**
It does so in any directory. The one allow is `.env.example`, the template the repo tracks. Nothing else is exempt, and no
`PKMNSCAN_*` hatch reaches it. The match is case-insensitive, because macOS is. The clause reads
names with `-z`, so a non-ASCII path is matched whole. It fails open like the hook's other clauses.

**The Claude hook cannot see `git add -f .` and Codex runs none.** The global Claude hook refuses a
forced add only when the command names the file. The repo hook is the one guard every tool runs
(D42, main moves by pull request, arms the same hooks).

**Enforced** by `scripts/githooks/pre-commit` and the secrets cases in `scripts/githooks-selftest.sh`.
