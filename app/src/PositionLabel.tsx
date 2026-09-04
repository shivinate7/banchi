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
 * A CARD IN NO SLOT IS RANKED TOO, AND IT IS THE FIGURE THAT GOES RATHER THAN THE TREATMENT
 * (D71). `join.departed_label` ends on a word where a slot number would be, and refusing the
 * whole label over it meant every screen fell back to the raw string at its payload size — so
 * `#/inventory` drew a sold card the pre-D41 way while every live card beside it was ranked.
 * The state and the store key ride the path (`BOX 3` / `DEPARTED B3 #36`), the number column is
 * drawn empty, and D58's refusal of a slot number for a card that has left is untouched: what
 * that refusal was ever about is the FIGURE, and there is none.
 *
 * THE FULFILLER NEVER IMPORTS THIS. `Fulfillment.tsx` renders `.fulfillment-place` /
 * `.fulfillment-place-large` as plain text and `CardLocations.tsx:FulfillerCard` renders
 * `.card-locations-place-large` as plain text, and both must go on doing exactly that.
 * `app/tests/fulfillment.spec.ts` floors those at >=32px with tabular figures and D31 keeps that
 * spec unweakened. The firewall is the COMPONENT GRAPH, not a selector: see the file header of
 * PositionLabel.css for how a future edit that breaches it fails loudly.
 */

import type { ReactNode } from 'react'

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

/* THE STORE KEY A LABEL MAY END ON — the `/inventory/<box>/<index>` path (D68) — IS DECLARED IN
   `storeKey.ts`, with the composer that writes one. It lived here until D92's sweep, which found
   two screens spelling a key by hand and wanted one place to send them; that place is not this
   file, because this one imports a stylesheet and a screen reaching here for a string would take
   an edge to CSS it does not otherwise want. Neither shape the regex matches is
   `<word> <number>`, which is what every part of a position label is — `Box 3`, `Section 1`,
   `Card 17` — and what the seam above is built on, so neither can be mistaken for a part. */

/* A PART WHOSE VALUE IS A NUMBER — `Box 3`, `Section 1`, `Card 17`. Every part of a label this
   component composes has this shape, which is what makes the seam above safe to take. */
const NUMBER = /^\d+$/

/* THE TERMINAL A LABEL MAY CARRY INSTEAD OF A SLOT NUMBER: one lowercase word, and today there
   is exactly one — `departed`. A STATE where a number would be, which is a shape `Position.label`
   composes deliberately (D58: a card that has left is in no slot) and which this component used
   to refuse wholesale. Refusing it is what put the pre-D41 plain string back on two screens; see
   the state branch below for the argument. Anchored and lowercase so it cannot match a name that
   wandered into the last part — the pooled label's `cards` is caught by the path guard instead. */
const STATE = /^[a-z]+$/

export function PositionLabel({
  label,
  flow = 'stack',
  lead = 'path',
  boxNote = null,
}: PositionLabelProps): ReactNode {
  const all = label.split(' · ')

  /* THE STORE KEY IS PEELED OFF FIRST AND IS NEVER PROMOTED (D68). `join.departed_label` ends on
     it — `Box 3 · departed · B3 #31` — because two departed copies of one card in one box were
     otherwise the identical string, and the index is the one number about a departed card that
     cannot lie about a shelf. What it must NOT become is the figure: this component draws the
     last part at `--pos-slot`, so a promoted key would put a 44px number in the slot column of a
     card that is in no slot, which is precisely the lie D58 refuses.

     WHERE IT GOES INSTEAD DEPENDS ON WHETHER THE REST RANKS (D71). For a label this component can
     rank it becomes the VALUE of the state that explains it — `DEPARTED B3 #31`, one path pair
     beside `BOX 3` — and for one it cannot it stays a demoted note under the plain string, which
     is the pooled row and the only caller left of that shape. Either way it is in the path's
     register and never in the figure's, which is the whole of D68's ask.

     THE LAST PART ONLY, AND ONLY WITH SOMETHING IN FRONT OF IT. A label that is nothing but a
     store key is not a shape anything composes, and reading one would be this component
     inventing a rendering for a string it was never handed. */
  const tail = all[all.length - 1]
  const hasKey = all.length >= 3 && tail !== undefined && STORE_KEY.test(tail)
  const storeKey = hasKey ? (tail as string) : null
  const parts = hasKey ? all.slice(0, -1) : all

  /* Whatever this component cannot rank renders whole — with the key still demoted beside it,
     because a fallback that drew the key at the site's own size would put the 44px figure back
     by a different door. `Pokémon code cards · pooled · 5/12` (`join.place_text`, D24) is what
     takes this path, and it is the honest render of a string that names no position: a pool has
     no coordinate to rank, so there is no key/figure pair to be had.

     `Box 3 · departed · B3 #36` USED TO TAKE IT AND NO LONGER DOES (D71). That label names a real
     box and is ranked below; drawing it here put the pre-D41 plain string back on two screens —
     44px and wrapped in the walk panel, the loudest row in the copies list — which is what a
     person saw the moment they marked a card sold. */
  const whole = (body: string): ReactNode =>
    storeKey === null ? (
      <>{body}</>
    ) : (
      <span className="position-plain" role="group" aria-label={label}>
        {body}
        <span className="position-storekey">{storeKey}</span>
      </span>
    )

  if (parts.length < 2) return whole(parts.join(' · '))

  const split = parts.map(seam)

  /* THE TERMINAL IS THE LAST PART, NOT THE THIRD. Anchoring to the end rather than to a fixed
     index is what keeps a two-part or four-part label honest: whatever the formula ends with is
     the finest thing said, and that is what the slot column answers with. */
  const terminal = split[split.length - 1]
  if (terminal === undefined) return whole(parts.join(' · '))

  const coarse = split.slice(0, -1)

  /* THE NUMERIC GUARD, AND IT IS THE ONE THING THIS COMPONENT HAS THAT D41's DID NOT.
     `#/inventory` draws only real positions, so promoting whatever sits after the last space was
     safe there. `#/review` is not: `app/tests/review.spec.ts` renders D24's pooled row as
     `Pokémon code cards · pooled`, which the shipped splitter turns into a path reading
     `POKÉMON CODE cards` — a key/value split of a phrase that has neither — and draws the
     lowercase word `pooled` as a 300.9px bold figure. Nothing breaks geometrically; the MEANING
     breaks, and no existing assertion sees it. A promoted slot is a slot number or it is nothing.

     The capture screen's `positionText` fallback used to be a second customer — `box 3, index 7`,
     which reached here only if someone later put a ' · ' in it. D92's sweep made that fallback a
     store key, so it is now the `parts.length < 2` bail above instead, drawn whole. The guard
     stands on the pooled case alone, which is enough on its own. */
  const numbered = NUMBER.test(terminal.value)

  /* A STATE TERMINAL IS RANKED RATHER THAN REFUSED, AND THE REFUSAL WAS A REGRESSION TO THE UI
     THIS COMPONENT REPLACED. `join.departed_label` composes `Box 3 · departed · B3 #36`, whose
     terminal is a word, so the guard above threw the WHOLE label out and `whole()` drew the raw
     server string at the site's payload size. Measured on the two sites that do not bail in CSS:
     the walk panel drew `Box 2 · departed` at 44px, wrapped onto two lines — the exact wrap D41
     exists to fix, on the exact screen it fixed it on — and the copies list drew it at 28px as
     the loudest thing in a list whose live rows are ranked. A sold card was the only card on
     `#/inventory` still rendered the pre-D41 way.

     WHAT THE GUARD WAS ACTUALLY PROTECTING is the FIGURE, not the treatment: D58 refuses a slot
     number for a card that is in no slot, and D68 adds that the store key must not take that
     number's place. Both are kept exactly — the slot column below draws no figure at all for a
     state — and the ranking is given back.

     THE STATE JOINS THE PATH AND CARRIES THE STORE KEY AS ITS VALUE. `DEPARTED B3 #36` is the same
     key/value shape as the `BOX 3` above it and the `SECTION 1` it stands in for, so a departed
     row costs the same two path lines a live row costs and reads in the same register. That is
     also what retires `.position-storekey`'s orphan sub-line for this label: the key is no longer
     a note under a string, it is the value of the thing that explains it.

     EVERY COARSE PART MUST STILL BE `<word> <number>`, WHICH IS WHAT KEEPS THE POOLED LABEL OUT.
     `Pokémon code cards · pooled · 5/12` (`join.place_text`, D24) has a lowercase terminal too,
     but its one coarse part seams to `POKÉMON CODE / cards` — the split of a phrase that has
     neither key nor value. That fails here and falls to `whole()`, which is the honest render of
     a string naming no position, and `.review-position:has(.position-parts)` still sizes it. */
  const stated =
    !numbered && STATE.test(terminal.value) && coarse.every((part) => NUMBER.test(part.value))

  if (!numbered && !stated) return whole(parts.join(' · '))

  const path = stated ? [...coarse, { key: terminal.value, value: storeKey ?? '' }] : coarse
  const slot = numbered ? terminal : null

  /* THE RUN FORM: the treatment's ranking without its geometry. Inline spans only — no flex, no
     column — so the label stays inside the line it was written into. Measured on the halt
     banner: 23px tall, identical to the plain string it replaces, and 14% narrower. */
  if (flow === 'run') {
    return (
      <span className="position-run" role="group" aria-label={label}>
        {path.map((part, at) => (
          <span className="position-run-path" key={part.key + part.value + at}>
            {part.key === '' ? null : `${part.key.toUpperCase()} `}
            {part.value === '' ? null : <b>{part.value}</b>}
          </span>
        ))}
        {/* NO VOID MARK INLINE, and that is the one place the two flows differ about a state.
            The stacked block draws a dash because it has a COLUMN whose emptiness has to be
            deliberate; a sentence has no column, so a dash mid-clause would be a mark the
            reader has to interpret rather than a slot left visibly unfilled. The state is
            already in the run above, which is the whole statement. */}
        {slot === null ? null : (
          <>
            {slot.key === '' ? null : (
              <span className="position-run-key">{slot.key.toUpperCase()}</span>
            )}
            <span className="position-run-num">{slot.value}</span>
          </>
        )}
      </span>
    )
  }

  return (
    <span className="position-parts" role="group" aria-label={label} data-lead={lead}>
      <span className="position-path">
        {path.map((part, at) => (
          <span key={part.key + part.value + at}>
            {part.key === '' ? null : `${part.key.toUpperCase()} `}
            {/* A KEY WITH NO VALUE IS A REAL PART, not a defect to render an empty `<b>` for:
                a state terminal reaching here without a store key beside it is the pre-D68
                spelling of the same label, and `DEPARTED` alone is the true thing to draw. */}
            {part.value === '' ? null : <b>{part.value}</b>}
            {at === 0 && boxNote !== null ? (
              <span className="position-path-note">{boxNote}</span>
            ) : null}
          </span>
        ))}
      </span>
      {/* THE NUMBER COLUMN, AND FOR A STATE IT IS DRAWN EMPTY RATHER THAN DROPPED. Dropping it
          would let the path slide left, so in the copies list — the one site that reads this
          block down a column (`lead='slot'`) — a sold row's `BOX 2` would start at a different
          x from every live row's, which is the ragged column that `lead` exists to prevent.
          It holds the reserve, and where there is a column to hold the stylesheet marks it with
          a dash: there is no number here, rather than a number that failed to arrive.

          THE MARK IS THE STYLESHEET'S AND THE ELEMENT IS THIS FILE'S, which is the split that
          keeps it out of the label. A dash in the DOM joins `textContent`, so `.browse-position`
          reads `BOX 2DEPARTED B2 #4—` to anything that greps the rendered text — a spec, a
          screenshot diff, a copy-paste — for a glyph that is pure typography and already
          `aria-hidden`. Empty here, `content` there. */}
      <span className="position-slot">
        {slot === null ? (
          <span className="position-void" aria-hidden="true" />
        ) : (
          <>
            {slot.key === '' ? null : (
              <span className="position-key">{slot.key.toUpperCase()}</span>
            )}
            <span className="position-num">{slot.value}</span>
          </>
        )}
      </span>
    </span>
  )
}