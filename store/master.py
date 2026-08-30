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

Positions are never renumbered and sold cards leave permanent gaps IN THE INDEX (D10).
That is a rule about this module's allocator and not about what a screen draws: since D58 a
card's NUMBER counts the cards in the box, so a departure closes up behind it everywhere it
is rendered while every index here stays exactly where it was assigned. Nothing in this
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
from typing import Dict, List, Optional, Tuple, Union

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
    or an iCloud eviction, which is what this repo was exposed to until it left iCloud
    Drive on 2026-08-29. A clone and a copy still lose it, so the reasoning is unchanged.

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
    # D3 RUNG 1'S FINISH CLAIM, AND IT IS A SET (amended 2026-08-23). One member determines,
    # exactly as this rung always has; two or more FILTER the candidate rows and let rungs 2
    # and 3 choose within what survives; an empty set is no claim at all, identical to the
    # `None` this field has always allowed. `pipeline/variant.py:_check_claim` is where all
    # three of those are decided — nothing in this package reads this value.
    #
    # BOTH SHAPES ARE LEGAL HERE PERMANENTLY, WHICH IS WHY THE ANNOTATION IS A UNION rather
    # than a list that a migration would arrive at eventually. A bare string reads as a
    # ONE-MEMBER SET and nothing writes one any more — D21's read-side backfill, for D21's
    # reason: every record written before the amendment carries a string, and rewriting them
    # to say what every reader can work out for itself is a write across the whole store that
    # changes nothing. There is no migration and there is not going to be one, so this field
    # holds two shapes for as long as those records do.
    #
    # A LIST, NEVER A TUPLE, and that is the trap rather than an inconsistency with the two
    # frozen carriers downstream. `to_payload` calls `asdict`, which PRESERVES a tuple;
    # `json.dumps` writes it as an array and `json.loads` hands back a list — so a tuple
    # assigned here goes in as a tuple and comes out as a list, and `to_payload` and `parse`
    # stop being each other's inverse. `Card` is not frozen, so a list is safe here.
    # `identify/sidecar.py:Capture` and `pipeline/join.py:IdentifiedCard` want the opposite
    # for the opposite reason: both ARE frozen, and a frozen carrier of a mutable member is a
    # hashability bug waiting for its first `set()`. `rarity_claim` below splits exactly the
    # same way and says so.
    metadata_finish: Optional[Union[str, List[str]]] = None
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


class SectionEmpty(ValueError):
    """`open_section` was asked to start a section where one already starts.

    The capture screen's `S` puts a divider in front of the next card, so pressing it twice
    with no capture between would put two dividers in one slot — which `check_sections`
    already refuses, in a sentence about a hand-typed layout that names neither the box nor
    the double press. This is that refusal moved to where it can be explained: the section
    you just opened is still empty, so the divider you want is already there.

    An EMPTY BOX takes this too, and it is the same fact rather than a special case: card 1
    is where the first section starts, so a divider in front of it is the one the box
    already has.
    """


class SectionAhead(ValueError):
    """`open_section` was asked to start a section behind one that is already declared.

    A layout may legitimately run past the fill — the dividers editor takes `[1, 51]` on a
    five-card box, and `_section_spans` renders that last section with a count of zero. A
    divider opened at the rig goes in front of the NEXT card, which in that state is behind
    a divider that already exists, and appending it would make the layout unsorted.
    `check_sections` would refuse it as exactly that, which is true and unhelpful; this
    names the declared divider that is in the way.
    """


class UnknownBox(ValueError):
    """A box number no registry entry covers."""


class BoxNameTaken(ValueError):
    """Two boxes cannot answer to one name once the name is how a box is addressed.

    D20 authored `name` as an optional label and nothing checked it, which was right while
    it was decoration: the number was the identifier and a duplicate name cost nothing but
    a confusing row on the Boxes screen. The capture screen now finds a box BY name, so a
    second "commons" is an ambiguous physical address — it moves the ambiguity off the key
    the operator stopped caring about and onto the label they navigate by, which is worse
    than where it started.

    FOLDED AND STRIPPED FOR COMPARISON, STORED VERBATIM. `Commons` and `commons ` are the
    same box to a person standing at a shelf, and a store that accepted both would be
    enforcing a rule nobody can see. What is written down is what was typed — the same
    split `pipeline/join.py:number_index_key` draws between a matching form and a stored
    one, for the same reason: a normalised value written back is a value the operator
    cannot correct.
    """


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
        # and what a new box starts with, and `pipeline/join.py:Position` renders it as ONE
        # section starting at card 1 — the box itself. There is no default divider size any
        # more (D10, amended 2026-08-29): a box was being cut into sections of 25 that
        # nobody had put a divider into, and the label sent a hand to count for a boundary
        # the plastic does not have. Nothing here changed with it, which is the point — this
        # module never knew the size and still does not.
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

        Empty means undeclared, which `Position` renders as the single section every box
        has before anybody divides it. Dividers are put in one at a time from the capture
        screen (`open_section`) or typed as a whole layout in the dividers editor.
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

    def release(self, budget: int) -> Dict[str, int]:
        """Give up at most `budget` copies TCGplayer is believed to hold. Returns what went.

        THE OPERATION THAT WAS MISSING, and the shape of the gap is worth stating because it
        took a box that could never be deleted to find it. `staged` is written by `reconcile`
        and drawn down in exactly one place — `cli/cmd_join.py`, by the RISE in live quantity
        a fresh Filtered Export reports. That is correct for an import that LANDS: the copies
        move to live and the staged count follows them down. It has no answer at all for one
        that does not. A staged row deleted on TCGplayer, or left sitting and then cleared by
        hand, never becomes live, so live never rises, so the drawdown never runs and the
        count stands forever. `staged_stale` names those SKUs — its own docstring calls them
        "the import nobody finished" — and until this method nothing could act on the warning.

        What that cost, measured on 2026-08-24: box 1's 53 Gate B cards were held by 45
        listing records carrying 53 staged copies, every one a claim about rows the owner had
        long since cleared off TCGplayer. `_listing_hold` reads those counts, so all 53 cards
        blocked `box_not_empty_of_commitments` and the box was PERMANENTLY undeletable.

        IT TAKES A BUDGET RATHER THAN ZEROING, AND THAT IS THE OWNER'S RULING OF 2026-08-24.
        The first build zeroed the record outright, on the argument that "TCGplayer holds
        nothing for this SKU" is a claim about TCGplayer and therefore cannot be scoped to one
        box. The owner overruled it, and the reason is better than the argument it replaced:
        **a release reached from box 1 must never be able to give up commitments that only
        box 3's copies could account for.** A budget of the calling box's copies makes that
        structurally impossible rather than merely unlikely — the caller cannot release more
        than the cards it is actually removing could ever have backed.

        The cost is real and is not hidden: where a SKU is shared, the remainder stays and the
        box stays held. That is the honest state — TCGplayer really is still holding copies of
        a SKU this box has copies of, and D7 makes every copy equally a candidate for being
        one of them — and `do_box_listings` puts it on screen before the press rather than
        leaving it to be discovered after.

        LEAST-COMMITTED FIRST: `pushed`, then `staged`, then `live`. The budget is a total
        across the three, never `budget` from each — two cards cannot account for two staged
        AND two live copies, and decrementing per stage would give up four commitments for two
        departing cards. Which stage a given copy actually backs is unknowable by construction
        (D7: copies are fungible and the backing is deliberately unrecorded), so the order is
        a rule rather than a lookup, and it is the conservative one: `pushed` is a row written
        into a file that may never have been imported, `staged` is a row TCGplayer confirmed,
        and `live` is a card actually for sale. Being wrong about `live` is the most expensive
        of the three, so it is surrendered last.

        `staged_at` IS CLEARED ONLY WHEN `staged` REACHES ZERO. `Listing.set` stamps it as
        `staged_at or at`, so a record released to zero and later re-staged would otherwise
        carry the old date forward and read as stale on the day it was staged — a warning
        firing on success. A record with staged copies REMAINING keeps its stamp, because
        those copies really have been staged since that date and are exactly what the warning
        exists to find.

        The record is left in place rather than deleted, because `_listing_hold` already reads
        all-zeros as not held and says so in as many words: "zeros mean TCGplayer is not
        holding anything". Popping it would be a second way of expressing the same fact, and
        the surviving `condition` is worth keeping.
        """
        remaining = max(0, int(budget))
        gave: Dict[str, int] = {}
        for stage in LISTING_STAGES:
            if remaining <= 0:
                break
            try:
                count = max(0, int(getattr(self, stage)))
            except (TypeError, ValueError):
                # `_listing_hold`'s rule: a count that will not coerce is "something is
                # there". It cannot be budgeted against because it cannot be read, so it is
                # zeroed and costs nothing — the honest reading of an unreadable quantity, and
                # the same direction the guard path takes everywhere else.
                setattr(self, stage, 0)
                continue
            take = min(count, remaining)
            if not take:
                continue
            setattr(self, stage, count - take)
            gave[stage] = take
            remaining -= take
        if int(self.staged or 0) <= 0:
            self.staged_at = None
        if gave:
            self.at = now()
        return gave


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
        # AN EMPTY CLAIM CARRIES NO FURTHER THAN A MISSING ONE, and this line read
        # `if value is not None` until D3's amendment of 2026-08-23 made that unsafe.
        #
        # `None` has always meant "this record makes no such claim, leave the incumbent
        # alone". A SET-VALUED claim has a second spelling of the same thing — D3: "an empty
        # set is no claim at all, identical to the null this field has always allowed" — and
        # `[]` is not `None`, so under the old test an incoming empty claim would OVERWRITE a
        # real one. Unrecoverably: a later re-record carrying `None` does not carry, so
        # nothing puts the claim back. It could not happen while the finish was a string,
        # because `capture_server._variant_shape` mapped `""` to `None` before the store ever
        # saw it; it can happen now, and `rarity_claim` has carried the identical hole since
        # the day it shipped — saved only by the server normalising `cleaned or None` on the
        # way in, which is the store depending on a normalisation it does not enforce itself.
        #
        # Truthiness rather than a per-shape test, and it is exact rather than loose here:
        # every member of `CAPTURE_CLAIM_FIELDS` is a string, a list of strings, or None, so
        # there is no falsy value among them that is a claim. It is also the same rule
        # `server/capture_server.py:sidecar_payload` already applies on the way to the file
        # ("a hint or a toggle the operator did not set is omitted rather than written
        # null"), so the record and the sidecar now agree about what an empty claim means.
        for attribute in CAPTURE_CLAIM_FIELDS:
            value = getattr(card, attribute)
            if value:
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
            if name is not None:
                self._check_name_free(name, number)
            entry = Box(box=number, name=name, created_at=now())
            self.boxes[str(number)] = entry
            self._log("box_created", None, box=number, name=name)
        elif name is not None and entry.name != name:
            # Through `set_name` rather than by assignment, so a rename reached this way
            # gets the same uniqueness check and the same `box_renamed` line as one reached
            # through the route. Assignment here is what made the name a field two callers
            # could set by different rules.
            self.set_name(number, name)
        return entry

    def _check_name_free(self, name: str, number: int) -> None:
        """Refuse a name another box already answers to. Folded and stripped to compare.

        Skips the box being written, so re-sending a box its own name is a no-op rather
        than a conflict with itself — which is the shape a screen that PUTs its whole form
        back produces, and refusing it would make an unrelated edit fail.
        """
        wanted = name.strip().casefold()
        if wanted == "":
            return
        for entry in self.boxes.values():
            if entry.box == number or entry.name is None:
                continue
            if entry.name.strip().casefold() == wanted:
                raise BoxNameTaken(f"box {entry.box} is already called {entry.name!r}")

    def set_name(self, number, name: Optional[str]) -> Box:
        """Name a box, rename it, or clear the name. Logs both names; refuses a duplicate.

        THE EVENT IS WHY THIS IS A METHOD AND NOT AN ASSIGNMENT. `server/capture_server.py`
        recorded the absence as a known gap and gave the right reason for leaving it: "a
        name is a label, not a claim the pipeline spends money against". That sentence was
        true while the number was the only address. It is not true now — the capture screen
        finds a box by name, so a rename relabels every card in it, and an unlogged rename
        leaves no record of what the box used to be called.

        THIS IS D10's DIVIDER ARGUMENT AT BOX SCALE, and it resolves the same way. Moving a
        divider relabels every card behind it, and D10 chose a `resectioned` event carrying
        both layouts over restricting the operation. `box_renamed` carries both names for
        exactly that reason: the trail is the safety, not a confirmation dialog
        `docs/DESIGN.md` would ban anyway.
        """
        entry = self.ensure_box(number)
        wanted = None if name is None or name.strip() == "" else name
        if wanted is not None:
            self._check_name_free(wanted, entry.box)
        before = entry.name
        if before == wanted:
            # A no-op writes no event, `do_put_card`'s rule: a log line for a request that
            # changed nothing is a rename that never happened, and the history is read as
            # the record of what did.
            return entry
        entry.name = wanted
        self._log("box_renamed", None, box=entry.box, name_from=before, name_to=wanted)
        return entry

    def next_box_number(self) -> int:
        """The lowest positive integer no box and no card claims. A HIGH-WATER MARK IT IS NOT.

        D10's allocator inside a box hands an index straight back when the newest record is
        deleted, deliberately: the position was assigned to a photograph that no longer
        exists and burning it would put a permanent hole in a box over a mis-tapped button.
        A box number is the other case. It names a physical object on a shelf, the operator
        no longer types it (the name is the address), and the only thing that reads it is
        the store, the disk and the wire — so the lowest free number is the honest answer
        and there is no gap for it to close wrongly.

        Cards are consulted as well as the registry, because a box that holds cards and has
        no registry entry is a real box — `_box_row` renders exactly that case, and handing
        its number out again would put two boxes' photographs in one directory.
        """
        taken = set()
        for key in self.boxes:
            try:
                taken.add(int(key))
            except (TypeError, ValueError):
                continue
        for card in self.cards.values():
            try:
                taken.add(int(card.box))
            except (TypeError, ValueError):
                continue
        number = 1
        while number in taken:
            number += 1
        return number

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

    def open_section(self, number) -> Tuple[int, ...]:
        """Put a divider in front of the next card. The capture screen's `S`.

        THE ACT AND THE RECORD ARE THE SAME GESTURE, which is the whole of D10's amendment
        of 2026-08-29. A layout was a list of indices typed into a field on another screen,
        after the fact, from memory — so the operator had to remember which card they were
        on when the divider went in, and the honest answer was usually "about eighty". This
        is pressed at the moment the plastic divider goes into the box, and the index it
        records is the one the next card will take.

        THE INDEX IS `next_index`, NOT A COUNT, and that is D10's high-water mark doing the
        same job it does for a capture: the next card lands on the end of the stack, so the
        divider in front of it belongs at the same number. A section opened over a box with
        gaps in it therefore starts where the hand will actually put the next card.

        AN UNDECLARED BOX MATERIALISES ITS FIRST DIVIDER HERE. `[]` becomes `[1, at]` rather
        than `[at]`, because `check_sections` requires the first section to start at index 1
        and it is right to: there is no card before the front of the box. Nothing is
        invented by that — section 1 already started at card 1, and this is the first time
        anything needed to write it down.

        LOGS `resectioned` THROUGH `set_sections`, deliberately reusing that event rather
        than minting `section_opened`. Both facts a reader wants — the layout before and the
        layout after — are already on it, and a new event name is a real cost in this store:
        `_state_before_sale` scans history filtering against `STATES`, and D26 records the
        day a state and an event sharing a word made months-old undo lines parse as states.

        Refuses on a sealed box (`BoxClosed`, the same refusal `allocate_capture` makes, for
        the same reason — a sealed box takes no more cards, so a section that can only hold
        future ones is a divider in front of nothing), on a section that is still empty
        (`SectionEmpty`), and behind a divider already declared past the fill
        (`SectionAhead`).
        """
        entry = self.ensure_box(number)
        if entry.closed:
            raise BoxClosed(
                f"box {entry.box} is sealed, so it takes no more cards — and a section with "
                f"no cards to come is a divider in front of nothing. Re-open the box first."
            )
        at = self.next_index(entry.box)
        layout = list(entry.layout()) or [1]
        last = layout[-1]
        if last == at:
            raise SectionEmpty(
                f"section {len(layout)} of box {entry.box} already starts at card {at} and "
                f"holds nothing yet. Capture a card into it before starting another."
            )
        if last > at:
            raise SectionAhead(
                f"box {entry.box} already declares a section starting at card {last}, which "
                f"is past the next card ({at}). Edit the dividers instead."
            )
        return self.set_sections(entry.box, layout + [at])

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
        """A box's declared layout, or an empty tuple meaning it has declared none."""
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
