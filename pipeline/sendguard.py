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
copies OUT of a file; it never puts one in. The price-only rows at the foot (`price_changes`)
put no copy in either: each carries Add to Quantity 0.

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


REQUIRED_COLUMNS = (tcgcsv.SKU_COLUMN, tcgcsv.LIVE_QUANTITY_COLUMN)


def live_by_sku(
    rows: Iterable[Mapping[str, str]], header: Optional[Sequence[str]] = None
) -> Dict[str, int]:
    """SKU -> the copies TCGplayer holds live, off a live export's `Total Quantity`.

    A CELL THAT IS NOT A WHOLE NUMBER IS A REFUSAL, NOT A ZERO. A zero here opens room, and
    room is the one thing this guard may never invent. `ValueError` reaches the caller, which
    refuses the send by name.

    A MISSING COLUMN IS THE SAME REFUSAL, AND IT WAS A SILENT ZERO UNTIL THE 2026-09-24 REVIEW.
    `row.get(...) or ""` read an export with no `Total Quantity` column as every SKU at zero —
    the guard's room wide open — and one with no `TCGplayer Id` as nothing live at all. So the
    header is checked when the caller has it, and every row is checked either way: a row
    without the key is a file that is not a live export.
    """
    if header is not None:
        absent = [column for column in REQUIRED_COLUMNS if column not in header]
        if absent:
            raise ValueError(f"the live export has no {', '.join(absent)} column")
    live: Dict[str, int] = {}
    for row in rows:
        absent = [column for column in REQUIRED_COLUMNS if column not in row]
        if absent:
            raise ValueError(f"a live export row has no {', '.join(absent)} column")
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


# ------------------------------------------------------------------- the price-only rows


@dataclass(frozen=True)
class PriceChange:
    """One card already live at TCGplayer whose typed price this send changes, adding no copy.

    THE OWNER'S RULING, 2026-09-24 ("Allow mixed", `D-one-press-sends-and-makes-live`): one
    press lists new copies AND reprices live ones. A price change is a row with Add to
    Quantity 0, so it moves no copy, claims no copy, and a second upload of it changes nothing
    (D100's own reason for its zero rule). `was` is TCGplayer's live price at the read, or
    None where the export carried none.
    """

    sku: str
    name: str
    price: str
    was: Optional[str]

    def as_dict(self) -> dict:
        return {"sku": self.sku, "name": self.name, "price": self.price, "was": self.was}


def live_prices(rows: Iterable[Mapping[str, str]]) -> Dict[str, Optional[str]]:
    """SKU -> TCGplayer's live marketplace price, two decimals, or None where the cell is blank.

    A CELL THAT IS NOT MONEY IS A REFUSAL (`ValueError`), NEVER A BLANK. A blank reads as "no
    price live", and this module would then propose a price change over it.
    """
    out: Dict[str, Optional[str]] = {}
    for row in rows:
        sku = str(row.get(tcgcsv.SKU_COLUMN) or "").strip()
        if not sku:
            continue
        text = str(row.get(tcgcsv.PRICE_COLUMN) or "").strip()
        try:
            value = tcgcsv.parse_price(text)
        except ArithmeticError:
            raise ValueError(f"the live export prices {sku} at {text!r}, which is not money") from None
        out[sku] = None if value is None else tcgcsv.format_price(value)
    return out


def price_changes(
    candidates: Mapping[str, tuple],
    typed: Iterable[str],
    live: Mapping[str, int],
    prices: Mapping[str, Optional[str]],
) -> List[PriceChange]:
    """The price-only rows one send carries. `candidates` is SKU -> (name, the plan's price) for
    every SKU the send prices and adds NO copy of.

    THE SMALLEST HONEST READING OF "A PRICE THE OWNER CHANGED ON A LIVE CARD". Three tests,
    and a row needs all three:

      - TYPED. The owner's own price for the card (`overrides` or `no_market_data`). A price
        the standing rule gives is never sent to a live listing: the rule speaks about most
        live listings on a store, and one press would move them all.
      - LIVE. TCGplayer holds at least one copy in the fresh export. A card with nothing live
        has no price there to change.
      - DIFFERENT. The typed price is not what TCGplayer already shows, to the cent. A row
        that changes nothing is not written.
    """
    wanted = {str(sku) for sku in typed}
    out: List[PriceChange] = []
    for sku, (name, price) in candidates.items():
        if sku not in wanted or int(live.get(sku, 0)) <= 0:
            continue
        now = tcgcsv.format_price(price)
        was = prices.get(sku)
        if was == now:
            continue
        out.append(PriceChange(sku=sku, name=str(name or ""), price=now, was=was))
    return out


def price_report(changes: Sequence[PriceChange]) -> dict:
    """The JSON object `cli/cmd_emit.py` prints for the price-only rows it wrote."""
    return {"send_prices": {"rows": [change.as_dict() for change in changes]}}
