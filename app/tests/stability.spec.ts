// Protects: nothing on screen moves unless the person moved it. Case one: a screen holds its final frame from the first paint.
// Governs: D313, D280
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test, expect, type Page, type Route } from '@playwright/test'
import { card, sealEveryTest } from './shell'
import { settleFonts } from './fontsReady'
import { routesFromNav } from './routes'
import { POPULATED_ROUTE_SEEDS, PRODUCT_ROUTE, severalOrdersWalkPlan } from './routeFixtures'
import { EXCLUDED_FROM_SWEEP } from './routeExclusions'
import { setViewport } from './phoneSwitch'
import { describeShifts, markNow, readShifts, sumOf, watchShifts, type Shift } from './layoutShift'

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

// L1 held frame
/* A READ AFTER A PRESS HOLDS THE OLD FRAME (D313, class B). A press that needs a read keeps what was
 * on screen, dimmed and busy, until the answer lands, then swaps once. Every row below holds the
 * press's read READ_MS, then asks two things of the browser's own `layout-shift` entries: nothing
 * moved while the read was out, and the swap after it is one cluster (entries under CLUSTER_MS
 * apart), never two layout changes for one press. The new content here is the same shape as the old
 * one on purpose, so any move is the frame and never the content. */
const READ_MS = 700
const CLUSTER_MS = 150
const OUT_SUM = 0.005

async function heldReads(page: Page, read: RegExp): Promise<{ on: boolean }> {
  const gate = { on: false }
  await page.route(read, async (route) => {
    if (gate.on) await new Promise((r) => setTimeout(r, READ_MS))
    await route.fallback()
  })
  return gate
}

/** Press, then read the shifts of the read-out window and of the swap that follows it. */
async function heldPress(page: Page, gate: { on: boolean }, press: () => Promise<void>) {
  await page.waitForTimeout(800)
  gate.on = true
  const from = await markNow(page)
  await press()
  await page.waitForTimeout(READ_MS * 2 + 400)
  gate.on = false
  const all = (await readShifts(page)).shifts.filter((s) => s.at >= from)
  const out = all.filter((s) => s.at < from + READ_MS - 150)
  const swap = all.filter((s) => s.at >= from + READ_MS - 150)
  let clusters = 0
  let last = -Infinity
  for (const s of swap) {
    if (s.at - last > CLUSTER_MS) clusters += 1
    last = s.at
  }
  return { out, swap, clusters }
}

function expectHeld(r: { out: Shift[]; swap: Shift[]; clusters: number }, budget = OUT_SUM): void {
  expect(sumOf(r.out), `it moved while the read was out: ${describeShifts(r.out)}`).toBeLessThan(budget)
  expect(r.clusters, `one press, ${r.clusters} layout changes after the read: ${describeShifts(r.swap)}`).toBeLessThanOrEqual(1)
}

/* ONE STORE FOR THE INVENTORY ROWS: every card carries a SKU, so each one answers a copies read, and
   every card is the same shape, so a card step or a box switch changes the content and nothing else. */
const L1_CARDS = {
  '2/1': card({ box: 2, index: 1, section: 1, card: 1, name: 'Volcanion', state: 'identified', sku: '9000001', boxName: 'SV commons', boxTotal: 4 }),
  '2/2': card({ box: 2, index: 2, section: 1, card: 2, name: 'Thievul', state: 'identified', sku: '9000002', boxName: 'SV commons', boxTotal: 4 }),
  '2/3': card({ box: 2, index: 3, section: 2, card: 3, name: 'Eiscue', state: 'identified', sku: '9000003', boxName: 'SV commons', boxTotal: 4 }),
  '2/4': card({ box: 2, index: 4, section: 2, card: 4, name: 'Pikachu', state: 'identified', sku: '9000004', boxName: 'SV commons', boxTotal: 4 }),
  '5/1': card({ box: 5, index: 1, section: 1, card: 1, name: 'Zacian', state: 'identified', sku: '9000005', boxTotal: 1 }),
}

async function l1Inventory(page: Page): Promise<void> {
  const json = (route: Route, body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  /* NO CARD IS QUEUED: the shell's seed queues box 2's first card, and a queue notice is content the
     other cards do not have. */
  await page.route(/\/queues$/, (route) => json(route, { review: [], parked: [] }))
  await page.route(/\/inventory\/(\d+)$/, (route) => {
    const box = Number(/\/inventory\/(\d+)$/.exec(route.request().url())?.[1])
    const cards = Object.fromEntries(Object.entries(L1_CARDS).filter(([, c]) => c.box === box))
    return json(route, { version: 2, cards, listings: {} })
  })
  await page.route(/\/search\?/, (route) => {
    const q = (new URL(route.request().url()).searchParams.get('q') ?? '').toLowerCase()
    const hit = Object.values(L1_CARDS).filter((c) => c.sku === q || (c.name ?? '').toLowerCase() === q)
    const skus = [...new Set(hit.map((c) => c.sku))]
    return json(route, {
      query: q,
      groups: skus.map((sku) => {
        const held = Object.entries(L1_CARDS).filter(([, c]) => c.sku === sku)
        const copies = held.map(([key, c]) => ({ key, state: c.state, state_at: c.state_at, has_photo: true, place: c.place }))
        return {
          sku,
          names: [...new Set(held.map(([, c]) => c.name))],
          number: '090',
          printed_total: '132',
          set_hint: 'ME01',
          condition: 'Near Mint',
          listed: { pushed: 0, staged: 0, live: 0 },
          sold_here: 0,
          live_as_of: null,
          on_hand: copies.length,
          listable: copies.length,
          copies,
        }
      }),
    })
  })
}

for (const width of [1440, 820]) {
  test(`held frame: switching the box holds the old box until its read lands, at ${width}`, async ({ page }) => {
    await l1Inventory(page)
    const gate = await heldReads(page, /\/inventory\/\d+$/)
    await watchShifts(page)
    await setViewport(page, { width, height: 1000 })
    await page.goto('/#/inventory')
    await expect(page.locator('.card-locations').first()).toBeVisible()
    const r = await heldPress(page, gate, () => page.locator('.browse-boxcell', { hasText: 'SV commons' }).click())
    expectHeld(r)
  })

  test(`held frame: stepping to the next card holds the copies until their read lands, at ${width}`, async ({ page }) => {
    await l1Inventory(page)
    const gate = await heldReads(page, /\/search\?/)
    await watchShifts(page)
    await setViewport(page, { width, height: 1000 })
    await page.goto('/#/inventory')
    await page.locator('.browse-boxcell', { hasText: 'SV commons' }).click()
    await expect(page.locator('.card-locations').first()).toBeVisible()
    await page.waitForTimeout(1500)
    const r = await heldPress(page, gate, () => page.keyboard.press('ArrowRight'))
    expectHeld(r)
  })
}

/* ORDERS: THE WALK OPENS OVER A READ. `Walk 3` asks the plan for three buyers' orders, so the walk
   holds the buyer it showed until the answer lands, then swaps once. The answer for several buyers
   is taller than the answer for one, which is content and is why only the read-out window and the
   cluster count are asked of it. */
async function l1Orders(page: Page): Promise<{ on: boolean }> {
  await POPULATED_ROUTE_SEEDS['#/orders']!(page)
  const gate = { on: false }
  await page.route(/\/orders\/walk-plan$/, async (route) => {
    if (gate.on) await new Promise((r) => setTimeout(r, READ_MS))
    const keys = (route.request().postDataJSON() as { keys: string[] }).keys
    const plan = severalOrdersWalkPlan()
    const stop = plan.stops[0]!
    if (keys.length > 1) stop.takes = [0, 1, 2].map((i) => ({ ...stop.takes[0]!, sku: `919148${i}` }))
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(plan) })
  })
  return gate
}

for (const width of [1440, 820]) {
  test(`held frame: opening the walk over several buyers holds the walk until its plan lands, at ${width}`, async ({ page }) => {
    const gate = await l1Orders(page)
    await watchShifts(page)
    await setViewport(page, { width, height: 1000 })
    await page.goto('/#/orders')
    await expect(page.locator('.orders-walk-list')).toBeVisible()
    const r = await heldPress(page, gate, () => page.getByRole('button', { name: 'Walk 3' }).click())
    /* A TIGHTER BUDGET: the walk list is short here, so a head swapped over the old rows moves them
       by a few hundredths at most. Nothing else on this screen moves in the window. */
    expectHeld(r, 0.001)
  })

  /* AND ONE BUYER: under 1000px a buyer press is also the walk's own mode (the page folds to the
     walk), so the fold waits for the plan too and the page changes once. */
  test(`held frame: selecting a buyer holds the screen until the walk's plan lands, at ${width}`, async ({ page }) => {
    const gate = await l1Orders(page)
    await watchShifts(page)
    await setViewport(page, { width, height: 1000 })
    await page.goto('/#/orders')
    await expect(page.locator('.orders-walk-list')).toBeVisible()
    const r = await heldPress(page, gate, () => page.getByRole('button', { name: 'Grace Hopper' }).first().click())
    expectHeld(r, 0.001)
  })
}

/* REVIEW: THE LOOKUP OPENS OVER A READ. `Search` replaces the candidate list with the export's rows,
   which are asked for when it opens. The candidates stay, dimmed, until the rows land, so the
   actions under the stage hold their place and the swap is one change. */
async function l1Review(page: Page): Promise<{ on: boolean }> {
  const json = (route: Route, body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  const candidates = [0, 1, 2].map((at) => ({
    sku: `860800${at}`,
    name: 'Snorlax',
    set: 'ME01',
    number: '014/132',
    condition: 'Near Mint',
    market: `${at + 4}.00`,
  }))
  await page.route(/\/queues$/, (route) =>
    json(route, {
      review: [
        {
          position: 'Box 2, Section 1, Card 1',
          box: 2,
          index: 1,
          label: 'Box 2, Section 1, Card 1',
          photo: 'photos/2/1.jpg',
          read: { name: 'Snorlax', number: '014/132', printed_total: '132', set_hint: 'ME01' },
          confidence: 'high',
          reason: 'set_ambiguous',
          candidates,
          first_seen: '2026-09-01T12:00:00+00:00',
          market: '4.00',
          cleared_by_human: false,
        },
      ],
      parked: [],
    }),
  )
  const gate = { on: false }
  await page.route(/\/review\/\d+\/\d+\/catalog/, async (route) => {
    if (gate.on) await new Promise((r) => setTimeout(r, READ_MS))
    json(route, {
      box: 2,
      index: 1,
      game: 'pokemon',
      query: 'Snorlax',
      searched: false,
      rows: candidates.map((one) => ({ ...one, name: 'Snorlax lookup' })),
      found: 3,
      truncated: false,
    })
  })
  return gate
}

for (const width of [1440, 820]) {
  test(`held frame: opening the lookup holds the candidates until its rows land, at ${width}`, async ({ page }) => {
    const gate = await l1Review(page)
    await watchShifts(page)
    await setViewport(page, { width, height: 1000 })
    await page.goto('/#/review')
    await expect(page.locator('.review-candidates')).toBeVisible()
    const r = await heldPress(page, gate, () => page.getByRole('button', { name: 'Search' }).click())
    expectHeld(r, 0.001)
  })
}
