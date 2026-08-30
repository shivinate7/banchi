#!/bin/sh
# EVERY PROVISIONED PATH IS IGNORED, WHATEVER KIND OF THING IS AT IT — the other half of D47.
#
# That entry's own "what would reopen this" named this check and did not build it: *"a path that
# ought to be ignored and is not, which is what let the first one through. `git check-ignore` over
# the provisioned set, run somewhere off the commit path, would close that half."* It reopened the
# same day. `harness/.cache/` and `.venv/` had kept their directory-only patterns on the reasoning
# that `scripts/worktree-guard.sh` copies one and builds the other, so neither is ever a link —
# sound about the script, silent about the path. A worktree provisioned by hand linked both, and
# they went straight back to untracked-rather-than-ignored: one `git add -A` from committing an
# absolute path into one Mac, which is the 133 MB the mirror cost the first time.
#
# IT ASKS ABOUT THE BARE NAME AND DELIBERATELY NOT ABOUT `name/`, WHICH IS THE ONE SUBTLETY
# HERE. The bare form is the one that decides whether `git add -A` can pick the path up, so it
# is the form that carries the protection — and it is answerable whatever is on disk. Asking the
# trailing-slash form means traversing the path, and git answers `fatal: pathspec ... is beyond a
# symbolic link` exactly when a symlink is there: unanswerable precisely in the case being
# guarded against. `scripts/docs-audit.py:ignored_paths` records the same refusal from the same
# cause. A check that cannot run in the failing case is not a check.
#
# `--no-index` IS WHY IT CAN ASK ABOUT A PATH THAT IS NOT THERE AT ALL. `git check-ignore`
# otherwise declines to answer for a tracked path; this makes it a question about the PATTERN,
# which is the question being asked — a fresh clone has none of these paths and the answer should
# be the same.
#
# OFF THE COMMIT PATH, DELIBERATELY, and for two reasons. D18: nothing that gates a commit may
# depend on local state. And this checks a property of provisioning — a fresh clone has none of
# these paths and would fail a commit over something that is not wrong. `make check` is invoked
# by a person; the git hook is not.
set -eu

# The four `scripts/worktree-guard.sh` can put something at. Order matches .gitignore's own.
PATHS='node_modules
app/node_modules
harness/images
harness/.cache
.venv'

failed=0
checked=0

for name in $PATHS; do
  checked=$((checked + 1))
  if ! git check-ignore --no-index -q "$name"; then
    echo "ignore-check: '$name' is NOT ignored."
    echo "    A worktree can put a file, a directory OR A SYMLINK at this path, and a"
    echo "    pattern ending in '/' matches only a directory. Drop the trailing slash in"
    echo "    .gitignore — see D47, which this check is the second half of."
    failed=1
  fi
done

if [ "$failed" -ne 0 ]; then
  exit 1
fi

echo "ignore-check: $checked provisioned paths, every one ignored whatever is at it"
