import { test, expect, type Page } from '@playwright/test'
import { routesFromNav } from './routes'
import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'

/* ONE LEFT EDGE FOR EVERY SCREEN (`D197`). The owner's own three screenshots,
 * 2026-09-13: `#/pricing`'s content started roughly 330px further right than `#/review` and
 * `#/inventory` at the SAME window width. The cause was `.bn-page { margin: 0 auto }` — every
 * screen that sets its own `--bn-page-max` (Pricing and ValueBands at 1120px, Codes/Home/Orders
 * at `--bn-page-w-rows`, 1344px) was CENTERED inside the shell's own column rather than pinned
 * to it, so a narrower cap moved the whole gutter and the left edge changed between routes. A
 * page's WIDTH may vary by screen — Pricing's table and Inventory's three columns legitimately
 * want different caps — but the LEFT EDGE may not: `.bn-page` is `margin: 0` now, never `auto`.
 *
 * THIS FILE FINDS ITS SUBJECTS THE WAY `wide.spec.ts` DOES: every owner route off the sidebar
 * (`routesFromNav`), at 1440 and 1920 (the owner's own rig is wide), in both rail states.
 * `#/fulfillment` renders NO shell at all (D5) — there is no sidebar-anchored column to compare
 * it against, and its `.ff-column` answers to no `--bn-page-max` — so it is the one route this
 * sweep excludes rather than measures.
 *
 * THE ASSERTION IS RELATIVE, NEVER A HARD-CODED PIXEL: every route's `.bn-page` left edge must
 * equal the FIRST route's (Home's) within 1px, at the same width and rail state. A hard-coded
 * expectation would have to be re-derived every time the sidebar width or the page padding
 * moved; this is right by construction as long as one screen is right.
 */

sealEveryTest({ store: true, cards: 40 })

const RAILS = [
  { label: 'sidebar', stored: 'wide' },
  { label: 'rail', stored: 'rail' },
] as const

/** Seeded before first paint, `wide.spec.ts:withRail`'s own argument: a keypress races the
 *  first frame this file measures, and `App.tsx:readRail` reads `banchi.rail` once, in a
 *  `useState` initialiser. */
async function withRail(page: Page, stored: string, width: number): Promise<void> {
  await page.addInitScript((value) => {
    try {
      /* eslint-disable-next-line no-restricted-syntax -- seeding the shell's own device key
         into a known state before first paint, the same call `wide.spec.ts:withRail` and
         `orders.spec.ts:remember` already make. */
      window.localStorage.setItem('banchi.rail', value)
    } catch {
      /* unreadable storage reads as never chosen, which is the sidebar — a real default */
    }
  }, stored)
  await page.setViewportSize({ width, height: 1000 })
}

test('every owner screen shares one left edge, at every width and rail state', async ({
  page,
}) => {
  await withRail(page, 'wide', 1920)
  const routes = (await routesFromNav(page)).filter((r) => r !== '#/fulfillment')

  /* ANTI-VACUITY: a harvest that returned almost nothing would make the comparison below
     vacuous — one route trivially "agrees" with itself. `routesFromNav` itself floors at 3;
     this floors at what the roster actually holds today (twelve screens, one excluded). */
  expect(routes.length, 'the route harvest returned too few screens to compare').toBeGreaterThan(6)

  const mismatches: string[] = []
  let measured = 0

  for (const width of [1440, 1920]) {
    for (const rail of RAILS) {
      await withRail(page, rail.stored, width)

      let referenceLeft: number | null = null
      let referenceRoute = ''

      for (const route of routes) {
        await page.goto(`/${route}`)
        await settleFonts(page)
        await expect(page.locator('main').first(), `${route}: drew no <main>`).toBeVisible()

        const left = await page.evaluate(() => {
          const el = document.querySelector('.bn-page')
          return el === null ? null : el.getBoundingClientRect().left
        })
        expect(left, `${route} at ${width} (${rail.label}): no .bn-page to measure`).not.toBeNull()
        measured += 1

        if (referenceLeft === null) {
          referenceLeft = left as number
          referenceRoute = route
          continue
        }

        const delta = Math.abs((left as number) - referenceLeft)
        if (delta > 1) {
          mismatches.push(
            `${route} at ${width}px (${rail.label}): left=${(left as number).toFixed(1)} vs ` +
              `${referenceRoute}'s ${referenceLeft.toFixed(1)} — off by ${delta.toFixed(1)}px`,
          )
        }
      }
    }
  }

  expect(measured, 'the sweep measured almost nothing — did the roster harvest break?')
    .toBeGreaterThan(20)
  expect(
    mismatches,
    'a screen\'s .bn-page left edge disagrees with the rest — a lower --bn-page-max is ' +
      'centering the page instead of narrowing it from a shared left inset:\n  ' +
      mismatches.join('\n  '),
  ).toEqual([])
})
