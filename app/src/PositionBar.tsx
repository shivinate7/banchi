import { useRef } from 'react'

import type { Place, SectionDetail } from './types'
import {
  clamp,
  graduationStep,
  sectionBlankSentence,
  sectionDepthOf,
  sentenceOf,
  spansOf,
} from './position'
import { isDeparted } from './server'
import type { Persona } from './position'
import './PositionBar.css'

/* How far into the box a card sits, at two scales — and the SECTION is the instrument.
 *
 * THE SECTION IS THE RULER AND THE BOX IS THE MARGIN NOTE. A graduated 26px ruler with a fill,
 * a pin that crosses it and the section's own bounds written inside its two ends; under it an
 * 8px strip of chips for the box, with a caret on the chip the card is in. The box scale is
 * kept because the owner asked for it and because it is the one that gets a thumb near the
 * right drawer — but at a 580px bar it is 1.45px a card, which is three or four distinguishable
 * states, while the caption above it already says `#51 of 53 · 96% in` exactly. The section
 * scale is 6.8 to 82.9px a card, which is a number you can point at.
 *
 * WHAT THERE IS NO LONGER: the SVG trapezoid that used to bracket the two. It carried three
 * defects and two of them were unfixable in principle — its two legs' slope ratio contains
 * neither a width nor a height term, and its arithmetic computed segment edges from card counts
 * while the real segments are flex children with a gap and a `min-width`, so its mouth pointed
 * at the wrong chip by 8px on a five-section box and 42px on a 22-section one. The caret that
 * replaces it is a pseudo-element ON the chip, so the browser registers it to its subject and
 * there is no second calculation to disagree.
 *
 * THE HEIGHT IS DECIDED BY THE PROP AND THE PAINT BY THE CARD'S STATE (D118). The zoom block is
 * mounted whenever `sectionDepth` is on — never on whether the depth RESOLVED — so the four
 * owner states render the identical DOM at the identical height. Before this the block was
 * gated on `depth !== null`, and two states nobody had measured drew a 29px bar in a list of
 * 73px ones.
 *
 * Nothing here decides where a divider is: every width and percentage comes off numbers the
 * server sent. `persona` picks the density and nothing else — the Fulfiller never turns the
 * second scale on, his captions clear the 20px floor his view is asserted against, and every
 * rule this file's stylesheet adds is scoped to `.position-bar-owner` or to `[data-depth]`.
 */

export type PositionBarProps = {
  place: Place

  /** Defaults to the owner, so a missing prop cannot hand the Fulfiller's density to a dense
   *  table. */
  persona?: Persona

  /** The box's real spans, from `GET /boxes`. Optional, and the picture is honest without it. */
  sections?: readonly SectionDetail[]

  /** Draw the section ruler above the box strip. Off by default; the Fulfiller's view never
   *  turns it on. NOT gated on the box having more than one section: an undeclared box gets the
   *  ruler too, which is what `docs/DESIGN.md` has claimed since it was written and the old
   *  `spans.length > 1` gate always prevented. */
  sectionDepth?: boolean

  /** Defaults to `true`, which is byte-identical to every caller before this prop existed. Set
   *  `false` only where the box's own denominator is not "still filling" — the walk, mid-pull
   *  (`docs/specs/order-walk-plan.md` §8's "The stop, rebuilt" ruling, owner, 2026-09-19: the
   *  copy's bar reads `#8 of 34`, never `#8 of 34 so far`). `#/capture` and `#/inventory` never
   *  pass it. */
  soFar?: boolean
}

export function PositionBar({
  place,
  persona = 'owner',
  sections,
  sectionDepth = false,
  soFar = true,
}: PositionBarProps) {
  const spans = spansOf(place, sections)
  const sentence = sentenceOf(place, persona, soFar)
  /* TWO SEPARATE FACTS, AND THE SECOND ONE DOES NOT DECIDE THE SHAPE. `sectionDepth` says the
     ruler is drawn; `depth` says what can be painted in it. The old single expression folded
     them together and took 44px out of the row in every state the arithmetic declined to
     answer. */
  const depth = sectionDepth ? sectionDepthOf(place) : null
  const sectionSentence = sectionDepth
    ? (depth?.sentence ?? sectionBlankSentence(place, persona))
    : null
  const gone = isDeparted(place)

  /* Drawn only when the server said where the card is. The clamp is for layout, not truth. */
  const marker = place.fraction === null ? null : clamp(place.fraction * 100, 0, 100)

  /* WHERE THE MARK WAS STANDING WHEN IT LOST ITS PLACE (D118). The sale nulls `fraction` in the
     same render that adds `data-gone`, and an absolutely positioned mark with no `left` snaps to
     its static position — the far end of the track — so it would teleport and only then fade.
     These refs are read ONLY on the way out: while the card is placed they are simply the value
     being drawn. The component stays mounted across the write, which is what makes them the
     previous frame's answer rather than a stale one from another card. */
  const lastBox = useRef(50)
  const lastSection = useRef(50)
  if (marker !== null) lastBox.current = marker
  if (depth?.marker != null) lastSection.current = depth.marker
  const boxAt = marker ?? lastBox.current
  const sectionAt = depth?.marker ?? lastSection.current

  return (
    <div
      className={`position-bar position-bar-${persona}`}
      role="img"
      /* THE SECOND SCALE IS ANNOUNCED HERE OR NOT AT ALL — `role="img"` hides every descendant.
         It follows the VISIBLE text, so the blank sentence travels too: a reader who cannot see
         the empty ruler is told in words why it is empty. */
      aria-label={sectionSentence === null ? sentence : `${sentence} · ${sectionSentence}`}
      data-place={place.label}
      data-gone={gone ? 'true' : undefined}
      data-depth={sectionDepth ? 'on' : undefined}
    >
      {/* DOM ORDER IS LOAD-BEARING AND IS NOT THE VISUAL ORDER. `inventory.spec.ts` reads the box
          track with `querySelector('.position-bar-track')`, and the section ruler carries that
          class too — only document order makes that selector return this one. The inversion is
          done entirely with CSS `order`. Reorder this JSX and that assertion silently measures
          the wrong element and goes green over nothing. */}
      <p className="position-bar-text position-bar-text-box">{sentence}</p>
      <div className="position-bar-track">
        {spans.length === 0 ? (
          /* A BOX THE SERVER COULD NOT SIZE STILL GETS AN OBJECT, not a void. `spansOf` returns
             nothing on `box_total <= 0`, and an empty flex row is three pixels of nothing under
             a caption that says the size is not known. */
          <span className="position-bar-segment position-bar-segment-blank" />
        ) : (
          spans.map((span) => (
            <span
              key={`${span.start}-${span.end}`}
              className={span.current ? 'position-bar-segment position-bar-here' : 'position-bar-segment'}
              style={{ flexGrow: span.end - span.start + 1 }}
            />
          ))
        )}
        {/* MOUNTED EVEN WITH NOWHERE TO STAND (D118), which is the whole of the animation the
            owner asked for. React keeps this node across the render that sells the card, so the
            mark eases out and drops instead of being deleted between two frames — and the row
            it sits in keeps its height either way, which is the part the page below feels.
            `left` holds its last value: an element on its way out may not also travel. */}
        <span
          className="position-bar-marker"
          data-gone={marker === null ? 'true' : undefined}
          style={{ left: `${boxAt}%` }}
          aria-hidden="true"
        />
      </div>

      {!sectionDepth ? null : (
        <div className="position-bar-zoom">
          <div className="position-bar-track position-bar-sectiontrack">
            {depth === null ? null : (
              <>
                {/* THE CARDS COUNTED PAST TO REACH THIS ONE, and not the card itself: `marker` is
                    `(slot - 1) / of`, the server's own `fraction` convention, so a card at slot 1
                    draws an empty bar and the pin IS the boundary. Left-only radius for the same
                    reason — the filled edge is hard. */}
                <span className="position-bar-fill" style={{ width: `${sectionAt}%` }} aria-hidden="true" />
                <span
                  className="position-bar-rule"
                  style={{ ['--pb-marks' as string]: String(depth.of / graduationStep(depth.of)) }}
                  aria-hidden="true"
                />
                {/* THE SECTION'S RUN IN BOX CARDS, read against the box caption's own `#54 of
                    400`. The trapezoid was reaching for how much of the box this slice is and
                    asked the reader to trust a drawing; these two numbers let them check one. */}
                <span className="position-bar-edge position-bar-edge-start" aria-hidden="true">{depth.firstCard}</span>
                <span className="position-bar-edge position-bar-edge-end" aria-hidden="true">{depth.lastCard}</span>
              </>
            )}
            {/* ALWAYS RENDERED, IN EVERY STATE, so the marker counts two specs pin hold whatever
                the arithmetic could answer — and so the pin drops out of an unlocated bar on the
                same mechanism a departed one uses rather than by a second code path. */}
            <span
              className="position-bar-marker"
              data-gone={depth?.marker == null ? 'true' : undefined}
              style={{ left: `${sectionAt}%` }}
              aria-hidden="true"
            />
          </div>
          <p className="position-bar-text position-bar-text-section">
            {depth === null ? (
              sectionSentence
            ) : (
              /* TWO SPANS, AND THE STRING IS NEVER SPLIT TO GET THEM. D132 lets the owner name a
                 section and nothing forbids a name containing ` · `, so a caption built by
                 splitting `sentence` cuts a name in half. The parts come out of `sectionDepthOf`
                 as fields; concatenated they are byte-identical to it. */
              <>
                <span className="position-bar-cap-head">{depth.head}</span>
                <span className="position-bar-cap-tail">{depth.tail}</span>
              </>
            )}
          </p>
        </div>
      )}
    </div>
  )
}
