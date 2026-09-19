# Sales — the gross-revenue retrospective, now a tool

`#/revenue`. Routed 2026-09-19, an eleventh nav row on purpose — tried off-nav the same day
and reversed the same day on the owner's own word. See D214 for why this is its own route,
why it is gross-only, and the full account of both rulings. See D-revenue-slice for the
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
never a pushed entry. D-revenue-slice states why, and names the trade it costs.

## What it deliberately does not do

- **No fees, no shipping revenue, no refunds.** None of the three exist on this wire.
  `server/order_transport.py`'s `project_order` allowlist drops `transaction` and `refunds`
  before either reaches the browser. There is nothing here to read.
- **No cost basis, no profit, no P&L.** This repository has never recorded what a card cost.
  Every figure on this screen is GROSS. The word "gross" is in the page's own lede so the
  number is never mistaken for profit.
- **No sealed/singles split.** `OrderLineWire.kind` is null on nearly every real line, and
  guessing a kind from a product name is refused by CLAUDE.md and by `pipeline/orders.py`'s
  own header. The product table is one mixed list, and sorting it does not un-mix it.
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

## The copy-budget ceiling

`app/tests/copy-budget.json` pins `#/revenue` at 64 words, raised from 56 by
`D-revenue-slice`. See that entry for the eight-word breakdown, and for why the ceiling was
already measuring a populated screen rather than the empty state.

## Measured, once, on the owner's live store (2026-09-19)

- 804 orders, 1,346 lines, zero missing `unit_price`.
- Excluding Canceled: $66,334.71 gross, 1,268 lines, 539 distinct product names.
- Months present: 2026-05 through 2026-09.
- `GET /orders`: 230ms, 1.15MB, one call.

These are a snapshot of one store on one day. They are kept here as the number this screen's
first build was checked against. They are never rewritten to match a later tree — the same
rule `docs/GATES.md` states for its own run records.
