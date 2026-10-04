// Protects: The Capture screen stays responsive as a sitting grows, so the shutter and the motion trigger never stall the operator at card 300.
// Governs: D10, D164
import { expect, test } from '@playwright/test'
import { sealEveryTest } from './shell'

/* A LONG SITTING MUST NOT FREEZE THE MAIN THREAD. 300 captures on a canvas camera, with a
 * `longtask` observer (the browser reports only tasks of 50 ms or more, so "no entry" is the
 * bar). 300, not 60: the owner's longest sitting is 555 cards and a cost that grows with the sitting hides at 60. Measured on the dev server before the fix: 50 to 69 ms tasks from about capture 46.
 * Camera and wire stubs follow `capture-undo.spec.ts` and `dispenser.spec.ts`; both keep theirs
 * file-local, so this one does too. Nothing reaches a store: `POST /capture` is answered here. */

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
const CAPTURES = 300

sealEveryTest()

test(`${CAPTURES} captures and an armed idle motion trigger raise no long task`, async ({ page }) => {
  test.setTimeout(900_000)
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
    const long: number[] = []
    ;(window as unknown as { __long: number[] }).__long = long
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) long.push(Math.round(entry.duration))
    }).observe({ entryTypes: ['longtask'] })
  })
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
  /* REAL-SIZE PHOTOS, so image decode is in the measurement. The capture camera saves 1920x1080;
     each index gets its own JPEG (a varied block and pixel) so the browser cannot share one
     decode. Made once, in a scratch page, so the encode never lands in the page under test. */
  const scratch = await page.context().newPage()
  const photos = await scratch.evaluate((count) => {
    const canvas = document.createElement('canvas')
    canvas.width = 1920
    canvas.height = 1080
    const c = canvas.getContext('2d')
    if (c === null) throw new Error('no 2d context')
    const out: string[] = []
    for (let i = 1; i <= count; i += 1) {
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
  }, CAPTURES)
  await scratch.close()
  await page.route(/\/photo\/\d+\/\d+/, (r) => {
    const at = Number(/\/photo\/\d+\/(\d+)/.exec(r.request().url())?.[1] ?? 1)
    return r.fulfill({ status: 200, contentType: 'image/jpeg', body: Buffer.from(photos[(at - 1) % CAPTURES] ?? '', 'base64') })
  })

  await page.goto('/#/capture')
  await expect(page.locator('.capture-row').filter({ hasText: /Finish/ })).toBeVisible()
  // Pressed until it lands: the key listener is a passive effect that can follow the paint.
  await expect(async () => {
    await page.keyboard.press('b')
    await expect(page.locator('.capture-opt').filter({ hasText: /Freeze test/ })).toBeVisible({ timeout: 1_000 })
  }).toPass({ timeout: 15_000 })
  await page.keyboard.type('5')
  await page.keyboard.press('Enter')
  await page.keyboard.press('v')
  await page.getByLabel('Rig').getByRole('button', { name: 'Connect' }).click()
  await page.locator('.capture-opt').filter({ hasText: /Canvas Cam Link/ }).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'Capture', exact: true })).toBeEnabled()

  const longTasks = () => page.evaluate(() => (window as unknown as { __long: number[] }).__long.slice())
  const clear = () => page.evaluate(() => { (window as unknown as { __long: number[] }).__long.length = 0 })
  const perCapture: number[][] = []
  for (let n = 1; n <= CAPTURES; n += 1) {
    await clear()
    await page.keyboard.press('c')
    await expect(page.locator('.capture-undo-row').first()).toHaveAttribute('aria-label', new RegExp(`Card ${n}$`))
    await page.waitForTimeout(400) // keep: 400 ms render settle window
    perCapture.push(await longTasks())
  }
  const summary = perCapture.map((tasks, i) => (tasks.length > 0 ? `#${i + 1}:${tasks.join('+')}` : '')).filter(Boolean).slice(-12).join(' ')
  expect(perCapture.slice(-10).flat(), `long tasks (ms) over the last 10 of ${CAPTURES} captures; last flagged: ${summary || 'none'}`).toEqual([])

  // Motion armed and idle at 300 cards: the trigger's own loop must not stall the thread.
  const rig = page.locator('.capture-rig-summary')
  if ((await rig.getAttribute('aria-expanded')) === 'false') await rig.click()
  await page.getByRole('button', { name: /Trigger/ }).click()
  await page.getByRole('button', { name: 'motion', exact: true }).click()
  await expect(page.locator('.capture-trigger')).toHaveAttribute('data-trigger', 'motion')
  await page.keyboard.press('Escape')
  await clear()
  await page.waitForTimeout(4_000) // keep: 4 s idle observation window
  expect(await longTasks(), 'long tasks (ms) over 4 s armed and idle at 300 cards').toEqual([])
})
