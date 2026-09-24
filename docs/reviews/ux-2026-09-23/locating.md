# Locating a card: how fast the owner knows where it is

Reviewed on the integration branch `claude/integration-photo-issues` at
`c60d53ef8430bcbfe3ba925e7e584044db188feb`, built with `make demo-static` (own store under
LOC scratch file, not kept) and served by `make demo-preview` on port 4173. Every finding below is
"reviewed on the integration branch at c60d53ef" unless it says "main state".

Widths 1440, 720 and 390, light and dark. Shots: LOC screenshot, not kept. Data: LOC scratch file, not kept.
Scripts: LOC scratch file, not kept.

**Demo limits that shape this lens.** The branch's demo has NO card photographs. The
recorder copied 0 photographs: it reads `captures/cards/box*/`, and the seed now writes
`photos/<xx>/<sha>.jpg`. The published main demo has the same gap. The order walk
(`POST /orders/walk-plan`), `#/graveyard`, `#/pricing?band=top` and `#/product?sku=` have no
recorded answer in either demo. Search on `#/fulfillment` fails ("The search did not
finish"). A sale in the demo does not change the recorded box. See "What I could not check".

## Grade matrix

Grades are for THIS lens only: can the owner tell where a card is, fast, and the same way
everywhere.

| Route | Grade | One-line reason |
|---|---|---|
| `#/` Home | C | Box level only, which is right. But boxes are numbered tiles here and unnumbered names on Inventory, in a different order. |
| `#/capture` | D | The recent tile says `B4 #18` for the card Inventory calls `#15`. `next index 19` shows three times. No section. |
| `#/runs` | n/a | Draws no card position in the states I reached. Not graded. |
| `#/review` | C | One 12px pill (`BOX 1 SECTION 3 CARD 13`) with no box name and no neighbours. Its link opens the box at card #1, not the card. |
| `#/pricing` | D | No row shows where the card is. Position shows only after a press on the 36x48 thumbnail, as a grey caption. |
| `#/orders` | Unknown | The demo refuses the walk. The screen shows no card position at all. Code draws section groups, unseen. |
| `#/shipping` | n/a | No card position drawn. Not graded. |
| `#/revenue` | n/a | No card position drawn. Not graded. |
| `#/inventory` | C | The richest answer (box, section, card, before/after, ruler). But three number scales on one panel, a caret that points at the wrong slot, no front/back, and below the fold at 390. |
| `#/graveyard` | Unknown | "The graveyard could not be read" in both demos. Code spells a place as the store key `B9 #3`. |
| `#/codes` | n/a | Code cards are pooled, with no position by design. Not graded. |
| `#/fulfillment` | F | Offers a departed card with "Pull this card" and "It sits between…". Says no orders are waiting while 7 are open. "Card 1" and "Card 12 of 34" on one panel. |
| `#/gallery` | B | The kit draws the position parts. Its bar caption (`#40 of 250 · 16% in`) is richer than the live one. |
| `#/product` | Unknown | Not recorded in either demo. |

## Time to "I know where to reach"

Method: I read each screenshot as the owner would and counted the reads needed. A read is
one label or number the eye must stop on. Seconds are MY ESTIMATES from those reads, not a
timed user study. Five cards per screen where the screen draws positions.

| Screen | Cards tried | Est. seconds | What carries the answer | What is only text |
|---|---|---|---|---|
| Inventory 1440 | B1 #1, #6, #11 (sec 1). #1 sec 2 (Double Trouble). B4 #5 (Buneary) | 3-4 each | Big `CARD n` numeral. The 26px section ruler | Box (12px `BOX RB Origins Box 1`), section (12px), before/after names, `#n of 34` (12px grey) |
| Inventory 720 | same | 5-7 each | Ruler. `1/34` in the box picker | Everything else. The list is gone, and the panel needs one scroll |
| Inventory 390 | same | 7-9 each, plus a scroll | Only the `1 / 34` pager is above the fold | Section, neighbours and ruler all start at y=1005 on an 844 fold |
| Cards to pull 1440/390 | Double Trouble, Piercing Light, Gentle Gemdragon, Bellows Breath, Ashe (departed) | About 2 each. Ashe: never (it is not there) | One large line `Box 1 · Section 2 · Card 1`. Section chips | `It sits between…`, `Card 12 of 34` |
| Review 1440/390 | Draven (box 1, section 3, card 13), and the 8 others with Skip (same pill) | 2-3 | The pill numerals | Box by number only. No neighbours. No box name |
| Pricing 1440 | Premonition, Public Execution, Mel, Akali, Progress Day | 5-6 each, with a press | Nothing on the row | 12px grey caption in the photo drawer |
| Capture 1440 | B4 #18 (the one recent tile) | Cannot. The tile's number is not the card's number on any other screen | `B4 #18` badge | none |
| Home | box level only | 1-2 for a box | Numbered box tiles | Box names |
| Orders | none reachable in the demo | unknown | — | — |

## Position vocabulary

| Screen | How a position is shown | What it leaves out |
|---|---|---|
| Home `#/` | Box: numbered black tile and name (`1 RB Origins`), in number order. Hero pin `Box 4 · Mixed Singles` | Section, card. The rail order Inventory uses |
| Capture `#/capture` | Recent tile badge `B4 #18` (store key). `next index 19` in the box picker, the stats strip and the camera foot. `index span` | Section. The counted number. The box name on the tile |
| Review `#/review` | Pill on the photo foot: `BOX 1  SECTION 3  CARD 13 →` (12px caps, 15px numeral). The header `Card 1 of 9` is the QUEUE position | Box name, section name, neighbours, how far in, front/back |
| Pricing `#/pricing` | Nothing on the row. Photo drawer caption: `Box 3 · Section 3 · Card 2 · 1 of 1` (12px grey) | Everything until a press. `1 of 1` is a copy count next to the card number |
| Inventory `#/inventory` list | `#1…#11` per SECTION. Departed rows `B1 #4` (store key) at the section's end, dimmed, with an external-link icon | Box-wide number. Where a departed card stood |
| Inventory copy panel | `CARD 1` (section count, 28px). `BOX RB Origins Box 1` (name first). `SECTION 2 Uncommons`. `AFTER x / BEFORE y`. Ruler with end labels `12 … 21` (BOX count) and caption `card 1 of 10 slots` (section count). Box strip of section chips with a caret and a marker. `#12 of 34` (box count, 12px grey) | Front/back. Which end is 1 |
| Inventory box card | `BOX 1 / RB Origins`. A second box strip with a dot at the walk's place | Nothing, but it is a third position instrument on one screen |
| Inventory 720/390 | Box picker `Box 1 (RB Origins)  1/34`. Pager `1 / 34` | Section and neighbours above the fold |
| Cards to pull list | `Box 1 · Section 1 · Card 1` per row, large | Box-wide count. Departed rows mixed in as `Box 1 · departed · B1 #19` |
| Cards to pull card | `Box 1 · Section 2 · Card 1` (30px). `The box is labelled RB Origins.` `Card 12 of 34` and section chips with a marker. `It sits between A and B.` | Front/back |
| Orders walk | Not seen (the demo refuses it). Code: section groups like the Inventory list | Unknown |
| Graveyard | Not seen. Code: `B9 #3` store key | Unknown |
| Product | Not seen | Unknown |
| Kit `#/gallery` | `Box 2 · Section 1 · Card 14`. Bar caption `#40 of 250 · 16% in` | — |

Three things share one glyph. `#1` is the card in its section (Inventory list). `#12 of 34`
is the card in its box (Inventory panel). `B1 #4` is the store key (departed rows, Capture
tile). "Card" names three counts: in section (`CARD 1`, Fulfiller `Card 1`), in box
(Fulfiller `Card 12 of 34`), and queue place (Review `Card 1 of 9`). No screen says which end
of the box is card 1.

## Icon legend

Colours are computed values at 1440 (light / dark).

| Icon or badge | Where | Its meaning there | Text label or tooltip | Light / dark colour |
|---|---|---|---|---|
| `Identified` outline pill | Inventory hero, under the card name | A run read the card | Text | grey text `#3B414B` on transparent / `#B9BFC9` on transparent |
| `Identified` filled pill and eye icon | Inventory copy row | Same state again. The eye is "Viewing" | Text. The eye's word is hidden | `#3B414B` on `#ECEEF2` / `#B9BFC9` on `#090B0E` |
| Eye in a circle | Inventory copy row | "Viewing" (this copy is the one on screen) | Visually hidden "Viewing" | grey outline |
| `Captured` pill | Inventory hero and copy row | Photographed, not read yet | Text | accent `#3D5AF1` on 10% accent / `#7F90FF` |
| `Not identified yet` (dimmed name) | Inventory list, hero | Same captured state, as a name | Text | muted grey |
| `Sold` pill | Inventory copy row (departed or just sold) | The card left by sale | Text | green `#15803D` on 12% green / `#3DDC84` |
| `Retired` pill | Inventory copy row | Card retired | Text | amber (warn tone) |
| `Moved` | Inventory box stats (`1 moved`) | Card moved to another box | Text only | none |
| External-link arrow | Inventory list, departed rows | The card left the box (sold, retired or moved alike) | `aria-hidden`, no title | grey `#7F8791` / `#707886` |
| External-link arrow | Sidebar `Cards to pull` | Opens in a new tab | Row text | grey |
| Clock | Inventory list rows | "Waiting in a queue" | `title` only, no accessible name | grey |
| Lock (closed), no text | Inventory rail, beside RB Epics | Box is sealed | None | grey |
| Lock (open) and `open` pill | Inventory box card | Box is open | Text | green |
| `sealed` word | Home box list | Box is sealed | Text | grey |
| Red dot and red numeral | Inventory `0 live on TCGplayer` | Live listing count | Text below | `#D63D2B` / `#FF6A58` |
| Grey dot | Pricing `0 live` in rows | Live count, same meaning | Text | `#7F8791` / `#707886` |
| Green dot | Sidebar foot `Server online`. Orders buyer rows | Server up. Order Ready | Text in the foot. None on the order dot | `#15803D` / `#3DDC84` |
| Amber dot and `Short` pill | Orders buyer rows | Order is short of copies | Pill text | `#B45309` / `#F5A524` |
| `Needs pricing` pill | Home recent runs, Runs | Run needs prices | Text | accent blue |
| `Typed`, `On the rule`, `At the $0.49 cut-off`, `Held` | Pricing rows | Price source | Text and title | green / grey |
| `Saved`, `Written` pills | Pricing | Autosave, policy written | Text | green |
| Green check badge | Cards to pull | "No orders are waiting" | Sentence | green |
| Caret (triangle) on a section chip | Inventory panel, box strip | Which section holds the card | None | accent |
| Blue marker bar | Inventory ruler, box strip, box card strip. Cards to pull chips | The card's place | None | accent |
| Pin | Home hero, Review pill, Pricing caption, Cards to pull | "A place follows" | None | accent / grey |

Found:
- **One meaning, two icons.** Identified shows twice per card in two styles. Sealed is a
  bare lock on Inventory and the word `sealed` on Home. "Live" is a red dot on Inventory and
  a grey dot on Pricing.
- **One icon, two meanings.** The external-link arrow (departed row / new tab). Green (sold
  and gone / ready, saved, online, open). Accent blue (captured / needs pricing / counts /
  links). Red (live listing / "Cannot be filled").
- **On every row, so no information.** `Identified`, twice, on nearly every card. The eye on
  a card with one copy. `Near Mint` on every row (kept by owner ruling, not a finding).
- **No accessible name.** The departed-row arrow (`aria-hidden`). The clock (`title` only).
  The rail lock. The Orders buyer dots. Every position marker and caret.
- **No icon where one would help the hand.** "First card" and "last card" in a section or a
  box, the hand's two landmarks. "Front of the box". A departed card on the Fulfiller's
  screen.

## Findings

### LOC-01 Cards to pull offers a card that is not in the box
- Severity: S1
- Screens: `#/fulfillment`
- Where: all
- Repro: `#/fulfillment` → tap `Box 1 · RB Origins` → tap `Ashe, Focused`.
- Seen: The list row reads `Box 1 · departed · B1 #19` between two live cards. The card page
  says "No longer in the box". Then it says "It sits between Relentless Pursuit and Punch
  First" and "The photo is missing. The card is still in the place shown here." A black
  `Pull this card` button follows. The Fulfiller will search the slot for a card that is
  gone.
- Shot: LOC-01, screenshot not kept.
  `ful-row-Ashe-1440-light.png`
- Direction: A departed card never appears on the Fulfiller's list or card page. If it must
  appear, it says only "This card has left the box" and offers no pull.
- Component: `Fulfillment.tsx` box list. `CardLocations.tsx` `FulfillerCard`. `PositionBar.tsx`.
- Annotation: violates D58 (a card's number counts cards, not slots). D58 says a departed
  card is in no slot, because an answer "would send a person to the wrong slot". The card
  page does exactly that. Caused by D68 (a departed label names the record) for the row
  label, which reaches the Fulfiller unchanged. This round: CONSOLIDATED UX-013 logs the row.
  The card page ("Pull this card", "It sits between") is new here. No prior in ux-2026-09-20.

### LOC-02 Cards to pull says no order waits while seven are open
- Severity: S1
- Screens: `#/fulfillment`, `#/`, `#/orders`
- Where: all
- Repro: open `#/`. It reads "6 copies for 7 open orders cannot be found" and "27 copies to
  pull". Then open `#/fulfillment`.
- Seen: `#/fulfillment` shows a green check and "No orders are waiting for a card right now."
  Orders shows 7 open orders and 21 lines. The Fulfiller's one job reads as done.
- Shot: LOC-02, screenshot not kept.
- Direction: The Fulfiller's screen and Home agree on how many cards are owed. Each owed line
  shows where every copy is.
- Component: `Fulfillment.tsx` (`waiting` keeps order groups with `cards.length > 0`).
- Annotation: caused by D212 (no order claims a copy). The Fulfiller's list is built from
  claimed copies, and D212 removed the claims, so every group is empty. The owner's ruling
  (RULINGS, "D212 pull list") already calls this built wrong by outcome. This round:
  CONSOLIDATED UX-001. prior: ux-2026-09-20/fulfillment.md saw this state as a normal empty
  landing.

### LOC-03 "#" and "Card" each name two or three different counts
- Severity: S2
- Screens: `#/inventory`, `#/fulfillment`, `#/review`, `#/capture`
- Where: all
- Repro: `#/inventory?box=1`, press → 11 times (Double Trouble).
- Seen: The list row says `#1` (card in section). The panel says `CARD 1` and `#12 of 34`
  (card in box). Departed rows say `B1 #4` (store key). Cards to pull draws `Card 1` and
  `Card 12 of 34` on one panel. Review's header says `Card 1 of 9` (queue place) above a pill
  that says `CARD 13`. The owner must know which count each "#" and each "Card" is.
- Shot: LOC-03, screenshot not kept.
  `review-1440-light.png`
- Direction: One word and one glyph per count, the same on every screen. The count the hand
  uses is the big one. The other count gets a different name ("12th of 34 in the box").
- Component: `BoxBrowse.tsx` rows. `CardLocations.tsx`. `PositionBar.tsx`. `ReviewQueue.tsx`.
- Annotation: violates D92 (a bare # is the count, the key carries a sigil). D92 gave the
  bare `#` to the box count so that one `#` never names two cards on one screen. The list's
  per-section `#1` names three cards in box 1. This round: CONSOLIDATED UX-012. No prior in
  ux-2026-09-20.

### LOC-04 The section ruler mixes two scales
- Severity: S2
- Screens: `#/inventory`
- Where: all
- Repro: `#/inventory?box=1`, press → 11 times.
- Seen: The ruler's end labels read `12` and `21` (box count). Its caption reads
  `card 1 of 10 slots`, and the numeral reads `CARD 1` (section count). One instrument shows
  two scales.
- Shot: LOC-04, screenshot not kept.
- Direction: The ruler's labels use the same count as its caption and the big numeral.
- Component: `PositionBar.tsx`.
- Annotation: caused by D155 (the section is the ruler). D155 writes "the section's own
  bounds" inside the ruler's two ends, and those bounds are box counts. The caption beside
  them is a section count. The decision is an argument here, not a defence. No prior.

### LOC-05 The box-strip caret points at the wrong slot
- Severity: S2
- Screens: `#/inventory`
- Where: all
- Repro: `#/inventory?box=1` (card 1). Then `#/inventory?box=4`, pick `Buneary`.
- Seen: The caret sits at the MIDDLE of the section's chip and points up into the ruler. On
  card 1 it points at ruler slot 2-3 while the marker sits at slot 1. On a one-section box
  (box 4) it sits at the box's middle for every card. Two marks on one strip disagree.
- Shot: LOC-05, screenshot not kept.
- Direction: One mark per scale, and each mark sits over the card.
- Component: `PositionBar.tsx` (box strip caret).
- Annotation: caused by D155 (the section is the ruler). D155 specifies "a caret on the chip
  the card is in", so the caret marks the chip, not the card. On a one-section box it carries
  no information. No prior.

### LOC-06 No screen says which end of the box is card 1
- Severity: S2
- Screens: `#/inventory`, `#/fulfillment`, `#/review`, `#/pricing`
- Where: all
- Repro: any card on those screens.
- Seen: The ruler runs 1 → N left to right. No label says "front" or "back". No on-screen
  string names the front or back of a box. I measured this over the `app/src` strings and
  saw it on no screen. For card 30 of 34, the hand can count 30 from the front when 5 from
  the back is faster. It can also count from the wrong end.
- Shot: LOC-06, screenshot not kept.
- Direction: Name the end where card 1 sits, once, on the instrument ("front" under the 1).
  For a card past the middle, say "5 from the back" beside the number.
- Component: `PositionBar.tsx`.
- Annotation: no decision covers this. No entry in `docs/decisions/` names the front or back
  of a box. No prior.

### LOC-07 AFTER and BEFORE read as the wrong neighbour
- Severity: S2
- Screens: `#/inventory`
- Where: all
- Repro: `#/inventory?box=1`, press → once (Gentle Gemdragon, card 2).
- Seen: The panel reads `AFTER Piercing Light` / `BEFORE Bellows Breath`. As a label beside a
  name, `AFTER Piercing Light` reads "the next card is Piercing Light", which is the
  opposite. Card 1 shows only `BEFORE`, with no "first card" cue. Cards to pull says the same
  fact in another way: "It sits between A and B."
- Shot: LOC-07, screenshot not kept.
- Direction: Draw the three cards as a row in box order (previous · THIS · next), the same on
  every screen. Mark "first in box" and "last in box".
- Component: `PlaceNeighbors.tsx`.
- Annotation: caused by D30 (the physical convention for a gap). D30 removed the
  connectives from the neighbour sentence and made `after` and `before` a key column. As bare
  labels they read as the neighbour's side, not this card's. D116 (a card nobody has named is
  not a landmark) decides which names show. No prior.

### LOC-08 On a phone and at half width the section is below the fold
- Severity: S2
- Screens: `#/inventory`
- Where: 390 and 720, both themes
- Repro: `#/inventory` at 390x844.
- Seen: Above the fold: name, photo, `1/34` in the box picker, pager `1 / 34`. The section,
  neighbours and ruler start at y=1005 (fold 844). At 720 the list is gone and the panel
  starts at y=539. The only position a thumb sees is "1 of 34". The photo's placeholder text
  names the section, but only because the photo is missing.
- Shot: LOC-08, screenshot not kept.
- Direction: At 390 and 720, the box, section and card number sit beside the name, above
  the photo.
- Component: `Inventory.tsx`, `CardLocations.tsx`.
- Annotation: no decision covers this. The owner's ruling on D197 (RULINGS) adds 720 to
  every check. No prior.

### LOC-09 A departed card still claims a place and neighbours
- Severity: S2
- Screens: `#/inventory`
- Where: all
- Repro: `#/inventory?box=4` → `Hide sold` off → pick `Vulpix`, then `Kennen, Storm of
  Shuriken`, then `Raboot`.
- Seen: Sold Vulpix reads `AFTER Buneary BEFORE Garganacl`. Its photo notice says "The card
  is still at Box 4, departed, B4 #6". Kennen and Raboot both read `AFTER Teemo, Scout BEFORE
  Nickit`. Two cards sit "between" the same two cards, and none of the three is there.
- Shot: LOC-09, screenshot not kept.
- Direction: A departed card says where it WAS, in the past tense ("was between…"). It never
  says "is still at".
- Component: `CardLocations.tsx`, `PlaceNeighbors.tsx`, `CardHero.tsx` (missing-photo notice).
- Annotation: violates D58 (a card's number counts cards, not slots) and D68 (a departed
  card's label names the record). D68 calls a slot printed for a departed card "a lie about a
  shelf". Neighbours and "is still at" state a shelf place in the same way. No prior.

### LOC-10 The walk and the list disagree on where departed cards are
- Severity: S2
- Screens: `#/inventory`
- Where: 1440
- Repro: `#/inventory?box=4` → `Hide sold` off → pick `Buneary` (#5) → press →.
- Seen: → goes to `Vulpix (B4 #6)`. The list draws Vulpix at the END of the section, below
  #15. The highlight jumps from row 5 to the list's foot, then back to #6.
- Shot: LOC-10, screenshot not kept.
- Direction: The list and the arrow keys follow one order.
- Component: `BoxBrowse.tsx`.
- Annotation: caused by D132 (sold is folded away by default). With sold shown, departed
  rows sink under the live ones (the chip's title says so). The walk keeps box order. No
  prior.

### LOC-11 After a sale nothing moves, and the card reads "Identified" and "Sold" at once
- Severity: S2
- Screens: `#/inventory`
- Where: 1440 light
- Repro: `#/inventory?box=4` → pick `Buneary` → `Mark sold` → then `re-rank`.
- Seen: The copy row shows `Identified` and a green `Sold` pill together. The hero still
  says `Identified`. `CARD 5` and `#5 of 15` do not change. The box still says `15 on hand`
  and `2 sold`. No neighbour's number changes, also after `re-rank`. Garganacl still reads
  `CARD 6`, `AFTER Buneary`. The owner cannot see the renumbering that the physical box just
  went through. In the demo the sale may not reach the recorded box. The receipt drawing is
  the product's.
- Shot: LOC-11, screenshot not kept.
  `sale-d-garganacl-1440-light.png`, `st-sale-3s-1440-light.png`
- Direction: After a sale, show before → after for the neighbours ("Garganacl is now #5").
  Draw one state per copy.
- Component: `CardLocations.tsx` `OwnerRows`. `BoxBrowse.tsx`.
- Annotation: caused by D181 (the order is taken once) for the frozen list. D58 (a card's
  number counts cards) requires that the card behind takes the number "on every screen". The
  renumbering after `re-rank` is unverified in the demo. The two pills on one copy: no
  decision covers this. This round: CONSOLIDATED held-screen notes log the unchanged counts
  (LOOP). No prior.

### LOC-12 Review's place pill opens the box at card 1, not the card
- Severity: S2
- Screens: `#/review` → `#/inventory`
- Where: all
- Repro: `#/review` → click the pill `BOX 1 SECTION 3 CARD 13 →`.
- Seen: It opens `#/inventory?box=1` on `Piercing Light`, card 1 of section 1. The card is
  Draven, section 3 card 13, and it is not selected. The pill's title reads "Open this box on
  Inventory". Its accessible text is `BOX 1SECTION 3CARD13`, with no spaces.
- Shot: LOC-12, screenshot not kept.
- Direction: A place link opens that card.
- Component: `ReviewQueue.tsx`, `PositionLabel.tsx` (`flow="run"`).
- Annotation: no decision covers this. No prior.

### LOC-13 Pricing rows do not say where the card is
- Severity: S2
- Screens: `#/pricing`
- Where: all
- Repro: `#/pricing` → press the thumbnail on `Premonition`.
- Seen: No row draws a box or section. The drawer caption is 12px grey. It reads
  `Box 3 · Section 3 · Card 2 · 1 of 1`. Here `1 of 1` is a copy count, but it reads as part
  of the card number. The thumbnail is 36x48 (44x60 at 390). That is too small to confirm a
  card.
- Shot: LOC-13, screenshot not kept.
- Direction: Each row carries its place in the shared vocabulary. The copy count gets its own
  label.
- Component: `Pricing.tsx` (photo drawer, `pricing-thumb`).
- Annotation: no decision covers a row's place on Pricing. This round: CONSOLIDATED UX-012
  names the drawer's section count. No prior.

### LOC-14 Capture's recent tile uses a number no other screen uses
- Severity: S2
- Screens: `#/capture`
- Where: all
- Repro: `#/capture` → `Pick a box` → `Mixed Singles`.
- Seen: The tile reads `B4 #18`. Inventory calls the same card `#15`. `next index 19` shows
  in the box picker, the stats strip and the camera foot. `index span` shows beside it. The
  tile shows no section. The owner cannot match the tile to a place.
- Shot: LOC-14, screenshot not kept.
- Direction: The tile shows the counted place (`Section 1 · #15`) that the next screen will
  show.
- Component: `CaptureScreen.tsx` recent strip and stats.
- Annotation: no decision covers the tile. D92 (a bare # is the count) is met, because the
  key carries its `B4` sigil. But the key is not a place the hand can use. D41 (the address is
  a rank) removed "next index" from Inventory as not a statistic. This round: CONSOLIDATED
  UX-052. No prior.

### LOC-15 Box counts disagree between Inventory and Cards to pull
- Severity: S2
- Screens: `#/fulfillment`, `#/inventory`, `#/`
- Where: all
- Repro: compare the `#/fulfillment` box list with `#/inventory` box 1.
- Seen: Cards to pull says `Box 1 · 35 cards` and "101 cards are in 4 boxes". Inventory says
  `34 on hand`, and Home says `100 on hand in 4 boxes`. The extra card is the departed one in
  LOC-01. The card page says `Card 12 of 34` under a `35 cards` header.
- Shot: LOC-15, screenshot not kept.
- Direction: One on-hand count, the same everywhere.
- Component: `Fulfillment.tsx`.
- Annotation: violates D58 (a card's number counts cards). D58 makes the denominator follow
  the cards on hand. Cards to pull counts a departed card. Same cause as LOC-01. No prior.

### LOC-16 A box is named five ways, in two orders
- Severity: S3
- Screens: `#/`, `#/inventory`, `#/fulfillment`, `#/review`, `#/pricing`
- Where: all
- Repro: visit each.
- Seen: Cards to pull and Pricing say `Box 1 · RB Origins`. The Inventory picker at 720/390
  says `Box 1 (RB Origins)`. The Inventory panel says `BOX RB Origins Box 1`, name first.
  Home draws a black `1` tile and `RB Origins`. The Inventory rail shows the name alone, with
  no number. Review shows `BOX 1` with no name. Home lists boxes by number. The Inventory
  rail lists them by recency.
- Shot: LOC-16, screenshot not kept.
  `ful-box1-1440-light-viewport.png`, `review-1440-light.png`
- Direction: One box label shape everywhere (number tile and name), in one order.
- Component: `Home.tsx`, `BoxBrowse.tsx`, `CardLocations.tsx`, `Fulfillment.tsx`, `ReviewQueue.tsx`.
- Annotation: caused by D132 (the address leads with the name, the rail is ordered by the
  hand) on Inventory. Home, Cards to pull and Review did not follow it, so the product now
  carries both conventions. RULINGS (D180/D153) asks for "box" everywhere. No prior.

### LOC-17 "Identified" is on every card, twice, in two styles
- Severity: S3
- Screens: `#/inventory`, `#/gallery`
- Where: all
- Repro: `#/inventory`, any identified card.
- Seen: An outline `Identified` pill sits under the name. A filled grey `Identified` pill
  sits in the copy row. Nearly every card is identified, so the pill tells the hand nothing.
  The owner named this: "the Identified icons, everywhere".
- Shot: LOC-17, screenshot not kept.
- Direction: Show a state only when it is the exception (captured, sold, retired, moved,
  in review), once per card.
- Component: `CardHero.tsx` (`browse-hero-chips`), `CardLocations.tsx` (`card-locations-state`).
- Annotation: no decision covers this. No prior.

### LOC-18 The eye beside "Identified" means "Viewing"
- Severity: S3
- Screens: `#/inventory`
- Where: all
- Repro: `#/inventory`, any card.
- Seen: An eye in a circle sits just left of `Identified`. Its word, "Viewing", is hidden.
  It reads as "identified = seen". On a one-copy card it marks the only row.
- Shot: LOC-18, screenshot not kept.
- Direction: Mark the viewed copy only when there are two or more copies, and not with an eye.
- Component: `CardLocations.tsx`.
- Annotation: no decision covers this. No prior.

### LOC-19 One arrow icon means "left the box" and "opens a new tab"
- Severity: S3
- Screens: `#/inventory`, shell
- Where: 1440
- Repro: `#/inventory` → `Hide sold` off. Compare with the sidebar's `Cards to pull` row.
- Seen: Departed rows carry an external-link arrow (`aria-hidden`, no title). The sidebar
  uses the same arrow for "opens in a new tab". Sold, retired and moved share it.
- Shot: LOC-19, screenshot not kept.
- Direction: A departed row names its state (sold, retired, moved) in words, or with a
  distinct mark that has a name.
- Component: `BoxBrowse.tsx` (`browse-row-badge is-out`).
- Annotation: no decision covers the icon. D58 says a departed label names no door, so the
  label does not say sold or retired. The icon does not say it either. No prior.

### LOC-20 Status colours carry several meanings each
- Severity: S3
- Screens: all
- Where: both themes
- Repro: compare `#/inventory`, `#/orders`, `#/`, `#/pricing`.
- Seen: Green is Sold (the card is gone) and also Ready, open, Saved, Written and online.
  Accent blue is Captured and also Needs pricing, counts and links. Red is "live on
  TCGplayer" (good) and "Cannot be filled" (bad). Amber is Retired/Moved and Short.
- Shot: LOC-20, screenshot not kept.
- Direction: One colour per card state, kept apart from "good/bad".
- Component: `cardState.ts` `stateTone`. Kit pills and dots.
- Annotation: no decision covers this. No prior.

### LOC-21 The section header cuts the name and keeps the count
- Severity: S3
- Screens: `#/inventory`
- Where: 1440
- Repro: `#/inventory?box=1`.
- Seen: `SECTION 2: UNCOM… , 10 CARDS`. The section name is the physical label on the
  divider. The count shows again in the pill beside it. A space before the comma is typed.
- Shot: LOC-21, screenshot not kept.
- Direction: Keep the name whole. Remove the repeated count.
- Component: `BoxBrowse.tsx` section title.
- Annotation: no decision covers the cut. D132 (a section can be named) gave sections their
  names. No prior.

### LOC-22 "slots" appears in some boxes and not others
- Severity: S3
- Screens: `#/inventory`
- Where: all
- Repro: compare box 1 card 1 with box 4 card 1.
- Seen: Box 1 says `card 1 of 11 slots` under a header that says `11 CARDS`. Box 4 says
  `card 1 of 15`.
- Shot: LOC-22, screenshot not kept.
- Direction: One phrase.
- Component: `PositionBar.tsx`.
- Annotation: no decision covers this. D58 (a card's number counts cards, not slots) argues
  against the word "slots" for a count of cards. No prior.

### LOC-23 A departed card's caption reads as a count of departures
- Severity: S3
- Screens: `#/inventory`
- Where: all
- Repro: `#/inventory?box=4` → `Hide sold` off → `Vulpix`.
- Seen: The ruler caption reads `Section 1 · 15 cards left this section`. That reads as
  "15 cards left (departed) this section". The intended reading is "15 cards. This one
  left."
- Shot: LOC-23, screenshot not kept.
- Direction: "Left this section" stands alone, or the count gets a label.
- Component: `PositionBar.tsx` (`sectionBlankSentence`).
- Annotation: no decision covers this. No prior.

### LOC-24 In dark, the ruler fill and the other section chips almost vanish
- Severity: S3
- Screens: `#/inventory`
- Where: dark, all widths
- Repro: `#/inventory?box=1`, dark, card 6.
- Seen: The fill is dark navy on near black. The two other section chips are faint outlines.
  It is hard to see which chip holds the card. Seen, contrast not measured.
- Shot: LOC-24, screenshot not kept.
- Direction: Chips and fill meet non-text contrast in dark.
- Component: `PositionBar.css`.
- Annotation: no decision covers dark contrast here. D155 (the section is the ruler) set the
  fill and chips. No prior.

### LOC-25 The list does not follow the walk into the next section
- Severity: S3
- Screens: `#/inventory`
- Where: 1440
- Repro: `#/inventory?box=1`, press → 11 times.
- Seen: The panel shows Double Trouble (section 2 card 1). The list still shows section 1's
  #7-#11, and the selected row is out of view.
- Shot: LOC-25, screenshot not kept.
- Direction: The selected row is always in view.
- Component: `BoxBrowse.tsx`.
- Annotation: no decision covers this. No prior.

### LOC-26 Review's pill is small and has no neighbours
- Severity: S3
- Screens: `#/review`
- Where: all
- Repro: `#/review`.
- Seen: 12px caps labels and a 15px numeral, in a grey pill on the photo's foot. No box
  name, no before/after. It is the only place cue while the owner decides about a card that
  may need a look in the box.
- Shot: LOC-26, screenshot not kept.
- Direction: Use the same place block as Inventory.
- Component: `ReviewQueue.tsx`, `PositionLabel.tsx`.
- Annotation: no decision covers Review's place block. D41 (the address is a rank) set the
  muted-path, large-number shape it uses. No prior.

### LOC-27 Cards to pull splits the address across lines at 390
- Severity: S3
- Screens: `#/fulfillment`
- Where: 390
- Repro: `#/fulfillment` at 390 → Box 1 → Double Trouble.
- Seen: `Box 1 · Section 2` / `Card 1` wraps in the middle of the address. With a real photo
  above it, the address moves lower (unmeasured, because the demo has no photos).
- Shot: LOC-27, screenshot not kept.
- Direction: The address never wraps inside a part, and sits above the photo on a phone.
- Component: `CardLocations.tsx` `FulfillerCard`.
- Annotation: no decision covers the wrap. D5 (two personas) sets the Fulfiller's floors.
  D155 (the section is the ruler) left the Fulfiller's bar unchanged on purpose. No prior.

### LOC-28 A captured neighbour is dropped from BEFORE
- Severity: S4
- Screens: `#/inventory`
- Where: all
- Repro: `#/inventory?box=4` → `#14 Not identified yet`.
- Seen: Only `AFTER Wally's Compassion` shows. `#15` has no name, so no `BEFORE` shows and
  nothing says a card follows.
- Shot: LOC-28, screenshot not kept.
- Direction: Show an unnamed neighbour as "an unread card".
- Component: `PlaceNeighbors.tsx`.
- Annotation: caused by D116 (a card nobody has named is not a landmark). D116 names the
  nearest NAMED card on each side and says how many it passed. At the end of a box there is
  no named card to name, so the count of passed cards is lost too. No prior.

### LOC-29 The kit shows "% in", the product does not
- Severity: S4
- Screens: `#/gallery`, `#/inventory`
- Where: 1440
- Repro: compare the `#/gallery` position bar with `#/inventory`.
- Seen: The kit's caption is `#40 of 250 · 16% in`. The live caption is only `#12 of 34`.
  The "how far in" answer the owner asked for is built and not shown.
- Shot: LOC-29, screenshot not kept.
- Direction: Show how far in, in the product.
- Component: `PositionBar.tsx`.
- Annotation: no decision covers this. No prior.

## Held-screen notes

Inventory, Orders and Review are in scope for this lens by the orchestrator's word. Their
findings are above (LOC-03 to LOC-12, LOC-17 to LOC-26, LOC-28). All were reviewed on the
integration branch at c60d53ef.

## What I could not check

- **Photos.** No card photograph renders in the branch demo or the main demo. Cause seen:
  `scripts/demo-record.py` `copy_photos` reads `captures/cards/box*/*.jpg`. The seed writes
  `photos/<xx>/<sha>.jpg`, so it copies 0. Pass 2: caused by D183 (a number a person reads
  is never a key), which moved photos to the card's name. The recorder did not follow.
  Whether a real photo confirms the card at the
  moment of reaching is UNKNOWN. Measured frames: Inventory 265x370 (1440), 266x371 (390).
  Pricing thumbnail 36x48. Capture tile 48x85.
- **Orders walk.** The demo refuses `POST /orders/walk-plan`. No card position renders on
  `#/orders`. UNKNOWN.
- **Graveyard, `#/pricing?band=top`, `#/product?sku=`.** Not recorded in either demo.
  UNKNOWN.
- **Renumbering after a sale, move or retire.** The demo's sale did not change the box's
  counts or numbers, also after `re-rank`. I cannot tell the product's renumbering from the
  demo's frozen recording. UNKNOWN.
- **Cards to pull search.** "The search did not finish" for every query. Demo gap or
  defect: UNKNOWN.
- **Timings** are reviewer estimates from reading screenshots, not a timed study.
- 820 was not shot. The lens asked for 720.
