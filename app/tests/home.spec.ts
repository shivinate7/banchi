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

/* UX-077, AMENDED AT THE PR 2 INTEGRATION (the owner's option c): the "Cannot be filled" press
 * opens Orders on the "Show" facet "Missing a copy" (`#/orders?show=missing`), every buyer who
 * owes a copy the store cannot find, whatever that buyer's state. Two ledgers: a buyer who is
 * only short, and `mixedLedger`, whose no-copies line leaves its buyer at "Needs a look". Both
 * land on a list that is not empty. */
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
  ['a buyer who is only short', shortLedger, 'missing'],
  ['a buyer whose missing copy leaves it at Needs a look', mixedLedger, 'missing'],
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
 * has the same split: Ada's two orders miss 5 copies with none recorded ("Needs a look"), Bob's
 * order misses 1 with one copy already pulled ("Short"), and Cy's open order misses nothing.
 * Home counts only the 3 orders that miss a copy, and the "Missing a copy" list adds up to it. */
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

test('"Cannot be filled" counts only the orders that miss a copy, and the list it opens adds up to it exactly', async ({ page }) => {
  await page.route(/\/orders$/, (route) => json(route, lookHeavyLedger()))
  await page.route(/\/orders\/walk-plan$/, (route) => json(route, EMPTY_PLAN))
  await page.goto('/#/')
  await expect(page.locator('main.home')).toBeVisible()

  const standingRow = page.locator('a.home-standing-row')
  await expect(standingRow).toContainText('Cannot be filled')
  const said = (await standingRow.innerText()).replace(/\s+/g, ' ')
  expect(said).toContain('6 copies missing across 3 orders')
  await expect(standingRow).toHaveAttribute('href', '#/orders?show=missing')
  await standingRow.click()

  /* FULL EQUALITY (the owner's option c): the "Missing a copy" list holds every buyer Home
     counted and nobody else, across both states. Ada is "Needs a look" and Bob is "Short", and
     Cy, whose open order misses nothing, is not listed. Each row says its own missing copies
     and orders, and they sum to Home's sentence. */
  const rows = page.locator('main.orders .orders-index-row')
  await expect(rows).toHaveCount(2)
  await expect(page.locator('main.orders')).not.toContainText('Cy Hopper')
  const figures = await page.locator('main.orders .orders-index-figure').allInnerTexts()
  const sums = figures.reduce(
    (acc, text) => {
      const m = /(\d+) missing in (\d+) orders?/.exec(text.replace(/\s+/g, ' '))
      expect(m, `a row's figure: "${text}"`).not.toBeNull()
      return { copies: acc.copies + Number(m![1]), orders: acc.orders + Number(m![2]) }
    },
    { copies: 0, orders: 0 },
  )
  expect(sums).toEqual({ copies: 6, orders: 3 })
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
      roster: [{ ...runRow({ joined: true, phase: 'emit' }), owes: ['1 card with no market price needs a price', 'never emitted'], owed: [{ code: 'needs_price', count: 1 }, { code: 'never_emitted', count: null }], open: true, unsent: 3 }],
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
  /* THE PRICING TILE COUNTS THE SAME COPIES (the screenshot review, R4): it summed every run's
     unsent copies, the unpriced and the held ones too. It reads the bar's rule now. */
  const tile = page.locator('a.home-stage[href="#/pricing"]')
  await expect(tile).toContainText('to price, 2 ready')
  await expect(tile).not.toContainText('3 ready')
  await expect(tile).not.toContainText('3 copies')
})

test('every card needs a price: Home says price it, and counts no copy as ready', async ({ page }) => {
  await page.route(/\/orders$/, (route) => json(route, { summary: '', orders: [], resolution: { orders: [], counts: {} } }))
  await page.route(/\/pipeline\/pricing(\?|$)/, (route) =>
    json(route, {
      runs: [],
      roster: [{ ...runRow({ joined: true, phase: 'emit' }), owes: ['1 card with no market price needs a price', 'never emitted'], owed: [{ code: 'needs_price', count: 1 }, { code: 'never_emitted', count: null }], open: true, unsent: 1 }],
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

/* DEBT42, THE OWNER'S RULING ("Screen shows $5.16"): a typed price on the `price` channel is
 * what the send lists at, even after the card's market went blank. So Home counts that copy as
 * ready and names no card that needs a price. The server's roster already agrees: it owes only
 * the first send. */
test('a typed price on a card whose market went blank counts as ready on Home', async ({ page }) => {
  await page.route(/\/orders$/, (route) => json(route, { summary: '', orders: [], resolution: { orders: [], counts: {} } }))
  await page.route(/\/pipeline\/pricing(\?|$)/, (route) =>
    json(route, {
      runs: [],
      roster: [{ ...runRow({ joined: true, phase: 'emit' }), owes: ['never emitted'], owed: [{ code: 'never_emitted', count: null }], open: true, unsent: 3 }],
      skus: [mixedSku('7001', 'listable', 1), mixedSku('7002', 'listable', 1), mixedSku('7003', 'no_market_data', 1)],
      written_at: {},
      skipped: [],
      asked: [],
      threshold: '0.49',
      floor: '0.49',
    }),
  )
  await page.route(
    (url) => url.pathname.endsWith('/pricing') && !url.pathname.includes('/pipeline/'),
    (route) =>
      route.request().method() === 'GET'
        ? json(route, { corpus: { version: 1, policy: { rule: 'match', basis: 'market', sub_threshold: { flat: '0.49' } }, skus: { '7003': { value: '5.16' } } }, path: '/tmp/prices.json', revision: 'rev-1' })
        : route.fallback(),
  )
  await page.goto('/#/')
  await expect(page.locator('main.home')).toBeVisible()
  await expect(page.locator('.home-standing .home-standing-say')).toContainText('send 3 copies to TCGplayer')
  await expect(page.locator('.home-standing')).not.toContainText('needs a price')
})

/* A HELD ROW OWES NOTHING AND SENDS NOTHING (`standing.ts:rowShare`). A hold sits on the
 * `price` channel on every row, one with a market price and one without, because `join` reads
 * it there first. So Home counts only the one unheld copy as ready and names no card that needs
 * a price. */
test('a held card, with or without a market price, is neither ready nor owed on Home', async ({ page }) => {
  await page.route(/\/orders$/, (route) => json(route, { summary: '', orders: [], resolution: { orders: [], counts: {} } }))
  await page.route(/\/pipeline\/pricing(\?|$)/, (route) =>
    json(route, {
      runs: [],
      roster: [{ ...runRow({ joined: true, phase: 'emit' }), owes: ['never emitted'], owed: [{ code: 'never_emitted', count: null }], open: true, unsent: 3 }],
      skus: [mixedSku('7001', 'listable', 1), mixedSku('7002', 'listable', 1), mixedSku('7003', 'no_market_data', 1)],
      written_at: {},
      skipped: [],
      asked: [],
      threshold: '0.49',
      floor: '0.49',
    }),
  )
  await page.route(
    (url) => url.pathname.endsWith('/pricing') && !url.pathname.includes('/pipeline/'),
    (route) =>
      route.request().method() === 'GET'
        ? json(route, { corpus: { version: 1, policy: { rule: 'match', basis: 'market', sub_threshold: { flat: '0.49' } }, skus: { '7002': { value: { withheld: 'bullish' } }, '7003': { value: { withheld: 'bullish' } } } }, path: '/tmp/prices.json', revision: 'rev-1' })
        : route.fallback(),
  )
  await page.goto('/#/')
  await expect(page.locator('main.home')).toBeVisible()
  await expect(page.locator('.home-standing .home-standing-say')).toContainText('send 1 copy to TCGplayer')
  await expect(page.locator('.home-standing')).not.toContainText('needs a price')
})

/* THE SCREEN READS THE CODE, NEVER THE SENTENCE (the coordinator's ruling on R4): the server's
 * words for a price owed may change, and Home must not change with them. The code stays
 * `needs_price`, so the line still sends the priced copies and blames no cut-off. */
test('a reworded owed sentence changes nothing on Home while its code stays', async ({ page }) => {
  await page.route(/\/orders$/, (route) => json(route, { summary: '', orders: [], resolution: { orders: [], counts: {} } }))
  await page.route(/\/pipeline\/pricing(\?|$)/, (route) =>
    json(route, {
      runs: [],
      roster: [{ ...runRow({ joined: true, phase: 'emit' }), owes: ['one card still lacks a market price', 'not written yet'], owed: [{ code: 'needs_price', count: 1 }, { code: 'never_emitted', count: null }], open: true, unsent: 3 }],
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
  await expect(page.locator('.home-standing .home-standing-say')).toContainText('send 2 copies to TCGplayer')
  await expect(page.locator('.home-standing')).toContainText('1 card needs a price')
  await expect(page.locator('.home-standing')).not.toContainText('cut-off')
})
