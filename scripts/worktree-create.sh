#!/usr/bin/env bash
# WorktreeCreate hook. Makes every Claude Code worktree with a plain `git worktree add`.
#
# Claude Code's own worktree creation (an Agent with isolation: worktree, `--worktree`) does
# not run git's post-checkout hook, so those trees got no .venv, node_modules or harness
# cache. This hook replaces that creation. A plain `git worktree add` fires
# scripts/githooks/post-checkout, which provisions the tree like every other worktree.
#
# Same layout as Claude Code's default: `<main>/.claude/worktrees/<name>` on branch
# `worktree-<name>`, cut from a freshly fetched origin/main.
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

git -C "$main" fetch --quiet origin main || echo "worktree-create: fetch failed, using the last fetched origin/main"
base=origin/main
git -C "$main" rev-parse --verify --quiet "$base" >/dev/null || base=HEAD

if git -C "$main" rev-parse --verify --quiet "refs/heads/$branch" >/dev/null; then
  git -C "$main" worktree add "$path" "$branch" || exit 1
else
  git -C "$main" worktree add -b "$branch" "$path" "$base" || exit 1
fi

echo "$path" >&3
