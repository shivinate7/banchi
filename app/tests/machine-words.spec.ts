import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect, type Page } from '@playwright/test'

import { settleFonts } from './fontsReady'
import { routesFromNav } from './routes'
import { sealEveryTest } from './shell'
import { POPULATED_ROUTE_SEEDS, SHIPPING_EXPORT_CSV } from './routeFixtures'
import { scanMachineWords } from './machineWords'
import { EXCLUDED_FROM_SWEEP, ROUTE_HASH_SHAPE } from './routeExclusions'

/* D196'S OWN GAP: THE AST WALK NEVER READS WHAT THE BROWSER PAINTS. The owner's ruling,
 * 2026-09-23: "codes go behind a details disclosure, the word list grows, and a new browser
 * check reads rendered text." `scripts/docs-audit.py`'s `no mechanism on screen` row still
 * owns the JSX-literal half (fast, runs on every commit, needs no browser); this file is the
 * half that reads what actually reaches the owner's screen — a server response relayed
 * verbatim, the demo's own fixture text, anything composed at runtime the AST walk cannot
 * trace — over `.bn-view`'s `innerText`, so a closed `<details>` (`D-notice-detail`'s new
 * home for a code or a path) contributes nothing, the same as it does to a person reading
 * the screen.
 *
 * ONE WORD LIST, `scripts/machine-words.json`, READ ONCE by both this file and the Python
 * row — never a second dictionary that could drift from the first.
 *
 * A SHRINKING PENDING LIST, keyed by ROUTE rather than file (rendered text carries no source
 * file): `machine-words-allow.json`, on the same shape and the same owner's Q3 ruling
 * `text-shape-allow.json` already argues for.
 *
 * TWO WIDTHS, 1440 AND 390 — `text-shape.spec.ts`'s own argument: the phone chrome folds and
 * hides content differently, so a word only the narrow layout draws would otherwise pass
 * unseen. See that file's header for why the 390 pass harvests its own roster off the phone
 * drawer rather than `routesFromNav`, which cannot run under 768px.
 */

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..', '..')
const ALLOW_PATH = resolve(HERE, 'machine-words-allow.json')
const WORDS_PATH = resolve(ROOT, 'scripts', 'machine-words.json')

type Allow = Record<string, Record<string, string>>

function readAllow(): Allow {
  const raw = JSON.parse(readFileSync(ALLOW_PATH, 'utf8')) as Allow & { _about?: string }
  const { _about, ...rest } = raw
  return rest
}

function readWords(): { words: Record<string, string>; repoTopDirs: string[] } {
  const raw = JSON.parse(readFileSync(WORDS_PATH, 'utf8')) as {
    words: Record<string, string>
    repoTopDirs: string[]
  }
  return { words: raw.words, repoTopDirs: raw.repoTopDirs }
}

/** The phone drawer's own roster — `phone.spec.ts:phoneRoutes`'s shape, kept local (see this
 *  file's header). `#/gallery` stays excluded here, the kit-sheet argument this file's header
 *  gives. */
async function drawerRoutes(page: Page): Promise<string[]> {
  await page.goto('/')
  await page.getByText('More', { exact: true }).click()
  await expect(page.locator('.bn-drawer')).toBeVisible()
  const hrefs = await page.locator('.bn-drawer .bn-nav a.bn-nav-link').evaluateAll((els) =>
    els.map((el) => (el as HTMLAnchorElement).getAttribute('href') ?? '').filter((h) => ROUTE_HASH_SHAPE.test(h)))
  await page.keyboard.press('Escape')
  await expect(page.locator('.bn-drawer')).toHaveCount(0)
  return hrefs.filter((route) => !EXCLUDED_FROM_SWEEP.test(route))
}

sealEveryTest({ store: true, cards: 122 })

async function sweep(
  page: Page,
  routes: string[],
  dictionary: { words: Record<string, string>; repoTopDirs: string[] },
  allow: Allow,
  used: Set<string>,
  problems: string[],
): Promise<void> {
  function key(route: string, term: string): string {
    return `${route}\u0000${term}`
  }

  function report(route: string, term: string, sample: string): void {
    const listed = allow[route]?.[term]
    if (listed !== undefined) {
      used.add(key(route, term))
      return
    }
    problems.push(
      `${route}: '${term}' — "${sample}". Not on the pending list: fix it, or add a pending entry naming the lane that owes it.`,
    )
  }

  for (const route of routes) {
    const populate = POPULATED_ROUTE_SEEDS[route]
    if (populate !== undefined) await populate(page)

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

    const result = await page.evaluate(scanMachineWords, dictionary)

    for (const hit of result.words) {
      report(route, hit.word.toLowerCase(), hit.sample)
    }
    for (const hit of result.paths) {
      report(route, hit.path.toLowerCase(), hit.sample)
    }
  }
}

test('no route draws a machine word or a request path where the owner reads it', async ({ page }) => {
  const ALLOW = readAllow()
  const dictionary = readWords()
  const used = new Set<string>()
  const problems: string[] = []

  await page.setViewportSize({ width: 1440, height: 1000 })
  const wideRoutes = (await routesFromNav(page)).filter((route) => !EXCLUDED_FROM_SWEEP.test(route))
  expect(wideRoutes.length, 'the route harvest returned too few screens to check').toBeGreaterThan(6)
  await sweep(page, wideRoutes, dictionary, ALLOW, used, problems)

  await page.setViewportSize({ width: 390, height: 844 })
  const phoneRoutesList = await drawerRoutes(page)
  expect(phoneRoutesList.length, 'the phone drawer harvest returned too few screens to check').toBeGreaterThan(6)
  await sweep(page, phoneRoutesList, dictionary, ALLOW, used, problems)

  const allRoutes = new Set([...wideRoutes, ...phoneRoutesList])
  for (const [route, terms] of Object.entries(ALLOW)) {
    for (const [term, lane] of Object.entries(terms)) {
      if (!allRoutes.has(route)) {
        problems.push(`${route} ${term}: pending for lane ${lane}, but that route no longer exists. Delete the entry.`)
        continue
      }
      if (!used.has(`${route}\u0000${term}`)) {
        problems.push(
          `${route} ${term}: pending for lane ${lane}, but nothing matched it this run — the pending entry is stale. Delete it.`,
        )
      }
    }
  }

  expect(problems, problems.join('\n')).toEqual([])
})
