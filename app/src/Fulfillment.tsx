import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import type {
  InventoryCard,
  OrderRow,
  Place,
  PullTarget,
  SaleResult,
  SearchCopy,
  SearchGroup,
  WalkPlan,
  WalkPlanRef,
  WalkPlanTake,
} from './types'
import {
  ServerError,
  getInventory,
  getOrders,
  markSold,
  photoUrl,
  placeSentence,
  positionLabel,
  pullCopy,
  undoPull,
  undoSale,
  walkPlan,
} from './server'
import { PullConfirm } from './PullConfirm'
import { SearchField } from './SearchField'
import { CardLocations } from './CardLocations'
import { PositionBar } from './PositionBar'
import { placePartsOf, placeWordsOf, sayPlace } from './position'
import { Icon, Logo, Modal, useOverlayLayer } from './kit'
import { isEditableTarget } from './keys'
import { useSearch } from './useSearch'
import './Fulfillment.css'

/* The Fulfiller's screen — D5's second persona: a retired, non-technical relative who fills
 * orders from his own device. This route is the whole product for him, so it has no nav, no
 * jargon and nothing destructive, and every floor in docs/DESIGN.md's Fulfillment table (20px
 * body, 32px place, 44px targets 12px apart, 7:1, undo >= 10s) is kept on merit here.
 *
 * Shape: the orders first, and never a preselected copy. `GET /orders` names what is open;
 * `POST /orders/walk-plan` resolves the open orders' own demand to every on-hand copy of each
 * SKU (D212, D93, and the owner's own ruling, 2026-09-23: "if an order has 2 of card X but I
 * have 14 in inventory, I shouldn't just see 2 cards that are preselected — I should be told I
 * need to pick 2, and here's where all the copies are"). One card owed is one entry: "Pick N",
 * the card, and every copy the store holds, ranked, none ahead of the others — with search as
 * the second way in. A copy an order is waiting for is sold THROUGH the order (`pullCopy`), so
 * the owner's ledger counts it; any other copy is marked sold on its own. A sale drops a
 * receipt into a sheet at the bottom of the screen with Undo and a clock he can see draining.
 * "Pulled today" keeps a record after the clock runs out. */

/** `store/master.py:TERMINAL_STATES` — `sold`, `retired`, and `moved` (D83's third door: a
 *  card leaves a box without being sold or retired, and is exactly as gone from it). This set
 *  had only the first two, so a moved card kept reaching his list, labelled `departed` by
 *  `pipeline/join.py:departed_label` — the owner's review finding UX-013, "Cards to pull lists
 *  a sold card as 'departed B1 #19'". */
const GONE = new Set(['sold', 'retired', 'moved'])

function forSale(card: InventoryCard): boolean {
  return !GONE.has(card.state)
}

/** A pooled card (D24) has no place and is never his to pull. */
function pooled(card: InventoryCard): boolean {
  return card.place?.located === false
}

function pooledCopy(copy: SearchCopy): boolean {
  return copy.place.located === false
}

/** Rows drawn per opened box before a sentence says to type a name instead. The list is not
 *  his task; it exists to say, without a word of instruction, that this screen is about cards
 *  he can go and fetch. */
const SHOWN_PER_BOX = 30

/** Owed cards drawn in full before the rest fold under one button, so a long list of SKUs
 *  stays reachable rather than pushing the box browse off the phone screen. */
const SHOWN_OWED = 6

/** The same words CardLocations uses for the same card, so one route says it one way. */
const NO_NAME = 'This card has no name yet'

/** How long Undo stands after a sale. Shared with Inventory and Orders. */
const UNDO_WINDOW_MS = 20_000

const ALREADY_SOLD = 'already_sold'
const NOT_SOLD = 'not_sold'
const NO_ORIGIN = 'sold_origin_unknown'
/** `POST /orders/pull`'s own refusals: the copy is already on the ledger, or the list he is
 *  looking at no longer describes the store. */
const ALREADY_PULLED = 'copy_already_pulled'
const PULL_STALE = new Set([
  'pull_entry_refused',
  'order_not_ingested',
  'sku_not_on_order',
  'over_fulfilled',
  'copy_not_identifiable',
])
/** The ledger never recorded this pull, so the way back is the plain sale undo. */
const PULL_NOT_RECORDED = 'pull_not_recorded'

function refusalCode(err: unknown): string {
  return err instanceof ServerError ? err.code : ''
}

/** Reverse a sale; a `not_sold` refusal means it already is, which is the outcome he wanted. */
async function unsell(box: number, index: number): Promise<void> {
  try {
    await undoSale(box, index)
  } catch (err) {
    if (refusalCode(err) === NOT_SOLD) return
    throw err
  }
}

/** Undo is offered only when the server says what the card goes back to. */
function canTakeBack(result: SaleResult): boolean {
  const origin: unknown = result.restores_to
  return typeof origin === 'string' && origin.trim() !== ''
}

/** The order a card is being pulled for: what `pullCopy` aims with, and the number he matches
 *  to the packing slip. `orderKey` is the ledger's `source:number`, for finding the group. */
type OrderRef = {
  orderKey: string
  source: string
  number: string
  /** The buyer's display name, verbatim off the feed (D193) — `null` for a nameless order.
   *  Never the raw order id alone on screen: `orderLabel` below pairs whichever of these
   *  two he sees with the other, secondary. */
  buyer: string | null
  sku: string
  capture_id: string
}

type Sellable = {
  key: string
  box: number
  index: number
  place: string
  name: string
  /** `Near Mint`, `181/219` — what is printed on the card, drawn beside the name as sibling
   *  facts (D218): the seam between them is CSS, `.ff-card-about`'s own rule, never a typed
   *  `' · '` in the string. */
  about: readonly string[] | null
  /** The place block, for the bar and the "between" sentence. */
  where: Place | null
  /** THE CARD'S OWN NAME FOR ITS PHOTOGRAPH (D172), or null where the row it was built from
   *  has none. `sellable` reads an `InventoryCard`, `asSellable` a `SearchCopy`, and
   *  `orderByKey` (below) a `WalkPlanCopy` — the same three fields `_copy_row` composes on
   *  every route, so every constructor carries one. Null and not absent, because this is a
   *  view model built three ways and a missing key would read as an oversight in whichever
   *  constructor forgot it. */
  cid: string | null
  /** Set when an open order is waiting for this copy. The sale then goes through the order
   *  rather than around it, so the owner's ledger counts the pull. */
  order: OrderRef | null
}

type Sale = {
  card: Sellable
  /** When the undo window closes. */
  until: number
  said: string
  canUndo: boolean
  note: string | null
}

/** A sale this session recorded and did not take back — the "Pulled today" list. */
type Done = { key: string; name: string; place: string; order: string | null }

type BoxGroup = { box: number; name: string | null; cards: Sellable[] }

/** One SKU an open order still owes, and every on-hand copy in the store — the owner's own
 *  ruling, 2026-09-23: "I shouldn't just see 2 cards that are preselected. I should be told I
 *  need to pick 2, and here's where all the copies are." No `pick` is preselected here; D212
 *  (every copy is fungible) and D93 (the copies panel is the picker) both already ruled this
 *  for the resolver and for a search result, and this is the same rule reaching the walk. */
type Owed = {
  key: string
  sku: string
  name: string
  about: string[] | null
  numberDisplay: string | null
  set: string | null
  rarity: string | null
  condition: string | null
  /** How many copies of this SKU the open orders still owe, capped at what the store holds —
   *  `WalkPlanTake.wanted` summed over every stop the solver split this SKU across. A SKU the
   *  store cannot fill AT ALL never reaches this type; `plan.shortfall` carries that one. */
  wanted: number
  /** Every open order waiting on this SKU, oldest first — `pipeline/walkplan.py:demand`'s own
   *  order. A copy pulled for this card is recorded against `refs[0]`, the oldest order that
   *  still owes it; a re-read after the write is what keeps that true, because a fulfilled
   *  order drops out of its own next `for` list. */
  refs: WalkPlanRef[]
  /** Every on-hand copy of this SKU, store-wide — never only the solver's own stop. Order is
   *  the wire's own (`WalkPlanTake.copies`'s own comment): pressable, none hidden, none ahead
   *  of the others by rule. */
  copies: WalkPlanTake['copies']
  /** The same three fields `SearchGroup` carries, off `WalkPlanTake`'s own added ones — the
   *  honest live-listing count, never a fabricated zero (`owedGroup`'s own comment). The take
   *  field is optional on the wire type, so an older server's answer falls back to the same
   *  all-zero shape an unlisted SKU sends. */
  listed: { pushed: number; staged: number; live: number }
  soldHere: number
  liveAsOf: string | null
}

/** The open orders' own demand, folded to one entry per SKU — `plan.stops[].takes[]` can name
 *  the SAME sku more than once when the solver split it across drawers, and the walk here
 *  draws no drawers at all, so every take for one SKU is one card he sees once. `wanted` sums
 *  across the splits (the total still owed); `copies`/`listed`/`soldHere`/`liveAsOf` are read
 *  off the FIRST take only, because `_walk_plan_take` sends the whole on-hand list and the
 *  whole listing reading on every split — the same store-wide facts, not a stop's own slice —
 *  so a second read would only repeat them. */
function owedFrom(plan: WalkPlan): Owed[] {
  const bySku = new Map<string, Owed>()
  for (const stop of plan.stops) {
    for (const take of stop.takes) {
      const existing = bySku.get(take.sku)
      if (existing === undefined) {
        const about = [take.condition, take.number_display].filter(
          (part): part is string => typeof part === 'string' && part.trim() !== '',
        )
        bySku.set(take.sku, {
          key: take.sku,
          sku: take.sku,
          name: take.name ?? NO_NAME,
          about: about.length === 0 ? null : about,
          numberDisplay: take.number_display,
          set: take.set,
          rarity: take.rarity,
          condition: take.condition,
          wanted: take.wanted,
          refs: [...take.for],
          copies: take.copies,
          listed: take.listed ?? { pushed: 0, staged: 0, live: 0 },
          soldHere: take.sold_here ?? 0,
          liveAsOf: take.live_as_of ?? null,
        })
        continue
      }
      existing.wanted += take.wanted
      for (const ref of take.for) {
        if (!existing.refs.some((held) => held.key === ref.key)) existing.refs.push(ref)
      }
    }
  }
  return [...bySku.values()]
}

/** An owed card with the copies sold on this screen taken out — `stillHere`'s own rule, one
 *  register up: `soldSet` is optimistic, ahead of the store's own next read. Null once nothing
 *  is left to show; the card leaves the list rather than standing empty. */
function stillOwed(item: Owed, gone: ReadonlySet<string>): Owed | null {
  const here = item.copies.filter((copy) => !GONE.has(copy.state) && !gone.has(copy.key))
  if (here.length === 0) return null
  return { ...item, copies: here }
}

/** `SearchGroup` synthesised from one owed card's own wire fields — `OrdersWalkPane.tsx`'s own
 *  `currentGroup` does the same fold for the owner's skin, one register up. `copies` rides in
 *  the WIRE's OWN ORDER, never re-sorted here, and `CardLocations` reads it with
 *  `preserveOrder` so its fullest-section re-rank never runs over it. `listed`/`sold_here`/
 *  `live_as_of` are off `WalkPlanTake`'s own added fields (server/capture_server.py:
 *  `_walk_plan_take`) — the same read `do_search` makes for a live SKU group, not a fabricated
 *  zero, because the Fulfiller's skin always draws that sentence. */
function owedGroup(item: Owed): SearchGroup {
  return {
    sku: item.sku,
    names: item.name === NO_NAME ? [] : [item.name],
    number: null,
    printed_total: null,
    number_display: item.numberDisplay,
    set_hint: null,
    set: item.set,
    rarity: item.rarity,
    condition: item.condition,
    listed: item.listed,
    sold_here: item.soldHere,
    on_hand: item.copies.length,
    listable: item.copies.length,
    live_as_of: item.liveAsOf,
    copies: item.copies.map(
      (copy): SearchCopy => ({
        key: copy.key,
        state: copy.state,
        state_at: null,
        has_photo: copy.has_photo,
        capture_id: copy.capture_id,
        cid: copy.cid,
        place: copy.place,
      }),
    ),
  }
}

function sellable(key: string, card: InventoryCard): Sellable | null {
  const place = positionLabel(card)
  if (place === null) return null
  const about = [card.condition, card.number_display].filter(
    (part): part is string => typeof part === 'string' && part.trim() !== '',
  )
  return {
    key,
    box: card.box,
    index: card.index,
    place,
    name: card.name ?? NO_NAME,
    about: about.length === 0 ? null : about,
    where: card.place ?? null,
    // The inventory row's own name for its photograph (D172). Raw here — `photoUrl` is what
    // refuses a `moved:` or `nophoto:` name, so this passes on whatever the store said.
    cid: card.cid ?? null,
    order: null,
  }
}

function asSellable(group: SearchGroup, copy: SearchCopy): Sellable {
  return {
    key: copy.key,
    box: copy.place.box,
    index: copy.place.index,
    place: copy.place.label ?? '',
    name: group.names.length === 0 ? NO_NAME : group.names.join(' / '),
    about: null,
    where: copy.place,
    // `_copy_row` already filtered this one to a name that really is a photograph's.
    cid: copy.cid ?? null,
    order: null,
  }
}

/** How he reads an order he does not have raw access to: the buyer's name where the ledger
 *  has one (D193), the id always present but never alone — paired as `secondary` rather than
 *  standing for the order by itself. A nameless order reads "No name", the same fallback
 *  `orderBuyers.ts:groupBuyers` uses on the owner's own screen, so the two views agree. */
function orderLabel(buyer: string | null, number: string): { primary: string; secondary: string } {
  const trimmed = buyer?.trim() ?? ''
  return { primary: trimmed === '' ? 'No name' : trimmed, secondary: `#${number}` }
}

function aimAt(card: Sellable, order: OrderRef): PullTarget {
  return { box: card.box, index: card.index, capture_id: order.capture_id }
}

/** A search group with the copies sold on this screen taken out, or null when none is left. */
function stillHere(group: SearchGroup, gone: ReadonlySet<string>): SearchGroup | null {
  const here = group.copies.filter(
    (copy) => !GONE.has(copy.state) && !gone.has(copy.key) && !pooledCopy(copy),
  )
  if (here.length === 0) return null
  const justSold = group.copies.filter((copy) => !GONE.has(copy.state) && gone.has(copy.key)).length
  const pooledHere = group.copies.filter(
    (copy) => !GONE.has(copy.state) && !gone.has(copy.key) && pooledCopy(copy),
  ).length
  return {
    ...group,
    copies: here,
    on_hand: Math.max(0, group.on_hand - justSold - pooledHere),
  }
}

function inWalkOrder(cards: Sellable[]): Sellable[] {
  return [...cards].sort((a, b) => a.box - b.box || a.index - b.index)
}

/** A search group's copies in the order he walks the boxes: the first is the one he pulls. */
function copiesInWalkOrder(copies: SearchCopy[]): SearchCopy[] {
  return [...copies].sort(
    (a, b) => a.place.box - b.place.box || a.place.index - b.place.index,
  )
}

/** `in Box 6`, `in Boxes 4 and 6`, `in Boxes 4, 6 and 7` — where a set of copies is. */
function inBoxNumbers(numbers: number[]): string {
  const boxes = [...new Set(numbers)].sort((a, b) => a - b)
  if (boxes.length === 0) return ''
  if (boxes.length === 1) return `in Box ${boxes[0]}`
  const last = boxes[boxes.length - 1]
  return `in Boxes ${boxes.slice(0, -1).join(', ')} and ${last}`
}

function inBoxes(copies: SearchCopy[]): string {
  return inBoxNumbers(copies.map((copy) => copy.place.box))
}

function groupKey(group: SearchGroup, at: number): string {
  return `${at}:${group.sku ?? group.names.join('/')}`
}

function byBox(cards: Sellable[]): BoxGroup[] {
  const groups = new Map<number, BoxGroup>()
  for (const card of cards) {
    const held = groups.get(card.box)
    const name = card.where?.box_name ?? null
    if (held === undefined) groups.set(card.box, { box: card.box, name, cards: [card] })
    else {
      held.cards.push(card)
      if (held.name === null) held.name = name
    }
  }
  return [...groups.values()].sort((a, b) => a.box - b.box)
}

function greeting(): string {
  const hour = new Date().getHours()
  if (hour < 5) return 'Good evening'
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function count(n: number, one: string, many: string): string {
  return `${n.toLocaleString()} ${n === 1 ? one : many}`
}

/** A sort comparator over a number that may be null, WITHOUT the `Infinity - Infinity = NaN`
 *  trap: `a - b` reads as a comparator return only while both sides are real numbers. A null
 *  sorts after every real number (there is nothing to rank it against, so it is put last
 *  rather than guessed into first); two nulls compare equal, 0 — the correct "no opinion"
 *  answer a NaN silently was not. */
function compareNullable(a: number | null, b: number | null): number {
  if (a === null) return b === null ? 0 : 1
  if (b === null) return -1
  return a - b
}

/** `Box 3`, `Section 1`, `Card 17`, the figures ranked above the words. The text content of each
 *  part is the server's string character for character; only the weight changes. Each part is
 *  its own span (D218) so a narrow screen can stack them on purpose, breaking before `Card N`
 *  with the seam drawn by CSS (`.ff-place-elem:not(:first-child)::before`) rather than typed —
 *  which is also what lets it disappear on the stacked line without a dangling character left
 *  behind, `Fulfillment.css`'s narrow-width rule below. */
function PlaceText({ label }: { label: string }): ReactNode {
  /* THE PARTS COME FROM THE ONE LABEL READER (`position.ts:placePartsOf`): the server's label is
     `<box name>, Section <n>, Card <m>` since the owner's box-name ruling, and a box name may
     hold a comma, so it is read from the right end. A label of another shape is drawn whole. */
  const place = placePartsOf(label)
  const parts =
    place === null || place.section === null || place.card === null
      ? [label]
      : [place.box, `Section ${place.section}`, `Card ${place.card}`]
  return parts.map((part, at) => {
    const seam = part.lastIndexOf(' ')
    const value = seam < 1 ? '' : part.slice(seam + 1)
    const numeric = /^\d+$/.test(value)
    return (
      <span className="ff-place-elem" key={at}>
        <span className="ff-place-part">
          {numeric ? (
            <>
              <span className="ff-place-key">{part.slice(0, seam)} </span>
              <b className="ff-place-num">{value}</b>
            </>
          ) : (
            part
          )}
        </span>
      </span>
    )
  })
}

function CheckMark({ size = 24 }: { size?: number }) {
  return (
    <svg className="ff-check" viewBox="0 0 24 24" width={size} height={size} aria-hidden="true">
      <path
        d="M5 12.5l4.5 4.5L19 7"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/** One row of the list, the same on an order and in a box: the name, the place, a chevron. */
function CardRow({ card, onOpen }: { card: Sellable; onOpen: (card: Sellable) => void }) {
  return (
    <li>
      <button className="fulfillment-row ff-row" type="button" onClick={() => onOpen(card)}>
        <span className="fulfillment-name ff-row-name">{card.name}</span>
        <span className="fulfillment-place ff-row-place">
          <PlaceText label={card.place} />
        </span>
        <Icon name="chevronRight" size={26} className="ff-row-chev" />
      </button>
    </li>
  )
}

export function Fulfillment() {
  const [cards, setCards] = useState<Sellable[] | null>(null)
  const [unplaced, setUnplaced] = useState(0)
  const [loadFailed, setLoadFailed] = useState(false)
  const [reads, setReads] = useState(0)
  /** The open orders, raw off `GET /orders` — null until the first read answers. */
  const [orders, setOrders] = useState<OrderRow[] | null>(null)
  /** Real picks: every open order's own demand, resolved to every on-hand copy of each SKU
   *  (`POST /orders/walk-plan`, D212/D93 reaching this screen). Null until the first read
   *  answers, and left null (never an empty plan) while no order is open, so `owed` below
   *  stays `[]` without a `keys_required` refusal for a request this screen never needs to
   *  send. */
  const [plan, setPlan] = useState<WalkPlan | null>(null)
  const [ordersFailed, setOrdersFailed] = useState(false)
  const [allOwed, setAllOwed] = useState(false)

  const { query, setQuery, results, loading, failure } = useSearch()

  const [chosenKey, setChosenKey] = useState<string | null>(null)
  /** The one copy past its first step. The single-fill guard: only this copy shows the fill. */
  const [pulledKey, setPulledKey] = useState<string | null>(null)
  /** A request in flight. Guards instead of disabling — his controls never grey out. */
  const [busyKey, setBusyKey] = useState<string | null>(null)
  const [trouble, setTrouble] = useState<string | null>(null)
  const [sales, setSales] = useState<Sale[]>([])
  const [done, setDone] = useState<Done[]>([])
  /** Copies sold here, so search results fetched before the sale drop them too. */
  const [soldHere, setSoldHere] = useState<string[]>([])
  const [photoMissing, setPhotoMissing] = useState<string | null>(null)
  const [photoReady, setPhotoReady] = useState<string | null>(null)
  const [zoom, setZoom] = useState(false)
  /** The keyboard reference for this screen alone (UX-101: the app shell's own `?` sheet
   *  cannot open here — D5, no shell — and the dead `/` row it once listed for this group is
   *  removed at the source, `App.tsx`'s own `SHORTCUTS` table). */
  const [showKeys, setShowKeys] = useState(false)
  const [openBoxes, setOpenBoxes] = useState<number[]>([])
  /** Search groups whose "more copies" disclosure he has opened, by group key. */
  const [openMore, setOpenMore] = useState<string[]>([])
  const [now, setNow] = useState(() => Date.now())
  /** The photo he tapped, so focus comes back to it when the big photo closes. */
  const photoBtn = useRef<HTMLButtonElement>(null)
  /** The zoomed photo itself — on the kit's own layer stack (`kit/overlay.tsx`), so it and the
   *  "?" sheet's `Modal` share one Escape and one z-order even though neither is portalled from
   *  the other's own call. */
  const zoomOverlay = useRef<HTMLButtonElement>(null)

  const reread = useCallback(() => setReads((n) => n + 1), [])

  /* THIS IS THE FULFILLER'S WHOLE-STORE BROWSE (D5/D6) — every sellable card across every
   * box, for when he has no order in hand to walk instead. It is store-wide by design and
   * cannot be scoped to "the boxes an order names": there may be no order at all. D192/item 2
   * gave `#/inventory`, `#/` and the order-resolution paths their own lean, box-scoped or
   * top-K reads, but no cheap replacement exists yet for "every sellable card, lean shape" —
   * building one under this item's own budget would be the band-aid CLAUDE.md's "fix the
   * cause" rule refuses. Order resolution itself never touched `getInventory()` here: `POST
   * /orders/walk-plan` already resolves every open order's demand to real copies carrying
   * their own place and capture id (`owedFrom`, above), so this is the ONE call site left on
   * the full walk. DEBT27 is the named debt: the measured cost, why this cannot be
   * box-scoped, and the candidate primitive. */
  useEffect(() => {
    let livePage = true
    getInventory()
      .then((inventory) => {
        if (!livePage) return
        const offered = Object.entries(inventory.cards).filter(
          ([, card]) => forSale(card) && !pooled(card),
        )
        const placed: Sellable[] = []
        for (const [key, card] of offered) {
          const row = sellable(key, card)
          if (row !== null) placed.push(row)
        }
        setCards(inWalkOrder(placed))
        setUnplaced(offered.length - placed.length)
        setLoadFailed(false)
      })
      .catch(() => {
        if (!livePage) return
        setLoadFailed(true)
      })
    return () => {
      livePage = false
    }
  }, [reads])

  /* The orders, read beside the cards and from the same trigger, so a sale re-reads both.
   * TWO CALLS, ONE EFFECT: `GET /orders` answers no picks at all any more (2026-09-16, its own
   * doc comment) — 52% of its wall time was decorating a `place` for every candidate copy of
   * every unfulfilled order, most of them for a buyer nobody had opened. `POST
   * /orders/walk-plan` is the second tier that resolves real picks for exactly the keys named,
   * over EVERY on-hand copy of each SKU rather than one preselected pick each (D212/D93,
   * widened 2026-09-19) — the same primitive `#/orders`' own walk already reads
   * (`OrdersWalkPane.tsx`). Skipped with no open order, since the route refuses an empty
   * `keys` list by name (`keys_required`) rather than answering an empty plan. */
  useEffect(() => {
    let livePage = true
    void (async () => {
      try {
        const payload = await getOrders()
        if (!livePage) return
        setOrders(payload.orders)
        const openKeys = payload.orders.filter((order) => order.open).map((order) => order.key)
        const freshPlan = openKeys.length === 0 ? null : await walkPlan(openKeys)
        if (!livePage) return
        setPlan(freshPlan)
        setOrdersFailed(false)
      } catch {
        if (!livePage) return
        setOrdersFailed(true)
      }
    })()
    return () => {
      livePage = false
    }
  }, [reads])

  /* Each receipt leaves when its own window closes. */
  useEffect(() => {
    if (sales.length === 0) return
    const soonest = Math.min(...sales.map((sale) => sale.until))
    const timer = window.setTimeout(
      () =>
        setSales((held) => {
          const standing = held.filter((sale) => sale.until > Date.now())
          return standing.length === held.length ? held : standing
        }),
      Math.max(0, soonest - Date.now()) + 25,
    )
    return () => window.clearTimeout(timer)
  }, [sales])

  /* The clock he can read, ticking while any receipt stands. */
  useEffect(() => {
    if (sales.length === 0) return
    setNow(Date.now())
    const timer = window.setInterval(() => setNow(Date.now()), 500)
    return () => window.clearInterval(timer)
  }, [sales.length])

  useEffect(() => {
    if (!zoom) return
    /* THE BUTTON IS CAPTURED HERE, NOT READ IN THE CLEANUP. By the time the cleanup runs the
       ref may point at a different card's photograph — the sale advances the walk while the
       zoom is open — and focus would land on whatever is in that slot now. This is the node
       he tapped. */
    const opener = photoBtn.current
    return () => {
      /* The page is hidden under the big photo, which drops focus; hand it back to the photo
         he tapped. Null once the card has left the screen, and then there is nothing to do. */
      opener?.focus({ preventScroll: true })
    }
  }, [zoom])

  /* ON THE KIT'S OWN LAYER STACK (`kit/overlay.tsx`), the same one the "?" sheet's `Modal`
   * joins — so whichever of the two opened last is the one Escape closes and the one painted
   * on top, and Escape pressed again then reaches the other. `trap: false`: the zoomed photo's
   * only control is itself (closing it, on click or Escape), so nothing needs to cycle by Tab. */
  useOverlayLayer(zoomOverlay, { active: zoom, onEscape: () => setZoom(false), trap: false })

  /* THE ONE BINDING THIS SCREEN ANSWERS TO ON ITS OWN, no shell to carry it (D5). `?` opens
   * the small reference below; `isEditableTarget` yields to typing, `App.tsx`'s own rule for
   * the same key. Escape closing the sheet itself is the kit Modal's own job now (its capture
   * listener stops the key reaching here at all while the sheet is the top layer), which is
   * also why this no longer needs `showKeys` in its own deps. */
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === '?' && !event.repeat && !isEditableTarget(event.target)) {
        setShowKeys((held) => !held)
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  const soldSet = useMemo(() => new Set(soldHere), [soldHere])

  /** Every open order, by key — `pipeline/walkplan.py:demand`'s own lookup, restated for the
   *  order's `source` (`OrderRef.source`, which a `WalkPlanRef` does not carry). */
  const ordersByKey = useMemo(() => new Map((orders ?? []).map((order) => [order.key, order])), [orders])
  const openOrderKeys = useMemo(
    () => (orders ?? []).filter((order) => order.open).map((order) => order.key),
    [orders],
  )

  /** The open orders' own demand, one card per SKU still owed — never a preselected copy
   *  (`owedFrom`'s own comment). `stillOwed` takes this session's own sales out before he sees
   *  them again, the same optimism `found` below already gives search results. Sorted by the
   *  PLACE of each card's own first copy — box, then section, then card — so the list follows
   *  the walk rather than `pipeline/walkplan.py:plan`'s own order (count descending, then SKU,
   *  never a position at all: `Take` carries no address). The solver is untouched; this is a
   *  client-side sort over its answer, for a screen with no drawer-by-drawer stop concept of
   *  its own. */
  const owed = useMemo(() => {
    if (plan === null) return []
    const items: Owed[] = []
    for (const item of owedFrom(plan)) {
      const here = stillOwed(item, soldSet)
      if (here !== null) items.push(here)
    }
    return [...items].sort((a, b) => {
      const pa = a.copies[0]?.place
      const pb = b.copies[0]?.place
      if (pa === undefined || pb === undefined) return 0
      return (
        pa.box - pb.box ||
        compareNullable(pa.section, pb.section) ||
        compareNullable(pa.card, pb.card)
      )
    })
  }, [plan, soldSet])

  /** How many copies to pick, across every card still owed — the "Today" figure. */
  const totalWanted = useMemo(() => owed.reduce((sum, item) => sum + item.wanted, 0), [owed])
  /** How many copies the open orders want that the store cannot place at all —
   *  `plan.shortfall`'s own count, the reason the empty state may never claim "nothing waits"
   *  while an order is open and unfillable (the owner's own review finding, UX-001). */
  const shortfallCount = useMemo(
    () => (plan?.shortfall ?? []).reduce((sum, short) => sum + short.short, 0),
    [plan],
  )

  /** Every copy an owed card names, as the full `Sellable` a sale through the order needs —
   *  keyed by copy so a card reached through a box or a search is ALSO sold through the order
   *  that is waiting for it (`claim`, below). The order picked for a copy is `item.refs[0]`,
   *  the oldest order still owing the SKU (`pipeline/walkplan.py:demand`'s own order) —
   *  re-read after every sale, so a fulfilled order drops off its own next `for` list rather
   *  than needing a per-press tally here (`OrdersWalkPane.tsx:pickOrderFor` solves the same
   *  problem for a live pass over several stops; this screen re-fetches instead, because one
   *  sale here is one request-and-reread, never a run of several before the next read). */
  const orderByKey = useMemo(() => {
    const map = new Map<string, Sellable>()
    for (const item of owed) {
      let ref: WalkPlanRef | undefined
      let row: OrderRow | undefined
      for (const candidate of item.refs) {
        const found = ordersByKey.get(candidate.key)
        if (found !== undefined) {
          ref = candidate
          row = found
          break
        }
      }
      if (ref === undefined || row === undefined) continue
      for (const copy of item.copies) {
        if (copy.capture_id === null || GONE.has(copy.state) || copy.place.located === false) continue
        map.set(copy.key, {
          key: copy.key,
          box: copy.place.box,
          index: copy.place.index,
          place: copy.place.label ?? '',
          name: item.name,
          about: item.about,
          where: copy.place,
          cid: copy.cid,
          order: {
            orderKey: ref.key,
            source: row.source,
            number: ref.number,
            buyer: ref.buyer,
            sku: item.sku,
            capture_id: copy.capture_id,
          },
        })
      }
    }
    return map
  }, [owed, ordersByKey])

  /** A real card from THIS store for the search field's example, rather than a name from a
   *  game that may hold none of this store's cards (D21 — game is a per-card claim, not a
   *  fixed catalog). Prefers what he is already holding — an owed card — so the hint matches
   *  the card he is most likely to try next; falls back to any named card on hand, and to a
   *  generic noun when the store has named nothing yet. */
  const exampleCardName = useMemo(() => {
    const owedNamed = owed.find((item) => item.name !== NO_NAME)?.name ?? null
    if (owedNamed !== null) return owedNamed
    return (cards ?? []).find((card) => card.name !== NO_NAME)?.name ?? null
  }, [owed, cards])

  /** The order's own copy of a card wherever one exists, so a card reached through a box or a
   *  search is still sold through the order that is waiting for it. */
  const claim = useCallback(
    (card: Sellable): Sellable => orderByKey.get(card.key) ?? card,
    [orderByKey],
  )

  const chosen = useMemo(() => {
    if (chosenKey === null) return null
    return orderByKey.get(chosenKey) ?? cards?.find((card) => card.key === chosenKey) ?? null
  }, [chosenKey, orderByKey, cards])
  const boxes = useMemo(() => (cards === null ? [] : byBox(cards)), [cards])

  const found = useMemo(() => {
    if (results === null) return null
    const groups: SearchGroup[] = []
    let pooledAway = false
    for (const group of results.groups) {
      if (group.copies.some((copy) => pooledCopy(copy) && !GONE.has(copy.state))) {
        pooledAway = true
      }
      const here = stillHere(group, soldSet)
      if (here !== null) groups.push(here)
    }
    return { total: results.groups.length, groups, pooledAway }
  }, [results, soldSet])

  const remember = useCallback((sale: Omit<Sale, 'until'>) => {
    setSales((held) => [
      { ...sale, until: Date.now() + UNDO_WINDOW_MS },
      ...held.filter((standing) => standing.card.key !== sale.card.key),
    ])
  }, [])

  const openCard = useCallback((card: Sellable) => {
    setChosenKey(card.key)
    setPulledKey(null)
    setTrouble(null)
    setPhotoReady(null)
  }, [])

  const drop = useCallback((card: Sellable) => {
    setCards((prev) => (prev === null ? prev : prev.filter((row) => row.key !== card.key)))
    setSoldHere((held) => (held.includes(card.key) ? held : [...held, card.key]))
    setChosenKey(null)
    setPulledKey(null)
    setZoom(false)
  }, [])

  const doSell = useCallback(
    async (card: Sellable) => {
      if (busyKey !== null) return
      setBusyKey(card.key)
      setTrouble(null)
      try {
        let reversible: boolean
        if (card.order === null) {
          reversible = canTakeBack(await markSold(card.box, card.index))
        } else {
          const pulled = await pullCopy(card.order, [aimAt(card, card.order)])
          reversible = pulled.sales.every(canTakeBack)
        }
        drop(card)
        remember({
          card,
          said: 'Marked sold.',
          canUndo: reversible,
          note: reversible
            ? null
            : 'You cannot take this one back here. Ask for help if it is wrong.',
        })
        setDone((held) => [
          { key: card.key, name: card.name, place: card.place, order: card.order?.number ?? null },
          ...held.filter((row) => row.key !== card.key),
        ])
        reread()
      } catch (err) {
        const code = refusalCode(err)
        if (code === ALREADY_SOLD || code === ALREADY_PULLED) {
          drop(card)
          remember({
            card,
            said: 'Already sold.',
            canUndo: false,
            note: 'Somebody else sold this card, so it has come off your list.',
          })
          reread()
          return
        }
        if (PULL_STALE.has(code)) {
          setTrouble('The list has changed since it was opened. Go back to the cards and try again.')
          reread()
          return
        }
        setTrouble('Nothing was saved. Press Mark it sold again.')
      } finally {
        setBusyKey(null)
      }
    },
    [busyKey, drop, remember, reread],
  )

  const doUndo = useCallback(
    async (card: Sellable) => {
      if (busyKey !== null) return
      setBusyKey(card.key)
      setTrouble(null)
      try {
        if (card.order === null) {
          await unsell(card.box, card.index)
        } else {
          try {
            await undoPull([aimAt(card, card.order)])
          } catch (err) {
            /* The ledger never held this pull, so the sale is put back the plain way. */
            if (refusalCode(err) !== PULL_NOT_RECORDED) throw err
            await unsell(card.box, card.index)
          }
        }
        setCards((prev) =>
          prev === null ? prev : inWalkOrder([...prev.filter((row) => row.key !== card.key), card]),
        )
        setSoldHere((held) => held.filter((key) => key !== card.key))
        setSales((held) => held.filter((standing) => standing.card.key !== card.key))
        setDone((held) => held.filter((row) => row.key !== card.key))
        reread()
      } catch (err) {
        const dead = refusalCode(err) === NO_ORIGIN
        setSales((held) =>
          held.map((standing) =>
            standing.card.key !== card.key
              ? standing
              : {
                  ...standing,
                  canUndo: dead ? false : standing.canUndo,
                  note: dead
                    ? 'This card stays sold. Ask for help to put it back.'
                    : 'The card did not come back. Press Undo again.',
                },
          ),
        )
      } finally {
        setBusyKey(null)
      }
    },
    [busyKey, reread],
  )

  const doSellCopy = useCallback(
    (group: SearchGroup, copy: SearchCopy) => {
      void doSell(claim(asSellable(group, copy)))
    },
    [doSell, claim],
  )

  /* The two steps never share a spot: after "Pull" the button's footprint becomes a sentence
   * and "Mark it sold" arrives BELOW it, so the second tap of a double-tap lands on text. */
  const actionFor = useCallback(
    (group: SearchGroup, copy: SearchCopy): ReactNode => {
      if (pulledKey !== copy.key) {
        return (
          <button
            className="ff-step"
            type="button"
            aria-label={`Pull ${copy.place.label === null ? group.names.join(' / ') : sayPlace(copy.place.label)}`}
            onClick={() => {
              setPulledKey(copy.key)
              setTrouble(null)
            }}
          >
            <Icon name="hand" size={24} />
            Pull this card
          </button>
        )
      }
      return (
        <>
          <p className="fulfillment-pulled ff-pulled">
            <span className="ff-pulled-icon">
              <CheckMark size={22} />
            </span>
            Pulled.
          </p>
          {trouble === null ? null : <p className="fulfillment-say ff-trouble">{trouble}</p>}
          <div className="ff-step2">
            <PullConfirm label="Mark it sold" onConfirm={() => doSellCopy(group, copy)} />
          </div>
        </>
      )
    },
    [pulledKey, trouble, doSellCopy],
  )

  const leaveCard = () => {
    setChosenKey(null)
    setPulledKey(null)
    setTrouble(null)
    setZoom(false)
    reread()
  }

  const tryAgain = () => {
    setLoadFailed(false)
    setOrdersFailed(false)
    reread()
  }

  const secondsLeft = (sale: Sale): number => Math.max(0, Math.ceil((sale.until - now) / 1000))

  /* ---- the receipt sheet ------------------------------------------------------------- */
  const sheet =
    sales.length === 0 ? null : (
      <div className="ff-sheet" role="status" aria-live="polite">
        {/* The newest receipt is drawn in full; the ones under it fold to a line each, so the
            sheet cannot stack past the screen while a run of sales is still inside its window. */}
        {sales.map((sale, at) => (
          <div
            className={`fulfillment-panel ff-receipt${at === 0 ? '' : ' ff-receipt-compact'}`}
            key={`${sale.card.key}:${sale.until}`}
          >
            <span className="ff-receipt-icon" data-tone={sale.canUndo ? 'ok' : 'note'}>
              {sale.canUndo ? <CheckMark /> : <Icon name="info" size={24} />}
            </span>
            <div className="ff-receipt-text">
              <p className="fulfillment-say ff-receipt-said">{sale.said}</p>
              <p className="fulfillment-say ff-receipt-what">
                <span className="ff-receipt-name">{sale.card.name}</span>
                {/* D218: found beyond the reader's own list — `sale.card.place` is the
                    server's raw label off a variable, so the reader's plain-string scan never
                    saw the dot in it. Same string, same register; the seam is CSS now. */}
                <span className="ff-receipt-place">
                  {placeWordsOf(sale.card.place).map((part, at) => (
                    <span key={at}>{part}</span>
                  ))}
                </span>
                {sale.card.order === null ? null : (
                  <span className="ff-receipt-order">Order {sale.card.order.number}</span>
                )}
              </p>
              {sale.note === null ? null : (
                <p className="fulfillment-say ff-receipt-note">{sale.note}</p>
              )}
            </div>
            {!sale.canUndo ? null : (
              <button
                className="ff-undo"
                type="button"
                aria-label={`Undo ${sayPlace(sale.card.place)}`}
                onClick={() => void doUndo(sale.card)}
              >
                <Icon name="undo" size={22} />
                Undo
              </button>
            )}
            {!sale.canUndo ? null : (
              <div className="ff-receipt-clock" aria-hidden="true">
                <span
                  className="ff-receipt-bar"
                  style={{ ['--ff-window' as string]: `${UNDO_WINDOW_MS}ms` }}
                />
                <span className="ff-receipt-secs">{secondsLeft(sale)} s</span>
              </div>
            )}
          </div>
        ))}
      </div>
    )

  /* ---- the list may have moved under him -------------------------------------------- */
  const stale =
    (loadFailed || ordersFailed) && cards !== null ? (
      <div className="ff-notice">
        <Icon name="alert" size={26} className="ff-notice-icon" />
        <p className="fulfillment-say">
          These cards may have changed since they were last checked. Try again.
        </p>
        <button className="ff-quiet" type="button" onClick={tryAgain}>
          <Icon name="refresh" size={22} />
          Try again
        </button>
      </div>
    ) : null

  const header = (
    <header className="ff-head">
      <Logo size={44} className="ff-mark" />
      <div className="ff-head-text">
        <p className="fulfillment-say ff-greeting">{greeting()}.</p>
        <h1 className="fulfillment-title ff-title">Cards to pull</h1>
      </div>
    </header>
  )

  let body: ReactNode
  let wide = false

  if (cards === null && loadFailed) {
    body = (
      <>
        {header}
        <div className="ff-empty">
          <span className="bn-empty-art bn-empty-art-lg">
            <Icon name="alert" size={30} />
          </span>
          <p className="fulfillment-say ff-empty-title">The cards did not load. Try again.</p>
          <button className="ff-quiet" type="button" onClick={tryAgain}>
            <Icon name="refresh" size={22} />
            Try again
          </button>
        </div>
      </>
    )
  } else if (cards === null) {
    body = (
      <>
        {header}
        <div className="ff-loading" aria-busy="true">
          <p className="fulfillment-say ff-loading-say">Getting the cards.</p>
          <span className="ff-skel ff-skel-today" />
          <span className="ff-skel ff-skel-search" />
          <span className="ff-skel ff-skel-row" />
          <span className="ff-skel ff-skel-row" />
          <span className="ff-skel ff-skel-row" />
        </div>
      </>
    )
  } else if (chosen !== null) {
    wide = true
    const between = placeSentence(chosen.where ?? undefined)
    const showBar = chosen.where !== null && chosen.where.located !== false
    const boxName = chosen.where?.box_name ?? null
    const missing = photoMissing === chosen.key
    /* BY NAME WHERE THE ROW HAS ONE (D172) — the inventory and search paths do, an order
       pick does not; see `Sellable.cid`. He is looking at a photograph to decide whether the
       card in his hand is the card on the screen, so it had better be this card's. */
    const src = photoUrl(chosen.box, chosen.index, chosen.cid)
    const forOrder = chosen.order

    body = (
      <>
        <div className="ff-nav">
          <button className="ff-back" type="button" onClick={leaveCard}>
            <Icon name="arrowLeft" size={24} />
            Back to the cards
          </button>
        </div>

        <article className="ff-card">
          <div className="ff-photo-wrap">
            {missing ? (
              <div className="bn-empty-well">
                <Icon name="image" size={40} />
                <p className="fulfillment-say">
                  The photo is missing. The card is still in the place shown here.
                </p>
              </div>
            ) : (
              <>
                <button
                  ref={photoBtn}
                  className="ff-photo-btn"
                  type="button"
                  aria-label="Show the photo bigger"
                  onClick={() => setZoom(true)}
                >
                  {photoReady === chosen.key ? null : (
                    <span className="ff-photo-skel" aria-hidden="true" />
                  )}
                  <img
                    key={chosen.key}
                    className="fulfillment-photo"
                    data-ready={photoReady === chosen.key ? 'true' : 'false'}
                    src={src}
                    alt={`The card in ${sayPlace(chosen.place)}`}
                    onLoad={() => setPhotoReady(chosen.key)}
                    onError={() => setPhotoMissing(chosen.key)}
                  />
                </button>
                <p className="fulfillment-say ff-photo-hint">
                  <Icon name="search" size={20} />
                  Tap the photo to see it bigger.
                </p>
              </>
            )}
          </div>

          {/* Name, place and the button share a column beside the photograph on a wide
              screen; on a phone `display: contents` lets them take their reading order
              around it — name, photo, place, button. */}
          <div className="ff-card-side">
          <header className="ff-card-head">
            {forOrder === null ? null : (
              <p className="fulfillment-say ff-card-eyebrow">
                <span className="ff-card-order">
                  For <b>{orderLabel(forOrder.buyer, forOrder.number).primary}</b>{' '}
                  <span className="ff-card-order-id">
                    {orderLabel(forOrder.buyer, forOrder.number).secondary}
                  </span>
                </span>
              </p>
            )}
            <h2 className="fulfillment-name ff-card-name">{chosen.name}</h2>
            {chosen.about === null ? null : (
              <p className="fulfillment-say ff-card-about">
                {chosen.about.map((part, at) => (
                  <span key={at}>{part}</span>
                ))}
              </p>
            )}
          </header>

          <section className="ff-where" aria-label="Where to find it">
            <p className="fulfillment-say ff-where-label">
              <Icon name="pin" size={22} />
              Where to find it
            </p>
            <p className="fulfillment-place fulfillment-place-large ff-place">
              <PlaceText label={chosen.place} />
            </p>
            {boxName === null ? null : (
              <p className="fulfillment-say ff-where-boxname">
                The box is labelled <b>{boxName}</b>.
              </p>
            )}
            {!showBar || chosen.where === null ? null : (
              <div className="ff-where-bar">
                <PositionBar place={chosen.where} persona="fulfiller" />
              </div>
            )}
            {between === null ? null : (
              <p className="fulfillment-say ff-where-between">{between}</p>
            )}
          </section>

          <div className="fulfillment-action ff-action">
            {trouble === null ? null : <p className="fulfillment-say ff-trouble">{trouble}</p>}
            {pulledKey === chosen.key ? (
              <>
                <p className="fulfillment-pulled ff-pulled">
                  <span className="ff-pulled-icon">
                    <CheckMark size={22} />
                  </span>
                  Pulled.
                </p>
                <div className="ff-step2">
                  <PullConfirm label="Mark it sold" onConfirm={() => void doSell(chosen)} />
                </div>
              </>
            ) : (
              /* The quiet first step, the same button a search result offers: the solid fill
                 is kept for the sale, which is the press that writes. */
              <button className="ff-step" type="button" onClick={() => setPulledKey(chosen.key)}>
                <Icon name="hand" size={24} />
                Pull this card
              </button>
            )}
          </div>
          </div>
        </article>
      </>
    )
  } else {
    const hunting = query.trim() !== ''

    let hits: ReactNode
    if (loading) {
      hits = (
        <div className="ff-loading" aria-busy="true">
          <p className="fulfillment-say ff-loading-say">Looking for that card.</p>
          <span className="ff-skel ff-skel-copy" />
        </div>
      )
    } else if (failure !== null) {
      /* UX-049: "Type the name again" is a remedy that cannot work — the search FAILED, so
         retyping asks the same broken thing again. The one step that does something is
         already on screen (the clear button beside the field), so the sentence says what it
         does rather than a step of its own. */
      hits = (
        <p className="fulfillment-say ff-say">
          The search could not run right now. Clear it to look through a box instead.
        </p>
      )
    } else if (found === null) {
      hits = null
    } else if (found.total === 0) {
      hits = <p className="fulfillment-say ff-say">No card here has that name. Check the spelling.</p>
    } else if (found.groups.length === 0 && found.pooledAway) {
      hits = (
        <p className="fulfillment-say ff-say">
          That card is not kept in the boxes, so there is nothing to pull.
        </p>
      )
    } else if (found.groups.length === 0) {
      hits = (
        <p className="fulfillment-say ff-say">
          Every copy of that card is sold. There is nothing to pull.
        </p>
      )
    } else {
      /* One card at a time: the first copy in walk order is the one he pulls, drawn in full.
         The rest — the store's common cards carry a dozen or more — fold under a disclosure
         in the box register, so a search never draws nineteen photographs down the page. */
      hits = found.groups.map((group, at) => {
        const key = groupKey(group, at)
        const [first, ...rest] = copiesInWalkOrder(group.copies)
        const open = openMore.includes(key)
        return (
          <div className="ff-found" key={key}>
            <CardLocations
              group={{ ...group, copies: first === undefined ? [] : [first] }}
              persona="fulfiller"
              onSell={(copy) => doSellCopy(group, copy)}
              busyKey={busyKey}
              soldKeys={soldSet}
              renderAction={(copy) => actionFor(group, copy)}
            />
            {rest.length === 0 ? null : (
              <div className="ff-more">
                <button
                  className="ff-more-head"
                  type="button"
                  aria-expanded={open}
                  onClick={() =>
                    setOpenMore((held) =>
                      held.includes(key) ? held.filter((k) => k !== key) : [...held, key],
                    )
                  }
                >
                  <span className="ff-more-num" aria-hidden="true">
                    {rest.length}
                  </span>
                  <span className="ff-more-text">
                    <span className="fulfillment-say ff-more-title">
                      {rest.length} more {rest.length === 1 ? 'copy' : 'copies'} of this card
                    </span>
                    <span className="fulfillment-say ff-more-where">{inBoxes(rest)}</span>
                  </span>
                  <Icon name="chevronDown" size={26} className="ff-more-chev" />
                </button>
                {!open ? null : (
                  <div className="ff-more-body">
                    <CardLocations
                      group={{ ...group, copies: rest }}
                      persona="fulfiller"
                      onSell={(copy) => doSellCopy(group, copy)}
                      busyKey={busyKey}
                      soldKeys={soldSet}
                      renderAction={(copy) => actionFor(group, copy)}
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })
    }

    /* ---- today: what the orders still owe, and whether it can all be found ------------- */
    let today: ReactNode
    if (orders === null) {
      today = ordersFailed ? null : (
        <div className="ff-loading" aria-busy="true">
          <span className="ff-skel ff-skel-today" />
        </div>
      )
    } else if (openOrderKeys.length === 0) {
      /* No order is open at all — the ONE state allowed to say "nothing waits" (the owner's
         own review finding, UX-001: a green "nothing waits" while orders are open and unread
         is the defect this screen had). */
      today = (
        <p className="fulfillment-say ff-today-none">
          <span className="bn-icon-badge bn-icon-badge--ok">
            <CheckMark size={22} />
          </span>
          No orders are waiting for a card right now. You can still find any card by name.
        </p>
      )
    } else if (owed.length === 0) {
      /* Orders are open, but not one copy any of them wants is on hand — never drawn as
         "nothing waits", which would read as caught up rather than stuck. */
      today = (
        <p className="fulfillment-say ff-today-none" data-tone="warn">
          <span className="bn-icon-badge bn-icon-badge--warn">
            <Icon name="alert" size={22} />
          </span>
          {count(openOrderKeys.length, 'order is', 'orders are')} waiting, but
          {' '}
          {count(shortfallCount, 'copy', 'copies')} {shortfallCount === 1 ? 'is' : 'are'} not in
          the boxes. Ask for help finding {shortfallCount === 1 ? 'it' : 'them'}.
        </p>
      )
    } else {
      today = (
        <section className="ff-today" aria-label="Today">
          <div className="ff-today-text">
            <p className="ff-today-figure">
              <b className="ff-today-num">{totalWanted.toLocaleString()}</b>{' '}
              <span className="ff-today-words">
                {totalWanted === 1 ? 'copy to pick' : 'copies to pick'}
              </span>
            </p>
            <p className="fulfillment-say ff-today-say">
              For {count(openOrderKeys.length, 'order', 'orders')}, listed below with every
              copy the store holds.
            </p>
            {shortfallCount === 0 ? null : (
              <p className="fulfillment-say ff-today-warn">
                <Icon name="alert" size={18} className="ff-today-warn-icon" />
                {count(shortfallCount, 'more copy', 'more copies')}{' '}
                {shortfallCount === 1 ? 'is' : 'are'} not in the boxes. Ask for help with{' '}
                {shortfallCount === 1 ? 'it' : 'those'}.
              </p>
            )}
          </div>
        </section>
      )
    }

    const shownOwed = allOwed ? owed : owed.slice(0, SHOWN_OWED)
    const hiddenOwed = owed.length - shownOwed.length

    body = (
      <>
        {header}

        {today}

        <div className="ff-search" data-clear={hunting ? 'true' : 'false'}>
          {/* No autoFocus: a software keyboard would cover the first thing he reads. */}
          <SearchField
            value={query}
            onChange={setQuery}
            persona="fulfiller"
            placeholder={
              exampleCardName === null ? "For example, a card's name" : `For example, ${exampleCardName}`
            }
          />
          {hunting ? (
            <button
              className="ff-clear"
              type="button"
              aria-label="Show every card"
              onClick={() => {
                setQuery('')
                setPulledKey(null)
                setTrouble(null)
              }}
            >
              <Icon name="x" size={28} />
            </button>
          ) : null}
        </div>

        {hunting ? (
          <section className="fulfillment-results ff-results" aria-live="polite">
            {hits}
          </section>
        ) : (
          <>
            {trouble === null ? null : <p className="fulfillment-say ff-trouble">{trouble}</p>}

            {done.length === 0 ? null : (
              <section className="ff-done" aria-label="Pulled today">
                <h2 className="ff-h2">
                  <span className="ff-h2-icon ff-h2-icon-ok">
                    <CheckMark size={18} />
                  </span>
                  Pulled today
                </h2>
                <ul className="ff-done-list">
                  {done.map((row) => (
                    <li className="ff-done-row" key={row.key}>
                      <span className="fulfillment-say ff-done-name">{row.name}</span>
                      {/* D218: found beyond the reader's own list — `row.place` is the
                          server's raw label off a variable, so the reader's plain-string scan
                          never saw the dot in it. Same string, same register; the seam is CSS
                          now. */}
                      <span className="fulfillment-say ff-done-place">
                        {placeWordsOf(row.place).map((part, at) => (
                          <span key={at}>{part}</span>
                        ))}
                      </span>
                      {row.order === null ? null : (
                        <span className="fulfillment-say ff-done-order">Order {row.order}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {owed.length === 0 ? null : (
              <section className="ff-owed" aria-label="Cards to pick">
                <h2 className="ff-h2">
                  <span className="ff-h2-icon">
                    <Icon name="cart" size={18} />
                  </span>
                  Cards to pick
                </h2>
                <div className="ff-found ff-owed-list">
                  {shownOwed.map((item, at) => {
                    const group = owedGroup(item)
                    return (
                      <div
                        className="ff-owed-card"
                        key={item.key}
                        style={{ animationDelay: `${Math.min(at, 8) * 40}ms` }}
                      >
                        <p className="fulfillment-say ff-owed-pick">
                          <b className="ff-owed-pick-num">Pick {item.wanted}</b>
                          {item.refs.length < 2 ? null : (
                            <span className="ff-owed-pick-for">
                              for {count(item.refs.length, 'order', 'orders')}
                            </span>
                          )}
                        </p>
                        <CardLocations
                          group={group}
                          persona="fulfiller"
                          preserveOrder
                          onSell={(copy) => doSellCopy(group, copy)}
                          busyKey={busyKey}
                          soldKeys={soldSet}
                          listedAt={item.liveAsOf}
                          renderAction={(copy) => actionFor(group, copy)}
                        />
                      </div>
                    )
                  })}
                </div>
                {hiddenOwed === 0 && !allOwed ? null : (
                  <button
                    className="ff-quiet ff-orders-more"
                    type="button"
                    aria-expanded={allOwed}
                    onClick={() => setAllOwed((held) => !held)}
                  >
                    <Icon name={allOwed ? 'chevronUp' : 'chevronDown'} size={22} />
                    {allOwed
                      ? 'Show fewer cards'
                      : `Show the other ${count(hiddenOwed, 'card', 'cards')}`}
                  </button>
                )}
              </section>
            )}

            {cards.length === 0 ? (
              <div className="ff-empty">
                <span className="bn-empty-art bn-empty-art-lg">
                  <Icon name="box" size={30} />
                </span>
                <p className="fulfillment-say ff-empty-title">
                  No cards are for sale right now. There is nothing to pull.
                </p>
              </div>
            ) : (
              <section className="ff-browse" aria-label="Look through a box">
                <h2 className="ff-h2">
                  <span className="ff-h2-icon">
                    <Icon name="box" size={18} />
                  </span>
                  Or look through a box
                </h2>
                <p className="fulfillment-say ff-browse-lede">
                  {count(cards.length, 'card is', 'cards are')} in {count(boxes.length, 'box', 'boxes')}
                  . Tap a box to see what is in it.
                </p>
                <div className="ff-boxes">
                  {boxes.map((group, at) => {
                    const open = openBoxes.includes(group.box)
                    return (
                      <div className="ff-box" key={group.box} style={{ animationDelay: `${at * 40}ms` }}>
                        <button
                          className="ff-box-head"
                          type="button"
                          aria-expanded={open}
                          onClick={() =>
                            setOpenBoxes((held) =>
                              held.includes(group.box)
                                ? held.filter((box) => box !== group.box)
                                : [...held, group.box],
                            )
                          }
                        >
                          <span className="ff-box-num" aria-hidden="true">
                            {group.box}
                          </span>
                          <span className="ff-box-text">
                            <span className="fulfillment-say ff-box-name">
                              Box {group.box}
                              {group.name === null ? null : <span className="ff-box-namepart">{group.name}</span>}
                            </span>
                            <span className="fulfillment-say ff-box-count">
                              {count(group.cards.length, 'card', 'cards')}
                            </span>
                          </span>
                          <Icon name="chevronDown" size={26} className="ff-box-chev" />
                        </button>
                        {!open ? null : (
                          <div className="ff-box-body">
                            <ul className="fulfillment-list ff-list">
                              {group.cards.slice(0, SHOWN_PER_BOX).map((card) => (
                                <CardRow card={card} onOpen={openCard} key={card.key} />
                              ))}
                            </ul>
                            {group.cards.length <= SHOWN_PER_BOX ? null : (
                              <p className="fulfillment-say ff-say">
                                {`Showing the first ${SHOWN_PER_BOX} of ${group.cards.length}. Search above to find the rest.`}
                              </p>
                            )}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </section>
            )}

            {unplaced === 0 ? null : (
              <p className="fulfillment-say ff-say ff-unplaced">
                {unplaced === 1
                  ? '1 card for sale is not shown here, because its place is missing. Ask for help with that one.'
                  : `${unplaced} cards for sale are not shown here, because their places are missing. Ask for help with those.`}
              </p>
            )}
          </>
        )}
      </>
    )
  }

  /* A sibling of the column, never inside it: the column animates in with a transform, and a
   * transformed ancestor would pin this fixed overlay to the column instead of the screen. */
  const bigPhoto =
    zoom && chosen !== null && photoMissing !== chosen.key ? (
      <button
        ref={zoomOverlay}
        className="ff-zoom"
        type="button"
        aria-label="Close the big photo"
        /* The page under it is hidden, so this is the one thing left to focus. */
        autoFocus
        onClick={() => setZoom(false)}
      >
        <img
          className="ff-zoom-img"
          /* The same address the confirm frame drew, so the big view is a cache hit. */
          src={photoUrl(chosen.box, chosen.index, chosen.cid)}
          alt={`The card in ${sayPlace(chosen.place)}, bigger`}
        />
        <span className="fulfillment-say ff-zoom-hint">Tap anywhere to go back.</span>
      </button>
    ) : null

  /* The one thing this screen answers to on its own — UX-101, "the key works for the
     Fulfiller, or it leaves the list". Built on the kit's own `Modal` (`kit/overlay.tsx`) —
     `App.tsx`'s own `.app-keys` is a hand-rolled twin of the same pair, scaled up for its own
     many-screen table, kept outside the kit because it is the shell's. This screen has none
     (D5), so this is its own sheet, over the kit's focus trap, layer stack, and return-focus;
     no route out, closed by Esc, the scrim, or its own Close. THE KEY CAP IS NOT `.bn-kbd` —
     that chip is 10px, sized for the owner's dense reference sheet, and this screen's own
     floor table reaches it too (`.ff-keys-key`, Fulfillment.css). */
  const keysSheet = (
    <Modal open={showKeys} onClose={() => setShowKeys(false)} title="Keyboard shortcuts" className="ff-keys">
      <ul className="ff-keys-list">
        <li>
          <kbd className="ff-keys-key">Esc</kbd>
          <span className="fulfillment-say">Close the enlarged photograph</span>
        </li>
        <li>
          <kbd className="ff-keys-key">?</kbd>
          <span className="fulfillment-say">Open or close this list</span>
        </li>
      </ul>
    </Modal>
  )

  return (
    <main
      className={`fulfillment ff${sales.length === 0 ? '' : ' ff-has-sheet'}`}
      data-view={chosen === null ? 'home' : 'card'}
      data-zoom={bigPhoto === null ? 'false' : 'true'}
    >
      <div className="ff-glow" aria-hidden="true" />
      <div className="ff-column" data-wide={wide ? 'true' : 'false'}>
        {stale}
        {body}
      </div>
      {sheet}
      {bigPhoto}
      {keysSheet}
    </main>
  )
}
