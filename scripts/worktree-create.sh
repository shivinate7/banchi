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

if git -C "$main" rev-parse --verify --quiet "refs/heads/$branch" >/dev/null 3>&-; then
  git -C "$main" worktree add "$path" "$branch" 3>&- || exit 1
else
  git -C "$main" worktree add -b "$branch" "$path" "$base" 3>&- || exit 1
fi

echo "$path" >&3
