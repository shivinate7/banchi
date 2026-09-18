import { test, expect, type Page } from '@playwright/test'
import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'

/* THE NAME -> VARIANT CHOOSER, PROVEN ON THE OWNER'S OWN TWO COLLISIONS
 * (D-the-set-is-a-stored-fact-and-the-hint-was-never-one).
 *
 * `card-variants.spec.ts` exists apart from `inventory.spec.ts` because its fixture is the
 * point: two SKUs identical in name, number, rarity AND condition, with `set_hint` NULL on
 * both, differing only by `set` — the exact shape measured on the owner's real `Mind Rune`
 * (SKU 9139852 against 9277742) that made the chooser draw two tiles nobody could tell
 * apart. A fixture that gave the chooser an easier field (a populated `set_hint`, a
 * differing number) would prove nothing about the defect it was built to fix.
 *
 * EVERY ASSERTION HERE READS RENDERED TEXT, NEVER THE PROPS PASSED IN. A test that reads the
 * `SearchGroup` object proves the DATA differs; it does not prove the SCREEN shows it — and
 * that gap is the whole reason this task exists (the data always held the set, and the
 * screen never drew it before this item).
 *
 * THREE CASES, ONE FIXTURE:
 *   Mind Rune         two SKUs, set is the ONLY differentiator, set_hint null on both —
 *                     BROKEN before this item, and the case that matters most.
 *   Vanguard Armory    two SKUs, condition is the only differentiator — condition was
 *                     already drawn and already 100% populated on the real store, so this
 *                     is the "prove it already works" case, not a new code path.
 *   Solo Print         one SKU. A single-group search must behave exactly as it did before
 *                     this feature existed: no chooser, no extra press.
 *   Twin Set           two SKUs, TWO DIFFERENT CARD NAMES sharing one `set_hint` — the
 *                     regression case (2026-09-17): a set hint is a fact about the box, not
 *                     the card, and several different cards sharing one must never draw the
 *                     chooser. See `groupsAreSamePrinting` in `BoxBrowse.tsx`.
 */

const NOW = '2026-09-17T12:00:00+00:00'

function place(box: number, section: number, card: number, boxTotal: number) {
  return {
    located: true,
    label: `Box ${box} · Section ${section} · Card ${card}`,
    box,
    index: card,
    section,
    card,
    box_name: null,
    section_start: 1,
    section_end: null,
    box_total: boxTotal,
    box_closed: false,
    fraction: card,
    neighbors: null,
    section_gaps: 0,
  }
}

/** One `InventoryCard` row, in `GET /inventory/<box>`'s own shape. */
function card(over: {
  box: number
  index: number
  name: string
  number: string
  sku: string
  condition: string
  setHint?: string | null
}) {
  return {
    box: over.box,
    index: over.index,
    label: `Box ${over.box} · Section 1 · Card ${over.index}`,
    section: 1,
    card: over.index,
    place: place(over.box, 1, over.index, 5),
    photo: `photos/${over.box}/${over.index}.jpg`,
    set_hint: over.setHint ?? null,
    metadata_finish: 'normal',
    game: 'riftbound',
    rarity_claim: null,
    note: null,
    captured_at: NOW,
    capture_id: `cap-${over.box}-${over.index}`,
    name: over.name,
    number: over.number,
    printed_total: '102',
    confidence: 'high',
    sku: over.sku,
    condition: over.condition,
    state: 'identified',
    state_at: NOW,
    retire_reason: null,
  }
}

const CARDS = {
  '1/1': card({ box: 1, index: 1, name: 'Mind Rune', number: 'R03a', sku: '9139852', condition: 'Near Mint Foil' }),
  '1/2': card({ box: 1, index: 2, name: 'Mind Rune', number: 'R03a', sku: '9277742', condition: 'Near Mint Foil' }),
  '1/3': card({ box: 1, index: 3, name: 'Vanguard Armory', number: '168/221', sku: '9035556', condition: 'Near Mint' }),
  '1/4': card({ box: 1, index: 4, name: 'Vanguard Armory', number: '168/221', sku: '9035561', condition: 'Near Mint Foil' }),
  '1/5': card({ box: 1, index: 5, name: 'Solo Print', number: '001', sku: '9000001', condition: 'Near Mint' }),
  '1/6': card({ box: 1, index: 6, name: 'Twin Alpha', number: '010', sku: '9000010', condition: 'Near Mint', setHint: 'TW01' }),
  '1/7': card({ box: 1, index: 7, name: 'Twin Beta', number: '011', sku: '9000011', condition: 'Near Mint', setHint: 'TW01' }),
}

/** One `SearchGroup`, built directly rather than derived — this spec's whole job is to
 *  assert the SCREEN over data the wire has always been able to send, not to re-derive
 *  `do_search`'s own grouping (T7's `check_set_and_rarity` already proves the wire shape
 *  against the real route). */
function group(over: {
  sku: string
  name: string
  number: string
  set: string | null
  rarity: string | null
  condition: string
  key: string
  box: number
  index: number
  setHint?: string | null
}) {
  return {
    sku: over.sku,
    names: [over.name],
    number: over.number,
    printed_total: '102',
    number_display: `${over.number}/102`,
    set_hint: over.setHint ?? null,
    set: over.set,
    rarity: over.rarity,
    condition: over.condition,
    listed: { pushed: 0, staged: 0, live: 0 },
    sold_here: 0,
    live_as_of: null,
    on_hand: 1,
    listable: 1,
    copies: [
      {
        key: over.key,
        state: 'identified',
        state_at: NOW,
        has_photo: true,
        capture_id: `cap-${over.box}-${over.index}`,
        place: place(over.box, 1, over.index, 5),
      },
    ],
  }
}

const MIND_RUNE = [
  group({ sku: '9139852', name: 'Mind Rune', number: 'R03a', set: 'Spiritforged', rarity: 'Showcase', condition: 'Near Mint Foil', key: '1/1', box: 1, index: 1 }),
  group({ sku: '9277742', name: 'Mind Rune', number: 'R03a', set: 'Unleashed', rarity: 'Showcase', condition: 'Near Mint Foil', key: '1/2', box: 1, index: 2 }),
]

const VANGUARD_ARMORY = [
  group({ sku: '9035556', name: 'Vanguard Armory', number: '168/221', set: 'Origins', rarity: 'Rare', condition: 'Near Mint', key: '1/3', box: 1, index: 3 }),
  group({ sku: '9035561', name: 'Vanguard Armory', number: '168/221', set: 'Origins', rarity: 'Rare', condition: 'Near Mint Foil', key: '1/4', box: 1, index: 4 }),
]

const SOLO_PRINT = [
  group({ sku: '9000001', name: 'Solo Print', number: '001', set: 'Origins', rarity: 'Common', condition: 'Near Mint', key: '1/5', box: 1, index: 5 }),
]

/** Two DIFFERENT cards sharing one `set_hint` — the regression's own shape (the real `ME01`
 *  case has ~110 of these). `names` disagrees across the groups, which is exactly what
 *  `groupsAreSamePrinting` reads to tell this apart from `MIND_RUNE`/`VANGUARD_ARMORY` above. */
const TWIN_SET = [
  group({ sku: '9000010', name: 'Twin Alpha', number: '010', set: null, rarity: null, condition: 'Near Mint', key: '1/6', box: 1, index: 6, setHint: 'TW01' }),
  group({ sku: '9000011', name: 'Twin Beta', number: '011', set: null, rarity: null, condition: 'Near Mint', key: '1/7', box: 1, index: 7, setHint: 'TW01' }),
]

function searchAnswer(query: string): { query: string; groups: unknown[] } {
  const asked = query.trim().toLowerCase()
  if (asked === 'mind rune') return { query, groups: MIND_RUNE }
  if (asked === 'vanguard armory') return { query, groups: VANGUARD_ARMORY }
  if (asked === 'solo print') return { query, groups: SOLO_PRINT }
  if (asked === 'tw01') return { query, groups: TWIN_SET }
  return { query, groups: [] }
}

const PHOTO_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><rect width="1" height="1"/></svg>'

async function open(page: Page): Promise<void> {
  await page.route(/\/photo\/\d+\/\d+/, (route) =>
    route.fulfill({ status: 200, contentType: 'image/svg+xml', body: PHOTO_SVG }),
  )
  await page.route(/\/pipeline\/runs$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ runs: [] }) }),
  )
  await page.route(/\/boxes$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        boxes: [
          {
            box: 1, bid: 1, name: null, sections: [], state: 'open', capacity: 100, fill: 7,
            next_index: 8, cards: 7, on_hand: 7, sold: 0, retired: 0, moved: 0, listed: 0,
            sections_detail: [{ section: 1, start: 1, end: 7, count: 7 }],
          },
        ],
      }),
    }),
  )
  await page.route(/\/inventory\/1$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 2, cards: CARDS, listings: {} }),
    }),
  )
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

sealEveryTest()

test.describe('the name -> variant chooser draws real collisions distinctly', () => {
  test('two SKUs identical but for set, with set_hint null on both, render as two tiles a person could tell apart', async ({ page }) => {
    await open(page)
    await page.getByPlaceholder('Card name, number or SKU').fill('Mind Rune')

    const chooser = page.locator('.browse-variants')
    await expect(chooser).toBeVisible()
    const tiles = chooser.locator('.browse-variant-tile')
    await expect(tiles).toHaveCount(2)

    const texts = await tiles.allTextContents()
    expect(texts).toHaveLength(2)
    // THE ASSERTION THAT MATTERS: the two tiles' own rendered text must differ. Both cards
    // share a name, a number, a rarity and a condition — `set` is the only field that can
    // make these two sentences unequal, and `set_hint` is null on both, so a chooser that
    // fell back to it would draw the same blank on both rows and this would still fail.
    expect(texts[0]).not.toEqual(texts[1])
    expect(texts.join('\n')).toContain('Spiritforged')
    expect(texts.join('\n')).toContain('Unleashed')
  })

  test('two SKUs identical but for condition render as two tiles — already correct, asserted rather than assumed', async ({ page }) => {
    await open(page)
    await page.getByPlaceholder('Card name, number or SKU').fill('Vanguard Armory')

    const chooser = page.locator('.browse-variants')
    await expect(chooser).toBeVisible()
    const tiles = chooser.locator('.browse-variant-tile')
    await expect(tiles).toHaveCount(2)

    const texts = await tiles.allTextContents()
    expect(texts[0]).not.toEqual(texts[1])
    expect(texts.join('\n')).toContain('Near Mint Foil')
    expect(texts.join('\n')).toContain('Near Mint')
  })

  test('a single printing draws no chooser at all — unchanged from before this item', async ({ page }) => {
    await open(page)
    await page.getByPlaceholder('Card name, number or SKU').fill('Solo Print')

    await expect(page.locator('.browse-variants')).toHaveCount(0)
    // It drops straight into the walk: the hero card for the one match is on screen with
    // no extra press.
    await expect(page.getByRole('heading', { name: 'Solo Print' })).toBeVisible()
  })

  test('a set hint shared by two different cards draws no chooser — the walk stays as it was', async ({ page }) => {
    await open(page)
    await page.getByPlaceholder('Card name, number or SKU').fill('TW01')

    // THE REGRESSION: `results.groups.length > 1` used to be the whole test, and two SKUs
    // sharing nothing but a set hint would draw the chooser and swallow the walk underneath
    // it (`app/tests/inventory.spec.ts`'s `ME01` cases, at real scale — ~110 groups there).
    await expect(page.locator('.browse-variants')).toHaveCount(0)

    // Both matched cards are directly in the walk, not behind a pick.
    await expect(page.locator('.browse-row', { hasText: 'Twin Alpha' })).toBeVisible()
    await expect(page.locator('.browse-row', { hasText: 'Twin Beta' })).toBeVisible()
  })
})
