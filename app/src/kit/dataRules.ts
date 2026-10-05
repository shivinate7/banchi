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
 *  2026-09-23). F5 verbiage cut (row 162): "Untitled" — "box" was redundant, every card in
 *  the view this fell back for is already a box. */
export const UNNAMED_BOX = 'Untitled'

/** When this browser last reached for each box, by box number (`deviceMemory.ts`). */
export type BoxRecency = ReadonlyMap<number, string>

/** A box's name for a label or a sentence: the stored name, or `Box <number>` without one.
 *  MIRRORS `store/numbers.py:box_title` EXACTLY (D259). This is not `UNNAMED_BOX` above —
 *  that placeholder is for a box that SHOULD already carry a stored name after the backfill,
 *  and never shows a number. `boxTitle` is for a caller with no registry row to ask at all: a
 *  box the registry no longer holds (deleted, D145), a legacy record from before the
 *  backfill, or a bare `(box, name)` pair passed down without a lookup. The number is the one
 *  fact those callers have, and it is the same fallback the server already writes for a new
 *  unnamed box, never a second vocabulary. */
export function boxTitle(name: string | null | undefined, number: number): string {
  const text = typeof name === 'string' ? name.trim() : ''
  return text !== '' ? text : `Box ${number}`
}

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


/** `1,234 cards`, `1 card`: a count with its noun, thousands grouped. THE one count word. */
export function count(n: number, one: string, many: string = `${one}s`): string {
  return `${n.toLocaleString('en-US')} ${n === 1 ? one : many}`
}

/** `999 B`, `1.2 kB`, `31.5 MB`: decimal units, one place. THE one byte size. */
export function byteSize(bytes: number): string {
  if (bytes < 1000) return `${bytes} B`
  if (bytes < 1_000_000) return `${(bytes / 1000).toFixed(1)} kB`
  return `${(bytes / 1_000_000).toFixed(1)} MB`
}
