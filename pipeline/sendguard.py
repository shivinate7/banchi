"""The double-send guard: a send never leaves TCGplayer holding more copies than the shelf.

THE OWNER'S RULING, 2026-09-23 (`D-one-press-sends-and-makes-live`), in their words: "maybe
before submitting prices there's a mandatory reconciliation that auto runs seeing my sales and
live inventory". So every send first reads a FRESH live export, and this module is the
arithmetic it is read for:

    after the send, live at TCGplayer + Add to Quantity  <=  copies on hand

per SKU. A row that would break it is TRIMMED to the room that is left, and the trim is named.
A send whose every row trims to nothing is refused by the caller.

WHY A SECOND RULE WHEN `cli/resolve.py:_copies_out` ALREADY COUNTS WHAT IS OUT. That figure is
built from the store's own bookkeeping — `pushed`, `staged`, a dated `live` — and the doubling
D100 §2 measured (nine SKUs at `2 x pushed - sold`) happened on exactly the path that
bookkeeping cannot see: a file uploaded by hand, twice. This rule reads NOTHING the store
wrote about listings. It reads the export (what TCGplayer holds) and the shelf (what is
physically here), so a wrong `pushed` or a stale `live` cannot open it. It only ever takes
copies OUT of a file; it never puts one in.

"ON HAND" IS THE UNION OF TWO SETS OF POSITIONS, AND BOTH HALVES ARE NEEDED. The store's cards
that already carry the SKU (every copy an earlier send wrote), and the positions this send's
own join matched to it (copies a first send has not stamped yet). Either half alone
under-counts: the store alone trims a new box's first copy of a card already live, and the
join alone forgets the copies in boxes this send does not cover. A card that has left — sold,
retired, moved — is not on hand, whichever half named it.

PURE. No file is read and nothing is written here. `cli/cmd_emit.py` supplies the export rows,
the store's cards and the matches, and prints what this returns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from pipeline import tcgcsv
from store import master


@dataclass(frozen=True)
class Trim:
    """One SKU the guard held back, and every figure the sentence about it needs."""

    sku: str
    name: str
    live: int
    on_hand: int
    would: int
    goes: int

    def as_dict(self) -> dict:
        return {
            "sku": self.sku,
            "name": self.name,
            "live": self.live,
            "on_hand": self.on_hand,
            "would": self.would,
            "goes": self.goes,
        }


def live_by_sku(rows: Iterable[Mapping[str, str]]) -> Dict[str, int]:
    """SKU -> the copies TCGplayer holds live, off a live export's `Total Quantity`.

    A CELL THAT IS NOT A WHOLE NUMBER IS A REFUSAL, NOT A ZERO. A zero here opens room, and
    room is the one thing this guard may never invent. `ValueError` reaches the caller, which
    refuses the send by name.
    """
    live: Dict[str, int] = {}
    for row in rows:
        sku = str(row.get(tcgcsv.SKU_COLUMN) or "").strip()
        if not sku:
            continue
        held = tcgcsv.parse_quantity(str(row.get(tcgcsv.LIVE_QUANTITY_COLUMN) or ""))
        # TWO ROWS FOR ONE SKU ARE ADDED, never the larger kept: an export row is one
        # listing, and two listings of one SKU are two sets of copies a buyer can buy.
        live[sku] = live.get(sku, 0) + max(0, held)
    return live


def on_hand(
    carrying: Iterable["master.Card"],
    cards: Mapping[str, "master.Card"],
    matched: Sequence[str] = (),
) -> int:
    """How many copies of one SKU are physically here: the store's unsold cards carrying it,
    union the positions this send matched to it, less every copy that has left.

    `carrying` is `Inventory.copies_on_hand(sku)`, the indexed read, so this never walks the
    whole store. `matched` is position keys (`store/master.py:position_key`), looked up one by
    one in `cards`. A matched key whose card the store says has LEFT is not counted, and a
    matched key the store has never seen is counted, because the join saw a photograph of it
    and the join is what is being sent.
    """
    keys = {
        master.position_key(card.box, card.index)
        for card in carrying
        if getattr(card, "state", None) not in master.TERMINAL_STATES
    }
    for key in matched:
        card = cards.get(key)
        if card is not None and getattr(card, "state", None) in master.TERMINAL_STATES:
            continue
        keys.add(key)
    return len(keys)


def room(live: int, held: int) -> int:
    """The copies a send may still add: what is on hand, less what TCGplayer already holds."""
    return max(0, int(held) - max(0, int(live)))


def trims(
    live: Mapping[str, int],
    would: Mapping[str, int],
    rooms: Mapping[str, int],
    held: Mapping[str, int],
    names: Optional[Mapping[str, str]] = None,
) -> List[Trim]:
    """Every SKU where the guard's room is less than what the send would otherwise have added.

    `would` is the figure BEFORE the guard (the send's own room, bounded by any quantity the
    operator typed). A SKU the send adds nothing to is never a trim, whatever TCGplayer holds.
    """
    names = names or {}
    out: List[Trim] = []
    for sku in sorted(would):
        before = max(0, int(would[sku]))
        if before == 0:
            continue
        allowed = rooms.get(sku)
        if allowed is None or allowed >= before:
            continue
        out.append(
            Trim(
                sku=sku,
                name=str(names.get(sku) or ""),
                live=int(live.get(sku, 0)),
                on_hand=int(held.get(sku, 0)),
                would=before,
                goes=max(0, int(allowed)),
            )
        )
    return out


def report(export: str, checked: int, trimmed: Sequence[Trim]) -> dict:
    """The one JSON object `cli/cmd_emit.py` prints and `server/send_routes.py` reads."""
    return {
        "send_guard": {
            "export": export,
            "checked": int(checked),
            "trimmed": [trim.as_dict() for trim in trimmed],
            "trimmed_copies": sum(trim.would - trim.goes for trim in trimmed),
        }
    }
