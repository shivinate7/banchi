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
#   harness/images/  SYMLINKED TO WHEREVER THE MAIN TREE'S MIRROR ACTUALLY IS — asked for, not
#                    assumed, since D47 moved it out of iCloud and this line went on pointing at
#                    the old place in silence. It is back at the in-repo default as of
#                    2026-08-29, which is precisely what asking makes irrelevant: the answer
#                    moved twice in two days and this line did not change either time.
#                    The difference from the line above is the point:
#                    133 MB
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
#   .claude/         WRITTEN, and it is the only one wanted in EVERY checkout rather than
#     launch.json    only in a worktree — `ports.dev_port()` answers the main tree's 5173
#                    there by construction. It is also the only one whose ABSENCE is worse
#                    than its presence: the others fail loudly, and a missing launch.json
#                    gets filled in from a template with a hardcoded port, which previews
#                    the MAIN TREE from a worktree while looking like it worked (D43).
#                    Written conservatively — absent or stale only, a hand-edit reported
#                    and never overwritten — because this runs unasked.
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

# `.claude/launch.json` FIRST, AND ABOVE THE WORKTREE TEST, because it is the one thing here
# that is wanted in EVERY checkout — `ports.dev_port()` answers 5173 in the main tree by
# construction, so the same call is right everywhere and there is no branch to get wrong.
#
# IT IS ALSO THE ONE PROVISIONED THING WHOSE ABSENCE IS WORSE THAN ITS PRESENCE. The others
# degrade loudly: no venv and T6 says numpy, no cache and T1 refuses. A missing launch.json
# degrades into the Browser pane's own instructions, which tell an agent to write one from a
# template carrying a hardcoded port — and a worktree that names 5173 previews the MAIN TREE
# while looking like it worked (D43, amended). Measured 2026-08-30 across this clone's five
# worktrees: four correct, one absent, one holding a 5173 nobody remembered writing.
#
# `--if-needed` so it writes an absent or a stale file and REPORTS anything else. This runs
# unasked on every session start, which is the strongest possible reason not to overwrite
# something a person put there; `make launch-config` is the deliberate, forcing half.
# `--quiet` so the ordinary case — already correct — says nothing at all.
#
# BEFORE THE VENV IS BUILT, deliberately: the port is wanted whether or not the pip install
# ever succeeds, and `scripts/launch-config.py` is stdlib-only for exactly that reason.
if [ -f scripts/launch-config.py ] && [ -f server/ports.py ]; then
  python3 scripts/launch-config.py --if-needed --quiet 2>/dev/null || true
fi

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
#
# THE SOURCE IS ASKED FOR, NEVER ASSUMED, AND D47 IS WHY. This read `[ -d "$main/harness/images" ]`
# and linked that path. D47 then moved the mirror out of iCloud behind `PKMNSCAN_IMAGE_MIRROR`,
# so on a tree that sets it the main checkout has no `harness/images` at all — the precondition
# went false, the whole block was skipped, and NOTHING WAS PRINTED, because the only failure
# message here is on the `ln` and the `ln` was never reached. A fresh worktree then downloaded
# 151 images at the first `make harness`, which is the exact cost the header says this line
# exists to avoid. Observed 2026-08-30, from a Stop hook that failed T1 in a worktree whose
# main tree was healthy.
#
# So the main tree's own harness is asked where its images are. `fixtures.IMAGES_DIR` is the ONE
# resolution — env var, then that checkout's `.env`, then its in-repo default — and re-deriving
# that precedence in shell is how the two drift apart again. Stdlib-only at module scope, so a
# bare `python3` answers; `.env` is read by `envfile` and never by this script, and the only
# thing that crosses the pipe is a path.
mirror="$(cd "$main" 2>/dev/null && python3 -c 'import sys; sys.path.insert(0, "."); from harness.eval import fixtures; print(fixtures.IMAGES_DIR)' 2>/dev/null)"
[ -n "$mirror" ] || mirror="$main/harness/images"

if [ ! -e harness/images ]; then
  if [ ! -d "$mirror" ]; then
    # Said out loud rather than skipped. The silent skip is the defect above.
    echo "worktree-guard: no image mirror at $mirror — T1 will re-download 151 images."
  elif mkdir -p harness 2>/dev/null && ln -s "$mirror" harness/images 2>/dev/null; then
    echo "worktree-guard: linked harness/images -> $mirror (T1 scores without downloading 151 files)."
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

# WHICH PORTS THIS TREE OWNS, SAID BEFORE ANY WORK STARTS (D43).
#
# Unconditional in a worktree, and deliberately not gated on `did_something`: a provisioned
# tree is exactly the one a session will now start servers in, and the numbers are the thing
# it cannot guess. The store defaults to the checkout the code runs from, so a worktree's
# `make server` serves that worktree's own — usually EMPTY — inventory, and before D43 they
# all fought over one port and whichever won answered everybody. That is how the main tree's
# real captures could have landed in a directory deleted with a branch.
#
# It never fails the hook. `|| true` on the whole thing and a stdlib-only import, because a
# SessionStart hook that can exit non-zero is a hook that stops a session from starting.
if [ -f .git ] && [ -f server/ports.py ]; then
  python3 - <<'PORTS' 2>/dev/null || true
import sys
sys.path.insert(0, ".")
from server import ports
print(f"worktree-guard: this tree serves capture :{ports.capture_port()} and dev :{ports.dev_port()}")
print(f"                the main checkout has :{ports.CAPTURE_BASE_PORT} / :{ports.DEV_BASE_PORT}, over a DIFFERENT store")
PORTS
fi

exit 0
