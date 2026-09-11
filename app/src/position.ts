import type { Place, SectionDetail } from './types'
import { isDeparted } from './server'

/* The position ARITHMETIC, with no component in it — `PositionBar.tsx` is the drawing.
 *
 * SPLIT OUT SO THE COMPONENT CAN HOT-RELOAD. React Refresh only updates a module in place
 * when every export it has is a component; one exported function beside one meant the whole
 * page reloaded on every edit to this file, and Vite said so on each one:
 *
 *     hmr invalidate /src/PositionBar.tsx  Could not Fast Refresh ("sectionDepthOf" export
 *     is incompatible)
 *
 * Keeping the arithmetic together in one module is the other half of the reason. `spansOf`,
 * `sentenceOf` and `sectionDepthOf` are one concept — where a card sits, said three ways —
 * and un-exporting the two with no outside caller would have left them private beside a
 * `spansOf` that had moved away.
 *
 * NOTHING HERE DECIDES WHERE A DIVIDER IS. Every width and percentage comes off numbers the
 * server sent; D58 is why each bound is a card COUNT and not a stored index.
 */

/** Which of the two people is looking at this. Owner screens are dense; the Fulfiller's are
 *  the entire product for a retired, non-technical user. Declared here because this is the
 *  lowest of the components that need it. */
export type Persona = 'owner' | 'fulfiller'

/** One drawn segment of the track: an inclusive run of card numbers, and whether the card
 *  being drawn is inside it. */
export type Span = { start: number; end: number; current: boolean }

export function clamp(value: number, low: number, high: number): number {
  if (!Number.isFinite(value)) return low
  return Math.min(high, Math.max(low, value))
}

/**
 * The segments to draw, from the box's own spans where they are known and from this card's
 * section where they are not. With a `Place` alone the segments are the three runs the record
 * states — before this card's section, the section, after — so every tick is a boundary the
 * server sent. With `sections` (a box record's `sections_detail`) the real tiling is drawn.
 * Every number is clamped into the box before it is drawn.
 */
export function spansOf(place: Place, sections?: readonly SectionDetail[]): Span[] {
  const total = place.box_total
  if (!Number.isFinite(total) || total <= 0) return []

  /* Off `slot`, not `index` (D58): every bound here is a card COUNT. Null means the card has no
     place among them — departed, or a box the server could not count — and nothing is marked. */
  const at = place.slot
  const holds = (start: number, end: number) => at !== null && at >= start && at <= end

  /* A DEPARTED CARD STILL HAS A SECTION, AND THE DRAWING KEEPS IT (D118). `slot` is null the
     moment a copy leaves, so `holds` is false for every span and the old picture had no subject
     at all — which is why the whole lens was skipped, and why the panel collapsed 85px on the
     press that sold the card. `section` survives on the wire (measured on a sold copy: `slot`
     and `card` null, `section: 2`, `section_start`/`section_end` intact), so the section the
     copy LEFT FROM is still nameable and is what the bracket zooms into.
     `current` here therefore means "the section this drawing is about", not "the card is in
     it" — and the two cannot be confused on screen, because a departed bar draws NO marker and
     its caption reads `no longer in the box`. */
  const left = isDeparted(place) ? place.section : null
  const wasIn = (start: number, end: number) =>
    left !== null && place.section_start >= start && place.section_start <= end

  if (sections !== undefined && sections.length > 0) {
    const spans: Span[] = []
    for (const detail of sections) {
      const start = clamp(detail.start, 1, total)
      const end = clamp(typeof detail.end === 'number' ? detail.end : total, start, total)
      spans.push({
        start,
        end,
        current: holds(start, end) || (left !== null && detail.section === left),
      })
    }
    if (spans.length > 0) return spans
  }

  const start = clamp(place.section_start, 1, total)
  const end = clamp(place.section_end === null ? total : place.section_end, start, total)

  const spans: Span[] = []
  if (start > 1) spans.push({ start: 1, end: start - 1, current: holds(1, start - 1) })
  spans.push({ start, end, current: holds(start, end) || wasIn(start, end) })
  if (end < total) spans.push({ start: end + 1, end: total, current: holds(end + 1, total) })
  return spans
}

/**
 * The sentence, which is also the accessible name. A closed box gets a percentage and an open
 * one never does: an open box's denominator is how many cards are in it *so far*. `fraction`
 * is the server's and is never recomputed. Null is not zero.
 *
 * The Fulfiller's form carries neither: "so far" is a pipeline notion and a percentage is not
 * a thing read at arm's length. He gets `Card 53 of 65`, in words.
 */
export function sentenceOf(place: Place, persona: Persona = 'owner'): string {
  const { slot, box_total, box_closed, fraction } = place
  if (isDeparted(place)) return persona === 'fulfiller' ? 'No longer in the box' : 'no longer in the box'
  if (slot === null) {
    return persona === 'fulfiller'
      ? 'Where this sits in the box is not known yet'
      : 'where this sits in the box is not known yet'
  }
  if (fraction === null || !Number.isFinite(box_total) || box_total <= 0) {
    return persona === 'fulfiller'
      ? `Card ${slot} · where it sits in the box is not known yet`
      : `#${slot} · where this sits in the box is not known yet`
  }
  if (persona === 'fulfiller') return `Card ${slot} of ${box_total}`
  if (box_closed) return `#${slot} of ${box_total} · ${Math.round(fraction * 100)}% in`
  return `#${slot} of ${box_total} so far`
}

/** The second scale: how far into its own SECTION a card sits. Null when there is no honest
 *  answer — a pooled card, a degraded block, a box the server cannot size. */
export type SectionDepth = {
  /** `Place.card`, the server's own slot number inside the section. Never derived here.
   *  NULL FOR A DEPARTED COPY, which has left every slot in the section it was in. */
  slot: number | null
  /** The denominator, and `growing` is what says which of the two things it is. */
  of: number
  /** True when the far bound is not final, so the number can be larger tomorrow. */
  growing: boolean
  /** 0..100 along the section track, and NULL where there is no card to mark — a departed
   *  copy. The bar keeps the mark mounted and animates it away rather than deleting it; see
   *  `PositionBar.tsx`. */
  marker: number | null
  sentence: string
}

/**
 * A section is `growing` when the box is open AND its declared end reaches or passes what the
 * box currently holds — the last section, the one the next capture lands in. A growing section
 * is measured against its fill so far and says `so far`; a settled one against its declared
 * width and says `slots`.
 */
export function sectionDepthOf(place: Place): SectionDepth | null {
  if (place.located === false) return null

  const { card: slot, section, section_start: start, section_end: end, box_total: total } = place
  const gone = isDeparted(place)
  if (section === null) return null
  /* THE SECTION'S NAME IS SAID WITH ITS NUMBER (D132) — `Section 6 · Rares · card 54 of 153
     so far`. The number is what a hand counts to and the name is what the owner calls it. */
  const named = place.section_name ? `Section ${section} · ${place.section_name}` : `Section ${section}`
  /* A DEPARTED COPY KEEPS THE SECOND SCALE AND LOSES ONLY ITS MARK (D118). `card` is null the
     moment it leaves, and returning null here used to take the whole zoom block with it — 40 of
     the 85px the lens was worth, and the reason the panel changed size on the press that sold
     the card. The section it was in is still a real run of slots and is still worth drawing;
     what is not true any more is that this copy is at a number inside it. */
  if (!gone && (slot === null || !Number.isFinite(slot) || slot < 1)) return null
  if (!Number.isFinite(total) || total <= 0) return null
  if (!Number.isFinite(start) || start < 1) return null

  const growing = !place.box_closed && (end === null || end >= total)
  const of = (growing ? total : (end ?? total)) - start + 1
  if (!Number.isFinite(of) || of <= 0) return null

  /* The same convention the server's own `fraction` uses — `(index - 1) / total` — so a card at
     the front of both tracks sits at the front of both. */
  const marker = gone || slot === null ? null : clamp(((slot - 1) / of) * 100, 0, 100)

  if (gone || slot === null) {
    return {
      slot: null,
      of,
      growing,
      marker: null,
      sentence: growing
        ? `${named} · ${of} cards so far · this copy is not among them`
        : `${named} · ${of} slots · this copy is not in one`,
    }
  }

  return {
    slot,
    of,
    growing,
    marker,
    sentence: growing
      ? `${named} · card ${slot} of ${of} so far`
      : `${named} · card ${slot} of ${of} slots`,
  }
}

