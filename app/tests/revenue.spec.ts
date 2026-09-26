import { test, expect, type Page, type Route } from '@playwright/test'
import { sealEveryTest } from './shell'

import type { OrderLineProgress, OrderLineWire, OrderRow, OrdersPayload } from '../src/types'

/* `#/revenue` (SALES) BECOMES A TOOL — sort, filter, cross-filter, deep-link and drill down
 * (`D217`), over the same `GET /orders` payload D214 already reshapes. Nothing here
 * touches what counts as revenue: D214's counting rules (gross only, Canceled dropped, no
 * sealed/singles split) are unchanged and this file does not re-test them — `docs/specs/
 * revenue.md` is where that argument lives.
 *
 * THE CLOCK IS FAKE AND FIXED, everywhere in this file. `windowsOf` and the in-progress bucket
 * both read the real wall clock (`now`) on purpose — a store that sold nothing this week still
 * has a "this month" that is genuinely in progress today — which means a case about either has
 * to pin what "today" is or it goes stale, and worse, flaky, the day the run crosses a month
 * boundary. `page.clock.install` runs before every `page.goto` below.
 */

const NOW = new Date(2026, 8, 19, 15, 0, 0) // 2026-09-19, matches this repo's own timeline

function json(route: Route, body: unknown) {
  return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
}

function line(over: Partial<OrderLineWire> = {}): OrderLineWire {
  return {
    sku: '9100001',
    quantity: 1,
    name: 'Charizard ex',
    number: '006',
    printing: 'Holo',
    condition: 'Near Mint',
    rarity: 'Rare',
    unit_price: '12.50',
    kind: null,
    ...over,
  }
}

function orderRow(over: Partial<OrderRow> & { lines: OrderLineWire[] }): OrderRow {
  const base: OrderRow = {
    key: `TCGplayer:${over.number ?? 'ORD-0000'}`,
    source: 'TCGplayer',
    number: 'ORD-0000',
    placed_at: '2026-08-01T10:00:00+00:00',
    status: 'Shipped',
    first_seen: '2026-08-01T10:05:00+00:00',
    changed_at: null,
    buyer: 'Ada Lovelace',
    wanted: 1,
    recorded: 1,
    open: false,
    terminal: true,
    progress: [],
    ...over,
  }
  return base
}

function payloadOf(orders: OrderRow[]): OrdersPayload {
  return {
    summary: `${orders.length} order${orders.length === 1 ? '' : 's'}`,
    orders,
    resolution: {
      orders: [],
      counts: { resolved: 0, short: 0, no_copies_on_hand: 0, sku_unknown: 0, sku_unseen: 0, not_a_single: 0 },
    },
  }
}

/** Two Charizard ex orders in July (a real drill-down subject: two orders, two prices), one
 *  Pikachu VMAX order in August, and one order in September whose line carries no name at
 *  all — the SKU-fallback case (defect 2). A Canceled order sits beside them, over a card
 *  named so its ghost would be unmissable if D214's own drop ever broke. */
function generalOrders(): OrderRow[] {
  return [
    orderRow({
      number: 'ORD-1001',
      placed_at: '2026-07-10T10:00:00+00:00',
      status: 'Ready to ship',
      lines: [line({ sku: '9100001', name: 'Charizard ex', quantity: 2, unit_price: '12.50' })],
    }),
    orderRow({
      number: 'ORD-1002',
      placed_at: '2026-07-25T14:00:00+00:00',
      status: 'Shipped',
      lines: [line({ sku: '9100001', name: 'Charizard ex', quantity: 1, unit_price: '12.50' })],
    }),
    orderRow({
      number: 'ORD-1003',
      placed_at: '2026-08-05T09:00:00+00:00',
      status: 'Shipped',
      lines: [line({ sku: '9200002', name: 'Pikachu VMAX', quantity: 2, unit_price: '8.00' })],
    }),
    orderRow({
      number: 'ORD-1004',
      placed_at: '2026-09-02T11:00:00+00:00',
      status: 'Shipped',
      lines: [line({ sku: '9199999', name: null, quantity: 1, unit_price: '3.25' })],
    }),
    orderRow({
      number: 'ORD-1005',
      placed_at: '2026-09-10T11:00:00+00:00',
      status: 'Canceled',
      lines: [line({ sku: '9300003', name: 'Should never appear', quantity: 5, unit_price: '99.00' })],
    }),
  ]
}

function progressOf(over: Partial<OrderLineProgress> & { sku: string }): OrderLineProgress {
  return {
    wanted: 1,
    recorded: 0,
    outstanding: 1,
    over: 0,
    copies: [],
    by_hand: 0,
    reason: null,
    declared_kind: null,
    closed_at: null,
    closed_reason: null,
    at: null,
    ...over,
  }
}

/** `/orders`, plus the two reads this screen now fires ON ARRIVAL (D-sales-rows-by-sku):
 *  the thumbnail lookup and "On the shelf" (moved off its own press, sales-directions.md
 *  finding 3). Every test stubs these through here so `sealEveryTest` sees nothing leak —
 *  neither shape matters to a case that is not testing them, so both default to "nothing
 *  found" rather than a case-specific fixture. */
async function stub(page: Page, orders: OrderRow[]) {
  await page.route(/\/orders$/, (route) => json(route, payloadOf(orders)))
  await page.route(/\/skus\/photos\?/, (route) => json(route, { photos: {} }))
  await page.route(/\/pipeline\/holdings-value\?/, (route) =>
    json(route, {
      range: 'month',
      width_days: 30,
      history_begins: null,
      at: '2026-09-19T00:00:00+00:00',
      on_hand_names: 0,
      series: [],
      totals: [],
      unmarked: { names: 0 },
      sealed_excluded: { names: 0, reason: 'sealed product has no card record' },
    }),
  )
}

/** Stubs `/pipeline/price-now` and counts how many times it was hit — the press-only
 *  contract (`getSoldPrices`'s own header) needs a positive assertion that it was NOT
 *  called on mount. `source` defaults to `'archive'`, matching the real route's own
 *  archive-first order (D225). */
function stubPrices(
  page: Page,
  entries: Record<string, { market: string; at: number; source?: 'archive' | 'live' }>,
) {
  let calls = 0
  const prices = Object.fromEntries(
    Object.entries(entries).map(([sku, e]) => [sku, { source: 'archive' as const, ...e }]),
  )
  page.route(/\/pipeline\/price-now\?/, (route) => {
    calls += 1
    json(route, { prices })
  })
  return () => calls
}

async function open(page: Page, query = ''): Promise<void> {
  await page.goto(`/#/revenue${query}`)
  await expect(page.locator('main.revenue')).toBeVisible()
}

/** Every visible (non-detail) product row's Name cell text, top to bottom, in the order the
 *  table currently draws it — locale-agnostic callers compare this array's own SHAPE (does it
 *  reverse, does it narrow) rather than asserting one hard-coded order. Reads `.bn-datalink`
 *  (the `ProductLink` the name sits inside) rather than the whole `<td>`, so a Foil `Pill`
 *  beside the name never concatenates onto it. */
async function productNames(page: Page): Promise<string[]> {
  return page.locator('.revenue-table tbody tr:not(.revenue-detail-row) td:nth-child(2) .bn-datalink').allInnerTexts()
}

sealEveryTest({ store: true })

test.beforeEach(async ({ page }) => {
  await page.clock.install({ time: NOW })
})

test('no orders at all draws the empty state, not a table with nothing in it', async ({ page }) => {
  await stub(page, [])
  await open(page)
  await expect(page.getByText('Nothing has sold yet.')).toBeVisible()
  await expect(page.locator('table.revenue-table')).toHaveCount(0)
})

test('a failed read draws the failure notice', async ({ page }) => {
  await stub(page, [])
  await page.route(/\/orders$/, (route) => route.abort('addressunreachable'))
  await page.goto('/#/revenue')
  await expect(page.getByText('Could not read your orders')).toBeVisible()
})

test('gross-descending is the default sort, and its column carries aria-sort', async ({ page }) => {
  await stub(page, generalOrders())
  await open(page, '?period=all')
  await expect(page.getByRole('columnheader', { name: 'Gross' })).toHaveAttribute('aria-sort', 'descending')
  await expect(page.getByRole('columnheader', { name: 'Name' })).not.toHaveAttribute('aria-sort', /.+/)
  // Charizard ex ($37.50) > Pikachu VMAX ($16.00) > the SKU fallback ($3.25).
  expect(await productNames(page)).toEqual(['Charizard ex', 'Pikachu VMAX', '9199999'])
})

test('clicking a column sorts by it, and clicking it again reverses the same column', async ({ page }) => {
  await stub(page, generalOrders())
  await open(page, '?period=all')

  await page.getByRole('columnheader', { name: 'Copies' }).getByRole('button').click()
  await expect(page.getByRole('columnheader', { name: 'Copies' })).toHaveAttribute('aria-sort', 'descending')
  // Copies: Charizard 3, Pikachu 2, fallback 1.
  expect(await productNames(page)).toEqual(['Charizard ex', 'Pikachu VMAX', '9199999'])

  await page.getByRole('columnheader', { name: 'Copies' }).getByRole('button').click()
  await expect(page.getByRole('columnheader', { name: 'Copies' })).toHaveAttribute('aria-sort', 'ascending')
  expect(await productNames(page)).toEqual(['9199999', 'Pikachu VMAX', 'Charizard ex'])
})

test('the Name column sorts, and a second click is the exact reverse of the first', async ({ page }) => {
  await stub(page, generalOrders())
  await open(page, '?period=all')

  await page.getByRole('columnheader', { name: 'Name' }).getByRole('button').click()
  const ascending = await productNames(page)
  expect(ascending).toHaveLength(3)

  await page.getByRole('columnheader', { name: 'Name' }).getByRole('button').click()
  const descending = await productNames(page)
  expect(descending).toEqual([...ascending].reverse())
})

test('the search field narrows the product table by name', async ({ page }) => {
  await stub(page, generalOrders())
  await open(page, '?period=all')
  await page.getByPlaceholder('Find what you sold').fill('pikachu')
  expect(await productNames(page)).toEqual(['Pikachu VMAX'])
})

test('a name that fell back to its SKU draws in mono; a real name does not', async ({ page }) => {
  await stub(page, generalOrders())
  await open(page, '?period=all')
  const fallbackRow = page.locator('.revenue-table tbody tr', { hasText: '9199999' })
  await expect(fallbackRow.locator('td').nth(1).locator('.bn-mono')).toHaveText('9199999')
  const realRow = page.locator('.revenue-table tbody tr', { hasText: 'Charizard ex' })
  await expect(realRow.locator('td').nth(1).locator('.bn-mono')).toHaveCount(0)
})

test('clicking a month filters the product table to it, and Clear removes the filter', async ({ page }) => {
  await stub(page, generalOrders())
  await open(page, '?period=all')

  await page.locator('.revenue-month-col', { hasText: 'Jul 2026' }).click()
  await expect(page.locator('.revenue-active-filter')).toContainText('Jul 2026 only')
  expect(await productNames(page)).toEqual(['Charizard ex'])
  await expect(page.locator('.revenue-month-col[aria-pressed="true"]')).toContainText('Jul 2026')

  await page.getByRole('button', { name: 'Clear the month' }).click()
  await expect(page.locator('.revenue-active-filter')).toHaveCount(0)
  expect(await productNames(page)).toHaveLength(3)
})

test('the current month is marked in progress on the strip', async ({ page }) => {
  await stub(page, generalOrders())
  await open(page, '?period=all')
  const current = page.locator('.revenue-month-col[data-current="true"]')
  await expect(current).toContainText('Sep 2026')
  await expect(current).toContainText('so far')
  await expect(page.locator('.revenue-month-col:has-text("so far")')).toHaveCount(1)
})

test('a drill-down opens a product row into the orders behind it, and closes again', async ({ page }) => {
  await stub(page, generalOrders())
  await open(page, '?period=all')

  const row = page.locator('.revenue-table tbody tr', { hasText: 'Charizard ex' })
  const toggle = row.getByRole('button', { name: /orders behind Charizard ex/ })
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')

  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-expanded', 'true')
  const detail = page.locator('.revenue-detail-table')
  await expect(detail).toBeVisible()
  const orderCells = detail.locator('tbody tr td:nth-child(2)')
  await expect(orderCells).toHaveText(['ORD-1002', 'ORD-1001']) // most recent first
  await expect(detail.locator('tbody tr').nth(0).locator('td').nth(2)).toHaveText('1')
  await expect(detail.locator('tbody tr').nth(1).locator('td').nth(2)).toHaveText('2')

  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-expanded', 'false')
  await expect(page.locator('.revenue-detail-table')).toHaveCount(0)
})

test('sort, search and the month filter all round-trip through the URL, including a reload', async ({ page }) => {
  await stub(page, generalOrders())
  await open(page, '?period=all')

  await page.getByRole('columnheader', { name: 'Name' }).getByRole('button').click()
  await page.getByPlaceholder('Find what you sold').fill('char')
  await page.locator('.revenue-month-col', { hasText: 'Jul 2026' }).click()

  await expect(page).toHaveURL(/[?&]sort=name&dir=asc/)
  await expect(page).toHaveURL(/[?&]q=char/)
  await expect(page).toHaveURL(/[?&]month=2026-07/)

  await page.reload()
  await expect(page.locator('main.revenue')).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'Name' })).toHaveAttribute('aria-sort', 'ascending')
  await expect(page.getByPlaceholder('Find what you sold')).toHaveValue('char')
  await expect(page.locator('.revenue-active-filter')).toContainText('Jul 2026 only')
  expect(await productNames(page)).toEqual(['Charizard ex'])
})

test('a same-path query change never scrolls the page back to the top (D201)', async ({ page }) => {
  // A short viewport over this fixture's own content — tall enough that the browser's own
  // scroll clamp cannot read 0 by accident of nothing being scrollable (`D201`'s own case
  // names exactly this trap: a destination short enough to fit the viewport passes for the
  // wrong reason).
  await page.setViewportSize({ width: 390, height: 360 })
  await stub(page, generalOrders())
  await open(page, '?period=all')
  /* THE TABLE FIRST, THEN THE SCROLL (the PR 2 integration's full run, twice under load): a
     scroll sent while the screen still drew its short loading state clamped to 0, and one
     `scrollTo` never repeated, so the wait below timed out before the page was ever tall. */
  await expect(page.getByRole('columnheader', { name: 'Name' })).toBeVisible()
  await expect
    .poll(async () => page.evaluate(() => (window.scrollTo(0, 400), window.scrollY)))
    .toBeGreaterThan(0)
  await page.getByRole('columnheader', { name: 'Name' }).getByRole('button').click()
  const y = await page.evaluate(() => window.scrollY)
  expect(y).toBeGreaterThan(0)
})

test('a custom range shows week buckets for a short span, and states the range in words', async ({ page }) => {
  await stub(page, generalOrders())
  await open(page, '?period=all')

  await page.getByRole('button', { name: 'Custom' }).click()
  await page.getByLabel('From', { exact: true }).fill('2026-09-01')
  // { exact: true }: Playwright's substring match otherwise also finds a missing-photo
  // thumbnail's "no photo" aria-label, which contains "to" (defect fix).
  await page.getByLabel('To', { exact: true }).fill('2026-09-15')

  await expect(page.getByText(/from Sep 1, 2026 to Sep 15, 2026/)).toBeVisible()
  await expect(page.getByRole('heading', { name: 'By week' })).toBeVisible()

  await expect(page).toHaveURL(/[?&]period=custom/)
  await expect(page).toHaveURL(/[?&]from=2026-09-01/)
  await expect(page).toHaveURL(/[?&]to=2026-09-15/)
})

test('a previous period that sums to exactly zero never renders Infinity% or NaN% (defect fix)', async ({ page }) => {
  await stub(page, [
    // The ONLY sale inside the previous (July) window: a real, free line. `previous` sums to
    // exactly 0 while the row itself is not absent — the case `salesOf`'s own finite-price
    // filter would NOT catch, because 0 is a finite number.
    orderRow({
      number: 'ORD-FREE',
      placed_at: '2026-07-15T10:00:00+00:00',
      status: 'Shipped',
      lines: [line({ sku: '9400004', name: 'Promo card', quantity: 1, unit_price: '0.00' })],
    }),
    // The current (August) window: a real, priced sale.
    orderRow({
      number: 'ORD-PAID',
      placed_at: '2026-08-10T10:00:00+00:00',
      status: 'Shipped',
      lines: [line({ sku: '9500005', name: 'Real sale', quantity: 1, unit_price: '5.00' })],
    }),
  ])
  await open(page, '?period=custom&from=2026-08-01&to=2026-08-31')

  const prior = page.locator('.revenue-verdict-prior')
  await expect(prior).toBeVisible()
  const text = await prior.innerText()
  expect(text).not.toContain('Infinity')
  expect(text).not.toContain('NaN')
  expect(text).toContain('$5.00 more')
})

test('the like-for-like wording appears when there is nothing to compare against over the same stretch', async ({ page }) => {
  // Every sale is in 2026 — "this year" compared against the same number of days last year
  // finds nothing there at all, which is a different sentence from finding nothing ever.
  await stub(page, generalOrders())
  await open(page, '?period=ytd')
  await expect(page.locator('.revenue-verdict-prior')).toHaveText(
    'So far, nothing is recorded for the period before this one.',
  )
})

test('no horizontal scroll at 390, with Custom selected — the fifth period option is the widest state', async ({ page }) => {
  // Measured while building this: a fifth Segmented option ("Custom") alone pushed
  // `.bn-head-actions` 11px past 390px width, invisible from the default period alone —
  // the widest state is the one with the extra sort icon's `flex-shrink: 0` PLUS the
  // Custom range fields open, so this checks that state specifically rather than the
  // screen's own resting one.
  await page.setViewportSize({ width: 390, height: 900 })
  await stub(page, generalOrders())
  await open(page, '?period=all')
  await page.getByRole('button', { name: 'Custom' }).click()
  await expect(page.getByLabel('From', { exact: true })).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(0)
})

test('no PAGE horizontal scroll at 390 with the Today column active — it scrolls in its own wrapper', async ({ page }) => {
  // The Today column (D225) is the widest state the product table can be in.
  // `.revenue-table-wrap` is where any overflow belongs, never `document.documentElement`.
  stubPrices(page, { '9100001': { market: '18.00', at: 1_758_000_000 } })
  await page.setViewportSize({ width: 390, height: 900 })
  await stub(page, generalOrders())
  await open(page, '?period=all')
  await page.getByRole('button', { name: "Compare to today's market" }).click()
  await expect(page.locator('.revenue-table thead th', { hasText: 'Today' })).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(0)
})

/* -------------------------------------------------------------- refunds (D225) */

test('a line closed as refunded is subtracted from the total, and the count is stated', async ({ page }) => {
  await stub(page, [
    orderRow({
      number: 'ORD-REAL',
      placed_at: '2026-08-05T10:00:00+00:00',
      status: 'Shipped',
      lines: [line({ sku: '9100001', name: 'Charizard ex', quantity: 1, unit_price: '12.50' })],
    }),
    orderRow({
      number: 'ORD-REFUND',
      placed_at: '2026-08-10T10:00:00+00:00',
      status: 'Shipped',
      lines: [line({ sku: '9200002', name: 'Pikachu VMAX', quantity: 1, unit_price: '20.00' })],
      progress: [progressOf({ sku: '9200002', closed_reason: 'not_shipping' })],
    }),
  ])
  await open(page, '?period=all')
  await expect(page.locator('.revenue-summary-figure')).toContainText('$12.50')
  await expect(page.locator('.revenue-summary-figure')).not.toContainText('$32.50')
  await expect(page.locator('.revenue-verdict-refunded')).toContainText(
    '1 line was marked refunded or canceled during fulfilment and left out.',
  )
  // The two exclusions are NEVER conflated: no order here carries a Canceled status, so
  // that sentence states zero rather than folding this line's count into it.
  await expect(page.locator('.revenue-verdict-canceled')).toHaveText('0 orders were canceled by the marketplace and left out.')
  expect(await productNames(page)).toEqual(['Charizard ex'])
})

test('a line closed for a DIFFERENT reason (shipped_elsewhere) is not excluded', async ({ page }) => {
  await stub(page, [
    orderRow({
      number: 'ORD-1010',
      placed_at: '2026-08-05T10:00:00+00:00',
      status: 'Shipped',
      lines: [line({ sku: '9100001', name: 'Charizard ex', quantity: 1, unit_price: '12.50' })],
      progress: [progressOf({ sku: '9100001', closed_reason: 'shipped_elsewhere' })],
    }),
  ])
  await open(page, '?period=all')
  await expect(page.locator('.revenue-summary-figure')).toContainText('$12.50')
  // BOTH exclusion sentences still render, stating zero plainly rather than staying silent.
  await expect(page.locator('.revenue-verdict-refunded')).toContainText(
    '0 lines were marked refunded or canceled during fulfilment and left out.',
  )
  await expect(page.locator('.revenue-verdict-canceled')).toHaveText('0 orders were canceled by the marketplace and left out.')
})

test('the owner\'s real store has zero not_shipping lines today, and the screen still says so honestly', async ({ page }) => {
  // Measured 2026-09-19: 796 fulfilment lines (739 shipped_elsewhere, 57 null, 0
  // not_shipping) and 56 Canceled orders ($3,059.07). This fixture mirrors that shape —
  // a real shipped_elsewhere line and a real Canceled order, NEITHER of which is a
  // not_shipping line — so the refund sentence has to state zero over real exclusions
  // already happening for OTHER reasons, not merely an empty fixture.
  await stub(page, [
    orderRow({
      number: 'ORD-SHIPPED-ELSEWHERE',
      placed_at: '2026-08-05T10:00:00+00:00',
      status: 'Shipped',
      lines: [line({ sku: '9100001', name: 'Charizard ex', quantity: 1, unit_price: '12.50' })],
      progress: [progressOf({ sku: '9100001', closed_reason: 'shipped_elsewhere' })],
    }),
    orderRow({
      number: 'ORD-CANCELED',
      placed_at: '2026-08-06T10:00:00+00:00',
      status: 'Canceled',
      lines: [line({ sku: '9300003', name: 'Should never appear', quantity: 1, unit_price: '99.00' })],
    }),
  ])
  await open(page, '?period=all')
  await expect(page.locator('.revenue-verdict-canceled')).toHaveText('1 order was canceled by the marketplace and left out.')
  await expect(page.locator('.revenue-verdict-refunded')).toContainText(
    '0 lines were marked refunded or canceled during fulfilment and left out.',
  )
})

/* ------------------------------------------------------------- the lead-string fix (defect) */

test('the prior-period line never says "So far" about the CLOSED prior period (defect fix)', async ({ page }) => {
  // Default period is 6 months: Apr 1 - Oct 1 2026 (nominal), still forming on 2026-09-19.
  // The prior window (Oct 2025 - Apr 2026) is fully CLOSED, so "so far" belongs to the
  // current window and never to this one.
  await stub(page, [
    orderRow({
      number: 'ORD-PRIOR',
      placed_at: '2025-11-01T10:00:00+00:00',
      status: 'Shipped',
      lines: [line({ sku: '9100001', name: 'Charizard ex', quantity: 1, unit_price: '10.00' })],
    }),
    orderRow({
      number: 'ORD-NOW',
      placed_at: '2026-09-05T10:00:00+00:00',
      status: 'Shipped',
      lines: [line({ sku: '9200002', name: 'Pikachu VMAX', quantity: 1, unit_price: '5.00' })],
    }),
  ])
  await open(page)
  const prior = page.locator('.revenue-verdict-prior')
  await expect(prior).toContainText('Over the same stretch, the period before this one made $10.00')
  await expect(prior).not.toContainText('So far, the period before this one made')
})

/* --------------------------------------------------------- then against now (D225) */

test('market comparison is a press, never a mount, and draws a sign and a word (D62)', async ({ page }) => {
  const calls = stubPrices(page, { '9100001': { market: '18.00', at: 1_758_000_000 } })
  await stub(page, [
    orderRow({
      number: 'ORD-1001',
      placed_at: '2026-08-05T10:00:00+00:00',
      status: 'Shipped',
      lines: [line({ sku: '9100001', name: 'Charizard ex', quantity: 1, unit_price: '12.50' })],
    }),
  ])
  await open(page, '?period=all')

  // Never fetched on mount.
  await page.waitForTimeout(200)
  expect(calls()).toBe(0)
  await expect(page.locator('.revenue-table thead th', { hasText: 'Today' })).toHaveCount(0)

  await page.getByRole('button', { name: "Compare to today's market" }).click()
  expect(calls()).toBeGreaterThan(0)

  await expect(page.locator('.revenue-table thead th', { hasText: 'Today' })).toBeVisible()
  const cell = page.locator('.revenue-table tbody tr', { hasText: 'Charizard ex' }).locator('.revenue-market')
  await expect(cell).toContainText('$18.00')
  // A SIGN and a WORD, never a colour (D62) — market is above what it sold for.
  await expect(cell).toContainText('+$5.50 above what it sold for')
  await expect(page.locator('.revenue-market-note')).toContainText('Blind to what any of this cost you')
})

test('a name with no price draws no figure, never a zero, and the coverage is stated', async ({ page }) => {
  stubPrices(page, {}) // neither the archive nor readings has priced anything
  await stub(page, generalOrders())
  await open(page, '?period=all')
  await page.getByRole('button', { name: "Compare to today's market" }).click()
  await expect(page.locator('.revenue-market-none').first()).toHaveText('no reading')
  await expect(page.locator('.revenue-market-none')).toHaveCount(3)
  await expect(page.locator('.revenue-market-note')).toContainText('0 of 3 names have a price today, 3 do not')
})

test('the archive answers first, and a name only readings has priced still draws (fallback)', async ({ page }) => {
  // Charizard ex: an archive `month` bucket. Pikachu VMAX: no archive entry, only a
  // `readings` (live) row — the fallback path, not the primary one.
  stubPrices(page, {
    '9100001': { market: '18.00', at: 1_758_000_000, source: 'archive' },
    '9200002': { market: '9.00', at: 1_758_000_000, source: 'live' },
  })
  await stub(page, generalOrders())
  await open(page, '?period=all')
  await page.getByRole('button', { name: "Compare to today's market" }).click()
  await expect(page.locator('.revenue-market-note')).toContainText('2 of 3 names have a price today, 1 do not')
  const charizard = page.locator('.revenue-table tbody tr', { hasText: 'Charizard ex' }).locator('.revenue-market')
  await expect(charizard).toContainText('$18.00')
  const pikachu = page.locator('.revenue-table tbody tr', { hasText: 'Pikachu VMAX' }).locator('.revenue-market')
  await expect(pikachu).toContainText('$9.00')
})

/* --------------------------------------------------------- rows by SKU (D-sales-rows-by-sku) */

test('a foil and a normal printing sharing a name draw as two rows, never one merged row (defect fix)', async ({ page }) => {
  await stub(page, [
    orderRow({
      number: 'ORD-NORMAL',
      placed_at: '2026-08-05T10:00:00+00:00',
      status: 'Shipped',
      lines: [line({ sku: '9100001', name: 'Charizard ex', condition: 'Near Mint', quantity: 1, unit_price: '12.50' })],
    }),
    orderRow({
      number: 'ORD-FOIL',
      placed_at: '2026-08-06T10:00:00+00:00',
      status: 'Shipped',
      lines: [line({ sku: '9100002', name: 'Charizard ex', condition: 'Near Mint Holofoil', quantity: 1, unit_price: '40.99' })],
    }),
  ])
  await open(page, '?period=all')
  // The old build collapsed these onto one row and compared the wrong printing's price —
  // two SKUs sharing a name now draw as two, both leading with the same name.
  expect(await productNames(page)).toEqual(['Charizard ex', 'Charizard ex'])
  const foilRow = page.locator('.revenue-table tbody tr', { hasText: 'Charizard ex' }).filter({ has: page.getByText('Foil') })
  await expect(foilRow.locator('.bn-money').first()).toHaveText('$40.99')
})

/* ----------------------------------------------------------- the $0.00 line (finding 1) */

test('a line with no price from TCGplayer draws "no price", never a false $0.00 (defect fix)', async ({ page }) => {
  await stub(page, [
    orderRow({
      number: 'ORD-NOPRICE',
      placed_at: '2026-08-05T10:00:00+00:00',
      status: 'Shipped',
      // The feed's own way of saying "no price on this line" — an empty string, not `null`.
      lines: [line({ sku: '9600006', name: 'Sizzlipede', quantity: 1, unit_price: '' })],
    }),
    orderRow({
      number: 'ORD-PRICED',
      placed_at: '2026-08-06T10:00:00+00:00',
      status: 'Shipped',
      lines: [line({ sku: '9100001', name: 'Charizard ex', quantity: 1, unit_price: '12.50' })],
    }),
  ])
  await open(page, '?period=all')
  // Both lines still count as sales — neither is dropped, and the unpriced one is never
  // read as a genuine $0.00 sale.
  expect(await productNames(page)).toEqual(['Charizard ex', 'Sizzlipede'])
  const unpriced = page.locator('.revenue-table tbody tr', { hasText: 'Sizzlipede' })
  await expect(unpriced.locator('.revenue-no-price')).toHaveText('no price')
  await expect(unpriced.locator('.bn-money')).toHaveCount(0)
  await expect(page.locator('.revenue-summary-figure')).toContainText('$12.50')
})

/* --------------------------------------------------------- the shelf spark (round 2 review) */

test('the shelf spark actually paints: its polyline carries a real stroke, not none (defect fix)', async ({ page }) => {
  await stub(page, generalOrders())
  // Override the default empty holdings stub with two real points — `HoldingsSpark` only
  // draws a `<polyline>` once `holdingsSegments` sees 2+ finite values.
  await page.route(/\/pipeline\/holdings-value\?/, (route) =>
    json(route, {
      range: 'month',
      width_days: 30,
      history_begins: '2026-08-01',
      at: '2026-09-19T00:00:00+00:00',
      on_hand_names: 10,
      series: [],
      totals: [
        { start: '2026-08-01', value: '100.00', priced_names: 8, unpriced_names: 2, gap_before: false },
        { start: '2026-09-01', value: '120.00', priced_names: 9, unpriced_names: 1, gap_before: false },
      ],
      unmarked: { names: 0 },
      sealed_excluded: { names: 0, reason: 'sealed product has no card record' },
    }),
  )
  await open(page, '?period=all')
  const polyline = page.locator('.revenue-spark polyline')
  await expect(polyline).toBeVisible()
  const style = await polyline.evaluate((el) => {
    const s = getComputedStyle(el)
    return { stroke: s.stroke, width: parseFloat(s.strokeWidth) }
  })
  expect(style.stroke).not.toBe('none')
  expect(style.width).toBeGreaterThan(0)
})

test('both themes: the table stays usable and sortable in dark', async ({ page }) => {
  await stub(page, generalOrders())
  await page.emulateMedia({ colorScheme: 'dark' })
  await open(page, '?period=all')
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
  await expect(page.locator('main.revenue')).toBeVisible()

  await page.getByRole('columnheader', { name: 'Copies' }).getByRole('button').click()
  await expect(page.getByRole('columnheader', { name: 'Copies' })).toHaveAttribute('aria-sort', 'descending')
  expect(await productNames(page)).toEqual(['Charizard ex', 'Pikachu VMAX', '9199999'])
})
