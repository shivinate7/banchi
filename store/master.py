"""The inventory — cards, positions, SKUs, listing states. The `cards`, `boxes` and
`listings` tables of `inventory/store.sqlite` since D88; `inventory.json` before it.

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

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

# THE ONE INTRA-PACKAGE IMPORT THIS MODULE MAKES, and it is a container rather than a disk.
# The comment beside `BadPosition` below explains why nothing here reaches `store/files.py`;
# `store/rows.py` imports nothing and touches nothing, and it is what lets `Inventory.cards`
# stay a dict to every caller while a session bound to the database loads one box at a time
# (D88). The table specs at the bottom of `Inventory` are the other half of that contract.
from store.rows import Rows, TableSpec, int_or_none

# `store/numbers.py`, NOT `pipeline/join.py` — CORRECTED: `store/` MAY NOT IMPORT
# `pipeline/` (D63: "store/ imports nothing from pipeline/, so there is no cycle"; the
# arrow runs the other way — `pipeline/orders.py`, `readings.py` and `selection.py` all
# import `store`). A module-level `from pipeline import join` here would be exactly the
# cycle that rule forbids. `store/numbers.py` is the leaf `join_key`/`display_number` moved
# to, with no imports beyond the stdlib, and `pipeline/join.py` imports them back and
# re-exports under the same names — so `_card_columns` reuses one fold (D55/D67) the same
# as every other reader, without `store/` crossing the one edge it may not cross.
from store.numbers import display_number, join_key

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

# A card's third door out of a box (D83): it did not sell and it did not leave inventory —
# it is still on hand, just at a different address. `retired` was built for a departure and
# every reader of `TERMINAL_STATES` treats that tuple as "gone from this box, permanently, for
# a reason worth recording" — which is exactly what a move is, and exactly why it is not
# spelled as a fifth `RETIRE_REASONS` member. A reason there says the card left INVENTORY;
# `MOVED` says the opposite; overloading the vocabulary would make every `copies_on_hand`/
# `copies_not_sold` caller reason about a "retirement" that leaves the card fully sellable at
# a new key.
#
# Named `moved` and not `relocated` for the same reason `retired` is not `removed` (see the
# comment on that name above): T7 asserts no event name collides with a state name, and this
# module's own `_log` writes the state name as the event name at every other transition —
# reusing that convention here rather than minting a second word for one fact.
MOVED = "moved"

# THE HISTORY EVENT A RECLAIMED PHOTOGRAPH WRITES (D89). An event and not a state: the card
# stays `sold`, and what changed is that the bytes behind `photo` are gone. Not a member of
# `STATES` for D26's reason — `_state_before_sale` filters history against that tuple, and
# an event sharing a state's word would make a reversal restorable to it.
PHOTO_RECLAIMED = "photo_reclaimed"

# A POSITION'S STATE DESCRIBES ONE PHYSICAL CARD AND NOTHING ELSE (D7, amended).
#
# `pushed`, `staged` and `live` used to live in this tuple, and a card wore one of them the
# way it wore `captured`. That made listing progress an address: `cli/cmd_join.py` picked
# WHICH positions became live, so four of seven copies were sellable and three were not, for
# no physical reason at all. The owner's ruling is that copies of one SKU are fungible — "if
# i have 15 of one copy and mark 3 as live, it's any 3 are live, not 3 specific locations are
# live". So the three moved off the card and onto the SKU, below, as counts.
STATES = (CAPTURED, IDENTIFIED, SOLD, RETIRED, MOVED)

# The three ways a POSITION becomes permanently vacant: a sale, D26's retirement, or D83's
# move to another box. All three keep the record and leave a permanent gap at this key;
# `copies_on_hand` filters on this tuple rather than on `SOLD` alone, which is what keeps a
# retired OR moved copy out of D7's refill arithmetic here — an emit that still counted a
# tombstone would double-list a card that is now sellable under a different key.
#
# `MOVED` belongs here even though the card itself has NOT left inventory, unlike its two
# siblings — this tuple is about the POSITION, not the card. D83's move primitive clears
# `sku`/`condition` off the tombstone specifically so `copies_not_sold`/`positions_for_sku`
# (which filter on `sku`, not on this tuple) never see the tombstone at all; membership here
# is what lets D58's occupancy rendering (`pipeline/join.py:Position`/`BoxView`) close the
# gap over a moved card for free, the same way it already closes over a sold or retired one.
TERMINAL_STATES = (SOLD, RETIRED, MOVED)

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

# What `Listing.observe_live` says it did with a reading of `live`. `UNCHANGED` is a reading
# equal to the stored one, whatever its age — nothing to arbitrate and nothing touched, which
# is what keeps `reconcile --live` idempotent. `KEPT` is a reading OLDER than the store's own
# observation, refused; `ADOPTED` is a newer one, written with the time it was taken.
ADOPTED = "adopted"
KEPT = "kept"
UNCHANGED = "unchanged"
# A READING THAT MOVED NO COPIES AND STILL WROTE (D115). The figure agreed, but the file was
# taken after sales this store had counted against the older reading — so the counter is
# emptied and `live_as_of` advances. DISTINCT FROM `ADOPTED` because three callers read these
# words and every one would say something false with it: `cli/cmd_reconcile.py` would report
# "settled N listing(s)" beside "0 copies corrected", `cli/cmd_join.py` would run a staged
# drawdown of `quantity - before == 0`, and `_settlement`'s preview has no word for a write it
# must promise.
CLEARED = "cleared"

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


class CardNotFound(ValueError):
    """`move_card` was asked to move a position holding no record."""


class CardNotSold(ValueError):
    """`record_photo_reclaimed` was asked about a card that has not sold (D89)."""


class CardDeparted(ValueError):
    """`move_card` was asked to move a card already sold, retired, or moved.

    A card that left through one door cannot leave again through another — the same
    argument `do_remove_card`'s target-state refusal already makes for delete, applied to
    the third door (D83). A card already `MOVED` names where it went, so this refusal is
    not a dead end: the operator moves the TRANSPLANT at that key instead.
    """


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


def _parse_stamp(stamp: Optional[str]) -> Optional[datetime]:
    """An ISO stamp as an aware datetime; naive is read as UTC. None on empty or garbage."""
    if not stamp:
        return None
    try:
        when = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when


def _days_since(stamp: Optional[str]) -> Optional[int]:
    when = _parse_stamp(stamp)
    if when is None:
        return None
    return (datetime.now(timezone.utc) - when).days


def newer_stamp(a: Optional[str], b: Optional[str]) -> Optional[bool]:
    """True iff stamp `a` is strictly later than stamp `b`; None if either will not parse.

    PARSED, NOT COMPARED AS STRINGS. `now()` writes milliseconds and `cli/runs.py:
    describe_source` writes seconds, so `...:24+00:00` and `...:24.500+00:00` differ in a
    character class before the offset and string order is only accidentally time order —
    the caveat `server/pipeline_routes.py:_box_name_for` carries for the same comparison.
    Naive stamps are read as UTC, which is what every writer in this store means.

    Three answers rather than a bool, because "cannot tell" is a real outcome a caller has
    to decide on: `Listing.live_reading` treats it as the stampless case, where the export
    keeps the authority it has always had.
    """
    left, right = _parse_stamp(a), _parse_stamp(b)
    if left is None or right is None:
        return None
    return left > right


def box_disowns_run(
    created_at: Optional[str],
    runs_present: Iterable[str],
    run: str,
    ran_at: Optional[str],
) -> bool:
    """True iff the box under this number is a different drawer from the one `run` was over.

    THE RULE `server/pipeline_routes.py:_box_name_for` HAS HELD SINCE D56, LIFTED HERE BECAUSE
    A SECOND CALLER REFUSES ON IT. `next_box_number` allocates the lowest FREE integer (D20
    amended), so a box that is deleted and a box that arrives later share a number, and a run
    over the first keeps describing it: `2026-08-22-box1-03` is over 53 Pokemon cards that
    `do_delete_box` removed on 2026-08-25, and box 1 has held 133 Riftbound cards since
    2026-08-29. The route withholds the newcomer's name from that run; `cli/resolve.py:
    refuse_reallocated` refuses to join it at all (D36 amended). Both decide by this function,
    so the screen and the command cannot disagree about which drawer a run was over.

    TWO CONDITIONS, BOTH REQUIRED, AND EACH RULES OUT THE OTHER'S FALSE POSITIVE:

      the registry entry was made AFTER the run started
      and the box's cards DISOWN the run — it holds some, and none of them is this run's

    The stamp alone would refuse a box named after its run, which is ordinary. The card set
    alone would refuse a fresh run over a box already holding another run's cards, since
    `run` is written onto a card by `identify` and a live run owns none until then. An empty
    box disowns nobody. Either stamp absent or unparseable is "cannot tell", and this
    abstains towards the box being the run's own — the claim it can least afford to make
    about runs it knows nothing about.
    """
    present = set(runs_present)
    if not present or run in present:
        return False
    return newer_stamp(created_at, ran_at) is True


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
    # C10's product claim: WHICH SEALED PRODUCT this code card came out of — a key from
    # `codes/products.py`. Only `pokemon_code` uses it, and it is the field that retires
    # C2's OCR half: code cards arrive in sealed-product batches, so the operator declares
    # the product once per stack and the camera never has to read a SKU line. `None` is no
    # claim, exactly like `rarity_claim` and for the same reason — there is no ladder that
    # infers a product, so an absent one stays absent rather than defaulting to `booster`,
    # which would silently file a $1.39 Pokemon Center ETB code as a $0.03 booster.
    #
    # ON `Card` RATHER THAN ONLY IN THE LEDGER, because a claim is a property of the capture
    # and `codes/ledger.py` is written by a LATER step that may never run. A photographed
    # card whose scan has not happened yet still knows what it is.
    product: Optional[str] = None
    # Free text, and the only claim on this record a human writes in prose. It exists for
    # the ~1% of stock that is neither identified nor joined — the occasional Yu-Gi-Oh,
    # Weiss Schwarz, foreign-language or Magic card — where the operator says what it is so
    # that `do_search` can find it later. Never parsed, never matched against a catalog.
    note: Optional[str] = None
    name: Optional[str] = None
    number: Optional[str] = None
    printed_total: Optional[str] = None
    confidence: Optional[str] = None
    # THE MODEL'S DETECTED FINISH, THE READING'S MISSING FIFTH FIELD
    # (D167).
    # `record_identification` writes `name`, `number`, `printed_total`
    # and `confidence` — one identification, four fields — and the model answers a fifth,
    # `finish`, which went only into the run's `identifications.json`. That asymmetry has no
    # argument behind it and it cost one: a reader rebuilding a card's reading off the store
    # had to take this one field from somewhere else, and the only other place it is written
    # down is a queue entry, which may have been written by an OLDER identification of the
    # same photograph. Measured on the owner's store: six of box 4's cards read `finish:
    # null` on 2026-09-12 while their queue entries still said `foil` from 2026-09-11, and a
    # refresh mixing the two queued six cards a join listed.
    #
    # NOT A CAPTURE CLAIM, so deliberately absent from `CAPTURE_CLAIM_FIELDS`:
    # `metadata_finish` beside it is what the OPERATOR said about the stack and survives a
    # re-record; this is what the MODEL saw in one photograph and is replaced whole by the
    # next identification, exactly as `name` and `confidence` are. The two are told apart
    # everywhere else in this pipeline (`pipeline/variant.py` rung 3 cross-checks one against
    # the other) and telling them apart here is the same distinction.
    #
    # None ON EVERY CARD IDENTIFIED BEFORE THIS FIELD EXISTED, and that is the honest
    # reading rather than a gap to backfill: the store does not know, and a value copied
    # from a queue entry would be another reading's answer wearing this one's name.
    detected_finish: Optional[str] = None
    sku: Optional[str] = None
    condition: Optional[str] = None
    # THE SET, AS THE CATALOGUE NAMES IT (D213).
    # `set_hint` above is the operator's own claim, typed at the shutter and evidence about
    # its own card; this is a fact about the PRODUCT, read off the export row `sku` resolved
    # to at the moment the SKU was committed. Two of five `Calm Rune` copies would tie on
    # every field this record carried before this one — name, number, `set_hint` (null on
    # all five) — and this is the one that tells them apart.
    #
    # NAMED `set_name`, NOT `set`. SQLite's `UPDATE ... SET` grammar cannot parse an unquoted
    # column literally spelled `set` — `sqlite3.OperationalError: near "set": syntax error`,
    # reproduced before this was written — so every DDL, DML and search statement that ever
    # touches it would need to carry a quoting exception this codebase draws nowhere else.
    # `set_name` is `pipeline/join.py:SkuMatch.set_name`'s own name for exactly this fact,
    # reused rather than invented.
    #
    # NULL ON EVERY CARD IDENTIFIED BEFORE THIS FIELD EXISTED, backfilled once by
    # `./pkmnscan cards variants --write` and never guessed: a SKU whose export row cannot be
    # found (no export ever fetched, or the SKU has aged out of one that was) keeps a null
    # set rather than a fallback value invented for the column.
    set_name: Optional[str] = None
    # THE CATALOGUE'S OWN RARITY, kept beside `rarity_claim` above and never merged into it.
    # `rarity_claim` is the operator's claim at the shutter (D23, D146) and can disagree with
    # what TCGplayer calls the product — a disagreement is itself information and both are
    # kept on the record for that reason. Same source and same write moment as `set_name`.
    rarity: Optional[str] = None
    state: str = CAPTURED
    state_at: Optional[str] = None
    # Why a retired card left — one of `RETIRE_REASONS`, set by `retire()` and cleared by
    # the route that reverses one; None on every card in any other state. NOT a capture
    # claim, and deliberately absent from `CAPTURE_CLAIM_FIELDS` below: a claim survives a
    # re-record and is settable at capture time, while this describes a departure — a
    # capture that could write it would retire a card by photographing it, and a re-record
    # by `identify` or `emit` must neither resurrect nor clear it (D26).
    retire_reason: Optional[str] = None
    # The key this card was transplanted TO, set only when `state == MOVED` — `retire_reason`'s
    # sibling for the third door (D83). Cleared by nothing: unlike a retirement, a move has no
    # reversal route that restores the tombstone, because the transplant is a normal, live
    # record a caller can move again in either direction. NOT a capture claim, for the same
    # reason `retire_reason` is not: a re-record by `identify`/`emit` must neither invent this
    # nor clear it.
    moved_to: Optional[str] = None
    run: Optional[str] = None
    # THE PHOTOGRAPH'S DIGEST, KEPT AFTER THE PHOTOGRAPH IS GONE (D89). Set by
    # `record_photo_reclaimed` and by nothing else; None on every card whose photograph is
    # still on disk, because while the file exists the file is the fact and a copy of its
    # digest here would be a second thing to keep true through D26's re-shoot. Once the bytes
    # are reclaimed this is the only trace of what was photographed — it is what D36's
    # `photo_sha256` binding on a run record can still be compared against, and what a
    # dispute about which card sold can be answered with. NOT a capture claim, for
    # `retire_reason`'s reason: a re-record must neither invent it nor clear it.
    photo_sha256: Optional[str] = None
    # When the photograph was reclaimed, or None while it is on disk. The pair travels
    # together: `record_photo_reclaimed` sets both, and a screen that finds this set draws
    # "reclaimed" rather than "missing" — the two are different facts about the store.
    photo_reclaimed_at: Optional[str] = None
    # THE CARD'S NAME: the sha256 of the photograph the store held when the id was issued,
    # read off the disk, FROZEN from that moment and never recomputed (D172). It is a birth
    # certificate and not a live content address, which is the single word that makes it
    # survive a D26 re-shoot, a D89 reclaim, a D83 move, a mid-box renumber and a box
    # deletion. It arrives BESIDE `key` and replaces nothing: `position_key` stays, and
    # `Box 3 · Section 2 · Card 17` is an instruction to a hand at a drawer and never a cid.
    #
    # READ IT AS `bid` : box :: `cid` : card. IT IS NOT AN ABBREVIATION OF `capture_id`,
    # which sits a few fields up and is a PHOTOGRAPH's id — `do_reshoot` overwrites that one
    # and `move_card` clears it, which is exactly why it could not be the card's name.
    #
    # IT IS ALSO WHERE THE PHOTOGRAPH IS FILED (`store/photos.py`), and that is the half the
    # owner re-scoped D172 for: filing the bytes under `(box, index)` is what made a
    # renumber cost N−k renames, a move cost five hand-moved copies, and one
    # remove-then-capture able to overwrite a photograph that cannot be re-taken. The path
    # is a pure function of this field, and `cards_cid` holds it UNIQUE, so two cards cannot
    # compose one path — see `D183`.
    #
    # FOUR SHAPES, ALL NAMED, AND A NULL IS NEVER ONE OF THEM: `<64 hex>`, `<64 hex>-<n>`
    # for the nth card whose bytes match an earlier one's, `moved:<…>` on a D83 tombstone,
    # and `nophoto:<box>/<index>@<captured_at>` for a card with no photograph and no digest
    # anywhere. `photos.is_photo_cid` is the predicate that tells the first two from the
    # last two. A NULL cannot distinguish "no photograph was found" from "this migration did
    # not look", which is this repo's signature defect — so a NULL is a condition to be
    # HEALED and reported, and `store/db.py:_repair` is what heals it.
    #
    # NOT A CAPTURE CLAIM, and deliberately absent from `CAPTURE_CLAIM_FIELDS`: a claim
    # survives a re-record, and this must not be settable by one. It is issued once, at the
    # birth of the record, by `record_capture`.
    cid: Optional[str] = None

    @property
    def key(self) -> str:
        return position_key(self.box, self.index)

    @property
    def days_in_state(self) -> Optional[int]:
        return _days_since(self.state_at)


class UnknownClaim(ValueError):
    """A capture tried to write a field that is not a capture claim."""


# D172's shape-3 marker: the tombstone a moved card leaves behind wears `moved:<name>` so
# one name is never on two rows. Spelled here rather than imported from `store.photos`
# because this module imports nothing from the rest of the package — see the note above
# `BadPosition` — and `photos.MOVED_PREFIX` is the same string, reconciled by a T7 arm.
MOVED_CID_PREFIX = "moved:"


class UnnamedCard(ValueError):
    """A new card row was minted with no `cid` (D172).

    A PROGRAMMING ERROR IN A CALLER AND NEVER A DATA CONDITION, which is why it is raised at
    the birth of a record and not at the flush: `_card_columns` is the single chokepoint
    every row passes through, and a refusal there would be a 500 on the shutter mid-feeder.
    See `record_capture`.
    """


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
CAPTURE_CLAIM_FIELDS = (
    "photo", "set_hint", "metadata_finish", "game", "rarity_claim", "product", "note",
)

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
    # THE TRUE INDEX: an identity this box keeps for as long as the store remembers it, and
    # that no later box is ever given (D145). `box` above is a LABEL on a physical
    # drawer and `next_box_number` hands out the lowest free one on purpose (D20) — so the
    # moment a drawer is emptied and deleted, the next drawer is called `Box 1` too, and every
    # record that outlives a box loses the ability to say which of them it meant.
    #
    # THE OWNER'S REPORT, 2026-09-11: *"i deleted an old box 1, started writing into a new box
    # (now new box 1) and if i go on say my runs tab it shows that i'd run a 'Box 1' run a long
    # time ago"*. Their ruling in the same breath: *"box # and index # should not be the same
    # thing, a box needs an index # not visible anywhere in the app thats a true index rather
    # than cheaply using boxes as an index"*.
    #
    # THIS IS D58 ONE REGISTER UP, and the vocabulary is deliberately D58's: `Place.index` is
    # the stored key and `Place.slot` is the number a person counts to. Here `bid` is the key
    # and `box` is the number a person reads off the shelf. Both pairs exist because a label a
    # human maintains and a key a machine joins on are different jobs, and one value cannot do
    # both.
    #
    # NEVER REUSED, WHICH IS THE ONE PROPERTY IT HAS AND `box` DOES NOT. `Inventory.next_box_id`
    # allocates `max(issued, every live bid) + 1` against a high-water mark that is persisted
    # beside the tables and is NOT lowered by a deletion — D10's rule for the card index inside
    # a box, applied here for the first time. CLAUDE.md's sentence that `next_box_number` is
    # "deliberately NOT D10's high-water mark" is still exactly right about the NUMBER; this is
    # the field that is one.
    #
    # NEVER DRAWN. The owner said so twice, and nothing in `app/` renders it: it travels on the
    # wire so the server can tell two drawers apart, and every screen still says `Box 1`.
    #
    # OPTIONAL FOREVER, for `Card.rarity_claim`'s reason rather than for want of a migration.
    # The v2 migration fills every box in an existing store, but `Box(box=7)` is a shape a
    # dozen tests and `Inventory.parse`'s v1 backfill construct directly, and a required field
    # would make an id something every caller had to source. `ensure_box` is the one allocator.
    bid: Optional[int] = None
    name: Optional[str] = None
    sections: List[int] = field(default_factory=list)
    # A divider's optional label, keyed by the STRINGIFIED divider index it starts at — string
    # for the same JSON-round-trip reason `Inventory.cards`/`boxes` are string-keyed dicts
    # rather than int-keyed ones (D83). Pure decoration, unlike `name`: nothing addresses a
    # section BY this the way the capture screen addresses a box by `name` (D20 amended), so
    # it carries none of `BoxNameTaken`'s uniqueness machinery. A divider index absent here has
    # no name, same as a box absent from `Box.name` has none. `move_cards` carries a moved
    # section's name to the fresh divider it opens at the destination.
    section_names: Dict[str, str] = field(default_factory=dict)
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

    `live` IS THE STORE'S LAST OBSERVATION OF WHAT TCGPLAYER HOLDS, WITH THE TIME IT WAS
    TAKEN, and it was "an optimistic local estimate between runs" until 2026-09-02 (D59 and
    D87, amended). D8 and D11 put the authority in the TCGplayer export's `Total Quantity`,
    and an export still corrects this number — but only where the export was READ LATER
    than the store's own reading. Two readings of the same quantity taken at different
    moments are not a fact and an estimate; they are two observations, and the newer one
    wins. Measured on the owner's store: a run's recorded export, fetched fifteen minutes
    before that run was emitted, carried a blank `Total Quantity` for every SKU it had just
    listed, and a re-join with it — the ordinary "Join again" on `#/runs` — took the store
    from 1,072 live copies over 406 SKUs to 700 over 266, overwriting D87's settlement.
    `observe_live` is the one rule, and `live_as_of` is what it arbitrates on.
    """

    sku: str
    condition: Optional[str] = None
    pushed: int = 0
    staged: int = 0
    live: int = 0
    at: Optional[str] = None
    staged_at: Optional[str] = None
    # WHEN THE `live` READING WAS TAKEN — not when this record was touched. The export
    # file's mtime for `join` and `reconcile --live` (a fetch's mtime is its fetch time, an
    # upload's is the file's own), and `now()` for a sale's ±1 and a D34 release, which are
    # observations this process makes itself. `at` is stamped by every writer of every
    # field and reads as "last touched", which is why it is not overloaded to carry this:
    # a `set(STAGED, …)` would then forge a fresher live observation than anything made.
    # None means NO READING YET — a record `emit` created and nothing has read `live` for —
    # and the export then wins whatever its age, because a default is not an observation.
    # A stored record written before the field existed has no key at all, and `from_record`
    # reads its `at` as the observation time — which is what protects D87's settlement rows,
    # whose `at` IS the settlement time. The two are told apart at the parse and nowhere
    # else: absent is legacy, null is unread.
    live_as_of: Optional[str] = None
    # COPIES SOLD HERE SINCE THAT READING — A DELTA THIS PROCESS MADE, NEVER A READING.
    # `live` above is what TCGplayer's export said and `live_as_of` is when it said it; this
    # is what has left the building since, and `live_estimate` is the two together.
    #
    # THEY WERE ONE NUMBER UNTIL D115, AND THAT IS THE WHOLE DEFECT. `observe_live` wrote a
    # reading, `bump(LIVE, -1)` wrote a delta, and nothing arbitrated them but a timestamp
    # race — so `reconcile --live` writing a figure that ALREADY reflected a sale, followed
    # by marking that card sold, subtracted the same copy twice. Measured on the owner's
    # store: a SKU at `pushed 4, live 1` read zero while TCGplayer held one, and understating
    # `live` tells the cap there is room that is not there. A reading and a delta are not the
    # same kind of fact and "newer wins" cannot arbitrate them; kept apart, ORDER STOPS
    # MATTERING — mark sold whenever, reconcile whenever.
    #
    # NOT A STAGE, and the distinction is load-bearing. `pushed`/`staged`/`live` are members
    # of `LISTING_STAGES`; this deliberately is not. `set`, `bump`, `release`,
    # `listing_counts` and `server/capture_server.py:_stages_held` all walk that tuple, so a
    # fourth member would be surrendered by D34's release, summed into the store's stage
    # totals, and drawn as a listing stage on three screens. It is a correction TO a stage.
    #
    # NEVER FLOORED ON THE WAY UP, which is what makes an undo exact. `bump` floored the
    # STORED figure, so a decrement lost to the floor was lost for good while a later undo
    # still added one back — an estimate drifted UP by one, the edge
    # `server/capture_server.py` accepted rather than paid for. The floor moved to
    # `live_estimate`, where it loses nothing.
    sold_here: int = 0
    # WHEN THE NEWEST COUNTED SALE HAPPENED — the counter's own `live_as_of`, and it is
    # required rather than decorative. `sale()` may no longer restamp `live_as_of`, and that
    # restamp was the ONLY thing standing between a sale and a re-join: `cli/cmd_join.py`
    # re-reads the run's RECORDED export, whose mtime is its fetch time (measured at fifteen
    # minutes before its own emit), so an export fetched BEFORE a sale and read AFTER it is
    # the ordinary "Join again" press. Without this stamp that file is newer than
    # `live_as_of`, clears a counter it knows nothing about, and the sale is gone.
    #
    # THE NEWEST SALE AND NOT THE OLDEST, so no sale is forgotten by a file that predates it.
    # Each stamp on this record is chosen so its field cannot silently lose what it holds:
    # `first_seen_live` keeps the EARLIEST sighting, `live_as_of` the NEWEST reading, and this
    # the NEWEST sale. A file landing between two counted sales cannot be split by one stamp,
    # so it clears neither and the estimate errs low — the direction D7 asks for.
    #
    # None means nothing is pending. Left standing on an undo that does not reach zero: it is
    # still the newest sale that can be named, and holding it errs toward not forgetting.
    sold_here_at: Optional[str] = None
    # THE FIRST MOMENT THIS SKU WAS SEEN LIVE AT TCGPLAYER, and the only field here that is
    # MONOTONE — earliest wins, and nothing overwrites it. It exists because D100's staleness
    # ranked on how long the CARD had been OWNED, `Listing` having no first-listed stamp, and
    # every report had to name the substitution in its own header. Measured on the owner's
    # store 2026-09-06: 184 of 387 live SKUs were refused `too_young` against an oldest
    # capture of 2026-08-23 — the window was measuring when this project got a camera.
    # Two dated readings are enough to give it a true value, for a SKU no card here carries
    # as much as for one photographed in a box, which is why it lives beside `live` rather
    # than on `Card`. None means never seen live, or seen only before this field existed.
    first_seen_live: Optional[str] = None
    # WHEN THIS STORE LAST SET A PRICE FOR THIS SKU — not what the price was. The figure
    # round-trips through TCGplayer's own export (`asking`), so storing it here would be a
    # second money truth that can disagree with the first; the stamp is the part the export
    # cannot tell us. It is what stops `reprice`'s rule compounding a markdown week over
    # week, and it is the non-held SKU's counterpart to `pipeline/corpus.py:stamp_answers`,
    # which dates an answer only for a card this store holds.
    priced_at: Optional[str] = None

    @classmethod
    def from_record(cls, record: dict) -> "Listing":
        """A stored payload as a `Listing` — the ONE place a legacy row is read.

        A row written before `live_as_of` existed carries no such key, and its `at` is the
        last time anything wrote it — for D87's settlement rows the settlement itself, for
        the rows a join or a sale last touched that reading. Materialised here rather than
        computed in a property, because a property could not tell that row from a fresh one
        `Inventory.listing` made a moment ago with `at=now()` and no reading at all — and
        that one, given the same fallback, outranked every export older than its own
        creation, including the run's recorded export on the very path D87's amendment was
        built to close. A row that carries the key, null or not, is read as written.
        """
        known = _known(cls, record)
        if "live_as_of" not in record:
            known["live_as_of"] = record.get("at")
        return cls(**known)

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

        AND THE SAME SENTENCE WAS FALSE ABOUT `pushed` FROM THE DAY IT WAS WRITTEN (D59).
        `pushed` means one thing: a CSV was written. The moment the operator imports it and
        moves the rows live, `Total Quantity` reports those copies — so `pushed` becomes the
        second subtraction this docstring spends its length forbidding, reached through the
        one stage nobody thought to check. Measured on the owner's own store: 167 copies
        across 72 SKUs at `pushed`, with `staged` and `live` both zero.

        THIS PROPERTY HAD NO CALLER AT ALL until `cli/resolve.py:_copies_out`, which is
        where the correction lives: the claim is bounded by `Inventory.copies_not_sold`
        rather than trusted. A rule with no caller cannot be kept honest by anything, and
        `server/capture_server.py:_stages_held` one process over already implements a
        DIFFERENT rule under a near-identical name.
        """
        return max(0, int(self.pushed)) + max(0, int(self.staged))

    @property
    def live_observed_at(self) -> Optional[str]:
        """When the stored `live` was read. None is a record nothing has read `live` for
        — see the field, and `from_record` for why a legacy row's `at` is not read here."""
        return self.live_as_of

    def live_reading(self, quantity: Optional[int], as_of: Optional[str]) -> int:
        """The `live` figure to believe, given an export's reading taken at `as_of`.

        THE ONE RULE, read by `cli/resolve.py:_copies_out` for the cap and by `observe_live`
        for the store, so the two cannot disagree. `quantity` None is a SKU the export has
        no row for: the store's reading stands, which is how D87's settlement reaches the
        cap for every SKU a run's own export does not cover. A row with a blank cell is a
        reading of ZERO at the file's time — the defect case — and loses to a newer one.

        Ties go to the store. Both stamps are to the millisecond (`describe_source` and
        `now()`), and an export whose mtime equals the store's stamp cannot be shown to be
        newer; a reading that cannot be shown newer is not adopted.
        No parseable stamp on either side — a hand-built fixture, a record nothing has
        read `live` for yet — is the stampless case, and there the export keeps the
        authority D8 and D11 gave it before this field existed.
        """
        if quantity is None:
            return max(0, int(self.live))
        quantity = max(0, int(quantity))
        verdict = newer_stamp(as_of, self.live_observed_at)
        if verdict is None or verdict:
            return quantity
        return max(0, int(self.live))

    def reading_taken_at(
        self, quantity: Optional[int], as_of: Optional[str]
    ) -> Optional[str]:
        """WHEN the reading `live_reading` would return was taken.

        `live_reading`'s third sibling, and it exists for the same reason the other two do:
        the rule is written ONCE so two callers cannot answer differently about one file. It
        answers the figure; `sales_pending` answers which counted sales survive it; this
        answers its DATE, which `cli/resolve.py:_copies_out` needs to ask whether a sale
        happened before or after the observation it is weighing the claim against.

        EVERY BRANCH MIRRORS `live_reading` EXACTLY, including the stampless one: where the
        export keeps the authority D8 and D11 gave it, the stamp returned is the export's,
        `None` and all — and a `None` stamp is one nothing can be shown to predate, which is
        the conservative end of every comparison that reads it.
        """
        if quantity is None:
            return self.live_observed_at
        verdict = newer_stamp(as_of, self.live_observed_at)
        if verdict is None or verdict:
            return as_of
        return self.live_observed_at

    def observe_live(self, quantity: int, as_of: Optional[str]) -> str:
        """Offer the store a reading of `live` taken at `as_of`. Returns what happened.

        FOUR VERDICTS SINCE D115, and the fourth is the reason this method was restructured
        rather than extended. `UNCHANGED`: the reading equals the stored figure and clears no
        counted sale — nothing to arbitrate, nothing touched, and the second pass stays a
        no-op. `CLEARED`: the figure agreed but the file postdates sales counted against the
        older reading, so the counter is emptied and `live_as_of` advances. `KEPT`: the file
        is older than the store's observation and is refused untouched, counter included.
        `ADOPTED`: `live` takes the reading, `live_as_of` takes THE FILE'S time, `at` takes
        now, and the counter takes whatever `sales_pending` says survives.

        THE EARLY EQUALITY RETURN IS NARROWED, NOT MOVED, and that is the whole subtlety.
        "Equal figure, whatever the age" is what keeps a second `reconcile --live` over one
        file a no-op; moving it past arbitration would turn it into `KEPT`, because
        `newer_stamp` gives ties to the store — the same file read twice would report itself
        outranked. What it may no longer do is return before the COUNTER is arbitrated: an
        equal figure read after a sale is a real correction, and it is the one D115 exists to
        make. Nothing is written when nothing moved, so the second pass computes from
        identical state and answers identically.

        ASSIGNED DIRECTLY RATHER THAN THROUGH `set`, which stamps `live_as_of` with `now()`
        — a forgery here, where it would date an export's reading to the moment it was copied
        in rather than the moment it was taken, and outrank a later settlement it should have
        lost to. (`set` was also right for a sale until D115; a sale no longer takes a
        reading at all — see `sale`.)
        """
        quantity = max(0, int(quantity))
        stored = max(0, int(self.live))
        pending = self.sales_pending(as_of)
        if quantity == stored:
            if pending == max(0, int(self.sold_here)):
                return UNCHANGED
            # `sales_pending` is all-or-nothing, so reaching here means it returned 0 against
            # a counter that is not: the file postdates every counted sale and supersedes it.
            self.sold_here = pending
            self.sold_here_at = None
            self.live_as_of = as_of
            self.at = now()
            return CLEARED
        if self.live_reading(quantity, as_of) == stored:
            return KEPT
        self.live = quantity
        self.live_as_of = as_of
        self.sold_here = pending
        if not self.sold_here:
            self.sold_here_at = None
        self.at = now()
        return ADOPTED

    @property
    def live_estimate(self) -> int:
        """What this store believes TCGplayer is holding NOW: the reading, less what has sold
        here since it. D7's number, derived instead of stored.

        D7'S ORDERING IS HONOURED AND NOT REVERSED. Its defence — "holding the count back
        until a join makes the app disagree with the shelf the operator is standing in front
        of" — is a rule about WHEN the figure drops, not about which field it drops in. This
        drops the instant `sale` is called, on the same request, with no join in between. What
        it no longer does is corrupt the reading on the way past.

        FLOORED HERE AND NOWHERE ELSE, and moving the floor is the repair. `bump` floored the
        STORED figure, so a decrement lost to the floor was lost for good while a later undo
        still added one back. A floor on a DERIVED value loses nothing: `sold_here` keeps the
        full count underneath it, so sell/sell/undo/undo returns exactly where it started even
        where every intermediate estimate read zero.

        A counter ABOVE the reading is not an error. It is the ordinary state of a store whose
        reading predates its sales, and the honest answer there is "none is for sale", which
        is what zero says.
        """
        return max(0, max(0, int(self.live)) - max(0, int(self.sold_here)))

    def sales_pending(self, as_of: Optional[str]) -> int:
        """How many counted sales survive a reading taken at `as_of`.

        THE ONE RULE, read by `observe_live` for the store and by `cli/resolve.py:_copies_out`
        for the cap, so the two cannot disagree about one file — `live_reading`'s sibling, and
        it exists for `live_reading`'s reason. ALL OR NOTHING: one stamp cannot split a file
        that landed between two sales, so a file that cannot be shown newer than the newest
        counted sale clears none of them.

        THE STAMPLESS CASE GOES THE OTHER WAY FROM `live_reading`, AND THE ASYMMETRY IS THE
        POINT. There, an undateable reading keeps the authority D8 and D11 gave the export
        before `live_as_of` existed. Here it keeps the counter: a reading that cannot be placed
        in time cannot be shown to postdate a sale, and cancelling a sale on a guess is the
        loss D7's immediacy exists to prevent. So an undateable file still wins the FIGURE and
        still cannot cancel a sale.
        """
        if not self.sold_here:
            return 0
        if newer_stamp(as_of, self.sold_here_at) is True:
            return 0
        return max(0, int(self.sold_here))

    def sale(self, *, undone: bool = False) -> int:
        """One copy of this SKU sold HERE, or that sale reversed. Returns the new counter.

        IT TOUCHES NEITHER `live` NOR `live_as_of`, AND THAT IS THE ENTRY (D115). `live` is the
        export's reading and this store did not read an export; dating a sale into `live_as_of`
        claimed an observation of TCGplayer that nobody made, and it is what let one copy be
        subtracted twice — once by the export that already knew, once by here.

        ONE KEYWORD AND NOT A SIGNED `by`. `bump(LIVE, 1 if undo else -1)` put a sign flip at
        the call site for a direction the caller already holds as a bool, and the sign is
        INVERTED relative to that expression — a `+1` that used to mean "undo" now means
        "sold". `sale(undone=undo)` against `_sell(..., undo)` is a check anyone can make;
        re-deriving a sign is not.

        THE STAMP GOES FORWARD AND NOT BACK. A reversal that does not reach zero leaves
        `sold_here_at` where it is: the sale it named may be the one just undone, but the
        remaining sales are all older, and a stamp that is too NEW only makes the counter
        harder for an old export to clear — the direction that forgets nothing.
        """
        if undone:
            self.sold_here = max(0, int(self.sold_here) - 1)
            if not self.sold_here:
                self.sold_here_at = None
        else:
            self.sold_here = max(0, int(self.sold_here)) + 1
            self.sold_here_at = now()
        self.at = now()
        return self.sold_here

    def sight(self, as_of: Optional[str]) -> bool:
        """Record that this SKU was live at `as_of`. Monotone: the EARLIEST wins.

        SEPARATE FROM `observe_live` ON PURPOSE, and the separation is the whole design.
        `observe_live` arbitrates a QUANTITY — two readings of one number, newer wins — and
        returns `UNCHANGED` without touching anything when the figure has not moved, which
        is what keeps `reconcile --live`'s second pass a no-op. A first sighting is the
        opposite kind of fact: it is settled by the OLDEST reading, and it has to be
        recordable on exactly the pass where the quantity did not move, because a SKU that
        has sat at 4 copies since before this field existed is the one whose age nothing
        else can establish. Folding it into `observe_live` would have made it unreachable in
        that case or made `UNCHANGED` a lie in every other.

        Returns whether anything was written, so the caller can count and report. A reading
        with no parseable stamp writes nothing: `None` is not an early date, and a sighting
        that cannot be placed in time is not evidence about age.
        """
        if not as_of:
            return False
        if self.first_seen_live is not None and not newer_stamp(self.first_seen_live, as_of):
            return False
        self.first_seen_live = as_of
        self.at = now()
        return True

    def price_set(self, at: Optional[str] = None) -> None:
        """Record that this store set a price for this SKU. Stamp only — never the figure.

        THE FIGURE IS NOT STORED AND THAT IS THE POINT. Once a price is published it is live
        at TCGplayer, and the next export reads it straight back as `asking`; keeping a copy
        here would be a second money truth able to disagree with the export on the one field
        a buyer can see. What the export cannot report is whether THIS store made the change,
        which is what `reprice`'s ratchet needs so a rule cannot mark the same card down
        every time the screen is opened.
        """
        self.priced_at = at or now()
        self.at = now()

    def set(self, stage: str, value: int) -> int:
        """Set one stage absolutely, floored at zero. Returns the new value.

        Separate from `bump` so that a caller has to say which of the two it means, and so
        neither has to re-stamp `at` by hand. `join` and `reconcile --live` do NOT come
        through here for `live` any more: they hold a reading with its own time and go
        through `observe_live`. Setting `live` here is an observation THIS PROCESS is making
        now — D34's release path, a fixture — so it is dated now.
        """
        if stage not in LISTING_STAGES:
            raise UnknownState(f"{stage!r} not in {LISTING_STAGES}")
        value = max(0, int(value))
        setattr(self, stage, value)
        self.at = now()
        if stage == STAGED and value > 0:
            self.staged_at = self.staged_at or self.at
        if stage == LIVE:
            self.live_as_of = self.at
        return value

    def bump(self, stage: str, by: int = 1) -> int:
        """Move one stage's count by `by`, floored at zero. Returns the new value.

        IT REFUSES `live`, AND THAT REFUSAL IS THE POINT (D115). This used to carry a sale's
        ±1 — "an observation made now, so it is dated now" — and that sentence was the whole
        defect: a sale is a DELTA and dating it into `live_as_of` claimed a reading of
        TCGplayer nobody took, which let one copy be subtracted twice. `live` now has exactly
        one writer (`observe_live`, for a reading) and one counter beside it (`sale`, for a
        delta). Leaving this expression callable with a docstring explaining how to move
        `live` with it is how the next session puts the defect back, so it raises instead.

        `set(LIVE, …)` STAYS, and the asymmetry is deliberate: that one states a figure
        outright and is what a fixture and D34's release path use, where "this process is
        asserting a quantity" is exactly what is meant.
        """
        if stage == LIVE:
            raise UnknownState(
                "`live` is not bumped (D115). A READING goes through `observe_live`, which "
                "arbitrates it by `live_as_of`; a SALE goes through `sale()`, which counts "
                "against the reading rather than editing it."
            )
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
            if gave.get(LIVE):
                # A D34 release that reached `live` is an observation made now, like a sale.
                # One that stopped at `pushed` or `staged` learned nothing about `live` and
                # leaves its stamp where the last reading put it.
                self.live_as_of = self.at
        return gave


def _card_columns(card: "Card") -> Dict[str, object]:
    """The indexed columns beside a card's payload (D88). `box`/`idx` are NULL where the
    stored value will not coerce, which is how `next_index` finds such a record without a
    scan — see `int_or_none`."""
    return {
        "box": int_or_none(card.box),
        "idx": int_or_none(card.index),
        "state": card.state,
        "sku": card.sku,
        "condition": card.condition,
        "set_name": card.set_name,
        "rarity": card.rarity,
        "capture_id": card.capture_id,
        "name": card.name,
        "number": card.number,
        "game": card.game,
        "set_hint": card.set_hint,
        "run": card.run,
        "captured_at": card.captured_at,
        "state_at": card.state_at,
        # THE CARD'S NAME, INDEXED AND UNIQUE (D172). It is here so `cid -> (box, idx)` is
        # an index probe rather than a walk — measured at 4.0 us, `EXPLAIN` says
        # `SEARCH cards USING INDEX cards_cid (cid=?)` — and so a person can ask the
        # `sqlite3` CLI which slot a photograph is at.
        #
        # IT DOES NOT REFUSE A NULL, AND THAT IS A DELIBERATE DECISION AGAINST THE OBVIOUS
        # PLACE FOR ONE. This function is the single chokepoint every card row passes
        # through on its way to SQLite, which is exactly why a refusal here is wrong: it
        # would be a 500 on `POST /capture` in the middle of a feeder sitting, with the
        # physical card already in the drawer and no record of it — and a lost capture
        # renumbers every card behind it. `docs/specs/stable-card-id.md` §0.6 hazard 2 is
        # the argument, and it is the one `_ensure_schema`'s own docstring makes one layer
        # up. The refusal lives at the BIRTH of a record instead (`record_capture`), where a
        # missing name is a programming error in a caller rather than a data condition; a
        # NULL that reaches disk anyway is HEALED and reported by `store/db.py:_repair`.
        "cid": card.cid,
        # STORE-SCALING ITEM 8: the two forms `server/capture_server.py`'s `_card_number_key`
        # and `_number_display` compose, stored so the FTS5 search index (and any other
        # reader) can see them without re-running `store/numbers.py`'s rules a second time.
        # "" rather than NULL when there is no number, matching every other text column
        # here — FTS5's external-content triggers read these as ordinary column values, and
        # NULL/"" both index as nothing, but "" keeps `PRAGMA table_info` and a `sqlite3`
        # CLI session boring.
        "number_key": join_key(card.number, card.printed_total) if (
            card.number and card.printed_total
        ) else "",
        "number_display": display_number(card.number, card.printed_total) or "",
    }


def _known(cls, record: dict) -> dict:
    return {k: v for k, v in record.items() if k in cls.__annotations__}


@dataclass
class Inventory:
    """The master record. Written through `store.session`, one transaction per session.

    `cards`, `boxes` and `listings` are `Rows` (D88): a dict to every caller, and to a
    session bound to the database a set of queries that load only the rows a method names.
    The methods below that used to walk every card — the high-water scan, the capture-id
    replay, the SKU walk, the box-number allocator — ask the mapping for the rows they want
    instead, and the memory-backed mapping answers the same questions over its dict, so T7
    drives both backings through one code path.
    """

    cards: "Rows" = field(default_factory=lambda: Rows(Inventory.CARDS))
    boxes: "Rows" = field(default_factory=lambda: Rows(Inventory.BOXES))
    listings: "Rows" = field(default_factory=lambda: Rows(Inventory.LISTINGS))
    events: List[dict] = field(default_factory=list)
    # THE HIGH-WATER MARK FOR `Box.bid`, AND THE ONLY PART OF IT A DELETION MUST NOT LOWER
    # (D145). It is a scalar rather than a row because it is a fact about the
    # STORE and not about any box: the boxes table cannot hold it, since the whole point is
    # that the row whose id it remembers has been deleted.
    #
    # `store/db.py` keeps it in the `meta` table that has existed since D88 and
    # `store/session.py` reads it into the snapshot and writes it back inside the same
    # transaction as every table — so a crash cannot commit a box holding an id the counter
    # has forgotten, which is the one ordering that could hand the id out twice.
    #
    # ZERO IS "NOTHING ISSUED YET" and is the honest default for a memory-backed inventory
    # with no database under it. `next_box_id` never trusts it alone for that reason.
    box_ids_issued: int = 0
    # WHETHER EVERY PHOTOGRAPH IS AT THE CARD'S OWN NAME YET, as an ISO stamp or None
    # (`D183`). It is the gate on reading the legacy
    # `(box, index)` photograph address: while it is None `store/photos.find` still looks
    # there, so a resumable move of 4.45 GB can be interrupted without any screen going
    # dark, and once it is set the old address is NEVER consulted again — which is what
    # stops a migration-window fallback becoming a permanent second lookup.
    #
    # A STAMP RATHER THAN A BOOLEAN, because "when" is the question a person asks about a
    # move, and because `pkmnscan cards photos` is the only writer: no session sets this,
    # so unlike `box_ids_issued` it travels one way only and `store/session.py` does not
    # write it back.
    photos_relocated: Optional[str] = None

    def __post_init__(self) -> None:
        # A caller handing in a plain dict gets the same mapping the default gives.
        if not isinstance(self.cards, Rows):
            self.cards = Rows(Inventory.CARDS, objects=dict(self.cards))
        if not isinstance(self.boxes, Rows):
            self.boxes = Rows(Inventory.BOXES, objects=dict(self.boxes))
        if not isinstance(self.listings, Rows):
            self.listings = Rows(Inventory.LISTINGS, objects=dict(self.listings))

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
            listings[str(key)] = Listing.from_record(record)

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
                    if stage == LIVE:
                        # A v1 `live` state was a reading taken when the card wore it.
                        entry.live_as_of = entry.live_as_of or card.state_at
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

        try:
            issued = int(payload.get("box_ids_issued") or 0)
        except (TypeError, ValueError):
            issued = 0
        relocated = payload.get("photos_relocated")
        return cls(
            cards=Rows(cls.CARDS, objects=cards),
            boxes=Rows(cls.BOXES, objects=boxes),
            listings=Rows(cls.LISTINGS, objects=listings),
            box_ids_issued=max(0, issued),
            photos_relocated=str(relocated) if relocated else None,
        )

    def to_payload(self) -> dict:
        """The whole inventory as one JSON document — the legacy file's shape, kept as the
        wire shape of `GET /inventory` and as what a migration test compares. Loads every
        row, which is what a whole-store read costs."""
        return {
            "version": VERSION,
            # The counter travels with the document, so the legacy JSON shape — which is also
            # `GET /inventory`'s wire shape — round-trips a store without losing its place in
            # the id sequence. A payload written before the field reads 0, and `next_box_id`
            # recovers from that by taking the live maximum into account.
            "box_ids_issued": int(self.box_ids_issued or 0),
            "photos_relocated": self.photos_relocated,
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
        for _key, at in self._positions_in(box):
            highest = max(highest, at)
        return highest + 1

    def _positions_in(self, box: int) -> List[Tuple[str, int]]:
        """`(key, index)` of every record in `box`, refusing on any record that will not
        coerce — ANYWHERE in the store, which is the rule `next_index` has always had.

        Asked of the mapping as three indexed queries rather than a walk (D88): the rows
        whose `box` column is this box, plus the rows whose `box` or `idx` column is NULL —
        which is exactly the set of records `int()` refuses, since the columns are derived
        by the same coercion. A record that will not coerce is then LOADED so the refusal
        can name it with its raw value, as it always did; there are none in a healthy store,
        so the load is free. Nothing else in the box is built as an object.
        """
        out: List[Tuple[str, int]] = []
        seen = set()
        for key, (raw_box, raw_index) in self.cards.select(("box", "idx"), box=box):
            seen.add(key)
            if raw_box is None or raw_index is None:
                card = self.cards[key]
                _as_position_int(card.box, f"box of card {key}")
                _as_position_int(card.index, f"index of card {key}")
            out.append((key, int(raw_index)))
        for equals in ({"box": None}, {"idx": None}):
            for key, _ in self.cards.select(("box", "idx"), **equals):
                if key in seen:
                    continue
                seen.add(key)
                card = self.cards[key]
                _as_position_int(card.box, f"box of card {key}")
                _as_position_int(card.index, f"index of card {key}")
        return out

    def occupied_indices(self, box: int) -> Tuple[Tuple[int, Optional[str]], ...]:
        """`(index, game claim)` for every ON-HAND (non-terminal) record in `box`, ascending
        by index — D58's `occupied` input for a caller that needs `Position.slot`/`label`/
        `section`/`card`/`fraction` and NOTHING ELSE: no name, no photo path, no D30 neighbor
        walk. `_positions_in`'s own docstring is the precedent: two indexed columns read as
        three `select` queries, never a walk that hydrates a `Card` per row.

        `_Places.for_keys` (`server/capture_server.py`) is the one caller. An order's picks
        can span most of the store's boxes, and hydrating a full `Card` — JSON payload, name,
        photo fields — per row, for every record in every touched box, to answer a question
        that only needs an index and a state, is exactly the O(cards) cost D88 already fixed
        once for the capture allocator's high-water scan.

        THE GAME CLAIM TRAVELS RAW, UNINTERPRETED. Whether a record counts toward D58's
        occupied space at all depends on D24 too — a pooled (code-card) record has no slot
        and must not consume one in this count, exactly as `_Places._walk` already excludes
        it from `occupants` — but `store/` imports nothing from `pipeline/` (D63), so the
        registry's `located` flag cannot be resolved here. The caller, which already imports
        `pipeline.games`, applies that filter to the claim this method hands back verbatim.

        Refuses on the same records `_positions_in` refuses on — a box/idx column that will
        not coerce, anywhere in the store — for the same reason: `next_index`'s rule that an
        unparsable record stops the read rather than being silently skipped past.
        """
        box = _as_position_int(box, "box")
        live: List[Tuple[int, Optional[str]]] = []
        seen = set()
        for key, (raw_index, state, game) in self.cards.select(
            ("idx", "state", "game"), box=box
        ):
            seen.add(key)
            if raw_index is None:
                card = self.cards[key]
                _as_position_int(card.box, f"box of card {key}")
                _as_position_int(card.index, f"index of card {key}")
                raw_index = card.index
                state = card.state
                game = card.game
            if state not in TERMINAL_STATES:
                live.append((int(raw_index), game))
        for equals in ({"box": None}, {"idx": None}):
            for key, _ in self.cards.select(("box", "idx"), **equals):
                if key in seen:
                    continue
                seen.add(key)
                card = self.cards[key]
                _as_position_int(card.box, f"box of card {key}")
                _as_position_int(card.index, f"index of card {key}")
        live.sort(key=lambda row: row[0])
        return tuple(live)

    def records_in(self, box) -> List[Tuple[int, str, Card]]:
        """`(index, key, card)` for every record in `box`, ascending, coerced the way
        `next_index` coerces and refusing the same way. What the box-scoped routes walk
        instead of the whole store (D88)."""
        box = _as_position_int(box, "box")
        self._positions_in(box)  # the refusal, before anything is built
        out = [
            (_as_position_int(card.index, f"index of card {card.key}"), card.key, card)
            for card in self.cards.where(box=box)
        ]
        out.sort(key=lambda row: row[0])
        return out

    def newest_captured(self, limit: int) -> List[Tuple[str, int, int, Optional[str]]]:
        """`(key, box, index, cid)` of the `limit` most recently captured cards, newest
        first, for Home's hero deck (D192/item 2). Column values only — no `Card` built —
        because the deck over-fetches and filters (state, name, photo) on the small
        surviving set, never on the full result."""
        rows = self.cards.top("captured_at", limit, ("box", "idx", "cid"))
        return [(key, int(box), int(idx), cid) for key, (box, idx, cid) in rows]

    def allocate_capture(
        self,
        box,
        *,
        capture_id: Optional[str] = None,
        cid: Optional[str] = None,
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

        # `cid` IS A KEYWORD BESIDE `capture_id` AND DELIBERATELY NOT A MEMBER OF
        # `CAPTURE_CLAIM_FIELDS` (D172). A claim survives a re-record and is settable by the
        # operator; the card's NAME is issued once, at the birth of the record, and a
        # re-record must neither invent it nor replace it. Passing it through the claims
        # would make it correctable from the capture screen, which is the one thing it must
        # never be.
        card = Card(box=box, index=index, capture_id=capture_id, cid=cid, **claims)
        return self.record_capture(card), True

    def card_by_capture_id(self, capture_id: str) -> Optional[Card]:
        """The card recorded under `capture_id`, or None. Refuses on a duplicate."""
        matches = self.cards.where(capture_id=capture_id)
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
            # THE REFUSAL FOR A NAMELESS CARD LIVES HERE AND NOWHERE ELSE (D172, amended by
            # `docs/specs/stable-card-id.md` §0.6 hazard 2).
            #
            # THIS IS WHERE A CARD IS BORN, and it is the birth site every writer reaches —
            # `allocate_capture` above, and the three that do not go through it:
            # `cli/cmd_identify.py` and `cli/cmd_emit.py` twice, which is the seam this
            # class's own header calls "a seam to watch rather than a guarantee". A record
            # minted without a name would be a card the photograph store cannot address.
            #
            # AND IT IS DELIBERATELY NOT IN `_card_columns`, WHICH IS THE OBVIOUS PLACE.
            # That function is the single chokepoint every card row passes on its way to
            # SQLite, so a refusal there would cover every writer including ones nobody has
            # enumerated — and would be a 500 on `POST /capture` in the middle of a feeder
            # sitting, with the physical card already in the drawer and no record of it,
            # which renumbers every card behind it. `_ensure_schema`'s own docstring rejects
            # exactly that shape one layer up. A missing name HERE is a programming error in
            # a caller; a NULL that reaches disk anyway is healed by `store/db.py:_repair`.
            #
            # THE SHUTTER CANNOT REACH IT: `do_capture` hashes a blob already in RAM, so a
            # capture arrives named at zero extra I/O.
            if not card.cid:
                raise UnnamedCard(
                    f"{card.key} would be a new card with no `cid`. A card's name is the "
                    "sha256 of the photograph the store held when the id was issued (D172), "
                    "it is issued once here, and the photograph is filed under it — so a "
                    "record without one names bytes nothing can find. Pass `cid=` to "
                    "`allocate_capture`, or compute it from the photograph with "
                    "`store.photos.sha256_of`."
                )
            card.captured_at = card.captured_at or now()
            card.state = card.state or CAPTURED
            card.state_at = card.state_at or card.captured_at
            self.cards[card.key] = card
            self._log(CAPTURED, card.key, photo=card.photo, cid=card.cid)
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
        detected_finish: Optional[str] = None,
    ) -> None:
        card = self.cards.get(key)
        if card is None:
            return
        card.name = name
        card.number = number
        card.printed_total = printed_total
        card.confidence = confidence
        # WRITTEN UNCONDITIONALLY, LIKE THE FOUR ABOVE. An identification REPLACES the
        # reading; it does not merge into it. A caller that read no finish (a code card,
        # whose profile is not asked for one) means "this reading detected none", and
        # keeping the previous reading's answer here would be the stale-across-readings
        # defect this field was added to remove. Defaulted so `codes/scan.py` says that by
        # saying nothing.
        card.detected_finish = detected_finish
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
        set_name: Optional[str] = None,
        rarity: Optional[str] = None,
        run: Optional[str] = None,
    ) -> bool:
        """Move one card to a new state. Returns False if this position has no record.

        The return value is not decoration. A silent no-op on an unknown position is v1
        bug #5's exact shape — a transition that appears to happen, is reported as having
        happened, and did not — so callers check it and report the gap rather than
        assuming the write landed.

        `set_name` AND `rarity` FOLLOW `sku`/`condition`'s OWN RULE: written only when the
        caller has an answer, because the moment a SKU is committed is the moment the
        catalogue row is in hand — `cli/cmd_emit.py`'s `SkuMatch` carries both beside the
        SKU it resolved. A caller with no catalogue row (a bare state transition) passes
        neither and leaves them as they were.
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
        if set_name is not None:
            card.set_name = set_name
        if rarity is not None:
            card.rarity = rarity
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

    def record_photo_reclaimed(self, key: str, *, sha256: str, size: int) -> bool:
        """Record that this card's photograph has been deleted on purpose (D89).

        The FILE is the route's to remove, inside the same lock; this writes the two facts
        the record keeps once it is gone — the digest of what was there and when it went —
        and the history line carrying both plus the bytes freed. One method rather than two
        assignments, for `retire`'s reason: a digest without a stamp, or a stamp without a
        digest, is a record nobody can read. False if the position holds no record.

        SOLD ONLY, and the store refuses the rest rather than leaving it to the route: a
        retired card's photograph is what lets the retirement be questioned (D26), a moved
        tombstone has none, and a card still on hand is a card whose photograph the pull
        preview shows. The route says the same in its own code first.
        """
        card = self.cards.get(key)
        if card is None:
            return False
        if card.state != SOLD:
            raise CardNotSold(f"{key} is {card.state}, and only a sold card's photograph is reclaimed")
        card.photo_sha256 = sha256
        card.photo_reclaimed_at = now()
        self._log(PHOTO_RECLAIMED, key, sku=card.sku, sha256=sha256, bytes=int(size))
        return True

    def move_card(self, key: str, to_box) -> Tuple[Card, Card]:
        """Move one card to a fresh index in another box. Returns `(tombstone, transplant)`.

        D83. A card leaving box A for box B is the same KIND of event as a sale or a
        retirement — the position at `key` becomes permanently vacant — and not the same
        kind of event as `do_remove_card`'s mid-box delete, which cascades every higher
        card down one slot. D58 already re-argued and rejected moving the stored index for
        exactly this class of change, building an entire rendering layer so stored indices
        can stay put forever while displayed ranks close up over gaps; this reuses that
        wall's third door rather than reopening it. Concretely: nothing here shifts a single
        OTHER card. `key` becomes a tombstone in place, and a full transplant is recorded at
        a freshly allocated index in `to_box` — the ordinary `next_index` mechanism, not a
        slide.

        A NAIVE IN-PLACE REKEY WOULD BE WRONG, and this is why the shape below is a copy
        rather than a mutation-and-reinsert. `next_index` is a raw high-water scan over
        EVERY card in a box regardless of state — that is exactly how D10/D26 guarantee an
        index is never reissued. Deleting `key` outright (rather than tombstoning it) would
        let a future `next_index(box A)` recompute downward if this card held the box's
        current high mark, and the next capture into A would silently reuse an index that
        used to belong to a different physical card — worse than the one case D10 already
        restricts index reuse to (an undo of the newest, still-`captured` record).

        THE TOMBSTONE CLEARS `sku`, `condition`, `capture_id` AND `photo` — the sharpest
        correctness requirement here, not decoration. `copies_not_sold` (D59's per-SKU shelf
        cap) and `positions_for_sku` both filter on `sku` alone, with no state exclusion; a
        tombstone that kept its SKU would be counted alongside its own transplant forever,
        double-billing every cap and every copies-of-this-SKU list. `capture_id` is cleared
        for the same reason `card_by_capture_id` exists: two cards sharing one id raises
        `DuplicateCaptureId`, so the id lives on the transplant — the photograph, not the
        vacated slot, is what the id anchors. Descriptive fields (name, number, game,
        confidence, etc.) are LEFT on the tombstone, exactly as `retire()` leaves them, so a
        person looking at the old slot's history still sees what card used to be there.

        `photo` ON THE TRANSPLANT IS `None`, deliberately not carried over. The path is not
        knowable until the destination index is allocated — same reason `allocate_capture`
        never receives `photo` as a claim — so the caller (the one place that also moves the
        file on disk) sets it after this returns, inside the same write lock.

        UNDO IS NOT A SEPARATE OPERATION. The transplant is not itself terminal; moving it
        back is calling this method again in the other direction. It lands at a NEW index in
        the original box — the tombstoned key is never reclaimed, the same permanent-gap
        behavior every other terminal state already has.

        Refuses `CardNotFound` if `key` holds no record, `CardDeparted` if it is already
        sold, retired, or moved (a card that left through one door cannot leave again
        through another — move the transplant instead), and `BoxClosed` if `to_box` is
        sealed (the same refusal `allocate_capture` makes: a sealed box takes no more
        cards, and an arrival is exactly that).
        """
        to_box = _as_position_int(to_box, "to_box")
        card = self.cards.get(key)
        if card is None:
            raise CardNotFound(f"no card at {key!r}")
        if card.state in TERMINAL_STATES:
            where = f" to {card.moved_to}" if card.state == MOVED and card.moved_to else ""
            raise CardDeparted(f"{key} is already {card.state}{where}")

        registered = self.boxes.get(str(to_box))
        if registered is not None and registered.closed:
            raise BoxClosed(
                f"box {to_box} is sealed at {registered.capacity} cards. "
                "Re-open it on the Boxes screen, or move into another box."
            )
        self.ensure_box(to_box)

        new_index = self.next_index(to_box)
        new_key = position_key(to_box, new_index)
        if new_key in self.cards:
            raise PositionOccupied(
                f"move_card computed {new_key}, which already holds a card. "
                "The high-water scan and this check disagree, which means the inventory "
                "was mutated outside the lock."
            )

        transplant = replace(card, box=to_box, index=new_index, photo=None)
        self.cards[new_key] = transplant

        card.state = MOVED
        card.state_at = now()
        card.moved_to = new_key
        card.sku = None
        card.condition = None
        card.capture_id = None
        card.photo = None
        # A FIFTH THING THE TOMBSTONE GIVES UP, AND IT IS A PREFIX RATHER THAN A CLEAR
        # (D172). `replace(card, ...)` above already handed the transplant this card's name
        # — the name is the CARD's and the card is what moved — so leaving it on the
        # tombstone as well would put one value on two rows and fire `cards_cid`, which is
        # UNIQUE. It is NOT cleared to NULL, because a NULL cannot distinguish "no
        # photograph was found" from "this migration did not look" and because `_repair`
        # would then re-issue a name for a vacated slot. `moved:<name>` is shape 3: it says
        # whose slot this was and where the bytes went, and `photos.is_photo_cid` answers
        # False for it so nothing composes a path from it.
        #
        # AND NO FILE MOVES ANY MORE. Under the old layout the caller renamed the photograph
        # into the destination box's directory, because the filename WAS the address; the
        # photograph is filed under the card's name now, so a move is this field update and
        # nothing else.
        card.cid = f"{MOVED_CID_PREFIX}{card.cid}" if card.cid else None

        self._log(MOVED, key, moved_to=new_key, run=card.run, cid=transplant.cid)
        self._log(str(transplant.state), new_key, moved_from=key, run=transplant.run)
        return card, transplant

    def move_cards(self, keys: Sequence[str], to_box) -> List[Tuple[Card, Card]]:
        """Move several cards to fresh, contiguous indices in `to_box`, in the given order.

        D83. A thin loop over `move_card`, called inside one `store.session.Store.write()`
        by convention (not enforced here — this class has no lock of its own) so a whole
        section, split, or merge lands atomically rather than half-migrated on a crash.
        Order-preserving placement at the destination is not separate bookkeeping: each
        call consumes the next `next_index(to_box)` in turn, so cards handed in ascending
        source-index order land contiguously in that same order. Callers select `keys`
        from the box's live, on-hand rendering (D58) and skip anything already departed —
        there is nothing to move for a card that is already a permanent gap.
        """
        return [self.move_card(key, to_box) for key in keys]

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

    def box_disowns_run(
        self, box, run: str, ran_at: Optional[str], bid: Optional[int] = None
    ) -> Optional[str]:
        """The sentence refusing `run` over `box`, or None when the box is the run's own.

        `bid` IS THE RUN'S OWN RECORD OF WHICH DRAWER IT WAS OVER, and where it is present and
        the box has one too, it is the whole answer — the module-level rule is not consulted
        at all. Absent (every run written before D145, and every caller that has
        not learned to pass one) this behaves exactly as it always did.

        `box_disowns_run` (module-level) is the rule; this reads its inputs off the store —
        the registry entry's `created_at` and the `run` column of every card in the box, one
        column read and no card objects (D88). The sentence names what the rule saw, because
        the operator has to be able to check it against the `sqlite3` CLI: the entry's stamp,
        the count, and the runs whose cards are there now. A box the registry has never seen
        is nobody's to disown.
        """
        entry = self.box(box)
        if entry is None:
            return None
        number = int(entry.box)
        # THE TRUE INDEX DECIDES OUTRIGHT WHERE THE CALLER HAS ONE (D145). The
        # rule below reasons from the shape of the evidence and has to abstain when it cannot
        # tell; an id is a fact about which drawer this is, so there is nothing to weigh. The
        # sentence names both drawers, because the operator has to be able to check it — and
        # `Box 1` on its own is exactly the string that stopped being able to tell them apart.
        if bid is not None and entry.bid is not None and int(bid) != int(entry.bid):
            return (
                f"box {number} was deleted and its number reused after this run (the run was "
                f"over the drawer with index {int(bid)}; box {number} is now the drawer with "
                f"index {int(entry.bid)})"
            )
        if bid is not None and entry.bid is not None:
            return None
        present = [
            value
            for _, (value,) in self.cards.select(("run",), box=number)
            if isinstance(value, str) and value.strip()
        ]
        if not box_disowns_run(entry.created_at, present, run, ran_at):
            return None
        others = ", ".join(sorted(set(present)))
        return (
            f"box {number} was deleted and its number reused after this run (registry "
            f"entry created {entry.created_at}, holding {len(present)} card(s) from run "
            f"{others})"
        )

    def box_by_id(self, bid) -> Optional[Box]:
        """The drawer wearing this true index, or None because it has been deleted.

        None IS AN ANSWER HERE AND NOT AN ABSENCE, which is the whole difference between this
        and `box(number)`. A number always resolves to whatever drawer wears it today; an id
        resolves to the drawer that was given it and to nothing else ever again, so None means
        "that drawer is gone" rather than "look again under another key".
        """
        try:
            wanted = int(bid)
        except (TypeError, ValueError):
            return None
        for key, (_,) in self.boxes.select(("bid",), bid=wanted):
            return self.boxes[key]
        return None

    def next_box_id(self) -> int:
        """The next true index. A HIGH-WATER MARK, WHICH `next_box_number` DELIBERATELY IS NOT.

        `max(issued, every live bid) + 1`. The two terms answer different failures and neither
        is redundant:

          `issued`        survives a deletion, which is the property the whole field exists
                          for. A box deleted today must not hand its id to a box created
                          tomorrow, and the live rows can no longer say it was ever taken.
          the live max    survives a counter that has fallen behind — a store migrated by an
                          older build, a payload parsed from a JSON document with no counter
                          in it, a hand-edited `meta` row. Without it a stale counter would
                          issue an id a live box is already wearing, which is the one outcome
                          worse than a gap.

        GAPS ARE CORRECT AND ARE NEVER CLOSED. D10 argues the same thing about the card index
        and `docs/map.py`'s culled step 12 is the same rule about a build-order id: a reused
        identifier resurrects every reference to the thing that used to wear it, and nothing
        can detect that, because a stale id still resolves.
        """
        highest = max(0, int(self.box_ids_issued or 0))
        for _key, (value,) in self.boxes.select(("bid",)):
            if value is not None:
                try:
                    highest = max(highest, int(value))
                except (TypeError, ValueError):
                    continue
        return highest + 1

    def _issue_box_id(self) -> int:
        """Take the next id and move the mark past it, in one step so no caller can do one
        without the other."""
        issued = self.next_box_id()
        self.box_ids_issued = issued
        return issued

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
            entry = Box(box=number, bid=self._issue_box_id(), name=name, created_at=now())
            self.boxes[str(number)] = entry
            # `bid` ON THE EVENT, NOT ONLY ON THE ROW. The row is deleted when the drawer is;
            # the history is the only place that can still say which drawer `Box 1` meant on a
            # given day, and `server/pipeline_routes.py` reads exactly this to recover a
            # departed drawer's name for a run that outlived it.
            self._log("box_created", None, box=number, bid=entry.bid, name=name)
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
        # `bid` travels on this line for `box_created`'s reason: once the drawer is deleted the
        # history is the only record of what it was called, and a rename is where a name most
        # often comes from.
        self._log(
            "box_renamed", None, box=entry.box, bid=entry.bid,
            name_from=before, name_to=wanted,
        )
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
        for value in self.cards.distinct("box"):
            if value is not None:
                taken.add(int(value))
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
        # THE NAMES RIDE THE DIVIDERS (D132). `section_names` is keyed by the index a divider
        # sits at, so a divider nudged one card later would otherwise leave its name behind on
        # an index no section starts at. A layout with the SAME NUMBER of dividers is read as
        # the same dividers moved — the i-th old one is the i-th new one — and every name goes
        # with its divider. A layout that adds or drops a divider keeps names by exact index
        # only: nothing here can say which of the new dividers is "the same" one, and guessing
        # would put a name on the wrong plastic. An index that vanished loses its name, and
        # the `resectioned` line below carries both layouts so the loss is on the record.
        old_layout = list(check_sections(before)) if before else [1]
        new_layout = list(layout) if layout else [1]
        held = dict(entry.section_names)
        if len(old_layout) == len(new_layout):
            moved: Dict[str, str] = {}
            for was, now in zip(old_layout, new_layout):
                name = held.get(str(int(was)))
                if name:
                    moved[str(int(now))] = name
            entry.section_names = moved
        else:
            entry.section_names = {
                key: name for key, name in held.items()
                if name and any(str(int(at)) == key for at in new_layout)
            }
        entry.sections = list(layout)
        self._log(
            "resectioned", None, box=entry.box, sections_from=before, sections_to=list(layout)
        )
        return layout

    def section_names_for(self, number) -> Dict[int, str]:
        """A box's section names by ORDINAL — `Position.section`'s space, 1-based.

        `Box.section_names` is keyed by the divider INDEX the section starts at, so a moved
        divider carries its name with it; every screen speaks in ordinals, so this is the
        one place the two are joined. An undeclared box has one section starting at index 1,
        which is the key `open_section` materialises its first divider under — so a name
        given to "section 1" of an undivided box survives the first divider going in.
        """
        entry = self.box(number)
        if entry is None or not entry.section_names:
            return {}
        try:
            layout = entry.layout() or (1,)
        except BadSections:
            return {}
        out: Dict[int, str] = {}
        for ordinal, start in enumerate(layout, start=1):
            name = entry.section_names.get(str(int(start)))
            if isinstance(name, str) and name.strip():
                out[ordinal] = name
        return out

    def set_section_names(self, number, names: Dict[int, Optional[str]]) -> Dict[int, str]:
        """Name sections by ordinal, or clear names with None/blank. Logs both maps.

        THE SAME ARGUMENT AS `set_name` AND `set_sections`: a name is a label the operator
        reads a box by, and a relabel with no record of what it used to say is a rename that
        never happened. `section_named` carries the whole before/after, keyed by ordinal as
        the operator sees it. A no-op writes no event.

        REFUSES AN ORDINAL THE LAYOUT DOES NOT HAVE, as `BadSections` — naming section 4 of
        a three-section box is a typo, not a declaration, and quietly storing it under a
        divider that does not exist would surface the day a divider lands there.
        """
        entry = self.ensure_box(number)
        layout = entry.layout() or (1,)
        before = self.section_names_for(number)
        held = dict(entry.section_names)
        for ordinal, name in names.items():
            try:
                at = int(ordinal)
            except (TypeError, ValueError):
                raise BadSections(f"section {ordinal!r} is not a number") from None
            if at < 1 or at > len(layout):
                raise BadSections(
                    f"section {at} does not exist: box {entry.box} has "
                    f"{len(layout)} section{'s' if len(layout) != 1 else ''}"
                )
            key = str(int(layout[at - 1]))
            wanted = None if name is None or not str(name).strip() else str(name).strip()
            if wanted is None:
                held.pop(key, None)
            else:
                held[key] = wanted
        entry.section_names = held
        after = self.section_names_for(number)
        if after != before:
            self._log(
                "section_named", None, box=entry.box, names_from=before, names_to=after
            )
        return after

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
        return sorted(self.cards.where(sku=sku), key=lambda c: (c.box, c.index))

    def in_state(self, state: str) -> List[Card]:
        check_state(state)
        return sorted(self.cards.where(state=state), key=lambda c: (c.box, c.index))

    def counts(self) -> Dict[str, int]:
        counts = {state: 0 for state in STATES}
        for _, (state,) in self.cards.select(("state",)):
            counts[state] = counts.get(state, 0) + 1
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

    def copies_not_sold(self, sku: str) -> List[Card]:
        """Every copy carrying this SKU that has not SOLD — the sent-copy bound (D59).

        `SOLD` alone, and NOT `TERMINAL_STATES`, which is the opposite of the choice
        `copies_on_hand` above makes and is right for the opposite reason. A sale is proof
        a copy reached TCGplayer and left it. A RETIREMENT (D26) is the other door: the
        card left THIS box and TCGplayer was never told, so its row is still out there and
        counting it as gone would free a slot under the cap that is not free.

        What it bounds is `cli/resolve.py:_copies_out`. `pushed` has no drawdown — it is
        written by `cli/cmd_emit.py` and cleared only by `cli/cmd_reconcile.py`, which an
        operator is not obliged to run — so once an import LANDS the count claims copies the
        export is already reporting live. This is the physical fact that corrects it: we
        cannot have sent more copies than we own and have not sold.

        WHAT IT IS FOR CHANGED UNDER THIS BRANCH, AND THE PREMISE THAT MOVED IS WORTH
        KEEPING. It was the SHELF BOUND — "we cannot have SENT more copies than we own and
        have not sold" — which held only while `cli/cmd_emit.py` stamped a SKU onto exactly
        the copies it wrote into a file. D7's 2026-08-30 amendment moved that stamp to `uncommitted_positions`,
        correctly: the cap bounds the LISTING, not the IDENTITY, and copies past the fourth
        were invisible to every SKU-keyed surface. **A stamp now means MATCHED, not SENT**,
        so a count of stamped copies includes backstock that reached no import file.

        SO `cli/resolve.py:_copies_out` READS IT AS THE OTHER HALF OF A SUBTRACTION —
        `positions_for_sku` minus this is the number of copies of the SKU that have SOLD,
        and a sale is the one event that proves a sent copy has left TCGplayer, because a
        copy cannot sell without having been listed. That reading survives the stamp move:
        an unsent backstock copy is in both counts and cancels out.
        """
        return [c for c in self.positions_for_sku(sku) if c.state != SOLD]

    def sales_before(self, sku: str, as_of: Optional[str]) -> int:
        """Copies of this SKU marked SOLD before a reading taken at `as_of`.

        THE SECOND WAY AN EXPORT CORROBORATES A SALE, and the reason it is a count rather
        than a flag is `cli/resolve.py:_copies_out`, its one caller. That expression ages a
        `pushed` claim by the SKU's sales only where the export vouches for the copies having
        been AT TCGplayer; a reading that reports copies live now vouches for all of them,
        and a reading of nothing vouches for exactly the sales it was taken AFTER — a zero
        read four days after a copy sold is that sale's own result, not evidence the copy was
        never listed.

        STRICTLY BEFORE, AND AN UNDATEABLE STAMP ON EITHER SIDE COUNTS NOTHING. `newer_stamp`
        gives ties and unparseable pairs to the store, and both land here as "cannot be shown
        to predate the reading" — which leaves the claim standing, the direction that strands
        a copy rather than double-listing one. A record with no reading at all (`as_of` None)
        counts nothing for the same reason, and that is the case that keeps D59's negative
        case green: four pushed, one sold, no export ever read, and nothing here ages it.
        """
        if not as_of:
            return 0
        return sum(
            1
            for card in self.positions_for_sku(sku)
            if card.state == SOLD and newer_stamp(as_of, card.state_at) is True
        )

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

    # ------------------------------------------------------------------- the tables

    # HOW EACH MAPPING BECOMES ROWS (D88). `parse` is the same annotation-filtered
    # construction `Inventory.parse` has always done per record, so a row and a JSON record
    # are read by one rule; `dump` is `asdict`, the same as `to_payload`; `columns` is the
    # handful of indexed fields `store/db.py` declares beside the payload. Declared here and
    # not in `store/db.py` because the dataclass is the authority on its own fields, and the
    # database module must not have to learn a field's name to store it.
    CARDS = TableSpec(
        "cards",
        parse=lambda key, record: Card(**_known(Card, record)),
        dump=asdict,
        columns=_card_columns,
        column_names=(
            "box", "idx", "state", "sku", "condition", "capture_id", "name", "number",
            "game", "set_hint", "run", "captured_at", "state_at", "cid",
            "number_key", "number_display",
            # D213, matching
            # `store/db.py:TABLES["cards"]` and `_card_columns` above.
            "set_name", "rarity",
        ),
    )
    BOXES = TableSpec(
        "boxes",
        parse=lambda key, record: Box(**_known(Box, record)),
        dump=asdict,
        columns=lambda box: {
            "box": int_or_none(box.box),
            # INDEXED, so `box_by_id` is a query and not a walk over every drawer — and so a
            # person can ask the `sqlite3` CLI which drawer a run meant.
            "bid": int_or_none(box.bid),
            "name": box.name,
            "state": box.state,
        },
        column_names=("box", "bid", "name", "state"),
    )
    LISTINGS = TableSpec(
        "listings",
        parse=lambda key, record: Listing.from_record(record),
        dump=asdict,
        columns=lambda entry: {
            "condition": entry.condition,
            "pushed": int_or_none(entry.pushed),
            "staged": int_or_none(entry.staged),
            "live": int_or_none(entry.live),
        },
        column_names=("condition", "pushed", "staged", "live"),
    )
