import { test, expect, type Page } from '@playwright/test'
import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'

/* THE LISTING-CORRECTION CONTROL — D252, asserted where nothing else can
 * reach it. `app/src/CardHero.tsx:ListingCorrection` is the one control the owner's ruling
 * asked for: "a 'this answer was wrong' press on Review and inventory." This file is the
 * `#/inventory` half — `CLAUDE.md`'s hard rule again, "a route is not a feature... nothing is
 * built until it is reachable from a screen."
 *
 * ITS OWN MINIMAL BOOT, NOT `inventory.spec.ts`'s. That file's `open()` is a module-private
 * helper built for its own ~150 cases; importing a `.spec.ts` file would re-run every `test()`
 * it registers as a module side effect, so this file stubs the small slice of the shell and the
 * walk that one selected, identified card needs to render — one box, one card (`Thievul`,
 * `8937370`, identified — the same fixture card `inventory.spec.ts` uses), auto-selected on
 * arrival exactly as that file's own cases assert it is.
 *
 * EVERYTHING IS STUBBED AND THE REAL STORE IS NEVER TOUCHED, `inventory.spec.ts`'s own rule:
 * every route is intercepted, including `POST /inventory/2/1/correct` — issuing a real one would
 * put this fixture's SKU into the owner's inventory.
 */

const VIEW_ROUTE = '/#/inventory'

const CARD = {
  box: 2,
  index: 1,
  label: 'Box 2, Section 1, Card 1',
  section: 1,
  card: 1,
  place: {
    located: true,
    label: 'Box 2, Section 1, Card 1',
    box: 2,
    index: 1,
    slot: 1,
    section: 1,
    card: 1,
    box_name: 'ME01 commons',
    section_start: 1,
    section_end: 2,
    box_total: 2,
    box_closed: false,
    fraction: 0,
    neighbors: null,
    section_gaps: 0,
  },
  photo: 'photos/2/1.jpg',
  photo_sha256: null,
  photo_reclaimed_at: null,
  set_hint: 'ME01',
  metadata_finish: 'normal',
  game: 'pokemon',
  set_name: null,
  rarity: null,
  rarity_claim: null,
  note: null,
  captured_at: '2026-08-22T12:34:00+00:00',
  capture_id: 'cap-1',
  name: 'Thievul',
  number: '090',
  printed_total: '132',
  number_display: '090/132',
  confidence: null,
  sku: '8937370',
  condition: 'Near Mint',
  state: 'identified',
  state_at: '2026-08-22T12:34:00+00:00',
  retire_reason: null,
  run: null,
}

const BOXES = {
  boxes: [
    {
      box: 2,
      name: 'ME01 commons',
      sections: [1],
      state: 'open',
      capacity: null,
      fill: 1,
      next_index: 2,
      cards: 1,
      on_hand: 1,
      sold: 0,
      retired: 0,
      moved: 0,
      listed: 0,
      sections_detail: [{ section: 1, start: 1, end: 2, count: 1 }],
    },
  ],
}

const GAMES = {
  games: [{ key: 'pokemon', display: 'Pokémon', located: true, products: [] }],
  default: 'pokemon',
}

/** The row `POST /inventory/2/1/correct` hands back once a catalog row is chosen — one member
 *  of `CorrectResult` (`types.ts`), the shape `CardHero.tsx:ListingCorrection` reads. */
function correctedBody() {
  return {
    position: '2/1',
    box: 2,
    index: 1,
    undone: false,
    sku: '8925897',
    condition: 'Near Mint',
    previous_sku: '8937370',
    released: { pushed: 1 },
    restores_to: { sku: '8937370', condition: 'Near Mint', set_name: null, rarity: null, name: 'Thievul' },
    card: { ...CARD, sku: '8925897', name: 'Adaptatron' },
  }
}

function undoneBody() {
  return {
    position: '2/1',
    box: 2,
    index: 1,
    undone: true,
    sku: '8937370',
    condition: 'Near Mint',
    restores_to: null,
    card: { ...CARD },
  }
}

async function open(page: Page): Promise<void> {
  await page.route(/\/status$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        captures_root: 'captures',
        store: 'inventory/store.sqlite',
        store_exists: true,
        cards: 1,
        states: {},
        queues: { review: 0, parked: 0 },
        next_index: {},
      }),
    })
  })
  await page.route(/\/orders$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ summary: 'no orders', orders: [], resolution: { orders: [], counts: {} } }),
    })
  })
  await page.route(/\/games$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(GAMES) })
  })
  await page.route(/\/boxes(\?.*)?$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(BOXES) })
  })
  await page.route(/\/search\?/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ q: '', groups: [] }),
    })
  })
  await page.route(/\/inventory\/\d+$/, async (route) => {
    const request = route.request()
    if (request.method() !== 'GET') return route.fallback()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 2, cards: { '2/1': CARD }, boxes: {}, listings: {} }),
    })
  })
  await page.route(/\/inventory$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 2, cards: { '2/1': CARD }, boxes: {}, listings: {} }),
    })
  })
  await page.route(/\/pipeline\/runs\/[^/]+\/pricing$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) })
  })
  await page.route(/\/pipeline\/runs$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ runs: [] }) })
  })
  await page.route(/\/queues$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ review: [], parked: [] }),
    })
  })
  await page.route(/\/photo\/(by-card\/[0-9a-f]+|\d+\/\d+)/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="63" height="88"><rect width="63" height="88" fill="#ccc"/></svg>',
    })
  })

  await page.goto(VIEW_ROUTE)
  await settleFonts(page)
  await expect(page.locator('.browse-hero-name')).toHaveText('Thievul')
}

sealEveryTest()

test('the listing-correction control is reachable on #/inventory for a card not in any queue', async ({
  page,
}) => {
  await open(page)

  // D46's own search, reused rather than a second lookup — `GET /review/<box>/<index>/catalog`,
  // stubbed as it would answer for a card in no queue at all (card.run is irrelevant here: the
  // server re-reads its own export, and this test asserts the CLIENT reaches the route, not the
  // export logic T7 already covers).
  let catalogQueries: string[] = []
  await page.route(/\/review\/2\/1\/catalog\?/, async (route) => {
    catalogQueries.push(new URL(route.request().url()).searchParams.get('q') ?? '')
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        box: 2,
        index: 1,
        game: 'riftbound',
        query: '',
        rows: [
          { sku: '8925897', name: 'Adaptatron', set: 'Origins', number: '056/298', condition: 'Near Mint', market: '0.12' },
        ],
        found: 1,
        truncated: false,
      }),
    })
  })

  let corrected: { method: string; body: unknown } | null = null
  let undone: { method: string; body: unknown } | null = null
  await page.route(/\/inventory\/2\/1\/correct$/, async (route) => {
    const request = route.request()
    const body = request.postDataJSON() as { undo?: boolean; sku?: string }
    if (body?.undo === true) {
      undone = { method: request.method(), body }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(undoneBody()) })
    } else {
      corrected = { method: request.method(), body }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(correctedBody()) })
    }
  })

  // The control sits beside the card's identity, inside the Details disclosure this file's
  // sibling already asserts is on screen without a click at desktop width.
  const wrongCard = page.getByRole('button', { name: 'Wrong card?' })
  await expect(wrongCard).toBeVisible()
  await wrongCard.click()

  // Opening the panel fires the empty-query suggestion, D46's arriving-at-the-card case.
  await expect.poll(() => catalogQueries.length).toBeGreaterThan(0)
  await expect(page.getByText('Adaptatron')).toBeVisible()

  await page.getByRole('button', { name: /Adaptatron/ }).click()

  await expect.poll(() => corrected).not.toBeNull()
  expect((corrected as unknown as { body: { sku: string } }).body.sku).toBe('8925897')

  // The receipt, with Undo — `Inventory.tsx`'s own toast shape, reused.
  const toast = page.locator('.bn-toast', { hasText: 'Card corrected' })
  await expect(toast).toBeVisible()
  await expect(toast).toContainText('8937370')
  await expect(toast).toContainText('8925897')

  await toast.getByRole('button', { name: 'Undo' }).click()

  await expect.poll(() => undone).not.toBeNull()
  expect((undone as unknown as { body: { undo: boolean } }).body.undo).toBe(true)
  const undoneToast = page.locator('.bn-toast', { hasText: 'Correction undone' })
  await expect(undoneToast).toBeVisible()
  // The body names the place from the card's own label, never the box and store index alone.
  await expect(undoneToast).toContainText('Box 2, Section 1, Card 1 — back to 8937370')
  await expect(undoneToast).not.toContainText('Box 2, Card 1')
})
