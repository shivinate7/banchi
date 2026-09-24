/* MATCHING RUNS BY ITSELF WHEN A READING FINISHES (flow interview, Q4).
 *
 * The owner's ruling: a finished reading is matched to TCGplayer with nobody pressing anything,
 * and a problem becomes the run's next step. No server job runs unattended (Q3's rule for the
 * live check, applied here), so the cue is a screen SEEING a run that waits for its match:
 * `#/runs` on every read of its list, and Home on a visit — the same two halves Q3 rules, for
 * a reading that finished while the app was open and one that finished while it was closed.
 *
 * ONCE PER RUN PER SITTING. `asked` is module-level so a remount, a second screen or the next
 * poll never asks twice. A run whose last match stopped carries `match_problem` and is skipped
 * here: the server records the problem, and only the door's own press ("Try again") asks
 * TCGplayer again over it. */

import { matchRun } from './server'
import type { RunSummary } from './types'

const asked = new Set<string>()

/** Match every run in `runs` that waits for its match and has not been asked this sitting.
 *  Resolves true when at least one was asked, so the caller knows to read the list again. A
 *  refused call is not retried here: the run's next read says what happened. */
export async function matchWaiting(runs: readonly RunSummary[]): Promise<boolean> {
  const waiting = runs.filter(
    (row) => row.phase === 'join' && !row.live && row.match_problem == null && !asked.has(row.run),
  )
  for (const row of waiting) asked.add(row.run)
  for (const row of waiting) {
    try {
      await matchRun(row.run)
    } catch {
      /* The row says what happened on its next read. */
    }
  }
  return waiting.length > 0
}
