"""D9 — threshold and floor, both $0.40.

Both derived from the $60/hr labor bar: a marginal pull is ~20s, and 0.8675 x $0.40
clears it. Both configurable; neither is a magic number to be nudged by feel.

  threshold  market >= $0.40 earns a listing. Below it the card exits through
             TCGplayer's native Bulk Lots category, not this pipeline.
  floor      listed price = max(pricing-rule output, $0.40) — clamps undercut rules in a
             collapsing market.

Three rules: `match`, `undercut:PCT`, `markup:PCT`. Two bases: `market` (default) and
`low`. Order of operations is fixed and is the reason `list_price` exists as a function
rather than as an expression at each call site:

    price = clamp_floor( round_2dp_half_up( rule(basis_price) ) )

Rounding BEFORE the clamp, never after. The other order lets a rule land at $0.398, clamp
to the floor, and then round back down under it — a floor that rounding can step over is
not a floor.

Basis default is Market — the recent actual-sale average — so an undercut prices below the
going rate instead of chasing one desperate seller. `low` switches to `TCG Low Price` for a
box you want gone. The THRESHOLD check ignores the basis entirely and always reads Market:
D9 says market >= $0.40 earns a listing, which is a statement about a card's value, not
about this run's pricing strategy.

A blank or $0.00 market price is `no_market_data` (D9), which is not the same as cheap.
`has_market_data` is the predicate; nothing in this module prices such a row, and nothing
sweeps it into the sub-threshold bucket. A missing price is an unknown price.

Sub-threshold cards are NOT disposed of by this module either. What happens to a $0.03 card
is a per-run decision by the owner, not a constant here — see `Disposition`, and
`pipeline.decisions`, which holds that choice as a file so the step 7 screen edits the same
contract the CLI does.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from pipeline import tcgcsv

THRESHOLD = Decimal("0.40")
FLOOR = Decimal("0.40")

CENT = Decimal("0.01")

# ------------------------------------------------------------------------------ rules

RULE_MATCH = "match"
RULE_UNDERCUT = "undercut"
RULE_MARKUP = "markup"
RULES = (RULE_MATCH, RULE_UNDERCUT, RULE_MARKUP)


class UnknownRule(ValueError):
    """A rule string outside the enum. Never coerced — a rule that silently becomes
    `match` while claiming to undercut is worse than one that fails."""


class UnknownBasis(ValueError):
    """A basis outside `market` | `low`."""


@dataclass(frozen=True)
class Rule:
    """One pricing rule. `percent` is a whole-number percentage: 5 means 5%."""

    kind: str = RULE_MATCH
    percent: Decimal = Decimal("0")

    @classmethod
    def parse(cls, text) -> "Rule":
        """`match`, `undercut:5`, `markup:12.5`. The spelling `inventory/prices.json`'s policy uses."""
        if isinstance(text, Rule):
            return text
        raw = str(text).strip().lower()
        kind, _, percent = raw.partition(":")
        if kind not in RULES:
            raise UnknownRule("{0!r} not in {1}".format(raw, RULES))
        if kind == RULE_MATCH:
            if percent:
                raise UnknownRule("`match` takes no percentage, got {0!r}".format(raw))
            return cls(kind=RULE_MATCH)
        if not percent:
            raise UnknownRule(
                "{0} needs a percentage, e.g. {0}:5".format(kind)
            )
        try:
            value = Decimal(percent)
        except Exception as exc:
            raise UnknownRule("{0!r} is not a percentage".format(percent)) from exc
        if value < 0:
            raise UnknownRule(
                "a negative percentage inverts the rule — use the other one, not {0!r}".format(raw)
            )
        if kind == RULE_UNDERCUT and value >= 100:
            raise UnknownRule("undercut:{0} prices at or below zero".format(value))
        return cls(kind=kind, percent=value)

    def apply(self, basis_price: Decimal) -> Decimal:
        """The rule's raw output. Unrounded and unclamped — `list_price` owns that order."""
        if self.kind == RULE_MATCH:
            return basis_price
        factor = self.percent / Decimal("100")
        if self.kind == RULE_UNDERCUT:
            return basis_price * (Decimal("1") - factor)
        if self.kind == RULE_MARKUP:
            return basis_price * (Decimal("1") + factor)
        raise UnknownRule("unknown rule kind: {0!r}".format(self.kind))

    @property
    def describe(self) -> str:
        if self.kind == RULE_MATCH:
            return "match the basis price"
        return "{0} {1}%".format(self.kind, self.percent)

    def __str__(self) -> str:
        if self.kind == RULE_MATCH:
            return RULE_MATCH
        return "{0}:{1}".format(self.kind, self.percent)


MATCH = Rule(kind=RULE_MATCH)

# ------------------------------------------------------------------------------ basis

BASIS_MARKET = "market"
BASIS_LOW = "low"
BASES = (BASIS_MARKET, BASIS_LOW)

# One source of truth for which column each basis reads.
BASIS_COLUMN = {
    BASIS_MARKET: tcgcsv.MARKET_PRICE_COLUMN,
    BASIS_LOW: tcgcsv.LOW_PRICE_COLUMN,
}


def check_basis(basis: str) -> str:
    if basis not in BASES:
        raise UnknownBasis("{0!r} not in {1}".format(basis, BASES))
    return basis


def basis_price(row: tcgcsv.Row, basis: str = BASIS_MARKET) -> Optional[Decimal]:
    """The price this run's rule is applied to. None when the cell is blank."""
    return tcgcsv.parse_price(row[BASIS_COLUMN[check_basis(basis)]])


def market_price(row: tcgcsv.Row) -> Optional[Decimal]:
    """What the THRESHOLD always reads, whatever `--basis` says. D9 is about value."""
    return tcgcsv.parse_price(row[tcgcsv.MARKET_PRICE_COLUMN])


# ------------------------------------------------------------------- threshold + floor


def has_market_data(price: Optional[Decimal]) -> bool:
    """A blank or $0.00 market cell is an UNKNOWN price, not a low one (D9).

    Separate from `is_listable` on purpose: both answer False, for opposite reasons, and
    collapsing them is what sweeps a chase card into the $0.40 flat bucket.
    """
    return price is not None and price > 0


def is_listable(market_price: Optional[Decimal], threshold: Decimal = THRESHOLD) -> bool:
    if not has_market_data(market_price):
        return False
    return market_price >= threshold


def round_money(value: Decimal) -> Decimal:
    """Two decimals, half up. Money is never a float."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def clamp_floor(value: Decimal, floor: Decimal = FLOOR) -> Decimal:
    return max(value, floor)


def list_price(
    price: Decimal,
    rule=MATCH,
    floor: Decimal = FLOOR,
) -> Decimal:
    """`clamp_floor(round(rule(basis)))` — in that order, so rounding cannot cross the floor.

    `price` is the BASIS price, which is Market by default and Low under `--basis=low`.
    The threshold decision was made before this was called, and made against Market.
    """
    return clamp_floor(round_money(Rule.parse(rule).apply(Decimal(price))), floor)


# The answer a `no_market_data` SKU gets when the decision is to not list it. A real
# decision with a name, so that "left out of the file" is distinguishable in the record
# from "nobody has looked at it yet" — which is the only reason `emit` can refuse on one
# and not the other.
UNLISTED = "unlisted"


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
