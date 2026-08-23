"""`review.json` and `parked.json` — the standing queues.

STANDING, not per-run. A card that could not be resolved on Tuesday is still unresolved on
Friday, and a per-run queue would report it as new every time it was re-joined while losing
how long it had actually been waiting. So entries are keyed by position and carry
`first_seen`, which survives every re-run.

TWO QUEUES, and the separation is the point (v2 §5.4). The main queue is work: cards worth a
tap, worked expensive-first. Parked is the low-value queue: an unidentifiable 15-cent card
may never be worth a tap, and mixing it into the main queue is how the $12 cards get missed.
Parked cards are explicitly candidates for the D9 Bulk Lots exit.

Every run report LEADS with these totals and their age, and `emit` RESTATES them beside the
row count it wrote. You see the number when choosing what to work on, and again at the
moment you commit an import file — which is the moment it is easiest to forget that seven
cards are still sitting in a box unlisted.

NOTHING HERE CLEARS AN ENTRY, and that is still the arrangement now that something finally
does. `do_review_answer` in `server/capture_server.py` sets `cleared_by_human`; this module
only honours it — `upsert` refuses to re-queue a cleared position, `release` refuses to drop
one, and `open_entries` hides it. That path stopped being untravelled on 2026-08-22: Gate B's
16 entries were all answered through it. Absent an answer the queues still only grow, and
that is the correct behaviour rather than a gap to be patched with a clearing command the
spec does not list — a card in a queue is at a known position in a box, and is not lost.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

MAIN = "review"
PARKED = "parked"

FILENAMES = {MAIN: "review.json", PARKED: "parked.json"}


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _age_days(stamp: Optional[str]) -> Optional[int]:
    if not stamp:
        return None
    try:
        seen = datetime.strptime(stamp, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - seen).days


@dataclass
class QueueEntry:
    """One card waiting for a human, with everything the review screen needs to show it."""

    position: str
    box: int
    index: int
    label: str
    photo: Optional[str] = None
    read: Dict[str, object] = field(default_factory=dict)
    confidence: Optional[str] = None
    reason: str = ""
    candidates: List[Dict[str, object]] = field(default_factory=list)
    first_seen: str = ""
    market: Optional[str] = None
    cleared_by_human: bool = False

    @property
    def age_days(self) -> Optional[int]:
        return _age_days(self.first_seen)

    @property
    def price(self) -> Optional[Decimal]:
        return None if self.market is None else Decimal(self.market)

    @property
    def sort_key(self) -> Tuple[int, Decimal, int, int]:
        """Priced first, descending by price, unpriced last; then box-walk order."""
        if self.price is None:
            return (1, Decimal("0"), self.box, self.index)
        return (0, -self.price, self.box, self.index)

    @property
    def describe(self) -> str:
        money = "unpriced" if self.market is None else f"${self.market}"
        age = self.age_days
        waited = "" if age is None else f", {age}d"
        return f"{self.label}  {self.read.get('name') or '?'}  {self.reason}  {money}{waited}"


@dataclass
class Queue:
    """One standing queue file."""

    name: str
    entries: Dict[str, QueueEntry] = field(default_factory=dict)

    @classmethod
    def parse(cls, name: str, payload: Optional[dict]) -> "Queue":
        entries = {}
        for key, record in (payload or {}).items():
            if key.startswith("_"):
                continue
            known = {k: v for k, v in record.items() if k in QueueEntry.__annotations__}
            try:
                entries[key] = QueueEntry(**known)
            except TypeError:
                continue
        return cls(name=name, entries=entries)

    def to_payload(self) -> dict:
        return {key: asdict(entry) for key, entry in sorted(self.entries.items())}

    def __len__(self) -> int:
        return len(self.open_entries)

    @property
    def open_entries(self) -> List[QueueEntry]:
        """Everything still waiting, in the order it should be worked."""
        return sorted(
            (e for e in self.entries.values() if not e.cleared_by_human),
            key=lambda e: e.sort_key,
        )

    @property
    def oldest_days(self) -> Optional[int]:
        ages = [e.age_days for e in self.open_entries if e.age_days is not None]
        return max(ages) if ages else None

    def upsert(self, entry: QueueEntry) -> bool:
        """Add or refresh an entry. Returns True if this position is newly queued.

        `first_seen` is preserved, and a cleared entry is left completely alone: re-queueing
        a card a human already answered would undo the answer, which is the one thing this
        module must never do.
        """
        existing = self.entries.get(entry.position)
        if existing is not None and existing.cleared_by_human:
            return False
        entry.first_seen = (
            existing.first_seen if existing and existing.first_seen else today()
        )
        self.entries[entry.position] = entry
        return existing is None

    def release(self, positions) -> List[str]:
        """Drop entries that no longer belong here — a card that resolved on a later run.

        Cleared entries stay: they are the human's answer, and the answer outliving the
        question is the entire point of `cleared_by_human`.
        """
        keep = set(positions)
        gone = [
            key
            for key, entry in self.entries.items()
            if key not in keep and not entry.cleared_by_human
        ]
        for key in gone:
            del self.entries[key]
        return gone

    @property
    def summary(self) -> str:
        count = len(self.open_entries)
        if not count:
            return f"0 cards in {self.name}"
        age = self.oldest_days
        oldest = "" if age is None else f", oldest {age} days"
        return f"{count} cards in {self.name}{oldest}"


def apply_run(
    review: Queue,
    parked: Queue,
    main_entries: List[QueueEntry],
    parked_entries: List[QueueEntry],
    freed: set,
) -> Tuple[int, int, List[str]]:
    """One run's verdict on the standing queues, applied as a unit.

    Upserts the run's entries, then releases everything the run superseded: positions that
    resolved outright (`freed`), and — the case a real run caught on 2026-08-22 — the entry
    a re-routed position leaves behind in the queue it moved OUT of. The garbage run put 45
    misidentified cards in review; the corrected run re-identified the same positions and
    parked 16 of them, and every one kept its stale review entry beside the live parked one,
    because each queue's release was computed from that queue's own entries alone. The
    review screen would have shown the same physical card twice, one of them describing an
    identification that no longer existed. This function exists so the two queues are never
    released in ignorance of each other again — and it lives here rather than in
    `cli/cmd_join.py` so the seam T7 tests is the seam the command runs.

    `Queue.release` still protects entries a human cleared: an answer outlives the
    question, including across a re-route.

    Returns (added_main, added_parked, released_positions).
    """
    added_main = sum(1 for queued in main_entries if review.upsert(queued))
    added_parked = sum(1 for queued in parked_entries if parked.upsert(queued))
    main_now = {queued.position for queued in main_entries}
    parked_now = {queued.position for queued in parked_entries}
    released = review.release(set(review.entries) - freed - parked_now)
    released += parked.release(set(parked.entries) - freed - main_now)
    return added_main, added_parked, released
