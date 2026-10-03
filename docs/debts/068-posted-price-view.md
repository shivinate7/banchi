## DEBT68 — the posted-price history has no screen

**Gap.** The owner wants a view of posted prices. `price_postings` (D243) records every posted price. The build waits on the gate: one SKU has a second posting, meaning `price_postings` rows exceed its distinct SKUs. Check with one query.

**Where.** Placement is settled: first a "What you asked" section on `#/revenue`, then an asked-price series on `#/product` reached from its row links. `docs/specs/sales-plan.md` holds both.
