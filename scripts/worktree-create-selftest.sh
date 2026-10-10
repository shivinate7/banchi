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
# Knobs: ROUNDS (default 5) and PARALLEL (default 4). Trees made: ROUNDS*PARALLEL, plus the main
# checkout. Raise them only if a red run is needed; the defaults are the stated contract.
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

tmp="$(mktemp -d "${TMPDIR:-/tmp}/banchi-worktree-create.XXXXXX")" || { echo "cannot make a temp dir"; exit 1; }
trap 'rm -rf "$tmp"' EXIT

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

names=()
total=$((ROUNDS * PARALLEL))
for k in $(seq 1 "$total"); do names+=("w$k"); done

# Rounds run one after another. Within a round, PARALLEL creations run at once.
for r in $(seq 1 "$ROUNDS"); do
  start=$(( (r - 1) * PARALLEL ))
  round_names=("${names[@]:start:PARALLEL}")
  printf '%s\n' "${round_names[@]}" | xargs -P"$PARALLEL" -n1 bash "$tmp/run_one.sh"
done

# Per-name assertions: exit 0, the path as the last stdout line, the tree on disk, the branch.
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
if [ "$trees" = "$((total + 1))" ]; then ok "$((total + 1)) trees in total"; else bad "trees: want $((total + 1)), got $trees"; fi
if [ "$branches" = "$total" ]; then ok "$total worktree branches in total"; else bad "branches: want $total, got $branches"; fi
if [ -e "$MAIN/.git/config.lock" ]; then bad "a .git/config.lock was left behind"; else ok "no .git/config.lock left behind"; fi

# The race named in the hook's header: a config-lock message in any creation's stderr.
lock_hits="$(grep -l 'could not lock config\|unable to write upstream' "$RUN_OUT"/*.err 2>/dev/null | wc -l | tr -d ' ')"
echo "  info   creations whose stderr shows a config-lock error: $lock_hits"

echo "worktree-create-selftest: $pass passed, $fail failed (rounds=$ROUNDS parallel=$PARALLEL)"
[ "$fail" -eq 0 ]
