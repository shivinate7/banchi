## DEBT-sales-export-price-series — the owner's realized prices are not read

**Gap.** OrderWand's sales export carries a price and a `Vendor Product Id` (a TCGplayer `productId`) on every row, so it joins to the price-history archive with no lookup. It answers what this seller actually got, against what the market did. It carries no SKU and cannot be turned into one. It holds buyer names, so no copy belongs in the tree.

**Limit.** It is a diagnostic. Turning it into a listing rule needs its own decision entry.
