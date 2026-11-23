## DEBT-screen-freshness-server-scope — The screen-freshness check misses a server.ts export

**What.** The screen-freshness check (`make screen-freshness-selftest`, `scripts/screen-freshness.mjs`) runs locally only when its own script changes, so a branch that adds an export to `app/src/server.ts` reaches CI before the check sees it.

**Cost.** Pull request 1129 hit this: the check first ran in CI, after the branch was pushed.

**Why unfixed.** Not recorded. The fix is to scope the check on `app/src/server.ts` too, in `scripts/guard-scope.py`.
