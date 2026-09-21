"""One SKU, two stored numbers — the SKU self-contradiction check kept apart from
`pipeline/identity_checks.py` on the owner's own ruling: *"keep the more speculative
contradiction rate as a separate thing from the four approved checks."*

THE FINDING THIS ANSWERS. A SKU is one product in one condition. There is no legitimate
reason for two copies of it to read a different card number. Measured against the owner's
real store: 150 of 881 SKUs with a number disagree, after normalizing through
`store.numbers.strip_set_code` and `pipeline.join.number_index_key`. This module needs no
catalogue to FIND that — the store already contradicts itself.

THE TEST IS NAME-AGREEMENT, NOT MERE EXISTENCE, AND THAT IS AN AMENDMENT OVER THIS
MODULE'S FIRST SHAPE. The first version asked only "does a real product carry this
number?" That test is vacuous in a dense set: measured on Vendetta, 258 products cover
100% of numbers 1 through 166, so every candidate number always resolves to SOME real
product, and the check reported `shared_sku` for what was almost always a plain misread.
The owner's correction: this store already holds the card's NAME on every copy, so ask
whether a candidate number's product is ALSO named what this card is stored as. Measured
against the real store and the live catalogue, over the 144 disagreeing Riftbound SKUs: the
stored name settles exactly one of the competing numbers in 131 of them. 13 are not settled
by the name at all.

THREE OUTCOMES, NEVER COLLAPSED INTO ONE. For each candidate normalized number, this asks
whether the catalogue's own product at that number carries a name matching (by
`pipeline.join.name_index_key`) the stored name of the card(s) that read it:

  - The name settles exactly one candidate -> `Outcome.MISREAD`. The settled number is
    named `confirmed_key`; the rest are misreads. **This is not the machine guessing an
    identification, which `CLAUDE.md` forbids.** It is the machine reporting an agreement
    between three sources it did not invent: two independent stored reads (this SKU's own
    copies) and the catalogue's own record that this specific name belongs to this
    specific number. A guess picks the more plausible of two options it cannot verify; this
    picks the only option a third, independent source already confirms.
  - The name settles MORE THAN ONE candidate -> `Outcome.SHARED_SKU`. Two different,
    correctly-numbered, correctly-named products share one SKU. The numbers are both fine;
    the defect is the SKU.
  - The name settles NONE of the candidates -> `Outcome.UNRESOLVED`. This module refuses to
    pick a winner. Routed to a human.

A DISAGREEMENT ON THE DENOMINATOR ITSELF NEEDS NO CATALOGUE CALL AT ALL. A set has one
size. `134/166` against `134/266` cannot both be the same product's printed total, so this
class is reported as `Outcome.DENOMINATOR_MISMATCH` without ever building a `Market`. This
is the bulk of the store's own finding — 101 of the 150 disagreeing SKUs, measured — and it
is the one class this module can call unambiguous on stored data alone.

`Market.products(category_id, group_id)` answers a whole group in one cached request, so
resolving many SKUs in one set costs one request, not one per SKU.

REPORTS BOTH DIRECTIONS AND PICKS NO WINNER OUTSIDE THE ONE-MATCH CASE. `resolve` never
writes a card, and never queues anything — the queue has nowhere to put a card that was
already answered: `store/queues.py:Queue.upsert` refuses to re-queue a position already
`cleared_by_human` (D167). It returns a `Resolution` a human, or a future caller, decides
what to do with. Proposing the correct number is as far as this module goes — a repair is a
separate press and a separate decision, and nothing here performs one.

Cites D146 (two agreeing signals release a claim; here, three sources — two stored reads
and the catalogue's own name record — agree, which is stronger than the two D146 asks
for), D173, D167, and the four approved stored-data checks built as a separate, sibling PR.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from pipeline.join import name_index_key, number_index_key
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
    """One card's stored number and name, and enough to resolve it against a catalogue
    group. `name` is what THIS PHYSICAL COPY read, not a SKU-level fact — two copies of one
    SKU can carry slightly different name reads even when their numbers agree, which is why
    the name test below is asked per candidate NUMBER, over every name any copy carrying
    that number stored, rather than once for the whole SKU.
    """

    key: str
    number: Optional[str]
    name: Optional[str] = None
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

    def names_for_key(self, key: str) -> Set[str]:
        """Every distinct stored name (folded) any copy carrying this candidate number
        read. A SKU can hold more than one such copy, and the check must ask about all of
        them — one copy's own name is the specific fact being tested against the
        catalogue's record for that number.
        """
        return {
            name_index_key(card.name)
            for card in self.cards
            if normalize_number(card.number) == key and (card.name or "").strip()
        }


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
    outside the one-name-match case `Outcome.MISREAD` names explicitly.
    """

    sku: str
    outcome: Outcome
    detail: str
    #: For `Outcome.MISREAD` only: the normalized key the name confirms.
    confirmed_key: Optional[str] = None
    #: For `Outcome.MISREAD` only: the normalized key(s) the name does not confirm.
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
    """Settle one `Disagreement` against the live catalogue, by NAME agreement.

    `product_line_for_game` is a callable, `game -> Product Line cell`
    (`pipeline/games.py:get(game)["product_line"]` is the real one) — passed in rather than
    imported, so a test never needs a real game registry entry to exercise the outcomes
    below.

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

    # NAME AGREEMENT, NOT MERE EXISTENCE. `index.by_number[key]` names every productId the
    # catalogue carries at this number; `index.by_name[name]` names every productId it
    # carries under this name. A candidate is CONFIRMED only when the two intersect — the
    # catalogue's own record that THIS number belongs to THIS name, not just that the
    # number exists at all.
    confirmed = []
    for key in disagreement.distinct_keys:
        number_hits = set(index.by_number.get(key, ()))
        if not number_hits:
            continue
        names = disagreement.names_for_key(key)
        name_hits: Set[int] = set()
        for name in names:
            name_hits |= set(index.by_name.get(name, ()))
        if number_hits & name_hits:
            confirmed.append(key)

    if len(confirmed) == 1:
        misread = tuple(k for k in disagreement.distinct_keys if k != confirmed[0])
        return Resolution(
            sku=disagreement.sku,
            outcome=Outcome.MISREAD,
            detail=(
                f"{confirmed[0]!r} is the only candidate whose catalogue product is named "
                f"what this card's own stored name reads — two stored reads and the "
                f"catalogue's own name record agree. {', '.join(repr(k) for k in misread)} "
                "the other read(s), do not match any product carrying this card's name at "
                "that number and are misreads"
            ),
            confirmed_key=confirmed[0],
            misread_keys=misread,
        )
    if len(confirmed) >= 2:
        return Resolution(
            sku=disagreement.sku,
            outcome=Outcome.SHARED_SKU,
            detail=(
                f"{', '.join(repr(k) for k in confirmed)} each carry a product whose name "
                "matches what a copy of this SKU stored — two different, correctly-read "
                f"products in {disagreement.set_name!r} share this one SKU"
            ),
        )
    return Resolution(
        sku=disagreement.sku,
        outcome=Outcome.UNRESOLVED,
        detail=(
            f"none of {', '.join(repr(k) for k in disagreement.distinct_keys)} carries a "
            f"product named what any copy of this SKU stored, in "
            f"{disagreement.set_name!r} — the name does not settle it and this check "
            "refuses to pick a winner"
        ),
    )
