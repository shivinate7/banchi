/* HOW THE BUYER LIST IS SORTED AND FILTERED — the owner's ruling read as an ORDERING, not a
 * HIDING: "Ready to Ship" leads, newest first within a group, everything else stays reachable
 * behind the status control. A default that silently dropped a row would be D103's refused
 * shape ("staleness is a filter and not a gate") landing here too, so nothing here ever removes
 * a group from `shownGroups` on its own — narrowing is only ever a person's press.
 *
 * THE STATUS OPTIONS ARE BUILT FROM THE FEED, NEVER FROM A LIST THIS FILE HOLDS (D114 —
 * "there is no status vocabulary anywhere in `app/`"). `statusVocabulary` reads whatever
 * strings `GET /orders` actually returned, with counts, so a status this pipeline has never
 * seen is an option the day it arrives rather than a string this file would need to learn.
 *
 * THE FREEZE IS `frozenRank.ts`'s RULING APPLIED TO A TOTAL ORDER RATHER THAN TO A SET OF
 * BOOLEANS (D181, D118). That module's own argument is against snapshotting a RENDERED ARRAY
 * OF KEYS where three call sites already compute the same ordering from a single per-row
 * predicate (departed or not) — a fourth copy of that arithmetic drifts the day one call site
 * gains a term the snapshot cannot see. Neither premise holds here: the buyer list has exactly
 * ONE call site, and what can change out from under it is not a per-row boolean but the ORDER
 * ITSELF — a status transition that moves a group between the Ready-to-Ship bucket and the
 * rest, a changed sort direction, or an arrival that inserts a new group in the middle. A
 * position snapshot (`OrderTake`, group key -> index) is the smallest state that can answer
 * "did the live order actually change" for a comparator with two keys and insertions, which a
 * single frozen boolean per key cannot. `takeOrder` / `applyTake` / `staleCount` below are that
 * module's PRINCIPLE — a press may reorder, nothing else may — carried over rather than
 * respelled: known rows keep the position they were taken at, a genuinely new row is appended
 * rather than hidden, and the count is the same "how far does this differ from a fresh take"
 * question `stalenessSentence` already answers for copies.
 */

import type { OrderRow, ResolvedOrder, WalkPlan } from './types'
import type { BuyerGroup } from './orderBuyers'
import type { SortValue } from './kit'

export type OrderSort = 'newest' | 'oldest'

/** The operator's whole standing view of the buyer list: which status narrows it, which way
 *  `placed_at` runs within a group, and whether a group with an unresolved SKU is folded out.
 *  Every field defaults to "show everything" — `status: null` is All, `hideUnknown: false` is
 *  off — so a device that has never touched these controls sees every row. */
export type OrderView = {
  readonly status: string | null
  readonly sort: OrderSort
  readonly hideUnknown: boolean
}

export const DEFAULT_ORDER_VIEW: OrderView = { status: null, sort: 'newest', hideUnknown: false }

export type StatusOption = { readonly status: string; readonly count: number }

/** The distinct `status` strings the FEED itself sent, with how many orders carry each —
 *  never a hardcoded list (D114). Sorted by count desc so the busiest status leads the
 *  select, ties broken alphabetically so the option order is stable across a re-read that
 *  changed nothing. A null or blank status (a paste that never carried one) is not a status
 *  word and is not offered as one. */
export function statusVocabulary(orders: readonly OrderRow[]): StatusOption[] {
  const counts = new Map<string, number>()
  for (const order of orders) {
    const status = order.status
    if (status === null) continue
    const trimmed = status.trim()
    if (trimmed === '') continue
    counts.set(trimmed, (counts.get(trimmed) ?? 0) + 1)
  }
  return [...counts.entries()]
    .map(([status, count]) => ({ status, count }))
    .sort((a, b) => b.count - a.count || a.status.localeCompare(b.status))
}

function isReadyToShip(status: string | null): boolean {
  return (status ?? '').trim().toLowerCase() === 'ready to ship'
}

/** Does this group carry a Ready-to-Ship order among its OPEN orders — what leads the default
 *  ordering. Read off `open` rather than every order: a buyer's closed history should not drag
 *  a settled group to the front because one of their old orders once said "Ready to Ship". */
export function groupIsReadyToShip(group: BuyerGroup): boolean {
  return group.open.some((order) => isReadyToShip(order.status))
}

function placedAtMs(placedAt: string | null): number {
  if (placedAt === null) return Number.NEGATIVE_INFINITY
  const parsed = Date.parse(placedAt)
  return Number.isNaN(parsed) ? Number.NEGATIVE_INFINITY : parsed
}

/* ---- the five sorts (`D-orders-sorts`, the owner's pick, 2026-09-25) -------------------------
 *
 * `placed` is the original D209 sort. The other four are the owner's own four picks, verbatim:
 * "Dollar value, Card count, Buyer name, Fewest drawers to open". Each ranks BUYERS — the group,
 * never one order — by an aggregate over the group's OPEN orders (D193), matching every other
 * figure this screen already counts per buyer (`groupMissing`, `verdictOf`).
 *
 * THE READY-TO-SHIP LEAD IS A GROUPING, NOT A SORT, AND IS KEPT ACROSS EVERY KEY. D209 built it
 * as a bucket the comparator checks BEFORE its own tiebreak, never as a special case of the
 * `placed` metric — `compareGroups` below still checks `ready` first, whichever key is asked
 * for, so a Ready-to-Ship buyer leads even under Dollar value or Buyer name. That is a finding,
 * not a guess: nothing about the four new keys touches the bucket check, and moving it inside a
 * `case 'placed':` arm would have been the alternative this file rejects.
 *
 * TIES BREAK BY PLACED DATE, NEWEST FIRST, on every key — the owner's own words for this task.
 * For `placed` itself this is a no-op (the tiebreak is the same field the primary key already
 * ordered by).
 *
 * `value` AND `cards` READ MUTABLE FIELDS (`OrderLineWire.quantity`/`unit_price` MINUS what a
 * pull has recorded), so a Mark Sold or an Undo changes them mid-view. `drawers` reads a
 * network answer that can also change under a pull. All three would re-rank the list under the
 * operator's hand the moment a write lands (D181, D118) if this file sorted `payload`'s live
 * numbers on every render — which is why `Orders.tsx` takes a POSITION SNAPSHOT
 * (`GroupTake`/`takeOrder`/`applyTake` below) at every EXPLICIT input (a sort press, a filter, a
 * search keystroke) and holds it across a write's own re-render. `placed` and `buyer` need no
 * such freeze on their own — neither field moves under a pull — but the position snapshot
 * covers every key uniformly rather than freezing three of five and not the other two. */

export type OrderSortKey = 'placed' | 'value' | 'cards' | 'buyer' | 'drawers'

/** The three aggregates `orderView.ts` cannot compute alone: a live money read, a walk-plan
 *  box count, and (for parity with the other two) the copy count — passed in by `Orders.tsx`
 *  so this module stays a pure comparator over data it is handed, never a fetcher.
 *  `drawersOf` returns `null` while the walk-plan this key needs has not landed yet — sorted
 *  last regardless of direction, so the list does not reorder twice (once on a guess, once on
 *  the real answer). */
export type OrderSortInputs = {
  readonly valueOf: (group: BuyerGroup) => number
  readonly cardsOf: (group: BuyerGroup) => number
  readonly drawersOf: (group: BuyerGroup) => number | null
}

/** `cardsOf`'s own answer where nothing narrower is asked for — copies still owed, summed over
 *  the group's open orders (the same figure `verdictOf`'s lede counts store-wide). */
export function groupCardsOwed(group: BuyerGroup): number {
  return group.open.reduce((sum, order) => sum + Math.max(0, order.wanted - order.recorded), 0)
}

/** `valueOf`'s own answer where nothing narrower is asked for: `quantity * unit_price` summed
 *  over every line of the group's open orders. A line with no price, or one that does not
 *  parse, contributes nothing — the same drop `Revenue.tsx:salesOf` makes for the identical
 *  string-to-number step (`OrderLineWire.unit_price` crosses the wire as text, D221's own
 *  reason). This is the ORDER'S OWN ASK, not a sale: it sums `quantity`, never `wanted -
 *  recorded`, because the owner's word was "order total", not "what is left of it". */
export function groupOrderValue(group: BuyerGroup): number {
  let total = 0
  for (const order of group.open) {
    for (const line of order.lines) {
      const price = line.unit_price === null ? NaN : Number(line.unit_price)
      if (!Number.isFinite(price)) continue
      total += price * line.quantity
    }
  }
  return total
}

/** `drawersOf`'s own answer: every BOX the walk planner's own solve says holds one of this
 *  group's takes, reused from a single store-wide `POST /orders/walk-plan` rather than a
 *  second computation (the brief's own instruction) — `Orders.tsx` fetches one plan over
 *  every walkable order on the screen and this function only reads it.
 *
 *  A POOLED STOP (D24) HOLDS NO BOX AND IS NEVER COUNTED. A SKU the plan could not fill at
 *  all (`shortfall`) touches no stop either. A buyer whose copies are entirely pooled, entirely
 *  short, or who owns no walkable order at all is not an error case here — it ranks at 0
 *  drawers, because there is genuinely nothing to open for them. Ascending (the key's default
 *  direction) puts them first, which reads correctly: fewest drawers to open, and this buyer
 *  needs none.
 *
 *  `orderToGroup` maps an `OrderRow.key` to the `BuyerGroup.key` that owns it — built once by
 *  the caller over every group on the screen, not recomputed per stop. */
export function drawerCountsFromPlan(plan: WalkPlan, orderToGroup: ReadonlyMap<string, string>): Map<string, number> {
  const boxesByGroup = new Map<string, Set<number>>()
  for (const stop of plan.stops) {
    if (stop.box === null) continue
    for (const take of stop.takes) {
      for (const ref of take.for) {
        const groupKey = orderToGroup.get(ref.key)
        if (groupKey === undefined) continue
        let boxes = boxesByGroup.get(groupKey)
        if (boxes === undefined) {
          boxes = new Set()
          boxesByGroup.set(groupKey, boxes)
        }
        boxes.add(stop.box)
      }
    }
  }
  const out = new Map<string, number>()
  for (const [key, boxes] of boxesByGroup) out.set(key, boxes.size)
  return out
}

const DEFAULT_SORT_INPUTS: OrderSortInputs = {
  valueOf: groupOrderValue,
  cardsOf: groupCardsOwed,
  drawersOf: () => null,
}

/** One key's own raw comparison, ascending: negative when `a` belongs before `b` at this key's
 *  OWN "asc" direction (low to high, oldest first, A to Z, fewest first). The caller flips the
 *  sign for `desc`. */
function primaryDiff(key: OrderSortKey, inputs: OrderSortInputs, a: BuyerGroup, b: BuyerGroup): number {
  switch (key) {
    case 'placed':
      return placedAtMs(a.latest) - placedAtMs(b.latest)
    case 'value':
      return inputs.valueOf(a) - inputs.valueOf(b)
    case 'cards':
      return inputs.cardsOf(a) - inputs.cardsOf(b)
    case 'buyer':
      return buyerLabel(a).localeCompare(buyerLabel(b))
    case 'drawers': {
      const da = inputs.drawersOf(a)
      const db = inputs.drawersOf(b)
      return (da ?? Number.POSITIVE_INFINITY) - (db ?? Number.POSITIVE_INFINITY)
    }
  }
}

/** The whole comparator: Ready-to-Ship groups first (a grouping, kept across every key — see
 *  the section banner above), then the picked key in the picked direction, then `placed_at`
 *  descending as the one tiebreak every key shares. */
export function compareGroups(
  sort: SortValue<OrderSortKey>,
  ready: (group: BuyerGroup) => boolean = groupIsReadyToShip,
  inputs: OrderSortInputs = DEFAULT_SORT_INPUTS,
): (a: BuyerGroup, b: BuyerGroup) => number {
  return (a, b) => {
    const aReady = ready(a)
    const bReady = ready(b)
    if (aReady !== bReady) return aReady ? -1 : 1
    const mul = sort.dir === 'asc' ? 1 : -1
    const primary = primaryDiff(sort.key, inputs, a, b) * mul
    if (primary !== 0) return primary
    return placedAtMs(b.latest) - placedAtMs(a.latest)
  }
}

/** The live-sorted list for the current view — no freeze, no filter. What a fresh take would
 *  produce right now. `ready` lets a screen hold a buyer it just finished where it stood
 *  (FLT-22): a finished buyer has no open order left to say Ready to ship. */
export function sortGroups(
  groups: readonly BuyerGroup[],
  sort: SortValue<OrderSortKey>,
  ready: (group: BuyerGroup) => boolean = groupIsReadyToShip,
  inputs: OrderSortInputs = DEFAULT_SORT_INPUTS,
): BuyerGroup[] {
  return [...groups].sort(compareGroups(sort, ready, inputs))
}

/* ---- the position freeze (D181, D118): a press may reorder, nothing else may -----------------
 *
 * `GroupTake` is a snapshot of WHERE each group stood the last time an explicit input (a sort
 * press, a filter, a search keystroke) was taken. `applyTake` renders every known group in that
 * position and appends a group the snapshot has never seen after them, in the FRESH order — an
 * arrival is never hidden by a freeze it was never part of. A group the fresh list no longer
 * contains (filtered out, or genuinely gone) is simply absent; nothing holds its place. */

export type GroupTake = ReadonlyMap<string, number>

/** Take the current fresh order as the new frozen position — called once per explicit input. */
export function takeOrder(groups: readonly BuyerGroup[]): GroupTake {
  return new Map(groups.map((group, index) => [group.key, index]))
}

/** Render `fresh` (this render's live sort) in `take`'s position — known groups first, in the
 *  order `take` recorded, then any group `take` has never seen, in `fresh`'s own order. */
export function applyTake(fresh: readonly BuyerGroup[], take: GroupTake): BuyerGroup[] {
  const known = fresh.filter((group) => take.has(group.key)).sort((a, b) => take.get(a.key)! - take.get(b.key)!)
  const arrived = fresh.filter((group) => !take.has(group.key))
  return [...known, ...arrived]
}

/** True when a sorted list leads with Ready to ship buyers AND holds others after them: the one
 *  case the list must say so, because the date order alone would not explain it (UX-170). */
export function sortedReadyFirst(
  groups: readonly BuyerGroup[],
  ready: (group: BuyerGroup) => boolean = groupIsReadyToShip,
): boolean {
  return groups.some(ready) && groups.some((group) => !ready(group))
}

/** Does this group carry a line the resolver could not identify — the "Never seen" chip's own
 *  reason (`sku_unseen`), read off the answers this screen already has rather than a new
 *  notion. Only OPEN orders are asked, matching every other reason-shaped question this screen
 *  answers over a group. */
export function groupHasUnseenLine(group: BuyerGroup, answers: ReadonlyMap<string, ResolvedOrder>): boolean {
  return group.open.some((order) => (answers.get(order.key)?.lines ?? []).some((line) => line.reason === 'sku_unseen'))
}

/** Does this group survive "Hide unknown SKUs"? Off (`false`) always passes. */
export function passesHideUnknown(
  group: BuyerGroup,
  hideUnknown: boolean,
  answers: ReadonlyMap<string, ResolvedOrder>,
): boolean {
  if (!hideUnknown) return true
  return !groupHasUnseenLine(group, answers)
}

/* --------------------------------------------------------------------- the unnamed label */

/** The label a nameless buyer draws in the NAME slot (UX-268): `Buyer on order …00012`, the tail
 *  of the group's most recent order id, in the UI face. The old `MM-DD-YY_XXXXX` form (the owner's
 *  ruling of 2026-09-19, D220) read as an order id. On the owner's store 0 of 834 orders have no
 *  buyer name, because TCGplayer always sends one, so this label is for a pasted order. The full id
 *  stays in the ORDER slot.
 *
 *  ONE ORDER IS READ, NOT AVERAGED: `groupBuyers` never merges two nameless orders into one group,
 *  so `orders[0]` is the only order. THE TAIL IS THE LAST 5 CHARACTERS of its id, or the whole id
 *  when it is shorter. */
export function unnamedBuyerLabel(group: BuyerGroup): string {
  return unnamedOrderLabel(group.orders[0]?.number ?? group.number ?? '')
}

/** The same label, for one order's number. */
export function unnamedOrderLabel(number: string): string {
  if (number === '') return 'Buyer with no name'
  /* A no-break space keeps "order …00012" one unit, so a narrow row wraps before it, never inside it. */
  return `Buyer on order\u00a0${number.length > 5 ? `…${number.slice(-5)}` : number}`
}

/** What the buyer of ONE order is called: the feed's name, or the same unnamed label the list
 *  draws for that buyer. One buyer has one name on every part of the screen. */
export function orderBuyerLabel(order: { readonly buyer: string | null; readonly number: string }): string {
  const name = order.buyer?.trim() ?? ''
  return name === '' ? unnamedOrderLabel(order.number) : name
}

/** What a buyer is called on screen: the feed's own name, or the unnamed label. */
export function buyerLabel(group: BuyerGroup): string {
  return group.name ?? unnamedBuyerLabel(group)
}
