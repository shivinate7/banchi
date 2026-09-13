"""Read-only access to the vendored pokemontcg.io catalog (D15, build-order step 9).

`vendor/pokemon-tcg-data/catalog.sqlite` is built by `scripts/catalog-index.py` from the
vendored snapshot under `vendor/pokemon-tcg-data/` (`make catalog-refresh` fetches the
snapshot, `make catalog-index` builds this file — both write, so neither runs on the commit
path per D18). This module is the READER: it opens what that script wrote and answers
lookups. It builds nothing and calls no network.

THIS SUPPLIES DATA, NOT A NEW MATCHING RULE. `pipeline/join.py`'s TCGplayer join reads a
card's `number` and `printedTotal` from the IDENTIFICATION and matches them against one
export's `Number` column — nothing there calls this module today, and `join.py`'s own
docstring says the vendored catalog's only caller is `harness/eval/fixtures.py`'s ground
truth. That stays true here: nothing in this file changes what a run listing does. What it
adds is a place a FUTURE caller — D46's "a card the pipeline could not place is offered the
catalog, and a human may point at a row" is the standing candidate — can look up a card by
the same `join_key` the runtime join already composes, without either side re-deriving the
fold `pipeline.join.number_index_key` exists to keep from drifting.

Read-only and lazy: `CatalogIndex.open` refuses with a clear sentence when the index has
never been built, rather than building it — a reader that can silently trigger a network
fetch or a multi-second index build on the read path is the shape D18 exists to forbid.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from pipeline.join import number_index_key

ROOT = Path(__file__).resolve().parent.parent
VENDOR_DIR = ROOT / "vendor" / "pokemon-tcg-data"
DEFAULT_INDEX_PATH = VENDOR_DIR / "catalog.sqlite"


class CatalogNotBuilt(RuntimeError):
    """The SQLite index does not exist yet. Never built implicitly — see module docstring."""


@dataclass(frozen=True)
class CatalogSet:
    id: str
    name: str
    series: Optional[str]
    printed_total: Optional[int]
    total: Optional[int]
    ptcgo_code: Optional[str]
    release_date: Optional[str]


@dataclass(frozen=True)
class CatalogCard:
    id: str
    set_id: str
    name: str
    number: str
    rarity: Optional[str]
    supertype: Optional[str]
    join_key: str
    image_small: Optional[str]
    image_large: Optional[str]


class CatalogIndex:
    """A read-only handle on `catalog.sqlite`. Use `CatalogIndex.open(...)`, not the constructor."""

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    @classmethod
    def open(cls, path: Path = DEFAULT_INDEX_PATH) -> "CatalogIndex":
        if not path.exists():
            raise CatalogNotBuilt(
                f"{path} does not exist. Run `make catalog-refresh` then `make catalog-index` "
                f"to build it — this module never builds it implicitly."
            )
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return cls(conn)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "CatalogIndex":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def set_by_id(self, set_id: str) -> Optional[CatalogSet]:
        row = self._conn.execute(
            "SELECT id, name, series, printed_total, total, ptcgo_code, release_date "
            "FROM sets WHERE id = ?",
            (set_id,),
        ).fetchone()
        return _set_from_row(row) if row else None

    def cards_by_join_key(self, join_key: str) -> List[CatalogCard]:
        """Every card whose composed number/printedTotal folds to this key (D15's join).

        `join_key` should already be folded through `pipeline.join.number_index_key` — pass
        the same value the TCGplayer join would look up, not a raw `Number` cell.
        """
        rows = self._conn.execute(
            "SELECT id, set_id, name, number, rarity, supertype, join_key, image_small, "
            "image_large FROM cards WHERE join_key = ?",
            (number_index_key(join_key),),
        ).fetchall()
        return [_card_from_row(row) for row in rows]

    def cards_by_name(self, name: str) -> List[CatalogCard]:
        """Case-sensitive exact match on the catalog's own `name` field — a narrow lookup
        for a human choosing among candidates, never a join key (see pipeline/join.py's
        own rule against Product Name as a key)."""
        rows = self._conn.execute(
            "SELECT id, set_id, name, number, rarity, supertype, join_key, image_small, "
            "image_large FROM cards WHERE name = ?",
            (name,),
        ).fetchall()
        return [_card_from_row(row) for row in rows]

    def card_by_id(self, card_id: str) -> Optional[CatalogCard]:
        row = self._conn.execute(
            "SELECT id, set_id, name, number, rarity, supertype, join_key, image_small, "
            "image_large FROM cards WHERE id = ?",
            (card_id,),
        ).fetchone()
        return _card_from_row(row) if row else None

    def counts(self) -> dict:
        sets_n = self._conn.execute("SELECT COUNT(*) FROM sets").fetchone()[0]
        cards_n = self._conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
        return {"sets": sets_n, "cards": cards_n}


def _set_from_row(row: sqlite3.Row) -> CatalogSet:
    return CatalogSet(
        id=row["id"],
        name=row["name"],
        series=row["series"],
        printed_total=row["printed_total"],
        total=row["total"],
        ptcgo_code=row["ptcgo_code"],
        release_date=row["release_date"],
    )


def _card_from_row(row: sqlite3.Row) -> CatalogCard:
    return CatalogCard(
        id=row["id"],
        set_id=row["set_id"],
        name=row["name"],
        number=row["number"],
        rarity=row["rarity"],
        supertype=row["supertype"],
        join_key=row["join_key"],
        image_small=row["image_small"],
        image_large=row["image_large"],
    )
