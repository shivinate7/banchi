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
  local url="$1" name="$2" want="${3:-}" dest="$OUT_DIR/$2.png" out status

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
      render "$url" "$name" "$want" || failed=1
    done < "$manifest"
    exit $failed
    ;;
  ''|-h|--help)
    usage
    ;;
  *)
    [ $# -eq 2 ] || [ $# -eq 3 ] || usage
    render "$1" "$2" "${3:-}"
    exit $?
    ;;
esac
