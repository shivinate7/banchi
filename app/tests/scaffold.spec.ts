import { test, expect, type Page } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { routesFromNav } from './routes'
import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'

/* EVERY SCREEN INHERITS THE PAGE SCAFFOLD, ASSERTED IN A BROWSER (D275).
 *
 * The owner, 2026-09-23: "say a new page in the sidebar gets built tomorrow, it should be able
 * to autocall/inherit the properties of the other pages". `scripts/kit-adoption.mjs` proves the
 * source renders `<Page>`. This file proves what the browser drew, per route in `ROUTES`, at the
 * four widths the overhaul verifies (1440, 820, 720, 390):
 *
 *   page     exactly one `[data-bn-page]`
 *   h1       exactly one visible h1, and its text is the route's `title ?? label`
 *   width    the page's max-width is `--bn-page-w`
 *   top      the h1 sits `--bn-page-top` below the page's top
 *   scroll   nothing scrolls sideways
 *   title    `document.title` is one FIXED title, "番地 " and the screen name in lowercase
 *            ("番地 pricing", "番地 home"). No alternation, no "— Banchi". The owner's ruling,
 *            2026-09-23. READ OVER TIME AND UNDER BOTH MOTION SETTINGS, never once: with normal
 *            motion the shell used to alternate the title on a timer, and with reduced motion it
 *            showed a second, joined form, so a single read under `reducedMotion: 'reduce'`
 *            never saw the alternation at all. On a fake clock (`page.clock`), the title is read
 *            every TITLE_STEP ms for TITLE_WINDOW ms, well past App.tsx's TITLE_DWELL
 *            (6000 + 4000), once per motion setting. Every read must be the one fixed title. The
 *            window is this file's own number, never read from App.tsx: a test that reads the
 *            value it checks passes when that value is wrong (brand.spec.ts says the same).
 *   palette  the palette ("Go to", D276) lists the route in its Screens group
 *   keys     the keyboard sheet, every screen shown, has an entry that names the route
 *
 * THE ROUTES ARE READ FROM `ROUTES` ITSELF, by the same reader the static check uses
 * (`kit-adoption.mjs --routes`), so a route added tomorrow is swept with no edit here and the
 * spec and the check cannot disagree about which routes exist. `routesFromNav` is called too,
 * as a cross-check: the table and the nav must name the same routes.
 *
 * EXCEPTIONS ARE THE SAME SHRINKING OFFENDER LIST THE STATIC CHECK READS:
 * `scripts/kit-adoption-allow.json`'s `runtime` block, route path -> assertion -> lane. A
 * failure it does not list is red. An entry whose assertion now passes at every width is red
 * too (stale), so the list only shrinks. `palette`, `keys` and `title` are the shell lane's to
 * build, and their entries name lane `shell`: the list shrinks when the shell lands. Nothing
 * here is skipped.
 *
 * ONE NAMED EXEMPTION, AND IT IS NOT AN ALLOW-LIST ENTRY: `EXEMPT` below. An allow entry is a
 * debt a lane owes and must pay. An exemption is a ruling that the assertion does not apply,
 * with its reason beside it. The allow list may not name an exempt assertion.
 *
 * WRITES NOTHING. Run by `make design-check`. */

sealEveryTest({ store: true, cards: 40 })

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..', '..')

type RouteRow = {
  readonly path: string
  readonly label: string
  readonly title: string | null
  readonly persona: string | null
  readonly redirect: boolean
  readonly view: string
  readonly file: string
}

const ROUTE_TABLE: readonly RouteRow[] = JSON.parse(
  execFileSync(process.execPath, [resolve(ROOT, 'scripts/kit-adoption.mjs'), '--routes'], { encoding: 'utf8' }),
) as RouteRow[]

type Allow = Record<string, Record<string, string>>
const ALLOW: Allow =
  (JSON.parse(readFileSync(resolve(ROOT, 'scripts/kit-adoption-allow.json'), 'utf8')) as { runtime?: Allow }).runtime ?? {}

const PER_ROUTE = ['page', 'h1', 'width', 'top', 'scroll', 'title'] as const
const SHELL_WIDE = ['palette', 'keys'] as const
const ASSERTIONS: readonly string[] = [...PER_ROUTE, ...SHELL_WIDE]

const WIDTHS: readonly (readonly [number, number])[] = [
  [1440, 900],
  [820, 1180],
  [720, 900],
  [390, 844],
]

const titleOf = (route: RouteRow): string => route.title ?? route.label
/** The owner's ruling, 2026-09-23: one fixed tab title, "番地 " and the screen name in lowercase.
 *  Home's reads "番地 home" (the orchestrator's call, 2026-09-23). */
const tabTitleOf = (route: RouteRow): string => `番地 ${titleOf(route).toLowerCase()}`

/** How often, and for how long, the tab title is read on the fake clock. 30s covers the old
 *  6s + 4s alternation three times over. */
const TITLE_STEP = 500
const TITLE_WINDOW = 30_000

/** The width assertion's verdict on one measurement: null when it holds. A `max-width` that is
 *  not a finite length (`none`, or no page at all) FAILS: `parseFloat('none')` is NaN, and every
 *  comparison with NaN is false, so a `> 0.5` test would have passed it. */
function widthFailure(maxWidth: string | null, pageW: number): string | null {
  const px = maxWidth === null ? Number.NaN : parseFloat(maxWidth)
  if (!Number.isFinite(px)) return `max-width ${maxWidth === null ? 'absent (no single page)' : `"${maxWidth}"`}, want ${pageW}px`
  if (Math.abs(px - pageW) > 0.5) return `max-width ${px}px, want ${pageW}px`
  return null
}

/** The title assertion's verdict on every read over the window: null when each read is `want`. */
function titleFailure(reads: readonly string[], want: string): string | null {
  const distinct = [...new Set(reads)]
  if (reads.length === 0) return 'the title was never read'
  if (distinct.length === 1 && distinct[0] === want) return null
  return `read ${JSON.stringify(distinct)} over ${TITLE_WINDOW / 1000}s, want only "${want}"`
}

/** Every value `document.title` takes over TITLE_WINDOW, on the page's fake clock. */
async function readTitles(page: Page): Promise<string[]> {
  const reads: string[] = []
  for (let t = 0; t <= TITLE_WINDOW; t += TITLE_STEP) {
    reads.push(await page.title())
    await page.clock.runFor(TITLE_STEP)
  }
  return reads
}

/* THE NAMED EXEMPTIONS: an assertion a persona is NOT held to, with the ruling that says so.
 * Never a debt, so never on the allow list, and the allow list may not name one. */
const EXEMPT: Readonly<Record<string, Readonly<Record<string, string>>>> = {
  fulfiller: {
    width: 'D5 (two personas) and docs/DESIGN.md\'s Fulfillment floors: the Fulfiller\'s screen has no shell and sizes its own column.',
    top: 'D5 and docs/DESIGN.md\'s Fulfillment floors: no shell, so no shared top gap to sit under.',
    title: 'D5: the Fulfiller\'s tab names the task and carries no brand.',
  },
}

/* A REDIRECT ROUTE (D-runs-folds-into-review's `#/runs`) renders nothing of its own — it sends
 * the browser straight to another route's screen. `h1` and `title` name what THAT screen drew,
 * not this row's `label`, so holding a redirect to its own label is asking it to fail forever on
 * a fact it was never going to make true. `page`/`width`/`top`/`scroll` still apply: they are
 * measuring the screen the browser actually lands on. */
const REDIRECT_EXEMPT = new Set(['h1', 'title'])

/** Is this route held to this assertion at all? `false` for a named exemption or a redirect. */
const applies = (route: RouteRow, assertion: string): boolean =>
  (route.persona === null || EXEMPT[route.persona]?.[assertion] === undefined) &&
  !(route.redirect && REDIRECT_EXEMPT.has(assertion))

/** Compare what failed against what the list excuses. Returns every disagreement, both ways. */
function reconcile(route: RouteRow, failures: ReadonlyMap<string, readonly string[]>, measured: readonly string[]): string[] {
  const listed = ALLOW[route.path] ?? {}
  const problems: string[] = []
  for (const assertion of measured) {
    const where = failures.get(assertion) ?? []
    const lane = listed[assertion]
    if (where.length > 0 && lane === undefined) {
      problems.push(`${route.path} ${assertion}: ${where.join('; ')}. Not on the allow list: fix the screen, render <Page> from ./kit.`)
    }
    if (where.length === 0 && lane !== undefined) {
      problems.push(`${route.path} ${assertion}: passes at every width, so the allow entry (lane ${lane}) is stale. Delete it.`)
    }
  }
  return problems
}

async function settle(page: Page): Promise<void> {
  await settleFonts(page)
  await expect(page.locator('main').first(), 'the route drew no <main>').toBeVisible()
  /* A screen still loading has not drawn its frame yet. `Page` marks its body `aria-busy`
     while it loads; wait for that to clear, but never fail on it: a screen that never clears
     it is measured as it stands.
     THE ROUTE'S OWN PAGE BODY, NOT ANY `aria-busy` ON THE SCREEN. `#/gallery` draws the kit's
     loading and busy specimens, and they are busy forever on purpose. A document-wide query
     waited the full 5s at every width there: 20s of a 30s test, measured under a 4x CPU
     throttle, and a timeout on the slower CI runner. */
  await page
    .waitForFunction(
      () => document.querySelector('main[data-bn-page]')?.querySelector(':scope > .bn-page-body[aria-busy="true"]') == null,
      null,
      { timeout: 5000 },
    )
    .catch(() => undefined)
}

test('the route table is read, and it names the same routes the nav does', async ({ page }) => {
  expect(ROUTE_TABLE.length, 'kit-adoption --routes returned almost nothing').toBeGreaterThan(3)
  await page.setViewportSize({ width: 1440, height: 900 })
  /* `routesFromNav` deliberately does not name `#/runs` — it redirects rather than drawing a
     screen, so the content sweeps built on that helper must not land on it (see its own
     comment). This reconciliation is the one place that does need it, so it is added here,
     the same way `#/gallery` and `#/product` are added inside the helper itself. */
  const fromNav = (await routesFromNav(page)).map((hash) => hash.replace(/^#/, '')).concat('/runs')
  expect([...new Set(fromNav)].sort(), 'ROUTES and the nav disagree about which routes exist').toEqual(
    ROUTE_TABLE.map((r) => r.path).sort(),
  )
})

test('the runtime allow list names only real routes, real assertions and a lane', () => {
  const bad: string[] = []
  for (const [path, entries] of Object.entries(ALLOW)) {
    const route = ROUTE_TABLE.find((r) => r.path === path)
    if (route === undefined) {
      bad.push(`${path} is not a route in ROUTES`)
      continue
    }
    for (const [assertion, lane] of Object.entries(entries)) {
      if (!ASSERTIONS.includes(assertion)) bad.push(`${path} -> ${assertion} is not one of ${ASSERTIONS.join(', ')}`)
      else if (!applies(route, assertion)) bad.push(`${path} -> ${assertion} is a named exemption (EXEMPT), never a debt: delete the entry`)
      if (typeof lane !== 'string' || lane.trim() === '') bad.push(`${path} -> ${assertion} names no lane`)
    }
  }
  expect(bad).toEqual([])
})

for (const route of ROUTE_TABLE) {
  test(`${route.path} inherits the page scaffold at every width`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    const failures = new Map<string, string[]>()
    const fail = (assertion: string, message: string) => failures.set(assertion, [...(failures.get(assertion) ?? []), message])
    const want = titleOf(route)

    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto(`/#${route.path}`)
    for (const [width, height] of WIDTHS) {
      await page.setViewportSize({ width, height })
      await page.reload()
      await settle(page)
      const m = await page.evaluate(() => {
        const probe = (prop: 'height' | 'width', value: string): number => {
          const el = document.createElement('div')
          el.style.position = 'absolute'
          el.style[prop] = value
          document.body.append(el)
          const px = el.getBoundingClientRect()[prop]
          el.remove()
          return px
        }
        const pages = document.querySelectorAll<HTMLElement>('[data-bn-page]')
        const main = pages.length === 1 ? pages[0] : null
        const h1s = Array.from(document.querySelectorAll<HTMLElement>('h1')).filter((h) => h.checkVisibility())
        const h1 = h1s.length === 1 ? h1s[0] : null
        return {
          pages: pages.length,
          h1s: h1s.map((h) => (h.textContent ?? '').trim()),
          maxWidth: main ? getComputedStyle(main).maxWidth : null,
          pageW: probe('width', 'var(--bn-page-w)'),
          gap: main && h1 && main.contains(h1) ? h1.getBoundingClientRect().top - main.getBoundingClientRect().top : null,
          pageTop: probe('height', 'var(--bn-page-top)'),
          sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        }
      })
      const at = `${width}px`
      if (m.pages !== 1) fail('page', `${at}: ${m.pages} [data-bn-page]`)
      if (m.h1s.length !== 1 || m.h1s[0] !== want) fail('h1', `${at}: h1 ${JSON.stringify(m.h1s)}, want ["${want}"]`)
      const wide = applies(route, 'width') ? widthFailure(m.maxWidth, m.pageW) : null
      if (wide !== null) fail('width', `${at}: ${wide}`)
      if (applies(route, 'top') && (m.gap === null || Math.abs(m.gap - m.pageTop) > 1)) fail('top', `${at}: h1 gap ${m.gap === null ? 'none' : m.gap.toFixed(1)}, want ${m.pageTop}`)
      if (m.sideways > 0) fail('scroll', `${at}: scrolls sideways by ${m.sideways}px`)
    }
    const measured = PER_ROUTE.filter((a) => a !== 'title' && applies(route, a))
    expect(reconcile(route, failures, measured)).toEqual([])
  })

  /* THE TAB TITLE, over time, under both motion settings. Its own test because it runs on a fake
     clock, and the geometry above must not: a faked requestAnimationFrame would stall `settle`. */
  if (applies(route, 'title')) {
    test(`${route.path} holds one fixed tab title, with and without reduced motion`, async ({ page }) => {
      await page.clock.install()
      const failures = new Map<string, string[]>()
      for (const reducedMotion of ['no-preference', 'reduce'] as const) {
        await page.emulateMedia({ reducedMotion })
        await page.goto(`/#${route.path}`)
        await expect(page.locator('main').first(), 'the route drew no <main>').toBeVisible()
        const wrong = titleFailure(await readTitles(page), tabTitleOf(route))
        if (wrong !== null) failures.set('title', [...(failures.get('title') ?? []), `reduced motion ${reducedMotion}: ${wrong}`])
      }
      expect(reconcile(route, failures, ['title'])).toEqual([])
    })
  }
}

/* THE TWO ASSERTIONS THAT ONCE PASSED ON NOTHING, proved to fail on their defect.
   F1 of the review: `max-width: none` read as NaN, and a NaN comparison passed. `#/gallery` holds
   the width assertion (no allow entry), so it is measured as it stands and then with the page's
   cap removed. The judges are the same functions the route tests call. */
test('a page whose max-width is none fails the width check (fixture)', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/gallery')
  await settle(page)
  const read = () =>
    page.evaluate(() => {
      const main = document.querySelector<HTMLElement>('[data-bn-page]')
      const el = document.createElement('div')
      el.style.position = 'absolute'
      el.style.width = 'var(--bn-page-w)'
      document.body.append(el)
      const pageW = el.getBoundingClientRect().width
      el.remove()
      return { maxWidth: main ? getComputedStyle(main).maxWidth : null, pageW }
    })
  const before = await read()
  expect(widthFailure(before.maxWidth, before.pageW), 'the Kit page holds the width assertion as it stands').toBeNull()
  await page.addStyleTag({ content: '.bn-page { max-width: none !important; }' })
  const after = await read()
  expect(after.maxWidth, 'the fixture did not take').toBe('none')
  expect(widthFailure(after.maxWidth, after.pageW), 'max-width: none must fail the width check').toContain('"none"')
})

/* F2 of the review: the title was read once, under reduced motion, so an alternation never ran.
   The judge must refuse a set of reads that starts on the right title and later changes. */
test('the title judge refuses a title that changes over the window, and an empty read', () => {
  expect(titleFailure(['番地 kit', '番地 kit'], '番地 kit')).toBeNull()
  expect(titleFailure(['番地 kit', '番地 kit', '番地 banchi', '番地 kit'], '番地 kit')).toContain('番地 banchi')
  expect(titleFailure(['kit · 番地 banchi'], '番地 kit')).not.toBeNull()
  expect(titleFailure([], '番地 kit')).not.toBeNull()
})

/* AND THE READ OVER TIME, IN A BROWSER, ON A TITLE THAT IS RIGHT FIRST AND WRONG LATER. The judge
   above is fed arrays; this proves `readTitles` itself sees a change that lands mid-window, on the
   same fake clock the route tests use. The fixture is a page timer that rewrites the title seven
   seconds in, the shape of the old alternation. The first read must be the right title, or the
   test would pass on a title that was never right. */
test('the over-time title read goes red when a right title changes later (fixture)', async ({ page }) => {
  await page.clock.install()
  await page.goto('/#/gallery')
  await expect(page.locator('main').first()).toBeVisible()
  const want = tabTitleOf({ path: '/gallery', label: 'Kit', title: null, persona: null, redirect: false, view: '', file: '' })
  expect(titleFailure(await readTitles(page), want), 'the Kit page holds its title as it stands').toBeNull()

  await page.evaluate(() => {
    window.setTimeout(() => {
      document.title = '番地 banchi'
    }, 7000)
  })
  const reads = await readTitles(page)
  expect(reads[0], 'the fixture starts on the right title').toBe(want)
  expect(titleFailure(reads, want), 'a title that changes seven seconds in must fail').toContain('番地 banchi')
})

test('the palette and the keyboard sheet name every route', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/')
  await settle(page)

  await page.keyboard.press('ControlOrMeta+k')
  const palette = page.getByRole('dialog', { name: 'Go to' })
  await expect(palette).toBeVisible()
  const goTo = await palette.evaluate((root) => {
    const out: string[] = []
    for (const section of Array.from(root.querySelectorAll('[role="listbox"] > div'))) {
      if (section.querySelector('.bn-cmdk-group')?.textContent?.trim() !== 'Screens') continue
      for (const option of Array.from(section.querySelectorAll('[role="option"] > span:not(.bn-cmdk-item-hint)'))) {
        out.push((option.textContent ?? '').trim())
      }
    }
    return out
  })
  expect(goTo.length, 'the palette drew no Screens group: did its markup move?').toBeGreaterThan(3)
  await page.keyboard.press('Escape')
  await expect(palette).toBeHidden()

  await page.keyboard.press('?')
  const sheet = page.getByRole('dialog', { name: 'Keyboard shortcuts' })
  await expect(sheet).toBeVisible()
  const showAll = sheet.getByRole('button', { name: /Show every screen/ })
  if (await showAll.isVisible()) await showAll.click()
  /* An entry names a route when a row's own text is the route's label: "Home" in the jump
     group. The row's own text is its direct text, without the "when" note beside it. */
  const entries = await sheet.evaluate((root) =>
    Array.from(root.querySelectorAll('dd')).map((dd) =>
      Array.from(dd.childNodes)
        .filter((n) => n.nodeType === Node.TEXT_NODE)
        .map((n) => n.textContent ?? '')
        .join('')
        .trim(),
    ),
  )
  expect(entries.length, 'the keyboard sheet drew no rows: did its markup move?').toBeGreaterThan(3)

  const problems: string[] = []
  for (const route of ROUTE_TABLE) {
    const failures = new Map<string, string[]>()
    if (!goTo.includes(route.label)) failures.set('palette', [`"${route.label}" is not in the palette's Screens group`])
    if (!entries.includes(route.label)) failures.set('keys', [`no keyboard-sheet entry names "${route.label}"`])
    problems.push(...reconcile(route, failures, SHELL_WIDE))
  }
  expect(problems).toEqual([])
})
