import { test, expect, type Page } from '@playwright/test'
import type { GameRegistry } from '../src/types'
import { sealEveryTest } from './shell'

/* THE SECTION RULER NEVER PASSES ITS CONTAINER — the owner's report, 2026-09-25, box WB1 R2:
 * "sections can pass the width of their container (wb1 R2 has 12 sections but only 11 show on
 * a card's locator)". `PositionBar.css` amends D155 again for it: every chip gets a readable
 * floor (`min-width: 20px` under `[data-depth]`, up from the bare 3px every other span still
 * uses) and the box strip scrolls inside its own track past that floor, rather than the strip
 * spilling past the card's own edge. `PositionBar.tsx` scrolls the current section into view and
 * marks which edge still has more (`data-fade-back`/`data-fade-front`).
 *
 * THIS FILE STUBS ITS OWN MINIMAL FIXTURE rather than importing `inventory.spec.ts`'s — one
 * copy is all a section ruler needs, and the fixture below builds a box of any section count on
 * request, which that file's fixed seven-record box cannot do. */

sealEveryTest()

const PHOTO_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="63" height="88"><rect width="63" height="88" fill="#ccc"/></svg>'

const GAMES: GameRegistry = {
  default: 'pokemon',
  games: [
    {
      key: 'pokemon',
      display: 'Pokémon',
      product_line: 'Pokemon',
      rarities: ['Common'],
      finishes: ['normal'],
      condition_by_finish: { normal: 'Near Mint' },
      finish_by_rarity: { Common: ['normal'] },
      located: true,
      join_key: 'number_over_printed_total',
      prompt: 'pokemon',
      crop_bands: ['title', 'number'],
      card_aspect: 0.716,
      unverified: false,
      catalogued: true,
    },
  ],
  product_game: 'pokemon_code',
  products: [],
}

/** A box of `sectionCount` sections, `cardsPerSection` cards each, with the current card at
 *  section 1 (or its last card, for a section smaller than 17 — the owner's own reported case). */
function buildBox(sectionCount: number, cardsPerSection: number) {
  const sections_detail = []
  let start = 1
  for (let s = 1; s <= sectionCount; s += 1) {
    sections_detail.push({ section: s, start, end: start + cardsPerSection - 1, count: cardsPerSection })
    start += cardsPerSection
  }
  const boxTotal = sectionCount * cardsPerSection
  const at = Math.min(17, cardsPerSection)
  const card = {
    box: 2,
    index: 1,
    label: `Box 2, Section 1, Card ${at}`,
    section: 1,
    card: at,
    place: {
      located: true,
      label: `Box 2, Section 1, Card ${at}`,
      box: 2,
      index: 1,
      slot: at,
      section: 1,
      card: at,
      box_name: 'WB1 R2',
      section_start: 1,
      section_end: cardsPerSection,
      box_total: boxTotal,
      fraction: (at - 1) / boxTotal,
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
    name: 'Mirror Image',
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
  const boxes = {
    boxes: [
      {
        box: 2,
        name: 'WB1 R2',
        sections: sections_detail.map((s) => s.section),
        state: 'open',
        capacity: null,
        fill: boxTotal,
        next_index: boxTotal + 1,
        cards: boxTotal,
        on_hand: boxTotal,
        sold: 0,
        retired: 0,
        moved: 0,
        listed: 0,
        sections_detail,
      },
    ],
  }
  return { card, boxes }
}

async function open(page: Page, sectionCount: number, cardsPerSection: number) {
  const { card, boxes } = buildBox(sectionCount, cardsPerSection)
  const cards = { '2/1': card }

  await page.route(/\/search\?/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        query: '',
        groups: [
          {
            sku: card.sku,
            name: card.name,
            number_display: card.number_display,
            set_hint: card.set_hint,
            condition: card.condition,
            copies: [{ key: '2/1', ...card }],
            on_hand: 1,
            listed: { pushed: 0, staged: 0, live: 0, sold_here: 0 },
          },
        ],
      }),
    }),
  )
  await page.route(/\/games$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(GAMES) }),
  )
  await page.route(/\/status$/, (route) =>
    route.fulfill({
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
    }),
  )
  await page.route(/\/orders$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ summary: 'no orders', orders: [], resolution: { orders: [], counts: {} } }),
    }),
  )
  await page.route(/\/boxes(\?.*)?$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(boxes) }),
  )
  await page.route(/\/inventory\/\d+$/, async (route) => {
    if (route.request().method() !== 'GET') return route.fallback()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 2, cards, listings: {} }),
    })
  })
  await page.route(/\/inventory$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 2, cards, boxes: {}, listings: {} }),
    }),
  )
  await page.route(/\/photo\/(by-card\/[0-9a-f]+|\d+\/\d+)/, (route) =>
    route.fulfill({ status: 200, contentType: 'image/svg+xml', body: PHOTO_SVG }),
  )
  await page.route(/\/pipeline\/runs$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"runs": []}' }),
  )
  await page.route(/\/queues$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ review: [], parked: [] }) }),
  )

  await page.goto('/#/inventory')
  await expect(page.locator('main.inventory')).toBeVisible()
  await expect(page.locator('.card-locations-row.is-current')).toBeVisible({ timeout: 15000 })
}

/** Either the strip fits outright, or the excess is the track's OWN intentional scroll with
 *  the current section fully in view — never an overflow past the card's own edge, and never a
 *  page-level horizontal scroll either way. This is the brief's own "OR", asserted as one
 *  function so both branches are proved the same way at every width and section count. */
async function assertRulerNeverOverflows(page: Page) {
  // THE ROW ITSELF MUST BE ON SCREEN FIRST: `toBeInViewport` reads the PAGE'S viewport, and a
  // row a search plants below the fold reads as ratio 0 for a reason that has nothing to do
  // with the ruler's own scroll track.
  await page.locator('.card-locations-row.is-current').scrollIntoViewIfNeeded()
  const track = page.locator('.card-locations-row.is-current .position-bar-owner[data-depth] > .position-bar-track')
  const info = await track.evaluate((el) => ({ scrollWidth: el.scrollWidth, clientWidth: el.clientWidth }))
  if (info.scrollWidth - info.clientWidth > 1) {
    // THE SCROLL-TRACK BRANCH: the strip is allowed to be wider than its window, because that
    // window scrolls on its own — but the section the walk is standing on must still be the one
    // showing, not scrolled off to prove the mechanism exists and nothing else.
    await expect(track.locator('.position-bar-here')).toBeInViewport({ ratio: 1 })
  }
  const pageScrollWidth = await page.evaluate(() => document.documentElement.scrollWidth)
  const viewportWidth = await page.evaluate(() => window.innerWidth)
  expect(pageScrollWidth, 'no page-level horizontal scroll from the ruler').toBeLessThanOrEqual(viewportWidth)
}

for (const sectionCount of [12, 30]) {
  for (const width of [1440, 820, 390]) {
    test(`the section ruler stays inside its card at ${sectionCount} sections, ${width}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 })
      await open(page, sectionCount, 5)
      await assertRulerNeverOverflows(page)
    })
  }
}

for (const width of [1440, 820, 390]) {
  test(`past the shrink floor, the strip scrolls in its own track and the current section stays fully visible, ${width}`, async ({
    page,
  }) => {
    // 60 sections at 2 cards each: comfortably past the point where 20px-floor chips plus gaps
    // exceed even the widest of these cards, so this is the scroll-track path at every one of
    // them and not the shrink-to-fit one — 1440 and 820 included, not only the 390 phone case.
    await page.setViewportSize({ width, height: 900 })
    await open(page, 60, 2)
    await page.locator('.card-locations-row.is-current').scrollIntoViewIfNeeded()
    const track = page.locator('.card-locations-row.is-current .position-bar-owner[data-depth] > .position-bar-track')
    const info = await track.evaluate((el) => ({ scrollWidth: el.scrollWidth, clientWidth: el.clientWidth }))
    // THE FLOOR IS REAL: 60 chips at the 20px legible minimum cannot fit any of these widths,
    // so this case is proof the SCROLL path is what is carrying it, not a shrink that happened
    // to fit.
    expect(info.scrollWidth).toBeGreaterThan(info.clientWidth + 50)

    const here = track.locator('.position-bar-here')
    await expect(here).toBeInViewport({ ratio: 1 })

    const pageScrollWidth = await page.evaluate(() => document.documentElement.scrollWidth)
    const viewportWidth = await page.evaluate(() => window.innerWidth)
    expect(pageScrollWidth, 'no page-level horizontal scroll from the ruler').toBeLessThanOrEqual(viewportWidth)
  })
}

test('the section ruler is drawn above the card ruler', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await open(page, 12, 5)
  const row = page.locator('.card-locations-row.is-current')
  const sectionTrack = row.locator('.position-bar-owner[data-depth] > .position-bar-track')
  const cardRuler = row.locator('.position-bar-sectiontrack')
  const sectionTop = (await sectionTrack.boundingBox())?.y ?? Infinity
  const cardTop = (await cardRuler.boundingBox())?.y ?? -Infinity
  expect(sectionTop, 'the section ruler sits above the card ruler').toBeLessThan(cardTop)
})

