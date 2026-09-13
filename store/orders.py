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

A NAME, AND NOTHING ELSE ABOUT A PERSON (D-the-ledger-names-the-buyer). The ledger holds
what is needed to pick and pack — a SKU, a quantity, what the feed called the card — plus
one more field: the buyer's DISPLAY NAME, because the owner walks drawers per *person* and
a number with no name on it cannot be walked that way. This was an exclusion this repo drew
on its own (D63/D69), never an owner ruling, and the owner's own ruling narrows rather than
repeals it: address, email, payment and the transaction breakdown stay out, by the same
allowlist mechanism this file has always used — `server/order_transport.py:project_*`
projects `buyerName` through and drops everything else exactly as before, and
`server/capture_server.py`'s three tuples still refuse `buyerName`'s siblings by name.
`inventory/` is gitignored whole, which is a reason to keep bearer instruments out of a
commit (`store/files.py`'s code ledger) and not a licence to accumulate somebody's postal
address on this disk — a display name is not a bearer instrument and an address is.

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

from store.rows import Rows, TableSpec

FILENAME = "orders.json"

VERSION = 1

# WHY A HAND-FILL MUST SAY WHICH KIND IT IS. `record_fill` closes a line with no physical
# card behind it, which is the one write in this module that cannot be checked against
# anything — there is no `capture_id` to collide, no photograph, no slot. The reason is
# therefore the whole audit trail, and a free-text box would make it prose nobody greps.
#
# TWO WORDS, AND THE THIRD ONE IS DELIBERATELY ABSENT. A refunded or cancelled line also
# stops owing copies, and closing it through here would spell "we shipped this" for a line
# nothing shipped — `fulfilled` is the count of copies that WENT, and overloading it is how
# a ledger stops being able to answer what left the building. That case wants its own state
# and it is named in D113 as a reopening rather than squeezed in here.
FILL_SEALED = "sealed"          # not a single: picked off a shelf and shipped by hand
FILL_OFF_SYSTEM = "off_system"  # a single this store never photographed
# THE COPY WAS HERE AND LEFT BY THE WRONG DOOR. Measured 2026-09-06: mark one copy sold on
# `#/inventory` while an order wants three, pull the other two through the walk, and the line
# ends at `fulfilled` 2, `outstanding` 1, `no_copies_on_hand` — open forever, with the third
# copy in the envelope. `#/inventory`'s sale does not touch the ledger (D63 keeps them apart,
# rightly: a sale is a fact about a card and a fulfilment is a fact about an order), so
# nothing counted it. NOT `off_system`, which means this store never photographed the card at
# all; this one it did, and the two want telling apart by whoever reads the row later.
FILL_SOLD_SEPARATELY = "sold_separately"
FILL_REASONS = (FILL_SEALED, FILL_OFF_SYSTEM, FILL_SOLD_SEPARATELY)

# WHY A LINE CAN STOP OWING WITHOUT ANYTHING BEING FILLED. A fill says copies WENT and adds
# to the count; a stand-down says this store is not going to account for them at all, and
# touches no count. The two are not interchangeable and the 2026-09-06 measurement is why:
# 69 of the owner's 83 open orders were ones TCGplayer had already shipped, and many shipped
# using copies that are STILL in the store as `identified` — hand-filling those would claim
# a copy went while leaving the card on the shelf to be offered to the next buyer. What they
# need is to stop being tracked, which is a different sentence.
#
# `not_shipping` IS THE CASE `record_fill` REFUSES TO SPELL. A refund or a cancellation
# stops a line owing without a copy going anywhere, and closing it through `fulfilled` would
# put a shipment on record for one that never happened. It belongs here, where nothing is
# counted, and D113 records that this is where it went.
CLOSE_SHIPPED_ELSEWHERE = "shipped_elsewhere"  # it went out; this store did not track it
CLOSE_NOT_SHIPPING = "not_shipping"            # refunded, cancelled — nothing will go
CLOSE_REASONS = (CLOSE_SHIPPED_ELSEWHERE, CLOSE_NOT_SHIPPING)

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
    `len(copies)` if a copy is ever recorded without one.

    A COPY IS RECORDED WITHOUT ONE BY `record_fill`, AND `by_hand` IS HOW MANY. The sentence
    above anticipated this from the beginning and nothing wrote it until 2026-09-06, which
    left three real orders permanently open — a sealed Holiday Calendar, a sealed Double Pack
    Set and a $404 single this store never photographed. None of them can ever have a
    `capture_id`, so `record_pull` — which requires one, for reasons that are right — could
    never close them, and no other writer existed. See D113.

    THE INVARIANT IS `fulfilled == len(copies) + by_hand`, and FOUR methods maintain it:
    `record_pull` and `forget_pull` move `fulfilled` with `copies`, `record_fill` and
    `forget_fill` move it with `by_hand`. Nothing else in this module writes any of the
    three, so they can only come apart in those four places — the same property the two-map
    split gives the file as a whole, one register down. `Ledger.progress_drift` reports any
    row where it does not hold, and T7 asserts that report is empty.

    `reason` SAYS WHY A HAND-FILL WAS HONEST and is never inferred. `kind` is the operator's
    own classification of the line, and it lives HERE rather than on `OrderLine` for the
    reason this whole map exists: `ingest` replaces an order record wholesale, so a kind
    written onto the feed's copy is destroyed by the next sync that sees any change — which
    is the defect the header describes for a fulfilment count, in a second currency.
    """

    fulfilled: int = 0
    copies: List[str] = field(default_factory=list)
    at: Optional[str] = None
    # Left unvalidated here on purpose, exactly as `OrderLine.kind` is and for the header's
    # reason: this module is a document. The door validates — `server/capture_server.py`
    # refuses a reason outside `FILL_REASONS` and a kind outside `LINE_KINDS` before either
    # reaches a write.
    by_hand: int = 0
    reason: Optional[str] = None
    kind: Optional[str] = None
    # THE STAND-DOWN, AND IT IS NOT A COUNT. `closed_at` set means this line needs nothing
    # further from this store even though `outstanding` may still be positive — the copies
    # are not claimed to have gone, they are simply no longer this store's to account for.
    # Derived `closed` rather than a second boolean, so a flag and a stamp cannot disagree.
    closed_at: Optional[str] = None
    closed_reason: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        """Whether this row records nothing at all.

        A row in this state is indistinguishable from no row — `recorded` invents an empty
        one for a caller that asks about a line nobody has touched — so keeping it is pure
        cost, and `progress`'s own docstring calls it what it is: a row claiming a pull that
        never happened. The reversals below drop one rather than leave it.

        `at` IS NOT READ HERE, deliberately. It is the stamp of whatever last happened, and a
        row whose every fact has been reversed is empty however recently it was emptied.
        """
        return (
            int(self.fulfilled) == 0
            and int(self.by_hand) == 0
            and not self.copies
            and self.kind is None
            and self.closed_at is None
        )

    @property
    def closed(self) -> bool:
        """Whether this line has been stood down. Derived, never stored.

        A stored boolean beside the stamp is two answers to one question, and the pair goes
        out of step the first time somebody clears one of them.
        """
        return self.closed_at is not None


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
    # THE ONE FACT ABOUT A PERSON THIS LEDGER HOLDS (D-the-ledger-names-the-buyer). A
    # display name, feed-owned exactly like `status` — it lives in `_content`, a change
    # stamps `changed_at`, and `ingest` replaces it wholesale on every sync. `None` means
    # the feed said nothing THIS TIME, which a paste routinely does; `Ledger.ingest` carries
    # the incumbent's name across in that case rather than erasing one the fetch wrote — see
    # its own docstring for why that carry-over is not the same rule as `first_seen`'s.
    buyer: Optional[str] = None
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
            self.buyer,
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


def _parse_order(key, record) -> Optional[OrderRecord]:
    """One order from its stored record, or None for one that will not construct.
    `__annotations__` filtering at both levels — see `Ledger.parse`."""
    if str(key).startswith("_") or not isinstance(record, dict):
        return None
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
        return OrderRecord(**known)
    except TypeError:
        return None


def _parse_fulfilment(key, per_sku) -> Optional[Dict[str, LineProgress]]:
    """One order's per-SKU progress map, or None where nothing constructs."""
    if str(key).startswith("_") or not isinstance(per_sku, dict):
        return None
    rows: Dict[str, LineProgress] = {}
    for sku, raw in per_sku.items():
        fields = {k: v for k, v in raw.items() if k in LineProgress.__annotations__}
        try:
            rows[str(sku)] = LineProgress(**fields)
        except TypeError:
            continue
    return rows or None


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
class NameReport:
    """What one names-only backfill did. `IngestReport`'s shape, one register narrower.

    `named` and `unchanged` between them account for every order this ledger already holds;
    `unknown` is an order the caller named that this ledger has never ingested — counted
    rather than silently dropped, and NEVER created (`name_buyer` refuses to). A backfill
    that raced ahead of an ingest, or a stray number in a hand-typed list, both land here
    rather than minting a placeholder order with a name and no lines.
    """

    named: int = 0
    unchanged: int = 0
    unknown: int = 0

    @property
    def total(self) -> int:
        return self.named + self.unchanged + self.unknown

    @property
    def summary(self) -> str:
        return (
            f"{self.total} name(s): {self.named} named, {self.unchanged} unchanged, "
            f"{self.unknown} unknown"
        )


@dataclass
class Ledger:
    """Two maps, and the split between them is the guard — see the header. `orders.json`
    until D88; the `orders` and `fulfilment` tables of `store.sqlite` since."""

    orders: "Rows" = field(default_factory=lambda: Rows(Ledger.ORDERS))
    fulfilment: "Rows" = field(default_factory=lambda: Rows(Ledger.FULFILMENT))

    # THE TWO TABLES (D88), and the split the header argues survives the move exactly:
    # `ingest` still cannot name `fulfilment`, because it is a different mapping bound to
    # a different table. A fulfilment row is one order's whole per-SKU map, which is the
    # unit `record_pull` reads and writes.
    ORDERS = TableSpec(
        "orders",
        parse=lambda key, record: _parse_order(key, record),
        dump=asdict,
        columns=lambda record: {
            "source": record.source,
            "number": record.number,
            "status": record.status,
        },
        column_names=("source", "number", "status"),
    )
    FULFILMENT = TableSpec(
        "fulfilment",
        parse=lambda key, record: _parse_fulfilment(key, record),
        dump=lambda rows: {sku: asdict(row) for sku, row in sorted(rows.items())},
        columns=lambda rows: {},
        column_names=(),
    )

    def __post_init__(self) -> None:
        if not isinstance(self.orders, Rows):
            self.orders = Rows(Ledger.ORDERS, objects=dict(self.orders))
        if not isinstance(self.fulfilment, Rows):
            self.fulfilment = Rows(Ledger.FULFILMENT, objects=dict(self.fulfilment))

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
            parsed = _parse_order(key, record)
            if parsed is not None:
                orders[str(key)] = parsed

        for key, per_sku in (payload.get("fulfilment") or {}).items():
            rows = _parse_fulfilment(key, per_sku)
            if rows:
                fulfilment[str(key)] = rows

        return cls(
            orders=Rows(cls.ORDERS, objects=orders),
            fulfilment=Rows(cls.FULFILMENT, objects=fulfilment),
        )

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

        TWO FIELDS ARE CARRIED ACROSS FROM THE INCUMBENT, NOT ONE — this docstring and D63
        both said exactly one until D-the-ledger-names-the-buyer, and both were wrong the
        moment `buyer` existed to carry. `first_seen` is carried because losing a date is
        cosmetic; `buyer` is carried under one narrower condition — only when the INCOMING
        record says nothing at all (`record.buyer is None`) — because a hand-typed paste
        routinely omits a name the fetch already wrote, and a paste that erased it would
        undo the one thing the backfill exists to do. A fetch that DOES carry a name still
        overwrites, same as `status` or any other feed-owned field: the feed is the
        authority whenever it speaks.

        `changed_at` is stamped only where the content actually moved.
        """
        report = IngestReport()
        for record in records:
            key = record.key
            existing = self.orders.get(key)
            self._check_lines_unique(record)

            if existing is not None and record.buyer is None:
                record.buyer = existing.buyer

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

    def name_buyer(self, source: str, number: str, buyer: str) -> str:
        """Attach a buyer's display name to an order this ledger already holds.

        RETURNS ONE OF THREE WORDS RATHER THAN RAISING, because a caller of this method is
        almost always working a LIST — `POST /orders/names` sends up to
        `ORDER_NAMES_LIMIT` at once — and a name against an order that shipped last month or
        was never fetched here is not a defect in the request, it is an ordinary fact about
        a backfill running against a moving ledger. `"unknown"` says so rather than raising
        and abandoning the rest of the batch.

        REFUSES TO CREATE AN ORDER, on the same ground `record_pull` and `record_fill`
        refuse to: an order minted from a name-and-number pair with no lines behind it is a
        purchase nobody can pick, and it would sit in `self.orders` forever answering
        `wanted == 0` to every reader that assumes an order has at least one line.

        `"unchanged"` when the stored name already equals what was sent, stripped — the same
        byte-identical-on-a-repeat promise `ingest` makes, because the steady-state press
        (D-the-ledger-names-the-buyer's `POST /orders/fetch` `names` list) is built to send
        exactly the orders that would NOT be unchanged, but a hand-built list or a race with
        a concurrent fetch can still repeat one, and a repeat must cost nothing.

        A NAME CHANGE STAMPS `changed_at`, because `buyer` is `_content` now and this is the
        same fact `ingest` would have written had the feed said it first — the two writers
        share one field and must agree about what moving it means.
        """
        try:
            key = order_key(source, number)
        except BadOrderKey:
            return "unknown"
        record = self.orders.get(key)
        if record is None:
            return "unknown"
        said = str(buyer).strip() or None
        if record.buyer == said:
            return "unchanged"
        record.buyer = said
        record.changed_at = now()
        return "named"

    def name_buyers(self, names: Sequence[Tuple[str, str, str]]) -> NameReport:
        """`name_buyer` over a list, mirroring `ingest`'s one-report-for-the-batch shape."""
        report = NameReport()
        for source, number, buyer in names:
            outcome = self.name_buyer(source, number, buyer)
            if outcome == "named":
                report.named += 1
            elif outcome == "unchanged":
                report.unchanged += 1
            else:
                report.unknown += 1
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
                f"{', '.join(str(each.sku) for each in record.lines) or 'nothing'}"
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

    # ------------------------------------------------------------------- the hand-fill

    def _line_or_raise(self, key: str, sku):
        """The line `key`/`sku` names, or the refusal saying which half was wrong.

        Lifted out of `record_pull` rather than copied into the three writers below: the two
        refusals are the same two, and a second spelling of `UnknownOrderLine`'s message is
        a second thing to keep true.
        """
        record = self.orders.get(str(key))
        if record is None:
            raise UnknownOrder(f"{str(key)!r} is not in this ledger")
        line = record.line_for(sku)
        if line is None:
            raise UnknownOrderLine(
                f"order {key} has no line for SKU {str(sku).strip()!r}; it ordered "
                f"{', '.join(str(each.sku) for each in record.lines) or 'nothing'}"
            )
        return line

    def record_fill(self, key: str, sku, count: int, reason: str) -> int:
        """Close `count` copies of a line with NO physical card behind them. Returns `count`.

        THE WRITE `record_pull` CANNOT MAKE, AND THE ONE THREE REAL ORDERS NEEDED. That
        method requires a `capture_id` per copy and is right to: a pull moves a card this
        store holds, and an unidentifiable one is a double-shipment waiting to happen. But a
        sealed Holiday Calendar has no card record and never will, and neither has a single
        that shipped from a pile this rig never photographed — so the line could not be
        closed at all, and the order stayed open forever with nothing on any screen able to
        move it. See D113.

        NOT IDEMPOTENT, AND THAT IS THE HONEST SHAPE. `record_pull` is idempotent because a
        `capture_id` is an identity — pressing twice names the same physical card, so the
        second press is nothing. A hand-fill has no identity to compare: two presses are two
        claims about two copies, and there is no fact in the store that can tell a repeat
        from a genuine second copy. So it ADDS, `OverFulfilled` is the ceiling that stops it
        running away, and the reversal below is what a mis-press is undone with. A screen
        that wants press-once semantics gets them by showing what is already recorded, which
        `_order_progress` already ships.

        THREE REFUSALS:

          `UnknownOrder`      nothing to fill. Inventing the order here would put a shipment
                              on record for a purchase nobody can produce — `record_pull`'s
                              own words, and the same hazard.
          `UnknownOrderLine`  the buyer did not order this SKU.
          `OverFulfilled`     recording more than the line ordered. NOT CLAMPED, for
                              `record_pull`'s reason: you cannot ship the fourth.

        A count of zero or less is refused too, and as a `ValueError` rather than a silent
        no-op: nothing on a screen should ever ask for it, so one arriving is a caller bug
        and swallowing it would hide the bug rather than the press.
        """
        count = int(count)
        if count <= 0:
            raise ValueError(f"a hand-fill records at least one copy; got {count}")
        line = self._line_or_raise(key, sku)

        row = self.recorded(key, sku)
        if int(row.fulfilled) + count > int(line.quantity):
            raise OverFulfilled(
                f"order {key} ordered {line.quantity} of SKU {line.sku} and has "
                f"{row.fulfilled} recorded; {count} more would be "
                f"{int(row.fulfilled) + count}"
            )

        stored = self.progress(key, sku)
        stored.fulfilled = int(stored.fulfilled) + count
        stored.by_hand = int(stored.by_hand) + count
        stored.reason = str(reason).strip() or None
        stored.at = now()
        return count

    def forget_fill(self, key: str, sku, count: int) -> int:
        """Take `count` hand-filled copies back off a line. Returns how many were removed.

        `record_fill`'s reversal, and it can only reach `by_hand`. A line carrying two pulled
        copies and one hand-filled one reverses to two pulled copies — never to one pulled
        and one hand-filled — because the two counts name different acts and this method
        knows only its own. Reversing a PULL is `forget_pull`, which needs the capture ids.

        CLAMPED RATHER THAN REFUSED, which is `forget_pull`'s asymmetry: asking to reverse
        more than is there reverses what is there. A reversal of something that already is
        not there has nothing left to do.

        `reason` IS CLEARED ONLY WHEN THE LAST ONE GOES. It describes the hand-fills on this
        line, so it outlives a partial reversal and dies with the last copy it explained.
        """
        count = int(count)
        row = self.fulfilment.get(str(key), {}).get(str(sku).strip())
        if row is None or count <= 0:
            return 0
        going = min(count, int(row.by_hand))
        if going <= 0:
            return 0
        row.by_hand = int(row.by_hand) - going
        row.fulfilled = max(0, int(row.fulfilled) - going)
        if row.by_hand == 0:
            row.reason = None
        row.at = now()
        self._drop_if_empty(key, sku)
        return going

    # ------------------------------------------------------------- the operator's claim

    def declare_kind(self, key: str, sku, kind: Optional[str]) -> None:
        """Record what the OPERATOR says this line is. `None` withdraws the claim.

        IT LIVES IN THIS MAP AND NOT ON `OrderLine`, and that is the header's own argument
        rather than a preference. `ingest` replaces an order record wholesale on any content
        change, so a kind written onto the feed's copy survives exactly until the marketplace
        moves the status string — at which point a sealed product silently becomes a single
        again and starts sending the picker to look for it in the boxes. The feed's `kind`
        stays where it is and stays the feed's; this is ours, and `ingest` cannot reach it
        for the same structural reason it cannot reach a count.

        UNVALIDATED HERE, VALIDATED AT THE DOOR — `OrderLine.kind`'s rule exactly, and the
        same one: a closed vocabulary in a document refuses a feed that learned a new product
        category, while an unknown kind stored through the server raises at RESOLVE time and
        takes the whole order screen down for one bad write.

        A ROW THAT EXISTS ONLY FOR THIS CLAIMS NO PULL. `progress`'s docstring warns that a
        row created by somebody looking at it is a row claiming a pull that never happened —
        this one carries `fulfilled` 0 and `by_hand` 0 and claims a classification, which is
        a thing the operator did say.
        """
        claimed = str(kind).strip() if kind is not None else ""
        self._line_or_raise(key, sku)
        if not claimed:
            row = self.fulfilment.get(str(key), {}).get(str(sku).strip())
            if row is not None:
                row.kind = None
                self._drop_if_empty(key, sku)
            return
        self.progress(key, sku).kind = claimed

    def declared_kind(self, key: str, sku) -> Optional[str]:
        """The operator's claim about this line, or None. Never the feed's."""
        return self.recorded(key, sku).kind

    def _drop_if_empty(self, key: str, sku) -> None:
        """Delete a row that has come to record nothing, and the order's map with it.

        CALLED BY EVERY REVERSAL, and it is not tidiness. A stand-down that is undone would
        otherwise leave one all-default row per line behind — measured at 80 rows from a
        single bulk close and its undo — and `_parse_fulfilment` faithfully reloads every one
        of them on the next open. `recorded` already answers for a line with no row, so these
        carry no information and cost a store lock's worth of writing on every save.
        """
        key = str(key)
        rows = self.fulfilment.get(key)
        if rows is None:
            return
        sku = str(sku).strip()
        row = rows.get(sku)
        if row is None or not row.is_empty:
            return
        del rows[sku]
        if not rows:
            del self.fulfilment[key]

    def close_line(self, key: str, sku, reason: str) -> bool:
        """Stand one line down: it needs nothing further from this store. Returns whether
        anything moved.

        NOT A FILL, AND THE DISTINCTION IS THE ENTRY. `record_fill` adds to `fulfilled` and
        says copies WENT; this touches no count and says only that this store is no longer
        accounting for them. Measured 2026-09-06 on the owner's store: 69 of 83 open orders
        were already shipped by TCGplayer, and many of them shipped using copies still
        sitting in the boxes as `identified`. Hand-filling those would have claimed a copy
        went while leaving the card on the shelf for the next buyer — the count would read
        right and the store would be wrong.

        IT IS PER LINE BECAUSE THE RESOLVER IS. An order-level flag would be a second place
        that decides whether a line is live, and `Ledger.unfulfilled` already walks lines;
        a caller standing a whole order down calls this once per line, which is what
        `server/capture_server.py:do_order_close` does inside one write.

        IDEMPOTENT, AND IT DOES NOT RE-STAMP. Closing a line that is already closed changes
        nothing and returns False, so a repeated press does not move `closed_at` — the
        stamp answers "when did this stop being ours", and a second press is not a second
        answer to it. A DIFFERENT reason does re-stamp: that is a correction, not a repeat.

        The two refusals are `record_fill`'s and for the same reasons.
        """
        line = self._line_or_raise(key, sku)
        said = str(reason).strip()
        row = self.recorded(key, sku)
        if row.closed and row.closed_reason == said:
            return False
        stored = self.progress(key, sku)
        stored.closed_at = now()
        stored.closed_reason = said or None
        # `line` is read for the refusals above and deliberately not used to change a count.
        del line
        return True

    def reopen_line(self, key: str, sku) -> bool:
        """Undo a stand-down. Returns whether anything moved.

        `close_line`'s reversal and nothing wider — it cannot touch a count, so reopening a
        line that was also hand-filled leaves the fill exactly where it was. Reversing THAT
        is `forget_fill`.

        NO WINDOW AND NO CLOCK, which is `forget_pull`'s ruling: how long an undo stays
        offered is the screen's business.
        """
        row = self.fulfilment.get(str(key), {}).get(str(sku).strip())
        if row is None or not row.closed:
            return False
        row.closed_at = None
        row.closed_reason = None
        self._drop_if_empty(key, sku)
        return True

    def closed_lines(self, key: str) -> int:
        """How many of one order's lines are stood down. For a screen's own sentence."""
        record = self.orders.get(str(key))
        if record is None:
            return 0
        return sum(1 for line in record.lines if self.recorded(key, line.sku).closed)

    def progress_drift(self) -> List[str]:
        """Every row where `fulfilled != len(copies) + by_hand`, said in words.

        THE INVARIANT'S READER. Four methods maintain it and a fifth would break it silently,
        because nothing downstream divides the count back into its two halves — a screen
        drawing "2 of 3 recorded" reads `fulfilled` alone and would be just as confident
        about a number that had come apart. Empty on a healthy ledger; T7 asserts it.

        A LIST RATHER THAN AN ASSERT. This is read from a running server over the owner's own
        store, and a raise here would take the order screen down over an arithmetic slip that
        loses nobody a card.
        """
        out: List[str] = []
        for key, rows in sorted(self.fulfilment.items()):
            for sku, row in sorted(rows.items()):
                parts = len(row.copies) + int(row.by_hand)
                if int(row.fulfilled) != parts:
                    out.append(
                        f"{key} SKU {sku}: fulfilled {row.fulfilled} but "
                        f"{len(row.copies)} copies + {row.by_hand} by hand = {parts}"
                    )
        return out

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

        A STOOD-DOWN LINE OWES NOTHING HERE EVEN WHERE `outstanding` IS POSITIVE. That is
        the whole point of `close_line` — see `CLOSE_REASONS` — and it is read here rather
        than subtracted from `outstanding`, because `outstanding` answers "how many copies
        does this line still owe", which is a fact about the ORDER and does not change
        because this store stopped tracking it. Two different questions, two readers.
        """
        out = [
            record
            for key, record in self.orders.items()
            if any(
                self.outstanding(key, line.sku) > 0
                and not self.recorded(key, line.sku).closed
                for line in record.lines
            )
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
