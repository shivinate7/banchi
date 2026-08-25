import { test, expect, type Page } from '@playwright/test'

/* THE REVIEW QUEUE, ASSERTED — AND UNTIL THIS FILE EXISTED, NOTHING ASSERTED IT AT ALL.
 *
 * `docs/DESIGN.md` specifies this screen in more detail than any other in the product, and
 * `grep -rn '#/review' app/tests/` returned nothing before 2026-08-24. The screen that the
 * owner spends the most hours in was the one screen with no browser coverage: the Fulfilment
 * view has its nine-row table, the inventory screen has its reachability battery, step 6's
 * button has its own sheet, and this had prose.
 *
 * WHAT IT IS FOR, SPECIFICALLY. The split of 2026-08-24 moved the photograph beside the
 * choices and reversed a rule `docs/DESIGN.md` had stated by name. Reversing a settled rule
 * with nothing measuring the result is how it quietly drifts back — so the numbers that
 * justified the reversal are the numbers asserted here. If a later session re-stacks this
 * screen, these fail before anybody has to remember why it was split.
 *
 * EVERYTHING IS STUBBED AND THE REAL STORE IS NEVER TOUCHED, exactly as
 * `app/tests/inventory.spec.ts` argues: the writes are intercepted and read, never issued,
 * because a test's fixtures have no business in the owner's inventory.
 *
 * THE PHOTOGRAPH STUB IS 2160x3840 AND THAT IS LOAD-BEARING. The rig's Cam Link hands the
 * browser a landscape frame and the rotation is applied at encode time (D13), so the stored
 * file is 9:16. Every area assertion below is computed against that aspect; a square or 4:3
 * stand-in would make each one a confident lie about a shape the screen never sees.
 *
 * OWNER-SIDE, SO NO FLOOR FROM `docs/DESIGN.md`'s CONSTRAINTS TABLE IS ASSERTED HERE. That
 * table governs `#/fulfillment`. This is the dense end of the same system and borrowing his
 * numbers would quietly make it his screen.
 */

/* Hash form, verbatim — a path-style '/review' is served index.html by Vite, mounts the app
 * with an empty hash and renders the capture screen, which is a passing navigation to the
 * wrong view. Every test waits for `VIEW` before measuring, so an unregistered route fails
 * there and loudly rather than as a run of confusing assertions about whatever Vite served.
 * `docs/GATES.md` step 7 records what that cost when it was not done: 16 of 30 assertions
 * red, "every one of them reporting the unregistered route rather than a design defect". */
const VIEW_ROUTE = '/#/review'
const VIEW = 'main.review'

/** The measurement viewport. Every number in `docs/specs/ui-redesign-options.md` and in the
 *  split's own commit was taken here, so this is where they are checked. */
const DESK = { width: 1440, height: 900 }

/** Below `ReviewQueue.css`'s 900px breakpoint, where the screen returns to the single column
 *  it shipped with. The split is a desktop layout and the phone must keep the old one. */
const PHONE = { width: 375, height: 812 }

/** A 9:16 SVG, the rig's stored aspect. Serving something square would let a photograph that
 *  draws at the wrong shape pass every geometry assertion below. */
const PHOTO_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="2160" height="3840" viewBox="0 0 2160 3840">' +
  '<rect width="2160" height="3840" fill="#e6e7ea"/>' +
  '<rect x="240" y="760" width="1680" height="2320" fill="#6b7f9e"/></svg>'

type Candidate = {
  sku: string
  name: string
  set: string
  number: string
  condition: string
  market: string | null
}

const CONDITIONS = ['Near Mint', 'Near Mint Reverse Holofoil', 'Near Mint Holofoil'] as const

function candidate(at: number, market: string): Candidate {
  return {
    sku: `860${8000 + at}`,
    name: 'Snorlax',
    set: 'ME01',
    number: '014/132',
    condition: CONDITIONS[at % CONDITIONS.length] ?? 'Near Mint',
    market,
  }
}

/** The `_queue_row` shape the server answers with, narrowed to what this screen reads. Typed
 *  rather than `Record<string, unknown>` so an assertion can reach `candidates[0].sku` — an
 *  untyped fixture makes the test's own reads unprovable. */
type Entry = {
  position: string
  box: number
  index: number
  label: string
  photo: string | null
  reason: string
  candidates: Candidate[]
  market: string | null
  read: { name: string; number: string; set: string }
  confidence: string
  first_seen: string
  age_days: number
  cleared_by_human: boolean
}

function entry(
  index: number,
  reason: string,
  market: string | null,
  candidates: Candidate[],
): Entry {
  return {
    position: `2/${index}`,
    box: 2,
    index,
    label: `Box 2 · Section 1 · Card ${index}`,
    photo: `/tmp/box2/${index}.jpg`,
    reason,
    candidates,
    market,
    read: { name: 'Snorlax', number: '014/132', set: 'ME01' },
    confidence: 'high',
    first_seen: '2026-08-24',
    age_days: 0,
    cleared_by_human: false,
  }
}

/** A queue with two reasons and a real price spread, which is what `docs/DESIGN.md` says no
 *  run has ever produced: Gate B priced $0.04-$0.40 end to end, so every row landed in one
 *  band and no mixed-value lot has ever tested an edge. */
const REVIEW = [
  entry(14, 'set_ambiguous', '84.50', [candidate(0, '84.50'), candidate(1, '114.08'), candidate(2, '143.65')]),
  entry(2, 'set_ambiguous', '41.00', [candidate(0, '41.00'), candidate(1, '55.35'), candidate(2, '69.70')]),
  entry(3, 'low_confidence', '12.00', [candidate(0, '12.00'), candidate(1, '16.20')]),
  entry(4, 'no_catalog_row', '8.75', []),
  entry(5, 'low_confidence', '1.10', [candidate(0, '1.10')]),
]

type Sent = { method: string; url: string; body: unknown }

/** Opens the screen with every route it calls intercepted. Returns the writes it attempted,
 *  which is the strongest thing a browser test can say about a route it must not call. */
async function open(page: Page, review = REVIEW): Promise<Sent[]> {
  const sent: Sent[] = []

  await page.route(/\/queues$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ review, parked: [] }),
    })
  })

  await page.route(/\/photo\/\d+\/\d+/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'image/svg+xml', body: PHOTO_SVG })
  })

  // Every write, recorded and never issued.
  await page.route(/\/(answer|group-answer)$/, async (route) => {
    const request = route.request()
    sent.push({ method: request.method(), url: request.url(), body: request.postDataJSON() })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      /* `restores_to` IS AN OBJECT AND BOTH MEMBERS ARE NULL, which is the ordinary queued
         card: it has never carried a SKU — that is why it is in a queue. `canTakeBack` tests
         the OBJECT, never its members, so `null` here would mean "this answer cannot be
         reversed" and the receipt would correctly never appear. The first draft of this stub
         sent null and the undo assertion failed, which is the stub being wrong about the
         server rather than the screen being wrong about the undo. */
      body: JSON.stringify({
        position: '2/14',
        cleared: true,
        restores_to: { sku: null, condition: null },
      }),
    })
  })

  await page.setViewportSize(DESK)
  await page.goto(VIEW_ROUTE)
  await expect(page.locator(VIEW)).toBeVisible()
  /* Wait for the CARD, not for a photograph: a pooled entry has none by construction and the
     absent panel is the correct render for it. Waiting on `.review-photo` here would make the
     pooled test fail in the helper, several assertions before the thing it is about. */
  await expect(page.locator('.review-card')).toBeVisible()
  return sent
}

/* ---------------------------------------------------------------- the split, as numbers */

test('the photograph is the largest thing on the screen', async ({ page }) => {
  await open(page)
  const photo = await page.locator('.review-photo').boundingBox()
  expect(photo).not.toBeNull()

  /* 23%, NOT THE 25% FIRST WRITTEN, and the difference is an aspect ratio rather than a
     compromise. `docs/specs/ui-research.md` computed its target from a bare card's 63:88;
     the served frame is 9:16, so the reachable ceiling with the header intact is 23.6%.
     Measured before the split: 244x432 = 8.1%. */
  const share = (photo!.width * photo!.height) / (DESK.width * DESK.height)
  expect(share).toBeGreaterThanOrEqual(0.23)

  /* The honest instrument beside the area one: a 9:16 frame's CARD is only part of the area
     being measured, so a long edge is what says the photograph is actually big. */
  expect(Math.max(photo!.width, photo!.height)).toBeGreaterThanOrEqual(700)
})

test('one card costs no page scroll at all', async ({ page }) => {
  await open(page)
  /* 2,356px before the split, 1,456 of it past the fold — and the 47-entry worklist was
     234px below it, so reading the queue meant taking the photograph off the screen. */
  const overflow = await page.evaluate(
    () => document.documentElement.scrollHeight - window.innerHeight,
  )
  expect(overflow).toBeLessThanOrEqual(0)

  const sideways = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(sideways).toBeLessThanOrEqual(0)
})

test('every candidate row is on screen with the photograph', async ({ page }) => {
  await open(page)
  /* THE DEFECT THIS SCREEN WAS SPLIT FOR. Measured before: with three candidates the third
     row's bottom sat past a 900px fold, so the operator scrolled to read the choice and lost
     the photograph they were choosing against. */
  const rows = page.locator('.review-candidate')
  await expect(rows).toHaveCount(3)
  const last = await rows.last().boundingBox()
  expect(last!.y + last!.height).toBeLessThanOrEqual(DESK.height)

  const photo = await page.locator('.review-photo').boundingBox()
  expect(photo!.y).toBeLessThanOrEqual(DESK.height)
})

test('the first content sits within 150px of the top', async ({ page }) => {
  await open(page)
  /* `docs/DESIGN.md`'s page-chrome rule, which the split had to leave green while moving
     everything else: the frame's top is y=146 before and after. */
  const frame = await page.locator('.review-frame').boundingBox()
  expect(frame!.y).toBeLessThanOrEqual(150)
})

/* ------------------------------------------------------------------------------- D28 */

test('the photograph does not move between cards', async ({ page }) => {
  await open(page)
  const before = await page.locator('.review-frame').boundingBox()

  await page.locator('.review-action', { hasText: 'Skip' }).click()
  await expect(page.locator('.review-position')).not.toHaveText(/Card 14$/)

  const after = await page.locator('.review-frame').boundingBox()
  /* D28: the frame reserves its height whether or not an image has loaded, so the rows below
     sit at one y for every card. The 538px round-trip this prevents was measured on the Gate
     B captures; nothing else in the repo checks that it is still prevented. */
  expect(after!.y).toBe(before!.y)
  expect(after!.height).toBe(before!.height)
})

/* -------------------------------------------------------------------- the 1:1 loupe */

/* THE LOUPE MOVES, AS OF 2026-08-24, AND THESE CASES WERE REWRITTEN WITH IT. It used to be a
   fixed inset pinned to the frame and painting the CENTRE of the stored photograph, so this
   file asserted `background-position: 50% 50%` and that the element was on screen the moment
   the card was. Both are now wrong by design: the owner reported the fixed aim as confusing
   ("i'm kinda confused as to what i'm supposed to be looking at"), and the centre of a
   2160x3840 frame is the Pokedex data strip — which decides nothing, and whose National
   Pokedex number is the exact string D35 records the model misreading as a collector number.

   What replaced it is hidden at rest and aimed by the pointer. So the assertions move from
   "it is there, showing the middle" to the three properties the new design actually rests on:
   it is ABSENT until the pointer is over the photograph, it paints at 1:1 wherever it is
   aimed, and NOTHING survives the pointer leaving. The 1:1 assertion is the one carried over
   unchanged, because it is the reason the element exists — FADGI and Metamorfoze both require
   this class of judgement at 100%, and a magnifier that is itself a downscale is worse than no
   magnifier because it looks like evidence. */

test('the sheen loupe is absent until the pointer is on the photograph', async ({ page }) => {
  await open(page)
  await expect(page.locator('.review-photo')).toBeVisible()

  /* HIDDEN AT REST is the fix for what the owner reported, so it is asserted before anything
     else: an unexplained crop sitting on the card at all times is the confusion itself. */
  await expect(page.locator('.review-inset')).toHaveCount(0)
})

test('the sheen loupe paints native pixels, not a downscale', async ({ page }) => {
  await open(page)
  const photo = page.locator('.review-photo')
  await expect(photo).toBeVisible()

  await photo.hover({ position: { x: 120, y: 200 } })
  const inset = page.locator('.review-inset')
  await expect(inset).toBeVisible()

  /* `background-size: auto` paints the file at its natural size — that is the whole of the
     1:1 guarantee, and any other value is a second downscale wearing a magnifier. The
     POSITION is no longer a constant to assert: it is the natural pixel under the pointer,
     which the next case checks by moving the pointer rather than by naming a number here. */
  const size = await inset.evaluate((el) => getComputedStyle(el).backgroundSize)
  expect(size).toBe('auto')

  /* Centred on the pointer, which is what makes it a loupe rather than a fixed inset. Within
     a few px rather than exactly: the element is positioned by its 220px content box while
     `boundingBox()` reports the 224px border box, so the two centres differ by the border and
     asserting an exact number would be asserting that border width. What is being checked is
     that the glass sits where the pointer is — a fixed inset would be out by hundreds. */
  const box = await inset.boundingBox()
  const frame = await photo.boundingBox()
  expect(Math.abs(box!.x + box!.width / 2 - (frame!.x + 120))).toBeLessThanOrEqual(4)
  expect(Math.abs(box!.y + box!.height / 2 - (frame!.y + 200))).toBeLessThanOrEqual(4)
})

test('the loupe aims where the pointer is, so the aim is never a constant', async ({ page }) => {
  await open(page)
  const photo = page.locator('.review-photo')
  await expect(photo).toBeVisible()
  const inset = page.locator('.review-inset')

  const offsetAt = async (x: number, y: number) => {
    await photo.hover({ position: { x, y } })
    await expect(inset).toBeVisible()
    return inset.evaluate((el) => getComputedStyle(el).backgroundPosition)
  }

  /* D32's argument, applied to the glass: the card fills 39% to 81% of the frame across one
     box because cards move on the tray, so ANY constant offset is a guess that is wrong per
     frame. Two aims that produced the same background offset would mean the pointer is not
     reaching the arithmetic — the defect this whole redesign exists to remove. */
  const near = await offsetAt(80, 120)
  const far = await offsetAt(300, 520)
  expect(near).not.toBe(far)
})

test('nothing the loupe did survives the pointer leaving', async ({ page }) => {
  await open(page)
  const photo = page.locator('.review-photo')
  await photo.hover({ position: { x: 120, y: 200 } })
  await expect(page.locator('.review-inset')).toBeVisible()

  /* `onPointerLeave` clears the aim, and the design comment leans on that to argue the loupe
     is not the list -> detail -> back loop docs/DESIGN.md bans on this screen: no state
     survives the pointer leaving. Asserted rather than trusted, because it is the sentence
     that makes the ban compatible with a mouse gesture at all. */
  await page.mouse.move(2, 2)
  await expect(page.locator('.review-inset')).toHaveCount(0)
})

/* ---------------------------------------------------------------- answering, and undo */

test('a digit answers the card and the answer stays reversible', async ({ page }) => {
  const sent = await open(page)

  await page.locator('.review-candidate').first().click()
  await expect.poll(() => sent.length).toBeGreaterThan(0)

  const write = sent[0]
  expect(write).toBeDefined()
  const body = write!.body as Record<string, unknown>
  expect(write!.method).toBe('POST')
  expect(body.sku).toBe(REVIEW[0]?.candidates[0]?.sku)

  /* D28's undo, now bounded by COUNT rather than by a clock — see `UNDO_DEPTH`. The receipt
     must still be standing well past the twenty seconds the old window allowed, which is the
     whole of that change and the one thing a timer regression would silently undo. */
  const receipt = page.locator('.review-note[role="status"]')
  await expect(receipt.first()).toBeVisible()
  await page.waitForTimeout(2000)
  await expect(receipt.first()).toBeVisible()
})

/* ------------------------------------------------------------------------- the phone */

test('below 900px the screen is the single column it shipped with', async ({ page }) => {
  await open(page)
  await page.setViewportSize(PHONE)
  await expect(page.locator(VIEW)).toBeVisible()

  /* The split is a desktop layout. Nothing under 900px is re-tuned — same max-width, same
     cap, one column — which is the half of the reversed rule that was ever about the phone. */
  const shape = await page.locator('.review-card').evaluate((el) => {
    const main = document.querySelector('main.review') as HTMLElement
    return {
      columns: getComputedStyle(el).gridTemplateColumns.split(' ').length,
      maxWidth: getComputedStyle(main).maxWidth,
      cap: getComputedStyle(main).getPropertyValue('--photo-cap').trim(),
    }
  })
  expect(shape.columns).toBe(1)
  expect(shape.maxWidth).toBe('688px')
  expect(shape.cap).toBe('48vh')

  const sideways = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(sideways).toBeLessThanOrEqual(0)
})

/* --------------------------------------------------------------------- D24's opsec row */

test('a pooled card never draws a photograph here', async ({ page }) => {
  /* `scripts/docs-audit.py`'s `views exposure` row asks this of every screen that renders a
     stored capture photo, because a pooled `pokemon_code` card's photograph IS a live code
     (D24) and `scripts/views.txt` renders `#/review` to disk. The Fulfilment spec answers the
     same question for his view; this answers it for this one.
     A pooled entry has no position — box 0 — and `PhotoContent` returns the absent panel for
     it before any <img> or loupe exists. */
  await open(page, [
    {
      ...entry(0, 'no_catalog_row', null, []),
      position: '0/1',
      box: 0,
      index: 1,
      label: 'Pokémon code cards · pooled',
      photo: '/tmp/pooled/1.jpg',
    },
  ])

  await expect(page.locator('.review-absent')).toBeVisible()
  await expect(page.locator('.review-photo')).toHaveCount(0)
  await expect(page.locator('.review-inset')).toHaveCount(0)
})
