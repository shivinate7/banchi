#!/usr/bin/env bash
# Usage: ci-skip-count.sh <target> <log>
# Prints how many cases a CI shard skipped, to stdout and the job's step summary. Reads the
# markers the tools already print: a gated self-test's `<name>: SKIPPED`, the docs-audit
# self-test's `UNKNOWN <case>` and Playwright's `N skipped` summary. It never fails the job:
# the calling step keeps its own exit code.
set -u
target="${1:?target}"
log="${2:?log}"
TARGET="$target" awk '
  /^[a-z0-9-]+: SKIPPED /               { gated += 1 }
  /^ +UNKNOWN /                         { unknown += 1 }
  /^ +[0-9]+ skipped/                   { tests += $1 }
  END { printf "skipped in %s: %d gated self-test(s), %d unknown case(s), %d test(s)\n", ENVIRON["TARGET"], gated, unknown, tests }
' "$log" | tee -a "${GITHUB_STEP_SUMMARY:-/dev/null}"
