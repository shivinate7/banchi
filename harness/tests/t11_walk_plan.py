"""T11 — The order walk plan: the fewest drawers that fill a ticked set of orders.

NEW 2026-09-17, with `pipeline/walkplan.py` and `docs/specs/order-walk-plan.md`. It exists as
its own failing test name because a solver is the kind of code that is confidently wrong in a
way no screen reveals: a plan that is one drawer too long, or that asks for a copy that is not
in the drawer it names, renders exactly like a correct one. The operator finds out at the
shelf, and by then the reach is already spent.

WHY T11 AND NOT T10. T10 is spelled for the Intelligent Mail barcode encoder, shelved on the
owner's ruling with `pipeline/imb.py` on branch `claude/tcgtracking-in-house-a7cb43` at
c9391e1 and recorded as T10 in five places in `docs/debts/026-*.md`. This repo's rule for a
contended id is to renumber your own and never another's, so the shelf keeps its number and
the gap is deliberate. `harness/run.py`'s docstring says the same thing beside `TESTS`.

THE FOUR WAYS A WALK PLAN CAN BE WRONG, and each is a separate check below because each fails
differently at the drawer:

    ONE DRAWER TOO MANY      the plan is a plan either way and nothing on screen tells a
                             solved one from a listed one (the spec says so, deliberately).
                             Checked by a fixture where GREEDY IS STRICTLY WORSE than the
                             optimum, so a regression that quietly drops the branch and bound
                             changes the answer rather than the timing.
    A COPY THAT IS NOT THERE the set-cover-versus-multicover mistake. A section holding one
                             copy of a card the walk wants two of does not cover it. Checked
                             by an instance a set-cover solver answers in one stop and the
                             correct answer needs two.
    A CARD NOBODY HAS        an unfillable SKU has no supplier, so leaving it in the
                             constraints makes the whole instance infeasible — and on the
                             owner's store 23 of 59 wanted SKUs are in that state. Checked by
                             asserting the plan still answers and the SKU lands in the
                             shortfall.
    A DRAWER THAT IS NOT ONE a pooled game is a count, not a place (D24). Checked by
                             asserting its stop is last, carries no box and no section, and
                             is not counted among the boxes.

AND A FIFTH THAT IS NOT ABOUT THE ANSWER: `exact` must be REACHABLE as false. A solver that
exhausts its budget and returns the greedy incumbent without saying so is indistinguishable
from one that proved the optimum. The flag exists to prevent a silent fall back to greedy, and
a flag nobody can make false is a flag nobody has tested — so this drives it with a budget it
cannot meet.

THE STORE IS SEEDED IN MEMORY, which is the whole fixture. `pipeline/walkplan.py` reads no
file, takes no lock and writes nothing, so a `master.Inventory` and a `store.orders.Ledger`
built here are the same inputs the route will hand it. Every count below is small enough to
verify by hand, which is the point: a fixture nobody can check by eye proves that the solver
agrees with itself.

WHAT A GREEN T11 DOES NOT MEAN. It does not mean the plan is fast on the owner's store — the
27.9 ms figure in `docs/specs/order-walk-plan.md` §6 was measured there and is not re-measured
here, because a timing assertion on a shared CI box is a flake rather than a guard. It does not
mean the screen draws any of this: §7's route and §8's screen are separate work and no code
here reaches a wire.
"""

from __future__ import annotations

from harness.tests import Checks, Result
from pipeline import walkplan
from store import master
from store import orders as order_store

NAME = "T11"
DESCRIPTION = "The order walk plan: fewest drawers, multiplicities, shortfall, pooled, exact"
PASS_CRITERIA = (
    "the plan is the proven optimum on a fixture greedy gets wrong. A section holding one "
    "copy never satisfies a demand for two. An unfillable SKU lands in the shortfall rather "
    "than making the instance infeasible. A pooled game is one stop, last, and never a "
    "section. And `exact` comes back false when the budget cannot be met"
)


# --------------------------------------------------------------------------- the fixture


def _store(layout, cards, game=None):
    """A one-box inventory: `layout` is the divider indices, `cards` the SKUs in index order.

    Every card is `identified` — on hand, in D24's located sense unless `game` says otherwise
    — because what this module reads is `Inventory.copies_on_hand`, and the states it excludes
    (`sold`, `retired`, `moved`) are `TERMINAL_STATES`' business rather than this test's.
    """
    inventory = master.Inventory()
    inventory.boxes["1"] = master.Box(box=1, sections=list(layout))
    for index, sku in enumerate(cards, start=1):
        inventory.cards[master.position_key(1, index)] = master.Card(
            box=1,
            index=index,
            sku=sku,
            state=master.IDENTIFIED,
            capture_id=f"cap-1-{index}",
            game=game,
        )
    return inventory


def _ledger(lines, key="tcg:1"):
    """One open order wanting `lines`, a `{sku: quantity}` map, under `key`."""
    source, number = key.split(":", 1)
    ledger = order_store.Ledger()
    ledger.ingest(
        [
            order_store.OrderRecord(
                source=source,
                number=number,
                placed_at="2026-09-17T00:00:00Z",
                lines=[
                    order_store.OrderLine(sku=sku, quantity=quantity)
                    for sku, quantity in sorted(lines.items())
                ],
            )
        ]
    )
    return ledger


def _sections(plan):
    """The section numbers the plan visits, in walk order."""
    return [stop.section for stop in plan.stops if not stop.pooled]


def _taken(plan):
    """`{sku: copies the plan says to take}`, summed over every stop."""
    out = {}
    for stop in plan.stops:
        for take in stop.takes:
            out[take.sku] = out.get(take.sku, 0) + take.wanted
    return out


# ------------------------------------------------------------------------------- the run


def run() -> Result:
    c = Checks()

    _optimum(c)
    _multiplicity(c)
    _shortfall(c)
    _pooled(c)
    _stood_down(c)
    _exact(c)
    _cost_name(c)
    _take_order(c)

    return c.result()


def _optimum(c: Checks) -> None:
    """The optimum, on an instance GREEDY GETS WRONG — which is what makes this a check.

    Six SKUs, one copy of each wanted, three sections in one box:

        section 1   A B C D      four cards — the biggest, so greedy takes it first
        section 2   A B E
        section 3   C D F

    Greedy takes section 1 (covers four), then needs E and F, and no remaining section holds
    both — so it takes two more and lands on THREE. The optimum is TWO: sections 2 and 3 cover
    all six between them. A fixture where greedy already equals the optimum would go green
    over a solver that had quietly become greedy, which is the regression most worth catching
    here — on the owner's own store greedy equalled the optimum at every measured size, so the
    difference is invisible there by construction.
    """
    inventory = _store([1, 5, 8], ["A", "B", "C", "D", "A", "B", "E", "C", "D", "F"])
    ledger = _ledger({sku: 1 for sku in "ABCDEF"})

    plan = walkplan.plan(inventory, ledger, ["tcg:1"])

    c.equal(plan.counts.stops, 2, "the plan is two drawers, which is the optimum by hand")
    c.equal(_sections(plan), [2, 3],
            "and it is sections 2 and 3 — A B E and C D F, which cover all six between them")
    c.equal(plan.counts.exact, True, "proved rather than guessed: `exact` is true")
    c.equal(_taken(plan), {sku: 1 for sku in "ABCDEF"},
            "every wanted copy is asked for exactly once across the walk")

    # THE INCUMBENT IS WORSE, WHICH IS WHAT SAYS THE SEARCH DID THE WORK. Asserted against the
    # module's own greedy rather than against a number typed here, so a change to the greedy
    # rule cannot make this check silently vacuous.
    clipped = walkplan._clip(
        walkplan.supply(inventory, list("ABCDEF")).per_stop, {sku: 1 for sku in "ABCDEF"}
    )
    greedy = walkplan._greedy(clipped, {sku: 1 for sku in "ABCDEF"})
    c.equal(len(greedy), 3,
            "the greedy upper bound is three drawers, so this fixture can tell a solved plan "
            "from a listed one")

    c.equal(plan.stops[0].order, 1, "stops are numbered from one, in walk order")
    c.equal([stop.order for stop in plan.stops], [1, 2], "and the numbering is contiguous")
    c.equal([stop.box for stop in plan.stops], [1, 1], "every stop names the drawer to open")


def _multiplicity(c: Checks) -> None:
    """A section holding ONE copy does not satisfy a demand for TWO. The multicover check.

        section 1   A B        one copy of A, one of B
        section 2   A A        two copies of A

    Wanted: two A and one B. A plain set-cover solver answers section 1 alone — it "covers"
    both SKUs — and sends the operator to one drawer for a second copy of A that is not in it.
    The correct answer is two stops, and the copies asked for must add up to the demand.
    """
    inventory = _store([1, 3], ["A", "B", "A", "A"])
    ledger = _ledger({"A": 2, "B": 1})

    plan = walkplan.plan(inventory, ledger, ["tcg:1"])

    c.equal(plan.counts.stops, 2,
            "two copies of A and one of B cannot come out of one drawer here — a set-cover "
            "solver answers one and is wrong at the shelf")
    c.equal(_taken(plan), {"A": 2, "B": 1},
            "and the plan asks for exactly the copies the order owes, counted rather than "
            "named")
    c.equal(plan.counts.copies, 3, "three copies across the walk")
    c.equal(plan.shortfall, (), "nothing is short: the store holds three A and one B")

    per_stop = {stop.section: {t.sku: t.wanted for t in stop.takes} for stop in plan.stops}
    c.ok(
        sum(take.get("A", 0) for take in per_stop.values()) == 2,
        "the two A copies are divided between the drawers that actually hold them",
        f"per stop: {per_stop!r}",
    )

    # EVERY COPY IS OFFERED, NOT `wanted` OF THEM (D93, D97). The plan says how many to take
    # and never which — a stop holding two copies of A lists both even where it is asked for
    # one.
    section_two = [stop for stop in plan.stops if stop.section == 2]
    if c.ok(bool(section_two), "section 2 is in the walk"):
        takes = {take.sku: take for take in section_two[0].takes}
        if c.ok("A" in takes, "and it is there for A"):
            c.equal(len(takes["A"].copies), 2,
                    "both of its copies of A are listed, however many it is asked for — the "
                    "machine ranks and the person reaches")


def _shortfall(c: Checks) -> None:
    """An unfillable SKU is reported, and does NOT make the instance infeasible.

        section 1   A C        one copy of C in the whole store
        section 2   A

    Wanted: three C and one A. C has one supplier holding one copy, so the demand for three is
    capped at one BEFORE the solve. Leaving it uncapped makes the constraint unsatisfiable and
    the whole plan unanswerable — which on the owner's store would be the ordinary case, not
    an edge one: 23 of the 59 SKUs their forty open orders want cannot be filled at all.
    """
    inventory = _store([1, 3], ["A", "C", "A"])
    ledger = _ledger({"C": 3, "A": 1})

    plan = walkplan.plan(inventory, ledger, ["tcg:1"])

    c.ok(plan.counts.stops > 0,
         "the plan still answers — an unfillable SKU is reported, never a refusal")
    c.equal(len(plan.shortfall), 1, "one SKU is short")

    short = plan.shortfall[0]
    c.equal(short.sku, "C", "and it is C")
    c.equal((short.wanted, short.on_hand, short.short), (3, 1, 2),
            "three wanted, one on hand, two short — the arithmetic the foot of the screen "
            "draws")
    c.equal(short.orders, ("tcg:1",), "and whose order it is")
    c.equal(_taken(plan).get("C"), 1,
            "the one copy that DOES exist is still walked to — capping the demand must not "
            "drop the card")
    c.equal(_taken(plan).get("A"), 1, "and the fillable line is unaffected")

    # AND THE CAP IS WHAT MAKES THAT TRUE, asserted rather than assumed. Handing `solve` the
    # RAW demand — three copies of a card the store holds one of — is an unsatisfiable
    # instance, and it is refused by name. This check is the reason `Uncoverable` exists: with
    # the cap removed and no refusal, the greedy walk simply ran out of useful stops and
    # returned a PARTIAL cover shaped exactly like a plan, and every assertion above stayed
    # green over it. Found by mutating the cap, not by reading the code.
    stocks = walkplan.supply(inventory, ["A", "C"])
    refused = c.raises(
        walkplan.Uncoverable,
        lambda: walkplan.solve(stocks.per_stop, {"C": 3, "A": 1}),
        "an UNCAPPED demand is refused by name rather than answered with a partial cover",
    )
    c.ok("C" in str(refused or ""),
         "and the refusal names the SKU nothing can fill",
         f"message was {str(refused or '')!r}")
    c.ok(
        walkplan.solve(stocks.per_stop, {"C": 1, "A": 1}).chosen,
        "the same instance capped at availability solves — the cap is the whole difference",
    )


def _pooled(c: Checks) -> None:
    """A pooled game is ONE stop, LAST, and never a section (D24).

    Two boxes in one store here: the ordinary one, and a pooled record that has no place at
    all. A code card is a count — the index survives as a key because the photo is named after
    it, but there is no drawer to open and no divider to count to. Drawing it as a section
    would send a hand looking for plastic that does not exist.
    """
    inventory = _store([1], ["A"])
    inventory.boxes["2"] = master.Box(box=2)
    for index, sku in enumerate(["P", "P"], start=1):
        inventory.cards[master.position_key(2, index)] = master.Card(
            box=2,
            index=index,
            sku=sku,
            state=master.IDENTIFIED,
            capture_id=f"cap-2-{index}",
            game="pokemon_code",
        )
    ledger = _ledger({"A": 1, "P": 2})

    plan = walkplan.plan(inventory, ledger, ["tcg:1"])

    c.equal(plan.counts.stops, 2, "one drawer and one pooled stop")
    c.equal([stop.pooled for stop in plan.stops], [False, True],
            "and the pooled stop is LAST — it is not a reach, so it does not sit between two "
            "that are")

    last = plan.stops[-1]
    c.equal((last.box, last.section), (None, None),
            "a pooled stop carries no box and no section — absence, not a zero a hand could "
            "walk to")
    c.equal(last.game, "pokemon_code", "it names its game instead")
    c.equal(last.game_display, "Pokémon code cards", "with the registry's own display name")
    c.equal(plan.counts.boxes, 1,
            "and it is not counted among the boxes, because it is not one")
    c.equal(_taken(plan).get("P"), 2, "both pooled copies are still asked for")

    pooled_sections = [stop for stop in plan.stops if stop.pooled and stop.section is not None]
    c.equal(pooled_sections, [], "no pooled stop is drawn as a section, by construction")


def _stood_down(c: Checks) -> None:
    """A STOOD-DOWN line owes zero and is not walked to. The owner's ruling, 2026-09-17.

    Their words, asked before the code was written: *"If I stand a line down, it should say
    owed 0 and not send me to the drawer for those lines."* `close_line` is the operator
    saying they will not ship that line. The ledger still reports `outstanding` above zero for
    it, because that is a fact about the ORDER — `Ledger.unfulfilled` reads `closed` beside it
    rather than subtracting it, and its docstring has the argument. A walk asks the other
    question, so it must not route a hand to that drawer.

    THE SPEC WAS AMENDED IN THE SAME COMMIT AS THIS CHECK. Section 5's formula was written
    without the carve-out, and the first draft of `pipeline/walkplan.py` applied one unasked.
    That was the wrong order. The ruling is now in the spec, in the module, and here.

    Two lines, so that the check sees a walk CHANGE rather than merely disappear: `A` stays
    open and `B` is stood down. A solver that ignores `closed` walks to both drawers.
    """
    inventory = _store([1, 2], ["A", "B"])
    ledger = _ledger({"A": 1, "B": 1})

    before = walkplan.plan(inventory, ledger, ["tcg:1"])
    c.equal(before.counts.stops, 2, "both lines open, so the walk is two drawers")

    ledger.close_line("tcg:1", "B", reason=order_store.CLOSE_REASONS[0])
    c.equal(ledger.recorded("tcg:1", "B").closed, True, "the line is now stood down")
    c.ok(ledger.outstanding("tcg:1", "B") > 0,
         "and the LEDGER still reports it outstanding — a fact about the order, which is what "
         "makes this a real filter rather than an arithmetic coincidence")

    after = walkplan.plan(inventory, ledger, ["tcg:1"])
    c.equal(_taken(after).get("B"), None,
            "the stood-down line owes zero here: nothing in the walk asks for B")
    c.equal(after.counts.stops, 1,
            "and the drawer that only held B is dropped — one reach saved, which is the whole "
            "point of the ruling")
    c.equal(_taken(after).get("A"), 1, "the open line on the same order is untouched")
    c.equal(after.shortfall, (),
            "a stood-down line is not a SHORTFALL either — the store can fill it, nobody is "
            "asking it to")


def _exact(c: Checks) -> None:
    """`exact: false` is REACHABLE, by handing the solver a budget it cannot meet.

    The budget is checked at the top of every node, before any bound is computed, so zero
    seconds exhausts on entry and the greedy incumbent comes back flagged. This is the check
    the flag exists for: a solver that falls back to greedy silently returns the same SHAPE as
    one that proved the optimum, and no screen can tell them apart. It must be possible to
    make this false, or nobody has ever seen the flag work.

    The same instance with the ordinary budget is proved, which is what says the difference is
    the budget rather than the fixture.
    """
    inventory = _store([1, 5, 8], ["A", "B", "C", "D", "A", "B", "E", "C", "D", "F"])
    ledger = _ledger({sku: 1 for sku in "ABCDEF"})

    starved = walkplan.plan(inventory, ledger, ["tcg:1"], budget_s=0.0)
    c.equal(starved.counts.exact, False,
            "a budget of zero comes back FLAGGED rather than quietly greedy")
    c.equal(_taken(starved), {sku: 1 for sku in "ABCDEF"},
            "and the incumbent it returns is still a real cover — every wanted copy is asked "
            "for, it is simply not proved shortest")
    c.equal(starved.counts.stops, 3,
            "the greedy incumbent, which is one drawer longer than the proved answer — the "
            "cost of the exhausted budget, made visible")

    proved = walkplan.plan(inventory, ledger, ["tcg:1"])
    c.equal(proved.counts.exact, True,
            "the same instance under the ordinary budget is proved, so the flag tracks the "
            "budget and not the fixture")


def _cost_name(c: Checks) -> None:
    """Exactly one cost function is legal today, and an unknown one is refused BY NAME.

    Defaulting a typo to `sections` would hand back a plan the caller did not ask for and
    cannot tell apart from the one they did. The legal values go in the message, because a
    refusal that does not say what would have worked is a second round trip.
    """
    inventory = _store([1], ["A"])
    ledger = _ledger({"A": 1})

    c.equal(walkplan.COST_NAMES, ("sections",),
            "one name is legal: sections counted flat, boxes free (the owner's ruling)")

    refused = c.raises(
        walkplan.UnknownCostFunction,
        lambda: walkplan.plan(inventory, ledger, ["tcg:1"], cost="by_box"),
        "an unknown cost function is refused rather than defaulted",
    )
    c.ok("sections" in str(refused or ""),
         "and the refusal names what would have worked",
         f"message was {str(refused or '')!r}")

    named = walkplan.plan(inventory, ledger, ["tcg:1"], cost="sections")
    c.equal(named.cost, "sections", "the plan says which cost function produced it")

    # A KEY THE LEDGER DOES NOT HOLD IS SKIPPED, NOT REFUSED — the route's own rule (§7),
    # decided here where the key is first looked up.
    unknown = walkplan.plan(inventory, ledger, ["tcg:1", "tcg:does-not-exist"])
    c.equal(unknown.counts.stops, named.counts.stops,
            "an order key the ledger has never ingested contributes nothing and raises "
            "nothing")


def _take_order(c: Checks) -> None:
    """A stop's `takes` rank DENSEST FIRST — the owner's ruling, 2026-09-18, read off main
    rather than the earlier draft of the spec. `buildWalkPlan`'s `cardsHere` in
    `app/src/Orders.tsx` does the same thing one level up: `count` descending, tie broken on
    something stable. `Take` carries no name, so the tie here is `sku` ascending instead.

    One stop, three SKUs, deliberately picked so that ALPHABETICAL AND DENSEST-FIRST GIVE
    DIFFERENT ANSWERS — a fixture where they agree would go green over the regression this
    check exists to catch:

        A   wanted 1
        M   wanted 2
        Z   wanted 2

    Alphabetical (the defect): A, M, Z. Densest first with the sku tie-break: M, Z, A — M
    and Z tie at two and M sorts first; A is last on one. Getting M ahead of Z on the tie
    proves the tie-break is really `sku` and not, say, insertion order.
    """
    inventory = _store([1], ["A", "M", "M", "Z", "Z"])
    ledger = _ledger({"A": 1, "M": 2, "Z": 2})

    plan = walkplan.plan(inventory, ledger, ["tcg:1"])

    c.equal(plan.counts.stops, 1, "one section holds every copy, so the walk is one stop")
    stop = plan.stops[0]
    c.equal(
        [take.sku for take in stop.takes],
        ["M", "Z", "A"],
        "densest first (M and Z, both wanted twice) then the singleton (A) — never the "
        "alphabetical A, M, Z a plain `sorted(take_counts)` would produce",
    )
    c.equal(
        [take.wanted for take in stop.takes],
        [2, 2, 1],
        "and the counts fall with the order: 2, 2, 1",
    )

    # THE PLAN DOES NOT RESHUFFLE ON A SECOND READ. Same snapshot, same ledger, computed
    # again: an operator who reopens the screen must see the same order, not a coin flip
    # `sorted` on a dict would not even risk — this is what makes the tie-break MEANINGFUL
    # rather than merely present.
    again = walkplan.plan(inventory, ledger, ["tcg:1"])
    c.equal(
        [take.sku for take in again.stops[0].takes],
        [take.sku for take in stop.takes],
        "a plan asked for twice over the same snapshot does not reshuffle",
    )
