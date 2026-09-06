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
  // THE BRAND IS THE COLLAPSE CONTROL, so it is a <button> here and an <a> in the phone drawer.
  // It was a link to #/ with a 22px chevron beside it, and that chevron was mostly unclickable:
  // `.bn-side` is `overflow: hidden` and it sat half outside the right edge, so the outer half
  // was clipped and the banner covered much of the rest.
  const brand = page.locator('.bn-side .bn-brand')
  await expect(brand).toHaveJSProperty('tagName', 'BUTTON')
  await expect(brand).toHaveAttribute('aria-label', 'Collapse the sidebar')
  await expect(brand).toHaveAttribute('aria-expanded', 'true')

  // TWO DRAWINGS, ONE OF WHICH IS SHOWING. Section 16 puts the lockup in the open sidebar and
  // the empty slot in the rail, and both are mounted at once so CSS can choose — a JSX branch on
  // `rail` would be wrong at 768-1023px, where App.css rails the shell by media query and
  // `data-rail` is inert. So this counts them and then scopes.
  await expect(brand.locator('.bn-brand-slot > svg')).toHaveCount(2)
  // and the third svg is the chevron, which is a HINT rather than the control: the control is the
  // whole 128 x 93 row, which is the entire point of moving the affordance here.
  await expect(brand.locator('.bn-brand-chevron')).toHaveCount(1)

  const svg = brand.locator('.bn-brand-mark')
  // The mark is never the accessible name of anything: every call site names its own wrapper.
  await expect(svg).toHaveAttribute('aria-hidden', 'true')
  await expect(svg).toHaveAttribute('viewBox', '0 0 100 100')

  // AND NEITHER IS THE LOCKUP, HERE. Standing alone at #/gallery it carries `role="img"` and a
  // name, because it IS the word — but inside this button a named child would announce the name
  // twice over the control's own label, so the sidebar's call site passes `decorative`.
  const lockup = brand.locator('.bn-brand-lockup')
  await expect(lockup).toHaveAttribute('aria-hidden', 'true')
  // section 16 settled kanji 40, which is a 128 x 93 block in the sidebar's 212px
  await expect(lockup).toHaveAttribute('width', '127.6')
  await expect(lockup).toHaveAttribute('height', '93.2')

  // THE LOCKUP REPLACES THE WORDMARK AND THE TAGLINE, it does not sit beside them (section 16).
  await expect(page.locator('.bn-side .bn-brand-name')).toHaveCount(0)
  await expect(page.locator('.bn-side .bn-brand-tag')).toHaveCount(0)

  // cursor.spec.ts requires exactly one `.bn-side a.bn-nav-link` outside <nav>, and the brand
  // must not become the second one. It is no longer an anchor at all, which is the strongest
  // form of that — but the assertion stays, because the phone drawer's brand still is one.
  await expect(brand).not.toHaveClass(/bn-nav-link/)
})

test('the small cut ships below 64px, and carries no filter', async ({ page }) => {
  await page.goto('/')

  const drawn = await page.locator('.bn-side .bn-brand .bn-brand-mark').evaluate((el) => ({
    width: el.getAttribute('width'),
    filters: el.querySelectorAll('filter').length,
    turbulence: el.querySelectorAll('feTurbulence').length,
    stroked: el.querySelectorAll('path[stroke-width]').length,
    caps: el.querySelectorAll('circle').length,
    // the tile and the card, which `Logo` draws and this does not
    tiles: el.querySelectorAll('rect').length,
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
  // THE EMPTY SLOT, NOT THE APP ICON (section 1). `Logo` draws a superellipse tile and the card
  // inside it; the rail draws the brackets with the card taken out. Shipping `Logo` here read as
  // the favicon rather than as the collapsed lockup, and no assertion in this file could tell —
  // every other number above is identical for both drawings.
  expect(drawn.tiles, 'the rail mark carries no tile and no card').toBe(0)
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

test('the tile mark is fixed dark in both themes, and the rail mark is not', async ({ page }) => {
  // D102: the placeholder was drawn in --bn-ink on --bn-bg and inverted with the theme. `Logo`
  // does not — a light ground was derived in section 12 and lost its silhouette at every size
  // this app draws. The gallery is where that claim lives now, because the sidebar no longer
  // draws a tile at all.
  await page.goto(GALLERY)
  const ground = () =>
    page
      .locator('[data-kit-section="mark"] svg[width="56"] linearGradient > stop')
      .first()
      .getAttribute('stop-color')

  const light = await ground()
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
  const dark = await ground()

  expect(light, 'the locked bluesteel ground').toBe('#182430')
  expect(dark, 'the same ground in dark theme').toBe(light)
})

/* AND THE RAIL MARK TAKES THE OPPOSITE RULE, ON PURPOSE.
 *
 * `Logo` can be one drawing in both themes because it brings its own dark tile. The rail mark has
 * no ground — it inherits the sidebar's surface — so painting `bluesteel`'s chrome on it flat
 * would put a #FFFFFF-to-#8FA4B8 wire on a light sidebar. Section 16 already settled that switch
 * for the lockup's frame, and this is the same object in the same metal, so it takes the same one.
 *
 * THE SYSTEM PREFERENCE IS SET TO DARK HERE AND THAT IS THE WHOLE TEST. This product resolves the
 * system preference in JS — `kit/index.tsx:applyTheme` stamps `data-theme="dark"` for dark and
 * REMOVES the attribute for light, and `tokens.css` carries no `prefers-color-scheme` block at
 * all. So the light theme is the ABSENCE of the attribute, and any media query in a stylesheet
 * fires in a state the rest of the product cannot enter: system dark, app painting light.
 *
 * IT SHIPPED THAT WAY. `.bn-lockup-bracket` carried
 * `@media (prefers-color-scheme: dark) { :root:not([data-theme='light']) ... }` — the three-state
 * pattern, correct for a stylesheet that reads the system preference itself and wrong for this
 * one — and on a system-dark machine with the theme set to light the running app read body
 * `rgb(244,245,248)`, kanji `rgb(15,18,23)` and bracket `url("#_r_0_m")`. Both RESTING themes
 * were right, which is why nothing caught it: the defect needs the system preference and the
 * stored choice to disagree, and every check in this repo ran with them agreeing.
 *
 * So the light half is reached the way the APP reaches it — by removing the attribute, never by
 * stamping `light`, which no code path in this product does. Stamping it would make this test
 * green against the defect it exists to catch. */
test.describe('with the system preference set to dark', () => {
  test.use({ colorScheme: 'dark' })

  test('the lockup and the rail mark follow the app, not the system', async ({ page }) => {
    await page.goto('/')
    const inks = () =>
      page.evaluate(() => ({
        body: getComputedStyle(document.body).backgroundColor,
        bracket: getComputedStyle(document.querySelector('.bn-lockup-bracket')!).fill,
        rail: getComputedStyle(document.querySelector('.bn-rail-mark-arm')!).stroke,
      }))

    // the app painting LIGHT while the machine asks for dark — the attribute is absent, which is
    // what `applyTheme` leaves behind, not `data-theme="light"`
    await page.evaluate(() => document.documentElement.removeAttribute('data-theme'))
    const light = await inks()
    expect(light.bracket, 'flat ink on light — a paint, not a gradient reference')
      .not.toContain('url(')
    expect(light.rail, 'the rail mark takes the same ink').not.toContain('url(')
    // and it is the SAME ink the type beside it is drawn in, which is section 16's own claim
    expect(light.rail, 'one ink for the whole frame').toBe(light.bracket)

    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
    const dark = await inks()
    expect(dark.bracket, "bluesteel's own chrome on dark").toContain('url(')
    expect(dark.rail, 'and the rail mark is the same object in it').toContain('url(')
  })
})

/* THE BRAND IS THE CONTROL — the user's own instruction, after the 22px chevron proved
   unclickable. Nothing else in this suite presses it, and the whole affordance is one onClick. */
test('pressing the brand collapses the sidebar and expands it again', async ({ page }) => {
  await page.goto('/')
  await page.setViewportSize({ width: 1440, height: 900 })
  const shell = page.locator('.bn-shell')
  const brand = page.locator('.bn-side .bn-brand')

  await expect(shell).not.toHaveAttribute('data-rail', 'true')
  await brand.click()
  await expect(shell).toHaveAttribute('data-rail', 'true')
  // the label and the state follow, because the control is the same element in both states
  await expect(brand).toHaveAttribute('aria-label', 'Expand the sidebar')
  await expect(brand).toHaveAttribute('aria-expanded', 'false')

  await brand.click()
  await expect(shell).not.toHaveAttribute('data-rail', 'true')
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
 * anybody retuned --bn-ease, which is a change this assertion should survive.
 *
 * IT FOUND TWO MORE OF THE SAME DEFECT AFTER THE FIRST FIX LANDED, which is the argument for
 * keeping it rather than deleting it as a one-off:
 *
 *   - `.bn-side` was given `transition: padding` so the 12px -> 8px gutter cut would ride the
 *     column's own clock. But in the rail a nav link is a 48px box at `padding-left`, so its
 *     icon's centre IS `padding-left + 24` — easing the padding dragged it 33 -> 35.9 -> 32,
 *     three pixels right of both resting positions. The padding snaps now.
 *   - The FOOTER still centred its buttons against the animating column (`align-items: center`,
 *     the same shape as the nav's old `margin: 0 auto`) and measured 37 -> 103.8 -> 20.5. The
 *     first pass had fixed the brand and the nav and never looked below them.
 *
 * EIGHT SAMPLES, NOT THREE, and that is a fix rather than a preference: the padding overshoot
 * lived in the first ~80ms, so at three samples this test failed one run in three and passed the
 * other two on identical code. A mid-transition assertion that samples sparsely is not a weaker
 * test, it is a flaky one, and a flaky test gets deleted by the next person to meet it. */
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
      return {
        mark: box('.bn-side .bn-brand svg'),
        nav: box('.bn-side .bn-nav-link .bn-icon'),
        // THE FOOTER, which the first pass never looked at. Its rail rule was
        // `align-items: center`, the same class of defect as the nav's `margin: 0 auto`, and it
        // measured 37 -> 103.8 -> 20.5 while the brand and the nav above it were already clean.
        foot: box('.bn-side .bn-side-foot .bn-btn .bn-icon'),
      }
    })

  const open = await centres()
  expect(open.mark, 'the brand is drawn').not.toBeNull()
  expect(open.foot, 'the footer is drawn').not.toBeNull()

  await page.keyboard.press('Meta+Period')
  // EIGHT samples across the whole 320ms, deliberately not synchronised to any frame. Three was
  // not enough: the padding overshoot this test found lived in the first ~80ms and a run whose
  // first sample landed late walked straight past it, so the test failed one time in three and
  // passed the other two on the same code.
  const during: Array<Record<'mark' | 'nav' | 'foot', number | null>> = []
  for (let i = 0; i < 8; i++) {
    await page.waitForTimeout(40)
    during.push(await centres())
  }
  await page.waitForTimeout(400)
  const rail = await centres()

  // the corridor: every mid-flight sample sits between the two resting positions, with 2px of
  // slack for subpixel layout. Before the fix these read ~114 against a corridor of 31.5 to 36.
  for (const [i, s] of during.entries()) {
    for (const key of ['mark', 'nav', 'foot'] as const) {
      const a = open[key]!, b = rail[key]!, v = s[key]!
      const lo = Math.min(a, b) - 2, hi = Math.max(a, b) + 2
      expect(v, `sample ${i}: the ${key} left its spine — ${v} is outside ${lo}..${hi}`)
        .toBeGreaterThanOrEqual(lo)
      expect(v, `sample ${i}: the ${key} left its spine — ${v} is outside ${lo}..${hi}`)
        .toBeLessThanOrEqual(hi)
    }
  }
})
