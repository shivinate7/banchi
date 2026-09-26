/* GROUP ORDERS BY PERSON, NOT BY NUMBER — `D193`.
 *
 * The owner walks drawers per PERSON, and until this module existed `#/orders` had no way to
 * say who two orders belonged to: `GET /orders` returns a flat `OrderRow[]` keyed on
 * `source:number`, and one buyer with three separate orders drew as three unrelated rows with
 * no thread between them. This is the one pure function that draws that thread — no fetch, no
 * store, no React: it takes the rows `GET /orders` already returned and folds them into
 * `BuyerGroup`s, the way `pipeline/orders.py` folds lines into an order.
 *
 * THE KEY IS FOLDED, AND THAT IS A COST NAMED RATHER THAN HIDDEN. `buyerKeyOf` trims,
 * collapses internal whitespace and normalizes case — the same reason `store/orders.py:
 * order_key` folds its own key, so two spellings of the same fact are not read as two facts.
 * What it costs: two different real people who happen to share a spelling (`"J Smith"` and
 * `"j   smith"`, or two customers both named "Alex") are merged into ONE walk. That is an
 * argued trade rather than an oversight — `groupBuyers` still returns every ORDER intact
 * inside the group (nothing is deduplicated, nothing is dropped), and the group's own header
 * enumerates each order beneath it with its own number and its own progress bar, so a
 * merged walk that turns out to be two people is still fully correctable per order. Silently
 * splitting near-duplicate spellings into separate walks was rejected: TCGplayer's own console
 * already normalizes nothing, so a trailing space or a stray capital would otherwise fracture
 * one person's history into two rows the owner has no way to recognise as the same buyer.
 *
 * AN ORDER WITH NO BUYER NAME GETS ITS OWN GROUP OF ONE, KEYED ON THE ORDER ITSELF
 * (`order:<key>`), never merged with any other nameless order — two strangers who both
 * declined to be named are not the same person, and the group's `name` is `null` so a screen
 * draws "No name · #<number>" rather than inventing one.
 *
 * SORTING AND THE 7-DAY SPLIT ARE BOTH CLIENT ARITHMETIC OVER WHAT THE SERVER ALREADY SENT —
 * nothing here calls the wire. `now` is a parameter rather than `Date.now()` read inside the
 * module for the reason every other pure module in this app takes its clock as an argument:
 * a test can pin it, and a screen can pass one `now` to `groupBuyers` and to the fetch
 * receipt above it so the two cannot disagree about what "today" means mid-render.
 */

import type { OrderLineReason, OrderRow, ResolvedLine, ResolvedOrder } from './types'

/** How long a buyer with nothing open still counts as RECENT rather than sinking under the
 *  `Earlier` fold — a client-side cut on `placed_at`, not a server concept. */
export const RECENT_DAYS = 7

const RECENT_MS = RECENT_DAYS * 24 * 60 * 60 * 1000

/** One buyer's whole standing in the ledger, folded from every order that keys to them.
 *
 *  `orders` IS EVERY ORDER, complete and in `placed_at` DESC order (nulls last) — nothing
 *  here drops a record, which is what lets the "By order" fold under a merged walk stay a
 *  faithful per-order view. `open`/`wanted`/`recorded` are derived from `orders` and never
 *  stored separately from it, so they cannot drift from what a screen could recompute itself. */
export type BuyerGroup = {
  /** `name:<folded>` for a named buyer, `order:<order.key>` for a nameless one. Stable across
   *  a re-fetch as long as the buyer's folded spelling does not change. */
  key: string
  /** The VERBATIM spelling on the buyer's most recent order — never the folded key, which
   *  exists only to group. `null` for a nameless group. */
  name: string | null
  /** The order number, ONLY for a nameless group — what "No name · #<number>" reads off.
   *  `null` for a named group, where the header names every order individually instead. */
  number: string | null
  orders: OrderRow[]
  open: OrderRow[]
  /** Sum of `wanted` over `open` alone — a closed order's ask is no longer owed. */
  wanted: number
  /** Sum of `recorded` over `open` alone, for the same reason. */
  recorded: number
  /** The latest `placed_at` across every order in the group (open or not), or `null` if none
   *  of them carry one. */
  latest: string | null
}

/** Trim, collapse internal whitespace, and fold case and compatibility forms — the same
 *  three steps `store/orders.py:order_key` applies to its own key, for the same reason: a
 *  key a person cannot proofread by eye should not be sensitive to a stray space or a shift
 *  key. `normalize('NFKC')` folds width and compatibility variants (a full-width letter, a
 *  ligature) before `toLocaleLowerCase()` folds case, so the two operations do not fight
 *  over which one runs last. */
/** Exported so a search box can fold a typed query the same way — one folding rule, not a
 *  second copy of it (`orderView.ts:passesQuery`). */
export function foldName(name: string): string {
  return name.trim().replace(/\s+/g, ' ').normalize('NFKC').toLocaleLowerCase()
}

/** The group key an order belongs to. A blank or whitespace-only `buyer` is treated as no
 *  name at all, the same way `requiredText` in `orderPaste.ts` treats a blank string as
 *  absent — a feed that sent `"   "` said nothing, not something unpronounceable. */
export function buyerKeyOf(order: OrderRow): string {
  const buyer = order.buyer
  if (buyer !== null) {
    const trimmed = buyer.trim()
    if (trimmed !== '') return `name:${foldName(trimmed)}`
  }
  return `order:${order.key}`
}

function placedAtMs(placedAt: string | null): number {
  if (placedAt === null) return Number.NEGATIVE_INFINITY
  const parsed = Date.parse(placedAt)
  return Number.isNaN(parsed) ? Number.NEGATIVE_INFINITY : parsed
}

/** Newest first; an order with no `placed_at` sorts last, matching `pipeline/orders.py:
 *  Order`'s own rule that a timestamp-less order sorts last rather than first. */
function byPlacedAtDesc(a: OrderRow, b: OrderRow): number {
  return placedAtMs(b.placed_at) - placedAtMs(a.placed_at)
}

/** Groups with open work first (by latest desc), then closed groups (by latest desc) — the
 *  one comparator both the `recent` and `earlier` lists are sorted with, since `earlier`
 *  never holds an open group (see `groupBuyers`) and this reduces to "latest desc" there. */
function byOpenThenLatestDesc(a: BuyerGroup, b: BuyerGroup): number {
  const aOpen = a.open.length > 0
  const bOpen = b.open.length > 0
  if (aOpen !== bOpen) return aOpen ? -1 : 1
  return placedAtMs(b.latest) - placedAtMs(a.latest)
}

/** Fold every order in the ledger's answer into one group per buyer, split into `recent` and
 *  `earlier`.
 *
 *  `earlier` IS A BUYER WITH NOTHING OPEN WHOSE LATEST ORDER IS OLDER THAN `RECENT_DAYS`
 *  — including a buyer whose only order has no `placed_at` at all, which counts as earlier
 *  rather than recent: an undated closed order is not evidence of a live conversation. Any
 *  buyer with an open order stays in `recent` regardless of age, because an outstanding line
 *  does not become less real for being old — it becomes more worth surfacing. */
export function groupBuyers(
  orders: readonly OrderRow[],
  now: number,
): { recent: BuyerGroup[]; earlier: BuyerGroup[] } {
  const byKey = new Map<string, OrderRow[]>()
  for (const order of orders) {
    const key = buyerKeyOf(order)
    const bucket = byKey.get(key)
    if (bucket) bucket.push(order)
    else byKey.set(key, [order])
  }

  const recent: BuyerGroup[] = []
  const earlier: BuyerGroup[] = []
  const cutoff = now - RECENT_MS

  for (const [key, bucket] of byKey) {
    const sorted = [...bucket].sort(byPlacedAtDesc)
    const mostRecent = sorted[0]
    if (mostRecent === undefined) continue // unreachable: every bucket is seeded with one order
    const named = key.startsWith('name:')
    const open = sorted.filter((order) => order.open)
    let latest: string | null = null
    for (const order of sorted) {
      if (order.placed_at !== null && (latest === null || placedAtMs(order.placed_at) > placedAtMs(latest))) {
        latest = order.placed_at
      }
    }
    const group: BuyerGroup = {
      key,
      name: named ? mostRecent.buyer : null,
      number: named ? null : mostRecent.number,
      orders: sorted,
      open,
      wanted: open.reduce((sum, order) => sum + order.wanted, 0),
      recorded: open.reduce((sum, order) => sum + order.recorded, 0),
      latest,
    }

    if (group.open.length === 0 && (latest === null || placedAtMs(latest) < cutoff)) {
      earlier.push(group)
    } else {
      recent.push(group)
    }
  }

  recent.sort(byOpenThenLatestDesc)
  earlier.sort(byOpenThenLatestDesc)
  return { recent, earlier }
}

/** The reverse lookup a `?order=<key>` URL needs: which buyer group holds this order key, so
 *  a deep link resolves to a group rather than requiring its own selection concept. `null`
 *  when no group in either list carries it — a stale link into a ledger that has since
 *  changed shape under it. */
export function groupForOrderKey(
  groups: { recent: readonly BuyerGroup[]; earlier: readonly BuyerGroup[] },
  orderKey: string,
): BuyerGroup | null {
  for (const group of groups.recent) {
    if (group.orders.some((order) => order.key === orderKey)) return group
  }
  for (const group of groups.earlier) {
    if (group.orders.some((order) => order.key === orderKey)) return group
  }
  return null
}

/* ---- a buyer's status: one state per order, the worst per buyer (UX-199). Pure, so Home's
   "Cannot be filled" press can name the same facet the Orders list filters on. */

export type Status = 'ready' | 'short' | 'look' | 'unresolved' | 'done'

/** A line whose on-hand copies were all pulled FOR THIS ORDER is short, not "none left"
 *  (UX-196): the owner's own sale is not a problem to look at. */
export function lineReason(order: OrderRow, line: ResolvedLine): OrderLineReason {
  if (line.reason !== 'no_copies_on_hand') return line.reason
  const got = order.progress.find((one) => one.sku === line.sku)?.recorded ?? 0
  return got > 0 ? 'short' : line.reason
}

export function statusOf(order: OrderRow, answer: ResolvedOrder | null): Status {
  if (!order.open) return 'done'
  if (answer === null) return 'unresolved'
  const reasons = answer.lines.map((line) => lineReason(order, line))
  if (reasons.some((reason) => reason !== 'resolved' && reason !== 'short')) return 'look'
  if (reasons.some((reason) => reason === 'short')) return 'short'
  return 'ready'
}

/** Worst-of ordering over a group's open orders — `look` and `unresolved` outrank `short`,
 *  which outranks `ready`. A group with nothing open is `done`. Used only to pick the ONE dot
 *  colour a multi-order buyer's row shows; every order's own status still shows on its own
 *  chip beside it. */
export const STATUS_RANK: Record<Status, number> = { look: 0, unresolved: 1, short: 2, ready: 3, done: 4 }

export function worstStatus(group: BuyerGroup, answers: ReadonlyMap<string, ResolvedOrder>): Status {
  let worst: Status = 'done'
  for (const order of group.open) {
    const status = statusOf(order, answers.get(order.key) ?? null)
    if (STATUS_RANK[status] < STATUS_RANK[worst]) worst = status
  }
  return worst
}

/** THE ONE RULE FOR "MISSING A COPY" (UX-077, the owner's option c at the PR 2 integration): a
 *  buyer's missing copies are the `outstanding` copies on its OPEN orders (D202), and its missing
 *  orders are the open orders with any. Home's "Cannot be filled" sentence and the Orders "Show"
 *  facet `missing` both read this, so the sentence and the list it opens count the same thing. */
export function groupMissing(
  group: BuyerGroup,
  answers: ReadonlyMap<string, ResolvedOrder>,
): { readonly copies: number; readonly orders: number } {
  let copies = 0
  let orders = 0
  for (const order of group.open) {
    const out = answers.get(order.key)?.outstanding ?? 0
    if (out > 0) {
      copies += out
      orders += 1
    }
  }
  return { copies, orders }
}

/** The "Show" facet value for every buyer who owes at least one missing copy. */
export const MISSING_FACET = 'missing'

/** WHAT HOME'S "Cannot be filled" LINE SAYS: every missing copy, and only the open orders that
 *  miss one, summed over `groupMissing`. The press opens `#/orders?show=missing`, which lists
 *  exactly the buyers counted here.
 *
 *  History (D287): the first build mapped a line reason to a facet, and the second
 *  opened the `worstStatus` facet holding the most copies. On the owner's store that still split
 *  135 copies across two facets (125 and 10), so no single status list matched the sentence. */
export function missingCopies(
  orders: readonly OrderRow[],
  resolution: readonly ResolvedOrder[],
  now: number,
): { readonly copies: number; readonly orders: number } {
  const answers = new Map(resolution.map((one) => [one.key, one] as const))
  const { recent, earlier } = groupBuyers(orders, now)
  let copies = 0
  let missingOrders = 0
  for (const group of [...recent, ...earlier]) {
    const missing = groupMissing(group, answers)
    copies += missing.copies
    missingOrders += missing.orders
  }
  return { copies, orders: missingOrders }
}
