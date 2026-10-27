# Price patterns: do chart signals carry a usable signal?

Research only. Nothing here is built, and nothing here sets a price. It is analysis for the
owner's own decisions, not investment advice.

## Scope

Riftbound and Pokemon singles first, with sealed as a side check. Slabs are not covered.
Singles are what the store lists in bulk and where the archive is deep: 1,004 Riftbound SKUs
across four sets. Slabs have no history here at all (the `slabs` tables hold zero rows).

## The data

| Source | What it is | How far back | Limits |
|---|---|---|---|
| `price_history` table (`banchi archive show`, D219, the archive never deletes) | TCGplayer's sold-price history per SKU: market, low, high, copies, transactions | 57 weekly buckets (the endpoint's annual range); 1-day buckets for the last 67 days | Only SKUs this store held or sold (D231, sold and sealed SKUs join the archive). About a third of weeks have no sale. The newest week is partial. The endpoint drops anything older than 357 days, so the archive is the only copy. |
| `inventory/.live/` live exports (D104, live fetch is guarded) | The store's own listings, with TCG Market Price and TCG Low Price per SKU | 90 files over about 7 weeks, with a two-week gap | Only SKUs the store lists. One reading of the lowest listing, not the whole order book. |
| `readings` table (`banchi readings show`, D189, the market reading is a table) | Newest market price per SKU | One reading per SKU, replaced on adopt | A cache, not history. Useless for time series. |
| `inventory/price-trends.json` | Month and annual points for the daily price job | Same window as the archive | A copy of what the archive holds. |
| Card Ladder (D320, My Slabs reads Card Ladder) | Slab sales, value and population | Card Ladder's own depth | Needs the owner's paid login. No slab is entered yet, so there is nothing to test. |
| TCGCSV daily archive (tcgcsv.com) | Nightly dump of TCGplayer's whole catalog prices | Its FAQ names the first daily file; not checked by download | Market and listing prices, not individual sales. Not downloaded. |
| PriceCharting, Cardmarket | eBay sold prices; EU marketplace prices | Years, per their sites | Different markets and fees from TCGplayer. Not downloaded. |

## Rules fixed before any test ran

- Use weekly buckets from the annual range only. Never stitch ranges (D219).
- Count a week only if it had at least one sale. Drop the partial newest week.
- Each set's clock starts at its US release week, checked on the web, not at its first sale.
- Momentum: 4 weeks back, skip 1 week, then 4 weeks ahead. Price at least $1, at least 2
  sales in each week used. Measure each card against its own set's median move that week,
  so the shared post-release fall is not mistaken for momentum. Skip each set's first 4 weeks.
- Score each test by rank correlation (Spearman) between signal and later move, per week, then
  average. A 90% interval comes from resampling blocks of 5 weeks. Zero means no signal.
- Effective sample is weeks, not card-weeks, because cards in one set move together.

## Findings

### 1. Price fall after release: real, steep and early. Its shape repeats; its depth does not.

Median price as a share of the release-week price, Riftbound singles. Cards per cell are
11 to 69.

| Set | Rarity | 2 wk | 4 wk | 8 wk | 12 wk | 24 wk |
|---|---|---|---|---|---|---|
| Spiritforged | Common | 0.57 | 0.51 | 0.46 | 0.40 | 0.49 |
| Spiritforged | Epic | 0.77 | 0.41 | 0.34 | 0.24 | 0.25 |
| Spiritforged | Showcase | 0.97 | 0.86 | 0.74 | 0.50 | 0.48 |
| Unleashed | Common | 0.47 | 0.41 | 0.36 | 0.35 | 0.39 |
| Unleashed | Epic | 0.72 | 0.61 | 0.59 | 0.54 | 0.47 |
| Unleashed | Showcase | 0.86 | 0.86 | 0.81 | 0.97 | 1.01 |
| Vendetta | Common | 0.56 | 0.42 | 0.37 | 0.37 | — |
| Vendetta | Epic | 0.55 | 0.48 | 0.30 | 0.24 | — |
| Origins | Rare | 1.07 | 1.03 | 0.85 | 0.56 | 0.70 |

- In sets 2 to 4, commons and uncommons lose about half their release-week price within
  2 weeks, and level out near 0.4 by week 8.
- Showcase cards fall least, and Unleashed's Showcase cards held their release price.
- Origins, the first set, behaved differently: rares rose for 4 weeks before falling.
- Pokemon Mega Evolution (5 to 12 cards per rarity) shows the same shape: 0.43 to 0.58 by
  week 4 to 8.
- **Did it predict?** The average of Origins and Spiritforged at week 12 forecast Unleashed and
  Vendetta. Rare: forecast 0.56, actual 0.59 and 0.46. Common: forecast 0.55, actual 0.35 and
  0.37. Epic: forecast 0.51, actual 0.54 and 0.24. The shape repeats; the level misses by up
  to 0.3. Four sets is too few to forecast depth.
- Presale weeks: rares sold at many times their release-week price two weeks before
  release (8 to 26 cards per set). This is suggestive only, from a few sales.

**Use:** a fresh set's commons, uncommons and Epics are worth most in their first two weeks.
That is a timing rule for listing, not a price.

### 2. Momentum (singles): no usable signal

| Variant | Weeks | Card-weeks | Mean score | 90% interval |
|---|---|---|---|---|
| Main rule | 48 | 6,637 | −0.04 | −0.08 to 0.01 |
| 3+ sales a week | 48 | 6,561 | −0.04 | −0.08 to 0.01 |
| Price at least $0.25 | 48 | 11,348 | 0.02 | −0.01 to 0.07 |
| Launch weeks kept | 48 | 7,355 | −0.02 | −0.07 to 0.02 |
| No skip week | 49 | 6,940 | −0.04 | −0.07 to 0.01 |
| First half / second half | 28 / 20 | — | −0.04 / −0.04 | both cross zero |

A card that rose more than its set over 4 weeks did not keep rising. If anything it gave a
little back, and every interval crosses zero.

### 3. Momentum (sealed): appeared, then failed out of sample

Over all weeks the score was 0.07 (interval 0.01 to 0.13, 2,839 product-weeks). The first half
scored 0.12 and the second half −0.00. It did not hold, so it is not usable.

### 4. Lowest listing against market price: the one signal that predicted

Signal: the lowest listing divided by TCG Market Price. Outcome: the change in TCG Market Price
over the next 14 days. Same SKUs each window, price at least $1.

| Window | SKUs | Score | Score after the prior 14-day move | Sealed only |
|---|---|---|---|---|
| 1 | 334 | 0.14 | 0.15 | 0.53 (83) |
| 2 | 333 | 0.36 | 0.36 | 0.41 (83) |
| 3 | 396 | 0.35 | 0.32 | 0.54 (111) |

- When the cheapest listing sits below the market price, the market price tends to fall
  toward it, and the reverse. About 1 SKU in 4 has its lowest listing above market.
- It is not just the market price snapping back: it survives removing the prior 14-day move.
- The store's own listing was the lowest on only 6 of 428 SKUs, so this is not the store
  moving its own number.
- **Limits:** 3 windows from about 7 weeks of files, mostly the same SKUs, all at one time of
  year. Treat it as strong-looking but not yet proven. Only the store's own listed SKUs.

### 5. Sealed against singles from the same set: unmeasured in practice

The pooled score was 0.27 over 51 set-periods in 7 sets. Per set it ran from −0.25 to 0.40,
with two of six sets negative. Too few sealed products per set to separate a signal from the
gap between sets.

### 6. Reprint shocks: unmeasured

There is no list of reprint dates. Finding reprints from price drops, then testing whether
price drops follow reprints, would be circular.

### 7. Slabs: unmeasured

No slab history exists in this store yet.

## What would change these answers

- **A whole-market history, not just this store's SKUs.** Every result above comes from cards
  the store held or sold. A daily full-catalog archive such as TCGCSV would remove that bias
  and add cards' lives before the store saw them.
- **More months of live exports.** Finding 4 needs a dozen or more non-overlapping windows to be
  trusted. The daily price job already collects them; time alone fixes this.
- **More set releases.** Four Riftbound sets cannot pin how deep a new set falls. Each new
  release adds one point.
- **A reprint calendar,** typed from announcements, to test reprint shocks.
- **Slabs entered on My Slabs,** to give Card Ladder history to test.

## Reproducing

The scripts are not product code. They read `inventory/store.sqlite` and `inventory/.live/`
read-only, and live in this lane's shared notes folder, outside the repo.
