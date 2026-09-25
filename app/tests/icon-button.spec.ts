import { test, expect } from '@playwright/test'
import { sealEveryTest } from './shell'
import { settleMotion } from './motionSettled'

declare global {
  interface Window {
    __iconClicks?: number
  }
}

/* ICONBUTTON, THE ROUND-2 FINDINGS KEPT AS BROWSER ASSERTIONS. `docs/decisions/D-icon-buttons.md`
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
  const tip = btn.locator('.bn-icon-tip')
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
  const before = await section.evaluate((el) =>
    [...el.querySelectorAll('*')]
      .filter((n) => !n.classList.contains('bn-icon-tip') && !n.closest('.bn-icon-tip'))
      .map((n) => { const r = n.getBoundingClientRect(); return `${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.width)},${Math.round(r.height)}` }),
  )
  await btn.hover()
  await expect(btn.locator('.bn-icon-tip')).toHaveCSS('opacity', '1')
  const after = await section.evaluate((el) =>
    [...el.querySelectorAll('*')]
      .filter((n) => !n.classList.contains('bn-icon-tip') && !n.closest('.bn-icon-tip'))
      .map((n) => { const r = n.getBoundingClientRect(); return `${Math.round(r.left)},${Math.round(r.top)},${Math.round(r.width)},${Math.round(r.height)}` }),
  )
  const moved = before.filter((v, i) => v !== after[i])
  expect(moved, `${moved.length} element(s) moved when the tooltip opened`).toHaveLength(0)
})

test('the overlay Close tooltip is not clipped by the sheet, at 1440 and at 390', async ({ page }) => {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 })
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
    const tip = close.locator('.bn-icon-tip')
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
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(GALLERY)
  const section = page.locator('[data-kit-section="icon-button"]')
  await section.scrollIntoViewIfNeeded()
  const first = section.locator('.bn-icon-btn').first()
  await first.hover()
  const tip = first.locator('.bn-icon-tip')
  await expect(tip).toHaveCSS('opacity', '1')
  const r = await tip.evaluate((e) => e.getBoundingClientRect())
  expect(r.left, 'the tooltip runs off the left edge at 390px').toBeGreaterThanOrEqual(0)
  expect(r.right, 'the tooltip runs off the right edge at 390px').toBeLessThanOrEqual(390)
})

test('a long-press opens the tooltip and does not also press the button', async ({ page, browserName }) => {
  test.skip(browserName !== 'chromium', 'CDP touch dispatch is Chromium-only')
  await page.setViewportSize({ width: 390, height: 844 })
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
  await page.waitForTimeout(700)
  await expect(btn).toHaveAttribute('data-tip-open', 'true')
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
  await page.waitForTimeout(300)
  const clicks = await page.evaluate(() => window.__iconClicks)
  expect(clicks, 'the long-press that revealed the tooltip also pressed the button').toBe(0)

  // A quick tap (under the long-press threshold) still presses it, exactly once.
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [point] })
  await page.waitForTimeout(60)
  await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
  await page.waitForTimeout(300)
  const tapClicks = await page.evaluate(() => window.__iconClicks)
  expect(tapClicks, 'a quick tap did not press the button').toBe(1)
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

/* THE ANCHOR FORM (round-2 sibling of D-icon-buttons): `href` renders an `<a>` instead of a
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
  const tip = link.locator('.bn-icon-tip')
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
