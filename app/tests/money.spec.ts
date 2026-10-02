// Protects: `money()` rounds to the cent and `moneyField` turns owner-typed text into a price the field sends, or null.
// Governs: D221
import { test, expect } from '@playwright/test'

import { sealEveryTest } from './shell'
import { money, moneyField } from '../src/money'

/* PURE LOGIC, NO BROWSER, like the first half of `kit-data.spec.ts`. `moneyField` is what a typed
 * price becomes before a press sends it, so a wrong cut here is a wrong price on TCGplayer. */

sealEveryTest()

test.describe('money()', () => {
  test('draws every figure to the cent', () => {
    expect(money(12)).toBe('$12.00')
    expect(money(0)).toBe('$0.00')
    expect(money(1.5)).toBe('$1.50')
  })

  test('rounds the third place, up and down', () => {
    expect(money(1.239)).toBe('$1.24')
    expect(money(1.231)).toBe('$1.23')
    expect(money(0.004)).toBe('$0.00')
    expect(money(349.9949)).toBe('$349.99')
  })

  test('says a dash where there is no figure', () => {
    expect(money(null)).toBe('—')
    expect(money(undefined)).toBe('—')
  })

  test('says the same dash for a figure that is not a finite number', () => {
    expect(money(NaN)).toBe('—')
    expect(money(Infinity)).toBe('—')
  })
})

test.describe('moneyField', () => {
  test('cuts an export price to two places', () => {
    expect(moneyField('349.9900')).toBe('349.99')
    expect(moneyField('0.4900')).toBe('0.49')
  })

  test('pads whole and short amounts to two places', () => {
    expect(moneyField('12')).toBe('12.00')
    expect(moneyField('12.5')).toBe('12.50')
    expect(moneyField('.5')).toBe('0.50')
  })

  test('trims the spaces a person leaves around a price', () => {
    expect(moneyField('  7.25 ')).toBe('7.25')
  })

  test('rounds the third place instead of cutting it', () => {
    expect(moneyField('1.239')).toBe('1.24')
    expect(moneyField('1.231')).toBe('1.23')
  })

  test('refuses text that is not a bare non-negative amount', () => {
    for (const bad of ['', '   ', '$5', '1,000', '-3', '+3', 'abc', '1.', '1.2.3', '5 dollars', '1e3']) {
      expect(moneyField(bad), JSON.stringify(bad)).toBeNull()
    }
  })

  test('refuses a missing value', () => {
    expect(moneyField(null)).toBeNull()
    expect(moneyField(undefined)).toBeNull()
  })
})
