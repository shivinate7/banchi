import { test, expect } from '@playwright/test'
import { sealEveryTest } from './shell'

/* THE ROW SHAPES `#/gallery` DRAWS THAT NOTHING ELSE IN THIS APP EVER DRAWS.
 *
 * `docs/DEBTS.md` §5's remaining half: the kit sheet is "rendered by the build so it cannot go
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

/** The departed shell, and BOTH CLASSES TOGETHER are the thing under test. `is-gone` alone is
 *  any sold copy and `is-nobar` alone is any copy with no bar to draw; their conjunction is the
 *  one row that has left its box, which is what `isDeparted` decides. */
const DEPARTED_ROW = '.card-locations-row.is-gone.is-nobar'

/** A row with no bar that has NOT left — the pooled copy, and the copy the walk stands on. */
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

  /* ONE STATE WORD. The state cell holds up to three things — a `Viewing` marker, an order's
     `Wanted` claim, and the state pill — and a departed copy has only the last of them. Counting
     pills rather than reading text is what makes this fail if a marker starts appearing on a row
     that has left the box, which is a claim about a card nobody can walk to. */
  const pills = row.locator('.card-locations-state .bn-pill')
  await expect(pills).toHaveCount(1)
  await expect(pills).toHaveText('Sold')

  /* AND NOTHING WHERE AN ACTION WOULD BE. `Mark sold` on a copy that is already gone is the
     press this component refuses to offer, and the state pill beside it has already said so —
     `CardLocations.tsx` renders null rather than a disabled control or a second word. */
  await expect(row.locator('.card-locations-action')).toHaveText('')
})

test('the pooled row is a second no-bar shell, and it has not left', async ({ page }) => {
  /* Two rows carry no bar without having left: the pooled copy and the current one. Both are
     real shells and the count is asserted so a fixture that quietly loses one is caught. */
  await expect(page.locator(NOBAR_PRESENT)).toHaveCount(2)

  /* The pooled one names itself. `.card-locations-boxname` is rendered only by the pooled branch
     of `OwnerRows` — a located row puts the box's name inside `PositionLabel`'s note instead —
     so this is the pooled shell and not a lookalike. */
  const pooled = page.locator(`${NOBAR_PRESENT}:has(.card-locations-boxname)`)
  await expect(pooled).toHaveCount(1)
  await expect(pooled.locator('.card-locations-boxname')).toContainText('pooled ·')

  /* AND NO POSITION LABEL ANYWHERE ON IT (D24). A pool has no coordinate; a row that fell back
     to `box/index` would print a slot number for a card that is in no slot, which is the one
     thing that ruling forbids. */
  await expect(pooled.locator('.position-parts')).toHaveCount(0)
})

test('the current row is drawn, and it is a shell of its own', async ({ page }) => {
  /* `currentKey` is passed to the owner specimen so the `is-current` treatment is on the sheet
     too — the third of the three reasons a row carries no bar, and the only one that is a
     statement about where the walk stands rather than about the card. */
  const current = page.locator('.card-locations-row.is-current')
  await expect(current).toHaveCount(1)
  await expect(current).toHaveAttribute('aria-current', 'true')
  await expect(current.locator('.card-locations-viewing')).toHaveText('Viewing')
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
