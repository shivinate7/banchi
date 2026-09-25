import { test, expect, type Page } from '@playwright/test'
import type { BoxRecord, SectionDetail, SectionMoveResult } from '../src/types'
import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'

/* THE SHELF (D264): every box from above, a section picked up, a box picked, and a gap pressed
 * or dragged to. EVERYTHING IS STUBBED: the two routes the view writes through are answered
 * here, and what the screen SENT is what each case asserts. The store is never touched. */

sealEveryTest()

const ROUTE = '/#/inventory?view=shelf'

function section(n: number, name: string | null, count: number, first: string): SectionDetail {
  return {
    section: n,
    start: 1,
    end: count,
    count,
    name,
    first_name: `${first} first`,
    last_name: `${first} last`,
    first_cid: `${first}-a`,
    last_cid: `${first}-z`,
  }
}

function box(n: number, name: string, sections: SectionDetail[], state = 'open'): BoxRecord {
  return {
    box: n,
    bid: n,
    name,
    sections: sections.map((s) => s.section),
    state,
    capacity: 0,
    fill: 0,
    next_index: 1,
    cards: 0,
    on_hand: sections.reduce((sum, s) => sum + s.count, 0),
    sold: 0,
    retired: 0,
    moved: 0,
    listed: 0,
    sections_detail: sections,
  } as BoxRecord
}

const BOXES: BoxRecord[] = [
  box(1, 'RB Origins', [section(1, 'Commons', 11, 'c'), section(2, 'Uncommons', 10, 'u'), section(3, 'Signatures', 13, 's')]),
  box(2, 'Mixed Singles', [section(1, null, 15, 'm'), section(2, 'Promos', 4, 'p')]),
  box(3, 'Sealed Box', [section(1, 'Old', 5, 'o')], 'closed'),
]

const RESULT: SectionMoveResult = {
  move: 'm1',
  box: 1,
  to_box: 2,
  created: null,
  moved: 10,
  landed: [2],
  receipt: {
    heading: 'Move 10 cards from RB Origins to Mixed Singles.',
    steps: [
      'In RB Origins, find the divider Uncommons. Its first card is u first. Its last card is u last.',
      'Take out that divider and the 10 cards on your side of it, up to the next divider.',
      'In Mixed Singles, find the divider Promos. Put them just on the far side of it, in the same order.',
    ],
    renumbered: ['In Mixed Singles, Promos moves from Section 2 to Section 3.'],
  },
  boxes: [],
}

type Sent = { path: string; body: unknown }

async function openShelf(page: Page): Promise<Sent[]> {
  const sent: Sent[] = []
  await page.route(/\/boxes(\?.*)?$/, (route) =>
    route.fulfill({ json: { boxes: BOXES, facets: { games: [], sets: {}, rarities: {} } } }),
  )
  await page.route(/\/boxes\/\d+\/sections\/move$/, async (route) => {
    sent.push({ path: new URL(route.request().url()).pathname, body: route.request().postDataJSON() })
    await route.fulfill({ json: RESULT })
  })
  await page.route(/\/boxes\/sections\/undo$/, async (route) => {
    sent.push({ path: new URL(route.request().url()).pathname, body: route.request().postDataJSON() })
    await route.fulfill({ json: { move: 'm1', undone: true, boxes: [] } })
  })
  await page.goto(ROUTE)
  await settleFonts(page)
  await expect(page.locator('.shelf-box')).toHaveCount(3)
  return sent
}

test('every box is drawn from above, card 1 at the top, counts and no money', async ({ page }) => {
  await openShelf(page)
  const first = page.locator('.shelf-box').first()
  await expect(first.locator('.shelf-block-name')).toHaveText(['Commons', 'Uncommons', 'Signatures'])
  await expect(page.locator('.shelf')).not.toContainText('$')
  /* A block's height follows its count: the 13-card section is taller than the 10-card one. */
  const heights = await first.locator('.shelf-block').evaluateAll((els) => els.map((el) => el.getBoundingClientRect().height))
  expect(heights[2]).toBeGreaterThan(heights[1] ?? 0)
  for (const h of heights) expect(h).toBeGreaterThanOrEqual(44)
})

test('pick up, pick the box, press a gap: the write names the gap and aims at what was seen', async ({ page }) => {
  const sent = await openShelf(page)
  await page.getByRole('button', { name: 'Move section Uncommons of RB Origins' }).click()
  await expect(page.getByRole('button', { name: 'Sealed Box is sealed' })).toBeDisabled()
  await page.getByRole('button', { name: 'Mixed Singles', exact: true }).click()
  await expect(page.locator('.shelf-pair .shelf-box')).toHaveCount(2)
  await page.getByRole('button', { name: /Put Uncommons just on the far side of Promos/ }).click()
  await expect(page.locator('.shelf-receipt')).toContainText('Move 10 cards from RB Origins to Mixed Singles.')
  expect(sent[0]).toEqual({
    path: '/boxes/1/sections/move',
    body: { first: 2, last: 2, to_box: 2, before: 2, aim: { count: 10, first: 'u-a', last: 'u-z' } },
  })
  await page.keyboard.press('u')
  await expect(page.locator('.shelf-receipt')).toContainText('Put back.')
  expect(sent[1]).toEqual({ path: '/boxes/sections/undo', body: { move: 'm1' } })
})

test('the keyboard alone moves a section, and Esc puts it down', async ({ page }) => {
  const sent = await openShelf(page)
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
  await expect.poll(() => sent.length).toBe(1)
  expect((sent[0]?.body as { to_box: number; before: number }).before).toBe(1)
  expect((sent[0]?.body as { to_box: number }).to_box).toBe(1)
})

test('a pointer drag drops the section on the gap under the pointer', async ({ page }) => {
  const sent = await openShelf(page)
  await page.getByRole('button', { name: 'Move section Commons of RB Origins' }).click()
  await page.getByRole('button', { name: 'Mixed Singles', exact: true }).click()
  const block = page.locator('.shelf-pair .shelf-block[data-lifted="true"]').first()
  const gap = page.getByRole('button', { name: /at the end of Mixed Singles nearest you/ })
  await page.locator('.shelf-pair').evaluate((el) => el.scrollIntoView({ block: 'start' }))
  const from = await block.boundingBox()
  const to = await gap.boundingBox()
  if (from === null || to === null) throw new Error('nothing to drag')
  await page.mouse.move(from.x + 20, from.y + from.height / 2)
  await page.mouse.down()
  await page.mouse.move(to.x + to.width / 2, to.y + to.height / 2, { steps: 8 })
  await page.mouse.up()
  await expect.poll(() => sent.length).toBe(1)
  expect(sent[0]?.body).toMatchObject({ first: 1, last: 1, to_box: 2, before: null })
})

test('the whole box moves as a merge, and a new box is a split', async ({ page }) => {
  const sent = await openShelf(page)
  await page.getByRole('button', { name: 'Move section Uncommons of RB Origins' }).click()
  await page.getByRole('button', { name: 'This and the next' }).click()
  await page.getByRole('button', { name: 'New box' }).click()
  await page.getByRole('button', { name: /Put Uncommons into a new box/ }).click()
  await expect.poll(() => sent.length).toBe(1)
  expect(sent[0]?.body).toMatchObject({ first: 2, last: 3, new_box: true })
})

test('every press on the shelf is 40px or more', async ({ page }) => {
  await openShelf(page)
  await page.getByRole('button', { name: 'Move section Uncommons of RB Origins' }).click()
  await page.getByRole('button', { name: 'Mixed Singles', exact: true }).click()
  const sizes = await page
    /* An icon button's 40px is its hit area around a 28px face: `icon-button.spec.ts` owns it. */
    .locator('.shelf .shelf-gap, .shelf .shelf-dests .bn-btn')
    .evaluateAll((els) => els.map((el) => Math.min(el.getBoundingClientRect().height, el.getBoundingClientRect().width)))
  expect(sizes.length).toBeGreaterThan(0)
  for (const size of sizes) expect(size).toBeGreaterThanOrEqual(40)
})

/* THE NEXT SLICE (owner, 2026-09-25): one card or a range from a lifted section. */
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

async function stubCards(page: Page): Promise<Sent[]> {
  const sent: Sent[] = []
  await page.route(/\/inventory\/1$/, (route) =>
    route.fulfill({ json: inv(1, [[1, 'c1', 1, 1], [12, 'u1', 2, 12], [13, 'u2', 2, 13], [14, 'u3', 2, 14], [30, 's1', 3, 30]]) }),
  )
  await page.route(/\/inventory\/2$/, (route) =>
    route.fulfill({ json: inv(2, [[1, 'm1', 1, 1], [2, 'm2', 1, 2], [16, 'p1', 2, 16]]) }),
  )
  await page.route(/\/boxes\/\d+\/cards\/move$/, async (route) => {
    sent.push({ path: new URL(route.request().url()).pathname, body: route.request().postDataJSON() })
    await route.fulfill({ json: { ...RESULT, receipt: { ...RESULT.receipt, heading: 'Move 2 cards from RB Origins to Mixed Singles.' } } })
  })
  return sent
}

test('a lifted section shows its cards; a range drops in front of a card of the other box', async ({ page }) => {
  const sent = await stubCards(page)
  await openShelf(page)
  await page.getByRole('button', { name: 'Move section Uncommons of RB Origins' }).click()
  await page.getByRole('button', { name: 'Some cards' }).click()
  const list = page.getByRole('list', { name: 'The cards in this section' })
  await expect(list.getByRole('button')).toHaveText([/u1/, /u2/, /u3/])
  await list.getByRole('button', { name: /u2/ }).click()
  await list.getByRole('button', { name: /u3/ }).click()
  await expect(list.getByRole('button', { pressed: true })).toHaveCount(2)
  await page.getByRole('button', { name: 'Mixed Singles', exact: true }).click()
  await page.getByRole('button', { name: /Put 2 cards just on the far side of m2/ }).click()
  await expect(page.locator('.shelf-receipt')).toContainText('Move 2 cards from RB Origins to Mixed Singles.')
  expect(sent[0]).toEqual({
    path: '/boxes/1/cards/move',
    body: { indices: [13, 14], to_box: 2, before_card: 2, section_end: null, aim: { count: 2, first: '1-13', last: '1-14' } },
  })
})

test('one card drops at the end of a section, and the keyboard alone can do it', async ({ page }) => {
  const sent = await stubCards(page)
  await openShelf(page)
  await page.getByRole('button', { name: 'Move section Uncommons of RB Origins' }).click()
  await page.getByRole('button', { name: 'Some cards' }).click()
  const u1 = page.getByRole('list', { name: 'The cards in this section' }).getByRole('button', { name: /u1/ })
  await u1.focus()
  await page.keyboard.press('Enter')
  await page.getByRole('button', { name: 'Mixed Singles', exact: true }).press('Enter')
  const gap = page.getByRole('button', { name: /Put u1 at the end of Promos, in Mixed Singles/ })
  await gap.focus()
  await page.keyboard.press('Enter')
  await expect.poll(() => sent.length).toBe(1)
  expect(sent[0]?.body).toMatchObject({ indices: [12], to_box: 2, before_card: null, section_end: 2 })
})
