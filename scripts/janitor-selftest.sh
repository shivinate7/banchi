#!/usr/bin/env bash
# `make janitor-selftest` — scripts/janitor.py, proved against a throwaway clone.
#
# WHY THIS EXISTS. The janitor deletes worktrees, branches and processes. It cannot be proved
# against this repo, because the cases worth proving are the destructive ones and the fixture
# has to be disposable. So it gets a temp origin, a clone, real worktrees, a fake liveness
# oracle and real processes in their own process groups, and every case runs against that.
#
# SOME OF THOSE PROCESSES CARRY A FAKE SHELL SNAPSHOT IN THEIR ARGV, because that is how
# `loose_processes` proves a Claude Code session started something. The most important case in
# this file is the one that must NOT fire: a long-lived process in the MAIN checkout, carrying
# the mark and owned by no session, which is what `make launch-agent` leaves running over the
# owner's real store. `pkill -f` has killed that process once already (D127).
#
# WHY IT IS NOT IN THE GIT HOOK. D18: it writes — a temp tree, and signals it sends. Nothing
# that writes may run on the path that decides whether a commit proceeds. It IS in `make check`,
# which is exactly `merge-selftest`'s standing.
#
# THE CASES THAT MATTER ARE THE REFUSALS. A sweep that reaps the right things and also reaps a
# live worktree is worse than no sweep, and on 2026-09-06 an early build of this one did offer
# to reap two trees with sessions in them — a timezone bug in the liveness oracle made every
# session read as dead. `_same_process` carries that account. So the KEEP cases here assert the
# janitor's own sentence, not merely that the thing survived: git would have refused some of
# them on its own, and survival by somebody else's refusal is not coverage.
#
# WHAT IT CANNOT PROVE. Anything about the real `~/.claude/sessions` — the oracle is pointed at
# a fixture directory here. And it never runs unconfined, so it says nothing about the sweep's
# behaviour over the machine's whole process table.

set -uo pipefail          # NOT -e: every case must run and be scored

JANITOR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/janitor.py"
pass=0
fail=0

[ -f "$JANITOR" ] || { echo "no janitor.py beside this script"; exit 1; }

tmp="$(mktemp -d "${TMPDIR:-/tmp}/pkmnscan-janitor.XXXXXX")" || { echo "cannot make a temp dir"; exit 1; }
kids=""
cleanup() {
  for k in $kids; do kill "$k" 2>/dev/null; done
  rm -rf "$tmp"
}
trap cleanup EXIT

say()  { printf '  %-6s %s\n' "$1" "$2"; }
ok()   { pass=$((pass + 1)); say "ok" "$1"; }
bad()  { fail=$((fail + 1)); say "FAIL" "$1"; }

# A process in ITS OWN process group, so the janitor's killpg can never reach this script.
#
# ITS PIPES GO TO /dev/null, AND THAT IS NOT TIDINESS. `$(spawn ...)` waits for every writer of
# the captured pipe to close it, so a child that inherits stdout holds the command substitution
# open for as long as it lives — this hung for the full `sleep` the first time it was run.
#
# AND IT IS PYTHON, NOT `bash -c '...' "$path"`, BECAUSE THE PATH HAS TO SURVIVE INTO `ps`.
# Bash execs a lone simple command instead of forking for it, so `bash -c 'sleep 300' /x/y.py`
# leaves `ps` showing `sleep 300` and nothing else — the janitor looks for the path in the
# argv, found none, and three cases passed for the wrong reason.
plain_spawn() {
  python3 -c "
import subprocess, sys
with open('/dev/null', 'wb') as null:
    p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)', sys.argv[1]],
                         stdin=null, stdout=null, stderr=null, start_new_session=True)
print(p.pid)
" "$1"
}

alive() { kill -0 "$1" 2>/dev/null; }

# A PROCESS STARTED THE WAY A CLAUDE CODE SESSION STARTS ONE, which is what `loose_processes`
# keys on. The Bash tool runs every command as `zsh -c 'source ~/.claude/shell-snapshots/
# snapshot-zsh-<n>-<id>.sh ... && <command>'`, so the wrapper's argv names a shell snapshot and
# the real command is its child. This reproduces both halves: it prints "<parent> <child>", the
# parent carrying the snapshot path in its argv and the child carrying only a path under the
# tree — so the child is a candidate ONLY if the ancestor walk works, which is the arm that
# matters. `plain_spawn` above is left alone: it detaches with `start_new_session`, so its own
# wrapper is gone and it carries no mark at all, which is exactly what the older cases need.
#
# BOTH PATHS IN THE ARGV MUST EXIST, AND THE SNAPSHOT IS THE ONE THAT BITES. It ends in `.sh`
# and sits under a directory named `.claude`, so a missing one is a TIER 1 ORPHAN by
# `_project_ancestor`'s test and the fixture's own processes would be reaped before the case
# under test ever ran.
# ARGUMENTS: <snapshot> <parent's path> <child's path> <working directory>. All four are
# explicit at every call site rather than defaulted, because three of the cases below exist
# precisely to make those paths DIFFER — a default would hide the case in the call.
spawn_marked_pair() {
  python3 - "$1" "$2" "$3" "$4" <<'PY'
import os, subprocess, sys
snap, target, kid_target, where = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
# The parent SLEEPS rather than waiting on the child, so a SIGTERM to one is not a SIGTERM to
# both: the cases below need each judged on its own.
body = (
    "import os, subprocess, sys, time\n"
    "null = open('/dev/null', 'wb')\n"
    "kid = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)',\n"
    "                        os.environ['FIXTURE_KID_PATH']],\n"
    "                       stdin=null, stdout=null, stderr=null)\n"
    "sys.stdout.write('%d %d\\n' % (os.getpid(), kid.pid))\n"
    "sys.stdout.flush()\n"
    "time.sleep(300)\n"
)
# THE CHILD'S PATH TRAVELS IN THE ENVIRONMENT AND NOT IN ARGV, WHICH IS THE WHOLE OF THE
# BYSTANDER CASE. `ps` shows argv, so a child path passed as an argument would appear in the
# PARENT's command line too and place the parent under the same tree — and the parent would be
# offered alongside the child, leaving `_stop`'s leader-only rule untested. Measured: it read 4
# offers where the case needs 3, and the bystander died of being a subject rather than of the
# mutation under test.
env = dict(os.environ, FIXTURE_KID_PATH=kid_target)
with open("/dev/null", "wb") as null:
    # `target` sits in the parent's argv, which is faithful — a wrapper's command line carries
    # the command it is about to run. `snap` is what makes it a session's wrapper.
    parent = subprocess.Popen([sys.executable, "-c", body, snap, target],
                              stdin=null, stdout=subprocess.PIPE, stderr=null,
                              start_new_session=True, cwd=where, env=env)
    print(parent.stdout.readline().decode().strip())
PY
}

# Assert the janitor SAID something, not just that the outcome happened.
said() {
  local what="$1" needle="$2" out="$3"
  case "$out" in
    *"$needle"*) ok "$what" ;;
    *) bad "$what — the janitor never said \"$needle\""
       printf '%s\n' "$out" | sed 's/^/         /' ;;
  esac
}

not_said() {
  local what="$1" needle="$2" out="$3"
  case "$out" in
    *"$needle"*) bad "$what — the janitor said \"$needle\" and should not have"
                 printf '%s\n' "$out" | sed 's/^/         /' ;;
    *) ok "$what" ;;
  esac
}

# --------------------------------------------------------------------------- the fixture
# Built with the hooks unarmed: the fixture is not the thing under test.
git init -q --bare "$tmp/origin.git"
git init -q -b main "$tmp/work"
cd "$tmp/work" || exit 1
git config user.email selftest@example.com
git config user.name  selftest
git config commit.gpgsign false
git remote add origin "$tmp/origin.git"

echo one > file.txt
git add file.txt
git commit -qm seed
git push -q -u origin main 2>/dev/null

# merged, nobody holds it -> reapable
git branch merged-loose
# merged, a worktree holds it -> kept
git branch merged-held
git worktree add -q "$tmp/work/.claude/worktrees/holder" merged-held 2>/dev/null
# unmerged, on no remote -> the one that must never be touched
git checkout -q -b unmerged-local
echo two > only-here.txt
git add only-here.txt
git commit -qm "a commit that exists on this disk and nowhere else"
git checkout -q main
# named backup/ -> never considered, whatever its state
git branch backup/keepme
# an idle worktree with no session -> tier 2 reapable
git branch idle-tree
git worktree add -q "$tmp/work/.claude/worktrees/idle" idle-tree 2>/dev/null
# a worktree with uncommitted work -> kept
git branch dirty-tree
git worktree add -q "$tmp/work/.claude/worktrees/dirty" dirty-tree 2>/dev/null
echo scratch > "$tmp/work/.claude/worktrees/dirty/uncommitted.txt"
# a worktree a session is standing in -> kept
git branch busy-tree
git worktree add -q "$tmp/work/.claude/worktrees/busy" busy-tree 2>/dev/null

# husks: directories under .claude/worktrees that git does not know about
mkdir -p "$tmp/work/.claude/worktrees/husk-quiet/.serve"
echo log > "$tmp/work/.claude/worktrees/husk-quiet/.serve/capture.log"
mkdir -p "$tmp/work/.claude/worktrees/husk-busy/.serve"
echo log > "$tmp/work/.claude/worktrees/husk-busy/.serve/capture.log"

# the fake liveness oracle
#
# THE LIVE PROCESSES POINT AT A FILE THAT EXISTS, AND THAT IS THE WHOLE DIFFERENCE between
# them and the orphan. Tier 1's test is "your own script is gone", so a fixture process named
# after a file nobody created IS an orphan and is meant to be reaped. Pointing the session's
# process at a real marker keeps the only difference between the cases the one under test.
# A session's tree is bound by the RECORD's cwd, never by its process's argv, so the marker
# can live outside the worktree and leave it clean.
mkdir -p "$tmp/sessions"
touch "$tmp/marker.py"
busy_pid="$(plain_spawn "$tmp/marker.py")"; kids="$kids $busy_pid"
now_ms="$(python3 -c 'import time; print(int(time.time()*1000))')"
cat > "$tmp/sessions/$busy_pid.json" <<JSON
{"pid": $busy_pid, "cwd": "$tmp/work/.claude/worktrees/busy",
 "startedAt": $now_ms, "name": "fixture-session"}
JSON

holder_pid="$(plain_spawn "$tmp/marker.py")"; kids="$kids $holder_pid"
cat > "$tmp/sessions/$holder_pid.json" <<JSON
{"pid": $holder_pid, "cwd": "$tmp/work/.claude/worktrees/holder",
 "startedAt": $now_ms, "name": "fixture-holder"}
JSON

# a process holding the busy husk open. Its marker sits INSIDE `.serve/` so the directory's
# contents stay a subset of HUSK_NAMES — put it beside `.serve/` and the directory stops
# being a husk at all, and the case would pass without ever testing anything.
touch "$tmp/work/.claude/worktrees/husk-busy/.serve/keep.py"
husk_pid="$(plain_spawn "$tmp/work/.claude/worktrees/husk-busy/.serve/keep.py")"; kids="$kids $husk_pid"

# an orphan: its own script is gone, its project directory is not
orphan_pid="$(plain_spawn "$tmp/work/.claude/worktrees/ghost/scripts/serve.py")"; kids="$kids $orphan_pid"

# ------------------------------------------------- the process nothing owns any more (D175)
#
# THE FAKE SHELL SNAPSHOT IS THE FIXTURE'S WHOLE LEVER. `loose_processes` will name only a
# process it can PROVE a session started, and the proof is this path in the argv. It lives
# outside the clone, exactly as the real one lives outside every checkout, and it is TOUCHED
# because a missing `.sh` under a `.claude` directory is a tier 1 orphan (see spawn_marked_pair).
mkdir -p "$tmp/fake-home/.claude/shell-snapshots"
snap="$tmp/fake-home/.claude/shell-snapshots/snapshot-zsh-1789000000000-fixture.sh"
touch "$snap"

# a worktree holding a background loop whose session has ended -> OFFERED, tier 2
git branch loose-tree
git worktree add -q "$tmp/work/.claude/worktrees/loose" loose-tree 2>/dev/null
mkdir -p "$tmp/work/.claude/worktrees/loose/scratchpad"
touch "$tmp/work/.claude/worktrees/loose/scratchpad/autodrive.sh"
read -r loose_parent loose_kid <<<"$(spawn_marked_pair "$snap" \
  "$tmp/work/.claude/worktrees/loose/scratchpad/autodrive.sh" \
  "$tmp/work/.claude/worktrees/loose/scratchpad/autodrive.sh" \
  "$tmp/work/.claude/worktrees/loose")"
kids="$kids $loose_parent $loose_kid"

# the same shape in a tree a session IS standing in -> REFUSED, and the count says so
git branch owned-tree
git worktree add -q "$tmp/work/.claude/worktrees/owned" owned-tree 2>/dev/null
mkdir -p "$tmp/work/.claude/worktrees/owned/scratchpad"
touch "$tmp/work/.claude/worktrees/owned/scratchpad/watcher.sh"
read -r owned_parent owned_kid <<<"$(spawn_marked_pair "$snap" \
  "$tmp/work/.claude/worktrees/owned/scratchpad/watcher.sh" \
  "$tmp/work/.claude/worktrees/owned/scratchpad/watcher.sh" \
  "$tmp/work/.claude/worktrees/owned")"
kids="$kids $owned_parent $owned_kid"
# The record names the PARENT, so the child is owned only through the ancestor walk — which is
# the half that carries the finding. A record naming the child itself would prove nothing.
now2_ms="$(python3 -c 'import time; print(int(time.time()*1000))')"
cat > "$tmp/sessions/$owned_parent.json" <<JSON
{"pid": $owned_parent, "cwd": "$tmp/work/.claude/worktrees/owned",
 "startedAt": $now2_ms, "name": "fixture-owner"}
JSON

# THE SUPERVISOR ARM, AND IT IS THE MOST IMPORTANT CASE IN THIS FILE. A long-lived process in
# the MAIN checkout with no session record at all is what `make launch-agent` leaves running over
# the owner's real store, and D53 means it to outlive every session. It is given the session mark
# as well — the worst case for the rule, not the easiest — so that being in the main checkout is
# the ONLY thing standing between it and a reap.
mkdir -p "$tmp/work/scripts"
touch "$tmp/work/scripts/serve.py"
read -r rig_parent rig_kid <<<"$(spawn_marked_pair "$snap" \
  "$tmp/work/scripts/serve.py" "$tmp/work/scripts/serve.py" "$tmp/work")"
kids="$kids $rig_parent $rig_kid"

# THE INCIDENT'S OWN SHAPE, AND THE ONLY CASE THE WORKING DIRECTORY CAN PLACE. The loop of
# 2026-09-11 was `bash scratchpad/autodrive.sh` — a script the session had written outside the
# checkout, so its command line carries no path under any clone at all and `_placed`'s first
# arm finds nothing. What ties it to a tree is the directory it RUNS in.
mkdir -p "$tmp/outside"
touch "$tmp/outside/autodrive.sh"
git branch cwd-tree
git worktree add -q "$tmp/work/.claude/worktrees/cwdonly" cwd-tree 2>/dev/null
read -r cwd_parent cwd_kid <<<"$(spawn_marked_pair "$snap" \
  "$tmp/outside/autodrive.sh" "$tmp/outside/autodrive.sh" \
  "$tmp/work/.claude/worktrees/cwdonly")"
kids="$kids $cwd_parent $cwd_kid"

# A BYSTANDER LEADING THE GROUP AN OFFERED PROCESS SITS IN. Only the CHILD is placed here — the
# parent's own path is outside the clone — so the child is offered alone while its parent leads
# the process group it belongs to. `_stop` signals the group only when the process LEADS it, and
# this is the case that makes that rule load-bearing: signalling the group on a non-leader's
# behalf reaches a process nothing in this sweep ever judged.
mkdir -p "$tmp/work/.claude/worktrees/loose/scratchpad"
touch "$tmp/bystander.sh" "$tmp/work/.claude/worktrees/loose/scratchpad/inner.sh"
read -r bystander_pid inner_pid <<<"$(spawn_marked_pair "$snap" \
  "$tmp/bystander.sh" "$tmp/work/.claude/worktrees/loose/scratchpad/inner.sh" \
  "$tmp/outside")"
kids="$kids $bystander_pid $inner_pid"

# A CLONE WITH NOTHING RUNNING UNDER IT, for the census. `examined` of nought and `examined` of
# twelve must not print the same sentence, and no case above can tell those apart because the
# fixture always has processes in it.
git init -q -b main "$tmp/quiet"
git -C "$tmp/quiet" config user.email selftest@example.com
git -C "$tmp/quiet" config user.name selftest
git -C "$tmp/quiet" config commit.gpgsign false
echo quiet > "$tmp/quiet/file.txt"
git -C "$tmp/quiet" add file.txt
git -C "$tmp/quiet" commit -qm seed

sleep 0.5

echo
echo "  -- the fixture arms the cases --"
git merge-base --is-ancestor merged-loose main \
  && ok "merged-loose really is an ancestor of main" \
  || bad "the fixture is wrong — merged-loose is not merged, so a reap would be right for the wrong reason"
git merge-base --is-ancestor unmerged-local main \
  && bad "the fixture is wrong — unmerged-local IS merged, so keeping it proves nothing" \
  || ok "unmerged-local really is unmerged"
[ -z "$(git for-each-ref --format='%(refname:short)' --contains unmerged-local refs/remotes/)" ] \
  && ok "unmerged-local really is on no remote" \
  || bad "the fixture is wrong — unmerged-local is on a remote, so losing it would be recoverable"
alive "$busy_pid"   && ok "the fixture session's pid is alive"   || bad "the fixture is wrong — session pid is dead"
alive "$orphan_pid" && ok "the orphan process is running"        || bad "the fixture is wrong — orphan is dead"
[ ! -e "$tmp/work/.claude/worktrees/ghost/scripts/serve.py" ] \
  && ok "the orphan's own script really is missing" \
  || bad "the fixture is wrong — the orphan's script exists, so it is not an orphan"
[ -f "$tmp/marker.py" ] \
  && ok "the live processes' marker really exists — they are not orphans by accident" \
  || bad "the fixture is wrong — the marker is missing, so every live process reads as an orphan"
[ -f "$snap" ] \
  && ok "the fake shell snapshot really exists — the marked processes are not orphans either" \
  || bad "the fixture is wrong — the snapshot is missing, so tier 1 reaps every marked process"
alive "$loose_parent" && alive "$loose_kid" \
  && ok "the loose pair is running" || bad "the fixture is wrong — the loose pair is dead"
alive "$owned_parent" && alive "$owned_kid" \
  && ok "the owned pair is running" || bad "the fixture is wrong — the owned pair is dead"
alive "$rig_parent" \
  && ok "the main-checkout process is running" || bad "the fixture is wrong — the rig arm is dead"
[ "$loose_parent" != "$loose_kid" ] && [ -n "$loose_kid" ] \
  && ok "the loose pair really is two processes — the ancestor walk has something to walk" \
  || bad "the fixture is wrong — spawn_marked_pair returned one pid, so the child case is absent"
alive "$cwd_kid" \
  && ok "the cwd-only pair is running" || bad "the fixture is wrong — the cwd-only pair is dead"
# `ps -o command=` WITHOUT `-a`: on BSD ps the `-a` flag overrides `-p` and prints the whole
# machine's process table, so the first spelling of this matched a path under the clone from
# somebody else's process entirely and failed a fixture that was correct.
case "$(ps -ww -o command= -p "$cwd_kid")" in
  *"$tmp/work"*) bad "the fixture is wrong — the cwd-only process names a path under the clone, so arm one places it and the cwd arm is never reached" ;;
  *) ok "the cwd-only process names NO path under the clone — only its directory ties it here" ;;
esac
alive "$bystander_pid" && alive "$inner_pid" \
  && ok "the bystander and the process inside its group are running" \
  || bad "the fixture is wrong — the bystander pair is dead"
[ "$(ps -o pgid= -p "$inner_pid" | tr -d ' ')" = "$bystander_pid" ] \
  && ok "the offered process really sits in the bystander's process group" \
  || bad "the fixture is wrong — inner is not in the bystander's group, so _stop's rule is untested"

# ------------------------------------------------------------------------------- PREVIEW
echo
echo "  -- preview presses nothing --"
prev="$(python3 "$JANITOR" --root "$tmp/work" --sessions "$tmp/sessions" --confine "$tmp" 2>&1)"

said "the idle tree is offered"            "would reap" "$prev"
said "the loose merged branch is offered"  "merged-loose" "$prev"
git show-ref -q --verify refs/heads/merged-loose \
  && ok "PREVIEW LEFT merged-loose ALONE" || bad "preview deleted merged-loose"
[ -d "$tmp/work/.claude/worktrees/idle" ] \
  && ok "PREVIEW LEFT the idle worktree alone" || bad "preview removed the idle worktree"

# ------------------------------------------------------------------------------ REFUSALS
echo
echo "  -- the refusals, asserted on the janitor's own sentence --"
said "a live session is named as the reason"  "a session is live in it" "$prev"
said "uncommitted work is named as the reason" "uncommitted file(s)"    "$prev"
said "an unmerged branch on no remote is called out" "ON NO REMOTE"     "$prev"
said "a backup/ branch is called out"          "named backup/"          "$prev"
not_said "the busy tree is never offered"      "worktrees/busy  (no"    "$prev"
not_said "the dirty tree is never offered"     "worktrees/dirty  (no"   "$prev"
not_said "an unmerged branch is never offered" "would reap unmerged-local" "$prev"
not_said "a backup/ branch is never offered"   "would reap backup/keepme" "$prev"
not_said "a held branch is never offered"      "would reap merged-held" "$prev"

# ------------------------------------------------------ the process nothing owns any more
echo
echo "  -- a background loop whose session has ended --"

said "the loose parent is offered"  "would reap pid $loose_parent" "$prev"
said "the loose child is offered — the ancestor walk found the mark" \
     "would reap pid $loose_kid" "$prev"
said "the offer says WHY"           "no live session owns it"       "$prev"
said "the offer names the tree"     "worktrees/loose"               "$prev"

# NON-VACUITY. A sweep that enumerated nothing must not print what a sweep that read the whole
# table prints. This is the line that tells those two apart, and the count in it is the proof
# the cases above were reached rather than skipped.
# THE INCIDENT ITSELF: a script outside the checkout, tied to a tree only by where it runs.
said "a loop whose script lives outside the clone is still offered" \
     "would reap pid $cwd_kid" "$prev"
said "and it is placed in the tree it RAN in" "worktrees/cwdonly" "$prev"

# NON-VACUITY, BOTH DIRECTIONS. A sweep that enumerated nothing must not print what a sweep
# that read the whole table prints.
said "the census line is printed"   "process(es) a session started under this clone" "$prev"
not_said "the census is not the empty sentence" "nothing to judge" "$prev"
quiet="$(python3 "$JANITOR" --root "$tmp/quiet" --sessions "$tmp/sessions" --confine "$tmp" 2>&1)"
said "a clone with nothing running under it says SO, in its own words" \
     "nothing to judge" "$quiet"
not_said "and does not print the census of a sweep that examined something" \
     "process(es) a session started under this clone" "$quiet"

# --------------------------------------------------------------- THE REFUSALS THAT MATTER
echo
echo "  -- and the three it must never touch --"

# THE SUPERVISOR ARM. `make launch-agent` keeps this process alive at login over the owner's
# real store; D53 means it to outlive every session, and `pkill -f` has already killed it once.
not_said "THE MAIN CHECKOUT'S PROCESS IS NEVER OFFERED" \
         "would reap pid $rig_parent" "$prev"
not_said "nor its child"            "would reap pid $rig_kid"    "$prev"
said "and the refusal is PRINTED, naming D53" \
     "the MAIN CHECKOUT's — D53 means it to outlive every session" "$prev"

# A live session owns these, so the sweep does not get to decide: the owner is there to ask.
not_said "a process a live session owns is never offered" \
         "would reap pid $owned_kid" "$prev"
not_said "nor its owning parent"    "would reap pid $owned_parent" "$prev"

# FAIL CLOSED ON A TARGET IT CANNOT PLACE. `$husk_pid` runs out of this clone and no session
# record mentions it, so every ownership test above says "loose" — and it is still passed over
# in silence, because nothing proves a SESSION started it. That is the whole asymmetry: absence
# of a record is not absence of an owner, and the owner's own hand-started `make dev` has no
# record either.
not_said "A PROCESS CARRYING NO SESSION MARK IS NEVER OFFERED" \
         "would reap pid $husk_pid" "$prev"

# AND IT NEVER OFFERS ITS OWN CHAIN. Run from a LINKED worktree, the sweep's own process is
# placed under a tree it is willing to reap in, carries the mark through the wrapper that
# started it, and is owned by a session this fixture's oracle has never heard of — every test
# says loose. `_chain(table, mine)` is the only thing between that and `--confirm` signalling
# the session's own shell. D111 records the one time this oracle returned nought: the sweep
# offered up the tree it was standing in.
#
# IT IS COUNTED RATHER THAN GREPPED FOR A NAME, and that is not a style choice: the offer line
# renders the command through `_shorten`, and this interpreter's own path is long enough that
# `janitor.py` falls off the end of it. An early version of this arm looked for that word,
# could never have found it, and passed while the guard it names was deleted.
own="$(python3 "$JANITOR" --root "$tmp/work/.claude/worktrees/loose" \
       --sessions "$tmp/sessions" --confine "$tmp" 2>&1)"
own_offers="$(printf '%s\n' "$own" | grep -c 'would reap pid' || true)"
[ "$own_offers" -gt 0 ] \
  && ok "the run from a linked worktree offers something — the count below means something" \
  || bad "the fixture is wrong — that run offered nothing at all, so the self-exclusion is untested"
case "$own" in
  *"would reap pid $inner_pid"*) ok "THE SWEEP NEVER NAMES ITSELF — it offers its subjects and not its own chain" ;;
  *) bad "the fixture is wrong — inner was not offered from the linked-worktree root" ;;
esac
[ "$own_offers" -eq 3 ] \
  && ok "exactly the three loose processes are offered, and the sweep is not the fourth" \
  || bad "THE SWEEP OFFERED $own_offers processes, not 3 — its own chain is in the list"

# THE WALL CLOCK, BOTH DIRECTIONS. Seconds old against a 48 h threshold must say nothing, and
# the same run with the threshold dropped must say it — otherwise the arm above passes because
# the staleness test is dead code rather than because the process is young.
not_said "a process under the threshold is not called stale" "still owns it" "$prev"
stale="$(python3 "$JANITOR" --root "$tmp/work" --sessions "$tmp/sessions" --confine "$tmp" \
         --stale-hours 0 2>&1)"
said "the same process IS called stale once the threshold is below it" \
     "still owns it" "$stale"
not_said "AND IT IS STILL NOT OFFERED, AT ANY THRESHOLD" \
         "would reap pid $owned_kid" "$stale"
alive "$owned_kid" && ok "the stale run pressed nothing" || bad "the stale run killed an owned process"

# ------------------------------------------------------------------------------- TIER 1
echo
echo "  -- tier 1: the provably dead, no confirmation --"
t1="$(python3 "$JANITOR" --root "$tmp/work" --sessions "$tmp/sessions" --confine "$tmp" --tier1 2>&1)"
sleep 0.5
alive "$orphan_pid" && bad "the orphan survived tier 1" || ok "the orphan whose script is gone was reaped"
alive "$busy_pid"   && ok "TIER 1 LEFT the live session's process alone" || bad "tier 1 killed the session's process"
alive "$husk_pid"   && ok "TIER 1 LEFT the husk's process alone"         || bad "tier 1 killed the husk's process"
[ ! -d "$tmp/work/.claude/worktrees/husk-quiet" ] \
  && ok "the quiet husk was reaped" || bad "the quiet husk survived"
[ -d "$tmp/work/.claude/worktrees/husk-busy" ] \
  && ok "THE BUSY HUSK SURVIVED — it would only come back" || bad "the busy husk was reaped under a running process"
said "the busy husk says why it was kept" "it would come back" "$t1"
# TIER 2, NOT TIER 1, AND THIS IS THE ARM THAT HOLDS THAT LINE. `make status` runs the bare
# preview at the head of every session and `sweep` reaps tier 1 before it looks at `confirm` at
# all — so a tier 1 placement would SIGTERM these with no preview and no prompt.
alive "$loose_parent" \
  && ok "TIER 1 LEFT THE LOOSE PROCESS ALONE — it waits for a word" \
  || bad "tier 1 killed a loose process; \`make status\` would now press this with no prompt"
alive "$rig_parent" \
  && ok "TIER 1 LEFT THE MAIN CHECKOUT'S PROCESS ALONE" || bad "tier 1 killed the rig arm"

# ------------------------------------------------------------------------------ CONFIRM
echo
echo "  -- --confirm performs tier 2 --"
did="$(python3 "$JANITOR" --root "$tmp/work" --sessions "$tmp/sessions" --confine "$tmp" --confirm 2>&1)"

git show-ref -q --verify refs/heads/merged-loose \
  && bad "merged-loose survived --confirm" || ok "merged-loose was reaped"
[ -d "$tmp/work/.claude/worktrees/idle" ] \
  && bad "the idle worktree survived --confirm" || ok "the idle worktree was reaped"
git show-ref -q --verify refs/heads/unmerged-local \
  && ok "UNMERGED-LOCAL SURVIVED --confirm — 47 commits is what this rule is worth" \
  || bad "unmerged-local was DELETED — commits that existed nowhere else are gone"
git show-ref -q --verify refs/heads/backup/keepme \
  && ok "backup/keepme survived --confirm" || bad "backup/keepme was deleted"
git show-ref -q --verify refs/heads/merged-held \
  && ok "merged-held survived — a worktree holds it" || bad "merged-held was deleted while held"
[ -d "$tmp/work/.claude/worktrees/busy" ] \
  && ok "THE BUSY TREE SURVIVED --confirm" || bad "a tree with a live session was removed"
[ -d "$tmp/work/.claude/worktrees/dirty" ] \
  && ok "the dirty tree survived --confirm" || bad "a tree with uncommitted work was removed"
[ -f "$tmp/work/file.txt" ] \
  && ok "THE MAIN CHECKOUT WAS NEVER TOUCHED" || bad "the main checkout was damaged"

sleep 0.5
alive "$loose_parent" && bad "the loose parent survived --confirm" \
  || ok "the loose parent was reaped on the word"
alive "$loose_kid"    && bad "the loose child survived --confirm" \
  || ok "the loose child was reaped with it"
alive "$owned_parent" \
  && ok "A PROCESS A LIVE SESSION OWNS SURVIVED --confirm" \
  || bad "--confirm killed a process a live session owns"
alive "$owned_kid" \
  && ok "and so did its child" || bad "--confirm killed an owned process's child"
alive "$rig_parent" \
  && ok "THE MAIN CHECKOUT'S PROCESS SURVIVED --confirm — this is the rig" \
  || bad "--confirm killed the main checkout's process; on the real machine that is the owner's server"
alive "$cwd_kid" && bad "the cwd-only loop survived --confirm" \
  || ok "the loop placed only by its directory was reaped"
alive "$bystander_pid" \
  && ok "THE BYSTANDER LEADING THE GROUP SURVIVED — the group is signalled only from its leader" \
  || bad "--confirm signalled a process group on a non-leader's behalf and took a bystander with it"

# ------------------------------------------------------------------------- NOT A REPO
echo
echo "  -- a directory that is not a clone --"
mkdir -p "$tmp/plain"
out="$(python3 "$JANITOR" --root "$tmp/plain" 2>&1)"
status=$?
case "$status:$out" in
  0:*) bad "a non-repository was accepted" ;;
  *REFUSED:*) ok "a non-repository is refused, with the marker" ;;
  *) bad "refused, but not by the janitor (no REFUSED: marker)"
     printf '%s\n' "$out" | sed 's/^/         /' ;;
esac

echo
if [ "$fail" -eq 0 ]; then
  echo "janitor self-test: $pass passed"
  exit 0
fi
echo "janitor self-test: $fail FAILED, $pass passed"
exit 1
