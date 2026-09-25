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

import { useRef, useState, type ReactNode } from 'react'

import { ReadingAge } from './CardLocations'
import { collectorNumber } from './cardNumber'
import { readingAgo, stateLabel, stateTone } from './cardState'
import { Button, Icon, Pill } from './kit'
import { toast } from './kit/toast'
import { sayPlace } from './position'
// D46's own picker, reused rather than forked — this file's own header rule: "added to
// inventory and both screens get it, not a fork" (D252).
import { CatalogPanel } from './ReviewQueue'
import {
  confirmIdentity,
  correctAnswer,
  describeFailure,
  photoUrl,
  reviewCatalog,
  undoConfirmIdentity,
  undoCorrectAnswer,
} from './server'
import type { CandidateRow, CatalogLookup, InventoryCard, Listing, PricingPayload } from './types'
import './CardHero.css'

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
  return members.length === 0 ? 'none recorded' : members.join(', ')
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

/** identity-follows-sku.md §5.4/§8.1, the owner's ruling on Details' two identity lines
 *  (2026-09-24, verbatim: "show listing name and/or hide when identical i dont think it's
 *  an or situation") — the second of the two, "Read as": what the camera actually returned,
 *  drawn only when `reading_differs` says it disputes what Card/Number already show. Gated
 *  on `reading_differs`, NOT `read_disputes` — that field answers a different question, once,
 *  at bind time; `reading_differs` is computed fresh off the card's current shown fields
 *  (`server/capture_server.py:_listing_decoration`), which is what keeps this line from
 *  repeating "Card:"/"Number:" word for word on a held card (the review-round defect).
 *  Composed from the raw `read_number`/`read_printed_total` pair rather than a folded
 *  `number_display` — this line is showing what the camera actually returned (D67 keeps the
 *  glued-set-code fold for the identity's own number, never for the read), the same choice
 *  `ReviewQueue.tsx`'s own read-facing rows make (`cardNumber.ts`'s header). */
function readAsFact(card: InventoryCard): Detail | null {
  if (card.reading_differs !== true) return null
  const name = typeof card.read_name === 'string' && card.read_name.trim() !== '' ? card.read_name.trim() : null
  const number = collectorNumber({ number: card.read_number, printed_total: card.read_printed_total })
  const value = [name, number].filter((part): part is string => part !== null).join(' ')
  return value === '' ? null : { label: 'Read as', value }
}

/** The first of Details' two identity lines, "Listed as" (§5.4/§8.1, the same 2026-09-24
 *  ruling): the SKU's own catalog name and number, drawn only when `listing_differs` says
 *  they disagree with what Card/Number already show — so the photo's reading and the
 *  listing can be read side by side, right above the confirm press below. `card.listing` is
 *  absent on a card with no SKU or a SKU the `skus` table does not (yet) hold; this function
 *  draws nothing then either, matching `listing_differs`'s own false in that case. */
function listedAsFact(card: InventoryCard): Detail | null {
  if (card.listing_differs !== true || card.listing == null) return null
  const name = card.listing.name.trim() !== '' ? card.listing.name.trim() : null
  const number = collectorNumber({ number: card.listing.number, printed_total: card.listing.printed_total })
  const value = [name, number].filter((part): part is string => part !== null).join(' ')
  return value === '' ? null : { label: 'Listed as', value }
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
  const listedAs = listedAsFact(card)
  const readAs = readAsFact(card)
  return [
    {
      title: 'Identity',
      facts: [
        { label: 'Card', value: nameOf(card) ?? 'not identified yet' },
        { label: 'Number', value: numberCell(card), kind: 'mono' },
        ...(listedAs !== null ? [listedAs] : []),
        ...(readAs !== null ? [readAs] : []),
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
  /* D218: `label` is the server's `Position.label`, and this panel only ever speaks it —
     the paragraph below and the photo's own `alt` are plain text and an accessible name,
     where there is no CSS to draw the ` · ' with, so `sayPlace` reads it as a sentence
     instead. Shared by `#/inventory` (`BoxBrowse.tsx`) and `#/orders`
     (`OrdersWalkPane.tsx`), so fixing it here fixes both callers at once. */
  const where = label === null ? `store key ${row.key}` : sayPlace(label)

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
        <span className="browse-machine bn-facts">
          <span>reclaimed {row.card.photo_reclaimed_at}</span>
          {row.card.photo_sha256 ? (
            <>
              {' '}
              <span>sha256 {row.card.photo_sha256.slice(0, 16)}…</span>
            </>
          ) : null}
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
 *  the caller, so both screens get the identical control with no prop to keep in step.
 *
 *  `correctable` IS THE SCREEN'S OWN WORD, on the owner's ruling (D252):
 *  "Inventory only" — the listing-correction control shows on `#/inventory` and not on
 *  `#/orders`, and the screen says so rather than this file guessing from the route. DEFAULTS
 *  FALSE — an ALLOW-LIST of one screen, on the owner's OWN wording, so a THIRD screen that
 *  mounts this pane later inherits nothing silently. `BoxBrowse.tsx` passes `correctable` at
 *  its one call site (the smallest edit that ruling reaches into a fenced file for);
 *  `OrdersWalkPane.tsx` needs no flag at all now — omitting one IS "no control", the same
 *  answer `false` gave before. `false`/omitted renders NOTHING for the control, not an empty
 *  reserved slot — D118 protects a control's OWN state change, and a screen that never draws
 *  the control has no such change to protect against. */
export function CardDetailsSection({
  card,
  market,
  listings,
  phone,
  correctable = false,
}: {
  readonly card: InventoryCard
  readonly market: MarketRead | undefined
  readonly listings: Readonly<Record<string, Listing>>
  readonly phone: boolean
  readonly correctable?: boolean
}) {
  const [openState, setOpenState] = useState<boolean | null>(null)
  const open = openState ?? !phone
  return (
    <details className="bn-panel browse-details" open={open} onToggle={(event) => setOpenState(event.currentTarget.open)}>
      <summary className="browse-details-summary">
        <Icon name="chevronRight" size={14} className="browse-details-chev" />
        <span className="bn-section-title">Details</span>
        <span className="browse-details-hint bn-facts">
          <span>identity</span> <span>claims</span> <span>provenance</span>
        </span>
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
      {correctable ? <ListingCorrection card={card} /> : null}
    </details>
  )
}

/* -------------------------------------------------------- correcting a listed answer */

/** D252: a card answered onto the wrong catalog row, whose wrong SKU is
 *  already pushed or live, has no way back through `do_review_answer`'s own undo —
 *  `undo_too_late` refuses it by name, and the message says "correct the card by hand". This
 *  is that hand: `POST /inventory/<box>/<index>/correct` rewrites the card to a DIFFERENT
 *  row from its own catalog export, whether or not it is still in any queue, and the wrong
 *  SKU is released (D34) rather than left silently over-listed.
 *
 *  SHOWN ONLY FOR AN IDENTIFIED, ON-HAND CARD — the two conditions the route itself refuses
 *  on (`not_identified`, `card_departed`) — so the control never offers a press the server
 *  would only reject.
 *
 *  ONE OF `#/inventory`'S OWN CARD PANE, on this file's own precedent: "added to inventory
 *  and both screens get it, not a fork." `#/orders` draws the same pane and gets the same
 *  control; retire, move and reshoot are Inventory-only for the same structural reason
 *  (`BoxBrowse.tsx`'s own `CardOps` menu is not reachable from here), while this one needs
 *  nothing `#/orders` cannot already do — the box and index alone.
 *
 *  identity-follows-sku.md §8.1 ADDS A SECOND PRESS TO THIS SAME COMPONENT, "The listing is
 *  right" — the sibling case a correction cannot answer: a HELD card
 *  (`identity_source: 'read'`) whose SKU is already the right one and whose drawn name is
 *  only the camera's. `#/inventory`-only exactly as the correction is, on the owner's own
 *  ruling (D252, "Inventory only"): both controls live behind `CardDetailsSection`'s
 *  `correctable` prop, so `#/orders` never renders this component's confirm press either. It
 *  shares this component's SLOT rather than getting a second one (D118) and its own eligible
 *  check is a NARROWING of `eligible` below — a card that cannot be corrected cannot be
 *  confirmed either, and the reverse is not true.
 *
 *  A SEPARATE PANEL EVERY WRITE ON THIS SCREEN TAKES: neither the header nor the details
 *  disclosure re-reads after a correction or a confirm, because both are drawn from the
 *  `card` this component was HANDED, owned by `BoxBrowse.tsx`/`OrdersWalkPane.tsx` and not by
 *  this file. The receipt below still stands and its Undo still works — the write and the
 *  reversal are both real — the rest of the pane simply catches up the way every other write
 *  on this screen does, on the caller's own next read. */
/** The identity this control believes the card carries RIGHT NOW — `card` if this control has
 *  written nothing, or the last write's own answer once it has. `screen-freshness.mjs`'s
 *  idiom 4 ("the response carries the new state"), and the real reason it exists: `card` is
 *  owned by `BoxBrowse.tsx`/`OrdersWalkPane.tsx` and does not move until their own next read,
 *  so without this a second press — or the small note below it — would work off what the
 *  card USED to be. `identity_source` is the field a confirm changes without changing `sku`
 *  at all, which is why it is carried here too: it is the only way this component can tell,
 *  before the caller's own next read, that a card it just confirmed is no longer eligible for
 *  a second confirm.
 *
 *  `via` IS WHY THE NOTE BELOW ONLY EVER DRAWS FOR A CORRECTION (D118). A correction's own
 *  note is D252's shipped behaviour, unchanged. A confirm's own receipt is the toast alone —
 *  `runConfirm` below already puts the same sentence there — because the note's own height
 *  is exactly the "control becomes its own result" case D118 names, and unlike a correction
 *  (which also opens a whole new catalog-search panel on `Wrong card?`, already the taller of
 *  this component's states) a confirm has no other draw that would ever need more room than
 *  the button it replaces. Drawing the note for it too would grow `.card-correction` on
 *  every confirm with nothing else on the card panel ever needing that height, which is
 *  measured screen shake and not a state this control has to draw twice — the toast already
 *  carries it once. */
type Written = { sku: string; condition: string; name: string | null; identity_source: string | null; via: 'correct' | 'confirm' }

function ListingCorrection({ card }: { readonly card: InventoryCard }) {
  const [open, setOpen] = useState(false)
  const [typed, setTyped] = useState('')
  const [lookup, setLookup] = useState<CatalogLookup | null>(null)
  const [failed, setFailed] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [confirmBusy, setConfirmBusy] = useState(false)
  const [written, setWritten] = useState<Written | null>(null)
  const inflight = useRef(0)

  const sku = written?.sku ?? card.sku
  const name = written?.name ?? nameOf(card)
  const identitySource = written?.identity_source ?? card.identity_source ?? null

  // The two refusals `POST /inventory/<box>/<index>/correct` would give this card anyway —
  // checked here so the control is never offered a press the server would only reject.
  const eligible = sku !== null && card.state === 'identified'

  // WHETHER THE CONFIRM PRESS EXISTS AT ALL FOR THIS CARD, read off `card` — the prop this
  // component was HANDED — and NEVER off `written` (D118). A card that arrived held
  // (`identity_source: 'read'`) keeps this press in the `.bn-actions-stack` for this
  // component's whole lifetime, so a successful confirm cannot shrink the stack by removing
  // its own button: the slot's height is set once, by the card `BoxBrowse.tsx` handed this
  // component, and a write inside this component never changes it again.
  const confirmable = eligible && card.identity_source === 'read'

  // §8.1's own third refusal, `already_confirmed`: once THIS component's own write (or the
  // caller's next full read, which arrives as a new `card` prop and a fresh `confirmable`
  // above) has bound the SKU, the button stays in place but goes inert rather than offering
  // a press the server would only refuse.
  const confirmDone = confirmable && identitySource !== 'read'

  const { box, index } = card

  const search = (query: string) => {
    const mine = ++inflight.current
    setLookup(null)
    setFailed(null)
    void reviewCatalog(box, index, query)
      .then((found) => {
        if (inflight.current === mine) setLookup(found)
      })
      .catch((err: unknown) => {
        if (inflight.current === mine) setFailed(describeFailure(err).message)
      })
  }

  const openPanel = () => {
    setOpen(true)
    setTyped('')
    search('')
  }

  /* The toast names the place the way the screen draws it: the card row's own label, read as a
     sentence. A row with no place (a pooled card) gets no place in the toast at all. */
  const withPlace = (row: InventoryCard, rest: string): string => {
    const label = row.label ?? card.label
    return label ? `${sayPlace(label)} — ${rest}` : rest.charAt(0).toUpperCase() + rest.slice(1)
  }

  const runUndo = (atBox: number, atIndex: number) => {
    void undoCorrectAnswer(atBox, atIndex)
      .then((result) => {
        setWritten({
          sku: result.sku,
          condition: result.condition,
          name: nameOf(result.card),
          identity_source: result.card.identity_source ?? null,
          via: 'correct',
        })
        toast({
          kind: 'ok',
          icon: 'undo',
          title: 'Correction undone',
          body: withPlace(result.card, `back to ${result.sku}`),
        })
      })
      .catch((err: unknown) => {
        toast({ kind: 'refusal', title: 'The correction was not undone', body: describeFailure(err).message })
      })
  }

  const choose = (row: CandidateRow) => {
    if (busy) return
    setBusy(true)
    correctAnswer(box, index, row.sku)
      .then((result) => {
        setOpen(false)
        setWritten({
          sku: result.sku,
          condition: result.condition,
          name: nameOf(result.card),
          identity_source: result.card.identity_source ?? null,
          via: 'correct',
        })
        toast({
          kind: result.restores_to ? 'receipt' : 'status',
          icon: 'wand',
          title: 'Card corrected',
          body: `${result.card.name ?? row.name} — SKU ${result.previous_sku ?? '?'} → ${result.sku}`,
          action: result.restores_to ? { label: 'Undo', onPress: () => runUndo(box, index) } : undefined,
        })
      })
      .catch((err: unknown) => {
        toast({ kind: 'refusal', title: 'The card was not corrected', body: describeFailure(err).message })
      })
      .finally(() => setBusy(false))
  }

  // §8.1: "`{"undo": true}` returns the card to `identity_source = read`" — D28's shape,
  // `runUndo` above's own twin. `do_confirm_identity` always captures a full snapshot before
  // it writes, so a fresh confirm's own Undo is offered unconditionally below, unlike
  // `choose`'s `result.restores_to` check — this route has no such field to be null.
  const runUndoConfirm = (atBox: number, atIndex: number) => {
    void undoConfirmIdentity(atBox, atIndex)
      .then((result) => {
        setWritten({
          sku: result.sku,
          condition: result.condition,
          name: nameOf(result.card),
          identity_source: result.card.identity_source ?? null,
          via: 'confirm',
        })
        toast({
          kind: 'ok',
          icon: 'undo',
          title: 'Confirmation undone',
          body: withPlace(result.card, "back to the camera's read."),
        })
      })
      .catch((err: unknown) => {
        toast({ kind: 'refusal', title: 'The confirmation was not undone', body: describeFailure(err).message })
      })
  }

  const runConfirm = () => {
    if (confirmBusy) return
    setConfirmBusy(true)
    confirmIdentity(box, index)
      .then((result) => {
        setWritten({
          sku: result.sku,
          condition: result.condition,
          name: nameOf(result.card),
          identity_source: result.card.identity_source ?? null,
          via: 'confirm',
        })
        toast({
          kind: 'receipt',
          icon: 'check',
          title: 'Listing confirmed',
          body: `${result.card.name ?? name ?? 'Card'} stays SKU ${result.sku}.`,
          action: { label: 'Undo', onPress: () => runUndoConfirm(box, index) },
        })
      })
      .catch((err: unknown) => {
        toast({ kind: 'refusal', title: 'The listing was not confirmed', body: describeFailure(err).message })
      })
      .finally(() => setConfirmBusy(false))
  }

  // THE SLOT KEEPS ITS HEIGHT WHEN THE CONTROL BECOMES ITS OWN RESULT (D118),
  // `.card-locations-action`'s own rule (app/src/CardLocations.css), reused rather than
  // invented: `.card-correction`'s CSS reserves `Wrong card?`'s own height always, so a press
  // ELSEWHERE ON THIS CARD (Mark sold — `card.state` turns `sold`/`retired`, `eligible` turns
  // false) empties this slot without resizing it. The wrapper always renders; what changes is
  // only what stands inside it.
  return (
    <div className="card-correction">
      {!eligible ? null : (
        <>
          {written !== null && written.via === 'correct' ? (
            // WRITTEN, NOT `card` — the header and the Details panel above still show what
            // this component was handed until the caller's own next read; this line is the
            // one place on the pane that already knows what actually happened.
            //
            // CORRECTION ONLY (D118). A confirm's own receipt is the toast alone — see
            // `Written.via`'s own comment above for why drawing this note for a confirm too
            // would grow this reserved slot for no card panel ever needs.
            <p className="card-correction-note">
              Now {name ?? 'unnamed'}, SKU {sku}. The rest of this panel updates on the next reload.
            </p>
          ) : null}
          {!open ? (
            // `.bn-actions-stack` (D195, kit.css): the two presses share this component's
            // one role — same variant, same size — so a sector holding both takes the
            // stack's own equal-width column rather than each button its own intrinsic
            // width, which is what `button-stack.spec.ts` finds and checks regardless of
            // which wrapper class drew it.
            <div className="bn-actions-stack">
              {!confirmable ? null : (
                <Button
                  variant="quiet"
                  size="sm"
                  icon="check"
                  busy={confirmBusy}
                  disabled={confirmDone}
                  onClick={runConfirm}
                >
                  The listing is right
                </Button>
              )}
              <Button variant="quiet" size="sm" icon="search" onClick={openPanel}>
                Wrong card?
              </Button>
            </div>
          ) : (
            <div
              className="bn-panel card-correction-panel"
              // `CatalogPanel`'s own copy promises `Esc` goes back — true on `#/review`, where
              // the container already binds it, and not true here without this. Bound on the
              // panel rather than the document, so it never reaches past this control.
              onKeyDown={(event) => {
                if (event.key === 'Escape') setOpen(false)
              }}
            >
              <div className="bn-panel-head">
                <span className="bn-section-title">Correct the listing</span>
                <Button size="sm" variant="ghost" iconOnly icon="x" onClick={() => setOpen(false)}>
                  Close
                </Button>
              </div>
              <div className="bn-panel-body">
                <CatalogPanel
                  lookup={lookup}
                  failed={failed}
                  typed={typed}
                  onTyped={setTyped}
                  onSearch={() => search(typed)}
                  onChoose={choose}
                  overruling
                  busy={busy}
                />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
