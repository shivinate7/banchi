// Protects: one name is drawn when the buyer ships to themselves, and two when they do not (D193).
// Governs: D193, app/src/orderBuyers.ts's shipToOf and foldName
import { test, expect } from './unit'
import { shipToOf } from '../../src/orderBuyers'

/* A comparison folded by `foldName`, the buyer key's own rule, so one person is one name. A
 * blank ship-to is no word at all. An order with no buyer still shows its ship-to, because then
 * it is the only name there is. */

test('shipToOf draws nothing when the ship-to is the buyer, whatever the case or spacing', () => {
  expect(shipToOf({ buyer: 'Ada  Lovelace', ship_to: 'ada lovelace' })).toBeNull()
  expect(shipToOf({ buyer: ' Ada Lovelace ', ship_to: 'Ada Lovelace' })).toBeNull()
})

test('shipToOf draws the ship-to when it is a different person', () => {
  expect(shipToOf({ buyer: 'Ada Lovelace', ship_to: 'Grace Hopper' })).toBe('Grace Hopper')
})

test('shipToOf draws the ship-to when the order has no buyer name', () => {
  expect(shipToOf({ buyer: null, ship_to: 'Grace Hopper' })).toBe('Grace Hopper')
})

test('shipToOf draws nothing for a blank or absent ship-to', () => {
  expect(shipToOf({ buyer: 'Ada Lovelace', ship_to: '   ' })).toBeNull()
  expect(shipToOf({ buyer: 'Ada Lovelace', ship_to: null })).toBeNull()
  expect(shipToOf({ buyer: 'Ada Lovelace' })).toBeNull()
})
