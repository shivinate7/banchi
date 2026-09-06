import { test, expect } from '@playwright/test'
import { sealEveryTest } from './shell'

/* THE MARK, IN THE BROWSER THAT DRAWS IT.
 *
 * Until this file existed nothing in `app/tests/` mentioned the mark at all — no snapshot, no
 * assertion on the brand block, no reference to `Logo`. The mark could have stopped rendering
 * in every one of its six call sites and `make check` and `make design-check` would both have
 * stayed green.
 *
 * WHAT IS ASSERTED HERE AND NOT IN `scripts/docs-audit.py`. The audit's `logo parity` row
 * reconciles `markPalettes.ts` against docs/specs/logo.md section 9, which is a comparison of
 * two literals and belongs in Python. What it cannot see is whether any of it reaches a screen
 * — CLAUDE.md's own hard rule, and the failure `docs/GATES.md` step 7 records: three tested
 * routes, full coverage, zero client functions, everything green. Only the DOM can say the
 * mark was drawn.
 *
 * THE CUT BOUNDARY IS THE POINT (D102). Section 3 requires two optical cuts and section 11
 * swept the small one. `Logo` picks between them at 64px, and every call site in this product
 * is below that — so a regression that quietly ships the DISPLAY cut everywhere would put a
 * 1.7 stroke into a 32px rail, which is section 9's own measured failure. That boundary is a
 * number in one expression and nothing else watches it.
 *
 * OBSERVED RED BEFORE IT WAS KEPT. Mutation: change `Logo`'s `size < 64` to `size < 16`. The
 * sidebar's 32px mark takes the display cut, `small cut below 64px` finds a filter where it
 * wants none, and the stroked bracket it counts on drops to 0.
 */

const GALLERY = '#/gallery'

/* NOTHING HERE MAY REACH THE CAPTURE SERVER. This file registers no fixtures of its own, so it
   takes the shared small store — `app/tests/shell.ts` carries the argument for both halves. The
   call has to sit above every hook and every case, which `make docs-audit`'s `spec seal` row
   checks: the navigation below happens inside a hook, and a seal declared under it would be
   installed after the requests it exists to catch.  */
sealEveryTest({ store: true })

test('the sidebar brand draws the mark, and names itself without it', async ({ page }) => {
  await page.goto('/')
  const brand = page.locator('.bn-side a.bn-brand')
  await expect(brand).toHaveAttribute('aria-label', 'Banchi home')

  const svg = brand.locator('svg')
  await expect(svg).toHaveCount(1)
  // The mark is never the accessible name of anything: every call site names its own wrapper.
  await expect(svg).toHaveAttribute('aria-hidden', 'true')
  await expect(svg).toHaveAttribute('viewBox', '0 0 100 100')

  // cursor.spec.ts requires exactly one `.bn-side a.bn-nav-link` outside <nav>, and the brand
  // must not become the second one.
  await expect(brand).not.toHaveClass(/bn-nav-link/)
})

test('the small cut ships below 64px, and carries no filter', async ({ page }) => {
  await page.goto('/')
  const svg = page.locator('.bn-side a.bn-brand svg')

  const drawn = await svg.evaluate((el) => ({
    width: el.getAttribute('width'),
    filters: el.querySelectorAll('filter').length,
    turbulence: el.querySelectorAll('feTurbulence').length,
    stroked: el.querySelectorAll('path[stroke-width]').length,
    caps: el.querySelectorAll('circle').length,
  }))

  expect(drawn.width, 'the sidebar draws the mark at 32px').toBe('32')
  // Section 11: the marbling loses to a flat prism gradient at every size this app draws, and
  // removing it is what makes the favicon a plain SVG.
  expect(drawn.filters, 'the small cut carries no filter').toBe(0)
  expect(drawn.turbulence, 'the small cut carries no feTurbulence').toBe(0)
  // No taper means the bracket is a constant-width wire: two stroked paths, not two outlines.
  expect(drawn.stroked, 'two stroked brackets').toBe(2)
  // The display cut caps each tapered free end with a disc. A constant-width wire ends in a
  // round linecap and needs none, so a circle here means the display cut leaked through.
  expect(drawn.caps, 'the small cut draws no cap discs').toBe(0)
})

test('the display cut is what the gallery shows at 64px and above', async ({ page }) => {
  await page.goto(GALLERY)
  const section = page.locator('[data-kit-section="mark"]')
  await expect(section).toBeVisible()

  const cuts = await section.evaluate((el) => {
    const at = (px: string) => el.querySelector(`svg[width="${px}"]`)
    const small = at('56')
    const display = at('96')
    return {
      small: small ? small.querySelectorAll('feTurbulence').length : -1,
      display: display ? display.querySelectorAll('feTurbulence').length : -1,
      boundary: at('64') ? at('64')!.querySelectorAll('feTurbulence').length : -1,
    }
  })

  expect(cuts.small, 'the 56px row is the small cut').toBe(0)
  expect(cuts.display, 'the 96px row is the display cut').toBe(1)
  // 64 is the boundary itself and belongs to the display cut — "64px and up" (section 3).
  expect(cuts.boundary, '64px takes the display cut').toBe(1)
})

test('all six locked marks are drawn, and they differ', async ({ page }) => {
  await page.goto(GALLERY)
  const palettes = await page
    .locator('[data-kit-section="mark"] svg[width="56"]')
    .evaluateAll((els) =>
      els.map((el) =>
        Array.from(el.querySelectorAll('stop'))
          .map((s) => s.getAttribute('stop-color'))
          .join(' '),
      ),
    )

  expect(palettes, 'section 9 locks six marks').toHaveLength(6)
  // The whole palette, not the ground: section 9 gives all three gold marks the same true
  // black, so grounds alone would only ever distinguish four. A variant prop that silently
  // fell back to the default would draw six identical tiles, and every other assertion in
  // this file would still pass.
  expect(new Set(palettes).size, 'each variant draws its own palette').toBe(6)
})

test('the mark is fixed dark in both themes', async ({ page }) => {
  // D102: the placeholder was drawn in --bn-ink on --bn-bg and inverted with the theme. This
  // one does not — a light ground was derived in section 12 and lost its silhouette at every
  // size this app draws.
  const ground = async () =>
    page
      .locator('.bn-side a.bn-brand svg linearGradient > stop')
      .first()
      .getAttribute('stop-color')

  await page.goto('/')
  const light = await ground()

  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
  const dark = await ground()

  expect(light, 'the locked bluesteel ground').toBe('#182430')
  expect(dark, 'the same ground in dark theme').toBe(light)
})

/* THE COLLAPSE DOES NOT THROW THE SIDEBAR ACROSS THE SCREEN.
 *
 * `.bn-side`'s rail rules used to centre their children — `justify-content: center` on the brand
 * and `margin: 0 auto` on every nav link. Both resolve against the sidebar's width, and that
 * width is ANIMATING for --bn-t-slow. So at frame 0 each one re-centred itself in a column that
 * had barely started closing and then slid back: measured at 1440, the mark's centre went
 * 36 -> 114.8 -> 31.5 and the nav icons did the same. A rubber-band on every row of the shipped
 * product.
 *
 * IT WAS INVISIBLE TO EVERY CHECK THIS REPO HAS, and would be again. Both RESTING states were
 * correct to the pixel, so a screenshot proves nothing and neither does an assertion on either
 * end; the defect existed only in the frames between them. This is the only test here that
 * samples mid-transition, and that is the whole point of it.
 *
 * The assertion is a corridor rather than a curve. Where exactly the mark sits at 80ms depends on
 * the easing token and on how fast the machine renders; that it never leaves the span between its
 * own two resting positions does not. A test that pinned the curve would fail the first time
 * anybody retuned --bn-ease, which is a change this assertion should survive. */
test('collapsing the sidebar moves nothing sideways off its spine', async ({ page }) => {
  await page.goto('/')
  await page.setViewportSize({ width: 1440, height: 900 })

  const centres = () =>
    page.evaluate(() => {
      const box = (sel: string) => {
        const el = document.querySelector(sel)
        if (!el) return null
        const r = el.getBoundingClientRect()
        return r.left + r.width / 2
      }
      return { mark: box('.bn-side .bn-brand svg'), nav: box('.bn-side .bn-nav-link .bn-icon') }
    })

  const open = await centres()
  expect(open.mark, 'the brand is drawn').not.toBeNull()

  await page.keyboard.press('Meta+Period')
  // three samples inside the 320ms, deliberately not synchronised to any frame
  const during: Array<{ mark: number | null; nav: number | null }> = []
  for (let i = 0; i < 3; i++) {
    await page.waitForTimeout(60)
    during.push(await centres())
  }
  await page.waitForTimeout(400)
  const rail = await centres()

  // the corridor: every mid-flight sample sits between the two resting positions, with 2px of
  // slack for subpixel layout. Before the fix these read ~114 against a corridor of 31.5 to 36.
  for (const [i, s] of during.entries()) {
    for (const key of ['mark', 'nav'] as const) {
      const a = open[key]!, b = rail[key]!, v = s[key]!
      const lo = Math.min(a, b) - 2, hi = Math.max(a, b) + 2
      expect(v, `sample ${i}: the ${key} left its spine — ${v} is outside ${lo}..${hi}`)
        .toBeGreaterThanOrEqual(lo)
      expect(v, `sample ${i}: the ${key} left its spine — ${v} is outside ${lo}..${hi}`)
        .toBeLessThanOrEqual(hi)
    }
  }
})
