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

/** The second scale: how far into its own SECTION a card sits. Null when there is no honest
 *  answer — a pooled card, a degraded block, a box the server cannot size. */
export type SectionDepth = {
  /** `Place.card`, the server's own slot number inside the section. Never derived here. */
  slot: number

  /** The denominator, and `growing` is what says which of the two things it is. */
  of: number

  /** True when the far bound is not final, so the number can be larger tomorrow. */
  growing: boolean

  /** 0..100 along the section track. */
  marker: number

  sentence: string
}

/**
 * HOW FAR INTO ITS SECTION, WHICH IS NOT THE QUESTION THE BAR ABOVE IT ANSWERS. The owner's
 * screenshot is the whole argument and it is two rows of one card:
 *
 *     Box 1 · Section 1 · Card 1    marker hard left     #1 OF 53 SO FAR
 *     Box 1 · Section 3 · Card 1    marker hard right    #51 OF 53 SO FAR
 *
 * The second copy draws as *near the end of the box* and it is the FIRST card of its section.
 * Both readings are true and they point opposite ways, and only one of them is drawable today —
 * the one that misleads at exactly the moment a divider matters. A person walking to a box needs
 * the box scale to get near it and the section scale to land on it, which is why this is
 * additive and the box bar above is untouched.
 *
 * ARITHMETIC ON TWO NUMBERS THE SERVER SENT, AND NEVER A SECOND LABEL FORMULA. `slot` is
 * `Place.card` verbatim — the server's own answer to which slot of its section this is — and the
 * denominator is the distance between two bounds it also sent. Nothing here derives a section
 * from an index, and nothing parses the label string. `pipeline/join.py:Position` stays the only
 * label formula in the repo, exactly as `spansOf` above refuses the tempting tiling.
 *
 * WHICH DENOMINATOR, AND WHY THE PICTURE HAS TO SAY WHICH. This is D20's open-versus-sealed
 * argument at section scale, and it bites harder on a bar than in a sentence. `section_end` is
 * the DECLARED bound — from the box's dividers, or from the 25-rule where a box declares none —
 * and it is not a count of cards present. Box 1 is open with 53 cards and its section 3 is
 * declared `51..75`, so three cards sit in twenty-five slots. Both readings are defensible and
 * they are different sentences:
 *
 *   - `card 1 of 25 slots` — true of the divider, and it draws a card at 4% with 96% empty
 *     track. Right for a section whose far bound is real and final.
 *   - `card 1 of 3 so far` — true of what is physically there, and it is the same word D20
 *     makes the box bar say while the box is open, for the identical reason: a denominator that
 *     is different tomorrow is worse than no denominator, because it is the kind of wrong
 *     nobody checks.
 *
 * SO THE RULE IS D20's, APPLIED TO WHICHEVER BOUND IS ACTUALLY FINAL. A section is `growing`
 * when the box is open AND its declared end reaches or passes what the box currently holds —
 * that is the last section, the one the next capture lands in, and its width will be larger
 * tomorrow. Every other section is bounded on both sides by something that is not moving: a
 * divider between two filled sections is 25 slots wide today and 25 slots wide next week, gaps
 * or no gaps. A growing section is measured against its fill so far and says `so far`; a settled
 * one is measured against its declared width and says `slots`. The word is the whole point —
 * a denominator that silently switched meaning between a full section and a half-empty one is
 * precisely what D20 exists to prevent.
 *
 * `section_end >= box_total` IS THE TEST AND IT NEEDS NOTHING BUT `place`. Checked against the
 * live store: box 1 open at 53, section 1 ends at 25 (settled, 25 slots), section 3 ends at 75
 * (growing, 53 - 51 + 1 = 3 so far); box 2 sealed at 544, section 5 ends at 544 (settled, 151).
 * A declared-divider box whose last section ends exactly at the fill is caught by the same test,
 * which is why it reads `>=` rather than `>`.
 *
 * D30's GAP COUNT IS DELIBERATELY NOT IN THIS SENTENCE. It is already drawn one line away by
 * `server.ts:placeSentence` — "2 slots in this section are empty" — on every screen that renders
 * this bar, and the two together are what make a settled section's `of N slots` countable by
 * hand. Repeating it inside the caption would be the same fact at two sizes in one row, which is
 * noise rather than emphasis.
 *
 * NO PERCENTAGE ON THIS LINE, where a settled section could legitimately carry one. The track is
 * the picture and the caption is the number; the box line already publishes the one percentage
 * this component makes, and a second would make two captions that have to be told apart by
 * reading rather than by shape.
 */
export function sectionDepthOf(place: Place): SectionDepth | null {
  /* A pooled card is a count and not a location (D24), so there is no section to be inside. */
  if (place.located === false) return null

  const { card: slot, section, section_start: start, section_end: end, box_total: total } = place
  if (slot === null || section === null) return null
  if (!Number.isFinite(slot) || slot < 1) return null
  if (!Number.isFinite(total) || total <= 0) return null
  if (!Number.isFinite(start) || start < 1) return null

  /* `end === null` — a box that declares no end for this section at all — is growing by the
   * same rule and by the same reading: nothing has bounded it, so what is in it is all there is
   * to measure against. It cannot reach the settled branch, which is why the `?? total` below
   * is unreachable rather than a second answer to the question. */
  const growing = !place.box_closed && (end === null || end >= total)
  const of = (growing ? total : (end ?? total)) - start + 1
  if (!Number.isFinite(of) || of <= 0) return null

  /* The same convention the server's own `fraction` uses — it answers `(index - 1) / box_total`,
   * so card 1 of an open box reads 0 and the last reads just short of the end. Mirrored exactly
   * rather than re-invented, because these two markers are stacked one above the other and a
   * card at the front of both must sit at the front of both. */
  const marker = clamp(((slot - 1) / of) * 100, 0, 100)

  return {
    slot,
    of,
    growing,
    marker,
    sentence: growing
      ? `Section ${section} · card ${slot} of ${of} so far`
      : `Section ${section} · card ${slot} of ${of} slots`,
  }
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

  /** Draw the second, section-scale depth beneath the box one (`sectionDepthOf`). ADDITIVE:
   *  the box track and its `#51 of 53 so far` are untouched, because the owner's ruling on the
   *  ask was "yes, while retaining box depth too" — the two answer different questions and
   *  that is the whole reason both are wanted.
   *
   *  OFF BY DEFAULT, AND THE DEFAULT IS D5's. This is an owner-side ask and the Fulfiller's
   *  view is the one screen in the product whose design is a floor: a second caption there is a
   *  second sentence somebody decided he needs to read, which `Fulfillment.css` names as the
   *  thing not to do, and every text node in that view is asserted at >= 20px. Turning it on
   *  for him is the owner's call, not a side effect of an owner-side request. `CardLocations`
   *  passes it on its owner rows only. */
  sectionDepth?: boolean
}

export function PositionBar({
  place,
  persona = 'owner',
  sections,
  sectionDepth = false,
}: PositionBarProps) {
  const spans = spansOf(place, sections)
  const sentence = sentenceOf(place)
  const depth = sectionDepth ? sectionDepthOf(place) : null

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
      /* BOTH SCALES IN THE ONE LABEL, for the reason `sentenceOf` gives about its own: one
         string so the two cannot drift. `role="img"` excludes every descendant from the
         accessibility tree, so the section caption below is invisible to a screen reader
         unless it is said here — which is also why the visible text carries no aria-hidden. */
      aria-label={depth === null ? sentence : `${sentence} · ${depth.sentence}`}
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

      {/* THE SECOND SCALE, AND IT HAS TO BE TELLABLE FROM THE FIRST AT A GLANCE — two honest
          bars that read alike are one honest bar turned into two ambiguous ones. Three cues,
          none of them a new colour:

            · a SHORTER track (8px against the box's 16px, and 16 against 26 at the Fulfiller's
              density), so the box scale stays the heavier of the two;
            · a hairline rule down the left with the whole block indented behind it — the
              product's one separation mechanism, saying "this is inside the thing above";
            · a caption that opens with the section's own number, where the box caption opens
              with `#`.

          Rejected: painting the current box segment to link the two, which needs a token that
          means "quiet fill" and this file already argues at length why that token does not
          exist. Rejected too: a lens drawn from the box segment's edges down to this track's —
          it is the prettiest of the options and it draws a 6%-wide funnel for box 1's section
          3, which is exactly the case the feature is for.

          NOT ITS OWN role="img". The wrapper above already claims both sentences, and a nested
          image role inside an image role is a second answer to what this component is. */}
      {depth === null ? null : (
        <div className="position-bar-zoom">
          <div className="position-bar-track position-bar-sectiontrack">
            <span className="position-bar-marker" style={{ left: `${depth.marker}%` }} />
          </div>
          <p className="position-bar-text">{depth.sentence}</p>
        </div>
      )}
    </div>
  )
}
