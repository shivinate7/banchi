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
 * `BoxBrowse.tsx` imports them back with no change to its own JSX. Lane A2a's own move below
 * (`CardHeroHead`/`CardPane`) DOES change `BoxBrowse.tsx`'s JSX — the markup now calls a
 * component instead of writing the tags out — but not what it RENDERS: `app/tests/
 * inventory.spec.ts` is what proves the rendered screen is unchanged (D97's "the screens
 * answer to the owner's interview" — this repo's own suite is the interview here).
 *
 * `CardHeroHead` IS THE WHOLE HEAD NOW (lane A2a) — the one `BoxBrowse.tsx` used to draw
 * inline, moved rather than reimplemented, because the two had drifted (no `place` line, no
 * printing-chooser or queue chip, and the state pill was drawn unconditionally instead of
 * BoxBrowse's own "only when it is the exception" rule, UX-221). `place`, `preChips` and
 * `postChips` are the slots `BoxBrowse.tsx`'s own header needed — the printing-chooser chip
 * goes in `preChips`, the review-queue chip in `postChips` — both left `undefined` by any
 * caller that has none, `#/orders` included. `actions` is an open slot for whatever a caller
 * puts beside the title — `BoxOps`'s `CardOps` menu is Inventory-only editing (retire, move,
 * correct claims) and is never passed in from `#/orders`.
 *
 * `CardPane` WRAPS THE HEAD, THE QUEUED NOTICE AND THE PHOTO BAND — `BoxBrowse.tsx`'s own
 * `<section className="browse-card">`, moved whole. `CardDetailsSection` stays a SEPARATE
 * component below it, exactly as it already sits in `BoxBrowse.tsx`'s own JSX (a sibling of
 * the section, never nested in it) — so a caller that wants the head and the copies without
 * the Details fold (`#/orders`, later, "we don't need details on this screen") simply does not
 * render `CardDetailsSection`, and needs no prop to say so.
 *
 * `CardDetailsSection` IS MOVED WHOLE — `BoxBrowse.tsx`'s own `<details className="bn-panel
 * browse-details">` block, unchanged, now owning its own open/closed state instead of reading
 * it off `BoxBrowse.tsx`'s local `detailsOpen` — the same default (open unless `phone`) and
 * the same manual-wins-until-toggled behaviour, just kept inside the component that draws it.
 */

import { useEffect, useRef, useState, type ReactNode } from 'react'

import { ReadingAge } from './CardLocations'
import { collectorNumber } from './cardNumber'
import { forSale, IDENTIFIED, readingAgo, readingAgoShort, readingExact, stateLabel, stateTone, staleReading } from './cardState'
import { Button, Icon, IconButton, Meter, Money, Pill, ProductLink, Skeleton } from './kit'
import { toast } from './kit/toast'
import { money } from './money'
import { relativeDate, toDate } from './dates'
import { sayPlace } from './position'
// D77's own picker, reused rather than forked — this file's own header rule: "added to
// inventory and both screens get it, not a fork" (D252).
import { CatalogPanel } from './ReviewQueue'
import {
  confirmIdentity,
  correctAnswer,
  describeFailure,
  getPricing,
  photoUrl,
  reviewCatalog,
  undoConfirmIdentity,
  undoCorrectAnswer,
  refusalToast,
} from './server'
import type { BoxRecord, CandidateRow, CatalogLookup, InventoryCard, Listing, PricingPayload, SearchGroup } from './types'
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
  const said = money(Number(price))
  if (ago === null) return `${said} · no age`
  return `${said} · read ${ago}`
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
        <span className="bn-tnum">{money(Number(price))}</span>
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

/** Where a transplant came from, in plain words — the UX review's graveyard ruling: "Move
 *  Moved out of Graveyard", so a moved card must still be findable from ITSELF on
 *  `#/inventory` rather than only from the tombstone `#/graveyard` reads. `card.moved_from`
 *  is `"box/index"` (`store/master.py:Card.moved_from`); only the box half is said, by name
 *  (D259), never the number. The old box can be gone by the time anyone looks — that is
 *  the graveyard review's own example, box 5 deleted after 264 cards moved out of it — so a
 *  name that does not resolve falls back to "another box" rather than the digits, the same
 *  honest answer `Graveyard.tsx:movedToName` gives for the matching case in `moved_to`. */
function movedFromFact(card: InventoryCard, boxes: readonly BoxRecord[]): Detail | null {
  // `== null` catches BOTH a stored `null` and a plain-JS fixture that never set the field
  // at all — `undefined`, the shape a route mock or an older server row actually carries,
  // where `.split` would throw and take the whole panel down with it (the crash this
  // guard exists to have already prevented, found by inventory.spec.ts's own real-server
  // fixture, `card()`, which never sets this new field on purpose).
  if (card.moved_from == null) return null
  const boxN = Number(card.moved_from.split('/')[0])
  const name = Number.isFinite(boxN) ? boxes.find((b) => b.box === boxN)?.name : undefined
  return { label: 'Moved from', value: typeof name === 'string' && name.trim() !== '' ? name : 'another box' }
}

/** When this card was photographed, as a person says it. THE TWO SANCTIONED FORMATS
 *  (`dates.ts`, "a screen picks one of the two, it never builds a third") — `relativeDate`
 *  is the fit here: a fact about WHEN something happened, which is exactly what it is for,
 *  and it already hands over to `absoluteDate` once the moment is more than a week old. */
function capturedText(stamp: string | null): string {
  if (stamp === null) return 'not recorded'
  if (toDate(stamp) === null) return stamp
  return relativeDate(stamp)
}

type FactGroup = { title: string; facts: Detail[] }

/** Identity, Claims, Provenance — the three groups `#/inventory`'s Details disclosure draws,
 *  and the exact grouping this file's own header describes moving whole. */
export function factGroupsOf(
  card: InventoryCard,
  market: MarketRead | undefined,
  listings: Readonly<Record<string, Listing>>,
  boxes: readonly BoxRecord[] = [],
): FactGroup[] {
  const listedAs = listedAsFact(card)
  const readAs = readAsFact(card)
  const movedFrom = movedFromFact(card, boxes)
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
        /* THE COPIES HEADER'S SKU AND CONDITION LINE IS GONE: these two are its facts, said here. */
        ...(card.sku === null || card.sku.trim() === '' ? [] : [{ label: 'SKU', value: card.sku.trim(), kind: 'mono' as const }]),
        ...(card.sku === null || listings[card.sku.trim()]?.condition == null
          ? []
          : [{ label: 'Condition', value: listings[card.sku.trim()]!.condition! }]),
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
        ...(movedFrom !== null ? [movedFrom] : []),
        marketFact(card, market),
        listingFact(card, listings),
      ],
    },
  ]
}

/* -------------------------------------------------------------------------- the hero head */

/** THE BAND'S FIGURES, HANDED IN BY WHICHEVER SCREEN HOLDS THE CARD'S SEARCH GROUP (the card-detail
 *  spec, "The band"). They are facts about the card and its copies, so they sit with the card and
 *  not over the copies list. `Inventory.tsx` and `Orders.tsx` both build one and pass it through
 *  `CardPane`, so the band is drawn in one place.
 *  - `listedAt`: when this store last wrote the SKU's listing figures. Null draws a quiet dash.
 *  - `hidden`: the departed copies the list folds away (`CardLocations.tsx:hiddenCopies`).
 *  - `cap`: `group.listable` where the screen has it. Null draws no ceiling meter, because a screen
 *    that cannot say the ceiling must not draw one (`#/orders`' take carries no cap). */
export type HeroFigures = {
  readonly group: SearchGroup
  readonly listedAt: string | null
  readonly hidden: number
  readonly cap: number | null
}

/** THE MARKET PRICE OF ONE CARD, read once per run off the pricing file (`marketTable`): the band's
 *  Market figure. One home, called by `CardPane`, so `#/inventory` and the `#/orders` walk draw the
 *  same figure from the same read. Null while it loads, on a failed read, and where the run holds no
 *  row for this card: the band draws a quiet dash and never a made-up figure. */
export function useMarketPrice(card: InventoryCard): number | null {
  const run = card.run ?? null
  const [read, setRead] = useState<{ run: string; table: MarketRead } | null>(null)
  useEffect(() => {
    if (run === null) return
    let live = true
    getPricing(run)
      .then((payload) => {
        if (live) setRead({ run, table: marketTable(payload) })
      })
      .catch(() => {
        if (live) setRead({ run, table: { kind: 'absent', why: 'could not be read' } })
      })
    return () => {
      live = false
    }
  }, [run])
  if (run === null || read === null || read.run !== run || read.table.kind !== 'table') return null
  const raw = read.table.rows[`${card.box}/${card.index}`]
  const price = raw === null || raw === undefined ? NaN : Number(raw)
  return Number.isNaN(price) ? null : price
}

/** Stored and Live, the two lead figures. A group with no SKU has no listing, so it draws no Live
 *  figure and no ceiling: the store has nothing to report and the band must not invent it (D119). */
function HeroLead({ figures, market }: { readonly figures: HeroFigures; readonly market: number | null }) {
  const { group, listedAt, cap } = figures
  const listing = group.sku !== null
  const live = forSale(group.listed.live, group.sold_here)
  const read = Boolean(listedAt) || group.listed.live > 0
  /* THE DOT SITS IN THE LABEL LINE, NOT ON THE FIGURE. Recent: the live dot at rest. Three days or
     more: amber (provisional, `cardState.ts:STALE_READING_DAYS`). Unread: no dot, a quiet dash. */
  const dot = !read
    ? null
    : staleReading(listedAt)
      ? 'bn-dot bn-dot-warn'
      : 'bn-dot bn-dot-live bn-dot-still'
  const ago = readingAgoShort(listedAt)
  const over = cap === null ? 0 : live - cap
  return (
    <div className="browse-hero-lead">
      <div className="browse-hero-fig">
        <span className="browse-hero-fig-label">
          <span className="bn-label">Stored</span>
        </span>
        <span className="browse-hero-fig-value">{group.on_hand}</span>
      </div>
      {listing ? (
        <div
          className="browse-hero-fig browse-hero-fig-live"
          data-read={read ? 'true' : 'false'}
          title={
            group.sold_here > 0
              ? `${group.listed.live} when read, ${group.sold_here} sold here since.`
              : read
                ? `This store last wrote these listing figures ${readingExact(listedAt) ?? 'at an unknown time'}.`
                : 'Nothing has written a listing figure for this yet.'
          }
        >
          <span className="browse-hero-fig-label">
            {dot === null ? null : <span className={dot} aria-hidden="true" />}
            <span className="bn-label">Live</span>
            <span className="browse-hero-age">{read ? ago : 'not read'}</span>
          </span>
          <span className="browse-hero-fig-value">{read ? live : '—'}</span>
          {cap === null || cap <= 0 ? null : (
            <Meter
              cells={cap}
              filled={live}
              tone={over > 0 ? 'warn' : undefined}
              end={over > 0 ? `Cap ${cap}, ${over} over` : <>Cap {cap}</>}
              label={over > 0 ? `${live} live, cap ${cap}, ${over} over` : `${live} live, cap ${cap}`}
            />
          )}
        </div>
      ) : null}
      {/* MARKET, beside Live: the price this card last read at, opening the product by SKU. A dash
          where nothing has read one. */}
      {listing && group.sku !== null ? (
        <div className="browse-hero-fig">
          <span className="browse-hero-fig-label">
            <span className="bn-label">Market</span>
          </span>
          <span className="browse-hero-fig-value">
            <ProductLink sku={group.sku} name={group.names[0]}>
              <Money value={market} />
            </ProductLink>
          </span>
        </div>
      ) : null}
    </div>
  )
}

/** STAND-IN TEXT: the text sets the box (the browser's own font, so the size is right on any
 *  platform) and is hidden, and the kit's `Skeleton` is laid over it for the bar and its shimmer. */
function Ghost({ children, className }: { readonly children: ReactNode; readonly className?: string }) {
  return (
    <span className={['bn-ghost', className].filter(Boolean).join(' ')}>
      {children}
      <Skeleton className="bn-ghost-bar" />
    </span>
  )
}

/** THE LEAD COLUMN WHILE THE COPIES SEARCH IS STILL ASKING (D118, a press changes what is on
 *  screen). The real column adds itself when the answer lands, and Actions, which rides the
 *  identity column's end, used to jump ~380px left under a press. This holds the column at its
 *  final size by drawing THE SAME ELEMENTS as `HeroLead`, with stand-in text the browser sets in
 *  the same face and hides (`.bn-ghost`): the figures' heights and widths come from the browser's
 *  own font, so the two states agree on any platform rather than by a tuned number. Stored, Live
 *  and Market for a card with a SKU, Stored alone for one without (D119, no SKU, no listing
 *  figures). */
function HeroLeadPending({ listing }: { readonly listing: boolean }) {
  const label = (text: string) => (
    <span className="browse-hero-fig-label">
      <span className="bn-label">{text}</span>
    </span>
  )
  return (
    <div className="browse-hero-lead" aria-hidden="true" data-pending="true">
      <div className="browse-hero-fig">
        {label('Stored')}
        <span className="browse-hero-fig-value">
          <Ghost>00</Ghost>
        </span>
      </div>
      {listing ? (
        <>
          <div className="browse-hero-fig browse-hero-fig-live">
            {label('Live')}
            <span className="browse-hero-fig-value">
              <Ghost>00</Ghost>
            </span>
            <span className="bn-meter">
              <span className="bn-meter-cells">
                <span />
              </span>
              <Ghost className="bn-meter-end">Cap 0</Ghost>
            </span>
          </div>
          <div className="browse-hero-fig">
            {label('Market')}
            <span className="browse-hero-fig-value">
              <span className="bn-datalink">
                <Ghost>$0.00</Ghost>
              </span>
            </span>
          </div>
        </>
      ) : null}
    </div>
  )
}

/** The header both screens share, drawn as the band (card-detail spec): the identity on the left
 *  (name, the meta line with the finish and rarity pills on the same line, the side facts) and the
 *  two lead figures on the right. One column under 520px of pane width. `actions` is where a
 *  caller's own edit menu goes (Inventory's `CardOps`); `#/orders` leaves it empty. `figures` is
 *  omitted by a caller with no search group, which then draws the identity alone. */
export function CardHeroHead({
  card,
  game,
  preChips,
  postChips,
  actions,
  figures,
  figuresPending = false,
  market = null,
}: {
  readonly card: InventoryCard
  readonly game: string | null
  /** Before the finish/rarity pills — `BoxBrowse.tsx`'s own printing-chooser chip. */
  readonly preChips?: ReactNode
  /** After the state pill — `BoxBrowse.tsx`'s own review-queue chip. */
  readonly postChips?: ReactNode
  readonly actions?: ReactNode
  readonly figures?: HeroFigures | null
  /** The copies search has not answered: hold the figures column at its final width. */
  readonly figuresPending?: boolean
  /** The Market figure's price (`useMarketPrice`). */
  readonly market?: number | null
}) {
  const name = nameOf(card)
  const number = numberCell(card)
  return (
    <div className="browse-hero-head">
      <div className="browse-hero-text">
        <div className="browse-hero-titlerow">
          <h2 className={name === null ? 'browse-hero-name is-unnamed' : 'browse-hero-name'}>{name ?? 'Not identified yet'}</h2>
          {actions}
        </div>
        {/* THE META LINE: number, set, game, then rarity and finish as outline pills on the SAME
            line. No row holds rarity alone. The seam between the three facts is CSS (D218). */}
        <p className="browse-hero-sub">
          <span className="browse-hero-parts">
            {[number === 'none' ? null : number, card.set_hint, game]
              .filter((part): part is string => typeof part === 'string' && part !== '')
              .map((part, i) => (
                <span key={`${part}-${i}`} className={i === 0 && number !== 'none' ? 'browse-hero-number' : undefined}>
                  {part}
                </span>
              ))}
          </span>
          {preChips}
          {claimList(card.metadata_finish).map((finish) => (
            <Pill key={`f-${finish}`} icon="sparkles" outline>
              {titleCase(finish)}
            </Pill>
          ))}
          {claimList(card.rarity_claim).map((rarity) => (
            <Pill key={`r-${rarity}`} outline>
              {titleCase(rarity)}
            </Pill>
          ))}
          {/* THE CARD'S STATE ONLY WHEN IT IS THE EXCEPTION (UX-221) — `BoxBrowse.tsx`'s own
              rule, moved with the rest of the head. The dead copy of this component always
              drew the pill; that was the divergence this move fixes. */}
          {card.state === IDENTIFIED ? null : <Pill tone={stateTone(card.state)}>{stateLabel(card.state)}</Pill>}
          {postChips}
        </p>
        {/* THE SIDE FACTS: history, quieter than the lead figures and equal to each other. Hidden
            is drawn at 0 too, so a sale that folds a copy away adds no line (D118). */}
        {figures == null ? (
          figuresPending ? (
            <div className="browse-hero-side" aria-hidden="true" data-pending="true">
              <Ghost>
                Captured<b>0</b>
              </Ghost>
              <Ghost>
                Hidden<b>0</b>
              </Ghost>
              {card.sku === null ? null : (
                <Ghost>
                  Sent<b>0</b>
                </Ghost>
              )}
            </div>
          ) : null
        ) : (
          <p className="browse-hero-side">
            <span>
              Captured<b>{figures.group.copies.length}</b>
            </span>
            <span>
              Hidden<b>{figures.hidden}</b>
            </span>
            {figures.group.sku === null ? null : (
              <span>
                Sent<b>{figures.group.listed.pushed}</b>
              </span>
            )}
          </p>
        )}
      </div>
      {figures != null ? (
        <HeroLead figures={figures} market={market} />
      ) : figuresPending ? (
        <HeroLeadPending listing={card.sku !== null} />
      ) : null}
    </div>
  )
}

/* -------------------------------------------------------------------------- the card pane */

/** The head, the queued notice and the photo band — `BoxBrowse.tsx`'s own `<section
 *  className="browse-card">`, moved whole. `CardDetailsSection` is deliberately NOT part of
 *  this component (see this file's own header) — a caller renders it separately, or not. */
export type CardPaneProps = {
  readonly row: Row
  readonly game: string | null
  /** `dimPanel` in `BoxBrowse.tsx`: a stale row held on screen while the next one loads. */
  readonly dimmed?: boolean
  readonly preChips?: ReactNode
  readonly postChips?: ReactNode
  /** Inventory's own "waiting in the review queue" notice. Null draws nothing. */
  readonly queued?: ReactNode
  /** `CardOps`, Inventory-only. Empty on `#/orders`. */
  readonly actions?: ReactNode
  /** The band's figures. Omitted, the band draws the identity alone. */
  readonly figures?: HeroFigures | null
  readonly figuresPending?: boolean
  readonly photo: Omit<PhotoPanelProps, 'row'>
  /** The copies list beside the photo — `Inventory.tsx`'s `CopiesPanel`, handed down because
   *  the caller already knows which card is selected. */
  readonly detail?: ReactNode
}

export function CardPane({ row, game, dimmed = false, preChips, postChips, queued, actions, figures, figuresPending, photo, detail }: CardPaneProps) {
  const market = useMarketPrice(row.card)
  return (
    <section
      className="bn-panel browse-card"
      aria-busy={dimmed ? 'true' : undefined}
      data-dimmed={dimmed ? 'true' : undefined}
      inert={dimmed}
    >
      <CardHeroHead card={row.card} game={game} preChips={preChips} postChips={postChips} actions={actions} figures={figures} figuresPending={figuresPending} market={market} />
      {queued}
      {/* NO `detail`, NO COPIES COLUMN: `#/orders`' walk draws where each copy is in its own column, so
          its card pane is the head, the band and the photograph alone (same components, switched off
          by omission, never a fork). */}
      <div className="browse-band" data-photo-only={detail === undefined ? 'true' : undefined}>
        <div className="browse-shot">
          <PhotoPanel row={row} {...photo} />
        </div>
        {detail === undefined ? null : <div className="browse-under">{detail}</div>}
      </div>
    </section>
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
export function photoSrc(row: Row, nonce: string | null): string | null {
  return photoUrl(row.card.box, row.card.index, row.card, nonce)
}

/** A `moved:` name is the tombstone a move left (D83). */
export function isMovedCid(cid: string | null | undefined): boolean {
  return typeof cid === 'string' && cid.startsWith('moved:')
}

/** THE ONE SENTENCE FOR A CARD WHOSE NAME IS NO PHOTOGRAPH'S (`photoUrl` gives it no address).
 *  A moved card lives on elsewhere with its photograph, so it says where it went, by box name
 *  (D259) and never the digits, and never "never photographed". Every view that draws a photo
 *  calls this, so no view words the case itself. `movedTo` is the tombstone's `"box/index"`. */
export function noPhotoSentence(
  cid: string | null | undefined,
  movedTo: string | null | undefined,
  boxes: readonly BoxRecord[] = [],
): string {
  if (!isMovedCid(cid)) return 'This card was never photographed.'
  const boxN = Number(movedTo?.split('/')[0])
  const name = Number.isFinite(boxN) ? boxes.find((b) => b.box === boxN)?.name : undefined
  return `This card moved to ${typeof name === 'string' && name.trim() !== '' ? name : 'another box'}.`
}

/** What every screen says when the file is gone. */
export const ABSENT_SENTENCE = "This card's photo is missing."

/** THE ONE PANEL FOR A PHOTOGRAPH THAT IS NOT THERE — a plain sentence and, where the card can
 *  be re-shot, one action. `#/inventory` and `#/orders` draw it through `PhotoPanel`, `#/review`
 *  and `#/pricing` call it directly, so no screen words the absence itself and none prints an
 *  address. `reshoot` is the caller's own control (Inventory re-shoots in place); without one, a
 *  card with a place gets a link to it on Inventory, which is where a re-shoot happens. `at` is
 *  that place, or null for a card with none. The host draws the frame, this draws what is in it. */
export function AbsentPhotoNote({
  sentence,
  icon = 'image',
  reshoot,
  at = null,
}: {
  sentence: string
  icon?: 'image' | 'alert' | 'check' | 'arrowRight'
  reshoot?: ReactNode
  at?: { box: number; cid?: string | null } | null
}) {
  const cid = at?.cid
  const card = typeof cid === 'string' && cid !== '' && !isMovedCid(cid) ? `&card=${encodeURIComponent(cid)}` : ''
  const href = at === null || at.box < 1 ? null : `#/inventory?box=${at.box}${card}`
  return (
    <div className="absent-photo">
      <Icon name={icon} size={28} />
      <p>{sentence}</p>
      {reshoot ??
        (href === null ? null : (
          <a className="bn-btn bn-btn-sm" href={href}>
            <Icon name="camera" size={14} />
            Re-shoot
          </a>
        ))}
    </div>
  )
}

export type PhotoPanelProps = {
  row: Row
  label: string | null
  absent: boolean
  onAbsent: () => void
  nonce: string | null
  onZoom: () => void
  reshoot: ReactNode
  /** The box registry, so a moved card can say which box it went to by name. */
  boxes?: readonly BoxRecord[]
}

/** Three ways a photo can be missing — never stored, reclaimed on purpose after the sale
 *  (D89), or claimed and not on disk — each a card-shaped placeholder. `reshoot` is optional
 *  by the caller's own choice: `#/orders` passes `null`, since re-shooting a card mid-walk is
 *  an Inventory-only correction. */
export function PhotoPanel({ row, label, absent, onAbsent, nonce, onZoom, reshoot, boxes = [] }: PhotoPanelProps) {
  /* D218: `label` is the server's `Position.label`, and this panel only ever speaks it —
     the paragraph below and the photo's own `alt` are plain text and an accessible name,
     where there is no CSS to draw the ` · ' with, so `sayPlace` reads it as a sentence
     instead. Shared by `#/inventory` (`BoxBrowse.tsx`) and `#/orders`
     (`OrdersWalkPane.tsx`), so fixing it here fixes both callers at once. */
  const where = label === null ? `store key ${row.key}` : sayPlace(label)

  if (row.card.photo === null) {
    return (
      <div className="bn-photo browse-absent">
        <AbsentPhotoNote sentence="No photo was stored for this card." reshoot={reshoot} at={{ box: row.card.box, cid: row.card.cid }} />
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

  /* The card's own name says it never had a photograph, so there is no file to ask for and
     nothing to call missing. */
  if (src === null) {
    return (
      <div className="bn-photo browse-absent">
        <AbsentPhotoNote
          sentence={noPhotoSentence(row.card.cid, row.card.moved_to, boxes)}
          icon={isMovedCid(row.card.cid) ? 'arrowRight' : 'image'}
          reshoot={reshoot}
          at={isMovedCid(row.card.cid) ? null : { box: row.card.box, cid: row.card.cid }}
        />
      </div>
    )
  }

  if (absent) {
    return (
      <div className="bn-photo browse-absent">
        <AbsentPhotoNote sentence={ABSENT_SENTENCE} icon="alert" reshoot={reshoot} at={{ box: row.card.box, cid: row.card.cid }} />
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
  boxes = [],
  correctable = false,
}: {
  readonly card: InventoryCard
  readonly market: MarketRead | undefined
  readonly listings: Readonly<Record<string, Listing>>
  readonly phone: boolean
  readonly boxes?: readonly BoxRecord[]
  readonly correctable?: boolean
}) {
  const [openState, setOpenState] = useState<boolean | null>(null)
  const open = openState ?? !phone
  return (
    <details className="bn-panel browse-details" open={open} onToggle={(event) => setOpenState(event.currentTarget.open)}>
      <summary className="browse-details-summary">
        <Icon name="chevronRight" size={14} className="browse-details-chev" />
        <span className="bn-section-title">Details</span>
      </summary>
      <div className="browse-about">
        {factGroupsOf(card, market, listings, boxes).map((group) => (
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
        toast({ ...refusalToast(err, 'The correction was not undone') })
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
        toast({ ...refusalToast(err, 'The card was not corrected') })
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
        toast({ ...refusalToast(err, 'The confirmation was not undone') })
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
        toast({ ...refusalToast(err, 'The listing was not confirmed') })
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
                Correct
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
                <IconButton size="sm" icon="x" label="Close" onClick={() => setOpen(false)} />
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
