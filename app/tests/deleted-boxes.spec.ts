// Protects: Inventory's Deleted boxes shelf lists the records of deleted boxes, the old Graveyard tab is gone, and a moved card names where it came from.
// Governs: D134, D196, D313
import { test, expect, type Page } from '@playwright/test'
import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'

/* THE DELETED BOXES SHELF, AND `#/inventory`'S "MOVED FROM" (D134 point 5, amended by the owner's
 * ruling "A: delete the tab"; the UX review's ruling "Move Moved out of Graveyard").
 *
 * A sold or retired record outlives its box as a `buried` line, and Inventory's box rail ends with
 * a shelf that reads those lines. This file proves the CLIENT: given an answer shaped the way
 * `GET /graveyard` answers (standing rows and buried rows mixed), the shelf counts and draws the
 * buried ones only, groups them by the box they sat in, opens one in the same card pane every other
 * card uses, and offers none of the card's actions. `do_graveyard` is Python and is proved by the
 * harness. It also proves the tab is gone: the nav has no such row and the old address is the
 * not-found page, which was chosen over a redirect so no route outlives the screen it named.
 *
 * NOT A HARNESS TEST AND MUST NOT BECOME ONE. `docs/GATES.md`'s contract is Python tests at the
 * Stop hook; this starts a browser, alongside `inventory.spec.ts` and `nav.spec.ts`.
 */

function departed(over: {
  how: 'sold' | 'retired'
  name: string
  box: number
  index: number
  boxName: string | null
  buried: boolean
  sku?: string | null
  retireReason?: string | null
}) {
  return {
    left_at: '2026-09-24T10:00:00+00:00',
    how: over.how,
    box: over.box,
    index: over.index,
    box_name: over.boxName,
    name: over.name,
    number: '025',
    game: 'pokemon',
    set_hint: null,
    sku: over.sku ?? null,
    condition: over.sku ? 'Near Mint' : null,
    retire_reason: over.retireReason ?? null,
    order: null,
    run: null,
    captured_at: '2026-09-01T10:00:00+00:00',
    photo_sha256: null,
    buried: over.buried,
    buried_at: over.buried ? '2026-09-26T00:00:00+00:00' : null,
  }
}

/** Two standing rows (they belong to Sales and to Inventory's own shelves) and three buried ones in
 *  two deleted boxes. The shelf counts and draws the three. */
const DEPARTED = [
  departed({ how: 'sold', name: 'Volcanion', box: 1, index: 1, boxName: 'Common bulk', buried: false, sku: '9191210' }),
  departed({ how: 'retired', name: 'Corviknight', box: 1, index: 2, boxName: 'Common bulk', buried: false, retireReason: 'damaged' }),
  departed({ how: 'sold', name: 'Ambessa, Respected and Feared', box: 3, index: 2, boxName: 'Old rares', buried: true, sku: '9191486' }),
  departed({ how: 'retired', name: 'Thievul', box: 3, index: 1, boxName: 'Old rares', buried: true, retireReason: 'miscut' }),
  departed({ how: 'sold', name: 'Eiscue', box: 4, index: 1, boxName: 'Spare bulk', buried: true }),
]

sealEveryTest()

test.describe('the Deleted boxes shelf', () => {
  test('counts the records of deleted boxes only, and ends the rail', async ({ page }) => {
    await openInventory(page, DEPARTED)
    const shelf = page.getByRole('button', { name: 'Records from deleted boxes' })
    await expect(shelf).toBeVisible()
    await expect(shelf).toContainText('3 records')
    // Last in the rail, after every box.
    await expect(page.locator('.browse-boxcell').last()).toHaveAccessibleName('Records from deleted boxes')
  })

  test('is absent when no box was ever deleted', async ({ page }) => {
    await openInventory(page, DEPARTED.filter((row) => !row.buried))
    await expect(page.locator('.browse-boxcell').first()).toBeVisible()
    await expect(page.getByRole('button', { name: 'Records from deleted boxes' })).toHaveCount(0)
  })

  test('a press walks the records by the box they sat in and opens one in the card pane', async ({ page }) => {
    await openInventory(page, DEPARTED)
    await page.getByRole('button', { name: 'Records from deleted boxes' }).click()

    const list = page.getByRole('list', { name: 'Records from deleted boxes' })
    await expect(list.locator('.browse-secttitle')).toHaveText(['Old rares', 'Spare bulk'])
    await expect(list.locator('.browse-row')).toHaveCount(3)
    // Standing rows never reach this shelf.
    await expect(list.getByText('Volcanion')).toHaveCount(0)
    // Slot order inside a box: Thievul (1) before Ambessa (2).
    await expect(list.locator('.browse-row-name').first()).toHaveText('Thievul')

    await expect(page.getByRole('heading', { name: 'Thievul' })).toBeVisible()
    await expect(page.getByText('The photograph went with the box.')).toBeVisible()
    await expect(page.locator('.browse-fact', { hasText: 'Where it sat' })).toContainText('Old rares')
    await expect(page.locator('.browse-fact', { hasText: 'How it left' })).toContainText('Retired, miscut')

    await list.getByRole('button', { name: /Ambessa/ }).click()
    await expect(page.getByRole('heading', { name: 'Ambessa, Respected and Feared' })).toBeVisible()
    await expect(page.getByRole('link', { name: /price history/ })).toHaveAttribute('href', '#/product?sku=9191486')

    // A record with no SKU has no price history to open.
    await list.getByRole('button', { name: /Eiscue/ }).click()
    await expect(page.getByRole('link', { name: /price history/ })).toHaveCount(0)
  })

  test('offers no card action, since a buried record cannot come back', async ({ page }) => {
    await openInventory(page, DEPARTED)
    await page.getByRole('button', { name: 'Records from deleted boxes' }).click()
    await expect(page.getByRole('heading', { name: 'Thievul' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Card actions' })).toHaveCount(0)
    await expect(page.getByText('Mark sold')).toHaveCount(0)
  })

  test('moves nothing above the shelf when it is pressed (D313)', async ({ page }) => {
    await openInventory(page, DEPARTED)
    const first = page.locator('.browse-boxcell').first()
    await expect(first).toBeVisible()
    await page.waitForTimeout(500) // the page's entrance has settled
    const before = await first.boundingBox()
    await page.getByRole('button', { name: 'Records from deleted boxes' }).click()
    await expect(page.getByRole('heading', { name: 'Thievul' })).toBeVisible()
    expect(await first.boundingBox(), 'the first box cell moved when the shelf was pressed').toEqual(before)
  })
})

test.describe('the Graveyard tab is gone', () => {
  test('the nav has no such row, and the old address is the not-found page', async ({ page }) => {
    await openInventory(page)
    await expect(page.locator('.bn-side').getByRole('link', { name: /^Graveyard/ })).toHaveCount(0)
    await page.goto('/#/graveyard')
    await expect(page.getByRole('heading', { name: 'Nothing lives at this address.' })).toBeVisible()
  })
})

// --------------------------------------------------------------------------- moved-from

const PHOTO_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><rect width="1" height="1"/></svg>'

function place(box: number, section: number, card: number, boxTotal: number) {
  return {
    located: true,
    label: `Box ${box}, Section ${section}, Card ${card}`,
    box,
    index: card,
    section,
    card,
    box_name: null,
    section_start: 1,
    section_end: null,
    box_total: boxTotal,
    fraction: card,
    neighbors: null,
    section_gaps: 0,
  }
}

/** One `InventoryCard`, in `GET /inventory/<box>`'s own shape — `card-variants.spec.ts`'s own
 *  fixture shape, plus `moved_from`, the field this whole item is about. */
function invCard(over: {
  box: number
  index: number
  name: string
  movedFrom: string | null
}) {
  return {
    box: over.box,
    index: over.index,
    label: `Box ${over.box}, Section 1, Card ${over.index}`,
    section: 1,
    card: over.index,
    place: place(over.box, 1, over.index, 1),
    photo: `photos/${over.box}/${over.index}.jpg`,
    set_hint: null,
    moved_from: over.movedFrom,
    metadata_finish: 'normal',
    game: 'pokemon',
    rarity_claim: null,
    note: null,
    captured_at: '2026-08-20T10:00:00+00:00',
    capture_id: `cap-${over.box}-${over.index}`,
    name: over.name,
    number: '090',
    printed_total: '202',
    confidence: null,
    sku: null,
    condition: null,
    state: 'identified',
    state_at: '2026-09-15T10:00:00+00:00',
    retire_reason: null,
  }
}

// Box 1 is a standing box a moved-in card can be named from; box 5 is deliberately absent
// from `GET /boxes` below, the same as a box that was deleted after the move.
const INVENTORY_CARDS = {
  '1/1': invCard({ box: 1, index: 1, name: 'Thievul', movedFrom: '2/1' }),
  '1/2': invCard({ box: 1, index: 2, name: 'Sableye', movedFrom: '5/9' }),
  // A CARD CAPTURED WHERE IT STANDS — the negative case: no "Moved from" fact for a card
  // that was never a transplant, only ever null on the wire.
  '1/3': invCard({ box: 1, index: 3, name: 'Eevee', movedFrom: null }),
}

const BOXES = {
  boxes: [
    {
      box: 1, bid: 1, name: 'Common bulk', sections: [], state: 'open', capacity: null,
      fill: 2, next_index: 3, cards: 2, on_hand: 2, sold: 0, retired: 0, moved: 0, listed: 0,
      sections_detail: [{ section: 1, start: 1, end: 2, count: 2 }],
    },
    {
      box: 2, bid: 2, name: 'Rares', sections: [], state: 'open', capacity: null,
      fill: 0, next_index: 1, cards: 0, on_hand: 0, sold: 0, retired: 0, moved: 0, listed: 0,
      sections_detail: [],
    },
    // NO BOX 5 — the moved-from box a later delete removed. `Sableye`'s `moved_from` names
    // `5/9`, which no entry here resolves, on purpose.
  ],
}

function searchAnswer(query: string): { query: string; groups: unknown[] } {
  const asked = query.trim().toLowerCase()
  const bySku = (key: string, card: ReturnType<typeof invCard>) => ({
    sku: null,
    names: [card.name],
    number: card.number,
    printed_total: card.printed_total,
    number_display: `${card.number}/${card.printed_total}`,
    set_hint: null,
    set: null,
    rarity: null,
    condition: null,
    listed: { pushed: 0, staged: 0, live: 0 },
    sold_here: 0,
    live_as_of: null,
    on_hand: 1,
    listable: 1,
    copies: [
      {
        key,
        state: card.state,
        state_at: card.state_at,
        has_photo: true,
        capture_id: card.capture_id,
        place: card.place,
      },
    ],
  })
  if (asked === 'thievul') return { query, groups: [bySku('1/1', INVENTORY_CARDS['1/1'])] }
  if (asked === 'sableye') return { query, groups: [bySku('1/2', INVENTORY_CARDS['1/2'])] }
  if (asked === 'eevee') return { query, groups: [bySku('1/3', INVENTORY_CARDS['1/3'])] }
  return { query, groups: [] }
}

async function openInventory(page: Page, departedRows: unknown[] = []): Promise<void> {
  // Inventory reads the burial lines for its Deleted boxes shelf, so every case answers `GET /graveyard`.
  await page.route(/\/graveyard$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ departed: departedRows }) }),
  )
  await page.route(/\/photo\/\d+\/\d+/, (route) =>
    route.fulfill({ status: 200, contentType: 'image/svg+xml', body: PHOTO_SVG }),
  )
  await page.route(/\/pipeline\/runs$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ runs: [] }) }),
  )
  await page.route(/\/boxes$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(BOXES) }),
  )
  // BOTH BOXES, NOT ONLY THE ONE THE FIRST TEST NEEDS. `BOXES` registers two open boxes
  // (`Common bulk` and the empty `Rares`), and the rail's own recency/prefetch can ask for
  // either one — an unstubbed `/inventory/2` reaches `sealEveryTest`'s catch-all and fails
  // the case with "reads reached the capture server" rather than the assertion under test.
  await page.route(/\/inventory\/\d+$/, (route) => {
    const box = Number(new URL(route.request().url()).pathname.split('/').pop())
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 2, cards: box === 1 ? INVENTORY_CARDS : {}, listings: {} }),
    })
  })
  await page.route(/\/search\?/, (route) => {
    const asked = new URL(route.request().url()).searchParams.get('q') ?? ''
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(searchAnswer(asked)) })
  })
  await page.route(/\/queues$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ review: [], parked: [] }) }),
  )
  await page.route(/\/orders$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ orders: [], updated_at: null }) }),
  )

  await page.goto('/#/inventory')
  await settleFonts(page)
  await expect(page.locator('main').first()).toBeVisible()
}

test.describe('#/inventory names where a moved card came from', () => {
  test('a card moved in from a box that still stands names it', async ({ page }) => {
    await openInventory(page)
    await page.getByPlaceholder('Search').fill('Thievul')

    await expect(page.getByRole('heading', { name: 'Thievul' })).toBeVisible()
    const fact = page.locator('.browse-fact', { hasText: 'Moved from' })
    await expect(fact).toBeVisible()
    await expect(fact).toContainText('Rares')
  })

  test('a card moved in from a box that was since deleted says so honestly', async ({ page }) => {
    await openInventory(page)
    await page.getByPlaceholder('Search').fill('Sableye')

    await expect(page.getByRole('heading', { name: 'Sableye' })).toBeVisible()
    const fact = page.locator('.browse-fact', { hasText: 'Moved from' })
    await expect(fact).toBeVisible()
    await expect(fact).toContainText('another box')
  })

  test('a card never moved carries no such fact at all', async ({ page }) => {
    await openInventory(page)
    await page.getByPlaceholder('Search').fill('Eevee')

    await expect(page.getByRole('heading', { name: 'Eevee' })).toBeVisible()
    await expect(page.locator('.browse-fact', { hasText: 'Moved from' })).toHaveCount(0)
  })
})
