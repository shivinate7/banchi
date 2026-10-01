// Protects: Home's history ribbon is built from every card's capture time, not the three cards of the hero deck; the deck opens the card in the picture.
// Governs: D121, D192, D172
import { test, expect } from '@playwright/test'
import { sealEveryTest } from './shell'
import { setViewport } from './phoneSwitch'

sealEveryTest({ store: true, cards: 260 })

/* Two hundred and sixty captures in three sittings (gaps of days), against a deck that holds three cards. Home
 * once drew its ribbon from the deck's three cards, so any store read as one sitting and one
 * block. The sitting count in the sentence and the blocks drawn under it come off the same
 * history, so they must agree, and agree with the three sittings seeded. SHOTS=<dir> also
 * writes pictures. */
/* Three realistic sittings, the way the owner's store looks: 60 to 120 cards each at a few
 * hundred an hour, on three different days. Heights are cards an hour against the fastest
 * sitting, which draws at full plot height. */
function sitting(day: string, start: string, count: number, perHour: number): string[] {
  const t0 = Date.parse(`${day}T${start}:00Z`)
  return Array.from({ length: count }, (_, i) => new Date(t0 + (i * 3_600_000) / perHour).toISOString())
}
const STAMPS = [
  ...sitting('2026-09-13', '09:00', 120, 600),
  ...sitting('2026-09-14', '14:00', 80, 900),
  ...sitting('2026-09-16', '20:00', 60, 450),
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
      const sizes: { width: number; height: number }[] = []
      for (const box of await page.locator('.home-ribbon-blk').all()) {
        const r = await box.boundingBox()
        expect(r !== null && r.width > 1 && r.height > 1, `a block has a visible size, got ${JSON.stringify(r)}`).toBe(true)
        sizes.push(r!)
      }
      /* The fastest sitting (900 an hour, the second) is the plot's full height; the others are
         their rate's share of it: 600/900 and 450/900. */
      const top = (await page.locator('.home-ribbon-ceil').boundingBox())!.y
      const rule = (await page.locator('.home-ribbon-axis').boundingBox())!.y
      const plot = rule - top
      const [a, b, c] = sizes.map((z) => z.height)
      expect(b, 'fastest block is the plot height').toBeCloseTo(plot, 0)
      expect(a! / b!, 'slower block is proportionally shorter').toBeCloseTo(600 / 900, 1)
      expect(c! / b!, 'slowest block is proportionally shorter').toBeCloseTo(450 / 900, 1)
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
