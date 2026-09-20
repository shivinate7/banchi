"""`price_history` and `price_history_sources` — the market-history buckets this machine has
read, kept past the source's own 357-day ceiling (D219).

WHY THIS TABLE EXISTS AT ALL. `pipeline/pricehistory.py` reads `infinite-api.tcgplayer.com`'s
history endpoint, and that endpoint's own `annual` range is 357 days wide and SLIDES: a
bucket that fell out of the window yesterday cannot be asked for again at any price, from any
range, ever. Nothing in this repo captured a bucket before it aged out until this table did.
`pipeline/pricearchive.py` is the walk that reads the live endpoint and offers this module
what it found; `cli/cmd_pricearchive.py` is the press that runs the walk and writes here.

THE KEY CARRIES THE RANGE, NOT THE WIDTH, AND THAT IS THE ONE ARGUMENT THIS MODULE HAS TO
MAKE (D62). Buckets from different ranges overlap on the calendar: one calendar day is a
one-day bucket in `month` and the same day sits inside a seven-day bucket in `annual`. Those
are two different facts about that day and D62 forbids merging them. A key built from
`(sku, width_days, start)` looks like it would tell them apart, until you notice
`semiannual` and `annual` are BOTH SEVEN-DAY BUCKETS (`pipeline/pricehistory.py:41-45`) — a
width-keyed table would silently fold a semiannual bucket and an annual bucket that happen to
start on the same date into one row, exactly the D62 collision this table exists to prevent,
and it would do it precisely on the boundary where the two ranges' coverage overlaps most.
`range` is the one field the endpoint itself uses to keep these two apart, so this table keys
on it directly: `(sku, range, start)`. `product_id` and `width_days` are stored as columns
for a reader to join or sort on, never as part of the key — a SKU never belongs to two
products, so `sku` alone already carries everything `product_id` would add to the key, and
`width_days` is a fact ABOUT the row (`RANGE_WIDTH_DAYS[range]`) rather than a second axis of
identity.

THIS TABLE NEVER DELETES A ROW, AND THAT IS THE WHOLE POINT OF THE FEATURE — the one place
this module differs from `store/readings.py`'s `Readings.replace()`, which is a full
clear-then-reinsert on every `readings adopt --write` because that table is a CACHE of files
still on disk. A price-history bucket has no such second copy: once the source's 357-day
window slides past it, THE BYTES ARE GONE EVERYWHERE ELSE. So `PriceHistory.upsert()` only
ever adds a key it has not seen or overwrites a key it has with a fresher reading of the SAME
bucket (a re-read of a still-in-window bucket with updated totals, or the finest range — the
endpoint has been observed correcting a week's own numbers after it closes). It never clears
what a sweep does not mention, and a sweep that skips a SKU entirely — a card sold, a set
hint changed, an operator's own query narrower than last time — leaves every bucket that
sweep did not visit exactly as it was.

BOTH ARE ORDINARY D88 TABLES: bound into `Snapshot` like `readings`, flushed inside the same
`Store.write()` transaction, read lock-free through `Store.read()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, NamedTuple, Optional

from store.rows import Rows, TableSpec

#: The four ranges `pipeline/pricehistory.py:RANGES` names, and how many days wide one of
#: their buckets is. Spelled here rather than imported, because `pipeline/pricehistory.py`'s
#: own header states the widths in prose (line 41) and never as a mapping any module can
#: read — this is that mapping, and it is the fact this module's whole docstring argument
#: turns on: `semiannual` and `annual` share a width, so width alone cannot be the key.
RANGE_WIDTH_DAYS: Dict[str, int] = {
    "month": 1,
    "quarter": 3,
    "semiannual": 7,
    "annual": 7,
}


class Bucket(NamedTuple):
    """One SKU's one bucket, from one range, as archived. See the module docstring for why
    `range` (not `width_days`) is the discriminator this is keyed on."""

    sku: str
    product_id: int
    range: str
    width_days: int
    start: str  # ISO date, "YYYY-MM-DD" — the bucket's own start, never re-derived
    market: Optional[str]
    quantity: int
    transactions: int
    low: Optional[str]
    high: Optional[str]
    at: int  # UNIX second this bucket was last read and written here


def _key(sku: str, range_: str, start: str) -> str:
    return f"{sku}:{range_}:{start}"


def _parse_bucket(key: str, record: dict) -> Optional[Bucket]:
    """One `price_history` row, or `None` for a shape that will not construct.

    SKIPPED RATHER THAN RAISED ON, `store/readings.py:_parse_reading`'s rule and for the same
    reason: an unreadable bucket costs one observation, not a claim protecting money already
    spent, so the rest of the archive stays legible.
    """
    sku = str(record.get("sku") or "")
    range_ = str(record.get("range") or "")
    start = str(record.get("start") or "")
    if not sku or range_ not in RANGE_WIDTH_DAYS or not start:
        return None
    try:
        product_id = int(record.get("product_id") or 0)
        width_days = int(record.get("width_days") or RANGE_WIDTH_DAYS[range_])
        quantity = int(record.get("quantity") or 0)
        transactions = int(record.get("transactions") or 0)
        at = int(record.get("at") or 0)
    except (TypeError, ValueError):
        return None
    return Bucket(
        sku=sku,
        product_id=product_id,
        range=range_,
        width_days=width_days,
        start=start,
        market=record.get("market"),
        quantity=quantity,
        transactions=transactions,
        low=record.get("low"),
        high=record.get("high"),
        at=at,
    )


class Source(NamedTuple):
    """The accounting beside `price_history`: one row per RANGE this pass swept, carrying how
    many SKUs it was asked about, how many actually answered, and how many refused — the
    number `pipeline/pricearchive.py:sweep`'s bucket count alone cannot answer, exactly the
    reason `store/readings.py:Source` exists beside `readings` (D189). Keyed by `range`
    alone: one sweep asks about every subject SKU once per range, so there is exactly one
    accounting row per range per press, and the newer press's row for that range replaces the
    older one — see `PriceArchive.record_pass`.
    """

    range: str
    at: int
    requested: int
    answered: int
    refused: int


def _parse_source(key: str, record: dict) -> Optional[Source]:
    range_ = str(record.get("range") or "")
    if range_ not in RANGE_WIDTH_DAYS:
        return None
    try:
        at = int(record.get("at") or 0)
        requested = int(record.get("requested") or 0)
        answered = int(record.get("answered") or 0)
        refused = int(record.get("refused") or 0)
    except (TypeError, ValueError):
        return None
    return Source(range=range_, at=at, requested=requested, answered=answered, refused=refused)


@dataclass
class PriceArchive:
    entries: "Rows" = field(default_factory=lambda: Rows(PriceArchive.ENTRIES))
    sources: "Rows" = field(default_factory=lambda: Rows(PriceArchive.SOURCES))

    ENTRIES = TableSpec(
        "price_history",
        parse=_parse_bucket,
        dump=lambda b: b._asdict(),
        columns=lambda b: {
            "sku": b.sku,
            "product_id": b.product_id,
            "range": b.range,
            "width_days": b.width_days,
            "start": b.start,
            "market": b.market,
            "quantity": b.quantity,
            "transactions": b.transactions,
            "low": b.low,
            "high": b.high,
            "at": b.at,
        },
        column_names=(
            "sku", "product_id", "range", "width_days", "start", "market",
            "quantity", "transactions", "low", "high", "at",
        ),
    )
    SOURCES = TableSpec(
        "price_history_sources",
        parse=_parse_source,
        dump=lambda s: s._asdict(),
        columns=lambda s: {
            "range": s.range,
            "at": s.at,
            "requested": s.requested,
            "answered": s.answered,
            "refused": s.refused,
        },
        column_names=("range", "at", "requested", "answered", "refused"),
    )

    def __post_init__(self) -> None:
        if not isinstance(self.entries, Rows):
            self.entries = Rows(PriceArchive.ENTRIES, objects=dict(self.entries))
        if not isinstance(self.sources, Rows):
            self.sources = Rows(PriceArchive.SOURCES, objects=dict(self.sources))

    # -------------------------------------------------------------------------- reading

    def sources_payload(self) -> List[dict]:
        """One row per range last swept, newest first."""
        rows = [source._asdict() for source in self.sources.values()]
        rows.sort(key=lambda row: row["at"], reverse=True)
        return rows

    def for_sku(self, sku: str) -> List[Bucket]:
        """Every bucket this archive holds for one SKU, across every range — ASCENDING by
        `(range, start)` so a caller can print or chart one range's own run of buckets by
        slicing on `range` without a second sort."""
        found = [b for b in self.entries.values() if b.sku == str(sku)]
        found.sort(key=lambda b: (b.range, b.start))
        return found

    # -------------------------------------------------------------------------- writing

    def upsert(self, buckets: Dict[str, Bucket]) -> None:
        """Fold freshly read buckets in. NEVER A CLEAR — see the module docstring for why a
        bucket this pass did not mention must survive untouched: it may be the only copy of
        an observation the source itself can no longer produce.

        `buckets` is keyed by `_key(sku, range, start)`; the caller
        (`pipeline/pricearchive.py:sweep`) builds that key so this method stays a pure
        write, with no argument-order convention of its own to get wrong.

        `Rows`'s diff is baseline-based, so a bucket whose reading is byte-identical to what
        is already stored costs nothing in the transaction — only a new key or one whose
        reading actually changed reaches disk.
        """
        for key, bucket in buckets.items():
            self.entries[key] = bucket

    def record_pass(self, sources: List[Source]) -> None:
        """One row per range this pass swept, replacing that range's own prior accounting
        row — never the whole table, and never another range's row. A press that only
        touched `annual` this time must not erase what the last `month` sweep reported."""
        for source in sources:
            self.sources[source.range] = source
