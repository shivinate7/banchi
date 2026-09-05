import { test, expect, type Page } from '@playwright/test'
import { settleFonts } from './fontsReady'

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

const VIEW = '/#/runs'
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
const consoles = (page: Page) => page.locator('.runs-md-console')

async function stub(page: Page): Promise<Wire[]> {
  const wire: Wire[] = []
  await page.route(/\/pipeline\/markdowns$/, async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ markdowns: [] }),
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
  await page.route(/\/pipeline\/markdowns\/[^/]+\/apply$/, async (route) => {
    const body = route.request().postDataJSON()
    wire.push({ path: '/apply', body })
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
  /* THE REST OF THE SCREEN, ANSWERED EMPTY. This file is about one sheet; a box list is what
     the run picker draws and neither reaches nor is reached by it. */
  await page.route(/\/boxes$/, async (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"boxes":[]}' }),
  )
  await page.route(/\/pipeline\/runs$/, async (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"runs":[]}' }),
  )
  await page.goto(VIEW)
  await settleFonts(page)
  return wire
}

async function open(page: Page): Promise<Wire[]> {
  const wire = await stub(page)
  await opener(page).click()
  await expect(sheet(page)).toBeVisible()
  return wire
}

async function pickExport(page: Page) {
  await page.locator('.runs-md .runs-drop input[type=file]').setInputFiles({
    name: 'TCGplayer__MyPricing.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('TCGplayer Id,Total Quantity\n8936515,4\n'),
  })
}

async function pickWorklist(page: Page) {
  await page.locator('.runs-md .runs-filebtn input[type=file]').setInputFiles({
    name: 'worklist.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('TCGplayer Id,TCG Marketplace Price\n8936515,0.44\n'),
  })
}

test('the markdown is reachable from the pipeline screen', async ({ page }) => {
  await open(page)

  /* ON `#/runs` AND NOT ON A ROUTE OF ITS OWN (D100) — a judgement now rather than the nav
     measurement it started as, and `App.tsx`'s ROUTES table carries this session's own
     re-measurement of what a tenth link would cost the sidebar. It is a sibling of the
     store-wide reconcile because both read the same file. */
  await expect(sheet(page)).toContainText('My Pricing')
  await expect(page.getByRole('button', { name: 'Reconcile the whole store' })).toBeVisible()
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
  const inside = () => page.evaluate(() => document.activeElement?.closest('.runs-md') !== null)
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
     Nothing on this path can do that, and the screen is where a person learns it. */
  await expect(sheet(page)).toContainText('Nothing is ever deleted at TCGplayer')
  await expect(sheet(page)).toContainText('Add to Quantity')

  /* THE PROXY, WHERE IT IS ACTED ON. The store cannot say how long a listing has been live —
     `Listing` has no first-listed stamp — so what is ranked is how long the card has been
     owned. A screen that stopped saying so would be one that quietly started lying. */
  await expect(page.locator('.runs-md-caveat')).toContainText('owned')
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
  expect(wire[2]?.path).toBe('/apply')
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
  expect(wire[2]?.path).toBe('/apply')
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
     `.runs-md .bn-btn[disabled], .runs-md [aria-busy="true"]` and took `.first()`, which is any
     disabled button in the sheet — and two of the six here disable for reasons that are NOT the
     request: the worklist press on `!survey.ok` and the import press on `!applied.ok`. A refusal
     with nothing in flight would have satisfied it. The drop zone's own input is disabled by
     `busy` alone, so it is the honest witness. */
  await expect(page.locator('.runs-md .runs-drop input[type=file]')).toBeDisabled()
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
 * `.runs-md-body > *`, a DIRECT-CHILD selector: the survey's console sits in a fragment and is
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
    wire.push({ path: '/apply', body })
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
    [...document.querySelectorAll('.runs-md-body .runslog')].map((node) => ({
      label: node.querySelector('.runslog-label')?.textContent ?? '?',
      shrink: getComputedStyle(node).flexShrink,
    })),
  )

  expect(wells).toHaveLength(2)
  for (const well of wells) expect(well.shrink).toBe('0')
})

