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

import type { OrderRow, ResolvedOrder } from './types'
import type { BuyerGroup } from './orderBuyers'

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

/** The two-key comparator: Ready-to-Ship groups first regardless of sort direction — the
 *  owner's ruling is about which groups LEAD, not about which way time runs — then `latest`
 *  within each bucket, in the direction `sort` asks for. */
export function compareGroups(
  sort: OrderSort,
  ready: (group: BuyerGroup) => boolean = groupIsReadyToShip,
): (a: BuyerGroup, b: BuyerGroup) => number {
  return (a, b) => {
    const aReady = ready(a)
    const bReady = ready(b)
    if (aReady !== bReady) return aReady ? -1 : 1
    const diff = placedAtMs(a.latest) - placedAtMs(b.latest)
    return sort === 'newest' ? -diff : diff
  }
}

/** The live-sorted list for the current view — no freeze, no filter. What a fresh take would
 *  produce right now. */
/** `ready` lets a screen hold a buyer it just finished where it stood (FLT-22): a finished
 *  buyer has no open order left to say Ready to ship. */
export function sortGroups(
  groups: readonly BuyerGroup[],
  sort: OrderSort,
  ready: (group: BuyerGroup) => boolean = groupIsReadyToShip,
): BuyerGroup[] {
  return [...groups].sort(compareGroups(sort, ready))
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
  const id = group.orders[0]?.number ?? group.number ?? ''
  if (id === '') return 'Buyer with no name'
  return `Buyer on order ${id.length > 5 ? `…${id.slice(-5)}` : id}`
}

/** What a buyer is called on screen: the feed's own name, or the unnamed label. */
export function buyerLabel(group: BuyerGroup): string {
  return group.name ?? unnamedBuyerLabel(group)
}
