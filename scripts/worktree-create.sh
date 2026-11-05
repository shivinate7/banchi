#!/usr/bin/env bash
# WorktreeCreate hook. Makes every Claude Code worktree with a plain `git worktree add`.
#
# Claude Code's own worktree creation (an Agent with isolation: worktree, `--worktree`) does
# not run git's post-checkout hook, so those trees got no .venv, node_modules or harness
# cache. This hook replaces that creation. A plain `git worktree add` fires
# scripts/githooks/post-checkout, which provisions the tree like every other worktree.
#
# Same layout as Claude Code's default: `<main>/.claude/worktrees/<name>` on branch
# `worktree-<name>`, cut from a freshly fetched origin/main. A name whose branch is still
# there reuses that branch as it stands. session-teardown.sh deletes the branch with `-d`.
#
# `--no-track`: a branch cut from origin/main gets upstream tracking by default, and that
# writes the shared .git/config. Parallel Agents raced on its lock ("could not lock config
# file", "unable to write upstream branch configuration") and two of three failed. The
# branch has no upstream now, which is an ordinary first push. session-teardown.sh, which used `-d` (merged into upstream, else HEAD), now also
# tests the branch against the local origin/main and deletes a merged one with `-D`.
#
# `git worktree add` also races itself: one add reads a sibling's half-written
# .git/worktrees/<n>/commondir and dies ("failed to read ... commondir: Success"). It
# reproduces with plain git. The add (not the fetch) therefore runs under a lock directory at
# <git common dir>/banchi-worktree-add.lock, so adds in one clone run one at a time. The lock
# holds its owner's pid in <lock>/pid. It is built privately with the pid already inside, then
# renamed into place in one step that fails while the lock exists, so no lock is ever visible
# without its pid. A pid that is no live process is a stale lock: one waiter wins the move to a
# private name and confirms it holds the pid it judged. A waiter prints one line, polls, and
# fails the creation after BANCHI_WORKTREE_LOCK_WAIT seconds (default 120).
# rename, kill -0 and python3 only: no flock (absent on macOS), no bash-4 syntax.
#
# settings.json runs the copy at $CLAUDE_PROJECT_DIR, the tree the session launched in, never
# the cwd copy. That tree's settings armed this hook, so it holds this file too, even when the
# session has since moved into a tree cut before this file existed.
#
# Contract: stdin is JSON with `name`. The LAST line of stdout is the absolute path, so
# everything else goes to stderr. A non-zero exit fails the creation, so it exits non-zero
# only when git could not make the tree. scripts/session-teardown.sh removes it again.

set -uo pipefail
exec 3>&1 1>&2

name="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("name") or "")' 2>/dev/null)"
case "$name" in
  ""|*..*|/*|*[!A-Za-z0-9._/-]*) echo "worktree-create: bad name '$name'"; exit 1 ;;
esac

common="$(git rev-parse --path-format=absolute --git-common-dir)" || exit 1
main="$(dirname "$common")"
path="$main/.claude/worktrees/$name"
branch="worktree-$name"

# fd 3 is Claude Code's stdout. Every child gets it closed (3>&-), or a backgrounded
# `npm ci` from the post-checkout hook would hold it open and creation would wait for npm.
if git -C "$main" worktree list --porcelain 3>&- | grep -qx "worktree $path"; then
  [ -d "$path" ] && { echo "$path" >&3; exit 0; }   # re-entry: the tree is already there
  git -C "$main" worktree prune 3>&-               # deleted by hand: drop the record, remake it
fi

GIT_TERMINAL_PROMPT=0 git -C "$main" -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=20 \
  fetch --quiet origin main 3>&- || echo "worktree-create: fetch failed, using the last fetched origin/main"
base=origin/main
git -C "$main" rev-parse --verify --quiet "$base" >/dev/null 3>&- || { base=HEAD; echo "worktree-create: no origin/main, cutting from HEAD"; }

lock="$common/banchi-worktree-add.lock"
LOCK_WAIT_S="${BANCHI_WORKTREE_LOCK_WAIT:-120}"
case "$LOCK_WAIT_S" in ""|*[!0-9]*) echo "worktree-create: BANCHI_WORKTREE_LOCK_WAIT '$LOCK_WAIT_S' is not seconds, using 120"; LOCK_WAIT_S=120 ;; esac
held=0
stage="$lock.new.$$"       # this process's private lock, built with its pid already inside

# Remove the lock only when this process holds it, so a failed take never removes a sibling's.
# The private stage is always this process's own.
release_lock() {
  if [ "$held" = 1 ] && [ "$(cat "$lock/pid" 2>/dev/null)" = "$$" ]; then rm -rf "$lock"; fi
  held=0
  rm -rf "$stage"
}

# Rename a directory to a path that does not exist yet. It fails when the target holds
# anything: rename(2) refuses a non-empty directory, which `mv` would move into instead. A lock
# always holds its pid file, so this is the one step that takes a free lock.
rename_noreplace() {
  python3 -c 'import os,sys; os.rename(sys.argv[1], sys.argv[2])' "$1" "$2" 3>&- 2>/dev/null
}
trap release_lock EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# One judgment, one read: sets judged_pid from the lock's pid file and returns 0 when that pid
# is not a live process. The caller acts on judged_pid and never reads the file again. EPERM (a
# live process of another user) is live. A lock with no pid file is not one of ours (ours hold
# their pid from the first instant), so it is judged stale only after a grace of nopid polls.
nopid=0
judged_pid=""
lock_is_stale() {
  local err
  judged_pid="$(cat "$lock/pid" 2>/dev/null)"
  case "$judged_pid" in
    "") nopid=$((nopid + 1)); [ "$nopid" -gt 20 ]; return ;;
    *[!0-9]*) nopid=0; return 0 ;;
  esac
  nopid=0
  err="$(LC_ALL=C kill -0 "$judged_pid" 2>&1)" && return 1
  case "$err" in *"No such process"*) return 0 ;; esac
  return 1
}

# Take a lock judged stale on judged_pid. The rename moves it to a name only this process uses,
# so one waiter wins. The moved directory must hold the pid that was judged. If it holds another,
# a live holder took the lock between the judgment and the move: put it back, and when that fails
# (a sibling took the path) leave it where it is. Nothing here deletes a lock it did not judge.
reap_stale() {
  local gone="$lock.stale.$$.$SECONDS.$RANDOM"
  mv "$lock" "$gone" 3>&- 2>/dev/null || return 0
  if [ "$(cat "$gone/pid" 2>/dev/null)" = "$judged_pid" ]; then
    rm -rf "$gone"
  elif ! rename_noreplace "$gone" "$lock"; then
    echo "worktree-create: moved a live lock aside and could not put it back: $gone"
  fi
}

take_lock() {
  local start=$SECONDS announced=0
  rm -rf "$stage"
  mkdir "$stage" && echo "$$" > "$stage/pid" || { echo "worktree-create: cannot write the private lock $stage"; return 1; }
  while :; do
    if rename_noreplace "$stage" "$lock"; then
      held=1
      return 0
    fi
    if lock_is_stale; then
      reap_stale
      continue
    fi
    if [ "$announced" = 0 ]; then
      echo "worktree-create: waiting for the worktree lock $lock (held by pid $judged_pid)"
      announced=1
    fi
    if [ $((SECONDS - start)) -ge "$LOCK_WAIT_S" ]; then
      echo "worktree-create: gave up after ${LOCK_WAIT_S} s waiting for the worktree lock $lock"
      return 1
    fi
    sleep 0.2
  done
}

take_lock || exit 1
if git -C "$main" rev-parse --verify --quiet "refs/heads/$branch" >/dev/null 3>&-; then
  git -C "$main" worktree add "$path" "$branch" 3>&- || exit 1
else
  git -C "$main" worktree add --no-track -b "$branch" "$path" "$base" 3>&- || exit 1
fi
release_lock

echo "$path" >&3
