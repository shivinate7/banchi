#!/usr/bin/env bash
# `make reap-selftest` — scripts/reap.py, proved by pointing it at processes it must not kill.
#
# WHY THIS EXISTS. The guard's whole claim is that it can tell a process this session started
# from one it did not, and refuse the second. That claim is only worth anything if the REFUSALS
# are exercised, and a refusal cannot be exercised against this repo: the process it exists to
# protect is the owner's live capture server on :8000 over their real 1,625-card store, and
# "run the guard at it and see" is the incident, not the test. So the fixture is a throwaway
# checkout, a throwaway sibling directory standing in for everywhere-else, and short-lived
# processes this script starts itself in their own process groups.
#
# WHY IT IS NOT IN THE GIT HOOK. D18: it writes a temp tree and it signals processes. It IS in
# `make check`, which is exactly janitor-selftest's and merge-selftest's standing.
#
# THE TWO INCIDENTS ARE CASES HERE, NOT PROSE. `pkill -f <name>` where a stranger also matches,
# and `for p in $(lsof -ti tcp:PORT); do kill $p; done` where a CLIENT holds the port — both are
# reproduced with real processes and a real socket rather than asserted about.
#
# WHAT IT CANNOT PROVE. Anything about the machine's real process table: every case is confined
# to the fixture. And the D53 case is proved through a `.serve/` pidfile it writes itself, so it
# proves the mechanism and not that the real supervisor writes one — `scripts/serve.py` owns
# that half and `make status` reads it.

set -uo pipefail          # NOT -e: every case must run and be scored

REAP="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/reap.py"
pass=0
fail=0

[ -f "$REAP" ] || { echo "no reap.py beside this script"; exit 1; }

tmp="$(mktemp -d "${TMPDIR:-/tmp}/pkmnscan-reap.XXXXXX")" || { echo "cannot make a temp dir"; exit 1; }
kids=""
strays=""                 # temp trees made after `tmp`, so cleanup reaches them too

# IT WAITS FOR THEM TO BE GONE, NOT MERELY SIGNALLED, and the `rm -rf` is half of how they go:
# every sleeper below watches its own script file and ends with it. A `kill` that returns is a
# signal DELIVERED, and the run that starts a second later inherits whatever has not finished
# dying — which is one of the two ways this suite's own processes reach a later run.
cleanup() {
  for k in $kids; do kill "$k" 2>/dev/null; done
  rm -rf "$tmp" $strays
  alive=""
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    alive=""
    for k in $kids; do kill -0 "$k" 2>/dev/null && alive="$alive $k"; done
    [ -z "$alive" ] && break
    sleep 0.2
  done
  for k in $alive; do kill -9 "$k" 2>/dev/null; done
  return 0
}
trap cleanup EXIT

say()  { printf '  %-6s %s\n' "$1" "$2"; }
ok()   { pass=$((pass + 1)); say "ok" "$1"; }
bad()  { fail=$((fail + 1)); say "FAIL" "$1"; }

# A process in ITS OWN process group, running a named script from a named directory, with its
# pipes on /dev/null. Every clause of that is load-bearing and janitor-selftest.sh's `spawn`
# carries the account: its own group so a killpg here can never reach this script, /dev/null so
# the command substitution is not held open by an inherited pipe, and a real script file so the
# path survives into `ps` (bash execs a lone simple command and leaves `ps` showing `sleep 300`).
spawn() {   # spawn <script-path> <cwd>
  python3 -c "
import subprocess, sys
with open('/dev/null', 'wb') as null:
    p = subprocess.Popen([sys.executable, sys.argv[1]], cwd=sys.argv[2],
                         stdin=null, stdout=null, stderr=null, start_new_session=True)
print(p.pid)
" "$1" "$2"
}

# A FIXTURE PROCESS THAT ENDS WHEN ITS OWN SCRIPT FILE IS DELETED, so `cleanup`'s `rm -rf`
# ENDS this run's processes rather than only asking them to. The leak it closes is structural
# rather than careless: `spawn` starts every child in its own session precisely so a `killpg`
# in here can never reach this script — which also means the SIGINT that stops a `make check`
# never reaches THEM either, and a run killed with -9 runs no trap at all. Under a shared name
# that survivor is the next run's stranger, which is the flake the tag above answers; this
# answers the other half, which is that it should not survive.
#
# The deadline behind it is the backstop for the -9 case, where nothing is deleted. It stays
# generous because an arm whose own subject died early fails for the wrong reason — the TAG,
# not the deadline, is what makes a survivor harmless.
sleeper() {   # sleeper <script-path>
  cat > "$1" <<'PY'
import os, sys, time
end = time.time() + 300
while time.time() < end and os.path.exists(sys.argv[0]):
    time.sleep(0.2)
PY
}

# The hook, asked about one command. Prints its stderr so a failing case can be read.
judge() {   # judge <cwd> <command> -> exit code, output in $out
  out="$(cd "$1" && printf '%s' "$2" \
        | python3 -c 'import json,sys; print(json.dumps({"tool_input":{"command":sys.stdin.read()}}))' \
        | (cd "$1" && python3 "$REAP" --hook) 2>&1)"
  return $?
}

# ------------------------------------------------------------------------------- the fixture
# EVERY SCRIPT THIS FIXTURE STARTS CARRIES A PER-RUN TAG, BECAUSE `pgrep -f` IS MACHINE-WIDE.
# The guard resolves `pkill -f mine.py` by running that pgrep ITSELF, across the whole machine —
# which is the whole point of it, and is correct. So a second copy of this fixture running
# anywhere else puts a live `mine.py` in a DIFFERENT checkout: a concurrent `make check` from
# another of this clone's worktrees, or a `time.sleep(300)` left behind by a run interrupted
# before its EXIT trap fired. The guard judges that one "outside this checkout" and refuses the
# command — the guard being right and the fixture being wrong — and the arm that fails is
# `KILLING ITS OWN PROCESS IS ALLOWED`, the one constraint this file must never break. Four
# such failures on 2026-09-11/12, against a byte-identical reap.py.
#
# THIS IS D122'S SHAPE ONE REGISTER DOWN (D157): a per-run fixture over a
# machine-wide resource. The
# suite lock answers it there by refusing to run twice at once; here the resource is the
# process table, which cannot be locked, so the fixture is made unable to collide instead.
#
# The tag is the temp directory's own mktemp suffix — unique by construction at the moment the
# directory was made — and this shell's pid. Either alone can in principle be reused by a
# leftover whose directory was swept; both together cannot.
#
# IT IS A FUNCTION AND NOT SIX STRING LITERALS, so `-- a second copy of this fixture --` below
# can build a rival's name BY THE SAME RULE rather than by hand. That is what makes the arm
# mutation-sensitive: spell a fixed name here and the rival gets the same fixed name, the guard
# correctly calls it a stranger, and the arm goes red. An arm whose decoy is hand-named would
# keep passing over exactly the bug this file is fixing.
fixture_script() {   # fixture_script <base> <temp-dir> -> a name no other run can produce
  printf '%s-%s-%s.py' "$1" "${2##*.}" "$$"
}

mine_script="$(fixture_script mine "$tmp")"
stranger_script="$(fixture_script stranger "$tmp")"
listen_script="$(fixture_script listen "$tmp")"
client_script="$(fixture_script client "$tmp")"
inner_script="$(fixture_script inner "$tmp")"
probe_script="$(fixture_script probe "$tmp")"

mkdir -p "$tmp/checkout" "$tmp/elsewhere"
git -C "$tmp/checkout" init -q .
sleeper "$tmp/checkout/$mine_script"
sleeper "$tmp/elsewhere/$stranger_script"

mine="$(spawn "$tmp/checkout/$mine_script" "$tmp/checkout")"
stranger="$(spawn "$tmp/elsewhere/$stranger_script" "$tmp/elsewhere")"
kids="$mine $stranger"
sleep 1

# ---------------------------------------------------------------- the hook: what it lets past
echo
echo "  -- commands the guard must not touch --"

judge "$tmp/checkout" "ls -la"
[ $? -eq 0 ] && ok "an ordinary command is not read at all" || bad "a non-kill command was blocked"

judge "$tmp/checkout" "echo 'remember: pkill -f is machine-wide'"
[ $? -eq 0 ] && ok "the word in a string is not a kill" || bad "prose mentioning pkill was blocked"

judge "$tmp/checkout" "cat > note.sh <<'EOF'
pkill -f $stranger_script
EOF"
[ $? -eq 0 ] && ok "a heredoc BODY is a document, not a command" || bad "writing a script that mentions pkill was blocked"

judge "$tmp/checkout" "kill -0 $stranger"
[ $? -eq 0 ] && ok "kill -0 is a liveness probe and sends no signal" || bad "kill -0 was blocked"

judge "$tmp/checkout" "sleep 5 & kill %1"
[ $? -eq 0 ] && ok "a job spec names this shell's own job" || bad "kill %1 was blocked"

judge "$tmp/checkout" "pkill -f $mine_script"
[ $? -eq 0 ] && ok "KILLING ITS OWN PROCESS IS ALLOWED" || {
  bad "a session was refused its own process — the constraint this must not break"
  printf '%s\n' "$out" | sed 's/^/         /'
}

# ------------------------------------------------------------------- the hook: incident one
echo
echo "  -- incident 1: pkill -f also matched a stranger --"

judge "$tmp/checkout" "pkill -f $stranger_script"
status=$?
case "$status:$out" in
  2:*outside\ this\ checkout*) ok "REFUSED, naming the pid and where it lives" ;;
  2:*) bad "refused, but not for being outside the checkout"
       printf '%s\n' "$out" | sed 's/^/         /' ;;
  *) bad "a stranger's process was cleared for killing" ;;
esac

kill -0 "$stranger" 2>/dev/null \
  && ok "the stranger is still running" || bad "the stranger was killed by the guard itself"

case "$out" in
  *PKMNSCAN_KILL=off*) ok "the refusal prints its escape hatch" ;;
  *) bad "a refusal with no way past it is one that gets disabled wholesale" ;;
esac
case "$out" in
  *"make reap"*) ok "the refusal names the tool that does the same job safely" ;;
  *) bad "the refusal does not say what to do instead" ;;
esac

# ------------------------------------------------- the flake: a second copy of this fixture
echo
echo "  -- a second copy of this fixture, running at the same time --"

# THE REGRESSION ARM FOR THE PER-RUN TAG, AND IT REPRODUCES THE FLAKE RATHER THAN ASSERTING
# ABOUT IT. A rival fixture is built the way a concurrent `make check` in another worktree
# builds one — its own `mktemp -d`, its own tag, its own `mine` — and left running while this
# run asks the guard to kill ITS OWN `mine`. With the tag, the two names cannot collide and the
# kill is allowed. Without it, both runs call their process `mine.py`, `pgrep -f mine.py`
# returns the rival as well, and the guard refuses — correctly, which is the whole problem.
# This failed four times on 2026-09-11/12 against a byte-identical reap.py, and nothing in this
# file could see it: the failing arm blamed the guard.
#
# The rival's pid is NOT added to `kids` in the usual way and then forgotten — it is, but its
# TREE goes on `strays`, because it lives outside `$tmp` and the trap would otherwise leave a
# `time.sleep(300)` behind. A leftover of exactly that kind is one of the two ways this flake
# reached a session in the first place.
rival_tmp="$(mktemp -d "${TMPDIR:-/tmp}/pkmnscan-reap.XXXXXX")" || rival_tmp=""
if [ -z "$rival_tmp" ]; then
  bad "cannot make a second temp dir — the concurrency arm cannot be posed"
else
strays="$strays $rival_tmp"
rival_script="$(fixture_script mine "$rival_tmp")"
mkdir -p "$rival_tmp/checkout"
git -C "$rival_tmp/checkout" init -q .
sleeper "$rival_tmp/checkout/$rival_script"
rival="$(spawn "$rival_tmp/checkout/$rival_script" "$rival_tmp/checkout")"
kids="$kids $rival"
sleep 1

judge "$tmp/checkout" "pkill -f $mine_script"
[ $? -eq 0 ] && ok "A CONCURRENT COPY OF THIS FIXTURE CANNOT REFUSE THIS RUN ITS OWN PROCESS" || {
  bad "a second run of this fixture made the guard refuse this run's own process — THE FLAKE"
  printf '%s\n' "$out" | sed 's/^/         /'
}

# And the rival is a real, live, resolvable stranger — so the case above did not pass because
# `pgrep` found nothing. Together the two say the NAMES are unique, not that the guard stopped
# looking, which is the difference between a fixture that collides and a guard that is broken.
judge "$tmp/checkout" "pkill -f $rival_script"
status=$?
case "$status:$out" in
  2:*outside\ this\ checkout*) ok "and the rival's own process is still refused, by name" ;;
  2:*) bad "the rival was refused, but not for living in another checkout"
       printf '%s\n' "$out" | sed 's/^/         /' ;;
  *) bad "the rival is not resolvable, so the case above proved nothing" ;;
esac
fi

# ------------------------------------------------------------------- the hook: incident two
echo
echo "  -- incident 2: lsof -ti returns clients as well as listeners --"

# `lsof` IS DECLARED IN scripts/checks.py:NEEDS AND IS NOT ASSUMED HERE. This suite runs on
# `ubuntu-latest` as well as on the owner's Mac, and a runner image without it would fail every
# case below for a reason that has nothing to do with the guard. The skip is LOUD and counts as
# neither a pass nor a failure — the vale target's bargain, taken for the same reason. Note that
# reap.py itself degrades correctly without lsof rather than opening a hole: with no working
# directory to read, a process carrying no absolute path in its argv is UNKNOWN and refused.
if ! command -v lsof >/dev/null 2>&1; then
  say "SKIP" "lsof is absent — the port cases cannot be posed on this machine at all"
  port=""
else
# AND THE PORT IS A RESERVATION, NOT A READING, FOR THE TAG'S REASON ONE CLAUSE OVER. Probing
# whether anything is listening on a candidate and then binding it is a TOCTOU: two concurrent
# runs read the same port free, one bind wins, and the LOSER's client connects to the WINNER's
# listener. That puts three pids on one port, fails the reproduction case, and makes every case
# under it vacuous by this file's own admission. Port 0 cannot be handed to two processes, so
# the listener is asked what it was given rather than told what to take.
cat > "$tmp/checkout/$listen_script" <<PY
import os, socket, time
s = socket.socket(); s.bind(("127.0.0.1", 0)); s.listen(5); s.settimeout(1.0)
with open("$tmp/port.part", "w") as fh: fh.write(str(s.getsockname()[1]))
os.rename("$tmp/port.part", "$tmp/port")   # atomic: a reader never sees half a number
held = []
end = time.time() + 90
while time.time() < end:
    try: held.append(s.accept()[0])
    except Exception: pass
PY
listener="$(spawn "$tmp/checkout/$listen_script" "$tmp/checkout")"
kids="$kids $listener"
port=""
tries=0
while [ ! -s "$tmp/port" ] && [ "$tries" -lt 50 ]; do sleep 0.2; tries=$((tries + 1)); done
[ -s "$tmp/port" ] && port="$(cat "$tmp/port")"

if [ -z "$port" ]; then
  bad "the listener never reported a port — every port case below is now vacuous"
else
cat > "$tmp/elsewhere/$client_script" <<PY
import socket, time
c = socket.socket(); c.connect(("127.0.0.1", $port)); time.sleep(90)
PY
client="$(spawn "$tmp/elsewhere/$client_script" "$tmp/elsewhere")"; sleep 1
kids="$kids $client"

holders="$(lsof -ti tcp:$port 2>/dev/null | tr '\n' ' ')"
# `wc -w` pads its answer with leading spaces on macOS, so this is arithmetic and not a
# `case` on its output — which matched nothing and failed a case that was in fact passing.
held=$(printf '%s' "$holders" | wc -w)
if [ "$held" -eq 2 ]; then
  ok "the fixture reproduces it: 2 processes hold port $port"
else
  bad "the fixture did not reproduce a client on the port (holders: $holders) — every case below is now vacuous"
fi

judge "$tmp/checkout" "for p in \$(lsof -ti tcp:$port); do kill \$p; done"
status=$?
case "$status:$out" in
  2:*pid\ $client*) ok "REFUSED, and it is the CLIENT the refusal names" ;;
  2:*) bad "refused, but not on the client — the pid that made this an incident"
       printf '%s\n' "$out" | sed 's/^/         /' ;;
  *) bad "the loop form walked straight past the guard" ;;
esac
fi
fi

# ------------------------------------------------------------- the hook: nothing to read
echo
echo "  -- a target the guard cannot place --"

judge "$tmp/checkout" 'kill $somepid'
status=$?
case "$status:$out" in
  2:*cannot\ tell\ what\ pid*) ok "an unreadable target is refused, not guessed at" ;;
  *) bad "a kill whose target cannot be read was allowed" ;;
esac

# ------------------------------------------------------------------------ the hook: D53
echo
echo "  -- D53: the main checkout's server, even from the main checkout --"

mkdir -p "$tmp/checkout/.serve"
printf '{"pid": %s, "argv": [], "started_at": 0}\n' "$mine" > "$tmp/checkout/.serve/capture.pid"
out="$(cd "$tmp/checkout" && python3 "$REAP" --explain "pid:$mine" 2>&1)"
case "$out" in
  *MAIN*) ok "a pid in the main checkout's own pidfile is refused THOUGH IT IS UNDER THE ROOT" ;;
  *) bad "the supervisor's own child was cleared for killing from inside the main checkout"
     printf '%s\n' "$out" | sed 's/^/         /' ;;
esac

judge "$tmp/checkout" "pkill -f $mine_script"
status=$?
case "$status:$out" in
  2:*make\ down\ ARGS=--confirm*) ok "and the refusal names the drain, not a harder kill" ;;
  2:*) bad 'refused without naming `make down`, which is the sanctioned way to stop it' ;;
  *) bad "the pidfile'd process was cleared once reached through pkill" ;;
esac
rm -f "$tmp/checkout/.serve/capture.pid"

# ------------------------------------------------------- a directory that is not a workspace
echo
echo "  -- a root that would contain everything --"

# THIS IS THE HOLE THE USER-LEVEL INSTALL EXPOSED, and it could not have been found from inside
# a clone: `git rev-parse --show-toplevel` always answers there, so the fallback never ran. The
# moment `make janitor-install` put the hook in the user's own `~/.claude/settings.json` it began
# firing in directories that are not repositories, and the fallback adopted the HOME DIRECTORY as
# "this checkout" — under which the owner's live capture server sits. Measured 2026-09-10: the
# exact command of incident 1, judged from `$HOME`, resolved that server to OURS.
#
# EVERY CASE HERE NEEDS A SUBJECT INSIDE THE DIRECTORY IT IS TESTING, and the first build of this
# block had none: it judged `$stranger`, which lives under the fixture's own `mktemp -d` — and on
# a Mac that is under `$TMPDIR` in `/var/folders`, not under `$HOME` and not under `/tmp`. So a
# broad root would not have claimed it either, three cases passed for the wrong reason, and three
# mutation arms survived. The processes below sit inside the directories being tested.
#
# AND `$HOME` IS FAKED RATHER THAN USED. `Path.home()` reads the environment, so the home cases
# run against a home directory inside the fixture — which is the only way to put a process under
# one without starting a process under the owner's real home directory.

mkdir -p "$tmp/home/deep"
sleeper "$tmp/home/deep/$inner_script"
inner="$(spawn "$tmp/home/deep/$inner_script" "$tmp/home/deep")"
kids="$kids $inner"
sleep 1

out="$(cd "$tmp/home/deep" && HOME="$tmp/home/deep" python3 "$REAP" --explain "pid:$inner" 2>&1)"
case "$out" in
  *OURS*) bad "the home directory was adopted as a checkout — everything under it is now ours" ;;
  *) ok "A HOME DIRECTORY IS NOT A WORKSPACE, though a process sits right inside it" ;;
esac

out="$(cd "$tmp/home" && HOME="$tmp/home/deep" python3 "$REAP" --explain "pid:$inner" 2>&1)"
case "$out" in
  *OURS*) bad "an ancestor of \$HOME was adopted, and it is on no fixed list" ;;
  *) ok "AN ANCESTOR OF \$HOME is refused wherever the home directory happens to sit" ;;
esac

# A broad directory that is on the list and is no ancestor of any home directory. `/private/tmp`
# reaches it whatever `$TMPDIR` is set to, which is why this probe is made under `/tmp` by name
# rather than beside the rest of the fixture.
probe="$(mktemp -d /tmp/pkmnscan-reap-probe.XXXXXX)"
sleeper "$probe/$probe_script"
probe_pid="$(spawn "$probe/$probe_script" "$probe")"
kids="$kids $probe_pid"
sleep 1
out="$(cd /tmp && python3 "$REAP" --explain "pid:$probe_pid" 2>&1)"
case "$out" in
  *OURS*) bad "/tmp was adopted as a checkout, claiming everything anyone has left in it" ;;
  *) ok "NOR IS /tmp, which is on the list and is no ancestor of a home directory" ;;
esac
rm -rf "$probe"

# `/` needs no special subject: everything on the machine is under it, `$stranger` included.
out="$(cd / && python3 "$REAP" --explain "pid:$stranger" 2>&1)"
case "$out" in
  *OURS*) bad "/ was adopted as a checkout, which claims the whole machine at once" ;;
  *) ok "and neither is /" ;;
esac

# The hook itself over the same ground. `judge` cannot be used here: it does not fake `$HOME`,
# and a home directory that is not the process's own home is an ORDINARY directory — which is
# the correct answer to a different question and would have passed this case for free.
out="$(cd "$tmp/home/deep" && printf '{"tool_input":{"command":"pkill -f %s"}}' "$inner_script" \
       | HOME="$tmp/home/deep" python3 "$REAP" --hook 2>&1)"
status=$?
[ $status -eq 2 ] && ok "a kill run from a home directory is refused, not guessed at" \
                  || bad "a kill run from a home directory was cleared"
case "$out" in
  *not\ a\ workspace*) ok "and the refusal says WHY rather than naming an empty checkout" ;;
  *) bad "the refusal quoted an empty root, which reads as a bug in the guard"
     printf '%s\n' "$out" | sed 's/^/         /' ;;
esac

# The fallback still has to WORK where the directory is an ordinary one, or a session outside a
# repository can never clean up after itself — which is the constraint this whole guard is under.
out="$(cd "$tmp/elsewhere" && python3 "$REAP" --explain "pid:$stranger" 2>&1)"
case "$out" in
  *OURS*) ok "AN ORDINARY NON-REPO DIRECTORY IS STILL A WORKSPACE — cleanup survives" ;;
  *) bad "a plain directory stopped being a root, so a session outside a repo cannot clean up"
     printf '%s\n' "$out" | sed 's/^/         /' ;;
esac

# --------------------------------------------------------------------- the escape hatch
echo
echo "  -- the escape hatch --"

judge "$tmp/checkout" "PKMNSCAN_KILL=off pkill -f $stranger_script"
[ $? -eq 0 ] && ok "the hatch is honoured in the command itself" || bad "the printed hatch does not work"
out="$(cd "$tmp/checkout" && printf '{"tool_input":{"command":"pkill -f %s"}}' "$stranger_script" \
       | PKMNSCAN_KILL=off python3 "$REAP" --hook 2>&1)"
[ $? -eq 0 ] && ok "and in the environment" || bad "PKMNSCAN_KILL=off in the environment did nothing"

# -------------------------------------------------------------------------- the reaper
echo
echo "  -- the reaper: it kills ours and reports theirs --"

if [ -n "$port" ]; then
out="$(cd "$tmp/checkout" && python3 "$REAP" "port:$port" 2>&1)"
case "$out" in
  *would\ stop*pid\ $listener*) ok "the preview names ours and presses nothing" ;;
  *) bad "the preview did not offer to stop the listener"
     printf '%s\n' "$out" | sed 's/^/         /' ;;
esac
kill -0 "$listener" 2>/dev/null && ok "and a preview really did press nothing" || bad "the preview killed something"

out="$(cd "$tmp/checkout" && python3 "$REAP" "port:$port" --confirm 2>&1)"
case "$out" in
  *REFUSED*pid\ $client*) ok "the refusal is PRINTED rather than swallowed" ;;
  *) bad "the reaper silently skipped the client — which teaches nothing"
     printf '%s\n' "$out" | sed 's/^/         /' ;;
esac
sleep 1
kill -0 "$listener" 2>/dev/null && bad "our own listener survived --confirm; cleanup is now impossible" || ok "OURS WAS STOPPED — a session can still clean up after itself"
kill -0 "$client" 2>/dev/null && ok "THE STRANGER SURVIVED --confirm" || bad "the reaper killed a process outside the checkout"
fi

out="$(cd "$tmp/checkout" && python3 "$REAP" 2>&1)"
case "$out" in
  *pid\ $mine*) ok "a bare run finds what is running under this checkout" ;;
  *) bad "a bare run did not find the process running under the checkout"
     printf '%s\n' "$out" | sed 's/^/         /' ;;
esac
case "$out" in
  *pid\ $stranger*) bad "a bare run reached outside the checkout" ;;
  *) ok "and reaches nothing outside it" ;;
esac

echo
if [ "$fail" -eq 0 ]; then
  echo "reap self-test: $pass passed"
  exit 0
fi
echo "reap self-test: $fail FAILED, $pass passed"
exit 1
