// Protects: Each app formatter (ago phrase, count word, byte size, local day key) has one home, and every screen reads it.
// Governs: one home per capability (CLAUDE.md hard rule)
import { readFileSync } from 'node:fs'
import { expect, test } from './unit'
import * as dates from '../../src/dates'
import * as rules from '../../src/kit/dataRules'
import { readingAgo } from '../../src/cardState'

/* THE FOUR HOMES, pinned. BUILDER CONTRACT (names the tests import):
 *   dates.ts          relativeDate (exists), localDay(at: Date = new Date()): 'YYYY-MM-DD' in the runtime zone
 *   kit/dataRules.ts  count(n, one, many = `${one}s`): '1,234 cards'   byteSize(bytes): decimal, 1 dp
 * A source check beside each behaviour fails when a second copy reappears. */

const src = (path: string): string => readFileSync(new URL(`../../src/${path}`, import.meta.url), 'utf8')
const fn = (mod: unknown, name: string): ((...a: unknown[]) => string) => {
  const f = (mod as Record<string, unknown>)[name]
  if (typeof f !== 'function') throw new Error(`export "${name}" is missing`)
  return f as (...a: unknown[]) => string
}

/* 1. AGO PHRASE */
const NOW = new Date('2026-06-15T12:00:00Z').getTime()
const AGES: ReadonlyArray<readonly [string, number]> = [
  ['30 s', 30_000],
  ['90 s', 90_000],
  ['1 h', 3_600_000],
  ['26 h', 26 * 3_600_000],
  ['8 days', 8 * 86_400_000],
]

for (const [label, ms] of AGES) {
  test(`readingAgo says what relativeDate says at ${label}`, () => {
    const RealDate = globalThis.Date
    class Fixed extends RealDate {
      constructor(...args: unknown[]) {
        // @ts-expect-error spread into the base constructor
        super(...(args.length === 0 ? [NOW] : args))
      }
      static now(): number {
        return NOW
      }
    }
    globalThis.Date = Fixed as unknown as DateConstructor
    try {
      const at = new RealDate(NOW - ms).toISOString()
      expect(readingAgo(at)).toBe(dates.relativeDate(at, new RealDate(NOW)))
    } finally {
      globalThis.Date = RealDate
    }
  })
}

test('no second "ago" formatter is defined outside dates.ts', () => {
  const defs = /(function|const)\s+(ageWords|readingAgoShort)\b/
  for (const f of ['RunPanel.tsx', 'Pricing.tsx', 'cardState.ts']) expect(src(f), f).not.toMatch(defs)
  expect(src('cardState.ts')).not.toMatch(/minutes? ago|\$\{hours\} hour/)
})

/* 2. COUNT WORD */
test('count groups thousands and pluralises', () => {
  const count = fn(rules, 'count')
  expect(count(1234, 'card')).toBe('1,234 cards')
  expect(count(1, 'card')).toBe('1 card')
  expect(count(0, 'card')).toBe('0 cards')
  expect(count(2, 'box', 'boxes')).toBe('2 boxes')
})

test('no screen keeps its own plural or count word', () => {
  const own = /(function|const)\s+(plural|cardsWord)\b|function count\(n: number, one/
  for (const f of ['Codes.tsx', 'Home.tsx', 'Fulfillment.tsx', 'InventorySets.tsx', 'SendCard.tsx', 'RunsComposer.tsx', 'dealer.ts', 'Orders.tsx', 'CardLocations.tsx'])
    expect(src(f), f).not.toMatch(own)
})

/* 3. BYTE SIZE */
test('byteSize is decimal, so 31,500,000 bytes reads 31.5 MB', () => {
  const byteSize = fn(rules, 'byteSize')
  expect(byteSize(31_500_000)).toBe('31.5 MB')
  expect(byteSize(999)).toBe('999 B')
  expect(byteSize(1_234)).toBe('1.2 kB')
  expect(byteSize(33_554_432)).toBe('33.6 MB')
})

test('no screen keeps its own byte formatter', () => {
  const own = /(function|const)\s+(mb|megabytes|sizeOf)\b|\/ 1024 \/ 1024|\/ 1000\)\.toFixed|\/ 1_000_000/
  for (const f of ['RunPanel.tsx', 'BoxOps.tsx', 'RunFiles.tsx', 'OrdersShipStage.tsx']) expect(src(f), f).not.toMatch(own)
})

/* 4. LOCAL DAY KEY */
test('localDay is the local date at 23:30 in UTC-5, not the UTC date', () => {
  const was = process.env.TZ
  process.env.TZ = 'America/Bogota' // UTC-5, no DST
  try {
    const at = new Date('2026-03-10T23:30:00-05:00') // 04:30 UTC the next day
    expect(at.toISOString().slice(0, 10)).toBe('2026-03-11')
    expect(fn(dates, 'localDay')(at)).toBe('2026-03-10')
  } finally {
    if (was === undefined) delete process.env.TZ
    else process.env.TZ = was
  }
})

test('no screen builds its own day key', () => {
  for (const f of ['Orders.tsx', 'Codes.tsx']) expect(src(f), f).not.toMatch(/toISOString\(\)\.slice\(0, 10\)/)
  expect(src('Revenue.tsx')).not.toMatch(/function isoDate/)
})
