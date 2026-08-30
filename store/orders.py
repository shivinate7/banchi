"""`inventory/orders.json` — the durable order ledger.

`pipeline/orders.py` RESOLVES and stores nothing; this is the half that persists. The
split is not tidiness: the resolver's answer is a set of positions true of one `Inventory`
snapshot and of no other (D36), so it must be recomputed on every read, while an order
itself is a fact about the outside world that outlives every snapshot. One record per
`{source}:{order_number}`, upserted, read and written through `store/session.py` in the
shape `store/queues.py` uses.

THE FILE HAS TWO TOP-LEVEL MAPS AND THE SEPARATION IS THE WHOLE DESIGN.

    orders      what the FEED said. Replaced wholesale on every sync.
    fulfilment  what WE did. `ingest` cannot name this map, let alone write it.

One record holding both would be the defect this module exists to prevent. Ingest replaces
by key, so a fulfilment count living inside the replaced record is destroyed on the next
sync — and the consequence is not a lost statistic, it is the picker being sent to a slot
whose card is already in the post, which is selling the same physical card twice. A
careful merge inside `ingest` would also work and would be one refactor away from not
working; two maps and a method that touches one of them is a property a reader can check
in five seconds. `first_seen` is the deliberate exception and is marked as one below,
because losing a date is cosmetic and losing a card is not.

INGEST WRITES NO CARD STATE AND NO LISTING COUNT. Not `set_state`, not `Listing.bump`, not
one byte of `inventory.json`. That is what makes pressing sync twice a no-op BY
CONSTRUCTION rather than by a guard somebody has to keep true — this module cannot reach a
card, because it holds no `Inventory` and imports nothing that does. A ledger that moved a
card to `sold` on ingest would re-sell every order in the file on every sync, and a guard
against that is one refactor from being wrong; not having the capability is not.

RE-INGESTING UNCHANGED ORDERS REWRITES NO BYTES. `changed_at` is stamped only where the
feed's content actually differs, so a sync that learns nothing leaves this file
byte-identical — T1's own rule for `harness/results/`, which does not restamp
`generated_at` on a cached re-scoring, for the same reason: a one-line diff on every run is
how a real change stops being visible. There is deliberately no `last_synced_at`; when the
sync ran is a property of the sync, not of an order, and storing it here would defeat the
paragraph above to record something no reader needs.

FULFILMENT IS A COUNT, AND WHERE AN IDENTITY IS UNAVOIDABLE IT IS A `capture_id`.
`LineProgress.fulfilled` is a NUMBER. It is never a list of positions, because a position
is not durable: D10 ruling 1 lets a junk capture be deleted from the middle of a box, which
slides every higher index down one, so a position written down today names a different card
tomorrow — that is D36, and `cli/resolve.py:realign` exists because a run directory made
exactly this mistake. A count survives a renumber because it names no slot, and it still
tells a filled order from an unfillable one, which is the only thing anybody asks of it.

`LineProgress.copies` carries `capture_id`s, and that is the one identity this module will
hold. It is minted once per `POST /capture`, it is unique store-wide
(`master.Inventory.card_by_capture_id` refuses a duplicate rather than picking), and it
survives a renumber by construction: the shift rewrites `box` and `index` and the record
keeps its id. `server/capture_server.py:_drop_from_stores` exists precisely because the
queues and the answer cache ARE position-keyed and have to be remapped by hand at every
delete; a fourth store in that condition is a fourth thing to remember, and this one
declines to be it.

WHAT `capture_id` DOES NOT SURVIVE, named rather than left to be discovered: a re-shoot.
`do_reshoot` requires the NEW photograph's id and writes it onto the record (D26), so a
copy re-shot after being pulled reads as a copy this ledger has never seen. It is not
reachable through any sequence that makes sense — a pulled copy is in the post and is not
re-photographed — and it is the honest limit on the sentence above.

NOTHING HERE CLEARS AN ORDER, and that is `store/queues.py`'s arrangement for
`store/queues.py`'s reason: the queues only grow, because a card in a queue is at a known
position in a box and is not lost. An order that is cancelled does not leave this file
either; `status` carries the feed's own word for it, verbatim, and a cancellation is a
status rather than a deletion. So there is no `drop` and no `release`, and adding one is a
decision about what an order's absence would mean rather than a convenience.

IT LOGS NOTHING TO `history.jsonl`. Two reasons and both are load-bearing. A sync that
appended a line per order would not be the no-op the third paragraph promises. And this
module changes nothing about a card, so there is nothing for that log to describe — when
the pull route is built, IT touches a card and IT logs, through `Inventory._log`, in the
same locked session. No order state is added to `master.STATES` for the same reason at one
remove: `server/capture_server.py:_state_before_sale` and `_state_before_retirement` scan
that log for the last event whose name is in that tuple, so a new member makes both
reversals restore a card to something that is not a state. That is D26's `removed`/`retired`
collision exactly, and this module stays on the other side of it by holding no states at
all.

IT IMPORTS NOTHING FROM `pipeline/`, WHICH IS WHY `OrderLine` IS DECLARED TWICE. The edge
runs the other way — `pipeline/orders.py` imports `store`, and `docs/map.py` records that
`store/` imports nothing from `pipeline/` so there is no cycle — so the resolver's frozen,
coercing `OrderLine` cannot be reused here and this file declares a stored one of its own.
They are not redundant: the same split `store/queues.py:QueueEntry` has against
`pipeline/join.py`'s carriers, for the same reasons. This one is a mutable dataclass that
`asdict` round-trips and `__annotations__` filters; that one is a frozen domain object
whose `__post_init__` coerces the SKU. Converting between them belongs to the caller that
already imports both, never here.

`kind` IS CARRIED VERBATIM AND VALIDATED NOWHERE IN THIS FILE. `pipeline/orders.py` owns
`LINE_KINDS` and refuses an unknown one with `UnknownLineKind`; a second copy of that
vocabulary here would be two lists nothing reconciles, which is the drift D16 exists to
catch. `None` means the feed declared nothing and reads as the resolver's own default —
D21's read-side backfill, applied at the read and never written.

NO BUYER, NO ADDRESS, NO EMAIL. The ledger holds what is needed to pick and pack — a SKU, a
quantity, and what the feed called the card — and nothing that identifies a person.
`inventory/` is gitignored whole, which is a reason to keep bearer instruments out of a
commit (`store/files.py`'s code ledger) and not a licence to accumulate somebody's postal
address on this disk.

IT DOES NO I/O AND HOLDS NO LOCK. Like `queues.py` it is a data structure; `store/session.py`
reads it, hands it over, and writes it back inside the lock it already holds. `files.exclusive`
polls at 50ms and gives up at 30s while the feeder captures a card every 623ms, so a module
down here that fetched an order feed would stall real capture — the fetch belongs to the
caller, ABOVE the lock, and `ingest` takes records that are already in memory.

WHAT THIS COSTS, NAMED HERE BECAUSE NOTHING ELSE WOULD SAY IT: `Store.write()` replaces
four JSON files in sequence and the set is not atomic. Each is atomic alone —
`files.write_atomic` stages beside the target and `os.replace`s — and nothing makes the
four one transaction, so a kill between them leaves a torn store. This file is a FIFTH, and
it widens that window by a fifth. D53 records the same exposure from the other end and
prices it: it is why the supervisor drains in-flight requests before it restarts a child,
because the risk is already live at Ctrl-C frequency. The honest ordering does not close it
either — this file is written LAST, after the four, so a torn write loses the ledger rather
than the inventory, which is the cheaper half to lose because the feed can be re-ingested
and a photograph cannot.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

FILENAME = "orders.json"

VERSION = 1

# The separator between the feed and the order's own number. The KEY is
# `{source}:{order_number}`, split on the FIRST colon, which is why `source` may not
# contain one and `order_number` may: without that asymmetry a source `a:b` with order `c`
# and a source `a` with order `b:c` are one key, and two different orders share one record.
SEPARATOR = ":"


def now() -> str:
    """UTC to the millisecond — `store/master.py:now`'s format, deliberately.

    Not imported from there: this module holds no other dependency on `master` and one
    function's worth of duplication is cheaper than an import that invites a second. The
    FORMAT is what matters, because `pipeline/orders.py:order_sequence` compares
    `placed_at` as a string on the stated grounds that ISO-8601 UTC sorts lexically, and a
    stamp written here in another shape would break that silently.
    """
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class BadOrderKey(ValueError):
    """A source or order number that cannot make an unambiguous key."""


class UnknownOrder(KeyError):
    """A fulfilment recorded against an order this ledger has never ingested."""


class UnknownOrderLine(KeyError):
    """A fulfilment recorded against a SKU that is not a line on that order."""


class DuplicateOrderLine(ValueError):
    """One order carrying two lines with the same SKU.

    REFUSED RATHER THAN MERGED, and refused rather than allowed. Fulfilment is keyed by
    SKU because that is the only line identifier stable across two ingests — a line's
    POSITION in the list is whatever order the feed happened to serialise it in — so two
    lines sharing a SKU make "how many of this have we pulled" a question with two answers
    and no way to tell which one a count belongs to.

    Summing the quantities was the alternative and is worse: a merged line loses which of
    the two was filled, so a partially shipped order reads as one line half done rather
    than as one line done and one not started. A TCGplayer SKU encodes product, printing,
    condition and language, so one order carrying two of them is the feed telling us
    something, and swallowing it is how that stops being visible.
    """


class CopyAlreadyPulled(ValueError):
    """One physical copy recorded against two lines. The failure this module exists for."""


class CopyNotIdentifiable(ValueError):
    """A pull of a copy carrying no `capture_id`, so it cannot be made idempotent."""


class OverFulfilled(ValueError):
    """A pull that would record more copies against a line than the buyer ordered."""


def order_key(source: str, number: str) -> str:
    """`{source}:{order_number}`, folded and stripped to compare, never to store.

    D20's rule for a box name, one register over and for the same reason: `TCGplayer` and
    `tcgplayer` are one marketplace to a person, so they must be one key, and what is
    written down is what the feed actually said. The record keeps `source` and `number`
    verbatim beside the key; only the key is normalised, and only for looking up.

    `source` MAY NOT CONTAIN THE SEPARATOR — see its comment. Both halves must be non-empty,
    because a key with an empty half collides with every other key with an empty half.
    """
    left = str(source).strip()
    right = str(number).strip()
    if not left or not right:
        raise BadOrderKey(f"source {source!r} and number {number!r} must both be non-empty")
    if SEPARATOR in left:
        raise BadOrderKey(
            f"source {left!r} contains {SEPARATOR!r}, which is the key separator — the key "
            f"is split on the FIRST one, so a source carrying it makes two different orders "
            f"share a record. An order NUMBER may contain it."
        )
    return f"{left.casefold()}{SEPARATOR}{right.casefold()}"


@dataclass
class OrderLine:
    """One line of one order, as the feed reported it. FEED-OWNED.

    Replaced wholesale by `ingest`, so nothing this module computes may be stored here.
    `sku` and `quantity` are what the pick turns on; the rest is the feed's own words, kept
    so a screen can show the buyer's description beside the position. None of it is a join
    key and none of it may become one — `CLAUDE.md` forbids joining on a product name
    because that column inconsistently embeds numbers, and the rule is not weaker for being
    one package down.
    """

    sku: str
    quantity: int = 1
    name: Optional[str] = None
    number: Optional[str] = None
    printing: Optional[str] = None
    condition: Optional[str] = None
    rarity: Optional[str] = None
    unit_price: Optional[str] = None
    # `pipeline/orders.py`'s `LINE_KINDS`, unvalidated here on purpose — see the header.
    # None is "the feed said nothing", which the resolver reads as its own default.
    kind: Optional[str] = None


@dataclass
class LineProgress:
    """What WE have recorded against one line. OURS — `ingest` cannot reach it.

    `fulfilled` is the authority and is a COUNT. `copies` is the capture ids of those of
    them we could identify, which is what makes a repeated pull a no-op; it is a SUBSET
    rather than a second spelling of the count, so `fulfilled` may legitimately exceed
    `len(copies)` if a copy is ever recorded without one. `Ledger.record_pull` is the only
    writer of either and moves both together, so the two cannot drift apart there.
    """

    fulfilled: int = 0
    copies: List[str] = field(default_factory=list)
    at: Optional[str] = None


@dataclass
class OrderRecord:
    """One order: what the feed said about it. Its fulfilment lives in the other map."""

    source: str
    number: str
    placed_at: Optional[str] = None
    # THE FEED'S OWN WORD, VERBATIM AND UNVALIDATED. A closed vocabulary here would refuse
    # a marketplace that learned a new status, and deciding what "open" means from a
    # marketplace's status string is the guessing `CLAUDE.md` forbids. `Ledger.unfulfilled`
    # answers the question this ledger actually owns — which orders still owe copies —
    # out of its own two halves rather than out of somebody else's noun.
    status: Optional[str] = None
    lines: List[OrderLine] = field(default_factory=list)
    # THE ONE FIELD `ingest` PRESERVES rather than replaces, and the header says why it is
    # allowed to be an exception: losing a date is cosmetic. `Queue.upsert` preserves
    # `first_seen` for the same reason and by the same mechanism.
    first_seen: str = ""
    # Stamped only where an ingest found the feed's content DIFFERENT — never on a sync
    # that learned nothing, which is what keeps an unchanged re-ingest byte-identical.
    changed_at: Optional[str] = None

    @property
    def key(self) -> str:
        return order_key(self.source, self.number)

    @property
    def wanted(self) -> int:
        return sum(max(0, int(line.quantity)) for line in self.lines)

    def line_for(self, sku) -> Optional[OrderLine]:
        wanted = str(sku).strip()
        for line in self.lines:
            if str(line.sku).strip() == wanted:
                return line
        return None

    @property
    def _content(self) -> tuple:
        """What `ingest` compares to decide whether the feed said anything new.

        Every feed-owned field and nothing else. `first_seen` and `changed_at` are excluded
        because they are answers to this comparison — including them would make every
        record differ from itself and restamp the file on every sync, which is the failure
        this comparison exists to prevent.
        """
        return (
            self.source,
            self.number,
            self.placed_at,
            self.status,
            tuple(
                (
                    line.sku,
                    line.quantity,
                    line.name,
                    line.number,
                    line.printing,
                    line.condition,
                    line.rarity,
                    line.unit_price,
                    line.kind,
                )
                for line in self.lines
            ),
        )


@dataclass
class IngestReport:
    """What one sync did. Counts, so a caller can say it out loud without re-deriving it."""

    added: int = 0
    changed: int = 0
    unchanged: int = 0

    @property
    def total(self) -> int:
        return self.added + self.changed + self.unchanged

    @property
    def wrote_nothing(self) -> bool:
        """True when this sync learned nothing — the second press of the button."""
        return self.added == 0 and self.changed == 0

    @property
    def summary(self) -> str:
        return (
            f"{self.total} order(s): {self.added} new, {self.changed} changed, "
            f"{self.unchanged} unchanged"
        )


@dataclass
class Ledger:
    """`orders.json`. Two maps, and the split between them is the guard — see the header."""

    orders: Dict[str, OrderRecord] = field(default_factory=dict)
    fulfilment: Dict[str, Dict[str, LineProgress]] = field(default_factory=dict)

    # ------------------------------------------------------------------ (de)serialising

    @classmethod
    def parse(cls, payload: Optional[dict]) -> "Ledger":
        """Rebuild from JSON, dropping every field the dataclasses do not declare.

        `__annotations__` FILTERING AT ALL THREE LEVELS, and the reason is the one
        `store/master.py:parse` records: a field written but not declared is served,
        persisted, and SILENTLY DROPPED on the next reload, so the value looks live right
        up until the process restarts. `OrderLine` and `LineProgress` are nested, so
        filtering only the record would let exactly that through one level down.

        A record that cannot be constructed is SKIPPED rather than raising, which is
        `Queue.parse`'s rule: one malformed order must not take the whole ledger — and with
        it every other order's fulfilment count — off the screen.
        """
        payload = payload or {}
        orders: Dict[str, OrderRecord] = {}
        fulfilment: Dict[str, Dict[str, LineProgress]] = {}

        for key, record in (payload.get("orders") or {}).items():
            if str(key).startswith("_"):
                continue
            known = {k: v for k, v in record.items() if k in OrderRecord.__annotations__}
            lines = []
            for raw in known.get("lines") or []:
                fields = {k: v for k, v in raw.items() if k in OrderLine.__annotations__}
                try:
                    lines.append(OrderLine(**fields))
                except TypeError:
                    continue
            known["lines"] = lines
            try:
                orders[str(key)] = OrderRecord(**known)
            except TypeError:
                continue

        for key, per_sku in (payload.get("fulfilment") or {}).items():
            if str(key).startswith("_"):
                continue
            rows: Dict[str, LineProgress] = {}
            for sku, raw in (per_sku or {}).items():
                fields = {k: v for k, v in raw.items() if k in LineProgress.__annotations__}
                try:
                    rows[str(sku)] = LineProgress(**fields)
                except TypeError:
                    continue
            if rows:
                fulfilment[str(key)] = rows

        return cls(orders=orders, fulfilment=fulfilment)

    def to_payload(self) -> dict:
        return {
            "version": VERSION,
            "orders": {key: asdict(record) for key, record in sorted(self.orders.items())},
            "fulfilment": {
                key: {sku: asdict(row) for sku, row in sorted(rows.items())}
                for key, rows in sorted(self.fulfilment.items())
            },
        }

    def __len__(self) -> int:
        return len(self.orders)

    # ------------------------------------------------------------------------- the feed

    def ingest(self, records: Iterable[OrderRecord]) -> IngestReport:
        """Upsert what the feed said. Writes NOTHING else — see the header's second rule.

        It touches `self.orders` and nothing further: not a card, not a listing count, not
        `self.fulfilment`. Re-ingesting an unchanged order is therefore a no-op down to the
        byte, which is what makes pressing sync twice safe by construction rather than by a
        guard.

        `first_seen` is carried across from the incumbent, and `changed_at` is stamped only
        where the content actually moved.
        """
        report = IngestReport()
        for record in records:
            key = record.key
            existing = self.orders.get(key)
            self._check_lines_unique(record)

            if existing is None:
                record.first_seen = record.first_seen or today()
                record.changed_at = record.changed_at or now()
                self.orders[key] = record
                report.added += 1
                continue

            if record._content == existing._content:
                # Nothing new. The incumbent is left exactly as it is — not re-assigned,
                # not re-stamped — so this file's bytes do not move.
                report.unchanged += 1
                continue

            record.first_seen = existing.first_seen or record.first_seen or today()
            record.changed_at = now()
            self.orders[key] = record
            report.changed += 1
        return report

    @staticmethod
    def _check_lines_unique(record: OrderRecord) -> None:
        seen = set()
        for line in record.lines:
            sku = str(line.sku).strip()
            if sku in seen:
                raise DuplicateOrderLine(
                    f"order {record.key} carries two lines for SKU {sku!r}; fulfilment is "
                    f"keyed by SKU, so a count against it would have two owners"
                )
            seen.add(sku)

    # -------------------------------------------------------------------- the fulfilment

    def progress(self, key: str, sku) -> LineProgress:
        """This line's progress, creating an empty one only when asked to WRITE.

        Read-only callers want `recorded` below, which invents nothing. This one is the
        writer's accessor and is why `to_payload` prunes: a `fulfilment` entry that exists
        because somebody looked at it is a row claiming a pull that never happened.
        """
        return self.fulfilment.setdefault(str(key), {}).setdefault(str(sku).strip(), LineProgress())

    def recorded(self, key: str, sku) -> LineProgress:
        """This line's progress, or an empty one that is NOT stored. Never writes."""
        return self.fulfilment.get(str(key), {}).get(str(sku).strip(), LineProgress())

    def fulfilled(self, key: str, sku) -> int:
        return int(self.recorded(key, sku).fulfilled)

    def outstanding(self, key: str, sku) -> int:
        """How many copies this line still owes. Floors at zero — see `over` below."""
        record = self.orders.get(str(key))
        line = record.line_for(sku) if record else None
        if line is None:
            return 0
        return max(0, int(line.quantity) - self.fulfilled(key, sku))

    def over(self, key: str, sku) -> int:
        """How many copies beyond the order this line has recorded. Normally zero.

        `record_pull` REFUSES TO CREATE THIS and this property still exists, because the
        two are different questions. A pull cannot over-fill a line — `OverFulfilled` —
        but a later ingest can REDUCE the quantity underneath a pull that was legitimate
        when it was made, and that state has to be readable rather than a crash. Refuse to
        create it, tolerate and report it where it arises.
        """
        record = self.orders.get(str(key))
        line = record.line_for(sku) if record else None
        if line is None:
            return 0
        return max(0, self.fulfilled(key, sku) - int(line.quantity))

    def holder_of(self, capture_id: str) -> Optional[Tuple[str, str]]:
        """`(order key, sku)` this copy is already recorded against, or None.

        The index behind `CopyAlreadyPulled`. Walked rather than cached: this ledger holds
        one record per order rather than per card, so the walk is over open orders and not
        over the store, and a cached reverse index is a second thing to keep true through
        every write for no measured gain.
        """
        wanted = str(capture_id).strip()
        for key, rows in self.fulfilment.items():
            for sku, row in rows.items():
                if wanted in row.copies:
                    return (key, sku)
        return None

    def record_pull(self, key: str, sku, capture_ids: Sequence[str]) -> int:
        """Record physical copies against one line. Returns how many were NEWLY recorded.

        IDEMPOTENT BY CONSTRUCTION rather than by a caller checking first: a capture id
        already on this line is skipped, so recording the same pull twice records nothing
        and returns 0. That is the same promise `ingest` makes one map over, and it is made
        the same way — by the operation being unable to do the wrong thing rather than by a
        flag saying it must not.

        FOUR REFUSALS, EACH OF WHICH IS A DIFFERENT WAY TO SHIP THE WRONG CARD:

          `UnknownOrder`        nothing to fulfil. A pull against an order the ledger has
                                never ingested is a screen and a store that disagree, and
                                inventing the order here would put a shipment on record for
                                a purchase nobody can produce.
          `UnknownOrderLine`    the buyer did not order this SKU. Keyed by SKU because that
                                is the only line identity stable across two ingests — see
                                `DuplicateOrderLine`.
          `CopyNotIdentifiable` a copy with no `capture_id`. Refused rather than counted
                                blind: without an identity the pull cannot be made
                                idempotent, and a silent double-pull is the worst outcome
                                this whole feature has. Every record on the owner's store
                                carries one, so this is a guard against a legacy card
                                rather than a common path.
          `CopyAlreadyPulled`   this exact physical card is already recorded against
                                another line. The thing the module exists to prevent, said
                                out loud rather than counted twice.

        `OverFulfilled` is the fifth and is about the LINE rather than about a copy:
        recording four copies against an order for three is a mistake, and there is nothing
        to be gained by clamping it silently — you cannot ship the fourth.

        VALIDATE EVERYTHING, THEN WRITE EVERYTHING, which is D29's rule for the group
        answer and is the reason the loops below are separate. A refusal partway through
        would leave some copies recorded against a pull the operator was told had failed,
        and the ledger would then be the only record that they had gone.
        """
        key = str(key)
        record = self.orders.get(key)
        if record is None:
            raise UnknownOrder(f"{key!r} is not in this ledger")
        line = record.line_for(sku)
        if line is None:
            raise UnknownOrderLine(
                f"order {key} has no line for SKU {str(sku).strip()!r}; it ordered "
                f"{', '.join(str(l.sku) for l in record.lines) or 'nothing'}"
            )

        row = self.recorded(key, sku)
        fresh: List[str] = []
        for raw in capture_ids:
            copy = str(raw).strip() if raw is not None else ""
            if not copy:
                raise CopyNotIdentifiable(
                    f"a copy pulled for order {key} SKU {line.sku} carries no capture_id, "
                    f"so this pull cannot be made idempotent and is refused. A capture id "
                    f"is minted per POST /capture and every record on this store has one."
                )
            if copy in row.copies or copy in fresh:
                # Already recorded against THIS line. The repeated press: skipped, not
                # refused, because the operator's intent has already been honoured.
                continue
            held = self.holder_of(copy)
            if held is not None:
                raise CopyAlreadyPulled(
                    f"capture_id {copy!r} is already recorded against order {held[0]} "
                    f"SKU {held[1]}; recording it again for {key} would send the same "
                    f"physical card to two buyers"
                )
            fresh.append(copy)

        if not fresh:
            return 0

        if int(row.fulfilled) + len(fresh) > int(line.quantity):
            raise OverFulfilled(
                f"order {key} ordered {line.quantity} of SKU {line.sku} and has "
                f"{row.fulfilled} recorded; {len(fresh)} more would be "
                f"{int(row.fulfilled) + len(fresh)}"
            )

        stored = self.progress(key, sku)
        stored.copies.extend(fresh)
        stored.fulfilled = int(stored.fulfilled) + len(fresh)
        stored.at = now()
        return len(fresh)

    def forget_pull(self, key: str, sku, capture_ids: Sequence[str]) -> int:
        """Take copies back off a line. Returns how many were actually removed.

        `record_pull`'s reversal and nothing wider. It removes only ids that are recorded
        against THIS line — an id that is not there is skipped rather than refused, which is
        the same asymmetry `record_pull` applies to a repeated press, and for the same
        reason: a reversal of something that already is not there has nothing left to do.

        IT MOVES `fulfilled` AND `copies` TOGETHER, floored at zero. Nothing else in this
        module may write either, so those two numbers cannot come apart anywhere but here.

        NO WINDOW AND NO CLOCK, which is `Queue.reopen`'s ruling: how long an undo stays
        offered is the screen's business — `app/src/Fulfillment.tsx` decides it for
        mark-sold — because a deadline enforced down here fails the reversal precisely when
        the store is slow to lock, and a ledger file has no way to know what time the tap
        was in any case.
        """
        key = str(key)
        row = self.fulfilment.get(key, {}).get(str(sku).strip())
        if row is None:
            return 0
        wanted = {str(c).strip() for c in capture_ids if c is not None and str(c).strip()}
        going = [copy for copy in row.copies if copy in wanted]
        if not going:
            return 0
        row.copies = [copy for copy in row.copies if copy not in wanted]
        row.fulfilled = max(0, int(row.fulfilled) - len(going))
        row.at = now()
        return len(going)

    # -------------------------------------------------------------------------- reading

    def get(self, key: str) -> Optional[OrderRecord]:
        return self.orders.get(str(key))

    def find(self, source: str, number: str) -> Optional[OrderRecord]:
        try:
            return self.orders.get(order_key(source, number))
        except BadOrderKey:
            return None

    def unfulfilled(self) -> List[OrderRecord]:
        """Every order still owing at least one copy, oldest first.

        THE LEDGER'S OWN QUESTION, computed from its own two halves rather than read off
        the feed's `status` string. Ordered the way `pipeline/orders.py:order_sequence`
        serves them — oldest `placed_at` first, then the key, with a missing stamp sorting
        LAST rather than first, because claiming an undated order is the oldest would hand
        it stock ahead of one we know is older. The two orderings agree on purpose: a
        screen listing what is outstanding and a resolver deciding who gets the last copy
        must not disagree about which order comes first.
        """
        out = [
            record
            for key, record in self.orders.items()
            if any(self.outstanding(key, line.sku) > 0 for line in record.lines)
        ]
        return sorted(
            out, key=lambda r: (r.placed_at is None, r.placed_at or "", r.key)
        )

    @property
    def summary(self) -> str:
        owing = len(self.unfulfilled())
        if not self.orders:
            return "0 orders"
        return f"{len(self.orders)} orders, {owing} still owing copies"
