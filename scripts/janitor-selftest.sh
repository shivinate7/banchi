#!/usr/bin/env bash
# `make janitor-selftest` — scripts/janitor.py, proved against a throwaway clone.
#
# WHY THIS EXISTS. The janitor deletes worktrees, branches and processes. It cannot be proved
# against this repo, because the cases worth proving are the destructive ones and the fixture
# has to be disposable. So it gets a temp origin, a clone, real worktrees, a fake liveness
# oracle and two real processes in their own process groups, and every case runs against that.
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
spawn() {
  python3 -c "
import subprocess, sys
with open('/dev/null', 'wb') as null:
    p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)', sys.argv[1]],
                         stdin=null, stdout=null, stderr=null, start_new_session=True)
print(p.pid)
" "$1"
}

alive() { kill -0 "$1" 2>/dev/null; }

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
busy_pid="$(spawn "$tmp/marker.py")"; kids="$kids $busy_pid"
now_ms="$(python3 -c 'import time; print(int(time.time()*1000))')"
cat > "$tmp/sessions/$busy_pid.json" <<JSON
{"pid": $busy_pid, "cwd": "$tmp/work/.claude/worktrees/busy",
 "startedAt": $now_ms, "name": "fixture-session"}
JSON

holder_pid="$(spawn "$tmp/marker.py")"; kids="$kids $holder_pid"
cat > "$tmp/sessions/$holder_pid.json" <<JSON
{"pid": $holder_pid, "cwd": "$tmp/work/.claude/worktrees/holder",
 "startedAt": $now_ms, "name": "fixture-holder"}
JSON

# a process holding the busy husk open. Its marker sits INSIDE `.serve/` so the directory's
# contents stay a subset of HUSK_NAMES — put it beside `.serve/` and the directory stops
# being a husk at all, and the case would pass without ever testing anything.
touch "$tmp/work/.claude/worktrees/husk-busy/.serve/keep.py"
husk_pid="$(spawn "$tmp/work/.claude/worktrees/husk-busy/.serve/keep.py")"; kids="$kids $husk_pid"

# an orphan: its own script is gone, its project directory is not
orphan_pid="$(spawn "$tmp/work/.claude/worktrees/ghost/scripts/serve.py")"; kids="$kids $orphan_pid"

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
