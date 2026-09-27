import { test, expect } from '@playwright/test'

import { sealEveryTest } from './shell'

/* THE OWNER'S "BY SET" VIEW (D293). Read D293 first.
 *
 * `GET /pipeline/sets` IS ALREADY AGGREGATED — grouping, quantities, printed-number order
 * and (as of the 2026-09-27 review) the display name itself are all server work
 * (`server/pipeline_routes.py:do_pipeline_sets`), verified against a `.backup` copy of the
 * owner's own store in that route's own header. What this file can see, that the server-side
 * check cannot, is the CLIENT half: one set on screen at a time, a picker that switches it, a
 * quantity that reads off `qty` rather than off the row count, and a tap that lands on the
 * ordinary box walk through the URL `BoxBrowse.tsx` already reads (`box`/`card`), never a walk
 * this view invents.
 *
 * REBUILT 2026-09-27, TWICE OVER. First for the owner's grid-of-photos rebuild (a picker
 * replaces every set rendering at once under `.bn-section`) — this is the "a set picker"
 * ruling the old "groups by set" case predates, and it is retired below rather than patched,
 * per that ruling. Second for the review round's own fix: the client no longer strips a
 * "CODE: Name" prefix itself, so this file no longer asserts a stripped string — the fixture
 * IS the server's own answer, and it is asserted verbatim.
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
  image_url: string | null
  printing: string | null
}

/** A `SetCard` with `image_url`/`printing` defaulted, so the cases above this one — written
 *  before `D301` — keep reading exactly as they did. */
function setCard(over: Partial<SetCard> & Pick<SetCard, 'sku' | 'cid' | 'box' | 'name' | 'number_display' | 'qty'>): SetCard {
  return { image_url: null, printing: null, ...over }
}

/** The whole `GET /pipeline/sets` shape, one group out of natural-sort order on purpose in
 *  the SOURCE array — this file must not accidentally pass because the server already
 *  happened to send the right order. A rendering that re-sorted, re-grouped, or dropped a
 *  card would show up here; the SORT ITSELF is the server's own subject, checked against the
 *  owner's real store in `do_pipeline_sets`'s own header (2,455 cards, 6 sets, 771 rows, 4
 *  with no set). `set_name` here is what the SERVER would already have resolved (D-review,
 *  2026-09-27) — this file no longer strips anything of its own, so the fixture carries
 *  whatever string a case wants asserted, unstripped or already clean. */
const SETS_PAYLOAD = {
  at: '2026-09-25T00:00:00+00:00',
  groups: [
    {
      game: 'pokemon',
      set_name: 'ME01: Mega Evolution',
      cards: [
        setCard({ sku: '8937200', cid: 'cid-charmander', box: 2, name: 'Charmander', number_display: '004/132', qty: 2 }),
        setCard({ sku: '8937370', cid: 'cid-thievul', box: 2, name: 'Thievul', number_display: '090/132', qty: 1 }),
      ],
    },
    {
      game: 'riftbound',
      set_name: 'Origins',
      cards: [
        setCard({ sku: '8811100', cid: 'cid-darius', box: 5, name: 'Darius, Blade of Origin', number_display: '001/298', qty: 3 }),
        // A REAL ROW WITH NO BOX (D293): a record whose position will not coerce.
        // `box=<n>&card=<cid>` cannot aim the walk at it, so a tap here falls back to the
        // OTHER existing deep link, `?q=<name>`.
        setCard({ sku: '8811101', cid: 'cid-unplaced', box: null, name: 'Unplaced Card', number_display: '005/298', qty: 1 }),
      ],
    },
  ],
  no_set: [
    setCard({ sku: null, cid: 'cid-blank', box: 2, name: null, number_display: null, qty: 1 }),
  ],
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

/** Open the set picker and choose one option by its visible label — the one interaction
 *  every case below needs before it can see a set that is not the default (the first array
 *  entry). `.bn-pick`/`.bn-pick-opt` are the kit's own `Select` classes (`app/src/kit/data.tsx`),
 *  the same ones `inventory.spec.ts`'s box-claim cases already drive. */
async function pickSet(page: import('@playwright/test').Page, label: string): Promise<void> {
  await page.locator('.sets-picker .bn-pick').click()
  await page.locator('.bn-pick-opt', { hasText: label }).click()
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
    // THE MARKET FIGURE ON EACH TILE (`getSoldPrices`, `GET /pipeline/price-now?sku=...`) —
    // fired for every set the picker shows, scoped to that set's own SKUs. Answering none is
    // itself a legal, empty response (`do_pipeline_price_now`'s own "absent, never null"
    // contract), so a tile with no priced answer simply draws no figure; this file's own
    // subject is the picker and the tap, not the number in the corner.
    await page.route(/\/pipeline\/price-now/, (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ prices: {} }) }),
    )
  })

  test('one set is on screen at a time, and the picker switches it', async ({ page }) => {
    // SUPERSEDES the old "groups by set, in the order the server sent" case — the owner's
    // own ruling, "a set picker" (2026-09-26), so every set is no longer rendered at once.
    // Every assertion that case made is still made here, just against one set on screen
    // rather than three at once.
    await page.goto(VIEW_ROUTE)
    await expect(page.getByRole('heading', { name: 'Inventory' })).toBeVisible()

    // THE PICKER ITSELF LISTS EVERY SET, WITH ITS GAME AND COUNT — the owner's ask, "list
    // every set held, with its game and card count."
    await page.locator('.sets-picker .bn-pick').click()
    const options = page.locator('.bn-pick-opt')
    await expect(options).toHaveCount(3) // two named sets, plus "No set on file"
    await expect(options.nth(0)).toContainText('ME01: Mega Evolution')
    await expect(options.nth(0)).toContainText('3') // qty 2 + qty 1
    await expect(options.nth(1)).toContainText('Origins')
    await expect(options.nth(1)).toContainText('4') // qty 3 + qty 1
    await expect(options.nth(2)).toContainText('No set on file')
    await expect(options.nth(2)).toContainText('1')
    await page.keyboard.press('Escape')

    // THE DEFAULT IS THE FIRST SET THE SERVER SENT, AND ONLY ITS OWN CARDS DRAW.
    await expect(page.locator('.sets-header')).toContainText('Pokemon')
    await expect(page.locator('.sets-header')).toContainText('ME01: Mega Evolution')
    const tiles = page.locator('.sets-tile')
    await expect(tiles).toHaveCount(2)
    // ORDER, AS SENT — Charmander before Thievul, the array's own order.
    await expect(tiles.nth(0)).toContainText('Charmander')
    await expect(tiles.nth(0)).toContainText('004/132')
    await expect(tiles.nth(0)).toContainText('2 copies')
    await expect(tiles.nth(1)).toContainText('Thievul')
    await expect(tiles.nth(1)).toContainText('1 copy')
    // THE OTHER SET'S CARDS ARE NOT ON SCREEN AT ALL — the whole point of the picker.
    await expect(page.getByText('Darius, Blade of Origin')).toHaveCount(0)

    // SWITCH TO THE SECOND SET.
    await pickSet(page, 'Origins')
    await expect(page.locator('.sets-header')).toContainText('Riftbound')
    await expect(page.locator('.sets-header')).toContainText('Origins')
    const originsTiles = page.locator('.sets-tile')
    await expect(originsTiles).toHaveCount(2)
    await expect(originsTiles.nth(0)).toContainText('Darius, Blade of Origin')
    await expect(originsTiles.nth(0)).toContainText('3 copies')
    // THE FIRST SET'S CARDS ARE GONE NOW — one set at a time, never a merge of both.
    await expect(page.getByText('Charmander')).toHaveCount(0)

    // A CARD WITH NO SET IS A CHOICE IN THE PICKER TOO, NEVER A SILENT DROP.
    await pickSet(page, 'No set on file')
    await expect(page.locator('.sets-header')).toContainText('No set on file')
    await expect(page.locator('.sets-tile')).toHaveCount(1)
    await expect(page.locator('.sets-tile')).toContainText('Not identified yet')
  })

  test('the stock image is the main view, and two variants sharing one keep their own label', async ({ page }) => {
    // `D301`: several SKUs (a foil and a normal printing) may resolve to the SAME
    // photo — the owner's own addition, mid-build — and this asserts the two rows stay
    // distinguishable by `printing` while sharing that one `image_url`. Removing the `<img>`
    // (or the `printing` pill) from `InventorySets.tsx` turns this red.
    const STOCK_URL = 'https://tcgplayer-cdn.tcgplayer.com/product/705996_200w.jpg'
    // THE BROWSER MUST NEVER REACH TCGCSV OR ANY OTHER OUTSIDE HOST — `sealEveryTest`'s own
    // `sealOutside` refuses every request that is not this checkout's two ports, so the
    // fixture's own `image_url` is answered from a route stub.
    await page.route(STOCK_URL, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'image/svg+xml',
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="63" height="88"><rect width="63" height="88" fill="#ccc"/></svg>',
      }),
    )
    await page.route(/\/pipeline\/sets$/, (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          at: '2026-09-26T00:00:00+00:00',
          groups: [
            {
              game: 'riftbound',
              set_name: 'Vendetta',
              cards: [
                setCard({
                  sku: '705996-normal', cid: 'cid-ahri-normal', box: 5, name: 'Ahri, Inquisitive',
                  number_display: 'SP3/006', qty: 1, image_url: STOCK_URL, printing: null,
                }),
                setCard({
                  sku: '705996-foil', cid: 'cid-ahri-foil', box: 5, name: 'Ahri, Inquisitive',
                  number_display: 'SP3/006', qty: 1, image_url: STOCK_URL, printing: 'Foil',
                }),
              ],
            },
          ],
          no_set: [],
        }),
      }),
    )
    await page.goto(VIEW_ROUTE)

    const tiles = page.locator('.sets-tile')
    await expect(tiles).toHaveCount(2)
    // BOTH TILES DRAW THE SAME PHOTO — never merged or deduped into one row.
    await expect(tiles.nth(0).locator('.sets-card-img')).toHaveAttribute('src', STOCK_URL)
    await expect(tiles.nth(1).locator('.sets-card-img')).toHaveAttribute('src', STOCK_URL)
    // AND EACH KEEPS ITS OWN LABEL — the normal print names none, the foil says so.
    await expect(tiles.nth(0)).not.toContainText('Foil')
    await expect(tiles.nth(1)).toContainText('Foil')
  })

  test('a join miss draws no image, never a guess', async ({ page }) => {
    await page.goto(VIEW_ROUTE)
    // Every row in the default fixture carries `image_url: null` (`setCard`'s own default).
    await expect(page.locator('.sets-card-img')).toHaveCount(0)
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
    // Thievul's set (ME01: Mega Evolution) is already the default, chosen explicitly anyway
    // so this case does not depend on which set the picker happens to open on.
    await pickSet(page, 'ME01: Mega Evolution')
    await page.locator('.sets-tile', { hasText: 'Thievul' }).click()

    // THE URL IS THE WALK'S OWN DEEP LINK (Review's place pill uses the identical shape) —
    // `view` and `set` are gone, `box`/`card` are the pair `BoxBrowse.tsx:wantedCard` already
    // reads.
    await expect(page).toHaveURL(/#\/inventory\?box=2&card=cid-thievul/)
    await expect(page).not.toHaveURL(/[?&]set=/)

    // THE VIEW SWITCH FOLLOWED THE URL, because it reads the same `view` param. One switch
    // serves the walk, the box map (D264) and Sets since the PR 3 integration. Its labels are
    // the owner's, 2026-09-25: "List / Map / Sets".
    const views = page.getByRole('group', { name: 'View' })
    await expect(views.getByRole('button', { name: 'List' })).toHaveAttribute('aria-pressed', 'true')
    await expect(views.getByRole('button', { name: 'Sets' })).toHaveAttribute('aria-pressed', 'false')

    // THE WALK LANDED ON THE NAMED CARD, never merely on the box — `BoxBrowse.tsx`'s own
    // `.browse-row[aria-current]`, the walk's one "this is where you are" mark.
    await expect(page.locator('.browse-row[aria-current="true"]', { hasText: 'Thievul' })).toBeVisible()
  })

  test('a card with no resolvable box is searched by name, never left with nothing to open', async ({ page }) => {
    await page.goto(VIEW_ROUTE)
    // "Unplaced Card" sits in the SECOND set (Origins), never the default — the picker has
    // to switch there before this row exists to click.
    await pickSet(page, 'Origins')
    await page.locator('.sets-tile', { hasText: 'Unplaced Card' }).click()

    // NO box/card PAIR — there is no row this row's own `box: null` could aim the walk at
    // (D293). `q=<name>` is the OTHER existing deep link, D285's own key for a
    // screen's search text, so the tap still lands somewhere useful.
    await expect(page).toHaveURL(/#\/inventory\?q=Unplaced(\+|%20)Card/)
    await expect(page).not.toHaveURL(/[?&]box=/)
    await expect(page).not.toHaveURL(/[?&]card=/)
    await expect(page).not.toHaveURL(/[?&]set=/)

    // AND THE SEARCH FIELD CARRIES THAT TEXT — `BoxBrowse.tsx:qParam`, seeded once on
    // mount, the same store-wide search a person typing the name would have run.
    await expect(page.locator('.search-field-input')).toHaveValue('Unplaced Card')
  })
})
