// Protects: The floating price-history card opens by focus or by its door, sits above its row by default, covers neither the row nor the next price field, keeps focus where its mode says, holds its size while history loads, and draws the product chart with the owner's asking step line and the suggestion dot.
// Governs: D313, D278, D227
import { test, expect, type Locator, type Page } from '@playwright/test'
import { sealEveryTest } from './shell'
import { setViewport } from './phoneSwitch'
import { productHistory } from './routeFixtures'
import { markNow, readShifts, sumOf, watchShifts } from './layoutShift'
import { settleMotion } from './motionSettled'
import { scanMoneyFace } from './moneyFace'
import type { AskingPosting, ProductHistoryPayload } from '../src/types'

/* THE CONTRACT THIS FILE PINS. `#/gallery` and `app/src/HistoryFloat.tsx` must match it.
 *
 * GALLERY. `[data-kit-section="history-float"]` on `#/gallery` holds exactly three rows, each
 * `[data-float-row="<i>"]` with one price field `[data-float-price]` and one history door
 * `[data-float-door]`, and one thumb `[data-float-thumb]` (the product photo, `PricingThumb` in the
 * mockup). Row 1 is the anchor in every case, row 0 is above it and row 2 below.
 * The price field is each row's only tab stop, so the door is `tabIndex={-1}`. Row 1 carries a
 * suggestion, and the sales fills are non-empty, so the chart has marks to assert. The section is not the last on the gallery, so a row can scroll to the top.
 *
 * CARD. `[data-history-float]`, mounted only while open (closed means absent). Attributes:
 *   data-mode       "focus" | "door"
 *   data-placement  "above" | "below"
 *   data-state      "loading" | "ready"
 *   data-row        the index of the row it is anchored to
 * A focus-opened card has no tab stop, so its close button is `tabIndex={-1}`.
 * Its close button is `[data-history-float-close]`. Its right edge sits on the row's history door.
 * Its legend holds "Low to high, each week". Its heading is "Last 90 days". "Full history" is a
 * text button (`role=button`), and its facts are four `dt` labels: Market, Lowest, Lowest,
 * shipped, and Direct Low.
 *
 * PROPS (HistoryFloat.tsx). `sku`, `anchor` (the row element), `mode` ("focus" | "door"),
 * `fills` (the owner's sales for the chart), `suggestion` (a money string, optional), `onClose`,
 * and `restoreFocus` (the door, which takes focus back in door mode). The card loads history
 * with `getProductHistory(sku)`, so its loading state is the gap before that answer.
 *
 * CHART MARKS INSIDE THE CARD. `.producthistory-chart`, `.producthistory-market-line` and
 * `.producthistory-spread` and `.producthistory-fill-mark` come from `ProductChart`. The asking
 * price is `[data-float="asking"]`, a dashed path with H and V runs (a step). The suggestion is
 * `[data-float="suggestion"]`, one circle.
 */

sealEveryTest({ store: true })

const GALLERY = '/#/gallery'
const CARD = '[data-history-float]'
const HISTORY = /\/pipeline\/products\/[^/]+\/history$/
const SIZES = [
  { width: 1440, height: 900 },
  { width: 1200, height: 900 },
  { width: 820, height: 900 },
] as const

const row = (page: Page, i: number) => page.locator(`[data-float-row="${i}"]`)
const priceOf = (page: Page, i: number) => row(page, i).locator('[data-float-price]')
const doorOf = (page: Page, i: number) => row(page, i).locator('[data-float-door]')
const card = (page: Page) => page.locator(CARD)

type Box = { x: number; y: number; width: number; height: number }

/* Two boxes share area. Edges that only touch do not count. */
const meets = (a: Box, b: Box) =>
  a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height

async function boxOf(loc: Locator): Promise<Box> {
  const box = await loc.boundingBox()
  expect(box, 'the element has a box').not.toBeNull()
  return box!
}

/* Rows 0 to 2 in page coordinates, so a scroll that Tab causes does not read as the list moving.
 * Settled first: `bn-page-in` moves the page by a few px over its entry, so a read taken inside
 * that window is a real position the page is still leaving (see `motionSettled.ts`). */
async function listGeometry(page: Page): Promise<Box[]> {
  await settleMotion(page)
  return page.evaluate(() =>
    [0, 1, 2].map((i) => {
      const r = document.querySelector(`[data-float-row="${i}"]`)!.getBoundingClientRect()
      return { x: r.x, y: r.y + window.scrollY, width: r.width, height: r.height }
    }),
  )
}

/* Row 1 at a fixed distance from the viewport top, away from both edges. The sticky banner slot
 * (`.bn-banner-slot`) covers the bottom 144px when a banner shows, and Playwright answers a covered
 * click by scrolling the row somewhere else, which flips the placement the case set up. */
async function placeRow(page: Page, top: number) {
  await row(page, 1).evaluate((el, t) => window.scrollBy({ top: el.getBoundingClientRect().top - t, behavior: 'instant' }), top)
  await settleMotion(page)
  expect(Math.abs((await boxOf(row(page, 1))).y - top), `row 1 sits ${top}px from the top`).toBeLessThanOrEqual(2)
}

async function openByFocus(page: Page, i = 1) {
  await priceOf(page, i).click()
  await expect(card(page)).toHaveAttribute('data-mode', 'focus')
}

/* Two asking postings, so the step line has a change to draw. */
function payloadWithAsking(): ProductHistoryPayload {
  const asking: AskingPosting[] = [
    { at: Date.UTC(2026, 6, 20) / 1000, price: '14.00', source: 'emit', replaced: null },
    { at: Date.UTC(2026, 7, 3) / 1000, price: '16.50', source: 'suggested', replaced: '14.00' },
  ]
  return { ...productHistory(), asking_postings: asking }
}

for (const size of SIZES) {
  test.describe(`at ${size.width} wide`, () => {
    test.beforeEach(async ({ page }) => {
      await setViewport(page, size)
      await watchShifts(page)
      await page.route(HISTORY, (route) =>
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payloadWithAsking()) }),
      )
      await page.goto(GALLERY)
      await expect(page.locator('[data-kit-section="history-float"]')).toBeVisible()
    })

    test('the card draws the product chart, the asking step line and the suggestion dot', async ({ page }) => {
      await openByFocus(page)
      const c = card(page)
      await expect(c.locator('.producthistory-chart')).toHaveCount(1)
      await expect(c.locator('.producthistory-market-line')).toHaveCount(1)
      await expect(c.locator('.producthistory-spread').first()).toBeAttached()
      await expect(c.locator('.producthistory-fill-mark').first()).toBeAttached()

      const asking = c.locator('[data-float="asking"]')
      await expect(asking).toHaveCount(1)
      const dash = await asking.evaluate((el) => getComputedStyle(el).strokeDasharray)
      expect(dash, 'the asking line is dashed').not.toBe('none')
      const d = (await asking.getAttribute('d')) ?? ''
      expect(d, 'the asking line is a step: M, then only H and V runs').toMatch(/^M[^A-Za-z]*(?:[HV][^A-Za-z]*)+$/)

      await expect(c.locator('[data-float="suggestion"]')).toHaveCount(1)
    })

    test('by default the card opens above its row and never covers the anchor row or its price field', async ({ page }) => {
      await placeRow(page, 600)
      expect((await boxOf(row(page, 1))).y, 'there is room above the row').toBeGreaterThan(400)
      await openByFocus(page)

      await expect(card(page)).toHaveAttribute('data-placement', 'above')
      const c = await boxOf(card(page))
      const anchor = await boxOf(row(page, 1))
      expect(c.y + c.height, 'the card ends above the row').toBeLessThanOrEqual(anchor.y)
      expect(meets(c, anchor), 'the card does not cover the row').toBe(false)
      expect(meets(c, await boxOf(priceOf(page, 1))), 'the card does not cover the anchor price field').toBe(false)
      /* Opened above, the card may cover the price fields of the rows above; nothing is asserted for row 0. */
    })

    test('with no room above, the card opens below and its right edge sits left of the price column', async ({ page }) => {
      await placeRow(page, 100)
      expect((await boxOf(row(page, 1))).y, 'the row sits at the top, so there is no room above').toBeLessThan(120)
      await openByFocus(page)

      await expect(card(page)).toHaveAttribute('data-placement', 'below')
      const c = await boxOf(card(page))
      const anchor = await boxOf(row(page, 1))
      expect(c.y, 'the card starts below the row').toBeGreaterThanOrEqual(anchor.y + anchor.height)
      expect(meets(c, anchor), 'the card does not cover the row').toBe(false)
      expect(meets(c, await boxOf(priceOf(page, 1))), 'the card does not cover the anchor price field').toBe(false)
      expect(meets(c, await boxOf(priceOf(page, 2))), 'the card does not cover the next row price field').toBe(false)
      const next = await boxOf(priceOf(page, 2))
      expect(c.x + c.width, 'the card right edge is left of the price column').toBeLessThanOrEqual(next.x)
      /* At 820 the card may cover names when opened below, so nothing is asserted against names here. */
    })

    test('the next price field stays uncovered in every state that requires it, in rows 1 and 2', async ({ page }) => {
      await placeRow(page, 100)
      for (const i of [1, 2]) {
        await openByFocus(page, i)
        const c = await boxOf(card(page))
        expect(meets(c, await boxOf(priceOf(page, i))), `the card does not cover price field ${i}`).toBe(false)
        if ((await card(page).getAttribute('data-placement')) === 'below' && i < 2) {
          expect(meets(c, await boxOf(priceOf(page, i + 1))), `opened below, the card does not cover price field ${i + 1}`).toBe(false)
        }
        await page.keyboard.press('Escape')
      }
    })

    test('in a short viewport the card takes the side with more room, fits the viewport and keeps Full history reachable', async ({ page }) => {
      await row(page, 1).evaluate((el) => el.scrollIntoView({ block: 'center' }))
      await openByFocus(page)
      const c = await boxOf(card(page))
      const view = page.viewportSize()!
      expect(c.x, 'inside on the left').toBeGreaterThanOrEqual(0)
      expect(c.y, 'inside on the top').toBeGreaterThanOrEqual(0)
      expect(c.x + c.width, 'inside on the right').toBeLessThanOrEqual(view.width)
      expect(c.y + c.height, 'inside on the bottom').toBeLessThanOrEqual(view.height)
      const anchor = await boxOf(row(page, 1))
      const roomAbove = anchor.y
      const roomBelow = view.height - (anchor.y + anchor.height)
      await expect(card(page)).toHaveAttribute('data-placement', roomAbove >= roomBelow ? 'above' : 'below')
      const full = await boxOf(card(page).getByRole('button', { name: 'Full history', exact: true }))
      expect(full.y + full.height, 'Full history is inside the viewport').toBeLessThanOrEqual(view.height)
      expect(full.y, 'Full history is inside the viewport').toBeGreaterThanOrEqual(0)
      expect(meets(c, await boxOf(priceOf(page, 1))), 'the card does not cover the anchor price field').toBe(false)
    })

    test("the chart's top axis label is not clipped by the chart box", async ({ page }) => {
      await openByFocus(page)
      await expect(card(page)).toHaveAttribute('data-state', 'ready')
      const chart = await boxOf(card(page).locator('.hfloat-chart'))
      const ticks = card(page).locator('.producthistory-tick-price')
      const n = await ticks.count()
      expect(n, 'the chart has price labels').toBeGreaterThan(0)
      let top: Box | null = null
      for (let i = 0; i < n; i++) {
        const b = await boxOf(ticks.nth(i))
        if (top === null || b.y < top.y) top = b
      }
      expect(top!.y, 'the top label starts inside the chart').toBeGreaterThanOrEqual(chart.y)
      expect(top!.y + top!.height, 'the top label ends inside the chart').toBeLessThanOrEqual(chart.y + chart.height)
    })

    test('a card opened by focus takes no focus, and nothing in the list moves', async ({ page }) => {
      const before = await listGeometry(page)
      await priceOf(page, 1).click()
      await expect(card(page)).toHaveAttribute('data-mode', 'focus')

      await expect(priceOf(page, 1)).toBeFocused()
      const focusInCard = await page.evaluate(() => !!document.activeElement?.closest('[data-history-float]'))
      expect(focusInCard, 'focus stayed in the price field').toBe(false)
      expect(await listGeometry(page)).toEqual(before)
    })

    test('Tab moves the card to the next row, and the list does not move', async ({ page }) => {
      await openByFocus(page)
      const before = await listGeometry(page)

      await page.keyboard.press('Tab')
      await expect(priceOf(page, 2)).toBeFocused()
      await expect(card(page)).toHaveAttribute('data-row', '2')
      await expect(card(page)).toHaveAttribute('data-mode', 'focus')
      expect(await listGeometry(page)).toEqual(before)
    })

    test('the door opens the card and takes focus into it, and Esc gives focus back to the door', async ({ page }) => {
      await doorOf(page, 1).click()
      await expect(card(page)).toHaveAttribute('data-mode', 'door')

      const inside = await page.evaluate(() => !!document.activeElement?.closest('[data-history-float]'))
      expect(inside, 'focus moved into the card').toBe(true)

      await page.keyboard.press('Escape')
      await expect(card(page)).toHaveCount(0)
      await expect(doorOf(page, 1)).toBeFocused()
    })

    test('Esc closes a card opened by focus, and the field keeps focus', async ({ page }) => {
      await openByFocus(page)
      await page.keyboard.press('Escape')
      await expect(card(page)).toHaveCount(0)
      await expect(priceOf(page, 1)).toBeFocused()
    })

    test('focus leaving the price fields closes a card opened by focus', async ({ page }) => {
      await priceOf(page, 2).click()
      await expect(card(page)).toHaveAttribute('data-mode', 'focus')

      await page.keyboard.press('Tab')
      await expect(card(page)).toHaveCount(0)
    })

    test('the close button closes the card and gives focus back to the door', async ({ page }) => {
      await doorOf(page, 1).click()
      await card(page).locator('[data-history-float-close]').click()
      await expect(card(page)).toHaveCount(0)
      await expect(doorOf(page, 1)).toBeFocused()
    })

    test('the card holds its size from first paint while history loads', async ({ page }) => {
      let release!: () => void
      const gate = new Promise<void>((done) => (release = done))
      await page.route(HISTORY, async (route) => {
        await gate
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payloadWithAsking()) })
      })

      const t0 = await markNow(page)
      await priceOf(page, 1).click()
      await expect(card(page)).toHaveAttribute('data-state', 'loading')
      const first = await boxOf(card(page))

      release()
      await expect(card(page)).toHaveAttribute('data-state', 'ready')
      const loaded = await boxOf(card(page))
      expect(loaded.width, 'width holds while history loads').toBeCloseTo(first.width, 0)
      expect(loaded.height, 'height holds while history loads').toBeCloseTo(first.height, 0)
      const { shifts } = await readShifts(page)
      expect(sumOf(shifts.filter((s) => s.at >= t0)), 'nothing on the page moved while history loaded').toBe(0)
    })

    test('the card draws from --bn tokens, and every price carries bn-money', async ({ page }) => {
      await openByFocus(page)
      /* A probe takes the token's own colour, so the card matches a token and no literal. The
         literal ban itself is `make docs-audit`'s `raw color` row, which reads the source. */
      const surface = await page.evaluate(() => {
        const probe = document.createElement('div')
        probe.style.backgroundColor = 'var(--bn-surface)'
        document.body.appendChild(probe)
        const want = getComputedStyle(probe).backgroundColor
        probe.remove()
        return { got: getComputedStyle(document.querySelector('[data-history-float]')!).backgroundColor, want }
      })
      expect(surface.got, 'the card surface is the --bn-surface token').toBe(surface.want)
      /* Every dollar figure in the card is drawn in the mono face, which is what the owner sees. */
      const face = await page.evaluate(scanMoneyFace, CARD)
      expect(face.noView, 'the card was scanned').toBe(false)
      expect(face.text, 'a dollar figure in the card is not drawn in mono').toEqual([])

      /* And each dollar figure carries the class itself, not only the face it inherits. */
      const bare = await card(page).evaluate((root) => {
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
        const out: string[] = []
        for (let n = walker.nextNode(); n; n = walker.nextNode()) {
          const t = n.textContent ?? ''
          if (/\$\d/.test(t) && !n.parentElement?.closest('.bn-money')) out.push(t.trim())
        }
        return out
      })
      expect(bare, 'every dollar figure in the card carries bn-money').toEqual([])
      expect(await card(page).locator('.bn-money').count(), 'the four prices are there').toBeGreaterThanOrEqual(4)
    })

    test("the card's right edge sits on its row's history door", async ({ page }) => {
      /* The door edge is the above placement's rule. Below, the card sits left of the price column (the
       * case above), so put row 1 low enough that there is room above, whatever the load position. */
      await placeRow(page, 600)
      expect((await boxOf(row(page, 1))).y, 'there is room above the row').toBeGreaterThan(400)
      await openByFocus(page)
      await expect(card(page)).toHaveAttribute('data-placement', 'above')
      const c = await boxOf(card(page))
      const door = await boxOf(doorOf(page, 1))
      expect(Math.abs(c.x + c.width - (door.x + door.width)), 'the card right edge is on the door right edge').toBeLessThanOrEqual(1)
    })

    test('the card covers no thumb of any gallery row', async ({ page }) => {
      await openByFocus(page)
      const c = await boxOf(card(page))
      for (const i of [0, 1, 2]) {
        const thumb = row(page, i).locator('[data-float-thumb]')
        await expect(thumb, `row ${i} shows its thumb`).toHaveCount(1)
        expect(meets(c, await boxOf(thumb)), `the card does not cover the thumb in row ${i}`).toBe(false)
      }
    })

    test('the legend names the spread as Low to high, each week', async ({ page }) => {
      await openByFocus(page)
      await expect(card(page).locator('.hfloat-legend > span', { hasText: 'Low to high, each week' })).toHaveCount(1)
    })

    test('the card has a Last 90 days heading', async ({ page }) => {
      await openByFocus(page)
      await expect(card(page).getByRole('heading', { name: 'Last 90 days', exact: true })).toHaveCount(1)
    })

    test('Full history is a text button in the card', async ({ page }) => {
      await openByFocus(page)
      await expect(card(page).getByRole('button', { name: 'Full history', exact: true })).toHaveText('Full history')
    })

    test('the card shows four prices: Market, Lowest, Lowest, shipped, and Direct Low', async ({ page }) => {
      await openByFocus(page)
      await expect(card(page).locator('.hfloat-facts dt')).toHaveText(['Market', 'Lowest', 'Lowest, shipped', 'Direct Low'])
    })
  })
}
