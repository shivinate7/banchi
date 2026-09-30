// Protects: Every filter and sort row is one kit control of one width, the sort direction sits inside its field, and a set filter differs from rest by more than weight.
// Governs: D-filters-are-one-kit-control, D195
import { test, expect, type Locator, type Page } from '@playwright/test'

import { sealEveryTest } from './shell'
import { settleFonts } from './fontsReady'
import { settleMotion } from './motionSettled'

sealEveryTest()

const PAGE = '/tests/filters/index.html'
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
      const widths = await rows.evaluateAll((els) => els.map((el) => Math.round(el.getBoundingClientRect().width)))
      expect(new Set(widths).size, `row widths ${widths.join(', ')}`).toBe(1)

      // The direction toggle is a segment inside the Sort field, never a loose icon beside it.
      const inside = await overlay.locator('.bn-sort').evaluate((sort) => {
        const box = sort.getBoundingClientRect()
        const dir = sort.querySelector('.bn-sort-dir')!.getBoundingClientRect()
        return dir.left >= box.left && dir.right <= box.right && dir.top >= box.top && dir.bottom <= box.bottom
      })
      expect(inside, 'direction toggle sits inside the sort field').toBe(true)

      const first = overlay.locator('.bn-fchip > .bn-pick:not([data-active])').first()
      const handle = (await first.elementHandle())!
      const rest = await look(first)
      const sortLook = await look(overlay.locator('.bn-sort > .bn-pick'))
      expect(rest.weight, 'one value weight at rest').toBe(sortLook.weight)
      expect(rest.ink, 'one value ink at rest').toBe(sortLook.ink)

      await first.click()
      await page.locator('[role="option"]').first().click()
      await page.keyboard.press('Escape')
      const set = await handle.evaluate((el) => {
        const at = getComputedStyle(el)
        const words = getComputedStyle(el.querySelector('.bn-pick-value')!)
        return { edge: at.borderTopColor, ground: at.backgroundColor, ink: words.color, weight: words.fontWeight }
      })
      expect(set.weight, 'set is not marked by weight').toBe(rest.weight)
      expect(set.ink, 'set changes ink').not.toBe(rest.ink)
      expect(set.edge, 'set changes edge').not.toBe(rest.edge)
      expect(set.ground, 'set changes ground').not.toBe(rest.ground)
    })
  }
}
