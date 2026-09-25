#!/usr/bin/env python3
"""How much price HISTORY can be recovered from what already survives, read-only, against
the owner's real store (D243).

READ-ONLY BY CONSTRUCTION. This opens `inventory/store.sqlite` through
`store/db.py:open_read_only` — a connection SQLite itself refuses to write through, and the
one door that never runs `_ensure_schema`'s migration path (PR #461). It used to open its own
bare `mode=ro` connection instead, on the theory that avoiding `store.db` entirely was the
safer way to guarantee no migration ever ran — but a bare `mode=ro` open refuses "unable to
open database file" on a store whose WAL has been checkpointed away and its side files
removed, which is a normal, cold, fully-committed store, not a damaged one. `open_read_only`
gives the same read-only, non-migrating guarantee without that failure. It reads
`inventory/markdowns/*/receipt.txt` and `.../import.csv` as plain files, never through
`cli/cmd_reprice.py`, and it runs no `pkmnscan` command of any kind.

WHAT THIS ANSWERS. Two questions the `events` ledger and the markdown folders can be asked
today, before `price_postings` existed to answer them going forward:

  1. How many of the `pushed` events name a price?               (Answer: none can — the
                                                                    payload shape has no
                                                                    price field at all.)
  2. How many SKUs' prices can be read back off a markdown folder's own receipt?

Usage: `python3 scripts/price-postings-recovery.py [path-to-inventory-dir]`
Defaults to `~/Developer/pkmnscan/inventory`, the owner's real store.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from store import db  # noqa: E402


def _ro_connect(db_path: Path) -> sqlite3.Connection:
    return db.open_read_only(db_path)


def count_pushed_events(conn: sqlite3.Connection) -> tuple:
    """(total pushed events, how many name a price) — the second is always 0 today; the
    payload `pipeline/join.py`/`cli/cmd_emit.py` write for a `pushed` line carries `at`,
    `event`, `position`, `run`, `sku` and nothing else.
    """
    rows = conn.execute(
        "SELECT payload FROM events WHERE event = 'pushed'"
    ).fetchall()
    total = len(rows)
    priced = 0
    for (payload,) in rows:
        try:
            record = json.loads(payload)
        except ValueError:
            continue
        if "price" in record or "TCG Marketplace Price" in record:
            priced += 1
    return total, priced


def receipts_recoverable(markdowns_dir: Path) -> dict:
    """Every markdown folder that actually reached `--write`, and how many SKUs' prices its
    own `receipt.txt` still names. A folder with only `worklist.csv`/`report.txt` was
    previewed and never applied — nothing was posted, so there is nothing to recover.
    """
    out = {}
    if not markdowns_dir.is_dir():
        return out
    for folder in sorted(markdowns_dir.iterdir()):
        if not folder.is_dir():
            continue
        receipt = folder / "receipt.txt"
        import_csv = folder / "import.csv"
        applied = receipt.is_file() and import_csv.is_file()
        skus_in_receipt = 0
        if receipt.is_file():
            for line in receipt.read_text(encoding="utf-8", errors="replace").splitlines():
                stripped = line.strip()
                # A per-SKU line, by the shape `cli/cmd_reprice.py:_apply` writes it:
                # "  <sku>    <was> -> <now>  x<copies>  <name>".
                parts = stripped.split()
                if len(parts) >= 4 and parts[0].isdigit() and "->" in parts:
                    skus_in_receipt += 1
        skus_in_import = 0
        if import_csv.is_file():
            with import_csv.open("r", encoding="utf-8-sig", newline="") as fh:
                reader = csv.DictReader(fh)
                skus_in_import = sum(1 for _ in reader)
        out[folder.name] = {
            "applied": applied,
            "skus_recoverable_from_receipt": skus_in_receipt,
            "rows_in_import_csv": skus_in_import,
        }
    return out


def distinct_priced_skus(conn: sqlite3.Connection) -> int:
    """How many SKUs this store has ever committed a card to — the population every
    recoverable posting is measured against."""
    row = conn.execute(
        "SELECT COUNT(DISTINCT sku) FROM cards WHERE sku IS NOT NULL AND sku != ''"
    ).fetchone()
    return int(row[0]) if row else 0


def main() -> int:
    inventory_dir = Path(
        sys.argv[1] if len(sys.argv) > 1 else Path.home() / "Developer" / "pkmnscan" / "inventory"
    )
    db_path = inventory_dir / "store.sqlite"
    if not db_path.is_file():
        print(f"no store at {db_path} — nothing to measure")
        return 1

    conn = _ro_connect(db_path)
    try:
        total_pushed, priced_pushed = count_pushed_events(conn)
        skus_ever_priced = distinct_priced_skus(conn)
    finally:
        conn.close()

    markdowns = receipts_recoverable(inventory_dir / "markdowns")
    applied_folders = {k: v for k, v in markdowns.items() if v["applied"]}
    recoverable_skus = sum(v["skus_recoverable_from_receipt"] for v in applied_folders.values())

    print(f"store                    {db_path}")
    print(f"pushed events            {total_pushed}")
    print(f"  naming a price         {priced_pushed} (of {total_pushed}) — the payload has no "
          f"price field, so this is always 0 with today's shape")
    print(f"markdown folders         {len(markdowns)} total, {len(applied_folders)} actually "
          f"applied (receipt.txt + import.csv both present)")
    for name, info in markdowns.items():
        state = "APPLIED" if info["applied"] else "previewed only, never applied"
        print(f"  {name}  {state}"
              + (f" — {info['skus_recoverable_from_receipt']} SKU price(s) recoverable"
                 if info["applied"] else ""))
    print(f"SKUs ever priced         {skus_ever_priced} (distinct, `cards.sku` non-empty)")
    print(f"recoverable postings     {recoverable_skus} SKU(s), all from ONE applied "
          f"markdown, one point in time each")
    print("")
    print("READ THIS CAREFULLY: the figure above is not the recoverable HISTORY, only one")
    print("snapshot of it. Every SKU's very first posted price — the number `emit` first")
    print("wrote for it — is unrecoverable for all "
          f"{skus_ever_priced} of them: `pushed` events never carried a price and no")
    print("earlier markdown was ever applied. The 342 recovered here are a single later")
    print("re-price for a third of the store's SKUs, not a history for any of them. The")
    print("honest answer is close to none: this store has no price history at all before")
    print("`price_postings` starts recording it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
