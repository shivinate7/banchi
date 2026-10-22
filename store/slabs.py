"""`slabs`, `slab_snapshots` and `slab_sales`: the My Slabs tables (D320, spec section 6).

THREE ORDINARY D88 TABLES, bound into `Snapshot` as `snapshot.slabs` and flushed in the one
`Store.write()` transaction, so a slab, its day's snapshot and its sales land together or not
at all.

- `slabs`: one row per (cert, grader). The grader is stored in Card Ladder's name, so `bgs`,
  `bvg` and `beckett` are one slab. A cert is text; `"0012345678"` keeps its zeros.
- `slab_snapshots`: one row per slab per day. A second write that day REPLACES the row whole.
  The slab row keeps a copy of its newest one (`Slab.latest`), so `GET /slabs` never reads this
  table. `record_snapshot` is the one snapshot writer and keeps the copy; `Slabs.add` reseeds it
  from the newest stored snapshot when it re-creates a removed slab; `_parse_slab` rebuilds it
  from the stored row.
- `slab_sales`: one row per Card Ladder sale id however many slabs and reads see it, and NEVER
  deleted: a sale Card Ladder later drops stays here. The row names every slab that read it.
- A remove (`Slabs.remove`) takes the slab row and its links only; snapshots and sales stay.
- `slab_sale_links`: one row per (slab, sale), indexed on the slab key, so `sales_for` fetches
  that slab's sales by key and never scans `slab_sales`.

NO GUESSED VALUE. A value Card Ladder did not give is `None`, stored as NULL: never 0, never "",
never filled from the other value. Money is text, kept exactly as given.

`GRADERS` lives here because `store/` may not import `pipeline/` (D63, `store/numbers.py`'s
precedent); `pipeline/cardladder.py` imports it back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, NamedTuple, Optional

from store.rows import Rows, TableSpec

# Card Ladder maps these to `beckett` (spec 3.1).
GRADERS = {"psa": "psa", "beckett": "beckett", "bgs": "beckett", "bvg": "beckett", "sgc": "sgc", "cgc": "cgc"}


def _grader(grader: Any) -> str:
    # Not `pipeline/cardladder.py`'s: `store/` may not import `pipeline/` (D63), and this raises ValueError.
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
    # The newest snapshot, by day. Payload only, no column. `record_snapshot` keeps it and
    # `Slabs.add` reseeds it on a re-create, so `GET /slabs` reads `slabs` alone and never
    # `slab_snapshots` (spec section 6).
    latest: Optional["SlabSnapshot"] = None

    @property
    def key(self) -> str:
        return _slab_key(self.cert, self.grader)


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
    # The card's grade ladder as that day's read gave it. Payload only, no column; a row stored
    # before this field reads None.
    ladder: Optional[list] = None


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
    row = {name: record.get(name) for name in Slab._fields}
    row["latest"] = _parse_snapshot(key, record["latest"]) if isinstance(record.get("latest"), dict) else None
    return Slab(**row)


def _dump_slab(slab: Slab) -> dict:
    return {**slab._asdict(), "latest": slab.latest._asdict() if slab.latest else None}


def _parse_snapshot(key: str, record: dict) -> Optional[SlabSnapshot]:
    if not record.get("cert") or not record.get("grader") or not record.get("day"):
        return None
    return SlabSnapshot(**{name: record.get(name) for name in SlabSnapshot._fields})


def _parse_sale(key: str, record: dict) -> Optional[_SaleRow]:
    if not record.get("id") or not isinstance(record.get("data"), dict):
        return None
    return _SaleRow(record["id"], record.get("date"), record["data"], tuple(record.get("slabs") or ()))


class Link(NamedTuple):
    slab: str
    sale: str


def _parse_link(key: str, record: dict) -> Optional[Link]:
    return Link(record["slab"], record["sale"])


@dataclass
class Slabs:
    slabs: "Rows" = field(default_factory=lambda: Rows(Slabs.SLABS))
    snapshots: "Rows" = field(default_factory=lambda: Rows(Slabs.SNAPSHOTS))
    sales: "Rows" = field(default_factory=lambda: Rows(Slabs.SALES))
    links: "Rows" = field(default_factory=lambda: Rows(Slabs.LINKS))

    SLABS = TableSpec(
        "slabs",
        parse=_parse_slab,
        dump=_dump_slab,
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

    LINKS = TableSpec(
        "slab_sale_links",
        parse=_parse_link,
        dump=lambda r: r._asdict(),
        columns=lambda r: {"slab": r.slab},
        column_names=("slab",),
    )

    def __post_init__(self) -> None:
        if not isinstance(self.links, Rows):
            self.links = Rows(Slabs.LINKS, objects=dict(self.links))
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
        # A slab added again after a remove keeps the snapshots it left, so its copy is the newest of them.
        history = self.snapshots_for(cert, grader)
        slab = Slab(str(cert), _grader(grader), profile_id, identity, subgrades, added, history[-1] if history else None)
        self.slabs[key] = slab
        return slab

    def record_snapshot(
        self, cert, grader, day, *, cl_value, cl_confidence, estimated_value,
        estimated_confidence, last_sale_price, last_sale_date, population, gem_rate, speed,
        ladder=None,
    ) -> SlabSnapshot:
        """One row per slab per day; a second write that day replaces every field.

        The slab row's `latest` moves in the same write, unless this day is older than the copy's.
        A slab with no row raises ValueError and writes nothing."""
        key = _slab_key(cert, grader)
        slab = self.slabs.get(key)
        if slab is None:
            raise ValueError("No slab %s to record a snapshot for." % key)
        snapshot = SlabSnapshot(
            str(cert), _grader(grader), day, cl_value, cl_confidence, estimated_value,
            estimated_confidence, last_sale_price, last_sale_date, population, gem_rate, speed, ladder,
        )
        self.snapshots["%s:%s" % (key, day)] = snapshot
        if slab.latest is None or day >= slab.latest.day:
            self.slabs[key] = slab._replace(latest=snapshot)
        return snapshot

    def record_sales(self, cert, grader, sales) -> None:
        """Keyed by sale id alone. All sales or none: one without an `id` or a text `date` raises first."""
        slab = _slab_key(cert, grader)
        sales = list(sales)
        if any(not sale.get("id") for sale in sales):
            raise ValueError("A Card Ladder sale has no id.")
        if any(not isinstance(sale.get("date"), str) for sale in sales):
            raise ValueError("A Card Ladder sale has no text date.")
        for sale in sales:
            key = str(sale["id"])
            seen = self.sales[key].slabs if key in self.sales else ()
            self.sales[key] = _SaleRow(key, sale.get("date"), sale, seen if slab in seen else seen + (slab,))
            self.links["%s|%s" % (slab, key)] = Link(slab, key)

    def remove(self, cert, grader) -> Optional[Slab]:
        """The slab row and its sale links go. Snapshots and sales stay, so adding it again brings them back."""
        key = _slab_key(cert, grader)
        slab = self.slabs.get(key)
        if slab is None:
            return None
        for link in self.links.where(slab=key):
            del self.links["%s|%s" % (link.slab, link.sale)]
        del self.slabs[key]
        return slab

    # -------------------------------------------------------------------------- reading

    def get(self, cert, grader) -> Optional[Slab]:
        return self.slabs.get(_slab_key(cert, grader))

    def list(self) -> List[Slab]:
        return [self.slabs[key] for key in sorted(self.slabs)]

    def keys_with_sales(self) -> set:
        """Keys (`grader:cert`) of the slabs that have a sale: one indexed read of the links."""
        return self.links.distinct("slab")

    def snapshots_for(self, cert, grader) -> List[SlabSnapshot]:
        rows = self.snapshots.where(cert=str(cert), grader=_grader(grader))
        return sorted(rows, key=lambda row: row.day)

    def sales_for(self, cert, grader) -> List[Sale]:
        rows = [self.sales[link.sale] for link in self.links.where(slab=_slab_key(cert, grader))]
        rows.sort(key=lambda row: (row.date or "", row.id), reverse=True)
        return [Sale(row.id, row.date, row.data) for row in rows]
