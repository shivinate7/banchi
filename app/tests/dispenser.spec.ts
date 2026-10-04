// Protects: The dispenser control sits under the shutter, gives its reason when it cannot deal, and stops dealing the moment a fire is dropped.
// Governs: D316, D19, D313
import { expect, test } from '@playwright/test'
import { sealEveryTest } from './shell'
import type { Page } from '@playwright/test'
import { CARD, armMotion, control, fakeBluetooth, injectScene, writes } from './dispenserRig'

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
