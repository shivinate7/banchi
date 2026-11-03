// Protects: The floating price-history card opens by focus or by its door, sits above its row by default, covers neither the row nor the next price field, keeps focus where its mode says, holds its size while history loads, and draws the product chart with the owner's asking step line and the suggestion dot. Its name carries the full card name as a title. On `#/pricing` it opens above the focused row, follows that row when the list above changes, and stays open while focus is in the list. It reads a row's history and prices once, only for the row where focus rests, and tries a failed sales read again on the next open. A send ends its kept reads, so the next open reads again, and a read begun before the send is not served after it. With no room above a row it opens below, inside the list, ending 8px left of the price column and clear of the sidebar or rail, and opened above it never overlaps the Send bar. Its title names the row whose price field has focus. Esc closes it and leaves focus in the price field. Each `#/pricing` row, a kept-off one too, has a history door that opens the card for that row, takes focus and gives it back on Esc.
// Governs: D313, D278, D227
import { test, expect, type Locator, type Page } from '@playwright/test'
import { sealEveryTest } from './shell'
import { setViewport } from './phoneSwitch'
import { productHistory } from './routeFixtures'
import { markNow, readShifts, sumOf, watchShifts } from './layoutShift'
import { afterPaint, settleMotion } from './motionSettled'
import { scanMoneyFace } from './moneyFace'
import { seedPopulatedPricing, order, line, payloadOf, sendSummary } from './routeFixtures'
import type { AskingPosting, LiveListing, ProductHistoryPayload } from '../src/types'

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
 * Its legend holds "Low to high, each week". Its heading is "Last 90 days". "Full History" (a button takes Title Case, docs/DESIGN.md R5) is a
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
  /* SETTLED BEFORE THE FIRST READ, NOT ONLY AFTER THE SCROLL: `.bn-page` still runs `bn-page-in`, a 6px rise, when the
   * scroll offset is taken off `getBoundingClientRect().top`, so the scroll lands 2.3 to 2.9px off under load. */
  await settleMotion(page)
  await row(page, 1).evaluate((el, t) => window.scrollBy({ top: el.getBoundingClientRect().top - t, behavior: 'instant' }), top)
  await settleMotion(page)
  expect(Math.abs((await boxOf(row(page, 1))).y - top), `row 1 sits ${top}px from the top`).toBeLessThanOrEqual(2)
}

async function openByFocus(page: Page, i = 1) {
  await priceOf(page, i).click()
  await expect(card(page)).toHaveAttribute('data-mode', 'focus')
}

/* THE ONE STEP FOR "THE CARD HAS READ", run before any case that counts or scans what the card draws.
 * The card reads only after focus rests on its row (D278), so right after `openByFocus` it is still
 * "loading" and holds no figure. `data-state` flips when the history lands; the facts come from a
 * second read and each shows its dash until that lands too. A condition, never a pause. */
async function cardLoaded(page: Page) {
  await expect(card(page)).toHaveAttribute('data-state', 'ready')
  await expect(card(page).locator('.hfloat-facts dd:not(:has(.bn-money, .hfloat-quiet))'), 'every fact has its answer, a price or "not carried"').toHaveCount(0)
}

/* The gap between the card's bottom edge and `anchor`'s top edge: positive when the card is above it. */
async function gapAbove(page: Page, anchor: Locator): Promise<number> {
  const c = await boxOf(card(page))
  const a = await boxOf(anchor)
  return a.y - (c.y + c.height)
}

/* A row added in front of `row`, and a row folded away. NO CONTROL FOLDS A GROUP YET, so both change
 * the list in the DOM, the way an added row or a folded group does. The card must follow its row
 * whatever draws the change. */
const addRowAbove = (row: Locator) =>
  row.evaluate((el) => {
    const added = document.createElement('div')
    added.setAttribute('aria-hidden', 'true')
    added.style.height = '96px'
    el.before(added)
  })
const foldRow = (row: Locator) =>
  row.evaluate((el) => {
    el.style.display = 'none'
  })

/* THE ONE STEP FOR "THE LIST ABOVE THE OPEN CARD CHANGED", run on the gallery specimen and on `#/pricing`.
 * Focus the row's price field, change the list so `row` moves in the viewport, and the card is still
 * above `row` at the distance it had (the door-edge tolerance of 1px). The browser's own scroll
 * anchoring is off for the change, so the row really moves. */
async function expectCardFollowsRow(page: Page, row: Locator, price: Locator, change: () => Promise<void>, way: 'down' | 'up') {
  await price.click()
  await expect(card(page)).toHaveAttribute('data-mode', 'focus')
  await expect(card(page)).toHaveAttribute('data-placement', 'above')
  const before = await gapAbove(page, row)
  expect(before, 'the card starts above the row').toBeGreaterThanOrEqual(0)
  const top = (await boxOf(row)).y

  await page.evaluate(() => {
    document.documentElement.style.overflowAnchor = 'none'
  })
  await change()
  const moved = (await boxOf(row)).y - top
  expect(way === 'down' ? moved : -moved, `the row moved ${way} with the list`).toBeGreaterThan(30)

  await expect.poll(async () => Math.abs((await gapAbove(page, row)) - before), `the card moved ${way} with its row`).toBeLessThanOrEqual(1)
  await expect(card(page)).toHaveAttribute('data-placement', 'above')
  expect(await gapAbove(page, row), 'the card still ends above the row').toBeGreaterThanOrEqual(0)
}

/* Two asking postings, so the step line has a change to draw. */
function payloadWithAsking(): ProductHistoryPayload {
  const asking: AskingPosting[] = [
    { at: Date.UTC(2026, 6, 20) / 1000, price: '14.00', source: 'emit', replaced: null },
    { at: Date.UTC(2026, 7, 3) / 1000, price: '16.50', source: 'suggested', replaced: '14.00' },
  ]
  return { ...productHistory(), asking_postings: asking }
}

/* The same history once the owner's price has gone out: one more asking posting, inside the chart's range, so the
 * step line gains a step (a `V` run) the line before it did not have. */
function payloadAfterSend(): ProductHistoryPayload {
  const before = payloadWithAsking()
  const posting: AskingPosting = { at: Date.UTC(2026, 7, 28, 12) / 1000, price: '17.25', source: 'suggested', replaced: '16.50' }
  return { ...before, asking_postings: [...(before.asking_postings ?? []), posting] }
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

    test('in a short viewport the card takes the side with more room, fits the viewport and keeps Full History reachable', async ({ page }) => {
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
      const full = await boxOf(card(page).getByRole('button', { name: 'Full History', exact: true }))
      expect(full.y + full.height, 'Full History is inside the viewport').toBeLessThanOrEqual(view.height)
      expect(full.y, 'Full History is inside the viewport').toBeGreaterThanOrEqual(0)
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
      await cardLoaded(page)
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

    test('Full History is a text button in the card, in Title Case (R5)', async ({ page }) => {
      await openByFocus(page)
      await expect(card(page).getByRole('button', { name: 'Full History', exact: true })).toHaveText('Full History')
    })

    test('the card shows four prices: Market, Lowest, Lowest, shipped, and Direct Low', async ({ page }) => {
      await openByFocus(page)
      await expect(card(page).locator('.hfloat-facts dt')).toHaveText(['Market', 'Lowest', 'Lowest, shipped', 'Direct Low'])
    })

    /* The name is cut to one line by an ellipsis (`.hfloat-name`), so its title is the way to read all of it. */
    test("the card's name carries the full card name as its title once history loads, and no title while it loads", async ({ page }) => {
      const FULL = 'Pikachu with Grey Felt Hat, SVP 085, Black Star Promos, Near Mint Holofoil, a name long enough that the ellipsis cuts it'
      let release!: () => void
      const gate = new Promise<void>((done) => (release = done))
      await page.route(HISTORY, async (route) => {
        await gate
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...payloadWithAsking(), name: FULL }) })
      })

      await priceOf(page, 1).click()
      await expect(card(page)).toHaveAttribute('data-state', 'loading')
      const name = card(page).locator('.hfloat-name')
      expect(await name.getAttribute('title'), 'no title while history loads').toBeNull()

      release()
      await expect(card(page)).toHaveAttribute('data-state', 'ready')
      await expect(name, 'the name is the loaded card name').toHaveText(FULL)
      await expect(name, 'its title is the whole name').toHaveAttribute('title', FULL)
    })

    /* The card measures its row when it opens, on resize and on scroll. A row that moves on its own, because
     * the list above it changed, is a move the card must follow, or it floats over the wrong place. */
    test('a row added above the open card keeps the card above its row', async ({ page }) => {
      await placeRow(page, 600)
      await expectCardFollowsRow(page, row(page, 1), priceOf(page, 1), () => addRowAbove(row(page, 1)), 'down')
    })

    test('rows above the open card folding away keep the card above its row', async ({ page }) => {
      await placeRow(page, 600)
      await expectCardFollowsRow(page, row(page, 1), priceOf(page, 1), () => foldRow(row(page, 0)), 'up')
    })
  })
}

/* ---- `#/pricing`: THE CARD'S ONE CALL SITE (spec `docs/specs/pricing-suggest.md` section 9c) --------
 *
 * OWNER RULING. On `#/pricing` the card opens when a price field takes focus, ABOVE its row, and
 * stays open while focus is anywhere in the list (`.pricing-list`). It closes on Esc, on its close
 * button, and when focus leaves the list for anything but the card. The gallery cases above pin the
 * card; these pin the mount, so each reads the real screen over `seedPopulatedPricing` (two rows in
 * "Going at the Rule", the second row has a row above it, and both have room above at every size).
 *
 * A row's tab stops, in order: price field, "Keep <name> off TCGplayer", the next row's photo
 * button, its name link, then its price field. The card keeps its row through the first three.
 *
 * The reflow cases share `expectCardFollowsRow` with the gallery cases above.
 */
const PRICING = '/#/pricing'
const listRow = (page: Page, i: number) => page.locator('.pricing-row').nth(i)
const listPrice = (page: Page, i: number) => listRow(page, i).getByRole('textbox', { name: /^Price for / })

/** The SKU a row's name link opens, so a case can tell which product the card was asked about. */
async function skuOfRow(page: Page, i: number): Promise<string> {
  const href = (await listRow(page, i).locator('a.pricing-name').getAttribute('href')) ?? ''
  const sku = /[?&]sku=([^&]+)/.exec(href)?.[1]
  expect(sku, `row ${i} name link names its SKU (${href})`).toBeTruthy()
  return decodeURIComponent(sku!)
}

/** A live listing whose suggestion starts ticked (Suggested changes). A worklist that carries one draws the Send bar,
 * which `seedPopulatedPricing` alone does not. */
const LIVE_SKU = '8609901'
const liveListing = (over: Partial<LiveListing> = {}): LiveListing => ({
  sku: LIVE_SKU, name: 'Gardevoir ex', set_name: 'Scarlet and Violet', image_url: null, market: '4.22', low: '4.35',
  asking: '3.40', last_sold_at: null, group: 'suggested', price: '4.01', source: 'Suggested', reason: 'Market up 18% since listed.', ...over,
})

for (const size of SIZES) {
  test.describe(`#/pricing at ${size.width} wide`, () => {
    let asked: string[]
    test.beforeEach(async ({ page }) => {
      asked = []
      await setViewport(page, size)
      await seedPopulatedPricing(page)
      await page.route(HISTORY, (route) => {
        asked.push(/\/products\/([^/]+)\/history$/.exec(new URL(route.request().url()).pathname)?.[1] ?? '')
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payloadWithAsking()) })
      })
      await page.goto(PRICING)
      await expect(page.locator('.pricing-row')).toHaveCount(2)
      await settleMotion(page)
    })

    test("focusing a row's price field opens the card above that row, for that row's product", async ({ page }) => {
      for (const i of [0, 1]) {
        await listPrice(page, i).click()
        await expect(card(page), `row ${i}: the price field took focus, so the card is open`).toHaveAttribute('data-mode', 'focus')
        await expect(card(page)).toHaveAttribute('data-placement', 'above')
        const c = await boxOf(card(page))
        const anchor = await boxOf(listRow(page, i))
        expect(c.y + c.height, `row ${i}: the card ends above the row`).toBeLessThanOrEqual(anchor.y)
        expect(meets(c, anchor), `row ${i}: the card does not cover the row`).toBe(false)
        const sku = await skuOfRow(page, i)
        await expect.poll(() => asked.at(-1), `row ${i}: the card asked for this row's history`).toBe(sku)
        await expect(listPrice(page, i)).toBeFocused()
        await page.keyboard.press('Escape')
        await expect(card(page)).toHaveCount(0)
      }
    })

    test('a row added above the open card keeps the card above its row', async ({ page }) => {
      await expectCardFollowsRow(page, listRow(page, 1), listPrice(page, 1), () => addRowAbove(listRow(page, 1)), 'down')
    })

    test('rows above the open card folding away keep the card above its row', async ({ page }) => {
      await expectCardFollowsRow(page, listRow(page, 1), listPrice(page, 1), () => foldRow(listRow(page, 0)), 'up')
    })

    test('Tab to other controls in the list keeps the card open on its row, and focus leaving the list closes it', async ({ page }) => {
      await listPrice(page, 0).click()
      await expect(card(page)).toHaveAttribute('data-mode', 'focus')
      const home = await gapAbove(page, listRow(page, 0))
      expect(home, 'the card starts above row 0').toBeGreaterThanOrEqual(0)

      /* Tab on until the next price field has focus. Every stop before it is another control in the list. */
      let between = 0
      for (;;) {
        await page.keyboard.press('Tab')
        if (await listPrice(page, 1).evaluate((el) => el === document.activeElement)) break
        between++
        expect(between, 'Tab reaches the next price field within a few stops').toBeLessThan(8)
        const at = await page.evaluate(() => {
          const a = document.activeElement
          return { inList: !!a?.closest('.pricing-list'), price: !!a?.matches('input[aria-label^="Price for "]') }
        })
        expect(at, `stop ${between}: Tab landed on another control in the list`).toEqual({ inList: true, price: false })
        await afterPaint(page)
        await expect(card(page), `stop ${between}: the card is still open`).toHaveAttribute('data-mode', 'focus')
        expect(Math.abs((await gapAbove(page, listRow(page, 0))) - home), `stop ${between}: the card stays on row 0`).toBeLessThanOrEqual(1)
      }
      expect(between, 'the lock, the next photo and the next name sit between the two price fields').toBeGreaterThanOrEqual(1)

      /* The next price field took focus: the card moves to its row. */
      await expect(listPrice(page, 1)).toBeFocused()
      await expect.poll(() => gapAbove(page, listRow(page, 1)), 'the card is above row 1').toBeGreaterThanOrEqual(0)
      await expect(card(page)).toHaveAttribute('data-mode', 'focus')

      /* Focus leaves the list for something that is not the card: the search box above it. */
      await page.getByRole('searchbox', { name: 'Search This List' }).focus()
      await expect(card(page)).toHaveCount(0)
    })
  })
}

/* ---- `#/pricing`: WHERE THE CARD SITS AGAINST THE SHELL (mockup `history-float.html`, items 5 and 6; spec 9c) ----
 *
 * The gallery rows carry `data-float-price` and `data-float-door`, and the card reads its placement off them. A
 * pricing row must carry them too (its price column and its history door, or the card has nothing to sit beside)
 * and the card must keep clear of the one other fixed thing over the list, the sticky Send bar.
 *
 * NO ROOM ABOVE: the card opens below the row, inside the list, and ends 8px left of the row's price column. It
 * never reaches the sidebar (1440) or the rail (1200 and 820). "Price column" is the cell the caption's Price sits
 * over or the field in it: the card's right edge is at the cell's left less 8px or at the field's left less 8px.
 *
 * THE BAR: "room above" ends under the Send bar once it has stuck at the top of the viewport. The card above a row
 * never overlaps the bar; a row with no room under the bar opens it below (the first case); a row with room under it
 * opens it above (the second case, which passes today and keeps a fix from always opening below).
 *
 * Sixteen filler rows, the two stored rows and one live listing, so the page scrolls far enough to put a row at any height. The viewport is 1200
 * tall so a card fits below the row at every width: at 900 the 385px card at 820 fits neither above the row under the
 * bar nor below it, and a case that no placement can pass says nothing about the placement. */
for (const size of SIZES) {
  test.describe(`#/pricing card placement at ${size.width} wide`, () => {
    const GAP_PX = 8
    /* A row high enough in the list that the page can scroll it to any height. */
    const ROW = 2
    /* Rows are 83px, so row `ROW` at 150px needs about 1050px of list under it: filler rows past that, plus the two stored rows and the live listing. */
    const FILLER = 16
    const barOf = (page: Page) => page.locator('.pricing-bar')
    test.beforeEach(async ({ page }) => {
      await setViewport(page, { width: size.width, height: 1200 })
      await seedPopulatedPricing(page, FILLER, () => [liveListing()])
      await page.route(HISTORY, (route) =>
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payloadWithAsking()) }),
      )
      await page.goto(PRICING)
      await expect(page.locator('.pricing-row')).toHaveCount(FILLER + 3)
      await settleMotion(page)
    })

    /* Row `i` at `top` px from the viewport top, with the Send bar stuck above it. */
    async function putRowAt(page: Page, i: number, top: number) {
      await listRow(page, i).evaluate((el, t) => window.scrollBy({ top: el.getBoundingClientRect().top - t, behavior: 'instant' }), top)
      await settleMotion(page)
      expect(Math.abs((await boxOf(listRow(page, i))).y - top), `row ${i} sits ${top}px from the top`).toBeLessThanOrEqual(2)
      expect((await boxOf(barOf(page))).y, 'the Send bar has stuck at the top').toBeLessThanOrEqual(1)
    }

    /* The card is one height whoever it is for (it holds its size while history loads), so one open measures it. */
    async function cardHeight(page: Page): Promise<number> {
      await listPrice(page, 0).focus()
      await expect(card(page)).toHaveAttribute('data-mode', 'focus')
      const { height } = await boxOf(card(page))
      await page.keyboard.press('Escape')
      await expect(card(page)).toHaveCount(0)
      await listPrice(page, 0).blur()
      return height
    }

    test('with no room above, the card opens below the row, inside the list, and ends 8px left of the price column', async ({ page }) => {
      await putRowAt(page, ROW, 150)
      await listPrice(page, ROW).focus()
      await expect(card(page)).toHaveAttribute('data-mode', 'focus')
      await expect(card(page)).toHaveAttribute('data-placement', 'below')

      const c = await boxOf(card(page))
      const side = await boxOf(page.locator('aside.bn-side'))
      const list = await boxOf(page.locator('.pricing-list'))
      expect.soft(meets(c, side), `the card (x ${Math.round(c.x)}) does not cover the sidebar or the rail (to x ${Math.round(side.x + side.width)})`).toBe(false)
      expect.soft(c.x, 'the card sits inside the list').toBeGreaterThanOrEqual(list.x)
      const cell = await boxOf(listRow(page, ROW).locator('.pricing-price'))
      const field = await boxOf(listPrice(page, ROW))
      const right = c.x + c.width
      expect.soft(right, 'the card ends no nearer than 8px to the price field').toBeLessThanOrEqual(field.x - GAP_PX + 1)
      expect.soft(right, 'the card ends 8px left of the price column, not further').toBeGreaterThanOrEqual(cell.x - GAP_PX - 1)
    })

    test('a card opened above a row never overlaps the Send bar: with no room under the bar it opens below', async ({ page }) => {
      const h = await cardHeight(page)
      /* Room above by the viewport alone (the row is `h` + 16 + 20 from the top), none under the 100px-plus bar. */
      await putRowAt(page, ROW, h + 2 * GAP_PX + 20)
      const row = await boxOf(listRow(page, ROW))
      const bar = await boxOf(barOf(page))
      expect(row.y - bar.height - 2 * GAP_PX, 'there is no room above the row under the bar').toBeLessThan(h)
      expect(page.viewportSize()!.height - (row.y + row.height) - 2 * GAP_PX, 'a card fits below the row').toBeGreaterThanOrEqual(h)
      await listPrice(page, ROW).focus()
      await expect(card(page)).toHaveAttribute('data-mode', 'focus')

      const c = await boxOf(card(page))
      expect(meets(c, bar), `the card (y ${Math.round(c.y)} to ${Math.round(c.y + c.height)}) does not overlap the Send bar (to y ${Math.round(bar.y + bar.height)})`).toBe(false)
      expect(meets(c, await boxOf(listRow(page, ROW))), 'the card does not cover the row').toBe(false)
      expect(meets(c, await boxOf(listPrice(page, ROW))), 'the card does not cover the price field').toBe(false)
    })

    test('with room above under the Send bar, the card opens above the row and clear of the bar', async ({ page }) => {
      const h = await cardHeight(page)
      const bar = await boxOf(barOf(page))
      /* Stuck, the bar ends at its own height. */
      await putRowAt(page, ROW, bar.height + h + 2 * GAP_PX + 40)
      await listPrice(page, ROW).focus()
      await expect(card(page)).toHaveAttribute('data-mode', 'focus')
      await expect(card(page)).toHaveAttribute('data-placement', 'above')
      const c = await boxOf(card(page))
      expect(meets(c, await boxOf(barOf(page))), 'the card does not overlap the Send bar').toBe(false)
    })
  })
}

/* ---- `#/pricing`: THE HISTORY DOOR (`list.html` notes, item 17; `history-float.html`; spec section 9c) ----
 *
 * Each row has a chart button, "Price History for <name>" (Title Case, docs/DESIGN.md R5), and it opens the card for that row. It is the only way in on a
 * row with no price field: a card the owner kept off TCGplayer draws no field, so focus can never open its history.
 * The door carries `data-float-door`, which the card reads to put its right edge on it (the contract at the top). A card
 * the door opens takes focus, and gives it back to the door when it closes (9c). Two widths: the row's layout differs.
 *
 * THE KEPT-OFF ROW IS FOUND BY ITS PILL, and by the one kept-off press when the list does not draw it, so the case
 * stands whether kept-off rows sit in the list or behind that press. */
for (const size of [SIZES[0], SIZES[2]]) {
  test.describe(`#/pricing history door at ${size.width} wide`, () => {
    const KEPT_OFF = '8608459'
    let asked: string[]
    test.beforeEach(async ({ page }) => {
      asked = []
      await setViewport(page, size)
      await seedPopulatedPricing(page, 0, undefined, [KEPT_OFF])
      await page.route(HISTORY, (route) => {
        asked.push(/\/products\/([^/]+)\/history$/.exec(new URL(route.request().url()).pathname)?.[1] ?? '')
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payloadWithAsking()) })
      })
      await page.goto(PRICING)
      await expect(page.locator('.pricing-row').first()).toBeVisible()
      await settleMotion(page)
    })

    /** The door of `scope`, pressed: the card opens for `sku` in door mode, holds focus, and gives it back on Esc. */
    async function expectDoorOpensCard(page: Page, scope: Locator, sku: string) {
      const door = scope.getByRole('button', { name: /^Price History for / })
      await expect(door, 'the row has a history door').toHaveCount(1)
      await expect(door, 'the door is the mark the card sits against').toHaveAttribute('data-float-door', '')
      await door.click()
      await expect(card(page), 'the door opened the card').toHaveAttribute('data-mode', 'door')
      await expect.poll(() => asked.at(-1), "the card asked for this row's history").toBe(sku)
      await expect.poll(() => page.evaluate(() => !!document.activeElement?.closest('[data-history-float]')), 'a card the door opens takes focus').toBe(true)
      if ((await card(page).getAttribute('data-placement')) === 'above') {
        const c = await boxOf(card(page))
        const d = await boxOf(door)
        expect(Math.abs(c.x + c.width - (d.x + d.width)), "the card's right edge sits on the door").toBeLessThanOrEqual(1)
      }
      await page.keyboard.press('Escape')
      await expect(card(page)).toHaveCount(0)
      await expect(door, 'Esc gives focus back to the door').toBeFocused()
    }

    test("a row's history door opens the card for that row", async ({ page }) => {
      const row = page.locator('.pricing-row', { has: page.getByRole('textbox', { name: 'Price for Articuno' }) })
      await expectDoorOpensCard(page, row, '8608859')
    })

    test('a kept-off row has no price field, and its door opens the card for that row', async ({ page }) => {
      const kept = page.locator('.pricing-row', { has: page.locator('.pricing-held') })
      const press = page.getByRole('button', { name: /kept off/i })
      await expect(kept.or(press).first(), 'the kept-off row, or the press that shows it, is drawn').toBeVisible()
      if ((await kept.count()) === 0) await press.first().click()
      await expect(kept, 'the kept-off row is drawn').toHaveCount(1)
      await expect(kept.getByRole('textbox', { name: /^Price for / }), 'a kept-off row has no price field').toHaveCount(0)
      await expectDoorOpensCard(page, kept, KEPT_OFF)
    })
  })
}

/* ---- `#/pricing`: WHAT THE CARD READS, AND WHEN (D278 "no request per arrow key"; spec section 9c) ----
 *
 * `getPriceHistory`'s docstring in `server.ts` says a walk may never fire it; the card's two reads
 * (`GET /pipeline/products/<sku>/history`, `GET /pipeline/price-facts?sku=`) are the same kind of
 * read, so a walk down the list asks for the row where focus RESTS and nothing on the way. A row
 * read once is not read again. `GET /orders`, the sale marks, is read on an open and, when it
 * failed, again on the next open. Esc closes the card and focus stays in the price field (9c).
 *
 * Ten rows: `seedPopulatedPricing`'s two and eight more. Every read lands in `reads`. The history
 * stub answers `productHistory`, the price read falls through to the shell's own answer, and the
 * orders read is stubbed by the case that needs sale marks. One width is enough: none of this is
 * placement. */
test.describe('#/pricing card reads', () => {
  let reads: { history: string[]; facts: string[]; orders: number }
  const readsOf = (list: string[], sku: string) => list.filter((one) => one === sku).length
  const skuOfRead = (url: string) =>
    new URL(url).searchParams.get('sku') ?? /\/products\/([^/]+)\/history$/.exec(new URL(url).pathname)?.[1] ?? ''

  test.beforeEach(async ({ page }) => {
    reads = { history: [], facts: [], orders: 0 }
    await setViewport(page, SIZES[0])
    await seedPopulatedPricing(page, 8)
    await page.route(HISTORY, (route) => {
      reads.history.push(skuOfRead(route.request().url()))
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(productHistory()) })
    })
    await page.route(/\/pipeline\/price-facts/, (route) => {
      reads.facts.push(skuOfRead(route.request().url()))
      return route.fallback()
    })
    await page.goto(PRICING)
    await expect(page.locator('.pricing-row')).toHaveCount(10)
    await settleMotion(page)
  })

  /* A card's reads are done: its history is drawn and its price read has gone out. A condition, not a pause. */
  const answered = async (page: Page, sku: string) => {
    await cardLoaded(page)
    await expect.poll(() => readsOf(reads.facts, sku), `the price read for ${sku} went out`).toBeGreaterThanOrEqual(1)
    await afterPaint(page)
  }

  test('a quick walk down ten rows sends one history read and one price read, for the row where focus rests', async ({ page }) => {
    await listPrice(page, 0).focus()
    for (let i = 0; i < 9; i++) await page.keyboard.press('ArrowDown')
    await expect(listPrice(page, 9)).toBeFocused()
    const rest = await skuOfRow(page, 9)

    await answered(page, rest)
    expect(reads.history, 'one history read, for the row where focus rests').toEqual([rest])
    expect(reads.facts, 'one price read, for the row where focus rests').toEqual([rest])
  })

  test('a row whose card was read once sends no second read when focus comes back to it', async ({ page }) => {
    const skus = { 3: await skuOfRow(page, 3), 4: await skuOfRow(page, 4), 5: await skuOfRow(page, 5) } as const
    for (const i of [3, 4, 3, 5] as const) {
      await listPrice(page, i).click()
      await answered(page, skus[i])
      await page.waitForTimeout(500) // keep: a repeat read has to show itself, and no event says it will not come
    }
    for (const [name, list] of [['history', reads.history], ['price', reads.facts]] as const) {
      expect(readsOf(list, skus[3]), `row 3: one ${name} read over two visits`).toBe(1)
      expect(readsOf(list, skus[4]), `row 4: one ${name} read over one visit`).toBe(1)
      expect(readsOf(list, skus[5]), `row 5: one ${name} read over one visit`).toBe(1)
    }
  })

  test('a failed sales read is tried again on the next open, and the second open draws the sale marks', async ({ page }) => {
    const sku = await skuOfRow(page, 0)
    const sale = order({ placed_at: '2026-08-27T12:00:00+00:00', lines: [{ ...line().line, sku, unit_price: '1.40' }] })
    let failing = true
    await page.route(/\/orders$/, (route) => {
      reads.orders++
      return failing
        ? route.fulfill({ status: 500, contentType: 'application/json', body: '{}' })
        : route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payloadOf([sale], [])) })
    })

    await listPrice(page, 0).click()
    await expect.poll(() => reads.orders, 'the first open asked for the sales').toBeGreaterThanOrEqual(1)
    await answered(page, sku)
    await expect(card(page).locator('.producthistory-fill-mark'), 'the failed read leaves the chart without sale marks').toHaveCount(0)

    /* Focus leaves the list and the card closes; the price field taking focus again is a new open, and the server answers now. */
    await page.getByRole('searchbox', { name: 'Search This List' }).focus()
    await expect(card(page)).toHaveCount(0)
    const failed = reads.orders
    failing = false
    await listPrice(page, 0).click()
    await expect(card(page)).toHaveAttribute('data-mode', 'focus')

    await expect.poll(() => reads.orders, 'the second open asked for the sales again').toBeGreaterThan(failed)
    await expect(card(page).locator('.producthistory-fill-mark').first(), 'the second open draws the sale mark').toBeAttached()
  })

  test('Esc in a price field closes the card and leaves focus in that field (spec 9c)', async ({ page }) => {
    await listPrice(page, 1).click()
    await expect(card(page)).toHaveAttribute('data-mode', 'focus')
    await expect(listPrice(page, 1)).toBeFocused()

    await page.keyboard.press('Escape')
    await expect(card(page)).toHaveCount(0)
    await expect(listPrice(page, 1), 'Esc leaves focus in the price field').toBeFocused()
  })

  /* THE TITLE NAMES THE ROW WHOSE PRICE FIELD HAS FOCUS. The block's history stub above answers `productHistory()`
   * for every SKU, so its title reads "Volcanion" over any row: the stub, not the card. This stub answers each SKU
   * with the name of the row that SKU belongs to, which is what the server does, so a title that names another row
   * is the card's. While the next row reads, the title is the quiet "Price history" and never the row left behind. */
  test("the card's title names the row whose price field has focus, and never the row focus left", async ({ page }) => {
    const names = new Map<string, string>()
    for (const i of [0, 1, 2]) names.set(await skuOfRow(page, i), (await listRow(page, i).locator('a.pricing-name').innerText()).trim())
    await page.route(HISTORY, (route) => {
      const sku = skuOfRead(route.request().url())
      reads.history.push(sku)
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ...productHistory(), sku, name: names.get(sku) }) })
    })
    const title = card(page).locator('.hfloat-name')

    await listPrice(page, 0).click()
    await cardLoaded(page)
    const [first, second] = [await skuOfRow(page, 0), await skuOfRow(page, 1)]
    await expect(title, 'row 0 has focus, so the card names row 0').toHaveText(names.get(first)!)
    await expect(card(page)).toHaveAttribute('aria-label', `Price history for ${names.get(first)}`)

    await page.keyboard.press('ArrowDown')
    await expect(listPrice(page, 1)).toBeFocused()
    expect(await title.textContent(), 'row 1 has focus, so the card does not name row 0 while row 1 reads').not.toBe(names.get(first))
    await cardLoaded(page)
    await expect(title, 'row 1 has focus, so the card names row 1').toHaveText(names.get(second)!)
    await expect(card(page)).toHaveAttribute('aria-label', `Price history for ${names.get(second)}`)
  })

  /* A SEND ENDS EVERY READ BEFORE IT (`server.ts:request`: a write bumps `writeGen`, clears the shared reads, and a read
   * is kept only when no write came while it ran). The card's own kept reads are no exception: what a card read before
   * the owner's price went out is the old store, so the next open reads again and draws the new one.
   *
   * X is a live listing whose kept suggestion rides the send alone (`runs: []`, a ticked price). Its history answers
   * step line A until the send lands and step line B after it (B has one more step, so its `d` has a `V` run). The
   * price read answers one Lowest before the send and another after it. Both stubs answer with what they held WHEN
   * THE READ ARRIVED, so a read held open across the send still carries the old store. The case reloads the page
   * over the block's own setup, so the worklist carries X. */
  test.describe('after a send', () => {
    const X = LIVE_SKU
    const listing = liveListing
    let answer: ProductHistoryPayload
    let lowest: string
    let sends: number
    let hold: Promise<void> | null
    const rowX = (page: Page) => page.locator('.pricing-row', { has: page.locator(`a.pricing-name[href*="sku=${X}"]`) })
    const priceX = (page: Page) => rowX(page).getByRole('textbox', { name: /^Price for / })
    const stepsOf = async (page: Page) => ((await card(page).locator('[data-float="asking"]').getAttribute('d')) ?? '').match(/V/g)?.length ?? 0
    const lowestOf = (page: Page) => card(page).locator('.hfloat-facts div', { has: page.locator('dt', { hasText: /^Lowest$/ }) }).locator('dd')

    test.beforeEach(async ({ page }) => {
      answer = payloadWithAsking()
      lowest = '1.11'
      sends = 0
      hold = null
      await seedPopulatedPricing(page, 8, () => [sends === 0 ? listing() : listing({ asking: '4.01', group: 'at_rule', source: 'Live', reason: '' })])
      await page.route(HISTORY, async (route) => {
        const body = JSON.stringify(answer)
        reads.history.push(skuOfRead(route.request().url()))
        await hold
        await route.fulfill({ status: 200, contentType: 'application/json', body })
      })
      await page.route(/\/pipeline\/price-facts/, (route) => {
        reads.facts.push(skuOfRead(route.request().url()))
        const prices = { market: '1.31', low: lowest, low_with_shipping: null, direct_low: null }
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ sku: X, name: null, at: null, through: null, prices, shelf: null, days: [], facts: null }) })
      })
      await page.route(/\/pipeline\/send$/, (route) => {
        sends++
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ send: sendSummary({ copies: 0, prices: 1 }), console: '' }) })
      })
      await page.reload()
      await expect(page.locator('.pricing-row')).toHaveCount(11)
      await settleMotion(page)
    })

    /* The screen's own send: X's suggestion starts ticked, the press sends it alone, and the worklist is read again with X still on it. */
    const sendTheNewPrice = async (page: Page) => {
      await expect(rowX(page).getByRole('checkbox', { name: /^Send the new price for / })).toBeChecked()
      await page.getByRole('button', { name: /^Send .* to TCGplayer$/i }).click()
      await expect.poll(() => sends, 'the send went out').toBe(1)
      await expect(page.getByText('Market up 18% since listed.'), 'the worklist was read again, and X is on it at the sent price').toHaveCount(0)
      await expect(rowX(page)).toHaveCount(1)
    }

    /* THE OPEN AFTER THE SEND: focus comes back to X's price field, the card reads again and draws what the store holds now. */
    const reopenedAfterSend = async (page: Page) => {
      await priceX(page).click()
      await expect(card(page)).toHaveAttribute('data-mode', 'focus')
      await cardLoaded(page)
      await afterPaint(page)
      expect(readsOf(reads.history, X), 'the open after the send read the history again').toBe(2)
      expect(await stepsOf(page), 'the card draws the line the store holds now (B, one step), not the one read before the send (A, none)').toBe(1)
    }

    test('the open after a send reads the history and the prices again, and draws what they now say', async ({ page }) => {
      await priceX(page).click()
      await answered(page, X)
      expect(await stepsOf(page), 'before the send the card draws line A').toBe(0)
      await expect(lowestOf(page)).toHaveText('$1.11')

      await sendTheNewPrice(page)
      answer = payloadAfterSend()
      lowest = '2.22'
      await reopenedAfterSend(page)
      expect(readsOf(reads.facts, X), 'the open after the send read the prices again').toBe(2)
      await expect(lowestOf(page), 'the card draws the Lowest the store holds now').toHaveText('$2.22')
    })

    test('a history read begun before a send and landing after it is not served to the next open', async ({ page }) => {
      let release!: () => void
      hold = new Promise<void>((done) => (release = done))
      await priceX(page).click()
      await expect.poll(() => readsOf(reads.history, X), 'the first history read is out and held').toBe(1)

      await sendTheNewPrice(page)
      answer = payloadAfterSend()
      hold = null
      release()
      await afterPaint(page)
      await reopenedAfterSend(page)
    })
  })
})
