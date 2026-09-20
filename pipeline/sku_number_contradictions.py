"""One SKU, two stored numbers — the SKU self-contradiction check kept apart from
`pipeline/identity_checks.py` on the owner's own ruling: *"keep the more speculative
contradiction rate as a separate thing from the four approved checks."*

THE FINDING THIS ANSWERS. A SKU is one product in one condition. There is no legitimate
reason for two copies of it to read a different card number. Measured against the owner's
real store: 150 of 881 SKUs with a number disagree, after normalizing through
`store.numbers.strip_set_code` and `pipeline.join.number_index_key`. This module needs no
catalogue to FIND that — the store already contradicts itself.

WHAT IT NEEDS A CATALOGUE FOR is telling apart two different reasons a SKU can disagree, and
this is the owner's second ruling, over the risk they raised themselves: in Riftbound, an
over-numbered card can carry the same name and text as its base-rarity twin while being a
genuinely different card. Two copies reading differently might be two CORRECT reads of two
DIFFERENT cards, with the real defect being the SKU they share rather than either number.
"Since it's cheap to pull the catalogue, it's easier and better to normalize off of it."

THREE OUTCOMES, NEVER COLLAPSED INTO ONE. `Market.products(category_id, group_id)` answers
a whole group in one cached request, so this stays cheap even over many SKUs; it reuses
the same object `pipeline/pricehistory.py:product_id_for_row`
already builds, so one already-open group costs nothing to ask a second time):

  - Only one side resolves to a real product number in the group -> the OTHER side is a
    misread. `Outcome.MISREAD`.
  - Both sides resolve to real, DISTINCT product numbers -> the numbers are both fine and
    the SKU itself is wrong, sitting on two different cards. `Outcome.SHARED_SKU`. A
    different defect than a misread, and reported as one.
  - Neither resolves -> the catalogue cannot settle it. `Outcome.UNRESOLVED`. This module
    never picks a winner here, matching `CLAUDE.md`'s own rule against guessing an
    identification.

A DISAGREEMENT ON THE DENOMINATOR ITSELF NEEDS NO CATALOGUE CALL AT ALL. A set has one
size. `134/166` against `134/266` cannot both be the same product's printed total, so this
class is reported as `Outcome.DENOMINATOR_MISMATCH` without ever building a `Market`. This
is the bulk of the store's own finding — 101 of the 150 disagreeing SKUs, measured — and it
is the one class this module can call unambiguous on stored data alone.

REPORTS BOTH DIRECTIONS AND PICKS NO WINNER. `resolve` never writes a card, never chooses
which of two disagreeing numbers is right, and never queues anything — the queue has
nowhere to put a card that was already answered — `store/queues.py:Queue.upsert` refuses
to re-queue a position already `cleared_by_human` (D167). It returns a `Resolution` a
human, or a future caller, decides what to do with.

Cites D146 (two agreeing signals release a claim; here, a catalogue lookup releases one
side over the other only when exactly one side agrees with it), D173, D167, and the four
approved stored-data checks built as a separate, sibling PR.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from pipeline.join import number_index_key
from store.numbers import strip_set_code

_DENOM_RE = re.compile(r"^(.*)/(\d+)$")


def normalize_number(number: Optional[str]) -> str:
    """The one fold both this check and the archive's own contradiction count pass
    through: `strip_set_code` first, to remove a glued prefix, then `number_index_key`, to
    fold zero-padding and case. Measured on the real store: 219 SKUs disagree on the raw
    string, 150 after this fold — most of the difference is glued set codes D234's own
    repair already handles, so comparing before this fold overstates the finding by nearly
    half.
    """
    return number_index_key(strip_set_code(number))


def _denominator(key: str) -> Optional[str]:
    match = _DENOM_RE.match(key)
    return match.group(2) if match else None


@dataclass(frozen=True)
class NumberRecord:
    """One card's stored number, and enough to resolve it against a catalogue group."""

    key: str
    number: Optional[str]
    set_name: Optional[str] = None
    game: Optional[str] = None


@dataclass(frozen=True)
class Disagreement:
    """One SKU whose cards disagree about the number, after normalizing."""

    sku: str
    set_name: Optional[str]
    game: Optional[str]
    cards: Tuple[NumberRecord, ...]
    distinct_keys: Tuple[str, ...]

    @property
    def denominator_mismatch(self) -> bool:
        """True unless every stored number cleanly parses as `NUM/DENOM` AND all of them
        carry the SAME denominator. A set has one size, so two clean-shaped numbers with
        different denominators can never both be right — no catalogue needed. A number
        that does not even parse this cleanly (a glued fragment, a bare digit run with no
        slash) is not "plausibly the same card at a different rarity" either — it is
        already a self-evident contradiction, and is folded into this same unambiguous
        bucket rather than a third, uncategorized one. Only a disagreement where EVERY
        side is a clean, agreeing-denominator number needs the catalogue at all.
        """
        matches = [_DENOM_RE.match(key) for key in self.distinct_keys]
        if not all(matches):
            return True
        denominators = {match.group(2) for match in matches}
        return len(denominators) > 1


def find_disagreements(by_sku: Dict[str, List[NumberRecord]]) -> Dict[str, Disagreement]:
    """The caller groups its rows by SKU first — the real store's `cards` table has no
    direct SKU index, so `cli`'s own reader does that grouping. This function only
    normalizes each group's numbers and keeps the SKUs that disagree after the fold.
    """
    out: Dict[str, Disagreement] = {}
    for sku, records in by_sku.items():
        numbered = [r for r in records if (r.number or "").strip()]
        if len(numbered) < 2:
            continue
        keys = {normalize_number(r.number) for r in numbered}
        if len(keys) <= 1:
            continue
        set_name = next((r.set_name for r in numbered if r.set_name), None)
        game = next((r.game for r in numbered if r.game), None)
        out[sku] = Disagreement(
            sku=sku,
            set_name=set_name,
            game=game,
            cards=tuple(numbered),
            distinct_keys=tuple(sorted(keys)),
        )
    return out


class Outcome(Enum):
    DENOMINATOR_MISMATCH = "denominator_mismatch"
    MISREAD = "misread"
    SHARED_SKU = "shared_sku"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class Resolution:
    """What `resolve` found for one `Disagreement`. Never a repair, never a winner picked
    between two catalogue-real numbers.
    """

    sku: str
    outcome: Outcome
    detail: str
    #: For `Outcome.MISREAD` only: the normalized key the catalogue confirms is real.
    confirmed_key: Optional[str] = None
    #: For `Outcome.MISREAD` only: the normalized key(s) with no match in the catalogue.
    misread_keys: Tuple[str, ...] = field(default_factory=tuple)


class _MarketLike:
    """Duck-typed against `pipeline/pricehistory.py:Market` — the three calls this module
    needs, so a test can hand it a fixture without a network.
    """

    def category_id(self, product_line: str) -> int: ...  # pragma: no cover

    def group_id(self, category_id: int, set_name: str) -> int: ...  # pragma: no cover

    def products(self, category_id: int, group_id: int):  # pragma: no cover
        ...


def resolve(
    disagreement: Disagreement,
    market: _MarketLike,
    product_line_for_game,
) -> Resolution:
    """Settle one `Disagreement` against the live catalogue.

    `product_line_for_game` is a callable, `game -> Product Line cell`
    (`pipeline/games.py:get(game)["product_line"]` is the real one) — passed in rather than
    imported, so a test never needs a real game registry entry to exercise the three
    outcomes below.

    A DENOMINATOR MISMATCH NEVER REACHES THE NETWORK. It is resolved before `market` is
    touched — see the module docstring for why this needs no catalogue at all.
    """
    if disagreement.denominator_mismatch:
        return Resolution(
            sku=disagreement.sku,
            outcome=Outcome.DENOMINATOR_MISMATCH,
            detail=(
                f"the {len(disagreement.distinct_keys)} stored numbers disagree on the "
                f"denominator itself ({', '.join(disagreement.distinct_keys)}); a set has "
                "one size, so this is unambiguous without a catalogue call"
            ),
        )

    if not disagreement.set_name or not disagreement.game:
        return Resolution(
            sku=disagreement.sku,
            outcome=Outcome.UNRESOLVED,
            detail="no set name or game claim on any copy of this SKU — nothing to look "
            "the catalogue up against",
        )

    try:
        product_line = product_line_for_game(disagreement.game)
        category_id = market.category_id(product_line)
        group_id = market.group_id(category_id, disagreement.set_name)
        index = market.products(category_id, group_id)
    except Exception as exc:  # noqa: BLE001 — any catalogue failure is "cannot settle it"
        return Resolution(
            sku=disagreement.sku,
            outcome=Outcome.UNRESOLVED,
            detail=f"the catalogue could not be asked: {exc}",
        )

    real = [key for key in disagreement.distinct_keys if key in index.by_number]
    fake = [key for key in disagreement.distinct_keys if key not in index.by_number]

    if len(real) == 1 and fake:
        return Resolution(
            sku=disagreement.sku,
            outcome=Outcome.MISREAD,
            detail=(
                f"{real[0]!r} is a real product in {disagreement.set_name!r}; "
                f"{', '.join(repr(k) for k in fake)} is not — the other read(s) are "
                "misreads"
            ),
            confirmed_key=real[0],
            misread_keys=tuple(fake),
        )
    if len(real) >= 2:
        return Resolution(
            sku=disagreement.sku,
            outcome=Outcome.SHARED_SKU,
            detail=(
                f"{', '.join(repr(k) for k in real)} are ALL real, distinct products in "
                f"{disagreement.set_name!r} — the numbers are fine and this SKU is shared "
                "between two different cards"
            ),
        )
    return Resolution(
        sku=disagreement.sku,
        outcome=Outcome.UNRESOLVED,
        detail=(
            f"none of {', '.join(repr(k) for k in disagreement.distinct_keys)} matches a "
            f"product the catalogue lists for {disagreement.set_name!r} — this check "
            "refuses to pick a winner"
        ),
    )
