/* D30's neighbours, RANKED rather than joined — D41's move one line down.
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
 * removing them — applied to the sentence beneath it: a muted key column says which side, the
 * names start at one x, and finding the second is a vertical saccade rather than a hunt for a
 * word. Bolding the champions in place was the alternative and it is the move D41 already
 * declined: it adds a cue on top of the parse instead of deleting the parse, and having
 * landed on `Galio` the reader must still read the grammar to learn which side he is on.
 *
 * THE KEYS WERE `after` AND `before` UNTIL 2026-09-23, and LOC-07 found them read backwards: a
 * bare `AFTER Piercing Light` beside a name reads as "the next card is Piercing Light". They are
 * now `back` and `front`, a SIDE of this card in the owner's own orientation (card 1 at the far
 * back), with this card drawn between them. See `PlaceNeighbors` below.
 *
 * ONE DELIBERATE DEPARTURE FROM D41: its payload got SIZE and this one gets POSITION. Two
 * thirty-character strings cannot take a 44px treatment, and D41's own amendment measured
 * what that costs a list — 44px in the copies row is +86px and drops a copy below the fold.
 *
 * AN UNREAD CARD IS A NEIGHBOUR (the owner's ruling, 2026-09-24, LOC-28, amending D116). D116
 * walked past an unnamed on-hand card to a named one, because the bare `#270` it drew read as a
 * sold card. The owner ruled the unread card is the neighbour, said in words: "an unread card",
 * or "3 unread cards" for a run of them (`server.ts:neighborWords`). Never a bare figure.
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

/** The card and its two neighbours, drawn from the BACK of the box to the FRONT, or nothing.
 *
 * THE OWNER'S ORIENTATION, 2026-09-23 (D-a-card-is-counted-in-its-section): card 1 is at the far
 * back and the highest number nearest the body. So the ladder is a picture of the box standing up:
 * the neighbour toward the back (`prev`, the lower number) on the first row, this card on the
 * middle row, and the neighbour toward the front (`next`) on the last. The keys name a SIDE of
 * this card, `back` and `front`, which is what LOC-07 found `after`/`before` could not do: as a
 * bare label beside a name, `AFTER Piercing Light` read as "the next card is Piercing Light".
 *
 * A DEPARTED CARD SPEAKS IN THE PAST TENSE (LOC-09). Its middle row reads `was here`, and the
 * accessible name says where it was ("It was in front of ... and behind ..."). It never says the
 * card IS there. The accessible name is `placeParts`'s own sentence, the one the Fulfiller reads,
 * so the two personas hear one wording.
 *
 * `placeParts` answers null (and this renders nothing, never a guess) for a pooled card (D24), an
 * older server, a decoration the server degraded, and the card whose box holds nothing else. */
export function PlaceNeighbors({
  place,
  flow = 'ladder',
  departed = false,
}: {
  place: Place | undefined
  flow?: 'ladder' | 'stack'
  /** The card has left its box. Callers read it off `isDeparted(place)`. */
  departed?: boolean
}): ReactNode {
  const parts = placeParts(place, departed)
  if (parts === null) return null

  const said = parts.said
  const here = place?.card ?? null

  return (
    /* The sentence rides on `aria-label`, so a screen reader hears one sentence where the eye is
       given three rows, and `role="group"` is what makes that name apply to the block. */
    <div className="nb" data-flow={flow} data-departed={departed ? 'true' : undefined} role="group" aria-label={said}>
      {parts.prev === null ? null : (
        <p className="nb-row" data-side="back">
          <span className="nb-key">back</span>
          <span className="nb-name">
            <span className="nb-name-line">
              <Name side={parts.prev} />
            </span>
          </span>
        </p>
      )}
      <p className="nb-row nb-this" data-side="this">
        <span className="nb-key">{departed ? 'was' : 'this'}</span>
        <span className="nb-name">
          <span className="nb-name-line">
            {departed ? 'here' : here === null ? 'this card' : `#${here}`}
          </span>
        </span>
      </p>
      {parts.next === null ? null : (
        <p className="nb-row" data-side="front">
          <span className="nb-key">front</span>
          <span className="nb-name">
            <span className="nb-name-line">
              <Name side={parts.next} />
            </span>
          </span>
        </p>
      )}
    </div>
  )
}
