// Protects: Sales gross is quantity times unit price over non-canceled orders, never profit, and a missing price is never a guessed zero.
// Governs: D214, D225, D298
import { test, expect } from '@playwright/test'

import { sealEveryTest } from './shell'
import { salesOf, sum } from '../src/revenueMath'
import type { OrderLineWire, OrderRow } from '../src/types'

/* PURE LOGIC, NO BROWSER. `revenue.spec.ts` reaches this arithmetic only through the screen;
 * this calls it directly. Gross only (D214): there is no cost, fee or refund figure to subtract. */

sealEveryTest()

function line(over: Partial<OrderLineWire> = {}): OrderLineWire {
  return {
    sku: '9100001', quantity: 1, name: 'Charizard ex', number: '006', printing: 'Holo',
    condition: 'Near Mint', rarity: 'Rare', unit_price: '12.50', kind: null, ...over,
  }
}

function order(lines: OrderLineWire[], over: Partial<OrderRow> = {}): OrderRow {
  return {
    key: 'TCGplayer:A', source: 'TCGplayer', number: 'A', placed_at: '2026-08-01T10:00:00+00:00',
    status: 'Shipped', first_seen: '2026-08-01T10:05:00+00:00', changed_at: null, buyer: 'Ada',
    wanted: 1, recorded: 1, open: false, terminal: true, progress: [], lines, ...over,
  }
}

test('gross is quantity times unit price, summed over every line', () => {
  const { sales } = salesOf([
    order([line({ quantity: 3, unit_price: '12.50' }), line({ sku: '9100002', quantity: 2, unit_price: '0.49' })]),
  ])
  expect(sum(sales)).toBeCloseTo(3 * 12.5 + 2 * 0.49, 6)
})

test('a canceled order adds nothing, whatever its case or spacing, and is counted apart', () => {
  const { sales, canceledOrders } = salesOf([
    order([line({ quantity: 2 })], { key: 'k1', number: '1' }),
    order([line({ quantity: 9 })], { key: 'k2', number: '2', status: 'Canceled' }),
    order([line({ quantity: 9 })], { key: 'k3', number: '3', status: ' canceled ' }),
  ])
  expect(sum(sales)).toBe(25)
  expect(canceledOrders).toBe(2)
})

test('a line closed as never shipping is left out of gross', () => {
  const { sales, refundExcluded } = salesOf([
    order([line({ quantity: 1 }), line({ sku: '9100002', quantity: 1, unit_price: '4.00' })], {
      progress: [{ sku: '9100002', closed_reason: 'not_shipping' } as OrderRow['progress'][number]],
    }),
  ])
  expect(sum(sales)).toBe(12.5)
  expect(refundExcluded).toBe(1)
})

test('a line with no readable price is kept and unpriced, never a guessed price', () => {
  const { sales } = salesOf([order([line({ unit_price: '' }), line({ sku: '9100002', unit_price: null })])])
  expect(sales.map((s) => s.priceKnown)).toEqual([false, false])
  expect(sum(sales)).toBe(0)
})

test('an order with no usable date is dropped and counted', () => {
  const { sales, dropped } = salesOf([order([line()], { placed_at: null }), order([line()], { placed_at: 'not a date' })])
  expect(sales).toHaveLength(0)
  expect(dropped).toBe(2)
})

test('the result is gross: it carries no cost, fee or profit field', () => {
  const sale = salesOf([order([line()])]).sales[0]!
  expect(Object.keys(sale).filter((key) => /profit|cost|fee|net|margin/i.test(key))).toEqual([])
})

/* MIX'S PIVOT MATH (docs/specs/sales-screen.md, Mix, checks 8 to 13 and 23), pure and browserless. */

/* BUILDER CONTRACT: `app/src/mixPivot.ts` exports the names below. Each case loads the module
 * with a dynamic import, so a missing file or export fails an assertion naming it, never an import.
 *
 *   type DimId      'game' | 'set' | 'rarity' | 'finish' | 'state' | 'box' | 'capw' | 'salew' | 'band'
 *                   (the URL's filter keys; `capw` reads `capturedWeek`, `salew` reads `soldWeek`,
 *                   null reads 'Not sold', `band` reads priceBand of the card's price)
 *   type MeasureId  'captured' | 'onhand' | 'sold' | 'pct' | 'recent' | 'weeks' | 'revenue' | 'median'
 *   type MixCard    the wire card: game set rarity finish state box capturedWeek soldWeek sku price soldRecent
 *   priceBand(price: number | null): string
 *   avgSalePrice(sales: readonly Sale[]): Record<sku, number>   // refund-adjusted gross / copies, per SKU
 *   measureOf(cards: MixCard[], measure: MeasureId, salePrice: Record<string, number>): number | null
 *       null is a dash. `pct` is a fraction (0.4), `weeks` is on hand over (recent / 2).
 *       A sold card's price is salePrice[sku]; any other card's price is its own `price`.
 *   pivot(cards, { by, across: DimId | null, measure, filters: Partial<Record<DimId, string[]>>, salePrice }):
 *       { columns: string[]  (distinct values of `across`, then 'All' last),
 *         rows: { key: string, cells: Record<string, number | null> }[] }
 *   optionCounts(cards, filters, dim): Record<string, number>
 *       cards each option of `dim` would leave, under every filter except `dim`'s own. */

type Mod = Record<string, (...args: never[]) => unknown>
async function load(): Promise<Mod | null> {
  try {
    // A variable specifier: the file does not exist before the build, and tsc must not fail on it.
    const where = '../src/mixPivot'
    return (await import(where)) as unknown as Mod
  } catch {
    return null
  }
}
async function need(name: string): Promise<(...args: any[]) => any> {
  const mod = await load()
  expect(mod, 'app/src/mixPivot.ts exists').not.toBeNull()
  const fn = mod![name]
  expect(typeof fn, `mixPivot exports "${name}"`).toBe('function')
  return fn as (...args: any[]) => any
}

const card = (over: Record<string, unknown> = {}) => ({
  game: 'riftbound', set: 'Origins', rarity: 'Rare', finish: 'Near Mint', state: 'On hand', box: 'Alpha',
  capturedWeek: '2026-09-14', soldWeek: null, sku: 'S1', price: 2, soldRecent: 0, ...over,
})
const sold = (over: Record<string, unknown> = {}) =>
  card({ state: 'Sold', soldWeek: '2026-09-14', soldRecent: 0, ...over })
const unlisted = (over: Record<string, unknown> = {}) =>
  card({ state: 'Not listed yet', sku: null, price: null, ...over })

test('8. Sold of captured counts unlisted cards in the divisor, over all time', async () => {
  const measureOf = await need('measureOf')
  const cards = [sold(), sold({ soldWeek: '2026-01-05' }), card(), unlisted(), unlisted()]
  expect(measureOf(cards, 'pct', {})).toBeCloseTo(2 / 5, 9)
  expect(measureOf([], 'pct', {}), 'a ratio over an empty set is a dash').toBeNull()
})

test('9. Weeks of stock is a dash with no sale in 14 days, never 0 or infinity', async () => {
  const measureOf = await need('measureOf')
  const none = [card(), card(), sold({ soldRecent: 0 })]
  expect(measureOf(none, 'weeks', {})).toBeNull()
  const some = [card(), card(), card(), sold({ soldRecent: 1 }), sold({ soldRecent: 1 })]
  expect(measureOf(some, 'weeks', {}), 'on hand 3 over (2 sold / 2 weeks)').toBeCloseTo(3, 9)
})

test('10. a median over no prices is a dash', async () => {
  const measureOf = await need('measureOf')
  expect(measureOf([unlisted(), card({ price: null })], 'median', {})).toBeNull()
  expect(measureOf([card({ price: 1 }), card({ price: 9 }), card({ price: 2 }), unlisted()], 'median', {})).toBe(2)
  expect(measureOf([card({ price: 1 }), card({ price: 3 })], 'median', {})).toBe(2)
})

test('11. price band edges: $0.99, $1, $4.99, $5, $19.99, $20', async () => {
  const priceBand = await need('priceBand')
  expect(
    [0.99, 1, 4.99, 5, 19.99, 20, null].map((p) => priceBand(p)),
  ).toEqual(['Under $1', '$1 to $5', '$1 to $5', '$5 to $20', '$5 to $20', '$20 and up', 'No price yet'])
})

test('12. a row’s cells sum to its All cell for Cards captured, On hand and Sold', async () => {
  const pivot = await need('pivot')
  const cards = [
    card(), card({ rarity: 'Epic' }), sold(), sold({ rarity: 'Epic', set: 'Spirit' }),
    unlisted({ rarity: 'No claim' }), card({ set: 'Spirit', rarity: 'Common' }),
  ]
  for (const measure of ['captured', 'onhand', 'sold']) {
    const out = pivot(cards, { by: 'set', across: 'rarity', measure, filters: {}, salePrice: {} })
    expect(out.columns.at(-1), 'All is the last column').toBe('All')
    expect(out.rows.length).toBeGreaterThan(1)
    for (const row of out.rows) {
      const parts = out.columns.filter((c: string) => c !== 'All').reduce((n: number, c: string) => n + (row.cells[c] ?? 0), 0)
      expect(parts, `${measure}, row ${row.key}`).toBe(row.cells.All)
    }
  }
})

test('13. each option count respects the other filters and ignores its own dimension', async () => {
  const optionCounts = await need('optionCounts')
  const cards = [
    card(), card({ rarity: 'Epic' }), card({ game: 'pokemon', rarity: 'Epic' }),
    card({ game: 'pokemon', rarity: 'Common' }), sold({ soldWeek: '2026-09-07' }),
  ]
  // Game is riftbound and Rarity is Rare: Rarity's own pick must not narrow Rarity's options.
  const rarity = optionCounts(cards, { game: ['riftbound'], rarity: ['Rare'] }, 'rarity')
  expect(rarity.Rare, 'the sold Rare card counts too').toBe(2)
  expect(rarity.Epic).toBe(1)
  expect(rarity.Common ?? 0, 'the other game is filtered out').toBe(0)
  // Game's options respect Rarity's pick.
  const game = optionCounts(cards, { game: ['riftbound'], rarity: ['Epic'] }, 'game')
  expect(game.riftbound).toBe(1)
  expect(game.pokemon).toBe(1)
  // A card that has not sold is 'Not sold' under Sale week.
  expect(optionCounts(cards, {}, 'salew')['Not sold']).toBe(4)
})

test('23. Mix revenue for a SKU equals Sales’ figure, with a refunded line left out', async () => {
  const avgSalePrice = await need('avgSalePrice')
  const measureOf = await need('measureOf')
  const wire = (qty: number, price: string): OrderLineWire => ({
    sku: 'S1', quantity: qty, name: 'Ahri', number: '001', printing: null, condition: 'Near Mint',
    rarity: 'Rare', unit_price: price, kind: null,
  })
  const order = (key: string, lines: OrderLineWire[], refunded = false): OrderRow =>
    ({
      key, source: 'TCGplayer', number: key, placed_at: '2026-09-01T10:00:00+00:00', status: 'Shipped',
      first_seen: '2026-09-01T10:00:00+00:00', changed_at: null, buyer: 'x', wanted: 1, recorded: 1,
      open: false, terminal: true, lines,
      progress: refunded
        ? [{ sku: 'S1', wanted: 1, recorded: 0, outstanding: 0, over: 0, copies: [], by_hand: 0, reason: null, declared_kind: null, closed_at: null, closed_reason: 'not_shipping', at: null }]
        : [],
    }) as unknown as OrderRow
  // Two copies at $10 sold; one $40 line refunded. Sales counts $20 over 2 copies.
  const { sales } = salesOf([order('A', [wire(2, '10.00')]), order('B', [wire(1, '40.00')], true)])
  expect(sum(sales)).toBe(20)
  const salePrice = avgSalePrice(sales)
  expect(salePrice.S1).toBe(10)
  const twoSold = [sold(), sold()]
  expect(measureOf(twoSold, 'revenue', salePrice), 'Mix agrees with Sales; ignoring the refund gives 40').toBe(sum(sales))
})
