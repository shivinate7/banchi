/**
 * What the product sheet says about one card's prices and sales, above its history (T on a row).
 *
 * IT READS ONE LOCAL ROUTE (`GET /pipeline/price-facts`): two saved files and the worklist. So it
 * opens at once and asks no market host (D278 keeps its rule: a press, never follow-focus). Every
 * figure was computed on the server (`Series.window`); this draws them. A card with no saved
 * history draws its prices, one sentence and no empty grid. `--bn-*` tokens only.
 */

import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Money, Notice } from './kit'
import { absoluteDate, clockTime, monthDay, relativeDate } from './dates'
import { describeFailure, getPriceFacts, type Failure, failureTone } from './server'
import type { PriceFacts } from './types'
import './PriceFacts.css'

const shortDay = (iso: string) => monthDay(`${iso}T12:00:00`)

/** A money cell the server sent as text, or a dash. */
function cash(value: string | null | undefined) {
  return value === null || value === undefined || value === '' ? '—' : <Money value={Number(value)} />
}

/** Both ends of a range, or a dash. */
function span(low: string | null | undefined, high: string | null | undefined) {
  if (low == null || high == null) return '—'
  return (
    <>
      <Money value={Number(low)} /> to <Money value={Number(high)} />
    </>
  )
}

function Cell({ label, children, title }: { readonly label: string; readonly children: ReactNode; readonly title?: string }) {
  return (
    <div className="pricefacts-cell" title={title}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

/** Units sold each day as bars, the day's Market as a thin line over them. */
function DayChart({ days }: { readonly days: PriceFacts['days'] }) {
  const width = 300
  const height = 72
  const slot = width / Math.max(days.length, 1)
  const top = Math.max(1, ...days.map((day) => day[1]))
  const markets = days.map((day) => (day[5] === null ? null : Number(day[5])))
  const priced = markets.filter((value): value is number => value !== null)
  const lowest = Math.min(...priced)
  const highest = Math.max(...priced)
  const level = (value: number) => (highest === lowest ? height / 2 : height - 4 - ((value - lowest) / (highest - lowest)) * (height - 8))
  /* A DAY WITH NO PRICE BREAKS THE LINE; it is never joined across (`sparkSegments`' own rule). */
  const lines: string[] = []
  let open: string[] = []
  markets.forEach((value, index) => {
    if (value === null) {
      if (open.length > 1) lines.push(open.join(' '))
      open = []
      return
    }
    open.push(`${(index * slot + slot / 2).toFixed(1)},${level(value).toFixed(1)}`)
  })
  if (open.length > 1) lines.push(open.join(' '))
  const first = days[0]
  const middle = days[Math.floor(days.length / 2)]
  const last = days[days.length - 1]
  return (
    <figure className="pricefacts-chart">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`Copies sold each day for ${days.length} days, with the market price over them`}
        preserveAspectRatio="none"
      >
        {days.map((day, index) => {
          const tall = (day[1] / top) * (height - 2)
          return <rect key={day[0]} className="pricefacts-bar" x={index * slot + 1} y={height - tall} width={Math.max(slot - 2, 1)} height={tall} />
        })}
        {lines.map((points) => (
          <polyline key={points} className="pricefacts-line" points={points} />
        ))}
      </svg>
      <p className="pricefacts-legend">Bars are copies sold a day. The line is the market price.</p>
      <figcaption className="pricefacts-ticks" aria-hidden="true">
        <span>{first?.[0] ? shortDay(first[0]) : ''}</span>
        <span>{middle?.[0] ? shortDay(middle[0]) : ''}</span>
        <span>{last?.[0] ? shortDay(last[0]) : ''}</span>
      </figcaption>
    </figure>
  )
}

function percent(fraction: string | null | undefined): string {
  if (fraction == null) return '—'
  const value = Number(fraction) * 100
  return `${value > 0 ? 'Up' : value < 0 ? 'Down' : 'Flat'} ${Math.abs(value) >= 10 ? Math.round(Math.abs(value)) : Math.abs(value).toFixed(1)}%`
}

/** WHAT A CELL DRAWS WHILE THE READ IS OUT: a dash in the same place, so the block holds its size
 *  from the first paint (D313). */
const BLANK: PriceFacts = { sku: '', name: null, at: null, through: null, prices: { market: '', low: null, low_with_shipping: null, direct_low: null }, shelf: { on_hand: null, can_be_sent: null, listed_now: null, asking: null }, days: [], facts: {} }

export function PriceFactsBlock({ sku }: { readonly sku: string }) {
  const [facts, setFacts] = useState<PriceFacts | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  useEffect(() => {
    let alive = true
    setFacts(null)
    setFailure(null)
    getPriceFacts(sku)
      .then((payload) => {
        if (alive) setFacts(payload)
      })
      .catch((error) => {
        if (alive) setFailure(describeFailure(error))
      })
    return () => {
      alive = false
    }
  }, [sku])

  if (failure !== null) return <Notice tone={failureTone(failure)} code={failure.code}>{failure.message}</Notice>
  const loading = facts === null
  const shown = facts ?? BLANK
  const f = shown.facts ?? {}
  const days = shown.days ?? []
  const sold = f.sold_30d ?? 0
  const read = shown.at === null || shown.at === undefined ? null : `Read ${relativeDate(shown.at * 1000)}, ${clockTime(shown.at * 1000)}`
  const perSale = f.sales_30d ? (sold / f.sales_30d).toFixed(1) : '—'
  const prices = shown.prices
  const shelf = shown.shelf
  return (
    <div className="pricefacts" aria-busy={loading ? 'true' : undefined}>
      <section className="pricefacts-section" aria-labelledby="pricefacts-now">
        <h3 id="pricefacts-now">Prices now</h3>
        <p className="pricefacts-when">{read}</p>
        {!loading && prices === null ? (
          <p className="pricefacts-none pricefacts-body">No price has been read for this card yet.</p>
        ) : (
          <dl className="pricefacts-grid pricefacts-body">
            <Cell label="Market">{loading ? '—' : cash(prices?.market)}</Cell>
            <Cell label="Lowest">{loading ? '—' : cash(prices?.low)}</Cell>
            <Cell label="Lowest with shipping">{loading ? '—' : cash(prices?.low_with_shipping)}</Cell>
            <Cell label="Direct low">{loading ? '—' : prices?.direct_low ? cash(prices.direct_low) : <span className="pricefacts-quiet">not carried</span>}</Cell>
          </dl>
        )}
      </section>

      <section className="pricefacts-section" aria-labelledby="pricefacts-sales">
        <h3 id="pricefacts-sales">Sales, last 30 days</h3>
        <p className="pricefacts-when">{shown.through ? `Sales through ${absoluteDate(`${shown.through}T12:00:00`)}` : null}</p>
        {!loading && days.length === 0 ? (
          <p className="pricefacts-none pricefacts-sales-body">No sales history is saved for this card yet. Refresh now on Pricing reads it.</p>
        ) : (
          <div className="pricefacts-sales-body">
            {loading ? <div className="pricefacts-chart-hold" /> : <DayChart days={days} />}
            <dl className="pricefacts-grid">
              <Cell label="Sold">{loading ? '—' : sold}</Cell>
              <Cell label="Per sale">{loading ? '—' : perSale}</Cell>
              <Cell label="Avg sale 30d">{loading ? '—' : cash(f.avg_30d)}</Cell>
              <Cell label="Avg sale 7d">{loading ? '—' : cash(f.avg_7d)}</Cell>
              <Cell label="Sale range 30d">{loading ? '—' : span(f.low_30d, f.high_30d)}</Cell>
              <Cell label="Sale range 7d">{loading ? '—' : span(f.low_7d, f.high_7d)}</Cell>
              <Cell label="Best day">{loading ? '—' : f.best_day ? `${shortDay(f.best_day[0])}, ${f.best_day[1]} sold` : '—'}</Cell>
              <Cell label="Market 30d">{loading ? '—' : percent(f.change_30d)}</Cell>
            </dl>
          </div>
        )}
      </section>

      <section className="pricefacts-section" aria-labelledby="pricefacts-shelf">
        <h3 id="pricefacts-shelf">On your shelf</h3>
        {!loading && shelf === null ? (
          <p className="pricefacts-none pricefacts-body">This card is not on the waiting list.</p>
        ) : (
          <dl className="pricefacts-grid pricefacts-body">
            <Cell label="On hand">{loading ? '—' : (shelf?.on_hand ?? '—')}</Cell>
            <Cell label="Can be sent">{loading ? '—' : (shelf?.can_be_sent ?? '—')}</Cell>
            <Cell label="Listed now">{loading ? '—' : (shelf?.listed_now ?? '—')}</Cell>
            <Cell label="Your price">{loading ? '—' : cash(shelf?.asking)}</Cell>
          </dl>
        )}
      </section>
    </div>
  )
}
