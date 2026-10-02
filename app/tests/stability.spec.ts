// Protects: nothing on screen moves unless the person moved it. Case one: a screen holds its final frame from the first paint.
// Governs: D313, D280
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test, expect, type Page, type Route } from '@playwright/test'
import { card, sealEveryTest } from './shell'
import { settleFonts } from './fontsReady'
import { settleMotion } from './motionSettled'
import { routesFromNav } from './routes'
import { POPULATED_ROUTE_SEEDS, PRODUCT_ROUTE, line, order, seedPopulatedOrders, severalOrders, severalOrdersWalkPlan } from './routeFixtures'
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

/* READ ORDER MOVES NOTHING ON HOME (D313). The standing line draws as soon as the status lands, as a
   pressable row or as plain prose by what the other reads say. Equal 800ms holds hide that race. Here
   the runs read lands first and the status second, so the line is drawn twice. Its row keeps one
   height, so nothing below it moves. */
/* Both stores: the populated seeds, and the shell's bare store of 122 cards over several boxes. Every
   read lands at its own moment, so the foot's clauses (status, boxes, history) land one after another. */
const LANDS: readonly [RegExp, number][] = [[/\/runs(\?|$)/, 100], [/\/status(\?|$)/, 200], [/\/boxes(\?|$)/, 400], [/\/inventory\/history(\?|$)/, 600]]
/* `wide` blocks the web fonts and draws everything in Verdana, a face wider than the product's, the way a
   Linux box wraps a sentence that a Mac does not. A frame holds only if its text can never outgrow it. */
for (const width of [1440, 820]) for (const seeded of [true, false]) for (const wide of [false, true]) {
  test(`loading: Home holds its frame when its reads land out of order, ${seeded ? 'seeded' : 'bare store'}${wide ? ', wide face' : ''}, at ${width}`, async ({ page }) => {
    if (wide) {
      await page.route(/\.(woff2?|ttf)(\?|$)/, (route) => route.abort())
      await page.addInitScript(() => {
        document.addEventListener('DOMContentLoaded', () => {
          const st = document.createElement('style')
          st.textContent = '*{font-family:Verdana,sans-serif !important}'
          document.head.append(st)
        })
      })
    }
    if (seeded) for (const seed of Object.values(POPULATED_ROUTE_SEEDS)) await seed(page)
    await page.route(
      () => true,
      async (route) => {
        const type = route.request().resourceType()
        if (type === 'fetch' || type === 'xhr') {
          const url = route.request().url()
          await new Promise((r) => setTimeout(r, LANDS.find(([re]) => re.test(url))?.[1] ?? SLOW_MS))
        }
        await route.fallback()
      },
    )
    await watchShifts(page)
    await setViewport(page, { width, height: 1000 })
    const { sum, shifts } = await shiftOf(page, '#/')
    expect(sum, describeShifts(shifts)).toBe(0)
  })
}

// L-fulfiller
/* A RECOVERY DOES NOT WAIT ON THE STATE IT RECOVERS. The orders and walk-plan reads have no
   timeout. When they never answer, the boxes still show and still open, and the Pick list's
   frame is all that waits. */
test('fulfiller: the boxes show and open while the orders read never answers', async ({ page }) => {
  for (const seed of Object.values(POPULATED_ROUTE_SEEDS)) await seed(page)
  await page.route(/\/orders(\/walk-plan)?$/, () => new Promise<void>(() => {}))
  await page.goto('/#/fulfillment')
  const head = page.locator('.ff-box-head').first()
  await expect(head).toBeVisible()
  await head.click()
  await expect(head).toHaveAttribute('aria-expanded', 'true')
  await expect(page.locator('.ff-owed-wait')).toHaveCount(1)
})

/** A screen's address by name, so this file types no route list of its own (the roster is `ROUTES`). */
const screen = (name: string): string => `/#/${name}`

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
    await page.goto(screen('inventory'))
    await expect(page.locator('.card-locations').first()).toBeVisible()
    const r = await heldPress(page, gate, () => page.locator('.browse-boxcell', { hasText: 'SV commons' }).click())
    expectHeld(r)
  })

  test(`held frame: stepping to the next card holds the copies until their read lands, at ${width}`, async ({ page }) => {
    await l1Inventory(page)
    const gate = await heldReads(page, /\/search\?/)
    await watchShifts(page)
    await setViewport(page, { width, height: 1000 })
    await page.goto(screen('inventory'))
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
  await seedPopulatedOrders(page)
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
    await page.goto(screen('orders'))
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
    await page.goto(screen('orders'))
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
    await page.goto(screen('review'))
    await expect(page.locator('.review-candidates')).toBeVisible()
    const r = await heldPress(page, gate, () => page.getByRole('button', { name: 'Search' }).click())
    expectHeld(r, 0.001)
  })
}

/* THE KEYS WAIT TOO. `inert` stops the pointer, never a window keydown, so while the walk stands on
   the old buyer's plan a digit would sell a copy of the old buyer's pick. Nothing is written and
   nothing steps until the new plan lands. */
for (const width of [1440, 820]) {
  test(`held frame: no walk key acts on the old plan while the new one is out, at ${width}`, async ({ page }) => {
    const gate = await l1Orders(page)
    const writes: string[] = []
    page.on('request', (r) => {
      if (r.method() === 'POST' && /\/orders\/pull$/.test(r.url())) writes.push(r.url())
    })
    await setViewport(page, { width, height: 1000 })
    await page.goto(screen('orders'))
    await expect(page.locator('.orders-walk-list')).toBeVisible()
    gate.on = true
    await page.getByRole('button', { name: 'Grace Hopper' }).first().click()
    await expect(page.locator('.orders-walk[aria-busy="true"]')).toHaveCount(1)
    await page.keyboard.press('1')
    await page.keyboard.press('ArrowRight')
    await page.keyboard.press('j')
    await page.waitForTimeout(300)
    expect(writes, 'a key sold a copy from the old plan').toEqual([])
    gate.on = false
  })
}

// L3 slots
/* RESERVED SLOTS, PILL HEIGHT AND FIXED-WIDTH LIVE COUNTS (D313, stability.md S8-S15 and S20).
 * Each row presses once and reads the rects of what sits BELOW or BESIDE the press: a rect that
 * moves is a slot that was not reserved. Geometry, not a shift sum, so a row names the exact
 * element that moved. */
const json = (route: Route, body: unknown) =>
  route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })


/** Top, left, width and height of each selector's first match, rounded to a pixel. */
async function boxes(page: Page, selectors: readonly string[]): Promise<Record<string, string>> {
  return page.evaluate((sels) => {
    const out: Record<string, string> = {}
    for (const s of sels) {
      const el = document.querySelector(s)
      const r = el?.getBoundingClientRect()
      out[s] = r ? `${Math.round(r.top)}|${Math.round(r.left)}|${Math.round(r.width)}|${Math.round(r.height)}` : 'absent'
    }
    return out
  }, selectors)
}

test('L3 S8: the In stock only count holds one box at 9, 99 and 1,234', async ({ page }) => {
  await setViewport(page, { width: 1440, height: 900 })
  await page.goto(screen('inventory'))
  const count = '.browse-hidesold .bn-hidetoggle-count'
  await expect(page.locator(count)).toBeVisible()
  await settleFonts(page)
  const seen = await boxPerVariant(page, count, ['9', '99', '1,234'], count)
  expect(seen, 'the count must exist').not.toContain('absent')
  expect(new Set(seen.map((s) => s.split('|')[2])).size, `the count's width: ${seen.join(' ; ')}`).toBe(1)
})

/** Set `selector`'s content to each variant in turn (as HTML) and read the box `read` names after
 *  each. The page's own React never sees it: this asks the STYLESHEET whether the box holds when
 *  its live text changes length, which is the whole of a "fixed line box" (D313, class E). */
async function boxPerVariant(
  page: Page,
  selector: string,
  variants: readonly string[],
  read: string,
): Promise<string[]> {
  return page.evaluate(
    ({ selector, variants, read }) => {
      const el = document.querySelector(selector)
      const target = document.querySelector(read)
      if (!el || !target) return ['absent']
      const keep = el.innerHTML
      const out: string[] = []
      for (const html of variants) {
        el.innerHTML = html
        const r = (document.querySelector(read) ?? target).getBoundingClientRect()
        out.push(`${Math.round(r.left)}|${Math.round(r.top)}|${Math.round(r.width)}|${Math.round(r.height)}`)
      }
      el.innerHTML = keep
      return out
    },
    { selector, variants, read },
  )
}

async function openOrdersWalk(page: Page, width: number): Promise<void> {
  await setViewport(page, { width, height: 1000 })
  await POPULATED_ROUTE_SEEDS[`#/${'orders'}`]?.(page)
  await page.goto(screen('orders'))
  await expect(page.locator('.orders-walk-pick-count').first()).toBeVisible()
  await settleFonts(page)
  await settleMotion(page)
}

for (const width of [1440, 820]) {
  test(`L3 S13: the pick count holds one box whatever it says, at ${width}`, async ({ page }) => {
    await openOrdersWalk(page, width)
    const first = '.orders-walk-pick-count'
    const seen = await boxPerVariant(page, first, ['1', '1 of 3', '12 of 12'], first)
    expect(seen, 'the element must exist').not.toContain('absent')
    expect(new Set(seen).size, `the pick count's box: ${seen.join(' | ')}`).toBe(1)
  })

}

/* The seeded walk is a Riftbound Epic card: the row holds the parts, the finish, the rarity, then the For and pick chips. The plan has
   two takes of the same card, so the REAL set text stays and only the pick chip changes: "Pick 1 of 1", then "Pick 3" and "2 short".
   `wide` is Verdana with the web fonts blocked, the face that wraps on Linux. */
for (const width of [1440, 820]) for (const wide of [false, true]) {
  test(`L3 S13: stepping to a bigger pick moves no chip left of the pick chip, real set text${wide ? ', wide face' : ''}, at ${width}`, async ({ page }) => {
    if (wide) {
      await page.route(/\.(woff2?|ttf)(\?|$)/, (route) => route.abort())
      await page.addInitScript(() => {
        document.addEventListener('DOMContentLoaded', () => {
          const st = document.createElement('style')
          st.textContent = '*{font-family:Verdana,sans-serif !important}'
          document.head.append(st)
        })
      })
    }
    const json = (route: Route, body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
    const epic = (index: number) => ({ ...card({ box: 3, index, section: 2, card: 17, name: 'Volcanion', state: 'identified', sku: '9191486', boxName: 'RB Epics', boxTotal: 133 }), rarity_claim: 'epic', metadata_finish: 'foil', game: 'riftbound', condition: 'Near Mint' })
    await page.route(/\/inventory\/copies$/, (route) => json(route, { cards: { '3/21': epic(21), '3/22': epic(22) }, listings: {} }))
    await setViewport(page, { width, height: 1000 })
    await seedPopulatedOrders(page)
    const plan = severalOrdersWalkPlan()
    const first = plan.stops[0]!.takes[0]!
    plan.stops[0]!.takes.push({ ...first, sku: '9191487', wanted: 3, copies: [{ ...first.copies[0]!, key: '3/22', place: { ...first.copies[0]!.place, index: 22 } }] })
    await page.route(/\/orders\/walk-plan$/, (route) => json(route, plan))
    await page.goto(screen('orders'))
    await expect(page.locator('.orders-pick-chip')).toBeVisible()
    await settleFonts(page)
    await settleMotion(page)
    const read = () =>
      page.evaluate(() => {
        const row = document.querySelector('.browse-hero-sub') as HTMLElement
        const kids = [...row.children] as HTMLElement[]
        const pick = row.querySelector('.orders-pick-chip') as HTMLElement
        const live = (pick.querySelector('.orders-pick-live') ?? pick) as HTMLElement
        const before = kids.filter((c) => c !== pick)
        const mid = before[before.length - 1]
        return {
          text: live.textContent ?? '',
          lefts: before.map((c) => Math.round(c.getBoundingClientRect().left)),
          last: kids[kids.length - 1] === pick,
          tops: new Set(kids.map((c) => Math.round(c.getBoundingClientRect().top + c.getBoundingClientRect().height / 2))).size,
          gapToPick: mid ? pick.getBoundingClientRect().left - mid.getBoundingClientRect().right : null,
          gap: parseFloat(getComputedStyle(row).columnGap),
          kinds: before.map((c) => c.className),
        }
      })
    const a = await read()
    await page.keyboard.press('ArrowRight')
    await expect(page.locator('.orders-pick-chip')).toContainText('2 short')
    await settleMotion(page)
    const b = await read()
    expect(a.text, 'the first pick says "of"').toContain('of 1')
    expect(b.text).toContain('Pick 3')
    expect(a.last && b.last, 'the pick chip is the last thing in the facts row').toBe(true)
    expect(a.kinds.some((k) => k.includes('bn-pill-outline')), 'the card has a finish and a rarity chip').toBe(true)
    expect(b.lefts, 'the parts, finish, rarity or For chip moved when the pick chip grew').toEqual(a.lefts)
    expect([a.tops, b.tops], 'the facts row kept one line').toEqual([1, 1])
    expect(b.gapToPick, 'no blank box between the last chip and the pick chip').toBeCloseTo(b.gap, 0)
  })
}

/* A SALE MOUNTS THE STATE PILL BEFORE THE FOR AND PICK CHIPS (the card is no longer identified once the store is re-read). Like
   Inventory's S12 it is new content, so the set text gives way for it, but the pick chip stays last and its figures hold, the row keeps one
   line and Sold keeps its own width (it never shrinks). */
test('L3 S13: a sale mounts Sold before the pick chip, which stays last, on one line, at 820', async ({ page }) => {
  const json = (route: Route, body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  let sold = false
  const epic = (state: string) => ({ ...card({ box: 3, index: 21, section: 2, card: 17, name: 'Volcanion', state, sku: '9191486', boxName: 'RB Epics', boxTotal: 133 }), rarity_claim: 'epic', metadata_finish: 'foil', game: 'riftbound', condition: 'Near Mint' })
  await page.route(/\/inventory\/copies$/, (route) => json(route, { cards: { '3/21': epic(sold ? 'sold' : 'identified') }, listings: {} }))
  await page.route(/\/orders\/pull$/, (route) => {
    sold = true
    return json(route, { undone: false, order_key: severalOrders().orders[0]!.key, sku: '9191486', newly: 1, recorded: 1, outstanding: 0, places: [], sales: [] })
  })
  await setViewport(page, { width: 820, height: 1000 })
  await seedPopulatedOrders(page)
  await page.goto(screen('orders'))
  await expect(page.locator('.orders-pick-chip')).toBeVisible()
  await settleFonts(page)
  await page.keyboard.press('1')
  await expect(page.locator('.browse-hero-sub')).toContainText('Sold')
  await settleMotion(page)
  const r = await page.evaluate(() => {
    const row = document.querySelector('.browse-hero-sub') as HTMLElement
    const kids = [...row.children] as HTMLElement[]
    const state = kids.find((c) => c.textContent === 'Sold') as HTMLElement
    return {
      stateBeforePick: kids.indexOf(state) === kids.length - 2,
      pickLast: kids[kids.length - 1]?.classList.contains('orders-pick-chip') === true,
      unclipped: state.scrollWidth <= state.clientWidth,
      lines: new Set(kids.map((c) => Math.round(c.getBoundingClientRect().top + c.getBoundingClientRect().height / 2))).size,
    }
  })
  expect(r, 'Sold sits just before the pick chip, whole, on one line').toEqual({ stateBeforePick: true, pickLast: true, unclipped: true, lines: 1 })
})

for (const width of [1440, 820]) {
  test(`L3 S14: the next card's price holds one box whatever it says, at ${width}`, async ({ page }) => {
    await setViewport(page, { width, height: 1000 })
    await POPULATED_ROUTE_SEEDS[`#/${'review'}`]?.(page)
    await page.goto(screen('review'))
    await expect(page.locator('.review-next-price')).toBeVisible()
    await settleFonts(page)
    await settleMotion(page)
    const price = '.review-next-price'
    const seen = await boxPerVariant(page, price, ['$0.10', '$4.20', '$1,234.50'], price)
    expect(new Set(seen.map((s) => s.split('|')[2])).size, `the price's width: ${seen.join(' | ')}`).toBe(1)
  })

  test(`L3 S14: the caption keeps its height from a card with no place to one with, at ${width}`, async ({ page }) => {
    await setViewport(page, { width, height: 1000 })
    await POPULATED_ROUTE_SEEDS[`#/${'review'}`]?.(page)
    const entry = (index: number, name: string, place: unknown) => ({
      position: `Box 2, Section 1, Card ${index}`, box: 2, index, label: `Box 2, Section 1, Card ${index}`,
      photo: `photos/2/${index}.jpg`, read: { name, number: '025', printed_total: '132', set_hint: 'ME01' },
      confidence: null, reason: 'no_catalog_row', candidates: [], first_seen: '2026-09-01T12:00:00+00:00',
      market: '4.20', cleared_by_human: false, ...(place === null ? {} : { place }),
    })
    const place = {
      label: 'Box 2, Section 1, Card 2', located: true, box: 2, index: 2, slot: 2, section: 1, card: 2, box_name: null,
      section_start: 1, section_end: null, box_total: 3, fraction: 0.5,
      neighbors: { prev: { name: 'Volcanion', unread: 0 }, next: { name: 'Snorlax', unread: 0 } },
    }
    await page.route(/\/queues$/, (route) =>
      json(route, { review: [entry(1, 'Volcanion', null), entry(2, 'Snorlax', place)], parked: [] }),
    )
    await page.goto(screen('review'))
    await expect(page.locator('.review-position')).toBeVisible()
    await settleFonts(page)
    await settleMotion(page)
    const height = async () => (await boxes(page, ['.review-position']))['.review-position']?.split('|')[3]
    const without = await height()
    await page.locator('.review-action', { hasText: 'Skip' }).click()
    await expect(page.locator('.review-caption-order')).toHaveCount(1)
    await settleMotion(page)
    expect(await height(), 'the caption changed height when the order line arrived').toEqual(without)
  })
}

for (const width of [1440, 820]) {
  test(`L3 S15: a box figure that gains a digit moves its sibling nowhere, at ${width}`, async ({ page }) => {
    await setViewport(page, { width, height: 1000 })
    await page.goto(screen('inventory'))
    await expect(page.locator('.boxops-stat').first()).toBeVisible()
    await settleFonts(page)
    await settleMotion(page)
    /* the figure beside a short label ("sold") gains a digit: the next stat keeps its place */
    const seen = await page.evaluate(() => {
      const stats = [...document.querySelectorAll('.boxops-stats > .boxops-stat')]
      const [one, next] = stats
      if (!one || !next) return ['absent']
      const label = one.querySelector('.bn-stat-label')
      const value = one.querySelector('.bn-stat-value')
      if (!label || !value) return ['absent']
      label.textContent = 'sold'
      const out: string[] = []
      for (const text of ['9', '10', '999']) {
        value.textContent = text
        const r = next.getBoundingClientRect()
        out.push(`${Math.round(r.left)}|${Math.round(r.top)}`)
      }
      return out
    })
    expect(seen, 'both figures must exist').not.toContain('absent')
    expect(new Set(seen).size, `the next figure's place: ${seen.join(' ; ')}`).toBe(1)
  })
}

/* S20 CANNOT RUN A CAMERA HEADLESS: the undo needs a capture, and a capture needs a stream. So this
 * reads the RESERVED BOX instead: the footer's height with its note slot empty, and with one note
 * line set into the slot. A slot that holds its room reads the same both times. */
for (const width of [1440, 820]) {
  test(`L3 S20: the Capture undo note has its room before it appears, at ${width}`, async ({ page }) => {
    await setViewport(page, { width, height: 1000 })
    await page.goto(screen('capture'))
    await expect(page.locator('.capture-film')).toBeVisible()
    await settleFonts(page)
    await settleMotion(page)
    const heights = await page.evaluate(() => {
      const film = document.querySelector('.capture-film')
      if (!film) return ['absent']
      const home = film.querySelector('.capture-undo-note') ?? film
      const keep = home.innerHTML
      const out: string[] = []
      for (const html of ['', '<p class="capture-quiet">Undid the last capture, back to Box 2, Card 4.</p>']) {
        home.innerHTML = html
        out.push(String(Math.round(film.getBoundingClientRect().height)))
      }
      home.innerHTML = keep
      return out
    })
    expect(new Set(heights).size, `the film strip's height, empty then noted: ${heights.join(' | ')}`).toBe(1)
  })
}

// L2 shell
/* THE SHELL AND GLOBAL CAUSES OF SHAKE (docs/specs/stability.md classes D, F, G, H, I). Each case
   is red on the code it guards and green after the fix. The browser is the check: a static scan
   cannot read a scrollbar, a banner or a font swap. */
const SHELL_BUDGET = 0.001

const STATUS_OK = JSON.stringify({ captures_root: 'captures', store: 's', store_exists: true, cards: 122, states: {}, queues: { review: 0, parked: 0 }, next_index: {} })

/* Playwright's headless Chromium starts with `--hide-scrollbars`, so a document scrollbar never takes
   width and the case would pass on any code. This case launches its own browser without the flag. A
   platform that draws overlay bars (macOS by default) has no gutter to reserve, so the case skips
   there and runs where bars are classic (Linux CI, Windows). */
test('L2 shell: a scrollbar coming or going moves nothing sideways (S7)', async ({ playwright, baseURL }) => {
  const browser = await playwright.chromium.launch({ ignoreDefaultArgs: ['--hide-scrollbars'] })
  try {
    const page = await browser.newPage({ baseURL, viewport: { width: 1440, height: 3000 } })
    await page.goto('/#/')
    await expect(page.locator('.bn-shell-main')).toBeVisible()
    await settleFonts(page)
    const probe = () =>
      page.evaluate(() => ({ main: document.querySelector('.bn-shell-main')!.getBoundingClientRect().width, bar: innerWidth - document.documentElement.clientWidth }))
    const short = await probe()
    await page.evaluate(() => {
      const pad = document.createElement('div')
      pad.style.height = '9000px'
      document.body.append(pad)
    })
    const tall = await probe()
    test.skip(tall.bar === 0 && short.bar === 0, 'this platform draws overlay scrollbars: no width to reserve')
    expect(tall.main, 'the shell is one width with or without a document scrollbar').toBe(short.main)
  } finally {
    await browser.close()
  }
})


test('L2 shell: the offline banner overlays and moves nothing (S6)', async ({ page }) => {
  await watchShifts(page)
  await setViewport(page, { width: 1440, height: 1000 })
  /* A screen whose own content does not read the server's status, so a shift here is the banner's. */
  await page.goto(screen('graveyard'))
  await settleFonts(page)
  const top = () => page.evaluate(() => document.querySelector('.bn-view')!.getBoundingClientRect().top)
  const before = await top()
  const mark = await markNow(page)
  await page.unroute(/\/status$/)
  await page.route(/\/status$/, (route) => route.abort())
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await expect(page.locator('.bn-banner')).toBeVisible()
  await page.waitForTimeout(600)
  expect(await top(), 'the view holds its place under the banner').toBe(before)
  const moved = (await readShifts(page)).shifts.filter((s) => s.at >= mark)
  expect(sumOf(moved), describeShifts(moved)).toBeLessThan(SHELL_BUDGET)
  await page.unroute(/\/status$/)
  await page.route(/\/status$/, (route) => route.fulfill({ status: 200, contentType: 'application/json', body: STATUS_OK }))
  /* A poll still in flight from the refused answer can land after the first Retry and put the banner back, so the press repeats until the banner stays gone. */
  await expect(async () => {
    const retry = page.getByRole('button', { name: 'Retry' })
    if ((await retry.count()) > 0) await retry.click()
    await expect(page.locator('.bn-banner')).toHaveCount(0, { timeout: 1500 })
  }).toPass({ timeout: 15_000 })
})

/* THE SERVER GOING AWAY MOVES NO CONTENT ON HOME (D313). The standing line reads the status, so an
   offline status changes what it says. It keeps its frame: nothing under it moves. */
test('L2 shell: Home holds its frame when the server goes offline (S6)', async ({ page }) => {
  await watchShifts(page)
  await setViewport(page, { width: 1440, height: 1000 })
  await page.goto(screen(''))
  await settleFonts(page)
  await page.waitForTimeout(2500)
  const mark = await markNow(page)
  await page.unroute(/\/status$/)
  await page.route(/\/status$/, (route) => route.abort())
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await expect(page.locator('.bn-banner')).toBeVisible()
  await page.waitForTimeout(800)
  const moved = (await readShifts(page)).shifts.filter((x) => x.at >= mark)
  expect(sumOf(moved), describeShifts(moved)).toBeLessThan(SHELL_BUDGET)
  await page.unroute(/\/status$/)
  await page.route(/\/status$/, (route) => route.fulfill({ status: 200, contentType: 'application/json', body: STATUS_OK }))
  await expect(async () => {
    const retry = page.getByRole('button', { name: 'Retry' })
    if ((await retry.count()) > 0) await retry.click()
    await expect(page.locator('.bn-banner')).toHaveCount(0, { timeout: 1500 })
  }).toPass({ timeout: 15_000 })
})

test('L2 shell: a new toast leaves the older ones where they are (S16)', async ({ page }) => {
  await setViewport(page, { width: 1440, height: 1000 })
  await page.goto('/#/')
  await settleFonts(page)
  const send = (n: number) =>
    page.evaluate(async (i) => {
      const { toast } = await import(/* @vite-ignore */ ['/src/kit', 'toast.tsx'].join('/'))
      toast({ kind: 'receipt', title: `Sold card ${i}`, body: 'Marked sold.', action: { label: 'Undo', kbd: 'U', onPress: () => {} } })
    }, n)
  const first = page.locator('.bn-toast').first()
  await send(1)
  await expect(first).toBeVisible()
  await page.waitForTimeout(500)
  const at = await first.boundingBox()
  await send(2)
  await send(3)
  await page.waitForTimeout(500)
  expect(await first.boundingBox(), 'the first toast holds its place under two newer ones').toEqual(at)
})

const sendToast = (page: Page, i: number, ttlMs: number) =>
  page.evaluate(
    async ([n, ttl]) => {
      const { toast } = await import(/* @vite-ignore */ ['/src/kit', 'toast.tsx'].join('/'))
      toast({ kind: 'receipt', title: `Sold card ${n}`, body: 'Marked sold.', ttlMs: ttl, action: { label: 'Undo', kbd: 'U', onPress: () => {} } })
    },
    [i, ttlMs] as const,
  )

test('L2 shell: a toast expiring leaves the others where they are (S16)', async ({ page }) => {
  await setViewport(page, { width: 1440, height: 1000 })
  await page.goto('/#/')
  await settleFonts(page)
  await sendToast(page, 1, 900)
  await sendToast(page, 2, 20000)
  const second = page.locator('.bn-toast', { hasText: 'Sold card 2' })
  await expect(second).toBeVisible()
  await page.waitForTimeout(300)
  const at = await second.boundingBox()
  await page.waitForTimeout(1500)
  expect(await second.boundingBox(), 'the second toast holds its place when the first expires').toEqual(at)
})

test('L2 shell: a toast past the fifth leaves the others where they are (S16)', async ({ page }) => {
  await setViewport(page, { width: 1440, height: 1000 })
  await page.goto('/#/')
  await settleFonts(page)
  for (const i of [1, 2, 3, 4, 5]) await sendToast(page, i, 20000)
  const second = page.locator('.bn-toast', { hasText: 'Sold card 2' })
  await expect(second).toBeVisible()
  await page.waitForTimeout(500)
  const at = await second.boundingBox()
  await sendToast(page, 6, 20000)
  await page.waitForTimeout(600)
  expect(await second.boundingBox(), 'the sixth toast does not move the second').toEqual(at)
})

/* A FACE THAT ARRIVES LATE MOVES NOTHING. The web faces are `font-display: optional`: a face not ready for
   first paint is never swapped in, so the page keeps what its stack drew first. The case holds every font
   file until it lets them go, draws one probe line in each of the three stacks, and measures it before and
   after the files land. The boxes must be the same, and no layout-shift entry may follow the release. The
   outcome is the same on every platform, whatever fallback face the system supplies. */
test('L2 shell: web fonts arriving late move nothing (S17)', async ({ page }) => {
  let release: () => void = () => {}
  const gate = new Promise<void>((done) => {
    release = done
  })
  await page.route(/\.woff2(\?|$)/, async (route) => {
    await gate
    await route.fallback()
  })
  await watchShifts(page)
  await setViewport(page, { width: 1440, height: 1000 })
  /* `load` waits on the held files (a preload is a load blocker), so the case waits for the commit. */
  await page.goto('/#/', { waitUntil: 'commit' })
  await expect(page.locator('.bn-shell-main')).toBeVisible()
  const read = () =>
    page.evaluate(() => {
      const out: Record<string, { w: number; h: number }> = {}
      for (const [name, weight] of [['display', 700], ['ui', 400], ['ui-bold', 700], ['mono', 400]] as const) {
        let probe = document.getElementById(`l2-${name}`)
        if (probe === null) {
          probe = document.createElement('span')
          probe.id = `l2-${name}`
          probe.textContent = 'Charizard ex 006/165 Near Mint Holo, 12 copies, $12.50 market price'
          probe.style.cssText = `position:absolute;left:0;top:0;white-space:nowrap;font-size:14px;font-weight:${weight};font-family:var(--bn-font-${name.replace('-bold', '')})`
          document.body.append(probe)
        }
        const r = probe.getBoundingClientRect()
        out[name] = { w: r.width, h: r.height }
      }
      return out
    })
  const before = await read()
  /* Past the block period, so a face that lands now would be a late one. */
  await page.waitForTimeout(500)
  const mark = await markNow(page)
  release()
  await page.evaluate(() => document.fonts.ready)
  await page.waitForTimeout(500)
  const after = await read()
  const moved = (await readShifts(page)).shifts.filter((x) => x.at >= mark)
  const off = Object.keys(before)
    .filter((k) => Math.abs(after[k]!.w - before[k]!.w) > 0.01 || Math.abs(after[k]!.h - before[k]!.h) > 0.01)
    .map((k) => `${k} ${before[k]!.w}x${before[k]!.h} to ${after[k]!.w}x${after[k]!.h}`)
  expect(off, 'a probe line changes box when the web face lands').toEqual([])
  expect(sumOf(moved), describeShifts(moved)).toBe(0)
})

test('L2 shell: a Sales podium thumbnail arriving moves nothing (S18)', async ({ page }) => {
  const STOCK = 'https://tcgplayer-cdn.tcgplayer.com/product/705996_200w.jpg'
  await page.route(STOCK, async (route) => {
    await new Promise((r) => setTimeout(r, 2000))
    await route.fulfill({ status: 200, contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="63" height="88"><rect width="63" height="88" fill="#ccc"/></svg>' })
  })
  const order = {
    key: 'TCGplayer:ORD-1', source: 'TCGplayer', number: 'ORD-1', placed_at: '2026-09-10T10:00:00+00:00', status: 'Shipped',
    first_seen: '2026-09-10T10:05:00+00:00', changed_at: null, buyer: 'Ada', wanted: 1, recorded: 1, open: false, terminal: true, progress: [],
    lines: [{ sku: '9100001', quantity: 1, name: 'Charizard ex', number: '006', printing: 'Holo', condition: 'Near Mint', rarity: 'Rare', unit_price: '12.50', kind: null }],
  }
  await page.route(/\/orders$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ summary: '1 order', orders: [order], resolution: { orders: [], counts: { resolved: 0, short: 0, no_copies_on_hand: 0, sku_unknown: 0, sku_unseen: 0, not_a_single: 0 } } }) }),
  )
  await page.route(/\/skus\/photos\?/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ photos: {}, stock_photos: { '9100001': STOCK } }) }),
  )
  await pricedShelf(page)
  await watchShifts(page)
  await setViewport(page, { width: 1440, height: 1000 })
  await page.goto(`/#/revenue`)
  await expect(page.locator('.revenue-podium .revenue-tile').first()).toBeVisible()
  await page.waitForTimeout(1500)
  const mark = await markNow(page)
  await expect(page.locator('.revenue-podium .bn-thumb-img').first()).toBeVisible({ timeout: 8000 })
  await page.waitForTimeout(600)
  const moved = (await readShifts(page)).shifts.filter((s) => s.at >= mark)
  expect(sumOf(moved), describeShifts(moved)).toBe(0)
})

test('L2 shell: the Fulfiller column does not animate its width (S19)', async ({ page }) => {
  await setViewport(page, { width: 1440, height: 1000 })
  await page.goto('/#/fulfillment')
  const column = page.locator('.ff-column')
  await expect(column).toBeVisible()
  const props = await column.evaluate((el) => getComputedStyle(el).transitionProperty)
  expect(props, 'a layout transition moves the content on every frame').not.toMatch(/max-width|width|height|margin|padding/)
})


/* A SALE NEVER MOVES THE CARD HEADER (D313). The sale press sits in the location panel; the Sold chip it
   draws in the header's facts row used to wrap onto a line of its own and push the stats, the photo and
   the panel down by one line. `wide` is Verdana with the web fonts blocked, the face that wraps on Linux.
   The chip set is a foil finish and a rarity, beside a set name long enough to fill the row, the one place a
   chip arriving wraps. The sidebar is open (it narrows the header); the facts row must stay one pill tall. */
const HERO_PARTS = ['.browse-hero-head', '.browse-hero-sub', '.browse-hero-side', '.browse-photo-frame', '.card-locations'] as const
const HINT = 'Spiritforged Unleashed'
for (const width of [1440, 820]) for (const wide of [false, true]) {
  test(`held frame: marking a copy sold and undoing it moves nothing in the card header${wide ? ', wide face' : ''}, at ${width}`, async ({ page }) => {
    test.setTimeout(120_000)
    if (wide) {
      await page.route(/\.(woff2?|ttf)(\?|$)/, (route) => route.abort())
      await page.addInitScript(() => {
        document.addEventListener('DOMContentLoaded', () => {
          const st = document.createElement('style')
          st.textContent = '*{font-family:Verdana,sans-serif !important}'
          document.head.append(st)
        })
      })
    }
    await l1Inventory(page)
    /* The sidebar open narrows the header, which is where the chip wraps; seeded before first paint. */
    await page.addInitScript((value) => {
      try {
        /* eslint-disable-next-line no-restricted-syntax -- seeding the shell's own device key, as `page-edge.spec.ts:withRail` does. */
        window.localStorage.setItem('banchi.rail', value)
      } catch {
        /* unreadable storage reads as never chosen */
      }
    }, 'wide')
    const mine = L1_CARDS['2/1'] as Record<string, unknown>
    const kept = { ...mine }
    Object.assign(mine, { metadata_finish: 'foil', rarity_claim: ['Common'], game: 'riftbound', number: '047', printed_total: '221' })
    try {
      const json = (route: Route, body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
      await page.route(/\/inventory\/2\/1\/sold$/, (route) => {
        const undo = (route.request().postDataJSON() as { undo?: boolean } | null)?.undo === true
        mine.state = undo ? 'identified' : 'sold'
        return json(route, { position: '2/1', box: 2, index: 1, undone: undo, state: mine.state, previous_state: undo ? 'sold' : 'identified', restores_to: undo ? null : 'identified', listing: null, card: null })
      })
      await setViewport(page, { width, height: 1000 })
      const read = () =>
        page.evaluate((sels) => sels.map((s) => { const r = document.querySelector(s)?.getBoundingClientRect(); return r ? [s, r.x, r.y, r.width, r.height] : [s] }), [...HERO_PARTS])
      const oneRow = () =>
        page.evaluate(() => {
          const sub = document.querySelector('.browse-hero-sub')?.getBoundingClientRect().height ?? 0
          const pill = document.querySelector('.browse-hero-sub .bn-pill')?.getBoundingClientRect().height ?? -1
          return Math.abs(sub - pill) < 1
        })
      const bad: string[] = []
      {
        mine.state = 'identified'
        mine.set_hint = HINT
        await page.goto('about:blank')
        await page.goto(screen('inventory'))
        await page.locator('.browse-boxcell', { hasText: 'SV commons' }).click()
        await expect(page.locator('.card-locations').first()).toBeVisible()
        await settleFonts(page)
        await page.waitForTimeout(500)
        const before = await read()
        if (!(await oneRow())) bad.push('before: the facts row is not one pill tall')
        await page.getByRole('button', { name: /Mark sold/ }).first().click()
        await expect(page.locator('.browse-hero-sub')).toContainText('Sold')
        await page.waitForTimeout(500)
        if (JSON.stringify(await read()) !== JSON.stringify(before)) bad.push('sale')
        if (!(await oneRow())) bad.push('sale: the facts row is not one pill tall')
        await page.getByRole('button', { name: /^Undo/ }).first().click()
        await expect(page.locator('.browse-hero-sub')).not.toContainText('Sold')
        await page.waitForTimeout(500)
        if (JSON.stringify(await read()) !== JSON.stringify(before)) bad.push('undo')
        if (!(await oneRow())) bad.push('undo: the facts row is not one pill tall')
      }
      expect(bad, 'these moved the card header').toEqual([])
    } finally {
      Object.assign(mine, kept)
    }
  })
}

/* ORDERS: A SALE AND ITS UNDO MOVE NOTHING THE PERSON DID NOT MOVE (D313). The list leads with the
   buyers whose every owed copy is in the boxes (D296), so readiness is a sort key a sale can change.
   The sale takes Ada's one copy and leaves her owing one with none on hand: no longer ready. The undo
   gives it back: ready again, the "a buyer becomes ready" case. Neither re-sorts the rows; the order
   is retaken only on the next sort, filter or search press. The headline's figures change, and its
   stats, the filter bar with Walk in it, and every row keep their boxes. `wide` is Verdana with the
   web fonts blocked. */
const ORDERS_PARTS = ['.bn-verdict', '.orders-headline .bn-stat:nth-child(4)', '.orders-filterbar', '.orders-walkall', '.orders-buyers-panel', '.orders-panel'] as const
for (const width of [1440, 820]) for (const wide of [false, true]) {
  test(`held frame: a sale and its undo on Orders move no row, no stat and no press${wide ? ', wide face' : ''}, at ${width}`, async ({ page }) => {
    if (wide) {
      await page.route(/\.(woff2?|ttf)(\?|$)/, (route) => route.abort())
      await page.addInitScript(() => {
        document.addEventListener('DOMContentLoaded', () => {
          const st = document.createElement('style')
          st.textContent = '*{font-family:Verdana,sans-serif !important}'
          document.head.append(st)
        })
      })
    }
    await l1Orders(page)
    const ready = severalOrders()
    const sold = severalOrders()
    sold.orders[0] = order({ wanted: 2, recorded: 1 })
    sold.resolution.orders[0] = {
      key: sold.orders[0].key,
      number: sold.orders[0].number,
      complete: false,
      outstanding: 1,
      lines: [line({ reason: 'no_copies_on_hand', owed: 1, outstanding: 1, on_hand: 0, picks: [], fulfilled: 0 })],
    }
    let afterSale = false
    const json = (route: Route, body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
    await page.route(/\/orders$/, (route) => json(route, afterSale ? sold : ready))
    await page.route(/\/orders\/pull$/, (route) => {
      const undo = (route.request().postDataJSON() as { undo?: boolean } | null)?.undo === true
      afterSale = !undo
      return json(route, { undone: undo, order_key: ready.orders[0]!.key, sku: '9191486', newly: undo ? -1 : 1, recorded: undo ? 0 : 1, outstanding: undo ? 1 : 0, places: [], sales: [] })
    })
    await setViewport(page, { width, height: 1000 })
    const read = () =>
      page.evaluate((sels) => {
        const boxes = sels.map((s) => { const r = document.querySelector(s)?.getBoundingClientRect(); return r ? [s, r.x, r.y, r.width, r.height] : [s] })
        const rows = [...document.querySelectorAll('.orders-index-row')].map((row) => { const r = row.getBoundingClientRect(); return [row.querySelector('.orders-index-number')?.textContent, r.x, r.y] })
        return JSON.stringify([boxes, rows])
      }, [...ORDERS_PARTS])
    const pickFigure = page.locator('.orders-headline .bn-stat').nth(2).locator('.bn-stat-value')
    await page.goto(screen('orders'))
    await expect(page.locator('.orders-walk-list')).toBeVisible()
    await settleFonts(page)
    await settleMotion(page)
    const before = await read()
    const was = await pickFigure.textContent()
    const bad: string[] = []
    await page.getByRole('button', { name: /Mark sold/ }).first().click()
    await expect(pickFigure).not.toHaveText(was ?? '')
    await settleMotion(page)
    if ((await read()) !== before) bad.push('sale')
    await page.getByRole('button', { name: /^Undo/ }).first().click()
    await expect(pickFigure).toHaveText(was ?? '')
    await settleMotion(page)
    if ((await read()) !== before) bad.push('undo, the buyer ready again')
    expect(bad, 'these moved something the person did not move').toEqual([])
  })
}

/* ORDERS: THE STRIP, THE HERO AND THE PANEL HOLD THEIR FRAMES (D313). The walk draws the open buyer's
   photographs in a strip over Inventory's card view. Opening a buyer, stepping to the next one, a sale
   and its undo move none of the three until the person moves them: while the plan is out the old buyer
   stands in the same boxes, and a sale or an undo leaves every box where it was. The plan here has
   three takes for every buyer, so the strip is drawn. `wide` is Verdana with the web fonts blocked. */
const STRIP_PARTS = ['.orders-strip', '.orders-cardcol .browse-band', '.orders-cardcol .browse-photo-frame', '.orders-panel', '.orders-pick-nav'] as const
for (const width of [1440, 820]) for (const wide of [false, true]) {
  const via = (name: string) => `held frame: ${name}${wide ? ', wide face' : ''}, at ${width}`
  const stripScreen = async (page: Page): Promise<{ gate: { on: boolean }; boxes: () => Promise<string> }> => {
    if (wide) {
      await page.route(/\.(woff2?|ttf)(\?|$)/, (route) => route.abort())
      await page.addInitScript(() => {
        document.addEventListener('DOMContentLoaded', () => {
          const st = document.createElement('style')
          st.textContent = '*{font-family:Verdana,sans-serif !important}'
          document.head.append(st)
        })
      })
    }
    await seedPopulatedOrders(page)
    const gate = { on: false }
    await page.route(/\/orders\/walk-plan$/, async (route) => {
      if (gate.on) await new Promise((r) => setTimeout(r, READ_MS))
      const plan = severalOrdersWalkPlan()
      const stop = plan.stops[0]!
      stop.takes = [0, 1, 2].map((i) => ({ ...stop.takes[0]!, sku: `919148${i}` }))
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(plan) })
    })
    await setViewport(page, { width, height: 1000 })
    await watchShifts(page)
    const boxes = () =>
      page.evaluate((sels) => JSON.stringify(sels.map((s) => { const r = document.querySelector(s)?.getBoundingClientRect(); return r ? [s, r.x, r.y + window.scrollY, r.width, r.height] : [s] })), [...STRIP_PARTS])
    return { gate, boxes }
  }

  for (const [name, press] of [
    ['opening a buyer', (page: Page) => page.getByRole('button', { name: 'Grace Hopper' }).first().click()],
    ['stepping to the next buyer', (page: Page) => page.keyboard.press('ArrowDown')],
  ] as const) {
    test(via(`${name} holds the strip, the hero and the panel until the plan lands`), async ({ page }) => {
      const { gate, boxes } = await stripScreen(page)
      await page.goto(screen('orders'))
      await expect(page.locator('.orders-strip')).toBeVisible()
      await settleFonts(page)
      await settleMotion(page)
      const before = await boxes()
      const r = await heldPress(page, gate, async () => {
        await press(page)
        await page.waitForTimeout(250)
        expect(await boxes(), 'a box moved while the plan was out').toBe(before)
      })
      expectHeld(r, 0.001)
    })
  }

  test(via('a sale and its undo move neither the strip, the hero nor the panel'), async ({ page }) => {
    const { boxes } = await stripScreen(page)
    await page.route(/\/orders\/pull$/, (route) => {
      const undo = (route.request().postDataJSON() as { undo?: boolean } | null)?.undo === true
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ undone: undo, order_key: severalOrders().orders[0]!.key, sku: '9191480', newly: undo ? -1 : 1, recorded: undo ? 0 : 1, outstanding: undo ? 1 : 0, places: [], sales: [] }) })
    })
    await page.goto(screen('orders'))
    await expect(page.locator('.orders-strip')).toBeVisible()
    await settleFonts(page)
    await settleMotion(page)
    const before = await boxes()
    const bad: string[] = []
    await page.getByRole('button', { name: /Mark sold/ }).first().click()
    await expect(page.locator('.orders-strip-card.is-done').first()).toBeVisible()
    await settleMotion(page)
    if ((await boxes()) !== before) bad.push('sale')
    await page.getByRole('button', { name: /^Undo/ }).first().click()
    await expect(page.locator('.orders-strip-card.is-done')).toHaveCount(0)
    await settleMotion(page)
    if ((await boxes()) !== before) bad.push('undo')
    expect(bad, 'these moved something the person did not move').toEqual([])
  })
}
