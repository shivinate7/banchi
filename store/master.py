"""`inventory.json` — cards, positions, SKUs, listing states.

One record per PHYSICAL CARD, keyed by position, never per SKU. D7 collapses copies to one
import row but keeps every copy as its own position with its own photo, because that is what
makes an order pull addressable: the app maps SKU -> all positions holding it, and the pull
marks one of them sold. Aggregation is a property of the import file, not of the inventory.

LISTING STATES, and why there are three after `pushed` rather than one:

    captured    a photo and a position exist
    identified  the model answered for it
    pushed      `emit` wrote its row into an import file
    staged      an Export From Staged download confirmed TCGplayer has it
    live        a later Filtered Export shows quantity against that SKU
    sold        a pull marked this specific copy sold

Writing a CSV proves only that a CSV was written, so each state past `pushed` is confirmed
by something outside this pipeline. Collapsing `staged` and `live` would make D7's refill
math wrong: `Add to Quantity = min(cap - live, backstock)` reads the LIVE number, and an
import that was staged and never moved live has no live quantity at all — so a collapsed
state would refill against inventory that is not for sale.

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

VERSION = 1

CAPTURED = "captured"
IDENTIFIED = "identified"
PUSHED = "pushed"
STAGED = "staged"
LIVE = "live"
SOLD = "sold"

STATES = (CAPTURED, IDENTIFIED, PUSHED, STAGED, LIVE, SOLD)

# Cards sitting here this long are named in the run report — an import that was staged and
# then never moved live is invisible otherwise, and it is a whole box not earning.
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


def check_state(state: str) -> str:
    if state not in STATES:
        raise UnknownState(f"{state!r} not in {STATES}")
    return state


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
    name: Optional[str] = None
    number: Optional[str] = None
    printed_total: Optional[str] = None
    confidence: Optional[str] = None
    sku: Optional[str] = None
    condition: Optional[str] = None
    state: str = CAPTURED
    state_at: Optional[str] = None
    run: Optional[str] = None

    @property
    def key(self) -> str:
        return position_key(self.box, self.index)

    @property
    def days_in_state(self) -> Optional[int]:
        return _days_since(self.state_at)


@dataclass
class Inventory:
    """The master record. Rewritten whole, always through `store.session`."""

    cards: Dict[str, Card] = field(default_factory=dict)
    events: List[dict] = field(default_factory=list)

    # ------------------------------------------------------------------ (de)serialising

    @classmethod
    def parse(cls, payload: Optional[dict]) -> "Inventory":
        payload = payload or {}
        cards = {}
        for key, record in (payload.get("cards") or {}).items():
            known = {k: v for k, v in record.items() if k in Card.__annotations__}
            cards[key] = Card(**known)
        return cls(cards=cards)

    def to_payload(self) -> dict:
        return {
            "version": VERSION,
            "cards": {key: asdict(card) for key, card in sorted(self.cards.items())},
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
        photo: Optional[str] = None,
        set_hint: Optional[str] = None,
        metadata_finish: Optional[str] = None,
    ) -> Tuple[Card, bool]:
        """Assign the next index in `box` and record the card. Returns `(card, created)`.

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

        if capture_id is not None:
            replay = self.card_by_capture_id(capture_id)
            if replay is not None:
                return replay, False

        index = self.next_index(box)
        key = position_key(box, index)
        if key in self.cards:
            raise PositionOccupied(
                f"allocate_capture computed {key}, which already holds a card. "
                "The high-water scan and this check disagree, which means the inventory "
                "was mutated outside the lock."
            )

        card = Card(
            box=box,
            index=index,
            capture_id=capture_id,
            photo=photo,
            set_hint=set_hint,
            metadata_finish=metadata_finish,
        )
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

        for attribute in ("photo", "set_hint", "metadata_finish"):
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

    def _log(self, event: str, key: str, **extra) -> None:
        record = {"at": now(), "event": event, "position": key}
        record.update({k: v for k, v in extra.items() if v is not None})
        self.events.append(record)

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

    def staged_stale(self, days: int = STAGED_STALE_DAYS) -> List[Card]:
        """Staged this long ago and still not live — the import nobody finished."""
        out = []
        for card in self.in_state(STAGED):
            age = card.days_in_state
            if age is not None and age >= days:
                out.append(card)
        return out
