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

/** THE VIEWER'S CLOCK, NOT UTC — and the reason is the row this label sits in. The same row
 *  already draws the placed date through `toLocaleDateString` (`Orders.tsx`, the `placed`
 *  line), which reads the local clock. A UTC label beside a local date makes one row state
 *  two different days for one event, for every viewer west of UTC, for part of every day.
 *  Cross-timezone stability is the weaker claim here: one store is read by one hand, and the
 *  label's job is to tell two nameless rows apart, not to travel. */
function shortDate(iso: string): string | null {
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) return null
  const mm = String(at.getMonth() + 1).padStart(2, '0')
  const dd = String(at.getDate()).padStart(2, '0')
  const yy = String(at.getFullYear() % 100).padStart(2, '0')
  return `${mm}-${dd}-${yy}`
}

/** The label a nameless buyer draws in the NAME slot — never a typed dot, never the order's
 *  full id (the owner's ruling, 2026-09-19). It reads `MM-DD-YY_XXXXX`: the group's own
 *  `latest` placed date, then the tail of an order id — the same two facts `BuyerRow` and
 *  `OrderPanel` already draw beside it, composed once here rather than three times.
 *
 *  ONE ORDER IS READ, NOT AVERAGED. `orderBuyers.ts:groupBuyers` never merges two nameless
 *  orders into one group (each keys on its own order), so today a nameless `group.orders`
 *  is always length 1 and this question does not arise in practice. If that invariant ever
 *  changes, this reads `orders[0]` — the most recent by `placed_at`, the same order `latest`
 *  is computed across and the same one a NAMED group's own `name` is read off — rather than
 *  averaging or concatenating several dates and ids into one string nobody could parse back.
 *
 *  THE TAIL IS THE LAST 5 CHARACTERS of that order's id, or the whole id when it is shorter
 *  than 5 — never padded, never repeated, so a 3-character id draws as itself rather than as
 *  a 5-character lie. This is a SHORT LABEL, not the id: the full id stays in the ORDER slot
 *  (`OrderPanel`'s own `ORDER <number>` / `<n> ORDERS`), never here.
 *
 *  `null` when there is neither a date nor an id to draw from — a group this bare has nothing
 *  this label can say, and an empty string is `BuyerRow`'s and `OrderPanel`'s own cue to fall
 *  back further (nothing here invents a placeholder date or id). */
export function unnamedBuyerLabel(group: BuyerGroup): string {
  const order = group.orders[0]
  const id = order?.number ?? group.number ?? ''
  const tail = id.length > 5 ? id.slice(-5) : id
  const date = group.latest === null ? null : shortDate(group.latest)
  if (date === null) return tail
  if (tail === '') return date
  return `${date}_${tail}`
}

/** What a buyer is called on screen: the feed's own name, or the unnamed label. */
export function buyerLabel(group: BuyerGroup): string {
  return group.name ?? unnamedBuyerLabel(group)
}
