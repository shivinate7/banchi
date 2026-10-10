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
# missing janitor, a Python that will not start. The one exception is a WorktreeRemove whose
# tree stays on disk, which exits 1, because Claude Code reads 0 as "removed". A hook that can refuse a session's end is worse
# than a leak, and whatever this misses is reaped by `make janitor` later — which is the point of
# having a sweep that does not depend on an event.
#
# IT IS NOT ON THE COMMIT PATH and must never be put there. D18: nothing that writes may run
# where a commit is decided.

set -uo pipefail

payload="$(cat 2>/dev/null || true)"

# WorktreeRemove names the tree in `worktree_path`. SessionEnd has only `cwd`, which follows
# Claude to its worktree root. `reason` is absent for WorktreeRemove and present for
# SessionEnd; an absent one is not a `clear`, so it proceeds.
read -r tree reason wtp <<EOF
$(python3 -c "
import json, sys
try:
    d = json.loads(sys.stdin.read() or '{}')
except Exception:
    d = {}
wtp = str(d.get('worktree_path') or '').strip()
cwd = wtp or str(d.get('cwd') or '').strip()
why = str(d.get('reason') or '').strip()
print((cwd or '-'), (why or '-'), (wtp or '-'))
" <<<"$payload" 2>/dev/null || echo "- - -")
EOF

[ "${tree:--}" = "-" ] && exit 0
[ "${reason:--}" = "clear" ] && exit 0     # the session continues; its servers are still wanted
[ -d "$tree" ] || exit 0

# BESIDE ITSELF FIRST, THEN ITS OWN REPO. Both files run from this repo's `scripts/`, so
# `janitor.py` sits beside this one; the repo path is the fallback.
mine="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" || exit 0
janitor="$mine/janitor.py"
[ -f "$janitor" ] || janitor="$(dirname "$mine")/scripts/janitor.py"
[ -f "$janitor" ] || exit 0

python3 "$janitor" --teardown "$tree" 2>/dev/null
in_use=$?    # 3: another session still stands in the tree (janitor.IN_USE)

# scripts/worktree-create.sh makes every Claude Code worktree, so removing it is this hook's
# job too. No --force: git refuses a tree with uncommitted work, and that tree stays on disk.
# WorktreeRemove reads exit 0 as "removed", so a tree left on disk exits 1. The branch goes
# with `-d`, which keeps a branch holding commits that no other ref has.
case "$wtp" in
  */.claude/worktrees/*)
    [ "$in_use" = 3 ] && exit 1
    branch="$(git -C "$tree" symbolic-ref --quiet --short HEAD 2>/dev/null)"
    main="$(dirname "$(git -C "$tree" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)")"
    git -C "$main" worktree remove "$tree" >/dev/null 2>&1 || exit 1
    case "$branch" in worktree-*) git -C "$main" branch -d "$branch" >/dev/null 2>&1 ;; esac
    ;;
esac

exit 0
