// Protects: a refusal the send press can raise before TCGplayer is asked never reads as "TCGplayer did not take the send".
// Governs: outcomes first (CLAUDE.md); server/send_routes.do_send
import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'

import { expect, test } from './unit'
import { lifted } from './lifted'

/* `refusalTitle` IS NOT EXPORTED, and exporting it is a product edit. So the unit tier asks the
 * language's own parser for the function, strips its types and runs it, and the cases check what
 * it SAYS. A text search for `case '<code>'` passes when the label sits in a comment, in a string
 * or in the other switch. The parser reads past comment openers inside strings, a multi-line
 * template literal and a lone quote in JSX text; the decoy case below pins that. The names it
 * reaches outside itself are lifted by the same parser from the file that declares them, so a case
 * runs the product's own code and words: the save code and its sentence come from server.ts.
 * `emptySendTitle` is the one name stubbed: no case here passes `data`, so the stub is never
 * called. Any other outside name throws a ReferenceError when a case calls the function. */
function functionNamed(source: string, name: string, outside: string[] = []): (code: string, data?: unknown) => string {
  const js = lifted(source, name, 'function')
  const emptySendTitle = (): never => { throw new Error('emptySendTitle is outside this check') }
  return runInNewContext(`${outside.join('\n')}\n${js}\n${name}`, { emptySendTitle }) as (code: string, data?: unknown) => string
}

const SERVER = readFileSync(new URL('../../src/server.ts', import.meta.url), 'utf8')
const SAVE_CODE_JS = lifted(SERVER, 'UNCONFIRMED_SAVE_CODE', 'const')
const SAVE_SENTENCE_JS = [lifted(SERVER, 'unconfirmedLine', 'function'), lifted(SERVER, 'unconfirmedPriceSaveAtSend', 'function')]
const SAVE_CODE = runInNewContext(`${SAVE_CODE_JS}\nUNCONFIRMED_SAVE_CODE`) as string

const refusalTitle = functionNamed(
  readFileSync(new URL('../../src/SendCard.tsx', import.meta.url), 'utf8'),
  'refusalTitle',
  [SAVE_CODE_JS, ...SAVE_SENTENCE_JS],
)

const TCG_LINE = 'TCGplayer did not take the send'
const UNKNOWN = 'zz_not_a_code'

/* Every code the press raises on this side of TCGplayer. `step_timed_out` and `banchi_missing`
   come from Banchi's own step (server/pipeline_routes), so they are listed too. Only the tcg_*
   codes come from the far side. */
const OURS = [
  'runs_required', 'too_many_runs', 'confirm_required', 'prices_invalid', 'moves_invalid',
  'run_name_invalid', 'no_such_run', 'claim_unreadable', 'send_busy', 'not_sendable', 'write_split',
  'needs_price', 'under_cut_off', 'nothing_to_send', 'price_refused',
  'step_timed_out', 'banchi_missing',
]

test('every refusal the press raises before TCGplayer has its own sentence', () => {
  const fallback = refusalTitle(UNKNOWN)
  for (const code of OURS) {
    const title = refusalTitle(code)
    expect(title, `${code} reads as the TCGplayer line`).not.toContain(TCG_LINE)
    expect(title, `${code} falls through to the default`).not.toBe(fallback)
  }
})

test('a send refused after an unanswered price save names that save in the server\'s own sentence', () => {
  expect(refusalTitle(SAVE_CODE), 'the save that got no answer has its own sentence').toBe(
    'The store did not confirm your last price save. Change the field to save it again before you send.',
  )
})

test('a Banchi failure is worded as Banchi\'s, and a timeout does not say nothing is live', () => {
  for (const code of ['step_timed_out', 'banchi_missing']) {
    expect(refusalTitle(code), code).toMatch(/^Banchi/)
  }
  expect(refusalTitle('step_timed_out')).not.toMatch(/nothing is live|nothing was sent/i)
})

test('a code nobody named gets a neutral line, and a tcg_ code keeps the TCGplayer line', () => {
  expect(refusalTitle(UNKNOWN)).not.toContain('TCGplayer')
  for (const code of ['tcg_write_refused', 'tcg_write_unreadable', 'tcg_session_expired', 'tcg_unreachable']) {
    expect(refusalTitle(code), code).toContain(TCG_LINE)
  }
})

test('the reader finds the real function past comment openers in strings, a template literal and a lone quote', () => {
  const decoy = [
    "// function refusalTitle(code) { return 'line comment' }",
    "/* function refusalTitle(code) { return 'block comment' } */",
    'const note = `',
    "function refusalTitle(code) { return 'template' }",
    '`',
    'function refusalTitle(code: string): string {',
    `  const a = '// not a comment', b = "/* not a block"`,
    `  return code === 'x' ? a + b + "*/" : 'real'`,
    '}',
    "export const Tip = () => <p>Don't</p>",
  ].join('\n')
  const read = functionNamed(decoy, 'refusalTitle')
  expect(read('x')).toBe('// not a comment/* not a block*/')
  expect(read('y')).toBe('real')
  expect(() => functionNamed('const refusalTitle = 1', 'refusalTitle')).toThrow(/found 0/)
})
