// Protects: The Capture screen stays responsive as a sitting grows: while the dispenser deals, the Recent rail pauses and the Last capture panel stays live, and a hand-fed sitting never stalls.
// Governs: D10, D164, D313, D316
import { expect, test } from '@playwright/test'
import { sealEveryTest, settleAnimations } from './shell'
import { CARD, GAP_LUMA, armMotion, control, fakeBluetooth, injectScene, writes } from './dispenserRig'
import type { CDPSession, Page } from '@playwright/test'
import { setViewport } from './phoneSwitch'
import { DEALING_RAIL_TILES, SAVE_WAIT_MS } from '../src/dealer'

/* A LONG SITTING MUST NOT FREEZE THE MAIN THREAD. A `longtask` observer reports only tasks of
 * 50 ms or more, so "no entry" is the bar. Three cases:
 *  1. DEALING, 50 captures, on PRs that change Capture code, and nightly: the rail (`footer.capture-undo`) stays live but draws only
 *     the newest DEALING_RAIL_TILES tiles, first tile the latest card, the Last capture panel
 *     (`aside.capture-last`) shows each new photo, no task over 50 ms in the last 10 captures, and
 *     after Stop the rail catches up to all of them. That one catch-up render may be long and is
 *     not barred. A cost that grows with the sitting can hide at 50. By the owner's word the
 *     per-PR run trades that for speed.
 *  2. DEALING, 300 captures, monthly and on demand (PKMNSCAN_LONG_SITTING=1): the same claims.
 *     This run is what catches growth. The owner's longest sitting is 555 cards.
 *  3. HAND FEED, 60 captures with the shutter: the old bar, so hand feeding cannot regress.
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

/** The long-task observer and a blocked-time probe, installed before the app runs, and the CPU
 *  throttled 4x over CDP so every machine measures the same regime. The probe is a 10 ms timer: how
 *  late it fires is how long the main thread was blocked, summed into `__jank`, which sees the cost
 *  that stays under the 50 ms long-task line. */
/* The CPU rate over the measured span, and over the drive around it. `FREEZE_THROTTLE=6` runs both at 6x,
 * to prove the drive does not depend on runner speed. */
const STRESS = Number(process.env.FREEZE_THROTTLE ?? 0)
const MEASURED_RATE = STRESS > 0 ? STRESS : 4
const DRIVE_RATE = STRESS > 0 ? STRESS : 1
const sessions = new WeakMap<Page, CDPSession>()
const throttle = (page: Page, rate: number) => sessions.get(page)?.send('Emulation.setCPUThrottlingRate', { rate })
async function observeLongTasks(page: Page): Promise<void> {
  const cdp = await page.context().newCDPSession(page)
  sessions.set(page, cdp)
  await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 })
  await page.addInitScript(() => {
    const long: number[] = []
    const w = window as unknown as { __long: number[]; __jank: { ms: number } }
    w.__long = long
    w.__jank = { ms: 0 }
    new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) long.push(Math.round(entry.duration))
    }).observe({ entryTypes: ['longtask'] })
    let last = performance.now()
    setInterval(() => {
      const now = performance.now()
      w.__jank.ms += Math.max(0, now - last - 10)
      last = now
    }, 10)
  })
}
const longTasks = (page: Page) => page.evaluate(() => (window as unknown as { __long: number[] }).__long.slice())
const clearLong = (page: Page) =>
  page.evaluate(() => {
    const w = window as unknown as { __long: number[]; __jank: { ms: number } }
    w.__long.length = 0
    w.__jank.ms = 0
  })
const blockedMs = (page: Page) => page.evaluate(() => Math.round((window as unknown as { __jank: { ms: number } }).__jank.ms))

/** The wire, and one distinct real-size JPEG per photo index, made once in a scratch page so the
 *  encode never lands in the page under test. */
async function stubWire(page: Page, count: number): Promise<{ undone: string[] }> {
  const undone: string[] = []
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
      out.push(canvas.toDataURL('image/jpeg', 0.9).replace(/^data:[^;]*;base64,/, ''))
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
  await page.route(/\/inventory\/\d+\/\d+(\/remove)?$/, (r) => {
    const path = new URL(r.request().url()).pathname
    undone.push(`${r.request().method()} ${path}`)
    const index = Number(/\/inventory\/\d+\/(\d+)/.exec(path)?.[1] ?? 0)
    return r.fulfill(json({
      deleted: `5/${index}`, box: 5, index, photo_deleted: true, sidecar_deleted: true, review_deleted: false,
      parked_deleted: false, cache_deleted: true, shifted: 0, next_index: index - 1, on_hand: index - 1,
    }))
  })
  await page.route(/\/photo\/\d+\/\d+/, (r) => {
    const at = Number(/\/photo\/\d+\/(\d+)/.exec(r.request().url())?.[1] ?? 1)
    return r.fulfill({ status: 200, contentType: 'image/jpeg', body: Buffer.from(photos[(at - 1) % count] ?? '', 'base64') })
  })
  return { undone }
}

/** A canvas camera at 1920x1080, for the hand-fed cases. */
async function handCamera(page: Page): Promise<void> {
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

const rail = (page: Page) => page.locator('footer.capture-undo')
const tiles = (page: Page) => rail(page).locator('.capture-undo-row')
const lastPanel = (page: Page) => page.locator('aside.capture-last')

/* THE CHECK IS A GROWTH CHECK, MEASURED IN ONE REGIME. Every case runs with the CPU throttled 4x
 * (`observeLongTasks`), so a fast Mac and a slow runner see the same slowdown and a fixed number
 * means the same thing on both. Each capture's cost is the main-thread blocked time in its window
 * (`blockedMs`); a window of captures is judged by the MEDIAN of its captures, so one noisy capture
 * cannot decide the run. The last 10 captures may cost at most `GROWTH` times the first 10 plus
 * `NOISE_MS`: a cost that grows with the sitting shows on any machine, and a constant cost passes
 * on any machine. Long tasks are reported in the message and are not the bar. */
const GROWTH = 1.4
const NOISE_MS = 30
const median = (xs: number[]) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)] ?? 0
/** Why a run fails the growth check, or '' when it holds. */
function judge(cost: number[], long: number[][], window: number, firstAt = 0): string {
  const early = median(cost.slice(firstAt, firstAt + window))
  const late = median(cost.slice(-window))
  console.log(`GROWTH median blocked ms per capture: first ${window} (from capture ${firstAt + 1}) ${early}, last ${window} ${late}`)
  if (late <= GROWTH * early + NOISE_MS) return ''
  const flagged = long.map((t, i) => (t.length > 0 ? `#${i + 1}:${t.join('+')}` : '')).filter(Boolean).slice(-12).join(' ')
  return `median blocked time per capture grew from ${early} ms (captures ${firstAt + 1} to ${firstAt + window}) to ${late} ms (the last ${window}), over ${GROWTH}x plus ${NOISE_MS} ms; last long tasks: ${flagged || 'none'}`
}

/** The dispenser connected and dealing into box 5. `dealOne(n)` waits for the machine to settle
 *  on the empty stand, lands card n in front of the lens, and resolves once the Last capture
 *  panel shows it at full size. */
async function startDealing(page: Page, count: number) {
  await observeLongTasks(page)
  await throttle(page, DRIVE_RATE)
  /* THE DEALER'S NO-PHOTO WAIT IS A WALL-CLOCK WINDOW, AND A SLOW RUNNER CAN LAND A CARD AFTER IT. These
   * cases assert the rail and its cost, not that the dealer stops when no photo comes (dispenser.spec.ts
   * and the dealer's unit tests own that), so the page's one timer of exactly `SAVE_WAIT_MS` is stretched
   * tenfold here: the drive then waits on events, never on a clock. Every other timer is untouched. */
  await page.addInitScript((save) => {
    const real = window.setTimeout.bind(window) as (fn: TimerHandler, ms?: number, ...args: unknown[]) => number
    window.setTimeout = ((fn: TimerHandler, ms?: number, ...args: unknown[]) =>
      real(fn, ms === save ? save * 10 : ms, ...args)) as typeof window.setTimeout
  }, SAVE_WAIT_MS)
  await fakeBluetooth(page)
  const wire = await stubWire(page, count)
  await pickCameraAndBox(page)
  await expect(page.getByRole('button', { name: 'Capture', exact: true })).toBeEnabled()
  await settleAnimations(page)
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
  let cost = 0
  let longs: number[] = []
  /* THE DEALER'S CLOCK DOES NOT THROTTLE. It stops with "no photo" if a card's save has not come
   * `SAVE_WAIT_MS` after COMPLETE, so the drive (waiting for START and for the machine's empty-stand
   * settle) runs at full speed, and only the span from the card landing to its photo on screen runs at
   * 4x, which is the span the cost is measured over. A slow runner that took its settle under the
   * throttle landed the card after the dealer had given up, and the second START never came. */
  const dealOne = async (n: number) => {
    await expect.poll(starts, { timeout: 15_000 }).toBeGreaterThanOrEqual(n)
    // the machine fires on a card only after it has settled on the empty stand, so wait on its own count
    await expect.poll(emptyStands, { timeout: 15_000 }).toBeGreaterThan(gaps)
    gaps = await emptyStands()
    await clearLong(page)
    await throttle(page, MEASURED_RATE)
    await setScene(n % 2 === 1 ? CARD : CARD - 50) // the card lands in front of the lens; each differs from the last fired
    const img = lastPanel(page).locator('img.capture-media')
    await expect(img).toHaveAttribute('alt', `Capture at Box 5, Card ${n}`, { timeout: 15_000 })
    await setScene(GAP_LUMA)
    await expect.poll(() => img.evaluate((el) => (el as HTMLImageElement).naturalWidth), { timeout: 15_000 }).toBe(1920)
    cost = await blockedMs(page)
    longs = await longTasks(page)
    await throttle(page, DRIVE_RATE)
  }
  const stop = async () => {
    await setScene(GAP_LUMA)
    await control(page, 'Stop dispenser').click()
    await expect(control(page, 'Start dispenser')).toBeVisible({ timeout: 10_000 })
  }
  return { wire, dealOne, stop, measured: () => ({ cost, longs }) }
}

async function dealing(page: Page, CAPTURES: number): Promise<void> {
  const { dealOne, stop, measured } = await startDealing(page, CAPTURES)
  const perCapture: number[][] = []
  const cost: number[] = []
  let railMoved = ''
  for (let n = 1; n <= CAPTURES; n += 1) {
    await dealOne(n)
    perCapture.push(measured().longs)
    cost.push(measured().cost)
    const count = await tiles(page).count()
    const top = (await tiles(page).first().getAttribute('aria-label')) ?? ''
    if (railMoved === '' && (count !== Math.min(n, DEALING_RAIL_TILES) || !top.endsWith(`Card ${n}`)))
      railMoved = `at capture ${n} the rail shows ${count} tiles, first "${top}"; want ${Math.min(n, DEALING_RAIL_TILES)}, first Card ${n}`
  }
  const verdict = judge(cost, perCapture, 10)

  await stop()
  // the catch-up render may be long and is not barred
  await expect(tiles(page)).toHaveCount(CAPTURES, { timeout: 30_000 })

  expect.soft(railMoved, 'while dealing the rail shows exactly the newest tiles, newest first').toBe('')
  expect(verdict, `blocked time over ${CAPTURES} dealt captures`).toBe('')
}

test('50 captures while the dispenser deals: the rail paused, the last capture live, no long task late', async ({ page }) => {
  test.setTimeout(180_000)
  await dealing(page, 50)
})

// Runs monthly and on demand: PKMNSCAN_LONG_SITTING=1. About 16 minutes.
test('300 captures while the dispenser deals: no growth in cost, the rail paused, the last capture live', async ({ page }) => {
  test.skip(process.env.PKMNSCAN_LONG_SITTING !== '1', 'runs monthly or on demand: set PKMNSCAN_LONG_SITTING=1')
  test.setTimeout(1_500_000)
  await dealing(page, 300)
})

test('hand-fed, captures 51 to 60 cost no more than captures 21 to 30', async ({ page }) => {
  const CAPTURES = 60
  test.setTimeout(300_000)
  await observeLongTasks(page)
  await handCamera(page)
  await stubWire(page, CAPTURES)
  await pickCameraAndBox(page)
  await expect(page.getByRole('button', { name: 'Capture', exact: true })).toBeEnabled()
  const perCapture: number[][] = []
  const cost: number[] = []
  for (let n = 1; n <= CAPTURES; n += 1) {
    await clearLong(page)
    await page.keyboard.press('c')
    await expect(page.locator('.capture-undo-row').first()).toHaveAttribute('aria-label', new RegExp(`Card ${n}$`), { timeout: 15_000 })
    await page.waitForTimeout(400) // keep: 400 ms render settle window
    perCapture.push(await longTasks(page))
    cost.push(await blockedMs(page))
  }
  /* The window starts at capture 21: the visible tile area fills up over the first ~20 captures, which is
   * a fixed cost that saturates, not growth. */
  expect(judge(cost, perCapture, 10, 20), `blocked time over ${CAPTURES} hand-fed captures`).toBe('')
})

test('a tile press undoes exactly the depth its label shows, even from a handler painted before more captures landed', async ({ page }) => {
  /* WHY THE OLD RACE IS GONE. A tile no longer carries its rank: the press reads its depth from the
   * tile's place in the live list, and a layout effect rewrites every label before paint on each
   * capture. So a handler painted as "Undo 3" cannot undo 5: it is called here after two more
   * captures landed, and must undo the depth the label shows at that moment, never the old one. */
  await observeLongTasks(page)
  await handCamera(page)
  const wire = await stubWire(page, 8)
  await pickCameraAndBox(page)
  await expect(page.getByRole('button', { name: 'Capture', exact: true })).toBeEnabled()
  const shoot = async (n: number) => {
    await page.keyboard.press('c')
    await expect(tiles(page).first()).toHaveAttribute('aria-label', new RegExp(`Card ${n}$`), { timeout: 15_000 })
  }
  for (const n of [1, 2, 3]) await shoot(n)
  // Hold the press handler of the Card 1 tile as it was painted (labelled "Undo 3 captures").
  await page.evaluate(() => {
    const row = [...document.querySelectorAll('footer.capture-undo .capture-undo-row')].at(-1) as HTMLElement
    const key = Object.keys(row).find((k) => k.startsWith('__reactProps$'))
    const props = key === undefined ? undefined : (row as unknown as Record<string, { onClick?: (e: unknown) => void }>)[key]
    if (props?.onClick === undefined) throw new Error('no React press handler on the oldest tile')
    ;(window as unknown as { __stale: (e: unknown) => void }).__stale = props.onClick
  })
  await expect(tiles(page).last()).toHaveAttribute('aria-label', /^Undo 3 captures, back to .*Card 1$/)
  for (const n of [4, 5]) await shoot(n)
  // U still undoes the newest, alone.
  await page.keyboard.press('u')
  await expect(tiles(page)).toHaveCount(4)
  expect(wire.undone).toEqual(['DELETE /inventory/5/5'])
  // The label of the oldest tile has already moved on to its live depth: 4, not 3.
  const label = (await tiles(page).last().getAttribute('aria-label')) ?? ''
  expect(label).toMatch(/^Undo 4 captures, back to .*Card 1$/)
  // The stale handler is pressed now: it must undo the four cards the label names, newest first.
  await page.evaluate(() => {
    const row = [...document.querySelectorAll('footer.capture-undo .capture-undo-row')].at(-1) as HTMLElement
    ;(window as unknown as { __stale: (e: unknown) => void }).__stale({ currentTarget: row })
  })
  await expect(tiles(page)).toHaveCount(0)
  expect(wire.undone, 'the press undid the depth its label showed, not the depth it was painted with').toEqual([
    'DELETE /inventory/5/5', 'DELETE /inventory/5/4', 'DELETE /inventory/5/3', 'DELETE /inventory/5/2', 'DELETE /inventory/5/1',
  ])
  await expect(page.locator('.bn-toast', { hasText: 'New cards arrived' })).toHaveCount(0)
})

test('past 15 cards the rail keeps its height across Stop and nothing below it moves', async ({ page }) => {
  const CARDS = DEALING_RAIL_TILES + 5
  test.setTimeout(300_000)
  const { dealOne, stop } = await startDealing(page, CARDS)
  for (let n = 1; n <= CARDS; n += 1) await dealOne(n)
  const geometry = () =>
    page.evaluate(() => {
      const footer = document.querySelector('footer.capture-undo') as HTMLElement
      const list = footer.querySelector('.capture-undo-list') as HTMLElement
      const below = [...document.querySelectorAll('footer.capture-undo ~ *')].map((el) => Math.round(el.getBoundingClientRect().top))
      return { list: Math.round(list.getBoundingClientRect().height), footerTop: Math.round(footer.getBoundingClientRect().top), below }
    })
  await expect(page.locator('footer.capture-undo .capture-undo-spacer').first()).toBeAttached()
  const dealing = await geometry()
  await stop()
  await expect(tiles(page)).toHaveCount(CARDS, { timeout: 30_000 })
  await expect(page.locator('footer.capture-undo .capture-undo-spacer')).toHaveCount(0)
  const stopped = await geometry()
  expect(stopped.list, 'the rail list holds its height across Stop').toBe(dealing.list)
  expect(stopped.footerTop, 'the rail does not move').toBe(dealing.footerTop)
  expect(stopped.below, 'nothing below the rail moves').toEqual(dealing.below)
})

/** The rail's shape: tile count, distinct tile rows, and the list's height. */
const railShape = (page: Page) =>
  page.evaluate(() => {
    const list = document.querySelector('footer.capture-undo .capture-undo-list') as HTMLElement
    const tops = [...list.querySelectorAll('.capture-undo-row')].map((el) => Math.round(el.getBoundingClientRect().top))
    return { tiles: tops.length, rows: new Set(tops).size, height: Math.round(list.getBoundingClientRect().height) }
  })

test('dealing with fewer than 15 cards after an undo leaves the rail as it was at Start and at Stop', async ({ page }) => {
  test.setTimeout(600_000)
  const { dealOne, stop, wire } = await startDealing(page, 15)
  for (let n = 1; n <= 15; n += 1) await dealOne(n)
  await stop()
  // Undo down to 7 cards with U, one press at a time.
  for (let left = 14; left >= 7; left -= 1) {
    await page.keyboard.press('u')
    await expect(tiles(page)).toHaveCount(left, { timeout: 15_000 })
  }
  expect(wire.undone).toHaveLength(8)
  for (const width of [1440, 820]) {
    await setViewport(page, { width, height: 900 })
    await expect(control(page, 'Start dispenser')).toBeVisible()
    const before = await railShape(page)
    await control(page, 'Start dispenser').click()
    await expect(control(page, 'Stop dispenser')).toBeVisible()
    await page.waitForTimeout(500) // keep: half a second of dealing with no card in the lens
    const dealing = await railShape(page)
    await control(page, 'Stop dispenser').click()
    await expect(control(page, 'Start dispenser')).toBeVisible({ timeout: 10_000 })
    const after = await railShape(page)
    expect(dealing, `rail at Start, ${width}px`).toEqual(before)
    expect(after, `rail at Stop, ${width}px`).toEqual(before)
  }
})

test('a tile far down the rail carries its live Undo label when it scrolls in or takes focus, and its press undoes that depth', async ({ page }) => {
  test.setTimeout(300_000)
  await observeLongTasks(page)
  await handCamera(page)
  const wire = await stubWire(page, 40)
  await pickCameraAndBox(page)
  await expect(page.getByRole('button', { name: 'Capture', exact: true })).toBeEnabled()
  const shoot = async (n: number) => {
    await page.keyboard.press('c')
    await expect(tiles(page).first()).toHaveAttribute('aria-label', new RegExp(`Card ${n}$`), { timeout: 15_000 })
  }
  const RANK = 20
  for (let n = 1; n <= 26; n += 1) await shoot(n)
  // Rank 20 is Card 6 now. Scroll it into view: its label is its live one.
  await tiles(page).nth(RANK).scrollIntoViewIfNeeded()
  await expect(tiles(page).nth(RANK)).toHaveAttribute('aria-label', new RegExp(`^Undo ${RANK + 1} captures, back to .*Card 6$`))
  // Two more captures, with the rail scrolled back to the newest, then focus the tile by keyboard.
  await tiles(page).first().scrollIntoViewIfNeeded()
  for (const n of [27, 28]) await shoot(n)
  await tiles(page).nth(RANK).focus()
  await expect(tiles(page).nth(RANK)).toHaveAttribute('aria-label', new RegExp(`^Undo ${RANK + 1} captures, back to .*Card 8$`))
  await page.keyboard.press('Enter')
  await expect(tiles(page)).toHaveCount(28 - (RANK + 1), { timeout: 30_000 })
  expect(wire.undone, 'the press undid the depth its label showed').toEqual(
    Array.from({ length: RANK + 1 }, (_, i) => `DELETE /inventory/5/${28 - i}`),
  )
})

/* TILES DRAW FROM THE PHOTO JUST SENT. Ten captures in one sitting ask `/photo` for none, and each
 * tile's image is the frame that capture uploaded (matched by capture_id), not a neighbour's. The
 * camera repaints every 15 ms in a new colour, so two captures never share bytes. */
test('10 captures in one sitting fetch no /photo, and each tile shows its own capture', async ({ page }) => {
  await page.addInitScript(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 640
    canvas.height = 360
    const c = canvas.getContext('2d')
    let n = 0
    setInterval(() => {
      n += 1
      if (c === null) return
      c.fillStyle = `hsl(${(n * 23) % 360},70%,50%)`
      c.fillRect(0, 0, 640, 360)
      c.fillStyle = '#fff'
      c.fillText(String(n * 7919), 20 + (n % 500), 40 + (n % 300))
    }, 15)
    const media = navigator.mediaDevices as unknown as { enumerateDevices: () => Promise<unknown[]>; getUserMedia: () => Promise<MediaStream> }
    const stream = canvas.captureStream(30)
    media.enumerateDevices = async () => [{ deviceId: 'canvas', kind: 'videoinput', label: 'Canvas Cam Link', groupId: 'g' }]
    media.getUserMedia = async () => stream
  })
  await stubWire(page, 1)
  const photoGets: string[] = []
  page.on('request', (r) => { if (/\/photo\//.test(r.url())) photoGets.push(r.url()) })
  const sent = new Map<string, string>() // capture_id -> uploaded base64, in capture order
  let next = 1
  await page.route(/\/capture$/, (r) => {
    const body = JSON.parse(r.request().postData() ?? '{}') as { image: string; capture_id: string }
    const index = next++
    sent.set(body.capture_id, body.image)
    return r.fulfill(json({
      box: 5, index, key: `5/${index}`, label: `Box 5, Card ${index}`, section: 1, card: index, section_div: '1',
      new_box: false, created: true, photo: `/tmp/5-${index}.jpg`, capture_id: body.capture_id,
      place: { box_total: index, located: true, label: `Box 5, Card ${index}` },
    }, 201))
  })
  await pickCameraAndBox(page)
  await expect(page.getByRole('button', { name: 'Capture', exact: true })).toBeEnabled()
  for (let n = 1; n <= 10; n += 1) {
    await page.keyboard.press('c')
    await expect(tiles(page).first()).toHaveAttribute('aria-label', new RegExp(`Card ${n}$`), { timeout: 15_000 })
  }
  expect(sent.size, 'ten distinct uploads').toBe(10)
  expect(new Set(sent.values()).size, 'the stub camera gave ten distinct frames').toBe(10)
  expect(photoGets, 'GET /photo for tiles taken in this page').toEqual([])
  const shown = await tiles(page).evaluateAll(async (rows) => Promise.all(rows.map(async (row) => {
    const src = row.querySelector('img.capture-undo-thumb')?.getAttribute('src') ?? ''
    const bytes = new Uint8Array(await (await fetch(src)).arrayBuffer())
    let bin = ''
    for (const b of bytes) bin += String.fromCharCode(b)
    return { label: row.getAttribute('aria-label') ?? '', src, b64: btoa(bin) }
  })))
  const frames = [...sent.values()]
  expect(shown.length, 'the rail holds the ten tiles').toBeGreaterThanOrEqual(10)
  for (const t of shown) {
    const n = Number(/Card (\d+)$/.exec(t.label)?.[1])
    expect(t.src.startsWith('blob:'), `${t.label} draws a local blob`).toBe(true)
    expect(t.b64 === frames[n - 1], `${t.label} shows the frame it uploaded`).toBe(true)
  }
})

/* A REPLAYED capture_id SAVED NOTHING. After a reload the next capture can reuse a restored id; the
 * server returns the card it already holds with `created: false` and drops the new bytes. The tile
 * must then show the server's photo (a GET /photo), never the frame just sent. */
test('a capture answered created:false shows the server photo, not the frame just sent', async ({ page }) => {
  await handCamera(page)
  await stubWire(page, 1)
  const photoGets: string[] = []
  page.on('request', (r) => { if (/\/photo\//.test(r.url())) photoGets.push(r.url()) })
  let sentFrame = ''
  await page.route(/\/capture$/, (r) => {
    const body = JSON.parse(r.request().postData() ?? '{}') as { image: string; capture_id: string }
    sentFrame = body.image
    return r.fulfill(json({
      box: 5, index: 1, key: '5/1', label: 'Box 5, Card 1', section: 1, card: 1, section_div: '1',
      new_box: false, created: false, photo: '/tmp/5-1.jpg', capture_id: body.capture_id,
      place: { box_total: 1, located: true, label: 'Box 5, Card 1' },
    }, 201))
  })
  await pickCameraAndBox(page)
  await expect(page.getByRole('button', { name: 'Capture', exact: true })).toBeEnabled()
  await page.keyboard.press('c')
  await expect(tiles(page).first()).toHaveAttribute('aria-label', /Card 1$/, { timeout: 15_000 })
  expect(sentFrame, 'a frame was uploaded').not.toBe('')
  const thumb = tiles(page).first().locator('img.capture-undo-thumb')
  await expect(thumb).toHaveAttribute('src', /\/photo\//)
  expect(await thumb.getAttribute('src'), 'the tile does not draw the unsaved frame').not.toMatch(/^blob:/)
  expect(photoGets.length, 'the tile asked the server for its photo').toBeGreaterThan(0)
})
