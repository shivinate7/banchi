// Protects: Every route inherits the page frame: one Page, one h1, the page width and top gap tokens, no sideways scroll, one fixed document title.
// Governs: D121, D275, D276, D291
import { test, expect, type Page } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { routesFromNav } from './routes'
import { settleFonts } from './fontsReady'
import { tabTitle } from '../src/tabTitle'
import { sealEveryTest } from './shell'
import { phoneOff, setViewport } from './phoneSwitch'

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
 *   headGap  `.bn-page-body`'s top minus the bottom of whatever `Page` draws directly above
 *            it (the header, or its own verdict/toolbar/status when the screen passes one)
 *            equals THAT element's own `margin-bottom`, with no second gap stacked on top of
 *            it (F4: Capture's own flex `gap` once doubled the header's margin — 28px at
 *            1440, 20px at 390, against every other screen's 16-24px). A route with no header
 *            (`header={false}`, the Fulfiller's screen) is exempt: there is no header to
 *            leave a gap after.
 *   scroll   nothing scrolls sideways
 *   title    ONE browser case, not per route: the shell's timer stamps `document.title` with the
 *            fixed title, read every TITLE_STEP ms over TITLE_WINDOW ms on a fake clock, under both
 *            motion settings. WHICH string each route gets is `tests/unit/tab-title.unit.ts`, over
 *            every `ROUTES` entry. The window is this file's own number, never read from App.tsx:
 *            a test that reads the value it checks passes when that value is wrong.
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
 * too (stale), so the list only shrinks. `palette` and `keys` are the shell lane's to
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

const PER_ROUTE = ['page', 'h1', 'width', 'top', 'headGap', 'scroll'] as const
const SHELL_WIDE = ['palette', 'keys'] as const
const ASSERTIONS: readonly string[] = [...PER_ROUTE, ...SHELL_WIDE]

const WIDTHS: readonly (readonly [number, number])[] = [
  [1440, 900],
  [820, 1180],
  [720, 900],
  [390, 844],
]

const titleOf = (route: RouteRow): string => route.title ?? route.label
/** The tab title's FUNCTION, over every route, is `tests/unit/tab-title.unit.ts`. Here the browser
 *  proves only that the shell's timer stamps `document.title` with it. */
const tabTitleOf = (route: RouteRow): string => tabTitle({ ...route, persona: route.persona ?? undefined })

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

/** Home's h1 is the hero greeting ("Good morning."), never the route's own title (D121: the
 *  front page says what is owed). The owner's ruling, 2026-09-25, answering the follow-up
 *  lane's question of whether the greeting stays: "yeah just keep the greeting". Only the TEXT
 *  match is exempt — Home still draws exactly one visible h1, same as every other route, so a
 *  route that grows a second h1 or loses its one h1 still goes red here. */
const H1_TEXT_EXEMPT = new Set(['/'])

/** The h1 assertion's verdict: exactly one visible h1, and — unless the route is in
 *  `H1_TEXT_EXEMPT` — its text is `want`. */
function h1Failure(path: string, h1s: readonly string[], want: string): string | null {
  if (h1s.length !== 1) return `h1 ${JSON.stringify(h1s)}, want exactly one`
  if (!H1_TEXT_EXEMPT.has(path) && h1s[0] !== want) return `h1 ${JSON.stringify(h1s)}, want ["${want}"]`
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
    headGap: 'D5: `header={false}` (no shell) means there is no `.bn-page-head` to leave a gap after.',
  },
}

/* A REDIRECT ROUTE (D291's `#/runs`) renders nothing of its own — it sends
 * the browser straight to another route's screen. `h1` names what THAT screen drew,
 * not this row's `label`, so holding a redirect to its own label is asking it to fail forever on
 * a fact it was never going to make true. `page`/`width`/`top`/`scroll` still apply: they are
 * measuring the screen the browser actually lands on. */
const REDIRECT_EXEMPT = new Set(['h1'])

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
  await setViewport(page, { width: 1440, height: 900 })
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
  /* `#/gallery`'S PAGE, H1, WIDTH, TOP GAP AND SIDEWAYS SCROLL ARE NOT READ HERE: `gallery.spec.ts`'s
     "the kit is a Page: one h1, one width, one top gap, no sideways scroll, at every width" holds
     those, in one load. Its head gap is NOT held there, so it still runs. */
  const heldByGallery = route.path === '/gallery' ? new Set(['page', 'h1', 'width', 'top', 'scroll']) : new Set<string>()
  test(`${route.path} inherits the page scaffold at every width`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    const failures = new Map<string, string[]>()
    const fail = (assertion: string, message: string) => heldByGallery.has(assertion) || failures.set(assertion, [...(failures.get(assertion) ?? []), message])
    const want = titleOf(route)

    await setViewport(page, { width: 1440, height: 900 })
    await page.goto(`/#${route.path}`)
    for (const [width, height] of WIDTHS) {
      if (phoneOff(width)) continue
      await setViewport(page, { width, height })
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
        const head = main ? main.querySelector<HTMLElement>(':scope > .bn-page-head') : null
        const body = main ? main.querySelector<HTMLElement>(':scope > .bn-page-body') : null
        /* THE ELEMENT DIRECTLY ABOVE THE BODY, NOT ALWAYS THE HEADER: `Page` may also draw a
           verdict, a toolbar or a status slot between them (Page.tsx), each with its own
           `margin-bottom`. The gap onto the body must equal THAT element's own margin, whichever
           one it is — never a header-to-body distance that a verdict or toolbar would legitimately
           widen past `head`'s own margin, and never a second gap stacked on top of it either. */
        const lastBeforeBody = body ? (body.previousElementSibling as HTMLElement | null) : null
        return {
          pages: pages.length,
          h1s: h1s.map((h) => (h.textContent ?? '').trim()),
          maxWidth: main ? getComputedStyle(main).maxWidth : null,
          pageW: probe('width', 'var(--bn-page-w)'),
          gap: main && h1 && main.contains(h1) ? h1.getBoundingClientRect().top - main.getBoundingClientRect().top : null,
          pageTop: probe('height', 'var(--bn-page-top)'),
          headGap: lastBeforeBody && body ? body.getBoundingClientRect().top - lastBeforeBody.getBoundingClientRect().bottom : null,
          headGapWant: lastBeforeBody ? parseFloat(getComputedStyle(lastBeforeBody).marginBottom) : null,
          hasHead: head !== null,
          sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        }
      })
      const at = `${width}px`
      if (m.pages !== 1) fail('page', `${at}: ${m.pages} [data-bn-page]`)
      const h1bad = h1Failure(route.path, m.h1s, want)
      if (h1bad !== null) fail('h1', `${at}: ${h1bad}`)
      const wide = applies(route, 'width') ? widthFailure(m.maxWidth, m.pageW) : null
      if (wide !== null) fail('width', `${at}: ${wide}`)
      if (applies(route, 'top') && (m.gap === null || Math.abs(m.gap - m.pageTop) > 1)) fail('top', `${at}: h1 gap ${m.gap === null ? 'none' : m.gap.toFixed(1)}, want ${m.pageTop}`)
      if (applies(route, 'headGap')) {
        if (!m.hasHead || m.headGap === null || m.headGapWant === null) {
          fail('headGap', `${at}: no .bn-page-head/.bn-page-body pair to measure`)
        } else if (Math.abs(m.headGap - m.headGapWant) > 1) {
          fail('headGap', `${at}: gap onto the body ${m.headGap.toFixed(1)}, want ${m.headGapWant.toFixed(1)} (the element right above it's own margin-bottom, no extra gap stacked on it)`)
        }
      }
      if (m.sideways > 0) fail('scroll', `${at}: scrolls sideways by ${m.sideways}px`)
    }
    const measured = PER_ROUTE.filter((a) => !heldByGallery.has(a) && applies(route, a))
    expect(reconcile(route, failures, measured)).toEqual([])
  })
}

/* THE SHELL'S TIMER STAMPS THE TAB TITLE, over time, under both motion settings: the one browser
   case for it. Which string each route gets is `tests/unit/tab-title.unit.ts`. One route is enough
   because the stamp is one effect in `App.tsx`, the same for every screen. On a fake clock, so its
   own test: a faked requestAnimationFrame would stall the geometry's `settle`. */
test('the shell holds one fixed tab title, with and without reduced motion', async ({ page }) => {
  await page.clock.install()
  const route = ROUTE_TABLE.find((r) => r.path === '/pricing')
  if (route === undefined) throw new Error('/pricing is not in ROUTES: pick another route for the title case')
  const failures: string[] = []
  for (const reducedMotion of ['no-preference', 'reduce'] as const) {
    await page.emulateMedia({ reducedMotion })
    await page.goto(`/#${route.path}`)
    await expect(page.locator('main').first(), 'the route drew no <main>').toBeVisible()
    const wrong = titleFailure(await readTitles(page), tabTitleOf(route))
    if (wrong !== null) failures.push(`reduced motion ${reducedMotion}: ${wrong}`)
  }
  expect(failures).toEqual([])
})

/* THE TWO ASSERTIONS THAT ONCE PASSED ON NOTHING, proved to fail on their defect.
   F1 of the review: `max-width: none` read as NaN, and a NaN comparison passed. `#/gallery` holds
   the width assertion (no allow entry), so it is measured as it stands and then with the page's
   cap removed. The judges are the same functions the route tests call. */
test('a page whose max-width is none fails the width check (fixture)', async ({ page }) => {
  await setViewport(page, { width: 1440, height: 900 })
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

/* The h1 exemption is Home's alone (owner's ruling, 2026-09-25, "yeah just keep the greeting").
   Every other route stays held to its own title: a mismatch anywhere else is still red, so the
   exemption cannot quietly widen to cover a defect on a different screen. */
test('h1Failure exempts only Home\'s text, and holds every route to exactly one h1', () => {
  expect(h1Failure('/pricing', ['Pricing'], 'Pricing')).toBeNull()
  expect(h1Failure('/pricing', ['Good morning'], 'Pricing'), 'a non-Home mismatch must fail').toContain('want')
  expect(h1Failure('/pricing', [], 'Pricing'), 'no h1 at all must fail').toContain('want exactly one')
  expect(h1Failure('/pricing', ['Pricing', 'Pricing'], 'Pricing'), 'two h1s must fail').toContain('want exactly one')
  expect(h1Failure('/', ['Good morning.'], 'Home'), 'Home\'s greeting is exempt from the text match').toBeNull()
  expect(h1Failure('/', [], 'Home'), 'Home still needs exactly one h1').not.toBeNull()
  expect(h1Failure('/', ['Good morning.', 'Home'], 'Home'), 'Home still needs exactly one h1').not.toBeNull()
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
  await setViewport(page, { width: 1440, height: 900 })
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
  const sheet = page.getByRole('dialog', { name: 'Shortcuts' })
  await expect(sheet).toBeVisible()
  const showAll = sheet.getByRole('button', { name: 'More' })
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
