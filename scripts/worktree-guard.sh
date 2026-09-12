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
#     harness/images   it T1 has nothing to replay, and T1's refusal is what stands between a
#   app/node_modules cold cache and a paid submission at the end of every turn. The mirror
#                    (133 MB) is SYMLINKED rather than copied, asked for rather than assumed
#                    — see scripts/worktree-provision.sh's header for why, and D47 for the
#                    drift that assuming cost once already. node_modules (~80 MB) is
#                    REPORTED, NEVER INSTALLED, for the reason the Makefile's NPM_GUARD
#                    already argues: an implicit install hides a slow, network-touching
#                    step, and nothing on the turn-end path needs it. All three are shared
#                    with `make worktree-setup` through that one script rather than kept as
#                    two copies of the same logic.
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
# THE MAIN CHECKOUT PARKED ON A MERGED BRANCH, WHICH IS THE OTHER WAY A TREE GOES STALE.
#
# Everything above is about a worktree missing what it needs. This is the opposite tree and
# the opposite failure: the MAIN checkout is the owner's live rig — their real store, the
# ports every doc names, the server `make launch-agent` starts at login — and it drifts by
# being left on a feature branch after that branch merges. Measured 2026-08-30: it sat on
# `claude/d57-cap-is-a-quantity` for a day, 70 commits behind, serving a store through code
# that predated four merged PRs. Nothing was lost, because the branch was fully merged; what
# it cost was a rig running code nobody was reading any more.
#
# `make status` already reported it — `0 ahead of main, 70 behind it` — and nobody was
# looking. That is the argument for putting it here instead: this runs unasked, before any
# work, which is D43's own reason for printing the ports here rather than leaving them to a
# target somebody has to remember.
#
# IT SYNCS NOW, AND IT USED TO REPORT AND NEVER SWITCH (D-the-primary-checkout-syncs-itself).
# The paragraph that stood here said a hook moving the branch would be "deciding for the
# operator, and `git switch` is theirs to type" — which is the ceiling the owner reopened in as
# many words. Offered a guard that only reported, they answered: *"why can't both parts sync,
# remember this is a one man show, it's just me working."*
#
# TWO PARTS, AND `post-checkout` CAN SEE ONLY ONE OF THEM. That hook fires on a branch switch
# and NOT on `git pull`, `git merge` or `git rebase` — measured — so it cannot see main going
# stale, only the tree going off it. "On main" and "at origin/main" are therefore genuinely
# separate questions, and this is one of the two readers that has ever printed the second.
# Now it answers both instead of printing them.
#
# THE REPORT BELOW IS KEPT AND IS NOT REDUNDANT. `scripts/primary_sync.py` refuses rather than
# discards — uncommitted tracked work, a half-finished rebase, a main that is not a
# fast-forward — and in every one of those the tree is still off main and the ahead/behind/dirty
# counts are still the thing a session needs. So the sync runs first and the report describes
# whatever it could not fix.
#
# IT IS NOT ONLY THE MERGED CASE, AND THE CODE WAS ALWAYS WIDER THAN THIS COMMENT (D139).
# What is reported is the main checkout standing on ANY branch that is not main, merged or not;
# the ahead/behind/dirty counts are printed so the reader can tell which they have. The 2026-08-30
# incident above is the merged instance of it, and the 2026-09-11 one is the other: this tree on
# `claude/env-key-rotation`, three live sessions in it, unmerged work, nothing anywhere saying so.
# D139 is why there are three readers of this one fact rather than this one — git has no
# `pre-checkout` hook, so no single moment can refuse the move, and a warning at one missable
# moment is a warning that gets missed. `scripts/githooks/post-checkout` says it at the moment
# of the switch, `make status` says it under SERVING beside the server it qualifies, and this
# says it to a session that arrives after the fact and would otherwise never ask.
#
# `.git` is a DIRECTORY here, which is exactly the test the block above uses inverted: a
# linked worktree gets a FILE. A worktree ON a feature branch is correct and is not reported.
if [ -d .git ] && git rev-parse --verify --quiet main >/dev/null 2>&1; then
  # THE SYNC, BEFORE THE READING, so what is reported is what is left rather than what was.
  # `|| true` and `2>/dev/null` on the whole thing for this file's standing rule: a
  # SessionStart hook that can exit non-zero is a hook that stops a session from starting, and
  # `primary_sync.py` already exits 0 for a refusal for the same reason. Its own bugs are
  # silent by design, so the worst case here is the bare report this block used to be.
  if [ -f scripts/primary_sync.py ] && [ -f server/ports.py ]; then
    python3 scripts/primary_sync.py --confirm --quiet 2>/dev/null || true
  fi
  branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
  if [ -n "$branch" ] && [ "$branch" != "main" ]; then
    counts=$(git rev-list --left-right --count main...HEAD 2>/dev/null || echo "")
    behind=$(echo "$counts" | awk '{print $1}')
    ahead=$(echo "$counts" | awk '{print $2}')
    dirty=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    echo "worktree-guard: this is the MAIN checkout and it is on '$branch', not main."
    echo "                ${ahead:-?} ahead / ${behind:-?} behind, ${dirty} uncommitted."
    # THE WHY, ABOVE THE BRANCHING ARMS SO IT IS SAID IN BOTH (D139). Until this line the
    # reason appeared only in the clean arm, as "This tree is the live rig" — and the arm a
    # session actually lands in is the OTHER one, because a tree somebody is working in has
    # uncommitted files by definition. So the case that needed the warning got the warning
    # without the reason, which reads as a tidiness notice and is not one.
    echo "                The live capture server is built out of THIS directory, so it is"
    echo "                serving this branch's code over the owner's REAL store (D53)."
    # REACHING EITHER ARM MEANS THE SYNC DID NOT PUT THIS TREE ON MAIN — it runs above, and the
    # branch is read after it. So neither arm asserts what the sync SAID: it may have declined
    # and printed a reason, or it may be switched off entirely with PKMNSCAN_SYNC=off, and a
    # sentence pointing at an explanation that is not there is worse than no sentence. Same
    # correction `scripts/serve.py:stand_down_lines` carries, for the same reason.
    if [ "$ahead" = "0" ] && [ "$dirty" = "0" ]; then
      echo "                Nothing here is unmerged and nothing is uncommitted, so"
      echo "                \`git switch main\` loses nothing. This tree is the live rig."
    else
      echo "                It holds work main does not, or edits not committed. Do not"
      echo "                switch blind — see \`make status\`."
    fi
    echo "                The self-sync runs ahead of this report and prints its own reason"
    echo "                when it declines; PKMNSCAN_SYNC=off stops it running at all."
  fi
fi

[ -f .git ] || exit 0

main="$(dirname "$(git rev-parse --git-common-dir 2>/dev/null)" 2>/dev/null)" || exit 0
[ -n "$main" ] && [ -d "$main" ] || exit 0
[ "$main" = "$(pwd)" ] && exit 0

did_something=0

# Cache and image-mirror provisioning is shared with `make worktree-setup` — see
# scripts/worktree-provision.sh's header for why this used to be two copies of the same
# cp/ln/python-one-liner sequence, and D47 for the drift that duplication cost. Presence is
# checked before and after so `did_something` still gates the summary line below exactly as
# it did when this logic lived here directly; the script itself is silent about which case
# it hit.
had_cache=0; [ -d harness/.cache ] && had_cache=1
had_images=0; [ -e harness/images ] && had_images=1

bash "$(dirname "$0")/worktree-provision.sh" --prefix "worktree-guard: " "$main"

{ [ "$had_cache" = 0 ] && [ -d harness/.cache ]; } && did_something=1
{ [ "$had_images" = 0 ] && [ -e harness/images ]; } && did_something=1

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
