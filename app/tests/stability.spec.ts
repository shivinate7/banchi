// Protects: nothing on screen moves unless the person moved it. Case one: a screen holds its final frame from the first paint.
// Governs: D313, D280
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test, expect, type Page } from '@playwright/test'
import { sealEveryTest } from './shell'
import { settleFonts } from './fontsReady'
import { routesFromNav } from './routes'
import { POPULATED_ROUTE_SEEDS, PRODUCT_ROUTE } from './routeFixtures'
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

// L2 shell
/* THE SHELL AND GLOBAL CAUSES OF SHAKE (docs/specs/stability.md classes D, F, G, H, I). Each case
   is red on the code it guards and green after the fix. The browser is the check: a static scan
   cannot read a scrollbar, a banner or a font swap. */
const SHELL_BUDGET = 0.001
const FONT_BUDGET = 0.0002

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
  await page.goto('/#/')
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
  await page.getByRole('button', { name: 'Retry' }).click()
  await expect(page.locator('.bn-banner')).toHaveCount(0)
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

test('L2 shell: a receipt holds its size while it stands (S16)', async ({ page }) => {
  await setViewport(page, { width: 1440, height: 1000 })
  await page.goto('/#/')
  await settleFonts(page)
  await page.evaluate(async () => {
    const { toast } = await import(/* @vite-ignore */ ['/src/kit', 'toast.tsx'].join('/'))
    toast({ kind: 'receipt', title: 'Sold Charizard ex', body: 'Marked sold. Undo puts it back.', action: { label: 'Undo', kbd: 'U', onPress: () => {} } })
  })
  const one = page.locator('.bn-toast')
  await expect(one).toBeVisible()
  const sizes: number[] = []
  for (let i = 0; i < 8; i += 1) {
    sizes.push(await one.evaluate((el) => (el as HTMLElement).offsetHeight))
    await page.waitForTimeout(100)
  }
  expect(new Set(sizes).size, `heights ${sizes.join(',')}`).toBe(1)
})

test('L2 shell: web fonts arriving late move nothing (S17)', async ({ page }) => {
  test.setTimeout(120_000)
  await page.route(/\.woff2(\?|$)/, async (route) => {
    await new Promise((r) => setTimeout(r, 2000))
    await route.fallback()
  })
  await watchShifts(page)
  await setViewport(page, { width: 1440, height: 1000 })
  const over: string[] = []
  for (const route of ['#/', '#/inventory', '#/revenue', '#/fulfillment']) {
    await page.goto('about:blank')
    await page.goto(`/${route}`)
    await page.waitForTimeout(3500)
    const shifts = (await readShifts(page)).shifts.filter((s) => s.at > 1900 && s.at < 2600)
    const sum = sumOf(shifts)
    if (sum >= FONT_BUDGET) over.push(`${route} ${sum.toFixed(4)} ${describeShifts(shifts)}`)
  }
  expect(over, 'a swap from the fallback face moves the page').toEqual([])
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
  await page.goto('/#/revenue')
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
