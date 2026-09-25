"""`pkmnscan cards contradictions` — RETIRED into `pkmnscan cards identity`
(`docs/specs/identity-follows-sku.md` §5.5, lane 2).

D242's own test compared two CARDS' stored numbers for one SKU. After lane 2's `bind_sku`
becomes the one writer of a card's identity (`store/master.py`, lane 1), every card bound to
one SKU carries that SKU's OWN number by construction — "After the change both read zero
forever. A guard that cannot see its subject proves nothing" (§5.5). The merged report reads
the SKU table directly instead: `pipeline/identity_binding.py`'s name half and number half,
run by `./pkmnscan cards identity`.

`run` below is now a one-line pointer, on the owner's own ruling ("Merge them", §12 ruling
6). `_read_only` and `_by_sku` stay — `_by_sku`'s own shape (`NumberRecord` per card) is
what proved D242's grouping in the first place, kept in case a later session wants the raw
grouping again; `cli/cmd_sku_name_contradictions.py` retired its own use of `_read_only` the
same way this file retired `run`, so neither reads the other's helpers any more.
`_market_cache_dir` and `_product_line_for_game`, which existed only to drive `--resolve`'s
network path, are deleted rather than kept as dead code — `pipeline/
sku_number_contradictions.py`'s own resolver (`find_disagreements`, `resolve`) is still
proved directly by `scripts/sku-number-contradictions-selftest.py` against fixtures, even
though nothing on the ordinary command path calls it any more (§9: "Given up... `cards
contradictions`... The one writer, the one table and the one report subsume each, and none
is lost" — the MODULE is not lost, only this command's own use of it).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List

from pipeline.sku_number_contradictions import NumberRecord
from store import db


def _read_only(directory: Path) -> sqlite3.Connection:
    """Same door `cli/cmd_cards.py:_read_only` uses — `mode=ro&immutable=1`, never
    `db.connect`, so a preview cannot perform a schema migration.
    """
    target = db.path(directory)
    if not target.is_file():
        raise FileNotFoundError(f"no store at {target}")
    return sqlite3.connect(f"file:{target}?mode=ro&immutable=1", uri=True)


def _by_sku(conn: sqlite3.Connection) -> Dict[str, List[NumberRecord]]:
    out: Dict[str, List[NumberRecord]] = {}
    for key, sku, name, number, set_name, game in conn.execute(
        "SELECT key, sku, name, number, set_name, game FROM cards "
        "WHERE sku IS NOT NULL AND sku != ''"
    ):
        out.setdefault(str(sku), []).append(
            NumberRecord(key=str(key), number=number, name=name, set_name=set_name, game=game)
        )
    return out


def run(args, say) -> int:
    """RETIRED (§5.5, ruling 6: "Merge them"). `./pkmnscan cards identity` carries this
    check's replacement — the number half of its name/number contradiction report, read off
    the SKU table rather than off two cards' stored numbers. Exits 0: an operator who typed
    the old command is told where to go, not refused."""
    say("`cards contradictions` is retired — run `./pkmnscan cards identity` instead. "
        "docs/specs/identity-follows-sku.md §5.5: the same question, answered off the SKU "
        "table, merged with `cards sku-names` into one report.")
    return 0
