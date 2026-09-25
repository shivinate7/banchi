# Lens 2: the owner's daily loop, end to end

Target: `https://shivinate7.github.io/banchi/` (main at 89544e01, built from PR #454), walked
2026-09-23. First at 1440 light with a mouse, then again at 390 dark (`isMobile`, `hasTouch`,
taps). Each stage starts from Home. One page stayed open for each pass, so the demo's in-memory
writes carried across stages. Presses count clicks, taps and keys. They do not count scrolls.
Scrolls are listed on their own.

## Loop walk

### 1440 light, mouse

| # | Stage | How I got there (presses) | Next step obvious? | State carried? | Dead ends / hidden things |
|---|---|---|---|---|---|
| 1 | Capture | Home > Start capturing > Open the camera > Pick a box > Mixed Singles > Capture card. **5** | Yes. The "Before you can capture" checklist names each missing step. | **No.** Home names "Box 4, Mixed Singles" as the capture target (hero pin and Capture tile). Capture opens with "No box yet". | Demo refuses capture (expected). It draws as "Captures are paused" with a Resume button. Resume, then capture, gives the same halt again (LOOP-16). The reason is behind "What the server said". |
| 2 | Identify / Runs | Capture > "Identify Mixed Singles on Runs" > Identify cards > Continue to the reading. **3**. Then the Box 3 run row: **+1** | Yes. The button names Runs. | **No.** Runs opens scoped to "Every card waiting to be identified", not Mixed Singles (LOOP-06). | Demo refuses at the reading step (expected). The sheet calls boxes "Drawers" (LOOP-22). It states a fixed "2,535 cards" (LOOP-17). |
| 3 | Review | Home > Review tile > answer with `1`. **2** | Yes. | **Yes.** Home went from 9 to 8 "to review" on return. | HELD. See held-screen notes. |
| 4 | Pricing | Run > "Price and emit this run". **1** (from a cold Home: nav > Runs > run row > price, **3**) | Yes. "Ready to write" names the press. | Partly. Home says "2 runs to price". Pricing says "Pricing is answered" and "Runs 1" (LOOP-20). | **The price field shows "$1" for $13.11 and "$2" for $2.52** (LOOP-01). |
| 5 | Listing (the import file) | Pricing > Write the import file. **1** | **No.** After the file, the next steps (upload, then "Export From Staged", then compare) are on Runs step 4, not on Pricing. Home's spine has no listing stage (LOOP-11). | n/a. Demo refuses emit (expected). | The refusal grows the sticky dock over the worklist (LOOP-30). |
| 6 | Orders | Home > ranked sentence "Cannot be filled". **1** | Partly. It lands on the first buyer with "All open (7)", not on the 6 short copies (LOOP-08). | Counts match Home (7 open, 27 to pull, 6 short). | HELD. Every order shows "0 sections" and the demo's refusal text instead of a pull list. |
| 7 | Pull the cards | Orders > Cards to pull (new tab). **1** | n/a | **No.** "No orders are waiting for a card right now", while Home and Orders say 27 copies to pull (LOOP-02). | Dead end. Also "101 cards are in 4 boxes" against Home's 100 on hand (LOOP-32). |
| 8 | Shipping | Home > Shipping tile. **1** | Yes: Download, Fill pick locations. | Home's tile said "no export read yet". After the visit it says 331. The demo loaded an export on arrival. | Order numbers here (`A2FFC195-000005-00023`) do not match the Orders stage (`09-03-26_00012` first). No row links to its order (LOOP-10). |
| 9 | Sales | Home has no Sales link. Nav > Sales. **1**. Expand one row: **+1** | n/a (end of loop) | **No.** "$41.47 across 7 orders, all time" against Home's "1,447 sold" (LOOP-03). | The order id in the expanded row is cut ("A2FFC195-958…") and is not a link (LOOP-10, LOOP-33). No link to `#/product` (LOOP-12). |
| A | Card that will not sell | Nav > Pricing > Mark down stale > Fetch my live listings. **3** | Partly. The sheet lives on the Pricing header. Nothing on Home or on a card points to it. | n/a. Demo refuses the live fetch (expected). | The sheet says "Run `reconcile --live`", a command-line step with no press (LOOP-18). |
| B1 | Card leaves: sold | Home > box 4 row > Mark sold. **2** | Yes | **Partly.** Home's summary moved (99 on hand, 1,448 sold). Home's own box row stayed "15 on hand, 2 sold" (LOOP-09). | HELD. See notes. |
| B2 | Card leaves: retired | Card row > Retire > Damaged. **3** | Yes | Same as B1 | HELD |
| B3 | Card leaves: moved | Tick card > Manage > Move to box. **3+**. Not finished. | **No.** "Move" is not on the card. It is in Manage box, over ticked cards. | n/a | HELD. Hidden: you must know that Move is a box operation. |
| B4 | Find it again | Nav > Graveyard. **1**. Then ⌘K "Crowd Favorite". Then Inventory search. | No working path | **No.** | Graveyard: "could not be read … Rebuild it with `make demo`". ⌘K: "Nothing matches". Inventory search: not recorded (LOOP-13, LOOP-14, LOOP-15). |

### 390 dark, touch

| # | Stage | Taps (+scrolls) | Against 1440 | What breaks |
|---|---|---|---|---|
| 1 | Capture | Start capturing > Open the camera > (scroll) > Pick a box > Mixed Singles > (scroll) > Capture card. **5 + 2 scrolls** | +2 scrolls | Camera fills the fold. "Capture card" is below it once a box is picked (LOOP-26). The RUN card is 279px beside 358px cards (LOOP-27). Keycaps B, C, S are drawn on a touch screen (LOOP-29). |
| 2 | Runs | (scroll) > Identify … on Runs > run row. **2 + 1 scroll** | +1 scroll | The same box drop as at 1440 |
| 4 | Pricing | Price 30 SKUs. **1** | same | About two rows per screen. The write dock (174px) and the tab bar take about a third of 844px (LOOP-25). The price field is correct here (159px wide). |
| 5 | Listing | Write the import file. **1** | same | The refusal grows the dock to about 60% of the viewport. |
| 6 | Orders | Logo (no Home tab) > ranked card. **2** | +1 | HELD. The buyer rail folds to one row. The order sheet has no side gutter. |
| 8 | Shipping | Menu > Shipping. **2** | +1 | "Needs a look", the one lane that needs the owner, starts at y = 32,257px (LOOP-24). |
| 9 | Sales | More > Sales. **2** | +1 | "More" and "Menu" open the same drawer. Drawer rows show `,H`, `,C` and the other chords (LOOP-28, LOOP-29). |
| A | Mark down | Menu > Pricing > Mark down. **3 + 1 scroll** | same, +1 scroll | "Fetch my live listings" sits at y = 1,054, below the fold. |
| B1 | Sold | Inventory tab > (scroll) > Mark sold. **2 + 1 scroll** | same, +1 scroll | HELD. Mark sold is at y = 1,069, below the fold. |

**Phone verdict.** The loop does not break on the phone. It costs more on every stage off the
tab bar. Home, Runs, Pricing, Shipping and Sales each take one more tap. Capture, Runs, Pricing
and Inventory each need a scroll to reach their main press. Shipping's hand-sort lane is 38
screens down. One defect is desktop-only: the unreadable price field (LOOP-01) exists at 1440,
not at 820 or 390.

## Grade matrix

| Route | Grade | One-line reason |
|---|---|---|
| `#/` Home | C | The ranked sentence and the one button point at different jobs. Its own figures disagree after one sale. Sales is not on the spine. |
| `#/capture` | C | Does not take the box Home names. A refusal reads as "paused", and Resume loops. The phone's main press is below the fold. |
| `#/runs` | C | The hand-off from Capture drops the box. A fixed store figure is stated as fact. Two different "Reconcile" presses. |
| `#/review` | HELD | Passed through. The count carried to Home correctly. |
| `#/pricing` | F | At 1440 the price field shows only its first digit ($1 for $13.11), on the screen that sets money. |
| `#/orders` | HELD | Passed through. No pull list drew on the demo. |
| `#/shipping` | C | Order numbers do not match the Orders stage. Raw reason codes. On a phone the hand-sort lane is 32,000px down. |
| `#/revenue` | C | 7 orders all time against Home's 1,447 sold. "Sold" means something else on Orders. The order id is cut and is not a link. |
| `#/inventory` | HELD | Passed through for the sold, retired and moved side loop. |
| `#/graveyard` | F | On the published demo it cannot be read, and it tells the owner to run `make demo`. |
| `#/codes` | not walked | Not on the daily loop (dormant feature). See "What I could not check". |
| `#/fulfillment` | D | Says no orders are waiting while 27 copies are owed. Its box counts differ from Home's. |
| `#/gallery` | not walked | Not on the daily loop. See "What I could not check". |
| `#/product` | D | No loop screen links to it (zero inbound links on 7 screens). By URL, the demo holds no history for a real SKU. |

## Findings

### LOOP-01 The price field shows only the first digit at desktop width
- Severity: S1
- Screens: `#/pricing`
- Where: 1440 light and dark. 820 is correct (65px field). 390 is correct (159px field).
- Repro: open `#/pricing?run=demo-box3` at 1440×900. Look at the Premonition row, "Lists at".
- Seen: the field is 8.5px wide. It shows "$ 1 ✓ Typed" for a stored 13.11, and "$ 2" for 2.52. It stays 8.5px when focused. Every row does this, so on the desk the owner cannot read a single listing price before "Write the import file". Measured and seen.
- Shot: LOOP-01, screenshot not kept.
- Direction: at every width, the listing price must show in full, at least to the cent, before and while it is edited.
- Component: `app/src/Pricing.tsx`, `.pricing-price` > `.pricing-field` > `input.pricing-input` (`Pricing.css`, the desktop grid gives the cell 60px).
- Annotation: no decision covers this. prior: none. The 2026-09-20 pricing review measured 1440 and 1280 on the live store and did not log it. The defect may be newer than that review (unmeasured).

### LOOP-02 "Cards to pull" says nothing is waiting while 27 copies are owed
- Severity: S1
- Screens: `#/fulfillment`, `#/`, `#/orders`
- Where: 1440 light (opened from Orders' "Cards to pull").
- Repro: `#/orders` > Cards to pull (opens a new tab at `#/fulfillment`).
- Seen: "No orders are waiting for a card right now." Home says "27 copies to pull" and Orders says 7 open with 21 lines. The Fulfiller is told there is nothing to do. This could be a demo recording gap (`getOrders` feeding `orderGroups`). I have not proven it on a live store.
- Shot: LOOP-02, screenshot not kept.
- Direction: the Fulfiller's screen and the owner's screens must agree on what is owed. If the Fulfiller's screen cannot read the orders, it must say so and never say "nothing waiting".
- Component: `app/src/Fulfillment.tsx`, the `today` block (`walk` built from `orderGroups(getOrders())`).
- Annotation: violates D5 (two personas). The Fulfiller's screen is the one place that says what to pull, and it says nothing is owed. prior: ux-2026-09-20/fulfillment.md reached the same empty state and did not check it against open orders.

### LOOP-03 Home's "sold" total and Sales' total are different universes
- Severity: S2
- Screens: `#/`, `#/revenue`
- Where: all
- Repro: `#/` reads "1,447 sold". `#/revenue` > All time reads "You grossed $41.47 over all time, across 7 orders" (about 30 copies).
- Seen: nothing on either screen says why 1,447 cards sold turn into 7 orders. The owner cannot tell which figure is the store.
- Shot: LOOP-03, screenshot not kept.
- Direction: one "sold" figure, or each figure says what it counts (store history against orders the ledger holds), and each links to the other.
- Component: `app/src/Home.tsx` (summary line), `app/src/Revenue.tsx` (verdict line)
- Annotation: caused by D214 (a gross-sales retrospective over the order ledger) beside D121 (the front page counts the store). Neither entry names the other's count. D214 measured 804 orders on the owner's store, so the gap may be wider on the demo seed than live (unmeasured). prior: none.

### LOOP-04 "Sold" means two different things on two stages
- Severity: S2
- Screens: `#/orders`, `#/revenue`
- Where: all
- Repro: `#/revenue` > expand Premonition: order `A2FFC195-958565-00010`, $12.14, sold Aug 31. `#/orders` > 08-31-26_00010 (the same order): "5 owed, 0 sold, 0 short".
- Seen: Sales counts the order as sold revenue. Orders says 0 sold, because nothing has been pulled. The same word means "the buyer paid" on one stage and "I pulled the card" on the next.
- Shot: LOOP-04, screenshot not kept.
- Direction: give each meaning its own word (for example "paid" and "pulled"), and use it the same way on every stage.
- Component: `app/src/Revenue.tsx`, `app/src/Orders.tsx` (order summary counters)
- Annotation: violates D214 (a retrospective over everything closed). Sales counts order 00010, which Orders shows open with nothing pulled. prior: none.

### LOOP-05 Home names a capture box, and Capture does not open with it
- Severity: S2
- Screens: `#/`, `#/capture`
- Where: all
- Repro: `#/` (hero pin "Box 4, Mixed Singles". Capture tile "Box 4, 18 cards in Mixed Singles") > Start capturing.
- Seen: Capture opens with "No box yet. Pick one, or type a new name". The owner must pick the box Home already named, which costs 2 presses on every cold start.
- Shot: LOOP-05, screenshot not kept.
- Direction: when Home names a box, "Start capturing" arrives with that box chosen. Or Home names no box.
- Component: `app/src/Home.tsx` (Capture tile, hero pin, `Start capturing`), `app/src/CaptureScreen.tsx` (box restore)
- Annotation: no decision covers this. D142 (the setup outlives the browser) and D153 (the restore asks which drawer) govern Capture's own memory, not Home's hand-off into it. prior: none. ux-2026-09-20/capture.md graded the "no box yet" state alone.

### LOOP-06 "Identify Mixed Singles on Runs" lands on Runs without Mixed Singles
- Severity: S2
- Screens: `#/capture`, `#/runs`
- Where: all
- Repro: `#/capture` > pick Mixed Singles > "Identify Mixed Singles on Runs".
- Seen: Runs opens with the scope chip "Every card waiting to be identified". The Identify sheet opens on "Everything that needs it", not on that drawer. The button promises one box and delivers all of them. Pressing on spends money across the store.
- Shot: LOOP-06, screenshot not kept.
- Direction: the press arrives with the named box as the scope, or the label does not name a box.
- Component: `app/src/CaptureScreen.tsx`, the `Identify {captureBoxLabel(...)} on Runs` button (`onClick` sets `#/runs` with no scope). `app/src/RunsComposer.tsx`.
- Annotation: violates D39 (the pipeline gets a route, and the selection is handed to it). prior: none.

### LOOP-07 Home's one action is not the ranked job
- Severity: S2
- Screens: `#/`
- Where: all
- Repro: `#/`
- Seen: the ranked sentence is "Cannot be filled: 6 copies for 7 open orders". The one big button under it is "Start capturing". The page ranks orders first and then asks the owner to go and photograph.
- Shot: LOOP-07, screenshot not kept.
- Direction: the one action is the ranked job, or the button explains why it outranks the ranked job.
- Component: `app/src/Home.tsx`
- Annotation: caused by D121 (the front page says what is owed). The entry makes the button STANDING and the ranked line conditional, to serve a fresh store where the line has nothing to press. On a working store the outcome is a button that points away from the ranked job. The argument is not a defence of that outcome. prior: none.

### LOOP-08 "Cannot be filled" lands on all open orders, not on the short ones
- Severity: S3
- Screens: `#/`, `#/orders`
- Where: all
- Repro: `#/` > ranked sentence.
- Seen: it lands on `#/orders?buyer=…00012` with the filter "All open (7)". The short copies the sentence counts are behind the "Short (6)" filter, which the owner must find.
- Shot: LOOP-08, screenshot not kept.
- Direction: a sentence about short copies opens the short copies.
- Component: `app/src/Home.tsx` (ranked link), `app/src/Orders.tsx` (filter)
- Annotation: no decision covers this. prior: none.

### LOOP-09 After one sale, Home disagrees with itself
- Severity: S3
- Screens: `#/`, `#/inventory`
- Where: 1440 light
- Repro: `#/inventory?box=4` > Mark sold on card #1 > `#/`.
- Seen: Home's summary moves to "99 on hand, 1,448 sold". Box 4's row on the same page stays "15 on hand, 2 sold". The Inventory box panel also stays 15/2/1. This may be the demo's recorded box list (the summary is recomputed and the box list is replayed). It is what the owner sees on the demo.
- Shot: LOOP-09, screenshot not kept.
- Direction: a sale moves every figure that counts that card, on every screen, at the same time.
- Component: `app/src/Home.tsx` (summary against box list), `app/src/demoServer.ts` `restat`
- Annotation: no decision covers this. prior: none.

### LOOP-10 One sale cannot be followed across Orders, Shipping and Sales
- Severity: S2
- Screens: `#/orders`, `#/shipping`, `#/revenue`
- Where: all
- Repro: `#/orders` shows `09-03-26_00012` large, with `A2FFC195-256158-00012` small. `#/shipping` rows show only `A2FFC195-000005-00023`-style ids. `#/revenue` rows show only the `A2FFC195-…` id.
- Seen: the order that the owner pulls under one name is shipped and counted under another. No row on Shipping or Sales links back to its order.
- Shot: LOOP-10, screenshot not kept.
- Direction: one order name leads on every stage, and each stage's row opens that order.
- Component: `app/src/Orders.tsx`, `app/src/Shipping.tsx` / `OrdersShipStage.tsx`, `app/src/Revenue.tsx`
- Annotation: no decision covers this. D69 (a route each for orders and shipping) joins the two stages in code only. prior: none.

### LOOP-11 After the import file, nothing says what to do next
- Severity: S2
- Screens: `#/pricing`, `#/runs`, `#/`
- Where: all
- Repro: `#/runs?run=demo-box3` > open step 4 "Reconcile": "After Import to Staged on TCGplayer, download its Export From Staged and compare…". `#/pricing` has no such step. Home's spine goes Capture, Runs, Review, Pricing, Orders, Shipping, with no listing stage.
- Seen: the file is written on Pricing, but the next three steps (upload, export, compare) are on Runs, one screen back. The owner must remember to go back. The demo refuses emit, so I could not see Pricing's success state.
- Shot: LOOP-11, screenshot not kept.
- Direction: the screen that writes the file shows the next step and a way to it. Home shows a run that is written but not yet compared as its own stage.
- Component: `app/src/Pricing.tsx` (write dock), `app/src/Runs.tsx` (step 4), `app/src/Home.tsx` (spine)
- Annotation: caused by D105 (the markdown lives where prices are decided) and D99 (one press writes one spreadsheet). The write moved to Pricing and the compare stayed on Runs. prior: none.

### LOOP-12 Sales and Product history are off the loop's paths
- Severity: S2
- Screens: `#/`, `#/revenue`, `#/product`
- Where: all
- Repro: count links to `#/revenue` on `#/` (0). Count links to `#/product` on `#/`, `#/pricing`, `#/revenue`, `#/inventory?box=4`, `#/orders`, `#/shipping`, `#/runs?run=demo-box3` (0 on each). Pricing's "Price history" opens a popover, not the route.
- Seen: the loop's last stage is reached only from the nav. The per-product view has no inbound link at all, so the owner has to type a SKU.
- Shot: LOOP-12, screenshot not kept.
- Direction: Home's spine ends at Sales. Every product name on Sales, Pricing and Inventory opens its product history.
- Component: `app/src/Home.tsx`, `app/src/Revenue.tsx`, `app/src/ProductHistory.tsx`
- Annotation: caused by D227 (a product price view: a route, not a lens). The `ROUTES` comment says Revenue.tsx carries no link because another branch was editing it. That leaves `#/product` against CLAUDE.md's hard rule that a route is not a feature until a screen reaches it. prior: none.

### LOOP-13 The "find it again" side loop has no working path on the demo
- Severity: S2
- Screens: `#/graveyard`, `#/inventory`, `#/pricing`, `#/product`
- Where: all
- Repro: `#/graveyard`. `#/inventory` search "Crowd Favorite". `#/pricing` > Price history on any row. `#/product?sku=9027180`.
- Seen: all four answer "This demo's recording holds no answer for …". None is one of the seven named refusals. They are reads the published demo never recorded, so a visitor cannot see where a departed card goes.
- Shot: LOOP-13, screenshot not kept.
- Direction: the published demo answers every read that a loop screen makes, or the screen hides the control.
- Component: `app/src/demoServer.ts` (`demo_not_recorded`), the demo recording (`make demo-record`)
- Annotation: no decision covers this. `docs/specs/demo.md` governs the demo. prior: ux-2026-09-20/FOLLOW-UPS.md section 7 logged the same class (the demo seed does not record every route) for two other routes.

### LOOP-14 Error copy names a build command and URL paths
- Severity: S3
- Screens: `#/graveyard`, `#/pricing`, `#/product`, `#/inventory`, `#/review`
- Where: all
- Repro: as LOOP-13. Also `#/inventory?box=4` card #1 photo panel. Also `#/review` first card.
- Seen: "Rebuild it with `make demo`." "/pipeline/runs/demo-box3/history?sku=9027180." "/banchi/demo/photos/4/1.jpg?card=demo-4-0001." Raw codes under refusals (`demo_read_only`, `demo_no_session`) and in toasts (`sold_origin_unknown`).
- Shot: LOOP-14, screenshot not kept.
- Direction: error text says what the owner can do, in words. Paths and codes go behind a disclosure, as Capture's halt already does.
- Component: `app/src/demoServer.ts` messages, `Graveyard.tsx`, `ProductHistory.tsx`, the inventory photo panel
- Annotation: violates D196 (no mechanism on screen). The text comes from the server or the demo, which the `no mechanism on screen` row does not read. prior: ux-2026-09-20/graveyard.md finding 2 logged a sibling defect (a raw machine string on Graveyard).

### LOOP-15 "Search" in the sidebar does not find cards
- Severity: S2
- Screens: shell (every route)
- Where: 1440 (⌘K). 390 (header search icon, not tested further).
- Repro: sidebar "Search ⌘K" > type "Crowd Favorite".
- Seen: "Nothing matches 'Crowd Favorite'." The palette finds screens only. The one control labelled Search cannot find a card.
- Shot: LOOP-15, screenshot not kept.
- Direction: Search finds cards, or its label says it finds screens and commands.
- Component: `app/src/App.tsx`, the command palette
- Annotation: caused by D95 (the shell is a rail, a palette and a reference sheet). The palette searches screens and verbs by design, and the sidebar labels it "Search". prior: none.

### LOOP-16 A capture refusal reads as "paused", and Resume loops
- Severity: S3
- Screens: `#/capture`
- Where: all
- Repro: `#/capture` > Open the camera > pick a box > Capture card > Resume captures > Capture card.
- Seen: every failure except a camera one is headlined "Captures are paused — the card was not recorded", with "Resume captures" as the one action. Resume, then capture, halts again. The real reason ("This demo has no disk behind it") is behind "What the server said". On a live rig, a failure that does not clear (for example a full disk) would loop the same way.
- Shot: LOOP-16, screenshot not kept.
- Direction: the halt headline says why it stopped. Resume is offered only when resuming can work.
- Component: `app/src/CaptureScreen.tsx`, `.capture-halt`
- Annotation: no decision covers this. prior: none.

### LOOP-17 The Identify sheet states a fixed store figure as fact
- Severity: S3
- Screens: `#/runs`
- Where: all
- Repro: `#/runs` > Identify cards.
- Seen: "on this store every one of 2,535 cards was already answered and cached". The demo store holds 122 cards (1,573 photographed). The number is typed into the copy.
- Shot: LOOP-17, screenshot not kept.
- Direction: state the live count or drop the sentence.
- Component: `app/src/RunsComposer.tsx` (copy near the "Everything that needs it" tab)
- Annotation: no decision covers this. D185 (a row that examined nothing says so) is the nearest principle: a published figure needs a reader. prior: none.

### LOOP-18 The markdown sheet asks for a command-line step
- Severity: S3
- Screens: `#/pricing` (Mark down stale)
- Where: all
- Repro: `#/pricing` > Mark down stale.
- Seen: "Run `reconcile --live` to give more rows a true one." The owner has no terminal step in the loop. The screen control is "Reconcile the store" on Runs, and the sheet does not link it.
- Shot: LOOP-18, screenshot not kept.
- Direction: name the screen press and link it.
- Component: `app/src/Markdown.tsx`
- Annotation: violates D196 (no mechanism on screen). D105 (the markdown lives where prices are decided) moved the sheet and kept the command-line remedy. prior: none.

### LOOP-19 Two different presses are both called "Reconcile" on Runs
- Severity: S3
- Screens: `#/runs`
- Where: all (at 390 the header press shortens to "Reconcile")
- Repro: `#/runs?run=demo-box3`. The header has "Reconcile the store" (live My Pricing, store-wide). Step 4 has "Reconcile" (Export From Staged, this run).
- Seen: at 390 both read "Reconcile". They take different files and do different jobs.
- Shot: LOOP-19, screenshot not kept.
- Direction: two names, one per job.
- Component: `app/src/Runs.tsx`
- Annotation: caused by D87 (the reconcile is store-wide), which added a second reconcile and did not rename the per-run one. prior: none. ux-2026-09-20/runs.md graded the header buttons' alignment, not their names.

### LOOP-20 Home says 2 runs to price, and Pricing says pricing is answered
- Severity: S3
- Screens: `#/`, `#/pricing`, `#/runs`
- Where: all
- Repro: `#/` ("2 runs to price") > Pricing tile.
- Seen: Pricing reads "Ready to write. Pricing is answered. 22 of 22 decided" and "Runs 1". Home counts runs that are not yet written as "to price".
- Shot: LOOP-20, screenshot not kept.
- Direction: Home's word for this state matches Pricing's ("to write", not "to price"), and the counts agree.
- Component: `app/src/Home.tsx` (Pricing tile, "Behind that")
- Annotation: no decision covers this. D198 (Home's Review tile counts both queues) is the precedent for Review only. prior: none.

### LOOP-21 "Behind that" names three jobs and links none
- Severity: S3
- Screens: `#/`
- Where: all
- Repro: `#/` > "Behind that: 27 copies to pull, 9 to review, 2 runs to price".
- Seen: plain text. The owner reads the next three jobs and then goes to the nav or the tiles below to reach them.
- Shot: LOOP-21, screenshot not kept.
- Direction: each named job opens its screen.
- Component: `app/src/Home.tsx`
- Annotation: caused by D121 (the front page says what is owed). The lines behind the ranked sentence are drawn as context, not as controls. prior: none.

### LOOP-22 Box on every screen, "Drawers" in the Identify sheet
- Severity: S3
- Screens: `#/runs` (Identify sheet)
- Where: all
- Repro: `#/runs` > Identify cards > tabs "Everything that needs it / Drawers / A previous run's cards".
- Seen: every other screen says Box. The owner meets a second word for the same thing at the step that costs money.
- Shot: LOOP-22, screenshot not kept.
- Direction: one word.
- Component: `app/src/RunsComposer.tsx`
- Annotation: no decision covers this. D180 (a press names the cards it is over) uses "drawer" in its own argument. prior: none.

### LOOP-23 Shipping rows print raw reason codes
- Severity: S3
- Screens: `#/shipping`
- Where: all
- Repro: `#/shipping`
- Seen: `cards_only`, `value_at_threshold` and `no_weight_data` on every row, beside a sentence that already says the same thing.
- Shot: LOOP-23, screenshot not kept.
- Direction: drop the code, or put it behind the row's detail.
- Component: `app/src/OrdersShipStage.tsx` / `Shipping.tsx`
- Annotation: no decision covers this. CLAUDE.md's typography rule allows reason codes in mono. prior: ux-2026-09-20/RANKING.md item 5 logged the same pattern on Review, and HANDOFF.md records that it came off Review. This is the same defect on another screen.

### LOOP-24 On a phone, the hand-sort shipping lane is 32,000px down
- Severity: S2
- Screens: `#/shipping`
- Where: 390 dark
- Repro: `#/shipping` at 390.
- Seen: Envelope (166 rows) and Parcel (126 rows) stack first. "Needs a look" (39 rows) starts at y = 32,257px of a 37,150px page. It is the one lane that asks the owner to decide. Collapsing the first two lanes takes two taps, and nothing says so. Measured, and the top of the stack was seen.
- Shot: LOOP-24, screenshot not kept.
- Direction: the lane that needs a decision comes first on a phone, or the lanes open collapsed.
- Component: `app/src/OrdersShipStage.tsx`
- Annotation: caused by D61 (three shipping lanes, the third is "I cannot tell"). The lanes are ordered by type, so the one that needs the owner comes last. prior: none. ux-2026-09-20/shipping.md did not cover 390.

### LOOP-25 On a phone, Pricing shows about two rows per screen
- Severity: S2
- Screens: `#/pricing`
- Where: 390 dark
- Repro: `#/pricing?run=demo-box3` at 390 > scroll to rows.
- Seen: each row is about 270px tall. The sticky write dock is 174px and the tab bar about 64px, so a third of the 844px screen never scrolls. 30 SKUs is about 15 screens.
- Shot: LOOP-25, screenshot not kept.
- Direction: fit more rows. The dock folds to one line until it is needed.
- Component: `app/src/Pricing.tsx` (phone row layout, write dock)
- Annotation: no decision covers this. D208 (one verdict on Pricing) governs the deck, not the phone row height. prior: none. ux-2026-09-20/pricing.md covered 1440 and 1280 only.

### LOOP-26 On a phone, Capture's main press falls below the fold
- Severity: S2
- Screens: `#/capture`
- Where: 390 dark
- Repro: `#/capture` at 390 > Open the camera > pick a box.
- Seen: the camera card fills the fold. "Capture card" sits under it and each card needs a scroll. After a halt, the halt card pushes it further down.
- Shot: LOOP-26, screenshot not kept.
- Direction: the capture press is reachable without a scroll at 390.
- Component: `app/src/CaptureScreen.tsx`
- Annotation: no decision covers this. D32 (the pixel budget is spent on the card) argues for the camera's size, not for the press below it. prior: none.

### LOOP-27 On a phone, Capture's RUN card is narrower than its siblings
- Severity: S4
- Screens: `#/capture`
- Where: 390 dark
- Repro: `#/capture` at 390.
- Seen: `.capture-card-run` is 279px wide. The camera, stack and rig cards are 358px. Its right edge does not line up with the others.
- Shot: LOOP-27, screenshot not kept.
- Direction: one width for the column.
- Component: `app/src/CaptureScreen.tsx`, `.capture-card-run`
- Annotation: no decision covers this. prior: none.

### LOOP-28 On a phone, most of the loop is two taps away, and there are two doors to one drawer
- Severity: S3
- Screens: shell
- Where: 390 dark
- Repro: at 390, the tab bar is Capture, Review, Orders, Inventory, More. The header has Search and Menu.
- Seen: no Home tab. Home is the logo, which is hidden knowledge. Runs, Pricing, Shipping and Sales each cost Menu or More plus one more tap. "More" and "Menu" open the same drawer.
- Shot: LOOP-28, screenshot not kept.
- Direction: one door to the drawer. Home reachable by a labelled control.
- Component: `app/src/App.tsx` (phone tab bar, `tab: true` flags)
- Annotation: caused by D120 (the shell speaks one brand at every width, and the phone bar is a rail) and the `tab: true` flags in `ROUTES`. prior: none.

### LOOP-29 Keyboard chords are drawn on a touch screen
- Severity: S3
- Screens: `#/`, `#/capture`, shell drawer
- Where: 390 dark
- Repro: `#/` at 390 (",O" on the ranked card). Drawer (",H", ",C" and so on on every row). `#/capture` (B, C, S, H, R, F keycaps).
- Seen: Home's "Start capturing" drops its chip on a phone and the ranked card keeps its chip. The drawer and Capture keep all of theirs.
- Shot: LOOP-29, screenshot not kept.
- Direction: hide chord hints when there is no keyboard, the same way on every screen.
- Component: `app/src/Home.tsx`, `app/src/App.tsx` (drawer), `app/src/CaptureScreen.tsx`
- Annotation: no decision covers this. prior: none. ux-2026-09-20/home.md noted the `,C` hint at desktop only.

### LOOP-30 A refusal grows the write dock over the worklist
- Severity: S3
- Screens: `#/pricing`
- Where: 1440 light, 390 dark
- Repro: `#/pricing?run=demo-box3` > Write the import file.
- Seen: the refusal opens inside the sticky dock. At 1440 it covers about 200px of rows. At 390 the dock takes about 60% of the viewport, and the refusal stays until dismissed.
- Shot: LOOP-30, screenshot not kept.
- Direction: the refusal sits where it does not hide the rows it is about.
- Component: `app/src/Pricing.tsx` (write dock)
- Annotation: no decision covers this. prior: none.

### LOOP-31 The separator dot hugs the next word
- Severity: S4
- Screens: `#/pricing`
- Where: all
- Repro: `#/pricing?run=demo-box3` header and "Before you write" card.
- Seen: "22 of 22 decided ·8 nothing to add", "1 run ·1 box", "14 never identified ·9 in review". The space is on the wrong side of the dot.
- Shot: LOOP-31, screenshot not kept.
- Direction: even spacing around the separator.
- Component: `app/src/Pricing.tsx` (CSS `::before` separator)
- Annotation: caused by D218 (no typed interpunct on screen) and D41 (the separator moves into CSS). The CSS separator's spacing is uneven here. prior: none.

### LOOP-32 Three different card totals for one store
- Severity: S3
- Screens: shell, `#/`, `#/fulfillment`
- Where: all
- Repro: sidebar foot "122 cards". Home "1,573 photographed, 100 on hand in 4 boxes". `#/fulfillment` "101 cards are in 4 boxes" with Box 1 at 35 cards, where Home says 34 on hand.
- Seen: four figures for "how many cards", and two of them disagree by one.
- Shot: LOOP-32, screenshot not kept.
- Direction: each figure says what it counts, and the two "in the boxes" figures agree.
- Component: `app/src/App.tsx` (server status), `app/src/Home.tsx`, `app/src/Fulfillment.tsx`
- Annotation: no decision covers this. prior: none.

### LOOP-33 Sales cuts the order id at the part that tells orders apart
- Severity: S4
- Screens: `#/revenue`
- Where: 1440 light
- Repro: `#/revenue` > expand Premonition.
- Seen: "A2FFC195-958…". Every order shares the `A2FFC195` prefix, so the cut removes the only part that differs.
- Shot: LOOP-33, screenshot not kept.
- Direction: show the tail, or the order's short name.
- Component: `app/src/Revenue.tsx`
- Annotation: no decision covers this. prior: none.

### LOOP-34 Demo photographs 404 across the loop
- Severity: S3
- Screens: `#/capture`, `#/pricing`, `#/inventory`, `#/review`
- Where: all
- Repro: `#/capture` recent strip (B4 #18, broken-image glyph). `#/pricing` row thumbnails (blank). `#/inventory?box=4` card photo ("The record has a photo but the file is not on disk"). `#/review` first card.
- Seen: `/banchi/demo/photos/4/18.jpg` and the other photo URLs return 404. The loop is built on "photo first", and the demo shows none.
- Shot: LOOP-34, screenshot not kept.
- Direction: the published demo ships the photographs its records name, or the records do not name them.
- Component: demo build (`demo-assets/`, `make demo-static`)
- Annotation: no decision covers this. `docs/specs/demo.md` governs the demo photographs. prior: none.

## Held-screen notes

Main state, re-check after merge.

- `#/orders`: every order card draws the demo's `demo_read_only` refusal as unstyled body text under "0 sections". No pull list appears for any order, Short or Ready (the walk-plan write is refused on the demo). Shots: LOOP-34 screenshot, not kept, LOOP-34 screenshot, not kept.
- `#/orders`: with a buyer picked, the right-hand pane holds only "Why each line answered as it did". It is an empty pane at 1440. Shot: LOOP-34 screenshot, not kept.
- `#/orders` at 390: the buyer sheet has no side gutter. Filters and the search field sit flush against the left edge, and they are narrower than the sheet. Shot: LOOP-34 screenshot, not kept.
- `#/orders`: the stage strip says "Shipping: No export" until Shipping is visited once (the demo loads an export on arrival).
- `#/inventory`: after Mark sold, the box panel and the Manage sheet still read 15 on hand, 2 sold, 1 retired. After a nav away and back, the sold card reads "Identified" with Mark sold offered again. This may be demo replay. Shots: LOOP-34 screenshot, not kept, LOOP-34 screenshot, not kept.
- `#/inventory`: the sale and retire toasts say the copy "cannot be put back from here (sold_origin_unknown)". There is no undo on the one press that loses a card from the box, and there is a code in the toast. This may be demo-only.
- `#/inventory`: after the sale, "1 live on TCGplayer" stays red with no next step for the live listing.
- `#/inventory`: the subtitle says "Sell, retire or move a copy from here". The card has Mark sold and Retire. Move is only Manage box > Move to box over ticked cards. Shot: LOOP-34 screenshot, not kept.
- `#/inventory`: the Retire dialog prints enum codes (`pulled`, `damaged`, `lost`, `given_away`) under each label. Shot: LOOP-34 screenshot, not kept.
- `#/inventory` at 390: Mark sold sits at y = 1,069, below the fold. Shot: LOOP-34 screenshot, not kept.
- `#/review`: the answered count carried to Home on return (9 to 8). This is positive. The missing-photo panel prints its URL path. Shot: LOOP-34 screenshot, not kept.

## What I could not check

- **The pull stage end to end.** On the demo no screen drew a pull list: Orders is refused and Cards to pull says nothing is waiting. So I could not count presses to pull an order, or see a pull carry to Shipping and Sales.
- **Pricing's success state after "Write the import file"** (emit is refused). LOOP-11 rests on the Runs step 4 text and on what Pricing draws before the press.
- **Whether LOOP-02, LOOP-09 and the held inventory count drift are product or demo.** The demo recomputes `/status` on a write and replays other reads. I cannot tell from the page which one a live store would show.
- **Graveyard, inventory search, price history and `#/product` content.** All four are unrecorded on the demo (LOOP-13).
- **Home's sold figure after later writes.** It fell from 1,448 to 1,436 after I answered one review and retired one card. That is the demo's `restat`, so I did not report it as a product finding.
- **`#/codes` and `#/gallery`.** They are not on the daily loop and were not walked. Their grade cells say "not walked", not a letter.
- **820 width and 390 light, 1440 dark** were not walked as a loop. I checked only LOOP-01 at 820 light and 1440 dark.
- **The live store.** Off limits by the brief.
