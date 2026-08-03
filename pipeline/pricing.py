"""D9 — threshold and floor, both $0.40.

Both derived from the $60/hr labor bar: a marginal pull is ~20s, and 0.8675 x $0.40
clears it. Both configurable; neither is a magic number to be nudged by feel.

  threshold  market >= $0.40 earns a listing. Below it the card exits through
             TCGplayer's native Bulk Lots category, not this pipeline.
  floor      listed price = max(pricing-rule output, $0.40) — clamps undercut rules in a
             collapsing market.

Only the `match` rule is wired. Undercut % and markup % are build-order step 4, and are
deliberately absent rather than stubbed: a rule that silently returns market price while
claiming to undercut is worse than one that does not exist.

Sub-threshold cards are NOT disposed of by this module. What happens to a $0.03 card is a
per-run decision by the owner, not a constant here — see `Disposition` and
`join.emit_import`, which refuses to write until that decision has been made.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

THRESHOLD = Decimal("0.40")
FLOOR = Decimal("0.40")

RULE_MATCH = "match"


def is_listable(market_price: Optional[Decimal], threshold: Decimal = THRESHOLD) -> bool:
    if market_price is None:
        return False
    return market_price >= threshold


def list_price(
    market_price: Decimal,
    rule: str = RULE_MATCH,
    floor: Decimal = FLOOR,
) -> Decimal:
    if rule != RULE_MATCH:
        raise NotImplementedError(f"pricing rule {rule!r} is build-order step 4")
    return max(market_price, floor)


# ------------------------------------------------------- sub-threshold dispositions


class BelowFloor(ValueError):
    """A flat price under the floor, without saying so on purpose."""


FLAT_FLOOR = "flat_floor"
FLAT_PRICE = "flat_price"


@dataclass(frozen=True)
class Disposition:
    """What to do with a card the D9 threshold says is not worth listing at market.

    Two kinds, both of which list the card:

      flat_floor   every sub-threshold card at the floor, whatever its market price
      flat_price   a number chosen for this run

    Bulk Lots is not a kind here. Which cards go to a bulk lot is a decision made later,
    against the price distribution the join preserves (`join.SubThresholdBucket.bands`) —
    not a bucket this pipeline sorts into blindly at emit time.
    """

    kind: str
    price: Optional[Decimal] = None

    def resolve(self, floor: Decimal = FLOOR) -> Decimal:
        if self.kind == FLAT_FLOOR:
            return floor
        if self.kind == FLAT_PRICE:
            return self.price
        raise ValueError(f"unknown disposition kind: {self.kind!r}")

    @property
    def describe(self) -> str:
        if self.kind == FLAT_FLOOR:
            return f"flat at the ${FLOOR} floor"
        return f"flat at ${self.price}"


def flat_floor() -> Disposition:
    return Disposition(kind=FLAT_FLOOR)


def flat_price(price, allow_below_floor: bool = False, floor: Decimal = FLOOR) -> Disposition:
    price = price if isinstance(price, Decimal) else Decimal(str(price))
    if price < floor and not allow_below_floor:
        raise BelowFloor(
            f"${price} is under the ${floor} floor, where a sale loses money including "
            f"labor. Pass allow_below_floor=True to mean it."
        )
    return Disposition(kind=FLAT_PRICE, price=price)
