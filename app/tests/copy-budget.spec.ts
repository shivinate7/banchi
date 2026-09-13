import { test, expect } from '@playwright/test'
import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { settleFonts } from './fontsReady'
import { routesFromNav } from './routes'
import { sealEveryTest } from './shell'

/* THE VISIBLE WORD COUNT ON EVERY OWNER SCREEN MAY ONLY GO DOWN (`D194`).
 *
 * The owner's ruling, 2026-09-13: "less text is always better than more." Several sessions
 * are cutting copy across every screen at once right now, on that word alone — and a rule
 * with no reader is advice, the same failure `D196` and
 * `D195` both name for their own owner's rulings. That row asserts the
 * CONTENT of a string (`scripts/user-strings.mjs`'s AST walk plus `NO_MECHANISM_WORDS`); this
 * one is deliberately blind to content and asserts only its VOLUME — the number of visible
 * words a route draws, never which words they are, because a session rewording a sentence to
 * mean the same thing in fewer words is exactly the behaviour this ratchet exists to reward,
 * and a content-aware guard would have opinions about the rewrite this one does not need.
 *
 * A RATCHET, NOT A CEILING SOMEONE PICKED. `app/tests/copy-budget.json` maps route to the
 * MEASURED word count on this tree the day it was pinned — no slack, because slack is how a
 * ratchet leaks: a ceiling padded "for safety" is headroom a later session spends without
 * ever being asked to. The only way a ceiling rises is `node scripts/copy-budget.mjs --pin`,
 * run by a human who is choosing to let an addition through, and the failure message below
 * says so in those words rather than leaving it to be rediscovered.
 *
 * THE REGION COUNTED IS `.bn-view` — App.tsx's own wrapper around `<route.view />` and
 * nothing else: not `.bn-side` (the sidebar/rail), not `.bn-topbar`/`.bn-tabbar` (the phone
 * chrome), not the banner, the drawer, the palette, the keys sheet or the toaster, all of
 * which are siblings of `.bn-view` inside `.bn-shell-main` or the shell root and never inside
 * it. That is a structural fact read off `App.tsx`, not a selector chosen to make the numbers
 * come out right — it is the same region every screen renders through and the only one that
 * changes when a screen's OWN copy is cut.
 *
 * ROUTES ARE DISCOVERED, THE SAME ARGUMENT `routesFromNav`, `cursor.spec.ts`, `wide.spec.ts`,
 * `button-stack.spec.ts` and `page-edge.spec.ts` all make already: a hand-typed roster goes
 * stale by going green. `#/fulfillment` is excluded — a persona this rule was not written for,
 * `docs/DESIGN.md`'s own Fulfillment floors govern his screen and this file does not reach for
 * a second authority over it.
 *
 * THE FIXTURE IS `sealEveryTest({ store: true, cards: 122 })` — `wide.spec.ts` and
 * `phone.spec.ts`'s own choice for a cross-route sweep, and the same small populated store
 * `cursor.spec.ts` reads to sweep every route, owner and Fulfiller alike, without a screen
 * rendering an empty state it would otherwise never draw a control in. It is NOT a bespoke
 * fixture per route — `#/runs`, `#/orders`, `#/shipping`, `#/codes` and `#/graveyard` see no
 * run, no order, no export and no departed record of their own, so their pinned ceilings are
 * ceilings on an EMPTY-ISH state for those screens rather than the busiest one a real store
 * would draw. That is a real gap and it is named in the wrap-up rather than argued away here:
 * closing it needs the same per-screen fixtures `cursor.spec.ts`'s own header already asks
 * for, and a route whose ceiling is pinned too low from an empty state will need a wider one
 * the day a fixture gives it real rows — which is `--pin`'s job, not a reason to leave this
 * unbuilt.
 *
 * TWO ENV VARS, BOTH READ HERE AND NOWHERE ELSE, SO THE TWO PATHS CANNOT DRIFT:
 *
 * `COPY_BUDGET_PIN=1` makes this file WRITE `copy-budget.json` from the counts it just
 * measured instead of asserting them — `scripts/copy-budget.mjs --pin` sets it and runs this
 * spec. The measuring code is the same in both modes; only what happens to the number differs.
 *
 * `COPY_BUDGET_MUTATE=<hash>` (e.g. `#/pricing`) injects a 30-plus-word sentence into that
 * route's `.bn-view` before it is measured, by `page.evaluate` — never by editing a file under
 * `app/src`, which this task is not permitted to touch. It exists for the mutation proof: run
 * `COPY_BUDGET_MUTATE='#/pricing' npx playwright test tests/copy-budget.spec.ts` from `app/`
 * and the spec fails, naming exactly that route.
 *
 * NOT A HARNESS TEST. `make design-check` runs it, the same as every other file in this
 * directory — this is a browser assertion over rendered copy, not one of the nine Python
 * tests `docs/GATES.md`'s contract names.
 */

const HERE = dirname(fileURLToPath(import.meta.url))
const CEILINGS_PATH = join(HERE, 'copy-budget.json')

const PIN = process.env.COPY_BUDGET_PIN === '1'
const MUTATE_ROUTE = process.env.COPY_BUDGET_MUTATE ?? ''

/* THE ONE COUNTING RULE, so the pin path and the assert path can never disagree about what a
 * "word" is. Split on whitespace, then drop any token carrying no letter — a bare number, a
 * currency figure, a lone dash or bullet, a card number's slash-shape. A token that MIXES a
 * letter with digits or punctuation (a SKU, a set code) still counts as one word, on the same
 * theory `docs/DESIGN.md`'s Copy rules already applies to reading: it is a word a person reads,
 * whatever else is folded into it. */
function countWords(text: string): number {
  return text
    .split(/\s+/)
    .map((token) => token.trim())
    .filter((token) => token.length > 0 && /[A-Za-z]/.test(token)).length
}

function readCeilings(): Record<string, number> {
  try {
    return JSON.parse(readFileSync(CEILINGS_PATH, 'utf8')) as Record<string, number>
  } catch {
    return {}
  }
}

/* A ROUTE ARRIVING (`<main>` visible) IS NOT A ROUTE LOADED. Several screens paint a real
 * `<main>` — "Reading the inventory…" — before their async store read resolves, the same gap
 * `routesFromNav`'s own header separates from a crashed screen: emptiness and breakage are
 * different facts, and this file cares about neither, only about whether the count it takes is
 * the FINAL one. Measured: `#/inventory` read as low as 4 words mid-load and 156 once painted,
 * both under one `toBeVisible()`. So this waits for `.bn-view`'s own text to stop changing —
 * two reads `quietMs` apart agreeing — rather than trusting one read taken the instant the
 * element exists. Generic on purpose: every route gets the same wait, never a per-screen
 * loading-string this file would have to keep in step with eleven screens' own copy. */
async function stableInnerText(
  region: import('@playwright/test').Locator,
  timeoutMs = 4000,
  quietMs = 150,
): Promise<string> {
  const deadline = Date.now() + timeoutMs
  let previous = await region.innerText()
  while (Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, quietMs))
    const next = await region.innerText()
    if (next === previous) return next
    previous = next
  }
  return previous
}

sealEveryTest({ store: true, cards: 122 })

test('the visible word count on every owner screen may only go down', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })

  const routes = (await routesFromNav(page)).filter((route) => route !== '#/fulfillment')
  expect(routes.length, 'the route harvest returned too few screens to budget').toBeGreaterThan(6)

  const counts: Record<string, number> = {}

  for (const route of routes) {
    await page.goto(`/${route}`)
    await settleFonts(page)
    await expect(page.locator('main').first(), `${route}: drew no <main>`).toBeVisible()

    if (MUTATE_ROUTE !== '' && MUTATE_ROUTE === route) {
      await page.evaluate(() => {
        const host = document.querySelector('.bn-view') ?? document.body
        const sentence = document.createElement('p')
        sentence.textContent =
          'This sentence exists only to prove the ratchet catches an addition of thirty or ' +
          'more words landing on one screen without anybody choosing to re-pin the budget on ' +
          'purpose which is exactly what a ratchet nobody ever reads would silently allow to ' +
          'pass unnoticed forever.'
        host.appendChild(sentence)
      })
    }

    const region = page.locator('.bn-view')
    await expect(region, `${route}: no .bn-view to count`).toHaveCount(1)
    const text = await stableInnerText(region)
    counts[route] = countWords(text)
  }

  if (PIN) {
    writeFileSync(CEILINGS_PATH, `${JSON.stringify(counts, null, 2)}\n`)
    return
  }

  const ceilings = readCeilings()
  const overages: string[] = []
  for (const route of routes) {
    const ceiling = ceilings[route]
    if (ceiling === undefined) {
      overages.push(
        `${route}: no ceiling pinned — run \`node scripts/copy-budget.mjs --pin\` first`,
      )
      continue
    }
    const count = counts[route] ?? 0
    if (count > ceiling) {
      overages.push(
        `${route}: ${count} words against a ceiling of ${ceiling} — copy may only go ` +
          'down — re-pin with `node scripts/copy-budget.mjs --pin` if the addition was ruled ' +
          'worth its words',
      )
    }
  }

  expect(overages, overages.join('\n')).toEqual([])
})
