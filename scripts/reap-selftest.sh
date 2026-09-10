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
cleanup() {
  for k in $kids; do kill "$k" 2>/dev/null; done
  rm -rf "$tmp"
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

# The hook, asked about one command. Prints its stderr so a failing case can be read.
judge() {   # judge <cwd> <command> -> exit code, output in $out
  out="$(cd "$1" && printf '%s' "$2" \
        | python3 -c 'import json,sys; print(json.dumps({"tool_input":{"command":sys.stdin.read()}}))' \
        | (cd "$1" && python3 "$REAP" --hook) 2>&1)"
  return $?
}

# ------------------------------------------------------------------------------- the fixture
mkdir -p "$tmp/checkout" "$tmp/elsewhere"
git -C "$tmp/checkout" init -q .
printf 'import time; time.sleep(300)\n' > "$tmp/checkout/mine.py"
printf 'import time; time.sleep(300)\n' > "$tmp/elsewhere/stranger.py"

mine="$(spawn "$tmp/checkout/mine.py" "$tmp/checkout")"
stranger="$(spawn "$tmp/elsewhere/stranger.py" "$tmp/elsewhere")"
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
pkill -f stranger.py
EOF"
[ $? -eq 0 ] && ok "a heredoc BODY is a document, not a command" || bad "writing a script that mentions pkill was blocked"

judge "$tmp/checkout" "kill -0 $stranger"
[ $? -eq 0 ] && ok "kill -0 is a liveness probe and sends no signal" || bad "kill -0 was blocked"

judge "$tmp/checkout" "sleep 5 & kill %1"
[ $? -eq 0 ] && ok "a job spec names this shell's own job" || bad "kill %1 was blocked"

judge "$tmp/checkout" "pkill -f mine.py"
[ $? -eq 0 ] && ok "KILLING ITS OWN PROCESS IS ALLOWED" || {
  bad "a session was refused its own process — the constraint this must not break"
  printf '%s\n' "$out" | sed 's/^/         /'
}

# ------------------------------------------------------------------- the hook: incident one
echo
echo "  -- incident 1: pkill -f also matched a stranger --"

judge "$tmp/checkout" "pkill -f stranger.py"
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
port=0
for candidate in $(python3 -c 'print(" ".join(str(p) for p in range(53900, 53960)))'); do
  if ! (exec 3<>/dev/tcp/127.0.0.1/"$candidate") 2>/dev/null; then port="$candidate"; break; fi
done

cat > "$tmp/checkout/listen.py" <<PY
import socket, time
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("127.0.0.1", $port)); s.listen(5); s.settimeout(1.0)
held = []
end = time.time() + 90
while time.time() < end:
    try: held.append(s.accept()[0])
    except Exception: pass
PY
cat > "$tmp/elsewhere/client.py" <<PY
import socket, time
c = socket.socket(); c.connect(("127.0.0.1", $port)); time.sleep(90)
PY

listener="$(spawn "$tmp/checkout/listen.py" "$tmp/checkout")"; sleep 1
client="$(spawn "$tmp/elsewhere/client.py" "$tmp/elsewhere")"; sleep 1
kids="$kids $listener $client"

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

judge "$tmp/checkout" "pkill -f mine.py"
status=$?
case "$status:$out" in
  2:*make\ down\ ARGS=--confirm*) ok "and the refusal names the drain, not a harder kill" ;;
  2:*) bad "refused without naming `make down`, which is the sanctioned way to stop it" ;;
  *) bad "the pidfile'd process was cleared once reached through pkill" ;;
esac
rm -f "$tmp/checkout/.serve/capture.pid"

# --------------------------------------------------------------------- the escape hatch
echo
echo "  -- the escape hatch --"

judge "$tmp/checkout" "PKMNSCAN_KILL=off pkill -f stranger.py"
[ $? -eq 0 ] && ok "the hatch is honoured in the command itself" || bad "the printed hatch does not work"
out="$(cd "$tmp/checkout" && printf '{"tool_input":{"command":"pkill -f stranger.py"}}' \
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
