// Protects: The box map edit mode queues every drag as a draft, writes nothing until Confirm, and then sends the whole draft as one request with fresh digests.
// Governs: D264
import { test, expect, type Page } from '@playwright/test'
import type { BoxRecord, SectionDetail, SectionMoveBatchResult } from '../src/types'
import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'

/* THE SHELF (D264), horizontal, edit-mode ruling (owner, 2026-09-26): read-only until "Edit
 * layout", every drag queues a draft move with no write, and Confirm sends the whole draft as
 * ONE request to `/boxes/sections/move-batch`, with `digests` — `content_digest`, card-aware,
 * not `layout_token` alone (the strict review's finding, 2026-09-27) — read fresh the moment
 * Edit layout is pressed. Card ranges rejoin edit mode the same way (owner's ruling,
 * 2026-09-27): a range drafts like a section, in the same draft, the same Confirm, the same
 * undo. EVERYTHING IS STUBBED: the routes the view writes through are answered here, and what
 * the screen SENT is what each case asserts. The store is never touched.
 *
 * STALE AGAINST THIS SPEC'S OWN PRIOR VERSION, flagged in the lane's report rather than
 * silently carried over: the old file pinned an immediate per-drag save through
 * `/boxes/<box>/sections/move` and `/boxes/<box>/cards/move`, and a vertical layout. Both
 * single-write routes and their own harness coverage are untouched; only this file changed. */

sealEveryTest()

const ROUTE = '/#/inventory?view=shelf'

function section(n: number, name: string | null, count: number): SectionDetail {
  return { section: n, start: 1, end: count, count, name }
}

function box(n: number, name: string, sections: SectionDetail[]): BoxRecord {
  return {
    box: n,
    bid: n,
    name,
    sections: sections.map((s) => s.section),
    fill: 0,
    next_index: 1,
    cards: 0,
    on_hand: sections.reduce((sum, s) => sum + s.count, 0),
    sold: 0,
    retired: 0,
    moved: 0,
    listed: 0,
    sections_detail: sections,
    layout_token: `tok-${n}`,
    content_digest: `dig-${n}`,
  } as BoxRecord
}

const BOXES: BoxRecord[] = [
  box(1, 'RB Origins', [section(1, 'Commons', 11), section(2, 'Uncommons', 10), section(3, 'Signatures', 13)]),
  box(2, 'Mixed Singles', [section(1, null, 15), section(2, 'Promos', 4)]),
  box(3, 'Old Box', [section(1, 'Old', 5)]),
]

const RESULT: SectionMoveBatchResult = {
  move: 'm1',
  created: null,
  moved: 10,
  receipt: {
    heading: '1 change to make.',
    steps: [
      'In RB Origins, find the divider Uncommons.',
      'Take out that divider and the 10 cards on your side of it, up to the next divider.',
      'In Mixed Singles, find the divider Promos. Put them just on the far side of it, in the same order.',
    ],
    renumbered: ['In Mixed Singles, Promos moves from Section 2 to Section 3.'],
    owed: '3 of these cards are owed to open orders. The orders stay as they are.',
    next_capture: [
      'The next card you capture in RB Origins joins Uncommons, Section 2. Press S first to start a new section.',
    ],
  },
  boxes: [],
}

type Sent = { path: string; body: unknown }

async function openShelf(page: Page, result: SectionMoveBatchResult = RESULT, boxes: BoxRecord[] = BOXES): Promise<Sent[]> {
  const sent: Sent[] = []
  await page.route(/\/boxes(\?.*)?$/, (route) =>
    route.fulfill({ json: { boxes, facets: { games: [], sets: {}, rarities: {} } } }),
  )
  await page.route(/\/boxes\/sections\/move-batch$/, async (route) => {
    sent.push({ path: new URL(route.request().url()).pathname, body: route.request().postDataJSON() })
    await route.fulfill({ json: result })
  })
  await page.route(/\/boxes\/sections\/undo$/, async (route) => {
    sent.push({ path: new URL(route.request().url()).pathname, body: route.request().postDataJSON() })
    await route.fulfill({ json: { move: 'm1', undone: true, boxes: [] } })
  })
  await page.goto(ROUTE)
  await settleFonts(page)
  await expect(page.locator('.shelf-box')).toHaveCount(boxes.length)
  return sent
}

test('read-only: every box is drawn horizontally, Back/Front replaces the sentence, no money, no grip', async ({ page }) => {
  await openShelf(page)
  const first = page.locator('.shelf-box').first()
  await expect(first.locator('.shelf-block-name')).toHaveText(['Commons', 'Uncommons', 'Signatures'])
  await expect(page.locator('.shelf')).not.toContainText('$')
  await expect(page.locator('.shelf')).not.toContainText('drawn from above')
  await expect(page.locator('.shelf-edges')).toContainText('Back')
  await expect(page.locator('.shelf-edges')).toContainText('Front')
  await expect(page.getByRole('button', { name: /Move section/ })).toHaveCount(0)
  /* Sections run in one row, left to right: a block's WIDTH follows its count now, not height. */
  const widths = await first.locator('.shelf-block').evaluateAll((els) => els.map((el) => el.getBoundingClientRect().width))
  expect(widths[2]).toBeGreaterThan(widths[1] ?? 0)
})

test('Layout enters edit mode; a queued drop writes nothing until Confirm, which sends the whole draft once', async ({ page }) => {
  const sent = await openShelf(page)
  await page.getByRole('button', { name: 'Layout' }).click()
  await page.getByRole('button', { name: 'Move section Uncommons of RB Origins' }).click()
  await expect(page.getByRole('button', { name: 'Old Box', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Mixed Singles', exact: true }).click()
  await expect(page.locator('.shelf-pair .shelf-box')).toHaveCount(2)
  await page.getByRole('button', { name: /Put Uncommons just on the far side of Promos/ }).click()
  expect(sent).toHaveLength(0)
  await expect(page.getByText('1 change queued.', { exact: false })).toBeVisible()

  await page.getByRole('button', { name: 'Confirm' }).click()
  expect(sent).toHaveLength(1)
  expect(sent[0]).toEqual({
    path: '/boxes/sections/move-batch',
    body: {
      digests: { '1': 'dig-1', '2': 'dig-2', '3': 'dig-3' },
      moves: [{ kind: 'section', box: 1, first: 2, last: 2, to_box: 2, before: 2 }],
    },
  })
  await expect(page.locator('.shelf-receipt')).toContainText('1 change to make.')
  await page.keyboard.press('u')
  await expect(page.locator('.shelf-receipt')).toContainText('Put back.')
  expect(sent[1]).toEqual({ path: '/boxes/sections/undo', body: { move: 'm1' } })
})

/* THE GRIP IS A DRAG HANDLE: a real pointer drag from "Drag section <name> of <box>" onto a slot
 * of a box. The left half of a slot drops in front of it, the right half after it. */
async function dragGrip(page: Page, grip: string, boxName: string, slot: number, half: 'left' | 'right') {
  const handle = page.getByRole('button', { name: grip })
  await handle.scrollIntoViewIfNeeded()
  const from = (await handle.boundingBox())!
  const target = page.locator(`section[aria-label="${boxName}"] [data-shelf-slot="${slot}"]`)
  await target.scrollIntoViewIfNeeded()
  const to = (await target.boundingBox())!
  const sx = from.x + from.width / 2
  const sy = from.y + from.height / 2
  const tx = to.x + to.width * (half === 'left' ? 0.25 : 0.75)
  const ty = to.y + to.height / 2
  await page.mouse.move(sx, sy)
  await page.mouse.down()
  for (let i = 1; i <= 8; i++) await page.mouse.move(sx + ((tx - sx) * i) / 8, sy + ((ty - sy) * i) / 8)
  await page.mouse.up()
}

test('grip drag: a section dropped on the left half of Commons reorders within its box', async ({ page }) => {
  const sent = await openShelf(page)
  await page.getByRole('button', { name: 'Layout' }).click()
  await dragGrip(page, 'Drag section Signatures of RB Origins', 'RB Origins', 1, 'left')
  await expect(page.getByText('1 change queued.', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Confirm' }).click()
  expect(sent).toHaveLength(1)
  expect((sent[0]!.body as { moves: unknown[] }).moves).toEqual([
    { kind: 'section', box: 1, first: 3, last: 3, to_box: 1, before: 1 },
  ])
})

test('grip drag: a section dropped on the right half of Promos moves to the far end of another box', async ({ page }) => {
  const sent = await openShelf(page)
  await page.getByRole('button', { name: 'Layout' }).click()
  await dragGrip(page, 'Drag section Uncommons of RB Origins', 'Mixed Singles', 2, 'right')
  await expect(page.getByText('1 change queued.', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Confirm' }).click()
  expect(sent).toHaveLength(1)
  expect((sent[0]!.body as { moves: unknown[] }).moves).toEqual([
    { kind: 'section', box: 1, first: 2, last: 2, to_box: 2, before: null },
  ])
})

test('grip drag: a drop queues and writes nothing; Confirm sends once; u sends the undo', async ({ page }) => {
  const sent = await openShelf(page)
  await page.getByRole('button', { name: 'Layout' }).click()
  await dragGrip(page, 'Drag section Uncommons of RB Origins', 'Mixed Singles', 2, 'right')
  await expect(page.getByText('1 change queued.', { exact: false })).toBeVisible()
  expect(sent).toHaveLength(0)
  await page.getByRole('button', { name: 'Confirm' }).click()
  await expect(page.locator('.shelf-receipt')).toContainText('1 change to make.')
  expect(sent.filter((s) => s.path === '/boxes/sections/move-batch')).toHaveLength(1)
  await page.keyboard.press('u')
  await expect(page.locator('.shelf-receipt')).toContainText('Put back.')
  expect(sent.at(-1)).toEqual({ path: '/boxes/sections/undo', body: { move: 'm1' } })
})

test('grip drag: a plain click on a grip shows the hint and opens no picker', async ({ page }) => {
  const sent = await openShelf(page)
  await page.getByRole('button', { name: 'Layout' }).click()
  await expect(page.getByText('Drag a section to move it.')).toBeVisible()
  await page.getByRole('button', { name: 'Drag section Uncommons of RB Origins' }).click()
  await expect(page.getByText('Drag to move it, or press the arrow.')).toBeVisible()
  await expect(page.locator('.shelf-lift')).toHaveCount(0)
  expect(sent).toHaveLength(0)
})

test('grip: Enter on a focused grip opens the destination picker, and the name says so', async ({ page }) => {
  await openShelf(page)
  await page.getByRole('button', { name: 'Layout' }).click()
  const grip = page.getByRole('button', { name: 'Drag section Uncommons of RB Origins' })
  await expect(grip).toHaveAccessibleName(/Press Enter to choose a box\.$/)
  await grip.focus()
  await page.keyboard.press('Enter')
  await expect(page.locator('.shelf-lift')).toBeVisible()
})

for (const [slot, half] of [[2, 'left'], [2, 'right'], [3, 'left']] as const) {
  test(`grip drag: a drop on its own place (slot ${slot}, ${half}) queues nothing`, async ({ page }) => {
    const sent = await openShelf(page)
    await page.getByRole('button', { name: 'Layout' }).click()
    await dragGrip(page, 'Drag section Uncommons of RB Origins', 'RB Origins', slot, half)
    await expect(page.getByText('Drag a section to move it.')).toBeVisible()
    await expect(page.getByText('change queued', { exact: false })).toHaveCount(0)
    await expect(page.locator('.shelf-drop-mark')).toHaveCount(0)
    expect(sent).toHaveLength(0)
  })
}

test('grip drag: a drop on an empty box queues a move to that box', async ({ page }) => {
  const empty = box(4, 'Empty Box', [])
  const sent = await openShelf(page, RESULT, [...BOXES, empty])
  await page.getByRole('button', { name: 'Layout' }).click()
  const handle = page.getByRole('button', { name: 'Drag section Uncommons of RB Origins' })
  const target = page.locator('section[aria-label="Empty Box"]')
  await target.scrollIntoViewIfNeeded()
  const from = (await handle.boundingBox())!
  const to = (await target.boundingBox())!
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2)
  await page.mouse.down()
  await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2, { steps: 8 })
  await page.mouse.up()
  await expect(page.getByText('1 change queued.', { exact: false })).toBeVisible()
  await page.getByRole('button', { name: 'Confirm' }).click()
  expect((sent[0]!.body as { moves: unknown[] }).moves).toEqual([
    { kind: 'section', box: 1, first: 2, last: 2, to_box: 4, before: null },
  ])
})

test('grip drag: nothing is sent while the pointer is still down', async ({ page }) => {
  const sent = await openShelf(page)
  await page.getByRole('button', { name: 'Layout' }).click()
  const handle = page.getByRole('button', { name: 'Drag section Uncommons of RB Origins' })
  const target = page.locator('section[aria-label="Mixed Singles"] [data-shelf-slot="2"]')
  await target.scrollIntoViewIfNeeded()
  const from = (await handle.boundingBox())!
  const to = (await target.boundingBox())!
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2)
  await page.mouse.down()
  await page.mouse.move(to.x + to.width * 0.75, to.y + to.height / 2, { steps: 8 })
  await expect(page.locator('.shelf-drop-mark')).toHaveCount(1)
  await page.waitForTimeout(300)
  expect(sent).toHaveLength(0)
  await page.mouse.up()
  await expect(page.getByText('1 change queued.', { exact: false })).toBeVisible()
  expect(sent).toHaveLength(0)
})

test('grip drag: a lost capture ends the drag, so a later release queues nothing', async ({ page }) => {
  const sent = await openShelf(page)
  await page.getByRole('button', { name: 'Layout' }).click()
  const handle = page.getByRole('button', { name: 'Drag section Uncommons of RB Origins' })
  const target = page.locator('section[aria-label="Mixed Singles"] [data-shelf-slot="2"]')
  await target.scrollIntoViewIfNeeded()
  const from = (await handle.boundingBox())!
  const to = (await target.boundingBox())!
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2)
  await page.mouse.down()
  await page.mouse.move(to.x + to.width * 0.75, to.y + to.height / 2, { steps: 8 })
  await expect(page.locator('.shelf-drop-mark')).toHaveCount(1)
  await handle.evaluate((el) => el.dispatchEvent(new PointerEvent('lostpointercapture', { pointerId: 1, bubbles: true })))
  await expect(page.locator('.shelf-drop-mark')).toHaveCount(0)
  await page.mouse.up()
  await page.mouse.click(to.x + to.width * 0.75, to.y + to.height / 2)
  await expect(page.getByText('change queued', { exact: false })).toHaveCount(0)
  await expect(page.locator('.shelf-drop-mark')).toHaveCount(0)
  expect(sent).toHaveLength(0)
})

test('grip drag: at 820 wide, a drag held at the bottom edge autoscrolls to a box below the fold', async ({ page }) => {
  await page.setViewportSize({ width: 820, height: 600 })
  const many = Array.from({ length: 8 }, (_, i) => box(i + 1, `Box ${i + 1}`, [section(1, `Sec ${i + 1}`, 6), section(2, `Part ${i + 1}`, 6)]))
  await openShelf(page, RESULT, many)
  await page.getByRole('button', { name: 'Layout' }).click()
  const handle = page.getByRole('button', { name: 'Drag section Sec 1 of Box 1' })
  const from = (await handle.boundingBox())!
  const last = page.locator('section[aria-label="Box 8"]')
  expect((await last.boundingBox())!.y).toBeGreaterThan(600)
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2)
  await page.mouse.down()
  await page.mouse.move(from.x + from.width / 2, 590, { steps: 8 })
  await expect.poll(async () => (await last.boundingBox())!.y, { timeout: 8000 }).toBeLessThan(560)
  const slot = last.locator('[data-shelf-slot="2"]')
  const to = (await slot.boundingBox())!
  await page.mouse.move(to.x + to.width * 0.75, to.y + to.height / 2, { steps: 8 })
  await page.mouse.up()
  await expect(page.getByText('1 change queued.', { exact: false })).toBeVisible()
})

test('the receipt names the cards owed to open orders and the section the next capture joins, and each line is absent at zero', async ({ page }) => {
  await openShelf(page)
  await page.getByRole('button', { name: 'Layout' }).click()
  await page.getByRole('button', { name: 'Move section Uncommons of RB Origins' }).click()
  await page.getByRole('button', { name: 'Mixed Singles', exact: true }).click()
  await page.getByRole('button', { name: /Put Uncommons just on the far side of Promos/ }).click()
  const firstBox = page.locator('.shelf-box').first()
  const top = async () => (await firstBox.boundingBox())?.y
  await page.getByRole('button', { name: 'Confirm' }).click()
  const receipt = page.locator('.shelf-receipt')
  await expect(receipt.locator('.shelf-receipt-note')).toHaveText([
    '3 of these cards are owed to open orders. The orders stay as they are.',
    'The next card you capture in RB Origins joins Uncommons, Section 2. Press S first to start a new section.',
  ])
  /* D313: the receipt sits below the map, so Undo drops the notes without moving the map. */
  const before = await top()
  await page.keyboard.press('u')
  await expect(receipt).toContainText('Put back.')
  await expect(receipt.locator('.shelf-receipt-note')).toHaveCount(0)
  expect(await top()).toBe(before)
})

test('a receipt with nothing owed and no last section moved draws neither line', async ({ page }) => {
  await openShelf(page, { ...RESULT, receipt: { ...RESULT.receipt, owed: null, next_capture: [] } })
  await page.getByRole('button', { name: 'Layout' }).click()
  await page.getByRole('button', { name: 'Move section Uncommons of RB Origins' }).click()
  await page.getByRole('button', { name: 'Mixed Singles', exact: true }).click()
  await page.getByRole('button', { name: /Put Uncommons just on the far side of Promos/ }).click()
  await page.getByRole('button', { name: 'Confirm' }).click()
  await expect(page.locator('.shelf-receipt')).toContainText('1 change to make.')
  await expect(page.locator('.shelf-receipt-note')).toHaveCount(0)
})

test('Cancel throws the whole draft away: nothing is sent, and the map returns to read-only', async ({ page }) => {
  const sent = await openShelf(page)
  await page.getByRole('button', { name: 'Layout' }).click()
  await page.getByRole('button', { name: 'Move section Uncommons of RB Origins' }).click()
  await page.getByRole('button', { name: 'Mixed Singles', exact: true }).click()
  await page.getByRole('button', { name: /Put Uncommons just on the far side of Promos/ }).click()
  await page.getByRole('button', { name: 'Cancel' }).click()
  expect(sent).toHaveLength(0)
  await expect(page.getByRole('button', { name: 'Layout' })).toBeVisible()
  await expect(page.getByRole('button', { name: /Move section/ })).toHaveCount(0)
})

test('the keyboard alone moves a section in edit mode, and Esc puts it down', async ({ page }) => {
  await openShelf(page)
  await page.getByRole('button', { name: 'Layout' }).click()
  const grip = page.getByRole('button', { name: 'Move section Signatures of RB Origins' })
  await grip.focus()
  await page.keyboard.press('Enter')
  await expect(page.locator('.shelf-lift')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.locator('.shelf-lift')).toHaveCount(0)
  await grip.focus()
  await page.keyboard.press('Space')
  await page.getByRole('button', { name: 'Another place in RB Origins' }).press('Enter')
  const gap = page.getByRole('button', { name: /Put Signatures just on the far side of Commons/ })
  await gap.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByText('1 change queued.', { exact: false })).toBeVisible()
})

test('a pointer drag queues a drop on the gap under the pointer', async ({ page }) => {
  await openShelf(page)
  await page.getByRole('button', { name: 'Layout' }).click()
  await page.getByRole('button', { name: 'Move section Commons of RB Origins' }).click()
  await page.getByRole('button', { name: 'Mixed Singles', exact: true }).click()
  const block = page.locator('.shelf-pair .shelf-block[data-lifted="true"]').first()
  const gap = page.getByRole('button', { name: /at the end of Mixed Singles nearest you/ })
  await page.locator('.shelf-pair').evaluate((el) => el.scrollIntoView({ block: 'start' }))
  const from = await block.boundingBox()
  const to = await gap.boundingBox()
  if (from === null || to === null) throw new Error('nothing to drag')
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2)
  await page.mouse.down()
  await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2, { steps: 8 })
  await page.mouse.up()
  await expect(page.getByText('1 change queued.', { exact: false })).toBeVisible()
})

test('the whole box queues as a merge, and New box queues a split', async ({ page }) => {
  const sent = await openShelf(page)
  await page.getByRole('button', { name: 'Layout' }).click()
  await page.getByRole('button', { name: 'Move section Uncommons of RB Origins' }).click()
  await page.getByRole('button', { name: 'This and the next' }).click()
  await page.getByRole('button', { name: 'New box' }).click()
  await page.getByRole('button', { name: /Put Uncommons into a new box/ }).click()
  await page.getByRole('button', { name: 'Confirm' }).click()
  expect(sent).toHaveLength(1)
  expect(sent[0]?.body).toMatchObject({ moves: [{ kind: 'section', first: 2, last: 3, new_box: true }] })
})

test('every press on the map is 40px or more', async ({ page }) => {
  await openShelf(page)
  await page.getByRole('button', { name: 'Layout' }).click()
  await page.getByRole('button', { name: 'Move section Uncommons of RB Origins' }).click()
  await page.getByRole('button', { name: 'Mixed Singles', exact: true }).click()
  const sizes = await page
    /* An icon button's 40px is its hit area around a 28px face: `icon-button.spec.ts` owns it. */
    .locator('.shelf .shelf-gap, .shelf .shelf-dests .bn-btn')
    .evaluateAll((els) => els.map((el) => Math.min(el.getBoundingClientRect().height, el.getBoundingClientRect().width)))
  expect(sizes.length).toBeGreaterThan(0)
  for (const size of sizes) expect(size).toBeGreaterThanOrEqual(40)
})

/* A box that changed since Edit layout was pressed (an S on the rig, another device's move):
   the server refuses the WHOLE draft, and the map reads its boxes again. */
test('a stale draft is refused whole, and the map reads again', async ({ page }) => {
  let reads = 0
  await page.route(/\/boxes(\?.*)?$/, (route) => {
    reads += 1
    return route.fulfill({ json: { boxes: BOXES, facets: { games: [], sets: {}, rarities: {} } } })
  })
  const sentence = 'RB Origins changed since the map was drawn, so nothing was moved. The map shows it as it is now.'
  await page.route(/\/boxes\/sections\/move-batch$/, (route) =>
    route.fulfill({ status: 409, json: { error: { code: 'draft_stale', message: sentence } } }),
  )
  await page.goto(ROUTE)
  await settleFonts(page)
  await expect(page.locator('.shelf-box')).toHaveCount(3)
  await page.getByRole('button', { name: 'Layout' }).click()
  await page.getByRole('button', { name: 'Move section Uncommons of RB Origins' }).click()
  await page.getByRole('button', { name: 'Mixed Singles', exact: true }).click()
  await page.getByRole('button', { name: /Put Uncommons just on the far side of Promos/ }).click()
  const before = reads
  await page.getByRole('button', { name: 'Confirm' }).click()
  await expect(
    page.getByText("A box's cards changed since Edit layout was pressed, so nothing in the draft was applied. The map shows it as it is now."),
  ).toBeVisible()
  await expect.poll(() => reads).toBeGreaterThan(before)
})

/* THE OWNER'S RULING (2026-09-27): card ranges rejoin edit mode. */
function inv(box: number, rows: Array<[number, string, number, number]>) {
  const cardsOf: Record<string, unknown> = {}
  for (const [index, name, section, order] of rows) {
    cardsOf[`${box}/${index}`] = {
      box, index, name, state: 'identified', cid: `${box}-${index}`,
      place: { box, index, order, section, card: index, label: name, slot: index },
    }
  }
  return { version: 2, cards: cardsOf }
}

async function stubCards(page: Page): Promise<void> {
  await page.route(/\/inventory\/1$/, (route) =>
    route.fulfill({ json: inv(1, [[1, 'c1', 1, 1], [12, 'u1', 2, 12], [13, 'u2', 2, 13], [14, 'u3', 2, 14], [30, 's1', 3, 30]]) }),
  )
  await page.route(/\/inventory\/2$/, (route) =>
    route.fulfill({ json: inv(2, [[1, 'm1', 1, 1], [2, 'm2', 1, 2], [16, 'p1', 2, 16]]) }),
  )
}

test('a lifted section shows its cards, and a range queues into the draft (no write until Confirm)', async ({ page }) => {
  await stubCards(page)
  const sent = await openShelf(page)
  await page.getByRole('button', { name: 'Layout' }).click()
  await page.getByRole('button', { name: 'Move section Uncommons of RB Origins' }).click()
  await page.getByRole('button', { name: 'Some cards' }).click()
  const list = page.getByRole('list', { name: 'The cards in this section' })
  await expect(list.getByRole('button')).toHaveText([/u1/, /u2/, /u3/])
  await list.getByRole('button', { name: /u2/ }).click()
  await list.getByRole('button', { name: /u3/ }).click()
  await expect(list.getByRole('button', { pressed: true })).toHaveCount(2)
  await page.getByRole('button', { name: 'Mixed Singles', exact: true }).click()
  await page.getByRole('button', { name: /Put 2 cards just on the far side of m2/ }).click()
  expect(sent).toHaveLength(0)
  await expect(page.getByText('1 change queued.', { exact: false })).toBeVisible()

  await page.getByRole('button', { name: 'Confirm' }).click()
  expect(sent).toHaveLength(1)
  expect(sent[0]?.body).toMatchObject({
    moves: [{ kind: 'range', box: 1, indices: [13, 14], to_box: 2, before_card: 2, section_end: null }],
  })
})

test('a mixed draft — a section and a range — sends both in one Confirm', async ({ page }) => {
  await stubCards(page)
  const sent = await openShelf(page)
  await page.getByRole('button', { name: 'Layout' }).click()
  await page.getByRole('button', { name: 'Move section Uncommons of RB Origins' }).click()
  await page.getByRole('button', { name: 'Some cards' }).click()
  const list = page.getByRole('list', { name: 'The cards in this section' })
  await list.getByRole('button', { name: /u1/ }).click()
  await page.getByRole('button', { name: 'Mixed Singles', exact: true }).click()
  await page.getByRole('button', { name: /Put u1 at the end of Promos, in Mixed Singles/ }).click()

  await page.getByRole('button', { name: 'Move section Old of Old Box' }).click()
  await page.getByRole('button', { name: 'Mixed Singles', exact: true }).click()
  await page.getByRole('button', { name: /at the end of Mixed Singles nearest you/ }).click()

  await page.getByRole('button', { name: 'Confirm' }).click()
  expect(sent).toHaveLength(1)
  expect(sent[0]?.body).toMatchObject({
    moves: [
      { kind: 'range', box: 1, indices: [12] },
      { kind: 'section', box: 3, first: 1, last: 1, to_box: 2 },
    ],
  })
})

test('a box the draft already touched cannot offer Some cards a second time', async ({ page }) => {
  await stubCards(page)
  await openShelf(page)
  await page.getByRole('button', { name: 'Layout' }).click()
  await page.getByRole('button', { name: 'Move section Commons of RB Origins' }).click()
  await page.getByRole('button', { name: 'Mixed Singles', exact: true }).click()
  await page.getByRole('button', { name: /at the end of Mixed Singles nearest you/ }).click()
  await page.getByRole('button', { name: 'Move section Signatures of RB Origins' }).click()
  await expect(page.getByRole('button', { name: 'Some cards' })).toHaveCount(0)
})

/* THE RE-REVIEW'S FINDING (2026-09-28): "dirtied" gated only the SOURCE a range could be
   picked up from. A box the draft already touched as a DESTINATION must be just as
   unreachable for a range: its live card list disagrees with what the earlier queued move
   already did to it. */
test('a box the draft already changed cannot be chosen as a range destination either', async ({ page }) => {
  await stubCards(page)
  await openShelf(page)
  await page.getByRole('button', { name: 'Layout' }).click()
  // Queue a section move that touches Mixed Singles (box 2) as a destination.
  await page.getByRole('button', { name: 'Move section Old of Old Box' }).click()
  await page.getByRole('button', { name: 'Mixed Singles', exact: true }).click()
  await page.getByRole('button', { name: /at the end of Mixed Singles nearest you/ }).click()
  await expect(page.getByText('1 change queued.', { exact: false })).toBeVisible()

  // Now lift a card range from an UNTOUCHED box and try to aim it at the touched one.
  await page.getByRole('button', { name: 'Move section Uncommons of RB Origins' }).click()
  await page.getByRole('button', { name: 'Some cards' }).click()
  await page.getByRole('list', { name: 'The cards in this section' }).getByRole('button', { name: /u1/ }).click()
  const dest = page.getByRole('button', { name: /Mixed Singles.*already changed/ })
  await expect(dest).toBeVisible()
  await expect(dest).toBeDisabled()
})

test('a stale draft on the card path is refused whole, the same way a section drop is', async ({ page }) => {
  await stubCards(page)
  let reads = 0
  await page.route(/\/boxes(\?.*)?$/, (route) => {
    reads += 1
    return route.fulfill({ json: { boxes: BOXES, facets: { games: [], sets: {}, rarities: {} } } })
  })
  const sentence = 'RB Origins changed since the map was drawn, so nothing was moved. The map shows it as it is now.'
  await page.route(/\/boxes\/sections\/move-batch$/, (route) =>
    route.fulfill({ status: 409, json: { error: { code: 'draft_stale', message: sentence } } }),
  )
  await page.goto(ROUTE)
  await settleFonts(page)
  await expect(page.locator('.shelf-box')).toHaveCount(3)
  await page.getByRole('button', { name: 'Layout' }).click()
  await page.getByRole('button', { name: 'Move section Uncommons of RB Origins' }).click()
  await page.getByRole('button', { name: 'Some cards' }).click()
  await page.getByRole('list', { name: 'The cards in this section' }).getByRole('button', { name: /u1/ }).click()
  await page.getByRole('button', { name: 'Mixed Singles', exact: true }).click()
  await page.getByRole('button', { name: /Put u1 at the end of Promos, in Mixed Singles/ }).click()
  const before = reads
  await page.getByRole('button', { name: 'Confirm' }).click()
  await expect(
    page.getByText("A box's cards changed since Edit layout was pressed, so nothing in the draft was applied. The map shows it as it is now."),
  ).toBeVisible()
  await expect.poll(() => reads).toBeGreaterThan(before)
})
