/**
 * The shape of a price, on the row — D79, the batched half of D62.
 *
 * D62 GAVE THE HISTORY A PANEL AND A PRESS PER CARD, AND NAMED WHAT WOULD REOPEN IT: *"the
 * panel being opened on every card… the honest answer is a batched route — `readings_for_rows`
 * already exists in the module and groups by productId — and a column on the row rather than
 * a panel beside it. The measurement is whether the operator presses `T` more often than they
 * press `H`."* The owner answered that on 2026-08-31 by asking for the graphs on every row.
 * This is the column that entry specified.
 *
 * ------------------------------------------------------------------------------------
 * A SHAPE AND A SIGN. NO MONEY ON THIS ROW, EVER.
 *
 * The row already carries four dollar columns — MARKET, DIRECT, LOW, +SHIP — and the field a
 * listing price is typed into. A fifth figure here would be a READING rather than a price,
 * sitting inches from that field, and the distance between reading it and copying it across is
 * one keystroke. D8 makes the export the pricing source and D62 refused to reopen it by name;
 * putting `$16.33 avg sale` on this row is that refusal being spent quietly rather than argued.
 *
 * So the vwap, its bound, the liquidity and the spread all stay on the panel, which is where
 * there is room to draw the anchor at size and the bound muted beneath it. What is here is the
 * question a list answers that a panel cannot: WHICH of these forty-six is moving.
 *
 * ------------------------------------------------------------------------------------
 * THE CAVEATS ARE STATED ONCE, ABOVE THE LIST, AND NOT FORTY-SIX TIMES.
 *
 * D62's panel owes a reader three things: that the ranges OVERLAP and can point opposite ways,
 * what span each covers, and that the wider one can be the staler. A 80px cell can carry none
 * of them, and forty-six copies of a date is the panel drawn badly rather than a list. They go
 * in `Pricing.tsx`'s one status line instead — which is honest because the spans are identical
 * across every SKU of a run: measured, all 46 on `2026-08-31-box3-01`, both ranges.
 *
 * ------------------------------------------------------------------------------------
 * DIRECTION IS A SIGN, NEVER A COLOR — D62's rule, and it binds harder here.
 *
 * `docs/DESIGN.md` locks a palette with no red and no green, and `accent` already means
 * "unsure" and "the only action". On the panel a colored percentage would collide with that;
 * on a list of forty-six it would also be the loudest thing on the screen, over the readings
 * that are the least authoritative thing on it. The sign carries it, at 10px, muted.
 */

import type { TrendRange } from './types'
import { RANGE_LABEL, sparkSegments } from './PriceHistory'
import './PriceTrend.css'

/** What this row's strip knows. `undefined` is "never asked", which is not a failure and is
 *  drawn as nothing — the at-cap rows the batch skips are in this state permanently, and a
 *  dash on them would report an outage over rows nobody asked about (see `TrendsPayload`). */
export type TrendRead =
  | { kind: 'reading' }
  | { kind: 'read'; ranges: TrendRange[] }
  | { kind: 'refused'; why: string }

/** A ratio the SERVER computed, as a percentage. The only arithmetic here, and it is the same
 *  function `PriceHistory.tsx` carries for the same reason: it multiplies an already-computed
 *  dimensionless ratio by 100 to write it the way people read it, and nothing downstream reads
 *  the result. It is ink. `app/src/server.ts` forbids this app computing rules the pipeline
 *  owns, and every one of those is about money. */
function percent(fraction: string | null): string | null {
  if (fraction === null) return null
  const value = Number(fraction)
  if (!Number.isFinite(value)) return null
  return `${value > 0 ? '+' : ''}${(value * 100).toFixed(1)}%`
}

/** One range: the shape, and the sign beneath it.
 *
 *  THE SVG IS `aria-hidden` AND THE PERCENTAGE IS NOT, which is the whole of this cell's
 *  accessibility story and is deliberate rather than an omission. There is no honest short
 *  alt text for thirty buckets, and the figure the shape is about is printed directly below it
 *  as text — so a reader that announced the path would be repeating the row rather than adding
 *  to it. `PriceHistory.tsx`'s Spark makes the identical call. */
function Mini({ range }: { range: TrendRange }) {
  const W = 80
  const H = 20
  const label = RANGE_LABEL[range.range] ?? range.range
  const moved = percent(range.fraction)
  const segments = sparkSegments(
    range.points.map((value) => (value === null ? null : Number(value))),
    W,
    H,
  )
  return (
    <span className="pricetrend-mini">
      {segments === null ? (
        /* FEWER THAN TWO PRICED BUCKETS IS NOT A LINE. Drawn as an empty box of the same
           height rather than as nothing, so the row below does not shift up into the gap and
           the column stays a column. */
        <span className="pricetrend-blank" aria-hidden="true" />
      ) : (
        <svg
          className="pricetrend-spark"
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          aria-hidden="true"
          focusable="false"
        >
          {segments.map((segment, at) => (
            <polyline key={at} points={segment.join(' ')} />
          ))}
        </svg>
      )}
      <span className="pricetrend-figure">
        {/* THE RANGE'S NAME IS IN THE CAPTION AND NOT ON THE ROW — one label per column, the
            same argument `.pricing-caption kbd` makes for the snap keys directly above: the
            four choices are the same on every row, so the key belongs where the eye already
            is. It is repeated here for a SCREEN READER only, which has no caption to have
            read, and hidden from the eye that does. */}
        <span className="pricetrend-said">{label} </span>
        {moved ?? '—'}
      </span>
    </span>
  )
}

/**
 * The strip in one row's trend column.
 *
 * IT DRAWS NOTHING UNTIL SOMETHING IS ASKED. An empty cell is the correct rendering of "the
 * operator has not pressed the button", of "this row is at the cap so the batch skipped it",
 * and of a run whose trends were never loaded — three states that all mean *no claim is being
 * made here*, and a placeholder in any of them would be a claim.
 */
export function TrendCell({ read }: { read: TrendRead | undefined }) {
  if (read === undefined) return <span className="pricetrend" />
  if (read.kind === 'reading') {
    return (
      <span className="pricetrend">
        <span className="pricetrend-waiting">reading…</span>
      </span>
    )
  }
  if (read.kind === 'refused') {
    /* A REFUSAL IS A DASH WITH ITS SENTENCE IN `title`, and the sentence is the server's
       own. There are three kinds and they have three different remedies — a `misc` card with
       no catalogue (D22), a walk that matched no single product, a mirror that did not answer
       — so the text is never flattened to "failed" here. What the row has room for is the
       fact that this one was asked and could not be told; the reason is one hover away, and
       the count is in the status line above the list. */
    return (
      <span className="pricetrend">
        <span className="pricetrend-refused" title={read.why}>
          —
        </span>
      </span>
    )
  }
  if (read.ranges.length === 0) {
    /* A REAL, CATALOGUED PRODUCT THE ENDPOINT HAS NEVER SEEN SELL. HTTP 200 with a null
       result, measured on two of them, so this is a card that has not traded rather than one
       we could not find — and drawing it as a refusal would report a join defect over a card
       that is merely illiquid. */
    return (
      <span className="pricetrend">
        <span className="pricetrend-refused" title="no recorded sales — this card has not traded">
          no sales
        </span>
      </span>
    )
  }
  return (
    <span className="pricetrend">
      {read.ranges.map((range) => (
        <Mini key={range.range} range={range} />
      ))}
    </span>
  )
}
