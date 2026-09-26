"""The order walk as a PLAN: the fewest sections a hand must open to fill a ticked set.

`docs/specs/order-walk-plan.md` is this module's brief and every number below was measured
against the owner's real store before a line was written. What that document rules and this
file implements: the operator ticks orders, and the machine answers with the smallest set of
drawers that satisfies every copy those orders still owe.

WHY THIS IS POSSIBLE ONLY SINCE D212, AND WHY IT COULD NOT HAVE BEEN WRITTEN BEFORE.
`pipeline/orders.py:_Draw._taken` used to hand each line up to `line.quantity` pre-chosen
copies and withhold them from every later order in the pass. There was nothing to choose
between: the allocation WAS the answer, and a solver over it would have been re-deriving a
decision already made. D212 removed the exclusive draw — every copy is fungible, every line
is offered every candidate, and the refusal moved to the write
(`store/orders.py:record_pull`'s `CopyAlreadyPulled`). The freedom this module minimises over
is exactly the freedom that ruling created. That is why this file cites D212 and not D7.

WHAT IT IS NOT ALLOWED TO DO, each earned rather than admired:

  IT TOUCHES NO WIRE AND NO BROWSER.  No route, no JSON, no rendering. It takes an
  `Inventory` snapshot, a `Ledger` and a set of order keys, and returns dataclasses. The
  route in the spec's §7 is a caller that composes labels over this answer; a label formula
  here would be the second-renderer failure `pipeline/join.py:Position` already carries the
  repo's only copy of (`docs/specs/capture-server.md` §6.3).

  IT STORES NOTHING AND IT READS NO FILE.  Every address in the answer is true of the
  snapshot it was computed from and of no other, which is D36 — a plan persisted and replayed
  tomorrow points at different cards. The screen's own freeze (§8) is a fact about one pass in
  one browser, never a stored plan.

  IT NEVER PICKS WHICH COPY.  A stop says how many to take and lists every copy of that SKU
  standing at it, ranked. D93 and D97 are unamended: the machine ranks, the person reaches.
  `Take.wanted` is a COUNT and `Take.copies` is longer than it by design.

  TWO REGISTERS, NOT ONE, and they do not share a rule (the owner's ruling, 2026-09-18, read
  off main rather than the earlier draft of the spec). `Stop.takes` — WHICH CARD to reach for
  first — ranks densest first: count descending, same as `buildWalkPlan`'s `cardsHere` in
  `app/src/Orders.tsx` on main. `Take.copies` — WHICH COPY of one card, once a hand is at it —
  ranks front to back, ascending slot, per `app/src/Orders.tsx`'s own comment on why a hand
  goes front to back. This file only orders `takes`; `copies` was already ordered correctly
  and is untouched.

  IT ADDS NO DEPENDENCY.  Pure Python, standard library only. `requirements.txt` argues every
  dependency it carries and this venv is Python 3.9.6 with no `scipy`. A 1.1 ms solve over the
  owner's forty open orders does not earn one — see `solve`'s own measurements.

THIS IS A SET MULTICOVER, NOT A SET COVER, AND THE DISTINCTION IS THE WHOLE POINT. Each
section supplies *K* copies of a SKU and a walk wants *N* of them. A section holding three
copies of a card the walk wants three of covers that card alone; a section holding one does
not. Plain set cover cannot say that, and a solver that gets it wrong sends a hand to a drawer
for a copy that is not there — which is a wasted reach the operator only discovers at the
shelf. `harness/tests/t11_walk_plan.py` asserts the distinction directly, because a solver is
exactly the kind of code that is confidently wrong in a way no screen reveals.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Optional, Sequence, Set, Tuple

from pipeline import games, join
from store import master
from store import orders as order_store

# --------------------------------------------------------------------------- vocabulary

# THE COST FUNCTION IS A NAMED ENTRY IN A TABLE, AND TODAY THE TABLE HOLDS ONE NAME. The
# owner's ruling (2026-09-17): sections counted flat, boxes free — *"what is the least amount
# of total sections I need to scavenge through"* — with the expectation that they will want to
# change it by mood later (*"maybe we need a settings tab lol"*). So the objective's
# coefficients are selected by a string and the constraint shape never moves. Adding
# `by_box` later is a table entry, not a second solver.
#
# NO SETTINGS TAB IS SPECIFIED AND NONE IS BUILT. The spec says the wire carries the name and
# exactly one name is legal; a second entry needs the owner's word, not an if-statement.
#
# WHAT THIS SHAPE GIVES UP, STATED RATHER THAN DISCOVERED. A cost that is not a per-section
# constant — "prefer the box I am standing at", "prefer sections already opened this pass" —
# does not fit, because it makes cost depend on the SOLUTION rather than on the section. Those
# need a different formulation and this table must not be stretched to pretend otherwise.
COST_SECTIONS = "sections"

COST_FUNCTIONS: Dict[str, int] = {
    COST_SECTIONS: 1,
}

COST_NAMES: Tuple[str, ...] = tuple(sorted(COST_FUNCTIONS))

# THE SOLVER'S WALL-CLOCK BUDGET, IN SECONDS. Two orders of magnitude above the worst instance
# ever measured on the owner's store (27.9 ms for all 275 walkable orders), because the number
# this bounds is not the expected case but the pathological one nobody has seen yet. It is a
# ceiling on a route's latency, not a target.
DEFAULT_BUDGET_S = 2.0


class UnknownCostFunction(ValueError):
    """A cost function outside `COST_FUNCTIONS`.

    Refused by name with the legal values in the message, never defaulted. Silently falling
    back to `sections` would make a typo on the wire produce a plan the caller did not ask
    for and cannot tell apart from the one they did.
    """


class Uncoverable(ValueError):
    """`solve` was handed a demand its supply cannot meet.

    THE CALLER CAPS THE DEMAND AT AVAILABILITY; THIS REFUSES IF IT DID NOT. `plan` does the
    capping (see its docstring) so this never fires in the product, and it exists because the
    alternative was worse than an error: a search over an unsatisfiable constraint set has no
    cover to find, and every natural implementation of the greedy walk and the bound simply
    RUNS OUT OF USEFUL STOPS and stops — returning a partial cover that has the shape of a
    plan and is one the operator can walk, minus the cards nobody has.

    That is the silent wrong answer this whole module is written against, and it was found by
    mutation rather than by reading: removing the cap left `harness/tests/t11_walk_plan.py`
    green, because a partial cover and a correct one differ only in a card that was never
    going to be found. A refusal by name is the honest outcome, and it is what makes the cap
    a load-bearing step rather than a tidy one.
    """


class _Exhausted(Exception):
    """The wall-clock budget ran out mid-search. Internal to `solve`."""


# ------------------------------------------------------------------------------ the parts


@dataclass(frozen=True)
class StopKey:
    """What tells two stops apart: a section, or a pooled game.

    A pooled game is NOT a section and must never be drawn as one (D24 — a code card is a
    count, not a place). It is one synthetic stop per game, and `box`/`section` are `None`
    for it rather than zero, because zero is a box number a hand-edited store could hold and
    absence is the fact being recorded.
    """

    box: Optional[int] = None
    section: Optional[int] = None
    game: Optional[str] = None

    @property
    def pooled(self) -> bool:
        return self.game is not None

    @property
    def walk_order(self) -> Tuple[int, int, int, str]:
        """The sort key of the walk: sections by box then section, pooled games LAST.

        The leading flag is what puts every pooled stop behind every drawer, whatever its
        game key sorts as. A pooled stop has nothing to open, so it belongs at the end of a
        walk that is otherwise a route between drawers.
        """
        if self.pooled:
            return (1, 0, 0, str(self.game))
        return (0, int(self.box or 0), int(self.section or 0), "")


@dataclass(frozen=True)
class Copy:
    """One physical copy standing at one stop, as it is RIGHT NOW.

    NOT A DURABLE ADDRESS, for `pipeline/orders.py:Pick`'s reason and under the same ruling
    (D36): `box` and `index` are true of the snapshot this was computed from and of no other.
    `capture_id` is the key that survives a renumber; `cid` is the card's own name (D172,
    D183) and is what lets a screen address the photograph the way `#/inventory` and
    `#/fulfillment` do rather than by `photoUrl(box, index)`. Both are Optional because a
    record written before either field existed carries neither.
    """

    box: int
    index: int
    sku: str
    capture_id: Optional[str] = None
    cid: Optional[str] = None


@dataclass(frozen=True)
class Take:
    """One SKU at one stop: how many to take, and every copy of it standing there.

    `wanted` IS A COUNT AND `copies` IS LONGER THAN IT ON PURPOSE. D97 one register down: the
    plan says how many, never which. Capping `copies` at `wanted` would put an address back
    on a fungible copy — the defect D212 overruled — and would send the operator to one card
    when four identical ones are within reach of the same hand.
    """

    sku: str
    wanted: int
    copies: Tuple[Copy, ...] = ()
    orders: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Stop:
    """One reach: a drawer to open, and what to take out of it."""

    key: StopKey
    order: int
    takes: Tuple[Take, ...] = ()

    @property
    def box(self) -> Optional[int]:
        return self.key.box

    @property
    def section(self) -> Optional[int]:
        return self.key.section

    @property
    def pooled(self) -> bool:
        return self.key.pooled

    @property
    def game(self) -> Optional[str]:
        return self.key.game

    @property
    def game_display(self) -> Optional[str]:
        """The registry's display name for a pooled stop's game, or None.

        `games.get` raises rather than defaulting, which is right where a key decides a join
        and wrong here: an unregistered key on a pooled stop is a store defect to be fixed in
        the registry, and taking a whole plan down over a display string would hide the plan
        that is otherwise correct. The key itself is always carried beside this.
        """
        if not self.pooled:
            return None
        try:
            return str(games.get(str(self.game))["display"])
        except games.UnknownGame:
            return None

    @property
    def copies(self) -> int:
        return sum(take.wanted for take in self.takes)


@dataclass(frozen=True)
class Short:
    """One SKU the store cannot fill, and by how much.

    NOT A STOP AND NEVER DRAWN AS ONE. It is the capped remainder — see `demand` — and it is
    reported rather than made infeasible, because 23 of the 59 SKUs the owner's forty open
    orders want cannot be filled from inventory at all. A solver that refused to answer over
    those would refuse to answer at all on the real store.
    """

    sku: str
    wanted: int
    on_hand: int
    orders: Tuple[str, ...] = ()

    @property
    def short(self) -> int:
        return max(0, self.wanted - self.on_hand)


@dataclass(frozen=True)
class Counts:
    """The plan's own arithmetic, including the two figures that say how hard it was.

    `exact` IS THE FIELD THIS CLASS EXISTS FOR. A solver that exhausts its budget and returns
    the greedy incumbent without saying so is indistinguishable from one that proved the
    optimum — same shape, same stops, a quietly worse answer. The spec (§7) requires the
    screen to draw it, and `harness/tests/t11_walk_plan.py` requires it to be REACHABLE, by
    handing the solver a budget it cannot meet. A flag nobody can make false is a flag nobody
    has tested.
    """

    stops: int = 0
    boxes: int = 0
    copies: int = 0
    sections_considered: int = 0
    sections_candidate: int = 0
    exact: bool = True
    solve_ms: int = 0


@dataclass(frozen=True)
class Plan:
    """The whole answer: where to go, what to take, and what cannot be filled."""

    cost: str = COST_SECTIONS
    stops: Tuple[Stop, ...] = ()
    shortfall: Tuple[Short, ...] = ()
    counts: Counts = field(default_factory=Counts)


# ---------------------------------------------------------------------------- the demand


@dataclass(frozen=True)
class Want:
    """One SKU the ticked set still owes, and which orders owe it."""

    sku: str
    wanted: int
    orders: Tuple[str, ...] = ()


def demand(ledger: order_store.Ledger, keys: Iterable[str]) -> Tuple[Want, ...]:
    """What the ticked orders still owe, per SKU, summed across them.

    `Ledger.outstanding` IS THE FORMULA AND IT IS NOT REIMPLEMENTED HERE. It is exactly
    `max(0, line.quantity - recorded.fulfilled)` — the spec's §5 demand — and it is the same
    call `server/capture_server.py:_engine_order` already makes to tell the resolver what is
    still owed. Spelling the subtraction out a second time would be a second answer to one
    question the moment either side learned about a new kind of fulfilment.

    THE LEDGER'S `recorded`, NEVER `ResolvedLine.fulfilled`, and `app/src/Orders.tsx:figureOf`
    already carries the reason: since D212 `fulfilled` is `len(picks)`, which is what could be
    OFFERED and never what has been TAKEN. Reading it here would make a line with five
    candidate copies and zero pulls look filled, and the walk would skip a card the buyer is
    still owed.

    A STOOD-DOWN LINE OWES ZERO HERE, ON THE OWNER'S OWN RULING (2026-09-17): *"If I stand a
    line down, it should say owed 0 and not send me to the drawer for those lines."* That is
    an AMENDMENT to the spec's section 5, made in the same commit as this code and not a
    silent departure from it — the first draft of this module applied the rule unasked, which
    was the wrong order.

    `LineProgress.closed` means the line needs nothing further from this store even though
    `outstanding` is positive. `Ledger.unfulfilled` already reads it exactly this way rather
    than subtracting it from `outstanding`, and its docstring says why: "how many copies does
    this line owe" is a fact about the ORDER, and "is this store still fetching it" is a fact
    about this store. A WALK IS THE SECOND QUESTION. `close_line` is the operator saying they
    are not shipping it, so a plan that routes a hand to that drawer is spending a reach on a
    card the operator already decided against.

    `server/capture_server.py:_engine_order` deliberately does NOT apply this filter, and the
    two are not in conflict. It feeds the RESOLVER, which answers what an order is owed — the
    first question. This answers the second.

    A KEY THE LEDGER DOES NOT HOLD CONTRIBUTES NOTHING AND RAISES NOTHING. The spec's route
    skips an unknown key rather than refusing the request, so the skip belongs here where the
    key is first looked up, not in a pre-flight the route would have to keep in step.
    """
    wanted: Dict[str, int] = {}
    owed_by: Dict[str, List[str]] = {}
    for raw in keys:
        key = str(raw).strip()
        record = ledger.orders.get(key)
        if record is None:
            continue
        for line in record.lines:
            sku = str(line.sku).strip()
            if not sku:
                continue
            if ledger.recorded(key, sku).closed:
                continue
            owed = ledger.outstanding(key, sku)
            if owed <= 0:
                continue
            wanted[sku] = wanted.get(sku, 0) + owed
            if key not in owed_by.setdefault(sku, []):
                owed_by[sku].append(key)
    return tuple(
        Want(sku=sku, wanted=wanted[sku], orders=tuple(owed_by.get(sku, ())))
        for sku in sorted(wanted)
    )


# ---------------------------------------------------------------------------- the supply


def _located(card: master.Card) -> bool:
    """Whether this copy is a card at a place, or a pooled count (D24).

    The read-side game backfill is applied here because this is a READ: a record written
    before D21's field existed is a Pokemon card. Byte-for-byte the rule
    `pipeline/orders.py:_located` and `server/capture_server.py:_location_of` apply, stated
    a third time only because those two are one module's private and one server's private;
    all three resolve through `join.is_located`, which is the single door.
    """
    return join.is_located(str(card.game) if card.game else games.DEFAULT_GAME)


def _sections_of(inventory: master.Inventory, box: int) -> Dict[int, int]:
    """`index -> section number` for every located, on-hand card in one box.

    ONE BOX LOOKUP PER BOX, NOT PER CARD, which is `server/capture_server.py:_Places`'s own
    rule and its reason: `Position.section` needs the box's divider layout and D58's counting
    space (`occupied`), and rebuilding both per card is O(cards) on a route the screen will
    press. `Inventory.occupied_indices` answers the counting space from two indexed integer
    columns rather than hydrating a `Card` per row, and hands the `game` claim back raw for
    exactly the reason this module can filter it and `store/` cannot (D63 — `store/` imports
    nothing from `pipeline/`).

    `Position` IS THE ONLY SECTION FORMULA IN THIS REPO and this walks it rather than
    re-deriving the bisect. A second spelling of a section number is a second spelling of an
    address somebody counts dividers against, which is the failure `Position`'s docstring
    spends a paragraph on.

    A BOX WHOSE RECORDS OR LAYOUT WILL NOT READ YIELDS NOTHING, rather than a guess. The
    supply this builds decides where a hand is sent; a section number derived from a layout
    that never went through `set_sections` would send it to a divider the plastic does not
    have. The copies in such a box simply do not enter the plan, which is visible as a
    shortfall rather than as a wrong drawer.
    """
    try:
        raw = inventory.occupied_indices(box)
        layout = inventory.sections_for(box)
    except (master.BadPosition, master.BadSections):
        return {}
    occupied = tuple(index for index, claim in raw if _claim_located(claim))
    # THROUGH `BoxView.at`, so a box with an order (D265) counts its sections in that order.
    view = join.BoxView(sections=layout, occupied=occupied, order=inventory.box_order(box))
    out: Dict[int, int] = {}
    for index in occupied:
        out[index] = view.at(box, index).section
    return out


def _claim_located(claim: Optional[str]) -> bool:
    """`_located` for a bare `game` column value rather than a whole `Card`.

    `Inventory.occupied_indices` hands back `(index, game)` pairs because `store/` cannot
    resolve D24's flag itself. The twin of `server/capture_server.py:_location_of`, and the
    same rule: an unregistered or absent claim reads as `games.DEFAULT_GAME` and is located.
    """
    return join.is_located(str(claim) if claim else games.DEFAULT_GAME)


@dataclass(frozen=True)
class Supply:
    """Where every copy of every demanded SKU is standing, grouped into stops.

    `per_stop` is the solver's input — a count per SKU per stop — and `copies` is what the
    plan renders from. They are built in one walk so they cannot come to disagree about how
    many copies a stop holds.
    """

    per_stop: Dict[StopKey, Dict[str, int]] = field(default_factory=dict)
    copies: Dict[Tuple[StopKey, str], Tuple[Copy, ...]] = field(default_factory=dict)
    on_hand: Dict[str, int] = field(default_factory=dict)
    sections_considered: int = 0


def supply(inventory: master.Inventory, skus: Sequence[str]) -> Supply:
    """Every on-hand copy of each demanded SKU, grouped by the stop it stands at.

    ASKED SKU BY SKU RATHER THAN BY WALKING THE STORE. `Inventory.copies_on_hand` is the
    sellable set (D7 amended, D26) answered off an indexed column, and a walk wants a handful
    of SKUs out of a store holding thousands of cards — so the cost is the demand's size, not
    the store's. That is also why the terminal-state rule is not restated here: `sold`,
    `retired` and `moved` leave inventory by three doors and `TERMINAL_STATES` is the one
    place that is decided.

    A POOLED GAME IS ONE SYNTHETIC STOP PER GAME (D24), not a section and not one stop per
    card. It is latent today — the store holds zero code-card records — and it is built
    anyway, because the alternative is a `None` section number reaching the walk order the
    first time one is captured, which is a wrong drawer rather than a missing feature.
    """
    per_stop: Dict[StopKey, Dict[str, int]] = {}
    found: Dict[Tuple[StopKey, str], List[Copy]] = {}
    on_hand: Dict[str, int] = {}
    sections: Dict[int, Dict[int, int]] = {}
    considered: Set[StopKey] = set()

    for raw in skus:
        sku = str(raw).strip()
        if not sku:
            continue
        for card in inventory.copies_on_hand(sku):
            if _located(card):
                box = int(card.box)
                if box not in sections:
                    sections[box] = _sections_of(inventory, box)
                    for number in set(sections[box].values()):
                        considered.add(StopKey(box=box, section=number))
                section = sections[box].get(int(card.index))
                if section is None:
                    # The box's own walk does not hold this index — a record whose position
                    # will not coerce, or a layout that will not read. `_sections_of` says
                    # why that is dropped rather than guessed at.
                    continue
                key = StopKey(box=box, section=section)
            else:
                key = StopKey(game=str(card.game) if card.game else games.DEFAULT_GAME)
                considered.add(key)

            per_stop.setdefault(key, {})
            per_stop[key][sku] = per_stop[key].get(sku, 0) + 1
            found.setdefault((key, sku), []).append(
                Copy(
                    box=int(card.box),
                    index=int(card.index),
                    sku=sku,
                    capture_id=card.capture_id,
                    cid=card.cid,
                )
            )
            on_hand[sku] = on_hand.get(sku, 0) + 1

    return Supply(
        per_stop=per_stop,
        copies={key: tuple(value) for key, value in found.items()},
        on_hand=on_hand,
        sections_considered=len(considered),
    )


# ---------------------------------------------------------------------------- the solver


@dataclass(frozen=True)
class Solution:
    chosen: FrozenSet[StopKey] = frozenset()
    exact: bool = True
    candidates: int = 0
    solve_ms: int = 0


def _clip(
    per_stop: Dict[StopKey, Dict[str, int]], wanted: Dict[str, int]
) -> Dict[StopKey, Dict[str, int]]:
    """Step 1: drop stops holding no demanded SKU, and clip what is left to the demand.

    A stop holding nine copies of a card the walk wants two of covers exactly the same set of
    instances as one holding two. Surplus never changes which cover is smallest, and clipping
    it away is what makes the dominance test below a componentwise comparison of short
    vectors rather than of counts that differ only above the ceiling.
    """
    out: Dict[StopKey, Dict[str, int]] = {}
    for key, held in per_stop.items():
        clipped = {
            sku: min(int(wanted[sku]), int(count))
            for sku, count in held.items()
            if sku in wanted and int(count) > 0
        }
        clipped = {sku: n for sku, n in clipped.items() if n > 0}
        if clipped:
            out[key] = clipped
    return out


def _dominated(clipped: Dict[StopKey, Dict[str, int]]) -> Set[StopKey]:
    """Step 2: every stop some other stop covers componentwise. This is where the search goes.

    SAFE ONLY BECAUSE THE COST IS A PER-SECTION CONSTANT. If *A* supplies at least as many
    copies of every demanded SKU as *B* and costs no more, any cover using *B* stays a cover
    when *B* is swapped for *A* and never grows. That reasoning is the cost function's, not
    the constraint's, so a future non-constant cost must revisit this function rather than
    inherit it — which is one of the two places `COST_FUNCTIONS`' docstring means when it says
    the table must not be stretched.

    TWO IDENTICAL STOPS DOMINATE EACH OTHER, AND DROPPING BOTH WOULD LOSE THE COVER. Ties are
    broken by walk order: of two stops with the same vector, the one a hand reaches first
    survives. That also makes the reduction deterministic, which a plan the operator sees
    twice has to be.
    """
    keys = sorted(clipped, key=lambda k: k.walk_order)
    dropped: Set[StopKey] = set()
    for i, b in enumerate(keys):
        if b in dropped:
            continue
        for j, a in enumerate(keys):
            if a is b or a in dropped:
                continue
            covers = all(
                clipped[a].get(sku, 0) >= count for sku, count in clipped[b].items()
            )
            if not covers:
                continue
            same = clipped[a] == clipped[b]
            # A strict cover always wins. An equal one wins only if it comes first in the
            # walk, which is what stops a mutual pair erasing itself.
            if same and j > i:
                continue
            dropped.add(b)
            break
    return dropped


def _coverage(held: Dict[str, int], remaining: Dict[str, int]) -> int:
    """How many still-outstanding COPIES this stop would supply. Multiplicity, not SKUs."""
    return sum(min(count, held.get(sku, 0)) for sku, count in remaining.items())


def _after(remaining: Dict[str, int], held: Dict[str, int]) -> Dict[str, int]:
    """What is still outstanding once this stop has been taken."""
    out: Dict[str, int] = {}
    for sku, count in remaining.items():
        left = count - held.get(sku, 0)
        if left > 0:
            out[sku] = left
    return out


def _greedy(
    clipped: Dict[StopKey, Dict[str, int]], wanted: Dict[str, int]
) -> List[StopKey]:
    """Step 3: take the stop covering the most outstanding copies, until nothing is left.

    THE INCUMBENT THE SEARCH IMPROVES ON, and on the owner's store it is also the answer: at
    every measured size greedy equalled the optimum. That is not a reason to ship greedy
    alone — `docs/specs/order-walk-plan.md` §6 is explicit that the solver earns its place on
    the ticked subsets the owner walks, and a heuristic that happens to be right on one store
    is a heuristic nobody can tell has stopped being right.

    Ties break on walk order, so a plan does not reshuffle between two presses over an
    unchanged store.
    """
    remaining = dict(wanted)
    taken: List[StopKey] = []
    available = sorted(clipped, key=lambda k: k.walk_order)
    while remaining:
        best: Optional[StopKey] = None
        best_cover = 0
        for key in available:
            if key in taken:
                continue
            cover = _coverage(clipped[key], remaining)
            if cover > best_cover:
                best, best_cover = key, cover
        if best is None:
            # Unreachable: `solve` refuses an uncoverable instance by name before this runs,
            # which is what stops this `break` returning a partial cover shaped like a plan.
            break
        taken.append(best)
        remaining = _after(remaining, clipped[best])
    return taken


def solve(
    per_stop: Dict[StopKey, Dict[str, int]],
    wanted: Dict[str, int],
    budget_s: float = DEFAULT_BUDGET_S,
) -> Solution:
    """The fewest stops that cover every demanded copy. Exact branch and bound, pure Python.

    THE FORMULATION IS THE MEASUREMENT, NOT A STYLE PREFERENCE, and the spec records both
    attempts. Branching on section index did not finish the owner's 275-order instance in 30
    seconds. Branching on the SCARCEST demanded SKU, over dominance-reduced vectors, solves
    the same instance in 27.9 ms. Anyone rewriting the branch rule is undoing a measured
    result and owes a new measurement, not an argument.

    WHY THE SCARCEST SKU. Every cover must contain at least one supplier of every demanded
    SKU, so branching over the suppliers of ONE SKU is exhaustive by construction — and
    picking the SKU with the fewest suppliers makes that branch the narrowest available.
    Branching on "in or out" of an arbitrary section is a binary tree over every section
    instead, most of whose leaves are covers nobody would consider.

    SIBLINGS ARE BANNED AS THEY ARE TRIED, which is what keeps the branches disjoint. Once the
    subtree containing supplier *s* has been searched, every cover containing *s* has been
    seen, so later siblings may exclude it. Without the ban the same cover is re-derived once
    per permutation of its members and the search is factorial in the answer's own size.

    THE BOUND. `|chosen| + ceil(outstanding / best single-stop coverage)` is a lower bound on
    any completion of this branch: no stop can supply more than the best one does, so no
    completion can be shorter than that many further stops. Reaching the incumbent's size
    prunes, since an equal answer is not an improvement.

    THE BUDGET IS CHECKED FIRST IN EVERY NODE, AND THAT IS WHAT MAKES `exact: false`
    REACHABLE. A budget of zero exhausts before the first bound is computed, so the greedy
    incumbent comes back flagged — which is how `harness/tests/t11_walk_plan.py` proves the
    flag can be false without needing an instance nobody has found. A silent fall back to
    greedy is the failure mode this return value exists to prevent.
    """
    started = time.monotonic()
    clipped = _clip(per_stop, wanted)

    # THE INSTANCE MUST BE COVERABLE BEFORE ANYTHING SEARCHES IT. Checked on the CLIPPED
    # vectors and before the dominance reduction, so the sum is over exactly the copies a
    # cover could use. `plan` caps the demand at availability first, so this is a statement
    # about the caller rather than about any real store — see `Uncoverable`.
    reach: Dict[str, int] = {}
    for held in clipped.values():
        for sku, count in held.items():
            reach[sku] = reach.get(sku, 0) + count
    missing = sorted(sku for sku, count in wanted.items() if reach.get(sku, 0) < int(count))
    if missing:
        raise Uncoverable(
            "no set of stops can fill "
            + ", ".join(
                f"{sku} (wants {wanted[sku]}, {reach.get(sku, 0)} reachable)"
                for sku in missing
            )
            + " — cap the demand at availability and report the remainder as a shortfall"
        )

    for key in _dominated(clipped):
        clipped.pop(key, None)
    candidates = len(clipped)

    if not wanted:
        return Solution(chosen=frozenset(), exact=True, candidates=candidates, solve_ms=0)

    suppliers: Dict[str, List[StopKey]] = {}
    for key in sorted(clipped, key=lambda k: k.walk_order):
        for sku in clipped[key]:
            suppliers.setdefault(sku, []).append(key)

    incumbent: List[StopKey] = _greedy(clipped, wanted)
    best: List[StopKey] = list(incumbent)
    deadline = started + max(0.0, float(budget_s))

    def search(chosen: List[StopKey], remaining: Dict[str, int], banned: Set[StopKey]) -> None:
        if time.monotonic() >= deadline:
            raise _Exhausted()
        if not remaining:
            if len(chosen) < len(best):
                best[:] = list(chosen)
            return
        if len(chosen) + 1 >= len(best):
            return

        usable = [
            key for key in clipped if key not in banned and key not in chosen
        ]
        reach = 0
        for key in usable:
            reach = max(reach, _coverage(clipped[key], remaining))
        if reach == 0:
            return
        outstanding = sum(remaining.values())
        if len(chosen) + math.ceil(outstanding / reach) >= len(best):
            return

        scarcest: Optional[str] = None
        fewest = 0
        for sku in sorted(remaining):
            count = len(
                [
                    key
                    for key in suppliers.get(sku, ())
                    if key not in banned and key not in chosen
                ]
            )
            if count == 0:
                # Every supplier of an outstanding SKU is banned or already taken: THIS
                # BRANCH cannot complete a cover. Never the instance — `Uncoverable` has
                # already refused one of those, so the root is always completable.
                return
            if scarcest is None or count < fewest:
                scarcest, fewest = sku, count

        local = set(banned)
        for key in suppliers.get(str(scarcest), ()):
            if key in local or key in chosen:
                continue
            chosen.append(key)
            search(chosen, _after(remaining, clipped[key]), local)
            chosen.pop()
            local.add(key)

    exact = True
    try:
        search([], dict(wanted), set())
    except _Exhausted:
        exact = False
    except RecursionError:
        # The same honest answer as a budget overrun: the incumbent, flagged. A plan nobody
        # can tell is unproven is the one thing this function may not return.
        exact = False

    return Solution(
        chosen=frozenset(best),
        exact=exact,
        candidates=candidates,
        solve_ms=int(round((time.monotonic() - started) * 1000)),
    )


# ------------------------------------------------------------------------------ the plan


def _assign(
    chosen: Sequence[StopKey],
    per_stop: Dict[StopKey, Dict[str, int]],
    wanted: Dict[str, int],
) -> Dict[StopKey, Dict[str, int]]:
    """How the demand is divided between the chosen stops: in walk order, as much as fits.

    THE COVER SAYS WHICH DRAWERS; THIS SAYS HOW MANY TO TAKE FROM EACH. Assigning in walk
    order means the operator takes what they can at the first drawer they reach and the later
    ones ask for the remainder — so a walk abandoned halfway has banked the most it could,
    rather than leaving every stop part-filled.

    A STOP MAY END UP WANTING NOTHING and is dropped by `plan`. It happens when an earlier
    stop in the walk covers what this one was chosen for, which a minimal cover permits: the
    cover is minimal in CARDINALITY, and an individual member can still be redundant once
    multiplicities land. Drawing a stop that asks for zero cards would send a hand to a drawer
    for nothing.
    """
    remaining = dict(wanted)
    out: Dict[StopKey, Dict[str, int]] = {}
    for key in chosen:
        held = per_stop.get(key, {})
        take: Dict[str, int] = {}
        for sku in sorted(held):
            if sku not in remaining:
                continue
            count = min(remaining[sku], int(held[sku]))
            if count <= 0:
                continue
            take[sku] = count
            remaining[sku] -= count
            if remaining[sku] <= 0:
                remaining.pop(sku)
        if take:
            out[key] = take
    return out


def plan(
    inventory: master.Inventory,
    ledger: order_store.Ledger,
    keys: Iterable[str],
    cost: str = COST_SECTIONS,
    budget_s: float = DEFAULT_BUDGET_S,
) -> Plan:
    """The whole answer for one ticked set, over one snapshot.

    THE DEMAND IS CAPPED AT AVAILABILITY BEFORE THE SOLVE, and that ordering is the design
    rather than an optimisation. A SKU the store cannot fill has no supplier, so leaving it in
    the constraint set makes the instance INFEASIBLE — and on the owner's store 23 of the 59
    SKUs their forty open orders want are in exactly that state. A solver that refuses to
    answer over a real store is a solver nobody can use. What cannot be filled is capped out
    here and reported as `shortfall`, which is a block at the foot of the screen rather than
    an error.

    THE SNAPSHOT IS THE CALLER'S AND EVERY ADDRESS IN THE ANSWER IS TRUE OF IT ALONE (D36).
    Nothing here writes, nothing here reads a file, and nothing here takes a lock.
    """
    name = str(cost).strip() or COST_SECTIONS
    if name not in COST_FUNCTIONS:
        raise UnknownCostFunction(
            f"{name!r} is not a cost function; legal: {', '.join(COST_NAMES)}"
        )

    wants = demand(ledger, keys)
    stocks = supply(inventory, [want.sku for want in wants])

    capped: Dict[str, int] = {}
    shortfall: List[Short] = []
    for want in wants:
        on_hand = int(stocks.on_hand.get(want.sku, 0))
        fillable = min(want.wanted, on_hand)
        if fillable > 0:
            capped[want.sku] = fillable
        if on_hand < want.wanted:
            shortfall.append(
                Short(
                    sku=want.sku,
                    wanted=want.wanted,
                    on_hand=on_hand,
                    orders=want.orders,
                )
            )

    solution = solve(stocks.per_stop, capped, budget_s=budget_s)
    walk = sorted(solution.chosen, key=lambda k: k.walk_order)
    assigned = _assign(walk, stocks.per_stop, capped)

    owed_by = {want.sku: want.orders for want in wants}
    stops: List[Stop] = []
    for key in walk:
        take_counts = assigned.get(key)
        if not take_counts:
            continue
        # TWO REGISTERS, NOT ONE (the owner's ruling, 2026-09-18, read off main rather than
        # the spec). THE TAKES AT A STOP RANK DENSEST FIRST — the card worth reaching for
        # first — count descending, same as `buildWalkPlan`'s `cardsHere` in
        # `app/src/Orders.tsx` on main (`count` descending, `name` ascending tie-break).
        # `Take` carries no name, so the tie-break here is `sku` ascending instead: stable,
        # and deterministic across two reads of the same plan. THE COPIES INSIDE ONE TAKE
        # rank the other way, front to back by slot (`app/src/Orders.tsx:1381`'s own
        # comment: a hand goes front to back) — that register is untouched here, `_assign`
        # and `supply` already order `Take.copies` that way, and this loop only orders the
        # SKUs, never the copies under one.
        ordered_skus = sorted(take_counts, key=lambda sku: (-take_counts[sku], sku))
        takes = tuple(
            Take(
                sku=sku,
                wanted=take_counts[sku],
                copies=stocks.copies.get((key, sku), ()),
                orders=owed_by.get(sku, ()),
            )
            for sku in ordered_skus
        )
        stops.append(Stop(key=key, order=len(stops) + 1, takes=takes))

    boxes = {stop.box for stop in stops if not stop.pooled}
    return Plan(
        cost=name,
        stops=tuple(stops),
        shortfall=tuple(shortfall),
        counts=Counts(
            stops=len(stops),
            boxes=len(boxes),
            copies=sum(stop.copies for stop in stops),
            sections_considered=stocks.sections_considered,
            sections_candidate=solution.candidates,
            exact=solution.exact,
            solve_ms=solution.solve_ms,
        ),
    )
