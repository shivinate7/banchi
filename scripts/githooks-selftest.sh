#!/usr/bin/env bash
# The main guard checks itself, in a repository built and destroyed for the purpose.
#
# WHY THIS EXISTS. `scripts/githooks/reference-transaction` and its pre-push sibling cannot be
# exercised in this repository without arming them here first, and `core.hooksPath` is stored
# in the common .git dir — one setting shared by every worktree of this clone. Flipping it to
# try something out would reach into whatever concurrent sessions are mid-commit. So the test
# builds its own origin and its own clone in a temporary directory, points core.hooksPath at
# THESE hook files, and runs the real gestures against them.
#
# WHY IT IS NOT IN THE GIT HOOK. It writes — a bare repo, a clone, commits, pushes. D18: nothing
# that writes may run on the path that decides whether a commit proceeds. It runs in `make check`,
# which a person invokes, exactly as `make audit-self-test` does and for the same reason.
#
# WHAT IT CANNOT PROVE. That the hooks are ARMED in the real clone. That is one line of config
# and `make hooks` is what sets it; `make hooks` prints the resolved path so the answer is
# visible rather than assumed. A green run here means the files behave, not that git is
# calling them.

set -uo pipefail

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/githooks" && pwd)"
pass=0
fail=0

tmp="$(mktemp -d "${TMPDIR:-/tmp}/pkmnscan-githooks.XXXXXX")" || { echo "cannot make a temp dir"; exit 1; }
cleanup() { rm -rf "$tmp"; }
trap cleanup EXIT

say()  { printf '  %-6s %s\n' "$1" "$2"; }
ok()   { pass=$((pass + 1)); say "ok" "$1"; }
bad()  { fail=$((fail + 1)); say "FAIL" "$1"; }

# Runs a command with output swallowed and compares its exit status against what the guard
# is supposed to do. `refuse` means non-zero, `allow` means zero — asserting the DIRECTION
# rather than a specific code, because a hook that refuses is allowed to pick its own.
# A refusal must be OURS. Git declines plenty of things on its own — it will not delete the
# branch you have checked out, and it will not push what is already up to date — and a case
# that goes green on git's own refusal is testing nothing. So `refuse` asserts both a non-zero
# exit AND the marker these hooks print, which is why they print one.
expect() {
  local want="$1" what="$2"; shift 2
  local out status
  out="$("$@" 2>&1)"; status=$?
  case "$want:$status" in
    refuse:0)
      bad "$what — expected a refusal, got through"
      printf '%s\n' "$out" | sed 's/^/         /' ;;
    refuse:*)
      case "$out" in
        *REFUSED:*) ok "$what — refused" ;;
        *) bad "$what — refused, but not by the hook (no REFUSED: marker)"
           printf '%s\n' "$out" | sed 's/^/         /' ;;
      esac ;;
    allow:0)   ok  "$what — allowed" ;;
    allow:*)   bad "$what — expected to be allowed, exit $status"
               printf '%s\n' "$out" | sed 's/^/         /' ;;
  esac
}

echo "githooks self-test  (hooks: $HOOKS_DIR)"

# ---------------------------------------------------------------- a repo and its origin
git init -q --bare "$tmp/origin.git"
git init -q -b main "$tmp/work"
cd "$tmp/work" || exit 1
git config user.email selftest@example.com
git config user.name  selftest
git config commit.gpgsign false
git remote add origin "$tmp/origin.git"

# Seeded with the guard OFF, so the fixture itself is not the thing under test.
echo one > file.txt
git add file.txt
PKMNSCAN_MAIN=off git commit -qm "seed"
PKMNSCAN_MAIN=off git push -q -u origin main 2>/dev/null

git config core.hooksPath "$HOOKS_DIR"

# ---------------------------------------------------------------------------- the cases
echo "  -- the ordinary path stays open --"
git switch -q -c feature
echo two > file.txt
git add file.txt
expect allow "commit on a branch" git commit -qm "work on a branch"
expect allow "push a branch to origin" git push -q -u origin feature

echo "  -- main does not move locally --"
git switch -q main
echo three > file.txt
git add file.txt
expect refuse "commit directly on main" git commit -qm "straight onto main"
git reset -q
git checkout -q -- file.txt

expect refuse "fast-forward a branch into main" git merge --ff-only feature
expect refuse "reset main onto a local commit"  git reset --hard feature

# BOTH OF THESE RUN OFF main, and that is the whole point of the pair. Git answers first when
# you aim them at the branch you are standing on — "cannot force update the branch checked out
# at ..." — so run from main they were testing git and not the hook. Run from `feature` they
# reach the ref transaction, and `git branch -D main` is what found the deletion bug: it
# reports zeros on BOTH sides, so the hook read a delete as a no-op and let it through.
git switch -q feature
expect refuse "git branch -f main"  git branch -f main feature
expect refuse "delete main"         git branch -D main
# The plumbing form. `branch -f` and `update-ref` are separate probes into the same hole and
# a hook could plausibly be fixed for one and not the other, so both are cases.
expect refuse "git update-ref main" git update-ref refs/heads/main feature
git switch -q main

echo "  -- nothing pushes to main --"
# main equals origin/main here, so `git push origin main` is "Everything up-to-date" and git
# never calls pre-push at all. That is a real property of the pair — with main unable to move
# locally there is usually nothing to push — but it makes a useless test, so each case below
# is arranged to have something to send.
expect refuse "push feature:main"  git push origin feature:main
git switch -q feature
expect refuse "push HEAD:main"     git push origin HEAD:main
git switch -q main

# Now main genuinely IS ahead — moved through the hatch — so the plain form has work to do.
PKMNSCAN_MAIN=off git merge -q --ff-only feature
expect refuse "push main"          git push origin main
PKMNSCAN_MAIN=off git reset -q --hard origin/main

echo "  -- the legitimate path is open --"
# A merged pull request: origin's main advances without us, then we pull. The bare repo has
# no hooksPath of its own, so this is the server doing what GitHub would do.
git -C "$tmp/origin.git" update-ref refs/heads/main "$(git rev-parse feature)"
git fetch -q origin
expect allow "pull a commit origin already has" git merge --ff-only origin/main

echo "  -- the escape hatch --"
echo four > file.txt
git add file.txt
expect allow "PKMNSCAN_MAIN=off commit on main" env PKMNSCAN_MAIN=off git commit -qm "deliberate"
expect allow "PKMNSCAN_MAIN=off push to main"   env PKMNSCAN_MAIN=off git push -q origin main

echo "  -- a fresh clone is not a violation --"
# Rule 2, which the header calls out and nothing else here reaches: cloning CREATES main, and
# a guard that refuses that refuses `git clone`. Cheap to prove, and the alternative is
# discovering it on a new machine.
expect allow "clone into a new checkout" git clone -q "$tmp/origin.git" "$tmp/fresh"
( cd "$tmp/fresh" && git config core.hooksPath "$HOOKS_DIR" 2>/dev/null ) || true

echo "  -- other refs are untouched --"
expect allow "create a branch"  git branch scratch
expect allow "delete a branch"  git branch -D scratch
expect allow "tag"              git tag v-selftest
expect allow "fetch"            git fetch -q origin

echo
if [ "$fail" -eq 0 ]; then
  echo "githooks self-test: $pass passed"
  exit 0
fi
echo "githooks self-test: $fail FAILED, $pass passed"
exit 1
