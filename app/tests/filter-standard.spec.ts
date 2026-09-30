// Protects: Every filter and sort row is one kit control of one width, the sort direction sits inside its field, and a set filter differs from rest by more than weight.
// Governs: D311, D195
import { test, expect, type Locator, type Page } from '@playwright/test'

import { sealEveryTest } from './shell'
import { settleFonts } from './fontsReady'
import { settleMotion } from './motionSettled'
import type { FilterFacet } from '../src/kit/data'

sealEveryTest()

const PAGE = '/tests/filters/index.html'
// The specimen bar's three facets: Game, Set and Rarity.
const FACET_KEYS: FilterFacet['key'][] = ['game', 'set', 'rarity']
const BAR = '[data-specimen="FilterBar"]'

async function openPopover(page: Page, width: number, theme: 'light' | 'dark') {
  await page.setViewportSize({ width, height: width > 1000 ? 900 : 1180 })
  await page.goto(theme === 'dark' ? `${PAGE}?theme=dark` : PAGE)
  await expect(page.locator('[data-kit-filters]')).toBeVisible()
  await settleFonts(page)
  await page.locator(`${BAR} .bn-filterbar-trigger`).click()
  const overlay = page.locator('[data-bn-overlay="popover"]')
  await expect(overlay).toBeVisible()
  await settleMotion(page)
  return overlay
}

const look = (locator: Locator) =>
  locator.evaluate((el) => {
    const value = el.querySelector('.bn-pick-value') as HTMLElement
    const at = getComputedStyle(el)
    const words = getComputedStyle(value)
    return { edge: at.borderTopColor, ground: at.backgroundColor, ink: words.color, weight: words.fontWeight }
  })

for (const theme of ['light', 'dark'] as const) {
  for (const width of [1440, 820]) {
    test(`filter rows share one width, and a set filter is not only bolder, at ${width} in ${theme}`, async ({ page }) => {
      const overlay = await openPopover(page, width, theme)
      const rows = overlay.locator('.bn-fchip, .bn-sort, .bn-hidetoggle')
      expect(await rows.count()).toBeGreaterThan(2)
      expect(await overlay.locator('.bn-fchip').count(), 'every facet is a kit row').toBe(FACET_KEYS.length)
      const widths = await rows.evaluateAll((els) => els.map((el) => Math.round(el.getBoundingClientRect().width)))
      expect(new Set(widths).size, `row widths ${widths.join(', ')}`).toBe(1)

      // The direction toggle is a segment inside the Sort field, never a loose icon beside it.
      // Measured: the sort owns ONE drawn edge; its key and direction sit inside that edge,
      // flush against each other, with no edge of their own on the key. A loose icon beside the
      // field (no edge on the sort, a gap between the two) fails every line.
      const field = await overlay.locator('.bn-sort').evaluate((sort) => {
        const box = sort.getBoundingClientRect()
        const edge = parseFloat(getComputedStyle(sort).borderTopWidth)
        const pick = sort.querySelector('.bn-pick')!
        const dir = sort.querySelector('.bn-sort-dir')!.getBoundingClientRect()
        const key = pick.getBoundingClientRect()
        return {
          edge,
          keyEdge: parseFloat(getComputedStyle(pick).borderTopWidth),
          gap: Math.round(dir.left - key.right),
          rightInset: Math.round(box.right - edge - dir.right),
          heightInset: Math.round(box.height - 2 * edge - dir.height),
        }
      })
      expect(field.edge, 'the sort draws one edge').toBeGreaterThan(0)
      expect(field.keyEdge, 'the key draws no edge of its own').toBe(0)
      expect(field.gap, 'the direction is flush against the key').toBeLessThanOrEqual(0)
      expect(field.rightInset, 'the direction ends at the field edge').toBe(0)
      expect(field.heightInset, 'the direction fills the field').toBe(0)

      const first = overlay.locator('.bn-fchip > .bn-pick:not([data-active])').first()
      // Found again by its label after the pick: a node held across a re-render can be a
      // detached copy, which reads no style at all.
      const facet = (await first.locator('.bn-pick-label').textContent())!
      const rest = await look(first)
      const sortLook = await look(overlay.locator('.bn-sort > .bn-pick'))
      expect(rest.weight, 'one value weight at rest').toBe(sortLook.weight)
      expect(rest.ink, 'one value ink at rest').toBe(sortLook.ink)

      await first.click()
      await page.locator('[role="option"]').first().click()
      // No Escape: a single-choice pick closes its own list, and a second Escape closes the
      // popover under it, so the trigger is read while the popover is still up.
      await settleMotion(page)
      await expect(overlay).toBeVisible()
      const set = await overlay.locator('.bn-fchip > .bn-pick', { has: page.locator('.bn-pick-label', { hasText: new RegExp(`^${facet}$`) }) }).evaluate((el) => {
        const at = getComputedStyle(el)
        const words = getComputedStyle(el.querySelector('.bn-pick-value')!)
        return { edge: at.borderTopColor, ground: at.backgroundColor, ink: words.color, weight: words.fontWeight }
      })
      expect(set.weight, 'the set look was read from a live node').not.toBe('')
      expect(set.weight, 'set is not marked by weight').toBe(rest.weight)
      expect(set.ink, 'set changes ink').not.toBe(rest.ink)
      expect(set.edge, 'set changes edge').not.toBe(rest.edge)
      expect(set.ground, 'set changes ground').not.toBe(rest.ground)
    })
  }
}
