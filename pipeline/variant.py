"""The D3 variant-resolution ladder.

Resolve normal / holo / reverse holo per card, in order:

  1. METADATA        capture-time variant toggle, stored in the card's JSON sidecar.
                     Primary path.
  2. CATALOG_FORCED  one condition row for that number in the fixture, so the row decides.
                     Most SV-era rares are holofoil-only; a single row is itself evidence.
  3. DETECTION       Haiku's `finish` field. Runs as a CROSS-CHECK even when metadata
                     exists: a normal card mis-sorted into the reverse stack still matches
                     a valid catalog row, so only detection catches it.
  4. REVIEW          still ambiguous, detection disagrees with metadata, or no matching
                     catalog row.

THE TOGGLE IS TRUSTED (owner's call, 2026-08-03). It is set per stack, not left on a
default, so metadata is a claim and not a hint. Two consequences, and they are the whole
shape of the ladder:

  - Metadata naming a variant the catalog does not stock — toggle says normal, the number
    has only a Near Mint Holofoil row — is a CONTRADICTION, not a correction. It reviews
    (METADATA_NOT_STOCKED). Something is misfiled or misidentified, and resolving it
    silently to the only available row would list a card nobody thought was in the stack.
    This costs a tap per mis-toggled holofoil-only rare; that is the price of the toggle
    meaning something.
  - Rung 2 therefore fires only when there is NO capture-time metadata: a card captured
    before the toggle was set, or a batch run without it. One condition row and no claim
    to contradict, so the row decides.

Both review paths carry a distinct reason so the queue can be triaged: a run full of
METADATA_NOT_STOCKED means a stack is misfiled, while METADATA_DETECTION_DISAGREEMENT
scattered across a run means individual cards are mis-sorted.

Guards v1 bug #1: variant mispricing from blindly taking holofoil || reverseHolofoil ||
normal.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional, Sequence, Tuple

from pipeline import tcgcsv

NORMAL = "normal"
HOLO = "holo"
REVERSE_HOLO = "reverse_holo"

FINISHES: Tuple[str, ...] = (NORMAL, HOLO, REVERSE_HOLO)

# D12: all Near Mint, hardcoded. Vintage condition strings are a spec change, not a
# parameter.
CONDITION_BY_FINISH: Dict[str, str] = {
    NORMAL: "Near Mint",
    HOLO: "Near Mint Holofoil",
    REVERSE_HOLO: "Near Mint Reverse Holofoil",
}
FINISH_BY_CONDITION: Dict[str, str] = {v: k for k, v in CONDITION_BY_FINISH.items()}

# Ladder stages, named for the rung that DECIDED — not merely one that was consulted.
METADATA = "metadata"
CATALOG_FORCED = "catalog_forced"
DETECTION = "detection"
REVIEW = "review"

# Review reasons. Distinct strings so the queue can be triaged and so a test can assert
# which path fired, rather than only that something failed.
NO_CATALOG_ROW = "no_catalog_row"
METADATA_NOT_STOCKED = "metadata_not_stocked"
METADATA_DETECTION_DISAGREEMENT = "metadata_detection_disagreement"
DETECTED_FINISH_NOT_STOCKED = "detected_finish_not_stocked"
AMBIGUOUS_NO_SIGNAL = "ambiguous_no_signal"
DUPLICATE_CONDITION = "duplicate_condition"


class UnknownFinish(ValueError):
    """A finish string outside the enum. Never coerce — guess once and it prices wrong."""


@dataclass(frozen=True)
class Resolution:
    stage: str
    reason: str
    row: Optional[tcgcsv.Row] = None
    condition: Optional[str] = None
    market_price: Optional[Decimal] = None

    @property
    def needs_review(self) -> bool:
        return self.stage == REVIEW

    @property
    def sku(self) -> Optional[str]:
        return self.row[tcgcsv.SKU_COLUMN] if self.row else None


def _check(finish: Optional[str]) -> Optional[str]:
    if finish is None:
        return None
    if finish not in FINISHES:
        raise UnknownFinish(f"{finish!r} not in {FINISHES}")
    return finish


def _resolved(stage: str, row: tcgcsv.Row) -> Resolution:
    return Resolution(
        stage=stage,
        reason=stage,
        row=row,
        condition=row[tcgcsv.CONDITION_COLUMN],
        market_price=tcgcsv.parse_price(row[tcgcsv.MARKET_PRICE_COLUMN]),
    )


def resolve(
    candidates: Sequence[tcgcsv.Row],
    metadata_finish: Optional[str] = None,
    detected_finish: Optional[str] = None,
) -> Resolution:
    """Walk the ladder for one card. `candidates` are the catalog rows for its number."""
    metadata_finish = _check(metadata_finish)
    detected_finish = _check(detected_finish)

    if not candidates:
        return Resolution(stage=REVIEW, reason=NO_CATALOG_ROW)

    by_condition: Dict[str, tcgcsv.Row] = {}
    for row in candidates:
        condition = row[tcgcsv.CONDITION_COLUMN]
        if condition in by_condition:
            # Two candidate rows claiming the same condition string. The dict this used to
            # be built as would have kept the last one silently and priced whichever the
            # export happened to list second — a coin flip dressed as a resolution. The
            # shape that produces it is a cross-set join-key collision (v2 §5.1), which
            # `Catalog.candidates` normally catches first; this is the backstop for every
            # other way two rows can arrive here, and it reviews rather than picking.
            return Resolution(stage=REVIEW, reason=DUPLICATE_CONDITION)
        by_condition[condition] = row

    # Rung 1 — capture-time metadata, trusted.
    if metadata_finish is not None:
        wanted = CONDITION_BY_FINISH[metadata_finish]
        if wanted not in by_condition:
            # The toggle claims a variant this card does not come in. Reported before the
            # detection cross-check because it is the more specific finding: it points at
            # a misfiled stack or a wrong identification, not at one mis-sorted card.
            return Resolution(stage=REVIEW, reason=METADATA_NOT_STOCKED)
        # Rung 3 as a cross-check, before trusting rung 1.
        if detected_finish is not None and detected_finish != metadata_finish:
            return Resolution(stage=REVIEW, reason=METADATA_DETECTION_DISAGREEMENT)
        return _resolved(METADATA, by_condition[wanted])

    # Rung 2 — catalog-forced. Reached only with no metadata to contradict.
    if len(candidates) == 1:
        return _resolved(CATALOG_FORCED, candidates[0])

    # Rung 3 — detection.
    if detected_finish is not None:
        wanted = CONDITION_BY_FINISH[detected_finish]
        if wanted in by_condition:
            return _resolved(DETECTION, by_condition[wanted])
        return Resolution(stage=REVIEW, reason=DETECTED_FINISH_NOT_STOCKED)

    # Rung 4 — review.
    return Resolution(stage=REVIEW, reason=AMBIGUOUS_NO_SIGNAL)
