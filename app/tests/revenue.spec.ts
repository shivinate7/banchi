import { test, expect, type Page, type Route } from '@playwright/test'
import { sealEveryTest } from './shell'

import type { OrderLineWire, OrderRow, OrdersPayload } from '../src/types'

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

async function stub(page: Page, orders: OrderRow[]) {
  await page.route(/\/orders$/, (route) => json(route, payloadOf(orders)))
}

async function open(page: Page, query = ''): Promise<void> {
  await page.goto(`/#/revenue${query}`)
  await expect(page.locator('main.revenue')).toBeVisible()
}

/** Every visible (non-detail) product row's Name cell text, top to bottom, in the order the
 *  table currently draws it — locale-agnostic callers compare this array's own SHAPE (does it
 *  reverse, does it narrow) rather than asserting one hard-coded order. */
async function productNames(page: Page): Promise<string[]> {
  return page.locator('.revenue-table tbody tr:not(.revenue-detail-row) td:nth-child(2)').allInnerTexts()
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

  await page.locator('.revenue-month-row', { hasText: 'Jul 2026' }).click()
  await expect(page.locator('.revenue-active-filter')).toContainText('Jul 2026 only')
  expect(await productNames(page)).toEqual(['Charizard ex'])
  await expect(page.locator('.revenue-month-row[aria-pressed="true"]')).toContainText('Jul 2026')

  await page.getByRole('button', { name: 'Clear' }).click()
  await expect(page.locator('.revenue-active-filter')).toHaveCount(0)
  expect(await productNames(page)).toHaveLength(3)
})

test('the current month is marked in progress on the strip', async ({ page }) => {
  await stub(page, generalOrders())
  await open(page, '?period=all')
  const current = page.locator('.revenue-month-row[data-current="true"]')
  await expect(current).toContainText('Sep 2026')
  await expect(current).toContainText('ongoing')
  await expect(page.locator('.revenue-month-row:has-text("ongoing")')).toHaveCount(1)
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
  await page.locator('.revenue-month-row', { hasText: 'Jul 2026' }).click()

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
  await page.evaluate(() => window.scrollTo(0, 400))
  await page.waitForFunction(() => window.scrollY > 0)
  await page.getByRole('columnheader', { name: 'Name' }).getByRole('button').click()
  const y = await page.evaluate(() => window.scrollY)
  expect(y).toBeGreaterThan(0)
})

test('a custom range shows week buckets for a short span, and states the range in words', async ({ page }) => {
  await stub(page, generalOrders())
  await open(page, '?period=all')

  await page.getByRole('button', { name: 'Custom' }).click()
  await page.getByLabel('From').fill('2026-09-01')
  await page.getByLabel('To').fill('2026-09-15')

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
  await expect(page.getByLabel('From')).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(overflow).toBeLessThanOrEqual(0)
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
