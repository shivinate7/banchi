// Protects: The section ruler never passes its container and scrolls the current section into view.
// Governs: D155
import { test, expect, type Locator, type Page } from '@playwright/test'
import type { GameRegistry } from '../src/types'
import { sealEveryTest } from './shell'
import { setViewport } from './phoneSwitch'

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
/** A box whose sections differ in size, with the walk's card in `section` at card `card`. */
type PinnedShape = { sizes: readonly number[]; section: number; card: number }

function buildBox(sectionCount: number, cardsPerSection: number, pinAt?: number, pinned?: PinnedShape) {
  const sizes = pinned?.sizes ?? Array.from({ length: sectionCount }, () => cardsPerSection)
  const sections_detail = []
  let start = 1
  for (let s = 1; s <= sizes.length; s += 1) {
    const count = sizes[s - 1] ?? 0
    sections_detail.push({ section: s, start, end: start + count - 1, count })
    start += count
  }
  const boxTotal = start - 1
  const pinSection = pinned?.section ?? 1
  const home = sections_detail[pinSection - 1]!
  const at = pinned?.card ?? pinAt ?? Math.min(17, cardsPerSection)
  const slot = home.start + at - 1
  const card = {
    box: 2,
    index: 1,
    label: `Box 2, Section ${pinSection}, Card ${at}`,
    section: pinSection,
    card: at,
    place: {
      located: true,
      label: `Box 2, Section ${pinSection}, Card ${at}`,
      box: 2,
      index: 1,
      slot,
      section: pinSection,
      card: at,
      box_name: 'WB1 R2',
      section_start: home.start,
      section_end: home.end,
      box_total: boxTotal,
      fraction: (slot - 1) / boxTotal,
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

async function open(
  page: Page,
  sectionCount: number,
  cardsPerSection: number,
  pinAt?: number,
  pinned?: PinnedShape,
) {
  const { card, boxes } = buildBox(sectionCount, cardsPerSection, pinAt, pinned)
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
            names: [card.name],
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
  // Inventory's Deleted boxes shelf reads the burial lines; this store has none.
  await page.route(/\/graveyard(\?.*)?$/, (route) => route.fulfill({ status: 200, contentType: 'application/json', body: '{"departed":[]}' }))
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
      await setViewport(page, { width, height: 900 })
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
    await setViewport(page, { width, height: 900 })
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
  await setViewport(page, { width: 1440, height: 900 })
  await open(page, 12, 5)
  const row = page.locator('.card-locations-row.is-current')
  const sectionTrack = row.locator('.position-bar-owner[data-depth] > .position-bar-track')
  const cardRuler = row.locator('.position-bar-sectiontrack')
  const sectionTop = (await sectionTrack.boundingBox())?.y ?? Infinity
  const cardTop = (await cardRuler.boundingBox())?.y ?? -Infinity
  expect(sectionTop, 'the section ruler sits above the card ruler').toBeLessThan(cardTop)
})


test('a numbered tick within 1 card of the end loses its number (D310)', async ({ page }) => {
  await setViewport(page, { width: 1440, height: 900 })
  await open(page, 3, 21)
  const ruler = page.locator('.card-locations-row.is-current .position-bar-sectiontrack')
  await expect(ruler.locator('.position-bar-tick')).toHaveCount(4)
  await expect(ruler.locator('.position-bar-tick-num')).toHaveText(['10'])
})

test('a long section ticks every 10 and numbers every 50 (D310)', async ({ page }) => {
  await setViewport(page, { width: 1440, height: 900 })
  await open(page, 3, 150)
  const ruler = page.locator('.card-locations-row.is-current .position-bar-sectiontrack')
  await expect(ruler.locator('.position-bar-tick')).toHaveCount(14)
  await expect(ruler.locator('.position-bar-tick-num')).toHaveText(['50', '100'])
})

test('the card ruler ticks every 5th card and numbers every 10th (D310)', async ({ page }) => {
  await setViewport(page, { width: 1440, height: 900 })
  await open(page, 3, 48)
  const ruler = page.locator('.card-locations-row.is-current .position-bar-sectiontrack')
  await expect(ruler.locator('.position-bar-tick')).toHaveCount(9)
  await expect(ruler.locator('.position-bar-tick[data-major]')).toHaveCount(4)
  await expect(ruler.locator('.position-bar-tick-num')).toHaveText(['10', '20', '30', '40'])
  await expect(ruler.locator('.position-bar-chip')).toHaveText('17')
  await expect(page.locator('.card-locations-row.is-current .position-bar-text-box')).toHaveCount(0)
})

/* THE CHIP IS CENTERED ON THE PIN AND CLAMPED INSIDE THE RULER (card-detail spec), so at card 1 and
   at the last card it never crosses the ruler's edge. Measured as boxes, not as a class. */
for (const [label, card] of [['first', 1], ['last', 30]] as const) {
  test(`the number chip stays inside the ruler at the ${label} card`, async ({ page }) => {
    await setViewport(page, { width: 1440, height: 900 })
    await open(page, 1, 30, card)
    const ruler = page.locator('.card-locations-row.is-current .position-bar-sectiontrack')
    const chip = ruler.locator('.position-bar-chip')
    await expect(chip).toHaveText(String(card))
    const r = (await ruler.boundingBox())!
    const c = (await chip.boundingBox())!
    expect(c.x, 'the chip starts inside the ruler').toBeGreaterThanOrEqual(r.x)
    expect(c.x + c.width, 'the chip ends inside the ruler').toBeLessThanOrEqual(r.x + r.width)
  })
}

test('the tick number under or next to the pin is hidden, and the chip sits mid-track', async ({ page }) => {
  await setViewport(page, { width: 1440, height: 900 })
  await open(page, 1, 79, 60)
  const ruler = page.locator('.card-locations-row.is-current .position-bar-sectiontrack')
  await expect(ruler.locator('.position-bar-chip')).toHaveText('60')
  await expect(ruler.locator('.position-bar-tick-num')).toHaveText(['10', '20', '30', '40', '50', '70'])
  const track = (await ruler.boundingBox())!
  const chip = (await ruler.locator('.position-bar-chip').boundingBox())!
  expect(Math.abs(chip.y + chip.height / 2 - (track.y + track.height / 2)), 'chip centred on the track').toBeLessThan(1.5)
})

/* THE PLACE BAR (the owner's screenshot, dark theme, about 820px: WB1 R3, "Section 12 · Card 18
 * of 58", thirteen chips with 12 selected). The box strip draws one chip per section, and a
 * vertical accent bar (`.position-bar-marker`) is drawn over it. In the screenshot the bar sits
 * across chip 11's number, so the chip reads "1|1". `PositionBar.tsx` puts that bar at the
 * card's box fraction (`place.fraction`), and the card's own section is the chip `.position-bar-here`.
 * So the bar's meaning is: it stands on the card's own section chip. */
const OWNER_SHAPE: PinnedShape = {
  sizes: [3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 58, 3],
  section: 12,
  card: 18,
}

type Box = { left: number; right: number; top: number; bottom: number }
type StripGeometry = {
  marker: Box
  here: Box | null
  labels: (Box & { text: string; inStrip: boolean })[]
}

/** Every rectangle is read in the viewport's own frame, so the bar and each chip's number are
 *  compared at the same scroll position. A number's box is its TEXT's box (a Range over the
 *  number), not the chip's, because the chip is wider than its digits. */
async function stripGeometry(track: Locator): Promise<StripGeometry> {
  return track.evaluate((el) => {
    const rect = (r: DOMRect) => ({ left: r.left, right: r.right, top: r.top, bottom: r.bottom })
    const strip = rect(el.getBoundingClientRect())
    // The bar may sit on the track or inside the card's own chip; either way it is this strip's bar.
    const marker = el.querySelector('.position-bar-marker')
    const here = el.querySelector('.position-bar-here')
    const labels = Array.from(el.querySelectorAll('.position-bar-segment-num')).map((node) => {
      const range = document.createRange()
      range.selectNodeContents(node)
      const box = rect(range.getBoundingClientRect())
      return {
        text: node.textContent ?? '',
        ...box,
        inStrip: box.left >= strip.left && box.right <= strip.right,
      }
    })
    return {
      marker: rect(marker!.getBoundingClientRect()),
      here: here === null ? null : rect(here.getBoundingClientRect()),
      labels,
    }
  })
}

/* Each case is a width and a colour scheme. The dark run is the owner's screenshot's theme. */
const PLACE_CASES = [
  [1440, 'light'],
  [820, 'light'],
  [830, 'light'],
  [880, 'light'],
  [1440, 'dark'],
  [820, 'dark'],
  [830, 'dark'],
  [880, 'dark'],
] as const
const CENTER_CASES = [
  [1440, 'light'],
  [820, 'light'],
  [1440, 'dark'],
  [820, 'dark'],
] as const

/** The bar is a mark a reader can see: at least 2px each way, and inside its own chip's box.
 *  A zero-height bar draws nothing, so the overlap check alone cannot tell it from a good one. */
function expectVisibleOnOwnChip(geo: StripGeometry) {
  expect(geo.here, "the card's own section chip is drawn").not.toBeNull()
  const here = geo.here!
  const m = geo.marker
  expect(m.right - m.left, 'the place bar is at least 2px wide').toBeGreaterThanOrEqual(2)
  expect(m.bottom - m.top, 'the place bar is at least 2px tall').toBeGreaterThanOrEqual(2)
  expect(m.left, "the place bar starts inside its own chip").toBeGreaterThanOrEqual(here.left)
  expect(m.right, "the place bar ends inside its own chip").toBeLessThanOrEqual(here.right)
  expect(m.top, "the place bar starts inside its own chip").toBeGreaterThanOrEqual(here.top)
  expect(m.bottom, "the place bar ends inside its own chip").toBeLessThanOrEqual(here.bottom)
}

/* 830 and 880 are measured bands where this fixture's bar crosses a chip number (a width sweep:
 * 790 and 800 cross "8", 830 and 840 cross "9", 880 crosses "10"). 820 exactly does not, so the
 * owner's "about 820" panel sits in one of those bands. */
for (const [width, scheme] of PLACE_CASES) {
  test(`the box strip's place bar crosses no chip number, 13 sections with the card in section 12, ${width}, ${scheme}`, async ({ page }) => {
    await setViewport(page, { width, height: 900 })
    await page.emulateMedia({ colorScheme: scheme })
    await open(page, OWNER_SHAPE.sizes.length, 0, undefined, OWNER_SHAPE)
    const row = page.locator('.card-locations-row.is-current')
    await row.scrollIntoViewIfNeeded()
    const track = row.locator('.position-bar-owner[data-depth] > .position-bar-track')
    await expect(track.locator('.position-bar-segment')).toHaveCount(13)
    await expect(track.locator('.position-bar-here')).toBeInViewport({ ratio: 1 })

    const geo = await stripGeometry(track)
    expectVisibleOnOwnChip(geo)
    const crossing = geo.labels
      .filter(
        (l) =>
          l.inStrip &&
          l.left < geo.marker.right &&
          l.right > geo.marker.left &&
          l.top < geo.marker.bottom &&
          l.bottom > geo.marker.top,
      )
      .map((l) => l.text)
    expect(crossing, "the place bar crosses no chip's number").toEqual([])
  })

  test(`the box strip's place bar stands on the card's own section chip, 13 sections with the card in section 12, ${width}, ${scheme}`, async ({ page }) => {
    await setViewport(page, { width, height: 900 })
    await page.emulateMedia({ colorScheme: scheme })
    await open(page, OWNER_SHAPE.sizes.length, 0, undefined, OWNER_SHAPE)
    const row = page.locator('.card-locations-row.is-current')
    await row.scrollIntoViewIfNeeded()
    const track = row.locator('.position-bar-owner[data-depth] > .position-bar-track')
    await expect(track.locator('.position-bar-here')).toBeInViewport({ ratio: 1 })

    const geo = await stripGeometry(track)
    expectVisibleOnOwnChip(geo)
    const center = (geo.marker.left + geo.marker.right) / 2
    expect(center, "the bar's center is not left of the card's own chip").toBeGreaterThanOrEqual(geo.here!.left)
    expect(center, "the bar's center is not right of the card's own chip").toBeLessThanOrEqual(geo.here!.right)
  })
}

/* THE BAR OVER ITS OWN CHIP'S NUMBER. Card 29 of 58 is the middle of section 12's cells, the
 * place the bar sits nearest the chip's center and so over the number "12". */
const CENTER_SHAPE: PinnedShape = { ...OWNER_SHAPE, card: 29 }

for (const [width, scheme] of CENTER_CASES) {
  test(`the place bar crosses no chip number with the card near its chip's center, 13 sections, ${width}, ${scheme}`, async ({ page }) => {
    await setViewport(page, { width, height: 900 })
    await page.emulateMedia({ colorScheme: scheme })
    await open(page, CENTER_SHAPE.sizes.length, 0, undefined, CENTER_SHAPE)
    const row = page.locator('.card-locations-row.is-current')
    await row.scrollIntoViewIfNeeded()
    const track = row.locator('.position-bar-owner[data-depth] > .position-bar-track')
    await expect(track.locator('.position-bar-here')).toBeInViewport({ ratio: 1 })

    const geo = await stripGeometry(track)
    expectVisibleOnOwnChip(geo)
    const crossing = geo.labels
      .filter(
        (l) =>
          l.inStrip &&
          l.left < geo.marker.right &&
          l.right > geo.marker.left &&
          l.top < geo.marker.bottom &&
          l.bottom > geo.marker.top,
      )
      .map((l) => l.text)
    expect(crossing, "the place bar crosses no chip's number").toEqual([])
  })
}
