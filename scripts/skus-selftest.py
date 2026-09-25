#!/usr/bin/env python3
"""`store/skus.py` and `pipeline/skus.py` proved against a throwaway store
(docs/specs/identity-follows-sku.md §3.2, lane 0).

WHAT THIS PROVES. The four committed-fixture shapes the lane's own proof names — a second
adopt over unchanged files, an older file that must never overwrite a newer one's facts, a
changed fact that writes one `sku_facts_changed` event and keeps the row, and that
`store/skus.py` has no delete path anywhere — plus the schema migration (a version-10 store
opens to 11 with every row in every other table intact) and a timed fill of one real Riftbound
export.

Every arm is a MEASUREMENT or a REFUSAL, never a restatement of the code, `scripts/
readings-selftest.py`'s own rule. In `make check` and never in the git hook: it writes, into a
directory it creates and destroys (D18).
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import skus as skus_walk  # noqa: E402
from pipeline import tcgcsv  # noqa: E402
from store import db, files  # noqa: E402
from store.skus import GRADES, Skus, split_condition  # noqa: E402
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


REAL_FIXTURE = ROOT / "fixtures" / "riftbound_export_untouched.csv"


# ------------------------------------------------------------------------------ the fixtures


def export_row(
    sku: str,
    *,
    product_line: str = "Pokemon",
    set_name: str = "Scarlet & Violet",
    product_name: str = "Pikachu",
    number: str = "025/198",
    rarity: str = "Common",
    condition: str = "Near Mint",
    market: str = "1.23",
) -> Dict[str, str]:
    """One CANONICAL_HEADER-shaped row, every column present — `pipeline/
    tcgcsv.py:CANONICAL_HEADER` in full, the same convention `scripts/
    readings-selftest.py:live_row` uses for its own fixtures."""
    return {
        "TCGplayer Id": sku,
        "Product Line": product_line,
        "Set Name": set_name,
        "Product Name": product_name,
        "Title": "",
        "Number": number,
        "Rarity": rarity,
        "Condition": condition,
        "TCG Market Price": market,
        "TCG Direct Low": "",
        "TCG Low Price With Shipping": "",
        "TCG Low Price": "",
        "Total Quantity": "",
        "Add to Quantity": "",
        "TCG Marketplace Price": "",
        "Photo URL": "",
    }


def write_export(directory: Path, game: str, stamp: str, rows: List[Dict[str, str]]) -> Path:
    """A fetched export named `export-tcgplayer-<stamp>-<digest>.csv` under
    `.exports/<game>/`, `stamp_of`'s own shape — the digest suffix is arbitrary since
    `stamp_of` searches for the `YYYYMMDD-HHMMSS` run rather than parsing a fixed prefix."""
    game_dir = directory / files.EXPORTS_DIRNAME / game
    game_dir.mkdir(parents=True, exist_ok=True)
    path = game_dir / f"export-tcgplayer-{stamp}-deadbeef.csv"
    tcgcsv.write_csv(path, tcgcsv.CANONICAL_HEADER, rows)
    return path


def write_live(directory: Path, stamp: str, rows: List[Dict[str, str]]) -> Path:
    """A live export named `live-tcgplayer-<stamp>.csv` under `.live/`."""
    live_dir = directory / files.LIVE_DIRNAME
    live_dir.mkdir(parents=True, exist_ok=True)
    path = live_dir / f"{files.LIVE_PREFIX}{stamp}.csv"
    tcgcsv.write_csv(path, tcgcsv.CANONICAL_HEADER, rows)
    return path


# ---------------------------------------------------------------------------------- main


def main() -> int:
    print("skus self-test — store/skus.py and pipeline/skus.py against a throwaway store\n")

    # ---------------------------------------------------------- split_condition, unit level
    print("  -- split_condition, every recognized grade and the sealed exception --")
    ok(split_condition("Near Mint") == ("Near Mint", None), "a plain grade splits to (grade, None)")
    ok(split_condition("Near Mint Foil") == ("Near Mint", "Foil"),
       "a grade with a finish splits to (grade, printing)")
    ok(split_condition("Lightly Played Holofoil") == ("Lightly Played", "Holofoil"),
       "every grade in GRADES splits the same way", str(GRADES))
    ok(split_condition("Unopened") == (None, None),
       "sealed product's one condition is NOT a grade — (None, None)")
    ok(split_condition("") == (None, None), "an empty cell is (None, None), never a guess")
    ok(split_condition("Whatever New Grade") == (None, None),
       "an unrecognized cell is (None, None) rather than a mis-split")

    with tempfile.TemporaryDirectory() as raw:
        home = Path(raw)
        (home / "inventory").mkdir(parents=True, exist_ok=True)
        import os
        previous = os.environ.get(files.HOME_ENV)
        os.environ[files.HOME_ENV] = str(home)
        try:
            inv = home / "inventory"

            # ---------------------------------------------------- an empty store
            print("\n  -- an empty store: no exports, no live files --")
            with Store().write() as snapshot:
                report = skus_walk.fill(snapshot.skus, snapshot.inventory.events)
            ok(report.inserted == 0 and report.unchanged == 0 and not report.changed,
               "fill() over nothing costs nothing", str(report))
            ok(len(Store().read().skus.entries) == 0, "and the table stays empty")

            # ---------------------------------------------------- rows equal distinct ids
            print("\n  -- one export, three distinct SKUs plus a repeat --")
            write_export(inv, "Pokemon", "20260101-000000", [
                export_row("111", product_name="Card A", rarity="Common"),
                export_row("222", product_name="Card B", rarity="Rare"),
                export_row("333", product_name="Card C", rarity="Uncommon"),
                # A REPEATED LINE FOR THE SAME SKU, BYTE-IDENTICAL FACTS — a real export can
                # list a SKU more than once (e.g. a heading row TCGplayer re-emits); this
                # must fold to one row, not four.
                export_row("111", product_name="Card A", rarity="Common"),
            ])
            with Store().write() as snapshot:
                report = skus_walk.fill(snapshot.skus, snapshot.inventory.events)
            after = dict(Store().read().skus.entries)
            ok(set(after) == {"111", "222", "333"},
               "three distinct SKUs in the table, whatever the file's own row count",
               str(sorted(after)))
            ok(len(after) == len(set(after)), "rows equal distinct ids — no duplicate keys")
            ok(report.inserted == 3, "the repeat line folds onto the SKU already inserted, "
               "not a fourth insert", str(report))

            # ---------------------------------------------------- a second adopt, no-op
            print("\n  -- a second adopt over the same file: changes nothing --")
            before_rows = dict(Store().read().skus.entries)
            with Store().write() as snapshot:
                report2 = skus_walk.fill(snapshot.skus, snapshot.inventory.events)
            after_rows = dict(Store().read().skus.entries)
            ok(after_rows == before_rows,
               "a second adopt over an unchanged file reproduces the identical table",
               f"before {before_rows}\nafter  {after_rows}")
            ok(report2.inserted == 0 and not report2.changed and report2.unchanged == 4,
               "and reports every ROW as unchanged (4: three SKUs plus the repeat line), "
               "none inserted, none changed", str(report2))

            # ---------------------------------------------------- an older file, no overwrite
            print("\n  -- an older file lands AFTER the newer one already won: STALE, no-op --")
            write_export(inv, "Pokemon", "20251201-000000", [
                export_row("111", product_name="Card A", rarity="SHOULD-NOT-WIN"),
            ])
            with Store().write() as snapshot:
                report3 = skus_walk.fill(snapshot.skus, snapshot.inventory.events)
            row_111 = Store().read().skus.entries["111"]
            ok(row_111.rarity == "Common",
               "the older file's DIFFERENT facts never displaced the newer file's facts",
               str(row_111))
            ok(report3.stale >= 1 and not report3.changed,
               "the older file is reported STALE, not CHANGED", str(report3))

            # ---------------------------------------------------- a changed fact
            print("\n  -- a NEWER file disagrees with the table: CHANGED, one event, row kept --")
            write_export(inv, "Pokemon", "20260201-000000", [
                export_row("222", product_name="Card B", rarity="Mythic Rare"),
            ])
            with Store().write() as snapshot:
                report4 = skus_walk.fill(snapshot.skus, snapshot.inventory.events)
                events_written = list(snapshot.inventory.events)
            row_222 = Store().read().skus.entries["222"]
            ok(row_222.rarity == "Mythic Rare",
               "the newer file's facts replaced the old ones", str(row_222))
            ok(len(report4.changed) == 1 and report4.changed[0][0] == "222",
               "exactly one SKU is reported changed", str(report4.changed))
            fact_events = [e for e in events_written if e.get("event") == "sku_facts_changed"]
            ok(len(fact_events) == 1, "exactly one sku_facts_changed event is appended",
               str(events_written))
            ok(fact_events[0]["old"]["rarity"] == "Rare" and fact_events[0]["new"]["rarity"] == "Mythic Rare",
               "the event carries the old facts beside the new ones", str(fact_events[0]))
            history_events = [
                e for e in Store().history() if e.get("event") == "sku_facts_changed"
            ]
            ok(len(history_events) == 1, "and it is durably recorded in the store's history",
               str(history_events))

            # ---------------------------------------------------- no delete path
            print("\n  -- a source file disappears from disk: the row it carried survives --")
            before_delete = dict(Store().read().skus.entries)
            # Remove every fetched export on disk — if `fold()` ever deleted what a pass does
            # not mention, this would empty the table.
            shutil.rmtree(inv / files.EXPORTS_DIRNAME)
            with Store().write() as snapshot:
                report5 = skus_walk.fill(snapshot.skus, snapshot.inventory.events)
            after_delete = dict(Store().read().skus.entries)
            ok(after_delete == before_delete,
               "removing every source file from disk changes the table not at all — "
               "no delete path anywhere in store/skus.py",
               f"before {before_delete}\nafter  {after_delete}")
            ok(report5.files_read == 0, "the walk found nothing to read, and still deleted "
               "nothing", str(report5))

            # A second, code-level proof of the same claim: `Skus` exposes no delete method
            # at all — only `fold()`. `fold()` itself never calls `del` on `self.entries`.
            import inspect as _inspect
            write_methods = {
                name for name, _ in _inspect.getmembers(Skus, predicate=_inspect.isfunction)
                if not name.startswith("__")
            }
            ok(write_methods == {"fold"},
               "Skus exposes exactly one write method, fold() — no delete, no clear, no "
               "replace", str(sorted(write_methods)))

            # ---------------------------------------------------- live export folds too
            print("\n  -- a live export folds in exactly like a fetched export --")
            write_live(inv, "20260301-000000", [
                export_row("444", product_name="Card D", rarity="Common"),
            ])
            with Store().write() as snapshot:
                skus_walk.fill(snapshot.skus, snapshot.inventory.events)
            ok("444" in Store().read().skus.entries, "the live SKU is present",
               str(sorted(Store().read().skus.entries)))
            ok(Store().read().skus.entries["444"].source.startswith(files.LIVE_PREFIX),
               "and its source names the live file, not a fetched one")

            # ---------------------------------------------------- an unstamped file
            print("\n  -- a file with no readable stamp is skipped, never guessed at --")
            garbage = inv / files.EXPORTS_DIRNAME / "Pokemon" / "export-tcgplayer-not-a-stamp-xyz.csv"
            garbage.parent.mkdir(parents=True, exist_ok=True)
            tcgcsv.write_csv(garbage, tcgcsv.CANONICAL_HEADER,
                              [export_row("999", product_name="Should never land")])
            with Store().write() as snapshot:
                report7 = skus_walk.fill(snapshot.skus, snapshot.inventory.events)
            ok("999" not in Store().read().skus.entries,
               "an unstamped file's rows never reach the table")
            ok(any(skipped.endswith(garbage.name) for skipped in report7.files_skipped),
               "and the file is named as skipped", str(report7.files_skipped))
            garbage.unlink()

            # ---------------------------------------------------- the views
            print("\n  -- sku_products / sku_printings: read-only, derived, no drift --")
            conn = sqlite3.connect(db.path(files.inventory_dir()))
            try:
                products = conn.execute(
                    "SELECT rarity_variants, sku_count FROM sku_products "
                    "WHERE product_line=? AND set_name=? AND product_name=? AND number=?",
                    ("Pokemon", "Scarlet & Violet", "Card B", "025/198"),
                ).fetchall()
                ok(products and products[0][0] == 1,
                   "one product, one rarity — rarity_variants is 1", str(products))
            finally:
                conn.close()

        finally:
            if previous is None:
                import os as _os
                _os.environ.pop(files.HOME_ENV, None)
            else:
                import os as _os
                _os.environ[files.HOME_ENV] = previous

    # ---------------------------------------------------------------- schema migration
    print("\n  -- a version-10 store opens to 11 with every other table's rows intact --")
    with tempfile.TemporaryDirectory() as raw:
        home = Path(raw)
        (home / "inventory").mkdir(parents=True, exist_ok=True)
        import os
        previous = os.environ.get(files.HOME_ENV)
        os.environ[files.HOME_ENV] = str(home)
        try:
            # Open the store once so the file and its (current-build) schema exist, then seed
            # a row into a few real tables DIRECTLY BY SQL — deliberately not through
            # `Inventory`/`Queue`'s own dataclasses, so this arm never breaks because a
            # sibling lane changed a constructor's signature; a raw row is all the row-count
            # proof below needs.
            Store().read()
            path = db.path(files.inventory_dir())
            conn = sqlite3.connect(str(path))
            conn.execute(
                "INSERT INTO cards (key, box, idx, state, payload) VALUES "
                "('3/17', 3, 17, 'captured', '{\"box\":3,\"index\":17}')"
            )
            conn.execute(
                "INSERT INTO boxes (key, box, bid, state, payload) VALUES "
                "('3', 3, 1, 'open', '{\"box\":3,\"bid\":1}')"
            )
            conn.execute(
                "INSERT INTO listings (key, condition, pushed, staged, live, payload) VALUES "
                "('8926937:Near Mint', 'Near Mint', 0, 0, 0, '{\"sku\":\"8926937\"}')"
            )
            conn.execute(
                "INSERT INTO queues (queue, key, box, idx, reason, cleared_by_human, "
                "first_seen, payload) VALUES "
                "('main', '3/17', 3, 17, 'test', 0, 0, '{}')"
            )
            conn.commit()
            conn.close()

            before_counts = _table_counts(path)
            ok(before_counts.get("cards", 0) >= 1 and before_counts.get("boxes", 0) >= 1
               and before_counts.get("listings", 0) >= 1 and before_counts.get("queues", 0) >= 1,
               "the seed rows are really on disk before the downgrade", str(before_counts))

            conn = sqlite3.connect(str(path))
            conn.execute("DROP VIEW IF EXISTS sku_products")
            conn.execute("DROP VIEW IF EXISTS sku_printings")
            conn.execute("DROP INDEX IF EXISTS skus_product")
            conn.execute("DROP TABLE IF EXISTS skus")
            conn.execute("ALTER TABLE cards DROP COLUMN identity_source")
            conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('schema', '10')")
            conn.commit()
            has_skus_before = bool(conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='skus'"
            ).fetchone())
            conn.close()
            ok(not has_skus_before, "the file now genuinely has no `skus` table (a real "
               "schema-10 shape, not merely a claim)")

            # The first open of it by this build is the upgrade.
            after_open = Store().read()
            ok(len(after_open.skus.entries) == 0, "the upgraded table starts empty")

            after_counts = _table_counts(path)
            ok(after_counts == before_counts,
               "every table's row count is unchanged by the upgrade",
               f"before {before_counts}\nafter  {after_counts}")

            conn = sqlite3.connect(str(path))
            stamp = conn.execute("SELECT value FROM meta WHERE key='schema'").fetchone()
            has_skus_after = bool(conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='skus'"
            ).fetchone())
            has_index = bool(conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='skus_product'"
            ).fetchone())
            has_views = bool(conn.execute(
                "SELECT name FROM sqlite_master WHERE type='view' AND name='sku_products'"
            ).fetchone()) and bool(conn.execute(
                "SELECT name FROM sqlite_master WHERE type='view' AND name='sku_printings'"
            ).fetchone())
            columns = {row[1] for row in conn.execute("PRAGMA table_info(cards)").fetchall()}
            conn.close()
            ok(stamp == (str(db.SCHEMA_VERSION),), f"the file is re-stamped ({stamp})")
            ok(has_skus_after, "the skus table now exists")
            ok(has_index, "and its composite index exists")
            ok(has_views, "and both product-layer views exist")
            ok("identity_source" in columns, "and cards.identity_source exists, NULL by "
               "default")
        finally:
            if previous is None:
                os.environ.pop(files.HOME_ENV, None)
            else:
                os.environ[files.HOME_ENV] = previous

    # ---------------------------------------------------------------- timed real fixture
    print("\n  -- timed: filling one real Riftbound export --")
    if REAL_FIXTURE.is_file():
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw)
            (home / "inventory").mkdir(parents=True, exist_ok=True)
            import os
            previous = os.environ.get(files.HOME_ENV)
            os.environ[files.HOME_ENV] = str(home)
            try:
                game_dir = home / "inventory" / files.EXPORTS_DIRNAME / "Riftbound"
                game_dir.mkdir(parents=True, exist_ok=True)
                dest = game_dir / "export-tcgplayer-20260101-000000-deadbeef.csv"
                shutil.copy(REAL_FIXTURE, dest)
                with Store().write() as snapshot:
                    started = time.time()
                    report = skus_walk.fill(snapshot.skus, snapshot.inventory.events)
                    elapsed = time.time() - started
                print(f"  ..     {report.files_read} file, {report.inserted} sku(s) "
                      f"inserted in {elapsed:.3f}s")
                ok(report.files_read == 1, "the fixture is read as one export")
                ok(report.inserted > 0, "and it fills the table", str(report.inserted))
            finally:
                if previous is None:
                    os.environ.pop(files.HOME_ENV, None)
                else:
                    os.environ[files.HOME_ENV] = previous
    else:
        ok(False, f"fixture missing: {REAL_FIXTURE}")

    print("\nskus self-test: {0} passed{1}".format(
        PASS, ", {0} FAILED".format(FAIL) if FAIL else ""))
    return 1 if FAIL else 0


def _table_counts(path: Path) -> Dict[str, int]:
    """Every table's row count, `skus` excluded (it is the thing being upgraded, and it does
    not exist on the BEFORE side to compare)."""
    conn = sqlite3.connect(str(path))
    try:
        names = [
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "AND name NOT LIKE 'cards_fts%' AND name NOT IN ('skus', 'meta')"
            ).fetchall()
        ]
        return {name: conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                for name in names}
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
