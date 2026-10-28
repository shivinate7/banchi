"""`daily_prices` and `daily_price_updates` — TCGCSV's current Riftbound prices, one row per product,
printing and source update, kept from the day this table exists (D88, D219's never-delete rule).

WHY THIS TABLE EXISTS. `tcgcsv.com` once served every past day as an archive and withdrew it, so a day not read
the day it is published is gone from the one source that gave a whole market's prices. `pipeline/dailyprices.py`
reads the current file once per source update and offers this module what it found; the history builds from now.
The price-pattern research that D325 names is the reader; no screen reads it yet.

THE KEY IS `(product_id, sub_type, day)` AND `day` IS THE SOURCE'S OWN UPDATE DATE, NEVER THE READ'S. A read at 23:00
and another at 05:15 the next day see the same data, so a key on the day of the read would save one update twice.
`updated` keeps the source's full stamp beside every row and `at` the second this machine read it. A second update
that lands on the same UTC day replaces that day's rows: it is a fresher read of the same day, the way
`store/pricearchive.py` overwrites a bucket re-read.

THIS TABLE NEVER DELETES A ROW. A product the source stops listing keeps every row it ever had. `DailyPrices.save`
only adds a key or overwrites its own.

`daily_price_updates` HOLDS WHAT MAKES AN UPDATE FINISHED, one row per source stamp: the groups whose rows are saved
and whether every group was. A pass saves its groups' rows and marks the groups in one call, so one `Store.write()`
commits both: a crash leaves nothing half-marked. The next pass for the same stamp asks for the groups not marked.
Only a pass that ends with no failed group sets `finished`, and only a finished update lets the next pass skip.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, NamedTuple, Optional, Tuple

from store.rows import Rows, TableSpec


class DailyPrice(NamedTuple):
    """One product's one printing under one source update. The five prices are `str` of the number as the source
    gave it, `None` for null, absent or zero (`pipeline/pricehistory.py:_decimal`)."""

    product_id: int
    sub_type: str
    day: str  # ISO date, the update stamp's UTC date
    updated: str  # the source's full stamp
    market: Optional[str]
    low: Optional[str]
    mid: Optional[str]
    high: Optional[str]
    direct_low: Optional[str]
    group_id: int
    at: int  # UNIX second this machine read it


class Update(NamedTuple):
    """One source update: the groups whose rows are saved, and whether every group is."""

    updated: str
    day: str
    groups: Tuple[int, ...]
    finished: bool
    at: int


def _key(product_id: int, sub_type: str, day: str) -> str:
    return f"{product_id}:{sub_type}:{day}"


def _parse_price(key: str, record: dict) -> Optional[DailyPrice]:
    """A row, or `None` for a shape that will not construct: skipped, not raised on, so one unreadable row costs
    one observation (`store/pricearchive.py:_parse_bucket`'s rule)."""
    try:
        product_id = int(record["product_id"])
        group_id = int(record.get("group_id") or 0)
        at = int(record.get("at") or 0)
    except (KeyError, TypeError, ValueError):
        return None
    day = str(record.get("day") or "")
    if not day:
        return None
    return DailyPrice(
        product_id=product_id, sub_type=str(record.get("sub_type") or ""), day=day,
        updated=str(record.get("updated") or ""), market=record.get("market"), low=record.get("low"),
        mid=record.get("mid"), high=record.get("high"), direct_low=record.get("direct_low"),
        group_id=group_id, at=at,
    )


def _parse_update(key: str, record: dict) -> Optional[Update]:
    updated = str(record.get("updated") or "")
    if not updated:
        return None
    try:
        groups = tuple(int(g) for g in record.get("groups") or ())
        at = int(record.get("at") or 0)
    except (TypeError, ValueError):
        return None
    return Update(updated, str(record.get("day") or ""), groups, bool(record.get("finished")), at)


@dataclass
class DailyPrices:
    entries: "Rows" = field(default_factory=lambda: Rows(DailyPrices.ENTRIES))
    updates: "Rows" = field(default_factory=lambda: Rows(DailyPrices.UPDATES))

    ENTRIES = TableSpec(
        "daily_prices",
        parse=_parse_price,
        dump=lambda p: p._asdict(),
        columns=lambda p: {
            "product_id": p.product_id, "sub_type": p.sub_type, "day": p.day, "group_id": p.group_id,
            "updated": p.updated,
        },
        column_names=("product_id", "sub_type", "day", "group_id", "updated"),
    )
    UPDATES = TableSpec(
        "daily_price_updates",
        parse=_parse_update,
        dump=lambda u: {**u._asdict(), "groups": list(u.groups)},
        columns=lambda u: {"updated": u.updated, "day": u.day, "finished": int(u.finished), "at": u.at},
        column_names=("updated", "day", "finished", "at"),
    )

    def __post_init__(self) -> None:
        if not isinstance(self.entries, Rows):
            self.entries = Rows(DailyPrices.ENTRIES, objects=dict(self.entries))
        if not isinstance(self.updates, Rows):
            self.updates = Rows(DailyPrices.UPDATES, objects=dict(self.updates))

    def update(self, updated: str) -> Optional[Update]:
        """The row for one source stamp, or `None` when no pass has saved a group of it."""
        return self.updates.get(updated)

    def save(self, update: Update, rows: Iterable[DailyPrice], group_ids: Iterable[int], *, finished: bool) -> Update:
        """Fold a pass's rows in and mark its groups saved, `finished` when no group failed. NEVER A CLEAR: a row
        this call does not mention stays as it was. Returns the update as marked."""
        for row in rows:
            self.entries[_key(row.product_id, row.sub_type, row.day)] = row
        update = update._replace(groups=tuple(sorted({*update.groups, *group_ids})), finished=finished)
        self.updates[update.updated] = update
        return update
