#!/usr/bin/env bash
# `make janitor-selftest` — scripts/janitor.py (tier 1, --branches, --teardown), proved against a throwaway clone.
# Protects: The janitor presses only what is provably dead, cuts only merged branches, and tears down only a leaving tree, proved on a throwaway clone with real processes.
#
# WHY THIS EXISTS. What stays in janitor.py deletes directories and signals nothing, but it
# still cannot be proved against this repo: the cases worth proving are the destructive ones and
# the fixture has to be disposable. So it gets a temp clone, a fake liveness oracle and real
# processes in their own process groups.
#
# THE SWEEP PROPER IS NOT HERE. Dead-rooted servers, loose processes, worktrees and tier 2 are
# claude-settings' `janitor/sweep.py`, proved by its own `test_sweep.py`. What this file keeps
# is the three modes that sweep has no equivalent for: tier 1 alone (`--tier1`), the lossless
# branch cut (`--branches`), and one tree's teardown (`--teardown`).
#
# WHY IT IS NOT IN THE GIT HOOK. D18: it writes. It IS in `make check`, which is exactly
# `merge-selftest`'s standing.
#
# THE CASES THAT MATTER ARE THE REFUSALS, asserted on the janitor's own sentence, because git
# refuses some of them on its own and survival by somebody else's refusal is not coverage.
#
# WHAT IT CANNOT PROVE. Anything about the real `~/.claude/sessions`: the oracle is pointed at a
# fixture directory here.

set -uo pipefail          # NOT -e: every case must run and be scored

JANITOR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/janitor.py"
pass=0
fail=0

[ -f "$JANITOR" ] || { echo "no janitor.py beside this script"; exit 1; }

tmp="$(mktemp -d "${TMPDIR:-/tmp}/pkmnscan-janitor.XXXXXX")" || { echo "cannot make a temp dir"; exit 1; }
kids=""
cleanup() {
  for k in $kids; do kill "$k" 2>/dev/null; done
  # One case below makes a directory unwritable to force `git worktree remove` to fail. It puts
  # the mode back itself; this is the backstop for a run that dies before it gets there, because
  # `rm -rf` cannot unlink out of a parent it may not write either.
  chmod -R u+rwX "$tmp" 2>/dev/null
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
git init -q -b main "$tmp/work"
cd "$tmp/work" || exit 1
git config user.email selftest@example.com
git config user.name  selftest
git config commit.gpgsign false
echo one > file.txt
git add file.txt
git commit -qm seed

# husks: directories under .claude/worktrees that git does not know about
mkdir -p "$tmp/work/.claude/worktrees/husk-quiet/.serve"
echo log > "$tmp/work/.claude/worktrees/husk-quiet/.serve/capture.log"
mkdir -p "$tmp/work/.claude/worktrees/husk-busy/.serve"
echo log > "$tmp/work/.claude/worktrees/husk-busy/.serve/capture.log"

# the fake liveness oracle. The process points at a file that exists, so nothing here is an
# orphan by accident.
mkdir -p "$tmp/sessions"
touch "$tmp/marker.py"
now_ms="$(python3 -c 'import time; print(int(time.time()*1000))')"
busy_pid="$(plain_spawn "$tmp/marker.py")"; kids="$kids $busy_pid"

# a process holding the busy husk open. Its marker sits INSIDE `.serve/` so the directory's
# contents stay a subset of HUSK_NAMES — put it beside `.serve/` and the directory stops
# being a husk at all, and the case would pass without ever testing anything.
touch "$tmp/work/.claude/worktrees/husk-busy/.serve/keep.py"
husk_pid="$(plain_spawn "$tmp/work/.claude/worktrees/husk-busy/.serve/keep.py")"; kids="$kids $husk_pid"

# A DIRECTORY UNDER `.claude/worktrees/` THAT CANNOT BE READ AT ALL. `husks` listed every entry
# with a bare `entry.iterdir()`, and an unreadable one raises — out of TIER 1, which runs
# unattended at every session end. It is not a husk and it is not reaped; it is stepped over.
mkdir -p "$tmp/work/.claude/worktrees/husk-sealed"
chmod 0000 "$tmp/work/.claude/worktrees/husk-sealed"

# A HUSK WITH A SESSION STANDING IN IT. A session whose worktree was pruned out from under it
# is left standing in exactly this: a directory git no longer registers, holding only `.serve/`.
mkdir -p "$tmp/work/.claude/worktrees/husk-session/.serve"
echo log > "$tmp/work/.claude/worktrees/husk-session/.serve/capture.log"
husk_session_pid="$(plain_spawn "$tmp/marker.py")"; kids="$kids $husk_session_pid"
cat > "$tmp/sessions/$husk_session_pid.json" <<JSON
{"pid": $husk_session_pid, "cwd": "$tmp/work/.claude/worktrees/husk-session",
 "startedAt": $now_ms, "name": "fixture-in-a-husk"}
JSON

# A STALE REGISTRATION: git lists a worktree whose directory is gone.
git branch gone-tree
git worktree add -q "$tmp/work/.claude/worktrees/gone" gone-tree 2>/dev/null
rm -rf "$tmp/work/.claude/worktrees/gone"

sleep 0.5

echo
echo "  -- the fixture arms the cases --"
alive "$busy_pid"   && ok "the fixture session's pid is alive"   || bad "the fixture is wrong — session pid is dead"
alive "$husk_pid"   && ok "the busy husk's process is running"   || bad "the fixture is wrong — the husk process is dead"
git worktree list | grep -q "/gone " \
  && ok "git still registers the removed worktree — the prune arm has a subject" \
  || bad "the fixture is wrong — no stale registration, so the prune arm tests nothing"

# ------------------------------------------------------------------------------- PREVIEW
echo
echo "  -- preview presses nothing --"
prev="$(python3 "$JANITOR" --root "$tmp/work" --sessions "$tmp/sessions" 2>&1)"
said "the quiet husk is offered"            "would reap" "$prev"
said "the stale registration is offered"    "registration" "$prev"
[ -d "$tmp/work/.claude/worktrees/husk-quiet" ] \
  && ok "PREVIEW LEFT the quiet husk alone" || bad "preview removed the quiet husk"
git worktree list | grep -q "/gone " \
  && ok "PREVIEW LEFT the stale registration alone" || bad "preview pruned the registration"

# ------------------------------------------------------------------------------ TIER 1
echo
echo "  -- tier 1: the provably dead, no confirmation --"
t1="$(python3 "$JANITOR" --root "$tmp/work" --sessions "$tmp/sessions" --tier1 2>&1)"
sleep 0.5
alive "$busy_pid"   && ok "TIER 1 LEFT the live session's process alone" || bad "tier 1 killed the session's process"
alive "$husk_pid"   && ok "TIER 1 LEFT the husk's process alone"         || bad "tier 1 killed the husk's process"
[ ! -d "$tmp/work/.claude/worktrees/husk-quiet" ] \
  && ok "the quiet husk was reaped" || bad "the quiet husk survived"
git worktree list | grep -q "/gone " \
  && bad "the stale registration survived tier 1" || ok "the stale registration was pruned"
# NON-VACUITY FOR THE SEALED DIRECTORY: the quiet husk sorts after `husk-sealed`, so a raise on
# the sealed one would have taken tier 1 down before ever reaching it.
[ -d "$tmp/work/.claude/worktrees/husk-sealed" ] \
  && ok "AND THE UNREADABLE DIRECTORY WAS STEPPED OVER, not deleted and not fatal" \
  || bad "a directory the sweep could not even list was removed"
[ -d "$tmp/work/.claude/worktrees/husk-busy" ] \
  && ok "THE BUSY HUSK SURVIVED — it would only come back" || bad "the busy husk was reaped under a running process"
said "the busy husk says why it was kept" "it would come back" "$t1"
[ -d "$tmp/work/.claude/worktrees/husk-session" ] \
  && ok "A HUSK WITH A LIVE SESSION IN IT SURVIVED TIER 1 — no process was running under it" \
  || bad "tier 1 deleted a directory a live session is standing in, with no preview and no prompt"
said "and it says a session is the reason" "a session is live in it (fixture-in-a-husk)" "$t1"


# ------------------------------------------------- THE LEAVING SESSION IS ITS OWN ANCESTOR
#
# `--teardown` is what the SessionEnd and WorktreeRemove hooks run. It excludes "this session"
# from the list of sessions still standing in the tree by comparing `os.getpid()` — the janitor
# process — against the record's pid, which is the `claude` process several levels ABOVE it.
# Those two can never be equal, so the leaving session always counted as somebody else still
# being there and the teardown declined to stop anything, every single time it ran.
#
# THE ARM IS TWO RUNS OVER ONE TREE, because "it stopped nothing" is what a correct teardown
# prints for a tree with nothing in it. One record names an ancestor of the janitor (this
# script's own shell, which the janitor is a descendant of); the other names a process that is
# no relation.
echo
echo "  -- a session ending does not count itself as somebody else --"

git init -q -b main "$tmp/td"
git -C "$tmp/td" config user.email selftest@example.com
git -C "$tmp/td" config user.name selftest
git -C "$tmp/td" config commit.gpgsign false
echo seed > "$tmp/td/file.txt"
git -C "$tmp/td" add file.txt
git -C "$tmp/td" commit -qm seed
git -C "$tmp/td" branch leaving
git -C "$tmp/td" worktree add -q "$tmp/td/.claude/worktrees/leaving" leaving 2>/dev/null
mkdir -p "$tmp/td/.claude/worktrees/leaving/scripts"
printf 'import sys\nsys.exit(0)\n' > "$tmp/td/.claude/worktrees/leaving/scripts/serve.py"

td_now="$(python3 -c 'import time; print(int(time.time()*1000))')"
mkdir -p "$tmp/td-mine" "$tmp/td-other"
cat > "$tmp/td-mine/$$.json" <<JSON
{"pid": $$, "cwd": "$tmp/td/.claude/worktrees/leaving",
 "startedAt": $(ps -o lstart= -p $$ | python3 -c 'import sys,time; print(int(time.mktime(time.strptime(sys.stdin.read().strip()))*1000))'),
 "name": "the-leaving-session"}
JSON
cat > "$tmp/td-other/$busy_pid.json" <<JSON
{"pid": $busy_pid, "cwd": "$tmp/td/.claude/worktrees/leaving",
 "startedAt": $td_now, "name": "somebody-else"}
JSON

td_mine="$(python3 "$JANITOR" --teardown "$tmp/td/.claude/worktrees/leaving" \
           --sessions "$tmp/td-mine" 2>&1)"
said "THE LEAVING SESSION'S OWN RECORD DOES NOT STOP ITS OWN TEARDOWN" \
     "servers stopped" "$td_mine"
td_other="$(python3 "$JANITOR" --teardown "$tmp/td/.claude/worktrees/leaving" \
            --sessions "$tmp/td-other" 2>&1)"
said "AND A RECORD THAT IS NO RELATION STILL DOES — the exclusion is the chain, not everybody" \
     "still here" "$td_other"

# ------------------------------------------- `--branches`: TIER 2'S LOSSLESS SUBSET, UNATTENDED
#
# ITS OWN FIXTURE, because every assertion here is about what SURVIVES, and the sweeps above
# have already reaped their own tree's branches by this point. A clone of its own is the only
# way to state "this and nothing else was cut" and have it mean anything.
echo
echo "  -- --branches: the one part of tier 2 a hook may run --"
git init -q -b main "$tmp/br"
cd "$tmp/br" || exit 1
git config user.email selftest@example.com
git config user.name  selftest
git config commit.gpgsign false
echo one > file.txt
git add file.txt
git commit -qm seed

git branch br-merged-loose                       # main has every commit, nobody holds it -> CUT
git branch br-merged-held                        # main has every commit, a tree holds it -> KEPT
git worktree add -q "$tmp/br/.claude/worktrees/held" br-merged-held 2>/dev/null
git branch backup/br-keepme                      # named backup/ -> never considered
# AN IDLE TREE, CLEAN AND SESSIONLESS — exactly what claude-settings' sweep removes under --confirm.
# Without one here, "no worktree was removed" is a claim over an empty set: the only branch
# this mode cuts has no tree by construction, so a mode that DID remove trees would pass.
git branch br-idle-tree
git worktree add -q "$tmp/br/.claude/worktrees/idle" br-idle-tree 2>/dev/null
git checkout -q -b br-unmerged
echo two > only-here.txt
git add only-here.txt
git commit -qm "a commit main does not have"
git checkout -q main

out="$(python3 "$JANITOR" --root "$tmp/br" --branches 2>&1)"
said "a bare --branches PREVIEWS the cut" "would reap br-merged-loose" "$out"
if git -C "$tmp/br" show-ref --quiet refs/heads/br-merged-loose; then
  ok "and presses nothing — the branch is still there after the preview"
else
  bad "the PREVIEW cut a branch"
fi

trees_before="$(git -C "$tmp/br" worktree list | wc -l | tr -d ' ')"
out="$(python3 "$JANITOR" --root "$tmp/br" --branches --confirm 2>&1)"
said "--branches --confirm cuts the merged, unheld branch" "reaped    br-merged-loose" "$out"

# A HELD BRANCH IS NOT CONSIDERED AT ALL, WHICH IS STRONGER THAN "IT SURVIVED". `git branch -D`
# refuses a branch checked out in a linked worktree on its own, so survival alone passes even
# when `held` is not consulted — measured: dropping `held` entirely left every arm here green.
# What only the real protection produces is SILENCE about that branch.
case "$out" in
  *br-merged-held*) bad "--branches considered a branch a worktree is standing on" ;;
  *) ok "and says nothing at all about the branch a worktree holds — the held set is \
consulted, rather than git's own refusal being leaned on after the fact" ;;
esac

if git -C "$tmp/br" show-ref --quiet refs/heads/br-merged-loose; then
  bad "br-merged-loose survived --branches --confirm"
else
  ok "br-merged-loose is gone, and every object it named is reachable from main"
fi
for keep in br-merged-held br-unmerged backup/br-keepme main; do
  if git -C "$tmp/br" show-ref --quiet "refs/heads/$keep"; then
    ok "$keep survived — held, unmerged, backup/ and main are each protected"
  else
    bad "$keep WAS CUT — --branches took something it had no business taking"
  fi
done

# THE LOSSLESS CLAIM IS THE WHOLE ARGUMENT FOR RUNNING THIS WITH NOBODY WATCHING, so it is
# asserted rather than stated: the worktree is still there and its files are still in it. The
# full sweep removes trees; this mode may not, whatever it decides about branches.
trees_now="$(git -C "$tmp/br" worktree list | wc -l | tr -d ' ')"
if [ "$trees_now" = "$trees_before" ] \
   && [ -f "$tmp/br/.claude/worktrees/held/file.txt" ] \
   && [ -f "$tmp/br/.claude/worktrees/idle/file.txt" ]; then
  ok "no worktree was removed — the IDLE one the sweep would have taken is still here, \
which is what makes this mode's blast radius branches and nothing else"
else
  bad "--branches removed a worktree ($trees_before trees before, $trees_now after)"
fi

# AND IT IS IDEMPOTENT, which is what lets a hook run it on every session end without a second
# thought about how many times it has already run.
out="$(python3 "$JANITOR" --root "$tmp/br" --branches --confirm 2>&1)"
case "$out" in
  *reaped*) bad "a second run cut something — it is not idempotent" ;;
  *) ok "a second run cuts nothing and says nothing — safe on every session end" ;;
esac

# FAILS CLOSED ON A LAYOUT IT CANNOT READ, AND THE SUBJECT HAS TO EXIST FOR THAT TO MEAN
# ANYTHING. `held` comes from `git worktree list`: with no trees, no branch is protected and
# every one becomes eligible, which is the one way this mode could cut something somebody is
# standing on. The first build of this arm copied the clone AFTER the cut above, so there was
# no cuttable branch left in it and the assertion passed over an empty set — green, and about
# nothing. This one makes a fresh cuttable branch first, then takes the tree list away, so the
# guard is the only thing standing between it and a cut.
git -C "$tmp/br" branch br-blind-subject
out="$(python3 - "$JANITOR" "$tmp/br" <<'BLIND'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("janitor", sys.argv[1])
j = importlib.util.module_from_spec(spec); sys.modules["janitor"] = j
spec.loader.exec_module(j)
j.worktrees = lambda root: []          # exactly what an unreadable `git worktree list` gives
print(j.cut_merged_branches(sys.argv[2], True))
BLIND
)"
said "a tree list it cannot read cuts nothing — the protection fails CLOSED" \
     "every branch" "$out"
if git -C "$tmp/br" show-ref --quiet refs/heads/br-blind-subject; then
  ok "and the branch it would have cut is still there — the arm had a real subject"
else
  bad "the blinded run cut br-blind-subject — the guard did not hold"
fi
cd "$tmp/work" || exit 1

# ------------------------------------------------------------- THE LIVENESS FAIL-LIVE ARMS
# A false "dead" deletes a tree somebody is working in, and no real process raises EPERM or
# hides from `ps` on demand, so the arms that answer LIVE on anything unreadable are forced
# here. Each line prints one verdict; the controls prove the functions can still say "dead".
echo
echo "  -- unreadable liveness reads as live --"
out="$(python3 - "$JANITOR" <<'LIVE'
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("janitor", sys.argv[1])
j = importlib.util.module_from_spec(spec); sys.modules["janitor"] = j
spec.loader.exec_module(j)

def kill_raising(exc):
    def kill(pid, sig):
        raise exc
    return kill

real_kill = os.kill
os.kill = kill_raising(PermissionError(1, "EPERM"))
print("pid-eperm", j._pid_alive(4242))
os.kill = kill_raising(ProcessLookupError(3, "ESRCH"))
print("pid-gone", j._pid_alive(4242))
os.kill = real_kill

real_run = j.run
def ps_says(ok, out):
    j.run = lambda args, cwd=None: j.Ran(ok, out, "")
ps_says(False, "")
print("same-no-ps", j._same_process({"startedAt": 1_000_000}, 4242))
ps_says(True, "garbage")
print("same-bad-ps", j._same_process({"startedAt": 1_000_000}, 4242))
ps_says(True, "Mon Jan  1 00:00:00 2001")
print("same-no-startedat", j._same_process({}, 4242))
print("same-mismatch", j._same_process({"startedAt": 1_000_000}, 4242))
j.run = real_run
LIVE
)"
said "EPERM on a pid means the process exists — alive"      "pid-eperm True" "$out"
said "control: ESRCH means gone — not alive"                "pid-gone False" "$out"
said "no answer from ps reads as the same process"          "same-no-ps True" "$out"
said "an unparseable ps answer reads as the same process"   "same-bad-ps True" "$out"
said "a record with no startedAt reads as the same process" "same-no-startedat True" "$out"
said "control: a start time that disagrees is a new process" "same-mismatch False" "$out"

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

