/* app/src/PositionLabel.tsx
 *
 * ONE RENDERING OF `pipeline/join.py:Position.label` FOR EVERY OWNER SITE. D41 shipped this
 * shape inline in `BoxBrowse.tsx` and scoped it there in writing — "taking this to them is a
 * decision about all three sites, not a copy of this one". That decision is D41's amendment;
 * this file is what it decided.
 *
 * THE SERVER STRING IS NEVER EDITED. `Position.label` still emits `Box N · Section N · Card N`,
 * this recomposes it into key/figure pairs for the eye, and the original travels verbatim on
 * `aria-label`. That is what makes a client-side split a VIEW rather than a quiet edit of the
 * record, and it is the property every spec asserts.
 *
 * THE FULFILLER NEVER IMPORTS THIS. `Fulfillment.tsx` renders `.fulfillment-place` /
 * `.fulfillment-place-large` as plain text and `CardLocations.tsx:FulfillerCard` renders
 * `.card-locations-place-large` as plain text, and both must go on doing exactly that.
 * `app/tests/fulfillment.spec.ts` floors those at >=32px with tabular figures and D31 keeps that
 * spec unweakened. The firewall is the COMPONENT GRAPH, not a selector: see the file header of
 * PositionLabel.css for how a future edit that breaches it fails loudly.
 */

import type { ReactNode } from 'react'

import './PositionLabel.css'

type Flow = 'stack' | 'run'
type Lead = 'path' | 'slot'

type PositionLabelProps = {
  /* The server's string, unmodified. Anything this component cannot parse renders whole. */
  label: string

  /* GEOMETRY, not size. `stack` is the two-dimensional block: a muted column of coarse parts
     with the slot figure beside it. `run` is the same RANKING laid out in one dimension, for a
     label sitting inside a running sentence — measured on the capture screen's halt banner, the
     stacked block there is 79px against the sentence's 23px and orphans the trailing period
     onto its own line. A sentence is a stream; the block is an object. */
  flow?: Flow

  /* WHICH PART COMES FIRST, and it is a property of being in a LIST rather than a taste call.
     Path-first is right for a singleton, where the eye arrives at the block and reads it
     coarse-to-fine. In a column of seven copies the coarse parts are IDENTICAL down every row,
     so path-first puts seven identical `BOX 2 / SECTION n` blocks in front of the only thing
     that differs — measured on the copies list, the figures land at x=400 behind them, which is
     the dense-grey-table failure docs/DESIGN.md names by the front door. `slot` puts the figures
     in a hard column at the cell's left edge. Reading order for anything that is not an eye is
     unchanged: `aria-label` carries the server string either way. */
  lead?: Lead

  /* A NOTE THAT RIDES THE FIRST PATH LINE. Exactly one caller passes it — the copies list, which
     hands over `Place.box_name` so the box's human name sits on the BOX line instead of taking a
     line of its own. That absorption is what makes the treatment height-free there; without it
     it is +17px on every row. Deliberately not a general slot: it attaches to the first path
     part and nowhere else, because the first path part is the only one it can be true about. */
  boxNote?: ReactNode
}

type Part = { key: string; value: string }

/* Each part is `<word...> <number>`, so the LAST space is the seam. `lastIndexOf` rather than a
   split, because a two-word key (`next index` shape) must stay whole; `at < 1` keeps a part with
   no space at all renderable rather than producing an empty key. Lifted verbatim from D41. */
function seam(part: string): Part {
  const at = part.lastIndexOf(' ')
  return at < 1 ? { key: '', value: part } : { key: part.slice(0, at), value: part.slice(at + 1) }
}

export function PositionLabel({
  label,
  flow = 'stack',
  lead = 'path',
  boxNote = null,
}: PositionLabelProps): ReactNode {
  const parts = label.split(' · ')
  if (parts.length < 2) return <>{label}</>

  const split = parts.map(seam)

  /* THE SLOT IS THE LAST PART, NOT THE THIRD. Anchoring to the end rather than to a fixed index
     is what keeps a two-part or four-part label honest: whatever the formula ends with is the
     finest thing said, and that is what is drawn at size. */
  const slot = split[split.length - 1]
  if (slot === undefined) return <>{label}</>

  /* THE NUMERIC GUARD, AND IT IS THE ONE THING THIS COMPONENT HAS THAT D41's DID NOT.
     `#/inventory` draws only real positions, so promoting whatever sits after the last space was
     safe there. `#/review` is not: `app/tests/review.spec.ts` renders D24's pooled row as
     `Pokémon code cards · pooled`, which the shipped splitter turns into a path reading
     `POKÉMON CODE cards` — a key/value split of a phrase that has neither — and draws the
     lowercase word `pooled` as a 300.9px bold figure. Nothing breaks geometrically; the MEANING
     breaks, and no existing assertion sees it. A promoted slot is a slot number or it is nothing.

     It also catches the capture screen's `positionText` fallback (`box 3, index 7`) for a second
     reason, which is worth having: that string reaches here only if someone later adds ' · ' to
     it, and the guard is cheaper than remembering. */
  if (!/^\d+$/.test(slot.value)) return <>{label}</>

  const path = split.slice(0, -1)

  /* THE RUN FORM: the treatment's ranking without its geometry. Inline spans only — no flex, no
     column — so the label stays inside the line it was written into. Measured on the halt
     banner: 23px tall, identical to the plain string it replaces, and 14% narrower. */
  if (flow === 'run') {
    return (
      <span className="position-run" role="group" aria-label={label}>
        {path.map((part, at) => (
          <span className="position-run-path" key={part.key + part.value + at}>
            {part.key === '' ? null : `${part.key.toUpperCase()} `}
            <b>{part.value}</b>
          </span>
        ))}
        {slot.key === '' ? null : (
          <span className="position-run-key">{slot.key.toUpperCase()}</span>
        )}
        <span className="position-run-num">{slot.value}</span>
      </span>
    )
  }

  return (
    <span className="position-parts" role="group" aria-label={label} data-lead={lead}>
      <span className="position-path">
        {path.map((part, at) => (
          <span key={part.key + part.value + at}>
            {part.key === '' ? null : `${part.key.toUpperCase()} `}
            <b>{part.value}</b>
            {at === 0 && boxNote !== null ? (
              <span className="position-path-note">{boxNote}</span>
            ) : null}
          </span>
        ))}
      </span>
      <span className="position-slot">
        {slot.key === '' ? null : <span className="position-key">{slot.key.toUpperCase()}</span>}
        <span className="position-num">{slot.value}</span>
      </span>
    </span>
  )
}