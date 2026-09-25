import { test, expect, type Route } from '@playwright/test'
import { sealEveryTest } from './shell'
import { runRow } from './routeFixtures'

import type { OrderRow, OrdersPayload, ResolvedLine, ResolvedOrder } from '../src/types'

/* HOME'S "CANNOT BE FILLED" FIGURE, PINNED AGAINST A MIXED LEDGER.
 *
 * `## D202`. `app/src/standing.ts` and `app/src/Home.tsx` both once
 * summed `ResolvedOrder.outstanding` across EVERY row `GET /orders`' `resolution.orders`
 * carried, unconditionally — so an order the feed itself has already closed (Shipped,
 * Delivered, Canceled — `store/orders.py:is_terminal_status`, D63 amended 2026-09-13) still
 * inflated the headline "cannot be found" figure, even though pressing the button Home sends
 * the operator to (`#/orders`) explains, calmly, that a terminal order needs a stand-down and
 * not a search.
 *
 * `server/capture_server.py:do_orders` now excludes a terminal order from `open_keys` before
 * either the wire's per-row `open` field or `resolution.orders` itself is built, so in a real
 * response the two are already the same population. This spec does not trust that invariant
 * blind: it hands the client a `resolution.orders` entry for a row whose own `open` reads
 * `false` — the shape a stale or partially-narrowed response would have — and asserts the
 * client joins by `open` itself rather than assuming the wire pre-filtered it. That is the
 * fix: `standing.ts` and `Home.tsx` now index the open orders by `key` and count a resolved
 * line's `outstanding` only where its own order is in that set.
 *
 * NEITHER FILE MAY READ `status` OR GROW ITS OWN TERMINAL VOCABULARY (D114 — "there is no
 * status vocabulary anywhere in `app/`"). `open` is the one field either module reads.
 */

/* `cards: 4` matches `stubStore`'s own `CARDS` fixture — `#/`'s tone-0 branch ("Nothing yet")
   fires on `status.cards === 0` and would otherwise short-circuit every branch this spec is
   about before `standing()` ever reaches the orders it is given. */
sealEveryTest({ store: true, cards: 4 })

const OPEN_KEY = 'TCGplayer:OPEN-0001'
const TERMINAL_KEY = 'TCGplayer:SHIPPED-0002'

function json(route: Route, body: unknown) {
  return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
}

function orderRow(over: Partial<OrderRow>): OrderRow {
  const base: OrderRow = {
    key: OPEN_KEY,
    source: 'TCGplayer',
    number: 'OPEN-0001',
    placed_at: '2026-09-01T10:00:00+00:00',
    status: 'Ready to ship',
    first_seen: '2026-09-01T10:05:00+00:00',
    changed_at: null,
    buyer: 'Ada Lovelace',
    wanted: 2,
    recorded: 0,
    open: true,
    terminal: false,
    lines: [],
    progress: [],
  }
  return { ...base, ...over }
}

function resolvedLine(sku: string, outstanding: number): ResolvedLine {
  return {
    order: '',
    order_key: '',
    sku,
    reason: outstanding > 0 ? 'no_copies_on_hand' : 'resolved',
    wanted: outstanding,
    owed: outstanding,
    fulfilled: 0,
    outstanding,
    on_hand: 0,
    sold: 0,
    retired: 0,
    pooled: 0,
    line: {
      sku,
      quantity: outstanding,
      name: 'Volcanion',
      number: '025',
      printing: 'Normal',
      condition: 'Near Mint',
      rarity: 'Rare',
      unit_price: '1.24',
      kind: 'single',
    },
    picks: [],
  }
}

/** One genuinely open order short 2 copies, and one order the feed has already reported
 *  Shipped — `open: false` — short 5. A response that had not narrowed `resolution.orders`
 *  to the open set would still carry both entries; this fixture hands the client exactly
 *  that shape and lets the CLIENT's own `open` join decide what counts. */
function mixedLedger(): OrdersPayload {
  const open = orderRow({ key: OPEN_KEY, number: 'OPEN-0001', status: 'Ready to ship', open: true, wanted: 2, recorded: 0 })
  const terminal = orderRow({
    key: TERMINAL_KEY,
    number: 'SHIPPED-0002',
    status: 'Shipped - Delivered',
    open: false,
    wanted: 5,
    recorded: 0,
  })
  const resolved: ResolvedOrder[] = [
    { key: OPEN_KEY, number: 'OPEN-0001', complete: false, outstanding: 2, lines: [resolvedLine('9191001', 2)] },
    { key: TERMINAL_KEY, number: 'SHIPPED-0002', complete: false, outstanding: 5, lines: [resolvedLine('9191002', 5)] },
  ]
  return {
    summary: '2 orders',
    orders: [open, terminal],
    resolution: {
      orders: resolved,
      counts: { resolved: 0, short: 0, no_copies_on_hand: 2, sku_unknown: 0, sku_unseen: 0, not_a_single: 0 },
    },
  }
}

test('a terminal order never inflates the "cannot be filled" figure, and the count is the open orders alone', async ({
  page,
}) => {
  await page.route(/\/orders$/, (route) => json(route, mixedLedger()))
  await page.goto('/#/')
  await expect(page.locator('main.home')).toBeVisible()

  const standing = page.locator('.home-standing')
  await expect(standing).toHaveAttribute('data-tone', 'danger')
  const text = (await standing.locator('.home-standing-say').innerText()).replace(/\s+/g, ' ')

  // The genuine shortfall alone: 2 copies, 1 order. Never 7 copies — the terminal
  // order's 5 must never reach this sentence. (UX-051/TXT-26: one word, "missing", once.)
  expect(text).toMatch(/\b2 copies missing across\b/)
  expect(text).not.toMatch(/\b7 copies\b/)
  expect(text).toMatch(/\b1 order\b/)
  expect(text).not.toMatch(/\b2 orders\b/)
})

test('the Orders stage tile on Home carries the same figure, joined by `open` and not by trust', async ({ page }) => {
  await page.route(/\/orders$/, (route) => json(route, mixedLedger()))
  await page.goto('/#/')
  await expect(page.locator('main.home')).toBeVisible()

  const ordersTile = page.locator('a.home-stage[href="#/orders"]')
  await expect(ordersTile).toBeVisible()
  // The tile loads `/orders` itself, on its own timer (D121 — every panel loads on its own),
  // so this waits for the resolved note rather than reading whatever text painted first.
  // "missing", the same word the standing line now uses (UX-051).
  await expect(ordersTile).toContainText('2 missing')
  const text = (await ordersTile.innerText()).replace(/\s+/g, ' ')
  expect(text).not.toContain('7 missing')
})

/* UX-077, AMENDED AT THE PR 2 INTEGRATION: the "Cannot be filled" press opens Orders on the
 * buyer list's "Show" facet (`#/orders?show=<facet>`), since Orders no longer filters by a line
 * reason. A short or no-copies reason maps to `short`, and any other reason maps to `look`. The
 * facet is kept only where a buyer who owes a missing copy has it, so the list is never empty
 * while Home's figure is above 0. Two ledgers prove both halves: one whose buyer is only short,
 * and `mixedLedger`, whose no-copies line leaves its buyer at "Needs a look". */
const EMPTY_PLAN = {
  cost: 'sections',
  stops: [],
  shortfall: [],
  counts: { stops: 0, boxes: 0, copies: 0, sections_considered: 0, sections_candidate: 0, exact: true, solve_ms: 0 },
}

/** `mixedLedger` with one copy of the open line already pulled for this order, so its line
 *  reads short (`lineReason`, UX-196) and the buyer's worst state is Short. */
function shortLedger(): OrdersPayload {
  const ledger = mixedLedger()
  const progress: OrderRow['progress'] = [
    { sku: '9191001', wanted: 3, recorded: 1, outstanding: 2, over: 0, copies: ['1:1'], by_hand: 0, reason: null, declared_kind: null, closed_at: null, closed_reason: null, at: null },
  ]
  return {
    ...ledger,
    orders: ledger.orders.map((row) => (row.key === OPEN_KEY ? { ...row, wanted: 3, recorded: 1, progress } : row)),
  }
}

for (const [label, ledger, facet] of [
  ['a buyer who is only short', shortLedger, 'short'],
  ['a buyer whose missing copy leaves it at Needs a look', mixedLedger, 'look'],
] as const) {
  test(`the "Cannot be filled" press opens a non-empty Orders list on show=${facet}: ${label}`, async ({ page }) => {
    await page.route(/\/orders$/, (route) => json(route, ledger()))
    await page.route(/\/orders\/walk-plan$/, (route) => json(route, EMPTY_PLAN))
    await page.goto('/#/')
    await expect(page.locator('main.home')).toBeVisible()

    const standingRow = page.locator('a.home-standing-row')
    await expect(standingRow).toContainText('Cannot be filled')
    await expect(standingRow).toHaveAttribute('href', `#/orders?show=${facet}`)
    await standingRow.click()

    await expect(page).toHaveURL(new RegExp(`#/orders\\?show=${facet}`))
    const rows = page.locator('main.orders .orders-index-row')
    await expect(rows.first()).toBeVisible()
    await expect(rows.first()).toContainText('Ada Lovelace')
  })
}

/* F2, THE OWNER'S STORE IN MINIATURE (PR 2 integration review). Home said "135 copies missing
 * across 71 orders" and opened `show=short`, which held 6 buyers and 10 of those copies. The
 * other 125 sat under "Needs a look", and only 57 open orders missed a copy at all. This ledger
 * has the same shape: Ada's two orders miss 5 copies with none recorded (Orders files that as
 * "Needs a look"), Bob's order misses 1 with one copy already pulled (Orders files that as
 * "Short"), and Cy's open order misses nothing. Home counts only the 3 orders that miss a copy,
 * and the press opens the facet that holds most of them: "Needs a look", with Ada in it. */
function lookHeavyLedger(): OrdersPayload {
  const ada1 = orderRow({ key: 'TCGplayer:ADA-1', number: 'ADA-1', buyer: 'Ada Lovelace', wanted: 3, recorded: 0 })
  const ada2 = orderRow({ key: 'TCGplayer:ADA-2', number: 'ADA-2', buyer: 'Ada Lovelace', wanted: 2, recorded: 0 })
  const bobProgress: OrderRow['progress'] = [
    { sku: '9191005', wanted: 2, recorded: 1, outstanding: 1, over: 0, copies: ['1:1'], by_hand: 0, reason: null, declared_kind: null, closed_at: null, closed_reason: null, at: null },
  ]
  const bob = orderRow({ key: 'TCGplayer:BOB-1', number: 'BOB-1', buyer: 'Bob Babbage', wanted: 2, recorded: 1, progress: bobProgress })
  const cy = orderRow({ key: 'TCGplayer:CY-1', number: 'CY-1', buyer: 'Cy Hopper', wanted: 1, recorded: 0 })
  const resolved: ResolvedOrder[] = [
    { key: 'TCGplayer:ADA-1', number: 'ADA-1', complete: false, outstanding: 3, lines: [resolvedLine('9191003', 3)] },
    { key: 'TCGplayer:ADA-2', number: 'ADA-2', complete: false, outstanding: 2, lines: [resolvedLine('9191004', 2)] },
    { key: 'TCGplayer:BOB-1', number: 'BOB-1', complete: false, outstanding: 1, lines: [resolvedLine('9191005', 1)] },
    { key: 'TCGplayer:CY-1', number: 'CY-1', complete: true, outstanding: 0, lines: [resolvedLine('9191006', 0)] },
  ]
  return {
    summary: '4 orders',
    orders: [ada1, ada2, bob, cy],
    resolution: {
      orders: resolved,
      counts: { resolved: 1, short: 0, no_copies_on_hand: 3, sku_unknown: 0, sku_unseen: 0, not_a_single: 0 },
    },
  }
}

test('"Cannot be filled" counts only the orders that miss a copy, and opens the facet holding most of them', async ({ page }) => {
  await page.route(/\/orders$/, (route) => json(route, lookHeavyLedger()))
  await page.route(/\/orders\/walk-plan$/, (route) => json(route, EMPTY_PLAN))
  await page.goto('/#/')
  await expect(page.locator('main.home')).toBeVisible()

  const standingRow = page.locator('a.home-standing-row')
  await expect(standingRow).toContainText('Cannot be filled')
  const said = (await standingRow.innerText()).replace(/\s+/g, ' ')
  expect(said).toContain('6 copies missing across 3 orders')
  await expect(standingRow).toHaveAttribute('href', '#/orders?show=look')
  await standingRow.click()

  /* THE LIST THE PRESS OPENS HOLDS THE BUYERS HOME COUNTED UNDER THAT FACET: Ada, and nobody
     else. Bob's one short copy is the other facet's, which is why the press did not go there. */
  const rows = page.locator('main.orders .orders-index-row')
  await expect(rows).toHaveCount(1)
  await expect(rows.first()).toContainText('Ada Lovelace')
})

/* D218: NO ROUTE TYPES A MIDDLE DOT OR BULLET. `stubStore`'s two boxes carry real
 * `on_hand`/`sold` figures (box 2: 3 on hand, 1 sold), which is what actually puts
 * `.home-box-meta` on screen with something to join — an empty-boxes fixture would let this
 * pass over a screen with nothing rendered at all. */
test('no dot is typed on the box list or the hero deck (D218)', async ({ page }) => {
  await page.route(/\/orders$/, (route) => json(route, { summary: '', orders: [], resolution: { orders: [], counts: {} } }))
  await page.goto('/#/')
  await expect(page.locator('main.home')).toBeVisible()

  const meta = page.locator('.home-box-meta').first()
  await expect(meta).toContainText('on hand')
  const typedDot = /[·•]/
  await expect(page.locator('.bn-view')).not.toContainText(typedDot)
})

/* THE OWNER'S Q4 RULING, ON A VISIT TO HOME: a reading that finished while the app was closed is
 * matched here, by itself, and the spine reads the runs again once the match has answered. A
 * run whose match already stopped is NOT asked again: only its own door does that. */
test('a visit to Home matches a finished reading, and asks nothing over a match that stopped', async ({ page }) => {
  const posted: unknown[] = []
  let reads = 0
  await page.route(/\/orders$/, (route) => json(route, { summary: '', orders: [], resolution: { orders: [], counts: {} } }))
  await page.route(/\/pipeline\/runs$/, (route) => {
    reads += 1
    return json(route, {
      runs: [
        runRow(),
        runRow({
          run: '2026-09-10-box9-01',
          match_problem: { code: 'export_needs_set_hint', message: 'Every card has to name its set.', step: 'fetch' },
        }),
      ],
    })
  })
  await page.route(/\/pipeline\/runs\/[^/]+\/match$/, (route) => {
    posted.push({ path: new URL(route.request().url()).pathname, body: route.request().postDataJSON() })
    return json(route, { ran: true, ok: true, summary: runRow({ phase: 'emit' }) })
  })
  await page.goto('/#/')
  await expect(page.locator('main.home')).toBeVisible()
  await expect.poll(() => posted.length).toBe(1)
  expect(posted[0]).toEqual({ path: `/pipeline/runs/${runRow().run}/match`, body: {} })
  await expect.poll(() => reads).toBeGreaterThan(1)
})

/* UX-139's anti-pattern reaches the Review tile too: a bare figure with no note reads as an
 * unlabelled number, the same defect the box row's trailing count had. The common case —
 * cards waiting in Review, none parked — must say so, in the standing line's own word. */
test('the Review tile says "waiting", never a bare figure, when the queue is not empty and nothing is parked', async ({
  page,
}) => {
  await page.route(/\/status$/, (route) =>
    json(route, {
      captures_root: 'captures',
      store: 'inventory/store.sqlite',
      store_exists: true,
      cards: 4,
      states: {},
      queues: { review: 9, parked: 0 },
      next_index: {},
    }),
  )
  await page.goto('/#/')
  await expect(page.locator('main.home')).toBeVisible()

  const reviewTile = page.locator('a.home-stage[href="#/review"]')
  await expect(reviewTile).toBeVisible()
  await expect(reviewTile).toContainText('waiting')
  const note = page.locator('a.home-stage[href="#/review"] .home-stage-note')
  await expect(note).not.toHaveText('')
})

