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
