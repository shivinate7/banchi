#!/usr/bin/env bash
# `make worktree-create-selftest` — scripts/worktree-create.sh (the WorktreeCreate hook) under
# parallel creation, proved against a throwaway repo with a bare origin.
# Protects: parallel Agents each get their worktree. Four creations racing one .git/config
# must all succeed, and none may leave a config lock behind.
# Governs: D18
#
# WHY PARALLEL. The race is a write to the shared .git/config. A branch cut from a
# remote-tracking ref (origin/main) gets upstream tracking by default, and git takes
# .git/config.lock for that write with no retry. Four creations at once make the old hook fail
# with "could not lock config file". One creation never does, so one creation proves nothing.
#
# WHY A THROWAWAY REPO. The hook makes real worktrees and a real fetch. It runs in a temp
# repo whose origin is a local bare repo, so no network is touched and this checkout is not.
# Its core.hooksPath points at an EMPTY directory, so git's post-checkout provisioning (npm
# ci, the harness cache) never runs in the temp tree. Any GIT_* variable a git hook exported
# is unset first, or git would act on this checkout.
#
# THE HOOK UNDER TEST. $WORKTREE_CREATE_SCRIPT names the copy to run, so the red proof can point
# it at the old script. Default: scripts/worktree-create.sh beside this file.
#
# ARMS. A deterministic arm holds .git/config.lock by hand and makes ONE tree, so the old hook
# fails every time, with no race needed. The lock arms cover the add lock at
# <git common dir>/banchi-worktree-add.lock: a free lock, a lock held by a live pid (the add must
# wait and say so), and a lock whose pid is gone (the add must take it over). Then: two waiters on
# one stale lock, a pid this user cannot signal (EPERM, skipped as root), the wait cap, and INT or
# TERM to a holder mid-add. The parallel arm then races ROUNDS*PARALLEL creations, which is the
# realistic shape. Trees made: the parallel count, plus lk, plus the lock-arm trees, plus the
# two-waiter and signal trees, plus the main checkout. Knobs: ROUNDS (default 5) and PARALLEL
# (default 4). Raise them only if a red run is needed; the defaults are the stated contract.
#
# TEMP FILES follow the run-folder standard (decision test-temp-standard). A sweep case proves
# that the first request of a run removes an old sibling run folder and keeps a new one.
#
# Output is kept, never silenced: each creation writes its stdout and stderr to a file, and a
# FAIL line prints the stderr so the reason shows.
#
# CONTRACT with the hook. The builder honours each line; an arm fails by name when one breaks.
#   - The add lock is mkdir at <git common dir>/banchi-worktree-add.lock, its holder's pid in <lock>/pid.
#   - A waiter prints one line on stderr containing `waiting for the worktree lock`, then polls.
#   - Knob BANCHI_WORKTREE_LOCK_WAIT=<seconds> is the wait cap (default 120). At the cap the add
#     exits non-zero and its stderr names the lock path.
#   - Seam, judgment: the hook reads the holder's pid with `cat "$lock/pid"` (the two-waiter arm
#     pauses that read). Seam, add: the hook runs `git worktree add` as a plain command under the lock.
#   - INT or TERM to a holder releases the lock on exit (the hook's traps).
#   - A kill -0 error other than "No such process" means the pid is live (EPERM).
# The seams are test-side only: PATH wrappers for git and cat, switched on by marker files. The hook
# carries no test code.

set -uo pipefail          # NOT -e: every case must run and be scored

unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${WORKTREE_CREATE_SCRIPT:-$HERE/worktree-create.sh}"
ROUNDS="${ROUNDS:-5}"
PARALLEL="${PARALLEL:-4}"
[ -f "$SCRIPT" ] || { echo "no worktree-create.sh at $SCRIPT"; exit 1; }

pass=0
fail=0
say() { printf '  %-6s %s\n' "$1" "$2"; }
ok()  { pass=$((pass + 1)); say "ok" "$1"; }
bad() { fail=$((fail + 1)); say "FAIL" "$1"; }

# One temp root, one run folder per run named <pid>-<hex32>. Teardown removes the run folder.
TEMP_ROOT="${TMPDIR:-/tmp}/banchi-test-temp"
mkdir -p "$TEMP_ROOT" || { echo "cannot make the temp root $TEMP_ROOT"; exit 1; }
hex32() { python3 -c 'import uuid; print(uuid.uuid4().hex)'; }
RUN_FOLDER="$TEMP_ROOT/$$-$(hex32)"
OLD_SIB="$TEMP_ROOT/1-$(hex32)"
NEW_SIB="$TEMP_ROOT/1-$(hex32)"
bg=""       # the held-lock creation, killed on any exit before it is reaped
BG_PIDS=""  # creations start_creation makes, killed on any exit before they are reaped
cleanup() {
  local p
  for p in $BG_PIDS "$bg"; do [ -n "$p" ] && kill -9 "$p" 2>/dev/null; done
  rm -rf "$RUN_FOLDER" "$OLD_SIB" "$NEW_SIB"
}
trap cleanup EXIT

# Sweep fixtures: an old sibling dated 2020, so over a day old on any clock, and a new one.
mkdir "$OLD_SIB" && touch -t 202001010000 "$OLD_SIB"
mkdir "$NEW_SIB"
[ -d "$OLD_SIB" ] && [ -d "$NEW_SIB" ] || { echo "cannot make the sweep fixtures"; exit 1; }

# The first request of the run: remove sibling run folders over a day old. This run's folder is
# not made yet, and a newer sibling stays.
find "$TEMP_ROOT" -mindepth 1 -maxdepth 1 -type d -name '[0-9]*-*' -mmin +1440 -exec rm -rf {} + 2>/dev/null
mkdir "$RUN_FOLDER" || { echo "cannot make the run folder $RUN_FOLDER"; exit 1; }
tmp="$RUN_FOLDER"

# Sweep proof. Both fixtures were made above, so each result is about the sweep alone.
if [ -e "$OLD_SIB" ]; then bad "sweep: an old sibling run folder was not removed"; else ok "sweep: an old sibling run folder is removed"; fi
if [ -d "$NEW_SIB" ]; then ok "sweep: a new sibling run folder stays"; else bad "sweep: a new sibling run folder was removed"; fi

# A bare origin with one commit on main, and a clone that has origin/main as a remote-tracking
# ref. That ref is what makes git write upstream tracking, so the race is reachable.
git -c init.defaultBranch=main init --bare -q "$tmp/origin.git"
git -c init.defaultBranch=main init -q "$tmp/main"
MAIN="$(cd "$tmp/main" && pwd -P)"
git -C "$MAIN" config user.email selftest@example.invalid
git -C "$MAIN" config user.name selftest
echo seed > "$MAIN/seed.txt"
git -C "$MAIN" add seed.txt
git -C "$MAIN" commit -q -m seed
git -C "$MAIN" remote add origin "$tmp/origin.git"
git -C "$MAIN" push -q origin main
# No hook from this repo or the machine runs in the temp tree: an empty hooksPath wins over
# any global or core.hooksPath setting.
mkdir -p "$tmp/no-hooks"
git -C "$MAIN" config core.hooksPath "$tmp/no-hooks"

# One creation, run from the temp main. Args: name. Output lands in $RUN_OUT, one file set per
# name, and nothing is discarded.
cat > "$tmp/run_one.sh" <<'RUN'
#!/usr/bin/env bash
name="$1"
printf '{"name": "%s"}' "$name" \
  | (cd "$RUN_MAIN" && bash "$RUN_SCRIPT") > "$RUN_OUT/$name.out" 2> "$RUN_OUT/$name.err"
echo $? > "$RUN_OUT/$name.rc"
RUN
chmod +x "$tmp/run_one.sh"

RUN_OUT="$tmp/out"
mkdir -p "$RUN_OUT"
export RUN_MAIN="$MAIN" RUN_SCRIPT="$SCRIPT" RUN_OUT

# SEAMS, test side only. PATH wrappers for git and cat, live only in creations that start_creation
# makes. Marker files in $CTL switch them on: hold-add pauses an add inside the lock until
# go-add-<pid> exists; hold-judge pauses the first read of the lock's pid file until go-judge exists.
# With SELFTEST_ADD_LOG set, each add logs `enter <pid>` and `exit <pid>` there.
CTL="$tmp/ctl"
WRAP="$tmp/wrap"
mkdir -p "$CTL" "$WRAP"
export SELFTEST_CTL="$CTL" SELFTEST_REAL_GIT="$(command -v git)" SELFTEST_REAL_CAT="$(command -v cat)"
cat > "$WRAP/git" <<'WRAPGIT'
#!/usr/bin/env bash
case " $* " in
  *" worktree add "*)
    if [ -n "${SELFTEST_ADD_LOG:-}" ]; then echo "enter $PPID" >> "$SELFTEST_ADD_LOG"; fi
    if [ -e "$SELFTEST_CTL/hold-add" ]; then
      for _ in $(seq 1 300); do [ -e "$SELFTEST_CTL/go-add-$PPID" ] && break; sleep 0.1; done
    fi
    "$SELFTEST_REAL_GIT" "$@"
    rc=$?
    if [ -n "${SELFTEST_ADD_LOG:-}" ]; then echo "exit $PPID" >> "$SELFTEST_ADD_LOG"; fi
    exit "$rc" ;;
esac
exec "$SELFTEST_REAL_GIT" "$@"
WRAPGIT
cat > "$WRAP/cat" <<'WRAPCAT'
#!/usr/bin/env bash
if [ -e "$SELFTEST_CTL/hold-judge" ]; then
  for a in "$@"; do
    if [ "$a" = "${SELFTEST_PIDFILE:-}" ] && mv "$SELFTEST_CTL/hold-judge" "$SELFTEST_CTL/judge-taken" 2>/dev/null; then
      "$SELFTEST_REAL_CAT" "$@"
      echo "$$" > "$SELFTEST_CTL/judged"
      for _ in $(seq 1 300); do [ -e "$SELFTEST_CTL/go-judge" ] && break; sleep 0.1; done
      exit 0
    fi
  done
fi
exec "$SELFTEST_REAL_CAT" "$@"
WRAPCAT
chmod +x "$WRAP/git" "$WRAP/cat"

# Starts a creation of <name> in the background, from the temp main, through the seams. `exec` makes
# the hook's own pid the job's pid, so $! names the hook in an add log. Output lands in
# $RUN_OUT/<name>.out and .err. The caller reaps it with reap.
start_creation() {
  printf '{"name": "%s"}' "$1" > "$tmp/in-$1.json"
  ( cd "$MAIN" && exec env PATH="$WRAP:$PATH" bash "$SCRIPT" < "$tmp/in-$1.json" > "$RUN_OUT/$1.out" 2> "$RUN_OUT/$1.err" ) &
  BG_PIDS="$BG_PIDS $!"
}
# The same, with INT left at its default. A background job of a non-interactive shell inherits INT
# ignored, and a trap cannot catch an ignored signal, so python resets INT and then execs the hook.
start_creation_signalable() {
  printf '{"name": "%s"}' "$1" > "$tmp/in-$1.json"
  ( cd "$MAIN" && exec env PATH="$WRAP:$PATH" python3 -c 'import os, signal, sys; signal.signal(signal.SIGINT, signal.SIG_DFL); os.execvp("bash", ["bash", sys.argv[1]])' "$SCRIPT" < "$tmp/in-$1.json" > "$RUN_OUT/$1.out" 2> "$RUN_OUT/$1.err" ) &
  BG_PIDS="$BG_PIDS $!"
}

# Waits, bounded at 300 polls 0.1 s apart, for pid to leave the process table, then reaps it. Sets
# REAPED (yes or no) and REAP_RC (its exit status, or none when it had to be killed).
reap() {
  local pid="$1" i
  REAPED=no
  for i in $(seq 1 300); do
    if [ -z "$(ps -o stat= -p "$pid" 2>/dev/null | grep -v '^ *Z')" ]; then REAPED=yes; break; fi
    sleep 0.1
  done
  if [ "$REAPED" = yes ]; then
    wait "$pid" 2>/dev/null
    REAP_RC=$?
  else
    kill -9 "$pid" 2>/dev/null
    wait "$pid" 2>/dev/null
    REAP_RC=none
  fi
}
# Bounded polls, 300 checks 0.1 s apart. Each returns 0 when its condition holds, 1 at the bound.
wait_for_file() { local i; for i in $(seq 1 300); do [ -e "$1" ] && return 0; sleep 0.1; done; return 1; }
wait_for_line() { local i; for i in $(seq 1 300); do grep -qx "$1" "$2" 2>/dev/null && return 0; sleep 0.1; done; return 1; }
# Adds in flight at once, from an add log: an enter while another add has not exited.
overlap_count() {
  awk '$1 == "enter" { if (n > 0) o++; n++ } $1 == "exit" { n-- } END { print o + 0 }' "$1"
}
# Frees every paused creation and the lock, so the next arm starts clean.
release_all() {
  local p
  : > "$CTL/go-judge"
  for p in $BG_PIDS; do : > "$CTL/go-add-$p"; reap "$p"; done
  rm -rf "$LOCK"
  rm -f "$CTL/hold-judge" "$CTL/hold-add"
  BG_PIDS=""
}

# DETERMINISTIC ARM. The config lock is held by hand, so the upstream write that the old hook
# makes fails every time. The new hook writes no upstream, so it passes with the lock held.
# One creation, no race needed. The lock is removed straight after.
: > "$MAIN/.git/config.lock"
bash "$tmp/run_one.sh" lk
rm -f "$MAIN/.git/config.lock"

# LOCK ARMS. The hook takes a mkdir lock at <git common dir>/banchi-worktree-add.lock around its
# `git worktree add`, so adds in one clone run one at a time. Three creations: a free lock (a
# control, green on the hook without the lock), a lock held by a live pid (the add must wait and
# say so), and a lock whose pid is gone (the add must take it over). Each wait polls a condition,
# bounded at 300 checks 0.1 s apart. No wait runs on a fixed time.
LOCK="$(git -C "$MAIN" rev-parse --path-format=absolute --git-common-dir)/banchi-worktree-add.lock"
WAIT_LINE='waiting for the worktree lock'
lock_names=(free held stale)

# free: no lock held. The creation must exit 0 and print no waiting line.
bash "$tmp/run_one.sh" free
rc="$(cat "$RUN_OUT/free.rc" 2>/dev/null)"
if [ "$rc" = "0" ]; then ok "free lock: exit 0"; else bad "free lock: exit ${rc:-none}"; tail -n 3 "$RUN_OUT/free.err" | sed 's/^/         stderr: /'; fi
if [ -d "$MAIN/.claude/worktrees/free" ] && git -C "$MAIN" rev-parse --verify --quiet refs/heads/worktree-free >/dev/null; then ok "free lock: tree and branch made"; else bad "free lock: tree or branch missing"; fi
if grep -q "$WAIT_LINE" "$RUN_OUT/free.err"; then bad "free lock: a waiting line was printed with no lock held"; else ok "free lock: no waiting line"; fi
if [ -e "$LOCK" ]; then bad "free lock: a lock dir was left behind"; else ok "free lock: no lock dir left behind"; fi

# held: the test takes the lock as a live holder, its own pid. The scope is set before the add.
mkdir "$LOCK" && echo "$$" > "$LOCK/pid"
if [ "$(cat "$LOCK/pid" 2>/dev/null)" = "$$" ]; then ok "held lock: the test holds the lock before the add starts"; else bad "held lock: the test could not take the lock"; fi

bash "$tmp/run_one.sh" held &
bg=$!
for i in $(seq 1 300); do
  grep -q "$WAIT_LINE" "$RUN_OUT/held.err" 2>/dev/null && break
  kill -0 "$bg" 2>/dev/null || break
  sleep 0.1
done
waited=no
grep -q "$WAIT_LINE" "$RUN_OUT/held.err" 2>/dev/null && waited=yes
if [ "$waited" = yes ]; then ok "held lock: the add printed the waiting line"; else bad "held lock: never waited for the held lock (no waiting line)"; fi
if [ -d "$MAIN/.claude/worktrees/held" ]; then bad "held lock: tree made while the lock was held"; else ok "held lock: tree not made while the lock is held"; fi

rm -rf "$LOCK"
exited=no
for i in $(seq 1 300); do
  [ -s "$RUN_OUT/held.rc" ] && { exited=yes; break; }
  sleep 0.1
done
if [ "$exited" = yes ]; then wait "$bg"; bg=""; fi
rc="$(cat "$RUN_OUT/held.rc" 2>/dev/null)"
if [ "$exited" = yes ] && [ "$rc" = "0" ]; then ok "held lock: exit 0 after the release"; else bad "held lock: no exit 0 after the release (exited=$exited rc=${rc:-none})"; tail -n 3 "$RUN_OUT/held.err" | sed 's/^/         stderr: /'; fi
if [ -d "$MAIN/.claude/worktrees/held" ] && git -C "$MAIN" rev-parse --verify --quiet refs/heads/worktree-held >/dev/null; then ok "held lock: tree and branch made"; else bad "held lock: tree or branch missing after the release"; fi
if [ -e "$LOCK" ]; then bad "held lock: lock dir left behind"; else ok "held lock: lock dir gone"; fi

# stale: the recorded pid is a process that has exited and been reaped. The add must take over.
true &
dead=$!
wait "$dead"
if kill -0 "$dead" 2>/dev/null; then bad "stale lock: the recorded pid is still live, so the case is not set up"; else ok "stale lock: the recorded pid is gone"; fi
mkdir "$LOCK" && echo "$dead" > "$LOCK/pid"
bash "$tmp/run_one.sh" stale
rc="$(cat "$RUN_OUT/stale.rc" 2>/dev/null)"
if [ "$rc" = "0" ]; then ok "stale lock: exit 0 with a dead holder"; else bad "stale lock: exit ${rc:-none} with a dead holder"; tail -n 3 "$RUN_OUT/stale.err" | sed 's/^/         stderr: /'; fi
if [ -d "$MAIN/.claude/worktrees/stale" ] && git -C "$MAIN" rev-parse --verify --quiet refs/heads/worktree-stale >/dev/null; then ok "stale lock: tree and branch made"; else bad "stale lock: tree or branch missing"; fi
if [ -e "$LOCK" ]; then bad "stale lock: a lock with a dead holder was left behind"; else ok "stale lock: no lock left"; fi
rm -rf "$LOCK"

# TWO WAITERS, ONE STALE LOCK. The lock's holder is dead. pb is paused at its first read of the
# lock's pid, so it judges the lock stale and holds there. pa then judges the same lock stale, takes
# it, and enters its add, which is paused. pb resumes with its judgment. A correct hook keeps pb out
# of its add until pa has left the lock. The seams order the reads, so this is deterministic.
PAIR_LOG="$tmp/add-pair.log"
: > "$PAIR_LOG"
export SELFTEST_ADD_LOG="$PAIR_LOG" SELFTEST_PIDFILE="$LOCK/pid"
true &
DEAD=$!
wait "$DEAD"
mkdir "$LOCK" && echo "$DEAD" > "$LOCK/pid"
: > "$CTL/hold-judge"
: > "$CTL/hold-add"
start_creation pb
PB=$!
if wait_for_file "$CTL/judged"; then
  start_creation pa
  PA=$!
  if wait_for_line "enter $PA" "$PAIR_LOG"; then
    : > "$CTL/go-judge"
    for _ in $(seq 1 300); do
      grep -qx "enter $PB" "$PAIR_LOG" 2>/dev/null && break
      grep -qF "$WAIT_LINE" "$RUN_OUT/pb.err" 2>/dev/null && break
      sleep 0.1
    done
    : > "$CTL/go-add-$PA"
    wait_for_line "enter $PB" "$PAIR_LOG"
    : > "$CTL/go-add-$PB"
    reap "$PA"; RC_A="$REAP_RC"; DONE_A="$REAPED"
    reap "$PB"; RC_B="$REAP_RC"; DONE_B="$REAPED"
    if [ "$DONE_A" = yes ] && [ "$RC_A" = 0 ]; then ok "two waiters: pa exits 0"; else bad "two waiters: pa did not exit 0 (rc ${RC_A:-none})"; tail -n 3 "$RUN_OUT/pa.err" | sed 's/^/         stderr: /'; fi
    if [ "$DONE_B" = yes ] && [ "$RC_B" = 0 ]; then ok "two waiters: pb exits 0"; else bad "two waiters: pb did not exit 0 (rc ${RC_B:-none})"; tail -n 3 "$RUN_OUT/pb.err" | sed 's/^/         stderr: /'; fi
    if [ -d "$MAIN/.claude/worktrees/pa" ] && git -C "$MAIN" rev-parse --verify --quiet refs/heads/worktree-pa >/dev/null; then ok "two waiters: pa's tree and branch made"; else bad "two waiters: pa's tree or branch missing"; fi
    if [ -d "$MAIN/.claude/worktrees/pb" ] && git -C "$MAIN" rev-parse --verify --quiet refs/heads/worktree-pb >/dev/null; then ok "two waiters: pb's tree and branch made"; else bad "two waiters: pb's tree or branch missing"; fi
    OVERLAPS="$(overlap_count "$PAIR_LOG")"
    if [ "$OVERLAPS" = 0 ]; then ok "two waiters: no two adds held the lock at once"; else bad "two waiters: $OVERLAPS add(s) entered while another add held the lock"; fi
    if [ -e "$LOCK" ]; then bad "two waiters: a lock dir was left behind"; else ok "two waiters: no lock dir left behind"; fi
  else
    bad "two waiters: pa never entered its add"
  fi
else
  bad "two waiters: pb never made its first read of the lock's pid"
fi
release_all
unset SELFTEST_ADD_LOG SELFTEST_PIDFILE

# EPERM COUNTS AS LIVE. A pid this user cannot signal is alive, so a lock it holds is not stale and
# the add waits. Pid 1 is such a pid for any user but root. Root signals every pid, so EPERM cannot
# happen there: the arm is skipped, and the SKIPPED line says why.
if [ "$(id -u)" = 0 ]; then
  echo "worktree-create-selftest: SKIPPED EPERM counts as live: unknown as root, which signals every pid, so EPERM cannot occur"
else
  mkdir "$LOCK" && echo 1 > "$LOCK/pid"
  start_creation eperm
  EP=$!
  for _ in $(seq 1 300); do
    grep -qF "$WAIT_LINE" "$RUN_OUT/eperm.err" 2>/dev/null && break
    [ -z "$(ps -o stat= -p "$EP" 2>/dev/null)" ] && break
    sleep 0.1
  done
  if grep -qF "$WAIT_LINE" "$RUN_OUT/eperm.err" 2>/dev/null; then
    ok "EPERM counts as live: the add waits on pid 1's lock"
    if [ "$(cat "$LOCK/pid" 2>/dev/null)" = 1 ]; then ok "EPERM counts as live: pid 1's lock is left in place"; else bad "EPERM counts as live: pid 1's lock was removed or changed"; fi
  else
    bad "EPERM counts as live: the add did not wait on pid 1's lock (no waiting line)"
  fi
  kill "$EP" 2>/dev/null
  reap "$EP"
  rm -rf "$LOCK"
fi

# CAP. A live lock that is never released makes the add fail at the cap, not wait for ever, and the
# failure names the lock path. BANCHI_WORKTREE_LOCK_WAIT=3 sets the cap for this arm.
mkdir "$LOCK" && echo "$$" > "$LOCK/pid"
export BANCHI_WORKTREE_LOCK_WAIT=3
start_creation cap
CP=$!
unset BANCHI_WORKTREE_LOCK_WAIT
reap "$CP"
if [ "$REAPED" != yes ]; then
  bad "cap: the add did not fail within 30 s, so BANCHI_WORKTREE_LOCK_WAIT=3 is not honoured"
elif [ "$REAP_RC" = 0 ]; then
  bad "cap: the add succeeded over a live lock"
else
  ok "cap: the add fails at the cap (rc $REAP_RC)"
  if grep -qF "$LOCK" "$RUN_OUT/cap.err" 2>/dev/null; then ok "cap: the failure names the lock path"; else bad "cap: the failure does not name the lock path"; tail -n 3 "$RUN_OUT/cap.err" | sed 's/^/         stderr: /'; fi
  if [ "$(cat "$LOCK/pid" 2>/dev/null)" = "$$" ]; then ok "cap: the live lock is left in place"; else bad "cap: the live lock was removed or changed"; fi
fi
rm -rf "$LOCK"

# SIGNAL RELEASES THE LOCK. INT or TERM to a holder mid-add must release the lock. The holder is
# paused inside its add, signalled, then let finish. The hook's trap runs when the add returns, so the
# holder exits with its signal's status, and its EXIT trap removes the lock.
for sig in INT TERM; do
  want=130
  [ "$sig" = TERM ] && want=143
  SIG_LOG="$tmp/add-$sig.log"
  : > "$SIG_LOG"
  export SELFTEST_ADD_LOG="$SIG_LOG"
  : > "$CTL/hold-add"
  start_creation_signalable "h$sig"
  HP=$!
  if wait_for_line "enter $HP" "$SIG_LOG"; then
    if [ "$(cat "$LOCK/pid" 2>/dev/null)" = "$HP" ]; then ok "$sig: the holder holds the lock while in its add"; else bad "$sig: the lock is not held by the holder while in its add"; fi
    kill -s "$sig" "$HP" 2>/dev/null
    : > "$CTL/go-add-$HP"
    reap "$HP"
    if [ "$REAPED" = yes ] && [ "$REAP_RC" = "$want" ]; then ok "$sig: the holder exits through its trap (rc $want) after its add"; else bad "$sig: the holder did not exit through its trap (rc ${REAP_RC:-none}, want $want)"; fi
    if [ -e "$LOCK" ]; then bad "$sig: the lock dir was left behind"; else ok "$sig: the lock dir is gone"; fi
  else
    bad "$sig: the holder never entered its add"
  fi
  release_all
done
unset SELFTEST_ADD_LOG

pnames=()
total=$((ROUNDS * PARALLEL))
for k in $(seq 1 "$total"); do pnames+=("w$k"); done

# Rounds run one after another. Within a round, PARALLEL creations run at once.
for r in $(seq 1 "$ROUNDS"); do
  start=$(( (r - 1) * PARALLEL ))
  round_names=("${pnames[@]:start:PARALLEL}")
  printf '%s\n' "${round_names[@]}" | xargs -P"$PARALLEL" -n1 bash "$tmp/run_one.sh"
done

# Per-name assertions: exit 0, the path as the last stdout line, the tree on disk, the branch.
names=("lk" "${pnames[@]}")
new_tree_names=(pa pb hINT hTERM)
made=$(( ${#names[@]} + ${#lock_names[@]} + ${#new_tree_names[@]} ))
for name in "${names[@]}"; do
  path="$MAIN/.claude/worktrees/$name"
  rc="$(cat "$RUN_OUT/$name.rc" 2>/dev/null)"
  last="$(tail -n 1 "$RUN_OUT/$name.out" 2>/dev/null)"
  if [ "$rc" = "0" ] && [ "$last" = "$path" ] && [ -d "$path" ] \
     && git -C "$MAIN" rev-parse --verify --quiet "refs/heads/worktree-$name" >/dev/null; then
    ok "$name: exit 0, path on the last stdout line, tree and branch made"
  else
    bad "$name: rc=${rc:-none} last=${last:-none} tree=$([ -d "$path" ] && echo yes || echo no)"
    tail -n 3 "$RUN_OUT/$name.err" | sed 's/^/         stderr: /'
  fi
done

# Totals: one main checkout plus one tree per creation, one branch per creation, no lock left.
trees="$(git -C "$MAIN" worktree list --porcelain | grep -c '^worktree ')"
branches="$(git -C "$MAIN" for-each-ref --format='%(refname)' 'refs/heads/worktree-*' | wc -l | tr -d ' ')"
if [ "$trees" = "$((made + 1))" ]; then ok "$((made + 1)) trees in total"; else bad "trees: want $((made + 1)), got $trees"; fi
if [ "$branches" = "$made" ]; then ok "$made worktree branches in total"; else bad "branches: want $made, got $branches"; fi
if [ -e "$MAIN/.git/config.lock" ]; then bad "a .git/config.lock was left behind"; else ok "no .git/config.lock left behind"; fi

# The race named in the hook's header: a config-lock message in any creation's stderr.
lock_hits="$(grep -l 'could not lock config\|unable to write upstream' "$RUN_OUT"/*.err 2>/dev/null | wc -l | tr -d ' ')"
echo "  info   creations whose stderr shows a config-lock error: $lock_hits"

echo "worktree-create-selftest: $pass passed, $fail failed (rounds=$ROUNDS parallel=$PARALLEL)"
[ "$fail" -eq 0 ]
