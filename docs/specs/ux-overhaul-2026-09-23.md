# UX overhaul, 2026-09-23: the review, the owner's rulings, and the build plan

**Status: RECORDED.** The owner ruled on every item below in an interview on 2026-09-23. The
build runs in lanes, and each lane lands by its own pull request. This document builds nothing.
It is the one place where the whole design lives, so the design does not live only in chat.

The record of findings is `docs/reviews/ux-2026-09-23/`. Its `INDEX.md` names every file.

## 1. Why

The owner's words:

```
I think I really need a massive UX pass/review again as so many features have been
incorporated since we started banchi and they're not syncing.
```

Features were added one at a time, each with its own decision. The owner felt that they no
longer read as one product.

## 2. How the review ran

1. **Seven blind lenses** looked at the published demo, built from main at PR #454 and #455:
   coherence, the daily loop, visual system, interaction, copy, access and text density. Each
   lens graded first, blind to `docs/`. It then read the decisions to annotate its findings.
   The visual lens also made a read-only look at the owner's live app: 10 page loads at 1440,
   GET requests only.
2. **One consolidation** merged 250 lens findings into **164 distinct findings**: 2 S1, 35 S2,
   89 S3 and 38 S4. It grouped them into ten themes and listed 21 decisions in question.
3. **Two more lenses** joined during the interview, on the owner's asks. The filtering lens
   (38 findings, FLT) looked at filters, sorting, search and scope. The locating lens (29
   findings, LOC) looked at how fast the owner knows where a card is.
4. **Three deliberations** answered questions that needed more than a choice: the flow from
   captured cards to live listings, the product views, and the box map.
5. **A held-screen pass** reviewed `#/orders`, `#/inventory` and `#/review` after the photo
   branch merged (PR #456). It found 35 findings on Orders (HOR) and 39 on Inventory and Review
   (HIR).
6. **The interview.** The owner ruled on each decision in question, each deliberation and each
   plan question.

A second consolidation was running when this document was written. It adds findings from
UX-165 on. Section 8 says what that means for this document.

## 3. The ten themes

The consolidation named ten ways the features fail to agree.

| Theme | What fails |
|---|---|
| T1 Counts that disagree | Six screens count the store, and no label says what each figure counts. |
| T2 One concept, several names | Box is also drawer and shelf. A card's place has four names. An order has three ids. |
| T3 Dead ends and dropped hand-offs | Product history has no inbound link. A card on one screen cannot open on another. |
| T4 Machine words on the owner's screen | Reason codes, error codes, request paths and a shell command reach the owner. |
| T5 Too many words | Shipping draws 4,942 words for three counts and a download. |
| T6 Each screen builds its own parts | Money has four faces. Errors have three shapes. Overlays have four designs. |
| T7 The phone is a second-class screen | The Pricing bar takes a third of a phone. The drawer hides two screens. |
| T8 The screen moves under the hand | Refusals, notices and releases push the next control. |
| T9 Built on fixtures, broken at real density | Sales at 562 rows, Graveyard wider than the page, the S1 on Cards to pull. |
| T10 Floors hold on some screens only | Focus traps, a skip link, field edges and contrast pass on some screens only. |

## 4. The owner's rulings

A settled decision is an argument, not a law. Each ruling below names the decision it keeps or
amends. Where no build lane writes the amendment, this lane wrote an entry. Section 4.12 lists
those entries.

### 4.1 Scope

- The two S1 findings fold into the plan. No separate hotfix lane.
- The build covers every finding, the small ones included.
- Cut every line the density lens proposed, about 4,200 words. D137 (the catalog is Near Mint
  by rule) is the one exception: "Near Mint" stays on every row.
- Every question-shaped item is an interview, not a default.
- **Durability.** What is built today must be reusable. A new sidebar page inherits the other
  pages' properties. Wave 0 builds a page scaffold and shared parts. `ROUTES` in
  `app/src/App.tsx` stays the one place a screen registers. A check fails a route that does not
  render through the scaffold, and a hand-made copy of a kit part.

### 4.2 Words on screen

| Ruling | Decision | Kept or amended |
|---|---|---|
| Codes go behind a "What the server said" disclosure. The word list grows. A browser check reads rendered text. | D196 (no user-visible string names a decision, a path or a pipeline noun) | Kept. Its `Notice.code` exemption is amended by the kit-frame lane. |
| The pinned word ceilings go. Three checks replace them: a repetition check, a sentence-shape check, and the text-density reviewer as a pass run on demand. No pinned counts. | D194 (the word count may only go down) | Superseded. The text-checks lane writes the entry. |
| A decision's argument printed as copy is deleted: D100, D168, D134, D70, D102 and D86. | Those six | Amended, slug `reasoning-is-not-screen-copy`. |
| Sales' refund and cancel notes draw only when their count is above 0. | D225 (a sales truth) | Amended, same entry. |
| "Box" everywhere on screen, and the count is read live from the store. | D180 (a press names its cards), D153 (the restore asks which box) | Kept. A copy fix only. |

### 4.3 Money and the page frame

| Ruling | Decision | Kept or amended |
|---|---|---|
| Money is mono everywhere, inputs and chips included, and a check refuses any other face. The owner saw both options drawn first. | D221 (money stays mono) | Confirmed, premise fixed, slug `money-is-mono-everywhere`. |
| One page width, 1600px, fluid at every narrower width. One top gap. | D197 (one left edge) | Amended by the kit-frame lane. |
| The owner uses two Chrome tabs side by side, about 720px each at 1440. That view is designed as well as the phone. 720 joins every verification. At 720 the desktop rail shows. Its breakpoint moves to about 640. | D197, D120 (one brand at every width) | The kit-frame and shell lanes. |

### 4.4 The shell

| Ruling | Decision | Kept or amended |
|---|---|---|
| The palette is labelled "Go to" and lists every screen. "More" lights up. The drawer and palette hold focus. Card search joins the palette now if the lift is low. | D95 (the shell is a rail, a palette and a reference sheet) | Amended by the shell lane. |
| The drawer's foot items join the scrolling list. The foot goes. | D204 (the drawer scrolls above its foot) | Amended, slug `drawer-foot-joins-the-list`. |

### 4.5 Screens

| Screen | Ruling | Decision |
|---|---|---|
| Home | The button stays as it is. "Behind that" lines that repeat a figure are cut. | D121 (the front page says what is owed). The home lane writes the amendment. |
| Capture | A fresh device always asks for a box ("No box yet"). Home's tile says what it shows: the newest box. | D142 (the setup outlives the browser). The capture lane writes it. |
| Box lists | Most recent first everywhere: the Inventory rail, the Capture picker, Home and Cards to pull. | D132, D142. Slug `a-press-reorders-and-nothing-else-moves`. |
| Sales | Rows lead with the card name. The table shows the top rows and "Show all". "On the shelf" moves above the table or to its own tab. | D214 (a gross-revenue retrospective), D250 (unsold stock on Sales). The sales lane writes it. |
| Sales | Printings of one name must be told apart. The code groups rows by name and keeps only the last SKU. The planner picked one row per printing. | D214, D217 (Sales becomes a tool). The sales lane. |
| Sales | "Literally just an excel sheet". It needs a visual redesign. A direction goes to the owner before the layout is built. | None. Held for the owner. |
| Shipping | The lane order stays. Every lane collapses on a phone. Per-card repetition is still cut. | D61 (the shipping lane is three lanes). The shipping lane writes it. |
| Product views | One product view. A sheet opens from every product name. `#/product?sku=` stays the deep link. The Pricing drawer folds in. First fix the trap that sends a person back to an empty `#/product`. | D227 (a route, not a lens), D62 (price history beside the hold). The product lane writes it. |
| Cards to pull | "Pick 2 of X", and where every copy is. Never 2 copies the app chose. | D212 (no order claims a copy). Slug `pull-list-is-a-pick-count`. |
| Cards to pull | Sold cards leave the list. The dead `/` row goes. `?` works. "Not a big rock." | D5 (two personas), D68 (a departed label). Kept. Same entry. |
| Pricing | The legend and the verdict sentence become one slim bar. | D208 (Pricing states its verdict once). Held for the Pricing re-interview. |
| Runs | Name the real next step, for example "Ready to write". The whole Runs process is still unintuitive. It needs its own re-interview. | D156 (one worklist). Slug `one-press-sends-and-makes-live`, and the re-interview. |

### 4.6 The flow from captured cards to live listings

The owner asked an agent to review the whole flow, not a multiple-choice answer (D105, D99,
D87). The review put eight questions. The rulings:

- **Q1.** Banchi sends the listing file itself. "Download the file instead" stays.
- **Q2.** One press sends and makes live. This amends D106 (the push and the publish are two
  presses).
- **Q3.** An open app checks what is live by itself when the 15-minute wait ends. A closed app
  checks on the next visit to Pricing or Home. No server job runs unattended.
- **Q4.** Matching runs by itself when the reading finishes. A problem becomes the run's next
  step.
- **Q5.** The cost check runs when the Identify sheet opens. Open, then spend.
- **Q6.** The Runs screen's shape is decided after the moves land.
- **Q7.** A manual "Check what is live" press sits on Pricing's send card and in the Mark-down
  sheet.
- **Q8.** Pricing names copies in a file that was written and never sent, with "Take them back".

Slug `one-press-sends-and-makes-live` records these and what each one touches.

### 4.7 Filtering

- **A sort press re-sorts at once** (FLT-01). This amends D209 (a re-sort is a press). The
  freeze still stops a sale from re-ranking a list.
- **Nothing jumps** (FLT-22). A sold row stays in place, marked sold, until the next box load
  or refresh. D118 (a press moves nothing around it) wins over the timing in D132 (sold is
  folded away).
- **One forgiving search matcher everywhere** (FLT-06, FLT-04), on the server too. Slug
  `one-forgiving-search-matcher`.
- **The owner's gripes, all confirmed by the lens.** Inventory's filters lock to game, then set,
  then rarity, and a game change clears the others. Filters must work in any order and combine.
  The Orders buyer list is "atrociously ugly". The Orders filter bar mixes widths and opens the
  operating system's own menu. Its "611 lines across 806 buyers" counts two different sets.
- **Capture's picker is "pretty decent".** It is the base for the one shared filter control.

Slug `a-press-reorders-and-nothing-else-moves` records the first two rulings.

### 4.8 Locating a card

- **The card number counts within the section,** and it starts again at every divider. This
  amends the display half of D58 (a card's number counts the cards in the box). A sale still
  renumbers the cards behind it, within the section.
- **Card 1 is at the far back.** The highest number is nearest the owner. Every drawing of a
  position shows that orientation.
- **The ruler is redesigned.** It marks the exact card, uses section numbers throughout and
  shows the sections before and after. This amends D155 (the section is the ruler).

Slug `a-card-is-counted-in-its-section` records all three.

### 4.9 The box map

A new feature. The spec is `docs/specs/box-map.md`. The rulings:

- A section is an object. It keeps its name, divider and cards when it moves.
- v1 moves a section before or after any section of another box. It reorders sections within a
  box. It merges and splits boxes. Single cards and ranges come right after.
- The map is a "Shelf" view inside Inventory. That keeps D31 (one owner-side view of stored
  cards).
- The map shows counts only.
- Pricing follows a moved card. This amends D165 (a run is bound to the box's true index).
- Placement needs a per-card order key, its own decision.

Slugs `a-section-is-an-object`, `card-order-key` and `a-moved-card-keeps-its-price` record them.

### 4.10 Answers the orchestrator gave

These are not the owner's rulings. The owner had no preference, or was not asked.

- A box map drop saves at once, with a receipt and Undo on `U`.
- A box map undo restores exactly while neither box has changed since.
- UX-073 (the price field's focus ring) moves into the pricing-clip lane.
- The Pricing drawer fold waits for the Pricing re-interview.
- The allow list for the new kit check is a list of offenders that only shrinks. Each entry
  names a file, a rule and a lane. A stale entry fails. There is no pinned count.

### 4.11 Coordination

- Merge order: the photo branch first (merged, PR #456), then this UX work, then the second
  token-literal sweep.
- `sayPlace()` in `app/src/position.ts` carries every server place label that becomes text or
  an accessible name.
- A CSS literal equal to a `--bn-*` value fails `make token-literal-check`.

### 4.12 Entries this lane wrote

| Slug | Keeps or amends |
|---|---|
| `pull-list-is-a-pick-count` | Amends D212's screen. Keeps D5 and D68. |
| `money-is-mono-everywhere` | Confirms D221 and fixes its premise. |
| `one-press-sends-and-makes-live` | Amends D106. Touches D33, D87, D100, D105 and D156. |
| `a-moved-card-keeps-its-price` | Amends D165. |
| `a-card-is-counted-in-its-section` | Amends D58's display, D92 and D155. |
| `a-press-reorders-and-nothing-else-moves` | Amends D209 and D132's timing. Extends D142. |
| `one-forgiving-search-matcher` | Sets the first app-wide rule for search. |
| `a-section-is-an-object` | Amends D83. Keeps D31. |
| `card-order-key` | Keeps D10 and D58's fixed index. Adds an order key. |
| `reasoning-is-not-screen-copy` | Amends D100, D168, D134, D70, D102, D86 and D225. |
| `drawer-foot-joins-the-list` | Amends D204. |

The build lanes write ten more: `one-page-width`, `notice-detail`, `page-scaffold`,
`palette-go-to`, `text-shape-checks`, `product-view-hybrid`, `home-owed-line`,
`capture-always-asks`, `sales-rows-by-sku` and `ship-lanes-collapse`.

## 5. The build plan

Each lane has one builder, its own worktree and its own branch. A reviewer follows each lane.
Screen lanes never edit the kit, the shell or another lane's files. The sum at planning time was
117 findings assigned, 44 blocked and 3 held, for 164.

| Wave | Lanes | What they do |
|---|---|---|
| 0, the foundation | kit-frame, kit-data, guards, pricing-clip. The fulfillment lane was already running. | The page scaffold, overlays, the shared data parts, the kit adoption check, and the Pricing price-field clip (the S1). The fulfillment lane fixes the Cards to pull S1. |
| 1 | shell, text-checks, product | The route table as the one registration point, the palette and drawer, the three text checks, and the one product view. |
| 2, the screens | home, capture, sales, shipping, library | Each screen moves onto the scaffold and the shared parts. |
| 3 | filtering, locating, docs-sweep, the held screens | Filters and search, the place of a card, the docs, and Inventory, Orders and Review. |
| records | specs (this lane) | This document, the box map spec, the review record and the decision entries. |

Wave 0 merges in this order: kit-data, then kit-frame, then guards. Every screen is checked at
1440, 820, 720 and 390, in both themes.

## 6. What is blocked, and why

- **Pricing** (the pricing lane, 19 findings). It waits for a Pricing re-interview. The D208
  ruling cuts the legend and the verdict sentence, and the owner said the screen likely needs
  more than that. The Pricing drawer fold into the product view waits with it.
- **Runs** (the runs lane, 25 findings). The flow rulings unblock most of it. It needs Pricing's
  write-bar region, so it runs after the pricing lane. The Runs screen's final shape (Q6) is
  decided after the send and live presses move to Pricing. Then the owner sees what is left and
  rules.
- **The box map.** Nothing is in a lane yet. Slice 0 of `docs/specs/box-map.md` is a safety fix
  that can ship first.

## 7. What is not decided yet

1. The Pricing re-interview.
2. The Runs screen's shape, after the moves land.
3. The visual direction for Sales. It goes to the owner before its layout is built.
4. Which mechanism replaces D100's zero-quantity check for a listing file. A file sent twice
   must not double a quantity.
5. Whether the one-press send also reaches the Mark-down sheet.
6. Which clock "most recent" reads for Home and Cards to pull.
7. Whether the search matcher folds accents, and whether a miss offers the closest name.
8. The form of the card order key.
9. The two box map defaults (section 4.10), shown to the owner.
10. The owner of the rendered-page money check. No lane names it yet.
11. Five measurements the flow review listed before any send is built. The first touches the
    real TCGplayer account and needs the owner's word.

### 7.1 An incident, and two findings that need a lane

The owner learned of these on 2026-09-23.

- **A scratch copy read the live store.** The held-Orders reviewer built main's app from a copy
  with no `.git`. Its API fell back to port 8000 and read the owner's live store once, by page
  load, with no press. The captures were deleted. The defect: a copied tree must never fall
  back to the main checkout's live port (D43, the port follows the store). It needs a lane over
  `server/ports.py` and `app/devPort.ts`.
- **HOR-04 (S1).** "Stand down N orders" in a buyer's Manage sheet closes every open order
  before today, live Ready to Ship orders included. It shows no cutoff. That breaks D203 (the
  backlog is stood down over a cutoff the operator sees). The owner was warned.
- **HOR-07.** Undo on a pull fails with `sold_origin_unknown` on a seeded store. The owner was
  asked to test it once on the real store.

## 8. The second consolidation

A second consolidation was rewriting the consolidated findings when this lane ran. It adds
findings from UX-165 on, and a lane addendum. Section 5's counts are the first plan's. The
record in `docs/reviews/ux-2026-09-23/` holds whichever consolidation was current when this lane
copied it, and its `INDEX.md` says which.
