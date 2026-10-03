// Protects: The dispenser control sits under the shutter, gives its reason when it cannot deal, and stops dealing the moment a fire is dropped.
// Governs: D-dispenser-button, D19, D313
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
    delete (navigator as unknown as { bluetooth?: unknown }).bluetooth
  })
  await page.goto('/#/capture')
  await expect(page.locator('.capture-controls').getByText('Needs Chrome on the Mac')).toBeVisible()
  await expect(control(page, 'Connect dispenser')).toBeDisabled()
})

test('armed and connected, a fire with no box is dropped and dealing stops with the not-photographed line', async ({ page }) => {
  await fakeBluetooth(page)
  await page.goto('/#/capture')
  await armMotion(page)
  await injectScene(page)
  await expect(page.locator('.capture-motion-hud')).toBeAttached({ timeout: 5_000 })
  await control(page, 'Connect dispenser').click()
  await expect(page.locator('.capture-controls').getByText('Connected', { exact: true })).toBeVisible()
  const start = control(page, 'Start dispenser')
  await expect(start).toBeEnabled({ timeout: 5_000 })
  await start.click()
  await expect(control(page, 'Stop dispenser')).toBeVisible()
  expect((await writes(page))[0]).toBe('MOTOR:START')

  // the card lands in front of the lens: motion fires, no box is picked, the fire is dropped
  await page.evaluate((base) => {
    ;(window as unknown as { __scene: { base: number } }).__scene.base = base
  }, CARD)
  await expect(
    page.locator('.capture-controls').getByText('Stopped: a card was not photographed. Resume captures first.'),
  ).toBeVisible({ timeout: 8_000 })
  await expect(control(page, 'Start dispenser')).toBeVisible()

  // the last write is STOP, and nothing is sent after it
  const sent = await writes(page)
  expect(sent.at(-1)).toBe('MOTOR:STOP')
  await page.waitForTimeout(1_500) // keep: quiet window proving nothing follows STOP
  expect(await writes(page)).toEqual(sent)
  for (const w of sent) expect(['MOTOR:START', 'MOTOR:STOP']).toContain(w)
})
