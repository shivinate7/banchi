import { test, expect, type Page } from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { routesFromNav } from './routes'
import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'

/* EVERY SCREEN INHERITS THE PAGE SCAFFOLD, ASSERTED IN A BROWSER (D-page-scaffold).
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
 *            2026-09-23.
 *   palette  the command palette's "Go to" group lists the route
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
  readonly view: string
  readonly file: string
}

const ROUTE_TABLE: readonly RouteRow[] = JSON.parse(
  execFileSync(process.execPath, [resolve(ROOT, 'scripts', 'kit-adoption.mjs'), '--routes'], { encoding: 'utf8' }),
) as RouteRow[]

type Allow = Record<string, Record<string, string>>
const ALLOW: Allow =
  (JSON.parse(readFileSync(resolve(ROOT, 'scripts', 'kit-adoption-allow.json'), 'utf8')) as { runtime?: Allow }).runtime ?? {}

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
/** The owner's ruling, 2026-09-23: one fixed tab title, "番地 " and the screen name in lowercase. */
const tabTitleOf = (route: RouteRow): string => `番地 ${titleOf(route).toLowerCase()}`

/* THE NAMED EXEMPTIONS: an assertion a persona is NOT held to, with the ruling that says so.
 * Never a debt, so never on the allow list, and the allow list may not name one. */
const EXEMPT: Readonly<Record<string, Readonly<Record<string, string>>>> = {
  fulfiller: {
    width: 'D5 (two personas) and docs/DESIGN.md\'s Fulfillment floors: the Fulfiller\'s screen has no shell and sizes its own column.',
    top: 'D5 and docs/DESIGN.md\'s Fulfillment floors: no shell, so no shared top gap to sit under.',
    title: 'D5: the Fulfiller\'s tab names the task and carries no brand.',
  },
}

/** Is this route held to this assertion at all? `false` only for a named exemption. */
const applies = (route: RouteRow, assertion: string): boolean =>
  route.persona === null || EXEMPT[route.persona]?.[assertion] === undefined

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
     it is measured as it stands. */
  await page
    .waitForFunction(() => document.querySelector('[aria-busy="true"]') === null, null, { timeout: 5000 })
    .catch(() => undefined)
}

test('the route table is read, and it names the same routes the nav does', async ({ page }) => {
  expect(ROUTE_TABLE.length, 'kit-adoption --routes returned almost nothing').toBeGreaterThan(3)
  await page.setViewportSize({ width: 1440, height: 900 })
  const fromNav = (await routesFromNav(page)).map((hash) => hash.replace(/^#/, ''))
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
          maxWidth: main ? parseFloat(getComputedStyle(main).maxWidth) : null,
          pageW: probe('width', 'var(--bn-page-w)'),
          gap: main && h1 && main.contains(h1) ? h1.getBoundingClientRect().top - main.getBoundingClientRect().top : null,
          pageTop: probe('height', 'var(--bn-page-top)'),
          sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          docTitle: document.title,
        }
      })
      const at = `${width}px`
      if (m.pages !== 1) fail('page', `${at}: ${m.pages} [data-bn-page]`)
      if (m.h1s.length !== 1 || m.h1s[0] !== want) fail('h1', `${at}: h1 ${JSON.stringify(m.h1s)}, want ["${want}"]`)
      if (applies(route, 'width') && (m.maxWidth === null || Math.abs(m.maxWidth - m.pageW) > 0.5)) fail('width', `${at}: max-width ${m.maxWidth}, want ${m.pageW}`)
      if (applies(route, 'top') && (m.gap === null || Math.abs(m.gap - m.pageTop) > 1)) fail('top', `${at}: h1 gap ${m.gap === null ? 'none' : m.gap.toFixed(1)}, want ${m.pageTop}`)
      if (m.sideways > 0) fail('scroll', `${at}: scrolls sideways by ${m.sideways}px`)
      if (applies(route, 'title') && m.docTitle !== tabTitleOf(route)) fail('title', `${at}: "${m.docTitle}", want "${tabTitleOf(route)}"`)
    }
    const measured = PER_ROUTE.filter((a) => applies(route, a))
    expect(reconcile(route, failures, measured)).toEqual([])
  })
}

test('the palette and the keyboard sheet name every route', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/#/')
  await settle(page)

  await page.keyboard.press('ControlOrMeta+k')
  const palette = page.getByRole('dialog', { name: 'Command palette' })
  await expect(palette).toBeVisible()
  const goTo = await palette.evaluate((root) => {
    const out: string[] = []
    for (const section of Array.from(root.querySelectorAll('[role="listbox"] > div'))) {
      if (section.querySelector('.bn-cmdk-group')?.textContent?.trim() !== 'Go to') continue
      for (const option of Array.from(section.querySelectorAll('[role="option"] > span:not(.bn-cmdk-item-hint)'))) {
        out.push((option.textContent ?? '').trim())
      }
    }
    return out
  })
  expect(goTo.length, 'the palette drew no "Go to" group: did its markup move?').toBeGreaterThan(3)
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
    if (!goTo.includes(route.label)) failures.set('palette', [`"${route.label}" is not in the palette's Go to group`])
    if (!entries.includes(route.label)) failures.set('keys', [`no keyboard-sheet entry names "${route.label}"`])
    problems.push(...reconcile(route, failures, SHELL_WIDE))
  }
  expect(problems).toEqual([])
})
