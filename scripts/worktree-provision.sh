#!/usr/bin/env bash
# Provisions (or reports on) a worktree's two heaviest untracked-but-needed pieces of
# harness state: the T1 replay cache and the T1 image mirror, plus a note about
# app/node_modules. Shared by scripts/worktree-guard.sh (the SessionStart hook, which runs
# unasked and fails open) and `make worktree-setup` (a person asking explicitly) — before
# this file existed, both carried their own copy of the same cp/ln/python-one-liner
# sequence, so D47's image-mirror fix had to land in both files by hand and the two could
# silently drift the next time either changed. One copy now; a fix here reaches both
# callers by construction.
#
# Takes the MAIN working tree's path as its last argument. Writes nothing to stdin,
# prompts for nothing, and every failure here is reported rather than fatal — this is
# provisioning, not a gate (D18 already keeps both callers off the commit path; this
# script does not change that).
#
# --prefix TEXT prepends TEXT to every line this script prints, so each caller keeps its
# own voice — scripts/worktree-guard.sh's lines all read "worktree-guard: ...", `make
# worktree-setup`'s do not — without duplicating the eleven messages themselves.

set -uo pipefail

prefix=""
if [ "${1:-}" = "--prefix" ]; then
  prefix="${2:-}"
  shift 2
fi
main="${1:?usage: worktree-provision.sh [--prefix TEXT] <main-worktree-path>}"

say() { printf '%s%s\n' "$prefix" "$1"; }

# The cache first: local, ~90 KB, no network, and the SAFETY one — without it T1 has
# nothing to replay and refuses rather than spending real money on a submission nobody
# asked for. Skipped if this worktree already has one: a person or an earlier session may
# have banked a fresher run here, and provisioning must never clobber it silently.
if [ ! -d harness/.cache ]; then
  if [ -d "$main/harness/.cache" ]; then
    if mkdir -p harness/.cache 2>/dev/null && cp -R "$main/harness/.cache/." harness/.cache/ 2>/dev/null; then
      say "copied harness/.cache from the main working tree (T1 can replay)."
    else
      say "could not copy harness/.cache from $main — run \`make worktree-setup\`."
    fi
  else
    say "NOTE: $main has no harness/.cache — T1 will refuse until a run is banked there."
  fi
fi

# The mirror: 133 MB, immutable, additive-only, so it is linked rather than copied.
# `fixtures.IMAGES_DIR` is the ONE resolution (env var, then that checkout's `.env`, then
# the in-repo default) — asked of the MAIN tree's own harness rather than re-derived here,
# because re-deriving that precedence in shell is exactly how this drifted out of sync the
# first time the mirror moved (D47): the old inline copy in each caller kept a hardcoded
# path after the real answer changed, and neither one said so.
if [ ! -e harness/images ]; then
  mirror="$(cd "$main" 2>/dev/null && python3 -c 'import sys; sys.path.insert(0, "."); from harness.eval import fixtures; print(fixtures.IMAGES_DIR)' 2>/dev/null)"
  [ -n "$mirror" ] || mirror="$main/harness/images"
  if [ ! -d "$mirror" ]; then
    say "NOTE: no image mirror at $mirror — T1 will re-download 151 images."
  elif mkdir -p harness 2>/dev/null && ln -s "$mirror" harness/images 2>/dev/null; then
    say "linked harness/images -> $mirror (133 MB, immutable/additive — T1 scores without downloading 151 files)."
  else
    say "could not link harness/images -> $mirror — T1 will re-download them."
  fi
fi

# Reported, never installed — ~80 MB, and nothing on the harness path needs it.
if [ ! -d app/node_modules ]; then
  say "app/ dependencies are absent (gitignored, so they do not travel)."
  say "\`make harness\` does not need them. lint, typecheck and design-check do:"
  say "  npm --prefix app install"
fi

exit 0
