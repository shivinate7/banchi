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

# Defaults to the TRACKED hooks beside this script. Overridable so the same nineteen cases
# can be run against the INSTALLED copy in the git common dir — `make hooks` copies rather
# than points now (D42, amended), and a copy that lands wrong is a guard that reads as armed
# and does nothing. Proving the files behave is not the same claim as proving the install did.
HOOKS_DIR="${PKMNSCAN_HOOKS_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/githooks" && pwd)}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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

# THE BRANCH WARNING IS ASSERTED ON OUTPUT, NOT ON EXIT STATUS, AND `expect` CANNOT SEE IT.
# `scripts/githooks/post-checkout` runs AFTER the switch has happened — git has no
# `pre-checkout` hook — so it has nothing left to refuse and exits 0 whichever way it decides
# (D139). A case written with `expect allow` would pass on a hook that printed nothing at all,
# which is the entire failure mode these two exist to catch. They assert the marker the warning
# leads with, which is why it leads with one rather than opening on prose.
MARK="PRIMARY CHECKOUT:"
says() {
  local what="$1"; shift
  local out; out="$("$@" 2>&1)"
  case "$out" in
    *"$MARK"*) ok "$what — warned" ;;
    *) bad "$what — no warning, and the live server is serving this branch"
       printf '%s\n' "$out" | sed 's/^/         /' ;;
  esac
}
silent() {
  local what="$1"; shift
  local out; out="$("$@" 2>&1)"
  case "$out" in
    *"$MARK"*) bad "$what — warned, and must not"
       printf '%s\n' "$out" | sed 's/^/         /' ;;
    *) ok "$what — silent" ;;
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
# THE SETUP SWITCHES BELOW DROP STDERR, AND ONLY BECAUSE THEY ARE SETUP. Every one of them moves
# this fixture — a primary checkout — onto a branch, so post-checkout's D139 warning fires on each
# and interleaves three blocks of it through sections about something else. The warning is ASSERTED
# in its own section at the foot of this file; muting it here is muting a passing guard's noise, not
# skipping a case, and it is done per-command rather than globally so a hook that starts printing
# somewhere unexpected still shows up.
git switch -q -c feature 2>/dev/null
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
git switch -q feature 2>/dev/null
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
git switch -q feature 2>/dev/null
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

echo "  -- D139: which branch the primary checkout stands on --"
# WHY THIS IS A GUARD AT ALL. D53 keeps a supervisor alive at login out of the PRIMARY checkout
# over the owner's real store, so the branch that ONE directory stands on silently decides which
# code serves their real inventory. A linked worktree has its own store and its own ports to be
# wrong on its own (D43), so it must stay silent — and that is the arm most likely to be written
# backwards, since `.git` is a FILE in the worktree and a DIRECTORY in the checkout and either
# reads fine to someone skimming it.
#
# MUTATION-TESTED 2026-09-11, by copying the hooks to a scratch directory, inverting that one
# test (`-d "$top/.git"` -> `-f "$top/.git"`) and re-running with PKMNSCAN_HOOKS_DIR pointed at
# the copy: the primary case and both worktree cases fail, 3 FAILED. Deleting the `!= "main"`
# arm fails the switch-back case. Deleting the block entirely fails all three `says` cases.
says   "a branch switch in the PRIMARY checkout"  git switch -q feature
# A FILE-LEVEL CHECKOUT IS NOT A BRANCH MOVE, and says nothing even standing off main: git passes
# $3 = 0 and the hook exits on it before either block. Asserted because without that gate every
# `git checkout -- path` would print the warning, which is the fastest way to teach a reader to
# skip it.
# IT IS GUARDED TWICE AND THIS CASE NEEDS BOTH GONE TO FAIL, which is a fact about the hook rather
# than a weakness here: git passes the SAME sha as $1 and $2 for a file-level checkout, so the
# `$old != $new` guard below covers exactly the same ground. Mutating either one alone leaves all
# twenty-eight cases green; mutating the pair fails this one.
silent "a file-level checkout while off main"     git checkout -q -- file.txt
silent "switching the PRIMARY checkout back to main" git switch -q main
# A DETACHED HEAD IS OFF MAIN AS SURELY AS A BRANCH IS, AND IT IS NAMED AS ONE. Two assertions
# and not the same one twice: `git rev-parse --abbrev-ref HEAD` answers the literal string `HEAD`
# when detached, so a warning that did not special-case it would read "now on HEAD, not main" and
# name a branch that does not exist. `says` cannot see that — mutating the naming out left every
# case in this section green. It also has to land on a DIFFERENT commit: `--detach` at the commit
# you are already on leaves $1 = $2, which the hook's own first guard drops as a no-op.
out="$(git switch -q --detach feature 2>&1)"
case "$out" in
  *"$MARK"*"detached HEAD"*) ok "a detached HEAD in the PRIMARY checkout — warned, and named as detached" ;;
  *"$MARK"*) bad "a detached HEAD warned, but was named as a branch called HEAD"
             printf '%s\n' "$out" | sed 's/^/         /' ;;
  *) bad "a detached HEAD in the PRIMARY checkout — no warning"
     printf '%s\n' "$out" | sed 's/^/         /' ;;
esac
silent "back to main from a detached HEAD"        git switch -q main

# A LINKED WORKTREE IS NOT THE SUBJECT. `main` is a real local branch here and the hook checks for
# one, so the silence below can only come from the primary/linked test — which is what makes these
# two cases worth having rather than passing for a second reason.
silent "creating a linked worktree"               git worktree add -q -b wt-one "$tmp/linked" feature
# AT `main`'s COMMIT AND NOT AT HEAD's, because `switch -c` at the same commit leaves $1 = $2 and
# the hook's own no-op guard drops it before the branch block is ever reached. Written that way
# first, this case passed on a mutant that had the primary/linked test INVERTED — green for the
# wrong reason, which is the defect this file's `expect` helper already has a paragraph about.
silent "a branch switch INSIDE a linked worktree" git -C "$tmp/linked" switch -q -c wt-two main
# Cleaned up so the fixture's own teardown is not left removing a registered worktree by rm -rf.
git worktree remove --force "$tmp/linked" 2>/dev/null || true
git branch -D wt-one wt-two 2>/dev/null >/dev/null || true

# A REPOSITORY THAT DOES NOT USE `main` IS NOT IN VIOLATION, and this is the one case the fixture
# above cannot make: `main` exists there by construction, so the hook's gate on `main` being a real
# local branch is unfalsifiable in it — mutating that gate out left all twenty-five other cases
# green. It matters because `make janitor-install` puts this repo's hooks in front of other
# checkouts, and a warning that fired in every `master`-based repository is a warning somebody
# switches off — which takes D42's refusals and the three opsec rules with it.
#
# Seeded BEFORE core.hooksPath is armed, for the same reason the fixture above is: the pre-commit
# hook is this repo's real one and the seed commit is not the thing under test. And branched at
# `master~1` rather than at HEAD, because a branch created at the commit you are standing on leaves
# $1 = $2 and never reaches the block.
git init -q -b master "$tmp/foreign"
git -C "$tmp/foreign" config user.email selftest@example.com
git -C "$tmp/foreign" config user.name  selftest
git -C "$tmp/foreign" config commit.gpgsign false
echo one > "$tmp/foreign/f.txt"; git -C "$tmp/foreign" add f.txt
git -C "$tmp/foreign" commit -qm "seed"
echo two > "$tmp/foreign/f.txt"; git -C "$tmp/foreign" add f.txt
git -C "$tmp/foreign" commit -qm "second"
git -C "$tmp/foreign" config core.hooksPath "$HOOKS_DIR"
silent "a branch switch where there is no \`main\`" git -C "$tmp/foreign" switch -q -c topic master~1

echo "  -- D-the-rig-refuses-to-serve-a-branch: the switch says what the SERVER will do about it --"
# WHY THE SECOND HALF IS IN THIS FILE AT ALL. The refusal itself lives in `scripts/serve.py`,
# and `scripts/serve.py` is a tracked file — so the checkout that just happened is exactly the
# event that can replace it with a copy carrying no guard. `make hooks` COPIES this hook into
# the common `.git` dir that `core.hooksPath` points every worktree at, so the copy git runs
# here is the one thing a branch switch cannot rewrite. It reports; it still refuses nothing.
mkdir -p "$tmp/work/.serve" "$tmp/work/scripts"
echo 1 > "$tmp/work/.serve/supervisor.pid"

# THE REAL serve.py, NOT A FIXTURE OF ONE, AND THAT IS THE POINT OF THIS PAIR. The hook decides
# whether a branch can refuse for itself by grepping that branch's serve.py for the escape
# hatch's name. A case that wrote the token by hand would stay green forever after the token
# was renamed in serve.py, and the hook would quietly start telling every switch that the guard
# is missing. Copying the shipped file makes the rename a FAILED COMMIT in one direction, and
# the gutted copy below covers the other.
cp "$REPO_ROOT/scripts/serve.py" "$tmp/work/scripts/serve.py"
out="$(git switch -q feature 2>&1)"
case "$out" in
  *"$MARK"*"will REFUSE to reload"*)
     ok "a live supervisor whose serve.py carries the guard — the switch says it will refuse" ;;
  *"$MARK"*)
     bad "the switch warned but said nothing about what the live server would do"
     printf '%s\n' "$out" | sed 's/^/         /' ;;
  *) bad "no warning at all on a branch switch with a live supervisor"
     printf '%s\n' "$out" | sed 's/^/         /' ;;
esac
git switch -q main 2>/dev/null

# THE OTHER DIRECTION, AND THE ONLY CASE THE SUPERVISOR'S OWN GUARD CANNOT COVER: a branch cut
# before the guard existed. Its serve.py will be re-exec'd into and will serve the real store,
# and nothing in that branch is going to say so — so this hook is the last thing that can.
sed 's/PKMNSCAN_SERVE_MAIN/RENAMED_BY_THIS_CASE/g' \
  "$REPO_ROOT/scripts/serve.py" > "$tmp/work/scripts/serve.py"
out="$(git switch -q feature 2>&1)"
case "$out" in
  *"$MARK"*"predates the guard"*)
     ok "a branch whose serve.py predates the guard — the switch says so and names the stop" ;;
  *"$MARK"*"will REFUSE to reload"*)
     bad "a branch with NO guard was reported as one that would refuse — the grep is inverted"
     printf '%s\n' "$out" | sed 's/^/         /' ;;
  *) bad "a branch predating the guard said nothing about the live server"
     printf '%s\n' "$out" | sed 's/^/         /' ;;
esac
git switch -q main 2>/dev/null

# AND IT MAY NOT INVENT A SERVER. D139's warning asserted that the live capture server "now
# runs THIS branch's code" whether or not one was running — the hazard printed as a fact. With
# no supervisor there is nothing to say about one, and a line that appears anyway is the same
# defect a register down.
rm -f "$tmp/work/.serve/supervisor.pid"
out="$(git switch -q feature 2>&1)"
case "$out" in
  *"supervisor is live"*)
     bad "no supervisor is running and the hook claimed one was"
     printf '%s\n' "$out" | sed 's/^/         /' ;;
  *"$MARK"*) ok "with no supervisor running, the switch warns and claims nothing about a server" ;;
  *) bad "the branch warning stopped firing when .serve/supervisor.pid went away"
     printf '%s\n' "$out" | sed 's/^/         /' ;;
esac
git switch -q main 2>/dev/null
rm -rf "$tmp/work/.serve" "$tmp/work/scripts/serve.py"

# AND THE BLOCK D139 DID NOT TOUCH, which was covered by nothing: deleting the `make hooks`
# staleness reminder outright left every other case in this file green. Two blocks now share one
# hook file, so "intact and untouched" was a claim about a diff rather than something asserted —
# and a reminder that silently stopped firing is a clone running hooks nobody installed.
# It fires when `scripts/githooks` differs across the two commits, so the fixture has to carry such
# a path on one side only. Switching TO main, so the branch warning is silent and this reminder is
# the only thing that can be in the output.
mkdir -p "$tmp/work/scripts/githooks"
echo "#!/bin/sh" > "$tmp/work/scripts/githooks/example"
git switch -q -c hookful 2>/dev/null
git add scripts/githooks/example
PKMNSCAN_MAIN=off git commit -qm "a branch that carries its own hooks" >/dev/null 2>&1
out="$(git switch -q main 2>&1)"
case "$out" in
  *"make hooks"*) ok "the \`make hooks\` staleness reminder still fires on a branch move" ;;
  *) bad "scripts/githooks differed across the switch and nothing said \`make hooks\`"
     printf '%s\n' "$out" | sed 's/^/         /' ;;
esac

# ------------------------------------------- main carrying an unclaimed id, the moment it moves
#
# WHY THIS BELONGS IN A HOOK AND NOT ONLY IN scripts/merge-pr.py. `make merge` runs the merge
# script of whatever checkout invoked it, so a guard inside that script is absent from exactly
# the checkouts that need it — 24 of the 30 working trees of this clone were behind main's copy
# of it the day this was written. `core.hooksPath` is one installed directory in the common
# .git dir, so THIS file is the same file for every one of them, and a main move is the one
# event all of them share.
#
# IT IS ASSERTED ON OUTPUT AND NOT ON EXIT STATUS, for the reason the branch warning above is:
# this half refuses nothing and exits 0 whatever it decides, so `expect allow` would pass over
# a hook that printed nothing at all. The marker it leads with is what the cases read.
echo "  -- main carrying an unclaimed id is reported the moment it moves --"
SLUG_MARK="UNCLAIMED ID ON main"
# THE FIXTURE'S IDS ARE COMPOSED AND NEVER SPELLED. This file sits inside the auditor's own
# haystack, so a literal `D-...` heading here IS a citation of an entry that does not exist and
# a literal number is a citation the map would then have to carry under `governed_by`. Both
# were reported on the first run of this block. scripts/claim-selftest.py composes its fixture
# ids from integers for exactly this reason and records it in the same words.
SLUG_ID="D-""an-id-nobody-claimed"
cd "$tmp/work" || exit 1
git switch -q -c slugful main 2>/dev/null
mkdir -p docs
printf '## %s — a title\n' "$SLUG_ID" > docs/DECISIONS.md
git add docs/DECISIONS.md
git commit -qm "an entry whose id the merge never claimed" >/dev/null 2>&1
git push -q -u origin slugful 2>/dev/null
SLUGGED="$(git rev-parse HEAD)"
git -C "$tmp/origin.git" update-ref refs/heads/main "$SLUGGED"
git switch -q --detach HEAD 2>/dev/null      # main checked out nowhere: the refspec form works
git fetch -q origin 2>/dev/null

slug_out="$(git fetch origin main:main 2>&1)"
case "$slug_out" in
  *"$SLUG_MARK"*) ok "a main that carries a slug is reported when it lands" ;;
  *) bad "main moved onto an unclaimed id and the hook said nothing"
     printf '%s\n' "$slug_out" | sed 's/^/         /' ;;
esac
case "$slug_out" in
  *"$SLUG_ID"*) ok "AND NAMES THE ID, so the repair does not need a search" ;;
  *) bad "reported, but did not name the id"
     printf '%s\n' "$slug_out" | sed 's/^/         /' ;;
esac
# ONCE, AND ABOUT main. A fetch that writes the refspec moves refs/heads/main and the
# remote-tracking ref in transactions the hook sees back to back; a report that does not ask
# which ref it is looking at says the same thing twice about one move, and a reader who has
# learned to skim a doubled warning is a reader this hook has already lost.
if [ "$(printf '%s\n' "$slug_out" | grep -c "$SLUG_MARK")" = "1" ]; then
  ok "exactly once — the report asks which ref moved"
else
  bad "the report fired $(printf '%s\n' "$slug_out" | grep -c "$SLUG_MARK") times for one move"
fi
# AND IT REFUSED NOTHING: main is where the fetch was taking it.
if [ "$(git rev-parse refs/heads/main)" = "$SLUGGED" ]; then
  ok "and main moved anyway — the report is a report"
else
  bad "the report blocked the move; main is at $(git rev-parse --short refs/heads/main)"
fi

# The other direction, which is the one a vacuous implementation passes: a clean main is SILENT.
git switch -q slugful 2>/dev/null
printf '## D%s — the same entry, with its number\n' 1 > docs/DECISIONS.md
git add docs/DECISIONS.md
git commit -qm "the number claimed" >/dev/null 2>&1
git push -q origin slugful 2>/dev/null
CLAIMED="$(git rev-parse HEAD)"
git -C "$tmp/origin.git" update-ref refs/heads/main "$CLAIMED"
git switch -q --detach HEAD 2>/dev/null
git fetch -q origin 2>/dev/null
clean_out="$(git fetch origin main:main 2>&1)"
case "$clean_out" in
  *"$SLUG_MARK"*) bad "a main with no unclaimed id was reported anyway"
     printf '%s\n' "$clean_out" | sed 's/^/         /' ;;
  *) ok "a main whose ids are all numbers — silent" ;;
esac

# AND IT IS main IT READS, NOT WHATEVER ELSE IS IN THE PAYLOAD. This clone's `main` moves to a
# clean commit while a second ref in the SAME transaction moves to the slugged one; a hook that
# read every line of a main-mentioning payload would report that other ref's commit under a
# heading that says `ON main`, which is worse than saying nothing.
#
# `update-ref --stdin` RATHER THAN A FETCH, AND THE FIXTURE MEASURED WHY. `git fetch` with two
# refspecs issues ONE TRANSACTION PER REF here — measured on this machine's git, two `prepared`
# payloads of one ref each — so no fetch can produce the shape this case needs. `update-ref
# --stdin` is the porcelain that batches, and it is a real gesture rather than the hook being
# fed by hand.
git switch -q slugful 2>/dev/null
printf '## D%s — the same entry\n## D%s — and another\n' 1 2 > docs/DECISIONS.md
git add docs/DECISIONS.md
git commit -qm "a second numbered entry" >/dev/null 2>&1
git push -q origin slugful 2>/dev/null
CLAIMED2="$(git rev-parse HEAD)"
git -C "$tmp/origin.git" update-ref refs/heads/main "$CLAIMED2"
git switch -q --detach HEAD 2>/dev/null
git fetch -q origin 2>/dev/null
both_out="$(printf 'update refs/heads/main %s\nupdate refs/heads/sidecar %s\n' \
              "$CLAIMED2" "$SLUGGED" | git update-ref --stdin 2>&1)"
if [ "$(git rev-parse refs/heads/sidecar 2>/dev/null)" = "$SLUGGED" ]; then
  ok "the fixture arms the case: one transaction moved main AND a slugged sidecar"
else
  bad "the fixture is wrong — the batched update-ref did not land"
  printf '%s\n' "$both_out" | sed 's/^/         /'
fi
case "$both_out" in
  *"$SLUG_MARK"*) bad "reported another ref's commit as main's"
     printf '%s\n' "$both_out" | sed 's/^/         /' ;;
  *) ok "a slug on a ref that is NOT main — silent" ;;
esac

echo
if [ "$fail" -eq 0 ]; then
  echo "githooks self-test: $pass passed"
  exit 0
fi
echo "githooks self-test: $fail FAILED, $pass passed"
exit 1
