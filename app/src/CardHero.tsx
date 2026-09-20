/* app/src/CardHero.tsx — the card pane's shared pieces, lifted out of `BoxBrowse.tsx` so
 * `#/orders`' walk can reuse them (`docs/specs/order-walk-plan.md` §13: "Inventory's card
 * pane, unchanged... the photograph, Every copy of this card with its triad, the SKU line,
 * ... Details"). Moved rather than forked, on the owner's own instruction: "if reusing the
 * pane needs a component lifted out of Inventory.tsx into its own file so both screens
 * import it, do that — that is added to inventory and both screens get it, not a fork."
 *
 * WHAT MOVED, AND WHY IT IS SAFE TO: every function and type below is PURE over its own
 * arguments — `Row`/`InventoryCard`, a `MarketRead`, a listings map — with no closure over
 * `BoxBrowse.tsx`'s own component state (the printing chooser, the review queue, reshoot).
 * `BoxBrowse.tsx` imports them back and its own JSX is UNCHANGED; `app/tests/inventory.spec.ts`
 * is what proves that (D96's "the screens answer to the owner's interview" — this repo's own
 * suite is the interview here).
 *
 * `CardHeroHead` IS NEW, not moved: `BoxBrowse.tsx`'s own hero head also draws the printing-
 * chooser chip and the review-queue chip, both wired to state this file cannot see and both
 * left for `BoxBrowse.tsx` to keep drawing itself. This component draws the rest of that
 * head — name, number line, finish/rarity pills, the state pill — off the same helpers, in
 * the same `.browse-hero-*` classes, so the two screens' headers render identically wherever
 * they overlap. `actions` is an open slot for whatever a caller puts beside the title —
 * `BoxOps`'s `CardOps` menu is Inventory-only editing (retire, move, correct claims) and is
 * never passed in from `#/orders`.
 *
 * `CardDetailsSection` IS MOVED WHOLE — `BoxBrowse.tsx`'s own `<details className="bn-panel
 * browse-details">` block, unchanged, now owning its own open/closed state instead of reading
 * it off `BoxBrowse.tsx`'s local `detailsOpen` — the same default (open unless `phone`) and
 * the same manual-wins-until-toggled behaviour, just kept inside the component that draws it.
 */

import { useState, type ReactNode } from 'react'

import { ReadingAge } from './CardLocations'
import { collectorNumber } from './cardNumber'
import { readingAgo, stateLabel, stateTone } from './cardState'
import { Icon, Pill } from './kit'
import { photoUrl } from './server'
import type { InventoryCard, Listing, PricingPayload } from './types'

/** One inventory row: the store key plus the card it names. `BoxBrowse.tsx` re-exports this
 *  (`export type { Row } from './CardHero'`) so `Inventory.tsx`'s own import keeps working. */
export type Row = { key: string; card: InventoryCard }

/* ------------------------------------------------------------------------------ pure facts */

/** The card's name, or null — an empty string is not a name (the pipeline writes `""` for a
 *  card it could not read). */
export function nameOf(card: InventoryCard): string | null {
  const name = card.name
  return typeof name === 'string' && name.trim() !== '' ? name.trim() : null
}

export function numberCell(card: InventoryCard): string {
  return collectorNumber(card) ?? 'none'
}

/** An enum value drawn as a word: `reverse_holofoil` → `Reverse Holofoil`. */
export function titleCase(raw: string): string {
  return raw
    .split(/[_\s]+/)
    .filter((word) => word !== '')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

const GAME_WORDS: Record<string, string> = {
  pokemon: 'Pokémon',
  pokemon_code: 'Pokémon code cards',
  one_piece: 'One Piece',
}
export function gameLabel(game: string): string {
  return GAME_WORDS[game] ?? titleCase(game)
}
export function gameWord(card: InventoryCard): string | null {
  if (card.place?.game_display) return card.place.game_display
  if (card.game === null) return null
  return gameLabel(card.game)
}

function isCode(text: string): boolean {
  return /^[a-z0-9]+(?:_[a-z0-9]+)+$/.test(text)
}

/** A set-valued claim, rendered — a bare string reads as a one-member set. */
export function claimText(claim: string | string[] | null, word: (member: string) => string = (member) => member): string {
  const members = claimList(claim).map(word)
  return members.length === 0 ? 'none recorded' : members.join(' · ')
}

export function claimList(claim: string | string[] | null): string[] {
  return (typeof claim === 'string' ? [claim] : (claim ?? [])).filter(
    (member) => typeof member === 'string' && member.trim() !== '',
  )
}

/* ------------------------------------------------------------------------------ the market */

export type MarketRead =
  | { kind: 'table'; at: number | null; rows: Record<string, string | null> }
  | { kind: 'absent'; why: string }

export function marketTable(payload: PricingPayload): MarketRead {
  const rows: Record<string, string | null> = {}
  for (const priced of payload.pricing?.skus ?? []) {
    for (const at of priced.positions ?? []) {
      rows[`${at.box}/${at.index}`] = priced.snap?.market ?? null
    }
  }
  return { kind: 'table', at: payload.written_at ?? null, rows }
}

function marketText(card: InventoryCard, read: MarketRead | undefined): string {
  if (card.run === null) return 'not joined yet'
  if (read === undefined) return 'reading…'
  if (read.kind === 'absent') return read.why

  const price = read.rows[`${card.box}/${card.index}`]
  if (price === undefined) return 'no row in this run'
  if (price === null) return 'no_market_data'

  const ago = read.at === null ? null : readingAgo(new Date(read.at * 1000).toISOString())
  if (ago === null) return `$${price} · no age`
  return `$${price} · read ${ago}`
}

/* `mono` is a machine string; `money` is Inter with tabular figures. `node` draws instead of
 * `value` where the fact carries something quieter beside it. */
type Detail = { label: string; value: string; kind?: 'mono' | 'money'; node?: ReactNode }

function marketFact(card: InventoryCard, read: MarketRead | undefined): Detail {
  const value = marketText(card, read)
  if (!value.startsWith('$') || read === undefined || read.kind !== 'table') {
    return { label: 'Market', value, kind: isCode(value) ? 'mono' : undefined }
  }
  const price = read.rows[`${card.box}/${card.index}`]
  return {
    label: 'Market',
    value,
    kind: 'money',
    node: (
      <span className="browse-fact-live">
        <span className="bn-tnum">${price}</span>
        <ReadingAge at={read.at === null ? null : new Date(read.at * 1000).toISOString()} />
      </span>
    ),
  }
}

function listingFact(card: InventoryCard, listings: Readonly<Record<string, Listing>>): Detail {
  const sku = card.sku === null ? '' : card.sku.trim()
  if (sku === '') return { label: 'Listed', value: 'no SKU yet' }
  const listing = listings[sku]
  if (listing === undefined) return { label: 'Listed', value: 'no import row yet' }
  return {
    label: 'Listed',
    value: `${listing.live} live`,
    node: (
      <span className="browse-fact-live">
        <span className="bn-tnum">{listing.live}</span> live
        <ReadingAge at={listing.live_as_of} />
      </span>
    ),
  }
}

/** When this card was photographed, as a person says it. */
function capturedText(stamp: string | null): string {
  if (stamp === null) return 'not recorded'
  const at = new Date(stamp)
  if (Number.isNaN(at.getTime())) return stamp

  const clock = at
    .toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
    .replace(/\s?([AP])M/i, (_m, half: string) => half.toLowerCase() + 'm')
  const day = at.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  const year = at.getFullYear()
  const suffix = year === new Date().getFullYear() ? '' : ` ${year}`
  return `${clock} · ${day}${suffix}`
}

type FactGroup = { title: string; facts: Detail[] }

/** Identity, Claims, Provenance — the three groups `#/inventory`'s Details disclosure draws,
 *  and the exact grouping this file's own header describes moving whole. */
export function factGroupsOf(
  card: InventoryCard,
  market: MarketRead | undefined,
  listings: Readonly<Record<string, Listing>>,
): FactGroup[] {
  return [
    {
      title: 'Identity',
      facts: [
        { label: 'Card', value: nameOf(card) ?? 'not identified yet' },
        { label: 'Number', value: numberCell(card), kind: 'mono' },
        { label: 'Game', value: gameWord(card) ?? 'not recorded' },
        { label: 'Set hint', value: card.set_hint ?? 'none', kind: 'mono' },
      ],
    },
    {
      title: 'Claims',
      facts: [
        { label: 'Finish', value: claimText(card.metadata_finish, titleCase) },
        { label: 'Rarity', value: claimText(card.rarity_claim, titleCase) },
        { label: 'Note', value: card.note ?? 'none' },
      ],
    },
    {
      title: 'Provenance',
      facts: [
        { label: 'State', value: stateLabel(card.state) },
        { label: 'Captured', value: capturedText(card.captured_at) },
        { label: 'Run', value: card.run ?? 'not identified yet', kind: 'mono' },
        { label: 'Confidence', value: card.confidence === null ? 'none recorded' : titleCase(card.confidence) },
        marketFact(card, market),
        listingFact(card, listings),
      ],
    },
  ]
}

/* -------------------------------------------------------------------------- the hero head */

/** The header both screens share: name, the number line, the finish/rarity pills, the state
 *  pill — `BoxBrowse.tsx`'s own `.browse-hero-*` classes. `actions` is where a caller's own
 *  edit menu goes (Inventory's `CardOps`); `#/orders` leaves it empty — Mark sold lives in the
 *  copies list below, not up here, and retire/move/reshoot are Inventory-only. */
export function CardHeroHead({
  card,
  game,
  actions,
}: {
  readonly card: InventoryCard
  readonly game: string | null
  readonly actions?: ReactNode
}) {
  const name = nameOf(card)
  const number = numberCell(card)
  return (
    <div className="browse-hero-head">
      <div className="browse-hero-text">
        <h2 className={name === null ? 'browse-hero-name is-unnamed' : 'browse-hero-name'}>{name ?? 'Not identified yet'}</h2>
        <p className="browse-hero-sub">
          {[number === 'none' ? null : number, card.set_hint, game]
            .filter((part): part is string => typeof part === 'string' && part !== '')
            .map((part, i) => (
              <span key={`${part}-${i}`} className={i === 0 && number !== 'none' ? 'browse-hero-number' : undefined}>
                {part}
              </span>
            ))}
        </p>
        <div className="browse-hero-chips">
          {claimList(card.metadata_finish).map((finish) => (
            <Pill key={`f-${finish}`} icon="sparkles">
              {titleCase(finish)}
            </Pill>
          ))}
          {claimList(card.rarity_claim).map((rarity) => (
            <Pill key={`r-${rarity}`}>{titleCase(rarity)}</Pill>
          ))}
          <Pill tone={stateTone(card.state)} outline={card.state === 'identified'}>
            {stateLabel(card.state)}
          </Pill>
        </div>
      </div>
      {actions}
    </div>
  )
}

/* ------------------------------------------------------------------------------- the photo */

/* THE ADDRESS NAMES THE PHOTOGRAPH (D172), AND THE `nonce`/`capture_id` STAMP STAYS FOR THE ONE
 * THING THE ADDRESS CANNOT SAY: a re-shoot writes new bytes at the SAME name, so the URL, the
 * freshness lifetime and the ETag all stay put and a browser that revalidates is answered 304
 * into the stale photograph. `capture_id` is the one field that moves when the bytes do
 * (`do_reshoot` writes a fresh one in the same transaction as the file), so it is the cache
 * key; `nonce` is the same id one step earlier, covering the window between the re-shoot's own
 * response and the inventory re-read that carries the new `capture_id` onto the row. Moved
 * from `BoxBrowse.tsx` whole — see that file's history for the measurement this rests on. */
export function photoSrc(row: Row, nonce: string | null): string {
  const base = photoUrl(row.card.box, row.card.index, row.card.cid)
  const stamp = nonce ?? row.card.capture_id
  return stamp === null ? base : `${base}?card=${encodeURIComponent(stamp)}`
}

export type PhotoPanelProps = {
  row: Row
  label: string | null
  absent: boolean
  onAbsent: () => void
  nonce: string | null
  onZoom: () => void
  reshoot: ReactNode
}

/** Three ways a photo can be missing — never stored, reclaimed on purpose after the sale
 *  (D89), or claimed and not on disk — each a card-shaped placeholder. `reshoot` is optional
 *  by the caller's own choice: `#/orders` passes `null`, since re-shooting a card mid-walk is
 *  an Inventory-only correction. */
export function PhotoPanel({ row, label, absent, onAbsent, nonce, onZoom, reshoot }: PhotoPanelProps) {
  const where = label ?? `store key ${row.key}`

  if (row.card.photo === null) {
    return (
      <div className="bn-photo browse-absent">
        <Icon name="image" size={28} />
        <p>No photo was stored for this card.</p>
        <span className="browse-machine">photo: null</span>
        {reshoot}
      </div>
    )
  }

  if (row.card.photo_reclaimed_at !== null) {
    return (
      <div className="bn-photo browse-absent">
        <Icon name="check" size={28} />
        <p>Photograph reclaimed after the sale — deleted on purpose, record kept.</p>
        <span className="browse-machine">
          reclaimed {row.card.photo_reclaimed_at}
          {row.card.photo_sha256 ? ` · sha256 ${row.card.photo_sha256.slice(0, 16)}…` : ''}
        </span>
      </div>
    )
  }

  const src = photoSrc(row, nonce)

  if (absent) {
    return (
      <div className="bn-photo browse-absent">
        <Icon name="alert" size={28} />
        <p>The record has a photo but the file is not on disk. The card is still at {where}.</p>
        <span className="browse-machine">{src}</span>
        {reshoot}
      </div>
    )
  }

  return (
    <button type="button" className="bn-photo browse-photo-frame" onClick={onZoom} aria-label="Open the photograph full size">
      <img
        key={`${row.key}:${row.card.capture_id ?? 'no-id'}:${src}`}
        className="browse-photo"
        src={src}
        alt={`The card photographed at ${where}`}
        onError={onAbsent}
      />
      <span className="browse-photo-zoom" aria-hidden="true">
        <Icon name="eye" size={14} /> tap to zoom
      </span>
    </button>
  )
}

/* ----------------------------------------------------------------------------- the details */

/** `identity · claims · provenance` — `BoxBrowse.tsx`'s own disclosure, moved whole. Owns its
 *  open/closed state (default open unless `phone`, same as before) rather than reading it off
 *  the caller, so both screens get the identical control with no prop to keep in step. */
export function CardDetailsSection({
  card,
  market,
  listings,
  phone,
}: {
  readonly card: InventoryCard
  readonly market: MarketRead | undefined
  readonly listings: Readonly<Record<string, Listing>>
  readonly phone: boolean
}) {
  const [openState, setOpenState] = useState<boolean | null>(null)
  const open = openState ?? !phone
  return (
    <details className="bn-panel browse-details" open={open} onToggle={(event) => setOpenState(event.currentTarget.open)}>
      <summary className="browse-details-summary">
        <Icon name="chevronRight" size={14} className="browse-details-chev" />
        <span className="bn-section-title">Details</span>
        <span className="browse-details-hint">identity · claims · provenance</span>
      </summary>
      <div className="browse-about">
        {factGroupsOf(card, market, listings).map((group) => (
          <div className="browse-factgroup" key={group.title}>
            <span className="bn-label">{group.title}</span>
            <dl className="browse-facts">
              {group.facts.map((fact) => (
                <div className="browse-fact" key={fact.label}>
                  <dt>{fact.label}</dt>
                  <dd className={fact.kind === 'mono' ? 'is-util' : fact.kind === 'money' ? 'is-money' : undefined}>
                    {fact.node ?? fact.value}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </details>
  )
}
