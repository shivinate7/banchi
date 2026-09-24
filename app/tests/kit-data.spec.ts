import { test, expect, type Page } from '@playwright/test'

import { sealEveryTest } from './shell'
import { settleFonts } from './fontsReady'
import { canonicalNumber, foldText, matchQuery, queryTokens } from '../src/kit/match'
import { absoluteDate, relativeDate } from '../src/dates'
import { moneyGrouped, moneySigned } from '../src/money'
import { STATUS_TONES, boxesMostRecentFirst } from '../src/kit/dataRules'

/* THE KIT'S DATA PRIMITIVES (`src/kit/data.tsx`), and the one matcher every search shares
 * (`src/kit/match.ts`).
 *
 * TWO HALVES. The first runs no browser: the matcher, the two date formats, money's words, the
 * box order and the status tones are pure functions, asserted as such. The second draws every
 * primitive on `tests/kit-data/index.html`, a test page the dev server serves and the build
 * never ships, so this spec does not wait on the kit page to mount the specimens. It sweeps the
 * four widths every screen is verified at, in both themes. */

sealEveryTest()

const PAGE = '/tests/kit-data/index.html'
const WIDTHS = [1440, 820, 720, 390] as const
const HEIGHT: Record<(typeof WIDTHS)[number], number> = { 1440: 900, 820: 1180, 720: 900, 390: 844 }

/** Every specimen the page draws. A specimen that quietly stops rendering fails the count. */
const SPECIMENS = [
  'Money', 'Count', 'Dates', 'Separator', 'Status', 'Card', 'Photo', 'Box', 'Place', 'Links',
  'Pick one', 'Filters', 'Filtered count', 'Sort', 'Search',
] as const

/* ============================================================================================
 * The matcher: one forgiving rule for every search.
 * ============================================================================================ */

test.describe('matchQuery', () => {
  const abra = {
    text: ['Abra', 'Scarlet & Violet', 'Near Mint'],
    numbers: ['054/132'],
    skus: ['8601230'],
    boxes: [{ box: 4, name: 'Mixed Singles' }],
  }

  test('a card number matches with or without the zeros in front', () => {
    expect(matchQuery('54/132', abra)).toBe(true)
    expect(matchQuery('054/132', abra)).toBe(true)
    expect(matchQuery('#54', abra)).toBe(true)
    expect(matchQuery('54', abra)).toBe(true)
    expect(matchQuery('54/131', abra)).toBe(false)
    /* Never a substring match on a number. */
    expect(matchQuery('54', { numbers: ['154/200'] })).toBe(false)
    expect(matchQuery('tg5/tg30', { numbers: ['TG05/TG30'] })).toBe(true)
    expect(canonicalNumber('054/132')).toBe('54/132')
    expect(canonicalNumber('SWSH050')).toBe('swsh50')
  })

  test('words match in any order, folded for case, accents and punctuation', () => {
    const akali = { text: ['Akali, Deadly Duelist'] }
    expect(matchQuery('akali deadly', akali)).toBe(true)
    expect(matchQuery('deadly akali', akali)).toBe(true)
    expect(matchQuery('akali, deadly', akali)).toBe(true)
    expect(matchQuery('AKALI', akali)).toBe(true)
    expect(matchQuery('akali zed', akali)).toBe(false)
    expect(matchQuery('flabebe', { text: ['Flabébé'] })).toBe(true)
    expect(matchQuery('heimerdinger-inventor', { text: ['Heimerdinger, Inventor'] })).toBe(true)
    expect(matchQuery('ventor', { text: ['Heimerdinger, Inventor'] })).toBe(true)
    expect(foldText('Flabébé')).toBe('flabebe')
  })

  test('a box, a SKU and a condition word each find the row', () => {
    expect(matchQuery('B4', abra)).toBe(true)
    expect(matchQuery('box4', abra)).toBe(true)
    expect(matchQuery('box 4', abra)).toBe(true)
    expect(matchQuery('B5', abra)).toBe(false)
    expect(matchQuery('mixed', abra)).toBe(true)
    expect(matchQuery('860123', abra)).toBe(true)
    expect(matchQuery('near mint', abra)).toBe(true)
    expect(matchQuery('damaged', { text: ['Boss’s Orders', 'Damaged'] })).toBe(true)
    expect(matchQuery('boss orders', { text: ['Boss’s Orders'] })).toBe(true)
  })

  test('an order label is found by what the row draws', () => {
    expect(matchQuery('09-03-26_00012', { text: ['09-03-26_00012'] })).toBe(true)
    expect(matchQuery('09-03-26', { text: ['09-03-26_00012'] })).toBe(true)
  })

  test('an empty query matches every row', () => {
    expect(queryTokens('  , ')).toEqual([])
    expect(matchQuery('', abra)).toBe(true)
  })
})

/* ============================================================================================
 * The formats and the orders.
 * ============================================================================================ */

test('dates have one relative and one absolute format, with no leading zero', () => {
  const now = new Date('2026-09-23T15:00:00')
  expect(absoluteDate(new Date('2026-09-04T12:00:00'))).toBe('Sep 4, 2026')
  expect(absoluteDate(null)).toBe('—')
  expect(relativeDate(new Date('2026-09-23T14:59:40'), now)).toBe('just now')
  expect(relativeDate(new Date('2026-09-23T14:55:00'), now)).toBe('5 minutes ago')
  expect(relativeDate(new Date('2026-09-23T14:00:00'), now)).toBe('1 hour ago')
  expect(relativeDate(new Date('2026-09-22T12:00:00'), now)).toBe('yesterday')
  expect(relativeDate(new Date('2026-09-20T12:00:00'), now)).toBe('3 days ago')
  expect(relativeDate(new Date('2026-09-01T12:00:00'), now)).toBe('Sep 1, 2026')
})

test('money always says its dollar sign, and a change says its sign', () => {
  expect(moneyGrouped(1234.5)).toBe('$1,234.50')
  expect(moneyGrouped(0.4)).toBe('$0.40')
  expect(moneySigned(1.2)).toBe('+$1.20')
  expect(moneySigned(-0.35)).toBe('−$0.35')
  expect(moneySigned(0)).toBe('$0.00')
})

test('a list of boxes is most recent first, then the newest box', () => {
  const recency = new Map([
    [2, '2026-09-20T10:00:00.000Z'],
    [5, '2026-09-22T10:00:00.000Z'],
  ])
  const boxes = [
    { box: 1, bid: 1 },
    { box: 2, bid: 2 },
    { box: 3, bid: 7 },
    { box: 5, bid: 5 },
  ]
  expect(boxesMostRecentFirst(boxes, recency).map((one) => one.box)).toEqual([5, 2, 3, 1])
})

test('amber means only "needs the owner", and blue only "moving now"', () => {
  const tones = Object.entries(STATUS_TONES)
  expect(tones.filter(([, tone]) => tone === 'warn').map(([kind]) => kind)).toEqual(['needs'])
  expect(tones.filter(([, tone]) => tone === 'accent').map(([kind]) => kind)).toEqual(['working'])
})

/* ============================================================================================
 * Every primitive, drawn, at every width and in both themes.
 * ============================================================================================ */

async function open(page: Page, width: (typeof WIDTHS)[number], theme: 'light' | 'dark'): Promise<void> {
  await page.setViewportSize({ width, height: HEIGHT[width] })
  await page.goto(theme === 'dark' ? `${PAGE}?theme=dark` : PAGE)
  await expect(page.locator('[data-kit-data]')).toBeVisible()
  await settleFonts(page)
}

for (const theme of ['light', 'dark'] as const) {
  for (const width of WIDTHS) {
    test(`every primitive renders at ${width} in ${theme}, with no sideways scroll`, async ({ page }) => {
      await open(page, width, theme)

      for (const name of SPECIMENS) {
        await expect(page.locator(`[data-specimen="${name}"]`), name).toBeVisible()
      }
      await expect(page.locator('[data-specimen]')).toHaveCount(SPECIMENS.length)

      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
      expect(overflow, 'the page scrolls sideways').toBeLessThanOrEqual(0)

      /* Every filter control in one bar is one height. */
      const heights = await page
        .locator('[data-specimen="Filters"] .bn-pick, [data-specimen="Filters"] .bn-fchip-clear, [data-specimen="Sort"] .bn-pick, [data-specimen="Sort"] .bn-sort-dir, [data-specimen="Pick one"] .bn-pick')
        .evaluateAll((els) => els.map((el) => Math.round(el.getBoundingClientRect().height)))
      expect(heights.length).toBeGreaterThanOrEqual(6)
      expect(new Set(heights).size, `heights ${heights.join(', ')}`).toBe(1)
    })
  }
}

test('money is drawn in the mono face everywhere it appears', async ({ page }) => {
  await open(page, 1440, 'light')
  const faces = await page.locator('[data-specimen="Money"] .bn-money').evaluateAll((els) =>
    els.map((el) => getComputedStyle(el).fontFamily),
  )
  expect(faces.length).toBe(5)
  for (const face of faces) expect(face).toContain('JetBrains Mono')
  await expect(page.locator('[data-specimen="Money"]')).toContainText('$66,334.71')
})

test('a separator is drawn, never typed, and a screen reader hears a comma', async ({ page }) => {
  await open(page, 1440, 'light')
  const line = page.locator('[data-specimen="Separator"] .bn-row > span').first()
  const text = await line.evaluate((el) => el.textContent ?? '')
  expect(text).not.toContain('·')
  expect(text).toBe('Obsidian Flames, Near Mint')
  const drawn = await page
    .locator('[data-specimen="Separator"] .bn-sep')
    .evaluate((el) => getComputedStyle(el, '::before').content)
  expect(drawn).toContain('·')
})

test('two printings of one card read differently', async ({ page }) => {
  await open(page, 1440, 'light')
  const lines = page.locator('[data-specimen="Card"] .bn-cardline')
  const first = (await lines.nth(0).textContent()) ?? ''
  const second = (await lines.nth(1).textContent()) ?? ''
  expect(first).toContain('Charizard ex')
  expect(second).toContain('Charizard ex')
  expect(first).not.toBe(second)
  expect(second).toContain('Holofoil')
})

test('a missing photograph is one state at every size', async ({ page }) => {
  await open(page, 1440, 'light')
  const missing = page.locator('[data-specimen="Photo"] .bn-thumb[data-missing="true"]')
  await expect(missing).toHaveCount(3)
  for (const size of ['sm', 'md', 'lg']) {
    await expect(page.locator(`[data-specimen="Photo"] .bn-thumb-${size}[data-missing="true"]`)).toHaveAttribute('aria-label', 'Abra: no photo')
  }
  const grounds = await missing.evaluateAll((els) => els.map((el) => getComputedStyle(el).backgroundColor))
  expect(new Set(grounds).size).toBe(1)
})

test('a product name opens the product page by SKU when no sheet is registered', async ({ page }) => {
  await open(page, 1440, 'light')
  await page.locator('[data-specimen="Links"] a', { hasText: 'Charizard ex' }).click()
  await expect.poll(() => page.evaluate(() => window.location.hash)).toBe('#/product?sku=8607411')
})

test('a pick list is the kit panel, never the native menu, and it picks by keyboard', async ({ page }) => {
  await open(page, 1440, 'light')
  await expect(page.locator('select')).toHaveCount(0)

  const game = page.locator('[data-specimen="Pick one"] .bn-pick').first()
  await expect(game).toContainText('Pokémon')
  await game.click()
  const list = page.getByRole('listbox', { name: 'Game' })
  await expect(list).toBeVisible()
  await expect(list.getByRole('option')).toHaveCount(3)
  await expect(list.getByRole('option', { name: /Pokémon/ })).toHaveAttribute('aria-selected', 'true')

  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await expect(list).toBeHidden()
  await expect(game).toContainText('Riftbound')
  await expect(game).toBeFocused()

  await game.click()
  await expect(list).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(list).toBeHidden()
  await expect(game).toBeFocused()
})

test('filters combine in any order, and the count says what they hide', async ({ page }) => {
  await open(page, 1440, 'light')
  const bar = page.locator('[data-specimen="Filters"]')
  const count = page.locator('[data-specimen="Filtered count"] .bn-filtercount')

  await expect(count).toContainText('37 of 122 cards, filtered by Pokémon')

  /* Rarity FIRST, before Set, with Game already on: no facet waits on another. */
  await bar.locator('.bn-pick', { hasText: 'Rarity' }).click()
  const rarity = page.getByRole('listbox', { name: 'Rarity' })
  await expect(rarity).toBeVisible()
  /* A long list gets the type-to-narrow entry. */
  await page.getByRole('textbox', { name: 'Narrow Rarity' }).fill('holo')
  await expect(rarity.getByRole('option')).toHaveCount(1)
  await rarity.getByRole('option', { name: /Holo Rare/ }).click()
  await expect(rarity.getByRole('option', { name: /Holo Rare/ })).toHaveAttribute('aria-selected', 'true')
  await page.keyboard.press('Escape')

  await bar.locator('.bn-pick', { hasText: 'Set' }).click()
  await page.getByRole('listbox', { name: 'Set' }).getByRole('option', { name: /Origins/ }).click()
  await page.keyboard.press('Escape')

  await expect(bar.locator('.bn-fchip[data-active="true"]')).toHaveCount(3)
  await expect(count).toContainText('filtered by Pokémon, Holo Rare and Origins')

  await bar.getByRole('button', { name: 'Clear Game' }).click()
  await expect(bar.locator('.bn-fchip[data-active="true"]')).toHaveCount(2)

  await bar.getByRole('button', { name: 'Clear all' }).click()
  await expect(bar.locator('.bn-fchip[data-active="true"]')).toHaveCount(0)
  await expect(count).toHaveText('122 cards')
})

test('the sort control says what it sorts by and which way, and reverses', async ({ page }) => {
  await open(page, 1440, 'light')
  const sort = page.locator('[data-specimen="Sort"]')
  await expect(sort.locator('.bn-pick')).toContainText('Captured')
  await expect(sort.locator('.bn-sort-dir')).toHaveText('Newest first')
  await sort.locator('.bn-sort-dir').click()
  await expect(sort.locator('.bn-sort-dir')).toHaveText('Oldest first')
  await sort.locator('.bn-pick').click()
  await page.getByRole('listbox', { name: 'Sort' }).getByRole('option', { name: 'Name' }).click()
  await expect(sort.locator('.bn-sort-dir')).toHaveText('A to Z')
})

test('an empty search press says what to type, and moves nothing below it', async ({ page }) => {
  await open(page, 1440, 'light')
  const search = page.locator('[data-specimen="Search"]')
  const before = (await search.boundingBox())?.height

  await search.getByRole('button', { name: 'Find' }).click()
  await expect(search.getByRole('status')).toHaveText('Type a card name, number or SKU first.')
  expect((await search.boundingBox())?.height).toBe(before)

  await search.getByRole('searchbox').fill('054/132')
  await expect(search.getByRole('status')).toHaveText('')
  await search.getByRole('searchbox').press('Enter')
  await expect(search.locator('[data-submitted]')).toHaveText('054/132')
})
