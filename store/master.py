"""`inventory.json` — cards, positions, SKUs, listing states.

One record per PHYSICAL CARD, keyed by position, never per SKU. D7 collapses copies to one
import row but keeps every copy as its own position with its own photo, because that is what
makes an order pull addressable: the app maps SKU -> all positions holding it, and the pull
marks one of them sold. Aggregation is a property of the import file, not of the inventory.

TWO KINDS OF STATE, WITH TWO DIFFERENT SUBJECTS. This header used to describe one, and the
distinction D7's amendment drew is the whole of what changed.

A CARD'S STATE describes one piece of cardboard:

    captured    a photo and a position exist
    identified  the model answered for it
    sold        this specific copy left inventory through a sale
    retired     it left without one — pulled, damaged, lost or given away (D26)

A SKU'S LISTING holds quantities, on `Listing`, and names no position at all:

    pushed      `emit` wrote that many rows into an import file
    staged      an Export From Staged download confirmed TCGplayer has them
    live        a later Filtered Export shows that quantity against the SKU

`pushed`, `staged` and `live` were card states until 2026-08-23, and moving them was the
owner's ruling that copies are FUNGIBLE: "if i have 15 of one copy and mark 3 as live, it's
any 3 are live, not 3 specific locations are live". As card states they made listing
progress an ADDRESS — `cli/cmd_join.py` picked which four of seven identical copies were
sellable, for no physical reason. `check_state` now refuses all three, which is the guard
that stops a caller reaching for the old per-position flag and getting silence back.

Writing a CSV proves only that a CSV was written, so each stage past `pushed` is still
confirmed by something outside this pipeline, and the three stay separate for the reason
they always did: `Add to Quantity = min(cap - live, backstock)` reads the LIVE number, and
an import that was staged and never moved live has no live quantity at all — so collapsing
them would refill against inventory that is not for sale.

POSITIONS ARE ASSIGNED HERE, by `allocate_capture` and nowhere else. It takes a box and no
index, so there is no parameter through which a caller's stale read can enter a write.
`record_capture` still accepts an explicit position, because `identify` and `emit` re-record
cards they did not allocate — that is a seam to watch rather than a guarantee, and the
safety is that the capture server never calls it.

Positions are never renumbered and sold cards leave permanent gaps (D10). Nothing in this
module deletes a card record; `sold` is a state, not a removal.

T7 REACHES THIS FILE, as of 2026-08-13. `harness/tests/t7_store_and_seams.py` imports this
module and drives the allocator directly: sequential positions that never collide, the
newest-record deletion undo inherits (D10), a replayed `capture_id` that burns no second
index, the string-typed record that once slipped past the box filter and handed back a
colliding index, and `BadPosition`, `DuplicateCaptureId` and `UnknownState` each refusing in
their own code.

The paragraph here said the opposite, and it outlived the gap it described — true from step 5
on 2026-08-11 until T7 landed two days later, wrong for the nine days after that. Corrected in
place rather than swapped quietly, because nothing mechanical checks a claim of this kind: the
audit resolves paths and thresholds, and a docstring asserting its own coverage is exactly the
sentence it cannot read.

WHAT T7 STILL DOES NOT ASSERT is in `docs/DEBTS.md`, so a green harness is read for what it
is rather than as coverage of everything below.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

VERSION = 2

CAPTURED = "captured"
IDENTIFIED = "identified"
SOLD = "sold"

# `sold`'s sibling (D26): this copy left inventory WITHOUT a sale — pulled out, damaged,
# lost or given away. Terminal like `sold`: the record stays, the position stays, and the
# gap it leaves is permanent (D10). Before it existed the only ways to record such a card
# were a sale record that lies or the mid-box delete D10 forbids.
#
# THE NAME IS `retired` AND DELIBERATELY NOT `removed`. `removed` was the drafted name and
# the owner renamed it on 2026-08-23, because it is already taken: the capture server
# appends a `removed` HISTORY EVENT when undo hard-deletes a record, T7 asserts that no
# event name is a member of this module's `STATES`, and `_state_before_sale` scans history
# filtering against this tuple — a state called `removed` would make months-old undo events
# parse as states, and a reversed sale restorable to one. The event keeps its on-disk name;
# the state gets its own word.
RETIRED = "retired"

# A POSITION'S STATE DESCRIBES ONE PHYSICAL CARD AND NOTHING ELSE (D7, amended).
#
# `pushed`, `staged` and `live` used to live in this tuple, and a card wore one of them the
# way it wore `captured`. That made listing progress an address: `cli/cmd_join.py` picked
# WHICH positions became live, so four of seven copies were sellable and three were not, for
# no physical reason at all. The owner's ruling is that copies of one SKU are fungible — "if
# i have 15 of one copy and mark 3 as live, it's any 3 are live, not 3 specific locations are
# live". So the three moved off the card and onto the SKU, below, as counts.
STATES = (CAPTURED, IDENTIFIED, SOLD, RETIRED)

# The two ways a card leaves inventory, by different doors: a sale, or D26's retirement.
# Both keep the record and leave a permanent gap; neither copy is on hand, sellable, or
# countable as backstock. `copies_on_hand` filters on this tuple rather than on `SOLD`
# alone, which is what keeps a retired copy out of D7's refill arithmetic — an emit that
# still counted it would list a card that is no longer in the box.
TERMINAL_STATES = (SOLD, RETIRED)

# Why a retired card left (D26). Required of every retirement and never inferred: it is the
# one fact about the departure the record cannot re-derive later, and the four are a closed
# vocabulary so the history stays greppable — free text would be a second `note`.
RETIRE_REASONS = ("pulled", "damaged", "lost", "given_away")

PUSHED = "pushed"
STAGED = "staged"
LIVE = "live"

# The three stages of one SKU's journey through TCGplayer, held as quantities on `Listing`.
# Deliberately NOT members of `STATES`: `check_state` refuses them, which is what stops a
# caller reaching for the old `set_state(key, LIVE)` and getting a silent per-position flag
# back. Same guard the server's SERVER_EVENTS rely on.
LISTING_STAGES = (PUSHED, STAGED, LIVE)

# What a v1 file could carry on a card. Read by `Inventory.parse`'s migration and by nothing
# else — never widen `check_state` with these.
LEGACY_STATES = (PUSHED, STAGED, LIVE)

# Copies sitting staged this long and still not live are named in the run report — an import
# that was staged and then never moved live is invisible otherwise, and it is a whole box not
# earning. Now a property of a SKU's listing rather than of a position.
STAGED_STALE_DAYS = 14


class UnknownState(ValueError):
    """A listing state outside the enum. Never coerced."""


# These subclass `ValueError` like `UnknownState` above, and NOT `store.files.StoreError`,
# which is the obvious-looking alternative. The reason is structural rather than stylistic:
# this module imports nothing from the rest of the package, and `StoreError` lives in
# `store/files.py`, so inheriting from it would give `master.py` its first intra-package
# import to buy nothing. Do not "fix" the inconsistency — it is the isolation.


class BadPosition(ValueError):
    """A stored box or index that will not parse as an integer. Never coerced past."""


class PositionOccupied(ValueError):
    """`allocate_capture` computed an index that already holds a card. Never upserted."""


class DuplicateCaptureId(ValueError):
    """Two cards carry one `capture_id`. The replay lookup refuses rather than guessing."""


class UnknownRetireReason(ValueError):
    """A retire reason outside `RETIRE_REASONS`. Never coerced, never defaulted."""


def check_state(state: str) -> str:
    if state not in STATES:
        raise UnknownState(f"{state!r} not in {STATES}")
    return state


def check_retire_reason(reason: str) -> str:
    if reason not in RETIRE_REASONS:
        raise UnknownRetireReason(f"{reason!r} not in {RETIRE_REASONS}")
    return reason


def position_key(box: int, index: int) -> str:
    return f"{int(box)}/{int(index)}"


def _as_position_int(value, where: str) -> int:
    """Coerce a stored box or index, or refuse naming the record it came from.

    This helper exists instead of a bare comparison because of a combination that hides
    itself: `Inventory.parse` reconstructs cards straight from JSON and coerces nothing,
    while `position_key` coerces with `int()`. A record written with a string box therefore
    keeps a perfectly ordinary-looking key and a mistyped field, and the two ways of
    getting it wrong fail differently — `c.box == box` drops the record silently and hands
    out an index that collides later, while coercing only the box feeds a string into
    `max()` and raises inside the lock. Measured, both of them, before this was written.

    Reachable from the capture server, which takes `box` out of a JSON request body: a
    client sending a string writes a string, and `asdict` round-trips it to disk.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        raise BadPosition(f"{where} is {value!r}, which is not an integer") from None


def now() -> str:
    """UTC, to the MILLISECOND — and the third decimal place is the whole point.

    This was `timespec="seconds"` until 2026-08-22, when Gate B showed what that costs. The
    feeder delivers a card roughly every 660ms, so whole-second stamps are coarser than the
    thing they are timing: the run's 53 captures collapsed to a gap sequence of 0s and 1s
    with a median absolute deviation of exactly 0.0, which reads as a perfectly regular
    machine and is an artifact of the truncation. The real jitter — 34ms — was recoverable
    only because APFS happened to preserve `st_birthtime` on the photographs through an
    unrelated rewrite, and that is filesystem metadata: it does not survive a clone, a copy,
    or an iCloud eviction of a repo that lives on iCloud Drive.

    Gate C tunes an auto-capture trigger against that cadence. It should not have to hope
    for a second accident, so the measurement is a property of the store now.

    `datetime.fromisoformat` parses both forms, so every stamp already on disk still reads.
    """
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _days_since(stamp: Optional[str]) -> Optional[int]:
    if not stamp:
        return None
    try:
        when = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - when).days


@dataclass
class Card:
    """One physical card at one position."""

    box: int
    index: int
    photo: Optional[str] = None
    set_hint: Optional[str] = None
    metadata_finish: Optional[str] = None
    captured_at: Optional[str] = None
    # Idempotency key for one POST /capture. Optional because every record predating the
    # capture server has none, and `parse` filters on `Card.__annotations__`, so a field
    # that is not declared here is dropped on reload rather than kept — which is why the
    # retry guard could not live in the sidecar alone.
    capture_id: Optional[str] = None
    # WHICH GAME THE OPERATOR SAID THIS CARD IS (D21). Optional here and required on the
    # capture screen, and those two are not in conflict: the field is required of the CLAIM
    # — the picker always has an answer and always sends it — while `None` here means the
    # record predates the field, which is exactly the read-side backfill D21 sanctions.
    # `pipeline/games.DEFAULT_GAME` is applied where such a record is READ, never here,
    # because a write-side default would make "the operator said Pokemon" and "nobody was
    # asked" the same value on disk forever after.
    game: Optional[str] = None
    # D23's multi-select rarity claim: the exact `Rarity` cells the operator said this
    # card's stack holds, set per stack on the capture screen like `metadata_finish` and
    # resent with every capture. `None` is no claim and narrows nothing — the compatibility
    # default, and unlike `game` above there is no backfill to apply at the read, because
    # no claim is a complete answer. A LIST because `asdict` round-trips it to JSON as one;
    # order is the registry's stack order as the capture screen sends it, and nothing
    # downstream depends on it.
    rarity_claim: Optional[List[str]] = None
    # Free text, and the only claim on this record a human writes in prose. It exists for
    # the ~1% of stock that is neither identified nor joined — the occasional Yu-Gi-Oh,
    # Weiss Schwarz, foreign-language or Magic card — where the operator says what it is so
    # that `do_search` can find it later. Never parsed, never matched against a catalog.
    note: Optional[str] = None
    name: Optional[str] = None
    number: Optional[str] = None
    printed_total: Optional[str] = None
    confidence: Optional[str] = None
    sku: Optional[str] = None
    condition: Optional[str] = None
    state: str = CAPTURED
    state_at: Optional[str] = None
    # Why a retired card left — one of `RETIRE_REASONS`, set by `retire()` and cleared by
    # the route that reverses one; None on every card in any other state. NOT a capture
    # claim, and deliberately absent from `CAPTURE_CLAIM_FIELDS` below: a claim survives a
    # re-record and is settable at capture time, while this describes a departure — a
    # capture that could write it would retire a card by photographing it, and a re-record
    # by `identify` or `emit` must neither resurrect nor clear it (D26).
    retire_reason: Optional[str] = None
    run: Optional[str] = None

    @property
    def key(self) -> str:
        return position_key(self.box, self.index)

    @property
    def days_in_state(self) -> Optional[int]:
        return _days_since(self.state_at)


class UnknownClaim(ValueError):
    """A capture tried to write a field that is not a capture claim."""


# ---------------------------------------------------------------- the capture claims
#
# EVERY FIELD A CAPTURE WRITES, IN ONE PLACE, read by `allocate_capture`, `record_capture`
# and — through `server/capture_server.py:CLAIM_WIRE_NAMES` — by the sidecar writer and the
# correction route. `docs/DEBTS.md` recorded the absence of this tuple as the highest-value
# edit in the project, and the reason is the two silences it closes:
#
#   `Inventory.parse` FILTERS ON `Card.__annotations__`. A field the dataclass does not
#   declare is dropped on reload, not kept. The record is written, the response is correct,
#   the file on disk carries the value, and the next read hands back a card that never had
#   it. That filter is right — `Card.capture_id`'s own comment explains why the retry guard
#   could not live in the sidecar alone — and its SILENCE is the debt. The assertion below
#   turns it into a refusal at import.
#
#   `record_capture` USED TO UPSERT OVER A LITERAL TUPLE. A fourth claim added everywhere
#   else in the chain would survive its first capture and be discarded by every re-record —
#   which works until the operator corrects a card, and is the harder failure to see.
#
# WHAT THIS TUPLE CANNOT REACH, stated here so it is not read as more than it is: the three
# app-side hops. `app/src/CaptureScreen.tsx`, `app/src/types.ts` and `app/src/server.ts` stay
# hand-carried whatever this file does, because no Python constant reaches a `.tsx` and
# `make typecheck` sees a field ADDED to the wire types and never one omitted from them. The
# chain is narrowed, not closed.
#
# `photo` IS THE ONE MEMBER NO CLIENT EVER SENDS. It is derived — the path is not knowable
# until the index is allocated — but it is a claim in every other respect: it is set at
# capture, it must survive a re-record, and `identify` and `emit` both re-record it.
CAPTURE_CLAIM_FIELDS = ("photo", "set_hint", "metadata_finish", "game", "rarity_claim", "note")

_undeclared = [name for name in CAPTURE_CLAIM_FIELDS if name not in Card.__annotations__]
if _undeclared:  # pragma: no cover - import-time contract, not a branch under test
    raise RuntimeError(
        "store/master.py:CAPTURE_CLAIM_FIELDS names "
        + ", ".join(repr(name) for name in _undeclared)
        + ", which `Card` does not declare. `Inventory.parse` filters on "
        "`Card.__annotations__`, so such a field would be written, answered, stored — and "
        "dropped on the next reload, silently. Declare it on `Card`."
    )


BOX_OPEN = "open"
BOX_CLOSED = "closed"
BOX_STATES = (BOX_OPEN, BOX_CLOSED)


class BadSections(ValueError):
    """A divider layout that is not a sorted, unique run of indices starting at 1."""


class BoxClosed(ValueError):
    """A write against a sealed box. Capacity is frozen; nothing more goes in."""


class UnknownBox(ValueError):
    """A box number no registry entry covers."""


def check_box_state(state: str) -> str:
    if state not in BOX_STATES:
        raise UnknownState(f"{state!r} not in {BOX_STATES}")
    return state


def check_sections(sections) -> Tuple[int, ...]:
    """Coerce and validate a divider layout, or refuse naming what is wrong with it.

    A layout is the indices each section STARTS at, so the first is always 1 — there is no
    card before the first divider. Sorted and unique, because two dividers at one index is a
    section holding no cards, and an unsorted list makes `Position.section` a scan whose
    answer depends on write order.

    Refuses rather than repairing. A layout is typed by a human on the Boxes screen and a
    silently sorted one would relabel a box without saying so, which is the exact failure
    D10's amended entry accepts the risk of and asks to be made visible.
    """
    try:
        out = tuple(int(v) for v in sections)
    except (TypeError, ValueError):
        raise BadSections(f"{sections!r} is not a list of integers") from None
    if not out:
        # UNDECLARED, and legal. An empty layout is what every box migrated from v1 carries
        # and what a new box starts with; `pipeline/join.py:Position` falls back to
        # CARDS_PER_SECTION for it, which is what keeps every label written before this
        # change byte-identical. Materialising the implied dividers is the SERVER's job
        # (it already imports Position), never this module's — `store/master.py` importing
        # `pipeline` to learn a divider size would trade the isolation this file is built
        # on for a constant it can be handed instead.
        return out
    if out[0] != 1:
        raise BadSections(f"the first section starts at index 1, not {out[0]}")
    if list(out) != sorted(out):
        raise BadSections(f"{list(out)} is not sorted")
    if len(set(out)) != len(out):
        raise BadSections(f"{list(out)} repeats an index — two dividers in one slot")
    if out[0] < 1:
        raise BadSections("indices are 1-based")
    return out


@dataclass
class Box:
    """One physical box: what it is called, where its dividers sit, whether it is sealed.

    D20 — the first box entity in this repo. Before it, a box existed only because a card
    named one, so it could not be created empty, named, or found by any screen but Capture,
    and a mistyped number was caught only by the `new_box` flag AFTER a photo was written.

    CAPACITY IS RETROACTIVE, and that is the whole of the lifecycle. While a box is open it
    has none: the honest denominator is the fill so far, and a screen saying "#40 of 53" has
    to say "so far" because tomorrow it is 54. Sealing the box freezes `capacity` at the
    final high-water mark, and only then does "#40 of 250 · 16% in" become a sentence that
    is true next week. Owner's ruling, and the reason a capacity field is not asked for at
    creation time: nobody knows it then.

    Sold cards leave permanent gaps (D10) and the high-water mark holds, so a sealed box's
    capacity never falls as its contents sell.
    """

    box: int
    name: Optional[str] = None
    sections: List[int] = field(default_factory=list)
    state: str = BOX_OPEN
    capacity: Optional[int] = None
    created_at: Optional[str] = None
    closed_at: Optional[str] = None

    @property
    def key(self) -> str:
        return str(int(self.box))

    @property
    def closed(self) -> bool:
        return self.state == BOX_CLOSED

    def layout(self) -> Tuple[int, ...]:
        """The divider indices, validated. What `pipeline/join.py:Position` renders from.

        Empty means undeclared, and `Position` renders those with the default divider size.
        """
        return check_sections(self.sections)


@dataclass
class Listing:
    """One SKU's progress through TCGplayer, as QUANTITIES rather than as addresses.

    D7 (amended). `pushed`, `staged` and `live` are counts of copies at each stage, and
    which physical copies they are is deliberately not recorded — every unsold copy of a SKU
    is equally sellable, so an address here would be a fiction the pull then has to honour.

    `live` IS AN OPTIMISTIC LOCAL ESTIMATE BETWEEN RUNS, and always was. D8 and D11 put the
    authority in the TCGplayer export's `Total Quantity`, which `./pkmnscan join` reads on
    every run — so a sale decrementing this number is a guess that the next join corrects,
    never a second source of truth competing with the export.
    """

    sku: str
    condition: Optional[str] = None
    pushed: int = 0
    staged: int = 0
    live: int = 0
    at: Optional[str] = None
    staged_at: Optional[str] = None

    @property
    def held(self) -> int:
        """Copies TCGplayer is holding for this SKU that its live quantity does NOT report.

        `pushed + staged`, and **`live` is deliberately excluded.** The reason lives here
        rather than at the call site because getting it wrong is invisible:
        `pipeline/join.py:SkuMatch.add_to_quantity` already subtracts `live_before`, which
        it reads straight off the export's `Total Quantity`. Counting `live` again here
        subtracts the same copies twice — a SKU with 3 live, 6 copies on hand and a Total
        Quantity of 3 would compute room for 0 instead of 1, and would under-list by one
        copy forever after. Measured by the Phase 3 rewrite; do not "simplify" it to
        `pushed + staged + live`.
        """
        return max(0, int(self.pushed)) + max(0, int(self.staged))

    def set(self, stage: str, value: int) -> int:
        """Set one stage absolutely, floored at zero. Returns the new value.

        `join` reads `live` off the export and assigns it rather than nudging it, because
        D8 and D11 put the authority there — the stored number is an estimate and the
        export is the fact. Separate from `bump` so that a caller has to say which of the
        two it means, and so neither has to re-stamp `at` by hand.
        """
        if stage not in LISTING_STAGES:
            raise UnknownState(f"{stage!r} not in {LISTING_STAGES}")
        value = max(0, int(value))
        setattr(self, stage, value)
        self.at = now()
        if stage == STAGED and value > 0:
            self.staged_at = self.staged_at or self.at
        return value

    def bump(self, stage: str, by: int = 1) -> int:
        """Move one stage's count by `by`, floored at zero. Returns the new value."""
        if stage not in LISTING_STAGES:
            raise UnknownState(f"{stage!r} not in {LISTING_STAGES}")
        value = max(0, int(getattr(self, stage)) + int(by))
        setattr(self, stage, value)
        self.at = now()
        if stage == STAGED and by > 0:
            self.staged_at = self.at
        return value


@dataclass
class Inventory:
    """The master record. Rewritten whole, always through `store.session`."""

    cards: Dict[str, Card] = field(default_factory=dict)
    boxes: Dict[str, Box] = field(default_factory=dict)
    listings: Dict[str, Listing] = field(default_factory=dict)
    events: List[dict] = field(default_factory=list)

    # ------------------------------------------------------------------ (de)serialising

    @classmethod
    def parse(cls, payload: Optional[dict]) -> "Inventory":
        payload = payload or {}
        try:
            version = int(payload.get("version") or 1)
        except (TypeError, ValueError):
            version = 1

        cards: Dict[str, Card] = {}
        boxes: Dict[str, Box] = {}
        listings: Dict[str, Listing] = {}

        for key, record in (payload.get("boxes") or {}).items():
            known = {k: v for k, v in record.items() if k in Box.__annotations__}
            boxes[str(key)] = Box(**known)
        for key, record in (payload.get("listings") or {}).items():
            known = {k: v for k, v in record.items() if k in Listing.__annotations__}
            listings[str(key)] = Listing(**known)

        for key, record in (payload.get("cards") or {}).items():
            known = {k: v for k, v in record.items() if k in Card.__annotations__}
            card = Card(**known)

            # MIGRATION v1 -> v2. A card wearing a listing stage becomes `identified` and
            # hands that stage to its SKU as a count. Runs only against a v1 payload, so a
            # v2 file carrying a stage on a card is left alone to fail `check_state` loudly
            # rather than being quietly repaired on every read.
            if version < VERSION and card.state in LEGACY_STATES:
                stage = card.state
                card.state = IDENTIFIED
                if card.sku:
                    entry = listings.get(card.sku)
                    if entry is None:
                        entry = Listing(sku=card.sku, condition=card.condition)
                        listings[card.sku] = entry
                    setattr(entry, stage, int(getattr(entry, stage)) + 1)
                    entry.at = entry.at or card.state_at
                    if stage == STAGED:
                        entry.staged_at = entry.staged_at or card.state_at
            cards[key] = card

        # Every box a card names gets a registry entry, with NO declared layout — which is
        # what makes the migration label-preserving. `Position` renders an empty layout with
        # the default divider size, so a card that read `Box 1 · Section 3 · Card 3` before
        # this change reads exactly that after it.
        if version < VERSION:
            for card in cards.values():
                try:
                    number = _as_position_int(card.box, "box")
                except BadPosition:
                    continue
                boxes.setdefault(str(number), Box(box=number))

        return cls(cards=cards, boxes=boxes, listings=listings)

    def to_payload(self) -> dict:
        return {
            "version": VERSION,
            "cards": {key: asdict(card) for key, card in sorted(self.cards.items())},
            "boxes": {key: asdict(box) for key, box in sorted(self.boxes.items())},
            "listings": {
                key: asdict(entry) for key, entry in sorted(self.listings.items())
            },
        }

    # ------------------------------------------------------------------------- writing

    def next_index(self, box) -> int:
        """The index `allocate_capture` would assign next in `box`. DISPLAY ONLY.

        High-water mark: `1 + max(index in this box)`, counting every state. Not count+1,
        which agrees only while the set is dense and disagrees the moment a record is
        removed; not first-free, which contradicts D10 — sold cards leave permanent gaps,
        and the next captured card goes on the end of the stack because that is where the
        operator's hand puts it.

        An unparsable box or index stops the scan rather than being skipped. Skipping one
        would hide exactly the collision it is about to cause, since the record still owns
        its key.

        Never pass this value into a write. Reading it and then recording is two lock
        acquisitions with a network round trip between them, which is the lost update
        `store/__init__.py` spends a paragraph on; `allocate_capture` takes no index so
        that there is no parameter to pass it through.
        """
        box = _as_position_int(box, "box")
        highest = 0
        for key, card in self.cards.items():
            if _as_position_int(card.box, f"box of card {key}") != box:
                continue
            highest = max(highest, _as_position_int(card.index, f"index of card {key}"))
        return highest + 1

    def allocate_capture(
        self,
        box,
        *,
        capture_id: Optional[str] = None,
        **claims,
    ) -> Tuple[Card, bool]:
        """Assign the next index in `box` and record the card. Returns `(card, created)`.

        `**claims` IS THE PASS-THROUGH, BOUND TO `CAPTURE_CLAIM_FIELDS` RATHER THAN RESTATED.
        It used to be four named keyword arguments, which made this the second of the three
        places that wrote the same list out by hand — and the one where adding a claim looked
        most obviously complete while `record_capture` below quietly kept discarding it. The
        cost of `**` is that a caller loses the signature as documentation; the tuple and its
        import-time assertion are what pay for that, and a misspelled keyword refuses by name
        here instead of raising `TypeError` from a `Card` constructor two frames down.

        The one sanctioned way to create a capture. Call it inside
        `store.session.Store.write()` — the lock plus the re-read inside it are what make
        the high-water read and the record a single step.

        `created` is False only when `capture_id` replays a capture already recorded. That
        is the retry guard: a response lost between commit and client makes the app repost,
        and without it the retry burns a second index and leaves two records for one
        physical card. The lookup is a linear scan, which is correct at a few thousand
        cards and not worth an index; two cards sharing one id is a refusal rather than a
        guess at which was meant.

        On collision it raises instead of upserting. `record_capture` would take its
        existing-record branch and copy photo, set hint and recorded variant over the
        incumbent, returning it with no log and nothing reported — a physical card gone
        from inventory. That branch is right for a re-record and wrong for an allocation,
        so this path refuses to reach it.
        """
        box = _as_position_int(box, "box")

        # Before anything is allocated, so a misspelled claim burns no index — the same
        # ordering the sealed-box check below argues for.
        unknown = sorted(set(claims) - set(CAPTURE_CLAIM_FIELDS))
        if unknown:
            raise UnknownClaim(
                f"{', '.join(unknown)} is not a capture claim. "
                f"Capture writes: {', '.join(CAPTURE_CLAIM_FIELDS)}. Adding one means "
                "declaring it on `Card` and naming it in CAPTURE_CLAIM_FIELDS, so that "
                "`Inventory.parse` keeps it and `record_capture` carries it over a re-record."
            )

        if capture_id is not None:
            replay = self.card_by_capture_id(capture_id)
            if replay is not None:
                return replay, False

        # A SEALED BOX TAKES NO MORE CARDS. Checked before the index is computed, so a
        # refusal burns nothing — the same ordering `next_index`'s docstring argues for.
        # Capacity was frozen at the fill when the lid went on (D20); admitting one more
        # card would make every fraction drawn from it wrong by one.
        registered = self.boxes.get(str(box))
        if registered is not None and registered.closed:
            raise BoxClosed(
                f"box {box} is sealed at {registered.capacity} cards. "
                "Re-open it on the Boxes screen, or capture into another box."
            )
        self.ensure_box(box)

        index = self.next_index(box)
        key = position_key(box, index)
        if key in self.cards:
            raise PositionOccupied(
                f"allocate_capture computed {key}, which already holds a card. "
                "The high-water scan and this check disagree, which means the inventory "
                "was mutated outside the lock."
            )

        card = Card(box=box, index=index, capture_id=capture_id, **claims)
        return self.record_capture(card), True

    def card_by_capture_id(self, capture_id: str) -> Optional[Card]:
        """The card recorded under `capture_id`, or None. Refuses on a duplicate."""
        matches = [c for c in self.cards.values() if c.capture_id == capture_id]
        if len(matches) > 1:
            raise DuplicateCaptureId(
                f"{capture_id!r} is on {len(matches)} cards: "
                f"{', '.join(sorted(c.key for c in matches))}"
            )
        return matches[0] if matches else None

    def record_capture(self, card: Card) -> Card:
        """Upsert a captured card. An existing record keeps its state and its history."""
        existing = self.cards.get(card.key)
        if existing is None:
            card.captured_at = card.captured_at or now()
            card.state = card.state or CAPTURED
            card.state_at = card.state_at or card.captured_at
            self.cards[card.key] = card
            self._log(CAPTURED, card.key, photo=card.photo)
            return card

        # THE TUPLE, NOT A LITERAL LIST OF THREE NAMES. This loop is where a claim added
        # everywhere else in the chain used to be discarded — on a re-record only, so it
        # worked until the operator corrected a card. `docs/DEBTS.md` named it.
        for attribute in CAPTURE_CLAIM_FIELDS:
            value = getattr(card, attribute)
            if value is not None:
                setattr(existing, attribute, value)
        return existing

    def record_identification(
        self,
        key: str,
        *,
        name: Optional[str],
        number: Optional[str],
        printed_total: Optional[str],
        confidence: Optional[str],
        run: Optional[str] = None,
    ) -> None:
        card = self.cards.get(key)
        if card is None:
            return
        card.name = name
        card.number = number
        card.printed_total = printed_total
        card.confidence = confidence
        card.run = run or card.run
        if card.state == CAPTURED:
            self.set_state(key, IDENTIFIED, run=run)

    def set_state(
        self,
        key: str,
        state: str,
        *,
        sku: Optional[str] = None,
        condition: Optional[str] = None,
        run: Optional[str] = None,
    ) -> bool:
        """Move one card to a new state. Returns False if this position has no record.

        The return value is not decoration. A silent no-op on an unknown position is v1
        bug #5's exact shape — a transition that appears to happen, is reported as having
        happened, and did not — so callers check it and report the gap rather than
        assuming the write landed.
        """
        check_state(state)
        card = self.cards.get(key)
        if card is None:
            return False
        card.state = state
        card.state_at = now()
        if sku is not None:
            card.sku = sku
        if condition is not None:
            card.condition = condition
        if run is not None:
            card.run = run
        self._log(state, key, sku=card.sku, run=card.run)
        return True

    def retire(self, key: str, reason: str) -> bool:
        """Move one card to `retired`, carrying why it left. False if the position is empty.

        `set_state` with the reason attached, and ONE method rather than a `set_state` call
        plus a field assignment at every call site, because the two must not come apart: a
        `retired` state with no reason answers none of the questions the state exists for,
        and a reason on a card in any other state reads as a fifth state nothing defines.
        The history line carries the reason for the same one-or-neither argument — it is the
        only record of WHY once the retirement is later reversed and the field cleared (D26).

        The reason is validated here as well as at the route, because this module is the
        store's own boundary: a caller that bypassed the server must still be unable to
        write a reason outside the vocabulary.
        """
        check_retire_reason(reason)
        card = self.cards.get(key)
        if card is None:
            return False
        card.retire_reason = reason
        card.state = RETIRED
        card.state_at = now()
        self._log(RETIRED, key, sku=card.sku, run=card.run, reason=reason)
        return True

    def _log(self, event: str, key: Optional[str], **extra) -> None:
        # `position` is dropped rather than written null for a box-level event: a box is not
        # at a position, and a null one would read as a card whose position went missing.
        record = {"at": now(), "event": event}
        if key is not None:
            record["position"] = key
        record.update({k: v for k, v in extra.items() if v is not None})
        self.events.append(record)

    # -------------------------------------------------------------- boxes and listings

    def box(self, number) -> Optional[Box]:
        """The registry entry for this box, or None. Never invents one."""
        return self.boxes.get(str(_as_position_int(number, "box")))

    def ensure_box(self, number, *, name: Optional[str] = None) -> Box:
        """The box, creating an undeclared one if the registry has never seen it.

        Capture reaches this: `allocate_capture` puts a card in a box the owner may never
        have registered, and refusing there would make the registry a second thing to keep
        in step with the cards. A box created this way is open, unnamed and undeclared —
        exactly the shape the v1 migration produces, so the two paths cannot diverge.
        """
        number = _as_position_int(number, "box")
        entry = self.boxes.get(str(number))
        if entry is None:
            entry = Box(box=number, name=name, created_at=now())
            self.boxes[str(number)] = entry
            self._log("box_created", None, box=number, name=name)
        elif name is not None and entry.name != name:
            entry.name = name
        return entry

    def set_sections(self, number, sections) -> Tuple[int, ...]:
        """Declare a box's divider layout. Refuses a bad one; never repairs it.

        D10 (amended): the INDEX never moves, and this does not touch one. What moves is the
        LABEL — every card behind an edited divider renders in a different section from now
        on. That is correct when the layout was wrong and silent when the edit was, which is
        why the caller logs `resectioned` with both layouts rather than this refusing the
        operation.
        """
        entry = self.ensure_box(number)
        before = list(entry.sections)
        layout = check_sections(sections)
        entry.sections = list(layout)
        self._log(
            "resectioned", None, box=entry.box, sections_from=before, sections_to=list(layout)
        )
        return layout

    def close_box(self, number) -> Box:
        """Seal a box: capacity freezes at the final high-water mark.

        The retroactive half of D20. Capacity is not asked for at creation because nobody
        knows it then; it is the fill at the moment the lid goes on. Sold cards leave
        permanent gaps (D10) and the high-water mark holds, so this number never falls as
        the box's contents sell.
        """
        entry = self.ensure_box(number)
        if entry.closed:
            raise BoxClosed(f"box {entry.box} is already sealed")
        entry.capacity = self.box_fill(entry.box)
        entry.state = BOX_CLOSED
        entry.closed_at = now()
        self._log("box_closed", None, box=entry.box, capacity=entry.capacity)
        return entry

    def reopen_box(self, number) -> Box:
        """Unseal a box. Capacity goes back to unknown rather than staying as a stale fact."""
        entry = self.ensure_box(number)
        entry.capacity = None
        entry.state = BOX_OPEN
        entry.closed_at = None
        self._log("box_reopened", None, box=entry.box)
        return entry

    def box_fill(self, number) -> int:
        """The highest index this box holds. `next_index` minus one, and DISPLAY ONLY."""
        return max(0, self.next_index(number) - 1)

    def sections_for(self, number) -> Tuple[int, ...]:
        """A box's declared layout, or an empty tuple meaning the default rule renders it."""
        entry = self.box(number)
        return entry.layout() if entry is not None else ()

    def listing_for(self, sku: str) -> Optional[Listing]:
        """This SKU's listing record, or None. Creates nothing.

        `listing()` below is get-or-create, which is right for a writer and wrong for a
        reader: a run that merely *matched* a thousand SKUs would otherwise leave a
        thousand empty records behind, and `staged_stale` and `listing_counts` would then
        walk them on every call. Readers use this one.
        """
        return self.listings.get(sku)

    def listing(self, sku: str, *, condition: Optional[str] = None) -> Listing:
        """This SKU's listing record, created empty if it has none."""
        entry = self.listings.get(sku)
        if entry is None:
            entry = Listing(sku=sku, condition=condition, at=now())
            self.listings[sku] = entry
        elif condition is not None and entry.condition is None:
            entry.condition = condition
        return entry

    # ------------------------------------------------------------------------- reading

    def get(self, key: str) -> Optional[Card]:
        return self.cards.get(key)

    def positions_for_sku(self, sku: str) -> List[Card]:
        """Every copy holding this SKU, in box-walk order (D7's SKU -> positions map)."""
        return sorted(
            (c for c in self.cards.values() if c.sku == sku),
            key=lambda c: (c.box, c.index),
        )

    def in_state(self, state: str) -> List[Card]:
        check_state(state)
        return sorted(
            (c for c in self.cards.values() if c.state == state),
            key=lambda c: (c.box, c.index),
        )

    def counts(self) -> Dict[str, int]:
        counts = {state: 0 for state in STATES}
        for card in self.cards.values():
            counts[card.state] = counts.get(card.state, 0) + 1
        return counts

    def copies_on_hand(self, sku: str) -> List[Card]:
        """Every copy of this SKU still physically here, in box-walk order.

        The sellable set (D7 amended). Not filtered by listing stage — a copy is sellable
        because it exists, and which copies back the `live` count is deliberately unrecorded.

        `TERMINAL_STATES` rather than `SOLD` alone since D26: a retired copy has left
        inventory exactly as a sold one has, just by the other door, and counting it here
        would put a card that is no longer in the box back into D7's refill arithmetic.
        """
        return [c for c in self.positions_for_sku(sku) if c.state not in TERMINAL_STATES]

    def listing_counts(self) -> Dict[str, int]:
        """Copies at each TCGplayer stage, summed across every SKU."""
        totals = {stage: 0 for stage in LISTING_STAGES}
        for entry in self.listings.values():
            for stage in LISTING_STAGES:
                totals[stage] += max(0, int(getattr(entry, stage)))
        return totals

    def staged_stale(self, days: int = STAGED_STALE_DAYS) -> List[Listing]:
        """Staged this long ago and still not live — the import nobody finished.

        Reads listings rather than positions since D7's amendment: staged is a quantity of a
        SKU, so the thing that has gone stale is the SKU's import, not any one card.
        """
        out = []
        for entry in sorted(self.listings.values(), key=lambda e: e.sku):
            if entry.staged <= 0 or not entry.staged_at:
                continue
            age = _days_since(entry.staged_at)
            if age is not None and age >= days:
                out.append(entry)
        return out
