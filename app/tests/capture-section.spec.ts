// Protects: The Capture section picker fills its row, steps with the bracket keys, sends S with the right section, falls back plainly on a stale pick, and never moves the shutter.
// Governs: D118, D128, D164, D260, D264
import { expect, test, type Locator } from '@playwright/test'
import { sealEveryTest } from './shell'
import { stubMatched } from './routeFixtures'
import { settleFonts } from './fontsReady'
import type { Page } from '@playwright/test'
import type { GameRegistry } from '../src/types'
import { setViewport } from './phoneSwitch'
import { afterPaint, settleMotion } from './motionSettled'

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
  layout_token: 'tok1',
}

async function open(
  page: Page,
  options: { spans?: Span[]; boxes?: readonly unknown[]; holdSweep?: boolean; bare?: boolean; sectionBumpsToken?: boolean } = {},
): Promise<{
  opens: { box: string; after?: string }[]
  closes: { box: string; div?: string }[]
  /** The background reader's switch: the bodies `PUT /pipeline/match/sweep` carried, and the
   *  release for its `GET`, which is held from the first request when `holdSweep` is set. */
  sweepPuts: unknown[]
  releaseSweep: () => void
  /** Simulates a re-space this browser never saw — another device's own S or capture.
   *  The next aim at this box that carries the OLD token is refused `section_gone`, exactly
   *  as a real one would be (subbox-capture.md 1). */
  bumpToken: () => void
}> {
  let releaseSweep: () => void = () => undefined
  const sweepGate = options.holdSweep === true ? new Promise<void>((resolve) => (releaseSweep = resolve)) : null
  let sweepOn = false
  const wire: {
    opens: { box: string; after?: string }[]
    closes: { box: string; div?: string }[]
    sweepPuts: unknown[]
    releaseSweep: () => void
    bumpToken: () => void
  } = {
    opens: [],
    closes: [],
    sweepPuts: [],
    releaseSweep: () => releaseSweep(),
    bumpToken: () => {
      token = `tok${++tokenGen}`
    },
  }
  let spans = options.spans ?? threeSections()
  let tokenGen = 1
  let token = 'tok1'

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
  const boxRow = () => ({ ...BOX, sections_detail: spans, layout_token: token })
  await page.route(/\/boxes$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ boxes: options.boxes ?? [boxRow()] }),
    }),
  )
  await page.route(/\/pipeline\/match\/sweep$/, async (route) => {
    const request = route.request()
    if (request.method() === 'PUT') {
      const asked = request.postDataJSON() as { on: boolean }
      wire.sweepPuts.push(asked)
      sweepOn = asked.on
    } else if (sweepGate !== null) await sweepGate
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ on: sweepOn, running: sweepOn, matched: 0 }),
    })
  })
  await page.route(/\/capture\/sitting$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ open: true, gap_minutes: 30, cards: [] }),
    }),
  )

  let nextIndex = 11
  await page.route(/\/capture$/, (route) => {
    const asked = route.request().postDataJSON() as { section?: string; layout_token?: string }
    // Whatever section the request named, or the last one — read here, never composed
    // twice (subbox-capture.md 1, "never compose a divider key").
    const named = asked.section
    // THE RE-SPACE GUARD (subbox-capture.md 1, the Opus review's first finding): a token
    // that no longer matches the box's own refuses exactly like a key the box does not have,
    // whether or not the key itself would still resolve to a real section.
    const target =
      named === undefined
        ? spans[spans.length - 1]!
        : asked.layout_token !== token
          ? undefined
          : spans.find((s) => s.div === named)
    if (target === undefined) {
      return route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({ error: { code: 'section_gone', message: 'That section is gone. Read the box again.' } }),
      })
    }
    // ALLOCATED ONLY ON A SUCCESS — a refused aim burns no index (the wire contract's own
    // promise), and a mismatch test that retried after Keep would otherwise skip one.
    const index = nextIndex
    nextIndex += 1
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
    const body = route.request().postDataJSON() as { after?: string; layout_token?: string }
    wire.opens.push({ box: '5', after: body.after })
    // A real server refuses an S aimed with a token the box has moved past.
    if (options.sectionBumpsToken === true && body.after !== undefined && body.layout_token !== token)
      return route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ error: { code: 'section_gone', message: 'That section is gone. Read the box again.' } }) })
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
    // a whole number while there is room, exactly `section_tail_key`'s own rule. A divider
    // inserted right where an already-empty later section starts lands on that section's OWN
    // number — divs are opaque strings (subbox-capture.md 1), never required to be numerically
    // distinct, so a real server would still hand back two different strings for two different
    // sections. This mock's `-2`/`-3`/… suffix is that same "make it distinct" step, nothing
    // this fixture would otherwise need to model.
    const picked = next.find((s) => s.section === afterOrdinal)!
    const wanted = String(picked.start + picked.count)
    const newDiv = next.some((s) => s.div === wanted) ? `${wanted}-${afterOrdinal}` : wanted
    next.push({ section: afterOrdinal + 1, start: picked.start + picked.count, end: null, count: 0, name: null, div: newDiv })
    next.sort((a, b) => a.section - b.section)
    spans = next
    // A real server re-spaces the box on S: the layout token changes with the new divider.
    if (options.sectionBumpsToken === true) token = `tok${++tokenGen}`
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
  if (options.bare === true) return wire

  await expect(async () => {
    await page.keyboard.press('b')
    await expect(page.locator('.capture-opt').filter({ hasText: /Sub-box test/ })).toBeVisible({
      timeout: 1_000,
    })
  }).toPass({ timeout: 15_000 })
  await page.keyboard.type('5')
  await page.keyboard.press('Enter')
  await page.keyboard.press('v')
  await page.getByLabel('Rig').getByRole('button', { name: 'Connect' }).click()
  await page.locator('.capture-opt').filter({ hasText: /Canvas Cam Link/ }).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'Capture', exact: true })).toBeEnabled()

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
  // NOT THE LAST SECTION: the row says where the card physically goes. Cut from "behind the
  // section N divider" (owner: "over verbiage", it truncated at 390) to "before section N".
  await expect(sectionRow(page)).toContainText('before section 3')
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

/* REVIEWER'S FINDING (Lane J, item 2 follow-up): `patchSectionCount` moved the Section row's
 * own count up on every capture (the test above) but nothing ever moved it back down on an
 * undo — `undoBack` called `patchOnHand` alone. The Section row stayed at the count from a
 * card that no longer existed until the next `GET /boxes`, and D118's own "one number
 * everywhere" ruling (item 2 of this same batch) then fanned that stale number out to the
 * header stat, the Box row and the stage foot too. Fixed by decrementing `patchSectionCount`
 * from the `UndoTarget`'s own `sectionDiv`, the same field the capture handler reads to
 * increment it. */
test('an undo into a picked, non-last section decrements that section too, not only the box (D260)', async ({
  page,
}) => {
  await open(page)
  await sectionRow(page).click()
  await page.locator('.capture-opt').filter({ hasText: /Section 2 of 3/ }).click()

  await expect(sectionRow(page)).toContainText('next card 11')

  await page.keyboard.press('c')
  await expect(sectionRow(page)).toContainText('next card 12')
  // THE SAME NUMBER, EVERYWHERE — item 2's own fix: the odometer's "next card" stat now
  // follows the PICKED section, not the box's bare on-hand count.
  await expect(page.locator('.capture-odo .bn-stat').nth(1).locator('.bn-stat-value')).toHaveText(
    '12',
  )

  // `undoCapture`'s own route — this file's fixture never captures a real photo, so the DELETE
  // it sends is stubbed here rather than in `open()`, which no other case in this file needs.
  await page.route(/\/inventory\/\d+\/\d+$/, (route) => {
    if (route.request().method() !== 'DELETE') return route.fallback()
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ deleted: '5/11', on_hand: 10 }),
    })
  })

  await page.keyboard.press('u')

  // BOTH READ 11 AGAIN — the defect's own shape was these two DISAGREEING: the section stuck
  // at 12 (nothing had ever decremented it) while the box-derived stat already read 11.
  await expect(sectionRow(page)).toContainText('next card 11')
  await expect(page.locator('.capture-odo .bn-stat').nth(1).locator('.bn-stat-value')).toHaveText(
    '11',
  )
})

test('a re-space under the pick halts and offers to keep the section by ordinal (finding 2)', async ({
  page,
}) => {
  const wire = await open(page)
  await sectionRow(page).click()
  await page.locator('.capture-opt').filter({ hasText: /Section 2 of 3/ }).click()
  await expect(sectionRow(page)).toContainText('Rares')

  // Another device re-spaced this box: the token this pick was made against is gone, and
  // the store never explains why over the wire — the token alone says so.
  wire.bumpToken()

  await page.keyboard.press('c')

  // NOTHING WAS WRITTEN, so the halt names that certainty rather than hedging — and there
  // is no bare "Resume captures" for this halt, only its own two named actions.
  await expect(page.locator('.capture-halt')).toContainText('section 2 (Rares) changed after a re-space')
  await expect(page.locator('.capture-halt')).toContainText('Nothing was written')
  await expect(page.getByRole('button', { name: 'Resume captures' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Keep Rares' }).click()

  // The pick is re-armed at the SAME ordinal (its div would differ after a real re-space;
  // this fixture only bumps the token, so the row still names the same section), and the
  // halt is gone — the press answered it.
  await expect(page.locator('.capture-halt')).toHaveCount(0)
  await expect(sectionRow(page)).toContainText('Section 2 of 3')
  await expect(sectionRow(page)).toContainText('Rares')

  // It captures cleanly next press, with the fresh token.
  await page.keyboard.press('c')
  await expect(page.locator('.capture-undo-row').first()).toHaveAttribute(
    'aria-label',
    /Box 5, Section 2, Card 11$/,
  )
})

test('a re-space under the pick with "Use the last section" falls back, and the halt names no fate for the card', async ({
  page,
}) => {
  const wire = await open(page)
  await sectionRow(page).click()
  await page.locator('.capture-opt').filter({ hasText: /Section 2 of 3/ }).click()

  wire.bumpToken()
  await page.keyboard.press('c')
  await expect(page.locator('.capture-halt')).toContainText('section 2 (Rares) changed after a re-space')

  await page.getByRole('button', { name: 'Use the last section' }).click()
  await expect(page.locator('.capture-halt')).toHaveCount(0)
  await expect(sectionRow(page)).toContainText('Section 3 of 3')
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
  await expect(page.locator('.capture-refused, .capture-note-ok').first()).toContainText('Section')
  await expect(page.locator('.capture-quiet').filter({ hasText: 'Section 3 is now 4' })).toBeVisible()
  // The screen picks the new section.
  await expect(sectionRow(page)).toContainText('Section 3 of 4')
})

test('S at the back is the ordinary S, and sends no `after`', async ({ page }) => {
  const wire = await open(page)
  await page.keyboard.press('s')
  expect(wire.opens).toEqual([{ box: '5', after: undefined }])
  // The ordinary case renumbers nothing.
  await expect(page.locator('.capture-refused, .capture-note-ok').first()).toContainText('Section')
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
  // label on the row above it (a section's name, or "before section N") can shift Chromium's
  // own sub-pixel text rounding by a hair without moving anything at all.
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
  await setViewport(page, { width: 390, height: 844 })
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

/* THE ONE REAL CLIENT THAT CAN STILL HIT A DIV-LESS RESPONSE: an older capture server —
 * `sections_detail[].div` is a field this feature's server-side patch added, so a browser
 * tab whose bundle is current while the Python process behind it has not yet restarted onto
 * that patch (a deploy in flight, `capture_server.py` not yet reloaded) reads exactly this
 * shape. `GET /status`'s `boot_id`/`started_at` fields exist for the same class of skew. This
 * is the fallback's own case — `doSection`'s `record.sections` read — and every other test in
 * this file and in capture-undo.spec.ts now carries `div`, so this is the ONLY one exercising
 * it. */
test('an older server with no sections_detail[].div still lets U reach the divider', async ({
  page,
}) => {
  const wire = { closes: [] as { div: string | null }[] }
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
      body: JSON.stringify({ cards: 0, next_index: { '9': 4 } }),
    }),
  )
  // An undeclared box, on an older server: `sections` (the raw list) is the ONLY thing that
  // has ever been on this wire — `sections_detail` itself, and its own `div`, are both this
  // feature's additions. `sections: []` is deliberate: it is what an undeclared box always
  // sent, on every server this repo has shipped.
  let sections: number[] = []
  const boxRow = () => ({
    box: 9,
    bid: 19,
    name: 'Legacy box',
    sections,
    fill: 3,
    next_index: 4,
    cards: 3,
    sold: 0,
    retired: 0,
    listed: 0,
    on_hand: 3,
    sections_detail: [{ section: 1, start: 1, end: null, count: 3, name: null }],
  })
  await page.route(/\/boxes$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ boxes: [boxRow()] }),
    }),
  )
  await page.route(/\/boxes\/9\/sections/, (route) => {
    const method = route.request().method()
    if (method === 'DELETE') {
      const div = new URL(route.request().url()).searchParams.get('div')
      wire.closes.push({ div })
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(boxRow()) })
    }
    if (method !== 'POST') return route.fallback()
    sections = [4]
    // THE OLDER SERVER'S OWN SHAPE: `sections_detail` still answers (it existed for D264's
    // box map before this feature), but neither of its two entries carries `div`.
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ...boxRow(),
        sections_detail: [
          { section: 1, start: 1, end: 3, count: 3, name: null },
          { section: 2, start: 4, end: null, count: 0, name: null },
        ],
      }),
    })
  })
  await page.route(/\/photo\/\d+\/\d+/, (route) =>
    route.fulfill({ status: 200, contentType: 'image/gif', body: Buffer.from('R0lGODlhAQABAAAAACw=', 'base64') }),
  )

  await page.goto('/#/capture')
  await expect(page.locator('.capture-row').filter({ hasText: /Finish/ })).toBeVisible()
  await expect(async () => {
    await page.keyboard.press('b')
    await expect(page.locator('.capture-opt').filter({ hasText: /Legacy box/ })).toBeVisible({ timeout: 1_000 })
  }).toPass({ timeout: 15_000 })
  await page.keyboard.type('9')
  await page.keyboard.press('Enter')

  await page.keyboard.press('s')
  await expect(page.locator('.capture-refused, .capture-note-ok').first()).toContainText('Section')
  // THE SECTION ROW'S OWN RE-RENDER, waited on before `U` — `pendingDivider` and the trigger
  // seam's own ref both move in the same commit as this text, so this is what makes the
  // press land on the ref the S just re-armed rather than a passive effect still in flight
  // (the same category of gap D128 names for the field-key listener elsewhere in this file).
  await expect(sectionRow(page)).toContainText('Section 2 of 2')

  await page.keyboard.press('u')

  // The fallback read `record.sections`' own last entry — "4" — and named it, exactly as a
  // current server's own `div` would have.
  await expect.poll(() => wire.closes).toEqual([{ div: '4' }])
})

/* THE SIX SPECS THE OPUS REVIEW ASKED FOR, 2026-09-26 (findings 1, 2, 3, 4, 5). */

test('S then U then capture: the prior pick is restored, not the removed divider (finding 3)', async ({
  page,
}) => {
  const wire = await open(page)
  await sectionRow(page).click()
  await page.locator('.capture-opt').filter({ hasText: /Section 2 of 3/ }).click()
  await expect(sectionRow(page)).toContainText('Rares')

  await page.keyboard.press('s')
  expect(wire.opens).toEqual([{ box: '5', after: '6' }])
  await expect(sectionRow(page)).toContainText('Section 3 of 4')

  await page.keyboard.press('u')
  await expect.poll(() => wire.closes).toHaveLength(1)

  // NOT THE STALE KEY U JUST REMOVED, AND NOT THE LAST SECTION — the pick the operator had
  // BEFORE the S, restored exactly.
  await expect(sectionRow(page)).toContainText('Section 2 of 3')
  await expect(sectionRow(page)).toContainText('Rares')

  // The very next capture lands cleanly — a stale key here would halt it on `section_gone`.
  await page.keyboard.press('c')
  await expect(page.locator('.capture-halt')).toHaveCount(0)
  await expect(page.locator('.capture-undo-row').first()).toHaveAttribute(
    'aria-label',
    /Box 5, Section 2, Card 11$/,
  )
})

test('a capture that changes the token and section_div takes the response as the new pick (finding 1)', async ({
  page,
}) => {
  await open(page)
  await sectionRow(page).click()
  await page.locator('.capture-opt').filter({ hasText: /Section 2 of 3/ }).click()
  await expect(sectionRow(page)).toContainText('Rares')

  // THE CAPTURE ITSELF RE-SPACED THE BOX (another writer landed between the pick and this
  // press) — the response's own `layout_token`/`section_div` say so, and neither matches
  // what the screen sent. An incremental patch of `layout_token` alone would leave
  // `selectedDiv` naming "6", a key `sectionsDetail` may now resolve to a DIFFERENT section.
  let sawSecondCapture: { section?: string; layout_token?: string } | null = null
  await page.route(/\/capture$/, async (route, request) => {
    const asked = request.postDataJSON() as { section?: string; layout_token?: string }
    if (sawSecondCapture === null && asked.section === '6') {
      sawSecondCapture = asked
      return route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          box: 5,
          index: 11,
          key: '5/11',
          label: 'Box 5, Section 2, Card 6',
          section: 2,
          card: 6,
          // THE RE-SPACED KEY AND TOKEN — not "6" and not "tok1".
          section_div: '7',
          layout_token: 'tok-respaced',
          new_box: false,
          created: true,
          photo: '/tmp/5-11.jpg',
          capture_id: null,
          place: { box_total: 11, located: true, label: 'Box 5, Section 2, Card 6' },
        }),
      })
    }
    return route.fallback()
  })
  await page.route(/\/boxes$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        boxes: [{ ...BOX, sections_detail: threeSections().map((s) => (s.div === '6' ? { ...s, div: '7' } : s)), layout_token: 'tok-respaced' }],
      }),
    }),
  )

  await page.keyboard.press('c')
  await expect.poll(() => sawSecondCapture).not.toBeNull()

  // THE PICK MOVED TO THE RESPONSE'S OWN `section_div` — "7", never the stale "6" the
  // request went out with — and the STORED pick carries the fresh token beside it, so a
  // restore later requires THAT token, not the one the pick was originally made against
  // (finding 1's own restore half, proved separately below).
  await expect.poll(() =>
    page.evaluate(() => {
      // eslint-disable-next-line no-restricted-syntax -- READING THE KEY UNDER TEST (finding 1's own token field).
      return JSON.parse(localStorage.getItem('banchi.capture.sections') ?? '{}') as Record<string, unknown>
    }),
  ).toMatchObject({ 'bid:15': { div: '7', token: 'tok-respaced' } })
})

test('S then a capture sends the new section and the new token, and never says the section is gone', async ({ page }) => {
  const wire = await open(page, { sectionBumpsToken: true })
  const posts: { section?: string; layout_token?: string }[] = []
  page.on('request', (r) => {
    if (r.method() === 'POST' && /\/capture$/.test(r.url())) posts.push(r.postDataJSON() as { section?: string; layout_token?: string })
  })
  await page.keyboard.press('s')
  await expect.poll(() => wire.opens.length).toBe(1)
  await expect(sectionRow(page)).toContainText('Section 4 of 4')
  await page.getByRole('button', { name: 'Capture', exact: true }).click()
  await expect.poll(() => posts.length).toBe(1)
  expect(posts[0]).toMatchObject({ section: '11-3', layout_token: 'tok2' })
  await expect(page.locator('.capture-refused').filter({ hasText: 'That section is gone' })).toHaveCount(0)
  await expect(sectionRow(page)).toContainText('Section 4 of 4')
})

test('S twice in a row while the new section is empty stays quiet', async ({ page }) => {
  const wire = await open(page, { sectionBumpsToken: true })
  await page.keyboard.press('s')
  await expect.poll(() => wire.opens.length).toBe(1)
  await expect(sectionRow(page)).toContainText('Section 4 of 4')
  await page.keyboard.press('s')
  await expect.poll(() => wire.opens.length).toBe(2)
  await expect(sectionRow(page)).toContainText('Section 5 of 5')
  await expect(page.locator('.capture-refused').filter({ hasText: 'That section is gone' })).toHaveCount(0)
  await expect(page.getByText('That section is gone')).toHaveCount(0)
})

test('a restore after a re-space requires the stored token to still match (finding 1)', async ({ page }) => {
  await open(page)
  // A PICK STORED BEFORE THE BOX WAS RE-SPACED: the key "6" is still a real
  // `sections_detail[].div` on THIS box (membership alone would pass), but the token it was
  // made against is not the box's current one — a re-space can leave a key resolving to a
  // DIFFERENT section, which membership can never see.
  await page.evaluate(() => {
    // eslint-disable-next-line no-restricted-syntax -- SEEDING THE KEY UNDER TEST (finding 1's own token field).
    localStorage.setItem(
      'banchi.capture.sections',
      JSON.stringify({ 'bid:15': { div: '6', at: Date.now(), token: 'tok-old' } }),
    )
  })
  await page.reload()
  await expect(page.locator('.capture-row').filter({ hasText: /Finish/ })).toBeVisible()
  await expect(async () => {
    await page.keyboard.press('b')
    await expect(page.locator('.capture-opt').filter({ hasText: /Sub-box test/ })).toBeVisible({ timeout: 1_000 })
  }).toPass({ timeout: 15_000 })
  await page.keyboard.type('5')
  await page.keyboard.press('Enter')

  // THE TOKEN MISMATCH IS TREATED LIKE A GONE KEY, never silently adopted — the box's own
  // token is "tok1" (the fixture's default), not "tok-old".
  await expect(sectionRow(page)).toContainText('Section 3 of 3')
  await expect(page.locator('.capture-section-slot .capture-refused')).toContainText('That section is gone')
})

test('a capture refreshes the pick\'s clock, so 30+ minutes since the PICK does not expire it (finding 5)', async ({
  page,
}) => {
  await page.clock.install()
  await open(page)
  await sectionRow(page).click()
  await page.locator('.capture-opt').filter({ hasText: /Section 2 of 3/ }).click()
  await expect(sectionRow(page)).toContainText('Rares')

  // 25 minutes in — still fresh — a capture lands and touches the pick's own clock.
  await page.clock.runFor(25 * 60_000)
  await page.keyboard.press('c')
  await expect(page.locator('.capture-halt')).toHaveCount(0)
  await expect(page.locator('.capture-undo-row').first()).toHaveAttribute(
    'aria-label',
    /Box 5, Section 2, Card 11$/,
  )

  // 25 MORE MINUTES (50 since the pick, but 25 since the capture that touched it) — a
  // reload restores the SAME pick, because the capture reset its clock. Without finding 5's
  // fix this would have expired at the 30-minute mark from the ORIGINAL pick.
  await page.clock.runFor(25 * 60_000)
  await page.reload()
  await expect(page.locator('.capture-row').filter({ hasText: /Finish/ })).toBeVisible()
  await expect(async () => {
    await page.keyboard.press('b')
    await expect(page.locator('.capture-opt').filter({ hasText: /Sub-box test/ })).toBeVisible({ timeout: 1_000 })
  }).toPass({ timeout: 15_000 })
  await page.keyboard.type('5')
  await page.keyboard.press('Enter')
  await expect(sectionRow(page)).toContainText('Section 2 of 3')
  await expect(sectionRow(page)).toContainText('Rares')
})

test('U right after S, with no settle time beyond the S round trip, undoes the divider it just made (finding 4, D128)', async ({
  page,
}) => {
  const wire = await open(page)
  await sectionRow(page).click()
  await page.locator('.capture-opt').filter({ hasText: /Section 2 of 3/ }).click()

  // WAIT ONLY FOR S'S OWN ROUND TRIP TO LAND (the request the mock answers), NEVER FOR A
  // SETTLED DOM TEXT OR AN ARBITRARY PAUSE — `expect.poll` on `wire.opens` resolves the
  // moment the response is back and `doSection`'s state updates are queued, which is the
  // EARLIEST point 'u' can mean anything. From there to `pendingDivider` actually being set
  // and `fireUndoRef` actually being re-armed is exactly the gap a passive `useEffect` leaves
  // open — the same gap this file's "older server" test names as "about one run in five"
  // without it. A layout effect closes that gap; a passive one does not.
  await page.keyboard.press('s')
  await expect.poll(() => wire.opens).toHaveLength(1)
  await page.keyboard.press('u')

  // THE DIVIDER S JUST OPENED IS THE ONE U JUST CLOSED — not a plain capture-undo (there is
  // no capture yet to undo), and not a no-op.
  // THE NEW DIVIDER'S OWN KEY, not the picked div "6" that named where it went — the fixture's
  // own S handler suffixes it ("11-2") only because it would otherwise collide with the
  // already-empty section 3's div in this exact fixture; a real server's opaque key would
  // simply differ (subbox-capture.md 1).
  await expect.poll(() => wire.closes).toEqual([{ box: '5', div: '11-2' }])
  await expect.poll(() => wire.opens).toEqual([{ box: '5', after: '6' }])
  await expect(sectionRow(page)).toContainText('Section 2 of 3')
  await expect(sectionRow(page)).toContainText('Rares')
})

test('a capture after a 409 with Keep unanswered does not fire — nothing was written stays true (finding 2)', async ({
  page,
}) => {
  const wire = await open(page)
  await sectionRow(page).click()
  await page.locator('.capture-opt').filter({ hasText: /Section 2 of 3/ }).click()
  wire.bumpToken()

  await page.keyboard.press('c')
  await expect(page.locator('.capture-halt')).toContainText('Nothing was written')

  // THE HALT SITS UNANSWERED — no Keep, no "Use the last section", no Resume (there is
  // none for this halt). A second press must not reach the server at all.
  let capturesSinceHalt = 0
  await page.route(/\/capture$/, (route) => {
    capturesSinceHalt += 1
    return route.fallback()
  })
  await page.keyboard.press('c')
  await page.keyboard.press('c')
  await expect(page.locator('.capture-halt')).toBeVisible()
  // THE DEFINITIVE PROOF: no request reached the server for either press — not merely that
  // the undo strip looks unchanged, which it would anyway (it falls back to the box's own
  // pre-existing newest card whenever this sitting has captured nothing, with or without a
  // halt in the way).
  expect(capturesSinceHalt).toBe(0)

  // Answering it is still the only way through, and it works.
  await page.getByRole('button', { name: 'Use the last section' }).click()
  await expect(page.locator('.capture-halt')).toHaveCount(0)
  await page.keyboard.press('c')
  await expect(page.locator('.capture-undo-row').first()).toBeVisible()
})

/* OWNER'S RULING, 2026-09-28: the open Section list goes in FRONT of the RECENT footer and
 * scrolls. `.capture-open-pinned` is z-indexed inside `.capture-card`'s own stacking context,
 * so the later footer painted over rows 8-11 of an 11-section box and they could not be
 * reached. The last option must take a real (never forced) click, at every width. */
function manySections(n: number): Span[] {
  return Array.from({ length: n }, (_, at) => ({
    section: at + 1,
    start: at * 5 + 1,
    end: at === n - 1 ? null : at * 5 + 5,
    count: at === n - 1 ? 0 : 5,
    name: null,
    div: String(at * 5 + 1),
  }))
}

for (const [width, height] of [
  [1440, 900],
  [550, 800],
  [390, 844],
] as const) {
  test(`the last of 12 sections scrolls into view and takes a real click at ${width}`, async ({ page }) => {
    await setViewport(page, { width, height })
    await open(page, {
      spans: manySections(12),
      boxes: [
        {
          ...BOX,
          sections: manySections(12).map((s) => s.start),
          sections_detail: manySections(12),
        },
      ],
    })
    await sectionRow(page).click()
    await expect(page.locator('.capture-open-pinned')).toBeVisible()
    const last = page.locator('.capture-opt').filter({ hasText: /Section 12 of 12/ })
    // A real click: Playwright scrolls the list, then refuses if anything else covers the row.
    await last.click({ timeout: 5_000 })
    await expect(sectionRow(page)).toContainText('Section 12 of 12')
  })
}

/* KEYBOARD AT 390. Capture's open list has no arrow-key handler (`[` and `]` step the pick and
 * never open the list), so the keyboard path is the native one: focus starts on the first
 * option and Tab walks the rest. Each focused option must stay inside the list and above the
 * tab bar, down to the last row. */
test('walking the open list by keyboard keeps the focused option in view to the last row at 390', async ({
  page,
}) => {
  await setViewport(page, { width: 390, height: 844 })
  await open(page, {
    spans: manySections(12),
    boxes: [
      { ...BOX, sections: manySections(12).map((s) => s.start), sections_detail: manySections(12) },
    ],
  })
  await sectionRow(page).click()
  await expect(page.locator('.capture-open-pinned')).toBeVisible()
  const tabTop = (await page.locator('.bn-tabbar').boundingBox())!.y
  for (let at = 0; at < 12; at += 1) {
    if (at > 0) await page.keyboard.press('Tab')
    const focused = page.locator('.capture-open-pinned .capture-opt:focus')
    await expect(focused).toContainText(`Section ${at + 1} of 12`)
    await afterPaint(page)
    const list = (await page.locator('.capture-open-pinned').boundingBox())!
    const opt = (await focused.boundingBox())!
    expect(opt.y).toBeGreaterThanOrEqual(list.y)
    expect(opt.y + opt.height).toBeLessThanOrEqual(list.y + list.height + 1)
    expect(opt.y + opt.height).toBeLessThanOrEqual(tabTop)
  }
})

/* PHONE CASE (coordinator, 2026-09-28): on opening, the whole list, its own header row
 * included, sits between the top bar and the tab bar. Measured right after the open, before
 * any scroll of the list. */
for (const [width, height] of [
  [550, 800],
  [390, 844],
] as const) {
  test(`the open list fits between the top bar and the tab bar at ${width}`, async ({ page }) => {
    await setViewport(page, { width, height })
    await open(page, {
      spans: manySections(12),
      boxes: [
        {
          ...BOX,
          sections: manySections(12).map((s) => s.start),
          sections_detail: manySections(12),
        },
      ],
    })
    await sectionRow(page).click()
    const pinned = page.locator('.capture-open-pinned')
    await expect(pinned).toBeVisible()
    await page.evaluate(() => new Promise<void>((done) => {
  const top = () => document.querySelector('.capture-open-pinned')!.getBoundingClientRect().top
  let last = top()
  let still = 0
  const tick = () => {
    const now = top()
    still = now === last ? still + 1 : 0
    last = now
    if (still >= 5) done()
    else requestAnimationFrame(tick)
  }
  requestAnimationFrame(tick)
}))
    const tabTop = (await page.locator('.bn-tabbar').boundingBox())!.y
    const topBarBottom = (await page.locator('.bn-topbar').boundingBox())!.y +
      (await page.locator('.bn-topbar').boundingBox())!.height
    const list = (await pinned.boundingBox())!
    expect(list.y + list.height).toBeLessThanOrEqual(tabTop)
    expect(list.y).toBeGreaterThanOrEqual(topBarBottom)
    const header = (await pinned.locator('> .capture-row').boundingBox())!
    expect(header.y).toBeGreaterThanOrEqual(list.y)
    expect(header.y + header.height).toBeLessThanOrEqual(list.y + list.height)
  })
}

/* THE BACKGROUND READER'S SWITCH (docs/specs/identify-engine-pick.md, section 8), a row on the Rig
 * panel. No box is open, so the panel is shown on arrival. */
test.describe('Background Match', () => {
  const row = (page: Page) => page.getByRole('switch', { name: /Background Match/ })

  test('holds its height while the switch state loads, and reads Off by default', async ({ page }) => {
    const wire = await open(page, { boxes: [], holdSweep: true, bare: true })
    await expect(row(page)).toBeVisible()
    await expect(row(page)).toBeDisabled()
    const before = (await row(page).boundingBox())!
    wire.releaseSweep()
    await expect(row(page)).toBeEnabled()
    await expect(row(page)).toContainText('Off')
    await expect(row(page)).toHaveAttribute('aria-checked', 'false')
    expect((await row(page).boundingBox())!.height, 'the row changed height when the state arrived').toBe(before.height)
  })

  test('a press calls PUT with the flipped state and shows it', async ({ page }) => {
    const wire = await open(page, { boxes: [], bare: true })
    await expect(row(page)).toBeEnabled()
    expect(wire.sweepPuts, 'nothing is written before a press').toEqual([])
    await row(page).click()
    await expect(row(page)).toContainText('On')
    await expect(row(page)).toHaveAttribute('aria-checked', 'true')
    await row(page).click()
    await expect(row(page)).toContainText('Off')
    expect(wire.sweepPuts).toEqual([{ on: true }, { on: false }])
  })
})

/* THE CAPTURE HEAD'S THIRD COUNTER, "matched" (owner ruling: fixed width, one word, no mechanism noun). */
const matchedStat = (page: Page, label: string): Locator => page.locator('.capture-odo .bn-stat').filter({ hasText: label })
const bgSwitch = (page: Page) => page.getByRole('switch', { name: /Background Match/ })
/** Document-relative: a real click scrolls the window, and a viewport box would read that as a move. */
const boxOf = async (l: Locator) =>
  l.evaluate((el) => {
    const r = el.getBoundingClientRect()
    return { x: r.x + window.scrollX, y: r.y + window.scrollY, width: r.width, height: r.height }
  })

/* 1. WITH THE SWITCH ON: the number is the route's `matched_here`, it follows the route without a reload,
   the read names this sitting's keys, and 9 -> 10 does not change the box. */
test('matched: the head shows the sitting\'s matched count live, in a box of fixed width', async ({ page }) => {
  const sweep = await stubMatched(page, 12, { matchedHere: 9 })
  await page.goto('/#/capture')
  await settleFonts(page)
  const matched = matchedStat(page, 'matched')
  await expect(matched).toHaveCount(1)
  await expect(matched.locator('.bn-stat-value')).toHaveText('9')
  expect(sweep.asked.at(-1), 'the read is scoped to this sitting\'s keys').toBe(Array.from({ length: 12 }, (_, i) => `3/${i + 1}`).join(','))
  const before = await boxOf(matched)
  sweep.matchedHere = 10
  await expect(matched.locator('.bn-stat-value')).toHaveText('10', { timeout: 8_000 }) // keep: waits one 3s poll tick, no reload
  const after = await boxOf(matched)
  expect(after.width, 'the counter grew a digit and its box changed width').toBe(before.width)
  expect(after.x).toBe(before.x)
  expect(await matched.locator('.bn-stat-value').evaluate((el) => getComputedStyle(el).fontVariantNumeric)).toContain('tabular-nums')
})

/* 2. WITH THE SWITCH OFF: no counter, and flipping the switch moves neither of the other two. */
test('matched: absent while the switch is off, and the flip moves neither other counter', async ({ page }) => {
  await stubMatched(page, 12, { on: false, matchedHere: 4 })
  await page.goto('/#/capture')
  await settleFonts(page)
  await expect(bgSwitch(page)).toHaveAttribute('aria-checked', 'false')
  await expect(page.locator('.capture-odo .bn-stat')).toHaveCount(2)
  await expect(page.locator('.capture-odo')).not.toContainText('matched')
  await settleMotion(page)
  const [cap0, next0] = [await boxOf(matchedStat(page, 'captured')), await boxOf(matchedStat(page, 'next card'))]
  await bgSwitch(page).click()
  await expect(matchedStat(page, 'matched')).toHaveCount(1)
  await settleMotion(page)
  const [cap1, next1] = [await boxOf(matchedStat(page, 'captured')), await boxOf(matchedStat(page, 'next card'))]
  expect(cap1, 'captured moved when the matched counter appeared').toEqual(cap0)
  expect(next1, 'next card moved when the matched counter appeared').toEqual(next0)
  await bgSwitch(page).click()
  await expect(page.locator('.capture-odo .bn-stat')).toHaveCount(2)
})

/* No mechanism words: the label is the one word, a number over it, no mechanism noun beside it. */
test('matched: the counter reads a number over "matched" and nothing else', async ({ page }) => {
  await stubMatched(page, 3, { matchedHere: 2 })
  await page.goto('/#/capture')
  await expect(matchedStat(page, 'matched')).toHaveCount(1)
  await expect(matchedStat(page, 'matched')).toHaveText(/^\s*2\s*matched\s*$/)
})

/* A FAILED FIRST READ OF THE SWITCH RECOVERS. The row says "Unavailable" and is pressable; the press reads
   again at once, and once a read lands the switch works and the matched counter appears. */
test('Background Match: a failed first read shows Unavailable, a press re-reads, then the switch works', async ({ page }) => {
  const sweep = await stubMatched(page, 5, { on: false, matchedHere: 3 })
  let reads = 0
  let failing = true // every read of the switch fails until the test lets one through
  await page.route(/\/pipeline\/match\/sweep(\?.*)?$/, (route) => {
    /* the switch's own read carries no `keys`; the counter's poll does, and is not the read under test */
    if (route.request().method() !== 'GET' || new URL(route.request().url()).searchParams.has('keys')) return route.fallback()
    reads += 1
    if (failing) return route.fulfill({ status: 500, contentType: 'application/json', body: '{"error":{"code":"boom","message":"no"}}' })
    return route.fallback()
  })
  await page.goto('/#/capture')
  const row = page.getByRole('switch', { name: /Background Match/ })
  await expect(row).toContainText('Unavailable')
  await expect(row).toBeEnabled()
  failing = false
  const before = reads
  await row.click()
  await expect(row).toContainText('Off')
  expect(reads, 'the press read again').toBeGreaterThan(before)
  await row.click()
  await expect(row).toContainText('On')
  expect(sweep.on).toBe(true)
  await expect(page.locator('.capture-odo .bn-stat').filter({ hasText: 'matched' }).locator('.bn-stat-value')).toHaveText('3')
})
