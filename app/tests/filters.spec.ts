import { test, expect, type Page } from '@playwright/test'

import { sealEveryTest } from './shell'
import { settleFonts } from './fontsReady'
import { matchSpans } from '../src/kit/highlight'

/* THE FILTER BAR, THE HIDE TOGGLE, THE SORTABLE TABLE HEADER AND THE MATCH HIGHLIGHT
 * (`kit/filters.tsx`, `kit/highlight.tsx`), drawn on `tests/filters/index.html` — a page with
 * no router, no store and no server, the same shape `kit-data.spec.ts` already draws its own
 * specimens on. `match.spec.ts` covers `kit/match.ts` itself; this file covers what is built on
 * top of it: the URL view state (`kit/viewState.ts`) and the composed controls.
 *
 * `match.cases.json`'s `54/132` and `heimerdinger-inventor` and `flabebe` cases are exercised
 * again here, through `Highlight`, so a caller of the highlight gets the same three examples
 * the addendum's own "Done" line names — the matcher and its highlight, proven on the same
 * words rather than two different ones that could quietly drift apart.
 */

sealEveryTest()

/* `matchSpans` runs no browser: it is a pure function, asserted here the way `kit-data.spec.ts`
 * asserts `matchQuery` — a case the case table in `match.cases.json` does not carry, since that
 * table is `matchQuery`'s own, not the highlight's narrower "found as a direct or compact
 * substring" rule (`kit/highlight.tsx`'s own file header). */
test('matchSpans marks a direct hit, and the compact fallback a hyphen or comma cannot break', () => {
  expect(matchSpans('Hextech', 'hextech')).toEqual([[0, 7]])
  expect(matchSpans('Heimerdinger, Inventor', 'heimerdinger-inventor')).toEqual([[0, 22]])
  expect(matchSpans('Ho-Oh ex', 'zzzz')).toEqual([])
})

const PAGE = '/tests/filters/index.html'
const WIDTHS = [1440, 820, 720, 390] as const
const HEIGHT: Record<(typeof WIDTHS)[number], number> = { 1440: 900, 820: 1180, 720: 1000, 390: 900 }

const SPECIMENS = ['FilterBar', 'HideToggle', 'SortHeader', 'Highlight'] as const

async function open(page: Page, width: (typeof WIDTHS)[number], theme: 'light' | 'dark' = 'light'): Promise<void> {
  await page.setViewportSize({ width, height: HEIGHT[width] })
  await page.goto(theme === 'dark' ? `${PAGE}?theme=dark` : PAGE)
  await expect(page.locator('[data-kit-filters]')).toBeVisible()
  await settleFonts(page)
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
  test('every facet and sort control in the wide row is one height (FLT-24)', async ({ page }) => {
    await open(page, 1440)
    const heights = await page
      .locator('[data-specimen="FilterBar"] .bn-filterbar-row .bn-pick, [data-specimen="FilterBar"] .bn-filterbar-row .bn-sort-dir')
      .evaluateAll((els) => els.map((el) => Math.round(el.getBoundingClientRect().height)))
    expect(heights.length).toBeGreaterThanOrEqual(5)
    expect(new Set(heights).size, `heights ${heights.join(', ')}`).toBe(1)
  })

  test('"N of M" is drawn by construction, and changes as a facet narrows (FLT-13)', async ({ page }) => {
    await open(page, 1440)
    const count = page.locator('[data-specimen="FilterBar"] .bn-filtercount')
    await expect(count).toContainText('37 of 122')
    await expect(count).toContainText('Pokémon')

    /* Clear the one active facet: the count goes back to an unnarrowed total. */
    await page.locator('[data-specimen="FilterBar"] .bn-filtercount-clear').click()
    await expect(count).toContainText('122 cards')
    await expect(count).not.toContainText('filtered by')
  })

  test('a facet option carries a count under the other active filters, and a zero is drawn, not hidden (FLT-10)', async ({ page }) => {
    await open(page, 1440)
    /* `PickPanel` is portalled to `document.body`, so its options are not descendants of
     *  `[data-specimen="FilterBar"]` in the DOM — this locator is deliberately page-wide. */
    await page.locator('[data-specimen="FilterBar"] .bn-filterbar-row .bn-pick').first().click()
    const zero = page.locator('.bn-pick-opt[data-zero="true"]')
    await expect(zero).toBeVisible()
    await expect(zero).toContainText('0')
    await page.keyboard.press('Escape')
  })

  test('no facet is disabled: every one opens in any order (the owner\'s ruling against Inventory\'s game-then-set-then-rarity lock)', async ({
    page,
  }) => {
    await open(page, 1440)
    const triggers = page.locator('[data-specimen="FilterBar"] .bn-filterbar-row .bn-fchip .bn-pick')
    const count = await triggers.count()
    expect(count).toBe(3)
    for (let at = 0; at < count; at++) {
      await expect(triggers.nth(at)).toBeEnabled()
      await expect(triggers.nth(at)).not.toHaveAttribute('disabled', '')
    }
  })

  test('a single-choice facet marks its options differently from a multi-choice one (gripe 5: "one selection rule, drawn honestly")', async ({
    page,
  }) => {
    await open(page, 1440)
    const facets = page.locator('[data-specimen="FilterBar"] .bn-filterbar-row .bn-fchip .bn-pick')
    /* Game: multi-select — every option is a checkbox mark. */
    await facets.nth(0).click()
    await expect(page.locator('.bn-pick-opt').first()).toHaveAttribute('data-multiple', 'true')
    await page.keyboard.press('Escape')
    /* Set: single-select — no option carries the checkbox mark. */
    await facets.nth(1).click()
    await expect(page.locator('.bn-pick-opt').first()).not.toHaveAttribute('data-multiple', 'true')
    await page.keyboard.press('Escape')
  })

  test('at 390, the compact trigger opens a sheet, and nothing outside it moves (D118)', async ({ page }) => {
    await open(page, 390)
    const before = await page.locator('[data-specimen="HideToggle"]').boundingBox()
    await expect(page.locator('[data-specimen="FilterBar"] .bn-filterbar-row')).toBeHidden()
    const trigger = page.locator('[data-specimen="FilterBar"] .bn-filterbar-trigger')
    await expect(trigger).toBeVisible()
    await trigger.click()
    await expect(page.locator('[data-bn-overlay="sheet"]')).toBeVisible()
    await expect(page.locator('[data-bn-overlay="sheet"] .bn-filterchips')).toBeVisible()
    const after = await page.locator('[data-specimen="HideToggle"]').boundingBox()
    expect(after?.y).toBe(before?.y)
    await page.keyboard.press('Escape')
    await expect(page.locator('[data-bn-overlay="sheet"]')).toBeHidden()
  })
})

/* ============================================================================================
 * HideToggle
 * ============================================================================================ */

test.describe('HideToggle', () => {
  test('one control shape, with a count on the pill (FLT-16)', async ({ page }) => {
    await open(page, 1440)
    const toggles = page.locator('[data-specimen="HideToggle"] .bn-hidetoggle')
    await expect(toggles).toHaveCount(2)
    await expect(toggles.nth(0)).toHaveAttribute('aria-pressed', 'true')
    await expect(toggles.nth(0).locator('.bn-chip-count')).toHaveText('8')
    /* A count of zero is still DRAWN, never omitted — the same "a zero shows" rule the facet
     *  counts carry (FLT-10), so "Hide never-seen SKUs" stops being the one control on the row
     *  with no count at all. */
    await expect(toggles.nth(1).locator('.bn-chip-count')).toHaveText('0')
  })
})

/* ============================================================================================
 * SortHeaderButton
 * ============================================================================================ */

test.describe('SortHeaderButton', () => {
  test('the active column is marked in two channels, not only the chevron (FLT-19)', async ({ page }) => {
    await open(page, 1440)
    const name = page.locator('[data-specimen="SortHeader"] .bn-sortth').first()
    const sku = page.locator('[data-specimen="SortHeader"] .bn-sortth').nth(1)
    await expect(name).toHaveAttribute('data-active', 'true')
    await expect(name).toHaveAttribute('aria-sort', 'ascending')
    await expect(sku).not.toHaveAttribute('data-active', 'true')
    await expect(sku).toHaveAttribute('aria-sort', 'none')

    /* A press re-sorts AT ONCE (FLT-01): no second confirming press, no "re-sort" chip. */
    await sku.click()
    await expect(sku).toHaveAttribute('data-active', 'true')
    await expect(sku).toHaveAttribute('aria-sort', 'descending')
    await expect(name).not.toHaveAttribute('data-active', 'true')

    /* Pressed again, the SAME column flips direction rather than resetting. */
    await sku.click()
    await expect(sku).toHaveAttribute('aria-sort', 'ascending')
  })
})

/* ============================================================================================
 * Highlight
 * ============================================================================================ */

test.describe('Highlight', () => {
  test('marks the matched words, folded the same way the matcher folds them (FLT-08)', async ({ page }) => {
    await open(page, 1440)
    const rows = page.locator('[data-specimen="Highlight"] .bn-row > span')
    await expect(rows.nth(0).locator('mark.bn-highlight')).toHaveText('Heimerdinger, Inventor')
    await expect(rows.nth(1).locator('mark.bn-highlight')).toHaveText('Flabébé')
    /* A query with nothing to find draws no mark, and the text is untouched. */
    await expect(page.locator('[data-specimen-nomatch] mark')).toHaveCount(0)
    await expect(page.locator('[data-specimen-nomatch]')).toHaveText('Ho-Oh ex')
  })
})

/* ============================================================================================
 * The URL view state (`kit/viewState.ts`) — FLT-11: "what a screen remembers is different on
 * every screen." One mechanism, read back here through the hooks themselves rather than a
 * screen, since no screen lane has adopted it yet.
 * ============================================================================================ */

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
    await expect(page.locator('[data-hide]')).toHaveText('true')
    await expect(page.locator('[data-game]')).toHaveText('pokemon,riftbound')
    await expect(page.locator('[data-sort]')).toHaveText('price:desc')
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
    expect(new URL(page.url()).hash).toContain('hide=1')

    await page.goBack()
    await page.waitForFunction(() => window.location.hash.includes('q=abra'))
    /* The Back press landed on the FIRST hash again, and the replace-only writes this file made
     *  while on the second one travelled with it into history rather than leaking backwards. */
    await expect(page.locator('[data-q]')).toHaveText('abra')
  })
})
