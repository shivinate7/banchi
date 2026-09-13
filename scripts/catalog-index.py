#!/usr/bin/env python3
"""Build the vendored catalog's SQLite index (D15, build-order step 9, piece 2).

Reads `vendor/pokemon-tcg-data/cards/en/*.json` and `sets/en.json` and writes a read-only
index at `vendor/pokemon-tcg-data/catalog.sqlite`. Cards join to sets BY FILENAME —
`cards/en/sv1.json` holds every card of set id `sv1`, and `printedTotal` lives only in the
matching row of `sets/en.json`, which is why D15 calls that join key "half the join key".

A GENERATOR, so it writes and never gates a commit (D18): `make catalog-index` is run on the
owner's word, exactly like `make catalog-refresh`. `pipeline/catalog.py` is the read-only
consumer that opens what this writes; nothing here is imported by it, and nothing this writes
changes what `pipeline/join.py` matches today — see that module's own docstring for why a
vendored catalog and a live TCGplayer join are deliberately two different keys answering two
different questions.

`join_key` on every card row is `pipeline.join.number_index_key(card.number)` composed with
the SAME set's `printedTotal` the way `pipeline/join.py`'s own docstring composes it
(`zfill(3)(number) + "/" + printedTotal`) — precomputed so a lookup is one indexed SELECT
rather than a fold on every read, and computed by IMPORTING that function rather than
reimplementing it, so the two can never drift the way the index and the lookup once did
(see `number_index_key`'s own docstring for that history).

    python3 scripts/catalog-index.py             # build vendor/pokemon-tcg-data/catalog.sqlite
    python3 scripts/catalog-index.py --out PATH   # build somewhere else (tests use this)
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.join import number_index_key  # noqa: E402  (see module docstring)

VENDOR_DIR = ROOT / "vendor" / "pokemon-tcg-data"
DEFAULT_OUT = VENDOR_DIR / "catalog.sqlite"

SCHEMA = """
CREATE TABLE sets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    series TEXT,
    printed_total INTEGER,
    total INTEGER,
    ptcgo_code TEXT,
    release_date TEXT,
    updated_at TEXT
);

CREATE TABLE cards (
    id TEXT PRIMARY KEY,
    set_id TEXT NOT NULL REFERENCES sets(id),
    name TEXT NOT NULL,
    number TEXT NOT NULL,
    rarity TEXT,
    supertype TEXT,
    join_key TEXT NOT NULL,
    image_small TEXT,
    image_large TEXT
);

CREATE INDEX idx_cards_set_id ON cards(set_id);
CREATE INDEX idx_cards_join_key ON cards(join_key);
CREATE INDEX idx_cards_name ON cards(name);
"""


class CatalogBuildError(RuntimeError):
    """The vendored snapshot could not be indexed. Refuses rather than writing a partial file."""


def load_sets(vendor_dir: Path) -> dict:
    sets_path = vendor_dir / "sets" / "en.json"
    if not sets_path.exists():
        raise CatalogBuildError(f"{sets_path} does not exist — run `make catalog-refresh` first")
    rows = json.loads(sets_path.read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in rows}
    if len(by_id) != len(rows):
        raise CatalogBuildError("sets/en.json has two entries with the same id")
    return by_id


def build(vendor_dir: Path, out_path: Path) -> dict:
    sets_by_id = load_sets(vendor_dir)
    cards_dir = vendor_dir / "cards" / "en"
    if not cards_dir.is_dir():
        raise CatalogBuildError(f"{cards_dir} does not exist — run `make catalog-refresh` first")

    card_files = sorted(cards_dir.glob("*.json"))
    if not card_files:
        raise CatalogBuildError(f"no card files under {cards_dir}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()
    conn = sqlite3.connect(str(out_path))
    try:
        conn.executescript(SCHEMA)

        missing_sets = []
        for path in card_files:
            set_id = path.stem  # THE JOIN: the filename IS the set id
            if set_id not in sets_by_id:
                missing_sets.append(set_id)
        if missing_sets:
            raise CatalogBuildError(
                f"{len(missing_sets)} card file(s) name a set with no entry in sets/en.json: "
                f"{', '.join(missing_sets[:5])}"
            )

        set_rows = 0
        for set_id, s in sets_by_id.items():
            conn.execute(
                "INSERT INTO sets (id, name, series, printed_total, total, ptcgo_code, "
                "release_date, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    set_id,
                    s.get("name"),
                    s.get("series"),
                    s.get("printedTotal"),
                    s.get("total"),
                    s.get("ptcgoCode"),
                    s.get("releaseDate"),
                    s.get("updatedAt"),
                ),
            )
            set_rows += 1

        card_rows = 0
        for path in card_files:
            set_id = path.stem
            printed_total = sets_by_id[set_id].get("printedTotal")
            cards = json.loads(path.read_text(encoding="utf-8"))
            for c in cards:
                number = c.get("number", "")
                # Composed exactly as pipeline/join.py's docstring composes the human-read
                # form, then folded through the SAME function the runtime lookup uses —
                # see that module's `number_index_key` for why the fold and not the padding
                # is what both sides must agree on.
                denom = str(printed_total) if printed_total is not None else ""
                composed = f"{str(number).zfill(3)}/{denom}" if denom else str(number)
                join_key = number_index_key(composed)
                images = c.get("images") or {}
                conn.execute(
                    "INSERT INTO cards (id, set_id, name, number, rarity, supertype, "
                    "join_key, image_small, image_large) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        c.get("id"),
                        set_id,
                        c.get("name"),
                        number,
                        c.get("rarity"),
                        c.get("supertype"),
                        join_key,
                        images.get("small"),
                        images.get("large"),
                    ),
                )
                card_rows += 1

        conn.commit()
    finally:
        conn.close()

    return {"sets": set_rows, "cards": card_rows, "out": str(out_path)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vendor-dir", type=Path, default=VENDOR_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    try:
        stats = build(args.vendor_dir, args.out)
    except CatalogBuildError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {stats['out']} — {stats['sets']} sets, {stats['cards']} cards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
