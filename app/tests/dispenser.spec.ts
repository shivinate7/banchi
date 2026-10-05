// Protects: The dispenser control sits under the shutter, gives its reason when it cannot deal, and stops dealing the moment a fire is dropped.
// Governs: D316, D19, D313
import { expect, test } from '@playwright/test'
import { sealEveryTest } from './shell'
import type { Page } from '@playwright/test'
import { CARD, GAP_LUMA, armMotion, control, fakeBluetooth, injectScene, slowCapture, writes } from './dispenserRig'

/* THE DISPENSER'S BROWSER HALF, in a real browser against the real capture screen. The unit tier
 * (`unit/dispenser.unit.ts`) holds the loop against tcg-dealer's recorded sequences; this file
 * proves the wiring: the control, its reasons, and the one gate that matters, that dealing stops
 * when a fire is dropped. `navigator.bluetooth` is a fake, installed by an init script, that
 * answers every START with COMPLETE after 420 ms and records every write on `window.__writes`.
 *
 * NO BOX IS EVER SELECTED, like `motion-live.spec.ts`: the first fire is dropped, and that drop
 * must stop dealing. The camera is a canvas stream into the screen's own video element.
 * The fake device and the camera live in `dispenserRig.ts`. */

sealEveryTest({ store: true })

test('in Manual the control is there, and Start is off with its reason', async ({ page }) => {
  await fakeBluetooth(page)
  await page.goto('/#/capture')
  await expect(page.locator('.capture-trigger')).toHaveAttribute('data-trigger', 'manual:c')
  await expect(page.locator('.capture-controls').getByText('Not connected')).toBeVisible()
  await control(page, 'Connect dispenser').click()
  const start = control(page, 'Start dispenser')
  await expect(start).toBeVisible()
  await expect(start).toBeDisabled()
  await expect(page.locator('.capture-controls').getByText('Turn on motion first')).toBeVisible()
  expect(await writes(page)).toEqual([])
})

test('with no navigator.bluetooth the screen says it needs Chrome on the Mac', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, 'bluetooth', { configurable: true, value: undefined })
  })
  await page.goto('/#/capture')
  await expect(page.locator('.capture-controls').getByText('Needs Chrome on the Mac')).toBeVisible()
  await expect(control(page, 'Connect dispenser')).toBeDisabled()
})

/* THE WIRE THIS SCREEN NEEDS, stubbed. `POST /capture` answers an ERROR, so a fire with a box
 * picked is a capture that fails: the screen counts it or halts, and either way dealing must stop.
 * Nothing reaches the real store. */
const GAME = {
  key: 'pokemon', display: 'Pokémon', product_line: 'Pokemon', rarities: ['Common'], finishes: ['normal'],
  condition_by_finish: { normal: 'Near Mint' }, finish_by_rarity: { Common: ['normal'] }, located: true,
  join_key: 'number_over_printed_total', prompt: 'pokemon', crop_bands: ['title', 'number'], card_aspect: 0.716,
  unverified: false, catalogued: true,
}
const SPAN = { section: 1, start: 1, end: null, count: 0, name: null, div: '1' }
const BOX = {
  box: 5, bid: 15, name: 'Dispenser box', sections: [1], state: 'open', capacity: null, fill: 0, next_index: 1,
  cards: 0, sold: 0, retired: 0, listed: 0, on_hand: 0, sections_detail: [SPAN], layout_token: 'tok1',
}
const json = (body: unknown, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) })
let capturePosts = 0

async function stubWire(page: Page): Promise<void> {
  capturePosts = 0
  await page.route(/\/games$/, (r) => r.fulfill(json({ default: 'pokemon', products: [], product_game: 'pokemon_code', games: [GAME] })))
  await page.route(/\/status$/, (r) => r.fulfill(json({ cards: 0, next_index: { '5': 1 } })))
  await page.route(/\/boxes$/, (r) => r.fulfill(json({ boxes: [BOX] })))
  await page.route(/\/capture\/sitting$/, (r) => r.fulfill(json({ open: true, gap_minutes: 30, cards: [] })))
  await page.route(/\/capture$/, (r) => {
    capturePosts += 1
    return r.fulfill(json({ error: { code: 'capture_failed', message: 'The capture failed.' } }, 500))
  })
}

/** Camera picked, optionally a box picked, motion armed, scene injected, dispenser connected. */
async function ready(page: Page, withBox: boolean, manual = false): Promise<void> {
  await fakeBluetooth(page)
  await stubWire(page)
  await page.goto('/#/capture')
  await expect(page.getByLabel('Rig')).toBeVisible()
  await page.keyboard.press('v')
  await page.getByLabel('Rig').getByRole('button', { name: 'Connect' }).click()
  await page.locator('.capture-opt').filter({ hasText: /Canvas Cam Link/ }).click()
  await page.keyboard.press('Escape')
  if (withBox) {
    await expect(async () => {
      await page.keyboard.press('b')
      await expect(page.locator('.capture-opt').filter({ hasText: /Dispenser box/ })).toBeVisible({ timeout: 1_000 })
    }).toPass({ timeout: 15_000 })
    await page.keyboard.type('5')
    await page.keyboard.press('Enter')
  }
  if (manual) return // Manual trigger: no motion, no scene, no dispenser
  await armMotion(page)
  await injectScene(page)
  await expect(page.locator('.capture-motion-hud')).toBeAttached({ timeout: 5_000 })
  await control(page, 'Connect dispenser').click()
}

test('armed with a camera but no box, Start is off and says to pick a box first', async ({ page }) => {
  await ready(page, false)
  await expect(control(page, 'Start dispenser')).toBeDisabled()
  await expect(page.locator('.capture-controls').getByText('Pick a box first')).toBeVisible()
  expect(await writes(page)).toEqual([])
})

test('with a box picked, a capture that fails stops dealing and the last write is STOP', async ({ page }) => {
  await ready(page, true)
  const start = control(page, 'Start dispenser')
  await expect(start).toBeEnabled({ timeout: 5_000 })
  await start.click()
  await expect(control(page, 'Stop dispenser')).toBeVisible()
  expect((await writes(page))[0]).toBe('MOTOR:START')

  // the card lands in front of the lens: motion fires, the capture POST fails
  await page.evaluate((base) => {
    ;(window as unknown as { __scene: { base: number } }).__scene.base = base
  }, CARD)
  await expect(control(page, 'Start dispenser')).toBeVisible({ timeout: 8_000 })
  expect(capturePosts).toBeGreaterThan(0)
  // the failed save is held: no Resume button exists, so Start's reason is the one thing to press
  await expect(page.locator('.capture-controls').getByText('Retry saving first')).toBeVisible()
  await expect(page.getByRole('button', { name: /^Resume captures/ })).toHaveCount(0)

  const sent = await writes(page)
  expect(sent.at(-1)).toBe('MOTOR:STOP')
  await page.waitForTimeout(1_500) // keep: a quiet 1.5 s after STOP
  expect(await writes(page)).toEqual(sent)
  for (const w of sent) expect(['MOTOR:START', 'MOTOR:STOP']).toContain(w)
})

test('a fire while the previous save is still out is photographed, not swallowed, and dealing goes on', async ({ page }) => {
  await ready(page, true)
  // Registered after `stubWire`, so it answers first: every save takes 4 s, far past a card's 0.42 s.
  const wire = await slowCapture(page, 4_000)
  const start = control(page, 'Start dispenser')
  await expect(start).toBeEnabled({ timeout: 5_000 })
  await start.click()
  const scene = (base: number) =>
    page.evaluate((b) => {
      ;(window as unknown as { __scene: { base: number } }).__scene.base = b
    }, base)

  await scene(CARD) // card 1 lands: fire 1, its save is held
  await expect.poll(wire.posts, { timeout: 8_000 }).toBe(1)
  await scene(GAP_LUMA) // card 1 leaves, card 2 arrives while save 1 is still out
  await page.waitForTimeout(400) // keep: let the gap register before the next card
  await scene(CARD - 40) // a different picture: the same one would be suppressed as unchanged
  await expect.poll(wire.posts, { timeout: 8_000 }).toBe(2) // fire 2 was kept and saved, not dropped
  await expect(page.locator('.capture-controls').getByText(/not photographed|Resume captures first/)).toHaveCount(0)
  await expect(control(page, 'Stop dispenser')).toBeVisible()
  await control(page, 'Stop dispenser').click()
})

test('saves reach the server in capture order: card 2 is sent only after card 1 has answered', async ({ page }) => {
  await ready(page, true)
  const wire = await slowCapture(page, 2_000)
  const start = control(page, 'Start dispenser')
  await expect(start).toBeEnabled({ timeout: 5_000 })
  await start.click()
  const scene = (base: number) =>
    page.evaluate((b) => {
      ;(window as unknown as { __scene: { base: number } }).__scene.base = b
    }, base)

  await scene(CARD) // card 1: fire 1, its save is held 2 s
  await expect.poll(wire.posts, { timeout: 8_000 }).toBe(1)
  await scene(GAP_LUMA)
  await page.waitForTimeout(400) // keep: let the gap register before the next card
  await scene(CARD - 40) // card 2 is photographed while save 1 is still out
  await expect.poll(wire.posts, { timeout: 8_000 }).toBe(2)
  // two photos in flight at once may commit out of order: card 2 goes only after card 1 answered
  expect(wire.events()).toEqual(['sent:1', 'answered:1', 'sent:2'])
  await expect.poll(wire.answered, { timeout: 8_000 }).toBe(2)
  // the slots came back 1 then 2: the second card's label follows the first
  await expect(page.getByText('Box 5, Card 2').first()).toBeVisible()
  await control(page, 'Stop dispenser').click()
})

/* ---- a save that does not come back: the store must know where every card is ---- */
const sceneTo = (page: Page, base: number) =>
  page.evaluate((b) => {
    ;(window as unknown as { __scene: { base: number } }).__scene.base = b
  }, base)

/** Card 1 fires and its save is held; card 2 is photographed behind it (queued, in memory). */
async function twoCards(page: Page, wire: Awaited<ReturnType<typeof slowCapture>>): Promise<void> {
  const start = control(page, 'Start dispenser')
  await expect(start).toBeEnabled({ timeout: 5_000 })
  await start.click()
  await sceneTo(page, CARD)
  await expect.poll(wire.posts, { timeout: 8_000 }).toBe(1)
  await sceneTo(page, GAP_LUMA)
  await page.waitForTimeout(400) // keep: let the gap register before the next card
  await sceneTo(page, CARD - 40)
  await page.waitForTimeout(400) // keep: card 2's fire lands behind save 1
}

/* CONTRACT: when card 1's save fails twice, the screen says `Box 5, Card 1 was not saved` (its own
 * label, the slot it was to take) and offers a button named `Retry saving` that re-sends it, then card 2,
 * in order. Card 2 is never sent in the meantime. */
test('card 1 fails twice with card 2 queued: card 2 is never sent, the dealer stops, the screen names card 1', async ({ page }) => {
  await ready(page, true)
  const wire = await slowCapture(page, 1_500, (n) => n <= 2)
  await twoCards(page, wire)
  await expect.poll(wire.answered, { timeout: 10_000 }).toBe(2) // the save and its one retry, both failed
  await page.waitForTimeout(2_000) // keep: card 2 gets time to be wrongly sent
  expect(wire.events()).toEqual(['sent:1', 'answered:1', 'sent:2', 'answered:2']) // no third POST: card 2 held
  await expect(control(page, 'Start dispenser')).toBeVisible() // the dealer is stopped
  await expect(page.getByText(/Box 5, Card 1\b.*not saved|not saved.*Box 5, Card 1\b/i).first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Retry saving' })).toBeVisible()
})

test('the not-saved line names the card that failed, never "the last card"', async ({ page }) => {
  await ready(page, true)
  const wire = await slowCapture(page, 1_500, (n) => n <= 2)
  await twoCards(page, wire)
  await expect.poll(wire.answered, { timeout: 10_000 }).toBe(2)
  await expect(control(page, 'Start dispenser')).toBeVisible()
  await expect(page.getByText(/Box 5, Card 1\b/).first()).toBeVisible()
  await expect(page.getByText(/last card/i)).toHaveCount(0)
})

/* CONTRACT: a reload with saves out reports every unsaved card, by count, in the carried-over notice. */
test('a reload with two saves in flight reports both unsaved cards', async ({ page }) => {
  await ready(page, true)
  const wire = await slowCapture(page, 60_000)
  await twoCards(page, wire)
  await page.reload()
  await expect(page.locator('.capture-carried')).toContainText(/\b2\b.*(cards|captures)/i, { timeout: 10_000 })
})

test('Undo pressed while a save is out says so, plainly, and deletes nothing', async ({ page }) => {
  await ready(page, true)
  const wire = await slowCapture(page, (n) => (n === 1 ? 50 : 6_000))
  const start = control(page, 'Start dispenser')
  await expect(start).toBeEnabled({ timeout: 5_000 })
  await start.click()
  await sceneTo(page, CARD)
  await expect.poll(wire.answered, { timeout: 8_000 }).toBe(1) // card 1 is saved
  await sceneTo(page, GAP_LUMA)
  await page.waitForTimeout(400) // keep: let the gap register before the next card
  await sceneTo(page, CARD - 40)
  await expect.poll(wire.posts, { timeout: 8_000 }).toBe(2) // card 2's save is out
  await page.keyboard.press('u')
  await expect(page.locator('.capture-undo-note')).toContainText(/saving|saved|wait/i, { timeout: 3_000 })
})

/* ---- Retry saving, and a held photo is never dropped ---- */
const slowThenQuick = (n: number) => (n <= 2 ? 1_500 : 150) // posts 1 and 2 are the failing pair
const unsaved = (page: Page) => page.locator('.capture-unsaved')
const captureButton = (page: Page) => page.getByRole('button', { name: 'Capture', exact: true })

/** Card 1's save fails twice, so card 2 is held behind it, and the dealer has stopped. */
async function held(page: Page, failIf: (post: number) => boolean, setup?: () => Promise<void>) {
  await ready(page, true)
  await setup?.()
  const wire = await slowCapture(page, slowThenQuick, failIf)
  await twoCards(page, wire)
  await expect.poll(wire.answered, { timeout: 10_000 }).toBe(2)
  await expect(unsaved(page)).toBeVisible()
  await expect(control(page, 'Start dispenser')).toBeVisible()
  return wire
}

test('R1: Retry saving sends card 1 then card 2, in order, each once, and the notice clears', async ({ page }) => {
  const wire = await held(page, (n) => n <= 2)
  await page.getByRole('button', { name: 'Retry saving' }).click()
  await expect.poll(wire.answered, { timeout: 10_000 }).toBe(4)
  await page.waitForTimeout(1_500) // keep: a stray extra POST gets time to show
  expect(wire.events()).toEqual([
    'sent:1', 'answered:1', 'sent:2', 'answered:2', 'sent:3', 'answered:3', 'sent:4', 'answered:4',
  ])
  const bodies = wire.bodies()
  expect(bodies[2]).toBe(bodies[0]) // card 1's own frame goes first
  expect(bodies[3]).not.toBe(bodies[2]) // card 2's own, different frame second
  await expect(unsaved(page)).toHaveCount(0)
})

test('R2: on retry card 1 saves and card 2 fails: card 2 stays held, the dealer stays stopped, the notice names card 2', async ({ page }) => {
  const wire = await held(page, (n) => n <= 2 || n === 4)
  await page.getByRole('button', { name: 'Retry saving' }).click()
  await expect.poll(wire.answered, { timeout: 10_000 }).toBe(4)
  await expect(unsaved(page)).toBeVisible()
  await expect(unsaved(page)).toContainText(/Box 5, Card 2\b.*not saved|not saved.*Box 5, Card 2\b/i)
  await expect(unsaved(page)).not.toContainText(/Card 1\b/)
  await expect(control(page, 'Start dispenser')).toBeVisible()
  await page.waitForTimeout(1_500) // keep: the dealer gets time to wrongly restart
  expect((await writes(page)).filter((w) => w === 'MOTOR:START')).toHaveLength(2)
})

test('R3: while a photo is held, Capture and the dispenser do nothing, there is no Resume, and the held frame survives', async ({ page }) => {
  const wire = await held(page, (n) => n <= 2)
  const posts = wire.posts()
  await captureButton(page).click({ force: true })
  await page.waitForTimeout(800) // keep: a wrongly sent POST gets time to land
  expect(wire.posts()).toBe(posts)
  await expect(page.getByRole('button', { name: /^Resume captures/ })).toHaveCount(0) // a failed save has no Resume
  await captureButton(page).click({ force: true })
  const start = control(page, 'Start dispenser')
  await expect(start).toBeDisabled() // and so is the dispenser
  await start.click({ force: true })
  await page.waitForTimeout(1_200) // keep: a wrongly sent POST or START gets time to land
  expect(wire.posts()).toBe(posts)
  expect((await writes(page)).filter((w) => w === 'MOTOR:START')).toHaveLength(2)
  // both frames are still there, and Retry saving sends them in order
  await expect(unsaved(page)).toBeVisible()
  await page.getByRole('button', { name: 'Retry saving' }).click()
  await expect.poll(wire.answered, { timeout: 10_000 }).toBe(4)
  expect(wire.events().slice(4)).toEqual(['sent:3', 'answered:3', 'sent:4', 'answered:4'])
})

/* MANUAL MODE keeps the generic halt: the banner and its Resume stay, and Resume never releases a held photo. */
test('R10: manual mode, a server halt with a held photo keeps its banner and Resume; Resume releases nothing and Retry saving sends it', async ({ page }) => {
  await ready(page, true, true)
  const wire = await slowCapture(page, 300, (n) => n === 1) // the first save fails, later ones succeed
  await captureButton(page).click()
  await expect.poll(wire.answered, { timeout: 8_000 }).toBe(1)
  await expect(page.getByText(/Captures are paused/i).first()).toBeVisible()
  const resume = page.getByRole('button', { name: /^Resume captures/ })
  await expect(resume).toBeVisible()
  await expect(unsaved(page).first()).toContainText(/Box 5, Card 1 was not saved/)
  await resume.click()
  await captureButton(page).click({ force: true })
  await page.waitForTimeout(800) // keep: a wrongly sent POST gets time to land
  expect(wire.posts()).toBe(1) // Resume and Capture released nothing
  await expect(unsaved(page).first()).toContainText(/Box 5, Card 1 was not saved/)
  await page.getByRole('button', { name: 'Retry saving' }).first().click()
  await expect.poll(wire.answered, { timeout: 8_000 }).toBe(2)
  await expect(unsaved(page)).toHaveCount(0)
})

test('R11: a camera halt keeps its banner and Resume', async ({ page }) => {
  await ready(page, true, true)
  await slowCapture(page, 100)
  // the camera dies under the screen: the next capture has no frame to take
  await page.evaluate(() => {
    const video = document.querySelector<HTMLVideoElement>('.capture-media')
    const stream = video?.srcObject as MediaStream | null
    for (const track of stream?.getTracks() ?? []) track.stop()
  })
  await captureButton(page).click({ force: true })
  await expect(page.getByText(/Captures are paused/i).first()).toBeVisible({ timeout: 8_000 })
  await expect(page.getByRole('button', { name: /^Resume captures/ })).toBeVisible()
})

test('R4: the not-saved notice says what was sent and what to press, with no mechanism word', async ({ page }) => {
  await held(page, (n) => n <= 2)
  const notice = unsaved(page)
  await expect(notice).toContainText(/Box 5, Card 1 was not saved/)
  await expect(notice).toContainText(/Nothing after it was sent/)
  await expect(notice).toContainText(/Retry saving/)
  await expect(notice).not.toContainText(/held here/i)
})

const SPANS_AFTER_S = [{ ...SPAN, end: 1 }, { ...SPAN, section: 2, start: 2, div: '2' }]

/** Counts the requests a divider or an undo would send: `POST` and `DELETE /boxes/5/sections`, and
 *  any write to `/inventory/5/<n>`. Answers a POST with the box row after S (two sections). */
async function countWrites(page: Page): Promise<{ opened: () => number; closed: () => number; removed: () => number }> {
  let opened = 0
  let closed = 0
  let removed = 0
  await page.route(/\/boxes\/5\/sections/, (route) => {
    const method = route.request().method()
    if (method === 'POST') {
      opened += 1
      return route.fulfill(json({ ...BOX, sections: [1, 2], sections_detail: SPANS_AFTER_S }))
    }
    if (method === 'DELETE') {
      closed += 1
      return route.fulfill(json(BOX))
    }
    return route.fallback()
  })
  await page.route(/\/inventory\/5\/\d+/, (route) => {
    removed += 1
    return route.fulfill(json({ error: { code: 'refused', message: 'not under test' } }, 409))
  })
  return { opened: () => opened, closed: () => closed, removed: () => removed }
}

test('R5: while held, S and the Section button open no divider; after Retry both cards land in the divider section and S works', async ({ page }) => {
  let w!: Awaited<ReturnType<typeof countWrites>>
  const wire = await held(page, (n) => n <= 2, async () => {
    w = await countWrites(page)
    await page.keyboard.press('s') // the divider first: the held frames claim its section
    await expect.poll(w.opened, { timeout: 5_000 }).toBe(1)
  })
  await page.keyboard.press('s')
  await page.getByRole('button', { name: 'Section', exact: true }).click({ force: true })
  await page.waitForTimeout(800) // keep: a wrongly sent section POST gets time to land
  expect(w.opened()).toBe(1)
  await page.getByRole('button', { name: 'Retry saving' }).click()
  await expect.poll(wire.answered, { timeout: 10_000 }).toBe(4)
  expect(wire.sections()).toEqual(['2', '2', '2', '2']) // every POST claims the divider's section, so the check can fail
  await expect(unsaved(page)).toHaveCount(0)
  await page.keyboard.press('s')
  await expect.poll(w.opened, { timeout: 5_000 }).toBe(2) // S works again
})

test('R7: while held, undo (divider and back) sends no request and the divider stays; after Retry the cards land in its section and undo works', async ({ page }) => {
  const w = await countWrites(page)
  await ready(page, true)
  // post 1 saves (card 0, a committed shot), posts 2 and 3 fail, later posts save
  const wire = await slowCapture(page, (n) => (n === 1 ? 100 : n <= 3 ? 1_500 : 150), (n) => n === 2 || n === 3)
  const start = control(page, 'Start dispenser')
  await expect(start).toBeEnabled({ timeout: 5_000 })
  await start.click()
  await sceneTo(page, CARD)
  await expect.poll(wire.answered, { timeout: 8_000 }).toBe(1) // card 0 is a committed shot
  await sceneTo(page, GAP_LUMA)
  await page.keyboard.press('s') // a divider after it
  await expect.poll(w.opened, { timeout: 5_000 }).toBe(1)
  await page.waitForTimeout(400) // keep: let the gap register before the next card
  await sceneTo(page, CARD - 40)
  await expect.poll(wire.posts, { timeout: 8_000 }).toBe(2) // card 1 after the divider, its save held
  await sceneTo(page, GAP_LUMA)
  await page.waitForTimeout(400) // keep: let the gap register before the next card
  await sceneTo(page, CARD)
  await expect.poll(wire.answered, { timeout: 10_000 }).toBe(3)
  await expect(unsaved(page)).toBeVisible()

  await page.keyboard.press('u') // undo the divider
  await page.locator('footer.capture-undo .capture-undo-row').first().click({ force: true }) // undo back
  await page.waitForTimeout(800) // keep: a wrongly sent undo gets time to land
  expect(w.closed() + w.removed()).toBe(0)
  await expect(page.locator('.capture-undo-note')).toContainText(/Retry saving first/)

  await page.getByRole('button', { name: 'Retry saving' }).click()
  await expect.poll(wire.answered, { timeout: 10_000 }).toBe(5)
  expect(wire.sections().slice(3)).toEqual(['2', '2']) // both held cards claim the divider's section
  await expect(unsaved(page)).toHaveCount(0)
  await page.keyboard.press('u')
  await expect.poll(() => w.closed() + w.removed(), { timeout: 5_000 }).toBeGreaterThan(0) // undo works again
})

for (const [width, height] of [[1440, 900], [820, 1100]] as const) {
  test(`R9: after a second save failure the one notice is uncovered and Retry saving is clickable at ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height })
    const wire = await held(page, (n) => n <= 2)
    const notice = unsaved(page)
    const title = notice.getByText('Box 5, Card 1 was not saved')
    await expect(title).toBeVisible()
    const retry = page.getByRole('button', { name: 'Retry saving' })
    await expect(retry).toBeVisible()
    await retry.scrollIntoViewIfNeeded()
    // the topmost element at the centre of each is the thing itself, not a banner over it
    const covered = (locator: typeof title, within: string) =>
      locator.evaluate((el, sel) => {
        const box = el.getBoundingClientRect()
        const top = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2)
        return top === null || top.closest(sel) === null
      }, within)
    expect(await covered(title, '.capture-unsaved'), 'the title is covered').toBe(false)
    expect(await covered(retry, 'button'), 'Retry saving is covered').toBe(false)
    const fits = await retry.evaluate((el) => {
      const b = el.getBoundingClientRect()
      return b.top >= 0 && b.left >= 0 && b.bottom <= innerHeight && b.right <= innerWidth
    })
    expect(fits, 'Retry saving is clipped by the viewport').toBe(true)
    await expect(page.getByText(/check whether that card was recorded/i)).toHaveCount(0)
    await expect(page.getByText(/Captures are paused/i)).toHaveCount(0)
    await expect(notice).toContainText(/Nothing after it was sent\. Press Retry saving\./)
    await retry.click() // no force: nothing sits over it
    await expect.poll(wire.answered, { timeout: 10_000 }).toBe(4)
  })
}

test('R8: while held, another box and another section are refused and the claim stays put', async ({ page }) => {
  let w!: Awaited<ReturnType<typeof countWrites>>
  await held(page, (n) => n <= 2, async () => {
    w = await countWrites(page)
    await page.route(/\/boxes$/, (r) => r.fulfill(json({ boxes: [{ ...BOX, sections_detail: SPANS_AFTER_S }, { ...BOX, box: 6, bid: 16, name: 'Other box' }] })))
    await page.keyboard.press('s')
    await expect.poll(w.opened, { timeout: 5_000 }).toBe(1)
  })
  const slot = page.locator('.capture-section-slot .capture-row').first()
  await expect(slot).toContainText(/Section \d of 2/)
  const claim = await slot.innerText()
  await page.keyboard.press('[') // another section, either way
  await page.keyboard.press(']')
  await page.keyboard.press('[')
  await page.keyboard.press('b') // another box
  const other = page.locator('.capture-opt').filter({ hasText: /Other box/ })
  if (await other.isVisible()) await other.click({ force: true })
  await page.waitForTimeout(600) // keep: a wrongly accepted pick gets time to show
  expect(await slot.innerText()).toBe(claim) // one `]` and two `[`: any accepted step would show
  await expect(page.locator('.capture-row').filter({ hasText: /Dispenser box/ }).first()).toBeVisible()
  await expect(page.locator('.capture-row').filter({ hasText: /Other box/ })).toHaveCount(0)
  await expect(page.getByText('Retry saving first').first()).toBeVisible()
})

test('R6: while held the Capture button is disabled; after a successful Retry Capture and Start are enabled again', async ({ page }) => {
  const wire = await held(page, (n) => n <= 2)
  await expect(captureButton(page)).toBeDisabled()
  await page.getByRole('button', { name: 'Retry saving' }).click()
  await expect.poll(wire.answered, { timeout: 10_000 }).toBe(4)
  await expect(unsaved(page)).toHaveCount(0)
  await expect(captureButton(page)).toBeEnabled()
  await expect(control(page, 'Start dispenser')).toBeEnabled()
})
