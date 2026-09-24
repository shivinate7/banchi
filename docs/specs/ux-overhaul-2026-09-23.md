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

A second consolidation then merged the round-two findings. It holds 272 findings. Section 8
says what changed.

## 3. The fourteen themes

The first consolidation named ten ways the features fail to agree. The second added four. The
themes are numbered, not given a T id here, because a T id reads as a harness test.

| Theme | What fails |
|---|---|
| 1. Counts that disagree | Six screens count the store, and no label says what each figure counts. |
| 2. One concept, several names | Box is also drawer and shelf. A card's place has four names. An order has three ids. |
| 3. Dead ends and dropped hand-offs | Product history has no inbound link. A card on one screen cannot open on another. |
| 4. Machine words on the owner's screen | Reason codes, error codes, request paths and a shell command reach the owner. |
| 5. Too many words | Shipping draws 4,942 words for three counts and a download. |
| 6. Each screen builds its own parts | Money has four faces. Errors have three shapes. Overlays have four designs. |
| 7. The phone is a second-class screen | The Pricing bar takes a third of a phone. The drawer hides two screens. |
| 8. The screen moves under the hand | Refusals, notices and releases push the next control. |
| 9. Built on fixtures, broken at real density | Sales at 562 rows, Graveyard wider than the page, the S1 on Cards to pull. |
| 10. Floors hold on some screens only | Focus traps, a skip link, field edges and contrast pass on some screens only. |
| 11. Filters and search that each screen invents | One question, "show me only these", has five answers. |
| 12. Where the card is, with no orientation | Three counts, two scales on one ruler, and no end named. |
| 13. A press that can lose work with no guard | A stand-down closes live orders. An Undo is offered, then refused. |
| 14. The work list gets the smallest box | The list the hand walks from is a window 96px to 216px tall. |

## 4. The owner's rulings

A settled decision is an argument, not a law. Each ruling below names the decision it keeps or
amends. Where no build lane writes the amendment, this lane wrote an entry. Section 4.13 lists
those entries.

### 4.1 Scope

- The two S1 findings fold into the plan. No separate lane for urgent fixes.
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
| A decision's argument printed as copy is deleted: D100 (nothing is deleted to lower a price), D168 (a typed price is cleared by a press), D134 (departed records are buried), D70 (the QR is the identification), D102 (the mark's spec) and D86 (one pricing file for the store). | Those six | Amended, slug `reasoning-is-not-screen-copy`. |
| Sales' refund and cancel notes draw only when their count is above 0. | D225 (a sales truth) | Amended, same entry. |
| "Box" everywhere on screen, and the count is read live from the store. | D180 (a press names its cards), D153 (the restore asks which box) | Kept. A copy fix only. |

### 4.3 Money and the page frame

| Ruling | Decision | Kept or amended |
|---|---|---|
| Money is mono everywhere, inputs and chips included, and a check refuses any other face. The owner saw both options drawn first. | D221 (money stays mono) | Confirmed, premise fixed, slug `money-is-mono-everywhere`. |
| One page width, 1600px, fluid at every narrower width. One top gap. | D197 (one left edge) | Amended by the kit-frame lane. |
| The owner uses two Chrome tabs side by side, about 720px each at 1440. That view is designed as well as the phone. 720 joins every verification. At 720 the desktop rail shows. Its breakpoint moves to about 640. | D197 (one left edge), D120 (one brand at every width) | The kit-frame and shell lanes. |

### 4.4 The shell

| Ruling | Decision | Kept or amended |
|---|---|---|
| The palette is labelled "Go to" and lists every screen. "More" lights up. The drawer and palette hold focus. Card search joins the palette now if the lift is low. | D95 (the shell is a rail, a palette and a reference sheet) | Amended by the shell lane. |
| The drawer's foot items join the scrolling list. The foot goes. | D204 (the drawer scrolls above its foot) | Amended, slug `drawer-foot-joins-the-list`. |
| The tab title is fixed: "番地 " and then the screen name in lowercase, for example "番地 pricing". It does not alternate, and it drops "— Banchi". | D94 (Banchi is the product's name) | Kept: the rename's reach already covers the document title. The scaffold check in the guards lane must assert this form. |

### 4.5 Screens

| Screen | Ruling | Decision |
|---|---|---|
| Home | The button stays as it is. "Behind that" lines that repeat a figure are cut. | D121 (the front page says what is owed). The home lane writes the amendment. |
| Capture | A fresh device always asks for a box ("No box yet"). Home's tile says what it shows: the newest box. | D142 (the setup outlives the browser). The capture lane writes it. |
| Box lists | Most recent first everywhere: the Inventory rail, the Capture picker, Home and Cards to pull. | D132 (sold is folded away), D142 (the setup outlives the browser). Slug `a-press-reorders-and-nothing-else-moves`. |
| Box names | A box is shown only by its name, everywhere. The number and the `bid` stay inside the store. A count of boxes may show. A box with no name gets a stored default name, "Box" and the count plus one. Today's unnamed boxes are backfilled with "Box" and their number, so nothing visible changes. A departed card's label reads box name, section and card, and a visual mark shows it has left. This overrides the earlier call on "Mixed Singles, Box 4". The locating lane builds it. | D145 (the number is a label), D68 (the departed label), D92 (the key's sigil), D20 (names are unique). Slug `a-box-is-shown-by-its-name`. |
| Orders and Shipping | Two sidebar rows, no tabs. The walk keeps its model and gets the screen's full height. An owner ruling from the final interview. | D220 (Orders is inventory's screen). Slug `orders-and-shipping-are-two-rows`. |
| Inventory | "Slots" names the box's capacity, in Inventory's box header and strip only. Every other place says "cards". An owner ruling from the final interview. | D58 (a card's number counts the cards). Slug `a-card-is-counted-in-its-section`. |
| Sales | Rows lead with the card name. The table shows the top rows and "Show all". "On the shelf" moves above the table. | D214 (a gross-revenue retrospective), D250 (unsold stock on Sales). |
| Sales | Printings of one name must be told apart. The code groups rows by name and keeps only the last SKU. The planner picked one row per printing. | D214 (a gross-revenue retrospective), D217 (Sales becomes a tool). The sales lane's entry. |
| Sales | Direction B: a summary band with month bars and the shelf value, the top three cards as photo tiles, a mix tile, places 4 to 10 as bar rows, then the table. "On the shelf" loads on arrival. A tile borrows another copy's photo by SKU. | D214 (a gross-revenue retrospective), D217 (Sales as a tool), D250 (unsold stock on Sales). Slug `sales-is-a-leaderboard`. |
| Sales | A line at $0.00 gets its real price from TCGplayer's own data. The owner: "TCGplayer has all the data of what items sold at what prices tho". | Same entry. |
| Shipping | The lane order stays. Every lane collapses on a phone. Per-card repetition is still cut. | D61 (the shipping lane is three lanes). The shipping lane writes it. |
| Product views | One product view. A sheet opens from every product name. `#/product?sku=` stays the deep link. The Pricing drawer folds in. First fix the trap that sends a person back to an empty `#/product`. | D227 (a route, not a lens), D62 (price history beside the hold). The product lane writes it. |
| Cards to pull | "Pick 2 of X", and where every copy is. Never 2 copies the app chose. | D212 (no order claims a copy). Slug `pull-list-is-a-pick-count`. |
| Cards to pull | Sold cards leave the list. The dead `/` row goes. `?` works. "Not a big rock." | D5 (two personas), D68 (a departed label). Kept. Same entry. |
| Pricing | See section 4.7. | D208 (one Pricing verdict), D98 (the cheap-card figure), D159 (the value band). Slug `pricing-is-one-list-and-one-send`. |
| Runs | Name the real next step, for example "Ready to write". The whole Runs process is still unintuitive, and its shape is decided after the moves land. | D156 (one worklist). Slug `one-press-sends-and-makes-live`. |

### 4.6 The flow from captured cards to live listings

The owner asked an agent to review the whole flow, not a multiple-choice answer. The flow
touched D105 (the markdown lives on Pricing), D99 (one press writes one file) and D87 (the
store-wide reconcile). The review put eight questions. The rulings:

- **Q1.** Banchi sends the listing file itself. "Download the file instead" stays.
- **Q2.** One press sends and makes live. This amends D106 (the push and the publish are two
  presses).
- **Q3.** An open app checks what is live by itself when the 15-minute wait ends. A closed app
  checks on the next visit to Pricing or Home. No server job runs unattended.
- **Q4.** Matching runs by itself when the reading finishes. A problem becomes the run's next
  step.
- **Q5.** The cost check runs when the Identify sheet opens. Open, then spend.
- **Q6.** The Runs screen's shape is decided after the moves land.
- **Q7.** A manual "Check what is live" press sits on Pricing's send card and on the Live tab.
- **Q8.** Pricing names copies in a file that was written and never sent, with "Take them back".

**The double-send guard.** The owner, in the Pricing re-interview:

```
maybe before submitting prices there's a mandatory reconciliation that auto runs seeing my
sales and live inventory
```

So every Send, for listings and for mark-downs, first runs a live reconcile by itself. It sends
only the copies TCGplayer does not already hold. It refuses or trims a send that would double a
quantity, and it shows what it trimmed. When the live check cannot run, Send refuses, says why
and offers "Try again". This amends D106 (push and publish are two presses) further, and D87
(the store-wide reconcile).

**An open question, derived from the send rulings.** D100 (nothing is deleted to lower a price)
makes the transport refuse a row whose Add to Quantity is not 0. A listing file cannot pass that
check. The rulings do not say what happens to it. This document does not claim the guard
replaces it. The owner decides.

Slug `one-press-sends-and-makes-live` records all of it.

### 4.7 Pricing, after its re-interview

The owner answered all ten questions, Q1 to Q10. The owner also ruled the double-send guard and
the refusal when the live check cannot run (section 4.6).

- **Q1.** Every row shows. The rows that need the owner go on top, then the rest by value.
- **Q2.** A row needs the owner in three cases: it has no market price, it is worth $5 or more,
  or its typed price is 25% or more away from today's market. Count these on the real store
  first.
- **Q3.** Send takes every ready copy. A row with no price stays on the list.
- **Q4.** The slim bar is sticky at the top at 1440 and 720. On a phone it is one line pinned
  above the tab bar.
- **Q5.** The rule and the cut-off are one line above the list, with "Change". Change opens one
  sheet: the rule, the cut-off, and a box's own cut-off.
- **Q6.** Mark-downs move to a "Live" tab on Pricing, with the same rows. The Mark-down sheet
  goes.
- **Q7.** A mark-down is one press too. There is no "Put the old prices back" control.
- **Q8.** The value list leaves Pricing. It becomes a "by value" sort on Inventory, in the
  shared sort control. This moves D159 (the band is copies).
- **Q9.** Measure the owner's typed prices first. If most follow one pattern, Pricing offers
  "Make this the rule" once.
- **Q10.** Nothing sits beside Send. The caps (at most N per card, only above the cut-off) are
  removed from beside Send. "Split in two files" moves under "Download the file instead". Where
  the caps live now is not ruled.

Slug `pricing-is-one-list-and-one-send` records the screen. It amends D208 (Pricing states its
verdict once), D98 (the cheap-card figure is the control) and D159 (the value band), and extends D105 (the markdown lives on Pricing).

### 4.8 Filtering

- **A sort press re-sorts at once** (FLT-01). This amends D209 (a re-sort is a press). The
  freeze still stops a sale from re-ranking a list.
- **Nothing jumps** (FLT-22). A sold row stays in place, marked sold, until the next box load
  or refresh. D118 (a press moves nothing around it) wins over the timing in D132 (sold is
  folded away).
- **One forgiving search matcher everywhere** (FLT-06, FLT-04), on the server too. It folds
  accents (an orchestrator call). A fuzzy number match never feeds the join. Slug
  `one-forgiving-search-matcher`.
- **Filter memory lives in the URL** on every screen (FLT-11), so a link, a bookmark and the
  back button restore the view. An owner ruling from the final interview. The storage-key
  roster in CLAUDE.md changes in the docs-sweep lane.
- **The owner's gripes, all confirmed by the lens.** Inventory's filters lock to game, then set,
  then rarity, and a game change clears the others. Filters must work in any order and combine.
  The Orders buyer list is "atrociously ugly". The Orders filter bar mixes widths and opens the
  operating system's own menu. Its "611 lines across 806 buyers" counts two different sets.
- **Capture's picker is "pretty decent".** It is the base for the one shared filter control.

Slug `a-press-reorders-and-nothing-else-moves` records the first two rulings.

### 4.9 Locating a card

- **The card number counts within the section,** and it starts again at every divider. This
  amends the display half of D58 (a card's number counts the cards in the box). Renumbering on
  departure still holds, within the section. When a card is sold, retired or moved, each later
  card in its section counts down by one.
- **Card 1 is at the far back.** The highest number is nearest the owner. Every drawing of a
  position shows that orientation. The locating lane owns it (an orchestrator call).
- **The ruler is redesigned.** It marks the exact card, uses section numbers throughout and
  shows the sections before and after. This amends D155 (the section is the ruler).

Slug `a-card-is-counted-in-its-section` records all three.

### 4.10 The box map

A new feature. The spec is `docs/specs/box-map.md`. The rulings:

- A section is an object. It keeps its name, divider and cards when it moves.
- v1 moves a section before or after any section of another box. It reorders sections within a
  box. It merges and splits boxes. Single cards and ranges come right after.
- The map is a "Shelf" view inside Inventory. That keeps D31 (one owner-side view of stored
  cards).
- The map shows counts only.
- Pricing follows a moved card. This amends D165 (a run is bound to the box's true index).
- The orchestrator infers that placement needs a per-card order key, as its own decision. The
  key and its design are the orchestrator's, not the owner's ruling.

Slugs `a-section-is-an-object`, `card-order-key` and `a-moved-card-keeps-its-price` record them.

### 4.11 Calls the orchestrator made

These are not the owner's rulings. Each sits under an "Orchestrator calls" heading in
`RULINGS.md`, or is marked there as an orchestrator default or call. Each was stated to the
owner and can be reversed.

- A box map drop saves at once, with a receipt and Undo on `U`.
- A box map undo restores exactly while neither box has changed since.
- UX-073 (the price field's focus ring) moves into the pricing-clip lane.
- The Pricing drawer fold waited for the Pricing re-interview. That interview is done, so the
  drawer folds into the one product view in the pricing lane.
- Search ignores accents.
- The text-checks lane owns the rendered-page money check.
- "Card 1 at the far back" belongs to the locating lane.
- The "cut everything" text ruling also covers the cut lists of the two held-screen reviews.
- The disclosure rule of D196 (no machine words on screen) wins over the 2026-09-20 taste call
  for Review's Close dialog.
- UX-013 stays S1. The Fulfiller was sent to pull a card that had left the box.
- The kit-frame review: no word-count re-pin, because the text-checks lane merges first. The
  fourth ink token is for non-text only, and text in it moves to the third ink. A ConfirmSheet
  opens with focus on Cancel. The phone's top gap is 16px below 768.
- The guards review: `app/src/PriceHistory.tsx` belongs to the product lane. `#/fulfillment` is
  exempt from the scaffold's width and top-gap rules. D5 (two personas) and the Fulfillment
  floors in `docs/DESIGN.md` are the reason. It keeps its page and its h1. Live-store counts may
  appear in public docs, and a real product string or buyer name may not. The docs must not
  claim that the transport check of D100 (nothing is deleted to lower a price) is replaced.
- An earlier call put the box number after the name ("Mixed Singles, Box 4"). The owner's own
  ruling overrides it: a box is shown by its name only.

The shrinking allow list for the new kit check is the owner's ruling, not a call. Each entry
names a file, a rule and a lane. A stale entry fails. There is no pinned count.

### 4.12 Coordination

- Merge order: the photo branch first (merged, PR #456), then this UX work, then the second
  token-literal sweep.
- `sayPlace()` in `app/src/position.ts` carries every server place label that becomes text or
  an accessible name.
- A CSS literal equal to a `--bn-*` value fails `make token-literal-check`.

### 4.13 Entries this lane wrote

| Slug | Keeps or amends |
|---|---|
| `pull-list-is-a-pick-count` | Amends the screen of D212 (no order claims a copy). Keeps D5 (two personas) and D68 (the departed label). |
| `money-is-mono-everywhere` | Confirms D221 (money stays mono) and fixes its premise. |
| `one-press-sends-and-makes-live` | Amends D106 (push and publish are two presses) and D87 (the store-wide reconcile). Records the check of D100 (nothing is deleted to lower a price) as an open question. Touches D33 (one route can spend), D105 (the markdown lives on Pricing) and D156 (one worklist). |
| `pricing-is-one-list-and-one-send` | Amends D208 (one Pricing verdict), D98 (the cheap-card figure) and D159 (the value band). Extends D105 (the markdown lives on Pricing). |
| `sales-is-a-leaderboard` | Amends D214 (a gross-revenue retrospective) and D217 (Sales as a tool). Moves the figure of D250 (unsold stock on Sales) up. |
| `orders-and-shipping-are-two-rows` | Amends the layout half of D220 (Orders is inventory's screen). |
| `a-moved-card-keeps-its-price` | Amends D165 (a run binds to the box's true index). |
| `a-card-is-counted-in-its-section` | Amends the display of D58 (a card's number counts the cards), D92 (a bare # is the count) and D155 (the section ruler). |
| `a-press-reorders-and-nothing-else-moves` | Amends D209 (a re-sort is a press) and the timing of D132 (sold is folded away). Extends D142 (the setup outlives the browser). |
| `one-forgiving-search-matcher` | Sets the first app-wide rule for search. |
| `a-section-is-an-object` | Amends D83 (a moved card). Keeps D31 (one owner-side view of stored cards). |
| `card-order-key` | Keeps the fixed index of D10 (the inventory model) and D58 (a card's number counts the cards). Proposes an order key, the orchestrator's inference. |
| `reasoning-is-not-screen-copy` | Amends D100 (nothing is deleted to lower a price), D168 (a typed price is cleared by a press), D134 (departed records are buried), D70 (the QR is the identification), D102 (the mark's spec), D86 (one pricing file for the store) and D225 (a sales truth). |
| `drawer-foot-joins-the-list` | Amends D204 (the drawer scrolls above its foot). |
| `a-box-is-shown-by-its-name` | Amends D145 (the box index nobody sees), D68 (the departed label) and the on-screen sigil of D92 (a bare # is the count). Keeps D20 (a box is an object). |

The round-one lanes write ten more: `one-page-width`, `notice-detail`, `page-scaffold`,
`palette-go-to`, `text-shape-checks`, `product-view-hybrid`, `home-owed-line`,
`capture-always-asks`, `sales-rows-by-sku` and `ship-lanes-collapse`.

**Duplicates to settle before merge.** The round-two lane plan was written after these entries.
It names lane entries that argue some of the same rulings:

| Lane entry | Same ruling as |
|---|---|
| `one-matcher` (filtering) | `one-forgiving-search-matcher` |
| `section-ruler`, `card-one-at-back`, `section-card-number` (locating) | `a-card-is-counted-in-its-section` |
| `nothing-jumps` (inventory), `orders-sort-press` (orders) | `a-press-reorders-and-nothing-else-moves` |
| `orders-walk-layout` (orders) | `orders-and-shipping-are-two-rows` |
| `sales-rows-by-sku` (sales) | overlaps `sales-is-a-leaderboard` |

One copy of each argument must go before either merges. The lane entries may still record what
their build adds.

## 5. The build plan

Each lane has one builder, its own worktree and its own branch. A reviewer follows each lane.
Screen lanes never edit the kit, the shell or another lane's files. A file passes from one wave
to a later wave only after its earlier owner merged, never inside a wave.

The second consolidation holds **272 findings**, UX-001 to UX-272. Each sits in exactly one
lane. The lanes that touch money, the live account, the store's transactions or safety use the
larger model tier.

| Wave | Lanes | Findings | What they do |
|---|---|---|---|
| 0, the foundation | kit-frame, kit-data, guards, pricing-clip, fulfillment, ports-safety | 48 | The page scaffold, overlays, the shared data parts, the kit adoption check, the Pricing price-field clip and the Cards to pull S1. Ports-safety stops a tree with no `.git` from reaching the live port. |
| 1 | shell, text-checks, product, demo, filtering, locating | 37 | The route table, the palette and drawer, the three text checks, the one product view, the demo's missing recordings, the one filter control and matcher, and the one place vocabulary. |
| 2, the screens | home, capture, sales, shipping, library, inventory, orders, review, search-server | 139 | Each screen moves onto the scaffold and the shared parts. Search-server makes the server matcher pass the shared case table. |
| 3 | docs-sweep | 0 | CLAUDE.md, README.md and DESIGN.md. |
| released | runs, then pricing | 47 | Section 6. |
| handed off | the token sweep after the UX PR | 1 | UX-157. |
| records | specs (this lane) | 0 | This document, the box map spec, the review record and the decision entries. |

What moved in round two:

- **Held screens.** The held lane is gone, because the photo branch merged. Three screen lanes
  replace it in wave 2: inventory, orders and review.
- **Filtering and locating moved to wave 1.** Both build shared parts the wave-2 screens must
  use. In wave 3 they would edit the same screen files twice.
- **Five new lanes:** ports-safety (wave 0), demo (wave 1), search-server (wave 2), and the
  three screen lanes. The orders lane carries HOR-04's stand-down fix as an item.
- **A cross-screen finding has one owner lane.** Each other lane lists it and does not open it
  again.
- **In wave 2, search-server owns the Makefile, `scripts/checks.py` and CLAUDE.md,** for one
  check target and its census line.

Wave 0 merges in this order: kit-data, then kit-frame, then guards. Every screen is checked at
1440, 820, 720 and 390, in both themes.

## 6. What was blocked, and what still waits

- **Runs and Pricing are released.** The owner released both once the Pricing re-interview and
  the flow interview were done. Both touch Pricing's write bar, so they run in sequence. The
  runs lane goes first (25 findings), with the send, live and reconcile plumbing. The pricing
  lane follows (22 findings), with the screen.
- **The Runs screen's final shape** (Q6) is decided after the send and live presses move to
  Pricing. Then the owner sees what is left and rules.
- **The box map.** Nothing is in a lane yet. Slice 0 of `docs/specs/box-map.md` is a safety fix
  that can ship first.

## 7. What is not decided yet

Six items are settled since the first version of this document. They are the Pricing
re-interview, the Sales direction, the double-send guard, the mark-down press, accents in
search, and the owner of the money check. Still open:

1. The transport check of D100 (nothing is deleted to lower a price). A listing file cannot pass
   it. The send rulings do not say what happens to it. The question goes to the owner.
2. Where the Send caps live, now that they are removed from beside Send.
3. The Runs screen's shape, after the moves land.
4. Where a $0.00 sale finds its real price: the order detail, the shipping export or another
   export. Measure first.
5. Three counts on the real store before Pricing is built: the rows that need the owner (Q2),
   the typed prices that follow one pattern (Q9), and the rows with no market price.
6. Which clock "most recent" reads for Home and Cards to pull.
7. Whether a search miss offers the closest name.
8. The form of the card order key.
9. The two box map defaults (section 4.11), shown to the owner.
10. The exact Orders layout once the walk takes the full height. The orders lane shows the owner
   first.
11. Five measurements the flow review listed before any send is built. The first touches the
   real TCGplayer account and needs the owner's word.
12. The duplicate entries in section 4.13.

### 7.1 An incident, and two findings, now in lanes

- **A scratch copy read the live store.** The held-Orders reviewer built main's app from a copy
  with no `.git`. Its API fell back to port 8000 and read the owner's live store once, by page
  load, with no press. The captures were deleted. A copied tree must never fall back to the
  main checkout's live port (D43, the port follows the store). The ports-safety lane fixes it
  in wave 0 and writes its own entry.
- **HOR-04 (S1).** "Stand down N orders" in a buyer's Manage sheet closes every open order
  before today, live Ready to Ship orders included. It shows no cutoff. That breaks D203 (the
  backlog is stood down over a cutoff the operator sees). The owner was warned. The orders lane
  carries the fix.
- **HOR-07.** Undo on a pull fails with `sold_origin_unknown` on a seeded store. The owner was
  asked to test it once on the real store.
- **A tooling defect.** `npx playwright test --list` writes `.serve/design-check.json` with a
  pass of 0 tests. A list run must not write the verdict file. It needs a guard, as a
  separate task.

## 8. The second consolidation

The second consolidation finished on 2026-09-23. It merged the 142 round-two findings (FLT,
LOC, HOR, HIR and one incident) into the first 164. The result is 272 findings, UX-001 to
UX-272: 9 S1, 74 S2, 138 S3 and 51 S4. Every round-one id is stable. `docs/reviews/ux-2026-09-23/CONSOLIDATED.md` is that second version. Section 5 carries
its lane addendum.
