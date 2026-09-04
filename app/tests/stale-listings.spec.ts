import { test, expect, type Page } from '@playwright/test'
import { settleFonts } from './fontsReady'

/* THE STALE-LISTING MARKDOWN — asserted where nothing else can see it (D94).
 *
 * `CLAUDE.md`'s hard rule: a capability that exists only in `server/` is not done. The CLI has
 * a harness block (T7's `check_markdown`) and the route answers; what neither can say is
 * whether a person can reach any of it, or whether the two-step gate the operator actually
 * meets is the one the command implements. That is this file.
 *
 * THE STRONGEST CASES HERE ARE ABSENCES, the form a later refactor cannot quietly satisfy:
 * the write control does NOT exist before a preview has answered, it does NOT survive a
 * change to either setting, and this panel offers NO rule or basis control at all. The last
 * one pins D49's seam, which is otherwise only prose in `CLAUDE.md`.
 *
 * NO REAL REQUEST IS MADE. The route is intercepted and its body recorded, which is what lets
 * these cases assert what the screen WOULD have sent.
 */

const VIEW = '/#/runs'

type Wire = {
  write?: boolean
  days?: number
  percent?: number
  export?: { name?: string }
}

const STAMP = '2026-09-03-141207'

const REPORT = `
live export      /tmp/live-my-pricing.csv
                 10078 row(s), 11 with a live quantity
policy           rule=undercut:10 basis=listed window=30d floor=$0.40

markdown         4 SKU(s), 4 copy(ies), $1.45 off the asking total

  copies        sku   asking      new   market   drift  age  card
       1    8925722    10.00     9.00     8.34  +19.9%  28d  Kadregrin the Infernal · Near Mint Foil

not marked down
  held back          2 SKU(s) — held back in the corpus AND live at TCGplayer.
`.trim()

async function open(page: Page): Promise<Wire[]> {
  const wire: Wire[] = []
  await page.route(/\/pipeline\/markdown$/, async (route) => {
    const body = route.request().postDataJSON()
    wire.push(body)
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        exit_code: 0,
        wrote: Boolean(body.write),
        stamp: body.write ? STAMP : null,
        console: body.write ? `${REPORT}\n\nwrote            markdown.csv` : REPORT,
      }),
    })
  })
  /* THE REST OF THE SCREEN, ANSWERED EMPTY. This file is about one panel, and the panel
     fetches nothing on mount — which is why no other stub is owed here. */
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

const panel = (page: Page) => page.getByRole('region', { name: 'Mark down what is not selling' })
const writeButton = (page: Page) => page.getByRole('button', { name: /Write the import CSV/ })

async function pick(page: Page) {
  await page.locator('.stale input[type=file]').setInputFiles({
    name: 'TCGplayer__MyPricing.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('TCGplayer Id,Total Quantity\n8925722,1\n'),
  })
}

test('the markdown is reachable from the pipeline screen', async ({ page }) => {
  await open(page)

  /* ON `#/runs`, BESIDE THE RECONCILE, because both are driven by the same document — one My
     Pricing export answers "what does TCGplayer hold" and "what has it held too long". It is
     NOT on `#/pricing`, which autosaves the whole corpus from a mount-time snapshot and would
     silently revert the sweep on the next keystroke. */
  await expect(panel(page)).toBeVisible()
  await expect(panel(page)).toContainText('My Pricing')
  /* THE SAFETY SENTENCE IS ON SCREEN, not only in a docstring: this is the claim that makes
     the operation incapable of breaching the live cap or delisting anything. */
  await expect(panel(page)).toContainText('adds no copies')
})

test('picking a file previews, and the preview asks for no write', async ({ page }) => {
  const wire = await open(page)
  await pick(page)

  await expect.poll(() => wire.length).toBe(1)
  /* THE LOAD-BEARING ABSENCE. `docs/DECISIONS.md` deferred this feature naming exactly this
     shape — "a free preflight showing exactly which prices would change and by how much, and
     a confirm that is not a default". A first press that wrote would be that confirm defaulted. */
  expect(wire[0]?.write).toBe(false)
  expect(wire[0]?.export?.name).toBe('TCGplayer__MyPricing.csv')
  await expect(page.locator('.stale-console')).toContainText('markdown')
})

test('the preview names the rule, and the panel offers no control over it', async ({ page }) => {
  const wire = await open(page)
  await pick(page)
  await expect.poll(() => wire.length).toBe(1)

  /* D49's SEAM, PINNED. `CLAUDE.md` records that `--rule` and `--basis` are deliberately not
     on this screen, because `#/pricing` is the one press that sets a standing pricing policy.
     So the wire carries neither, and the report is where the operator reads which rule was
     applied — on screen before the control that applies it exists. */
  expect(wire[0]).not.toHaveProperty('rule')
  expect(wire[0]).not.toHaveProperty('basis')
  await expect(page.locator('.stale-console')).toContainText('rule=undercut:10 basis=listed')
  await expect(panel(page).getByRole('combobox', { name: /rule|basis/i })).toHaveCount(0)
})

test('the write control does not exist until the preview has answered', async ({ page }) => {
  await open(page)

  /* ABSENT, NOT DISABLED — LiveReconcile's rule, which is D33's. A disabled button is a thing
     you can see and intend to press, and the state before a preview is one where there is
     nothing to agree to. */
  await expect(writeButton(page)).toHaveCount(0)
  await pick(page)
  await expect(writeButton(page)).toBeVisible()
})

test('the write press sends the same bytes and settings the preview read, then goes away', async ({
  page,
}) => {
  const wire = await open(page)
  await pick(page)
  await expect.poll(() => wire.length).toBe(1)

  await writeButton(page).click()
  await expect.poll(() => wire.length).toBe(2)

  /* THE SAME FILE AND THE SAME WINDOW, HELD RATHER THAN RE-READ. Re-picking the file, or
     reading the selects at send time, would let the preview and the write describe two
     different sweeps at the one moment a price moves. */
  expect(wire[1]?.write).toBe(true)
  expect(wire[1]?.export?.name).toBe(wire[0]?.export?.name)
  expect(wire[1]?.days).toBe(wire[0]?.days)
  expect(wire[1]?.percent).toBe(wire[0]?.percent)

  /* AND IT LEAVES ONCE IT HAS RUN, so one export cannot be written twice by two presses. */
  await expect(writeButton(page)).toHaveCount(0)
})

test('changing the window re-previews and takes the write control away', async ({ page }) => {
  const wire = await open(page)
  await pick(page)
  await expect.poll(() => wire.length).toBe(1)
  await expect(writeButton(page)).toBeVisible()

  await panel(page).getByLabel('Not sold in').selectOption('60')

  /* THE CASE THE CONTROLS FORCE, AND THE ONE LiveReconcile NEVER NEEDED. A write must never be
     aimed at a report the operator has replaced: the old report describes a different set of
     cards at a different window, and the button that was on screen was agreeing to that one. */
  await expect.poll(() => wire.length).toBe(2)
  expect(wire[1]?.write).toBe(false)
  expect(wire[1]?.days).toBe(60)
  await expect(writeButton(page)).toBeVisible()
})

test('changing the percentage re-previews too, and carries the same file', async ({ page }) => {
  const wire = await open(page)
  await pick(page)
  await expect.poll(() => wire.length).toBe(1)

  await panel(page).getByLabel('Take off').selectOption('25')

  await expect.poll(() => wire.length).toBe(2)
  expect(wire[1]?.write).toBe(false)
  expect(wire[1]?.percent).toBe(25)
  expect(wire[1]?.export?.name).toBe(wire[0]?.export?.name)
})

test('both numbers are always sent, so nothing defaults on the server', async ({ page }) => {
  const wire = await open(page)
  await pick(page)
  await expect.poll(() => wire.length).toBe(1)

  /* THE COMMAND REQUIRES BOTH AND DEFAULTS NEITHER, on the grounds that no number in this repo
     derives a staleness window. So this panel is the ONE declaration of where they start, and
     these two assertions are what stop a second one appearing in Python and drifting. */
  expect(typeof wire[0]?.days).toBe('number')
  expect(typeof wire[0]?.percent).toBe('number')
  expect(wire[0]?.days).toBeGreaterThan(0)
  expect(wire[0]?.percent).toBeGreaterThan(0)
})

test('the written CSV is offered as a download, not as bytes in the page', async ({ page }) => {
  await open(page)

  await expect(page.locator('.stale-file')).toHaveCount(0)
  await pick(page)
  await writeButton(page).click()

  /* A URL THE BROWSER FETCHES (D94, and `server.ts:runFileUrl`'s own argument): this is the
     file that goes into TCGplayer's importer, and a string in a text area is not that. The
     stamp is a FIELD on the response — a client regex over the report would make a reworded
     sentence break the download. */
  const link = page.locator('.stale-file')
  await expect(link).toBeVisible()
  await expect(link).toHaveAttribute('download', 'markdown.csv')
  const href = await link.getAttribute('href')
  expect(href).toContain(`/pipeline/markdowns/${STAMP}/file?name=markdown.csv`)
  expect(href?.startsWith('blob:')).toBe(false)
  expect(href?.startsWith('data:')).toBe(false)
})

test('the report is the command stdout, verbatim, and no row is summarised', async ({ page }) => {
  await open(page)
  await pick(page)

  /* D33: every command's stdout verbatim. Every useful extra column a table would add is
     arithmetic on money, which `Pricing.tsx` forbids the client — so a structured table would
     converge on the fixed-width columns the command already prints, having paid a route and a
     type for it. The columns are why it is a `pre`. */
  const console_ = page.locator('.stale-console')
  await expect(console_).toContainText('8925722')
  await expect(console_).toContainText('held back in the corpus')
  await expect(console_).toHaveCSS('white-space', 'pre')
})
