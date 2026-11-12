// Protects: a pasted order keeps the name on the parcel and never the street beside it (D193).
// Governs: D193, D69 (the paste boundary), app/src/orderPaste.ts's ORDER_KEEP and readOrder
import { test, expect } from './unit'
import { readPaste } from '../../src/orderPaste'

/* THE PASTE IS PROJECTED, NOT VALIDATED: a key nobody named is a key nobody sends. These cases
 * hold the one new key to the same rule. `ship_to` crosses as text, an object under it never
 * does, and the `shippingAddress` object TCGplayer sends beside it is not opened at all. */

const ORDER = {
  source: 'TCGplayer',
  number: 'A-1',
  placed_at: '2026-08-27T10:00:00.000+00:00',
  status: 'Processing',
  buyer: 'Buyer Placeholder',
  ship_to: 'Recipient Placeholder',
  shippingAddress: { addressOne: '101 Example St', city: 'Springfield' },
  lines: [{ sku: '9191486', quantity: 1 }],
}

test('a paste keeps the ship-to name beside the buyer, and the street object beside it is dropped', () => {
  const reading = readPaste(JSON.stringify({ orders: [ORDER] }))
  expect(reading.ok).toBe(true)
  if (!reading.ok) return
  expect(reading.orders[0]!.ship_to).toBe('Recipient Placeholder')
  expect(reading.orders[0]!.buyer).toBe('Buyer Placeholder')
  expect(reading.dropped).toContain('shippingAddress')
  expect(JSON.stringify(reading.orders)).not.toContain('101 Example St')
})

test('an address object nested under ship_to never crosses, and ship_to is left unset', () => {
  const reading = readPaste(JSON.stringify({
    orders: [{ ...ORDER, ship_to: { addressOne: '101 Example St', city: 'Springfield' } }],
  }))
  expect(reading.ok).toBe(true)
  if (!reading.ok) return
  expect(reading.orders[0]).not.toHaveProperty('ship_to')
  expect(JSON.stringify(reading.orders)).not.toContain('101 Example St')
})

test('a paste that names no ship-to sets none, so the name already held is kept by the ingest', () => {
  const withoutShipTo = { ...ORDER, ship_to: undefined }
  const reading = readPaste(JSON.stringify({ orders: [withoutShipTo] }))
  expect(reading.ok).toBe(true)
  if (!reading.ok) return
  expect(reading.orders[0]).not.toHaveProperty('ship_to')
})
