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
async function ready(page: Page, withBox: boolean): Promise<void> {
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
  await expect(
    page.locator('.capture-controls').getByText(/Stopped: a card was not photographed|Resume captures first/),
  ).toBeVisible()

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
async function held(page: Page, failIf: (post: number) => boolean) {
  await ready(page, true)
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

test('R3: while a photo is held, Capture sends no POST and the held frame survives, before and after Resume', async ({ page }) => {
  const wire = await held(page, (n) => n <= 2)
  const posts = wire.posts()
  await captureButton(page).click({ force: true })
  await page.waitForTimeout(800) // keep: a wrongly sent POST gets time to land
  expect(wire.posts()).toBe(posts)
  const resume = page.getByRole('button', { name: /^Resume captures/ })
  if (await resume.isVisible()) await resume.click()
  await captureButton(page).click({ force: true })
  const start = control(page, 'Start dispenser')
  if (await start.isEnabled()) await start.click() // the dispenser may not deal while a photo is held
  await page.waitForTimeout(1_200) // keep: a wrongly sent POST or START gets time to land
  expect(wire.posts()).toBe(posts)
  expect((await writes(page)).filter((w) => w === 'MOTOR:START')).toHaveLength(2)
  // both frames are still there, and Retry saving sends them in order
  await expect(unsaved(page)).toBeVisible()
  await page.getByRole('button', { name: 'Retry saving' }).click()
  await expect.poll(wire.answered, { timeout: 10_000 }).toBe(4)
  expect(wire.events().slice(4)).toEqual(['sent:3', 'answered:3', 'sent:4', 'answered:4'])
})

test('R4: the not-saved notice says what was sent and what to press, with no mechanism word', async ({ page }) => {
  await held(page, (n) => n <= 2)
  const notice = unsaved(page)
  await expect(notice).toContainText(/Box 5, Card 1 was not saved/)
  await expect(notice).toContainText(/Nothing after it was sent/)
  await expect(notice).toContainText(/Retry saving/)
  await expect(notice).not.toContainText(/held here/i)
})
