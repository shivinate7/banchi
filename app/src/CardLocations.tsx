import { useState, type ReactNode } from 'react'

import type { SearchCopy, SearchGroup, SectionDetail } from './types'
import { photoUrl, placeSentence } from './server'
import { PullConfirm } from './PullConfirm'
import { PositionBar, type Persona } from './PositionBar'
import './CardLocations.css'

/* One card, every copy of it, and where each copy physically is.
 *
 * THE FLOW THIS IS THE MIDDLE OF: a card sells, somebody types its name, and the answer has to
 * be good enough to walk to a box with. D7 keeps every copy as its own position with its own
 * photo precisely so that a sale can be recorded against one of them, and this is the screen
 * where that map stops being a data structure.
 *
 * ONE CORE, TWO SKINS, AND `persona` IS THE WHOLE OF THE DIFFERENCE. docs/DESIGN.md's "one
 * system, two densities" applied to a component rather than to a stylesheet: same data, same
 * order, same actions, same tokens. What changes is density, vocabulary and what is shown at
 * all. A second component was the alternative and it is the one this repo has already rejected
 * twice — it doubles the surface and gives two things to keep in step, and the day they drift
 * is the day the Fulfiller's screen shows a card the owner's does not.
 *
 * WHAT THE TWO SKINS MAY SAY IS NOT A STYLE PREFERENCE. The owner's screens speak the
 * pipeline's vocabulary on purpose — `Inventory.tsx` argues that being able to grep what you
 * saw is worth more to the person debugging a run than a consistent register. The Fulfiller's
 * may not: docs/DESIGN.md bans SKU, CSV, import, sync, batch, queue and staged from his copy
 * outright, and Fulfillment.tsx goes further and shows him no machine string at all. Both rules
 * are honoured below by construction rather than by care — the pipeline's words are only ever
 * read inside `persona === 'owner'` branches, so there is no path by which one reaches him.
 *
 * D7 WAS AMENDED ON 2026-08-23 AND THIS COMPONENT IS BUILT AFTER THE AMENDMENT, which is worth
 * saying because the obvious implementation is now the wrong one. Copies are fungible: `live`
 * is a quantity held against the SKU, not a flag on four particular cards, and "every unsold
 * copy is sellable" is the entry's own sentence. So there is no state to filter the sell
 * control on, no such thing as a copy that is backstock, and the count of what is for sale
 * comes off `group.listed` and never off the copies. A version of this that walked the copies
 * looking for `state === 'live'` would find none at all — those words are not members of
 * `store/master.py:STATES` any more — and would silently offer nothing.
 */

/** A copy the pipeline considers gone. The only terminal state a position carries, and the one
 *  word this file tests `SearchCopy.state` against — see the header for why there is no `live`
 *  to compare with. */
const SOLD = 'sold'

/* `retired` (D26) joined `sold` as a terminal state a position can carry. On the Fulfiller's
 * skin both read as the same fact — the copy is not in the boxes for him to pull — and
 * "Sold." would be a lie about a card the owner gave away, so the sentence stays honest and
 * generic for the non-sale door. Owner skin renders the state string verbatim as always. */
const RETIRED = 'retired'

/** What the Fulfiller is told about a copy, and the reason it is a lookup rather than the
 *  state string.
 *
 *  Fulfillment.tsx: no machine string appears on his screen. `identified` is a correct and
 *  useless thing to tell a retired man holding a card. Two sentences cover the two cases that
 *  matter to him — it is here, or it is gone — and the default says the safe one rather than
 *  falling through to the raw word, because a state added to `store/master.py` next year must
 *  not be the first machine string he has ever seen. */
function saidState(state: string): string {
  if (state === SOLD) return 'Sold.'
  if (state === RETIRED) return 'No longer in the boxes.'
  return 'In the boxes.'
}

/** `1 copy` / `4 copies`. A third small copy of this in the app; `Inventory.tsx` has the other
 *  two and neither file could import the other's on the day it was written. A shared module is
 *  the fix if a fourth arrives — the threshold `describeFailure` was held to before it moved
 *  into server.ts. */
function count(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

/** The collector number as the model returned it, unpadded, or null when there is none.
 *
 *  `pipeline/join.py:join_key` zero-fills to three digits to match the export's `Number`
 *  column; doing that here would put a string on screen that nothing in the run ever said.
 *  Same rule and the same shape as the card-shaped twin in `Inventory.tsx` — this one takes a
 *  group, which is why it is not that one. */
function collectorNumber(group: SearchGroup): string | null {
  const { number, printed_total } = group
  if (number === null || number.trim() === '') return null
  return printed_total === null ? number : `${number}/${printed_total}`
}

export type CardLocationsProps = {
  group: SearchGroup

  /** Required, not defaulted. A default would make the Fulfiller's skin the one you get by
   *  forgetting, or the owner's the one he gets by the same accident, and both are the kind of
   *  mistake that renders perfectly. */
  persona: Persona

  /** Record a sale of ONE copy — the position is the whole of the selection (D7, and
   *  `server.ts:markSold`). This component does not call the server: the caller owns the
   *  request, its refusals and its undo window, because those are one decision per screen and
   *  Fulfillment.tsx already holds a worked example of how much reasoning that is. */
  onSell: (copy: SearchCopy) => void

  /** The `SearchCopy.key` of a sale in flight, or null. One at a time, deliberately:
   *  `Store.write()` takes the file lock per call, so several at once stack against a lock and
   *  return their failures out of order — the same reason the review screen serialises. */
  busyKey: string | null

  /** Copies the caller has already sold and is holding a receipt for. An optimistic overlay
   *  and nothing more: the wire still says `identified` until the next read, and this is how
   *  the row stops offering to sell a card twice in the seconds before it. */
  soldKeys: ReadonlySet<string>

  /** Each box's own divider layout, keyed by `Place.box` — `GET /boxes`'s `sections_detail`,
   *  handed straight to every `PositionBar` this component draws and read nowhere else.
   *
   *  A MAP PER BOX AND NEVER ONE ARRAY, because a search group is not a box. D7 keeps every
   *  copy at its own position, so one card that just sold can have copies in three different
   *  boxes — and each box carries its own list of divider indices (D10, amended 2026-08-23),
   *  set where the operator physically put them. Today box 1 declares none and is rendered by
   *  the 25-rule while box 95 declares `[1, 24, 74, 84]`; nothing makes those two layouts
   *  resemble each other. One array handed to every bar would draw one box's dividers across
   *  another box's card, confidently, with nothing on screen saying it had guessed — which is
   *  the same wrong answer `PositionBar:spansOf` refuses to reach by arithmetic, arrived at
   *  through a prop shape instead. So the shape is the guard: there is no way to pass this
   *  that loses which box a layout belongs to.
   *
   *  OPTIONAL, AND THE BAR IS HONEST WITHOUT IT. `spansOf` falls back to the three runs a
   *  `Place` states on its own — the part of the box before this card's section, the section,
   *  the part after — so a caller holding no box records draws a coarser picture and never a
   *  wrong or an empty one. A map that is missing one box is the same case as no map at all:
   *  `Map.get` answers undefined and the fallback is the one `spansOf` already documents.
   *  Nothing here waits for it and nothing reports its absence.
   *
   *  BOTH SKINS GET IT. Same data, same order, same picture — the header's rule, and the
   *  Fulfiller needs it more than the owner does, since he is walking to a box he did not
   *  fill. One skin drawing the real dividers while the other drew this card's own section is
   *  precisely the drift one component with two skins exists to prevent. */
  sections?: ReadonlyMap<number, readonly SectionDetail[]>

  /** Which copy the caller is currently pointing at, or undefined. OWNER SKIN ONLY, and the
   *  Fulfiller's ignores it by construction rather than by care: his view has no walk and no
   *  cursor, so "the current one" is not a fact that exists on his screen. `Fulfillment.tsx`
   *  passes nothing and gets exactly what it got before.
   *
   *  WHY IT IS NEEDED AT ALL. Since D31's merge the owner reaches this list by selecting a card
   *  in the box walk, so one of these rows IS the card whose photograph is on screen beside it.
   *  Unmarked, a group of four identical copies gives no answer to "which of these am I looking
   *  at" — and the answer decides which slot a hand goes to. Carried as `aria-current` and drawn
   *  as ink against muted, the same mark the walk's own rows use, so it is one idiom rather than
   *  a second. */
  currentKey?: string

  /** Replaces the action slot for EVERY copy, sold ones included.
   *
   *  THE SOLD ONES ARE THE POINT OF THE PROP, not an edge case it happens to cover.
   *  docs/DESIGN.md requires undo on every mark-sold with at least a ten-second window, and
   *  this component is given `onSell` and no `onUndo` — so a screen that has to satisfy that
   *  row draws its own receipt-and-undo here, exactly as Fulfillment.tsx does with a per-sale
   *  timer it owns. Without it the Fulfiller skin below cannot meet that constraint on its
   *  own, and that is stated rather than hidden. */
  renderAction?: (copy: SearchCopy) => ReactNode
}

export function CardLocations(props: CardLocationsProps) {
  const { persona } = props

  /* Photos that failed to load, by copy key. Not derived from `has_photo`: that flag says the
   * server had bytes when it answered, and undo deletes a photo, so the load can still fail
   * between the search and the render. Fulfillment.tsx keeps the same state for the same
   * reason and swaps in a sentence that says where the card still is. */
  const [missing, setMissing] = useState<string[]>([])

  return persona === 'fulfiller' ? (
    <FulfillerCard {...props} missing={missing} setMissing={setMissing} />
  ) : (
    <OwnerRows {...props} />
  )
}

/* Shared by both skins so the two cannot disagree about what may be done to a copy. Sold is
 * the only thing that stops a sale, which is D7's "every unsold copy is sellable" stated as
 * code — there is deliberately no second condition here to keep in step with the decision. */
function isSold(copy: SearchCopy, soldKeys: ReadonlySet<string>): boolean {
  return copy.state === SOLD || copy.state === RETIRED || soldKeys.has(copy.key)
}

/* A POOLED COPY — the owner's ruling that a code card is a count, not a location
 * (`pipeline/games.py`'s `located` flag; "Code cards are pooled inventory, not located" in
 * docs/DECISIONS.md). Its place block arrives with `located: false`, a null label and the
 * game's display name, and this component's job splits accordingly: the position cell shows
 * the pooled fact, and the position BAR is not drawn at all — a marker some fraction into a
 * box that means nothing is worse than absent, because it is the kind of wrong a glance
 * believes. `!== false` so an older server's blocks, which omit the flag entirely, keep
 * reading as located. */
function isPooled(copy: SearchCopy): boolean {
  return copy.place.located === false
}

// ------------------------------------------------------------------------- the owner's skin

/* Dense rows, and the position bar on EVERY one of them.
 *
 * THE OWNER RULED AGAINST HOVER, and the ruling is the reason this is a row and not a tooltip.
 * "How far into the box" is the thing he opened the screen to learn, and a fact you have to
 * point at to see is a fact you compare one at a time — which is exactly what four copies of
 * one card in four boxes makes impossible. Every bar on screen at once is the feature.
 *
 * The budget is about 56px a row. It is a budget rather than a floor: a box with a name draws
 * a second line in the position cell and the row grows, because the alternative is truncating
 * either a position label or a box name and both are things somebody carries to a shelf.
 */
function OwnerRows({
  group,
  onSell,
  busyKey,
  soldKeys,
  sections,
  currentKey,
  renderAction,
}: Omit<CardLocationsProps, 'persona'>) {
  /* The machine line, in the shape `Inventory.tsx` established so that this screen and a
   * `curl /inventory` use one vocabulary. `sku: null` rather than a friendlier phrase for the
   * group that has none — a card is given a SKU when `emit` writes its row and never before,
   * and saying so plainly is more use to the owner than hiding it. */
  const number = collectorNumber(group)
  const meta =
    group.sku === null
      ? ['sku: null']
      : [
          `sku ${group.sku}`,
          ...(group.set_hint === null ? [] : [group.set_hint]),
          ...(number === null ? [] : [number]),
          ...(group.condition === null ? [] : [group.condition]),
        ]

  return (
    <section className="card-locations card-locations-owner">
      <header className="card-locations-head">
        <h3 className="card-locations-name">
          {group.names.length === 0 ? 'Not identified yet' : group.names.join(' / ')}
        </h3>
        <p className="card-locations-meta">{meta.join(' · ')}</p>

        {/* `listed N of CAP` reads the LIVE count against D7's cap, because that entry's cap is
            a cap on live quantity and nothing else. The other two counts are printed beside it
            rather than folded into it: `staged` and `live` are two facts about two different
            things — an import that was staged and never moved live has no live quantity at all
            — and a single number would hide exactly the box that is not earning. */}
        <p className="card-locations-counts">
          <span className="card-locations-listed">
            listed {group.listed.live} of {group.cap}
          </span>
          <span className="card-locations-onhand">on hand {group.on_hand}</span>
          <span className="card-locations-breakdown">
            pushed {group.listed.pushed} · staged {group.listed.staged} · live{' '}
            {group.listed.live}
          </span>
        </p>
      </header>

      <ul className="card-locations-rows">
        {group.copies.map((copy) => {
          const sold = isSold(copy, soldKeys)
          const pooled = isPooled(copy)
          /* D30's sentence for this copy, or null — see the render note below. Read once
             per row so the presence test and the rendering cannot disagree. */
          const between = placeSentence(copy.place)
          return (
            <li
              className="card-locations-row"
              key={copy.key}
              /* On the row and not on a control, because it marks WHICH COPY rather than which
                 thing is pressable — the row is not a button here, unlike the walk's. */
              aria-current={copy.key === currentKey ? 'true' : undefined}
            >
              <span className="card-locations-place">
                {pooled ? (
                  /* The pooled fact where the label would have gone — see `isPooled`. The
                     display name is the server's stamp off the registry, and the sub-line
                     carries the store key because it is the only handle a pooled copy has:
                     `pooled ·` in front so `5/2` cannot read as a position. Owner register,
                     greppable against the place block that produced it. */
                  <>
                    <span className="card-locations-label">
                      {copy.place.game_display ?? 'Pooled'}
                    </span>
                    <span className="card-locations-boxname">pooled · {copy.key}</span>
                  </>
                ) : (
                  <>
                    {/* The server's own label, displayed and never composed — types.ts states
                        the rule on `Place.label` and D10 is why it has teeth: Section and Card
                        are a view of the index against the box's current divider layout, and
                        the only formula for it in this repo is `pipeline/join.py:Position`. */}
                    <span className="card-locations-label">{copy.place.label}</span>
                    {copy.place.box_name === null ? null : (
                      <span className="card-locations-boxname">{copy.place.box_name}</span>
                    )}
                    {/* D30's digital half, quiet under the label: "between Mantine and
                        Thievul · 2 slots in this section are empty". This row's label names
                        the SLOT, and once the section holds permanent gaps a hand-count
                        stops reaching it; the neighbours restore the count, the gap tally
                        says why it came out short. `server.ts:placeSentence` is the one
                        composer and answers null — rendering nothing here — when there is
                        nothing true to say. The boxname class rather than a new one: it is
                        the same quiet sub-line register, and this file's stylesheet is not
                        this change's to grow. */}
                    {between === null ? null : (
                      <span className="card-locations-boxname">{between}</span>
                    )}
                  </>
                )}
              </span>

              {/* The box's own dividers where the caller has them, this card's own section
                  where it does not — `sections` says which, and the lookup is per copy
                  because two rows of one group can be in two differently divided boxes.
                  NO BAR AT ALL FOR A POOLED COPY — `isPooled` has the argument. */}
              {/* `sectionDepth` ON THE OWNER'S ROWS AND NOT THE FULFILLER'S. This is the row
                  the owner's own screenshot was taken of, and it is where the box scale alone
                  misleads: two copies of one card, one at `Section 1 · Card 1` drawing hard
                  left and one at `Section 3 · Card 1` drawing hard right, both of them the
                  first card of their section. The second bar is the answer to that, and
                  `PositionBar.tsx` argues the denominator it uses.

                  The Fulfiller's block below deliberately does NOT pass it — see the prop's
                  own note: a second caption in his view is a second sentence somebody decided
                  he needs to read, and that is the owner's call rather than a side effect of
                  an owner-side ask. */}
              {pooled ? null : (
                <PositionBar
                  place={copy.place}
                  persona="owner"
                  sections={sections?.get(copy.place.box)}
                  sectionDepth
                />
              )}

              {/* The pipeline's own word, verbatim. A friendly label here would be a second
                  vocabulary nothing audits — the drift docs/DESIGN.md shows reason codes as
                  machine strings to avoid — and this is the screen where being able to grep
                  what you saw is worth more than a consistent register. */}
              <span className="card-locations-state">{copy.state}</span>

              <span className="card-locations-action">
                {renderAction !== undefined ? (
                  renderAction(copy)
                ) : sold ? (
                  <span className="card-locations-gone">sold</span>
                ) : (
                  /* No accent fill. docs/DESIGN.md reserves the solid fill for a screen with
                     exactly one thing to do, and a list of copies is a screen with several —
                     filling all of them would teach the fill to mean "press something", which
                     is the drift the two-jobs rule exists to stop. */
                  <button
                    className="card-locations-sell"
                    type="button"
                    disabled={busyKey !== null}
                    onClick={() => onSell(copy)}
                  >
                    Mark sold
                  </button>
                )}
              </span>
            </li>
          )
        })}
      </ul>
    </section>
  )
}

// --------------------------------------------------------------------- the Fulfiller's skin

/* EVERY COPY IS ITS OWN CARD, which is the owner's explicit ruling and not the shape that fell
 * out of the layout. The alternative — one chosen copy drawn large with the rest listed as text
 * beneath it — makes the screen decide which copy he walks to, and it is wrong whenever the box
 * it picked is the one across the room. Copies are fungible (D7), so the choice is his and
 * every option has to carry the same information: a photo to confirm against, a position label
 * he can read at arm's length, a bar saying how far in, and its own control.
 *
 * KNOWN HAZARD, RECORDED RATHER THAN QUIETLY DIFFERENT. Fulfillment.tsx puts two steps between
 * looking at a photo and recording a sale — "Pull", then "Mark sold" in a different place —
 * because those were once one control and a double-tap sold the card. Here the action is one
 * press by specification. The photo is on the same card rather than a modal away, so the
 * photo-confirm the design asks for is satisfied structurally; what is not covered is the
 * overshoot. If it ever happens, Fulfillment.tsx's two-step is the fix to reach for first, and
 * `renderAction` is where it would go without touching this component.
 */
function FulfillerCard({
  group,
  onSell,
  busyKey,
  soldKeys,
  sections,
  renderAction,
  missing,
  setMissing,
}: Omit<CardLocationsProps, 'persona'> & {
  missing: string[]
  setMissing: (next: (held: string[]) => string[]) => void
}) {
  const number = collectorNumber(group)

  /* HIS HEADER CARRIES NO SKU, NO SET CODE AND NO STATE WORDS. The collector number stays
   * because it is printed on the card in his hand and is how he tells two printings apart; a
   * set id like `sv1` is not printed on anything and would be one more thing to explain. */
  const about = [
    ...(group.condition === null ? [] : [group.condition]),
    ...(number === null ? [] : [number]),
  ]

  return (
    <section className="card-locations card-locations-fulfiller">
      <header className="card-locations-head">
        <h2 className="card-locations-name">
          {group.names.length === 0 ? 'This card has no name yet' : group.names.join(' / ')}
        </h2>
        {about.length === 0 ? null : <p className="card-locations-say">{about.join(' · ')}</p>}

        {/* `for sale` is a quantity against the card, not against any one copy — D7 again, and
            the reason this number cannot be counted off the list below it. No cap and no
            breakdown: "2 of 4" needs the cap explained, and the words that explain it are on
            his banned list. */}
        <p className="card-locations-say">
          {count(group.on_hand, 'copy here', 'copies here')} · {group.listed.live} for sale
        </p>
      </header>

      <ul className="card-locations-copies">
        {group.copies.map((copy) => {
          const sold = isSold(copy, soldKeys)
          const noPhoto = !copy.has_photo || missing.includes(copy.key)
          /* A pooled copy should never reach this skin at all: Fulfillment.tsx drops every
           * one before this component renders, with the argument made there beside its
           * other filters — this skin's job is to send him to a box, and a pooled copy has
           * none. The guards below (`where`, the label line, the bar) are for the TYPE,
           * which says a label can be null now, and they render nothing rather than the
           * word "null" — never a second copy of the view's filter. */
          const where = copy.place.label

          /* D30's sentence, and HE is who the decision is really for: the Fulfiller
           * creates a permanent gap with every order he pulls, walks to boxes he did not
           * fill, and has nobody to ask why section 2 counts short. The composer is the
           * owner's same one — same data, same order, same sentence, the header's
           * two-skins rule — and its words pass his register: card names, plain "slots"
           * and "empty", nothing off the banned list. Its one degraded form, `#41` for a
           * neighbour nothing has named, is a slot number he can count to, not a machine
           * string. */
          const between = placeSentence(copy.place)

          return (
            <li key={copy.key}>
              {/* An article and not a button. Fulfillment.tsx makes the whole row the target so
                  that the smallest thing to hit is the size of the row — that rule is about a
                  row with no control in it, and this card carries one. Nesting a button inside
                  a button is invalid markup, and two overlapping targets on his screen is the
                  overshoot hazard the header comment is about. */}
              <article className="card-locations-copy">
                {noPhoto ? (
                  /* The photo is gone and the card is not. Says where it still is, because that
                     is the only part of this he needs to finish the job. */
                  <p className="card-locations-say">
                    The photo is missing. The card is still in the place below.
                  </p>
                ) : (
                  <img
                    // Keyed per copy so a failed load cannot leave one card's broken state
                    // attached to the next card's element.
                    key={copy.key}
                    className="card-locations-photo"
                    src={photoUrl(copy.place.box, copy.place.index)}
                    alt={where === null ? 'The card' : `The card in ${where}`}
                    onError={() =>
                      setMissing((held) => (held.includes(copy.key) ? held : [...held, copy.key]))
                    }
                  />
                )}

                {where === null ? null : <p className="card-locations-place-large">{where}</p>}
                {copy.place.box_name === null ? null : (
                  <p className="card-locations-say">{copy.place.box_name}</p>
                )}
                {/* Quiet, under the position label — see `between` above. The say class
                    because it is a sentence he reads, which also keeps it over the 20px
                    floor his whole view is asserted against. */}
                {between === null ? null : <p className="card-locations-say">{between}</p>}

                {/* The same lookup the owner's row makes, for the same reason. He is the one
                    walking to a box he did not fill, so the difference between the box's real
                    dividers and this card's own section is worth more on his screen than on
                    the owner's — and a skin that quietly drew the coarser one would be the
                    two-skins drift the header refuses. No bar for a pooled copy, as on the
                    owner's rows — not that one should ever be here; see `where` above. */}
                {isPooled(copy) ? null : (
                  <PositionBar
                    place={copy.place}
                    persona="fulfiller"
                    sections={sections?.get(copy.place.box)}
                  />
                )}

                <p className="card-locations-say">{saidState(copy.state)}</p>

                <div className="card-locations-action">
                  {renderAction !== undefined ? (
                    renderAction(copy)
                  ) : sold ? null : (
                    /* GUARDED, NEVER DISABLED. docs/DESIGN.md gives his view no disabled state
                       at all and `PullConfirm.disabled` is documented owner-side only — a
                       control that greys out under his finger is one he presses again harder.
                       A second press while the first is in flight does nothing instead, which
                       is the ruling Fulfillment.tsx already made and the reason `busyKey` is
                       read here rather than passed down.

                       No `keyHint`: his screens are touch and show no keys. */
                    <PullConfirm
                      label="Mark sold"
                      onConfirm={() => {
                        if (busyKey !== null) return
                        onSell(copy)
                      }}
                    />
                  )}
                </div>
              </article>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
