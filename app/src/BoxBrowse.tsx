import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import type { CSSProperties, KeyboardEvent as ReactKeyboardEvent, ReactNode } from 'react'

import { isEditableTarget } from './keys'
import { placePartsOf, sayPlace, sectionCountOf, sectionCountWords, sectionTitleText, type SectionTitleParts } from './position'
import { SectionTitle } from './SectionTitle'
import type {
  BoxRecord,
  FacetCell,
  InventoryCard,
  Listing,
  QueueEntryWire,
  QueueSnapshot,
  RemoveResult,
  SearchCopy,
  SearchGroup,
} from './types'
import type { SaleResult } from './types'
import type { Failure } from './server'
import {
  describeFailure,
  isDeparted,
  positionLabel,
  getBoxes,
  getQueues,
  getInventoryBox,
  getPricing,
  getValueAggregates,
  photoUrl,
  removeCardInPlace,
  reshootPhoto,
  updateCard,
  newCaptureId,
  undoRetire,
  undoSale,
} from './server'
import { BoxIdentity, BoxOps, ClaimEditor, type ClaimPatch } from './BoxOps'
import { reasonLabel } from './reasons'
import {
  CardDetailsSection,
  claimList,
  gameLabel,
  gameWord,
  marketTable,
  nameOf,
  numberCell,
  PhotoPanel,
  photoSrc,
  titleCase,
  type MarketRead,
  type Row,
} from './CardHero'
import { IDENTIFIED, stateLabel, stateTone } from './cardState'
import { storeKeyText } from './storeKey'
import { useSearch } from './useSearch'
import { Button, Chip, EmptyState, FilterBar, HideToggle, Icon, IconButton, Loading, Money, Notice, Pill, boxesMostRecentFirst, countFacets, filterRows, type SortValue } from './kit'
import { UNNAMED_BOX } from './kit/data'
import type { FilterFacet, FilterValue } from './kit/data'
import { useFacetParams } from './kit/viewState'
import { storedBoxRecency, touchBox } from './deviceMemory'
import { toast } from './kit/toast'
import { Dialog as Overlay } from './kit/overlay'
import { RANK_IS_CURRENT, ranksAsLive, ranksAsShown, type FrozenRank } from './frozenRank'
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
 * where a row carries no label — never parsed into a position. `Row` itself now lives in
 * `CardHero.tsx` (re-exported here so `Inventory.tsx`'s own `import { BoxBrowse, type Row }
 * from './BoxBrowse'` keeps working) — `#/orders`' walk pane builds one too. */
export type { Row } from './CardHero'

/* Box-walk order — box, then index — the order the cards physically sit in. */
function rowsOf(cards: Record<string, InventoryCard>): Row[] {
  return Object.entries(cards)
    .map(([key, card]) => ({ key, card }))
    .sort((a, b) => a.card.box - b.card.box || a.card.index - b.card.index)
}

const NO_ROWS: Row[] = []
const EMPTY_GROUPS: SearchGroup[] = []

/** Strips a trailing parenthetical off a card name — `"Calm Rune (R02a)"` -> `"Calm Rune"` —
 *  so a base printing and its promo/alt-art siblings fold to the same key. This is the ONE
 *  naming convention this store's own data was measured to use for "another printing of the
 *  same card": `pkmnscan cards name`'s corpus and the real Riftbound export both carry the
 *  parenthetical suffix on exactly the rows that are a variant of the un-suffixed name, never
 *  on an unrelated card that happens to share a word. */
function baseCardName(name: string): string {
  return name.replace(/\s*\([^()]*\)\s*$/, '').trim()
}

/** THE "SAME CARD" TEST (2026-09-17 regression fix). `results.groups` is several SKUs
 *  whenever a search's matched cards span more than one SKU — and that shape means two very
 *  different things depending on what those SKUs ARE:
 *
 *   - several PRINTINGS of one card (`Mind Rune`: 3 SKUs, `names: ['Mind Rune']` on every one
 *     of them; `Vanguard Armory`: 2 SKUs, same story, differing only by condition) — the
 *     missing level this branch built the chooser for.
 *   - several DIFFERENT cards that merely share a `set_hint` (`ME01`: ~110 SKUs, each with its
 *     own name — Abra, Bayleef, Bewear, ... — because a set hint is a fact about the BOX, not
 *     the card) — the case that regressed: the chooser drew over a plain multi-card search and
 *     swallowed the walk the two `inventory.spec.ts` tests below depend on.
 *
 *  MEASURED against the real store (`do_search`, read-only) before choosing: every "same
 *  card" case above has every group's `names` identical once a trailing parenthetical variant
 *  suffix is stripped (`baseCardName`); every "different cards" case has a distinct base name
 *  per group, with one group (`Corphish`) even disagreeing WITHIN itself on spelling — which
 *  is a fact about that one SKU's own copies, not a reason to compare across groups by
 *  anything looser than exact base-name equality. So: several groups are the same card only
 *  when EVERY group has at least one name, and stripping the parenthetical from every name in
 *  every group leaves exactly one base name across the whole result. A group with no name at
 *  all (an unidentified card) never satisfies this — D22's free-text note case is not a
 *  "printing" of anything, and a query cannot equal a null name in the first place, so this
 *  never actually excludes a real match. */
function groupsAreSamePrinting(groups: readonly SearchGroup[]): boolean {
  if (groups.length < 2) return false
  let shared: string | null = null
  for (const group of groups) {
    if (group.names.length === 0) return false
    for (const name of group.names) {
      const base = baseCardName(name)
      if (base === '') return false
      if (shared === null) shared = base
      else if (base !== shared) return false
    }
  }
  return shared !== null
}

/** No listing records read yet. Not the same as "this store has listed nothing". */
const NO_LISTINGS: Readonly<Record<string, Listing>> = {}

/* Where a walk lands: the first card still on hand, so a box never opens on a departed record
 * while it holds a card to look at; the first row only when nothing is. */
function landingOf(rows: readonly Row[]): Row | undefined {
  return rows.find((row) => !hasDeparted(row.card)) ?? rows[0]
}

/* Where a SEARCH lands (D132 amended, the owner's rule): the first live row of the section
 * holding the most live rows — the place a hand can pull the most from. Ties go to the section
 * met first in walk order; with nothing live, `landingOf`'s answer.
 *
 * IT TAKES NO FREEZE, AND THAT IS A DELETION RATHER THAN AN OMISSION (`frozenRank.ts`). The
 * first build threaded one through here for symmetry with the rail and the copies list. It is
 * unreachable: this runs only when the query is FRESH, and a fresh query is exactly what
 * releases the freeze — so the argument could only ever be empty, and a mutation deleting it
 * left the whole suite green. A parameter no call can populate is a claim nothing can check. */
function landingInFullest(rows: readonly Row[]): Row | undefined {
  const counts = new Map<string, number>()
  const keyOf = (row: Row) => `${row.card.box}/${row.card.section ?? '?'}`
  const live = (row: Row) => !hasDeparted(row.card)
  for (const row of rows) {
    if (!live(row)) continue
    counts.set(keyOf(row), (counts.get(keyOf(row)) ?? 0) + 1)
  }
  let best: Row | undefined
  let most = 0
  for (const row of rows) {
    if (!live(row)) continue
    const n = counts.get(keyOf(row)) ?? 0
    if (n > most) {
      most = n
      best = row
    }
  }
  return best ?? landingOf(rows)
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

/* The same two facts `shelfOf`/`hasDeparted` read off a Row, read off a SearchCopy instead —
 * for the cross-box search ranking, which no longer has every box's Rows loaded to ask
 * (D192, item 2): the box being browsed fetches only its own cards, so a search that spans
 * boxes has to rank off the search's OWN result rather than off a store-wide `rows` array. */
function copyShelf(copy: SearchCopy): Shelf {
  if (copy.place.located === false) return 'pooled'
  const box = copy.place.box
  return typeof box === 'number' && !Number.isNaN(box) ? box : 'unplaced'
}

function copyDeparted(copy: SearchCopy): boolean {
  return isDeparted(copy.place)
}

/* A SHELF BY ITS NAME (D259): the owner ruled the box number an index the
 * store keeps, never a label. Every box carries a stored name since the backfill, so `Box <n>`
 * is only the fallback for a registry the screen has not read yet, and it is the same string
 * the backfill stores for that box. */
function shelfLabel(shelf: Shelf, name?: string | null): string {
  if (shelf === 'pooled') return 'Pooled'
  if (shelf === 'unplaced') return 'No box'
  if (name !== undefined && name !== null && name.trim() !== '') return name.trim()
  return `Box ${shelf}`
}

/* What a 36px tile can say about a box (D132): the first word of its name, at most four
 * characters — `WB1` — and the number only where there is no name to shorten. */
function miniLabel(name: string | null, box: number): string {
  const word = name?.trim().split(/\s+/)[0] ?? ''
  return word === '' ? String(box) : word.slice(0, 4)
}

/* Every shelf the current walk touches, boxes first, plus every box the registry knows when
 * nothing is being searched for — an empty box is the only state from which it can be renamed,
 * sealed or deleted. */
function shelvesOf(
  rows: Row[],
  registry: readonly number[] = [],
  order: (a: number, b: number) => number = (a, b) => a - b,
): Shelf[] {
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
  boxes.sort(order)
  const out: Shelf[] = [...boxes]
  if (pooled) out.push('pooled')
  if (unplaced) out.push('unplaced')
  return out
}

// -------------------------------------------------------------------- D213's game/set/rarity filter

const NO_CELLS: readonly FacetCell[] = []

const FACET_KEYS = ['game', 'set', 'rarity'] as const
type FacetKey = (typeof FACET_KEYS)[number]

/* THE UNCLASSIFIED BUCKET, AS A PICK: the URL's blank value (`?set=`), the same spelling the
 * wire uses for "no claim". Blank and null both mean no claim, the fold `_card_facets` and
 * `_card_matches_filters` apply on the server, so a card and a cell compare the same way. */
const UNCLASSIFIED = ''

const FACET_WORDS: Readonly<Record<FacetKey, { readonly label: string; readonly none: string }>> = {
  game: { label: 'Game', none: 'No game recorded' },
  set: { label: 'Set', none: 'No set on file' },
  rarity: { label: 'Rarity', none: 'No rarity on file' },
}

function cellValue(cell: FacetCell, key: string): string {
  const raw = key === 'game' ? cell.game : key === 'set' ? cell.set : cell.rarity
  return raw ? raw : UNCLASSIFIED
}

function cardFacetValue(card: InventoryCard, key: FacetKey): string {
  const raw = key === 'game' ? card.game : key === 'set' ? card.set_name : card.rarity
  return raw ? raw : UNCLASSIFIED
}

/* The three facets, each offering every value the store holds: one flat list per facet, never
 * scoped to a game first. Real values alphabetically, the unclassified bucket last. */
function facetsOf(cells: readonly FacetCell[]): FilterFacet[] {
  return FACET_KEYS.map((key) => {
    const values = new Set<string>()
    for (const cell of cells) values.add(cellValue(cell, key))
    const sorted = [...values].sort((a, b) => (a === UNCLASSIFIED ? 1 : b === UNCLASSIFIED ? -1 : a.localeCompare(b)))
    return {
      key,
      label: FACET_WORDS[key].label,
      options: sorted.map((value) => ({
        value,
        label: value === UNCLASSIFIED ? FACET_WORDS[key].none : key === 'game' ? gameLabel(value) : value,
      })),
    }
  })
}

/* Does this card pass every facet with a pick? Several picks in one facet are OR, the facets
 * are AND (`kit/facets.ts`'s rule). */
function passesFacets(card: InventoryCard, value: FilterValue): boolean {
  for (const key of FACET_KEYS) {
    const picked = value[key]
    if (picked !== undefined && picked.length > 0 && !picked.includes(cardFacetValue(card, key))) return false
  }
  return true
}

/* Which stretch of one shelf's walk a row belongs to, worded as its header will say it.
 * Composed from the server's own decorations — no position arithmetic here beyond
 * `sectionCountOf`'s own (`position.ts`), which this shares with `sectionDepthOf`. */
function sectionTitleOf(row: Row): SectionTitleParts {
  if (isPooled(row.card)) {
    return { head: `Pooled: ${row.card.place?.game_display ?? row.card.game ?? 'cards'}`, count: null }
  }
  if (row.card.section === undefined) return { head: 'No position label', count: null }

  /* THE SECTION'S NAME RIDES ITS NUMBER (D132): `Section 6: Rares`. Off the place block, where
     the server joined it at read time, so a rename reaches every header at once. D218: the
     separator is punctuation in a real sentence, never a typed middle dot. */
  const named = row.card.place?.section_name
    ? `Section ${row.card.section}: ${row.card.place.section_name}`
    : `Section ${row.card.section}`

  /* THE HEADER STATES THE SECTION'S OWN COUNT, NEVER THE BOX-WIDE SPAN. `section_start`/
     `section_end` count across the whole BOX (D58's units, but the box's own numbering) —
     drawing them here as `#54–#93` put a box-wide range over a row reading `#37`, the number
     WITHIN THE SECTION (`row.card.card`, `pipeline/join.py:Position.card`). Two rulers on one
     screen, one scale up from the bug D092 already named for the position bar. `sectionCountOf`
     answers in the section's own scale, honestly on a growing section too — no "so far" (owner's
     ruling, 2026-09-19, see `sectionDepthOf`'s comment) — so the fold below has one number
     rather than a range with nothing to check it against. */
  return { head: named, count: sectionCountWords(row.card.place ? sectionCountOf(row.card.place) : null) }
}

type Section = { key: string; title: string; parts: SectionTitleParts; first: Row; rows: Row[] }

function sectionKeyOf(row: Row, title: string): string {
  const box = row.card.box
  const section = row.card.section
  return typeof box === 'number' && typeof section === 'number'
    ? `section @ ${box}/${section}`
    : `section @ ${title}`
}

/* Run-length over the walk, so whatever order the rows arrive in survives exactly. Keyed by
 * the BOX AND SECTION NUMBER rather than by the title or by the first row, so a fold survives
 * the re-read after a sale — which changes the title's card range but not which section this
 * is — and survives the sold rows being folded away or shown again (D132), which changes which
 * row comes first in a section whose first card has left. A section with no number (pooled,
 * unlabelled) keys on its title, which is all it has. */
function sectionsOf(rows: Row[]): Section[] {
  const out: Section[] = []
  for (const row of rows) {
    const open = out[out.length - 1]
    const parts = sectionTitleOf(row)
    const title = sectionTitleText(parts)
    if (open !== undefined && open.title === title) open.rows.push(row)
    else out.push({ key: sectionKeyOf(row, title), title, parts, first: row, rows: [row] })
  }
  /* A DEPARTED ROW STAYS WHERE IT SAT (UX-189, the owner's "nothing jumps"). D132 sank departed
     rows under the live ones in their section while Hide sold was off, so the list drew a sold
     card at the section's foot while the arrow keys still stepped onto it in box order: the
     highlight jumped to the foot and back. One order now, the box's own, for the list and the
     keys alike. The row's own mark says it left. */
  return out
}

/* What a row's left cell says: the slot alone under a section header, read off the server's
 * `card` decoration; the fallbacks for a departed, pooled or unlabelled record. */
function rowSlot(row: Row): string {
  if (row.card.card !== undefined) return `#${row.card.card}`
  if (hasDeparted(row.card)) return departedSlot(row.card)
  const label = positionLabel(row.card)
  if (label !== null) return label
  return isPooled(row.card) ? pooledText(row.card, row.key) : `no label, ${row.key}`
}

/** WHAT A DEPARTED ROW'S SLOT SAYS (the owner's ruling, 2026-09-23,
 *  D259): the server's departed label carries the number of the place
 *  it left, and the row's own mark (`.is-departed`, struck through by the stylesheet) says it
 *  left, never a word or the store key. A label from before the ruling names no card, so the
 *  store key is the fallback.
 *
 *  A FUNCTION OF ITS OWN (S5), SO THE GHOST BELOW CAN ASK IT TOO. It used to reserve the store
 *  key unconditionally, on the premise that a sale rewrites `#1` into that wider spelling —
 *  true before this ruling, false since: a departed row keeps its own number's width
 *  unchanged. Reserving the store key regardless left the ghost wider than the slot ever
 *  draws once a box's card numbers reach two digits, and every name after it sat those pixels
 *  too far right. */
function departedSlot(card: InventoryCard): string {
  const was = placePartsOf(positionLabel(card))?.card ?? null
  return was === null ? departedKey(card) : `#${was}`
}

/** `join.departed_label`'s store key, in the server's spelling (`B3 #96`, D68).
 *
 *  THE SPELLING ITSELF MOVED TO `storeKey.ts` IN D92's SWEEP, beside the regex that reads it back
 *  off a label. It was composed here and, independently, on the capture screen — two ideas of
 *  what a key looks like on screen, one respelling away from disagreeing. The argument for a key
 *  wearing the bare sigil at all is in that module. */
function departedKey(card: InventoryCard): string {
  return storeKeyText(card.box, card.index)
}

function hasDeparted(card: InventoryCard): boolean {
  return isDeparted(card.place)
}

/* `nameOf` moved to `CardHero.tsx` (imported above), for the reason its own header gives. */

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
   *  ignored. `box` (D192, item 2) is the target's box, when known — `rows` is
   *  box-scoped now, so a jump to another box can no longer discover it by scanning `rows`
   *  for the key the way it used to when `rows` held the whole store. Null for a pooled
   *  card, which has no box to switch to. */
  goTo?: { key: string; at: number; box: number | null } | null

  /** What a run would be scoped to: the box being walked, and the ticked cards inside it. */
  onScope?: (scope: { box: number | null; indices: readonly number[] }) => void

  /** FOLD DEPARTED ROWS AWAY (D132). The state is the route's, because the same answer reaches
   *  the copies list beside this walk; this component draws the control and applies it. Hidden,
   *  a sold or retired row is not in the walk — except the row the walk is standing on, which
   *  keeps its receipt (D119). Shown, departed rows sink under the live ones in each section. */
  hideSold?: boolean
  onHideSold?: () => void

  /** THE COPIES THAT LEFT SINCE THIS ORDER WAS TAKEN (`frozenRank.ts`). The rail's rank, the
   *  landing and the fold all read it, so a sale moves no box tile and drops no walk row. The
   *  state is the route's, exactly as `hideSold` is, because one press makes this walk AND the
   *  copies list beside it stale. */
  frozen?: FrozenRank

  /** A NEW ANSWER IS A NEW ORDER. Called when the searchbox's text changes, so the route can
   *  let the old order go: nothing has been worked down under a query that was just typed, and
   *  a `2 copies stale` chip over a fresh answer would be counting the previous search's cards. */
  onQuery?: (query: string) => void
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
  /* THE PART OF THE SCROLLER A PERSON CAN SEE, not the whole of it (UX-227). The rail is sticky
     and taller than the window below the page head until the page scrolls, so its list runs
     past the bottom of the window. A row brought to the list's own foot was still out of view. */
  const edge = Math.max(box.top + scroller.clientTop, 0)
  const foot = Math.min(box.top + scroller.clientTop + scroller.clientHeight, window.innerHeight)

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
  return `${card.place?.game_display ?? card.game ?? 'pooled'}, pooled, ${key}`
}

/* `nameOf`, `numberCell`, `titleCase`, `claimList`, `gameLabel`, `gameWord`, `MarketRead`,
 * `marketTable` and `factGroupsOf`/`CardDetailsSection` moved to `CardHero.tsx` so `#/orders`'
 * walk pane can share them (`docs/specs/order-walk-plan.md` §13) — imported below, this file's
 * own JSX unchanged. */

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

/** The card named on the hash, by its stable name (D172): `#/inventory?box=3&card=<cid>`, the
 *  way Review's place pill links here (LOC-12: a place link opens that card, not the box's
 *  first). Null when the hash names none. */
function cardParam(): string | null {
  const hash = window.location.hash
  const at = hash.indexOf('?')
  if (at === -1) return null
  const value = new URLSearchParams(hash.slice(at + 1)).get('card')
  return value === null || value.trim() === '' ? null : value.trim()
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

/** THE MISSING NAME -> VARIANT LEVEL: one row per SKU a name search answers with, when there
 *  is more than one. Before this, a name matching five printings dumped every copy of all
 *  five into one undifferentiated walk, and the only way to a sibling was clicking rows until
 *  one happened to belong to a different SKU (`app/src/Inventory.tsx`'s `CopiesPanel` then
 *  asks for that ROW's own SKU, so the walk anchors there and the other four stop being
 *  fetched at all). This is what stands between the search and that walk instead.
 *
 *  A LIST, NOT A GRID — legible whatever the count, and the count runs high: measured on the
 *  owner's own store, one name reaches 15 rows (three sets by five conditions). A grid needs
 *  a second axis to wrap a name into and a phone at 390px has none to spare; a list only ever
 *  grows taller, and the panel around it already scrolls.
 *
 *  `sku` KEYS THE ROW WHEN THERE IS ONE; THE UNIDENTIFIED BAG (`sku: null`) TAKES ITS OWN
 *  INDEX-KEYED ROW AND IS NEVER LEFT OUT — a card the pipeline could not name is exactly the
 *  card an operator searches for, and the hard rule against dropping one silently reaches
 *  this list too. */
function VariantChooser({
  groups,
  onPick,
}: {
  groups: readonly SearchGroup[]
  onPick: (index: number) => void
}) {
  /* RARITY DRAWN ONLY WHERE THE PRINTINGS ON SCREEN ACTUALLY DIFFER IN IT. The Runes all
     read `Showcase`, and a word every tile repeats is not what tells two tiles apart — it
     is `number_display`/set/condition doing that work, exactly as they already do below.
     Two real SKUs can still be separated by rarity alone (a promo stamp on an otherwise
     identical row), and this is what puts the word back the moment that happens. */
  const rarities = new Set(groups.map((group) => group.rarity).filter((r): r is string => !!r))
  const showRarity = rarities.size > 1

  return (
    <div className="browse-variants">
      <p className="browse-variants-lede">{groups.length} printings match.</p>
      <ul className="browse-variants-list" role="list">
        {groups.map((group, index) => {
          const photoCopy = group.copies.find((copy) => copy.has_photo)
          const name = group.names[0] ?? 'Not identified yet'
          // THE CATALOGUE'S OWN SET FIRST, `set_hint` ONLY WHEN THERE IS NO OTHER ANSWER
          // (D213) — the fallback D65
          // already established for the case no export has ever priced this game.
          const subParts = [
            group.number_display,
            group.set ?? group.set_hint,
            group.condition,
            showRarity ? group.rarity : null,
          ].filter((part): part is string => typeof part === 'string' && part !== '')
          return (
            <li key={group.sku ?? `unidentified-${index}`}>
              <button type="button" className="browse-variant-tile" onClick={() => onPick(index)}>
                <span className="browse-variant-photo" aria-hidden="true">
                  {photoCopy === undefined ? (
                    <Icon name="image" size={18} />
                  ) : (
                    <img src={photoUrl(photoCopy.place.box, photoCopy.place.index, photoCopy.cid)} alt="" />
                  )}
                </span>
                <span className="browse-variant-text">
                  <span className={name === 'Not identified yet' ? 'browse-variant-name is-unnamed' : 'browse-variant-name'}>
                    {name}
                  </span>
                  {subParts.length === 0 ? null : (
                    <span className="browse-variant-sub bn-facts">
                      {subParts.map((part, partIndex) => (
                        <span key={partIndex}>
                          {part}
                          {partIndex < subParts.length - 1 ? ' ' : ''}
                        </span>
                      ))}
                    </span>
                  )}
                </span>
                <span className="browse-variant-count">
                  {group.on_hand.toLocaleString()} {group.on_hand === 1 ? 'copy' : 'copies'}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export function BoxBrowse({
  detail,
  boxPanel,
  actionBar,
  onSelect,
  onBoxes,
  onListings,
  onScope,
  goTo,
  reloadToken = 0,
  hideSold = false,
  onHideSold,
  frozen = RANK_IS_CURRENT,
  onQuery,
}: BoxBrowseProps) {
  const [rows, setRows] = useState<Row[] | null>(null)
  /** Which shelf `rows` currently answers for (D192, item 2).
   *
   *  STATE RATHER THAN A REF SINCE 2026-09-19, and the reason is the whole of this file's
   *  half of the copies-panel blanking defect. It was a ref because only the cross-box jump
   *  effect read it, and an effect reads a ref at the right moment by construction. The
   *  RENDER needs the same fact now — `selectedRow` below must tell "the walk has no row"
   *  from "the box the walk just moved to has not answered yet", and only this says which.
   *  It is written in the same batch as `setRows`, so the two can never disagree in a
   *  committed render. */
  const [rowsShelf, setRowsShelf] = useState<number | null>(null)
  /** The rows on hand when this box was opened (FLT-22, "nothing jumps"). Taken once per box
   *  load: a write re-reads the same box and keeps it, and a new box, a reload or a new visit
   *  takes it again. A row that leaves while the box is open stays drawn until then. */
  const [enteredLive, setEnteredLive] = useState<{ readonly shelf: number; readonly keys: ReadonlySet<string> } | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [selected, setSelected] = useState<string | null>(null)

  /* Which shelf the walk is of, or null before the first read has said which shelves exist. */
  const [shelf, setShelf] = useState<Shelf | null>(null)

  /* The mass-select, by store key. Not persisted; cleared when the box changes. */
  const [picked, setPicked] = useState<readonly string[]>([])

  /* Which sections are open, by section key. Per-box for free: a section key names a box. */
  const [opened, setOpened] = useState<readonly string[]>([])

  const [boxRecords, setBoxRecords] = useState<readonly BoxRecord[]>([])
  /** THE STORE'S TOTAL CARD COUNT (D192, item 2) — off `GET /boxes`'s own per-box
   *  `cards` figure, summed, rather than off `rows.length`. `rows` is box-scoped now: before
   *  this item it held every card in the store and `rows.length` WAS the store's total by
   *  construction, which is what both the header's "N cards" census and the "no cards
   *  captured yet" empty state below were built against. Landing on an empty box (a
   *  never-captured one, or one a search or the recency rule picked with nothing in it) made
   *  `rows.length === 0` true for a store that plainly has cards elsewhere — the whole-store
   *  empty state and a "0 cards" census on a four-box store, both real regressions caught
   *  by this item's own browser suite rather than by any server-side guard. `GET /boxes`
   *  (`do_boxes`) is unaffected by this item — it stays on the `unscoped walk` allowlist as
   *  cheap, one indexed column — so this is free. */
  const storeCards = useMemo(
    () => boxRecords.reduce((sum, record) => sum + record.cards, 0),
    [boxRecords],
  )
  /* Whether the registry read above has come back, either way. `boxRecords` cannot answer this
     itself — `[]` is both "not yet" and "no boxes" — and the shelf effect needs to tell those
     apart to know whether a box the hash asked for is genuinely absent or merely not here yet. */
  const [boxesAnswered, setBoxesAnswered] = useState(false)
  /* WHEN THIS BROWSER LAST OPENED EACH BOX (D132) — the rail's first sort key. READ ONCE, ON
     ARRIVAL, AND NEVER RE-READ HERE (UX-215, the owner's "nothing jumps"). A press writes the
     device's map (`touchBox`), and the rail takes the new order on the next visit. Re-sorting on
     the press moved the pressed box to the top, and the row under the pointer became another
     box. */
  const [recency] = useState<ReadonlyMap<number, string>>(() => storedBoxRecency())
  /* THE RAIL'S OWN SORT (the ruling of 2026-09-24: the value list is D159's own screen no
   * longer — it is an Inventory sort, through the same `SortControl` every other sorted list
   * in the kit uses). `recent` is the resting order above and needs no fetch; `value` reads
   * `GET /pipeline/value`'s aggregates, fetched lazily the first time it is picked and kept —
   * a box's own dollar total does not move under a sale the way `on_hand` does, so nothing
   * here re-fetches on a write the way `boxRecords` does. */
  const [sort, setSort] = useState<SortValue<'recent' | 'value'>>({ key: 'recent', dir: 'desc' })
  const [valueByBox, setValueByBox] = useState<ReadonlyMap<number, number> | null>(null)
  useEffect(() => {
    if (sort.key !== 'value' || valueByBox !== null) return
    let live = true
    getValueAggregates()
      .then((aggregates) => {
        if (live) setValueByBox(new Map(aggregates.boxes.map((box) => [box.box, Number(box.total)])))
      })
      .catch(() => {
        // Deliberately nothing — the rail falls back to box order below (D18's own reason:
        // a sort with no data to sort by is not a failure the operator asked to hear about).
      })
    return () => {
      live = false
    }
  }, [sort.key, valueByBox])
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
  /* The same node as state, so the rail's height effect runs when the rail mounts (it is not
     drawn on the first render). */
  const [mapEl, setMapEl] = useState<HTMLDivElement | null>(null)
  const holdMap = useCallback((node: HTMLDivElement | null) => {
    mapRef.current = node
    setMapEl(node)
  }, [])
  const boxesRef = useRef<HTMLDivElement | null>(null)
  /** N3: set by `selectShelf` alone, right before `setShelf`, so the rail's own scroll-into-view
   *  effect below skips exactly one run — the one a direct press on a row already caused to be
   *  on screen. Every other `setShelf` caller (a walk-to, a deep link) leaves it unset, because
   *  those targets may genuinely be off screen and still need bringing into view. */
  const skipRailScroll = useRef(false)
  const jumpRef = useRef<string | null>(null)
  const [jump, setJump] = useState<string | null>(null)
  const askedAt = useRef<number | null>(null)
  /* The box the hash asked for, honoured once on the first read. */
  const wanted = useRef<number | null>(boxParam())

  /* Layout state: the phone's rail sheet, the desktop rail's collapse, the box sheet, the
     photo lightbox, the details disclosure. */
  const phone = useMediaQuery('(max-width: 639px)')
  const [railOpen, setRailOpen] = useState(false)
  const [railCollapsed, setRailCollapsed] = useState(false)
  const [manage, setManage] = useState(false)
  const [zoomed, setZoomed] = useState(false)

  /* The search is the server's matcher filtering this screen's own list: the answer is read
   * for its copy KEYS and nothing else. No autoFocus: this screen is opened to WALK. */
  const { query, setQuery, results, loading, failure: searchFailure } = useSearch()
  const searching = query.trim() !== ''

  /* D213's game/set/rarity filter, independent of the search above and ANDed with it.
   * THE FACETS WORK IN ANY ORDER (FLT-09, the owner: "I hate how on the inventory screen I
   * have to filter by game first, then set, then rarity and only IN THAT ORDER"). Each facet
   * takes several picks at once, none waits on another, and none clears another. The
   * vocabulary and every count come off `GET /boxes`'s `facet_cells`, folded here with the
   * kit's `countFacets`, so a pick asks the server nothing. The picks live in the URL
   * (D285): a reload, a link and Back restore them. */
  const [facetCells, setCells] = useState<readonly FacetCell[]>(NO_CELLS)
  const facetDefs = useMemo(() => facetsOf(facetCells), [facetCells])
  const [facetValue, setFacetValue] = useFacetParams(facetDefs)
  const facetActive = Object.keys(facetValue).length > 0

  /* A NEW ANSWER IS A NEW ORDER (`frozenRank.ts`). Told on the TEXT and not on the answer: the
     answer for `Thiev` and the answer for `Thievul` are two orders too, and waiting for the
     response would leave the previous search's staleness chip on screen through the debounce.
     A ref, so this fires on a CHANGE and never on a re-render that merely re-ran the effect. */
  const askedFor = useRef(query)
  useEffect(() => {
    if (askedFor.current === query) return
    askedFor.current = query
    onQuery?.(query)
  }, [query, onQuery])

  /* WHICH PRINTING THE OPERATOR PICKED, when a search answers with more than one SKU group
   * sharing a name (the missing name -> variant level: five printings of one name are five
   * SKUs, and nothing before this told them apart). Tied to the QUERY TEXT it was picked for,
   * rather than cleared by an effect: a changed query is a new question and invalidates the
   * old pick just by no longer matching it, which is the same idiom `frozenRank.ts`'s callers
   * already use for "this answer is for a different question now". */
  const [chosenVariant, setChosenVariant] = useState<{ query: string; index: number } | null>(null)

  const searchGroups = results?.groups ?? null
  /* MORE THAN ONE SKU FOR ONE ANSWER — the shape a name search returns when it is not really
     naming one card. `null`-SKU cards (not yet identified) count as a group like any other:
     CLAUDE.md's own hard rule is never to drop a card silently, and a card the pipeline
     could not name is exactly the card an operator searches for. */
  const multiGroup = searchGroups !== null && groupsAreSamePrinting(searchGroups)
  const resolvedVariant =
    chosenVariant !== null &&
    chosenVariant.query === query &&
    searchGroups !== null &&
    chosenVariant.index < searchGroups.length
      ? chosenVariant.index
      : null
  /* THE CHOOSER IS SHOWING, AND NOTHING BELOW MAY ACT AS IF A PRINTING WERE PICKED. */
  const chooserActive = multiGroup && resolvedVariant === null

  /* THE GROUPS EVERY BOX-WALK COMPUTATION BELOW READS, IN PLACE OF `results.groups` DIRECTLY.
   * Empty while the chooser is showing — which is what makes clicking a box a no-op then: the
   * box list's own `cells` marks every shelf unreachable when `shelves` is empty, so this one
   * substitution is what keeps the walk from being enterable until a printing is picked, with
   * no second flag to keep in step. One group — the picked one, or the sole one a query
   * already resolves to — once it is. */
  const activeGroups = useMemo(() => {
    if (searchGroups === null || chooserActive) return EMPTY_GROUPS
    if (resolvedVariant === null) return searchGroups
    const picked = searchGroups[resolvedVariant]
    return picked === undefined ? searchGroups : [picked]
  }, [searchGroups, chooserActive, resolvedVariant])

  /* THE WALK LEAVES THE BOX IT WAS ON WHILE THE CHOOSER IS SHOWING. The shelf-picking effect
   * below returns early the moment `shelves` is empty (its own guard, written for the
   * registry's late arrival — see its own comment) — which under a plain empty search is
   * exactly right, and under an UNRESOLVED chooser would otherwise leave the walk parked on
   * whatever box it was on before the operator typed, with every one of its cells now
   * disabled under it. One box press cannot reach it either: `cells` marks every shelf
   * unreachable while `shelves` is empty, so nothing downstream can act as if a printing were
   * picked — this is the one line that also has to say so out loud. */
  useEffect(() => {
    if (chooserActive) {
      /* NOT A RE-RANK: `shelf` is going to `null`, never to another box, so `awaitingRows`
       * can never read true off this move — but every `setShelf` call marks `shelfSource`
       * on the same convention, so a later reader never has to know which sites happen to
       * be safe today for a reason of their own. */
      shelfSource.current = 'manual'
      setShelf(null)
    }
  }, [chooserActive])

  const matched = useMemo(() => {
    if (results === null) return null
    const keys = new Set<string>()
    for (const group of activeGroups) for (const copy of group.copies) keys.add(copy.key)
    return keys
  }, [results, activeGroups])

  /* Filtered only when there is an answer to filter by. D213's facet filter is a SEPARATE
   * and-ed narrowing, applied after the search's own — clearing one leaves the other
   * standing, and neither reads the other's state. */
  const inQuery = useMemo(() => {
    if (rows === null) return NO_ROWS
    let base = rows
    if (searching && matched !== null) base = base.filter((row) => matched.has(row.key))
    if (facetActive) base = base.filter((row) => passesFacets(row.card, facetValue))
    return base
  }, [rows, searching, matched, facetActive, facetValue])

  const filtered = searching && matched !== null

  /* THE RAIL'S ORDER IS THE HAND'S (D132): the box opened most recently on this browser first,
     then its own true index (`bid`, newest box first), then the number — `kit/dataRules.ts:
     boxesMostRecentFirst`, the one primitive for a box order every list of boxes now shares.
     B3: `on_hand` USED TO BREAK THE RECENCY TIE, AND A SALE MOVES `on_hand`. Two boxes neither
     side of this browser has ever opened tie on recency (both unstored) and used to fall to
     whichever held more copies — so a sale that took RB Epics from 26 to 25 dropped it under
     MEG Bulk IN THE SAME SESSION, with no press on the rail at all. `bid` and the box number
     are both facts about the DRAWER, not the count inside it, so nothing a sale touches can
     move this tie-break again. */
  const order = useMemo(() => {
    /* VALUE IS ITS OWN, SIMPLER ORDER — the operator asked to see the money, not the money
       folded into the recency rule's own tie-breaks. A box the aggregates never mention (none
       of its cards have a market reading) sorts last regardless of direction, never as if it
       were worth $0. */
    if (sort.key === 'value') {
      const dirMul = sort.dir === 'asc' ? 1 : -1
      return (a: number, b: number): number => {
        const va = valueByBox?.get(a)
        const vb = valueByBox?.get(b)
        if (va === undefined && vb === undefined) return a - b
        if (va === undefined) return 1
        if (vb === undefined) return -1
        if (va !== vb) return (va - vb) * dirMul
        return a - b
      }
    }
    const rankOf = new Map(boxesMostRecentFirst(boxRecords, recency).map((record, i) => [record.box, i]))
    /* UNDER A SEARCH THE BOX WHOSE FULLEST SECTION HOLDS THE MOST LIVE COPIES OF THE ANSWER
       LEADS (D132, amended on the owner's rule of 2026-09-11): "the largest quantity of
       whatever I searched, BY SECTION, is the order". A box is ranked by its best section and
       not by its total, so the rail agrees with the copies list and with where the walk lands:
       three in one section outranks one-plus-two across two. Sold copies count for nothing —
       a box full of departed matches is not where the hand goes. With no query this term is
       zero everywhere and the rail is the hand's again. */
    /* D192, item 2: this box's own `rows` no longer stands for every box's cards, so the
       cross-box tally reads the search's OWN result (`results`) instead — `SearchCopy`
       carries `place.box`/`place.section`, everything this needed off a `Row`. */
    const liveMatches = new Map<number, number>()
    if (filtered && results !== null) {
      const perSection = new Map<string, number>()
      for (const group of activeGroups) {
        for (const copy of group.copies) {
          const shelf = copyShelf(copy)
          /* A COPY THAT LEFT SINCE THIS ORDER WAS TAKEN STILL COUNTS (`frozenRank.ts`), so a
             sale does not re-rank the rail under the hand that made it. */
          if (typeof shelf !== 'number' || !ranksAsLive(copy.key, copyDeparted(copy), frozen)) continue
          const key = `${shelf}/${copy.place.section ?? '?'}`
          const n = (perSection.get(key) ?? 0) + 1
          perSection.set(key, n)
          liveMatches.set(shelf, Math.max(liveMatches.get(shelf) ?? 0, n))
        }
      }
    }
    return (a: number, b: number): number => {
      const ma = liveMatches.get(a) ?? 0
      const mb = liveMatches.get(b) ?? 0
      if (ma !== mb) return mb - ma
      const rra = rankOf.get(a) ?? Number.MAX_SAFE_INTEGER
      const rrb = rankOf.get(b) ?? Number.MAX_SAFE_INTEGER
      if (rra !== rrb) return rra - rrb
      return a - b
    }
  }, [sort, valueByBox, boxRecords, recency, filtered, results, activeGroups, frozen])

  /* D192, item 2: under a search, which OTHER boxes hold a match comes off the search's own
     result now — `inQuery` is only this box's matched rows since the fetch became box-scoped,
     so it can no longer answer "which boxes does this search touch" on its own. */
  /* S3: the same Hide-sold rule `matchesByShelf` now keeps — a box a search touches only
     through a departed copy is not a box the fold offers to reach for, so it is not one of
     the "N of M boxes" the count line below states. */
  const searchBoxes = useMemo(() => {
    if (results === null) return []
    const boxes = new Set<number>()
    for (const group of activeGroups) {
      for (const copy of group.copies) {
        if (hideSold && copyDeparted(copy)) continue
        const shelf = copyShelf(copy)
        if (typeof shelf === 'number') boxes.add(shelf)
      }
    }
    return [...boxes]
  }, [results, activeGroups, hideSold])

  /* WHAT HIDE SOLD KEEPS, for every count the filter draws: with it on, a count is of the cards
   * the walk would draw (UX-210's rule: the counts follow the other filters, Hide sold too). */
  const keepCell = useCallback((cell: FacetCell) => !hideSold || !cell.gone, [hideSold])

  /* Every option's count under the OTHER picks and Hide sold (the kit's one rule). */
  const countedFacets = useMemo(
    () => countFacets(facetCells, facetDefs, facetValue, cellValue, keepCell, (cell) => cell.count),
    [facetCells, facetDefs, facetValue, keepCell],
  )

  /* D213: how many cards of each box the facet picks let through, off the same cells. A box
   * with none is not reachable, exactly as a box a search does not touch is not. */
  const facetMatchesByBox = useMemo(() => {
    const out = new Map<number, number>()
    if (!facetActive) return out
    for (const cell of filterRows(facetCells, facetDefs, facetValue, cellValue, keepCell)) {
      if (cell.box !== null) out.set(cell.box, (out.get(cell.box) ?? 0) + cell.count)
    }
    return out
  }, [facetActive, facetCells, facetDefs, facetValue, keepCell])

  /* The boxes the rail may open: under a search the boxes it touches, under a facet pick the
   * boxes holding a match, and under both the boxes that satisfy both. */
  const reachableBoxes = useMemo(() => {
    const all = boxRecords.map((record) => record.box)
    const bySearch = filtered ? new Set(searchBoxes) : null
    return all
      .concat(filtered ? searchBoxes.filter((box) => !all.includes(box)) : [])
      .filter((box) => (bySearch === null || bySearch.has(box)) && (!facetActive || (facetMatchesByBox.get(box) ?? 0) > 0))
  }, [boxRecords, filtered, searchBoxes, facetActive, facetMatchesByBox])

  const shelves = useMemo(() => shelvesOf(inQuery, reachableBoxes, order), [inQuery, reachableBoxes, order])

  /* The filter bar's count line counts BOXES, the list it sits over: `3 of 13 boxes, filtered by
   * Pokémon`. */
  const reachableCount = reachableBoxes.length

  const onShelf = useMemo(() => {
    if (shelf === null) return NO_ROWS
    return inQuery.filter((row) => shelfOf(row) === shelf)
  }, [inQuery, shelf])

  /* THE WALK, WITH SOLD FOLDED AWAY (D132), AT A MOMENT WHEN NO ROW IS UNDER THE HAND.
     NOTHING JUMPS (FLT-22, the owner's ruling of 2026-09-23,
     D263): a row that was on hand when this box was opened stays drawn, in its place and
     marked sold, until the next box load. D132 folded it "the moment the walk steps off it", and
     that moment is a press: the owner sold #1, pressed #2, and every row under #2 came up 32px
     at that click, so #2 slid from under the pointer. D118 wins over D132's timing. The fold
     still happens, on the next box load or reload, when no row is under the pointer.
     Three rows are kept besides:
     - the row the walk stands on, whatever its state (D119's receipt, D45's walk-to onto a sold
       copy),
     - under a search, a row that left since this order was taken (`frozenRank.ts`, D181), which
       the same rule now covers for this box but a search may have walked from another box,
     - a row that left while this box was open (`enteredLive`). */
  const visible = useMemo(() => {
    if (!hideSold) return onShelf
    return onShelf.filter(
      (row) =>
        !hasDeparted(row.card) ||
        row.key === selected ||
        enteredLive?.keys.has(row.key) === true ||
        (filtered && ranksAsShown(row.key, true, frozen)),
    )
  }, [onShelf, hideSold, selected, filtered, frozen, enteredLive])

  /* THE PILL COUNTS WHAT THE FOLD ACTUALLY HIDES, NEVER EVERY DEPARTED ROW ON THE SHELF.
     `visible`'s own exceptions above keep some departed rows drawn — the row the walk stands
     on (D119), and under a search a row `ranksAsShown` in the frozen rank (D118/D181) — so a
     count of every departed row overstates what pressing the chip removed. A LIVE ROW IS NEVER
     REMOVED BY THIS FILTER, so the shrink from `onShelf` to `visible` is exactly the departed
     rows the fold took out, in both states of the toggle: zero while it is off, since nothing
     is filtered yet. Measured on the owner's screenshot: `departedHere` (the old count) read 6,
     one just-sold row stayed drawn under the selection exception, and only 5 left the shelf. */
  const hiddenBySold = useMemo(() => onShelf.length - visible.length, [onShelf, visible])

  const sections = useMemo(() => sectionsOf(visible), [visible])

  /* How many matches each shelf holds under a query, for the box list. Off `results` rather
     than `inQuery` for the same reason `order`/`shelves` are, above (D192, item 2).
     S3: WITH Hide sold ON, A DEPARTED COPY DOES NOT COUNT — `keepCell`'s own rule, below,
     asked of a search match rather than a facet cell. `visible` already folds a departed copy
     off the shelf it sold from; a rail cell counting it too, and a "2 of 4 boxes" line built on
     the same count, disagreed with the very pane saying "Nothing matches". Off when the toggle
     is off, matching the fold's own two states. */
  const matchesByShelf = useMemo(() => {
    const out = new Map<Shelf, number>()
    if (!filtered || results === null) return out
    for (const group of activeGroups) {
      for (const copy of group.copies) {
        if (hideSold && copyDeparted(copy)) continue
        const s = copyShelf(copy)
        out.set(s, (out.get(s) ?? 0) + 1)
      }
    }
    return out
  }, [filtered, results, activeGroups, hideSold])

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

  /* D192, item 2: this box's cards, box-scoped from the server rather than filtered
   * client-side out of a whole-store fetch. Re-runs on a shelf switch (a data fetch now,
   * not a filter) and on every reload trigger — `reloads`/`reloadToken` bumped by a sale,
   * a retire, a re-shoot or a box op re-fetch exactly this box, which is the right box
   * every one of those writes just changed. Waits for the first shelf to resolve (below)
   * so it never fetches box 0 / NaN on first paint. */
  useEffect(() => {
    if (typeof shelf !== 'number') return
    let live = true
    getInventoryBox(shelf)
      .then((inventory) => {
        if (!live) return
        const next = rowsOf(inventory.cards)
        setRows(next)
        setEnteredLive((held) =>
          held !== null && held.shelf === shelf
            ? held
            : { shelf, keys: new Set(next.filter((row) => !hasDeparted(row.card)).map((row) => row.key)) },
        )
        /* WHICH SHELF `rows` NOW ANSWERS FOR, so the cross-box jump effect below can tell
         * "this box's own rows just landed and truly lack the target" from "the fetch for a
         * NEW shelf has not landed yet, so `rows` is still the OLD box's stale data" —
         * without this, a jump that just switched shelves reads the stale `rows` on the very
         * next render (`shelf` alone changing re-runs that effect too) and gives up before
         * the new box's cards ever arrive. */
        setRowsShelf(shelf)
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
  }, [shelf, reloads, reloadToken, onListings])

  /* B2: A ROW THE WALK STANDS ON IS "DRAWN DURING THIS BOX LOAD" EVEN WHEN IT ARRIVED SOLD.
   *
   * `enteredLive`'s own snapshot above only catches what was LIVE at the fetch — a row that
   * was already sold when this box was opened never entered it, so `visible`'s fallback for it
   * was `row.key === selected` alone. That holds only while the walk stands on it: land on a
   * sold card by its `&card=<cid>` link with Hide sold on, step onto a live row next, and the
   * sold row has nothing left to stand on — it folds, and every row below it moves.
   *
   * Selecting a row THIS SHELF's own snapshot already covers adds it to the standing set
   * instead of replacing it, so it goes on being drawn for the rest of the load. `held.shelf
   * !== shelf` is the same "until the next load" guard the snapshot above uses: a shelf
   * switch's own fetch overwrites `enteredLive` wholesale, and this effect is not the one that
   * decides what a NEW box starts with. */
  useEffect(() => {
    if (selected === null) return
    setEnteredLive((held) => {
      if (held === null || held.shelf !== shelf || held.keys.has(selected)) return held
      return { shelf: held.shelf, keys: new Set(held.keys).add(selected) }
    })
  }, [selected, shelf])

  /* The box registry, on the same counter and allowed to fail without anybody hearing. The
   * facet cells ride on the same answer, so a filter pick needs no second read (FLT-09). */
  useEffect(() => {
    let live = true
    getBoxes()
      .then((summary) => {
        if (!live) return
        const records = Array.isArray(summary.boxes) ? summary.boxes : []
        setBoxRecords(records)
        onBoxes?.(records)
        setCells(Array.isArray(summary.facet_cells) ? summary.facet_cells : NO_CELLS)
      })
      .catch(() => {
        // Deliberately nothing: the walk is whole without this.
      })
      .finally(() => {
        /* ANSWERED, NOT SUCCEEDED, AND `finally` FOR EXACTLY THAT REASON. The shelf effect
           below holds the hash's box until this flips, so a `catch` that left it false would
           hold a stale request open for the life of the screen — and this call is allowed to
           fail silently, so that is a real path and not a hypothetical. */
        if (live) setBoxesAnswered(true)
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
     box 1 with the hash still reading `?box=3`.

     HELD UNTIL THE REGISTRY HAS ANSWERED, AND THAT IS THE WHOLE FIX (2026-09-05). `shelves` is
     built from the ROWS first and the registry second, and the two arrive on separate reads. A
     box with no LOCATED rows — every box of code cards, because D24 pools them — is therefore
     absent from the first `shelves` this effect sees. The ref was consumed and cleared there,
     `shelves.includes(askedFor)` was false, and the walk landed on box 1; when the registry
     landed a tick later and the box joined the list, there was nothing left to honour.

     The effect of that was to break the one link that uses this deep form on a box of codes:
     `#/codes`'s "Fix on Inventory" aims at the box holding the unclaimed codes, which by
     construction has no located rows, so it always arrived at box 1 — whose claim editor draws
     no Product row at all, because box 1 is Pokemon. Measured against `?box=3`, a box with real
     rows, which worked and hid it.

     So the ref is cleared only when it has been HONOURED or when the registry has ANSWERED and
     cannot honour it. That bounds the window: while it is open a live request outranks `prev`,
     which is what lets the late-arriving box win the shelf it was asked for; once closed the
     rule is the old one and a stale hash can never yank a walk somebody has moved. */
  const shelfAnswered = useRef<string | null>(null)
  /* WHY THE SHELF LAST CHANGED, so the row-hold below (D118's fourth floor) can tell a
   * fresh SEARCH ANSWER re-ranking the walk apart from a PRESS choosing a different
   * drawer on purpose (2026-09-19, the review that caught PR #404's regression).
   *
   * Both produce the exact same shape — `shelf` changes, `rows` still answers for the
   * box before it — but only one of them may hold the old row on screen. A press to
   * another drawer, or a walk-to a specific copy elsewhere, is the operator asking for a
   * DIFFERENT card; holding `selectedRow` there drew box 2's Thievul under a `Box 7`
   * header with `CardOps` live against it, while the walk list said "Nothing in box 7
   * yet" — an operator could act on the wrong box's card. Defaults to `'manual'`, so an
   * unmarked transition (a filter change, a reload) never holds either. */
  const shelfSource = useRef<'search' | 'manual'>('manual')
  useEffect(() => {
    if (shelves.length === 0) return
    const askedFor = wanted.current
    const honorable = askedFor !== null && shelves.includes(askedFor)
    if (honorable || boxesAnswered) wanted.current = null
    /* A SEARCH LANDS ON A LIVE COPY, NEVER ON A SOLD ONE (D132, the owner's report of
       2026-09-11: "it pulled up a sold listing as the front runner"). Under a query a shelf
       counts as holding the answer only if one of its matches is still on hand — a box whose
       only match has departed is a box the hand does not go to. The box the walk was on keeps
       the walk only by that test, and the first box in rail order with a live match takes it
       otherwise. With nothing live anywhere the old rule stands, so a sold-out card still
       shows where its copies were.

       D192 (store-scaling item 2): off `results` rather than `inQuery`, for the
       same reason `order`'s own tally above is — `inQuery` is this box's own matched rows
       now, and a candidate shelf other than the one on screen would never appear in it, which
       silently made every OTHER box read as holding no live match at all. */
    const holdsLive = (candidate: Shelf) =>
      !filtered ||
      results === null ||
      activeGroups.some((group) =>
        group.copies.some(
          (copy) => copyShelf(copy) === candidate && ranksAsLive(copy.key, copyDeparted(copy), frozen),
        ),
      )
    const live = shelves.filter(holdsLive)
    const pool = live.length > 0 ? live : shelves
    /* A FRESH ANSWER GOES TO THE FULLEST BOX (D132 amended, the owner's rule): `shelves` is in
       rail order, and under a query the rail leads with the box holding the most live copies
       of the answer — so on the first render of each new answer the walk takes `pool[0]`
       rather than staying where it was. A rail press afterwards still moves it anywhere. */
    const query = filtered ? (results?.query ?? null) : null
    const fresh = query !== null && query !== shelfAnswered.current
    shelfAnswered.current = query
    setShelf((prev) => {
      /* THE HASH'S BOX IS A DIRECTED NAVIGATION, NOT A RE-RANK — same reasoning as a press:
       * the operator (or a deep link) named a specific drawer, so a stale row from the one
       * before it must not linger under the new header. Set before the early returns so
       * every branch this effect can take leaves a correct answer, never a stale one from
       * whichever branch ran last time. */
      shelfSource.current = 'manual'
      if (honorable) return askedFor
      if (!fresh && prev !== null && pool.includes(prev)) return prev
      /* THE ONE BRANCH THAT IS A SEARCH RE-RANK: a fresh answer moves the walk to the
       * fullest box on its own, with no press behind it (D132). This is the case D118's
       * row-hold below exists for. */
      shelfSource.current = 'search'
      return pool[0] ?? null
    })
  }, [shelves, boxesAnswered, filtered, results, activeGroups, frozen])

  /* The selection follows the filter. When nothing matches it is left alone.
     A NEW ANSWER LANDS IN THE FULLEST SECTION (D132 amended): the query's answer is drawn by
     where the most live copies are, so the walk goes to the first live row of the section
     holding the most of them — the same row the copies list puts at its top — and it does so
     on every fresh answer, not only when the old selection fell out of the filter. */
  const answered = useRef<string | null>(null)
  useEffect(() => {
    /* THE EMPTY TICK IS RETURNED ON, AND THE QUERY IS NOT RECORDED WHILE IT IS. `visible` is
       empty while the box a fresh answer moved the walk to has not answered yet, and D132's
       rule is that a fresh answer lands in the fullest section — which cannot happen until the
       rows it would land in exist. Recording the query on that empty tick would spend `fresh`
       on a render that landed nothing, and the answer would never land at all. (A 2026-09-19
       fix moved these three lines above this guard; it was reverted the same day. It could not
       reach the blanking it was aimed at — the copies column was being torn down by a `key`
       further down this file, not re-pointed — and it put D132's landing at risk.) */
    if (visible.length === 0) return
    const query = filtered ? (results?.query ?? null) : null
    const fresh = query !== null && query !== answered.current
    answered.current = query
    setSelected((prev) => {
      if (!fresh && prev !== null && visible.some((row) => row.key === prev)) return prev
      return (filtered ? landingInFullest(visible) : landingOf(visible))?.key ?? null
    })
  }, [visible, filtered, results])

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

  /* THE RAIL'S TOP AT REST, for its height (BoxBrowse.css `.browse-map`, UX-227). Read off the
     rail's parent, which is never sticky, so a resize while the page is scrolled reads the same
     number as one at rest. */
  useLayoutEffect(() => {
    const map = mapEl
    const body = map?.parentElement ?? null
    if (map === null || body === null) return
    const measure = () => {
      map.style.setProperty('--browse-rail-rest', `${Math.round(body.getBoundingClientRect().top + window.scrollY)}px`)
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [mapEl])

  /* Keep the selected row where it can be seen — within the rail, never by scrolling the page. */
  useEffect(() => {
    const current = listRef.current?.querySelector('[aria-current="true"]')
    if (current instanceof HTMLElement) {
      scrollWithin(current, mapRef.current, jumpRef.current === selected ? 'start' : 'nearest')
    }
    jumpRef.current = null
  }, [selected, visible])

  /* And the selected box, in a box list long enough to scroll — UNLESS a direct press put it
     there (N3, D118): the operator can already see a row they just pressed, so scrolling the
     rail in answer to their own click moves it under the hand that pressed it. */
  useEffect(() => {
    if (skipRailScroll.current) {
      skipRailScroll.current = false
      return
    }
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
   * to the list, arming the deep keys.
   *
   * D192 (item 2): under a search, the landing is computed off `results` — the
   * search's own cross-box answer — rather than off `inQuery`, which is this box's own
   * matched rows now and can never describe a box being switched TO. `inQuery` still answers
   * for the UNFILTERED case (no query: `next` is always the box already on screen at that
   * point, so `inQuery` — this box's own rows, unfiltered — is exactly right for it). Once
   * the target box's OWN rows land (the box-scoped fetch effect), the "selection follows the
   * filter" effect below re-derives the same answer from `visible` and confirms it — this is
   * what lets the row highlight and the copies list update the instant the press lands,
   * without waiting for that fetch first. */
  const selectShelf = (next: Shelf) => {
    /* A PRESS NAMES THE DRAWER; IT IS NEVER A RE-RANK (D118, the review that caught PR
     * #404's regression). Marked before `setShelf` so the row-hold below never stands on
     * the box the operator just left. */
    shelfSource.current = 'manual'
    /* N3: the row named here is a row the operator is already looking at (they just pressed
       it), so the rail's own scroll-into-view effect skips this one run. */
    skipRailScroll.current = true
    setShelf(next)
    if (typeof next === 'number') touchBox(next)
    let landingKey: string | undefined
    if (filtered && results !== null) {
      const counts = new Map<string, number>()
      const keyOf = (copy: SearchCopy) => `${copy.place.box}/${copy.place.section ?? '?'}`
      const candidates: SearchCopy[] = []
      for (const group of results.groups) {
        for (const copy of group.copies) {
          if (copyShelf(copy) !== next) continue
          candidates.push(copy)
          if (!copyDeparted(copy)) counts.set(keyOf(copy), (counts.get(keyOf(copy)) ?? 0) + 1)
        }
      }
      let best: SearchCopy | undefined
      let most = 0
      for (const copy of candidates) {
        if (copyDeparted(copy)) continue
        const n = counts.get(keyOf(copy)) ?? 0
        if (n > most) {
          most = n
          best = copy
        }
      }
      landingKey = (best ?? candidates.find((copy) => !copyDeparted(copy)) ?? candidates[0])?.key
    } else {
      const rowsThere = inQuery.filter((row) => shelfOf(row) === next)
      landingKey = landingOf(rowsThere)?.key
    }
    if (landingKey !== undefined) {
      jumpRef.current = landingKey
      setSelected(landingKey)
    }
    listRef.current?.focus(FOCUS)
  }

  /* THE ROW THE WALK STANDS ON — AND IT DOES NOT BLINK OUT WHILE A SEARCH RE-RANK IS
   * FETCHING THE BOX IT MOVED TO (2026-09-19, the owner's "fix the product" ruling;
   * amended the same day by the review that caught PR #404's regression; D118's fourth
   * floor).
   *
   * `visible` is `rows` — ONE BOX'S cards since D192 — narrowed to `shelf`. A fresh
   * search answer can move `shelf` to another box on its own (D132), with no press
   * behind it, and `rows` still holds the box before it until that box's own
   * `GET /inventory/<box>` lands. In that window `visible` is EMPTY, this found nothing,
   * `onSelect(null)` reached `Inventory.tsx`, and its `detail` — the whole copies column
   * — was UNMOUNTED and then mounted again when the rows arrived. Measured on the rig
   * with that box read delayed 400ms at 6x CPU throttle: the column was gone for 679ms
   * and came back as the skeleton (see D118's amendment).
   *
   * THE FIRST FIX HELD THE ROW ACROSS EVERY SHELF CHANGE, AND THAT WAS THE REGRESSION. A
   * PRESS to another drawer, or a walk-to a specific copy elsewhere, produces the exact
   * same shape — `shelf` changes, `rows` lags — but the operator is asking for a
   * DIFFERENT card on purpose. Holding then drew box 2's card under a `Box 7` header
   * with `CardOps` live against it, while the list said "Nothing in box 7 yet" — false,
   * and an operator could act on the wrong box's card. `shelfSource` (declared above,
   * beside `shelfAnswered`) says WHY `shelf` last moved, and only a search re-rank may
   * hold. A press or a walk-to falls straight to `null`, which is the pre-fix behaviour:
   * the detail column blanks rather than lying about whose card it shows. */
  const found = useMemo(
    () => visible.find((row) => row.key === selected) ?? null,
    [visible, selected],
  )
  const held = useRef<Row | null>(null)
  useEffect(() => {
    if (found !== null) held.current = found
  }, [found])
  const awaitingRows = typeof shelf === 'number' && rowsShelf !== shelf
  const searchReRank = shelfSource.current === 'search'
  /* THE OWNER'S RULING, 2026-09-19: THE PREVIOUS DRAWER STAYS ON SCREEN, DIMMED, WHILE THE NEW
   * ONE IS IN FLIGHT — NEVER BLANK. Before this, `awaitingRows` on a PRESS or a walk-to (never
   * a search re-rank, which already holds via `searchReRank` above) drew nothing at all: no
   * sentence, no spinner, in both the walk list and the copies column. Blank was itself a
   * regression risk — an empty pane invites a second press — and it cost a layout jump when
   * the real rows finally landed and the pane reappeared at its full height.
   *
   * `heldSections` and `heldDetail` are this file's OWN memory of the last box that actually
   * answered, kept beside `held` (the row) above — all three write only when the render is
   * NOT awaiting (this box's rows are its own), so none of them can ever be primed with a
   * partial or in-flight answer. They read as the DISPLAYED content during the wait, never as
   * a claim about the box the header now names — a4f3594b's regression was exactly that claim
   * (box 2's card drawn live under a `Box 7` header), so the dimmed render below is marked
   * `aria-busy` and stripped of every pointer and keyboard path to it (`.browse-list[aria-busy]`
   * / `.browse-card[aria-busy]` in BoxBrowse.css), on top of being visually dimmed to
   * `--bn-disabled`. It is a transition, not a claim. */
  const heldSections = useRef<readonly Section[]>([])
  useEffect(() => {
    if (!awaitingRows) heldSections.current = sections
  }, [sections, awaitingRows])
  const heldDetail = useRef<ReactNode>(null)
  useEffect(() => {
    if (found !== null) heldDetail.current = detail
  }, [found, detail])
  /* THE LIST'S OWN HEIGHT, HELD THROUGH THE SAME WINDOW (this collision's fix, found merging
   * against a27c811f/b8bd679b, 2026-09-19). `heldSections` above keeps the CONTENT identical
   * through a press — the same three rows, dimmed — but the list's rendered HEIGHT still
   * depends on `.browse-box-head` and `.browse-status` above it in the SAME viewport-capped
   * flex column (`.browse-map`'s `max-height`), and those differ BY BOX for reasons that have
   * nothing to do with the list: a census with more figures, a name that wraps, more sections,
   * a ticked selection, a taller status line. When the outgoing box's own head+status needed
   * more of that shared budget than the incoming box's does, `.browse-list`'s `flex: 0 1 auto`
   * gives up the difference and its min-height floor absorbs the rest — so the SAME held rows
   * render shorter under the old box and spring back to their natural height the instant the
   * header switches to the new one, before a single new row has landed. Held content at a
   * height that moves for a reason unrelated to the content is the same regression a27c811f
   * fixed one layer up, so it gets the same medicine: `heldListHeight` is the list's own last
   * MEASURED height while it was still answering for ITS OWN box, PINNED as an explicit
   * `height` (not `minHeight` — the new box's own budget can be LARGER too, and the point is
   * that the held rows render at the SAME height either way) for exactly the `awaitingRows`
   * window, and released the instant the new box's rows land, so the new box's own steady
   * state is never constrained by the old one's. */
  const heldListHeight = useRef<number | null>(null)
  useLayoutEffect(() => {
    if (!awaitingRows) heldListHeight.current = listRef.current?.getBoundingClientRect().height ?? null
  })
  const listHoldStyle: CSSProperties | undefined =
    awaitingRows && heldListHeight.current !== null ? { height: heldListHeight.current } : undefined
  /* THE WALK LIST'S OWN DISPLAYED CONTENT — the last box that answered, while this one has
   * not. `sections` itself goes empty the instant `shelf` moves (D192: `rows` is one box's
   * cards, and `onShelf` narrows by the NEW `shelf` before the new box's own read lands), so
   * reading `sections` straight through the wait is what drew nothing at all. */
  const displaySections = awaitingRows ? heldSections.current : sections
  /* THE WALK HAS NOTHING TO STAND ON ONLY WHEN THERE IS NOTHING THERE AND THE BOX HAS SAID SO.
   * Two different gaps close here and both of them used to unmount the copies column, and
   * both are scoped to `searchReRank` for the reason above. The box the walk moved to has
   * not answered yet (`awaitingRows`, `visible` empty). Or its rows HAVE landed and
   * `selected` is still the key from the box before — `visible` is full, this finds
   * nothing, and the landing effect above re-points `selected` in the very next effect
   * pass. A single render of `null` is enough to destroy `CopiesPanel` and its answer, so
   * neither gap may produce one WHILE THE MOVE WAS A RE-RANK. Null is reserved for the
   * honest case: the shelf has answered and holds no row to walk, or the shelf changed by
   * a press or a walk-to and the panel is honestly between cards. */
  const selectedRow = found ?? (visible.length === 0 && !awaitingRows ? null : searchReRank ? held.current : null)
  /* THE CARD PANEL'S OWN DISPLAYED ROW AND DETAIL (owner's ruling, 2026-09-19), scoped to the
   * one case `searchReRank` does not already cover — a search re-rank still holds via
   * `selectedRow` itself, above. A press or a walk-to falls straight to `null` there on
   * purpose (the a4f3594b fix), so this is the one place that stands the previous row back
   * up — DIMMED, never as a claim about the box now named — while that box's own rows are in
   * flight. */
  const dimPanel = awaitingRows && selectedRow === null && held.current !== null
  const panelRow = dimPanel ? held.current : selectedRow
  const panelDetail = dimPanel ? heldDetail.current : detail

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

  /* A jump is accepted here and landed below. `jumpBox` rides beside `jump` in a ref rather
   * than in state: it is read once, synchronously, the moment the jump effect below needs to
   * switch shelves, and giving it its own state would be a second trigger for the same
   * effect to chase. */
  const jumpBox = useRef<number | null>(null)

  /* THE CARD THE HASH NAMED, walked to once its box's rows have landed. The same `jump` a
     copies-list press takes, so the box, the fold, the mark and the scroll arrive together.

     READ ON EVERY HASH CHANGE INSIDE `#/inventory`, NOT ONLY ON MOUNT. Review's pill is a link,
     and a second pill pressed while this screen is already open changes the hash without a new
     mount; reading the hash once left the walk on the first card. A card in another box moves
     the walk to that box first (its `box=`), and this runs again when that box's rows land. */
  const [wantedCard, setWantedCard] = useState<{ cid: string; box: number | null } | null>(() => {
    const cid = cardParam()
    return cid === null ? null : { cid, box: boxParam() }
  })
  useEffect(() => {
    const onHash = () => {
      if (!window.location.hash.startsWith('#/inventory')) return
      const cid = cardParam()
      if (cid !== null) setWantedCard({ cid, box: boxParam() })
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  useEffect(() => {
    if (wantedCard === null || rows === null) return
    const row = rows.find((candidate) => candidate.card.cid === wantedCard.cid)
    if (row === undefined) {
      const box = wantedCard.box
      if (box !== null && box !== shelf && shelves.includes(box)) {
        /* A NAMED CARD, NEVER A RE-RANK — `selectShelf`'s own reason (D118). */
        shelfSource.current = 'manual'
        setShelf(box)
      }
      return
    }
    setWantedCard(null)
    jumpBox.current = typeof row.card.box === 'number' ? row.card.box : null
    setJump(row.key)
  }, [rows, wantedCard, shelf, shelves])
  useEffect(() => {
    if (goTo === undefined || goTo === null) return
    if (askedAt.current === goTo.at) return
    askedAt.current = goTo.at
    jumpBox.current = goTo.box
    setJump(goTo.key)
  }, [goTo])

  /* Walk to the card something outside asked for: the box, the fold, the mark and the scroll
   * in one batch. A query that hides the target is dropped rather than the jump.
   *
   * D192 (store-scaling item 2): `rows` now holds only the CURRENT box's cards, so
   * a jump to a copy in a DIFFERENT box can no longer find it there by scanning `rows` the way
   * it used to when `rows` held the whole store. `goTo.box` (carried by the caller, which
   * already knows it — `Inventory.tsx`'s `walkTo` reads it off the `SearchCopy` the press
   * came from) is switched to FIRST when the target is not on the current shelf; `jump` is
   * left set, so the next run of this effect, once that box's `rows` has landed and really
   * contains the target, finishes the section-opening/selection/scroll work below. */
  useEffect(() => {
    if (jump === null) return
    if (rows === null) return
    const row = rows.find((candidate) => candidate.key === jump)
    if (row === undefined) {
      const landing = jumpBox.current
      if (typeof landing === 'number' && landing !== shelf) {
        /* A WALK-TO NAMES ONE CARD, NEVER A RE-RANK — same reasoning as `selectShelf`
         * (D118, the review that caught PR #404's regression). */
        shelfSource.current = 'manual'
        setShelf(landing)
        return
      }
      /* `rows` MUST ACTUALLY BE THIS SHELF'S OWN BEFORE GIVING UP. `shelf` alone catching up
       * to `landing` re-runs this effect on the very next render, while `rows` is still the
       * PREVIOUS shelf's stale data — the fetch for the new shelf has not landed yet. Without
       * this check the jump was abandoned right there, before the box it just switched to had
       * any chance to answer. */
      if (rowsShelf !== shelf) return
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
    /* This `landing` is already the current shelf in the ordinary case — `row` came from
     * `rows`, which is box-scoped (D192) — so this rarely moves `shelf` at all. Marked
     * `'manual'` anyway for the one path where it can (a target found through `inQuery`
     * on a shelf the box-scoped fetch has not caught up to): a walk-to is always a named
     * card, never a re-rank, and the row-hold below must not stand on a superseded box. */
    shelfSource.current = 'manual'
    setShelf(landing)
    if (typeof landing === 'number') touchBox(landing)
    jumpRef.current = jump
    setSelected(jump)
    listRef.current?.focus(FOCUS)
    setJump(null)
  }, [jump, rows, rowsShelf, inQuery, searching, setQuery, shelf])

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

  const selectedLabel = panelRow === null ? null : positionLabel(panelRow.card)
  const at = visible.findIndex((row) => row.key === selected)
  const boxMap = useMemo(() => new Map(boxRecords.map((record) => [record.box, record])), [boxRecords])

  /* The box list: every reachable shelf, and under a query the boxes with no match, dimmed. */
  const cells = useMemo(() => {
    const out: { shelf: Shelf; reachable: boolean }[] = shelves.map((s) => ({ shelf: s, reachable: true }))
    if (filtered || facetActive) {
      for (const record of boxRecords) {
        if (!shelves.includes(record.box)) out.push({ shelf: record.box, reachable: false })
      }
      out.sort((a, b) => {
        if (typeof a.shelf === 'number' && typeof b.shelf === 'number') return order(a.shelf, b.shelf)
        if (typeof a.shelf === 'number') return -1
        if (typeof b.shelf === 'number') return 1
        return String(a.shelf).localeCompare(String(b.shelf))
      })
    }
    return out
  }, [shelves, filtered, facetActive, boxRecords, order])

  const shelfName = shelfBox?.name ?? null
  const shelfChip =
    shelf === null ? 'Boxes' : shelfLabel(shelf, shelfName)

  // ---------------------------------------------------------------------------- the rail

  const rail = (
    <div className="browse-map" ref={holdMap}>
      {/* THE KIT'S FILTER BAR (FLT-09): the search, the three facets in any order and the one
          count line. Hide sold stays on the walk's own bar, beside the rows it folds. The rail is narrow, so the facets sit behind one Filters
          press: a popover beside it on a desk, a sheet on a phone. */}
      <FilterBar
        className="browse-filterbar"
        facets={countedFacets}
        value={facetValue}
        onChange={setFacetValue}
        compact={phone ? 'sheet' : 'popover'}
        search={{
          query,
          onChange: setQuery,
          loading,
          failure: searchFailure,
          /* N5: `SearchField`'s own default, "Card name, number or SKU", cut to "Card na" in
             the rail's own narrow column at 720 and 820 — a raw clip, no ellipsis, off the
             native `placeholder` attribute. Shorter here, where the column is narrowest. */
          placeholder: 'Search',
        }}
        count={{ shown: reachableCount, total: boxRecords.length, noun: { one: 'box', many: 'boxes' } }}
        sort={{
          options: [
            { key: 'recent', label: 'Most recent' },
            { key: 'value', label: 'Value', asc: 'Lowest first', desc: 'Highest first', first: 'desc' },
          ],
          value: sort,
          onChange: setSort,
          defaultValue: { key: 'recent', dir: 'desc' },
        }}
        beside={
          phone ? undefined : (
            <IconButton
              icon="chevronLeft"
              label="Collapse the box rail"
              className="browse-rail-toggle"
              onClick={() => setRailCollapsed(true)}
            />
          )
        }
      />

      {cells.length === 0 ? null : (
        <div className="browse-boxes bn-panel" role="group" aria-label="Choose a box to walk" ref={boxesRef}>
          {cells.map(({ shelf: cell, reachable }) => {
            const record = typeof cell === 'number' ? boxMap.get(cell) : undefined
            const onHand = record ? (record.on_hand ?? record.cards - record.sold - record.retired - record.moved) : null
            const pct = record && record.cards > 0 && onHand !== null ? Math.round((onHand / record.cards) * 100) : 0
            const sealed = record?.state === 'closed'
            const matches = matchesByShelf.get(cell) ?? (typeof cell === 'number' ? facetMatchesByBox.get(cell) : undefined)
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
                      : /* The bare figure in `.browse-boxcell-count` (`record.cards`) has no
                         unit of its own — a screen reader would otherwise read the button's
                         name and then a naked number. Naming it here, in the one aria-label
                         the button already carries, rather than a second aria-label on the
                         count span, which a button's own explicit aria-label would swallow
                         (S16). SEALED STAYS LAST: `inventory.spec.ts`'s own sealed-row case
                         reads `/sealed$/` off this string, so the captured count is inserted
                         before it rather than appended after. */
                        `${shelfLabel(cell, record?.name)}${record ? `, ${record.cards.toLocaleString()} captured` : ''}${sealed ? ', sealed' : ''}`
                }
                aria-current={cell === shelf ? 'true' : undefined}
                disabled={!reachable}
                onClick={() => selectShelf(cell)}
              >
                {/* NO NUMBER TILE (D132). The name is how the owner knows a drawer, the index
                    is how the store keys it; an unnamed box still reads `Box N` in the name
                    column and every cell's accessible name still says `Box N`. The two pseudo
                    shelves keep their glyph, which was never a number. */}
                {typeof cell === 'number' ? null : (
                  <span className="browse-boxcell-glyph">
                    <Icon name={cell === 'pooled' ? 'layers' : 'alert'} size={14} />
                  </span>
                )}
                <span className="browse-boxcell-text">
                  <span
                    className="browse-boxcell-name"
                    title={typeof cell === 'number' ? (record?.name ?? `Box ${cell}`) : shelfLabel(cell)}
                  >
                    {typeof cell === 'number' ? (record?.name ?? `Box ${cell}`) : shelfLabel(cell)}
                  </span>
                  {/* The lock beside the row already says sealed; the meta keeps to the count. */}
                  <span className="browse-boxcell-meta">
                    {/* ONE LABEL FOR "NO MATCH HERE" (UX-261), whether a search or a filter
                        left the box out. Sorted by value and not searching, the meta is the
                        one figure that sort is actually about (D221: `Money`, never a plain
                        string, or this dollar sign sits in the wrong face). */}
                    {!reachable
                      ? 'No match'
                      : matches !== undefined
                      ? `${matches} ${matches === 1 ? 'match' : 'matches'}`
                      : record && sort.key === 'value' && typeof cell === 'number'
                        ? valueByBox?.has(cell) ? <Money value={valueByBox.get(cell)} /> : 'no reading'
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
                {record ? (
                  // The track exists on every record row, sealed or not (the lock's own
                  // horizontal form of D118: a row's geometry may not depend on which of its
                  // states is drawn). Only the glyph inside is conditional.
                  <span
                    className="browse-boxcell-lock"
                    title={sealed ? 'Sealed' : undefined}
                    aria-hidden={sealed ? undefined : 'true'}
                  >
                    {sealed ? <Icon name="lock" size={12} /> : null}
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
                  <IconButton
                    size="sm"
                    icon="settings"
                    label="Manage this box"
                    className="browse-manage"
                    aria-haspopup="dialog"
                    onClick={() => setManage(true)}
                  />
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
                <p>These cards have no box or place the store can read.</p>
              </div>
            )}
            {shelfBox === null ? null : boxPanel}
          </div>

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
                {/* THE HEADERS BELOW ALREADY COUNT THE SECTIONS (cut list #11, UX-269). */}
                {anyExpanded ? 'Collapse all' : 'Expand all'}
              </button>
            )}

            {searching && loading ? <span className="browse-status-text">Looking…</span> : null}
            {/* No "nothing matches" line here when this box's own matches are zero — that
                condition always coincides with `visible.length === 0 && filtered` below,
                which draws the `EmptyState` with the same message and a way to clear the
                search besides. Two "no matches" strings stacked for one empty result was
                the actual defect; the count line stays for the case this box DOES have
                matches, which the EmptyState never covers. */}
            {searching && !loading && results !== null && inQuery.length > 0 ? (
              <span className="browse-status-text bn-facts">
                <span>{visible.length} here</span> <span>{inQuery.length} of {rows?.length ?? 0} match</span>
              </span>
            ) : null}

            {onShelf.length === 0 || onHideSold === undefined ? null : (
              /* UX-254 (owner's ruling, 2026-09-24: "maybe in stock only should be the toggle
                 name?"): the words, never the meaning — checked still folds a departed copy
                 away, on by default (`storedHideSold`), and the count is still what it hides. */
              <HideToggle checked={hideSold} count={hiddenBySold} className="browse-hidesold" onChange={() => onHideSold()}>
                In stock only
              </HideToggle>
            )}

            <span className="bn-spacer" />

            {visible.length === 0 ? null : (
              <button className="browse-quiet" type="button" aria-pressed={shownAllTicked} onClick={tickAllShown}>
                {shownAllTicked ? 'untick shown' : 'tick shown'}
              </button>
            )}
          </div>

          {/* EVERY EMPTY STATE BELOW IS GATED ON `!awaitingRows` TOO (the review that caught
              PR #404's regression). `visible.length === 0` is also true for the length of a
              shelf switch — a press, a walk-to, OR a search re-rank — because `rows` still
              answers for the box before it (D192). Without the gate a press from box 2 to
              box 7 drew "Nothing in box 7 yet" while box 7 held three cards, which is a
              false sentence an operator could act on. Nothing is drawn while `awaitingRows`
              is true; the honest empty state waits for the shelf to actually answer. */}
          {visible.length === 0 && !awaitingRows && !filtered && !facetActive && shelfBox !== null ? (
            <div className="browse-empty">
              <EmptyState
                icon="box"
                title={`Nothing in ${shelfLabel(shelfBox.box, shelfBox.name)} yet`}
                body="Capture a card, or manage the box above."
                actions={
                  <Button size="sm" icon="camera" onClick={() => (window.location.hash = '#/capture')}>
                    Capture into this box
                  </Button>
                }
              />
            </div>
          ) : null}

          {/* NO SECOND "NOTHING MATCHES" HERE (UX-260): the card pane says it once, with the
              one Clear. */}

          {/* D213: the filter narrowed this box to nothing, told apart from a search's own
              empty state above — clearing the filter is a different action from clearing
              the search box, so the two never share one button. */}
          {visible.length === 0 && !awaitingRows && !filtered && facetActive ? (
            <div className="browse-empty">
              <EmptyState
                icon="filter"
                title="Nothing here matches the filter"
                body={`No card in ${shelfLabel(shelf, shelfName)} matches the game, set or rarity chosen.`}
                actions={
                  <Button size="sm" icon="x" onClick={() => setFacetValue({})}>
                    Clear the filter
                  </Button>
                }
              />
            </div>
          ) : null}

          {displaySections.length === 0 ? null : (
            <ul
              className="browse-list"
              /* THE PHONE'S BOX SHEET OPENS ON THE LIST (UX-253): its overlay focuses this first,
                 not the search, whose keyboard would cover the list the sheet was opened for. */
              data-autofocus=""
              ref={listRef}
              style={listHoldStyle}
              tabIndex={awaitingRows ? -1 : 0}
              aria-label="Captured cards, in box-walk order"
              aria-keyshortcuts="ArrowLeft ArrowRight PageUp PageDown Home End X"
              onKeyDown={awaitingRows ? undefined : onListKeys}
              aria-busy={awaitingRows ? 'true' : undefined}
              data-dimmed={awaitingRows ? 'true' : undefined}
            >
              {/* OWNER'S RULING, 2026-09-19: while `awaitingRows`, `displaySections` is
                  `heldSections` — the last box that answered — never the live (empty)
                  `sections`. Every row below still comes off the SAME `Row` objects the
                  live walk would use once they exist; nothing here is invented. The
                  `aria-busy`/`data-dimmed` pair above and `tabIndex={-1}` /
                  `onKeyDown={undefined}` close the one path a stale row could still act
                  on: BoxBrowse.css's `[aria-busy='true']` rule dims it and drops
                  `pointer-events`, so a click cannot land, and the list drops out of the
                  tab order so a key cannot either — a transition is drawn, never acted on. */}
              {displaySections.map((section) => {
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
                    : `${onHand} on hand, ${gone} departed, ${section.rows.length} records`
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
                        /* SAID ONCE (UX-271): the section and its count are the fold's own name,
                           beside this, so the tick names only what it ticks. */
                        aria-label={`Tick all of ${section.parts.head}`}
                        onChange={(event) => tickSection(section, event.target.checked)}
                      />
                      <button
                        className="browse-sectfold"
                        type="button"
                        aria-expanded={open}
                        onClick={() => toggleSection(section)}
                      >
                        <Icon name="chevronRight" size={14} className="browse-sectmark" />
                        <SectionTitle parts={section.parts} />
                        {/* ONE COUNT PER HEADER (cut list #9): the title already says how many
                            cards. The badge draws only a tick count, and keeps its slot while
                            empty, so a tick moves nothing in the header (D118). */}
                        <span
                          className="browse-sectcount"
                          data-empty={ticked === 0 ? 'true' : undefined}
                          aria-hidden={ticked === 0 ? 'true' : undefined}
                          title={ticked === 0 ? undefined : `${ticked} of ${section.rows.length} ticked; ${census}`}
                        >
                          {ticked === 0 ? '' : `${ticked}/${section.rows.length}`}
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
                                {/* THE WIDTH A DEPARTURE WILL NEED, RESERVED BEFORE IT IS
                                    SPENT (D118). `departedSlot` (S5) is what the slot cell
                                    ITSELF draws once this row departs — its own struck `#N`
                                    in the ordinary case, the store key only for the rare
                                    pre-ruling record with no label to read a number off. The
                                    ghost holds that exact string, in the face it will be set
                                    in, so the track is already that wide and a departure
                                    changes only which of the two is painted.
                                    IT IS `content:` AND NOT A TEXT NODE, AND IT IS
                                    `aria-hidden`. A hidden twin in the DOM would put the
                                    reserved string into every row's text content, where the
                                    census, the walk's locators and this button's own
                                    accessible name all read; pseudo content is in none of
                                    those, and the attribute keeps the pseudo out of the
                                    accessibility tree as well. And it is the STRING rather
                                    than a `ch` count of it: the count was the first build and
                                    it is an estimate — a face whose weight is synthesized does
                                    not set five characters at five times the advance of `0`,
                                    which is the register the whole 1px is in. */}
                                <span className="browse-row-position">
                                  <span className="browse-row-slot">{rowSlot(row)}</span>
                                  <span
                                    className="browse-row-slotghost"
                                    aria-hidden="true"
                                    style={{ '--bn-slot-key': JSON.stringify(departedSlot(row.card)) } as CSSProperties}
                                  />
                                </span>
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
                                {/* A ROW THAT LEFT THE BOX (UX-222): the headstone, the product's one mark
                                    for a card that left (`ICON_MEANINGS`), named by its state. It
                                    was the arrow that means "opens a new tab". */}
                                {departed ? (
                                  <span className="browse-row-badge is-out" title={stateLabel(row.card.state)}>
                                    <Icon name="headstone" size={12} />
                                    <span className="bn-sr">{stateLabel(row.card.state)}</span>
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

          {/* NO KEY LEGEND UNDER THE LIST (UX-272, cut list #10): the ? sheet lists every key this
              list takes (App.tsx INVENTORY_KEYS), and the legend cost the list a row. */}
        </div>
      )}
    </div>
  )

  const miniRail = (
    <div className="browse-rail-mini">
      <IconButton
        icon="chevronRight"
        label="Expand the box rail"
        onClick={() => setRailCollapsed(false)}
      />
      {cells
        .flatMap(({ shelf: cell }) => (typeof cell === 'number' ? [cell] : []))
        .map((cell) => (
          <button
            key={String(cell)}
            type="button"
            className="browse-boxcell-mini"
            aria-label={shelfLabel(cell, boxMap.get(cell)?.name)}
            title={shelfLabel(cell, boxMap.get(cell)?.name)}
            aria-current={cell === shelf ? 'true' : undefined}
            onClick={() => {
              selectShelf(cell)
              setRailCollapsed(false)
            }}
          >
            {miniLabel(boxMap.get(cell)?.name ?? null, cell)}
          </button>
        ))}
    </div>
  )

  // ---------------------------------------------------------------------------- the pane

  const open = panelRow === null ? null : openQuestion(queued, panelRow)
  const game = panelRow === null ? null : gameWord(panelRow.card)

  /* THE ZERO-BOX STORE (D192, this item). `shelf` never leaves `null` here: the shelf
   * effect above returns the instant `shelves.length === 0`, so the box-scoped rows fetch
   * that effect gates on a numeric shelf never fires, `rows` never leaves `null`, and
   * `failure` is never set either — a fresh store had no error to report. The registry read
   * (`boxesAnswered`) is the one signal that DOES land regardless, so it is what tells "no
   * boxes exist" apart from "the registry has not answered yet." Read off `boxRecords`
   * rather than `shelves` so a search with zero matching boxes never falls into this branch. */
  const noBoxesYet = boxesAnswered && boxRecords.length === 0

  return (
    <section className="browse">
      {failure === null ? null : (
        <Notice tone="danger" title={failure.message} code={failure.code}>
          <Button size="sm" icon="refresh" onClick={() => setReloads((n) => n + 1)}>
            Try again
          </Button>
        </Notice>
      )}

      {rows === null && failure === null && !noBoxesYet ? (
        <div className="browse-body browse-body-loading">
          {/* THE KIT'S LOADING SHAPE (D275): the rail's rows, then the card. */}
          <Loading rows={6} label="Reading the inventory" />
          <Loading shape="cards" rows={1} label="Reading the card" />
        </div>
      ) : null}

      {rows === null && failure === null && noBoxesYet ? (
        <div className="bn-panel">
          <EmptyState
            icon="box"
            title="No boxes yet"
            body="Capture a card to make one."
            actions={
              <Button variant="primary" icon="camera" onClick={() => (window.location.hash = '#/capture')}>
                Capture a card
              </Button>
            }
          />
        </div>
      ) : null}

      {rows !== null && boxesAnswered && storeCards === 0 ? (
        <div className="bn-panel">
          <EmptyState
            icon="camera"
            title="No cards captured yet"
            body="Captured cards show up here."
            actions={
              <Button variant="primary" icon="camera" onClick={() => (window.location.hash = '#/capture')}>
                Capture your first card
              </Button>
            }
          />
        </div>
      ) : null}

      {/* D192 (item 2): `storeCards`, not `rows.length` — this gates the RAIL as
       * well as the current box's own rows, and the rail has to go on showing every box
       * (so the operator can switch away) even when the box landed on happens to hold none.
       * `rows.length === 0` here used to mean "the whole store is empty" back when `rows`
       * held the whole store; now it just as often means "this one box is empty," which is
       * `.browse-empty`'s own case inside the panel below, not a reason to hide the rail. */}
      {rows !== null && storeCards > 0 ? (
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
              <IconButton icon="search" label="Search cards" onClick={() => setRailOpen(true)} />
            </div>
          ) : null}

          <div className="browse-body" data-rail={railCollapsed && !phone ? 'collapsed' : undefined}>
            {phone ? null : railCollapsed ? miniRail : rail}

            <div className="browse-side">
              {panelRow === null ? (
                <div className="bn-panel">
                  {chooserActive && searchGroups !== null ? (
                    <VariantChooser
                      groups={searchGroups}
                      onPick={(index) => setChosenVariant({ query, index })}
                    />
                  ) : awaitingRows ? null /* THE SAME FALSE CLAIM, A SECOND PLACE (the review
                      that caught PR #404's regression): a press or a walk-to can land
                      `selectedRow` on null while the shelf it moved to is still fetching, and
                      "Nothing in box N yet" is exactly as false here as it was in the list
                      above — the box the header already names can hold cards this panel has
                      not seen yet. Nothing is drawn until the shelf answers UNLESS `held`
                      already has a previous row to stand on, in which case `panelRow` is
                      already non-null and this branch does not run at all (owner's ruling,
                      2026-09-19: dimmed, not blank — see `dimPanel` above). This branch is
                      left for the one case `held` cannot cover: the very first box a session
                      opens, where there is no previous row to dim. */ : filtered ? (
                    <EmptyState
                      icon="search"
                      title={`Nothing matches “${query.trim()}”`}
                      body="Searches name, number, SKU, set, note."
                      actions={
                        <Button icon="x" onClick={() => setQuery('')}>
                          Clear the search
                        </Button>
                      }
                    />
                  ) : (
                    <EmptyState
                      icon="box"
                      title={shelf === null ? 'Pick a box' : `Nothing in ${shelfLabel(shelf, shelfName)} yet`}
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
                  {/* NO `key` ON THIS SECTION (2026-09-19, the owner's "fix the product"
                      ruling). It carried `key={selectedRow.key}` from the rebuild (D94-D99)
                      so `.browse-card`'s `bn-page-in` entrance replayed on every card. The
                      copies column — `{detail}`, which is `Inventory.tsx`'s `CopiesPanel` —
                      is INSIDE this section, so that key tore it down and built it again on
                      every change of selection. A rebuilt `CopiesPanel` has no search answer
                      and no memory of one, so it drew its skeleton for a debounce plus a
                      fetch: the copies list went from six rows to none and back, under the
                      hand, with no press (D118). Measured on the rig at 6x CPU throttle with
                      the box read delayed: 400ms of skeleton per selection change.
                      `CopiesPanel`'s own D118 guard — keep the group found in the still-old
                      `results` while the re-read runs — assumes it survives a row change, and
                      this key is why it had never once run. The entrance now plays when the panel appears,
                      which is what an entrance is for. `CardOps` below keeps its own key:
                      that one resets a MENU, not a fetch. */}
                  <section
                    className="bn-panel browse-card"
                    aria-busy={dimPanel ? 'true' : undefined}
                    data-dimmed={dimPanel ? 'true' : undefined}
                    /* REVIEW, PR #407: `pointer-events: none` (BoxBrowse.css) blocks the
                     * mouse alone. Tab still reached `CardOps`' "Card actions" button and
                     * Enter opened its menu on `held.current` — the previous box's card,
                     * under the new box's header, live — which is the a4f3594b regression
                     * again, by keyboard. `inert` removes the whole subtree from the tab
                     * order AND refuses activation, so neither path reaches a stale
                     * control while `dimPanel` is true. */
                    inert={dimPanel}
                  >
                    <div className="browse-hero-head">
                      <div className="browse-hero-text">
                        <h2 className={nameOf(panelRow.card) === null ? 'browse-hero-name is-unnamed' : 'browse-hero-name'}>
                          {nameOf(panelRow.card) ?? 'Not identified yet'}
                        </h2>
                        <p className="browse-hero-sub">
                          {[numberCell(panelRow.card) === 'none' ? null : numberCell(panelRow.card), panelRow.card.set_hint, game]
                            .filter((part): part is string => typeof part === 'string' && part !== '')
                            .map((part, i) => (
                              <span key={`${part}-${i}`} className={i === 0 && numberCell(panelRow.card) !== 'none' ? 'browse-hero-number' : undefined}>
                                {part}
                              </span>
                            ))}
                        </p>
                        {/* WHERE IT IS, BESIDE THE NAME, IN A ONE-COLUMN PANE (UX-187). At 390 and
                            720 the copy row that says it sits under the photograph, below the
                            fold. Drawn only where the pane is one column (BoxBrowse.css), so the
                            wide pane does not say it twice. */}
                        {positionLabel(panelRow.card) === null ? null : (
                          <p className="browse-hero-place">{sayPlace(positionLabel(panelRow.card) ?? '')}</p>
                        )}
                        <div className="browse-hero-chips">
                          {/* No `chooserActive` check needed here: while the chooser shows,
                              `panelRow` is null and this whole branch does not render, so
                              nothing here can bypass it. This chip is reachable only once a
                              printing is picked (or the search always had one), and it is
                              what gets an operator back to the chooser after the walk has
                              carried them away from it. */}
                          {searchGroups !== null && searchGroups.length > 1 ? (
                            <Chip icon="layers" onClick={() => setChosenVariant(null)}>
                              <span className="bn-facts">
                                <span>{searchGroups.length} printings</span> <span>change</span>
                              </span>
                            </Chip>
                          ) : null}
                          {claimList(panelRow.card.metadata_finish).map((finish) => (
                            <Pill key={`f-${finish}`} icon="sparkles">
                              {titleCase(finish)}
                            </Pill>
                          ))}
                          {claimList(panelRow.card.rarity_claim).map((rarity) => (
                            <Pill key={`r-${rarity}`}>{titleCase(rarity)}</Pill>
                          ))}
                          {/* THE CARD'S STATE ONLY WHEN IT IS THE EXCEPTION (UX-221). */}
                          {panelRow.card.state === IDENTIFIED ? null : (
                            <Pill tone={stateTone(panelRow.card.state)}>{stateLabel(panelRow.card.state)}</Pill>
                          )}
                          {open === null ? null : (
                            <a className="bn-pill bn-pill-warn browse-queuechip" href="#/review">
                              <Icon name="clock" size={12} />
                              In the {open.queue} queue
                            </a>
                          )}
                        </div>
                      </div>
                      <CardOps
                        key={panelRow.key}
                        row={panelRow}
                        onChanged={() => setReloads((n) => n + 1)}
                        reshoot={
                          <ReshootControl
                            row={panelRow}
                            busy={reshootBusy === panelRow.key}
                            failure={
                              reshootFailure !== null && reshootFailure.key === panelRow.key
                                ? reshootFailure.failure
                                : null
                            }
                            onPick={(file) => beginReshoot(panelRow, file)}
                          />
                        }
                      />
                    </div>

                    {open === null ? null : (
                      <div className="browse-queued">
                        <Notice tone="warn" title={`Waiting in the ${open.queue} queue — ${reasonLabel(open.entry.reason)}.`} code={`${open.entry.reason}, ${open.queue}, ${open.entry.candidates.length} candidates`}>
                          {waitingFor(open.entry.first_seen)}.{' '}
                          {open.entry.candidates.length > 0
                            ? `${open.entry.candidates.length} candidate row${open.entry.candidates.length === 1 ? '' : 's'} on Review.`
                            : 'No candidate rows — cannot be answered as it stands. Re-shoot it, or stand it down on Review.'}{' '}
                          <a href="#/review">Open the review queue</a>
                        </Notice>
                      </div>
                    )}

                    <div className="browse-band">
                      <div className="browse-shot">
                        <PhotoPanel
                          row={panelRow}
                          label={selectedLabel}
                          absent={photoAbsent === panelRow.key}
                          onAbsent={() => setPhotoAbsent(panelRow.key)}
                          nonce={reshot[panelRow.key] ?? null}
                          onZoom={() => setZoomed(true)}
                          reshoot={
                            <ReshootControl
                              row={panelRow}
                              busy={reshootBusy === panelRow.key}
                              failure={
                                reshootFailure !== null && reshootFailure.key === panelRow.key
                                  ? reshootFailure.failure
                                  : null
                              }
                              onPick={(file) => beginReshoot(panelRow, file)}
                            />
                          }
                        />
                      </div>
                      <div className="browse-under">{panelDetail}</div>
                    </div>
                  </section>

                  <CardDetailsSection
                    card={panelRow.card}
                    market={panelRow.card.run === null ? undefined : priced[panelRow.card.run]}
                    listings={listings}
                    phone={phone}
                    // "Inventory only" (owner's ruling, D252): `correctable`
                    // defaults false — an allow-list of one screen — so this is the one call
                    // site that opts in. The smallest edit that ruling reaches into this file for.
                    correctable
                  />
                </>
              )}
            </div>
          </div>

          {phone ? (
            <div className="browse-actionbar">
              <div className="browse-stepper" role="group" aria-label="Step through the box">
                <IconButton
                  className="browse-stepper-btn"
                  icon="chevronLeft"
                  label="Previous card"
                  size="lg"
                  disabled={visible.length === 0 || at <= 0}
                  onClick={() => stepSelection(-1)}
                />
                <span className="browse-stepper-count">
                  {at >= 0 ? `${at + 1} / ${visible.length}` : '—'}
                </span>
                <IconButton
                  className="browse-stepper-btn"
                  icon="chevronRight"
                  label="Next card"
                  size="lg"
                  disabled={visible.length === 0 || at >= visible.length - 1}
                  onClick={() => stepSelection(1)}
                />
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
 * inside), delete a junk capture out of the middle of a box, and — for a sold or retired
 * card — bring it back (`docs/specs/undo.md` §4's slow path, the departed row's own menu).
 * The correction is reversible and takes no confirm; the mid-box delete renumbers and asks a
 * second time. Correct-claims and delete are drawn only for a card still on hand; the
 * resurrect item is drawn only for the terminal states, and moved is excluded — a move is a
 * transplant reached through `Inventory.move_card` alone, and reversing one wears the same
 * word for a different write. */
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
  // Set once a resurrect attempt refuses as `sold_origin_unknown` or `retired_origin_unknown`
  // — the store's own answer that history cannot say what to put this card back to. There is
  // no route to ask that in advance (`_sale_origin`/`_retirement_origin` run inside the
  // write's own lock), so the FIRST press is what learns it; every one after degrades to the
  // note, the same way the sale receipt withholds Undo once `restores_to` reads null.
  const [originUnknown, setOriginUnknown] = useState(false)
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
      toast({ kind: 'ok', icon: 'wand', title: 'Claims written', body: `${row.key}: ${Object.keys(patch).join(', ')}` })
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
        title: `${nameOf(row.card) ?? 'The card'} is deleted`,
        body:
          result.shifted === 0
            ? 'It was the last card in its box, so no number changed.'
            : `${result.shifted} ${result.shifted === 1 ? 'card after it takes' : 'cards after it take'} the number before.`,
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

  /* THE SLOW PATH: bring a departed card back, exactly where it was. No confirm — this route
   * IS the reversal, and `docs/DESIGN.md` bans a confirm on an action that already is one.
   * One press: the state goes back (D10, D58 — the stored index never moved, so nothing here
   * renumbers), and where the sale pulled this copy for an order, that line is released in
   * the same write (`docs/specs/undo.md` §4) — the receipt below says so without a second
   * request. */
  const resurrect = async () => {
    if (busy) return
    setBusy(true)
    setTrouble(null)
    try {
      // NOT `positionLabel`: for a departed card that reads "Box 1 · departed · B1 #1"
      // (D68), which would say a card just brought back is still departed. The box's own
      // NAME (S1: never its number) plus the store index names the same physical card
      // without the tense clash `storeKeyText`'s box number used to carry.
      // sigil-ok: a store key, `storeKeyText`'s own shape (D92) with the box respelled from
      // its number to its name — this card is not in a slot to count, same as that one.
      const label = `${row.card.place?.box_name ?? UNNAMED_BOX} #${row.card.index}`
      if (row.card.state === 'sold') {
        const result: SaleResult = await undoSale(row.card.box, row.card.index)
        toast({
          kind: 'ok',
          icon: 'undo',
          title: 'Card brought back',
          body: result.order_released
            ? `${label} is back in its box. The order it was pulled for no longer counts it shipped.`
            : `${label} is back in its box.`,
          ttlMs: 12000,
        })
      } else {
        await undoRetire(row.card.box, row.card.index)
        toast({
          kind: 'ok',
          icon: 'undo',
          title: 'Card brought back',
          body: `${label} is back in its box.`,
          ttlMs: 12000,
        })
      }
      setMenu(false)
      onChanged()
    } catch (err) {
      const failure = describeFailure(err)
      if (failure.code === 'sold_origin_unknown' || failure.code === 'retired_origin_unknown') {
        setOriginUnknown(true)
      }
      setTrouble(failure)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="browse-cardops" ref={anchor}>
      <IconButton
        icon="more"
        label="Card actions"
        aria-haspopup="menu"
        aria-expanded={menu}
        onClick={() => setMenu((held) => !held)}
      />
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
            <Icon name="pencil" size={16} /> Correct claims
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
            <>
              {!terminal || !addressable ? null : (
                <>
                  <div className="bn-menu-sep" />
                  {originUnknown ? (
                    <p className="browse-menu-note">
                      {row.card.state === 'sold'
                        ? 'The store has no earlier state for this card, so the sale cannot be reversed here. Set it by hand instead.'
                        : 'The store has no earlier state for this card, so the retirement cannot be reversed here. Set it by hand instead.'}
                    </p>
                  ) : (
                    <button
                      role="menuitem"
                      type="button"
                      className="bn-menu-item"
                      disabled={busy}
                      onClick={() => void resurrect()}
                    >
                      <Icon name="undo" size={16} /> Bring this card back
                    </button>
                  )}
                </>
              )}
              <p className="browse-menu-note">
                This card has left inventory, so it cannot be removed from its box.
              </p>
              {trouble === null ? null : (
                <Notice tone="danger" title={trouble.message} code={trouble.code} />
              )}
            </>
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
            <IconButton icon="x" label="Close" onClick={() => setOpen(null)} />
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
            <span className="bn-eyebrow bn-facts">
              <span>{positionLabel(row.card) ?? row.key}</span>
            </span>
            <h2 className="inv-dialog-title">Delete {nameOf(row.card) ?? 'this card'}?</h2>
          </div>
          <div className="inv-dialog-body">
            <p>
              Every card after it takes the number before it. <strong>No undo.</strong>
            </p>
            <p className="bn-muted">Refused if a card after it was sold, retired or listed.</p>
            {trouble === null ? null : <Notice tone="danger" title={trouble.message} code={trouble.code} />}
          </div>
          <div className="inv-dialog-foot">
            <Button variant="ghost" onClick={() => setOpen(null)} data-autofocus="">
              Cancel
            </Button>
            <Button variant="danger-solid" icon="trash" busy={busy} onClick={() => void remove()}>
              Delete this card
            </Button>
          </div>
        </Overlay>
      )}
    </div>
  )
}
