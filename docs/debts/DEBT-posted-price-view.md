## DEBT-posted-price-view — the posted-price history has no screen

**Gap.** The owner wants a view of posted prices. `price_postings` (D243) records every posted price and starts empty, so a view would draw nothing yet. Build it once one SKU has a second recorded posting: `price_postings` rows exceed its distinct SKUs. Check with one query.

**Where.** Not settled. A third series on the per-product page (D227) or a Sales section are both open.
