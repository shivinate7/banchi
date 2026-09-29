// Protects: The one search matcher passes every row of the shared case table and stays fast on a large list.
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
 * from scratch by every path that reaches it, growing like Fibonacci.
 *
 * TIGHTENED, F4 (round-5 Opus delta review, 2026-09-25): the review's own complaint was
 * that a 1000ms bound never goes red on a fast runner — a memoized pass here measures
 * 60-80ms, and CI has plenty of room to still pass at 1000ms even with the memo gone,
 * just slower. `cover` is a module-private function with no exported hook to count its
 * own calls without changing production code for a test's sake, so the fix is the
 * ALTERNATIVE the review names: a MUCH LARGER hostile query (60 repeated tokens, not 27),
 * which keeps the MEMOIZED cost linear and still fast (measured under 40ms), while the
 * UN-MEMOIZED cost grows exponentially from there — 27 tokens alone measured 4.5s
 * un-memoized; 60 is far beyond what any un-memoized run finishes before a reasonable
 * timeout. A 150ms bound is generous against the memoized cost and nowhere near reachable
 * without the memo, on a slow CI runner or a fast one alike. */
test('cover stays fast on 60 repeated tokens (memo regression)', () => {
  const fields: MatchFields = { numbers: ['132/132'] }
  const query = '132 '.repeat(60) + '/132 /999'
  const start = Date.now()
  const result = matchQuery(query, fields)
  const took = Date.now() - start
  expect(result, "60 repeated '132' tokens plus two unmatched ones do not cover").toBe(false)
  expect(took, `cover took ${took}ms, over the 150ms bound (un-memoized: never finishes in a reasonable time at this size)`).toBeLessThan(150)
  /* filterByQuery threads the same memo per row, never across rows — proven by running the
   * hostile query over several rows and staying fast in total, not only once. */
  const rows = Array.from({ length: 5 }, () => fields)
  const filterStart = Date.now()
  const matched = filterByQuery(rows, query, (row) => row)
  const filterTook = Date.now() - filterStart
  expect(matched.length).toBe(0)
  expect(filterTook, `filterByQuery over 5 rows took ${filterTook}ms`).toBeLessThan(150)
})

/* LANE F11b, rule 8: `raw` is a plain, case-folded substring, with none of rule 7's word
 * rules. A code-card code such as `PROMO1234XY` is one unbroken alphanumeric run, so its
 * middle digits are never a "word" of their own — rule 7's digit test only finds the START
 * of a digit-only word, and `234` here starts nothing. `raw` still finds it. */
test('raw finds a digit run in the middle of a code (Codes, F11b)', () => {
  const fields: MatchFields = { raw: ['PROMO1234XY'] }
  expect(matchQuery('234', fields)).toBe(true)
  // The same digit run through `text` instead of `raw` does not match (rule 7's own limit).
  expect(matchQuery('234', { text: ['PROMO1234XY'] })).toBe(false)
})

/* F11c: rule 4's `/`-prefix guard must run BEFORE `raw` gets a turn. `/19` names the
 * SECOND PART of a card number (`numberMatch`'s own reading). A `raw` field holding `19`
 * (a code, a key cap) must never answer for it — `rawSubstringMatch` used to run first,
 * so a `raw` row with no matching card number still matched on the plain substring. */
test('a leading slash never falls through to raw (F11c)', () => {
  expect(matchQuery('/19', { raw: ['19'] })).toBe(false)
  // The same query still finds a real card number whose second part is 19.
  expect(matchQuery('/19', { numbers: ['4/19'] })).toBe(true)
})
