# Lane A of PR 4B: the Orders walk becomes Inventory's screen

Status: a design and a build plan. NOTHING IS BUILT. The owner approves the mockups and answers
the questions at the end before any lane below starts. The governing plan is
`PLAN-PR4-PR5.md` in this folder, section "A. Orders: the walk becomes Inventory's screen".

## The owner's direction, numbered

The numbers are the pins on the mockups.

1. Inventory's left rail becomes the Orders buyer list, with checkboxes and "Walk all N buyers".
2. The walk list keeps its style: grouped by section, with "Pick N of M". Sort by box NAME, then
   section.
3. Every pick row carries Inventory's location detail: box, section and card, the section strip,
   the back-to-front ruler, and the neighbour names. Mark sold works on the row. Reuse
   Inventory's own components. Never fork them.
4. A click on a row fills the right pane with the photo and the card facts. Below them goes
   every on-hand copy, in Inventory's copies list, with the walk's chosen copy first.
5. Lane E makes a sold walk row stay in place until the next load. Lane A must keep that fix.
6. On a phone, the buyer shows before the photo.

## The mockups

The HTML is in this folder. It is built from the real Inventory DOM, read off the public demo.
It links the app's own CSS: `tokens.css`, `kit.css`, the three `kit/*.css`, and the component
files (`BoxBrowse.css`, `CardLocations.css`, `PositionBar.css`, `PlaceNeighbors.css`,
`CardHero.css`, `Orders.css` and others). `mock.css` holds only what the build would add, and
the numbered pins. Every name is a demo name. Every box is shown by its name (D259, a box is
shown only by its name).

- `desk.html`: the recommended layout (layout R below), at 1440 and 820.
- `desk-walk-in-rail.html`: the walk inside Inventory's 300px rail, read literally. It is the
  evidence for question Q1.
- `phone.html`: 390, the buyer before the photograph.
- `render.cjs`: draws the PNGs.

THE PNGS ARE NOT TRACKED. `scripts/githooks/pre-commit` refuses any image outside the demo photo
folders, because a code-card photo is a bearer instrument. The brief asked for the PNGs in this
folder. That conflicts with the opsec rule, so they go outside the repository:

```
NODE_PATH=app/node_modules node docs/reviews/ux-2026-09-23/orders-a/render.cjs <out-dir>
```

It writes `desk-1440-{light,dark}.png`, `desk-820-{light,dark}.png`,
`phone-390-{light,dark}.png` (the first screen), `phone-390-scroll-{light,dark}.png` (the whole
page, fixed bars hidden) and `alt-walk-in-rail-1440-light.png`. No render scrolls sideways.

What each state shows:

- The buyer list with ticks and "Walk all 70 buyers" (pin 1). Jane Doe 805 is selected.
- A walk in progress, sections in box-name order: WB1 R1, WB1 R3, WB1 R4 (pin 2). Today the
  same walk draws WB1 R3 before WB1 R1.
- Each pick row with its copies, each copy drawn as an Inventory `CardLocations` row: the box,
  section and card, the neighbours, the section strip and the ruler, and Mark sold (pin 3).
- A sold copy still in place with "Hide picked" on, reading "Sold" with its Undo (pin 5).
- The right pane: Inventory's hero head (name, number, set, game, place, pills), the photo,
  then "Every copy of this card" with the walk's chosen copy first and marked current (pin 4),
  then the Details fold.
- The phone: the buyer panel, then the card, then the walk (pin 6).

## Where the built screen drifted from D220

D220 (Orders is Inventory's screen with orders in the rail, and the walk is a mode of it). Each
line names the rule and what is built. D274 (Orders and Shipping are two sidebar rows, and the
walk gets the full height) ruled some of these on purpose. Those lines say so.

1. **The pane.** D220: "The main pane is inventory's card pane, one component, reused whole."
   Built: `OrdersWalkPane.tsx:WalkCardPane`, a walk-only pane with its own `orders-card-*`
   classes. Its copy rows draw the kit `Location` alone: no `PositionBar`, no `PlaceNeighbors`,
   no hero head, no Details fold. D274 ruled this ("The pane is no longer inventory's whole
   pane (UX-169)"). The owner's point 4 now reverses that part of D274.
2. **The hero head is shared by nobody.** D220 says that `CardHero.tsx` holds the hero head,
   the photograph and the Details fold, and that both screens import them. Built:
   `CardHero.tsx:CardHeroHead` has no caller. `BoxBrowse.tsx` draws its own hero head inline,
   and the two differ. The inline head draws the state pill only as an exception (UX-221). The
   dead one always draws it. Orders imports only `PhotoPanel` and `marketTable`.
3. **The walk list is a walk-only component.** Spec §13: "Do not write a walk-specific component
   where inventory already has one." Built: `OrdersWalkPane.tsx:WalkList` draws
   `orders-walk-*` rows with the slot numbers and the name only. It shares `SectionTitle` and
   nothing else. The owner's point 2 keeps this style on purpose. So the drift to fix is the
   missing location detail (point 3), not the row itself.
4. **The skeleton.** D220: "`#/orders` is `#/inventory`'s skeleton with orders where the boxes
   are." Built: `Orders.tsx:PullStage` lays out its own `orders-layout` grid (`Orders.css`,
   container `orders`, 560 and 1000). It uses no part of Inventory's `browse-body`,
   `browse-map` or `browse-side`. D274 ruled the three-column shape. The rail frame (sticky,
   fits the window, D289) is not reused.
5. **The walk order is neither density nor name.** D220's owner quote says
   `in order walk it's sorted by density`. Built: `pipeline/walkplan.py:plan` sorts the chosen
   stops by `StopKey.walk_order`, which is the hidden box NUMBER, then the section. Density
   ranks only the takes inside one stop. The demo walk for Jane Doe 805 draws WB1 R3, WB1 R1,
   WB1 R4.
6. **A box number can still reach the screen.** D259 (a box is shown only by its name). Built:
   `OrdersWalkPane.tsx:stopTitle` falls back to `Box ${stop.box}` when `box_name` is null. The
   server sends a null `box_name` for a stop whose takes carry no copies
   (`server/capture_server.py:_walk_plan_stop`).
7. **A sold row folds at once.** D263 ruling 2: "A sold row stays in place, marked sold, until
   the next box load or refresh." Built: `WalkList` filters a picked line out under Hide picked
   at the press. Lane E owns this fix. Lane A builds on top of it.
8. **The phone draws the buyer under the photograph.** D274 puts one buyer line first under
   560, then the card, then the walk. Built at 390 on the demo: the buyer chip, the card pane,
   then `OrderPanel` below the photograph. Point 6 moves the buyer first.

## The layout: two readings of point 1

Point 1 says that Inventory's left rail becomes the buyer list. D220 put the walk in that rail
too, where Inventory's section list is. The walk rows now carry a full `CardLocations` row per
copy (point 3). That row needs width.

- **Layout L, the walk in the 300px rail (D220 read literally).** `desk-walk-in-rail.html`.
  Measured at 1440x900: the rail fits the window (D289). After the buyers and the order panel,
  the walk list gets a 320px window. One copy row takes about 210px at 300px wide. The owner
  sees one pick at a time.
- **Layout R, recommended.** One container, three registrations, D274's own breakpoints:
  - 1000px of column and up: three columns. Inventory's rail frame holds the filter bar and the
    buyer list (sticky, it fits the window, its list scrolls). The walk column holds the order
    panel, the strip and the walk list, on the page's own scroll. The card pane is sticky.
  - 560 to 999: Inventory's own skeleton. The rail holds the buyers (3.5 rows, D289) over the
    walk. The card pane is beside it and sticky.
  - Under 560: the buyer panel, then the card, then the walk.

## The component reuse map

"As is" means that the lane imports it unchanged. "Prop" means that it gets one new optional
prop, and every existing caller stays unchanged. "Split" means that code moves out of a file
into a shared home, and the old caller imports it back.

| Piece | Home today | Reuse | Why |
|---|---|---|---|
| Section strip and ruler | `PositionBar.tsx:PositionBar` | As is | Reached through `CardLocations`. Orders passes `sections` from one `getBoxes()` read, as `Inventory.tsx` does with `layoutsOf`. Orders reads no box layouts today. |
| Neighbour names | `PlaceNeighbors.tsx:PlaceNeighbors` | As is | The walk wire's `place` already carries `neighbors` (`_copy_row`, the place block `/search` sends too). |
| Box, section and card | `CardLocations.tsx:RowIdentity` | As is, inside `CardLocations` | Not exported. No need to export it. |
| Copies list (pane) | `CardLocations.tsx:CardLocations` | As is | `preserveOrder`, `currentKey`, `soldKeys`, `renderAction` and `sections` already exist. `preserveOrder` was built for the walk. |
| Copies list (walk row) | `CardLocations.tsx:OwnerRows` | Prop | A `head={false}` prop draws the rows without the heading, the stats and the SKU line. The wrapper opens a `copies` container, so the rows take the narrow layout. |
| Photo | `CardHero.tsx:PhotoPanel` | As is | Orders already uses it. |
| Card facts, Details fold | `CardHero.tsx:CardDetailsSection` | As is | `correctable` stays false: correction is Inventory only (D252, a wrong answer gets a correct route). |
| Hero head | inline in `BoxBrowse.tsx:BoxBrowse`, dead copy in `CardHero.tsx:CardHeroHead` | Split | Move the inline head into `CardHeroHead`, with slots for the place line, the extra chips and the actions. Inventory imports it back. Delete the dead divergence. Orders adds a "Pick N of M" pill in the chip slot. |
| Card pane frame | inline in `BoxBrowse.tsx:BoxBrowse` (`browse-card`, `browse-band`, then Details) | Split | A `CardPane` in `CardHero.tsx`: the head, the band and the Details fold. Below 560px of pane the band already stacks the copies under the photo (`BoxBrowse.css`, `@container pane`). In layout R that is point 4's "below them". |
| Rail frame | inline in `BoxBrowse.tsx:BoxBrowse` (`browse-map`, the `--browse-rail-rest` measure) | Split | A `RailFrame` with the rest-top measure and the fit-to-window height (D289 rule 2). Inventory passes its box list and walk. Orders passes its buyer list. |
| Buyer rows, ticks, "Walk all" | `Orders.tsx:BuyerRow`, the `buyerList` in `PullStage` | As is | They move into the rail frame. |
| Walk list | `OrdersWalkPane.tsx:WalkList` | Keep, extend | Point 2 keeps its style. Each line gains the take's here-copies as `CardLocations` rows (head off). |
| Mark sold, Undo | `OrdersWalkPane.tsx:RowAction` | As is | Handed to `CardLocations` as `renderAction`, in the row and in the pane. |
| Section title | `SectionTitle.tsx:SectionTitle` | As is | Already shared. |

## The sort change: box name, then section

`StopKey.walk_order` has four callers in `pipeline/walkplan.py`. Three of them are the solver's
own determinism. One is what the screen draws:

- `_dominated`: the order in which dominated stops are dropped.
- `_greedy`: the order of candidates, which breaks ties.
- `solve`: the supplier order that the exact search walks.
- `plan`: `walk = sorted(solution.chosen, key=lambda k: k.walk_order)`. This is the drawn order,
  and `Stop.order` numbers it.

RECOMMENDATION: keep `walk_order` as it is, and change only the sort in `plan`. A change to
`walk_order` itself can change which stops the solver picks on a tie. That changes what the walk
holds, not only its order. `plan` already holds the `inventory`, so the new key is
`(pooled flag, name key of inventory.box_title(box), section)`. `store/master.py:box_title`
composes a box's name, and the refusals already use it. Pooled stops stay last.

Every caller of the drawn order:

- `server/capture_server.py:do_order_walk_plan` and `_walk_plan_stop`: they serialize
  `result.stops` in order and send `order`. No change.
- `app/src/OrdersWalkPane.tsx:rowsOf`: "Nothing here sorts." No change. The screen follows the
  wire.
- `app/src/Fulfillment.tsx`: it folds `plan.stops[].takes[]` to one entry per SKU. The lane
  checks whether that fold keeps first-seen order anywhere a person sees it.
- `app/src/orderView.ts`: the "Fewest drawers" buyer sort reads counts, not order. No change.
- `harness/tests/t11_walk_plan.py`: asserts that `order` is contiguous from 1. A new case adds
  two boxes whose number order and name order disagree.

## How the state flows

- **Selection.** Unchanged: `selectedKey` plus `walkTicked` make `walkedKeys`. A click on a
  buyer selects it and starts the walk. A tick joins the walk live. The URL keeps `?buyer=`
  (D285, a screen's filter state lives in the URL).
- **The walk.** Unchanged: `useOrderWalk` reads `POST /orders/walk-plan` once per key set.
  `rows` and `sections` follow the wire. `current` is the row the pane shows.
- **The chosen copy.** `currentRow.copy.key` becomes the `currentKey` of `CardLocations`. The
  pane's group is `currentGroup` in the wire's order, this stop's copies first (D212, every copy
  is fungible). The pane passes `preserveOrder`, so no fullest-section rank reorders it.
- **Sold in place.** `receipts` and `soldKeys` stay in `useOrderWalk`. Lane E decides when a
  sold row folds: on the next load. Lane A reads the same `soldKeys` for the walk row and the
  pane, and adds no fold of its own. A walk row's height must not change on a sale (D118, a
  press changes what is on the screen, never where the rest of it is).
- **Section layouts.** One `getBoxes()` read on the screen, turned into a map with
  `Inventory.tsx`'s own `layoutsOf`. It moves to a shared home, and it is not copied. It feeds
  the `sections` of `CardLocations` in both places.
- **Market and listings.** `CardDetailsSection` takes the per-run market read that the pane
  keeps today. It takes the `listings` that the copies read already returns (D220's amendment).

## Tests

Changed:

- `orders.spec.ts`, "the card pane is the photograph, the pick and every copy with its place and
  Mark sold (UX-169)": rewritten for Inventory's pane classes, the hero head and the Details
  fold.
- `orders.spec.ts`, "the buyer list is not a scroll box of its own, and no hint sits on its
  rows": rewritten if Q2 takes Inventory's rail.
- `orders.spec.ts`, the layout tests at each width and the 390 walk-mode test: rewritten for
  layout R and the answer to Q4.
- `orders.spec.ts`, "#/inventory renders its own known shell unchanged by any of this": kept. It
  must stay green through the splits.
- `order-walk.spec.ts`, "the walk's card pane carries no listing-correction control": kept.

New, one per point:

1. At 1440, the buyer list sits inside the rail frame, and the rail fits the window. "Walk all
   N buyers" ticks every row (the existing tick tests move with it).
2. T11: a store where box 2 is named "WB1 R3" and box 5 is named "WB1 R1". The plan draws
   WB1 R1 first. The case is red on the old `plan` sort.
3. Every walk row draws `.card-locations-identity` with the box name, `.nb` and
   `.position-bar[data-depth='on']` for each here-copy. A Mark sold press on a row sends that
   row's own capture id and position.
4. A click on a walk row fills the pane: the hero name, the photo and one copies row per
   on-hand copy. The first row is the walk's chosen copy, with `aria-current`. The Details fold
   is present.
5. Lane E's test, run again after lane A: with Hide picked on, the sold row stays in place and
   moves no other row. It folds on reload. UN-6 stays green with no `scrollTo` pin.
6. At 390, the buyer panel's top is above the photograph's top.

Each new test goes red on the tree before its change. The repo trusts a guard only after that.

## The lanes

Each lane is small enough for one Sonnet builder, with its own check. A0 goes first. A1 and A2
run in parallel. A3 and A4 wait for A2. A5 waits for A3 and A4. A6 runs at any time.

| Lane | What | Files | Check |
|---|---|---|---|
| A0 | Record the owner's answers: a decision entry slug that amends D220 and D274, and spec §16 in `docs/specs/order-walk-plan.md`. | docs only | `make docs-audit` |
| A1 | The walk sorts by box name, then section, in `plan` only. | `pipeline/walkplan.py`, `harness/tests/t11_walk_plan.py` | `make harness` green, and the new T11 case red on the old sort |
| A2a | Split the hero head and the card pane frame out of `BoxBrowse.tsx` into `CardHero.tsx`. Inventory imports them back. | `BoxBrowse.tsx`, `CardHero.tsx` | `tsc`, `inventory.spec.ts`, and a pixel diff of `#/inventory` at 1440, 820 and 390, both themes, before and after |
| A2b | Split the rail frame (the rest-top measure and the height) out of `BoxBrowse.tsx`. | `BoxBrowse.tsx`, a new `RailFrame.tsx`, `docs/map.py` | The same as A2a |
| A2c | `CardLocations` gets `head={false}`. `layoutsOf` moves to a shared home. | `CardLocations.tsx`, `Inventory.tsx` | `tsc`, `gallery.spec.ts`, `inventory.spec.ts` |
| A3 | The Orders pane becomes `CardPane`. `WalkCardPane` is deleted. Orders reads `getBoxes()`. | `OrdersWalkPane.tsx`, `Orders.tsx`, `OrdersWalkPane.css` | The point 4 test, the changed UX-169 test, `order-walk.spec.ts` |
| A4 | Walk rows carry their copies as `CardLocations` rows, on top of lane E. | `OrdersWalkPane.tsx`, `OrdersWalkPane.css` | The point 3 and point 5 tests, and UN-6 |
| A5 | Layout R: the buyer list in `RailFrame`, the three registrations, the phone order. | `Orders.tsx`, `Orders.css` | The point 1 and point 6 tests, `scaffold.spec.ts`, `page-edge.spec.ts`, the changed layout tests, and a look at 1440, 820, 720 and 390 in both themes |
| A6 | D259 cleanup: no `Box <n>` fallback in `stopTitle`. The server names a stop's box with `box_title` when its takes carry no copies. | `OrdersWalkPane.tsx`, `server/capture_server.py` | A harness case over `_walk_plan_stop`, and `machine-words.spec.ts` |

A6 is Haiku-shaped: the edit is spelled out above.

## Risks

- **Density.** One copy row is about 200px in the walk column. A pick with three candidates is
  about 600px. "Walk all 70 buyers" on the demo is 81 picks. Q3 offers a lighter row.
- **Render cost.** A long walk mounts one `PositionBar` per candidate copy. The lane measures a
  "Walk all" render on the demo store before it merges.
- **The Inventory splits.** `BoxBrowse` is one 2,031-line component, and `#/inventory` is the
  screen the owner uses most. A2a and A2b move code only. Each one proves that `#/inventory` is
  pixel-identical before it merges.
- **A narrow rail cuts the box name.** From 560 to 999 the rail is 280px wide. The identity line
  of `CardLocations` then cuts the box name ("WB1 R..." in `desk-820`). The comment in
  `CardLocations.css` calls the box name the one part a hand reads first. A4 adds a narrow band
  that wraps the section and card under a whole box name.
- **The text checks.** `text-shape.spec.ts` fails a sentence repeated on three or more rows.
  Every `PositionBar` draws "Section 4 of 9" and "back" and "front". `#/inventory` already
  draws many of them. So the lane first checks how `text-shape-allow.json` treats Inventory.
- **The phone scroll.** In layout R at 390, the walk starts under the whole card pane, about
  2,500px down on the demo. Q4 is about this.
- **Lane E.** The lane E branch is not pushed yet. A4 starts only after lane E merges into
  `ux/pr4b`.
- **One fact said twice on the phone.** The phone mockup shows the buyer twice: the chip that
  opens the buyer sheet, and the buyer panel. A5 makes the panel's name the control that opens
  the sheet, and drops the chip.

## Open questions for the owner

**Q1. Where does the walk list go on a desk?**

- (a) Layout R: three columns at 1000px and up, buyers in Inventory's rail, then the walk, then
  the card. Inventory's skeleton from 560 to 999. RECOMMENDED: every copy row keeps its full
  width, and the walk is the tallest thing on the screen (D274).
- (b) Layout L: the walk inside the 300px rail under the buyers, as D220 first said. One pick
  shows at a time at 1440x900 (`alt-walk-in-rail-1440`).

**Q2. Does the buyer list scroll inside its own rail?**

- (a) Yes, in Inventory's rail: sticky, it fits the window, and its list scrolls. RECOMMENDED:
  that is what "Inventory's left rail" does, and it keeps the buyers in view during a long walk.
- (b) No, the page scrolls everything, as D274 ruled (HOR-33, one scroll).

**Q3. How much location detail goes on every pick row?**

- (a) Every copy row in full: box, section and card, neighbours, strip and ruler, and Mark
  sold. RECOMMENDED: it is what you asked for, and the walk column has room.
- (b) Full detail on the row the pane shows, and one line (box, section, card and Mark sold) on
  the others.
- (c) The identity and the neighbours on every row. The strip and the ruler only on the row the
  pane shows.

**Q4. On a phone, what comes after the buyer?**

- (a) The card, then the walk, as mocked. The walk starts far down.
- (b) The walk, and a tap on a row opens the card in a sheet. RECOMMENDED: the walk is what a
  hand steps through at the shelf, and the stepper bar already moves card by card.
- (c) Keep the D274 walk mode (`?walk=1`) as built, with the buyer panel moved first.

**Q5. How does a box name sort?**

- (a) Natural order: "R2" before "R10". RECOMMENDED: box names on this store carry numbers
  ("WB1 R1" to "WB1 R4"), and a plain sort puts "R10" before "R2".
- (b) Plain text order.

**Q6. The pane's card facts: the whole Details fold?**

- (a) Yes: the hero head and the Details fold, Inventory's pane whole. RECOMMENDED: one pane
  and one set of words, which is the outcome D220 protects.
- (b) The hero head only, as D274 had it. The Details table stays on Inventory.

**Q7. The PNGs cannot be tracked (the opsec rule above). Where do they live?**

- (a) Outside the repository, drawn by `render.cjs` on demand. RECOMMENDED: the rule protects a
  bearer instrument, and the HTML is the record.
- (b) A named exception in `scripts/githooks/pre-commit` for review mockups. That widens an
  opsec guard, and the hook itself calls that "a decision to argue, not a convenience".
