#!/usr/bin/env bash
# scripts/merge-pr.py's local half, in a repository built and destroyed for the purpose.
#
# WHY THIS EXISTS. The local half MOVES main. It cannot be exercised in this repository
# without moving the main every live worktree is cut from, which is the incident D42 was built
# to stop — so the test builds its own origin, its own clone and its own linked worktree in a
# temporary directory, arms THESE hook files against it, and runs the real gestures. Exactly
# the arrangement scripts/githooks-selftest.sh takes, for the same reason and with the same
# `PKMNSCAN_HOOKS_DIR` override.
#
# WHY IT IS NOT IN THE GIT HOOK. It writes — a bare repo, a clone, a worktree, commits, pushes.
# D18: nothing that writes may run on the path that decides whether a commit proceeds. And
# githooks-selftest's second reason applies unchanged: it drives the thing that moves main.
#
# THE CASE THAT MATTERS IS `the footgun`. D42 names it and leaves it to a session to remember:
# main checked out NOWHERE while some other tree sits on a feature branch, where
# `git -C <that tree> pull --ff-only` fast-forwards THAT BRANCH, moves no protected ref, trips
# no hook, and says nothing. That case asserts the feature branch is byte-identical afterwards
# — the only assertion here that would catch the whole reason this wrapper was written.
#
# WHAT IT CANNOT PROVE. Anything about `gh`. The GitHub half is a shell-out to a service, so it
# is verified by ASKING gh for the state afterwards rather than by a test here; `--local` is
# the seam, and it exists so the dangerous half is the testable one.

set -uo pipefail

HOOKS_DIR="${PKMNSCAN_HOOKS_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/githooks" && pwd)}"
MERGE_PR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/merge-pr.py"
pass=0
fail=0

[ -f "$MERGE_PR" ] || { echo "no merge-pr.py beside this script"; exit 1; }

tmp="$(mktemp -d "${TMPDIR:-/tmp}/pkmnscan-merge.XXXXXX")" || { echo "cannot make a temp dir"; exit 1; }
cleanup() { rm -rf "$tmp"; }
trap cleanup EXIT

say()  { printf '  %-6s %s\n' "$1" "$2"; }
ok()   { pass=$((pass + 1)); say "ok" "$1"; }
bad()  { fail=$((fail + 1)); say "FAIL" "$1"; }
note() { printf '         %s\n' "$1"; }

# Asserts the DIRECTION of the exit status, like githooks-selftest, and for the same reason: a
# refusal is allowed to pick its own code. `refuse` also demands the REFUSED: marker, so a case
# that goes green because python crashed or git declined on its own is not scored as ours.
expect() {
  local want="$1" what="$2"; shift 2
  local out status
  out="$("$@" 2>&1)"; status=$?
  case "$want:$status" in
    refuse:0) bad "$what — expected a refusal, got through"; printf '%s\n' "$out" | sed 's/^/         /' ;;
    refuse:*) case "$out" in
                *REFUSED:*) ok "$what — refused" ;;
                *) bad "$what — refused, but not by the wrapper (no REFUSED: marker)"
                   printf '%s\n' "$out" | sed 's/^/         /' ;;
              esac ;;
    allow:0)  ok  "$what" ;;
    allow:*)  bad "$what — expected to succeed, exit $status"; printf '%s\n' "$out" | sed 's/^/         /' ;;
  esac
}

same() {  # a ref must not have moved
  local what="$1" was="$2" now="$3"
  if [ "$was" = "$now" ]; then ok "$what"; else bad "$what — moved $was -> $now"; fi
}

moved() {
  local what="$1" was="$2" now="$3"
  if [ "$was" != "$now" ] && [ -n "$now" ]; then ok "$what"; else bad "$what — still at $was"; fi
}

echo "merge self-test  (hooks: $HOOKS_DIR)"

# THE RIG HALF IS PINNED OFF FOR EVERY ARM BELOW, AND TURNED BACK ON FOR THE ONE SECTION THAT IS
# ABOUT IT (D176). `make merge` now has a third half: after main
# moves it puts the PRIMARY CHECKOUT back on main and fast-forwards it — and in this fixture the
# primary checkout is `$tmp/work`, which nearly every arm below deliberately parks on `feature`.
#
# MEASURED, BECAUSE THE FIRST DRAFT DID NOT DO THIS: the sync SUCCEEDED in the first local-half
# arm, switched `$tmp/work` onto main, and the footgun arm two sections later then found main
# checked out in a worktree and correctly picked the pull form — failing an assertion about the
# refspec form that had nothing wrong with it. Four arms went red for one state change three
# sections earlier, which is the hardest kind of fixture failure to read.
#
# So the arms that assert THE LOCAL HALF keep asserting exactly that, and the rig half gets a
# section of its own rather than being folded into every arm's expected state.
export PKMNSCAN_SYNC=off

# --------------------------------------------------- an origin, a clone and a second worktree
git init -q --bare "$tmp/origin.git"
git init -q -b main "$tmp/work"
cd "$tmp/work" || exit 1
git config user.email selftest@example.com
git config user.name  selftest
git config commit.gpgsign false
git remote add origin "$tmp/origin.git"

# Seeded with the guard OFF, so the fixture is not the thing under test.
echo one > file.txt
git add file.txt
PKMNSCAN_MAIN=off git commit -qm "seed"
PKMNSCAN_MAIN=off git push -q -u origin main 2>/dev/null

# The work a pull request would carry, landed on origin the way a merge on GitHub lands it:
# the server moves its own main and this clone has not seen it yet.
git switch -q -c feature
echo two > file.txt
git add file.txt
git commit -qm "the pull request"
git push -q -u origin feature 2>/dev/null
MERGED="$(git rev-parse feature)"
git -C "$tmp/origin.git" update-ref refs/heads/main "$MERGED"

# A SECOND COMMIT ON feature, PUSHED, THEN REWOUND LOCALLY — so the local branch is BEHIND its
# upstream and a `git pull --ff-only` aimed at it has something to do. Without this the footgun
# case below cannot fail: mutation-tested 2026-09-01 by forcing the picker to always choose the
# pull form, and the "other tree's branch did not move" assertion stayed green because the
# branch was already at the commit a pull would have brought it to. A case that cannot fail is
# not coverage, and that is this repo's own rule about its port checker.
echo two-and-a-bit > file.txt
git add file.txt
git commit -qm "further work on the branch, pushed"
git push -q origin feature 2>/dev/null
FEATURE_AHEAD="$(git rev-parse HEAD)"
git reset -q --hard "$MERGED"        # local feature is now one behind origin/feature

git switch -q --detach HEAD          # main is now checked out NOWHERE in this clone

git config core.hooksPath "$HOOKS_DIR"

# ------------------------------------------------------------------ main is checked out nowhere
echo "  -- main checked out nowhere: the refspec form --"
before="$(git rev-parse refs/heads/main)"
expect allow "preview presses nothing" python3 "$MERGE_PR" --local "$MERGED"
same "and main did not move under the preview" "$before" "$(git rev-parse refs/heads/main)"

expect allow "the local half, confirmed" python3 "$MERGE_PR" --local "$MERGED" --confirm
moved "main advanced to the merged commit" "$before" "$(git rev-parse refs/heads/main)"
if [ "$(git rev-parse refs/heads/main)" = "$MERGED" ]; then
  ok "and it is exactly the commit origin carries"
else
  bad "main is not the merged commit"
fi

# ------------------------------------------------------------------------------- THE FOOTGUN
echo "  -- the footgun: main nowhere, a feature branch in the other tree --"
# Reset so there is something to do again, then put a SECOND worktree on `feature`. This is the
# state D42 describes: the unconditional `git -C <other tree> pull --ff-only` advances that
# branch, silently. The wrapper must choose the refspec form and leave it alone.
PKMNSCAN_MAIN=off git update-ref refs/heads/main "$(git rev-list --max-parents=0 HEAD | tail -1)"
git worktree add -q "$tmp/other" feature 2>/dev/null
feature_before="$(git -C "$tmp/other" rev-parse HEAD)"
main_before="$(git rev-parse refs/heads/main)"
if [ "$feature_before" = "$FEATURE_AHEAD" ]; then
  bad "the fixture is wrong — feature is already at its upstream, so a wrong pull would be a no-op"
else
  ok "the fixture arms the case: feature is one behind origin/feature"
fi

expect allow "the wrapper picks the refspec form" python3 "$MERGE_PR" --local "$MERGED" --confirm
moved "main advanced" "$main_before" "$(git rev-parse refs/heads/main)"
same "AND THE OTHER TREE'S BRANCH DID NOT" "$feature_before" "$(git -C "$tmp/other" rev-parse HEAD)"
git worktree remove --force "$tmp/other" 2>/dev/null

# ------------------------------------------------------------- main checked out in a worktree
echo "  -- main checked out in a worktree: the pull form --"
PKMNSCAN_MAIN=off git update-ref refs/heads/main "$(git rev-list --max-parents=0 HEAD | tail -1)"
git worktree add -q "$tmp/mainwt" main 2>/dev/null
main_before="$(git -C "$tmp/mainwt" rev-parse HEAD)"
expect allow "the local half, confirmed" python3 "$MERGE_PR" --local "$MERGED" --confirm
moved "main advanced in the tree that holds it" "$main_before" "$(git -C "$tmp/mainwt" rev-parse HEAD)"

echo "  -- a dirty main worktree is reported, never forced --"
PKMNSCAN_MAIN=off git -C "$tmp/mainwt" reset -q --hard "$(git rev-list --max-parents=0 HEAD | tail -1)"
echo "uncommitted" >> "$tmp/mainwt/file.txt"
dirty_before="$(git -C "$tmp/mainwt" rev-parse HEAD)"
expect refuse "a dirty tree" python3 "$MERGE_PR" --local "$MERGED" --confirm
same "and nothing moved" "$dirty_before" "$(git -C "$tmp/mainwt" rev-parse HEAD)"
git -C "$tmp/mainwt" checkout -q -- file.txt
git worktree remove --force "$tmp/mainwt" 2>/dev/null

# ------------------------------------------------------------------------------- THE RIG HALF
#
# D176. THE HOLE THIS CLOSES IS THE REFSPEC FORM'S: with main
# checked out in no worktree — the ordinary state of a clone running ~30 worktrees on branches —
# `git fetch origin main:main` moves `refs/heads/main` while standing in no tree at all. main is
# then current and the primary checkout is still parked on whatever it was on, which is D158's
# exact state reached by the command whose job is to leave everything tidy.
#
# THE HATCH COMES OFF FOR THIS SECTION ONLY, and goes back on after it.
echo "  -- and the rig itself is put back on main --"
PKMNSCAN_MAIN=off git update-ref refs/heads/main "$(git rev-list --max-parents=0 HEAD | tail -1)"
git switch -q feature
parked_main="$(git rev-parse refs/heads/main)"
if [ "$(git rev-parse --abbrev-ref HEAD)" = "feature" ]; then
  ok "the fixture arms it: the primary checkout is parked on feature, main nowhere"
else
  bad "the fixture is wrong — the primary checkout is not on feature"
fi

unset PKMNSCAN_SYNC
expect allow "the merge runs, refspec form and all" python3 "$MERGE_PR" --local "$MERGED" --confirm
moved "main advanced" "$parked_main" "$(git rev-parse refs/heads/main)"
if [ "$(git rev-parse --abbrev-ref HEAD)" = "main" ]; then
  ok "AND THE PRIMARY CHECKOUT IS BACK ON MAIN — the half that used to be left undone"
else
  bad "the primary checkout is still on $(git rev-parse --abbrev-ref HEAD), not main"
fi
if [ "$(git rev-parse HEAD)" = "$(git rev-parse refs/remotes/origin/main)" ]; then
  ok "at origin/main, so the code in the rig is the code that was merged"
else
  bad "on main but not at origin/main — the second part did not run"
fi

# AND IT REFUSES RATHER THAN DISCARDING, which is the one thing it must never get wrong here.
git switch -q feature
PKMNSCAN_MAIN=off git update-ref refs/heads/main "$(git rev-list --max-parents=0 HEAD | tail -1)"
echo "work in progress" >> file.txt
rig_dirty_head="$(git rev-parse HEAD)"
out="$(python3 "$MERGE_PR" --local "$MERGED" --confirm 2>&1)"
case "$out" in
  *"uncommitted tracked changes"*file.txt*)
     ok "a dirty rig is REFUSED and the file is NAMED, and the merge still succeeded" ;;
  *) bad "a dirty rig was not refused by name"
     printf '%s\n' "$out" | sed 's/^/         /' ;;
esac
same "and the rig was not switched out from under the edit" "$rig_dirty_head" "$(git rev-parse HEAD)"
moved "while main still advanced — the rig half never fails the merge" \
  "$(git rev-list --max-parents=0 HEAD | tail -1)" "$(git rev-parse refs/heads/main)"
git checkout -q -- file.txt
export PKMNSCAN_SYNC=off

# ------------------------------------------------------------ a commit origin does not carry
echo "  -- the precondition the ref hook evaluates --"
PKMNSCAN_MAIN=off git update-ref refs/heads/main "$(git rev-list --max-parents=0 HEAD | tail -1)"
git switch -q -c local-only feature
echo three > file.txt
git add file.txt
git commit -qm "never pushed"
LOCAL_ONLY="$(git rev-parse HEAD)"
git switch -q --detach HEAD
before="$(git rev-parse refs/heads/main)"
expect refuse "a commit that is not on origin/main" python3 "$MERGE_PR" --local "$LOCAL_ONLY" --confirm
same "and main did not move" "$before" "$(git rev-parse refs/heads/main)"

echo "  -- a rev that names nothing --"
expect refuse "an unknown rev" python3 "$MERGE_PR" --local "no-such-thing" --confirm

# ------------------------------------------------------------------- the branch afterwards
# NEW 2026-09-05. `delete_head_branch` runs after a successful local half and deletes the merged
# PR's head branch. Its gh lookup cannot be tested here; `--cut` is the seam, exactly as
# `--local` is for the half that moves main.
#
# THE CASE THAT MATTERS IS THE WORKTREE ONE. The wrapper refused to delete anything for a
# stated reason — "live worktrees track branches in this clone" — and that reason is now a
# runtime check rather than a blanket refusal. If the check goes, a merge deletes a branch
# somebody is standing on.
echo "  -- the merged branch is deleted, unless somebody is standing on it --"
PKMNSCAN_MAIN=off git update-ref refs/heads/main "$MERGED"
git switch -q --detach HEAD
git update-ref refs/heads/feature "$MERGED"

expect allow "the preview presses nothing" python3 "$MERGE_PR" --cut feature
if git rev-parse --verify -q refs/heads/feature >/dev/null; then
  ok "and the branch is still here after the preview"
else
  bad "the preview deleted the branch"
fi

# held by a worktree — the branch must survive even though it IS an ancestor of main
git worktree add -q "$tmp/standing" feature 2>/dev/null
held_out="$(python3 "$MERGE_PR" --cut feature --confirm 2>&1)"
if git rev-parse --verify -q refs/heads/feature >/dev/null; then
  ok "KEPT — a tree is standing on it"
else
  bad "deleted a branch that is checked out in $tmp/standing"
fi
# AND IT IS THIS CHECK THAT KEPT IT. Survival alone is vacuous here: `git branch -D` refuses a
# branch checked out in a worktree on its own, so the assertion above stayed green with the
# worktree check mutated out — caught 2026-09-05. What the check actually buys is a stated
# decision instead of git's opaque "Cannot delete branch ... checked out at", so that sentence
# is what the case asserts.
case "$held_out" in
  *"kept — checked out in"*) ok "AND SAID SO, rather than leaving git to refuse it" ;;
  *) bad "kept, but not by this wrapper — git's own refusal stood in for the check"
     printf '%s\n' "$held_out" | sed 's/^/         /' ;;
esac
git worktree remove --force "$tmp/standing" 2>/dev/null

# not an ancestor of main — the branch holds commits main does not, so it must survive
expect allow "a branch main does not contain" python3 "$MERGE_PR" --cut local-only --confirm
if git rev-parse --verify -q refs/heads/local-only >/dev/null; then
  ok "KEPT — it is not an ancestor of main"
else
  bad "deleted a branch holding commits main does not have"
fi

# nobody standing on it, and every commit is in main — this one goes, on both sides.
#
# ORIGIN IS RE-ARMED HERE ON PURPOSE. The worktree case above KEPT the local branch and still
# deleted the remote one — the remote is checked out nowhere by definition, so that half is
# unconditional — which left origin with no feature branch and made the "AND DELETED ON ORIGIN"
# assertion below pass without this case doing anything. Caught 2026-09-05 by the fixture
# assertion that follows, which is the only reason it was not scored as coverage.
git -C "$tmp/origin.git" update-ref refs/heads/feature "$MERGED"
if git -C "$tmp/origin.git" rev-parse --verify -q refs/heads/feature >/dev/null; then
  ok "the fixture arms the case: origin still carries feature"
else
  bad "the fixture is wrong — origin has no feature branch to delete"
fi
expect allow "an ancestor branch nobody holds" python3 "$MERGE_PR" --cut feature --confirm
if git rev-parse --verify -q refs/heads/feature >/dev/null; then
  bad "the branch survived"
else
  ok "deleted here"
fi
if git -C "$tmp/origin.git" rev-parse --verify -q refs/heads/feature >/dev/null; then
  bad "origin still carries it"
else
  ok "AND DELETED ON ORIGIN"
fi

# A branch GitHub already deleted server-side. Once `delete_branch_on_merge` is on — set
# 2026-09-05 — this is EVERY merge, so the wrapper must not report the outcome it wanted as an
# error. `feature` is gone from origin by now: the case above deleted it.
if git -C "$tmp/origin.git" rev-parse --verify -q refs/heads/feature >/dev/null; then
  bad "the fixture is wrong — origin still has feature, so 'already gone' cannot be exercised"
else
  ok "the fixture arms the case: origin no longer carries feature"
fi
git update-ref refs/heads/feature "$MERGED"
already_out="$(python3 "$MERGE_PR" --cut feature --confirm 2>&1)"
case "$already_out" in
  *"already gone — nothing to delete"*) ok "a branch origin already dropped is not an error" ;;
  *) bad "reported a server-side deletion as a failure"
     printf '%s\n' "$already_out" | sed 's/^/         /' ;;
esac

# -------------------------------------- the copy of the merge THIS checkout would be running
#
# THE DEFECT IS THAT `make merge` RUNS THE MERGE SCRIPT OF WHATEVER CHECKOUT INVOKED IT, and
# a checkout older than a capability performs the merge without it, reports success, and leaves
# the work undone. It happened twice with the id claim. Measured the day this was written: 24
# of the 30 working trees of this clone were behind main's copy of that script, 16 of them
# missing the commit that introduced the claim at all.
#
# THE FIXTURE IS BUILT AS A PROGRESSION rather than as six repositories, because the arms that
# matter are the ones that must NOT fire and they are only meaningful against the same tree
# that does fire. main gains an unrelated commit (allowed), then a merge-surface commit
# (refused), the branch merges main (allowed), the branch then EDITS the merge itself (allowed
# — this is the pull request that wrote this block), and main moves again underneath it
# (refused).
echo "  -- the merge refuses a checkout whose own copy of it is behind --"
git init -q --bare "$tmp/surface-origin.git"
git init -q -b main "$tmp/surface"
cd "$tmp/surface" || exit 1
git config user.email selftest@example.com
git config user.name  selftest
git config commit.gpgsign false
git remote add origin "$tmp/surface-origin.git"

mkdir -p scripts
echo "# the merge, as it was" > scripts/merge-pr.py
echo "# the claimer, as it was" > scripts/claim-ids.py
echo "one" > unrelated.txt
git add -A
git commit -qm "the merge machinery as it was"
git push -q -u origin main 2>/dev/null
SURFACE_BASE="$(git rev-parse HEAD)"

# main moves, on something that is NOT the merge surface.
echo "two" > unrelated.txt
git add -A
git commit -qm "a change to something else entirely"
git push -q origin main 2>/dev/null

git switch -q -c surface-branch "$SURFACE_BASE"
git fetch -q origin 2>/dev/null

# NARROWNESS FIRST, because a guard that refuses everything behind main would refuse almost
# every branch in this clone and be turned off within a day. Being behind on `unrelated.txt`
# is not being behind on the merge.
expect allow "behind main, but not on the merge surface" python3 "$MERGE_PR" --surface

# main takes a capability, in the file `make merge` actually runs. THIS is the incident.
git switch -q main
echo "def claim_half():  # the capability" >> scripts/merge-pr.py
git add -A
git commit -qm "The number is claimed at the merge"
git push -q origin main 2>/dev/null
git switch -q surface-branch
git fetch -q origin 2>/dev/null

surface_out="$(python3 "$MERGE_PR" --surface 2>&1)"
if [ $? -eq 0 ]; then
  bad "a checkout missing main's merge-pr.py was allowed to merge"
  printf '%s\n' "$surface_out" | sed 's/^/         /'
else
  case "$surface_out" in
    *REFUSED:*scripts/merge-pr.py*"The number is claimed at the merge"*)
      ok "a checkout behind on scripts/merge-pr.py — refused, named the file AND the commit" ;;
    *REFUSED:*)
      bad "refused, but named neither the file nor the commit main has"
      printf '%s\n' "$surface_out" | sed 's/^/         /' ;;
    *) bad "refused, but not by the wrapper (no REFUSED: marker)"
       printf '%s\n' "$surface_out" | sed 's/^/         /' ;;
  esac
fi

# AND IT NAMES BOTH SHAS. The refusal is only actionable if it says which copy is which.
here_blob="$(git rev-parse --short HEAD:scripts/merge-pr.py)"
main_blob="$(git rev-parse --short origin/main:scripts/merge-pr.py)"
case "$surface_out" in
  *"$here_blob"*"$main_blob"*) ok "and both blobs, so the two copies can be told apart" ;;
  *) bad "the refusal names neither blob ($here_blob / $main_blob)"
     printf '%s\n' "$surface_out" | sed 's/^/         /' ;;
esac

# The fix the refusal prints has to be the fix.
git -c user.email=selftest@example.com -c user.name=selftest merge -q --no-edit origin/main 2>/dev/null
expect allow "and the merge it tells you to run clears it" python3 "$MERGE_PR" --surface

# ------------------------------------------------------------------- AHEAD IS NOT BEHIND
# The false positive that would make this guard unusable, and the case that decided the
# predicate. A branch DEVELOPING the merge differs from main's copy in every byte that matters
# — the pull request that added this section did exactly that — and `differs from origin/main`
# would refuse it. What is refused is MISSING main's commits, which this branch is not.
echo "  -- a branch that is developing the merge itself goes through --"
echo "# and this branch is changing it further" >> scripts/merge-pr.py
git add -A
git commit -qm "work on the merge itself"
if [ -n "$(git diff --stat origin/main -- scripts/merge-pr.py)" ]; then
  ok "the fixture arms the case: this branch's copy DIFFERS from main's"
else
  bad "the fixture is wrong — the branch's copy is identical, so \`differs\` could not fire"
fi
expect allow "AHEAD of main on the merge, and carrying every commit main has" \
  python3 "$MERGE_PR" --surface

# ----------------------------------------------------- and the surface is DERIVED, not the self
# scripts/claim-ids.py is in the surface because merge-pr.py declares it as the script it
# shells out to. A guard that only ever checked itself would have been green through the whole
# of the incident's second half.
echo "  -- the second file of the surface is guarded too --"
git switch -q main
echo "# a capability in the claimer" >> scripts/claim-ids.py
git add -A
git commit -qm "The claimer learns to read a commit"
git push -q origin main 2>/dev/null
git switch -q surface-branch
git fetch -q origin 2>/dev/null

claimer_out="$(python3 "$MERGE_PR" --surface 2>&1)"
case "$claimer_out" in
  *REFUSED:*scripts/claim-ids.py*)
    ok "behind on scripts/claim-ids.py — refused, and named it" ;;
  *REFUSED:*)
    bad "refused, but did not name scripts/claim-ids.py — the surface is not derived"
    printf '%s\n' "$claimer_out" | sed 's/^/         /' ;;
  *) bad "a checkout behind on the claimer was allowed to merge"
     printf '%s\n' "$claimer_out" | sed 's/^/         /' ;;
esac
# The same run is the DIVERGED case: this branch has its own commit on merge-pr.py AND lacks
# main's on claim-ids.py. It reads as behind, and that is right — it lacks the capability
# exactly as the stale checkout does.
case "$claimer_out" in
  *"merge origin/main"*) ok "AND the diverged branch is told to merge main, not to start over" ;;
  *) bad "the refusal does not print the one-command fix"
     printf '%s\n' "$claimer_out" | sed 's/^/         /' ;;
esac

# --------------------------------------------------- an answer it has not got is not a pass
echo "  -- an origin with no main --"
git init -q --bare "$tmp/surface-empty.git"
git init -q -b main "$tmp/surface-nomain"
cd "$tmp/surface-nomain" || exit 1
git config user.email selftest@example.com
git config user.name  selftest
git config commit.gpgsign false
git remote add origin "$tmp/surface-empty.git"
mkdir -p scripts
echo "# alone" > scripts/merge-pr.py
git add -A
git commit -qm "a clone whose origin has no main"
expect refuse "an origin carrying no main at all" python3 "$MERGE_PR" --surface

cd "$tmp/work" || exit 1

echo "  -- no pull request named --"
expect refuse "a bare invocation" python3 "$MERGE_PR"

echo
if [ "$fail" -eq 0 ]; then
  echo "merge self-test: $pass passed"
  exit 0
fi
echo "merge self-test: $fail FAILED, $pass passed"
exit 1
