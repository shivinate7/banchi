#!/usr/bin/env bash
# `make janitor-selftest` — scripts/janitor.py (--teardown), proved against a throwaway clone.
# Protects: The janitor tears down only a leaving tree, and reads every unreadable liveness answer as live, proved with real processes.
#
# WHY THIS EXISTS. janitor.py signals processes, so the cases worth proving cannot run against
# this repo. It gets a temp clone, a fake liveness oracle and real processes in their own
# process groups.
#
# THE SWEEP PROPER IS NOT HERE. It is claude-settings' `janitor/sweep.py`, proved by its own
# `test_sweep.py`. What this file keeps is one tree's teardown (`--teardown`) and the liveness
# reads it stands on.
# WHY IT IS NOT IN THE GIT HOOK. D18: it writes. It IS in `make check`, which is exactly
# `revert-selftest`'s standing.
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


# the fake liveness oracle. The process points at a file that exists, so nothing here is an
# orphan by accident.
touch "$tmp/marker.py"
busy_pid="$(plain_spawn "$tmp/marker.py")"; kids="$kids $busy_pid"
python3 -c 'import time; time.sleep(0.5)'
alive "$busy_pid" && ok "the fixture session's pid is alive" || bad "the fixture is wrong — session pid is dead"

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


echo
if [ "$fail" -eq 0 ]; then
  echo "janitor self-test: $pass passed"
  exit 0
fi
echo "janitor self-test: $fail FAILED, $pass passed"
exit 1

