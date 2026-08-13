#!/usr/bin/env bash
# Headless render of a URL to captures/ui/<name>.png.
#
# Claude Code writes CSS it has never looked at, so a layout that is technically correct
# can still be broken. This is the loop that closes that gap — see docs/DESIGN.md.
#
# Uses Playwright's built-in `screenshot` CLI via npx, so there is no driver code and no
# package.json until the Vite app actually needs one (when the Vite capture app lands).
# The version is pinned here; bump it deliberately.
#
#   scripts/screenshot.sh <url> <name>          one render
#   scripts/screenshot.sh --manifest <file>     one render per "<name> <url>" line
#
# Renders go to captures/, which is gitignored. Never write them anywhere tracked: the
# same directory holds code-card photos, and a live unredeemed code is a bearer instrument.

set -uo pipefail

# Must match app/package.json's @playwright/test pin — two Playwright versions in one repo
# is two browser downloads and two behaviours. 1.55.1 rather than 1.55.0: GHSA-7mvr-c777-76hp,
# browsers downloaded without verifying the SSL certificate.
PLAYWRIGHT_VERSION="1.55.1"
VIEWPORT="1280,900"
WAIT_MS=600

cd "$(dirname "$0")/.." || exit 1
OUT_DIR="captures/ui"

usage() {
  echo "usage: scripts/screenshot.sh <url> <name>" >&2
  echo "       scripts/screenshot.sh --manifest <file>" >&2
  exit 1
}

if ! command -v npx >/dev/null 2>&1; then
  echo "screenshot: npx not found. Install Node: https://nodejs.org (or: brew install node)" >&2
  exit 1
fi

# Renders one URL. Returns non-zero unless a non-empty PNG lands on disk — an exit 0 from
# the CLI is not proof that anything was written.
render() {
  local url="$1" name="$2" dest="$OUT_DIR/$2.png" out status

  mkdir -p "$OUT_DIR" || return 1
  rm -f "$dest"

  out="$(npx --yes "playwright@$PLAYWRIGHT_VERSION" screenshot \
    --viewport-size="$VIEWPORT" \
    --full-page \
    --wait-for-timeout="$WAIT_MS" \
    "$url" "$dest" 2>&1)"
  status=$?

  if [ ! -s "$dest" ]; then
    echo "screenshot: FAILED $name ($url)" >&2
    echo "$out" | sed 's/^/  /' >&2
    case "$out" in
      *"Executable doesn't exist"*|*"executable doesn't exist"*|*"npx playwright install"*)
        echo "  Fix: npx playwright@$PLAYWRIGHT_VERSION install chromium" >&2
        ;;
      *ECONNREFUSED*|*ERR_CONNECTION_REFUSED*|*"net::ERR"*)
        echo "  Fix: nothing is serving $url. Start it first (make dev)." >&2
        ;;
    esac
    return 1
  fi

  # A non-empty PNG exists, so the render succeeded even if the CLI grumbled on the way out.
  [ $status -eq 0 ] || echo "screenshot: $name rendered, but the CLI exited $status" >&2
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
    while read -r name url _rest; do
      case "$name" in ''|\#*) continue ;; esac
      if [ -z "$url" ]; then
        echo "screenshot: manifest line missing a URL: $name" >&2
        failed=1
        continue
      fi
      render "$url" "$name" || failed=1
    done < "$manifest"
    exit $failed
    ;;
  ''|-h|--help)
    usage
    ;;
  *)
    [ $# -eq 2 ] || usage
    render "$1" "$2"
    exit $?
    ;;
esac
