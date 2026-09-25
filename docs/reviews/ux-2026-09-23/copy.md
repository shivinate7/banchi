# Copy and register

Lens 5. Target: the published demo at `https://shivinate7.github.io/banchi/`, built from PR #454.
Read on 2026-09-23. The route list comes from `ROUTES` in `app/src/App.tsx` (14 routes).

The raw strings for each route are in COPY screenshot, not kept. Each file holds the
headings, the controls, the attributes (`aria-label`, `title`, `placeholder`, `alt`), the main
text and the whole page. After that, each file records every distinct control, pressed once
from a fresh load, with the lines that the press added. The shell, the palette, the key sheet
and the typed states are in COPY screenshot, not kept. The scripts are
COPY scratch file, not kept.

Verbatim product text is in backticks.

## Glossary

One concept, every word the product uses for it, and the screens. This table is the copy half
of the owner's complaint (`"they're not syncing"`). The owner meets a new word for an old
thing on most screens.

| Concept | Words used | Where |
|---|---|---|
| The container of cards | `Box` | Home, Capture, Inventory, Fulfillment, Codes, Runs list, Pricing |
| | `Drawers`, `Whole drawer`, `whatever drawer it is in`, `exactly one drawer picked above` | Runs, Identify dialog |
| | `The drawer this run was over has since been deleted` | Runs, rebind sheet |
| | `sitting somewhere else on a shelf` | Runs, rebind sheet |
| The place of a card in a box | `Box 1 · Section 2 · Card 1` (count starts again in each section) | Fulfillment, Pricing photo sheet |
| | `#12` (count runs across the box), `SECTION 1: COMMONS, #1–#11` | Inventory (held) |
| | `BOX 1 SECTION 3 CARD 13` | Review (held) |
| | `B1 #19` (after `departed`) | Fulfillment, Inventory |
| | `index`, `next index 43`, `index span` | Capture top strip, Capture box picker |
| | `slot` (`The card is still at its slot`) | Review (held) |
| One TCGplayer printing | `SKU` (`30 SKUs`, `Price 30 SKUs`, `Hide never-seen SKUs`) | Pricing, Runs, Orders (held) |
| | `sku 9027180` (lower case, the raw number) | Pricing photo sheet |
| | `TCGplayer SKU` (a number the owner must type) | Product history |
| | `product` (`BY PRODUCT`, `Product history`) | Sales, Product history |
| | `row` (`21 rows`, `Is this the row it matched?`, `which is in no row`) | Pricing, Review (held) |
| | `listing` | Pricing, markdown sheet |
| A price that the owner set | `typed` (`Typed`, `Clear typed`, `21 typed`) | Pricing |
| | `answer` (`Pricing is answered.`, `Removes pricing answers`, `Which answers`) | Pricing, Clear sheet |
| | `decided` (`22 of 22 decided`) | Pricing header |
| | `Lists at` (column) | Pricing |
| The price used when none is set | `the standing rule`, `on the rule`, `Rule for the rows you have not set` | Pricing |
| | `The pricing rule and basis are one answer for the whole store now.` | Runs, run detail |
| The low-price threshold | `cut-off` (`The cut-off`, `Above the cut-off`) | Pricing |
| | `the line` (`the line, and what everything under it lists at`) | Pricing |
| | `cheap` (`cheap = under the cut-off`) | Pricing legend |
| | `floor` (`clamped at the floor after rounding`) | Pricing, rule note |
| | `sub-threshold` (`Emit refuses while a sub-threshold price is unanswered.`) | Runs, run detail |
| Keep a card out of the file | `Hold`, `Hold back`, `held`, `Holding 1`, `Keeping this one` | Pricing |
| Undo a hold | `Release` (button), `Lift one on its own row` | Pricing row, Clear sheet |
| Write the file for TCGplayer | `Write the import file` (the button) | Pricing |
| | `emit` (`Emit can still refuse.`, `Price and emit this run`, `Never emitted`, stage `Emit`) | Pricing, Runs, Pricing run picker |
| | `send` (`nothing here can send them`, `Show everything unsent`) | Pricing |
| | `upload` (`the upload edits the live listing in place`) | Pricing, markdown sheet |
| The market figure | `Market` (column), `TCG Market Price: 12.14` (tooltip) | Pricing |
| | `The recent actual-sale average` | Pricing, rule note |
| | `today's market` (`Compare to today's market`) | Sales |
| | `Low`, `TCG Low`, `+Ship` | Pricing |
| | `reading` (`PRICES READ`, `The reading did not come back`) | Pricing, history sheet |
| Other meanings of "reading" | `Reading` is the cost check before Identify (`Continue to the reading`) | Runs, Identify dialog |
| | `read` is what the model saw (`This read`, `Low confidence read`, `30 photographs read by the model`) | Review (held), Runs |
| The word "run" | A pipeline job over a box (`Recent runs`, `2 runs to price`, `Runs 1`) | Home, Runs, Pricing |
| | `RUN` labels the panel with the box picker and the shutter | Capture |
| | `Run box 1`, `Nothing running` | Inventory (held) |
| | `Run reconcile --live` (a shell command) | Pricing, markdown sheet |
| Card identification | `Identify`, `never identified`, `waiting to be identified`, `answered and cached`, `read by the model` | Runs, Pricing, Home |
| The review queue | `9 to review` | Home line |
| | `9 to answer` | Home tile |
| | `9 in review` | Pricing |
| | `Queue`, `To review`, `Parked` | Review (held), Runs |
| Cards that orders need | `copies to pull` | Home |
| | `owed` (`4 owed`) | Orders (held) |
| | `Cards to pull`, `waiting for a card` | Fulfillment |
| | `Every copy found`, `Ready`, `Ready to ship` | Orders (held) |
| Needed cards that cannot be found | `Cannot be filled`, `cannot be found` | Home banner |
| | `not found` (`27 copies to pull and 6 not found`) | Home tile |
| | `Short` | Orders (held) |
| One order | `A2FFC195-256158-00012` | Shipping, Sales drill-down, Orders detail |
| | `09-03-26_00012` (where a buyer is named) | Orders rail (held) |
| A card that left | `sold` | Home, Inventory, Sales |
| | `departed` (`Box 1 · departed · B1 #19`) | Fulfillment |
| | `left inventory — sold, retired, or moved` | Graveyard |
| | `has left the box` | Pricing |
| How many cards the store holds | `100 on hand in 4 boxes` | Home |
| | `122 cards` | Sidebar foot, Inventory |
| | `101 cards are in 4 boxes` | Fulfillment |
| | `1,573 photographed` | Home |
| | `2,535 cards` | Runs, Identify dialog |
| TCGplayer's price file | `My Pricing export`, `Fetch my live listings`, `live` | Runs reconcile sheet, Pricing markdown sheet |
| TCGplayer's catalogue | `the export` (`Not in the export`, `Search the export`) | Review (held) |
| TCGplayer's shipping file | `export` (`export.csv`, `No export`, `no export read yet`) | Shipping, Orders, Home |
| Check the store against TCGplayer | `Reconcile the store` (button), `Reconcile the whole store` (sheet), stage `Reconcile` | Runs |
| Rank by value | `Find by value` (1440), `By value` (390), `Rank inventory by value` (aria-label), `What's worth pulling` (the screen it opens) | Pricing |
| Mark down | `Mark down stale` (1440), `Mark down` (390), `Mark down stale listings` (aria-label), `Mark down what is not selling` (sheet) | Pricing |
| Camera state | `Camera off` (chip), `Not open` (Rig row), `The camera is not open` (viewfinder) | Capture |
| Shutter mode | `Key` (Rig row), `Manual` (chip), `manual:c` (Rig row), `C fires it` | Capture |
| A set or rarity that the operator declares | `claim` (`No claim`, `0 of 13 claimed`, `Stack claims`) and `hint` (`Set hint`, `Needed`) | Capture |
| Theme | `Dark mode` (sidebar), `Switch to dark mode` (palette) | Shell |
| The palette | `Search ⌘K` (sidebar), `command palette` (key sheet), `Jump to a screen…` (placeholder) | Shell |
| The Sales screen | `Sales` (nav, H1), `sales` (tab title), `gross-revenue retrospective` (subtitle), `#/revenue` (address) | Sales |
| A period of time | `3 months`, `6 months`, `This year`, `All time`, `Custom` | Sales, top |
| | `Month`, `Quarter`, `6 months`, `Year` | Sales, `On the shelf` |
| Dates | `WEDNESDAY, SEPTEMBER 23`, `Sep 4`, `placed Sep 3`, `Aug 31, 2026`, `Sep 03, 2026`, `Aug 24, 2026`, `Aug 24–30`, `Sep 2026`, `1h ago`, `2 hours ago` | Home, Pricing run picker, Orders, Sales, Runs |

## Word counts at 1440 (default state, light)

COPY scratch file, not kept counts tokens that start with a letter, a digit or `$`. It counts
the `innerText` of `main`, and the whole page with the shell. This is NOT the repo's own
copy-budget counter. The figures will not match its pinned ceilings.

| Route | Main | Whole page | Note |
|---|---|---|---|
| `#/` Home | 137 | 172 | |
| `#/capture` | 107 | 142 | |
| `#/runs` | 70 | 105 | More than 520 when a run is open |
| `#/review` | 150 | 185 | HELD |
| `#/pricing` | 870 | 905 | 813 at 390 |
| `#/orders` | 173 | 208 | HELD |
| `#/shipping` | 4,939 | 4,974 | One sentence repeats for each order. See COPY-08. |
| `#/revenue` Sales | 267 | 302 | |
| `#/inventory` | 282 | 317 | HELD |
| `#/graveyard` | 33 | 68 | Refusal state only |
| `#/codes` | 34 | 69 | |
| `#/fulfillment` | 72 | 72 | No shell |
| `#/gallery` Kit | 2,374 | 2,409 | Developer screen |
| `#/product` | 40 | 75 | |

## Grade matrix

| Route | Grade | One-line reason |
|---|---|---|
| `#/` Home | C | Five different card counts in one view. One fact (missing copies) has three names. The Orders tile cuts its own sentence. |
| `#/capture` | C | Machine words on the main strip (`next index`, `index span`, `manual:c`). One shutter mode has three names. |
| `#/runs` | D | The whole screen speaks the pipeline: identify, join, emit, reconcile, SKUs, parked, sub-threshold, the model, JSON files. `Needs pricing` contradicts Pricing. |
| `#/review` | HELD | See the held-screen notes. |
| `#/pricing` | F | At 1440 the `Lists at` field shows `$1` for a $13.11 price. The screen also needs a printed key to decode its five words for a price. |
| `#/orders` | HELD | See the held-screen notes. |
| `#/shipping` | D | Raw reason codes beside plain sentences. One sentence printed 331 times. Weights to four decimals. Orders named only by a 21-character number. |
| `#/revenue` Sales | C | The verdict is plain. The subtitle is jargon, two zero-count notes say too much, and two period controls use different words. |
| `#/inventory` | HELD | See the held-screen notes. |
| `#/graveyard` | C | The one state that the demo draws is a refusal. It prints an API path and a `make` command, and offers a retry that cannot help. |
| `#/codes` | B | Short and plain. `tier` in the subtitle is the only word without an explanation. |
| `#/fulfillment` | D | Tells the Fulfiller that no orders wait while seven are open. Lists a sold card as `departed B1 #19`. Counts 101 cards where Home counts 100. |
| `#/gallery` Kit | B | A developer page, and it reads as one. Repository paths and build notes are on screen. This is acceptable only because no owner task lands here. |
| `#/product` | D | No screen and no palette search reaches it (`Nothing matches “product”.`). It asks for a TCGplayer SKU number that the owner sees nowhere else. |

## Findings

### COPY-01 `Lists at` shows $1 for a $13.11 price
- Severity: S1
- Screens: `#/pricing`
- Where: 1440/light. At 820 the same field is correct (65px wide). 390 and dark: not measured.
- Repro: Open `#/pricing` at 1440x900. Look at the first row (Premonition), column `LISTS AT`.
- Seen: The field shows `$ 1 ✓ Typed`. Its value is 13.11. The input is 9px wide and shows only the first digit. Every row does the same (`$ 2` for 2.52, `$ 0` for 0.70). A correct `$12.14` market figure sits beside it. So the owner reads a typed price 90% under market.
- Shot: COPY-01, screenshot not kept.
- Direction: The typed price is readable in full, to the cent, at every width.
- Component: `app/src/Pricing.tsx`, `Pricing` (the row input with `aria-label="Price for …"`)
- Annotation: no decision covers this.

### COPY-02 One store, five card counts
- Severity: S2
- Screens: `#/`, shell, `#/fulfillment`, `#/runs`, `#/codes`, `#/inventory` (held)
- Where: all
- Repro: Open `#/`. Read the stats line and the sidebar foot. Open `#/fulfillment`. Open `#/runs` and press `Identify cards`. Open `#/codes` and press `Read a box`.
- Seen: Home says `100 on hand in 4 boxes`, `1,573 photographed` and `1,447 sold`. The sidebar foot says `122 cards`. Fulfillment says `101 cards are in 4 boxes`, and `35 cards` for Box 1, where Home says `34 on hand`. The Identify dialog says `2,535 cards`. Home's box rows add up to 19 sold, not 1,447. Sales counts 7 orders. No label says which count is which.
- Shot: COPY-02, screenshot not kept.
- Direction: One count of cards on hand, with the same words on every screen. Each other count says what it counts ("sold since you started", "sold cards included").
- Component: `app/src/Home.tsx` stats line, `app/src/App.tsx` sidebar foot, `app/src/Fulfillment.tsx` box list
- Annotation: no decision covers this. D198 (Home's Review tile reads the same total as `#/review`) applies "one figure for one concept" to one tile only.

### COPY-03 The Fulfiller reads that no orders wait while seven are open
- Severity: S1
- Screens: `#/fulfillment`, against `#/` and `#/orders`
- Where: all
- Repro: Open `#/`. Read `Cannot be filled — 6 copies for 7 open orders` and `27 copies to pull`. Open `#/fulfillment`.
- Seen: The Fulfiller's screen shows a green check and `No orders are waiting for a card right now.` The owner's screens say that 27 copies wait for 7 open orders. The Fulfiller has no other screen to learn the truth.
- Shot: COPY-03, screenshot not kept.
- Direction: The Fulfiller's sentence agrees with the owner's count of copies to pull. Or it says why these orders are not the Fulfiller's yet.
- Component: `app/src/Fulfillment.tsx`, `Fulfillment` (the `today` block when `walk` is empty)
- Annotation: no decision covers this. D5 (two personas) governs the screen, not this sentence.

### COPY-04 Runs speaks the pipeline, not the job
- Severity: S2
- Screens: `#/runs`
- Where: all
- Repro: Open `#/runs`. Press the first run.
- Seen: The subtitle is `Identify, join, emit and reconcile a box.` The stages are `Identify / Join / Emit / Reconcile`. The figures are `Cards in / SKUs / To review / Parked`. Badges say `Free · re-runnable`. Other text: `30 photographs read by the model`, `Emit refuses while a sub-threshold price is unanswered.`, `The pricing rule and basis are one answer for the whole store now.` A FILES list shows `identifications.json`, `pricing.json` and `report.txt`. The owner does not say join, emit, parked or basis.
- Shot: COPY-04, screenshot not kept.
- Direction: Each step has the name of what it does for the owner: read the cards, match them to TCGplayer, price and write the file, check what is live. Internal files leave the main view.
- Component: `app/src/Runs.tsx`
- Annotation: violates D196 (no mechanism on screen). `the model` and `the join` are on its word list. `30 photographs read by the model` and the stage `Join` are on screen, so its guard does not see composed strings.

### COPY-05 `Needs pricing` on a run that Pricing calls answered
- Severity: S2
- Screens: `#/`, `#/runs`, `#/pricing`
- Where: all
- Repro: Open `#/`. Read `Box 3 · RB Epics … Needs pricing` under Recent runs, and the tile `2 runs to price`. Open `#/pricing`, which opens on Box 3.
- Seen: Pricing says `22 of 22 decided`, `Pricing is answered.` and `Ready to write` for that run. Home and Runs still say `Needs pricing`. The tooltip shows that the badge is a stage count (`3 of 6 stages done`). So the badge names the next stage, not the state of the prices.
- Shot: COPY-05, screenshot not kept.
- Direction: The status says what the owner must do next ("Ready to write the file"). It agrees with Pricing.
- Component: `app/src/Runs.tsx` run list badge, `app/src/Home.tsx` recent runs
- Annotation: no decision covers this.

### COPY-06 A shell command on screen
- Severity: S2
- Screens: `#/pricing`, Mark down sheet
- Where: all
- Repro: Open `#/pricing`. Press `Mark down stale`.
- Seen: `Run reconcile --live to give more rows a true one; the report says which clock dated each.` The owner has no shell on this path. The same note says `a floor on the real age, never the age itself`.
- Shot: COPY-06, screenshot not kept.
- Direction: Point at the control that does the job (`Reconcile the store` on Runs, or a button here), in one short sentence.
- Component: `app/src/Markdown.tsx`
- Annotation: violates D196 (no mechanism on screen). A shell command is mechanism, and the word list does not hold it.

### COPY-07 Shipping prints raw reason codes
- Severity: S2
- Screens: `#/shipping`
- Where: all
- Repro: Open `#/shipping`. Read the lower-right corner of any order card.
- Seen: Each card has a mono code (`cards_only`, `value_at_threshold`, `no_weight_data`, `non_card_signal`). A plain sentence above it already says the same thing.
- Shot: COPY-07, screenshot not kept.
- Direction: The sentence is the reason. The owner does not see the code.
- Component: `app/src/OrdersShipStage.tsx`, `ShipStage` (`.shipping-reason`)
- Annotation: caused by D61 (three shipping lanes). D61 keeps five reasons so that a screen can show which answers to check. The sentence already does that. Related: prior: ux-2026-09-20/review.md, the same defect on Review. There the owner ruled the code off the page (TASTE-CALLS, "The reason code: chip, tooltip, gone"). Shipping still prints it.

### COPY-08 One sentence, 331 times
- Severity: S3
- Screens: `#/shipping`
- Where: all
- Repro: Open `#/shipping`. Scroll a lane.
- Seen: Each Envelope card says `Cards only, and under $50.` (166 times). Each Parcel card says `Worth $50 or more, so tracking is required.` (112 times). The lane header already says it. The page holds 4,939 words. The unique text is fewer than 60 lines.
- Shot: COPY-08, screenshot not kept.
- Direction: A card shows a sentence only when its reason differs from its lane.
- Component: `app/src/OrdersShipStage.tsx`, `ShipStage` (`.shipping-says`)
- Annotation: caused by D194 (the word count may only go down). Its pinned ceiling for `#/shipping` is 133 words, measured on a fixture with no export loaded. The loaded state draws 4,939 words and the check cannot see it. The ceiling for `#/pricing` is 46 words against 870 here, for the same reason.

### COPY-09 Weights to four decimals
- Severity: S3
- Screens: `#/shipping`
- Where: all
- Repro: Open `#/shipping`.
- Seen: `0.0700 oz/item`, `2.5000 oz/item`. The zeros suggest a precision that the file does not have.
- Shot: COPY-09, screenshot not kept.
- Direction: Write the weight as a person does ("0.07 oz each").
- Component: `app/src/OrdersShipStage.tsx`, `figuresOf`
- Annotation: no decision covers this.

### COPY-10 `Inferred` and `Certain` have no explanation
- Severity: S3
- Screens: `#/shipping`
- Where: all
- Repro: Open `#/shipping`. Read the upper-right label on each card.
- Seen: Envelope cards say `Inferred`. Parcel cards say `Certain`. Needs-a-look cards say neither. Nothing says what was inferred, or how that changes the owner's choice of lane.
- Shot: COPY-10, screenshot not kept.
- Direction: Say what to check ("check the weight"), or remove the label where it changes nothing.
- Component: `app/src/OrdersShipStage.tsx`, `qualityOf`
- Annotation: caused by D61 (three shipping lanes). `Routing.certain` is the split that D61 wants drawn. The label draws it with no word on what to do.

### COPY-11 Box, drawer and shelf
- Severity: S2
- Screens: `#/runs` (Identify dialog, rebind sheet), against every other screen
- Where: all
- Repro: Open `#/runs`. Press `Identify cards`.
- Seen: The dialog tab is `Drawers`. The select is `Whole drawer`. The hint is `A section is a divider inside one drawer`. The body says `whatever drawer it is in`. Every other screen says `Box`, and so does the Runs list behind the dialog. The rebind sheet adds `shelf`.
- Shot: COPY-11, screenshot not kept.
- Direction: One word, "box", everywhere a person picks one.
- Component: `app/src/RunsComposer.tsx`
- Annotation: caused by D153 (the restore asks which drawer) and D180 (a selection of cards). Both use "drawer" for "box" in their prose, and the prose word reached the screen. No decision picks one word.

### COPY-12 "Run" has two meanings
- Severity: S3
- Screens: `#/capture`, `#/runs`, `#/`, `#/pricing`, `#/inventory` (held)
- Where: all
- Repro: Open `#/capture`. Read the label of the upper-left panel. Open `#/runs`.
- Seen: On Capture, `RUN` labels the panel with the box picker and the shutter. On all other screens a run is a pipeline job over a box (`Recent runs`, `2 runs to price`, `Runs 1`). Inventory adds `Run box 1` and `Nothing running`.
- Shot: COPY-12, screenshot not kept.
- Direction: The Capture panel gets a word that is not "run" ("Box" or "Shooting").
- Component: `app/src/CaptureScreen.tsx`
- Annotation: no decision covers this. D196 names "run" as an owner word, so both meanings pass its check.

### COPY-13 "Reading" has three meanings
- Severity: S3
- Screens: `#/runs` Identify dialog, `#/pricing`, `#/review` (held)
- Where: all
- Repro: Open `#/runs` and press `Identify cards`. Open `#/pricing` and press the price history button on a row.
- Seen: In the Identify dialog, `Reading` is the step that shows the cost (`Continue to the reading`). On Pricing, a reading is a market price (`PRICES READ 2 hours ago`, `The reading did not come back`). On Review, a read is what the model saw (`Low confidence read`, `This read`).
- Shot: COPY-13, screenshot not kept.
- Direction: Name the Identify step by what it shows ("Cost check"). Keep "read" for one meaning.
- Component: `app/src/RunsComposer.tsx`
- Annotation: no decision covers this.

### COPY-14 Three ways to number the place of a card
- Severity: S2
- Screens: `#/fulfillment`, `#/pricing` photo sheet, `#/capture`, `#/inventory` and `#/review` (held)
- Where: all
- Repro: Open `#/fulfillment`. Open Box 1. Read the row for Mirror Image. Open `#/inventory?box=1` and find Mirror Image.
- Seen: Fulfillment and the Pricing photo sheet count in each section (`Box 1 · Section 3 · Card 1`). Inventory counts across the box (`#22`). Review prints `BOX 1 SECTION 3 CARD 13`. A sold card is `B1 #19`. Capture says `next index 43`. "Card 22" for the owner and `Card 1` for the Fulfiller are the same card.
- Shot: COPY-14, screenshot not kept.
- Direction: One address format on each screen that tells a person where a card is.
- Component: `app/src/Fulfillment.tsx` `PlaceText`, `app/src/Pricing.tsx` photo sheet
- Annotation: no decision covers this. D58 (a card number counts the cards in the box) and D41 (the address is a rank) govern the number and how it is drawn. Neither picks one scheme for all screens.

### COPY-15 The Fulfiller sees a sold card as `departed B1 #19`
- Severity: S2
- Screens: `#/fulfillment`
- Where: all (seen at 390)
- Repro: Open `#/fulfillment`. Press Box 1. Scroll to Ashe, Focused.
- Seen: A sold card is in the list of cards to look through. Where each other row gives a section and a card, this row gives `Box 1 · departed · B1 #19`. `departed` and `B1 #19` are record words. The Fulfiller cannot pull a card that is gone.
- Shot: COPY-15, screenshot not kept.
- Direction: The Fulfiller's box list shows only cards that the Fulfiller can pull. A card that is gone, when it must show, says "Sold".
- Component: `app/src/Fulfillment.tsx`, `CardRow` and `PlaceText`
- Annotation: caused by D68 (a departed label names the record). D68 put the store key `B3 #31` on the label for the owner. The same label reaches the Fulfiller, who cannot use it.

### COPY-16 Pricing needs a key for its own words
- Severity: S3
- Screens: `#/pricing`
- Where: all
- Repro: Open `#/pricing`. Read the line under the header.
- Seen: `typed = you set a price. held = held back on purpose. on the rule = following the standing rule. cheap = under the cut-off.` The screen also says `decided`, `answered`, `answers` and `Lists at` for the same things. A printed key shows that the words do not carry their meaning alone.
- Shot: COPY-16, screenshot not kept.
- Direction: Words that need no key ("Your price", "Held", "Default price", "Under $0.49"), and no key line.
- Component: `app/src/Pricing.tsx`, `Pricing` header
- Annotation: caused by D49 (one pricing answer, and a card can be held on purpose) and D86 (one pricing file for the store). Their word "answer" reached the screen as a word for a price.

### COPY-17 The threshold has five names
- Severity: S3
- Screens: `#/pricing`, `#/runs`
- Where: all
- Repro: Open `#/pricing`. Press `Market −5%`. Open a run on `#/runs`.
- Seen: `cut-off`, `the line`, `cheap`, `floor` (`clamped at the floor after rounding`) and, on Runs, `sub-threshold`. The caption of the cut-off panel is `the line, and what everything under it lists at`.
- Shot: COPY-17, screenshot not kept.
- Direction: One word ("cut-off"), and a caption that says what it does in plain words.
- Component: `app/src/Pricing.tsx` `CutoffPanel`, `app/src/Runs.tsx`
- Annotation: no decision covers this.

### COPY-18 "Emit" outlived its button
- Severity: S3
- Screens: `#/pricing`, `#/runs`
- Where: all
- Repro: Open `#/pricing`. Read the panel under `Ready to write`. Press `Runs`.
- Seen: The button says `Write the import file`. The panel under it says `Emit can still refuse.` The run picker says `Never emitted`. Runs says `Price and emit this run`. No screen explains "emit".
- Shot: COPY-18, screenshot not kept.
- Direction: Use the words of the button everywhere ("written", "not written yet").
- Component: `app/src/Pricing.tsx` `ReadyPanel` and `PickRuns`, `app/src/Runs.tsx`
- Annotation: no decision covers this. D196's word list does not hold "emit".

### COPY-19 Missing copies have three names on one screen
- Severity: S3
- Screens: `#/`
- Where: all
- Repro: Open `#/`.
- Seen: The banner says `Cannot be filled — 6 copies for 7 open orders cannot be found.` It states the fact twice. `6 copies for 7 orders` also reads as if each order lacks less than one copy. The Orders tile says `27 copies to pull and 6 not found`. Orders says `Short`.
- Shot: COPY-19, screenshot not kept.
- Direction: One sentence with one verb ("6 copies are missing across 7 orders"), and the same word on Orders.
- Component: `app/src/Home.tsx`
- Annotation: no decision covers this. D121 (the front page says what is owed) governs the banner, not its words.

### COPY-20 The review count is `to review`, `to answer` and `in review`
- Severity: S3
- Screens: `#/`, `#/pricing`
- Where: all
- Repro: Open `#/`. Compare the `Behind that` line with the Review tile. Open `#/pricing`.
- Seen: `9 to review`, then 200px lower `9 to answer`. Pricing says `9 in review`.
- Shot: COPY-20, screenshot not kept.
- Direction: One phrase for the same nine cards.
- Component: `app/src/Home.tsx`, `app/src/Pricing.tsx` `UnreachableLine`
- Annotation: no decision covers this. D198 makes the number agree across screens. The words still disagree.

### COPY-21 The Orders tile cuts its own sentence
- Severity: S3
- Screens: `#/`
- Where: 1440/light
- Repro: Open `#/` at 1440.
- Seen: `27 copies to pull and 6 ...` The cut half is the half with the bad news.
- Shot: COPY-21, screenshot not kept.
- Direction: A tile caption that fits ("27 to pull, 6 missing").
- Component: `app/src/Home.tsx` workflow tiles
- Annotation: no decision covers this.

### COPY-22 Dates in seven formats
- Severity: S3
- Screens: `#/`, `#/runs`, `#/pricing`, `#/revenue`, `#/orders` (held)
- Where: all
- Repro: Open each screen in the list.
- Seen: `WEDNESDAY, SEPTEMBER 23` (Home). `1h ago` (Home, Runs). `2 hours ago` (Pricing, `PRICES READ`). `Sep 4` (Pricing run picker). `placed Sep 3` (Orders). `Sep 03, 2026` with a zero in the Sales table. `Aug 24, 2026` without a zero in the Sales range sentence. `Aug 24–30` (Sales weeks). `1h` and `2 hours` are one unit with two spellings.
- Shot: COPY-22, screenshot not kept.
- Direction: One relative format and one absolute format everywhere, with no leading zero on the day.
- Component: each screen. No shared formatter was seen.
- Annotation: no decision covers this.

### COPY-23 Money without a dollar sign, and $0.00 sales
- Severity: S3
- Screens: `#/pricing`, `#/revenue`
- Where: all
- Repro: Hover the Market figure on a Pricing row. Open `#/revenue` and read the end of the By product table.
- Seen: The tooltip says `TCG Market Price: 12.14, press M to use it`, with no dollar sign. Sales lists six cards sold for `$0.00`. No word says why a sale earned nothing.
- Shot: COPY-23, screenshot not kept.
- Direction: Each money figure has "$". A zero sale says what it was (a gift, a bundle line, a missing price).
- Component: `app/src/Pricing.tsx` market cell `title`, `app/src/Revenue.tsx`
- Annotation: no decision covers this. D221 (money stays mono) governs the face of a money figure, not its sign.

### COPY-24 Notices print the raw error code and the request path
- Severity: S3
- Screens: `#/product`, `#/pricing`, `#/shipping`, `#/revenue`, `#/graveyard`
- Where: all
- Repro: Open `#/product?sku=9027180`. Or press `Write the import file` on `#/pricing`.
- Seen: The notice shows the server's text, then the code in mono (`demo_not_recorded`, `demo_read_only`). The demo text names `/pipeline/products/9027180/history` and `make demo`. The demo refusal is expected. The code line is the product's own notice layout, and it will show on the live app too.
- Shot: COPY-24, screenshot not kept.
- Direction: The owner sees one plain sentence and one action. Codes stay out of the owner's view.
- Component: the kit notice in `app/src/kit/`, as `ProductHistory.tsx` and the toast stack use it
- Annotation: caused by D196 (no mechanism on screen). D196 exempts the `code` prop of `Notice`, on the premise that the raw string "stays available on hover and in the run log". The code draws in plain view under the sentence, so that premise does not hold. Measured on `#/product` and `#/pricing`.

### COPY-25 Nothing leads to Product history
- Severity: S2
- Screens: `#/product`, palette
- Where: all
- Repro: Press ⌘K. Type "product", then "sku". Look on each screen for a link to `#/product`.
- Seen: The palette says `Nothing matches “product”.` for a screen with the name Product history. No screen links to it: not the Sales rows, not the Pricing rows, not the price history sheet. The screen asks for a `TCGplayer SKU` (placeholder `e.g. 555123`). The owner sees that number nowhere, except as `sku 9027180` in small type on the Pricing photo sheet.
- Shot: COPY-25, screenshot not kept.
- Direction: The owner gets to the history of a product from the card on screen, by name. The palette finds it.
- Component: `app/src/App.tsx` palette `goTo` (it keeps only `r.nav` routes), `app/src/ProductHistory.tsx`
- Annotation: caused by D227 (a product price view, off-nav). The `ROUTES` comment in `App.tsx` says that no link from Sales was added because another branch held `Revenue.tsx`. The link was never added after that branch merged.

### COPY-26 Product history explains its mechanism
- Severity: S4
- Screens: `#/product`
- Where: all
- Repro: Open `#/product`.
- Seen: The empty state says `Enter a SKU to see its history.` and `This page is per product, and it never guesses which one you mean.` The second sentence is about how the page was built.
- Shot: COPY-26, screenshot not kept.
- Direction: One sentence that says what to type and where to find it.
- Component: `app/src/ProductHistory.tsx`
- Annotation: caused by D227 (a product price view). The sentence restates its "never guesses" rule on screen.

### COPY-27 The Capture top strip is machine words
- Severity: S3
- Screens: `#/capture`
- Where: all
- Repro: Open `#/capture`. Read the strip at the upper right. Press the Box picker.
- Seen: `0 captured`, `— next index`, `— index span`. The box picker lists `next index 43` and `next index 29`. Home calls one box `18 cards in Mixed Singles`, and the picker says `next index 19` for it.
- Shot: COPY-27, screenshot not kept.
- Direction: Count in cards ("18 cards in this box, next is card 19"). Remove "span".
- Component: `app/src/CaptureScreen.tsx`
- Annotation: no decision covers this.

### COPY-28 One shutter mode, three names
- Severity: S3
- Screens: `#/capture`
- Where: all
- Repro: Open `#/capture`. Compare the chip on the viewfinder with the Trigger row in the Rig panel.
- Seen: The chip says `Manual`. The Trigger row says `Key`, with `manual:c` under it. The menu says `Manual` and `C fires it`.
- Shot: COPY-28, screenshot not kept.
- Direction: One name ("Manual") in all three places. Do not show `manual:c`.
- Component: `app/src/CaptureScreen.tsx`
- Annotation: no decision covers this.

### COPY-29 The Capture set-hint note speaks the plumbing
- Severity: S4
- Screens: `#/capture`
- Where: all
- Repro: Open `#/capture`. Press `Set hint`.
- Seen: `No TCGplayer session. The hint is stored exactly as typed.` The row value `Needed` shows in the warning color. Rarity and finish use `claim` (`No claim`, `0 of 13 claimed`).
- Shot: COPY-29, screenshot not kept.
- Direction: Say what the owner can do ("Type the set name. We cannot check it now.").
- Component: `app/src/CaptureScreen.tsx`
- Annotation: no decision covers this. D76 (a hint is evidence about its card) governs the hint, not the note.

### COPY-30 Sales says too much about nothing
- Severity: S3
- Screens: `#/revenue`
- Where: all
- Repro: Open `#/revenue`.
- Seen: The subtitle is `Your gross-revenue retrospective — what sold, for how much, by name. Gross only: no fees, no cost, no profit.` Both counts below are zero, but two long notes still show: `0 orders were canceled by the marketplace and left out.` and `0 lines were marked refunded or canceled during fulfilment and left out — your own note, not TCGplayer's, so treat it as a habit rather than a guarantee.` The note spells `fulfilment` with one L. The address spells `fulfillment`.
- Shot: COPY-30, screenshot not kept.
- Direction: A short plain subtitle ("What you sold, before fees"). A note shows only when its count is more than zero.
- Component: `app/src/Revenue.tsx`
- Annotation: caused by D225 (Sales stops counting a refund as revenue). D225 makes both notes render at zero, so that a silent mechanism does not look unwired. That is a check for the builder, placed on the owner's screen. It also reverses D214 (gross sales retrospective), which ruled that Canceled is dropped with no footnote. `fulfilment` is the spelling of the wire field.

### COPY-31 Two period controls with different words
- Severity: S3
- Screens: `#/revenue`
- Where: all
- Repro: Open `#/revenue`. Compare the control at the upper right with the `On the shelf` control at the bottom.
- Seen: The top control says `3 months / 6 months / This year / All time / Custom`. The bottom control says `Month / Quarter / 6 months / Year`. Both have `6 months`. A choice in one does not move the other.
- Shot: COPY-31, screenshot not kept.
- Direction: One set of period words on one screen. Or a label that says the bottom control answers a different question.
- Component: `app/src/Revenue.tsx`
- Annotation: caused by D250 (unsold stock reaches `#/revenue`). It added the bottom control with its own period words.

### COPY-32 The Identify dialog states a fixed, stale number
- Severity: S2
- Screens: `#/runs`, Identify dialog
- Where: all
- Repro: Open `#/runs`. Press `Identify cards`.
- Seen: `Most of the time that figure is nothing: on this store every one of 2,535 cards was already answered and cached.` The figure is typed into the screen. The screen does not read it from the store. The demo store has 122 cards, and the owner's store will move away from 2,535. The dialog never says how many cards this press is over (`Every card waiting to be identified`). Pricing already knows that count (`14 never identified`).
- Shot: COPY-32, screenshot not kept.
- Direction: The dialog gives the live count of cards that this press will read, and no past count.
- Component: `app/src/RunsComposer.tsx`
- Annotation: no decision covers this.

### COPY-33 The key sheet starts with a paragraph about itself
- Severity: S3
- Screens: shell (`?`)
- Where: all
- Repro: Press `?` on any owner screen.
- Seen: `Banchi is meant to be driven from the keyboard. Everything it answers to is here, in 85 entries — a row that shows several caps is a run of keys, not one.` Then `Showing Anywhere, Jump to a screen.` Under Esc: `a sheet mid-request is the one thing that stays put; Runs says so below`.
- Shot: COPY-33, screenshot not kept.
- Direction: A title and the keys. A note is one short line at the key it applies to.
- Component: `app/src/App.tsx` key sheet, `app/src/keys.ts`
- Annotation: no decision covers this. D95 (the shell is a rail, a palette and a reference sheet) governs the contents of the sheet, not its intro.

### COPY-34 Tab titles are lower case
- Severity: S4
- Screens: all
- Where: browser tab
- Repro: Open any route. Read the browser tab.
- Seen: `capture`, `runs`, `sales`, `cards to pull`, `product history`, `not found`. The Home tab is `番地 banchi`. The nav and every H1 use a capital letter (`Capture`, `Sales`).
- Shot: COPY-34, screenshot not kept.
- Direction: Tab titles match the H1 ("Capture — Banchi").
- Component: `app/src/App.tsx` document title
- Annotation: no decision covers this.

### COPY-35 One action, four names
- Severity: S3
- Screens: `#/pricing`
- Where: all
- Repro: Open `#/pricing`. Read the `Find by value` and `Mark down stale` buttons, their aria-labels, and the views they open.
- Seen: `Find by value`, `Rank inventory by value`, `What's worth pulling`, `By value` (390). `Mark down stale`, `Mark down stale listings`, `Mark down what is not selling`, `Mark down` (390). A screen reader user and a sighted user hear different names.
- Shot: COPY-35, screenshot not kept.
- Direction: The button, its label and the view it opens share one name.
- Component: `app/src/Pricing.tsx` header toolbar
- Annotation: no decision covers this.

### COPY-36 At 390, `Clear` loses its object
- Severity: S3
- Screens: `#/pricing`
- Where: 390/light
- Repro: Open `#/pricing` at 390.
- Seen: `Clear typed` becomes `Clear`. Beside `Saved` and `Runs`, it reads as a clear of the screen or a filter. It clears every typed price.
- Shot: COPY-36, screenshot not kept.
- Direction: A destructive button keeps its object at every width ("Clear prices").
- Component: `app/src/Pricing.tsx` header toolbar
- Annotation: no decision covers this.

### COPY-37 Buttons that do not say what they do
- Severity: S3
- Screens: `#/pricing`, `#/shipping`, `#/`
- Where: all
- Repro: Open each screen. Press each button in the list.
- Seen: On Pricing, `Compare` adds two columns, `LOW` and `+SHIP`. `Load trends` adds daily and weekly lines to each row. `Custom` opens an undercut rule. On Shipping, `Forget` drops the loaded file. `Fill pick locations` fills a column in the Pirate Ship file. On Home, `Browse` opens Inventory.
- Shot: COPY-37, screenshot not kept.
- Direction: A verb and its object ("Show lowest prices", "Show price trends", "Forget this file", "Add box locations to the file").
- Component: `app/src/Pricing.tsx`, `app/src/OrdersShipStage.tsx`, `app/src/Home.tsx`
- Annotation: no decision covers this.

### COPY-38 `Load trends` answers in shorthand
- Severity: S3
- Screens: `#/pricing`
- Where: all
- Repro: Open `#/pricing`. Press `Load trends`.
- Seen: The result line is `Read again · 22 read · 8 not asked · ranges overlap`. Each row gets `DAILY / WEEKLY / no sales`.
- Shot: COPY-38, screenshot not kept.
- Direction: One sentence ("Trends for 22 cards. 8 cards have no sales to show.").
- Component: `app/src/Pricing.tsx`
- Annotation: no decision covers this.

### COPY-39 `hold to [no cap] live per card`
- Severity: S3
- Screens: `#/pricing`
- Where: all. At 390 it reads `hold to [no cap] live`.
- Repro: Open `#/pricing`. Read the fixed footer beside `Write the import file`.
- Seen: A checkbox, `split it in two, either side of the cut-off`. Then `hold to`, a field with the placeholder `no cap`, and `live per card`. The phrase is not English that a person can parse. It sits beside the one button that writes the file.
- Shot: COPY-39, screenshot not kept.
- Direction: A field with a label that says what it limits ("At most [ ] copies listed for each card").
- Component: `app/src/Pricing.tsx` footer
- Annotation: caused by D7 (duplicates aggregate by SKU, amended). D7 makes the cap something a send asks for. The control is correct. Its label is not.

### COPY-40 Held counts disagree and do not say why
- Severity: S3
- Screens: `#/pricing`
- Where: all
- Repro: Open `#/pricing`. Read `Holding 1` and `Held back from this run · 1 SKU`. Press `Clear typed`.
- Seen: The screen says 1 held. The Clear sheet says `3 held back on purpose.` Neither count says that one is this run and the other is the store.
- Shot: COPY-40, screenshot not kept.
- Direction: Each count names its scope ("1 in this run, 3 in the store").
- Component: `app/src/Pricing.tsx` `HoldPanel`, Clear sheet
- Annotation: no decision covers this.

### COPY-41 The hold sheet explains the store model
- Severity: S4
- Screens: `#/pricing`, Hold sheet
- Where: all
- Repro: Open `#/pricing`. Press the hold button on any row.
- Seen: `Every copy stays out of every import file until you release it — one answer for the whole store, outliving every run over this box.` The reasons are `Bullish`, `Keeping this one` and `A later batch`. The undo verb is `Release` on the row and `Lift` in the Clear sheet.
- Shot: COPY-41, screenshot not kept.
- Direction: "This card stays out of every file until you release it." One verb to undo a hold.
- Component: `app/src/Pricing.tsx` `HoldPanel`
- Annotation: caused by D49 (one pricing answer, and a card can be held on purpose). The sheet repeats the decision in its own words.

### COPY-42 A refusal drawn as a failure to retry
- Severity: S3
- Screens: `#/graveyard`, `#/pricing?band=top`, `#/revenue` (On the shelf, Compare)
- Where: all
- Repro: Open `#/graveyard`.
- Seen: The heading is `The graveyard could not be read`. Then the path `/graveyard`, then `Rebuild it with make demo.`, then `Try again`. The value view adds `Waiting on the capture server.` above the same refusal. `Try again` changes nothing. The demo refusal is expected. The product's part is the layout: a permanent "no" drawn as a short failure, with a retry.
- Shot: COPY-42, screenshot not kept.
- Direction: A refusal says in one sentence that this cannot be done here. It has no retry.
- Component: `app/src/Graveyard.tsx`, shared error notice
- Annotation: no decision covers this.

### COPY-43 The Fulfillment search fails with advice that cannot help
- Severity: S3
- Screens: `#/fulfillment`
- Where: all
- Repro: Open `#/fulfillment`. Type "Piercing" (a card in Box 1), then "zzzz".
- Seen: Both give `The search did not finish. Type the name again.` A second try gives the same answer. It is not known whether the demo refuses search. The sentence is the product's.
- Shot: COPY-43, screenshot not kept.
- Direction: Say what the Fulfiller can do in its place ("Search is not working. Look through a box below.").
- Component: `app/src/Fulfillment.tsx`
- Annotation: no decision covers this.

### COPY-44 Shipping has a file, and Home and Orders say it has none
- Severity: S3
- Screens: `#/shipping`, `#/`, `#/orders` (held)
- Where: all
- Repro: Open `#/shipping`, which loads 331 orders. Press the Orders tab. Open `#/`.
- Seen: Shipping says `EXPORT LOADED`, `export.csv`, `331 orders`. The Orders tab strip beside it says `Shipping · No export`. The Shipping tile on Home says `no export read yet`. The demo can load the file only on this screen. The three labels still disagree.
- Shot: COPY-44, screenshot not kept.
- Direction: One state of the shipping file, drawn the same in all three places.
- Component: `app/src/OrdersShipStage.tsx`, `app/src/Home.tsx`
- Annotation: no decision covers this.

### COPY-45 Shipping and Sales name an order only by a 21-character number
- Severity: S3
- Screens: `#/shipping`, `#/revenue` drill-down
- Where: all
- Repro: Open `#/shipping`. Open `#/revenue` and press the chevron on Premonition.
- Seen: Each order is `A2FFC195-000005-00023` and nothing more. Orders names the same order by buyer (`09-03-26_00012` in the demo). The owner cannot tell who a Shipping card is for.
- Shot: COPY-45, screenshot not kept.
- Direction: Show the buyer first, then the order number in small type.
- Component: `app/src/OrdersShipStage.tsx`, `app/src/Revenue.tsx`
- Annotation: no decision covers this. D193 (the ledger holds the buyer's name) puts the name in the store. These two screens do not use it.

### COPY-46 Home's box rows end in a number with no unit
- Severity: S4
- Screens: `#/`
- Where: all
- Repro: Open `#/`. Read the Boxes panel.
- Seen: `RB Origins · 34 on hand · 7 sold`, then a bar, then `42`. The 42 is every card ever captured (34 + 7 + 1 moved). No word says so.
- Shot: COPY-46, screenshot not kept.
- Direction: Give the figure a label, or remove it.
- Component: `app/src/Home.tsx`
- Annotation: no decision covers this.

### COPY-47 Pricing header spacing, and a run id in the header
- Severity: S4
- Screens: `#/pricing`
- Where: 1440 and 390
- Repro: Open `#/pricing`.
- Seen: `22 of 22 decided ·8 nothing to add` and `1 run ·1 box`. The separator touches the next word. `demo-box3`, the machine name of a run, is in the header in mono.
- Shot: COPY-47, screenshot not kept.
- Direction: Even spacing. The header names the box, not the run id.
- Component: `app/src/Pricing.tsx` header, `ReadyPanel`
- Annotation: no decision covers this.

### COPY-48 The Kit shows repository paths and build notes
- Severity: S4
- Screens: `#/gallery`
- Where: all
- Repro: Open `#/gallery` from the palette (`Component kit`).
- Seen: `tokens.css`, `kit.css`, `kit/index.tsx`. `docs/specs/logo.md is the state of record and scripts/build-mark.mjs generates the geometry…` Captions such as `every one of those numbers is a structural zero`. It is a developer page, and it reads as one.
- Shot: COPY-48, screenshot not kept.
- Direction: If the owner is meant to use the Kit, remove the paths. For a developer-only Kit, no change.
- Component: `app/src/Gallery.tsx`
- Annotation: no decision covers this. D196 does not say whether `#/gallery` is exempt.

## Held-screen notes

Main state. Check again after the merge.

- `#/review`: A missing photo prints its file path on screen (`/banchi/demo/photos/1/42.jpg`) under `The file is not on disk`. The reason names are internal (`Two rows, one condition`, `Nothing decided the finish`, `Not in the export`). `Search the export` and `This read — what the run recorded about this card` use pipeline words. The position is `BOX 1SECTION 3CARD13` (COPY-14).
- `#/orders`: Buyers show as `09-03-26_00012`. This is demo data. Check what the live app shows. Other strings: `Hide never-seen SKUs`, `owed / sold / short`, `Every copy found (15)` beside `Ready to ship (5)`, `Tick shown / Untick shown`. The stage strip says `Shipping · No export` while Shipping has 331 orders loaded (COPY-44). `Showing only the copies this order was offered — not every copy in the store.` explains a mechanism.
- `#/inventory`: The header says `122 cards 4 boxes`, the fourth count (COPY-02). `Run box 1` and `Nothing running` use "run" again (COPY-12). `42 captured` where Home says `photographed`. Numbering runs across the box (`#1`, COPY-14).

## What I could not check

- `#/product` with data. The demo refuses every SKU tried (9027180, 9189757, 8937200). The chart, the sales markers and their labels are not read.
- `#/graveyard` contents. The demo holds no answer. Only the refusal state has a grade.
- Sales `On the shelf` (`Value my stock`) and `Compare to today's market`. The demo refuses both.
- Fulfillment search results and the pull view of a card. Search gave no answer (COPY-43).
- The contents of the Pricing price history sheet. The demo refuses it.
- Runs after step 1 of Identify (Reading, Cost). Reconcile and Mark down after the file drop. They need a TCGplayer file, or the demo refuses the call.
- Capture with a live camera after the frozen demo frame, and the text of the motion trigger readout.
- Codes with a code on file. The store holds none.
- Dark theme and 820 were not extracted separately. The strings do not change with the theme. Text that is cut at 820 is not checked, except COPY-01 (correct at 820).
- Tooltips were read as `title` attributes, not shown on hover (COPY-23, COPY-34 are measured, not seen).
- Toasts from real writes. Only the Release receipt was reached (`Released Astral Heron`, `Back on the rule until you set a price.`, `Undo`).
- The rule behind the `Needs pricing` badge (COPY-05) comes from its tooltip, not from code.
