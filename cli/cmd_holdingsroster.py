"""`banchi holdings-roster <csv>` - the owner's investment roster valued at this store's prices
(D324, `docs/specs/holdings-roster.md`). A one-off, read-only report: no screen, no write.

The store opens through `store/db.py:open_read_only`, which never migrates and never writes.
`--store PATH` names a sqlite file instead of this checkout's own store. The `skus` rows and the
price archive are read through the same `TableSpec` parse the store itself uses.
"""

from __future__ import annotations

from pathlib import Path

from pipeline.rosterholdings import SkuRow, build_roster_report, read_roster
from store import db, files
from store.pricearchive import PriceArchive
from store.rows import Rows
from store.skus import Skus


def run(args, say) -> int:
    store_path = Path(args.store) if args.store else db.path(files.inventory_dir())
    if not store_path.exists():
        say(f"No store at {store_path}.")
        return 1
    with open(args.csv, newline="", encoding="utf-8-sig") as handle:
        try:
            roster = read_roster(handle)
        except ValueError as exc:
            say(str(exc))
            return 1
    conn = db.open_read_only(store_path)
    try:
        skus = [
            SkuRow(key, row.set_name, row.product_name, row.number, row.condition, row.printing)
            for key, row in Rows(Skus.ENTRIES, source=db.source(conn, "skus"), track=False).items()
        ]
        archive = PriceArchive(
            entries=Rows(PriceArchive.ENTRIES, source=db.source(conn, "price_history"), track=False))
        priced_ids = {int(r[0]) for r in conn.execute("SELECT DISTINCT product_id FROM price_history")
                      if r[0] is not None}
        say(build_roster_report(roster, skus, archive, priced_ids).render())
    finally:
        conn.close()
    return 0
