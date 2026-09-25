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

  // The genuine shortfall alone: 2 copies, 1 open order. Never 7 copies — the terminal
  // order's 5 must never reach this sentence.
  expect(text).toMatch(/\b2 copies for\b/)
  expect(text).not.toMatch(/\b7 copies for\b/)
  expect(text).toMatch(/\b1 open order\b/)
  expect(text).not.toMatch(/\b2 open orders\b/)
})

test('the Orders stage tile on Home carries the same figure, joined by `open` and not by trust', async ({ page }) => {
  await page.route(/\/orders$/, (route) => json(route, mixedLedger()))
  await page.goto('/#/')
  await expect(page.locator('main.home')).toBeVisible()

  const ordersTile = page.locator('a.home-stage[href="#/orders"]')
  await expect(ordersTile).toBeVisible()
  // The tile loads `/orders` itself, on its own timer (D121 — every panel loads on its own),
  // so this waits for the resolved note rather than reading whatever text painted first.
  await expect(ordersTile).toContainText('2 not found')
  const text = (await ordersTile.innerText()).replace(/\s+/g, ' ')
  expect(text).not.toContain('7 not found')
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


/* THE REVIEWER'S MIXED STORE (the delta review, R4 F1): one run, two priced cards and one with
 * no market price. The owner's Q3 ruling sends the two and keeps the third on the list, so
 * Home says "send 2", names the price apart, and never says the run cannot be sent. The count
 * is Pricing's own bar rule, per SKU, never per run. */
function mixedSku(sku: string, bucket: string, add: number) {
  return {
    sku,
    game: 'pokemon',
    name: `Card ${sku}`,
    bucket,
    add_to_quantity: add,
    at_cap: false,
    in: [{ run: runRow().run }],
    claimed_add: add,
    over_cap: false,
    row: {},
    snap: { market: bucket === 'no_market_data' ? null : '2.00', direct_low: null, low: null, low_with_shipping: null, now: null },
  }
}

test('a mixed run: Home sends the priced copies and names the unpriced card apart', async ({ page }) => {
  await page.route(/\/orders$/, (route) => json(route, { summary: '', orders: [], resolution: { orders: [], counts: {} } }))
  await page.route(/\/pipeline\/pricing(\?|$)/, (route) =>
    json(route, {
      runs: [],
      roster: [{ ...runRow({ joined: true, phase: 'emit' }), owes: ['1 card with no market price needs a price', 'never emitted'], open: true, unsent: 3 }],
      skus: [mixedSku('7001', 'listable', 1), mixedSku('7002', 'listable', 1), mixedSku('7003', 'no_market_data', 1)],
      written_at: {},
      skipped: [],
      asked: [],
      threshold: '0.49',
      floor: '0.49',
    }),
  )
  await page.goto('/#/')
  await expect(page.locator('main.home')).toBeVisible()
  const say = page.locator('.home-standing .home-standing-say')
  await expect(say).toContainText('send 2 copies to TCGplayer')
  await expect(page.locator('.home-standing')).toContainText('1 card needs a price')
  await expect(page.locator('.home-standing')).not.toContainText('before it can be sent')
  await expect(page.locator('.home-standing')).not.toContainText('before they can be sent')
})

test('every card needs a price: Home says price it, and counts no copy as ready', async ({ page }) => {
  await page.route(/\/orders$/, (route) => json(route, { summary: '', orders: [], resolution: { orders: [], counts: {} } }))
  await page.route(/\/pipeline\/pricing(\?|$)/, (route) =>
    json(route, {
      runs: [],
      roster: [{ ...runRow({ joined: true, phase: 'emit' }), owes: ['1 card with no market price needs a price', 'never emitted'], open: true, unsent: 1 }],
      skus: [mixedSku('7003', 'no_market_data', 1)],
      written_at: {},
      skipped: [],
      asked: [],
      threshold: '0.49',
      floor: '0.49',
    }),
  )
  await page.goto('/#/')
  await expect(page.locator('main.home')).toBeVisible()
  const say = page.locator('.home-standing .home-standing-say')
  await expect(say).toContainText('price 1 card')
  await expect(say).not.toContainText('send')
  await expect(page.locator('.home-standing')).not.toContainText('before it can be sent')
})
