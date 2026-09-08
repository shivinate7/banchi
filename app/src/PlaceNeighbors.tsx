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
 * THE KEYS ARE `after` AND `before` — THE COMPOSER'S OWN WORDS, NOT A SECOND VOCABULARY.
 * `in front` / `behind` was built first, renders better as a physical pair, and is wrong in
 * a way a picture cannot show: it takes the NEIGHBOUR as its subject ("Galio is in front")
 * where `placeParts` takes THIS CARD ("this card is after Galio"). Both are true and they
 * are opposite framings, so a screen reader would have announced `before Conscription` over
 * a row reading `BEHIND Conscription`. Borrowing the composer's two words costs the physical
 * reading and buys an `aria-label` that says what the eye is looking at — the same argument
 * D22 makes against a friendly second spelling of a machine string.
 *
 * ONE DELIBERATE DEPARTURE FROM D41: its payload got SIZE and this one gets POSITION. Two
 * thirty-character strings cannot take a 44px treatment, and D41's own amendment measured
 * what that costs a list — 44px in the copies row is +86px and drops a copy below the fold.
 *
 * A CARD NOBODY HAS NAMED IS NOT A LANDMARK (D116, 2026-09-07). The server walks past an
 * unnamed on-hand card to the nearest one it can name, so this block stopped drawing the bare
 * `#270` the owner read as a sold card leaking into the ladder. It was never that — it was a
 * live card at a real count — but a figure names nothing you can recognise while flipping a
 * box, which is this block's only job. `Skipped` is what the walk costs, stated on the row.
 *
 * THE FULFILLER NEVER IMPORTS THIS. `CardLocations.tsx:FulfillerCard` draws the joined
 * sentence at `.card-locations-say`, 20px body, which `app/tests/fulfillment.spec.ts` floors
 * and D31 keeps unweakened. The firewall is the component graph and not a selector prefix —
 * the same rule `PositionLabel.tsx` records for itself, and for the same reason: a prefix is
 * what a refactor drops, and an import is not.
 */
import type { ReactNode } from 'react'

import { placeParts } from './server'
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
  /* A NAMELESS SIDE IS AN OLDER SERVER AND NOTHING ELSE, since D116: `_company` walks past a
     card nothing has named and answers null rather than naming it, so a current server never
     sends one. The slot fallback stays for the older one — never a blank, and never the
     INDEX, which is what it drew until D92: `#41` composed from the store key names a card
     that is not the one a hand counting to 41 arrives at, and the two diverge by every card
     that has left the box in front of it — 76 in box 3. `side.index` is still on the wire and
     must not be drawn bare. */
  if (side.name === null) return <b>#{side.slot}</b>

  const [champion, epithet] = seam(side.name)
  return (
    <>
      <b>{champion}</b>
      {epithet === null ? null : <span className="nb-rest">, {epithet}</span>}
    </>
  )
}

/* HOW FAR AWAY THE LANDMARK REALLY IS, on the rows where that is not one card (D116).
 *
 * The walk passes over an on-hand card nothing has named, so `after Rell, Noxus` can name the
 * card two along — and a hand counting from it lands one short, which is the failure D30 says
 * this sentence may never cause. The line is the price of the skip and is drawn only where
 * the skip happened: 27 rows on the owner's store, none in a fully identified box.
 *
 * ITS OWN LINE RATHER THAN A SUFFIX, and that is the same width argument the file's header
 * makes: these names run to thirty characters at a `ladder` flow already, and a trailing
 * clause is what would wrap them. A DEPARTED card is never counted here — the box closed up
 * over it (D58), so it is between nothing at all. */
function Skipped({ side }: { side: PlaceNeighbor }): ReactNode {
  const n = side.skipped ?? 0
  if (n === 0) return null
  return (
    <span className="nb-skip">
      {n} unidentified card{n === 1 ? '' : 's'} between
    </span>
  )
}

/** The two rows, or nothing at all.
 *
 * `placeParts` answers null — and this renders nothing, never a guess — for a pooled card
 * (D24: a count has no neighbours), an older server, a decoration the server degraded, and
 * the one card whose box holds nothing else.
 *
 * `flow` IS THE ONE CHOICE A SITE MAKES and it is about width, not taste: `ladder` puts the
 * key in a column beside the name and `stack` puts it on a line above, which costs ~72px less
 * of width and one more line of height. Nothing passes `stack` today; it is here because the
 * copies row's container query already cuts that row at 880px and a 231px place cell cannot
 * hold a key column beside a thirty-character name without breaking it. */
export function PlaceNeighbors({
  place,
  flow = 'ladder',
}: {
  place: Place | undefined
  flow?: 'ladder' | 'stack'
}): ReactNode {
  const parts = placeParts(place)
  if (parts === null) return null

  return (
    /* The composed sentence rides on `aria-label`, so a screen reader hears one sentence where
       the eye is given two rows — and `role="group"` is what makes that name apply to the
       block rather than being read past it. */
    <div className="nb" data-flow={flow} role="group" aria-label={parts.said}>
      {parts.prev === null ? null : (
        <p className="nb-row">
          <span className="nb-key">after</span>
          <span className="nb-name">
            <span className="nb-name-line">
              <Name side={parts.prev} />
            </span>
            <Skipped side={parts.prev} />
          </span>
        </p>
      )}
      {parts.next === null ? null : (
        <p className="nb-row">
          <span className="nb-key">before</span>
          <span className="nb-name">
            <span className="nb-name-line">
              <Name side={parts.next} />
            </span>
            <Skipped side={parts.next} />
          </span>
        </p>
      )}
    </div>
  )
}
