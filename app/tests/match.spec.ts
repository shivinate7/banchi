import { test, expect } from '@playwright/test'

import { sealEveryTest } from './shell'
import { matchQuery, filterByQuery, type MatchFields } from '../src/kit/match'
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

/* R6, round-4 Opus review, 2026-09-25: a test that goes red if `cover`'s own memoization
 * (F1, round-3) is lost. Mirrors `scripts/match-selftest.py:
 * case_match_query_stays_fast_on_repeated_tokens` exactly — the same hostile query and the
 * same card, so both implementations of the one matcher are held to the same shape of
 * proof. Un-memoized, `cover` tries the single-token AND the pair branch at every position,
 * and each branch recurses into the rest of the tokens: the same position is solved again
 * from scratch by every path that reaches it, growing like Fibonacci. A bound generous
 * enough to survive a slow CI runner, nowhere near the un-memoized cost, so a regression
 * here fails LOUD rather than merely slow. */
test('cover stays fast on 27 repeated tokens (memo regression)', () => {
  const fields: MatchFields = { numbers: ['132/132'] }
  const query = '132 '.repeat(27) + '/132 /999'
  const start = Date.now()
  const result = matchQuery(query, fields)
  const took = Date.now() - start
  expect(result, "27 repeated '132' tokens plus two unmatched ones do not cover").toBe(false)
  expect(took, `cover took ${took}ms, over the 1000ms bound (un-memoized: seconds)`).toBeLessThan(1000)
  /* filterByQuery threads the same memo per row, never across rows — proven by running the
   * hostile query over several rows and staying fast in total, not only once. */
  const rows = Array.from({ length: 5 }, () => fields)
  const filterStart = Date.now()
  const matched = filterByQuery(rows, query, (row) => row)
  const filterTook = Date.now() - filterStart
  expect(matched.length).toBe(0)
  expect(filterTook, `filterByQuery over 5 rows took ${filterTook}ms`).toBeLessThan(1000)
})
