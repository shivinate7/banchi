# D254 — Resolve a product from its SKU

**Tier (b) reads the store-owned SKU table (D258).** Before, it merged every cached export on each call. The tier order and the ruling below stand. Only the source of tier (b)'s map changed.

**The ruling.** Find the product from the SKU itself. Use the SKU's own catalog row, which gives TCGplayer's own name and number for that SKU. Or use the product the archive already verified for that SKU. The card's read name and number are never used there. Identification errors are fixed at the join (Lane 1) and by the "Wrong card?" press. Price history then follows automatically.

**The reversed attempt.** A session widened `pipeline/pricehistory.py:ProductIndex.find` to weigh a card's own read name against the number it found (D240's measured seam). Review reversed the approach. The reviewer re-derived the session's 914/865/29/20 measurement. Then they checked all 49 changed lookups against the owner's cached price-history files. Those files list the real SKUs sold under each product. 16 of 49 were worse. 15 of 20 new refusals had a correct old answer. One example: SKU 9034674, stored name "Rengar, Uta, Cat", 025/221, is really "Rengar, Pouncing". 1 of 29 flips was wrong. SKU 8927537, "Dragon's Rage", 256/298, is really "Fox-Fire". On Riftbound "Champion, Title" cards, the read name is the unreliable field, not the number. Weighing a read name against a number is backwards for this shape of card.

**The failure mechanism.** `store/pricearchive.py` keys each bucket `(sku, range, start)`. A wrong productId gives an EMPTY series for the SKU. The endpoint's answer for a different product almost never carries this SKU's own id among its results. It never writes another product's numbers under this SKU's key.

**The fix.** Never ask the card. A SKU's own product is a fact about the SKU, not about a photograph. `pipeline/join.py:_walk` already fixes an actual misidentification. The review screen's "Wrong card?" press already corrects a wrong stored name after the fact. This module's job is narrower. Given a SKU already in the store, find its product without re-deriving an identification for it.

**Three tiers, in order.**

- (a) `store/pricearchive.py:Bucket.product_id`, an archive a previous sweep already verified for this exact SKU. No lookup at all.
- (b) The SKU's own row in the store's cached Filtered Export (`inventory/.exports/<game>/*.csv`, `pipeline/pricearchive.py:merged_export_rows_by_sku`). TCGplayer filed the SKU under that row. Its Product Name and Number therefore describe that SKU's product.
- (c) Today's behavior, unchanged: the card's own last-known name and number, resolved through `pipeline/pricehistory.py:Market.product_id_for_row` exactly as before. Reached only when neither (a) nor (b) answers.

`ProductIndex.find` is fully reverted to its pre-D240 shape. It takes only a number and a name, and it carries no dispute logic of its own. `Market.reading_for_row` and `readings_for_rows` take an optional `product_id` or `product_ids` parameter. A caller holding a verified id skips resolution. This class weighs nothing.

**Checked first.** Neither tcgcsv's mirror nor the Filtered Export maps a SKU straight to a productId in one step. tcgcsv publishes no SKUs at all (`pipeline/pricehistory.py`'s own header). The export carries a SKU, a Product Name and a Number on one row, but no productId. Resolving that is still `ProductIndex.find`'s job. This entry changes only the row it is fed.

**Measured on the owner's real store.** The reviewer's method was read-only. It made no network call and wrote nothing. The subjects are the same 914 card-covered SKUs. Each change between the old and new resolution was checked against the owner's cached price-history files. The check asks whether the candidate productId's cached history carries this SKU's own id. The match is exact, never fuzzy.

| verdict | count |
|---|---|
| same (id unchanged) | 862 |
| confirmed better | 20 |
| confirmed worse | 0 |
| inconclusive (no cached history to check either candidate against) | 32 |

Zero were confirmed worse. Every changed SKU whose old answer could be checked was FALSE against its own cached history. So the old per-card resolution was already wrong for each one, not merely different. The 32 inconclusive rows have a new candidate whose history was never fetched or cached, so neither answer can be checked yet. None of them regresses a verified-correct answer.

**What this does not touch.** `pipeline/join.py` itself. Another lane owns it, and this entry only imports from it. The archive's key (D219) and its pacing (D222) are unchanged. The real listing join's D162 and D240 behavior is unchanged.

Cites D240 (the seam and its reversed attempt), D219 (the archive this reads `Bucket.product_id` from, and the empty-series mechanism), D222 (pacing), and D234 (the glued-set-code repair that `ProductIndex.find` still runs).
