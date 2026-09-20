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

# BESIDE ITSELF FIRST, THEN ITS OWN REPO. `make janitor-install` copies this file and
# `janitor.py` into `~/.claude/bin` so a user-level hook can run them in a repo that has never
# heard of this one; the installed pair has to find each other with no checkout in sight. The
# repo path is the fallback, which is what this file uses when it runs from the tree.
mine="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)" || exit 0
janitor="$mine/janitor.py"
[ -f "$janitor" ] || janitor="$(dirname "$mine")/scripts/janitor.py"
[ -f "$janitor" ] || exit 0

python3 "$janitor" --teardown "$tree" 2>/dev/null || true

# Then the provably-dead: a supervisor whose tree has just been removed is only findable from
# the process table, because `.serve/` went with the tree. Tier 1 never touches anything that
# could be live, so it needs no confirmation and asks for none.
#
# GATED ON THERE BEING A CLONE AT ALL. Ending a session in a directory that is not a repository
# is ordinary, and the sweep refuses one loudly — correct when a person typed the command, and
# noise on every session end when a hook did. Ask git first, quietly.
if git -C "$tree" rev-parse --show-toplevel >/dev/null 2>&1; then
  python3 "$janitor" --root "$tree" --tier1 2>/dev/null || true

  # AND THE ONE PART OF TIER 2 THAT DESTROYS NOTHING. A branch reaches this list only when main
  # is a descendant of every commit on it, so `git branch -D` removes a label and no object.
  # The word tier 2 waits on is about the other two halves of it — removing a worktree can cost
  # uncommitted work, stopping a process can cost a run somebody wanted — and holding a
  # lossless act behind the same word as a lossy one is what left nine merged branches on this
  # disk with nobody to press it.
  #
  # HERE RATHER THAN ONLY ON A SCHEDULE, because this is the moment the branch became cuttable:
  # a tree going is what releases its branch from `held`. The daily agent is the backstop for
  # the events this misses, which `.claude/settings.json` already says are many.
  #
  # `--branches` READS THE CLONE'S OWN LAYOUT AND REFUSES WHEN IT CANNOT. See
  # `cut_merged_branches`: no worktree list means no branch is protected, so it keeps every one.
  python3 "$janitor" --root "$tree" --branches --confirm 2>/dev/null || true
fi

exit 0
