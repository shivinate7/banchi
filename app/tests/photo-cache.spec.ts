// Protects: Home, Review and Pricing ask for each photograph by card name and version, never by box slot.
// Governs: D26, D172
import { test, expect, type Page } from '@playwright/test'
import { sealEveryTest, card } from './shell'
import { seedPopulatedPricing } from './routeFixtures'
import { afterPaint } from './motionSettled'

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

/* A CARD WITH NO PHOTOGRAPH GETS NO PHOTO ADDRESS AT ALL (D172). Its name is `nophoto:…`, which
 * no route serves, and building `/photo/<box>/<index>` from its slot 404s. Home is seeded on
 * purpose with a store whose every recent card is one. The card read is HELD while `/boxes`
 * answers and the screen renders, because that is the window in which a slot placeholder used
 * to ask for `/photo/<box>/<index>` before anything knew what sat there. */
test('Home asks for no photograph before the card read answers, or of a card that has none', async ({ page }) => {
  const asked: string[] = []
  page.on('request', (r) => {
    if (/\/photo\//.test(r.url())) asked.push(r.url())
  })
  let release!: () => void
  const held = new Promise<void>((resolve) => (release = resolve))
  await page.route(/\/inventory\/recent(\?|$)/, async (route) => {
    await held
    const cards = Object.fromEntries(
      [1, 2, 3].map((index) => [
        `2/${index}`,
        {
          ...card({ box: 2, index, section: 1, card: index, name: `Card ${index}`, boxName: 'SV commons', boxTotal: 3 }),
          cid: `nophoto:2/${index}@2026-08-22T12:34:00`,
        },
      ]),
    )
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ cards }) })
  })
  await page.route(/\/inventory\/history$/, (route) => route.fulfill({ status: 200, contentType: 'application/json', body: '{"cards":{}}' }))
  const boxesRead = page.waitForResponse(/\/boxes$/)
  await page.goto('/')
  await boxesRead
  await afterPaint(page)
  await expect(page.locator('.home-deck')).toBeVisible()
  expect(asked, 'no /photo/ request while the card read is out').toEqual([])
  const answered = page.waitForResponse(/\/inventory\/recent/)
  release()
  await answered
  await afterPaint(page)
  await expect(page.locator('.home-deck[data-empty="true"]')).toBeVisible()
  expect(await page.evaluate(() => [...document.images].filter((i) => i.src.includes('/photo/')).length)).toBe(0)
  expect(asked, 'no /photo/ request at all').toEqual([])
})

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
