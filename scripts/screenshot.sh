#!/usr/bin/env bash
# Headless render of a URL to captures/ui/<name>.png.
#
# Claude Code writes CSS it has never looked at, so a layout that is technically correct
# can still be broken. This is the loop that closes that gap — see docs/DESIGN.md.
#
# The browser half is scripts/screenshot.mjs — read its header for why this stopped being
# `npx playwright screenshot`, why `fullPage` survived the report that proposed replacing it,
# and what the completeness proof does. This file owns the manifest loop and the messages.
#
# A RENDER CAN NOW FAIL FOR THE RIGHT REASON. Until 2026-09-07 the only failure here was an
# empty file, so a render MISSING AN ELEMENT — a valid, non-empty, plausible-looking PNG —
# passed, and a session looked at an incomplete page and called a screen fine. A manifest line
# may name the elements the render must prove it drew, and this exits non-zero when one of
# them painted nothing.
#
#   scripts/screenshot.sh <url> <name> [<selector>[,<selector>...]]   one render
#   scripts/screenshot.sh --manifest <file>     one render per "<name> <url> [<selectors>]" line
#
# Renders go to captures/, which is gitignored. Never write them anywhere tracked: the
# same directory holds code-card photos, and a live unredeemed code is a bearer instrument.

set -uo pipefail

# Must match app/package.json's @playwright/test pin — two Playwright versions in one repo
# is two browser downloads and two behaviours. 1.55.1 rather than 1.55.0: GHSA-7mvr-c777-76hp,
# browsers downloaded without verifying the SSL certificate.
#
# IT IS THE SAME COPY NOW, NOT A MATCHING ONE. The render drives app/node_modules's
# @playwright/test — what `make design-check` runs — so this constant no longer selects a
# second download; it is the claim screenshot.mjs checks app/package.json against, and a
# disagreement fails the render rather than waiting to be noticed in a diff.
PLAYWRIGHT_VERSION="1.55.1"
VIEWPORT="1280,900"
WAIT_MS=600

cd "$(dirname "$0")/.." || exit 1
OUT_DIR="captures/ui"

# WHICH APP THIS CHECKOUT RENDERS (D43).
#
# scripts/views.txt names the MAIN tree's dev origin, because that is what CLAUDE.md, the
# Makefile's help and every spec name, and it is true there. A linked worktree serves its own
# port off its own path, over its own store — so rendering the manifest VERBATIM from a
# worktree photographs the MAIN TREE'S APP. That is D43's whole subject arriving in the one
# file D43 never reached, and `server/ports.py`'s own header names this line while leaving it:
# "scripts/views.txt points the screenshot runner at 5173".
#
# What it cost, before this: a branch's renders showed main's code with nothing saying so —
# the exact shape of the design-check fault app/devPort.ts was built to close, where the only
# signal a check gives is the one you were hoping for. Worse in the other direction, since the
# main checkout's server is the owner's real inventory: `make screenshot` from a worktree drew
# their store and wrote it into captures/ui/, which is where the `views exposure` row's whole
# argument about bearer instruments lives.
#
# DERIVED FROM server/ports.py AND NEVER RE-IMPLEMENTED HERE. That module is the same
# derivation `make dev`, `make server` and `make status` use, `app/devPort.ts` is its twin,
# and `make port-agreement` is what keeps the two honest. A third spelling of the algorithm in
# shell would be a third thing to keep in step — the risk ports.py names in its own header.
# stdlib-only, so no venv, matching scripts/worktree-guard.sh's call shape exactly.
read -r DEV_PORT DEV_BASE_PORT <<EOF
$(python3 - <<'PORTS' 2>/dev/null
import sys
sys.path.insert(0, ".")
from server import ports
print(ports.dev_port(), ports.DEV_BASE_PORT)
PORTS
)
EOF

# A LINKED WORKTREE THAT CANNOT DERIVE ITS PORT RENDERS NOTHING. `.git` as a FILE is the
# linked-worktree test, the same one fact app/devPort.ts, server/ports.py and
# scripts/worktree-guard.sh all detect on. Refusing is the answer here rather than an
# obstacle: falling back to the documented default would render the main checkout's app and
# the renders would look fine, which is the failure being fixed and not a degraded version
# of it. The main tree has nothing to derive and needs none of this.
if [ -z "${DEV_PORT:-}" ]; then
  if [ -f .git ]; then
    echo "screenshot: this is a linked worktree and its dev port could not be derived." >&2
    echo "  Without it the manifest's :5173 would render the MAIN checkout's app — a branch's" >&2
    echo "  screenshots showing main's code, over the owner's real store (D43). Refusing." >&2
    echo "  Fix: python3 must be able to import server/ports.py from $(pwd)" >&2
    exit 1
  fi
  DEV_PORT=5173
  DEV_BASE_PORT=5173
fi

# Says it once, and only when there is something to say. `make server` prints which port it
# took and whose store it is serving for the same reason: a tool that quietly moved is
# indistinguishable from one that did not.
if [ "$DEV_PORT" != "$DEV_BASE_PORT" ]; then
  echo "screenshot: this worktree serves :$DEV_PORT — rendering that, not the main tree's :$DEV_BASE_PORT."
fi

# Rewrites the MAIN tree's dev origin to this checkout's. Anchored at the start of the URL and
# scoped to the origin, so a :5173 anywhere else in a URL is left alone — and any other origin
# is passed through untouched, which is what keeps `make docs-audit`'s `views opsec` row the
# authority on what a manifest line may address.
#
# THE MANIFEST ONLY, AND THE SPLIT IS THE POINT. scripts/views.txt's `:5173` is a CONVENTION —
# every doc in this repo names that port and the file is tracked, so it cannot name a port that
# is a property of one machine's directory layout. A URL typed on the command line is an
# INSTRUCTION, and silently rendering a different port than the one someone typed is the same
# disease in a new place. So the manifest is rewritten and a typed URL is obeyed and warned
# about — which also leaves the one legitimate way to render the main tree from here.
this_tree() {
  if [ "$DEV_PORT" = "$DEV_BASE_PORT" ]; then
    printf '%s' "$1"
    return
  fi
  printf '%s' "$1" | sed -E "s#^http://(localhost|127\\.0\\.0\\.1):$DEV_BASE_PORT#http://\\1:$DEV_PORT#"
}

# The typed-URL half of that split: obeyed, never rewritten, and never silent about it.
warn_other_tree() {
  [ "$DEV_PORT" = "$DEV_BASE_PORT" ] && return 0
  case "$1" in
    http://localhost:"$DEV_BASE_PORT"/*|http://localhost:"$DEV_BASE_PORT"|\
    http://127.0.0.1:"$DEV_BASE_PORT"/*|http://127.0.0.1:"$DEV_BASE_PORT")
      echo "screenshot: :$DEV_BASE_PORT is the MAIN checkout's app, over a different store (D43)." >&2
      echo "  This worktree serves :$DEV_PORT. Rendering what you asked for, not this tree." >&2
      ;;
  esac
}

usage() {
  echo "usage: scripts/screenshot.sh <url> <name> [<selector>[,<selector>...]]" >&2
  echo "       scripts/screenshot.sh --manifest <file>" >&2
  echo "" >&2
  echo "  The selectors are what the render must PROVE it drew. Naming none renders the" >&2
  echo "  page and can only fail by writing no file at all." >&2
  exit 1
}

if ! command -v node >/dev/null 2>&1; then
  echo "screenshot: node not found. Install Node: https://nodejs.org (or: brew install node)" >&2
  exit 1
fi

# The Makefile's NPM_GUARD already required this of `make screenshot`; the standalone
# invocation did not, because npx downloaded its own Playwright. It does now.
if [ ! -d app/node_modules ]; then
  echo "screenshot: app/ dependencies are not installed, and the render reads Playwright from" >&2
  echo "  there rather than downloading a second copy (see scripts/screenshot.mjs)." >&2
  echo "  Fix: npm --prefix app install" >&2
  exit 1
fi

# Renders one URL and, where the manifest names selectors, proves they are in the picture.
# Two ways to fail and they mean different things: no PNG on disk, or a PNG that is missing
# something it was told to contain. The old sentence here — "an exit 0 from the CLI is not
# proof that anything was written" — was right and did not go far enough: a written file was
# never proof that the PAGE was written.
render() {
  local url name want dest out status
  url="$1"
  name="$2"
  want="${3:-}"
  dest="$OUT_DIR/$2.png"

  mkdir -p "$OUT_DIR" || return 1
  rm -f "$dest"

  out="$(EXPECTED_PLAYWRIGHT="$PLAYWRIGHT_VERSION" node scripts/screenshot.mjs \
    --url "$url" \
    --out "$dest" \
    --viewport "$VIEWPORT" \
    --wait-ms "$WAIT_MS" \
    --require "$want" 2>&1)"
  status=$?

  if [ ! -s "$dest" ]; then
    echo "screenshot: FAILED $name ($url)" >&2
    echo "$out" | sed 's/^/  /' >&2
    case "$out" in
      *"Executable doesn't exist"*|*"executable doesn't exist"*|*"playwright install"*)
        echo "  Fix: npx playwright@$PLAYWRIGHT_VERSION install chromium" >&2
        ;;
      *ECONNREFUSED*|*ERR_CONNECTION_REFUSED*|*"net::ERR"*)
        echo "  Fix: nothing is serving $url. Start it first (make dev)." >&2
        ;;
    esac
    return 1
  fi

  # A PNG landed. Whether it is a picture of the whole page is the other question, and the
  # exit status is the only thing that answers it — the file's existence never could.
  if [ $status -ne 0 ]; then
    echo "$out" | sed 's/^/  /' >&2
    return 1
  fi

  echo "$out" | grep -v '^[[:space:]]*$' | sed 's/^/  /' >&2
  echo "screenshot: $dest"
  return 0
}

case "${1:-}" in
  --manifest)
    manifest="${2:-}"
    [ -n "$manifest" ] || usage

    if [ ! -f "$manifest" ] || ! grep -qEv '^[[:space:]]*(#|$)' "$manifest" 2>/dev/null; then
      echo "make screenshot: no views to render yet."
      echo "  Needs $manifest listing '<name> <url>' lines, one per key view."
      echo "  Unblocked when the capture app's views exist — see docs/GATES.md and docs/DESIGN.md."
      echo "  To render a single URL now: scripts/screenshot.sh <url> <name>"
      exit 1
    fi

    failed=0
    while read -r name url want _rest; do
      case "$name" in ''|\#*) continue ;; esac
      if [ -z "$url" ]; then
        echo "screenshot: manifest line missing a URL: $name" >&2
        failed=1
        continue
      fi
      render "$(this_tree "$url")" "$name" "$want" || failed=1
    done < "$manifest"
    exit $failed
    ;;
  ''|-h|--help)
    usage
    ;;
  *)
    [ $# -eq 2 ] || [ $# -eq 3 ] || usage
    warn_other_tree "$1"
    render "$1" "$2" "${3:-}"
    exit $?
    ;;
esac
