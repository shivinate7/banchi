import { createRequire } from 'node:module'

import { test, expect, type Page } from '@playwright/test'

import { sealEveryTest } from './shell'
import { settleFonts } from './fontsReady'
import { settleMotion } from './motionSettled'
import { matchSpans } from '../src/kit/highlight'
import { countFacets, filterRows, withCounts } from '../src/kit/facets'
import { parseViewQuery, readFacets, readFlag, readSort, writeFlag } from '../src/kit/viewState'
import type { FilterFacet } from '../src/kit/data'

/* THE FILTER BAR, THE HIDE TOGGLE, THE SORTABLE TABLE HEADER AND THE MATCH HIGHLIGHT
 * (`kit/filters.tsx`, `kit/highlight.tsx`, `kit/facets.ts`), drawn on `tests/filters/index.html`
 * — a page with no router, no store and no server, the same shape `kit-data.spec.ts` already
 * draws its own specimens on. `match.spec.ts` covers `kit/match.ts` itself; this file covers
 * what is built on top of it: the URL view state (`kit/viewState.ts`), the facet counts, and the
 * composed controls.
 *
 * Each guard below went red on its own defect before the fix (the filtering review, round 2). */

sealEveryTest()

/* ============================================================================================
 * Pure functions: no browser.
 * ============================================================================================ */

test.describe('the URL is read as untrusted', () => {
  test('a flag whose default is on can be turned off, and stays off (Hide sold, D132)', () => {
    expect(writeFlag(false, true)).toBe('0')
    expect(readFlag(writeFlag(false, true), true)).toBe(false)
    expect(writeFlag(true, true)).toBeNull()
    expect(writeFlag(true, false)).toBe('1')
    expect(writeFlag(false, false)).toBeNull()
    expect(readFlag('yes', true)).toBe(true)
    expect(readFlag(null, false)).toBe(false)
  })

  test('a malformed escape is ignored, and the pairs around it are kept', () => {
    const query = parseViewQuery('q=%E0%A4%A&game=pokemon&set=sv%201')
    expect(query.get('q')).toBeNull()
    expect(query.get('game')).toBe('pokemon')
    expect(query.get('set')).toBe('sv 1')
  })

  test('a facet keeps only known values, once each, and a single-choice facet keeps one', () => {
    const facets: FilterFacet[] = [
      { key: 'game', label: 'Game', options: [{ value: 'pokemon', label: 'Pokémon' }, { value: 'riftbound', label: 'Riftbound' }] },
      { key: 'set', label: 'Set', multiple: false, options: [{ value: 'sv1', label: 'One' }, { value: 'sv3', label: 'Three' }] },
    ]
    const value = readFacets(parseViewQuery('game=pokemon&game=bogus&game=pokemon&game=riftbound&set=nope&set=sv3&set=sv1&other=x'), facets)
    expect(value).toEqual({ game: ['pokemon', 'riftbound'], set: ['sv3'] })
  })

  test('a sort key no option has falls back to the default, and a bad direction to the key\'s own first', () => {
    const options = [
      { key: 'name', label: 'Name', first: 'asc' as const },
      { key: 'price', label: 'Price' },
    ]
    const rest = { key: 'price' as const, dir: 'desc' as const }
    expect(readSort('nope', 'asc', rest, options)).toEqual(rest)
    expect(readSort('name', 'sideways', rest, options)).toEqual({ key: 'name', dir: 'asc' })
    expect(readSort('name', 'desc', rest, options)).toEqual({ key: 'name', dir: 'desc' })
    expect(readSort(null, null, rest, options)).toEqual(rest)
  })

  test('an absent sort key still reads a written direction, against the DEFAULT\'s own key (the reversed-default regression, filtering round 3: reversing the resting column wrote only `?dir=`, and readSort ignored it because the key was absent)', () => {
    const options = [
      { key: 'name', label: 'Name', first: 'asc' as const },
      { key: 'price', label: 'Price' },
    ]
    const def = { key: 'name' as const, dir: 'asc' as const }
    expect(readSort(null, 'desc', def, options)).toEqual({ key: 'name', dir: 'desc' })
    expect(readSort(null, 'asc', def, options)).toEqual(def)
    expect(readSort(null, null, def, options)).toEqual(def)
  })
})

test.describe('facet counts', () => {
  const rows = [
    { game: 'pokemon', rarity: 'rare' },
    { game: 'pokemon', rarity: 'common' },
    { game: 'pokemon', rarity: 'common' },
    { game: 'riftbound', rarity: 'rare' },
    { game: 'riftbound', rarity: 'common' },
  ]
  const facets: FilterFacet[] = [
    { key: 'game', label: 'Game', options: [{ value: 'pokemon', label: 'Pokémon' }, { value: 'riftbound', label: 'Riftbound' }, { value: 'onepiece', label: 'One Piece' }] },
    { key: 'rarity', label: 'Rarity', options: [{ value: 'common', label: 'Common' }, { value: 'rare', label: 'Rare' }] },
  ]
  const valueOf = (row: (typeof rows)[number], key: string) => (key === 'game' ? row.game : key === 'rarity' ? row.rarity : null)
  const countsOf = (facet: FilterFacet | undefined) => Object.fromEntries((facet?.options ?? []).map((one) => [one.value, one.count]))

  test('an option counts under the OTHER active filters: a change in one facet changes another\'s counts, never its own', () => {
    const open = countFacets(rows, facets, {}, valueOf)
    expect(countsOf(open[1])).toEqual({ common: 3, rare: 2 })

    const picked = countFacets(rows, facets, { game: ['riftbound'] }, valueOf)
    expect(countsOf(picked[1])).toEqual({ common: 1, rare: 1 })
    /* Game's own counts do not move when Game is picked: each says what picking it would show. */
    expect(countsOf(picked[0])).toEqual({ pokemon: 3, riftbound: 2, onepiece: 0 })

    const both = countFacets(rows, facets, { game: ['riftbound'], rarity: ['rare'] }, valueOf)
    expect(countsOf(both[0])).toEqual({ pokemon: 1, riftbound: 1, onepiece: 0 })
    expect(filterRows(rows, facets, { game: ['riftbound'], rarity: ['rare'] }, valueOf)).toHaveLength(1)
  })

  test('several picks in one facet are OR, and a screen\'s own `keep` narrows every count', () => {
    expect(filterRows(rows, facets, { game: ['pokemon', 'riftbound'] }, valueOf)).toHaveLength(5)
    const kept = countFacets(rows, facets, {}, valueOf, (row) => row.rarity === 'common')
    expect(countsOf(kept[0])).toEqual({ pokemon: 2, riftbound: 1, onepiece: 0 })
  })

  test('server counts copy onto the options, and an option the server did not name is zero', () => {
    const out = withCounts(facets, { game: { pokemon: 40 } })
    expect(countsOf(out[0])).toEqual({ pokemon: 40, riftbound: 0, onepiece: 0 })
  })
})

test.describe('matchSpans', () => {
  test('marks a direct hit, and the compact fallback a hyphen or comma cannot break', () => {
    expect(matchSpans('Hextech', 'hextech')).toEqual([[0, 7]])
    expect(matchSpans('Heimerdinger, Inventor', 'heimerdinger-inventor')).toEqual([[0, 22]])
    expect(matchSpans('Ho-Oh ex', 'zzzz')).toEqual([])
  })

  test('marks nothing on a row the matcher refuses, even where one word is in the text', () => {
    expect(matchSpans('Pikachu ex', 'pika zzzz')).toEqual([])
    /* The same word, on a row whose OTHER field carries the second token, is marked. */
    expect(matchSpans('Pikachu ex', 'pika 8607', { row: { text: ['Pikachu ex'], skus: ['8607411'] } })).toEqual([[0, 4]])
    expect(matchSpans('Pikachu ex', 'pika 9999', { row: { text: ['Pikachu ex'], skus: ['8607411'] } })).toEqual([])
  })

  test('marks a card number by its canonical form, never as a substring', () => {
    expect(matchSpans('054/132', '54/132', { kind: 'number' })).toEqual([[0, 7]])
    expect(matchSpans('054/132', '54', { kind: 'number' })).toEqual([[0, 3]])
    expect(matchSpans('054/132', '/132', { kind: 'number' })).toEqual([[4, 7]])
    expect(matchSpans('054/132', '54 132', { kind: 'number' })).toEqual([[0, 7]])
    expect(matchSpans('054/132', '054-132', { kind: 'number' })).toEqual([[0, 7]])
    expect(matchSpans('154/200', '54', { kind: 'number' })).toEqual([])
  })
})

/* ============================================================================================
 * The page.
 * ============================================================================================ */

const PAGE = '/tests/filters/index.html'
const WIDTHS = [1440, 820, 720, 390] as const
const HEIGHT: Record<(typeof WIDTHS)[number], number> = { 1440: 900, 820: 1180, 720: 1000, 390: 900 }

const SPECIMENS = ['FilterBar', 'Rail', 'HideToggle', 'SortHeader', 'Highlight'] as const

async function open(page: Page, width: (typeof WIDTHS)[number], theme: 'light' | 'dark' = 'light', hash = ''): Promise<void> {
  await page.setViewportSize({ width, height: HEIGHT[width] })
  await page.goto(`${theme === 'dark' ? `${PAGE}?theme=dark` : PAGE}${hash}`)
  await expect(page.locator('[data-kit-filters]')).toBeVisible()
  await settleFonts(page)
}

const BAR = '[data-specimen="FilterBar"]'
const RAIL = '[data-specimen-rail]'
const POPOVER = '[data-bn-overlay="popover"]'
const SHEET = '[data-bn-overlay="sheet"]'

/** Opens `scope`'s "Filters" trigger and waits for its overlay (D270's
 *  amendment: one line, at every width — the trigger is the only way to reach a facet, the
 *  sort or the hide toggle now, and its `compact` prop picks a `Popover` or a `Sheet`). */
async function openTrigger(page: Page, scope: string, kind: 'popover' | 'sheet' = 'popover') {
  await page.locator(`${scope} .bn-filterbar-trigger`).click()
  const overlay = page.locator(kind === 'popover' ? POPOVER : SHEET)
  await expect(overlay).toBeVisible()
  /* THE POPOVER POPS IN (`.bn-menu`'s `bn-pop` animation, kit.css). A height or width read
   *  inside that window is a real, transient frame, not noise (`motionSettled.ts`'s own
   *  argument) — measured here too: every control inside the panel read 1px short of the
   *  search field beside it until this wait was added. */
  await settleMotion(page)
  return overlay
}

for (const theme of ['light', 'dark'] as const) {
  for (const width of WIDTHS) {
    test(`every specimen renders at ${width} in ${theme}, with no sideways scroll`, async ({ page }) => {
      await open(page, width, theme)

      for (const name of SPECIMENS) {
        await expect(page.locator(`[data-specimen="${name}"]`), name).toBeVisible()
      }
      await expect(page.locator('[data-kit-filters] > [data-specimen]')).toHaveCount(SPECIMENS.length)

      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
      expect(overflow, 'the page scrolls sideways').toBeLessThanOrEqual(0)
    })
  }
}

/* ============================================================================================
 * FilterBar
 * ============================================================================================ */

test.describe('FilterBar', () => {
  /* ONE LINE, AT EVERY WIDTH (D270's amendment, 2026-09-24): there is no wide
   *  row any more. `BAR`'s own trigger (default `compact="popover"`) opens a `Popover` at
   *  every width, 1440 down to 390 — never a container query. The search field stays outside
   *  the popover, in the bar's own line; the facets, the sort and the hide toggle live inside
   *  it. The trigger is sized to the field beside it (the orders lane's own finding,
   *  ux/orders 555d6b62), so it carries the SAME height as the search and the popover's own
   *  controls. */
  for (const width of [1440, 820, 720, 390] as const) {
    test(`the trigger and the search read one height at ${width}, and the popover's own controls match it (FLT-24)`, async ({ page }) => {
      await open(page, width)
      const search = await page.locator(`${BAR} .bn-filterbar-search .search-field-box`).evaluate((el) => Math.round(el.getBoundingClientRect().height))
      const trigger = await page.locator(`${BAR} .bn-filterbar-trigger`).evaluate((el) => Math.round(el.getBoundingClientRect().height))
      const overlay = await openTrigger(page, BAR)
      const inside = await overlay.locator('.bn-pick, .bn-sort-dir, .bn-hidetoggle').evaluateAll((els) => els.map((el) => Math.round(el.getBoundingClientRect().height)))
      const heights = [search, trigger, ...inside]
      expect(heights.length).toBeGreaterThanOrEqual(7)
      expect(new Set(heights).size, `heights ${heights.join(', ')}`).toBe(1)
      /* `--bn-control-h`: 34px on a desk, raised to 42px below 768px for a thumb (tokens.css). */
      expect(heights[0]).toBe(width >= 768 ? 34 : 42)
      await page.keyboard.press('Escape')
    })

    test(`the search input reads at the bar's own 13px, same as the facet triggers inside the popover, at ${width}`, async ({ page }) => {
      await open(page, width)
      const barInput = await page.locator(`${BAR} .bn-filterbar-search .search-field-input`).evaluate((el) => getComputedStyle(el).fontSize)
      const overlay = await openTrigger(page, BAR)
      const pick = await overlay.locator('.bn-pick').first().evaluate((el) => getComputedStyle(el).fontSize)
      expect(barInput).toBe(pick)
      expect(barInput).toBe('13px')
      await page.keyboard.press('Escape')
    })

    test(`every facet trigger in the popover is ONE width at ${width}, and a pick changes none (the owner's gripe, D118)`, async ({ page }) => {
      await open(page, width)
      const overlay = await openTrigger(page, BAR)
      const triggers = overlay.locator('.bn-fchip > .bn-pick')
      const widths = () => triggers.evaluateAll((els) => els.map((el) => Math.round(el.getBoundingClientRect().width)))
      const before = await widths()
      expect(before).toHaveLength(3)
      expect(new Set(before).size, `widths ${before.join(', ')}`).toBe(1)

      /* Pick a set (single-choice): its value takes the slot, and no width moves. */
      await triggers.nth(1).click()
      await page.locator('.bn-pick-opt', { hasText: 'Obsidian Flames' }).click()
      await expect(triggers.nth(1)).toContainText('Obsidian Flames')
      expect(await widths()).toEqual(before)
      await page.keyboard.press('Escape')
    })
  }

  test('"N of M" is drawn by construction, names what narrows, and one Clear resets the facets (FLT-13)', async ({ page }) => {
    await open(page, 1440)
    const count = page.locator(`${BAR} .bn-filtercount`)
    /* Twelve Pokémon cards, three of them sold and hidden by default. */
    await expect(count).toContainText('9 of 24 cards')
    await expect(count).toContainText('Pokémon')
    await expect(count).toContainText('Hide sold')

    /* THE SEARCH IS NAMED TOO, in the words typed. The search field stays outside the popover. */
    await page.locator(`${BAR} .search-field-input`).fill('ex')
    await expect(count).toContainText('“ex”')

    /* ONE clear-all in the bar: the count line's. FilterChips' own would show once two facets
     * are on, so pick a second one first. */
    const overlay = await openTrigger(page, BAR)
    await overlay.locator('.bn-fchip > .bn-pick').nth(2).click()
    await page.locator('.bn-pick-opt', { hasText: /^Rare/ }).click()
    await page.keyboard.press('Escape')
    await expect(count).toContainText('Rare')
    await expect(page.locator(`${BAR} .bn-filterchips-clear`)).toBeHidden()
    await expect(page.locator(`${BAR} .bn-filtercount-clear`)).toHaveCount(1)
    await page.locator(`${BAR} .bn-filtercount-clear`).click()
    await expect(page.locator(`${BAR} .search-field-input`)).toHaveValue('')
    /* Hide sold is at its default, so Clear leaves it on: 24 cards, 6 sold. */
    await expect(count).toContainText('18 of 24 cards')
    await expect(count).not.toContainText('Pokémon')
  })

  test('a facet option carries a count under the other active filters, and a zero is drawn, not hidden (FLT-10)', async ({ page }) => {
    await open(page, 1440)
    /* `PickPanel` is portalled to `document.body`: this locator is deliberately page-wide. Under
     * Game = Pokémon, the two sets from other games count zero and are still offered. */
    const overlay = await openTrigger(page, BAR)
    await overlay.locator('.bn-pick').nth(1).click()
    const zero = page.locator('.bn-pick-opt[data-zero="true"]')
    await expect(zero).toHaveCount(2)
    await expect(zero.first()).toContainText('0')
    await page.keyboard.press('Escape')
  })

  test('a pick in one facet changes the counts in ANOTHER (the counts helper, FLT-10)', async ({ page }) => {
    await open(page, 1440)
    const overlay = await openTrigger(page, BAR)
    const rarity = overlay.locator('.bn-fchip > .bn-pick').nth(2)
    const commonCount = page.locator('.bn-pick-opt', { hasText: 'Common' }).locator('.bn-pick-count')

    await rarity.click()
    const underPokemon = await commonCount.textContent()
    await page.keyboard.press('Escape')

    /* Clear Game: Rarity's Common count now counts every game. */
    await overlay.locator('.bn-fchip-clear').first().click()
    await rarity.click()
    await expect(commonCount).not.toHaveText(underPokemon ?? '')
    expect(underPokemon).toBe('4')
    await expect(commonCount).toHaveText('7')
    await page.keyboard.press('Escape')
  })

  test("no facet is disabled: every one opens in any order (the owner's ruling against Inventory's game-then-set-then-rarity lock)", async ({ page }) => {
    await open(page, 1440)
    const overlay = await openTrigger(page, BAR)
    const triggers = overlay.locator('.bn-fchip .bn-pick')
    const count = await triggers.count()
    expect(count).toBe(3)
    for (let at = 0; at < count; at++) {
      await expect(triggers.nth(at)).toBeEnabled()
      await expect(triggers.nth(at)).not.toHaveAttribute('disabled', '')
    }
  })

  test('a single-choice facet marks its options differently from a multi-choice one (gripe 5: "one selection rule, drawn honestly")', async ({ page }) => {
    await open(page, 1440)
    const overlay = await openTrigger(page, BAR)
    const facets = overlay.locator('.bn-fchip .bn-pick')
    await facets.nth(0).click()
    await expect(page.locator('.bn-pick-opt').first()).toHaveAttribute('data-multiple', 'true')
    await page.keyboard.press('Escape')
    await facets.nth(1).click()
    await expect(page.locator('.bn-pick-opt').first()).not.toHaveAttribute('data-multiple', 'true')
    await page.keyboard.press('Escape')
  })

  test('at 390, the popover trigger opens a floating panel, nothing outside it moves (D118)', async ({ page }) => {
    await open(page, 390)
    const before = await page.locator('[data-specimen="HideToggle"]').boundingBox()
    const trigger = page.locator(`${BAR} .bn-filterbar-trigger`)
    await expect(trigger).toBeVisible()
    const overlay = await openTrigger(page, BAR)
    await expect(overlay.locator('.bn-filterchips')).toBeVisible()
    const after = await page.locator('[data-specimen="HideToggle"]').boundingBox()
    expect(after?.y).toBe(before?.y)

    /* THE BLANK BAND: FilterChips' reserved Clear-all slot took a 42px row under the last facet.
     * The gap from the last facet to the sort is the overlay's own gap, nothing more. */
    const gap = await overlay.evaluate((root) => {
      const facets = root.querySelectorAll('.bn-fchip')
      const last = facets[facets.length - 1]?.getBoundingClientRect()
      const sort = root.querySelector('.bn-sort')?.getBoundingClientRect()
      return last === undefined || sort === undefined ? -1 : Math.round(sort.top - last.bottom)
    })
    expect(gap).toBeGreaterThanOrEqual(0)
    expect(gap).toBeLessThanOrEqual(16)

    /* The thumb floor inside the popover: every control is 40px or taller (below 768px, the
       raised `--bn-control-h`). */
    const heights = await overlay
      .locator('.bn-pick, .bn-sort-dir, .bn-hidetoggle')
      .evaluateAll((els) => els.map((el) => Math.round(el.getBoundingClientRect().height)))
    expect(Math.min(...heights), `heights ${heights.join(', ')}`).toBeGreaterThanOrEqual(40)

    await page.keyboard.press('Escape')
    await expect(overlay).toBeHidden()
  })

  test('at 390, a pick list inside the popover works by keyboard: the arrows move, and Escape closes the list only', async ({ page }) => {
    await open(page, 390)
    const overlay = await openTrigger(page, BAR)

    const game = overlay.locator('.bn-fchip > .bn-pick').first()
    await game.focus()
    await page.keyboard.press('ArrowDown')
    const panel = page.locator('[data-bn-pick-panel]')
    await expect(panel).toBeVisible()
    /* FOCUS STAYS IN THE LIST. Before the list joined the overlay stack, the overlay's own trap
     * pulled it straight back into the popover. */
    await expect.poll(() => page.evaluate(() => document.activeElement?.closest('[data-bn-pick-panel]') !== null)).toBe(true)

    const active = () => panel.locator('.bn-pick-opt[data-active="true"]').textContent()
    const first = await active()
    await page.keyboard.press('ArrowDown')
    await expect.poll(active).not.toBe(first)
    await page.keyboard.press('Space')
    await expect(panel.locator('.bn-pick-opt[aria-selected="true"]')).toHaveCount(2)

    /* Escape closes the LIST, and the popover stays, with focus back on the trigger. */
    await page.keyboard.press('Escape')
    await expect(panel).toHaveCount(0)
    await expect(overlay).toBeVisible()
    await expect(game).toBeFocused()

    await page.keyboard.press('Escape')
    await expect(overlay).toBeHidden()
  })

  test('at 390, the "Filters" badge counts what differs from rest: a Hide sold on by default is not counted', async ({ page }) => {
    await open(page, 390)
    /* `.bn-filterbar-trigger-count` WAS HERE — the trigger is an IconButton now
       (D288), and its badge is `.bn-icon-count`, generic across every IconButton
       that carries one. */
    const badge = page.locator(`${BAR} .bn-filterbar-trigger .bn-icon-count`)
    /* Game = Pokémon is one. Hide sold is on, and on is its default. */
    await expect(badge).toHaveText('1')
    const overlay = await openTrigger(page, BAR)
    await overlay.locator('.bn-hidetoggle').click()
    await page.keyboard.press('Escape')
    await expect(badge).toHaveText('2')
  })

  test('compact picks the overlay: the default bar opens a Popover, the rail (compact="sheet") opens a Sheet, both at 1440', async ({ page }) => {
    await open(page, 1440)
    const rail = page.locator(RAIL)
    await expect(rail.locator('.bn-filterbar-trigger')).toBeVisible()
    /* And the full-width bar, at the same window width, is also the trigger alone — no wide
       row at any width (D270's amendment). */
    await expect(page.locator(`${BAR} .bn-filterbar-trigger`)).toBeVisible()

    await rail.locator('.bn-filterbar-trigger').click()
    await expect(page.locator(SHEET)).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(page.locator(SHEET)).toBeHidden()

    await page.locator(`${BAR} .bn-filterbar-trigger`).click()
    await expect(page.locator(POPOVER)).toBeVisible()
    await page.keyboard.press('Escape')

    const search = await rail.locator('.search-field-box').boundingBox()
    const beside = await rail.locator('.bn-filterbar-beside .bn-btn').boundingBox()
    expect(search).not.toBeNull()
    expect(beside).not.toBeNull()
    /* One line: the control sits to the right of the search, vertically centred on it. */
    expect(beside!.x).toBeGreaterThan(search!.x + search!.width - 1)
    expect(Math.abs(beside!.y + beside!.height / 2 - (search!.y + search!.height / 2))).toBeLessThanOrEqual(1)
    await expect(rail.locator('.search-field-box')).toHaveAttribute('aria-busy', 'true')
    await expect(rail.locator('.search-field-spin')).toBeVisible()
  })

  test("a search failure is drawn in the kit's one failure shape, and its retry press asks again", async ({ page }) => {
    await open(page, 1440)
    const demo = page.locator('[data-failure-demo]')
    await expect(demo.locator('.bn-notice, [role="alert"]').first()).toBeVisible()
    await expect(demo).toContainText('The search did not answer.')
    await demo.getByRole('button', { name: 'Try again' }).click()
    await expect(demo.locator('[data-retries]')).toHaveText('1')
  })
})

/* ============================================================================================
 * HideToggle
 * ============================================================================================ */

test.describe('HideToggle', () => {
  test('quiet: on is the check mark, never a black or white fill (FLT-16)', async ({ page }) => {
    for (const theme of ['light', 'dark'] as const) {
      await open(page, 1440, theme)
      const toggles = page.locator('[data-specimen="HideToggle"] .bn-hidetoggle')
      await expect(toggles).toHaveCount(2)
      await expect(toggles.nth(0)).toHaveAttribute('aria-pressed', 'true')
      await expect(toggles.nth(1)).toHaveAttribute('aria-pressed', 'false')
      const fills = await toggles.evaluateAll((els) => els.map((el) => getComputedStyle(el).backgroundColor))
      expect(fills[0], `${theme}: the pressed toggle fills differently from the unpressed one`).toBe(fills[1])
      const markOn = await toggles.nth(0).locator('.bn-hidetoggle-mark').evaluate((el) => getComputedStyle(el).backgroundColor)
      const markOff = await toggles.nth(1).locator('.bn-hidetoggle-mark').evaluate((el) => getComputedStyle(el).backgroundColor)
      expect(markOn).not.toBe(markOff)
    }
  })

  test('its name keeps the count and says no state twice; a zero count is drawn', async ({ page }) => {
    await open(page, 1440)
    const toggles = page.locator('[data-specimen="HideToggle"] .bn-hidetoggle')
    await expect(toggles.nth(0)).toHaveAccessibleName('Hide sold 3')
    await expect(toggles.nth(1)).toHaveAccessibleName('Hide never-seen SKUs 0')
    await expect(toggles.nth(1).locator('.bn-hidetoggle-count')).toHaveText('0')
  })

  test('one bar height: 34px on a desk, 40px or more at 390', async ({ page }) => {
    await open(page, 1440)
    const toggle = page.locator('[data-specimen="HideToggle"] .bn-hidetoggle').first()
    expect(Math.round((await toggle.boundingBox())!.height)).toBe(34)
    await open(page, 390)
    expect(Math.round((await toggle.boundingBox())!.height)).toBeGreaterThanOrEqual(40)
  })
})

/* ============================================================================================
 * SortHeader
 * ============================================================================================ */

test.describe('SortHeader', () => {
  test('aria-sort sits on the active <th>, never on the button; the active column is marked in two channels (FLT-19)', async ({ page }) => {
    await open(page, 1440)
    const heads = page.locator('[data-specimen="SortHeader"] th')
    const name = heads.nth(0)
    const price = heads.nth(1)
    await expect(price).toHaveAttribute('aria-sort', 'descending')
    await expect(name).not.toHaveAttribute('aria-sort', /.*/)
    await expect(page.locator('[data-specimen="SortHeader"] button[aria-sort]')).toHaveCount(0)
    await expect(price.locator('.bn-sortth')).toHaveAttribute('data-active', 'true')

    /* NAME STARTS A TO Z on its first press; a price starts at the highest. */
    await name.locator('button').click()
    await expect(name).toHaveAttribute('aria-sort', 'ascending')
    await expect(page.locator('[data-specimen="SortHeader"] tbody tr').first()).toContainText('Flabébé')
    await expect(price).not.toHaveAttribute('aria-sort', /.*/)

    /* Pressed again, the SAME column flips. */
    await name.locator('button').click()
    await expect(name).toHaveAttribute('aria-sort', 'descending')
    await price.locator('button').click()
    await expect(price).toHaveAttribute('aria-sort', 'descending')
  })

  test('axe finds nothing on the sort headers, in both themes', async ({ page }) => {
    const axePath = createRequire(import.meta.url).resolve('axe-core/axe.min.js')
    for (const theme of ['light', 'dark'] as const) {
      await open(page, 1440, theme)
      await page.addScriptTag({ path: axePath })
      const violations = await page.evaluate(async () => {
        const w = window as unknown as {
          axe: { run: (ctx: object, opts: object) => Promise<{ violations: { id: string; nodes: { target: string[] }[] }[] }> }
        }
        const r = await w.axe.run({ include: [['[data-specimen="SortHeader"]']] }, { resultTypes: ['violations'] })
        return r.violations.flatMap((v) => v.nodes.map((n) => `${v.id} ${n.target.join(' ')}`))
      })
      expect(violations, theme).toEqual([])
    }
  })
})

/* ============================================================================================
 * Highlight
 * ============================================================================================ */

test.describe('Highlight', () => {
  test('marks the matched words and numbers, and nothing on a row the matcher refuses (FLT-08)', async ({ page }) => {
    await open(page, 1440)
    const rows = page.locator('[data-specimen="Highlight"] .bn-row > span')
    await expect(rows.nth(0).locator('mark.bn-highlight')).toHaveText('Heimerdinger, Inventor')
    await expect(rows.nth(1).locator('mark.bn-highlight')).toHaveText('Flabébé')
    await expect(page.locator('[data-specimen-number] mark.bn-highlight')).toHaveText('054/197')
    await expect(page.locator('[data-specimen-refused] mark')).toHaveCount(0)
    await expect(page.locator('[data-specimen-refused]')).toHaveText('Ho-Oh ex')
  })
})

/* ============================================================================================
 * The URL view state (`kit/viewState.ts`) — FLT-11: "what a screen remembers is different on
 * every screen." One mechanism, read back through a real FilterBar bound to the hooks.
 * ============================================================================================ */

const DEMO = '[data-view-state-demo]'

test.describe('view state in the URL', () => {
  test('a press writes the value into the URL, and a value at its default writes no key', async ({ page }) => {
    await open(page, 1440)
    await page.locator('[data-set-q]').click()
    await expect(page.locator('[data-q]')).toHaveText('pikachu')
    expect(new URL(page.url()).hash).toContain('q=pikachu')

    await page.locator('[data-clear-q]').click()
    await expect(page.locator('[data-q]')).toHaveText('')
    expect(new URL(page.url()).hash).not.toContain('q=')
  })

  test('the search typed into the bar lives in the URL, and the count line names it', async ({ page }) => {
    await open(page, 1440)
    await page.locator(`${DEMO} .search-field-input`).fill('char')
    await expect(page.locator('[data-q]')).toHaveText('char')
    expect(new URL(page.url()).hash).toContain('q=char')
    await expect(page.locator(`${DEMO} .bn-filtercount`)).toContainText('“char”')
  })

  test('Hide sold, on by default, turns off and STAYS off across a reload (D132)', async ({ page }) => {
    await open(page, 1440)
    await expect(page.locator('[data-hide]')).toHaveText('true')
    expect(new URL(page.url()).hash).not.toContain('hidesold')

    let overlay = await openTrigger(page, DEMO)
    await overlay.locator('.bn-hidetoggle').click()
    await expect(page.locator('[data-hide]')).toHaveText('false')
    expect(new URL(page.url()).hash).toContain('hidesold=0')

    await page.reload()
    await expect(page.locator('[data-hide]')).toHaveText('false')
    overlay = await openTrigger(page, DEMO)
    await expect(overlay.locator('.bn-hidetoggle')).toHaveAttribute('aria-pressed', 'false')

    /* Back on: the default again, so no key. */
    await overlay.locator('.bn-hidetoggle').click()
    await expect(page.locator('[data-hide]')).toHaveText('true')
    expect(new URL(page.url()).hash).not.toContain('hidesold')
  })

  test('a hand-edited URL: unknown values dropped, one value for a single-choice facet, no duplicates, a bad escape ignored, the sort at rest', async ({ page }) => {
    await open(page, 1440, 'light', '#/demo?game=pokemon&game=bogus&game=pokemon&set=sv1&set=sv3&sort=nope&dir=sideways&q=%E0%A4%A&hidesold=yes')
    await expect(page.locator('[data-game]')).toHaveText('pokemon')
    await expect(page.locator('[data-set]')).toHaveText('sv1')
    await expect(page.locator('[data-sort]')).toHaveText('name:asc')
    await expect(page.locator('[data-q]')).toHaveText('')
    await expect(page.locator('[data-hide]')).toHaveText('true')
    /* THE COUNT LINE NEVER SHOWS A BOGUS WORD. */
    const line = page.locator(`${DEMO} .bn-filtercount`)
    await expect(line).toContainText('Pokémon')
    await expect(line).toContainText('Scarlet & Violet')
    await expect(line).not.toContainText('bogus')
    await expect(line).not.toContainText('Obsidian Flames')
    await expect(line).not.toContainText('�')

    /* And the bar itself, handed an unknown pick with no URL reader in front of it, never names
     * it either. */
    const raw = page.locator('[data-raw-demo] .bn-filtercount')
    await expect(raw).toContainText('Pokémon')
    await expect(raw).not.toContainText('bogus')
  })

  test('a facet writes one repeated key per value, never a joined string', async ({ page }) => {
    await open(page, 1440)
    await page.locator('[data-set-game]').click()
    await expect(page.locator('[data-game]')).toHaveText('pokemon,riftbound')
    const hash = new URL(page.url()).hash
    expect(hash.match(/game=pokemon/)).not.toBeNull()
    expect(hash.match(/game=riftbound/)).not.toBeNull()
    expect(hash).not.toContain('pokemon%2Criftbound')
    expect(hash).not.toContain('pokemon,riftbound')
  })

  test('sort writes two keys, and a reload restores every value (FLT-11: reload restores the view)', async ({ page }) => {
    await open(page, 1440)
    await page.locator('[data-set-q]').click()
    await page.locator('[data-toggle-hide]').click()
    await page.locator('[data-set-game]').click()
    await page.locator('[data-set-sort]').click()
    await expect(page.locator('[data-sort]')).toHaveText('price:desc')

    await page.reload()
    await expect(page.locator('[data-q]')).toHaveText('pikachu')
    await expect(page.locator('[data-hide]')).toHaveText('false')
    await expect(page.locator('[data-game]')).toHaveText('pokemon,riftbound')
    await expect(page.locator('[data-sort]')).toHaveText('price:desc')
  })

  test('reversing the DEFAULT column writes only `?dir=`, and the value reads back at once and survives a reload (the reversed-default regression, filtering round 3)', async ({ page }) => {
    await open(page, 1440)
    let overlay = await openTrigger(page, DEMO)
    const dir = overlay.locator('.bn-sort-dir')
    await expect(page.locator('[data-sort]')).toHaveText('name:asc')
    expect(new URL(page.url()).hash).not.toContain('sort=')

    await dir.click()
    /* The key stays at rest (no `sort=` key written), only the direction moves. */
    expect(new URL(page.url()).hash).toContain('dir=desc')
    expect(new URL(page.url()).hash).not.toContain('sort=')
    await expect(page.locator('[data-sort]')).toHaveText('name:desc')
    await expect(dir).toHaveAccessibleName('Order: Z to A. Press to reverse.')

    await page.reload()
    expect(new URL(page.url()).hash).toContain('dir=desc')
    await expect(page.locator('[data-sort]')).toHaveText('name:desc')
    overlay = await openTrigger(page, DEMO)
    await expect(overlay.locator('.bn-sort-dir')).toHaveAccessibleName('Order: Z to A. Press to reverse.')
  })

  test('a link elsewhere in the app (a path change) leaves a place for Back to return to', async ({ page }) => {
    await open(page, 1440)
    /* Reaching the first URL the way a screen link would (`App.tsx:go`): assigning
     *  `location.hash` PUSHES a history entry, unlike this file's own `patchViewQuery` writes,
     *  which replace. */
    await page.evaluate(() => {
      window.location.hash = '#/demo?q=abra'
    })
    await page.waitForFunction(() => window.location.hash.includes('q=abra'))
    await expect(page.locator('[data-q]')).toHaveText('abra')

    await page.evaluate(() => {
      window.location.hash = '#/demo?q=raboot'
    })
    await page.waitForFunction(() => window.location.hash.includes('q=raboot'))
    await page.locator('[data-toggle-hide]').click()
    expect(new URL(page.url()).hash).toContain('q=raboot')
    expect(new URL(page.url()).hash).toContain('hidesold=0')

    await page.goBack()
    await page.waitForFunction(() => window.location.hash.includes('q=abra'))
    /* The Back press landed on the FIRST hash again, and the replace-only writes this file made
     *  while on the second one travelled with it into history rather than leaking backwards. */
    await expect(page.locator('[data-q]')).toHaveText('abra')
  })
})
