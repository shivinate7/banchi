# Holdings roster: the one-off value report

**Status: IN BUILD.** D324 (Banchi values the owner's investment holdings) governs. This is its
first deliverable: a read-only report of the owner's investment roster at Banchi's own prices.
The sell-signal flags are not built here.

Departs from: the repo rule that a route is not a feature. This is a CLI verb with no screen,
because D324 calls the first deliverable a one-off, read-only report.

## Module and verb

- `pipeline/rosterholdings.py` sits beside `pipeline/holdings.py`. That module values the store's
  own stock. This one values a CSV roster. `pipeline/holdings.py` does not change.
- The pure entry point is `build_roster_report(lines, skus, archive)`.
  - `lines` comes from `read_roster(fileobj)`.
  - `skus` holds `SkuRow(key, set_name, product_name, number, condition, printing)`, the store's
    `skus` columns.
  - `archive` is a `store.pricearchive.PriceArchive`. Prices come only from `PriceArchive.for_sku`.
- The verb is `./banchi holdings-roster <csv>`, in `cli/cmd_holdingsroster.py`. It opens the
  store with `store.db.open_read_only` and never writes.

## Read

- The `csv` module only. Keep a row only when `Type` is `purchase`, `Vendor` is `TCG` and
  `Shipping Status` is not `canceled`. Count the other rows by reason: `sale`, `not_tcg`,
  `canceled`.
- Keep only the product id (`Vendor Product Id`), `Set Name`, `Product Name`, `Condition`,
  `Finish`, `Quantity` and paid (`Total Amount`). Every other column is dropped at read. A
  seller, buyer, account, order id or URL never reaches a dataclass or the output.
- A kept row with a blank or unreadable amount, a quantity of zero or less, or missing columns
  stops the report with an error that names its file line.

## Join

- The key is the roster's product id against `price_history.product_id` (D324, waiting-page item
  119). A product id maps to the SKU keys of every archive row that carries it, any range. Id `0`
  means the archive had none and is never a key. One product id is one product, so there is no
  ambiguous bucket.
  - No archive row carries the id: `unmatched`.
  - An archive SKU with no `skus` row: `unpriced`, reason `no_sku_row`.
- The price of a matched line: among the product's SKUs whose condition starts with
  `Near Mint`, keep the printing that agrees with `Finish`. `non-foil` keeps a SKU with no `Foil`
  in its condition and no `Foil`, `Holofoil` or `Reverse Holofoil` printing. Any other finish
  keeps a SKU with `Foil` in its condition or printing. When exactly one kept SKU has a latest
  `month` bucket with a market, that market is the unit price. Otherwise the line is `unpriced`,
  with the reason `no_price` or `printing`. A product whose SKUs are all `Unopened` (sealed) is priced
  from its `Unopened` SKU's latest `month` market, for any finish.
- The name join is the cross-check: `(pipeline.join.normalize_set(set),
  pipeline.join.name_index_key(name))`, folded the same way on the SKU side, priced the same way.
- No line is dropped. Every kept line is priced, unpriced or unmatched.

## Report, in order

1. `units received unknown`, then `units sold unknown`. Units held are units bought until the
   owner answers both questions.
2. Excluded row counts by reason, and the base line count.
3. Unmatched, roster side: product ids with line and unit counts.
4. Unmatched, store side: lines the name join prices that the id join leaves unmatched or
   unpriced. Product ids and a count.
5. Unpriced: counts by reason.
6. Per priced product id: units, paid, market each, market total, gain.
7. Totals: paid, market, gain, and the price date (the newest bucket start used).
8. Coverage: `priced X of N lines (P%)`, with units and paid.

The output carries product ids, counts and money only.
