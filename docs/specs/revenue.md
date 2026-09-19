# Sales — the gross-revenue retrospective

`#/revenue`. Routed 2026-09-19, an eleventh nav row on purpose — tried off-nav the same day
and reversed the same day on the owner's own word. See D214 for why
this is its own route, why it is gross-only, and the full account of both rulings.

## What it answers

TCGplayer's seller Orders page indexes orders, not line items. It cannot answer "how much did
I make selling this card, this month". This screen can, because the ledger it reads already
carries the number: `GET /orders` (`server/capture_server.py:do_orders`), unchanged, feeding
`app/src/server.ts:getOrders`, unchanged. `app/src/Revenue.tsx` is a pure reshaping of that
one payload. No new server route. No change to order parsing, resolution, or the ledger.

## What is on the screen, three tiers

1. **The verdict.** One sentence: the gross total for the selected period, and the order
   count behind it. A second, smaller line compares it against the equal-length period right
   before it, or says there is none to compare against (`all time`).
2. **The month strip.** One row per month inside the selected period: gross, order count, a
   sparkline over the whole strip (`PriceHistory.tsx:sparkSegments`, unmodified).
3. **The product table.** One row per line's own `name`, aggregated: copies sold, gross, last
   sold date. Sorted by gross. Searchable by name (`SearchField`, the same `/` hotkey every
   other search field in this app answers to).

A `Segmented` period control (`3 months`, `6 months`, `This year`, `All time`) filters all
three tiers together, off the same underlying set of sales.

## What it deliberately does not do

- **No fees, no shipping revenue, no refunds.** None of the three exist on this wire.
  `server/order_transport.py`'s `project_order` allowlist drops `transaction` and `refunds`
  before either reaches the browser. There is nothing here to read.
- **No cost basis, no profit, no P&L.** This repository has never recorded what a card cost.
  Every figure on this screen is GROSS. The word "gross" is in the page's own lede so the
  number is never mistaken for profit.
- **No sealed/singles split.** `OrderLineWire.kind` is null on nearly every real line, and
  guessing a kind from a product name is refused by CLAUDE.md and by `pipeline/orders.py`'s
  own header. The product table is one mixed list. Measured 2026-09-19: the top eight names
  by gross on the owner's store are all sealed product. A split assuming singles dominate
  would be wrong about most of the data.
- **Canceled orders are silently excluded.** The owner's ruling, 2026-09-19, having seen the
  alternative. No footnote, no disclosed count. `Revenue.tsx:isCanceled` folds and compares
  the wire's own `status` string against the single word `canceled`. That is narrower than
  `store/orders.py:TERMINAL_STATUSES`, which also covers Shipped and Delivered — both real
  revenue, and both kept.
- **No buyer detail.** `OrderRow.buyer` is never read here. This screen answers "what sold",
  never "to whom" — that question is `#/orders`'s (D193).

## Measured, once, on the owner's live store (2026-09-19)

- 804 orders, 1,346 lines, zero missing `unit_price`.
- Excluding Canceled: $66,334.71 gross, 1,268 lines, 539 distinct product names.
- Months present: 2026-05 through 2026-09.
- `GET /orders`: 230ms, 1.15MB, one call.

These are a snapshot of one store on one day. They are kept here as the number this screen's
build was checked against. They are never rewritten to match a later tree — the same rule
`docs/GATES.md` states for its own run records.

## Where a session goes to change this

- `app/src/Revenue.tsx` — the screen. All three tiers, the period control, the empty state.
- `app/src/Revenue.css` — its layout. `--bn-*` tokens only.
- `app/src/App.tsx` — the `ROUTES` row (`path: '/revenue'`, `hotkey: 'v'`, `group: 'sell'`),
  the `,V` jump binding, and the Sales entry in the keyboard reference sheet.
- `scripts/views.txt` — the `revenue` render line, over the empty store every worktree starts
  with (D43).
