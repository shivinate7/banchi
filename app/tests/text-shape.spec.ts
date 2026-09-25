import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '@playwright/test'

import { sealEveryTest } from './shell'
import { routesFromNav } from './routes'
import { sweepEveryRoute } from './routeSweep'
import { PRODUCT_ROUTE } from './routeFixtures'
import { injectRepeatedSentence, measureTextShape, type TextShapeResult } from './textShape'

/* D194 IS SUPERSEDED BY `D284`. The owner's ruling, 2026-09-23: "I think we
 * need to kill ceilings and instead just use a different way I don't like keeping a stagnant
 * static pin." This file is the repetition check and the sentence-shape check. The third
 * piece, the on-demand density pass, is `make text-density`, which runs THIS file's sweep in a
 * report mode (`TEXT_DENSITY=1`, below), so the pass reads the same screens in the same state.
 * See `textShape.ts` for what each of the four signals measures and why.
 *
 * THE SWEEP IS `routeSweep.ts:sweepEveryRoute`, shared with `machine-words.spec.ts` and
 * `money-face.spec.ts`: every route at 1440 and at 390, every populated seed registered once,
 * and every screen measured only once it is LOADED (the shell names the route, one
 * `.bn-view`, nothing busy, the text holding still). Its header says what is NOT read: no
 * sheet, modal, popover, toast, drawer or palette is opened, and only `.bn-view` is read.
 *
 * A SHRINKING PENDING LIST, NEVER A CEILING. `text-shape-allow.json` is
 * route -> assertion -> finding key -> lane. The finding key is the finding's own text (see
 * `textShape.ts:TextShapeResult`), so a listed entry excuses that one finding and no other: a
 * NEW finding on a route that already has one listed still goes red. An entry that matches
 * nothing this run is STALE and fails the run until it is deleted, so the list only shrinks.
 *
 * THE MUTATION PROOF (`TEXT_SHAPE_MUTATE=<hash>`) is `textShape.ts:injectRepeatedSentence`,
 * through `page.evaluate`, never an edit under `app/src`. It draws one sentence on three
 * cards, and the sentence carries the fact "4321 widgets", so it trips `repeated-sentence` and
 * `repeated-fact` at once. From `app/`, `TEXT_SHAPE_MUTATE='#/' npx playwright test
 * tests/text-shape.spec.ts` fails on a route whose `repeated-fact` is already listed.
 */

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..', '..')
const ALLOW_PATH = resolve(HERE, 'text-shape-allow.json')
const DENSITY_PATH = resolve(ROOT, '.serve', 'text-density.json')

const ASSERTIONS = ['repeated-sentence', 'repeated-fact', 'long-sentence', 'caption-heading'] as const
type Assertion = (typeof ASSERTIONS)[number]

/** route -> assertion -> finding key -> lane. */
type Allow = Record<string, Partial<Record<Assertion, Record<string, string>>>>

function readAllow(): Allow {
  const raw = JSON.parse(readFileSync(ALLOW_PATH, 'utf8')) as Allow & { _about?: string }
  const { _about, ...rest } = raw
  return rest
}

const MUTATE_ROUTE = process.env.TEXT_SHAPE_MUTATE ?? ''
const DENSITY = process.env.TEXT_DENSITY === '1'

sealEveryTest({ store: true, cards: 122 })

test('a route repeats no sentence across its cards and no fact twice, and keeps every sentence short and every caption its own', async ({
  page,
}) => {
  const ALLOW = readAllow()
  const used = new Set<string>()
  const problems: string[] = []
  const density: Array<{ route: string; width: number } & TextShapeResult> = []

  function report(route: string, assertion: Assertion, key: string, message: string): void {
    if (ALLOW[route]?.[assertion]?.[key] !== undefined) {
      used.add(`${route}\u0000${assertion}\u0000${key}`)
      return
    }
    problems.push(
      `${route} ${assertion} ${JSON.stringify(key)}: ${message}. Not on the pending list: fix it, or add a pending entry naming the lane that owes it.`,
    )
  }

  const swept = await sweepEveryRoute(page, async (route, width) => {
    if (MUTATE_ROUTE !== '' && MUTATE_ROUTE === route) await page.evaluate(injectRepeatedSentence)
    const result = await page.evaluate(measureTextShape)
    if (DENSITY) {
      density.push({ route, width, ...result })
      return
    }
    for (const hit of result.repeatedSentences) {
      report(route, 'repeated-sentence', hit.key, `at ${width}, on ${hit.count} elements of class "${hit.groupClass}"`)
    }
    for (const hit of result.repeatedFacts) {
      report(route, 'repeated-fact', hit.key, `at ${width}, stated in ${hit.count} separate blocks`)
    }
    for (const hit of result.longSentences) {
      report(route, 'long-sentence', hit.key, `at ${width}, ${hit.words} words: "${hit.sample}"`)
    }
    for (const hit of result.captionHeading) {
      report(route, 'caption-heading', hit.key, `at ${width}, repeats ${hit.overlap}% of its heading "${hit.heading}"`)
    }
  })

  // REPORT MODE (`make text-density`): write the receipt, assert nothing. D18: a pass that
  // writes never gates, and this mode is on no gate's path.
  if (DENSITY) {
    mkdirSync(dirname(DENSITY_PATH), { recursive: true })
    writeFileSync(DENSITY_PATH, `${JSON.stringify({ measured: density }, null, 2)}\n`)
    return
  }

  for (const [route, byAssertion] of Object.entries(ALLOW)) {
    for (const [assertion, keys] of Object.entries(byAssertion)) {
      for (const [key, lane] of Object.entries(keys ?? {})) {
        if (!swept.has(route)) {
          problems.push(`${route} ${assertion} ${JSON.stringify(key)}: pending for lane ${lane}, but that route was not swept. Delete the entry.`)
        } else if (!used.has(`${route}\u0000${assertion}\u0000${key}`)) {
          problems.push(
            `${route} ${assertion} ${JSON.stringify(key)}: pending for lane ${lane}, but nothing matched it this run — the pending entry is stale. Delete it.`,
          )
        }
      }
    }
  }

  expect(problems, problems.join('\n')).toEqual([])
})

test('the pending list names only real routes, real assertions and a lane', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  const routes = await routesFromNav(page)
  const ALLOW = readAllow()
  const problems: string[] = []
  for (const [route, byAssertion] of Object.entries(ALLOW)) {
    if (!routes.includes(route) && route !== PRODUCT_ROUTE) problems.push(`${route}: not a route the sweep reads`)
    for (const [assertion, keys] of Object.entries(byAssertion)) {
      if (!(ASSERTIONS as readonly string[]).includes(assertion)) problems.push(`${route} ${assertion}: not a real assertion`)
      if (typeof keys !== 'object' || keys === null) {
        problems.push(`${route} ${assertion}: not a finding-key -> lane map`)
        continue
      }
      for (const [key, lane] of Object.entries(keys)) {
        if (typeof lane !== 'string' || lane.trim() === '') problems.push(`${route} ${assertion} ${key}: no lane named`)
      }
    }
  }
  expect(problems, problems.join('\n')).toEqual([])
})
