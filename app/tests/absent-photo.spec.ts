// Protects: a missing photograph says so in one plain sentence with one way to re-shoot, and never prints an address.
// Governs: D118, D196, D172
import { test, expect, type Locator, type Page } from '@playwright/test'
import { sealEveryTest } from './shell'
import { place, seedPopulatedPricing } from './routeFixtures'
import { setViewport } from './phoneSwitch'

/* THE PHOTOGRAPH IS GONE (a 404 on the file), ON THREE SCREENS, AND EACH SAYS IT THE SAME WAY.
 *
 * The screen pass found three different answers to one question: Review printed a machine
 * sentence naming an "entry" plus the raw photo URL, Orders and Inventory printed the URL in a
 * mono strip, and Pricing showed the browser's broken-image alt text with no sentence and no
 * action. `CardHero.tsx:AbsentPhotoNote` is the one panel now. What is asserted is what the
 * owner reads: the sentence, a re-shoot action, and no `http` anywhere in the panel.
 *
 * Orders' half of this lives in `orders.spec.ts`, beside the fixtures only that file builds.
 * Set SHOTS=<dir> to write a screenshot per case. */
sealEveryTest({ store: true, cards: 4 })

const SENTENCE = "This card's photo is missing."

const CHIP_PLACE = place({
  label: 'Rares, Section 1, Card 14',
  box: 2,
  index: 1,
  slot: 14,
  section: 1,
  card: 14,
  box_name: 'Rares',
  neighbors: {
    prev: { slot: 13, index: 13, name: 'Charmander' },
    next: { slot: 15, index: 15, name: null, unread: 1 },
  },
})

async function openReview(page: Page): Promise<void> {
  await page.route(/\/photo\//, (route) => route.fulfill({ status: 404, body: '' }))
  await page.route(/\/queues$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        review: [
          {
            position: '2/1',
            box: 2,
            index: 1,
            label: 'Rares, Section 1, Card 14',
            photo: 'photos/2/1.jpg',
            read: { name: 'Volcanion', number: '025', printed_total: '132', set_hint: 'ME01' },
            confidence: null,
            reason: 'no_catalog_row',
            candidates: [],
            first_seen: '2026-09-01T12:00:00+00:00',
            market: null,
            cleared_by_human: false,
            place: CHIP_PLACE,
          },
        ],
        parked: [],
      }),
    }),
  )
  await page.goto('/#/review')
  await expect(page.locator('main.review')).toBeVisible()
}

async function shot(page: Page, name: string): Promise<void> {
  const dir = process.env.SHOTS
  if (!dir) return
  await page.waitForTimeout(700) // let a sheet finish sliding in; only when a person asked for pictures
  await page.screenshot({ path: `${dir}/${name}.png` })
}

/** The panel holds the sentence, a re-shoot link, and no address or machine noun. */
async function expectPlain(panel: Locator): Promise<void> {
  await expect(panel).toContainText(SENTENCE)
  await expect(panel.getByRole('link', { name: /re-shoot/i })).toBeVisible()
  const text = await panel.innerText()
  expect(text).not.toMatch(/http|localhost|\/photo\//i)
  expect(text).not.toMatch(/\bentry\b/i)
}

for (const theme of ['light', 'dark'] as const) {
  for (const size of [
    { width: 1440, height: 900 },
    { width: 820, height: 1000 },
  ]) {
    test(`Review, photo missing, ${size.width} ${theme}: the sentence, one action, a readable place chip`, async ({ page }) => {
      await setViewport(page, size)
      await openReview(page)
      await page.evaluate((t) => document.documentElement.setAttribute('data-theme', t), theme)
      const panel = page.locator('.review-absent')
      await expect(panel).toBeVisible()
      await expectPlain(panel)
      await expect(panel.getByRole('link', { name: /re-shoot/i })).toHaveAttribute('href', /#\/inventory\?box=2/)

      /* F3: the chip's ground is opaque, so no photograph behind it can change its contrast. */
      const chip = page.locator('.review-caption')
      await expect(chip).toBeVisible()
      const ground = await chip.evaluate((el) => getComputedStyle(el).backgroundColor)
      expect(ground, 'the chip ground is opaque').not.toMatch(/rgba\(.*,\s*0?\.\d+\)$/)
      const worst = await chip.evaluate((el) => {
        const rgb = (v: string) => (v.match(/[\d.]+/g) ?? []).slice(0, 3).map(Number)
        const lum = (c: number[]) => {
          const [r, g, b] = c.map((x) => ((x / 255) <= 0.03928 ? x / 255 / 12.92 : ((x / 255 + 0.055) / 1.055) ** 2.4))
          return 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (b ?? 0)
        }
        const bg = lum(rgb(getComputedStyle(el).backgroundColor))
        let low = Infinity
        for (const one of el.querySelectorAll('.position-run-key, .position-run-path, .position-run-path b, .position-run-num, .review-caption-end, .review-caption-nb, .review-caption-this')) {
          if ((one.textContent ?? '').trim() === '') continue
          const fg = lum(rgb(getComputedStyle(one).color))
          const [hi, lo] = fg > bg ? [fg, bg] : [bg, fg]
          low = Math.min(low, (hi + 0.05) / (lo + 0.05))
        }
        return low
      })
      expect(worst, `the chip's lowest text contrast in ${theme}`).toBeGreaterThanOrEqual(4.5)

      /* F3: the place label is one line, its parts on one baseline. */
      const tops = await chip.locator('.position-run-key, .position-run-num').evaluateAll((els) =>
        els.map((one) => Math.round(one.getBoundingClientRect().bottom)),
      )
      expect(Math.max(...tops) - Math.min(...tops), 'label parts share a line').toBeLessThanOrEqual(6)

      /* F4: where the card column is narrow the chip sits under the photograph, not on it. */
      if (size.width < 900) {
        const well = await page.locator('.review-well').boundingBox()
        const box = await chip.boundingBox()
        if (well === null || box === null) throw new Error('no well or chip')
        expect(box.y).toBeGreaterThanOrEqual(well.y + well.height - 1)
      }
      await shot(page, `review-${size.width}-${theme}`)
    })
  }
}

for (const theme of ['light', 'dark'] as const) {
  test(`Pricing, photo missing, ${theme}: the sheet says so and offers a re-shoot`, async ({ page }) => {
    await page.route(/\/photo\//, (route) => route.fulfill({ status: 404, body: '' }))
    await seedPopulatedPricing(page)
    await page.goto('/#/pricing')
    await page.evaluate((t) => document.documentElement.setAttribute('data-theme', t), theme)
    await page.locator('.pricing-thumb').first().click()
    const panel = page.getByRole('dialog').locator('.pricing-photo-frame')
    await expect(panel).toBeVisible()
    await expectPlain(panel)
    await shot(page, `pricing-sheet-${theme}`)
  })
}
