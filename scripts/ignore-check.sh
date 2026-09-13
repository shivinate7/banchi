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

# THE LIST IS READ OUT OF .gitignore ITSELF, RATHER THAN DUPLICATED HERE — this is the fix for
# the failure that made this list necessary a second time. `photos` (D172) was added to
# .gitignore's prose and to its own decision entry's "this is gitignored" sentence, and never
# added to this file's own hand-kept PATHS list beside it — a claim true in one file and untested
# in the other, until a real 4.45 GB migration populated the directory for the first time and
# nothing had ever checked it. The fix is not "remember to update both files next time": it is
# that there is only one file to update. Every bare (no-trailing-slash) line in .gitignore
# carries an inline `# ignore-check: ...` marker when it exists FOR THIS REASON — the top-of-file
# rule about worktree-provisioned paths — and this script reads exactly those lines. A path
# added to .gitignore with that marker is checked from the next run onward; a path added without
# it is a deliberate signal that this script's reasoning does not apply to it (an ordinary
# machine-local file like .claude/settings.local.json, never provisioned by anything that could
# put a symlink there).
# THE MARKER IS A COMMENT LINE OF ITS OWN, NEVER TRAILING ON THE PATTERN LINE. `.gitignore`
# has no concept of an inline comment -- a `#` only opens one as the FIRST character of a
# line, so `node_modules  # ignore-check` is not "node_modules, with a comment" to git at
# all: it is the literal 26-character pattern "node_modules  # ignore-check", which does not
# match anything a worktree ever creates. That exact form was this file's own first draft and
# broke every single line it touched, caught only by testing against a path that was already
# known to pass. `grep -A1` reads the marker and the pattern line immediately below it instead.
PATHS="$(grep -A1 -E '^# ignore-check:' .gitignore | grep -v -E '^# ignore-check:|^--$')"

# `app/node_modules` is not its own .gitignore line — the bare `node_modules` pattern above
# already matches it at any depth, which is the whole point of the bare form. Checked here as an
# extra, explicit confidence case for the exact path the 2026-08-30 incident actually broke on,
# not because it needs a pattern of its own.
PATHS="$PATHS
app/node_modules"

if [ -z "$(echo "$PATHS" | tr -d '[:space:]')" ]; then
  echo "ignore-check: no marked paths found in .gitignore — the marker or the grep is broken."
  exit 1
fi

failed=0
checked=0

# `set --` over `echo | while read` on purpose: the latter runs its body in a SUBSHELL under
# `sh`, so `checked` and `failed` would reset to 0 the moment the loop ends. Positional
# parameters are the shell's own state, not a pipeline's.
oldIFS="$IFS"
IFS='
'
set -- $PATHS
IFS="$oldIFS"

for raw in "$@"; do
  [ -z "$raw" ] && continue
  checked=$((checked + 1))
  # `git check-ignore` takes a PATH to test, not a pattern -- a leading "/" in .gitignore
  # anchors a pattern to the repo root, but the same leading "/" on the path being tested
  # reads as an OS-absolute path outside the repo and refuses to answer at all. Strip it;
  # the anchoring is a property of the pattern in .gitignore, not of the path being asked
  # about, and testing the bare root-relative name is exactly what an anchored pattern means.
  #
  # AND A TRAILING "/" IS ALWAYS STRIPPED TOO, WHATEVER .gitignore ACTUALLY SAYS -- this is
  # not cosmetic, it is the entire question this check exists to ask. The path list is read
  # out of .gitignore itself, so testing it AS WRITTEN would make a corrupted entry validate
  # itself: change `photos` to the directory-only `photos/` and `git check-ignore` reports a
  # PATH ending in `/` as ignored, because a trailing slash on the thing being tested tells
  # git to treat it as a directory — the exact case D47 exists to refuse, passing because the
  # test path and the pattern under test were the same corrupted string. Testing the BARE
  # form regardless of what is on the line is what "ignored whatever is at it" means.
  name="${raw#/}"
  name="${name%/}"
  if ! git check-ignore --no-index -q "$name"; then
    echo "ignore-check: '$raw' is NOT ignored."
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
