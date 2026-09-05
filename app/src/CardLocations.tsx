import { useState, type CSSProperties, type ReactNode } from 'react'

import type { SearchCopy, SearchGroup, SectionDetail } from './types'
import { isDeparted, photoUrl, placeSentence } from './server'
import { PlaceNeighbors } from './PlaceNeighbors'
import { PullConfirm } from './PullConfirm'
import { PositionBar, type Persona } from './PositionBar'
import { PositionLabel } from './PositionLabel'
import { collectorNumber } from './cardNumber'
import { Button, Icon, Pill } from './kit'
import './CardLocations.css'

/* One card, every copy of it, and where each copy physically is.
 *
 * ONE CORE, TWO SKINS, and `persona` is the whole of the difference: same data, same order,
 * same actions, same tokens. The owner's rows are dense and speak the pipeline's vocabulary;
 * the Fulfiller's cards are big, plain, and carry no machine string at all — his words only
 * ever come out of the `fulfiller` branch, so there is no path by which a SKU reaches him.
 *
 * Copies are fungible (D7): `live` is a quantity held against the SKU, not a flag on four
 * particular cards, so every unsold copy is sellable and the count of what is for sale comes
 * off `group.listed`, never off the copies.
 */

/* ------------------------------------------------- how old a LIVE reading is (D-rulings) ---
 *
 * A LIVE COUNT IS A FACT ABOUT WHEN THIS STORE LAST LOOKED, NOT A FACT ABOUT THE MARKETPLACE.
 * `store/master.py:Listing` says so in as many words — "an optimistic local estimate between
 * runs" — so no screen in this group draws the figure without saying how old it is.
 *
 * The stamp is `Listing.at` off `GET /inventory`. Every `set`/`bump` re-stamps it, so after a
 * `join` or a `reconcile --live` it is the moment TCGplayer's own figures were read in.
 *
 * IT IS JOINED CLIENT-SIDE BECAUSE `/search` DOES NOT CARRY IT: `SearchGroup.listed` is three
 * counts and no time at all on this branch. Both come off the same store record, so the join
 * is exact rather than a guess — but the day `listed` grows an `at` of its own, read that and
 * delete the join.
 */

const MINUTE = 60_000
const HOUR = 3_600_000
const DAY = 86_400_000

/** `3 days`, `4 hours`, `just now` — coarse on purpose; the exact moment is in the title. */
export function readingAgo(at: string | null | undefined): string | null {
  if (typeof at !== 'string' || at.trim() === '') return null
  const when = Date.parse(at)
  if (Number.isNaN(when)) return null
  const elapsed = Math.max(0, Date.now() - when)
  if (elapsed < 2 * MINUTE) return 'just now'
  if (elapsed < HOUR) return `${Math.floor(elapsed / MINUTE)} minutes ago`
  if (elapsed < DAY) {
    const hours = Math.floor(elapsed / HOUR)
    return `${hours} hour${hours === 1 ? '' : 's'} ago`
  }
  const days = Math.floor(elapsed / DAY)
  return `${days} day${days === 1 ? '' : 's'} ago`
}

/** The moment itself, as a person's clock says it — the hover behind the coarse phrase. */
export function readingExact(at: string | null | undefined): string | undefined {
  if (typeof at !== 'string') return undefined
  const when = new Date(at)
  if (Number.isNaN(when.getTime())) return undefined
  return when.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/** `read 3 days ago`, drawn beside a live count and never louder than it. */
export function ReadingAge({ at, className }: { readonly at?: string | null; readonly className?: string }) {
  const ago = readingAgo(at)
  return (
    <span
      className={['inv-readage', ago === null ? 'is-unread' : '', className ?? ''].filter(Boolean).join(' ')}
      title={
        ago === null
          ? 'Nothing has written a listing figure for this yet.'
          : `This store last wrote these listing figures ${readingExact(at)}.`
      }
    >
      {ago === null ? 'not read yet' : `read ${ago}`}
    </span>
  )
}

/** An open order that has named one copy, keyed by the copy's store key. Structural, so the
 *  screen's own richer `Wanted` fits without a second import of it. */
export type CopyClaim = { readonly order: string }

/** A copy the pipeline considers gone. */
const SOLD = 'sold'

/** The other door out (D26). On the Fulfiller's skin both read as the same fact. */
const RETIRED = 'retired'

/** What the Fulfiller is told about a copy — two sentences, never the raw state word. */
function saidState(state: string): string {
  if (state === SOLD) return 'Sold.'
  if (state === RETIRED) return 'No longer in the boxes.'
  return 'In the boxes.'
}

function count(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

/* HOW MUCH ROOM IS LEFT UNDER THE CEILING — said as headroom, never as a second live count.
 *
 * `group.listable` is D7's `min(cap, on hand)` computed by the server: what the rule permits
 * for THIS SKU. Drawn as `up to 3 may be live` it used the same numeral as the live figure two
 * lines above it, and the two sentences could not be told apart — is three live, or may three
 * be? Headroom is the same fact in terms nothing else on the panel is measured in. */
function headroom(group: SearchGroup): string {
  const room = group.listable - group.listed.live
  if (group.listable === 0) return 'No copies can go live'
  if (room > 0) return `Room for ${room} more live`
  if (room === 0) return `At the ceiling of ${group.listable}`
  return `${-room} over the ceiling of ${group.listable}`
}

export type CardLocationsProps = {
  group: SearchGroup

  /** Required, not defaulted: a skin you get by forgetting is a skin nobody chose. */
  persona: Persona

  /** Record a sale of ONE copy — the position is the whole of the selection. The caller owns
   *  the request, its refusals and its undo window. */
  onSell: (copy: SearchCopy) => void

  /** The `SearchCopy.key` of a sale in flight, or null. One at a time. */
  busyKey: string | null

  /** Copies the caller has already sold and is holding a receipt for. An optimistic overlay. */
  soldKeys: ReadonlySet<string>

  /** Each box's own divider layout, keyed by `Place.box` — handed to every `PositionBar`.
   *  A map per box and never one array, because a search group is not a box. Optional; the
   *  bar is honest without it. */
  sections?: ReadonlyMap<number, readonly SectionDetail[]>

  /** Which copy the caller is currently pointing at, or undefined. Owner skin only.
   *
   *  A STATEMENT OF WHERE THE WALK STANDS, NEVER A RECOMMENDATION. The row it names is drawn
   *  in full like every other and keeps its own controls; all it gets extra is a quiet
   *  `Viewing` marker and a neutral rail, because the owner picks which physical copy to
   *  reach for and the UI does not get a vote. */
  currentKey?: string

  /** When this store last wrote this SKU's listing figures — `Listing.at` off `GET
   *  /inventory`. Optional; absent draws `not read yet` rather than a bare live count. */
  listedAt?: string | null

  /** Which copies an open order has already named, by copy key. A claimed copy is DRAWN AND
   *  MARKED, never hidden and never un-pressable: this screen is also where a walk-in sale is
   *  recorded, and the owner ruled that `Mark sold` stays. */
  claims?: ReadonlyMap<string, CopyClaim>

  /** Walk to this copy. Owner skin only, optional; never drawn on the current copy or a pooled
   *  one. */
  onGoTo?: (copy: SearchCopy) => void

  /** Replaces the action slot for EVERY copy, sold ones included — this is how a screen draws
   *  its own undo. */
  renderAction?: (copy: SearchCopy) => ReactNode
}

export function CardLocations(props: CardLocationsProps) {
  const { persona } = props

  /* Photos that failed to load, by copy key. */
  const [missing, setMissing] = useState<string[]>([])

  return persona === 'fulfiller' ? (
    <FulfillerCard {...props} missing={missing} setMissing={setMissing} />
  ) : (
    <OwnerRows {...props} />
  )
}

/* Sold is the only thing that stops a sale — D7's "every unsold copy is sellable" as code. */
function isSold(copy: SearchCopy, soldKeys: ReadonlySet<string>): boolean {
  return copy.state === SOLD || copy.state === RETIRED || soldKeys.has(copy.key)
}

/* A pooled copy — a count, not a location (D24). `!== false` so an older server's blocks keep
   reading as located. */
function isPooled(copy: SearchCopy): boolean {
  return copy.place.located === false
}

/** The tone of a state pill. Shared with `BoxBrowse` so the two draw one register. */
export function stateTone(state: string): 'default' | 'ok' | 'warn' | 'accent' {
  if (state === SOLD) return 'ok'
  if (state === RETIRED || state === 'moved') return 'warn'
  if (state === 'captured') return 'accent'
  return 'default'
}

/** A card state as a word — the one map every state pill on the owner's screens draws
 *  through, so a raw wire value is never printed as a label. An unknown state is still
 *  shown, capitalised, rather than dropped. */
const STATE_WORDS: Readonly<Record<string, string>> = {
  captured: 'Captured',
  identified: 'Identified',
  sold: 'Sold',
  retired: 'Retired',
  moved: 'Moved',
}
export function stateLabel(state: string): string {
  const known = STATE_WORDS[state]
  if (known !== undefined) return known
  const raw = String(state).replace(/_/g, ' ')
  return raw.charAt(0).toUpperCase() + raw.slice(1)
}

// ------------------------------------------------------------------------- the owner's skin

/* EVERY COPY OF THIS CARD, AND WHERE EACH ONE PHYSICALLY IS — the panel the owner picks a copy
 * out of, so three rules bind it:
 *
 *   1. Every copy is drawn, in full. No copy is folded away for being the one the walk happens
 *      to be standing on, and none is dropped for being far away, sold or spoken for.
 *   2. Nothing is preselected and nothing is recommended. The row the walk stands on carries a
 *      quiet `Viewing` marker and a neutral rail — a statement of where you are, not a nudge —
 *      and it keeps its own controls like every other row.
 *   3. A copy an open order has already named is MARKED, never hidden and never disabled: this
 *      is also where a walk-in sale is recorded, and `Mark sold` stays on every live row.
 *
 * The position lens is on every row: "how far into the box" is the thing the owner opened the
 * screen to learn, and every bar on screen at once is the feature.
 */
function OwnerRows({
  group,
  onSell,
  busyKey,
  soldKeys,
  sections,
  currentKey,
  listedAt,
  claims,
  onGoTo,
  renderAction,
}: Omit<CardLocationsProps, 'persona'>) {
  const number = collectorNumber(group)

  /* HOW MANY DIGITS THIS LIST'S SLOT COLUMN HAS TO HOLD, which is the one term of that column
     that is DATA rather than typography (`CardLocations.css`'s `--pos-slot-key` is the other).
     A row cannot compute it — it cannot see what its siblings drew — so the list does, over the
     copies it is about to render, and every row reserves the same width from it.

     `place.card` AND NOT THE LABEL. It is the same field `pipeline/join.py:Position.label`
     composes its last part from, it is already on the wire, and it is null exactly for the rows
     that draw no figure (D58, D71) — so reading it needs no second copy of `PositionLabel`'s
     seam here, which is the duplication D67 and D92 both record.

     Floored at three so no list renders narrower than every store, fixture and screenshot did
     before this existed. */
  const slotDigits = Math.max(
    3,
    ...group.copies.map((copy) =>
      copy.place.card === null ? 0 : String(copy.place.card).length,
    ),
  )
  /* The machine strings — SKU, set code, number — in mono; the condition is a phrase and is
     drawn beside them in the UI face. */
  const meta =
    group.sku === null
      ? ['no SKU yet']
      : [
          `SKU ${group.sku}`,
          ...(group.set_hint === null ? [] : [group.set_hint]),
          ...(number === null ? [] : [number]),
        ]

  return (
    <section className="card-locations card-locations-owner">
      <header className="card-locations-head">
        <h3 className="bn-section-title card-locations-title">Every copy of this card</h3>
        <div className="card-locations-stats">
          <div className="bn-stat card-locations-stat">
            <span className="bn-stat-value">{group.copies.length}</span>
            <span className="bn-stat-label">{group.copies.length === 1 ? 'copy' : 'copies'}</span>
          </div>
          <div className="bn-stat card-locations-stat">
            <span className="bn-stat-value">{group.on_hand}</span>
            <span className="bn-stat-label">in the boxes</span>
          </div>
          {/* THE LIVE FIGURE NEVER STANDS ALONE. It is what this store last believed, so its
              reading age sits under it, quieter than the count itself. */}
          <div className="bn-stat card-locations-stat card-locations-live">
            <span className="bn-stat-value">
              <span className="bn-dot bn-dot-live" aria-hidden="true" />
              {group.listed.live}
            </span>
            <span className="bn-stat-label">live on TCGplayer</span>
            <ReadingAge at={listedAt} />
          </div>
        </div>

        <p className="card-locations-meta">
          <span className="card-locations-meta-mono">{meta.join(' · ')}</span>
          {group.condition === null ? null : (
            <span className="card-locations-cond">{group.condition}</span>
          )}
        </p>
        {/* THE CEILING, SAID SO IT CANNOT BE READ AS A SECOND READING. `up to 3 may be live`
            sat two lines under `3 live on TCGplayer` and used the same figure to mean the
            other thing, so a reader could not tell whether three ARE live or three MAY be.
            Headroom is the honest form of the same fact. */}
        <p className="card-locations-counts">
          Pushed {group.listed.pushed} · Staged {group.listed.staged} · {headroom(group)}
        </p>
      </header>

      <ul
        className="card-locations-rows bn-stagger"
        style={{ ['--pos-slot-digits']: slotDigits } as CSSProperties}
      >
        {group.copies.map((copy, i) => {
          const sold = isSold(copy, soldKeys)
          const pooled = isPooled(copy)
          const departed = isDeparted(copy.place)
          const current = copy.key === currentKey
          const label = copy.place.label
          const claim = claims?.get(copy.key) ?? null

          /* The walk-to for THIS copy, or null when there is nowhere to send anyone. */
          const goesTo = onGoTo === undefined || pooled || current ? null : () => onGoTo(copy)
          /* No bar for a pooled copy (a count has no place), a departed one (a bar cannot draw
             a card that is in no place) — or the copy the walk is STANDING ON, whose lens is
             already drawn full size in the location card ~150px above this list, with the same
             `#N of M` caption under it. Two identical bars a screen apart read as a rendering
             fault, not as hero-and-list. The row itself stays, in full, with its own controls:
             what goes is the duplicate widget, not the row. */
          const noBar = pooled || departed || current

          return (
            <li
              className={[
                'card-locations-row',
                noBar ? 'is-nobar' : '',
                sold || departed ? 'is-gone' : '',
                current ? 'is-current' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              key={copy.key}
              style={{ ['--i' as string]: i }}
              aria-current={current ? 'true' : undefined}
            >
              <span className="card-locations-place">
                {pooled ? (
                  <>
                    <span className="card-locations-label">
                      {copy.place.game_display ?? 'Pooled'}
                    </span>
                    <span className="card-locations-boxname">pooled · {copy.key}</span>
                  </>
                ) : (
                  <>
                    {/* The server's own label, displayed and never composed. Slot-first here
                        because this is a list: the figures land in a hard column. Where the
                        caller offers a walk-to, the same rendering sits inside a button. */}
                    <span className="card-locations-label">
                      {label === null ? null : goesTo === null ? (
                        <PositionLabel label={label} lead="slot" boxNote={copy.place.box_name} />
                      ) : (
                        <button
                          className="card-locations-goto"
                          type="button"
                          aria-label={`Walk to ${label}`}
                          onClick={goesTo}
                        >
                          <PositionLabel label={label} lead="slot" boxNote={copy.place.box_name} />
                          <Icon name="arrowUpRight" size={14} className="card-locations-goto-icon" />
                        </button>
                      )}
                    </span>
                    <PlaceNeighbors place={copy.place} />
                  </>
                )}
              </span>

              {noBar ? null : (
                <PositionBar
                  place={copy.place}
                  persona="owner"
                  sections={sections?.get(copy.place.box)}
                  sectionDepth
                />
              )}

              <span className="card-locations-state">
                {current ? (
                  <Pill icon="eye" outline className="card-locations-viewing">
                    Viewing
                  </Pill>
                ) : null}
                {claim === null ? null : (
                  <a
                    className="bn-pill bn-pill-warn card-locations-claim"
                    href="#/orders"
                    aria-label={`Order ${claim.order} is waiting on this copy`}
                    title={`Order ${claim.order} is waiting on this copy. It is still yours to sell from here.`}
                  >
                    <Icon name="cart" size={12} />
                    Wanted
                    {/* The order number itself is 21 characters. It is drawn where the panel is
                        wide enough to hold it, and the mark alone where it is not — the number
                        is on the location card above, in the title, and one press away. */}
                    <span className="card-locations-claim-id">{claim.order}</span>
                  </a>
                )}
                <Pill tone={stateTone(copy.state)}>{stateLabel(copy.state)}</Pill>
              </span>

              {/* The action, or what stands where one would. A sold copy's own state pill
                  already says so; only an optimistic sale whose re-read is still in flight
                  needs a word. */}
              <span className="card-locations-action">
                {renderAction !== undefined ? (
                  renderAction(copy)
                ) : sold ? (
                  copy.state === SOLD || copy.state === RETIRED ? null : <Pill tone="ok">Sold</Pill>
                ) : (
                  <Button
                    size="sm"
                    busy={busyKey === copy.key}
                    disabled={busyKey !== null && busyKey !== copy.key}
                    onClick={() => onSell(copy)}
                  >
                    Mark sold
                  </Button>
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

/* Every copy is its own card: a photo to confirm against, a position label he can read at
 * arm's length, a bar saying how far in, and its own control. Unchanged by the owner-side
 * rebuild; every floor in docs/DESIGN.md's constraints table binds here. */
function FulfillerCard({
  group,
  onSell,
  busyKey,
  soldKeys,
  sections,
  listedAt,
  renderAction,
  missing,
  setMissing,
}: Omit<CardLocationsProps, 'persona'> & {
  missing: string[]
  setMissing: (next: (held: string[]) => string[]) => void
}) {
  const number = collectorNumber(group)

  /* His header carries no SKU, no set code and no state words. */
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
        {/* HIS LIVE COUNT CARRIES ITS AGE TOO, in his words rather than in the pipeline's —
            "for sale" reads as a fact about the shop when it is a fact about the last time
            this store looked. Drawn only when the caller hands over the stamp, because
            "not read yet" is a sentence about plumbing and he is owed none of those.
            `Fulfillment.tsx` has to pass `listedAt` for this half to appear. */}
        <p className="card-locations-say">
          {count(group.on_hand, 'copy here', 'copies here')} · {group.listed.live} for sale
          {readingAgo(listedAt) === null ? '' : `, counted ${readingAgo(listedAt)}`}
        </p>
      </header>

      <ul className="card-locations-copies">
        {group.copies.map((copy) => {
          const sold = isSold(copy, soldKeys)
          const noPhoto = !copy.has_photo || missing.includes(copy.key)
          const where = copy.place.label
          const between = placeSentence(copy.place)

          return (
            <li key={copy.key}>
              <article className="card-locations-copy">
                {noPhoto ? (
                  <p className="card-locations-say">
                    The photo is missing. The card is still in the place below.
                  </p>
                ) : (
                  <img
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
                {between === null ? null : <p className="card-locations-say">{between}</p>}

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
