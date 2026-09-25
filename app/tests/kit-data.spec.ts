import { test, expect, type Page } from '@playwright/test'

import { sealEveryTest } from './shell'
import { settleFonts } from './fontsReady'
import { canonicalNumber, compactText, foldText, matchQuery, queryTokens } from '../src/kit/match'
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

  test("a box's name, a SKU and a condition word each find the row", () => {
    expect(matchQuery('mixed', abra)).toBe(true)
    expect(matchQuery('mixed singles', abra)).toBe(true)
    expect(matchQuery('860123', abra)).toBe(true)
    expect(matchQuery('near mint', abra)).toBe(true)
    expect(matchQuery('damaged', { text: ['Boss’s Orders', 'Damaged'] })).toBe(true)
    expect(matchQuery('boss orders', { text: ['Boss’s Orders'] })).toBe(true)
  })

  test('an order label is found by what the row draws', () => {
    expect(matchQuery('09-03-26_00012', { text: ['09-03-26_00012'] })).toBe(true)
    expect(matchQuery('09-03-26', { text: ['09-03-26_00012'] })).toBe(true)
  })

  /* The reviewer's probes, 2026-09-23. Every card below is in a box, so a digit that falls back
   * to a box's number is caught. */
  const inBox = (box: number, text: string[], numbers: string[] = [], name = 'Mixed Singles') => ({
    text,
    numbers,
    skus: ['7700001'],
    boxes: [{ box, name }],
  })

  test('a digit never finds a box by its number', () => {
    expect(matchQuery('54', inBox(154, ['Pikachu'], ['001/100']))).toBe(false)
    expect(matchQuery('4', inBox(14, ['Pikachu'], ['010/100']))).toBe(false)
    expect(matchQuery('4', inBox(41, ['Pikachu'], ['010/100']))).toBe(false)
    expect(matchQuery('box 4', inBox(14, ['Pikachu']))).toBe(false)
    expect(matchQuery('box 4', inBox(41, ['Pikachu']))).toBe(false)
    expect(matchQuery('#12', inBox(112, ['Pikachu'], ['001/100']))).toBe(false)
    /* A box is found by its NAME only (the owner's ruling, 2026-09-23): box 4 named `Mixed
       Singles` is not found by its number in any spelling. */
    expect(matchQuery('4', inBox(4, ['Pikachu'], ['010/100']))).toBe(false)
    expect(matchQuery('B4', inBox(4, ['Pikachu'], ['010/100']))).toBe(false)
    expect(matchQuery('box4', inBox(4, ['Pikachu']))).toBe(false)
    expect(matchQuery('box 4', inBox(4, ['Pikachu']))).toBe(false)
    expect(matchQuery('mixed', inBox(4, ['Pikachu']))).toBe(true)
    /* An unnamed box carries the stored name `Box 4`, and that name is text. */
    expect(matchQuery('box 4', inBox(4, ['Pikachu'], [], 'Box 4'))).toBe(true)
    expect(matchQuery('box 4', inBox(14, ['Pikachu'], [], 'Box 14'))).toBe(false)
    expect(matchQuery('#12', inBox(112, ['Pikachu'], ['012/100']))).toBe(true)
    /* A digit word in text is a whole word or the START of one, zeros ignored: `12` finds
       `00012`, never `112`; `0001` finds `00012` while an order label is typed. */
    expect(matchQuery('12', inBox(3, ['Order 112']))).toBe(false)
    expect(matchQuery('12', inBox(3, ['09-03-26_00012']))).toBe(true)
    expect(matchQuery('0001', inBox(3, ['09-03-26_00012']))).toBe(true)
    expect(matchQuery('12', inBox(3, ['Order 123']))).toBe(true)
    expect(matchQuery('09-03-26_1', inBox(3, ['09-03-26_00012']))).toBe(true)
    /* The first key of an order label is a zero, and it must not empty the list. */
    expect(matchQuery('0', inBox(3, ['09-03-26_00012']))).toBe(true)
    expect(matchQuery('00', inBox(3, ['09-03-26_00012']))).toBe(true)
    expect(matchQuery('0', inBox(3, ['Order 112']))).toBe(false)
    expect(matchQuery('09-03-26_0001', inBox(3, ['09-03-26_00012']))).toBe(true)
    expect(matchQuery('09-03-26_0002', inBox(3, ['09-03-26_00012']))).toBe(false)
    expect(matchQuery('09-03-27', inBox(3, ['09-03-26_00012']))).toBe(false)
    const order = inBox(3, ['A2FFC195-000001-00007'])
    expect(matchQuery('A2FFC195-000001-0000', order)).toBe(true)
    expect(matchQuery('a2ffc195-000001', order)).toBe(true)
    expect(matchQuery('a2ffc195-00000', order)).toBe(true)
    expect(matchQuery('A2FFC195-000002', order)).toBe(false)
    expect(matchQuery('A2FFC195-000001-00008', order)).toBe(false)
  })

  test('an apostrophe or a hyphen never splits a word the query runs together', () => {
    expect(matchQuery('farfetchd', inBox(2, ["Farfetch'd"]))).toBe(true)
    expect(matchQuery('farfetchd', inBox(2, ['Farfetch’d']))).toBe(true)
    expect(matchQuery('professors research', inBox(2, ["Professor's Research"]))).toBe(true)
    expect(matchQuery('hooh', inBox(2, ['Ho-Oh ex']))).toBe(true)
    expect(matchQuery('porygonz', inBox(2, ['Porygon-Z']))).toBe(true)
    expect(matchQuery('ho-oh', inBox(2, ['Ho-Oh ex']))).toBe(true)
    expect(matchQuery('hooh', inBox(2, ['Hoothoot']))).toBe(false)
    expect(matchQuery('porygonz', inBox(2, ['Porygon2']))).toBe(false)
    expect(compactText('Ho-Oh ex')).toBe('hoohex')
    /* The fold itself, which any search that must agree with this one copies. */
    expect(foldText("Farfetch'd")).toBe('farfetchd')
    expect(foldText('Professor\u2019s Research')).toBe('professors research')
  })

  test('a card number split by a space, a hyphen or a slash still finds the card', () => {
    const abra4 = inBox(4, ['Abra'], ['054/132'])
    const swsh = inBox(4, ['Pikachu'], ['SWSH050'])
    expect(matchQuery('swsh 050', swsh)).toBe(true)
    expect(matchQuery('swsh 051', swsh)).toBe(false)
    expect(matchQuery('54 132', abra4)).toBe(true)
    expect(matchQuery('54 131', abra4)).toBe(false)
    expect(matchQuery('054-132', abra4)).toBe(true)
    expect(matchQuery('054-131', abra4)).toBe(false)
    expect(matchQuery('/132', abra4)).toBe(true)
    expect(matchQuery('/131', abra4)).toBe(false)
    expect(matchQuery('/132', inBox(132, ['Abra'], ['054/200']))).toBe(false)
    expect(matchQuery('５４', abra4)).toBe(true)
    expect(matchQuery('５４／１３２', abra4)).toBe(true)
    expect(matchQuery('５５', abra4)).toBe(false)
    expect(matchQuery('abra 54 132', abra4)).toBe(true)
    expect(matchQuery('OP01-001', inBox(4, ['Luffy'], ['OP01-001']))).toBe(true)
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

test('a box is drawn by its name and never by its number', async ({ page }) => {
  await open(page, 1440, 'light')
  const boxes = page.locator('[data-specimen="Box"] .bn-boxlabel')
  await expect(boxes).toHaveText(['RB Epics', 'Mixed Singles', 'Unnamed box'])
  await expect(page.locator('[data-specimen="Box"]')).not.toContainText(/Box \d/)
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
  const gameValue = game.locator('.bn-pick-value')
  await expect(gameValue).toHaveText('Pokémon')
  await game.click()
  const list = page.getByRole('listbox', { name: 'Game' })
  await expect(list).toBeVisible()
  await expect(list.getByRole('option')).toHaveCount(3)
  await expect(list.getByRole('option', { name: /Pokémon/ })).toHaveAttribute('aria-selected', 'true')

  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await expect(list).toBeHidden()
  await expect(gameValue).toHaveText('Riftbound')
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
  await expect(sort.locator('.bn-pick-value')).toHaveText('Captured')
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

  /* A STANDALONE SearchField (no `controlHeight="bar"`) reads at its own 14px
   *  (`--bn-fs-base`), UNCHANGED by FilterBar's 13px bar-only rule (`SearchField.css:
   *  .search-field-bar .search-field-input`, filtering round 3). */
  await expect(search.locator('.search-field-input')).toHaveCSS('font-size', '14px')

  await search.getByRole('button', { name: 'Find' }).click()
  await expect(search.getByRole('status')).toHaveText('Type a card name, number or SKU first.')
  expect((await search.boundingBox())?.height).toBe(before)

  await search.getByRole('searchbox').fill('054/132')
  await expect(search.getByRole('status')).toHaveText('')
  await search.getByRole('searchbox').press('Enter')
  await expect(search.locator('[data-submitted]')).toHaveText('054/132')
})

/* ============================================================================================
 * Focus: every press leaves focus on something stable.
 * ============================================================================================ */

test('Tab from an open list goes back to its trigger, and the next Tab reaches the next control', async ({ page }) => {
  await open(page, 1440, 'light')
  const bar = page.locator('[data-specimen="Filters"]')
  const rarity = bar.locator('.bn-pick', { hasText: 'Rarity' })
  await rarity.click()
  await expect(page.getByRole('textbox', { name: 'Narrow Rarity' })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(page.getByRole('listbox', { name: 'Rarity' })).toBeHidden()
  await expect(rarity).toBeFocused()

  /* A short list, with the list itself focused. */
  const set = bar.locator('.bn-pick', { hasText: 'Set' })
  await set.click()
  await expect(page.getByRole('listbox', { name: 'Set' })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(set).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(rarity).toBeFocused()
})

test('a facet is picked and cleared from the keyboard alone, and the list holds no Clear', async ({ page }) => {
  await open(page, 1440, 'light')
  const bar = page.locator('[data-specimen="Filters"]')
  const set = bar.locator('.bn-pick', { hasText: 'Set' })
  await set.focus()
  await page.keyboard.press('ArrowDown')
  const list = page.getByRole('listbox', { name: 'Set' })
  await expect(list).toBeFocused()
  /* The one way to clear a facet is its own x beside the trigger: the list has no Clear. */
  await expect(page.locator('[data-bn-pick-panel] button')).toHaveCount(0)
  await page.keyboard.press('Enter')
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('Enter')
  await expect(list.getByRole('option', { selected: true })).toHaveCount(2)
  await page.keyboard.press('Tab')
  await expect(list).toBeHidden()
  await expect(set).toBeFocused()
  /* The next Tab reaches the facet's clear press, and Enter on it clears the facet. */
  await page.keyboard.press('Tab')
  const clear = bar.getByRole('button', { name: 'Clear Set' })
  await expect(clear).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(bar.locator('.bn-fchip').nth(1)).not.toHaveAttribute('data-active', 'true')
  await expect(set).toBeFocused()
  await expect(set.locator('.bn-pick-value')).toHaveText('Any')
})

test('Clear all and the count line Clear leave focus on something that stays', async ({ page }) => {
  await open(page, 1440, 'light')
  const bar = page.locator('[data-specimen="Filters"]')
  await bar.locator('.bn-pick', { hasText: 'Set' }).click()
  await page.getByRole('listbox', { name: 'Set' }).getByRole('option', { name: /Origins/ }).click()
  await page.keyboard.press('Escape')
  await bar.getByRole('button', { name: 'Clear all' }).click()
  await expect(bar.locator('.bn-pick').first()).toBeFocused()
  await expect(bar.locator('.bn-fchip[data-active="true"]')).toHaveCount(0)

  await bar.locator('.bn-pick', { hasText: 'Set' }).click()
  await page.getByRole('listbox', { name: 'Set' }).getByRole('option', { name: /Origins/ }).click()
  await page.keyboard.press('Escape')
  const count = page.locator('[data-specimen="Filtered count"] .bn-filtercount')
  await count.getByRole('button', { name: 'Clear' }).click()
  await expect(count).toBeFocused()
  await expect(count).toHaveText('122 cards')
})

/* ============================================================================================
 * D118: a pick moves nothing.
 * ============================================================================================ */

for (const width of [1440, 390] as const) {
  test(`a pick, a second pick and a clear move no filter in the bar at ${width}`, async ({ page }) => {
    await open(page, width, 'light')
    const bar = page.locator('[data-specimen="Filters"]')
    /* The filters, the count line under them, and the Sort control under that. */
    const rects = () =>
      page
        .locator('[data-specimen="Filters"] .bn-fchip, [data-specimen="Filters"] .bn-filterchips-clear, [data-specimen="Filtered count"], [data-specimen="Sort"] .bn-sort')
        .evaluateAll((els) =>
        els.map((el) => {
          const r = el.getBoundingClientRect()
          /* Page coordinates: opening a list may scroll the page to show it, and a scroll is
             not a move. */
          return [Math.round(r.x + window.scrollX), Math.round(r.y + window.scrollY), Math.round(r.width), Math.round(r.height)]
        }),
      )
    const start = await rects()
    expect(start.length).toBe(6)

    /* Three picks, which made the count line wrap before it was held to one line. */
    await bar.locator('.bn-pick', { hasText: 'Set' }).click()
    await page.getByRole('listbox', { name: 'Set' }).getByRole('option', { name: /Scarlet/ }).click()
    await page.getByRole('listbox', { name: 'Set' }).getByRole('option', { name: /Obsidian/ }).click()
    await page.keyboard.press('Escape')
    await bar.locator('.bn-pick', { hasText: 'Rarity' }).click()
    await page.getByRole('listbox', { name: 'Rarity' }).getByRole('option', { name: /Special Illustration Rare/ }).click()
    await page.keyboard.press('Escape')
    await expect(bar.locator('.bn-fchip[data-active="true"]')).toHaveCount(3)
    await expect(page.locator('[data-specimen="Filtered count"] .bn-filtercount-text')).toHaveAttribute(
      'title',
      '37 of 122 cards, filtered by Pokémon, Scarlet & Violet, Obsidian Flames and Special Illustration Rare',
    )
    expect(await rects(), 'a pick moved a filter, the count line or Sort').toEqual(start)

    await bar.getByRole('button', { name: 'Clear Game' }).click()
    expect(await rects(), 'a clear moved a filter').toEqual(start)
  })
}

for (const width of [390, 720] as const) {
  test(`the count line's words stay put when its Clear comes and goes at ${width}`, async ({ page }) => {
    await open(page, width, 'light')
    const bar = page.locator('[data-specimen="Filters"]')
    const count = page.locator('[data-specimen="Filtered count"] .bn-filtercount')
    const words = () =>
      count.locator('.bn-filtercount-text').evaluate((el) => {
        const r = el.getBoundingClientRect()
        return [Math.round((r.y + window.scrollY) * 10) / 10, Math.round(r.height * 10) / 10]
      })
    const line = () => count.evaluate((el) => Math.round(el.getBoundingClientRect().height * 10) / 10)

    /* One filter on, so the Clear press is drawn. */
    await expect(count.getByRole('button', { name: 'Clear' })).toBeVisible()
    const one = await words()
    const oneLine = await line()

    /* One to zero: the press goes. */
    await bar.getByRole('button', { name: 'Clear Game' }).click()
    await expect(count.getByRole('button', { name: 'Clear' })).toHaveCount(0)
    expect(await words(), 'the words moved when the Clear press went').toEqual(one)
    expect(await line()).toBe(oneLine)

    /* Zero to one: the press comes back. */
    await bar.locator('.bn-pick', { hasText: 'Game' }).click()
    await page.getByRole('listbox', { name: 'Game' }).getByRole('option', { name: /Riftbound/ }).click()
    await expect(count.getByRole('button', { name: 'Clear' })).toBeVisible()
    expect(await words(), 'the words moved when the Clear press came').toEqual(one)
    expect(await line()).toBe(oneLine)
  })
}

/* ============================================================================================
 * The thumb floor, and the contrast of the words the primitives draw.
 * ============================================================================================ */

test('every kit-data control a thumb presses is 40px tall at 390', async ({ page }) => {
  await open(page, 390, 'light')
  const bar = page.locator('[data-specimen="Filters"]')
  await bar.locator('.bn-pick', { hasText: 'Set' }).click()
  await page.getByRole('listbox', { name: 'Set' }).getByRole('option', { name: /Origins/ }).click()
  await page.keyboard.press('Escape')
  const sizes = await page
    .locator(
      '[data-kit-data] .bn-pick, [data-kit-data] .bn-fchip-clear, [data-kit-data] .bn-filterchips-clear, ' +
        '[data-kit-data] .bn-sort-dir, [data-kit-data] .bn-filtercount-clear, [data-kit-data] .bn-datalink, ' +
        '[data-kit-data] .search-field-submit, [data-kit-data] .search-field-clear',
    )
    .evaluateAll((els) =>
      els
        .filter((el) => getComputedStyle(el).visibility !== 'hidden')
        .map((el) => {
          const r = el.getBoundingClientRect()
          return { name: el.className, h: Math.round(r.height), w: Math.round(r.width) }
        }),
    )
  expect(sizes.length).toBeGreaterThanOrEqual(9)
  for (const size of sizes) {
    expect(size.h, `${size.name} is ${size.w}x${size.h}`).toBeGreaterThanOrEqual(40)
    expect(size.w, `${size.name} is ${size.w}x${size.h}`).toBeGreaterThanOrEqual(40)
  }
})

/** The WCAG contrast of an element's text against the ground under it, both read from the
 *  computed style of the element and its first painted ancestor, alpha composited in order. */
async function contrastOf(page: Page, selector: string): Promise<number> {
  /* Every running transition finishes first. A ground read mid-fade is lighter than the one
     that stays, and it reads a pass that is not there. */
  await page.evaluate(() => Promise.all(document.getAnimations().map((one) => one.finished.catch(() => undefined))))
  return page.locator(selector).first().evaluate((el) => {
    const parse = (value: string): number[] => {
      const m = value.match(/rgba?\(([^)]+)\)/)
      if (m === null) return [0, 0, 0, 0]
      const parts = (m[1] ?? '').match(/[\d.]+/g)?.map(Number) ?? []
      return [parts[0] ?? 0, parts[1] ?? 0, parts[2] ?? 0, parts[3] ?? 1]
    }
    const over = (top: number[], under: number[]): number[] => {
      const a = top[3] ?? 1
      return [0, 1, 2].map((i) => (top[i] ?? 0) * a + (under[i] ?? 0) * (1 - a)).concat(1)
    }
    const layers: number[][] = []
    for (let node: Element | null = el; node !== null; node = node.parentElement) {
      const bg = parse(getComputedStyle(node).backgroundColor)
      if ((bg[3] ?? 0) > 0) layers.push(bg)
      if ((bg[3] ?? 0) >= 1) break
    }
    let ground = [255, 255, 255, 1]
    for (const layer of layers.reverse()) ground = over(layer, ground)
    const ink = over(parse(getComputedStyle(el).color), ground)
    const lum = (c: number[]) => {
      const [r, g, b] = [0, 1, 2].map((i) => {
        const v = (c[i] ?? 0) / 255
        return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
      })
      return 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (b ?? 0)
    }
    const [hi, lo] = [lum(ink), lum(ground)].sort((x, y) => y - x)
    return ((hi ?? 0) + 0.05) / ((lo ?? 0) + 0.05)
  })
}

for (const theme of ['light', 'dark'] as const) {
  test(`every field edge reads 3:1 against the page in ${theme}`, async ({ page }) => {
    await open(page, 1440, theme)
    const edges = await page
      .locator('[data-kit-data] .bn-pick:not([data-active]), [data-kit-data] .bn-sort-dir, [data-kit-data] .search-field-box')
      .evaluateAll((els) => {
        const parse = (v: string): number[] => {
          const n = (v.match(/[\d.]+/g) ?? []).map(Number)
          return [n[0] ?? 0, n[1] ?? 0, n[2] ?? 0, n[3] ?? 1]
        }
        const over = (t: number[], u: number[]): number[] =>
          [0, 1, 2].map((i) => (t[i] ?? 0) * (t[3] ?? 1) + (u[i] ?? 0) * (1 - (t[3] ?? 1))).concat(1)
        const lum = (c: number[]): number => {
          const [r, g, b] = [0, 1, 2].map((i) => {
            const v = (c[i] ?? 0) / 255
            return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
          })
          return 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (b ?? 0)
        }
        return els.filter((el) => (el as HTMLElement).closest('.bn-fchip[data-active="true"]') === null).map((el) => {
          /* The ground OUTSIDE the edge: the first painted ancestor above the field. */
          const layers: number[][] = []
          for (let node = el.parentElement; node !== null; node = node.parentElement) {
            const bg = parse(getComputedStyle(node).backgroundColor)
            if (getComputedStyle(node).backgroundColor !== 'rgba(0, 0, 0, 0)') layers.push(bg)
            if ((bg[3] ?? 0) >= 1 && getComputedStyle(node).backgroundColor !== 'rgba(0, 0, 0, 0)') break
          }
          let ground = [255, 255, 255, 1]
          for (const layer of layers.reverse()) ground = over(layer, ground)
          const edge = over(parse(getComputedStyle(el).borderTopColor), ground)
          const [hi, lo] = [lum(edge), lum(ground)].sort((x, y) => y - x)
          return { name: el.className, ratio: ((hi ?? 0) + 0.05) / ((lo ?? 0) + 0.05) }
        })
      })
    expect(edges.length).toBeGreaterThanOrEqual(5)
    for (const edge of edges) expect(edge.ratio, `${edge.name} edge ${edge.ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(3)
  })

  test(`the words the primitives draw reach 4.5:1 in ${theme}`, async ({ page }) => {
    await open(page, 1440, theme)
    /* The active filter's label, on its tint over the page. */
    expect(await contrastOf(page, '[data-specimen="Filters"] .bn-fchip[data-active="true"] .bn-pick-label')).toBeGreaterThanOrEqual(4.5)
    /* The `+N` on an active filter, once a facet holds two picks. */
    await page.locator('[data-specimen="Filters"] .bn-pick', { hasText: 'Set' }).click()
    await page.getByRole('listbox', { name: 'Set' }).getByRole('option', { name: /Scarlet/ }).click()
    await page.getByRole('listbox', { name: 'Set' }).getByRole('option', { name: /Origins/ }).click()
    await page.keyboard.press('Escape')
    expect(await contrastOf(page, '[data-specimen="Filters"] .bn-pick-value .bn-fchip-more')).toBeGreaterThanOrEqual(4.5)
    /* The empty money figure. */
    expect(await contrastOf(page, '[data-specimen="Money"] .bn-money[data-empty="true"]')).toBeGreaterThanOrEqual(4.5)
    /* A choice with a count of 0, at rest and under the pointer. */
    await page.locator('[data-specimen="Filters"] .bn-pick', { hasText: 'Game' }).click()
    const zero = '[data-bn-pick-panel] .bn-pick-opt[data-zero="true"]'
    expect(await contrastOf(page, zero)).toBeGreaterThanOrEqual(4.5)
    await page.locator(zero).hover()
    await expect(page.locator(zero)).toHaveAttribute('data-active', 'true')
    expect(await contrastOf(page, zero)).toBeGreaterThanOrEqual(4.5)
  })
}

test('at 390 the filters stack one a row, all one width (D195)', async ({ page }) => {
  await open(page, 390, 'light')
  const widths = await page
    .locator('[data-specimen="Filters"] .bn-fchip')
    .evaluateAll((els) => els.map((el) => Math.round(el.getBoundingClientRect().width)))
  expect(widths.length).toBe(3)
  expect(new Set(widths).size, `widths ${widths.join(', ')}`).toBe(1)
})
