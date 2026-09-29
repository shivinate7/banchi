// Protects: The Graveyard shows its three tabs with the right cards in each, and Inventory shows where a moved card came from.
// Governs: D134, D196
import { test, expect, type Page } from '@playwright/test'
import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'

/* THE GRAVEYARD'S OWN SPEC, AND `#/inventory`'S "MOVED FROM" — NEITHER HAD ONE (D134, amended
 * by the UX review's graveyard ruling, 2026-09-26, verbatim "Move Moved out of Graveyard").
 *
 * THE OWNER'S REPORT, verbatim: "in graveyard, when i clikc moved or buried i see the same
 * list." Measured on a copy of the owner's real store: 1,358 departed rows, 264 `moved`
 * (every one of them also `buried`, since box 5 — where they all moved out of — was later
 * deleted) and not one `moved` row was ever also sold or retired. `#/graveyard` no longer
 * offers a Moved tab or a Buried tab at all — `buried` is a fact about the BOX, drawn as a
 * quiet tag on the Where cell, never a way a card left.
 *
 * WHAT THIS FILE CAN PROVE, AND WHAT IT CANNOT. `do_graveyard` (`server/capture_server.py`)
 * is what filters `moved` out server-side, and that half is Python, proven by reading the
 * function rather than by a browser. What THIS file proves is the client: given a graveyard
 * answer shaped the way the amended route actually answers (sold and retired rows only, one
 * of them buried), the screen draws exactly three filter tabs, the counts on them are right,
 * and a buried row's tag reads in plain words rather than the pipeline noun "buried" itself
 * (D196). And on `#/inventory`, that a moved-in card's Details panel names where it came
 * from — by the old box's name when that box still stands, and "another box" when it does
 * not, the same honest fallback `Graveyard.tsx`'s own `movedToName` gives `moved_to`.
 *
 * NOT A HARNESS TEST AND MUST NOT BECOME ONE. `docs/GATES.md`'s contract is Python tests at
 * the Stop hook; this starts a browser, alongside `inventory.spec.ts` and `nav.spec.ts`.
 */

// --------------------------------------------------------------------------- the graveyard

const GRAVEYARD_ROUTE = '/#/graveyard'

/** One `GET /graveyard` row, in the amended shape — `how` is `'sold' | 'retired'` only, the
 *  narrowed type `types.ts:DepartedCard` now carries. No `moved_to` either: D134's amendment
 *  removed it as dead weight once a `moved` row can never reach this route. */
function departed(over: {
  how: 'sold' | 'retired'
  name: string
  box: number
  index: number
  boxName: string | null
  buried?: boolean
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
    sku: over.how === 'sold' ? '9191210' : null,
    condition: over.how === 'sold' ? 'Near Mint' : null,
    retire_reason: over.retireReason ?? null,
    order: null,
    run: null,
    captured_at: '2026-09-01T10:00:00+00:00',
    photo_sha256: null,
    buried: over.buried ?? false,
    buried_at: over.buried === true ? '2026-09-26T00:00:00+00:00' : null,
  }
}

/** Two sold, one retired — one of the sold rows buried (its box deleted since). Three
 *  departed rows, never a `moved` one: the amendment's own claim is that a `moved` row can
 *  no longer reach this screen at all, so this fixture is the route's real shape rather than
 *  an adversarial one. */
const GRAVEYARD_ROWS = [
  departed({ how: 'sold', name: 'Volcanion', box: 1, index: 1, boxName: 'Common bulk' }),
  departed({ how: 'retired', name: 'Corviknight', box: 1, index: 2, boxName: 'Common bulk', retireReason: 'damaged' }),
  departed({
    how: 'sold',
    name: 'Ambessa, Respected and Feared',
    box: 3,
    index: 1,
    boxName: 'Old bin',
    buried: true,
  }),
]

async function openGraveyard(page: Page, rows: unknown[] = GRAVEYARD_ROWS): Promise<void> {
  await page.route(/\/graveyard$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ departed: rows }) }),
  )
  await page.goto(GRAVEYARD_ROUTE)
  await settleFonts(page)
  await expect(page.getByRole('heading', { name: 'Graveyard' })).toBeVisible()
}

sealEveryTest()

test('at 820 no header or cell in the table is cut short (screen pass F7)', async ({ page }) => {
  // The wrap is ~690px at 820: seven columns left `Captured` reading "CAPTURE", its cells "28 da…" and
  // the condition "Near Mint …". The two lowest-value columns leave and the rest stay whole.
  await page.setViewportSize({ width: 820, height: 900 })
  await openGraveyard(page, GRAVEYARD_ROWS.map((row) => (row.sku === null ? row : { ...row, condition: 'Near Mint Holofoil' })))
  await expect(page.locator('.graveyard-table tbody tr').first()).toBeVisible()
  const cut = await page.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>('.graveyard-table th, .graveyard-table td, .graveyard-table .graveyard-condition, .graveyard-table .bn-pill')]
      .filter((el) => el.getClientRects().length > 0 && el.scrollWidth > el.clientWidth + 1)
      .map((el) => `${el.tagName}:${(el.textContent ?? '').slice(0, 24)}`),
  )
  expect(cut).toEqual([])
})

test.describe('the graveyard', () => {
  test('exactly three tabs, All/Sold/Retired, with the right counts — no Moved, no Buried', async ({
    page,
  }) => {
    await openGraveyard(page)

    const filters = page.getByRole('group', { name: 'Filter by how a card left' })
    await expect(filters).toBeVisible()
    const tabs = filters.getByRole('button')
    await expect(tabs).toHaveCount(3)

    // COUNTS: 3 departed rows total, 2 sold, 1 retired — the number in each tab's own label.
    await expect(tabs.nth(0)).toHaveText('All (3)')
    await expect(tabs.nth(1)).toHaveText('Sold (2)')
    await expect(tabs.nth(2)).toHaveText('Retired (1)')

    // NO FOURTH OR FIFTH TAB, BY NAME — the amendment's own claim, not only a count. A tab
    // renamed or reordered without changing the count would pass the count check above and
    // still be the regression the owner reported.
    await expect(filters.getByRole('button', { name: /^Moved/ })).toHaveCount(0)
    await expect(filters.getByRole('button', { name: /^Buried/ })).toHaveCount(0)
  })

  test('no moved row is ever drawn', async ({ page }) => {
    await openGraveyard(page)

    const rows = page.locator('.graveyard-row')
    await expect(rows).toHaveCount(3)
    // Not one row's own How pill reads "Moved" — every row this screen draws left through
    // one of the two real doors.
    await expect(page.locator('.graveyard-table').getByText('Moved', { exact: true })).toHaveCount(0)
  })

  test('a buried row draws a plain quiet tag, never the word "buried" itself', async ({ page }) => {
    await openGraveyard(page)

    const buriedRow = page.locator('.graveyard-row', { hasText: 'Ambessa' })
    await expect(buriedRow).toBeVisible()
    await expect(buriedRow.getByText('Its box was deleted')).toBeVisible()
    // D196: the pipeline noun itself never reaches the screen as a typed word.
    await expect(buriedRow.getByText('Buried', { exact: true })).toHaveCount(0)

    // The two rows whose box still stands carry no such tag at all.
    const standingRow = page.locator('.graveyard-row', { hasText: 'Volcanion' })
    await expect(standingRow.getByText('Its box was deleted')).toHaveCount(0)
  })
})

// --------------------------------------------------------------------------- #/inventory

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

async function openInventory(page: Page): Promise<void> {
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
