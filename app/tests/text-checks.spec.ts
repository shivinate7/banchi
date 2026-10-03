// Protects: Every screen is read once, and no screen draws a money figure off the mono face, a machine word, a repeated sentence or fact, an over-long sentence or a caption that repeats its heading.
// Governs: D18, D196, D221, D269, D284
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect, type Page } from '@playwright/test'

import { sealEveryTest } from './shell'
import { routesFromNav } from './routes'
import { sweepEveryRoute } from './routeSweep'
import { PRODUCT_ROUTE } from './routeFixtures'
import { injectRepeatedSentence, measureTextShape, type TextShapeResult } from './textShape'
import { injectMachineWord, scanMachineWords } from './machineWords'
import { injectInterMoney, scanMoneyFace } from './moneyFace'
import { setViewport } from './phoneSwitch'

/* ONE SWEEP, THREE CHECKS (D284). `money-face.spec.ts`, `machine-words.spec.ts` and
 * `text-shape.spec.ts` each ran `routeSweep.ts:sweepEveryRoute` on their own: the same routes,
 * the same store, three page loads of every screen, about 38s together. This file opens each screen
 * ONCE and runs all three measurements on it, so the checks still cannot disagree about which state
 * a screen was measured in, and the cost is one sweep. The sweep's header says what is NOT read (no
 * sheet, modal, popover, toast, drawer or palette; only `.bn-view`).
 *
 * EACH CHECK KEEPS ITS OWN MEASUREMENT (`moneyFace.ts`, `machineWords.ts`, `textShape.ts`), ITS OWN
 * SHRINKING PENDING LIST AND ITS OWN FINDINGS. A finding is named `[money-face]`, `[machine-words]`
 * or `[text-shape]`, and each check asserts its own list of problems apart from the others
 * (`expect.soft`), so one check going red never hides another's verdict.
 *
 *   money-face     D221. Every dollar figure draws in the mono face. Pending list
 *                  `money-face-allow.json`: route -> amount -> lane. The amount is the figure as drawn.
 *   machine-words  D196, D269. No decision id, repository path or pipeline noun in the rendered text.
 *                  Pending list `machine-words-allow.json`: route -> word or path (lower-cased) -> lane.
 *                  The word list is `scripts/machine-words.json`, read once here and by the Python row.
 *   text-shape     D284. No sentence repeated across cards, no fact stated twice, no sentence over 25
 *                  words, no caption that repeats its heading. Pending list `text-shape-allow.json`:
 *                  route -> assertion -> finding key -> lane. `make text-density` runs this file with
 *                  `TEXT_DENSITY=1`: only this check reads, and the receipt is written, nothing asserted.
 *
 * A PENDING ENTRY EXCUSES ONE FINDING AND NO OTHER, and an entry that matches nothing this run is
 * STALE and red until deleted, so every list only shrinks.
 *
 * THE MUTATION PROOF, one environment variable per check, each through `page.evaluate` and never an
 * edit under `app/src`. Set it to a route's hash; that route gets the check's own defect, and only
 * that check goes red. From `app/`:
 *   MONEY_FACE_MUTATE='#/shipping'   npx playwright test tests/text-checks.spec.ts   ($987.65 in Inter)
 *   MACHINE_WORDS_MUTATE='#/capture' npx playwright test tests/text-checks.spec.ts   (a machine word)
 *   TEXT_SHAPE_MUTATE='#/'           npx playwright test tests/text-checks.spec.ts   (one sentence on three cards)
 */

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..', '..')
const DENSITY_PATH = resolve(ROOT, '.serve', 'text-density.json')
const DENSITY = process.env.TEXT_DENSITY === '1'

/** route -> finding id -> lane. For text-shape the id is `<assertion> <key as JSON>`. */
type Allow = Record<string, Record<string, string>>

function readJson<T>(name: string): T {
  return JSON.parse(readFileSync(resolve(HERE, name), 'utf8')) as T
}

function readFlatAllow(name: string): Allow {
  const { _about, ...rest } = readJson<Allow & { _about?: string }>(name)
  void _about
  return rest
}

const TEXT_SHAPE_ASSERTIONS = ['repeated-sentence', 'repeated-fact', 'long-sentence', 'caption-heading'] as const
type TextShapeAssertion = (typeof TEXT_SHAPE_ASSERTIONS)[number]
type TextShapeAllow = Record<string, Partial<Record<TextShapeAssertion, Record<string, string>>>>

function readTextShapeAllow(): TextShapeAllow {
  const { _about, ...rest } = readJson<TextShapeAllow & { _about?: string }>('text-shape-allow.json')
  void _about
  return rest
}

/** The text-shape list, flattened to the other two lists' shape. */
function flattenTextShape(allow: TextShapeAllow): Allow {
  const flat: Allow = {}
  for (const [route, byAssertion] of Object.entries(allow)) {
    for (const [assertion, keys] of Object.entries(byAssertion)) {
      for (const [key, lane] of Object.entries(keys ?? {})) (flat[route] ??= {})[`${assertion} ${JSON.stringify(key)}`] = lane
    }
  }
  return flat
}

function readWords(): { words: Record<string, string>; repoTopDirs: string[] } {
  const raw = JSON.parse(readFileSync(resolve(ROOT, 'scripts/machine-words.json'), 'utf8')) as {
    words: Record<string, string>
    repoTopDirs: string[]
  }
  return { words: raw.words, repoTopDirs: raw.repoTopDirs }
}

/** What a check reports to the sweep: a finding with an id the pending list can name, or a
 *  problem no list may excuse. */
type Hit = (id: string, detail: string) => void
type Read = (route: string, width: number, hit: Hit, problem: (message: string) => void) => Promise<void>

interface Check {
  readonly name: string
  readonly mutateEnv: string
  readonly allow: Allow
  readonly inject: (page: Page) => Promise<void>
  readonly read: (page: Page) => Read
}

const density: Array<{ route: string; width: number } & TextShapeResult> = []

const CHECKS: readonly Check[] = [
  {
    name: 'money-face',
    mutateEnv: 'MONEY_FACE_MUTATE',
    allow: readFlatAllow('money-face-allow.json'),
    inject: (page) => page.evaluate(injectInterMoney),
    read: (page) => async (route, width, hit, problem) => {
      const result = await page.evaluate(scanMoneyFace)
      if (result.noView) {
        problem(`${route} at ${width}: the page drew no .bn-view, so no dollar figure was read. A screen with no view cannot be checked.`)
        return
      }
      for (const one of result.text) hit(one.amount, `at ${width}, drawn as "${one.fontFamily}" in "${one.sample}"`)
      for (const one of result.fields) hit(one.amount, `at ${width}, a <${one.tag}> field drawn as "${one.fontFamily}"`)
    },
  },
  {
    name: 'machine-words',
    mutateEnv: 'MACHINE_WORDS_MUTATE',
    allow: readFlatAllow('machine-words-allow.json'),
    inject: (page) => page.evaluate(injectMachineWord),
    read: (page) => {
      const dictionary = readWords()
      return async (_route, width, hit) => {
        const result = await page.evaluate(scanMachineWords, dictionary)
        for (const one of result.words) hit(one.word.toLowerCase(), `at ${width}, "${one.sample}"`)
        for (const one of result.paths) hit(one.path.toLowerCase(), `at ${width}, "${one.sample}"`)
      }
    },
  },
  {
    name: 'text-shape',
    mutateEnv: 'TEXT_SHAPE_MUTATE',
    allow: flattenTextShape(readTextShapeAllow()),
    inject: (page) => page.evaluate(injectRepeatedSentence),
    read: (page) => async (route, width, hit) => {
      const result = await page.evaluate(measureTextShape)
      if (DENSITY) {
        density.push({ route, width, ...result })
        return
      }
      const at = (assertion: TextShapeAssertion, key: string, detail: string): void =>
        hit(`${assertion} ${JSON.stringify(key)}`, `at ${width}, ${detail}`)
      for (const one of result.repeatedSentences) at('repeated-sentence', one.key, `on ${one.count} elements of class "${one.groupClass}"`)
      for (const one of result.repeatedFacts) at('repeated-fact', one.key, `stated in ${one.count} separate blocks`)
      for (const one of result.longSentences) at('long-sentence', one.key, `${one.words} words: "${one.sample}"`)
      for (const one of result.captionHeading) at('caption-heading', one.key, `repeats ${one.overlap}% of its heading "${one.heading}"`)
    },
  },
]

sealEveryTest({ store: true, cards: 122 })

test('one sweep: every route is read once by the money-face, machine-words and text-shape checks', async ({ page }) => {
  const live = DENSITY ? CHECKS.filter((check) => check.name === 'text-shape') : CHECKS
  const used = new Map<string, Set<string>>(live.map((check) => [check.name, new Set<string>()]))
  const problems = new Map<string, string[]>(live.map((check) => [check.name, []]))
  const reads = live.map((check) => ({ check, read: check.read(page) }))

  const swept = await sweepEveryRoute(page, async (route, width) => {
    for (const { check, read } of reads) {
      if (process.env[check.mutateEnv] === route) await check.inject(page)
      const found = problems.get(check.name) ?? []
      const hit: Hit = (id, detail) => {
        if (check.allow[route]?.[id] !== undefined) {
          used.get(check.name)?.add(`${route}\u0000${id}`)
          return
        }
        found.push(`[${check.name}] ${route} ${id}: ${detail}. Not on the pending list: fix it, or add a pending entry naming the lane that owes it.`)
      }
      await read(route, width, hit, (message) => found.push(`[${check.name}] ${message}`))
    }
  })

  // REPORT MODE (`make text-density`): write the receipt, assert nothing. D18: a pass that
  // writes never gates, and this mode is on no gate's path.
  if (DENSITY) {
    mkdirSync(dirname(DENSITY_PATH), { recursive: true })
    writeFileSync(DENSITY_PATH, `${JSON.stringify({ measured: density }, null, 2)}\n`)
    return
  }

  for (const check of live) {
    const found = problems.get(check.name) ?? []
    for (const [route, ids] of Object.entries(check.allow)) {
      for (const [id, lane] of Object.entries(ids)) {
        if (!swept.has(route)) {
          found.push(`[${check.name}] ${route} ${id}: pending for lane ${lane}, but that route was not swept. Delete the entry.`)
        } else if (used.get(check.name)?.has(`${route}\u0000${id}`) !== true) {
          found.push(`[${check.name}] ${route} ${id}: pending for lane ${lane}, but nothing matched it this run, so the pending entry is stale. Delete it.`)
        }
      }
    }
    expect.soft(found, found.join('\n')).toEqual([])
  }
})

test('the text-shape pending list names only real routes, real assertions and a lane', async ({ page }) => {
  await setViewport(page, { width: 1440, height: 1000 })
  const routes = await routesFromNav(page)
  const problems: string[] = []
  for (const [route, byAssertion] of Object.entries(readTextShapeAllow())) {
    if (!routes.includes(route) && route !== PRODUCT_ROUTE) problems.push(`${route}: not a route the sweep reads`)
    for (const [assertion, keys] of Object.entries(byAssertion)) {
      if (!(TEXT_SHAPE_ASSERTIONS as readonly string[]).includes(assertion)) problems.push(`${route} ${assertion}: not a real assertion`)
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

/* THE KIT'S OWN `Stat`, WHICH NO SWEEP READS (the PR 2 screen pass, D221). `#/gallery` is out of
 * the sweep (`routeExclusions.ts`), and no owner screen passes `Stat` a dollar figure today, so
 * the one place a money `Stat` is drawn is the kit sheet. `.bn-stat-value` sets the display face,
 * so a figure passed through `Stat` broke D221 by construction. `Stat`'s `money` prop takes the
 * mono face; this reads the gallery's own "$184 to list" specimen. */
test('a dollar figure drawn through the kit Stat is in the mono face', async ({ page }) => {
  await page.goto('/#/gallery')
  const stat = page.locator('.bn-stat', { hasText: 'to list' }).first()
  await stat.scrollIntoViewIfNeeded()
  const face = await stat.locator('.bn-stat-value').evaluate((el) => getComputedStyle(el).fontFamily)
  expect(face, `"$184 to list" drawn as "${face}"`).toContain('JetBrains Mono')
})

/* EVERY DOLLAR FIGURE ON THE KIT SHEET (the PR 2 delta review, D221). The sweep skips
 * `#/gallery`, and the Stat case above read one specimen, so the primary button's
 * "Push 12 listings, $184.20" sat in Inter unseen. This reads every dollar text node and money
 * field in the gallery's `.bn-view` through the sweep's own scanner. */
test('every dollar figure on the kit sheet is drawn in the mono face', async ({ page }) => {
  await page.goto('/#/gallery')
  await expect(page.locator('main.gallery')).toBeVisible()
  const result = await page.evaluate(scanMoneyFace)
  expect(result.noView, 'the kit sheet drew no .bn-view, so no dollar figure was read').toBe(false)
  const misses = [
    ...result.text.map((hit) => `'${hit.amount}' drawn as "${hit.fontFamily}" in "${hit.sample}"`),
    ...result.fields.map((hit) => `'${hit.amount}' in a <${hit.tag}> drawn as "${hit.fontFamily}"`),
  ]
  expect(misses, misses.join('\n')).toEqual([])
})
