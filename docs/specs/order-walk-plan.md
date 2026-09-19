# The order walk is a plan, not a list

**Status: the solver and the route are BUILT. The screen is NOT BUILT.** `pipeline/walkplan.py`
implements sections 5 and 6, and `harness/tests/t11_walk_plan.py` is its contract. Section 7's
`POST /orders/walk-plan` is built now (`server/capture_server.py:do_order_walk_plan`,
`app/src/server.ts:walkPlan`, `app/src/types.ts:WalkPlan`). It composes every label through
`_Places.of` — `pipeline/join.py:Position` — rather than a second formula. Section 8's screen
is separate work. No code exists for it yet. The route is reachable from no screen, which by
CLAUDE.md's own rule means the capability is not landed. The owner ruled on this document on
2026-09-17, before any of it was written.

**Three architectural calls were put to the owner on 2026-09-17 and ruled on.** They are
settled in this document and are not open questions: the solver runs **on the server**;
`buildWalkPlan` is **replaced, not extended**; and the plan does not move **inside a pass**,
where a pass is one press of Start to the end of that walk and nothing longer (section 8,
which carries the owner's own words).

**What it replaces.** `#/orders`'s `Walk the boxes` stage, and the sentence block, the
`By order` fold and `buildWalkPlan` around it. `#/orders` and `#/shipping` stay two stages of
one screen and two routes. No new route appears in `App.tsx`'s `ROUTES` table.

---

## 1. The complaint

On 2026-09-17 the owner looked at `#/orders` after D212 (every copy is fungible, so no order
claims one) landed and said *"This is so stupid."* Three reviewers judged the screen cold,
barred from the repo, the docs and the history. They converged. Ranked by what each cost:

1. **Over-pulling has no stop.** A line wanting **2** copies drew **10 live Pull buttons**
   across four box groups. Nothing greyed out. Nothing counted down. The quantity was said
   once, in a sentence block scrolled far above the rows. The owner's ruling: *"It's not
   inherently wrong to overpull... it's just unintuitive, it should just close after the 2
   selections are met (of course with a little period to undo in case if I've misclicked)."*
2. **No card photographs.** `#/orders` is the only card-pulling screen in this product
   without them. `#/inventory` and `#/fulfillment` both lead with a large photograph, the
   card's physical neighbors and a position bar. Owner: *"Yup."*
3. **No cross-order walk by default.** `By buyer` walks one buyer Box 1 → 2 → 3, then the
   next buyer starts again at Box 1. Thirty-nine buyers is thirty-nine traversals of one
   shelf. `Walk the boxes` already flattens correctly and is the second tab, with its
   relationship to the first never stated.
4. **A wall of sentences.** `WalkCards` draws one line per card reading
   `Card name — Pull 1 — 6 on hand across 3 boxes.` Nine lines on a real order, ungrouped and
   uncollapsed. No other screen speaks this way. Owner: *"Horrible."* It was added earlier
   the same day by the orchestrating session and is that session's own mistake to undo.
5. **The good part is hidden.** `buildWalkPlan` already ranks stops fullest-first, behind an
   unstyled `By order` text toggle with no chevron and no button styling. A reviewer found it
   by hunting and called it the at-a-glance thing the owner asked for, buried behind the
   least discoverable control on the page. Owner: *"Yup."*

## 2. What the owner asked for

Their words: *"depending on the orders selected to walk, it dynamically adjusts which sections
I could pull from first, with the idea being that of all the orders selected to walk, what is
the least amount of total sections I need to scavenge through to satisfy all selected
orders."*

**Two rulings are already given and are not reopened here.**

- **The cost is SECTIONS, counted flat. More boxes is acceptable.** The owner also said they
  would like to change this by mood later (*"maybe we need a settings tab lol"*). So the cost
  function is a named, swappable input to the solver. **No settings tab is specified.** The
  wire carries the cost function's name; today exactly one name is legal.
- **Selection is: tick the orders, then walk.** The plan covers exactly the ticked set.

## 3. The mandate that shapes every part of this

The owner: boxes and sections *"aren't supposed to be so demanding / taxing on how we
build/operate."*

The operator must not have to think in the box and section taxonomy. The screen says *open
this drawer, take these four*, and the addressing stays the machine's problem. Today it is the
reverse — the taxonomy is on screen and the arithmetic is in the operator's head. Every
section below is judged against that sentence.

This does not delete the taxonomy. Sections become the thing being minimised, so section
fragmentation gains a purpose it never had. It is the machine's unit now, not the operator's
vocabulary.

## 4. Why this is possible only now

**D212, every copy is fungible, so no order claims one.** Before it, `pipeline/orders.py`'s
`_Draw._taken` handed each line up to `line.quantity` pre-chosen copies and withheld them from
every later order in the pass. There was no freedom. A solver had nothing to choose between.
D212 removed the exclusive draw: every line now carries every candidate copy the store holds,
and the refusal moved to the write, `store/orders.py:record_pull`'s `CopyAlreadyPulled`.

That is the choice space this solver works in. It did not exist three days ago.

D212 also named this cost, and it is this document's inheritance: `GET /orders` went from
54–98ms to 520–580ms on the day it became correct. The route specified in §7 is a second tier
over the same snapshot, not a third resolution of the whole ledger.

## 5. The model

### Demand

For each ticked order, for each of its lines, the **outstanding** copy count:

```
demand[sku] = Σ over ticked orders of max(0, line.quantity − progress.recorded[sku])
```

`recorded` is the ledger's, from `OrderRow.progress`, not the resolver's `fulfilled` — the
reason `figureOf` already gives: `ResolvedLine.fulfilled` is `len(picks)`, which since D212 is
what could be offered, never what has been taken.

**Amended 2026-09-17, on the owner's ruling: a STOOD-DOWN line owes zero.** Their words, asked
before the code was written: *"If I stand a line down, it should say owed 0 and not send me to
the drawer for those lines."* So a line whose `LineProgress.closed` is set contributes nothing
to `demand`, whatever `outstanding` still reads. `Ledger.unfulfilled` already reads `closed`
this way rather than subtracting it from `outstanding`, and its own docstring carries the
argument: "how many copies does this line owe" is a fact about the ORDER, and "is this store
still fetching it" is a fact about this store. A walk is the second question. `close_line` is
the operator saying they will not ship it, so routing a hand to that drawer spends a reach on a
card they already decided against.

`server/capture_server.py:_engine_order` deliberately does NOT apply this filter, and the two
do not conflict. It feeds the resolver, which answers the first question.

Demand is **capped at total availability** before the solve. A SKU the store cannot fill is
not the solver's problem; it is reported separately (§8, the shortfall block) and never makes
the instance infeasible. On the owner's store this is not a footnote: of the 59 SKUs the 40
open orders want, **23 cannot be filled from inventory at all**.

### Supply

For each section, the count of on-hand cards wearing each SKU:

```
supply[(box, section)][sku] = |{ cards in that section, state not in {sold, retired, moved} }|
```

A pooled game's cards (D24, `located: false`) have no section. They are **one synthetic stop
per game**, cost 1, always last in the walk order. They are not a section and must not be
drawn as one.

### The cost function

```
minimise  Σ over sections s of cost(s) · x[s]
subject to Σ over s of supply[s][k] · x[s]  ≥  demand[k]   for every sku k
           x[s] ∈ {0, 1}
```

`cost(s) = 1` for every section. That is the owner's ruling: sections counted flat, boxes
free.

**Why it is swappable, and what that costs.** The owner said they would want to change this by
mood. So `cost` is a named function selected by a string on the wire (`plan.cost`), resolved
server-side against a small table. The constraint shape never changes; only the objective's
coefficients do. Adding `cost_by_box` later is a table entry and a string, not a second solver.
**What this gives up:** a cost function that is not a per-section constant — "prefer the box I
am standing at", "prefer sections I have already opened this pass" — does not fit this shape,
because it makes cost depend on the solution rather than on the section. Those need a
different formulation and this design does not pretend otherwise.

### This is not plain set cover, and the distinction is load-bearing

Each section supplies *K* copies of a SKU; demand is *N* copies. A section holding three
copies of a card the walk wants three of covers that card alone; a section holding one does
not. Plain set cover cannot say that. This is a **minimum-cardinality set multicover**, an
integer program. Treating it as set cover would return plans that send the operator to a
drawer for a copy that is not there.

## 6. The solver

### Algorithm

Exact branch and bound, pure Python, in a new `pipeline/walkplan.py`. Four parts:

1. **Restrict.** Drop every section holding no demanded SKU. Clip each section's supply vector
   to the demand (`min(demand[k], supply[s][k])`) — surplus copies never change the answer.
2. **Dominance reduction.** Drop section *B* when some section *A* covers it componentwise on
   the clipped vectors. Safe for a min-cardinality objective under a constant cost, and it is
   where most of the search space goes.
3. **Greedy upper bound.** Repeatedly take the section covering the most outstanding copies.
   This is the incumbent the search improves on.
4. **Branch on the scarcest SKU**, never on section index. Pick the outstanding SKU with the
   fewest usable suppliers and try each supplier in turn, banning already-tried siblings.
   Bound: `|chosen| + ⌈outstanding / best single-section coverage⌉ ≥ |incumbent|` prunes.

### Measured, on the owner's real store

Read read-only from the running server on 2026-09-17 (`GET /orders`, `GET /boxes`,
`GET /inventory/<box>` for boxes 1, 2, 3, 4 and 6 — no POST, no restart).

**The store.** 5 boxes, 50 sections, 3,510 cards, 2,954 on hand. 48 sections hold at least one
on-hand card carrying a SKU; 2,947 such copies. 804 orders, 40 open, 275 walkable under
`ownsAWalkableBody`.

**The solve.** Worst of twenty random draws at each size below 40, exact in every case:

| ticked | SKUs | copies | candidate sections | optimum | boxes | greedy | exact solve |
|---|---|---|---|---|---|---|---|
| 1 order | 2 | 4 | 1 | 1 | 1 | 1 | 0.0 ms |
| 5 orders | 16 | 22 | 11 | 8 | 4 | 8 | 0.3 ms |
| 10 orders | 21 | 30 | 12 | 9 | 4 | 9 | 0.4 ms |
| 20 orders | 31 | 53 | 17 | 12 | 4 | 12 | 0.9 ms |
| all 40 open | 36 | 69 | 18 | 14 | 4 | 14 | 1.1 ms |
| all 275 walkable | 202 | 619 | 41 | 41 | 4 | 41 | 27.9 ms |

**Exact is cheap. No heuristic is taken, and no dependency is added.** The naive
branch-on-section-index formulation was tried first and did not finish the 275-order instance
in 30 seconds; branching on the scarcest SKU with dominance reduction solves it in 27.9 ms.
The difference is the formulation, not the language.

**No solver library.** This venv is Python 3.9.6 with no `scipy`, and `requirements.txt` argues
every dependency it carries. A 1.1 ms pure-Python solve does not earn a new one.

### What the plan is worth, measured

Over the 40 open orders on the owner's store, counting section visits:

| | section visits |
|---|---|
| today, `By buyer` — 39 buyers, each walking their own sections | **109** |
| today, `Walk the boxes` — the flat union of every offered copy's section | **29** |
| the plan | **14** |

### The honest half of that table

At full walkable scale the plan selects **41 of 41** candidate sections. The demand is spread
so wide that minimisation buys nothing, and greedy equals optimum in every row above. **The
solver earns its place on the ticked subsets the owner actually walks, not on the whole
ledger.** A design argued on the 109 → 14 line alone would be argued on a number that shrinks
as the tick list grows.

### Where it runs

**Server-side, in `pipeline/walkplan.py`.** The owner ruled this on 2026-09-17, on three
reasons, in order:

- This repo forbids pipeline logic in the browser, and "which copies satisfy which demand" is
  pipeline reasoning over inventory.
- The harness can test it. A solver in `Orders.tsx` is reachable only by a Playwright suite,
  which `make design-check` keeps off the commit path. A new `harness/tests/` case over a
  seeded store runs in `make harness`.
- It reads one `Store().read()` snapshot. The client would need the whole inventory to do the
  same arithmetic, which is the second store this repo does not have.

**The counter-argument, stated.** The client already holds every pick after
`POST /orders/picks`, so a browser solve would add no request. It is refused because of the
three reasons above, not because the data is absent.

## 7. The route

```
POST /orders/walk-plan
  { "keys": ["source:number", ...],        required, non-empty, same limit as /orders/picks
    "cost": "sections" }                   optional, defaults to "sections", one legal value
```

Body-addressed for `ORDER_PULL_FIELDS`'s own reason: an order key is `source:number` and a
number may legally carry a colon.

It follows `POST /orders/picks` exactly: one `Store().read()` snapshot, no lock, no write, a
key the ledger does not hold is **skipped rather than refused**, an empty `keys` list is
**refused rather than answered empty**. An unknown `cost` is refused by name, with the legal
values in the message.

```
{ "cost": "sections",
  "stops": [
    { "key": "box/3/section/6",
      "box": 3, "box_name": "WB1 R1", "section": 6, "section_name": null,
      "pooled": false, "game": null, "game_display": null,
      "order": 1,                       the walk order, ascending box then section
      "span": { "start": 242, "end": 284 },
      "takes": [
        { "sku": "8990745", "name": "...", "number_display": "...",
          "wanted": 2,                  this stop's share of the demand
          "for": [ { "key": "...", "number": "...", "buyer": "..." } ],
          "copies": [
            { "box": 3, "index": 271, "slot": 244, "capture_id": "...", "cid": "...",
              "card": 244, "label": "Box 3 · Section 6 · Card 244",
              "neighbors": { "prev": {...}, "next": {...} } } ] } ] } ],
  "shortfall": [ { "sku": "...", "name": "...", "wanted": 3, "on_hand": 1, "short": 2,
                   "for": [ ... ] } ],
  "counts": { "stops": 14, "boxes": 4, "copies": 69, "sections_considered": 48,
              "sections_candidate": 18, "exact": true, "solve_ms": 1 } }
```

**`copies` carries every copy of that SKU at that stop, not `wanted` of them.** D93 and D97
are unamended. The machine ranks, the person reaches. The plan says how many to take. It does
not pick which.

Two registers, not one. The owner's ruling, 2026-09-18, read off main rather than the earlier
draft of this sentence. `stop.takes` ranks densest first — `count` descending, same as
`buildWalkPlan`'s `cardsHere` in `app/src/Orders.tsx`. That is which card to reach for first.
A `Take`'s own `copies` rank front to back, ascending slot, per that file's own comment at
line 1381. That is which copy of one card, once a hand is at it. `buildCopyMap` ranks boxes
densest-first for a different screen and does not reach here.

**`cid` is a new field on a pick-shaped row.** `Pick` carries `box`, `index` and `capture_id`
but no `cid`, so today a photograph on this screen would be addressed by
`photoUrl(box, index)` rather than by the card's own name (D172, D183). Carrying `cid` here
lets the walk address photographs the way `#/inventory` and `#/fulfillment` do. It is one
field on one new route and amends nothing.

**`exact: false` is reachable and must be drawn.** The solver takes a wall-clock budget. If it
ever exhausts it, the greedy incumbent is returned and the screen says the plan is a good one
rather than the best one. A silent fallback to greedy is the failure mode this field exists to
prevent. On the owner's store today it has never fired.

## 8. The screen

`Walk the boxes` **becomes** this mode. It is not a third mode beside the existing two, and
`By buyer` keeps its own job: one person, one envelope, the ledger's own view (D193, D209).

### Selecting

**SUPERSEDED 2026-09-18 by the owner, after looking at the built screen. The replacement is
section 12. Read that, not this paragraph.** What this paragraph specified — a second list,
behind a mode tab, with a tick per row — was built exactly and is wrong. The owner's words:
*"I imagined an integrated screen, no separate tabs for By Buyer and Walk the boxes, just an
order screen, and in that screen I can be seeing the buyers and if I want tick next to their
names and then 'start the walk' rather than clicking a new tab, then operate a UI, then click
start."*

The original text, kept because section 12 is an argument against it: the buyer list gains a
tick per walkable order and one `Walk N orders` button. The default tick is every currently
open order, so the default press is the same press it is today. The plan covers exactly the
ticked set, and the head says so in the operator's units: **"Six drawers. Forty-one cards."**
Not sections, not boxes, not SKUs.

**The head's sentence survives section 12 unchanged.** It is the one part of this paragraph the
owner did not overturn.

### A stop

**The unit on screen is the drawer, with the cards at it.** Not one card at a time.
`#/fulfillment` shows one card because it serves a different job and a different person. The
owner's sentence is *one reach, take four*, and the stop is that reach.

One stop, top to bottom:

- **The instruction, in the operator's words.** *"Open WB1 R1. Take 4."* The box name leads;
  the number is the label beneath it. The section is drawn as **where in the drawer** — the
  span bar `#242–284 of 987` that `#/inventory` already draws — and never as the phrase
  `Section 6` standing alone, which is the taxonomy on screen the mandate forbids.
- **One row per card at this stop**, each leading with a **large photograph** at
  `#/inventory`'s size, the card's name beside it, its position bar, and its physical
  neighbors. This is the whole of finding number 2, and it is why the stop is the unit: four
  photographs at one drawer is a page; four photographs one card at a time is four pages.
- **The take count on the row**, as a counter and not a sentence: **`0 of 2 taken`**, beside
  the copies. It is the figure the owner had to scroll to find.
- **The copies**, each with its own Pull, ranked densest-first, every copy drawn and none
  preselected (D93, D97).
- **Who it is for** — the buyer's name — said per card, and only when the stop serves more
  than one buyer.

### How a row closes

This is finding 1, and the owner's ruling is the specification.

A row's demand is met the moment `taken == wanted`. On that press:

- The row's remaining Pull buttons are **disabled**, not removed. Removal moves what is around
  it, which D118 forbids.
- The row draws its completed state and its **Undo**, for `UNDO_WINDOW_MS` — **20 s**, the
  constant `Orders.tsx`, `Inventory.tsx` and `Fulfillment.tsx` already share. This is the
  owner's *"little period to undo in case if I've misclicked."*
- When the window closes, the row **collapses to one line** — the card's name, `2 taken`, and
  a chevron that opens it again. It does not leave the stop. A stop whose every row has
  collapsed collapses itself the same way.
- **Nothing re-ranks.** The stop order, the row order and the copy order are frozen for the
  pass, D181 and D118's rule applied to a walk: a take may not move what the hand is reaching
  for. A row that collapses reserves the height of its tallest state, so the collapse changes
  what is on the screen and never where the rest of it is.

**Over-pulling stays possible and stops being accidental.** Pull is disabled, not gone, and a
`Take another` control re-enables the row. The owner's own words: it is not inherently wrong
to overpull. It is wrong for it to be the path of least resistance.

**The undo window moves nothing.** An undo inside 20 s restores the row in place. The plan is
never recomputed, by any press (below).

### The pass, and why the plan does not move inside it

**A pass is one press of Start to the end of that walk, and nothing longer.** The owner, 2026-09-17:
*"I'm thinking of walk as every time I tick some orders and hit start this walk, only for that
period things remain frozen for me, not some longer duration than that. As soon as I finish
those that were ticked and return to the app then things can move."*

**Leaving the walk ends the pass** (the owner's ruling, same interview). Tap another screen,
close the tab, come back an hour later — that walk is over. The buyer list keeps the ticks. The
next Start builds a **fresh plan against the store as it is then**. One screen, one pass, and
no walk outlives the sitting it was built in.

**Inside a pass, the plan is computed once and does not move.** The owner, on what a mid-walk
change should do: *"maybe a toast spawns, but frankly I can't imagine a copy sold on another
screen ever happening, and a new order arriving shouldn't alter my walk."* So there is **no
`Re-plan` control**. An earlier draft of this document offered one and was wrong.

### Leaving mid-walk loses nothing, and the reason is where the write lands

**A pull is banked at the press, not at the end of the walk.** `store/orders.py:record_pull`
writes to the ledger the moment the button is pressed. So a pass abandoned after three pulls
has three pulls recorded, exactly as if it had run to the end.

**The next plan asks only for what is still owed.** Demand is `quantity − progress.recorded`
(section 5), so a banked copy is already out of the arithmetic. Nothing is asked for twice.

**A half-filled line simply shrinks, and may re-route.** Two copies wanted, one taken, the
second drawer never reached: the next plan wants one, and it may send the operator to a
different drawer than the first plan did. That is the solver being correct, not the plan
changing under a hand — it is a **new** plan, over what is left, in a new pass.

**The one real hole is not this plan's, and is recorded rather than fixed here.** The 20 s
undo lives only on a toast. `app/src/server.ts:undoPull` has exactly two callers in the whole
product, `Orders.tsx:undoFromToast` and `Fulfillment.tsx`, both of them toasts. Leave the
screen inside those 20 s and the undo dies with the toast: the card stays sold and no screen
offers a way back. The owner's ruling, 2026-09-17: fix it separately, as the reach of the pull
receipt across `#/orders` and `#/fulfillment` together, not as a clause of this document. This
paragraph exists so the gap is not discovered again from scratch.

Inside a pass, then:

- **A new order arriving does not touch the walk.** The walk covers the set ticked at the
  press. An order that arrives after it is simply not in it.
- **A copy that goes while the walk is open** marks its own row — `gone, skip` — and moves
  nothing around it (D118). The stop stays in the list at its own position even when every row
  in it has gone, because removing it would move the rest.
- **A toast is the ceiling of the interruption.** One toast, said once, and no banner, no line
  in the list and no control. The owner does not expect this state to occur.
- **`CopyAlreadyPulled` is the same shape.** The row that lost marks itself. The walk is
  unchanged.

This is D181's rule (the order is taken once, and a sale may not retake it) applied to a walk,
and D118's (a press changes what is on the screen, never where the rest of it is) applied to
the list the press sits in.

### The shortfall block

The plan cannot fill every SKU, and on this store it misses 23 of 59. One block, at the foot,
one line per card: what is wanted, what is on hand, whose order it is. It is not a stop and
carries no Pull. Today this state is scattered through per-line reason chips and is not
countable at a glance.

## 9. What is deleted

- **`WalkCards` and the sentence block go.** Finding 4, the orchestrating session's own
  mistake from earlier the same day. What the sentences said — how many to pull, how many are
  on hand, across how many boxes — is said by the take counter on the row and the stop the row
  sits in. No sentence replaces them.
- **`buildWalkPlan` is replaced, not extended** (the owner's ruling, 2026-09-17). It groups by BOX (`key = box/${pick.box}`),
  ranks by density, is scoped to **one order**, and tallies sections for display only. It is a
  sort. The plan is a cover with multiplicities across many orders. Nothing of its shape
  survives the change of unit, of scope and of objective. Its `PlanStop`/`PlanCard` types go
  with it.
- **The `By order` fold stops being a fold.** Finding 5 — the ranked view it hides becomes the
  default mode of `Walk the boxes`, so there is nothing left for the toggle to reveal. Under
  `By buyer`, one order's own stops stay reachable as a real `Button` with a chevron, in the
  kit, not an unstyled `<summary>`.
- **`buildWalk`'s grouping goes.** The client stops deriving stops from pick order; it renders
  `stops` as the route sends them. `buildCopyMap` stays — it answers the per-line question on
  `By buyer`, which is unchanged.

## 9a. What landed, and four things the first build got wrong

The route and the screen landed on 2026-09-18. The mechanics of section 8 are built and were
driven by hand in a real browser over a seeded store: the head reads the size in the operator's
units, the instruction leads with the box name, Pull DISABLES rather than vanishes, the counter
moves, Undo and `Take another` appear, nothing below the row moves, and there is no horizontal
scroll at 375px.

**Four layout defects shipped with it, found by the orchestrating session at the first render
and NOT by the agent that built it, which reported the screenshots as reviewed.** They are
recorded here rather than fixed in that round, on the owner's ruling: land it, then look at it,
then make one deliberate pass. The first is the serious one.

1. **THE TAXONOMY IS ON SCREEN, ON EVERY ROW.** Each card draws `BOX <name> · Box <n>` and
   `SECTION <n> · <name>` as labelled fields. Section 3 is the mandate every other section is
   judged against, and section 8 forbids this by name: the section is drawn as WHERE IN THE
   DRAWER and never as the phrase `Section 6` standing alone. The stop header already names the
   drawer, so the row repeats it and adds the divider on top. At 375px it costs four lines per
   card. This is the defect this whole document exists to remove, reintroduced one register
   down.
2. **Every row carries a raw order key** rather than the buyer's name, and carries it always.
   Section 8 says who it is for is the buyer's NAME, said only when the stop serves MORE THAN
   ONE buyer. It is neither conditional nor a name.
3. **The photograph is a thumbnail rather than `#/inventory`'s size.** Finding 2 of section 1
   was that this screen has no card photographs at all, and the remedy was a large photograph
   leading each row. At phone width it loses its space to defect 1.
4. **No position bar and no neighbours on the row.** Section 8 lists both. The row draws
   `Card 8` and stops. The stop's own span chip is present and correct.

5. **THE SELECTION IS A FLAT LIST AND NOTHING ELSE, AND THIS ONE IS THIS DOCUMENT'S FAULT.**
   `WalkSelect` draws one checkbox per walkable order, a `Walk N orders` button, and that is the
   entire component. There is no tick all, no untick all, no search, no status filter and no
   sort. Everything arrives ticked and the only way to narrow it is to untick rows one at a time.

   **The build matches this document exactly, which is the problem.** Section 8's "Selecting"
   specifies a tick per walkable order, one button, and every open order ticked by default. It
   says nothing about narrowing the list, so nothing was built. On a seven-order demo store the
   result looks correct, which is how it passed a render.

   **`By buyer` sits three inches away and has all of it**: a search box, four status chips
   (`All open`, `Every copy found`, `Short`, `Done`), a Newest and Oldest sort, and
   `Hide unknown SKUs`. The walk is the mode meant for the operator with the most on their plate
   — 275 walkable orders on the owner's own store, against 40 open — and it is the mode with the
   fewest ways to say what they mean.

   The owner, looking at the real screen on 2026-09-18: *"I immediately get everything all
   ticked with no other options, no untick all, no tick all, no 'open only', no other filters."*

   **RULED 2026-09-18: the walk BORROWS `By buyer`'s controls.** The owner's word: *"Just borrow
   for now."* Not a second vocabulary for the same job — the same chips, the same search, the
   same sort, so there is one set of behaviours to learn and one place they are decided.

   **What the ruling costs, stated rather than discovered.** Those controls are not components.
   They are inline JSX inside `PullStage` — the chips built as a local `chips` value, the search,
   the sort and `Hide unknown SKUs` each written in place. Borrowing them means EXTRACTING them,
   and the thing they are extracted out of is the mode this document does not touch. So the
   hazard is not the walk. It is breaking `By buyer` while lifting its own controls out from
   under it.

   **And the default press changes meaning, which follows from the ruling rather than being a
   separate one.** Section 8 made every open order ticked by default so the first press stays the
   press it is today. Once the list can be narrowed, a filter has to narrow BOTH the list and
   what the button covers, and the button has to say what it covers — `Walk 12 orders` where
   twelve is what survived the filter. A control that changes the list without changing the press
   is a control that lies about what the press will do.

   **AMENDED 2026-09-18, by the owner: nothing is ticked by default.** Section 12 carries the
   ruling. The button still says what it covers, and over an empty selection it is not offered
   at all.

   Findings 1 through 4 are deferred behind this one, on the owner's ruling. They are about the
   row read with a hand already in a drawer. This one is about reaching a drawer at all.

**A settled figure lost its footing, and this paragraph is the record rather than the ruling.**
D96's "N orders complete in this pass" head figure, and the boot-triggered clear beside it, are
GONE from the rebuild. That figure was twice amended and hard won: it existed because a lifetime
total was masquerading as a progress figure on the owner's own store. Nothing here answers its
argument. It simply has nothing left to attach to — `WalkPass` fetches the plan once and never
re-reads `GET /orders`, so there is no live comparison between what is open and what this pass
covers, and completion is now counted per card row rather than per order.

**This document does NOT rule D96 superseded.** A settled decision is an argument, and repealing
one is the owner's act, not a session's. What is recorded is that the argument is unanswered and
the mechanism is absent. Two ways out, for the owner: rebuild the figure client-side over the
orders already in hand and the pass's own recorded map, or rule D96 superseded here and say so in
an entry. One piece of D96 IS already reversed in the open, by section 8's own words: "leaving the
walk ends the pass" directly contradicts D96 amended's "a toggle is not the end of a pass," and
that reversal was the owner's, in the 2026-09-17 interview.

It is named here so it cannot be lost the way a silent revert is lost. `make docs-audit`'s
`recorded deletions` row and `make revert-guard` both exist because this repository has dropped
settled work by accident before.

**Two questions the build raised and nobody has answered.** They are design, not defects.

- **Which order a press records against**, when one card at a stop serves more than one buyer.
  The wire names every order a take serves and does not say how the demand splits between them,
  so the client picks. Today it takes the first order in `for` still owing by the live ledger
  figure. That is a rendering-side heuristic standing in for a fact the route could carry.
- **Whether the stop span should be a proportional bar.** `WalkPlanStop` carries no box total,
  so the screen draws the honest span numbers rather than fabricating a proportion.

## 10. What this gives up

- **The plan can be worse for a hand that is already at a drawer.** A constant per-section cost
  cannot know where the operator is standing. A plan of 14 sections may send them back to box 1
  after box 6. §5 says why that cost function does not fit this formulation.
- **Fewer sections is not always less work.** A section with 70 cards costs the same as one
  with 33 (both are real on this store). The owner ruled sections counted flat; this is the
  price of the ruling, and it is the first thing a second cost function would address.
- **A stale pass stays stale to its end.** Freezing is what stops the screen moving under the
  hand, and inside a pass the owner ruled it absolute. So there is no way to refresh a walk
  that has drifted. The remedy is to end the pass and press Start again, which is cheap —
  leaving the screen is what ends it, the ticks are kept and every pull is already banked. The
  trade is bounded by the pass, not by the day, and it is taken on the owner's own estimate
  that a copy going during a walk is a state they cannot imagine occurring.
- **A second operator is worse off than today.** D212 already named this: two hands pulling at
  once learn of a conflict only at `CopyAlreadyPulled`. A frozen plan makes the wrong walk
  longer before the refusal arrives. This design does not address two hands and should not be
  read as safe for them.
- **The minimisation is invisible when it does nothing.** At full walkable scale it selects
  every candidate section. The operator sees a plan either way and cannot tell a solved plan
  from a listed one. Nothing on screen distinguishes them, deliberately — a badge saying
  "optimal" would be noise on every screen where it is trivially true.
- **A collapsed row hides its copies.** The map D97 argues for is one press away rather than on
  screen. That is the cost of the wall of rows not returning in another form.
- **One more route on the order path.** `GET /orders`, then `POST /orders/picks`, then
  `POST /orders/walk-plan`. Three tiers where D212's follow-up was already asked to make the
  first one cheaper.
- **`#/orders` gets longer, not shorter.** Photographs at `#/inventory`'s size are the
  screen's pixel budget spent on the card (D32) and the scroll is the cost. The word count
  should fall (D194), because sentences are replaced by counters — but this design is not
  argued on the ratchet and must not be pinned to fit.

## 11. What would reopen this

- **The owner asks for a different cost function.** Expected — they said so. A per-section
  constant is a table entry; anything depending on the operator's position is a reformulation
  and a new entry.
- **A ticked set that does not solve exactly.** `exact: false` reaching the screen means the
  measurements in §6 no longer bound the real instances. The budget, the bound or the
  formulation is then the subject, not the screen.
- **A second operator.** Two hands change what a frozen plan is worth, and D212's own
  reopening condition is the same one. With no re-plan control at all, the second hand's walk
  cannot be corrected inside the pass — only ended and started again.
- **A copy going mid-walk turns out to be common.** The absence of a `Re-plan` control rests
  on the owner's estimate that it does not happen. A count of `gone, skip` rows over a month
  of real walks is the measurement that would settle it. If the number is not near zero, the
  control comes back — as a press, never as an automatic recompute, which stays refused.
- **The stop stops being the right unit.** If the owner walks with the phone in one hand and
  wants one card at a time after all, `#/fulfillment`'s unit is the answer and this document's
  §8 is what changes.
- **Sections stop fragmenting.** The whole objective assumes sections are finer than boxes. On
  this store they are — 50 sections over 5 boxes — and a store that stops sectioning makes the
  cost function equal to counting boxes.

## 12. One screen, and the list that is already there

**Ruled by the owner on 2026-09-18, looking at the built screen.** This section replaces
section 8's "Selecting" and makes finding 5 in section 9a moot rather than fixed. It is the
next piece of work and nothing in sections 1 to 7 changes.

### What is wrong with what was built

Three presses stand between the operator and a drawer: click a tab they were not on, work a
list they have never seen, press start. The middle list is a SECOND list of the same orders,
with none of the controls the first one has — no search, no status chips, no sort, no tick all,
no untick all. Everything arrives ticked. On the owner's store that is 275 rows.

**The second list should not be narrowed. It should not exist.** The screen already draws a
list of these orders, with every control, and the operator is already reading it. That list is
the selection.

### The shape

`#/orders` takes `#/inventory`'s frame. That frame is `.browse-body` in `app/src/BoxBrowse.css`:

```
grid-template-columns: 300px minmax(0, 1fr);     /* the rail, then the work */
[data-rail='collapsed']  52px  minmax(0, 1fr)
<= 1100px-ish            268px minmax(0, 1fr)
phone                    minmax(0, 1fr)          /* one column, stacked */
```

- **The left column is the orders**, the list that exists today, with every control it has
  today, and a tick per walkable row.
- **The main column is the walk**, the stops and their cards.
- **No mode strip and no `PullMode`.** `By buyer` and `Walk the boxes` stop being two modes of
  one screen and become one screen. The strip at `app/src/Orders.tsx:3127` goes, and so does
  `PullMode` in `app/src/OrdersHubStore.ts:21` and both branches on `mode === 'walk'` at
  `Orders.tsx:3156` and `:3256`.
- **`WalkSelect` in `app/src/OrdersWalk.tsx` is DELETED**, not improved. It is the second list.
- **One press starts the walk**, from the list the operator was already reading.

### What this settles, and what is left to the build

**Settled by the shape itself.** The filters and the search are the ones already on the screen, because there is
only one list now. A filter narrows what the press covers, because the list and the selection
are the same thing — the question section 9a raised about that answers itself here.

**Settled by the owner on 2026-09-18, answering this section's own three questions.**

**1. A tick does NOT survive a filter that hides its row.** Filter to `Short` and every buyer
who falls out of view loses the tick. Filtering back does not bring it back. The tick is a
property of the list as drawn, not a set held behind it.

This makes the filter a selecting tool rather than a view. The flow is: narrow the list, tick
what is left, press Start. Tick all and untick all act on the rows in view, because those are
the only rows that can hold a tick.

**3. Nothing is ticked by default.** The first draft ticked every open order so that the first
press matched the press before the walk existed. That argument is retired. The operator says
who the walk is for, every time, and an empty selection means Start is not offered.

**2 was not a question the owner could answer as asked, because "a frozen pass" was this
document's word and not defined here.** It is defined in section 8: from the press of Start to
the end of that walk, the plan is computed once and does not move. A new order does not join
it. A copy that goes elsewhere marks its own row and moves nothing around it. The freeze covers
the WALK, in the main column.

The left column is the orders list, and that list is live. It re-sorts on Ready to Ship (D209).
Rows change status under the hand. So one screen would hold a frozen walk beside a moving list.

**The answers above resolve it, and the resolution needs the owner's word.** The walk covers the
set that was ticked AT THE PRESS. Once Start is pressed the list is no longer the walk's input,
so the list may keep filtering, sorting and unticking without touching the walk. The two clocks
do not collide, because only one of them is read.

What that leaves open is what the ticks LOOK LIKE during a pass, and it is small enough to
decide at build time with the owner watching: the ticks stay as the operator left them and are
simply not read again, or the press clears them, which says plainly that the walk is now its own
thing.

### Sequencing

1. The three questions above are answered. What the ticks look like during a pass is decided
   at build time, in front of the owner.
2. Build the frame and move the list into it. This is the whole of the layout change and it
   touches `Orders.tsx`, `OrdersWalk.tsx`, their sheets and `OrdersHubStore.ts`.
3. Delete `WalkSelect`, the mode strip and `PullMode` in the same change. A half-removed mode is
   worse than either state.
4. Findings 1 through 4 in section 9a, deferred behind this on the owner's word. They are the
   ROW read with a hand already in a drawer. This section is about reaching a drawer at all.

### What the next session must not repeat

**`make check` DOES NOT RUN THE BROWSER SUITE.** `make design-check` is deliberately outside it
(DEBT16). The agent that built section 8's screen ran `make check`, got exit 0, and reported the
screen verified. Thirteen tests in `app/tests/orders.spec.ts` were red on CI, all of them
asserting the walk section 9 had deleted. Run `make design-check` before claiming a screen
works, and check the verdict's own `counts.total` — a `PW_ARGS` `--grep` containing spaces
silently becomes a file filter and runs other tests green.

**The suite is the only thing that reads these screens, and it asserts the OLD walk in places.**
Removing the mode strip will break tests that click it. Rewrite them against the rule they were
protecting, re-aim them if the subject moved, and delete only with the claim named — section 9a
records what a quiet deletion cost this document already.

**Render it against a store with real volume.** Finding 5 passed a render because the demo store
holds seven orders. The defect only appears at the owner's 275. A screen that looks right on the
fixture is not verified.

**Never `git stash` in any worktree of this clone.** The stack is per-clone, not per-worktree, so
another session's pop takes it. Commit to set work aside. `git show <rev>:<path>` or a `.bak`
copy to read a baseline.
