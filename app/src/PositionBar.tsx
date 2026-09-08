import { useRef } from 'react'

import type { Place, SectionDetail } from './types'
import { clamp, sentenceOf, sectionDepthOf, spansOf } from './position'
import { isDeparted } from './server'
import type { Persona, Span } from './position'
import './PositionBar.css'

/* How far into the box a card sits, drawn as the box — a lens.
 *
 * Two scales: the box track (one segment per section, the card's own section painted) and,
 * beneath a bracket that zooms out of that segment, the section track. Nothing here decides
 * where a divider is: every width and percentage comes off numbers the server sent. `persona`
 * picks the density and nothing else — the Fulfiller's is bigger and his captions clear the
 * 20px floor his view is asserted against.
 */

/** Where the current section's edges sit along the box track, 0..100, for the bracket. */
function lensOf(spans: readonly Span[]): { left: number; right: number } | null {
  const total = spans.reduce((n, span) => n + (span.end - span.start + 1), 0)
  if (total <= 0) return null
  let at = 0
  for (const span of spans) {
    const width = span.end - span.start + 1
    if (span.current) return { left: (at / total) * 100, right: ((at + width) / total) * 100 }
    at += width
  }
  return null
}

export type PositionBarProps = {
  place: Place

  /** Defaults to the owner, so a missing prop cannot hand the Fulfiller's density to a dense
   *  table. */
  persona?: Persona

  /** The box's real spans, from `GET /boxes`. Optional, and the picture is honest without it. */
  sections?: readonly SectionDetail[]

  /** Draw the second, section-scale depth beneath the box one. Off by default; the Fulfiller's
   *  view never turns it on. Skipped on a box with one section, where both tracks would say
   *  the same numbers. */
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
  const depth = sectionDepth && spans.length > 1 ? sectionDepthOf(place) : null
  const lens = depth === null ? null : lensOf(spans)
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
      aria-label={depth === null ? sentence : `${sentence} · ${depth.sentence}`}
      data-place={place.label}
      data-gone={gone ? 'true' : undefined}
    >
      <p className="position-bar-text position-bar-text-box">{sentence}</p>
      <div className="position-bar-track">
        {spans.map((span) => (
          <span
            key={`${span.start}-${span.end}`}
            className={span.current ? 'position-bar-segment position-bar-here' : 'position-bar-segment'}
            style={{ flexGrow: span.end - span.start + 1 }}
          />
        ))}
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

      {depth === null ? null : (
        <div className="position-bar-zoom">
          {lens === null ? null : (
            <svg
              className="position-bar-lens"
              viewBox="0 0 100 10"
              preserveAspectRatio="none"
              aria-hidden="true"
              focusable="false"
            >
              <polygon points={`${lens.left},0 ${lens.right},0 100,10 0,10`} />
              <line x1={lens.left} y1="0" x2="0" y2="10" />
              <line x1={lens.right} y1="0" x2="100" y2="10" />
            </svg>
          )}
          <div className="position-bar-track position-bar-sectiontrack">
            <span
              className="position-bar-marker"
              data-gone={depth.marker === null ? 'true' : undefined}
              style={{ left: `${sectionAt}%` }}
              aria-hidden="true"
            />
          </div>
          <p className="position-bar-text position-bar-text-section">{depth.sentence}</p>
        </div>
      )}
    </div>
  )
}
