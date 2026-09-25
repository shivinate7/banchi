# Coherence across features

Target: the published demo, `https://shivinate7.github.io/banchi/`, built from main at PR #454/#455.
Checkout: `agent-ae5fbc60bd788c62c` at `89544e01`. Routes come from `app/src/App.tsx` `ROUTES` (14).
Screenshots, probe scripts and raw data: not kept in this record.
390 in light and dark (full page, and a viewport-only shot at 390). Contact sheets:
`sheet-390-light.png`, `sheet-390-dark.png`, `sheet-820-light.png`, `sheet-820-dark.png`, `sheet-1440-dark.png`.

## Concept ledger

"Word" is the text on screen. "Drawn" is the visual form. "Where" is the place on the screen.
Held screens are marked (held). A dash means that the screen does not show the concept.
A slash separates two forms in one cell.

| Concept | Screen | Word | Drawn | Where |
|---|---|---|---|---|
| **Card** | Home | "cards", "photographed" | count in a sentence / one blank pastel card in the hero | stats line under the verdict / hero top right |
| | Capture | "Capture card", "captured" | stat figure | top-right stats / left panel button |
| | Runs | "Cards in", "photographs", "(30 cards)" | stat strip figure / count in a run title | run panel |
| | Pricing | card name + "Near Mint Foil · Spiritforged · 087/221 · Epic" | row: grey thumb square, bold name, grey meta line | worklist rows |
| | Sales | name only ("Premonition") | table cell, plain Inter, no set, no number, no thumb | By product table |
| | Fulfillment | "Type the name of the card", "cards" | large search field / box cards "35 cards" | centre column |
| | Product | "product" | - (SKU field only) | - |
| | Inventory (held) | name + "023/221 · Riftbound" | H2 name, mono number, game / list row "#1 Piercing Light" | right card panel / left list |
| | Review (held) | "Draven, Audacious · 148/221" | name + mono number | question panel |
| **Copy** | Home | "copies to pull", "copies ... cannot be found" | inline bold figure | verdict and "Behind that" line |
| | Pricing | "QTY … of 1", "21 copies" | number input with "of N" under it | QTY column / right card |
| | Sales | "Copies" | table column | By product table |
| | Inventory (held) | "copy", "Every copy of this card" | stat figure + copy card | right panel |
| | Orders (held) | "owed", "short" | stat figures | order panel |
| **Box / drawer** | Home | "RB Origins" (no "Box" word) + number tile / hero pill "Box 4 · Mixed Singles" / tile "Box 4" | black number tile + name / dark pill with mono | Boxes card / hero / Capture tile |
| | Capture | "BOX / No box yet", "No box" | picker in the left panel / label under the camera | left panel / camera foot |
| | Runs | "Box 3 · RB Epics" + "demo-box3" | title + mono slug | run list / run panel |
| | Pricing | "Box 3 · RB Epics" + "demo-box3", "1 box" | meta line + mono slug | under the H1 / Scope block |
| | Fulfillment | "Box 1 · RB Origins", "35 cards" | black number tile + bold "Box N · name" | box list |
| | Inventory (held) | rail "RB Origins" (no number, recency order) / panel "BOX 1 / RB Origins" / 390 picker "Box 1 (RB Origins)" / details "BOX RB Origins Box 1" | four forms on one screen | left rail / box panel / phone picker / card panel |
| | Review (held) | "BOX 1 SECTION 3 CARD 13" | caps pill with an arrow on the photo | photo foot |
| | (all screens) | "drawer" is on no owner screen | - | - |
| **Section** | Capture | "New section" | ghost button with S keycap | left panel |
| | Inventory (held) | "SECTION 1: COMMONS, #1–#11", "Section 1 · Commons" | caps group header / meta line | list / card panel |
| | Review (held) | "SECTION 3" | inside the address pill | photo foot |
| **Position / address** | Capture | "next index", "index span" | top-right stat | header |
| | Inventory (held) | "#1", "CARD 1", "card 1 of 11 slots", "#1 of 34", "Box 1 · Section 1 · Card 1" | five forms | list / card panel / position bar / photo note |
| | Review (held) | "CARD 13", "still at its slot" | pill / sentence | photo |
| | Pricing, Sales, Shipping, Runs | - (no address shown) | - | - |
| **SKU** | Runs | "30 SKUs" | stat strip | run panel |
| | Pricing | "30 SKUs", "15 SKUs", "8 SKUs" / drawer "sku 9027180" (lower case, mono) | chip counts / mono line | header meta / section heads / history drawer |
| | Product | "TCGplayer SKU", `e.g. 555123` | plain input + a separate button below | top of page |
| | Inventory (held) | "SKU 9027170" | mono meta line, not a link | card panel |
| | Orders (held) | "Hide never-seen SKUs" | checkbox | filter column |
| **Product** | Sales | "BY PRODUCT" | section eyebrow over a name table | lower half |
| | Product | "Product history", "per product" | page title | header |
| **Set** | Pricing | "Spiritforged" | inside the grey meta line | row |
| | Capture | "Set hint … Needed" | stack row | left panel |
| | Inventory (held) | "Set" filter / "Set hint none" | select / details row | rail / Details |
| | Sales, Review, Fulfillment | - | - | - |
| **Price: market** | Pricing | "MARKET" | bold Inter figure | column 3 |
| | Sales | "Compare to today's market" | ghost button | By product |
| | Review (held) | unlabelled "$1.32" on each condition row / "NEXT … $0.48" | Manrope figure / Inter chip | option rows / photo top |
| | Inventory (held) | "Market could not be read" | details row | Details |
| **Price: listing** | Pricing | "LISTS AT", "Typed", "On the rule", "0 live" | bordered input with "$" and a check | column 4 |
| | Inventory (held) | "live on TCGplayer" / "Pushed 0 · Staged 0 · Room for 1 more live" / "Listed: no import row yet" | red dot figure / meta line / details row | card panel |
| **Price: floor** | Pricing | "The cut-off", "Under the cut-off", "cheap = under the cut-off" | big $0.49 figure in a card / section head | top-left card |
| | Runs | "sub-threshold price" | sentence | Emit step |
| **Price: hold** | Pricing | "Hold", "Holding 1", "Held back from this run", "held = held back on purpose" | lock icon button / pill / section band / orange "Holding" chip | row / toolbar / list |
| | other screens | - | - | - |
| **Price history** | Pricing | "Price history" / "History" | clock icon on each row, opens a floating card from the LEFT | row actions |
| | Product | "Product history" | whole route | off-nav |
| | Sales | row expansion: Date / Order / Copies / Unit price | chevron row | By product |
| **Sale** | Home | "1,447 sold" | stats line | under the verdict |
| | Sales | "grossed", "Last sold" | verdict H2 / table | page |
| | Inventory (held) | "Mark sold", "7 sold" | button / stat | card panel / box panel |
| **Order** | Home | "7 open orders", "ORDERS 7" | verdict / tile | top / tile row |
| | Shipping | "331 orders" (tab), "126 orders" (download), order id "A2FFC195-000005-00023" | tab badge / mono id per card | tab strip / lane cards |
| | Home | the same 331 called "331 shipments in lanes" | tile | tile row (after a visit to Shipping) |
| | Sales | "across 7 orders", "ORDER A2FFC195-958565-00010" | sentence / mono id in the expansion | verdict / row |
| | Orders (held) | "7 open", "09-03-26_00012", "ORDER A2FFC195-256158-0…" | tab badge / big title / truncated mono eyebrow | tab / order panel |
| | Fulfillment | "No orders are waiting for a card right now" | green check card | top |
| **Buyer** | Orders (held) | "7 buyers", "Search buyers or order #" | subtitle / search placeholder | header / filter |
| | Shipping, Sales | - (no buyer shown) | - | - |
| **Run** | Home | "Recent runs", "2 runs to price", "Needs pricing" | list card / tile / blue chip | lower right / tiles |
| | Runs | run list + run panel, "Needs pricing" | list + stepper | page |
| | Pricing | "Runs 1", "1 run", "THIS RUN ONLY" | picker / scope block / grey card | toolbar / right card / cut-off card |
| | Inventory (held) | "Run box 1 →", "Run demo-run-1" | link / details row | box panel / Details |
| **Export / file** | Runs | "identifications.json", "pricing.json", "report.txt", "import files" | file tiles / sentence | FILES / Emit step |
| | Pricing | "Write the import file", "21 rows … in the import file", "Emit can still refuse." | primary button in a sticky bottom bar / sentences | bottom bar / right card |
| | Shipping | "export.csv", "pirateship-import.csv", "Read another file" | mono names in cards | top cards |
| | Review (held) | "Not in the export", "Search the export" | reason chip / button | reason strip / actions |
| **Reading** | Pricing | "PRICES READ 1 hour ago", "read 1 hour ago", "The reading did not come back" | stat / row meta / drawer error | right card / row / drawer |
| | Inventory (held) | "not read yet", "Market could not be read" | italics / details | card panel |
| | Review (held) | "This read", "Low confidence read" | disclosure / chip | foot / reason strip |
| **The store** | Home | "1,573 photographed · 100 on hand in 4 boxes · 1,447 sold" | stats line | under the verdict |
| | Shell | "122 cards" | mono text by the server dot | sidebar foot, every screen |
| | Inventory (held) | "122 cards · 4 boxes" | mono chip | header right |
| | Fulfillment | "101 cards are in 4 boxes" | sentence | above the box list |
| | Runs | "Reconcile the store" | secondary button | header toolbar |

## Grade matrix

| Route | Grade | One-line reason |
|---|---|---|
| `#/` Home | C | It sums up every feature, and three of its figures disagree with the screens it links to (card counts, "needs pricing", the capture box). |
| `#/capture` Capture | C | A private header shape, "index" where the other screens say card or #, and a box state that contradicts Home. |
| `#/runs` Runs | C | "Needs pricing" disagrees with Pricing, and it calls the write step "Emit" where Pricing says "Write the import file". |
| `#/review` Review | HELD | Held screen. Notes below. |
| `#/pricing` Pricing | D | The listing price reads "$1" for $13.11 at desktop widths. Its history drawer, money face and floor word differ from the rest of the app. |
| `#/orders` Orders | HELD | Held screen. Notes below. |
| `#/shipping` Shipping | C | "Order" means 331 here and 7 one tab away. Raw reason codes show where Review uses words. No order links to Orders. |
| `#/revenue` Sales | C | A card is a bare name with no link to the card, its history or its order. The order shows as a raw id. |
| `#/inventory` Inventory | HELD | Held screen. Notes below. |
| `#/graveyard` Graveyard | C | Header and error card match Codes. Its list could not be seen (the demo holds no recording for it). |
| `#/codes` Codes | B | It follows the shared header, empty state and action place. Its primary action moves at 390. |
| `#/fulfillment` Cards to pull | D | It tells the Fulfiller that no order waits, while Home and Orders say 27 copies are owed on 7 open orders. |
| `#/gallery` Kit | B | The kit is sound. Three screens use private primitives it does not hold (history drawer, plain SKU input, capture header). |
| `#/product` Product history | D | No screen and no palette entry leads to it. It asks for a SKU that only one held screen shows. |

## Findings

### COH-01 The Fulfiller is told that nothing waits, while the owner is told that 27 copies are owed
- Severity: S1
- Screens: `#/fulfillment`, `#/`, `#/orders`
- Where: all
- Repro: open `#/` and read "Cannot be filled: 6 copies for 7 open orders cannot be found. Behind that: 27 copies to pull". Open `#/fulfillment` in the same browser.
- Seen: Cards to pull says "No orders are waiting for a card right now." with a green check. Home and Orders (7 open, 21 lines across 7 buyers) say that work is owed. Both screens read the same order data but give opposite verdicts. The Fulfiller is the person who acts on it.
- Shot: COH-01, screenshot not kept.
- Direction: one answer to "what waits to be pulled", computed once and drawn on Home, Orders and Cards to pull. If the Fulfiller's screen cannot place a card, it says so. It never shows a green "nothing waits".
- Component: `app/src/Fulfillment.tsx`, `orderGroups` and the `today` branch (`first === undefined`). Home's count is in `app/src/Home.tsx`.
- Annotation: no decision covers this. D212 (no order claims a copy) is the nearest entry. Home counts owed copies across the store, and Cards to pull builds its walk from the picks of each order. Which count is right is unmeasured. prior: none (the 2026-09-20 fulfillment review saw this empty state on a store with zero open orders, where it was true).

### COH-02 The listing price shows only its first digit at desktop widths
- Severity: S1
- Screens: `#/pricing`
- Where: 1100, 1280 and 1440 in both themes (measured). 820 and 390 show the full figure.
- Repro: open `#/pricing` at 1440. Read the LISTS AT column for Premonition.
- Seen: the input holds 13.11 but is 9px wide, so the cell reads "$ 1 ✓ Typed". Every row shows one digit: $2.52 reads "$2" and $0.49 reads "$0". The same price reads in full at 820, and every other screen draws a price in full. The owner sets prices from this column.
- Shot: COH-02, screenshot not kept.
- Direction: the listing price is legible in full at every width, the same as the market figure beside it.
- Component: `app/src/Pricing.tsx`, the `pricing-input` field in the worklist row.
- Annotation: no decision covers this.

### COH-03 Product history has no door
- Severity: S2
- Screens: `#/product`, and every screen that shows a card
- Where: all
- Repro: from any screen, look for a link to a product's history. Press ⌘K and type "product" or "history".
- Seen: no screen links to `#/product` (DOM links measured on all 14 routes). ⌘K "product" answers "Nothing matches". "history" offers only Sales and Graveyard. The page then asks for a "TCGplayer SKU". Only Inventory (held) shows a SKU number, and it is plain text, not a link. Pricing rows, Sales rows and Review never show one.
- Shot: COH-03, screenshot not kept.
- Direction: every place that shows a card or a product opens its history in one press, and the palette finds the page by name.
- Component: `app/src/App.tsx`, `commands` (the palette lists only `r.nav` routes). `app/src/ProductHistory.tsx`.
- Annotation: caused by D227 (a product price view is a route, not a lens). Its premise "reachable through its own control" does not hold. The control is on the page, and nothing leads to the page, because the palette lists only nav routes. The link from Sales that D227 deferred "the day that file is free" is still not built.

### COH-04 Price history lives in three places that do not know about each other
- Severity: S2
- Screens: `#/pricing`, `#/product`, `#/revenue`
- Where: all
- Repro: on `#/pricing`, press the clock icon on a row. On `#/revenue`, open the chevron of a row. Open `#/product?sku=9027180`.
- Seen: Pricing opens a floating drawer with History and Photo tabs. Sales opens a row into Date / Order / Copies / Unit price. Product history is a full page with its own chart. None of them links to another. The owner must know three places to answer one question: what has this card sold for?
- Shot: COH-04, screenshot not kept.
- Direction: one price-history view for a SKU. The other two places open it, or become it.
- Component: `app/src/Pricing.tsx` (`pricing-drawer`), `app/src/Revenue.tsx`, `app/src/ProductHistory.tsx`.
- Annotation: caused by D62 (price history drawn beside the hold, not on Inventory) and D227 (a product price view is a route). D227 shares one reader between the two, but not one view. Nothing covers the Sales row expansion.

### COH-05 Every screen gives a different number of cards
- Severity: S2
- Screens: shell (every screen), `#/`, `#/fulfillment`, `#/runs`, `#/inventory` (held)
- Where: all
- Repro: open `#/`, then `#/fulfillment`, then `#/runs`. Read the sidebar foot on each.
- Seen: the sidebar foot says "122 cards". Home says "100 on hand in 4 boxes" and "1,573 photographed". Cards to pull says "101 cards are in 4 boxes". Box 1 is "34 on hand" on Home and "35 cards" on Cards to pull. Box 4 is "15 on hand", but the Capture tile on Home says "18 cards in Mixed Singles". Runs says "Box 3 · RB Epics (30 cards)" against 26 on hand. Each figure can count a different thing. No label says which, so they read as disagreement.
- Shot: COH-05, screenshot not kept.
- Direction: one word per count ("on hand", "photographed", "ever captured"), used the same on every screen. The headline "cards" figure means one thing everywhere.
- Component: `app/src/App.tsx` sidebar foot (`status.cards`), `app/src/Home.tsx`, `app/src/Fulfillment.tsx`.
- Annotation: no decision covers this. D198 (Home's Review tile counts both queues) is the precedent for one tile that reads the same total as its screen. It was not applied to the card counts.

### COH-06 "Needs pricing" shows on runs that Pricing calls answered
- Severity: S2
- Screens: `#/`, `#/runs`, `#/pricing`
- Where: all
- Repro: `#/runs` shows both runs as "Needs pricing", and Home says "2 runs to price". Open `#/pricing` and `#/pricing?run=demo-box1`.
- Seen: Pricing says "22 of 22 decided … Pricing is answered. Ready to write" for Box 3, and "29 of 29 decided … Pricing is answered" for Box 1. The run waits on the write, not on a price. Two features give one state two names, and one name is wrong.
- Shot: COH-06, screenshot not kept.
- Direction: the status of a run names the step it really waits on, in the words that Pricing uses.
- Component: `app/src/Runs.tsx` status chip, `app/src/Home.tsx` Pricing tile.
- Annotation: caused by D156 (a run stays open until the last unsent copy has gone). The run stays open for the write, and the chip still says "pricing".

### COH-07 A card on one screen cannot take you to the same card on another
- Severity: S2
- Screens: `#/pricing`, `#/revenue`, `#/shipping`, `#/runs`, `#/inventory` (held)
- Where: all
- Repro: on each screen, try to open the place of a card in its box, its history, or its orders.
- Seen: hash links measured per screen: Pricing links only to Runs and Review. Sales links to Home only. Shipping links only to its own tabs. Inventory links only to Runs. The one card-to-card link in the app is the address pill on Review, which opens Inventory. A Pricing row, a Sales row and a Shipping order are dead ends.
- Shot: COH-07, screenshot not kept.
- Direction: a card or order drawn anywhere opens the same card or order where it lives, in one press, the same way on every screen.
- Component: row components in `Pricing.tsx`, `Revenue.tsx` and `Shipping.tsx`.
- Annotation: no decision covers this in general. D62 (price history drawn beside the hold) keeps history off Inventory on purpose, which removes one of the links.

### COH-08 "Order" counts two different things, one tab apart
- Severity: S2
- Screens: `#/shipping`, `#/orders` (held), `#/`, `#/revenue`
- Where: all
- Repro: open `#/shipping` and read the stage tabs. Then open `#/` after the visit.
- Seen: the tab strip reads "Orders 7 open" beside "Shipping 331 orders". The Home tile calls the same 331 "shipments in lanes". Sales says "7 orders" for its period. Three strings name one order: the Orders title "09-03-26_00012", the Orders eyebrow "A2FFC195-256158-0…", and the raw mono "A2FFC195-…" on Shipping and Sales. Shipping and Sales never show the buyer that Orders groups by.
- Shot: COH-08, screenshot not kept.
- Direction: one word and one label for an order on every screen, with the buyer beside it. A count says what it counts ("331 in the export", "7 open").
- Component: `app/src/Shipping.tsx` lane cards, the OrdersHub stage strip.
- Annotation: no decision covers the word. D193 (the ledger holds the buyer's name) is why Orders groups by buyer. Shipping and Sales do not use it.

### COH-09 The write step has three names
- Severity: S3
- Screens: `#/runs`, `#/pricing`
- Where: all
- Repro: open a run on `#/runs`, then open `#/pricing`.
- Seen: Runs calls it "Emit" (step 3) and "Price and emit this run". The Pricing button says "Write the import file", and the same card then says "Emit can still refuse." The owner cannot tell that these are one act.
- Shot: COH-09, screenshot not kept.
- Direction: one name for the act, the words on the button, on both screens.
- Component: `app/src/Runs.tsx` step list, `app/src/Pricing.tsx` ready card.
- Annotation: violates D196 (no pipeline-internal noun on screen). "Emit" is the name of a pipeline command. Unmeasured whether the D196 checker lists this word.

### COH-10 The floor is "the cut-off" on Pricing and "sub-threshold" on Runs
- Severity: S3
- Screens: `#/pricing`, `#/runs`
- Where: all
- Repro: read the top-left card on `#/pricing`. Then open `#/runs`, Box 3, Emit step.
- Seen: Pricing says "The cut-off", "Under the cut-off" and "cheap = under the cut-off". Runs says "Emit refuses while a sub-threshold price is unanswered."
- Shot: COH-10, screenshot not kept.
- Direction: one word for the floor on every screen.
- Component: `app/src/Runs.tsx` Emit step copy.
- Annotation: violates D196 (no pipeline-internal noun on screen). D98 (the cheap-card figure is the control) is the entry that named the floor for Pricing.

### COH-11 A box is drawn and named in six ways, and listed in two orders
- Severity: S3
- Screens: `#/`, `#/capture`, `#/runs`, `#/pricing`, `#/fulfillment`, `#/inventory` (held), `#/review` (held)
- Where: all. The parenthesis form shows at 390.
- Repro: compare the Boxes card on `#/`, the run title on `#/runs`, the box list on `#/fulfillment`, and the rail on `#/inventory`.
- Seen: Home draws a black number tile + name, with no word "Box", and a hero pill "Box 4 · Mixed Singles". Runs and Pricing draw "Box 3 · RB Epics" + the mono slug "demo-box3". Cards to pull draws a number tile + "Box 1 · RB Origins". Inventory draws the name alone in the rail, "BOX 1 / RB Origins" in the panel, and "Box 1 (RB Origins)" at 390. Review draws "BOX 1" in a caps pill. Home and Cards to pull list boxes 1 to 4. The Inventory rail lists RB Origins, RB Epics, MEG Bulk, Mixed Singles.
- Shot: COH-11, screenshot not kept.
- Direction: one box label (number + name) on every screen, and one order for a list of boxes.
- Component: `Home.tsx` Boxes card, `Fulfillment.tsx` box list, the Inventory rail.
- Annotation: caused by D132 (the Inventory rail is ordered by the hand) and D142 (the Capture box list is ordered by the hand). Both are owner rulings for two screens. Home and Cards to pull keep the numeric order. No decision covers the label form.

### COH-12 The place of a card is "index", "#", "Card" and "slot"
- Severity: S3
- Screens: `#/capture`, `#/inventory` (held), `#/review` (held)
- Where: all
- Repro: read the `#/capture` header, the `#/inventory` card panel, and the `#/review` photo pill.
- Seen: Capture shows "next index" and "index span". Inventory shows "#1", "CARD 1", "card 1 of 11 slots", "#1 of 34" and "Box 1 · Section 1 · Card 1" on one screen. Review shows "CARD 13" and "still at its slot".
- Shot: COH-12, screenshot not kept.
- Direction: one word for the place of a card and one address form everywhere, the Capture header included.
- Component: `app/src/CaptureScreen.tsx` header stats.
- Annotation: caused by D58 (a number counts the cards in the box, the stored index never moves). Capture shows the stored index, Inventory shows the count, and the two use different words. "index" on screen also violates D196 (no pipeline-internal noun on screen).

### COH-13 Each screen draws a card in a different way
- Severity: S3
- Screens: `#/pricing`, `#/revenue`, `#/fulfillment`, `#/inventory` (held), `#/review` (held)
- Where: all
- Repro: compare one card row on each screen.
- Seen: Pricing draws a thumb + name + "Near Mint Foil · Spiritforged · 087/221 · Epic". Sales draws the name alone, with no set, number or thumb, so two printings of one name look the same. Inventory draws name + mono number + game. Review draws name + "· 148/221". There is no shared card row.
- Shot: COH-13, screenshot not kept.
- Direction: one card identity line (name, set, number, finish) wherever a card is listed.
- Component: `Pricing.tsx` row, `Revenue.tsx` name cell.
- Annotation: no decision covers the card line. D67 (the number a screen draws is composed once) covers the number only.

### COH-14 A missing photograph is drawn in four ways
- Severity: S3
- Screens: `#/pricing`, `#/`, `#/inventory` (held), `#/review` (held)
- Where: all
- Repro: open each screen in the demo (the demo serves no photo files).
- Seen: Pricing draws an empty grey square with no message. The Home hero draws a pastel gradient card. Inventory draws a hatched panel with a warning, a sentence and a file path. Review draws a dark panel, "The file is not on disk", with a path.
- Shot: COH-14, screenshot not kept.
- Direction: one "no photo" state, drawn the same at every size.
- Component: `Pricing.tsx` `PricingThumb`, the Home hero.
- Annotation: no decision covers this.

### COH-15 Money is set in four typefaces
- Severity: S3
- Screens: `#/revenue`, `#/pricing`, `#/shipping`, `#/review` (held)
- Where: all (measured at 1440, seen in the shots)
- Repro: compare a dollar figure on each screen.
- Seen: Sales uses JetBrains Mono (`.bn-money`). The Pricing market column uses bold Inter. The Shipping value chips use Inter. Review uses Manrope for candidate prices and Inter for the "NEXT" price.
- Shot: COH-15, screenshot not kept.
- Direction: one money style on every screen.
- Component: `pricing-ref-market`, `shipping-figure`, `review-candidate-price`.
- Annotation: violates D221 (money stays mono). D221 argues that "Pricing's worklist … agree[s] on the mono face already". Measured: the Pricing market column is Inter, so that premise is false. prior: ux-2026-09-20/pricing.md (finding 4, Pricing money skips the shared formatter).

### COH-16 The reload control has five forms in five places
- Severity: S3
- Screens: `#/runs`, `#/pricing`, `#/graveyard`, `#/codes`, `#/revenue`, `#/orders` (held), `#/review` (held)
- Where: 1440 and 390
- Repro: find the reload control on each screen.
- Seen: Runs has a bare icon after the scope chip. Pricing has an icon + "R" keycap in the toolbar. Review has an icon + "R" keycap at top right. Graveyard has a bare icon at top right, on its own row at 390. Codes has an icon left of the primary button. Orders has a "Read it again" text button in an info bar. Sales has "Compare to today's market".
- Shot: COH-16, screenshot not kept.
- Direction: one reload control in one place in the page header, with the same key on every screen.
- Component: the header of each screen.
- Annotation: no decision covers this.

### COH-17 The page header has a different shape on each screen
- Severity: S3
- Screens: `#/`, `#/capture`, `#/runs`, `#/pricing`, `#/shipping`, `#/revenue`, `#/codes`, `#/fulfillment`, `#/product`
- Where: all
- Repro: open each route at 1440 and look at the top 120px.
- Seen: Home has a 56px greeting and no title. Capture has its own header (`capture-head`) with stats at top right and no subtitle. Pricing has a meta line and a small legend of definitions under the title. Orders has a count as its subtitle. The other screens have a sentence. The primary action also moves. It sits under the subtitle on Runs and at top right on Codes. Pricing puts it in a sticky bottom bar, Shipping inside a card, and Capture in a side panel.
- Shot: COH-17, screenshot not kept.
- Direction: one header: a title, one line, and the one primary action of the screen in one place.
- Component: `bn-head` on most screens, `capture-head` in `CaptureScreen.tsx`, `home-title` in `Home.tsx`.
- Annotation: no decision covers this. D197 (one left edge for every page) governs the edge only.

### COH-18 The verdict line sits in a different place, or nowhere
- Severity: S3
- Screens: `#/`, `#/revenue`, `#/pricing`, `#/runs`, `#/shipping`
- Where: all
- Repro: find the one sentence that says where things stand.
- Seen: Home has a ranked alert card under the greeting. Sales has an H2 "You grossed…" under the header. Pricing has "Pricing is answered." inside the right-hand card, halfway down. Runs and Shipping have none.
- Shot: COH-18, screenshot not kept.
- Direction: each work screen states its verdict in the same place and in the same form.
- Component: each screen.
- Annotation: no decision covers this across screens. D208 (Pricing states its verdict once) governs Pricing alone, and puts the verdict in the headline deck, not inside a side card.

### COH-19 Price history opens from the left as a floating card, and every other sheet opens from the right
- Severity: S3
- Screens: `#/pricing`, compared with `#/runs` and `#/inventory` (held)
- Where: 1440
- Repro: on `#/pricing`, press the clock icon of a row. Then press "Mark down stale". On `#/runs`, press "Reconcile the store".
- Seen: measured. Mark down (x=880, w=560), Reconcile (x=920, w=520) and Manage box (x=980, w=460) open full height from the right edge. Price history opens at x=252, w=380, as a card with a gap above and below it, over the list.
- Shot: COH-19, screenshot not kept.
- Direction: one side-sheet behaviour for the whole app.
- Component: `app/src/Pricing.tsx` `bn-sheet-left pricing-drawer`.
- Annotation: no decision covers the side. D62 (price history drawn beside the hold) argues that the panel is pinned, not where it opens.

### COH-20 Search has two forms, and is missing where the list is longest
- Severity: S3
- Screens: `#/product` and `#/pricing`, compared with `#/revenue`, `#/fulfillment`, `#/inventory` (held) and `#/orders` (held)
- Where: all
- Repro: compare the search field on each screen.
- Seen: Sales, Orders and Inventory share one field with a "/" keycap (37px). Cards to pull uses the same field at 60px. Product history uses a plain 34px input with a separate button below it. Pricing has no name search over its 30-plus rows.
- Shot: COH-20, screenshot not kept.
- Direction: the shared search field on every screen that lists or finds cards, Pricing included.
- Component: `ProductHistory.tsx` uses `bn-input`, not the search field.
- Annotation: no decision covers this. D227 (a product price view is a route) built the plain field.

### COH-21 One clock icon has four meanings
- Severity: S3
- Screens: shell nav, `#/product`, `#/runs`, `#/`, `#/pricing`
- Where: all
- Repro: look at the Graveyard nav row, the Product history title, the Runs list header, "Recent runs" on Home, and the history button on each Pricing row.
- Seen: the same `history` icon marks the graveyard, product price history, the run list and the price history of a row.
- Shot: COH-21, screenshot not kept.
- Direction: one icon, one meaning.
- Component: `ROUTES` (`icon: 'history'` on `/graveyard` and `/product`).
- Annotation: no decision covers this.

### COH-22 Shipping shows raw reason codes, and Review puts its reasons in words
- Severity: S3
- Screens: `#/shipping`, `#/review` (held)
- Where: all
- Repro: open any lane card on `#/shipping`, then the reason strip on `#/review`.
- Seen: every Shipping card ends in a mono code: "cards_only", "value_at_threshold" or "no_weight_data", beside a sentence that already says the same. Review puts its reasons in words ("Low confidence read", "Not in the export").
- Shot: COH-22, screenshot not kept.
- Direction: reasons in words only, as Review does.
- Component: `app/src/Shipping.tsx` lane card.
- Annotation: violates D196 (no pipeline-internal noun on screen). prior: ux-2026-09-20/review.md (finding 1). The owner removed the reason code from Review (TASTE-CALLS "chip, tooltip, gone"). The same fix did not reach Shipping.

### COH-23 A listing has six names
- Severity: S3
- Screens: `#/pricing`, `#/inventory` (held)
- Where: all
- Repro: read the listing words on both screens.
- Seen: Pricing says "Lists at", "0 live" and "Every copy is already at TCGplayer". Inventory says "live on TCGplayer", "Pushed 0 · Staged 0 · Room for 1 more live" and "Listed: no import row yet".
- Shot: COH-23, screenshot not kept.
- Direction: one word for "on TCGplayer now" and one for "sent but not yet live", on both screens.
- Component: the copy of each screen.
- Annotation: violates D196 (no pipeline-internal noun on screen) for "Pushed" and "Staged". D87 (the reconcile writes live) is where "live" comes from.

### COH-24 Dates and times use six formats
- Severity: S3
- Screens: `#/`, `#/runs`, `#/pricing`, `#/revenue`, `#/orders` (held), `#/inventory` (held)
- Where: all
- Repro: read any timestamp.
- Seen: "1h ago" (Home, Runs), "1 hour ago" (Pricing), "Aug 31, 2026" and a zero-padded "Sep 03, 2026" (Sales), "9:30am · Aug 13" (Inventory), "placed Sep 3" (Orders), "WEDNESDAY, SEPTEMBER 23" (Home).
- Shot: COH-24, screenshot not kept.
- Direction: one relative form and one absolute form, used everywhere.
- Component: the date formatter of each screen.
- Annotation: no decision covers this. prior: ux-2026-09-20/sales.md (finding 3, Sales date format). It changed since, to a zero-padded form, and still differs from the other screens.

### COH-25 Home says that the capture box is Box 4, and Capture says that there is no box
- Severity: S3
- Screens: `#/`, `#/capture`
- Where: all (fresh browser)
- Repro: open `#/` in a fresh browser. The Capture tile reads "Box 4, 18 cards in Mixed Singles" and the hero pill reads "Box 4 · Mixed Singles". Press the tile.
- Seen: Capture says "No box yet. Pick one", and its Recent panel says "Pick a box to start." Home reads the store. Capture reads the setup of this device. The owner sees two answers to "which box am I filling?".
- Shot: COH-25, screenshot not kept.
- Direction: the Home tile and Capture agree, or the tile names what it shows ("last box captured").
- Component: `Home.tsx` Capture tile, `CaptureScreen.tsx` box picker.
- Annotation: caused by D142 (the setup outlives the browser, and lives on the device). Home reads the store, and Capture reads the device. Nothing reconciles the two.

### COH-26 "2 runs to price" on Home opens a page scoped to one run
- Severity: S3
- Screens: `#/`, `#/pricing`
- Where: all
- Repro: on `#/`, press the Pricing tile ("2 runs to price").
- Seen: it opens `#/pricing` scoped to Box 3 only ("Runs 1"). Box 1 is behind the Runs picker, and nothing on the page says that a second run waits.
- Shot: COH-26, screenshot not kept.
- Direction: the link opens what its label counted.
- Component: `Home.tsx` Pricing tile href, the default scope of Pricing.
- Annotation: violates D156 (every copy TCGplayer does not hold is one worklist). Measured on the demo: the default landing shows one run, and the second run opened by hand has 27 rows to write.

### COH-27 An error is drawn in three ways
- Severity: S3
- Screens: `#/graveyard`, `#/pricing`, `#/revenue`, `#/orders` (held)
- Where: all
- Repro: open `#/graveyard`. Open the history drawer on `#/pricing`. Press "Value my stock" on `#/revenue`.
- Seen: Graveyard draws a centred card with an icon badge and "Try again". The Pricing drawer draws a red alert box, then a "Try again" button, then a separate "Close" button. Sales draws a red banner at the foot of the page. Orders draws its demo notice as an unstyled paragraph. All four texts show a repo command (`make demo`) and a wire path. That text comes from the demo layer, but the three error drawings are the product's.
- Shot: COH-27, screenshot not kept.
- Direction: one error state, used everywhere a read fails.
- Component: the error branch of each screen.
- Annotation: no decision covers this.

### COH-28 On a phone, the tab bar does not show where you are on seven screens
- Severity: S4
- Screens: `#/`, `#/runs`, `#/pricing`, `#/shipping`, `#/revenue`, `#/graveyard`, `#/codes`
- Where: 390, both themes
- Repro: open any of these screens at 390.
- Seen: the tab bar holds Capture, Review, Orders, Inventory and More. On these seven screens no tab is lit, "More" included.
- Shot: COH-28, screenshot not kept.
- Direction: "More" is lit when the screen lives behind it.
- Component: `app/src/App.tsx` `bn-tabbar`.
- Annotation: no decision covers this.

### COH-29 The Sales table draws two rules under each row
- Severity: S4
- Screens: `#/revenue`
- Where: 1440 and 820, both themes
- Repro: open `#/revenue` and look at the By product table.
- Seen: the bottom rule of the name cell sits higher than the rule of the row. Each row has a short line under the name and a full line under the row. No other list in the app does this.
- Shot: COH-29, screenshot not kept.
- Direction: one rule per row, as the other lists draw it.
- Component: `app/src/Revenue.tsx` name cell.
- Annotation: no decision covers this.

## Held-screen notes

Main state, re-check after merge.

- `#/orders`: rows and the order panel have the title "09-03-26_00012", while the subtitle says "7 buyers" and the search says "Search buyers". No buyer name shows. (`orders-1440-light.png`)
- `#/orders`: the stage tab reads "Shipping · No export" until `#/shipping` is visited. After that it reads "331 orders". The Shipping tile on Home changes the same way. This can be demo seeding (see below).
- `#/orders`: the demo notice under the order panel is an unstyled paragraph at body size that runs to the edge of the card.
- `#/inventory`: the rail lists boxes by name only, in recency order. The panel says "BOX 1 / RB Origins". At 390 the picker says "Box 1 (RB Origins)". Three box forms on one screen (COH-11).
- `#/inventory`: the header chip "122 cards · 4 boxes" sits beside a box panel of "34 on hand" (COH-05).
- `#/inventory`: the card panel shows "SKU 9027170" as text and "Market could not be read", with no link to Pricing, price history or Product history (COH-03, COH-07).
- `#/inventory`: five position forms on one screen: "#1", "CARD 1", "card 1 of 11 slots", "#1 of 34", "Box 1 · Section 1 · Card 1" (COH-12).
- `#/review`: its address pill is the only card-to-card link in the app. It is the pattern that the other screens do not have (COH-07).
- `#/review`: candidate prices have no label and use Manrope. The "NEXT" price uses Inter (COH-15).

## What I could not check

- The content of `#/graveyard`. The demo holds no recording for it, so only its error state was seen.
- "Value my stock" on Sales, and the content of the Pricing price-history drawer. The demo holds no recording for either.
- Whether COH-01 (the Fulfiller is told that nothing waits) occurs on the live app. It was seen on the recorded demo data only.
- The first state of Shipping. On the demo, the Shipping screen shows "export.csv, 331 orders" at once. Home and Orders say "no export" until Shipping is visited. This can be how the demo seeds itself. Unknown for the live app.
- Codes with codes on file (the feature is dormant and empty in the demo). Capture with a camera (the demo refuses it).
- A full-page capture of `#/review` at 1440 collapsed the sidebar during the capture. The page is 913px tall, so the capture resizes the viewport. At a fixed window the sidebar stays open (measured). This is not a finding.
- Hover and focus states. Not reviewed for this lens.
