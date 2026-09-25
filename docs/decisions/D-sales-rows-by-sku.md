## D-sales-rows-by-sku — Sales rows are per printing, and a line with no price says so

**Amends D214** (the gross-revenue retrospective) and **D217** (Sales becomes a tool: sort,
filter, cross-filter, drill down and deep-link). Builds Direction B
(`sales-directions.md`, the owner's choice, RULINGS.md "## Sales") on `#/revenue`.

### Multi-SKU rows (RULINGS.md, "Multi-SKU Sales rows")

`Revenue.tsx`'s `products` map grouped by `sale.name` and kept only the last SKU sold under
that name (`Product.lastSku`). Confirmed true on this store's own shape. A foil and a normal
printing of the same card share one display name. Two SKUs collapsed into one row. The row's
own "Today" column compared the wrong printing's price half the time.

**Fixed by re-keying the group on SKU, not name.** Every `Product` is now one printing. Two
printings sharing a name draw as two rows, name first on both — "separately identifiable"
(the ruling's own words), with no invented second label. `row.name` still leads every row.
`row.sku` decides whether two rows merge, nothing else does.

### The $0.00 line (sales-directions.md, finding 1)

`salesOf`'s price guard tested only for `null`. TCGplayer's feed sends `unit_price: ""` for a
line it never priced, not `null`. `Number('')` is `0`. The line landed at $0.00 and counted as
a real free sale. Measured on the published demo: 6 of about 40 lines.

**Measured whether another source this repo already reads can fill it.** The order ledger
carries `unit_price` per line. That is the one place a price could live once an order is
ingested, and the empty string above is what it already says. `ShippingRow.value` (`GET
/shipping/batches/<id>`) is the other reachable figure. It fails on two counts. It is an
ORDER total, not a per-line price. It is useless once an order carries more than one line.
It is not a standing table — it exists only inside a just-uploaded, TTL'd shipping batch
(`#/shipping`), and `#/revenue` has no standing access to it. Neither the sold-price archive
(D219) nor `readings` (D189) is a sale record. Both are market observations. Filling a "what
did this sell for" cell from either would be the guess CLAUDE.md refuses.
**Conclusion: no source this repo already reads holds the real figure for these lines.** The
count on the owner's own store is unmeasured. This build does not assume that the demo's
count applies there too.

**The fix is in `salesOf`, not only the render.** `unit_price === ''`, and any other
non-numeric, non-null string, is now treated the same as `null`: `priceKnown: false` on the
`Sale`, `gross: 0`, and the line is not dropped. It is a real sale, one this store cannot
price. A `Sale` and a `Product` both carry an unpriced-copy count. A row whose every sale is
unpriced draws "TCGplayer sent no price" in place of a dollar figure, never `$0.00`. A mixed
row draws its known gross plus a note naming how many copies had no price. This is `salesOf`'s
own change, so `#/orders` and any other reader of `OrderRow` is untouched.

### Thumbnails (RULINGS.md, "## Sales": "a server lookup by SKU for another copy's photo")

D89 reclaims a sold card's own photograph on purpose, so a sales row cannot show the
photograph of the copy that actually sold. `GET /skus/photos?sku=<s>&sku=<s>`
(`do_skus_photos`, `server/capture_server.py`) answers the first on-hand, still-photographed
copy of each named SKU. It reuses the same `photo_for` predicate `do_search`'s `_copy_row`
already applies, no second copy of that rule. A SKU with nothing on hand, or nothing
photographed, is simply absent from the answer. The row falls back to a plain tile, never a
guessed or stand-in image. `getSkuPhotos` (`app/src/server.ts`) is the one client caller. A
plain read, costs nothing, called on arrival — unlike `getSoldPrices`/`getHoldingsValue`
beside it, which stay presses (D225, D236). A thumbnail is not a number a reader could
mistake for live market data.

### "On the shelf" on arrival (sales-directions.md, finding 3)

Moves the existing `holdingsSection` fetch from behind "Value my stock" to firing on mount,
matching the ruling. `getHoldingsValue`'s own cost is unchanged. Only when this screen asks
for it moved. Unmeasured on the owner's real store, as the ruling itself says.

### Layout: Direction B

The summary band carries the gross figure, six month bars and "On the shelf". The top three
printings draw as photo tiles. A fourth tile shows the foil/rarity mix. Places 4-10 follow as
bar rows on the podium's own gross scale. The full table comes last, search and sort above
it, "Show all" below the podium. Built in `app/src/Revenue.tsx`/`Revenue.css`, styled from
`sales-dir/mock/B.html`'s own CSS shapes, `--bn-*` tokens throughout. The table keeps its
shape: every printing, still sortable, still the drill-down into an order. It no longer
carries the whole screen. The podium answers the owner's "it is just an excel sheet" gripe.
The table stays for the full list.
