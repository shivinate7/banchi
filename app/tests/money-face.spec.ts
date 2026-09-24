import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '@playwright/test'

import { sealEveryTest } from './shell'
import { sweepEveryRoute } from './routeSweep'
import { injectInterMoney, scanMoneyFace } from './moneyFace'

/* D221 — MONEY STAYS MONO, EVERYWHERE. Owned by the text-checks lane on the orchestrator's own
 * assignment: "the rendered-page money check". It reads rendered text the same way
 * `machine-words.spec.ts` does. See `moneyFace.ts` for what is measured and why
 * `getComputedStyle` rather than a class-name check.
 *
 * THE SWEEP IS `routeSweep.ts:sweepEveryRoute`, shared with the other two text checks: every
 * route at 1440 and 390, every seed registered once, each screen read only once it is loaded.
 * Its header says what is NOT read (no sheet, modal, toast, drawer or palette; only
 * `.bn-view`). The fixture is deterministic, so a route draws the same amounts every run.
 *
 * A SHRINKING PENDING LIST, `money-face-allow.json`: route -> amount -> lane. The amount is
 * the figure exactly as the screen draws it (`$3.31`, `$50`, or a field's value), so a listed
 * entry excuses that one figure and no other: a NEW figure drawn in the wrong face on a listed
 * route is red. A listed entry that matches nothing is stale, and red until it is deleted.
 *
 * THE MUTATION PROOF (`MONEY_FACE_MUTATE=<hash>`) is `moneyFace.ts:injectInterMoney`: a
 * `$987.65` drawn in Inter, through `page.evaluate`, never an edit under `app/src`. From
 * `app/`, `MONEY_FACE_MUTATE='#/shipping' npx playwright test tests/money-face.spec.ts` fails
 * on a route that already has amounts listed, naming `$987.65`.
 */

const HERE = dirname(fileURLToPath(import.meta.url))
const ALLOW_PATH = resolve(HERE, 'money-face-allow.json')

/** route -> amount -> lane. */
type Allow = Record<string, Record<string, string>>

function readAllow(): Allow {
  const raw = JSON.parse(readFileSync(ALLOW_PATH, 'utf8')) as Allow & { _about?: string }
  const { _about, ...rest } = raw
  return rest
}

const MUTATE_ROUTE = process.env.MONEY_FACE_MUTATE ?? ''

sealEveryTest({ store: true, cards: 122 })

test('every visible dollar figure on every route is drawn in the mono face', async ({ page }) => {
  const ALLOW = readAllow()
  const used = new Set<string>()
  const problems: string[] = []

  function report(route: string, amount: string, detail: string, width: number): void {
    if (ALLOW[route]?.[amount] !== undefined) {
      used.add(`${route}\u0000${amount}`)
      return
    }
    problems.push(
      `${route}: '${amount}' at ${width} — ${detail}. Not on the pending list: draw it in .bn-money, or add a pending entry naming the lane that owes it.`,
    )
  }

  const swept = await sweepEveryRoute(page, async (route, width) => {
    if (MUTATE_ROUTE !== '' && MUTATE_ROUTE === route) await page.evaluate(injectInterMoney)
    const result = await page.evaluate(scanMoneyFace)
    for (const hit of result.text) {
      report(route, hit.amount, `drawn as "${hit.fontFamily}" in "${hit.sample}"`, width)
    }
    for (const hit of result.fields) {
      report(route, hit.amount, `a <${hit.tag}> field drawn as "${hit.fontFamily}"`, width)
    }
  })

  for (const [route, amounts] of Object.entries(ALLOW)) {
    for (const [amount, lane] of Object.entries(amounts)) {
      if (!swept.has(route)) {
        problems.push(`${route} ${amount}: pending for lane ${lane}, but that route was not swept. Delete the entry.`)
      } else if (!used.has(`${route}\u0000${amount}`)) {
        problems.push(
          `${route} ${amount}: pending for lane ${lane}, but nothing matched it this run — the pending entry is stale. Delete it.`,
        )
      }
    }
  }

  expect(problems, problems.join('\n')).toEqual([])
})
