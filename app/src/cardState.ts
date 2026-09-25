/* CARD-STATE VOCABULARY AND THE AGE OF A READING — no component in it.
 *
 * SPLIT OUT SO `CardLocations.tsx` CAN HOT-RELOAD. React Refresh only updates a module in
 * place when every export it has is a component, and that file exported four plain functions
 * beside two components, so every edit to it reloaded the whole page. Vite named it each
 * time:
 *
 *     hmr invalidate /src/CardLocations.tsx  Could not Fast Refresh ("readingAgo" export
 *     is incompatible)
 *
 * `SOLD` and `RETIRED` live here rather than beside the component because they are the
 * vocabulary `stateTone` and `stateLabel` are written in — D26's two doors out — and the
 * component imports them back.
 */

import type { RetireReason } from './types'

const MINUTE = 60_000
const HOUR = 3_600_000
const DAY = 86_400_000

/** `3 days`, `4 hours`, `just now` — coarse on purpose; the exact moment is in the title. */
export function readingAgo(at: string | null | undefined): string | null {
  if (typeof at !== 'string' || at.trim() === '') return null
  const when = Date.parse(at)
  if (Number.isNaN(when)) return null
  const elapsed = Math.max(0, Date.now() - when)
  if (elapsed < 2 * MINUTE) return 'just now'
  if (elapsed < HOUR) return `${Math.floor(elapsed / MINUTE)} minutes ago`
  if (elapsed < DAY) {
    const hours = Math.floor(elapsed / HOUR)
    return `${hours} hour${hours === 1 ? '' : 's'} ago`
  }
  const days = Math.floor(elapsed / DAY)
  return `${days} day${days === 1 ? '' : 's'} ago`
}

/** The moment itself, as a person's clock says it — the hover behind the coarse phrase. */
export function readingExact(at: string | null | undefined): string | undefined {
  if (typeof at !== 'string') return undefined
  const when = new Date(at)
  if (Number.isNaN(when.getTime())) return undefined
  return when.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/** A copy the pipeline considers gone. */
export const SOLD = 'sold'

/** The other door out (D26). On the Fulfiller's skin both read as the same fact. */
export const RETIRED = 'retired'

/** The ordinary state, and so the one a screen does not draw as a pill (UX-221): nearly every
 *  copy is identified, so the word tells the hand nothing. */
export const IDENTIFIED = 'identified'

/** The tone of a state pill. Shared with `BoxBrowse` so the two draw one register. */
export function stateTone(state: string): 'default' | 'ok' | 'warn' | 'accent' {
  if (state === SOLD) return 'ok'
  if (state === RETIRED || state === 'moved') return 'warn'
  if (state === 'captured') return 'accent'
  return 'default'
}

/** A card state as a word — the one map every state pill on the owner's screens draws
 *  through, so a raw wire value is never printed as a label. An unknown state is still
 *  shown, capitalised, rather than dropped. */
const STATE_WORDS: Readonly<Record<string, string>> = {
  captured: 'Captured',
  identified: 'Identified',
  sold: 'Sold',
  retired: 'Retired',
  moved: 'Moved',
}
export function stateLabel(state: string): string {
  const known = STATE_WORDS[state]
  if (known !== undefined) return known
  const raw = String(state).replace(/_/g, ' ')
  return raw.charAt(0).toUpperCase() + raw.slice(1)
}

/** A wire number this screen is about to do arithmetic on, as a number it can.
 *
 *  THE ONE PLACE `NaN` IS STOPPED, AND IT IS STOPPED BY COERCION RATHER THAN BY A CHECK AT
 *  EACH READER (D115, amended). `Math.max(0, undefined)` is `NaN`, and `NaN` survives every
 *  `Math.max`, every subtraction and every template literal after it — so an absent counter
 *  does not fail loudly, it renders `NaN live` on the screen where money is decided. That is
 *  what shipped: `cli/cmd_join.py` froze `listing` into `pricing.json` before D115 existed,
 *  and all 171 stored listings on the owner's store carry no `sold_here` at all.
 *
 *  A TYPE CANNOT CATCH THIS ONE. `PricingSku.listing` is a record read back off disk, not a
 *  value the server composes, so its declaration describes what `join` writes TODAY and every
 *  table written before a field existed contradicts it. `PricingPayload.written_at` is the
 *  same class and says so; what this adds is that the arithmetic is guarded even where the
 *  declaration has not caught up. */
function figure(n: number | null | undefined): number {
  return typeof n === 'number' && Number.isFinite(n) ? Math.max(0, n) : 0
}

/** What this store believes TCGplayer is holding NOW: the reading, less what has sold here
 *  since it (D115).
 *
 *  ONE HELPER RATHER THAN SIX SUBTRACTIONS. `store/master.py:Listing.live_estimate` is the
 *  same expression server-side, and a derived value never rides a payload — so the two
 *  numbers travel and the client subtracts. Six inline `Math.max(0, …)` is the rule living in
 *  six places, which is what `SearchGroup.listable` exists to avoid for the shelf count.
 *
 *  AND BECAUSE THE CLIENT IS THE SUBTRACTOR, THE CLIENT OWNS THE GUARD ON ITS INPUTS (D115,
 *  amended). Both are taken as `number | null | undefined` and read through `figure` above,
 *  so a `listing` object written before `sold_here` existed draws the reading itself — which
 *  is what this screen drew before D115, and correct as of the join. The route is deliberately
 *  NOT where that zero is supplied: `do_pipeline_pricing` serves `pricing.json` through and
 *  the honest fill is the same constant, because the store's counter counts sales since THE
 *  STORE'S OWN reading and pairing it with the run's frozen one double-counts every
 *  `reconcile --live` run since the join — the arbitration `pricingSource.ts:asRow` already
 *  spends a paragraph refusing for the very same reason.
 *
 *  FLOORED, AND THE FLOOR IS NOT AN ERROR CASE. A counter above the reading is the ordinary
 *  state of a store whose reading predates its sales, and the honest answer there is "we
 *  believe none is for sale" — which is what zero says. */
export function forSale(live: number | null | undefined, soldHere: number | null | undefined): number {
  return Math.max(0, figure(live) - figure(soldHere))
}

/** How many copies have sold here since the reading, as a figure a sentence may be built on.
 *
 *  EXPORTED SO A READER NEVER TESTS THE RAW FIELD. `soldHere > 0` on an absent counter is
 *  `false`, which is the right answer by accident; `${soldHere} sold since` on the same value
 *  is `undefined sold since`, which is the same defect one branch over. One reading, one
 *  coercion, and the clause and the figure can never disagree. */
export function soldSince(soldHere: number | null | undefined): number {
  return figure(soldHere)
}

/* THE FOUR WAYS A CARD LEAVES WITHOUT A SALE (D26), ONE LABEL AND ONE SENTENCE EACH (UX-241).
 *
 * Inventory's Retire dialog and Review's Close dialog named the same four stored codes two ways:
 * "Pulled out" beside "Pulled", "Not in a condition to sell" beside "Not sellable at the
 * condition listed". This is the one table both read. The stored code never reaches the screen
 * (D196): a screen draws `label` and `said`. */
export const RETIRE_REASONS: readonly { readonly reason: RetireReason; readonly label: string; readonly said: string }[] = [
  { reason: 'pulled', label: 'Pulled out', said: 'Taken out of the box by hand.' },
  { reason: 'damaged', label: 'Damaged', said: 'Not in a condition to sell.' },
  { reason: 'lost', label: 'Lost', said: 'Gone, and not sold.' },
  { reason: 'given_away', label: 'Given away', said: 'Left as a gift or a trade.' },
]

/** The retire reason as a person reads it: `given_away` is `Given away`. Takes `string` because
 *  `DepartedCard.retire_reason` is stored untyped. An unknown value falls back to itself. */
export function reasonWord(reason: string): string {
  return RETIRE_REASONS.find((candidate) => candidate.reason === reason)?.label ?? reason
}
