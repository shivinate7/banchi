import { test, expect, type Route } from '@playwright/test'
import { sealEveryTest } from './shell'

import type { OrderRow, OrdersPayload, ProductHistoryPayload, SearchGroup, SearchResult } from '../src/types'

/* `#/product` — THE PER-PRODUCT VIEW (D227, D62, `D278`). Off-nav, reached
 * by hash and `?sku=`, so `VIEW_ROUTE` below is the one thing a compiler cannot check for this
 * screen — the same reason `fulfillment.spec.ts` and `gallery.spec.ts` pin their own route
 * verbatim.
 *
 * ASSERTIONS THIS FILE EXISTS FOR, each one this screen's own hard rule:
 *   1. The market series and the owner's own fills draw as two DIFFERENT SVG shapes, never
 *      one mark: a market run is a `<polyline>`, a fill is a `<path>` (a diamond). This spec
 *      counts both by their own class name, which a regression that drew a fill as another
 *      `<polyline>` point on the market series — the exact "one continuous line" the brief
 *      forbids — would fail by miscounting one class or the other.
 *   2. A fill older than `history_begins` is listed under "Sales older than this history"
 *      and NEVER plotted on any chart. The fixture below places one fill six months before
 *      the archive's own earliest bucket for exactly this reason.
 *   3. THE TRAP (`D278`): leaving `#/product?sku=X` by any nav press must
 *      land on the target hash. It must never bounce back to an empty `#/product`.
 *   4. `registerSheet('product', ...)` actually registers — `openSheet('product', …)` opens
 *      this view, not the fallback route change, once a sheet is registered.
 *   5. The name field (`SearchField` + `useSearch`) finds a demo card and loads it.
 *   6. Printings of one name are separately identifiable, with a one-press switch (owner
 *      ruling, 2026-09-23).
 */

function json(route: Route, body: unknown) {
  return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
}

const VIEW_ROUTE = '/#/product?sku=555123'
const SKU = '555123'

function searchGroup(over: Partial<SearchGroup> & { sku: string; names: string[] }): SearchGroup {
  return {
    number: null,
    printed_total: null,
    number_display: null,
    set_hint: null,
    set: null,
    rarity: null,
    condition: null,
    listed: { pushed: 0, staged: 0, live: 0 },
    sold_here: 0,
    live_as_of: null,
    on_hand: 1,
    listable: 1,
    copies: [],
    ...over,
  }
}

function searchResult(query: string, groups: SearchGroup[]): SearchResult {
  return { query, groups }
}

function historyPayload(): ProductHistoryPayload {
  return {
    sku: SKU,
    product_id: 42,
    name: 'Vilemaw',
    set_name: 'Twilight Masquerade',
    condition: 'Near Mint',
    source: 'archive',
    history_begins: '2026-03-01',
    never_sold: false,
    ranges: [
      {
        range: 'month',
        width_days: 1,
        buckets: 5,
        from: '2026-08-01',
        to: '2026-08-05',
        latest_market: '16.33',
        points: [
          // Two consecutive priced buckets, so `sparkSegments` has a real run to draw
          // (a lone point either side of a gap has nothing to connect to and correctly
          // draws no line at all — that is `sparkSegments`'s own rule, not this screen's).
          { at: '2026-08-01', market: '15.00', quantity: 2, low: '14.00', high: '16.00' },
          { at: '2026-08-02', market: '15.20', quantity: 1, low: '14.50', high: '16.00' },
          // A bucket with NO price at all — the line must break here, never interpolate.
          { at: '2026-08-03', market: null, quantity: 0, low: null, high: null },
          { at: '2026-08-04', market: '16.00', quantity: 1, low: '15.00', high: '17.00' },
          { at: '2026-08-05', market: '16.33', quantity: 1, low: '12.54', high: '20.35' },
        ],
      },
    ],
  }
}

function orderRow(over: Partial<OrderRow> & { lines: OrderRow['lines'] }): OrderRow {
  return {
    key: `TCGplayer:${over.number ?? 'ORD-0000'}`,
    source: 'TCGplayer',
    number: 'ORD-0000',
    placed_at: '2026-08-02T10:00:00+00:00',
    status: 'Shipped',
    first_seen: '2026-08-02T10:05:00+00:00',
    changed_at: null,
    buyer: 'Ada Lovelace',
    wanted: 1,
    recorded: 1,
    open: false,
    terminal: true,
    progress: [],
    ...over,
  }
}

function ordersPayload(): OrdersPayload {
  return {
    summary: '2 orders',
    orders: [
      // WITHIN the archive's own history — draws as a fill mark on the chart.
      orderRow({
        number: 'ORD-1001',
        placed_at: '2026-08-02T10:00:00+00:00',
        lines: [{ sku: SKU, quantity: 1, name: 'Vilemaw', number: '123', printing: null, condition: 'Near Mint', rarity: null, unit_price: '15.50', kind: null }],
      }),
      // OLDER than `history_begins` (2026-03-01) — must land in the "older than this
      // history" table and must NEVER be plotted.
      orderRow({
        number: 'ORD-0900',
        placed_at: '2025-09-01T10:00:00+00:00',
        lines: [{ sku: SKU, quantity: 1, name: 'Vilemaw', number: '123', printing: null, condition: 'Near Mint', rarity: null, unit_price: '9.00', kind: null }],
      }),
    ],
    resolution: {
      orders: [],
      counts: { resolved: 0, short: 0, no_copies_on_hand: 0, sku_unknown: 0, sku_unseen: 0, not_a_single: 0 },
    },
  }
}

test.describe('#/product — the per-product view', () => {
  sealEveryTest({ cards: 0 })

  test.beforeEach(async ({ page }) => {
    await page.route(/\/pipeline\/products\/[^/]+\/history$/, (route) => json(route, historyPayload()))
    await page.route(/\/orders$/, (route) => json(route, ordersPayload()))
    // THE PRINTINGS SWITCH ASKS `/search` ON ITS OWN (`usePrintings`), as soon as the
    // product's name loads — sealCapture aborts anything a test does not stub. One group
    // by default: fewer than two, so the switch draws nothing unless a case overrides this.
    await page.route(/\/search\?/, (route) =>
      json(route, searchResult('Vilemaw', [searchGroup({ sku: SKU, names: ['Vilemaw'], set: 'Twilight Masquerade', condition: 'Near Mint' })])),
    )
  })

  test('draws the market series and the owner\'s own fills as two different marks, never one line', async ({ page }) => {
    await page.goto(VIEW_ROUTE)
    const view = page.locator('main.producthistory')
    await expect(view).toBeVisible()

    // THE PRODUCT LOADED, off the archive, with no host reached.
    await expect(view.getByText('Vilemaw', { exact: false })).toBeVisible()
    await expect(view.getByText('Read from the archive', { exact: false })).toBeVisible()

    // THE LEGEND NAMES BOTH MARKS — the one place this screen states the distinction in
    // words, beside the shapes.
    await expect(view.getByText('Market bucket (aggregate', { exact: false })).toBeVisible()
    await expect(view.getByText("Your sale (exact", { exact: false })).toBeVisible()

    // THE MARKET LINE IS BROKEN AT THE NULL BUCKET, never interpolated across it: two
    // buckets on either side of the gap, sharing no run, draw as two separate polylines
    // rather than one. A regression that interpolated would draw exactly one.
    const marketLines = view.locator('svg.producthistory-chart polyline.producthistory-market-line')
    await expect(marketLines).toHaveCount(2)

    // THE OWNER'S OWN FILL, WITHIN HISTORY, DRAWS AS ITS OWN MARK — never merged into the
    // market polyline above. Exactly one: the second order predates `history_begins` and
    // must not appear here at all.
    const fillMarks = view.locator('svg.producthistory-chart path.producthistory-fill-mark')
    await expect(fillMarks).toHaveCount(1)

    // THE OLDER SALE IS LISTED, NAMED AS HAVING NO MARKET DATA, NEVER PLOTTED.
    await expect(view.getByText('Sales older than this history', { exact: false })).toBeVisible()
    await expect(view.getByText('ORD-0900', { exact: false })).toBeVisible()
  })

  test('the trap is fixed: leaving #/product?sku=X lands on the target, never an empty #/product (D278)', async ({ page }) => {
    await page.goto(VIEW_ROUTE)
    await expect(page.locator('main.producthistory')).toBeVisible()

    /* A NAV PRESS AWAY, simulated the way a real one arrives: the hash changes under the
       screen. BEFORE THE FIX, `ProductHistory`'s own `hashchange` listener read this new
       hash, found no `sku` on it, set `sku` to `''`, and the `writeSkuToHash` effect rewrote
       the hash back to an empty `#/product` — the trap `D278` fixed. */
    await page.evaluate(() => {
      window.location.hash = '#/gallery'
    })
    await expect(page).toHaveURL(/#\/gallery$/)
    // A beat for the OLD defect's own effect to have fired, if it still could.
    await page.waitForTimeout(300)
    await expect(page).toHaveURL(/#\/gallery$/)
  })

  test('registerSheet wires the product sheet, and its fallback route is #/product?sku= (D278)', async ({ page }) => {
    await page.goto('/#/gallery')
    const [registered, href] = await page.evaluate(async () => {
      const mod = await import(('/src/kit/sheets' + '.ts'))
      return [mod.hasSheet('product'), mod.sheetHref('product', { sku: '555123' })]
    })
    expect(registered).toBe(true)
    expect(href).toBe('#/product?sku=555123')
  })

  test('the name field (SearchField + useSearch) finds a demo card and loads it', async ({ page }) => {
    await page.route(/\/search\?q=Charizard/, (route) =>
      json(
        route,
        searchResult('Charizard', [searchGroup({ sku: '777777', names: ['Charizard'], set: 'Base Set', condition: 'Near Mint' })]),
      ),
    )
    await page.route(/\/pipeline\/products\/777777\/history$/, (route) =>
      json(route, {
        sku: '777777',
        product_id: 7,
        name: 'Charizard',
        set_name: 'Base Set',
        condition: 'Near Mint',
        source: 'archive',
        history_begins: null,
        never_sold: true,
        ranges: [],
      } satisfies ProductHistoryPayload),
    )

    await page.goto('/#/product')
    await expect(page.getByText('Enter a SKU to see its history.', { exact: false })).toBeVisible()

    await page.getByLabel('Find a product').fill('Charizard')
    const result = page.locator('.producthistory-result', { hasText: 'Charizard' })
    await expect(result).toBeVisible()
    await result.click()

    await expect(page).toHaveURL(/#\/product\?sku=777777/)
    await expect(page.getByRole('heading', { name: 'Charizard' })).toBeVisible()
  })

  test('printings of one name are separately identifiable, with a one-press switch (owner ruling, 2026-09-23)', async ({ page }) => {
    await page.route(/\/search\?/, (route) =>
      json(
        route,
        searchResult('Vilemaw', [
          searchGroup({ sku: SKU, names: ['Vilemaw'], set: 'Twilight Masquerade', condition: 'Near Mint' }),
          searchGroup({ sku: '555999', names: ['Vilemaw'], set: 'Twilight Masquerade', condition: 'Holo' }),
        ]),
      ),
    )
    await page.route(/\/pipeline\/products\/555999\/history$/, (route) =>
      json(route, {
        sku: '555999',
        product_id: 43,
        name: 'Vilemaw',
        set_name: 'Twilight Masquerade',
        condition: 'Holo',
        source: 'archive',
        history_begins: null,
        never_sold: true,
        ranges: [],
      } satisfies ProductHistoryPayload),
    )

    await page.goto(VIEW_ROUTE)
    const view = page.locator('main.producthistory')
    await expect(view).toBeVisible()

    const switcher = view.locator('.producthistory-printings')
    await expect(switcher).toBeVisible()
    const chips = switcher.locator('.bn-chip')
    await expect(chips).toHaveCount(2)
    await expect(chips.filter({ hasText: 'Near Mint' })).toHaveAttribute('aria-pressed', 'true')
    await expect(chips.filter({ hasText: 'Holo' })).toHaveAttribute('aria-pressed', 'false')

    // ONE PRESS SWITCHES — never a second chart drawn on top of the first.
    await chips.filter({ hasText: 'Holo' }).click()
    await expect(page).toHaveURL(/#\/product\?sku=555999/)
    await expect(view.getByText('This product has never been recorded to sell', { exact: false })).toBeVisible()
  })
})
