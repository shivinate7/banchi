#!/usr/bin/env bash
# Stop hook. Runs the harness before letting a turn end — but only once the harness is
# real. During scaffolding the tests exist and are meant to fail, so gating on them would
# block every turn for no reason.
#
# Arming is keyed on implementation status, not on filenames: the gate stays disarmed
# while any test still carries its NOT_IMPLEMENTED marker, and arms itself the moment the
# last one is deleted. No toggle to remember, and no filename coincidence that a later
# rename would silently break.
#
# Escape hatch:  PKMNSCAN_GATE=off
#   For debugging the last test after its marker is gone. Deliberate, visible in your
#   shell, and — unlike editing this file or re-adding a marker — it does not change what
#   the gate means.
#
# Status:  scripts/stop-gate.sh --status
#   Prints armed/disarmed and why, without running anything.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 0

# Why the gate is not running the harness right now, or empty if it is.
# Ordered most-decisive first.
disarmed_reason() {
  if [ "${PKMNSCAN_GATE:-}" = "off" ]; then
    echo "PKMNSCAN_GATE=off"
    return
  fi
  if [ ! -f Makefile ] || ! grep -qE '^harness:' Makefile; then
    echo "no harness target in Makefile"
    return
  fi
  if [ ! -d harness/tests ]; then
    echo "harness/tests does not exist"
    return
  fi

  # Test modules only. harness/tests/__init__.py documents the marker, and counting it
  # would disarm the gate forever — which is exactly what happened the first time.
  local stubs
  stubs="$(grep -rl 'NOT_IMPLEMENTED' harness/tests --exclude='__init__.py' 2>/dev/null \
    | sed -e 's#.*/##' -e 's/_.*//' \
    | sort -u \
    | tr '\n' ' ')"
  stubs="${stubs% }"
  if [ -n "$stubs" ]; then
    echo "stubs remain: $stubs"
    return
  fi

  echo ""
}

reason="$(disarmed_reason)"

if [ "${1:-}" = "--status" ]; then
  if [ -n "$reason" ]; then
    echo "disarmed — $reason"
  else
    echo "armed"
  fi
  exit 0
fi

[ -n "$reason" ] && exit 0

output="$(make harness 2>&1)"
status=$?

if [ $status -ne 0 ]; then
  echo "Harness is failing — the turn cannot end here. Fix it or say explicitly why this failure is expected." >&2
  echo "$output" | tail -30 >&2
  exit 2
fi

exit 0
