"""The TCGplayer Export Shipping CSV, and the lane an order belongs in.

Two things, and the second is the only one that decides anything. `read_shipping` parses
the 17-column export `docs/specs/shipping-export.md` documents; `route` answers which of
three lanes one order ships in, or refuses to answer.

THERE ARE THREE LANES, NOT A $50 LINE, and the middle one is the whole reason this is a
router rather than a comparison:

    < $50, all cards          tcgtracking IMb envelope     LANE_ENVELOPE
    < $50, contains non-card  Pirate Ship parcel           LANE_PARCEL
    >= $50                    Pirate Ship parcel           LANE_PARCEL

A playmat cannot go in an envelope whatever it cost, and TCGplayer mandates tracking above
$49.99 whatever it weighs. Those are two independent facts about one order, so a rule
reading only the money puts a $12 sealed booster box into a stamped envelope, and a rule
reading only the contents ships a $600 single untracked.

THE TWO SIGNALS ARE NOT THE SAME STRENGTH OF CLAIM, AND THE ORDER THEY ARE ASKED IN IS THE
DIFFERENCE BETWEEN ABSTAINING ON 29% OF ORDERS AND ABSTAINING ON 12%.

  `Value Of Products` IS A FACT. It is present on all 331 rows of the fixture, it needs no
  weight, and $50 is a threshold TCGplayer publishes rather than one this project fitted.

  `Product Weight / Item Count` IS A PROXY, AND IT ABSTAINS. It is derived, not measured —
  see below — and it is missing on 97 of 331 rows.

So the value question is asked FIRST, and that is not a style preference: measured on the
fixture, **58 of the 97 weightless orders are at or over $50** and are answered with
certainty by a rule that never needed a weight. Abstention falls from 97 orders (29%) to
39 (11.8%). It also answers the single case `docs/specs/shipping-export.md` names as its
worst — "it abstains on 29% of orders, and one of them is a $1750 order". That order is
`A2FFC195-0000F4-006AC`, one item, no weight, $1750.00, and this router sends it to a
tracked parcel without consulting the proxy at all.

THE NON-CARD SIGNAL IS ALREADY DERIVED AND IS NOT RE-DERIVED HERE. `docs/specs/
shipping-export.md` measured it and the numbers are that spec's, not this module's:
`Product Weight` is a summed per-product CATALOG CONSTANT — 0.07 oz a single, 2.50 oz a
sealed product, and every mixed order is an exact combination of the two — so the ratio
proxies "does this order contain a non-single". It takes five exact values with an empty
band between 0.0700 and 1.2850, an 18.4x separation with nothing whatsoever inside it, and
the cut is 0.30, the geometric midpoint of that gap. Derived from where the distribution is
empty rather than picked, which is D19's rule about tuning from a real trace.

IT SAYS "HEAVIER THAN CARDS ALONE" AND MAY NEVER SAY "CONTAINS A PLAYMAT". Even at 18x that
is an inference, and this repo prefers refusal over inference. The reason code says
`non_card_signal` and the lane it produces is the same lane the value rule produces, so
nothing downstream needs the guess to be any sharper than it is.

EXACT RATIONAL ARITHMETIC, NEVER FLOATS, and that is a defect this project already paid
for. `docs/specs/shipping-export.md` records that a float pass "reported a phantom sub-0.07
row" on a distribution whose true minimum is exactly 0.07 — and the sub-0.07 band is
precisely where `SUB_SINGLE_WEIGHT` below abstains, so a float would manufacture the one
outcome this module treats as impossible. `Fraction` over the decimal strings is exact.

ABSTENTION IS A THIRD ANSWER AND NEVER A DEFAULT TO A LANE. `LANE_UNJUDGED` is returned,
named, and counted. Defaulting it to the envelope ships a playmat in a stamped mailer;
defaulting it to the parcel spends money on postage nobody asked for. Both are decisions,
and this module is not entitled to make either — the operator is, looking at the order.

THIS IS A PRE-LINE-DATA STOPGAP AND SHOULD BE RETIRED RATHER THAN TUNED. The export carries
no line items — no SKUs, no product names, only `Item Count`, confirmed against a real
export — which is why the weight ratio is the best signal available at all.
`pipeline/orders.py` already answers this question properly from line kinds when a feed
supplies them (`OrderResolution.ships_in_an_envelope`), and the day the Bridge lands, the
cut here is the thing to delete, not the thing to re-fit.

BUYER PII PASSES THROUGH AND IS NOT PERSISTED. `Shipment` holds a real name and a real
street address for as long as the caller holds it. Nothing here writes, caches, or reaches
`store/` — this module imports the format and the lane rule and nothing else.
"""

from __future__ import annotations

import codecs
import csv
import io
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

from pipeline import pirateship

ENCODING = "utf-8"

# The 17 columns, in order, exactly as `docs/specs/shipping-export.md` records them.
# Declared so that a changed export refuses loudly rather than being misread: a reader that
# took whatever columns it found would answer `no_weight_data` for every order on the day
# TCGplayer renamed `Product Weight`, and 331 abstentions look like a quiet afternoon.
CANONICAL_HEADER: Tuple[str, ...] = (
    "Order #",
    "FirstName",
    "LastName",
    "Address1",
    "Address2",
    "City",
    "State",
    "PostalCode",
    "Country",
    "Order Date",
    "Product Weight",
    "Shipping Method",
    "Item Count",
    "Value Of Products",
    "Shipping Fee Paid",
    "Tracking #",
    "Carrier",
)

ORDER_COLUMN = "Order #"
WEIGHT_COLUMN = "Product Weight"
ITEM_COUNT_COLUMN = "Item Count"
VALUE_COLUMN = "Value Of Products"

# STRUCTURALLY EMPTY ON ALL 331 ROWS — present and blank, not omitted. Named as constants
# rather than left as two strings nobody reads, because the temptation they create is real:
# a reader that assumed `Tracking #` carried data would find an empty string and could
# reasonably conclude the order had not shipped. It carries nothing on any row, ever, which
# is a fact about the format and not about any order. Closing that loop is what
# `pirateship.ORDER_ID_COLUMN` is for.
TRACKING_COLUMN = "Tracking #"
CARRIER_COLUMN = "Carrier"

# --------------------------------------------------------------------------- the lanes

LANE_ENVELOPE = "envelope"
LANE_PARCEL = "parcel"
LANE_UNJUDGED = "unjudged"
LANES: Tuple[str, ...] = (LANE_ENVELOPE, LANE_PARCEL, LANE_UNJUDGED)

# WHY A LANE IS NOT ENOUGH AND EVERY ANSWER CARRIES A REASON. Two orders both land in
# `parcel` — one because it is worth $600 and one because it probably holds a playmat — and
# they are a certainty and an inference. A screen that cannot tell them apart cannot show
# the operator which of its answers is worth checking.
VALUE_AT_THRESHOLD = "value_at_threshold"
NON_CARD_SIGNAL = "non_card_signal"
CARDS_ONLY = "cards_only"
NO_WEIGHT_DATA = "no_weight_data"
NO_VALUE_DATA = "no_value_data"
SUB_SINGLE_WEIGHT = "sub_single_weight"

LANE_REASONS: Tuple[str, ...] = (
    VALUE_AT_THRESHOLD,
    NON_CARD_SIGNAL,
    CARDS_ONLY,
    NO_WEIGHT_DATA,
    NO_VALUE_DATA,
    SUB_SINGLE_WEIGHT,
)

# TCGplayer mandates tracking above $49.99, so the test is `>=` against 50.00 and the
# fixture holds a row at exactly 50.00 to prove which side of the line it falls on.
TRACKING_THRESHOLD = Decimal("50.00")

# The cut, and the constant it is a midpoint above. Both are `docs/specs/shipping-export.md`
# measurements; neither is chosen here. `Fraction` rather than `Decimal` because the
# comparison is against a RATIO and a ratio of two decimals is not a decimal —
# 45.14 / 20 terminates, 115 / 86 does not, and that row is real.
NON_CARD_CUT = Fraction(3, 10)
SINGLES_WEIGHT = Fraction(7, 100)


class MalformedShipping(Exception):
    """The bytes are not the export this module contracts to read."""


# -------------------------------------------------------------------------- the reader


@dataclass(frozen=True)
class Shipment:
    """One row of the export: one order, and no line items.

    `cells` is every column verbatim, because this file is somebody else's and a reader
    that kept only what it currently uses would have to be edited before anything could ask
    a new question of it. The named accessors below are the ones the router reads.

    THE THREE NUMBERS PARSE TO `None` RATHER THAN TO ZERO, and that is the whole of the
    abstention. `Product Weight` of 0.00 is ABSENT DATA on 97 of 331 rows — including a
    $1750 order — not a light package, so a reader answering `Decimal("0")` would hand the
    router a number it would compare against a cut and get an answer for. Absent has to
    stay distinguishable from small all the way to the decision.
    """

    cells: Dict[str, str]

    @property
    def order(self) -> str:
        return self.cells.get(ORDER_COLUMN, "").strip()

    def _decimal(self, column: str) -> Optional[Decimal]:
        raw = (self.cells.get(column) or "").strip()
        if not raw:
            return None
        try:
            return Decimal(raw)
        except InvalidOperation:
            # A cell that is present and unparseable is not zero either. It abstains for
            # the same reason a blank one does, and it does it without raising: one
            # malformed cell in a 331-row export must not cost the other 330 their answer.
            return None

    @property
    def value(self) -> Optional[Decimal]:
        return self._decimal(VALUE_COLUMN)

    @property
    def weight(self) -> Optional[Decimal]:
        weight = self._decimal(WEIGHT_COLUMN)
        return None if weight is None or weight == 0 else weight

    @property
    def item_count(self) -> Optional[int]:
        raw = (self.cells.get(ITEM_COUNT_COLUMN) or "").strip()
        try:
            count = int(raw)
        except ValueError:
            return None
        return count if count > 0 else None

    @property
    def weight_per_item(self) -> Optional[Fraction]:
        """The proxy, exact. `None` when either half is absent.

        `Fraction(str)` off the raw cell rather than off a float — see the module header:
        a float pass on this very column reported a row below a minimum that is exactly
        0.07, which is the one value this module treats as a floor.
        """
        weight, count = self.weight, self.item_count
        if weight is None or count is None:
            return None
        return Fraction(str(weight)) / count


@dataclass(frozen=True)
class ShippingExport:
    header: Tuple[str, ...]
    shipments: Tuple[Shipment, ...]
    source: Optional[Path] = None

    def __iter__(self) -> Iterator[Shipment]:
        return iter(self.shipments)

    def __len__(self) -> int:
        return len(self.shipments)


def parse(data: bytes, source: Optional[Path] = None) -> ShippingExport:
    """Parse the export. Refuses a header that is not the documented 17 columns.

    LINE ENDINGS ARE NOT CHECKED, DELIBERATELY. The export is LF-terminated where the
    import CSVs are CRLF (T2), and `csv.reader` reads either — so this refuses on the thing
    that would make a reading WRONG (a column that moved) and not on the thing that would
    only make it unfamiliar. The write side is where a line ending is load-bearing, and
    this module never writes this format.
    """
    if data.startswith(codecs.BOM_UTF8):
        raise MalformedShipping("unexpected UTF-8 BOM; the real export has none")

    records = list(csv.reader(io.StringIO(data.decode(ENCODING), newline="")))
    if not records:
        raise MalformedShipping("empty file")

    header = tuple(records[0])
    if header != CANONICAL_HEADER:
        missing = [c for c in CANONICAL_HEADER if c not in header]
        extra = [c for c in header if c not in CANONICAL_HEADER]
        raise MalformedShipping(
            "not the Export Shipping header this module reads; "
            f"missing {missing}, unexpected {extra}"
        )

    shipments: List[Shipment] = []
    for lineno, record in enumerate(records[1:], start=2):
        if len(record) != len(header):
            raise MalformedShipping(
                f"line {lineno}: {len(record)} fields, header has {len(header)}"
            )
        shipments.append(Shipment(cells=dict(zip(header, record))))
    return ShippingExport(header=header, shipments=tuple(shipments), source=source)


def read_shipping(path) -> ShippingExport:
    path = Path(path)
    return parse(path.read_bytes(), source=path)


# -------------------------------------------------------------------------- the router


@dataclass(frozen=True)
class Routing:
    """Which lane one order ships in, and on what grounds."""

    order: str
    lane: str
    reason: str
    value: Optional[Decimal] = None
    weight_per_item: Optional[Fraction] = None

    @property
    def judged(self) -> bool:
        return self.lane != LANE_UNJUDGED

    @property
    def certain(self) -> bool:
        """Whether the answer rests on a fact or on the proxy.

        `value_at_threshold` reads a published price against a published threshold.
        `non_card_signal` and `cards_only` read an 18x separation and are inferences, which
        is why a screen needs to be able to tell them apart even though two of the three
        produce the same lane.
        """
        return self.reason == VALUE_AT_THRESHOLD


def route(shipment: Shipment, threshold: Decimal = TRACKING_THRESHOLD) -> Routing:
    """The lane for one order. Never raises, and never guesses.

    THE SEQUENCE IS THE DESIGN — see the module header. The fact is asked before the proxy,
    which answers 58 of the fixture's 97 weightless orders with certainty and takes
    abstention from 29% to 11.8%.
    """
    value, ratio = shipment.value, shipment.weight_per_item
    answer = lambda lane, reason: Routing(  # noqa: E731
        order=shipment.order, lane=lane, reason=reason, value=value, weight_per_item=ratio
    )

    # 1. THE FACT. Needs no weight, so it runs before anything that can abstain.
    if value is not None and value >= threshold:
        return answer(LANE_PARCEL, VALUE_AT_THRESHOLD)

    # 2. AN UNKNOWN VALUE ABSTAINS, AND IT ABSTAINS BEFORE THE PROXY IS CONSULTED. This
    #    guard was a COMMENT before it was a line of code, and T7 caught the difference: a
    #    valueless order of pure singles fell through to step 5 and read `cards_only`, which
    #    is a $600 single going out untracked in a stamped envelope. The proxy cannot rescue
    #    it — a cards-only order is exactly the shape an expensive single takes — so the
    #    weight has nothing to say about the question the threshold asks.
    #
    #    ITS OWN REASON RATHER THAN `no_weight_data`, because the two have different
    #    remedies: this one is answered by looking at what the order was worth, and that one
    #    by looking at what is in it.
    #
    #    LATENT, LIKE `sub_single_weight` BELOW. `Value Of Products` is present on all 331
    #    rows of the fixture, so no observed order reaches this. It is one comparison, and
    #    the alternative to making it is untracked postage on an order of unknown size.
    if value is None:
        return answer(LANE_UNJUDGED, NO_VALUE_DATA)

    # 3. NO PROXY TO READ. Under the threshold, and with no usable ratio to ask about the
    #    contents — the absent-is-not-zero rule, arriving at the decision intact.
    if ratio is None:
        return answer(LANE_UNJUDGED, NO_WEIGHT_DATA)

    # 4. THE PROXY'S OWN FLOOR, AND IT ABSTAINS RATHER THAN READING AS SAFE. Every catalog
    #    weight observed is at least a single's 0.07, so a summed constant divided by the
    #    item count cannot come out below it — a ratio that does means at least one product
    #    on the order carries a catalog weight lower than a card's, which is a weightless
    #    non-card and precisely the thing the proxy exists to find.
    #
    #    `docs/specs/shipping-export.md` names this as a FALSE-NEGATIVE PATH with no row in
    #    the sample: "an order of one card plus one weightless non-card reads 0.035 oz/item
    #    — BELOW the singles constant, so it would read as safer than a pure-singles order."
    #    Read as `cards_only` it is a playmat in a stamped envelope, silently. It is one
    #    comparison to turn that silence into a third answer, and an abstention is the
    #    honest one: the model does not apply, so this module has nothing to say.
    if ratio < SINGLES_WEIGHT:
        return answer(LANE_UNJUDGED, SUB_SINGLE_WEIGHT)

    # 5. THE PROXY. Strictly above the cut, so a hypothetical order landing exactly on 0.30
    #    reads as cards — the conservative side of a threshold that sits in an empty band
    #    18x wide, where nothing has ever been observed.
    if ratio > NON_CARD_CUT:
        return answer(LANE_PARCEL, NON_CARD_SIGNAL)
    return answer(LANE_ENVELOPE, CARDS_ONLY)


def route_all(
    shipments: Iterable[Shipment], threshold: Decimal = TRACKING_THRESHOLD
) -> Tuple[Routing, ...]:
    return tuple(route(shipment, threshold) for shipment in shipments)


def lane_counts(routings: Iterable[Routing]) -> Dict[str, int]:
    """How many orders landed in each lane. Every lane, including the zeros.

    Reporting only the lanes that fired would make "nothing was unjudged" and "nothing was
    checked" the same output — `pipeline/orders.py:Resolution.counts` says the same thing
    about its six reasons, for the same reason.
    """
    tally = {lane: 0 for lane in LANES}
    for routing in routings:
        tally[routing.lane] = tally.get(routing.lane, 0) + 1
    return tally


def reason_counts(routings: Iterable[Routing]) -> Dict[str, int]:
    tally = {reason: 0 for reason in LANE_REASONS}
    for routing in routings:
        tally[routing.reason] = tally.get(routing.reason, 0) + 1
    return tally


# --------------------------------------------------------------- the seam to Pirate Ship


def to_parcel(
    shipment: Shipment,
    stamps: Sequence[str] = (),
    weight: Optional[str] = None,
) -> pirateship.Parcel:
    """One export row as one import row. The only place the two formats meet.

    IT LIVES HERE AND NOT IN `pirateship.py`, WHICH IS THE ONE-WAY EDGE. That module knows
    the Pirate Ship format and nothing about TCGplayer, so it can be fed by the Bridge — or
    by anything else — without being touched. This module already reads the export, so the
    translation is cheap here and would be an import cycle the other way round. Same
    direction `store/` and `pipeline/` have, and for the same reason.

    `stamps` AND `weight` ARE THE CALLER'S AND ARE EMPTY BY DEFAULT. Neither is derivable
    from this row: the export carries no line items, so nothing here knows where a card
    sits (`pipeline/orders.py` resolves that, from SKUs this file does not have), and
    `Product Weight` is a catalog constant that under-states the parcel — see
    `pipeline/pirateship.py`'s header for why writing it costs money at the far end.

    `Order ID` IS WHAT CLOSES THE LOOP. `Tracking #` and `Carrier` are empty on all 331
    rows of the export; carrying the TCGplayer order number into Pirate Ship is what lets
    the tracking number it mints be matched back to the order that needed it.
    """
    cells = shipment.cells
    return pirateship.Parcel.from_parts(
        first_name=cells.get("FirstName", ""),
        last_name=cells.get("LastName", ""),
        address=cells.get("Address1", ""),
        address2=cells.get("Address2", ""),
        city=cells.get("City", ""),
        state=cells.get("State", ""),
        zipcode=cells.get("PostalCode", ""),
        country=cells.get("Country", ""),
        order_id=shipment.order,
        weight=weight,
        stamps=tuple(stamps),
    )


def parcel_lane(
    export: ShippingExport, threshold: Decimal = TRACKING_THRESHOLD
) -> Tuple[Tuple[Shipment, Routing], ...]:
    """Every order this router puts in the Pirate Ship lane, with the grounds for it.

    THE UNJUDGED ARE NOT IN IT, and that is the abstention arriving where it matters. An
    order nobody can place is not swept into the parcel lane to be safe — being swept in is
    a postage charge the operator did not choose, which is the same objection insurance
    gets one module over. `lane_counts` is how they are reported instead.
    """
    return tuple(
        (shipment, routing)
        for shipment, routing in zip(export.shipments, route_all(export.shipments, threshold))
        if routing.lane == LANE_PARCEL
    )
