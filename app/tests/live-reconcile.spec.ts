import { test, expect, type Page } from '@playwright/test'
import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'

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
 * IT IS A SHEET NOW, NOT AN INLINE PANEL, and every case here goes through the control that
 * opens it. That is not a layout detail dressed up as behaviour: reachability from a screen IS
 * the property this file exists to assert, and a sheet nobody can open is the server-only
 * capability the hard rule refuses. The old assertions asserted their way into a panel that was
 * merely present in the DOM — which the closed sheet still is — so each is re-pointed at the
 * opened sheet rather than at markup that happens to exist.
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

/** The sheet itself. A dialog, so a screen reader is told the rest of the page is behind it. */
const panel = (page: Page) => page.getByRole('dialog', { name: 'Reconcile the whole store' })

/** The control on the Runs header that opens it — the only way in, and the reachability claim. */
const opener = (page: Page) => page.getByRole('button', { name: 'Reconcile the whole store' })

/** The press that settles. Named apart from the opener above: the opener's accessible name is
 *  "Reconcile the whole store" and this one's is "Reconcile the store", so the anchors matter. */
const settle = (page: Page) => page.getByRole('button', { name: /^Reconcile the store$/ })

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
  await opener(page).click()
  await expect(panel(page)).toBeVisible()
  return wire
}

async function pick(page: Page) {
  await page.locator('.livecheck input[type=file]').setInputFiles({
    name: 'TCGplayer__MyPricing.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from('TCGplayer Id,Total Quantity\n8608859,2\n'),
  })
}

/* NOTHING HERE MAY REACH THE CAPTURE SERVER, AND THE SHELL'S OWN READ IS NOT THIS SCREEN'S.
   `app/tests/shell.ts` carries the argument; the call has to sit above every hook and every
   case in the file, which is what `make docs-audit`'s `spec seal` row checks. */
sealEveryTest()

test('the store-wide reconcile is reachable from the pipeline screen', async ({ page }) => {
  await open(page)

  /* ON `#/runs` BECAUSE THIS SCREEN'S OWN LEDE NAMES THE FOUR COMMANDS — "identify · join ·
     emit · reconcile" — and this is the fourth in the only shape that can answer both
     directions. It is NOT on `#/inventory`, which is where a card's state changes; this
     changes no card's state (D7). */
  await expect(panel(page)).toContainText('My Pricing')
  await expect(panel(page)).toContainText('marks no card sold')
})

test('the sheet is not open until it is asked for, and Escape puts it away', async ({ page }) => {
  await page.route(/\/boxes$/, async (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"boxes":[]}' }),
  )
  await page.route(/\/pipeline\/runs$/, async (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"runs":[]}' }),
  )
  await page.goto(VIEW)
  await settleFonts(page)

  /* CLOSED IS AN ABSENCE, not a thing drawn off-screen: the sheet is `hidden`, so it is out of
     the accessibility tree and nothing in it can be reached by a keyboard or read out. Asserted
     because the markup IS in the DOM either way — every case below would pass against a sheet
     no one could open, exactly as they did before this file was re-pointed. */
  await expect(panel(page)).toHaveCount(0)

  await opener(page).click()
  await expect(panel(page)).toBeVisible()

  /* Escape is the way out of any modal, and this one settles the ledger — leaving with the
     keyboard must not need a press aimed at a button. */
  await page.keyboard.press('Escape')
  await expect(panel(page)).toHaveCount(0)
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
  await expect(settle(page)).toHaveCount(0)
  await pick(page)
  await expect(settle(page)).toBeVisible()
})

test('the settle press sends the same bytes the preview read, and then goes away', async ({
  page,
}) => {
  const wire = await open(page)
  await pick(page)
  await expect.poll(() => wire.length).toBe(1)

  await settle(page).click()
  await expect.poll(() => wire.length).toBe(2)

  /* THE SAME FILE, HELD RATHER THAN RE-PICKED. Re-reading it for the write would let the
     preview and the settlement describe two different exports — the straddle
     `do_pipeline_pricing` argues about one level down, at the moment the ledger changes. */
  expect(wire[1]?.body.write).toBe(true)
  expect(wire[1]?.body.export?.name).toBe(wire[0]?.body.export?.name)

  /* AND IT LEAVES ONCE IT HAS RUN, so a second press cannot settle the same export twice
     against a ledger the first press already moved. */
  await expect(settle(page)).toHaveCount(0)
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

/* THE LOG WELL'S FOLD TOGGLE IS A THUMB TARGET, AND IT WAS 28px EVERYWHERE BUT ONE SHEET.
 *
 * `Runs.css` lifted it to 36px in a phone block near the top of the file and set its 28px base
 * height further down at the SAME specificity — so the base won inside the media query too, and
 * the lift was dead from the day it was written. The only rule that ever took effect was a
 * `.markdown`-scoped 40px copy, which reached the markdown sheet and nothing else: not this sheet,
 * not the identify composer, not the run panel. `CLAUDE.md`'s floor is 40px on a coarse pointer.
 *
 * THIS SHEET IS THE ASSERTION BECAUSE IT IS NOT THAT SHEET. A case inside `.markdown` would have
 * passed against the defect for as long as the scoped copy existed, which is exactly how the
 * defect survived — the one place anybody looked was the one place it did not apply. */
test('the log well fold toggle is a thumb target on a phone, outside the markdown sheet too', async ({
  page,
}) => {
  await open(page)
  await pick(page)
  await expect(page.locator('.livecheck .runslog')).toBeVisible()

  await page.setViewportSize({ width: 390, height: 844 })
  await settleFonts(page)

  const seen = await page.evaluate(() => {
    const well = document.querySelector('.livecheck .runslog') as HTMLElement
    const toggle = well.querySelector('.runslog-toggle') as HTMLElement
    return {
      insideMarkdownSheet: well.closest('.markdown') !== null,
      toggle: +toggle.getBoundingClientRect().height.toFixed(1),
    }
  })

  /* If this ever reads true the case has stopped testing what it says it does. */
  expect(seen.insideMarkdownSheet).toBe(false)
  expect(seen.toggle).toBeGreaterThanOrEqual(40)
})

/* ESCAPE HOLDS HERE TOO, AND THIS SHEET IS WHERE IT WAS WIRED AND NOT TESTED.
 *
 * `LiveReconcile.tsx` passes `busy` as `useOverlayFocus`'s `hold`, the same as the markdown sheet,
 * and until now the only case for it lived in `markdown.spec.ts` — so this sheet's half of the
 * contract was asserted by a file that does not render it. The two sheets share one hook and
 * nothing else; a case in one is not coverage of the other.
 *
 * WHAT THE HOLD IS FOR, restated because it is narrow: this sheet stays mounted, so a picked file
 * and a preview survive a close and reopen intact. What does not survive is a request nobody can
 * see — nothing aborts it, and its receipt toasts for a sheet that is gone. Everything else closes
 * on Escape as it always has, which the second half asserts. */
test('Escape leaves this sheet alone while it is mid-request, and closes it once the answer lands', async ({
  page,
}) => {
  const wire: Wire[] = []
  let release = () => {}
  const held = new Promise<void>((resolve) => {
    release = resolve
  })

  await open(page)

  /* Registered AFTER `open`, which installs its own route for this path: Playwright matches the
     most recently registered first, so this one has to come second to win. Getting that backwards
     is silent — `open`'s route answers instantly, the sheet never enters the state under test, and
     the only thing that catches it is the `wire` length at the end of this case. */
  await page.route(/\/pipeline\/reconcile-live$/, async (route) => {
    wire.push({ path: '/pipeline/reconcile-live', body: route.request().postDataJSON() })
    await held
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, exit_code: 0, wrote: false, console: REPORT }),
    })
  })

  await pick(page)

  /* In flight, said by the drop zone's own input — disabled by `busy` and nothing else, unlike
     the footer's presses. */
  await expect(page.locator('.livecheck input[type=file]')).toBeDisabled()
  await page.keyboard.press('Escape')
  await expect(panel(page)).toBeVisible()

  release()
  await expect(settle(page)).toBeVisible()

  /* Answered: it closes, which is what says the hold was the request and not the sheet. */
  await page.keyboard.press('Escape')
  await expect(panel(page)).toHaveCount(0)
  expect(wire).toHaveLength(1)
})

