// Protects: Each app formatter (ago phrase, count word, byte size, local day key) has one home, and every screen reads it.
// Governs: one home per capability (CLAUDE.md hard rule)
import { readFileSync } from 'node:fs'
import { expect, test } from './unit'
import * as dates from '../../src/dates'
import * as rules from '../../src/kit/dataRules'
import * as cardState from '../../src/cardState'
import { readingAgo } from '../../src/cardState'

/* THE FOUR HOMES, pinned. BUILDER CONTRACT (names the tests import):
 *   dates.ts          relativeDate (exists), localDay(at: Date = new Date()): 'YYYY-MM-DD' in the runtime zone
 *                     utcDay(at: Date = new Date()): 'YYYY-MM-DD' in UTC (the wire's and the server's day)
 *                     relativeDateShort(at, now = new Date()): 'just now' | '5m ago' | '5h ago' | '2d ago'
 *   cardState.ts      readingBound(at): 'Recent' | 'Recent, 3 days' | null (moved here from BoxOps.tsx, which imports it)
 *   kit/dataRules.ts  count(n, one, many = `${one}s`): '1,234 cards'   byteSize(bytes): 1024 units labelled MB, 1 dp
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

/* 3. BYTE SIZE: 1024 units, labelled MB, so the screen agrees with the server's `MAX_BYTES // (1024*1024)` ("32 MB"). */
test('byteSize counts 1024-byte units, so the 32 MiB export cap reads 32.0 MB', () => {
  const byteSize = fn(rules, 'byteSize')
  expect(byteSize(999)).toBe('999 B')
  expect(byteSize(1_048_576)).toBe('1.0 MB')
  expect(byteSize(31_500_000)).toBe('30.0 MB')
  expect(byteSize(32_629_598)).toBe('31.1 MB')
  expect(byteSize(33_554_432)).toBe('32.0 MB')
})

test('no screen keeps its own byte formatter', () => {
  const own = /(function|const)\s+(mb|megabytes|sizeOf)\b|\/ 1024 \/ 1024|\/ 1000\)\.toFixed|\/ 1_000_000/
  for (const f of ['RunPanel.tsx', 'BoxOps.tsx', 'RunFiles.tsx', 'OrdersShipStage.tsx', 'RunsComposer.tsx']) expect(src(f), f).not.toMatch(own)
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

/* 4b. UTC DAY KEY: `placed_at` and the server's `_reconcile_cutoff` are keyed in UTC, so the backlog
 *     panel's default cutoff is the UTC day. At 2026-10-05T20:00Z Auckland (UTC+13) is already 10-06. */
test('utcDay is the UTC date at 20:00Z in Auckland, where localDay is already the next day', () => {
  const was = process.env.TZ
  process.env.TZ = 'Pacific/Auckland'
  try {
    const at = new Date('2026-10-05T20:00:00Z')
    expect(fn(dates, 'localDay')(at)).toBe('2026-10-06')
    expect(fn(dates, 'utcDay')(at)).toBe('2026-10-05')
  } finally {
    if (was === undefined) delete process.env.TZ
    else process.env.TZ = was
  }
})

test('the reconcile backlog panel keys its day in UTC, not the local zone', () => {
  const orders = src('Orders.tsx')
  expect(orders).toMatch(/\butcDay\(/)
  expect(orders).not.toMatch(/\blocalDay\(/)
})

/* 6. SHORT AGE: the hero's age chip sits in a 128px nowrap cell. */
const AT = (ms: number): Date => new Date(NOW - ms)
test('relativeDateShort says 2d ago, 5h ago, 5m ago and just now', () => {
  const short = fn(dates, 'relativeDateShort')
  const now = new Date(NOW)
  expect(short(AT(30_000), now)).toBe('just now')
  expect(short(AT(5 * 60_000), now)).toBe('5m ago')
  expect(short(AT(5 * 3_600_000), now)).toBe('5h ago')
  expect(short(AT(26 * 3_600_000), now)).toBe('1d ago')
  expect(short(AT(2 * 86_400_000), now)).toBe('2d ago')
  expect(short(null, now)).toBe('—')
})

test('the hero age chip is drawn by relativeDateShort', () => {
  const hero = src('CardHero.tsx')
  expect(hero).toMatch(/relativeDateShort/)
  expect(hero).not.toMatch(/readingAgo\(listedAt\)/)
})

/* 7. READING BOUND: `read within 4 days`, said as a bound. It strips the unit phrase, never a date. */
test('readingBound says Recent, or Recent with the coarse age, and never a date', () => {
  const bound = (cardState as unknown as Record<string, unknown>).readingBound
  if (typeof bound !== 'function') throw new Error('export "readingBound" is missing')
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
    const at = (ms: number): string => new RealDate(NOW - ms).toISOString()
    expect(bound(null)).toBeNull()
    expect(bound(at(30_000))).toBe('Recent')
    expect(bound(at(5 * 3_600_000))).toBe('Recent, 5 hours')
    expect(bound(at(86_400_000 + 60_000))).toBe('Recent, 1 day')
    expect(bound(at(3 * 86_400_000 + 60_000))).toBe('Recent, 3 days')
    expect(bound(at(10 * 86_400_000))).toBe('Recent, 10 days')
  } finally {
    globalThis.Date = RealDate
  }
})

/* 5b. LEFTOVER COPIES, inline. Tight on purpose: only a ternary whose two arms are one noun and its
 *     plural (`=== 1 ? 'card' : 'cards'`, `=== 1 ? '' : 's'`). Verb and pronoun pairs (is/are, it/them) pass. */
function inlinePlurals(text: string): string[] {
  const hits: string[] = []
  for (const m of text.matchAll(/===\s*1\s*\?\s*(['"`])(\w*)\1\s*:\s*(['"`])(\w+)\3/g)) {
    const one = m[2] ?? ''
    const many = m[4] ?? ''
    const stem = one.replace(/y$/, '')
    if ((one === '' && /^(s|es)$/.test(many)) || (one !== '' && many.startsWith(stem) && many !== one)) hits.push(m[0])
  }
  return hits
}

test('no screen keeps an inline plural; count() is the home', () => {
  const files = ['BoxBrowse.tsx', 'DeletedBoxes.tsx', 'CaptureScreen.tsx', 'PriceMovers.tsx', 'OrdersShipStage.tsx', 'BoxOps.tsx', 'ClearPrices.tsx']
  for (const f of files) expect(inlinePlurals(src(f)), f).toEqual([])
})

test('the plural pattern leaves verbs and pronouns alone', () => {
  expect(inlinePlurals("n === 1 ? 'is' : 'are'")).toEqual([])
  expect(inlinePlurals("n === 1 ? 'it' : 'them'")).toEqual([])
  expect(inlinePlurals("n === 1 ? 'x' : 'xs'")).toHaveLength(1)
  expect(inlinePlurals("`${n} card${n===1?'':'s'}`")).toHaveLength(1)
  expect(inlinePlurals("n === 1 ? 'copy' : 'copies'")).toHaveLength(1)
})

test('no screen builds its own day key from getFullYear/getMonth/getDate', () => {
  const day = /getFullYear\(\)\}-\$\{\w+\([^`]*?getMonth\(\)[^`]*?\}-\$\{\w+\([^`]*?getDate\(\)/
  for (const f of ['RunsComposer.tsx', 'Orders.tsx', 'Codes.tsx', 'Revenue.tsx', 'Home.tsx', 'Pricing.tsx']) expect(src(f), f).not.toMatch(day)
})

test('BoxBrowse keeps no days/hours phrase of its own', () => {
  expect(src('BoxBrowse.tsx')).not.toMatch(/\/\s*86_?400_?000|\/\s*3_?600_?000/)
})
