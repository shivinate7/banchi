import { test, expect } from '@playwright/test'

import { sealEveryTest } from './shell'
import { matchQuery, type MatchFields } from '../src/kit/match'
/* An IMPORT ATTRIBUTE, not only `resolveJsonModule`: Node's own ESM loader (this repo's
 * Playwright runs on Node 25) refuses a bare `import … from '*.json'` at runtime, whatever
 * TypeScript's own module resolution allows for the type check. */
import cases from '../src/kit/match.cases.json' with { type: 'json' }

/* THE MATCHER'S OWN CASE TABLE, RUN DATA-DRIVEN (the addendum's "Done" line: "match.spec passes
 * every row of match.cases.json"). `kit-data.spec.ts` already carries `matchQuery`'s
 * hand-written, narrated tests — this file is the other half: a case table anything else that
 * must agree with the one matcher can read and run too, `search-server`'s Python candidate step
 * among them. Runs no browser: `matchQuery` is a pure function. */

sealEveryTest()

type Case = {
  readonly note: string
  readonly query: string
  readonly fields: MatchFields
  readonly match: boolean
}

const CASES = cases as readonly Case[]

test('the case table is not empty, and covers both a hit and a miss', () => {
  expect(CASES.length).toBeGreaterThan(20)
  expect(CASES.some((one) => one.match)).toBe(true)
  expect(CASES.some((one) => !one.match)).toBe(true)
})

for (const [at, one] of CASES.entries()) {
  test(`case ${at + 1}: ${one.note}`, () => {
    expect(matchQuery(one.query, one.fields), JSON.stringify(one)).toBe(one.match)
  })
}
