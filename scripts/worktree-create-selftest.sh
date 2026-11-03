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
# wait and say so), and a lock whose pid is gone (the add must take it over). The parallel arm
# then races ROUNDS*PARALLEL creations, which is the realistic shape. Trees made: the parallel
# count, plus lk, plus the three lock-arm trees, plus the main checkout. Knobs: ROUNDS (default 5)
# and PARALLEL (default 4). Raise them only if a red run is needed; the defaults are the stated
# contract.
#
# TEMP FILES follow the run-folder standard (decision test-temp-standard). A sweep case proves
# that the first request of a run removes an old sibling run folder and keeps a new one.
#
# Output is kept, never silenced: each creation writes its stdout and stderr to a file, and a
# FAIL line prints the stderr so the reason shows.

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
bg=""   # the held-lock creation, killed on any exit before it is reaped
trap 'rm -rf "$RUN_FOLDER" "$OLD_SIB" "$NEW_SIB"; [ -n "$bg" ] && kill "$bg" 2>/dev/null; true' EXIT

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
made=$(( ${#names[@]} + ${#lock_names[@]} ))
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
