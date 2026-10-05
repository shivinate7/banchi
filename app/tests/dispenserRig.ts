import { expect } from '@playwright/test'
import type { Page } from '@playwright/test'

/* THE DISPENSER'S BROWSER RIG, shared by `dispenser.spec.ts` and `capture-freeze.spec.ts`:
 * a fake `navigator.bluetooth` that answers every START with COMPLETE after 420 ms and records
 * every write on `window.__writes`, a canvas camera, motion armed from the Trigger group, and a
 * scene canvas the test drives to put a card in front of the lens. No product gate is touched. */

const SERVICE = '7e8a1e10-1234-4bcd-8aef-1234567890ab'
export const GAP_LUMA = 20
export const CARD = 170

export async function fakeBluetooth(page: Page): Promise<void> {
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

/** `POST /capture` answers a real capture, but only after `ms`: a slow save. `posts` counts every POST
 *  that reached the wire, answered or not. Nothing reaches the real store. */
export async function slowCapture(page: Page, ms: number): Promise<{ posts: () => number; answered: () => number }> {
  let posts = 0
  let answered = 0
  await page.route(/\/capture$/, (route) => {
    posts += 1
    const index = posts
    setTimeout(() => { // keep: the slow save held
      answered += 1
      void route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          box: 5, index, key: `5/${index}`, label: `Box 5, Card ${index}`, section: 1, card: index, section_div: '1',
          new_box: false, created: true, photo: `/tmp/5-${index}.jpg`, capture_id: null,
          place: { box_total: index, located: true, label: `Box 5, Card ${index}` },
        }),
      })
    }, ms)
  })
  return { posts: () => posts, answered: () => answered }
}

export async function writes(page: Page): Promise<string[]> {
  return page.evaluate(() => (window as unknown as { __writes: string[] }).__writes)
}

export const control = (page: Page, name: string) => page.getByRole('button', { name, exact: true })

export async function armMotion(page: Page): Promise<void> {
  // picking a box folds the Rig group, a moment after the pick; open it again whenever it is shut
  const rig = page.getByRole('region', { name: 'Rig' }).getByRole('button', { name: /^Rig/ })
  const trigger = page.getByRole('button', { name: /Trigger/ })
  await expect(async () => {
    if (!(await trigger.isVisible())) await rig.click()
    await expect(trigger).toBeVisible({ timeout: 1_000 })
  }).toPass({ timeout: 15_000 })
  await trigger.click()
  await page.getByRole('button', { name: 'motion', exact: true }).click()
  await expect(page.locator('.capture-trigger')).toHaveAttribute('data-trigger', 'motion')
}

export async function injectScene(page: Page): Promise<void> {
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
