#!/usr/bin/env bash
# SessionStart hook. Provisions a git worktree's untracked state before any work starts.
#
# THE PROBLEM IT EXISTS FOR, measured 2026-08-29. A worktree gets the TRACKED files and
# nothing else, and four things `make check` needs are gitignored by deliberate decision:
#
#   .venv/              -> T6 "No module named 'numpy'"
#                          T7 "AttributeError: 'NoneType' object has no attribute 'new'"
#   harness/.cache/     -> T1 has nothing to replay
#   app/node_modules/   -> `make check` stops at lint
#   .git is a FILE      -> handled in scripts/docs-audit.py, not here
#
# NOT ONE OF THOSE MESSAGES CONTAINS THE WORD "worktree". A session lands in a fresh tree,
# the Stop hook runs the harness, three tests fail with errors that point at numpy, at a
# fixture's internals and at an empty cache, and the turn is spent diagnosing the
# environment instead of doing the work. That happened, and this script is its receipt.
#
# WHY NOT A DEVCONTAINER, since it is the obvious suggestion. A devcontainer's
# postCreateCommand fires when a CONTAINER is created. Claude Code's worktrees are created
# by `git worktree add` inside an existing checkout, sharing one container and one
# filesystem, so postCreateCommand never fires for them and every new worktree would start
# exactly as bare as before. A devcontainer answers "new machine, new clone", which is a
# real need and a different one. SessionStart is the event that actually corresponds to
# "somebody is about to work in this tree".
#
# WHAT IT INSTALLS AND WHAT IT ONLY REPORTS, because the line is deliberate:
#
#   harness/.cache/  COPIED. Local, ~90 KB, no network. It is also the SAFETY one: without
#                    it T1 has nothing to replay, and T1's refusal is what stands between a
#                    cold cache and a paid submission at the end of every turn.
#   harness/images/  SYMLINKED, and the difference from the line above is the point. 133 MB
#                    is too much to duplicate per worktree, and unlike the cache these are
#                    immutable: `fixtures.load` only ever ADDS a missing file, keyed by card
#                    id, so two trees sharing them cannot make each other score differently.
#                    A `PKMNSCAN_RERUN_T1=1` rewrites the CACHE, which is exactly why that
#                    one is copied and this one is not.
#                    Without it T1 still passes — by DOWNLOADING 151 images from
#                    pokemontcg.io. That is slow, rate-limited without a key, and simply
#                    fails offline, so a green T1 there was bought with a network fetch
#                    nobody asked for. Measured 2026-08-29 on a throwaway worktree, which is
#                    how this line came to exist at all.
#   .venv/           BUILT. A network pip install, but small, idempotent, and once per
#                    worktree — and it is what makes the harness able to run at all, which
#                    is the thing the Stop hook demands every turn.
#   app/node_modules REPORTED, NEVER INSTALLED. ~80 MB. The Makefile's NPM_GUARD already
#                    argues this and the argument is its own: "an implicit install hides a
#                    slow, network-touching step", and nothing on the turn-end path needs
#                    it. `make harness` does not; lint, typecheck and design-check do.
#
# IT FAILS OPEN, ALWAYS, which is this repo's standing rule for hooks and was learned the
# hard way — scripts/guard-opsec.sh over-triggered and was disabled within a day. A hook
# that can break a session is a hook that gets removed, and a removed hook guards nothing.
# Every path here exits 0: not a worktree, nothing missing, a failed copy, a failed pip, a
# bug in this file. The worst outcome is the bare worktree you already had.
#
# It is NOT on the commit path and must never be put there. D18: nothing that writes may
# run where a commit is decided. This writes, so it belongs at session start and nowhere
# near the git hook or `make check`.

set -uo pipefail
cd "$(dirname "$0")/.." 2>/dev/null || exit 0

# A linked worktree's `.git` is a FILE holding `gitdir: ...`; a normal clone's is a
# directory. That one fact is the whole detection, and it needs no subprocess.
[ -f .git ] || exit 0

main="$(dirname "$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null)" || exit 0
[ -n "$main" ] && [ -d "$main" ] || exit 0
[ "$main" = "$(pwd)" ] && exit 0

did_something=0

# The cache first: it is instant, it needs no network, and it is the one whose absence can
# cost money rather than time.
if [ ! -d harness/.cache ] && [ -d "$main/harness/.cache" ]; then
  if mkdir -p harness/.cache 2>/dev/null \
     && cp -R "$main/harness/.cache/." harness/.cache/ 2>/dev/null; then
    echo "worktree-guard: copied harness/.cache from the main working tree (T1 can replay)."
    did_something=1
  else
    echo "worktree-guard: could not copy harness/.cache — run \`make worktree-setup\`."
  fi
fi

# Symlinked rather than copied — 133 MB, immutable, additive-only. See the header.
if [ ! -e harness/images ] && [ -d "$main/harness/images" ]; then
  if mkdir -p harness 2>/dev/null && ln -s "$main/harness/images" harness/images 2>/dev/null; then
    echo "worktree-guard: linked harness/images (T1 scores without downloading 151 files)."
    did_something=1
  else
    echo "worktree-guard: could not link harness/images — T1 will re-download them."
  fi
fi

if [ ! -x .venv/bin/python ]; then
  echo "worktree-guard: building .venv (once for this worktree)…"
  if make venv >/dev/null 2>&1; then
    echo "worktree-guard: .venv ready — T6 and T7 can run."
    did_something=1
  else
    echo "worktree-guard: \`make venv\` failed. Run it by hand to see why; the harness"
    echo "                will fail T1, T6 and T7 until it succeeds."
  fi
fi

# Reported, never installed — see the header.
if [ ! -d app/node_modules ]; then
  echo "worktree-guard: app/ dependencies are absent (gitignored, so they do not travel)."
  echo "                \`make harness\` does not need them. lint, typecheck and"
  echo "                design-check do:  npm --prefix app install"
fi

[ "$did_something" = "1" ] && echo "worktree-guard: this worktree is provisioned. See \`make worktree-setup\`."

exit 0
