import { test, expect, type Page } from '@playwright/test'
import { settleFonts } from './fontsReady'

/* THE STALE-LISTING MARKDOWN, ASSERTED WHERE NOTHING ELSE CAN SEE IT (D100).
 *
 * `CLAUDE.md`'s hard rule: a capability that exists only in `server/` is not done. The CLI has
 * a harness block (T7's `check_markdown`) and the routes answer; what neither can say is
 * whether a person can reach any of it, or whether the three presses arrive in the order the
 * design says they do. That is this file.
 *
 * THE STRONGEST CASES HERE ARE ABSENCES, which is the form a later refactor cannot quietly
 * satisfy: neither write control EXISTS before the read before it has answered, and both
 * previews carry `write: false`. That is D33's two-step gate applied twice, to the press that
 * writes a worklist and to the press that writes the file the operator uploads.
 *
 * AND ONE PRESENCE THAT IS LOAD-BEARING: the screen says, in its own words, that nothing is
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

async function open(page: Page): Promise<Wire[]> {
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
  await page.route(/\/boxes$/, async (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"boxes":[]}' }),
  )
  await page.goto(VIEW)
  await settleFonts(page)
  return wire
}

async function pickExport(page: Page) {
  await page.locator('.markdown-step input[type=file]').first().setInputFiles({
    name: 'TCGplayer__MyPricing.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('TCGplayer Id,Total Quantity\n8936515,4\n'),
  })
}

test('the markdown is reachable from the pipeline screen', async ({ page }) => {
  await open(page)

  /* ON `#/runs` AND NOT ON A ROUTE OF ITS OWN (D100). It wanted one on D49's precedent — a
     worklist the operator sits in is what earned `#/pricing` a route — and the nav has no room
     for an eleventh link at 1,440. `App.tsx`'s ROUTES table carries the measurement. It sits
     under the store-wide reconcile, whose file it also reads. */
  await expect(page.getByRole('region', { name: 'Mark down what is not selling' })).toBeVisible()
  await expect(page.locator('main.no-such-view')).toHaveCount(0)
})

test('the screen states the two things the operator must not get wrong', async ({ page }) => {
  await open(page)

  /* THE DELETION ANSWER, IN THE PRODUCT AND NOT ONLY IN A SPEC. Measured on the owner's own
     store: one import file uploaded twice left nine SKUs at exactly twice what was pushed.
     Nothing on this path can do that, and the screen is where a person learns it. */
  await expect(page.locator('.markdown')).toContainText('Nothing is ever deleted at TCGplayer')
  await expect(page.locator('.markdown')).toContainText('Add to Quantity')

  /* THE PROXY, WHERE IT IS ACTED ON. The store cannot say how long a listing has been live —
     `Listing` has no first-listed stamp — so what is ranked is how long the card has been
     owned. A screen that stopped saying so would be one that quietly started lying. */
  await expect(page.locator('.markdown-caveat')).toContainText('owned')
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
  await expect(page.locator('.markdown-console')).toContainText('would mark down')
})

test('the worklist control does not exist until the preview has answered', async ({ page }) => {
  await open(page)

  /* ABSENT, NOT DISABLED, which is D33's distinction: a disabled button is a thing you can see
     and intend to press, and the state before a preview is one where there is nothing yet to
     agree to. */
  await expect(page.getByRole('button', { name: /Write the worklist/ })).toHaveCount(0)
  await pickExport(page)
  await expect(page.getByRole('button', { name: /Write the worklist/ })).toBeVisible()
})

test('the worklist press sends the same bytes the preview read', async ({ page }) => {
  const wire = await open(page)
  await pickExport(page)
  await expect.poll(() => wire.length).toBe(1)

  await page.getByRole('button', { name: /Write the worklist/ }).click()
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
  await expect(page.getByRole('button', { name: /Check it/ })).toHaveCount(0)
  await pickExport(page)
  await page.getByRole('button', { name: /Write the worklist/ }).click()
  await expect.poll(() => wire.length).toBe(2)

  await expect(page.getByRole('button', { name: /Check it/ })).toBeVisible()
  await page.getByRole('button', { name: /Check it/ }).click()
  await expect.poll(() => wire.length).toBe(3)
  expect(wire[2]?.path).toBe('/apply')
  expect(wire[2]?.body.write).toBe(false)

  /* AND ONLY THEN THE PRESS THAT WRITES THE FILE THAT GOES TO TCGPLAYER. */
  await expect(page.getByRole('button', { name: /Write the import CSV/ })).toBeVisible()
  await page.getByRole('button', { name: /Write the import CSV/ }).click()
  await expect.poll(() => wire.length).toBe(4)
  expect(wire[3]?.body.write).toBe(true)
  await expect(page.getByRole('link', { name: 'import.csv' })).toBeVisible()
})

test('the report is the command stdout, verbatim, in a block that does not wrap', async ({
  page,
}) => {
  await open(page)
  await pickExport(page)

  /* D33: every command's stdout verbatim. Summarising it here would be a second opinion about
     which of its answers mattered, taken on the operator's behalf at the moment prices move.
     The fixed-width columns are why it is a `pre`. */
  const report = page.locator('.markdown-console')
  await expect(report).toContainText('would mark down  109 SKU(s), 394 copy(ies)')
  await expect(report).toContainText('8936515')
  await expect(report).toHaveCSS('white-space', 'pre')
})
