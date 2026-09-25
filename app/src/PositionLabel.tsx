/* app/src/PositionLabel.tsx
 *
 * ONE RENDERING OF `pipeline/join.py:Position.label` FOR EVERY OWNER SITE (D41, amended).
 *
 * THE LABEL IS THE BOX'S NAME, THE SECTION AND THE CARD WITHIN ITS SECTION, AND NOTHING ELSE
 * (the owner's rulings of 2026-09-23: D259 and
 * D260). The server composes `Mixed Singles, Section 2, Card 17`,
 * `position.ts:placePartsOf` reads it back from the right end (a box name may hold a comma), and
 * this ranks the three facts for the eye: a muted path of box and section, and the card as the
 * figure. The box NUMBER is never drawn, not as a value and not as a note.
 *
 * A DEPARTED CARD IS RANKED THE SAME WAY AND MARKED, NOT WORDED. Its label names the place it
 * left; the caller says it left (`departed`, from `isDeparted(place)`), and the stylesheet strikes
 * the figure through and mutes the block. D58 still holds on the wire: a departed `Place.slot` is
 * null, and the card that closed up behind it answers to the same number, drawn plain.
 *
 * THE FULFILLER NEVER IMPORTS THIS. `Fulfillment.tsx` and `CardLocations.tsx:FulfillerCard` draw
 * the server label as plain text, which is why the server label carries no typed separator
 * (D218). `app/tests/fulfillment.spec.ts` floors those at >=32px, and D31 keeps that spec
 * unweakened. The firewall is the COMPONENT GRAPH, not a selector: see the file header of
 * PositionLabel.css.
 */

import { Fragment, type ReactNode } from 'react'

import { placePartsOf, sayPlace } from './position'
import { STORE_KEY } from './storeKey'
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
     so `slot` puts the figures in a hard column at the cell's left edge. Reading order for
     anything that is not an eye is unchanged: `aria-label` carries the whole place either way. */
  lead?: Lead

  /* A NOTE THAT RIDES THE FIRST PATH LINE — the box's human name, handed over by a caller whose
     label predates the name being in it. Since the owner's ruling the server's label already
     says the name (D259), so a note equal to it is not drawn twice. */
  boxNote?: ReactNode

  /* THE BOX'S NAME (D132, then D259). When given it is the box part's
     value. The box NUMBER is never drawn beside it any more: the owner ruled that the number is
     an index the store keeps, and a person reads the name. */
  boxName?: string | null

  /* THE SECTION'S NAME RIDES ITS OWN PART (D132): `SECTION 6 Rares`. The number stays the value,
     because a section is counted to, and the name is the note beside it. */
  sectionName?: string | null

  /* THE CARD HAS LEFT ITS BOX: sold, retired or moved (the owner's ruling, 2026-09-23). The
     label still names the place it left, and this draws the difference VISUALLY, never as a
     word: the figure is struck through and muted, and the accessible name is in the past tense.
     A caller holding a `Place` passes `isDeparted(place)`. */
  departed?: boolean
}

type Part = { key: string; value: string; note?: ReactNode }

/* A BOX PART'S KEY. `BOX Mixed Singles` reads as a label and a value; a box whose name already
   says `Box` (every backfilled default, `Box 3`) takes no key, so it never reads `BOX Box 3`. */
function boxPart(name: string): Part {
  return /^box\b/i.test(name) ? { key: '', value: name } : { key: 'Box', value: name }
}

export function PositionLabel({
  label,
  flow = 'stack',
  lead = 'path',
  boxNote = null,
  boxName = null,
  sectionName = null,
  departed = false,
}: PositionLabelProps): ReactNode {
  const place = placePartsOf(label)

  /* ANYTHING THAT IS NOT A PLACE RENDERS WHOLE — the pooled line (`Pokémon code cards · pooled ·
     5/12`, D24) is the one caller of this shape. Its parts each get a span and the seam between
     them is drawn by CSS, never retyped (D218); a trailing store key is demoted beside it. */
  if (place === null) {
    const all = label.split(' · ')
    const tail = all[all.length - 1]
    const hasKey = all.length >= 3 && tail !== undefined && STORE_KEY.test(tail)
    const parts = hasKey ? all.slice(0, -1) : all
    const body = (
      <span className="position-plain-parts">
        {parts.map((part, at) => (
          <span key={at}>{part}</span>
        ))}
      </span>
    )
    return hasKey ? (
      <span className="position-plain" role="group" aria-label={sayPlace(label)}>
        {body}
        <span className="position-storekey">{tail}</span>
      </span>
    ) : (
      body
    )
  }

  /* A LABEL FROM BEFORE THE RULING THAT NAMED NO CARD (`Box 3 · departed · B3 #96`) is a departed
     card too, and it has no figure at all to strike. */
  const gone = departed || place.card === null
  const named = boxName !== null && boxName.trim() !== '' ? boxName.trim() : place.box
  const sectioned = sectionName !== null && sectionName.trim() !== '' ? sectionName.trim() : null
  const note = boxNote !== null && boxNote !== named ? boxNote : null

  const path: Part[] = [{ ...boxPart(named), note }]
  if (place.section !== null) path.push({ key: 'Section', value: String(place.section), note: sectioned })
  const slot: Part | null = place.card === null ? null : { key: 'Card', value: String(place.card) }

  /* THE SPOKEN FORM IS THE SERVER'S LABEL AS A SENTENCE (LOC-12 heard `BOX 1SECTION 3CARD13`):
     since the owner's ruling it already names the box by its name, with commas, and `sayPlace`
     reads an older dotted label the same way. A departed card's is in the past tense. */
  const aria = gone ? `Was at ${sayPlace(label)}` : sayPlace(label)

  if (flow === 'run') {
    return (
      <span className="position-run" role="group" aria-label={aria} data-departed={gone ? 'true' : undefined}>
        {/* A `<wbr>` AFTER EACH PART: the parts touch with no space between them (the gap is a
            margin), so without it a narrow line had no place to break and clipped the card's own
            number off the end. It adds nothing to the text. */}
        {path.map((part, at) => (
          <Fragment key={part.key + part.value + at}>
            <span className="position-run-path">
              {part.key === '' ? null : `${part.key.toUpperCase()} `}
              <b>{part.value}</b>
              {part.note === null || part.note === undefined ? null : (
                <span className="position-run-note">{part.note}</span>
              )}
            </span>
            <wbr />
          </Fragment>
        ))}
        {slot === null ? null : (
          <>
            <span className="position-run-key">{slot.key.toUpperCase()}</span>
            <span className="position-run-num">{slot.value}</span>
          </>
        )}
      </span>
    )
  }

  return (
    <span className="position-parts" role="group" aria-label={aria} data-lead={lead} data-departed={gone ? 'true' : undefined}>
      <span className="position-path">
        {path.map((part, at) => (
          <span key={part.key + part.value + at}>
            {part.key === '' ? null : `${part.key.toUpperCase()} `}
            <b>{part.value}</b>
            {part.note === null || part.note === undefined ? null : (
              <span className="position-path-note">{part.note}</span>
            )}
          </span>
        ))}
      </span>
      {/* THE NUMBER COLUMN. A departed card keeps its figure, struck through by the stylesheet
          (the owner's ruling: the place stays, the departure is drawn). A legacy departed label
          with no figure holds the column with a void, so the path does not slide left in a list
          whose other rows carry one (the hard column `lead='slot'` exists to draw). */}
      <span className="position-slot">
        {slot === null ? (
          <span className="position-void" aria-hidden="true" />
        ) : (
          <>
            <span className="position-key">{slot.key.toUpperCase()}</span>
            <span className="position-num">{slot.value}</span>
          </>
        )}
      </span>
    </span>
  )
}
