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
does. TWO things set `cleared_by_human`, and they are categorically different:
`do_review_answer` writes an identification onto the card (D4), and `do_review_stand_down`
writes NOTHING to the card at all — it closes the QUESTION and leaves the card in its slot,
sellable if it is ever identified properly (D37, whose reasons are `STAND_DOWN_REASONS`
below). One flag, two meanings, and the log is what tells them apart: `_clearing_event` reads
back which event closed a question so the un-dismiss control cannot take back a real answer.
This module only honours the flag — `upsert` refuses to re-queue a cleared position, `release` refuses to drop
one, and `open_entries` hides it. That path stopped being untravelled on 2026-08-22: Gate B's
16 entries were all answered through it. Absent an answer the queues still only grow, and
that is the correct behaviour rather than a gap to be patched with a clearing command the
spec does not list — a card in a queue is at a known position in a box, and is not lost.

`reopen` IS THE ONE DOOR BACK OUT, AND IT IS D28's UNDO WINDOW RATHER THAN A LOOSENING OF ANY
OF THAT. The paragraph above is written about a LATER RUN re-asking a question a human has
already settled, which is the thing that must never happen; the answer's own undo is the same
human reversing himself while the tap is still warm, which is a different caller entirely. The
two rules coexist because they are about different callers, and every refusal above is
unchanged: `upsert` still will not re-queue a cleared entry, and `release` still will not drop
one. See `Queue.reopen` for how narrow the door is, and D28 for why it exists at all.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from store.rows import Rows, TableSpec, int_or_none

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


# How long a card may wait before it outranks price. Thirty days rather than a tuned
# number: it is long enough that nothing in a normal week of working the queue is touched
# by it, and short enough that a starved card surfaces inside the month it was captured.
# It is a threshold and not a token — docs/DESIGN.md's scale is spacing.
STARVATION_DAYS = 30

# D37 — why a human waved a card off the queue without answering it.
#
# ITS OWN VOCABULARY RATHER THAN `master.RETIRE_REASONS`, and the difference is the whole
# point of the feature. D26's four reasons — pulled, damaged, lost, given_away — all say the
# CARD left inventory. A stand-down says the QUESTION is closed while the card stays exactly
# where it is, in its slot, in its box, still findable and still sellable if it is ever
# identified properly. Borrowing the retire words would have made "stop asking me" indexable
# as "this card is gone", which is the one thing it must not mean.
#
# THREE, AND HAND-AUTHORED IN D22'S SENSE. A later session could reasonably disagree with the
# cut, so it is argued rather than derived, and it renders verbatim on screen beneath its
# human label exactly as a routing reason does.
STAND_DOWN_REASONS = ("wasted_position", "cannot_settle", "not_listing")


class UnknownStandDownReason(ValueError):
    """A stand-down reason outside `STAND_DOWN_REASONS`. Never coerced, never defaulted."""


def check_stand_down_reason(reason: str) -> str:
    if reason not in STAND_DOWN_REASONS:
        raise UnknownStandDownReason(f"{reason!r} not in {STAND_DOWN_REASONS}")
    return reason


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
    def sort_key(self) -> Tuple[int, int, Decimal, int, int]:
        """Starved first, then priced descending, then unpriced; ties by box-walk order.

        THE STARVATION TIER EXISTS BECAUSE PRICE ALONE NEVER RELEASES SOME CARDS. A card
        with no catalog row has no market price, `price` is None, and the tier below sorts
        it last — permanently. Box 2 left 47 residual entries in exactly that state, every
        one `no_catalog_row`, and no amount of working the queue from the top ever reaches
        them. At forty boxes that is several hundred entries that are queued, counted, and
        unreachable.

        This is not a new idea and it is not a guess: prioritised medical worklists hit the
        same wall, where a scored ordering pushed the worst-case wait to 1178 minutes
        against 890 under plain FIFO until a maximum-waiting-time escalation was added.
        docs/specs/ui-research.md carries the citation. The fix is the same shape here.

        ESCALATION IS A TIER, NOT A WEIGHT. A blended score — price plus some multiple of
        age — would be one number nobody could predict, and it would quietly re-order the
        expensive cards against each other as days passed. A tier leaves
        docs/DESIGN.md's "worked expensive-first" ordering byte-identical for everything
        inside the threshold, and only ever promotes a card that has genuinely been
        abandoned. Inside the tier the OLDEST goes first, which is the only ordering that
        makes the tier empty itself.

        An entry with no `first_seen` has no age, so it can never starve. That is the
        conservative reading: `_age_days` returns None for a missing or malformed stamp,
        and a card whose wait cannot be measured must not be promoted over one whose
        price is known.
        """
        age = self.age_days
        if age is not None and age >= STARVATION_DAYS:
            return (0, -age, Decimal("0"), self.box, self.index)
        if self.price is None:
            return (2, 0, Decimal("0"), self.box, self.index)
        return (1, 0, -self.price, self.box, self.index)

    @property
    def describe(self) -> str:
        money = "unpriced" if self.market is None else f"${self.market}"
        age = self.age_days
        waited = "" if age is None else f", {age}d"
        return f"{self.label}  {self.read.get('name') or '?'}  {self.reason}  {money}{waited}"


def _parse_entry(key: str, record: dict) -> Optional[QueueEntry]:
    """One queued card from its stored record, or None for a shape that will not construct.
    One rule for a JSON record and a database row (D88)."""
    if str(key).startswith("_"):
        return None
    known = {k: v for k, v in record.items() if k in QueueEntry.__annotations__}
    try:
        return QueueEntry(**known)
    except TypeError:
        return None


@dataclass
class Queue:
    """One standing queue. Was one file each; both are the `queues` table since D88,
    told apart by the `queue` column that `store/session.py` binds each mapping to."""

    name: str
    entries: "Rows" = field(default_factory=lambda: Rows(Queue.ENTRIES))

    ENTRIES = TableSpec(
        "queues",
        parse=_parse_entry,
        dump=asdict,
        columns=lambda entry: {
            "box": int_or_none(entry.box),
            "idx": int_or_none(entry.index),
            "reason": entry.reason,
            "cleared_by_human": 1 if entry.cleared_by_human else 0,
            "first_seen": entry.first_seen,
        },
        column_names=("box", "idx", "reason", "cleared_by_human", "first_seen"),
    )

    def __post_init__(self) -> None:
        if not isinstance(self.entries, Rows):
            self.entries = Rows(Queue.ENTRIES, objects=dict(self.entries))

    @classmethod
    def parse(cls, name: str, payload: Optional[dict]) -> "Queue":
        entries = {}
        for key, record in (payload or {}).items():
            entry = _parse_entry(key, record)
            if entry is not None:
                entries[key] = entry
        return cls(name=name, entries=Rows(cls.ENTRIES, objects=entries))

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

    def reopen(self, position: str) -> bool:
        """Put one answered entry back to waiting. False when there was nothing to reopen.

        D28's UNDO WINDOW, AND NOTHING WIDER. `upsert` above refuses to re-queue a position a
        human has cleared and `release` below refuses to drop one, so that an answer outlives
        the question that produced it. This is a hole punched through that on purpose rather
        than a softening of it, and what makes the two compatible is the CALLER. `upsert`'s
        refusal guards against a LATER RUN asking a question that has already been settled;
        this is the same person reversing his own answer inside a window measured in seconds.
        Neither is the other, and one file can honour both.

        WHAT IT WILL NOT DO IS AS NARROW AS WHAT IT DOES. It flips one flag on one entry that
        is already in this queue. It never creates an entry — a position whose row was dropped
        is a card whose question is gone, and inventing a fresh one here would put a queue
        entry on screen that no run produced. It does not touch `first_seen` either, which was
        never touched on the way in: the card has been waiting since it was first queued, and
        an answer that stood for twenty seconds does not reset how long that has been.

        NO CLOCK LIVES HERE, and that is D28's ruling rather than an omission. The window is
        the screen's — `app/src/ReviewQueue.tsx` decides how long the control stays up, exactly
        as `app/src/Fulfillment.tsx` does for mark-sold — because a deadline enforced down here
        would fail the reversal precisely when the store was slow to lock. A queue file has no
        way to know what time the tap was in any case.

        FALSE RATHER THAN A RAISE, AND THE CALLER IS EXPECTED TO CHECK IT. An entry that is
        absent and an entry that was never answered are both "nothing to reopen" from here, and
        they are two different refusals to the route above: `not_in_queue` sends the operator
        to another card, `not_answered` tells him the reversal already happened. That is a
        distinction this module has no vocabulary for and should not grow one for. A silent
        no-op reported as a success is v1 bug 5's shape, so `server/capture_server.py` checks
        this return the way it checks `Inventory.set_state`'s.

        `release` IS UNCHANGED. A reopened entry is an open entry, so a later run may release
        it exactly as it could before the answer — which is correct: once the answer has been
        withdrawn there is no answer left for anything to outlive.
        """
        entry = self.entries.get(position)
        if entry is None or not entry.cleared_by_human:
            return False
        entry.cleared_by_human = False
        return True

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
