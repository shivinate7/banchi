import { Fragment, useEffect, useId, useMemo, useState, type CSSProperties } from 'react'

import { describeFailure, getOrders, getSoldPrices, type Failure, type SoldPricesLookup } from './server'
import type { OrderLineWire, OrderRow } from './types'
import { Button, EmptyState, Icon, Notice, PageHeader, Pill, Segmented } from './kit'
import { money, moneyGrouped } from './money'
import { sparkSegments } from './PriceHistory'
import { SearchField } from './SearchField'
import { ReadingAge } from './CardLocations'
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
 * product — the table is one list, sorted by gross, mixed on purpose. NONE OF THE ABOVE
 * CHANGED (D214's counting rules stand): what is new is what a person can do with the same
 * rows once they are on screen — sort them, filter them, cross-filter by month, drill into
 * one product's own orders, and share the exact view as a link. See D217.
 */

/** The one word this screen treats as "not a sale" — folded the way `is_terminal_status`
 *  folds its own vocabulary, but for exactly one status rather than that whole terminal set. */
function isCanceled(status: string | null): boolean {
  return (status ?? '').trim().toLowerCase() === 'canceled'
}

type Period = '3m' | '6m' | 'ytd' | 'all' | 'custom'

const PERIODS: readonly { readonly value: Period; readonly label: string }[] = [
  { value: '3m', label: '3 months' },
  { value: '6m', label: '6 months' },
  { value: 'ytd', label: 'This year' },
  { value: 'all', label: 'All time' },
  { value: 'custom', label: 'Custom' },
]

type SortKey = 'name' | 'copies' | 'gross' | 'last'
type SortDir = 'asc' | 'desc'

/** The first click on a column shows what a reader wants first — biggest gross, most
 *  copies, most recent sale, or the name from the top. Every later click on the same
 *  column just flips it. */
const DEFAULT_DIR: Record<SortKey, SortDir> = { name: 'asc', copies: 'desc', gross: 'desc', last: 'desc' }
const SORT_LABEL: Record<SortKey, string> = { name: 'Name', copies: 'Copies', gross: 'Gross', last: 'Last sold' }
const SORT_KEYS: readonly SortKey[] = ['name', 'copies', 'gross', 'last']

type Granularity = 'week' | 'month'

/** Below this many days in the selected window, a monthly bar chart draws one or two bars —
 *  too coarse to read as a trend. Above it, a weekly strip would draw dozens. Chosen, not
 *  measured: roughly two months is where a week-wide bar stops being the more legible one. */
const GRANULARITY_THRESHOLD_DAYS = 60

/** One line, with its order's placed-at date and a real number for `unit_price` — the one
 *  arithmetic step this screen performs, over a string the wire sends because money crosses
 *  it as text (`OrderLineWire`'s own comment). A line with no price or no date cannot be
 *  placed on the sparkline or the verdict and is left out, counted once in `dropped`. */
type Sale = {
  /** The order's identity (`OrderRow.key`) — never shown, only counted and grouped by. */
  readonly order: string
  /** The order's label (`OrderRow.number`) — what the drill-down shows a person. */
  readonly orderNumber: string
  readonly at: Date
  readonly name: string
  /** True where `name` fell back to the line's own SKU because the feed sent no name —
   *  the fact `nameIsSku` at the render site draws in mono rather than guessing from the
   *  string's own shape. */
  readonly nameIsSku: boolean
  /** The line's own SKU — never shown here, only used to ask `getSoldPrices` what this exact
   *  name is worth today (D225). */
  readonly sku: string
  readonly quantity: number
  readonly unitPrice: number
  readonly gross: number
}

/** `true` where the OPERATOR closed this line as never shipping — a refund or a
 *  cancellation, `store/orders.py:174`'s own words for `not_shipping` — during fulfilment,
 *  matched by SKU against the same order's `OrderLineProgress` list (D225,
 *  `docs/specs/revenue-plan.md` §2). `closed_reason` rides on every order's `progress`
 *  already; this screen was simply never reading it. NOT THE MARKETPLACE'S WORD: the value
 *  is recorded by a person during fulfilment, so a line can be a real refund the operator
 *  never got around to closing, and this can only ever undercount, never overcount. */
function isClosedNotShipping(order: OrderRow, sku: string): boolean {
  return order.progress.some((p) => p.sku === sku && p.closed_reason === 'not_shipping')
}

function salesOf(
  orders: readonly OrderRow[],
): {
  readonly sales: Sale[]
  readonly dropped: number
  readonly refundExcluded: number
  readonly canceledOrders: number
} {
  const sales: Sale[] = []
  let dropped = 0
  let refundExcluded = 0
  let canceledOrders = 0
  for (const order of orders) {
    if (isCanceled(order.status)) {
      canceledOrders += 1
      continue
    }
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
      if (isClosedNotShipping(order, line.sku)) {
        refundExcluded += 1
        continue
      }
      const price = line.unit_price === null ? NaN : Number(line.unit_price)
      if (!Number.isFinite(price)) {
        dropped += 1
        continue
      }
      sales.push({
        order: order.key,
        orderNumber: order.number,
        at,
        name: line.name ?? line.sku,
        nameIsSku: line.name === null,
        sku: line.sku,
        quantity: line.quantity,
        unitPrice: price,
        gross: price * line.quantity,
      })
    }
  }
  return { sales, dropped, refundExcluded, canceledOrders }
}

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

/** `YYYY-MM-DD` in local time — the one shape both `<input type="date">` and this screen's
 *  own URL state use, so a value round-trips through either without a timezone shift. */
function isoDate(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

/** `null` for anything that is not exactly that shape — a malformed or hand-edited URL reads
 *  as "no date" rather than as a wrong one. */
function parseIsoDate(s: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
  if (m === null) return null
  const [, y, mo, d] = m
  const at = new Date(Number(y), Number(mo) - 1, Number(d))
  return Number.isNaN(at.getTime()) ? null : at
}

function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate())
}

/** The moment right after the given day ends — an EXCLUSIVE upper bound, so a sale placed at
 *  any time on the last day of a range is still counted. */
function dayAfter(d: Date): Date {
  const next = startOfDay(d)
  next.setDate(next.getDate() + 1)
  return next
}

function monthKey(at: Date): string {
  return `${at.getFullYear()}-${pad2(at.getMonth() + 1)}`
}

function monthLabel(key: string): string {
  const parts = key.split('-').map(Number)
  const year = parts[0] ?? 0
  const month = parts[1] ?? 1
  return new Date(year, month - 1, 1).toLocaleDateString(undefined, { month: 'short', year: 'numeric' })
}

/** Monday-start, matching the physical convention this repo already keeps for a week
 *  elsewhere in the store rather than inventing a Sunday-start one here. */
function weekStart(d: Date): Date {
  const day = d.getDay()
  const diff = day === 0 ? -6 : 1 - day
  const s = startOfDay(d)
  s.setDate(s.getDate() + diff)
  return s
}

function weekLabel(start: Date, end: Date): string {
  const last = new Date(end)
  last.setDate(last.getDate() - 1)
  const sameMonth = start.getMonth() === last.getMonth() && start.getFullYear() === last.getFullYear()
  const startStr = start.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  const lastStr = sameMonth
    ? String(last.getDate())
    : last.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  return `${startStr}–${lastStr}`
}

function formatShort(iso: string): string {
  const d = parseIsoDate(iso)
  return d === null ? iso : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function sum(sales: readonly Sale[]): number {
  return sales.reduce((total, sale) => total + sale.gross, 0)
}

function orderCount(sales: readonly Sale[]): number {
  return new Set(sales.map((sale) => sale.order)).size
}

/** The selected window's start and NOMINAL end (the calendar boundary the period names, even
 *  when that boundary has not arrived yet — "this year" nominally ends December 31st on day
 *  19 of September just as honestly as it does on day 364), plus the equal-length window
 *  right before it to compare against. `previousStart` is `null` only for `all`: there is
 *  nothing before everything. Anchored on `now` (the real clock), never on the latest sale —
 *  a store that sold nothing this week still has a "this month" that is genuinely in
 *  progress today. */
function windowsOf(
  period: Period,
  now: Date,
  custom: { readonly from: string | null; readonly to: string | null },
): { readonly start: Date; readonly nominalEnd: Date; readonly previousStart: Date | null } {
  if (period === 'custom') {
    const from = custom.from !== null ? parseIsoDate(custom.from) : null
    const to = custom.to !== null ? parseIsoDate(custom.to) : null
    const start = from ?? startOfDay(now)
    const nominalEnd = to !== null ? dayAfter(to) : now
    const span = Math.max(0, nominalEnd.getTime() - start.getTime())
    return { start, nominalEnd, previousStart: new Date(start.getTime() - span) }
  }
  if (period === 'all') return { start: new Date(0), nominalEnd: now, previousStart: null }
  if (period === 'ytd') {
    return {
      start: new Date(now.getFullYear(), 0, 1),
      nominalEnd: new Date(now.getFullYear() + 1, 0, 1),
      previousStart: new Date(now.getFullYear() - 1, 0, 1),
    }
  }
  const months = period === '3m' ? 3 : 6
  return {
    start: new Date(now.getFullYear(), now.getMonth() - months + 1, 1),
    nominalEnd: new Date(now.getFullYear(), now.getMonth() + 1, 1),
    previousStart: new Date(now.getFullYear(), now.getMonth() - 2 * months + 1, 1),
  }
}

/** One line in the verdict's own smaller-type comparison. `previousRows === null` reads as
 *  "no prior period at all" (the `all time` control has nothing before it) — a different
 *  fact from `previousRows` being empty, which is "the store has no ORDERS recorded that far
 *  back". `likeForLike` names a window this function did not choose: the caller has already
 *  cut the prior period down to the SAME number of elapsed days the current one has had, so
 *  the wording says so rather than letting a shorter slice masquerade as the whole thing. */
function compareLine(current: number, previousRows: readonly Sale[] | null, likeForLike: boolean): string {
  if (previousRows === null) return 'No earlier period to compare it against yet.'
  if (previousRows.length === 0) {
    return likeForLike
      ? 'So far, nothing is recorded for the period before this one.'
      : 'Nothing is recorded for the period before this one.'
  }
  const previous = sum(previousRows)
  // `likeForLike` means THIS window is still forming, not the PRIOR one — the prior window is
  // a closed stretch cut down to the same elapsed length for a fair comparison, and "so far"
  // belongs to the one that has not finished, never to the one already over (defect fix).
  const lead = likeForLike
    ? 'Over the same stretch, the period before this one made'
    : 'The period before this one made'
  // A REAL DIVIDE-BY-ZERO GUARD: rows exist and still sum to exactly $0.00 — free lines are
  // real and are not filtered out. A percentage has no base to divide by here, so this says
  // the dollar amount plainly instead of rendering `Infinity%` or `NaN%`.
  if (previous === 0) {
    if (current === 0) return `${lead} ${moneyGrouped(0)} too.`
    return `${lead} ${moneyGrouped(0)}; this one has already made ${moneyGrouped(current)} more.`
  }
  const change = ((current - previous) / previous) * 100
  const said = change >= 0 ? `up ${change.toFixed(0)}%` : `down ${Math.abs(change).toFixed(0)}%`
  return `${lead} ${moneyGrouped(previous)}, ${said}.`
}

type Bucket = {
  readonly key: string
  readonly label: string
  readonly start: Date
  readonly end: Date
  readonly gross: number
  readonly orders: number
  /** `now` falls inside `[start, end)` — the one bucket a naive read would mistake for a
   *  collapse rather than for "not over yet". */
  readonly inProgress: boolean
}

/** The bucket key, its own start/end, and its label — one shape both grains share, computed
 *  once per date rather than duplicated at every call site. */
function bucketRangeOf(at: Date, granularity: Granularity): { readonly key: string; readonly start: Date; readonly end: Date; readonly label: string } {
  if (granularity === 'month') {
    const start = new Date(at.getFullYear(), at.getMonth(), 1)
    const end = new Date(at.getFullYear(), at.getMonth() + 1, 1)
    return { key: monthKey(at), start, end, label: monthLabel(monthKey(at)) }
  }
  const start = weekStart(at)
  const end = dayAfter(new Date(start.getTime() + 6 * 86_400_000))
  return { key: isoDate(start), start, end, label: weekLabel(start, end) }
}

/** ONLY THE BUCKETS THAT HAVE A SALE, same as the screen this replaces always drew — a
 *  historical month with nothing in it was never on the strip before this change and is not
 *  now either (D194's own cost of drawing one, measured: `copy-budget.spec.ts`'s populated
 *  fixture alone adds four empty rows across an otherwise one-sale window). The one bucket
 *  forced onto the strip even when it is empty is the CURRENT one, and only when the
 *  selection actually reaches `now` (`forceNow`, `null` for a closed custom range that ended
 *  before today) — a month with no sale yet still has to be ON the strip to be marked in
 *  progress rather than simply missing. */
function buildBuckets(sales: readonly Sale[], granularity: Granularity, forceNow: Date | null): Bucket[] {
  const by = new Map<string, { start: Date; end: Date; label: string; gross: number; orders: Set<string> }>()
  for (const sale of sales) {
    const { key, start, end, label } = bucketRangeOf(sale.at, granularity)
    const existing = by.get(key)
    if (existing) {
      existing.gross += sale.gross
      existing.orders.add(sale.order)
    } else {
      by.set(key, { start, end, label, gross: sale.gross, orders: new Set([sale.order]) })
    }
  }
  if (forceNow !== null) {
    const { key, start, end, label } = bucketRangeOf(forceNow, granularity)
    if (!by.has(key)) by.set(key, { start, end, label, gross: 0, orders: new Set() })
  }
  return Array.from(by.entries())
    .sort(([, a], [, b]) => a.start.getTime() - b.start.getTime())
    .map(([key, b]) => ({
      key,
      label: b.label,
      start: b.start,
      end: b.end,
      gross: b.gross,
      orders: b.orders.size,
      inProgress: forceNow !== null && forceNow >= b.start && forceNow < b.end,
    }))
}

type Product = {
  readonly name: string
  readonly nameIsSku: boolean
  readonly copies: number
  readonly gross: number
  readonly last: Date
  /** The SKU and unit price of the MOST RECENT sale under this name — what `getSoldPrices` is
   *  asked about, and the "then" half of "then against now" (D225). Two SKUs can
   *  share a display name (a reprint, a different printing the feed named the same); this
   *  is deliberately the latest one sold, not an average across them. */
  readonly lastSku: string
  readonly lastPrice: number
}

/** "Then against now" for one already-sold name (D225) — a market observation and
 *  NEVER a profit or a loss, D62's rule for this exact shape ("direction is a sign and a
 *  word, never a color"). `word` is never rendered as a color anywhere this is used. */
type MarketCompare = { readonly market: number; readonly at: number; readonly diff: number; readonly word: 'above' | 'below' | 'even with' }

/** `null` for a SKU `prices` was never asked about or never has an entry for — NEVER
 *  drawn as a zero (D189's own rule, restated for this screen: "a name with no reading
 *  shows no figure"). `prices[row.lastSku]` is a lookup against the LAST sale's own SKU
 *  (`Product.lastSku`), not an average across every SKU this name has ever sold under. */
function marketCompareOf(row: Product, prices: SoldPricesLookup): MarketCompare | null {
  const entry = prices[row.lastSku]
  if (entry === undefined) return null
  const market = Number(entry.market)
  if (!Number.isFinite(market)) return null
  const diff = market - row.lastPrice
  const word = diff > 0 ? 'above' : diff < 0 ? 'below' : 'even with'
  return { market, at: entry.at, diff, word }
}

function compareProducts(a: Product, b: Product, key: SortKey): number {
  if (key === 'name') return a.name.localeCompare(b.name)
  if (key === 'copies') return a.copies - b.copies
  if (key === 'last') return a.last.getTime() - b.last.getTime()
  return a.gross - b.gross
}

/* ---------------------------------------------------------------------- URL state (D201) */

/** THE URL IS THE ONE COPY. Every reader below is shape-checked the way `pricingSource.ts`'s
 *  `bandInHash`/`markdownInHash` already are: a value this screen did not mint reads as
 *  "unset" rather than as itself, so a hand-edited or stale link degrades to a default
 *  instead of drawing something this screen never produced. */
function revenueQuery(): URLSearchParams {
  return new URLSearchParams(window.location.hash.split('?')[1] ?? '')
}

type UrlState = {
  readonly period: Period
  readonly q: string
  readonly sort: SortKey
  readonly dir: SortDir
  readonly bucket: string | null
  readonly from: string | null
  readonly to: string | null
}

const URL_DEFAULT: UrlState = { period: '6m', q: '', sort: 'gross', dir: 'desc', bucket: null, from: null, to: null }

function readUrlState(): UrlState {
  const params = revenueQuery()
  const periodRaw = params.get('period') ?? ''
  const period = PERIODS.some((p) => p.value === periodRaw) ? (periodRaw as Period) : URL_DEFAULT.period
  const sortRaw = params.get('sort') ?? ''
  const sort = (SORT_KEYS as readonly string[]).includes(sortRaw) ? (sortRaw as SortKey) : URL_DEFAULT.sort
  const dirRaw = params.get('dir')
  const dir: SortDir = dirRaw === 'asc' ? 'asc' : dirRaw === 'desc' ? 'desc' : URL_DEFAULT.dir
  const bucketRaw = params.get('month')
  const dateRe = /^\d{4}-\d{2}-\d{2}$/
  const fromRaw = params.get('from')
  const toRaw = params.get('to')
  return {
    period,
    q: params.get('q') ?? '',
    sort,
    dir,
    bucket: bucketRaw !== null && bucketRaw !== '' ? bucketRaw : null,
    from: fromRaw !== null && dateRe.test(fromRaw) ? fromRaw : null,
    to: toRaw !== null && dateRe.test(toRaw) ? toRaw : null,
  }
}

/** WRITES BY REPLACING, NEVER BY PUSHING. Every other lens in this app (`Pricing.tsx`'s
 *  `?band=`/`?markdown=`) is a discrete click and a real `location.hash =` assignment reads
 *  fine as one back-button step for those. This screen's search field is not discrete — it
 *  fires on every keystroke — so pushing a history entry per letter would turn Back into
 *  something that undoes one keystroke at a time. `replaceState` keeps the URL always
 *  accurate (deep-linkable, and a reload lands on the same view) without touching the
 *  back-button stack at all, for every control here, sort and month included, so one control
 *  does not behave differently from its neighbours. It never changes the PATH, so App.tsx's
 *  own query-stripped `key={path}` never remounts this screen or resets its scroll (D201). */
function writeUrlState(state: UrlState): void {
  const params = new URLSearchParams()
  if (state.period !== URL_DEFAULT.period) params.set('period', state.period)
  if (state.q !== '') params.set('q', state.q)
  if (state.sort !== URL_DEFAULT.sort || state.dir !== URL_DEFAULT.dir) {
    params.set('sort', state.sort)
    params.set('dir', state.dir)
  }
  if (state.bucket !== null) params.set('month', state.bucket)
  if (state.period === 'custom') {
    if (state.from !== null) params.set('from', state.from)
    if (state.to !== null) params.set('to', state.to)
  }
  const qs = params.toString()
  const next = qs === '' ? '#/revenue' : `#/revenue?${qs}`
  if (window.location.hash !== next) window.history.replaceState(null, '', next)
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

  const [period, setPeriod] = useState<Period>(() => readUrlState().period)
  const [query, setQuery] = useState(() => readUrlState().q)
  const [sortKey, setSortKey] = useState<SortKey>(() => readUrlState().sort)
  const [sortDir, setSortDir] = useState<SortDir>(() => readUrlState().dir)
  const [activeBucket, setActiveBucket] = useState<string | null>(() => readUrlState().bucket)
  const [customFrom, setCustomFrom] = useState<string | null>(() => readUrlState().from)
  const [customTo, setCustomTo] = useState<string | null>(() => readUrlState().to)
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(() => new Set())

  const fromId = useId()
  const toId = useId()

  // Snapshot once — this is a retrospective, not a ticking clock, and a stable `now` keeps
  // every derived value below from recomputing on its own timer.
  const [now] = useState(() => new Date())

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

  // THE WRITER. Fires after every state change above and after mount; on mount it composes
  // the exact string the URL already has, so the `!==` guard inside `writeUrlState` makes it
  // a no-op rather than a redundant replace.
  useEffect(() => {
    writeUrlState({ period, q: query, sort: sortKey, dir: sortDir, bucket: activeBucket, from: customFrom, to: customTo })
  }, [period, query, sortKey, sortDir, activeBucket, customFrom, customTo])

  // THE READER. Back/forward and a pasted link while already on this screen both fire
  // `hashchange` — `replaceState` above never does, so this cannot see its own writes.
  useEffect(() => {
    const onHash = () => {
      const next = readUrlState()
      setPeriod(next.period)
      setQuery(next.q)
      setSortKey(next.sort)
      setSortDir(next.dir)
      setActiveBucket(next.bucket)
      setCustomFrom(next.from)
      setCustomTo(next.to)
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  // A month picked under one range answers nothing about a different one. This skips its own
  // first run so a deep link (`?period=6m&month=2026-08`) is not cleared the instant it loads.
  const [skipFirst, setSkipFirst] = useState(true)
  useEffect(() => {
    if (skipFirst) {
      setSkipFirst(false)
      return
    }
    setActiveBucket(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period, customFrom, customTo])

  const { sales, dropped, refundExcluded, canceledOrders } = useMemo(() => salesOf(orders ?? []), [orders])

  // THE PRESS, NEVER THE MOUNT (D225, over D189's/D219's own
  // tables). `prices` is `null` until pressed once — a screen that fetched it on mount would
  // draw a number that looks live off a table that is really a cache of the last archive
  // sweep, `readings adopt`, or live fetch. `pricesLoading` and `pricesFailure` describe that
  // one press.
  const [prices, setPrices] = useState<SoldPricesLookup | null>(null)
  const [pricesLoading, setPricesLoading] = useState(false)
  const [pricesFailure, setPricesFailure] = useState<string | null>(null)

  const { start: windowStart, nominalEnd, previousStart } = useMemo(
    () => windowsOf(period, now, { from: customFrom, to: customTo }),
    [period, now, customFrom, customTo],
  )

  const elapsedEnd = nominalEnd.getTime() < now.getTime() ? nominalEnd : now
  // `partial`: the NOMINAL window (a full calendar year, the current month) has not actually
  // finished yet — this is what compareLine truncates the prior window against.
  const partial = elapsedEnd.getTime() < nominalEnd.getTime()
  // `nowInScope`: the SELECTION reaches all the way to today, so its current bucket may be
  // empty and still belongs on the strip. True for every preset and for `all time` (both are
  // always open-ended at `now`); false for a closed custom range whose `to` is in the past.
  const nowInScope = elapsedEnd.getTime() === now.getTime()
  const elapsedMs = Math.max(0, elapsedEnd.getTime() - windowStart.getTime())

  const inPeriod = useMemo(
    () => sales.filter((sale) => sale.at >= windowStart && sale.at < elapsedEnd),
    [sales, windowStart, elapsedEnd],
  )
  const inPrevious = useMemo(() => {
    if (previousStart === null) return null
    const end = new Date(previousStart.getTime() + elapsedMs)
    return sales.filter((sale) => sale.at >= previousStart && sale.at < end)
  }, [sales, previousStart, elapsedMs])

  const spanDays = (nominalEnd.getTime() - windowStart.getTime()) / 86_400_000
  const granularity: Granularity = spanDays <= GRANULARITY_THRESHOLD_DAYS ? 'week' : 'month'

  const buckets = useMemo(
    () => buildBuckets(inPeriod, granularity, nowInScope ? now : null),
    [inPeriod, granularity, nowInScope, now],
  )

  const spark = useMemo(() => sparkSegments(buckets.map((b) => b.gross), 560, 64), [buckets])

  const activeRange = activeBucket === null ? null : buckets.find((b) => b.key === activeBucket) ?? null
  const scopeSales = activeRange === null ? inPeriod : inPeriod.filter((s) => s.at >= activeRange.start && s.at < activeRange.end)

  const products = useMemo(() => {
    const by = new Map<string, Product>()
    for (const sale of scopeSales) {
      const existing = by.get(sale.name)
      if (existing) {
        const newer = sale.at > existing.last
        by.set(sale.name, {
          ...existing,
          copies: existing.copies + sale.quantity,
          gross: existing.gross + sale.gross,
          last: newer ? sale.at : existing.last,
          lastSku: newer ? sale.sku : existing.lastSku,
          lastPrice: newer ? sale.unitPrice : existing.lastPrice,
        })
      } else {
        by.set(sale.name, {
          name: sale.name,
          nameIsSku: sale.nameIsSku,
          copies: sale.quantity,
          gross: sale.gross,
          last: sale.at,
          lastSku: sale.sku,
          lastPrice: sale.unitPrice,
        })
      }
    }
    const rows = Array.from(by.values())
    const q = query.trim().toLowerCase()
    const filtered = q === '' ? rows : rows.filter((row) => row.name.toLowerCase().includes(q))
    return filtered.slice().sort((a, b) => {
      const base = compareProducts(a, b, sortKey)
      return sortDir === 'asc' ? base : -base
    })
  }, [scopeSales, query, sortKey, sortDir])

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir(DEFAULT_DIR[key])
    }
  }

  const handlePeriod = (next: Period) => {
    setPeriod(next)
    if (next === 'custom') {
      setCustomFrom((prev) => prev ?? isoDate(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 30)))
      setCustomTo((prev) => prev ?? isoDate(now))
    }
  }

  const toggleExpanded = (name: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  /** THE PRESS. Asks only about the names on screen right now — a filtered or bucket-narrowed
   *  view presses a smaller list, and merging the answer onto whatever `prices` already
   *  held (rather than replacing it) means widening the filter back out does not blank a name
   *  this press already answered. */
  const refreshReadings = () => {
    const skus = Array.from(new Set(products.map((p) => p.lastSku)))
    if (skus.length === 0) return
    setPricesLoading(true)
    setPricesFailure(null)
    getSoldPrices(skus)
      .then((found) => setPrices((prev) => ({ ...(prev ?? {}), ...found })))
      .catch((err) => setPricesFailure(describeFailure(err).message))
      .finally(() => setPricesLoading(false))
  }

  const noReading = useMemo(() => {
    if (prices === null) return 0
    return products.filter((p) => prices[p.lastSku] === undefined).length
  }, [products, prices])

  const earliestSale = useMemo(
    () => sales.reduce((min: Date | null, s) => (min === null || s.at < min ? s.at : min), null),
    [sales],
  )

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
  const periodLabel = PERIODS.find((p) => p.value === period)?.label ?? period
  const periodPhrase =
    period === 'custom'
      ? customFrom !== null && customTo !== null
        ? `from ${formatShort(customFrom)} to ${formatShort(customTo)}`
        : 'over the selected range'
      : `over ${periodLabel.toLowerCase()}`
  const rangeInvalid = customFrom !== null && customTo !== null && customFrom > customTo
  const activeBucketLabel = activeRange?.label ?? null

  return (
    <main className="revenue bn-page">
      <PageHeader
        title="Sales"
        icon="dollar"
        lede="Your gross-revenue retrospective — what sold, for how much, by name. Gross only: no fees, no cost, no profit."
        actions={
          <div className="revenue-period">
            <Segmented label="Period" value={period} options={PERIODS} onChange={handlePeriod} />
            {period === 'custom' ? (
              <div className="revenue-range">
                <div className="bn-field">
                  <label className="bn-field-label" htmlFor={fromId}>
                    From
                  </label>
                  <input
                    className="bn-input"
                    id={fromId}
                    type="date"
                    value={customFrom ?? ''}
                    max={customTo ?? isoDate(now)}
                    min={earliestSale !== null ? isoDate(earliestSale) : undefined}
                    onChange={(event) => setCustomFrom(event.target.value === '' ? null : event.target.value)}
                  />
                </div>
                <div className="bn-field">
                  <label className="bn-field-label" htmlFor={toId}>
                    To
                  </label>
                  <input
                    className="bn-input"
                    id={toId}
                    type="date"
                    value={customTo ?? ''}
                    min={customFrom ?? undefined}
                    max={isoDate(now)}
                    onChange={(event) => setCustomTo(event.target.value === '' ? null : event.target.value)}
                  />
                </div>
                {rangeInvalid ? <p className="bn-field-hint">Pick an end on or after the start.</p> : null}
              </div>
            ) : null}
          </div>
        }
      />

      <section className="revenue-verdict">
        <p className="revenue-verdict-said">
          {'You grossed '}
          <strong>{moneyGrouped(total)}</strong>
          {` ${periodPhrase}, across ${orderCount(inPeriod).toLocaleString()} ${orderCount(inPeriod) === 1 ? 'order' : 'orders'}.`}
        </p>
        <p className="revenue-verdict-prior">{compareLine(total, inPrevious, partial)}</p>
        {dropped === 0 ? null : (
          <p className="revenue-verdict-dropped">
            {`${dropped.toLocaleString()} ${dropped === 1 ? 'line has' : 'lines have'} no usable price or date and ${dropped === 1 ? 'is' : 'are'} left out of every figure here.`}
          </p>
        )}
        {/* TWO SEPARATE EXCLUSIONS, TWO SEPARATE SENTENCES, EACH STATED EVEN AT ZERO
            (D225). Measured on the owner's real store: 56 Canceled orders
            ($3,059.07) and, as of this build, ZERO lines marked `not_shipping` — this
            screen never claims the second mechanism has caught anything until it counts
            one. Collapsing the two into one sentence, or hiding either at zero, would say
            more than this store actually knows. */}
        <p className="revenue-verdict-canceled">
          {`${canceledOrders.toLocaleString()} ${canceledOrders === 1 ? 'order was' : 'orders were'} canceled by the marketplace and left out.`}
        </p>
        <p className="revenue-verdict-refunded">
          {`${refundExcluded.toLocaleString()} ${refundExcluded === 1 ? 'line was' : 'lines were'} marked refunded or canceled during fulfilment and left out — your own note, not TCGplayer's, so treat it as a habit rather than a guarantee.`}
        </p>
      </section>

      <section className="revenue-months">
        <h2 className="bn-label">{granularity === 'week' ? 'By week' : 'By month'}</h2>
        {spark === null ? null : (
          <>
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
            {/* THE AXIS, NAMED RATHER THAN LEFT TO GUESSING. Oldest-left is the direction a
                reader already expects of a line chart, but the row list right below runs the
                other way on purpose (a retrospective reads "what happened lately" first) --
                so the two ends are said in words, not just drawn. */}
            {buckets.length > 0 ? (
              <div className="revenue-spark-axis" aria-hidden="true">
                <span>{buckets[0]!.label}</span>
                <span>{buckets[buckets.length - 1]!.label}</span>
              </div>
            ) : null}
          </>
        )}
        <div
          className="revenue-month-rows bn-stagger"
          role="group"
          aria-label={granularity === 'week' ? 'Filter by week' : 'Filter by month'}
        >
          {buckets
            .slice()
            .reverse()
            .map((b, i) => (
              <button
                type="button"
                className="revenue-month-row"
                key={b.key}
                data-current={b.inProgress}
                aria-pressed={activeBucket === b.key}
                style={{ '--i': i } as CSSProperties}
                onClick={() => setActiveBucket((cur) => (cur === b.key ? null : b.key))}
              >
                <span className="revenue-month-name">
                  {b.label}
                  {b.inProgress ? (
                    <Pill size="sm" tone="accent">
                      ongoing
                    </Pill>
                  ) : null}
                </span>
                <span className="bn-money">{moneyGrouped(b.gross)}</span>
                <span className="revenue-month-orders">{`${b.orders.toLocaleString()} ${b.orders === 1 ? 'order' : 'orders'}`}</span>
              </button>
            ))}
        </div>
      </section>

      <section className="revenue-products">
        <div className="revenue-products-head">
          <h2 className="bn-label">By product</h2>
          {activeBucketLabel !== null ? (
            <div className="revenue-active-filter">
              <Pill tone="accent">{`${activeBucketLabel} only`}</Pill>
              <Button variant="ghost" size="sm" icon="x" onClick={() => setActiveBucket(null)}>
                Clear
              </Button>
            </div>
          ) : null}
          <div className="revenue-search">
            <SearchField value={query} onChange={setQuery} persona="owner" placeholder="Find what you sold" />
          </div>
        </div>

        {/* THEN AGAINST NOW (D225). A press, never a mount — see `getSoldPrices`'s
            own header. `noReading` counts by NAME on screen right now, so widening the
            filter can only ever raise it, never silently shrink what it claims to cover. */}
        <div className="revenue-market-refresh">
          <Button
            variant="ghost"
            size="sm"
            icon="refresh"
            onClick={refreshReadings}
            disabled={pricesLoading || products.length === 0}
          >
            {pricesLoading ? 'Reading…' : "Compare to today's market"}
          </Button>
          {prices === null ? null : (
            <p className="revenue-market-note">
              {`Blind to what any of this cost you. ${products.length - noReading} of ${products.length} names have a price today, ${noReading} do not.`}
            </p>
          )}
        </div>
        {pricesFailure === null ? null : (
          <Notice tone="danger" title="Could not read today's prices">
            {pricesFailure}
          </Notice>
        )}

        {products.length === 0 ? (
          <EmptyState icon="search" title="Nothing sold under that name in this period." />
        ) : (
          <div className="revenue-table-wrap">
          <table className="bn-table revenue-table">
            <thead>
              <tr>
                <th className="revenue-disclosure-col" />
                {(['name', 'copies', 'gross', 'last'] as const).map((key) => {
                  const active = sortKey === key
                  const numeric = key === 'copies' || key === 'gross'
                  return (
                    <th
                      key={key}
                      className={numeric ? 'num' : undefined}
                      aria-sort={active ? (sortDir === 'asc' ? 'ascending' : 'descending') : undefined}
                    >
                      <button type="button" className="revenue-sort" onClick={() => handleSort(key)}>
                        {SORT_LABEL[key]}
                        <Icon
                          name={active && sortDir === 'asc' ? 'chevronUp' : 'chevronDown'}
                          size={12}
                          className={active ? 'revenue-sort-icon-active' : 'revenue-sort-icon'}
                        />
                      </button>
                    </th>
                  )
                })}
                {prices === null ? null : <th>Today</th>}
              </tr>
            </thead>
            <tbody className="bn-stagger">
              {products.map((row, i) => {
                const isOpen = expanded.has(row.name)
                const detailId = `revenue-detail-${row.name}`
                const lines = scopeSales
                  .filter((s) => s.name === row.name)
                  .slice()
                  .sort((a, b) => b.at.getTime() - a.at.getTime())
                const compare = prices === null ? null : marketCompareOf(row, prices)
                return (
                  <Fragment key={row.name}>
                    <tr style={{ '--i': i } as CSSProperties}>
                      <td className="revenue-disclosure-col">
                        <button
                          type="button"
                          className="revenue-disclosure"
                          aria-expanded={isOpen}
                          aria-controls={detailId}
                          aria-label={`${isOpen ? 'Hide' : 'Show'} the orders behind ${row.name}`}
                          onClick={() => toggleExpanded(row.name)}
                        >
                          <Icon name={isOpen ? 'chevronDown' : 'chevronRight'} size={14} />
                        </button>
                      </td>
                      <td>{row.nameIsSku ? <span className="bn-mono">{row.name}</span> : row.name}</td>
                      <td className="num">{row.copies.toLocaleString()}</td>
                      {/* PLAIN, NOT GROUPED — a per-product row reads at three or four digits,
                          the same size `money()` is already right for everywhere else it is used,
                          and a comma here would be the only one in a column of otherwise-plain
                          figures. Grouping is for the two headline totals, not every number on
                          the screen. */}
                      <td className="num"><span className="bn-money">{money(row.gross)}</span></td>
                      <td>{row.last.toLocaleDateString()}</td>
                      {prices === null ? null : (
                        <td className="revenue-market">
                          {compare === null ? (
                            <span className="revenue-market-none">no reading</span>
                          ) : (
                            <>
                              <span className="bn-money">{money(compare.market)}</span>
                              <span className="revenue-market-delta">
                                {`${compare.diff > 0 ? '+' : compare.diff < 0 ? '−' : ''}${money(Math.abs(compare.diff))} ${compare.word} what it sold for`}
                              </span>
                              <ReadingAge at={new Date(compare.at * 1000).toISOString()} />
                            </>
                          )}
                        </td>
                      )}
                    </tr>
                    {isOpen ? (
                      <tr id={detailId} className="revenue-detail-row">
                        <td colSpan={prices === null ? 5 : 6}>
                          <table className="bn-table revenue-detail-table" aria-label={`Orders that included ${row.name}`}>
                            <thead>
                              <tr>
                                <th>Date</th>
                                <th>Order</th>
                                <th className="num">Copies</th>
                                <th className="num">Unit price</th>
                              </tr>
                            </thead>
                            <tbody>
                              {lines.map((s, i) => (
                                <tr key={`${s.order}-${i}`}>
                                  <td>{s.at.toLocaleDateString()}</td>
                                  <td><span className="bn-mono">{s.orderNumber}</span></td>
                                  <td className="num">{s.quantity.toLocaleString()}</td>
                                  <td className="num"><span className="bn-money">{money(s.unitPrice)}</span></td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
          </div>
        )}
      </section>
    </main>
  )
}
