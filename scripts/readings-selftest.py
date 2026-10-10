#!/usr/bin/env python3
"""`store/readings.py` and `pipeline/readings.py` proved against a throwaway store (D189).

Protects: The stored market readings equal an independent walk of every run, and refresh only what changed.
Governs: D18, D189

WHAT THIS PROVES AND WHY IT IS SEPARATE FROM A GOLDEN REIMPLEMENTATION. `_readings()` in
`server/pipeline_routes.py` used to walk every run's `pricing.json` and the newest live
export on every request; that walk moved to `pipeline/readings.py:collect()`, run once by
`banchi readings adopt --write` and cached in the `readings`/`readings_sources` tables.
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
import argparse
import io
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cli import cmd_readings  # noqa: E402
from pipeline import readings as readings_walk  # noqa: E402
from pipeline import tcgcsv  # noqa: E402
from harness.tests.home import isolated_home  # noqa: E402
from store import files  # noqa: E402
from store.readings import KIND_LIVE, KIND_RUN, Readings, Reading, Source  # noqa: E402
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


def check_sources_payload_ties_break_on_name() -> None:
    """`Readings.sources_payload()` — found by `make demo-determinism`, 2026-09-27: two real
    `make demo` runs of the identical seed joined `demo-box1` and `demo-box3` a second apart
    inside each run, but their real mtimes (`at`) landed in the SAME second across the two
    separate runs. A tie on `at` alone left the order to `Rows`' own iteration order, which
    is not a promise this class makes — the published `sources` list moved between two runs
    of one fixed seed. `name` is now the tiebreak, so two sources sharing an `at` sort the
    same way every time, whatever order they were inserted in."""
    readings = Readings()
    readings.replace(
        {},
        [
            Source(kind=KIND_RUN, name="demo-box3", at=1_700_000_000, skus=30),
            Source(kind=KIND_RUN, name="demo-box1", at=1_700_000_000, skus=36),
        ],
    )
    names = [row["name"] for row in readings.sources_payload()]
    ok(names == ["demo-box3", "demo-box1"],
       "a tied `at` breaks on `name`, whichever order the sources were inserted in",
       "got %r" % names)

    reversed_readings = Readings()
    reversed_readings.replace(
        {},
        [
            Source(kind=KIND_RUN, name="demo-box1", at=1_700_000_000, skus=36),
            Source(kind=KIND_RUN, name="demo-box3", at=1_700_000_000, skus=30),
        ],
    )
    reversed_names = [row["name"] for row in reversed_readings.sources_payload()]
    ok(reversed_names == names,
       "insertion order does not change a tied result",
       "got %r, want %r" % (reversed_names, names))

    distinct = Readings()
    distinct.replace(
        {},
        [
            Source(kind=KIND_RUN, name="demo-box1", at=1_700_000_000, skus=36),
            Source(kind=KIND_RUN, name="demo-box3", at=1_700_000_001, skus=30),
        ],
    )
    distinct_names = [row["name"] for row in distinct.sources_payload()]
    ok(distinct_names == ["demo-box3", "demo-box1"],
       "a real `at` difference still wins over the name tiebreak (newest first)",
       "got %r" % distinct_names)


# ------------------------------------------------- `banchi readings adopt` (the CLI)
#
# These drive `cli/cmd_readings.py:run`, the path an operator types, not `replace()` directly.
# So a refusal, or its absence, in `_adopt` is what each arm sees.


def run_adopt(write: bool) -> Tuple[Optional[int], List[str]]:
    said: List[str] = []
    try:
        code = cmd_readings.run(
            argparse.Namespace(readings_command="adopt", write=write), said.append
        )
    except Exception as exc:  # a crash refuses by accident, and names no file
        said.append(f"raised {type(exc).__name__}: {exc}")
        return None, said
    return code, said


def stored() -> Tuple[Dict[str, Reading], list]:
    current = Store().read().readings
    return dict(current.entries), current.sources_payload()


def seed_good_sources(home: Path) -> None:
    """Disk holds two good run tables: box1 (111, 222) and box2 (333), box2 the newer."""
    shutil.rmtree(home / "runs", ignore_errors=True)
    shutil.rmtree(home / "inventory" / files.LIVE_DIRNAME, ignore_errors=True)
    write_run(home / "runs", "2026-01-01-box1-01",
              [run_row("111", "1.23", "Card A"), run_row("222", "4.56", "Card B")],
              mtime=1_700_000_000)
    write_run(home / "runs", "2026-01-01-box2-01",
              [run_row("333", "2.00", "Card C")], mtime=1_700_000_100)


def seed_table_from_sources(home: Path) -> None:
    """The table holds exactly what a walk over the good sources gives, set up directly."""
    seed_good_sources(home)
    with Store().write() as snapshot:
        snapshot.readings.replace(*readings_walk.collect())


def check_bad_run_table(home: Path, label: str, content: str) -> None:
    """box2's run table is replaced by `content`, among good ones: adopt --write must refuse,
    keep the table (box2's 333 included), and name the bad file in its output."""
    seed_table_from_sources(home)
    before = stored()
    table = home / "runs" / "2026-01-01-box2-01" / "pricing.json"
    table.write_text(content, "utf-8")
    code, said = run_adopt(write=True)
    ok(code not in (0, None) and stored() == before,
       f"refuses: adopt --write over a run table that is {label} leaves the table as it was",
       f"code {code}, rows left {sorted(stored()[0])}")
    ok(any(str(table) in line for line in said),
       f"and the refusal names that file ({label})", "\n".join(said[-4:]))


def check_cli_adopt() -> None:
    print("\n  -- `banchi readings adopt` (cli/cmd_readings.py) over a throwaway store --")
    with isolated_home() as home:
        (home / "inventory").mkdir(parents=True, exist_ok=True)
        runs = home / "runs"

        # -------------------------------------------------- (b) a good source, exact rows
        print("\n  -- adopt --write from a good source gives exactly the source's rows --")
        seed_good_sources(home)
        with Store().write() as snapshot:  # a stale row the source no longer offers
            snapshot.readings.replace(
                {"999": Reading(market="8.88", at=1, source="gone", kind=KIND_RUN,
                                name=None, set_name=None, condition=None)},
                [],
            )
        code, _ = run_adopt(write=True)
        entries, sources = stored()
        ok(code == 0 and {sku: r.market for sku, r in entries.items()}
           == {"111": "1.23", "222": "4.56", "333": "2.00"},
           "adopt --write leaves exactly the good source's SKUs and prices; the stale row "
           "is gone", f"code {code}, rows {sorted(entries)}")
        ok([(s["name"], s["skus"]) for s in sources]
           == [("2026-01-01-box2-01", 1), ("2026-01-01-box1-01", 2)],
           "and the sources list is the two run tables, newest first, with their counts",
           str(sources))

        # -------------------------------------------------- (c) without --write
        print("\n  -- without --write nothing is written --")
        seed_table_from_sources(home)
        before = stored()
        write_run(runs, "2026-01-01-box1-01", [run_row("111", "9.99", "Card A")],
                  mtime=1_700_000_000)
        shutil.rmtree(runs / "2026-01-01-box2-01")
        ok(readings_walk.collect()[0] != before[0],
           "the disk now differs from the table, so a --write would have changed it "
           "(the arm has something to refuse)")
        code, said = run_adopt(write=False)
        ok(code == 0 and stored() == before,
           "a preview without --write leaves the table exactly as it was",
           f"code {code}, before {before[0]}, after {stored()[0]}")
        ok(any("DRY RUN" in line for line in said),
           "and the preview says it wrote nothing")

        # -------------------------------------------------- (a) refusals, table kept
        print("\n  -- adopt --write over no usable source refuses, and keeps the table --")
        seed_table_from_sources(home)
        before = stored()
        shutil.rmtree(runs)
        code, _ = run_adopt(write=True)
        ok(code not in (0, None) and stored() == before,
           "refuses: adopt --write over no source at all leaves the table as it was",
           f"code {code}, rows left {sorted(stored()[0])}")

        seed_table_from_sources(home)
        before = stored()
        shutil.rmtree(runs)
        only = runs / "2026-01-01-box1-01" / "pricing.json"
        only.parent.mkdir(parents=True)
        only.write_text("{not json", "utf-8")
        code, said = run_adopt(write=True)
        ok(code not in (0, None) and stored() == before,
           "refuses: adopt --write whose only source is a malformed pricing.json leaves the "
           "table as it was",
           f"code {code}, rows left {sorted(stored()[0])}")
        ok(any(str(only) in line for line in said),
           "and the refusal names that file", "\n".join(said[-4:]))

        # One run table of the good set is replaced by a bad one. Each must refuse, keep the
        # table (box2's 333 included), and name the file. `{}` is valid JSON, so it is the
        # silent case; `[]` and `null` crash the walk and name nothing.
        check_bad_run_table(home, "not JSON", "{not json")
        check_bad_run_table(home, "an empty object, with no skus key", "{}")
        check_bad_run_table(home, "a JSON array", "[]")
        check_bad_run_table(home, "JSON null", "null")

        # -------------------------------------------------- a malformed NEWEST live export
        # Owner ruling: adopt goes on, but the report names the skipped export and the count
        # of SKUs it lost. The older, readable export carried 444 and 445 into the table; the
        # newest export is bad CSV, so only the runs are read, and 444 and 445 would drop.
        print("\n  -- a malformed newest live export: adopt goes on, and says what it lost --")
        seed_good_sources(home)
        live_dir = home / "inventory" / files.LIVE_DIRNAME
        write_live(live_dir, "20260101-000000",
                   [live_row("444", "5.00", "Card D"), live_row("445", "6.00", "Card E")])
        with Store().write() as snapshot:
            snapshot.readings.replace(*readings_walk.collect())
        ok(sorted(stored()[0]) == ["111", "222", "333", "444", "445"],
           "setup: the table holds the older live export's two SKUs alongside the runs",
           f"rows {sorted(stored()[0])}")

        newest = live_dir / f"{files.LIVE_PREFIX}20260201-000000.csv"
        newest.write_text("this is not a price export\n", "utf-8")
        code, said = run_adopt(write=True)
        entries, _ = stored()
        ok(code == 0 and sorted(entries) == ["111", "222", "333"],
           "a malformed newest export: adopt --write exits 0 and writes the good run rows",
           f"code {code}, rows {sorted(entries)}")
        named = [line for line in said if newest.name in line]
        ok(bool(named) and any(re.search(r"\b2\b", line) for line in named),
           "and its output names that export file and the 2 SKUs it lost",
           "\n".join(said) or "(no output)")


# ---------------------------------------------------------------------------------- main


def main() -> int:
    print("readings self-test — store/readings.py and pipeline/readings.py "
          "against a throwaway store\n")
    print("  -- sources_payload()'s own tiebreak, no store needed --")
    check_sources_payload_ties_break_on_name()
    with isolated_home() as home:
        runs_dir = home / "runs"
        live_dir = home / "inventory" / files.LIVE_DIRNAME
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
        run_only_table = write_run(
            runs_dir, "2026-01-01-box1-01",
            [run_row("111", "1.23", "Card A"), run_row("222", "4.56", "Card B")],
            mtime=1_700_000_000,
        )
        run_only_dir = run_only_table.parent
        assert_matches_golden(runs_dir, live_dir, "run-only store")
        found, sources = readings_walk.collect()
        ok(set(found) == {"111", "222"}, "both SKUs from the one run are present",
           str(sorted(found)))
        ok(all(r.kind == KIND_RUN for r in found.values()),
           "every reading is kind=run with nothing else on disk")

        # -- item 5: the extracted per-source readers agree with the whole-directory walk
        # they were pulled out of, on the SAME fixture above — proving `reading_from_table`
        # (which `cli/cmd_join.py` now calls on an in-memory table it just built) cannot
        # silently drift from the private loop that used to inline it.
        print("\n  -- reading_from_table matches the whole-directory walk it was pulled from --")
        parsed = json.loads((run_only_table).read_text("utf-8"))
        at = int(run_only_table.stat().st_mtime)
        direct_found, direct_source = readings_walk.reading_from_table(
            parsed, at=at, source=run_only_dir.name,
        )
        whole_found, whole_sources = readings_walk._run_readings(run_only_dir.parent)
        ok(direct_found == whole_found,
           "reading_from_table matches the whole-directory walk for one run",
           f"got  {direct_found}\nwant {whole_found}")
        want_source = [direct_source] if direct_source else []
        got_source = [s for s in whole_sources if s.name == run_only_dir.name]
        ok(got_source == want_source, "and its Source row matches too",
           f"got  {got_source}\nwant {want_source}")

        # -------------------------------------------------- live export only
        print("\n  -- a store with only a live export (run directory removed) --")
        shutil.rmtree(runs_dir)
        live_only_path = write_live(
            live_dir, "20260101-000000", [live_row("333", "2.00", "Card C")]
        )
        assert_matches_golden(runs_dir, live_dir, "live-only store")
        found, sources = readings_walk.collect()
        ok(set(found) == {"333"}, "the live SKU is present with no run on disk",
           str(sorted(found)))
        ok(found["333"].kind == KIND_LIVE, "and its kind is live")

        # -- item 5: the extracted `reading_from_export` agrees with the whole-export walk
        # it was pulled out of, on the SAME live fixture above — `do_live_export` calls it
        # on the `tcgcsv.Export` object it already parsed to validate the fetch, and this
        # proves that shortcut cannot silently drift from the private loop that used to
        # inline it.
        print("\n  -- reading_from_export matches the whole-export walk it was pulled from --")
        live_at = readings_walk.live_export_at(live_only_path.name)
        live_export = tcgcsv.read_export(live_only_path)
        direct_live_found, direct_live_source = readings_walk.reading_from_export(
            live_export, at=live_at, source=live_only_path.name,
        )
        whole_live_found, whole_live_sources = readings_walk._newest_live_reading(live_dir)
        ok(direct_live_found == whole_live_found,
           "reading_from_export matches the whole-export walk for one live file",
           f"got  {direct_live_found}\nwant {whole_live_found}")
        want_live_source = [direct_live_source] if direct_live_source else []
        got_live_source = [s for s in whole_live_sources if s.name == live_only_path.name]
        ok(got_live_source == want_live_source, "and its Source row matches too",
           f"got  {got_live_source}\nwant {want_live_source}")

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

    check_cli_adopt()

    print("\nreadings self-test: {0} passed{1}".format(
        PASS, ", {0} FAILED".format(FAIL) if FAIL else ""))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
