import { expect, test } from '@playwright/test'
import { sealEveryTest } from './shell'
import type { Page } from '@playwright/test'
import type { GameRegistry } from '../src/types'

/* SUB-BOX CAPTURE, LANE B — the Capture screen's own section picker
 * (docs/specs/subbox-capture.md §5). Lane A (the store, the server, the harness) is proved by
 * `harness/tests/t7_box_map.py:check_capture_into_section`; this file proves the SCREEN: the
 * picked section fills the Section row, `[`/`]` step it, S sends `after` and moves the pick,
 * a stale pick falls back with a plain sentence, and D118 holds (a pick or an S never moves
 * the shutter below it).
 *
 * THE CAMERA IS A CANVAS, exactly as `capture-undo.spec.ts` does it — `useCamera` needs to
 * reach `ready`, which is what the shutter gates on, and nothing here can be a real device.
 */

const GAMES: GameRegistry = {
  default: 'pokemon',
  products: [],
  product_game: 'pokemon_code',
  games: [
    {
      key: 'pokemon',
      display: 'Pokémon',
      product_line: 'Pokemon',
      rarities: ['Common', 'Uncommon', 'Rare'],
      finishes: ['normal', 'holo', 'reverse_holo'],
      condition_by_finish: {
        normal: 'Near Mint',
        holo: 'Near Mint Holofoil',
        reverse_holo: 'Near Mint Reverse Holofoil',
      },
      finish_by_rarity: {
        Common: ['normal'],
        Uncommon: ['normal', 'reverse_holo'],
        Rare: ['normal', 'holo', 'reverse_holo'],
      },
      located: true,
      join_key: 'number_over_printed_total',
      prompt: 'pokemon',
      crop_bands: ['title', 'number'],
      card_aspect: 0.716,
      unverified: false,
      catalogued: true,
    },
  ],
}

type Span = {
  section: number
  start: number
  end: number | null
  count: number
  name: string | null
  div: string
}

/** THREE SECTIONS: 1 (cards 1-5), 2 (cards 6-10), 3 (empty, from card 11). Section 1's own
 *  div is "1" (the box's front, `store/master.py:front_of_box`); section 2's is "6", the key
 *  D260 gives its own first card; section 3's is "11". */
function threeSections(): Span[] {
  return [
    { section: 1, start: 1, end: 5, count: 5, name: null, div: '1' },
    { section: 2, start: 6, end: 10, count: 5, name: 'Rares', div: '6' },
    { section: 3, start: 11, end: null, count: 0, name: null, div: '11' },
  ]
}

const BOX = {
  box: 5,
  bid: 15,
  name: 'Sub-box test',
  sections: [1, 6, 11],
  state: 'open',
  capacity: null,
  fill: 10,
  next_index: 11,
  cards: 10,
  sold: 0,
  retired: 0,
  listed: 0,
  on_hand: 10,
  sections_detail: threeSections(),
}

async function open(
  page: Page,
  options: { spans?: Span[]; boxes?: readonly unknown[] } = {},
): Promise<{ opens: { box: string; after?: string }[]; closes: { box: string; div?: string }[] }> {
  const wire: { opens: { box: string; after?: string }[]; closes: { box: string; div?: string }[] } = {
    opens: [],
    closes: [],
  }
  let spans = options.spans ?? threeSections()

  await page.addInitScript(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 640
    canvas.height = 360
    const context = canvas.getContext('2d')
    if (context !== null) {
      context.fillStyle = 'rgb(180,180,180)'
      context.fillRect(0, 0, 640, 360)
    }
    const stream = canvas.captureStream(30)
    const media = navigator.mediaDevices as unknown as {
      enumerateDevices: () => Promise<unknown[]>
      getUserMedia: () => Promise<MediaStream>
    }
    media.enumerateDevices = async () => [
      { deviceId: 'canvas', kind: 'videoinput', label: 'Canvas Cam Link', groupId: 'g' },
    ]
    media.getUserMedia = async () => stream
  })

  await page.route(/\/games$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(GAMES) }),
  )
  await page.route(/\/status$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ cards: 0, next_index: { '5': 11 } }),
    }),
  )
  const boxRow = () => ({ ...BOX, sections_detail: spans })
  await page.route(/\/boxes$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ boxes: options.boxes ?? [boxRow()] }),
    }),
  )
  await page.route(/\/capture\/sitting$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ open: true, gap_minutes: 30, cards: [] }),
    }),
  )

  let nextIndex = 11
  await page.route(/\/capture$/, (route) => {
    const asked = route.request().postDataJSON() as { section?: string }
    const index = nextIndex
    nextIndex += 1
    // Whatever section the request named, or the last one — read here, never composed
    // twice (subbox-capture.md 1, "never compose a divider key").
    const named = asked.section
    const target = named === undefined ? spans[spans.length - 1]! : spans.find((s) => s.div === named)
    if (target === undefined) {
      return route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({ error: { code: 'section_gone', message: 'That section is gone. Read the box again.' } }),
      })
    }
    spans = spans.map((s) => (s.section === target.section ? { ...s, count: s.count + 1 } : s))
    return route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        box: 5,
        index,
        key: `5/${index}`,
        label: `Box 5, Section ${target.section}, Card ${target.start + target.count}`,
        section: target.section,
        card: target.start + target.count,
        section_div: target.div,
        new_box: false,
        created: true,
        photo: `/tmp/5-${index}.jpg`,
        capture_id: null,
        place: { box_total: 11, located: true, label: `Box 5, Section ${target.section}, Card ${target.start + target.count}` },
      }),
    })
  })

  await page.route(/\/boxes\/5\/sections/, (route) => {
    const method = route.request().method()
    if (method === 'DELETE') {
      const div = new URL(route.request().url()).searchParams.get('div') ?? undefined
      wire.closes.push({ box: '5', div })
      spans = spans.filter((s) => s.div !== div)
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(boxRow()),
      })
    }
    if (method !== 'POST') return route.fallback()
    const body = route.request().postDataJSON() as { after?: string }
    wire.opens.push({ box: '5', after: body.after })
    const afterOrdinal = body.after === undefined ? spans.length : (spans.find((s) => s.div === body.after)?.section ?? spans.length)
    const next: Span[] = []
    for (const s of spans) {
      if (s.section <= afterOrdinal) {
        next.push(s)
        continue
      }
      next.push({ ...s, section: s.section + 1 })
    }
    // The new divider's own key: the card number right after the picked section's last one —
    // a whole number while there is room, exactly `section_tail_key`'s own rule.
    const picked = next.find((s) => s.section === afterOrdinal)!
    const newDiv = String(picked.start + picked.count)
    next.push({ section: afterOrdinal + 1, start: picked.start + picked.count, end: null, count: 0, name: null, div: newDiv })
    next.sort((a, b) => a.section - b.section)
    spans = next
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(boxRow()) })
  })

  await page.route(/\/photo\/\d+\/\d+/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'image/gif',
      body: Buffer.from('R0lGODlhAQABAAAAACw=', 'base64'),
    }),
  )

  await page.goto('/#/capture')
  await expect(page.locator('.capture-row').filter({ hasText: /Finish/ })).toBeVisible()

  await expect(async () => {
    await page.keyboard.press('b')
    await expect(page.locator('.capture-opt').filter({ hasText: /Sub-box test/ })).toBeVisible({
      timeout: 1_000,
    })
  }).toPass({ timeout: 15_000 })
  await page.keyboard.type('5')
  await page.keyboard.press('Enter')
  await page.keyboard.press('v')
  await page.getByLabel('Rig').getByRole('button', { name: 'Open the camera' }).click()
  await page.locator('.capture-opt').filter({ hasText: /Canvas Cam Link/ }).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'Capture card', exact: true })).toBeEnabled()

  return wire
}

function sectionRow(page: Page) {
  return page.locator('.capture-section-slot .capture-row').first()
}

/** Document-relative, never `boundingBox()` — D118's own measure (`capture-undo.spec.ts`
 *  carries the argument: viewport coordinates move with the scroll a field's opening causes,
 *  document coordinates do not). */
async function place(page: Page, selector: string): Promise<{ top: number; height: number }> {
  return page.locator(selector).evaluate((el) => {
    const rect = el.getBoundingClientRect()
    return { top: Math.round(rect.top + window.scrollY), height: Math.round(rect.height) }
  })
}

sealEveryTest()

test('the Section row names the pick, its count and where it physically goes', async ({ page }) => {
  await open(page)

  // The default is the last section — nothing picked yet.
  await expect(sectionRow(page)).toContainText('Section 3 of 3')
  await expect(sectionRow(page)).toContainText('next card 11')

  // Open the list and pick section 2 — its own count and name are on the row.
  await sectionRow(page).click()
  await expect(page.locator('.capture-opt').filter({ hasText: 'Rares' })).toContainText('5 cards')
  await page.locator('.capture-opt').filter({ hasText: /Section 2 of 3/ }).click()

  await expect(sectionRow(page)).toContainText('Section 2 of 3')
  await expect(sectionRow(page)).toContainText('Rares')
  await expect(sectionRow(page)).toContainText('next card 11')
  // NOT THE LAST SECTION: the row says where the card physically goes.
  await expect(sectionRow(page)).toContainText('behind the section 3 divider')
})

test('every capture sends the picked section, and the placed label reads it back', async ({ page }) => {
  await open(page)
  await sectionRow(page).click()
  await page.locator('.capture-opt').filter({ hasText: /Section 2 of 3/ }).click()

  await page.keyboard.press('c')

  await expect(page.locator('.capture-undo-row').first()).toHaveAttribute(
    'aria-label',
    /Box 5, Section 2, Card 11$/,
  )
  // The section's own count moved, off the response — no re-fetch needed for it to show.
  await expect(sectionRow(page)).toContainText('next card 12')
})

test('[ and ] step the pick toward the back and the front', async ({ page }) => {
  await open(page)
  await expect(sectionRow(page)).toContainText('Section 3 of 3')

  await page.keyboard.press('[')
  await expect(sectionRow(page)).toContainText('Section 2 of 3')
  await page.keyboard.press('[')
  await expect(sectionRow(page)).toContainText('Section 1 of 3')
  // Nothing before the back.
  await page.keyboard.press('[')
  await expect(sectionRow(page)).toContainText('Section 1 of 3')

  await page.keyboard.press(']')
  await expect(sectionRow(page)).toContainText('Section 2 of 3')
  await page.keyboard.press(']')
  await page.keyboard.press(']')
  // Nothing past the front.
  await expect(sectionRow(page)).toContainText('Section 3 of 3')
})

test('S in the middle inserts right after the pick, and later sections renumber', async ({ page }) => {
  const wire = await open(page)
  await page.keyboard.press('[')
  await expect(sectionRow(page)).toContainText('Section 2 of 3')

  await page.keyboard.press('s')

  expect(wire.opens).toEqual([{ box: '5', after: '6' }])
  await expect(page.locator('.capture-refused, .capture-note-ok').first()).toContainText('New section')
  await expect(page.locator('.capture-quiet').filter({ hasText: 'Section 3 is now 4' })).toBeVisible()
  // The screen picks the new section.
  await expect(sectionRow(page)).toContainText('Section 3 of 4')
})

test('S at the back is the ordinary S, and sends no `after`', async ({ page }) => {
  const wire = await open(page)
  await page.keyboard.press('s')
  expect(wire.opens).toEqual([{ box: '5', after: undefined }])
  // The ordinary case renumbers nothing.
  await expect(page.locator('.capture-refused, .capture-note-ok').first()).toContainText('New section')
  await expect(page.locator('.capture-quiet').filter({ hasText: /is now/ })).toHaveCount(0)
})

test('a stale pick falls back to the last section, with one plain sentence', async ({ page }) => {
  await page.clock.install()
  await open(page)
  await sectionRow(page).click()
  await page.locator('.capture-opt').filter({ hasText: /Section 2 of 3/ }).click()
  await expect(sectionRow(page)).toContainText('Section 2 of 3')

  // Switch away and back to this box on a fresh mount — the effect that restores a pick
  // reads `boxesSeen` and the box change, so reload is the cleanest way to force it.
  await page.reload()
  await expect(page.locator('.capture-row').filter({ hasText: /Finish/ })).toBeVisible()
  await expect(async () => {
    await page.keyboard.press('b')
    await expect(page.locator('.capture-opt').filter({ hasText: /Sub-box test/ })).toBeVisible({ timeout: 1_000 })
  }).toPass({ timeout: 15_000 })
  await page.keyboard.type('5')
  await page.keyboard.press('Enter')
  // WITHIN THE SITTING: the pick survives a reload.
  await expect(sectionRow(page)).toContainText('Section 2 of 3')

  // PAST THE SITTING (GAP_MINUTES, D164) — the fake clock is only ever advanced.
  await page.clock.runFor(31 * 60_000)
  await page.reload()
  await expect(page.locator('.capture-row').filter({ hasText: /Finish/ })).toBeVisible()
  await expect(async () => {
    await page.keyboard.press('b')
    await expect(page.locator('.capture-opt').filter({ hasText: /Sub-box test/ })).toBeVisible({ timeout: 1_000 })
  }).toPass({ timeout: 15_000 })
  await page.keyboard.type('5')
  await page.keyboard.press('Enter')

  await expect(sectionRow(page)).toContainText('Section 3 of 3')
  await expect(page.locator('.capture-section-slot .capture-refused')).toContainText('the last section')
})

test('the row does not move the shutter below it, on a pick or an S (D118)', async ({ page }) => {
  await open(page)
  const atRest = await place(page, '.capture-shutter')

  await sectionRow(page).click()
  const withListOpen = await place(page, '.capture-shutter')
  await page.locator('.capture-opt').filter({ hasText: /Section 2 of 3/ }).click()
  const afterPick = await place(page, '.capture-shutter')
  // THE POSITION IS D118'S OWN CONCERN, never the shutter's own rendered height — a longer
  // label on the row above it (a section's name, or "behind the section N divider") can
  // shift Chromium's own sub-pixel text rounding by a hair without moving anything at all.
  expect(afterPick.top).toBe(withListOpen.top)
  expect(afterPick.top).toBe(atRest.top)

  await page.keyboard.press('s')
  await expect(page.locator('.capture-refused, .capture-note-ok').first()).toBeVisible()
  const afterS = await place(page, '.capture-shutter')
  expect(afterS.top).toBe(afterPick.top)
})

test('at 390, the row stacks, every target is 40px or more, and nothing scrolls sideways', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await open(page)

  const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth)
  const clientWidth = await page.evaluate(() => document.documentElement.clientWidth)
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 1)

  const row = sectionRow(page)
  await expect(row).toBeVisible()
  const box = await row.boundingBox()
  expect(box?.height ?? 0).toBeGreaterThanOrEqual(40)

  await row.click()
  const options = page.locator('.capture-opt')
  const count = await options.count()
  for (let i = 0; i < count; i += 1) {
    const optBox = await options.nth(i).boundingBox()
    expect(optBox?.height ?? 0).toBeGreaterThanOrEqual(40)
  }
})
