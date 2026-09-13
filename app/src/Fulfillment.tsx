import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import type {
  InventoryCard,
  OrderRow,
  OrdersPayload,
  PickRow,
  Place,
  PullTarget,
  ResolvedLine,
  SaleResult,
  SearchCopy,
  SearchGroup,
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
} from './server'
import { PullConfirm } from './PullConfirm'
import { SearchField } from './SearchField'
import { CardLocations } from './CardLocations'
import { PositionBar } from './PositionBar'
import { Icon, Logo } from './kit'
import { useSearch } from './useSearch'
import './Fulfillment.css'

/* The Fulfiller's screen — D5's second persona: a retired, non-technical relative who fills
 * orders from his own device. This route is the whole product for him, so it has no nav, no
 * jargon and nothing destructive, and every floor in docs/DESIGN.md's Fulfillment table (20px
 * body, 32px place, 44px targets 12px apart, 7:1, undo >= 10s) is kept on merit here.
 *
 * Shape: the orders first. `GET /orders` resolves every open order to the copies that fill it
 * (D69), and those copies ARE his list — order by order, each order's cards in the order he
 * walks the boxes — with search as the second way in. A card is one screen — its name, a big
 * photograph, where it is, and one button. A card an order is waiting for is sold THROUGH the
 * order (`pullCopy`), so the owner's ledger counts it; any other card is marked sold on its own.
 * A sale drops a receipt into a sheet at the bottom of the screen with Undo and a clock he can
 * see draining, and the next card the orders want opens under it. "Pulled today" keeps a record
 * after the clock runs out. */

const GONE = new Set(['sold', 'retired'])

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

/** Orders drawn in full before the rest fold under one button. Twenty open orders carry
 *  eighty-odd cards, and the boxes under them have to stay reachable. */
const SHOWN_ORDERS = 6

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
  sku: string
  capture_id: string
}

type Sellable = {
  key: string
  box: number
  index: number
  place: string
  name: string
  /** `Near Mint · 181/219` — what is printed on the card, drawn beside the name. */
  about: string | null
  /** The place block, for the bar and the "between" sentence. */
  where: Place | null
  /** THE CARD'S OWN NAME FOR ITS PHOTOGRAPH (D172), or null where the row it was built from
   *  has none. TWO OF THE THREE SOURCES CARRY ONE: `sellable` reads an `InventoryCard` and
   *  `asSellable` a `SearchCopy`, both of which the server names; `pickSellable` reads a
   *  `PickRow` off the order resolver, which carries `capture_id` and no `cid` at all — so an
   *  order pick addresses the slot, exactly as it always did. Null and not absent, because
   *  this is a view model built three ways and a missing key would read as an oversight in
   *  whichever constructor forgot it. */
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

/** One open order as he sees it: its number, the cards in the boxes that fill it in walk
 *  order, and how many of the things it wants are not cards in the boxes at all. */
type OrderGroup = { key: string; number: string; cards: Sellable[]; elsewhere: number }

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
    about: about.length === 0 ? null : about.join(' · '),
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

/** A copy the resolver offered an order, as a card he can go and fetch — or null when it is
 *  not one: no place to name, already gone, already spoken for, or nothing to aim the pull at. */
function pickSellable(order: OrderRow, line: ResolvedLine, pick: PickRow): Sellable | null {
  const label = pick.place.label
  if (label === null || pick.place.located === false) return null
  if (pick.state === null || GONE.has(pick.state)) return null
  if (pick.held_by !== null) return null
  if (pick.capture_id === null || pick.capture_id.trim() === '') return null
  const about = [pick.condition, pick.card_number].filter(
    (part): part is string => typeof part === 'string' && part.trim() !== '',
  )
  return {
    key: `${pick.box}/${pick.index}`,
    box: pick.box,
    index: pick.index,
    place: label,
    name: pick.card_name ?? NO_NAME,
    about: about.length === 0 ? null : about.join(' · '),
    where: pick.place,
    // THE SLOT ROUTE FOR AN ORDER PICK, BECAUSE `PickRow` CARRIES NO NAME. The order
    // resolver's row is built for aiming a WRITE — `capture_id` is what `POST /orders/pull`
    // checks against the card actually at the slot — and D93's carve-out kept it to that; a
    // `cid` has never been on it. `GET /photo/<box>/<index>` is the correct address here.
    cid: null,
    order: {
      orderKey: order.key,
      source: order.source,
      number: order.number,
      sku: line.sku,
      capture_id: pick.capture_id,
    },
  }
}

/** The open orders, each with its cards in walk order. A physical copy is offered once. */
function orderGroups(payload: OrdersPayload): OrderGroup[] {
  const rows = new Map(payload.orders.map((order) => [order.key, order]))
  const seen = new Set<string>()
  const groups: OrderGroup[] = []
  for (const resolved of payload.resolution.orders) {
    const row = rows.get(resolved.key)
    if (row === undefined || !row.open) continue
    const cards: Sellable[] = []
    let elsewhere = 0
    for (const line of resolved.lines) {
      let found = 0
      for (const pick of line.picks) {
        const card = pickSellable(row, line, pick)
        if (card === null || seen.has(card.key)) continue
        seen.add(card.key)
        cards.push(card)
        found += 1
      }
      const recorded = row.progress.find((progress) => progress.sku === line.sku)?.recorded ?? 0
      elsewhere += Math.max(0, line.wanted - recorded - found)
    }
    if (cards.length === 0 && elsewhere === 0) continue
    groups.push({ key: resolved.key, number: resolved.number, cards: inWalkOrder(cards), elsewhere })
  }
  return groups
}

function withoutCard(groups: OrderGroup[], key: string): OrderGroup[] {
  return groups.map((group) =>
    group.cards.some((card) => card.key === key)
      ? { ...group, cards: group.cards.filter((card) => card.key !== key) }
      : group,
  )
}

/** The card back in its order, after an undo, in the place the walk gives it. */
function withCard(groups: OrderGroup[], card: Sellable): OrderGroup[] {
  const order = card.order
  if (order === null) return groups
  return groups.map((group) =>
    group.key !== order.orderKey || group.cards.some((row) => row.key === card.key)
      ? group
      : { ...group, cards: inWalkOrder([...group.cards, card]) },
  )
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

/** `Box 3 · Section 1 · Card 17` with the figures ranked above the words. The text content is
 *  the server's string character for character; only the weight changes. Each ` · ` is its own
 *  span so a narrow screen can stack the parts on purpose, breaking before `Card N` with the
 *  separator hidden rather than left dangling at the end of a line. */
function PlaceText({ label }: { label: string }): ReactNode {
  return label.split(' · ').map((part, at) => {
    const seam = part.lastIndexOf(' ')
    const value = seam < 1 ? '' : part.slice(seam + 1)
    const numeric = /^\d+$/.test(value)
    return (
      <span key={at}>
        {at === 0 ? null : <span className="ff-place-sep"> · </span>}
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
  /** The open orders, resolved to cards; null until the first read answers. */
  const [orders, setOrders] = useState<OrderGroup[] | null>(null)
  const [ordersFailed, setOrdersFailed] = useState(false)
  const [allOrders, setAllOrders] = useState(false)

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
  const [openBoxes, setOpenBoxes] = useState<number[]>([])
  /** Search groups whose "more copies" disclosure he has opened, by group key. */
  const [openMore, setOpenMore] = useState<string[]>([])
  const [now, setNow] = useState(() => Date.now())
  /** The photo he tapped, so focus comes back to it when the big photo closes. */
  const photoBtn = useRef<HTMLButtonElement>(null)

  const reread = useCallback(() => setReads((n) => n + 1), [])

  /* THIS IS THE FULFILLER'S WHOLE-STORE BROWSE (D5/D6) — every sellable card across every
   * box, for when he has no order in hand to walk instead. It is store-wide by design and
   * cannot be scoped to "the boxes an order names": there may be no order at all. D-per-box-read/item 2
   * gave `#/inventory`, `#/` and the order-resolution paths their own lean, box-scoped or
   * top-K reads, but no cheap replacement exists yet for "every sellable card, lean shape" —
   * building one under this item's own budget would be the band-aid CLAUDE.md's "fix the
   * cause" rule refuses. Order resolution itself never touched `getInventory()` here: `GET
   * /orders` already resolves every open order's lines to picks carrying their own place and
   * capture id (`orderGroups`, above), so this is the ONE call site left on the full walk.
   * `docs/DEBTS.md` §27 is the named debt: the measured cost, why this cannot be box-scoped,
   * and the candidate primitive. */
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

  /* The orders, read beside the cards and from the same trigger, so a sale re-reads both. */
  useEffect(() => {
    let livePage = true
    getOrders()
      .then((payload) => {
        if (!livePage) return
        setOrders(orderGroups(payload))
        setOrdersFailed(false)
      })
      .catch(() => {
        if (!livePage) return
        setOrdersFailed(true)
      })
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
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setZoom(false)
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      /* The page is hidden under the big photo, which drops focus; hand it back to the photo
         he tapped. Null once the card has left the screen, and then there is nothing to do. */
      opener?.focus({ preventScroll: true })
    }
  }, [zoom])

  /* The walk: every card an open order is waiting for, order by order, each order's cards in
     box order. `Start with Box N` opens the first; a sale opens the next. */
  const waiting = useMemo(
    () => (orders ?? []).filter((group) => group.cards.length > 0),
    [orders],
  )
  const walk = useMemo(() => waiting.flatMap((group) => group.cards), [waiting])
  const orderByKey = useMemo(() => new Map(walk.map((card) => [card.key, card])), [walk])

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
  const soldSet = useMemo(() => new Set(soldHere), [soldHere])
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
    setOrders((prev) => (prev === null ? prev : withoutCard(prev, card.key)))
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
      /* The card after this one in the walk, found before the list moves. */
      const at = walk.findIndex((row) => row.key === card.key)
      const next = at < 0 ? null : (walk[at + 1] ?? null)
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
        if (next !== null) openCard(next)
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
          if (next !== null) openCard(next)
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
    [busyKey, walk, drop, remember, openCard, reread],
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
        setOrders((prev) => (prev === null ? prev : withCard(prev, card)))
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
            aria-label={`Pull ${copy.place.label ?? group.names.join(' / ')}`}
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
                <span className="ff-receipt-sep" aria-hidden="true">
                  {' '}
                  ·{' '}
                </span>
                <span className="ff-receipt-place">{sale.card.place}</span>
                {sale.card.order === null ? null : (
                  <>
                    <span className="ff-receipt-sep" aria-hidden="true">
                      {' '}
                      ·{' '}
                    </span>
                    <span className="ff-receipt-order">Order {sale.card.order.number}</span>
                  </>
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
                aria-label={`Undo ${sale.card.place}`}
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
          <span className="ff-empty-art">
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
    const walkAt = walk.findIndex((card) => card.key === chosen.key)
    const next = walkAt < 0 ? null : (walk[walkAt + 1] ?? null)

    body = (
      <>
        <div className="ff-nav">
          <button className="ff-back" type="button" onClick={leaveCard}>
            <Icon name="arrowLeft" size={24} />
            Back to the cards
          </button>
          {next === null ? null : (
            <button className="ff-quiet ff-next" type="button" onClick={() => openCard(next)}>
              Next card
              <Icon name="arrowRight" size={24} />
            </button>
          )}
        </div>

        <article className="ff-card">
          <div className="ff-photo-wrap">
            {missing ? (
              <div className="ff-photo-missing">
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
                    alt={`The card in ${chosen.place}`}
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
            {forOrder === null || walkAt < 0 ? null : (
              <p className="fulfillment-say ff-card-eyebrow">
                <span className="ff-card-step">
                  Card {walkAt + 1} of {walk.length}
                </span>
                <span className="ff-card-eyebrow-sep" aria-hidden="true">
                  {' '}
                  ·{' '}
                </span>
                <span className="ff-card-order">
                  For order <b>{forOrder.number}</b>
                </span>
              </p>
            )}
            <h2 className="fulfillment-name ff-card-name">{chosen.name}</h2>
            {chosen.about === null ? null : (
              <p className="fulfillment-say ff-card-about">{chosen.about}</p>
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
              <p className="fulfillment-say ff-where-between">It sits {between}.</p>
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
      hits = (
        <p className="fulfillment-say ff-say">The search did not finish. Type the name again.</p>
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

    /* ---- today: what the orders are waiting for, and where to start --------------------- */
    let today: ReactNode
    const first = walk[0]
    if (orders === null) {
      today = ordersFailed ? null : (
        <div className="ff-loading" aria-busy="true">
          <span className="ff-skel ff-skel-today" />
        </div>
      )
    } else if (first === undefined) {
      today = (
        <p className="fulfillment-say ff-today-none">
          <span className="ff-today-none-icon">
            <CheckMark size={22} />
          </span>
          No orders are waiting for a card right now. You can still find any card by name.
        </p>
      )
    } else {
      today = (
        <section className="ff-today" aria-label="Today">
          <div className="ff-today-text">
            <p className="ff-today-figure">
              <b className="ff-today-num">{walk.length.toLocaleString()}</b>
              <span className="ff-today-words">
                {walk.length === 1 ? 'card to pull' : 'cards to pull'}
              </span>
            </p>
            <p className="fulfillment-say ff-today-say">
              For {count(waiting.length, 'order', 'orders')}, listed below in the order you
              walk the boxes.
            </p>
          </div>
          <button className="ff-start" type="button" onClick={() => openCard(first)}>
            <Icon name="hand" size={26} />
            Start with Box {first.box}
            <Icon name="arrowRight" size={26} className="ff-start-arrow" />
          </button>
        </section>
      )
    }

    const shownOrders = allOrders ? waiting : waiting.slice(0, SHOWN_ORDERS)
    const hiddenOrders = waiting.length - shownOrders.length

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
            placeholder="For example, Charizard"
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
                      <span className="fulfillment-say ff-done-place">{row.place}</span>
                      {row.order === null ? null : (
                        <span className="fulfillment-say ff-done-order">Order {row.order}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {walk.length === 0 ? null : (
              <section className="ff-orders" aria-label="Orders to fill">
                <h2 className="ff-h2">
                  <span className="ff-h2-icon">
                    <Icon name="cart" size={18} />
                  </span>
                  Orders to fill
                </h2>
                <div className="ff-order-list">
                  {shownOrders.map((group, at) => (
                    <article
                      className="ff-order"
                      key={group.key}
                      style={{ animationDelay: `${Math.min(at, 8) * 40}ms` }}
                    >
                      <header className="ff-order-head">
                        <span className="ff-order-rank" aria-hidden="true">
                          {at + 1}
                        </span>
                        <span className="ff-order-text">
                          <span className="fulfillment-say ff-order-title">
                            Order <b>{group.number}</b>
                          </span>
                          <span className="fulfillment-say ff-order-count">
                            {count(group.cards.length, 'card', 'cards')} to pull
                            {group.elsewhere === 0
                              ? ''
                              : ` · ${count(group.elsewhere, 'thing', 'things')} on this order ${group.elsewhere === 1 ? 'is' : 'are'} not in the boxes`}
                          </span>
                        </span>
                      </header>
                      <ul className="fulfillment-list ff-list ff-order-cards">
                        {group.cards.map((card) => (
                          <CardRow card={card} onOpen={openCard} key={card.key} />
                        ))}
                      </ul>
                    </article>
                  ))}
                </div>
                {hiddenOrders === 0 && !allOrders ? null : (
                  <button
                    className="ff-quiet ff-orders-more"
                    type="button"
                    aria-expanded={allOrders}
                    onClick={() => setAllOrders((held) => !held)}
                  >
                    <Icon name={allOrders ? 'chevronUp' : 'chevronDown'} size={22} />
                    {allOrders
                      ? 'Show fewer orders'
                      : `Show the other ${count(hiddenOrders, 'order', 'orders')}`}
                  </button>
                )}
              </section>
            )}

            {cards.length === 0 ? (
              <div className="ff-empty">
                <span className="ff-empty-art">
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
                              {group.name === null ? '' : ` · ${group.name}`}
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
                                {`These are the first ${SHOWN_PER_BOX} of ${group.cards.length} cards in this box. Type a name above to find any of the others.`}
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
          alt={`The card in ${chosen.place}, bigger`}
        />
        <span className="fulfillment-say ff-zoom-hint">Tap anywhere to go back.</span>
      </button>
    ) : null

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
    </main>
  )
}
