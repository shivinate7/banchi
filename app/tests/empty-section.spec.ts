import { test, expect, type Page } from '@playwright/test'
import type { GameRegistry } from '../src/types'
import { sealEveryTest } from './shell'

/* F9 (the owner's report, 2026-09-27): "if a section has no cards in it, i don't want it
 * included in my inventory view, i frequently make a section when done capturing that's
 * basically empty, and because it shows in inventory it messes with my reverse count since it
 * doesn't actually exist yet ... i'd really like it (but be careful about this change) if i
 * didn't see for example: WB1 R4 section 11".
 *
 * THIS IS A DISPLAY CHANGE OVER THE WALK'S OWN RULER ONLY (`PositionBar.tsx`, `position.ts`):
 * the section strip, the "Section N of M" caption, and nothing else. Capture, Manage box and
 * the section move targets read `sections_detail` straight off the wire and are untouched, so
 * the same box's empty section is proved still reachable there.
 *
 * THIS FILE STUBS ITS OWN MINIMAL FIXTURE, the way `section-ruler.spec.ts` does, rather than
 * importing `inventory.spec.ts`'s fixed box.
 */

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

/** WB1 R4: ten sections of three cards each (30 on hand), and an eleventh the owner opened
 *  after capturing and never filled — the owner's own example, "WB1 R4 section 11". The
 *  current card is the last card of section 10, matching the owner's screenshot ("Section 10 ·
 *  Card 30"). */
function buildBox() {
  const sections_detail = []
  let start = 1
  for (let s = 1; s <= 10; s += 1) {
    sections_detail.push({ section: s, start, end: start + 2, count: 3, name: null })
    start += 3
  }
  sections_detail.push({ section: 11, start, end: null, count: 0, name: null })
  const boxTotal = 30

  const card = {
    box: 2,
    index: 30,
    label: 'Box 2, Section 10, Card 3',
    section: 10,
    card: 3,
    place: {
      located: true,
      label: 'Box 2, Section 10, Card 3',
      box: 2,
      index: 30,
      slot: 30,
      section: 10,
      card: 3,
      box_name: 'WB1 R4',
      section_start: 28,
      section_end: 30,
      box_total: boxTotal,
      fraction: 29 / 30,
      neighbors: null,
      section_gaps: 0,
    },
    photo: 'photos/2/30.jpg',
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
        name: 'WB1 R4',
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

async function open(page: Page) {
  const { card, boxes } = buildBox()
  const cards = { '2/30': card }

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
            copies: [{ key: '2/30', ...card }],
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

test('an empty last section does not draw in the walk strip, and "of N" does not count it (F9)', async ({
  page,
}) => {
  await open(page)
  const row = page.locator('.card-locations-row.is-current')
  const track = row.locator('.position-bar-owner[data-depth] > .position-bar-track')

  // THE STRIP: eleven sections are declared, ten hold a card. Only ten chips draw.
  await expect(track.locator('.position-bar-segment')).toHaveCount(10)
  await expect(track.getByText('11', { exact: true })).toHaveCount(0)

  // "OF N": the empty eleventh section is not the denominator.
  await expect(row.locator('.position-bar-text-box')).toHaveText('Section 10 of 10')
})

test('that same empty section still appears in Capture and Manage box (F9)', async ({ page }) => {
  const { boxes } = buildBox()
  const emptySection = boxes.boxes[0]?.sections_detail.find((detail) => detail.section === 11)
  expect(emptySection?.count, 'the fixture’s own section 11 is the empty one').toBe(0)

  await open(page)
  await page.getByRole('button', { name: 'Manage' }).click()
  // BoxOps.tsx:BoxIdentity draws one chip per DECLARED section (`boxops-span`), off the same
  // `sections_detail` this walk read — eleven, empty section included, because that reading is
  // untouched by this lane.
  await expect(page.locator('.boxops-track .boxops-span')).toHaveCount(11)
  await page.keyboard.press('Escape')

  // Capture's own picker reads `sections_detail` directly too (`CaptureScreen.tsx`), never
  // through `PositionBar`/`position.ts` — proved already, unmodified, by
  // `capture-section.spec.ts`'s own empty-last-section fixture (`threeSections()`'s section 3).
})
