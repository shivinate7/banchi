import { test, expect, type Page } from '@playwright/test'
import { settleFonts } from './fontsReady'

/* THE FOURTH COMMAND, OVER THE WHOLE STORE — asserted where nothing else can see it (D87).
 *
 * `CLAUDE.md`'s hard rule: a capability that exists only in `server/` is not done. The CLI has
 * a harness block (T7's `check_live_reconcile`) and the route answers; what neither can say is
 * whether a person can reach any of it. That is this file.
 *
 * THE STRONGEST CASES HERE ARE ABSENCES, which is the form a later refactor cannot quietly
 * satisfy: the settle control does NOT exist before a preview has answered, and the preview
 * request carries `write: false`. Both are D33's two-step gate applied to the press that
 * settles the ledger rather than the one that spends.
 *
 * NO REAL REQUEST IS MADE. The route is intercepted and its body recorded, which is what lets
 * these cases assert what the screen WOULD have sent.
 */

const VIEW = '/#/runs'

type Wire = { path: string; body: { write?: boolean; export?: { name?: string } } }

const REPORT = `
live export      /tmp/live.csv
ledger           443 SKU(s) with a listing record

agreed           400 SKU(s) — every pushed copy is live or marked sold

unexplained      55 copy(ies) across 32 SKU(s)
  copies        sku push live sold hand  card
       3    9027215    3    0    0    3  Boots of Swiftness
`.trim()

async function open(page: Page): Promise<Wire[]> {
  const wire: Wire[] = []
  await page.route(/\/pipeline\/reconcile-live$/, async (route) => {
    const body = route.request().postDataJSON()
    wire.push({ path: '/pipeline/reconcile-live', body })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        exit_code: 0,
        wrote: Boolean(body.write),
        console: body.write ? `${REPORT}\n\nsettled          393 listing(s)` : REPORT,
      }),
    })
  })
  /* THE REST OF THE SCREEN, ANSWERED EMPTY. This file is about one panel; a box list is what
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

const panel = (page: Page) => page.getByRole('region', { name: 'Reconcile the whole store' })

async function pick(page: Page) {
  await page.locator('.livecheck input[type=file]').setInputFiles({
    name: 'TCGplayer__MyPricing.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('TCGplayer Id,Total Quantity\n8608859,2\n'),
  })
}

test('the store-wide reconcile is reachable from the pipeline screen', async ({ page }) => {
  await open(page)

  /* ON `#/runs` BECAUSE THIS SCREEN'S OWN LEDE NAMES THE FOUR COMMANDS — "identify · join ·
     emit · reconcile" — and this is the fourth in the only shape that can answer both
     directions. It is NOT on `#/inventory`, which is where a card's state changes; this
     changes no card's state (D7). */
  await expect(panel(page)).toBeVisible()
  await expect(panel(page)).toContainText('My Pricing')
  await expect(panel(page)).toContainText('marks no card sold')
})

test('picking a file previews, and the preview asks for no write', async ({ page }) => {
  const wire = await open(page)
  await pick(page)

  await expect.poll(() => wire.length).toBe(1)
  /* THE LOAD-BEARING ABSENCE. A first press that wrote would be the settlement happening
     before anything was read — D33's two-step gate, pointed at the ledger. */
  expect(wire[0]?.body.write).toBe(false)
  expect(wire[0]?.body.export?.name).toBe('TCGplayer__MyPricing.csv')
  await expect(page.locator('.livecheck-console')).toContainText('unexplained')
})

test('the settle control does not exist until the preview has answered', async ({ page }) => {
  await open(page)

  /* ABSENT, NOT DISABLED. D33 spends a paragraph on the difference for the control that
     spends: a disabled button is a thing you can see and intend to press, and the state
     before a preview is one where there is nothing to agree to. */
  await expect(page.getByRole('button', { name: /Settle the ledger/ })).toHaveCount(0)
  await pick(page)
  await expect(page.getByRole('button', { name: /Settle the ledger/ })).toBeVisible()
})

test('the settle press sends the same bytes the preview read, and then goes away', async ({
  page,
}) => {
  const wire = await open(page)
  await pick(page)
  await expect.poll(() => wire.length).toBe(1)

  await page.getByRole('button', { name: /Settle the ledger/ }).click()
  await expect.poll(() => wire.length).toBe(2)

  /* THE SAME FILE, HELD RATHER THAN RE-PICKED. Re-reading it for the write would let the
     preview and the settlement describe two different exports — the straddle
     `do_pipeline_pricing` argues about one level down, at the moment the ledger changes. */
  expect(wire[1]?.body.write).toBe(true)
  expect(wire[1]?.body.export?.name).toBe(wire[0]?.body.export?.name)

  /* AND IT LEAVES ONCE IT HAS RUN, so a second press cannot settle the same export twice
     against a ledger the first press already moved. */
  await expect(page.getByRole('button', { name: /Settle the ledger/ })).toHaveCount(0)
  await expect(page.locator('.livecheck-console')).toContainText('settled')
})

test('the report is the command stdout, verbatim, and no row is summarised', async ({ page }) => {
  await open(page)
  await pick(page)

  /* D33: every command's stdout verbatim. Summarising it here would be a second opinion about
     which of the four answers mattered, taken on the operator's behalf at the one moment the
     ledger changes. The fixed-width columns are why it is a `pre`. */
  const console_ = page.locator('.livecheck-console')
  await expect(console_).toContainText('agreed           400 SKU(s)')
  await expect(console_).toContainText('9027215')
  await expect(console_).toHaveCSS('white-space', 'pre')
})
