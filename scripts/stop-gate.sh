#!/usr/bin/env bash
# Stop hook. USED TO run the harness before letting a turn end. Owner's ruling, 2026-09-20
# (see D248, docs/decisions/): the harness runs on the commit path
# and in CI only, never at turn end. Measured cost of the old behaviour: 23-24s on every
# single turn, whether or not the turn touched code the harness could catch anything in.
#
# This file is kept, on the Stop hook roster, doing no work, rather than deleted, so that a
# session asking "does anything run at turn end" gets an honest answer from --status instead
# of silence. The disarmed-reason mechanism below is the SAME SHAPE the old scaffolding-era
# arming logic used (most-decisive reason first, one `--status` flag, one escape hatch) — the
# decision entry argues why that shape, not the harness question, is worth keeping.
#
# Escape hatch:  PKMNSCAN_GATE=off
#   No longer changes what runs (nothing does), but stays recognised so a shell profile or
#   script that already sets it is not silently made meaningless — --status still names it
#   first, most-decisive, exactly as it did when it mattered.
#
# Status:  scripts/stop-gate.sh --status
#   Prints why the gate is not running the harness, without running anything. Read by
#   `make status`'s "turn gate" line.

set -uo pipefail
cd "$(dirname "$0")/.." || exit 0

# Why the gate does not run the harness at turn end. Ordered most-decisive first, matching
# the retired arming logic's own order.
disarmed_reason() {
  if [ "${PKMNSCAN_GATE:-}" = "off" ]; then
    echo "PKMNSCAN_GATE=off (redundant now — the harness left turn end entirely, D248)"
    return
  fi
  echo "harness moved off turn end — commit path and CI only (D248)"
}

reason="$(disarmed_reason)"

if [ "${1:-}" = "--status" ]; then
  echo "disarmed — $reason"
  exit 0
fi

# Always disarmed. Nothing runs at turn end.
exit 0
