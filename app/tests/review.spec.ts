// Protects: Review shows the photograph beside the choices and lets the owner resolve each card in the queue.
// Governs: D23, D24, D28, D32, D77, D118, D218
import { test, expect, type Page, type Locator } from '@playwright/test'
import { settleFonts } from './fontsReady'
import { sealEveryTest, settleAnimations, stubStore } from './shell'
import { settleMotion } from './motionSettled'
import type { Place } from '../src/types'
import { NO_FREE_FIELDS, runRow, seedPopulatedReview, stubMatchState } from './routeFixtures'
import { describeShifts, markNow, readShifts, sumOf, watchShifts } from './layoutShift'
import { setViewport } from './phoneSwitch'

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

/** The measurement viewport. Every number in the split's own commit was taken here, so this is where they are checked. */
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
  read: {
    name: string
    number: string
    set: string
    rarity_claim?: string[]
    matcher_pick?: { name: string | null; number: string | null; set: string | null; reason: string } | null
  }
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

/* D77 — the export rows a lookup offers for a card the pipeline found nothing for. Modelled
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
 *  Before D77 this was a dead end: the answer route refuses it as `no_candidates`, so the
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
/** THE SUMMARY BAND'S OWN READS (`GET /pipeline/match` and `GET /pipeline/match/sweep`, with and without `keys`), answered
 *  answered for every case by the file's `beforeEach`, so each one that opens Review is sealed. `/capture/sitting` is the
 *  shell's own stub. A case steers the answer through the returned object, or registers its own routes, which win.
 *  `paidKeys` are the cards waiting for a paid look; `paid` is their count. */
type BandSweep = { paidKeys: string[]; unread: number }

async function stubBandReads(page: Page): Promise<BandSweep> {
  await stubMatchState(page)
  const answer: BandSweep = { paidKeys: [], unread: 0 }
  await page.route(/\/pipeline\/match\/sweep(\?.*)?$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ on: false, running: false, blocked: null, aside: 0, matched: 0, matched_here: 0, paid: answer.paidKeys.length, paid_keys: answer.paidKeys, unread: answer.unread }),
    }),
  )
  return answer
}

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

  /* D77's catalog lookup. Fulfilled from `catalogRows`, which the zero-candidate test
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

  await setViewport(page, DESK)
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
/* Every case opens Review, and the band reads the sweep and the free reader's state, so none may reach the real server. */
test.beforeEach(async ({ page }) => stubBandReads(page))

test('the photograph is the largest thing on the screen', async ({ page }) => {
  await open(page)
  /* 23%, NOT THE 25% FIRST WRITTEN, and the difference is an aspect ratio rather than a
     compromise. the first UI research pass computed its target from a bare card's 63:88;
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
  /* THE BAND TAKES ITS HEIGHT FROM THE PHOTOGRAPH (the owner's ruling), so the 23% above is history. Measured with the band
     drawn: 1440 draws 338.6x602 = 0.157 and 820 draws 172.1x306 = 0.071 of the viewport. The floor is the lower, rounded
     down to two places, per width: 1440 holds 0.15 and a 600px long edge, 820 holds 0.07 and 300px, in place of 0.23 and 700. */
  for (const [width, floor, edge] of [[1440, 0.15, 600], [820, 0.07, 300]] as const) {
    await setViewport(page, { width, height: DESK.height })
    await settleAnimations(page)
    const box = await page.locator('.review-photo').boundingBox()
    expect(box).not.toBeNull()
    const share = (box!.width * box!.height) / (width * DESK.height)
    expect(share, `the photograph at ${width}`).toBeGreaterThanOrEqual(floor)
    expect(Math.max(box!.width, box!.height), `the long edge at ${width}`).toBeGreaterThanOrEqual(edge)
  }
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
     costs less than 30% of the viewport, the band included. A re-added banner, a second toolbar or a
     restored lede block fails this exactly as it failed the old form. */
  const head = await page.locator('.review-pagehead').boundingBox()
  expect(head!.y).toBeLessThanOrEqual(150)

  for (const width of [1440, 820]) {
    await setViewport(page, { width, height: DESK.height })
    await settleFonts(page)
    await settleAnimations(page)
    const body = await page.locator('.review-body').boundingBox()
    /* THE BAND COUNTS AS CHROME (the owner's ruling: the photo shrinks by the band's height). Measured at 1440 and at 820,
       the card starts at 257.8px of 900 (the band is 114px of it, the rest 143.8px), so the floor is 30% of the viewport,
       270px, up from a quarter, 225px. Growing the band or the rest of the chrome past that fails here. */
    expect(body!.y).toBeLessThan(DESK.height * 0.3)
  }
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

test('finding #14 (the Opus review round) — the tray has no clock: a faked minute later, the newest receipt still stands, no drain bar', async ({
  page,
}) => {
  /* THE OLD BUILD DRAINED THE TRAY OFF SCREEN AFTER TWENTY SECONDS, with a bar counting down
   * the wait — the one remaining clock on this screen. `docs/specs/undo.md` §11.1 (UN-5):
   * rank replaces the clock everywhere else on this product; this proves it here too. */
  await page.clock.install()
  const sent = await open(page)

  await page.locator('.review-candidate').first().click()
  await expect(page.locator('.review-receipt')).toHaveCount(1)
  await expect(page.locator('.review-receipt .bn-receipt-bar')).toHaveCount(0)

  /* PAST THE OLD TWENTY-SECOND WINDOW, WHICH IS NO LONGER A DEADLINE. */
  await page.clock.runFor(60_000)
  await expect(page.locator('.review-receipt')).toHaveCount(1)
  await expect(page.locator('.review-receipt').getByRole('button', { name: 'Undo' })).toBeVisible()

  /* FINDING #11 (the Opus review round) — not only the visible control: `U` itself still
   * fires a minute later, because `useUndoHotkey` reads nothing off a clock either. */
  await page.keyboard.press('u')
  await expect
    .poll(() => sent.filter((s) => s.method === 'POST' && (s.body as { undo?: boolean } | null)?.undo === true).length)
    .toBe(1)
})

test('finding #10 (the Opus review round) — the receipt reserves its own row, and nothing else moves (D118)', async ({
  page,
}) => {
  /* Review used to draw the same receipt twice: `.review-tray`'s own reserved row in the
   * body, and a second, UNRESERVED `PageUndo` in the page header (`docs/specs/undo.md`
   * §11.10's own UN-9/UN-10 entry). The header copy's mount is what pushed everything below
   * it down 56px on the first answer of a session — orchestrator's call (§11.12): drop the
   * header copy, keep only the reserved one. */
  await open(page)
  await expect(page.locator('.review-receipt')).toHaveCount(0)

  const before = await settled(page)
  await page.locator('.review-candidate').first().click()
  await expect(page.locator('.review-receipt')).toHaveCount(1)
  await expect(page.locator('.review-receipt').getByRole('button', { name: 'Undo' })).toBeVisible()
  const after = await settled(page)

  const moved = whatMoved(before, after)
  expect(
    moved,
    `${moved.length} element(s) outside the card panel moved when the receipt arrived:\n${moved.slice(0, 12).join('\n')}`,
  ).toHaveLength(0)
})

/* ------------------------------------------------------------------------- the phone */

test('below 900px the screen is the single column it shipped with', async ({ page }) => {
  await open(page)
  await setViewport(page, PHONE)
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

/* ---------------------------------------------------------- D77: the card with no rows */

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
     write as `no_candidates`, which is the guard D77 deliberately left standing for every
     answer that does not come from the catalog. */
  expect(body.from_catalog).toBe(true)
})

test('an ordinary answer carries no catalog flag at all', async ({ page }) => {
  const sent = await open(page)
  await page.locator('.review-candidate').first().click()

  await expect.poll(() => sent.filter((s) => s.method === 'POST').length).toBeGreaterThan(0)
  const body = sent.find((s) => s.method === 'POST')!.body as { from_catalog?: boolean }
  /* Absent, not false. Every answer this screen has ever written goes through one call, and
     a flag about D77 riding on all of them would put a claim about how the row was found
     onto thousands of answers that have nothing to do with it. */
  expect(body.from_catalog).toBeUndefined()
})

test('the search box does not answer the card when a digit is typed into it', async ({
  page,
}) => {
  const sent = await open(page, NO_ROWS)
  /* `.search-field-input`, not `.review-catalog-input`: the catalog's own search box moved
     onto the kit's `SearchField` (R2-search, 2026-09-27), which owns its own input class. */
  const box = page.locator('.review-catalog .search-field-input')
  await box.click()
  await box.fill('1')

  /* THE NEGATIVE CASE, and it is the one that matters. The digits on this screen answer the
     card; an input that swallowed one would be fine, but an input that did NOT would write a
     SKU onto a real card while the operator was typing a collector number. `isEditableTarget`
     is what stops it, and nothing in the type system says so. */
  await page.waitForTimeout(150) // keep: asserts the digit typed into the box sends nothing
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
    await page.waitForTimeout(75) // keep: the poll interval of a loop that compares two reads apart in time
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

/* THE CASE D77 COULD NOT REACH, and it is not hypothetical: box 3 card 66 in the owner's own
   store, and the only open entry in it. `Nasus, Ascended` was read with its number misread as
   `8/298` — a REAL key in that export, belonging to `Get Excited!` — so the entry carries two
   confident candidate rows for a different card at $0.07 and $0.29, while the card's own row
   (`046/166`, Near Mint Foil, $0.74) sits in the same file. D77 offered the export only where
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

  /* D77'S SECOND ARGUMENT, KEPT. It refused to fetch a catalog beside a good list of rows —
     "a second, looser list beside a good one is how a screen teaches you to stop reading the
     first" — and that is an argument about what appears UNASKED, which D77 does not touch.
     The timeout is the assertion: an arrival fetch would already have been sent. */
  await page.waitForTimeout(200) // keep: asserts no catalog fetch is sent unasked
  expect(sent.filter((s) => s.url.includes('/catalog?'))).toHaveLength(0)
  await expect(page.locator('.review-catalog')).toHaveCount(0)
})

test('the operator can overrule the pipeline rows and search the export instead', async ({
  page,
}) => {
  const sent = await open(page, WRONG_ROWS)
  await page.locator('.review-actions').getByRole('button', { name: 'Search' }).click()

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
  await page.locator('.review-actions').getByRole('button', { name: 'Search' }).click()
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
  await page.locator('.review-actions').getByRole('button', { name: 'Search' }).click()
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
  await expect(page.locator('.review-actions').getByRole('button', { name: 'Search' })).toHaveCount(0)
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
     "Photo" beside it, at the same word count (D284's ratchet). */
  const chip = page.locator('.review-chip', { hasText: 'Rarity' })
  await expect(chip).toContainText('Epic')
})

/* THE FREE READER'S TOP PICK, on a card it did not accept and whose paid answer is held here
   (`docs/specs/identify-engine-pick.md` section 2). The fact is the pick beside the paid answer, so
   the person sees both readings of one photograph. An entry the free reader never saw carries no
   `matcher_pick` at all, and draws no fact. */
const SECOND_LOOK_ENTRY: Entry = {
    ...entry(61, 'low_confidence', '1.20', [
      {
        sku: '9100002',
        name: 'Raichu',
        set: 'Base Set',
        number: '014/102',
        condition: 'Near Mint',
        market: '1.20',
        rarity: 'Rare',
      },
    ]),
    read: {
      name: 'Raichu',
      number: '014/102',
      set: 'Base Set',
      matcher_pick: { name: 'Pikachu', number: '058', set: 'Base Set', reason: 'margin_too_small' },
    },
}
const SECOND_LOOK: Entry[] = [SECOND_LOOK_ENTRY]

test('a second-look card shows the free reader pick in its details, and not its reason code', async ({ page }) => {
  await open(page, SECOND_LOOK)
  await page.locator('.review-details-summary').click()
  const fact = page.locator('.review-fact', { hasText: 'Free reader' })
  await expect(fact).toHaveCount(1)
  await expect(fact.locator('dt')).toHaveText('Free reader')
  await expect(fact.locator('dd')).toHaveText('Pikachu 058')
  await expect(page.locator('.review-card')).not.toContainText('margin_too_small')
})

test('a card the free reader never saw draws no Free reader fact', async ({ page }) => {
  await open(page, NAMED_CONTRADICTION)
  await page.locator('.review-details-summary').click()
  await expect(page.locator('.review-fact', { hasText: 'Photo read' })).toHaveCount(1)
  await expect(page.locator('.review-fact', { hasText: 'Free reader' })).toHaveCount(0)
})

test('a pick with no name says there was none, rather than drawing an empty fact', async ({ page }) => {
  const bare: Entry[] = [
    {
      ...SECOND_LOOK_ENTRY,
      read: { ...SECOND_LOOK_ENTRY.read, matcher_pick: { name: null, number: null, set: null, reason: 'no_card_found' } },
    },
  ]
  await open(page, bare)
  await page.locator('.review-details-summary').click()
  await expect(page.locator('.review-fact', { hasText: 'Free reader' }).locator('dd')).toHaveText('no pick')
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

  /* F5 verbiage cut, the owner's ruling on the held mismatch paragraph: the sentence is now
     "Mismatch: <read> / <listing>" — the two names are the whole of it, and the "may be
     another card" chip and the trailing "came off the same card" sentence are both cut, since
     "Mismatch?" is now the headline itself. */
  const sentence = page.locator('.review-sentence')
  await expect(sentence).not.toContainText('no sentence for')
  await expect(sentence).toContainText('Mismatch:')
  await expect(sentence).toContainText('Irelia, Blade Dancer')
  await expect(sentence).toContainText('Forgefire Cape')
  await expect(page.locator('.review-question-title')).toContainText('Mismatch?')
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
  fraction: 0.7,
  neighbors: {
    prev: { slot: 13, index: 13, name: 'Charmander' },
    next: { slot: 15, index: 15, name: null, unread: 1 },
  },
}

/** The WCAG contrast of an element's text against the ground under it, both read from the
 *  computed style of the element and its painted ancestors, alpha composited in order —
 *  `app/tests/kit-data.spec.ts:contrastOf`'s own method, duplicated rather than imported
 *  (every spec file in this repo carries its own contrast helper; `fulfillment.spec.ts`
 *  does too). This one is the right shape for a TRANSLUCENT
 *  ground — `noThinContrast` in `fulfillment.spec.ts` refuses one by design (`docs/DESIGN.md`'s
 *  floor is for an opaque owner-facing panel), and this pill is glass over a photograph. */
async function contrastOf(page: Page, selector: string): Promise<number> {
  await settleAnimations(page)
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
  /* THE FREE READER, PREPARED: it is the Identify sheet's default pick and the sheet reads its state on opening. */
  await stubMatchState(page)
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
        total: { photographs: 12, cache_hits: 0, to_send: 12, estimate_usd: 0.04, cards: 12, ...NO_FREE_FIELDS },
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

/* THE BAND REPLACED THE IDENTIFY STRIP (identify-engine-pick.md section 8). Its one press reads "Read the N left, about $X",
 * N is the cards waiting for a paid look (the sweep's `paid`), and the press spends at once. The cases below are the
 * strip's own, re-pointed at the band. "Check first" and the ticked-handoff scope have no band equal and are gone. */

/** The sweep says these keys wait for a paid look. Registered after the file's `beforeEach`, so it wins. */
async function paidWait(page: Page, keys: string[]): Promise<{ paidKeys: string[] }> {
  const sweep = await stubBandReads(page)
  sweep.paidKeys = keys
  return sweep
}

const press = (page: Page) => page.locator('.review-band-read')

test('the band shows no press while no card waits for a paid look', async ({ page }) => {
  await runsReads(page, [])
  await open(page)
  await expect(page.locator('.review-band')).toBeVisible()
  await expect(page.locator('.review-identify-strip')).toHaveCount(0)
  await expect(press(page)).toHaveCount(0)
})

test('the press names the waiting count and this store’s own past cost per card', async ({ page }) => {
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
  await paidWait(page, keysOf(12))
  await open(page)
  await expect(press(page)).toHaveText('Read the 12 left, about $0.04')
  /* D221: the dollar figure is the mono face's own span, never typed into the label. */
  await expect(press(page).locator('.bn-money')).toHaveText('$0.04')
})

test('a store with no recorded spend draws the press with no figure rather than a guess', async ({ page }) => {
  await waiting(page, 1)
  await runsReads(page, [runRow({ usage: {} })], keysOf(1))
  await paidWait(page, keysOf(1))
  await open(page)
  await expect(press(page)).toHaveText('Read the 1 left')
})

/* A REFUSED COUNT IS SAID, NOT SWALLOWED. The server refuses `/pipeline/waiting` over a claim it
 * cannot read; the band's place shows that sentence, and offers no press. */
test('the band says why when the server refuses to count', async ({ page }) => {
  await waiting(page, 3)
  await runsReads(page, PAST, [])
  await page.route(/\/pipeline\/waiting$/, (route) =>
    route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({
        error: {
          code: 'claim_unreadable',
          message: 'Sending is paused because one saved record cannot be read. Nothing was sent.',
        },
      }),
    }),
  )
  await open(page)
  const notice = page.locator('.review-identify-refusal')
  await expect(notice).toContainText('saved record cannot be read')
  await expect(press(page)).toHaveCount(0)
})

/* THE PRESS COUNTS WHAT THE SPEND COUNTS. `/status` says 14 cards are in the captured state, but
 * none waits for a paid look, so there is no press rather than one the server would refuse. */
test('the press counts the cards waiting for a paid look, not the captured state', async ({ page }) => {
  await waiting(page, 14)
  const { asked } = await runsReads(page, PAST, [])
  await open(page)
  await expect.poll(() => asked.filter((row) => row.path === '/pipeline/waiting').length).toBe(1)
  await expect(page.locator('.review-band')).toBeVisible()
  await expect(press(page)).toHaveCount(0)
})

/* THE OWNER'S RULING: the press spends at once, with no pre-check and no confirm. IT SPENDS EXACTLY THE CARDS THE SWEEP
 * SAID WAIT FOR A PAID LOOK: the whole send body is those keys and the composer's default reading. A capture in another
 * tab after the band read its list (the waiting answer grows to 30 here) cannot grow the spend. The receipt quotes the
 * SERVER'S count. PROVED RED: sending `{state: 'captured'}` in place of the keys fails the body assertion. */
test('the press spends exactly the cards it named, with no pre-check', async ({ page }) => {
  await waiting(page, 12)
  const { asked, answer } = await runsReads(page, PAST, keysOf(12))
  await paidWait(page, keysOf(12))
  const spends = await spendRoute(page, { cards: 11 })
  await open(page)
  await expect(press(page)).toContainText('Read the 12 left')

  answer(keysOf(30))
  await waiting(page, 30)
  await press(page).click()

  await expect.poll(() => spends.length).toBe(1)
  expect(spends[0]?.body).toEqual({ confirm: true, keys: keysOf(12), crop: true, max_edge: 1200, engine: 'marqo-b' })
  expect(asked.map((row) => row.path)).not.toContain('/pipeline/preflight')
  await expect(page.locator('.bn-toast', { hasText: 'Identify started' })).toContainText('11 cards sent to be read.')
  await expect(page.locator('.runs-composer')).toHaveCount(0)
  await expect(page.getByRole('dialog')).toHaveCount(0)
})

/* THE PRESS SENDS ONLY THE CARDS WAITING FOR A PAID LOOK. Twelve cards wait in scope, but the sweep says only
 * 9/4 and 9/5 wait for a paid look (`paid_keys`, beside `paid`); the rest the free reader has not looked at yet, and a paid
 * read of those would spend money the free reader may save. */
test('the press sends only the paid-look keys, never the unread ones', async ({ page }) => {
  await waiting(page, 12)
  await runsReads(page, PAST, keysOf(12))
  await paidWait(page, ['9/4', '9/5'])
  const spends = await spendRoute(page, { cards: 2 })
  await open(page)
  await expect(press(page)).toContainText('Read the 2 left')
  await press(page).click()
  await expect.poll(() => spends.length).toBe(1)
  expect(spends[0]?.body.keys, 'only the cards the sweep named as waiting for a paid look').toEqual(['9/4', '9/5'])
})

/* AFTER A SPEND THE BAND STOPS OFFERING THOSE CARDS. The run claimed them, so the server's
 * list no longer holds them, and the band reads again once the press answers. */
test('after a spend the band reads again and stops offering the claimed cards', async ({ page }) => {
  await waiting(page, 12)
  const reads = await runsReads(page, PAST, keysOf(12))
  const sweep = await paidWait(page, keysOf(12))
  await spendRoute(page, {
    after: () => {
      reads.answer([])
      sweep.paidKeys = []
    },
  })
  await open(page)
  await press(page).click()
  await expect.poll(() => reads.asked.filter((row) => row.path === '/pipeline/waiting').length).toBe(2)
  await expect(press(page)).toHaveCount(0)
})

/* A REFUSED PRESS MOVES NOTHING (D118). The refusal is a toast, never a notice that grows the
 * band, so the card under review stays where it was. */
test('a refused press says so in a toast and moves nothing', async ({ page }) => {
  await waiting(page, 12)
  await runsReads(page, PAST, keysOf(12))
  await paidWait(page, keysOf(12))
  await spendRoute(page, { refuse: true })
  await open(page)
  const card = page.locator('.review-card')
  const before = await card.boundingBox()
  await press(page).click()
  await expect(page.locator('.bn-toast', { hasText: 'Nothing was paid for' })).toContainText('already paying to read 3')
  const after = await card.boundingBox()
  expect(after?.y).toBe(before?.y)
  expect(after?.x).toBe(before?.x)
})

/* A DOUBLE PRESS BUYS ONCE. Two clicks land in one task, before React can draw the busy state,
 * so the only thing that can stop the second is the screen's own in-flight guard. The server's
 * claim (D174) still refuses a second tab; that half is `make submission-selftest`'s.
 * PROVED RED: deleting the `spending` ref's early return sends two spends. */
test('a double press spends once', async ({ page }) => {
  await waiting(page, 12)
  await runsReads(page, [], keysOf(12))
  await paidWait(page, keysOf(12))
  let release = () => {}
  const held = new Promise<void>((resolve) => {
    release = resolve
  })
  const spends = await spendRoute(page, { hold: held })
  await open(page)
  await press(page).evaluate((button: HTMLButtonElement) => {
    button.click()
    button.click()
  })
  await expect.poll(() => spends.length).toBe(1)
  await expect(press(page)).toBeDisabled()
  release()
  await expect(page.locator('.bn-toast', { hasText: 'Identify started' })).toBeVisible()
  expect(spends).toHaveLength(1)
})

test('the reason lens is disabled while an answer is in flight', async ({ page }) => {
  await open(page)
  let release: () => void = () => undefined
  const held = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route(/\/answer$/, async (route) => {
    await held
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ position: '2/14', cleared: true, restores_to: null }),
    })
  })
  const trigger = page.locator('.review-filters .bn-filterbar-trigger')
  await expect(trigger).toBeEnabled()
  await page.locator('.review-candidate').first().click()
  await expect(trigger).toBeDisabled()
  release()
  await expect(trigger).toBeEnabled()
})

/* ------------------------------------------------------------ the route from Capture to Review (D291)
 * Three defects and one rename found by a walk of the app. Every read is stubbed. */

const routeJson = (body: unknown) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })

/** The reads Review, its Runs sheet and the composer make, with 12 cards waiting in box 5. */
async function stubRouteReads(page: Page): Promise<void> {
  const keys = Array.from({ length: 12 }, (_, at) => `5/${at + 1}`)
  await stubMatchState(page)
  await page.route(/\/status$/, (route) =>
    route.fulfill(routeJson({ captures_root: 'captures', store: 'inventory/store.sqlite', store_exists: true, cards: 12, states: { captured: 12 }, queues: { review: 1, parked: 0 }, next_index: { '5': 13 } })),
  )
  await page.route(/\/photo\/\d+\/\d+/, (route) => route.fulfill({ status: 200, contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="9" height="16"/>' }))
  await page.route(/\/queues$/, (route) => route.fulfill(routeJson({ review: [], parked: [] })))
  await page.route(/\/pipeline\/waiting$/, (route) => route.fulfill(routeJson({ keys, claimed: 0 })))
  await page.route(/\/pipeline\/runs$/, (route) => route.fulfill(routeJson({ runs: [] })))
  await page.route(/\/boxes$/, (route) => route.fulfill(routeJson({ boxes: [] })))
  await page.route(/\/inventory$/, (route) => route.fulfill(routeJson({ version: 2, cards: {} })))
  await page.route(/\/games$/, (route) => route.fulfill(routeJson({ games: [] })))
  await page.route(/\/pipeline\/submissions$/, (route) => route.fulfill(routeJson({ claims: [], counts: { claims: 0, keys: 0, stale: 0 } })))
  await page.route(/\/pipeline\/preflight$/, (route) =>
    route.fulfill(routeJson({ ok: true, exit_code: 0, selection: { state: 'captured' }, sentence: 'captured', scope: null, capture_dirs: [], console: '', claimed: null, total: { photographs: 12, cache_hits: 0, to_send: 12, estimate_usd: 0.04, cards: 12, ...NO_FREE_FIELDS } })),
  )
}

/** Capture with box 5 holding cards, so the Shooting panel's onward button shows. */
async function stubRouteCapture(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 640
    canvas.height = 360
    canvas.getContext('2d')?.fillRect(0, 0, 640, 360)
    const stream = canvas.captureStream(30)
    const media = navigator.mediaDevices as unknown as { enumerateDevices: () => Promise<unknown[]>; getUserMedia: () => Promise<MediaStream> }
    media.enumerateDevices = async () => [{ deviceId: 'canvas', kind: 'videoinput', label: 'Canvas Cam Link', groupId: 'g' }]
    media.getUserMedia = async () => stream
  })
  await page.addInitScript(() => {
    /* eslint-disable-next-line no-restricted-syntax -- SEEDING THE VERY KEY UNDER TEST; the same disable capture-claims.spec.ts carries. */
    window.localStorage.setItem('banchi.capture.setup', JSON.stringify({ box: 5, bid: 15, game: 'pokemon', setHint: '', finish: [], rarityClaim: [], product: null }))
  })
  const game = { key: 'pokemon', display: 'Pokémon', product_line: 'Pokemon', rarities: ['Common'], finishes: ['normal'], condition_by_finish: { normal: 'Near Mint' }, finish_by_rarity: { Common: ['normal'] }, located: true, join_key: 'number_over_printed_total', prompt: 'pokemon', crop_bands: ['title', 'number'], card_aspect: 0.716, unverified: false, catalogued: true }
  await page.route(/\/games$/, (route) => route.fulfill(routeJson({ default: 'pokemon', products: [], product_game: 'pokemon_code', games: [game] })))
  const box = { box: 5, bid: 15, name: 'Test box', sections: [1], state: 'open', capacity: null, fill: 12, next_index: 13, cards: 12, sold: 0, retired: 0, listed: 0, on_hand: 12, sections_detail: [{ section: 1, start: 1, end: null, count: 12, name: null, div: '1' }], layout_token: 'tok1' }
  await page.route(/\/boxes$/, (route) => route.fulfill(routeJson({ boxes: [box] })))
  await page.route(/\/capture\/sitting$/, (route) => route.fulfill(routeJson({ open: true, gap_minutes: 30, cards: [] })))
  await page.route(/\/pipeline\/match\/sweep(\?.*)?$/, (route) => route.fulfill(routeJson({ on: false, running: false, matched: 0, aside: 0, blocked: null, matched_here: 0, paid: 0, unread: 0, paid_keys: [] })))
}

/* NO SCREEN LIST IS TYPED HERE: Review's route is `VIEW_ROUTE`, Runs' is derived from it, and
   Capture's is read off the sidebar link the shell draws from `ROUTES`. Hashes only, no slash. */
const REVIEW_HASH = VIEW_ROUTE.replace('/', '')
const RUNS_HASH = REVIEW_HASH.replace('review', 'runs')

/** The hash of Capture's own sidebar link, read from the page. */
async function captureHash(page: Page): Promise<string> {
  await page.goto(VIEW_ROUTE)
  await expect(page.locator(VIEW)).toBeVisible()
  const href = await page.locator('.bn-side a.bn-nav-link', { hasText: /capture/i }).first().getAttribute('href')
  expect(href, 'the sidebar names Capture').not.toBeNull()
  return href ?? ''
}

async function arriveFromRouteCapture(page: Page): Promise<string> {
  await stubRouteReads(page)
  await stubRouteCapture(page)
  await setViewport(page, { width: 1440, height: 900 })
  const capture = await captureHash(page)
  await page.goto(`/${capture}`)
  await settleFonts(page)
  await expect(page.locator('.capture-onward button')).toBeVisible()
  return capture
}

test('a typed #/runs leaves one history entry, so one Back returns', async ({ page }) => {
  await stubRouteReads(page)
  await setViewport(page, { width: 1440, height: 900 })
  const capture = await captureHash(page)
  await page.goto(`/${capture}`)
  await page.evaluate((hash) => (window.location.hash = hash), RUNS_HASH)
  await expect.poll(() => new URL(page.url()).hash).toContain(REVIEW_HASH)
  await page.waitForTimeout(300) // keep: a redirect that pushes lands a tick after the first URL change
  await page.goBack()
  await expect.poll(() => new URL(page.url()).hash).toBe(capture)
})

test('the onward button then one Back returns to Capture', async ({ page }) => {
  const capture = await arriveFromRouteCapture(page)
  await page.locator('.capture-onward button').click()
  await expect.poll(() => new URL(page.url()).hash).toContain(REVIEW_HASH)
  await page.waitForTimeout(300) // keep: a redirect that pushes lands a tick after the first URL change
  await page.goBack()
  await expect.poll(() => new URL(page.url()).hash).toBe(capture)
})

test('the onward button lands on Review with no composer open', async ({ page }) => {
  await arriveFromRouteCapture(page)
  await page.locator('.capture-onward button').click()
  await expect(page.locator('main.review')).toBeVisible()
  await page.waitForTimeout(500) // keep: the composer opens a beat after arrival, so absence needs the beat
  await expect(page.getByRole('dialog')).toHaveCount(0)
})

test('the onward button reads just Review', async ({ page }) => {
  await arriveFromRouteCapture(page)
  await expect(page.locator('.capture-onward button')).toHaveText('Review')
})

test('arriving at Review, the band moves nothing', async ({ page }) => {
  await stubRouteReads(page)
  await seedPopulatedReview(page)
  await watchShifts(page)
  await setViewport(page, { width: 1440, height: 900 })
  await page.goto(VIEW_ROUTE)
  await settleFonts(page)
  await expect(page.locator('.review-band')).toBeVisible()
  await page.waitForTimeout(800) // keep: the window is the measurement
  const { shifts } = await readShifts(page)
  expect(sumOf(shifts), describeShifts(shifts)).toBe(0)
})

/* ------------------------------------------------------------ the band and Queue button hold their frames (D291) */

/** Holds every `/queues` read until `release()`, registered after `open`'s own so it wins. */
async function holdQueues(page: Page): Promise<() => void> {
  let release: () => void = () => undefined
  const gate = new Promise<void>((resolve) => (release = resolve))
  await page.route(/\/queues$/, async (route) => {
    await gate
    await route.fallback()
  })
  return () => release()
}

/* THE QUEUE BUTTON IS HELD ON THE FIRST LOAD ONLY. A reload and an Identify now each
 * read the queues again; none may hide the button or take focus off it. */
test('the Queue button keeps focus and stays visible across a reload', async ({ page }) => {
  await open(page)
  const toggle = page.locator('.review-queue-toggle')
  await toggle.focus()
  const release = await holdQueues(page)
  await page.keyboard.press('r')
  await page.waitForTimeout(300) // keep: the read is held, so the loading state is what is measured
  await expect(toggle).toBeVisible()
  await expect(toggle).toBeFocused()
  release()
  await page.waitForTimeout(300) // keep: the answer lands after the gate opens
  await expect(toggle).toBeVisible()
  await expect(toggle).toBeFocused()
})

test('the Queue button stays visible across the press', async ({ page }) => {
  await waiting(page, 12)
  const reads = await runsReads(page, PAST, keysOf(12))
  await paidWait(page, keysOf(12))
  await spendRoute(page, { after: () => reads.answer([]) })
  await open(page)
  await expect(press(page)).toBeVisible()
  const release = await holdQueues(page)
  await press(page).click()
  await page.waitForTimeout(300) // keep: the read is held, so the loading state is what is measured
  const toggle = page.locator('.review-queue-toggle')
  await expect(toggle).toBeVisible()
  await expect(toggle).not.toHaveAttribute('inert', /.*/)
  release()
})

/* ------------------------------------------------------------ the summary band (identify-engine-pick.md section 8) */

test.describe('the Review summary band', () => {
  /* THE REVIEW SUMMARY BAND (`docs/specs/identify-engine-pick.md`, section 8). It replaces `.review-identify-strip`
   * in the same slot. These cases are written RED against the strip and go green when the band is built.
   *
   * WHAT THE BUILDER MUST ADD, NAMED SO THE FIXTURE AND THE CODE AGREE:
   *   - the band's root is `.review-band`; each count is a `.review-band-count`; the health line is `.review-band-health`;
   *     the paid press is a button named "Read the N left, about $X"; the way back is a button or link "Back to Capture".
   *   - `GET /pipeline/match/sweep?keys=<csv>` adds two fields beside `matched_here`:
   *       `paid`   how many named keys wait for a paid look (captured, no identification, tried by the free reader and not accepted)
   *       `unread` how many named keys the free reader has not looked at yet (captured, no identification, not tried, not set aside)
   *     "waiting for you" is read client-side from `/queues` (review rows whose `box/index` is in the scope).
   *   - the scope's keys are `GET /capture/sitting`'s `cards[].key` when `open`; otherwise `GET /pipeline/waiting`'s `keys`.
   *   The stub below answers each count from the keys it was ASKED, so a band that scopes wrongly reads wrong numbers.
   */

  const SIZES = [
    { width: 1440, height: 900 },
    { width: 820, height: 1000 },
  ] as const

  /** Per position key, what the pipeline knows. The sweep stub counts over whatever keys it is asked. */
  type Fate = 'matched' | 'paid' | 'unread' | 'review' | 'done'

  const keyOf = (n: number): string => `3/${n}`

  /** IN THE SITTING: 3/1-3/10. matched 3, paid 2, unread 2, waiting for you 2, one already answered.
   *  OUTSIDE IT: 3/11 matched, 3/12 waits for the owner, 3/13 waits for a paid look, 3/14 unread. A band scoped to
   *  every card would read matched 4, paid 3, unread 3, you 3. */
  const FATES: Record<string, Fate> = {
    '3/1': 'matched', '3/2': 'matched', '3/3': 'matched',
    '3/4': 'paid', '3/5': 'paid',
    '3/6': 'unread', '3/7': 'unread',
    '3/8': 'review', '3/9': 'review',
    '3/10': 'done',
    '3/11': 'matched', '3/12': 'review', '3/13': 'paid', '3/14': 'unread',
  }
  const SITTING = Array.from({ length: 10 }, (_, i) => keyOf(i + 1))
  const EVERY_OPEN = Object.keys(FATES).filter((key) => FATES[key] !== 'done')

  type Wire = {
    on: boolean
    running: boolean
    blocked: null | 'runtime_missing'
    aside: number
    fates: Record<string, Fate>
    sittingOpen: boolean
    /** the keys each `?keys=` read named, newest last */
    asked: string[][]
    spends: { body: Record<string, unknown> }[]
    /** hold the first keys-scoped answer back until released */
    hold: Promise<void> | null
    /** Pokemon cards in scope with no set hint: the free reader never queues them (`unhinted` on the wire) */
    unhinted: number
    /** keys that carry a free-reader row AND an open review row */
    alsoReview: string[]
    /** runs when a spend lands, so a case can move the cards the way the server would */
    onSpend: (() => void) | null
  }

  const json = (body: unknown) => ({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })

  function reviewEntry(key: string) {
    const [box, index] = key.split('/').map(Number) as [number, number]
    return {
      position: `Box ${box}, Section 1, Card ${index}`,
      box,
      index,
      label: `Box ${box}, Section 1, Card ${index}`,
      photo: `photos/${box}/${index}.jpg`,
      read: { name: 'Snorlax', number: '051', printed_total: '132', set_hint: 'ME01' },
      confidence: null,
      reason: 'no_catalog_row',
      candidates: [],
      first_seen: '2026-09-01T12:00:00+00:00',
      market: null,
      cleared_by_human: false,
    }
  }

  function sittingCard(key: string) {
    const [box, index] = key.split('/').map(Number) as [number, number]
    return {
      box, index, key, label: `Box ${box}, Section 1, Card ${index}`, section: 1, card: index,
      new_box: index === 1, created: true, photo: `/tmp/${key.replace('/', '-')}.jpg`, capture_id: null,
      place: { box_total: index }, captured_at: '2026-09-25T12:00:00+00:00', set_hint: null,
      metadata_finish: null, game: 'pokemon', state: 'captured',
    }
  }

  async function seed(page: Page, over: Partial<Wire> = {}): Promise<Wire> {
    const wire: Wire = {
      on: true, running: false, blocked: null, aside: 0, fates: { ...FATES },
      sittingOpen: true, asked: [], spends: [], hold: null, unhinted: 0, alsoReview: [], onSpend: null, ...over,
    }
    await page.route(/\/capture\/sitting$/, (route) =>
      route.fulfill(json({ open: wire.sittingOpen, gap_minutes: 30, cards: wire.sittingOpen ? SITTING.map(sittingCard) : [] })),
    )
    await page.route(/\/boxes$/, (route) =>
      route.fulfill(json({ boxes: [{ box: 3, bid: 13, name: 'Band box', sections: [1], state: 'open', capacity: null, fill: 14, next_index: 15, cards: 14, sold: 0, retired: 0, listed: 0, on_hand: 14, sections_detail: [{ section: 1, start: 1, end: null, count: 14, name: null, div: '1' }], layout_token: 't' }] })),
    )
    await page.route(/\/status$/, (route) =>
      route.fulfill(json({ captures_root: 'captures', store: 'inventory/store.sqlite', store_exists: true, cards: 14, states: { captured: 8 }, queues: { review: 3, parked: 0 }, next_index: { '3': 15 } })),
    )
    await page.route(/\/pipeline\/match\/sweep(\?.*)?$/, async (route) => {
      const asked = new URL(route.request().url()).searchParams.get('keys')
      if (asked === null) return route.fulfill(json({ on: wire.on, running: wire.running, blocked: wire.blocked, aside: wire.aside, matched: 500 }))
      const keys = (asked.match(/[^,]+/g) ?? [])
      wire.asked.push(keys)
      if (wire.hold !== null) await wire.hold
      const count = (fate: Fate) => keys.filter((key) => wire.fates[key] === fate).length
      return route.fulfill(
        json({ on: wire.on, running: wire.on && wire.running, worker: wire.running, blocked: wire.blocked, aside: wire.aside, matched_here: count('matched'), paid: count('paid'), matched_keys: keys.filter((key) => wire.fates[key] === 'matched'), unhinted: wire.unhinted, paid_keys: keys.filter((key) => wire.fates[key] === 'paid'), unread: count('unread') }),
      )
    })
    await page.route(/\/queues$/, (route) =>
      route.fulfill(json({ review: [...Object.keys(wire.fates).filter((key) => wire.fates[key] === 'review'), ...wire.alsoReview].map(reviewEntry), parked: [] })),
    )
    await page.route(/\/pipeline\/waiting$/, (route) =>
      route.fulfill(json({ keys: Object.keys(wire.fates).filter((key) => ['matched', 'paid', 'unread'].includes(wire.fates[key] ?? '')), claimed: 0 })),
    )
    /* $0.30 over 10 cards: $0.03 a card, so two paid cards read "about $0.06". */
    await page.route(/\/pipeline\/runs$/, (route) => route.fulfill(json({ runs: [runRow({ counts: { cards_in: 10 }, usage: { cost_usd: 0.3 } })] })))
    await page.route(/\/photo\/\d+\/\d+/, (route) => route.fulfill({ status: 200, contentType: 'image/gif', body: Buffer.from('R0lGODlhAQABAAAAACw=', 'base64') }))
    await page.route(/\/review\/\d+\/\d+\/catalog/, (route) => route.fulfill(json({ box: 3, index: 8, game: 'pokemon', query: '', searched: false, rows: [], found: 0, truncated: false })))
    await page.route(/\/pipeline\/identify$/, (route) => {
      wire.spends.push({ body: route.request().postDataJSON() as Record<string, unknown> })
      wire.onSpend?.()
      return route.fulfill(
        json({ started: [{ run: '2026-09-25-box3-01', path: '/tmp/runs/x', pid: 999, selection: { keys: [] }, scope: null, cards: 2, argv: [] }], failed: [] }),
      )
    })
    await page.route(/\/pipeline\/runs\/[^/]+\/scope/, (route) => route.fulfill(json({ run: 'x', games: [], scopes: [], asked: null, reason: null, message: null })))
    await page.route(/\/pipeline\/runs\/[^/]+$/, (route) => route.fulfill(json({ ...runRow({ live: true, pid: 999, phase: 'identifying', collected: false }), console: '', files: [], manifest: {} })))
    return wire
  }

  const band = (page: Page): Locator => page.locator('.review-band')
  const count = (page: Page, label: string): Locator => band(page).locator('.review-band-count').filter({ hasText: new RegExp(label, 'i') })
  const health = (page: Page): Locator => band(page).locator('.review-band-health')
  const press = (page: Page): Locator => band(page).getByRole('button', { name: /^Read the \d+ left/ })

  /** Capture's "Review" button shows once a box with cards is picked: the Box field, `3`, Enter. */
  async function pickBox(page: Page): Promise<void> {
    await expect(async () => {
      await page.keyboard.press('b')
      await expect(page.locator('.capture-opt').filter({ hasText: /Band box/ })).toBeVisible({ timeout: 1_000 })
    }).toPass({ timeout: 15_000 })
    await page.keyboard.type('3')
    await page.keyboard.press('Enter')
  }

  async function openReview(page: Page): Promise<void> {
    await page.goto('/#/review')
    await expect(page.locator('main.review')).toBeVisible()
    await settleFonts(page)
  }

  test.beforeEach(async ({ page }) => stubStore(page))

  for (const size of SIZES) {
    test.describe(`${size.width}`, () => {
      test(`opening Review from Capture shows the band in the strip's slot, and Back to Capture returns`, async ({ page }) => {
        await seed(page)
        await setViewport(page, size)
        await page.goto('/#/capture')
        await expect(page.locator('.capture-odo')).toBeVisible()
        await pickBox(page)
        await page.getByRole('button', { name: 'Review', exact: true }).click()
        await expect(page.locator('main.review')).toBeVisible()
        await expect(band(page)).toBeVisible()
        await expect(page.locator('.review-identify-strip')).toHaveCount(0)
        /* the strip's slot: the first thing in the view, above the filters and the card being judged */
        const slot = await band(page).evaluate((el) => {
          const view = el.closest('main.review')!
          const rect = (node: Element) => node.getBoundingClientRect().top
          const others = Array.from(view.querySelectorAll('.review-filters, .review-card, .review-lone, .review-catalog'))
          return { bandTop: rect(el), firstOther: others.length === 0 ? Infinity : Math.min(...others.map(rect)) }
        })
        expect(slot.bandTop, 'the band sits above the work').toBeLessThanOrEqual(slot.firstOther)
        await band(page).getByRole('button', { name: 'Back to Capture' }).or(band(page).getByRole('link', { name: 'Back to Capture' })).first().click()
        await expect(page).toHaveURL(/#\/capture/)
        await expect(page.locator('.capture-odo')).toBeVisible()
      })

      test('four labeled counts are scoped to the sitting, and matched free equals the Capture counter', async ({ page }) => {
        const wire = await seed(page)
        await setViewport(page, size)
        await openReview(page)
        await expect(count(page, 'matched free')).toHaveText(/3\s+matched free/i)
        await expect(count(page, 'waiting for a paid look')).toHaveText(/2\s+waiting for a paid look/i)
        await expect(count(page, 'not yet looked at')).toHaveText(/2\s+not yet looked at/i)
        await expect(count(page, 'waiting for you')).toHaveText(/2\s+waiting for you/i)
        expect(wire.asked.at(-1), 'the band reads the sitting\'s keys, the same a Capture counter sends').toEqual(SITTING)
        /* the Capture counter, same keys, same stub: the two numbers must agree */
        await page.goto('/#/capture')
        await expect(page.locator('.capture-odo')).toBeVisible()
        const matched = page.locator('.capture-odo .bn-stat').filter({ hasText: 'matched' }).locator('.bn-stat-value')
        await expect(matched).toHaveText('3')
      })

      test('the press names its count and cost, spends at once with no confirm, and is absent at zero', async ({ page }) => {
        const wire = await seed(page)
        await setViewport(page, size)
        await openReview(page)
        const go = press(page)
        await expect(go).toHaveText(/^\s*Read the 2 left, about \$0\.06\s*$/)
        await go.click()
        await expect(page.getByRole('dialog')).toHaveCount(0)
        await expect.poll(() => wire.spends.length).toBe(1)
        const sent = JSON.stringify(wire.spends[0]!.body)
        expect(sent).toContain('3/4')
        expect(sent).toContain('3/5')
        expect(sent, 'only the paid cards in the sitting, never 3/13').not.toContain('3/13')
      })

      test('a long health line keeps the presses inside the band, clear of the photo, and the band the same height', async ({ page }) => {
        const wire = await seed(page, { running: true, aside: 2, unhinted: 2 })
        await setViewport(page, size)
        await openReview(page)
        await expect(health(page)).toHaveText(/matching now/i)
        await expect(health(page)).toHaveText(/2 set aside/i)
        await expect(health(page)).toHaveText(/2 need a set named/i)
        await expect(press(page)).toBeVisible()
        await settleMotion(page)
        const boxes = () =>
          page.evaluate(() => {
            const rect = (sel: string) => {
              const r = document.querySelector(sel)?.getBoundingClientRect()
              return r === undefined ? null : { x: r.x, y: r.y, right: r.right, bottom: r.bottom, height: r.height }
            }
            const line = document.querySelector('.review-band-health') as HTMLElement | null
            const clipped = line === null ? true : [line, ...Array.from(line.querySelectorAll('*'))].some((el) => el.scrollWidth > el.clientWidth + 1 || getComputedStyle(el).textOverflow === 'ellipsis')
            return { band: rect('.review-band'), press: rect('.review-band-read'), back: rect('.review-band-back'), health: rect('.review-band-health'), photo: rect('.review-photo'), clipped }
          })
        const long = await boxes()
        const inside = (part: { x: number; y: number; right: number; bottom: number } | null) =>
          part !== null && long.band !== null && part.x >= long.band.x - 1 && part.right <= long.band.right + 1 && part.y >= long.band.y - 1 && part.bottom <= long.band.bottom + 1
        expect(inside(long.press), 'the press sits inside the band').toBe(true)
        expect(inside(long.back), 'Back to Capture sits inside the band').toBe(true)
        expect(inside(long.health), 'the health line sits inside the band').toBe(true)
        expect(long.clipped, 'no part of the health line is clipped or ellipsised').toBe(false)
        if (long.band !== null && long.photo !== null) {
          expect(long.band.bottom, 'nothing in the band reaches the photo').toBeLessThanOrEqual(long.photo.y + 0.5)
          for (const part of [long.press, long.back, long.health]) expect(part!.bottom).toBeLessThanOrEqual(long.photo.y + 0.5)
        }
        /* the same band with a short health line: nothing running, nothing set aside, nothing unhinted */
        wire.running = false
        wire.aside = 0
        wire.unhinted = 0
        await expect(health(page)).not.toHaveText(/set aside/i, { timeout: 8_000 }) // keep: waits one 3s poll tick
        await settleMotion(page)
        const short = await boxes()
        expect(short.band!.height, 'the band changed height with a shorter health line').toBe(long.band!.height)
      })

      test('the band holds its loaded size from first paint, and a count change moves nothing below it', async ({ page }) => {
        let release: () => void = () => undefined
        const wire = await seed(page, { running: true, hold: new Promise<void>((done) => (release = done)) })
        await watchShifts(page)
        await setViewport(page, size)
        await openReview(page)
        await expect(band(page)).toBeVisible()
        const below = () =>
          band(page).evaluate((el) => {
            const r = el.getBoundingClientRect()
            const next = el.nextElementSibling?.getBoundingClientRect()
            return { top: r.top + scrollY, width: r.width, height: r.height, nextTop: next === undefined ? null : next.top + scrollY }
          })
        const first = await below()
        release()
        await expect(count(page, 'matched free')).toHaveText(/3\s+matched free/i)
        await settleMotion(page)
        expect(await below(), 'the band changed size when its counts arrived').toEqual(first)
        const mark = await markNow(page)
        const loaded = await below()
        for (const [matched, paid] of [[10, 2], [100, 1], [1000, 0]] as const) {
          for (let at = 1; at <= 10; at += 1) wire.fates[keyOf(at)] = 'done'
          for (let at = 1; at <= Math.min(matched, 10); at += 1) wire.fates[keyOf(at)] = at <= paid ? 'paid' : 'matched'
          await expect(count(page, 'matched free')).toHaveText(new RegExp(`\\b${Math.min(matched, 10) - paid}\\s+matched free`, 'i'), { timeout: 8_000 }) // keep: waits one 3s poll tick per step
          expect(await below(), `a count change moved the band or what is under it (${matched})`).toEqual(loaded)
        }
        await expect(press(page)).toHaveCount(0)
        expect(await below(), 'the press leaving moved what is under the band').toEqual(loaded)
        const shifts = (await readShifts(page)).shifts.filter((s) => s.at >= mark)
        expect(sumOf(shifts), describeShifts(shifts)).toBe(0)
      })
    })
  }

  test.describe('1440', () => {
    test.beforeEach(async ({ page }) => setViewport(page, SIZES[0]))

    test('with no sitting on this device the scope is every captured card with no identification', async ({ page }) => {
      const wire = await seed(page, { sittingOpen: false })
      await openReview(page)
      await expect(count(page, 'matched free')).toHaveText(/4\s+matched free/i)
      await expect(count(page, 'waiting for a paid look')).toHaveText(/3\s+waiting for a paid look/i)
      await expect(count(page, 'not yet looked at')).toHaveText(/3\s+not yet looked at/i)
      expect(new Set(wire.asked.at(-1)), 'the keys are the unidentified captured cards').toEqual(new Set(EVERY_OPEN.filter((key) => FATES[key] !== 'review')))
    })

    test('the health line says matching now while a worker runs', async ({ page }) => {
      await seed(page, { running: true })
      await openReview(page)
      await expect(health(page)).toHaveText(/matching now/i)
    })

    test('the health line says needs setup when blocked', async ({ page }) => {
      await seed(page, { blocked: 'runtime_missing' })
      await openReview(page)
      await expect(health(page)).toHaveText(/needs setup/i)
    })

    test('the health line says needs setup when the model is missing', async ({ page }) => {
      await seed(page)
      await page.route(/\/pipeline\/match$/, (route) =>
        route.fulfill(json({ model_present: false, model_ok: false, model_bytes: 0, index_present: false, ready: false })),
      )
      await openReview(page)
      await expect(health(page)).toHaveText(/needs setup/i)
    })

    test('the health line says how many were set aside', async ({ page }) => {
      await seed(page, { aside: 3 })
      await openReview(page)
      await expect(health(page)).toHaveText(/3 set aside/i)
    })

    test('after a press with the sitting open, the band reads again and does not offer the same cards twice', async ({ page }) => {
      const wire = await seed(page)
      wire.onSpend = () => {
        wire.fates['3/4'] = 'done'
        wire.fates['3/5'] = 'done'
      }
      await openReview(page)
      await expect(press(page)).toContainText('Read the 2 left')
      await press(page).click()
      await expect.poll(() => wire.spends.length).toBe(1)
      const reads = wire.asked.length
      await expect.poll(() => wire.asked.length, { timeout: 6_000 }).toBeGreaterThan(reads) // keep: one poll tick, never the 20s idle one
      await expect(press(page)).toHaveCount(0)
    })

    test('a card with an open review row counts only in waiting for you, never also in matched free', async ({ page }) => {
      await seed(page, { alsoReview: ['3/1'] })
      await openReview(page)
      await expect(count(page, 'waiting for you')).toHaveText(/3\s+waiting for you/i)
      await expect(count(page, 'matched free')).toHaveText(/2\s+matched free/i)
    })

    test('the health line shows set aside beside matching now', async ({ page }) => {
      await seed(page, { running: true, aside: 2 })
      await openReview(page)
      await expect(health(page)).toHaveText(/matching now/i)
      await expect(health(page)).toHaveText(/2 set aside/i)
    })

    test('the health line names the cards that need a set named', async ({ page }) => {
      await seed(page, { unhinted: 2 })
      await openReview(page)
      await expect(health(page)).toHaveText(/2 need a set named/i)
    })

    test('a carried scope wins over the open sitting', async ({ page }) => {
      const carried = ['3/2', '3/3', '3/4']
      await page.addInitScript((keys) => window.sessionStorage.setItem('banchi.run-scope', JSON.stringify({ keys })), carried)
      const wire = await seed(page)
      await openReview(page)
      await expect(count(page, 'matched free')).toHaveText(/2\s+matched free/i)
      expect(wire.asked.at(-1), 'the band reads the handed-off cards, not the sitting').toEqual(carried)
    })

    test('the band names no mechanism', async ({ page }) => {
      for (const over of [{ running: true }, { blocked: 'runtime_missing' as const }, { aside: 2 }]) {
        await page.unrouteAll({ behavior: 'ignoreErrors' })
        await seed(page, over)
        await openReview(page)
        await expect(band(page)).toBeVisible()
        const said = await band(page).innerText()
        expect(said, 'the band is empty').not.toBe('')
        expect(said).not.toMatch(/\b(runs?|readers?|models?|sweep|marqo|haiku|engine|pipeline)\b/i)
      }
    })
  })
})

/* ------------------------------------------------------- the lookahead chip, never clipped */

/* PR #694 shrank the photograph by the summary band's height, and at 820 the "Next" chip on it
   then clipped its own price ("no market pric"). No word in the chip may be cut by its own box,
   the chip stays inside the photograph, and its height is one number whether the next card's
   name is short or long (nothing on screen moves unless the person moved it). The name span ellipsizes by design and is exempt from the clip check. */
const nextOf = (name: string): Entry[] => [
  entry(14, 'set_ambiguous', '84.50', [candidate(0, '84.50'), candidate(1, '114.08')]),
  { ...entry(2, 'set_ambiguous', null, [candidate(0, '41.00')]), read: { name, number: '014/132', set: 'ME01' } },
]

for (const width of [820, 1440]) {
  test(`the next-card chip is not clipped and keeps one height at ${width} wide, light`, async ({ page }) => {
    await page.addInitScript(() => window.localStorage.setItem('banchi.theme', 'light'))
    const heights: number[] = []
    for (const name of ['Mew', 'Snorlax, Sleeping Giant']) {
      await open(page, nextOf(name)) // a later route for /queues wins over the earlier one
      await setViewport(page, { width, height: DESK.height })
      await settleFonts(page)
      await settleEnter(page)
      const chip = page.locator('.review-next')
      await expect(chip).toContainText('no market price')
      const read = await chip.evaluate((el) => {
        const photo = el.parentElement!.querySelector('.review-frame')!.getBoundingClientRect()
        const box = el.getBoundingClientRect()
        const kids = [el, ...Array.from(el.children)] as HTMLElement[]
        return {
          clipped: kids.filter((k) => !k.classList.contains('review-next-name') && k.scrollWidth > k.clientWidth).map((k) => `${k.className}: ${k.scrollWidth}>${k.clientWidth}`),
          inside: box.left >= photo.left && box.right <= photo.right && box.top >= photo.top && box.bottom <= photo.bottom,
          height: box.height,
        }
      })
      expect(read.clipped, `${name}: text cut by its own box`).toEqual([])
      expect(read.inside, `${name}: chip box leaves the photograph`).toBe(true)
      heights.push(read.height)
    }
    expect(heights[1], 'chip height changes with its text').toBe(heights[0])
  })
}
