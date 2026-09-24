import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '@playwright/test'

import { sealEveryTest } from './shell'
import { sweepEveryRoute } from './routeSweep'
import { injectMachineWord, scanMachineWords } from './machineWords'

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
 * THE SWEEP IS `routeSweep.ts:sweepEveryRoute`, shared with `text-shape.spec.ts` and
 * `money-face.spec.ts`: every route at 1440 and 390, every seed registered once, each screen
 * read only once it is loaded. Its header says what is NOT read (no sheet, modal, toast,
 * drawer or palette; only `.bn-view`).
 *
 * A SHRINKING PENDING LIST, `machine-words-allow.json`: route -> word or path (lower-cased)
 * -> lane. Keyed by ROUTE, not by file, because rendered text carries no source file. There is
 * no wildcard route: the fixture is deterministic, so every hit lands on the same route every
 * run. A NEW word on a listed route is red. A listed entry that matches nothing is stale, and
 * red until it is deleted.
 *
 * THE MUTATION PROOF (`MACHINE_WORDS_MUTATE=<hash>`) is `machineWords.ts:injectMachineWord`,
 * through `page.evaluate`, never an edit under `app/src`. From `app/`,
 * `MACHINE_WORDS_MUTATE='#/capture' npx playwright test tests/machine-words.spec.ts` fails on
 * a route that already has entries listed, naming the injected word.
 */

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..', '..')
const ALLOW_PATH = resolve(HERE, 'machine-words-allow.json')
const WORDS_PATH = resolve(ROOT, 'scripts/machine-words.json')

/** route -> word or path (lower-cased) -> lane. */
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

const MUTATE_ROUTE = process.env.MACHINE_WORDS_MUTATE ?? ''

sealEveryTest({ store: true, cards: 122 })

test('no route draws a machine word or a request path where the owner reads it', async ({ page }) => {
  const ALLOW = readAllow()
  const dictionary = readWords()
  const used = new Set<string>()
  const problems: string[] = []

  function report(route: string, term: string, sample: string, width: number): void {
    if (ALLOW[route]?.[term] !== undefined) {
      used.add(`${route}\u0000${term}`)
      return
    }
    problems.push(
      `${route}: '${term}' at ${width} — "${sample}". Not on the pending list: fix it, or add a pending entry naming the lane that owes it.`,
    )
  }

  const swept = await sweepEveryRoute(page, async (route, width) => {
    if (MUTATE_ROUTE !== '' && MUTATE_ROUTE === route) await page.evaluate(injectMachineWord)
    const result = await page.evaluate(scanMachineWords, dictionary)
    for (const hit of result.words) report(route, hit.word.toLowerCase(), hit.sample, width)
    for (const hit of result.paths) report(route, hit.path.toLowerCase(), hit.sample, width)
  })

  for (const [route, terms] of Object.entries(ALLOW)) {
    for (const [term, lane] of Object.entries(terms)) {
      if (!swept.has(route)) {
        problems.push(`${route} ${term}: pending for lane ${lane}, but that route was not swept. Delete the entry.`)
      } else if (!used.has(`${route}\u0000${term}`)) {
        problems.push(
          `${route} ${term}: pending for lane ${lane}, but nothing matched it this run — the pending entry is stale. Delete it.`,
        )
      }
    }
  }

  expect(problems, problems.join('\n')).toEqual([])
})
