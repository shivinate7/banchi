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
# branch has no upstream now. guard-shell's `_tracked_branch` reads no upstream as an ordinary
# first push. session-teardown.sh, which used `-d` (merged into upstream, else HEAD), now also
# tests the branch against the local origin/main and deletes a merged one with `-D`.
#
# `git worktree add` also races itself: one add reads a sibling's half-written
# .git/worktrees/<n>/commondir and dies ("failed to read ... commondir: Success"). It
# reproduces with plain git. The add (not the fetch) therefore runs under a mkdir lock at
# <git common dir>/banchi-worktree-add.lock, so adds in one clone run one at a time. The lock
# holds its owner's pid in <lock>/pid. A pid that is no live process is a stale lock and is
# taken over. A waiter prints one line, polls, and fails the creation after LOCK_WAIT_S.
# mkdir and kill -0 only: no flock (absent on macOS), no bash-4 syntax.
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
LOCK_WAIT_S=120
held=0

# Remove the lock only when this process holds it, so a failed take never removes a sibling's.
release_lock() {
  if [ "$held" = 1 ] && [ "$(cat "$lock/pid" 2>/dev/null)" = "$$" ]; then rm -rf "$lock"; fi
  held=0
}
trap release_lock EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# True when the pid in <lock>/pid is not a live process. EPERM (a live process of another
# user) is live. An empty pid file is the holder between mkdir and its write: live for a short
# grace (nopid polls), then stale, so a holder killed in that gap cannot wedge the lock.
nopid=0
lock_is_stale() {
  local pid err
  pid="$(cat "$lock/pid" 2>/dev/null)"
  case "$pid" in
    "") nopid=$((nopid + 1)); [ "$nopid" -gt 20 ]; return ;;
    *[!0-9]*) return 0 ;;
  esac
  nopid=0
  err="$(LC_ALL=C kill -0 "$pid" 2>&1)" && return 1
  case "$err" in *"No such process"*) return 0 ;; esac
  return 1
}

take_lock() {
  local start=$SECONDS announced=0 pid gone
  while :; do
    if mkdir "$lock" 2>/dev/null; then
      echo "$$" > "$lock/pid"
      held=1
      return 0
    fi
    if lock_is_stale; then
      # Move the stale lock aside (one rename wins), then check it was the one judged stale.
      pid="$(cat "$lock/pid" 2>/dev/null)"
      gone="$lock.stale.$$"
      if mv "$lock" "$gone" 2>/dev/null; then
        if [ "$(cat "$gone/pid" 2>/dev/null)" = "$pid" ]; then
          rm -rf "$gone"
        else
          mv "$gone" "$lock" 2>/dev/null || rm -rf "$gone"   # took a live lock: put it back
        fi
      fi
      continue
    fi
    if [ "$announced" = 0 ]; then
      echo "worktree-create: waiting for the worktree lock $lock (held by pid $(cat "$lock/pid" 2>/dev/null))"
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
