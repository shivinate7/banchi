// Protects: Home's verdict follows the greeting at the header gap; the card deck never stretches the header.
// Governs: D121, D275
import { test, expect } from '@playwright/test'
import { sealEveryTest } from './shell'

sealEveryTest({ store: true, cards: 4 })

/* The deck once sat in `Page`'s actions slot, so the header grew to its 310px height and left
 * a ~250px empty band between the greeting and the verdict. The deck now sits beside the
 * verdict block, and the verdict follows the h1 at the normal gap. SHOTS=<dir> also writes pictures. */
for (const [w, h] of [[1440, 900], [820, 1100]] as const) {
  for (const theme of ['light', 'dark']) {
    test(`Home verdict sits under the greeting, ${w}px ${theme}`, async ({ page }) => {
      await page.setViewportSize({ width: w, height: h })
      await page.addInitScript((t) => {
        try { localStorage.setItem('banchi.theme', t) } catch { /* no storage */ }
      }, theme)
      await page.route(/\/orders$/, (route) =>
        route.fulfill({ contentType: 'application/json', body: JSON.stringify({ summary: '', orders: [], resolution: { orders: [], counts: {} } }) }),
      )
      await page.goto('/#/')
      await expect(page.locator('main.home')).toBeVisible()
      const verdict = page.locator('.home-standing')
      await expect(verdict).toBeVisible()
      await page.waitForTimeout(700)
      if (process.env.SHOTS) await page.screenshot({ path: `${process.env.SHOTS}/home-${w}-${theme}.png` })
      const h1 = await page.locator('main.home h1').boundingBox()
      const v = await verdict.boundingBox()
      expect(h1 && v).toBeTruthy()
      const gap = v!.y - (h1!.y + h1!.height)
      expect(gap, 'gap between the greeting and the verdict').toBeLessThan(64)
    })
  }
}
