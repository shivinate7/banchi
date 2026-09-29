# Sales — the gross-revenue retrospective, now a tool

`#/revenue`. Routed 2026-09-19, an eleventh nav row on purpose — tried off-nav the same day
and reversed the same day on the owner's own word. See D214 for why this is its own route,
why it is gross-only, and the full account of both rulings. See D217 for the
sort, filter, cross-filter, drill-down and URL work this document now describes. Neither
entry's own counting rules changed.

## What it answers

TCGplayer's seller Orders page indexes orders, not line items. It cannot answer one thing.
How much did I make selling this card, this month. This screen can. The ledger it reads
already carries the number. `GET /orders` (`server/capture_server.py:do_orders`), unchanged,
feeds `app/src/server.ts:getOrders`, unchanged. `app/src/Revenue.tsx` is a reshaping of that
one payload. No new server route. No change to order parsing, resolution, or the ledger.

## What is on the screen, three tiers, all sliceable

1. **The verdict.** One sentence: the gross total for the selected period, and the order
   count behind it. A second line compares it against the period right before it. Where the
   current period has not fully elapsed, that comparison is cut to the same number of
   elapsed days on both sides. It says so in words ("So far, ..."). Where there is no
   earlier period at all (`all time`), it says that instead.
2. **The month or week strip.** One row per bucket that has a real sale, gross, order
   count, a sparkline over the whole strip (`PriceHistory.tsx:sparkSegments`, unmodified).
   A wide window buckets by month. A window of 60 days or fewer buckets by week. That
   granularity is derived from the range, never a separate control. One bucket draws even
   with nothing in it: the one containing today, whenever the selection reaches that far,
   marked "ongoing" so a half-finished month is never misread as a decline. Each row is a
   button. Selecting one cross-filters the product table below to that bucket alone. The
   selection is a dismissible chip.
3. **The product table.** One row per line's own `name`, aggregated: copies sold, gross,
   last sold date. Searchable by name (`SearchField`). Sortable by any of its four columns,
   `aria-sort` on the active one, gross-descending the default. Each row opens into the
   orders behind it: date, order number, copies, unit price. That comes from `Sale.order`
   (`OrderRow.key`, the identity) and the new `Sale.orderNumber` (`OrderRow.number`, the
   label a person reads).

A `Segmented` period control (`3 months`, `6 months`, `This year`, `All time`, `Custom`)
filters all three tiers together, off the same underlying set of sales. `Custom` reveals a
`From`/`To` date pair. Every one of these controls lives in the URL's own query string:
`?period=&q=&sort=&dir=&month=&from=&to=`. So does the search text and the active bucket. A
view can be reloaded or shared exactly as it was left. Writes use `history.replaceState`,
never a pushed entry. D217 states why, and names the trade it costs.

## What it deliberately does not do

- **No fees, no shipping revenue, no refunds.** None of the three exist on this wire.
  `server/order_transport.py`'s `project_order` allowlist drops `transaction` and `refunds`
  before either reaches the browser. There is nothing here to read.
- **No cost basis, no profit, no P&L.** This repository has never recorded what a card cost.
  Every figure on this screen is GROSS. The word "gross" is in the page's own lede so the
  number is never mistaken for profit.
- **Sealed and singles are still one mixed list by default, gross-sorted the same way.** A
  Singles/Sealed/All switch (`ProductView`, review round 2026-09-26, defaulting to Singles)
  narrows it, never re-sorts it — see "The Singles/Sealed switch" below for the rule it
  narrows on.
- **Canceled orders are silently excluded.** The owner's ruling, 2026-09-19, having seen the
  alternative. No footnote, no disclosed count. `Revenue.tsx:isCanceled` folds and compares
  the wire's own `status` string against the single word `canceled`. That is narrower than
  `store/orders.py:TERMINAL_STATUSES`, which also covers Shipped and Delivered — both real
  revenue, and both kept.
- **No buyer detail.** `OrderRow.buyer` is never read here. This screen answers "what sold".
  It never answers "to whom" — that question belongs to `#/orders` instead (D193).

## Where a session goes to change this

- `app/src/Revenue.tsx` — the screen. All three tiers, the period control, the URL state,
  the drill-down, the empty state.
- `app/src/Revenue.css` — its layout. `--bn-*` tokens only.
- `app/src/App.tsx` — the `ROUTES` row (`path: '/revenue'`, `hotkey: 'v'`, `group: 'sell'`),
  the `,V` jump binding, and the Sales entry in the keyboard reference sheet.
- `app/tests/revenue.spec.ts` — the screen's own Playwright suite. It covers the empty and
  failure states, every sort, the search, the cross-filter, the drill-down, and URL
  round-tripping. It also covers the custom range's granularity switch, both the
  zero-divide and mono-treatment defects, and a 390px overflow this build found in its own
  header.
- `scripts/views.txt` — the `revenue` render line, over the empty store every worktree starts
  with (D43).

## The copy-budget ceiling (retired)

No pinned word ceiling applies. The current checks (D284) are
`app/tests/text-shape.spec.ts`, `app/tests/machine-words.spec.ts` and
`app/tests/money-face.spec.ts`. None of them pins a count.

## Measured, once, on the owner's live store (2026-09-19)

- 804 orders, 1,346 lines, zero missing `unit_price`.
- Excluding Canceled: $66,334.71 gross, 1,268 lines, 539 distinct product names.
- Months present: 2026-05 through 2026-09.
- `GET /orders`: 230ms, 1.15MB, one call.

These are a snapshot of one store on one day. They are kept here as the number this screen's
first build was checked against. They are never rewritten to match a later tree — the same
rule `docs/GATES.md` states for its own run records.

## Review round, owner's preview, 2026-09-26

Nine findings from a screenshot round, fixed together (the ux-2026-09-23 review's
"Sales preview review, round 2").

- **The board's value bar gets its own grid column, never shared with the price.** A bar
  width plus a long dollar figure used to sit in one flex row. A flex item's default
  min-width is its own content. Neither one shrank. The row overflowed, and the overflow
  drew over the neighbouring columns' text. `.revenue-board-track` (the bar) and
  `.revenue-board-value` (the price) are two separate grid cells now. A grid cell cannot
  overlap a sibling cell's text, at any width.
- **Finish and rarity are completed from the `skus` table, never left blank.**
  `server/capture_server.py:_order_line_wire` fills `condition`/`rarity` from
  `snapshot.skus.entries` when the order line's own fields are empty. `_row_for_bind` and
  `_listing_decoration` already read this same table (identity-follows-sku.md §3.2).
  Measured on the owner's real store: 0 of 1,406 lines carried a `condition` or `rarity`
  from the feed itself. After the join, 1,373 resolve a condition and 1,117 resolve a
  rarity. TCGplayer's own literal `"None"` (`pipeline/games.py`'s `rarities_not_claimed`) is
  read as no rarity, the way that module already treats it. It never draws as a real rarity
  string.
- **The Singles/Sealed switch (item 5).** Verbatim in the RULINGS.md entry above. The rule,
  `isSealed` in `Revenue.tsx`: `kind === 'sealed'` (the feed's own declared word), OR
  `condition` equal to `pipeline/tcgcsv.py:SEALED_CONDITION` ("Unopened"), case-folded. The
  second half carries almost all of the real signal. `kind` is never set in practice. Sealed
  product with neither signal reads as a single, never as a guess — the same "no evidence,
  no claim" rule the rest of this repo already keeps.
- **A short display name, mechanically trimmed, never guessed.** `shortProductName` strips
  the line's own `product_line`/`set_name`, and the tail of `set_name` after its last colon
  (for a title that repeats the set a second time), off the front of the raw TCGplayer
  title. It strips `condition` off the back too. A name the SKU table has nothing to say
  about stays full-length — never cut on a guess. The full title sits on the name's `title`
  attribute, for a hover or a focus. A bare trailing `"#"` is trimmed too: a sealed
  product's own number-placeholder noise (`pipeline/pricearchive.py:_split_ledger_tail`'s
  documented shape). A real card number always carries digits, and stays untouched.
- **A card with no on-hand sibling draws a compact placeholder, not a full-bleed empty
  tile.** `.revenue-tile-art:has(.bn-thumb[data-missing='true'])` undoes the tile's own
  "fill the art area" rule, for exactly that one state.
- **The row thumbnail is cropped to the card (D125), the same way every other screen crops
  one.** `RowThumb` now asks `useCardCropWhenSeen` for the sibling copy's own rectangle —
  the same primitive `Pricing.tsx`'s thumbnail already uses. The photo was never
  un-croppable. This screen had simply never asked.
- **"0% of gross" is now "<1% of gross", or nothing at all.** `pctLabel` rounds a real,
  nonzero share down to `<1%` rather than to a false `0%`. It draws nothing for a $0 line.
- **"Best sellers" is "What sold."** The heading sat over a sort control that could read
  "Latest" or "A to Z" — neither one is "best". The new heading is true under any sort.
- **`.revenue-tile-name` needed `display: block`, so its own ellipsis rule works
  everywhere, not only inside a flex row.** A plain `<span>` is inline by default.
  `overflow`/`text-overflow: ellipsis` do nothing on an inline box. It worked by accident in
  the podium tile — a flex parent blockifies its own items — and failed in the board's
  plain `<div>`. It also failed at every width the kit's own thumb-floor rule turns
  `.bn-datalink` into `inline-flex` (`kit/data.css`, D117, under 767px). Both `Revenue.css`
  rules are fixed the same way: `display: block; max-width: 100%`.
- **"Last sold" and its date now share one line.** A deliberate trade against
  `text-shape.spec.ts`'s repeated-sentence floor: three podium tiles landing on the same
  sale date now repeat one four-word-or-longer sentence, which the checker is built to
  catch. `text-shape-allow.json` lists it, by route, if the fixture ever produces that
  coincidence. The owner asked for the line. The floor's own escape hatch is exactly for an
  accepted finding like this one.
