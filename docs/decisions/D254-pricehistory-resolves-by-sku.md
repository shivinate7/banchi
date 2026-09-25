## D254 — A product is resolved from its SKU, never from a card's own read fields

**AMENDED IN ONE LINE (`D-identity-follows-the-sku`).** Tier (b) reads the store-owned SKU
table now, instead of merging every cached export on each call. The tier order stands. The
owner's ruling stands. Only the source of tier (b)'s own map moved.

**The reversed attempt.** A session widened `pipeline/pricehistory.py:ProductIndex.find` to
weigh a card's own READ name against the number it found (D240's measured seam). The owner's
review reversed the whole approach.

**Why it was wrong.** The reviewer re-derived the session's own 914/865/29/20 measurement.
The reviewer then checked all 49 changed lookups against the owner's cached price-history
files, which list the real SKUs sold under each product. 16 of 49 were WORSE. 15 of 20 new
refusals had a correct old answer. One example: SKU 9034674, stored name "Rengar, Uta,
Cat", 025/221, is really "Rengar, Pouncing". 1 of 29 flips was wrong. SKU 8927537,
"Dragon's Rage", 256/298, is really "Fox-Fire". On Riftbound "Champion, Title" cards, the
READ NAME is the unreliable field, not the number. Weighing a read name against a number is
backwards for this shape of card.

**The failure mechanism, corrected.** The earlier entry overstated it. `store/pricearchive.py`
keys each bucket `(sku, range, start)`. A wrong productId gives an EMPTY series for the SKU.
The endpoint's answer for a different product almost never carries this SKU's own id among
its results. It never writes another product's numbers under this SKU's own key.

**The owner's ruling (2026-09-23), verbatim:** *"From the SKU itself: Look up the product
by the SKU's own catalog row (TCGplayer's own name and number for that SKU, which always
agree), or the product the archive already verified for that SKU. The card's read
name/number is never used there. Identification errors are fixed at the join (Lane 1) and
by the 'Wrong card?' press, and price history follows automatically."*

**The fix.** Never ask the card at all. A SKU's own product is a fact about the SKU, not
about a photograph. `pipeline/join.py:_walk` already owns fixing an actual
misidentification. The review screen's "Wrong card?" press already owns correcting a wrong
stored name after the fact. This module's job is narrower: given a SKU already in the
store, find its product without re-deriving an identification for it.

**Three tiers, in the owner's own order.**

- (a) `store/pricearchive.py:Bucket.product_id`, an archive a previous sweep already
  verified for this exact SKU. No lookup at all.
- (b) the SKU's own row in the store's cached Filtered Export
  (`inventory/.exports/<game>/*.csv`, `pipeline/pricearchive.py:
  merged_export_rows_by_sku`). Its Product Name and Number describe that SKU's product by
  definition, because TCGplayer itself filed the SKU under that row.
- (c) today's behaviour, unchanged: the card's own last-known name and number, resolved
  through `pipeline/pricehistory.py:Market.product_id_for_row` exactly as it always was.
  Reached only when neither (a) nor (b) answers.

`ProductIndex.find` itself is fully reverted to its pre-D240 shape. It takes only a number
and a name, and it carries no dispute logic of its own. `Market.reading_for_row`/
`readings_for_rows` gained an optional `product_id`/`product_ids` parameter, so a caller
holding a verified id skips resolution entirely rather than this class weighing anything.

**Checked first.** Neither tcgcsv's own mirror nor the Filtered Export map a SKU straight
to a productId in one step. tcgcsv publishes no SKUs at all
(`pipeline/pricehistory.py`'s own header). The export carries a SKU and a Product Name and
a Number on one row, but not a productId. Resolving that is still `ProductIndex.find`'s own
job. This entry only changes what row it is fed.

**Measured against the owner's real store, the reviewer's own method.** Read-only, no
network call, nothing written. The subjects are the same 914 card-covered SKUs. Each CHANGE
between the old resolution and the new one is checked against the owner's own cached
price-history files. The check: does the candidate productId's cached history actually
carry this SKU's own id. An exact match, never a fuzzy one.

| verdict | count |
|---|---|
| same (id unchanged) | 862 |
| confirmed better | 20 |
| confirmed worse | 0 |
| inconclusive (no cached history to check either candidate against) | 32 |

Zero confirmed worse. Every changed SKU whose old answer could be checked was checked FALSE
against its own cached history. The old per-card resolution was already wrong for every
one of them, not merely different. The 32 inconclusive rows are SKUs whose new candidate
has never had its own history fetched and cached, so neither answer can be checked yet.
None of them regress a currently-verified-correct answer.

**What this does not touch.** `pipeline/join.py` itself. Another lane owns it. This entry
only imports from it. The archive's key (D219) and its pacing (D222) are untouched. The
real listing join's own D162/D240 behaviour is untouched.

Cites D240 (the seam and its first, reversed attempt), D219 (the archive this reads
`Bucket.product_id` from, and the empty-series mechanism this entry corrects), D222
(pacing, untouched), D234 (the glued-set-code repair `ProductIndex.find` still runs,
unchanged).
