// Protects: The icon button keeps its 40px hit area, unclipped tooltip, no ghost click after a long press, readable toast close and correct glyph size.
// Governs: D118, D288
import { test, expect } from '@playwright/test'
import { sealEveryTest } from './shell'
import { settleMotion } from './motionSettled'
import { iconTip } from './iconTooltip'
import { phoneOff, setViewport } from './phoneSwitch'

declare global {
  interface Window {
    __iconClicks?: number
  }
}

/* ICONBUTTON, THE ROUND-2 FINDINGS KEPT AS BROWSER ASSERTIONS. D288
 * and `docs/specs/iconography.md` carry the argument; this file is what proved the fixes and
 * refuses their return.
 *
 * EACH CASE WAS OBSERVED RED, ON THE REVIEW'S OWN MEASUREMENTS, BEFORE THIS FILE EXISTED:
 *   - the hit area: before round 2, the 40px floor was the whole box, so it grew a 34px field
 *     row (FLT-24) and the search field on the first keystroke (D118). `SD/review/kit-icons/
 *     fields.mjs` measured the growth; the fix moved the floor to a `::before`.
 *   - the tooltip inside a sheet: `SD/review/kit-icons/overlay.mjs` measured the overlay
 *     Close tooltip's own top landing at -14px, clipped by `.bn-sheet`'s `overflow: hidden`.
 *   - the long-press: `SD/review/kit-icons/interact.mjs` measured a `click` firing once the
 *     touch that opened the tooltip lifted.
 *   - the toast contrast: `SD/review/kit-icons/toast.mjs` measured the dismiss glyph at
 *     1.83:1 in light theme, `.bn-icon-face`'s own colour beating `.bn-toast-close`'s
 *     `color: inherit`.
 *
 * ROUND 3's own delta review found a fifth, in the same file this list already covers:
 *   - the glyph size: round 2 dropped the `.bn-icon-face` wrapper and put `style={{ width:
 *     FACE_PX[size], height: FACE_PX[size] }}` straight on `<Icon>`. `Icon.tsx` spreads
 *     `rest` onto the `<svg>` after its own `width`/`height` attributes, and inline CSS beats
 *     an SVG attribute — every glyph drew at the FACE size, filling its whole box, not at
 *     GLYPH_PX. The fix drops that `style` prop; the button's own box is already FACE_PX and
 *     `.bn-icon-btn`'s flex centring places the smaller glyph inside it.
 */

const GALLERY = '/#/gallery'

sealEveryTest({ store: true })

test.beforeEach(async ({ page }) => {
  await page.goto(GALLERY)
  await expect(page.locator('[data-kit-section="icon-button"]')).toBeVisible()
  await settleMotion(page)
})

/* FACE_PX and GLYPH_PX, `kit/index.tsx`'s own table, read here rather than imported: this
 * file is a browser spec and the table is a private module constant, so it is the test's own
 * record of intent, checked against what the DOM actually draws. */
const SIZES: readonly { readonly size: string; readonly face: number; readonly glyph: number }[] = [
  { size: 'sm', face: 24, glyph: 12 },
  { size: 'md', face: 28, glyph: 14 },
  { size: 'lg', face: 34, glyph: 16 },
  { size: 'xl', face: 40, glyph: 18 },
]

test('every size draws its face at FACE_PX and its glyph at GLYPH_PX, never the face size on the svg', async ({ page }) => {
  const section = page.locator('[data-kit-section="icon-button"]')
  for (const { size, face, glyph } of SIZES) {
    const btn = section.getByRole('button', { name: `Undo (${size})` })
    const svg = btn.locator('svg')
    const faceBox = await btn.evaluate((el) => { const r = el.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height) } })
    const glyphBox = await svg.evaluate((el) => { const r = el.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height) } })
    expect([faceBox.w, faceBox.h], `size ${size} face`).toEqual([face, face])
    expect([glyphBox.w, glyphBox.h], `size ${size} glyph`).toEqual([glyph, glyph])
  }
})

test('the 40px hit area extends past the visual face, and clicking the extension still presses the button', async ({ page }) => {
  const section = page.locator('[data-kit-section="icon-button"]')
  const btn = section.getByRole('button', { name: 'Retire' })
  await btn.scrollIntoViewIfNeeded()
  const box = await btn.boundingBox()
  expect(box, 'the button drew no box at all').not.toBeNull()
  const b = box as NonNullable<typeof box>
  // The face is smaller than 40px at this size (FLT-24: the visual box is the face, not the
  // floor) — the button's OWN box, read from the DOM, is the face; the ::before pseudo is
  // what extends the click past it, invisibly, so this asserts the extension by clicking a
  // point outside the drawn box and inside where 40px would reach.
  expect(Math.max(b.width, b.height), 'the face itself is already 40px or more — nothing to extend').toBeLessThan(40)
  await page.evaluate(() => {
    window.__iconClicks = 0
    document.addEventListener('click', (e) => {
      if ((e.target as HTMLElement)?.closest('.bn-icon-btn')) window.__iconClicks = (window.__iconClicks ?? 0) + 1
    })
  })
  // 3px outside the box's own top edge, centred horizontally — outside the face itself and
  // safely inside where the 40px floor reaches (up to 6px past a 28px face here). Measured:
  // a real click AT the outer edge of that reach (6px out) misses on a whole band of viewport
  // widths — a genuine sub-pixel rounding gap in Chromium's own hit-test, present headed and
  // headless alike, not a Playwright artifact. 3px keeps clear of that edge on every width
  // this suite runs at while still proving the extension, since the face's own edge is 14px
  // out from centre and the floor's is 20px.
  const x = b.x + b.width / 2
  const y = b.y - 3
  await page.mouse.click(x, y)
  const clicks = await page.evaluate(() => window.__iconClicks)
  expect(clicks, 'a click just outside the visual face did not reach the button — the 40px floor is not there').toBe(1)
})

test('the tooltip shows on hover and on keyboard focus, and hides after a mouse click', async ({ page }) => {
  const section = page.locator('[data-kit-section="icon-button"]')
  const btn = section.getByRole('button', { name: 'Retire' })
  const tip = await iconTip(btn)
  await expect(tip).toHaveCSS('opacity', '0')
  await btn.hover()
  await expect(tip).toHaveCSS('opacity', '1')
  await page.mouse.move(0, 0)
  await btn.focus()
  await expect(tip).toHaveCSS('opacity', '1')
  await btn.click()
  await expect(tip).toHaveCSS('opacity', '0')
})

test('showing the tooltip moves nothing else on the page (D118)', async ({ page }) => {
  const section = page.locator('[data-kit-section="icon-button"]')
  const btn = section.getByRole('button', { name: 'Retire' })
  await btn.scrollIntoViewIfNeeded()
  /* The tip is portalled to `<body>` (round 3), so `section.querySelectorAll('*')` never
   * finds it — no filter is needed to keep it out of this "moved" comparison, unlike round 2's
   * DOM-child shape. */
  const before = await section.evaluate((el) =>
    [...el.querySelectorAll('*')]
      .map((n) => { const r = n.getBoundingClientRect(); return `${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.width)},${Math.round(r.height)}` }),
  )
  await btn.hover()
  await expect(await iconTip(btn)).toHaveCSS('opacity', '1')
  const after = await section.evaluate((el) =>
    [...el.querySelectorAll('*')]
      .map((n) => { const r = n.getBoundingClientRect(); return `${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.width)},${Math.round(r.height)}` }),
  )
  const moved = before.filter((v, i) => v !== after[i])
  expect(moved, `${moved.length} element(s) moved when the tooltip opened`).toHaveLength(0)
})

test('the overlay Close tooltip is not clipped by the sheet, at 1440 and at 390', async ({ page }) => {
  for (const width of [1440, 390]) {
    if (phoneOff(width)) continue
    await setViewport(page, { width, height: 900 })
    const opener = page.locator('[data-kit-section] button', { hasText: /^Open (a |the )?(sheet|modal)/i }).first()
    if ((await opener.count()) === 0) continue
    await opener.scrollIntoViewIfNeeded()
    await opener.click()
    const close = page.locator('.bn-overlay-close').last()
    await expect(close).toBeVisible()
    // The sheet/modal's own entrance animation (bn-dialog-in/bn-sheet-up, kit.css) still moves
    // the Close button under a transform for the first --bn-t-slow after it mounts. A hover
    // landing mid-animation loses the button out from under the pointer as it keeps sliding,
    // which reads here as opacity climbing then reversing (fulfillment.spec.ts's own D118
    // comment names the same shape of reading). settleMotion first, like that file does.
    await settleMotion(page)
    await close.hover()
    const tip = await iconTip(close)
    await expect(tip).toHaveCSS('opacity', '1')
    const r = await tip.evaluate((e) => e.getBoundingClientRect())
    expect(r.top, `the tooltip's own top is off-screen at ${width}px`).toBeGreaterThanOrEqual(0)
    expect(r.left, `the tooltip runs off the left edge at ${width}px`).toBeGreaterThanOrEqual(0)
    expect(r.right, `the tooltip runs off the right edge at ${width}px`).toBeLessThanOrEqual(width)
    // Escape to close before the next width's pass reuses the page.
    await page.keyboard.press('Escape')
  }
})

test('the tooltip stays inside the viewport at 390, for the first icon button on the page', async ({ page }) => {
  await setViewport(page, { width: 390, height: 844 })
  await page.goto(GALLERY)
  const section = page.locator('[data-kit-section="icon-button"]')
  await section.scrollIntoViewIfNeeded()
  const first = section.locator('.bn-icon-btn').first()
  await first.hover()
  const tip = await iconTip(first)
  await expect(tip).toHaveCSS('opacity', '1')
  const r = await tip.evaluate((e) => e.getBoundingClientRect())
  expect(r.left, 'the tooltip runs off the left edge at 390px').toBeGreaterThanOrEqual(0)
  expect(r.right, 'the tooltip runs off the right edge at 390px').toBeLessThanOrEqual(390)
})

test('a long-press opens the tooltip and does not also press the button', async ({ page, browserName }) => {
  test.skip(browserName !== 'chromium', 'CDP touch dispatch is Chromium-only')
  await setViewport(page, { width: 390, height: 844 })
  await page.goto(GALLERY)
  const section = page.locator('[data-kit-section="icon-button"]')
  await section.scrollIntoViewIfNeeded()
  const btn = section.locator('.bn-icon-btn').first()
  await page.evaluate(() => {
    window.__iconClicks = 0
    document.querySelector('[data-kit-section="icon-button"] .bn-icon-btn')?.addEventListener('click', () => {
      window.__iconClicks = (window.__iconClicks ?? 0) + 1
    })
  })
  const box = await btn.boundingBox()
  expect(box).not.toBeNull()
  const b = box as NonNullable<typeof box>
  const point = { x: Math.round(b.x + b.width / 2), y: Math.round(b.y + b.height / 2) }
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [point] })
  // the hold is the touch itself; the tooltip opens once it passes the long-press threshold
  await expect(btn).toHaveAttribute('data-tip-open', 'true')
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
  await page.waitForTimeout(300) // keep: asserts the long-press release presses nothing
  const clicks = await page.evaluate(() => window.__iconClicks)
  expect(clicks, 'the long-press that revealed the tooltip also pressed the button').toBe(0)

  // A quick tap (under the long-press threshold) still presses it, exactly once.
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [point] })
  await page.waitForTimeout(60) // keep: a tap under the long-press threshold is a real duration
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
  await expect.poll(() => page.evaluate(() => window.__iconClicks), { message: 'a quick tap did not press the button' }).toBe(1)
})

test('the toast dismiss glyph clears 4.5:1 against the toast ground, in both themes', async ({ page }) => {
  for (const scheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme: scheme })
    await page.goto(GALLERY)
    const toast = page.locator('.bn-toast.bn-toast-receipt')
    await expect(toast).toBeVisible()
    const close = toast.locator('.bn-toast-close')
    const ratio = await close.evaluate((el, toastEl) => {
      const L = (c: string) => {
        const m = c.match(/[\d.]+/g)
        if (!m) return 0
        const a = m.slice(0, 3).map((v) => {
          const s = Number(v) / 255
          return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
        })
        return 0.2126 * (a[0] ?? 0) + 0.7152 * (a[1] ?? 0) + 0.0722 * (a[2] ?? 0)
      }
      const bg = getComputedStyle(toastEl as Element).backgroundColor
      const fg = getComputedStyle(el).color
      const a = L(fg)
      const b = L(bg)
      return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
    }, await toast.elementHandle())
    expect(ratio, `${scheme} theme: the dismiss glyph is ${ratio.toFixed(2)}:1 against the toast`).toBeGreaterThanOrEqual(4.5)
  }
})

/* THE ANCHOR FORM (round-2 sibling of D288): `href` renders an `<a>` instead of a
 * `<button>`, so a link that opens another route or tab keeps the browser's own middle-click,
 * right-click "open in new tab" and "copy link" — none of which a `window.open` in an
 * `onClick` can give. The specimen is `#/gallery`'s "the anchor form" spec, `IconButton icon=
 * "external" label="Cards to pull" href="#/fulfillment" target="_blank" rel="noreferrer"`. */
test('the anchor form renders an <a> with the given href, target and rel', async ({ page }) => {
  const section = page.locator('[data-kit-section="icon-button"]')
  const link = section.getByRole('link', { name: 'Cards to pull' })
  await expect(link).toBeVisible()
  expect(await link.evaluate((el) => el.tagName)).toBe('A')
  await expect(link).toHaveAttribute('href', '#/fulfillment')
  await expect(link).toHaveAttribute('target', '_blank')
  await expect(link).toHaveAttribute('rel', 'noreferrer')
})

test('keyboard Enter follows the anchor form, the way a native link does', async ({ page }) => {
  const section = page.locator('[data-kit-section="icon-button"]')
  const link = section.getByRole('link', { name: 'Cards to pull' })
  await link.focus()
  await expect(link).toBeFocused()
  const [popup] = await Promise.all([
    page.context().waitForEvent('page'),
    page.keyboard.press('Enter'),
  ])
  await popup.waitForLoadState()
  expect(popup.url()).toContain('#/fulfillment')
  await popup.close()
})

test('the anchor form draws the same face, hit area and tooltip as the button form', async ({ page }) => {
  const section = page.locator('[data-kit-section="icon-button"]')
  const link = section.getByRole('link', { name: 'Cards to pull' })
  const btn = section.getByRole('button', { name: 'Retire' })
  // Both are `size="md"` (the default): same FACE_PX box.
  const linkBox = await link.evaluate((el) => { const r = el.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height) } })
  const btnBox = await btn.evaluate((el) => { const r = el.getBoundingClientRect(); return { w: Math.round(r.width), h: Math.round(r.height) } })
  expect(linkBox).toEqual(btnBox)
  await link.scrollIntoViewIfNeeded()
  // The tooltip, the same accessible name and text as the label passed to it — read BEFORE
  // the click below, which opens a new tab and leaves this one backgrounded.
  const tip = await iconTip(link)
  await expect(tip).toHaveCSS('opacity', '0')
  await link.hover()
  await expect(tip).toHaveCSS('opacity', '1')
  await expect(tip).toHaveText('Cards to pull')
  await expect(link).toHaveAccessibleName('Cards to pull')
  await page.mouse.move(0, 0)
  // The `::before` hit area reaches 40px past the drawn face on the anchor too.
  const box = await link.boundingBox()
  expect(box, 'the link drew no box at all').not.toBeNull()
  const b = box as NonNullable<typeof box>
  expect(Math.max(b.width, b.height), 'the face itself is already 40px or more — nothing to extend').toBeLessThan(40)
  await page.evaluate(() => {
    window.__iconClicks = 0
    document.addEventListener('click', (e) => {
      if ((e.target as HTMLElement)?.closest('a.bn-icon-btn')) window.__iconClicks = (window.__iconClicks ?? 0) + 1
    }, { capture: true })
  })
  const x = b.x + b.width / 2
  const y = b.y - 3
  const [popup] = await Promise.all([
    page.context().waitForEvent('page'),
    page.mouse.click(x, y),
  ])
  await popup.close()
  const clicks = await page.evaluate(() => window.__iconClicks)
  expect(clicks, 'a click just outside the visual face did not reach the anchor — the 40px floor is not there').toBe(1)
})

/* SIZE AND CENTRING, EVERY GLYPH (owner's word, 2026-09-29; F7 of PLAN-PR4-PR5). The gallery's
 * `data-icon-glyphs` row draws every icon in the set in one xl IconButton. The glyph's centre
 * is read two ways because neither alone is optical: the geometric centre of its bounding box,
 * and the centroid of its ink (an alpha-weighted render, the measure the lock's re-centring
 * used). The button centre must lie between the two, within GLYPH_TOL_PX. A triangle's ink
 * sits off its box centre by design, so the pair brackets the answer where one number alone
 * would fail `play`. A glyph that fails is fixed by a rigid shift of its path in `Icon.tsx`,
 * the lock's mechanism, never by a per-screen nudge. */
const GLYPH_TOL_PX = 0.3

test('every glyph in an xl button: one box size, one glyph size, centre between its box centre and its ink centre', async ({ page }) => {
  const rows = await page.evaluate(async () => {
    const out: { n: string; w: number; h: number; gw: number; gh: number; ex: number; ey: number }[] = []
    for (const b of document.querySelectorAll('[data-icon-glyphs] .bn-icon-btn')) {
      const s = b.querySelector('svg') as SVGSVGElement
      const r = b.getBoundingClientRect()
      const sr = s.getBoundingClientRect()
      const src = new XMLSerializer().serializeToString(s).replace('currentColor', '#000').replace(/width="[^"]*"/, 'width="240"').replace(/height="[^"]*"/, 'height="240"')
      const img = new Image()
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(src)
      await img.decode()
      const c = document.createElement('canvas')
      c.width = c.height = 240
      const x = c.getContext('2d') as CanvasRenderingContext2D
      x.drawImage(img, 0, 0)
      const d = x.getImageData(0, 0, 240, 240).data
      let m = 0, sx = 0, sy = 0
      for (let j = 0; j < 240; j++) for (let i = 0; i < 240; i++) { const a = d[(j * 240 + i) * 4 + 3] ?? 0; m += a; sx += a * (i + 0.5); sy += a * (j + 0.5) }
      const k = sr.width / 240
      const kk = sr.width / 24
      const bb = s.getBBox()
      const ox = sr.x + sr.width / 2 - r.x - r.width / 2
      const oy = sr.y + sr.height / 2 - r.y - r.height / 2
      const cx = (sx / m - 120) * k + ox, cy = (sy / m - 120) * k + oy
      const bx = (bb.x + bb.width / 2 - 12) * kk + ox, by = (bb.y + bb.height / 2 - 12) * kk + oy
      // How far the button centre (0) lies outside the span of the two readings, per axis.
      const out1 = (a: number, b2: number) => Math.max(0, Math.min(a, b2), -Math.max(a, b2))
      out.push({ n: b.getAttribute('aria-label') ?? '?', w: Math.round(r.width), h: Math.round(r.height), gw: Math.round(sr.width), gh: Math.round(sr.height), ex: out1(cx, bx), ey: out1(cy, by) })
    }
    return out
  })
  expect(rows.length, 'the glyph row drew no buttons').toBeGreaterThan(50)
  const odd = rows.filter((r) => r.w !== 40 || r.h !== 40 || r.gw !== 18 || r.gh !== 18)
  expect(odd.map((r) => `${r.n} ${r.w}x${r.h} glyph ${r.gw}x${r.gh}`), 'a button or glyph off the xl size').toEqual([])
  const off = rows.filter((r) => r.ex > GLYPH_TOL_PX || r.ey > GLYPH_TOL_PX)
  expect(off.map((r) => `${r.n}: ${r.ex.toFixed(2)}px x, ${r.ey.toFixed(2)}px y outside`), 'glyphs sitting off their button centre').toEqual([])
})

/* A PANEL'S ENTRY MAY FADE AND MAY NOT MOVE (the kit's `bn-dialog-in`, `bn-sheet-in`).
 *
 * A control that moves between pointer-down and pointer-up gets no `click` (the up lands on its
 * parent), so a press held ~200ms during a moving entry was lost. This samples a control's box as
 * soon as the panel is drawn, then once the motion is done; a keyframe that translates or scales
 * the panel moves the control between the two and goes red. */
for (const [kind, opener, panel, control] of [
  ['dialog', 'modal', '.bn-dialog', 'Done'],
  ['sheet', 'sheet', '.bn-sheet', 'Save'],
] as const) {
  test(`a ${kind}'s controls hold still while it enters`, async ({ page }) => {
    await page.locator(`[data-kit-open="${opener}"]`).click()
    const btn = page.locator(panel).getByRole('button', { name: control, exact: true })
    await btn.waitFor({ state: 'attached' })
    const during = await btn.boundingBox()
    await settleMotion(page)
    const after = await btn.boundingBox()
    expect(during, `${kind} control drawn`).not.toBeNull()
    expect(after, `${kind} control settled`).not.toBeNull()
    expect(Math.abs(during!.x - after!.x), `${kind} control x`).toBeLessThanOrEqual(0.5)
    expect(Math.abs(during!.y - after!.y), `${kind} control y`).toBeLessThanOrEqual(0.5)
    expect(Math.abs(during!.width - after!.width), `${kind} control width`).toBeLessThanOrEqual(0.5)
  })
}
