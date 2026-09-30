## 34 — The catalogue cache never expires, on a membership claim this store cannot re-check on its own

`pipeline/pricehistory.py:CATALOG_TTL_SECONDS` is `float("inf")`. The owner ruled that the cards in a catalogue set do not change between pulls: recently modified products keep their original low product ids, no new ids appear, and churn is a field edit to an existing record. `Market.prices` keeps its own `PRICE_TTL_SECONDS`, because a daily price must not become permanent. Unmeasured: whether the mirror ever corrects a collector number on an existing card, which is the one field `pipeline/join.py` reads off the catalogue. A diff of `by_number` keys between two snapshots of one group, a week apart, settles it at no request cost.

**Outcome at risk.** A wrong or partial cached entry is never repaired by expiry. Fixing one means deleting a derived directory.

**Closes when.** Cache size on disk becomes material, the store covers enough sets that one bad entry is no longer cheap to notice by hand, or the diff above finds a corrected number.
