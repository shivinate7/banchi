// Protects: The published static demo build draws real data, photographs and controls on every screen a reviewer grades it on.
// Governs: D183, D227, D271, D277, D298, D295, D301
/**
 * The published demo, as built: every screen a reviewer grades on it must draw its data.
 *
 * WHY THIS EXISTS. Every reviewer of the 2026-09 UX overhaul graded the product on the public
 * demo, and the demo could not show photographs (the recorder copied from a folder the seed
 * stopped writing when D183 moved them), undo, the order walk, the deleted boxes shelf, product history,
 * value bands, facet counts or a typed search. Each of those failed as a quiet refusal or a
 * broken image, so a reviewer could not tell a demo gap from a product defect. This spec reads
 * the BUILT artifact, `dist-demo/`, and fails when one of those screens goes back to refusing.
 *
 * WHAT IT RUNS AGAINST. The files `make demo-static` wrote, served on this checkout's own dev
 * origin under the demo's base path, exactly as a static host serves them (every request under
 * the base path is answered from `dist-demo/` and nothing reaches Vite). With
 * `DEMO_PREVIEW_URL` set — for example `http://localhost:4173` while `make demo-preview`
 * runs — each file is fetched from that preview server instead, so the same assertions read
 * what the preview serves. Either way the page itself talks to its own origin and to one named
 * outside host, `tcgplayer-cdn.tcgplayer.com` (see the allow-list below), and
 * `sealEveryTest` still refuses anything else.
 *
 * SKIPPED, BY NAME, WHEN THERE IS NO BUILD. `make design-check` does not build the demo, so a
 * tree without `dist-demo/` skips these cases with the reason rather than failing them.
 * Run `make demo-static` first. `DEMO_REQUIRED=1` turns the skip into a failure: that is how
 * `.github/workflows/demo.yml` runs it, after its own build and before it publishes.
 *
 * EVERY SCREEN IS REACHED THE WAY A VISITOR REACHES IT, WITH ONE NAMED EXCEPTION. The page opens
 * on the demo's root with no hash, and each case moves by the sidebar or by a control on the
 * screen. The one exception is `#/product`. D227 makes it a deep link reached by SKU, and no
 * screen or palette row links to it today, so the case opens the link a shared URL would carry.
 * No other route is typed. So the spec is not a roster of routes (`make docs-audit`'s
 * `route rosters` row), and it proves the hash router works under the demo's base path, which
 * only a published build can get wrong.
 */
import { test, expect, type Page } from '@playwright/test'
import { createReadStream, existsSync, readFileSync, statSync } from 'node:fs'
import { createServer, type Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import { dirname, extname, join, normalize } from 'node:path'
import { fileURLToPath } from 'node:url'
import { CAPTURE_PORT, DEV_PORT } from '../devPort'
import { isOutside, sealEveryTest } from './shell'
import { afterPaint, settleMotion } from './motionSettled'

const HERE = dirname(fileURLToPath(import.meta.url))
const DIST = join(HERE, '..', '..', 'dist-demo')
const BUNDLE = join(HERE, '..', 'demo', 'bundle.json')
const BUILT = existsSync(join(DIST, 'index.html'))
const PREVIEW = process.env.DEMO_PREVIEW_URL?.replace(/\/$/, '') ?? null
const REQUIRED = process.env.DEMO_REQUIRED === '1'

/** The base path the build was made for (`DEMO_BASE`), read off its own index.html. */
function basePath(): string {
  const html = readFileSync(join(DIST, 'index.html'), 'utf-8')
  const found = /(?:src|href)="(\/[^"]*?)assets\//.exec(html)
  return found?.[1] ?? '/'
}

const REFUSAL = 'Not in this demo.'

// THE NAMED STOCK-IMAGE HOSTS, NEVER A STUB (closed). A second host, `images.pokemontcg.io`, joined
// when the mirror refresh gave Sales rows Pokemon stock photographs: the same hotlink design. `pipeline/stockimages.py` (D301)
// hotlinks Riftbound and One Piece stock images straight from `tcgplayer-cdn.tcgplayer.com` —
// that is the design, not a leak, and the published page really does load them. A one-pixel
// stub used to answer in its place, which tested a rule the shipped page does not follow: the
// owner's own words, "isn't that a scenario of revising the test like the test is the wrong
// test to keep now?" So this file names the one host it is allowed to actually reach —
// `sealOutside`'s own `allowOutside` option (shell.ts), never a widened default there, which
// would weaken the seal for every OTHER spec that imports it — and lets the real request land.
// `the seal still refuses a host not on the allow list` below proves every other outside host
// is refused exactly as before (example.com stays the probe).
// The one loopback `host:port` of this file's own HTTP server over dist-demo (or the DEMO_PREVIEW_URL host)
// joins this list in `beforeAll`, which runs before the seal reads it. Other ports on loopback stay refused.
const ALLOWED: string[] = ['tcgplayer-cdn.tcgplayer.com', 'images.pokemontcg.io']
sealEveryTest({ allowOutside: ALLOWED })

test.skip(!BUILT && !REQUIRED, 'no dist-demo/ in this checkout: run `make demo-static` first')

test('the demo was built', () => {
  expect(BUILT, 'DEMO_REQUIRED=1 and there is no dist-demo/index.html').toBe(true)
})

// A UNIT TEST OF THE PREDICATE, NOT A LIVE FETCH — the reason is `sealOutside`'s own
// mechanism: it both ABORTS and RECORDS an outside request, and this file's own `afterEach`
// (`sealEveryTest`, shell.ts) fails any test that leaves a recorded escape behind, on purpose.
// So a case that deliberately drove a second host through the real page would trip that
// blanket assertion regardless of what it itself expected, which is the wrong test to write
// against a guard built to fail loudly. `isOutside` is the whole rule the seal applies; reading
// it directly proves the allow-list names exactly one host and nothing wider.
test('the seal still refuses a host that is not on the allow list', () => {
  const allowed = new URL('https://tcgplayer-cdn.tcgplayer.com/product/684215_200w.jpg')
  const other = new URL('https://example.com/anything')
  expect(isOutside(allowed, ['tcgplayer-cdn.tcgplayer.com'])).toBe(false)
  expect(isOutside(other, ['tcgplayer-cdn.tcgplayer.com'])).toBe(true)
})

test('the seal refuses a loopback port that is not the demo server', () => {
  const own = new URL(serverOrigin || 'http://127.0.0.1:4999')
  const list = [...ALLOWED, own.host]
  expect(isOutside(new URL(`${own.origin}/x`), list)).toBe(false)
  expect(isOutside(new URL('http://127.0.0.1:9999/x'), list)).toBe(true)
  expect(isOutside(new URL(`http://localhost:${Math.max(DEV_PORT, CAPTURE_PORT) + 1}/x`), list)).toBe(true)
})

const TYPES: Record<string, string> = {
  '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.webp': 'image/webp', '.webmanifest': 'application/manifest+json', '.woff2': 'font/woff2', '.wasm': 'application/wasm', '.ico': 'image/x-icon',
}

/** One real loopback HTTP server over `dist-demo`, shared by this worker's tests. A body goes over a
 *  socket and never through Playwright's `route.fulfill`: that base64-encodes the whole body into one
 *  DevTools pipe message, which headless Chromium caps at 100 MiB, and the 86 MB `demoServer` chunk is
 *  about 115 MB encoded, so the browser connection dies. Any window the demo opens is served too. */
let server: Server | null = null
let serverOrigin = ''
async function listen(): Promise<string> {
  if (server !== null) return serverOrigin
  const base = basePath()
  const made = createServer(async (req, res) => {
    let pathname: string
    try {
      pathname = decodeURIComponent(new URL(req.url ?? '/', 'http://x').pathname)
    } catch {
      return void res.writeHead(400).end()
    }
    let file = normalize(join(DIST, pathname.slice(base.length)))
    if (!pathname.startsWith(base) || !file.startsWith(DIST)) return void res.writeHead(403).end()
    if (existsSync(file) && statSync(file).isDirectory()) file = join(file, 'index.html')
    if (!existsSync(file)) return void res.writeHead(404).end()
    // DEMO_CHUNK_DELAY_MS=<ms> holds back the 75 MB `demoServer` chunk the way a cold host or a loaded
    // runner does (run 36807030451). Deterministic where a CPU throttle is not: the first photograph
    // of every screen is requested only after that chunk has arrived and parsed.
    if (/\/demoServer-[^/]*\.js$/.test(pathname) && process.env.DEMO_CHUNK_DELAY_MS)
      await new Promise((done) => setTimeout(done, Number(process.env.DEMO_CHUNK_DELAY_MS))) // keep: chunk delay from DEMO_CHUNK_DELAY_MS, a latency fixture on purpose
    res.writeHead(200, { 'Content-Type': TYPES[extname(file)] ?? 'application/octet-stream' })
    createReadStream(file).on('error', () => res.destroy()).pipe(res)
  })
  await new Promise<void>((done) => made.listen(0, '127.0.0.1', done))
  server = made
  serverOrigin = `http://127.0.0.1:${(made.address() as AddressInfo).port}`
  return serverOrigin
}
test.beforeAll(async () => {
  ALLOWED.push(PREVIEW !== null ? new URL(PREVIEW).host : new URL(await listen()).host)
})
test.afterAll(async () => {
  const stop = server
  server = null
  if (stop !== null) await new Promise((done) => stop.close(done))
})

/** The URL the demo opens at: `DEMO_PREVIEW_URL` as given, else this worker's own HTTP server. */
async function serveDemo(_page: Page): Promise<string> {
  return `${PREVIEW ?? (await listen())}${basePath()}`
}

/** Budget for anything that waits on the public demo's ~75 MB `demoServer` chunk to arrive and evaluate
 *  (about 15 s on the CI runner, so the 15 s expect default flakes). See DEBT84. */
const DEMO_CHUNK_BUDGET_MS = 30_000

/** The demo's reads have landed and drawn: the screen holds content, no skeleton or busy mark stands,
 *  nothing still moves. Content first, so a skeleton that has not mounted yet cannot pass. */
async function drawn(page: Page): Promise<void> {
  await page.waitForFunction(() => (document.querySelector('main')?.innerText.trim().length ?? 0) > 20)
  await expect(page.locator('.bn-skeleton, [aria-busy="true"]')).toHaveCount(0, { timeout: DEMO_CHUNK_BUDGET_MS })
  await settleMotion(page)
  await afterPaint(page)
}

/** The demo's own root, no hash typed, and its first read landed. */
async function openRoot(page: Page): Promise<void> {
  const origin = await serveDemo(page)
  await page.goto(origin)
  await page.locator('main').first().waitFor()
  // The demo answers every read after a 45-135 ms pause, on purpose (`demoRequest`).
  await drawn(page)
}

/** A deep link, opened the way a shared URL opens it. Only `#/product` uses this (D227). */
async function openLink(page: Page, link: string): Promise<void> {
  const origin = await serveDemo(page)
  await page.goto(`${origin}${link}`)
  await page.locator('main').first().waitFor()
  await drawn(page)
}

/** Arrive at a screen the way a visitor does: land on the root, press its row in the sidebar.
 *  `Home` is the root itself. */
async function visit(page: Page, screen: string): Promise<void> {
  await openRoot(page)
  if (screen === 'Home') return
  await page.locator('.bn-side').getByRole('link', { name: new RegExp(`^${screen}`) }).first().click()
  await page.locator('main').first().waitFor()
  await drawn(page)
}

/** The Fulfiller's screen: its sidebar row opens it in a new window, as it does at the desk. */
async function visitFulfiller(page: Page): Promise<Page> {
  await openRoot(page)
  const [fulfiller] = await Promise.all([
    page.waitForEvent('popup'),
    page.locator('.bn-side').getByRole('link', { name: 'Pull' }).first().click(),
  ])
  await fulfiller.locator('main, body').first().waitFor()
  await drawn(fulfiller)
  return fulfiller
}

/** Every demo photograph the page asked for, with the status it got. */
function watchPhotos(page: Page): Array<{ url: string; status: number }> {
  const seen: Array<{ url: string; status: number }> = []
  page.on('response', (response) => {
    if (response.url().includes('/demo/photos/')) seen.push({ url: response.url(), status: response.status() })
  })
  return seen
}

test.describe('the published demo draws what reviewers grade', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  // EVIDENCE, TO THE JOB LOG, NEVER TO AN ARTIFACT (2026-09-27, after two rounds of
  // guessing at CI runs 36314954311/36316345981/36317770339 with no downloadable trace —
  // `demo.yml` uploads `test-results/` now too, but this reads without needing the
  // download). Console/pageerror capture starts here, scoped to the one test this was
  // written for, because `request()` (`server.ts`) calls `demoServer` directly rather than
  // over a real fetch — there is no network response to read, so a console error or a
  // thrown exception is the nearest thing to one.
  const ordersConsole: string[] = []
  test.beforeEach(async ({ page }, testInfo) => {
    if (testInfo.title !== 'Orders draws a walk') return
    ordersConsole.length = 0
    page.on('console', (m) => ordersConsole.push(`[console.${m.type()}] ${m.text()}`))
    page.on('pageerror', (e) => ordersConsole.push(`[pageerror] ${e.message}`))
  })

  // Fires only on a case that did not pass, and only for the one case this was written
  // for — a page dump on every OTHER case's failure would be noise nobody asked for.
  // Prints the Orders page's own visible text (trimmed), whether "Walk all" exists and
  // its exact label, and whether the demo's one refusal notice is on screen.
  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status === 'passed') return
    if (testInfo.title !== 'Orders draws a walk') return
    const walkAll = page.getByRole('button', { name: /^Walk \d+$/ })
    const walkAllCount = await walkAll.count().catch(() => -1)
    const walkAllLabel =
      walkAllCount > 0
        ? await walkAll.first().textContent({ timeout: 3_000 }).catch(() => null)
        : null
    const refusalCount = await page.getByText(REFUSAL).count().catch(() => -1)
    // AN EXPLICIT, SHORT TIMEOUT ON EVERY ACTION HERE, NOT JUST `.catch()` — an action
    // wait with no timeout of its own hangs until the ENCLOSING test timeout kills it
    // (measured while proving this hook: a missing `main` consumed the whole 60s budget
    // and printed "Test timeout ... exceeded while running afterEach hook" instead of any
    // evidence at all). `.catch()` alone does nothing for a promise that never rejects.
    const bodyText = await page
      .locator('main')
      .first()
      .innerText({ timeout: 3_000 })
      .catch((exc) => `<could not read main: ${String(exc).slice(0, 200)}>`)
    console.log('=== Orders draws a walk: failure evidence ===')
    console.log('"Walk N" button count:', walkAllCount)
    console.log('"Walk N" button label:', walkAllLabel)
    console.log(`"${REFUSAL}" count:`, refusalCount)
    console.log('console/pageerror during this test:', ordersConsole.length === 0 ? '<none>' : '')
    for (const line of ordersConsole) console.log(' ', line)
    console.log('main innerText (first 4000 chars):')
    console.log(bodyText.slice(0, 4000))
    console.log('=== end evidence ===')
  })

  test('every card in the recorded store has its photograph in the build', () => {
    const bundle = JSON.parse(readFileSync(BUNDLE, 'utf-8')) as {
      responses: Record<string, { body: { cards?: Record<string, { box: number; index: number; photo?: string | null }> } }>
    }
    const cards = Object.values(bundle.responses['/inventory']?.body.cards ?? {})
    const withPhoto = cards.filter((card) => typeof card.photo === 'string' && card.photo !== '')
    expect(withPhoto.length, 'the recorded store holds no card with a photograph').toBeGreaterThan(0)
    const missing = withPhoto
      .filter((card) => !existsSync(join(DIST, 'demo', 'photos', String(card.box), `${card.index}.jpg`)))
      .map((card) => `${card.box}/${card.index}`)
    expect(missing, 'cards whose photograph the build does not carry').toEqual([])
  })

  test('every SKU an order line names has its Sales photo lookup recorded', () => {
    const bundle = JSON.parse(readFileSync(BUNDLE, 'utf-8')) as { responses: Record<string, unknown> }
    const keys = Object.keys(bundle.responses)
    const asked = keys.filter((key) => key.startsWith('/pipeline/price-now?sku='))
    const missing = asked.filter((key) => !(`/skus/photos?sku=${key.slice('/pipeline/price-now?sku='.length)}` in bundle.responses))
    expect(asked.length, 'the recording holds no price-now reading').toBeGreaterThan(0)
    expect(missing, 'SKUs whose /skus/photos answer the bundle lacks; re-run make demo-mirror').toEqual([])
  })

  for (const screen of ['Inventory', 'Review', 'Pricing', 'Home', 'Cards to pull'] as const) {
    test(`${screen} draws its photographs, and every one answers 200`, async ({ page }) => {
      test.setTimeout(60_000)
      let photos = watchPhotos(page)
      if (screen === 'Cards to pull') {
        // LISTEN ON THE CONTEXT BEFORE THE WINDOW OPENS, NEVER AFTER. This used to attach to the
        // popup once it had loaded and then `reload()` it to see its photographs again, which
        // loaded the 75 MB `demoServer` chunk a second time and started the poll's clock before
        // that chunk had even arrived. On a loaded runner the second load alone outlasted the poll
        // (run 36807030451). A context listener sees the popup's first request, so nothing reloads.
        photos = []
        const opener = page
        page.context().on('response', (response) => {
          if (response.url().includes('/demo/photos/') && response.frame()?.page() !== opener)
            photos.push({ url: response.url(), status: response.status() })
        })
        page = await visitFulfiller(page)
      } else await visit(page, screen)
      // REAL, NOT STALE (2026-09-27, D295 full mirror): the owner's real review queue has
      // zero cards still owed an answer right now (every open entry's card has since
      // sold or retired) — measured against a fresh `.backup` of the store, not guessed.
      // A mirror is a snapshot, and this is what the snapshot genuinely holds; nothing here
      // fabricates a queue entry to make the screen busier than the real store is today.
      if (screen === 'Review') {
        // `/Card \d+ of \d+/` matched no text `ReviewQueue.tsx` has ever drawn — the
        // progress line reads "Nothing is waiting." when the queue is empty and
        // "Progress <N> of <M>" otherwise (UX-256). Invisible until this branch's own
        // re-snapshot put a real, non-empty queue in the recording for the first time.
        const empty = page.getByText('Nothing is waiting.')
        await expect(empty.or(page.getByText(/Progress \d+ of \d+/))).toBeVisible()
        if ((await empty.count()) > 0) {
          await expect(page.getByText(REFUSAL)).toHaveCount(0)
          return
        }
      }
      // THE FIRST PHOTOGRAPH WAITS ON THE 75 MB `demoServer` CHUNK, so the budget is the chunk's, not the
      // default 15 s: 3 s unthrottled, and the case passes with the chunk held back 13 s (DEMO_CHUNK_DELAY_MS).
      await expect.poll(() => photos.length, { message: `${screen} asked for no photograph`, timeout: DEMO_CHUNK_BUDGET_MS }).toBeGreaterThan(0)
      expect(photos.filter((photo) => photo.status !== 200)).toEqual([])
      const broken = await page.evaluate(
        () => [...document.images].filter((img) => img.src.includes('/demo/photos/') && img.complete && img.naturalWidth === 0).length,
      )
      expect(broken, 'a photograph the page drew as broken').toBe(0)
    })
  }

  test('Capture draws its recent strip once a box is picked, and every photograph answers 200', async ({ page }) => {
    // STALE, REWRITTEN 2026-09-27 (D295, full mirror): "Pick a box" / "RB Origins" pinned
    // the 60-card sample's own box picker shape and box name. The box Row (`.capture-box-slot
    // button`, `CaptureScreen.tsx`) opens a search-and-pick field over `.capture-opts`
    // buttons — behavior unchanged, just read the first offered box instead of a name.
    const photos = watchPhotos(page)
    await visit(page, 'Capture')
    await page.locator('.capture-box-slot button').first().click()
    await page.locator('.capture-opts button').first().click()
    await expect.poll(() => photos.length, { message: 'Capture asked for no photograph' }).toBeGreaterThan(0)
    expect(photos.filter((photo) => photo.status !== 200)).toEqual([])
  })

  test('Inventory: Mark sold, then Undo, puts the card and the box counts back', async ({ page }) => {
    // STALE, REWRITTEN 2026-09-27 (D295, full mirror): this pinned "RB Origins" and
    // "34 on hand", a fact of the 60-card SAMPLE. The full mirror's own boxes carry
    // different names and counts (measured: WB1 R4, WB1 R2, WB1 R1, ME01 C/UC, WB1 R3),
    // so the box and its starting count are read off the screen instead of hardcoded —
    // same behavior asserted (Mark sold decrements by one, Undo restores it), against
    // whichever box and count the mirror actually holds.
    // COPY RENAMED (F5 verbiage cut, ff1b3f71 and after): a box row reads "N stored", the
    // Fulfiller's search placeholder is "Card name or number", and Sales' shelf line is
    // "N of M priced, K not yet". Same behaviour asserted, new words.
    await visit(page, 'Inventory')
    const box = page.locator('button', { hasText: /\d+ stored/ }).first()
    await expect(box).toBeVisible()
    const before = await box.textContent()
    const match = /(\d+)\s*stored/.exec(before ?? '')
    expect(match, 'a box button carries an "N stored" count').not.toBeNull()
    const startCount = Number(match![1])
    await page.getByRole('button', { name: 'Mark sold' }).first().click()
    await expect(box).toContainText(`${startCount - 1} stored`)
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
    await page.getByRole('button', { name: /^Undo/ }).first().click()
    await expect(box).toContainText(`${startCount} stored`)
    await expect(page.getByRole('button', { name: 'Mark sold' }).first()).toBeVisible()
  })

  test('Inventory: a Game pick draws a count on every box', async ({ page }) => {
    await visit(page, 'Inventory')
    // The rail's FilterBar: the Filters press opens a popover, and Game is its first facet.
    await page.locator('.browse-filterbar .bn-filterbar-trigger:visible').click()
    await page.locator('.bn-filterbar-popover .bn-pick', { hasText: /^Game/ }).click()
    await page.locator('.bn-pick-opt').nth(1).click()
    await page.keyboard.press('Escape')
    const rows = page.locator('button:has-text("match")')
    await expect(rows.first()).toBeVisible()
    // Same DEBT23 shape as the walk's own count below: the first row being visible does not
    // mean every row has rendered, so poll the count rather than reading it once.
    await expect.poll(() => rows.count()).toBeGreaterThanOrEqual(4)
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
  })

  test('Inventory: a typed search finds a card the recorder never searched for', async ({ page }) => {
    // STALE LOCATOR, REWRITTEN 2026-09-27 (D271, one forgiving search matcher): the box
    // picker's own "Card name" field was folded into the rail's unified `role="searchbox"`
    // control ("Search cards"). "Crowd Favorite" is still a real card name in the full
    // mirror (unchanged) — only the field it is typed into moved.
    await visit(page, 'Inventory')
    await page.getByRole('searchbox').first().pressSequentially('Crowd Favorite', { delay: 40 })
    // A matched card is a row BUTTON (its name inside, alongside set/condition/copies), not
    // a heading — confirmed against the rebuilt bundle's own accessibility tree.
    await expect(page.getByRole('button', { name: /Crowd Favorite/ }).first()).toBeVisible()
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
  })

  test('Cards to pull: search finds a card', async ({ page }) => {
    page = await visitFulfiller(page)
    await page.getByPlaceholder('Card name or number').pressSequentially('Crowd', { delay: 40 })
    await expect(page.getByText('Crowd Favorite').first()).toBeVisible()
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
  })

  test('Orders draws a walk', async ({ page }) => {
    // STALE, REWRITTEN 2026-09-27 (D295 full mirror, plus an unrelated aria-label rename):
    // no order is ticked by default, and nothing named "cards this walk covers" exists any
    // more — `OrdersWalkPane.tsx:WalkList`'s list is now "The cards to pick, in the order
    // the boxes are walked". Press "Walk N" first (the demo-mirror-data-build
    // lane's walk-plan fix records exactly this "walk all" set), then read the current list.
    //
    // THE PRIOR FIX (CI run 36314954311) RAISED THE WRONG TIMEOUT. Pressing "Walk all"
    // over this mirror's full 71 open orders (70 buyers) runs `useOrderWalk`'s solve
    // client-side, over every one of them plus the whole inventory already in memory —
    // a real cost, confirmed by reproducing the click with console/pageerror logging: no
    // error, the walk pane renders correctly, just slower than a toggle. Raising only the
    // assertion's own wait (to 45s) did nothing, because Playwright's own PER-TEST timeout
    // (30s, this file's config sets none of its own) killed the whole test first — CI run
    // 36316345981's own error names it: "Test timeout of 30000ms exceeded." `test.setTimeout`
    // is the knob that actually needed raising.
    test.setTimeout(60_000)
    await visit(page, 'Orders')
    await page.getByRole('button', { name: /^Walk \d+$/ }).first().click()
    const walk = page.getByRole('list', { name: /cards to pick/i })
    await expect(walk).toBeVisible({ timeout: 30_000 })
    // DEBT23's shape: the list container appearing does not mean its rows have. A bare
    // count() right after does not retry, so it can read zero while the rows are still
    // filling in. Wait for a row itself, web-first, before counting.
    const walkRows = walk.getByRole('button')
    await expect(walkRows.first()).toBeVisible()
    // THE LIST APPEARS BEFORE THE PRESS DOES ANYTHING (the selected buyer's own walk is
    // already drawn), so "a row exists" passed on that list and raced the walk-all plan the
    // press asks for (main's demo run 36599655970 caught the race under CI load). The
    // walk-all plan is many rows and the single buyer's is a few: wait for the many. A plan
    // the recording lacks replaces the list with a notice, and this then fails, on any speed.
    await expect.poll(() => walkRows.count(), { message: 'the walk-all plan never replaced the single-buyer list' }).toBeGreaterThan(20)
    await expect(page.getByText('Could not read where the copies are')).toHaveCount(0)
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
  })

  test('Review: an answer, then Undo, puts the question back', async ({ page }) => {
    await visit(page, 'Review')
    // REAL, NOT STALE (2026-09-27, D295 full mirror). Whether the owner's store owes an
    // answer right now is a fact about today, so this reads the queue's own progress line
    // ("Nothing is waiting." when empty, "Progress <N> of <M>" otherwise, UX-256 — never
    // `/Card \d+ of \d+/`, which no version of ReviewQueue.tsx has drawn) rather than
    // asserting either shape by name. Answer-then-undo runs only when a card is queued;
    // an empty queue asserts the honest empty state instead of fabricating a card.
    const label = page.getByText(/Progress \d+ of \d+/)
    const empty = page.getByText('Nothing is waiting.')
    await expect(label.or(empty)).toBeVisible()
    if ((await empty.count()) > 0) {
      await expect(page.getByText(REFUSAL)).toHaveCount(0)
      return
    }
    const before = await label.textContent()
    await page.locator('button:has-text("Near Mint Foil")').first().click()
    await expect(page.getByText(/Answered as/).first()).toBeVisible()
    await page.getByRole('button', { name: /^Undo/ }).first().click()
    await expect(page.getByText(before ?? '')).toBeVisible()
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
  })

  test('Inventory: the Deleted boxes shelf lists the records of deleted boxes', async ({ page }) => {
    await visit(page, 'Inventory')
    await page.getByRole('button', { name: 'Records from deleted boxes' }).click()
    await expect(page.getByRole('list', { name: 'Records from deleted boxes' }).locator('.browse-row').first()).toBeVisible()
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
  })

  test('Product history draws the one real reading the demo carries', async ({ page }) => {
    // The one typed link in this file: see the header for why.
    await openLink(page, '#/product?sku=9189317')
    await expect(page.getByRole('heading', { name: 'Vilemaw' })).toBeVisible()
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
  })

  test('Inventory: the value sort draws its cards', async ({ page }) => {
    // The value sort re-ranks the boxes in the rail and draws each box's value figure as its
    // meta (D277: the value list is an Inventory sort). Card rows are not its claim: sections
    // land collapsed, so no row is on screen until one opens.
    await visit(page, 'Inventory')
    await page.locator('.browse-filterbar .bn-filterbar-trigger:visible').click()
    await page.locator('.bn-filterbar-popover .bn-pick', { hasText: /^Sort/ }).click()
    await page.locator('.bn-pick-opt', { hasText: 'Value' }).click()
    await page.keyboard.press('Escape')
    await expect(page.locator('.browse-boxcell-meta', { hasText: /\$\d/ }).first()).toBeVisible()
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
  })

  test('Sales: "Priced for" draws a figure', async ({ page }) => {
    // STALE, REWRITTEN 2026-09-27 (D298: "a line with no price gets its price from
    // TCGplayer" — pricing the shelf became automatic, and the "Value my stock" button that
    // used to trigger it is gone). Same behavior: the figure draws once holdings load, with
    // no press needed.
    await visit(page, 'Sales')
    await expect(page.getByText(/\d+ of \d+ priced/)).toBeVisible()
    await expect(page.getByText(REFUSAL)).toHaveCount(0)
  })
})
