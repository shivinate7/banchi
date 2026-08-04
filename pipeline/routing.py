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
                   in decisions.json. D9: a missing price is an unknown price.

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

# Hard failures: no usable answer at all, so no price can be reasoned about. Always main,
# always sorted last.
UNPRICEABLE_REASONS = (NO_POSITION, IDENTIFICATION_FAILED)

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
