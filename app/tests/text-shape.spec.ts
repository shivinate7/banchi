import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect, type Page } from '@playwright/test'

import { settleFonts } from './fontsReady'
import { routesFromNav } from './routes'
import { sealEveryTest } from './shell'
import { POPULATED_ROUTE_SEEDS, SHIPPING_EXPORT_CSV } from './routeFixtures'
import { injectRepeatedSentence, measureTextShape } from './textShape'
import { EXCLUDED_FROM_SWEEP } from './routeExclusions'

/* D194 IS SUPERSEDED BY `D-text-shape-checks`. The owner's ruling, 2026-09-23: "I think we
 * need to kill ceilings and instead just use a different way I don't like keeping a stagnant
 * static pin." This file is two thirds of the replacement (the text-density reviewer under
 * `scripts/text-density/` is the on-demand third — never a gate, D18). See
 * `app/tests/textShape.ts` for what each of the four signals below measures and why.
 *
 * A SHRINKING PENDING LIST, NEVER A CEILING. `text-shape-allow.json` is route -> assertion ->
 * lane, on `scripts/kit-adoption-allow.json`'s own precedent (the owner's Q3 ruling). This
 * check WILL find real offenders on screens no wave-2 lane has reached yet — that is expected,
 * not a bug in the check, and the fix is a pending entry naming the lane that owes it, not a
 * wider check or a suppressed route. An entry that no longer matches anything is STALE and
 * fails the run until it is deleted, so the list can only shrink.
 *
 * THE FIXTURE IS `copy-budget.spec.ts`'s OWN, kept exactly: `sealEveryTest({ store: true,
 * cards: 122 })` plus `POPULATED_ROUTE_SEEDS` for the five routes that fixture alone draws
 * empty. A repeated sentence or a long paragraph is exactly the kind of defect that only shows
 * up once a screen has real rows to repeat itself over.
 *
 * TWO WIDTHS, 1440 AND 390, because a card or a row is not the same DOM shape at both — the
 * phone chrome folds, stacks and hides differently, and a repetition only the narrow layout
 * draws would otherwise pass unseen. `routesFromNav` cannot run under 768 (`.bn-nav-link` is
 * `display: none` there, its own header says so), so the 390 pass harvests its roster off the
 * phone drawer instead, `phone.spec.ts:phoneRoutes`'s own shape, kept local here rather than
 * imported — that file is the shell lane's, not this one's, and it keeps its own copy for the
 * identical reason.
 *
 * THE MUTATION PROOF (`TEXT_SHAPE_MUTATE=<hash>`) is in `textShape.ts:injectRepeatedSentence`
 * — never by editing a file under `app/src`. Run `TEXT_SHAPE_MUTATE='#/shipping' npx
 * playwright test tests/text-shape.spec.ts` from `app/` and the spec fails, naming
 * `#/shipping` and the injected sentence.
 */

const HERE = dirname(fileURLToPath(import.meta.url))
const ALLOW_PATH = resolve(HERE, 'text-shape-allow.json')

type Allow = Record<string, Record<string, string>>

function readAllow(): Allow {
  const raw = JSON.parse(readFileSync(ALLOW_PATH, 'utf8')) as Allow & { _about?: string }
  const { _about, ...rest } = raw
  return rest
}

const MUTATE_ROUTE = process.env.TEXT_SHAPE_MUTATE ?? ''

/** The phone drawer's own roster — `phone.spec.ts:phoneRoutes`'s shape, kept local (see this
 *  file's header for why it is not imported). `#/gallery` is excluded here rather than added
 *  back, unlike that file: the kit sheet is out of scope for THIS check on purpose. */
async function drawerRoutes(page: Page): Promise<string[]> {
  await page.goto('/')
  await page.getByText('More', { exact: true }).click()
  await expect(page.locator('.bn-drawer')).toBeVisible()
  const hrefs = await page.locator('.bn-drawer .bn-nav a.bn-nav-link').evaluateAll((els) =>
    // `/^#\//` INLINE, NOT `ROUTE_HASH_SHAPE`: this callback is serialised into the BROWSER
    // by `evaluateAll` (`toString()`, the same rule `textShape.ts`'s header states for
    // `page.evaluate`), so an imported module-level const is invisible to it — measured:
    // `ROUTE_HASH_SHAPE is not defined` the first time this ran under `make design-check`.
    els.map((el) => (el as HTMLAnchorElement).getAttribute('href') ?? '').filter((h) => /^#\//.test(h)))
  await page.keyboard.press('Escape')
  await expect(page.locator('.bn-drawer')).toHaveCount(0)
  return hrefs.filter((route) => !EXCLUDED_FROM_SWEEP.test(route))
}

sealEveryTest({ store: true, cards: 122 })

async function sweep(page: Page, routes: string[], allow: Allow, used: Set<string>, problems: string[]): Promise<void> {
  function key(route: string, assertion: string): string {
    return `${route}\u0000${assertion}`
  }

  function report(route: string, assertion: string, message: string): void {
    const listed = allow[route]?.[assertion]
    if (listed !== undefined) {
      used.add(key(route, assertion))
      return
    }
    problems.push(`${route} ${assertion}: ${message}. Not on the pending list: fix it, or add a pending entry naming the lane that owes it.`)
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
      await page.evaluate(injectRepeatedSentence)
    }

    const result = await page.evaluate(measureTextShape)

    for (const hit of result.repeatedSentences) {
      report(
        route,
        'repeated-sentence',
        `"${hit.sample}" repeats on ${hit.count} elements sharing class "${hit.groupClass}"`,
      )
    }
    for (const hit of result.repeatedFacts) {
      report(route, 'repeated-fact', `"${hit.fact}" is stated in ${hit.count} separate blocks`)
    }
    for (const hit of result.longSentences) {
      report(route, 'long-sentence', `${hit.words} words: "${hit.sample}"`)
    }
    for (const hit of result.captionHeading) {
      report(
        route,
        'caption-heading',
        `"${hit.caption}" repeats ${hit.overlap}% of its heading "${hit.heading}"`,
      )
    }
  }
}

test('a route repeats no sentence across its cards and no fact twice, and keeps every sentence short and every caption its own', async ({
  page,
}) => {
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
  for (const [route, assertions] of Object.entries(ALLOW)) {
    for (const [assertion, lane] of Object.entries(assertions)) {
      if (!allRoutes.has(route)) {
        problems.push(`${route} ${assertion}: pending for lane ${lane}, but that route no longer exists. Delete the entry.`)
        continue
      }
      if (!used.has(`${route}\u0000${assertion}`)) {
        problems.push(
          `${route} ${assertion}: pending for lane ${lane}, but nothing matched it this run — the pending entry is stale. Delete it.`,
        )
      }
    }
  }

  expect(problems, problems.join('\n')).toEqual([])
})

test('the pending list names only real routes and a lane', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  const routes = await routesFromNav(page)
  const ALLOW = readAllow()
  const problems: string[] = []
  const validAssertions = new Set(['repeated-sentence', 'repeated-fact', 'long-sentence', 'caption-heading'])
  for (const [route, assertions] of Object.entries(ALLOW)) {
    if (!routes.includes(route) && !/^#\/fulfillment$/.test(route)) {
      problems.push(`${route}: not a real route`)
    }
    for (const [assertion, lane] of Object.entries(assertions)) {
      if (!validAssertions.has(assertion)) problems.push(`${route} ${assertion}: not a real assertion`)
      if (typeof lane !== 'string' || lane.trim() === '') problems.push(`${route} ${assertion}: no lane named`)
    }
  }
  expect(problems, problems.join('\n')).toEqual([])
})
