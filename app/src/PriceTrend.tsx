/**
 * The shape of a price, inline on a pricing row — D79, the batched half of D62.
 *
 * A shape and a sign, never money: the vwap, its bound, the liquidity and the spread all stay
 * on the history drawer, where there is room to draw the anchor at size. What this cell answers
 * is the question a list answers and a drawer cannot — WHICH of these forty-six is moving.
 *
 * The caveats (the two ranges overlap, each has its own span, the wider is the staler) are
 * stated once above the list by `Pricing.tsx`, not forty-six times here.
 */

import type { TrendRange } from './types'
import { RANGE_LABEL, sparkSegments } from './PriceHistory'
import './PriceTrend.css'

/** What this row's strip knows. `undefined` is "never asked", which is not a failure and is
 *  drawn as nothing — the at-cap rows the batch skips are in this state permanently. */
export type TrendRead =
  | { kind: 'reading' }
  | { kind: 'read'; ranges: TrendRange[] }
  | { kind: 'refused'; why: string }

/** A ratio the SERVER computed, as a percentage. The only arithmetic here; it is ink. */
function percent(fraction: string | null): string | null {
  if (fraction === null) return null
  const value = Number(fraction)
  if (!Number.isFinite(value)) return null
  return `${value > 0 ? '+' : ''}${(value * 100).toFixed(1)}%`
}

function directionOf(fraction: string | null): 'up' | 'down' | 'flat' | 'none' {
  if (fraction === null) return 'none'
  const value = Number(fraction)
  if (!Number.isFinite(value) || value === 0) return 'flat'
  return value > 0 ? 'up' : 'down'
}

/** One range: the shape, and the sign beside it. The SVG is decorative; the figure is text. */
function Mini({ range }: { range: TrendRange }) {
  const W = 56
  const H = 18
  const label = RANGE_LABEL[range.range] ?? range.range
  const moved = percent(range.fraction)
  const direction = directionOf(range.fraction)
  const segments = sparkSegments(
    range.points.map((value) => (value === null ? null : Number(value))),
    W,
    H,
  )
  return (
    <span className="pricetrend-mini" data-direction={direction} title={`${label} · ${moved ?? 'not enough sales to say'}`}>
      {segments === null ? (
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
            <polyline key={at} points={segment.join(' ')} pathLength={1} />
          ))}
        </svg>
      )}
      <span className="pricetrend-figure">
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
 * and of a run whose trends were never loaded.
 */
export function TrendCell({ read }: { read: TrendRead | undefined }) {
  if (read === undefined) return <span className="pricetrend pricetrend-empty" />
  if (read.kind === 'reading') {
    return (
      <span className="pricetrend pricetrend-reading" aria-label="reading the trend">
        <span className="bn-skeleton pricetrend-skel" />
        <span className="bn-skeleton pricetrend-skel" />
      </span>
    )
  }
  if (read.kind === 'refused') {
    return (
      <span className="pricetrend">
        <span className="pricetrend-refused" title={read.why}>
          —
        </span>
      </span>
    )
  }
  if (read.ranges.length === 0) {
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
