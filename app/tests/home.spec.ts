import { test, expect, type Route } from '@playwright/test'
import { sealEveryTest } from './shell'

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
