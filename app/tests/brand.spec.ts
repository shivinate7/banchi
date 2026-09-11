import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from '@playwright/test'
import { sealEveryTest } from './shell'
import { BLOCK, PARAMS, ROMAN_TRACK_SOLVED } from '../src/kit/lockupGeometry'

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

  // ONE DRAWING. It was two — the lockup and a separate rail mark, crossfading — until the
  // generator was taught to emit both ends of the bracket at one topology. A second svg here is
  // that crossfade coming back, and it would look almost right, which is why this counts.
  await expect(brand.locator('.bn-brand-slot > svg')).toHaveCount(1)
  // the chevron is a HINT, not the control: the control is the whole 128 x 93 row, which is the
  // entire point of moving the affordance here.
  await expect(brand.locator('.bn-brand-chevron')).toHaveCount(1)

  // NOT THE ACCESSIBLE NAME OF ANYTHING, HERE. Standing alone at #/gallery the lockup carries
  // `role="img"` and a name, because it IS the word — but inside this button a named child would
  // announce the name twice over the control's own label, so this call site passes `decorative`.
  // The a11y tree is then identical either side of the collapse.
  const lockup = brand.locator('.bn-brand-lockup')
  await expect(lockup).toHaveAttribute('aria-hidden', 'true')
  await expect(lockup).not.toHaveAttribute('role', 'img')
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

/* THE COLLAPSE LANDS ON THE MARK'S OWN WIRE, AND THAT IS THE WHOLE RISK OF THE MORPH.
 *
 * Section 16 recorded a morph as impossible — "a ~600-point filled taper against a 52-byte stroked
 * wire" — and shipped two drawings crossfading instead. The claim was true of how the two were
 * EXPRESSED and false of what they are: both are one L, and `taperParts` emits that L at a fixed
 * 301 samples, so the mark's small cut is the same call with `tip = 1`. The generator now emits
 * both ends and refuses to write if its untapered end differs from `SMALL_BRACKET` by more than 2%
 * of inked pixels at 10x.
 *
 * WHAT THAT CANNOT SEE is the app: the geometry can be exactly the mark and still be drawn at the
 * wrong size, in the wrong place, or not reached at all. It already was — `base.css` gives every
 * svg `max-width: 100%`, so the slot closing to 32px rescaled the whole viewBox underneath the
 * morph and it landed at a QUARTER of the mark. Both resting states still looked plausible.
 *
 * So this reads `markGeometry.ts` off disk rather than retyping its numbers — the values are
 * generated and a copy here would be the defect this repo keeps finding — derives the ink box the
 * mark's wire must occupy at the rail's 32px, and measures the settled bracket against it. */
const MARK_GEOMETRY = resolve(dirname(fileURLToPath(import.meta.url)), '../src/kit/markGeometry.ts')

function markInkBox(px: number) {
  const src = readFileSync(MARK_GEOMETRY, 'utf8')
  const d = /SMALL_BRACKET = '([^']+)'/.exec(src)
  const w = /SMALL_STROKE = ([\d.]+)/.exec(src)
  if (!d || !w) throw new Error('markGeometry.ts has no SMALL_BRACKET / SMALL_STROKE')
  /* `M x yBottom V yTop A r r 0 0 1 xElbow yTop H xRight` in the mark's 100 x 100 box, parsed by
     SHAPE and not by counting numbers: an arc carries three FLAGS (`0 0 1`) that scan as numbers,
     so a bare number sweep puts `yTop` on a flag and quietly reads 0 — which is a height of 33.34
     against the real 22.94, and a test that fails for a reason that has nothing to do with the
     drawing. The twin is `rotate(180 50 50)`, so the PAIR runs from (x, yTop) to their mirrors;
     the stroke is added because a round cap puts half of it outside the geometry at each end and
     `getBoundingClientRect` measures ink. */
  const L = /^M([\d.-]+) ([\d.-]+)V([\d.-]+)A([\d.-]+) [\d.-]+ 0 0 1 ([\d.-]+) ([\d.-]+)H([\d.-]+)$/
    .exec((d[1] ?? '').trim())
  if (!L) throw new Error(`SMALL_BRACKET is not the vertical-elbow-horizontal L this reads: ${d[1]}`)
  const x = Number(L[1]!)
  const yTop = Number(L[6]!)
  const stroke = Number(w[1])
  return { w: ((100 - 2 * x + stroke) * px) / 100, h: ((100 - 2 * yTop + stroke) * px) / 100 }
}

test('the collapsed bracket is markGeometry.ts own wire, at the rail size', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await page.click('.bn-side .bn-brand')
  await page.waitForTimeout(700)

  const drawn = await page.locator('.bn-side .bn-lockup-bracket').evaluate((el) => {
    const r = el.getBoundingClientRect()
    return {
      w: r.width, h: r.height,
      // the morph must not have left a second drawing or a filter behind it
      svgs: el.closest('.bn-brand-slot')!.querySelectorAll('svg').length,
      filters: el.querySelectorAll('filter').length,
      tiles: el.closest('svg')!.querySelectorAll('rect').length,
    }
  })

  const want = markInkBox(32)
  // half a pixel: the assertion is that this IS the mark, not that it resembles it. Before the
  // `max-width` fix these read 4.7 x 5.7 against 18.87 x 22.94.
  expect(Math.abs(drawn.w - want.w), `settled bracket ${drawn.w.toFixed(2)}px wide, the mark is ${want.w.toFixed(2)}`).toBeLessThan(0.5)
  expect(Math.abs(drawn.h - want.h), `settled bracket ${drawn.h.toFixed(2)}px tall, the mark is ${want.h.toFixed(2)}`).toBeLessThan(0.5)

  expect(drawn.svgs, 'one drawing, not a crossfade between two').toBe(1)
  // Section 11: the marbling loses to a flat prism gradient at every size this app draws.
  expect(drawn.filters, 'the small cut carries no filter').toBe(0)
  // THE EMPTY SLOT, NOT THE APP ICON (section 1). `Logo` draws a superellipse tile and the card
  // inside it; this is the brackets with the card taken out.
  expect(drawn.tiles, 'the rail carries no tile and no card').toBe(0)
})

test('the bracket is one continuous path across the collapse, never two', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  const arm = page.locator('.bn-side .bn-lockup-arm').first()
  const open = await arm.getAttribute('d')

  await page.click('.bn-side .bn-brand')
  // mid-flight: the path must already be neither end. A crossfade would leave `d` untouched and
  // move opacity instead, which is exactly what shipped before and what this catches.
  await page.waitForTimeout(90)
  const mid = await arm.getAttribute('d')
  await page.waitForTimeout(700)
  const rail = await arm.getAttribute('d')

  expect(mid, 'the bracket did not move mid-collapse — it is being swapped, not morphed').not.toBe(open)
  expect(mid, 'the bracket jumped straight to the rail end').not.toBe(rail)
  expect(rail, 'the collapse ended where it started').not.toBe(open)
  // and the command structure never changes, which is what makes the lerp defined at all
  const shape = (d: string | null) => (d ?? '').replace(/-?\d+\.?\d*/g, '#')
  expect(shape(mid), 'the two ends are not the same topology').toBe(shape(open))
  expect(shape(rail), 'the two ends are not the same topology').toBe(shape(open))
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

test('the tile mark is fixed dark in both themes, and the brand frame is not', async ({ page }) => {
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

  test('the brand frame follows the app, not the system', async ({ page }) => {
    await page.goto('/')
    const inks = () =>
      page.evaluate(() => ({
        body: getComputedStyle(document.body).backgroundColor,
        bracket: getComputedStyle(document.querySelector('.bn-lockup-bracket')!).fill,
        kanji: getComputedStyle(document.querySelector('.bn-lockup-kanji')!).fill,
      }))

    // the app painting LIGHT while the machine asks for dark — the attribute is absent, which is
    // what `applyTheme` leaves behind, not `data-theme="light"`
    await page.evaluate(() => document.documentElement.removeAttribute('data-theme'))
    const light = await inks()
    expect(light.bracket, 'flat ink on light — a paint, not a gradient reference')
      .not.toContain('url(')
    // ONE DRAWING, so there is no second element to disagree — which is itself the fix. The
    // rail mark used to be its own component with its own copy of this switch.
    expect(light.bracket, 'the frame is the same ink as the type inside it').toBe(light.kanji)

    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
    const dark = await inks()
    expect(dark.bracket, "bluesteel's own chrome on dark").toContain('url(')
    expect(dark.kanji, 'and the type stays flat ink — only the frame carries metal').not.toContain('url(')
  })
})

/* THE CHEVRON IS THE ONE THING ON SCREEN SAYING THE BRAND COLLAPSES THE SIDEBAR, and it shipped
 * with no styling at all.
 *
 * The morph commit rewrote the CSS region `.bn-brand-chevron` sat inside and deleted its rule
 * block along with it. The element still rendered — as a bare `.bn-icon`: always at full ink, no
 * `margin-left: auto`, so it floated 12px off the frame in the middle of a 109px row instead of
 * sitting at the row's edge. `make check`, `make harness` and 407 browser specs were all green,
 * because the filmstrips never hovered and nothing in this suite asserted where it sits or how
 * loud it is. The operator found it by looking at the product.
 *
 * TWO CLAIMS, AND NEITHER SURVIVES THE DELETION. Position: pinned to the row's right edge, which
 * only `margin-left: auto` does. Volume: quiet at rest and full under the cursor — the owner chose
 * that over a hover-only reveal on 2026-09-06, because an affordance that must be discovered
 * before it can help is a poor way to announce the only control on the row. */
test('the chevron is quiet, and it is pinned to the row edge rather than floating', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')

  const read = () =>
    page.evaluate(() => {
      const c = document.querySelector<HTMLElement>('.bn-brand-chevron')!
      const row = document.querySelector('.bn-side .bn-brand')!.getBoundingClientRect()
      const box = c.getBoundingClientRect()
      const pad = parseFloat(getComputedStyle(document.querySelector('.bn-side .bn-brand')!).paddingRight)
      return {
        opacity: Number(getComputedStyle(c).opacity),
        // distance from the row's inner right edge: 0 means pinned, ~49 was the floating bug
        offEdge: row.right - pad - box.right,
      }
    })

  const rest = await read()
  // VISIBLE BUT SUBORDINATE. Both bounds matter: 0 is the hover-only treatment the owner did not
  // choose, and 1 is the regression's full-ink glyph beside a mark designed without one.
  expect(rest.opacity, 'the chevron is drawn at rest').toBeGreaterThan(0)
  expect(rest.opacity, 'and it is quieter than the mark beside it').toBeLessThan(1)
  expect(Math.abs(rest.offEdge), `the chevron is ${rest.offEdge.toFixed(1)}px off the row edge — it is floating, not pinned`)
    .toBeLessThan(1)

  await page.hover('.bn-side .bn-brand')
  await page.waitForTimeout(250)
  expect((await read()).opacity, 'and it comes up to full under the cursor').toBe(1)

  // GONE IN THE RAIL, not faded: 64px less two gutters leaves 48 and the mark takes 32.
  await page.click('.bn-side .bn-brand')
  await page.waitForTimeout(500)
  await expect(page.locator('.bn-brand-chevron')).toBeHidden()
})

/* THE TAB TITLE ALTERNATES, AND THE THREE PLACES IT MUST NOT.
 *
 * `Inventory · 番地 banchi` is twenty characters and a browser tab shows perhaps a dozen, so the
 * concatenation truncates and the half that survives is whichever came first. The owner asked for
 * the two to take turns instead. That is a `setInterval` on `document.title`, which is the kind of
 * thing that breaks quietly: a stale timer surviving a route change fights the new one, and a
 * cleanup that runs too eagerly leaves the tab frozen on one half. Neither shows up in a
 * screenshot and neither throws.
 *
 * THE EXEMPTIONS ARE THE POINT AS MUCH AS THE ALTERNATION. Home has nothing to alternate WITH —
 * the screen and the product are the same word. The Fulfiller's tab names his task, not whose
 * product it is. And `prefers-reduced-motion` falls back to the concatenation, because a title
 * that changes on a timer may be announced by a screen reader every time it changes, and that
 * query is how this product is told to stop moving things.
 *
 * THE SCREENS ARE READ OFF THE NAV, NOT TYPED. `make docs-audit`'s `route rosters` row refused an
 * earlier draft of this file for pinning four hashes, and it was right to: a list somebody typed
 * goes stale silently, and the route added next month is simply not in it. What these cases need
 * is not a roster but "some named screen" and "the Fulfiller's", and the sidebar knows both — his
 * link is the only `.bn-nav-link` it draws outside `<nav>`, which is the same structural fact
 * `cursor.spec.ts` harvests on. */
async function screens(page: import('@playwright/test').Page) {
  await page.goto('/#/')
  await expect(page.locator('.bn-side a.bn-nav-link').first()).toBeVisible()
  const found = await page.evaluate(() =>
    Array.from(document.querySelectorAll<HTMLAnchorElement>('.bn-side a.bn-nav-link')).map((a) => ({
      href: a.getAttribute('href') ?? '',
      label: (a.querySelector('.bn-nav-text') ?? a).textContent?.trim() ?? '',
      outsideNav: a.closest('nav') === null,
    })),
  )
  const named = found.find((r) => r.href !== '#/' && !r.outsideNav)
  const fulfiller = found.find((r) => r.outsideNav)
  expect(named, 'the sidebar drew no named screen to alternate on').toBeTruthy()
  expect(fulfiller, "the sidebar drew no link outside <nav> — the Fulfiller's has moved").toBeTruthy()
  return { named: named!, fulfiller: fulfiller! }
}

/* THE CLOCK IS FAKED AND ONLY EVER ADVANCED, WHICH IS A CHANGE TO THE WAIT AND NOT TO THE
 * ASSERTION (D136). These three cases were the suite's longest by a distance — 46.5s, 17.5s and
 * 17.0s on the runner, all of it `waitForTimeout` on a 6s + 4s cadence — and the owner ruled on
 * 2026-09-11 that a sleep on a real clock may become a fake one. `page.clock.install()` goes in
 * BEFORE the first navigation, with no fixed time: the page's clock starts at the real time and
 * keeps ticking at the real pace (measured, not assumed — a probe against 1.58 saw a 500ms
 * interval fire on schedule under it), so the 63 `toLocaleDateString` sites draw today. What
 * `runFor` adds is a jump: every timer and interval due inside the span fires, in order, with
 * `Date.now()` moving in step. The title timer is a chained `setTimeout`, so a jump of 500ms is
 * exactly one real 500ms to it. Same samples, same window, same expected set.
 *
 * MUTATION-TESTED, because a faked wait that stays green through a broken app is worse than the
 * sleep it replaced: with the first `setTimeout(flip, ...)` deleted from App.tsx the alternation
 * case fails on the sampled set, and with the effect's cleanup deleted the Home case fails on
 * `after` — the surviving timer keeps writing the old route's halves. */
test('the tab title alternates on a named screen, and holds still where it should', async ({ page }) => {
  await page.clock.install()
  const { named } = await screens(page)

  await page.goto(`/${named.href}`)
  await page.waitForTimeout(400)
  /* Sampled across more than one full cycle. The dwell is ASYMMETRIC — the screen holds longer
     than the name — so the window has to clear the sum of both, not twice the shorter one. Sixteen
     seconds at 500ms covers a 6s + 4s cycle with room for the machine to be slow, and it is
     deliberately not derived from the constants: a test that reads the value it is checking
     passes when that value is wrong. A fake clock advanced by an explicit number honours that
     just the same — the number is still this file's and not App.tsx's. */
  const seen = new Set<string>()
  for (let i = 0; i < 32; i++) { seen.add(await page.title()); await page.clock.runFor(500) }
  expect([...seen].sort(), 'the tab shows each half in turn, neither truncated into the other')
    .toEqual([named.label.toLowerCase(), '番地 banchi'].sort())

  // Home: one word for both the screen and the product, so nothing to take turns with
  await page.goto('/#/')
  await page.clock.runFor(8000)   // past the longer dwell, so a timer would have shown by now
  const home = await page.title()
  await page.clock.runFor(8000)
  expect(await page.title(), 'Home has nothing to alternate with and must hold still').toBe(home)
  expect(home).toBe('番地 banchi')

  // and the timer from the screen we just left must not have survived to fight this one
  const after = new Set<string>()
  for (let i = 0; i < 26; i++) { after.add(await page.title()); await page.clock.runFor(500) }
  expect([...after], 'a timer from the previous route is still running').toEqual(['番地 banchi'])

  /* THE TAB IS LOWERCASE AND THE NAV IS NOT, which is the whole shape of this change. The label
     is one string drawn by the sidebar, the palette and the keyboard sheet; lowercasing it at the
     source would have rewritten all three. Asserting the nav's casing here is what stops the
     cheap fix from passing. */
  expect(named.label, 'the nav keeps Title Case — only the tab speaks lowercase')
    .not.toBe(named.label.toLowerCase())
})

test("the Fulfiller's tab names his task, not the product", async ({ page }) => {
  await page.clock.install()   // two jumps past the longer dwell, to prove it does not move
  const { fulfiller } = await screens(page)
  await page.goto(`/${fulfiller.href}`)
  await page.clock.runFor(8000)
  const first = await page.title()
  await page.clock.runFor(8000)
  expect(first, 'his tab says what he is doing, lowercase like every other tab').toBe('cards to pull')
  expect(await page.title(), 'and it does not alternate at him').toBe(first)
})

/* `reducedMotion` is set on an explicit CONTEXT rather than through `test.use`, which this
   Playwright's fixture types do not accept it in. */
test('with reduced motion the tab stops taking turns and shows both at once', async ({ browser, baseURL }) => {
  const ctx = await browser.newContext({ reducedMotion: 'reduce', baseURL })
  const page = await ctx.newPage()
  await page.clock.install()   // a full cycle's worth of samples, to prove none of them differ
  const { named } = await screens(page)
  await page.goto(`/${named.href}`)
  await page.waitForTimeout(600)
  const seen = new Set<string>()
  for (let i = 0; i < 32; i++) { seen.add(await page.title()); await page.clock.runFor(500) }
  await ctx.close()
  expect([...seen], 'reduced motion gets one steady title, concatenated')
    .toEqual([`${named.label.toLowerCase()} · 番地 banchi`])
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

  const centers = () =>
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

  const open = await centers()
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
    during.push(await centers())
  }
  await page.waitForTimeout(400)
  const rail = await centers()

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

/* ---- the phone chrome (logo.md section 19) -------------------------------------------------
 *
 * THE SHELL SPOKE TWO BRANDS UNTIL 2026-09-07, and nothing here could tell. Every case above
 * sets a desktop viewport, `nav.spec.ts:35` scopes itself to `.bn-side` on purpose, and
 * `cursor.spec.ts` harvests its routes from `.bn-side a.bn-nav-link` — which is `display: none`
 * below 768, so that file cannot run at a phone width even in principle. The result was that the
 * desktop shell drew the lockup, the phone drew a `Logo` tile with a wordmark and a tagline
 * beside it, and 407 browser specs were green through all of it.
 */

const PHONE = { width: 390, height: 844 }

test('the phone bar draws the empty slot, at the rail size and never the tile', async ({ page }) => {
  await page.setViewportSize(PHONE)
  await page.goto('/')

  const drawn = await page.locator('.bn-topbar-brand .bn-lockup-bracket').evaluate((el) => {
    const r = el.getBoundingClientRect()
    const svg = el.closest('svg')!
    const read = (sel: string) => {
      const n = svg.querySelector(sel)
      return n === null ? null : Number(getComputedStyle(n).opacity)
    }
    return {
      w: r.width, h: r.height,
      svgs: el.closest('.bn-brand-slot')!.querySelectorAll('svg').length,
      tiles: svg.querySelectorAll('rect').length,
      kanji: read('.bn-lockup-kanji'),
      roman: read('.bn-lockup-roman'),
    }
  })

  /* THE SAME ASSERTION THE COLLAPSED SIDEBAR TAKES, at the same size. The bar is 52px tall and
     the lockup's floor is a 102 x 75 block, so this surface can only ever hold the rail's end —
     which is the arithmetic that keeps the lockup out of the 64px rail as well. */
  const want = markInkBox(32)
  expect(Math.abs(drawn.w - want.w), `bar bracket ${drawn.w.toFixed(2)}px wide, the mark is ${want.w.toFixed(2)}`).toBeLessThan(0.5)
  expect(Math.abs(drawn.h - want.h), `bar bracket ${drawn.h.toFixed(2)}px tall, the mark is ${want.h.toFixed(2)}`).toBeLessThan(0.5)

  expect(drawn.svgs, 'one drawing in the bar, not a crossfade between two').toBe(1)
  // THE EMPTY SLOT, NOT THE APP ICON (section 1). A `Logo` here draws a superellipse tile and
  // the card inside it — which is what this bar carried until section 19, and what sank into
  // the bar on dark.
  expect(drawn.tiles, 'the phone bar carries no tile and no card').toBe(0)
  // the type is off because `--bn-brand-open` is 0 here, not because anything hid it
  expect(drawn.kanji, 'the kanji is not drawn in the railed bar').toBe(0)
  expect(drawn.roman, 'the roman is not drawn in the railed bar').toBe(0)
})

test('the phone drawer draws the lockup, and no wordmark or tagline beside it', async ({ page }) => {
  await page.setViewportSize(PHONE)
  await page.goto('/')
  await page.getByText('More', { exact: true }).click()
  await expect(page.locator('.bn-drawer')).toBeVisible()
  await page.waitForTimeout(500)

  const lockup = page.locator('.bn-drawer .bn-brand-lockup')
  // section 19 settled kanji 40 — the sidebar's own number, drawn at 390 and 320 in both themes
  // against 32 before it was taken. A 128 x 93 block in ~268px of usable drawer width.
  await expect(lockup).toHaveAttribute('width', '127.6')
  await expect(lockup).toHaveAttribute('height', '93.2')
  // and it is the OPEN end here: the drawer is the sidebar at this width, not the rail
  await expect(page.locator('.bn-drawer .bn-lockup-kanji')).toHaveCSS('opacity', '1')

  /* THE LOCKUP REPLACES THE MARK, THE WORDMARK AND THE TAGLINE TOGETHER (section 16, extended by
     section 19). This drawer was the last place `every card has an address` was drawn; the three
     classes it needed are deleted from App.css, so these count anywhere in the document and not
     merely inside the drawer. */
  await expect(page.locator('.bn-brand-name')).toHaveCount(0)
  await expect(page.locator('.bn-brand-tag')).toHaveCount(0)
  await expect(page.getByText('every card has an address')).toHaveCount(0)

  // the sidebar's server line, count and all — it said only `Server online` here until section 19
  await expect(page.locator('.bn-drawer .bn-server .bn-server-detail')).toContainText('cards')
})

test('every lockup the product draws clears the size floor', async ({ page }) => {
  /* SECTION 15 ASKED FOR THIS AND NOTHING BUILT IT. "app/tests/brand.spec.ts gains the floor — a
     lockup below kanji 32 must not render." Section 11 measured why: 番's counters read 1.07 at
     32 and 0.87 at 26, so the kanji fills in before the bracket gives out.
     WHAT THIS CASE CAN AND CANNOT SEE. The refusal itself is `Lockup`'s own early return and
     there is no render harness in this suite to call it with an arbitrary size — Playwright only
     ever sees what a screen mounts. So this asserts the arm that a browser CAN answer, and it is
     the arm that regresses: a new call site drawn too small. Every lockup on every surface, at
     every width, is at or above the floor's own block. */
  for (const [w, h] of [[1440, 900], [390, 844]] as const) {
    await page.setViewportSize({ width: w, height: h })
    for (const hash of ['/', GALLERY]) {
      await page.goto(hash)
      if (w < 768 && hash === '/') await page.getByText('More', { exact: true }).click()
      await page.waitForTimeout(400)
      const sizes = await page.locator('.bn-lockup').evaluateAll((els) =>
        els.map((el) => Number(el.getAttribute('width'))))
      expect(sizes.length, `${hash} at ${w} draws no lockup at all`).toBeGreaterThan(0)
      for (const drawn of sizes) {
        // 32 * BLOCK.w / BLOCK.ref = 102.08, the narrowest block the floor permits
        expect(drawn, `${hash} at ${w} drew a lockup ${drawn}px wide, under the floor's 102.08`)
          .toBeGreaterThanOrEqual(102)
      }
    }
  }
})

test('the phone wordmark is the lockup roman, set as text', async ({ page }) => {
  /* IT WAS THE RIGHT FACE IN THE WRONG VOICE. `Banchi` in Manrope 700 at 16px, sentence case, no
     tracking, full ink — beside a mark whose own name is drawn in caps at 45% with the tracking a
     width-match solved for. The owner asked for the bar's word to BE that roman, so every value
     here comes off `lockupGeometry.ts` and none of it is typed into a stylesheet.
     WHAT THIS CATCHES is the copy drifting from the drawing: the generator can re-solve the
     tracking, or §13 can move `romanSize`, and a hand-typed em in App.css would go on saying the
     old number with nothing to contradict it. */
  await page.setViewportSize(PHONE)
  await page.goto('/')

  const mark = page.locator('.bn-topbar-wordmark')
  const seen = await mark.evaluate((el) => {
    const cs = getComputedStyle(el)
    return {
      text: el.textContent,
      transform: cs.textTransform,
      /* THE FIRST FAMILY IN THE STACK, WITHOUT `split(',')` — `app/eslint.config.js` bans that
         call outright as v1's CSV bug, and an inline disable on a guard is how a guard stops
         being one. A font stack is not a CSV row, but it is also one regex away from not
         needing the exemption. */
      family: (/^\s*["']?([^,"']+)/.exec(cs.fontFamily)?.[1] ?? '').trim(),
      weight: cs.fontWeight,
      trackPx: Number.parseFloat(cs.letterSpacing),
      sizePx: Number.parseFloat(cs.fontSize),
      opacity: Number(cs.opacity),
    }
  })

  // THE DOM KEEPS THE WORD. `text-transform` rather than a capitalised string, so find-in-page
  // finds `Banchi` and a screen reader is not handed six letters to spell out.
  expect(seen.text, 'the DOM text is the word, not the caps').toBe('Banchi')
  expect(seen.transform).toBe('uppercase')

  // Manrope 700 is what `scripts/build-lockup.mjs` outlines the roman in — its own header says so.
  expect(seen.family).toBe('Manrope')
  expect(seen.weight).toBe('700')

  /* THE TRACKING IS THE SOLVED ONE, CONVERTED. `ROMAN_TRACK_SOLVED` is a fraction of the KANJI's
     size and `letter-spacing` is a fraction of the element's own, so the em is the ratio of the
     two. Half a pixel, because the assertion is that this IS the drawing's tracking rather than
     that it resembles it. */
  const wantEm = ROMAN_TRACK_SOLVED / PARAMS.romanSize
  expect(
    Math.abs(seen.trackPx - wantEm * seen.sizePx),
    `the wordmark tracks ${seen.trackPx.toFixed(2)}px against the roman's ${(wantEm * seen.sizePx).toFixed(2)}`,
  ).toBeLessThan(0.5)

  expect(seen.opacity, 'the roman is drawn at section 13’s own opacity').toBeCloseTo(PARAMS.romanOpacity, 3)

  /* AND THE WORD IS THE ONLY THING IN THE BAR THAT GROWS, which is why no negative margin is
     needed for the trailing letter's tracking — asserted here so the reasoning in App.css has a
     reader, and so that right-aligning this word later fails loudly rather than quietly leaving
     5.8px of air after the I. */
  const grows = await mark.evaluate((el) => getComputedStyle(el).flexGrow)
  expect(grows, 'the wordmark fills the bar, so its trailing tracking is invisible').toBe('1')
})

/* THE DRAWER ON A SHORT SCREEN (logo.md section 19, amended) --------------------------------
 *
 * A phone in Safari gets about 90px less than its own height, and the lockup's head is 61px
 * taller than the wordmark block it replaced. Measured at 390 x 754 — an iPhone 14 with the
 * toolbars up — the nav ran 85px past the fold and showed 7 of its 9 rows.
 *
 * THE OWNER RULED TO SHRINK THE GROUP HEADINGS RATHER THAN DROP THEM. Both were built and drawn
 * side by side; dropping them was one rule and 85px, keeping them costs five and lands the
 * drawer's own lockup at kanji 34. This case is what stops the five drifting back apart.
 *
 * AMENDED BY D134'S TENTH ROW: the iPhone 14 no longer fits nine rows' worth of arithmetic
 * shrunk down to eight rows plus headroom — it fits ten rows at the 40px floor instead, the
 * same step the mini already needed (see App.css and the case below). This case still measures
 * the SAME fold — headings, lockup, and every row reachable without scrolling — it is the row
 * height itself, asserted next door, that moved.
 */
const SHORT_PHONE = { width: 390, height: 754 }

test('the drawer fits an iPhone in Safari, with its headings intact', async ({ page }) => {
  await page.setViewportSize(SHORT_PHONE)
  await page.goto('/')
  await page.getByText('More', { exact: true }).click()
  await expect(page.locator('.bn-drawer')).toBeVisible()
  await page.waitForTimeout(400)

  const seen = await page.evaluate(() => {
    const drawer = document.querySelector('.bn-drawer')!
    const nav = drawer.querySelector('.bn-nav')!
    const box = nav.getBoundingClientRect()
    const links = [...drawer.querySelectorAll('.bn-nav a.bn-nav-link')]
    return {
      overflow: nav.scrollHeight - nav.clientHeight,
      shown: links.filter((l) => {
        const r = l.getBoundingClientRect()
        return r.top >= box.top - 1 && r.bottom <= box.bottom + 1
      }).length,
      total: links.length,
      headings: drawer.querySelectorAll('.bn-nav-group-label').length,
      lockup: Number(drawer.querySelector('.bn-lockup')!.getAttribute('width')),
    }
  })

  // every screen the drawer offers is on the screen, with nothing to scroll to reach it
  expect(seen.overflow, `the nav runs ${seen.overflow}px past the fold`).toBeLessThanOrEqual(0)
  expect(seen.shown, `${seen.shown} of ${seen.total} rows are on screen`).toBe(seen.total)

  // AND THE HEADINGS SURVIVED, which is the whole reason this is five rules and not one
  expect(seen.headings, 'the four groups still name themselves').toBeGreaterThan(2)

  // kanji 34 — 34 * BLOCK.w / BLOCK.ref
  expect(seen.lockup, 'the drawer draws the short-screen lockup').toBeCloseTo((34 * BLOCK.w) / BLOCK.ref, 0)
})

test('the second step reaches the mini and the iPhone 14, and stops short of a taller phone', async ({ page }) => {
  /* D134's TENTH ROW MOVED WHAT THIS STEP HAS TO REACH. It used to stop short of the iPhone 14
     at 754 on purpose — that phone fit nine rows at 44 with nothing to spare. A tenth row costs
     every phone in this family one more 44px row than the arithmetic had, and 754 no longer
     "already fits": ten rows at 44 measured 41px over, and ten at the 40px floor measured 0. So
     the step's own boundary moved to 754 (see App.css), and this case moved with it. */
  await page.setViewportSize(SHORT_PHONE)
  await page.goto('/')
  await page.getByText('More', { exact: true }).click()
  await expect(page.locator('.bn-drawer')).toBeVisible()
  await page.waitForTimeout(400)

  const iphone14 = await page.evaluate(() => {
    const nav = document.querySelector('.bn-drawer .bn-nav')!
    return {
      overflow: nav.scrollHeight - nav.clientHeight,
      row: Math.round(document.querySelector('.bn-drawer .bn-nav a.bn-nav-link')!.getBoundingClientRect().height),
    }
  })
  expect(iphone14.overflow, `the iPhone 14's nav runs ${iphone14.overflow}px past the fold`).toBeLessThanOrEqual(0)
  expect(iphone14.row, 'the rows sit ON the thumb floor at 754, not at 44').toBe(40)

  /* THE MINI GENUINELY DOES NOT FIT TEN ROWS AT THE FLOOR, AND THAT IS THE HONEST ANSWER. 375 x
     722 needs more than ten rows at 40 plus the head, the foot and three headings leave room
     for — 29px short, measured — and there is no third step: the next one would break the thumb
     floor CLAUDE.md sets. What covers it is the fade-scroll fallback already built for a phone
     this cannot reach at all (the iPhone SE, below), now doing the same job one family up: the
     row is on the floor, the list scrolls, and the scroll-driven mask says there is more. */
  await page.setViewportSize({ width: 375, height: 722 })
  await page.goto('/')
  await page.getByText('More', { exact: true }).click()
  await page.waitForTimeout(400)

  const mini = await page.evaluate(() => {
    const nav = document.querySelector('.bn-drawer .bn-nav')!
    const links = [...document.querySelectorAll('.bn-drawer .bn-nav a.bn-nav-link')]
    return {
      overflow: nav.scrollHeight - nav.clientHeight,
      total: links.length,
      row: Math.round(links[0]!.getBoundingClientRect().height),
      scrollable: getComputedStyle(nav).overflowY === 'auto' || getComputedStyle(nav).overflowY === 'scroll',
    }
  })
  expect(mini.row, 'the rows sit ON the thumb floor, not under it').toBe(40)
  expect(mini.overflow, 'the mini genuinely does not fit ten rows at the floor').toBeGreaterThan(0)
  expect(mini.scrollable, 'what does not fit scrolls, rather than clipping silently').toBe(true)
  // every row is still reachable, just not without scrolling
  await page.locator('.bn-drawer .bn-nav a.bn-nav-link').last().scrollIntoViewIfNeeded()
  await expect(page.locator('.bn-drawer .bn-nav a.bn-nav-link').last()).toBeVisible()

  // AND A TALLER PHONE IS UNTOUCHED, which is the half a threshold gets wrong when it is placed
  // by feel rather than by where the arithmetic actually changes.
  await page.setViewportSize({ width: 390, height: 900 })
  await page.goto('/')
  await page.getByText('More', { exact: true }).click()
  await page.waitForTimeout(400)
  const tall = await page.locator('.bn-drawer .bn-nav a.bn-nav-link').first()
    .evaluate((el) => Math.round(el.getBoundingClientRect().height))
  expect(tall, 'a phone with room to spare keeps its 44px rows').toBe(44)
})

test('a tall phone keeps the full lockup, because it has the room', async ({ page }) => {
  /* THE CONDITION IS HEIGHT AND NOT WIDTH, and this is what says so: a Pro Max is a phone, gets
     the drawer, and has no reason to give up 6px of brand. Without the height arm this case
     draws 34 and fails. */
  await page.setViewportSize({ width: 430, height: 842 })
  await page.goto('/')
  await page.getByText('More', { exact: true }).click()
  await expect(page.locator('.bn-drawer')).toBeVisible()
  await page.waitForTimeout(400)

  const lockup = await page.locator('.bn-drawer .bn-lockup').evaluate((el) => Number(el.getAttribute('width')))
  expect(lockup, 'a tall phone draws the sidebar’s own kanji 40').toBeCloseTo((40 * BLOCK.w) / BLOCK.ref, 0)
})
