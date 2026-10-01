// Protects: a screen that loads late holds its final frame from the first paint, so nothing moves when data lands.
// Governs: D-loading-holds-loaded-size, D280
import { test, expect, type Page } from '@playwright/test'
import { sealEveryTest } from './shell'
import { settleFonts } from './fontsReady'
import { routesFromNav } from './routes'
import { POPULATED_ROUTE_SEEDS, PRODUCT_ROUTE } from './routeFixtures'
import { EXCLUDED_FROM_SWEEP } from './routeExclusions'
import { setViewport } from './phoneSwitch'
import allow from './load-shift-allow.json'

/* LOAD-TIME LAYOUT SHIFT, PER SCREEN, UNDER A SLOW SERVER.
 *
 * Every read the app makes is held 800ms before the stub answers, so an area that draws a
 * different box while it waits shows up as a `layout-shift` entry. The sum is taken with no
 * recent-input exclusion over the first 3s of the document, and the sources name what moved.
 * The measure is the browser's own, so a font or a CI box cannot tune it. */
sealEveryTest({ store: true, cards: 122 })

const SLOW_MS = 800
const WINDOW_MS = 3000
const BUDGET = 0.01

interface Shift { value: number; at: number; moved: string[] }

async function watchShifts(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const w = window as unknown as { __shifts: unknown[] }
    w.__shifts = []
    new PerformanceObserver((list) => {
      for (const e of list.getEntries() as unknown as {
        value: number; startTime: number; sources: { node: Node | null }[]
      }[]) {
        const name = (n: Node | null) => {
          const el = n instanceof Element ? n : n?.parentElement
          if (!el) return '?'
          const cls = typeof el.className === 'string' && el.className.trim() ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : ''
          return el.tagName.toLowerCase() + cls
        }
        w.__shifts.push({ value: e.value, at: e.startTime, moved: e.sources.map((s) => name(s.node)) })
      }
    }).observe({ type: 'layout-shift', buffered: true })
  })
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
  const all = await page.evaluate(() => (window as unknown as { __shifts: Shift[] }).__shifts)
  const shifts = all.filter((s) => s.at < WINDOW_MS)
  return { sum: shifts.reduce((a, s) => a + s.value, 0), shifts }
}

for (const width of [1440, 820]) {
  test(`load shift under a slow server at ${width}`, async ({ page }) => {
    test.setTimeout(240_000)
    for (const seed of Object.values(POPULATED_ROUTE_SEEDS)) await seed(page)
    await slowReads(page)
    await watchShifts(page)
    await setViewport(page, { width, height: 1000 })
    const routes = (await routesFromNav(page)).filter((r) => !EXCLUDED_FROM_SWEEP.test(r))
    routes.push(PRODUCT_ROUTE)
    const excused = allow as Record<string, string>
    const over: string[] = []
    const stale: string[] = []
    const table: string[] = []
    for (const route of routes) {
      const { sum, shifts } = await shiftOf(page, route)
      table.push(
        `${width} ${route} ${sum.toFixed(4)} ` +
          shifts.map((s) => `${s.value.toFixed(3)}@${Math.round(s.at)}[${s.moved.join(',')}]`).join(' '),
      )
      if (route in excused) {
        if (sum < BUDGET) stale.push(`${route} now passes: delete its entry in load-shift-allow.json`)
      } else if (sum >= BUDGET) over.push(`${route} ${sum.toFixed(4)}`)
    }
    console.log('SHIFT\n' + table.join('\n'))
    expect(over, 'screens that shift while loading').toEqual([])
    expect(stale, 'a stale exception').toEqual([])
  })
}
