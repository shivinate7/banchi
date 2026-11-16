## DEBT68 — the posted-price history has no screen

**What.** The owner wants a view of posted prices. `price_postings` (D243) records every posted price. The build waits on the gate: one SKU has a second posting, meaning `price_postings` rows exceed its distinct SKUs. Check with one query.

One screen already draws posted prices: the history card on `#/pricing` shows a SKU's postings as an asking step line, through the product-history route's `asking_postings`. `#/pricing`'s kept-clears notice also reads postings, but draws none. Neither placement below is built.

**Where.** Placement is settled: first a "What you asked" section on `#/revenue`, then an asked-price series on `#/product` reached from its row links. `docs/specs/sales-plan.md` holds both.
