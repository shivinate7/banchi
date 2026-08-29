/* THE SCOPE A RUN IS STARTED OVER, CARRIED BETWEEN TWO SCREENS — and this module exists
 * because the runs left `#/inventory` on 2026-08-29 (D39) and their scope did not follow on its own.
 *
 * WHAT BROKE WHEN THE PANEL MOVED. `RunPanel` gates its spend on `scope.box !== null`, and
 * until the move that box came from `BoxBrowse`'s own walk: the box strip picked it, the
 * section ticks narrowed it, and `Inventory.tsx` passed the pair straight down. D33 spent a
 * paragraph on why that was right — "a route of its own would have to re-implement the box
 * strip, the search and the mass-select, and would then be free to disagree with them about
 * what is selected" — and the owner moved the panel anyway. So the box is re-answered on
 * `#/runs` by a picker of its own, which is cheap and honest, and the SELECTION is not: there
 * is no second mass-select, and building one would be the disagreement D33 named.
 *
 * SO THE SELECTION IS HANDED OVER RATHER THAN REBUILT. `#/inventory` keeps the one mass-select
 * in the product; when the operator has cards ticked it offers to run them, writes the pair
 * here, and sends them to `#/runs`, which draws what it was handed and says where it came
 * from. One selection, one owner, and the two screens cannot disagree about it because only
 * one of them can produce one.
 *
 * `sessionStorage`, WHICH IS D27's CARVE-OUT AND NOT A NEW ONE. That entry opens session
 * storage to state that is "device-local and meaningless anywhere else", against `CLAUDE.md`'s
 * ban on browser storage — a ban D13 imposes so that two devices cannot disagree about where a
 * card IS. A set of ticked indices is not where a card is; it is what this browser was pointing
 * at a moment ago, and the Fulfiller's device has no opinion about it. It is also exactly the
 * shape D27 already permits for the capture screen's in-flight state, down to the reason: a
 * reload during the handoff would otherwise lose the selection with nothing on screen to say
 * a selection had ever existed.
 *
 * IT IS NOT CLEARED BY BEING READ. `#/runs` polls, an identify run takes minutes to hours, and
 * a reload mid-run is an ordinary thing to do — a read-once handoff would drop the operator
 * from "36 ticked cards" to "the whole box" silently, which is a change to what the next press
 * spends money on. It is cleared by the operator, by picking a different box, and by nothing
 * else.
 *
 * IT FALLS THROUGH RATHER THAN GUESSING, which is D3 rung 0's rule applied one register down.
 * Anything unparseable, wrong-shaped, or naming a box the registry no longer holds is dropped
 * whole and the screen behaves as though nothing had been handed over. A half-read handoff
 * would put a run over a box the operator did not choose.
 */

/** A box, and the cards ticked inside it. Never an empty `indices` — a handoff that carries no
 *  selection is the whole box, which is what picking a box on `#/runs` already means, so the
 *  writer refuses to make one and there is no second spelling of the same scope. */
export type CarriedScope = {
  readonly box: number
  readonly indices: readonly number[]
}

/** THE ONE KEY, NAMED HERE AND NOWHERE ELSE. D27 requires the permitted keys to be nameable so
 *  that a lint rule could enforce the boundary; `app/eslint.config.js` bans `localStorage` by
 *  selector and cannot see a key string, so the defence for this one is that it is declared
 *  once and every reader and writer in the app goes through the three functions below. */
const KEY = 'pkmnscan.run-scope'

/** Reads whatever is stored, or `null`. `window.sessionStorage` throws in a browser with
 *  storage disabled, so the access is guarded: the handoff is a convenience and losing it is
 *  never a reason to take the screen down. */
function read(): unknown {
  try {
    const raw = window.sessionStorage.getItem(KEY)
    return raw === null ? null : (JSON.parse(raw) as unknown)
  } catch {
    return null
  }
}

/** The carried scope, validated, or `null` when there is none to carry.
 *
 *  VALIDATED FIELD BY FIELD rather than cast. What comes back is a string this browser wrote,
 *  which is exactly the argument for trusting it and exactly why it is not trusted: the writer
 *  may be an older build of this app whose shape has since moved, and the cost of reading a
 *  stale shape is a run over the wrong cards. Indices are filtered to positive integers and
 *  deduplicated, because `server/pipeline_routes.py` builds a symlink directory out of them. */
export function carriedScope(): CarriedScope | null {
  const value = read()
  if (value === null || typeof value !== 'object') return null
  const record = value as Record<string, unknown>
  const box = record.box
  if (typeof box !== 'number' || !Number.isInteger(box) || box < 1) return null
  if (!Array.isArray(record.indices)) return null
  const indices = [
    ...new Set(
      record.indices.filter(
        (index): index is number => typeof index === 'number' && Number.isInteger(index) && index > 0,
      ),
    ),
  ].sort((a, b) => a - b)
  if (indices.length === 0) return null
  return { box, indices }
}

/** Hands a selection to `#/runs`. Refuses an empty selection for the reason `CarriedScope`
 *  gives — the whole box is not a handoff, it is what the picker already says. */
export function carryScope(scope: CarriedScope): void {
  if (scope.indices.length === 0) return
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify({ box: scope.box, indices: [...scope.indices] }))
  } catch {
    /* Storage refused. The screen still navigates and still draws the whole box, which is the
       wider scope rather than a wrong one — the operator sees `the whole box` on the header and
       can tick again. Silently narrowing would be the dangerous direction. */
  }
}

/** Drops the handoff. Called by the operator's own Clear, and by picking another box. */
export function clearCarriedScope(): void {
  try {
    window.sessionStorage.removeItem(KEY)
  } catch {
    /* Nothing to do and nothing to report: a handoff that cannot be removed cannot have been
       written either, since both go through this module. */
  }
}
