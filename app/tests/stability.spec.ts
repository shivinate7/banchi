// Protects: nothing on screen moves unless the person moved it. Case one: a screen holds its final frame from the first paint.
// Governs: D313, D280
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test, expect, type Page, type Route } from '@playwright/test'
import { sealEveryTest } from './shell'
import { settleFonts } from './fontsReady'
import { settleMotion } from './motionSettled'
import { routesFromNav } from './routes'
import { POPULATED_ROUTE_SEEDS, PRODUCT_ROUTE } from './routeFixtures'
import { EXCLUDED_FROM_SWEEP } from './routeExclusions'
import { setViewport } from './phoneSwitch'
import { describeShifts, readShifts, sumOf, watchShifts, type Shift } from './layoutShift'

/* LAYOUT SHIFT, PER CASE. THE FIRST CASE IS LOAD TIME, PER SCREEN, UNDER A SLOW SERVER.
 *
 * Every read the app makes is held 800ms before the stub answers, so an area that draws a
 * different box while it waits shows up as a `layout-shift` entry. The sum is taken with no
 * recent-input exclusion over the first 3s of the document, and the sources name what moved.
 * The measure is the browser's own, so a font or a CI box cannot tune it. */
sealEveryTest({ store: true, cards: 122 })

const HERE = dirname(fileURLToPath(import.meta.url))
const EXCUSED = JSON.parse(readFileSync(resolve(HERE, 'stability-allow.json'), 'utf8')) as Record<string, string>

const SLOW_MS = 800
const WINDOW_MS = 3000
const BUDGET = 0.01

/** A store with priced holdings, so the shelf draws its figure and spark. The shell's default
 *  answers "nothing priced", which is a thinner frame than a real store's. */
async function pricedShelf(page: Page): Promise<void> {
  await page.route(/\/pipeline\/holdings-value(\?|$)/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        range: 'month',
        width_days: 30,
        history_begins: '2026-08-01',
        at: '2026-09-19T00:00:00+00:00',
        on_hand_names: 10,
        series: [],
        totals: [
          { start: '2026-08-01', value: '100.00', priced_names: 8, unpriced_names: 2, gap_before: false },
          { start: '2026-09-01', value: '120.00', priced_names: 9, unpriced_names: 1, gap_before: false },
        ],
        unmarked: { names: 1 },
        sealed_excluded: { names: 2, reason: 'sealed product has no card record' },
      }),
    }),
  )
}

async function slowReads(page: Page): Promise<void> {
  await page.route(
    () => true,
    async (route) => {
      const type = route.request().resourceType()
      if (type === 'fetch' || type === 'xhr') await new Promise((r) => setTimeout(r, SLOW_MS))
      await route.fallback()
    },
  )
}

async function shiftOf(page: Page, route: string): Promise<{ sum: number; shifts: Shift[] }> {
  /* a hash change alone keeps the document and its old shifts; a blank page first makes a cold load. */
  await page.goto('about:blank')
  await page.goto(`/${route}`)
  await settleFonts(page)
  await page.waitForTimeout(WINDOW_MS)
  const shifts = (await readShifts(page)).shifts.filter((s) => s.at < WINDOW_MS)
  return { sum: sumOf(shifts), shifts }
}

/* THE CASE TABLE (D313). A new class of shift is a row here, never a new
 * file. `name` keys `stability-allow.json` as `<name>:<screen>`. The press cases need a screen's
 * own fixtures, so they sit in that screen's spec and read the same observer (`layoutShift.ts`):
 * the sale press is in `inventory.spec.ts`. */
const CASES = [{ name: 'loading', widths: [1440, 820], budget: BUDGET }] as const

for (const one of CASES) {
  for (const width of one.widths) {
    test(`${one.name}: nothing moves while a screen loads under a slow server, at ${width}`, async ({ page }) => {
      test.setTimeout(240_000)
      for (const seed of Object.values(POPULATED_ROUTE_SEEDS)) await seed(page)
      await pricedShelf(page)
      await slowReads(page)
      await watchShifts(page)
      await setViewport(page, { width, height: 1000 })
      /* EVERY NAV SCREEN, PLUS THE FULFILLER'S: `#/fulfillment` is his whole product and has no nav
         row, so it is named. `#/gallery` stays out on purpose: it is the kit's specimen page, reached
         from the palette only, and its specimens loop on their own. */
      const routes = (await routesFromNav(page)).filter((r) => !EXCLUDED_FROM_SWEEP.test(r))
      routes.push(PRODUCT_ROUTE, '#/fulfillment')
      const blank = Object.entries(EXCUSED).filter(([, why]) => why.trim() === '').map(([key]) => key)
      expect(blank, 'an exception with no reason: write why, or delete it').toEqual([])
      const over: string[] = []
      const stale: string[] = []
      const table: string[] = []
      for (const route of routes) {
        const { sum, shifts } = await shiftOf(page, route)
        table.push(`${width} ${route} ${sum.toFixed(4)} ${describeShifts(shifts)}`)
        const key = `${one.name}:${route}`
        if (key in EXCUSED) {
          if (sum < one.budget) stale.push(`${key} now passes: delete its entry in stability-allow.json`)
        } else if (sum >= one.budget) over.push(`${route} ${sum.toFixed(4)}`)
      }
      console.log('SHIFT\n' + table.join('\n'))
      expect(over, 'screens that shift while loading').toEqual([])
      expect(stale, 'a stale exception').toEqual([])
    })
  }
}

/* A FAILED READ HOLDS NO FRAME (D313). The history foot's frame stands for a
   read that is out. A read that failed is not out, so Home draws what it drew before the frame existed
   and never a skeleton that waits for an answer that is not coming. */
test('failed: a failed history read leaves no skeleton on Home', async ({ page }) => {
  await page.route(/\/inventory\/history$/, (route) => route.fulfill({ status: 500, contentType: 'application/json', body: '{"error":"no"}' }))
  await page.goto('/#/')
  await expect(page.locator('.home-foot-sum')).toBeVisible()
  await page.waitForTimeout(1500)
  await expect(page.locator('.home-foot .bn-skeleton')).toHaveCount(0)
  await expect(page.locator('.home-hold')).toHaveCount(0)
})

// L3 slots
/* RESERVED SLOTS, PILL HEIGHT AND FIXED-WIDTH LIVE COUNTS (D313, stability.md S8-S15 and S20).
 * Each row presses once and reads the rects of what sits BELOW or BESIDE the press: a rect that
 * moves is a slot that was not reserved. Geometry, not a shift sum, so a row names the exact
 * element that moved. */
const json = (route: Route, body: unknown) =>
  route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })

/** A screen's address, built so this block types no route list of its own (the roster is `ROUTES`). */
const screen = (name: string) => `/#/${name}`

/** Top, left, width and height of each selector's first match, rounded to a pixel. */
async function boxes(page: Page, selectors: readonly string[]): Promise<Record<string, string>> {
  return page.evaluate((sels) => {
    const out: Record<string, string> = {}
    for (const s of sels) {
      const el = document.querySelector(s)
      const r = el?.getBoundingClientRect()
      out[s] = r ? `${Math.round(r.top)},${Math.round(r.left)},${Math.round(r.width)},${Math.round(r.height)}` : 'absent'
    }
    return out
  }, selectors)
}

function salesLine(over: Record<string, unknown> = {}) {
  return {
    sku: '9100001', quantity: 1, name: 'Charizard ex', number: '006', printing: 'Holo', condition: 'Near Mint',
    rarity: 'Rare', unit_price: '12.50', kind: null, ...over,
  }
}
function salesOrder(number: string, placed: string, status: string, lines: unknown[]) {
  return {
    key: `TCGplayer:${number}`, source: 'TCGplayer', number, placed_at: placed, status, first_seen: placed,
    changed_at: null, buyer: 'Ada Lovelace', wanted: 1, recorded: 1, open: false, terminal: true, progress: [], lines,
  }
}
async function openSales(page: Page, orders: unknown[]): Promise<void> {
  await page.clock.install({ time: new Date(2026, 8, 19, 15, 0, 0) })
  await page.route(/\/orders$/, (route) =>
    json(route, {
      summary: `${orders.length} orders`, orders,
      resolution: { orders: [], counts: { resolved: 0, short: 0, no_copies_on_hand: 0, sku_unknown: 0, sku_unseen: 0, not_a_single: 0 } },
    }),
  )
  await page.route(/\/skus\/photos\?/, (route) => json(route, { photos: {} }))
  await page.route(/\/pipeline\/holdings-value\?/, (route) =>
    json(route, {
      range: 'month', width_days: 30, history_begins: null, at: '2026-09-19T00:00:00+00:00', on_hand_names: 0,
      series: [], totals: [], unmarked: { names: 0 }, sealed_excluded: { names: 0, reason: 'sealed product has no card record' },
    }),
  )
  await page.goto(screen('revenue'))
  await expect(page.locator('main.revenue')).toBeVisible()
  await settleFonts(page)
  await settleMotion(page)
}
const SALES_ORDERS = () => [
  salesOrder('ORD-1', '2026-07-10T10:00:00+00:00', 'Shipped', [salesLine({ quantity: 2 })]),
  salesOrder('ORD-2', '2026-08-05T09:00:00+00:00', 'Shipped', [salesLine({ sku: '9200002', name: 'Pikachu VMAX', unit_price: '8.00' })]),
  salesOrder('ORD-3', '2026-09-02T11:00:00+00:00', 'Shipped', [salesLine({ sku: '9300003', name: 'Mew', unit_price: '3.25' })]),
  salesOrder('ORD-4', '2026-09-10T11:00:00+00:00', 'Canceled', [salesLine({ sku: '9400004', name: 'Never', unit_price: '99.00' })]),
]
const SALES_BELOW = ['.revenue-podium', '.revenue-bar-head', '.revenue-months', '.revenue-summary']

for (const width of [1440, 820]) {
  test(`L3 S9: picking a month moves nothing below it, at ${width}`, async ({ page }) => {
    await setViewport(page, { width, height: 1000 })
    await openSales(page, SALES_ORDERS())
    const before = await boxes(page, SALES_BELOW)
    await page.locator('.revenue-month-col', { hasText: 'Jul 2026' }).click()
    await expect(page.locator('.revenue-month-col[aria-pressed="true"]')).toHaveCount(1)
    await settleMotion(page)
    expect(await boxes(page, SALES_BELOW)).toEqual(before)
  })

  test(`L3 S10: choosing the All period moves nothing below the summary, at ${width}`, async ({ page }) => {
    await setViewport(page, { width, height: 1000 })
    await openSales(page, SALES_ORDERS())
    const below = ['.revenue-podium', '.revenue-bar-head']
    const before = await boxes(page, below)
    await page.getByLabel('Period').getByRole('button', { name: 'All', exact: true }).click()
    await settleMotion(page)
    expect(await boxes(page, below)).toEqual(before)
  })
}

for (const width of [1440, 820]) {
  test(`L3 S11: a Pricing filter moves nothing below the filter bar, at ${width}`, async ({ page }) => {
    await setViewport(page, { width, height: 1000 })
    await POPULATED_ROUTE_SEEDS[`#/${'pricing'}`]?.(page)
    await page.goto(screen('pricing'))
    await expect(page.locator('.pricing-filterbar')).toBeVisible()
    await settleFonts(page)
    await settleMotion(page)
    /* the list's own height and the row's follow the filter on purpose; its top is the claim */
    const topOf = async () => (await boxes(page, ['.pricing-list']))['.pricing-list']?.split(',')[0]
    const before = await topOf()
    await page.locator('.pricing-filterbar input[type="search"], .pricing-filterbar input').first().fill('Arti')
    await expect(page.locator('.pricing-filter-note, .bn-slot')).not.toHaveCount(0)
    await settleMotion(page)
    expect(await topOf()).toEqual(before)
  })
}

for (const width of [1440, 820]) {
  test(`L3 S8: ticking a card moves nothing in the Inventory list toolbar, at ${width}`, async ({ page }) => {
    await setViewport(page, { width, height: 900 })
    await page.goto(screen('inventory'))
    await expect(page.locator('.browse-rowtick').first()).toBeVisible()
    await settleFonts(page)
    await settleMotion(page)
    const parts = ['.browse-status', '.browse-list']
    const before = await boxes(page, parts)
    await page.locator('.browse-rowtick').first().check()
    await expect(page.locator('.browse-status-picked')).toBeVisible()
    await settleMotion(page)
    const after = await boxes(page, parts)
    /* the toolbar keeps its line and the list keeps its place */
    expect(after['.browse-status']?.split(',')[0]).toEqual(before['.browse-status']?.split(',')[0])
    expect(after['.browse-status']?.split(',')[3], 'the toolbar changed height').toEqual(before['.browse-status']?.split(',')[3])
    expect(after['.browse-list']).toEqual(before['.browse-list'])
  })
}

test('L3 S8: the In stock only count holds two digits, so a digit gained moves nothing beside it', async ({ page }) => {
  await setViewport(page, { width: 1440, height: 900 })
  await page.goto(screen('inventory'))
  const count = page.locator('.browse-hidesold .bn-hidetoggle-count')
  await expect(count).toBeVisible()
  await settleFonts(page)
  const [width, ch] = await count.evaluate((el) => {
    const probe = document.createElement('span')
    probe.style.cssText = 'position:absolute;visibility:hidden;width:2ch;font:inherit'
    el.appendChild(probe)
    const two = probe.getBoundingClientRect().width
    probe.remove()
    return [el.getBoundingClientRect().width, two]
  })
  expect(width).toBeGreaterThanOrEqual((ch ?? 0) - 0.5)
})
