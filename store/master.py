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

Positions are never renumbered and sold cards leave permanent gaps (D10). Nothing in this
module deletes a card record; `sold` is a state, not a removal.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

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


def check_state(state: str) -> str:
    if state not in STATES:
        raise UnknownState(f"{state!r} not in {STATES}")
    return state


def position_key(box: int, index: int) -> str:
    return f"{int(box)}/{int(index)}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
