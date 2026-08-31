"""The code ledger: every extracted code, keyed by the code itself.

THE KEY IS THE CODE, AND THAT IS A CHANGE FROM C8's FIRST BUILD. That build upserted by
`(box, index)` — the POSITION — which was the right key for the job it was written for:
C8's dispute lookup wants "show me the photograph this code came from", and the position is
what names the photograph. It is the wrong key for everything else the track needs, and the
reason is D24: **the physical card is destroyed once the code is extracted.** A position
whose card no longer exists is a filing reference, not an identity. The code outlives it.

WHAT THE POSITION KEY COULD NOT DO, AND THIS ONE DOES:

  DEDUPE. C3 says the code string is the natural primary key "giving free dedupe and
  structural protection against double-selling". Under a position key the same code
  scanned at two positions is two ledger lines, both sellable, and the second sale is the
  unrecoverable one the fork's hard rules are written against. Under this key it is one
  line with `duplicate_positions` naming both photographs.

  RESERVATION. "Atomic dequeue is required. A code is marked reserved the instant it is
  assigned to an order ID. Never reissue." A reservation has to be held against the thing
  being sold, and the thing being sold is the code.

THE POSITION IS NOT LOST — it is an attribute (`box`, `index`, `photo`), and C8's dispute
lookup still works exactly as specified, because the code is what the operator types and the
photo path is on the line the code returns. What changed is which field is unique.

A LEDGER OF UNREDEEMED CODES IS A FILE OF BEARER INSTRUMENTS. C8's own sentence, and it
decides the storage: this file lives under `inventory/` beside the master store, which
`.gitignore` covers whole, and it never reaches a commit. The runtime writing codes into a
gitignored file is the sanctioned path; `scripts/guard-opsec.sh` and the pre-commit hook
exist to stop an agent pasting one into a tracked file. Those two facts are not in tension
and it is worth saying so once: the guards protect the REPOSITORY, not the store.

STATES, AND WHY THEY ARE NOT THE CARD'S STATES. `store/master.py` already has a card state
machine (`captured`, `identified`, `sold`, `retired`) and it describes a piece of cardboard.
These describe a code, and a code's life does not end when its cardboard is destroyed — that
is the whole of D24. A card can be `retired` (destroyed, per D24's disposal) while its code
is still `held` and perfectly saleable, and conflating the two would make disposal look like
losing the asset.

    held        extracted and on hand. Sellable.
    reserved    assigned to an order and NOT sellable. The atomic step C3 demands.
    delivered   sent to the buyer it was reserved for. Terminal.
    dead        known bad — already redeemed, refused by the buyer, or a duplicate that
                lost the tie-break. Terminal, and kept rather than deleted: a code that
                turned out dead is exactly what a dispute is about later.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from store import files as store_files

HELD = "held"
RESERVED = "reserved"
DELIVERED = "delivered"
DEAD = "dead"

STATES = (HELD, RESERVED, DELIVERED, DEAD)
TERMINAL_STATES = (DELIVERED, DEAD)

# Why a code is dead. Named rather than free text for `retire_reason`'s reason: a reason
# nothing constrains becomes a field nothing can count, and the whole value of knowing a
# code is dead is knowing HOW MANY died which way — a supplier whose bulk is 8% redeemed is
# a different business decision from a buyer who disputed one code.
DEAD_REASONS = ("already_redeemed", "buyer_disputed", "duplicate", "withdrawn")

# How the code was read. The point of recording it is that the rungs have different
# reliabilities and the ledger is the only place that could ever show it: if disputes
# cluster on `vision` reads, the paid fallback is costing more than it saves.
SOURCE_QR = "qr"
SOURCE_VISION = "vision"
SOURCE_HUMAN = "human"
SOURCES = (SOURCE_QR, SOURCE_VISION, SOURCE_HUMAN)

_G3, _G4 = "[A-Z0-9]{3}", "[A-Z0-9]{4}"
_SHAPE = re.compile("^" + "-".join((_G3, _G4, _G3, _G3)) + "$")


class LedgerError(RuntimeError):
    """The ledger could not be read or a write was refused."""


class UnknownCodeState(LedgerError):
    """A state outside `STATES`. Never coerced, never defaulted."""


class CodeNotHeld(LedgerError):
    """A reservation was asked for against a code that is not `held`.

    THE ONE REFUSAL THAT PROTECTS THE MONEY. Reserving an already-reserved code is how a
    code gets sold twice, and the fork's hard rules call double-selling unrecoverable. It
    is a refusal rather than a no-op precisely so a caller cannot mistake it for success.
    """


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_state(state: str) -> str:
    if state not in STATES:
        raise UnknownCodeState(f"{state!r} not in {STATES}")
    return state


def well_formed(code: str) -> bool:
    """Whether a code matches the printed 3-4-3-3 layout C1 recorded.

    REPORTED, NEVER ENFORCED — `codes/qr.py:QrRead.well_formed` carries the full argument.
    A code that survived the QR's own error correction is far likelier to be a layout this
    repo has not met than a misread.
    """
    return bool(code and _SHAPE.match(code))


@dataclass
class Entry:
    """One code. `code` is the identity; everything else describes or tracks it."""

    code: str
    state: str = HELD
    # Where the photograph is. Kept as a path AND a digest because D24 destroys the card:
    # once that happens the photograph is the only surviving evidence of what was printed,
    # and a path alone cannot tell you the file was later replaced by a re-shoot (D26).
    photo: Optional[str] = None
    photo_sha256: Optional[str] = None
    box: Optional[int] = None
    index: Optional[int] = None
    # What product this code redeems. `product` is the key from `codes/products.py`;
    # `set_hint` is the operator's own claim as typed at capture; `sku` is the resolved
    # TCGplayer catalog Product Name where one was found. All three, because they fail
    # independently: the operator can be right where the catalog has no row, and the
    # catalog can name a row for a set the operator never claimed.
    set_hint: Optional[str] = None
    product: Optional[str] = None
    sku: Optional[str] = None
    source: Optional[str] = None
    # Which ladder rung and which detector answered, for `codes/qr.py`'s reads. Diagnostic
    # only, and cheap: a track where `upscale2x` suddenly answers most frames has a rig
    # that moved, and nothing else in this repo would notice.
    rung: Optional[str] = None
    detector: Optional[str] = None
    scanned_at: Optional[str] = None
    run: Optional[str] = None
    # The sale. Written together by `reserve`, and never one without the others.
    order_id: Optional[str] = None
    buyer: Optional[str] = None
    reserved_at: Optional[str] = None
    delivered_at: Optional[str] = None
    dead_reason: Optional[str] = None
    state_at: Optional[str] = None
    # Every OTHER position this same code was read at. Empty on the overwhelming majority.
    # A non-empty list is a real finding and not a bookkeeping artefact: either one physical
    # card was photographed twice, or the supplier shipped two cards bearing one code, and
    # the second case means one of them is worth nothing. Named so a human can look at both
    # photographs and decide, rather than resolved by a rule that would be wrong half the
    # time.
    duplicate_positions: List[Dict[str, object]] = field(default_factory=list)

    @property
    def sellable(self) -> bool:
        return self.state == HELD

    def to_payload(self) -> dict:
        out = dict(self.__dict__)
        out["duplicate_positions"] = list(self.duplicate_positions)
        return out

    @classmethod
    def parse(cls, payload: dict) -> "Entry":
        known = {k: v for k, v in payload.items() if k in cls.__annotations__}
        entry = cls(**known)
        entry.duplicate_positions = list(entry.duplicate_positions or [])
        return entry


def path():
    return store_files.codes_ledger_path()


def read(where=None) -> List[Entry]:
    return [Entry.parse(row) for row in store_files.read_jsonl(where or path())]


def index_by_code(entries: Iterable[Entry]) -> Dict[str, Entry]:
    return {entry.code: entry for entry in entries}


def write(entries: Sequence[Entry], where=None) -> None:
    """Rewrite the ledger whole, through the atomic replace `store_files` already owns.

    WHOLE RATHER THAN UPSERT-BY-KEY, unlike C8's first build. `upsert_jsonl` is the right
    primitive for a file whose writers only ever touch their own lines; this ledger has
    writers that MOVE a line's identity — a duplicate merges two reads into one entry — and
    an upsert cannot express a delete. The file is one line per code and a pile of ten
    thousand codes is under two megabytes, so rewriting it costs nothing worth optimising.
    """
    store_files.write_atomic(
        store_files.Path(where or path()),
        "".join(
            store_files.json.dumps(entry.to_payload(), sort_keys=True) + "\n"
            for entry in entries
        ).encode("utf-8"),
    )


def merge(existing: Sequence[Entry], reads: Sequence[Entry]) -> Tuple[List[Entry], Dict[str, int]]:
    """Fold fresh reads into the ledger. Returns (entries, counts).

    IDEMPOTENT BY CONSTRUCTION, which is what makes re-running a scan free. A read of a
    code already on file at the SAME position updates that line in place; the whole scan
    can be run again after a crash and the ledger is identical.

    A read of a code already on file at a DIFFERENT position is the duplicate case and is
    recorded rather than resolved: the incoming position joins `duplicate_positions` and
    the entry's state is untouched. Deciding which of two identical codes is the real one
    is a human's job with two photographs in front of them, and a rule that picked the
    earlier one would be wrong exactly as often as it was right.

    A read is NEVER allowed to move a code out of a terminal state. A code that was
    delivered to a buyer and then re-scanned off a photograph is still delivered; silently
    returning it to `held` would offer it for sale a second time, which is the one outcome
    this module exists to prevent.
    """
    by_code = {entry.code: entry for entry in existing}
    counts = {"new": 0, "updated": 0, "duplicate": 0, "terminal_skipped": 0}

    for fresh in reads:
        current = by_code.get(fresh.code)
        if current is None:
            fresh.state_at = fresh.state_at or now()
            by_code[fresh.code] = fresh
            counts["new"] += 1
            continue
        same_place = (current.box, current.index) == (fresh.box, fresh.index)
        if not same_place:
            place = {"box": fresh.box, "index": fresh.index, "photo": fresh.photo}
            if place not in current.duplicate_positions:
                current.duplicate_positions.append(place)
                counts["duplicate"] += 1
            continue
        if current.state in TERMINAL_STATES:
            counts["terminal_skipped"] += 1
            continue
        # Same code, same position, still live: refresh what the read knows and leave the
        # sale fields and the state exactly where they were.
        for attr in ("photo", "photo_sha256", "set_hint", "product", "sku",
                     "source", "rung", "detector", "scanned_at", "run"):
            value = getattr(fresh, attr)
            if value is not None:
                setattr(current, attr, value)
        counts["updated"] += 1

    return list(by_code.values()), counts


def reserve(entries: Sequence[Entry], code: str, *, order_id: str, buyer: Optional[str] = None) -> Entry:
    """Assign one code to an order. Refuses anything that is not `held`.

    THE ATOMIC STEP C3 ASKS FOR, and the atomicity is the CALLER's: this function mutates
    an in-memory list and the caller writes it inside the store lock, exactly as every
    other write under `inventory/` works. Putting a lock in here would give the store two
    locking disciplines, and the one that exists already serialises the capture server
    against the CLI.
    """
    for entry in entries:
        if entry.code != code:
            continue
        if entry.state != HELD:
            raise CodeNotHeld(
                f"{code[:3]}-**** is {entry.state}, not {HELD}; it cannot be reserved. "
                "A code is assigned to exactly one order, ever."
            )
        entry.state = RESERVED
        entry.order_id = order_id
        entry.buyer = buyer
        entry.reserved_at = now()
        entry.state_at = entry.reserved_at
        return entry
    raise LedgerError(f"{code[:3]}-**** is not in the ledger")


def take(entries: Sequence[Entry], *, order_id: str, count: int,
         product: Optional[str] = None, buyer: Optional[str] = None) -> List[Entry]:
    """Reserve `count` sellable codes for one order, optionally narrowed to a product.

    ALL OR NOTHING. A partial fill would leave an order half-served and some codes reserved
    against it, which is worse than refusing: the operator can buy more stock or split the
    order, but cannot easily discover that three of the fifty went out and forty-seven did
    not. `sellable` is the only filter — a duplicate is still sellable, because exactly one
    of the two cards bearing that code is genuine and the ledger holds ONE entry for it.
    """
    pool = [e for e in entries if e.sellable and (product is None or e.product == product)]
    if len(pool) < count:
        raise LedgerError(
            f"{count} requested, {len(pool)} sellable"
            + (f" for product {product!r}" if product else "")
            + " — nothing was reserved"
        )
    return [reserve(entries, e.code, order_id=order_id, buyer=buyer) for e in pool[:count]]


def deliver(entries: Sequence[Entry], code: str) -> Entry:
    for entry in entries:
        if entry.code == code:
            if entry.state != RESERVED:
                raise CodeNotHeld(f"{code[:3]}-**** is {entry.state}; only a reserved code is delivered")
            entry.state = DELIVERED
            entry.delivered_at = now()
            entry.state_at = entry.delivered_at
            return entry
    raise LedgerError(f"{code[:3]}-**** is not in the ledger")


def kill(entries: Sequence[Entry], code: str, reason: str) -> Entry:
    """Mark a code dead. Reachable from any state, including a delivered one.

    FROM ANY STATE ON PURPOSE. The commonest real path to `dead` is a buyer reporting that
    a DELIVERED code did not work — which is C6's replace-don't-refund case — and a state
    machine that refused it would leave the one event the ledger most needs to record with
    nowhere to go.
    """
    if reason not in DEAD_REASONS:
        raise LedgerError(f"{reason!r} not in {DEAD_REASONS}")
    for entry in entries:
        if entry.code == code:
            entry.state = DEAD
            entry.dead_reason = reason
            entry.state_at = now()
            return entry
    raise LedgerError(f"{code[:3]}-**** is not in the ledger")


def counts(entries: Iterable[Entry]) -> Dict[str, int]:
    out = {state: 0 for state in STATES}
    for entry in entries:
        out[entry.state] = out.get(entry.state, 0) + 1
    return out
