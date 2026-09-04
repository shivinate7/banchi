/**
 * What one SKU has been selling for, drawn in the pricing drawer beside the hold that needs it.
 *
 * THE VWAP IS THE ANCHOR AND THE BOUND IS A SANITY CHECK — never peers. `vwap` is the only
 * figure at display size; `bound` is one muted line beneath it carrying its own width.
 *
 * THE TWO RANGES SIT SIDE BY SIDE AND NOTHING ADDS THEM UP. `annual` includes the same recent
 * days as `month` at a coarser width, so they can point opposite ways, and the wider one is
 * the staler (weekly buckets are stamped at the start of their week). Each range draws its
 * own span.
 *
 * THIS PANEL PRICES NOTHING AND WRITES NOTHING. Every figure is a reading beside the export.
 */

import { useMemo } from 'react'
import type { HistoryPoint, HistoryRange, PriceHistoryPayload } from './types'
import { Button, Icon, Notice } from './kit'
import './PriceHistory.css'

/** How a range is captioned. The endpoint's own range names are drawn beside these, small. */
export const RANGE_LABEL: Record<string, string> = {
  month: 'Daily',
  quarter: '3-day',
  semiannual: 'Weekly',
  annual: 'Weekly',
}

/** A ratio the SERVER computed, rendered as a percentage. The only arithmetic on this panel. */
function percent(fraction: string | null): string | null {
  if (fraction === null) return null
  const value = Number(fraction)
  if (!Number.isFinite(value)) return null
  return `${value > 0 ? '+' : ''}${(value * 100).toFixed(1)}%`
}

/** POSITIVE IS RISING — a word beside the number so the sign is legible to a person. */
function direction(fraction: string | null): 'rising' | 'falling' | 'flat' | 'not enough sales to say' {
  if (fraction === null) return 'not enough sales to say'
  const value = Number(fraction)
  if (!Number.isFinite(value) || value === 0) return 'flat'
  return value > 0 ? 'rising' : 'falling'
}

/** A series of prices as polyline point-lists, oldest on the left. `null` where a bucket
 *  carries no price at all; the line BREAKS there rather than interpolating across it.
 *  Shared with `PriceTrend.tsx` so the panel and the row cannot disagree on the geometry. */
export function sparkSegments(
  priced: (number | null)[],
  W: number,
  H: number,
): Point[][] | null {
  const known = priced.filter((v): v is number => v !== null && Number.isFinite(v))
  if (known.length < 2) return null
  const lo = Math.min(...known)
  const hi = Math.max(...known)
  const span = hi - lo || 1
  const step = priced.length > 1 ? W / (priced.length - 1) : W
  /* POINTS, NOT STRINGS. A segment used to be an array of `"x,y"` and the renderer read a
     point's x back out of it with `split(',')` — which is the shape `app/eslint.config.js`
     bans on sight, for a good reason that happens not to apply here and a rule that cannot
     tell. Carrying the pair and formatting once at the edge is better anyway: the renderer
     stops parsing something this function just built. */
  const segments: Point[][] = []
  let current: Point[] = []
  priced.forEach((value, at) => {
    if (value === null || !Number.isFinite(value)) {
      if (current.length > 1) segments.push(current)
      current = []
      return
    }
    current.push([at * step, H - ((value - lo) / span) * (H - 4) - 2])
  })
  if (current.length > 1) segments.push(current)
  return segments.length ? segments : null
}

/** One plotted point, in the viewBox's own units. */
type Point = readonly [number, number]

/** A run of points as SVG wants them: `x,y x,y` at one decimal. */
function plot(segment: readonly Point[]): string {
  return segment.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
}

function Spark({ points, tone }: { points: HistoryPoint[]; tone: string }) {
  const W = 320
  const H = 56
  const runs = useMemo(
    () =>
      sparkSegments(
        points.map((p) => (p.market === null ? null : Number(p.market))),
        W,
        H,
      ),
    [points],
  )
  if (runs === null) return <div className="pricehistory-spark pricehistory-spark-empty" aria-hidden="true" />
  return (
    <svg
      className="pricehistory-spark"
      data-tone={tone}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      aria-hidden="true"
      focusable="false"
    >
      {runs.map((segment, at) => {
        const first = (segment[0]?.[0] ?? 0).toFixed(1)
        const last = (segment[segment.length - 1]?.[0] ?? W).toFixed(1)
        const line = plot(segment)
        return (
          <g key={at}>
            <polygon className="pricehistory-area" points={`${first},${H} ${line} ${last},${H}`} />
            <polyline points={line} pathLength={1} />
          </g>
        )
      })}
    </svg>
  )
}

function Range({ range }: { range: HistoryRange }) {
  const label = RANGE_LABEL[range.range] ?? range.range
  const moved = percent(range.momentum.fraction)
  const word = direction(range.momentum.fraction)
  const tone = word === 'rising' ? 'up' : word === 'falling' ? 'down' : 'flat'
  return (
    <section className="pricehistory-range" data-tone={tone}>
      <header className="pricehistory-range-head">
        <div className="pricehistory-range-title">
          <h4>{label}</h4>
          <span className="pricehistory-machine">{range.range}</span>
        </div>
        <span className="pricehistory-span">
          {range.from ?? '?'} → {range.to ?? '?'}
        </span>
      </header>

      <Spark points={range.points} tone={tone} />

      <div className="pricehistory-anchor">
        {range.vwap === null ? (
          <span className="pricehistory-none">no sales in this range</span>
        ) : (
          <>
            <span className="pricehistory-figure">${range.vwap}</span>
            <span className="pricehistory-vwap-key">avg sale</span>
            {moved === null ? null : (
              <span className="pricehistory-moved" data-tone={tone}>
                <Icon name={tone === 'up' ? 'trendUp' : tone === 'down' ? 'trendDown' : 'minus'} size={12} />
                {moved}
              </span>
            )}
          </>
        )}
      </div>
      {range.bound === null ? null : (
        <p className="pricehistory-bound">
          could be ${range.bound.low}–${range.bound.high}
          {percent(range.bound.width_of_vwap) === null
            ? null
            : ` · ±${((Number(range.bound.width_of_vwap) / 2) * 100).toFixed(0)}%`}
        </p>
      )}

      <dl className="pricehistory-facts">
        <div>
          <dt>Moved</dt>
          <dd>
            {moved === null ? '—' : moved}
            <span className="pricehistory-word">{word}</span>
          </dd>
        </div>
        <div>
          <dt>Sold</dt>
          <dd>
            {range.liquidity}
            <span className="pricehistory-word">
              {range.transactions} order{range.transactions === 1 ? '' : 's'}
            </span>
          </dd>
        </div>
        <div>
          <dt>Spread</dt>
          <dd>
            {range.dispersion === null ? '—' : `$${range.dispersion}`}
            <span className="pricehistory-word">within a bucket</span>
          </dd>
        </div>
      </dl>
    </section>
  )
}

export type HistoryRead =
  | { kind: 'reading' }
  | { kind: 'read'; payload: PriceHistoryPayload }
  | { kind: 'refused'; why: string }

/**
 * The body of the history drawer. `pinned` is the deliberate open (the history control's
 * click, or this panel's own Keep) and stands until closed; unpinned is a HELD `t` aimed by
 * the pointer, which ends on the release — so the footer offers the press that stops it ending.
 */
export function PriceHistoryPanel({
  sku,
  name,
  read,
  pinned,
  readAge,
  onClose,
  onKeep,
  onRetry,
}: {
  sku: string
  name: string
  read: HistoryRead | undefined
  pinned: boolean
  /** How old the EXPORT figure below is, in words. The sales history is fetched live; the
   *  market price beside it is a cell out of a file the join froze, so it is dated rather than
   *  drawn as a fact about today (the owner's rule for a live figure, 2026-09-03). */
  readAge?: string | null
  onClose: () => void
  onKeep: () => void
  onRetry: () => void
}) {
  return (
    <div className="pricehistory" data-pinned={pinned ? 'true' : 'false'}>
      <header className="pricehistory-head">
        <h3 title={name}>{name}</h3>
        <span className="pricehistory-machine">sku {sku}</span>
      </header>

      {read === undefined || read.kind === 'reading' ? (
        <div className="pricehistory-loading" aria-live="polite" aria-label="reading the price history">
          <span className="bn-skeleton" style={{ height: 18, width: '55%' }} />
          <span className="bn-skeleton" style={{ height: 56 }} />
          <span className="bn-skeleton" style={{ height: 30, width: '40%' }} />
          <span className="bn-skeleton" style={{ height: 56 }} />
          <span className="bn-skeleton" style={{ height: 30, width: '40%' }} />
        </div>
      ) : read.kind === 'refused' ? (
        <div className="pricehistory-state">
          <Notice tone="danger" title="The reading did not come back">
            {read.why}
          </Notice>
          <Button icon="refresh" onClick={onRetry}>
            Try again
          </Button>
        </div>
      ) : read.payload.never_sold || read.payload.ranges.length === 0 ? (
        <div className="pricehistory-state">
          <Notice tone="info" title="No recorded sales">
            The product resolved, so this is a card that has not traded rather than one we
            could not find.
          </Notice>
        </div>
      ) : (
        <>
          <div className="pricehistory-listed">
            <span className="pricehistory-listed-key">
              <Icon name="tag" size={12} /> Export market
            </span>
            <span className="pricehistory-listed-value" data-empty={read.payload.market === null ? 'true' : undefined}>
              {read.payload.market === null ? 'no market price' : `$${read.payload.market}`}
            </span>
            <span className="pricehistory-listed-note">
              {read.payload.market === null ? (
                <>
                  the export carries no price for this card
                  <span className="pricehistory-machine">no_market_data</span>
                </>
              ) : (
                <>
                  what the card is priced against
                  {readAge === null || readAge === undefined ? null : (
                    <span className="pricehistory-listed-age">· read {readAge}</span>
                  )}
                </>
              )}
            </span>
          </div>
          <div className="pricehistory-ranges">
            {read.payload.ranges.map((range) => (
              <Range key={range.range} range={range} />
            ))}
          </div>
          {read.payload.ranges.length > 1 ? (
            <p className="pricehistory-note">
              <Icon name="info" size={13} />
              The ranges overlap and are read separately — the wider one includes these same
              recent days at a coarser width, so they can point opposite ways.
            </p>
          ) : null}
        </>
      )}

      <div className="pricehistory-controls">
        {pinned ? (
          <Button variant="quiet" icon="x" onClick={onClose}>
            Close
          </Button>
        ) : (
          <>
            <span className="pricehistory-peek">
              Release <kbd className="bn-kbd">T</kbd> to close
            </span>
            <Button variant="quiet" icon="pin" onClick={onKeep}>
              Keep open
            </Button>
          </>
        )}
      </div>
    </div>
  )
}
