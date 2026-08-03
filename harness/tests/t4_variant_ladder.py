"""T4 — Variant ladder.

For a card with normal, holo, and reverse rows in the fixture, assert each ladder stage
resolves to the correct condition string and price.

Pass: all four stages, plus the review path fires on disagreement.

The ladder (D3 in docs/DECISIONS.md), in order:
  1. Capture-time metadata — variant toggle recorded in the card's JSON sidecar. Primary
     path. `--variant` on the batch script is only an override.
  2. Catalog-forced — one condition row for that number in the fixture (most SV-era rares
     are holofoil-only), so the row decides.
  3. Haiku `finish` field (normal | holo | reverse_holo), returned in every identification
     call at no extra cost. Runs as a cross-check even when metadata exists: a normal card
     mis-sorted into the reverse stack still matches a valid catalog row, so only
     detection catches it.
  4. Review queue — still ambiguous, detection disagrees with metadata, or no matching
     catalog row.

Stage 4 is not an afterthought: the disagreement case is the one that catches a mis-sort,
and it must be asserted to fire, not merely to be reachable.

Guards v1 bug #1: variant mispricing, which blindly took
holofoil || reverseHolofoil || normal.
"""

from harness.tests import NotImplementedYet, Result

NAME = "T4"
DESCRIPTION = "Variant ladder resolves all four stages"
PASS_CRITERIA = "all four stages correct, and review fires on metadata/detection disagreement"

FINISHES = ("normal", "holo", "reverse_holo")


def run() -> Result:
    raise NotImplementedYet(
        "NOT_IMPLEMENTED: no variant resolution yet (build-order step 5)"
    )
