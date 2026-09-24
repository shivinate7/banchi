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
 * The box caption in two facts rather than one joined string (D218) — `main` is the position
 * itself and `detail` is the qualifier beside it, when there is one. A caller that draws text
 * renders them as sibling elements with the separator drawn by CSS; `sentenceOf` below joins
 * them back with a typed `' · '` for the one caller allowed to keep it, the accessible name
 * (D41).
 *
 * A closed box gets a percentage and an open one never does. `fraction` is the server's and is
 * never recomputed. Null is not zero.
 *
 * The Fulfiller's form is `Card 53 of 65`, in words.
 *
 * NO "SO FAR" (owner's ruling, 2026-09-19: "this typed dot" — no, this string — "needs to be
 * removed everywhere it exists"; `#20 of 34` stays). The words used to trail an OPEN box's own
 * denominator, opted out only where a caller passed `soFar={false}`, which no caller ever did —
 * `PositionBar`'s own walk-pane exception was never wired, so every open box read `so far`
 * everywhere, unconditionally, the whole time. The flag is gone rather than fixed forward: a
 * parameter nothing ever set to `false` was not an opt-out, it was dead code with one branch
 * live.
 */
export type SentenceParts = { main: string; detail: string | null }

/** How many cards this card's own SECTION holds — never the box's total (owner's ruling,
 *  2026-09-23, amending how D58's number is DRAWN: "a card's place number counts WITHIN ITS
 *  SECTION, not within the whole box... restarting at every divider"). THE SERVER ALREADY
 *  SENDS THE NUMERATOR SECTION-RELATIVE: `place.card` is `pipeline/join.py:Position.card`,
 *  `slot - section_start + 1`, so the same number `Box 3 · Section 2 · Card 1` already puts
 *  in the label. What is missing is the DENOMINATOR — the server sends the section's bounds
 *  (`section_start`/`section_end`), not its size — so this is the one client-side derivation
 *  the ruling asks for, never a server change. `section_end` is null only for an open box's
 *  final section, which runs to the box's own end (`box_total`), the same fallback
 *  `pipeline/join.py:Position.card`'s own docstring and `_of_uncached` already use server-side
 *  for that same section's `section_end`. */
function sectionCardTotal(place: Place): number | null {
  const { section_start, section_end, box_total } = place
  const end = section_end ?? (Number.isFinite(box_total) && box_total > 0 ? box_total : null)
  if (end === null) return null
  return Math.max(0, end - section_start + 1)
}

export function sentencePartsOf(place: Place, persona: Persona = 'owner'): SentenceParts {
  const { slot, card, box_total, box_closed, fraction } = place
  if (isDeparted(place)) {
    return { main: persona === 'fulfiller' ? 'No longer in the box' : 'no longer in the box', detail: null }
  }
  if (slot === null) {
    return {
      main:
        persona === 'fulfiller'
          ? 'Where this sits in the box is not known yet'
          : 'where this sits in the box is not known yet',
      detail: null,
    }
  }
  if (fraction === null || !Number.isFinite(box_total) || box_total <= 0) {
    return persona === 'fulfiller'
      ? { main: `Card ${slot}`, detail: 'where it sits in the box is not known yet' }
      : { main: `#${slot}`, detail: 'where this sits in the box is not known yet' }
  }
  if (persona === 'fulfiller') {
    // SECTION-RELATIVE, not box-wide (see `sectionCardTotal` above) — `card`/the section
    // total fall back to the box-wide reading only if the server ever omits either, which it
    // does not on this path (slot is not null here, and `card`/`section_start` are computed
    // together with it).
    const total = sectionCardTotal(place)
    if (card !== null && total !== null) return { main: `Card ${card} of ${total}`, detail: null }
    return { main: `Card ${slot} of ${box_total}`, detail: null }
  }
  if (box_closed) return { main: `#${slot} of ${box_total}`, detail: `${Math.round(fraction * 100)}% in` }
  return { main: `#${slot} of ${box_total}`, detail: null }
}

/** The joined form, for the accessible name only (D41 kept the dot there on purpose). Never
 *  render this string directly — draw `sentencePartsOf`'s two fields as elements instead. */
export function sentenceOf(place: Place, persona: Persona = 'owner'): string {
  const { main, detail } = sentencePartsOf(place, persona)
  return detail === null ? main : `${main} · ${detail}`
}

/** D218: a typed middle dot is a defect wherever it is typed, and `Position.label`'s own
 *  ` · ' is exactly that — server-composed and real, but never fit to retype as a screen's
 *  visible or spoken text. Every screen that DRAWS a position splits it and lets CSS join the
 *  parts (`PositionLabel.tsx`); a toast body, a sentence built around the label (`Walk to
 *  ${label}`, `The card at ${label}`), and any other plain-text or accessible-name use carry
 *  the label as a SENTENCE FRAGMENT, where there is no CSS to draw a separator with — this
 *  reads it as a sentence instead, the same `', '` `Home.tsx`'s box line takes for its own
 *  `title` attribute. THE SERVER STRING ITSELF IS NEVER EDITED (other screens split on it);
 *  this is a read, not a rewrite. `PositionLabel.tsx`'s own internal `aria-label` is the one
 *  caller D41 lets keep the raw dot, because it carries `Position.label` whole as its OWN
 *  accessible name rather than splicing it into a bigger sentence — that caller does not
 *  reach this function. */
export function sayPlace(label: string): string {
  return label.replace(/ · /g, ', ')
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
  /** THE CAPTION'S TWO HALVES, HANDED OVER AS FIELDS AND NEVER RECOVERED BY SPLITTING
   *  `sentence`. The ruler's caption ellipsizes its head and pins its tail, which needs two
   *  elements. Each half is now a LIST OF FACTS (D218) rather than a joined string — `head` is
   *  `['Section 6']` or `['Section 6', 'Rares']` when the owner has named the section (D132),
   *  and `tail` is one or two facts depending on `growing` and whether the copy departed. A
   *  caller draws each list as sibling elements with the separator drawn by CSS; joining every
   *  entry of `head` then `tail` with `' · '` is byte-identical to `sentence`, which stays
   *  whole because it is also the accessible name (D41). */
  head: readonly string[]
  tail: readonly string[]
  /** The section's bounds IN BOX CARDS — `86` and `170` of a box holding 400 — so the ruler's
   *  two ends can state the nesting as a number the reader checks against the box caption
   *  rather than as a shape they have to trust. D58's unit: a card COUNT, never a stored
   *  index. */
  firstCard: number
  lastCard: number
}

/** The pitch of the ruler's minor graduations, in cards, so the comb never draws more than 24
 *  teeth. The ladder is the ordinary 1-2-5 one; past 500-card sections it falls back to an
 *  exact 24. Narrowest render this component has in the product is the retire dialog at a 390
 *  viewport — 194px — which is 8.1px a tooth at the cap. */
const GRADUATIONS = [1, 2, 5, 10, 25, 50, 100, 250, 500] as const
export function graduationStep(of: number): number {
  return GRADUATIONS.find((step) => of / step <= 24) ?? Math.ceil(of / 24)
}

/**
 * The section caption for the two states `sectionDepthOf` cannot answer — a card whose record
 * carries no section, and a box the server could not size. The ruler is drawn in both of them
 * (the box is still there; what is unknown is which part of it), so it needs a sentence.
 *
 * "WHICH PART OF THE BOX", NOT "WHICH SECTION", on purpose: the sentence must not presuppose
 * the very thing it is saying is unknown. This stays on the right side of D68 — that entry
 * deleted an object that drew a FAILED MEASUREMENT as if it were a position; this one claims
 * nothing at all.
 */
export function sectionBlankSentence(place: Place, persona: Persona = 'owner'): string {
  if (isDeparted(place)) {
    return persona === 'fulfiller'
      ? 'Which part of the box it was in is not recorded'
      : 'which part of the box it was in is not recorded'
  }
  return persona === 'fulfiller'
    ? 'Which part of the box this sits in is not known yet'
    : 'which part of the box this sits in is not known yet'
}

/** The section's bounds, with no one card in mind — the arithmetic `sectionDepthOf` and
 *  `sectionCountOf` both stand on. `start`/`of`/`growing` are D58's units throughout: a card
 *  COUNT, never a stored index. Null where neither caller can go on: no section, or a box the
 *  server could not size. */
function sectionSpan(place: Place): { start: number; of: number; growing: boolean } | null {
  const { section, section_start: start, section_end: end, box_total: total } = place
  if (section === null) return null
  if (!Number.isFinite(total) || total <= 0) return null
  if (!Number.isFinite(start) || start < 1) return null

  const growing = !place.box_closed && (end === null || end >= total)
  const of = (growing ? total : (end ?? total)) - start + 1
  if (!Number.isFinite(of) || of <= 0) return null
  return { start, of, growing }
}

/** The section's own card count (D58's units), with no one card's position in mind — what a
 *  section HEADER states, on `#/inventory`'s walk and everywhere else a section is named
 *  without naming a card inside it. Null where `sectionDepthOf` would also refuse: a pooled
 *  block (D24) or a box the server could not size.
 *
 *  THE ONE NUMBER STATED IS THIS SECTION'S OWN COUNT, NEVER THE BOX-WIDE SPAN `section_start`/
 *  `section_end` carry. A header built from those two box-wide numbers reads in a different
 *  scale than a row's own `card` (the count WITHIN the section, D58) — `#54–#93` over a row
 *  reading `#37` is not out of range, it is two rulers on one screen, the bug D092 already
 *  named for the position bar and this repeats one scale up. */
export type SectionCount = { of: number; growing: boolean }
export function sectionCountOf(place: Place): SectionCount | null {
  if (place.located === false) return null
  const span = sectionSpan(place)
  return span === null ? null : { of: span.of, growing: span.growing }
}

/** A section title in its two parts: `head` names the section (and, on `#/orders`, the box), and
 *  `count` is `sectionCountOf`'s answer in words, or null where it has none. Two parts because
 *  a narrow column may cut the name but never the count (`SectionTitle.tsx` draws them). */
export type SectionTitleParts = { readonly head: string; readonly count: string | null }

/** `19 cards`, `1 card`. The words every section title states its count in. */
export function sectionCountWords(count: SectionCount | null): string | null {
  return count === null ? null : `${count.of} card${count.of === 1 ? '' : 's'}`
}

/** The whole title as one sentence: what a screen reader hears, what a fold groups by, and
 *  exactly the text `SectionTitle` draws. */
export function sectionTitleText(parts: SectionTitleParts): string {
  return parts.count === null ? parts.head : `${parts.head}, ${parts.count}`
}

/**
 * A section is `growing` when the box is open AND its declared end reaches or passes what the
 * box currently holds — the last section, the one the next capture lands in. A growing section
 * is measured against its fill and says only the count (the owner's ruling, 2026-09-19: no
 * `so far` anywhere); a settled one against its declared width and says `slots`.
 */
export function sectionDepthOf(place: Place): SectionDepth | null {
  if (place.located === false) return null

  const { card: slot, section, section_start: start, box_total: total } = place
  const gone = isDeparted(place)
  if (section === null) return null
  /* THE SECTION'S NAME IS SAID WITH ITS NUMBER (D132) — `Section 6`, `Rares`, `card 54 of 153`.
     The number is what a hand counts to and the name is what the owner calls it. Two facts, not
     one string: `head` carries both so a caller draws the separator in CSS instead of typing it
     into the name (D218). */
  const head: readonly string[] = place.section_name ? [`Section ${section}`, place.section_name] : [`Section ${section}`]
  /* A DEPARTED COPY KEEPS THE SECOND SCALE AND LOSES ONLY ITS MARK (D118). `card` is null the
     moment it leaves, and returning null here used to take the whole zoom block with it — 40 of
     the 85px the lens was worth, and the reason the panel changed size on the press that sold
     the card. The section it was in is still a real run of slots and is still worth drawing;
     what is not true any more is that this copy is at a number inside it. */
  if (!gone && (slot === null || !Number.isFinite(slot) || slot < 1)) return null

  const span = sectionSpan(place)
  if (span === null) return null
  const { of, growing } = span

  /* The same convention the server's own `fraction` uses — `(index - 1) / total` — so a card at
     the front of both tracks sits at the front of both. */
  const marker = gone || slot === null ? null : clamp(((slot - 1) / of) * 100, 0, 100)

  /* THE SECTION'S OWN RUN, COUNTED IN BOX CARDS, which is what the ruler writes inside its two
     ends. `of` is already the width in the growing and the settled case alike, so the far bound
     follows from the near one and cannot disagree with the denominator the caption prints. */
  const firstCard = clamp(start, 1, total)
  const lastCard = firstCard + of - 1

  if (gone || slot === null) {
    /* A SHORT TAIL THAT DOES NOT FIGHT THE RULER UNDER IT. The old two facts (`40 slots`,
       `this copy is not in one`) forced the head — the section's own name — to be the part
       that ellipsized (`PositionBar.css` had it backwards: the head shrank, the tail never
       did), so a named section read as `Secti… · 40 slots · this copy is not in one`, cut
       mid-word beside a ruler still drawing the section whole. `sectionDepthOf` gets only a
       `Place`, which carries no sold/retired distinction — a caller that reads the copy's own
       `state` could say `sold from here` or `retired from here`, but every caller of this
       function today is fed through `PositionBar`, which does not thread that word in either.
       One neutral phrase, shorter than what it replaces, says exactly what is known and no
       more (D194 — the count only ever goes down). */
    const tail: readonly string[] = [growing ? `${of} cards` : `${of} slots`, 'left this section']
    return {
      slot: null,
      of,
      growing,
      marker: null,
      sentence: [...head, ...tail].join(' · '),
      head,
      tail,
      firstCard,
      lastCard,
    }
  }

  const tail: readonly string[] = [growing ? `card ${slot} of ${of}` : `card ${slot} of ${of} slots`]
  return {
    slot,
    of,
    growing,
    marker,
    sentence: [...head, ...tail].join(' · '),
    head,
    tail,
    firstCard,
    lastCard,
  }
}

