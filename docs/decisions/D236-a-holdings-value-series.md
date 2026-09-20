## D236 — Unsold stock is valued by SKU off the archive, one range at a time, and sealed stock is a counted gap

**THE FEATURE.** `docs/specs/revenue-plan.md` section 1 names two features. `D225` built the
first: sold cards, then against now. This entry builds the second: unsold stock, valued at
market, shown moving over time. Neither may merge into the other's figure. That is the
owner's own ruling.

**THE POSITION IS THE SKU.** D212 settles fungibility. Every copy of a SKU is
interchangeable. A holding is one quantity, not a list of slots.
`pipeline/holdings.py:on_hand_quantities` counts a copy once. It counts a copy only when its
`state` is not one of `store/master.py:TERMINAL_STATES`. `Inventory.copies_on_hand` already
states this rule for one SKU. This function walks the whole table once instead. It never
reads `Listing.live`. That count is a stale marketplace mirror between reconciles. It answers
a different question.

**THE SERIES SOURCE IS THE ARCHIVE.** This became possible only today. When
`docs/specs/revenue-plan.md` was written, this store held only one market reading per SKU
(`readings`, D189). The price-history archive (D219) has since grown to roughly 155,000
buckets over 1,121 SKUs. That covers 99.96% of gross. That is what turns "value over time"
into an actual line. `pipeline/holdings.py:sku_series` reads
`store/pricearchive.py:PriceArchive.for_sku`. It filters to one requested range. It
multiplies each bucket's own `market` by the SKU's current on-hand quantity.

**RANGES ARE NEVER MERGED.** D62 sets this rule. This feature answers four separate
questions, not one. `GET /pipeline/holdings-value?range=<month|quarter|semiannual|annual>`
answers exactly one range per call. Nothing here offers a combined series. The four ranges
overlap on the calendar. Adding them would double-count. `month` is the default. It is the
finest range and the closest thing to a daily mark.

**A MISSING BUCKET BREAKS THE LINE, AND THERE ARE TWO WAYS TO BE MISSING.** A day the
source answered with no price stores a real row, dated correctly, with `market: None`.
`pipeline/productview.py`'s own convention already passes that null through, and this
feature does the same: the point's own `value` is `None`, never a zero. A day no sweep ever
reached is different. It never appears in `archive.for_sku`'s own list at all, so it cannot
carry a null. This module gives that case its own signal: `gap_before`, a boolean on every
`SeriesPoint` after the first. It is computed from the immediately preceding STORED point,
never from the calendar day before it. It is true only when two stored points are not
exactly one bucket-width apart. A priced-None day one bucket-width from its own neighbor
carries no gap. The missing PRICE and the missing DAY are two different facts. Only the
second breaks the line by date. A screen must still treat a `null` value as nothing to plot.
It must still break its drawn line at `gap_before`. `aggregate_totals`'s own portfolio
points carry the same `gap_before` field, computed the same way.

**QUANTITY IS NEVER HISTORICAL.** This store keeps no record of past on-hand counts. Every
point in one SKU's series is valued at today's on-hand count. `SeriesPoint.quantity` states
this on every point. A screen drawing this series draws what today's shelf would have been
worth on each past date. It never draws what the shelf actually held then.

**SEALED PRODUCT IS A NAMED, COUNTABLE EXCLUSION.** It is never a silent drop. The owner
ruled this again on 2026-09-20: "still stands — singles, stated gap." Sealed product has no
`cards` row. It never will. `pipeline/games.py` states plainly that sealed is never
captured. So there is no quantity for this feature to multiply through. This is a fact about
the schema, not an oversight. `pipeline/holdings.py:sealed_excluded_count` counts what it can
count. It counts every distinct SKU the order ledger has ever priced a line for, that the
`cards` table has never recorded in any state. `pipeline/pricearchive.py:ledger_subject_rows`
already found this gap. This function reads it directly, and skips that function's own live
catalog resolution, which this feature does not need. The route's `sealed_excluded` field
carries the count and the reason together. A caller cannot forward the number without the
sentence that makes it honest. The ledger widening that landed today only tells this store
about sealed product the owner sold. It adds no on-hand quantity anywhere. The count above is
still the only honest answer to how much sealed stock sits on the shelf.

**AN UNPRICED NAME IS COUNTED, NEVER SHOWN AS ZERO.** D159 sets this rule and it is
inherited here. `unmarked.names` is the on-hand SKU count minus however many of them
`archive.for_sku` answers anything for, in any range. A SKU the sweep has visited under
`quarter` but not yet under `month` is a coverage fact about the sweep. It is not an absent
card.

**THE PORTFOLIO TOTAL IS AN HONEST PARTIAL SUM.** It is never a rollup held over.
`pipeline/holdings.py:aggregate_totals` sums, at every calendar start any SKU has a priced
point for, only the SKUs actually priced at that exact date. A later total covering fewer
SKUs is a smaller, honestly partial number. It never carries forward a value from a SKU this
pass did not re-read. Every `TotalPoint` carries `priced_names` and `unpriced_names` beside
the sum. A total never implies coverage it does not have.

### What this does not touch

No route here reads or writes `readings` (D189). That table is a single live mark built for
`#/pricing`'s on-hand walk. D225 found it answers for under 1% of sold gross. The archive is
now the whole story for a series. Nothing here falls back to `readings`, unlike
`do_pipeline_price_now`'s single-point read. Nothing here writes anything. This is a read
over an already-swept archive, the same posture as `do_pipeline_value` and
`do_product_history`. `pkmnscan archive sweep` stays the one press that fills the table this
feature reads. D219's own statement on that stands, unamended.

### Not yet reachable from a screen

`GET /pipeline/holdings-value` exists on the wire and nowhere else. There is no client
function in `app/src/server.ts`. There is no wire type in `app/src/types.ts`. There is no
control in `#/revenue` or anywhere else. `CLAUDE.md`'s route-is-not-a-feature rule applies.
The capability is not built. It is only reachable. This is named here rather than left to be
found later. The wire shape below is exact, so the screens lane can build against it without
guessing.

```
GET /pipeline/holdings-value?range=month|quarter|semiannual|annual   (default: month)

200 {
  "range": "month",
  "width_days": 1,
  "history_begins": "2026-08-01" | null,   // earliest bucket start any on-hand SKU has in
                                            // this range, or null if nothing archived yet
  "at": 1758345600,                         // this READ's own moment, not a series date
  "on_hand_names": 812,                     // distinct on-hand SKUs this store knows of
  "series": [
    {
      "sku": "123456",
      "name": "Vilemaw",
      "quantity": 3,
      "latest_value": "61.50" | null,       // null when every point is unpriced
      "points": [
        {
          "start": "2026-08-01",
          "market": "20.50" | null,          // this bucket's own market. Null means a real
                                              // day the source answered with nothing
          "quantity": 3,
          "value": "61.50" | null,           // market times quantity. Null when market is
                                              // null
          "gap_before": false                // true means this point does not continue
                                              // from the one before it. Break the line.
                                              // Never connect across it. Never interpolate.
        }
      ]
    }
  ],
  "totals": [
    {
      "start": "2026-08-01",
      "value": "4213.90",                    // sum of every SKU priced at exactly this date
      "priced_names": 340,
      "unpriced_names": 472,                 // on_hand_names minus priced_names, at this
                                              // one date
      "gap_before": false
    }
  ],
  "unmarked": { "names": 261 },              // on-hand SKUs the archive has never priced,
                                              // in any range. Never shown as zero
  "sealed_excluded": {
    "names": 47,
    "reason": "Sealed product has no card record. This store cannot count what sits on the
               shelf. Sales of sealed product are known. Unsold sealed stock is not counted
               here."
  }
}

400 { "code": "range_unknown", "message": "..." }         // range not one of the four
503 { "code": "store_unreadable", "message": "..." }
```

A screen built against this must never draw a straight line through a `gap_before: true`
point. It must never draw `unmarked.names` or `sealed_excluded.names` as zero. It must never
omit either count. It must never sum `series[].points` on its own into a second total. That
second total could drift from `totals`. The server's own partial-coverage sum is the only
total this route offers.

### What was measured, and how

`scripts/holdings-selftest.py` proves `pipeline/holdings.py` against fixtures built inside
the test. There is no store on disk and no network. It covers four cases. An on-hand name
with no archived reading at all is counted in `unmarked`, never shown as a zero. An on-hand
name with a reading produces a correctly valued point. A range with a real calendar gap
between two archived buckets sets `gap_before` true. It sets it on the point after the gap,
and on the aggregate total's own point at the same seam. A ledger SKU absent from `cards` is
counted in `sealed_excluded_count`. It is never silently dropped.

Two mutation arms are included. Each is proved to fail once the guard it checks is defeated.
Forcing `_adjacent` to always answer `True` makes the gap interpolate, and turns the gap
assertion red. Skipping `sealed_excluded_count`'s subtraction, so it always answers `0`,
turns the sealed assertion red. This selftest is not wired into `make check`. That follows
`scripts/pricearchive-selftest.py`'s own precedent. Both are fast, self-contained proofs of a
package with no caller reachable from a screen yet.

This entry does not freeze a coverage number measured against the owner's real store. Such a
number goes stale the moment the next sweep runs. The PR body carries what was measured once,
read-only, at build time.
