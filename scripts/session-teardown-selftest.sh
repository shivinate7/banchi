#!/usr/bin/env bash
# `make session-teardown-selftest` — scripts/session-teardown.sh's branch delete (the WorktreeRemove
# path), proved against a throwaway repo with a bare origin.
# Protects: a worktree branch merged into origin/main is deleted even when the primary checkout's HEAD lags origin/main, and an unmerged branch is kept.
# Governs: D18
#
# WHY. The hook removes a worktree, then deletes its branch. The delete is `-D` only when the branch
# is an ancestor of origin/main, else `-d`, which checks HEAD of the primary checkout only. A
# merged branch that HEAD lags behind used to stay behind. These cases prove the three shapes:
#   (a) merged into origin/main, primary HEAD behind: deleted with -D.
#   (b) not merged anywhere: kept. Both flags refuse it.
#   (c) merged into primary HEAD only, not origin/main: deleted with -d, as before.
#
# A STUB janitor.py sits beside the hook copy under test, so the hook's teardown call touches no
# real session or process. A throwaway repo and origin hold every ref. core.hooksPath is an empty
# directory, so no hook runs in the temp tree. Nothing here touches this checkout.
#
# THE HOOK UNDER TEST. $SESSION_TEARDOWN_SCRIPT names the copy to run, so the red proof can point it
# at the old script. Default: scripts/session-teardown.sh beside this file.
#
# Output is kept, never silenced: the hook's stdout and stderr go to files, and a FAIL prints them.

set -uo pipefail          # NOT -e: every case must run and be scored

unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${SESSION_TEARDOWN_SCRIPT:-$HERE/session-teardown.sh}"
[ -f "$SCRIPT" ] || { echo "no session-teardown.sh at $SCRIPT"; exit 1; }

pass=0
fail=0
say() { printf '  %-6s %s\n' "$1" "$2"; }
ok()  { pass=$((pass + 1)); say "ok" "$1"; }
bad() { fail=$((fail + 1)); say "FAIL" "$1"; }

tmp="$(mktemp -d "${TMPDIR:-/tmp}/banchi-session-teardown.XXXXXX")" || { echo "cannot make a temp dir"; exit 1; }
trap 'rm -rf "$tmp"' EXIT

# The hook copy under test, beside a stub janitor. The hook finds janitor.py beside itself first.
mkdir -p "$tmp/scripts"
cp "$SCRIPT" "$tmp/scripts/session-teardown.sh"
printf 'import sys\nsys.exit(0)\n' > "$tmp/scripts/janitor.py"
HOOK="$tmp/scripts/session-teardown.sh"

git -c init.defaultBranch=main init --bare -q "$tmp/origin.git"
git -c init.defaultBranch=main init -q "$tmp/main"
MAIN="$(cd "$tmp/main" && pwd -P)"
git -C "$MAIN" config user.email selftest@example.invalid
git -C "$MAIN" config user.name selftest
git -C "$MAIN" remote add origin "$tmp/origin.git"
mkdir -p "$tmp/no-hooks"
git -C "$MAIN" config core.hooksPath "$tmp/no-hooks"

commit_file() { # dir name
  echo "$2" > "$1/$2.txt"
  git -C "$1" add "$2.txt"
  git -C "$1" commit -q -m "$2"
}

# Shared base: one commit on main, pushed, so origin/main and the primary HEAD agree.
commit_file "$MAIN" base
git -C "$MAIN" push -q origin main

# A worktree on a new branch, cut from origin/main the way the WorktreeCreate hook makes one.
# An optional start point overrides it: case c cuts from the primary HEAD.
make_tree() { # name [start]
  git -C "$MAIN" worktree add -q --no-track -b "worktree-$1" "$MAIN/.claude/worktrees/$1" "${2:-origin/main}"
}

run_teardown() { # name -> writes $tmp/<name>.out and .err, and $tmp/<name>.rc
  local tree="$MAIN/.claude/worktrees/$1"
  printf '{"worktree_path": "%s"}' "$tree" \
    | (cd "$MAIN" && bash "$HOOK") > "$tmp/$1.out" 2> "$tmp/$1.err"
  echo $? > "$tmp/$1.rc"
}

# ------------------------------------------------------------------ case a: merged into origin/main

make_tree a
commit_file "$MAIN/.claude/worktrees/a" a
git -C "$MAIN/.claude/worktrees/a" push -q origin HEAD:main
# Setup check: origin/main now holds the branch, and the primary HEAD does not.
if git -C "$MAIN" merge-base --is-ancestor worktree-a origin/main \
   && ! git -C "$MAIN" merge-base --is-ancestor worktree-a HEAD; then
  ok "a: setup holds (branch in origin/main, primary HEAD lags)"
else
  bad "a: setup did not hold; the case proves nothing"
fi
run_teardown a
if [ "$(cat "$tmp/a.rc")" = "0" ]; then ok "a: teardown exits 0"; else bad "a: teardown exit $(cat "$tmp/a.rc")"; fi
if [ ! -d "$MAIN/.claude/worktrees/a" ]; then ok "a: tree removed"; else bad "a: tree still on disk"; fi
if git -C "$MAIN" rev-parse --verify --quiet refs/heads/worktree-a >/dev/null; then
  bad "a: branch worktree-a kept though origin/main holds it"
  tail -n 3 "$tmp/a.err" | sed 's/^/         stderr: /'
else
  ok "a: branch worktree-a deleted (merged into origin/main, primary HEAD lags)"
fi

# ------------------------------------------------------------------ case b: merged nowhere

make_tree b
commit_file "$MAIN/.claude/worktrees/b" b
run_teardown b
if [ "$(cat "$tmp/b.rc")" = "0" ]; then ok "b: teardown exits 0"; else bad "b: teardown exit $(cat "$tmp/b.rc")"; fi
if git -C "$MAIN" rev-parse --verify --quiet refs/heads/worktree-b >/dev/null; then
  ok "b: unmerged branch worktree-b kept"
else
  bad "b: unmerged branch worktree-b was deleted"
fi

# ------------------------------------------------------------------ case c: merged into primary HEAD only

commit_file "$MAIN" local
make_tree c HEAD
# Setup check: the branch is in the primary HEAD, and not in origin/main.
if git -C "$MAIN" merge-base --is-ancestor worktree-c HEAD \
   && ! git -C "$MAIN" merge-base --is-ancestor worktree-c origin/main; then
  ok "c: setup holds (branch in primary HEAD, not in origin/main)"
else
  bad "c: setup did not hold; the case proves nothing"
fi
run_teardown c
if [ "$(cat "$tmp/c.rc")" = "0" ]; then ok "c: teardown exits 0"; else bad "c: teardown exit $(cat "$tmp/c.rc")"; fi
if git -C "$MAIN" rev-parse --verify --quiet refs/heads/worktree-c >/dev/null; then
  bad "c: branch worktree-c kept though the primary HEAD holds it (-d should delete)"
  tail -n 3 "$tmp/c.err" | sed 's/^/         stderr: /'
else
  ok "c: branch worktree-c deleted with -d (merged into primary HEAD)"
fi

echo "session-teardown-selftest: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
