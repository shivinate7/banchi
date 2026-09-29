# Sales: the gross-revenue screen

**Status: BUILT.** `#/revenue` is a nav row on purpose. It was tried off-nav and reversed on the
owner's word. D214 (sales shows gross, never profit) records why it is its own route and why it is
gross-only. D217 (sales sorts, filters and deep links) records the sort, filter, cross-filter,
drill-down and URL work. `docs/specs/revenue-plan.md` holds what was built beside it, and
`docs/specs/revenue-next.md` holds the open findings.

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
  one sentence, which `text-shape.spec.ts` is built to catch. `text-shape-allow.json` lists it by
  route if a fixture produces the coincidence.

## Where a change goes

- `app/src/Revenue.tsx` is the screen: the tiers, the period control, the URL state, the drill-down
  and the empty state. `app/src/Revenue.css` is its layout, in `--bn-*` tokens only.
- `app/src/App.tsx` holds the `ROUTES` row (`path: '/revenue'`, `hotkey: 'v'`, `group: 'sell'`), the
  `,V` jump and the entry in the keyboard sheet.
- `app/tests/revenue.spec.ts` is the screen's suite. `scripts/views.txt` holds its render line, over
  the empty store every worktree starts with (D43).
- Text shape is three checks and none is a count (D284): `app/tests/text-shape.spec.ts`,
  `app/tests/machine-words.spec.ts` and `app/tests/money-face.spec.ts`.
