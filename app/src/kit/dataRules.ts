import { storedBoxRecency } from '../deviceMemory'

/* THE PURE HALF OF THE KIT'S DATA PRIMITIVES: what a status means in colour, and what order a
 * list of boxes is in. No React and no stylesheet, so a spec and a non-React caller can import
 * it. `data.tsx` re-exports all of it, and a screen imports from there. */

/** The meanings a status can have. A screen maps its own states onto these, and the tone
 *  follows: the review found "needs pricing" in two colours on one screen, and blue meaning
 *  several different things. */
export type StatusKind =
  /** Waits on the OWNER. The one attention tone. */
  | 'needs'
  /** Moving now, with nothing for the owner to do. */
  | 'working'
  /** Finished well. */
  | 'done'
  /** Stopped, and the owner must look. */
  | 'failed'
  /** Waits on somebody else: a buyer, the marketplace, a run. */
  | 'waiting'
  /** A plain fact with no state. */
  | 'neutral'

export type StatusTone = 'warn' | 'accent' | 'ok' | 'danger' | 'default'

/** The one tone for each meaning. Amber is ONLY "needs the owner"; blue is ONLY "moving now";
 *  a neutral count is never coloured. */
export const STATUS_TONES: Readonly<Record<StatusKind, StatusTone>> = {
  needs: 'warn',
  working: 'accent',
  done: 'ok',
  failed: 'danger',
  waiting: 'default',
  neutral: 'default',
}

/** What a box with no stored name is called. Never its number (the owner's ruling,
 *  2026-09-23). */
export const UNNAMED_BOX = 'Unnamed box'

/** When this browser last reached for each box, by box number (`deviceMemory.ts`). */
export type BoxRecency = ReadonlyMap<number, string>

/** A list of boxes, MOST RECENT FIRST (the owner's ruling, 2026-09-23, for every list of boxes).
 *
 *  THREE TERMS. The box this browser reached for last leads. A box it never reached for sorts
 *  after every box it has, NEWEST BOX FIRST by its true index `bid` (D145), which only grows as
 *  boxes are made. The box number breaks what is left. Returns a new array. */
export function boxesMostRecentFirst<T extends { readonly box: number; readonly bid?: number | null }>(
  boxes: readonly T[],
  recency: BoxRecency = storedBoxRecency(),
): T[] {
  return [...boxes].sort((left, right) => {
    const ra = recency.get(left.box) ?? ''
    const rb = recency.get(right.box) ?? ''
    if (ra !== rb) return ra > rb ? -1 : 1
    const ba = left.bid ?? -1
    const bb = right.bid ?? -1
    if (ba !== bb) return bb - ba
    return left.box - right.box
  })
}

