#!/usr/bin/env bash
# The SessionEnd / WorktreeRemove hook: stop what a leaving session started, and nothing else.
#
# WHY THIS EXISTS. Nothing ran when a session ended. `.claude/settings.json` wired SessionStart,
# PreToolUse, PostToolUse and Stop — and `Stop` fires at TURN end, so it is a gate and not a
# teardown. A worktree's supervisor therefore outlived its session, then outlived the tree, and
# four of them were found on 2026-09-06 still restarting against directories that had been
# deleted, the oldest since 2026-08-30.
#
# WORKTREEREMOVE IS THE EVENT THIS IS REALLY FOR. It fires at the moment the tree goes, which is
# exactly the moment whose absence produced those four. SessionEnd is the second anchor and a
# weaker one: it cannot be relied on at app quit or machine sleep, and its `reason` includes
# `clear`, where the session CONTINUES — stopping servers there would kill work in progress, so
# that reason is skipped by name.
#
# IT FAILS OPEN, ALWAYS. Every path here exits 0: no stdin, unparseable stdin, no such tree, a
# missing janitor, a Python that will not start. A hook that can refuse a session's end is worse
# than a leak, and whatever this misses is reaped by `make janitor` later — which is the point of
# having a sweep that does not depend on an event.
#
# IT IS NOT ON THE COMMIT PATH and must never be put there. D18: nothing that writes may run
# where a commit is decided.

set -uo pipefail

payload="$(cat 2>/dev/null || true)"

# `cwd` follows Claude, so it is the worktree root rather than the project root, which is
# exactly the value wanted here. `reason` is absent for WorktreeRemove and present for
# SessionEnd; an absent one is not a `clear`, so it proceeds.
read -r tree reason <<EOF
$(python3 -c "
import json, sys
try:
    d = json.loads(sys.stdin.read() or '{}')
except Exception:
    d = {}
cwd = str(d.get('cwd') or '').strip()
why = str(d.get('reason') or '').strip()
print((cwd or '-'), (why or '-'))
" <<<"$payload" 2>/dev/null || echo "- -")
EOF

[ "${tree:--}" = "-" ] && exit 0
[ "${reason:--}" = "clear" ] && exit 0     # the session continues; its servers are still wanted
[ -d "$tree" ] || exit 0

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." 2>/dev/null && pwd)" || exit 0
janitor="$here/scripts/janitor.py"
[ -f "$janitor" ] || exit 0

python3 "$janitor" --teardown "$tree" 2>/dev/null || true

# Then the provably-dead, machine-wide: a supervisor whose tree has just been removed is only
# findable from the process table, because `.serve/` went with the tree. Tier 1 never touches
# anything that could be live, so it needs no confirmation and asks for none.
python3 "$janitor" --root "$tree" --tier1 2>/dev/null || true

exit 0
