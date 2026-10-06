import type { MixCard } from './types'
import type { Sale } from './revenueMath'

/* THE MIX PIVOT'S MATH (`docs/specs/sales-screen.md`, Mix), PURE, so a spec can call it. The wire
 * (`GET /stock/mix`) carries card rows; every count, ratio and group is made here, in the browser,
 * so a press on any control is a local recompute and fetches nothing.
 *
 * REVENUE IS NOT A SERVER SUM. A sold card's price is its SKU's average sale price off
 * `salesOf`'s refund-adjusted lines (`avgSalePrice`), so Mix cannot disagree with Sales (D225).
 * Gross only, never profit (D214). */

export type DimId = 'game' | 'set' | 'rarity' | 'finish' | 'state' | 'box' | 'capw' | 'salew' | 'band'
export type MeasureId = 'captured' | 'onhand' | 'sold' | 'pct' | 'recent' | 'weeks' | 'revenue' | 'median'
export type { MixCard }

/** The URL's filter keys, in the order the bar draws them. */
export const DIMENSIONS: readonly { readonly id: DimId; readonly label: string }[] = [
  { id: 'game', label: 'Game' },
  { id: 'set', label: 'Set' },
  { id: 'rarity', label: 'Rarity' },
  { id: 'finish', label: 'Finish' },
  { id: 'state', label: 'State' },
  { id: 'box', label: 'Box' },
  { id: 'capw', label: 'Capture week' },
  { id: 'salew', label: 'Sale week' },
  { id: 'band', label: 'Price band' },
]

export type MeasureKind = 'count' | 'money' | 'ratio' | 'weeks'

export const MEASURES: readonly { readonly id: MeasureId; readonly label: string; readonly kind: MeasureKind }[] = [
  { id: 'captured', label: 'Cards captured', kind: 'count' },
  { id: 'onhand', label: 'On hand', kind: 'count' },
  { id: 'sold', label: 'Sold', kind: 'count' },
  { id: 'pct', label: 'Sold of captured', kind: 'ratio' },
  { id: 'recent', label: 'Sold, last 14 days', kind: 'count' },
  { id: 'weeks', label: 'Weeks of stock', kind: 'weeks' },
  { id: 'revenue', label: 'Revenue', kind: 'money' },
  { id: 'median', label: 'Median price', kind: 'money' },
]

/** SKU to its average sale price. */
export type SalePrice = Readonly<Record<string, number>>
export type MixFilters = Readonly<Partial<Record<DimId, readonly string[]>>>

const BANDS = ['No price yet', 'Under $1', '$1 to $5', '$5 to $20', '$20 and up'] as const
const RARITY_ORDER = ['Common', 'Uncommon', 'Rare', 'Epic', 'Showcase']
const STATE_ORDER = ['On hand', 'Sold', 'Not listed yet']
const NOT_SOLD = 'Not sold'
const NO_WEEK = 'No date'

export function priceBand(price: number | null): string {
  if (price === null) return BANDS[0]
  if (price < 1) return BANDS[1]
  if (price < 5) return BANDS[2]
  if (price < 20) return BANDS[3]
  return BANDS[4]
}

/** Each SKU's refund-adjusted gross over its copies, from `salesOf`'s own lines. A line with no
 *  usable price adds neither a dollar nor a copy, and a SKU with no priced copy is absent. */
export function avgSalePrice(sales: readonly Sale[]): Record<string, number> {
  const gross: Record<string, number> = {}
  const copies: Record<string, number> = {}
  for (const sale of sales) {
    if (!sale.priceKnown || sale.quantity <= 0) continue
    gross[sale.sku] = (gross[sale.sku] ?? 0) + sale.gross
    copies[sale.sku] = (copies[sale.sku] ?? 0) + sale.quantity
  }
  const out: Record<string, number> = {}
  for (const sku of Object.keys(gross)) out[sku] = gross[sku]! / copies[sku]!
  return out
}

/** A card's price: a sold card's is its SKU's average sale price (none if the orders never saw
 *  it, never a market reading passed off as a sale), any other card's is its own reading. */
export function priceOf(card: MixCard, salePrice: SalePrice): number | null {
  if (card.state !== 'Sold') return card.price
  return card.sku !== null && card.sku in salePrice ? salePrice[card.sku]! : null
}

/** One card's value on one dimension. */
export function dimValue(card: MixCard, dim: DimId, salePrice: SalePrice = {}): string {
  switch (dim) {
    case 'game': return card.game
    case 'set': return card.set
    case 'rarity': return card.rarity
    case 'finish': return card.finish
    case 'state': return card.state
    case 'box': return card.box
    case 'capw': return card.capturedWeek ?? NO_WEEK
    case 'salew': return card.soldWeek ?? NOT_SOLD
    case 'band': return priceBand(priceOf(card, salePrice))
  }
}

const median = (values: number[]): number | null => {
  if (values.length === 0) return null
  const sorted = [...values].sort((a, b) => a - b)
  const mid = sorted.length >> 1
  return sorted.length % 2 === 1 ? sorted[mid]! : (sorted[mid - 1]! + sorted[mid]!) / 2
}

/** One measure over a group of cards. `null` is a dash: a ratio over nothing, weeks of stock with
 *  no sale in 14 days, a median over no prices. */
export function measureOf(cards: readonly MixCard[], measure: MeasureId, salePrice: SalePrice): number | null {
  const sold = cards.filter((card) => card.state === 'Sold')
  const recent = cards.reduce((n, card) => n + card.soldRecent, 0)
  switch (measure) {
    case 'captured': return cards.length
    case 'onhand': return cards.filter((card) => card.state === 'On hand').length
    case 'sold': return sold.length
    case 'pct': return cards.length === 0 ? null : sold.length / cards.length
    case 'recent': return recent
    case 'weeks': return recent === 0 ? null : cards.filter((card) => card.state === 'On hand').length / (recent / 2)
    case 'revenue': return sold.reduce((n, card) => n + (priceOf(card, salePrice) ?? 0), 0)
    case 'median': {
      const prices: number[] = []
      for (const card of cards) {
        const price = priceOf(card, salePrice)
        if (price !== null) prices.push(price)
      }
      return median(prices)
    }
  }
}

/** The values of a dimension in the order a person reads them: rarity and state by their own
 *  ladder, a price band low to high, a week by date, the rest A to Z. */
export function orderValues(dim: DimId, values: Iterable<string>): string[] {
  const list = [...new Set(values)]
  const ladder = dim === 'rarity' ? RARITY_ORDER : dim === 'state' ? STATE_ORDER : dim === 'band' ? [...BANDS] : null
  const rank = (value: string) => {
    const at = ladder === null ? -1 : ladder.indexOf(value)
    return at < 0 ? ladder === null ? 0 : ladder.length : at
  }
  const last = (value: string) => (dim === 'salew' && value === NOT_SOLD) || (dim === 'capw' && value === NO_WEEK) ? 1 : 0
  return list.sort((a, b) => last(a) - last(b) || rank(a) - rank(b) || a.localeCompare(b))
}

/** The cards every filter lets through, except the dimension named in `skip`. A card passes a
 *  filter when its value is one of the picks. */
export function filterCards(cards: readonly MixCard[], filters: MixFilters, salePrice: SalePrice = {}, skip: DimId | null = null): MixCard[] {
  const active = DIMENSIONS.filter((dim) => dim.id !== skip && (filters[dim.id]?.length ?? 0) > 0)
  if (active.length === 0) return [...cards]
  return cards.filter((card) => active.every((dim) => filters[dim.id]!.includes(dimValue(card, dim.id, salePrice))))
}

/** How many cards each option of `dim` would leave, under every filter except `dim`'s own. */
export function optionCounts(cards: readonly MixCard[], filters: MixFilters, dim: DimId, salePrice: SalePrice = {}): Record<string, number> {
  const out: Record<string, number> = {}
  for (const card of filterCards(cards, filters, salePrice, dim)) {
    const value = dimValue(card, dim, salePrice)
    out[value] = (out[value] ?? 0) + 1
  }
  return out
}

export type PivotSpec = {
  readonly by: DimId
  /** `null` draws one column per measure. */
  readonly across: DimId | null
  /** One measure, or several when `across` is null. */
  readonly measure: MeasureId | readonly MeasureId[]
  readonly filters: MixFilters
  readonly salePrice: SalePrice
}

export type PivotRow = { readonly key: string; readonly cells: Record<string, number | null> }
export type Pivot = {
  /** Column keys: the distinct values of `across`, then `All`; or the measure ids. */
  readonly columns: string[]
  readonly rows: PivotRow[]
  /** The `All` row: every filtered card, per column. */
  readonly total: Record<string, number | null>
  /** The cards the filters left. */
  readonly matched: number
}

export const ALL = 'All'

export function pivot(cards: readonly MixCard[], spec: PivotSpec): Pivot {
  const { by, across, filters, salePrice } = spec
  const measures = ([] as MeasureId[]).concat(spec.measure as MeasureId | MeasureId[])
  const kept = filterCards(cards, filters, salePrice)
  const first = measures[0]!
  const split = across === null ? null : orderValues(across, kept.map((card) => dimValue(card, across, salePrice)))
  const columns = split === null ? measures.map(String) : [...split, ALL]
  const cellsOf = (group: readonly MixCard[]): Record<string, number | null> => {
    const cells: Record<string, number | null> = {}
    if (across === null) {
      for (const measure of measures) cells[measure] = group.length === 0 ? null : measureOf(group, measure, salePrice)
      return cells
    }
    for (const value of split!) {
      const part = group.filter((card) => dimValue(card, across, salePrice) === value)
      cells[value] = part.length === 0 ? null : measureOf(part, first, salePrice)
    }
    cells[ALL] = group.length === 0 ? null : measureOf(group, first, salePrice)
    return cells
  }
  const keys = orderValues(by, kept.map((card) => dimValue(card, by, salePrice)))
  const rows = keys.map((key) => ({
    key,
    cells: cellsOf(kept.filter((card) => dimValue(card, by, salePrice) === key)),
  }))
  return { columns, rows, total: cellsOf(kept), matched: kept.length }
}
