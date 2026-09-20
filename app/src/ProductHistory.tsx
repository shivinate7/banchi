/**
 * `#/product` — one product's own page: what it has been selling for, with the owner's own
 * sales marked on it (D227, `docs/specs/revenue-plan.md` section 3).
 *
 * TWO KINDS OF OBSERVATION, NEVER ONE LINE. The market series is an aggregate of many
 * transactions this store never saw. The owner's own fills — from `GET /orders`, the same
 * payload `Revenue.tsx` already reshapes — are exact: a price, a quantity, a date, each one
 * real. They are drawn with different marks and a legend, and NEVER joined into one polyline.
 * `sparkSegments`'s break-on-null rule already covers the market series; nothing here
 * interpolates across a bucket with no price.
 *
 * BUCKET WIDTH IS STATED BESIDE EVERY CHART, because it is not a fact about the sale — it is
 * a fact about how coarsely the source is willing to describe it TODAY. The same sale reads
 * as a one-day bucket this month and a seven-day bucket by winter.
 *
 * NOTHING DRAWS PAST WHAT THE SOURCE ACTUALLY READ. `history_begins` comes off the server,
 * computed from the buckets it actually holds — never the 357-day ceiling as a constant. A
 * sale older than that has no market data at all, and it is listed separately, named as such,
 * rather than silently dropped or plotted against nothing.
 *
 * READ-ONLY. This screen writes nothing and triggers no sweep — `getProductHistory` reads
 * `store/pricearchive.py` first and only reaches a live host when that table has never swept
 * this SKU, which its own docstring states plainly under `source`.
 *
 * REACHED BY HASH ALONE. `app/src/Revenue.tsx` is being edited by another branch as this was
 * built, so no link into this screen was added there (see `app/src/App.tsx`'s route
 * comment). This page carries its own SKU field, which is the control a person who lands
 * here with no query string actually finds — `?sku=<id>` is the deep link for everyone else.
 */

import { useEffect, useMemo, useState } from 'react'
import { describeFailure, getOrders, getProductHistory, type Failure } from './server'
import type { OrderLineWire, OrderRow, ProductHistoryPayload, ProductHistoryRange } from './types'
import { Button, EmptyState, Notice, PageHeader, Pill } from './kit'
import { money } from './money'
import { sparkSegments } from './PriceHistory'
import './ProductHistory.css'

const RANGE_LABEL: Record<string, string> = {
  month: 'Daily',
  quarter: '3-day',
  semiannual: 'Weekly',
  annual: 'Weekly',
}

/** The one word this screen shares with `Revenue.tsx` for "not a sale" — folded the same way. */
function isCanceled(status: string | null): boolean {
  return (status ?? '').trim().toLowerCase() === 'canceled'
}

type Fill = {
  readonly at: Date
  readonly orderNumber: string
  readonly quantity: number
  readonly unitPrice: number
}

/** Every fill this store recorded for one SKU — D212's grain, never a name. Mirrors
 *  `Revenue.tsx:salesOf`'s own filter (canceled dropped, an unparseable price or date
 *  dropped) but keyed on `line.sku` rather than grouped by name, because a name can cover
 *  more than one printing and this page is about one product. */
function fillsFor(sku: string, orders: readonly OrderRow[]): Fill[] {
  const fills: Fill[] = []
  for (const order of orders) {
    if (isCanceled(order.status)) continue
    if (order.placed_at === null) continue
    const at = new Date(order.placed_at)
    if (Number.isNaN(at.getTime())) continue
    for (const line of order.lines as readonly OrderLineWire[]) {
      if (line.sku !== sku) continue
      const price = line.unit_price === null ? NaN : Number(line.unit_price)
      if (!Number.isFinite(price)) continue
      fills.push({ at, orderNumber: order.number, quantity: line.quantity, unitPrice: price })
    }
  }
  fills.sort((a, b) => a.at.getTime() - b.at.getTime())
  return fills
}

function readSkuFromHash(): string {
  return new URLSearchParams(window.location.hash.split('?')[1] ?? '').get('sku') ?? ''
}

function writeSkuToHash(sku: string): void {
  const next = sku === '' ? '#/product' : `#/product?sku=${encodeURIComponent(sku)}`
  if (window.location.hash !== next) window.history.replaceState(null, '', next)
}

/** ONE PLOTTED POINT, in real chart-space pixels, over a TIME scale — not the equal-spaced
 *  index scale `PriceHistory.tsx:sparkSegments` uses for its own compact panel. A per-product
 *  page has room to be honest about WHEN a bucket sits relative to WHEN a fill happened,
 *  which the panel's five-figure summary does not need to be. */
type Plotted = readonly [number, number]

function timeScale(fromMs: number, toMs: number, w: number): (ms: number) => number {
  const span = toMs - fromMs || 1
  return (ms: number) => ((ms - fromMs) / span) * w
}

function ProductChart({ range, fills, w = 640, h = 160 }: { range: ProductHistoryRange; fills: readonly Fill[]; w?: number; h?: number }) {
  const parsed = useMemo(() => {
    const starts = range.points.map((p) => (p.at ? new Date(p.at).getTime() : null))
    const knownStarts = starts.filter((v): v is number => v !== null)
    if (knownStarts.length === 0) return null
    const fromMs = Math.min(...knownStarts)
    // Buckets are stamped at the START of their span, so the chart's own right edge is the
    // last bucket's start PLUS its width — otherwise a weekly bucket's whole week reads as
    // one instant and every fill inside it draws past the line's own end.
    const widthMs = (range.width_days ?? 1) * 86_400_000
    const toMs = Math.max(...knownStarts) + widthMs
    const relevant = fills.filter((f) => f.at.getTime() >= fromMs)
    const prices = [
      ...range.points.flatMap((p) => [p.market, p.low, p.high].map((v) => (v === null ? null : Number(v)))),
      ...relevant.map((f) => f.unitPrice),
    ].filter((v): v is number => v !== null && Number.isFinite(v))
    if (prices.length === 0) return null
    const lo = Math.min(...prices)
    const hi = Math.max(...prices)
    const span = hi - lo || 1
    const x = timeScale(fromMs, toMs, w)
    const y = (price: number) => h - ((price - lo) / span) * (h - 8) - 4
    return { fromMs, toMs, x, y, relevant }
  }, [range, fills, w, h])

  if (parsed === null) {
    return <div className="producthistory-chart-empty">No priced buckets in this range.</div>
  }
  const { x, y, relevant } = parsed

  const marketByIndex = range.points.map((p) => (p.market === null ? null : Number(p.market)))
  const runs = sparkSegments(marketByIndex, w, h) // index-spaced runs, re-mapped to time x below
  const marketSegments: Plotted[][] = []
  if (runs !== null) {
    // Re-place each run's points at their bucket's own real time, never the equal-spaced
    // index `sparkSegments` was built for — the break-on-null behaviour is what is reused,
    // not the x axis.
    let cursor = 0
    for (const run of runs) {
      const segment: Plotted[] = []
      for (const [, py] of run) {
        while (cursor < range.points.length && marketByIndex[cursor] === null) cursor += 1
        const at = range.points[cursor]?.at
        if (at) segment.push([x(new Date(at).getTime()), py])
        cursor += 1
      }
      if (segment.length > 1) marketSegments.push(segment)
    }
  }

  return (
    <svg
      className="producthistory-chart"
      viewBox={`0 0 ${w} ${h}`}
      role="img"
      aria-label={`${RANGE_LABEL[range.range] ?? range.range} market buckets, with the owner's own sales marked`}
    >
      {/* THE SPREAD, CARRIED PER BUCKET — a thin vertical tick from low to high, never
          collapsed into one number across the whole series (D62's own rule, restated for a
          per-bucket reading rather than a whole-series bound). */}
      {range.points.map((p, i) => {
        if (p.at === null || p.low === null || p.high === null) return null
        const px = x(new Date(p.at).getTime())
        return (
          <line
            key={`spread-${i}`}
            className="producthistory-spread"
            x1={px} x2={px}
            y1={y(Number(p.low))} y2={y(Number(p.high))}
          />
        )
      })}
      {/* THE MARKET SERIES — an aggregate, drawn as a line, broken at any bucket with no
          price. Never the same mark as a fill below. */}
      {marketSegments.map((segment, i) => (
        <polyline
          key={`market-${i}`}
          className="producthistory-market-line"
          points={segment.map(([px, py]) => `${px.toFixed(1)},${py.toFixed(1)}`).join(' ')}
        />
      ))}
      {/* THE OWNER'S OWN FILLS — exact, one diamond per sale, at its real date and price.
          Never joined to the market line or to each other: D212's grain is the SKU, not an
          order, and each mark is one fact, not a trend. */}
      {relevant.map((f, i) => (
        <path
          key={`fill-${i}`}
          className="producthistory-fill-mark"
          d={diamond(x(f.at.getTime()), y(f.unitPrice), 5)}
        >
          <title>{`${f.at.toLocaleDateString()} — ${f.quantity} sold at ${money(f.unitPrice)}`}</title>
        </path>
      ))}
    </svg>
  )
}

function diamond(cx: number, cy: number, r: number): string {
  return `M${cx} ${cy - r} L${cx + r} ${cy} L${cx} ${cy + r} L${cx - r} ${cy} Z`
}

function RangeSection({ range, fills }: { range: ProductHistoryRange; fills: readonly Fill[] }) {
  const label = RANGE_LABEL[range.range] ?? range.range
  const width = range.width_days
  return (
    <section className="producthistory-range">
      <header className="producthistory-range-head">
        <div className="producthistory-range-title">
          <h3>{label}</h3>
          <span className="producthistory-machine">{range.range}</span>
        </div>
        <span className="producthistory-span">
          {range.from ?? '?'} → {range.to ?? '?'}
          {width !== null ? (
            <span className="producthistory-bucket-width">{`${width}-day bucket${width === 1 ? '' : 's'}, as read today`}</span>
          ) : null}
        </span>
      </header>
      <ProductChart range={range} fills={fills} />
      <p className="producthistory-note">
        Reported precision decays over time for a fixed sale — the same sale sits in a finer
        bucket today than it will in a few months. This range currently reads at{' '}
        {width ?? '?'} day{width === 1 ? '' : 's'} per bucket.
      </p>
    </section>
  )
}

function Legend() {
  return (
    <div className="producthistory-legend">
      <span><span className="producthistory-legend-line" /> Market bucket (aggregate — many transactions this store never saw)</span>
      <span><span className="producthistory-legend-diamond" aria-hidden="true" /> Your sale (exact — one order, one price)</span>
    </div>
  )
}

export function ProductHistory() {
  const [skuInput, setSkuInput] = useState(() => readSkuFromHash())
  const [sku, setSku] = useState(() => readSkuFromHash())
  const [payload, setPayload] = useState<ProductHistoryPayload | null>(null)
  const [orders, setOrders] = useState<OrderRow[] | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const onHash = () => {
      const next = readSkuFromHash()
      setSku(next)
      setSkuInput(next)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    writeSkuToHash(sku)
  }, [sku])

  useEffect(() => {
    let alive = true
    if (sku.trim() === '') {
      setPayload(null)
      setFailure(null)
      return
    }
    setLoading(true)
    setFailure(null)
    Promise.all([getProductHistory(sku.trim()), getOrders()])
      .then(([history, ordersPayload]) => {
        if (!alive) return
        setPayload(history)
        setOrders(ordersPayload.orders)
      })
      .catch((err) => {
        if (!alive) return
        setPayload(null)
        setFailure(describeFailure(err))
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [sku])

  const fills = useMemo(() => (payload && orders ? fillsFor(payload.sku, orders) : []), [payload, orders])

  const { withinHistory, beforeHistory } = useMemo(() => {
    if (payload === null || payload.history_begins === null) {
      return { withinHistory: fills, beforeHistory: [] as Fill[] }
    }
    const cutoff = new Date(payload.history_begins).getTime()
    const within: Fill[] = []
    const before: Fill[] = []
    for (const fill of fills) {
      if (fill.at.getTime() >= cutoff) within.push(fill)
      else before.push(fill)
    }
    return { withinHistory: within, beforeHistory: before }
  }, [fills, payload])

  return (
    <main className="producthistory bn-page">
      <PageHeader
        title="Product history"
        icon="history"
        lede="What one product has been selling for, with your own sales marked on it."
      />

      <form
        className="producthistory-search"
        onSubmit={(event) => {
          event.preventDefault()
          setSku(skuInput.trim())
        }}
      >
        <label htmlFor="producthistory-sku">TCGplayer SKU</label>
        <input
          id="producthistory-sku"
          className="bn-input"
          value={skuInput}
          onChange={(event) => setSkuInput(event.target.value)}
          placeholder="e.g. 555123"
          inputMode="numeric"
        />
        <Button type="submit" icon="search">Look up</Button>
      </form>

      {sku.trim() === '' ? (
        <EmptyState
          icon="search"
          title="Enter a SKU to see its history."
          body="This page is per product, and it never guesses which one you mean."
        />
      ) : loading ? (
        <p className="bn-lede">Reading the archive…</p>
      ) : failure !== null ? (
        <Notice tone="danger" code={failure.code}>{failure.message}</Notice>
      ) : payload === null ? null : (
        <>
          <header className="producthistory-product">
            <h2>{payload.name ?? <span className="bn-mono">{payload.sku}</span>}</h2>
            <div className="producthistory-product-meta">
              {payload.set_name ? <Pill tone="default">{payload.set_name}</Pill> : null}
              {payload.condition ? <Pill tone="default">{payload.condition}</Pill> : null}
              <Pill tone={payload.source === 'archive' ? 'ok' : 'default'}>
                {payload.source === 'archive' ? 'Read from the archive — no host reached' : 'Read live, just now'}
              </Pill>
            </div>
          </header>

          {payload.history_begins !== null ? (
            <p className="producthistory-begins">History on this page begins {payload.history_begins} — nothing older than that is market data.</p>
          ) : null}

          {payload.never_sold ? (
            <Notice tone="info">This product has never been recorded to sell over the ranges read here.</Notice>
          ) : null}

          {payload.ranges.length > 0 ? (
            <>
              <Legend />
              {payload.ranges.map((range) => (
                <RangeSection key={range.range} range={range} fills={withinHistory} />
              ))}
            </>
          ) : null}

          {beforeHistory.length > 0 ? (
            <section className="producthistory-outside">
              <h3>Sales older than this history</h3>
              <p className="producthistory-note">
                No market data exists for these at all — they sold before the archive's own
                start date. Shown for the record, not plotted against anything.
              </p>
              <table className="bn-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Order</th>
                    <th className="num">Copies</th>
                    <th className="num">Unit price</th>
                  </tr>
                </thead>
                <tbody>
                  {beforeHistory.map((f, i) => (
                    <tr key={i}>
                      <td>{f.at.toLocaleDateString()}</td>
                      <td><span className="bn-mono">{f.orderNumber}</span></td>
                      <td className="num">{f.quantity}</td>
                      <td className="num"><span className="bn-money">{money(f.unitPrice)}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ) : null}
        </>
      )}
    </main>
  )
}
