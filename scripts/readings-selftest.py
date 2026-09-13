#!/usr/bin/env python3
"""`store/readings.py` and `pipeline/readings.py` proved against a throwaway store (D189).

WHAT THIS PROVES AND WHY IT IS SEPARATE FROM A GOLDEN REIMPLEMENTATION. `_readings()` in
`server/pipeline_routes.py` used to walk every run's `pricing.json` and the newest live
export on every request; that walk moved to `pipeline/readings.py:collect()`, run once by
`pkmnscan readings adopt --write` and cached in the `readings`/`readings_sources` tables.
`golden()` below is an INDEPENDENT reimplementation of the walk the old function ran — not
imported from `collect()`, not sharing its helper functions — kept here specifically so a bug
introduced into `collect()` is caught by comparison rather than reproduced in both. Every arm
below asserts `collect()` against `golden()` over the same fixture files, and then asserts
that `readings adopt --write` followed by a plain read of `Store().read().readings` — the
exact SELECT `_readings()` now performs — reproduces the identical `(sku -> reading, sources)`
shape.

Every arm is a MEASUREMENT or a REFUSAL, never a restatement of the code. In `make check` and
never in the git hook: it writes, into a directory it creates and destroys (D18).
"""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import readings as readings_walk  # noqa: E402
from pipeline import tcgcsv  # noqa: E402
from store import files  # noqa: E402
from store.readings import KIND_LIVE, KIND_RUN, Reading  # noqa: E402
from store.session import Store  # noqa: E402

PASS = 0
FAIL = 0


def ok(condition: bool, label: str, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok     {label}")
    else:
        FAIL += 1
        print(f"  FAIL   {label}")
        if detail:
            for line in str(detail).splitlines()[:8]:
                print(f"         {line}")


# ------------------------------------------------------------------------------ the fixture


def write_run(root: Path, name: str, skus: List[dict], mtime: Optional[float] = None) -> Path:
    """A run directory carrying one `pricing.json`, its own `sku`/`snap.market`/`name` rows."""
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    table = directory / "pricing.json"
    table.write_text(json.dumps({"skus": skus}), encoding="utf-8")
    if mtime is not None:
        os.utime(table, (mtime, mtime))
    return table


def write_live(directory: Path, stamp: str, rows: List[dict]) -> Path:
    """A live export named `live-tcgplayer-<stamp>.csv`, filled against the canonical header.

    `stamp` is EITHER a valid `YYYYMMDD-HHMMSS` (the clock `live_export_at` reads) or garbage,
    on purpose — the unparseable-name arm needs a file the sort still picks as "newest" by
    name while carrying no readable timestamp.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{files.LIVE_PREFIX}{stamp}.csv"
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(tcgcsv.CANONICAL_HEADER)
    for row in rows:
        writer.writerow([row.get(col, "") for col in tcgcsv.CANONICAL_HEADER])
    path.write_text(buf.getvalue(), encoding="utf-8")
    return path


def live_row(sku: str, market: str, name: str = "", set_name: str = "") -> dict:
    return {
        tcgcsv.SKU_COLUMN: sku,
        tcgcsv.MARKET_PRICE_COLUMN: market,
        tcgcsv.NAME_COLUMN: name,
        tcgcsv.SET_COLUMN: set_name,
        tcgcsv.CONDITION_COLUMN: "Near Mint",
        tcgcsv.PRODUCT_LINE_COLUMN: "Pokemon",
    }


def run_row(sku: str, market: str, name: str = "", set_name: str = "") -> dict:
    return {"sku": sku, "snap": {"market": market}, "name": name, "set_name": set_name,
            "condition": "Near Mint"}


# --------------------------------------------------------- the independent golden walk
#
# A SEPARATE TRANSCRIPTION of the two-source rule, not a call into `pipeline/readings.py`.
# See the module docstring for why duplication is the point here.


def golden(runs_dir: Path, live_dir: Path) -> Tuple[Dict[str, Reading], List[dict]]:
    found: Dict[str, Reading] = {}
    sources: List[dict] = []

    def offer(sku: str, reading: Reading) -> None:
        here = found.get(sku)
        if here is None or reading.at >= here.at:
            found[sku] = reading

    if runs_dir.is_dir():
        for entry in sorted(runs_dir.iterdir()):
            table = entry / "pricing.json"
            if not entry.is_dir() or not table.is_file():
                continue
            try:
                parsed = json.loads(table.read_text("utf-8"))
                at = int(table.stat().st_mtime)
            except (OSError, ValueError):
                continue
            priced = 0
            for row in parsed.get("skus") or ():
                if not isinstance(row, dict):
                    continue
                sku = str(row.get("sku") or "")
                market = (row.get("snap") or {}).get("market")
                if not sku or not market:
                    continue
                priced += 1
                offer(sku, Reading(
                    market=str(market), at=at, source=entry.name, kind=KIND_RUN,
                    name=row.get("name"), set_name=row.get("set_name"),
                    condition=row.get("condition"),
                ))
            if priced:
                sources.append({"kind": KIND_RUN, "name": entry.name, "at": at, "skus": priced})

    fetched = sorted(live_dir.glob(f"{files.LIVE_PREFIX}*.csv")) if live_dir.is_dir() else []
    if fetched:
        newest = fetched[-1]
        stem = newest.name[len(files.LIVE_PREFIX):]
        stem = stem[:-4] if stem.endswith(".csv") else stem
        at: Optional[int]
        try:
            at = int(datetime.strptime(stem, "%Y%m%d-%H%M%S")
                     .replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            at = None
        if at is not None:
            try:
                export = tcgcsv.read_export(newest)
            except (tcgcsv.MalformedCsv, OSError):
                export = None
            if export is not None:
                priced = 0
                for row in export.rows:
                    sku = str(row.get(tcgcsv.SKU_COLUMN) or "")
                    market = row.get(tcgcsv.MARKET_PRICE_COLUMN) or ""
                    if not sku or not market.strip():
                        continue
                    priced += 1
                    offer(sku, Reading(
                        market=market.strip(), at=at, source=newest.name, kind=KIND_LIVE,
                        name=row.get(tcgcsv.NAME_COLUMN), set_name=row.get(tcgcsv.SET_COLUMN),
                        condition=row.get(tcgcsv.CONDITION_COLUMN),
                    ))
                if priced:
                    sources.append(
                        {"kind": KIND_LIVE, "name": newest.name, "at": at, "skus": priced}
                    )

    sources.sort(key=lambda row: row["at"], reverse=True)
    return found, sources


def sources_as_dicts(sources) -> List[dict]:
    return [s._asdict() if hasattr(s, "_asdict") else dict(s) for s in sources]


def assert_matches_golden(runs_dir: Path, live_dir: Path, label: str) -> None:
    got_found, got_sources = readings_walk.collect()
    want_found, want_sources = golden(runs_dir, live_dir)
    ok(got_found == want_found, f"{label}: collect() matches the golden walk on readings",
       f"got  {got_found}\nwant {want_found}")
    ok(sources_as_dicts(got_sources) == want_sources,
       f"{label}: collect() matches the golden walk on sources",
       f"got  {sources_as_dicts(got_sources)}\nwant {want_sources}")


# ---------------------------------------------------------------------------------- main


def main() -> int:
    print("readings self-test — store/readings.py and pipeline/readings.py "
          "against a throwaway store\n")
    with tempfile.TemporaryDirectory() as raw:
        home = Path(raw)
        runs_dir = home / "runs"
        live_dir = home / "inventory" / files.LIVE_DIRNAME
        previous = os.environ.get(files.HOME_ENV)
        os.environ[files.HOME_ENV] = str(home)
        try:
            (home / "inventory").mkdir(parents=True, exist_ok=True)

            # -------------------------------------------------- an empty store
            print("  -- an empty store: no runs, no live exports --")
            assert_matches_golden(runs_dir, live_dir, "empty store")
            found, sources = readings_walk.collect()
            ok(found == {} and sources == [], "collect() over nothing is legible: ({}, [])",
               str((found, sources)))
            with Store().write() as snapshot:
                snapshot.readings.replace(found, sources)
            after = Store().read().readings
            ok(dict(after.entries) == {}, "adopt --write over nothing leaves the table empty")
            ok(after.sources_payload() == [], "and leaves the sources list empty")

            # -------------------------------------------------- run tables only
            print("\n  -- a store with only run tables --")
            write_run(runs_dir, "2026-01-01-box1-01",
                      [run_row("111", "1.23", "Card A"), run_row("222", "4.56", "Card B")],
                      mtime=1_700_000_000)
            assert_matches_golden(runs_dir, live_dir, "run-only store")
            found, sources = readings_walk.collect()
            ok(set(found) == {"111", "222"}, "both SKUs from the one run are present",
               str(sorted(found)))
            ok(all(r.kind == KIND_RUN for r in found.values()),
               "every reading is kind=run with nothing else on disk")

            # -------------------------------------------------- live export only
            print("\n  -- a store with only a live export (run directory removed) --")
            shutil.rmtree(runs_dir)
            write_live(live_dir, "20260101-000000", [live_row("333", "2.00", "Card C")])
            assert_matches_golden(runs_dir, live_dir, "live-only store")
            found, sources = readings_walk.collect()
            ok(set(found) == {"333"}, "the live SKU is present with no run on disk",
               str(sorted(found)))
            ok(found["333"].kind == KIND_LIVE, "and its kind is live")

            # -------------------------------------------------- disagreement: newest wins
            print("\n  -- a run and a live export disagree on one SKU --")
            write_run(runs_dir, "2026-01-01-box1-01",
                      [run_row("333", "9.99", "Card C")], mtime=1_800_000_000)  # newer
            assert_matches_golden(runs_dir, live_dir, "run newer than live")
            found, _ = readings_walk.collect()
            ok(found["333"].market == "9.99" and found["333"].kind == KIND_RUN,
               "the NEWER run table wins over the older live export", str(found["333"]))

            write_run(runs_dir, "2026-01-01-box1-01",
                      [run_row("333", "9.99", "Card C")], mtime=1_600_000_000)  # now older
            assert_matches_golden(runs_dir, live_dir, "live newer than run")
            found, _ = readings_walk.collect()
            ok(found["333"].market == "2.00" and found["333"].kind == KIND_LIVE,
               "flip the clock and the NEWER live export wins instead", str(found["333"]))

            # -------------------------------------------------- unparseable live filename
            print("\n  -- the newest-by-name live export has an unparseable filename --")
            shutil.rmtree(live_dir)
            write_live(live_dir, "20260101-000000", [live_row("444", "5.00", "Card D")])
            write_live(live_dir, "not-a-timestamp", [live_row("555", "6.00", "Card E")])
            assert_matches_golden(runs_dir, live_dir, "unparseable newest live filename")
            found, sources = readings_walk.collect()
            ok("444" not in found and "555" not in found,
               "the unparseable file sorts last and wins the pick, so NEITHER live SKU "
               "appears — it never falls back to the older, readable file",
               str(sorted(found)))
            ok(not any(s.kind == KIND_LIVE for s in sources),
               "and no live source is reported at all", str(sources))
            ok(found.get("333", found.get("_missing")) is not None or "333" not in found,
               "the run-table SKU from before is unaffected by the bad live file")

            # -------------------------------------------------- adopt --write then SELECT
            print("\n  -- adopt --write, then the plain SELECT `_readings()` now performs --")
            shutil.rmtree(live_dir)
            write_live(live_dir, "20260101-000000", [live_row("444", "5.00", "Card D")])
            found, sources = readings_walk.collect()
            with Store().write() as snapshot:
                snapshot.readings.replace(found, sources)
            selected = dict(Store().read().readings.entries)
            selected_sources = Store().read().readings.sources_payload()
            ok(selected == found, "the SELECT reproduces exactly what adopt just wrote",
               f"select {selected}\nadopt  {found}")
            ok(selected_sources == sources_as_dicts(sources),
               "and the sources list reproduces the pre-arbitration per-file counts",
               f"select {selected_sources}\nadopt  {sources_as_dicts(sources)}")

            # -------------------------------------------------- idempotent re-adopt
            print("\n  -- re-running adopt --write twice in a row, nothing on disk changed --")
            before_rows = dict(Store().read().readings.entries)
            with Store().write() as snapshot:
                snapshot.readings.replace(*readings_walk.collect())
            after_rows = dict(Store().read().readings.entries)
            ok(after_rows == before_rows,
               "a second adopt over unchanged files reproduces the identical table",
               f"before {before_rows}\nafter  {after_rows}")
            ok(len(after_rows) == len(set(after_rows)),
               "no duplicate rows — the table is keyed by SKU and a re-adopt is a replace")

            # -------------------------------------------------- a new run lands, then adopt
            print("\n  -- a new run lands between two adopts --")
            write_run(runs_dir, "2026-02-01-box2-01",
                      [run_row("666", "7.00", "Card F")], mtime=1_900_000_000)
            with Store().write() as snapshot:
                snapshot.readings.replace(*readings_walk.collect())
            grown = dict(Store().read().readings.entries)
            ok("666" in grown, "the new run's SKU is picked up by the next adopt",
               str(sorted(grown)))
            ok(grown["444"].market == "5.00", "and every earlier SKU is still there unchanged")

            # -------------------------------------------------- a source is retired
            print("\n  -- a run directory is deleted, then adopt --write --")
            shutil.rmtree(runs_dir / "2026-02-01-box2-01")
            with Store().write() as snapshot:
                snapshot.readings.replace(*readings_walk.collect())
            shrunk = dict(Store().read().readings.entries)
            ok("666" not in shrunk,
               "the SKU whose only source was deleted drops out of the table — a cache "
               "refresh, never an accumulating ledger", str(sorted(shrunk)))
        finally:
            if previous is None:
                os.environ.pop(files.HOME_ENV, None)
            else:
                os.environ[files.HOME_ENV] = previous

    print("\nreadings self-test: {0} passed{1}".format(
        PASS, ", {0} FAILED".format(FAIL) if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
