import { test, expect, type Locator, type Page } from '@playwright/test'
import { createRequire } from 'node:module'
import { sealEveryTest } from './shell'
import { settleMotion } from './motionSettled'

/* THE ROW SHAPES `#/gallery` DRAWS THAT NOTHING ELSE IN THIS APP EVER DRAWS.
 *
 * DEBT5's remaining half: the kit sheet is "rendered by the build so it cannot go
 * stale", and it renders `CardLocations` — but until this file existed its fixture group held
 * four copies that were all LOCATED and all carried a slot number. Two of that component's four
 * row shells were therefore reachable in the product and unreachable on the sheet:
 *
 *   - the DEPARTED row (`is-gone is-nobar`), the shell a sold or retired copy gets once
 *     `server.ts:isDeparted` is true of its place — a null slot beside a real
 *     `join.departed_label`. The sheet's sold specimen inherited `slot: 40` from the base
 *     fixture, so `isDeparted` was false for it and this shell was drawn nowhere.
 *   - the POOLED row (`is-nobar`, `located: false`), D24's count-with-no-place.
 *
 * A SPECIMEN THAT IS NEVER RENDERED IS NOT A SPECIMEN, and the failure mode is the quiet one
 * this repo keeps a document about: the sheet stays green, `make screenshot` renders a page with
 * no departed row on it, and nobody looking at that page can tell the shell has stopped existing.
 * So the fixture gained the two rows and this file asserts they are actually on the page.
 *
 * WHY THIS IS A BROWSER ASSERTION AND NOT A `scripts/docs-audit.py` ROW. The condition under
 * test is `isDeparted(place) && state === 'sold'` resolved by React against a TypeScript fixture.
 * A Python row could only re-implement that predicate over the literal in `Gallery.tsx` — and it
 * would then go green over a fixture that renders nothing at all, which is exactly the vacuous
 * green docs/DEBTS.md warns about. Only the DOM can say the shell was drawn.
 *
 * OBSERVED RED BEFORE IT WAS KEPT. Mutation: give `Gallery.tsx`'s `DEPARTED` fixture a numeric
 * `slot`. `isDeparted` goes false, `noBar` goes false, both classes drop, and the first case
 * below reports 0 where it wants 1.
 *
 * NOT A HARNESS TEST AND MUST NOT BECOME ONE. `docs/GATES.md`'s contract is nine Python tests at
 * the Stop hook; this starts a browser. `make design-check` runs it.
 */

/* The hash form verbatim, for the reason every other spec in this directory records: a
   path-style '/gallery' is served index.html by Vite, mounts the app with an empty hash and
   renders HOME — a passing navigation to the wrong view. */
const GALLERY = '/#/gallery'

/** The departed shell. `is-gone` AND a lens that says so: `is-gone` alone is any sold copy —
 *  including one sold out of a box it is still sitting in — and `data-gone` on the lens is the
 *  row's own statement that this copy has left, which is what `isDeparted` decides.
 *
 *  IT WAS `.is-gone.is-nobar` UNTIL D118, and the pair meant the same thing for a reason that
 *  has since been repealed: a departed row drew no bar at all (D68), so having none was how you
 *  recognised one. That absence was 20px of row height arriving on the press that sold the copy,
 *  which moved every row beneath it — so the lens stays now and its MARK is what leaves. The
 *  conjunction is still what is under test; one half of it has a new spelling. */
const DEPARTED_ROW = '.card-locations-row.is-gone:has(.position-bar[data-gone])'

/** A row with no bar that has NOT left — the pooled copy, and only the pooled copy since D119. */
const NOBAR_PRESENT = '.card-locations-row.is-nobar:not(.is-gone)'

/** Page-wide and not scoped to the owner specimen, deliberately. `CardLocations`'s Fulfiller
 *  skin renders `.card-locations-copy` and no `.card-locations-row` at all, so a page-wide count
 *  is the stronger claim: exactly one departed row shell exists anywhere on this sheet. If the
 *  Fulfiller's skin ever started emitting owner row classes, that is a defect and this notices. */
/* NOTHING HERE MAY REACH THE CAPTURE SERVER. This file registers no fixtures of its own, so it
   takes the shared small store — `app/tests/shell.ts` carries the argument for both halves. The
   call has to sit above every hook and every case, which `make docs-audit`'s `spec seal` row
   checks: the navigation below happens inside a hook, and a seal declared under it would be
   installed after the requests it exists to catch.  */
sealEveryTest({ store: true })

test.beforeEach(async ({ page }) => {
  await page.goto(GALLERY)
  await expect(page.locator('[data-kit-section="locations"]')).toBeVisible()
})

test('the departed row shell is drawn', async ({ page }) => {
  await expect(page.locator(DEPARTED_ROW)).toHaveCount(1)
})

test('the departed row says one state and offers no action', async ({ page }) => {
  const row = page.locator(DEPARTED_ROW)

  /* NO PILL (S2, round 2, `CardLocations.tsx`'s own comment on this span): a departed copy's
     state pill was deleted outright, not merely hidden for the current row — the struck
     figure `PositionLabel` draws is this row's own mark, in past tense
     (`data-departed`/`aria-label="Was at …"`, `PositionLabel.tsx`), and pairing it with a
     second, present-tense "Sold" pill said the same fact twice in two tenses. This case
     asserted the pre-S2 pill until this round: `git show 0ebe59cf:app/src/CardLocations.tsx`
     already carried the exclusion, so the code was already this way three rounds ago and the
     case was simply never run against it (`gallery.spec.ts` was outside round 2's own
     design-check scope) — not a regression this lane's own round 3-5 work introduced. */
  const pills = row.locator('.card-locations-state .bn-pill')
  await expect(pills).toHaveCount(0)
  const mark = row.locator('.card-locations-label [data-departed="true"]').first()
  await expect(mark).toHaveAttribute('data-departed', 'true')
  await expect(mark).toHaveAttribute('aria-label', /^Was at /)

  /* AND NOTHING WHERE AN ACTION WOULD BE. `Mark sold` on a copy that is already gone is the
     press this component refuses to offer, and the state pill beside it has already said so —
     `CardLocations.tsx` renders null rather than a disabled control or a second word.

     THE SLOT IS STILL THERE, EMPTY, AND THAT IS D118 rather than a leak: the cell holds its
     137x28 whether or not it has a control in it, because a slot that collapses when its button
     becomes a result slides everything beside it. Empty TEXT is the claim; a zero-width box
     never was. */
  await expect(row.locator('.card-locations-action')).toHaveText('')
  const slot = await row.locator('.card-locations-action').boundingBox()
  expect(slot?.width ?? 0, 'the action slot keeps its width with nothing in it').toBeGreaterThanOrEqual(137)
})

test('the pooled row is the only no-bar shell that has not left', async ({ page }) => {
  /* ONE, not two. The copy the walk stands on used to be the second — its lens was drawn in the
     location card above the list — and D119 gave it a bar like every other row. A pooled copy is
     now the only row that carries no bar without having left the box, and the count is asserted
     so a fixture that quietly loses it is caught. */
  await expect(page.locator(NOBAR_PRESENT)).toHaveCount(1)

  /* The pooled one names itself. `.card-locations-boxname` is rendered only by the pooled branch
     of `OwnerRows` — a located row puts the box's name inside `PositionLabel`'s note instead —
     so this is the pooled shell and not a lookalike. */
  const pooled = page.locator(`${NOBAR_PRESENT}:has(.card-locations-boxname)`)
  await expect(pooled).toHaveCount(1)
  await expect(pooled.locator('.card-locations-boxname')).toContainText('pooled')

  /* AND NO POSITION LABEL ANYWHERE ON IT (D24). A pool has no coordinate; a row that fell back
     to `box/index` would print a slot number for a card that is in no slot, which is the one
     thing that ruling forbids. */
  await expect(pooled.locator('.position-parts')).toHaveCount(0)
})

test('the current row is drawn, and it is a row like every other', async ({ page }) => {
  /* `currentKey` is passed to the owner specimen so the `is-current` treatment is on the sheet
     too — a marker and a rail saying where the walk stands, and a statement about the walk
     rather than about the card. */
  const current = page.locator('.card-locations-row.is-current')
  await expect(current).toHaveCount(1)
  await expect(current).toHaveAttribute('aria-current', 'true')
  await expect(current.locator('.card-locations-viewing')).toHaveText('Viewing')

  /* AND IT DRAWS A BAR (D119). This is the assertion the retitle is for: `is-current` is a
     marker on an ORDINARY row now, not a third reason to carry no bar. The specimen's current
     copy sits in an open box and has a slot to draw. */
  await expect(current.locator('.position-bar')).toHaveCount(1)
  await expect(current).not.toHaveClass(/is-nobar/)
})

/** A path-led specimen on the kit sheet — the flow `PositionLabel.css`'s re-rank fires under. */
const PATH_LED = ".kit-poslabel:has(.position-parts[data-lead='path'])"

test('a label with no figure re-ranks its path, and a live one does not (D71)', async ({ page }) => {
  /* THE SITE THIS MOVED FROM IS GONE. It was asserted on `#/inventory`'s location card until
     D119 deleted that card, and after the deletion NO screen in this product renders a
     `lead='path'` label with a void in it — the copies list, the order picker and the walk are
     all `lead='slot'`, and `PositionLabel.css`'s re-rank fires under `path` alone. The rule
     survives with this sheet as its only renderer, which is exactly the condition CLAUDE.md
     calls an exception with no reader: assert it here or nowhere.

     The two specimens sit side by side in the `position-label` section at one inline size, so
     the comparison is between the rule and nothing else. */
  const size = (sel: string) =>
    page.locator(sel).evaluate((node) => Number.parseFloat(window.getComputedStyle(node).fontSize))
  /* BOTH SPECIMENS PINNED TO `lead='path'`, so the only thing that differs between them is the
     void. The sheet draws a slot-led live label too, and comparing against that one would be a
     measurement of the LEAD as much as of the re-rank — which is the rule's own condition and
     not a control for it. */
  const departed = await size(`${PATH_LED}:has(.position-void) .position-path`)
  const live = await size(`${PATH_LED}:not(:has(.position-void)) .position-path`)
  expect(
    departed,
    `a departed path at ${departed}px is drawn in a live label's metadata register`,
  ).toBeGreaterThan(live)
})

/* THE SPECIMEN IS DRAWN IN THE LAYOUT THE PRODUCT DRAWS, AND UNTIL 2026-09-05 IT WAS NOT.
 *
 * `CardLocations.css` answers to `@container copies` in four places, and the widest of them is
 * not the interesting one: `(max-width: 619px)` is the whole narrow layout — the address on its
 * own line with the state and the action beneath it — which that file's comment calls "most of
 * the time, because the pane is one column of a three-column screen".
 *
 * `container-name: copies` was established in exactly ONE place in this app, `Inventory.css`'s
 * `.inventory-detail`. This sheet is not inside it. So every one of those four rules was dead
 * here and the specimen drew the base grid at every width — measured at 390, where the address
 * collapsed to one word a line and `ME01 commons` clipped to `M…`. The row was on the page and
 * it was the wrong row, which is the failure this whole file exists to catch one level up.
 *
 * OBSERVED RED BEFORE IT WAS KEPT. Mutation: drop `container-name: copies` from `.kit-copies` in
 * `Gallery.css`. The query stops matching, the computed areas fall back to the base
 * `"place state action" / "bar bar bar"`, and this reports that string instead.
 *
 * The viewport is set here rather than in the config because it is the thing under test: this
 * case is about what happens to the specimen when its container is narrow, and every other case
 * in this file is about what is in the DOM at any width.
 */
test('the copies specimen answers to its own width, as the screen does', async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 900 })

  const row = page.locator('.card-locations-owner .card-locations-row').first()
  await expect(row).toBeVisible()

  /* Under 620px the container query rewrites the grid. Comparing the resolved areas rather than
     asserting a class is what makes this a statement about the CASCADE — a class can be present
     while the rule that reads it never matches, and that is precisely the defect. */
  const areas = await row.evaluate((el) => getComputedStyle(el).gridTemplateAreas)
  expect(areas).toBe('"place place" "state action" "bar bar"')
})

/* THE SHEET'S IMAGERY IS THE SHEET'S, AND UNTIL 2026-09-06 IT WAS THE OWNER'S STORE'S.
 *
 * `Gallery.tsx`'s fixture gives four copies `has_photo: true`, and `CardLocations`'s Fulfiller
 * skin drew each one as `photoUrl(box, index)` — `GET /photo/<box>/<index>` on the capture port.
 * So the kit sheet showed whatever was in box 3 slot 40, box 7 slot 12, box 4 slot 1 and box 3
 * slot 31 of whichever store was up, and showed different cards as those boxes changed. The
 * page whose entire purpose is being compared against a reference was the one page whose
 * contents nobody could reproduce, and a pooled capture's photograph is a live code card (D24)
 * that `make screenshot` would have written into `captures/ui/`.
 *
 * WHY THE SEAL ALONE DOES NOT PROVE THIS. `app/tests/shell.ts`'s `stubStore` answers
 * `/photo/<box>/<index>` with an inline SVG, so the catch-all never fires for it and every case
 * above went green over a component that was asking. Reading the `src` back off the DOM is the
 * assertion that survives the stub — and the check it makes is the one that matters, since a
 * screenshot run has no Playwright in it at all. (Proof of the other half, once, by hand:
 * delete that stub and the whole file still passes, because nothing asks any more.)
 *
 * WHY THIS IS NOT SATISFIED BY `has_photo: false` ON THE FOUR. That is the one-line version and
 * it deletes the photo-bearing shell from the sheet, which is the trade this entire file exists
 * to refuse for the departed and pooled rows. So the count is asserted in both directions: four
 * images and two missing-photo sentences, the two shells the skin can draw.
 *
 * OBSERVED RED BEFORE IT WAS KEPT. Mutation: drop `photoSrc` from the fulfiller specimen in
 * `Gallery.tsx`. `src` reverts to the capture origin, the `data:` assertion reports
 * `http://localhost:<capture>/photo/3/40`, and `naturalWidth` goes to whatever the stub served.
 */
const PHOTO = '.card-locations-fulfiller .card-locations-photo'

test('every photograph on the sheet is its own specimen, not a stored capture', async ({
  page,
}) => {
  const photos = page.locator(PHOTO)

  /* FOUR, BECAUSE FOUR FIXTURE COPIES CARRY `has_photo: true`. A count rather than a
     `toBeVisible` so that buying a closed sheet by emptying the fixture fails here. */
  await expect(photos).toHaveCount(4)

  /* AND THE OTHER SHELL IS STILL DRAWN BESIDE IT — the two copies with no photograph. Both
     states are on the page or neither is specified. */
  await expect(
    page.locator('.card-locations-fulfiller .card-locations-copy').filter({
      hasText: 'The photo is missing.',
    }),
  ).toHaveCount(2)

  /* NOTHING ADDRESSES THE PHOTO SERVICE. `/photo/` is the literal `server.ts:photoUrl` mints,
     and the same shape `scripts/docs-audit.py`'s `views opsec` row refuses in the manifest. */
  const sources = await photos.evaluateAll((nodes) =>
    nodes.map((node) => (node as HTMLImageElement).getAttribute('src') ?? ''),
  )
  expect(sources).toHaveLength(4)
  for (const src of sources) {
    expect(src.startsWith('data:image/svg+xml')).toBe(true)
    expect(src).not.toContain('/photo/')
  }

  /* AND THE SPECIMEN ACTUALLY DECODED. A bundled image that fails to parse draws a broken
     shell, `onError` moves the copy into `missing`, and the sheet silently becomes the
     no-photograph page this case just refused — with every assertion above still green. */
  const natural = await photos.evaluateAll((nodes) =>
    nodes.map((node) => (node as HTMLImageElement).naturalWidth),
  )
  for (const width of natural) expect(width).toBeGreaterThan(0)
})

/* ================================================================================
   THE SIDEBAR REVIEW'S SHARED-KIT ITEMS (2026-09-20): `.bn-stat`, `.bn-progress` and
   `.bn-seg` each shipped able to serve only one call site's own ratio or size, so Orders and
   Inventory hand-rolled their own. These cases prove the ADDED capability on the sheet — none
   of them touch Orders.tsx, Orders.css, orderView.ts, OrdersWalkPane.tsx or how Inventory
   itself draws today; #/orders and #/inventory's own specs, unchanged and still green (see
   inventory.spec.ts's own review of `.browse-boxcell`'s aria-label, S16, next to this file),
   ARE the proof that no screen's current output moved.
   ================================================================================ */

test('stat sm and xs read Orders\' and Inventory\'s own ratios (S9)', async ({ page }) => {
  const spec = page.locator('[data-specimen="stat-sizes"]')
  const base = spec.locator('.bn-stat').nth(0)
  const sm = spec.locator('.bn-stat').nth(1)
  const xs = spec.locator('.bn-stat').nth(2)

  /* The base size is untouched: every existing <Stat> in the product keeps reading 22:12. */
  await expect(base.locator('.bn-stat-value')).toHaveCSS('font-size', '22px')
  await expect(base.locator('.bn-stat-label')).toHaveCSS('font-size', '12px')

  /* `-sm` reads Orders' own two tokens: `--bn-fs-base` (14px) over `--bn-fs-xs` (11px),
     `.orders-index-figure b` / `.orders-index-figure`'s own measured pair. */
  await expect(sm.locator('.bn-stat-value')).toHaveCSS('font-size', '14px')
  await expect(sm.locator('.bn-stat-label')).toHaveCSS('font-size', '11px')

  /* `-xs` reads Inventory's own single token for both: `.browse-boxcell-count` beside
     `.browse-boxcell-meta`, both `--bn-fs-xs` (11px), value un-bolded (weight 600, not 800). */
  await expect(xs.locator('.bn-stat-value')).toHaveCSS('font-size', '11px')
  await expect(xs.locator('.bn-stat-value')).toHaveCSS('font-weight', '600')
  await expect(xs.locator('.bn-stat-label')).toHaveCSS('font-size', '11px')
})

test('progress-sm composes with -ok, which Inventory\'s own bar cannot (S9)', async ({ page }) => {
  const spec = page.locator('[data-specimen="progress-sm-done"]')
  const bars = spec.locator('.bn-progress')
  await expect(bars).toHaveCount(2)

  /* Both bars are the small height Inventory's own hand-rolled `.browse-boxcell-bar` (44x5)
     carries, which the kit's base 6px size never matched. */
  for (const bar of await bars.all()) await expect(bar).toHaveCSS('height', '5px')

  /* The first is mid-fill and reads the accent color; the second is at 100% and, because it
     composes `bn-progress-ok`, reads the ok color instead — the exact combination
     Inventory's own bar (no `-ok` modifier at all) can never draw. */
  const accent = await bars.nth(0).locator('span').evaluate((el) => getComputedStyle(el).backgroundColor)
  const done = await bars.nth(1).locator('span').evaluate((el) => getComputedStyle(el).backgroundColor)
  expect(done).not.toBe(accent)
  await expect(bars.nth(1).locator('span')).toHaveCSS('width', '44px')
})

test('segmented sm totals 28px, flush with a 28px button beside it (S10)', async ({ page }) => {
  const spec = page.locator('[data-specimen="seg-sm"]')
  const seg = spec.locator('.bn-seg')
  const btn = spec.locator('.bn-btn')
  const segBox = await seg.evaluate((el) => el.getBoundingClientRect().height)
  const btnBox = await btn.evaluate((el) => el.getBoundingClientRect().height)
  expect(Math.round(segBox)).toBe(28)
  expect(Math.round(btnBox)).toBe(28)
})

test('bn-truncate clips a name too long for its row (S13)', async ({ page }) => {
  const el = page.locator('[data-specimen="truncate"] .bn-truncate')
  await expect(el).toHaveCSS('text-overflow', 'ellipsis')
  await expect(el).toHaveCSS('overflow-x', 'hidden')
  const [scrollWidth, clientWidth] = await el.evaluate((node) => [node.scrollWidth, node.clientWidth])
  /* The text is wider than the box it sits in — proof the ellipsis is actually doing
     something inside a flex row, and not merely declared and unreachable. `.bn-truncate`
     needed no extra property for this: its own `overflow: hidden` already zeroes a flex
     item's automatic minimum size (kit.css's own note on this rule). */
  expect(scrollWidth).toBeGreaterThan(clientWidth)
})

/* ================================================================================================
   THE KIT FRAME (the UX overhaul's wave 0, 2026-09-23). `#/gallery` is the first screen built on
   `Page`, and the one page that draws every part of the frame, so the frame is asserted here:
   one width, one top gap, one h1 (D272), the notice disclosure (D269), a
   status slot that never moves a row on a one-line answer (D118) and never clips a long one,
   the layer stack, the confirm, the popover, the contrast floors, reduced motion, key hints on a
   touch screen, the toggle focus ring, and axe. Each case went red on its own defect before it
   was kept (a `.bak` mutation per case).
   ============================================================================================== */

const WIDTHS: readonly (readonly [number, number])[] = [
  [1440, 900],
  [820, 1180],
  [720, 900],
  [390, 844],
]

/** A token's value as the browser resolves it, as a color. */
async function tokenColor(page: import('@playwright/test').Page, token: string): Promise<string> {
  return page.evaluate((t) => {
    const el = document.createElement('span')
    el.style.color = `var(${t})`
    document.body.append(el)
    const c = getComputedStyle(el).color
    el.remove()
    return c
  }, token)
}

async function setTheme(page: import('@playwright/test').Page, theme: 'light' | 'dark'): Promise<void> {
  await page.evaluate((t) => {
    if (t === 'dark') document.documentElement.setAttribute('data-theme', 'dark')
    else document.documentElement.removeAttribute('data-theme')
  }, theme)
  // a theme flip eases every colour over a beat (base.css); read after it lands
  await page.waitForTimeout(450)
}

test('the kit is a Page: one h1, one width, one top gap, no sideways scroll, at every width', async ({ page }) => {
  for (const [width, height] of WIDTHS) {
    await page.setViewportSize({ width, height })
    await page.waitForTimeout(100)
    const m = await page.evaluate(() => {
      const main = document.querySelector<HTMLElement>('main[data-bn-page]')
      const h1 = main?.querySelector('h1')
      const probe = document.createElement('div')
      probe.style.height = 'var(--bn-page-top)'
      probe.style.width = 'var(--bn-page-w)'
      document.body.append(probe)
      const topPx = probe.getBoundingClientRect().height
      const wPx = getComputedStyle(probe).width
      probe.remove()
      return {
        pages: document.querySelectorAll('[data-bn-page]').length,
        h1s: document.querySelectorAll('main h1').length,
        h1: h1?.textContent?.trim() ?? null,
        maxWidth: main ? getComputedStyle(main).maxWidth : null,
        wPx,
        gap: main && h1 ? Math.round(h1.getBoundingClientRect().top - main.getBoundingClientRect().top) : null,
        topPx: Math.round(topPx),
        sideways: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      }
    })
    expect(m.pages, `${width}: one page`).toBe(1)
    expect(m.h1s, `${width}: one h1`).toBe(1)
    expect(m.h1, `${width}: the h1 is the title`).toBe('Kit')
    expect(m.maxWidth, `${width}: the page reads --bn-page-w`).toBe(m.wPx)
    expect(m.gap, `${width}: the title sits --bn-page-top below the page's top`).toBe(m.topPx)
    expect(m.topPx, `${width}: --bn-page-top is 16 on a phone and 24 above`).toBe(width < 768 ? 16 : 24)
    expect(m.sideways, `${width}: nothing scrolls sideways`).toBeLessThanOrEqual(0)
  }
})

test('a notice keeps the machine\'s words behind "What the server said" (D269)', async ({ page }) => {
  const notice = page.locator('[data-specimen="notice-said"] .bn-notice')
  const code = notice.locator('.bn-notice-code')
  const said = notice.locator('details.bn-notice-said')
  await expect(said).not.toHaveAttribute('open')
  await expect(code).toBeHidden()
  await expect(notice).not.toContainText('sku_not_a_candidate', { useInnerText: true })
  await said.locator('summary').click()
  await expect(code).toBeVisible()
  await expect(code).toHaveText('sku_not_a_candidate')
})

test('the status slot: a one-line answer moves nothing at 390, 720, 820 and 1440 (D118)', async ({ page }) => {
  for (const width of [390, 720, 820, 1440]) {
    await page.setViewportSize({ width, height: 900 })
    const spec = page.locator('[data-specimen="status-slot"]')
    const under = spec.locator('[data-kit-under-slot]')
    await spec.getByRole('button', { name: 'Clear' }).click()
    await expect(spec.locator('.bn-notice')).toHaveCount(0)
    await spec.scrollIntoViewIfNeeded()
    const top = () => under.evaluate((el) => el.getBoundingClientRect().top + window.scrollY)
    const before = await top()
    await spec.locator('[data-kit-answer="short"]').click()
    await expect(spec.locator('.bn-notice')).toBeVisible()
    const lines = await spec.locator('.bn-notice-text').evaluate((el) => Math.round(el.getBoundingClientRect().height / parseFloat(getComputedStyle(el).lineHeight)))
    expect(lines, `${width}: the specimen answer is one line`).toBeLessThanOrEqual(1)
    const answered = await top()
    await spec.locator('summary').click()
    await expect(spec.locator('.bn-notice-code')).toBeVisible()
    const opened = await top()
    expect(Math.abs(answered - before), `${width}: a one-line answer moved the row under the slot`).toBeLessThanOrEqual(0.5)
    expect(Math.abs(opened - before), `${width}: opening "What the server said" moved the row under the slot`).toBeLessThanOrEqual(0.5)
  }
})

test('at 390 a 300-character answer is never cut, and its disclosure stays inside the gutter', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const spec = page.locator('[data-specimen="status-slot"]')
  await spec.scrollIntoViewIfNeeded()
  await spec.locator('[data-kit-answer="long"]').click()
  const notice = spec.locator('.bn-notice')
  await expect(notice).toBeVisible()
  const body = notice.locator('.bn-notice-body')
  expect((await body.innerText()).length, 'the specimen answer is a long one').toBeGreaterThanOrEqual(240)
  const cut = await notice.evaluate((root) => {
    const out: string[] = []
    for (const el of Array.from(root.querySelectorAll<HTMLElement>('.bn-notice-title, .bn-notice-body, .bn-notice-text'))) {
      const cs = getComputedStyle(el)
      if (cs.textOverflow === 'ellipsis' && cs.whiteSpace === 'nowrap') out.push(`${el.className} ellipsis`)
      if (el.scrollWidth > el.clientWidth + 1) out.push(`${el.className} wider than its box`)
      if (el.scrollHeight > el.clientHeight + 1 && cs.overflowY !== 'visible') out.push(`${el.className} taller than its box`)
    }
    const r = root.getBoundingClientRect()
    const slot = root.parentElement?.getBoundingClientRect()
    if (slot !== undefined && r.bottom > slot.bottom + 1) out.push('the notice spills out of the slot')
    return out
  })
  expect(cut, 'the answer is clipped').toEqual([])
  await notice.locator('summary').click()
  const panel = notice.locator('.bn-notice-said-body')
  await expect(panel).toBeVisible()
  const box = await panel.evaluate((el) => {
    const r = el.getBoundingClientRect()
    return { left: r.left, right: r.right }
  })
  expect(box.left, 'the panel starts left of the gutter').toBeGreaterThanOrEqual(16 - 1)
  expect(box.right, 'the panel ends right of the gutter').toBeLessThanOrEqual(390 - 16 + 1)
})

for (const kind of ['sheet', 'modal'] as const) {
  test(`a ${kind} keeps focus inside, closes on Escape, and gives focus back`, async ({ page }) => {
    const opener = page.locator(`[data-kit-open="${kind}"]`)
    await opener.scrollIntoViewIfNeeded()
    await opener.focus()
    await page.keyboard.press('Enter')
    const dialog = page.locator(`[data-bn-overlay="${kind}"]`)
    await expect(dialog).toBeVisible()
    await expect(dialog).toHaveAttribute('aria-modal', 'true')
    await expect(dialog.locator('h2')).toHaveCount(1)
    await expect(dialog.getByRole('button', { name: 'Close' })).toHaveCount(1)
    await expect.poll(() => dialog.evaluate((el) => el.contains(document.activeElement))).toBe(true)
    for (let i = 0; i < 12; i++) {
      await page.keyboard.press(i % 3 === 2 ? 'Shift+Tab' : 'Tab')
      const inside = await dialog.evaluate((el) => el.contains(document.activeElement))
      expect(inside, `Tab ${i + 1} left the ${kind}`).toBe(true)
    }
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    await expect(opener).toBeFocused()
  })
}

/* `[TABINDEX="-1"]` IS NEVER A TAB STOP, WHATEVER TAG IT IS ON (kit-frame-2, 2026-09-24 — the
 * shell lane's own finding: focus escaped the palette). `focusables()` (kit/overlay.tsx)
 * selected by TAG for the elements that are focusable by default — `button:not([disabled])`
 * and its siblings — and `tabindex="-1"` on one of THOSE never disqualified it, only on an
 * element whose sole claim to being focusable WAS its `tabindex`. A control marked
 * `tabindex="-1"` on purpose (a row a screen reader announces but a keyboard should skip past,
 * the shape the palette's own selected row takes) was therefore still counted in `items`.
 * A REAL BROWSER'S OWN TAB KEY ALREADY SKIPS `tabindex="-1"` — that half of the trap was never
 * broken, and a blind press-Tab-N-times loop never observes this defect, because native Tab
 * traversal ignores `focusables()` entirely except at the trap's own edges. The actual escape is
 * in the WRAP: `onKey`'s `first?.focus()` / `last?.focus()` call `.focus()` PROGRAMMATICALLY,
 * which — unlike a real Tab press — works on a `tabindex="-1"` element without complaint. So the
 * marker is placed FIRST in the panel (making it `items[0]` under the buggy selector), and the
 * probe is Tab pressed from the panel's true LAST control: the trap sees `at === last` and calls
 * `first.focus()`, landing on the marker if the selector still counts it.
 * A RAW ELEMENT, INJECTED, RATHER THAN A NEW SPECIMEN: `Gallery.tsx` is not this lane's file,
 * and the defect is in `focusables()`'s own selector, not in anything a specimen draws — so the
 * fixture is built the same way `tokenColor()` above builds its own, prepended straight into an
 * already-open, already-trapped panel, ahead of even its own header.
 * OBSERVED RED BEFORE IT WAS KEPT. Mutation: `.bak` `kit/overlay.tsx` and put back
 * `[tabindex]:not([tabindex="-1"])` as the ONLY clause carrying that exclusion. Tab from Cancel
 * wraps onto the marker instead of Close, and both assertions below fail. */
test('a tabindex="-1" control is never landed on when focus wraps inside a trapped layer', async ({ page }) => {
  const opener = page.locator('[data-kit-open="sheet"]')
  await opener.scrollIntoViewIfNeeded()
  await opener.click()
  const sheet = page.locator('[data-bn-overlay="sheet"]')
  await expect(sheet).toBeVisible()
  await sheet.evaluate((panel) => {
    const marker = document.createElement('button')
    marker.type = 'button'
    marker.tabIndex = -1
    marker.id = 'kf2-not-a-tab-stop'
    marker.textContent = 'a row a screen reader hears and a keyboard skips'
    panel.prepend(marker)
  })
  // Cancel is the panel's own true last focusable control (its footer's last button).
  await sheet.getByRole('button', { name: 'Cancel' }).focus()
  await page.keyboard.press('Tab')
  const id = await page.evaluate(() => document.activeElement?.id ?? null)
  expect(id, 'Tab wrapped from the last real control onto the tabindex="-1" marker').not.toBe('kf2-not-a-tab-stop')
  await expect(sheet.getByRole('button', { name: 'Close' }), 'Tab from the last control should wrap to the panel\'s true first, Close').toBeFocused()
  await page.keyboard.press('Escape')
  await expect(sheet).toHaveCount(0)
})

test('a confirm is an alertdialog, its first focus is Cancel, and a held Enter confirms nothing', async ({ page }) => {
  const opener = page.locator('[data-kit-open="confirm"]')
  await opener.scrollIntoViewIfNeeded()
  await opener.focus()
  /* hold Enter: the press that opens it, then the key's own repeats landing inside it */
  await page.keyboard.down('Enter')
  const dialog = page.locator('[data-bn-overlay="modal"]')
  await expect(dialog).toBeVisible()
  await expect(dialog).toHaveAttribute('role', 'alertdialog')
  await expect(dialog.getByRole('button', { name: 'Cancel' })).toBeFocused()
  /* a second `down` on a held key is the browser's own auto-repeat (`repeat: true`), trusted, and
     it lands on Cancel: were a held key honoured, Cancel would close the confirm right here */
  for (let i = 0; i < 5; i++) await page.keyboard.down('Enter')
  await page.keyboard.up('Enter')
  /* a closing layer keeps drawing for its leave beat, so wait it out and ask whether it is leaving */
  await page.waitForTimeout(400)
  await expect(dialog, 'a held Enter closed the confirm').toBeVisible()
  await expect(dialog, 'a held Enter closed the confirm').not.toHaveAttribute('data-leaving')
  await page.keyboard.press('Escape')
  await expect(dialog).toHaveCount(0)
  await expect(opener).toBeFocused()
})

test('a busy confirm cannot be closed by Close, Escape or the scrim', async ({ page }) => {
  const opener = page.locator('[data-kit-open="busy-confirm"]')
  await opener.scrollIntoViewIfNeeded()
  await opener.click()
  const dialog = page.locator('[data-bn-overlay="modal"]')
  await expect(dialog).toBeVisible()
  await dialog.getByRole('button', { name: 'Delete 3 cards' }).click()
  await expect(dialog.getByRole('button', { name: 'Close' })).toBeDisabled()
  await page.keyboard.press('Escape')
  await page.mouse.click(4, 4)
  await page.waitForTimeout(300)
  await expect(dialog, 'a busy confirm closed').toBeVisible()
  await expect(dialog, 'a busy confirm closed').not.toHaveAttribute('data-leaving')
  /* the specimen's write finishes, and then it closes */
  await expect(dialog).toHaveCount(0, { timeout: 5000 })
})

test('layers stack: the top one takes focus and Escape, and each gives focus back in turn', async ({ page }) => {
  const opener = page.locator('[data-kit-open="layered"]')
  await opener.scrollIntoViewIfNeeded()
  await opener.focus()
  await page.keyboard.press('Enter')
  const first = page.locator('[data-bn-overlay="modal"]').filter({ hasText: 'The first layer' })
  await expect(first).toBeVisible()
  const secondOpener = first.locator('[data-kit-open="second"]')
  await secondOpener.focus()
  await page.keyboard.press('Enter')
  const second = page.locator('[data-bn-overlay="modal"]').filter({ hasText: 'The second layer' })
  await expect(second).toBeVisible()
  await expect.poll(() => second.evaluate((el) => el.contains(document.activeElement))).toBe(true)
  for (let i = 0; i < 6; i++) {
    await page.keyboard.press('Tab')
    expect(await second.evaluate((el) => el.contains(document.activeElement)), `Tab ${i + 1} left the top layer`).toBe(true)
  }
  await page.keyboard.press('Escape')
  await expect(second).toHaveCount(0)
  await expect(first, 'one Escape closed both layers').toBeVisible()
  await expect(secondOpener).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(first).toHaveCount(0)
  await expect(opener).toBeFocused()
})

/* A rectangle in VIEWPORT coordinates — `getBoundingClientRect()`'s own frame, which is what
 * `elementFromPoint` reads too, so a point computed from one is valid for the other. */
type Box = { readonly x: number; readonly y: number; readonly width: number; readonly height: number }

async function boxOf(target: Locator): Promise<Box> {
  return target.evaluate((el) => {
    const r = el.getBoundingClientRect()
    return { x: r.x, y: r.y, width: r.width, height: r.height }
  })
}

/** A point inside `lower` and outside `upper` — whichever margin `lower` extends past `upper`
 *  on (top, bottom, left or right), the midpoint of that strip. `null` when `upper` fully
 *  covers `lower`, which would make a point that is "inside lower, outside upper" undefined. */
function pointOutside(lower: Box, upper: Box): { readonly x: number; readonly y: number } | null {
  if (lower.y < upper.y) {
    return { x: lower.x + lower.width / 2, y: (lower.y + Math.min(lower.y + lower.height, upper.y)) / 2 }
  }
  if (lower.y + lower.height > upper.y + upper.height) {
    return { x: lower.x + lower.width / 2, y: (Math.max(lower.y, upper.y + upper.height) + lower.y + lower.height) / 2 }
  }
  if (lower.x < upper.x) {
    return { x: (lower.x + Math.min(lower.x + lower.width, upper.x)) / 2, y: lower.y + lower.height / 2 }
  }
  if (lower.x + lower.width > upper.x + upper.width) {
    return { x: (Math.max(lower.x, upper.x + upper.width) + lower.x + lower.width) / 2, y: lower.y + lower.height / 2 }
  }
  return null
}

/* A SECOND SCRIMMED LAYER'S OWN SCRIM HAS TO DIM THE FIRST LAYER'S PANEL — a review finding,
 * 2026-09-23. `useOverlayLayer` gives the panel a z-index from its own position in the stack
 * (`kit/overlay.tsx`), but until this fix every scrim shared ONE static number (60, kit.css)
 * regardless of which layer it belonged to — so a second scrim (60) sat BELOW the first layer's
 * own panel (61) instead of above it, and the layer underneath was never actually dimmed. Two
 * shapes: a `ConfirmSheet` opened from inside an open `Sheet`, and the kit's own `Modal`-over-
 * `Modal` fixture (`layered`/`second`). Both read the SAME two things: the upper scrim's own
 * z-index against both panels' (`assertUpperScrimDims`), and a real point — computed, not
 * guessed — where only the scrim, not the upper panel itself, could be covering the lower one. */
async function assertUpperScrimDims(page: Page, lower: Locator, upper: Locator): Promise<void> {
  // The upper panel's own entrance transform (`bn-dialog-in`/`bn-sheet-up`, kit.css) is still
  // animating for `toBeVisible()`'s whole first frame — a `getBoundingClientRect()` read mid
  // scale is a real but TRANSIENT box, not the settled one this geometry is about (the same
  // shape of reading `fulfillment.spec.ts`'s own `settleMotion` calls exist for).
  await settleMotion(page)
  const scrims = page.locator('.bn-scrim')
  await expect(scrims).toHaveCount(2)
  const [lowerZ, upperZ, scrimZs] = await Promise.all([
    lower.evaluate((el) => Number(window.getComputedStyle(el).zIndex)),
    upper.evaluate((el) => Number(window.getComputedStyle(el).zIndex)),
    scrims.evaluateAll((els) => els.map((el) => Number(window.getComputedStyle(el).zIndex))),
  ])
  const upperScrimZ = Math.max(...scrimZs)
  expect(upperScrimZ, `scrims: ${scrimZs.join(', ')}, lower panel: ${lowerZ}`).toBeGreaterThan(lowerZ)
  expect(upperScrimZ, `scrims: ${scrimZs.join(', ')}, upper panel: ${upperZ}`).toBeLessThan(upperZ)

  const [lowerBox, upperBox] = await Promise.all([boxOf(lower), boxOf(upper)])
  const point = pointOutside(lowerBox, upperBox)
  expect(point, 'no margin between the two panels to probe an uncovered point in').not.toBeNull()
  const covering = await page.evaluate(({ x, y }) => document.elementFromPoint(x, y)?.className ?? null, point!)
  expect(covering, `element at (${point!.x}, ${point!.y}): "${covering}"`).toContain('bn-scrim')
}

test('a confirm opened from inside an open sheet dims the sheet with its own scrim, not the sheet\'s', async ({
  page,
}) => {
  const openSheet = page.locator('[data-kit-open="sheet"]')
  await openSheet.scrollIntoViewIfNeeded()
  await openSheet.click()
  const sheet = page.locator('[data-bn-overlay="sheet"]')
  await expect(sheet).toBeVisible()

  await sheet.locator('[data-kit-open="confirm-in-sheet"]').click()
  const confirm = page.locator('[role="alertdialog"]')
  await expect(confirm).toBeVisible()

  await assertUpperScrimDims(page, sheet, confirm)

  await confirm.getByRole('button', { name: 'Cancel' }).click()
  await expect(confirm).toHaveCount(0)
  await expect(sheet).toBeVisible()
})

test('a second modal over the first dims it with its own scrim, not the first modal\'s', async ({ page }) => {
  const opener = page.locator('[data-kit-open="layered"]')
  await opener.scrollIntoViewIfNeeded()
  await opener.click()
  const first = page.locator('[data-bn-overlay="modal"]').filter({ hasText: 'The first layer' })
  await expect(first).toBeVisible()

  await first.locator('[data-kit-open="second"]').click()
  const second = page.locator('[data-bn-overlay="modal"]').filter({ hasText: 'The second layer' })
  await expect(second).toBeVisible()

  await assertUpperScrimDims(page, first, second)

  await page.keyboard.press('Escape')
  await expect(second).toHaveCount(0)
  await expect(first).toBeVisible()
})

/* A THIRD SCRIMMED LAYER IS A DEVELOPMENT-TIME CRASH, AND A PRODUCTION-TIME LOG (coordinator
 * review, 2026-09-24, amending kit-frame-2's first cut of this). `layerZ` (kit/overlay.tsx)
 * clamps at `MAX_LAYER_DEPTH` (2): past it, a scrimmed layer's own scrim would reuse the SECOND
 * layer's pair and land BELOW its panel — undimmed, the same defect `assertUpperScrimDims`
 * above exists to catch, reappearing one layer deeper where nothing here was checking. Nothing
 * this product opens goes three scrimmed layers deep (the file's own argument). In DEVELOPMENT
 * `useOverlayLayer` throws rather than joining the stack, and the nearest route's own error
 * boundary (App.tsx's `RouteBoundary`) is where that lands — the same door a real defect uses.
 * This case proves that half. The next one proves PRODUCTION never crashes over the same thing.
 * NO NEW SPECIMEN NEEDED: the existing "Open a modal" trigger (`data-kit-open="modal"`) still
 * sits in the DOM under the two open layers, so calling its own `.click()` reaches its
 * independent `Modal` — exactly a third concurrent scrimmed layer. A `page.locator(...).click()`
 * would hit the top scrim instead (it covers the viewport and is what a real pointer would
 * land on), which is the wrong thing to be testing: this proves the THIRD LAYER is refused, not
 * that a click can be aimed through two others.
 * OBSERVED RED BEFORE IT WAS KEPT. Mutation: `.bak` `kit/overlay.tsx` and drop the `throw` (keep
 * the two `push`es). The third layer opens, `.no-such-view` never appears, and the assertion
 * below reports 0 where it wants 1 — silently wrong, exactly the failure mode this guards. */
test('in development, a third scrimmed layer crashes loudly rather than drawing a broken dim', async ({ page }) => {
  const opener = page.locator('[data-kit-open="layered"]')
  await opener.scrollIntoViewIfNeeded()
  await opener.click()
  const first = page.locator('[data-bn-overlay="modal"]').filter({ hasText: 'The first layer' })
  await expect(first).toBeVisible()

  await first.locator('[data-kit-open="second"]').click()
  const second = page.locator('[data-bn-overlay="modal"]').filter({ hasText: 'The second layer' })
  await expect(second).toBeVisible()

  await page.locator('[data-kit-open="modal"]').evaluate((el) => (el as HTMLElement).click())
  await expect(page.locator('.no-such-view')).toBeVisible()
  await expect(page.locator('.no-such-view-path')).toHaveText('Too many things tried to open on this screen at once.')

  /* `sealEveryTest`'s own `afterEach` (shell.ts) refuses to end ANY case on this crash page — a
     defect this suite is built to notice, and this case's own assertion just above is the one
     place that is meant to see it. "Reload this screen" is `RouteBoundary`'s own recovery, the
     same one a real crash offers, and it leaves the route fully fresh (every specimen's state
     was in the tree the boundary discarded). */
  await page.getByRole('button', { name: 'Reload this screen' }).click()
  await expect(page.locator('.no-such-view')).toHaveCount(0)
  await expect(page.locator('h1')).toHaveText('Kit')
})

/* THE PRODUCTION HALF. `make design-check`'s webServer is always `vite dev` (devPort.ts's own
 * header), so `import.meta.env.DEV` is `true` in every browser this suite ever drives — a real
 * production bundle (`vite build`) is a different command this suite never runs, and Vite
 * inlines that constant at build time, so no page script can flip it after the fact either.
 * `window.__overlaySetDevModeForTest` (kit/overlay.tsx, registered only while `import.meta.env.
 * DEV` is true, which a real build never is) is the STUB the coordinator's review asked for:
 * it overrides the internal check `useOverlayLayer` actually reads, so this drives the exact
 * branch a production bundle would take without needing a second webServer or a built dist/.
 * OBSERVED RED BEFORE IT WAS KEPT. Mutation: `.bak` `kit/overlay.tsx` and drop the
 * `overlayIsDevMode()` branch, always throwing. The third layer never opens and the
 * `toBeVisible()` below times out. */
test('in production, a third scrimmed layer opens (clamped) and logs once, never crashing', async ({ page }) => {
  await page.evaluate(() => (window as unknown as { __overlaySetDevModeForTest: (v: boolean) => void }).__overlaySetDevModeForTest(false))
  const errors: string[] = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(msg.text())
  })

  const opener = page.locator('[data-kit-open="layered"]')
  await opener.scrollIntoViewIfNeeded()
  await opener.click()
  const first = page.locator('[data-bn-overlay="modal"]').filter({ hasText: 'The first layer' })
  await expect(first).toBeVisible()

  await first.locator('[data-kit-open="second"]').click()
  const second = page.locator('[data-bn-overlay="modal"]').filter({ hasText: 'The second layer' })
  await expect(second).toBeVisible()

  await page.locator('[data-kit-open="modal"]').evaluate((el) => (el as HTMLElement).click())
  const third = page.locator('[data-bn-overlay="modal"]').filter({ hasText: 'One decision' })
  await expect(third, 'the third layer opened instead of being dropped').toBeVisible()
  await expect(page.locator('.no-such-view'), 'production crashed the whole screen').toHaveCount(0)
  await expect
    .poll(() => errors.some((e) => e.includes('a third scrimmed layer opened')), 'a console.error named the degraded stacking')
    .toBe(true)

  await page.evaluate(() => (window as unknown as { __overlaySetDevModeForTest: (v: boolean | null) => void }).__overlaySetDevModeForTest(null))
})

/** The rendered width of the single space between two known words inside an element's own text
 *  node, isolated with a `Range` rather than read off the whole element — the only way to
 *  measure one character's own advance rather than the string's total width. Returns -1 if the
 *  two words are not adjacent, single-spaced text inside the element. */
async function wordSpaceWidth(el: Locator, before: string, after: string): Promise<number> {
  return el.evaluate(
    (node, [b, a]) => {
      const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT)
      for (let text = walker.nextNode(); text !== null; text = walker.nextNode()) {
        const content = text.textContent ?? ''
        const at = content.indexOf(`${b} ${a}`)
        if (at < 0) continue
        const range = document.createRange()
        range.setStart(text, at + b.length)
        range.setEnd(text, at + b.length + 1)
        return range.getBoundingClientRect().width
      }
      return -1
    },
    [before, after] as [string, string],
  )
}

/* `.bn-overlay-title` IS AN `h2` (kit/overlay.tsx) with no class of its own governing type, so
 * it falls to base.css's bare `h1, h2, h3, h4` rule: Manrope, `letter-spacing:
 * var(--bn-tracking-tight)`, -0.02em, -0.32px at this title's own 16px (`--bn-fs-h3`).
 * `letter-spacing` is added after EVERY character INCLUDING THE SPACE GLYPH, and Manrope's own
 * space advance at 16px is narrow enough that this shaves it to under 3px — a two-word title
 * reads as one word: "Go to" measured at 2.9px wide, visually "Goto". The defect is
 * viewport-independent (letter-spacing is a font-metric effect, not a layout one), but this
 * checks both widths this suite otherwise verifies, in case a future rule makes it size-aware.
 * OBSERVED RED BEFORE IT WAS KEPT. Mutation: `.bak` `kit.css` and drop `.bn-overlay-title`'s
 * `word-spacing` rule (below). The measured space falls back under 3px at both widths and the
 * assertion below fails. */
for (const width of [1440, 390]) {
  test(`an overlay title's word space stays visible at ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    const opener = page.locator('[data-kit-open="modal"]')
    await opener.scrollIntoViewIfNeeded()
    await opener.click()
    const dialog = page.locator('[data-bn-overlay="modal"]').filter({ hasText: 'One decision' })
    await expect(dialog).toBeVisible()
    const space = await wordSpaceWidth(dialog.locator('.bn-overlay-title'), 'One', 'decision')
    expect(space, "the rendered width of the space in the overlay title's two words").toBeGreaterThanOrEqual(3.5)
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
  })
}

test('a popover closes on Escape, and on Tab past its last item, and gives focus back to its trigger', async ({ page }) => {
  const opener = page.locator('[data-kit-open="popover"]')
  await opener.scrollIntoViewIfNeeded()
  const pop = page.locator('[data-bn-overlay="popover"]')
  await opener.click()
  await expect(pop).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(pop).toHaveCount(0)
  await expect(opener).toBeFocused()

  await opener.click()
  await expect(pop).toBeVisible()
  const items = pop.locator('button')
  await items.last().focus()
  await page.keyboard.press('Tab')
  await expect(pop).toHaveCount(0)
  await expect(opener, 'Tab past the last item walked on into the page').toBeFocused()
})

test('at 390 a popover near the foot opens above its trigger, clear of the tab bar', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const opener = page.locator('[data-kit-open="popover"]')
  await opener.scrollIntoViewIfNeeded()
  /* put the trigger just above the tab bar, where there is no room below it */
  await opener.evaluate((el) => {
    const bar = document.querySelector('.bn-tabbar')?.getBoundingClientRect().top ?? window.innerHeight
    const r = el.getBoundingClientRect()
    window.scrollBy(0, r.bottom - bar + 12)
  })
  await opener.click()
  const pop = page.locator('[data-bn-overlay="popover"]')
  await expect(pop).toBeVisible()
  const m = await pop.evaluate((el) => {
    const r = el.getBoundingClientRect()
    const bar = document.querySelector('.bn-tabbar')
    const floor = bar !== null && bar.getClientRects().length > 0 ? bar.getBoundingClientRect().top : window.innerHeight
    return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, floor, width: window.innerWidth, squashed: el.scrollHeight > el.clientHeight + 1 }
  })
  expect(m.squashed, 'the popover is squashed into the room below instead of opening above').toBe(false)
  expect(m.bottom, 'the popover runs under the tab bar').toBeLessThanOrEqual(m.floor)
  expect(m.top, 'the popover runs off the top').toBeGreaterThanOrEqual(0)
  expect(m.left).toBeGreaterThanOrEqual(0)
  expect(m.right).toBeLessThanOrEqual(m.width)
  await page.keyboard.press('Escape')
})

for (const theme of ['light', 'dark'] as const) {
  test(`ink-4 is a visible non-text tier, and the pills and the field edge reach their floors (${theme})`, async ({ page }) => {
    await setTheme(page, theme)
    const r = await page.evaluate(() => {
      const parse = (c: string) => {
        const p = (c.match(/[\d.]+/g) ?? []).map(Number)
        return { rgb: p.slice(0, 3), a: p.length > 3 ? (p[3] ?? 1) : 1 }
      }
      const lum = (rgb: number[]) => {
        const f = (v: number) => {
          const x = v / 255
          return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4
        }
        return 0.2126 * f(rgb[0] ?? 0) + 0.7152 * f(rgb[1] ?? 0) + 0.0722 * f(rgb[2] ?? 0)
      }
      const ratio = (a: number[], b: number[]) => {
        const x = lum(a)
        const y = lum(b)
        return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05)
      }
      const over = (top: { rgb: number[]; a: number }, bot: number[]) => top.rgb.map((v, i) => v * top.a + (bot[i] ?? 0) * (1 - top.a))
      const probe = (css: string) => {
        const el = document.createElement('span')
        el.style.color = css
        document.body.append(el)
        const c = getComputedStyle(el).color
        el.remove()
        return parse(c)
      }
      const grounds = ['--bn-bg', '--bn-surface', '--bn-surface-2'].map((t) => probe(`var(${t})`).rgb)
      // A SELECTED ROW'S OWN GROUND: `.bn-list-row[aria-selected]` (kit.css) tints `.bn-panel`'s
      // `--bn-surface` with `--bn-accent-tint`, and a pill drawn on it sits on a second tint over
      // that first one, not on a plain ground — the review found a danger pill there at 4.08:1
      // in dark, under a spec that had only ever checked a pill against the three PLAIN grounds
      // above (kit-frame-2, 2026-09-24).
      const selectedRow = over(probe('var(--bn-accent-tint)'), probe('var(--bn-surface)').rgb)
      const pillGrounds = [...grounds, selectedRow]
      const ink3 = probe('var(--bn-ink-3)').rgb
      const ink4 = probe('var(--bn-ink-4)').rgb
      const edge = probe('var(--bn-field-edge)').rgb
      const pills = ['accent', 'ok', 'warn', 'danger', 'live'].map((tone) => {
        const ink = probe(`var(--bn-pill-ink-${tone})`).rgb
        const tint = probe(`var(--bn-${tone}-tint)`)
        return { tone, ink, worst: Math.min(...pillGrounds.map((g) => ratio(ink, over(tint, g)))) }
      })
      const hue = (rgb: number[]) => {
        const [r, g, b] = rgb.map((v) => v / 255) as [number, number, number]
        const max = Math.max(r, g, b)
        const min = Math.min(r, g, b)
        if (max === min) return 0
        const d = max - min
        const h = max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4
        return (h * 60 + 360) % 360
      }
      const live = pills.find((p) => p.tone === 'live')?.ink ?? [0, 0, 0]
      const danger = pills.find((p) => p.tone === 'danger')?.ink ?? [0, 0, 0]
      const apart = Math.min(Math.abs(hue(live) - hue(danger)), 360 - Math.abs(hue(live) - hue(danger)))
      const lightness = ratio(live, danger)
      return {
        ink4: Math.min(...grounds.map((g) => ratio(ink4, g))),
        tier: ratio(ink3, ink4),
        edge: Math.min(...grounds.map((g) => ratio(edge, g))),
        pills: pills.map((p) => ({ tone: p.tone, worst: p.worst })),
        apart,
        lightness,
      }
    })
    expect(r.ink4, 'ink-4, a graphic, on every ground').toBeGreaterThanOrEqual(3)
    expect(r.tier, 'ink-4 is a visible step below ink-3').toBeGreaterThanOrEqual(1.25)
    expect(r.edge, 'a field edge on every ground').toBeGreaterThanOrEqual(3)
    for (const pill of r.pills) expect(pill.worst, `the ${pill.tone} pill's word on its tint`).toBeGreaterThanOrEqual(4.5)
    expect(r.apart, 'the live and danger pills are two hues').toBeGreaterThanOrEqual(15)
    if (theme === 'dark') expect(r.lightness, 'the live and danger pills are two lightnesses').toBeGreaterThanOrEqual(1.2)
    const field = page.locator('[data-kit-section="fields"] .bn-input').first()
    await expect(field).toHaveCSS('border-top-color', await tokenColor(page, '--bn-field-edge'))
    const okPill = page.locator('[data-kit-section="pills"] .bn-pill-ok').first()
    await expect(okPill).toHaveCSS('color', await tokenColor(page, '--bn-pill-ink-ok'))
  })
}

test.describe('under reduced motion', () => {
  /* `emulateMedia` and not `test.use`, which this Playwright's fixture types do not accept for
     `reducedMotion` (brand.spec.ts says the same, and there it used a context of its own). */
  test('the shimmer and the live dot stop, and nothing moves faster (UX-125)', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' })
    const shimmer = await page.locator('.bn-skeleton').first().evaluate((el) => getComputedStyle(el, '::after').animationIterationCount)
    const dot = await page.locator('.bn-dot-live').first().evaluate((el) => getComputedStyle(el).animationIterationCount)
    expect(shimmer, 'the skeleton shimmer still loops').toBe('1')
    expect(dot, 'the live dot still pulses').toBe('1')
  })
})

test.describe('on a touch screen', () => {
  test.use({ hasTouch: true, isMobile: true, viewport: { width: 390, height: 844 } })

  test('a key hint leaves as a whole phrase, a keycap in a control hides, and a bare keycap stays (UX-040)', async ({ page }) => {
    const drawn = (sel: string) =>
      page.evaluate((s) => Array.from(document.querySelectorAll<HTMLElement>(s)).filter((el) => el.getClientRects().length > 0).length, sel)
    expect(await page.locator('main .bn-keyhint').count(), 'the sheet draws a key hint').toBeGreaterThan(0)
    expect(await drawn('main .bn-keyhint'), 'a key hint still drawn on a touch screen').toBe(0)
    expect(await page.locator('main .bn-btn .bn-kbd').count(), 'the sheet draws keycaps in buttons').toBeGreaterThan(0)
    expect(await drawn('main .bn-btn .bn-kbd'), 'a keycap inside a button still drawn').toBe(0)
    /* a bare keycap in running text is left alone: hiding it alone breaks its sentence */
    const bare = page.locator('[data-kit-section="kbd"] .kit-row > .bn-kbd').first()
    await expect(bare).toBeVisible()
  })
})

test.describe('on a touch screen at 1440', () => {
  /* THE POINTER DECIDES, NOT THE WIDTH (CLAUDE.md, docs/DESIGN.md's own "an iPad in portrait is
     820px wide and all thumb"). `.bn-status-slot`'s two-row layout (kit.css) fires on
     `(max-width: 1023px), (hover: none) and (pointer: coarse)` — an OR of a width and a pointer
     — and every status-slot case above only ever drove the WIDTH half of it, always at a fine
     (mouse) pointer. A coarse pointer at a DESKTOP width was never exercised, so an `and` typed
     where the rule means `or` would still read green above (kit-frame-2, 2026-09-24).
     OBSERVED RED BEFORE IT WAS KEPT. Mutation: `.bak` kit.css and change this query's leading
     `,` to `and`. The grid stays four columns at 1440 on a touch context and both assertions
     below fail. */
  test.use({ hasTouch: true, viewport: { width: 1440, height: 900 } })

  test('the status slot still draws two rows at 1440 on a coarse pointer (D118)', async ({ page }) => {
    const spec = page.locator('[data-specimen="status-slot"]')
    await spec.scrollIntoViewIfNeeded()
    await spec.locator('[data-kit-answer="short"]').click()
    const notice = spec.locator('.bn-notice')
    await expect(notice).toBeVisible()
    const icon = notice.locator('.bn-icon').first()
    const said = notice.locator('.bn-notice-said > summary')
    const [iconTop, saidTop, columns] = await Promise.all([
      icon.evaluate((el) => el.getBoundingClientRect().top),
      said.evaluate((el) => el.getBoundingClientRect().top),
      notice.evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(' ').length),
    ])
    expect(columns, 'a coarse pointer drops the notice grid to three columns, even at 1440').toBe(3)
    expect(saidTop, 'the disclosure sits on a second row, under the sentence').toBeGreaterThan(iconTop + 4)
  })
})

/* THE PHONE CHROME'S OWN SEAM MOVED TO 640, NOT 768 (owner ruling, the shell lane: 720 gets the
 * DESKTOP rail, docs/DESIGN.md's "640 the phone/tablet seam"). Two of the kit's own rules
 * answered to the shell's OLD seam (767) rather than to `.bn-tabbar`'s actual presence: the
 * sheet/dialog bottom-rise (kit.css, "on a phone every sheet and dialog rises from the bottom")
 * and the toast stack's 64px lift for the tab bar it clears. At 720 — a width that now draws the
 * desktop rail and NO tab bar — either rule still answering to 767 would rise a sheet from the
 * bottom of a desktop page, or lift a toast for a bar that is not there.
 * A REAL `Sheet` FOR THE FIRST HALF: the "sheet" specimen, edge-to-edge and pinned to the bottom
 * only below the seam.
 * A RAW `.bn-toasts` ELEMENT FOR THE SECOND: the kit's `Toaster` (kit/toast.tsx, not this lane's
 * file) only mounts one when a real toast is pushed, and nothing here can reach its module-scoped
 * `toast()` from outside React — so, exactly as `tokenColor()` above probes a token with a
 * disposable element, this probes kit.css's OWN rule the same way: append the one class the rule
 * matches, read where the box lands, remove it. Nothing about `Toaster`'s own behaviour is
 * under test here, only the stylesheet rule this lane changed.
 * OBSERVED RED BEFORE IT WAS KEPT. Mutation: `.bak` kit.css and put both media queries back at
 * `max-width: 767px`. At 720 the sheet rises from the bottom and the toast reports a 64px lift,
 * and both assertions below fail. */
for (const width of [639, 720] as const) {
  const phone = width < 640
  test(`at ${width}, ${phone ? 'a sheet rises from the bottom and the toast clears the tab bar' : 'a sheet stays on its own edge and the toast sits at the page corner'} (kit-frame-2)`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 })

    const opener = page.locator('[data-kit-open="sheet"]')
    await opener.scrollIntoViewIfNeeded()
    await opener.click()
    const sheet = page.locator('[data-bn-overlay="sheet"]')
    await expect(sheet).toBeVisible()
    const sheetBox = await sheet.evaluate((el) => {
      const r = el.getBoundingClientRect()
      return { left: Math.round(r.left), bottom: Math.round(r.bottom) }
    })
    if (phone) {
      expect(sheetBox.left, `${width}: the sheet spans edge to edge`).toBe(0)
      expect(sheetBox.bottom, `${width}: the sheet rises from the bottom of the viewport`).toBeGreaterThanOrEqual(899)
    } else {
      expect(sheetBox.left, `${width}: the sheet keeps its own width, not edge to edge`).toBeGreaterThan(0)
    }
    await page.keyboard.press('Escape')
    await expect(sheet).toHaveCount(0)

    const toastLift = await page.evaluate(() => {
      const el = document.createElement('div')
      el.className = 'bn-toasts'
      document.body.append(el)
      const lift = window.innerHeight - el.getBoundingClientRect().bottom
      el.remove()
      return Math.round(lift)
    })
    if (phone) {
      expect(toastLift, `${width}: the toast clears a 64px tab bar`).toBeGreaterThanOrEqual(60)
    } else {
      expect(toastLift, `${width}: the toast sits at the page's own corner gap, not lifted for a bar`).toBeLessThan(30)
    }
  })
}

test('every toggle shows the focus ring, whatever outline it wears (UX-100)', async ({ page }) => {
  const toolbar = page.locator('[data-specimen="toolbar"]')
  await toolbar.scrollIntoViewIfNeeded()
  /* the shape Shipping's dashed lane chip has: a one-class outline of its own, declared after
     base.css, which outranked the ring by source order before the toggle floor existed */
  await page.addStyleTag({ content: '.kit-test-dashed { outline: 1.5px dashed red; outline-offset: -1.5px; }' })
  const chip = toolbar.locator('.bn-chip').first()
  await chip.evaluate((el) => el.classList.add('kit-test-dashed'))
  await toolbar.locator('input').focus()
  await page.keyboard.press('Tab')
  await expect(chip).toBeFocused()
  await expect(chip).toHaveCSS('outline-style', 'solid')
  await expect(chip).toHaveCSS('outline-width', '2px')
})

test('the toolbar: one control height, and at 390 the field takes the whole first row', async ({ page }) => {
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 })
    const toolbar = page.locator('[data-specimen="toolbar"] .bn-toolbar')
    await toolbar.scrollIntoViewIfNeeded()
    const m = await toolbar.evaluate((root) => {
      const kids = Array.from(root.children) as HTMLElement[]
      const boxes = kids.map((el) => el.getBoundingClientRect())
      const rootBox = root.getBoundingClientRect()
      const field = boxes[0]
      return {
        heights: [...new Set(boxes.map((b) => Math.round(b.height)))],
        fieldFull: field !== undefined && Math.abs(field.width - rootBox.width) <= 1,
        othersBelow: boxes.slice(1).every((b) => field !== undefined && b.top >= field.bottom - 1),
      }
    })
    expect(m.heights, `${width}: one control height`).toHaveLength(1)
    if (width === 390) {
      expect(m.fieldFull, '390: the field takes the whole first row').toBe(true)
      expect(m.othersBelow, '390: the chips and the sort wrap below the field').toBe(true)
    }
  }
})

test('a section inside a layer is an h3, and on the page an h2', async ({ page }) => {
  await expect(page.locator('[data-specimen="section"] section.bn-section h2')).toHaveCount(1)
  const opener = page.locator('[data-kit-open="sheet"]')
  await opener.scrollIntoViewIfNeeded()
  await opener.click()
  const sheet = page.locator('[data-bn-overlay="sheet"]')
  await expect(sheet.locator('section.bn-section h3')).toHaveCount(1)
  await page.keyboard.press('Escape')
})

/* AXE ON THE KIT, AT BOTH ENDS AND IN BOTH THEMES. What is left is listed by selector and by the
   lane that owns the fix — a shrinking list, never a pinned count. A violation not listed fails.
   A listed entry that matches nothing in any of the four runs fails too, so the list only
   shrinks: take the entry out in the commit that fixes it. */
const AXE_KNOWN: readonly { readonly rule: string; readonly selector: string; readonly owner: string; readonly why: string }[] = [
  {
    rule: 'color-contrast',
    selector: '.position-path',
    owner: 'locating lane',
    why: 'PositionLabel draws a label with no figure muted: 2.89:1 light, 3.2:1 dark. The same on main.',
  },
  {
    rule: 'color-contrast',
    selector: '.position-key',
    owner: 'locating lane',
    why: 'the same muted PositionLabel, its store key',
  },
]

test('axe finds nothing on the kit at 390 and 1440 in both themes, but what is listed with its owner', async ({ page }) => {
  test.setTimeout(90_000)
  const axePath = createRequire(import.meta.url).resolve('axe-core/axe.min.js')
  const seen = new Set<number>()
  const unlisted: string[] = []
  for (const theme of ['light', 'dark'] as const) {
    for (const width of [390, 1440]) {
      await page.setViewportSize({ width, height: 900 })
      await setTheme(page, theme)
      await page.addScriptTag({ path: axePath })
      /* two states: the page at rest, and the page with a layer open over it (a layer is
         portalled to <body>, so it is audited with the page, landmarks and all) */
      for (const state of ['rest', 'layer'] as const) {
        const opener = page.locator('[data-kit-open="sheet"]')
        if (state === 'layer') {
          await opener.scrollIntoViewIfNeeded()
          await opener.click()
          await expect(page.locator('[data-bn-overlay="sheet"]')).toBeVisible()
          await page.waitForTimeout(400)
        }
        const violations = await page.evaluate(async () => {
          const w = window as unknown as {
            axe: { run: (ctx: object, opts: object) => Promise<{ violations: { id: string; nodes: { target: string[] }[] }[] }> }
          }
          const include = [['main[data-bn-page]'], ...(document.querySelector('[data-bn-overlay]') === null ? [] : [['[data-bn-overlay]']])]
          const r = await w.axe.run({ include }, { resultTypes: ['violations'] })
          return r.violations.flatMap((v) => v.nodes.map((n) => ({ rule: v.id, target: n.target.join(' ') })))
        })
        for (const v of violations) {
          const at = AXE_KNOWN.findIndex((k) => k.rule === v.rule && v.target.includes(k.selector))
          if (at >= 0) seen.add(at)
          else unlisted.push(`${theme} ${width} ${state}: ${v.rule} ${v.target}`)
        }
        if (state === 'layer') {
          await page.keyboard.press('Escape')
          await expect(page.locator('[data-bn-overlay="sheet"]')).toHaveCount(0)
        }
      }
    }
  }
  expect(unlisted, `axe violations nobody owns:\n${unlisted.join('\n')}`).toEqual([])
  const stale = AXE_KNOWN.filter((_, i) => !seen.has(i)).map((k) => `${k.selector} (${k.owner})`)
  expect(stale, 'listed violations that are gone: take them off the list').toEqual([])
})
