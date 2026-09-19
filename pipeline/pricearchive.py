"""The sweep `pkmnscan archive sweep` runs: read `pipeline/pricehistory.py`'s live endpoint
for every name the owner has sold or holds, and hand what came back to `store/pricearchive.py`
(D-a-price-history-archive).

TWO STEPS, KEPT APART SO THE FIRST NEEDS NO NETWORK. `rows_from_store` reads the store alone
and answers "which SKUs is this pass over, and what does the export-shaped row for each one
look like" — pure, and the whole thing a test can exercise with a throwaway store and no
`Market`. `sweep` takes those rows and a `Market` (or anything shaped like one — see below)
and does the one thing this module exists to do: ask the live endpoint for every range, and
turn what it hands back into `store/pricearchive.py:Bucket` rows keyed the way that module
argues they must be.

THE SUBJECT IS EVERY DISTINCT SKU THE `cards` TABLE NAMES. A card keeps its `sku` for as
long as it exists in the store, sold or not — D26/D134 retire a box and reclaim a sold card's
photograph, but the record and its SKU stay (`store/master.py:STATES` includes `sold` as a
state a card carries, never a deletion) — so "every name the owner has sold or holds" is
exactly "every distinct, non-empty `sku` this table has ever recorded a card against." A
card's own most recent row supplies the `Product Name`, `Number`, `Set Name`, `Condition` and
`game` an export-shaped row needs to be resolved against the catalog the same way
`pipeline/pricehistory.py:Market.product_id_for_row` already resolves a real export row —
this module invents no second resolution path.

`Market.readings_for_rows` TAKES `pipeline/tcgcsv.Row`-SHAPED DICTS, WHICH IS WHAT
`_export_row` BUILDS. A `tcgcsv.Row` is a plain dict keyed by the export's own column names
(`pipeline/tcgcsv.py:SKU_COLUMN` etc.), and every one of those columns is a fact the `cards`
table already carries per card — `Product Line` alone has no column of its own and is derived
from `pipeline/games.py:get(card.game)["product_line"]`, the same table `join.py` already
reads for every other purpose.

NEITHER FUNCTION IMPORTS `pipeline/pricehistory.py:Market` BY NAME IN ITS SIGNATURE. `sweep`
duck-types on `.readings_for_rows(rows, ranges=...)`, which is exactly `Market`'s own method
— this is so a test can hand it a stand-in with no network underneath, per `CLAUDE.md`'s "no
network call in a test" rule, without this module importing anything from `unittest.mock`.
"""

from __future__ import annotations

import time
from typing import Dict, Iterable, List, Optional, Protocol, Tuple

from pipeline import games, tcgcsv
from store.pricearchive import RANGE_WIDTH_DAYS, Bucket, Source, _key
from store.session import Store


class _MarketLike(Protocol):
    def readings_for_rows(
        self, rows: Iterable[dict], ranges: Tuple[str, ...] = ()
    ) -> Tuple[Dict[str, object], Dict[str, str]]:
        ...


def _export_row(sku: str, name: str, number: str, set_name: str, condition: str, game: str) -> dict:
    """One card's own last-known facts, shaped exactly like a real export row.

    `game` IS RESOLVED THROUGH `pipeline/games.py`, NEVER STORED AS `Product Line` DIRECTLY —
    `cards.game` is the operator's claim (`pokemon`, `misc`, ...), and the catalogue walk
    wants the human-facing product line string that claim maps to. A card whose claim is
    empty falls back through `games.DEFAULT_GAME` the same way every other reader in this
    repo backfills an unset `game` (`store/master.py:Card.game`'s own docstring).
    """
    registry = games.get(game or games.DEFAULT_GAME)
    line = registry.get("product_line")
    return {
        tcgcsv.PRODUCT_LINE_COLUMN: line if line is not None else "",
        tcgcsv.SET_COLUMN: set_name or "",
        tcgcsv.NUMBER_COLUMN: number or "",
        tcgcsv.NAME_COLUMN: name or "",
        tcgcsv.SKU_COLUMN: sku,
        tcgcsv.CONDITION_COLUMN: condition or "",
    }


def rows_from_store(snapshot=None) -> Dict[str, dict]:
    """`sku -> export-shaped row`, one per distinct SKU the `cards` table has ever named.

    A FULL-TABLE `select`, NOT `.values()` — `select` hands back only the six columns this
    needs as plain tuples, never a `Card` object per row (`store-scaling` item 2's own
    complaint about a table-wide walk, avoided the same way `cli/cmd_reprice.py` and
    `cli/resolve.py` already avoid it elsewhere in this package). The LAST row this loop
    sees for a SKU wins — `cards.select` has no declared order, so a SKU captured under two
    slightly different set-hint spellings over its lifetime resolves to whichever row this
    process happened to read last; that is a pre-existing ambiguity in what "the" name for a
    SKU is, not one this module introduces, and it costs nothing worse than a possibly-stale
    `Number`/`Set Name` pair that `Market.product_id_for_row` will refuse on its own if the
    two together no longer resolve.
    """
    snapshot = snapshot if snapshot is not None else Store().read()
    rows: Dict[str, dict] = {}
    columns = ("sku", "name", "number", "set_name", "condition", "game")
    for _, values in snapshot.inventory.cards.select(columns):
        sku, name, number, set_name, condition, game = values
        sku = str(sku or "").strip()
        if not sku:
            continue
        rows[sku] = _export_row(sku, name, number, set_name, condition, game)
    return rows


def sweep(
    rows: Dict[str, dict],
    market: _MarketLike,
    ranges: Tuple[str, ...] = (),
    *,
    now: Optional[int] = None,
) -> Tuple[Dict[str, Bucket], List[Source], Dict[str, str]]:
    """Ask `market` for every SKU in `rows`, over every range in `ranges`, and answer
    `(buckets_by_key, sources_by_range, refusals_by_sku)`.

    `ranges` DEFAULTS TO EVERY RANGE `pipeline/pricehistory.py:RANGES` NAMES, not
    `DEFAULT_RANGES` — the screen panel `PriceHistory.tsx` draws only `month` and `annual`
    because two views is what a person can read at once, but an archive whose entire reason
    to exist is "capture it before it ages out" has no such excuse to skip `quarter` and
    `semiannual`. A caller that wants a narrower pass (an operator re-running just the
    monthly figures) still passes its own tuple; nothing here hardcodes the full set as a
    constant a caller cannot override.

    BOTH DIRECTIONS ARE REPORTED, PER `CLAUDE.md`'S HARD RULE. `refusals_by_sku` is every SKU
    `rows` named that this pass could not read anything for — not catalogued, not resolvable,
    the endpoint unreachable or blocked — carrying `Market`'s own message, never dropped.
    """
    now = int(now if now is not None else time.time())
    ranges = tuple(ranges) if ranges else tuple(RANGE_WIDTH_DAYS)

    readings, refusals = market.readings_for_rows(rows.values(), ranges=ranges)

    buckets: Dict[str, Bucket] = {}
    answered_by_range: Dict[str, int] = {r: 0 for r in ranges}
    for sku, reading in readings.items():
        product_id = getattr(reading, "product_id", 0)
        series_by_range = getattr(reading, "series", {}) or {}
        for range_, series in series_by_range.items():
            if range_ not in RANGE_WIDTH_DAYS:
                continue
            width = RANGE_WIDTH_DAYS[range_]
            saw_bucket = False
            for candidate in getattr(series, "buckets", ()):
                if candidate.start is None:
                    continue
                saw_bucket = True
                start = candidate.start.isoformat()
                buckets[_key(sku, range_, start)] = Bucket(
                    sku=sku,
                    product_id=int(product_id),
                    range=range_,
                    width_days=width,
                    start=start,
                    market=str(candidate.market) if candidate.market is not None else None,
                    quantity=int(candidate.quantity),
                    transactions=int(candidate.transactions),
                    low=str(candidate.low) if candidate.low is not None else None,
                    high=str(candidate.high) if candidate.high is not None else None,
                    at=now,
                )
            if saw_bucket:
                answered_by_range[range_] = answered_by_range.get(range_, 0) + 1

    requested = len(rows)
    sources = [
        Source(
            range=range_,
            at=now,
            requested=requested,
            answered=answered_by_range.get(range_, 0),
            refused=len(refusals),
        )
        for range_ in ranges
    ]
    return buckets, sources, refusals
