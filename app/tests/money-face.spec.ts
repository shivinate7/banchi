import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect, type Page } from '@playwright/test'

import { settleFonts } from './fontsReady'
import { routesFromNav } from './routes'
import { sealEveryTest } from './shell'
import { POPULATED_ROUTE_SEEDS, SHIPPING_EXPORT_CSV } from './routeFixtures'
import { scanMoneyFace } from './moneyFace'
import { EXCLUDED_FROM_SWEEP, ROUTE_HASH_SHAPE } from './routeExclusions'

/* D221 — MONEY STAYS MONO, EVERYWHERE. Owned by the text-checks lane on the orchestrator's own
 * assignment: "the rendered-page money check" — this file already reads rendered text the
 * same way `machine-words.spec.ts` does, so it is the natural home for the second rendered-
 * page check the 2026-09-23 review asked for. See `moneyFace.ts` for what is measured and why
 * `getComputedStyle` rather than a class-name check.
 *
 * A SHRINKING PENDING LIST, `money-face-allow.json`, route -> amount -> lane, on the same
 * shape `text-shape-allow.json` and `machine-words-allow.json` already use.
 *
 * TWO WIDTHS, `text-shape.spec.ts`'s own argument — see that file's header for the phone-
 * drawer harvest this one reuses locally.
 *
 * THE MUTATION PROOF (`MONEY_FACE_MUTATE=<hash>`): injects a real dollar figure drawn in
 * Inter — never by editing a file under `app/src`. Run `MONEY_FACE_MUTATE='#/pricing' npx
 * playwright test tests/money-face.spec.ts` from `app/` and the spec fails, naming the route
 * and the figure.
 */

const HERE = dirname(fileURLToPath(import.meta.url))
const ALLOW_PATH = resolve(HERE, 'money-face-allow.json')

// route -> lane, ONE LEVEL, unlike `text-shape-allow.json` and `machine-words-allow.json`'s
// route -> term -> lane. A specific dollar FIGURE is seeded-random on several routes
// (`sealEveryTest({ cards: 122 })`'s own card weights and prices draw a different amount on
// every run — measured: `#/shipping`'s cards read `$4.20`/`$12.40`/`$18.00` one run and
// nothing the next, `#/revenue` read `$3.31` a run after that). Keying on the amount itself
// would make the pending list flake with the fixture instead of with the product, so this
// list names the ROUTE that owes a fix, on the orchestrator's own "file -> lane" shape.
type Allow = Record<string, string>

function readAllow(): Allow {
  const raw = JSON.parse(readFileSync(ALLOW_PATH, 'utf8')) as Allow & { _about?: string }
  const { _about, ...rest } = raw
  return rest
}

const MUTATE_ROUTE = process.env.MONEY_FACE_MUTATE ?? ''

/** The phone drawer's own roster, kept local — `text-shape.spec.ts`'s own argument. */
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

async function sweep(page: Page, routes: string[], allow: Allow, used: Set<string>, problems: string[]): Promise<void> {
  function report(route: string, amount: string, detail: string): void {
    const listed = allow[route]
    if (listed !== undefined) {
      used.add(route)
      return
    }
    problems.push(
      `${route}: '${amount}' — ${detail}. Not on the pending list: draw it in .bn-money, or add a pending entry naming the lane that owes it.`,
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

    if (MUTATE_ROUTE !== '' && MUTATE_ROUTE === route) {
      await page.evaluate(() => {
        const host = document.querySelector('.bn-view') ?? document.body
        const span = document.createElement('span')
        span.style.fontFamily = "'Inter', sans-serif"
        span.textContent = '$4.20'
        host.appendChild(span)
      })
    }

    const result = await page.evaluate(scanMoneyFace)

    for (const hit of result.text) {
      report(route, hit.amount, `drawn as "${hit.fontFamily}" in "${hit.sample}"`)
    }
    for (const hit of result.fields) {
      report(route, hit.amount, `a <${hit.tag}> field drawn as "${hit.fontFamily}"`)
    }
  }
}

test('every visible dollar figure on every route is drawn in the mono face', async ({ page }) => {
  const ALLOW = readAllow()
  const used = new Set<string>()
  const problems: string[] = []

  await page.setViewportSize({ width: 1440, height: 1000 })
  const wideRoutes = (await routesFromNav(page)).filter((route) => !EXCLUDED_FROM_SWEEP.test(route))
  expect(wideRoutes.length, 'the route harvest returned too few screens to check').toBeGreaterThan(6)
  await sweep(page, wideRoutes, ALLOW, used, problems)

  await page.setViewportSize({ width: 390, height: 844 })
  const phoneRoutesList = await drawerRoutes(page)
  expect(phoneRoutesList.length, 'the phone drawer harvest returned too few screens to check').toBeGreaterThan(6)
  await sweep(page, phoneRoutesList, ALLOW, used, problems)

  const allRoutes = new Set([...wideRoutes, ...phoneRoutesList])
  for (const [route, lane] of Object.entries(ALLOW)) {
    if (!allRoutes.has(route)) {
      problems.push(`${route}: pending for lane ${lane}, but that route no longer exists. Delete the entry.`)
      continue
    }
    if (!used.has(route)) {
      problems.push(
        `${route}: pending for lane ${lane}, but nothing matched it this run — the pending entry is stale. Delete it.`,
      )
    }
  }

  expect(problems, problems.join('\n')).toEqual([])
})
