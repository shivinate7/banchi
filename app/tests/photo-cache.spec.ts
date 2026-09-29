import { test, expect, type Page } from '@playwright/test'
import { sealEveryTest } from './shell'
import { seedPopulatedPricing } from './routeFixtures'

/* HOME, REVIEW AND PRICING ADDRESS PHOTOGRAPHS BY NAME AND BY VERSION (D172).
 *
 * `GET /photo/<box>/<index>` names a slot, so it answers `no-cache` and the browser asks again
 * on every visit. `GET /photo/by-card/<cid>?v=<capture_id>` names the photograph and its
 * version and answers `immutable`, so a revisit sends nothing. The version is what makes that
 * safe: a D26 re-shoot writes new bytes under the SAME cid, and only `capture_id` moves with
 * them. `server.ts:photoUrl` is the one place that stamps it. A route-fulfilled stub is never
 * stored by Chromium's HTTP cache, so this spec cannot count a cache hit. It holds the
 * app's half, read off the DOM once each screen has drawn (never off a request log, which
 * races the render): every photograph is a by-card URL with a `v` parameter, never a bare
 * by-card URL and never a slot URL.
 *
 * `shell.ts`'s queue entry, cards and positions carry `cid` and `capture_id`, as the wire does. */
sealEveryTest({ store: true, cards: 4 })

const PHOTO = /\/photo\/by-card\/[0-9a-f]{64}\?v=[^&]+$/

async function photosOn(page: Page, hash: string): Promise<string[]> {
  await page.evaluate((h) => (window.location.hash = h), hash)
  /* Pricing draws the owner's own photograph in its photo sheet (the thumb shows the stock
     picture), so open it: the thumb press is what asks for the by-card URL. */
  if (hash === '#/pricing') await page.locator('.pricing-thumb').first().click()
  let srcs: string[] = []
  await expect
    .poll(async () => {
      srcs = await page.evaluate(() =>
        [...document.images].map((img) => img.getAttribute('src') ?? '').filter((s) => s.includes('/photo/')),
      )
      return srcs.length
    })
    .toBeGreaterThan(0)
  return srcs
}

for (const [name, path] of [
  /* The three screens this case is about, not a roster of the app: paths, with the `#` added below. */
  ['Home', '/'],
  ['Review', '/review'],
  ['Pricing', '/pricing'],
] as const) {
  test(`${name} draws every photograph by name and version, on the first visit and the revisit`, async ({ page }) => {
    if (path === '/pricing') await seedPopulatedPricing(page)
    await page.goto('/#/shipping')
    for (const visit of [1, 2]) {
      for (const src of await photosOn(page, `#${path}`)) expect(src, `${name}, visit ${visit}`).toMatch(PHOTO)
      await page.evaluate(() => (window.location.hash = '#/shipping'))
    }
  })
}
