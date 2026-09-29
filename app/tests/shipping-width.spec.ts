// Protects: The empty states of Shipping, Orders and Review fill the frame to one cap, centered, and Shipping's loaded lanes leave no band.
// Governs: D197, D309
import { expect, test, type Page } from '@playwright/test'
import { sealEveryTest, settleAnimations } from './shell'
import { batchOf, shippingRow as row } from './routeFixtures'

/* AN EMPTY STATE FILLS THE FRAME TO ONE CAP, CENTRED (D309).
 * `.shipping-empty` was capped at 880px and `.orders-empty`, `.review-lone` at 720px inside a frame
 * up to 1600px: a band of 500px at 1440, 700px at 2000. WHAT THIS MEASURES: each state's block is
 * as wide as the smaller of the frame and `--bn-empty-w`, and is centered in the frame. Shipping's
 * loaded lanes must reach the frame's right edge. */

sealEveryTest()

const SLACK = 2
const EMPTY_W = 960

const SCREENS = [
  { name: 'Shipping', block: '.shipping-empty' },
  { name: 'Orders', block: '.orders-empty' },
  { name: 'Review', block: '.review-done' },
] as const

const json = (body: unknown) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })

async function stubReads(page: Page): Promise<void> {
  await page.route(/\/orders$/, (r) => r.fulfill(json({ summary: 'no orders', orders: [], resolution: { orders: [], counts: {} } })))
  await page.route(/\/inventory$/, (r) => r.fulfill(json({ version: 2, cards: {}, boxes: {}, listings: {} })))
  await page.route(/\/shipping\/batches$/, (r) =>
    r.fulfill(json(batchOf([row({ lane: 'parcel' }), row({ order: 'B31A0C7D-0001A2-00311', lane: 'unjudged' })]))),
  )
  await page.route(/\/queues$/, (r) => r.fulfill(json({ review: [], parked: [] })))
  await page.route(/\/pipeline\/(waiting|runs|submissions|preflight)$/, (r) =>
    r.fulfill(json({ keys: [], claimed: 0, runs: [], claims: [], counts: { claims: 0, keys: 0, stale: 0 } })),
  )
  await page.route(/\/boxes$/, (r) => r.fulfill(json({ boxes: [] })))
  await page.route(/\/games$/, (r) => r.fulfill(json({ games: [] })))
}

const frameOf = (page: Page, sel: string) =>
  page.evaluate((s) => {
    const el = document.querySelector('.bn-page')!
    const cs = getComputedStyle(el)
    const r = el.getBoundingClientRect()
    // The content box: the page's own inset is not a band.
    const frame = { left: r.left + parseFloat(cs.paddingLeft), right: r.right - parseFloat(cs.paddingRight), width: r.width - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) }
    const b = document.querySelector(s)!.getBoundingClientRect()
    return { frameW: frame.width, w: b.width, left: b.left - frame.left, right: frame.right - b.right }
  }, sel)

for (const theme of ['light', 'dark'] as const) {
  for (const [width, height] of [
    [1440, 900],
    [820, 1100],
    [2000, 1300],
  ] as const) {
    test.describe(`${width}, ${theme}`, () => {
      test.beforeEach(async ({ page }) => {
        if (width === 2000) {
          await page.addInitScript(() => {
            try {
              /* eslint-disable-next-line no-restricted-syntax -- seeding the shell's own device key before first paint, as `capture-width.spec.ts` does. */
              window.localStorage.setItem('banchi.rail', 'rail')
            } catch {
              /* unreadable storage reads as the sidebar, a real default */
            }
          })
        }
        await stubReads(page)
        await page.setViewportSize({ width, height })
        await page.emulateMedia({ colorScheme: theme })
      })

      for (const { name, block } of SCREENS) {
        test(`${name} empty state fills the frame to one cap, centered`, async ({ page }) => {
          await page.goto(`/#/${name.toLowerCase()}`)
          await page.locator(block).waitFor()
          await settleAnimations(page)
          const m = await frameOf(page, block)
          expect(m.w, `${Math.round(m.w)}px block in a ${Math.round(m.frameW)}px frame`).toBeGreaterThanOrEqual(Math.min(m.frameW, EMPTY_W) - SLACK)
          expect(m.w).toBeLessThanOrEqual(EMPTY_W + SLACK)
          expect(Math.abs(m.left - m.right), 'centered').toBeLessThanOrEqual(SLACK)
          await page.screenshot({ path: `/tmp/empty-${name}-${width}-${theme}.png` })
        })
      }

      test('Shipping loaded lanes reach the frame edge', async ({ page }) => {
        await page.goto('/#/shipping')
        await page.locator('.shipping-empty').waitFor()
        await page.getByLabel('Read an export').setInputFiles({ name: 'x.csv', mimeType: 'text/csv', buffer: Buffer.from('Order #\nA\n') })
        await page.locator('.shipping-lanes').waitFor()
        await settleAnimations(page)
        const m = await frameOf(page, '.shipping-lanes')
        expect(m.right, `${Math.round(m.right)}px unpainted right of the loaded lanes`).toBeLessThanOrEqual(SLACK)
        await page.screenshot({ path: `/tmp/loaded-Shipping-${width}-${theme}.png` })
      })
    })
  }
}
