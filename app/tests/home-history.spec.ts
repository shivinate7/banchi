// Protects: Home's history ribbon is built from every card's capture time, not the three cards of the hero deck; the deck opens the card in the picture.
// Governs: D121, D192, D172
import { test, expect } from '@playwright/test'
import { sealEveryTest } from './shell'
import { setViewport } from './phoneSwitch'

sealEveryTest({ store: true, cards: 10 })

/* Ten captures in three sittings (gaps of hours), against a deck that holds three cards. Home
 * once drew its ribbon from the deck's three cards, so any store read as one sitting and one
 * block. The sitting count in the sentence and the blocks drawn under it come off the same
 * history, so they must agree, and agree with the three sittings seeded. SHOTS=<dir> also
 * writes pictures. */
const STAMPS = [
  '2026-09-13T09:00:00+00:00', '2026-09-13T09:02:00+00:00', '2026-09-13T09:04:00+00:00', '2026-09-13T09:06:00+00:00',
  '2026-09-14T14:00:00+00:00', '2026-09-14T14:05:00+00:00', '2026-09-14T14:10:00+00:00',
  '2026-09-16T20:00:00+00:00', '2026-09-16T20:03:00+00:00', '2026-09-16T20:05:00+00:00',
]

for (const [w, h] of [[1440, 900], [820, 1100]] as const) {
  for (const theme of ['light', 'dark']) {
    test(`Home ribbon draws every sitting, ${w}px ${theme}`, async ({ page }) => {
      await setViewport(page, { width: w, height: h })
      await page.route(/\/inventory\/history$/, (route) =>
        route.fulfill({
          contentType: 'application/json',
          body: JSON.stringify({
            cards: Object.fromEntries(STAMPS.map((at, i) => [`2/${i + 1}`, { captured_at: at, box: 2, state: 'identified' }])),
          }),
        }),
      )
      await page.goto('/#/')
      await expect(page.locator('.home-ribbon')).toBeVisible()
      await page.evaluate((t) => document.documentElement.setAttribute('data-theme', t), theme)
      await page.waitForTimeout(700)
      if (process.env.SHOTS) await page.locator('.home-foot').screenshot({ path: `${process.env.SHOTS}/home-ribbon-${w}-${theme}.png` })
      const said = /over (\d+) sittings?/.exec((await page.locator('.home-foot-sum').innerText()).replace(/\s+/g, ' '))
      expect(said, 'the sentence names a sitting count').not.toBeNull()
      const blocks = await page.locator('.home-ribbon-blk').count()
      expect(Number(said![1]), 'sittings in the sentence').toBe(3)
      expect(blocks, 'blocks drawn').toBe(3)
    })
  }
}

test('Home deck opens the card in the picture, not the box', async ({ page }) => {
  const recent = page.waitForResponse(/\/inventory\/recent/)
  await page.goto('/#/')
  const cards = Object.values((await (await recent).json()).cards) as { cid: string; name: string | null }[]
  const front = cards.find((c) => c.name !== null && c.name !== 'Eiscue')!
  await expect(page.locator('a.home-deck')).toBeVisible()
  await page.locator('a.home-deck').click()
  await expect(page).toHaveURL(/#\/inventory\?box=\d+&card=/)
  expect(new URL(page.url()).hash.split('card=')[1]).toBe(encodeURIComponent(front.cid))
})
