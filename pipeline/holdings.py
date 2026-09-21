"""Unsold stock, valued at market and drawn as a series over time (`docs/specs/revenue-plan.md`
section 1, second half — the half `D225` did not build).

THE POSITION IS THE SKU (D212): every copy is fungible and no order claims one, so a card's
holding is one number — how many copies are on hand — never a list of physical slots. This
module answers two things and keeps them apart, per this feature's own rules:

  1. `on_hand_quantities` — how many copies of each SKU are still on hand, read off the
     `cards` table's own `state` column, NEVER off `Listing.live` (`store/master.py`'s own
     word for why: that count is a stale mirror until the next reconcile). The primitive
     already existed one register down — `store/master.py:Inventory.copies_on_hand` answers
     one SKU at a time; this walks the same rule once over the whole table with `Rows.select`
     rather than materializing a `Card` per row, so a store-wide series pays one query, not
     one per SKU.

  2. `sku_series` / `build_holdings_report` — that quantity multiplied through the price-
     history archive (D219, `store/pricearchive.py`), which never deletes a bucket, so it is
     the series source rather than a single live reading. Reused rather than re-derived:
     `store.pricearchive.PriceArchive.for_sku` is the one reader this module calls into that
     table with.

WHAT THIS MODULE DELIBERATELY DOES NOT DO. It does not fetch. It does not write. It does not
run `pkmnscan archive sweep`'s walk — that is `pipeline/pricearchive.py`'s job and stays a
press (D219's own statement, D62's before it: this reader cannot fire on its own). It takes
an already-loaded `Snapshot`'s `inventory`, `archive` and `ledger` and answers a pure
computation over them, so a test never needs a store on disk, only the three dataclasses this
module actually reads.

RANGES ARE NEVER MERGED (D62). Every function here is asked for exactly one
`store.pricearchive.RANGE_WIDTH_DAYS` key and answers only that range's own buckets. A caller
wanting all four ranges calls this four times; nothing in this file offers a combined answer,
because D62 forbids one existing at all.

A MISSING BUCKET BREAKS THE LINE, MADE INTO DATA RATHER THAN LEFT FOR A SCREEN TO INFER.
`pipeline/productview.py`'s existing convention passes a bucket's own `market: null` straight
through and leaves "the client breaks the line there" as a comment — correct for a single
SKU's own row, where a null is the only kind of gap that can occur (`archive.for_sku` already
returns every bucket a sweep actually wrote, in order). This module aggregates ACROSS SKUs
with independent sweep histories, so a SKU can also be missing a bucket ENTIRELY — a start
date no sweep ever recorded for it, which never appears in `archive.for_sku`'s own list at
all and so cannot be represented by a null. Both cases need one signal a test can assert on
rather than two: every `SeriesPoint` after the first in a SKU's series carries `gap_before`,
computed from the immediately preceding POINT's own `start` — true whenever the two are not
exactly one bucket-width apart, whether the buckets between them were never swept or were
swept and priced `None`. NOTHING FORWARD-FILLS OR INTERPOLATES ACROSS A GAP: a point with no
`market` costs its own row (carried so a screen can still draw the gap's extent) but
contributes no `value`, and a screen drawing a line must break it at `gap_before`.

SEALED PRODUCT IS A NAMED, COUNTABLE EXCLUSION, NEVER A SILENT DROP (the owner's ruling,
2026-09-20: "still stands — singles, stated gap"). `pipeline/pricearchive.py:ledger_subject_rows`
already found the reachability gap this counts: a SKU the order ledger has priced a line for
that the `cards` table has never recorded at all, because sealed product is never captured
(`pipeline/games.py`'s own line for it) and so has no quantity this store can count. This
module does not attempt to value that stock — it cannot, the quantity does not exist anywhere
— it only counts how many distinct such names exist, so a screen states the gap by number
rather than by a footnote nobody has to read.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional

from pipeline import tcgcsv
from store.master import TERMINAL_STATES, Inventory
from store.orders import Ledger
from store.pricearchive import Bucket, PriceArchive, RANGE_WIDTH_DAYS


def on_hand_quantities(inventory: Inventory) -> Dict[str, int]:
    """`sku -> count of copies not in a terminal state` — `Inventory.copies_on_hand`'s own
    rule (`store/master.py`), walked once over the whole `cards` table rather than once per
    SKU. A card with no SKU (never identified) contributes to no SKU's count; it is exactly
    `do_pipeline_value`'s `never_identified`/`read_nothing` population and this feature has
    nothing to value for it."""
    counts: Dict[str, int] = {}
    for _, (sku, state) in inventory.cards.select(("sku", "state")):
        sku = str(sku or "").strip()
        if not sku or state in TERMINAL_STATES:
            continue
        counts[sku] = counts.get(sku, 0) + 1
    return counts


def on_hand_names(inventory: Inventory) -> Dict[str, str]:
    """`sku -> the most recently walked on-hand copy's own name`. Display only — never a
    resolution key, and never consulted to decide what is on hand (that is `state` alone)."""
    names: Dict[str, str] = {}
    for _, (sku, state, name) in inventory.cards.select(("sku", "state", "name")):
        sku = str(sku or "").strip()
        if not sku or state in TERMINAL_STATES or not name:
            continue
        names[sku] = str(name)
    return names


def sealed_excluded_count(inventory: Inventory, ledger: Ledger) -> int:
    """How many distinct SKUs the order ledger has ever priced a line for that the `cards`
    table has NO record of at all, sold or on hand — `pipeline/pricearchive.py:
    ledger_subject_rows`'s own finding, read directly rather than through that function
    (which also resolves each one against a live catalog walk this module has no need to
    pay for; it only wants the count).

    EVERY CARD THIS STORE HAS EVER RECORDED, NOT ONLY THE ON-HAND ONES, because a SKU
    already sold is proof the `cards` table CAN name it — the gap this counts is a SKU the
    table could never have named, in any state, which is the sealed-product signature."""
    known: set = set()
    for _, (sku,) in inventory.cards.select(("sku",)):
        sku = str(sku or "").strip()
        if sku:
            known.add(sku)
    ledger_skus: set = set()
    for order in getattr(ledger, "orders", {}).values():
        for line in getattr(order, "lines", ()) or ():
            sku = str(getattr(line, "sku", "") or "").strip()
            if sku:
                ledger_skus.add(sku)
    return len(ledger_skus - known)


def _money(text: Optional[str]) -> Optional[Decimal]:
    """A bucket's own stored money string as a `Decimal`, or `None` for anything that will
    not parse — never raises, matching `server/pipeline_routes.py:_market_of`'s rule for the
    same reason: one bucket's bad cell costs that bucket's own value, not the whole series."""
    if text is None:
        return None
    try:
        return Decimal(str(text))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _adjacent(prev_start: str, start: str, width_days: int) -> bool:
    """Is `start` exactly one bucket-width after `prev_start`? Both are ISO dates
    (`store/pricearchive.py:Bucket.start`'s own format). Anything that will not parse is
    treated as NOT adjacent — a gap this module cannot read is a gap, never silently bridged."""
    try:
        prev = date.fromisoformat(prev_start)
        cur = date.fromisoformat(start)
    except ValueError:
        return False
    return cur - prev == timedelta(days=width_days)


@dataclass(frozen=True)
class SeriesPoint:
    """One SKU's one archived bucket, valued at the quantity on hand NOW. The quantity is
    never historical — this store keeps no record of how many copies were on hand on a past
    date, so every point in one SKU's series carries the SAME quantity, stated rather than
    implied to have moved with the card's own history."""

    start: str
    market: Optional[str]
    quantity: int
    value: Optional[str]
    gap_before: bool


@dataclass(frozen=True)
class SkuSeries:
    sku: str
    name: str
    quantity: int
    points: List[SeriesPoint]

    @property
    def latest_value(self) -> Optional[str]:
        """The most recent priced point's own value, or `None` when every point in this
        SKU's series carries no market at all — never a zero standing in for an absent
        price (D159's rule, inherited)."""
        for point in reversed(self.points):
            if point.value is not None:
                return point.value
        return None


def sku_series(sku: str, quantity: int, name: str, buckets: List[Bucket]) -> Optional[SkuSeries]:
    """One SKU's own series for ONE range's already-filtered, already-sorted buckets
    (`PriceArchive.for_sku` sorts ascending by `(range, start)`, so a caller that has already
    filtered to one range hands this an ascending run). `None` when there is nothing archived
    for this SKU in this range at all — the caller's own signal to count it toward
    `unmarked_count` rather than draw an empty series."""
    if not buckets:
        return None
    points: List[SeriesPoint] = []
    prev_start: Optional[str] = None
    width_days = buckets[0].width_days
    for bucket in buckets:
        market = _money(bucket.market)
        value = tcgcsv.format_price(market * quantity) if market is not None else None
        gap = prev_start is not None and not _adjacent(prev_start, bucket.start, width_days)
        points.append(
            SeriesPoint(
                start=bucket.start,
                market=bucket.market,
                quantity=quantity,
                value=value,
                gap_before=gap,
            )
        )
        prev_start = bucket.start
    return SkuSeries(sku=sku, name=name, quantity=quantity, points=points)


@dataclass(frozen=True)
class TotalPoint:
    """One calendar start's aggregate — the sum of every SKU that has a PRICED point at
    exactly this start, in this range. `priced_names` and `unpriced_names` are stated beside
    it rather than left for the total alone to imply full coverage: `priced_names` never
    equals the store's whole on-hand SKU count until the archive has swept everything, and a
    total that looked complete before then would be exactly the silent-total this repo
    refuses everywhere else (D159's rule, one register up)."""

    start: str
    value: str
    priced_names: int
    unpriced_names: int
    gap_before: bool


def aggregate_totals(series: List[SkuSeries], on_hand_count: int) -> List[TotalPoint]:
    """The portfolio's own value at every calendar start any SKU's series carries a priced
    point for, in this range. NEVER A ROLLUP FILLED FORWARD: a start where fewer SKUs have a
    price than the last start is a smaller, honestly-partial total, not a value held over
    from a SKU whose price this pass never re-read at that date.

    `width_days` for the gap test is read off whichever series is longest, since every
    `SkuSeries` handed to one call was built from the same requested range and therefore
    shares one bucket width; a caller that mixes ranges here has already broken D62's own
    rule and this function will compute a meaningless gap column rather than raise, because
    the mixing is a caller bug this module cannot see from its own arguments alone.
    """
    if not series:
        return []
    width_days = 0
    for one in series:
        if one.points:
            width_days = _bucket_width_from_series(one)
            break
    by_start: Dict[str, Decimal] = {}
    priced_by_start: Dict[str, int] = {}
    for one in series:
        for point in one.points:
            if point.value is None:
                continue
            by_start[point.start] = by_start.get(point.start, Decimal("0")) + Decimal(point.value)
            priced_by_start[point.start] = priced_by_start.get(point.start, 0) + 1
    totals: List[TotalPoint] = []
    prev_start: Optional[str] = None
    for start in sorted(by_start):
        priced = priced_by_start[start]
        gap = prev_start is not None and not _adjacent(prev_start, start, width_days)
        totals.append(
            TotalPoint(
                start=start,
                value=tcgcsv.format_price(by_start[start]),
                priced_names=priced,
                unpriced_names=max(0, on_hand_count - priced),
                gap_before=gap,
            )
        )
        prev_start = start
    return totals


def _bucket_width_from_series(series: SkuSeries) -> int:
    """The bucket width `sku_series` closed over, recovered from the series it produced
    rather than threaded through as a second argument nothing else needs — `RANGE_WIDTH_DAYS`
    is keyed by range name, not by `SkuSeries`, so this reads the one series-adjacent fact
    that is available: two adjacent, non-gapped points are exactly one bucket-width apart, by
    `sku_series`'s own construction. A series with fewer than two adjacent points cannot
    recover a width this way, so the caller only reaches this on the first non-empty series it
    finds — good enough for `aggregate_totals`'s own single use, which only needs A width, not
    every series's own."""
    for prev, cur in zip(series.points, series.points[1:]):
        if not cur.gap_before:
            try:
                return (date.fromisoformat(cur.start) - date.fromisoformat(prev.start)).days
            except ValueError:
                continue
    return 0


@dataclass(frozen=True)
class HoldingsReport:
    range: str
    width_days: int
    history_begins: Optional[str]
    # THIS READ'S OWN MOMENT, AS `store/master.py:now()` ACTUALLY RETURNS IT — an ISO
    # string, not a Unix second. The annotation used to say `int`; the caller
    # (`server/pipeline_routes.py:do_pipeline_holdings_value`) has always fed this straight
    # from `master.now() -> str`, so the field was lying about its own type, and D236's own
    # wire-shape example inherited the lie (`"at": 1758345600`). Corrected on the owner's
    # word, 2026-09-20, alongside `build_holdings_report`'s `now` parameter below. The wire
    # itself is unchanged — this is the type catching up to what it has always sent.
    at: str
    series: List[SkuSeries]
    totals: List[TotalPoint]
    unmarked_count: int
    sealed_excluded_count: int
    on_hand_count: int


def build_holdings_report(
    inventory: Inventory,
    archive: PriceArchive,
    ledger: Ledger,
    range_: str,
    now: str,
) -> HoldingsReport:
    """The whole answer for one range: every on-hand SKU's own valued series, the portfolio
    total that follows from them, and the two named, countable gaps — a name the archive has
    never priced in ANY range, and a name sealed product hides from the `cards` table
    entirely. Raises `ValueError` for a range D219's own table does not key on; the caller is
    expected to validate against `store.pricearchive.RANGE_WIDTH_DAYS` before this, the same
    way every other archive reader in this repo does."""
    if range_ not in RANGE_WIDTH_DAYS:
        raise ValueError(f"{range_!r} is not one of {sorted(RANGE_WIDTH_DAYS)}")
    width_days = RANGE_WIDTH_DAYS[range_]
    quantities = on_hand_quantities(inventory)
    names = on_hand_names(inventory)

    series: List[SkuSeries] = []
    ever_priced_any_range = 0
    earliest: Optional[str] = None
    for sku, quantity in quantities.items():
        all_buckets = archive.for_sku(sku)
        if all_buckets:
            ever_priced_any_range += 1
        buckets = [b for b in all_buckets if b.range == range_]
        one = sku_series(sku, quantity, names.get(sku, ""), buckets)
        if one is None:
            continue
        series.append(one)
        for point in one.points:
            if earliest is None or point.start < earliest:
                earliest = point.start

    unmarked = len(quantities) - ever_priced_any_range
    sealed = sealed_excluded_count(inventory, ledger)
    totals = aggregate_totals(series, len(quantities))

    return HoldingsReport(
        range=range_,
        width_days=width_days,
        history_begins=earliest,
        at=now,
        series=series,
        totals=totals,
        unmarked_count=unmarked,
        sealed_excluded_count=sealed,
        on_hand_count=len(quantities),
    )
