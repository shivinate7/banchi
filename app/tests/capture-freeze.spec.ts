// Protects: The Capture screen stays responsive as a sitting grows: while the dispenser deals, the Recent rail pauses and the Last capture panel stays live, and a hand-fed sitting never stalls.
// Governs: D10, D164, D313, D316
import { expect, test } from '@playwright/test'
import { sealEveryTest } from './shell'
import { CARD, GAP_LUMA, armMotion, control, fakeBluetooth, injectScene, writes } from './dispenserRig'
import type { Page } from '@playwright/test'

/* A LONG SITTING MUST NOT FREEZE THE MAIN THREAD. A `longtask` observer reports only tasks of
 * 50 ms or more, so "no entry" is the bar. Two cases:
 *  1. DEALING, 300 captures (the owner's longest sitting is 555 cards, and a cost that grows with
 *     the sitting hides at 60): the rail (`footer.capture-undo`) stays live but draws only the
 *     newest DEALING_TILES tiles, first tile the latest card, the Last capture panel (`aside.capture-last`) shows each new
 *     photo, no task over 50 ms in the last 10 captures, and after Stop the rail catches up to all
 *     300. That one catch-up render may be long and is not barred.
 *  2. HAND FEED, 60 captures with the shutter: the old bar, so hand feeding cannot regress.
 * Photos are distinct 1920x1080 JPEGs, so image decode is in the measurement. The dealer is the
 * fake Bluetooth device of `dispenser.spec.ts` (shared in `dispenserRig.ts`). Nothing reaches a
 * store: `POST /capture` is answered here. */

const GAME = {
  key: 'pokemon', display: 'Pokémon', product_line: 'Pokemon', rarities: ['Common', 'Uncommon', 'Rare'],
  finishes: ['normal', 'holo', 'reverse_holo'],
  condition_by_finish: { normal: 'Near Mint', holo: 'Near Mint Holofoil', reverse_holo: 'Near Mint Reverse Holofoil' },
  finish_by_rarity: { Common: ['normal'], Uncommon: ['normal', 'reverse_holo'], Rare: ['normal', 'holo', 'reverse_holo'] },
  located: true, join_key: 'number_over_printed_total', prompt: 'pokemon', crop_bands: ['title', 'number'],
  card_aspect: 0.716, unverified: false, catalogued: true,
}
const BOX = {
  box: 5, bid: 15, name: 'Freeze test', sections: [1], state: 'open', capacity: null, fill: 0, next_index: 1,
  cards: 0, sold: 0, retired: 0, listed: 0, on_hand: 0,
  sections_detail: [{ section: 1, start: 1, end: null, count: 0, name: null, div: '1' }], layout_token: 'tok1',
}
const json = (body: unknown, status = 200) => ({ status, contentType: 'application/json', body: JSON.stringify(body) })

sealEveryTest()

/** The long-task observer, installed before the app runs. */
async function observeLongTasks(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const long: number[] = []
    ;(window as unknown as { __long: number[] }).__long = long
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) long.push(Math.round(entry.duration))
    }).observe({ entryTypes: ['longtask'] })
  })
}
const longTasks = (page: Page) => page.evaluate(() => (window as unknown as { __long: number[] }).__long.slice())
const clearLong = (page: Page) => page.evaluate(() => { (window as unknown as { __long: number[] }).__long.length = 0 })

/** The wire, and one distinct real-size JPEG per photo index, made once in a scratch page so the
 *  encode never lands in the page under test. */
async function stubWire(page: Page, count: number): Promise<void> {
  const scratch = await page.context().newPage()
  const photos = await scratch.evaluate((n) => {
    const canvas = document.createElement('canvas')
    canvas.width = 1920
    canvas.height = 1080
    const c = canvas.getContext('2d')
    if (c === null) throw new Error('no 2d context')
    const out: string[] = []
    for (let i = 1; i <= n; i += 1) {
      const g = c.createLinearGradient(0, 0, 1920, 1080)
      g.addColorStop(0, `hsl(${(i * 37) % 360},60%,45%)`)
      g.addColorStop(1, `hsl(${(i * 91) % 360},50%,25%)`)
      c.fillStyle = g
      c.fillRect(0, 0, 1920, 1080)
      for (let k = 0; k < 40; k += 1) {
        c.fillStyle = `rgb(${(i * 7 + k * 31) % 256},${(i * 13 + k * 17) % 256},${(i * 29 + k * 5) % 256})`
        c.fillRect((k * 97 + i * 11) % 1800, (k * 53 + i * 7) % 1000, 120, 80)
      }
      out.push(canvas.toDataURL('image/jpeg', 0.9).split(',')[1] ?? '')
    }
    return out
  }, count)
  await scratch.close()
  await page.route(/\/games$/, (r) => r.fulfill(json({ default: 'pokemon', products: [], product_game: 'pokemon_code', games: [GAME] })))
  await page.route(/\/status$/, (r) => r.fulfill(json({ cards: 0, next_index: { '5': 1 } })))
  await page.route(/\/boxes$/, (r) => r.fulfill(json({ boxes: [BOX] })))
  await page.route(/\/pipeline\/match\/sweep$/, (r) => r.fulfill(json({ on: false, running: false, matched: 0 })))
  await page.route(/\/capture\/sitting$/, (r) => r.fulfill(json({ open: true, gap_minutes: 30, cards: [] })))
  let next = 1
  await page.route(/\/capture$/, (r) => {
    const index = next++
    return r.fulfill(json({
      box: 5, index, key: `5/${index}`, label: `Box 5, Card ${index}`, section: 1, card: index, section_div: '1',
      new_box: false, created: true, photo: `/tmp/5-${index}.jpg`, capture_id: null,
      place: { box_total: index, located: true, label: `Box 5, Card ${index}` },
    }, 201))
  })
  await page.route(/\/photo\/\d+\/\d+/, (r) => {
    const at = Number(/\/photo\/\d+\/(\d+)/.exec(r.request().url())?.[1] ?? 1)
    return r.fulfill({ status: 200, contentType: 'image/jpeg', body: Buffer.from(photos[(at - 1) % count] ?? '', 'base64') })
  })
}

/** Camera chosen on the rig, then the box. Pressed until it lands: the key listener is a passive
 *  effect that can follow the paint. */
async function pickCameraAndBox(page: Page): Promise<void> {
  await page.goto('/#/capture')
  await expect(page.locator('.capture-row').filter({ hasText: /Finish/ })).toBeVisible()
  await page.keyboard.press('v')
  await page.getByLabel('Rig').getByRole('button', { name: 'Connect' }).click()
  await page.locator('.capture-opt').filter({ hasText: /Canvas Cam Link/ }).click()
  await page.keyboard.press('Escape')
  await expect(async () => {
    await page.keyboard.press('b')
    await expect(page.locator('.capture-opt').filter({ hasText: /Freeze test/ })).toBeVisible({ timeout: 1_000 })
  }).toPass({ timeout: 15_000 })
  await page.keyboard.type('5')
  await page.keyboard.press('Enter')
}

/* The rail's cap while dealing. the product's own export is not there yet; replace this
 * with an import of it (CaptureScreen.tsx or dealer.ts) once the builder lands it. */
const DEALING_TILES = 15
const rail = (page: Page) => page.locator('footer.capture-undo')
const tiles = (page: Page) => rail(page).locator('.capture-undo-row')
const lastPanel = (page: Page) => page.locator('aside.capture-last')

test('300 captures while the dispenser deals: no long task, the rail paused, the last capture live', async ({ page }) => {
  const CAPTURES = 300
  test.setTimeout(1_500_000)
  await observeLongTasks(page)
  await fakeBluetooth(page)
  await stubWire(page, CAPTURES)
  await pickCameraAndBox(page)
  await armMotion(page)
  await injectScene(page)
  await expect(page.locator('.capture-motion-hud')).toBeAttached({ timeout: 5_000 })
  await control(page, 'Connect dispenser').click()
  const start = control(page, 'Start dispenser')
  await expect(start).toBeEnabled({ timeout: 5_000 })
  await start.click()
  await expect(control(page, 'Stop dispenser')).toBeVisible()

  const setScene = (base: number) =>
    page.evaluate((b) => { (window as unknown as { __scene: { base: number } }).__scene.base = b }, base)
  const starts = async () => (await writes(page)).filter((w) => w === 'MOTOR:START').length
  const emptyStands = async () => {
    const spans = await page.locator('.capture-motion-hud span').allTextContents()
    return Number(spans.map((t) => /^empty\s+(\d+)$/.exec(t.trim())?.[1]).find((v) => v !== undefined) ?? 0)
  }
  let gaps = 0
  const perCapture: number[][] = []
  let railMoved = ''
  for (let n = 1; n <= CAPTURES; n += 1) {
    await expect.poll(starts, { timeout: 15_000 }).toBeGreaterThanOrEqual(n)
    await clearLong(page)
    // the machine fires on a card only after it has settled on the empty stand, so wait on its own count
    await expect.poll(emptyStands, { timeout: 15_000 }).toBeGreaterThan(gaps)
    gaps = await emptyStands()
    await setScene(n % 2 === 1 ? CARD : CARD - 50) // the card lands in front of the lens; each differs from the last fired
    const img = lastPanel(page).locator('img.capture-media')
    await expect(img).toHaveAttribute('alt', `Capture at Box 5, Card ${n}`, { timeout: 15_000 })
    await setScene(GAP_LUMA)
    await expect.poll(() => img.evaluate((el) => (el as HTMLImageElement).naturalWidth), { timeout: 15_000 }).toBe(1920)
    perCapture.push(await longTasks(page))
    const count = await tiles(page).count()
    const top = (await tiles(page).first().getAttribute('aria-label')) ?? ''
    if (railMoved === '' && (count !== Math.min(n, DEALING_TILES) || !top.endsWith(`Card ${n}`)))
      railMoved = `at capture ${n} the rail shows ${count} tiles, first "${top}"; want ${Math.min(n, DEALING_TILES)}, first Card ${n}`
  }
  const summary = perCapture.map((tasks, i) => (tasks.length > 0 ? `#${i + 1}:${tasks.join('+')}` : '')).filter(Boolean).slice(-12).join(' ')
  const last10 = perCapture.slice(-10).flat()

  await setScene(GAP_LUMA)
  await control(page, 'Stop dispenser').click()
  await expect(control(page, 'Start dispenser')).toBeVisible({ timeout: 10_000 })
  // the catch-up render may be long and is not barred
  await expect(tiles(page)).toHaveCount(CAPTURES, { timeout: 30_000 })

  expect.soft(railMoved, 'while dealing the rail shows exactly the newest tiles, newest first').toBe('')
  expect(last10, `long tasks (ms) over the last 10 of ${CAPTURES} dealt captures; last flagged: ${summary || 'none'}`).toEqual([])
})

test('60 hand-fed captures raise no long task', async ({ page }) => {
  const CAPTURES = 60
  test.setTimeout(180_000)
  await observeLongTasks(page)
  await page.addInitScript(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 1920
    canvas.height = 1080
    const context = canvas.getContext('2d')
    if (context !== null) {
      context.fillStyle = 'rgb(180,180,180)'
      context.fillRect(0, 0, 1920, 1080)
    }
    const stream = canvas.captureStream(30)
    const media = navigator.mediaDevices as unknown as {
      enumerateDevices: () => Promise<unknown[]>
      getUserMedia: () => Promise<MediaStream>
    }
    media.enumerateDevices = async () => [{ deviceId: 'canvas', kind: 'videoinput', label: 'Canvas Cam Link', groupId: 'g' }]
    media.getUserMedia = async () => stream
  })
  await stubWire(page, CAPTURES)
  await pickCameraAndBox(page)
  await expect(page.getByRole('button', { name: 'Capture', exact: true })).toBeEnabled()
  const perCapture: number[][] = []
  for (let n = 1; n <= CAPTURES; n += 1) {
    await clearLong(page)
    await page.keyboard.press('c')
    await expect(page.locator('.capture-undo-row').first()).toHaveAttribute('aria-label', new RegExp(`Card ${n}$`))
    await page.waitForTimeout(400) // keep: 400 ms render settle window
    perCapture.push(await longTasks(page))
  }
  const summary = perCapture.map((tasks, i) => (tasks.length > 0 ? `#${i + 1}:${tasks.join('+')}` : '')).filter(Boolean).slice(-12).join(' ')
  expect(perCapture.slice(-3).flat(), `long tasks (ms) around capture ${CAPTURES}; last flagged: ${summary || 'none'}`).toEqual([])
})
