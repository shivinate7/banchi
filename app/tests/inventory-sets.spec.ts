import { test, expect } from '@playwright/test'

import { sealEveryTest } from './shell'

/* THE OWNER'S "BY SET" VIEW (D-set-view). Read `docs/decisions/D-set-view.md` first.
 *
 * `GET /pipeline/sets` IS ALREADY AGGREGATED — grouping, quantities and printed-number order
 * are all server work (`server/pipeline_routes.py:do_pipeline_sets`), verified against a
 * `.backup` copy of the owner's own store in that route's own header. What this file can see,
 * that the server-side check cannot, is the CLIENT half: a group renders in the order the
 * server sent it, a quantity reads off `qty` rather than off the row count, and a tap lands on
 * the ordinary box walk through the URL `BoxBrowse.tsx` already reads (`box`/`card`), never a
 * walk this view invents.
 *
 * NOT A HARNESS TEST AND MUST NOT BECOME ONE. `docs/GATES.md`'s contract is Python tests at
 * the Stop hook; this starts a browser, alongside `inventory.spec.ts` and `nav.spec.ts`.
 */

const VIEW_ROUTE = '/#/inventory?view=sets'

type SetCard = {
  sku: string | null
  cid: string | null
  box: number | null
  name: string | null
  number_display: string | null
  qty: number
}

/** The whole `GET /pipeline/sets` shape, one group out of natural-sort order on purpose in
 *  the SOURCE array — this file must not accidentally pass because the server already
 *  happened to send the right order. A rendering that re-sorted, re-grouped, or dropped a
 *  card would show up here; the SORT ITSELF is the server's own subject, checked against the
 *  owner's real store in `do_pipeline_sets`'s own header (2,455 cards, 6 sets, 771 rows, 4
 *  with no set). */
const SETS_PAYLOAD = {
  at: '2026-09-25T00:00:00+00:00',
  groups: [
    {
      game: 'pokemon',
      set_name: 'ME01: Mega Evolution',
      cards: [
        { sku: '8937200', cid: 'cid-charmander', box: 2, name: 'Charmander', number_display: '004/132', qty: 2 },
        { sku: '8937370', cid: 'cid-thievul', box: 2, name: 'Thievul', number_display: '090/132', qty: 1 },
      ] as SetCard[],
    },
    {
      game: 'riftbound',
      set_name: 'Origins',
      cards: [
        { sku: '8811100', cid: 'cid-darius', box: 5, name: 'Darius, Blade of Origin', number_display: '001/298', qty: 3 },
        // A REAL ROW WITH NO BOX (D-set-view): a record whose position will not coerce.
        // `box=<n>&card=<cid>` cannot aim the walk at it, so a tap here falls back to the
        // OTHER existing deep link, `?q=<name>`.
        { sku: '8811101', cid: 'cid-unplaced', box: null, name: 'Unplaced Card', number_display: '005/298', qty: 1 },
      ] as SetCard[],
    },
  ],
  no_set: [
    { sku: null, cid: 'cid-blank', box: 2, name: null, number_display: null, qty: 1 },
  ] as SetCard[],
}

/** A minimal `InventoryCard`, close kin to `shell.ts`'s own private `card()` but carrying
 *  `cid` — the one field that helper leaves off by default (its own comment says why: most
 *  cases there predate D172). This view's whole "tap lands in the walk" case turns on `cid`
 *  matching, so the fixture has to carry it. */
function boxCard(over: { box: number; index: number; name: string | null; sku: string | null; cid: string }) {
  return {
    box: over.box,
    index: over.index,
    label: `Box ${over.box}, Section 1, Card ${over.index}`,
    section: 1,
    card: over.index,
    place: {
      located: true,
      label: `Box ${over.box}, Section 1, Card ${over.index}`,
      box: over.box,
      index: over.index,
      section: 1,
      card: over.index,
      box_name: null,
      section_start: 1,
      section_end: null,
      box_total: 2,
      box_closed: false,
      fraction: over.index,
      neighbors: null,
      section_gaps: 0,
    },
    photo: `photos/${over.box}/${over.index}.jpg`,
    set_hint: 'ME01',
    set_name: 'ME01: Mega Evolution',
    rarity: null,
    metadata_finish: 'normal',
    game: 'pokemon',
    rarity_claim: null,
    note: null,
    captured_at: '2026-09-25T00:00:00+00:00',
    capture_id: `cap-${over.box}-${over.index}`,
    name: over.name,
    number: '090',
    printed_total: '132',
    number_display: '090/132',
    confidence: null,
    sku: over.sku,
    condition: null,
    state: 'identified',
    state_at: '2026-09-25T00:00:00+00:00',
    retire_reason: null,
    cid: over.cid,
  }
}

const BOX_2_CARDS = {
  '2/1': boxCard({ box: 2, index: 1, name: 'Charmander', sku: '8937200', cid: 'cid-charmander' }),
  '2/2': boxCard({ box: 2, index: 2, name: 'Thievul', sku: '8937370', cid: 'cid-thievul' }),
}

test.describe('the set view', () => {
  /* `{ store: true }`: `Inventory.tsx` calls `getOrders()` on mount regardless of which view
   * is showing, and the box-walk case below also needs `getBoxes()`/`getQueues()` answered —
   * `sealEveryTest`'s default (`stubShell` alone) leaves all three unstubbed on purpose, for
   * a spec that never reaches them. This one does. */
  sealEveryTest({ store: true })

  test.beforeEach(async ({ page }) => {
    await page.route(/\/pipeline\/sets$/, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(SETS_PAYLOAD) }),
    )
  })

  test('groups by set, in the order the server sent, with a quantity per card', async ({ page }) => {
    await page.goto(VIEW_ROUTE)
    await expect(page.getByRole('heading', { name: 'Inventory' })).toBeVisible()

    const groups = page.locator('.bn-section')
    await expect(groups).toHaveCount(3) // two named sets, plus "No set on file"

    const first = groups.nth(0)
    await expect(first).toContainText('Pokemon')
    await expect(first).toContainText('ME01: Mega Evolution')
    const firstRows = first.locator('.sets-card-row')
    await expect(firstRows).toHaveCount(2)
    // ORDER, AS SENT — Charmander before Thievul, the array's own order.
    await expect(firstRows.nth(0)).toContainText('Charmander')
    await expect(firstRows.nth(0)).toContainText('004/132')
    await expect(firstRows.nth(0)).toContainText('2 copies')
    await expect(firstRows.nth(1)).toContainText('Thievul')
    await expect(firstRows.nth(1)).toContainText('1 copy')

    const second = groups.nth(1)
    await expect(second).toContainText('Riftbound')
    await expect(second).toContainText('Origins')
    await expect(second).toContainText('Darius, Blade of Origin')
    await expect(second).toContainText('3 copies')

    // A CARD WITH NO SET IS A GROUP, NEVER A SILENT DROP.
    const noSet = groups.nth(2)
    await expect(noSet).toContainText('No set on file')
    await expect(noSet.locator('.sets-card-row')).toHaveCount(1)
    await expect(noSet).toContainText('Not identified yet')
  })

  test('an empty store draws the empty state, not a blank page', async ({ page }) => {
    await page.route(/\/pipeline\/sets$/, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ at: '2026-09-25T00:00:00+00:00', groups: [], no_set: [] }),
      }),
    )
    await page.goto(VIEW_ROUTE)
    await expect(page.getByText('No cards on hand yet')).toBeVisible()
  })

  test('a tap lands on the ordinary box walk, at that card, with Sets left behind', async ({ page }) => {
    await page.route(/\/inventory\/2$/, (route) => {
      if (route.request().method() !== 'GET') return route.fallback()
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ version: 2, cards: BOX_2_CARDS, listings: {} }),
      })
    })
    await page.route(/\/photo\/(by-card\/[\w-]+|\d+\/\d+)/, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="63" height="88"><rect width="63" height="88" fill="#ccc"/></svg>',
      }),
    )

    await page.goto(VIEW_ROUTE)
    await page.locator('.sets-card-row', { hasText: 'Thievul' }).click()

    // THE URL IS THE WALK'S OWN DEEP LINK (Review's place pill uses the identical shape) —
    // `view` is gone, `box`/`card` are the pair `BoxBrowse.tsx:wantedCard` already reads.
    await expect(page).toHaveURL(/#\/inventory\?box=2&card=cid-thievul/)

    // THE VIEW SWITCH FOLLOWED THE URL, because it reads the same `view` param. One switch
    // serves the walk, the Shelf (D264) and Sets since the PR 3 integration.
    const views = page.getByRole('group', { name: 'View' })
    await expect(views.getByRole('button', { name: 'Walk' })).toHaveAttribute('aria-pressed', 'true')
    await expect(views.getByRole('button', { name: 'Sets' })).toHaveAttribute('aria-pressed', 'false')

    // THE WALK LANDED ON THE NAMED CARD, never merely on the box — `BoxBrowse.tsx`'s own
    // `.browse-row[aria-current]`, the walk's one "this is where you are" mark.
    await expect(page.locator('.browse-row[aria-current="true"]', { hasText: 'Thievul' })).toBeVisible()
  })

  test('a card with no resolvable box is searched by name, never left with nothing to open', async ({ page }) => {
    await page.goto(VIEW_ROUTE)
    await page.locator('.sets-card-row', { hasText: 'Unplaced Card' }).click()

    // NO box/card PAIR — there is no row this row's own `box: null` could aim the walk at
    // (D-set-view). `q=<name>` is the OTHER existing deep link, D285's own key for a
    // screen's search text, so the tap still lands somewhere useful.
    await expect(page).toHaveURL(/#\/inventory\?q=Unplaced(\+|%20)Card/)
    await expect(page).not.toHaveURL(/[?&]box=/)
    await expect(page).not.toHaveURL(/[?&]card=/)

    // AND THE SEARCH FIELD CARRIES THAT TEXT — `BoxBrowse.tsx:qParam`, seeded once on
    // mount, the same store-wide search a person typing the name would have run.
    await expect(page.locator('.search-field-input')).toHaveValue('Unplaced Card')
  })
})
