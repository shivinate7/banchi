// Protects: The dispenser control sits under the shutter, gives its reason when it cannot deal, and stops dealing the moment a fire is dropped.
// Governs: D316, D19, D313
import { expect, test } from '@playwright/test'
import { sealEveryTest } from './shell'
import type { Page } from '@playwright/test'

/* THE DISPENSER'S BROWSER HALF, in a real browser against the real capture screen. The unit tier
 * (`unit/dispenser.unit.ts`) holds the loop against tcg-dealer's recorded sequences; this file
 * proves the wiring: the control, its reasons, and the one gate that matters, that dealing stops
 * when a fire is dropped. `navigator.bluetooth` is a fake, installed by an init script, that
 * answers every START with COMPLETE after 420 ms and records every write on `window.__writes`.
 *
 * NO BOX IS EVER SELECTED, like `motion-live.spec.ts`: the first fire is dropped, and that drop
 * must stop dealing. The camera is a canvas stream into the screen's own video element. */

const SERVICE = '7e8a1e10-1234-4bcd-8aef-1234567890ab'
const GAP_LUMA = 20
const CARD = 170

sealEveryTest({ store: true })

async function fakeBluetooth(page: Page): Promise<void> {
  await page.addInitScript((service) => {
    const w = window as unknown as { __writes: string[]; __chooser: number }
    w.__writes = []
    w.__chooser = 0
    const listeners: Array<(e: unknown) => void> = []
    const write = async (data: BufferSource) => {
      const bytes = ArrayBuffer.isView(data) ? new Uint8Array(data.buffer, data.byteOffset, data.byteLength) : new Uint8Array(data)
      const text = new TextDecoder().decode(bytes)
      w.__writes.push(text)
      if (text === 'MOTOR:START') {
        setTimeout(() => { // keep: recorded dealer COMPLETE delay
          const value = new DataView(new TextEncoder().encode('MOTOR:COMPLETE').buffer)
          for (const fn of listeners) fn({ target: { value } })
        }, 420)
      }
    }
    const characteristic = (): Record<string, unknown> => {
      const self: Record<string, unknown> = {
        writeValue: write,
        writeValueWithResponse: write,
        writeValueWithoutResponse: write,
        startNotifications: async () => self,
        addEventListener: (name: string, fn: (e: unknown) => void) => {
          if (name === 'characteristicvaluechanged') listeners.push(fn)
        },
        removeEventListener: () => {},
      }
      return self
    }
    const server = {
      connected: true,
      connect: async () => server,
      disconnect: () => {},
      getPrimaryService: async (uuid: string) => {
        if (uuid !== service) throw new Error('no such service')
        return { getCharacteristic: async () => characteristic() }
      },
    }
    const device = { name: 'ESP_OTA_GATTS', gatt: server, addEventListener: () => {}, removeEventListener: () => {} }
    /* A READY CAMERA THE WAY THE PRODUCT READS IT: a canvas stream behind getUserMedia, one device
       in enumerateDevices, as capture-section.spec.ts does. No product gate is touched. */
    const canvas = document.createElement('canvas')
    canvas.width = 640
    canvas.height = 360
    const context = canvas.getContext('2d')
    if (context !== null) {
      context.fillStyle = 'rgb(20,20,20)'
      context.fillRect(0, 0, 640, 360)
      // a canvas stream delivers frames only when something is drawn, and metadata needs a frame
      let tick = 0
      setInterval(() => {
        tick += 1
        context.fillStyle = `rgb(${20 + (tick % 2)},20,20)`
        context.fillRect(0, 0, 640, 360)
      }, 33)
    }
    const stream = canvas.captureStream(30)
    const media = navigator.mediaDevices as unknown as {
      enumerateDevices: () => Promise<unknown[]>
      getUserMedia: () => Promise<MediaStream>
    }
    media.enumerateDevices = async () => [{ deviceId: 'canvas', kind: 'videoinput', label: 'Canvas Cam Link', groupId: 'g' }]
    media.getUserMedia = async () => stream
    Object.defineProperty(navigator, 'bluetooth', {
      configurable: true,
      value: {
        requestDevice: async () => {
          w.__chooser += 1
          return device
        },
      },
    })
  }, SERVICE)
}

async function writes(page: Page): Promise<string[]> {
  return page.evaluate(() => (window as unknown as { __writes: string[] }).__writes)
}

const control = (page: Page, name: string) => page.getByRole('button', { name, exact: true })

async function armMotion(page: Page): Promise<void> {
  // picking a box folds the Rig group; open it again when it is shut
  const rig = page.getByRole('region', { name: 'Rig' }).getByRole('button', { name: /^Rig/ })
  if ((await rig.getAttribute('aria-expanded')) === 'false') await rig.click()
  await page.getByRole('button', { name: /Trigger/ }).click()
  await page.getByRole('button', { name: 'motion', exact: true }).click()
  await expect(page.locator('.capture-trigger')).toHaveAttribute('data-trigger', 'motion')
}

async function injectScene(page: Page): Promise<void> {
  await page.evaluate((first) => {
    const video = document.querySelector<HTMLVideoElement>('.capture-media')
    if (video === null) throw new Error('no video element on the capture screen')
    const canvas = document.createElement('canvas')
    canvas.width = 640
    canvas.height = 360
    const context = canvas.getContext('2d')
    if (context === null) throw new Error('no 2d context')
    const scene = { base: first }
    const draw = () => {
      context.fillStyle = `rgb(${scene.base},${scene.base},${scene.base})`
      context.fillRect(0, 0, 640, 360)
      if (scene.base !== first) {
        for (let y = 0; y < 360; y += 40) {
          const up = Math.min(255, scene.base + 40)
          const down = Math.max(0, scene.base - 40)
          context.fillStyle = `rgb(${up},${up},${up})`
          context.fillRect(0, y, 640, 20)
          context.fillStyle = `rgb(${down},${down},${down})`
          context.fillRect(0, y + 20, 640, 20)
        }
      }
      window.requestAnimationFrame(draw)
    }
    draw()
    ;(window as unknown as { __scene: typeof scene }).__scene = scene
    video.srcObject = canvas.captureStream(30)
    void video.play()
  }, GAP_LUMA)
}

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
