import { test, expect } from '@playwright/test'
import { sealEveryTest } from './shell'

/* HOME AND REVIEW ADDRESS PHOTOGRAPHS BY NAME, SO A REVISIT SENDS NO SLOT-URL REQUEST.
 *
 * `GET /photo/<box>/<index>` names a slot, so it answers `no-cache` and the browser asks again
 * on every visit. `GET /photo/by-card/<cid>` names the photograph and answers `immutable`
 * (`capture_server._photo_by_card`; harness T7 `check_photo_cache` holds the header and the
 * 304), so a revisit sends nothing. A route-fulfilled stub is never stored by Chromium's HTTP
 * cache, so this spec cannot count the cache hit itself. It holds the app's half of the claim:
 * every photograph either screen asks for, on the first visit and on the revisit, is a by-card
 * URL. A slot URL is what re-requested on every visit before.
 *
 * `shell.ts`'s queue entry and cards carry a `cid`, as `_queue_row` and `_card_row` send. */
sealEveryTest({ store: true, cards: 4 })

test('Home and Review draw every photograph by name, on the first visit and the revisit', async ({ page }) => {
  const photos: string[] = []
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname
    if (path.startsWith('/photo/')) photos.push(path)
  })
  const visit = async (hash: string, selector: string) => {
    await page.goto(`/#${hash}`)
    await page.locator(selector).first().waitFor({ state: 'attached' })
    await page.waitForLoadState('networkidle')
  }
  const round = async () => {
    await visit('/', '.home-hero img, img')
    await visit('/review', 'img')
  }

  await round()
  expect(photos.length, 'the first visit draws photographs').toBeGreaterThan(0)

  await page.evaluate(() => (location.hash = '#/'))
  await round()
  expect(photos.filter((p) => !p.startsWith('/photo/by-card/')), 'no slot URL, ever').toEqual([])
})
