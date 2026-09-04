"""The order resolver: one TCGplayer order line, resolved to the copies that fill it.

An order line is `(sku, quantity)`. This repo stores POSITIONS — `(box, index)`, one per
physical card. Turning the first into the second is the whole of this module, and it is
transport-independent on purpose: no route, no screen, no CSV, no network. The input is
domain objects and an `Inventory`; the output is an answer computed on the spot.

THE JOIN KEY IS EXACT AND IS ALREADY PROVEN END TO END. An order line's SKU is the
export's `TCGplayer Id` is `store/master.py:Card.sku`, which `cli/cmd_emit.py` stamps onto
every copy a run matched (D7, amended 2026-08-30 — the live cap bounds the LISTING, not the
identity, so a fifth copy is stamped like the first four). Observed: sku 9191486 (Moonfall)
resolves to box 3, cards 3, 31, 34 and 35.

WHAT THIS MODULE IS NOT ALLOWED TO DO, and each of the five is a defect it was written
against rather than a principle it admires:

  IT RESOLVES EVERY OPEN ORDER IN ONE PASS.  `resolve_all` is the entry point and
  `resolve_one` does not exist. Resolving per order takes the first `quantity` copies of
  `copies_on_hand` every time, so two open orders for one SKU are handed THE SAME PHYSICAL
  CARDS and both report success — a picker walks to box 3 card 3 twice and the second
  envelope goes out short, or does not go out at all. One pass, a deterministic sequence,
  and a SHARED per-SKU pool is the only shape that cannot do that.

  IT STORES NOTHING.  Every answer here is recomputed from the `Inventory` it was handed.
  D10 ruling 1 lets a junk capture be deleted from the middle of a box, which slides every
  higher index down one, so a position list saved yesterday points at a different card
  today — that is D36, and it is why a run's own slot numbers are not the truth and why
  `cli/resolve.py:realign` exists. A caller that persists a `Pick` has re-created exactly
  the defect D36 was written to close.

  FULFILMENT IS A COUNT.  `LineResolution.fulfilled` is a NUMBER, derived from the picks
  rather than stored beside them, so a filled line is distinguishable from an unfillable
  one without anybody writing an address down. That is the one fact about an order line
  that is safe to keep: it survives a renumber because it names no slot.

  IT KEYS ANY IDENTITY BY `capture_id`, NEVER BY A POSITION KEY.  `Pick.capture_id` is
  carried for exactly this reason. A position-keyed record is a fourth thing no renumber
  path remaps — `server/capture_server.py:_drop_from_stores` exists because the store, the
  queues and the answer cache are already three — while a capture id is minted once per
  `POST /capture` and survives a renumber by construction.

  ITS CANDIDATES ARE A HINT, NEVER A PERMISSION SET.  This module never computes a slice
  of copies and then refuses anything outside it. A copy is valid for a line when it holds
  the line's SKU, is not in a terminal state, is a located game, and has not already been
  recorded against another line — four properties of the copy, none of them an address.
  Slicing first and refusing afterwards re-imposes an address on a fungible copy, which is
  the defect D7's own amendment overruled: `live` is a quantity, not a set of addresses,
  and any three of seven identical cards fill an order for three.

THE SKU IS COERCED AT THE BOUNDARY, AND WITHOUT THAT NOTHING WORKS AT ALL. `Card.sku` is
a string, because it comes out of a CSV cell; a JSON order payload carries the same value
as an int. `"9191486" == 9191486` is False in Python, so an uncoerced resolver reports
every line unresolvable, raises nothing, and logs nothing — a silent total failure whose
only symptom is an empty answer. `OrderLine` calls `str(sku).strip()` in `__post_init__`,
so a line built from any feed is comparable the moment it exists. The CARD side is left to
`store/master.py`'s own readers on purpose: one rule in one place, and a card whose `sku`
is not a string is a store defect to be fixed there rather than papered over here.

WHY IT IMPORTS `store`, WHICH NO OTHER MODULE IN THIS PACKAGE DOES. The alternative is a
second copy of `Inventory.copies_on_hand`'s terminal-state rule — the rule that a retired
card has left the box exactly as a sold one has (D26) — written here and audited against
nothing. `store/` imports nothing from `pipeline/`, so the edge is one-way and there is no
cycle; what it buys is that the sellable set has one definition.

NO LABEL IS RENDERED HERE. A `Pick` carries `box` and `index`, which are the physical
location; `Box N · Section N · Card M` is a RENDERING of that location, and since D58 it
counts the cards in the box rather than the slots, so drawing one needs the box's whole
occupancy. `pipeline/join.py:Position` is the only label formula in this repo and
`server/capture_server.py:_Places` is the walk that feeds it, cached per request. A second
walk here would be the second-renderer failure this repo has already recorded three times.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from pipeline import games, join
from store import master

# --------------------------------------------------------------------------- vocabulary

# WHAT A LINE IS FOR. `single` is a card that lives at a position; the other two do not,
# and telling them apart is a ROUTING signal rather than a cosmetic one — an order carrying
# a sealed box or a playmat cannot ship in an envelope, which is a fact about postage the
# owner needs before they pick anything.
#
# THIS MODULE DOES NOT CLASSIFY, IT ROUTES ON WHAT THE FEED SAYS. Deciding that "Booster
# Box" is sealed by reading a product name is guessing, which `CLAUDE.md` forbids for an
# identification and forbids here for the same reason. So the kind is declared on the line
# by whatever builds it, `single` is the default, and a feed that says nothing produces a
# line that will be looked for among the cards — and report `sku_unseen` when it is not
# there, which is the honest outcome rather than a quiet reclassification.
LINE_KIND_SINGLE = "single"
LINE_KIND_SEALED = "sealed"
LINE_KIND_ACCESSORY = "accessory"
LINE_KINDS = (LINE_KIND_SINGLE, LINE_KIND_SEALED, LINE_KIND_ACCESSORY)

# WHY AN EMPTY RESULT GETS SIX WORDS AND NOT ONE. "We found nothing" has several causes
# with different remedies, and a screen that cannot tell them apart sends the owner to the
# wrong one every time.
RESOLVED = "resolved"
SHORT = "short"
NO_COPIES_ON_HAND = "no_copies_on_hand"
SKU_UNKNOWN = "sku_unknown"
SKU_UNSEEN = "sku_unseen"
NOT_A_SINGLE = "not_a_single"

LINE_REASONS = (
    RESOLVED,
    SHORT,
    NO_COPIES_ON_HAND,
    SKU_UNKNOWN,
    SKU_UNSEEN,
    NOT_A_SINGLE,
)

# WHICH RECORD ANSWERED. A copy found because it CARRIES the SKU and a copy found because a
# run's paperwork names its position are two different strengths of claim, and a screen has
# to be able to say "matched via run X, not stamped". A fallback nobody can see is what
# makes a later disagreement unexplainable.
SOURCE_CARD = "card"
SOURCE_RUN = "run"


class UnknownLineKind(ValueError):
    """An order line declaring a kind outside `LINE_KINDS`.

    Refused rather than defaulted. A feed that has learned a new product category is
    telling us something, and swallowing it as `single` would send somebody looking through
    boxes for a playmat.
    """


# ------------------------------------------------------------------------------- inputs


@dataclass(frozen=True)
class OrderLine:
    """One line of one order: what was bought, and how many.

    Only `sku` and `quantity` decide anything. Everything else is what the feed said, kept
    verbatim so a screen can show the buyer's own words beside the position — the shape is
    a real observed line: name "Moonfall", number "UNL #198/219", Foil, Near Mint, rarity
    Epic, SKU 9191486, qty 3, $11.88. None of it is matched against a catalog and none of
    it may ever become a join key: `CLAUDE.md` forbids joining on a product name because
    the column inconsistently embeds numbers, and that rule is not weaker here.
    """

    sku: str
    quantity: int
    name: Optional[str] = None
    number: Optional[str] = None
    printing: Optional[str] = None
    condition: Optional[str] = None
    rarity: Optional[str] = None
    unit_price: Optional[str] = None
    kind: str = LINE_KIND_SINGLE

    def __post_init__(self) -> None:
        # THE COERCION THIS WHOLE MODULE RESTS ON — see the header. Frozen, so it goes
        # through `object.__setattr__`; done here rather than at every comparison so there
        # is exactly one place it can be forgotten, and it cannot be.
        object.__setattr__(self, "sku", str(self.sku).strip())
        object.__setattr__(self, "quantity", int(self.quantity))
        # ZERO IS A LINE ALREADY FILLED, AND IT IS ALLOWED ON PURPOSE. The server asks this
        # engine for what is still OWED — the ledger's outstanding, not the buyer's quantity
        # (`capture_server._engine_order`) — so a line whose copies are all pulled arrives
        # wanting nothing: `_Draw.line` picks none, `_reason` answers `resolved` at once, and
        # the breakdown behind it is still counted, which is how a filled line keeps its
        # figures on screen without a second implementation of this class. A negative
        # quantity is still the bug it always was.
        if self.quantity < 0:
            raise ValueError(f"an order line for {self.sku!r} wants {self.quantity} copies")
        if self.kind not in LINE_KINDS:
            raise UnknownLineKind(
                f"{self.kind!r} is not one of {', '.join(LINE_KINDS)}"
            )


@dataclass(frozen=True)
class Order:
    """One open order, and the lines on it.

    `placed_at` decides the SEQUENCE two orders competing for one SKU are resolved in, and
    is optional because a feed may not carry it. An order with no timestamp sorts LAST
    rather than first: the alternative claims it is the oldest, which would hand it stock
    ahead of an order we know is older.
    """

    number: str
    lines: Tuple[OrderLine, ...] = ()
    placed_at: Optional[str] = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "number", str(self.number).strip())
        object.__setattr__(self, "lines", tuple(self.lines))


@dataclass(frozen=True)
class PaperworkEntry:
    """What one run's `pricing.json` says about one SKU: which positions held a copy.

    THE BACKUP SOURCE, AND IT IS SECOND FOR A REASON. The owner's ruling is card-first:
    ask `Inventory.positions_for_sku`, and consult the run's paperwork only where a line
    comes up short. A stamped card is the store's own answer; a run directory is a record
    of what was true when the run was written.

    `positions` MUST ALREADY BE REALIGNED. `pricing.json` stores position keys, and
    positions move (D10 ruling 1, D36) — so the caller re-binds them through
    `cli/resolve.py:realign` before building this, which is what
    `cli/resolve.py:paperwork_for` does. This module cannot do it itself and should not:
    realignment reads photographs off disk, and a pure core does no I/O.
    """

    sku: str
    run: str
    positions: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "sku", str(self.sku).strip())
        object.__setattr__(self, "run", str(self.run))
        object.__setattr__(self, "positions", tuple(self.positions))


# ------------------------------------------------------------------------------ outputs


@dataclass(frozen=True)
class Pick:
    """One physical copy, recorded against one line, as it stands RIGHT NOW.

    NOT A DURABLE ADDRESS. `box` and `index` are true of the `Inventory` this was computed
    from and of no other, which is the whole of D36 — recompute on every read. `capture_id`
    is here so that a caller who genuinely must record something records the thing that
    survives a renumber; it is `None` only for a record written before the capture server
    existed, and every one of the 715 records on the owner's store carries one.
    """

    box: int
    index: int
    capture_id: Optional[str] = None
    source: str = SOURCE_CARD
    run: Optional[str] = None

    @property
    def position(self) -> str:
        """The store's own position key for this copy — `store/master.py:position_key`.

        A convenience for a caller that needs to look the card back up in the SAME
        inventory this pick came from. Never a key to write down.
        """
        return master.position_key(self.box, self.index)


@dataclass(frozen=True)
class LineResolution:
    """What one line resolved to, and why it did not resolve further.

    `picks` is the answer; `fulfilled` and `outstanding` are derived from it, so they
    cannot come to disagree with it. The three counts beside them are the BREAKDOWN
    `no_copies_on_hand` exists to make readable: positions for this SKU exist and none of
    them is available, and the operator needs to know whether that is because they sold,
    because they were retired (D26 — a departure with no sale, so "already shipped" would
    be a lie), or because the game is pooled (D24 — a code card is a count, not a place).
    """

    order: str
    line: OrderLine
    reason: str
    picks: Tuple[Pick, ...] = ()
    on_hand: int = 0
    sold: int = 0
    retired: int = 0
    pooled: int = 0

    @property
    def sku(self) -> str:
        return self.line.sku

    @property
    def wanted(self) -> int:
        return self.line.quantity

    @property
    def fulfilled(self) -> int:
        """How many copies this line found. A COUNT, never a set of addresses."""
        return len(self.picks)

    @property
    def outstanding(self) -> int:
        return max(0, self.wanted - self.fulfilled)


@dataclass(frozen=True)
class OrderResolution:
    order: Order
    lines: Tuple[LineResolution, ...] = ()

    @property
    def number(self) -> str:
        return self.order.number

    @property
    def complete(self) -> bool:
        """Every line found every copy it wanted."""
        return all(line.reason == RESOLVED for line in self.lines)

    @property
    def outstanding(self) -> int:
        return sum(line.outstanding for line in self.lines)

    @property
    def ships_in_an_envelope(self) -> bool:
        """Whether every line on this order is a single (the D24/postage routing signal)."""
        return all(line.reason != NOT_A_SINGLE for line in self.lines)


@dataclass(frozen=True)
class Resolution:
    """Every open order, resolved against one inventory in one pass."""

    orders: Tuple[OrderResolution, ...] = ()

    @property
    def lines(self) -> Tuple[LineResolution, ...]:
        return tuple(line for order in self.orders for line in order.lines)

    @property
    def complete(self) -> bool:
        return all(order.complete for order in self.orders)

    def for_order(self, number) -> Optional[OrderResolution]:
        wanted = str(number).strip()
        for order in self.orders:
            if order.number == wanted:
                return order
        return None

    def counts(self) -> Dict[str, int]:
        """How many lines landed on each reason. Every reason, including the zeros.

        Reporting only the reasons that fired would make "nothing was short" and "nothing
        was checked" the same output.
        """
        tally = {reason: 0 for reason in LINE_REASONS}
        for line in self.lines:
            tally[line.reason] = tally.get(line.reason, 0) + 1
        return tally


# ------------------------------------------------------------------------------- the pass


def order_sequence(orders: Iterable[Order]) -> Tuple[Order, ...]:
    """The deterministic order two orders competing for one SKU are served in.

    Oldest `placed_at` first, then the order number — so the answer does not depend on
    whatever sequence a feed happened to hand them over in, and re-running the resolver
    over an unchanged store produces the identical allocation.

    STRING COMPARISON ON `placed_at`, which is exact for the stamps this project writes:
    `store/master.py:now()` is UTC ISO-8601, so lexical order is time order, and
    `store/queues.py:sort_key` already compares `first_seen` the same way. A feed mixing
    UTC offsets would need parsing, and this is the paragraph to reopen when one turns up
    — parsing it silently today would be inventing a guarantee nobody has measured.
    """
    return tuple(
        sorted(
            orders,
            key=lambda o: (o.placed_at is None, o.placed_at or "", o.number),
        )
    )


@dataclass(frozen=True)
class _Copy:
    """A candidate copy and which record produced it — internal to one pass."""

    card: master.Card
    source: str
    run: Optional[str] = None


def _identity(card: master.Card) -> str:
    """What tells two copies apart inside one pass.

    `capture_id` first, always, because it is the key that survives a renumber and it is
    what any DURABLE record of a pick would have to use. The position key is the fallback
    for a record predating the capture server, and it is safe HERE and nowhere else: one
    pass reads one in-memory `Inventory` snapshot in which nothing moves, and this value is
    never written down. A store keyed this way would be the defect D36 names.
    """
    return card.capture_id or card.key


def _located(card: master.Card) -> bool:
    """Whether this copy is a card at a place, or a pooled count (D24).

    The read-side game backfill is applied here because this is a READ: a record written
    before D21's field existed is a Pokemon card. `pipeline/join.py:is_located` is the one
    reader of the registry's `located` flag, and it answers True for an unregistered game
    string — the status-quo rendering, and the loud stop for a typo belongs to the join.

    Latent today: the store holds zero code-card records. It is one clause, D24 forbids a
    pooled card in the pull flow in as many words, and `app/tests/fulfillment.spec.ts`
    already asserts the screen half — so the resolver refusing to walk somebody to a place
    that does not exist costs nothing and closes it at the source.
    """
    return join.is_located(str(card.game) if card.game else games.DEFAULT_GAME)


class _Draw:
    """The shared pool, drawn down once across every order in the pass.

    One instance per `resolve_all`. It holds a set of identities already recorded against
    a line and nothing else — no per-line slice, no reservation table, no addresses. That
    absence is the point: a copy is valid because of what it IS, and the only thing the
    pass remembers is which ones have been spoken for.
    """

    def __init__(
        self,
        inventory: master.Inventory,
        paperwork: Sequence[PaperworkEntry] = (),
    ) -> None:
        self._inventory = inventory
        self._taken: set = set()
        self._copies: Dict[str, Tuple[_Copy, ...]] = {}
        self._paper: Dict[str, List[PaperworkEntry]] = {}
        for entry in paperwork:
            self._paper.setdefault(entry.sku, []).append(entry)

    def copies(self, sku: str) -> Tuple[_Copy, ...]:
        """Every copy this resolver can see for a SKU, in the order it will draw them.

        CARD-FIRST, THEN THE PAPERWORK, which is the owner's ruling expressed as an
        ordering rather than as two loops with two sets of rules. `positions_for_sku` is
        the store's own answer and comes in box-walk order; the run's paperwork then adds
        any position it names that the store does not already know carries this SKU —
        which is exactly the copy `cli/cmd_emit.py` never stamped, because its run was
        joined and never emitted.

        EVERY STATE, NOT ONLY THE AVAILABLE ONES. This is the SKU's whole history in the
        store, because `no_copies_on_hand` needs the departed copies in order to say why
        there are none left. `available` below is what a line actually draws from.
        """
        cached = self._copies.get(sku)
        if cached is not None:
            return cached

        found: List[_Copy] = []
        seen: set = set()
        for card in self._inventory.positions_for_sku(sku):
            seen.add(_identity(card))
            found.append(_Copy(card=card, source=SOURCE_CARD))
        for entry in self._paper.get(sku, ()):
            for position in entry.positions:
                card = self._inventory.cards.get(position)
                # A position the paperwork names that the store no longer holds is not an
                # error: a whole-box delete (D10 ruling 3) removes records the run still
                # describes. It contributes nothing and says nothing.
                if card is None:
                    continue
                key = _identity(card)
                if key in seen:
                    continue
                seen.add(key)
                found.append(_Copy(card=card, source=SOURCE_RUN, run=entry.run))

        self._copies[sku] = tuple(found)
        return self._copies[sku]

    def available(self, sku: str) -> Tuple[_Copy, ...]:
        """The copies a line may draw from: here, not departed, and at a place.

        Not filtered by which line, by which order, or by how many are wanted — that is
        the hint-not-a-permission-set rule. What a line takes is decided by walking this
        and skipping what is already spoken for.
        """
        return tuple(
            copy
            for copy in self.copies(sku)
            if copy.card.state not in master.TERMINAL_STATES and _located(copy.card)
        )

    def line(self, order: Order, line: OrderLine) -> LineResolution:
        """Resolve one line against what the pass has not already given away."""
        if line.kind != LINE_KIND_SINGLE:
            # CHECKED BEFORE ANY LOOKUP, and the order matters. An accessory's SKU is not
            # a card's SKU and never will be, so asking the inventory about it produces
            # `sku_unseen` — which reads as "we have lost track of a card" and sends the
            # owner hunting through boxes for a playmat. The routing answer is available
            # without a lookup, so it is given without one.
            return LineResolution(order=order.number, line=line, reason=NOT_A_SINGLE)

        sku = line.sku
        picks: List[Pick] = []
        for copy in self.available(sku):
            if len(picks) >= line.quantity:
                break
            key = _identity(copy.card)
            if key in self._taken:
                continue
            self._taken.add(key)
            picks.append(
                Pick(
                    box=copy.card.box,
                    index=copy.card.index,
                    capture_id=copy.card.capture_id,
                    source=copy.source,
                    run=copy.run,
                )
            )

        every = self.copies(sku)
        on_hand = len(self.available(sku))
        breakdown = {
            "sold": len([c for c in every if c.card.state == master.SOLD]),
            "retired": len([c for c in every if c.card.state == master.RETIRED]),
            "pooled": len(
                [
                    c
                    for c in every
                    if c.card.state not in master.TERMINAL_STATES and not _located(c.card)
                ]
            ),
        }

        return LineResolution(
            order=order.number,
            line=line,
            reason=self._reason(sku, line.quantity, len(picks), on_hand, every),
            picks=tuple(picks),
            on_hand=on_hand,
            **breakdown,
        )

    def _reason(
        self,
        sku: str,
        wanted: int,
        fulfilled: int,
        on_hand: int,
        every: Sequence[_Copy],
    ) -> str:
        """Which of the six words this line earned. Disjoint by construction.

        `short` COVERS THE ZERO CASE WHERE THE COPIES EXIST AND ARE SPOKEN FOR, and that
        is worth stating because it is the one outcome the six words do not name directly.
        Two orders for three copies of a SKU there are three of: the first resolves, the
        second finds nothing — and the remedy is the same as any other shortfall (wait for
        stock, or ship what is there), so it is `short` with `fulfilled` 0 and `outstanding`
        equal to the whole line. It is deliberately NOT `no_copies_on_hand`, which means
        the copies have LEFT and whose remedy is to stop looking; `on_hand` beside the
        reason is what tells a screen which kind of `short` it is holding. A seventh reason
        was the alternative and was declined: six were specified, and the fact is carried
        by a number rather than by a word nothing else in the product knows.
        """
        if fulfilled >= wanted:
            return RESOLVED
        if fulfilled > 0 or on_hand > 0:
            return SHORT
        if every:
            # Positions exist for this SKU and not one of them is available. `sold`,
            # `retired` and `pooled` on the resolution say which, and they say it as three
            # counts because a lot can be all three at once.
            #
            # DELIBERATELY NOT "already_pulled". "This order shipped", "another buyer got
            # the last one" and "retired as damaged" produce an identical empty list, and
            # D26 makes a retirement a departure WITHOUT a sale — so calling it filled
            # tells the owner to ship nothing and believe it shipped.
            return NO_COPIES_ON_HAND
        if sku in self._paper:
            # The store holds no record carrying this SKU, and a run priced it. That is a
            # different fault from never having seen it: the pipeline knows the card, so
            # the remedy is to look at what happened to the box rather than at the order.
            return SKU_UNKNOWN
        return SKU_UNSEEN


def resolve_all(
    inventory: master.Inventory,
    orders: Iterable[Order],
    paperwork: Sequence[PaperworkEntry] = (),
) -> Resolution:
    """Resolve every open order against one inventory, in ONE pass over a shared pool.

    THIS IS THE ONLY ENTRY POINT, AND THERE IS DELIBERATELY NO `resolve_one`. A per-order
    resolver cannot see what another order has already been promised, so it hands two
    buyers the same physical card and reports success twice. Anything that wants one
    order's answer resolves them all and reads the one it wanted off `for_order` — the
    cost is a walk over the open orders, and the alternative is an envelope that cannot be
    filled discovered at the box.

    `paperwork` is the run-side backup and defaults to nothing: with none, this is a pure
    card-first resolution and every reason but `sku_unknown` is still reachable.

    Nothing here writes, and nothing here reads a file. The `Inventory` is a snapshot the
    caller owns, and every position in the answer is true of THAT snapshot — recompute on
    every read (D36).
    """
    draw = _Draw(inventory, paperwork)
    resolved = []
    for order in order_sequence(orders):
        resolved.append(
            OrderResolution(
                order=order,
                lines=tuple(draw.line(order, line) for line in order.lines),
            )
        )
    return Resolution(orders=tuple(resolved))
