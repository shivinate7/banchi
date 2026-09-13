"""The two-source market-reading walk `pkmnscan readings adopt` runs (D189).

THIS IS THE ARBITRATION `server/pipeline_routes.py:_readings()` USED TO RUN ON EVERY
`GET /pipeline/value`, MOVED HERE UNCHANGED. Two sources, compared on a clock rather than on
a precedence rule, and the clock is what makes this correct: the obvious shape — "a fetched
live export beats a run table" — is wrong on a real store whenever the newest run table was
written after the newest live fetch, which would serve a stale figure for every SKU both
files carry. Every reading therefore carries the second it was taken and the newest wins,
the same rule `store/master.py:Listing.observe_live` applies to `live` against `live_as_of`
(D87, amended).

  run tables    `runs/<n>/pricing.json`, at the table's own mtime — a join already
                establishes that this is the moment it last read an export, and that every
                figure under `snap` came out of it.
  live exports  the newest file under `inventory/.live`, at the stamp in its name. Read
                through `pipeline/tcgcsv.py:read_export` like every other export in this
                repo — never `split(",")`, which is a hard rule and not a style note.

MEASURED, ON THE OWNER'S STORE, WHICH IS WHY BOTH ARE HERE (the measurement this function's
predecessor was built to explain, unchanged by the move): run tables alone priced 1,823 of
2,245 cards on hand (81.2%), the newest live export alone 1,584 (70.6%), and the two together
1,855 (82.6%). The 32 cards the second source adds are cards whose run predates a listing —
and the freshness it brings reaches every SKU both files hold.

IT NEVER RAISES. A run directory half-written, a live export that will not parse, a `snap`
with no `market` cell — each costs its own rows and none of them costs the walk. What a
caller gets instead is a `Source` list saying which files actually answered, so a thin
reading is legible as a thin reading rather than as a store with no valuable cards in it.

WHY THIS IS A PIPELINE MODULE AND NOT A SERVER ONE. `server/` sits above `cli/`, `pipeline/`
and `store/` in this repo's layering — it imports them, never the reverse — and
`pkmnscan readings adopt` (`cli/cmd_readings.py`) has to run this walk with no server in
sight. So it lives here, one layer down from where it used to run, and
`server/pipeline_routes.py` no longer needs any of this: `_readings()` there is a plain
`SELECT` against the table this walk fills.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pipeline import tcgcsv
from store import files
from store.readings import KIND_LIVE, KIND_RUN, Reading, Source

# `cli/runs.py:PRICING`, duplicated rather than imported. `pipeline/` sits below `cli/` in
# this repo's layering (store <- pipeline <- cli <- server), so `cli/runs.py` — which also
# names `manifest.json`, `decisions.json` and every other run-directory filename — is not
# reachable from here. The string is the one fact that must agree; both spellings are this
# literal, and a run directory that renamed its join table would need to change here too.
RUN_PRICING_FILENAME = "pricing.json"


def live_export_at(name: str) -> Optional[int]:
    """The UNIX second a fetched live export was taken, out of its own filename.

    THE NAME IS THE ONLY HONEST CLOCK HERE. `server/pipeline_routes.py:do_live_export` writes
    `live-tcgplayer-<YYYYMMDD>-<HHMMSS>.csv` from `datetime.now(timezone.utc)` at the moment
    of the fetch, and the file's mtime is the moment it was WRITTEN TO THIS DISK — the same
    second today, and a different one entirely for a file restored from a backup or copied
    between checkouts. The stamp travels with the bytes; the mtime does not.

    `None` for a name this cannot read rather than a guess, which puts the file behind every
    run table in `collect` instead of in front of them. A reading whose age is unknown must
    never win a comparison against one whose age is known.
    """
    stem = name[len(files.LIVE_PREFIX) :] if name.startswith(files.LIVE_PREFIX) else name
    stem = stem[:-4] if stem.endswith(".csv") else stem
    try:
        moment = datetime.strptime(stem, "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return int(moment.timestamp())


def reading_from_table(parsed: dict, *, at: int, source: str) -> Tuple[Dict[str, Reading], Optional[Source]]:
    """One run's ALREADY-PARSED `pricing.json` (or an equivalent in-memory dict of the same
    shape, `cli/cmd_join.py`'s `_pricing_table`'s own return value), at a caller-supplied
    `at`.

    PULLED OUT OF `_run_readings` SO A JOIN CAN CALL IT ON THE TABLE IT JUST BUILT, without a
    disk round trip and without a second, drifting copy of the row-reading rule (`cli/
    cmd_join.py`'s `_pricing_table` already returns exactly this `{"skus": [...]}` shape, with
    the same `sku`, `snap.market`, `name`, `set_name`, `condition` fields this function reads).
    `_run_readings` below still owns the file I/O and the mtime; this owns only the
    row-to-`Reading` rule, which is the part two callers now share.
    """
    found: Dict[str, Reading] = {}
    priced = 0
    for row in parsed.get("skus") or ():
        if not isinstance(row, dict):
            continue
        sku = str(row.get("sku") or "")
        market = (row.get("snap") or {}).get("market")
        if not sku or not market:
            continue
        priced += 1
        found[sku] = Reading(
            market=str(market),
            at=at,
            source=source,
            kind=KIND_RUN,
            name=row.get("name"),
            set_name=row.get("set_name"),
            condition=row.get("condition"),
        )
    source_row = Source(kind=KIND_RUN, name=source, at=at, skus=priced) if priced else None
    return found, source_row


def _run_readings(root: Path) -> Tuple[Dict[str, Reading], List[Source]]:
    """Every run's `pricing.json` under `root`, oldest to newest by directory name."""
    found: Dict[str, Reading] = {}
    sources: List[Source] = []
    if not root.is_dir():
        return found, sources
    for entry in sorted(root.iterdir()):
        table = entry / RUN_PRICING_FILENAME
        if not entry.is_dir() or not table.is_file():
            continue
        try:
            parsed = json.loads(table.read_text("utf-8"))
            at = int(table.stat().st_mtime)
        except (OSError, ValueError):
            continue
        run_found, run_source = reading_from_table(parsed, at=at, source=entry.name)
        for sku, candidate in run_found.items():
            here = found.get(sku)
            if here is None or candidate.at >= here.at:
                found[sku] = candidate
        if run_source is not None:
            sources.append(run_source)
    return found, sources


def reading_from_export(export, *, at: int, source: str) -> Tuple[Dict[str, Reading], Optional[Source]]:
    """One ALREADY-PARSED `tcgcsv.Export` (the object `tcgcsv.read_export` returns), at a
    caller-supplied `at`.

    `do_live_export` has this object in hand the moment it validates the fetch — this lets it
    skip a second parse of a file that can run to several MB at 50,000 listings, the same file
    it just wrote and just read once already.
    """
    found: Dict[str, Reading] = {}
    priced = 0
    for row in export.rows:
        sku = str(row.get(tcgcsv.SKU_COLUMN) or "")
        market = row.get(tcgcsv.MARKET_PRICE_COLUMN) or ""
        if not sku or not market.strip():
            continue
        priced += 1
        found[sku] = Reading(
            market=market.strip(),
            at=at,
            source=source,
            kind=KIND_LIVE,
            name=row.get(tcgcsv.NAME_COLUMN),
            set_name=row.get(tcgcsv.SET_COLUMN),
            condition=row.get(tcgcsv.CONDITION_COLUMN),
        )
    source_row = Source(kind=KIND_LIVE, name=source, at=at, skus=priced) if priced else None
    return found, source_row


def _newest_live_reading(directory: Path) -> Tuple[Dict[str, Reading], List[Source]]:
    """The newest file under `directory`, and only the newest — never the whole directory.

    `do_live_export` never sweeps that directory — the file is the evidence for the reading
    the store wrote off it — so it can hold every fetch this machine has ever made. Reading
    all of them would parse megabytes just to have the newest overwrite the rest by the clock
    `live_export_at` reads.
    """
    found: Dict[str, Reading] = {}
    sources: List[Source] = []
    fetched = sorted(directory.glob(f"{files.LIVE_PREFIX}*.csv")) if directory.is_dir() else []
    if not fetched:
        return found, sources
    newest = fetched[-1]
    at = live_export_at(newest.name)
    if at is None:
        return found, sources
    try:
        export = tcgcsv.read_export(newest)
    except (tcgcsv.MalformedCsv, OSError):
        return found, sources
    live_found, live_source = reading_from_export(export, at=at, source=newest.name)
    found.update(live_found)
    if live_source is not None:
        sources.append(live_source)
    return found, sources


def collect() -> Tuple[Dict[str, Reading], List[Source]]:
    """`sku -> the NEWEST market price this machine can read for it`, and where each source's
    reading came from. The whole two-source walk; see the module docstring for the rule.

    NEWEST WINS ACROSS BOTH SOURCES, computed by re-running `offer`'s comparison over both
    sets in one pass rather than merging two already-arbitrated dicts — a run table's SKU
    that ties the live export's `at` keeps the same "later source wins ties" rule the
    original single-pass version had (`>=`, not `>`), so a live export fetched in the same
    second as a run table's mtime still displaces it.
    """
    found: Dict[str, Reading] = {}

    def offer(sku: str, reading: Reading) -> None:
        here = found.get(sku)
        if here is None or reading.at >= here.at:
            found[sku] = reading

    sources: List[Source] = []

    run_found, run_sources = _run_readings(files.runs_dir())
    for sku, reading in run_found.items():
        offer(sku, reading)
    sources.extend(run_sources)

    live_found, live_sources = _newest_live_reading(files.inventory_dir() / files.LIVE_DIRNAME)
    for sku, reading in live_found.items():
        offer(sku, reading)
    sources.extend(live_sources)

    sources.sort(key=lambda source: source.at, reverse=True)
    return found, sources
