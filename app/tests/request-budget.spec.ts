// Protects: the client asks the capture server for no more than a screen needs, and never keeps asking for a screen that is gone.
// Governs: D207
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { test, expect, type Page, type Request } from '@playwright/test'
import { sealEveryTest } from './shell'
import { routesFromNav } from './routes'
import { EXCLUDED_FROM_SWEEP } from './routeExclusions'
import { POPULATED_ROUTE_SEEDS, PRODUCT_ROUTE } from './routeFixtures'
import { openSettled } from './routeSweep'
import { setViewport } from './phoneSwitch'

/* THE CLIENT REQUEST BUDGET, PER SCREEN.
 *
 * Every nav screen is opened once, cold, against the populated stubs, and left running on a
 * fake clock for a minute. The stub answers every read slowly, so a burst shows as requests
 * in flight and a screen that re-asks shows as the same path twice. Two instruments read the
 * same walk: the browser's own `request` events (in flight, aborts, URL size) and a page-side
 * log stamped by the FAKE clock (spacing), because a poll is only slow or fast in page time.
 *
 * A NEW SCREEN IS COVERED BY ITS ROUTES ENTRY, `routesFromNav`, with no edit here. An overage
 * is an entry in `request-budget-allow.json`, keyed `<rule>:<route>`, with the measurement as
 * its reason. The list only shrinks: an entry whose rule now passes fails the run. */
sealEveryTest({ store: true, cards: 122 })

const HERE = dirname(fileURLToPath(import.meta.url))
const EXCUSED = JSON.parse(readFileSync(resolve(HERE, 'request-budget-allow.json'), 'utf8')) as Record<string, string>

const SLOW_MS = 300
const MAX_IN_FLIGHT = 4
const MIN_POLL_MS = 3000
const MAX_STATUS_PER_MINUTE = 5
const MINUTE_MS = 60_000
const STEP_MS = 3000
const SAME_GET_MS = 1000
const MAX_URL_BYTES = 8 * 1024

interface Logged { m: string; u: string; t: number }
interface Seen { method: string; url: string; path: string; failed: string | null; done: boolean; order: number }

const RULES = ['inflight', 'poll', 'status-rate', 'same-get', 'url-size', 'home-pricing', 'review-queues'] as const

/** `/boxes/12/photos?x=1` -> `/boxes/:n/photos`. Spacing is judged per path, not per id. */
/** A route hash by name, so no screen is typed here as a roster entry. */
const hash = (name: string): string => `#/${name}`

const shape =(url: string): string => new URL(url, 'http://x').pathname.replace(/\d+/g, ':n')

/** Fake clock first, so the page-side log below is stamped by it. Then the page-side log, then
 *  the slow answers. Every handler falls through to the shell's own stubs. */
async function instrument(page: Page): Promise<{ seen: Seen[]; peak: () => number; reset: () => void }> {
  await page.clock.install()
  await page.addInitScript(() => {
    const log: Logged[] = []
    ;(window as unknown as { __reqs: Logged[] }).__reqs = log
    const realFetch = window.fetch
    window.fetch = function (this: unknown, input: RequestInfo | URL, init?: RequestInit) {
      const m = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase()
      log.push({ m, u: input instanceof Request ? input.url : String(input), t: Date.now() })
      return realFetch.call(window, input, init)
    }
    const open = XMLHttpRequest.prototype.open
    XMLHttpRequest.prototype.open = function (this: XMLHttpRequest, method: string, url: string | URL, ...rest: unknown[]) {
      log.push({ m: method.toUpperCase(), u: String(url), t: Date.now() })
      return (open as (...a: unknown[]) => void).call(this, method, url, ...rest)
    } as typeof open
  })
  await page.route(
    () => true,
    async (route) => {
      const type = route.request().resourceType()
      if (type === 'fetch' || type === 'xhr') await new Promise((r) => setTimeout(r, SLOW_MS)) // keep: stubbed answer held SLOW_MS on purpose, a latency fixture
      await route.fallback()
    },
  )
  /* THE MOUNT IS MEASURED AS A BUILD MOUNTS IT. `main.tsx` wraps the app in `StrictMode`, which in
     the dev server runs every mount effect twice, so every first read would count double and a
     rule about "once on mount" could never hold. The entry module is served with the wrapper
     swapped for a pass-through. If the swap finds nothing to swap, the run stops: a silent miss
     would put the doubled reads back and read as the app's own. */
  await page.route(/\/src\/main\.tsx(\?|$)/, async (route) => {
    const res = await route.fetch()
    const text = await res.text()
    const body = text.replace(/(?:const|let|var)\s+StrictMode\s*=\s*[^;\n]+;?/, 'const StrictMode = ({ children }) => children;')
    if (body === text) throw new Error('request-budget: main.tsx no longer has a StrictMode binding to swap out')
    await route.fulfill({ response: res, body })
  })
  const seen: Seen[] = []
  const open = new Map<Request, Seen>()
  let peak = 0
  const isRead = (r: Request) => r.resourceType() === 'fetch' || r.resourceType() === 'xhr'
  page.on('request', (r) => {
    if (!isRead(r)) return
    const one: Seen = { method: r.method(), url: r.url(), path: shape(r.url()), failed: null, done: false, order: seen.length }
    seen.push(one)
    open.set(r, one)
    peak = Math.max(peak, open.size)
  })
  page.on('requestfinished', (r) => { const one = open.get(r); if (one) one.done = true; open.delete(r) })
  page.on('requestfailed', (r) => { const one = open.get(r); if (one) one.failed = r.failure()?.errorText ?? 'failed'; open.delete(r) })
  return { seen, peak: () => peak, reset: () => { peak = open.size } }
}

const pageLog = (page: Page): Promise<Logged[]> => page.evaluate(() => (window as unknown as { __reqs: Logged[] }).__reqs.slice())
const pageNow = (page: Page): Promise<number> => page.evaluate(() => Date.now())

/** The fake clock jumps in `STEP_MS` strides, with a beat of real time between so the slow stub
 *  can answer and the next tick has something to schedule from. */
async function runMinute(page: Page): Promise<void> {
  for (let spent = 0; spent < MINUTE_MS; spent += STEP_MS) {
    await page.clock.runFor(STEP_MS)
    await page.waitForTimeout(SLOW_MS + 100) // keep: real time for the slow stub to answer between fake-clock strides
  }
}

function judge(route: string, log: Logged[], mountEnd: number, peak: number): Record<string, string> {
  const found: Record<string, string> = {}
  const reads = log.filter((l) => l.m === 'GET')
  const after = reads.filter((l) => l.t > mountEnd)

  if (peak > MAX_IN_FLIGHT) found.inflight = `${peak} in flight, limit ${MAX_IN_FLIGHT}`

  const byPath = new Map<string, number[]>()
  for (const l of after) byPath.set(shape(l.u), [...(byPath.get(shape(l.u)) ?? []), l.t])
  const fast: string[] = []
  for (const [path, ts] of byPath) {
    const gap = Math.min(...ts.slice(1).map((t, i) => t - (ts[i] as number)))
    if (ts.length > 1 && gap < MIN_POLL_MS) fast.push(`${path} every ${gap}ms`)
  }
  if (fast.length > 0) found.poll = `${fast.join(', ')}, limit ${MIN_POLL_MS}ms`

  const status = (byPath.get('/status') ?? []).length
  if (status > MAX_STATUS_PER_MINUTE) found['status-rate'] = `${status} /status in 60s, limit ${MAX_STATUS_PER_MINUTE}`

  const twice: string[] = []
  const lastAt = new Map<string, number>()
  for (const l of reads) {
    const before = lastAt.get(l.u)
    if (before !== undefined && l.t - before < SAME_GET_MS) twice.push(`${shape(l.u)} ${l.t - before}ms apart`)
    lastAt.set(l.u, l.t)
  }
  if (twice.length > 0) found['same-get'] = `${[...new Set(twice)].join(', ')}, limit ${SAME_GET_MS}ms`

  const big = log.filter((l) => l.u.length > MAX_URL_BYTES)
  if (big.length > 0) found['url-size'] = `${shape(big[0]!.u)} ${big[0]!.u.length} bytes, limit ${MAX_URL_BYTES}`

  if (route === '#/') {
    const unscoped = reads.filter((l) => /\/(pipeline\/)?pricing$/.test(new URL(l.u, 'http://x').pathname))
    if (unscoped.length > 0) found['home-pricing'] = `${unscoped.length} unscoped pricing read on mount, limit 0`
  }
  if (route === hash('review')) {
    const queues = reads.filter((l) => new URL(l.u, 'http://x').pathname === '/queues').length
    if (queues !== 1) found['review-queues'] = `${queues} /queues reads on mount, limit 1`
  }
  return found
}

test('every screen stays inside its request budget for a minute', async ({ page }) => {
  test.setTimeout(900_000)
  const blank = Object.entries(EXCUSED).filter(([, why]) => why.trim() === '').map(([key]) => key)
  expect(blank, 'an exception with no reason: write why, or delete it').toEqual([])
  const watch = await instrument(page)
  for (const seed of Object.values(POPULATED_ROUTE_SEEDS)) await seed(page)
  await setViewport(page, { width: 1440, height: 1000 })
  const routes = (await routesFromNav(page)).filter((r) => !EXCLUDED_FROM_SWEEP.test(r))
  routes.push(PRODUCT_ROUTE)

  const over: string[] = []
  const table: string[] = []
  const used = new Set<string>()
  let polled = 0
  for (const route of routes) {
    await page.goto('about:blank')
    watch.reset()
    await openSettled(page, route)
    const mountEnd = await pageNow(page)
    await runMinute(page)
    const log = await pageLog(page)
    polled += log.filter((l) => l.t > mountEnd && shape(l.u) === '/status').length
    const found = judge(route, log, mountEnd, watch.peak())
    for (const rule of RULES) {
      const key = `${rule}:${route}`
      const what = found[rule]
      if (what === undefined) continue
      table.push(`${route} ${rule}: ${what}`)
      if (key in EXCUSED) used.add(key)
      else over.push(`${key} ${what}`)
    }
  }
  console.log('BUDGET\n' + table.join('\n'))
  expect(polled, 'the fake clock drove no /status poll: the spacing rules would pass over nothing').toBeGreaterThan(0)
  expect(over, 'screens over their request budget').toEqual([])
  const stale = Object.keys(EXCUSED).filter((k) => RULES.some((r) => k.startsWith(`${r}:`)) && !used.has(k))
  expect(stale, 'a stale exception: the rule now passes, delete its entry in request-budget-allow.json').toEqual([])
})

/* ---------------------------------------------------------------- reads after a write */

const MAX_READS_AFTER_SALE = 3
const MAX_READS_AFTER_ANSWER = 2
const QUIET_REAL_MS = 1500

/** Presses `act` and counts the GETs the page starts from the write on, until it has been quiet
 *  for `QUIET_REAL_MS`. `/status` is the shell's own poll and is never a consequence of a write. */
async function readsAfter(page: Page, seen: Seen[], isWrite: (s: Seen) => boolean, act: () => Promise<void>): Promise<string[]> {
  const from = seen.length
  await act()
  await expect.poll(() => seen.slice(from).some(isWrite), { message: 'the write never went out' }).toBe(true)
  let count = -1
  while (count !== seen.length) {
    count = seen.length
    await page.waitForTimeout(QUIET_REAL_MS) // keep: real quiet time, the burst is judged over what follows the write
  }
  const write = seen.slice(from).find(isWrite)!
  return seen.filter((s) => s.order > write.order && s.method === 'GET' && s.path !== '/status').map((s) => s.path)
}

function twoCards(): unknown[] {
  return [3, 4].map((index) => ({
    position: `2/${index}`,
    box: 2,
    index,
    label: `Box 2, Section 1, Card ${index}`,
    photo: `/tmp/box2/${index}.jpg`,
    reason: 'set_ambiguous',
    candidates: [0, 1].map((at) => ({ sku: `860${8000 + at}`, name: 'Snorlax', set: 'ME01', number: '014/132', condition: 'Near Mint', market: '12.00' })),
    market: '12.00',
    read: { name: 'Snorlax', number: '014/132', set: 'ME01' },
    confidence: 'high',
    first_seen: '2026-08-24',
    age_days: 0,
    cleared_by_human: false,
  }))
}

/** One write, then the reads it starts. A rule with an allow entry must still be over, or the
 *  entry is stale. */
function judgeBurst(rule: string, route: string, reads: string[], limit: number): void {
  const key = `${rule}:${route}`
  console.log(`BURST ${key} ${reads.length}: ${reads.join(' ')}`)
  if (key in EXCUSED) expect(reads.length, `a stale exception: ${key} now passes, delete its entry in request-budget-allow.json`).toBeGreaterThan(limit)
  else expect(reads, `${key}: more than ${limit} reads after one write`).toHaveLength(Math.min(reads.length, limit))
}

test('a sale re-reads no more than it must', async ({ page }) => {
  test.setTimeout(120_000)
  const watch = await instrument(page)
  await page.route(/\/inventory\/\d+\/\d+\/sold$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ box: 2, index: 1, position: '2/1', state: 'sold', previous_state: 'identified', sold_at: '2026-09-01T12:00:00+00:00' }) }),
  )
  await setViewport(page, { width: 1440, height: 1000 })
  await openSettled(page, hash('inventory'))
  const reads = await readsAfter(page, watch.seen, (s) => s.method === 'POST' && /\/sold$/.test(s.path), async () => {
    await page.getByRole('button', { name: 'Mark sold' }).first().click()
  })
  judgeBurst('sale-reads', hash('inventory'), reads, MAX_READS_AFTER_SALE)
})

test('a review answer re-reads no more than it must', async ({ page }) => {
  test.setTimeout(120_000)
  const watch = await instrument(page)
  await page.route(/\/queues$/, (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ review: twoCards(), parked: [] }) }))
  await page.route(/\/(answer|group-answer)$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ position: '2/3', cleared: true, restores_to: { sku: null, condition: null } }) }),
  )
  await setViewport(page, { width: 1440, height: 1000 })
  await openSettled(page, hash('review'))
  const reads = await readsAfter(page, watch.seen, (s) => s.method === 'POST' && /\/answer$/.test(s.path), async () => {
    await page.locator('.review-candidate').first().click()
  })
  judgeBurst('answer-reads', hash('review'), reads, MAX_READS_AFTER_ANSWER)
})

/* ---------------------------------------------------------------- leaving a screen */

const HOLD_MS = 1500
const MOUNT_LOOK_MS = 400
const AFTER_SWITCH_MS = 2500
/** The shell's own reads, the ones every screen's mount makes. They outlive a screen on purpose. */
const SHELL = new Set(['GET /status'])

const named = (s: Seen): string => `${s.method} ${s.path}`

test('a screen that is left stops asking, and what it had open is aborted', async ({ page }) => {
  test.setTimeout(300_000)
  const watch = await instrument(page)
  await page.route(
    () => true,
    async (route) => {
      const type = route.request().resourceType()
      if (type === 'fetch' || type === 'xhr') await new Promise((r) => setTimeout(r, HOLD_MS - SLOW_MS)) // keep: a read held HOLD_MS so it is still open when the screen is left
      await route.fallback()
    },
  )
  for (const seed of Object.values(POPULATED_ROUTE_SEEDS)) await seed(page)
  await setViewport(page, { width: 1440, height: 1000 })
  const routes = (await routesFromNav(page)).filter((r) => !EXCLUDED_FROM_SWEEP.test(r))
  routes.push(PRODUCT_ROUTE)

  /* what each screen asks for on its own mount, cold */
  const mounts = new Map<string, Set<string>>()
  for (const route of routes) {
    await page.goto('about:blank')
    const from = watch.seen.length
    await page.goto(`/${route}`)
    await page.waitForTimeout(HOLD_MS * 2) // keep: real time for the held reads and the reads they start
    mounts.set(route, new Set(watch.seen.slice(from).map(named)))
  }
  const shell = new Set([...SHELL, ...[...mounts.get(routes[0]!)!].filter((one) => routes.every((r) => mounts.get(r)!.has(one)))])

  const found = new Map<string, string[]>()
  const note = (route: string, what: string) => found.set(route, [...(found.get(route) ?? []), what])
  for (let at = 0; at + 1 < routes.length; at++) {
    const from = routes[at]!
    const to = routes[at + 1]!
    await page.goto('about:blank')
    await page.goto(`/${from}`)
    await page.waitForTimeout(MOUNT_LOOK_MS) // keep: the screen has asked, and the held reads are still open
    const mark = watch.seen.length
    const open = watch.seen.filter((s) => !s.done && s.failed === null && !shell.has(named(s)) && s.method === 'GET')
    await page.evaluate((hash) => { window.location.hash = hash }, to.slice(1))
    await page.waitForTimeout(AFTER_SWITCH_MS) // keep: real time for an abort to land, or a stale ask to start
    const kept = open.filter((s) => s.failed === null)
    if (kept.length > 0) note(from, `abort: ${kept.length} of ${open.length} open reads not aborted on leaving (${[...new Set(kept.map(named))].join(', ')})`)
    const stale = [...new Set(watch.seen.slice(mark).map(named))].filter((one) => mounts.get(from)!.has(one) && !mounts.get(to)!.has(one) && !shell.has(one))
    if (stale.length > 0) note(from, `after: ${stale.join(', ')} started after leaving`)
  }
  const over: string[] = []
  const used = new Set<string>()
  for (const [route, what] of found) {
    const key = `leave:${route}`
    console.log(`LEAVE ${route} ${what.join('; ')}`)
    if (key in EXCUSED) used.add(key)
    else over.push(`${key} ${what.join('; ')}`)
  }
  expect(over, 'screens that keep asking after they are left').toEqual([])
  const stale = Object.keys(EXCUSED).filter((k) => k.startsWith('leave:') && !used.has(k))
  expect(stale, 'a stale exception: the rule now passes, delete its entry in request-budget-allow.json').toEqual([])
})
