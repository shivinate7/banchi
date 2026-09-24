import { useRef } from 'react'

import type { Place, SectionDetail } from './types'
import {
  clamp,
  graduationStep,
  sectionBlankSentence,
  sectionDepthOf,
  sentenceOf,
  sentencePartsOf,
  spansOf,
} from './position'
import { isDeparted } from './server'
import type { Persona } from './position'
import './PositionBar.css'

/* Where a card sits: its section, drawn as a ruler that marks the card, and the box's sections
 * on either side of it.
 *
 * THE OWNER'S RULING, 2026-09-23, AMENDS D155 (D-a-card-is-counted-in-its-section). The ruler
 * uses SECTION NUMBERS THROUGHOUT: its two ends are card 1 and the section's last card, the same
 * count the caption and the big numeral use. The box-wide bounds it wrote before were a second
 * scale on one instrument (LOC-04). It MARKS THE EXACT CARD: the card's own cell is filled and the
 * pin stands at the cell's centre, where D155's fill counted the cards passed and its caret sat on
 * the middle of a chip (LOC-05). It SHOWS THE SECTIONS BEFORE AND AFTER: the strip under it is
 * one chip per section, numbered where the chip has room, with this section's chip marked.
 *
 * CARD 1 IS AT THE FAR BACK, AND BOTH DRAWINGS SAY SO. The owner's words: the card closest to
 * the body is the last card and the one all the way at the back is the first. So the left end
 * of both scales is `back` and the right end is `front`, written once under the strip.
 *
 * THE HEIGHT IS DECIDED BY THE PROP AND THE PAINT BY THE CARD'S STATE (D118). The zoom block is
 * mounted whenever `sectionDepth` is on, never on whether the depth RESOLVED, so every owner
 * state renders the identical DOM at the identical height, a departed copy included.
 *
 * Nothing here decides where a divider is: every width and percentage comes off numbers the
 * server sent. `persona` picks the density and nothing else — the Fulfiller never turns the
 * section ruler on, and every rule this file's stylesheet adds is scoped to `.position-bar-owner`
 * or to `[data-depth]`.
 */

export type PositionBarProps = {
  place: Place

  /** Defaults to the owner, so a missing prop cannot hand the Fulfiller's density to a dense
   *  table. */
  persona?: Persona

  /** The box's real spans, from `GET /boxes`. Optional, and the picture is honest without it:
   *  the strip then draws the sections before, this section, and the sections after. */
  sections?: readonly SectionDetail[]

  /** Draw the section ruler above the box strip. Off by default; the Fulfiller's view never
   *  turns it on. An undeclared box gets the ruler too: its one section is the whole box. */
  sectionDepth?: boolean
}

export function PositionBar({
  place,
  persona = 'owner',
  sections,
  sectionDepth = false,
}: PositionBarProps) {
  const spans = spansOf(place, sections)
  const sentence = sentenceOf(place, persona)
  const parts = sentencePartsOf(place, persona)
  const depth = sectionDepth ? sectionDepthOf(place) : null
  const sectionSentence = sectionDepth
    ? (depth?.sentence ?? sectionBlankSentence(place, persona))
    : null
  const gone = isDeparted(place)

  /* THE STRIP'S CAPTION IS THE SECTION AMONG THE BOX'S SECTIONS once the ruler above carries the
     card's own count: one count per instrument, and section numbers throughout. Without the
     ruler the caption is the card's own `Card 5 of 12`. */
  const sectionCount = sections !== undefined && sections.length > 0 ? sections.length : null
  const boxCaption =
    sectionDepth && place.section !== null
      ? sectionCount === null
        ? /* No count of the box's sections to state, and the section caption above already names
             this one: the line keeps only back and front. */
          ''
        : `Section ${place.section} of ${sectionCount}`
      : parts.main
  const boxDetail = sectionDepth ? null : parts.detail

  /* Drawn only when the server said where the card is. The clamp is for layout, not truth. */
  const marker = place.fraction === null ? null : clamp(place.fraction * 100, 0, 100)

  /* WHERE THE MARK WAS STANDING WHEN IT LOST ITS PLACE (D118). The sale nulls `fraction` in the
     same render that adds `data-gone`, and an absolutely positioned mark with no `left` snaps to
     the far end of the track, so it would teleport and only then fade. These refs are read ONLY
     on the way out. */
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
      /* The section scale is announced here or not at all: `role="img"` hides every descendant. */
      aria-label={sectionSentence === null ? sentence : `${sentence}, ${sectionSentence}`}
      data-place={place.label}
      data-gone={gone ? 'true' : undefined}
      data-depth={sectionDepth ? 'on' : undefined}
    >
      {/* DOM ORDER IS LOAD-BEARING AND IS NOT THE VISUAL ORDER. `inventory.spec.ts` reads the box
          track with `querySelector('.position-bar-track')`, and the section ruler carries that
          class too; only document order makes that selector return the strip. The visual order
          is done with CSS `order`. */}
      {/* WITH THE RULER, THE CAPTION SHARES ITS LINE WITH \`back\` AND \`front\` (LOC-06), so saying which
          end is card 1 costs the row no height: the copies row is sized to the fold (D118). */}
      {sectionDepth ? (
        <div className="position-bar-ends-row">
          <span className="position-bar-end-back" aria-hidden="true">back</span>
          <p className="position-bar-text position-bar-text-box">{boxCaption}</p>
          <span className="position-bar-end-front" aria-hidden="true">front</span>
        </div>
      ) : (
        <p className="position-bar-text position-bar-text-box">
          {boxCaption}
          {boxDetail === null ? null : <span className="position-bar-text-detail">{boxDetail}</span>}
        </p>
      )}
      <div className="position-bar-track">
        {spans.length === 0 ? (
          <span className="position-bar-segment position-bar-segment-blank" />
        ) : (
          spans.map((span) => (
            <span
              key={`${span.start}-${span.end}`}
              className={span.current ? 'position-bar-segment position-bar-here' : 'position-bar-segment'}
              style={{ flexGrow: span.end - span.start + 1 }}
              title={span.section === null || span.section === undefined ? undefined : `Section ${span.section}`}
            >
              {/* THE SECTION NUMBERS BEFORE AND AFTER, on the strip itself. A chip too narrow for
                  its digits clips them (the stylesheet), and the chip still marks the run. */}
              {sectionDepth && span.section !== null && span.section !== undefined ? (
                <span className="position-bar-segment-num" aria-hidden="true">
                  {span.section}
                </span>
              ) : null}
            </span>
          ))
        )}
        {/* MOUNTED EVEN WITH NOWHERE TO STAND (D118): the mark eases out on the render that sells
            the card instead of being deleted between two frames. */}
        <span
          className="position-bar-marker"
          data-gone={marker === null ? 'true' : undefined}
          style={{ left: `${boxAt}%` }}
          aria-hidden="true"
        />
      </div>

      {/* THE FULFILLER'S STRIP SAYS WHICH END IS CARD 1 TOO (the owner's orientation: the far back),
          at his 20px floor. The owner's is written once under the ruler, inside the zoom block. */}
      {persona !== 'fulfiller' ? null : (
        <p className="position-bar-ends" aria-hidden="true">
          <span className="position-bar-end-back">Back</span>
          <span className="position-bar-end-front">Front</span>
        </p>
      )}

      {!sectionDepth ? null : (
        <div className="position-bar-zoom">
          <div className="position-bar-track position-bar-sectiontrack">
            {depth === null ? null : (
              <>
                {/* THE CARD'S OWN CELL, filled: the mark sits on the card, not on the boundary
                    in front of it (LOC-05). */}
                {depth.cell === null ? null : (
                  <span
                    className="position-bar-cell"
                    style={{ left: `${depth.cell.left}%`, width: `${depth.cell.width}%` }}
                    aria-hidden="true"
                  />
                )}
                <span
                  className="position-bar-rule"
                  style={{ ['--pb-marks' as string]: String(depth.of / graduationStep(depth.of)) }}
                  aria-hidden="true"
                />
                {/* SECTION NUMBERS AT BOTH ENDS (LOC-04): card 1 at the back, the last card at the
                    front, the same count as the caption above. */}
                <span className="position-bar-edge position-bar-edge-start" aria-hidden="true">{depth.firstCard}</span>
                <span className="position-bar-edge position-bar-edge-end" aria-hidden="true">{depth.lastCard}</span>
              </>
            )}
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
              <>
                <span className="position-bar-cap-head">
                  {depth.head.map((fact, i) => (
                    <span key={i} className="position-bar-cap-fact">
                      {fact}
                    </span>
                  ))}
                </span>
                <span className="position-bar-cap-tail">
                  {depth.tail.map((fact, i) => (
                    <span key={i} className="position-bar-cap-fact">
                      {fact}
                    </span>
                  ))}
                </span>
              </>
            )}
          </p>
        </div>
      )}
    </div>
  )
}
