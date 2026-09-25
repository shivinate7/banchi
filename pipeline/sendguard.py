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
from decimal import Decimal
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
    Quantity 0, so it moves no copy, claims its card at 0 copies (round 6, S3), and a second upload of it changes nothing
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


#: Why a price the screen named is LEFT OUT of the file, and the press still goes.
LEFT_ALREADY = "already"        # TCGplayer already shows this price
LEFT_NOT_LIVE = "not_live"      # TCGplayer holds no copy now, so there is no price to change
LEFT_ADDS_COPIES = "adds_copies"  # this press adds a copy, and that row carries the price
#: Why a price the screen named REFUSES the whole press.
REFUSED_LIVE_MOVED = "live_moved"      # TCGplayer's price is not the one the screen showed
REFUSED_NOT_SAVED = "not_saved"        # the saved price is not the one the button named
REFUSED_BELOW_FLOOR = "below_floor"    # under the store's floor, the mark-down door's rule
REFUSED_NOT_IN_SEND = "not_in_send"    # the button named a card this press does not price
REFUSED_MOVE_UNNAMED = "move_unnamed"  # a listing row would move live copies the button did not name


@dataclass(frozen=True)
class PriceNote:
    """One price the screen named that did not become a row, and why (a `LEFT_*` or `REFUSED_*`)."""

    sku: str
    name: str
    why: str
    price: Optional[str] = None
    live: Optional[str] = None
    shown: Optional[str] = None
    copies: int = 0

    def as_dict(self) -> dict:
        return {
            "sku": self.sku, "name": self.name, "why": self.why,
            "price": self.price, "live": self.live, "shown": self.shown, "copies": self.copies,
        }


def price_changes(
    named: Mapping[str, tuple],
    candidates: Mapping[str, tuple],
    live: Mapping[str, int],
    prices: Mapping[str, Optional[str]],
    floor,
    adding: Iterable[str] = (),
) -> tuple:
    """The price-only rows one send carries: `(changes, left, refused)`.

    THE ORCHESTRATOR'S RULING ON THE OWNER'S WORDS (round 6): ONLY A PRICE THE SCREEN NAMED
    RIDES. `named` is SKU -> (the price the button counted, the live price the screen showed)
    — the SKUs the owner typed a price for on the worklist this visit. A corpus answer the
    owner did not type there (a Live tab preset, `reprice apply --write`) is not in `named`,
    so it never becomes a row. `candidates` is SKU -> (name, the plan's price) for every SKU
    this press prices and adds NO copy of.

    Per named SKU:

      - this press adds a copy of it (`adding`): LEFT (`adds_copies`). Its listing row
        already carries the price;
      - this press does not price it at all: REFUSED (`not_in_send`);
      - the saved price is not the button's: REFUSED (`not_saved`);
      - under the store's floor (`policy.threshold`): REFUSED (`below_floor`), the mark-down
        door's own `BELOW_FLOOR` rule;
      - TCGplayer holds no copy now: LEFT (`not_live`);
      - TCGplayer already shows that price: LEFT (`already`);
      - TCGplayer's price is not the one the screen showed: REFUSED (`live_moved`). A price
        the button did not name is never sent;
      - otherwise, a row.

    A REFUSAL STOPS THE WHOLE PRESS, by name, before a file exists. A LEFT row is named and
    the press goes on.
    """
    changes: List[PriceChange] = []
    left: List[PriceNote] = []
    refused: List[PriceNote] = []
    adding = {str(sku) for sku in adding}
    for sku in sorted(named):
        typed, shown = named[sku]
        typed = tcgcsv.format_price(typed)
        shown = None if shown in (None, "") else tcgcsv.format_price(shown)
        if sku in adding:
            left.append(PriceNote(sku, "", LEFT_ADDS_COPIES, price=typed))
            continue
        if sku not in candidates:
            refused.append(PriceNote(sku, "", REFUSED_NOT_IN_SEND, price=typed))
            continue
        name, plan = candidates[sku]
        plan = tcgcsv.format_price(plan)
        now = prices.get(sku)
        note = dict(sku=sku, name=str(name or ""), price=plan, live=now, shown=shown)
        if plan != typed:
            refused.append(PriceNote(why=REFUSED_NOT_SAVED, **dict(note, price=typed)))
        elif Decimal(plan) < Decimal(str(floor)):
            refused.append(PriceNote(why=REFUSED_BELOW_FLOOR, **note))
        elif int(live.get(sku, 0)) <= 0:
            left.append(PriceNote(why=LEFT_NOT_LIVE, **note))
        elif now == plan:
            left.append(PriceNote(why=LEFT_ALREADY, **note))
        elif now != shown:
            refused.append(PriceNote(why=REFUSED_LIVE_MOVED, **note))
        else:
            changes.append(PriceChange(sku=sku, name=str(name or ""), price=plan, was=now))
    return changes, left, refused


@dataclass(frozen=True)
class LiveMove:
    """Live copies of a card that a LISTING row moves to its price (the owner's ruling,
    2026-09-24, round 7): a new copy of a card already live carries Banchi's stored price, and
    TCGplayer lists every copy of one SKU at one price, so the live copies move with it."""

    sku: str
    name: str
    copies: int
    price: str
    was: Optional[str]

    def as_dict(self) -> dict:
        return {"sku": self.sku, "name": self.name, "copies": self.copies, "price": self.price, "was": self.was}


def live_moves(
    going: Mapping[str, tuple],
    named: Mapping[str, str],
    live: Mapping[str, int],
    prices: Mapping[str, Optional[str]],
) -> tuple:
    """`(moves, refused)`: the live copies this press's LISTING rows move, and any the button did
    not name.

    `going` is SKU -> (name, the row's price) for every row that adds a copy. A row moves live
    copies when TCGplayer holds some and shows another price. The button names each move it
    drew with its price (`named`, SKU -> price), off the same newest live export the worklist
    carries. A move the button did not name, or named at another price, REFUSES the press with
    the live figure as data, so the screen can say "TCGplayer shows $X now" and send again.
    """
    moves: List[LiveMove] = []
    refused: List[PriceNote] = []
    for sku in sorted(going):
        name, price = going[sku]
        price = tcgcsv.format_price(price)
        held = int(live.get(sku, 0))
        now = prices.get(sku)
        # A LIVE ROW WITH NO PRICE SHOWS NONE TO MOVE FROM, and TCGplayer lists no copy without
        # one, so it is not named. Only a price TCGplayer shows can be said to move.
        if held <= 0 or now is None or now == price:
            continue
        told = named.get(sku)
        if told is None or tcgcsv.format_price(told) != price:
            refused.append(
                PriceNote(sku, str(name or ""), REFUSED_MOVE_UNNAMED, price=price, live=now,
                          shown=None if told is None else tcgcsv.format_price(told), copies=held)
            )
            continue
        moves.append(LiveMove(sku=sku, name=str(name or ""), copies=held, price=price, was=now))
    return moves, refused


def price_report(changes: Sequence[PriceChange], left=(), refused=(), moves=()) -> dict:
    """The JSON object `cli/cmd_emit.py` prints for the price-only rows, the ones it did not
    write, and the live copies its listing rows move. `server/send_routes.py` reads it."""
    return {
        "send_prices": {
            "rows": [change.as_dict() for change in changes],
            "left": [note.as_dict() for note in left],
            "refused": [note.as_dict() for note in refused],
            "moves": [move.as_dict() for move in moves],
        }
    }
