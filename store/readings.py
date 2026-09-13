"""`readings` and `readings_sources` — the market prices this machine has read, cached (D189).

WHAT USED TO BE A LIVE RECOMPUTATION IS NOW TWO TABLES A PRESS FILLS. Before this, every
`GET /pipeline/value` walked every run's `runs/<n>/pricing.json` and the newest file under
`inventory/.live`, parsing JSON and CSV on every request to answer one question: `sku -> the
newest market price this machine has read for it`. That walk — the two-source arbitration,
newest wins by a clock rather than by precedence — has not changed and has not moved out of
this package; it moved to `pipeline/readings.py:collect`, run once by `pkmnscan readings
adopt --write` rather than once per request. This module is the READ half: the table that
walk fills, and what `server/pipeline_routes.py:_readings()` now does is a plain `SELECT`
against it.

TWO TABLES, BECAUSE ONE ANSWER HAS TWO SHAPES. `readings` is `sku -> Reading`, one row per
SKU, exactly the mapping the old function returned. `readings_sources` is the accounting
beside it — which files answered, and how many SKUs EACH ONE priced BEFORE arbitration —
because that count is not recoverable from `readings` alone: a run table that priced 100 SKUs
and lost 20 of them to a newer live export leaves only 80 rows in `readings` carrying its
name, and the old function's `sources` list reported the full 100. A caller that wants to know
whether a thin reading is a thin STORE or a thin FETCH needs the number the source actually
offered, not the number that survived.

BOTH ARE ORDINARY D88 TABLES: bound into `Snapshot` like `cards` or `submissions`, flushed
inside the same `Store.write()` transaction, and read lock-free through `Store.read()`. A
`readings adopt --write` press is a FULL REPLACE of both — `Readings.replace()` clears every
row and writes exactly the fresh set — because this table is a CACHE of the filesystem walk
and not an independent ledger: a SKU whose only source has since been deleted (a run
directory removed, a live export superseded) must disappear from it exactly as it would have
dropped out of the old live walk on its very next request. See `pipeline/readings.py` for the
walk itself, and `cli/cmd_readings.py` for the press that runs it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, NamedTuple, Optional

from store.rows import Rows, TableSpec

#: The two kinds of file `collect()` reads. Not an enum — every table column here is a plain
#: string, D88's own convention — but named so both this module and `pipeline/readings.py`
#: spell them once.
KIND_RUN = "run"
KIND_LIVE = "live"
KINDS = (KIND_RUN, KIND_LIVE)


class Reading(NamedTuple):
    """One SKU's most recently observed market price, and where it came from.

    `at` IS A UNIX SECOND so two sources of different kinds can be compared without parsing
    two date formats — a run table has an mtime and a fetched export has a stamp in its name,
    and neither is a superset of the other's freshness. `kind` is new against the private
    `_Reading` this replaces in `server/pipeline_routes.py`: it is what lets
    `Readings.sources_payload()` reconstruct the old `sources` list's `kind` field without a
    second lookup, and it is a real column so a person with the `sqlite3` CLI can ask
    `select kind, count(*) from readings group by kind` without touching Python at all.
    """

    market: str
    at: int
    source: str
    kind: str
    name: Optional[str] = None
    set_name: Optional[str] = None
    condition: Optional[str] = None


def _parse_reading(key: str, record: dict) -> Optional[Reading]:
    """One `readings` row, or `None` for a shape that will not construct.

    SKIPPED RATHER THAN RAISED ON, `Cache.parse`'s rule and not `Submissions._parse`'s: an
    unreadable reading costs one SKU's price, not a claim protecting a dollar already spent,
    so the store stays open and the rest of the table stays legible.
    """
    try:
        at = int(record.get("at") or 0)
    except (TypeError, ValueError):
        return None
    kind = str(record.get("kind") or "")
    source = str(record.get("source") or "")
    market = str(record.get("market") or "")
    if not market or not source or kind not in KINDS:
        return None
    return Reading(
        market=market,
        at=at,
        source=source,
        kind=kind,
        name=record.get("name"),
        set_name=record.get("set_name"),
        condition=record.get("condition"),
    )


class Source(NamedTuple):
    """One file `collect()` read that priced at least one SKU, and how many — BEFORE
    arbitration. A source's `skus` here is every row it offered, whether or not the
    newest-wins comparison let it win any of them; see the module docstring for why that
    count cannot be recovered from `readings` alone."""

    kind: str
    name: str
    at: int
    skus: int


def _parse_source(key: str, record: dict) -> Optional[Source]:
    try:
        at = int(record.get("at") or 0)
        skus = int(record.get("skus") or 0)
    except (TypeError, ValueError):
        return None
    kind = str(record.get("kind") or "")
    name = str(record.get("name") or "")
    if not name or kind not in KINDS:
        return None
    return Source(kind=kind, name=name, at=at, skus=skus)


def _source_key(kind: str, name: str) -> str:
    """The `readings_sources` primary key. `kind` is part of it on purpose: a run directory
    and a live export filename never collide in practice, but nothing about this table's
    contract should depend on that being true forever."""
    return f"{kind}:{name}"


@dataclass
class Readings:
    entries: "Rows" = field(default_factory=lambda: Rows(Readings.ENTRIES))
    sources: "Rows" = field(default_factory=lambda: Rows(Readings.SOURCES))

    # The `readings` table (D88's shape): the reading whole in the payload, and the four
    # facts a person with the `sqlite3` CLI would ask for beside it.
    ENTRIES = TableSpec(
        "readings",
        parse=_parse_reading,
        dump=lambda r: r._asdict(),
        columns=lambda r: {
            "market": r.market,
            "at": r.at,
            "source": r.source,
            "kind": r.kind,
        },
        column_names=("market", "at", "source", "kind"),
    )
    # The `readings_sources` table: one row per file `collect()` read, keyed by `kind:name`
    # rather than by `name` alone — see `_source_key`.
    SOURCES = TableSpec(
        "readings_sources",
        parse=_parse_source,
        dump=lambda s: s._asdict(),
        columns=lambda s: {
            "kind": s.kind,
            "name": s.name,
            "at": s.at,
            "skus": s.skus,
        },
        column_names=("kind", "name", "at", "skus"),
    )

    def __post_init__(self) -> None:
        if not isinstance(self.entries, Rows):
            self.entries = Rows(Readings.ENTRIES, objects=dict(self.entries))
        if not isinstance(self.sources, Rows):
            self.sources = Rows(Readings.SOURCES, objects=dict(self.sources))

    # -------------------------------------------------------------------------- reading

    def sources_payload(self) -> List[dict]:
        """The `sources` list exactly as the old live `_readings()` returned it, newest
        first — `[{"kind", "name", "at", "skus"}, ...]`."""
        rows = [source._asdict() for source in self.sources.values()]
        rows.sort(key=lambda row: row["at"], reverse=True)
        return rows

    # -------------------------------------------------------------------------- writing

    def replace(self, found: Dict[str, Reading], sources: List[Source]) -> None:
        """Full replace: exactly what one `collect()` walk just computed, and nothing it
        did not.

        `readings adopt` IS A CACHE REFRESH, NEVER AN INCREMENTAL MERGE. A SKU whose only
        source has since been retired — a run directory deleted, a live export superseded and
        removed by hand — must disappear from this table exactly as it would have dropped out
        of the old live walk on its very next call. So every row this table holds is cleared
        first, inside the caller's `Store.write()`, before the fresh set is written back.

        `Rows`'s diff is BASELINE-based and not delete-history-based (see `store/rows.py:
        Rows.changes`), so deleting a key and re-`__setitem__`-ing the identical value back
        writes nothing: only a SKU whose reading actually changed, or one that is new, costs a
        row in the transaction this runs inside. A SKU this walk no longer offers stays
        deleted.
        """
        for key in list(self.entries.keys()):
            del self.entries[key]
        for sku, reading in found.items():
            self.entries[str(sku)] = reading

        for key in list(self.sources.keys()):
            del self.sources[key]
        for source in sources:
            self.sources[_source_key(source.kind, source.name)] = source
