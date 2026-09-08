import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

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

test('the tab title alternates on a named screen, and holds still where it should', async ({ page }) => {
  /* A LONGER BUDGET, AND IT IS THE CADENCE THAT NEEDS IT. One cycle is now 6s + 4s, and a case
     that proves alternation has to watch more than one of them — then prove the timer STOPPED,
     which means waiting past the longer dwell twice. That sums past Playwright's 30s default.
     Set explicitly rather than raised globally: every other spec in this suite should still fail
     fast, and a default nudged up to suit one file hides a hang in all of them. */
  test.setTimeout(90_000)
  const { named } = await screens(page)

  await page.goto(`/${named.href}`)
  await page.waitForTimeout(400)
  /* Sampled across more than one full cycle. The dwell is ASYMMETRIC — the screen holds longer
     than the name — so the window has to clear the sum of both, not twice the shorter one. Sixteen
     seconds at 500ms covers a 6s + 4s cycle with room for the machine to be slow, and it is
     deliberately not derived from the constants: a test that reads the value it is checking
     passes when that value is wrong. */
  const seen = new Set<string>()
  for (let i = 0; i < 32; i++) { seen.add(await page.title()); await page.waitForTimeout(500) }
  expect([...seen].sort(), 'the tab shows each half in turn, neither truncated into the other')
    .toEqual([named.label.toLowerCase(), '番地 banchi'].sort())

  // Home: one word for both the screen and the product, so nothing to take turns with
  await page.goto('/#/')
  await page.waitForTimeout(8000)   // past the longer dwell, so a timer would have shown by now
  const home = await page.title()
  await page.waitForTimeout(8000)
  expect(await page.title(), 'Home has nothing to alternate with and must hold still').toBe(home)
  expect(home).toBe('番地 banchi')

  // and the timer from the screen we just left must not have survived to fight this one
  const after = new Set<string>()
  for (let i = 0; i < 26; i++) { after.add(await page.title()); await page.waitForTimeout(500) }
  expect([...after], 'a timer from the previous route is still running').toEqual(['番地 banchi'])

  /* THE TAB IS LOWERCASE AND THE NAV IS NOT, which is the whole shape of this change. The label
     is one string drawn by the sidebar, the palette and the keyboard sheet; lowercasing it at the
     source would have rewritten all three. Asserting the nav's casing here is what stops the
     cheap fix from passing. */
  expect(named.label, 'the nav keeps Title Case — only the tab speaks lowercase')
    .not.toBe(named.label.toLowerCase())
})

test("the Fulfiller's tab names his task, not the product", async ({ page }) => {
  test.setTimeout(60_000)   // two waits past the longer dwell, to prove it does not move
  const { fulfiller } = await screens(page)
  await page.goto(`/${fulfiller.href}`)
  await page.waitForTimeout(8000)
  const first = await page.title()
  await page.waitForTimeout(8000)
  expect(first, 'his tab says what he is doing, lowercase like every other tab').toBe('cards to pull')
  expect(await page.title(), 'and it does not alternate at him').toBe(first)
})

/* `reducedMotion` is set on an explicit CONTEXT rather than through `test.use`, which this
   Playwright's fixture types do not accept it in. */
test('with reduced motion the tab stops taking turns and shows both at once', async ({ browser, baseURL }) => {
  test.setTimeout(60_000)   // a full cycle's worth of samples, to prove none of them differ
  const ctx = await browser.newContext({ reducedMotion: 'reduce', baseURL })
  const page = await ctx.newPage()
  const { named } = await screens(page)
  await page.goto(`/${named.href}`)
  await page.waitForTimeout(600)
  const seen = new Set<string>()
  for (let i = 0; i < 32; i++) { seen.add(await page.title()); await page.waitForTimeout(500) }
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
