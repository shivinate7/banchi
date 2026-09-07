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

/** What this store believes TCGplayer is holding NOW: the reading, less what has sold here
 *  since it (D115).
 *
 *  ONE HELPER RATHER THAN SIX SUBTRACTIONS. `store/master.py:Listing.live_estimate` is the
 *  same expression server-side, and a derived value never rides a payload — so the two
 *  numbers travel and the client subtracts. Six inline `Math.max(0, …)` is the rule living in
 *  six places, which is what `SearchGroup.listable` exists to avoid for the cap.
 *
 *  FLOORED, AND THE FLOOR IS NOT AN ERROR CASE. A counter above the reading is the ordinary
 *  state of a store whose reading predates its sales, and the honest answer there is "we
 *  believe none is for sale" — which is what zero says. */
export function forSale(live: number, soldHere: number): number {
  return Math.max(0, Math.max(0, live) - Math.max(0, soldHere))
}
