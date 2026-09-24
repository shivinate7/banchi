"""The walk that fills `skus` (docs/specs/identity-follows-sku.md §3.2, lane 0): every cached
TCGplayer export, oldest stamp first, folded into `store/skus.py:Skus`.

WHY A PIPELINE MODULE AND NOT A SERVER ONE. `server/` sits above `cli/`, `pipeline/` and
`store/` in this repo's layering — it imports them, never the reverse — and `pkmnscan skus
adopt` (`cli/cmd_skus.py`) has to run this walk with no server in sight, exactly
`pipeline/readings.py`'s own reason for living here (see that module's docstring). A later
lane wires the fetch routes in `server/pipeline_routes.py` and the CLI writers in
`cli/cmd_join.py`/`cli/cmd_reconcile.py` to call `apply_rows` below on the one export they
already have in hand; this module does not reach into either file.

OLDEST STAMP FIRST, AND THAT ORDER IS LOAD-BEARING. `Skus.fold` decides `STALE` vs `CHANGED`
by comparing `last_seen`, which makes the FINAL table order-independent — folding two files in
either order over an empty table produces the identical facts and stamps. What is NOT
order-independent is the `sku_facts_changed` EVENT `fill` appends: it exists to say "an older
reading disagreed with a newer one", and that sentence is only true when the older reading was
actually folded in before the newer one changed it. Processing files newest-first would still
land on the correct final row, silently — the newer file would insert clean and the older
file would refuse as `STALE`, never surfacing that the two ever disagreed. `_ordered_files`
sorts ascending by `stamp_of` for exactly this reason, `pipeline/readings.py:_run_readings`'s
own `sorted(entry.iterdir())` and `cli/cmd_cards.py:export_for`'s own
`sorted(directory.glob("*.csv"))` applied to files carrying a stamp instead of a name.

THE STAMP IS THE FILE'S OWN NAME, NEVER ITS MTIME. `server/pipeline_routes.py:_keep_export`
touches a reused file's mtime on every hit and leaves its name alone; `pipeline/
readings.py:live_export_at`'s own docstring is the argument this module reuses rather than
restates: "the stamp travels with the bytes; the mtime does not." `export-tcgplayer-<stamp>
-<digest>.csv` and `live-tcgplayer-<stamp>.csv` both carry one `YYYYMMDD-HHMMSS` run, so
`stamp_of` searches for that shape rather than stripping either prefix by name — `pipeline/`
sits below `server/pipeline_routes.py` (where `FETCHED_PREFIX` is declared) in this repo's
layering, so that constant is not reachable from here (D63: the arrow runs one way), and
`store/files.py:LIVE_PREFIX` alone would not answer for the fetched-export half. A name this
cannot read sorts last and is skipped, reported rather than guessed — `pipeline/
readings.py:live_export_at`'s own rule, "a reading whose age is unknown must never win a
comparison against one whose age is known", read here as "never folded at all" rather than
"folded last": an unstamped file could be OLDER than everything else on disk, and folding it
last would let it silently overwrite facts a real, dated file already established.

IT NEVER RAISES. A malformed export, an unreadable stamp, an empty SKU cell — each costs its
own rows or its own file, and none of them costs the walk. `Report.files_skipped` says which
files never even opened, so a thin fill is legible as a thin fill.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from pipeline import tcgcsv
from store import files
from store.skus import CHANGED, INSERTED, STALE, UNCHANGED, SkuRow, Skus, split_condition

# `YYYYMMDD-HHMMSS`, the one shape both `export-tcgplayer-<stamp>-<digest>.csv` and
# `live-tcgplayer-<stamp>.csv` reduce to — see the module docstring for why this searches
# rather than strips a known prefix.
_STAMP_RE = re.compile(r"(\d{8}-\d{6})")


def stamp_of(name: str) -> Optional[int]:
    """The UNIX second a fetched or live export was taken, out of its own filename alone.
    `None` for a name carrying no readable stamp — see the module docstring for why such a
    file is skipped rather than sorted to either end by guess."""
    match = _STAMP_RE.search(name)
    if not match:
        return None
    try:
        moment = datetime.strptime(match.group(1), "%Y%m%d-%H%M%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None
    return int(moment.timestamp())


def _ordered_files() -> List[Tuple[Path, int]]:
    """Every export this walk will fold — `.exports/<game>/*.csv` for every game directory,
    and `.live/*.csv` — paired with its stamp and sorted ascending. A file `stamp_of` cannot
    read is left out here rather than appended with a guessed order; the caller reports it as
    skipped."""
    found: List[Tuple[Path, int]] = []
    exports_root = files.inventory_dir() / files.EXPORTS_DIRNAME
    if exports_root.is_dir():
        for game_dir in sorted(p for p in exports_root.iterdir() if p.is_dir()):
            for path in sorted(game_dir.glob("*.csv")):
                stamp = stamp_of(path.name)
                if stamp is not None:
                    found.append((path, stamp))
    live_root = files.inventory_dir() / files.LIVE_DIRNAME
    if live_root.is_dir():
        for path in sorted(live_root.glob("*.csv")):
            stamp = stamp_of(path.name)
            if stamp is not None:
                found.append((path, stamp))
    found.sort(key=lambda item: (item[1], item[0].name))
    return found


def _unstamped_files() -> List[Path]:
    """The files `_ordered_files` left out, for the report — every `.csv` under either
    directory whose name `stamp_of` could not read."""
    skipped: List[Path] = []
    exports_root = files.inventory_dir() / files.EXPORTS_DIRNAME
    if exports_root.is_dir():
        for game_dir in sorted(p for p in exports_root.iterdir() if p.is_dir()):
            for path in sorted(game_dir.glob("*.csv")):
                if stamp_of(path.name) is None:
                    skipped.append(path)
    live_root = files.inventory_dir() / files.LIVE_DIRNAME
    if live_root.is_dir():
        for path in sorted(live_root.glob("*.csv")):
            if stamp_of(path.name) is None:
                skipped.append(path)
    return skipped


def row_from_csv(row: tcgcsv.Row, *, at: int, source: str) -> Optional[Tuple[str, SkuRow]]:
    """One export row turned into `(sku, SkuRow)`, or `None` for a row with no SKU cell —
    the blank-`TCGplayer Id` lines a Filtered Export sometimes carries for a heading or a
    note, `pipeline/join.py:Catalog`'s own reason for skipping them."""
    sku = str(row.get(tcgcsv.SKU_COLUMN) or "").strip()
    if not sku:
        return None
    condition = str(row.get(tcgcsv.CONDITION_COLUMN) or "").strip()
    grade, printing = split_condition(condition)
    return sku, SkuRow(
        product_line=str(row.get(tcgcsv.PRODUCT_LINE_COLUMN) or "").strip(),
        set_name=str(row.get(tcgcsv.SET_COLUMN) or "").strip(),
        product_name=str(row.get(tcgcsv.NAME_COLUMN) or "").strip(),
        number=str(row.get(tcgcsv.NUMBER_COLUMN) or "").strip(),
        rarity=str(row.get(tcgcsv.RARITY_COLUMN) or "").strip(),
        condition=condition,
        grade=grade,
        printing=printing,
        first_seen=at,
        last_seen=at,
        source=source,
        raw=dict(row),
    )


def _changed_event(sku: str, old: SkuRow, new: SkuRow, source: str) -> dict:
    """The `sku_facts_changed` event spec §3.2 names: "one event with the old facts"."""
    fields = ("product_line", "set_name", "product_name", "number", "rarity", "condition")
    return {
        "event": "sku_facts_changed",
        "sku": sku,
        "source": source,
        "old": {name: getattr(old, name) for name in fields},
        "new": {name: getattr(new, name) for name in fields},
    }


@dataclass
class Report:
    """What one `fill()`/`apply_rows()` call did — never a description of the code, a count
    of what happened."""

    files_read: int = 0
    files_skipped: List[str] = field(default_factory=list)
    inserted: int = 0
    unchanged: int = 0
    stale: int = 0
    changed: List[Tuple[str, SkuRow, SkuRow]] = field(default_factory=list)

    @property
    def total_rows(self) -> int:
        return self.inserted + self.unchanged + self.stale + len(self.changed)


def apply_rows(
    rows, *, at: int, source: str, skus: Skus, events: List[dict], report: Optional[Report] = None
) -> Report:
    """Fold one ALREADY-READ export's rows into `skus`, appending one `sku_facts_changed`
    event to `events` per `CHANGED` fold. `report` lets a caller accumulate across several
    calls (`fill` below does); a fresh one is returned when none is passed, so a single-file
    caller (a later lane's fetch route) can call this directly, `pipeline/
    readings.py:reading_from_export`'s own shape — pulled out so that caller need not re-walk
    the whole disk for the one file it just fetched.
    """
    report = report if report is not None else Report()
    for row in rows:
        built = row_from_csv(row, at=at, source=source)
        if built is None:
            continue
        sku, incoming = built
        result = skus.fold(sku, incoming)
        if result.outcome == INSERTED:
            report.inserted += 1
        elif result.outcome == UNCHANGED:
            report.unchanged += 1
        elif result.outcome == STALE:
            report.stale += 1
        elif result.outcome == CHANGED:
            report.changed.append((sku, result.old, incoming))
            events.append(_changed_event(sku, result.old, incoming, source))
    return report


def fill(skus: Skus, events: List[dict]) -> Report:
    """The whole-disk walk `pkmnscan skus adopt` runs: every cached export this machine has,
    oldest stamp first, folded into `skus` — see the module docstring for why the order
    matters and why an unstamped file is skipped rather than guessed at.

    NEVER RAISES. A file that will not parse as a Filtered Export costs its own row in
    `Report.files_skipped`, exactly like a name `stamp_of` cannot read; the walk continues
    either way.
    """
    report = Report()
    for path in _unstamped_files():
        report.files_skipped.append(str(path))
    for path, stamp in _ordered_files():
        try:
            export = tcgcsv.read_export(path)
        except (tcgcsv.MalformedCsv, OSError):
            report.files_skipped.append(str(path))
            continue
        report.files_read += 1
        apply_rows(export.rows, at=stamp, source=path.name, skus=skus, events=events, report=report)
    return report
