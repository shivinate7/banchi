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

  test(`L3 S13: the pick chip holds one box whether or not copies are short, at ${width}`, async ({ page }) => {
    await openOrdersWalk(page, width)
    const chip = '.orders-pick-chip'
    await expect(page.locator(chip)).toBeVisible()
    const seen = await boxPerVariant(
      page,
      chip,
      [
        '<span class="bn-pill bn-pill-accent">Pick 1 of 2</span>',
        '<span class="bn-pill bn-pill-accent">Pick 12</span> <span class="bn-pill bn-pill-warn">12 short</span>',
      ],
      chip,
    )
    expect(seen, 'the chip must exist').not.toContain('absent')
    expect(new Set(seen.map((s) => s.split('|')[2])).size, `the chip's width: ${seen.join(' | ')}`).toBe(1)
  })
}

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
