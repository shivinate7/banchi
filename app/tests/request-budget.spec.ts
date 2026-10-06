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
 * NOTHING HERE WAITS ON A WALL-CLOCK GUESS. A step is over when no read is open and none has
 * started across two frames (`quiet`), so a loaded runner takes longer and measures the same.
 *
 * A NEW SCREEN IS COVERED BY ITS ROUTES ENTRY, `routesFromNav`, with no edit here. An overage is
 * an entry in `request-budget-allow.json`, keyed `<rule>:<route>`, as `{ max, why }`. `max` is
 * the measured count today, never a time: above it fails, below it fails as stale ("lower to
 * N"), so the list only shrinks. A spacing rule pins how many paths offend, not how many
 * milliseconds. */
sealEveryTest({ store: true, cards: 122 })

const HERE = dirname(fileURLToPath(import.meta.url))
type Excuse = { max: number; why: string }
const EXCUSED = JSON.parse(readFileSync(resolve(HERE, 'request-budget-allow.json'), 'utf8')) as Record<string, Excuse>

const STILL_FRAMES = 20
const MINUTE_HOLD_MS = 0
const LEAVE_HOLD_MS = 1500
/* A read the screen has open when it is left must still be open then, however slow the runner: a
   wall-clock hold of 1.5s lost that race and the read finished on its own, read as "kept". The
   hold on the screen being left is long; it drops to nothing the moment before it is left. */
const OPEN_UNTIL_LEFT_MS = 60_000
const MIN_POLL_MS = 3000
const MINUTE_MS = 60_000
const STEP_MS = 250
const QUIET_TIMEOUT_MS = 30_000

/** Per rule, the most a screen may measure with no allow entry. */
const LIMIT = {
  inflight: 4,
  poll: 0,
  'status-rate': 5,
  'same-get': 0,
  'url-size': 8 * 1024,
  'home-pricing': 0,
  'review-queues': 1,
  'sale-reads': 3,
  'answer-reads': 2,
  leave: 0,
} as const
type Rule = keyof typeof LIMIT
const SCREEN_RULES: Rule[] = ['inflight', 'poll', 'status-rate', 'same-get', 'url-size', 'home-pricing', 'review-queues']

/** `t` starts a read and `e` ends it, both in FAKE time. A read with no `e` is still open. */
interface Logged { m: string; u: string; t: number; e?: number }
interface Seen { method: string; url: string; path: string; failed: string | null; done: boolean; order: number }
interface Watch {
  seen: Seen[]
  reset: () => void
  openCount: () => number
  openPaths: () => string[]
  hold: { ms: number; except?: (r: Request) => boolean }
  close: () => void
  release: () => void
}
interface Measure { value: number; detail: string }

/** A route hash by name, so no screen is typed here as a roster entry. */
const hash = (name: string): string => `#/${name}`

/** `/boxes/12/photos?x=1` -> `/boxes/:n/photos`. Spacing is judged per path, not per id. */
const shape = (url: string): string => new URL(url, 'http://x').pathname.replace(/\d+/g, ':n')

const named = (s: Seen): string => `${s.method} ${s.path}`

/** Fake clock first, so the page-side log below is stamped by it. Then the page-side log, then
 *  the slow answers. Every handler falls through to the shell's own stubs. */
async function instrument(page: Page): Promise<Watch> {
  await page.clock.install()
  await page.addInitScript(() => {
    const log: Logged[] = []
    ;(window as unknown as { __reqs: Logged[] }).__reqs = log
    const realFetch = window.fetch
    window.fetch = function (this: unknown, input: RequestInfo | URL, init?: RequestInit) {
      const m = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase()
      const entry: Logged = { m, u: input instanceof Request ? input.url : String(input), t: Date.now() }
      log.push(entry)
      const answer = realFetch.call(window, input, init)
      const ended = () => { entry.e = Date.now() }
      answer.then(ended).catch(ended)
      return answer
    }
    const open = XMLHttpRequest.prototype.open
    XMLHttpRequest.prototype.open = function (this: XMLHttpRequest, method: string, url: string | URL, ...rest: unknown[]) {
      const entry: Logged = { m: method.toUpperCase(), u: String(url), t: Date.now() }
      log.push(entry)
      this.addEventListener('loadend', () => { entry.e = Date.now() })
      return (open as (...a: unknown[]) => void).call(this, method, url, ...rest)
    } as typeof open
  })
  const hold: { ms: number; except?: (r: Request) => boolean } = { ms: MINUTE_HOLD_MS }
  let gate: Promise<void> = Promise.resolve()
  let open_: () => void = () => {}
  await page.route(
    () => true,
    async (route) => {
      const type = route.request().resourceType()
      if (type === 'fetch' || type === 'xhr') {
        await gate // a closed gate holds every answer until the burst has been counted
        if (!hold.except?.(route.request())) await new Promise((r) => setTimeout(r, hold.ms)) // keep: stubbed answer held on purpose, a latency fixture
      }
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
  const isRead = (r: Request) => r.resourceType() === 'fetch' || r.resourceType() === 'xhr'
  page.on('request', (r) => {
    if (!isRead(r)) return
    const one: Seen = { method: r.method(), url: r.url(), path: shape(r.url()), failed: null, done: false, order: seen.length }
    seen.push(one)
    open.set(r, one)
  })
  page.on('requestfinished', (r) => { const one = open.get(r); if (one) one.done = true; open.delete(r) })
  page.on('requestfailed', (r) => { const one = open.get(r); if (one) one.failed = r.failure()?.errorText ?? 'failed'; open.delete(r) })
  return {
    seen,
    hold,
    close: () => { gate = new Promise<void>((r) => { open_ = r }) },
    release: () => open_(),
    /* a new page starts from nothing: what the last page left open is not this page's */
    reset: () => { open.clear() },
    openCount: () => open.size,
    openPaths: () => [...open.values()].map(named).sort(),
  }
}

const pageLog = (page: Page): Promise<Logged[]> => page.evaluate(() => (window as unknown as { __reqs: Logged[] }).__reqs.slice())
const pageNow = (page: Page): Promise<number> => page.evaluate(() => Date.now())

/** Holds until no read is open and none has started across two frames. Slow runners take longer
 *  and measure the same. */
async function quiet(page: Page, watch: Watch): Promise<void> {
  const deadline = Date.now() + QUIET_TIMEOUT_MS
  for (;;) {
    const before = watch.seen.length
    await page.evaluate(() => new Promise<void>((done) => requestAnimationFrame(() => requestAnimationFrame(() => done()))))
    if (watch.openCount() === 0 && watch.seen.length === before) return
    if (Date.now() > deadline) throw new Error(`request-budget: reads never went quiet, ${watch.openCount()} still open`)
  }
}

/** Holds until no read has started for `STILL_FRAMES` frames in a row. */
async function stillFor(page: Page, watch: Watch): Promise<void> {
  const deadline = Date.now() + QUIET_TIMEOUT_MS
  let still = 0
  while (still < STILL_FRAMES) {
    const before = watch.seen.length
    await page.evaluate(() => new Promise<void>((done) => requestAnimationFrame(() => done())))
    still = watch.seen.length === before ? still + 1 : 0
    if (Date.now() > deadline) throw new Error('request-budget: reads kept starting')
  }
}

/** A minute of FAKE time in `STEP_MS` strides, every answer instant and let land before the next
 *  stride. `usePoll` asks again only after its last answer, so a stride longer than the answer's
 *  trip would hide a fast poller behind the stride itself. The minute is read off the page's own
 *  clock, which also runs a little between strides. */
async function runMinute(page: Page, watch: Watch, from: number): Promise<void> {
  while ((await pageNow(page)) - from < MINUTE_MS) {
    await page.clock.runFor(STEP_MS)
    await quiet(page, watch)
  }
}

function measure(route: string, log: Logged[], mountEnd: number, burst: number): Partial<Record<Rule, Measure>> {
  const out: Partial<Record<Rule, Measure>> = {}
  const reads = log.filter((l) => l.m === 'GET')
  const after = reads.filter((l) => l.t > mountEnd)

  out.inflight = { value: burst, detail: `${burst} reads held open at once by the mount` }

  const byPath = new Map<string, number[]>()
  for (const l of after) byPath.set(shape(l.u), [...(byPath.get(shape(l.u)) ?? []), l.t])
  const fast = [...byPath].filter(([, ts]) => ts.slice(1).some((t, i) => t - (ts[i] as number) < MIN_POLL_MS)).map(([path]) => path)
  out.poll = { value: fast.length, detail: `paths polled faster than ${MIN_POLL_MS}ms: ${fast.join(', ')}` }

  const status = (byPath.get('/status') ?? []).length
  out['status-rate'] = { value: status, detail: `${status} /status in 60s` }

  /* BY WHAT STARTED, NOT BY A GAP: an identical GET that starts while the same one is still open
     is a duplicate, in fake time. A read asked again after the first was answered is a chain, and
     how far apart a chain lands is the runner's stall, not the screen's. */
  const twice = new Set<string>()
  const lastOf = new Map<string, Logged>()
  for (const l of reads) {
    const before = lastOf.get(l.u)
    if (before !== undefined && (before.e === undefined || l.t < before.e)) twice.add(shape(l.u))
    lastOf.set(l.u, l)
  }
  out['same-get'] = { value: twice.size, detail: `paths asked again while the same read was still open: ${[...twice].join(', ')}` }

  const longest = Math.max(0, ...log.map((l) => l.u.length))
  out['url-size'] = { value: longest, detail: `longest URL ${longest} bytes` }

  if (route === '#/') {
    const unscoped = reads.filter((l) => /\/(pipeline\/)?pricing$/.test(new URL(l.u, 'http://x').pathname)).length
    out['home-pricing'] = { value: unscoped, detail: `${unscoped} unscoped pricing reads on mount` }
  }
  if (route === hash('review')) {
    const queues = reads.filter((l) => new URL(l.u, 'http://x').pathname === '/queues').length
    out['review-queues'] = { value: queues, detail: `${queues} /queues reads on mount` }
  }
  return out
}

/** One measurement against the limit and the allow file. Pushes what is wrong; marks the entry
 *  used. Over the limit with no entry, over its `max`, or under its `max` all fail. */
function judge(rule: Rule, route: string, got: Measure, bad: string[], used: Set<string>): void {
  const key = `${rule}:${route}`
  const limit = LIMIT[rule]
  const entry = EXCUSED[key]
  const exactlyOnce = rule === 'review-queues' && got.value === 0
  if (entry === undefined) {
    if (got.value > limit || exactlyOnce) bad.push(`${key}: ${got.detail}, limit ${limit}`)
    return
  }
  used.add(key)
  if (got.value > entry.max) bad.push(`${key}: ${got.detail}, allowed up to ${entry.max}`)
  else if (got.value < entry.max) bad.push(`${key}: stale exception, ${got.detail}. lower to ${got.value > limit ? got.value : `nothing: delete the entry (limit ${limit})`}`)
}

/** An entry for a rule in `rules` that nothing measured is stale. */
function unused(rules: readonly Rule[], used: Set<string>): string[] {
  return Object.keys(EXCUSED).filter((k) => rules.some((r) => k.startsWith(`${r}:`)) && !used.has(k)).map((k) => `${k}: stale exception, the rule now passes. delete the entry`)
}

function badAllowFile(): string[] {
  return Object.entries(EXCUSED)
    .filter(([, e]) => typeof e?.why !== 'string' || e.why.trim() === '' || !Number.isInteger(e.max) || e.max < 0)
    .map(([key]) => `${key}: needs { "max": <whole number>, "why": <what and how much> }`)
}

test('every screen stays inside its request budget for a minute', async ({ page }) => {
  test.setTimeout(900_000)
  expect(badAllowFile(), 'an exception with no max or no reason').toEqual([])
  const watch = await instrument(page)
  for (const seed of Object.values(POPULATED_ROUTE_SEEDS)) await seed(page)
  await setViewport(page, { width: 1440, height: 1000 })
  const routes = (await routesFromNav(page)).filter((r) => !EXCLUDED_FROM_SWEEP.test(r))
  routes.push(PRODUCT_ROUTE)

  const bad: string[] = []
  const used = new Set<string>()
  let polled = 0
  for (const route of routes) {
    await page.goto('about:blank')
    watch.reset()
    /* THE BURST IS COUNTED WITH EVERY ANSWER HELD: the gate stays shut until no new read has
       started for `STILL_FRAMES` frames, so what is open then is exactly what the mount asked
       for at once, and a chained read cannot slip in or out with the timing. */
    watch.close()
    await page.goto(`/${route}`)
    await stillFor(page, watch)
    const burst = watch.openCount()
    watch.release()
    await openSettled(page, route)
    await quiet(page, watch)
    const mountEnd = await pageNow(page)
    await runMinute(page, watch, mountEnd)
    const log = await pageLog(page)
    polled += log.filter((l) => l.t > mountEnd && shape(l.u) === '/status').length
    for (const [rule, got] of Object.entries(measure(route, log, mountEnd, burst)) as [Rule, Measure][]) judge(rule, route, got, bad, used)
  }
  expect(polled, 'the fake clock drove no /status poll: the spacing rules would pass over nothing').toBeGreaterThan(0)
  bad.push(...unused(SCREEN_RULES, used))
  expect(bad, 'screens off their request budget').toEqual([])
})

/* ---------------------------------------------------------------- reads after a write */

/** Presses `act` and counts the GETs the page starts from the write on, until nothing is open and
 *  nothing new starts. `/status` is the shell's own poll and is never a consequence of a write. */
async function readsAfter(page: Page, watch: Watch, isWrite: (s: Seen) => boolean, act: () => Promise<void>): Promise<string[]> {
  const from = watch.seen.length
  await act()
  await expect.poll(() => watch.seen.slice(from).some(isWrite), { message: 'the write never went out' }).toBe(true)
  await quiet(page, watch)
  const write = watch.seen.slice(from).find(isWrite)!
  return watch.seen.filter((s) => s.order > write.order && s.method === 'GET' && s.path !== '/status').map((s) => s.path)
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

function judgeBurst(rule: 'sale-reads' | 'answer-reads', route: string, reads: string[]): void {
  const bad: string[] = []
  const used = new Set<string>()
  judge(rule, route, { value: reads.length, detail: `${reads.length} reads after one write (${reads.join(' ')})` }, bad, used)
  expect(bad, 'reads after a write off budget').toEqual([])
  expect(unused([rule], used).filter((k) => k.startsWith(`${rule}:${route}`)), 'stale exception').toEqual([])
}

test('a sale re-reads no more than it must', async ({ page }) => {
  test.setTimeout(120_000)
  const watch = await instrument(page)
  await page.route(/\/inventory\/\d+\/\d+\/sold$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ box: 2, index: 1, position: '2/1', state: 'sold', previous_state: 'identified', sold_at: '2026-09-01T12:00:00+00:00' }) }),
  )
  await setViewport(page, { width: 1440, height: 1000 })
  await openSettled(page, hash('inventory'))
  await quiet(page, watch)
  const reads = await readsAfter(page, watch, (s) => s.method === 'POST' && /\/sold$/.test(s.path), async () => {
    await page.getByRole('button', { name: 'Mark sold' }).first().click()
  })
  judgeBurst('sale-reads', hash('inventory'), reads)
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
  await quiet(page, watch)
  const reads = await readsAfter(page, watch, (s) => s.method === 'POST' && /\/answer$/.test(s.path), async () => {
    await page.locator('.review-candidate').first().click()
  })
  judgeBurst('answer-reads', hash('review'), reads)
})

test('a write that changes pricing drops the kept price table, so the next ask reads it again', async ({ page }) => {
  /* `getPricing` keeps each run's table for five minutes. A pricing write (`putPricingCorpus`) changes the answers
     that table carries, so the ask after it must go to the server. Two asks with no write between share one read. */
  let reads = 0
  await page.route(/\/pipeline\/runs\/[^/]+\/pricing$/, (route) => {
    reads += 1
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ run: 'run-1', skus: [], rows: [] }) })
  })
  await page.route(/\/pricing$/, (route) => {
    if (route.request().method() !== 'PUT') return route.fallback()
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, written: 'x', answers: 0, revision: 'r2' }) })
  })
  await setViewport(page, { width: 1440, height: 1000 })
  await page.goto('/#/gallery')
  const ask = () =>
    page.evaluate(async () => {
      const mod = await import(('/src/server' + '.ts'))
      await mod.getPricing('run-1')
    })
  await ask()
  await ask()
  expect(reads, 'the second ask did not share the kept table').toBe(1)
  await page.evaluate(async () => {
    const mod = await import(('/src/server' + '.ts'))
    await mod.putPricingCorpus({ answers: {} })
  })
  await ask()
  expect(reads, 'a pricing write left the kept table in place').toBe(2)
})

/* ---------------------------------------------------------------- leaving a screen */

/** The shell's own reads, the ones every screen's mount makes. They outlive a screen on purpose. */
const SHELL = new Set(['GET /status'])

test('a screen that is left stops asking, and what it had open is aborted', async ({ page }) => {
  test.setTimeout(300_000)
  const watch = await instrument(page)
  watch.hold.ms = LEAVE_HOLD_MS
  for (const seed of Object.values(POPULATED_ROUTE_SEEDS)) await seed(page)
  await setViewport(page, { width: 1440, height: 1000 })
  const routes = (await routesFromNav(page)).filter((r) => !EXCLUDED_FROM_SWEEP.test(r))
  routes.push(PRODUCT_ROUTE)

  /* what each screen asks for on its own mount, cold */
  const mounts = new Map<string, Set<string>>()
  for (const route of routes) {
    await page.goto('about:blank')
    watch.reset()
    const from = watch.seen.length
    await page.goto(`/${route}`)
    await quiet(page, watch)
    mounts.set(route, new Set(watch.seen.slice(from).map(named)))
  }
  const first = mounts.get(routes[0]!)!
  const shell = new Set([...SHELL, ...[...first].filter((one) => routes.every((r) => mounts.get(r)!.has(one)))])

  /* The shell's reads outlive a screen on purpose, so the long hold never touches them. */
  watch.hold.except = (r) => r.method() !== 'GET' || shell.has(`${r.method()} ${shape(r.url())}`)
  const bad: string[] = []
  const used = new Set<string>()
  for (let at = 0; at + 1 < routes.length; at++) {
    const from = routes[at]!
    const to = routes[at + 1]!
    await page.goto('about:blank')
    watch.reset()
    const before = watch.seen.length
    watch.hold.ms = OPEN_UNTIL_LEFT_MS
    await page.goto(`/${from}`)
    const own = (s: Seen) => !s.done && s.failed === null && !shell.has(named(s)) && s.method === 'GET'
    /* a screen may ask nothing on arrival (`#/shipping`): the wait is for an open read OR for the
       screen to be quiet with none, whichever is first, so it never runs out a clock */
    await expect.poll(async () => {
      if (watch.seen.slice(before).some(own)) return true
      await page.evaluate(() => new Promise<void>((done) => requestAnimationFrame(() => requestAnimationFrame(() => done()))))
      return watch.seen.length > before && watch.openCount() === 0
    }, { message: `${from}: neither an open read nor a quiet page` }).toBe(true)
    const mark = watch.seen.length
    const open = watch.seen.slice(before).filter(own)
    watch.hold.ms = 0
    await page.evaluate((next) => { window.location.hash = next }, to.slice(1))
    await expect.poll(() => open.every((s) => s.done || s.failed !== null), { message: `${from}: reads neither finished nor failed`, timeout: 15_000 }).toBe(true)
    await quiet(page, watch)
    const kept = open.filter((s) => s.failed === null).map(named)
    const stale = [...new Set(watch.seen.slice(mark).map(named))].filter((one) => mounts.get(from)!.has(one) && !mounts.get(to)!.has(one) && !shell.has(one))
    const offenders = [...new Set([...kept, ...stale])]
    judge('leave', from, { value: offenders.length, detail: `${offenders.length} paths keep asking after leaving (${offenders.join(', ')})` }, bad, used)
  }
  bad.push(...unused(['leave'], used))
  expect(bad, 'screens that keep asking after they are left').toEqual([])
})
