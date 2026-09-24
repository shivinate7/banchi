"""Which queue a card lands in — batch script v2 §5.4.

The variant ladder (D3) decides *which row* a card is. This module decides *whether that
answer is trusted enough to list*, which is a different question and is answered after the
ladder has had its say.

Confidence is the only signal that a card was guessed at. Nothing downstream can catch a
misread collector number: `026/198` read as `025/198` is still a valid number that joins to
a real row, prices cleanly, and ships the wrong card to a buyer. So a low-confidence read
is not a resolution problem to be fixed later — it is the one moment the pipeline knows
something might be wrong, and it has to act on it there.

Four destinations, not two:

  LISTED           resolved, and trusted. Goes in the import file.
  MAIN             the standing review queue. A human looks at the photo.
  PARKED           the standing low-value queue. Not listed, not dropped, and deliberately
                   NOT in the main queue: an unidentifiable 15-cent card may never be worth
                   a tap, and mixing it in with the $12 ones is how the $12 ones get missed.
  NO_MARKET_DATA   matched, but the catalog row carries a blank or $0.00 market price.
                   Not a queue and not sub-threshold — it is a price to be entered by hand
                   on #/pricing (inventory/prices.json). D9: a missing price is an unknown
                   price.

The main/parked cut is made on PRICE, and on the cheapest candidate when nothing resolved —
cheapest, because that is the price the card is worth *at least*, and routing on the
optimistic end of a range would park cards that might be valuable.

An unpriced card sorts LAST in the main queue but is never parked. No price is not a low
price; a misread secret rare is exactly this case.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Sequence

from pipeline import pricing

# Destinations.
LISTED = "listed"
MAIN = "review"
PARKED = "parked"
NO_MARKET_DATA = "no_market_data"

# Routing reasons that are NOT ladder reasons (those come from `variant`, unchanged, so the
# queue can be triaged by the same strings D3 already defines).
LOW_CONFIDENCE = "low_confidence"
NO_POSITION = "no_position"
IDENTIFICATION_FAILED = "identification_failed"
SET_AMBIGUOUS = "set_ambiguous"
CARD_NOT_DETECTED = "card_not_detected"
# D35 — the collector number could not be read, and the card's row was found by its name
# inside the set the operator declared. Emitted by `join_batch`, the same way and for the
# same reason as `SET_AMBIGUOUS` directly above: both are facts about HOW the catalog row was
# reached, which is the catalog's question and not the finish ladder's.
#
# IT IS A REVIEW REASON ON A CARD THAT RESOLVED, and what is unique about it is that the JOIN
# writes it OVER a successful ladder resolution — `low_confidence` and `no_market_data` also sit
# on resolved cards, but they reach `routing.route` still resolved and are re-routed there,
# where this one arrives already un-resolved. That is the whole of D35. The ladder really did pick one row and the entry really does carry it —
# the card is queued anyway, because a row reached without its number is a row a human should
# see beside the photograph before it is listed. What that costs is one press, not one press
# per card: every such entry offers exactly one candidate under one shared reason, which is
# precisely D29's group-answer eligibility.
NUMBER_UNREAD_NAME_MATCHED = "number_unread_name_matched"
# THE CROSS-CHECK RUN THE OTHER WAY: the number found rows, and the NAME the model read off
# the same photograph matches none of them. Emitted by `join_batch` over a resolution the
# ladder completed, exactly as `NUMBER_UNREAD_NAME_MATCHED` directly above is, and for the
# same reason — it is a fact about how well the catalog row FITS the card, which is the
# catalog's question and not the finish ladder's.
#
# IT IS THE OTHER HALF OF THE RARITY RELEASE AND MUST NOT SHIP WITHOUT IT. The ladder now
# lets a contradicting rarity claim go when the name agrees; on its own that only makes the
# pipeline quieter, in both directions. The claim was never only refusing right cards — it
# was also WAVING WRONG ONES THROUGH whenever the wrong card's rows happened to satisfy it.
# Card `1/51` on the owner's store: read `Irelia, Blade Dancer`, number `190/221`, which in
# that export is `Forgefire Cape` — `Epic`, which is precisely what the operator claimed, so
# nothing was flagged and no queue entry was ever written. Nine box-1 cards are that shape.
#
# A number a confident model got wrong lands on a REAL row for another card, which is the
# failure no confidence threshold fires on and the one D23 was written for. The name is the
# only other thing read off that photograph, so it is the only thing that can contradict it.
NAME_DISPUTED = "name_disputed"

# `docs/specs/identity-follows-sku.md` §7.3, lane 2: the migration's own review reason, for
# a HELD card (`identity_source = read`, a SKU the read disputes on name or on number, §3.1)
# that is IDENTIFIED rather than sold. `./pkmnscan cards identity --write` opens the entry
# directly, through `store/queues.py:Queue.upsert` — never through `route()` above, which is
# the join's own reasoning and has nothing to say about a card the migration is looking at
# long after the join ran. Label on screen, `app/src/ReviewQueue.tsx`'s own `QUESTIONS` map
# (§7.3's exact words): "Is the listing the right card?"
#
# DELIBERATELY NOT IN `ROUTING_REASONS` BELOW. That tuple is `route()`'s own emitted
# vocabulary, reconciled against `app/src/reasons.ts` and `docs/DESIGN.md` by `make
# docs-audit`'s `reason codes`/`reason emissions` rows — neither file is lane 2's to touch
# (see the lane's own fence). A reason outside the roster still renders: `#/review`'s
# `reasonLabel` falls back to the raw string exactly as it does for any code `reasons.ts`
# has not labelled yet (`app/src/reasons.ts`'s own docstring: "an unknown code renders as
# itself... so a reason added to the pipeline shows up here as a plain string rather than a
# blank line"). Wiring this into the roster, `reasons.ts` and `docs/DESIGN.md` is real work
# a later lane owns.
LISTING_DISPUTED = "listing_disputed"

# ROUTING'S OWN REVIEW REASONS, PUBLISHED AS A SET. The ladder's six live in
# `pipeline/variant.py:LADDER_REASONS`; together the two tuples are the whole vocabulary, and
# the split is the same one docs/DESIGN.md credits each reason by.
#
# `NO_MARKET_DATA` is in here and is ALSO a destination, which is why no rule over this file's
# layout could have derived this list: it is declared under the `# Destinations.` heading at
# the top, four lines above constants that are destinations and nothing else. A reader keying
# off the comment blocks gets it wrong; so does one keying off the name, the case, or the
# value's shape. See `variant.LADDER_REASONS` for the argument in full.
ROUTING_REASONS = (
    LOW_CONFIDENCE,
    NO_POSITION,
    IDENTIFICATION_FAILED,
    SET_AMBIGUOUS,
    CARD_NOT_DETECTED,
    NUMBER_UNREAD_NAME_MATCHED,
    NAME_DISPUTED,
    NO_MARKET_DATA,
)

# Hard failures: no usable answer at all, so no price can be reasoned about. Always main,
# always sorted last.
UNPRICEABLE_REASONS = (NO_POSITION, IDENTIFICATION_FAILED)

# The one runtime assertion worth writing here, and it is about the SUBSET rather than the
# roster: a tuple built from the constants beside it cannot disagree with them, but a later
# edit adding something to `UNPRICEABLE_REASONS` that is not a reason at all would be a real
# error and a silent one — `route()` tests membership of it per card.
assert set(UNPRICEABLE_REASONS) <= set(ROUTING_REASONS), (
    "UNPRICEABLE_REASONS must be a subset of ROUTING_REASONS"
)

# `--review-below-confidence`. `none` restores "confidence never routes on its own".
CONFIDENCE_NONE = "none"
CONFIDENCE_LOW = "low"
CONFIDENCE_MEDIUM = "medium"
REVIEW_BELOW_CHOICES = (CONFIDENCE_NONE, CONFIDENCE_LOW, CONFIDENCE_MEDIUM)

# Weakest first. A card routes when its confidence is at or below the configured level.
_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


class UnknownConfidenceGate(ValueError):
    """`--review-below-confidence` outside none | low | medium."""


def check_review_below(level: str) -> str:
    if level not in REVIEW_BELOW_CHOICES:
        raise UnknownConfidenceGate(
            "{0!r} not in {1}".format(level, REVIEW_BELOW_CHOICES)
        )
    return level


def confidence_routes(confidence: Optional[str], review_below: str = CONFIDENCE_LOW) -> bool:
    """Does this confidence level, on its own, send a resolved card to a queue?"""
    check_review_below(review_below)
    if review_below == CONFIDENCE_NONE or confidence is None:
        return False
    rank = _CONFIDENCE_RANK.get(confidence)
    if rank is None:
        return False
    return rank <= _CONFIDENCE_RANK[review_below]


@dataclass(frozen=True)
class Destination:
    """Where one card goes, and the price that decided it."""

    queue: str
    reason: str
    price: Optional[Decimal] = None

    @property
    def listed(self) -> bool:
        return self.queue == LISTED

    @property
    def unpriced(self) -> bool:
        return self.price is None

    @property
    def sort_key(self):
        """Main-queue order: priced first, descending by price; unpriced last.

        Tuple ordering does the work — `(0, -price)` sorts every priced card ahead of every
        `(1, 0)` unpriced one, and the negation puts the expensive end first. You work the
        known-valuable cards first, and nothing is hidden behind them.
        """
        if self.price is None:
            return (1, Decimal("0"))
        return (0, -self.price)

    @property
    def describe(self) -> str:
        money = "unpriced" if self.price is None else "${0}".format(self.price)
        return "{0} ({1}, {2})".format(self.queue, self.reason, money)


def cheapest(prices: Sequence[Optional[Decimal]]) -> Optional[Decimal]:
    """Lowest real market price among candidate rows, or None if none carries one."""
    real = [p for p in prices if pricing.has_market_data(p)]
    return min(real) if real else None


def _by_price(
    price: Optional[Decimal], reason: str, threshold: Decimal
) -> Destination:
    """The main/parked cut. No price means main, sorted last — never parked."""
    if price is None:
        return Destination(queue=MAIN, reason=reason, price=None)
    if price >= threshold:
        return Destination(queue=MAIN, reason=reason, price=price)
    return Destination(queue=PARKED, reason=reason, price=price)


def route(
    *,
    resolved: bool,
    reason: str,
    confidence: Optional[str] = None,
    price: Optional[Decimal] = None,
    candidate_prices: Sequence[Optional[Decimal]] = (),
    threshold: Decimal = pricing.THRESHOLD,
    review_below: str = CONFIDENCE_LOW,
) -> Destination:
    """Route one card.

    `price` is the resolved row's market price (None when nothing resolved, or when the
    cell is blank). `candidate_prices` are the market prices of the rows the card *could*
    have been, consulted only when nothing resolved.
    """
    check_review_below(review_below)

    # 1. No usable answer at all. There is nothing to price and nothing to compare.
    if reason in UNPRICEABLE_REASONS:
        return Destination(queue=MAIN, reason=reason, price=None)

    # 2. The ladder or the catalog sent it to review. Cut on the cheapest thing it could be.
    if not resolved:
        return _by_price(cheapest(candidate_prices), reason, threshold)

    # 3. Resolved, but the read itself is suspect. Checked BEFORE no-market-data: a
    #    low-confidence read of a row with no price is the misread-secret-rare case, and
    #    that belongs in front of a human, not in a file waiting for a hand-typed price.
    if confidence_routes(confidence, review_below):
        return _by_price(
            price if pricing.has_market_data(price) else None, LOW_CONFIDENCE, threshold
        )

    # 4. Resolved and trusted, but the catalog has no price for it.
    if not pricing.has_market_data(price):
        return Destination(queue=NO_MARKET_DATA, reason=NO_MARKET_DATA, price=None)

    # 5. Listed.
    return Destination(queue=LISTED, reason=LISTED, price=price)
