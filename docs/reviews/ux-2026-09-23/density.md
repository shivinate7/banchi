# Text density: too many words

Target: the published demo, `https://shivinate7.github.io/banchi/` (main at #455). The route
list comes from `app/src/App.tsx` `ROUTES`, 14 rows. Scripts: TXT scratch file, not kept and
TXT scratch file, not kept.

A "word" is a visible token on the page. Text in a screen-reader span (`.bn-sr`, a 1px clip)
and text under `display: none` are not counted. "Main" is the `<main>` element, so the counts
do not include the shell sidebar (about 36 words at 1440). A "prose block" is one block element
with 6 or more words.

Text in backticks inside quotes is the exact text on the screen.

## Cut list

"J" marks a judgement call. The owner decides. The totals include J rows, and the J share is
given beside each total.

| ID | Route | Current text | Proposed | Words saved |
|---|---|---|---|---|
| TXT-01 | #/shipping | "`Cards only, and under $50.`" on each of 166 Envelope cards | delete (the lane header says "Cards only, under $50") | 830 |
| TXT-01 | #/shipping | "`Worth $50 or more, so tracking is required.`" on each of 112 Parcel cards | delete (the lane header says it) | 896 |
| TXT-02 | #/shipping | `cards_only` or `value_at_threshold` on each of 278 lane cards, `non_card_signal` on 14 Parcel cards, and `no_weight_data` on 39 Needs-a-look cards | delete | 331 |
| TXT-03 | #/shipping | "`Inferred`" (180 cards) or "`Certain`" (112 cards) | an icon with the word as a tooltip (J) | 292 |
| TXT-04 | #/shipping | "`0.0700 oz/item`" on 187 cards, the same value on each | if it is the plain-card weight, delete it. Keep it where it differs (J) | 374 |
| TXT-05 | #/shipping | "`TCGplayer's shipping export, sorted into three lanes.`" | delete | 7 |
| TXT-05 | #/shipping | "`126 orders in the parcel lane are in this file.`" | delete (the button says "Download · 126 orders") | 10 |
| TXT-05 | #/shipping | "`held in memory for about 30 minutes · nothing written to disk`" | "kept 30 min" | 8 |
| TXT-06 | #/pricing | "`typed = you set a price. held = held back on purpose. on the rule = following the standing rule. cheap = under the cut-off.`" | delete | 21 |
| TXT-07 | #/pricing | "`Near Mint`" on each of 30 rows | delete "Near Mint" and keep "Foil" | 60 |
| TXT-08 | #/pricing | "`Typed`" under each of 21 price fields | delete (the check in the field shows it), keep the exceptions | 21 |
| TXT-08 | #/pricing | "`of 1`" under each of 22 quantity fields | if the quantity equals the copies on hand, delete it (J) | 44 |
| TXT-09 | #/pricing | "`the line, and what everything under it lists at`" | delete | 9 |
| TXT-09 | #/pricing | "`15 under · 15 above`" | delete (each section header gives "15 SKUs") | 4 |
| TXT-09 | #/pricing | "`Market below $0.49, so these go out at $0.49 — unless you type a price on the row.`" | "Lists at $0.49 unless typed." | 11 |
| TXT-09 | #/pricing | "`At the $0.49 cut-off`" under 5 rows | "Cut-off" | 15 |
| TXT-10 | #/pricing | "`Pricing is answered.`" | delete (the heading and the green check say it) | 3 |
| TXT-10 | #/pricing | "`Not on this list, because nothing here can send them:`" | "Not listed:" | 8 |
| TXT-10 | #/pricing | "`21 rows and 21 copies would go in the import file.`" | "21 rows, 21 copies" | 6 |
| TXT-10 | #/pricing | "`Emit can still refuse.`" | delete (J) | 4 |
| TXT-10 | #/pricing | "`Scope 1 run · 1 box`" | delete (the header names the box) | 4 |
| TXT-10 | #/pricing | "`Nothing to add 8 SKUs`" | delete (the header says "8 nothing to add") | 4 |
| TXT-11 | #/pricing | "`split it in two, either side of the cut-off`" | "Split at cut-off" | 6 |
| TXT-11 | #/pricing | "`hold to [no cap] live per card`" | "Cap [ ]" | 4 |
| TXT-11 | #/pricing | "`next M L S D snap H hold T history P photo U undo`", always shown | move it to the `?` sheet (J) | 6 |
| TXT-12 | #/pricing, Load trends | "`no sales`" on each of 22 rows | "—" | 44 |
| TXT-13 | #/pricing, Mark down stale | "`Reads your live My Pricing export and proposes a lower price for listings that have not sold.`" | delete (the title says it) | 19 |
| TXT-13 | #/pricing, Mark down stale | "`Nothing is deleted at TCGplayer; the upload edits the live listing in place.`" | "Edits live listings. Deletes nothing." | 8 |
| TXT-13 | #/pricing, Mark down stale | "`This ranks on how long the listing has been live, … the report says which clock dated each.`" (52 words) | delete, or one ⓘ tooltip | 52 |
| TXT-13 | #/pricing, Mark down stale | "`or drop a My Pricing export below.`" | delete (the drop zone says it) | 7 |
| TXT-14 | #/pricing, Clear typed | "`Removes the answer, not the card — a cleared row shows the standing rule again. Nothing at TCGplayer changes.`" | "Nothing at TCGplayer changes." | 14 |
| TXT-14 | #/pricing, Clear typed | "`Nothing expires on its own — an answer stands until you clear it.`" | delete | 13 |
| TXT-14 | #/pricing, Clear typed | "`Undo is offered on the receipt, and it puts every answer back with the date it was typed on.`" | "You can undo this." | 15 |
| TXT-15 | #/pricing, Hold | "`Bullish — waiting for the price to move`" | delete (the selected chip says "Bullish") | 7 |
| TXT-15 | #/pricing, Hold | "`Every copy stays out of every import file until you release it — one answer for the whole store, outliving every run over this box.`" | "Stays out of every import until you release it." | 15 |
| TXT-16 | #/runs | "`Identify, join, emit and reconcile a box. Identify is the only step that spends money.`" | "Only Identify costs money." | 11 |
| TXT-17 | #/runs | "`Join, emit and reconcile act on the run you pick from the list.`" | delete (keep "Pick a run") | 13 |
| TXT-17 | #/runs | the panel title "`Runs`" under the H1 "`Runs`" | delete (keep "2 runs") | 1 |
| TXT-18 | #/runs, a run | "`Queued a whole stack under the wrong rarity? Fix it on Inventory → Manage box → Rarity, then press Identify and Join again here — correcting the box alone changes nothing. It costs nothing.`" | delete from the run page. Show it next to the Rarity control. | 31 |
| TXT-19 | #/runs, a run | the step strip "`Identify Join Emit Reconcile`" above the same four steps as rows | delete the strip | 4 |
| TXT-19 | #/runs, a run | "`30 SKUs, 0 to review and 0 parked`" (Join subtitle) | delete (the stat row gives 30, 0, 0) | 8 |
| TXT-19 | #/runs, a run | "`Free · re-runnable`" three times | "Free" | 3 |
| TXT-20 | #/runs, a run, Emit | "`Prices, holds and the sub-threshold answer are set on Pricing, and the same screen writes the import files. Emit refuses while a sub-threshold price is unanswered.`" | delete (the subtitle and the button say it) | 27 |
| TXT-20 | #/runs, a run, Emit | "`The pricing rule and basis are one answer for the whole store now. They are set on Pricing, not in this run.`" | delete | 22 |
| TXT-21 | #/runs, a run, Join open | "`Resolves each card against a TCGplayer export and writes the queues and the pricing questions.`" | delete | 15 |
| TXT-21 | #/runs, a run, Join open | "`Preview writes nothing — it walks the ladder and says what it would queue. One export file per game; fetching needs a TCGplayer session.`" | "Preview is free and writes nothing." | 17 |
| TXT-21 | #/runs, a run, Reconcile open | "`After Import to Staged on TCGplayer, download its Export From Staged and compare it with what emit wrote. Quantities move; nothing is marked sold.`" | "Upload TCGplayer's Export From Staged." (J) | 19 |
| TXT-21 | #/runs, a run, Identify open | "`Nothing was captured here — this run was started from a terminal.`" | delete (J) | 11 |
| TXT-22 | #/runs, Identify step 1 | "`Every photograph in the store whose card has not been identified yet — whatever drawer it is in.`" | "Every unidentified photograph, any drawer." | 12 |
| TXT-22 | #/runs, Identify step 1 | "`A card that has already been read is not read again, … on this store every one of 2,535 cards was already answered and cached.`" (45 words) | delete (the Cost step shows the real figure) | 45 |
| TXT-22 | #/runs, Identify step 1 | "`A section is a divider inside one drawer, so it needs exactly one drawer picked above.`" | "Pick one drawer first." | 12 |
| TXT-22 | #/runs, Identify step 1 | the footer "`Every card waiting to be identified`" | delete (it repeats the selected tab) | 6 |
| TXT-23 | #/runs, Identify step 2 | "`Crops to the card, sent at 1200px: $0.62 on box 2 and sharpest on the number. Photographs on disk are never touched.`" | "Crops to the card, 1200px." | 16 |
| TXT-23 | #/runs, Identify step 2 | "`This reading reaches every card in the press. Two drawers that want two readings are two presses.`" | delete | 17 |
| TXT-23 | #/runs, Identify step 2 | "`Every card waiting to be identified`" in the header and again in the footer | delete one | 6 |
| TXT-24 | #/runs, Reconcile the store | "`One live export — TCGplayer’s My Pricing, all printings — checked against every SKU in the store. … Moves quantities; marks no card sold.`" (44 words) | "Checks every SKU against your live TCGplayer listings. Moves quantities. Marks nothing sold." | 31 |
| TXT-24 | #/runs, Reconcile the store | "`Every LIVE figure in the store is only as current as the last time this ran.`" | "Last run: <date>" | 13 |
| TXT-24 | #/runs, Reconcile the store | "`or drop a My Pricing export below.`" | delete | 7 |
| TXT-25 | #/ | "`Behind that: 27 copies to pull · 9 to review · 2 runs to price`" | delete (the stage strip below gives the same numbers) | 13 |
| TXT-26 | #/ | "`Cannot be filled — 6 copies for 7 open orders cannot be found.`" | "Cannot be filled — 6 copies missing for 7 orders." | 6 |
| TXT-27 | #/ | stage notes "`runs on file`" and "`to answer`" | delete | 5 |
| TXT-27 | #/ | stage notes "`runs to price`", "`27 copies to pull and 6 …`" (truncated), "`no export read yet`" | "runs", "27 to pull", delete | 11 |
| TXT-28 | #/ | "`Wednesday, September 23`" and "`Good evening.`" | delete, and make the ranked line the heading (J) | 5 |
| TXT-29 | #/capture | "`Open the camera.`" (checklist line above an "Open the camera" button) | delete | 3 |
| TXT-29 | #/capture | "`The camera is not open`" (viewfinder heading above its own "Open the camera" button) | delete | 5 |
| TXT-30 | #/capture | "`Pick or name a box.`" (checklist line above a "Pick a box" button) | delete | 5 |
| TXT-30 | #/capture | "`Pick a box to start.`" (empty Recent panel) | delete | 5 |
| TXT-31 | #/capture | "`Nothing to clear.`" under the disabled "Clear the setup" button | delete | 3 |
| TXT-32 | #/capture, box picker | "`next index 43`" on each row | "#43" | 6 |
| TXT-32 | #/capture, box picker | "`Enter takes the top row. Anything new is created by name.`" | delete (J) | 11 |
| TXT-32 | #/capture, box picker | "`4 boxes`" above a list of four boxes | delete | 2 |
| TXT-33 | #/capture, Set hint | "`Needed for this game`" under a row that says "Needed" | delete | 4 |
| TXT-33 | #/capture, Tuning | "`Arm the motion trigger under Rig (T) and the machine's readout appears here.`" | "Trigger is off." | 10 |
| TXT-35 | #/revenue | "`Your gross-revenue retrospective — what sold, for how much, by name. Gross only: no fees, no cost, no profit.`" | "Gross sales. No fees or costs." | 12 |
| TXT-36 | #/revenue | "`So far, nothing is recorded for the period before this one.`" | delete | 11 |
| TXT-36 | #/revenue | "`0 orders were canceled by the marketplace and left out.`" | at 0, delete. Above 0, "N canceled orders left out". | 10 |
| TXT-36 | #/revenue | "`0 lines were marked refunded or canceled during fulfilment and left out — your own note, not TCGplayer's, so treat it as a habit rather than a guarantee.`" | at 0, delete. Above 0, "N refunded lines left out". | 27 |
| TXT-37 | #/revenue | "`, 2026`" on each of 22 "Last sold" dates | if all rows are in one year, drop the year | 22 |
| TXT-38 | #/graveyard | "`Every card that's left inventory — sold, retired, or moved. Read-only.`" | "Sold, retired and moved cards." | 5 |
| TXT-39 | #/codes | "`Read, tier, and hand off code cards.`" | delete | 7 |
| TXT-39 | #/codes, Read a box | "`Decodes every code-card photograph in the box. Free — the QR is the code.`" | "Free." | 12 |
| TXT-40 | #/product | "`What one product has been selling for, with your own sales marked on it.`" | delete | 14 |
| TXT-40 | #/product | "`This page is per product, and it never guesses which one you mean.`" | delete | 13 |
| TXT-41 | #/fulfillment | "`No orders are waiting for a card right now. You can still find any card by name.`" | "No orders waiting." (J) | 14 |
| TXT-41 | #/fulfillment | "`101 cards are in 4 boxes. Tap a box to see what is in it.`" | delete (J) | 15 |
| TXT-42 | #/fulfillment, a box open | "`Box 1 · Section 1 · Card 1`" on each of 35 rows inside the open Box 1 | a "Section 1" header, then "Card 1" on each row (J) | 64 |
| TXT-43 | #/fulfillment, a box open | the row "`Box 1 · departed · B1 #19`" in the pull list | delete the row | 5 |
| TXT-44 | #/gallery | ten design-log notes, 436 words ("`swept in section 11 at 16, 28, 32 and 44px`", "`settled by forced choice over thirty-seven rounds`") | one caption line each, about 10 words | 336 |
| TXT-44 | #/gallery | "`Switch the theme in the nav to see both.`" | delete | 9 |
| TXT-45 | shell, every owner route | "`Server online · 122 cards`" | "Server online" | 2 |
| TXT-46 | demo only | the 36-word demo refusal, drawn twice in the Identify modal, step 2 | draw it once | 36 |
| TXT-46 | demo only | "`This demo's recording holds no answer for GET /pipeline/price-now?sku=…`" (21 SKUs in the URL) "`Rebuild it with make demo.`", and four more of this shape | "Not in this demo." | 89 |

### Words saved

| Route | Saved | Of which J | Main words now (1440, default state) |
|---|---|---|---|
| #/ | 40 | 5 | 146 |
| #/capture | 54 | 11 | 105 |
| #/runs (default, run page, two modals, one sheet) | 346 | 30 | 67 in the default state |
| #/review | HELD | | 178 |
| #/pricing (default, four sheets and popovers) | 423 | 54 | 747 |
| #/orders | HELD | | 207 |
| #/shipping | 2,748 | 666 | 4,942 |
| #/revenue | 82 | 0 | 265 |
| #/inventory | HELD | | 270 |
| #/graveyard | 5 | 0 | 32 |
| #/codes | 19 | 0 | 33 |
| #/fulfillment | 98 | 93 | 76 (326 with Box 1 open) |
| #/gallery | 345 | 0 | 2,422 |
| #/product | 27 | 0 | 40 |
| shell | 2 | 0 | 36 |
| **Total, product** | **4,189** | **859** | |
| demo-only text | 125 | 0 | |
| **Total, with demo** | **4,314** | | |

Shipping is 66% of the total. The screens other than Shipping and the Kit give 1,096 words.

## Density per route

Default state, light theme. "Fold" is the count of words in `<main>` that are in the first
viewport (1440×900, or 390×844 on a touch device). "Blocks" is the count of distinct text blocks
in `<main>`.

| Route | Main words 1440 | Fold 1440 | Fold 390 | Text blocks | Prose blocks (6+ words) | Prose words |
|---|---|---|---|---|---|---|
| #/ | 146 | 146 | 65 | 58 | 4 | 36 |
| #/capture | 105 | 99 | 42 | 54 | 1 | 7 |
| #/runs | 67 | 67 | 49 | 17 | 4 | 40 |
| #/review | 178 | 178 | 106 | 67 | 7 | 69 |
| #/pricing | 747 | 239 | 138 | 371 | 11 | 126 |
| #/orders | 207 | 161 | 100 | 69 | 10 | 121 |
| #/shipping | 4,942 | 295 | 92 | 2,209 | 171 | 1,658 |
| #/revenue | 265 | 150 | 104 | 117 | 5 | 75 |
| #/inventory | 270 | 191 | 68 | 133 | 4 | 52 |
| #/graveyard | 32 | 32 | 32 | 5 | 3 | 29 |
| #/codes | 33 | 33 | 33 | 6 | 2 | 21 |
| #/fulfillment | 76 | 76 | 69 | 18 | 3 | 38 |
| #/gallery | 2,422 | 294 | 149 | 763 | 80 | 1,305 |
| #/product | 40 | 40 | 40 | 6 | 3 | 34 |

Pressed states, 1440 light, whole page with the shell:

| State | Words | Words in the sheet or modal |
|---|---|---|
| #/runs, a run open | 262 | none |
| #/runs, Identify step 1 | 381 | about 120 |
| #/runs, Identify step 2 | 279 | 171 (the demo refusal twice) |
| #/runs, Reconcile the store | 194 | 86 |
| #/pricing, Mark down stale | 1,065 | 163 |
| #/pricing, Clear typed | 1,022 | 110 |

**The screens with the most text for what they do:**

1. **#/shipping.** Its job is three counts and a download. It draws 4,942 words. Of these,
   2,057 are two sentences and four codes, repeated on each order card.
2. **#/gallery.** A component sheet with 1,305 words of prose. 436 of them are a design log:
   sweep sections, round counts, repo paths.
3. **#/product and #/graveyard.** They are small, but prose is 85% and 91% of their words.
   Each has a lede and an empty-state body that repeat the title.
4. **#/revenue at 390.** The first viewport is the lede and three sentences about zero counts.
   No product row shows before a scroll.
5. **#/pricing.** Labels on each row ("Near Mint", "Typed", "of 1") and five statements of the
   cut-off make the worklist long and noisy.

## Grade matrix

| Route | Grade | One-line reason |
|---|---|---|
| #/ (Home) | B | Lean. One line repeats the stage strip, and some stage notes repeat their label. |
| #/capture | C | The screen says "no box" five times and "camera not open" five times. |
| #/runs | C | The default state is lean. The run page, the Identify modal and the Reconcile sheet are heavy with paragraphs. |
| #/review | HELD | Held screen. See the notes. |
| #/pricing | D | A 21-word legend, three labels on each row, the cut-off five ways, and sheets that start with paragraphs. |
| #/orders | HELD | Held screen. See the notes. |
| #/shipping | F | Mostly repeated prose. Each order card repeats its lane rule as a sentence and as a code. |
| #/revenue (Sales) | C | At 390 the fold is a lede and three sentences about zeros. |
| #/inventory | HELD | Held screen. See the notes. |
| #/graveyard | B | A 10-word lede that can be 5. |
| #/codes | B | A lede that repeats the title, and a sheet sentence that can be one word. |
| #/fulfillment | B | Plain and short. "Box 1" repeats on each row inside Box 1, and a departed card is in the list. |
| #/gallery (Kit) | D | 2,422 words. A design log is printed on the component sheet. |
| #/product | C | 40 words, and 27 of them are a lede and an empty-state body that the field already says. |

## Findings

### TXT-01 Each shipping card repeats its lane rule as a sentence
- Severity: S2
- Screens: #/shipping
- Where: all
- Repro: open `#/shipping`. Look at any card in the Envelope lane or the Parcel lane.
- Seen: the lane header says "`Cards only, under $50`" or "`$50 or more, or not all cards`". Then each of 166 Envelope cards says "`Cards only, and under $50.`". Each of 112 Parcel cards says "`Worth $50 or more, so tracking is required.`". That is 1,726 words. On a phone, the owner scrolls past 166 copies of one sentence before the Parcel lane starts.
- Shot: TXT-01, screenshot not kept.
- Direction: say the rule once, in the lane header. A card shows its order and its figures. If the reason for a card is not the lane rule, the card also shows that reason.
- Component: `app/src/OrdersShipStage.tsx` (`.shipping-says`)
- Annotation: no decision covers this. D61 (the shipping lane is three lanes) argues that the reason is important where two grounds reach one lane. The proposal keeps the reason on those rows (the 14 `non_card_signal` Parcel cards) and on every Needs-a-look card.

### TXT-02 Each shipping card also prints the machine reason code
- Severity: S2
- Screens: #/shipping
- Where: all
- Repro: open `#/shipping`. Look at the bottom right of any card.
- Seen: `cards_only`, `value_at_threshold`, `no_weight_data` and `non_card_signal` sit under a sentence that says the same thing in words. There are 331 codes. The code is the third statement of the lane rule on the card.
- Shot: TXT-02, screenshot not kept.
- Direction: delete the code from the card.
- Component: `app/src/OrdersShipStage.tsx` (`.shipping-reason`)
- Annotation: violates D196 (no mechanism on screen). The CLAUDE.md Register rule keeps the machine string for hover and the run log only. The mechanized row cannot see it, because the code is data and not a JSX literal. prior: ux-2026-09-20/review.md (the same pattern, a reason code next to its own translation, on #/review).

### TXT-03 "Inferred" and "Certain" as a word on each card
- Severity: S3
- Screens: #/shipping
- Where: all
- Repro: open `#/shipping`.
- Seen: 292 cards show the word "`Inferred`" or "`Certain`" at the top right. Judgement call: the fact is important, but it is a two-state flag, and an icon can show it.
- Shot: TXT-03, screenshot not kept.
- Direction: a two-state icon with a tooltip. The word goes in the lane header or a legend.
- Component: `app/src/OrdersShipStage.tsx` (`.shipping-quality`)
- Annotation: caused by D61 (the shipping lane is three lanes). D61 calls `Routing.certain` the split that matters. The proposal keeps the fact and changes only its form.

### TXT-04 The same "0.0700 oz/item" value on 187 cards
- Severity: S3
- Screens: #/shipping
- Where: all
- Repro: open `#/shipping`. Read the Envelope lane.
- Seen: 187 cards show the same chip, "`0.0700 oz/item`". A value that is the same on every card tells the owner nothing about the card. Judgement call: where the value differs (44 cards show "`2.5000 oz/item`"), it is evidence.
- Shot: TXT-04, screenshot not kept.
- Direction: if the weight per item is the plain-card weight, do not show it.
- Component: `app/src/OrdersShipStage.tsx` (`.shipping-figure`)
- Annotation: caused by D61 (the shipping lane is three lanes). D61 infers the lane from weight per item, so the figure is evidence. It is evidence only where it is not the plain-card constant.

### TXT-05 The shipping header says each count twice
- Severity: S4
- Screens: #/shipping
- Where: 1440 and 820. The lede is hidden at 390.
- Repro: open `#/shipping`.
- Seen: the lede "`TCGplayer's shipping export, sorted into three lanes.`" describes the three lanes below it. "`126 orders in the parcel lane are in this file.`" is above the button "`Download · 126 orders`", near a lane that says 126. The tab and the export card both say "`331 orders`".
- Shot: TXT-05, screenshot not kept.
- Direction: one statement for each count. Delete the lede and the parcel sentence. Make the memory note "kept 30 min".
- Component: `app/src/OrdersShipStage.tsx`
- Annotation: no decision covers this.

### TXT-06 Pricing prints a four-term legend under the title
- Severity: S3
- Screens: #/pricing
- Where: all. It takes two lines at 390.
- Repro: open `#/pricing`.
- Seen: a 21-word glossary is always on the screen: "`typed = you set a price. held = held back on purpose. on the rule = following the standing rule. cheap = under the cut-off.`" A person reads it once. The row states it explains are already plain words.
- Shot: TXT-06, screenshot not kept.
- Direction: delete it. If a state needs an explanation, give it in the tooltip of that pill.
- Component: `app/src/Pricing.tsx` (`.pricing-scope-legend`)
- Annotation: caused by D208 (one verdict on pricing), in its amendment "the cut-off strip's four words got a visible legend". That legend glossed a `typed`/`held`/`on the rule`/`cheap` breakdown in the header. The header now reads "22 of 22 decided · 8 nothing to add", so the four words it explains are not beside it. The premise is gone (seen in the shot). The outcome it protected (a touch user can read the four states) is kept if each row pill carries its own plain word, as it does now. Proposal: delete the legend. The owner decides.

### TXT-07 "Near Mint" on every pricing row
- Severity: S3
- Screens: #/pricing
- Where: all
- Repro: open `#/pricing`. Read the grey line under any card name.
- Seen: all 30 rows say "`Near Mint`" or "`Near Mint Foil`". No row differs, so the words give no information. They also move the set and the number to the right.
- Shot: TXT-07, screenshot not kept.
- Direction: if the store has only one condition, do not show it. Keep "Foil".
- Component: `app/src/Pricing.tsx` (`.pricing-cond`)
- Annotation: caused by D137 (the catalog is Near Mint by rule). Every row is Near Mint by rule, so the label cannot differ between rows.

### TXT-08 "Typed" and "of 1" under the fields on every row
- Severity: S3
- Screens: #/pricing
- Where: all
- Repro: open `#/pricing`.
- Seen: 21 rows say "`Typed`" under the price field, and the field already shows a green check. 22 rows say "`of 1`" under a quantity of 1. The exceptions ("`Holding`", "`On the rule`", "`At the $0.49 cut-off`") are hard to find among them. "of 1" is a judgement call, because it tells the quantity from the copy count.
- Shot: TXT-08, screenshot not kept.
- Direction: show only a state that is not the default. If N equals the quantity, do not show "of N".
- Component: `app/src/Pricing.tsx` (`.pricing-state`, `.pricing-qty-of`)
- Annotation: no decision covers this.

### TXT-09 The cut-off is stated five ways
- Severity: S3
- Screens: #/pricing
- Where: all
- Repro: open `#/pricing`. Scroll to "Under the cut-off".
- Seen: the policy card shows "`$0.49`" with the caption "`the line, and what everything under it lists at`" and "`15 under · 15 above`". The section headers say "`15 SKUs`" each. The lower section adds "`Market below $0.49, so these go out at $0.49 — unless you type a price on the row.`" and a chip "`$0.49 the store's cut-off`". Five rows say "`At the $0.49 cut-off`".
- Shot: TXT-09, screenshot not kept.
- Direction: the figure once, in the policy card. The sections give the counts. The rows say "Cut-off".
- Component: `app/src/Pricing.tsx` (`.pricing-cheap-says`, the section header)
- Annotation: no decision covers this. D99 (the cut-off is a figure the operator sets) makes the figure important. It does not ask for the figure five times.

### TXT-10 The "Ready to write" panel repeats its heading and the page header
- Severity: S3
- Screens: #/pricing
- Where: all
- Repro: open `#/pricing`.
- Seen: "`Ready to write`" has a green check, and then "`Pricing is answered.`" follows. "`Scope 1 run · 1 box`" and "`Nothing to add 8 SKUs`" repeat the header line. "`Box 3 · RB Epics`" is shown three times above the fold. "`Emit can still refuse.`" is a warning with no reason and no action (judgement call).
- Shot: TXT-10, screenshot not kept.
- Direction: the heading, the not-listed counts as links, and one line, "21 rows, 21 copies".
- Component: `app/src/Pricing.tsx` (`.pricing-verdict-says`, the verdict `dl`)
- Annotation: caused by D208 (one verdict on pricing). D208 Ruling A kept `.pricing-verdict-says` as the one statement of the figures. The figures now sit on their own lines, so the sentence says only what the heading says. This is D208's own "two accounts" defect, one level down.

### TXT-11 The pricing write bar uses phrases for its controls
- Severity: S4
- Screens: #/pricing
- Where: 1440 and 820. At 390 the bar already says "split in two".
- Repro: open `#/pricing`. Look at the bar at the bottom.
- Seen: "`split it in two, either side of the cut-off`", "`hold to [no cap] live per card`", and a shortcut row that is always on: "`next M L S D snap H hold T history P photo U undo`".
- Shot: TXT-11, screenshot not kept.
- Direction: "Split at cut-off" and "Cap". The shortcut row goes in the `?` sheet (judgement call: it helps in the first hour at the keyboard).
- Component: `app/src/Pricing.tsx` (`.pricing-ship-cap`)
- Annotation: caused by D208 (one verdict on pricing). D208 left the bar as "the press and its two controls". The shortcut row was added after, and no decision covers it.

### TXT-12 "no sales" on each row after Load trends
- Severity: S4
- Screens: #/pricing
- Where: all
- Repro: open `#/pricing`. Press "Load trends".
- Seen: 22 rows get the words "`no sales`". An empty trend is an absence, and a dash shows an absence.
- Shot: TXT-12, screenshot not kept.
- Direction: "—".
- Component: `app/src/PriceTrend.tsx`
- Annotation: no decision covers this.

### TXT-13 The Mark-down sheet has 92 words before its first field
- Severity: S3
- Screens: #/pricing
- Where: all
- Repro: open `#/pricing`. Press "Mark down stale".
- Seen: an intro that repeats the title, a bold reassurance, and a 52-word grey note about how the listing age is dated. The note tells the owner to "`Run reconcile --live`". Then "`or drop a My Pricing export below.`" is above a drop zone that says the same.
- Shot: TXT-13, screenshot not kept.
- Direction: the title, one line ("Edits live listings. Deletes nothing."), then the form. The age note goes behind an ⓘ.
- Component: `app/src/Markdown.tsx`
- Annotation: caused by D100 (the age is a proxy that says so). D100 puts the proxy "on the screen in its own paragraph" and asserts it in a browser spec. The outcome D100 protects (nobody reads the age as real) needs one sentence, not 52 words. The "Run reconcile --live" sentence also violates D196 (no mechanism on screen): it names a shell command.

### TXT-14 The Clear-typed sheet explains itself three times
- Severity: S4
- Screens: #/pricing
- Where: all
- Repro: open `#/pricing`. Press "Clear typed".
- Seen: an 18-word intro, then "`Nothing expires on its own — an answer stands until you clear it.`", then a 19-word footer about how undo works.
- Shot: TXT-14, screenshot not kept.
- Direction: "Nothing at TCGplayer changes." and "You can undo this."
- Component: `app/src/ClearPrices.tsx`
- Annotation: caused by D168 (a typed price is cleared by a press, never by an expiry). The sentence restates D168's rule to the owner. D168 asks for a scoped, counted and reversible press, and the sheet has all three without the sentence.

### TXT-15 The Hold popover gives a caption to its own chip
- Severity: S4
- Screens: #/pricing
- Where: all
- Repro: open `#/pricing`. Press the lock icon on the first row.
- Seen: the selected chip says "`Bullish`", and the line below it says "`Bullish — waiting for the price to move`". A 24-word footer explains that a hold stays after the run.
- Shot: TXT-15, screenshot not kept.
- Direction: delete the caption. Make the footer "Stays out of every import until you release it."
- Component: `app/src/Pricing.tsx` (the hold popover)
- Annotation: no decision covers this. D49 (a card can be held back on purpose) and D168 give a hold a reason. They do not ask for a caption under the chosen reason.

### TXT-16 The Runs lede lists the four steps
- Severity: S4
- Screens: #/runs
- Where: 1440 and 820
- Repro: open `#/runs`.
- Seen: "`Identify, join, emit and reconcile a box. Identify is the only step that spends money.`" The first sentence lists steps that the run page shows. The second sentence is the one fact to keep.
- Shot: TXT-16, screenshot not kept.
- Direction: "Only Identify costs money." Or a cost chip on the Identify button, and no lede.
- Component: `app/src/Runs.tsx`
- Annotation: caused by D33 (one route can spend). The money fact comes from D33, and the proposal keeps it.

### TXT-17 The empty Runs panel explains the list next to it
- Severity: S4
- Screens: #/runs
- Where: all
- Repro: open `#/runs`.
- Seen: "`Pick a run`", then "`Join, emit and reconcile act on the run you pick from the list.`". The list panel has the title "`Runs`" under the H1 "`Runs`".
- Shot: TXT-17, screenshot not kept.
- Direction: "Pick a run" alone. Delete the panel title and keep its count.
- Component: `app/src/Runs.tsx`
- Annotation: no decision covers this.

### TXT-18 A 31-word tip about a rare mistake is on every run
- Severity: S3
- Screens: #/runs
- Where: all
- Repro: open `#/runs`. Pick "demo-box3".
- Seen: "`Queued a whole stack under the wrong rarity? Fix it on Inventory → Manage box → Rarity, then press Identify and Join again here — correcting the box alone changes nothing. It costs nothing.`" It is between the stats and the steps on every run.
- Shot: TXT-18, screenshot not kept.
- Direction: remove it from the run page. Show it at the moment it applies: next to the rarity control, or after a rarity change.
- Component: `app/src/RunPanel.tsx`
- Annotation: no decision covers this.

### TXT-19 The run page shows its steps twice and repeats the stats
- Severity: S3
- Screens: #/runs
- Where: all
- Repro: open `#/runs`. Pick "demo-box3".
- Seen: a step strip, "`Identify · Join · Emit · Reconcile`", and below it the same four steps as rows. The Join row says "`30 SKUs, 0 to review and 0 parked`" under a stat row that gives 30, 30, 0 and 0. Three rows say "`Free · re-runnable`".
- Shot: TXT-19, screenshot not kept.
- Direction: one list of steps. Delete the Join subtitle. Write "Free".
- Component: `app/src/RunPanel.tsx`
- Annotation: no decision covers this.

### TXT-20 The Emit step says "Pricing" five times
- Severity: S3
- Screens: #/runs
- Where: all
- Repro: open `#/runs`. Pick "demo-box3". The Emit row is open.
- Seen: the subtitle "`Price the SKUs and write the import files — on Pricing`", a 27-word paragraph that says the same, the button "`Price and emit this run`", and a 22-word note that the rule is set on Pricing. The stat row above also has "`Price 30 SKUs →`".
- Shot: TXT-20, screenshot not kept.
- Direction: the subtitle and the button only.
- Component: `app/src/RunPanel.tsx`
- Annotation: caused by D86 (one pricing file for the store). The word "now" in "one answer for the whole store now" is a migration note from D86, and it has outlived the migration (unmeasured: when the last run-scoped rule was used).

### TXT-21 An open step explains what the step does
- Severity: S4
- Screens: #/runs
- Where: all
- Repro: open `#/runs`. Pick "demo-box3". Open Join, then Reconcile, then Identify.
- Seen: Join shows "`Resolves each card against a TCGplayer export and writes the queues and the pricing questions.`" and a 23-word preview note. Reconcile shows 24 words of TCGplayer procedure above a button that names the file. Identify shows "`Nothing was captured here — this run was started from a terminal.`" (judgement call).
- Shot: TXT-21, screenshot not kept.
- Direction: one short line for each step, or none. "Preview is free and writes nothing."
- Component: `app/src/RunPanel.tsx`
- Annotation: no decision covers this.

### TXT-22 Identify step 1 has 84 words of explanation
- Severity: S3
- Screens: #/runs
- Where: all
- Repro: open `#/runs`. Press "Identify cards".
- Seen: a 17-word description of the selected tab, and a 45-word paragraph about the cache. The paragraph gives a fixed store figure ("`every one of 2,535 cards was already answered`"). A 16-word note explains why Section needs a drawer. The footer repeats the tab. The Cost step exists to show the real figure.
- Shot: TXT-22, screenshot not kept.
- Direction: one line for each tab. Delete the cache paragraph. Disable Section with "Pick one drawer first."
- Component: `app/src/RunsComposer.tsx`
- Annotation: caused by D180 (a press names the cards it is over). D180 measured "2,535 cards and 0 to send" on the owner's store. The screen prints that measurement as a fixed sentence, and in the demo the store is not 2,535 cards. The figure is stale on any store but the one it was measured on.

### TXT-23 Identify step 2 explains the press model
- Severity: S4
- Screens: #/runs
- Where: all
- Repro: open `#/runs`. Press "Identify cards", then "Continue to the reading".
- Seen: "`Crops to the card, sent at 1200px: $0.62 on box 2 and sharpest on the number. Photographs on disk are never touched.`" and "`This reading reaches every card in the press. Two drawers that want two readings are two presses.`". "`Every card waiting to be identified`" is in the header and in the footer.
- Shot: TXT-23, screenshot not kept.
- Direction: "Crops to the card, 1200px." Delete the press-model sentence. Say the scope once.
- Component: `app/src/RunsComposer.tsx`
- Annotation: no decision covers this.

### TXT-24 The Reconcile sheet starts with a 44-word sentence
- Severity: S3
- Screens: #/runs
- Where: all
- Repro: open `#/runs`. Press "Reconcile the store".
- Seen: a 44-word description of the two directions of the compare. Then "`Every LIVE figure in the store is only as current as the last time this ran.`", with no date. Then "`or drop a My Pricing export below.`" above a drop zone.
- Shot: TXT-24, screenshot not kept.
- Direction: one sentence about what it does, a real "Last run" date in place of the warning, the button, and the drop zone.
- Component: `app/src/LiveReconcile.tsx`
- Annotation: caused by D87 (the reconcile is store-wide). D87 makes the reconcile report both directions. It does not ask for the sheet to describe both before the press.

### TXT-25 The Home "Behind that" line repeats the stage strip
- Severity: S3
- Screens: #/
- Where: all
- Repro: open `#/`.
- Seen: "`Behind that: 27 copies to pull · 9 to review · 2 runs to price`" is 200px above a strip of six tiles. The tiles show Review 9, Pricing 2 and Orders "`27 copies to pull`". The same three numbers are above the fold two times at 1440.
- Shot: TXT-25, screenshot not kept.
- Direction: keep one. If the rank order is important, rank the strip and delete the line.
- Component: `app/src/Home.tsx` (`.home-standing-behind`)
- Annotation: violates D121 (the front page says what is owed). D121 rejected six lines because their figure "is drawn again by the six-stage spine 24px below", and called duplicated figures "furniture". The "Behind that" line repeats three spine figures.

### TXT-26 The Home verdict says "cannot" twice
- Severity: S4
- Screens: #/
- Where: all
- Repro: open `#/`.
- Seen: "`Cannot be filled — 6 copies for 7 open orders cannot be found.`" The title and the sentence make the same claim.
- Shot: TXT-26, screenshot not kept.
- Direction: "Cannot be filled — 6 copies missing for 7 orders."
- Component: `app/src/Home.tsx`
- Annotation: no decision covers this.

### TXT-27 Home stage notes repeat their tile label
- Severity: S4
- Screens: #/
- Where: all
- Repro: open `#/`. Read the six stage tiles.
- Seen: RUNS "`runs on file`", REVIEW "`to answer`", PRICING "`runs to price`", ORDERS "`27 copies to pull and 6 …`" (truncated at 1440), SHIPPING "`no export read yet`" under a dash.
- Shot: TXT-27, screenshot not kept.
- Direction: a note only where it adds a unit or a second number, for example "27 to pull".
- Component: `app/src/Home.tsx` (`.home-stage-note`)
- Annotation: no decision covers this.

### TXT-28 The Home greeting and date
- Severity: S4
- Screens: #/
- Where: all
- Repro: open `#/`.
- Seen: "`Wednesday, September 23`" and a 60px "`Good evening.`" are at the top of the screen. Judgement call: this is the voice of the brand, but it gives no information. At 390 it moves the "Start capturing" button lower.
- Shot: TXT-28, screenshot not kept.
- Direction: the owner decides. The ranked verdict can be the heading.
- Component: `app/src/Home.tsx`
- Annotation: no decision covers this. D121 (the front page says what is owed) kept the greeting above the ranked line.

### TXT-29 Capture says "the camera is not open" five times
- Severity: S3
- Screens: #/capture
- Where: all
- Repro: open `#/capture`.
- Seen: a "`Camera off`" pill. In the checklist, "`Open the camera.`" and an "`Open the camera`" button. In the viewfinder, "`The camera is not open`" and an "`Open the camera`" button. Under Rig, "`Camera`" "`Not open`".
- Shot: TXT-29, screenshot not kept.
- Direction: keep the viewfinder button and the Rig value. Delete the checklist line and the viewfinder heading.
- Component: `app/src/CaptureScreen.tsx` (`.capture-block-say`, `.capture-frame-title`)
- Annotation: no decision covers this.

### TXT-30 Capture says "no box" five times
- Severity: S3
- Screens: #/capture
- Where: all
- Repro: open `#/capture`.
- Seen: "`No box yet`" with "`Pick one, or type a new name`". "`Pick or name a box.`" with a "`Pick a box`" button. The Recent panel says "`Pick a box to start.`". The viewfinder footer says "`No box`".
- Shot: TXT-30, screenshot not kept.
- Direction: the Box field says it. Delete the checklist line and the Recent sentence. An empty Recent panel can be blank.
- Component: `app/src/CaptureScreen.tsx`
- Annotation: no decision covers this.

### TXT-31 "Nothing to clear." under a disabled button
- Severity: S4
- Screens: #/capture
- Where: all
- Repro: open `#/capture`. Scroll the left column to the end.
- Seen: a disabled "`Clear the setup`" button, and under it "`Nothing to clear.`".
- Shot: TXT-31, screenshot not kept.
- Direction: delete the sentence. The disabled state says it.
- Component: `app/src/CaptureScreen.tsx` (`.capture-opennote`)
- Annotation: no decision covers this.

### TXT-32 The Capture box picker gives each row the label "next index"
- Severity: S4
- Screens: #/capture
- Where: all
- Repro: open `#/capture`. Press the Box field.
- Seen: "`next index 43`", "`next index 29`" and "`next index 19`" on the rows. "`Next index 43`" in the field. "`4 boxes`" above four rows. "`Enter takes the top row. Anything new is created by name.`" (judgement call).
- Shot: TXT-32, screenshot not kept.
- Direction: "#43" on each row. Delete the count.
- Component: `app/src/CaptureScreen.tsx`
- Annotation: no decision covers this row. D41 (the address is a rank) removed `next index` from the Inventory box row, because it is not a statistic. D153 (the restore asks which drawer) records the owner calling numbers in this picker "waste of space".

### TXT-33 Capture sheets give a caption to their own row
- Severity: S4
- Screens: #/capture
- Where: all
- Repro: open `#/capture`. Press "Set hint". Then press "Tuning".
- Seen: "`Needed for this game`" is under a row that says "`Needed`". The empty Tuning panel has 13 words of instruction: "`Arm the motion trigger under Rig (T) and the machine's readout appears here.`"
- Shot: TXT-33, screenshot not kept.
- Direction: delete the caption. "Trigger is off."
- Component: `app/src/CaptureScreen.tsx`
- Annotation: no decision covers this.

### TXT-34 Keycaps on a touch phone
- Severity: S3
- Screens: #/, #/capture, #/revenue
- Where: 390, touch device
- Repro: open `#/capture` on a 390px touch device.
- Seen: 8 keycaps (B, H, R, F, G, V, O, T) next to the Capture rows, "`,O`" on the Home verdict, and "`/`" in the Sales search field. A phone has no keyboard for them. The count is measured, and I saw it on Home and Capture.
- Shot: TXT-34, screenshot not kept.
- Direction: hide keycaps on a coarse pointer. The kit sheet says the review keycaps already do this.
- Component: `app/src/CaptureScreen.tsx` (`.capture-k`), `app/src/Home.tsx`, `app/src/Revenue.tsx`
- Annotation: no decision covers this. The Kit's own Keycaps caption says keycaps are "Hidden on coarse pointers", and these are not.

### TXT-35 The Sales lede
- Severity: S4
- Screens: #/revenue
- Where: all
- Repro: open `#/revenue`.
- Seen: "`Your gross-revenue retrospective — what sold, for how much, by name. Gross only: no fees, no cost, no profit.`" It has 18 words. The fact to keep is "gross only".
- Shot: TXT-35, screenshot not kept.
- Direction: "Gross sales. No fees or costs."
- Component: `app/src/Revenue.tsx`
- Annotation: caused by D214 (a gross-revenue retrospective). D214 asks the lede to say "gross". The proposal keeps that word.

### TXT-36 Sales prints three sentences about zero
- Severity: S3
- Screens: #/revenue
- Where: all. It is worst at 390.
- Repro: open `#/revenue` at 390.
- Seen: "`So far, nothing is recorded for the period before this one.`", "`0 orders were canceled by the marketplace and left out.`", and a 27-word sentence that starts "`0 lines were marked refunded`". At 390 the first viewport holds the lede, the verdict and these three sentences. No product row is in it.
- Shot: TXT-36, screenshot not kept.
- Direction: if an exclusion count is 0, do not show it. If it is above 0, say it in five words.
- Component: `app/src/Revenue.tsx` (`.revenue-verdict-prior`, `.revenue-verdict-canceled`, `.revenue-verdict-refunded`)
- Annotation: caused by D225 (a sales truth). D225 rules that the screen "states BOTH counts, plainly", and it measured that the refund mechanism catches 0 on the owner's store. So the screen shows two zeros every day. The outcome D225 protects (the owner knows that refunds are excluded) is kept by one short line, or by the line only when the count is above 0. The owner decides.

### TXT-37 The year on every sale date
- Severity: S4
- Screens: #/revenue
- Where: all
- Repro: open `#/revenue`.
- Seen: every "Last sold" cell ends in "`, 2026`". The range is 6 months, all in 2026.
- Shot: TXT-37, screenshot not kept.
- Direction: if the full range is in one year, drop the year.
- Component: `app/src/Revenue.tsx`
- Annotation: no decision covers this.

### TXT-38 The Graveyard lede
- Severity: S4
- Screens: #/graveyard
- Where: all
- Repro: open `#/graveyard`.
- Seen: "`Every card that's left inventory — sold, retired, or moved. Read-only.`" The screen has no edit control, so "Read-only" says what the layout shows.
- Shot: TXT-38, screenshot not kept.
- Direction: "Sold, retired and moved cards."
- Component: `app/src/Graveyard.tsx`
- Annotation: caused by D134 (the graveyard is where the departed are read). The word "Read-only" is D134's rule printed as copy.

### TXT-39 The Codes lede and the Read-a-box sheet
- Severity: S4
- Screens: #/codes
- Where: all
- Repro: open `#/codes`. Press "Read a box".
- Seen: "`Read, tier, and hand off code cards.`" is under the title "`Codes`", next to a "`Read a box`" button. The sheet starts with "`Decodes every code-card photograph in the box. Free — the QR is the code.`"
- Shot: TXT-39, screenshot not kept.
- Direction: delete the lede. The sheet says "Free."
- Component: `app/src/Codes.tsx`
- Annotation: caused by D70 (the QR is the whole identification). "Free — the QR is the code" restates D70 to the owner.

### TXT-40 Product history says what its field is for three times
- Severity: S4
- Screens: #/product
- Where: all
- Repro: open `#/product`.
- Seen: a 14-word lede, a field "`TCGplayer SKU`" and its button, an empty title "`Enter a SKU to see its history.`", and a body "`This page is per product, and it never guesses which one you mean.`". 27 of the 40 words can go.
- Shot: TXT-40, screenshot not kept.
- Direction: the title, the field, the button, and the empty title alone.
- Component: `app/src/ProductHistory.tsx`
- Annotation: caused by D227 (a product price view, off-nav). The body sentence restates the design argument ("it never guesses") to the owner.

### TXT-41 The Fulfillment status sentence and browse sentence
- Severity: S4
- Screens: #/fulfillment
- Where: all
- Repro: open `#/fulfillment`.
- Seen: "`No orders are waiting for a card right now. You can still find any card by name.`" is above a field with the label "`Type the name of the card`". "`101 cards are in 4 boxes. Tap a box to see what is in it.`" is above four boxes that show their counts. Judgement call: this screen is for a person who needs plain words, so the owner can keep them.
- Shot: TXT-41, screenshot not kept.
- Direction: "No orders waiting." Delete the browse sentence.
- Component: `app/src/Fulfillment.tsx` (`.ff-today-none`, `.ff-browse-lede`)
- Annotation: caused by D5 (two personas). D5 says a Fulfiller screen must be self-evident, which argues for these sentences. This is why both rows are J.

### TXT-42 Inside Box 1, every row says "Box 1"
- Severity: S3
- Screens: #/fulfillment
- Where: all
- Repro: open `#/fulfillment`. Tap "Box 1".
- Seen: 35 rows say "`Box 1 · Section 1 · Card N`" in large type, inside a panel with the heading "`Box 1 · RB Origins`". Judgement call: a full address on each row helps the pull, but the box is already open in the hand.
- Shot: TXT-42, screenshot not kept.
- Direction: a "Section 1" header, then "Card 1", "Card 2" on the rows.
- Component: `app/src/Fulfillment.tsx`
- Annotation: violates D41 (the address is a rank, not a list). D155 (the section is the ruler) cites D41 as refusing `Box 2 · Section 1 · Card 14` as three equal parts where the first two are answered on screen. D5 (two personas) is the counter-argument for the Fulfiller.

### TXT-43 A departed card is in the pull list
- Severity: S3
- Screens: #/fulfillment
- Where: all
- Repro: open `#/fulfillment`. Tap "Box 1". Scroll to the second section.
- Seen: the row "`Ashe, Focused`" "`Box 1 · departed · B1 #19`" is among the cards to pull. The card is not in the box. Measured, not seen.
- Shot: TXT-43, screenshot not kept.
- Direction: do not show departed cards on the Fulfiller's screen.
- Component: `app/src/Fulfillment.tsx`
- Annotation: no decision covers this. D134 (the graveyard is where the departed are read) puts departed records on #/graveyard.

### TXT-44 The Kit prints a design log
- Severity: S3
- Screens: #/gallery
- Where: all
- Repro: open `#/gallery`.
- Seen: 2,422 words. Ten notes (436 words) are history, for example "`swept in section 11 at 16, 28, 32 and 44px`" and "`settled by forced choice over thirty-seven rounds (section 13)`". They name the repo paths `docs/specs/logo.md` and `scripts/build-mark.mjs`. The lede says "`Switch the theme in the nav to see both.`".
- Shot: TXT-44, screenshot not kept.
- Direction: one caption line for each specimen. The history goes in the spec that it cites.
- Component: `app/src/Gallery.tsx` (`.kit-spec-note`)
- Annotation: caused by D102 (the mark is an illustration, and the spec is its store of record). The notes copy the spec's sweep history onto the sheet. The repo paths also meet D196 (no mechanism on screen), if the Kit counts as an owner screen (unknown: D196 does not say).

### TXT-45 The shell footer prints a card count
- Severity: S4
- Screens: every owner route
- Where: 1440, in the sidebar
- Repro: open `#/`. Read the foot of the sidebar.
- Seen: "`Server online · 122 cards`". The same screen says "`100 on hand`", and the Fulfiller's screen says "`101 cards`". A third count in the chrome is one more number to compare.
- Shot: TXT-45, screenshot not kept.
- Direction: "Server online".
- Component: `app/src/App.tsx` (the sidebar foot)
- Annotation: no decision covers this. D207 (the foot learns from every request) governs the dot, not the count.

### TXT-46 Demo failures print the endpoint and a make command
- Severity: S4
- Screens: #/runs, #/revenue, #/product, #/graveyard, #/pricing
- Where: all, demo only
- Repro: open `#/runs`, press "Identify cards", then "Continue to the reading". Or open `#/revenue` and press "Compare to today's market".
- Seen: the Identify modal shows the same 36-word refusal twice, in a banner and in a side panel. Sales prints "`This demo's recording holds no answer for GET /pipeline/price-now?sku=…`" with 21 SKUs in the URL, and "`Rebuild it with make demo.`". This is not a product defect. It is how the demo shows its refusals.
- Shot: TXT-46, screenshot not kept.
- Direction: one short refusal for each screen: "Not in this demo."
- Component: `app/src/RunsComposer.tsx`, `app/src/Revenue.tsx`, the demo transport
- Annotation: violates D196 (no mechanism on screen): a route path and a `make` command. The demo spec is not read, so whether the demo transport is in the scope of D196 is unknown.

## Held-screen notes

Main state. Re-check after merge. Not graded.

- **#/review.** "`Box 1 · Section 3 · Card 13`" is shown twice: in the details list and in the position label. The missing-photo notice has 18 words: "`The entry has a photograph and nothing here can restore it. The card is still at its slot.`"
- **#/orders.** A count row, "`A run priced this card and no record carries the SKU`", has the note "`Not asked on this screen; always 0.`". A row that is always 0 on this screen does not need to be on it. Also "`Showing only the copies this order was offered — not every copy in the store.`" (14 words).
- **#/inventory.** The lede "`Walk any box card by card. Sell, retire or move a copy from here.`" (14 words) repeats the controls. The missing-photo sentence has 23 words and repeats the address next to it.

## What I could not check

- The owner's live store. The demo's shipping export has 331 orders. The live count, and so the real size of TXT-01 to TXT-04, is unknown.
- Toasts and receipts. I did not press a sale or a price edit that makes one outside the held screens. Their word count is unknown.
- States that the demo refuses (identify cost, emit, fetch, fill pick locations, code read, graveyard). I graded only how the refusal is shown. The success states are unknown.
- `#/product` with data. The demo has no recording for any SKU, so the filled screen is unknown. I found no link from another screen to `#/product`. I opened it by URL only.
- `#/graveyard` with data. The demo returns an error, so the list state is unknown.
- 820 and dark. I took shots of every route (`*-820-*.png`, `*-dark*.png`). The word counts at 820 match 1440 less the sidebar, and the theme does not change the text. I did not read every dark shot.
