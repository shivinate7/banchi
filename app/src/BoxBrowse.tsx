import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent, ReactNode } from 'react'

import { isEditableTarget } from './keys'
import type {
  BoxRecord,
  InventoryCard,
  Listing,
  PricingPayload,
  QueueEntryWire,
  QueueSnapshot,
  RemoveResult,
} from './types'
import type { Failure } from './server'
import {
  describeFailure,
  isDeparted,
  positionLabel,
  getBoxes,
  getQueues,
  getInventory,
  getPricing,
  photoUrl,
  removeCardInPlace,
  reshootPhoto,
  updateCard,
  newCaptureId,
} from './server'
import { BoxIdentity, BoxOps, ClaimEditor, type ClaimPatch } from './BoxOps'
import { reasonLabel } from './reasons'
import { collectorNumber } from './cardNumber'
import { ReadingAge, readingAgo, stateLabel, stateTone } from './CardLocations'
import { SearchField } from './SearchField'
import { useSearch } from './useSearch'
import { Button, EmptyState, Icon, Kbd, Notice, PageHeader, Pill } from './kit'
import { toast } from './kit/toast'
import { Overlay } from './InventoryOverlay'
import './BoxBrowse.css'

/* THE BROWSE — box, then section, then card. The spine of `#/inventory`.
 *
 * The rail on the left is the instrument: search, the box list, the box's own header and the
 * walk of its cards. The pane on the right is what the walk points at: the card's name and
 * claims, its photograph, and — handed down by the screen above as `detail` — its location and
 * every copy of it. This component owns the reads, the selection, the folds, the ticks and the
 * keys; `Inventory.tsx` owns the writes.
 */

/* The inventory arrives as a map keyed `"3/1"`. The key is kept for identity and shown only
 * where a row carries no label — never parsed into a position. */
export type Row = { key: string; card: InventoryCard }

/* Box-walk order — box, then index — the order the cards physically sit in. */
function rowsOf(cards: Record<string, InventoryCard>): Row[] {
  return Object.entries(cards)
    .map(([key, card]) => ({ key, card }))
    .sort((a, b) => a.card.box - b.card.box || a.card.index - b.card.index)
}

const NO_ROWS: Row[] = []

/** No listing records read yet. Not the same as "this store has listed nothing". */
const NO_LISTINGS: Readonly<Record<string, Listing>> = {}

/* Where a walk lands: the first card still on hand, so a box never opens on a departed record
 * while it holds a card to look at; the first row only when nothing is. */
function landingOf(rows: readonly Row[]): Row | undefined {
  return rows.find((row) => !hasDeparted(row.card)) ?? rows[0]
}

// ------------------------------------------------------------------ the walk, in sections

/* Which shelf a row is on: a box number, `pooled` for a card whose game says `located: false`
 * (a count, not a location), `unplaced` for the record whose box will not coerce. */
type Shelf = number | 'pooled' | 'unplaced'

function shelfOf(row: Row): Shelf {
  if (isPooled(row.card)) return 'pooled'
  const box = row.card.box
  if (typeof box !== 'number' || Number.isNaN(box)) return 'unplaced'
  return box
}

function shelfLabel(shelf: Shelf): string {
  if (shelf === 'pooled') return 'Pooled'
  if (shelf === 'unplaced') return 'No box'
  return `Box ${shelf}`
}

/* Every shelf the current walk touches, boxes first, plus every box the registry knows when
 * nothing is being searched for — an empty box is the only state from which it can be renamed,
 * sealed or deleted. */
function shelvesOf(rows: Row[], registry: readonly number[] = []): Shelf[] {
  const boxes: number[] = []
  let pooled = false
  let unplaced = false
  for (const row of rows) {
    const shelf = shelfOf(row)
    if (shelf === 'pooled') pooled = true
    else if (shelf === 'unplaced') unplaced = true
    else if (!boxes.includes(shelf)) boxes.push(shelf)
  }
  for (const box of registry) if (!boxes.includes(box)) boxes.push(box)
  boxes.sort((a, b) => a - b)
  const out: Shelf[] = [...boxes]
  if (pooled) out.push('pooled')
  if (unplaced) out.push('unplaced')
  return out
}

/* Which stretch of one shelf's walk a row belongs to, worded as its header will say it.
 * Composed from the server's own decorations — no position arithmetic here. */
function sectionTitleOf(row: Row): string {
  if (isPooled(row.card)) {
    return `Pooled · ${row.card.place?.game_display ?? row.card.game ?? 'cards'}`
  }
  if (row.card.section === undefined) return 'No position label'

  const start = row.card.place?.section_start
  const end = row.card.place?.section_end
  if (typeof start !== 'number') return `Section ${row.card.section}`
  return typeof end === 'number'
    ? `Section ${row.card.section} · #${start}–#${end}`
    : `Section ${row.card.section} · #${start} onward`
}

type Section = { key: string; title: string; first: Row; rows: Row[] }

/* Run-length over the walk, so whatever order the rows arrive in survives exactly. Keyed by
 * the first row's store key rather than by the title, so a fold survives the re-read after a
 * sale — which changes the title's card range but not which section this is. */
function sectionsOf(rows: Row[]): Section[] {
  const out: Section[] = []
  for (const row of rows) {
    const open = out[out.length - 1]
    const title = sectionTitleOf(row)
    if (open !== undefined && open.title === title) open.rows.push(row)
    else out.push({ key: `section @ ${row.key}`, title, first: row, rows: [row] })
  }
  return out
}

/* What a row's left cell says: the slot alone under a section header, read off the server's
 * `card` decoration; the fallbacks for a departed, pooled or unlabelled record. */
function rowSlot(row: Row): string {
  if (row.card.card !== undefined) return `#${row.card.card}`
  /* The key alone. The row's muted register and its badge say departed, so a state is never
     drawn as a mono string beside a number. */
  if (hasDeparted(row.card)) return departedKey(row.card)
  const label = positionLabel(row.card)
  if (label !== null) return label
  return isPooled(row.card) ? pooledText(row.card, row.key) : `no label · ${row.key}`
}

/** `join.departed_label`'s store key, in the server's spelling (`B3 #96`, D68).
 *
 *  THE ONE PLACE A `#` IS A KEY AND NOT A COUNT, and it is deliberate. D92 gave the bare sigil
 *  to D58's count, and every other `#` in this product obeys that. This function exists to
 *  reproduce a string the SERVER composed — `join.departed_label`, for a card that has left its
 *  box — and a departed record is in no slot at all, so there is no count to draw instead. */
function departedKey(card: InventoryCard): string {
  // sigil-ok: the server's own spelling of a departed record's key, and a departed card has no slot
  return `B${card.box} #${card.index}`
}

function hasDeparted(card: InventoryCard): boolean {
  return isDeparted(card.place)
}

/** The card's name, or null — AND AN EMPTY STRING IS NOT A NAME. The pipeline writes `""` for
 *  a card whose name it could not read (8 of them in the owner's store today), and a bare `??`
 *  lets that through as a blank heading and a blank row in the walk. */
function nameOf(card: InventoryCard): string | null {
  const name = card.name
  return typeof name === 'string' && name.trim() !== '' ? name.trim() : null
}

// -------------------------------------------------------------- stepping through the list

/* Left and Right move the selection one card. A held key repeats and the ends stop. */
const STEPS = [
  { key: 'ArrowLeft', label: '←', delta: -1 },
  { key: 'ArrowRight', label: '→', delta: 1 },
] as const

/* The deep keys, list-scoped: PageUp/PageDown move by section boundary, Home/End to the ends
 * of the current filter, X ticks the current card. */
const SECTION_KEYS = [
  { key: 'PageUp', label: 'PgUp', delta: -1 },
  { key: 'PageDown', label: 'PgDn', delta: 1 },
] as const

const EDGE_KEYS = [
  { key: 'Home', label: 'Home', last: false },
  { key: 'End', label: 'End', last: true },
] as const

const TICK_KEY = { key: 'x', label: 'X' } as const

/* Is the person typing? A checkbox takes no text, so a focused one must not kill the arrows. */
function isTyping(target: EventTarget | null): boolean {
  if (target instanceof HTMLInputElement && target.type === 'checkbox') return false
  return isEditableTarget(target)
}

/** What the screen above hands down, and what it gets back. */
type BoxBrowseProps = {
  /** The page title. */
  head?: ReactNode

  /** Rendered beside the photograph, for the selected card: its location, its copies and its
   *  writes. Given as a node because the caller already knows which card is selected. */
  detail?: ReactNode

  /** Rendered under the box header, for the BOX being walked rather than for a card in it. */
  boxPanel?: ReactNode

  /** The one primary action for the selected copy, drawn in the phone's sticky action bar. */
  actionBar?: ReactNode

  /** Which card the walk is pointing at, reported on every change and `null` when the filter
   *  leaves nothing to point at. */
  onSelect?: (row: Row | null) => void

  /** The box registry, as this component's own `GET /boxes` answered it. */
  onBoxes?: (records: readonly BoxRecord[]) => void

  /** Every SKU's listing record, as this component's own `GET /inventory` answered it. Handed
   *  up so the screen above can put a reading age beside the live count it draws — the same
   *  map this component reads for the card facts and hands to the box sheet. */
  onListings?: (listings: Readonly<Record<string, Listing>>) => void

  /** Bumped by the caller after it writes a card, to force the same re-read the Reload does. */
  reloadToken?: number

  /** Walk to one card, by store key. `at` is the request; a request already answered is
   *  ignored. */
  goTo?: { key: string; at: number } | null

  /** What a run would be scoped to: the box being walked, and the ticked cards inside it. */
  onScope?: (scope: { box: number | null; indices: readonly number[] }) => void
}

/* Bring a row into view without moving the page: each scrollable ancestor from the row up to
 * `boundary` inclusive is adjusted, and nothing above it — so the document scroller is out of
 * reach by construction. */
const FOCUS = { preventScroll: true } as const

type Bring = 'start' | 'nearest'

function scrollWithin(target: HTMLElement, boundary: HTMLElement | null, mode: Bring): void {
  let node: HTMLElement | null = target.parentElement
  let next: Bring = mode
  while (node !== null) {
    if (node === document.body || node === document.documentElement) return
    if (node.scrollHeight > node.clientHeight) {
      bringInto(target, node, next)
      next = 'nearest'
    }
    if (node === boundary) return
    node = node.parentElement
  }
}

function bringInto(target: HTMLElement, scroller: HTMLElement, mode: Bring): void {
  const style = window.getComputedStyle(target)
  const rect = target.getBoundingClientRect()
  const box = scroller.getBoundingClientRect()
  const top = rect.top - (parseFloat(style.scrollMarginTop) || 0)
  const bottom = rect.bottom + (parseFloat(style.scrollMarginBottom) || 0)
  const edge = box.top + scroller.clientTop
  const foot = edge + scroller.clientHeight

  if (mode === 'start' || top < edge) {
    scroller.scrollTop += top - edge
    return
  }
  if (bottom > foot) scroller.scrollTop += bottom - foot
}

/* A pooled card — a count, not a location (D24). */
function isPooled(card: InventoryCard): boolean {
  return card.place?.located === false
}

function pooledText(card: InventoryCard, key: string): string {
  return `${card.place?.game_display ?? card.game ?? 'pooled'} · pooled · ${key}`
}

/* `mono` is for a machine string — the number, the set hint, the run name, a reason code.
 * `money` is Inter with tabular figures. Everything else is a word.
 *
 * `node` is drawn instead of `value` where the fact is a figure PLUS something quieter beside
 * it — a live count and how old the reading is. `value` stays required so every fact has a
 * plain-text form for the title attribute and for anything that reads the row as a string. */
type Detail = { label: string; value: string; kind?: 'mono' | 'money'; node?: ReactNode }

/** An enum value drawn as a word: `reverse_holofoil` → `Reverse Holofoil`. Only the first
 * letter of each word moves, so a value that already carries its own casing keeps it. */
function titleCase(raw: string): string {
  return raw
    .split(/[_\s]+/)
    .filter((word) => word !== '')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

/* The game as a word. The server's `game_display` when it is on the wire; the id otherwise,
 * through the few names title-casing gets wrong. */
const GAME_WORDS: Record<string, string> = {
  pokemon: 'Pokémon',
  pokemon_code: 'Pokémon code cards',
  one_piece: 'One Piece',
}
function gameWord(card: InventoryCard): string | null {
  if (card.place?.game_display) return card.place.game_display
  if (card.game === null) return null
  return GAME_WORDS[card.game] ?? titleCase(card.game)
}

/** A snake_case reason code — `no_market_data` — which is drawn verbatim, in mono. */
function isCode(text: string): boolean {
  return /^[a-z0-9]+(?:_[a-z0-9]+)+$/.test(text)
}

/** A set-valued claim, rendered — a bare string reads as a one-member set. `word` is how each
 * member is drawn; the default is verbatim, which is what a rarity string wants. */
function claimText(claim: string | string[] | null, word: (member: string) => string = (member) => member): string {
  const members = claimList(claim).map(word)
  return members.length === 0 ? 'none recorded' : members.join(' · ')
}

function claimList(claim: string | string[] | null): string[] {
  return (typeof claim === 'string' ? [claim] : (claim ?? [])).filter(
    (member) => typeof member === 'string' && member.trim() !== '',
  )
}

/* What a run's join said a card is worth, and how long ago it said it. The store has no price
 * in it (D8); the edge is card -> `run` -> that run's `pricing.json`, keyed by position. */
type MarketRead =
  | { kind: 'table'; at: number | null; rows: Record<string, string | null> }
  | { kind: 'absent'; why: string }

function marketTable(payload: PricingPayload): MarketRead {
  const rows: Record<string, string | null> = {}
  for (const priced of payload.pricing?.skus ?? []) {
    for (const at of priced.positions ?? []) {
      rows[`${at.box}/${at.index}`] = priced.snap?.market ?? null
    }
  }
  return { kind: 'table', at: payload.written_at ?? null, rows }
}

/* A price is never drawn without its age — the age of the JOIN. `no_market_data` verbatim,
 * because a blank Market cell is an UNKNOWN price rather than a low one. */
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

/* THE MARKET ROW AND THE LISTED ROW ARE ADJACENT AND SAY THE SAME KIND OF THING, so they say
 * it the same way. This one used to render `$0.34 · read 4d` — a terse compact age behind a
 * mid-dot — directly above `3 live  read 16 hours ago`, and read as two different kinds of
 * fact. One `ReadingAge`, one weight, one colour, both rows. */
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

type FactGroup = { title: string; facts: Detail[] }

/* WHAT THIS CARD'S SKU IS BELIEVED TO HAVE LIVE, AND WHEN THAT WAS LAST READ. The live count
 * is an estimate between runs (`store/master.py:Listing`), so the age is not decoration — it
 * is the difference between "TCGplayer is holding four of these" and "four is what we wrote
 * down on Tuesday". The record comes off `GET /inventory`'s own `listings` map. */
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
        <ReadingAge at={listing.at} />
      </span>
    ),
  }
}

function factGroupsOf(
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

/* When this card was photographed, as a person says it — local time, the year only when it is
 * not this one. A string that will not parse is returned verbatim. */
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

/** The open question about one position, or null — the entry and which queue it is in. */
function openQuestion(
  snapshot: QueueSnapshot | null,
  row: Row,
): { entry: QueueEntryWire; queue: 'review' | 'parked' } | null {
  if (snapshot === null) return null
  const mine = (entry: QueueEntryWire) =>
    entry.box === row.card.box && entry.index === row.card.index
  const inReview = snapshot.review.find(mine)
  if (inReview !== undefined) return { entry: inReview, queue: 'review' }
  const inParked = snapshot.parked.find(mine)
  return inParked === undefined ? null : { entry: inParked, queue: 'parked' }
}

/** How long ago a moment was, coarsely — `3 days`, `4 hours`, `today`. The compact form this
 *  used to carry is gone with its one caller: the Market row draws `ReadingAge` now, like the
 *  Listed row beside it. */
function sinceText(at: number): string {
  const elapsed = Date.now() - at
  const days = Math.floor(elapsed / 86400000)
  if (days >= 1) return `${days} day${days === 1 ? '' : 's'}`
  const hours = Math.floor(elapsed / 3600000)
  if (hours < 1) return 'today'
  return `${hours} hour${hours === 1 ? '' : 's'}`
}

function waitingFor(firstSeen: string): string {
  const at = Date.parse(firstSeen)
  return Number.isNaN(at) ? 'unknown age' : sinceText(at)
}

function numberCell(card: InventoryCard): string {
  return collectorNumber(card) ?? 'none'
}

/** The box named on the hash — `#/inventory?box=3`, the way the home screen links here. */
function boxParam(): number | null {
  const hash = window.location.hash
  const at = hash.indexOf('?')
  if (at === -1) return null
  const value = new URLSearchParams(hash.slice(at + 1)).get('box')
  if (value === null) return null
  const n = Number.parseInt(value, 10)
  return Number.isInteger(n) && n > 0 ? n : null
}

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches)
  useEffect(() => {
    const mql = window.matchMedia(query)
    const onChange = () => setMatches(mql.matches)
    mql.addEventListener('change', onChange)
    setMatches(mql.matches)
    return () => mql.removeEventListener('change', onChange)
  }, [query])
  return matches
}

export function BoxBrowse({
  head,
  detail,
  boxPanel,
  actionBar,
  onSelect,
  onBoxes,
  onListings,
  onScope,
  goTo,
  reloadToken = 0,
}: BoxBrowseProps) {
  const [rows, setRows] = useState<Row[] | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [selected, setSelected] = useState<string | null>(null)

  /* Which shelf the walk is of, or null before the first read has said which shelves exist. */
  const [shelf, setShelf] = useState<Shelf | null>(null)

  /* The mass-select, by store key. Not persisted; cleared when the box changes. */
  const [picked, setPicked] = useState<readonly string[]>([])

  /* Which sections are open, by section key. Per-box for free: a section key names a box. */
  const [opened, setOpened] = useState<readonly string[]>([])

  const [boxRecords, setBoxRecords] = useState<readonly BoxRecord[]>([])
  /* Every SKU's listing record, off the same read as the cards. Read for `at` — how old the
     live figures are — and never for a second copy of the counts. */
  const [listings, setListings] = useState<Readonly<Record<string, Listing>>>(NO_LISTINGS)
  /* The key whose photo 404'd, not a boolean. */
  const [photoAbsent, setPhotoAbsent] = useState<string | null>(null)
  /* The open questions, read once for the whole screen. Fails silent. */
  const [queued, setQueued] = useState<QueueSnapshot | null>(null)
  /* The market prices, one run's table at a time and cached by run name. */
  const [priced, setPriced] = useState<Record<string, MarketRead>>({})
  const asked = useRef<Set<string>>(new Set())
  const [reloads, setReloads] = useState(0)
  /* Each re-shot card's NEW capture id, by row key — the cache nonce the photo appends. */
  const [reshot, setReshot] = useState<Record<string, string>>({})
  const [reshootBusy, setReshootBusy] = useState<string | null>(null)
  const [reshootFailure, setReshootFailure] = useState<{ key: string; failure: Failure } | null>(
    null,
  )
  const listRef = useRef<HTMLUListElement | null>(null)
  const mapRef = useRef<HTMLDivElement | null>(null)
  const boxesRef = useRef<HTMLDivElement | null>(null)
  const jumpRef = useRef<string | null>(null)
  const [jump, setJump] = useState<string | null>(null)
  const askedAt = useRef<number | null>(null)
  /* The box the hash asked for, honoured once on the first read. */
  const wanted = useRef<number | null>(boxParam())

  /* Layout state: the phone's rail sheet, the desktop rail's collapse, the box sheet, the
     photo lightbox, the details disclosure. */
  const phone = useMediaQuery('(max-width: 767px)')
  const [railOpen, setRailOpen] = useState(false)
  const [railCollapsed, setRailCollapsed] = useState(false)
  const [manage, setManage] = useState(false)
  const [zoomed, setZoomed] = useState(false)
  const [detailsOpen, setDetailsOpen] = useState<boolean | null>(null)

  /* The search is the server's matcher filtering this screen's own list: the answer is read
   * for its copy KEYS and nothing else. No autoFocus: this screen is opened to WALK. */
  const { query, setQuery, results, loading, failure: searchFailure } = useSearch()
  const searching = query.trim() !== ''

  const matched = useMemo(() => {
    if (results === null) return null
    const keys = new Set<string>()
    for (const group of results.groups) for (const copy of group.copies) keys.add(copy.key)
    return keys
  }, [results])

  /* Filtered only when there is an answer to filter by. */
  const inQuery = useMemo(() => {
    if (rows === null) return NO_ROWS
    if (!searching || matched === null) return rows
    return rows.filter((row) => matched.has(row.key))
  }, [rows, searching, matched])

  const filtered = searching && matched !== null

  const shelves = useMemo(
    () => shelvesOf(inQuery, filtered ? [] : boxRecords.map((record) => record.box)),
    [inQuery, filtered, boxRecords],
  )

  const visible = useMemo(() => {
    if (shelf === null) return NO_ROWS
    return inQuery.filter((row) => shelfOf(row) === shelf)
  }, [inQuery, shelf])

  const sections = useMemo(() => sectionsOf(visible), [visible])

  /* How many matches each shelf holds under a query, for the box list. */
  const matchesByShelf = useMemo(() => {
    const out = new Map<Shelf, number>()
    if (!filtered) return out
    for (const row of inQuery) {
      const s = shelfOf(row)
      out.set(s, (out.get(s) ?? 0) + 1)
    }
    return out
  }, [inQuery, filtered])

  /* Every position with an open question, for the row badges. */
  const queuedKeys = useMemo(() => {
    const out = new Set<string>()
    if (queued === null) return out
    for (const entry of [...queued.review, ...queued.parked]) out.add(`${entry.box}/${entry.index}`)
    return out
  }, [queued])

  const shelfBox = useMemo(() => {
    if (typeof shelf !== 'number') return null
    return boxRecords.find((record) => record.box === shelf) ?? null
  }, [boxRecords, shelf])

  /* The re-shoot, from a picked file to the server. A fresh capture id per pick. */
  const beginReshoot = (row: Row, file: File) => {
    setReshootBusy(row.key)
    const reader = new FileReader()
    reader.onload = () => {
      const url = String(reader.result)
      const imageBase64 = url.slice(url.indexOf(',') + 1)
      const captureId = newCaptureId()
      reshootPhoto(row.card.box, row.card.index, imageBase64, captureId)
        .then(() => {
          setReshot((held) => ({ ...held, [row.key]: captureId }))
          setReshootBusy(null)
          setReshootFailure(null)
          setReloads((n) => n + 1)
          toast({ kind: 'ok', title: 'Photo replaced', body: row.key, icon: 'camera' })
        })
        .catch((err: unknown) => {
          setReshootBusy(null)
          const failed = describeFailure(err)
          setReshootFailure({ key: row.key, failure: failed })
          toast({ kind: 'refusal', title: failed.message, body: failed.code })
        })
    }
    reader.onerror = () => {
      setReshootBusy(null)
      setReshootFailure({
        key: row.key,
        failure: describeFailure(reader.error ?? new Error('the picked file could not be read')),
      })
    }
    reader.readAsDataURL(file)
  }

  useEffect(() => {
    let live = true
    getInventory()
      .then((inventory) => {
        if (!live) return
        const next = rowsOf(inventory.cards)
        setRows(next)
        const held = inventory.listings ?? NO_LISTINGS
        setListings(held)
        onListings?.(held)
        setFailure(null)
        setPhotoAbsent(null)
        /* Keep the selection across a reload when the card is still there. */
        setSelected((prev) =>
          prev !== null && next.some((row) => row.key === prev) ? prev : (landingOf(next)?.key ?? null),
        )
      })
      .catch((err: unknown) => {
        if (!live) return
        setRows(null)
        setFailure(describeFailure(err))
      })
    return () => {
      live = false
    }
  }, [reloads, reloadToken, onListings])

  /* The box registry, on the same counter and allowed to fail without anybody hearing. */
  useEffect(() => {
    let live = true
    getBoxes()
      .then((summary) => {
        if (!live) return
        const records = Array.isArray(summary.boxes) ? summary.boxes : []
        setBoxRecords(records)
        onBoxes?.(records)
      })
      .catch(() => {
        // Deliberately nothing: the walk is whole without this.
      })
    return () => {
      live = false
    }
  }, [reloads, reloadToken, onBoxes])

  useEffect(() => {
    let live = true
    getQueues()
      .then((snapshot) => {
        if (live) setQueued(snapshot)
      })
      .catch(() => {
        // Deliberately nothing — the panel is whole without it.
      })
    return () => {
      live = false
    }
  }, [reloads, reloadToken])

  /* A reload drops every cached price table. */
  useEffect(() => {
    asked.current = new Set()
    setPriced({})
  }, [reloads, reloadToken])

  /* The shelf follows the filter; the hash's box is honoured once, on the first pick. The ref
     is read and cleared in the effect body and never inside the updater: React runs an updater
     twice under StrictMode, and a ref consumed on the first pass left the second landing on
     box 1 with the hash still reading `?box=3`. */
  useEffect(() => {
    if (shelves.length === 0) return
    const askedFor = wanted.current
    wanted.current = null
    setShelf((prev) => {
      if (prev !== null && shelves.includes(prev)) return prev
      if (askedFor !== null && shelves.includes(askedFor)) return askedFor
      return shelves[0] ?? null
    })
  }, [shelves])

  /* The selection follows the filter. When nothing matches it is left alone. */
  useEffect(() => {
    if (visible.length === 0) return
    setSelected((prev) =>
      prev !== null && visible.some((row) => row.key === prev) ? prev : (landingOf(visible)?.key ?? null),
    )
  }, [visible])

  /* The ticks are the box's, so they go when the box does. */
  useEffect(() => {
    setPicked([])
  }, [shelf])

  /* One step, in the walk's own order. Both ends stop. */
  const stepSelection = useCallback(
    (delta: 1 | -1) => {
      setSelected((prev) => {
        const at = visible.findIndex((row) => row.key === prev)
        if (at === -1) {
          const landing = delta === 1 ? visible[0] : visible[visible.length - 1]
          return landing?.key ?? prev
        }
        return visible[at + delta]?.key ?? prev
      })
    },
    [visible],
  )

  /* The arrow keys, armed on the window so the walk needs no click to arm it. Auto-repeat is
   * the feature: holding Right walks the box. */
  useEffect(() => {
    if (visible.length === 0) return

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return
      const step = STEPS.find((candidate) => candidate.key === event.key)
      if (step === undefined) return
      if (isTyping(event.target)) return
      event.preventDefault()
      stepSelection(step.delta)
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [visible, stepSelection])

  /* Keep the selected row where it can be seen — within the rail, never by scrolling the page. */
  useEffect(() => {
    const current = listRef.current?.querySelector('[aria-current="true"]')
    if (current instanceof HTMLElement) {
      scrollWithin(current, mapRef.current, jumpRef.current === selected ? 'start' : 'nearest')
    }
    jumpRef.current = null
  }, [selected, visible])

  /* And the selected box, in a box list long enough to scroll. */
  useEffect(() => {
    const current = boxesRef.current?.querySelector('[aria-current="true"]')
    if (current instanceof HTMLElement) scrollWithin(current, boxesRef.current, 'nearest')
  }, [shelf])

  /* The deep keys: a React handler on the list, so focus within the list IS the scope. */
  const onListKeys = (event: ReactKeyboardEvent<HTMLUListElement>) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return
    if (isTyping(event.target)) return

    if (event.key.toLowerCase() === TICK_KEY.key) {
      event.preventDefault()
      if (selected !== null) toggleTick(selected)
      return
    }

    const edge = EDGE_KEYS.find((candidate) => candidate.key === event.key)
    const jumpTo = SECTION_KEYS.find((candidate) => candidate.key === event.key)
    if (edge === undefined && jumpTo === undefined) return

    event.preventDefault()

    if (edge !== undefined) {
      const landing = edge.last ? visible[visible.length - 1] : visible[0]
      if (landing !== undefined) setSelected(landing.key)
      return
    }
    if (jumpTo === undefined) return

    setSelected((prev) => {
      const at = sections.findIndex((section) => section.rows.some((row) => row.key === prev))
      if (at === -1) return sections[0]?.first.key ?? prev
      if (jumpTo.delta === 1) return sections[at + 1]?.first.key ?? prev
      const own = sections[at]
      if (own !== undefined && own.first.key !== prev) return own.first.key
      return sections[at - 1]?.first.key ?? prev
    })
  }

  /* A box press changes what the walk is of, scrolls the landing to the top and hands focus
   * to the list, arming the deep keys. The landing comes off `inQuery`, not `visible`. */
  const selectShelf = (next: Shelf) => {
    setShelf(next)
    const landing = landingOf(inQuery.filter((row) => shelfOf(row) === next))
    if (landing !== undefined) {
      jumpRef.current = landing.key
      setSelected(landing.key)
    }
    listRef.current?.focus(FOCUS)
  }

  const selectedRow = useMemo(
    () => visible.find((row) => row.key === selected) ?? null,
    [visible, selected],
  )

  /* What a bulk write would reach: the ticked rows in the box being walked, as indices. */
  const pickedIndices = useMemo(() => {
    if (rows === null || typeof shelf !== 'number') return []
    return rows
      .filter(
        (row) =>
          picked.includes(row.key) &&
          row.card.box === shelf &&
          typeof row.card.index === 'number' &&
          Number.isFinite(row.card.index),
      )
      .map((row) => row.card.index)
  }, [rows, picked, shelf])

  const isOpen = (section: Section) => opened.includes(section.key)
  const anyExpanded = sections.some((section) => opened.includes(section.key))

  const toggleAllSections = () =>
    setOpened(anyExpanded ? [] : sections.map((section) => section.key))

  const toggleSection = (section: Section) =>
    setOpened((held) =>
      held.includes(section.key)
        ? held.filter((key) => key !== section.key)
        : [...held, section.key],
    )

  const toggleTick = (key: string) =>
    setPicked((held) => (held.includes(key) ? held.filter((k) => k !== key) : [...held, key]))

  const tickSection = (section: Section, on: boolean) =>
    setPicked((held) => {
      const keys = section.rows.map((row) => row.key)
      const rest = held.filter((key) => !keys.includes(key))
      return on ? [...rest, ...keys] : rest
    })

  const shownAllTicked = visible.length > 0 && visible.every((row) => picked.includes(row.key))

  const tickAllShown = () =>
    setPicked((held) => {
      const keys = visible.map((row) => row.key)
      const rest = held.filter((key) => !keys.includes(key))
      return shownAllTicked ? rest : [...rest, ...keys]
    })

  /* The section the mark lands in is opened as a consequence of the move — including the
   * first one, so the walk never arrives with its selection hidden. A fold the operator asked
   * for is not undone on a re-read, because a re-read does not move the selection. */
  const openedFor = useRef<string | null>(null)
  useEffect(() => {
    if (selected === null || selected === openedFor.current) return
    const holding = sections.find((section) => section.rows.some((row) => row.key === selected))
    if (holding === undefined) return
    openedFor.current = selected
    setOpened((held) => (held.includes(holding.key) ? held : [...held, holding.key]))
  }, [selected, sections])

  /* A search opens every section it matches into. */
  useEffect(() => {
    if (!filtered) return
    setOpened((held) => {
      const shut = sections.filter((section) => !held.includes(section.key))
      return shut.length === 0 ? held : [...held, ...shut.map((section) => section.key)]
    })
  }, [filtered, sections])

  /* And gives it back when the query goes — folding everything but the section holding the
   * selection, so a cleared search leaves the walk showing the card the pane shows. */
  const latest = useRef({ sections, selected })
  latest.current = { sections, selected }
  const wasFiltered = useRef(false)
  useEffect(() => {
    if (filtered) {
      wasFiltered.current = true
      return
    }
    if (!wasFiltered.current) return
    wasFiltered.current = false
    const { sections: now, selected: mark } = latest.current
    const holding = now.find((section) => section.rows.some((row) => row.key === mark))
    setOpened(holding === undefined ? [] : [holding.key])
  }, [filtered])

  /* A jump is accepted here and landed below. */
  useEffect(() => {
    if (goTo === undefined || goTo === null) return
    if (askedAt.current === goTo.at) return
    askedAt.current = goTo.at
    setJump(goTo.key)
  }, [goTo])

  /* Walk to the card something outside asked for: the box, the fold, the mark and the scroll
   * in one batch. A query that hides the target is dropped rather than the jump. */
  useEffect(() => {
    if (jump === null) return
    if (rows === null) return
    const row = rows.find((candidate) => candidate.key === jump)
    if (row === undefined) {
      setJump(null)
      return
    }
    if (!inQuery.some((candidate) => candidate.key === jump)) {
      if (!searching) setJump(null)
      else setQuery('')
      return
    }
    const landing = shelfOf(row)
    const holding = sectionsOf(inQuery.filter((candidate) => shelfOf(candidate) === landing)).find(
      (section) => section.rows.some((candidate) => candidate.key === jump),
    )
    if (holding !== undefined) {
      setOpened((held) => (held.includes(holding.key) ? held : [...held, holding.key]))
    }
    setShelf(landing)
    jumpRef.current = jump
    setSelected(jump)
    listRef.current?.focus(FOCUS)
    setJump(null)
  }, [jump, rows, inQuery, searching, setQuery])

  useEffect(() => {
    onSelect?.(selectedRow)
  }, [selectedRow, onSelect])

  /* The selected card's run, read once and then not again — and re-asked after a reload. */
  const pricedRun = selectedRow?.card.run ?? null
  useEffect(() => {
    if (pricedRun === null) return
    if (asked.current.has(pricedRun)) return
    asked.current.add(pricedRun)
    let live = true
    getPricing(pricedRun)
      .then((payload) => {
        if (live) setPriced((held) => ({ ...held, [pricedRun]: marketTable(payload) }))
      })
      .catch((error: unknown) => {
        const why =
          describeFailure(error).code === 'pricing_not_written'
            ? 'join this run'
            : 'could not be read'
        if (live) setPriced((held) => ({ ...held, [pricedRun]: { kind: 'absent', why } }))
      })
    return () => {
      live = false
    }
  }, [pricedRun, reloads, reloadToken])

  useEffect(() => {
    onScope?.({ box: typeof shelf === 'number' ? shelf : null, indices: pickedIndices })
  }, [shelf, pickedIndices, onScope])

  /* The phone's sheet closes once a card is chosen; the box picker keeps it open. */
  const pickRow = (key: string) => {
    setSelected(key)
    if (phone) setRailOpen(false)
  }

  const selectedLabel = selectedRow === null ? null : positionLabel(selectedRow.card)
  const at = visible.findIndex((row) => row.key === selected)
  const boxMap = useMemo(() => new Map(boxRecords.map((record) => [record.box, record])), [boxRecords])

  /* The box list: every reachable shelf, and under a query the boxes with no match, dimmed. */
  const cells = useMemo(() => {
    const out: { shelf: Shelf; reachable: boolean }[] = shelves.map((s) => ({ shelf: s, reachable: true }))
    if (filtered) {
      for (const record of boxRecords) {
        if (!shelves.includes(record.box)) out.push({ shelf: record.box, reachable: false })
      }
      out.sort((a, b) => {
        const an = typeof a.shelf === 'number' ? a.shelf : Infinity
        const bn = typeof b.shelf === 'number' ? b.shelf : Infinity
        if (an !== bn) return an - bn
        return String(a.shelf).localeCompare(String(b.shelf))
      })
    }
    return out
  }, [shelves, filtered, boxRecords])

  const shelfName = shelfBox?.name ?? null
  const shelfChip =
    shelf === null ? 'Boxes' : `${shelfLabel(shelf)}${shelfName ? ` · ${shelfName}` : ''}`

  // ---------------------------------------------------------------------------- the rail

  const rail = (
    <div className="browse-map" ref={mapRef}>
      <div className="browse-map-top">
        <SearchField value={query} onChange={setQuery} persona="owner" />
        {phone ? null : (
          <Button
            variant="ghost"
            icon="chevronLeft"
            iconOnly
            className="browse-rail-toggle"
            onClick={() => setRailCollapsed(true)}
          >
            Collapse the box rail
          </Button>
        )}
      </div>

      {cells.length === 0 ? null : (
        <div className="browse-boxes bn-panel" role="group" aria-label="Choose a box to walk" ref={boxesRef}>
          {cells.map(({ shelf: cell, reachable }) => {
            const record = typeof cell === 'number' ? boxMap.get(cell) : undefined
            const onHand = record ? (record.on_hand ?? record.cards - record.sold - record.retired - record.moved) : null
            const pct = record && record.cards > 0 && onHand !== null ? Math.round((onHand / record.cards) * 100) : 0
            const sealed = record?.state === 'closed'
            const matches = matchesByShelf.get(cell)
            return (
              <button
                key={String(cell)}
                className="browse-boxcell"
                type="button"
                aria-label={
                  cell === 'pooled'
                    ? 'Pooled cards, which have no box'
                    : cell === 'unplaced'
                      ? 'Records with no readable box'
                      : `Box ${cell}${sealed ? ', sealed' : ''}`
                }
                aria-current={cell === shelf ? 'true' : undefined}
                disabled={!reachable}
                onClick={() => selectShelf(cell)}
              >
                <span className="browse-boxcell-num">
                  {typeof cell === 'number' ? cell : <Icon name={cell === 'pooled' ? 'layers' : 'alert'} size={14} />}
                </span>
                <span className="browse-boxcell-text">
                  <span
                    className="browse-boxcell-name"
                    title={typeof cell === 'number' ? (record?.name ?? `Box ${cell}`) : shelfLabel(cell)}
                  >
                    {typeof cell === 'number' ? (record?.name ?? `Box ${cell}`) : shelfLabel(cell)}
                  </span>
                  {/* The lock beside the row already says sealed; the meta keeps to the count. */}
                  <span className="browse-boxcell-meta">
                    {matches !== undefined
                      ? `${matches} ${matches === 1 ? 'match' : 'matches'}`
                      : record
                        ? `${(onHand ?? 0).toLocaleString()} on hand`
                        : cell === 'pooled'
                          ? 'a count, not a location'
                          : cell === 'unplaced'
                            ? 'no position at all'
                            : ''}
                  </span>
                </span>
                {record ? (
                  <span className="browse-boxcell-bar" aria-hidden="true">
                    <span style={{ width: `${pct}%` }} />
                  </span>
                ) : null}
                {sealed ? (
                  <span className="browse-boxcell-lock" title="Sealed">
                    <Icon name="lock" size={12} />
                  </span>
                ) : null}
                {record ? <span className="browse-boxcell-count">{record.cards.toLocaleString()}</span> : null}
              </button>
            )
          })}
        </div>
      )}

      {shelf === null ? null : (
        <div className="browse-walk bn-panel">
          <div className="browse-box-head">
            {shelfBox !== null ? (
              <BoxIdentity
                record={shelfBox}
                at={
                  selectedRow !== null && selectedRow.card.box === shelfBox.box
                    ? (selectedRow.card.place?.fraction ?? null)
                    : null
                }
                actions={
                  <Button
                    variant="quiet"
                    size="sm"
                    icon="settings"
                    className="browse-manage"
                    aria-haspopup="dialog"
                    onClick={() => setManage(true)}
                  >
                    Manage
                  </Button>
                }
              />
            ) : shelf === 'pooled' ? (
              <div className="browse-shelfnote">
                <span className="boxops-identity-num">Pooled</span>
                <p>A count, not a location. These cards have no box, section or card position.</p>
              </div>
            ) : (
              <div className="browse-shelfnote">
                <span className="boxops-identity-num">No box</span>
                <p>These records reached the store with a box or index that is not a number, so the server sent no position. The server status page lists them.</p>
              </div>
            )}
            {shelfBox === null ? null : boxPanel}
          </div>

          {searchFailure === null ? null : (
            <div className="browse-mapnote">
              <Notice tone="danger" title={searchFailure.message} code={searchFailure.code} />
            </div>
          )}

          <div className="browse-status">
            {/* While anything is ticked the selection leads the row — the count would only
                repeat the pill, and the three controls then fit the rail in one line. */}
            {picked.length > 0 ? (
              <>
                <Pill tone="accent" className="browse-status-picked">
                  {picked.length} ticked
                </Pill>
                <button className="browse-quiet" type="button" onClick={() => setPicked([])}>
                  clear
                </button>
              </>
            ) : sections.length < 2 ? (
              /* Under a search the match sentence carries the local count; a second one is noise. */
              searching ? null : (
                <span className="browse-status-text">
                  {visible.length.toLocaleString()} {visible.length === 1 ? 'card' : 'cards'}
                </span>
              )
            ) : (
              <button className="browse-quiet" type="button" onClick={toggleAllSections}>
                <Icon name={anyExpanded ? 'chevronUp' : 'chevronDown'} size={12} />
                {anyExpanded ? 'collapse all' : 'expand all'}
                <span className="browse-status-sep">·</span>
                {sections.length} sections
              </button>
            )}

            {searching && loading ? <span className="browse-status-text">Looking…</span> : null}
            {searching && !loading && results !== null ? (
              <span className="browse-status-text">
                {inQuery.length === 0
                  ? `nothing matches “${results.query}”`
                  : `${visible.length} here · ${inQuery.length} of ${rows?.length ?? 0} match`}
              </span>
            ) : null}

            <span className="bn-spacer" />

            {visible.length === 0 ? null : (
              <button className="browse-quiet" type="button" onClick={tickAllShown}>
                {shownAllTicked ? 'untick shown' : 'tick shown'}
              </button>
            )}
          </div>

          {visible.length === 0 && !filtered && shelfBox !== null ? (
            <div className="browse-empty">
              <EmptyState
                icon="box"
                title={`Nothing in box ${shelfBox.box} yet`}
                body="Capture a card into it, or manage the box above — rename, divide, seal or delete it."
                actions={
                  <Button size="sm" icon="camera" onClick={() => (window.location.hash = '#/capture')}>
                    Capture into box {shelfBox.box}
                  </Button>
                }
              />
            </div>
          ) : null}

          {visible.length === 0 && filtered ? (
            <div className="browse-empty">
              <EmptyState
                icon="search"
                title="Nothing matches here"
                body={`No card in ${shelfLabel(shelf)} matches “${query.trim()}”.`}
                actions={
                  <Button size="sm" icon="x" onClick={() => setQuery('')}>
                    Clear the search
                  </Button>
                }
              />
            </div>
          ) : null}

          {visible.length === 0 ? null : (
            <ul
              className="browse-list"
              ref={listRef}
              tabIndex={0}
              aria-label="Captured cards, in box-walk order"
              aria-keyshortcuts="ArrowLeft ArrowRight PageUp PageDown Home End X"
              onKeyDown={onListKeys}
            >
              {sections.map((section) => {
                const open = isOpen(section)
                const ticked = section.rows.filter((row) => picked.includes(row.key)).length
                /* The pill counts what the title's range counts — the cards on hand. A
                 * departed record has no slot, so it is in the tick's population and in the
                 * title, and not in the figure beside a range it is not part of. */
                const onHand = section.rows.filter((row) => !hasDeparted(row.card)).length
                const gone = section.rows.length - onHand
                const census =
                  gone === 0
                    ? `${section.rows.length} ${section.rows.length === 1 ? 'card' : 'cards'}`
                    : `${onHand} on hand · ${gone} departed · ${section.rows.length} records`
                return (
                  <li className="browse-group" key={section.key}>
                    <div className="browse-secthead">
                      <input
                        className="browse-secttick browse-tick"
                        type="checkbox"
                        checked={ticked > 0 && ticked === section.rows.length}
                        ref={(node) => {
                          if (node !== null)
                            node.indeterminate = ticked > 0 && ticked < section.rows.length
                        }}
                        aria-label={`Tick every card in ${section.title} (${census})`}
                        onChange={(event) => tickSection(section, event.target.checked)}
                      />
                      <button
                        className="browse-sectfold"
                        type="button"
                        aria-expanded={open}
                        onClick={() => toggleSection(section)}
                      >
                        <Icon name="chevronRight" size={14} className="browse-sectmark" />
                        <span className="browse-secttitle">{section.title}</span>
                        <span
                          className="browse-sectcount"
                          title={ticked === 0 ? census : `${ticked} of ${section.rows.length} records ticked · ${census}`}
                        >
                          {ticked === 0 ? onHand : `${ticked}/${section.rows.length}`}
                        </span>
                      </button>
                    </div>
                    {!open ? null : (
                      <ul className="browse-group-rows">
                        {section.rows.map((row) => {
                          const departed = hasDeparted(row.card)
                          return (
                            <li
                              className={departed ? 'browse-rowline is-departed' : 'browse-rowline'}
                              key={row.key}
                            >
                              <input
                                className="browse-rowtick browse-tick"
                                type="checkbox"
                                checked={picked.includes(row.key)}
                                aria-label={`Tick ${departed ? `departed ${rowSlot(row)}` : rowSlot(row)}`}
                                onChange={() => toggleTick(row.key)}
                              />
                              <button
                                className="browse-row"
                                type="button"
                                aria-current={row.key === selected ? 'true' : undefined}
                                title={departed ? 'Departed — no longer in this box' : undefined}
                                onClick={() => pickRow(row.key)}
                              >
                                <span className="browse-row-position">{rowSlot(row)}</span>
                                {/* NEVER the state word here: the row would read `#1
                                    Identified` while the hero for the same card reads `Not
                                    identified yet`. One phrase, dimmed, on every surface that
                                    has no name to draw (hero, claims sheet, this row). */}
                                <span
                                  className={
                                    nameOf(row.card) === null
                                      ? 'browse-row-name is-unnamed'
                                      : 'browse-row-name'
                                  }
                                >
                                  {nameOf(row.card) ?? 'Not identified yet'}
                                </span>
                                {departed ? (
                                  <span className="browse-row-badge is-out" aria-hidden="true">
                                    <Icon name="external" size={12} />
                                  </span>
                                ) : null}
                                {queuedKeys.has(row.key) ? (
                                  <span className="browse-row-badge" title="Waiting in a queue">
                                    <Icon name="clock" size={12} />
                                  </span>
                                ) : null}
                              </button>
                            </li>
                          )
                        })}
                      </ul>
                    )}
                  </li>
                )
              })}
            </ul>
          )}

          <p className="browse-listkeys">
            <span>
              <Kbd>←</Kbd>
              <Kbd>→</Kbd> card
            </span>
            <span>
              <Kbd>PgUp</Kbd>
              <Kbd>PgDn</Kbd> section
            </span>
            <span>
              <Kbd>X</Kbd> tick
            </span>
          </p>
        </div>
      )}
    </div>
  )

  const miniRail = (
    <div className="browse-rail-mini">
      <Button
        variant="ghost"
        icon="chevronRight"
        iconOnly
        onClick={() => setRailCollapsed(false)}
      >
        Expand the box rail
      </Button>
      {cells
        .filter((cell) => typeof cell.shelf === 'number')
        .map(({ shelf: cell }) => (
          <button
            key={String(cell)}
            type="button"
            className="browse-boxcell-mini"
            aria-label={`Box ${cell}`}
            aria-current={cell === shelf ? 'true' : undefined}
            onClick={() => {
              selectShelf(cell)
              setRailCollapsed(false)
            }}
          >
            {cell}
          </button>
        ))}
    </div>
  )

  // ---------------------------------------------------------------------------- the pane

  const open = selectedRow === null ? null : openQuestion(queued, selectedRow)
  const game = selectedRow === null ? null : gameWord(selectedRow.card)

  return (
    <section className="browse">
      <PageHeader
        eyebrow="Library"
        title={head ?? 'Inventory'}
        icon="box"
        lede={
          rows === null
            ? failure === null
              ? 'Reading the inventory…'
              : 'The inventory could not be read.'
            : 'Walk any box card by card. Sell, retire or move a copy from here.'
        }
        actions={
          rows === null ? null : (
            <Pill mono className="browse-census">
              {rows.length.toLocaleString()} {rows.length === 1 ? 'card' : 'cards'} · {boxRecords.length}{' '}
              {boxRecords.length === 1 ? 'box' : 'boxes'}
            </Pill>
          )
        }
      />

      {failure === null ? null : (
        <Notice tone="danger" title={failure.message} code={failure.code}>
          <Button size="sm" icon="refresh" onClick={() => setReloads((n) => n + 1)}>
            Try again
          </Button>
        </Notice>
      )}

      {rows === null && failure === null ? (
        <div className="browse-body browse-body-loading">
          <div className="browse-map">
            <div className="bn-skeleton browse-skel-search" />
            <div className="bn-panel browse-skel-panel">
              {Array.from({ length: 5 }, (_, i) => (
                <div key={i} className="bn-skeleton browse-skel-row" />
              ))}
            </div>
          </div>
          <div className="browse-side">
            <div className="bn-panel browse-card">
              <div className="browse-hero-head">
                <div className="bn-skeleton" style={{ width: 260, height: 26 }} />
              </div>
              <div className="browse-band">
                <div className="bn-skeleton browse-skel-photo" />
                <div className="bn-stack">
                  <div className="bn-skeleton" style={{ height: 120 }} />
                  <div className="bn-skeleton" style={{ height: 80 }} />
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {rows !== null && rows.length === 0 ? (
        <div className="bn-panel">
          <EmptyState
            icon="camera"
            title="No cards captured yet"
            body="Every card you capture gets an address — a box, a section, a card number — and shows up here."
            actions={
              <Button variant="primary" icon="camera" onClick={() => (window.location.hash = '#/capture')}>
                Capture your first card
              </Button>
            }
          />
        </div>
      ) : null}

      {rows !== null && rows.length > 0 ? (
        <>
          {phone ? (
            <div className="browse-mobilebar">
              <button
                type="button"
                className="browse-boxchip"
                aria-haspopup="dialog"
                onClick={() => setRailOpen(true)}
              >
                <Icon name="box" size={16} />
                <span className="browse-boxchip-text">{shelfChip}</span>
                {at >= 0 ? <span className="browse-boxchip-count">{at + 1}/{visible.length}</span> : null}
                <Icon name="chevronDown" size={14} className="browse-boxchip-chev" />
              </button>
              <Button variant="quiet" icon="search" iconOnly onClick={() => setRailOpen(true)}>
                Search cards
              </Button>
            </div>
          ) : null}

          <div className="browse-body" data-rail={railCollapsed && !phone ? 'collapsed' : undefined}>
            {phone ? null : railCollapsed ? miniRail : rail}

            <div className="browse-side">
              {selectedRow === null ? (
                <div className="bn-panel">
                  {filtered ? (
                    <EmptyState
                      icon="search"
                      title={`Nothing matches “${query.trim()}”`}
                      body="The search reads the card's name, number, SKU, set hint and note."
                      actions={
                        <Button icon="x" onClick={() => setQuery('')}>
                          Clear the search
                        </Button>
                      }
                    />
                  ) : (
                    <EmptyState
                      icon="box"
                      title={shelf === null ? 'Pick a box' : `Nothing in ${shelfLabel(shelf)} yet`}
                      body="Choose a box on the left, or capture a card into this one."
                      actions={
                        <Button icon="camera" onClick={() => (window.location.hash = '#/capture')}>
                          Capture a card
                        </Button>
                      }
                    />
                  )}
                </div>
              ) : (
                <>
                  <section className="bn-panel browse-card" key={selectedRow.key}>
                    <div className="browse-hero-head">
                      <div className="browse-hero-text">
                        <h2 className={nameOf(selectedRow.card) === null ? 'browse-hero-name is-unnamed' : 'browse-hero-name'}>
                          {nameOf(selectedRow.card) ?? 'Not identified yet'}
                        </h2>
                        <p className="browse-hero-sub">
                          {[numberCell(selectedRow.card) === 'none' ? null : numberCell(selectedRow.card), selectedRow.card.set_hint, game]
                            .filter((part): part is string => typeof part === 'string' && part !== '')
                            .map((part, i) => (
                              <span key={`${part}-${i}`} className={i === 0 && numberCell(selectedRow.card) !== 'none' ? 'browse-hero-number' : undefined}>
                                {part}
                              </span>
                            ))}
                        </p>
                        <div className="browse-hero-chips">
                          {claimList(selectedRow.card.metadata_finish).map((finish) => (
                            <Pill key={`f-${finish}`} icon="sparkles">
                              {titleCase(finish)}
                            </Pill>
                          ))}
                          {claimList(selectedRow.card.rarity_claim).map((rarity) => (
                            <Pill key={`r-${rarity}`}>{titleCase(rarity)}</Pill>
                          ))}
                          <Pill tone={stateTone(selectedRow.card.state)} outline={selectedRow.card.state === 'identified'}>
                            {stateLabel(selectedRow.card.state)}
                          </Pill>
                          {open === null ? null : (
                            <a className="bn-pill bn-pill-warn browse-queuechip" href="#/review">
                              <Icon name="clock" size={12} />
                              In the {open.queue} queue
                            </a>
                          )}
                        </div>
                      </div>
                      <CardOps
                        key={selectedRow.key}
                        row={selectedRow}
                        onChanged={() => setReloads((n) => n + 1)}
                        reshoot={
                          <ReshootControl
                            row={selectedRow}
                            busy={reshootBusy === selectedRow.key}
                            failure={
                              reshootFailure !== null && reshootFailure.key === selectedRow.key
                                ? reshootFailure.failure
                                : null
                            }
                            onPick={(file) => beginReshoot(selectedRow, file)}
                          />
                        }
                      />
                    </div>

                    {open === null ? null : (
                      <div className="browse-queued">
                        <Notice tone="warn" title={`Waiting in the ${open.queue} queue — ${reasonLabel(open.entry.reason)}.`} code={`${open.entry.reason} · ${open.queue} · candidates ${open.entry.candidates.length}`}>
                          {waitingFor(open.entry.first_seen)}.{' '}
                          {open.entry.candidates.length > 0
                            ? `${open.entry.candidates.length} candidate row${open.entry.candidates.length === 1 ? '' : 's'} to choose from on the review screen.`
                            : 'No candidate rows, so it cannot be answered as it stands — re-shoot it, or stand it down from the review screen.'}{' '}
                          <a href="#/review">Open the review queue</a>
                        </Notice>
                      </div>
                    )}

                    <div className="browse-band">
                      <div className="browse-shot">
                        <PhotoPanel
                          row={selectedRow}
                          label={selectedLabel}
                          absent={photoAbsent === selectedRow.key}
                          onAbsent={() => setPhotoAbsent(selectedRow.key)}
                          nonce={reshot[selectedRow.key] ?? null}
                          onZoom={() => setZoomed(true)}
                          reshoot={
                            <ReshootControl
                              row={selectedRow}
                              busy={reshootBusy === selectedRow.key}
                              failure={
                                reshootFailure !== null && reshootFailure.key === selectedRow.key
                                  ? reshootFailure.failure
                                  : null
                              }
                              onPick={(file) => beginReshoot(selectedRow, file)}
                            />
                          }
                        />
                      </div>
                      <div className="browse-under">{detail}</div>
                    </div>
                  </section>

                  <details
                    className="bn-panel browse-details"
                    open={detailsOpen ?? !phone}
                    onToggle={(event) => setDetailsOpen(event.currentTarget.open)}
                  >
                    <summary className="browse-details-summary">
                      <Icon name="chevronRight" size={14} className="browse-details-chev" />
                      <span className="bn-section-title">Details</span>
                      <span className="browse-details-hint">identity · claims · provenance</span>
                    </summary>
                    <div className="browse-about">
                      {factGroupsOf(
                        selectedRow.card,
                        selectedRow.card.run === null ? undefined : priced[selectedRow.card.run],
                        listings,
                      ).map((group) => (
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
                </>
              )}
            </div>
          </div>

          {phone ? (
            <div className="browse-actionbar">
              <div className="browse-stepper" role="group" aria-label="Step through the box">
                <button
                  type="button"
                  className="browse-stepper-btn"
                  aria-label="Previous card"
                  disabled={visible.length === 0 || at <= 0}
                  onClick={() => stepSelection(-1)}
                >
                  <Icon name="chevronLeft" size={18} />
                </button>
                <span className="browse-stepper-count">
                  {at >= 0 ? `${at + 1} / ${visible.length}` : '—'}
                </span>
                <button
                  type="button"
                  className="browse-stepper-btn"
                  aria-label="Next card"
                  disabled={visible.length === 0 || at >= visible.length - 1}
                  onClick={() => stepSelection(1)}
                >
                  <Icon name="chevronRight" size={18} />
                </button>
              </div>
              <div className="browse-actionbar-slot">{actionBar}</div>
            </div>
          ) : null}
        </>
      ) : null}

      {phone && railOpen ? (
        <Overlay kind="bottom" label="Boxes and cards" onClose={() => setRailOpen(false)} passKeys className="browse-railsheet">
          {rail}
        </Overlay>
      ) : null}

      {shelfBox === null ? null : (
        <BoxOps
          record={shelfBox}
          selection={pickedIndices}
          boxes={boxRecords}
          listings={listings}
          open={manage}
          onClose={() => setManage(false)}
          onChanged={() => setReloads((n) => n + 1)}
        />
      )}

      {zoomed && selectedRow !== null && selectedRow.card.photo !== null ? (
        <Overlay kind="lightbox" label="The photograph, full size" onClose={() => setZoomed(false)}>
          <img
            src={photoSrc(selectedRow, reshot[selectedRow.key] ?? null)}
            alt={`The card photographed at ${selectedLabel ?? `store key ${selectedRow.key}`}`}
          />
        </Overlay>
      ) : null}
    </section>
  )
}

/* THE URL NAMES THE PHOTOGRAPH, NOT THE SLOT (D52): `capture_id` is stable for the life of a
 * photograph, so a URL only changes when the thing behind it does. A re-shoot's new id wins
 * while it is set. */
function photoSrc(row: Row, nonce: string | null): string {
  const base = photoUrl(row.card.box, row.card.index)
  const stamp = nonce ?? row.card.capture_id
  return stamp === null ? base : `${base}?card=${encodeURIComponent(stamp)}`
}

type PhotoPanelProps = {
  row: Row
  label: string | null
  absent: boolean
  onAbsent: () => void
  nonce: string | null
  onZoom: () => void
  reshoot: ReactNode
}

/* Three ways a photo can be missing, and they are different facts: never stored, reclaimed on
 * purpose after the sale (D89), or claimed and not on disk. Each is a card-shaped placeholder
 * with the add-a-photo control on it. */
function PhotoPanel({ row, label, absent, onAbsent, nonce, onZoom, reshoot }: PhotoPanelProps) {
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
        /* Remounted per card, per occupant and per replacement. */
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

/* The re-shoot control — a file, not a camera. Never drawn for a sold or retired card. */
type ReshootControlProps = {
  row: Row
  busy: boolean
  failure: Failure | null
  onPick: (file: File) => void
}

function ReshootControl({ row, busy, failure, onPick }: ReshootControlProps) {
  const inputRef = useRef<HTMLInputElement | null>(null)

  if (row.card.state === 'sold' || row.card.state === 'retired') return null

  /* The label stays put while busy; the button's own spinner says the replacement is in flight. */
  const label = row.card.photo === null ? 'Add a photo' : 'Re-shoot this photo'

  return (
    <div className="browse-reshoot">
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg"
        hidden
        onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = ''
          if (file !== undefined) onPick(file)
        }}
      />
      <Button size="sm" icon="camera" busy={busy} onClick={() => inputRef.current?.click()}>
        {label}
      </Button>
      {failure === null ? null : <Notice tone="danger" title={failure.message} code={failure.code} />}
    </div>
  )
}

/* THE CARD-LEVEL OPERATIONS behind one menu: correct what this card claims (with the re-shoot
 * inside), and delete a junk capture out of the middle of a box. The correction is reversible
 * and takes no confirm; the mid-box delete renumbers and asks a second time. Neither is drawn
 * for a sold or retired card. */
function CardOps({
  row,
  onChanged,
  reshoot,
}: {
  row: Row
  onChanged: () => void
  reshoot?: ReactNode
}) {
  const [menu, setMenu] = useState(false)
  const [open, setOpen] = useState<'claims' | 'delete' | null>(null)
  const [busy, setBusy] = useState(false)
  const [trouble, setTrouble] = useState<Failure | null>(null)
  const anchor = useRef<HTMLDivElement | null>(null)

  const terminal = row.card.state === 'sold' || row.card.state === 'retired'
  const addressable =
    typeof row.card.box === 'number' &&
    Number.isFinite(row.card.box) &&
    typeof row.card.index === 'number' &&
    Number.isFinite(row.card.index)

  useEffect(() => {
    if (!menu) return
    const onDown = (event: MouseEvent) => {
      if (anchor.current !== null && !anchor.current.contains(event.target as Node)) setMenu(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenu(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [menu])

  const correct = async (patch: ClaimPatch) => {
    if (busy) return
    setBusy(true)
    setTrouble(null)
    try {
      await updateCard(row.card.box, row.card.index, patch)
      toast({ kind: 'ok', icon: 'wand', title: 'Claims written', body: `${row.key} · ${Object.keys(patch).join(' · ')}` })
      setOpen(null)
      onChanged()
    } catch (err) {
      setTrouble(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    if (busy) return
    setBusy(true)
    setTrouble(null)
    try {
      /* The capture id is the aim, sent exactly as the record holds it, null included. */
      const result: RemoveResult = await removeCardInPlace(row.card.box, row.card.index, row.card.capture_id)
      toast({
        kind: 'ok',
        icon: 'trash',
        title:
          result.shifted === 0
            ? 'Capture removed'
            : `Capture removed · ${result.shifted} ${result.shifted === 1 ? 'card' : 'cards'} moved down`,
        body: `${
          result.shifted === 0
            ? 'It was the top of its box, so nothing moved.'
            : 'Every card behind it moved down one index — every one of those labels has changed.'
        } ${result.deleted} is removed and the box's next index is ${result.next_index}. ${
          result.photo_deleted
            ? result.sidecar_deleted
              ? 'Its photograph and sidecar went with it.'
              : 'Its photograph went with it; no sidecar was on disk.'
            : 'No photograph was on disk to delete.'
        }`,
        ttlMs: 12000,
      })
      setOpen(null)
      onChanged()
    } catch (err) {
      setTrouble(describeFailure(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="browse-cardops" ref={anchor}>
      <Button
        variant="quiet"
        icon="more"
        iconOnly
        aria-haspopup="menu"
        aria-expanded={menu}
        onClick={() => setMenu((held) => !held)}
      >
        Card actions
      </Button>
      {!menu ? null : (
        <div className="bn-menu browse-menu" role="menu">
          <button
            role="menuitem"
            type="button"
            className="bn-menu-item"
            onClick={() => {
              setMenu(false)
              setTrouble(null)
              setOpen('claims')
            }}
          >
            <Icon name="wand" size={16} /> Correct claims
          </button>
          {/* The screen re-reads after every write of its own; this is for a write made on
              another device. */}
          <button
            role="menuitem"
            type="button"
            className="bn-menu-item"
            onClick={() => {
              setMenu(false)
              onChanged()
            }}
          >
            <Icon name="refresh" size={16} /> Re-read the inventory
          </button>
          {terminal || !addressable ? (
            <p className="browse-menu-note">
              This card has left inventory, so it cannot be removed from its box.
            </p>
          ) : (
            <>
              <div className="bn-menu-sep" />
              <button
                role="menuitem"
                type="button"
                className="bn-menu-item bn-menu-item-danger"
                onClick={() => {
                  setMenu(false)
                  setTrouble(null)
                  setOpen('delete')
                }}
              >
                <Icon name="trash" size={16} /> Remove this card…
              </button>
            </>
          )}
        </div>
      )}

      {open !== 'claims' ? null : (
        <Overlay kind="sheet" label="Correct claims" onClose={() => setOpen(null)} className="browse-claims-sheet">
          <header className="inv-sheet-head">
            <div className="inv-sheet-head-text">
              {/* The ADDRESS, not the store key: `1/1` in an eyebrow reads as a page counter. */}
              <span className="bn-eyebrow">{positionLabel(row.card) ?? `store key ${row.key}`}</span>
              <h2 className="inv-sheet-title">Correct claims</h2>
              <p className="browse-claims-who">{nameOf(row.card) ?? 'Not identified yet'}</p>
            </div>
            <Button variant="ghost" icon="x" iconOnly onClick={() => setOpen(null)}>
              Close
            </Button>
          </header>
          <div className="inv-sheet-body">
            {reshoot === undefined ? null : (
              <section className="browse-claims-photo">
                <span className="bn-label">Photograph</span>
                {reshoot}
              </section>
            )}
            <ClaimEditor
              scope="this card"
              game={row.card.game}
              busy={busy}
              onApply={(patch) => void correct(patch)}
              onCancel={() => setOpen(null)}
            />
            {trouble === null ? null : <Notice tone="danger" title={trouble.message} code={trouble.code} />}
          </div>
        </Overlay>
      )}

      {open !== 'delete' ? null : (
        <Overlay kind="dialog" label="Remove this card" onClose={() => setOpen(null)}>
          <div className="inv-dialog-head">
            <span className="bn-eyebrow">Box {row.card.box} · {row.key}</span>
            <h2 className="inv-dialog-title">Remove this card and slide the box down?</h2>
          </div>
          <div className="inv-dialog-body">
            <p>
              This deletes the record, the photograph and the sidecar, and{' '}
              <strong>every card behind it in box {row.card.box} moves down one index</strong> —
              so every stored position above it changes. There is no undo, and this card is not
              necessarily still in your hand.
            </p>
            <p className="bn-muted">
              It is refused if any card behind it has been sold, retired or listed: those records
              are departures and commitments rather than clutter.
            </p>
            <span className="browse-machine">
              aiming at capture id {row.card.capture_id ?? 'null (written before ids existed)'}
            </span>
            {trouble === null ? null : <Notice tone="danger" title={trouble.message} code={trouble.code} />}
          </div>
          <div className="inv-dialog-foot">
            <Button variant="ghost" onClick={() => setOpen(null)} data-autofocus="">
              Cancel
            </Button>
            <Button variant="danger-solid" icon="trash" busy={busy} onClick={() => void remove()}>
              Remove this card and slide the box down
            </Button>
          </div>
        </Overlay>
      )}
    </div>
  )
}
