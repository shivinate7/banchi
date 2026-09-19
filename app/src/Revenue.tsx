import { useEffect, useMemo, useState } from 'react'

import { describeFailure, getOrders, type Failure } from './server'
import type { OrderLineWire, OrderRow } from './types'
import { EmptyState, Notice, PageHeader, Segmented } from './kit'
import { money } from './money'
import { sparkSegments } from './PriceHistory'
import { SearchField } from './SearchField'
import './Revenue.css'

/* SALES (`#/revenue`) — the owner's gross-revenue retrospective.
 *
 * TCGplayer's own seller Orders page indexes ORDERS, not line items, so it cannot answer
 * "how much did I make selling <card>". `GET /orders` (`server/capture_server.py:do_orders`)
 * already carries every line's `unit_price` — this screen is a reshaping of that one payload,
 * nothing more. Measured on the owner's live store, 2026-09-19: 804 orders, 1,346 lines, zero
 * missing `unit_price`; $66,334.71 gross over 1,268 lines once Canceled is left out.
 *
 * GROSS ONLY, NEVER PROFIT. There is no cost basis anywhere in this repo, and
 * `server/order_transport.py`'s `project_order` allowlist drops `transaction` and `refunds`
 * at parse — no fee, shipping or refund figure ever reaches this wire. `docs/specs/revenue.md`
 * argues this at length; the word "gross" stays on screen so the figure is never read as
 * profit.
 *
 * CANCELED IS DROPPED SILENTLY — the owner's ruling, 2026-09-19, having been shown the
 * alternative. Not every terminal status: Shipped and Completed are real sales and stay.
 * `store/orders.py:is_terminal_status` is a wider vocabulary that answers a different
 * question ("is this order still open"); this screen asks one narrower word of the feed's
 * own `status` string, the same way `order_key` and `is_terminal_status` themselves fold
 * case and edge whitespace before comparing.
 *
 * NO SEALED/SINGLES SPLIT. `OrderLine.kind` is null on nearly every line because the feed
 * says nothing, and guessing a kind from the product name is what CLAUDE.md and
 * `pipeline/orders.py` both refuse at length. Revenue is in fact dominated by sealed
 * product — the table is one list, sorted by gross, mixed on purpose.
 */

/** The one word this screen treats as "not a sale" — folded the way `is_terminal_status`
 *  folds its own vocabulary, but for exactly one status rather than that whole terminal set. */
function isCanceled(status: string | null): boolean {
  return (status ?? '').trim().toLowerCase() === 'canceled'
}

type Period = '3m' | '6m' | 'ytd' | 'all'

const PERIODS: readonly { readonly value: Period; readonly label: string }[] = [
  { value: '3m', label: '3 months' },
  { value: '6m', label: '6 months' },
  { value: 'ytd', label: 'This year' },
  { value: 'all', label: 'All time' },
]

/** One line, with its order's placed-at date and a real number for `unit_price` — the one
 *  arithmetic step this screen performs, over a string the wire sends because money crosses
 *  it as text (`OrderLineWire`'s own comment). A line with no price or no date cannot be
 *  placed on the sparkline or the verdict and is left out, counted once in `dropped`. */
type Sale = {
  readonly order: string
  readonly at: Date
  readonly name: string
  readonly quantity: number
  readonly gross: number
}

function salesOf(orders: readonly OrderRow[]): { readonly sales: Sale[]; readonly dropped: number } {
  const sales: Sale[] = []
  let dropped = 0
  for (const order of orders) {
    if (isCanceled(order.status)) continue
    if (order.placed_at === null) {
      dropped += order.lines.length
      continue
    }
    const at = new Date(order.placed_at)
    if (Number.isNaN(at.getTime())) {
      dropped += order.lines.length
      continue
    }
    for (const line of order.lines as readonly OrderLineWire[]) {
      const price = line.unit_price === null ? NaN : Number(line.unit_price)
      if (!Number.isFinite(price)) {
        dropped += 1
        continue
      }
      sales.push({
        order: order.key,
        at,
        name: line.name ?? line.sku,
        quantity: line.quantity,
        gross: price * line.quantity,
      })
    }
  }
  return { sales, dropped }
}

/** `YYYY-MM`, in the order placed's own local reading — a month strip counts a person's
 *  months, not UTC's. */
function monthKey(at: Date): string {
  return `${at.getFullYear()}-${String(at.getMonth() + 1).padStart(2, '0')}`
}

function monthLabel(key: string): string {
  const parts = key.split('-').map(Number)
  const year = parts[0] ?? 0
  const month = parts[1] ?? 1
  return new Date(year, month - 1, 1).toLocaleDateString(undefined, { month: 'short', year: 'numeric' })
}

/** The window a period control names, and the equal-length window right before it — the
 *  verdict's own comparison. `null` for `all`'s previous window: there is nothing before
 *  everything, and the verdict says so rather than drawing a manufactured zero. */
function windowsOf(period: Period, latest: Date): { readonly current: Date; readonly previous: Date | null } {
  if (period === 'all') return { current: new Date(0), previous: null }
  if (period === 'ytd') {
    const start = new Date(latest.getFullYear(), 0, 1)
    const previousStart = new Date(latest.getFullYear() - 1, 0, 1)
    return { current: start, previous: previousStart }
  }
  const months = period === '3m' ? 3 : 6
  const current = new Date(latest.getFullYear(), latest.getMonth() - months + 1, 1)
  const previous = new Date(latest.getFullYear(), latest.getMonth() - 2 * months + 1, 1)
  return { current, previous }
}

function sum(sales: readonly Sale[]): number {
  return sales.reduce((total, sale) => total + sale.gross, 0)
}

function orderCount(sales: readonly Sale[]): number {
  return new Set(sales.map((sale) => sale.order)).size
}

/** One line in the verdict's own smaller-type comparison. `null` reads as "no prior period",
 *  never as a silent zero. */
function compareLine(current: number, previous: number | null): string {
  if (previous === null) return 'No earlier period to compare it against yet.'
  if (previous === 0) return `The period before had no gross at all.`
  const change = ((current - previous) / previous) * 100
  const said = change >= 0 ? `up ${change.toFixed(0)}%` : `down ${Math.abs(change).toFixed(0)}%`
  return `The period before this one made ${money(previous)}, ${said}.`
}

function Loading() {
  return (
    <main className="revenue bn-page">
      <PageHeader title="Sales" icon="dollar" lede="Your gross-revenue retrospective." />
      <p className="bn-lede">Reading your orders…</p>
    </main>
  )
}

export function Revenue() {
  const [orders, setOrders] = useState<OrderRow[] | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [period, setPeriod] = useState<Period>('6m')
  const [query, setQuery] = useState('')

  useEffect(() => {
    let alive = true
    getOrders()
      .then((payload) => {
        if (alive) setOrders(payload.orders)
      })
      .catch((err) => {
        if (alive) setFailure(describeFailure(err))
      })
    return () => {
      alive = false
    }
  }, [])

  const { sales, dropped } = useMemo(() => salesOf(orders ?? []), [orders])

  const months = useMemo(() => {
    const by = new Map<string, Sale[]>()
    for (const sale of sales) {
      const key = monthKey(sale.at)
      const list = by.get(key)
      if (list) list.push(sale)
      else by.set(key, [sale])
    }
    return Array.from(by.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, rows]) => ({ key, gross: sum(rows), orders: orderCount(rows) }))
  }, [sales])

  const latest = sales.reduce((max, sale) => (sale.at > max ? sale.at : max), sales[0]?.at ?? new Date())
  const { current: windowStart, previous: previousStart } = windowsOf(period, latest)

  const inPeriod = useMemo(() => sales.filter((sale) => sale.at >= windowStart), [sales, windowStart])
  const inPrevious = useMemo(
    () => (previousStart === null ? null : sales.filter((sale) => sale.at >= previousStart && sale.at < windowStart)),
    [sales, previousStart, windowStart],
  )

  const periodMonths = useMemo(() => months.filter((m) => new Date(`${m.key}-01`) >= windowStart), [months, windowStart])

  const spark = useMemo(
    () => sparkSegments(periodMonths.map((m) => m.gross), 560, 64),
    [periodMonths],
  )

  const products = useMemo(() => {
    const by = new Map<string, { name: string; copies: number; gross: number; last: Date }>()
    for (const sale of inPeriod) {
      const existing = by.get(sale.name)
      if (existing) {
        existing.copies += sale.quantity
        existing.gross += sale.gross
        if (sale.at > existing.last) existing.last = sale.at
      } else {
        by.set(sale.name, { name: sale.name, copies: sale.quantity, gross: sale.gross, last: sale.at })
      }
    }
    const rows = Array.from(by.values())
    const q = query.trim().toLowerCase()
    const filtered = q === '' ? rows : rows.filter((row) => row.name.toLowerCase().includes(q))
    return filtered.sort((a, b) => b.gross - a.gross)
  }, [inPeriod, query])

  if (failure !== null) {
    return (
      <main className="revenue bn-page">
        <PageHeader title="Sales" icon="dollar" lede="Your gross-revenue retrospective." />
        <Notice tone="danger" title="Could not read your orders">
          {failure.message}
        </Notice>
      </main>
    )
  }

  if (orders === null) return <Loading />

  if (sales.length === 0) {
    return (
      <main className="revenue bn-page">
        <PageHeader title="Sales" icon="dollar" lede="Your gross-revenue retrospective." />
        <EmptyState
          icon="dollar"
          title="Nothing has sold yet."
          body="Once an order comes in with a price on it, this screen adds it up by month and by name — the search TCGplayer's own Orders page will not do for you."
        />
      </main>
    )
  }

  const total = sum(inPeriod)
  const previousTotal = inPrevious === null ? null : sum(inPrevious)
  const periodLabel = PERIODS.find((p) => p.value === period)?.label ?? period

  return (
    <main className="revenue bn-page">
      <PageHeader
        title="Sales"
        icon="dollar"
        lede="Your gross-revenue retrospective — what sold, for how much, by name. Gross only: no fees, no cost, no profit."
        actions={<Segmented label="Period" value={period} options={PERIODS} onChange={setPeriod} />}
      />

      <section className="revenue-verdict">
        <p className="revenue-verdict-said">
          {`You grossed ${money(total)} over ${periodLabel.toLowerCase()}, across ${orderCount(inPeriod).toLocaleString()} ${orderCount(inPeriod) === 1 ? 'order' : 'orders'}.`}
        </p>
        <p className="revenue-verdict-prior">{compareLine(total, previousTotal)}</p>
        {dropped === 0 ? null : (
          <p className="revenue-verdict-dropped">
            {`${dropped.toLocaleString()} ${dropped === 1 ? 'line has' : 'lines have'} no usable price or date and ${dropped === 1 ? 'is' : 'are'} left out of every figure here.`}
          </p>
        )}
      </section>

      <section className="revenue-months">
        <h2 className="bn-label">By month</h2>
        {spark === null ? null : (
          <svg
            className="revenue-spark"
            viewBox="0 0 560 64"
            preserveAspectRatio="none"
            aria-hidden="true"
            focusable="false"
          >
            {spark.map((segment, at) => (
              <polyline key={at} points={segment.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ')} />
            ))}
          </svg>
        )}
        <div className="revenue-month-rows">
          {periodMonths
            .slice()
            .reverse()
            .map((m) => (
              <div className="revenue-month-row" key={m.key} data-current={m.key === monthKey(latest)}>
                <span className="revenue-month-name">{monthLabel(m.key)}</span>
                <span className="bn-money">{money(m.gross)}</span>
                <span className="revenue-month-orders">{`${m.orders.toLocaleString()} ${m.orders === 1 ? 'order' : 'orders'}`}</span>
              </div>
            ))}
        </div>
      </section>

      <section className="revenue-products">
        <div className="revenue-products-head">
          <h2 className="bn-label">By product</h2>
          <div className="revenue-search">
            <SearchField value={query} onChange={setQuery} persona="owner" placeholder="Find what you sold" />
          </div>
        </div>
        {products.length === 0 ? (
          <EmptyState icon="search" title="Nothing sold under that name in this period." />
        ) : (
          <table className="bn-table revenue-table">
            <thead>
              <tr>
                <th>Name</th>
                <th className="num">Copies</th>
                <th className="num">Gross</th>
                <th>Last sold</th>
              </tr>
            </thead>
            <tbody>
              {products.map((row) => (
                <tr key={row.name}>
                  <td>{row.name}</td>
                  <td className="num">{row.copies.toLocaleString()}</td>
                  <td className="num"><span className="bn-money">{money(row.gross)}</span></td>
                  <td>{row.last.toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </main>
  )
}
