import { expect, type Locator, type Page, type Request } from '@playwright/test'

import { settleFonts } from './fontsReady'
import { routesFromNav } from './routes'
import { EXCLUDED_FROM_SWEEP } from './routeExclusions'
import { POPULATED_ROUTE_SEEDS, PRODUCT_ROUTE, SHIPPING_EXPORT_CSV } from './routeFixtures'

/* THE ONE SWEEP `text-shape.spec.ts`, `machine-words.spec.ts` AND `money-face.spec.ts` RUN,
 * and `make text-density` through the first of them (D-text-shape-checks). One copy, so the
 * three checks cannot disagree about which state a screen was measured in.
 *
 * THE STORE IS THE SAME AT EVERY STOP. `sealEveryTest({ store: true, cards: 122 })` is the
 * small store. Every seed in `routeFixtures.ts:POPULATED_ROUTE_SEEDS` is registered ONCE,
 * before the first navigation. Nothing in either fixture is random. The first build of these
 * specs registered each seed on arrival at its own route. The handlers then piled up in nav
 * order, so a screen drawn before `#/orders` at 1440 read an empty ledger, and the same screen
 * at 390 read a full one. That, and the load race below, was all of the "variation" the first
 * build blamed on the fixture.
 *
 * A ROUTE ARRIVING IS NOT A ROUTE LOADED. `copy-budget.spec.ts` (D194, deleted) measured it:
 * `#/inventory` painted "Reading the inventory…" under a visible `<main>`, and read 4 words
 * mid-load against 156 once painted. `openSettled` waits for five things before any caller
 * reads the screen: `.bn-shell[data-route]` names the route, exactly one `.bn-view` exists,
 * nothing on the page is `[aria-busy="true"]`, no read is open or starts, and `.bn-view`'s
 * `innerText` holds still, all over `QUIET_MS` together. The wait is generic. It never waits
 * on one screen's own loading sentence. The open-read count is what makes it hold for a SLOW
 * read: `#/inventory`'s "Reading the inventory…" carries no `aria-busy`, and a text-stability
 * wait alone returns that sentence once a read takes longer than `QUIET_MS`. The started-read
 * count is what makes a request LOOP fail every run rather than on where a sample lands.
 *
 * THE ROUTES ARE DISCOVERED: `routesFromNav` at 1440, the phone drawer at 390 (the nav links
 * are `display: none` under 768, `routes.ts`'s own header). `#/product` is off-nav, so it is
 * appended WITH a SKU (`PRODUCT_ROUTE`) — without one that screen draws only its search.
 * `#/fulfillment` and `#/gallery` are excluded (`routeExclusions.ts`).
 *
 * WHAT NO SWEEP READS. Only each route's LANDING state, plus the one export `#/shipping` is
 * handed and the SKU `#/product` is opened with. No sheet, modal, popover, toast, drawer or
 * the palette is opened, so their copy is never read. Each check reads `.bn-view` alone, so
 * the sidebar, the phone bars and the banner are never read either.
 */

/** How long `.bn-view`'s text must hold still before the screen counts as loaded. Four equal
 *  reads, 150ms apart. */
const POLL_MS = 150
const QUIET_MS = 450
const SETTLE_TIMEOUT_MS = 10_000

/** The route's own `ROUTES` path, as `App.tsx` writes it on `.bn-shell[data-route]`:
 *  `#/` -> `/`, `#/product?sku=1` -> `/product`. */
function routePath(route: string): string {
  return route.slice(1).split('?')[0] ?? '/'
}

/** The page's `fetch`/`xhr` reads, per page: the ones still waiting for an answer, and the
 *  last few STARTED, with a running count. Set up once by `trackReads`; a page nobody tracks
 *  counts as having none. */
interface Reads {
  open: Set<Request>
  started: number
  recent: string[]
}
const READS = new WeakMap<Page, Reads>()

function trackReads(page: Page): void {
  if (READS.has(page)) return
  const reads: Reads = { open: new Set(), started: 0, recent: [] }
  READS.set(page, reads)
  page.on('request', (request) => {
    if (request.resourceType() !== 'fetch' && request.resourceType() !== 'xhr') return
    reads.open.add(request)
    reads.started += 1
    reads.recent = [...reads.recent.slice(-4), `${request.method()} ${new URL(request.url()).pathname}`]
  })
  page.on('requestfinished', (request) => reads.open.delete(request))
  page.on('requestfailed', (request) => reads.open.delete(request))
}

/** Holds until, for `QUIET_MS` together, the text has not changed, no read is open and no new
 *  read has STARTED. The last clause makes a request loop fail every time: a screen that
 *  re-asks every few milliseconds has an open read at some samples and none at others, and a
 *  check of "open" alone passes or fails on where the sample lands. Throws, naming the route
 *  and the reads, when the screen never settles: that is a finding, not a pass. */
async function settledInnerText(page: Page, region: Locator, route: string): Promise<string> {
  const reads = READS.get(page)
  const deadline = Date.now() + SETTLE_TIMEOUT_MS
  let previous = await region.innerText()
  let startedBefore = reads?.started ?? 0
  let quietSince = Date.now()
  let textReset = 0
  let readsReset = 0
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, POLL_MS))
    const next = await region.innerText()
    const started = reads?.started ?? 0
    const busy = reads !== undefined && (reads.open.size > 0 || started !== startedBefore)
    if (next !== previous || busy) {
      if (busy) readsReset += 1
      if (next !== previous) textReset += 1
      previous = next
      startedBefore = started
      quietSince = Date.now()
      continue
    }
    if (Date.now() - quietSince >= QUIET_MS) return next
  }
  const why = [
    textReset > 0 ? `the text changed at ${textReset} samples` : '',
    readsReset > 0 ? `reads were open or starting at ${readsReset} samples, the last: ${reads?.recent.join(', ')}` : '',
  ].filter(Boolean)
  throw new Error(`${route}: never settled within ${SETTLE_TIMEOUT_MS}ms — ${why.join('; ')}`)
}

/** Open one route and wait until it is LOADED, not merely arrived. `#/shipping` fetches
 *  nothing on mount (`shipping.spec.ts`'s own header), so it is handed one export through the
 *  drop zone first, the way `shipping.spec.ts:readExport` does. */
export async function openSettled(page: Page, route: string): Promise<void> {
  await page.goto(`/${route}`)
  await settleFonts(page)
  await expect(page.locator('main').first(), `${route}: drew no <main>`).toBeVisible()

  if (route === '#/shipping') {
    await page.getByLabel('Read an export').setInputFiles({
      name: 'TCGplayer_ShippingExport_20260830.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(SHIPPING_EXPORT_CSV),
    })
    await expect(page.locator('a.shipping-file'), `${route}: the populated batch never drew`).toHaveCount(1)
  }

  await expect(page.locator('.bn-shell'), `${route}: the shell never reached the route`).toHaveAttribute(
    'data-route',
    routePath(route),
  )
  await expect(page.locator('.bn-view'), `${route}: not exactly one .bn-view`).toHaveCount(1)
  await expect(page.locator('[aria-busy="true"]'), `${route}: still busy`).toHaveCount(0)
  await settledInnerText(page, page.locator('.bn-view'), route)
}

/** The phone drawer's own roster, `phone.spec.ts:phoneRoutes`'s shape. `#/gallery` stays
 *  excluded (`routeExclusions.ts`). */
async function drawerRoutes(page: Page): Promise<string[]> {
  await page.goto('/')
  await page.getByText('More', { exact: true }).click()
  await expect(page.locator('.bn-drawer')).toBeVisible()
  const hrefs = await page.locator('.bn-drawer .bn-nav a.bn-nav-link').evaluateAll((els) =>
    // `/^#\//` INLINE: this callback runs in the BROWSER (`evaluateAll` serialises it by
    // `toString()`), so an imported module-level const is invisible to it.
    els.map((el) => (el as HTMLAnchorElement).getAttribute('href') ?? '').filter((h) => /^#\//.test(h)))
  await page.keyboard.press('Escape')
  await expect(page.locator('.bn-drawer')).toHaveCount(0)
  return hrefs.filter((route) => !EXCLUDED_FROM_SWEEP.test(route))
}

export type Visit = (route: string, width: number) => Promise<void>

/** Every route at 1440, then every route at 390, each opened with `openSettled` before
 *  `visit` reads it. Returns every route swept, for the callers' stale-entry checks. */
export async function sweepEveryRoute(page: Page, visit: Visit): Promise<Set<string>> {
  trackReads(page)
  for (const seed of Object.values(POPULATED_ROUTE_SEEDS)) await seed(page)

  await page.setViewportSize({ width: 1440, height: 1000 })
  const wide = (await routesFromNav(page)).filter((route) => !EXCLUDED_FROM_SWEEP.test(route))
  expect(wide.length, 'the route harvest returned too few screens to check').toBeGreaterThan(6)
  wide.push(PRODUCT_ROUTE)
  for (const route of wide) {
    await openSettled(page, route)
    await visit(route, 1440)
  }

  await page.setViewportSize({ width: 390, height: 844 })
  const phone = await drawerRoutes(page)
  expect(phone.length, 'the phone drawer harvest returned too few screens to check').toBeGreaterThan(6)
  phone.push(PRODUCT_ROUTE)
  for (const route of phone) {
    await openSettled(page, route)
    await visit(route, 390)
  }

  return new Set([...wide, ...phone])
}
