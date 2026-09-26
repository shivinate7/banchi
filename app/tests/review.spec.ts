import { test, expect, type Page } from '@playwright/test'
import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'
import type { Place } from '../src/types'
import { runRow } from './routeFixtures'

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
  /* Half of what `rarity_claim_mismatch` means, on the wire since 2026-09-11 and absent on
     every entry queued before it — which is why the fixtures here carry both shapes. */
  rarity?: string
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
  read: { name: string; number: string; set: string; rarity_claim?: string[] }
  confidence: string
  first_seen: string
  age_days: number
  cleared_by_human: boolean
  /* Optional, like the wire's own field (`QueueEntryWire.place`): absent on every entry
     above, present on the F3 fixture below, which is the one place this file exercises
     `CaptionOrder` — the pill's "back … this card … front" line was otherwise never
     rendered by any test in this file at all. */
  place?: Place
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

/* D46 — the export rows a lookup offers for a card the pipeline found nothing for. Modelled
   on the real case: run 2026-08-29-box1-01 read `Master Yi, Wuju Master` as `Wuju Master`,
   dropping the champion, so an exact name match finds nothing and only a substring does. */
const CATALOG_ROWS: Candidate[] = [
  {
    sku: '9192027',
    name: 'Master Yi, Wuju Master',
    set: 'Unleashed',
    number: '191/219',
    condition: 'Near Mint Foil',
    market: '0.12',
  },
  {
    sku: '9197294',
    name: 'Master Yi, Wuju Master (Overnumbered)',
    set: 'Unleashed',
    number: '231/219',
    condition: 'Near Mint Foil',
    market: '51.52',
  },
]

/** A queue entry the pipeline offered NO rows for — `no_catalog_row` with zero candidates.
 *  Before D46 this was a dead end: the answer route refuses it as `no_candidates`, so the
 *  only moves were skip and stand-down. */
const NO_ROWS: Entry[] = [entry(14, 'no_catalog_row', null, [])]

/** The page's enter animation, finished.
 *
 *  THE SAME ARGUMENT `fontsReady.ts` MAKES ABOUT THE SWAP WINDOW, one branch over: `.bn-page`
 *  slides its content in over `--bn-t-slow`, so a rect read while it is still running is a
 *  measurement of a transform rather than of a layout — the frame reads 3.5px low and settles
 *  after. It cost the D28 case below a red that had nothing to do with the photograph. It
 *  weakens nothing: no threshold moves, and a page that really did shift is still shifted once
 *  the animation it was riding has ended. */
async function settleEnter(page: Page): Promise<void> {
  await page.waitForFunction(() => {
    const main = document.querySelector('main')
    return main !== null && main.getAnimations().every((one) => one.playState === 'finished')
  })
}

type Sent = { method: string; url: string; body: unknown }

/** Opens the screen with every route it calls intercepted. Returns the writes it attempted,
 *  which is the strongest thing a browser test can say about a route it must not call.
 *
 *  `catalogRows` defaults to `CATALOG_ROWS`, D77's own fixture — a fourth parameter rather
 *  than a second `page.route` call after this one returns, because the arrival fetch this
 *  screen makes on a zero-candidate entry has already gone through `open()`'s own `goto` by
 *  the time a caller could register anything after it (found running `openWide`'s first
 *  draft: a route added post-`open()` never won a single request, and every assertion read
 *  the two-row default instead). `truncated`/`found` are read off `catalogRows.length`
 *  rather than pinned at `false`, so a caller that wants to prove D23's own ceiling can pass
 *  a fixture the client should treat as cut off. */
async function open(
  page: Page,
  review = REVIEW,
  parked: Entry[] = [],
  catalogRows: Candidate[] = CATALOG_ROWS,
): Promise<Sent[]> {
  const sent: Sent[] = []

  await page.route(/\/queues$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ review, parked }),
    })
  })

  await page.route(/\/photo\/\d+\/\d+/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'image/svg+xml', body: PHOTO_SVG })
  })

  /* D46's catalog lookup. Fulfilled from `catalogRows`, which the zero-candidate test
     overrides; every other test in this file has candidates on every entry and so never
     reaches it. Recorded into `sent` as a GET so a test can assert it was asked at all —
     the suggest-on-arrival property is otherwise invisible. */
  await page.route(/\/catalog\?/, async (route) => {
    const request = route.request()
    sent.push({ method: request.method(), url: request.url(), body: null })
    const url = new URL(request.url())
    const q = url.searchParams.get('q') ?? ''
    const rows = q === '' || catalogRows.some((r) => r.name.toLowerCase().includes(q.toLowerCase()))
      ? catalogRows
      : []
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        box: 2,
        index: 14,
        game: 'riftbound',
        query: q || 'Wuju Master',
        searched: q !== '',
        rows,
        found: rows.length,
        truncated: false,
      }),
    })
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
  /* THE FACES BEFORE THE RULER. Every geometry case in this file measures type, and
     `index.html` fetches its faces with `display=swap` — so a rect read inside the swap window
     is a measurement of the fallback. It cost this file a real red: the frame's top was read
     4px apart either side of a Skip and the case that owns D28's no-movement property failed
     on a font arriving, not on the photograph moving. */
  await settleFonts(page)
  await settleEnter(page)
  /* Wait for the CARD, not for a photograph: a pooled entry has none by construction and the
     absent panel is the correct render for it. Waiting on `.review-photo` here would make the
     pooled test fail in the helper, several assertions before the thing it is about. */
  await expect(page.locator('.review-card')).toBeVisible()
  return sent
}

/* ---------------------------------------------------------------- the split, as numbers */

/* NOTHING HERE MAY REACH THE CAPTURE SERVER, AND THIS FILE PAID FOR THE RULE. Six cases below
   spent thirty seconds each on a detached switch, and two more failed as bare pixel counts,
   because the shell's `/status` went to whatever answers this checkout's capture port — the
   owner's real server in the main tree, nothing at all in a worktree, where the shell then drew
   its 44px offline banner above every measurement. Fixed by hand on 2026-09-05 and folded into
   the shared mechanism here, so there is one spelling of it rather than two.
   `app/tests/shell.ts` carries the argument, including the two invariants this call replaces:
   it asserts the banner is absent and that no route boundary is showing its crash page. */
sealEveryTest()

test('the photograph is the largest thing on the screen', async ({ page }) => {
  await open(page)
  const photo = await page.locator('.review-photo').boundingBox()
  expect(photo).not.toBeNull()

  /* 23%, NOT THE 25% FIRST WRITTEN, and the difference is an aspect ratio rather than a
     compromise. `docs/specs/ui-research.md` computed its target from a bare card's 63:88;
     the served frame is 9:16, so the reachable ceiling with the header intact is 23.6%.
     Measured before the split: 244x432 = 8.1%.

     IT WENT RED ON THIS BRANCH AND THE FLOOR WAS NOT MOVED TO MEET THE BUILD. The rebuilt
     screen drew 692x389 at 1440x900 — 20.8% — and the whole shortfall was vertical chrome:
     24px page padding-top, 72px pagehead plus a 24px margin, 34px of filter strip plus 24px
     less an 8px pull-up, 24px of well padding, 64px page padding-bottom. 258px, of which the
     stylesheet counted 208 — a second, separate defect that ran the document 50px past a 900px
     viewport.

     The two pulled opposite ways, which is why the answer was not a number. Correcting the
     subtrahend alone would have fitted the document by taking the photograph DOWN to 642px
     (17.9%). So the chrome was cut to 172px instead, on D32's rule that the pixel budget is
     spent on the card and not on the desk — 86px off the page's own padding, the header's
     margin, the filter strip's margin and the well's — and the photograph is 728px, 23.0%.
     The arithmetic is written above `--rv-chrome` in `ReviewQueue.css`, where the pieces are. */
  const share = (photo!.width * photo!.height) / (DESK.width * DESK.height)
  expect(share).toBeGreaterThanOrEqual(0.23)

  /* The honest instrument beside the area one: a 9:16 frame's CARD is only part of the area
     being measured, so a long edge is what says the photograph is actually big. */
  expect(Math.max(photo!.width, photo!.height)).toBeGreaterThanOrEqual(700)
})

test('answering a card costs no scrolling, and the page never scrolls sideways', async ({
  page,
}) => {
  await open(page)
  /* 2,356px before the split, 1,456 of it past the fold — and the 47-entry worklist was
     234px below it, so reading the queue meant taking the photograph off the screen.

     THE DOCUMENT-HEIGHT ASSERTION IS BACK, AND ITS ABSENCE WAS A REAL DEFECT RATHER THAN A
     threshold anybody chose. It was re-pointed to the surfaces below because
     `ReviewQueue.css`'s photo height under-counted the chrome around the well — 208px counted
     against 258px real — so at 1440x900 the document ran 50px past the viewport and the bottom
     of the photo WELL sat just off the fold. The chrome is 172px now, cut on D32's rule that the
     budget is spent on the card rather than the desk, and the document fits. Both instruments
     are kept: this one catches an overflow anywhere, the three below say WHICH surface left the
     screen, and a failure in one but not the other is the useful signal. */
  /* THE RULER AND THE TYPE HAVE TO AGREE ABOUT WHICH FACE IS ON SCREEN. This case takes four pixel
     measurements and was the only one in this directory that measured without settling the faces
     first. `app/index.html` fetches with `&display=swap`, which is a deliberate instruction to paint
     in the fallback and re-lay-out when the real face arrives — right for a reader, wrong for a
     ruler. Under `make design-check`'s parallel load the swap window is wide enough to be measured
     inside: observed at 88px over the viewport on a run where it passes alone every time.
     `fontsReady.ts` carries the whole argument. It weakens nothing — a false statement is still
     false, and the document either fits or it does not. */
  await settleFonts(page)

  const tall = await page.evaluate(() => document.documentElement.scrollHeight - window.innerHeight)
  expect(tall).toBeLessThanOrEqual(0)

  const stage = await page.locator('.review-frame').boundingBox()
  expect(stage!.y).toBeGreaterThanOrEqual(0)

  const rows = page.locator('.review-candidate')
  const last = await rows.last().boundingBox()
  expect(last!.y + last!.height).toBeLessThanOrEqual(DESK.height)

  /* Skip, Search the export, Close — the three presses that move past a card. */
  const actions = await page.locator('.review-actions').boundingBox()
  expect(actions!.y + actions!.height).toBeLessThanOrEqual(DESK.height)

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

test('the page chrome does not push the card down the screen', async ({ page }) => {
  await open(page)
  /* `docs/DESIGN.md`'s page-chrome rule. It used to be asserted as `.review-frame` at y<=150,
     because the photograph WAS the first thing on the page — this screen now leads with a
     title, a progress reading and the reason filters, all of which are content rather than
     chrome, and the frame starts below them.

     SO IT IS ASSERTED IN TWO PARTS INSTEAD, neither of which is the old number moved: the
     page's own first content is still near the top, and everything above the card together
     costs less than a quarter of the viewport. A re-added banner, a second toolbar or a
     restored lede block fails this exactly as it failed the old form. */
  const head = await page.locator('.review-pagehead').boundingBox()
  expect(head!.y).toBeLessThanOrEqual(150)

  const body = await page.locator('.review-body').boundingBox()
  expect(body!.y).toBeLessThan(DESK.height / 4)
})

/* ------------------------------------------------------------------------------- D28 */

/** The frame's place in the DOCUMENT, and its height, read in one go.
 *
 *  DOCUMENT COORDINATES RATHER THAN THE VIEWPORT, and the reason is a defect rather than a
 *  preference: this branch's page is 95px taller than the fold at 1440x900 (see the report on
 *  `--rv-photo-h`), so a click that Playwright has to scroll to reach moves the whole document
 *  under the sticky stage and a viewport `y` reads 92px lower for a layout that never changed.
 *  D28's claim is about the LAYOUT — the frame holds its box whether or not an image has
 *  arrived — and this is that claim measured where a scroll cannot forge it. Both reads happen
 *  inside one `evaluate`, for the reason `fontsReady.ts` gives about splitting a measurement. */
async function framePlace(page: Page): Promise<{ y: number; height: number }> {
  return page.locator('.review-frame').evaluate((el) => {
    const box = el.getBoundingClientRect()
    return { y: box.y + window.scrollY, height: box.height }
  })
}

test('the photograph does not move between cards', async ({ page }) => {
  await open(page)
  const before = await framePlace(page)

  await page.locator('.review-action', { hasText: 'Skip' }).click()
  /* AGAINST THE `aria-label`, NOT THE RENDERED TEXT, because the rendered text no longer contains
     the string this was matching. `.review-position`'s innerText is now `BOX 2SECTION 1CARD14` —
     de-dotted and uppercased by `PositionLabel` — so `/Card 14$/` can never match for ANY card and
     the assertion would go on passing while detecting nothing. That is the silently-weakened shape
     D16 forbids, and this case's whole job is to prove the Skip actually advanced. The server
     string survives verbatim on `aria-label`, which is what makes it the right thing to match.

     `.position-run`, NOT `.position-parts`: the caption sits inside the photo well now and
     `PositionLabel` is asked for its one-dimensional `flow="run"` form there. Both forms carry
     the server's string verbatim on `aria-label` — that is the component's stated contract and
     the reason the selector can move without the assertion changing meaning. */
  await expect(page.locator('.review-position .position-run')).not.toHaveAttribute(
    'aria-label',
    /Card 14$/,
  )

  const after = await framePlace(page)
  /* D28: the frame reserves its height whether or not an image has loaded, so the rows below
     sit at one y for every card. The 538px round-trip this prevents was measured on the Gate
     B captures; nothing else in the repo checks that it is still prevented. */
  expect(after.y).toBe(before.y)
  expect(after.height).toBe(before.height)
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
  await page.clock.install()   // D136: the two seconds below are jumped, not slept
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
  // A fake clock advanced two seconds fires every timer due in them; a receipt that a timer
  // would have taken away is gone by the second read. Mutation-tested against exactly that.
  await page.clock.runFor(2000)
  await expect(receipt.first()).toBeVisible()
})

/* UX-205: a write the server cannot restore (`restores_to: null`, never an object) used to
 * write NO receipt at all — `remember` ran only when `canTakeBack` was true. Six of nine
 * answers in one real session drew nothing on screen. The receipt is unconditional now; only
 * its Undo control depends on `restores_to`. */
test('a write with no restores_to still gets a receipt, with no Undo on it', async ({ page }) => {
  const sent = await open(page)
  await page.route(/\/answer$/, async (route) => {
    const request = route.request()
    sent.push({ method: request.method(), url: request.url(), body: request.postDataJSON() })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ position: '2/14', cleared: true, restores_to: null }),
    })
  })

  await page.locator('.review-candidate').first().click()
  await expect.poll(() => sent.filter((s) => s.method === 'POST').length).toBe(1)

  const receipt = page.locator('.review-note[role="status"]')
  await expect(receipt.first()).toBeVisible()
  await expect(receipt.first()).toContainText('Answered as')
  await expect(receipt.getByRole('button', { name: 'Undo' })).toHaveCount(0)

  // The session list carries the same receipt, and the same absence of Undo.
  await page.locator('.review-queue-toggle').click()
  await expect(page.locator('.review-session-row')).toHaveCount(1)
  await expect(page.locator('.review-session-row').getByRole('button', { name: 'Undo' })).toHaveCount(0)
})

test('only the newest answer keeps a tray, and the rest are a rail three deep', async ({
  page,
}) => {
  const sent = await open(page)

  /* THE UNDO IS A DEPTH, NOT A CLOCK, AND THE RAIL IS WHERE THE DEPTH LIVES. One answer at a
     time is the whole shape of this screen, so a stack of receipts in the flow would push the
     next card down the page by however many cards the operator had just answered. The newest
     stays beside the card it undoes; the older ones become rows in the queue rail. */
  for (let at = 0; at < 4; at += 1) {
    await page.locator('.review-candidate').first().click()
    await expect.poll(() => sent.filter((s) => s.method === 'POST').length).toBe(at + 1)
  }

  await expect(page.locator('.review-receipt')).toHaveCount(1)

  /* THE REST ARE IN THE QUEUE, WHICH AT THIS WIDTH IS A DRAWER — the third column does not fit
     beside the sidebar until 1500px, so the rail is opened by the Queue button rather than
     standing open. Opening it is how the operator reaches the older answers, so it is how this
     case reaches them too. */
  await page.locator('.review-queue-toggle').click()
  await expect(page.locator('.review-session-tally')).toContainText('4 answered')

  /* THREE DEEP, AND THE FOURTH IS NOT DROPPED. A rail that silently forgot the oldest answer
     would be an undo the operator cannot reach for a write that already happened, so the cap
     is a fold rather than a discard. */
  await expect(page.locator('.review-session-row')).toHaveCount(3)
  const more = page.getByRole('button', { name: /more$/ })
  await expect(more).toBeVisible()
  await more.click()
  await expect(page.locator('.review-session-row')).toHaveCount(4)

  // Every one of them is still reversible — the rail is the undo, not a log of it.
  await expect(
    page.locator('.review-session-row').last().getByRole('button', { name: 'Undo' }),
  ).toBeVisible()
})

/* ------------------------------------------------------------------------- the phone */

test('below 900px the screen is the single column it shipped with', async ({ page }) => {
  await open(page)
  await page.setViewportSize(PHONE)
  await expect(page.locator(VIEW)).toBeVisible()

  /* The split is a desktop layout, and below 900px the card is one column with the
     photograph first — which is the half of the reversed rule that was ever about the phone.

     THE TWO PINS THAT WENT ARE PINS ON A STYLESHEET, NOT ON BEHAVIOUR. `main.review` no longer
     sets its own `max-width: 688px` or a `--photo-cap`; the page frame carries the width and
     the photo well sizes itself from `--rv-photo-h`. Neither number is reachable from a phone
     viewport anyway — at 375px the cap that decides the layout is the viewport. What the case
     is about is the shape the operator gets, so that is what is left: one column, the
     photograph above the rows, and nothing off the side. */
  const columns = await page
    .locator('.review-card')
    .evaluate((el) => getComputedStyle(el).gridTemplateColumns.split(' ').length)
  expect(columns).toBe(1)

  const stage = await page.locator('.review-stage').boundingBox()
  const verdict = await page.locator('.review-verdict').boundingBox()
  expect(stage!.y).toBeLessThan(verdict!.y)

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

/* ---------------------------------------------------------- D46: the card with no rows */

/* Before this, the zero-candidate arm drew one paragraph of prose saying the only move was
   to skip and pointing at a command in a terminal. Both halves were stale: D37 had put a
   stand-down on this very screen, and the row the pipeline missed was usually sitting in the
   export the whole time. These four cases are the properties that repair depends on. */

test('a card the pipeline found nothing for is offered rows out of the export', async ({
  page,
}) => {
  const sent = await open(page, NO_ROWS)

  // Asked on ARRIVAL, with no query — the owner's ask was that the screen suggest rather
  // than wait to be asked. This is the only assertion that can see that it was asked at all.
  await expect.poll(() => sent.filter((s) => s.url.includes('/catalog?')).length).toBe(1)
  expect(sent[0]!.url).toContain('q=')
  expect(sent[0]!.method).toBe('GET')

  const rows = page.locator('.review-catalog .review-candidate')
  await expect(rows).toHaveCount(CATALOG_ROWS.length)
  await expect(rows.first()).toContainText('Master Yi, Wuju Master')
  // The digits mean these rows, exactly as they mean the pipeline's own.
  await expect(rows.first().locator('.review-key')).toHaveText('1')
})

test('choosing a suggested row answers the card and says the row came from the catalog', async ({
  page,
}) => {
  const sent = await open(page, NO_ROWS)
  await page.locator('.review-catalog .review-candidate').first().click()

  await expect.poll(() => sent.filter((s) => s.method === 'POST').length).toBeGreaterThan(0)
  const write = sent.find((s) => s.method === 'POST')!
  const body = write.body as { sku: string; condition: string; from_catalog?: boolean }
  expect(body.sku).toBe(CATALOG_ROWS[0]!.sku)
  expect(body.condition).toBe(CATALOG_ROWS[0]!.condition)
  /* THE FLAG IS THE WHOLE POINT OF THE ROUTE CHANGE. Without it the server refuses this
     write as `no_candidates`, which is the guard D46 deliberately left standing for every
     answer that does not come from the catalog. */
  expect(body.from_catalog).toBe(true)
})

test('an ordinary answer carries no catalog flag at all', async ({ page }) => {
  const sent = await open(page)
  await page.locator('.review-candidate').first().click()

  await expect.poll(() => sent.filter((s) => s.method === 'POST').length).toBeGreaterThan(0)
  const body = sent.find((s) => s.method === 'POST')!.body as { from_catalog?: boolean }
  /* Absent, not false. Every answer this screen has ever written goes through one call, and
     a flag about D46 riding on all of them would put a claim about how the row was found
     onto thousands of answers that have nothing to do with it. */
  expect(body.from_catalog).toBeUndefined()
})

test('the search box does not answer the card when a digit is typed into it', async ({
  page,
}) => {
  const sent = await open(page, NO_ROWS)
  const box = page.locator('.review-catalog-input')
  await box.click()
  await box.fill('1')

  /* THE NEGATIVE CASE, and it is the one that matters. The digits on this screen answer the
     card; an input that swallowed one would be fine, but an input that did NOT would write a
     SKU onto a real card while the operator was typing a collector number. `isEditableTarget`
     is what stops it, and nothing in the type system says so. */
  await page.waitForTimeout(150)
  expect(sent.filter((s) => s.method === 'POST')).toHaveLength(0)
  await expect(box).toHaveValue('1')
})

/* ---------------------------------- D23 amendment: no cutoff, and "Show N more" */

/* `4/383` on the owner's real store: `GET /review/4/383/catalog?q=Calm%20Rune` found 16
   rows and the server used to send 9. This fixture is that shape — sixteen rows, one
   query — over `pipeline/join.py:rank_by_claims`'s own real Riftbound fixture data
   (`fixtures/riftbound_export_untouched.csv`), so the SKUs and names here are the real
   ones T3's and T7's own harness tests assert against, not invented. */
const WIDE_CATALOG_ROWS: Candidate[] = [
  { sku: '8925762', name: 'Calm Rune (R02a)', set: 'Origins', number: '042a/298', condition: 'Near Mint Foil', market: '3.10', rarity: 'Showcase' },
  { sku: '9139842', name: 'Calm Rune (R02a)', set: 'Spiritforged', number: 'R02a', condition: 'Near Mint Foil', market: '2.85', rarity: 'Showcase' },
  { sku: '9277737', name: 'Calm Rune (R02a)', set: 'Unleashed', number: 'R02a', condition: 'Near Mint Foil', market: '2.40', rarity: 'Showcase' },
  { sku: '9436656', name: 'Calm Rune (R02a)', set: 'Vendetta', number: 'R02a', condition: 'Near Mint Foil', market: '2.55', rarity: 'Showcase' },
  { sku: '8925752', name: 'Calm Rune', set: 'Origins', number: '042/298', condition: 'Near Mint', market: '0.12', rarity: 'Common' },
  { sku: '8925757', name: 'Calm Rune', set: 'Origins', number: '042/298', condition: 'Near Mint Foil', market: '0.20', rarity: 'Common' },
  { sku: '9011917', name: 'Calm Rune (R02b)', set: 'Riftbound Organized Play Promotional Cards', number: '042b/298', condition: 'Near Mint Foil', market: '0.30', rarity: 'Promo' },
  { sku: '9139616', name: 'Calm Rune', set: 'Spiritforged', number: 'R02', condition: 'Near Mint', market: '0.10', rarity: 'Common' },
  { sku: '9314061', name: 'Calm Rune', set: 'Unleashed', number: 'R02', condition: 'Near Mint', market: '0.10', rarity: 'Common' },
  { sku: '9314066', name: 'Calm Rune', set: 'Unleashed', number: 'R02', condition: 'Near Mint Foil', market: '0.18', rarity: 'Common' },
  { sku: '9405193', name: 'Calm Rune', set: 'Vendetta', number: 'R02', condition: 'Near Mint', market: '0.10', rarity: 'Common' },
  { sku: '9445915', name: 'Calm Rune', set: 'Vendetta', number: 'R02', condition: 'Near Mint Foil', market: '0.18', rarity: 'Common' },
  { sku: '9012001', name: 'Calm Rune (R02c)', set: 'Riftbound Organized Play Promotional Cards', number: 'R02c', condition: 'Near Mint', market: '0.25', rarity: 'Promo' },
  { sku: '9012002', name: 'Calm Rune (R02b)', set: 'Riftbound Organized Play Promotional Cards', number: 'R02b', condition: 'Near Mint Foil', market: '0.30', rarity: 'Promo' },
  { sku: '9012003', name: 'Calm Rune', set: 'Origins', number: '042/298', condition: 'Near Mint', market: '0.12', rarity: 'Common' },
  { sku: '9012004', name: 'Calm Rune', set: 'Origins', number: '042/298', condition: 'Near Mint Foil', market: '0.20', rarity: 'Common' },
]

const WIDE_ROWS: Entry[] = [
  { ...entry(383, 'set_ambiguous', null, []), read: { name: 'Calm Rune', number: 'R02', set: '', rarity_claim: ['Showcase'] } },
]

async function openWide(page: Page): Promise<Sent[]> {
  return open(page, WIDE_ROWS, [], WIDE_CATALOG_ROWS)
}

test('nine rows are keyed, and the rest wait behind "Show N more"', async ({ page }) => {
  await openWide(page)

  const rows = page.locator('.review-catalog .review-candidate')
  await expect(rows).toHaveCount(9)
  await expect(rows.nth(3).locator('.review-key')).toHaveText('4')
  // The claim-agreeing rows lead, so the ninth key still belongs to a row the number's own
  // five Commons never offered — the whole point of the widen this amendment builds.
  await expect(rows.first()).toContainText('Calm Rune')

  const more = page.getByRole('button', { name: /Show \d+ more/ })
  await expect(more).toBeVisible()
  await expect(more).toHaveText('Show 7 more')

  await more.click()
  await expect(rows).toHaveCount(16)
  await expect(more).toHaveCount(0)
  // Past the ninth, a row is mouse-only — the same floor `CandidateButton` has always held
  // for a row past `MAX_KEYED_CANDIDATES`, unchanged by where the cutoff used to sit.
  await expect(rows.nth(9).locator('.review-key-blank')).toBeVisible()
})

test('"Show N more" reveals rows already on the wire, never a second fetch', async ({ page }) => {
  const sent = await openWide(page)
  await page.getByRole('button', { name: /Show \d+ more/ }).click()
  await expect(page.locator('.review-catalog .review-candidate')).toHaveCount(16)

  // One GET on arrival, none from the press — the wire already carried all 16.
  await expect
    .poll(() => sent.filter((s) => s.url.includes('/catalog?')).length)
    .toBe(1)
})

/** `.review-card`'s own bounding shape, sampled the way `confirm-identity.spec.ts`'s own
 *  `outsideThePanel` samples `.browse-card`'s: everything on the page OUTSIDE the panel a
 *  press lands in, keyed by a stamped id so a re-render of the SAME element is still the
 *  same row here. NOT AN IMPORT of that file's own helper — importing a spec file re-runs
 *  every `test()` it registers as a module side effect, so each file keeps its own copy. */
type Placed = { label: string; x: number; y: number }

/** POSITION ONLY, NOT HEIGHT — the one deliberate difference from
 *  `confirm-identity.spec.ts`'s own `outsideThePanel`. That press never changes the
 *  page's height at all, so comparing height caught a real move there. This press adds
 *  rows BELOW the panel BY DESIGN, so every block ancestor of `.review-card` legitimately
 *  grows taller (`div.review-body`, `main.review`, `.bn-shell`, …) without their own
 *  top-left corner ever moving — measured: every ancestor's `x,y` held exactly still
 *  while its height grew from 1,177px to 1,621px. Comparing height here would fail on the
 *  feature working as designed, not on a defect. */
async function outsideThePanel(page: Page): Promise<Record<string, Placed>> {
  return await page.evaluate(() => {
    const out: Record<string, Placed> = {}
    const stamp = () => `n${Math.random().toString(36).slice(2)}`
    for (const el of Array.from(document.querySelectorAll<HTMLElement>('body *'))) {
      if (el.closest('.review-card') !== null) continue
      let fixed = false
      for (let a: HTMLElement | null = el; a !== null && a !== document.body; a = a.parentElement) {
        if (getComputedStyle(a).position === 'fixed') {
          fixed = true
          break
        }
      }
      if (fixed) continue
      const r = el.getBoundingClientRect()
      if (r.width === 0 && r.height === 0) continue
      if (el.dataset.stableId === undefined) el.dataset.stableId = stamp()
      const cls =
        typeof el.className === 'string' && el.className !== '' ? `.${el.className.trim().split(/\s+/)[0]}` : ''
      out[el.dataset.stableId] = { label: `${el.tagName.toLowerCase()}${cls}`, x: r.x, y: r.y }
    }
    return out
  })
}

// A ONE-PIXEL ROUNDING FLOOR, MEASURED RATHER THAN GUESSED AT. Over the same page growth
// (1,177px to 1,621px) three sidebar/header icons — nowhere near `.review-catalog` — read
// one device pixel off between two independently `settled()` samples, both stable across
// 40 re-reads each. That is sub-pixel layout rounding from the taller document, not a
// human-visible shift; a threshold above 1px would start hiding the moves this sweep
// exists to catch.
const ROUNDING_FLOOR_PX = 1

function whatMoved(before: Record<string, Placed>, after: Record<string, Placed>): string[] {
  const moved: string[] = []
  for (const [id, was] of Object.entries(before)) {
    const now = after[id]
    if (now === undefined) continue
    if (Math.abs(now.x - was.x) <= ROUNDING_FLOOR_PX && Math.abs(now.y - was.y) <= ROUNDING_FLOOR_PX) continue
    moved.push(
      `${was.label} @ ${Math.round(was.x)},${Math.round(was.y)}   ->   ${now.label} @ ${Math.round(now.x)},${Math.round(now.y)}`,
    )
  }
  return moved
}

/** Sampled twice, 75ms apart, until two reads agree — `confirm-identity.spec.ts`'s own
 *  `settled()`, read for the before and after samples the D118 sweep below takes. */
async function settled(page: Page, tries = 40): Promise<Record<string, Placed>> {
  let last = await outsideThePanel(page)
  for (let i = 0; i < tries; i += 1) {
    await page.waitForTimeout(75)
    const next = await outsideThePanel(page)
    if (JSON.stringify(next) === JSON.stringify(last)) return next
    last = next
  }
  return last
}

test('"Show N more" adds rows below and moves nothing outside the card panel (D118)', async ({
  page,
}) => {
  await openWide(page)
  const more = page.getByRole('button', { name: /Show \d+ more/ })
  await expect(more).toBeVisible()
  // `confirm-identity.spec.ts`'s own precedent: scrolled into view BEFORE the "before"
  // sample, so the click's own actionability scroll is not read as something the PRESS
  // moved — the sweep is about what the press's EFFECT moves, not what reaching the
  // button on a tall panel costs.
  await more.scrollIntoViewIfNeeded()

  const before = await settled(page)
  await more.click()
  await expect(page.locator('.review-catalog .review-candidate')).toHaveCount(16)
  const after = await settled(page)

  const moved = whatMoved(before, after)
  expect(
    moved,
    `${moved.length} element(s) outside the card panel moved on the press:\n${moved.slice(0, 12).join('\n')}`,
  ).toHaveLength(0)
})

/* ------------------------------------- D77: the rows are there and they are the wrong card */

/* THE CASE D46 COULD NOT REACH, and it is not hypothetical: box 3 card 66 in the owner's own
   store, and the only open entry in it. `Nasus, Ascended` was read with its number misread as
   `8/298` — a REAL key in that export, belonging to `Get Excited!` — so the entry carries two
   confident candidate rows for a different card at $0.07 and $0.29, while the card's own row
   (`046/166`, Near Mint Foil, $0.74) sits in the same file. D46 offered the export only where
   the pipeline offered nothing, so the only moves here were to answer with a wrong row, skip
   forever, or close the card.

   The fixture keeps the real shape rather than the real strings' spirit only: the candidates
   are a DIFFERENT NAME from the read, which is the whole diagnostic. */
const WRONG_ROWS: Entry[] = [
  {
    ...entry(66, 'rarity_claim_mismatch', '0.07', [
      {
        sku: '8925477',
        name: 'Get Excited!',
        set: 'Origins',
        number: '008/298',
        condition: 'Near Mint',
        market: '0.07',
      },
      {
        sku: '8925482',
        name: 'Get Excited!',
        set: 'Origins',
        number: '008/298',
        condition: 'Near Mint Foil',
        market: '0.29',
      },
    ]),
    read: { name: 'Nasus, Ascended', number: '8/298', set: '' },
  },
]

test('an entry with rows is not offered the export unasked', async ({ page }) => {
  const sent = await open(page, WRONG_ROWS)
  await expect(page.locator('.review-candidate').first()).toContainText('Get Excited!')

  /* D46'S SECOND ARGUMENT, KEPT. It refused to fetch a catalog beside a good list of rows —
     "a second, looser list beside a good one is how a screen teaches you to stop reading the
     first" — and that is an argument about what appears UNASKED, which D77 does not touch.
     The timeout is the assertion: an arrival fetch would already have been sent. */
  await page.waitForTimeout(200)
  expect(sent.filter((s) => s.url.includes('/catalog?'))).toHaveLength(0)
  await expect(page.locator('.review-catalog')).toHaveCount(0)
})

test('the operator can overrule the pipeline rows and search the export instead', async ({
  page,
}) => {
  const sent = await open(page, WRONG_ROWS)
  await page.getByRole('button', { name: /search tcgplayer/i }).click()

  await expect.poll(() => sent.filter((s) => s.url.includes('/catalog?')).length).toBe(1)

  /* ONE LIST, NOT TWO. Both are answered on digits, so a screen showing both would make `1`
     mean two different rows — which is the mis-write this swap exists to make impossible
     rather than merely unlikely. */
  const rows = page.locator('.review-candidate')
  await expect(rows).toHaveCount(CATALOG_ROWS.length)
  await expect(rows.first()).toContainText('Master Yi, Wuju Master')
  await expect(page.locator('.review-choice')).not.toContainText('Get Excited!')
})

test('a digit answers the row that is on screen, not the row the entry holds', async ({
  page,
}) => {
  const sent = await open(page, WRONG_ROWS)
  await page.getByRole('button', { name: /search tcgplayer/i }).click()
  await expect(page.locator('.review-candidate').first()).toContainText('Master Yi')

  /* ONE FRAME AFTER THE ROWS PAINT, and it is a synchronisation rather than a sleep. The digit
     handler is a window listener re-registered by an effect keyed on `lookup`/`showCatalog`,
     so it is the PREVIOUS closure — the one that still reads the pipeline's rows — until the
     effect has run. A key pressed inside that window is dropped, which is a real race and is
     reported as one; what this wait removes is the test asking a question of a screen that has
     painted an answer it cannot yet act on. */
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => done(null))))
  await page.keyboard.press('1')

  await expect.poll(() => sent.filter((s) => s.method === 'POST').length).toBeGreaterThan(0)
  const body = sent.find((s) => s.method === 'POST')!.body as {
    sku: string
    from_catalog?: boolean
  }
  /* THE SILENT MIS-WRITE THIS FILE EXISTS TO CATCH. The keyboard handler picked its list by
     `candidates.length > 0` for as long as the two lists could not both exist — so the first
     build of D77 would have seen the export's first row, been pressed `1`, and written the
     ENTRY's first row: `Get Excited!`, a different card, onto a real position, with no
     refusal because that SKU is a perfectly good candidate. */
  expect(body.sku).toBe(CATALOG_ROWS[0]!.sku)
  expect(body.sku).not.toBe(WRONG_ROWS[0]!.candidates[0]!.sku)
  expect(body.from_catalog).toBe(true)
})

test('escape comes back to the pipeline rows and writes nothing', async ({ page }) => {
  const sent = await open(page, WRONG_ROWS)
  await page.getByRole('button', { name: /search tcgplayer/i }).click()
  await expect(page.locator('.review-candidate').first()).toContainText('Master Yi')

  await page.keyboard.press('Escape')

  await expect(page.locator('.review-candidate').first()).toContainText('Get Excited!')
  await expect(page.locator('.review-catalog')).toHaveCount(0)
  /* Leaving a list is not an answer. The card is still queued and still unanswered — which is
     what makes this a way back rather than a third way past a card. */
  expect(sent.filter((s) => s.method === 'POST')).toHaveLength(0)
})

test('a zero-candidate card is not offered a control that would toggle one list for itself', async ({
  page,
}) => {
  await open(page, NO_ROWS)
  await expect(page.locator('.review-catalog')).toBeVisible()

  /* It is already showing the export, so the control has nothing to swap to. Drawing it
     would be a button whose two states are identical — the shape `CLEAR_KEY` states the rule
     for: a control that is drawn while it does nothing is the opposite of what showing it is
     for. */
  await expect(page.getByRole('button', { name: /search tcgplayer/i })).toHaveCount(0)
})

test('the reason the pipeline gave has a sentence, and it says the rows may be another card', async ({
  page,
}) => {
  await open(page, WRONG_ROWS)

  /* `rarity_claim_mismatch` had a chip label and no sentence from the day the reason shipped,
     so this screen drew "a reason this screen has no sentence for" over the one open entry in
     the owner's store. It is the ONLY reason the pipeline emits that can mean the candidate
     rows themselves are the wrong card, and nothing else on screen says so. */
  const sentence = page.locator('.review-sentence')
  await expect(sentence).not.toContainText('no sentence for')
  await expect(sentence).toContainText('rarities claimed at capture')
  await expect(sentence).toContainText('different card')
})

/* ---------------------- the two words on screen, and the cross-check run backwards */

/* THE CONTRADICTION, WITH BOTH HALVES ON THE WIRE. `rarity_claim_mismatch` is the one reason
   whose meaning is "A contradicts B" and it could name neither A nor B until 2026-09-11: the
   owner read 141 of these and had to work out for themselves which word disagreed with which.
   The fixture is box 1's real shape that day — a stack claimed `Epic`, rows the catalogue
   calls `Rare`. */
const NAMED_CONTRADICTION: Entry[] = [
  {
    ...entry(51, 'rarity_claim_mismatch', '3.00', [
      {
        sku: '9100001',
        name: 'Ezreal, Dashing',
        set: 'Origins',
        number: '082/221',
        condition: 'Near Mint Foil',
        market: '3.00',
        rarity: 'Rare',
      },
    ]),
    read: {
      name: 'Ezreal, Dashing',
      number: '082/221',
      set: '',
      rarity_claim: ['Epic'],
    },
  },
]

test('the contradiction names both words, not just that there was one', async ({ page }) => {
  await open(page, NAMED_CONTRADICTION)

  const sentence = page.locator('.review-sentence')
  await expect(sentence).toContainText('You claimed this stack holds')
  await expect(sentence).toContainText('Epic')
  await expect(sentence).toContainText('Rare')
  /* The old wording is GONE for an entry that carries both, rather than sitting beside the
     new one — two sentences saying the same thing differently is how a screen stops being
     read. */
  await expect(sentence).not.toContainText('rarities claimed at capture')
})

test('the claim is a chip, so it is on screen before the sentence is read', async ({ page }) => {
  await open(page, NAMED_CONTRADICTION)
  /* "Claimed" alone did not say claimed WHAT — renamed to "Rarity" to match "Sorted as" and
     "Photo" beside it, at the same word count (D194's ratchet). */
  const chip = page.locator('.review-chip', { hasText: 'Rarity' })
  await expect(chip).toContainText('Epic')
})

test('an entry queued before the fields existed keeps the wording it had', async ({ page }) => {
  /* A queue file outlives the run that wrote it, so this is an ordinary case and not a
     migration. The fallback is asserted because a screen that drew "You claimed this stack
     holds " with nothing after it would be worse than the sentence it replaced. */
  await open(page, WRONG_ROWS)
  const sentence = page.locator('.review-sentence')
  await expect(sentence).toContainText('rarities claimed at capture')
  await expect(sentence).not.toContainText('You claimed this stack holds')
  await expect(page.locator('.review-chip', { hasText: 'Rarity' })).toHaveCount(0)
})

/* THE MIRROR. `1/51` on the owner's store: read `Irelia, Blade Dancer`, number `190/221`,
   which that export calls `Forgefire Cape` — `Epic`, which is exactly what was claimed, so
   D23's cross-check AGREED and the card was listed with no question asked. This reason is
   what asks it. */
const NAME_DISPUTED: Entry[] = [
  {
    ...entry(51, 'name_disputed', '0.31', [
      {
        sku: '9038408',
        name: 'Forgefire Cape',
        set: 'Origins',
        number: '190/221',
        condition: 'Near Mint Foil',
        market: '0.31',
        rarity: 'Epic',
      },
    ]),
    read: { name: 'Irelia, Blade Dancer', number: '190/221', set: '', rarity_claim: ['Epic'] },
  },
]

test('a disputed name says which two readings disagree', async ({ page }) => {
  await open(page, NAME_DISPUTED)

  const sentence = page.locator('.review-sentence')
  await expect(sentence).not.toContainText('no sentence for')
  await expect(sentence).toContainText('Irelia, Blade Dancer')
  await expect(sentence).toContainText('Forgefire Cape')
  await expect(sentence).toContainText('came off the same card and they disagree')
  await expect(page.locator('.review-chip', { hasText: 'another card' })).toBeVisible()
})

/* ------------------------------------------------- the group press, and what suppresses it */

/* BOX 1'S PARKED QUEUE, IN MINIATURE: entries that share one reason, one row and one
   condition, plus the two that do not. On the owner's store that was 99 and 2, and the two
   returned null for the other ninety-nine. */
function uniform(index: number): Entry {
  return {
    ...entry(index, 'rarity_claim_mismatch', '3.00', [
      {
        sku: `910000${index}`,
        name: 'Ezreal, Dashing',
        set: 'Origins',
        number: '082/221',
        condition: 'Near Mint Foil',
        market: '3.00',
        rarity: 'Rare',
      },
    ]),
    read: { name: 'Ezreal, Dashing', number: '082/221', set: '', rarity_claim: ['Epic'] },
  }
}

const TWO_ROW_ODD_ONE: Entry = {
  ...entry(9, 'rarity_claim_mismatch', '3.00', [
    { sku: '9200001', name: 'Poro Herder', set: 'Origins', number: '061/298',
      condition: 'Near Mint', market: '1.00', rarity: 'Rare' },
    { sku: '9200002', name: 'Poro Herder', set: 'Origins', number: '061/298',
      condition: 'Near Mint Foil', market: '2.00', rarity: 'Rare' },
  ]),
  read: { name: 'Leona, Radiant Dawn', number: '61/298', set: '', rarity_claim: ['Epic'] },
}

test('one two-row entry no longer suppresses the group press for every other card', async ({
  page,
}) => {
  /* THE REGRESSION THIS IS FOR, measured: `groupOffer` required the WHOLE worklist to be
     uniform, so the last entry here used to return null for the three above it. The anchor
     is the card on screen, which is the first. */
  await open(page, [uniform(1), uniform(2), uniform(3), TWO_ROW_ODD_ONE])
  await expect(page.getByRole('button', { name: /Answer all 3 together/i })).toBeVisible()
})

test('the group press says what it is leaving behind', async ({ page }) => {
  await open(page, [uniform(1), uniform(2), uniform(3), TWO_ROW_ODD_ONE])
  await page.getByRole('button', { name: /Answer all 3 together/i }).click()

  /* An unstated remainder reads as "the queue is done", which is the one way this control
     can mislead now that it answers a subset. */
  await expect(page.locator('.review-group-left')).toContainText('1 more card is still in this list')
})

test('a disputed name is never swept into a group, even a uniform one', async ({ page }) => {
  /* D29's eligibility is a claim about cards nobody is looking at individually, and this
     reason exists because two readings of one photograph disagree — exactly the card that
     must not be answered without being looked at. The anchor is disputed, so no group at
     all is offered. */
  const disputed = (index: number): Entry => ({ ...NAME_DISPUTED[0]!, position: `2/${index}`, index })
  await open(page, [disputed(1), disputed(2), disputed(3)])
  await expect(page.getByRole('button', { name: /Answer all/i })).toHaveCount(0)
})

/* ------------------------------------------------------------- D218: no typed interpunct */

/* THE DOT SWEEP (D218), MUTATION-PROVED. `scripts/user-strings.mjs` cannot see a component's
 * own render decisions — it reads literals, not what `ReviewQueue.tsx` decides to draw from
 * them — so these three read `.bn-view`'s own rendered text and assert directly against the
 * two characters a screen may never type. Each covers a state the sweep actually touched:
 * a card with a question (the "Next" preview, the shared-candidate meta, the rarity chip),
 * the parked rail (the divider label that used to be one CSS string, `'Parked · under the
 * threshold'`, now two elements), and the group-answer confirmation (the session tally). */
test('a card with a question types no interpunct anywhere on the view', async ({ page }) => {
  await open(page, REVIEW)
  const text = await page.locator('.bn-view').innerText()
  expect(text).not.toMatch(/[·•]/)
})

test('the parked rail types no interpunct, including its own divider label', async ({ page }) => {
  const parkedEntry = entry(30, 'low_confidence', '0.30', [candidate(0, '0.30')])
  await open(page, REVIEW, [parkedEntry])
  await page.getByRole('button', { name: /^Queue/ }).click()
  await expect(page.locator('.review-row-parked-label')).toBeVisible()
  const text = await page.locator('.bn-view').innerText()
  expect(text).not.toMatch(/[·•]/)
})

test('the group-answer confirmation types no interpunct', async ({ page }) => {
  await open(page, [uniform(1), uniform(2), uniform(3)])
  await page.getByRole('button', { name: /Answer all 3 together/i }).click()
  await expect(page.locator('.review-group')).toBeVisible()
  const text = await page.locator('.bn-view').innerText()
  expect(text).not.toMatch(/[·•]/)
})

/* --------------------------------------------------------- F3: the order line's contrast */

/* THE PILL SITS ON `--bn-surface-glass` OVER `--rv-well`, NEVER OVER `--bn-bg` — the ground
 * every `--bn-*` ink token's documented ratio in `tokens.css` is measured against. `--bn-ink-3`
 * reads 4.85:1 there and only 2.8:1 here in light, which is how `back`, `front`, the arrows
 * and an unread neighbour's name went under the 4.5:1 floor (found in the locating review,
 * round 3). This fixture is the ONLY place in this file `CaptionOrder` renders at all — every
 * other entry above carries no `place`, so the pill's order line has never been on screen for
 * any other test here.
 *
 * `PlaceNeighbor` per `app/src/types.ts`: `prev` (toward the back) named, `next` (toward the
 * front) unread, so both `.review-caption-nb` states are on screen at once. */
const ORDER_LINE_PLACE: Place = {
  label: 'Rares, Section 1, Card 14',
  located: true,
  box: 2,
  index: 14,
  slot: 14,
  section: 1,
  card: 14,
  box_name: 'Rares',
  section_start: 1,
  section_end: null,
  box_total: 20,
  box_closed: false,
  fraction: 0.7,
  neighbors: {
    prev: { slot: 13, index: 13, name: 'Charmander' },
    next: { slot: 15, index: 15, name: null, unread: 1 },
  },
}

/** The WCAG contrast of an element's text against the ground under it, both read from the
 *  computed style of the element and its painted ancestors, alpha composited in order —
 *  `app/tests/kit-data.spec.ts:contrastOf`'s own method, duplicated rather than imported
 *  (every spec file in this repo carries its own contrast helper; `pull-confirm.spec.ts`
 *  and `fulfillment.spec.ts` each do too). This one is the right shape for a TRANSLUCENT
 *  ground — `noThinContrast` in `fulfillment.spec.ts` refuses one by design (`docs/DESIGN.md`'s
 *  floor is for an opaque owner-facing panel), and this pill is glass over a photograph. */
async function contrastOf(page: Page, selector: string): Promise<number> {
  await page.evaluate(() =>
    Promise.all(document.getAnimations().map((one) => one.finished.catch(() => undefined))),
  )
  return page.locator(selector).first().evaluate((el) => {
    const parse = (value: string): number[] => {
      const m = value.match(/rgba?\(([^)]+)\)/)
      if (m === null) return [0, 0, 0, 0]
      const parts = (m[1] ?? '').match(/[\d.]+/g)?.map(Number) ?? []
      return [parts[0] ?? 0, parts[1] ?? 0, parts[2] ?? 0, parts[3] ?? 1]
    }
    const over = (top: number[], under: number[]): number[] => {
      const a = top[3] ?? 1
      return [0, 1, 2].map((i) => (top[i] ?? 0) * a + (under[i] ?? 0) * (1 - a)).concat(1)
    }
    const layers: number[][] = []
    for (let node: Element | null = el; node !== null; node = node.parentElement) {
      const bg = parse(getComputedStyle(node).backgroundColor)
      if ((bg[3] ?? 0) > 0) layers.push(bg)
      if ((bg[3] ?? 0) >= 1) break
    }
    let ground = [255, 255, 255, 1]
    for (const layer of layers.reverse()) ground = over(layer, ground)
    const ink = over(parse(getComputedStyle(el).color), ground)
    const lum = (c: number[]) => {
      const [r, g, b] = [0, 1, 2].map((i) => {
        const v = (c[i] ?? 0) / 255
        return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
      })
      return 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (b ?? 0)
    }
    const [hi, lo] = [lum(ink), lum(ground)].sort((x, y) => y - x)
    return ((hi ?? 0) + 0.05) / ((lo ?? 0) + 0.05)
  })
}

const ORDER_LINE_FLOOR = 4.5

for (const theme of ['light', 'dark'] as const) {
  test(`the pill's order line reads ${ORDER_LINE_FLOOR}:1 in ${theme}: back, the neighbours, front`, async ({
    page,
  }) => {
    const withPlace: Entry = { ...entry(14, 'set_ambiguous', '84.50', [candidate(0, '84.50')]), place: ORDER_LINE_PLACE }
    await open(page, [withPlace])
    if (theme === 'dark') {
      await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'))
    }
    await expect(page.locator('.review-caption-order')).toBeVisible()

    // `back` and `front`, `.review-caption-end` — the low-contrast pair the finding named.
    const ends = page.locator('.review-caption-end')
    await expect(ends).toHaveCount(2)
    for (let i = 0; i < 2; i += 1) {
      const c = await contrastOf(page, `.review-caption-end >> nth=${i}`)
      expect(c, `.review-caption-end[${i}] in ${theme}`).toBeGreaterThanOrEqual(ORDER_LINE_FLOOR)
    }

    // The two arrows between `back`/`this card`/`front`.
    const arrows = page.locator('.review-caption-arrow')
    await expect(arrows).toHaveCount(2)
    for (let i = 0; i < 2; i += 1) {
      const c = await contrastOf(page, `.review-caption-arrow >> nth=${i}`)
      expect(c, `.review-caption-arrow[${i}] in ${theme}`).toBeGreaterThanOrEqual(ORDER_LINE_FLOOR)
    }

    // The unread neighbour toward the front — the dimmer, italic state.
    const unread = await contrastOf(page, '.review-caption-nb.is-unread')
    expect(unread, `.review-caption-nb.is-unread in ${theme}`).toBeGreaterThanOrEqual(ORDER_LINE_FLOOR)

    // The named neighbour toward the back, for completeness — never regressed by this fix.
    const named = await contrastOf(page, '.review-caption-nb:not(.is-unread)')
    expect(named, `.review-caption-nb (named) in ${theme}`).toBeGreaterThanOrEqual(ORDER_LINE_FLOOR)
  })
}

/* ------------------------------------------------------------ the Identify strip (D291) */

/** `GET /status` with `n` cards in the `captured` state. Registered after the shell's own stub,
 *  so it wins (Playwright tries the newest route first). It is only the strip's cheap gate:
 *  the count the strip draws is `/pipeline/waiting`'s. */
async function waiting(page: Page, n: number): Promise<void> {
  await page.route(/\/status$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        captures_root: 'captures',
        store: 'inventory/store.sqlite',
        store_exists: true,
        cards: 40,
        states: { captured: n },
        queues: { review: 0, parked: 0 },
        next_index: {},
      }),
    }),
  )
}

/** `n` position keys in box 9, the shape `/pipeline/waiting` answers. */
function keysOf(n: number, box = 9): string[] {
  return Array.from({ length: n }, (_, at) => `${box}/${at + 1}`)
}

type Asked = { path: string; body: Record<string, unknown> | null }

/** Every read the strip, the Runs sheet and its composer make, stubbed and recorded. The
 *  strip's list answers `keys`, and `later` replaces it once the case says so. The spend route
 *  is a 500 here, and a case that spends registers `spendRoute` over it. */
async function runsReads(page: Page, runs: unknown[], keys: string[] = []): Promise<{ asked: Asked[]; answer: (next: string[]) => void }> {
  const asked: Asked[] = []
  let current = keys
  const json = (body: unknown) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  const record = (path: string, route: { request(): { postDataJSON(): unknown; method(): string } }) =>
    asked.push({ path, body: route.request().method() === 'POST' ? (route.request().postDataJSON() as Record<string, unknown>) : null })
  await page.route(/\/pipeline\/waiting$/, (route) => {
    record('/pipeline/waiting', route)
    return route.fulfill(json({ keys: current, claimed: 0 }))
  })
  await page.route(/\/pipeline\/runs$/, (route) => {
    record('/pipeline/runs', route)
    return route.fulfill(json({ runs }))
  })
  await page.route(/\/boxes$/, (route) => route.fulfill(json({ boxes: [] })))
  await page.route(/\/inventory$/, (route) => route.fulfill(json({ version: 2, cards: {} })))
  await page.route(/\/games$/, (route) => route.fulfill(json({ games: [] })))
  await page.route(/\/pipeline\/submissions$/, (route) =>
    route.fulfill(json({ claims: [], counts: { claims: 0, keys: 0, stale: 0 } })),
  )
  await page.route(/\/pipeline\/preflight$/, (route) => {
    record('/pipeline/preflight', route)
    return route.fulfill(
      json({
        ok: true,
        exit_code: 0,
        selection: { state: 'captured' },
        sentence: 'captured',
        scope: null,
        capture_dirs: ['/tmp/captures/cards'],
        console: 'estimated cost $0.04\n',
        claimed: null,
        total: { photographs: 12, cache_hits: 0, to_send: 12, estimate_usd: 0.04, cards: 12 },
      }),
    )
  })
  await page.route(/\/pipeline\/identify$/, (route) => {
    record('/pipeline/identify', route)
    return route.fulfill({ status: 500, body: 'this case never spends' })
  })
  /* The run a started spend opens in the sheet, and its export scope (D76), in run-panel's
     own shape: registered first, so the more general run route below cannot shadow it. */
  await page.route(/\/pipeline\/runs\/[^/]+\/scope/, (route) =>
    route.fulfill(
      json({
        run: '2026-09-25-box9-01',
        games: [],
        scopes: ['category', 'sets'],
        asked: null,
        reason: null,
        message: null,
      }),
    ),
  )
  await page.route(/\/pipeline\/runs\/[^/]+$/, (route) =>
    route.fulfill(json({ ...runRow({ live: true, pid: 999, phase: 'identifying', collected: false }), console: '', files: [], manifest: {} })),
  )
  return {
    asked,
    answer: (next) => {
      current = next
    },
  }
}

type Spend = { body: Record<string, unknown> }

/** The spend route, STUBBED: nothing here reaches a paid service. Registered after `runsReads`,
 *  so it wins. `cards` is what the SERVER says it sent, which the receipt must quote. `hold`
 *  keeps the answer back until the case releases it. `refuse` answers D174's 409 instead. */
async function spendRoute(
  page: Page,
  opts: { cards?: number; hold?: Promise<void>; refuse?: boolean; after?: () => void } = {},
): Promise<Spend[]> {
  const spends: Spend[] = []
  await page.route(/\/pipeline\/identify$/, async (route) => {
    spends.push({ body: route.request().postDataJSON() as Record<string, unknown> })
    if (opts.hold !== undefined) await opts.hold
    opts.after?.()
    if (opts.refuse === true) {
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'cards_already_claimed',
            message: 'Run 2026-09-25-box9-01 is already paying to read 3 of these cards. Nothing in this send was started.',
          },
        }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        started: [
          {
            run: '2026-09-25-box9-01',
            path: '/tmp/runs/2026-09-25-box9-01',
            pid: 999,
            selection: { keys: [] },
            scope: null,
            cards: opts.cards ?? 12,
            argv: [],
          },
        ],
        failed: [],
      }),
    })
  })
  return spends
}

const PAST = [runRow({ counts: { cards_in: 100 }, usage: { cost_usd: 0.3 } })]

test('the Identify strip is absent while no card waits, and neither list is read for it', async ({ page }) => {
  const { asked } = await runsReads(page, [])
  await open(page)
  await expect(page.locator('.review-identify-strip')).toHaveCount(0)
  expect(asked).toEqual([])
})

test('the Identify strip names the waiting count and this store’s own past cost per card', async ({ page }) => {
  await waiting(page, 12)
  /* $0.30 over 100 cards is $0.003 a card, so 12 cards is about $0.036. The second run spent
     nothing and the third read no cards: neither may move the rate. */
  await runsReads(
    page,
    [
      runRow({ counts: { cards_in: 100 }, usage: { cost_usd: 0.3 } }),
      runRow({ run: 'b', counts: { cards_in: 50 }, usage: { cost_usd: 0 } }),
      runRow({ run: 'c', counts: {}, usage: { cost_usd: 9 } }),
    ],
    keysOf(12),
  )
  await open(page)
  const strip = page.locator('.review-identify-strip')
  await expect(strip.locator('.review-identify-strip-said')).toHaveText('Identify 12 cards, ~$0.04 (estimate)')
  /* D221: the dollar figure is the mono face's own span, never typed into the label. */
  await expect(strip.locator('.bn-money')).toHaveText('$0.04')
  /* And it says it is an estimate to a pointer, not only to a screen reader. */
  await expect(strip.locator('.review-identify-estimate')).toHaveAttribute('title', /estimate/)
})

test('a store with no recorded spend draws the strip with no figure rather than a guess', async ({ page }) => {
  await waiting(page, 1)
  await runsReads(page, [runRow({ usage: {} })], keysOf(1))
  await open(page)
  await expect(page.locator('.review-identify-strip-said')).toHaveText('Identify 1 card')
})

/* THE STRIP COUNTS WHAT THE SPEND COUNTS. `/status` says 14 cards are in the captured state, but
 * none of them has a photograph a spend could buy (the demo store's own shape), so the strip is
 * absent rather than offering a press the server would refuse. PROVED RED: drawing N from
 * `status.states.captured` draws "Identify 14 cards" here. */
test('the strip counts the cards a spend would buy, not the captured state', async ({ page }) => {
  await waiting(page, 14)
  const { asked } = await runsReads(page, PAST, [])
  await open(page)
  await expect.poll(() => asked.filter((row) => row.path === '/pipeline/waiting').length).toBe(1)
  await expect(page.locator('.review-identify-strip')).toHaveCount(0)
})

test('Check first opens the money gate on top, spends nothing, and leaving it goes back to Review', async ({ page }) => {
  await waiting(page, 12)
  const { asked } = await runsReads(page, PAST, keysOf(12))
  await open(page)
  await page.locator('.review-identify-open').click()

  /* The composer is the TOP layer, though it mounts in the same commit as the Runs sheet
     around it: its own Close takes the press, rather than the sheet under it taking it. */
  const composer = page.locator('.runs-composer')
  await expect(composer).toBeVisible()
  await expect(page.locator('.run-quote')).toBeVisible()
  expect(asked.filter((row) => row.path === '/pipeline/preflight')).toHaveLength(1)
  await composer.getByRole('button', { name: 'Close' }).click()

  await expect(composer).toHaveCount(0)
  await expect(page.locator('.review-runs-sheet')).toHaveCount(0)
  expect(asked.map((row) => row.path)).not.toContain('/pipeline/identify')
})

/* THE OWNER'S RULING, 2026-09-25: "Identify now" spends at once, with no pre-check and no
 * confirm. IT SPENDS EXACTLY THE CARDS THE STRIP PRICED: the whole send body is those keys and
 * the composer's default reading, and nothing else. A capture in another tab after the strip
 * read its list (the waiting answer grows to 30 here, and `/status` with it) cannot grow the
 * spend. The receipt quotes the SERVER'S count. PROVED RED: sending `{state: 'captured'}` in
 * place of the keys fails the body assertion. */
test('Identify now spends exactly the cards the strip priced, with no pre-check', async ({ page }) => {
  await waiting(page, 12)
  const { asked, answer } = await runsReads(page, PAST, keysOf(12))
  const spends = await spendRoute(page, { cards: 11 })
  await open(page)
  await expect(page.locator('.review-identify-strip-said')).toContainText('Identify 12 cards')

  answer(keysOf(30))
  await waiting(page, 30)
  await page.locator('.review-identify-now').click()

  await expect.poll(() => spends.length).toBe(1)
  expect(spends[0]?.body).toEqual({ confirm: true, keys: keysOf(12), crop: true, max_edge: 1200 })
  expect(asked.map((row) => row.path)).not.toContain('/pipeline/preflight')
  /* No confirm screen: the composer never opens. The receipt is a toast with the server's own
     count, then the run itself, open in the Runs sheet, where its own progress reads itself. */
  await expect(page.locator('.bn-toast', { hasText: 'Identify started' })).toContainText('11 cards sent to be read.')
  await expect(page.locator('.runs-composer')).toHaveCount(0)
  await expect(page.locator('.review-runs-sheet')).toBeVisible()
})

/* AFTER A SPEND THE STRIP STOPS OFFERING THOSE CARDS. The run claimed them, so the server's
 * list no longer holds them, and the strip reads it again once the press answers. */
test('after a spend the strip reads its list again and stops offering the claimed cards', async ({ page }) => {
  await waiting(page, 12)
  const reads = await runsReads(page, PAST, keysOf(12))
  await spendRoute(page, { after: () => reads.answer([]) })
  await open(page)
  await page.locator('.review-identify-now').click()
  await expect(page.locator('.review-runs-sheet')).toBeVisible()
  await expect.poll(() => reads.asked.filter((row) => row.path === '/pipeline/waiting').length).toBe(2)
  await page.keyboard.press('Escape')
  await expect(page.locator('.review-identify-strip')).toHaveCount(0)
})

/* ONE RULE FOR BOTH PRESSES: when `#/inventory` handed over ticked cards (`banchi.run-scope`),
 * the strip names, prices and spends THAT set, the same one "Check first" opens on. PROVED RED:
 * `openingSelection` ignoring the handoff asks for `state: 'captured'` instead. */
test('a ticked handoff is the set the strip names and Identify now spends', async ({ page }) => {
  const ticked = ['9/2', '9/3', '9/7']
  await page.addInitScript((keys) => {
    window.sessionStorage.setItem('banchi.run-scope', JSON.stringify({ keys }))
  }, ticked)
  const { asked } = await runsReads(page, PAST, ['9/2', '9/3'])
  const spends = await spendRoute(page, { cards: 2 })
  await open(page)
  await expect(page.locator('.review-identify-strip-said')).toContainText('Identify 2 cards')
  expect(asked.find((row) => row.path === '/pipeline/waiting')?.body).toEqual({ keys: ticked })
  await page.locator('.review-identify-now').click()
  await expect.poll(() => spends.length).toBe(1)
  expect(spends[0]?.body).toEqual({ confirm: true, keys: ['9/2', '9/3'], crop: true, max_edge: 1200 })
})

/* A REFUSED PRESS MOVES NOTHING (D118). The refusal is a toast, never a notice that grows the
 * strip, so the card under review stays where it was. */
test('a refused Identify now says so in a toast and moves nothing', async ({ page }) => {
  await waiting(page, 12)
  await runsReads(page, PAST, keysOf(12))
  await spendRoute(page, { refuse: true })
  await open(page)
  const card = page.locator('.review-card')
  const before = await card.boundingBox()
  await page.locator('.review-identify-now').click()
  await expect(page.locator('.bn-toast', { hasText: 'Nothing was paid for' })).toContainText('already paying to read 3')
  const after = await card.boundingBox()
  expect(after?.y).toBe(before?.y)
  expect(after?.x).toBe(before?.x)
})

/* A DOUBLE PRESS BUYS ONCE. Two clicks land in one task, before React can draw the busy state,
 * so the only thing that can stop the second is the screen's own in-flight guard. The server's
 * claim (D174) still refuses a second tab; that half is `make submission-selftest`'s.
 * PROVED RED: deleting the `spending` ref's early return sends two spends. */
test('a double press on Identify now spends once', async ({ page }) => {
  await waiting(page, 12)
  await runsReads(page, [], keysOf(12))
  let release = () => {}
  const held = new Promise<void>((resolve) => {
    release = resolve
  })
  const spends = await spendRoute(page, { hold: held })
  await open(page)
  await page.locator('.review-identify-now').evaluate((button: HTMLButtonElement) => {
    button.click()
    button.click()
  })
  await expect.poll(() => spends.length).toBe(1)
  await expect(page.locator('.review-identify-now')).toBeDisabled()
  release()
  await expect(page.locator('.review-runs-sheet')).toBeVisible()
  expect(spends).toHaveLength(1)
})
