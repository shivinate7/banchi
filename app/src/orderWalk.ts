import type {
  FillLine,
  OrderRow,
  OrdersPayload,
  PickRow,
  PullTarget,
  ResolvedLine,
  ResolvedOrder,
} from './types'

/* THE ORDER WALK'S QUEUE, AS PURE FUNCTIONS OVER ONE `GET /orders` ANSWER.
 *
 * An order drives the box walk on `#/inventory` (docs/specs/order-pipeline.md §3 T6): the
 * walk lands on the first copy an order needs, the copies panel shows every copy of that SKU,
 * ArrowRight moves to the next stop, and one press per ORDER — the envelope — records every
 * copy as pulled and sold. This module decides what the stops are and in what order; it
 * holds no state, calls no server and imports no React, so `Inventory.tsx` can stay the
 * screen and the browser spec can reason about the queue without a store.
 *
 * NOTHING HERE IS STORED, AND THE QUEUE IS RE-DERIVED ON EVERY READ (D36). A run's slot
 * numbers are not the truth and neither is a pick list computed a minute ago: a mid-box
 * delete slides every higher index down, a sale on another device removes a copy, and the
 * resolver's allocation over the whole open set moves when any line moves. So every function
 * below takes the payload the screen just read and answers from it; the only thing the screen
 * carries across reads is the CURSOR, and `cursorAfter` says how it survives.
 *
 * A STOP IS A LINE, NOT A POSITION (T6's first determination), standing at its next pullable
 * copy. The copies panel already draws the whole SKU group for whatever the walk points at,
 * so landing on a line's first pick puts its entire pick list on screen for free; a queue of
 * positions would stand a second pick list beside the one already drawn. Wave mode does not
 * break this: it SORTS the same line-stops by where their landing sits, and because a landing
 * is re-derived per read, a three-copy line whose first copy was just filled stands at its
 * next unfilled copy. The pass through the boxes is a property of the read, not a list.
 *
 * THE PANEL IS THE PICKER (D93). Every unsold copy of the stop's SKU carries its own take, in
 * any box, so which copies an envelope records is CHOSEN from the list rather than corrected one
 * at a time against the resolver's answer. `targetsOf` is where the operator's list meets that
 * answer, and the resolver's picks are still the default — the picker costs a press only when
 * the operator has an opinion about which copies.
 *
 * THE URL IS THE HANDOFF, NOT `sessionStorage` (D49's argument for `#/pricing?run=`): an
 * order key has one source of truth — the ledger — and is validated against the payload on
 * every read, so it needs no second key with its own clearing rules. What that buys is a
 * reload landing on the first REMAINING stop, a Back button that works, and two tabs that
 * cannot disagree. The colon in `source:number` is why the key is encoded.
 */

export type WalkAsk = { kind: 'order'; key: string } | { kind: 'wave' } | null

const ORDER_PARAM = 'order'
const WAVE_PARAM = 'orders'
/* `open` rather than `all`: filled orders are never in the queue, and a word that claimed
 * they were would be the first thing a reader wondered about. */
const WAVE_VALUE = 'open'

/** What the location hash asks the walk to drive. `null` is the plain walk. */
export function askInHash(hash: string): WalkAsk {
  const query = hash.split('?')[1] ?? ''
  if (query === '') return null
  const params = new URLSearchParams(query)
  const key = params.get(ORDER_PARAM)
  if (key !== null && key.trim() !== '') return { kind: 'order', key: key.trim() }
  if (params.get(WAVE_PARAM) === WAVE_VALUE) return { kind: 'wave' }
  return null
}

/** The link that enters the walk. `#/orders` draws these; nothing else composes them. */
export function walkHash(ask: NonNullable<WalkAsk>): string {
  return ask.kind === 'order'
    ? `#/inventory?${ORDER_PARAM}=${encodeURIComponent(ask.key)}`
    : `#/inventory?${WAVE_PARAM}=${WAVE_VALUE}`
}

/** The hash that leaves it: the same route, no parameter. `currentPath()` strips the query,
 *  so the view does not remount on the way out. */
export const PLAIN_WALK_HASH = '#/inventory'

/** One stop: an order line the ledger still owes copies on, standing at its next pullable copy. */
export type Stop = {
  /** `${orderKey}/${sku}` — stable across reads, which is what the cursor is kept by. */
  readonly id: string
  readonly orderKey: string
  readonly order: string
  readonly source: string
  readonly sku: string
  readonly name: string | null
  /** The buyer's number, what the ledger has recorded, and what it still owes. Ledger figures
   *  off `OrderRow.progress`, never counted in this client. */
  readonly wanted: number
  readonly recorded: number
  readonly owed: number
  /** The resolver's allocation for what is still owed, in `(box, index)` order. */
  readonly picks: readonly PickRow[]
  /** How many of those picks the walk could actually aim at. The DENOMINATOR OF THE SHORTFALL
   *  (D93): a line owed 2 that the resolver could only find 1 copy for is short by one whatever
   *  the operator does with their hands, and that is a different fact from a copy they chose
   *  not to take. `Inventory.tsx:shortfalls` is the only reader and it splits the two. */
  readonly available: number
  /** The first pick with a capture id that no other line has already recorded, or null. */
  readonly landing: PickRow | null
  /** `(order position, line position)` in the payload — the order-mode order and the wave tiebreak. */
  readonly sequence: readonly [number, number]
}

/** One order's stops, grouped for the envelope press. */
export type Envelope = {
  readonly orderKey: string
  readonly order: string
  readonly source: string
  readonly stops: readonly Stop[]
}

export type Queue = {
  /** The stops the walk can stand on, in walk order. */
  readonly stops: readonly Stop[]
  /** Lines still owed that no aimable copy answers for — counted on the banner, never walked to. */
  readonly unfillable: readonly Stop[]
  /** One per open order in the queue, in payload order. */
  readonly envelopes: readonly Envelope[]
}

/** Which copies the walk may aim at for a line: a capture id to aim by, and not already
 *  recorded against some other line. `aimOf` on `#/orders` is the same test. */
function aimable(pick: PickRow): boolean {
  return pick.capture_id !== null && pick.capture_id.trim() !== '' && pick.held_by === null
}

function stopOf(
  row: OrderRow,
  answer: ResolvedOrder,
  line: ResolvedLine,
  sequence: readonly [number, number],
): Stop {
  const progress = row.progress.find((one) => one.sku === line.sku)
  const offered = line.picks.filter(aimable)
  return {
    id: `${row.key}/${line.sku}`,
    orderKey: row.key,
    order: answer.number,
    source: row.source,
    sku: line.sku,
    name: line.line.name,
    wanted: progress?.wanted ?? line.wanted,
    recorded: progress?.recorded ?? 0,
    owed: progress?.outstanding ?? line.owed,
    picks: line.picks,
    available: offered.length,
    landing: offered[0] ?? null,
    sequence,
  }
}

/**
 * The queue for one ask, derived from one payload.
 *
 * MEMBERSHIP: open orders only (`resolution.orders` is already `Ledger.unfulfilled()`), lines
 * the ledger still owes on, and — for a stop the walk can stand on — a landing. A line owed
 * copies with no aimable pick (`no_copies_on_hand`, a pooled copy, a record with no capture
 * id) is `unfillable`: the banner counts it and points at `#/orders`, and the walk never
 * lands on a place that does not exist.
 *
 * ORDER MODE keeps the payload's order (already `order_sequence`) and each order's line
 * order. WAVE MODE sorts by `(landing.box, landing.index)`, ties by sequence, so the pass
 * through the drawers is one direction.
 */
export function stopsOf(payload: OrdersPayload, ask: NonNullable<WalkAsk>): Queue {
  const rows = new Map(payload.orders.map((row) => [row.key, row] as const))
  const stops: Stop[] = []
  const unfillable: Stop[] = []
  const envelopes: Envelope[] = []
  payload.resolution.orders.forEach((answer, orderAt) => {
    if (ask.kind === 'order' && answer.key !== ask.key) return
    const row = rows.get(answer.key)
    if (row === undefined) return
    const own: Stop[] = []
    answer.lines.forEach((line, lineAt) => {
      const stop = stopOf(row, answer, line, [orderAt, lineAt])
      if (stop.owed <= 0) return
      if (stop.landing === null) {
        unfillable.push(stop)
        return
      }
      own.push(stop)
    })
    if (own.length > 0) {
      envelopes.push({ orderKey: row.key, order: answer.number, source: row.source, stops: own })
      stops.push(...own)
    }
  })
  if (ask.kind === 'wave') {
    stops.sort((a, b) => {
      const la = a.landing as PickRow
      const lb = b.landing as PickRow
      return (
        la.box - lb.box ||
        la.index - lb.index ||
        a.sequence[0] - b.sequence[0] ||
        a.sequence[1] - b.sequence[1]
      )
    })
  }
  return { stops, unfillable, envelopes }
}

/** The store key of a pick, in the walk's own address space. */
export function keyOf(pick: { box: number; index: number }): string {
  return `${pick.box}/${pick.index}`
}

/**
 * The marks the copies panel draws while an order drives — keyed by `"<box>/<index>"`, which
 * is `SearchCopy.key`. Highest claim wins where two apply: a copy already pulled outranks one
 * merely allocated, and a copy the ledger holds for another line outranks a pick.
 *
 *   pulled   recorded against an order and sold — the slot a pulled card came out of
 *   held     the ledger records it for a line but it is still on hand (a sale undone by hand)
 *   target   what this envelope will record for the stop named
 *   pick     the resolver's offer for a stop in the queue that is not among its targets
 *   spoken   another open order's pick, outside this queue (order mode only)
 */
export type CopyMark =
  | { kind: 'pulled'; order: string }
  | { kind: 'held'; order: string }
  | { kind: 'target'; stopId: string; order: string }
  | { kind: 'pick'; stopId: string; order: string }
  | { kind: 'spoken'; order: string }

export function marksOf(
  payload: OrdersPayload,
  queue: Queue,
  targets: ReadonlyMap<string, readonly PullTarget[]>,
): ReadonlyMap<string, CopyMark> {
  const marks = new Map<string, CopyMark>()
  const queued = new Set(queue.stops.map((stop) => stop.id))
  const inQueue = new Set(queue.envelopes.map((envelope) => envelope.orderKey))

  /* Lowest claim first, so a later `set` is a higher one winning. */
  for (const answer of payload.resolution.orders) {
    if (inQueue.has(answer.key)) continue
    for (const line of answer.lines) {
      for (const pick of line.picks) marks.set(keyOf(pick), { kind: 'spoken', order: answer.number })
    }
  }
  for (const stop of [...queue.stops, ...queue.unfillable]) {
    if (!queued.has(stop.id)) continue
    const aimed = new Set((targets.get(stop.id) ?? []).map(keyOf))
    for (const pick of stop.picks) {
      const key = keyOf(pick)
      marks.set(key, aimed.has(key)
        ? { kind: 'target', stopId: stop.id, order: stop.order }
        : { kind: 'pick', stopId: stop.id, order: stop.order })
    }
    for (const target of targets.get(stop.id) ?? []) {
      marks.set(keyOf(target), { kind: 'target', stopId: stop.id, order: stop.order })
    }
  }
  for (const answer of payload.resolution.orders) {
    for (const line of answer.lines) {
      for (const pick of line.picks) {
        if (pick.held_by !== null) marks.set(keyOf(pick), { kind: 'held', order: pick.held_by.order })
      }
    }
  }
  for (const row of payload.orders) {
    for (const progress of row.progress) {
      for (const pulled of progress.pulled) {
        if (pulled.box === null || pulled.index === null) continue
        marks.set(keyOf({ box: pulled.box, index: pulled.index }), { kind: 'pulled', order: row.number })
      }
    }
  }
  return marks
}

/**
 * The copies an envelope will record for one stop: the resolver's picks, aimed by their own
 * capture ids, until the operator says otherwise. `chosen` maps a stop to the copies they took
 * with their hands — this screen's and this session's, lost on a reload, when the picks stand
 * in again.
 *
 * ONE MAP AND NOT TWO (D93). This took `retargets` and `excluded` — a stop's replacement list
 * and a set of capture ids the operator had said were not in the drawer — because the two
 * corrections it served were `Take this one instead` and `Not here`, each a note against the
 * resolver's answer. The panel is the picker now: a copy is taken or it is not, so what the
 * operator said is ONE list per stop, and an empty list is a real answer rather than an absent
 * one. `?? ` and not `||` for exactly that: a stop the operator has emptied stays empty and
 * does not fall back to the picks.
 *
 * THE DEFAULT IS STILL THE RESOLVER'S, which is what keeps the common case free. A line owed
 * two with two copies on the shelf is zero presses; the picker costs a press only when the
 * operator has an opinion about WHICH copies.
 */
export function targetsOf(
  stop: Stop,
  chosen: ReadonlyMap<string, readonly PullTarget[]>,
): PullTarget[] {
  const taken =
    chosen.get(stop.id) ??
    stop.picks.filter(aimable).map((pick) => ({
      box: pick.box,
      index: pick.index,
      capture_id: pick.capture_id as string,
    }))
  /* CLAMPED TO WHAT THE LEDGER STILL OWES, and the clamp is about the operator's list rather
   * than the picks. The resolver never returns more picks than the line is owed, and the picker
   * refuses a take at capacity — but `chosen` is this screen's own state and survives every
   * re-read: another device pulling one copy of the line brings `owed` down to 1 while the
   * operator's two hand-picked copies are still stored, and the press would then send two copies
   * for a line owing one — `record_pull` refuses `over_fulfilled` and nothing is clamped there
   * on purpose, so the whole envelope is lost at the drawer. Trimming from the end keeps the
   * copy the walk is standing on, which is the first one. */
  return taken.slice(0, Math.max(0, stop.owed))
}

/** What one envelope press sends: one `FillLine` per stop with at least one copy taken. */
export function envelopeLines(
  envelope: Envelope,
  chosen: ReadonlyMap<string, readonly PullTarget[]>,
): FillLine[] {
  return envelope.stops
    .map((stop) => ({ sku: stop.sku, targets: targetsOf(stop, chosen) }))
    .filter((line) => line.targets.length > 0)
}

/**
 * Where the cursor stands after a re-read. The same stop still queued: keep it — its landing
 * may have moved, and the landing effect follows. Gone (filled, or no longer fillable): the
 * first stop that came after it in the OLD queue and is still in the new one, else the
 * earliest remaining, else `null`, which is "complete". Never a count kept in the client.
 */
export function cursorAfter(
  before: { readonly stops: readonly Stop[]; readonly cursor: string | null },
  after: readonly Stop[],
): string | null {
  if (after.length === 0) return null
  if (before.cursor !== null && after.some((stop) => stop.id === before.cursor)) return before.cursor
  const at = before.stops.findIndex((stop) => stop.id === before.cursor)
  if (at !== -1) {
    const ids = new Set(after.map((stop) => stop.id))
    const next = before.stops.slice(at + 1).find((stop) => ids.has(stop.id))
    if (next !== undefined) return next.id
  }
  return after[0]?.id ?? null
}

/** The arrows: one stop either way, ends stop, never wrap — `STEPS`' own semantics. A cursor
 *  not in the queue steps in from the end being stepped from. */
export function stepCursor(
  stops: readonly Stop[],
  cursor: string | null,
  delta: -1 | 1,
): string | null {
  if (stops.length === 0) return null
  const at = stops.findIndex((stop) => stop.id === cursor)
  if (at === -1) return (delta === 1 ? stops[0] : stops[stops.length - 1])?.id ?? null
  return stops[at + delta]?.id ?? cursor
}
