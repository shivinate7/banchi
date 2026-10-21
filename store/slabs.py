"""`slabs`, `slab_snapshots` and `slab_sales`: the My Slabs tables (D320, spec section 6).

THREE ORDINARY D88 TABLES, bound into `Snapshot` as `snapshot.slabs` and flushed in the one
`Store.write()` transaction, so a slab, its day's snapshot and its sales land together or not
at all.

- `slabs`: one row per (cert, grader). The grader is stored in Card Ladder's name, so `bgs`,
  `bvg` and `beckett` are one slab. A cert is text; `"0012345678"` keeps its zeros.
- `slab_snapshots`: one row per slab per day. A second write that day REPLACES the row whole.
- `slab_sales`: one row per Card Ladder sale id however many slabs and reads see it, and NEVER
  deleted: a sale Card Ladder later drops stays here. The row names every slab that read it.

NO GUESSED VALUE. A value Card Ladder did not give is `None`, stored as NULL: never 0, never "",
never filled from the other value. Money is text, kept exactly as given.

`GRADERS` lives here because `store/` may not import `pipeline/` (D63, `store/numbers.py`'s
precedent); `pipeline/cardladder.py` imports it back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, NamedTuple, Optional

from store.rows import Rows, TableSpec

# Card Ladder maps these to `beckett` (spec 3.1).
GRADERS = {"psa": "psa", "beckett": "beckett", "bgs": "beckett", "bvg": "beckett", "sgc": "sgc", "cgc": "cgc"}


def _grader(grader: Any) -> str:
    try:
        return GRADERS[str(grader).lower()]
    except KeyError:
        raise ValueError("Unknown grader %r." % (grader,)) from None


def _slab_key(cert: Any, grader: Any) -> str:
    return "%s:%s" % (_grader(grader), cert)


class Slab(NamedTuple):
    cert: str
    grader: str
    profile_id: Optional[str]
    identity: dict
    subgrades: Optional[dict]
    added: str


class SlabSnapshot(NamedTuple):
    cert: str
    grader: str
    day: str
    cl_value: Optional[str]
    cl_confidence: Optional[int]
    estimated_value: Optional[str]
    estimated_confidence: Optional[int]
    last_sale_price: Optional[str]
    last_sale_date: Optional[str]
    population: Optional[int]
    gem_rate: Optional[float]
    speed: Optional[dict]


class Sale(NamedTuple):
    id: str
    date: Optional[str]
    data: dict


class _SaleRow(NamedTuple):
    """What the table holds: the sale and every slab (by key) that read it."""

    id: str
    date: Optional[str]
    data: dict
    slabs: tuple


def _parse_slab(key: str, record: dict) -> Optional[Slab]:
    if not record.get("cert") or not record.get("grader"):
        return None
    return Slab(**{name: record.get(name) for name in Slab._fields})


def _parse_snapshot(key: str, record: dict) -> Optional[SlabSnapshot]:
    if not record.get("cert") or not record.get("grader") or not record.get("day"):
        return None
    return SlabSnapshot(**{name: record.get(name) for name in SlabSnapshot._fields})


def _parse_sale(key: str, record: dict) -> Optional[_SaleRow]:
    if not record.get("id") or not isinstance(record.get("data"), dict):
        return None
    return _SaleRow(record["id"], record.get("date"), record["data"], tuple(record.get("slabs") or ()))


@dataclass
class Slabs:
    slabs: "Rows" = field(default_factory=lambda: Rows(Slabs.SLABS))
    snapshots: "Rows" = field(default_factory=lambda: Rows(Slabs.SNAPSHOTS))
    sales: "Rows" = field(default_factory=lambda: Rows(Slabs.SALES))

    SLABS = TableSpec(
        "slabs",
        parse=_parse_slab,
        dump=lambda r: r._asdict(),
        columns=lambda r: {"cert": r.cert, "grader": r.grader, "profile_id": r.profile_id, "added": r.added},
        column_names=("cert", "grader", "profile_id", "added"),
    )
    # The five value columns are real so a person with the `sqlite3` CLI can read them; the
    # payload holds the whole row.
    SNAPSHOTS = TableSpec(
        "slab_snapshots",
        parse=_parse_snapshot,
        dump=lambda r: r._asdict(),
        columns=lambda r: {
            "cert": r.cert, "grader": r.grader, "day": r.day,
            "cl_value": r.cl_value, "cl_confidence": r.cl_confidence,
            "estimated_value": r.estimated_value, "estimated_confidence": r.estimated_confidence,
            "last_sale_price": r.last_sale_price,
        },
        column_names=(
            "cert", "grader", "day", "cl_value", "cl_confidence",
            "estimated_value", "estimated_confidence", "last_sale_price",
        ),
    )
    SALES = TableSpec(
        "slab_sales",
        parse=_parse_sale,
        dump=lambda r: r._asdict(),
        columns=lambda r: {"date": r.date},
        column_names=("date",),
    )

    def __post_init__(self) -> None:
        if not isinstance(self.slabs, Rows):
            self.slabs = Rows(Slabs.SLABS, objects=dict(self.slabs))
        if not isinstance(self.snapshots, Rows):
            self.snapshots = Rows(Slabs.SNAPSHOTS, objects=dict(self.snapshots))
        if not isinstance(self.sales, Rows):
            self.sales = Rows(Slabs.SALES, objects=dict(self.sales))

    # -------------------------------------------------------------------------- writing

    def add(self, cert, grader, *, profile_id, identity, subgrades, added) -> Slab:
        """The slab, or the row already there: a second add keeps the first `added`."""
        key = _slab_key(cert, grader)
        if key in self.slabs:
            return self.slabs[key]
        slab = Slab(str(cert), _grader(grader), profile_id, identity, subgrades, added)
        self.slabs[key] = slab
        return slab

    def record_snapshot(
        self, cert, grader, day, *, cl_value, cl_confidence, estimated_value,
        estimated_confidence, last_sale_price, last_sale_date, population, gem_rate, speed,
    ) -> SlabSnapshot:
        """One row per slab per day; a second write that day replaces every field."""
        snapshot = SlabSnapshot(
            str(cert), _grader(grader), day, cl_value, cl_confidence, estimated_value,
            estimated_confidence, last_sale_price, last_sale_date, population, gem_rate, speed,
        )
        self.snapshots["%s:%s" % (_slab_key(cert, grader), day)] = snapshot
        return snapshot

    def record_sales(self, cert, grader, sales) -> None:
        """Keyed by sale id alone. All sales or none: one without an `id` raises first."""
        slab = _slab_key(cert, grader)
        sales = list(sales)
        if any(not sale.get("id") for sale in sales):
            raise ValueError("A Card Ladder sale has no id.")
        for sale in sales:
            key = str(sale["id"])
            seen = self.sales[key].slabs if key in self.sales else ()
            self.sales[key] = _SaleRow(key, sale.get("date"), sale, seen if slab in seen else seen + (slab,))

    # -------------------------------------------------------------------------- reading

    def get(self, cert, grader) -> Optional[Slab]:
        return self.slabs.get(_slab_key(cert, grader))

    def list(self) -> List[Slab]:
        return [self.slabs[key] for key in sorted(self.slabs)]

    def snapshots_for(self, cert, grader) -> List[SlabSnapshot]:
        rows = self.snapshots.where(cert=str(cert), grader=_grader(grader))
        return sorted(rows, key=lambda row: row.day)

    def sales_for(self, cert, grader) -> List[Sale]:
        # ponytail: a sale names its slabs in the payload, so this reads every sale row.
        # Fine at one owner's slabs; add a slab-to-sale link table if the sales grow past it.
        slab = _slab_key(cert, grader)
        rows = [row for row in self.sales.values() if slab in row.slabs]
        rows.sort(key=lambda row: (row.date or "", row.id), reverse=True)
        return [Sale(row.id, row.date, row.data) for row in rows]
