# The order walk is a plan, not a list

**Status: BUILT.** The solver, the route and the screen all exist. `pipeline/walkplan.py`
implements sections 5 and 6, and `harness/tests/t11_walk_plan.py` is its contract. Section 7's
`POST /orders/walk-plan` is `server/capture_server.py:do_order_walk_plan`, with the client call
`app/src/server.ts:walkPlan` and the type `app/src/types.ts:WalkPlan`. It composes every label
through `_Places.of` (`pipeline/join.py:Position`) and never through a second formula. The
screen is `#/orders` (section 13). `#/fulfillment` reads the same route for its Owed section.

**Three architectural calls are settled.** The solver runs **on the server**. The old
client-side `buildWalkPlan` was replaced and not extended. The plan is a live read of the
walked set, and it does not move on a press (section 8).

`#/orders` and `#/shipping` are two rows of the shell and two routes (D274). No route was added
to `App.tsx`'s `ROUTES` table for the walk.

---

## 1. What the screen must do

Five rules, ranked by cost. Each one is a rule the screen keeps.

1. **Stop over-pulling.** A row closes when its demand is met, and the copy keeps an undo
   (section 8). Over-pulling stays possible. It must not be the path of least resistance.
2. **Show card photographs.** `#/inventory` and `#/fulfillment` lead with a large photograph,
   the card's physical neighbors and a position bar. The walk does too.
3. **Walk across orders.** The walk covers the whole ticked set in one traversal. Walking one
   buyer after another would send the operator through box 1, 2 and 3 for each buyer.
4. **Use counters and not sentences.** One sentence per card is a register no other screen
   uses.
5. **Rank fullest-first by default.** The ranked view is the default order and is not behind a
   toggle.

## 2. What the owner asked for

The owner's words: depending on the orders selected to walk, the screen dynamically adjusts
which sections to pull from first. Across all selected orders, it uses the least total sections
that satisfy them.

**Two rulings are given and not reopened.**

- **The cost is SECTIONS, counted flat. More boxes is acceptable.** The owner may change this
  by mood later. So the cost function is a named, swappable input to the solver. **No settings
  tab is specified.** The wire carries the cost function's name. Today exactly one name is
  legal.
- **Selection is: tick the orders, then walk.** The plan covers exactly the walked set.

## 3. The mandate that shapes every part of this

The owner: boxes and sections should not be so demanding on how the app is built and operated.
The operator must not have to think in the box and section taxonomy. The screen says which
place to open and which cards to take. The addressing is the machine's problem.

This does not delete the taxonomy. Sections become the thing that the solver minimizes. They
are the machine's unit and not the operator's vocabulary. Every section below is judged against
that sentence.

## 4. Why this is possible only now

**D212, every copy is fungible, so no order claims one.** Before it, `pipeline/orders.py`
handed each line up to `line.quantity` pre-chosen copies and withheld them from every later
order in the pass. The solver had nothing to choose between. D212 removed the exclusive draw.
Every line now carries every candidate copy that the store holds, and the refusal moved to the
write, `store/orders.py:record_pull`'s `CopyAlreadyPulled`. That is the choice space this
solver works in.

D212 also named a cost that this document inherits. `GET /orders` became slower when it became
correct. The walk route is a second tier over the same snapshot. It is not a third resolution
of the whole ledger.

## 5. The model

### Demand

For each walked order, for each of its lines, the **outstanding** copy count:

```
demand[sku] = Σ over walked orders of max(0, line.quantity − progress.recorded[sku])
```

`recorded` is the ledger's, from `OrderRow.progress`. It is not the resolver's `fulfilled`,
which since D212 is what could be offered and never what has been taken.

**A stood-down line owes zero.** A line whose `LineProgress.closed` is set adds nothing to
`demand`, whatever `outstanding` reads. `Ledger.unfulfilled` reads `closed` the same way. "How
many copies does this line owe" is a fact about the ORDER. "Is this store still fetching it" is
a fact about this store. A walk asks the second question. `close_line` is the operator saying
that they will not ship it, so a hand must not go to that drawer.
`server/capture_server.py:_engine_order` does not apply this filter. It feeds the resolver,
which answers the first question.

Demand is **capped at total availability** before the solve. A SKU that the store cannot fill
is not the solver's problem. It is reported as `shortfall`, and it never leaves the instance
without a solution.

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

`cost(s) = 1` for every section (`COST_SECTIONS` in `COST_FUNCTIONS`). That is the owner's
ruling: sections counted flat, boxes free.

**Why it is swappable, and what that costs.** `cost` is a named function, selected by a string
on the wire (`plan.cost`) and resolved server-side against a small table. The constraint shape
never changes. Only the objective's coefficients do. Adding `cost_by_box` later is a table
entry and a string, and not a second solver. **What this gives up:** a cost that is not a
per-section constant does not fit this shape. "Prefer the box I am standing at" and "prefer
sections I have already opened" make cost depend on the solution and not on the section. They
need a different formulation.

### This is not plain set cover, and the distinction is load-bearing

Each section supplies *K* copies of a SKU, and demand is *N* copies. A section with three
copies of a card that the walk wants three of covers that card alone. A section with one does
not. Plain set cover cannot say that. This is a **minimum-cardinality set multicover**, an
integer program. Treating it as set cover would send the operator to a drawer for a copy that
is not there.

## 6. The solver

### Algorithm

Exact branch and bound, pure Python, in `pipeline/walkplan.py`. It has four parts.

1. **Restrict.** Drop every section that holds no demanded SKU. Clip each section's supply
   vector to the demand (`min(demand[k], supply[s][k])`). Surplus copies never change the
   answer.
2. **Dominance reduction** (`_dominated`). Drop section *B* when some section *A* covers it
   componentwise on the clipped vectors. This is safe for a min-cardinality objective under a
   constant cost, and it removes most of the search space. A cost that is not constant breaks
   it.
3. **Greedy upper bound** (`_greedy`). Repeatedly take the section that covers the most
   outstanding copies. This is the incumbent that the search improves on.
4. **Branch on the scarcest SKU** in `solve`, never on section index. Pick the outstanding SKU
   with the fewest usable suppliers. Try each supplier in turn, and ban the siblings already
   tried. The bound `|chosen| + ⌈outstanding / best single-section coverage⌉ ≥ |incumbent|`
   prunes.

**Exact is cheap, so no heuristic is taken and no dependency is added.** Branching on the
section index did not finish a real 275-order instance. Branching on the scarcest SKU with
dominance reduction solves it in milliseconds. The difference is the formulation, and not the
language. No solver library is used, because `requirements.txt` argues every dependency it
carries, and a millisecond solve does not earn a new one.

### What the plan is worth

The plan is worth most on the ticked subsets that the owner actually walks. At full walkable
scale the demand spreads so wide that the plan selects every candidate section, and greedy
equals the optimum. A design argued on the whole ledger would be argued on a number that shrinks
as the tick list grows. Unmeasured now: the current store's figures. The harness does not
re-measure timing, because a timing assertion on a shared CI machine is a flake and not a guard
(`harness/tests/t11_walk_plan.py`).

### Where it runs

**Server-side, in `pipeline/walkplan.py`**, for three reasons.

- This repo forbids pipeline logic in the browser, and "which copies satisfy which demand" is
  pipeline reasoning over inventory.
- The harness can test it. A solver in the browser is reachable only by a Playwright suite,
  which `make design-check` keeps off the commit path. A case over a seeded store runs in
  `make harness`.
- It reads one `Store().read()` snapshot. The client would need the whole inventory to do the
  same arithmetic, which is the second store that this repo does not have.

The client already holds every pick after `POST /orders/picks`, so a browser solve would add no
request. It is refused for the three reasons above and not because the data is absent.

## 7. The route

```
POST /orders/walk-plan
  { "keys": ["source:number", ...],        required, non-empty, capped at ORDER_PICKS_LIMIT
    "cost": "sections" }                   optional, defaults to "sections", one legal value
```

The body carries the keys, because an order key is `source:number` and a number may legally
carry a colon. The route follows `POST /orders/picks`. It takes one `Store().read()` snapshot,
takes no lock and writes nothing. A key that the ledger does not hold is **skipped and not
refused**. An empty `keys` list is **refused and not answered empty**. An unknown `cost` is
refused by name, with the legal values in the message.

The answer is `WalkPlan` in `app/src/types.ts`:

- `cost`: the cost function's name.
- `stops[]` (`WalkPlanStop`): one reach each. It has `key`, `box`, `box_name`, `section`,
  `section_name`, `pooled`, `game`, `order` (1-based, the drawn order), `span` and the box
  total, so the span chip can read `#242–284 of 987`. Its `takes[]` (`WalkPlanTake`) carry `sku`,
  `name`, `number_display`, `wanted`, `for[]` (the orders that want it, each with `owed`) and
  `copies[]`.
- `shortfall[]`: SKUs that the store cannot fill, with `wanted`, `on_hand` and `short`.
- `counts`: `stops`, `boxes`, `copies`, `sections_considered`, `sections_candidate`, `exact`
  and `solve_ms`.

**`copies` carries every on-hand copy of that SKU in the whole store, and not `wanted` of them.**
The stop's own copies come first, densest first. Every other copy follows in box-walk order, by
box and then by order key (D294). D93, D97 and D212 hold: the machine ranks, the person reaches.
The plan says how many to take. It does not pick which.

Each copy is a `WalkPlanCopy` with its `key`, `state`, `has_photo`, `capture_id`, `cid`, `here`
(the copy stands at this stop) and full `place`. The route reads the store-wide copies from the
snapshot it already holds. It never calls `search()` per card. On a large walk that would be one
whole-store read per card.

**Two registers, not one.** `stop.takes` rank densest first (`count` descending). That is
which card to reach for first. A take's `copies` rank front to back, by slot. That is which copy
of one card, once a hand is at it.

**`cid` is on each copy**, so the walk addresses a photograph by the card's own name (D172,
D183), as `#/inventory` and `#/fulfillment` do.

**The route uses the ordinary `_Places`.** It is lazy per box. This route runs once per walked
set and covers only the boxes that the plan touches, which the solver keeps few. So the
neighbor decoration is affordable here. `do_orders` uses a narrower constructor, because its
picks span most of the store.

**`exact: false` is reachable.** The solver takes a wall-clock budget (`DEFAULT_BUDGET_S`).
When it runs out, the greedy incumbent returns, flagged. No screen draws the flag today. **That
is unbuilt.** A silent fallback to greedy is the failure that the field exists to prevent. So a
screen that draws a plan should say that the plan is a good one and not the best one. The
harness asserts that `exact` can be false (`harness/tests/t11_walk_plan.py`).

## 8. The screen

`#/orders` is one screen (section 13). The walk is not a separate mode with its own tab.
Selecting an order in the rail starts its walk at once, as opening a box in `#/inventory` does.
The rules below hold for the walk in that screen.

### Selecting

- **Nothing is ticked by default.** The operator says who the walk is for, every time. With no
  order selected, no walk runs.
- **A tick does not survive a filter that hides its row**, and filtering back does not bring it
  back. The stored set is pruned. A render-time intersection would hand the tick back when the
  filter clears. `app/tests/orders.spec.ts` asserts both directions. The walk says how many
  buyers a filter took out of it (`walkNote`).
- **The bulk tick controls act on the rows in view**, because those are the only rows that can
  hold a tick. One control toggles every shown buyer into the walk (`Walk N`, and `Stop` when
  all are ticked).
- The walked set is the selected order plus every ticked one. The walk covers the orders that
  own a walkable body (`ownsAWalkableBody`), and not only the open ones. A shipped order can
  still owe copies.
- **Opening a buyer is not ticking one.** `#/orders` opens the first buyer in the list on its
  own, as `#/inventory` opens its first box. The tick set stays empty. On a phone no sheet
  opens by itself.

### The plan moves when the walked set moves, and on nothing else

`app/src/OrdersWalkPane.tsx:useOrderWalk` fetches `POST /orders/walk-plan` again when the key
set changes, and never on a press. An answer for any other key set is dropped, whenever it
lands. There is no `Re-plan` control. A new order that arrives is not in the walked set, so it
does not touch the walk. A copy that goes while the walk is open marks its own row and moves
nothing around it (D118). The stop stays in the list even when every row in it has gone,
because removing it would move the rest. A toast is the ceiling of the interruption.
`CopyAlreadyPulled` has the same shape: the row that lost marks itself.

**The freeze is about RANKING, and never about where a card sits.**

- **Held while the walked set stays the same:** which places the walk visits and which cards
  it asks for. Also the order of the stops, the rows and the copies. A pull re-solves nothing. This is D181 and D118 applied to the walk.
- **Refreshed on every pull, for the rows still ahead in the box that changed:** the card's
  neighbors, its own number and its position bar. These are not the plan. They describe a card
  that is still the same card at the same place in the list, said correctly and not stale.

The walk's own normal operation forces this. The solver packs a walk into few drawers, so two
cards at one stop are likely to be neighbors. Pull the first, and D58 renumbers everything
after it in that box. The second card's neighbor line would then name a card that is gone. So
**all positional facts refresh together, or none do**. A line between them would be arbitrary,
and they come back in one query.

`POST /orders/pull` takes `refresh` and answers `refreshed`, in both directions. `refresh` is a
list of `{box, index}` that the caller still draws and is not pulling. It carries no
`capture_id`, because nothing is aimed at. `refreshed` is one post-write `Place` per position
whose box the press touched. A position in any other box is skipped. `places` stays the
pre-write receipt. `useOrderWalk` keeps a `facts` map and folds `refreshed` into it. A row that
has gone blanks its own neighbor line.

Nothing here may move anything on screen (D118). A refreshed fact changes the text inside a row
that is already there, at a height already reserved. A row that grows or shrinks on another
row's press is this rule built wrong.

### How a row closes

A copy is pressed with **Mark sold**, the same button and word as `#/inventory` (D57). On this
screen the press also records the copy against an owing order. D212 says no order claims a
copy, and the write refuses a full line.

- The row's figure is **Pick N of M** (D279, D212). `M` is capped at what is on hand
  (`take.copies.length`). A card that is too short drops `of M` for a short flag, such as
  `Pick 1` beside `7 short`. `M` must never count a copy that the store does not have.
- **Undo is per copy and has no clock** (`docs/specs/undo.md` §2-3, D164). A copy's `Undo`
  stays until a newer pull takes the "newest" rank from it, or the walk resets.
  `UNDO_WINDOW_MS` is only the toast's own lifetime.
- **The pane does not advance itself** (UN-6). A new card must not light under the finger that
  just sold. The sold copy's row turns into `Undo` in place (D57). Nothing else moves (D118).
  The operator steps on `J` and `K`.
- **Hide picked folds on a press and never on a sale** (D304, D263, D118). A sale that lands
  while it is on leaves the row in place. It folds at the next press or load.
- **A stop can hold more candidates than a take wants.** Then the row says `(either)`, because
  every copy is fungible. It never picks one for the operator (D97).
- **The pass's own tally and the plan's snapshot decide which order a press records against.**
  A live re-read never decides it. `_walk_plan_order_ref` puts `owed` on every ref: the
  ledger's own `outstanding`, zeroed for a stood-down line. `pickOrderFor` takes the ref whose
  remaining (`owed` less what this walk has recorded against it) is smallest and still
  positive. It returns `null`, never `for[0]`, once no ref owes. Ties go to the order placed
  longest ago. The order closest to done is the one that a single short copy is most likely to
  finish. `pickOrderFor` must never fall back to `for[0]`, because that sends presses to an
  already full order (`over_fulfilled`). This rule decides only which OPEN order a press records
  against. It never decides which physical copy answers it. Do not put the options "decide at
  Start, keep live, or ask at the press" to the owner again.

### Leaving mid-walk loses nothing, and the reason is where the write lands

**A pull is banked at the press.** `store/orders.py:record_pull` writes to the ledger when the
button is pressed. A walk abandoned after three pulls has three pulls recorded. **The next plan
asks only for what is still owed**, because demand is `quantity − progress.recorded`. A
half-filled line shrinks and may re-route. That is a new plan over what is left. It is not a
plan that changed under a hand.

### The shortfall

The plan reports the SKUs that the store cannot fill, in `shortfall`. `#/orders` draws that state
per line, as reason chips and in the buyer's own figures (section 14). It does not draw a
separate block. `Fulfillment.tsx` counts `plan.shortfall`, so its empty state never claims that
nothing waits.

## 9. What is deleted

- **`WalkCards` and the sentence block.** Counters replace them.
- **`buildWalkPlan`.** It grouped by box, ranked by density, covered one order and tallied
  sections for display. It was a sort. The plan is a cover with multiplicities across many
  orders. Nothing of its shape survived the change of unit, scope and objective.
- **The `By order` fold as a hidden ranked view**, and `buildWalk`'s grouping. The client renders
  `stops` as the route sends them and derives none.
- **`WalkSelect`, the mode strip, `PullMode` and `HubState.mode`.** The rail is the selection.
- **The walk-only pane and row.** `#/orders` reuses `CardPane` and `CardLocations` whole (D304).
  The walk-only stop, take header, copy row, bars and pill were deleted and not adapted.

## 9a. Rules from the first builds

1. **Do not design a walk-only row.** `CardLocations` already draws the photograph, the position
   bar and the neighbors. The taxonomy on every row is the defect that this document exists to
   remove.
2. **A list of orders needs the controls that the order list already has.** Search, status
   filter, sort and tick-all belong to the one list that the operator reads (section 12).
3. **Verify a screen against volume.** A small fixture hides defects that show at hundreds of
   orders.
4. **`make check` does not run the browser suite.** `make design-check` is outside it (DEBT16).
   Check the verdict's own `counts.total`. A `PW_ARGS` `--grep` with spaces silently becomes a
   file filter.
5. **D97's "N orders complete in this pass" head figure is gone.** The walk holds no pass. D97's
   argument is unanswered and not repealed. The owner ruled that the figure is not needed now.
   A rebuild could count it off the presses of the walk.

## 10. What this gives up

- **The plan can be worse for a hand that is already at a drawer.** A constant per-section cost
  cannot know where the operator stands. A plan of 14 sections may send them back to box 1
  after box 6. Section 5 says why that cost does not fit this formulation.
- **Fewer sections is not always less work.** A section with 70 cards costs the same as one with
  33. That is the price of the flat-cost ruling, and a second cost function would address it
  first.
- **The plan does not refresh mid-set.** Ranking is held while the walked set stays the same.
  The remedy for a drifted plan is to change the walked set, which re-solves it. Every pull is
  already banked.
- **A second operator is worse off than today.** D212 named this. Two hands that pull at once
  learn of a conflict only at `CopyAlreadyPulled`. This design does not address two hands.
- **The minimization is invisible when it does nothing.** At full walkable scale it selects
  every candidate section, and the operator cannot tell a solved plan from a listed one.
  Nothing distinguishes them on screen, deliberately. A badge that says "optimal" would be
  noise where it is trivially true.
- **A collapsed row hides its copies.** The map that D97 argues for is one press away and not on
  screen.
- **One more route on the order path.** `GET /orders`, then `POST /orders/picks`, then
  `POST /orders/walk-plan`.

## 11. What would reopen this

- **The owner asks for a different cost function.** A per-section constant is a table entry.
  Anything that depends on the operator's position is a reformulation.
- **A ticked set that does not solve exactly.** `exact: false` in a real answer means that the
  solver's budget, bound or formulation is the subject, and not the screen.
- **A second operator.** Two hands change what a held ranking is worth. D212's own reopening
  condition is the same one.
- **A copy going mid-walk turns out to be common.** The absence of a `Re-plan` control rests on
  the owner's estimate that it does not happen. A count of `gone, skip` rows over real walks
  would settle it. If it is not near zero, the control comes back as a press. An automatic
  recompute stays refused.
- **Sections stop fragmenting.** The objective assumes sections are finer than boxes. A store
  that stops sectioning makes the cost function equal to counting boxes.

## 12. One screen, and the list that is already there

**The walk selects from the list that the operator is already reading.** That list is the
selection. There is no second list behind a tab.

- **The left column is the orders**, with every control the list has (search, status, sort) and
  a tick per walkable row.
- **The main column is the walk.**
- **No mode strip.** `By buyer` and `Walk the boxes` are one screen. The filters that once hid
  when the walk began are the selecting tool now.
- **A filter narrows what the walk covers**, because the list and the selection are the same
  thing.
- **The walk covers the set that is walked.** The list may keep filtering, sorting and
  unticking. A change to the walked set re-solves the plan (section 8).

## 13. Orders is inventory's screen with orders in the rail

**The owner's rule:** walking an order is a tweaked way of routing inventory. It is a tailored
prompt that still uses the inventory engine. The left portion of the inventory screen turns into
orders, and the sort is by density. The owner also said: use Inventory's UI and words exactly.
**Do not design a stop, a row or a walk-only component where Inventory already has one.** If
the walk needs something the card pane does not draw, add it to Inventory, and both screens
get it.

**`#/inventory` is not touched.** `#/orders` is its own row (D274) and takes Inventory's
skeleton: the rail, the card pane, the strip between them and the header. The layout, the row
detail, the pane and the phone order are D304's. D220 and D274 hold the arguments.

### The header

Inventory's: `Orders`, one line under it, and a count chip at top right.

### The rail

1. **The search slot:** the buyer search, the status select and the sort (D296).
2. **Where Inventory lists boxes, Orders lists orders.** One row per buyer, with the buyer,
   the placed date, what is left with its bar, and the status. A tick sits beside each walkable
   row. Clicking an order selects it and its walk starts at once. Ticking others joins them to
   the walk, live, and each tick re-plans. There is no Start button. Clicking B while walking A
   replaces A. The walked set is the selected order plus every ticked one.
3. **Where Inventory shows the box panel, Orders shows the selected order's panel.** It has the
   order id, the buyer's name, `Manage`, the status pill and the census figures in the kit's
   `bn-stat`. **Behind `Manage`** are the Add orders well (fetch and paste), the fetch receipt,
   the status picker and both stand-down prompts.
4. **The strip:** `collapse all`, the section count and `Hide sold`, as Inventory draws it.
   `Hide sold` reads Inventory's own stored key (D132).
5. **Where Inventory lists sections and cards, Orders lists the walk.** Boxes and sections come
   in density order (the solver), the cards sit under each, the current card is lit, and sold
   copies fold under `Hide sold`. A press on a card lands on it. `J` and `K` step through the
   walk list.

### The main pane

Inventory's card pane: `CardHero.tsx:CardPane` for the head, and `CardLocations`
for every on-hand copy with its position facts. The walk's chosen copy comes first (D212). The
copies in the section that the operator stands in come first. The order is held for the walk
(section 8). A sale refreshes the positions as Inventory already does. No Details fold sits on
this screen (D304). The card's details table stays on `#/inventory` alone. **`Mark sold` is
the button and the word.**

### Words

Inventory's only: box, section, card, copy, on hand, sold, Mark sold. The buyer row's
"all pulled" reads "all sold". The order pill reads **`Ready`**, one word. A typed middle dot is
in no string (D218).

A nameless buyer's name slot reads `MM-DD-YY_XXXXX`. `app/src/orderView.ts:unnamedBuyerLabel`
composes it once: the group's placed date in UTC, an underscore, and the last five characters of
the group's most recent order id. `BuyerRow`, `OrderPanel`, the phone rail chip and the Manage
sheet's title all read it. A nameless group holds one order today, because `orderBuyers.ts` keys
a nameless order on itself. The full id stays in the order slot alone.

### Answers after review

- **Copy budget (D284).** The reused pane carries Inventory's vocabulary. Hiding facts on one
  screen would make the two panes differ, so the words are kept.
- **`#8 of 34` is the whole caption on every screen**, with no `so far`. The section line reads
  `card 7 of 14` for a growing section and `card 7 of 14 slots` for a settled one.
- **The pane's `market` and `listings` facts come from the same reads as `#/inventory`.**
  `POST /inventory/copies` answers `listings` beside `cards`. Unknown: where in `Orders.tsx` the
  market read is wired today.
- **Small readings that were defects.** A buyer row's per-order pill shows the status word and
  not the order's number. "Hide unknown SKUs" filters `sku_unseen`, the "Never seen" chip's own
  reason. The bulk tick controls read "Tick shown" and "Untick shown", as `#/inventory` says.

## 14. The screen's own arithmetic, one formula, one unit

**Every count `#/orders` draws over one open order's lines reconciles in one unit: copies.** Sum
this formula line by line, over any set of open orders:

```
owed = pick + short + elsewhere
```

- `owed` is `line.owed`. What the order still wants.
- `pick` is `line.owed - line.outstanding`, summed only where positive. What the resolver can
  offer now. `cardsToPull` sums this the same way over whichever set is walked.
- `short` is `line.outstanding` where the line's reason is `no_copies_on_hand` or `short`. Both
  reasons name one fact: nothing is left on hand for this SKU. The split exists only so
  `statusOf` can rank a buyer who got some above one who got none. A screen states both as one
  bucket, "short".
- `elsewhere` is `line.outstanding` where the reason is `sku_unseen`, `sku_unknown` or
  `not_a_single`. This store has never carried the SKU, or the line is sealed product. A
  compact chip states only their sum.

The header and the walk's count answer two different questions. One counts the whole store. The
other counts only the walked subset. Neither said which question it answered, so together they
read as one contradicted claim. The header states its own breakdown once (`verdictOf`). It is a
stat row like Inventory's box panel: copies owed, buyers, to pick, and not in boxes
(`short + elsewhere`). Each label names its unit, so a copy count never reads as buyers. A
reader can see that the identity holds without needing the walk's number to match. A buyer row
draws its owed copies as a bare number, and the header says the unit once. The opened buyer's
pane splits that number into to pick and not in boxes, then sold.

A buyer chip must not disagree with that buyer's own figures. `lookWords` sums every reason's
`outstanding`, never `owed` and never only the loudest reason. One reason explains the whole
total, and the chip names it ("7 short"). Two or more reasons together read "N review".

## 15. Every copy is fungible, and the row says so

A take's slot list can outnumber what it wants. `wanted = 1` over two candidate cards at the
same stop is not an error. It is D212 reaching the row. Without a word, a row that prints both
card numbers reads as "take both". So `OrdersWalkPane.tsx` appends `(either)` only when the stop
holds more candidates than the take wants. It never picks one for the operator (D97). It says
that the choice is free.

## 16. The walk rejoins Inventory's own components

`D304` (orders walk reuses Inventory's rows) names where the built screen drifted from D220 and
D274. This section holds the one argument that belongs in this spec: the sort key.

**The sort key changes, and only in `plan`.** `StopKey.walk_order` has four callers in
`pipeline/walkplan.py`. Three are the solver's own determinism, and stay untouched: `_dominated`
(the order dominated stops are dropped in), `_greedy` (the order candidates are offered in,
which breaks ties) and `solve` (the supplier order that the exact search walks). The fourth,
`plan`, is the drawn order. A change to `walk_order` itself can change which stops the solver
picks on a tie. That would change what the walk holds, and not only its order.

So `plan` alone changes. Its key is `_drawn_key`: `(pooled flag, density, natural name key of
inventory.box_title(box), section)`. Density is `Stop.copies`, the count of cards that the
stop's takes already ask for. The box name breaks a tie only, in natural order, so "WB1 R2"
sorts before "WB1 R10". The name is never the hidden box number (D259). Pooled stops stay
last.

Every reader of the drawn order follows the wire:

- `do_order_walk_plan` and `_walk_plan_stop` serialize `result.stops` in order and send
  `order`.
- `OrdersWalkPane.tsx:rowsOf` sorts nothing of its own.
- `app/src/Fulfillment.tsx` folds `plan.stops[].takes[]` to one entry per SKU, and the screen
  must keep first-seen order wherever a person sees it.
- `app/src/orderView.ts`'s "Fewest drawers" buyer sort reads counts, and not order.
- `harness/tests/t11_walk_plan.py` asserts that `order` is contiguous from 1, and has a case
  with two boxes whose number order and name order disagree.

## 17. How each screen ranks a search — one shared record

Inventory and the Orders walk both lead with section density. They break a tie the same way.
D132 (Inventory) and D304 (the walk) each point here.

**Inventory's box rail under a search** (`app/src/BoxBrowse.tsx`'s `order`):

1. Main key: the most LIVE copies of the answer in the box's best section. A box is ranked by
   its fullest section, never by its total. Only the best rank tier that still has a live copy
   counts.
2. Tie: the box's natural name (`boxTitle`, digit runs compared as numbers, so "Box 2" comes
   before "Box 10").
3. Then the box's own `bid`, newest first, then the box number.

**The Orders walk** (`pipeline/walkplan.py`'s `_drawn_key`):

1. Main key: `Stop.copies`, the density of the section. Pooled stops last.
2. Tie: the box name from `box_title`, in natural order (`_natural_key`).
3. Then the section number.

**With no search**, Inventory ranks by this device's box recency, then `bid`, then the box
number (D132). The walk has no no-search order.

**The order is frozen once taken** (D181, D118, `app/src/frozenRank.ts`). A copy that left since
the order was taken still counts for its section. So a sale never re-ranks a list under the hand
that made it. The walk's ranking is held the same way (section 8).

One difference stays. Inventory's natural sort is the platform's `Intl.Collator` with
`numeric`. The walk's is `_natural_key`. Python and TypeScript cannot share one function. The
two agree on digit runs and case, and may differ on punctuation and accents.
