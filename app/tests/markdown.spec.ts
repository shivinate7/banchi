import { test, expect, type Page } from '@playwright/test'
import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'

/* THE STALE-LISTING MARKDOWN, ASSERTED WHERE NOTHING ELSE CAN SEE IT (D100).
 *
 * `CLAUDE.md`'s hard rule: a capability that exists only in `server/` is not done. The CLI has
 * a harness block (T7's `check_markdown`) and the routes answer; what neither can say is
 * whether a person can reach any of it, or whether the three presses arrive in the order the
 * design says they do. That is this file.
 *
 * IT IS A SHEET, AND EVERY CASE GOES THROUGH THE CONTROL THAT OPENS IT. That is not a layout
 * detail dressed up as behaviour — reachability from a screen IS the property this file exists
 * to assert, and a sheet nobody can open is exactly the server-only capability the hard rule
 * refuses. The markup is in the DOM whether the sheet is open or not, so a case that asserted
 * its way into the closed panel would pass against a build whose opener had been deleted;
 * `does not exist until it is asked for` is the case that pins that down.
 *
 * THE STRONGEST CASES HERE ARE ABSENCES, which is the form a later refactor cannot quietly
 * satisfy: none of the three presses EXISTS before the read before it has answered, and both
 * previews carry `write: false`. That is D33's two-step gate applied twice — to the press that
 * writes a worklist and to the press that writes the file the operator uploads.
 *
 * AND ONE PRESENCE THAT IS LOAD-BEARING: the sheet says, in its own words, that nothing is
 * deleted at TCGplayer and that the age it ranks on is OWNERSHIP age. The second is the weak
 * term in the whole predicate, and a screen that stopped saying so would be a screen that
 * quietly started lying — see D100 and `pipeline/reprice.py`'s header.
 *
 * NO REAL REQUEST IS MADE. Both routes are intercepted and their bodies recorded, which is
 * what lets these cases assert what the screen WOULD have sent.
 */

/* THE SHEET LIVES ON `#/pricing` NOW (D105) — it decides a price, and that is the screen
   where prices are decided. D100 put it on `#/runs` because it reads the same export as the
   store-wide reconcile, which is kinship of implementation rather than of work. */
const VIEW = '/#/pricing'
const STAMP = '20260903-221500'

type Wire = { path: string; body: Record<string, unknown> }

const SURVEY = `
live export      /tmp/live.csv
                 757 row(s), 441 live at TCGplayer
window           7 day(s) — no sale here and owned since before 2026-08-27T00:00:00

age is OWNERSHIP, not listing age.

would mark down  109 SKU(s), 394 copy(ies)
                 asking $193.06 -> $173.36  (giving up $19.70)

  copies  sku         asking      new   vs mkt   card
       4  8936515        0.49     0.44    +81%   Bulbasaur - 001/132 (Near Mint)
`.trim()

const APPLIED = `
worklist         /tmp/worklist.csv
would upload     109 SKU(s), 394 copy(ies)
`.trim()

/** The sheet itself. A dialog, so a screen reader is told the rest of the page is behind it. */
const sheet = (page: Page) => page.getByRole('dialog', { name: 'Mark down what is not selling' })

/** The control on the Runs header that opens it — the only way in, and the reachability
 *  claim. Its accessible name is deliberately not any of the three presses inside the sheet. */
const opener = (page: Page) => page.getByRole('button', { name: 'Mark down stale listings' })

const worklistPress = (page: Page) => page.getByRole('button', { name: /Write the worklist/ })
const checkPress = (page: Page) => page.getByRole('button', { name: /^Check it$/ })
const importPress = (page: Page) => page.getByRole('button', { name: /Write the import CSV/ })

/** Both consoles are `LogWell`s and carry this class; the survey's is the first. */
const consoles = (page: Page) => page.locator('.markdown-console')

/** Markdowns this store has already written, for the cases about the history list. Default is
 *  empty, which is what every case written before D103 assumed. */
let HISTORY: unknown[] = []

/** Whether `POST /pipeline/live-export` answers or refuses. `'refuse'` sends the envelope the
 *  capture server actually sends, so the danger arm is exercised against a real shape. */
let LIVE_FETCH: 'ok' | 'refuse' = 'ok'

/** The HOST screen's own reads, kept apart from `wire` (D105).
 *
 *  `wire` is the sheet's traffic and half this file indexes it positionally — `wire[0]` is the
 *  preview, `wire[1]` the write. Folding the pricing screen's mount reads into it renumbers
 *  every one of those. This is the screen underneath, and only the key-guard case reads it. */
let HOST_READS: string[] = []

async function stub(page: Page): Promise<Wire[]> {
  const wire: Wire[] = []
  await page.route(/\/pipeline\/markdowns$/, async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ markdowns: HISTORY }),
      })
      return
    }
    const body = route.request().postDataJSON()
    wire.push({ path: '/pipeline/markdowns', body })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        exit_code: 0,
        wrote: Boolean(body.write),
        console: SURVEY,
        stamp: body.write ? STAMP : null,
      }),
    })
  })
  await page.route(/\/pipeline\/live-export$/, async (route) => {
    wire.push({ path: '/pipeline/live-export', body: route.request().postDataJSON() })
    if (LIVE_FETCH === 'refuse') {
      await route.fulfill({
        status: 502,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'tcg_session_expired',
            message: 'The TCGplayer session has expired. Sign in and copy the cookie again.',
          },
        }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        fetched: 'live-tcgplayer-20260906-120000.csv',
        at: '2026-09-06T12:00:00.000+00:00',
        rows: 759,
        live_rows: 441,
        live_copies: 1140,
      }),
    })
  })
  await page.route(/\/pipeline\/markdowns\/[^/]+\/apply$/, async (route) => {
    const body = route.request().postDataJSON()
    /* THE STAMP IS IN THE PATH AND NOWHERE ELSE, so the record keeps it. A hand-back judged
       against another markdown's manifest is the failure D103's resume exists to prevent, and
       a record that flattened this to `/apply` could not tell the two apart. */
    wire.push({ path: new URL(route.request().url()).pathname, body })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        exit_code: 0,
        wrote: Boolean(body.write),
        console: APPLIED,
        stamp: STAMP,
      }),
    })
  })
  /* THE REST OF THE SCREEN, ANSWERED EMPTY. This file is about one sheet; what the host screen
     draws around it belongs to `pricing.spec.ts`. A store with no joined runs is deliberate —
     it puts the sheet in the empty-state branch, which is where an operator who has photographed
     nothing will look for it, and proves the door exists there too. */
  await page.route(/\/boxes$/, async (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"boxes":[]}' }),
  )
  await page.route(/\/pipeline\/runs$/, async (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"runs":[]}' }),
  )
  await page.route(/\/pipeline\/pricing/, async (route) => {
    /* RECORDED, because a reload is exactly what this call being made twice LOOKS like — and
       the key-guard case below has nothing else to watch. */
    HOST_READS.push(new URL(route.request().url()).pathname)
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        runs: [], roster: [], skus: [], written_at: {}, skipped: [], asked: [],
 threshold: null, floor: null,
      }),
    })
  })
  /* REGISTERED LAST AND SO MATCHED FIRST — Playwright walks newest-first, and this pattern
     also matches `/pipeline/pricing` when no run is picked (no query, so `$` still anchors).
     Both are recorded by pathname rather than by which handler caught them. */
  await page.route(/\/pricing$/, async (route) => {
    HOST_READS.push(new URL(route.request().url()).pathname)
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        corpus: {
          version: 1,
          policy: { rule: 'match', basis: 'market', sub_threshold: { flat: '0.49' }, threshold: '0.49' },
          skus: {},
        },
        path: '/tmp/prices.json',
        revision: 'rev-1',
      }),
    })
  })
  await page.goto(VIEW)
  await settleFonts(page)
  return wire
}

async function open(page: Page): Promise<Wire[]> {
  HOST_READS = []
  const wire = await stub(page)
  await stubTheLens(page)
  await opener(page).click()
  await expect(sheet(page)).toBeVisible()
  return wire
}

/** What `#/pricing?markdown=<stamp>` reads on arrival — the destination of this sheet's own
 *  door (D103).
 *
 *  STUBBED HERE RATHER THAN THE DOOR CASE ASSERTING LESS. `shell.ts`'s seal records every
 *  unstubbed read and fails the test that made it, which is exactly right: pressing a button
 *  that leaves for a screen is a claim about where it lands, and a case that stopped at "the
 *  button exists" would not catch a door wired to the wrong stamp — the one failure that would
 *  open somebody else's survey.
 *
 *  DELIBERATELY THIN. This file is about the sheet; `pricing-markdown.spec.ts` owns what the
 *  lens draws. All these have to do is let the destination mount without leaking. */
async function stubTheLens(page: Page) {
  await page.route(/\/pipeline\/markdowns\/[^/]+\/table$/, async (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        stamp: STAMP,
        at: '2026-09-06T00:00:00.000+00:00',
        asked: {},
        counts: { considered: 0, offered: 0, deferred: 0, refused: 0 },
        source: {},
        skus: [],
        says: {},
        unpriceable: [],
        /* The cut-off, which is the floor (D9, amended 2026-09-09) — the same figure this
           fixture's `policy.threshold` carries, because the server sends one key for both. */
        floor: '0.49',
      }),
    }),
  )
  await page.route(/\/pricing$/, async (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        corpus: {
          version: 1,
          policy: { rule: 'match', basis: 'market', sub_threshold: { flat: '0.49' }, threshold: '0.49' },
          skus: {},
        },
        path: '/tmp/prices.json',
        revision: 'rev-1',
      }),
    }),
  )
}

async function pickExport(page: Page) {
  await page.locator('.markdown .runs-drop input[type=file]').setInputFiles({
    name: 'TCGplayer__MyPricing.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('TCGplayer Id,Total Quantity\n8936515,4\n'),
  })
}

async function pickWorklist(page: Page) {
  await page.locator('.markdown .runs-filebtn input[type=file]').setInputFiles({
    name: 'worklist.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('TCGplayer Id,TCG Marketplace Price\n8936515,0.44\n'),
  })
}

/* NOTHING HERE MAY REACH THE CAPTURE SERVER, AND THE SHELL'S OWN READ IS NOT THIS SCREEN'S.
   `app/tests/shell.ts` carries the argument; the call has to sit above every hook and every
   case in the file, which is what `make docs-audit`'s `spec seal` row checks. */
sealEveryTest()

test('the markdown is reachable from the screen where prices are decided', async ({ page }) => {
  await open(page)

  /* ON `#/pricing` (D105), AND STILL NOT ON A ROUTE OF ITS OWN. D100 put it on `#/runs` beside
     the store-wide reconcile because both read the same My Pricing export — kinship of
     IMPLEMENTATION. The owner's objection was that it is not kinship of work: `#/runs` is the
     pipeline over a box just photographed, and a markdown decides a PRICE over inventory
     already listed. */
  await expect(sheet(page)).toContainText('My Pricing')

  /* AND THE RECONCILE DID NOT COME WITH IT — an absence, and the half of D105 that is easy to
     lose. It writes `live` onto the store's own record, which is a fact about inventory and is
     settled where the other inventory facts are. Two sheets moving together would have been
     the co-location argument surviving the objection to it. */
  await expect(page.getByRole('button', { name: 'Reconcile the whole store' })).toHaveCount(0)

  /* THE DOOR IS THIS SCREEN'S HEADER, in a store with no joined runs — the empty-state branch,
     which is where an operator who has photographed nothing will look for it. */
  await page.keyboard.press('Escape')
  await expect(opener(page)).toBeVisible()
})

/* THE SHEET IS AN OPEN SURFACE, AND THIS SCREEN'S UNMODIFIED KEYS ENUMERATE THOSE BY NAME.
 *
 * `R` reloads and held-`T` peeks a price history, and neither yielded to a surface that did not
 * exist when they were written. The harmful one is `R`: typed into the sheet's "Cut, percent"
 * field it would have discarded an in-flight survey out from under the operator. */
test('the host screen’s bare keys yield to the sheet', async ({ page }) => {
  const wire = await open(page)
  await pickExport(page)
  await expect.poll(() => wire.length).toBe(1)

  /* THE HOST'S OWN READ, ONCE, ON MOUNT. Anything after this is the reload firing. */
  const before = HOST_READS.length
  expect(before).toBeGreaterThan(0)

  await page.keyboard.press('r')
  await page.waitForTimeout(600)

  await expect(sheet(page)).toBeVisible()
  /* NO RELOAD. `R` would call `load()`, which re-reads the worklist and the corpus and would
     throw away the survey this sheet is holding — the operator's export is bytes the SCREEN
     holds, so a reload behind the scrim loses the thing they just waited for. */
  expect(HOST_READS.length).toBe(before)
})

test('the sheet is not open until it is asked for, and Escape puts it away', async ({ page }) => {
  await stub(page)

  /* CLOSED IS AN ABSENCE, not a thing drawn off-screen: the sheet is `hidden`, so it is out of
     the accessibility tree and nothing in it can be reached by a keyboard or read out. */
  await expect(sheet(page)).toHaveCount(0)

  await opener(page).click()
  await expect(sheet(page)).toBeVisible()

  await page.keyboard.press('Escape')
  await expect(sheet(page)).toHaveCount(0)
})

test('focus lands in the sheet and Tab keeps it there', async ({ page }) => {
  await open(page)

  /* THE THREE THINGS A MODAL OWES THE KEYBOARD (`runsOverlay.ts`): focus lands inside on
     open, Tab and Shift-Tab stay inside, and it goes back to the opener on close. Asserted
     because the sheet is portalled to <body> — in the DOM it is a SIBLING of the page, so
     nothing about its position keeps a Tab from walking straight into the nav behind it. */
  const inside = () => page.evaluate(() => document.activeElement?.closest('.markdown') !== null)
  expect(await inside()).toBe(true)
  for (let i = 0; i < 12; i += 1) await page.keyboard.press('Tab')
  expect(await inside()).toBe(true)

  await page.keyboard.press('Escape')
  await expect(opener(page)).toBeFocused()
})

test('the sheet states the two things the operator must not get wrong', async ({ page }) => {
  await open(page)

  /* THE DELETION ANSWER, IN THE PRODUCT AND NOT ONLY IN A SPEC. Measured on the owner's own
     store: one import file uploaded twice left nine SKUs at exactly twice what was pushed.
     Nothing on this path can do that, and the screen is where a person learns it.
     THE COPY WAS CUT 2026-09-13, on the owner's complaint about over-explaining: the
     `Add to Quantity`-is-0 mechanism sentence is gone from the sheet's own words (it is still
     true and still in `docs/specs/stale-listings.md` §2), so this only asserts the guarantee
     that remains on screen. */
  await expect(sheet(page)).toContainText('Deletes nothing')

  /* THE PROXY, WHERE IT IS ACTED ON. The store cannot say how long a listing has been live —
     `Listing` has no first-listed stamp — so what is ranked is how long the card has been
     owned. A screen that stopped saying so would be one that quietly started lying. */
  await expect(page.locator('.markdown-caveat')).toContainText('photographed')
})

test('picking the export previews, and the preview asks for no write', async ({ page }) => {
  const wire = await open(page)
  await pickExport(page)

  await expect.poll(() => wire.length).toBe(1)
  /* THE LOAD-BEARING ABSENCE. A first press that wrote would be the worklist appearing before
     anything had been read — D33's two-step gate, pointed at a proposal about money. */
  expect(wire[0]?.body.write).toBe(false)
  expect((wire[0]?.body.export as { name?: string } | undefined)?.name).toBe(
    'TCGplayer__MyPricing.csv',
  )
  await expect(consoles(page).first()).toContainText('would mark down')
})

test('the worklist control does not exist until the preview has answered', async ({ page }) => {
  await open(page)

  /* ABSENT, NOT DISABLED, which is D33's distinction: a disabled button is a thing you can see
     and intend to press, and the state before a preview is one where there is nothing yet to
     agree to. */
  await expect(worklistPress(page)).toHaveCount(0)
  await pickExport(page)
  await expect(worklistPress(page)).toBeVisible()
})

/* NO TYPED MIDDLE DOT OR BULLET REACHES THE SHEET (D218). The eyebrow, the four numbered
 * steps and the worklist step's heading are all drawn by CSS now (`.bn-dotline`'s `::after`),
 * never typed into a string. `pickExport` is what reveals step 2, the furthest this sweep's
 * sites reach without a live write. */
test('no typed middle dot or bullet reaches the markdown sheet (D218)', async ({ page }) => {
  await open(page)
  await pickExport(page)
  await expect(worklistPress(page)).toBeVisible()

  const text = await sheet(page).innerText()
  expect(text).not.toMatch(/[·•]/)
})

test('the worklist press sends the same bytes the preview read', async ({ page }) => {
  const wire = await open(page)
  await pickExport(page)
  await expect.poll(() => wire.length).toBe(1)

  await worklistPress(page).click()
  await expect.poll(() => wire.length).toBe(2)

  /* THE SAME FILE, HELD RATHER THAN RE-PICKED, which is `LiveReconcile`'s rule and matters
     more here: the numbers the operator read and the rows the worklist carries have to be
     about one export, or the preview was about something else. */
  expect(wire[1]?.body.write).toBe(true)
  expect((wire[1]?.body.export as { name?: string } | undefined)?.name).toBe(
    (wire[0]?.body.export as { name?: string } | undefined)?.name,
  )

  /* AND THE FILE IS OFFERED, because a worklist the operator cannot open is not a worklist.
     `CLAUDE.md`'s hard rule ends at the thing a human can reach. */
  await expect(page.getByRole('link', { name: 'worklist.csv' })).toBeVisible()

  /* AND SO IS THE LENS, WHICH IS THE PRESS THE OWNER ACTUALLY ASKED FOR (D103). It shipped for
     a day reachable ONLY by typing `#/pricing?markdown=<stamp>` into the address bar — every
     mechanical check green over a screen no human could open, which is `docs/GATES.md` step 7
     verbatim and the reason CLAUDE.md's hard rule is a rule rather than a check.

     THE HASH IS ASSERTED AND NOT JUST THE BUTTON, because a control that navigates to the
     wrong stamp is worse than none: it would open somebody else's survey. */
  const toLens = page.getByRole('button', { name: 'Price these on the pricing screen' })
  await expect(toLens).toBeVisible()
  await toLens.click()
  await expect.poll(() => new URL(page.url()).hash).toBe(`#/pricing?markdown=${STAMP}`)
  /* AND THE SHEET CLOSES ON THE WAY OUT. A modal left standing over the screen it just sent
     the operator to is a scrim between them and the rows they came to price. */
  await expect(sheet(page)).toHaveCount(0)
})

test('the upload step appears only after a worklist exists, and previews before it writes', async ({
  page,
}) => {
  const wire = await open(page)

  /* STEP THREE IS ABSENT UNTIL STEP TWO HAS RUN. There is nothing to apply against until a
     manifest exists, and a control offering to write the upload file before then is offering
     something the server would refuse. */
  await expect(checkPress(page)).toHaveCount(0)
  await pickExport(page)
  await worklistPress(page).click()
  await expect.poll(() => wire.length).toBe(2)

  await expect(checkPress(page)).toBeVisible()
  await expect(importPress(page)).toHaveCount(0)
  await checkPress(page).click()
  await expect.poll(() => wire.length).toBe(3)
  expect(wire[2]?.path).toContain('/apply')
  expect(wire[2]?.body.write).toBe(false)

  /* AND ONLY THEN THE PRESS THAT WRITES THE FILE THAT GOES TO TCGPLAYER. */
  await expect(importPress(page)).toBeVisible()
  await importPress(page).click()
  await expect.poll(() => wire.length).toBe(4)
  expect(wire[3]?.body.write).toBe(true)
  await expect(page.getByRole('link', { name: 'import.csv' })).toBeVisible()
})

test('an edited worklist handed back is what the apply is asked about', async ({ page }) => {
  const wire = await open(page)
  await pickExport(page)
  await worklistPress(page).click()
  await expect.poll(() => wire.length).toBe(2)

  await pickWorklist(page)
  await expect.poll(() => wire.length).toBe(3)

  /* SENDING NO `worklist` MEANS "the one you wrote"; sending one means this one. Both are
     real flows and the difference is one field, so the field is asserted rather than assumed
     — and picking it previews, exactly as picking the export does. */
  expect(wire[2]?.path).toContain('/apply')
  expect(wire[2]?.body.write).toBe(false)
  expect((wire[2]?.body.worklist as { name?: string } | undefined)?.name).toBe('worklist.csv')
})

test('the report is the command stdout, verbatim, in a block that does not wrap', async ({
  page,
}) => {
  await open(page)
  await pickExport(page)

  /* D33: every command's stdout verbatim. Summarising it here would be a second opinion about
     which of its answers mattered, taken on the operator's behalf at the moment prices move.
     The fixed-width columns are why it is a `pre`. */
  const report = consoles(page).first()
  await expect(report).toContainText('would mark down  109 SKU(s), 394 copy(ies)')
  await expect(report).toContainText('8936515')
  await expect(report).toHaveCSS('white-space', 'pre')

  /* AND IT IS ACTUALLY TALL, which is not implied by any of the three above and is the defect
     this case was written from. `.runslog` sets `overflow: hidden`, which makes its automatic
     minimum size as a flex item ZERO; inside the sheet's scrolling column it was squeezed to
     512px wide and 0px tall with every line of stdout present in the DOM. A receipt nobody can
     read is not a receipt, and every text assertion above passed against it. */
  const box = await report.boundingBox()
  expect(box?.height ?? 0).toBeGreaterThan(60)
})

/* THE HISTORY IS FETCHED WHEN THE SHEET IS OPENED, NOT WHEN THE SCREEN IS.
 *
 * This sheet is always mounted — `Runs.tsx` renders it unconditionally and hides it with
 * `hidden={!open}` — so an effect with no `open` guard fired `GET /pipeline/markdowns` on every
 * visit to `#/runs`, for a sheet most visits never open. `LiveReconcile`, the sheet this file
 * declares itself a clone of, makes no request until it is asked to.
 *
 * BOTH DIRECTIONS, because gating on `open` can be got wrong in the other one too: an effect that
 * never re-runs leaves a worklist written this session missing from the list the next opening
 * draws. */
test('the history is not fetched until the sheet is opened, and is fetched when it is', async ({
  page,
}) => {
  const gets: string[] = []
  page.on('request', (request) => {
    if (request.method() === 'GET' && /\/pipeline\/markdowns$/.test(request.url())) {
      gets.push(request.url())
    }
  })

  await stub(page)
  await expect(opener(page)).toBeVisible()
  expect(gets).toHaveLength(0)

  await opener(page).click()
  await expect(sheet(page)).toBeVisible()
  await expect.poll(() => gets.length).toBe(1)
})

/* ESCAPE HOLDS WHILE A REQUEST IS IN FLIGHT, and does not otherwise.
 *
 * Everything in this sheet survives a close — it stays mounted, so a typed field, a picked file
 * and a written stamp are all there on the next opening, and the cost of an accidental Escape is
 * a reopen. What does not survive is a request nobody can see: nothing aborts it, and its receipt
 * toasts for a sheet that is gone. So the hold is exactly that case, and the second half of this
 * asserts it is exactly that case — a sheet with the answer in hand closes as it always has. */
test('Escape leaves a sheet alone while it is mid-request, and closes it once the answer lands', async ({
  page,
}) => {
  await stub(page)

  /* Registered after `stub`, so it wins: Playwright matches the most recent route first. The
     survey hangs until this test lets it go. */
  let release = () => {}
  const held = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route(/\/pipeline\/markdowns$/, async (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    await held
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, exit_code: 0, wrote: false, console: SURVEY, stamp: null }),
    })
  })

  await opener(page).click()
  await expect(sheet(page)).toBeVisible()
  await pickExport(page)

  /* IN FLIGHT, SAID BY THE ONE CONTROL THAT CANNOT BE BUSY FOR ANOTHER REASON. This read
     `.markdown .bn-btn[disabled], .markdown [aria-busy="true"]` and took `.first()`, which is any
     disabled button in the sheet — and two of the six here disable for reasons that are NOT the
     request: the worklist press on `!survey.ok` and the import press on `!applied.ok`. A refusal
     with nothing in flight would have satisfied it. The drop zone's own input is disabled by
     `busy` alone, so it is the honest witness. */
  await expect(page.locator('.markdown .runs-drop input[type=file]')).toBeDisabled()
  await page.keyboard.press('Escape')
  await expect(sheet(page)).toBeVisible()

  release()
  await expect(worklistPress(page)).toBeVisible()

  /* Answered: it closes, which is what says the hold was the request and not the sheet. */
  await page.keyboard.press('Escape')
  await expect(sheet(page)).toHaveCount(0)
})

/* A REFUSED CHECK LEAVES THE WAY BACK TO IT.
 *
 * `apply` sets its answer whether or not the answer is `ok`, so a refusal used to move the footer
 * on to the import press — drawn DISABLED, because `!applied.ok` — with nothing beside it. The
 * only escape was re-picking the export, and that clears the stamp: it would have thrown away the
 * worklist the refused check was about. Three absences rather than three disabled buttons is this
 * footer's rule (D33), and a disabled forward button alone is the state it exists to prevent. */
test('a check that comes back refused keeps the press that runs it again', async ({ page }) => {
  await stub(page)
  await page.route(/\/pipeline\/markdowns\/[^/]+\/apply$/, async (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: false,
        exit_code: 2,
        wrote: false,
        console: 'refused: two rows name a SKU this manifest does not hold',
        stamp: STAMP,
      }),
    }),
  )

  await opener(page).click()
  await pickExport(page)
  await worklistPress(page).click()
  await checkPress(page).click()

  await expect(page.getByText('refused: two rows name a SKU this manifest does not hold')).toBeVisible()
  await expect(checkPress(page)).toBeVisible()
  await expect(importPress(page)).toHaveCount(0)
})

/* NEITHER CONSOLE MAY BE SQUEEZED FLAT, and one of the two was not covered.
 *
 * A flex item whose own `overflow` is not `visible` has an automatic minimum size of ZERO, and
 * `.runslog` sets `overflow: hidden` — so in a column that overflows it is squeezed flat with
 * every line of stdout still in the DOM, which nothing that reads text can tell. `Runs.css` had
 * `.markdown-body > *`, a DIRECT-CHILD selector: the survey's console sits in a fragment and is
 * therefore a child of the body, and the apply's sits one `<div>` deeper. Measured in the check
 * state before this: the survey's was `flex: 0 0 auto` and the apply's `0 1 auto`.
 *
 * IT ASSERTS THE COMPUTED `flex-shrink` RATHER THAN A HEIGHT, because a height is only zero once
 * the column actually overflows — at this fixture's sizes both consoles render tall and a height
 * assertion would pass against the defect. */
/* AND THE SAME ON THE PRESS THAT WRITES THE FILE. `apply` sets its answer whether or not the
 * answer is `ok`, and `write: true` goes through the same call — so a refused WRITE lands in
 * exactly the state a refused check does. The check case above proves the `nextPress` condition
 * reads `applied.ok`; this one proves the condition is reached from the other press too, which is
 * the half a single case cannot show. */
test('a write that comes back refused also keeps the press that runs it again', async ({ page }) => {
  const wire = await stub(page)
  let refuse = false
  await page.route(/\/pipeline\/markdowns\/[^/]+\/apply$/, async (route) => {
    const body = route.request().postDataJSON()
    wire.push({ path: new URL(route.request().url()).pathname, body })
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: !refuse,
        exit_code: refuse ? 2 : 0,
        wrote: false,
        console: refuse ? 'refused: the manifest moved under this worklist' : APPLIED,
        stamp: STAMP,
      }),
    })
  })

  await opener(page).click()
  await pickExport(page)
  await worklistPress(page).click()
  await checkPress(page).click()
  await expect(importPress(page)).toBeVisible()

  /* The write refuses. The footer must go back to offering the check, not strand the operator on
     a disabled import press with the worklist it was about still on the server. */
  refuse = true
  await importPress(page).click()
  await expect(page.getByText('refused: the manifest moved under this worklist')).toBeVisible()
  await expect(checkPress(page)).toBeVisible()
  await expect(importPress(page)).toHaveCount(0)
})

test('both consoles refuse to shrink, not just the one that is a direct child', async ({ page }) => {
  const wire = await open(page)
  await pickExport(page)
  await worklistPress(page).click()
  await expect.poll(() => wire.length).toBe(2)
  await checkPress(page).click()
  await expect(page.getByText('What the check printed')).toBeVisible()

  const wells = await page.evaluate(() =>
    [...document.querySelectorAll('.markdown-body .runslog')].map((node) => ({
      label: node.querySelector('.runslog-label')?.textContent ?? '?',
      shrink: getComputedStyle(node).flexShrink,
    })),
  )

  expect(wells).toHaveLength(2)
  for (const well of wells) expect(well.shrink).toBe('0')
})

/* A MARKDOWN IS DURABLE STATE, AND THE SHEET'S OWN FLOW LEAVES THE MACHINE IN THE MIDDLE OF IT.
 *
 * Step 2 hands the operator a CSV to edit in a spreadsheet. Nothing says that finishes today —
 * and until D103 the only way back in was to re-pick the export and survey again, which mints a
 * NEW stamp. The file they had spent an evening editing would then be judged against a manifest
 * that was not its own. The history list drew that worklist as a download, beside a sheet that
 * could not take it back. */
test('a markdown written on an earlier day can be handed back, at the step it was left at', async ({
  page,
}) => {
  HISTORY = [
    {
      stamp: '20260901-120000',
      at: '2026-09-01T12:00:00.000+00:00',
      asked: { days: 7, rule: 'undercut:10', above_market: null, limit: 40 },
      source: '/tmp/my-pricing.csv',
      skus: 12,
      files: ['manifest.json', 'report.txt', 'survey.json', 'worklist.csv'],
    },
  ]
  const wire = await open(page)
  await expect(page.locator('.markdown-history-row')).toHaveCount(1)

  /* WHAT IT ASKED FOR, so two markdowns are not two identical rows. Both fields were already on
     the wire and drawn nowhere: the operator could see THAT they had run four surveys and
     nothing about which was which. */
  await expect(page.locator('.markdown-history-asked')).toContainText('7 days')
  await expect(page.locator('.markdown-history-asked')).toContainText('10% off')
  await expect(page.locator('.markdown-history-asked')).toContainText('top 40')

  /* AND THE REPORT IS OFFERED. It has been written by every `--write` since D100 and dropped by
     this list's own filter — the one artefact that says WHY a row is in the worklist, and states
     the ownership-age substitution the whole window rests on. */
  await expect(page.getByRole('link', { name: 'report.txt' })).toBeVisible()

  await page.getByRole('button', { name: 'Hand it back' }).click()

  /* IT LANDS AT STEP 3, not at step 1. The upload control is the one for the worklist, and no
     survey console is drawn — nothing above it describes a sitting that already ended. */
  await expect(page.getByRole('button', { name: /^Check it$/ })).toBeVisible()
  await expect(consoles(page)).toHaveCount(0)

  /* AND THE PRESS GOES TO THAT STAMP. A hand-back judged against another markdown's manifest is
     the exact failure re-surveying caused, so this is the assertion the whole case exists for. */
  await page.locator('.markdown .runs-filebtn input[type=file]').setInputFiles({
    name: 'worklist.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('TCGplayer Id,TCG Marketplace Price\n8936515,1.50\n'),
  })
  await expect.poll(() => wire.filter((row) => row.path.includes('/apply')).length).toBe(1)
  expect(wire.find((row) => row.path.includes('/apply'))?.path).toContain('20260901-120000')

  HISTORY = []
})

/* A MARKDOWN THAT PREDATES THE LENS HAS NO SURVEY, and an offer that leads to a refusal is
 * worse than no offer: `GET .../table` answers `survey_not_written` for it. */
test('a markdown with no survey offers its files and not the lens', async ({ page }) => {
  HISTORY = [
    {
      stamp: '20260830-090000',
      at: '2026-08-30T09:00:00.000+00:00',
      asked: { days: 7, rule: 'undercut:10' },
      source: '/tmp/old.csv',
      skus: 3,
      files: ['manifest.json', 'report.txt', 'worklist.csv'],
    },
  ]
  await open(page)
  await expect(page.locator('.markdown-history-row')).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Price these' })).toHaveCount(0)
  /* But it can still be handed back — the manifest is what `apply` judges against, and that
     predates the lens too. */
  await expect(page.getByRole('button', { name: 'Hand it back' })).toBeVisible()
  HISTORY = []
})

/* THE CUT COMES OFF SOMETHING, AND UNTIL D103 THE SCREEN COULD ONLY SAY "the asking price".
 *
 * `--basis` was on the wire, validated by `_markdown_flags` against `reprice.BASES`, and
 * reachable by no control — a route and a wire type that no screen touches is what CLAUDE.md's
 * hard rule calls not done. `asking` stays the default for D100's reason: `TCG Marketplace
 * Price` is populated on 441 of 441 live rows of a My Pricing export and blank on 7,787 of
 * 7,802 of the wide Filtered Export. */
test('the survey says what the cut comes off, and defaults to the operator’s own price', async ({
  page,
}) => {
  const wire = await open(page)
  await pickExport(page)
  await expect.poll(() => wire.length).toBe(1)
  expect((wire[0]?.body as { basis?: string }).basis).toBe('asking')

  await page.getByLabel('Cut comes off').selectOption('market')
  await page.getByRole('button', { name: /Read it again/ }).click()
  await expect.poll(() => wire.length).toBe(2)
  expect((wire[1]?.body as { basis?: string }).basis).toBe('market')

  /* AND THE SAME BYTES, because the basis is a question about one export and re-picking the
     file would make the two answers about two reads. */
  expect((wire[1]?.body as { export?: { name?: string } }).export?.name).toBe(
    (wire[0]?.body as { export?: { name?: string } }).export?.name,
  )
})

/* AND A PAST SURVEY SAYS WHICH BASIS IT USED, or two markdowns that differ only by it are two
 * identical rows. `asking` is left silent — naming the default on every row would be noise on
 * the ordinary case. */
test('the history line names a basis only when it is not the default', async ({ page }) => {
  HISTORY = [
    {
      stamp: '20260902-100000',
      at: '2026-09-02T10:00:00.000+00:00',
      asked: { days: 7, rule: 'undercut:10', basis: 'market' },
      source: '/tmp/a.csv',
      skus: 4,
      files: ['manifest.json', 'worklist.csv'],
    },
    {
      stamp: '20260902-090000',
      at: '2026-09-02T09:00:00.000+00:00',
      asked: { days: 7, rule: 'undercut:10', basis: 'asking' },
      source: '/tmp/b.csv',
      skus: 4,
      files: ['manifest.json', 'worklist.csv'],
    },
  ]
  await open(page)
  const lines = page.locator('.markdown-history-asked')
  await expect(lines.first()).toContainText('10% off of market')
  await expect(lines.nth(1)).toContainText('10% off')
  await expect(lines.nth(1)).not.toContainText('of market')
  HISTORY = []
})

/* MATCH IS THE OTHER HALF OF THE CLI'S OWN EXCLUSIVE PAIR, and the screen mirrors the exclusion
 * rather than inventing a third state: `_markdown_flags` reads `rule` first and `percent` only
 * `elif`, so a request carrying both would silently drop one. `markup` is deliberately absent —
 * a price above the live one is `RAISED`, which refuses the WHOLE file, so a control whose every
 * use is refused is worse than no control. */
test('pricing at the basis exactly sends a rule and no percent, and hides the percent field', async ({
  page,
}) => {
  const wire = await open(page)
  await page.getByLabel('New price is').selectOption('match')
  /* THE PERCENT FIELD GOES, because it is not a number this survey has a use for. An absence
     rather than a disabled input, which is this sheet's rule throughout (D33). */
  await expect(page.getByLabel('Cut, percent')).toHaveCount(0)

  await pickExport(page)
  await expect.poll(() => wire.length).toBe(1)
  const body = wire[0]?.body as { rule?: string; percent?: string }
  expect(body.rule).toBe('match')
  expect(body.percent).toBeUndefined()

  await page.getByLabel('New price is').selectOption('percent')
  await expect(page.getByLabel('Cut, percent')).toBeVisible()
  await page.getByRole('button', { name: /Read it again/ }).click()
  await expect.poll(() => wire.length).toBe(2)
  const second = wire[1]?.body as { rule?: string; percent?: string }
  expect(second.rule).toBeUndefined()
  expect(second.percent).toBe('10')
})

/* STEP 1 USED TO HAPPEN ENTIRELY OFF THIS MACHINE (D104).
 *
 * The screen could only point at TCGplayer and say "nothing here fetches it for you yet".
 * `POST /pipeline/live-export` brings the operator's own live listings at `MyInventory: True` —
 * the opposite document from the run path's catalogue fetch, behind its own guarded constant. */
test('the live export is fetched in one press, and the survey follows it', async ({ page }) => {
  const wire = await open(page)
  await page.getByRole('button', { name: 'Fetch my live listings' }).click()

  await expect.poll(() => wire.filter((r) => r.path === '/pipeline/live-export').length).toBe(1)
  /* AND THE SURVEY FOLLOWS IN THE SAME PRESS, naming the file rather than re-uploading it. The
     fetch is not a thing the operator wants for its own sake; the survey is the answer they
     came for. */
  await expect.poll(() => wire.filter((r) => r.path === '/pipeline/markdowns').length).toBe(1)
  const survey = wire.find((r) => r.path === '/pipeline/markdowns')?.body as {
    fetched?: string
    export?: unknown
  }
  expect(survey.fetched).toBe('live-tcgplayer-20260906-120000.csv')
  /* ONE DOCUMENT AND NOT TWO. The route refuses a request carrying both, so the screen must not
     be able to build one. */
  expect(survey.export).toBeUndefined()

  await expect(page.getByText('441 listings live 1140 copies')).toBeVisible()
})

/* THE REQUEST TAKES NO SCOPE, SO THERE IS NOTHING IT COULD HAVE LEFT OUT (D104).
 *
 * `Export From Live` is a GET with two query parameters and no category, no sets, no
 * conditions. The first build of this path guessed a FILTERED request and owed a "what I could
 * not bring" caveat; the measured one does not have one to owe. An answer with no rows is
 * refused by the server rather than drawn here as an empty inventory. */
test('the fetch reports every product line and offers no caveat', async ({ page }) => {
  await open(page)
  await page.getByRole('button', { name: 'Fetch my live listings' }).click()
  await expect(page.getByText('441 listings live 1140 copies')).toBeVisible()
  await expect(page.getByText('across every product line')).toBeVisible()
})

/* A DEAD COOKIE MUST NOT BE A DEAD END. Every fetch refusal is a sentence with its own code,
 * and the drop zone below is what it leaves the operator — which is why the zone is not a
 * fallback that appears on failure but a door that was always open. */
test('a refused fetch names the reason and leaves the drop zone open', async ({ page }) => {
  LIVE_FETCH = 'refuse'
  await open(page)
  await page.getByRole('button', { name: 'Fetch my live listings' }).click()

  await expect(page.locator('.markdown .bn-notice-danger')).toContainText('session has expired')
  await expect(page.locator('.markdown .bn-notice-danger')).toContainText('tcg_session_expired')
  await expect(page.locator('.markdown .runs-drop input[type=file]')).toBeEnabled()
  LIVE_FETCH = 'ok'
})

function expectStill(
  before: Record<string, { x: number; y: number; width: number; height: number } | null>,
  during: Record<string, { x: number; y: number; width: number; height: number } | null>,
) {
  for (const key of Object.keys(before)) {
    const a = before[key]
    const b = during[key]
    expect(b, `${key} is drawn during the press`).not.toBeNull()
    for (const side of ['x', 'y', 'width', 'height'] as const) {
      expect(Math.abs((b?.[side] ?? 0) - (a?.[side] ?? 0)), `${key} ${side}`).toBeLessThanOrEqual(0.5)
    }
  }
}

/* ROUND 9, D118: THE SHEET'S SEND PRESS KEEPS ITS PLACE AND SIZE WHILE IT RUNS. It read "Send
   these prices to TCGplayer" and became "Checking TCGplayer, then sending…" under the finger.
   Measured before and during a press held open. */
for (const width of [390, 820]) {
  test(`r9: the sheet's send press keeps its place and size while it runs (${width})`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    const wire = await stub(page)
    await stubTheLens(page)
    await page.route(/\/pipeline\/markdowns\/[^/]+\/send$/, async (route) => {
      wire.push({ path: new URL(route.request().url()).pathname, body: route.request().postDataJSON() })
      await new Promise((r) => setTimeout(r, 1500))
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          published: { upload_id: 'u-1', rows: 1, accepted: 1, messages: [], published_at: '2026-09-24T12:00:00+00:00' },
          stamp: STAMP,
        }),
      })
    })
    await page.getByRole('button', { name: /^Mark down stale listings$/ }).click()
    await expect(sheet(page)).toBeVisible()
    await pickExport(page)
    await worklistPress(page).click()
    await checkPress(page).click()
    await importPress(page).click()
    const named = page.getByRole('button', { name: 'Send these prices to TCGplayer' })
    await expect(named).toBeVisible()
    /* HOVER FIRST, SO ANY SCROLL THAT BRINGS THE PRESS UNDER THE POINTER HAPPENS BEFORE THE
       MEASUREMENT: a locator's own click scrolls again, and at 390 it scrolled the sheet itself,
       which is the test moving the press rather than the screen. The press is then pressed where
       it was measured. */
    await named.hover()
    /* BY THE ELEMENT AND NOT ITS NAME: the name is what changed under the finger. */
    const press = await named.elementHandle()
    const before = { press: await press?.boundingBox() ?? null }
    const at = before.press
    await page.mouse.click((at?.x ?? 0) + (at?.width ?? 0) / 2, (at?.y ?? 0) + (at?.height ?? 0) / 2)
    await expect.poll(() => wire.filter((row) => row.path.endsWith('/send')).length).toBe(1)
    await expect.poll(async () => press?.getAttribute('data-busy')).toBe('true')
    expectStill(before, { press: await press?.boundingBox() ?? null })
  })
}
