# Holdings roster: the one-off value report

**Status: IN BUILD.** D324 (Banchi values the owner's investment holdings) governs. This is its
first deliverable: a read-only report of the owner's investment roster at Banchi's own prices.
The sell-signal flags are not built here.

Departs from: the repo rule that a route is not a feature. This is a CLI verb with no screen,
because D324 calls the first deliverable a one-off, read-only report.

## Module and verb

- `pipeline/rosterholdings.py` sits beside `pipeline/holdings.py`. That module values the store's
  own stock. This one values a CSV roster. `pipeline/holdings.py` does not change.
- The pure entry point is `build_roster_report(lines, skus, archive, product_ids_priced)`.
  - `lines` comes from `read_roster(fileobj)`.
  - `skus` holds `SkuRow(key, set_name, product_name, number, condition, printing)`, the store's
    `skus` columns.
  - `archive` is a `store.pricearchive.PriceArchive`. Prices come only from `PriceArchive.for_sku`.
  - `product_ids_priced` is the set of TCGplayer product ids the archive holds.
- The verb is `./banchi holdings-roster <csv>`, in `cli/cmd_holdingsroster.py`. It opens the
  store with `store.db.open_read_only` and never writes.

## Read

- The `csv` module only. Keep a row only when `Type` is `purchase`, `Vendor` is `TCG` and
  `Shipping Status` is not `canceled`. Count the other rows by reason: `sale`, `not_tcg`,
  `canceled`.
- Keep only the product id (`Vendor Product Id`), `Set Name`, `Product Name`, `Condition`,
  `Finish`, `Quantity` and paid (`Total Amount`). Every other column is dropped at read. A
  seller, buyer, account, order id or URL never reaches a dataclass or the output.

## Join

- The key is `(pipeline.join.normalize_set(set), pipeline.join.name_index_key(name))`, folded
  the same way on the SKU side. There is no second normalizer.
- The candidate SKUs are all SKUs with the key. A product is a distinct
  `(set_name, product_name, number)` among them.
  - No product: `unmatched`.
  - More than one product: `ambiguous`. It goes to review and is never valued.
  - One product: matched.
- The price of a matched line: among the product's SKUs whose condition starts with
  `Near Mint`, keep the printing that agrees with `Finish`. `non-foil` keeps a SKU with no `Foil`
  in its condition and no `Foil`, `Holofoil` or `Reverse Holofoil` printing. Any other finish
  keeps a SKU with `Foil` in its condition or printing. When exactly one kept SKU has a latest
  `month` bucket with a market, that market is the unit price. Otherwise the line is `unpriced`,
  with the reason `no_price` or `printing`. A product whose SKUs are all `Unopened` (sealed) is priced
  from its `Unopened` SKU's latest `month` market, for any finish.
- No line is dropped. Every kept line is priced, unpriced, ambiguous or unmatched.

## Report, in order

1. `units received unknown`, then `units sold unknown`. Units held are units bought until the
   owner answers both questions.
2. Excluded row counts by reason, and the base line count.
3. Unmatched, roster side: product ids with line and unit counts.
4. Unmatched, store side: lines the name join left unmatched or ambiguous whose product id the
   store prices. Product ids and a count.
5. Ambiguous: product ids, for review.
6. Unpriced: counts by reason.
7. Per priced product id: units, paid, market each, market total, gain.
8. Totals: paid, market, gain, and the price date (the newest bucket start used).
9. Coverage: `priced X of N lines (P%)`, with units and paid.

The output carries product ids, counts and money only.
