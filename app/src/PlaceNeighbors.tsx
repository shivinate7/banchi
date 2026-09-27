/* D30's neighbours, RANKED rather than joined, drawn as ONE LINE (Direction B, the owner's
 * pick, 2026-09-25, corrected the same day: "THIS #5 repeats Card 5. Remove it." —
 * `CardLocations.tsx:RowIdentity` already states the card's own figure once, so this line
 * names only what is beside it, `Name → Name`). This collapsed a three-row `back`/`this`/
 * `front` ladder that stood here from 2026-09-11 to 2026-09-25; the substance every rule below
 * argued for is unchanged, only the shape is. D260's own protection — card 1 at the far back
 * — is not carried by this component any more: it is carried by the two RULERS
 * (`PositionBar`'s own `BACK`/`FRONT` words), which is what the owner's correction scoped
 * "keep it on each ruler" to. `data-side="back"`/`"front"` still marks which name is which, so
 * a test can still read the orientation with no visible word for it.
 *
 * `Card 19` is the nineteenth card in the box and the neighbours are what let a hand count to
 * it. The sentence that used to say so was "between Galio, Indefaticable and Evelynn,
 * Entrancing", and the owner could not read it: "it's hard seeing galio and evelynn or
 * between kha and poppy, maybe we make longer (y axis) for them?"
 *
 * THE REASON IS THE NAMES, NOT THE LENGTH, and it is specific to this catalog. Every
 * Riftbound name is `Champion, Epithet` — 494 of 1368 carry a comma and none carries two — so
 * the running sentence holds commas INSIDE names and connectives BETWEEN them, and the
 * strongest punctuation in the string is the one that is not a boundary. It fires a median
 * five characters in; the real boundary (`and`) is thirty characters later. The reader parses
 * grammar to find two proper nouns, then regresses left to recover where the first began.
 *
 * SO THE CONNECTIVES ARE DELETED RATHER THAN RESTYLED. That is exactly D41's ruling for
 * `Box 2 · Section 1 · Card 14` — the owner rejected painting the interpuncts muted and chose
 * removing them — applied to the sentence beneath it: an arrow marks the seam, the names start
 * at one x on either side of it, and finding the second is a short saccade rather than a hunt
 * for a word. Bolding the champions in place was the alternative and it is the move D41 already
 * declined: it adds a cue on top of the parse instead of deleting the parse, and having
 * landed on `Galio` the reader must still read the grammar to learn which side he is on.
 *
 * THE ORIENTATION WAS `after`/`before` UNTIL 2026-09-23, and LOC-07 found them read backwards: a
 * bare `AFTER Piercing Light` beside a name reads as "the next card is Piercing Light". The
 * sides are ordered `back` then `front` now, the owner's own orientation (card 1 at the far
 * back), never the reverse.
 *
 * AN UNREAD CARD IS A NEIGHBOUR (the owner's ruling, 2026-09-24, LOC-28, amending D116). D116
 * walked past an unnamed on-hand card to a named one, because the bare `#270` it drew read as a
 * sold card. The owner ruled the unread card is the neighbour, said in words: "an unread card",
 * or "3 unread cards" for a run of them (`server.ts:neighborWords`). Never a bare figure.
 *
 * A DEPARTED CARD SPEAKS IN THE PAST TENSE (LOC-09), on `aria-label` alone: `placeParts`
 * conjugates `sits`/`was` off the `departed` flag this component still takes, so a screen
 * reader hears the right tense even though nothing about the two neighbour names changes on
 * screen when the card between them leaves.
 *
 * THE FULFILLER NEVER IMPORTS THIS. `CardLocations.tsx:FulfillerCard` draws the joined
 * sentence at `.card-locations-say`, 20px body, which `app/tests/fulfillment.spec.ts` floors
 * and D31 keeps unweakened. The firewall is the component graph and not a selector prefix —
 * the same rule `PositionLabel.tsx` records for itself, and for the same reason: a prefix is
 * what a refactor drops, and an import is not.
 */
import type { ReactNode } from 'react'

import { neighborWords, placeParts } from './server'
import type { Place, PlaceNeighbor } from './types'
import './PlaceNeighbors.css'

/* `Champion, Epithet` split on the FIRST `, ` — champion median 5 characters, epithet 23.
 *
 * A name of any other shape renders WHOLE rather than being cut at some other punctuation,
 * which is the refusal `PositionLabel` makes for a label it cannot parse. Pokemon names carry
 * no comma at all, so they take that branch and are drawn exactly as the server sent them.
 *
 * THE EPITHET IS DEMOTED AND NEVER DROPPED: 61 of 99 champions carry more than one — Master
 * Yi has 14 — so `Master Yi` alone names fourteen different cards and is not an identity. */
function seam(name: string): [string, string | null] {
  const at = name.indexOf(', ')
  return at < 1 ? [name, null] : [name.slice(0, at), name.slice(at + 2)]
}

function Name({ side }: { side: PlaceNeighbor }): ReactNode {
  /* A NAMELESS SIDE IS AN UNREAD CARD, OR A RUN OF THEM (LOC-28): said in words, muted, never
     the slot and never the INDEX (D92: `side.index` is on the wire and must not be drawn bare). */
  if (side.name === null) return <span className="nb-unread">{neighborWords(side)}</span>

  const [champion, epithet] = seam(side.name)
  return (
    <>
      <b>{champion}</b>
      {epithet === null ? null : <span className="nb-rest">, {epithet}</span>}
    </>
  )
}

/** The card's two neighbours, back then front (D260's orientation, card 1 at the far back), as
 *  one line: `Name → Name`, or the one side that exists at a box's own edge, or nothing.
 *
 *  `placeParts` answers null (and this renders nothing, never a guess) for a pooled card (D24), an
 *  older server, a decoration the server degraded, and the card whose box holds nothing else. */
export function PlaceNeighbors({
  place,
  departed = false,
}: {
  place: Place | undefined
  /** The card has left its box. Callers read it off `isDeparted(place)`. Reaches only
   *  `placeParts`, for `aria-label`'s tense (LOC-09) — nothing about the neighbour names
   *  themselves changes when this card, drawn nowhere in this component any more, departs. */
  departed?: boolean
}): ReactNode {
  const parts = placeParts(place, departed)
  if (parts === null) return null

  return (
    /* The sentence rides on `aria-label`, so a screen reader hears one full sentence
       (`placeParts`'s own composition, the one the Fulfiller reads too — one composer, one
       wording) where the eye is given two names and an arrow. `role="group"` is what makes
       that name apply to the whole line rather than to either name alone. */
    <p className="nb" role="group" aria-label={parts.said}>
      {parts.prev === null ? null : (
        <span className="nb-side" data-side="back">
          <Name side={parts.prev} />
        </span>
      )}
      {parts.prev !== null && parts.next !== null ? <span className="nb-arrow" aria-hidden="true" /> : null}
      {parts.next === null ? null : (
        <span className="nb-side" data-side="front">
          <Name side={parts.next} />
        </span>
      )}
    </p>
  )
}
