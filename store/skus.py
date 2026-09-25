"""`skus` — the store-owned TCGplayer SKU table: every SKU this repo has ever read out of a
Filtered Export or a live export, and the six facts that row carried (docs/specs/
identity-follows-sku.md §3.2, lane 0, "the SKU table" — owner's ruling, 2026-09-24: "yes I'd
been saying we build this").

WHY A TABLE, AND NOT A LIVE JOIN TO AN EXPORT (the spec's own argument, restated once).
`#/inventory` is a polled route, and an export ages out of `inventory/.exports/` (D166) — a
live join answers neither. A SKU lookup against this table is one indexed probe, and a row
outlives the file that brought it. Three in-memory copies of exactly this map already exist
in this repo (`pipeline/pricearchive.merged_export_rows_by_sku`, `pipeline/
sku_name_contradictions.Catalog`, and `cli/cmd_cards.py`'s `export_for`, retired with `cards
variants`); this table is that map, written down once, and the two left become readers of it
in a later lane — this module does not rewire them.

THE SIX FACT CELLS ARE VERBATIM, AND `grade`/`printing` ARE DERIVED FROM `condition` AT WRITE
TIME, never stored twice: `split_condition` below is the one place a `Condition` cell is
parsed, so a change to the vocabulary changes in one place.

THIS TABLE NEVER DELETES A ROW, WHATEVER A CARD POINTS AT — `store/pricearchive.py`'s rule,
not `store/readings.py`'s: a SKU TCGplayer stops listing keeps its row, because a card bound
to it still needs its facts, and unlike `readings` this is not a cache of "what does the
market say right now" but a record of "what has this SKU ever been". `Skus.fold()` is the
ONLY write path this module exposes, and it never calls `del` on `self.entries` — proved
behaviourally in `scripts/skus-selftest.py` by folding a second file that omits an earlier
SKU and asserting the earlier row survives untouched, the same proof
`scripts/pricearchive-selftest.py` runs for `price_history`.

NEWEST WINS BY THE FILE'S OWN STAMP, D189's rule for `readings` applied here rather than
restated: `first_seen`/`last_seen` and `source` are read off a file's OWN NAME
(`pipeline/skus.py:stamp_of`), never its mtime and never the moment of the press — D166's own
rule, "a reuse never touches the reading's time".

A CHANGED FACT WRITES A NEW ROW AND LOGS THE OLD ONE. `Skus.fold()` returns a `FoldResult`
naming which of four things just happened (`INSERTED`, `UNCHANGED`, `STALE`, `CHANGED`); on
`CHANGED` it hands back the row BEFORE the write, and the caller
(`pipeline/skus.py:fill`/`apply_rows`) is what turns that into one `sku_facts_changed` event
— this module never touches `Inventory.events` itself, because it has no snapshot to append
one to; it only ever answers "what changed", and never decides where that gets written down.
`first_seen` RESETS to the changed file's own stamp on a `CHANGED` fold: the old facts and the
new facts are two different rows in every sense but the key, so the row's own "oldest file
that carried THIS row" starts again at the moment those facts became true. Measured frequency
across the four fixture exports: 0.

BOTH ARE ORDINARY D88 TABLES: bound into `Snapshot` like `cards` or `readings`, flushed
inside the same `Store.write()` transaction, read lock-free through `Store.read()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, NamedTuple, Optional, Tuple

from store.rows import Rows, TableSpec

# The five grade prefixes a `Condition` cell can start with (D137's own vocabulary: "drop the
# play grades" — Near Mint plus the four play grades). MEASURED across every committed
# fixture export (`fixtures/*_export_untouched.csv`, all four product lines this repo has
# real exports for): exactly these five strings, and no others, appear as a `Condition`
# cell's own prefix. `Unopened` — sealed product's one condition
# (`pipeline/tcgcsv.py:SEALED_CONDITION`) — is deliberately NOT one of them: it is not a
# grade a played card wears, so a SKU carrying it gets `grade=None, printing=None` and its
# whole `Condition` cell still lives in `condition` (the fact cell) and in `raw`, just never
# split.
GRADES: Tuple[str, ...] = (
    "Near Mint", "Lightly Played", "Moderately Played", "Heavily Played", "Damaged",
)

INSERTED = "inserted"
UNCHANGED = "unchanged"
STALE = "stale"
CHANGED = "changed"


def split_condition(condition: str) -> Tuple[Optional[str], Optional[str]]:
    """`(grade, printing)` out of one `Condition` cell, or `(None, None)` for a cell outside
    `GRADES` (chiefly `Unopened`, and anything this repo has not seen yet).

    A cell equal to its grade exactly — plain `Near Mint`, no finish suffix — answers
    `(grade, None)`, never `(grade, "")`: there is nothing to its right to call a printing.
    The search tries every grade rather than special-casing the longest match, so a future
    grade that happened to be a prefix of an existing one would not silently mis-split —
    unreachable today (no string in `GRADES` is a prefix of another), but the loop costs
    nothing to make safe against it anyway.
    """
    condition = condition or ""
    for grade in GRADES:
        if condition == grade:
            return grade, None
        prefix = grade + " "
        if condition.startswith(prefix):
            printing = condition[len(prefix):].strip()
            return grade, (printing or None)
    return None, None


class SkuRow(NamedTuple):
    """One SKU's facts, as the newest file this table has folded still agrees they are.

    `raw` is the WHOLE CSV row, verbatim — "payload... for any column not promoted" (spec
    §3.2's own words for this table's `payload` column): `Title`, the price columns, `Photo
    URL`, everything `tcgcsv.CANONICAL_HEADER` carries that the six fact cells and the two
    split condition columns do not. It is never read by `facts()`, so a price moving from one
    file to the next is never a "changed fact" — only the six cells below are.
    """

    product_line: str
    set_name: str
    product_name: str
    number: str
    rarity: str
    condition: str
    grade: Optional[str]
    printing: Optional[str]
    first_seen: int
    last_seen: int
    source: str
    raw: Dict[str, str]

    def facts(self) -> Tuple[str, str, str, str, str, str]:
        """The six fact cells alone (spec §3.2) — what a fold compares, and what the audit
        (§4.3, a later lane) means by "a product whose SKUs disagree on rarity"."""
        return (
            self.product_line, self.set_name, self.product_name, self.number,
            self.rarity, self.condition,
        )


def _parse_sku(key: str, record: dict) -> Optional[SkuRow]:
    """One `skus` row, or `None` for a shape that will not construct.

    SKIPPED RATHER THAN RAISED ON, `store/readings.py:_parse_reading`'s rule and for the same
    reason: an unreadable row costs one SKU's facts, not a claim protecting money already
    spent, so the rest of the table stays legible.
    """
    source = str(record.get("source") or "")
    if not source:
        return None
    try:
        first_seen = int(record.get("first_seen") or 0)
        last_seen = int(record.get("last_seen") or 0)
    except (TypeError, ValueError):
        return None
    raw = record.get("raw")
    if not isinstance(raw, dict):
        raw = {}
    return SkuRow(
        product_line=str(record.get("product_line") or ""),
        set_name=str(record.get("set_name") or ""),
        product_name=str(record.get("product_name") or ""),
        number=str(record.get("number") or ""),
        rarity=str(record.get("rarity") or ""),
        condition=str(record.get("condition") or ""),
        grade=(str(record["grade"]) if record.get("grade") else None),
        printing=(str(record["printing"]) if record.get("printing") else None),
        first_seen=first_seen,
        last_seen=last_seen,
        source=source,
        raw={str(k): str(v) for k, v in raw.items()},
    )


class FoldResult(NamedTuple):
    """What one `Skus.fold()` call just did. `old` is set only for `CHANGED` — the row as it
    stood immediately before this write, for the caller to log beside the new one."""

    outcome: str
    old: Optional[SkuRow] = None


@dataclass
class Skus:
    entries: "Rows" = field(default_factory=lambda: Rows(Skus.ENTRIES))

    # The `skus` table (D88's shape): the six fact cells and the split condition promoted to
    # indexed columns, `first_seen`/`last_seen`/`source` beside them, everything else — the
    # whole CSV row as read — in `payload` through `raw`.
    ENTRIES = TableSpec(
        "skus",
        parse=_parse_sku,
        dump=lambda r: r._asdict(),
        columns=lambda r: {
            "product_line": r.product_line,
            "set_name": r.set_name,
            "product_name": r.product_name,
            "number": r.number,
            "rarity": r.rarity,
            "condition": r.condition,
            "grade": r.grade,
            "printing": r.printing,
            "first_seen": r.first_seen,
            "last_seen": r.last_seen,
            "source": r.source,
        },
        column_names=(
            "product_line", "set_name", "product_name", "number", "rarity", "condition",
            "grade", "printing", "first_seen", "last_seen", "source",
        ),
    )

    def __post_init__(self) -> None:
        if not isinstance(self.entries, Rows):
            self.entries = Rows(Skus.ENTRIES, objects=dict(self.entries))

    # -------------------------------------------------------------------------- writing

    def fold(self, sku: str, incoming: SkuRow) -> FoldResult:
        """Fold one freshly-read row for `sku` in. THE ONLY WRITE PATH THIS MODULE EXPOSES,
        and it never deletes — see the module docstring.

        Four outcomes, in the owner's own words (spec §3.2):

        - `sku` is new to this table: `INSERTED`, `incoming` written whole.
        - `incoming.last_seen` is OLDER than the stored `last_seen`: `STALE`, no-op — "an
          incoming row from an older file changes nothing", even where the facts happen to
          differ.
        - `incoming.last_seen` is newer or equal and the six facts agree: `UNCHANGED` —
          `first_seen` is KEPT (the oldest file that ever carried these facts), `last_seen`/
          `source`/`raw`/`grade`/`printing` move forward to the incoming file.
        - `incoming.last_seen` is newer or equal and the six facts disagree: `CHANGED` — the
          new facts replace the old, `first_seen` resets to this file's own stamp (a
          different set of facts started being true here), and the row as it stood a moment
          ago is handed back so the caller can log `sku_facts_changed` beside it.

        A tie on `last_seen` (`incoming.last_seen == existing.last_seen`) is NOT stale — the
        later-processed source wins, `pipeline/readings.py:collect`'s own `>=` rule applied
        here rather than restated.
        """
        key = str(sku)
        existing = self.entries.get(key)
        if existing is None:
            self.entries[key] = incoming
            return FoldResult(INSERTED)
        if incoming.last_seen < existing.last_seen:
            return FoldResult(STALE)
        if incoming.facts() == existing.facts():
            self.entries[key] = existing._replace(
                last_seen=incoming.last_seen,
                source=incoming.source,
                raw=incoming.raw,
                grade=incoming.grade,
                printing=incoming.printing,
            )
            return FoldResult(UNCHANGED)
        self.entries[key] = incoming._replace(first_seen=incoming.last_seen)
        return FoldResult(CHANGED, existing)
