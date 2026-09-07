"""D9 — threshold and floor, both $0.40.

Both derived from the $60/hr labor bar: a marginal pull is ~20s, and 0.8675 x $0.40
clears it. Both configurable; neither is a magic number to be nudged by feel.

  threshold  market >= $0.40 earns a listing. Below it the card exits through
             TCGplayer's native Bulk Lots category, not this pipeline. THE CONSTANT
             BELOW IS THE DEFAULT AND NOT THE ANSWER: the figure in force is
             `pipeline/corpus.py`'s `policy.threshold`, set by the operator on
             `#/pricing`, validated by `check_threshold` and threaded to every partition
             through `SkuMatch.threshold`. A store that has never set one reads this.
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
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Optional

from pipeline import tcgcsv

THRESHOLD = Decimal("0.40")

# THE LIVE CAP'S DEFAULT, HERE BECAUSE BOTH `join` AND `corpus` IMPORT THIS MODULE AND
# NEITHER IMPORTS THE OTHER. D7: "Live quantity caps at 4 per SKU (a playset; CONFIGURABLE)
# regardless of copies owned" — it blocks an envelope-buster order, and it bounds how many
# copies a price spike can sell at a stale price. `pipeline/join.py` re-exports it under the
# name every caller and 218 lines of documentation already use, so this is where the figure
# lives and `join.LIVE_QUANTITY_CAP` is still how it is spelled.
#
# CONFIGURABLE SINCE 2026-09-06, WHICH D7 PROMISED AND NOTHING BUILT. The parameter was
# threaded through `SkuMatch`, `join` and `resolve.load` from the start and no caller ever
# passed anything but this default: no flag set it, no policy key held it, and
# `server/pipeline_routes.py` read the module constant directly in three places.
LIVE_QUANTITY_CAP = 4

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


class InvalidThreshold(ValueError):
    """A stored threshold that is not money.

    A `ValueError` and NOT a `MalformedDecisions`, exactly as `UnknownRule` and
    `UnknownBasis` are, because it is raised from the same place for the same reason:
    `pipeline/corpus.py:parse` validates the policy at READ time so the refusal lands where
    a command is already catching it, rather than in the middle of an `emit` an hour later.
    The message names the value, because a threshold nobody can see is a threshold nobody
    can correct."""


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


def check_threshold(value) -> Decimal:
    """A stored threshold as a `Decimal`, or a refusal naming what was written.

    `check_basis`'s shape, for `check_basis`'s reason: the policy is validated where it is
    read, and the caller gets back the parsed value rather than the string it was stored as.

    THE CONSTANT IS THE DEFAULT AND NOT THE ONLY ANSWER (D9: *"both configurable"*). What is
    validated is that the figure is MONEY and is positive: a threshold of zero lists a $0.00
    card, and a negative one is not a number anybody meant. `None` is the store that has
    never set one, which is every store written before this — it reads the constant, so the
    partition it produces is byte-identical to the one it produced yesterday.

    IT DOES NOT ROUND. A threshold of `0.405` is a boundary the operator typed and is
    compared against Market as written; rounding it here would move a decision by a cent
    without saying so, which is the failure `list_price` orders its own operations to avoid.
    """
    if value is None:
        return THRESHOLD
    text = str(value).strip()
    try:
        parsed = Decimal(text)
    except (ArithmeticError, InvalidOperation, ValueError) as exc:
        raise InvalidThreshold(
            "threshold {0!r} is not a price".format(text)
        ) from exc
    if not parsed.is_finite() or parsed <= 0:
        raise InvalidThreshold(
            "threshold {0!r} must be above zero".format(text)
        )
    return parsed


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


# The three presets the pricing screen offers, priced HERE so this module runs once and in
# Python (D49). The owner picked these three and their numbers in an interview: match market,
# undercut market by 5, undercut TCG Low by 1. A fourth is a change to this tuple and to
# `app/src/Pricing.tsx`'s labels, and to nothing else.
#
# THE CLIENT PERFORMS NO ARITHMETIC ON MONEY, WHICH IS WHAT THIS TUPLE BUYS. Re-implementing
# `Rule.apply` + `round_money` + `clamp_floor` in TypeScript would put the rounding-before-
# clamping order in two languages with nothing auditing the second, and that order is the whole
# reason `list_price` is a function rather than an expression.
#
# HERE RATHER THAN IN `cli/cmd_join.py`, WHICH IS WHERE IT LIVED UNTIL 2026-09-07. Two callers
# need it now — a run's `pricing.json` and a markdown's `survey.json` — and the second was
# shipping `presets: {}`, so every preset button on the lens filled nothing while still writing
# the store's standing rule. One copy of the arithmetic, or the two doors drift.
PRESETS = (
    ("market_match", RULE_MATCH, BASIS_MARKET),
    ("market_undercut_5", "undercut:5", BASIS_MARKET),
    ("low_undercut_1", "undercut:1", BASIS_LOW),
)


def preset_prices(row) -> dict:
    """What each named preset would list this export row at, keyed by preset name.

    TAKES THE EXPORT ROW AND NOTHING ELSE, which is what lets a run and a lens share it: a
    run has a `SkuMatch` and a lens has a survey entry, and the only thing both carry is the
    verbatim row.

    `None` IS A REAL ANSWER AND NOT AN ERROR. Measured on the wide Pokemon export, 394 of
    2,476 listable rows carry a blank `TCG Low Price`, so a Low-based preset genuinely has
    nothing to price them from. The screen prices what it can, leaves the rest, and says
    which (the owner's ruling).
    """
    out = {}
    for name, rule, basis in PRESETS:
        column = tcgcsv.MARKET_PRICE_COLUMN if basis == BASIS_MARKET else tcgcsv.LOW_PRICE_COLUMN
        basis_price = tcgcsv.parse_price(row.get(column, ""))
        out[name] = (
            None
            if basis_price is None or basis_price <= 0
            else str(list_price(basis_price, rule=Rule.parse(rule)))
        )
    return out
