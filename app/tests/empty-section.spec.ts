// Protects: A section with no cards is hidden from the Inventory ruler, its caption and the box header, and stays reachable in the move picker.
import { test, expect, type Page } from '@playwright/test'
import type { GameRegistry } from '../src/types'
import { sealEveryTest } from './shell'

/* F9 (the owner's report, 2026-09-27): "if a section has no cards in it, i don't want it
 * included in my inventory view, i frequently make a section when done capturing that's
 * basically empty, and because it shows in inventory it messes with my reverse count since it
 * doesn't actually exist yet ... i'd really like it (but be careful about this change) if i
 * didn't see for example: WB1 R4 section 11".
 *
 * THIS IS A DISPLAY CHANGE OVER THE WALK'S OWN RULER AND BOX HEADER
 * (`PositionBar.tsx`/`position.ts`'s `nonEmptySections`, and `BoxOps.tsx:BoxIdentity`'s own
 * call to the same function): the section strip, the "Section N of M" caption, and the box
 * header's own track — nothing else. Capture, the Shelf view (`?view=shelf`) and the section
 * move targets read `sections_detail` straight off the wire and are untouched, so the same
 * empty section is proved still reachable through the move picker below.
 *
 * `BoxIdentity` IS NOT "MANAGE BOX" (the review round, 2026-09-27). It is rendered
 * unconditionally in `BoxBrowse.tsx`'s `browse-box-head`, the walk's own always-visible box
 * header — never inside the `BoxOps` sheet that "Manage" opens. The first round of this file
 * asserted its 11 spans as a FEATURE, which the review caught: the header is IN SCOPE and
 * must filter too.
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
 *  Card 30"). `extraBoxes` lets a case add a move DESTINATION beside this one, without
 *  disturbing the walk it stands on. */
function buildBox(extraBoxes: readonly Record<string, unknown>[] = []) {
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
      ...extraBoxes,
    ],
  }
  return { card, boxes }
}

/** A move DESTINATION box, "WB1 R5": two sections, the second declared and never filled — the
 *  same shape as WB1 R4's own eleventh, so a move onto it is a real proof that the section
 *  move target draws an empty section. `div` is required for `BoxOps.tsx:moveTargetSections`'s
 *  own filter (`subbox-capture.md` 1.1); it is unrelated to F9. */
const MOVE_DESTINATION = {
  box: 3,
  name: 'WB1 R5',
  sections: [1, 3],
  state: 'open',
  capacity: null,
  fill: 2,
  next_index: 3,
  cards: 2,
  on_hand: 2,
  sold: 0,
  retired: 0,
  moved: 0,
  listed: 0,
  layout_token: 'tok-r5',
  sections_detail: [
    { section: 1, start: 1, end: 2, count: 2, name: null, div: '1' },
    { section: 2, start: 3, end: null, count: 0, name: null, div: '3' },
  ],
}

async function open(page: Page, extraBoxes: readonly Record<string, unknown>[] = []) {
  const { card, boxes } = buildBox(extraBoxes)
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
  await expect(row.locator('.position-bar-text')).toHaveCount(0)
})

test('the box header hides the same empty section too, and a move target still shows it (F9)', async ({
  page,
}) => {
  const { boxes } = buildBox([MOVE_DESTINATION])
  const wb1r4 = boxes.boxes[0] as { sections_detail: Array<{ section: number; count: number }> }
  const emptySection = wb1r4.sections_detail.find((detail) => detail.section === 11)
  expect(emptySection?.count, 'the fixture’s own section 11 is the empty one').toBe(0)

  await open(page, [MOVE_DESTINATION])

  /* THE HEADER: `BoxOps.tsx:BoxIdentity`'s `.boxops-track` is drawn at the top of the walk's
     open box, ALWAYS — not behind "Manage". It reads the same `sections_detail` through the
     same `nonEmptySections` filter the ruler uses, so it hides section 11 too, before any
     click. */
  const header = page.locator('.browse-box-head .boxops-track')
  await expect(header.locator('.boxops-span')).toHaveCount(10)
  await expect(header).toHaveAccessibleName('WB1 R4, 10 sections')

  /* THE MOVE TARGET: a genuinely untouched surface. `BoxOps.tsx`'s "Move to box" panel reads
     the DESTINATION box's own `sections_detail` directly (`moveTargetSections`), never through
     `spansOf`/`nonEmptySections` — so WB1 R5's own declared-but-empty second section is a real
     "still shown" proof, not a re-assertion of the header this round found wrong. */
  await page.getByRole('button', { name: 'Manage' }).click()
  await page.locator('.boxops-sheet').getByRole('button', { name: 'Move' }).click()
  await page.locator('.bn-field .bn-pick').click()
  await page.locator('.bn-pick-opt', { hasText: 'WB1 R5' }).click()
  const options = page.locator('.bn-section-pick-item')
  await expect(options).toHaveCount(2)
  await expect(options.nth(1)).toContainText('Section 2')
  await expect(options.nth(1)).toContainText('0 cards')
})

/* THE OWNER'S "REVERSE COUNT" MUST NOT COLLAPSE UNDER THE WALK'S OWN FEET (D118, D181): selling
 * the only card of a section empties it to `count: 0`, the same shape as a section that was
 * never filled — but the walk is standing on that exact card when the press happens, so its
 * section must stay drawn, on the ruler and in the header, through the sale. This is
 * `nonEmptySections`'s own "keep current" exemption, proved live rather than read off a
 * fixture that never changes. */

const SALE_GAMES = GAMES

/** Two sections, one card each: section 1 is filler and never sold; section 2 holds the ONE
 *  card the case sells. `sold` toggles what every route answers, so the walk's own re-read
 *  after `Mark sold` (D57) is what proves the exemption, not a second fixture. */
function buildSaleBox(sold: boolean) {
  const onHand = sold ? 1 : 2
  // THE LONE CARD IS INDEX 1, SECTION 1 — `BoxBrowse.tsx:landingOf` lands the walk on the
  // first non-departed row in walk order, so the card this case sells has to be that first
  // row for the walk to be STANDING ON IT already, with no extra click to set the stage.
  const section1Count = sold ? 0 : 1
  const lone = {
    box: 2,
    index: 1,
    label: 'Box 2, Section 1, Card 1',
    section: 1,
    card: sold ? null : 1,
    place: {
      located: true,
      label: 'Box 2, Section 1, Card 1',
      box: 2,
      index: 1,
      slot: sold ? null : 1,
      section: 1,
      card: sold ? null : 1,
      box_name: 'WB1 R4',
      section_start: 1,
      section_end: 1,
      box_total: onHand,
      fraction: sold ? null : 0,
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
    state: sold ? 'sold' : 'identified',
    state_at: '2026-08-22T12:34:00+00:00',
    retire_reason: null,
    run: null,
  }
  const filler = {
    box: 2,
    index: 2,
    label: 'Box 2, Section 2, Card 1',
    section: 2,
    card: 1,
    place: {
      located: true,
      label: 'Box 2, Section 2, Card 1',
      box: 2,
      index: 2,
      slot: onHand,
      section: 2,
      card: 1,
      box_name: 'WB1 R4',
      section_start: 2,
      section_end: 2,
      box_total: onHand,
      fraction: 1,
      neighbors: null,
      section_gaps: 0,
    },
    photo: 'photos/2/2.jpg',
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
    name: 'Filler card',
    number: '001',
    printed_total: '132',
    number_display: '001/132',
    confidence: null,
    sku: 'filler-1',
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
        sections: [1, 2],
        state: 'open',
        capacity: null,
        fill: 2,
        next_index: 3,
        cards: 2,
        on_hand: onHand,
        sold: sold ? 1 : 0,
        retired: 0,
        moved: 0,
        listed: 0,
        sections_detail: [
          { section: 1, start: 1, end: 1, count: section1Count, name: null },
          { section: 2, start: 2, end: 2, count: 1, name: null },
        ],
      },
    ],
  }
  return { filler, lone, boxes }
}

async function openSale(page: Page): Promise<{ sell: () => void }> {
  let sold = false
  const current = () => buildSaleBox(sold)

  await page.route(/\/search\?/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        (() => {
          const { lone } = current()
          return {
            query: '',
            groups: [
              {
                sku: lone.sku,
                name: lone.name,
                number_display: lone.number_display,
                set_hint: lone.set_hint,
                condition: lone.condition,
                copies: [{ key: '2/1', ...lone }],
                on_hand: sold ? 0 : 1,
                listed: { pushed: 0, staged: 0, live: 0, sold_here: sold ? 1 : 0 },
              },
            ],
          }
        })(),
      ),
    }),
  )
  await page.route(/\/games$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(SALE_GAMES) }),
  )
  await page.route(/\/status$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        captures_root: 'captures',
        store: 'inventory/store.sqlite',
        store_exists: true,
        cards: 2,
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
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(current().boxes) }),
  )
  await page.route(/\/inventory\/\d+\/\d+\/sold$/, async (route) => {
    sold = true
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        position: '2/1',
        box: 2,
        index: 1,
        undone: false,
        state: 'sold',
        previous_state: 'identified',
        restores_to: 'identified',
        order_released: null,
        listing: null,
        card: null,
      }),
    })
  })
  await page.route(/\/inventory\/\d+$/, async (route) => {
    if (route.request().method() !== 'GET') return route.fallback()
    const { filler, lone } = current()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 2, cards: { '2/1': lone, '2/2': filler }, listings: {} }),
    })
  })
  await page.route(/\/inventory$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 2, cards: {}, boxes: {}, listings: {} }),
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

  return {
    sell: () => {
      sold = true
    },
  }
}

test('selling the only card of a section keeps that section on the ruler and the header (D118, D181, F9)', async ({
  page,
}) => {
  await openSale(page)

  const row = page.locator('.card-locations-row.is-current')
  const track = row.locator('.position-bar-owner[data-depth] > .position-bar-track')
  const header = page.locator('.browse-box-head .boxops-track')

  // BEFORE: two real sections, both on hand.
  await expect(track.locator('.position-bar-segment')).toHaveCount(2)
  await expect(header.locator('.boxops-span')).toHaveCount(2)

  await row.getByRole('button', { name: 'Mark sold' }).click()

  // THE RE-READ, WAITED FOR RATHER THAN ASSUMED: `toHaveCount(2)` right after the click would
  // pass on the STALE pre-sale DOM alone, before the sale's own re-fetch has landed, and prove
  // nothing about the exemption at all. "1 on hand" is `doSell`'s own `setReloads` bump having
  // reached a fresh `GET /boxes` — the sync point every assertion after this line stands on.
  await expect(page.locator('.browse-box-head .boxops-stat .bn-stat-value').first()).toHaveText('1')

  // AFTER: section 2 is down to zero on hand, and the walk is still standing on the card that
  // just left it — its section must stay drawn on both instruments, not fall to one chip.
  await expect(track.locator('.position-bar-segment')).toHaveCount(2)
  await expect(header.locator('.boxops-span')).toHaveCount(2)
})
