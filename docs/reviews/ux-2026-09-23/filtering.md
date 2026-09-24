# Filtering, sorting, search and scope

Lens 8. Target: the published demo (`https://shivinate7.github.io/banchi/`, main at PR #454),
plus MY OWN capture server over a seeded demo store (`scripts/demo-seed.py` into
FLT scratch file, not kept, this checkout's own port 8170, `app/dist` built from this checkout).
The demo recording cannot answer three things that this lens needs, so I started that server.
The recording holds only 12 capitalised first words and the SKUs for free-text inventory search.
It holds no inventory facet counts. It does not hold `#/graveyard` at all. Every finding says
which target it was seen on. Shots from my server are under FLT screenshot, not kept.

Held screens: per the coordinator's change to the brief, `#/inventory`, `#/orders` and
`#/review` ARE graded for this lens. Every finding on them is marked "main state, re-check
after merge".

Owner's words: `"I feel like I had gripes in how we filter and such."`

## Filter inventory

"Remembered": R = survives reload and leaving the route. U = carried in the URL hash.
— = lost on reload and on leaving. Measured by reload, by leaving to another route and back,
and by reading every `banchi.*` key in localStorage and sessionStorage.

| Route | List it acts on | Control | Kind | Default | Remembered | Visible when active? | How you clear it | Empty result says |
|---|---|---|---|---|---|---|---|---|
| `#/` Home | none | tiles link to `#/orders`, `#/pricing`, `#/review`, `#/inventory?box=N`, `#/runs?run=` | nav | — | U (box, run) | n/a | n/a | n/a |
| `#/capture` | none (the pickers are capture claims, not filters) | — | — | — | — | — | — | — |
| `#/runs` | run list | none. `?run=` picks a run | scope (U) | first run | U | selected row | pick another | "Pick a run" |
| `#/runs` Identify sheet | cards to identify | Everything / Drawers / A previous run's cards | scope (segmented) | Everything | not measured | footer "Every card waiting to be identified" | Cancel | not reached |
| `#/runs` Identify sheet | same | Game "Any game", Section "Whole drawer", "Photographed since" + Today | select, select, period (native date-time) | any / whole / empty | not measured | the fields | reset by hand | not reached |
| `#/review` | review queue | six reason chips with counts | chip (single) | none (all 9) | — | pressed chip plus "× Every reason" | "Every reason" | not reached |
| `#/pricing` | pricing worklist | Runs popover ("Runs 1", "1 picked") | scope (multi) | newest run (Box 3) | — (reload returns to Box 3) | "Runs 1" and the subtitle "Box 3 · RB Epics" | "Show everything unsent" | not reached |
| `#/pricing` | same | "Holding 1" | toggle | off | — | pressed chip, and the OTHER rows dim | press again | n/a |
| `#/pricing` | same | Find by value, then `?band=top` | scope (route mode) | off | U | page title `What's worth pulling` | "Back to pricing" | "Nothing here has a price yet" (my server) |
| `#/pricing` | same | Compare | toggle (columns) | off | R (`banchi.pricing.compare`, per CLAUDE.md, not measured) | pressed | press again | n/a |
| `#/orders` | buyer rail | "All open (7) / Every copy found (15) / Short (6) / Done (0)" | select | All open | — | the select text | pick "All open", or "Show all open" in the empty state | "Nothing fulfilled yet. Pick another filter, or show every open order." |
| `#/orders` | buyer rail | Search buyers or order # | search (client) | empty | — | text in the field | × in the field, or "Clear search" | "No buyer matches. Nobody's name or order number contains “zzzz”." |
| `#/orders` | buyer rail | Status (Ready to ship (5) / Shipped (2)) | select (native) | none | R (`banchi.orders.fetch-filter`) | the select text on the desk, NOTHING on the phone | pick "Status" | not reached |
| `#/orders` | buyer rail | Newest / Oldest | sort (segmented) | Newest | R | pressed half, but see FLT-01 | n/a | n/a |
| `#/orders` | buyer rail | Hide never-seen SKUs | toggle (native checkbox) | off | R | the tick only, no count | untick | not reached |
| `#/orders` | the walk | Hide sold | toggle (pill with count) | on | R (`banchi.inventory.hide-sold`, shared with Inventory) | pill with count | press | "Nothing to walk…" |
| `#/orders` | selection | `?buyer=` | scope (U) | first row, auto-written | U | selected row | pick another | "Choose a buyer on the left." |
| `#/shipping` | three lanes, 331 orders | Envelope / Parcel / Needs a look | toggle ×3 (lane cards) | all on | — | "166 orders folded away" | press again | n/a |
| `#/revenue` Sales | month strip and product table | 3 months / 6 months / This year / All time / Custom (From, To date fields) | period (segmented) | 6 months | U `?period=`, `&from&to` | pressed segment, headline "over 6 months" | pick another | n/a |
| `#/revenue` | product table | a month row | scope (row button) | none | U `&month=` | tinted row + chip "Aug 2026 only × Clear" | Clear | same as search |
| `#/revenue` | product table | Find what you sold | search (client, name only) | empty | U `&q=` | text in field | × | "Nothing sold under that name in this period." |
| `#/revenue` | product table | Name / Copies / Gross / Last sold | sort (headers) | Gross, high first | U `?sort=&dir=` | a chevron on every header | click again | n/a |
| `#/revenue` | shelf chart | Month / Quarter / 6 months / Year | period bucket (segmented) | Month | not measured | pressed segment | n/a | n/a |
| `#/inventory` | box rail and walk | Card name, number or SKU | search (server, 200 ms debounce) | empty | — | text, the rail says "N match", and "1 here · 1 of 42 match" | × in the field, or "Clear the search" | "Nothing matches “zzzz”. Searches name, number, SKU, set, note." (drawn twice) |
| `#/inventory` | box rail and walk | Game "(37)/(85)", Set, Rarity | select ×3 | none | — | select text, and the rail says "28 matches" or "0 matches" (my server) | "Clear filter" | "Nothing here matches the filter" |
| `#/inventory` | the walk | Hide sold | toggle (pill with count) | on | R (`banchi.inventory.hide-sold`) | pill + count | press | n/a |
| `#/inventory` | box rail | box row, `?box=N` | scope | last box | U + R (`banchi.box-recency` re-orders the rail) | selected row | pick another | n/a |
| `#/graveyard` (my server) | departed table | All (22) / Sold (19) / Retired (2) / Moved (1) / Buried (0) | segmented with counts | All | — | pressed segment | press All | "Nothing matches. No departed card matches those filters." (no action) |
| `#/graveyard` (my server) | same | Find a card, SKU or box | search (client, raw input) | empty | — | text | the browser's own × | same |
| `#/codes` | ledger | state chips, lane chips, search, reveal (read from `Codes.tsx`) | chip, search | — | not measured | not seen | not seen | not seen: the ledger is empty on both targets |
| `#/fulfillment` | card finder | Type the name of the card | search (server) | empty | — | results | clear the field | "No card here has that name. Check the spelling." (my server) |
| `#/gallery` | kit samples | Segmented, SearchField, Newest/Oldest | kit | — | — | — | — | — |
| `#/product` | one product | TCGplayer SKU field and its button | scope (U `?sku=`) | empty | U | the SKU | edit the field | "Enter a SKU to see its history." |

Search timing (input event to the last change of `main`, `performance.now()`):
- `#/revenue` has the longest client-filtered list with a search in the demo (21 rows). It
  takes 8–13 ms to two animation frames, every query.
- `#/inventory` on my server (122 cards): 430–445 ms to a settled list when there is a match,
  about 212 ms when there is none. The first 200 ms is the fixed debounce. Unmeasured on the
  owner's real store (about 2,500 cards).
- The demo has no long searchable list. Shipping's 331 orders is the longest list, and it has
  no search.

## Grade matrix

| Route | Grade | One-line reason |
|---|---|---|
| `#/` Home | C | Tiles name a narrowed problem ("6 copies cannot be found", "2 runs to price") and land on an unfiltered list. |
| `#/capture` | n/a | No list to filter. Its pickers are claims, graded only in the gripe section. |
| `#/runs` | B | The Identify scope sheet is clear, but it says "Any game" and "drawer" where other screens say "Game" and "box", and it uses a native date-time field. |
| `#/review` | B | One chip strip with counts and a clear, but "Card 1 of 9" ignores the filter and nothing is remembered. Main state, re-check after merge. |
| `#/pricing` | C | Scope is a popover that forgets on reload, "Holding" dims instead of filtering, and a price-rule control looks exactly like a filter. |
| `#/orders` | D | The sort toggle does not sort, the filter counts use a different unit from the rows, one filter is remembered invisibly, and search misses the label on the row. Main state, re-check after merge. |
| `#/shipping` | C | Lane toggles are clear and say what they fold, but 331 orders have no find, and nothing is remembered. |
| `#/revenue` | B | The best filter screen: URL deep links, a visible "Aug 2026 only × Clear" chip. It loses marks for a literal name-only search and a headline that ignores the month. |
| `#/inventory` | C | Facets with per-box counts work on the real server. But Set and Rarity lock until Game is chosen, counts include sold, only Hide sold is remembered, and number search needs leading zeros. Main state, re-check after merge. |
| `#/graveyard` | C | Segmented filter and search work, but the search misses text drawn on its own rows, counts ignore the search, and the field is not the kit's. |
| `#/codes` | UNKNOWN | Empty ledger on both targets. Filters exist in code, not seen. |
| `#/fulfillment` | B | One forgiving name search with plain empty states. It cannot find a card by its printed number. |
| `#/gallery` | C | The kit has Segmented, Chip and SearchField, but no filter-bar pattern, so each screen invents one. |
| `#/product` | C | The only way in is a SKU typed by hand. A card name is refused. |

## Findings

### FLT-01 Orders: the Newest/Oldest press does not re-order the list
- Severity: S1
- Screens: `#/orders`
- Where: all (seen 1440/light, demo)
- Repro: open `#/orders`. Read the order of the rail: 00012 (placed Sep 3), 00011 (Sep 2), 00010 (Aug 31), 00013 (Aug 30), 00009 (Aug 28), 00008 (Sep 3), 00007 (Aug 28). Press "Oldest".
- Seen: "Oldest" shows pressed and the list does not move. A new chip appears, "Order is 6 buyers stale, re-sort", and only that press re-orders. The default "Newest" order already puts a Sep 3 order sixth, below four August orders. The toggle states an order that the list does not have.
- Shot: FLT-01, screenshot not kept.
- Direction: a sort press re-orders at once. If the order must freeze during a walk, the toggle must not claim a sort that is not applied.
- Component: `app/src/Orders.tsx` rail toolbar (`searchSlot`), `app/src/orderView.ts` freeze (`sortGroups`)
- Annotation: caused by D209 (the buyer list leads with Ready to Ship, and a re-sort is a press). D209 rules that a changed SORT only offers the `re-sort` chip, extending D181 (the order is taken once). The Sort toggle IS the explicit press that D209's own title names, so the entry argues against itself here. D209 also puts Ready to Ship first, which is why `Newest` shows a Sep 3 order sixth, and the screen never says so. no prior.
- Main state, re-check after merge.

### FLT-02 Orders: "Every copy found" lists orders marked Short
- Severity: S2
- Screens: `#/orders`
- Where: all (1440/light, demo)
- Repro: `#/orders`, pick "Every copy found (15)" in the first select.
- Seen: 6 buyers show. 08-28-26_00009 and 09-03-26_00008 carry an orange "Short · 7 owed" badge under a filter that says every copy was found. The filter and the row badge contradict.
- Shot: FLT-02, screenshot not kept.
- Direction: a filter named for a state shows only rows in that state. If not, name it for what it selects ("has a found line").
- Component: `app/src/Orders.tsx` (`chips` select)
- Annotation: no decision covers this. no prior.
- Main state, re-check after merge.

### FLT-03 Orders: filter counts are lines, the list is buyers
- Severity: S2
- Screens: `#/orders`, `#/` Home
- Where: all
- Repro: `#/orders`, open the first select: "All open (7) / Every copy found (15) / Short (6) / Done (0)". Pick "Short (6)".
- Seen: "Short (6)" shows 3 rows. "Every copy found (15)" shows 6. "All open (7)" counts buyers and the next two count lines, in one menu. Home says "27 copies to pull", and the header says "21 lines across 7 buyers": three units for one pile.
- Shot: FLT-03, screenshot not kept.
- Direction: each option's count is the number of rows the list will show, in one unit.
- Component: `app/src/Orders.tsx` (`chips`)
- Annotation: no decision covers this. prior: ux-2026-09-20/orders.md (the header count wording, a different defect on the same line).
- Main state, re-check after merge.

### FLT-04 Search needs the leading zeros of a collector number
- Severity: S2
- Screens: `#/inventory`, `#/fulfillment`
- Where: all (my server, and the matcher run directly over the seeded store)
- Repro: `#/inventory`, type `54/132`. Then type `054/132`.
- Seen: `54/132` finds nothing. `054/132` finds Abra. `12/219` misses `012/219`, and a bare `54` misses too. A collector reads "54/132" off the card. The Fulfiller's search answers "No card here has that name" to `54/132`.
- Shot: FLT-04, screenshot not kept.
- Direction: a number typed with or without zero padding finds the card.
- Component: `server/capture_server.py:_match_rank`, `_fts_query` (screen: `app/src/BoxBrowse.tsx` search)
- Annotation: no decision covers this. The cause is the FTS5 candidate step of the store-scaling work (`docs/specs/store-scaling.md`, item 8). `do_search`'s own comment names the `4/102` split and accepts it. Before that step, a substring walk found `54/132` inside `054/132`. no prior.
- Main state, re-check after merge.

### FLT-05 Search drops a hyphen or an accent spelling
- Severity: S3
- Screens: `#/inventory`, `#/fulfillment`
- Where: all (my server). The accent case was measured by calling `_match_rank` and an FTS5 table directly, not seen on screen.
- Repro: `#/inventory`, type `heimerdinger-inventor`. Also type `flabebe` for a card named Flabébé.
- Seen: `heimerdinger inventor` finds the card, and `heimerdinger-inventor` finds nothing. For accents, the index finds Flabébé for `flabebe`, then the rank step drops it, so the screen shows nothing. Mid-word text (`ventor`) also finds nothing. Typos (`bosss`, `exegcute`) find nothing, and nothing suggests a near match.
- Shot: FLT-05, screenshot not kept.
- Direction: punctuation and accents fold the same way on both sides. A miss offers the closest name.
- Component: `server/capture_server.py:do_search` (per-term `_match_rank` after FTS)
- Annotation: no decision covers this. Same cause as FLT-04: the index folds accents and the rank step does not. no prior.
- Main state, re-check after merge.

### FLT-06 Four search fields, four rules for what matches
- Severity: S2
- Screens: `#/inventory`, `#/revenue`, `#/graveyard`, `#/orders`
- Where: all
- Repro: search the same card on each screen. Sales: `akali deadly`. Graveyard (my server): `boss orders`, `B4`, `damaged`.
- Seen: Inventory matches each word anywhere (name, number, SKU, set, note). Sales matches the literal string in the name only. There, `akali deadly` fails and `akali, deadly` works, and a SKU or number finds nothing although the field is labelled "Search cards". Graveyard matches the literal string over name, number, SKU, box name and order. There, `boss orders` fails, and `B4` and `Damaged` find nothing although its rows draw both and the placeholder promises "box". Orders matches buyer name and the hidden TCGplayer number.
- Shot: FLT-06, screenshot not kept.
- Direction: one matching rule everywhere: every word, any order, case, accent and punctuation folded, over every field the row draws.
- Component: `app/src/Revenue.tsx` (row filter), `app/src/Graveyard.tsx` (`visible`), `app/src/orderView.ts:passesQuery`, `server/capture_server.py:do_search`
- Annotation: caused in part by D214 (a gross-revenue retrospective is its own route), which scopes Sales to names. No decision sets one matching rule for the app. no prior.
- Main state for Inventory and Orders, re-check after merge.

### FLT-07 Orders: the label drawn on the row cannot be searched
- Severity: S2
- Screens: `#/orders`
- Where: all (demo)
- Repro: `#/orders`, type `09-03-26` or `09-03-26_00012`. The first row draws both.
- Seen: "No buyer matches". Only the TCGplayer number (`00012`, `a2ffc195-256158`) matches, and the row does not draw it. A space in place of the hyphen (`A2FFC195 256158`) also fails.
- Shot: FLT-07, screenshot not kept.
- Direction: what the row shows is what the search finds.
- Component: `app/src/orderView.ts:passesQuery`
- Annotation: caused by D220 (Orders is inventory's screen), which composes the `MM-DD-YY_XXXXX` label from the placed date. The search predates the label and was not taught it. no prior.
- Main state, re-check after merge.

### FLT-08 No search result shows what matched
- Severity: S3
- Screens: `#/inventory`, `#/revenue`, `#/graveyard`, `#/orders`, `#/fulfillment`
- Where: all
- Repro: `#/inventory`, type `Hextech`. `#/revenue`, type `premo`.
- Seen: no highlight on any screen. When the match is on a SKU, set hint or note, the row shows no reason why it is in the list.
- Shot: FLT-08, screenshot not kept.
- Direction: mark the matched text. Name the field that matched when the row does not draw it.
- Component: each list row. No shared primitive exists.
- Annotation: no decision covers this. no prior.

### FLT-09 Inventory: Set and Rarity are locked until Game is chosen
- Severity: S2
- Screens: `#/inventory`
- Where: all (demo and my server)
- Repro: `#/inventory`, open the Set select before you choose a Game.
- Seen: Set and Rarity are `disabled`, drawn at 0.7 opacity with a not-allowed cursor, and give no reason. After a game is chosen, Set offers only "No set on file (37)". The facets work in one order only.
- Shot: FLT-09, screenshot not kept.
- Direction: every facet is usable in any order and narrows the options and counts of the others.
- Component: `app/src/BoxBrowse.tsx` facet selects (`disabled={facetFilter.game === undefined}`)
- Annotation: no decision covers the lock. The facet read keys sets and rarities per game, so the select has no options until a game is chosen. D213 (the set is a stored fact) chose a dropdown on the owner's word "for standardization across card games", and the lock works against that aim. no prior.
- Main state, re-check after merge.

### FLT-10 Inventory: filter counts include sold cards while the list hides them
- Severity: S3
- Screens: `#/inventory`
- Where: all (my server)
- Repro: `#/inventory` with Hide sold on. Pick Game "Pokémon (37)", then pick box Mixed Singles.
- Seen: the rail says "9 matches", and the walk shows "7 cards". "Pokémon (37)" and "Riftbound (85)" add up to 122, every card ever captured, sold and moved included. The header says "122 cards" where Home says "100 on hand".
- Shot: FLT-10, screenshot not kept.
- Direction: a count beside a filter is the number of rows it will show under the other active filters.
- Component: `app/src/BoxBrowse.tsx` (`facetMatchesByShelf`), server `_box_row` matches
- Annotation: no decision covers the count basis. D132 (sold is folded away by default) hides sold rows, and D213's counts were not told. no prior.
- Main state, re-check after merge.

### FLT-11 What a screen remembers is different on every screen
- Severity: S2
- Screens: `#/inventory`, `#/orders`, `#/review`, `#/graveyard`, `#/shipping`, `#/pricing`, `#/revenue`
- Where: all
- Repro: set every filter on each screen, reload, then leave and come back.
- Seen: Sales keeps everything in the URL. Orders keeps Status, sort and Hide never-seen in localStorage, but forgets its first select and its search. Inventory keeps only Hide sold. It loses game, set, rarity and search on reload AND on a visit to one other route. Pricing's run scope returns to the newest run on reload. Review, Graveyard and Shipping keep nothing. No screen says that it restored a filter.
- Shot: FLT-11, screenshot not kept.
- Direction: one rule for all screens. A narrowed view lives in the URL, so reload, back and a shared link all restore it.
- Component: per screen. No shared filter-state hook exists.
- Annotation: no single decision. D217 (Sales becomes a tool) makes the URL the one copy of that screen's state. D209 put Orders' view in localStorage on D142's precedent (the setup outlives the browser). Two rulings give two mechanisms on two screens, and five screens have none. no prior.
- Main state for the held screens, re-check after merge.

### FLT-12 Orders: a remembered Status filter is invisible on the phone
- Severity: S2
- Screens: `#/orders`
- Where: 390/light (demo)
- Repro: at 1440 pick Status "Shipped". Open `#/orders` at 390.
- Seen: the phone shows one collapsed row, "09-03-26_00008", with no word that the list holds only 2 of 7 buyers. The filter shows only inside the picker sheet. On the desk the header still reads "21 lines across 7 buyers".
- Shot: FLT-12, screenshot not kept.
- Direction: an active filter shows on the collapsed control ("Shipped · 2 of 7"), with a clear.
- Component: `app/src/Orders.tsx` phone rail sheet
- Annotation: caused by D209 (the view is stored with the fetch filter) and D220 (the phone rail chip shows only the selected buyer). No decision covers showing an active filter on a phone. no prior.
- Main state, re-check after merge.

### FLT-13 A filtered list never says how many it hides
- Severity: S2
- Screens: `#/orders`, `#/review`, `#/graveyard`, `#/revenue`
- Where: all
- Repro: `#/review`, press "Not in the export 3". `#/graveyard` (my server), type `raboot`. `#/revenue`, press a month row.
- Seen: Review still says "Card 1 of 9". Graveyard's segments still say "All (22) Sold (19)" over 1 row. The Orders header stays "21 lines across 7 buyers" under every filter. The Sales headline stays "over all time, across 7 orders" while the table shows August only.
- Shot: FLT-13, screenshot not kept.
- Direction: every narrowed list states "N of M". The headline follows the scope or says that it does not.
- Component: `app/src/ReviewQueue.tsx` header, `app/src/Graveyard.tsx` toolbar, `app/src/Orders.tsx` header, `app/src/Revenue.tsx` verdict
- Annotation: the Sales half is caused by D217, which keeps "the verdict and the chart" scoped to the whole period and narrows only the table. That ruling is an argument, and here it reads as a wrong total. The Review, Graveyard and Orders halves: no decision covers this. prior: ux-2026-09-20/graveyard.md (finding 6, segment counts, a related defect).
- Main state for Review and Orders, re-check after merge.

### FLT-14 Home's tiles land on unfiltered lists
- Severity: S2
- Screens: `#/`, `#/orders`, `#/pricing`
- Where: all (demo)
- Repro: on `#/` press "Cannot be filled — 6 copies for 7 open orders cannot be found." Then press the PRICING tile ("2 runs to price").
- Seen: the first lands on `#/orders` with "All open (7)", not "Short". The PRICING tile lands on a worklist with "Runs 1" (Box 3 only). The link names the narrowed thing and does not narrow to it.
- Shot: FLT-14, screenshot not kept.
- Direction: a link that names a subset opens the list filtered to that subset, and the filter says so.
- Component: `app/src/Home.tsx` links. The targets need a URL-carried filter first (FLT-11).
- Annotation: no decision covers where a Home link lands. The Pricing half violates D156 (every copy TCGplayer does not hold is one worklist) as the demo draws it, because D156 makes every unsent copy the default landing. Not reproduced on my server, which has no joined run, so it can be a recording gap. no prior.

### FLT-15 One idea, "pick a category and see how many", drawn four ways
- Severity: S2
- Screens: `#/inventory`, `#/orders`, `#/graveyard`, `#/review`, `#/shipping`
- Where: all
- Repro: compare Inventory's Game select, Orders' first select, Graveyard's segments, Review's chips and Shipping's lane cards.
- Seen: Inventory and Orders use a native select with "(37)". Graveyard uses a segmented bar with "(19)". Review uses a wrapping chip strip with a count badge and a "× Every reason" clear. Shipping uses three large toggle cards that are multi-select. The clear is "Clear filter" (Inventory), "Show all open" (only in Orders' empty state), "Every reason" (Review), a press on "All" (Graveyard), and a second press on the card (Shipping).
- Shot: FLT-15, screenshot not kept.
- Direction: one filter control for "one of N categories with counts", and one place for clear.
- Component: kit `Segmented` and `Chip`, the `bn-select` CSS, and the toolbar of each screen
- Annotation: caused by D213 and D220, both of which chose a native dropdown on the owner's word for one screen each. No decision sets one filter control for the app. no prior.

### FLT-16 "Hide X" is three different controls
- Severity: S3
- Screens: `#/inventory`, `#/orders`, `#/pricing`
- Where: all
- Repro: compare Inventory's "Hide sold 8", Orders' "Hide never-seen SKUs" and Pricing's "Holding 1".
- Seen: Hide sold is a black pill with a count. Hide never-seen is a 13 px native checkbox with no count. Holding is a blue chip that DIMS every other row and hides nothing. On Orders, "Hide sold" and "Hide never-seen SKUs" sit on one screen as two different controls.
- Shot: FLT-16, screenshot not kept.
- Direction: one toggle control for "hide or show a kind of row", with a count of what it hides.
- Component: `app/src/BoxBrowse.tsx`, `app/src/Orders.tsx`, `app/src/Pricing.tsx`
- Annotation: caused by D132 (the `Hide sold` chip) and D209 (the `Hide unknown SKUs` toggle), two entries that each drew their own toggle. prior: ux-2026-09-20/pricing.md (finding 5, the Holding pill's geometry).
- Main state for Inventory and Orders, re-check after merge.

### FLT-17 Pricing: "Holding" dims the list instead of showing the held rows
- Severity: S3
- Screens: `#/pricing`
- Where: 1440/light (demo)
- Repro: `#/pricing`, press "Holding 1".
- Seen: all 29 rows stay. Every row dims except Astral Heron, which is at y≈1,518, below the fold. The press gives no sign of where the held row is.
- Shot: FLT-17, screenshot not kept.
- Direction: the held rows come to the top, or the others go.
- Component: `app/src/Pricing.tsx` (Holding chip)
- Annotation: no decision covers this. D49 (a card can be held) defines the hold, not how the list shows it. no prior.

### FLT-18 A price rule and a period filter are the same control
- Severity: S3
- Screens: `#/pricing`, `#/revenue`
- Where: all
- Repro: compare Pricing's "Match market / Market −5% / TCG Low −1% / Custom" with Sales's "3 months / 6 months / This year / All time / Custom".
- Seen: the two segmented bars are identical, and both end in "Custom". On Sales it narrows a view. On Pricing it changes the prices written. Sales also has two segmented bars that both offer "6 months", one a period filter and one a chart bucket.
- Shot: FLT-18, screenshot not kept.
- Direction: a control that writes looks different from one that only narrows.
- Component: kit `Segmented` in `app/src/Pricing.tsx` and `app/src/Revenue.tsx`
- Annotation: no decision covers this. no prior.

### FLT-19 Sort: the current order is hard to see, and most tables cannot sort
- Severity: S3
- Screens: `#/revenue`, `#/graveyard`, `#/pricing`, `#/inventory`, `#/orders`
- Where: all
- Repro: `#/revenue`, look at the table headers.
- Seen: every header carries a chevron. Only `aria-sort` tells that Gross is the active column. The Graveyard and Pricing tables have no sort at all. Orders sorts by a Newest/Oldest toggle. The Inventory walk has no sort control.
- Shot: FLT-19, screenshot not kept.
- Direction: one sort affordance on every table, with the active column clearly marked.
- Component: `app/src/Revenue.tsx` header buttons
- Annotation: D217 set the `aria-sort` shape for Sales, and the visual marks every column. No decision covers sort on the other tables. no prior.

### FLT-20 Graveyard's search is not the kit's search field
- Severity: S3
- Screens: `#/graveyard`
- Where: 1440/light (my server)
- Repro: `#/graveyard`, type `zzzz`.
- Seen: no search icon, no `/` key cap, and the browser's own bright blue ×. The field sits far right, away from the segments that it combines with. The empty state has no clear action, while Inventory and Orders offer one.
- Shot: FLT-20, screenshot not kept.
- Direction: use the shared search field and the shared empty state with a clear.
- Component: `app/src/Graveyard.tsx` (raw `<input className="bn-input graveyard-search">`)
- Annotation: no decision covers this. D134 (a departed record is buried) defines the screen, not its field. no prior.

### FLT-21 Inventory: a press on a box moves it to the top of the rail
- Severity: S3
- Screens: `#/inventory`
- Where: 1440/light (my server)
- Repro: with a Game filter on, press Mixed Singles, the fourth row.
- Seen: Mixed Singles jumps to the first row, and the row under the pointer is now a different box. A second press there opens the wrong box.
- Shot: FLT-21, screenshot not kept.
- Direction: the rail order does not change under the pointer. Re-order it on the next visit.
- Component: `app/src/BoxBrowse.tsx` rail (`banchi.box-recency`)
- Annotation: caused by D132 ("sort them by most recently clicked") and D142 (the box list is ordered by the hand). The rulings ask for recency order on arrival. Neither needs the rail to re-order under the pointer at the press. no prior.
- Main state, re-check after merge.

### FLT-22 Inventory: after a sale, the next click moves the list under the pointer
- Severity: S2
- Screens: `#/inventory`
- Where: 1440/light (my server)
- Repro: `#/inventory`, Box 1, Hide sold on. Press Mark sold on #1 Piercing Light. Press #2 Gentle Gemdragon.
- Seen: at that click the sold row folds away, and every row below moves up 32 px (Gentle 819 → 787, Bellows 851 → 819). The row that the owner just pressed slides away from the pointer.
- Shot: FLT-22, screenshot not kept.
- Direction: a departed row folds away at a moment when nothing under the hand depends on its place, for example the next box load. It never folds at the click.
- Component: `app/src/BoxBrowse.tsx` (`visible`, the Hide sold fold)
- Annotation: caused by D132 ("the row goes the moment the walk steps off it"), and it violates D118 (a press changes what is on the screen, never where the rest of it is). Two decisions conflict here, and the owner has to pick. no prior.
- Main state, re-check after merge.

### FLT-23 The demo draws two filter states the product does not have
- Severity: S3
- Screens: `#/inventory` (demo only)
- Where: demo, all widths
- Repro: demo `#/inventory`, pick Game "Pokémon (37)".
- Seen: every box in the rail goes grey and disabled, with no "matches" count. The card panel says "Nothing in Box 1 yet — capture a card into this one" for a box of 42. My server shows "28 matches / 0 matches" and jumps to MEG Bulk. On the demo, Mark sold also leaves the box walk unchanged ("34 on hand", Hide sold 8), while Home moves to 99 on hand. This is not a refusal. The demo shows a broken filter to anyone who opens the link.
- Shot: FLT-23, screenshot not kept.
- Direction: record the facet counts and patch the box walk on a sale, or refuse by name.
- Component: `app/src/demoServer.ts`, `scripts/demo-record.py`
- Annotation: no decision covers this (the demo rules live in `docs/specs/demo.md`). no prior.

### FLT-24 Orders: the filter block pushes the buyer list to four rows
- Severity: S3
- Screens: `#/orders`
- Where: 1440/light and 820/light (demo)
- Repro: `#/orders` at 1440×900.
- Seen: five controls in four rows take y 217–400 above the list. The buyer list is a scroll box that shows 4 of 7 buyers. The controls have four widths: first select 168 px, search 300 px, Status 141 px, Newest/Oldest about 136 px. A native checkbox follows.
- Shot: FLT-24, screenshot not kept.
- Direction: one row of equal-height controls, or a single "Filter" control that opens them. The list gets the height.
- Component: `app/src/Orders.tsx` (`searchSlot`, `orders-rail-toolbar`)
- Annotation: caused by D220, amended 2026-09-19 ("the filter strip became a native dropdown on the owner's word"), and D209 (one strip of Status, Sort and Hide unknown). The owner now dislikes the result (gripe 3 below). no prior.
- Main state, re-check after merge.

### FLT-25 Orders: ticked orders a filter hides drop out of the walk without a word
- Severity: S2
- Screens: `#/orders`
- Where: 1440/light (my server)
- Repro: `#/orders`, press "Tick shown" (7 ticked). Pick "Short (6)".
- Seen: 3 ticked rows stay visible. The walk goes from 8 sections and 21 cards to 7 sections and 12 cards. Nothing says that 4 ticked orders are now outside the walk. They come back when the filter is cleared.
- Shot: FLT-25, screenshot not kept.
- Direction: the walk states what it covers ("3 of 7 ticked orders, 4 hidden by Short").
- Component: `app/src/Orders.tsx`, `app/src/OrdersWalkPane.tsx`
- Annotation: no decision covers what a filter does to ticked orders. D220 rules that a tick widens the walk live. no prior.
- Main state, re-check after merge.

### FLT-26 Product history is reached only by a SKU
- Severity: S2
- Screens: `#/product`
- Where: all (demo and my server)
- Repro: `#/product`, type `boss`, press the `Look up` button.
- Seen: "No card in this store has ever carried SKU boss." A person knows the name, not the 7-digit SKU. No screen in the demo links a name into this view.
- Shot: FLT-26, screenshot not kept.
- Direction: the field finds a product by name or number and offers the matches.
- Component: `app/src/ProductHistory.tsx`
- Annotation: caused by D227 (a route, not a lens), which makes the SKU the grain "never a name" because a name can cover more than one printing. That premise argues for a picker of printings, not for a field that refuses names. The owner's 2026-09-23 hybrid ruling (a sheet from every product name) reaches most of it. no prior.

### FLT-27 Shipping: 331 orders and no way to find one
- Severity: S3
- Screens: `#/shipping`
- Where: all (demo)
- Repro: `#/shipping`, look for order `A2FFC195-000078-00348`.
- Seen: three lanes of cards, no search, no sort. The lane toggles fold a lane and show "166 orders folded away", which is good, but they forget it on reload.
- Shot: FLT-27, screenshot not kept.
- Direction: the stage that shares a screen with Orders gets the same search.
- Component: `app/src/Shipping.tsx`, `app/src/OrdersShipStage.tsx`
- Annotation: no decision covers search on the lanes. D61 (the shipping lane is three lanes) defines the lanes only. no prior.

### FLT-28 The palette does not find cards
- Severity: S3
- Screens: the palette (⌘K) on every route
- Where: 1440/light (demo)
- Repro: ⌘K, type `abra`.
- Seen: "Nothing matches “abra”." The palette searches screen names only. To find a card you must first go to Inventory.
- Shot: FLT-28, screenshot not kept.
- Direction: the palette answers a card name with the card's place.
- Component: `app/src/App.tsx` palette (`goTo` commands)
- Annotation: caused by D95 (the shell is a rail, a palette and a reference sheet), which scopes the palette to routes and screen verbs. The owner's 2026-09-23 ruling wants card search in the palette. no prior.

### FLT-29 The Identify scope says it differently from the rest of the app
- Severity: S3
- Screens: `#/runs`
- Where: 1440/light (demo)
- Repro: `#/runs`, press "Identify cards".
- Seen: the unset game reads "Any game" here and "Game" on Inventory. The scope says "Drawers" and "Whole drawer" where every other screen says "box". "Photographed since" is a native date-time field (`mm/dd/yyyy, --:-- --`). Sales's Custom range uses two date-only fields.
- Shot: FLT-29, screenshot not kept.
- Direction: one word for a box, one label for "not narrowed", one date control.
- Component: `app/src/RunsComposer.tsx`
- Annotation: violates the owner's 2026-09-23 ruling ("box" everywhere on screen). D180 (a selection of cards) defines the scope grammar. no prior.

### FLT-30 Sales: month rows do not look pressable, and the current month looks picked
- Severity: S3
- Screens: `#/revenue`
- Where: all
- Repro: `#/revenue`, look at "Sep 2026 ongoing" and "Aug 2026".
- Seen: the rows are filter buttons with no press affordance. Sep 2026 is bold beside a regular Aug 2026. That reads as selected when nothing is selected.
- Shot: FLT-30, screenshot not kept.
- Direction: the month strip reads as a picker, and weight does not stand in for "ongoing".
- Component: `app/src/Revenue.tsx` month strip
- Annotation: D217 made each month row a `button aria-pressed` and added the "ongoing" pill. No decision covers the weight. no prior.

### FLT-31 Inventory: the phone filter sheet overlaps the box summary
- Severity: S3
- Screens: `#/inventory`
- Where: 390/light (demo)
- Repro: at 390, press "Box 1 (RB Origins)", then pick a Game.
- Seen: after "Clear filter" appears, the rail card draws over the box summary. "Nothing running · Run box 1" is cut in half under it.
- Shot: FLT-31, screenshot not kept.
- Direction: the sheet reflows when the clear row appears.
- Component: `app/src/BoxBrowse.tsx` phone sheet
- Annotation: no decision covers this. no prior.
- Main state, re-check after merge.

### FLT-32 Inventory: "nothing matches" is said twice
- Severity: S4
- Screens: `#/inventory`
- Where: 1440/light (my server)
- Repro: `#/inventory`, type `zzzz`.
- Seen: the list says "Nothing matches here… Clear the search". The card panel says "Nothing matches “zzzz”… Clear the search". Two clears.
- Shot: FLT-32, screenshot not kept.
- Direction: one empty state, one clear.
- Component: `app/src/BoxBrowse.tsx`
- Annotation: no decision covers this. no prior.
- Main state, re-check after merge.

### FLT-33 Inventory: the rail labels change meaning between search and facet
- Severity: S4
- Screens: `#/inventory`
- Where: 1440/light (my server)
- Repro: type `Hextech`. Then clear it and pick a Game.
- Seen: under a search, a box with no match still says "25 on hand" in grey. Under a facet it says "0 matches". Same rail, same question, two labels.
- Shot: FLT-33, screenshot not kept.
- Direction: one label for "no match here".
- Component: `app/src/BoxBrowse.tsx` rail cell meta
- Annotation: no decision covers this. no prior.
- Main state, re-check after merge.

### FLT-34 Sales: the no-result sentence has no clear and ignores the month
- Severity: S4
- Screens: `#/revenue`
- Where: 1440/light (demo)
- Repro: `#/revenue`, press Aug 2026, type `zzzz`.
- Seen: "Nothing sold under that name in this period." No clear action. The narrower scope is the month, and the sentence does not name it.
- Shot: FLT-34, screenshot not kept.
- Direction: name the scope and offer the clear.
- Component: `app/src/Revenue.tsx`
- Annotation: no decision covers this. no prior.

### FLT-35 Sales: the period control wraps unevenly on a phone
- Severity: S4
- Screens: `#/revenue`
- Where: 390/light
- Repro: `#/revenue` at 390.
- Seen: the five periods wrap 3 + 2, with "All time / Custom" left-aligned under a full first row. The search is below the fold.
- Shot: FLT-35, screenshot not kept.
- Direction: a single-line control on a phone (a scroll or a select).
- Component: `app/src/Revenue.tsx` period `Segmented`
- Annotation: no decision covers this. no prior.

### FLT-36 Inventory search waits 200 ms before it asks
- Severity: S4
- Screens: `#/inventory`, `#/fulfillment`
- Where: all (my server)
- Repro: type a name and time it.
- Seen: about 430 ms from keystroke to a settled list on 122 cards, and 200 ms of it is a fixed wait. Client-side searches (Sales) answer in about 10 ms. It is not slow, but two screens feel visibly different.
- Shot: FLT-36, screenshot not kept.
- Direction: measure on the owner's store before you choose the wait.
- Component: `app/src/useSearch.ts` (`SEARCH_DEBOUNCE_MS`)
- Annotation: no decision covers this. `useSearch.ts` marks the 200 ms as an unmeasured assumption. no prior.
- Main state, re-check after merge.

### FLT-37 Orders: the header counts owed lines against every buyer ever seen
- Severity: S2
- Screens: `#/orders`
- Where: all (read from the code and from my server's `/orders` payload. The owner's live figure "611 lines across 806 buyers" was reported, not seen.)
- Repro: open `#/orders` on a store where some buyers have only finished orders.
- Seen: `summaryOf` adds the lines of every record that still owes copies (the server's `resolve_keys = ledger.unfulfilled()`). `buyerCount` groups EVERY order in the payload, finished ones included (`groupBuyers(payload.orders)`, recent plus earlier). The two numbers count different sets, so the header can say fewer lines than buyers. On the demo all 7 orders are open, so the fault does not show there.
- Shot: FLT-37, screenshot not kept.
- Direction: both numbers count the same orders, for example "611 lines owed to N buyers", with N taken from the orders that own those lines.
- Component: `app/src/Orders.tsx` (`summaryOf`, `buyerCount`), `server/capture_server.py` orders route (`resolve_keys`)
- Annotation: no decision covers this. The buyer count came from the 2026-09-20 review's suggested fix, and the code comment cites it. prior: ux-2026-09-20/orders.md (its header fix introduced the mixed count).
- Main state, re-check after merge.

### FLT-38 Orders: each buyer row says its status twice and draws an empty bar
- Severity: S3
- Screens: `#/orders`
- Where: all (1440 light and dark, demo)
- Repro: `#/orders`, look at the buyer rail.
- Seen: a Short row shows an orange dot AND an orange "Short" chip for one fact. Every row draws a thin bar under "N owed" that stays an empty track while nothing is sold. The column head is two text buttons ("Tick shown", "Untick shown"), and a key hint ("step through buyers") sits in the list's foot. Each row carries a checkbox, a dot, a mono label, a chip, a figure and a bar in 298 px.
- Shot: FLT-38, screenshot not kept.
- Direction: one mark per fact. Drop the dot or the chip, draw the bar only when it carries a value, and put tick-all behind one control.
- Component: `app/src/Orders.tsx` (`BuyerRow`, the rail head)
- Annotation: caused by D220 (Orders is inventory's screen), which lists the row's parts: a status pill, an owed/sold/short triad and a bar. no prior.
- Main state, re-check after merge.

## Held-screen notes

Per the coordinator, the held screens are graded above and not only noted. Every finding on
`#/inventory`, `#/orders` and `#/review` is main state, re-check after merge. That covers
FLT-01, 02, 03, 04, 05, 06, 07, 09, 10, 11, 12, 13, 15, 16, 21, 22, 24, 25, 31, 32, 33, 36, 37 and 38.
The other branch changes the section titles, the Hide sold COUNT, the sale toast and a
correction press. Of these findings, FLT-16 (the count on Hide sold) and FLT-22 (the fold after
a sale) are the most likely to move.

## What I could not check

- `#/codes` filters: the code ledger is empty on the demo and on my seeded store. I know the
  controls from `Codes.tsx` only (state chips, lane chips, search, reveal). UNKNOWN.
- `#/pricing?band=top`: the demo refuses it (`demo_not_recorded`). On my server no card has a
  price, so I saw only its empty state. Band switching and its counts: UNKNOWN.
- Pricing with two runs picked: the demo answered "Nothing loaded." when I added Box 1. It can
  be a recording gap. UNKNOWN.
- Search timing and matching at the owner's scale (about 2,500 cards): not measured. My figures
  are on 122 cards.
- The accent case (FLT-05) was measured by calling the real functions, not seen on a screen.
  No card in either store has an accented name.
- The memory of the Runs Identify sheet across reload: not measured.
- The memory of the Sales shelf-bucket control: not measured.
- Dark theme: I looked at 1440/dark for Sales and at the 390/dark shots. I saw no dark defect
  specific to a filter. I did not shoot every filter state in dark.
- 720 wide: shots taken (`*-720-light.png`), not reviewed one by one.

## Owner gripes, verified

The owner's gripes arrived after pass 1 was saved. They did not change a pass-1 grade.

**1. Inventory: game first, then set, then rarity, in that order only.**
Verdict: PARTLY CONFIRMED. Game must come first: Set and Rarity are `disabled` until a game is
chosen (FLT-09). After that, Set and Rarity work in either order. The code adds a second trap
that the owner will meet: a change of Game WIPES Set and Rarity (`BoxBrowse.tsx:setGameFilter`,
"A GAME CHANGE RESETS SET AND RARITY"). So the only safe order is game, then the others, and a
later change of game starts again. Read from the code, not seen: no store here carries sets.
- Shot: FLT-38, screenshot not kept.

**2. Orders buyer list is "atrociously ugly".**
Verdict: CONFIRMED for every element named that the demo draws. The "Tick shown / Untick shown"
head, the checkboxes, the status dots, the "N owed" figures with a bar under each, and the "step
through buyers" hint are all there. The demo draws "Short" chips, not "Needs a look": that chip
name was not seen. The measurable part: the status is said twice per row (dot and chip), and
the bar is an empty track on every row with nothing sold. Shots:
FLT-38 screenshot, not kept,
FLT-38 screenshot, not kept. New finding: FLT-38. Related: FLT-24.

**3. Orders filter bar: mixed widths, a native Status menu, too many words.**
Verdict: CONFIRMED. Measured at 1440: the first select is 168 × 28 px at 12 px type, the
search 300 × 40 px at 14 px, Status 141 × 28 px at 12 px, Newest/Oldest 138 × 34 px at 14 px,
and "Hide never-seen SKUs" is a 147 × 18 px checkbox label at 12 px. That is four widths,
four heights and two type sizes in one block. Status and the first select are `<select>`
elements, so the menu they open is the operating system's own (seen in code, since a headless
browser cannot draw the macOS menu). The block carries 26 words with the options, about 14
visible at rest. Shot: FLT-38 screenshot, not kept. Findings: FLT-24,
FLT-15.

**4. "611 lines across 806 buyers" looks like a count bug.**
Verdict: CONFIRMED BY THE CODE, the live figure not seen. The line total counts the lines of
orders that still owe copies. The buyer total counts every buyer in the payload, finished
orders included. The two numbers are over different sets. New finding: FLT-37.

**5. Could Capture's pickers become the ONE filter control?**
Verdict: YES AS A BASE, with five changes. Seen at 1440 light: each Capture picker is one row
that reads "label, current value, chevron" ("Rarity · 0 of 13 claimed", "Game · Pokémon").
It opens in place into a list with number-key shortcuts. The Box picker adds a type-ahead field
and a note per option ("next index 43"). Its strongest property is the one the list screens
lack: the closed row ALWAYS shows the current value, which answers "is this list filtered, and
by what" (FLT-12, FLT-13). To filter a list it needs:
- **A count per option under the other active filters**, with a zero drawn and not hidden
  (FLT-10). Today the note slot holds "next index", so the slot exists.
- **One selection rule, drawn honestly.** Rarity is multi-select with checkboxes. The Box
  picker draws the same square boxes for a single choice. A filter needs checkboxes only where
  several values can be on.
- **A clear per row and one clear for all**, in the same place on every screen (FLT-15).
  Capture has only the global "Clear the setup".
- **No order lock and no wipe between rows** (gripe 1). Each row narrows the others' counts
  and never empties their choice.
- **Somewhere to open that does not push the list down.** In place works in Capture's side
  column. Over a list it shifts the rows under the hand (the thing D118 forbids), so a list
  screen needs a popover on the desk and a sheet on the phone. The value must also live in the
  URL (FLT-11).
- Shot: FLT-38, screenshot not kept.
FLT-38 screenshot, not kept,
FLT-38 screenshot, not kept.
