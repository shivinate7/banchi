# Banchi UX review 2026-09-23: consolidated

Seven blind lenses (coherence, loop, visual, interaction, copy, access, density) over the published demo, built from main at PR #454/#455. The visual lens also made a read-only look at the owner's live app at 1440. Brief: `BRIEF.md`. Lens files: `coherence.md`, `loop.md`, `visual.md`, `interaction.md`, `copy.md`, `access.md`, `density.md`. No screenshot was kept in this record. The live screenshots held real store data, and no finding links one.

**164 distinct findings** from 250 lens findings: 2 S1, 35 S2, 89 S3, 38 S4.

## Grade matrix

Routes from `app/src/App.tsx` `ROUTES` (14). HELD = another branch is changing the screen. 'not walked' = off the loop lens's path. The median ignores HELD and 'not walked'; an even count between two grades shows both.

| Route | Coherence | Loop | Visual | Interaction | Copy | Access | Density | Median |
|---|---|---|---|---|---|---|---|---|
| `#/` Home | C | C | C | B | C | B | B | **C** |
| `#/capture` Capture | C | C | B | D | C | C | C | **C** |
| `#/runs` Runs | C | C | B | B | D | B | C | **C** |
| `#/review` Review | HELD | HELD | HELD | HELD | HELD | HELD | HELD | **HELD** |
| `#/pricing` Pricing | D | F | F | F | F | D | D | **F** |
| `#/orders` Orders | HELD | HELD | HELD | HELD | HELD | HELD | HELD | **HELD** |
| `#/shipping` Shipping | C | C | C | C | D | C | F | **C** |
| `#/revenue` Sales | C | C | C | B | C | D | C | **C** |
| `#/inventory` Inventory | HELD | HELD | HELD | HELD | HELD | HELD | HELD | **HELD** |
| `#/graveyard` Graveyard | C | F | D | C | C | B | B | **C** |
| `#/codes` Codes | B | not walked | B | C | B | B | B | **B** |
| `#/fulfillment` Cards to pull | D | D | F | B | D | B | B | **D** |
| `#/gallery` Kit | B | not walked | B | B | B | C | D | **B** |
| `#/product` Product history | D | D | C | D | D | C | C | **D** |

Cards to pull: visual moved its grade to F after the live check (VIS-34); interaction, access and density graded B on looks alone, before the S1 was confirmed. Pricing's F median rests on the price-field clip (UX-002), which four lenses graded F.

## Themes

The owner's complaint is that features 'are not syncing'. These ten themes are the ways they fail to sync.

### T1 Counts that disagree
Home, the shell, Cards to pull, Runs, Pricing and Sales each count the store, and no label says what each figure counts. So correct figures read as disagreement, and one of them (Cards to pull) is simply false. This is the most direct form of 'not syncing'.

Findings: UX-001, UX-004, UX-006, UX-019, UX-023, UX-074, UX-105, UX-126, UX-139

### T2 One concept, several names
Box is also drawer and shelf. The write step is Emit and Write the import file. The floor has five names. A card's place is index, #, Card and slot. An order has three ids. Each feature named its concept in its own decision, and no glossary joins them.

Findings: UX-008, UX-012, UX-018, UX-029, UX-044, UX-045, UX-051, UX-060, UX-079, UX-080, UX-081, UX-082, UX-102, UX-103, UX-104, UX-106, UX-108, UX-110, UX-149, UX-161

### T3 Dead ends and dropped hand-offs
Features were added as routes and sheets, but the doors between them were not built. Product history has no inbound link. A card or order on one screen does not open it on another. Home's links and Capture's hand-off to Runs drop the scope that their label names.

Findings: UX-003, UX-011, UX-021, UX-022, UX-027, UX-028, UX-030, UX-031, UX-032, UX-050, UX-077, UX-078

### T4 Machine words on the owner's screen
Reason codes, error codes, request paths, a shell command, `make demo`, pipeline verbs (join, emit, parked) and fixed measurements reach the owner. D196's guard reads JSX literals only, so data-driven and server text passes it.

Findings: UX-005, UX-010, UX-013, UX-017, UX-020, UX-024, UX-038, UX-049, UX-052, UX-130

### T5 Too many words
Shipping draws 4,942 words for three counts and a download. Pricing, Runs sheets, Sales and Capture repeat the same fact three to five times, and several sheets restate a decision's argument as copy. The copy-budget ceilings were pinned on fixture states that do not draw this text.

Findings: UX-015, UX-053, UX-054, UX-061, UX-062, UX-063, UX-064, UX-065, UX-083, UX-084, UX-085, UX-088, UX-089, UX-119, UX-120, UX-121, UX-122, UX-123, UX-124, UX-131, UX-132, UX-140, UX-141, UX-142, UX-150, UX-151, UX-152, UX-153, UX-154, UX-160, UX-162, UX-163

### T6 Each screen builds its own parts
Money has four faces, errors three shapes, overlays four designs, reload five forms, loading four forms and search three forms. Headers, verdict lines, card rows and the missing-photo state differ per screen. The kit does not hold a sheet, an error or a card-row primitive, so each feature made its own.

Findings: UX-002, UX-041, UX-042, UX-043, UX-056, UX-057, UX-066, UX-067, UX-068, UX-075, UX-076, UX-086, UX-087, UX-098, UX-099, UX-101, UX-109, UX-111, UX-112, UX-115, UX-116, UX-117, UX-118, UX-127, UX-129, UX-133, UX-134, UX-136, UX-137, UX-144, UX-145, UX-148, UX-157, UX-158, UX-159

### T7 The phone is a second-class screen
Pricing's sticky bar takes a third of the phone. The tab bar lights no tab on eight screens. The drawer hides two screens and is not modal. Keycaps show on a touch screen. Capture's main press and Shipping's decision lane sit below long scrolls.

Findings: UX-007, UX-009, UX-016, UX-033, UX-035, UX-037, UX-039, UX-040, UX-046, UX-055, UX-059, UX-072, UX-097, UX-107, UX-128, UX-143, UX-146, UX-147, UX-155, UX-156

### T8 The screen moves under the hand
Refusals, notices, inline fields, view toggles and releases push the control that the owner presses next. D118 exists for this, but its specs guard Inventory only.

Findings: UX-025, UX-058, UX-069, UX-070, UX-071, UX-093, UX-135

### T9 Built on fixtures, broken at real density
The live look found layouts that work on demo data and break on the owner's store: Sales at 562 rows with full catalog names, Graveyard wider than the page, a hidden Runs scroll. The Cards to pull S1 is the same class: a wire field that the fixture never exercised.

Findings: UX-034, UX-036, UX-113, UX-114

### T10 Keyboard and contrast floors hold on some screens only
Focus traps, focus return, a skip link, field edges, small-text contrast and headings pass on some screens and fail on others. Each floor was set for one screen and not carried to the next.

Findings: UX-014, UX-026, UX-047, UX-048, UX-073, UX-090, UX-091, UX-092, UX-094, UX-095, UX-096, UX-100, UX-125, UX-138, UX-164

## Ranked findings

Order: severity, then the number of lenses that found it, then how often the owner meets the screen. UX-001 is pinned first on the coordinator's word (confirmed live). Severity is the highest any lens gave; a note says where lenses disagree.

### S1

#### UX-001 Cards to pull says no orders wait while open orders owe copies
- Severity: S1 (Lenses disagree on the route grade: visual F after the live check, coherence/loop/copy D, interaction/access/density B on looks alone.)
- Screens: `#/fulfillment`, `#/`, `#/orders`
- Sources: COH-01, LOOP-02, VIS-34, COPY-03 (4 lenses: coherence, loop, visual, copy)
- Theme: T1 Counts that disagree
- Defect: The Fulfiller's screen shows a green 'No orders are waiting for a card right now' while Home and Orders count 27 copies owed on 7 open orders (demo), and CONFIRMED live: 71 open orders, 129 open lines and 216 copies wanted.
- Direction: Compute 'what waits to be pulled' once and draw it on Home, Orders and Cards to pull. If the screen cannot place a copy, it says how many. It never shows a green 'nothing waits' while orders are open.
- Shot: UX-001, screenshot not kept.
- Decision: Likely cause (VIS-34, from source and wire counts, not confirmed by a fix): `Fulfillment.tsx` `orderGroups` builds cards only from `GET /orders` picks, which carry 0 picks on the demo and on the live store; Orders reads `POST /orders/picks`. Caused by D212 (every copy is fungible, so no order claims one): D212 measured `GET /orders` offering 84 picks, and that premise no longer holds. Violates D5 (two personas) (LOOP-02). COH-01 and COPY-03: no decision covers the sentence. Which change moved the picks is unmeasured. prior: ux-2026-09-20/fulfillment.md saw this empty state on a store with zero open orders, where it was true.

#### UX-002 Pricing 'Lists at' field shows only the first digit of the price at desk widths
- Severity: S1
- Screens: `#/pricing`
- Sources: COH-02, LOOP-01, VIS-01, INT-01, COPY-01 (5 lenses: coherence, loop, visual, interaction, copy)
- Theme: T6 Each screen builds its own parts
- Defect: At 1100-1920 px the price input is 8.5-9 px wide, so 13.11 reads '$ 1', 2.52 '$ 2' and 0.49 '$ 0', in both themes and while focused. The same field is 65 px and correct at 820 and 159 px at 390.
- Direction: The listing price is legible in full, to the cent, at every width, before and during an edit. Size the price column from its widest value, not from what is left over.
- Shot: UX-002, screenshot not kept.
- Decision: No decision covers this (all five lenses). Likely cause (VIS-01, measured, not confirmed): the row has 5 children and the grid has 8 tracks (`36 444 56 68 68 68 132 68` under `data-trends=off`), so the price lands in a 68 px track beside a 132 px one; field rules date from commit 379ce843 (2026-09-04). D221 (money stays mono) governs the face, not the width. prior: not in ux-2026-09-20; that review measured 1440 and 1280 on the live store and did not log it, so the defect may be newer (unmeasured).

### S2

#### UX-003 Product history has no door: no link, no palette entry, no nav row
- Severity: S2
- Screens: `#/product`, `#/revenue`, `#/pricing`, shell palette
- Sources: COH-03, LOOP-12 (part), INT-30, COPY-25, ACC-06, VIS-29 (part) (6 lenses: coherence, loop, interaction, copy, access, visual)
- Theme: T3 Dead ends and dropped hand-offs
- Defect: No anchor on any of the 14 routes points at `#/product`, the palette answers 'Nothing matches "product"', and the page asks for a TCGplayer SKU that the owner sees only in small type on the Pricing history sheet and the held Inventory card.
- Direction: Every place that names a card or product (Sales row, Pricing row, history sheet, Inventory card) opens its history in one press, and the palette finds the page by name.
- Shot: UX-003, screenshot not kept.
- Decision: Caused by D227 (a product price view is a route, not a lens): its premise 'reachable through its own control' does not hold, and the Sales link it deferred 'the day that file is free' was never built after that branch merged (COH-03, INT-30, COPY-25, ACC-06, VIS-29, LOOP-12). The palette drops it because D95 (the shell is a rail, a palette and a reference sheet) builds 'Go to' from `nav` routes only. Violates the CLAUDE.md hard rule that a route is not a feature until a screen reaches it.

#### UX-004 Every screen gives a different number of cards
- Severity: S2 (COH-05 and COPY-02 S2; LOOP-32 and VIS-26 S3; TXT-45 S4.)
- Screens: shell, `#/`, `#/fulfillment`, `#/runs`, `#/codes`, `#/inventory (held)`
- Sources: COH-05, COPY-02, LOOP-32, VIS-26, TXT-45 (5 lenses: coherence, copy, loop, visual, density)
- Theme: T1 Counts that disagree
- Defect: Sidebar '122 cards', Home '100 on hand' and '1,573 photographed', Cards to pull '101 cards are in 4 boxes', Box 1 is 34 on Home and 35 on Cards to pull, Runs '(30 cards)' against 26 on hand, Identify '2,535 cards'. Live: sidebar 3,510 against Cards to pull 2,633. No label says what each counts.
- Direction: One word per count ('on hand', 'photographed', 'ever captured'), used the same way on every screen. The two 'in the boxes' figures agree. The shell foot drops its count or names it.
- Shot: UX-004, screenshot not kept.
- Decision: No decision covers this. D198 (Home's Review tile reads the same total as #/review) is the precedent for one figure per concept, applied to one tile only. D207 (the foot learns from every request) governs the dot, not the count.

#### UX-005 Shipping prints raw reason codes on every card
- Severity: S2 (COPY-07 and TXT-02 S2; COH-22, LOOP-23 and VIS-06 S3.)
- Screens: `#/shipping`
- Sources: COH-22, LOOP-23, VIS-06, COPY-07, TXT-02 (5 lenses: coherence, loop, visual, copy, density)
- Theme: T4 Machine words on the owner's screen
- Defect: Each of 331 cards ends in a mono `cards_only`, `value_at_threshold`, `no_weight_data` or `non_card_signal`, under a sentence that already says the same thing.
- Direction: Reasons in words only, as Review now does. The code is not on the card.
- Shot: UX-005, screenshot not kept.
- Decision: Violates D196 (no mechanism on screen) (COH-22, TXT-02); the D196 row cannot see it because the code is data, not a JSX literal. Caused by D61 (three shipping lanes) per COPY-07: D61 keeps five reasons so a screen can show which answers to check, and the sentence already does that. prior: ux-2026-09-20/review.md and TASTE-CALLS ('The reason code: chip, tooltip, gone') removed the same pattern from Review; the fix did not reach Shipping.

#### UX-006 'Needs pricing' shows on runs that Pricing calls answered
- Severity: S2 (COH-06 and COPY-05 S2; LOOP-20 S3.)
- Screens: `#/`, `#/runs`, `#/pricing`
- Sources: COH-06, COPY-05, LOOP-20 (3 lenses: coherence, copy, loop)
- Theme: T1 Counts that disagree
- Defect: Runs and Home say 'Needs pricing' and '2 runs to price', while Pricing says '22 of 22 decided. Pricing is answered. Ready to write' for the same run. The run waits on the write, not on a price.
- Direction: The run status names the step it really waits on, in Pricing's words ('Ready to write the file'), and Home's count agrees.
- Shot: UX-006, screenshot not kept.
- Decision: Caused by D156 (a run stays open until the last unsent copy has gone) (COH-06): the run stays open for the write and the chip still says 'pricing'. COPY-05 and LOOP-20: no decision covers the word. D198 is the precedent for one figure per concept.

#### UX-007 On a phone, Pricing's sticky write bar takes a third of the screen, and two rows fit per screen
- Severity: S2
- Screens: `#/pricing`
- Sources: LOOP-25, VIS-18, ACC-02 (3 lenses: loop, visual, access)
- Theme: T7 The phone is a second-class screen
- Defect: At 390 the write bar is 174-186 px and sticks above a 60-64 px tab bar under a 52 px top bar: 29-34% of 844 px (39% at 360) never scrolls. Rows are about 270 px, so 30 SKUs is about 15 screens.
- Direction: On a phone only the write action stays pinned, as one line that opens on a tap. Rows fit more per screen.
- Shot: UX-007, screenshot not kept.
- Decision: Caused by D208 (one verdict on Pricing) (ACC-02): its phone rule stacks the split checkbox, the cap field and the Write button full width and keeps them sticky; D208 argues the stack, not its cost in height. D99 (one press writes one spreadsheet) put the write on this bar (VIS-18). prior: none; 2026-09-20 was desktop only.

#### UX-008 An order has three names, and no Shipping or Sales row leads back to it
- Severity: S2
- Screens: `#/shipping`, `#/revenue`, `#/orders (held)`, `#/`
- Sources: COH-08, LOOP-10, COPY-45 (3 lenses: coherence, loop, copy)
- Theme: T2 One concept, several names
- Defect: Orders shows '09-03-26_00012' large and 'A2FFC195-256158-0…' small; Shipping and Sales show only 'A2FFC195-…' ids and never the buyer. 'Order' also counts 7 open on one tab and 331 in the export on the next, and Home calls the 331 'shipments in lanes'.
- Direction: One order label, led by the buyer, on every stage, and each row opens that order. A count says what it counts ('331 in the export', '7 open').
- Shot: UX-008, screenshot not kept.
- Decision: No decision covers the word or the link. D193 (the ledger holds the buyer's name) puts the name in the store; Shipping and Sales do not use it. D69 (a route each for orders and shipping) joins the two stages in code only.

#### UX-009 Sales name cell: its line clamp cuts names through the letters on a phone and floats its rule above the row rule
- Severity: S2 (ACC-03 S2; VIS-09 S3; COH-29 S4.)
- Screens: `#/revenue`
- Sources: ACC-03, VIS-09, COH-29 (3 lenses: access, visual, coherence)
- Theme: T7 The phone is a second-class screen
- Defect: The name `<td>` is 39 px in a 53 px row, so each row draws a stepped double rule at every width. At 390 and 360 the two-line clamp cuts the second line of every two-word name in half, the header scrolls away, and at 360 the Last sold year is cut at the edge.
- Direction: One rule per row. A full product name reads on a phone, and every column keeps its label while the table scrolls.
- Shot: UX-009, screenshot not kept.
- Decision: No decision covers this. The cause is one rule: `.revenue-table td:nth-child(2)`, a `-webkit-box` line clamp on a table cell (ACC-03). D217 (Sales becomes a tool) governs the table and argues only the header overflow at 390.

#### UX-010 The Identify sheet states a fixed '2,535 cards' and spends 84 words before the choice
- Severity: S2 (COPY-32 S2; LOOP-17 and TXT-22 S3.)
- Screens: `#/runs`
- Sources: COPY-32, LOOP-17, TXT-22 (3 lenses: copy, loop, density)
- Theme: T4 Machine words on the owner's screen
- Defect: 'On this store every one of 2,535 cards was already answered and cached' is typed into the copy (the demo holds 122). The sheet never says how many cards this press is over, although Pricing knows ('14 never identified').
- Direction: The sheet gives the live count of cards that this press will read, one line per tab, and no past measurement.
- Shot: UX-010, screenshot not kept.
- Decision: Caused by D180 (a press names the cards it is over) (TXT-22): D180 measured 2,535 on the owner's store and the screen prints that measurement as a fixed sentence. D185 (a published figure needs a reader) is the nearest principle (LOOP-17).

#### UX-011 Home names the capture box, and Capture opens with no box
- Severity: S2 (LOOP-05 S2; COH-25 S3.)
- Screens: `#/`, `#/capture`
- Sources: COH-25, LOOP-05 (2 lenses: coherence, loop)
- Theme: T3 Dead ends and dropped hand-offs
- Defect: Home's hero and Capture tile say 'Box 4, Mixed Singles'. 'Start capturing' opens Capture on 'No box yet. Pick one', so each cold start costs two presses and shows two answers to 'which box am I filling'.
- Direction: When Home names a box, Capture arrives with that box picked, or the tile says what it shows ('last box captured').
- Shot: UX-011, screenshot not kept.
- Decision: Caused by D142 (the setup outlives the browser, and lives on the device) (COH-25): Home reads the store, Capture reads the device, and nothing reconciles them. D153 (the restore asks which drawer) governs Capture's own memory, not Home's hand-off (LOOP-05).

#### UX-012 The place of a card is numbered three ways
- Severity: S2 (COPY-14 S2; COH-12 S3.)
- Screens: `#/fulfillment`, `#/capture`, `#/pricing (photo sheet)`, `#/inventory (held)`, `#/review (held)`
- Sources: COPY-14, COH-12 (2 lenses: copy, coherence)
- Theme: T2 One concept, several names
- Defect: Fulfillment and the Pricing photo sheet count within a section ('Box 1 · Section 3 · Card 1'), Inventory counts across the box ('#22'), Review prints 'CARD 13', a sold card is 'B1 #19', and Capture says 'next index'. The owner's 'card 22' is the Fulfiller's 'Card 1'.
- Direction: One word and one address form for where a card is, on every screen.
- Shot: UX-012, screenshot not kept.
- Decision: Caused by D58 (a number counts the cards in the box, the stored index never moves) (COH-12): Capture shows the stored index and Inventory the count. D41 (the address is a rank) governs how it is drawn; neither picks one scheme. 'index' on screen also violates D196 (no mechanism on screen).

#### UX-013 Cards to pull lists a sold card as 'departed B1 #19'
- Severity: S2 (COPY-15 S2; TXT-43 S3.)
- Screens: `#/fulfillment`
- Sources: COPY-15, TXT-43 (2 lenses: copy, density)
- Theme: T4 Machine words on the owner's screen
- Defect: Inside Box 1, 'Ashe, Focused' shows 'Box 1 · departed · B1 #19' among the cards to look through. The card is not in the box, and 'departed' and 'B1 #19' are record words.
- Direction: The Fulfiller's box list shows only cards that can be pulled. If a gone card must show, it says 'Sold'.
- Shot: UX-013, screenshot not kept.
- Decision: Caused by D68 (a departed label names the record) (COPY-15): D68 put the store key on the label for the owner, and the same label reaches the Fulfiller. D134 (the graveyard is where the departed are read) puts departed records on #/graveyard (TXT-43).

#### UX-014 The phone drawer is not modal, and focus stays behind it
- Severity: S2 (ACC-04 S2; INT-28 S4.)
- Screens: shell
- Sources: ACC-04, INT-28 (2 lenses: access, interaction)
- Theme: T10 Keyboard and contrast floors hold on some screens only
- Defect: The drawer ('Screens', `role=dialog`) has no `aria-modal`, the page behind is not inert, focus stays on the Menu button, and three Tabs land in the page. A backdrop tap sends focus to body. Every other sheet moves focus in and carries `aria-modal`.
- Direction: The drawer acts like the other sheets: focus moves in, stays in, and returns to its opener.
- Shot: UX-014, screenshot not kept.
- Decision: No decision covers this. D95 (the shell is a rail, a palette and a reference sheet) builds the drawer and says nothing about focus.

#### UX-015 Each Shipping card repeats its lane rule as a sentence (4,942 words on one screen)
- Severity: S2
- Screens: `#/shipping`
- Sources: COPY-08, TXT-01 (2 lenses: copy, density)
- Theme: T5 Too many words
- Defect: 'Cards only, and under $50.' prints on 166 cards and 'Worth $50 or more, so tracking is required.' on 112, under a lane header that says it once. The page holds 4,942 words, with fewer than 60 unique lines.
- Direction: Say the rule once in the lane header. A card shows a sentence only when its reason differs from its lane.
- Shot: UX-015, screenshot not kept.
- Decision: Caused by D194 (the visible word count may only go down) (COPY-08): its pinned ceiling for #/shipping is 133 words, measured on a fixture with no export loaded, so the check cannot see the loaded 4,939. D61 (three shipping lanes) argues the reason matters where two grounds reach one lane; the proposal keeps it there (TXT-01).

#### UX-016 On a phone, Shipping is a 37,000 px page and the lane that needs a decision is last
- Severity: S2 (LOOP-24 S2; ACC-19 S3.)
- Screens: `#/shipping`
- Sources: LOOP-24, ACC-19 (2 lenses: loop, access)
- Theme: T7 The phone is a second-class screen
- Defect: All 331 cards draw in open lanes. 'Needs a look' (39 rows), the one lane that asks the owner to decide, starts at y = 32,257 of 37,150 px. Nothing says that a lane folds.
- Direction: On a phone the owner sees every lane's count in one screen, the decision lane comes first or the lanes open collapsed.
- Shot: UX-016, screenshot not kept.
- Decision: Caused by D61 (three shipping lanes) (LOOP-24): lanes are ordered by type, so the lane that needs the owner is last. ACC-19: D61 sets the lanes, not whether they start open.

#### UX-017 The Mark down sheet tells the owner to run a shell command
- Severity: S2 (COPY-06 S2; LOOP-18 S3.)
- Screens: `#/pricing`
- Sources: COPY-06, LOOP-18 (2 lenses: copy, loop)
- Theme: T4 Machine words on the owner's screen
- Defect: 'Run `reconcile --live` to give more rows a true one.' The owner has no terminal on this path. The screen control is 'Reconcile the store' on Runs, and the sheet does not link it.
- Direction: Name the screen press and link it, in one short sentence.
- Shot: UX-017, screenshot not kept.
- Decision: Violates D196 (no mechanism on screen): a shell command is mechanism, and the word list does not hold it. D105 (the markdown lives where prices are decided) moved the sheet and kept the command-line remedy.

#### UX-018 Box is 'drawer' and 'shelf' in the Identify and rebind sheets
- Severity: S2 (COPY-11 S2; LOOP-22 S3.)
- Screens: `#/runs`
- Sources: COPY-11, LOOP-22 (2 lenses: copy, loop)
- Theme: T2 One concept, several names
- Defect: The Identify tabs say 'Drawers' and 'Whole drawer', the hint says 'a divider inside one drawer', and the rebind sheet says 'shelf'. Every other screen, and the Runs list behind the sheet, says Box, and this is the step that spends money.
- Direction: One word, 'box', everywhere a person picks one.
- Shot: UX-018, screenshot not kept.
- Decision: Caused by D153 (the restore asks which drawer) and D180 (a press names the cards it is over): both use 'drawer' in their prose, and the prose word reached the screen. No decision picks one word.

#### UX-019 Home's 'sold' total and Sales' total are different universes
- Severity: S2
- Screens: `#/`, `#/revenue`
- Sources: LOOP-03, COPY-02 (part) (2 lenses: loop, copy)
- Theme: T1 Counts that disagree
- Defect: Home says '1,447 sold'; Sales says '$41.47 over all time, across 7 orders' (about 30 copies); Home's own box rows add up to 19 sold. Nothing says why.
- Direction: One 'sold' figure, or each figure says what it counts (store history against the order ledger), and each links to the other.
- Shot: UX-019, screenshot not kept.
- Decision: Caused by D214 (a gross-sales retrospective over the order ledger) beside D121 (the front page says what is owed): neither entry names the other's count. D214 measured 804 orders live, so the gap may be smaller live (unmeasured).

#### UX-020 Runs speaks the pipeline, not the job
- Severity: S2 (COPY-04 S2; TXT-16 S4.)
- Screens: `#/runs`
- Sources: COPY-04, TXT-16 (2 lenses: copy, density)
- Theme: T4 Machine words on the owner's screen
- Defect: Subtitle 'Identify, join, emit and reconcile a box', stages Join and Emit, figures 'Parked', 'Free · re-runnable', '30 photographs read by the model', 'sub-threshold', and a FILES list of `identifications.json`, `pricing.json`, `report.txt`.
- Direction: Each step is named for what it does for the owner (read the cards, match to TCGplayer, price and write the file, check what is live). Internal files leave the main view. Keep 'Only Identify costs money'.
- Shot: UX-020, screenshot not kept.
- Decision: Violates D196 (no mechanism on screen): 'the model' and 'the join' are on its word list, and the guard does not see composed strings (COPY-04). D33 (one route can spend) is where the money sentence comes from (TXT-16).

#### UX-021 Home's one big button is not the job Home ranks first
- Severity: S2
- Screens: `#/`
- Sources: LOOP-07 (1 lens: loop)
- Theme: T3 Dead ends and dropped hand-offs
- Defect: The ranked line is 'Cannot be filled: 6 copies for 7 open orders'; the one button under it is 'Start capturing'.
- Direction: The one action is the ranked job, or the button says why it outranks it.
- Shot: UX-021, screenshot not kept.
- Decision: Caused by D121 (the front page says what is owed): it makes the button STANDING to serve a fresh store where the line has nothing to press. On a working store the button points away from the ranked job.

#### UX-022 'Search' in the sidebar finds screens, not cards
- Severity: S2
- Screens: shell
- Sources: LOOP-15 (1 lens: loop)
- Theme: T3 Dead ends and dropped hand-offs
- Defect: Typing 'Crowd Favorite' answers 'Nothing matches'. The one control labelled Search cannot find a card.
- Direction: Search finds cards, or its label says it finds screens and commands.
- Shot: UX-022, screenshot not kept.
- Decision: Caused by D95 (the shell is a rail, a palette and a reference sheet): the palette searches screens and verbs by design, and the sidebar labels it 'Search'.

#### UX-023 A refused capture adds a Recent tile while the banner says it was not recorded
- Severity: S2
- Screens: `#/capture`
- Sources: INT-02 (1 lens: interaction)
- Theme: T1 Counts that disagree
- Defect: The red banner says 'the card was not recorded' and the RECENT strip gains a 'B1 #42' tile with a U badge; U then says 'Undid 0 of 1'.
- Direction: A refused shot never looks like a shot that landed.
- Shot: UX-023, screenshot not kept.
- Decision: No decision covers this. D164 (the undo stack is the sitting) rules what U undoes, not how a refused shot draws.

#### UX-024 New section prints a raw JavaScript exception
- Severity: S2
- Screens: `#/capture`
- Sources: INT-03 (1 lens: interaction)
- Theme: T4 Machine words on the owner's screen
- Defect: After a refused capture, S or New section shows 'Cannot read properties of undefined (reading 'length')'. The demo notice invites this path ('dividers write for real').
- Direction: A failed divider says what failed and what to do. Client crash text never reaches the screen.
- Shot: UX-024, screenshot not kept.
- Decision: No decision covers this. The answer shape may come from `demoServer.ts` `openSection` (re-check live).

#### UX-025 The capture refusal banner pushes the Capture button down 123 px
- Severity: S2
- Screens: `#/capture`
- Sources: INT-04 (1 lens: interaction)
- Theme: T8 The screen moves under the hand
- Defect: The banner appears above the header; the header, the RUN card and Capture card move from y 43 to y 166, so the next press at the same place hits another control while the hand is on the rig.
- Direction: A refusal during capture never moves the controls under the hand.
- Shot: UX-025, screenshot not kept.
- Decision: Violates D118 (a press changes what is on the screen, never where the rest of it is).

#### UX-026 Pricing row details read at 3:1
- Severity: S2
- Screens: `#/pricing`
- Sources: ACC-07 (1 lens: access)
- Theme: T10 Keyboard and contrast floors hold on some screens only
- Defect: The grey line under each name (condition, set, rarity, number) is `#91959c` on white, 3.0:1 at 11-12 px (dark 3.33:1). It carries 'Near Mint Foil' against 'Near Mint', which decides the price.
- Direction: Every fact that changes a price decision reads at 4.5:1 or better in both themes.
- Shot: UX-026, screenshot not kept.
- Decision: No decision covers this. prior: related, not the same: system.md logged `--bn-ink-3` at 4.43:1; these spans use a lighter ink.

#### UX-027 Price history lives in three places that do not link to each other
- Severity: S2
- Screens: `#/pricing`, `#/product`, `#/revenue`
- Sources: COH-04 (1 lens: coherence)
- Theme: T3 Dead ends and dropped hand-offs
- Defect: Pricing opens a floating drawer, Sales expands a row into Date / Order / Copies / Unit price, and Product history is a full page with its own chart. None links to another.
- Direction: One price-history view per SKU. The other two places open it, or become it.
- Shot: UX-027, screenshot not kept.
- Decision: Caused by D62 (price history drawn beside the hold) and D227 (a product price view is a route): D227 shares one reader between them, not one view. Nothing covers the Sales row expansion.

#### UX-028 A card on one screen cannot open the same card on another
- Severity: S2
- Screens: `#/pricing`, `#/revenue`, `#/shipping`, `#/runs`, `#/inventory (held)`
- Sources: COH-07 (1 lens: coherence)
- Theme: T3 Dead ends and dropped hand-offs
- Defect: Measured hash links: Pricing links only to Runs and Review, Sales only to Home, Shipping only to its own tabs, Inventory only to Runs. The only card-to-card link is the held Review address pill.
- Direction: A card or order drawn anywhere opens where it lives, in one press, the same way on every screen.
- Shot: UX-028, screenshot not kept.
- Decision: No decision covers this in general. D62 (price history drawn beside the hold) keeps history off Inventory on purpose, which removes one link.

#### UX-029 'Sold' means 'paid' on Sales and 'pulled' on Orders
- Severity: S2
- Screens: `#/revenue`, `#/orders (held)`
- Sources: LOOP-04 (1 lens: loop)
- Theme: T2 One concept, several names
- Defect: Sales counts order 00010 as sold revenue; Orders shows the same order '5 owed, 0 sold, 0 short' because nothing is pulled.
- Direction: Give each meaning its own word ('paid', 'pulled') and use it the same on every stage.
- Shot: UX-029, screenshot not kept.
- Decision: Violates D214 (a retrospective over everything closed): Sales counts an order that Orders shows open.

#### UX-030 'Identify Mixed Singles on Runs' lands on Runs scoped to every box
- Severity: S2
- Screens: `#/capture`, `#/runs`
- Sources: LOOP-06 (1 lens: loop)
- Theme: T3 Dead ends and dropped hand-offs
- Defect: The button names one box. Runs opens on 'Every card waiting to be identified' and the Identify sheet on 'Everything that needs it', so the next press spends money across the store.
- Direction: The press arrives with the named box as the scope, or the label names no box.
- Shot: UX-030, screenshot not kept.
- Decision: Violates D39 (the pipeline gets a route, and the selection is handed to it).

#### UX-031 After the import file is written, nothing says what to do next
- Severity: S2
- Screens: `#/pricing`, `#/runs`, `#/`
- Sources: LOOP-11 (1 lens: loop)
- Theme: T3 Dead ends and dropped hand-offs
- Defect: The file is written on Pricing, but the next steps (upload, Export From Staged, compare) are on Runs step 4. Home's spine has no listing stage.
- Direction: The screen that writes the file shows the next step and a way to it. Home shows 'written, not yet compared' as a stage.
- Shot: UX-031, screenshot not kept.
- Decision: Caused by D105 (the markdown lives where prices are decided) and D99 (one press writes one spreadsheet): the write moved to Pricing and the compare stayed on Runs. Pricing's success state was not seen (emit refused).

#### UX-032 Home does not lead to Sales
- Severity: S2 (LOOP-12 rated the combined Sales + Product finding S2.)
- Screens: `#/`, `#/revenue`
- Sources: LOOP-12 (part) (1 lens: loop)
- Theme: T3 Dead ends and dropped hand-offs
- Defect: Home has 0 links to `#/revenue`; the loop's last stage is reached only from the nav.
- Direction: Home's spine ends at Sales.
- Shot: UX-032, screenshot not kept.
- Decision: No decision covers the spine's end. D214 (Sales is its own route) added the route after D121's spine.

#### UX-033 On a phone, Capture's main press falls below the fold
- Severity: S2
- Screens: `#/capture`
- Sources: LOOP-26 (1 lens: loop)
- Theme: T7 The phone is a second-class screen
- Defect: At 390 the camera card fills the fold; 'Capture card' sits under it once a box is picked, so each card needs a scroll, and a halt pushes it further.
- Direction: The capture press is reachable without a scroll at 390.
- Shot: UX-033, screenshot not kept.
- Decision: No decision covers this. D32 (the pixel budget is spent on the card) argues the camera's size, not the press below it.

#### UX-034 Sales at real density leads each row with the full catalog string
- Severity: S2
- Screens: `#/revenue`
- Sources: VIS-02 (1 lens: visual)
- Theme: T9 Built on fixtures, broken at real density
- Defect: Live, every row reads like 'Riftbound League of Legends Trading Card Game - Vendetta: …'; the card name sits mid-string and the figures get the right 290 px.
- Direction: Lead each row with the card name; set, number and condition as quiet secondary text; the game once.
- Shot: UX-034, screenshot not kept.
- Decision: Caused by D214 (a gross-revenue retrospective, searchable by name): D214 measured 539 distinct names and still draws each verbatim. The live screenshots were not kept.

#### UX-035 Pricing scrolls sideways at 360 px
- Severity: S2
- Screens: `#/pricing`
- Sources: ACC-01 (1 lens: access)
- Theme: T7 The phone is a second-class screen
- Defect: At 360 the 'Custom' option of the price-rule strip runs 6 px past the edge; the tab bar and sheets then measure 366 px on a 360 px screen.
- Direction: The rule strip fits 360 px so the page never pans sideways.
- Shot: UX-035, screenshot not kept.
- Decision: No decision covers this. D117 and CLAUDE.md name 390 as the smallest checked width, so 360 has no reader.

#### UX-036 Graveyard at real density is wider than the page and 86,935 px tall
- Severity: S2
- Screens: `#/graveyard`
- Sources: VIS-03 (1 lens: visual)
- Theme: T9 Built on fixtures, broken at real density
- Defect: Live at 1440 the table's right edge is at x = 1517, the Run column is cut, a 250 px Order column holds only '–', condition wraps to three lines, and 1,180 rows make an 86,935 px page.
- Direction: The table fits at 1440, width goes to columns that carry data, condition stays on one line, and a long list is paged or windowed.
- Shot: UX-036, screenshot not kept.
- Decision: No decision covers width or length. D134 (the graveyard is where the departed are read) set the screen. prior: ux-2026-09-20/graveyard.md finding 5 logged the length (863 rows, now 1,180); the width overflow is new. The live screenshots were not kept.

#### UX-037 The phone drawer hides Graveyard and Codes below its fold
- Severity: S2
- Screens: shell
- Sources: ACC-05 (1 lens: access)
- Theme: T7 The phone is a second-class screen
- Defect: At 390 the Library group shows only Inventory, then Cards to pull; Graveyard and Codes sit under the foot with only a 32 px fade as a cue.
- Direction: Every screen in the drawer shows without a scroll on a common phone, or the list plainly continues.
- Shot: UX-037, screenshot not kept.
- Decision: Caused by D204 (the drawer scrolls above its foot): D204 proved Codes is tappable after a scroll, not that a person knows to scroll.

### S3

#### UX-038 Error and refusal notices print raw codes, request paths and a repo command
- Severity: S3 (All S3 except TXT-46 S4.)
- Screens: `#/runs`, `#/pricing`, `#/capture`, `#/codes`, `#/shipping`, `#/revenue`, `#/product`, `#/graveyard`
- Sources: INT-08, COPY-24, LOOP-14, TXT-46 (4 lenses: interaction, copy, loop, density)
- Theme: T4 Machine words on the owner's screen
- Defect: Each notice adds a mono code line (`demo_read_only`, `demo_not_recorded`), and server text is drawn verbatim, so paths ('GET /pipeline/price-now?sku=…' with 21 SKUs) and 'Rebuild it with `make demo`' reach the owner. The words are the demo's; the layout that prints them is the product's.
- Direction: A refusal is one sentence and one way forward. Codes and paths stay behind a disclosure, as Capture's 'What the server said' already does.
- Shot: UX-038, screenshot not kept.
- Decision: Violates D196 (no mechanism on screen) (INT-08, LOOP-14, TXT-46). Caused by D196's exemption of the `Notice` `code` prop (COPY-24): its premise that the raw string 'stays available on hover and in the run log' is false, because the code draws in plain view. Server and demo text is not read by the `no mechanism on screen` row. prior: ux-2026-09-20/graveyard.md finding 2 (sibling raw string).

#### UX-039 Home's tile notes are cut, and the cut half is the bad news
- Severity: S3
- Screens: `#/`
- Sources: VIS-19, COPY-21, ACC-18 (3 lenses: visual, copy, access)
- Theme: T7 The phone is a second-class screen
- Defect: '27 copies to pull and 6 ...' is cut at 1440 (whole at 820); at 390 '18 cards in Mixed Singl…' and the Orders note end in an ellipsis. '6 not found' is the part that needs action.
- Direction: A tile's note reads whole at every width, or has a short form on purpose ('27 to pull, 6 missing').
- Shot: UX-039, screenshot not kept.
- Decision: No decision covers this. D121 (the front page says what is owed) makes the owed part Home's point, and the ellipsis cuts exactly that part.

#### UX-040 Keyboard hints show on a touch phone
- Severity: S3
- Screens: `#/`, `#/capture`, `#/revenue`, shell drawer, shell palette
- Sources: LOOP-29, ACC-10, TXT-34 (3 lenses: loop, access, density)
- Theme: T7 The phone is a second-class screen
- Defect: At 390 Home's ranked card keeps ',O', the drawer shows ',H', ',C' on every row, Capture shows eight keycaps, Sales shows '/', and the palette footer shows '↑↓ move' and an 'esc' chip that does nothing on a tap.
- Direction: On a coarse pointer the screen shows only what a finger can use, the same on every screen.
- Shot: UX-040, screenshot not kept.
- Decision: No decision covers this. D51 and D95 own the keys, not how they show on touch. The Kit's own Keycaps caption says keycaps are 'Hidden on coarse pointers' (TXT-34). prior: ux-2026-09-20/home.md noted ',O' at 1440 only.

#### UX-041 Errors and refusals have no one shape, and a permanent 'no' is drawn as a retry
- Severity: S3 (COH-27, INT-09 and COPY-42 S3; INT-26 S4.)
- Screens: `#/graveyard`, `#/pricing`, `#/revenue`, `#/capture`, `#/runs`, `#/codes`, `#/shipping`, `#/product`, `#/orders (held)`
- Sources: COH-27, INT-09, COPY-42, INT-26 (3 lenses: coherence, interaction, copy)
- Theme: T6 Each screen builds its own parts
- Defect: Capture uses a full-width banner with Resume, Pricing a notice inside the sticky bar, Codes a dismissable notice, Sales a banner at the page foot, Graveyard a neutral empty-state card with an accent icon. Only Codes can dismiss, only Capture offers a next step, and Graveyard's 'Try again' redraws the same error with no busy state.
- Direction: One error shape and one refusal shape, next to the control that caused them, with the same tone and next step. A refusal says it cannot be done here and offers no retry; a retry shows that it is trying.
- Shot: UX-041, screenshot not kept.
- Decision: No decision covers this.

#### UX-042 Search has three forms, and Pricing's 30-row list has none
- Severity: S3 (COH-20 S3; INT-25 and VIS-29 S4.)
- Screens: `#/product`, `#/pricing`, `#/revenue`, `#/fulfillment`
- Sources: COH-20, INT-25, VIS-29 (part) (3 lenses: coherence, interaction, visual)
- Theme: T6 Each screen builds its own parts
- Defect: Sales, Orders and Inventory share one field with '/'; Cards to pull uses it at 60 px with a dead '/'; Product uses a plain 1,140 px-wide input with a separate button that does nothing on an empty press; Pricing has no name search.
- Direction: The shared search field on every screen that lists or finds cards, Pricing included; an empty press says what to type.
- Shot: UX-042, screenshot not kept.
- Decision: No decision covers this. D227 (a product price view) built the plain field.

#### UX-043 Money is drawn in four faces
- Severity: S3
- Screens: `#/revenue`, `#/pricing`, `#/shipping`, `#/gallery`, `#/review (held)`
- Sources: COH-15, VIS-04 (2 lenses: coherence, visual)
- Theme: T6 Each screen builds its own parts
- Defect: Sales uses JetBrains Mono (`.bn-money`), Pricing's Market column Inter 13/600 and its field Inter 16/700, Shipping chips Inter 11/600, Review Manrope 18/800, the Kit stat Manrope 22/800.
- Direction: One face for a dollar figure on every screen, inside inputs and chips too.
- Shot: UX-043, screenshot not kept.
- Decision: Violates D221 (money stays mono). D221's premise that 'Pricing's worklist … agree[s] on the mono face already' is measured false: the Market column is Inter. prior: ux-2026-09-20/pricing.md finding 4 (format, not face).

#### UX-044 The write step is 'Emit' in some places and 'Write the import file' in others
- Severity: S3
- Screens: `#/runs`, `#/pricing`
- Sources: COH-09, COPY-18 (2 lenses: coherence, copy)
- Theme: T2 One concept, several names
- Defect: Runs says 'Emit' and 'Price and emit this run'; Pricing's button says 'Write the import file', then 'Emit can still refuse.' and the run picker 'Never emitted'. No screen explains 'emit'.
- Direction: One name for the act, the button's words, everywhere ('written', 'not written yet').
- Shot: UX-044, screenshot not kept.
- Decision: Violates D196 (no mechanism on screen): 'emit' is a pipeline command, and D196's word list does not hold it.

#### UX-045 The price floor has five names
- Severity: S3
- Screens: `#/pricing`, `#/runs`
- Sources: COH-10, COPY-17 (2 lenses: coherence, copy)
- Theme: T2 One concept, several names
- Defect: 'cut-off', 'the line', 'cheap', 'floor' ('clamped at the floor after rounding') on Pricing, and 'sub-threshold' on Runs.
- Direction: One word ('cut-off') and a caption that says what it does.
- Shot: UX-045, screenshot not kept.
- Decision: Violates D196 (no mechanism on screen) for 'sub-threshold' (COH-10). D98 (the cheap-card figure is the control) named the floor for Pricing only.

#### UX-046 The phone tab bar lights no tab on eight screens
- Severity: S3 (ACC-09 S3; COH-28 S4.)
- Screens: `#/`, `#/runs`, `#/pricing`, `#/shipping`, `#/revenue`, `#/graveyard`, `#/codes`, `#/product`
- Sources: ACC-09, COH-28 (2 lenses: access, coherence)
- Theme: T7 The phone is a second-class screen
- Defect: The bar holds Capture, Review, Orders, Inventory and More; on these screens no tab is lit, More never shows current, and Shipping does not light Orders. Menu and More have no `aria-expanded`.
- Direction: Every screen shows its place in the bar ('More' lit when the screen is behind it), and the drawer buttons say they open it.
- Shot: UX-046, screenshot not kept.
- Decision: Caused by D95 (the shell is a rail, a palette and a reference sheet): four routes on the bar and no current state for the rest. D204 keeps the bar at five slots on the owner's word.

#### UX-047 Tertiary text and sidebar hints fall under contrast in light
- Severity: S3
- Screens: `#/`, `#/revenue`, `#/gallery`, shell, `#/inventory (held)`, `#/orders (held)`
- Sources: VIS-17, ACC-08 (2 lenses: visual, access)
- Theme: T10 Keyboard and contrast floors hold on some screens only
- Defect: `--bn-ink-4` is 3.33:1 on the ground ('Behind that:', Sales month labels); pills 3.84-4.28:1 at 10-11 px; sidebar ',H' hints 2.22:1 at 10 px, group labels and '122 cards' 3.63:1.
- Direction: Raise the lightest ink, the tinted pill inks and the hints to 4.5:1 in light, or keep them off text a person must read.
- Shot: UX-047, screenshot not kept.
- Decision: No decision covers owner-screen contrast; DESIGN.md's 7:1 floor is Fulfiller-only. prior: ux-2026-09-20/RANKING.md item 2 and graveyard.md finding 3; the fix raised `--bn-ink-3`, `--bn-ink-4` is still 3.33:1.

#### UX-048 Capture has no heading on a phone
- Severity: S3 (ACC-14 S3; VIS-31 S4.)
- Screens: `#/capture`
- Sources: ACC-14, VIS-31 (2 lenses: access, visual)
- Theme: T10 Keyboard and contrast floors hold on some screens only
- Defect: At 390 the only h1 is 0x0, so the screen has no visible title and no heading at all (axe `page-has-heading-one`). Every other screen keeps a 28 px title.
- Direction: Capture names itself at every width, visibly or to a screen reader.
- Shot: UX-048, screenshot not kept.
- Decision: No decision covers this. D32 (the pixel budget is spent on the card) explains the hidden visible title, not the lost heading.

#### UX-049 A failed Fulfillment search gives a remedy that cannot work
- Severity: S3
- Screens: `#/fulfillment`
- Sources: INT-31, COPY-43 (2 lenses: interaction, copy)
- Theme: T4 Machine words on the owner's screen
- Defect: 'The search did not finish. Type the name again.' for both a real name and 'zzzz'; typing again gives the same line, and it never says 'no card by that name'.
- Direction: A failed search says whether nothing matched or the search could not run, and offers a step that helps ('Look through a box below').
- Shot: UX-049, screenshot not kept.
- Decision: No decision covers this. Whether the demo refuses search is unknown; the sentence is the product's.

#### UX-050 The 'Behind that' line repeats the spine and links nothing
- Severity: S3
- Screens: `#/`
- Sources: LOOP-21, TXT-25 (2 lenses: loop, density)
- Theme: T3 Dead ends and dropped hand-offs
- Defect: 'Behind that: 27 copies to pull · 9 to review · 2 runs to price' is plain text 200 px above tiles that show the same three figures.
- Direction: Keep one: either the line's jobs open their screens, or the ranked spine carries them and the line goes. The lenses disagree on which (LOOP-21: link; TXT-25: delete).
- Shot: UX-050, screenshot not kept.
- Decision: Caused by D121 (the front page says what is owed) (LOOP-21): the lines are drawn as context, not controls. Violates D121 (TXT-25): D121 itself rejected lines whose figure 'is drawn again by the six-stage spine' as furniture.

#### UX-051 Home names missing copies three ways and says 'cannot' twice
- Severity: S3 (COPY-19 S3; TXT-26 S4.)
- Screens: `#/`, `#/orders (held)`
- Sources: COPY-19, TXT-26 (2 lenses: copy, density)
- Theme: T2 One concept, several names
- Defect: 'Cannot be filled — 6 copies for 7 open orders cannot be found.' (reads as less than one copy per order), the tile '6 not found', and Orders 'Short'.
- Direction: One sentence and one word ('6 copies are missing across 7 orders'), the same on Orders.
- Shot: UX-051, screenshot not kept.
- Decision: No decision covers the words. D121 governs the banner, not its wording.

#### UX-052 Capture's strip and box picker count in 'index'
- Severity: S3 (COPY-27 S3; TXT-32 S4.)
- Screens: `#/capture`
- Sources: COPY-27, TXT-32 (2 lenses: copy, density)
- Theme: T4 Machine words on the owner's screen
- Defect: '0 captured', '— next index', '— index span'; picker rows 'next index 43', a '4 boxes' count above four rows. Home calls the same box '18 cards'.
- Direction: Count in cards ('18 cards, next is card 19') and drop 'span' and the redundant count.
- Shot: UX-052, screenshot not kept.
- Decision: No decision covers this row. D41 (the address is a rank) removed 'next index' from Inventory as not a statistic; D153 records the owner calling picker numbers 'waste of space'.

#### UX-053 Pricing needs a printed key for its own words
- Severity: S3
- Screens: `#/pricing`
- Sources: COPY-16, TXT-06 (2 lenses: copy, density)
- Theme: T5 Too many words
- Defect: A 21-word legend is always on screen ('typed = you set a price. held = …'), and the screen also says 'decided', 'answered' and 'answers' for the same things.
- Direction: Words that need no key ('Your price', 'Held', 'Default price', 'Under $0.49'), and no key line.
- Shot: UX-053, screenshot not kept.
- Decision: Caused by D208 (one verdict on Pricing), amendment 'the cut-off strip's four words got a visible legend': the header it glossed now reads '22 of 22 decided · 8 nothing to add', so the premise is gone (TXT-06). Caused by D49 and D86 (one pricing answer) for the word 'answer' (COPY-16).

#### UX-054 The write bar's cap control reads 'hold to [no cap] live per card'
- Severity: S3 (COPY-39 S3; TXT-11 S4.)
- Screens: `#/pricing`
- Sources: COPY-39, TXT-11 (2 lenses: copy, density)
- Theme: T5 Too many words
- Defect: Beside the one button that writes the file: 'split it in two, either side of the cut-off', 'hold to [no cap] live per card', and an always-on shortcut row.
- Direction: A labelled field ('At most [ ] copies listed per card'), 'Split at cut-off', and the shortcut row in the `?` sheet.
- Shot: UX-054, screenshot not kept.
- Decision: Caused by D7 (duplicates aggregate by SKU, amended) (COPY-39): the control is right, the label is not. Caused by D208 (TXT-11): it left the bar as 'the press and its two controls'; the shortcut row came later.

#### UX-055 The Fulfiller's search placeholder is cut on a phone
- Severity: S3 (VIS-25 S3; ACC-23 S4.)
- Screens: `#/fulfillment`
- Sources: VIS-25, ACC-23 (2 lenses: visual, access)
- Theme: T7 The phone is a second-class screen
- Defect: At 390 it reads 'For example, Piercing Li', in the Fulfiller's one 22 px field.
- Direction: A placeholder that fits at 390.
- Shot: UX-055, screenshot not kept.
- Decision: No decision covers this. DESIGN.md's Fulfillment floors are met, and none reads the placeholder.

#### UX-056 The reload control has five forms, and only two show a busy state or answer R
- Severity: S3
- Screens: `#/runs`, `#/pricing`, `#/graveyard`, `#/codes`, `#/revenue`, `#/review (held)`, `#/orders (held)`
- Sources: COH-16, INT-12 (2 lenses: coherence, interaction)
- Theme: T6 Each screen builds its own parts
- Defect: A bare icon on Runs, Graveyard and Codes (no spinner, no disable, R does nothing), icon + R keycap that disables and spins on Pricing and Review, a text button on Orders, 'Compare to today's market' on Sales.
- Direction: One reload control in one header place, the same busy state and the same key on every screen.
- Shot: UX-056, screenshot not kept.
- Decision: No decision covers this.

#### UX-057 Overlays come in four designs and open from both sides
- Severity: S3
- Screens: `#/pricing`, `#/runs`, `#/codes`
- Sources: INT-18, COH-19 (2 lenses: interaction, coherence)
- Theme: T6 Each screen builds its own parts
- Defect: Identify is a centred modal with a stepper, Reconcile/Mark down/Clear are right sheets with differing footers ('Not now', 'Cancel', none), Read a box is a right sheet with an icon header, Hold and the Runs picker are popovers, and Price history opens from the LEFT as a floating card at x = 252. The kit holds no sheet or dialog primitive.
- Direction: One sheet, one modal and one popover from the kit, each with the same side, header, dismiss word and first focus.
- Shot: UX-057, screenshot not kept.
- Decision: No decision covers this. D62 (price history drawn beside the hold) argues the panel is pinned, not which side it opens.

#### UX-058 A refusal or notice pushes the page under the pointer
- Severity: S3
- Screens: `#/shipping`, `#/codes`, `#/revenue`, `#/pricing`
- Sources: INT-10, LOOP-30 (2 lenses: interaction, loop)
- Theme: T8 The screen moves under the hand
- Defect: Shipping Forget/Fill pushes 4,164 elements 123 px (162 at 390); Codes pushes its form 103 px; Sales Compare pushes the table 112 px; Pricing's refusal grows the sticky bar about 200 px over the rows (60% of a phone viewport).
- Direction: A press answers in place and never hides the rows it is about.
- Shot: UX-058, screenshot not kept.
- Decision: Violates D118 (a press changes what is on the screen, never where the rest of it is) (INT-10). LOOP-30: no decision covers the dock.

#### UX-059 Touch targets under 40 px on Pricing and Shipping
- Severity: S3
- Screens: `#/pricing`, `#/shipping`
- Sources: INT-29, ACC-11 (2 lenses: interaction, access)
- Theme: T7 The phone is a second-class screen
- Defect: Price fields are 27 px tall, Compare 34 px, the inline links '14 never identified' and '9 in review' 16 px and 8 px apart, and Shipping's 'What this file does not carry' 18 px.
- Direction: Every control a thumb presses meets the 40 px floor, links in a sentence included.
- Shot: UX-059, screenshot not kept.
- Decision: Violates D117 (the thumb floor is the kit's, the measurement is the hit area). D208 added the Compare toggle (ACC-11).

#### UX-060 Dates use seven formats
- Severity: S3
- Screens: `#/`, `#/runs`, `#/pricing`, `#/revenue`, `#/orders (held)`, `#/inventory (held)`
- Sources: COH-24, COPY-22 (2 lenses: coherence, copy)
- Theme: T2 One concept, several names
- Defect: 'WEDNESDAY, SEPTEMBER 23', '1h ago', '2 hours ago', 'Sep 4', 'placed Sep 3', 'Sep 03, 2026' (zero-padded), 'Aug 24, 2026', '9:30am · Aug 13'.
- Direction: One relative and one absolute format, from one formatter, with no leading zero.
- Shot: UX-060, screenshot not kept.
- Decision: No decision covers this. prior: ux-2026-09-20/sales.md finding 3; it changed since to a zero-padded form and still differs.

#### UX-061 Load trends answers in shorthand and prints 'no sales' on each row
- Severity: S3
- Screens: `#/pricing`
- Sources: COPY-38, TXT-12 (2 lenses: copy, density)
- Theme: T5 Too many words
- Defect: 'Read again · 22 read · 8 not asked · ranges overlap', then 'no sales' on 22 rows.
- Direction: One sentence ('Trends for 22 cards. 8 have no sales.') and '—' for an empty trend.
- Shot: UX-061, screenshot not kept.
- Decision: No decision covers this.

#### UX-062 Sales says too much about nothing
- Severity: S3 (COPY-30 and TXT-36 S3; TXT-35 S4.)
- Screens: `#/revenue`
- Sources: COPY-30, TXT-36, TXT-35 (2 lenses: copy, density)
- Theme: T5 Too many words
- Defect: An 18-word jargon lede ('gross-revenue retrospective'), then 'nothing is recorded for the period before', '0 orders were canceled…' and a 27-word '0 lines were marked refunded…' note. At 390 no product row is in the first viewport. 'fulfilment' is misspelt.
- Direction: A short subtitle ('Gross sales. No fees or costs.'); an exclusion note only when its count is above 0.
- Shot: UX-062, screenshot not kept.
- Decision: Caused by D225 (Sales stops counting a refund as revenue): it makes both notes render at zero so a silent mechanism does not look unwired, a builder's check on the owner's screen, and it measured 0 refunds live, so the owner sees two zeros every day. It also reverses D214 (Canceled dropped with no footnote). D214 asks the lede to say 'gross' (TXT-35).

#### UX-063 Shipping cards say 'Inferred' or 'Certain' with no meaning given
- Severity: S3
- Screens: `#/shipping`
- Sources: COPY-10, TXT-03 (2 lenses: copy, density)
- Theme: T5 Too many words
- Defect: 292 cards carry the word; nothing says what was inferred or how it changes the lane choice.
- Direction: Say what to check ('check the weight'), or show it as an icon with a tooltip and a legend in the lane header.
- Shot: UX-063, screenshot not kept.
- Decision: Caused by D61 (three shipping lanes): `Routing.certain` is the split D61 wants drawn, and the label draws it with no word on what to do.

#### UX-064 Shipping weights print to four decimals, the same on 187 cards
- Severity: S3
- Screens: `#/shipping`
- Sources: COPY-09, TXT-04 (2 lenses: copy, density)
- Theme: T5 Too many words
- Defect: '0.0700 oz/item' on 187 cards and '2.5000 oz/item' on 44.
- Direction: A person's number ('0.07 oz each'), shown only where it differs from the plain-card weight.
- Shot: UX-064, screenshot not kept.
- Decision: Caused by D61 (TXT-04): the lane is inferred from weight, so the figure is evidence only where it is not the constant. COPY-09: no decision covers the format.

#### UX-065 The Kit prints a design log and repository paths
- Severity: S3 (TXT-44 S3; COPY-48 S4.)
- Screens: `#/gallery`
- Sources: TXT-44, COPY-48 (2 lenses: density, copy)
- Theme: T5 Too many words
- Defect: 2,422 words; ten notes (436 words) are sweep history ('settled by forced choice over thirty-seven rounds') and name `docs/specs/logo.md`, `scripts/build-mark.mjs`, `tokens.css`.
- Direction: One caption line per specimen; the history lives in the spec it cites.
- Shot: UX-065, screenshot not kept.
- Decision: Caused by D102 (the mark is an illustration, and the spec is its store of record): the notes copy the spec's history. D196 does not say whether #/gallery is exempt (unknown).

#### UX-066 The page header has a different shape on each screen
- Severity: S3
- Screens: `#/`, `#/capture`, `#/runs`, `#/pricing`, `#/shipping`, `#/revenue`, `#/codes`, `#/fulfillment`, `#/product`
- Sources: COH-17 (1 lens: coherence)
- Theme: T6 Each screen builds its own parts
- Defect: Home has a 56 px greeting and no title, Capture a private header with stats, Pricing a meta line and a legend. The primary action sits under the subtitle on Runs, top right on Codes, in a sticky bar on Pricing, in a card on Shipping and in a side panel on Capture.
- Direction: One header: a title, one line, and the screen's one primary action in one place.
- Shot: UX-066, screenshot not kept.
- Decision: No decision covers this. D197 (one left edge for every page) governs the edge only.

#### UX-067 Heading sizes have no scale
- Severity: S3
- Screens: all
- Sources: VIS-13 (1 lens: visual)
- Theme: T6 Each screen builds its own parts
- Defect: h1 is 28 px on 11 screens, 56 px on Home and 38 px on Cards to pull; h2 has six sizes from 11 px to 24 px; Home's 56 px is off the token scale.
- Direction: Three heading steps, and every h1, h2 and h3 mapped to them.
- Shot: UX-067, screenshot not kept.
- Decision: No decision covers a heading scale. prior: ux-2026-09-20/system.md ('an accumulation, not a scale') and kit.md finding 1, still open.

#### UX-068 The verdict line sits in a different place on each screen, or nowhere
- Severity: S3
- Screens: `#/`, `#/revenue`, `#/pricing`, `#/runs`, `#/shipping`
- Sources: COH-18 (1 lens: coherence)
- Theme: T6 Each screen builds its own parts
- Defect: Home has a ranked card under the greeting, Sales an H2, Pricing 'Pricing is answered.' inside a side card halfway down, Runs and Shipping none.
- Direction: Each work screen states where things stand in the same place and form.
- Shot: UX-068, screenshot not kept.
- Decision: No decision covers this across screens. D208 (Pricing states its verdict once) puts the verdict in the headline deck, not inside a side card, so Pricing drifts from its own decision.

#### UX-069 Opening a Capture field moves the Capture button 202 px (258 px on a phone)
- Severity: S3
- Screens: `#/capture`
- Sources: INT-05 (1 lens: interaction)
- Theme: T8 The screen moves under the hand
- Defect: The Box row opens inline and pushes Capture card and the blocker down; Set hint moves rows 95 px, Rarity 420 px (576 px at 390).
- Direction: Choosing a box does not move the button pressed next.
- Shot: UX-069, screenshot not kept.
- Decision: Violates D118 (a press changes what is on the screen, never where the rest of it is): an inline field pushing the next control is the case D118 measured on Inventory.

#### UX-070 Pricing view toggles lay the whole table out again
- Severity: S3
- Screens: `#/pricing`
- Sources: INT-19 (1 lens: interaction)
- Theme: T8 The screen moves under the hand
- Defect: Market −5% moves every row 2 px; Load trends moves the table 50 px and QTY 140 px left; Custom moves the rule sentence 458 px; own cut-off moves the run card 29 px.
- Direction: A preset or trend load does not move the row being read.
- Shot: UX-070, screenshot not kept.
- Decision: Violates D118 (a press changes what is on the screen, never where the rest of it is).

#### UX-071 Release moves the row away from the pointer
- Severity: S3
- Screens: `#/pricing`
- Sources: INT-20 (1 lens: interaction)
- Theme: T8 The screen moves under the hand
- Defect: Releasing a held row moves 658 elements and the next row slides under the pointer. The Undo toast is good.
- Direction: A released row stays in place until the owner leaves it.
- Shot: UX-071, screenshot not kept.
- Decision: Violates D118. D181 (the order is taken once, and a sale may not retake it) already solves this on Inventory.

#### UX-072 On a phone, most of the loop is two taps away, and two buttons open one drawer
- Severity: S3
- Screens: shell
- Sources: LOOP-28 (1 lens: loop)
- Theme: T7 The phone is a second-class screen
- Defect: No Home tab (Home is the logo); Runs, Pricing, Shipping and Sales cost Menu or More plus a tap; More and Menu open the same drawer.
- Direction: One door to the drawer. Home reachable by a labelled control.
- Shot: UX-072, screenshot not kept.
- Decision: Caused by D120 (the shell speaks one brand at every width, and the phone bar is a rail) and the `tab: true` flags in ROUTES.

#### UX-073 The Pricing price field's focus ring is a faint halo
- Severity: S3
- Screens: `#/pricing`
- Sources: ACC-13 (1 lens: access)
- Theme: T10 Keyboard and contrast floors hold on some screens only
- Defect: Focus adds only a 3 px halo at 18% alpha (about 1.3:1); the border stays grey. Every other control shows a 2 px solid accent outline.
- Direction: The focused price field is as visible as every other focused control.
- Shot: UX-073, screenshot not kept.
- Decision: Violates D50 (an interactive element's feedback is the product's): the price cell replaces the global focus ring.

#### UX-074 While loading, screens state an empty store as fact
- Severity: S3
- Screens: `#/`, `#/shipping`, `#/pricing`, `#/capture`
- Sources: INT-13 (1 lens: interaction)
- Theme: T1 Counts that disagree
- Defect: At 350 ms Home says 'no boxes yet' and 'no export read yet', Shipping draws its full empty drop zone then jumps to 331 orders, Pricing shows a green 'Saved', Capture 'No box yet'.
- Direction: Until the answer arrives, a screen says it is reading. It never says 'none' or 'saved'.
- Shot: UX-074, screenshot not kept.
- Decision: No decision covers this. D171 (a refusal that reaches nobody did not happen) names the same class: a reader that cannot tell 'nothing is wrong' from 'nothing is known yet'.

#### UX-075 Pricing's U key works only in a price field while 'Undo U' shows everywhere
- Severity: S3
- Screens: `#/pricing`
- Sources: INT-11 (1 lens: interaction)
- Theme: T6 Each screen builds its own parts
- Defect: After Escape leaves the field, U does nothing, but the toolbar keycap shows U with no condition. On Capture U works anywhere.
- Direction: The key drawn next to Undo works from anywhere on the screen, or the keycap shows only where it works.
- Shot: UX-075, screenshot not kept.
- Decision: No decision covers this. The `?` sheet's Pricing note is the only record of the rule.

#### UX-076 A capture refusal reads as 'paused', and Resume loops
- Severity: S3
- Screens: `#/capture`
- Sources: LOOP-16 (1 lens: loop)
- Theme: T6 Each screen builds its own parts
- Defect: Every non-camera failure is headlined 'Captures are paused — the card was not recorded' with Resume; Resume then capture halts again, and the reason is behind 'What the server said'. A full disk live would loop the same way.
- Direction: The headline says why it stopped. Resume shows only when resuming can work.
- Shot: UX-076, screenshot not kept.
- Decision: No decision covers this.

#### UX-077 'Cannot be filled' lands on all open orders, not on the short ones
- Severity: S3
- Screens: `#/`, `#/orders (held)`
- Sources: LOOP-08 (1 lens: loop)
- Theme: T3 Dead ends and dropped hand-offs
- Defect: The ranked sentence opens `#/orders?buyer=…` on 'All open (7)'; the short copies are behind the 'Short (6)' filter.
- Direction: A sentence about short copies opens the short copies.
- Shot: UX-077, screenshot not kept.
- Decision: No decision covers this.

#### UX-078 '2 runs to price' on Home opens a page scoped to one run
- Severity: S3
- Screens: `#/`, `#/pricing`
- Sources: COH-26 (1 lens: coherence)
- Theme: T3 Dead ends and dropped hand-offs
- Defect: The Pricing tile opens Box 3 only ('Runs 1'); Box 1, with 27 rows to write, is behind the Runs picker and nothing says it waits.
- Direction: The link opens what its label counted.
- Shot: UX-078, screenshot not kept.
- Decision: Violates D156 (every copy TCGplayer does not hold is one worklist): measured, the default landing shows one run.

#### UX-079 A box is drawn and named six ways, and listed in two orders
- Severity: S3
- Screens: `#/`, `#/capture`, `#/runs`, `#/pricing`, `#/fulfillment`, `#/inventory (held)`, `#/review (held)`
- Sources: COH-11 (1 lens: coherence)
- Theme: T2 One concept, several names
- Defect: Home draws a number tile with no word 'Box', Runs and Pricing 'Box 3 · RB Epics' + a mono slug, Inventory three forms on one screen, Review a caps pill. Home and Cards to pull list 1-4; the Inventory rail lists by recency.
- Direction: One box label (number + name) everywhere, and one order for a list of boxes.
- Shot: UX-079, screenshot not kept.
- Decision: Caused by D132 (Inventory rail ordered by the hand) and D142 (Capture box list ordered by the hand): owner rulings for two screens; Home and Cards to pull keep numeric order. No decision covers the label.

#### UX-080 'Run' names the Capture panel and a pipeline job
- Severity: S3
- Screens: `#/capture`, `#/runs`, `#/`, `#/pricing`, `#/inventory (held)`
- Sources: COPY-12 (1 lens: copy)
- Theme: T2 One concept, several names
- Defect: On Capture 'RUN' labels the box picker and shutter panel; everywhere else a run is a pipeline job.
- Direction: The Capture panel gets another word ('Box', 'Shooting').
- Shot: UX-080, screenshot not kept.
- Decision: No decision covers this. D196 names 'run' as an owner word, so both meanings pass.

#### UX-081 The review count is 'to review', 'to answer' and 'in review'
- Severity: S3
- Screens: `#/`, `#/pricing`
- Sources: COPY-20 (1 lens: copy)
- Theme: T2 One concept, several names
- Defect: '9 to review' in 'Behind that', '9 to answer' on the tile 200 px lower, '9 in review' on Pricing.
- Direction: One phrase for the same nine cards.
- Shot: UX-081, screenshot not kept.
- Decision: No decision covers this. D198 makes the number agree; the words still disagree.

#### UX-082 Capture's shutter mode has three names
- Severity: S3
- Screens: `#/capture`
- Sources: COPY-28 (1 lens: copy)
- Theme: T2 One concept, several names
- Defect: The viewfinder chip says 'Manual', the Trigger row 'Key' with `manual:c` under it, the menu 'Manual' and 'C fires it'.
- Direction: One name ('Manual') in all three places, and no `manual:c`.
- Shot: UX-082, screenshot not kept.
- Decision: No decision covers this.

#### UX-083 Pricing's cut-off figure is stated five times
- Severity: S3
- Screens: `#/pricing`
- Sources: TXT-09 (1 lens: density)
- Theme: T5 Too many words
- Defect: The policy card, its caption, '15 under · 15 above', the lower-section sentence and chip, and 'At the $0.49 cut-off' on five rows.
- Direction: The figure once in the policy card; sections give counts; rows say 'Cut-off'.
- Shot: UX-083, screenshot not kept.
- Decision: No decision covers this. D99 makes the figure important, not five times.

#### UX-084 Pricing rows repeat 'Near Mint', 'Typed' and 'of 1'
- Severity: S3
- Screens: `#/pricing`
- Sources: TXT-07, TXT-08 (1 lens: density)
- Theme: T5 Too many words
- Defect: All 30 rows say 'Near Mint' (every row is Near Mint by rule); 21 say 'Typed' under a field with a green check; 22 say 'of 1'. The exceptions are hard to find.
- Direction: Show only states that are not the default; keep 'Foil'.
- Shot: UX-084, screenshot not kept.
- Decision: Caused by D137 (the catalog is Near Mint by rule) (TXT-07): the label cannot differ between rows. TXT-08: no decision covers this.

#### UX-085 The 'Ready to write' panel repeats its heading and the page header
- Severity: S3
- Screens: `#/pricing`
- Sources: TXT-10 (1 lens: density)
- Theme: T5 Too many words
- Defect: 'Ready to write' + check, then 'Pricing is answered.'; 'Scope 1 run · 1 box' and 'Nothing to add 8 SKUs' repeat the header; 'Box 3 · RB Epics' three times above the fold; 'Emit can still refuse.' with no reason.
- Direction: The heading, the not-listed counts as links, and one line '21 rows, 21 copies'.
- Shot: UX-085, screenshot not kept.
- Decision: Caused by D208 (one verdict on Pricing): Ruling A kept `.pricing-verdict-says` as the one statement of the figures; now the figures have their own lines, so D208's own 'two accounts' defect returns one level down.

#### UX-086 'Needs pricing' is two colours on one screen, and blue means several states
- Severity: S3
- Screens: `#/`, `#/runs`
- Sources: VIS-12 (1 lens: visual)
- Theme: T6 Each screen builds its own parts
- Defect: The Pricing tile uses amber for attention; the same state in Recent runs is a blue accent pill; blue also marks neutral counts, green marks 'open', 'Sold' and 'Saved'.
- Direction: One tone for 'needs the owner', apart from neutral counts.
- Shot: UX-086, screenshot not kept.
- Decision: No decision covers a status-colour map.

#### UX-087 Mono is used for dates, names, counts and eyebrows
- Severity: S3
- Screens: `#/`, `#/pricing`, `#/gallery`, shell
- Sources: VIS-05 (1 lens: visual)
- Theme: T6 Each screen builds its own parts
- Defect: Home's date and hero pill ('Box 4 · Mixed Singles'), Home box figures, Pricing eyebrows, the Kit eyebrow and '122 cards' are JetBrains Mono.
- Direction: Mono for SKUs, run ids, card numbers, key caps and money only.
- Shot: UX-087, screenshot not kept.
- Decision: No decision covers this. D221 keeps mono for money and machine strings; the type-role rule is NOT MECHANIZED in CLAUDE.md.

#### UX-088 Capture says 'the camera is not open' five times and 'no box' five times
- Severity: S3
- Screens: `#/capture`
- Sources: TXT-29, TXT-30 (1 lens: density)
- Theme: T5 Too many words
- Defect: 'Camera off' pill, checklist line, button, viewfinder heading, button, Rig 'Not open'; 'No box yet', 'Pick or name a box.', 'Pick a box', 'Pick a box to start.', 'No box'.
- Direction: Keep the viewfinder button, the Box field and the Rig value; delete the repeats.
- Shot: UX-088, screenshot not kept.
- Decision: No decision covers this.

#### UX-089 Inside Box 1 on Cards to pull, every row says 'Box 1 · Section 1'
- Severity: S3
- Screens: `#/fulfillment`
- Sources: TXT-42 (1 lens: density)
- Theme: T5 Too many words
- Defect: 35 rows in large type repeat 'Box 1 · Section 1 · Card N' under a 'Box 1 · RB Origins' heading.
- Direction: A 'Section 1' header, then 'Card 1', 'Card 2' on the rows (owner's call).
- Shot: UX-089, screenshot not kept.
- Decision: Violates D41 (the address is a rank, not a list), as D155 cites it. D5 (two personas) is the counter-argument for the Fulfiller.

#### UX-090 Modal sheets and the palette let Tab walk into the page behind
- Severity: S3
- Screens: `#/codes`, `#/pricing`, shell
- Sources: INT-06 (1 lens: interaction)
- Theme: T10 Keyboard and contrast floors hold on some screens only
- Defect: Read a box has `aria-modal` but 18 of 20 Tab stops land behind the scrim; Clear typed 10 of 20; the palette 4 of 20. Identify, Reconcile and Mark down keep all 20 inside. Measured, not seen.
- Direction: Every blocking overlay keeps focus inside until it closes.
- Shot: UX-090, screenshot not kept.
- Decision: No decision covers this. D95 builds the palette and rules no focus behaviour.

#### UX-091 When an overlay closes, focus often drops to the page body
- Severity: S3
- Screens: shell, `#/pricing`, `#/capture`, `#/revenue`, `#/graveyard`
- Sources: INT-07 (1 lens: interaction)
- Theme: T10 Keyboard and contrast floors hold on some screens only
- Defect: Palette, Clear typed, Set hint, Value my stock and Try again send focus to body; Hold returns it to the price field. After a route change focus is on body on every screen. Measured, not seen.
- Direction: After a sheet, panel or press closes, focus is where the owner left it.
- Shot: UX-091, screenshot not kept.
- Decision: No decision covers this.

#### UX-092 No skip link: each screen starts 15 Tab stops into the sidebar
- Severity: S3
- Screens: all owner routes
- Sources: INT-15 (1 lens: interaction)
- Theme: T10 Keyboard and contrast floors hold on some screens only
- Defect: Brand toggle, 11 links, Cards to pull, Search and Dark mode come first; after a sidebar Enter focus stays on the link, after a ',' chord it goes to body. The `?` sheet says Banchi 'is meant to be driven from the keyboard'.
- Direction: After any navigation, one key press reaches the screen's first control.
- Shot: UX-092, screenshot not kept.
- Decision: No decision covers this. D201 (a route change lands at the top) rules scroll, not focus.

#### UX-093 On a phone, opening one Sales row moves the columns of every row
- Severity: S3
- Screens: `#/revenue`
- Sources: INT-33 (1 lens: interaction)
- Theme: T8 The screen moves under the hand
- Defect: At 390 the disclosure moves Copies, Gross and Last sold 21 px right in all rows (227 elements). Measured, not seen.
- Direction: Opening a row does not change column widths around it.
- Shot: UX-093, screenshot not kept.
- Decision: Violates D118.

#### UX-094 Field and checkbox edges read at 1.4:1
- Severity: S3
- Screens: `#/pricing`, `#/product`, `#/gallery`, `#/inventory (held)`, `#/orders (held)`
- Sources: ACC-12 (1 lens: access)
- Theme: T10 Keyboard and contrast floors hold on some screens only
- Defect: `.bn-input`, `.bn-select` and plain checkboxes draw a 1 px edge at 1.41:1 (dark 1.56-1.63:1) on a same-colour fill.
- Direction: Every field and checkbox edge reads at 3:1 in both themes.
- Shot: UX-094, screenshot not kept.
- Decision: Violates D50 (an interactive element's feedback is the product's): D50 set the `--field` edge at 3.36:1; `--field` now reads `--bn-line-strong`. This is a regression of a settled floor.

#### UX-095 Several screens have one heading and nothing to jump between
- Severity: S3
- Screens: `#/runs`, `#/shipping`, `#/codes`, `#/graveyard`, `#/product`, `#/capture`
- Sources: ACC-20 (1 lens: access)
- Theme: T10 Keyboard and contrast floors hold on some screens only
- Defect: Section titles (the Runs card, lane names, export cards, empty-state titles) are not headings. Measured, not seen.
- Direction: Each visible section title is a heading.
- Shot: UX-095, screenshot not kept.
- Decision: No decision covers this.

#### UX-096 Capture puts an aria-label on a plain paragraph
- Severity: S3
- Screens: `#/capture`
- Sources: ACC-15 (1 lens: access)
- Theme: T10 Keyboard and contrast floors hold on some screens only
- Defect: `<p class="capture-odo-split" aria-label="Where this sitting went">`; axe `aria-prohibited-attr`, serious. The name is lost.
- Direction: The summary is read with its name, or the name is visible text.
- Shot: UX-096, screenshot not kept.
- Decision: No decision covers this.

#### UX-097 The Mark down sheet hides its only forward action at the bottom of the scroll on a phone
- Severity: S3
- Screens: `#/pricing`
- Sources: ACC-17 (1 lens: access)
- Theme: T7 The phone is a second-class screen
- Defect: The pinned footer holds only 'Not now'; 'Fetch my live listings' sits at the end of a 1,044 px body. Clear typed pins both.
- Direction: A sheet's forward action sits next to its dismiss action.
- Shot: UX-097, screenshot not kept.
- Decision: No decision covers this. D105 places the sheet, not its footer.

#### UX-098 Loading takes four forms, and Pricing's header changes shape when data arrives
- Severity: S3
- Screens: all data routes
- Sources: INT-14 (1 lens: interaction)
- Theme: T6 Each screen builds its own parts
- Defect: Skeletons (Home, Runs, Pricing, Graveyard, Codes), a text line (Sales), a spinner and sentence (Fulfillment), nothing (Capture, Shipping, Product). Pricing's toolbar moves below a new subtitle after load.
- Direction: One loading style, in the shape of the loaded screen.
- Shot: UX-098, screenshot not kept.
- Decision: No decision covers this.

#### UX-099 Destructive presses follow three patterns
- Severity: S3
- Screens: `#/shipping`, `#/pricing`, `#/capture`
- Sources: INT-17 (1 lens: interaction)
- Theme: T6 Each screen builds its own parts
- Defect: Shipping Forget acts at once with no confirmation; Clear typed asks first with a count; Capture Clear the setup and Pricing Release act and then offer Undo.
- Direction: One rule for which presses ask first and which offer Undo after.
- Shot: UX-099, screenshot not kept.
- Decision: Caused by D142 (Capture's receipt toast with Undo) and D168 (a typed price is cleared by a press, the Clear sheet); no decision covers Forget. Three rulings made one screen at a time, and no rule joins them.

#### UX-100 The Shipping 'Needs a look' chip has no focus ring
- Severity: S3
- Screens: `#/shipping`
- Sources: INT-16 (1 lens: interaction)
- Theme: T10 Keyboard and contrast floors hold on some screens only
- Defect: Envelope and Parcel draw a 2 px accent ring; 'Needs a look' keeps only its dashed orange border.
- Direction: Every chip shows focus the same way.
- Shot: UX-100, screenshot not kept.
- Decision: No decision covers this. D50 sets cursor, hover and press floors, and no focus floor.

#### UX-101 The Fulfiller's '/' key does nothing, and the Fulfiller cannot open '?'
- Severity: S3
- Screens: `#/fulfillment`
- Sources: INT-24 (1 lens: interaction)
- Theme: T6 Each screen builds its own parts
- Defect: The shortcuts table lists '/ Jump into the search field' for Fulfillment; the key does nothing there, and `?` does not open without a shell.
- Direction: The key works for the Fulfiller, or it leaves the list.
- Shot: UX-101, screenshot not kept.
- Decision: Caused by D5 (two personas), which gives the Fulfiller no shell and so no `?` sheet. The dead '/' is not covered.

#### UX-102 Two different presses are both called 'Reconcile' on Runs
- Severity: S3
- Screens: `#/runs`
- Sources: LOOP-19 (1 lens: loop)
- Theme: T2 One concept, several names
- Defect: Header 'Reconcile the store' (live My Pricing, store-wide) and step 4 'Reconcile' (Export From Staged, this run); at 390 both read 'Reconcile'.
- Direction: Two names, one per job.
- Shot: UX-102, screenshot not kept.
- Decision: Caused by D87 (the reconcile is store-wide), which added a second reconcile and did not rename the first.

#### UX-103 A listing has six names
- Severity: S3
- Screens: `#/pricing`, `#/inventory (held)`
- Sources: COH-23 (1 lens: coherence)
- Theme: T2 One concept, several names
- Defect: 'Lists at', '0 live', 'Every copy is already at TCGplayer', 'live on TCGplayer', 'Pushed 0 · Staged 0 · Room for 1 more live', 'Listed: no import row yet'.
- Direction: One word for 'on TCGplayer now' and one for 'sent, not yet live'.
- Shot: UX-103, screenshot not kept.
- Decision: Violates D196 (no mechanism on screen) for 'Pushed' and 'Staged'. D87 is where 'live' comes from.

#### UX-104 'Reading' has three meanings
- Severity: S3
- Screens: `#/runs`, `#/pricing`, `#/review (held)`
- Sources: COPY-13 (1 lens: copy)
- Theme: T2 One concept, several names
- Defect: The Identify cost step ('Continue to the reading'), a market price ('PRICES READ', 'The reading did not come back') and what the model saw ('Low confidence read').
- Direction: Name the Identify step by what it shows ('Cost check') and keep 'read' for one meaning.
- Shot: UX-104, screenshot not kept.
- Decision: No decision covers this.

#### UX-105 Held counts disagree and do not say why
- Severity: S3
- Screens: `#/pricing`
- Sources: COPY-40 (1 lens: copy)
- Theme: T1 Counts that disagree
- Defect: 'Holding 1' and 'Held back from this run · 1 SKU' against the Clear sheet's '3 held back on purpose'.
- Direction: Each count names its scope ('1 in this run, 3 in the store').
- Shot: UX-105, screenshot not kept.
- Decision: No decision covers this.

#### UX-106 One Pricing action has four names
- Severity: S3
- Screens: `#/pricing`
- Sources: COPY-35 (1 lens: copy)
- Theme: T2 One concept, several names
- Defect: 'Find by value', 'Rank inventory by value', 'What's worth pulling', 'By value'; 'Mark down stale', '… listings', 'Mark down what is not selling', 'Mark down'. Screen-reader and sighted users hear different names.
- Direction: The button, its label and its view share one name.
- Shot: UX-106, screenshot not kept.
- Decision: No decision covers this.

#### UX-107 At 390, 'Clear typed' becomes 'Clear'
- Severity: S3
- Screens: `#/pricing`
- Sources: COPY-36 (1 lens: copy)
- Theme: T7 The phone is a second-class screen
- Defect: Beside 'Saved' and 'Runs' it reads as a clear of the screen; it clears every typed price.
- Direction: A destructive button keeps its object at every width.
- Shot: UX-107, screenshot not kept.
- Decision: No decision covers this.

#### UX-108 Buttons that do not say what they do
- Severity: S3
- Screens: `#/pricing`, `#/shipping`, `#/`
- Sources: COPY-37 (1 lens: copy)
- Theme: T2 One concept, several names
- Defect: 'Compare' adds LOW and +SHIP columns, 'Load trends' adds daily and weekly lines, 'Custom' opens an undercut rule, 'Forget' drops the file, 'Fill pick locations' fills a column, 'Browse' opens Inventory.
- Direction: A verb and its object ('Show lowest prices', 'Forget this file').
- Shot: UX-108, screenshot not kept.
- Decision: No decision covers this.

#### UX-109 Money without a dollar sign, and $0.00 sales with no reason
- Severity: S3
- Screens: `#/pricing`, `#/revenue`
- Sources: COPY-23 (1 lens: copy)
- Theme: T6 Each screen builds its own parts
- Defect: The Market tooltip says 'TCG Market Price: 12.14'; Sales lists six cards at '$0.00' with no word why. Tooltip measured, not seen.
- Direction: Every money figure has '$'; a zero sale says what it was.
- Shot: UX-109, screenshot not kept.
- Decision: No decision covers this. D221 governs the face, not the sign.

#### UX-110 Sales has two period controls with different words
- Severity: S3
- Screens: `#/revenue`
- Sources: COPY-31 (1 lens: copy)
- Theme: T2 One concept, several names
- Defect: Top: '3 months / 6 months / This year / All time / Custom'. On the shelf: 'Month / Quarter / 6 months / Year'. A choice in one does not move the other.
- Direction: One set of period words, or a label that says the lower control answers another question.
- Shot: UX-110, screenshot not kept.
- Decision: Caused by D250 (unsold stock reaches #/revenue), which added the lower control with its own words.

#### UX-111 Sales is the one screen without panels
- Severity: S3
- Screens: `#/revenue`
- Sources: VIS-08 (1 lens: visual)
- Theme: T6 Each screen builds its own parts
- Defect: Headline, chart, month list and table sit on the page ground with hairlines and 11 px eyebrows; other screens use bordered cards with 16-18 px headings.
- Direction: Give Sales the same section surface and heading pattern.
- Shot: UX-111, screenshot not kept.
- Decision: No decision covers the surface. D214 and D217 set content only.

#### UX-112 The Sales chart labels only its two ends
- Severity: S3
- Screens: `#/revenue`
- Sources: VIS-10 (1 lens: visual)
- Theme: T6 Each screen builds its own parts
- Defect: A 60 px line with no axis, no markers and labels for the first and last month; no point can be read.
- Direction: Mark each month, or drop the chart and let the month list carry it.
- Shot: UX-112, screenshot not kept.
- Decision: Caused by D217 (Sales becomes a tool): it keeps the sparkline `aria-hidden` as decoration; the outcome is a chart that tells the owner nothing.

#### UX-113 Sales at real density is a 30,598 px page, with 'On the shelf' at the end
- Severity: S3
- Screens: `#/revenue`
- Sources: VIS-11 (1 lens: visual)
- Theme: T9 Built on fixtures, broken at real density
- Defect: Live: 562 product rows on one page; 'Value my stock' is after all of them.
- Direction: Cap the list (top N with 'show all', or paging) so the sections below are reachable.
- Shot: UX-113, screenshot not kept.
- Decision: Caused by D250 (unsold stock reaches #/revenue): measured on an empty store, it did not see the table at 562 rows. The live screenshots were not kept.

#### UX-114 The Runs list hides most of a real list without a cue
- Severity: S3
- Screens: `#/runs`
- Sources: VIS-27 (1 lens: visual)
- Theme: T9 Built on fixtures, broken at real density
- Defect: Live: header '17 runs', 10 drawn, the rest in an inner scroll with no scrollbar or fade. Cause measured, not confirmed.
- Direction: Show that the list continues, or drop the inner scroll.
- Shot: UX-114, screenshot not kept.
- Decision: No decision covers this. The live screenshots were not kept.

#### UX-115 Body text is 11-12 px on the dense screens
- Severity: S3
- Screens: `#/pricing`, `#/shipping`, `#/revenue`, `#/runs`, `#/inventory (held)`
- Sources: VIS-07 (1 lens: visual)
- Theme: T6 Each screen builds its own parts
- Defect: Shipping: 1,193 nodes at 11 px, 1 at 14 px. Pricing: 271 at 12 px, 59 at 11 px. The stated body size is 14 px.
- Direction: A 13 px floor for text a person must read; 10-11 px for labels only.
- Shot: UX-115, screenshot not kept.
- Decision: No decision covers a reading-size floor on owner screens; D117 is a target floor. prior: ux-2026-09-20/system.md counted tokens, not graded.

#### UX-116 Each screen draws a card differently
- Severity: S3
- Screens: `#/pricing`, `#/revenue`, `#/fulfillment`, `#/inventory (held)`, `#/review (held)`
- Sources: COH-13 (1 lens: coherence)
- Theme: T6 Each screen builds its own parts
- Defect: Pricing: thumb + name + condition/set/number/rarity. Sales: name only, so two printings look the same. Inventory: name + mono number + game. Review: name + '· 148/221'.
- Direction: One card identity line (name, set, number, finish) wherever a card is listed.
- Shot: UX-116, screenshot not kept.
- Decision: No decision covers the line. D67 covers the number only.

#### UX-117 A missing photograph is drawn four ways
- Severity: S3
- Screens: `#/pricing`, `#/`, `#/inventory (held)`, `#/review (held)`
- Sources: COH-14 (1 lens: coherence)
- Theme: T6 Each screen builds its own parts
- Defect: An empty grey square (Pricing), a pastel gradient card (Home), a hatched panel with a path (Inventory), a dark panel 'The file is not on disk' with a path (Review).
- Direction: One 'no photo' state at every size.
- Shot: UX-117, screenshot not kept.
- Decision: No decision covers this.

#### UX-118 One clock icon has four meanings
- Severity: S3
- Screens: shell, `#/product`, `#/runs`, `#/`, `#/pricing`
- Sources: COH-21 (1 lens: coherence)
- Theme: T6 Each screen builds its own parts
- Defect: The same `history` icon marks Graveyard, Product history, the run list and a row's price history.
- Direction: One icon, one meaning.
- Shot: UX-118, screenshot not kept.
- Decision: No decision covers this.

#### UX-119 The key sheet opens with a paragraph about itself
- Severity: S3
- Screens: shell
- Sources: COPY-33 (1 lens: copy)
- Theme: T5 Too many words
- Defect: 'Banchi is meant to be driven from the keyboard. Everything it answers to is here, in 85 entries — …' and notes like 'a sheet mid-request is the one thing that stays put'.
- Direction: A title and the keys; a note is one short line at its key.
- Shot: UX-119, screenshot not kept.
- Decision: No decision covers the intro. D95 governs the sheet's contents.

#### UX-120 The Mark down sheet has 92 words before its first field
- Severity: S3
- Screens: `#/pricing`
- Sources: TXT-13 (1 lens: density)
- Theme: T5 Too many words
- Defect: An intro that repeats the title, a reassurance, a 52-word note on how listing age is dated, and 'or drop a My Pricing export below' above a drop zone that says it.
- Direction: The title, one line ('Edits live listings. Deletes nothing.'), then the form; the age note behind an info control.
- Shot: UX-120, screenshot not kept.
- Decision: Caused by D100 (the age is a proxy that says so): it puts the proxy in its own paragraph and asserts it in a spec; the outcome needs one sentence.

#### UX-121 The Reconcile sheet starts with a 44-word sentence and an undated warning
- Severity: S3
- Screens: `#/runs`
- Sources: TXT-24 (1 lens: density)
- Theme: T5 Too many words
- Defect: A 44-word account of both directions, then 'Every LIVE figure … is only as current as the last time this ran.' with no date.
- Direction: One sentence, a real 'Last run' date, the button, the drop zone.
- Shot: UX-121, screenshot not kept.
- Decision: Caused by D87 (the reconcile is store-wide): it asks the report for both directions, not the sheet.

#### UX-122 A 31-word tip about a rare mistake is on every run
- Severity: S3
- Screens: `#/runs`
- Sources: TXT-18 (1 lens: density)
- Theme: T5 Too many words
- Defect: 'Queued a whole stack under the wrong rarity? Fix it on Inventory → Manage box → Rarity…' sits between the stats and the steps.
- Direction: Show it next to the rarity control, or after a rarity change.
- Shot: UX-122, screenshot not kept.
- Decision: No decision covers this.

#### UX-123 The run page shows its steps twice and repeats its stats
- Severity: S3
- Screens: `#/runs`
- Sources: TXT-19 (1 lens: density)
- Theme: T5 Too many words
- Defect: A step strip above the same four steps as rows; the Join subtitle repeats the stat row; 'Free · re-runnable' three times.
- Direction: One list of steps; 'Free'.
- Shot: UX-123, screenshot not kept.
- Decision: No decision covers this.

#### UX-124 The Emit step says 'Pricing' five times
- Severity: S3
- Screens: `#/runs`
- Sources: TXT-20 (1 lens: density)
- Theme: T5 Too many words
- Defect: Subtitle, a 27-word paragraph, the button, a 22-word note ('one answer for the whole store now'), and 'Price 30 SKUs →'.
- Direction: The subtitle and the button only.
- Shot: UX-124, screenshot not kept.
- Decision: Caused by D86 (one pricing file for the store): 'now' is a migration note that has outlived the migration (unmeasured when the last run-scoped rule was used).

#### UX-125 Reduced motion speeds up the live dot and keeps the shimmer
- Severity: S3
- Screens: `#/inventory (held)`, `#/runs`, all loading screens
- Sources: ACC-16 (1 lens: access)
- Theme: T10 Keyboard and contrast floors hold on some screens only
- Defect: Under `prefers-reduced-motion` the live dot pulses every 1.4 s (normal 1.8 s) and the skeleton shimmer keeps sweeping. Measured, not seen.
- Direction: A request for less motion never makes a thing move faster, and decorative sweeps stop.
- Shot: UX-125, screenshot not kept.
- Decision: No decision covers this. The `base.css` comment argues a stopped shimmer reads as broken; it does not cover a faster dot.

#### UX-126 'Waiting on the capture server' shows while the shell says 'Server online'
- Severity: S3
- Screens: `#/pricing?band=top`
- Sources: INT-32 (1 lens: interaction)
- Theme: T1 Counts that disagree
- Defect: Find by value says 'The store could not be read. Waiting on the capture server.' beside 'Server online · 122 cards'; its primary blue Try again differs from the secondary ones elsewhere.
- Direction: An error names its real cause, and the same retry looks the same everywhere.
- Shot: UX-126, screenshot not kept.
- Decision: No decision covers this.

### S4

#### UX-127 The CSS separator dot is glued to the next figure
- Severity: S4
- Screens: `#/pricing`
- Sources: LOOP-31, VIS-22, COPY-47 (3 lenses: loop, visual, copy)
- Theme: T6 Each screen builds its own parts
- Defect: '22 of 22 decided ·8 nothing to add', '1 run ·1 box'; 68 hand-written `content: '·'` rules across 21 CSS files with five margin patterns. The header also shows the run id `demo-box3` in mono.
- Direction: One separator primitive in the kit; the header names the box, not the run id.
- Shot: UX-127, screenshot not kept.
- Decision: Caused by D41 (the separator is deleted, not replaced) and D218 (a typed dot is a defect): D218 moved each seam into CSS file by file and gave no kit primitive.

#### UX-128 Capture's RUN card is narrower than its siblings on a phone
- Severity: S4
- Screens: `#/capture`
- Sources: LOOP-27, ACC-24 (2 lenses: loop, access)
- Theme: T7 The phone is a second-class screen
- Defect: `.capture-card-run` is 279-290 px beside 358 px cards, leaving about 70 px empty.
- Direction: One width for the phone column.
- Shot: UX-128, screenshot not kept.
- Decision: No decision covers this.

#### UX-129 The Home greeting is twice every other title and outranks the owed line
- Severity: S4
- Screens: `#/`
- Sources: VIS-30, TXT-28 (2 lenses: visual, density)
- Theme: T6 Each screen builds its own parts
- Defect: A 56 px 'Good afternoon.' and a date, the largest thing in the product, above the 'Cannot be filled' line; at 390 it pushes Start capturing lower.
- Direction: The owed line leads at the product's title size (owner's call on the greeting).
- Shot: UX-129, screenshot not kept.
- Decision: D121 (the front page says what is owed) argues the owed line leads and kept the greeting above it. prior: ux-2026-09-20/system.md lists the 56 px literal as off-scale.

#### UX-130 Capture sheets speak the plumbing and caption their own row
- Severity: S4
- Screens: `#/capture`
- Sources: COPY-29, TXT-33 (2 lenses: copy, density)
- Theme: T4 Machine words on the owner's screen
- Defect: 'No TCGplayer session. The hint is stored exactly as typed.'; 'Needed for this game' under 'Needed'; a 13-word Tuning instruction.
- Direction: Say what the owner can do ('Type the set name. We cannot check it now.'), 'Trigger is off.'
- Shot: UX-130, screenshot not kept.
- Decision: No decision covers this. D76 governs the hint, not the note.

#### UX-131 The hold sheet explains the store model and uses two undo verbs
- Severity: S4
- Screens: `#/pricing`
- Sources: COPY-41, TXT-15 (2 lenses: copy, density)
- Theme: T5 Too many words
- Defect: '…one answer for the whole store, outliving every run over this box.'; the chip 'Bullish' is captioned 'Bullish — waiting for the price to move'; 'Release' on the row, 'Lift' in the Clear sheet.
- Direction: 'This card stays out of every file until you release it.' One verb.
- Shot: UX-131, screenshot not kept.
- Decision: Caused by D49 (a card can be held back on purpose): the sheet repeats the decision in its own words.

#### UX-132 Product history explains its own mechanism
- Severity: S4
- Screens: `#/product`
- Sources: COPY-26, TXT-40 (2 lenses: copy, density)
- Theme: T5 Too many words
- Defect: 'This page is per product, and it never guesses which one you mean.' plus a 14-word lede; 27 of 40 words can go.
- Direction: Title, field, button and one empty title.
- Shot: UX-132, screenshot not kept.
- Decision: Caused by D227: the sentence restates its 'never guesses' rule on screen.

#### UX-133 The title moves up and down between screens
- Severity: S4
- Screens: all owner screens
- Sources: VIS-14 (1 lens: visual)
- Theme: T6 Each screen builds its own parts
- Defect: h1 top is 16, 24, 27, 43 or 53 px by screen; the left edge is constant.
- Direction: One top inset for every title.
- Shot: UX-133, screenshot not kept.
- Decision: D197 protects the left edge only.

#### UX-134 Sidebar foot icons sit 5 px right of the nav icons
- Severity: S4
- Screens: shell
- Sources: VIS-21 (1 lens: visual)
- Theme: T6 Each screen builds its own parts
- Defect: Nav rows: 18 px icon at x = 24, 36 px row. Search and Dark mode: 16 px at x = 29, 34 px row.
- Direction: One icon column and row height for the whole sidebar.
- Shot: UX-134, screenshot not kept.
- Decision: D152 guards the collapsed foot only.

#### UX-135 An Undo button appears after the first write and pushes Holding left
- Severity: S4
- Screens: `#/pricing`
- Sources: INT-21 (1 lens: interaction)
- Theme: T8 The screen moves under the hand
- Defect: 'Undo U' appears between Holding and Load trends; Holding moves about 90 px.
- Direction: Keep a place for Undo, or show it disabled from the start.
- Shot: UX-135, screenshot not kept.
- Decision: Violates D118.

#### UX-136 The Capture card button has no press dip
- Severity: S4
- Screens: `#/capture`
- Sources: INT-22 (1 lens: interaction)
- Theme: T6 Each screen builds its own parts
- Defect: Pressed, it only darkens; every other `bn-btn` dips 1 px and scales to .99. Computed style.
- Direction: The most-pressed button answers like every other.
- Shot: UX-136, screenshot not kept.
- Decision: Violates D50: no `translate: none` opt-out comment in `CaptureScreen.css`, so the loss looks accidental.

#### UX-137 The Capture Box row has no hover
- Severity: S4
- Screens: `#/capture`
- Sources: INT-23 (1 lens: interaction)
- Theme: T6 Each screen builds its own parts
- Defect: Set hint, Rarity, Finish and Rig rows tint on hover; the large Box row does not.
- Direction: The same row gets the same hover.
- Shot: UX-137, screenshot not kept.
- Decision: Violates D50.

#### UX-138 Capture fields disagree on where focus goes when they open
- Severity: S4
- Screens: `#/capture`
- Sources: INT-27 (1 lens: interaction)
- Theme: T10 Keyboard and contrast floors hold on some screens only
- Defect: Box and Set hint focus their text field; Rarity, Finish, Game, Camera, Rotation and Trigger open with focus on body.
- Direction: An open field puts focus on its first choice.
- Shot: UX-138, screenshot not kept.
- Decision: No decision covers this.

#### UX-139 Home's box rows end in a number with no unit
- Severity: S4
- Screens: `#/`
- Sources: COPY-46 (1 lens: copy)
- Theme: T1 Counts that disagree
- Defect: 'RB Origins · 34 on hand · 7 sold', a bar, then '42' (every card ever captured).
- Direction: Label the figure or remove it.
- Shot: UX-139, screenshot not kept.
- Decision: No decision covers this.

#### UX-140 Home stage notes repeat their tile label
- Severity: S4
- Screens: `#/`
- Sources: TXT-27 (1 lens: density)
- Theme: T5 Too many words
- Defect: 'runs on file', 'to answer', 'runs to price', 'no export read yet' under a dash.
- Direction: A note only where it adds a unit or a second number.
- Shot: UX-140, screenshot not kept.
- Decision: No decision covers this.

#### UX-141 Capture's 'Nothing to clear.' sits under a disabled button
- Severity: S4
- Screens: `#/capture`
- Sources: TXT-31 (1 lens: density)
- Theme: T5 Too many words
- Defect: A disabled 'Clear the setup' and 'Nothing to clear.' under it.
- Direction: Delete the sentence.
- Shot: UX-141, screenshot not kept.
- Decision: No decision covers this.

#### UX-142 The Fulfillment status and browse sentences
- Severity: S4
- Screens: `#/fulfillment`
- Sources: TXT-41 (1 lens: density)
- Theme: T5 Too many words
- Defect: 'No orders are waiting… You can still find any card by name.' above a labelled field; '101 cards are in 4 boxes. Tap a box…' above four counted boxes.
- Direction: Owner's call: 'No orders waiting.' and no browse sentence.
- Shot: UX-142, screenshot not kept.
- Decision: Caused by D5 (two personas), which argues for plain sentences; both cuts are judgement calls.

#### UX-143 The translucent tab bar shows large text through its labels
- Severity: S4
- Screens: all owner screens
- Sources: ACC-25 (1 lens: access)
- Theme: T7 The phone is a second-class screen
- Defect: 72% opaque with a 14 px blur; large headings show as letter shapes between the 10 px labels.
- Direction: The labels always sit on a quiet ground.
- Shot: UX-143, screenshot not kept.
- Decision: No decision covers this. D205 sets the bar's height.

#### UX-144 Page width has three maximums
- Severity: S4
- Screens: `#/pricing`, `#/`, `#/codes`, `#/shipping`, others
- Sources: VIS-15 (1 lens: visual)
- Theme: T6 Each screen builds its own parts
- Defect: Max-width 1120 px (Pricing), 1344 px (Home, Codes, Shipping), 1600 px elsewhere; at 1440 Pricing stops 84 px short.
- Direction: Fewer page widths, each for a reason the screen shows.
- Shot: UX-144, screenshot not kept.
- Decision: Caused by D197 (one left edge, only width may vary): 'legitimately different caps' gives a right edge that moves between screens.

#### UX-145 Keycaps sit on different sides of their labels
- Severity: S4
- Screens: `#/capture`, shell, `#/`, `#/pricing`
- Sources: VIS-20 (1 lens: visual)
- Theme: T6 Each screen builds its own parts
- Defect: Left of the label in Capture, right in the sidebar, inside the button on Home, beside the header on Pricing.
- Direction: One placement rule for a shortcut hint.
- Shot: UX-145, screenshot not kept.
- Decision: No decision covers placement.

#### UX-146 The Pricing toolbar wraps into ragged rows at 820 and 390
- Severity: S4
- Screens: `#/pricing`
- Sources: VIS-23 (1 lens: visual)
- Theme: T7 The phone is a second-class screen
- Defect: At 820 refresh and its R cap drop alone to a second row; at 390 two rows of unequal buttons with 'Runs 1' floating.
- Direction: A toolbar that folds as a unit.
- Shot: UX-146, screenshot not kept.
- Decision: No decision covers this. D195 exempts a horizontal row.

#### UX-147 The Sales period picker breaks into two rows on a phone
- Severity: S4
- Screens: `#/revenue`
- Sources: VIS-24 (1 lens: visual)
- Theme: T7 The phone is a second-class screen
- Defect: The five-segment control wraps to 3 + 2 inside one tray.
- Direction: One row (shorter labels or scrolling), or a select.
- Shot: UX-147, screenshot not kept.
- Decision: No decision covers this.

#### UX-148 Runs is mostly empty space at 1440
- Severity: S4
- Screens: `#/runs`
- Sources: VIS-28 (1 lens: visual)
- Theme: T6 Each screen builds its own parts
- Defect: A 320 px list and an 800x360 panel that says only 'Pick a run'; empty below 512 px.
- Direction: Open the newest run by default at desk width, or let the list use the width.
- Shot: UX-148, screenshot not kept.
- Decision: D39 created the layout; no decision covers the empty state.

#### UX-149 Sales cuts the order id at the part that tells orders apart
- Severity: S4
- Screens: `#/revenue`
- Sources: LOOP-33 (1 lens: loop)
- Theme: T2 One concept, several names
- Defect: 'A2FFC195-958…': every order shares the prefix.
- Direction: Show the tail, or the order's short name.
- Shot: UX-149, screenshot not kept.
- Decision: No decision covers this.

#### UX-150 The Shipping header says each count twice
- Severity: S4
- Screens: `#/shipping`
- Sources: TXT-05 (1 lens: density)
- Theme: T5 Too many words
- Defect: A lede describing the lanes, '126 orders in the parcel lane are in this file.' above 'Download · 126 orders', '331 orders' on tab and card.
- Direction: One statement per count; 'kept 30 min'.
- Shot: UX-150, screenshot not kept.
- Decision: No decision covers this.

#### UX-151 The empty Runs panel explains the list beside it
- Severity: S4
- Screens: `#/runs`
- Sources: TXT-17 (1 lens: density)
- Theme: T5 Too many words
- Defect: 'Join, emit and reconcile act on the run you pick from the list.' and a 'Runs' panel title under the H1 'Runs'.
- Direction: 'Pick a run' alone.
- Shot: UX-151, screenshot not kept.
- Decision: No decision covers this.

#### UX-152 An open run step explains what the step does
- Severity: S4
- Screens: `#/runs`
- Sources: TXT-21 (1 lens: density)
- Theme: T5 Too many words
- Defect: Join: 'Resolves each card against a TCGplayer export…' and a 23-word preview note; Reconcile: 24 words of procedure; Identify: 'this run was started from a terminal'.
- Direction: One short line per step, or none.
- Shot: UX-152, screenshot not kept.
- Decision: No decision covers this.

#### UX-153 Identify step 2 explains the press model
- Severity: S4
- Screens: `#/runs`
- Sources: TXT-23 (1 lens: density)
- Theme: T5 Too many words
- Defect: 'Crops to the card, sent at 1200px: $0.62 on box 2…', 'Two drawers that want two readings are two presses.', scope in header and footer.
- Direction: 'Crops to the card, 1200px.' and the scope once.
- Shot: UX-153, screenshot not kept.
- Decision: No decision covers this.

#### UX-154 The Year on every Sales date
- Severity: S4
- Screens: `#/revenue`
- Sources: TXT-37 (1 lens: density)
- Theme: T5 Too many words
- Defect: Every 'Last sold' ends in ', 2026' though the range is one year.
- Direction: Drop the year when the range is in one year.
- Shot: UX-154, screenshot not kept.
- Decision: No decision covers this.

#### UX-155 The Sales table has an empty header and a wide chevron column
- Severity: S4
- Screens: `#/revenue`
- Sources: ACC-22 (1 lens: access)
- Theme: T7 The phone is a second-class screen
- Defect: The disclosure `<th>` is empty (axe) and on a phone takes a quarter of the width.
- Direction: A column as narrow as its chevron, with a hidden name.
- Shot: UX-155, screenshot not kept.
- Decision: No decision covers this.

#### UX-156 The palette has no close control on a phone
- Severity: S4
- Screens: shell
- Sources: ACC-26 (1 lens: access)
- Theme: T7 The phone is a second-class screen
- Defect: The 'esc' chip is not a button; a tap on the dim page closes it, and nothing says so.
- Direction: A Close control on touch, as the sheets have.
- Shot: UX-156, screenshot not kept.
- Decision: No decision covers this. D95 builds the palette.

#### UX-157 Radii drift off the scale
- Severity: S4
- Screens: all
- Sources: VIS-16 (1 lens: visual)
- Theme: T6 Each screen builds its own parts
- Defect: 2, 3, 5, 7, 10, 14 and 20 px radii are in use outside the 4/6/12/16/18/22 token scale; 5 px is on pills on 12 screens. Measured, not seen.
- Direction: Snap each radius to a token.
- Shot: UX-157, screenshot not kept.
- Decision: No decision covers radius drift. prior: ux-2026-09-20/system.md and RANKING.md, still open.

#### UX-158 Counts are drawn two ways
- Severity: S4
- Screens: `#/graveyard`, `#/pricing`, `#/shipping`, `#/orders (held)`
- Sources: VIS-32 (1 lens: visual)
- Theme: T6 Each screen builds its own parts
- Defect: Graveyard tabs use '(1179)'; Pricing, Shipping and Orders use a pill.
- Direction: One count style.
- Shot: UX-158, screenshot not kept.
- Decision: No decision covers this.

#### UX-159 Codes offers two different first steps
- Severity: S4
- Screens: `#/codes`
- Sources: VIS-33 (1 lens: visual)
- Theme: T6 Each screen builds its own parts
- Defect: A primary 'Read a box' in the header and a secondary 'Go to capture' in the empty state.
- Direction: One first step.
- Shot: UX-159, screenshot not kept.
- Decision: No decision covers this. The feature is dormant.

#### UX-160 The Clear typed sheet explains itself three times
- Severity: S4
- Screens: `#/pricing`
- Sources: TXT-14 (1 lens: density)
- Theme: T5 Too many words
- Defect: An 18-word intro, 'Nothing expires on its own…', a 19-word undo footer.
- Direction: 'Nothing at TCGplayer changes.' and 'You can undo this.'
- Shot: UX-160, screenshot not kept.
- Decision: Caused by D168 (a typed price is cleared by a press): the sheet restates D168's rule; it already has the scope, count and undo.

#### UX-161 Tab titles are lower case
- Severity: S4
- Screens: all
- Sources: COPY-34 (1 lens: copy)
- Theme: T2 One concept, several names
- Defect: 'capture', 'runs', 'sales', 'cards to pull'; Home is '番地 banchi'. Measured, not seen.
- Direction: Tab titles match the H1 ('Capture — Banchi').
- Shot: UX-161, screenshot not kept.
- Decision: No decision covers this.

#### UX-162 The Graveyard lede prints 'Read-only'
- Severity: S4
- Screens: `#/graveyard`
- Sources: TXT-38 (1 lens: density)
- Theme: T5 Too many words
- Defect: 'Every card that's left inventory — sold, retired, or moved. Read-only.'
- Direction: 'Sold, retired and moved cards.'
- Shot: UX-162, screenshot not kept.
- Decision: Caused by D134: 'Read-only' is the decision's rule printed as copy.

#### UX-163 The Codes lede and the Read-a-box sheet restate their decision
- Severity: S4
- Screens: `#/codes`
- Sources: TXT-39 (1 lens: density)
- Theme: T5 Too many words
- Defect: 'Read, tier, and hand off code cards.' beside 'Read a box'; 'Free — the QR is the code.'
- Direction: Delete the lede; the sheet says 'Free.'
- Shot: UX-163, screenshot not kept.
- Decision: Caused by D70 (the QR is the whole identification). Feature is dormant.

#### UX-164 The Kit fails axe and does not fit a phone
- Severity: S4
- Screens: `#/gallery`
- Sources: ACC-21 (1 lens: access)
- Theme: T10 Keyboard and contrast floors hold on some screens only
- Defect: Tab samples carry `aria-selected` with no `role=tab`; three field samples and a select have no label; the Data table is 402 px on a 390 px screen.
- Direction: The kit shows the accessible form of each primitive.
- Shot: UX-164, screenshot not kept.
- Decision: No decision covers this. D117 moved `.bn-tab` into the kit for its height, not its role.

## Decisions in question

Each entry is an argument for the owner's word, not a repeal. Premises are quoted from the lens annotations, which read the entries in pass 2. 'Unmeasured' is kept where a lens said so.

### D212: Every copy is fungible, so no order claims one
- Premise that no longer holds: Cards to pull can build its walk from the picks that `GET /orders` carries (D212 measured 84 picks on a seeded store).
- Evidence: VIS-34: `GET /orders` now carries 0 picks on the demo (7 open orders, 29 copies wanted) and live (71 open, 216 wanted); Orders reads `POST /orders/picks` instead; Cards to pull shows 'No orders are waiting'. Which change moved the picks is unmeasured.
- What it protected: No order holds a copy hostage, so a sale can record against any owing order.
- Options:
  - A. Cards to pull reads the same picks source as Orders (`POST /orders/picks`), keeping D212's fungibility.
  - B. `GET /orders` carries picks again, and a check asserts it on a seeded store.
  - C. Cards to pull counts owed copies from the ledger and says how many it cannot place, with no picks at all.
- Recommendation: A, plus the refusal rule from C: never draw 'nothing waits' while any order is open. It fixes the S1 at its cause and keeps D212's outcome.
- Findings: UX-001

### D227: A product price view is a route, not a lens
- Premise that no longer holds: The route is reachable through its own control, and the Sales link can wait until another branch frees `Revenue.tsx`.
- Evidence: COH-03, INT-30, COPY-25, ACC-06, LOOP-12, VIS-29: 0 inbound links on 14 routes; the palette answers 'Nothing matches "product"' because D95 builds 'Go to' from `nav` routes; the branch that held `Revenue.tsx` merged and no link followed.
- What it protected: A per-product view that never guesses which product is meant, without a new nav row.
- Options:
  - A. Link every product name (Sales, Pricing row and history sheet, Inventory card) to `#/product?sku=`, and add off-nav routes with keywords to the palette.
  - B. Put the product view on the nav.
  - C. Fold the view into one price-history sheet that every screen opens (see D62).
- Recommendation: A. It keeps the route off-nav as D227 wants and closes the hard-rule breach (a route is not a feature until a screen reaches it). Take C later with the price-history theme.
- Findings: UX-003, UX-032, UX-042, UX-132

### D221: Money stays mono, and the rule is amended to match
- Premise that no longer holds: 'Pricing's worklist … agree[s] on the mono face already.'
- Evidence: COH-15, VIS-04: measured, the Pricing Market column is Inter 13/600, the price field Inter 16/700, Shipping chips Inter 11/600, Review Manrope 18/800. Only Sales uses `.bn-money`.
- What it protected: Dollar figures read as one kind of number across screens.
- Options:
  - A. Keep the ruling and apply `.bn-money` on Pricing, Shipping, Review and the Kit, including inputs and chips.
  - B. Amend to one Inter tabular style for money, and retire `.bn-money` mono.
  - C. Mechanize the rule first (a checker for dollar text outside `.bn-money`), then pick A or B.
- Recommendation: A, with C's checker in the same change. The ruling is sound; its premise was false when written, and nothing guarded it.
- Findings: UX-043

### D208: Pricing states its verdict once, and the worklist discloses progressively
- Premise that no longer holds: (1) The four-word legend glosses a typed/held/on-the-rule/cheap breakdown in the header. (2) `.pricing-verdict-says` is the one statement of the figures. (3) The phone stack (split, cap, Write) can stay sticky.
- Evidence: TXT-06: the header now reads '22 of 22 decided · 8 nothing to add', so the legend explains words that are not beside it. TXT-10: the figures now have their own lines, so the verdict sentence repeats the heading. ACC-02, VIS-18, LOOP-25: the sticky phone bar is 174-186 px, 29-39% of the screen. ACC-11: the Compare toggle it added is 34 px. COH-18: the verdict sits inside a side card, not the headline deck D208 names.
- What it protected: One statement of where pricing stands, and touch users can read the four states.
- Options:
  - A. Delete the legend (row pills already carry plain words), cut the verdict sentence, and on a phone pin only a one-line Write bar.
  - B. Keep the legend as a tooltip on each pill, keep the layout, and only shrink the phone bar.
  - C. Re-run D208's owner interview on the current screen.
- Recommendation: A. Each part removes text or chrome whose premise is gone, and it keeps the outcome D208 protected.
- Findings: UX-007, UX-053, UX-054, UX-059, UX-068, UX-085

### D225: Sales stops counting a refund as revenue
- Premise that no longer holds: Both exclusion notes must render at zero so a silent mechanism does not look unwired.
- Evidence: COPY-30, TXT-36: the owner's store catches 0 refunds (D225's own measurement), so two zero-count sentences (27 words for one) show every day, and at 390 they fill the first viewport with no product row. It also reverses D214's 'Canceled dropped with no footnote'.
- What it protected: The owner knows refunds and cancellations are excluded, and the builder can see the mechanism is wired.
- Options:
  - A. Show each note only when its count is above 0, as 'N refunded lines left out'.
  - B. One short standing line ('Refunds and cancellations excluded') and no counts at zero.
  - C. Keep as is.
- Recommendation: A. The builder's wiring check belongs in a test, not on the owner's screen.
- Findings: UX-062

### D196: No user-visible string may name a decision, a repository path, or a pipeline-internal noun (guard gap)
- Premise that no longer holds: (1) The `Notice` `code` prop is exempt because the raw string 'stays available on hover and in the run log'. (2) Scanning JSX literals with a word list covers what the owner sees.
- Evidence: COPY-24: the code draws in plain view under the sentence. INT-08, LOOP-14, TXT-46: server and demo text (paths, `make demo`) is drawn verbatim and never scanned. TXT-02, VIS-06, COH-22: Shipping's reason codes are data, not literals. COPY-04: composed strings ('read by the model', 'Join') pass. COH-09, COPY-18, COPY-06: 'emit' and a shell command are not on the word list. COPY-48, TXT-44: whether #/gallery is exempt is unstated.
- What it protected: The owner never meets machine vocabulary.
- Options:
  - A. Remove the `code` exemption: codes render behind a disclosure, as Capture's 'What the server said' does; add 'emit', 'sub-threshold', 'index', 'Staged', 'Pushed' and shell-command shapes to the list.
  - B. Add a browser-side sweep over rendered text (the copy lens's extractor is a start) for snake_case codes, URL paths and `make`.
  - C. State the Kit's status (exempt developer page, or owner screen).
- Recommendation: A and C now; B as the mechanism that makes D196 true for data-driven text. Without B the guard stays green on text the owner sees.
- Findings: UX-005, UX-017, UX-020, UX-038, UX-044, UX-065

### D194: The visible word count on every owner screen may only go down (ceilings measured on fixture states)
- Premise that no longer holds: The pinned ceiling is a measurement of what the owner reads.
- Evidence: COPY-08: #/shipping's ceiling is 133 words, measured with no export loaded; the loaded screen draws 4,939. #/pricing's ceiling is 46 against 870 drawn. The check cannot see the text that most needs cutting.
- What it protected: Every screen's text may only shrink, so additions are decisions.
- Options:
  - A. Pin each screen's ceiling on its loaded, typical state (a fixture with an export, a populated worklist).
  - B. Pin two ceilings per screen: empty and loaded.
  - C. Keep the empty-state pin and add a separate per-card repetition check.
- Recommendation: B. It keeps D194's ratchet and makes it see the loaded screens where the 4,000-word problem lives.
- Findings: UX-015

### D121: The front page says what is owed, and the library is drawn as the work that made it
- Premise that no longer holds: (1) The button is standing because a fresh store has nothing for the ranked line to press. (2) A figure drawn again on the spine is furniture. (3) The greeting may sit above the ranked line.
- Evidence: LOOP-07: on a working store 'Start capturing' points away from 'Cannot be filled'. TXT-25: 'Behind that' repeats three spine figures, which D121 itself rejected. LOOP-21: those lines link nothing. VIS-30, TXT-28: a 56 px greeting outranks the owed line.
- What it protected: Home always has one obvious action, even on an empty store.
- Options:
  - A. The button follows the ranked line when one exists and falls back to 'Start capturing' only on an empty store; drop 'Behind that' or make it the links.
  - B. Keep the standing button and make the ranked line itself the primary press.
  - C. Keep as is.
- Recommendation: A. It keeps the empty-store outcome and ends the split between what Home ranks and what it asks.
- Findings: UX-021, UX-050, UX-129

### D214 / D250: Sales is a gross-revenue retrospective (D214); unsold stock reaches #/revenue (D250)
- Premise that no longer holds: Drawing every product name verbatim is fine (D214 measured 539 names). 'On the shelf' can follow the product table (D250 measured on an empty store).
- Evidence: VIS-02: live rows lead with a 50-character catalog prefix. VIS-11: 562 rows, a 30,598 px page, 'Value my stock' at the very end. COPY-31: D250's control uses different period words. LOOP-03, LOOP-04: Sales' 'sold' disagrees with Home and Orders.
- What it protected: A searchable, honest retrospective and a stock valuation on one screen.
- Options:
  - A. Lead rows with the card name, cap the table (top N + show all), and put 'On the shelf' above it or on its own tab.
  - B. Move 'On the shelf' to its own route.
  - C. Keep as is and add a jump link.
- Recommendation: A. Both premises were measured on data that the live store does not match.
- Findings: UX-019, UX-029, UX-034, UX-110, UX-113

### D61: The shipping lane is three lanes, and the third answer is 'I cannot tell'
- Premise that no longer holds: Lanes ordered by type, open by default, with a reason, a quality word and a weight on each card.
- Evidence: LOOP-24, ACC-19: on a phone the 'Needs a look' lane, the only one that asks the owner, starts at y = 32,257 of 37,150 px. COPY-07, COPY-10, TXT-03, TXT-04: the reason code, 'Inferred'/'Certain' and '0.0700 oz/item' repeat on hundreds of cards.
- What it protected: The owner can check which cards were routed on weak evidence.
- Options:
  - A. 'Needs a look' first; lanes after it open collapsed with counts; per-card evidence only where it differs from the lane rule.
  - B. Keep the order and collapse all lanes on a phone.
  - C. Keep as is.
- Recommendation: A. It keeps D61's evidence where it is evidence and puts the decision lane where the thumb is.
- Findings: UX-005, UX-016, UX-063, UX-064

### D142: The setup outlives the browser, and the box list is ordered by the hand
- Premise that no longer holds: Capture's box is a fact about the device, separate from what the store says.
- Evidence: COH-25, LOOP-05: Home names 'Box 4, Mixed Singles' from the store and Capture opens with 'No box yet' from the device. COH-11: Capture and Inventory order boxes by hand, Home and Cards to pull by number. INT-17: the Capture half of the destructive-press patterns.
- What it protected: A shift resumes where the device left off, with no server round trip.
- Options:
  - A. When the device has no setup, Capture adopts the box Home names (store's last capture box).
  - B. Home names the device's box, or no box.
  - C. Keep both and label the Home tile 'last box captured'.
- Recommendation: A. It keeps D142's device memory and removes the two-answer moment on every cold start.
- Findings: UX-011, UX-079, UX-099

### D156: Every copy TCGplayer does not hold is one worklist, and a run stays open until the last copy has gone
- Premise that no longer holds: An open run can keep the status 'Needs pricing'.
- Evidence: COH-06, COPY-05, LOOP-20: the run waits on the write, Pricing says 'Pricing is answered', Home says '2 runs to price'. COH-26: Home's tile opens Pricing scoped to one run, against D156's own 'one worklist'.
- What it protected: No unsent copy is forgotten.
- Options:
  - A. Name the run's real next step ('Ready to write') on Runs and Home, and open Pricing on every unsent copy from Home.
  - B. Keep the chip and change only the Home tile words.
- Recommendation: A.
- Findings: UX-006, UX-078

### D95: The shell is a rail, a palette and a reference sheet
- Premise that no longer holds: A palette of screens and verbs, labelled Search, and a phone bar with four routes are enough to move around.
- Evidence: LOOP-15: 'Search' cannot find a card. INT-30, COPY-25: the palette omits off-nav routes. ACC-09, COH-28: no tab is lit on eight phone screens. ACC-04, INT-06: the drawer and palette do not hold focus.
- What it protected: One small, keyboard-first shell.
- Options:
  - A. Relabel the palette ('Go to' / 'Commands') or teach it cards; list off-nav routes; light 'More' for screens behind it; make the drawer and palette modal.
  - B. Keep the label and add card search to the palette.
- Recommendation: A now; B is a feature and needs its own decision.
- Findings: UX-003, UX-014, UX-022, UX-046, UX-090

### D204: The phone drawer's nav scrolls in the space above its foot
- Premise that no longer holds: Being tappable after a scroll is enough.
- Evidence: ACC-05: at 390 Graveyard and Codes sit under the foot with only a 32 px fade; the Library group looks complete with one row.
- What it protected: Any row count fits.
- Options:
  - A. A visible 'more below' cue or a shorter foot so every row shows at 390x844.
  - B. Move the foot items into the list.
- Recommendation: A.
- Findings: UX-037

### D197: A page is anchored to the shell's inset, and only its width may vary by screen
- Premise that no longer holds: A pricing table and a three-column screen legitimately want different caps.
- Evidence: VIS-15: three maximums (1120, 1344, 1600); at 1440 Pricing's right edge stops 84 px short of others. VIS-14: the top inset varies, which D197 does not cover.
- What it protected: One left edge.
- Options:
  - A. Two widths at most, and one top inset.
  - B. Keep, and add the top inset only.
- Recommendation: B unless the owner sees the right-edge move; it is S4.
- Findings: UX-133, UX-144

### D180 / D153: A press names the cards it is over (D180); the restore asks which drawer (D153)
- Premise that no longer holds: The decisions' prose word 'drawer' and D180's measurement ('2,535 cards') are internal.
- Evidence: COPY-11, LOOP-22: 'Drawers', 'Whole drawer' and 'shelf' reached the Identify and rebind sheets. COPY-32, LOOP-17, TXT-22: '2,535 cards' is typed into the sheet as a fact.
- What it protected: A press that states its scope.
- Options:
  - A. Use 'box' on screen and read the live count.
  - B. Keep 'drawer' and add it to a glossary.
- Recommendation: A.
- Findings: UX-010, UX-018

### D105 / D99 / D87: The markdown lives where prices are decided (D105); one press writes one spreadsheet (D99); the reconcile is store-wide (D87)
- Premise that no longer holds: Moving the write to Pricing and adding a store-wide reconcile needed no change to Runs.
- Evidence: LOOP-11: the file is written on Pricing and its next steps are on Runs step 4. LOOP-18, COPY-06: the markdown sheet kept a `reconcile --live` command. LOOP-19: two presses called 'Reconcile'. TXT-24: the reconcile sheet opens with 44 words.
- What it protected: Prices are decided and written in one place.
- Options:
  - A. Pricing's success state shows the upload and compare steps with a link; rename the per-run reconcile ('Check the staged file'); link the store reconcile from the markdown sheet.
  - B. Move the per-run compare to Pricing.
- Recommendation: A.
- Findings: UX-017, UX-031, UX-102, UX-121

### D62: The price history is drawn beside the hold, not beside the location
- Premise that no longer holds: History belongs on Pricing only.
- Evidence: COH-04: three unlinked history views (Pricing drawer, Sales row, Product page). COH-07: no history on Inventory removes a card link. COH-19: the drawer opens from the left, unlike every other sheet.
- What it protected: Price history is at hand where a price is decided.
- Options:
  - A. One history view per SKU, opened from Pricing, Sales and Inventory alike.
  - B. Keep, and only add links.
- Recommendation: A, with D227 option A as the first step.
- Findings: UX-027, UX-028, UX-057

### D5 / D68: Two personas (D5); a departed label names the record (D68)
- Premise that no longer holds: The Fulfiller's screen can reuse owner labels, and needs no shell.
- Evidence: COPY-15, TXT-43: a sold card shows 'departed B1 #19' in the Fulfiller's list. INT-24: the listed '/' key is dead and '?' cannot open. TXT-42: 'Box 1 · Section 1' repeats on 35 rows (D5 is the counter-argument). The S1 (Cards to pull says nothing waits) lands on this persona.
- What it protected: A self-evident screen with no way out for the Fulfiller.
- Options:
  - A. Filter departed cards out of the Fulfiller's lists and drop the '/' row from its shortcuts.
  - B. Give the Fulfiller its own label set.
- Recommendation: A.
- Findings: UX-013, UX-089, UX-101

### D137: The catalog is Near Mint by rule
- Premise that no longer holds: Condition is worth showing on each row.
- Evidence: TXT-07: all 30 Pricing rows say 'Near Mint'; by rule the label cannot differ.
- What it protected: Condition is explicit.
- Options:
  - A. Hide the condition when it is the rule; keep 'Foil'.
  - B. Keep.
- Recommendation: A.
- Findings: UX-084

### D100 / D168 / D134 / D70 / D102 / D86: Decisions printed as copy
- Premise that no longer holds: A decision's argument helps the owner when restated on screen.
- Evidence: TXT-13 (D100's 52-word age note), TXT-14 (D168's clear rule), TXT-38 (D134's 'Read-only'), TXT-39 (D70's 'the QR is the code'), TXT-44 (D102's sweep history on the Kit), TXT-20 (D86's 'now' migration note), COPY-26 and TXT-40 (D227's 'never guesses').
- What it protected: The owner is not misled (for example, reading a proxy age as real).
- Options:
  - A. One sentence per outcome the decision protects, the rest behind an info control or in the spec.
  - B. Keep.
- Recommendation: A. Each outcome survives in one line.
- Findings: UX-065, UX-120, UX-124, UX-160, UX-162, UX-163

## Held-screen notes

Main state, re-check after merge. Not graded. Where a note is the same defect as a ranked finding, it says so.

### `#/orders`
- Buyers show as order-style names ('09-03-26_00012') while the subtitle says '7 buyers' and the search 'Search buyers'. No buyer name shows (demo data; check live). (COH held, COPY held)
- The stage strip says 'Shipping · No export' until #/shipping is visited, then '331 orders'; Home's Shipping tile changes the same way. Probably demo seeding (see Demo coverage). (COH held, LOOP held, COPY-44)
- Every order draws the demo's `demo_read_only` refusal as unstyled body text under '0 sections'; no pull list appears (walk-plan write refused on the demo). (COH held, LOOP held)
- With a buyer picked, the right pane holds only 'Why each line answered as it did', an empty pane at 1440. (LOOP held)
- At 390 the buyer sheet has no side gutter; filters and search sit flush left and are narrower than the sheet. (LOOP held)
- Stepping in by ⌘→ or any Home link selects a buyer, writes `?buyer=…` and shows 'Showing only the copies this order was offered — not every copy in the store'. Arrival is never neutral; the sentence explains a mechanism. (INT held, COPY held, TXT held)
- Raw enum codes in mono in the 'why each line answered' legend: `no_copies_on_hand`, `sku_unknown`, `sku_unseen`, `not_a_single` (T4). Order ids 11 px at 3.64:1; 'Short' pill 3.84:1 at 10 px. (VIS held)
- 'A run priced this card and no record carries the SKU' with 'Not asked on this screen; always 0.' A row that is always 0 need not show. Other strings: 'Hide never-seen SKUs', 'owed / sold / short', 'Every copy found (15)' beside 'Ready to ship (5)', 'Tick shown / Untick shown'. (TXT held, COPY held)
- 'Sold' here means pulled, and Sales counts the same order as sold (UX finding on 'Sold', LOOP-04).
- Row checkboxes and `.bn-select` filters draw 1.41:1 edges (ACC-12). At 360 the last list item's bottom edge measured 758 px on a 740 px page; check it is reachable above the tab bar. Stage tabs 138x40 and 166x40 sit 4 px apart. (ACC held)
- The filter select and search show focus as a tint ring with no outline; consistent with Pricing and Product. Noted only. (INT held)

### `#/inventory`
- Three box forms on one screen: rail name only in recency order, panel 'BOX 1 / RB Origins', phone picker 'Box 1 (RB Origins)'. (COH held; UX finding on box labels)
- Header chip '122 cards · 4 boxes' (mono) beside a box panel of '34 on hand'; '42 captured' where Home says 'photographed'. (COH, COPY, VIS held; UX card counts)
- Five position forms on one screen: '#1', 'CARD 1', 'card 1 of 11 slots', '#1 of 34', 'Box 1 · Section 1 · Card 1'. (COH held; UX place-of-card)
- Card panel shows 'SKU 9027170' as text and 'Market could not be read', with no link to Pricing, price history or Product history. (COH held; UX product door, card links)
- After Mark sold, the box panel and the Manage sheet still read 15 on hand, 2 sold; after nav away and back the sold card reads 'Identified' with Mark sold offered again. May be demo replay. (LOOP held)
- Sale and retire toasts say the copy 'cannot be put back from here (sold_origin_unknown)': no undo on the press that loses a card, and a code in the toast. May be demo-only. (LOOP held)
- After the sale, '1 live on TCGplayer' stays red with no next step for the live listing. (LOOP held)
- The subtitle says 'Sell, retire or move a copy from here'; the card has Mark sold and Retire only; Move is Manage box > Move to box over ticked cards. (LOOP held, TXT held)
- The Retire dialog prints enum codes (`pulled`, `damaged`, `lost`, `given_away`) under each label. (LOOP held)
- At 390 Mark sold sits at y = 1,069, below the fold. (LOOP held)
- The missing-photo state prints a raw URL in mono and a 23-word sentence that repeats the address. (VIS held, TXT held)
- 'Run box 1' and 'Nothing running' reuse 'run' (COPY held). Box-number chips are black on Home and white on Cards to pull (VIS held).
- The search field puts its ring on the wrapper, same as Sales. Consistent. Noted only. (INT held)
- The live dot is where the reduced-motion pulse was measured (ACC-16). Rail rows: 33-34 nodes at 3.63:1, 11 px. Row checkboxes 1.41:1. (ACC held)

### `#/review`
- Its address pill is the only card-to-card link in the app: the pattern other screens lack. Keep it. (COH held)
- Candidate prices have no label and use Manrope 18/800; the 'NEXT' price uses Inter: a third money face. (COH, VIS held)
- The card name is drawn in JetBrains Mono 12.6 px/600. The position strip 'BOX / SECTION / CARD' is 2.80:1 in light and reads 'BOX 1SECTION 3CARD13' as text. (VIS, COPY held)
- A missing photo prints its file path under 'The file is not on disk'; the 18-word notice says 'The card is still at its slot'. (LOOP, COPY, TXT held)
- Reason names and actions use pipeline words: 'Two rows, one condition', 'Nothing decided the finish', 'Not in the export', 'Search the export', 'This read — what the run recorded'. (COPY held)
- 'Box 1 · Section 3 · Card 13' shows twice (details list and position label). (TXT held)
- Reload is disabled and spins; with Pricing it is the only screen that does (UX reload finding). (INT held)
- At 390 the reason chips measured 28 px then 40 px tall on two runs; the chips after the second scroll sideways. 'Next' label 2.81:1. (ACC held)
- The answered count carried to Home on return (9 to 8). Positive. (LOOP held)

### shell (ring)
- The ⌘→ ring stops at Codes and does not wrap; ⌘← on Home does nothing. (INT held-notes)

## Demo coverage

Gaps in the demo's recording or seeding, not product defects. Each blocks a check; fix the recording (`make demo-record`) or re-check on a live store.

| Gap | Sources | What it hid |
|---|---|---|
| Graveyard list | LOOP-13, COH could-not-check, VIS could-not-check, COPY could-not-check, ACC could-not-check, TXT could-not-check | `GET /graveyard` has no recording, so the demo draws only the error ('could not be read … Rebuild it with `make demo`'). LOOP graded Graveyard F for this; visual graded it from the live look. The live list has its own S2 (Graveyard overflow). |
| `#/product` data | LOOP-13, INT-08 (part), COPY could-not-check, TXT could-not-check | No SKU has a recorded history (9027180, 9189757, 8937200 tried), so the chart and sale markers were never seen. |
| Inventory search | LOOP-13 | Search 'Crowd Favorite' on #/inventory is not recorded, so the 'find it again' side loop has no working path on the demo. |
| Pricing price-history sheet | LOOP-13, COH could-not-check, COPY could-not-check | The history sheet's contents are not recorded. |
| Orders walk plan and pull list | LOOP held-notes, LOOP could-not-check | The walk-plan write is refused, so no pull list draws on Orders and the pull stage could not be walked end to end (presses, carry to Shipping and Sales). |
| Sales 'Value my stock' and 'Compare to today's market' | COH could-not-check, COPY could-not-check, INT-08 (part) | Both are refused or unrecorded; On the shelf was seen only live and only as a position (VIS-11). |
| Demo photographs 404 | LOOP-34 | `/banchi/demo/photos/…` returns 404 on Capture's recent strip, Pricing thumbs, Inventory and Review. The loop is 'photo first' and the demo shows none. The four missing-photo drawings are a product finding (COH-14). |
| Home box rows after a sale | LOOP-09 | After Mark sold, Home's summary moved (99 on hand, 1,448 sold) and Box 4's row stayed '15 on hand, 2 sold'. The demo recomputes `/status` and replays `/boxes`, so this may be demo replay. Re-check on a live store before treating it as a product defect. |
| Shipping file state on Home and Orders | COPY-44, COH held-notes | Shipping shows 'export.csv, 331 orders' at once, while Home says 'no export read yet' and Orders 'Shipping · No export' until Shipping is visited. The demo loads the export on arrival at Shipping. Unknown for the live app; re-check live. |
| Demo refusal text | TXT-46 (part), INT-08 (part) | The 36-word Identify refusal draws twice (banner and side pane), and demo text names `make demo` and request paths. The text is the demo's; how the notice prints it is the product finding on error text. |
| Fulfillment search | COPY-43, INT-31 | Whether the demo refuses search is unknown, so search results and the pull view of a card were never seen. The remedy sentence is a product finding. |

## What no lens could check

- The owner's live store, except VIS's read-only look at Sales, Runs, Graveyard, Cards to pull and Codes at 1440 (10 GET-only loads). Home, Pricing, Shipping, Orders, Inventory, Review and Capture at real density are unknown; they send POSTs on mount or are held. Pricing is the likeliest to show more. (VIS, TXT, LOOP)
- Real-server writes and their success states: identify cost, emit (Pricing after 'Write the import file'), live reconcile, live export, order fetch, capture, code scan, Fill pick locations, Shipping Forget's undo. Only how each refusal draws was graded. (all lenses)
- The pull stage end to end: no pull list drew on the demo. (LOOP)
- Whether LOOP-09, the held Inventory count drift, and the Shipping file state are product or demo. (LOOP, COH)
- Codes with codes on file (dormant, empty store), and Capture with a live camera, the motion trigger and its readout. (COH, COPY, INT)
- Dark theme: interaction measured states on 8 routes only and shot overlays in light only; copy did not extract dark; density did not read every dark shot. Light-theme contrast of Capture's camera lamps (1.03-2.25:1) is probably false (background image) and was left out. (INT, COPY, TXT, VIS)
- 820 px: loop, interaction and access ran no presses or a11y pass at 820; ACC-04 probably holds at 820 (unknown). (LOOP, INT, ACC)
- Widths above 1440: VIS-15's three page maximums are measured from CSS, not seen. (VIS)
- Hover, focus and pressed states outside the interaction lens. (COH, VIS)
- Touch gestures (press-and-hold T, swipe), a real phone (iOS safe-area insets, on-screen keyboard, pinch zoom), browser zoom to 200% and text-only zoom. (INT, ACC)
- Screen-reader speech: ARIA and DOM focus were read, not what VoiceOver or TalkBack says. (INT, ACC)
- Focus order after the first 30 Tab stops per route; sheets on the held screens (Manage box, Review close); the dark drawer at 360. (ACC)
- Toasts and receipts from real writes, and their word counts; only the Release receipt was reached. (COPY, TXT)
- Tooltips read as `title` attributes, not shown on hover (COPY-23, COPY-34). (COPY)
- The rule behind the 'Needs pricing' badge was read from its tooltip ('3 of 6 stages done'), not from code. (COPY)
- `prefers-reduced-motion` in the interaction lens (the access lens measured it, ACC-16). (INT)
- The live Shipping export count, so the real size of the Shipping word findings is unknown. (TXT)
