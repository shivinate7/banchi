import type { Place, SectionDetail } from './types'
import './PositionBar.css'

/* How far into the box a card sits, drawn as the box.
 *
 * THE QUESTION THIS ANSWERS IS NOT THE ONE A POSITION LABEL ANSWERS, and that is the whole
 * reason it exists. `Box 3 · Section 2 · Card 17` says exactly which slot, and says nothing
 * about whether that slot is at the front of the box or two thirds of the way to the back —
 * which is what decides whether you lift the lid or dig. The owner asked for the second thing
 * beside the first, and the Fulfiller needs it more than he does: he is walking to a box he
 * did not fill, and D5 says his screens have to be self-evident.
 *
 * A DRAWING, NEVER A CLAIM. types.ts sets the rule on `Place` and this is the component it was
 * written for: the label is rendered as the server sent it, and everything below computes
 * nothing but widths and a percentage out of numbers the server also sent. Nothing here
 * decides where a divider is. See `spansOf` for the one place that distinction had teeth.
 *
 * ONE COMPONENT, TWO DENSITIES — docs/DESIGN.md's "one system, two densities" rather than two
 * components. `persona` picks the scale and nothing else: same palette, same three faces, same
 * 4px radius, same markup, same sentence. The Fulfiller's is bigger and his text clears the
 * 20px floor his view is asserted against.
 *
 * NO TRAVELLED-DISTANCE FILL, and its absence is a decision rather than a thing left out. A
 * bar filled from the front of the box up to the marker would read well and there is no token
 * that means "quiet fill": `--hover` is documented as row hover only, `--line` is the 1px
 * hairline, and `--accent` has exactly two jobs of which this is neither. The lesson
 * `--on-accent` taught this repo is that the answer to "no token means what I mean" is a
 * missing token argued for in docs/DESIGN.md, never a literal painted here — so the marker
 * carries the position, the ticks carry the dividers, and the sentence carries the percentage.
 */

/** Which of D5's two people is looking at this. Owner screens are a tool and dense is fine;
 *  the Fulfiller's are the entire product for a retired, non-technical user.
 *
 *  DECLARED HERE AND NOT IN types.ts, deliberately. That file's first line is "the shapes the
 *  capture server speaks" and no route has ever spoken a persona — it is D5's vocabulary, not
 *  the wire's, and putting it there would make the file mean two things. It lives in the
 *  lowest-level of the three components that need it and the other two import it from here.
 *  The moment a fourth file needs it, or anything else UI-shaped wants a home, this is the
 *  type that moves into a shared module — the same threshold `describeFailure` was held to. */
export type Persona = 'owner' | 'fulfiller'

/** One drawn segment of the track: an inclusive run of `Place.index` values, and whether the
 *  card being drawn is inside it. */
export type Span = { start: number; end: number; current: boolean }

function clamp(value: number, low: number, high: number): number {
  if (!Number.isFinite(value)) return low
  return Math.min(high, Math.max(low, value))
}

/**
 * The segments to draw, from the box's own spans where they are known and from this card's
 * section where they are not.
 *
 * THE HONEST FORM IS THE DEFAULT, AND THE TEMPTING ONE IS REFUSED. Given a single `Place` it
 * looks like a full tiling is one line away: this section is `section_end - section_start + 1`
 * cards wide, so lay that width end to end across `box_total` and draw every divider in the
 * box. That is exactly the section arithmetic types.ts forbids on `Place`, and D10 as amended
 * 2026-08-23 is why it would be wrong rather than merely disallowed — dividers go where the
 * operator physically put them, a box carries its own list of them, and a uniform width is an
 * assumption about a box nobody made. A bar drawn that way would show dividers that are not
 * in the box, at a glance, with no way to tell it had guessed.
 *
 * So with a `Place` alone the segments are the three runs the record actually states: the part
 * of the box before this card's section, the section itself, and the part after. Every tick is
 * a boundary the server sent. A box that declares no sections yields `section_start` 1 and no
 * end, which collapses to one segment covering the whole box — that is the single-span case,
 * and it renders as one segment rather than as an error because one undivided box is a real
 * box and not a missing answer.
 *
 * PASS `sections` AND YOU GET THE REAL TILING. `GET /boxes` carries `sections_detail`, which
 * is `pipeline/join.py`'s own rendering of the layout — the spans, computed once, in the one
 * place the repo allows them to be computed. A screen that already holds a box record should
 * hand them over; a screen that only has the card should not go and fetch them to make the
 * picture prettier, because the three-span form is true and the difference is decoration.
 *
 * Every number is clamped into the box before it is drawn. A span that ran off the end would
 * be invisible rather than obviously wrong, which is the failure mode worth spending four
 * lines to avoid.
 */
export function spansOf(place: Place, sections?: readonly SectionDetail[]): Span[] {
  const total = place.box_total
  if (!Number.isFinite(total) || total <= 0) return []

  const holds = (start: number, end: number) => place.index >= start && place.index <= end

  if (sections !== undefined && sections.length > 0) {
    const spans: Span[] = []
    for (const detail of sections) {
      /* Read field by field rather than trusted, the same reason `server.ts:positionLabel`
       * keeps a `typeof` check its type says is redundant: this module casts rather than
       * validates, so an older capture server on the Mac can answer a shape this type says
       * is impossible. A section whose end did not arrive is treated as running to the end of
       * the box, which is what an open last section is. */
      const start = clamp(detail.start, 1, total)
      const end = clamp(typeof detail.end === 'number' ? detail.end : total, start, total)
      spans.push({ start, end, current: holds(start, end) })
    }
    if (spans.length > 0) return spans
  }

  const start = clamp(place.section_start, 1, total)
  const end = clamp(place.section_end === null ? total : place.section_end, start, total)

  const spans: Span[] = []
  if (start > 1) spans.push({ start: 1, end: start - 1, current: holds(1, start - 1) })
  spans.push({ start, end, current: holds(start, end) })
  if (end < total) spans.push({ start: end + 1, end: total, current: holds(end + 1, total) })
  return spans
}

/**
 * The sentence, which is also the accessible name. One string so the two cannot drift.
 *
 * A CLOSED BOX GETS A PERCENTAGE AND AN OPEN ONE NEVER DOES. This is the distinction the whole
 * component is for. `#40 of 250 · 16% in` is a statement about a box whose size is final: the
 * 250 will still be 250 tomorrow and 16% will still be 16%. An open box's denominator is how
 * many cards are in it *so far*, so the same card reads 30% today and 12% next week without
 * having moved — a number that changes while the fact it describes does not is worse than no
 * number, because it is the kind of wrong nobody checks. `so far` is doing real work in that
 * sentence and is not filler.
 *
 * `fraction` IS THE SERVER'S AND IS NEVER RECOMPUTED FROM `index / box_total`. Those two are a
 * second derivation of one fact, and the day they disagree is the day something is wrong that
 * is worth seeing rather than papering over.
 *
 * NULL IS NOT ZERO. types.ts says it on the field and it matters here: a marker at zero points
 * at the front of the box, which is a specific and wrong place to send somebody, and it looks
 * exactly like a correct answer. The track draws empty and the sentence says so instead.
 */
export function sentenceOf(place: Place): string {
  const { index, box_total, box_closed, fraction } = place

  if (fraction === null || !Number.isFinite(box_total) || box_total <= 0) {
    return `#${index} · where this sits in the box is not known yet`
  }
  if (box_closed) return `#${index} of ${box_total} · ${Math.round(fraction * 100)}% in`
  return `#${index} of ${box_total} so far`
}

export type PositionBarProps = {
  place: Place

  /** Defaults to the owner, because the owner's screens are where this first appears and a
   *  missing prop should not silently hand the Fulfiller's density to a dense table. */
  persona?: Persona

  /** The box's real spans, from `GET /boxes`. Optional, and the picture is honest without it —
   *  see `spansOf`. Not in the prop shape this component was specified with; it is here
   *  because it is the difference between drawing the dividers the box has and drawing this
   *  card's own section, and a screen holding a box record already has them. */
  sections?: readonly SectionDetail[]
}

export function PositionBar({ place, persona = 'owner', sections }: PositionBarProps) {
  const spans = spansOf(place, sections)
  const sentence = sentenceOf(place)

  /* Drawn only when the server said where the card is. The clamp is for layout and not for
   * truth: a fraction outside 0..1 is a bug, and pinning the marker to an end at least leaves
   * it on screen where it can be seen, rather than positioning it off the track where the bar
   * looks empty and correct. */
  const marker = place.fraction === null ? null : clamp(place.fraction * 100, 0, 100)

  return (
    /* role="img" with the sentence as its label, so a screen reader is told the one thing this
       is — how far in — instead of walking a row of empty decorative elements. Its descendants
       are not exposed, which is why the visible text below carries no aria-hidden of its own:
       the role already excludes it, and a second mechanism doing the same job is one that can
       be deleted without the first one noticing. */
    <div
      className={`position-bar position-bar-${persona}`}
      role="img"
      aria-label={sentence}
      data-place={place.label}
    >
      <div className="position-bar-track">
        {spans.map((span) => (
          <span
            key={`${span.start}-${span.end}`}
            className={span.current ? 'position-bar-segment position-bar-here' : 'position-bar-segment'}
            /* flex-grow rather than a width percentage: the segments are siblings in a flex
               row, so their proportions are exactly the spans and no rounding has to be
               reconciled against 100%. */
            style={{ flexGrow: span.end - span.start + 1 }}
          />
        ))}
        {marker === null ? null : (
          <span className="position-bar-marker" style={{ left: `${marker}%` }} />
        )}
      </div>
      <p className="position-bar-text">{sentence}</p>
    </div>
  )
}
