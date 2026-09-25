"""`price_postings` — every `TCG Marketplace Price` this store has ever written into a file
bound for the marketplace, kept forever (D243).

WHY THIS TABLE EXISTS AT ALL. Measured on the owner's real store, 2026-09-20: the `events`
ledger carries 143 `pushed` lines and none of them names a price — the payload is `at`,
`event`, `position`, `run` and `sku`. `inventory/prices.json` (D86) is newest-wins by
design: every repricing overwrites the one before it, so it can only ever answer "what is
the price now," never "what did I ask before." The seven `inventory/markdowns/` folders
record what a reprice worklist PROPOSED, and only for the runs that went through that path,
and only until an operator cleans the folder up. So the answer to "what have I asked for
this card over time" is unrecoverable for nearly every SKU in the store today, and it is
lost a little further every time a price is posted. This table is the fix: append a row at
the moment a price is decided, on every path that decides one.

THE SHAPE IS `store/pricearchive.py`'s AND `store/readings.py`'s, ONE REGISTER OVER — an
append-only table keyed by subject and time, filled by a press, with an accounting of what
that press wrote. It differs from both in the one respect that matters: neither of THOSE
tables can ever be a true log, because both are a CACHE of a number a live source can be
asked for again (a history bucket inside its 357-day window, a market reading refreshed by
`readings adopt`), so both are correctly `upsert`s that fold a fresher reading of the SAME
key over an older one. A posted price has no such second copy. The number this table
records is not observed from anywhere else — it is composed once, here, at the instant a
caller decides to write it into a CSV cell, and once that byte has left for TCGplayer there
is no live endpoint left to ask what it used to be. So `record()` below is never an upsert:
it is one `INSERT`, every time, and the table has no update statement and no delete
statement anywhere in this module. Losing that property loses the whole feature — a second
posting of a SKU that overwrote the first would answer "what is the price now," which
`inventory/prices.json` already answers, and nothing would be gained.

THE GRAIN IS THE SKU, NOT A CARD OR A COPY (D212). Every copy of a SKU is fungible and one
press writes one cell for the whole SKU, so a posting is one row per SKU per press — never
per physical card, and never per unit of quantity that press happened to add.

WHAT IS RECORDED, AND WHAT IS NOT. A row is created only for a price that actually reached a
file the press went on to write to disk — `emit`'s `pushed` gate and `reprice apply`'s
`--write` gate are also this module's gate, because a proposal an operator edited and
discarded, or a run that refused before a single byte was written, was never posted and is
not this table's business to remember. `source` names which press wrote the row (`emit`,
`emit-merged`, `reprice`, and `emit-price` for a send's price-only row on a live card, which
carries the live price it replaced), `run` names which run or worklist decided it, and `replaced`
carries the price this posting is known to have superseded when the caller already has that
value in hand — `reprice apply` always does (the worklist's own `was` column); `emit` does
not track a prior asking price at all, so its rows carry `replaced=None` rather than a
guess.

BOUND LIKE `archive` AND `readings` (D88): flushed inside the same `Store.write()`
transaction as every other table a press touches, so a posting can never land without the
inventory and listing writes that went with it, or vice versa.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Postings:
    """The postings one `Store.write()` session has decided to record, held in memory until
    `Store.write()`'s own commit flushes them with `store.db.append_postings` — the same
    accumulate-then-flush shape `Inventory.events` uses for the `events` ledger, chosen for
    the identical reason: this is a pure log, so there is no dict-keyed row to look up,
    mutate, or diff, only a list of facts to append.
    """

    entries: List[dict] = field(default_factory=list)

    def record(
        self,
        *,
        sku: str,
        price: str,
        source: str,
        run: Optional[str] = None,
        replaced: Optional[str] = None,
        at: Optional[int] = None,
    ) -> None:
        """Append one posted price. Never call this for a price that was only proposed.

        `price` and `replaced` are already-formatted strings ("9.99"), never a `Decimal` —
        this module is store-layer and does not import `pipeline.tcgcsv`'s money formatting,
        so the caller (which already has `tcgcsv.format_price`) does that once, before the
        value reaches here, rather than this module reimplementing rounding it would then
        have to keep in step with the CSV writer's own.
        """
        self.entries.append(
            {
                "at": int(at) if at is not None else int(time.time()),
                "sku": str(sku),
                "price": str(price),
                "source": str(source),
                "run": str(run) if run is not None else None,
                "replaced": str(replaced) if replaced is not None else None,
            }
        )
