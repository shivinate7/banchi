// Protects: A refusal the server sent to the shell's status poll never draws the offline banner.
// Governs: D207
import { test, expect } from '@playwright/test'
import { sealEveryTest } from './shell'
import type { ServerStatus } from '../src/types'

/* `/status` SHARES THE PHOTO LANE, so a photo flood can turn it away `photo_busy` (503). The
 * server answered, so it is up. `useServerPresence` used to mark the app offline on ANY poll
 * error; now only "no response at all" does. `sealEveryTest`'s afterEach also asserts the
 * banner is absent, so a regression fails twice, once as itself here. */
sealEveryTest({ store: true })

test('a 503 from /status keeps the shell online', async ({ page }) => {
  // The wire shape the poll reads, so a rename in `ServerStatus` is seen here.
  const shape: keyof ServerStatus = 'cards'
  expect(shape).toBe('cards')
  const refusal = {
    status: 503,
    code: 'photo_busy',
    message: 'The server is busy with 4 photo, file and status requests already. Try again in a moment.',
  }
  await page.route(/\/status$/, (route) =>
    route.fulfill({
      status: refusal.status,
      contentType: 'application/json',
      headers: { 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify({ error: { code: refusal.code, message: refusal.message } }),
    }),
  )
  const answered = page.waitForResponse((r) => /\/status$/.test(r.url()) && r.status() === refusal.status)
  await page.goto('/')
  await answered
  await page.waitForTimeout(300)
  await expect(page.locator('.bn-banner')).toHaveCount(0)
})
