# Sales: the gross-revenue screen

**Status: BUILT.** `#/revenue` is a nav row on purpose. It was tried off-nav and reversed on the
owner's word. D214 (sales shows gross, never profit) records why it is its own route and why it is
gross-only. D217 (sales sorts, filters and deep links) records the sort, filter, cross-filter,
drill-down and URL work. `docs/specs/sales-plan.md` holds what was built beside it, and
`docs/specs/sales-findings.md` holds the open findings.

## What it answers

TCGplayer's seller Orders page indexes orders, not line items. It cannot say how much a card made
in a month. This screen can, because the ledger already carries the number. `GET /orders`
(`server/capture_server.py:do_orders`) feeds `app/src/server.ts:getOrders`, and
`app/src/Revenue.tsx` reshapes that one payload. There is no new route, and no change to order
parsing, resolution or the ledger.

## What is on the screen

1. **The verdict.** One sentence gives the gross total for the selected period and the order count
   behind it. A second line compares it with the period right before it. While the current period
   is unfinished, the comparison cuts both sides to the same number of elapsed days and says so in
   words. Where no earlier period exists (`all time`), it says that instead.
2. **The month or week strip.** One row per bucket that has a real sale, with gross, order count and
   a sparkline over the strip. A wide window buckets by month. A window of 60 days or fewer buckets
   by week. The range decides the grain and no control does. The bucket that holds today always
   draws, marked as partial, so a half-finished month is never read as a decline. Each row is a
   button. Selecting one cross-filters the product table to that bucket, and the selection is a
   dismissible chip.
3. **The product table.** One row per line's own `name`, with copies sold, gross and last-sold date.
   It is searchable by name and sortable by any column, with `aria-sort` on the active one and
   gross-descending as the default. Each row opens into the orders behind it: date, order number,
   copies and unit price.

A `Segmented` period control (`3 months`, `6 months`, `This year`, `All time`, `Custom`) filters all
three tiers from one set of sales. Every control lives in the URL query (`?period=&q=&sort=&dir=&month=&from=&to=`),
so a view reloads and shares as it was left. Writes use `history.replaceState` and never push an
entry.

## What it deliberately does not do

- **No fees, no shipping revenue, no cost basis and no profit.** The wire carries none of the
  three, because the allowlist in `server/order_transport.py` drops `transaction` before it reaches
  the browser. Every figure is gross, and the page's own lede says so.
- **Refunds subtract what the operator already recorded.** A line closed as never shipping is
  dropped from the total and counted in `refundExcluded` (D225, refunds subtract from sales).
- **Canceled orders are silently excluded.** The owner ruled this on seeing the alternative.
  `Revenue.tsx:isCanceled` compares the wire's `status` with the single word `canceled`. That is
  narrower than `store/orders.py:TERMINAL_STATUSES`, which also covers Shipped and Delivered. Both
  are real revenue and both stay.
- **No buyer detail.** `OrderRow.buyer` is never read. That question belongs to `#/orders` (D193).
- **Sealed and singles share one list**, sorted the same way. A Singles, Sealed and All switch
  narrows it and never re-sorts it. `isSealed` in `Revenue.tsx` is true when `kind` is `sealed` or
  when `condition` equals `pipeline/tcgcsv.py:SEALED_CONDITION` ("Unopened"), case-folded. The
  condition carries almost all of the signal, because `kind` is never set in practice. Sealed
  product with neither signal reads as a single. With no evidence, it makes no claim.

## Rules a change must keep

- **The board's value bar and its price sit in separate grid cells.** In one flex row, a bar width
  and a long dollar figure both refused to shrink, and the overflow drew over neighboring text. A
  grid cell cannot overlap a sibling cell's text at any width.
- **Finish and rarity are completed from the `skus` table and never left blank.**
  `_order_line_wire` fills `condition` and `rarity` from `snapshot.skus.entries` when the order
  line's own fields are empty. On the owner's real store, the feed carried a condition or rarity on
  none of its lines, and the join resolved most of them. TCGplayer's literal `"None"` reads as no
  rarity.
- **A short display name is trimmed mechanically and never guessed.** `shortProductName` strips the
  line's own `product_line` and `set_name`, and the tail of `set_name` after its last colon, off the
  front of the title. It strips `condition` off the back. A name the SKU table says nothing about
  stays full-length. The full title sits on the `title` attribute. A bare trailing `#` is a sealed
  product's placeholder noise and is trimmed. A real card number always carries digits.
- **A row thumbnail is cropped to the card (D125).** `RowThumb` asks `useCardCropWhenSeen` for the
  sibling copy's rectangle, as `Pricing.tsx` does. A card with no on-hand sibling draws a compact
  placeholder and not a full-bleed empty tile.
- **A share under one percent reads "<1%".** `pctLabel` rounds a real nonzero share down to that
  and never to a false `0%`. It draws nothing for a $0 line.
- **The heading over the product table is "What sold".** It is true under any sort.
- **`.revenue-tile-name` is `display: block`,** so its ellipsis rule works outside a flex row. An
  inline box ignores `overflow` and `text-overflow`.
- **"Last sold" and its date share one line.** Three podium tiles on the same sale date then repeat
  one sentence, which `text-checks.spec.ts` is built to catch. `text-shape-allow.json` lists it by
  route if a fixture produces the coincidence.

## Where a change goes

- `app/src/Revenue.tsx` is the screen: the tiers, the period control, the URL state, the drill-down
  and the empty state. `app/src/Revenue.css` is its layout, in `--bn-*` tokens only.
- `app/src/App.tsx` holds the `ROUTES` row (`path: '/revenue'`, `hotkey: 'v'`, `group: 'sell'`), the
  `,V` jump and the entry in the keyboard sheet.
- `app/tests/revenue.spec.ts` is the screen's suite. `scripts/views.txt` holds its render line, over
  the empty store every worktree starts with (D43).
- Text shape is three checks and none is a count (D284), run in one sweep by `app/tests/text-checks.spec.ts`.

## Mix: a view inside Sales (`#/revenue?lens=mix`)

**Status: BUILT.** The owner approved a Mix view inside Sales, not a new route. D214
(sales shows gross, never profit) keeps its rules: Mix is a lens on the same retrospective job, and
it adds no profit, fee or cost figure. D31 (one owner-side view of stored cards) stays whole: Mix
draws counts and sums and never a card walk. `ROUTES` gains no row, so the route census and
README's route table do not move. A `Segmented` control, `Sales | Mix`, sits under the page
heading and writes `lens` (Sales keeps `view` for singles, sealed and all).

**The job.** A pivot over what the owner captured, holds and sold, to decide what to capture next.
Filters on any dimension. Rows and columns split by any dimension. A choice of measures.

### Definitions

A card is one row of the `cards` table. A card in state `retired` or `moved` left the stock, and
counts as neither held nor sold, so the route leaves it out.

- **State.** `Sold` is state `sold`. `On hand` has a SKU and is not sold. `Not listed yet` has no
  SKU.
- **Dimensions, nine.** Game, Set, Rarity, Finish, State, Box, Capture week, Sale week, Price band.
  - Capture week and Sale week are the Monday that starts the week, as an ISO date. Sale week of a
    card that has not sold is `Not sold`.
  - Price band is `No price yet`, `Under $1`, `$1 to $5`, `$5 to $20` or `$20 and up`, from the
    card's price. The browser derives it. The wire carries no band.
  - A listed card reads rarity, set and finish from its SKU. A card with no rarity reads `Unread`,
    and no set reads `No set yet`.
  - **An unlisted card counts by its claimed rarity**: the capture's `rarity_claim`, joined with
    ` or ` if there are two, and `No claim` if empty. Its set is `set_hint`. Its finish is
    `Near Mint Foil`, `Near Mint` or `Unknown` from `metadata_finish`.
  - Box is the box name, `Box <n>` for an unnamed one and `No box` for none (D20, a box is
    addressed by name).
- **Price.** A sold card's price is **its SKU's average sale price**: Sales' own refund-adjusted
  gross for that SKU divided by its copies. The browser takes both from `salesOf` in `Revenue.tsx`
  (D225, refunds subtract from Sales), over the orders Sales already loads, summed per SKU. Mix has
  no second copy of the refund rule and no server sum. Any other card's price is the SKU's
  market reading. A card with no reading has no price.
- **Measures, eight.**
  1. Cards captured: the count of rows.
  2. On hand: rows in state `On hand`.
  3. Sold: rows in state `Sold`.
  4. **Sold of captured**: sold over captured, **all time**, with unlisted cards in the divisor.
  5. Sold, last 14 days: sold cards whose `state_at` is under 14 days before the as-of time.
  6. Weeks of stock: on hand over (sold in 14 days / 2). **A dash if nothing sold in 14 days.**
  7. Revenue: the sum of sold cards' prices. Gross, never profit (D214).
  8. Median price: the median of the prices of cards that have one.
- A ratio over an empty set, and a median over no prices, draw a dash and never `0`.
- Money draws through `Money`, counts through `Count`. A dash is a dash and never a typed
  interpunct (D218, a typed dot is a defect).

### Route

`GET /stock/mix` returns `{asOf, cards: [...]}`. It lives in one home, `pipeline/stockmix.py`.
`server/capture_server.py` calls it and nothing else does. It returns card rows only. It reads no
order and carries no revenue, because the refund rule lives in `salesOf` (D225) and a server sum
would be a second home for it.

- Each card carries small fields only: `game`, `set`, `rarity`, `finish`, `state`, `box`,
  `capturedWeek`, `soldWeek` (null if not sold), `sku` (null if unlisted, the join key to
  `salesOf`'s lines), `price` (the market reading, null if none) and `soldRecent` (0 or 1). No
  photograph and no buyer is on the wire. The owner's store of about
  4,300 cards is about 900 KB as JSON, about 100 KB gzipped.
- The as-of time is the server clock at the read. The 14-day window and the week starts derive
  from it, and the response names it.
- **One statement, no per-card Python walk and no store call in a loop.** `cards` joined to `skus`,
  `readings` and `boxes`. The retired and moved cards are skipped after it, so the query has no
  WHERE and no alias (`read_budget.scans` reads both). The read budget (`docs/specs/efficiency.md`)
  gets a row in `harness/tests/t7/read_budget.py`: `'/stock/mix': {"status": 200, 'sql': 11, 'store_read': 1}`,
  11 is the store open's own statements plus this one,
  with the same count at S and 2S. Its fixture holds sold, unlisted, retired and moved cards. That
  covers the hit path and not only the empty path (DEBT85).
- `app/src/server.ts` gets one client function, `getStockMix`. `app/src/types.ts` gets its type.
- The browser pivots. Pivot math lives in one pure file, `app/src/mixPivot.ts`, with the
  dimension and measure tables. Every control press is a local recompute and fetches nothing.
- A new `pipeline/` file needs its `docs/map.py` entry in the same commit (`repo map` row).

### Controls

Every control is a kit control (D311, filters are one kit control). No screen draws its own row of
pills.

- **Filters: nine multi-select dropdowns, one per dimension**, in one `FilterChips` bar. Each shows
  its selection count. Each option shows the count it would give under the other filters, faint
  but still offered at zero. `FilterChips` already draws a multi-select pick list (`FilterFacet`
  with `multiple`), and its trigger names the first pick plus `+N`.
  **The smallest extension:** one optional `FilterFacet` field, `countOnly`. If it is set, the
  trigger reads `Set 3`: the label, then the count of picks. With none picked it reads the label
  and `Any`. `FacetChip` takes the field and the other callers are untouched. There is no second
  primitive and no new CSS class (R2-class reserves the kit's filter classes).
- **Rows**: a `Select` over the nine dimensions. **Columns**: a `Select` over the nine dimensions
  and `Nothing`, which draws one column per measure.
- **Measures**: one multi-select `FilterFacet` over the eight measures. A column split allows one
  measure at a time, so the facet becomes single-pick (`multiple: false`). A pick that would break
  this rule rewrites the facet's picks and never leaves two.
- **Sort**: `SortControl`. Its keys are `Row name` and the measures drawn. Its direction segment
  is the kit's own. A sort key that leaves the drawn measures falls back to `Row name`.
- The controls wrap into rows under the heading at 1440 and 820. Each is 40px or more tall
  (`--bn-control-h`).
- **A pivot cell is not a link.** Drill-down to Inventory (D31, D293), saved layouts and CSV
  export are deferred, and named so.

### URL state (D285)

All view state is in the hash query. `patchViewQuery` writes it with `history.replaceState`, and a
reload reads it back. A repeated key carries a multi-value, never a joined string.
`?lens=mix&game=riftbound&rarity=rare&rarity=epic&by=set&across=rarity&measure=pct&sort=pct&dir=desc`

- Filter keys are the dimension ids: `game`, `set`, `rarity`, `finish`, `state`, `box`, `capw`,
  `salew`, `band`. Layout keys are `by`, `across`, `measure` (repeated), `sort`, `dir`.
- A key at its rest value is omitted, so the rest view reads as `?lens=mix`. Rest is rows by Set
  and columns by Rarity. The measure is Sold of captured, sorted by row name, ascending. The Game
  filter sits on the game with the most cards.
- Writing `lens=mix` drops Sales' own keys (`period`, `q`, `month`, `from`, `to`, `view`, `sort`, `dir`). Going back to
  Sales drops Mix's keys. The view ignores a key it does not know. It also ignores a value that
  names nothing in the payload, and never errors.
- No `localStorage` key is added, so the storage roster stays as it is.

### Empty states

- **No cards at all** (an empty store, every worktree's start, D43): one sentence and one action.
  "Nothing is captured yet. Capture a card and its mix shows here." The action is a link to
  Capture.
- **Filters match nothing**: "No cards match these filters." and one action, `Clear all`, which is
  the `FilterChips` clear.
- A fetch failure shows the screen's one error state with a retry.
- A line under the table names the as-of date and the card count matched. For Weeks of stock or
  Sold of captured it adds one sentence on the rule. No decision id, path or pipeline noun is
  shown (D196, no user-visible string may name a decision).

### Screens

One verdict per screen, each looked at and not described, in light and dark at 1440 and 820.
390 only on an owner phone report.

| Screen | Verdict needed |
| --- | --- |
| Mix at rest, with cards | filters wrap, table scrolls inside its frame, first column sticks |
| Mix with a column split and a heat tint | tint reads in both themes, tokens only |
| Mix, several measures, no column split | one column per measure |
| Mix, no match | one sentence, one action |
| Mix, empty store | one sentence, one action |

`scripts/views.txt` gains a render line for the empty store (D43). The tint is `--bn-accent-tint`
steps and never a raw color (`raw color` row of `make docs-audit`). A loading area holds its loaded
size from the first paint (D313, nothing on screen moves unless the person moved it).

### Checks, for the test-author

Each is red before the build and green after. Server checks run on a synthetic store.

1. `GET /stock/mix` leaves out `retired` and `moved` cards. Red: a fixture with one of each shows
   in `cards`.
2. The wire carries no `revenue` field, and a sold card's wire `price` is its market reading.
   Red: a server that sums orders adds a `revenue` key.
3. An unlisted card's `rarity` is its claim joined with ` or `. An empty claim gives `No claim`.
4. A card with no SKU is `Not listed yet`. A sold card is `Sold`. Any other is `On hand`.
5. `soldRecent` is 1 at 13 days and 0 at 14 days before the as-of time.
6. The read budget row exists, and `sql` is equal at S and 2S. Red: a per-card query makes it grow.
7. The wire carries no photograph or buyer field. Red: an added `buyer` key fails the allowlist.
8. `mixPivot`: Sold of captured counts unlisted cards in the divisor, over all time.
9. `mixPivot`: Weeks of stock is a dash for a group with no sale in 14 days, never `0` or infinity.
10. `mixPivot`: a median over no prices is a dash.
11. `mixPivot`: price band edges, at $0.99, $1, $4.99, $5, $19.99 and $20.
12. `mixPivot`: a row's cells sum to its `All` cell for Cards captured, On hand and Sold.
13. `mixPivot`: each option's count respects the other filters and ignores its own dimension.
14. UI: nine filter dropdowns draw, and a trigger with picks shows their count.
15. UI: a column split limits the Measures facet to one pick. Without a split it allows several.
16. UI: every control writes the URL with `replaceState`, and a reload restores the same table.
    Red: a control that keeps state only in React.
17. UI: a rest view writes no query beyond `lens=mix`.
18. UI: `Sales | Mix` leaves `ROUTES` as it is (`route rosters` row).
19. UI: a press on any control fires no request (`app/tests/request-budget.spec.ts`).
20. UI: the empty store and the no-match state each show one sentence and one action.
21. `app/tests/filter-standard.spec.ts` still passes for the Mix bar, and `make kit-adoption` finds
    no hand-rolled select or pill row in the Mix view.
22. Screens: light and dark at 1440 and 820 pass `app/tests/scaffold.spec.ts` and the stability
    check (D313), with no horizontal page scroll.
23. Mix revenue for a SKU equals Sales' figure for that SKU, over a fixture with a refunded line.
    Red: a Mix that ignores the refund rule is higher.

### Where a change goes

`pipeline/stockmix.py` (new), `server/capture_server.py` (the route), `app/src/mixPivot.ts` (new),
`app/src/MixView.tsx` (new, drawn inside Sales' own `<Page>`), `app/src/Revenue.tsx` (the view
switch), `app/src/kit/data.tsx` (`FilterFacet.countOnly`), `app/src/server.ts`, `app/src/types.ts`,
`harness/tests/t7/read_budget.py`, `scripts/views.txt` and `docs/map.py`.
