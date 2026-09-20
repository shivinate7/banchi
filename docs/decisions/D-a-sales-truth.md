## D-a-sales-truth — Sales stops counting a refund as revenue, and a shortfall against today's market is not a loss

**Two changes to `#/revenue`.** Both are about what the screen admits it does not know. `docs/specs/revenue-plan.md` §1-2 is the plan. This is the record of what was built, corrected twice against the owner's real store, and why the second half stays honest.

### 1. Refunds: subtract what the operator already told this store, and say what that mechanism has actually caught

`closed_reason` rode on every order line's `progress` since D113. This screen never read it. `store/orders.py:174`'s own words for `not_shipping`: a refund or a cancellation, nothing will go. A sale later reversed stayed counted as revenue forever. There was no decrement and no flag. `docs/specs/revenue-next.md` §2 names this the most consequential finding in the file.

**The fix reads data already on the wire.** `salesOf` now matches each line's SKU against that order's own `progress` list. A line closed `not_shipping` is dropped from the total. It is counted in a new `refundExcluded` tally. No new route. No wire change. No widening of `server/order_transport.py`'s allowlist — the owner's ruling on the marketplace's own `refunds` field stands. This reads a value the store already had and was throwing away.

**Measured against the owner's real store, this mechanism catches nothing today.** 796 `fulfilment` lines: 739 `shipped_elsewhere`, 57 `null`, **0 `not_shipping`**. A search of all 804 order payloads for the string "refund" returned zero hits. The marketplace's own refund signal is not in this store in any form. What the screen already excludes is D214's own mechanism: 56 orders carrying `status = Canceled`, $3,059.07 of $69,393.78 gross (4.4%), unchanged by this branch.

**So the screen states BOTH counts, plainly, and never conflates them.** `revenue-verdict-canceled` says how many orders the marketplace's own `Canceled` status excluded. `revenue-verdict-refunded` says how many lines the OPERATOR's own `not_shipping` closed. Both render even at zero. A mechanism that stays silent when it has caught nothing looks identical to one that is not wired up. The refund sentence's own words remain: *"your own note, not TCGplayer's, so treat it as a habit rather than a guarantee."* This can only ever undercount a real refund. It can never overcount one. The day the owner closes a line as `not_shipping`, the count moves with no further change to this code.

### 2. Then against now: a market observation, never a profit or a loss

For an already-sold name, the product table can show its last sale's price against today's market. One press, `Compare to today's market`, calls `GET /pipeline/price-now?sku=...`.

**The first cut of this route read `readings` (D189) alone, and that was measured to be nearly worthless.** Against the owner's real store: 93 of 539 sold names had a `readings` entry. That covered $606 of $66,335 gross. It is 0.9%. None of those 93 were sealed product, which is roughly 93% of the owner's money. `readings` is built for `#/pricing`'s own on-hand walk. A sold copy is routinely gone from inventory. It is routinely never priced by that walk at all. Leaning on it here answered for under one percent of what this feature exists to cover.

**The real source is the price-history archive (D-a-price-history-archive, PR #416), tried first, with `readings` as the fallback.** `pkmnscan archive sweep` walks every SKU this store has ever recorded, sold or held, across four ranges. Sealed product is included. Unlike `readings`, the archive is filtered through neither on-hand inventory nor `#/pricing`'s own live-export walk. `do_pipeline_price_now` reads each SKU's newest `month`-range bucket. `month` is the finest range the archive keeps, so its newest bucket is the closest thing to a live quote. A bucket with no `market` is skipped in favor of an older one that has a price. Only where the archive has nothing does the route fall back to `readings`. `source` (`'archive'` or `'live'`) travels with the answer. The two ages mean different things: an archived bucket's age is the calendar day it covers. A `readings` row's age is the moment something last fetched or joined it.

**The coverage is stated on the screen, not left for a reader to infer.** `revenue-market-note` reads *"N of M names have a price today, K do not"*. A reader seeing a low N knows that is what they are looking at. Nobody has to assume every row got an honest look. Until the archive's sweep has covered the store, most rows will show `no reading`. That is D159's own rule applied here, not a defect: never a zero standing in for an absent price.

**Five rules, each checked by `app/tests/revenue.spec.ts`:**

1. **Never a profit or a loss.** No label says gain, loss, performance, beat or missed. The card was sold and the money was taken. The screen's own words: *"above/below/even with what it sold for."*
2. **Blind to cost, stated beside the figure.** `revenue-market-note` says so once, whenever a price has been fetched: *"Blind to what any of this cost you."* A card bought at two dollars and sold at eighteen against a twenty-dollar market is a large gain. This figure alone would draw it as a shortfall.
3. **A sign and a word, never a color (D62).** `marketCompareOf` returns `above`, `below` or `even with`. The cell prepends `+` or `−`. Nothing about the row's color changes with direction.
4. **Today's price carries its own age, whichever table answered.** `ReadingAge`, already built for D189's other callers, draws beside the figure regardless of `source`.
5. **No price draws no figure, never a zero.** A SKU neither table has priced renders `no reading`. The coverage count sits beside the total.

**The comparison is against the LAST sale under a name, not an average.** `Product.lastSku` and `Product.lastPrice` track the most recent sale's own SKU and price. Two printings can share a display name. Averaging across them would blur two different physical cards into one number nobody asked for.

### Ride-along defects (`docs/specs/revenue-plan.md` §5)

Taken in the same branch. The `compareLine` `lead` string no longer attributes "So far" to the closed prior period. It now reads *"Over the same stretch, the period before this one made..."*. `revenue.spec.ts` proves this against a populated prior window at the default period. The drill-down's order number now truncates on purpose with an ellipsis at a 14-character budget. It no longer clips mid-digit by accident. The product-name column is capped at two lines. A long name can no longer drag a row's numeric baselines down with it. The fifth period option (`Custom`) now wraps as a 3-and-2 grid at 390px, instead of sitting alone on its own row. `bn-stagger` now animates the month rows and the product table body. The verdict's headline figure is wrapped in one `<strong>`, matching Pricing's own rule for a verdict's key number.

### What this does not touch

The month chart's three known faults stand, per the owner's 2026-09-19 ruling. Money typography stays mono pending the repository-level ruling named in `docs/specs/revenue-plan.md` §5. The unsold-holdings "value over time" feature is untouched — a separate feature, deliberately not built here. Which sales the screen counts, and how the wire delivers them, is unchanged except for the refund subtraction above.

### Corrected twice, on measurement

This entry's first draft claimed refunds were reachable and that `readings` was the right source for "today's price". Neither claim was measured against the owner's real store before it was written. Both turned out wrong. The orchestrating session caught both, mid-build, by running the counts above. Neither correction touched the mechanism this branch already had right. `not_shipping` was always the correct field to read. The archive-first order is a source swap, never a rewrite of the comparison logic. What changed is what the screen is allowed to imply it has already handled.
