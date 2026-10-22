// Protects: a refusal the send press can raise before TCGplayer is asked never reads as "TCGplayer did not take the send".
// Governs: outcomes first (CLAUDE.md); server/send_routes.do_send
import { readFileSync } from 'node:fs'
import { expect, test } from './unit'

const read = (path: string): string => readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

/* Every code the press raises on this side of TCGplayer. The tcg_* codes and step_timed_out come
   from the far side, so the default line is true for them and they are not listed. */
const OURS = [
  'runs_required', 'too_many_runs', 'confirm_required', 'prices_invalid', 'moves_invalid',
  'run_name_invalid', 'no_such_run', 'claim_unreadable', 'send_busy', 'not_sendable', 'write_split',
  'needs_price', 'under_cut_off', 'nothing_to_send', 'price_refused',
]

test('every refusal the press raises before TCGplayer has its own sentence', () => {
  const card = read('src/SendCard.tsx')
  for (const code of OURS) {
    expect(card.includes(`case '${code}'`), `${code} falls through to the TCGplayer line`).toBe(true)
  }
})
