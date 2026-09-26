import { test, expect, type Page } from '@playwright/test'
import { sealEveryTest } from './shell'
import { batchOf, order as orderRow, payloadOf, shippingRow as row } from './routeFixtures'

import type { OrderRow, ShippingBatch } from '../src/types'

/* NOTHING HERE MAY REACH THE CAPTURE SERVER, AND THE SHELL'S OWN READ IS NOT THIS SCREEN'S.
   `app/tests/shell.ts` carries the argument; the call has to sit above every hook and every
   case in the file, which is what `make docs-audit`'s `spec seal` row checks. */
sealEveryTest()

/* THE SHIPPING SCREEN, ASSERTED WHERE NOTHING ELSE CAN SEE IT.
 *
 * `make design-check` ONLY, AND NOT A HARNESS TEST — it must never become one. `docs/GATES.md`'s
 * harness contract is seven Python tests run at the Stop hook, and this starts a browser.
 *
 * WHY IT EXISTS AT ALL. `CLAUDE.md`'s hard rule is "A ROUTE IS NOT A FEATURE", and step 7's own
 * record is 7b shipping with three screens missing from `App.tsx`'s ROUTES table while harness,
 * lint, typecheck and docs-audit were ALL green. Nothing on the path that decides whether a
 * commit proceeds can tell whether a human can open a screen. This file is that check for
 * `#/shipping`, which is why its first case is the dullest one in it: does the hash resolve, and
 * does the nav offer the chord.
 *
 * THE STRONGEST CASES HERE ARE ABSENCES, and an absence is the form a later refactor cannot
 * quietly satisfy:
 *
 *   NO FIGURE IS EVER RENDERED AS ZERO. `pipeline/shipping.py` abstains precisely because a
 *   figure is missing — it refuses to let an absent weight mean a light one — and a screen that
 *   printed `0.0000 oz/item` under "No usable weight on the row" would undo the whole abstention
 *   in the one place the operator looks. Case 4 is that rule.
 *
 *   THE UNJUDGED ROW DRAWS NEITHER QUALITY WORD. `certain` is a two-way split on a JUDGED row —
 *   a published price against a published threshold, or an inference off a weight ratio — and on
 *   an abstention the same word would be a third meaning wearing one label. Case 3 asserts the
 *   absence beside the two presences.
 *
 *   THE FILTER REMOVES AND NEVER REORDERS. Case 5 records the rendered order, hides the middle
 *   lane, and asserts the survivors keep their original relative order — which is the property a
 *   `sort` slipped in later would break and a count-based assertion would not notice.
 *
 *   THE DOWNLOAD IS NOT CLICKED. Case 6 asserts the `href` and the `download` attribute and
 *   stops there. Pressing it starts a real download against a batch no server is holding.
 *
 * NO REAL REQUEST IS EVER MADE. Every route is intercepted, and the POST that hands the export
 * over is RECORDED rather than performed — which is what lets case 9 assert the exact shape the
 * screen would have sent.
 */

const VIEW_ROUTE = '/#/shipping'
const VIEW = 'main.shipping'

/** The batch id every stub answers with, and the one case 6 expects to find inside the
 *  download's `href`. */
const BATCH = 'b-2026-08-30-01'

/** A CSV body with no meaning whatsoever: the file never reaches a parser, because the route
 *  that would parse it is stubbed. What it has to be is a real `File` the browser can read as
 *  text, so `app/src/csvUpload.ts:readUpload` resolves and the screen gets as far as posting. */
const CSV = 'Order #,FirstName\nA2FFC195-0000F4-006AC,Ada\n'

type Wire = { method: string; path: string; body: unknown }

/* `row` and `batchOf` moved to `./routeFixtures` (D194's copy-ratchet fixtures) so
 * `copy-budget.spec.ts` can build the same `#/shipping` shapes without a second, drifting
 * copy. `routeFixtures.ts:batchOf`'s default `batch` id is this file's own `BATCH` constant,
 * kept in step deliberately — see that file's comment. */

/**
 * Land on the screen with every route it can reach intercepted, and return the log of what it
 * sent. Nothing is fetched on mount — that is the screen's own rule — so this leaves it on the
 * pre-read empty state and the cases drive it from there.
 *
 * THE ROUTES ARE THE ONES THE INTEGRATION PASS WIRES: `POST /shipping/batches` hands an upload
 * over and answers a batch, and `DELETE /shipping/batches/<batch>` forgets one. The download's
 * address is asserted rather than routed, in case 6, because the operator's browser is what
 * fetches it and this file never presses it.
 */
async function open(
  page: Page,
  options: {
    batch?: ShippingBatch
    refuse?: { code: string; message: string }
    /** The ledger's own orders (D63), for UX-008: a row whose order number is in here opens
     *  it via `OrderLink`. Empty by default, which is what leaves a row as plain text. */
    orders?: OrderRow[]
  } = {},
): Promise<Wire[]> {
  const wire: Wire[] = []

  /* THE HUB'S TWO READS, WHICH ARE NOT THIS SCREEN'S AND WERE THEREFORE MISSED. `#/shipping`
     is the Ship stage of `OrdersHub` — `Shipping.tsx` does nothing but point the route at it
     with `stage="ship"` — so the hub's own `getOrders` and `getInventory` fire on mount here
     as surely as they do on `#/orders`. Nothing in this file asked for them and nothing
     stubbed them, so both went to the capture port until `sealEveryTest` named them.

     EMPTY IS THE HONEST ANSWER RATHER THAN A CONVENIENCE. Every case in this file works from
     an uploaded export; D63's ledger is `orders.spec.ts`'s subject. What matters is that the
     Ship stage draws its lanes out of the file and not out of a store, which these two make
     true by holding nothing. */
  await page.route(/\/orders$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        options.orders === undefined
          ? { summary: 'no orders', orders: [], resolution: { orders: [], counts: {} } }
          : payloadOf(options.orders, []),
      ),
    })
  })

  await page.route(/\/inventory$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 2, cards: {}, boxes: {}, listings: {} }),
    })
  })

  await page.route(/\/shipping\/batches$/, async (route) => {
    wire.push({
      method: route.request().method(),
      path: new URL(route.request().url()).pathname,
      body: route.request().postDataJSON(),
    })
    if (options.refuse !== undefined) {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        /* THE ENVELOPE THE CAPTURE SERVER ACTUALLY SENDS — `{error: {code, message}}`, which
           `app/src/server.ts:errorEnvelope` is the only reader of. A flatter stub falls through
           to the invented `http_error` message, so the panel would draw "400 Bad Request from
           …" and this case would pass while asserting nothing about the sentence the server
           wrote. */
        body: JSON.stringify({ error: options.refuse }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(options.batch ?? batchOf([row()])),
    })
  })

  await page.route(/\/shipping\/batches\/[^/]+$/, async (route) => {
    wire.push({
      method: route.request().method(),
      path: new URL(route.request().url()).pathname,
      body: null,
    })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ batch: BATCH, forgotten: true }),
    })
  })

  await page.goto(VIEW_ROUTE)
  await expect(page.locator(VIEW)).toBeVisible()
  return wire
}

/** Hand the screen a file, the way the operator does: a real `File` on the real input, so
 *  `readUpload` runs and the screen posts what it read. `Buffer` is `capture-undo.spec.ts`'s
 *  precedent in this suite — Playwright's `setInputFiles` takes one and nothing else. */
async function readExport(page: Page): Promise<void> {
  /* BY ITS ACCESSIBLE NAME, NOT BY A CLASS. The stage was rebuilt around a drop zone whose
     input is visually hidden inside its label, so the old `.shipping-plain input` is gone; what
     has not changed is that the control a person uses to hand this screen an export is a file
     input they can name. A selector on the name survives the next redraw too. */
  await page.getByLabel('Read an export').setInputFiles({
    name: 'TCGplayer_ShippingExport_20260830.csv',
    mimeType: 'text/csv',
    buffer: Buffer.from(CSV),
  })
}

/* -------------------------------------------------------------------------------------- 1 */

test('the route resolves, and the nav offers it under its own chord', async ({ page }) => {
  await open(page)

  /* THE DULLEST ASSERTION IN THE FILE AND THE ONE THAT PAYS FOR IT. A screen absent from
     `App.tsx`'s ROUTES table renders the unresolved-hash page instead, which nothing else in
     this repo can tell — harness, lint, typecheck and docs-audit all stay green over it. */
  await expect(page.locator(VIEW)).toBeVisible()

  /* The chord is still `,S`, and it is still printed on the nav link — the keycap's own class
     went with the rebuild, so this reads the `kbd` inside the link for this route. */
  await expect(page.locator('a.app-nav-link[href="#/shipping"] kbd')).toHaveText(',S')
})

/* -------------------------------------------------------------------------------------- 2 */

test('before any file is read it says where the file comes from, and offers nothing else', async ({
  page,
}) => {
  await open(page)

  await expect(page.locator('.shipping-empty')).toContainText('Orders → Export Shipping')

  /* NOTHING IS DRAWN FROM A BATCH THERE IS NOT ONE OF. A chip strip of three zeroes or a dead
     download anchor would both be state the server does not hold — this screen makes no read on
     mount, and these two absences are what that decision looks like on screen. */
  await expect(page.locator('a.shipping-file')).toHaveCount(0)
  await expect(page.locator('.shipping-chip')).toHaveCount(0)
})

/* -------------------------------------------------------------------------------------- 3 */

const VALUE_ORDER = 'A2FFC195-0000F4-006AC'
const WEIGHT_ORDER = 'B31A0C7D-0001A2-00311'
const UNJUDGED_ORDER = 'C99E4410-0002B8-004F0'

/** One of each kind the screen has to tell apart: a certainty, an inference, and an
 *  abstention. */
function threeKinds(): ShippingBatch {
  return batchOf([
    row({ order: VALUE_ORDER, lane: 'parcel', reason: 'value_at_threshold', certain: true }),
    row({
      order: WEIGHT_ORDER,
      lane: 'parcel',
      reason: 'non_card_signal',
      certain: false,
      value: '12.40',
      weight_per_item_oz: '2.5000',
      item_count: 1,
    }),
    row({
      order: UNJUDGED_ORDER,
      lane: 'unjudged',
      reason: 'no_weight_data',
      certain: false,
      value: '18.00',
      weight_per_item_oz: null,
      item_count: 2,
    }),
  ])
}

test('a card says its reason only where it differs from its lane, and never the machine code', async ({
  page,
}) => {
  await open(page, { batch: threeKinds() })
  await readExport(page)

  const value = page.locator('.shipping-row').filter({ hasText: VALUE_ORDER })
  const weight = page.locator('.shipping-row').filter({ hasText: WEIGHT_ORDER })
  const unjudged = page.locator('.shipping-row').filter({ hasText: UNJUDGED_ORDER })

  /* TXT-01/UX-015: `value_at_threshold` IS the Parcel lane's own rule — its chip already says
     "$50 or more" — so the sentence would repeat the header on every such card and this row
     draws none. `non_card_signal` is the ground two grounds reach one lane on (D61), so it
     keeps its own sentence. The unjudged lane names no single ground in its header, so every
     abstention still says which one it is. */
  await expect(value.locator('.shipping-says')).toHaveCount(0)
  await expect(weight.locator('.shipping-says')).toHaveText(
    'Heavier per item than cards run, so something in it is not a card.',
  )
  await expect(unjudged.locator('.shipping-says')).toHaveText(
    'No usable weight on the row, so what is in it is unknown.',
  )

  /* UX-005/TXT-02: NO CARD PRINTS ITS RAW REASON STRING ANY MORE (D196). */
  await expect(page.locator('.shipping-reason')).toHaveCount(0)

  /* UX-063/TXT-03: the word moves off the card and into the icon's tooltip and accessible
     name — the visible face is the icon alone. */
  await expect(value.locator('.shipping-quality')).not.toContainText('Certain')
  await expect(value.locator('.shipping-quality')).toHaveAttribute('aria-label', /^Certain/)
  await expect(weight.locator('.shipping-quality')).not.toContainText('Inferred')
  await expect(weight.locator('.shipping-quality')).toHaveAttribute('aria-label', /^Inferred/)
  /* The word still exists once on screen, in the legend above the lanes. */
  await expect(page.locator('.shipping-quality-legend')).toContainText('Certain')
  await expect(page.locator('.shipping-quality-legend')).toContainText('Inferred')

  /* NEITHER WORD ON THE ABSTENTION. An abstention is not a low-confidence answer, it is the
     absence of one, and either word here would be a third meaning wearing one label. */
  await expect(unjudged.locator('.shipping-quality')).toHaveCount(0)

  /* The abstention lane is still counted and still named in words of its own — the words are
     'Needs a look' now, which is the same third answer D61 argued for under a label that says
     what to do about it. */
  const chip = page.locator('.shipping-chip-unjudged')
  await expect(chip.locator('.shipping-chip-label')).toHaveText('Needs a look')
  await expect(chip.locator('.shipping-chip-count')).toHaveText('1')
})

/* -------------------------------------------------------------------------------------- 3b */

test('a weight is shown only as evidence, rounded for a person, and never the plain card constant', async ({
  page,
}) => {
  /* Both rows carry the SAME weight, so this proves the gate is the REASON and not merely
     whether a weight is present — the defect (TXT-04) is 187 identical `0.0700` figures on
     cards whose reason never needed the number at all. */
  const cardsOnly = 'A1000000-000100-00100'
  const overWeight = 'A2000000-000200-00200'
  await open(page, {
    batch: batchOf([
      row({ order: cardsOnly, lane: 'envelope', reason: 'cards_only', certain: false, value: '4.25', weight_per_item_oz: '0.0700', item_count: 1 }),
      row({ order: overWeight, lane: 'parcel', reason: 'value_at_threshold', certain: true, value: '55.00', weight_per_item_oz: '0.0700', item_count: 1 }),
      row({
        order: WEIGHT_ORDER,
        lane: 'parcel',
        reason: 'non_card_signal',
        certain: false,
        value: '12.40',
        weight_per_item_oz: '2.5000',
        item_count: 1,
      }),
    ]),
  })
  await readExport(page)

  /* `cards_only` and `value_at_threshold` are the two reasons a lane's own rule already
     explains (LANE_OWN_REASON): the weight they happen to carry is not evidence. */
  await expect(page.locator('.shipping-row').filter({ hasText: cardsOnly }).locator('.shipping-figures')).not.toContainText('oz')
  await expect(page.locator('.shipping-row').filter({ hasText: overWeight }).locator('.shipping-figures')).not.toContainText('oz')

  /* `non_card_signal` is evidence — the ratio is heavier than cards run — so the weight stays,
     rounded to two places and read as "each" rather than the module's own four decimal places
     and "/item". */
  const weight = page.locator('.shipping-row').filter({ hasText: WEIGHT_ORDER })
  await expect(weight.locator('.shipping-figures')).toContainText('2.50 oz each')
  await expect(weight.locator('.shipping-figures')).not.toContainText('2.5000')
})

/* -------------------------------------------------------------------------------------- 4 */

test('an absent figure draws nothing at all, and never a zero', async ({ page }) => {
  const noWeight = 'D4410AAB-0003C1-00922'
  const noValue = 'E7712FF0-0004D3-00A05'
  await open(page, {
    batch: batchOf([
      /* A row the value rule answered without ever consulting the proxy — `pipeline/
         shipping.py` records that this is 58 of the fixture's 97 weightless orders, and the
         worst of them is a $1750 order with one item and no weight at all. */
      row({
        order: noWeight,
        lane: 'parcel',
        reason: 'value_at_threshold',
        certain: true,
        value: '1750.00',
        weight_per_item_oz: null,
        item_count: null,
      }),
      row({
        order: noValue,
        lane: 'unjudged',
        reason: 'no_value_data',
        certain: false,
        value: null,
        weight_per_item_oz: '0.0700',
        item_count: 2,
      }),
    ]),
  })
  await readExport(page)

  /* `0.0000 oz/item` under "no usable weight" is the defect this case exists for: it undoes the
     abstention in the last inch, and it is the exact shape a float pass already manufactured
     once — the spec records "a phantom sub-0.07 row" on a distribution whose true minimum is
     exactly 0.07. */
  const weightless = await page.locator('.shipping-row').filter({ hasText: noWeight }).innerText()
  expect(weightless).not.toMatch(/oz\/item/)

  /* And `$0.00` beside "no value on the row" would claim a free order. */
  const valueless = await page.locator('.shipping-row').filter({ hasText: noValue }).innerText()
  expect(valueless).not.toContain('$')
})

/* -------------------------------------------------------------------------------------- 5 */

test('the filter removes and never reorders', async ({ page }) => {
  /* THE LANES ARE THREE COLUMNS NOW, so the export's order survives WITHIN a lane rather than
     across the whole list, and the fixture is shaped to catch a sort inside one: two envelope
     orders, separated in the export by an order of another lane, whose ids sort the OTHER way
     round. A screen that sorted its rows would hand back `[secondEnvelope, firstEnvelope]`.
     A screen that grouped them is what this branch built, and grouping is a layout choice; the
     promise being asserted is that nothing reorders and the collapse only removes. */
  const firstEnvelope = 'F3000000-0005E4-00B11'
  const middle = 'F2000000-0006F5-00C22'
  const secondEnvelope = 'F1000000-000706-00D33'
  const parcel = 'F4000000-000817-00E44'

  /* THE ABSTENTION SITS IN THE MIDDLE OF THE EXPORT ON PURPOSE. With it at either end, a screen
     that quietly sorted its list would still pass — the survivors would come back in the order
     they went in by accident. From the middle, a sort has somewhere to move them to. */
  await open(page, {
    batch: batchOf([
      row({ order: firstEnvelope, lane: 'envelope', reason: 'cards_only', certain: false, value: '4.25' }),
      row({
        order: middle,
        lane: 'unjudged',
        reason: 'sub_single_weight',
        certain: false,
        value: '9.10',
        weight_per_item_oz: '0.0350',
        item_count: 2,
      }),
      row({ order: secondEnvelope, lane: 'envelope', reason: 'cards_only', certain: false, value: '6.10' }),
      row({ order: parcel, lane: 'parcel', reason: 'value_at_threshold', certain: true }),
    ]),
  })
  await readExport(page)

  /* `toHaveText` AND NOT `expect(await ...allTextContents())`. The second form is a SNAPSHOT
     with no auto-wait: it reads once, and a list that has not rendered yet reads as `[]` and
     fails an assertion about a product that is fine. It cost this file a red run on the first
     full-suite pass. The web-first form retries until the list matches or the timeout ends,
     and asserts exactly the same thing — count, text and order. */
  const envelope = page.locator('.shipping-lane-col-envelope .shipping-order')
  await expect(envelope).toHaveText([firstEnvelope, secondEnvelope])

  const orders = page.locator('.shipping-order')
  await expect(orders).toHaveText([firstEnvelope, secondEnvelope, parcel, middle])

  const chip = page.locator('.shipping-chip-unjudged')
  await chip.click()
  await expect(chip).toHaveAttribute('aria-pressed', 'false')
  await expect(orders).toHaveText([firstEnvelope, secondEnvelope, parcel])

  await chip.click()
  await expect(chip).toHaveAttribute('aria-pressed', 'true')
  await expect(orders).toHaveText([firstEnvelope, secondEnvelope, parcel, middle])
  await expect(envelope).toHaveText([firstEnvelope, secondEnvelope])
})

/* -------------------------------------------------------------------------------------- 6 */

test('the parcel file is offered as a download, and the caption says what it does not carry', async ({
  page,
}) => {
  await open(page, { batch: threeKinds() })
  await readExport(page)

  const file = page.locator('a.shipping-file')
  const href = await file.getAttribute('href')

  /* NOT CLICKED. This asserts the address and the attribute and stops: pressing it starts a real
     download against a batch no server is holding, and the browser's own dialog is not something
     a design check should be steering. */
  expect(href ?? '').toMatch(
    new RegExp(`/shipping/batches/${BATCH}/file\\?name=pirateship-import\\.csv$`),
  )
  await expect(file).toHaveAttribute('download', 'pirateship-import.csv')

  const ship = page.locator('.shipping-ship')
  /* UX-150/TXT-05: the count is said ONCE, on the download button — the redundant "2 orders in
     the parcel lane are in this file" sentence beside it is gone. */
  await expect(ship).not.toContainText('in the parcel lane are in this file')
  await expect(ship.locator('.shipping-download-count')).toContainText('2 orders')

  /* THE CAPTION IS BEHIND A DISCLOSURE NOW, so this opens it and asserts the sentences are
     VISIBLE rather than merely present in the markup — text nobody can read is not a caption.
     The disclosure itself is the owner's ruling and is not something this file argues with. */
  await ship.locator('.shipping-caveats summary').click()
  const caveats = ship.locator('.shipping-caveats p')
  await expect(caveats).toBeVisible()

  /* THE TWO SENTENCES THAT KEEP AN OPERATOR OUT OF TROUBLE. Understated postage is charged back
     weeks later at the far end, where nobody is looking, and insurance is a per-order choice
     made inside Pirate Ship against a value only the owner can see. Both blanks are deliberate
     and the caption is the only place either is said. */
  await expect(caveats).toContainText('Package Weight is blank on every row')
  await expect(caveats).toContainText('No insurance column')
})

/* -------------------------------------------------------------------------------------- 6b */

test('the file card names an object with its verb, and says its own memory note once', async ({
  page,
}) => {
  await open(page, { batch: threeKinds() })
  await readExport(page)

  /* UX-108: a verb and its object, so a screen reader and a skim both learn what is dropped. */
  await expect(page.getByRole('button', { name: 'Forget this file' })).toBeVisible()

  /* UX-150/TXT-05: one line for the memory note, not "held in memory for about N minutes" next
     to "nothing written to disk" — the empty state already says the file is never written. */
  const meta = page.locator('.shipping-file-meta')
  await expect(meta).toContainText('kept')
  await expect(meta).toContainText('min')
  await expect(meta).not.toContainText('written to disk')
})

/* -------------------------------------------------------------------------------------- 6c */

test('the "What this file does not carry" disclosure meets the 40 px thumb floor (UX-059)', async ({
  page,
}) => {
  await open(page, { batch: threeKinds() })
  await readExport(page)

  const summary = page.locator('.shipping-caveats summary')
  const box = await summary.boundingBox()
  expect(box).not.toBeNull()
  /* THE VISIBLE FACE STAYS ITS OWN SIZE — this reads the CSS hit area, `::before`, not the
     rendered box, because D117 is about the measurement, never the ink. */
  const hit = await summary.evaluate((el) => {
    const before = getComputedStyle(el, '::before')
    return { height: parseFloat(before.height) }
  })
  expect(hit.height).toBeGreaterThanOrEqual(40)
})

/* -------------------------------------------------------------------------------------- 7 */

test('an unjudged order is not in the parcel file', async ({ page }) => {
  await open(page, { batch: threeKinds() })
  await readExport(page)

  await expect(page.locator('.shipping-ship')).toBeVisible()

  /* AN ABSTENTION IS NEVER DEFAULTED INTO A LANE, and the download block is where that would
     leak: sweeping the unjudged pile into the parcel file spends money on postage nobody asked
     for, and doing it silently is worse than doing it. */
  await expect(page.locator('.shipping-ship')).not.toContainText(UNJUDGED_ORDER)
})

/* -------------------------------------------------------------------------------------- 8 */

test('a refusal is a sentence and a code, with nothing to press beside it', async ({ page }) => {
  await open(page, {
    refuse: {
      code: 'export_not_shipping',
      message:
        'That file is a Pricing export, not a Shipping export. Orders → Export Shipping is the ' +
        'one that carries an address.',
    },
  })
  await readExport(page)

  /* The refusal is drawn with the kit's Notice now — the server's sentence in its title slot
     and the reason code in its own — so this reads those two slots inside the screen's notice.
     What is asserted is unchanged: the sentence the SERVER wrote, and the code beside it. */
  const note = page.locator('.shipping-note')
  await expect(note.locator('.bn-notice-title')).toContainText(
    'That file is a Pricing export, not a Shipping export.',
  )
  await expect(note.locator('.bn-notice-code')).toHaveText('export_not_shipping')

  /* NO ANSWER CONTROL, AND NO DISABLED RETRY. Every refusal this route sends has one remedy —
     read a different file — and the file input in the header already is that control. A second
     button that only ever repeats the same rejection teaches the operator that pressing it means
     nothing. */
  await expect(note.locator('button')).toHaveCount(0)
  await expect(note.locator('a')).toHaveCount(0)
})

/* -------------------------------------------------------------------------------------- 9 */

test('the export crosses the wire as exactly a name and a body', async ({ page }) => {
  const wire = await open(page)
  await readExport(page)
  await expect(page.locator('.shipping-list')).toBeVisible()

  const posted = wire.find((one) => one.method === 'POST')
  expect(posted).toBeDefined()

  /* `CsvUpload` AND NOTHING ELSE. A field this screen invented on the way out — a lane, a
     threshold, a weight — would be a second copy of a rule `pipeline/shipping.py` owns, and the
     drift D16 exists to catch. The route takes a file; every judgement is made on the far side
     of it. */
  expect(Object.keys(posted?.body as Record<string, unknown>).sort()).toEqual(['content', 'name'])
})

/* -------------------------------------------------------------------------------------- 10 */

/* D218: NO DOT IS TYPED. `threeKinds()` puts a real batch on screen — a shipment count, an
 * expiry note and a parcel count on the download button — which is what actually reaches
 * `.shipping-file-meta` and `.shipping-download`; an empty batch (`before any file is read`,
 * above) never draws either element at all. */
test('no dot is typed on the file card or the download button (D218)', async ({ page }) => {
  await open(page, { batch: threeKinds() })
  await readExport(page)

  await expect(page.locator('.shipping-file-meta')).toContainText('order')
  await expect(page.locator('.shipping-download')).toContainText('order')

  const typedDot = /[·•]/
  await expect(page.locator('.shipping-file-meta')).not.toContainText(typedDot)
  await expect(page.locator('.shipping-download')).not.toContainText(typedDot)
})

/* -------------------------------------------------------------------------------------- 11 */

test('an order the ledger already knows opens it; an order it does not stays plain text (UX-008)', async ({
  page,
}) => {
  await open(page, { batch: threeKinds(), orders: [orderRow({ key: `TCGplayer:${VALUE_ORDER}`, number: VALUE_ORDER })] })
  await readExport(page)

  const value = page.locator('.shipping-row').filter({ hasText: VALUE_ORDER })
  const link = value.locator('a.bn-datalink')
  await expect(link).toHaveText(VALUE_ORDER)
  await expect(link).toHaveAttribute('href', '#/orders?order=' + encodeURIComponent(`TCGplayer:${VALUE_ORDER}`))

  /* The ledger never heard of this one (D63: the export and the ledger are two maps that only
     sometimes agree), so it stays a plain string rather than a link to nothing. */
  const weight = page.locator('.shipping-row').filter({ hasText: WEIGHT_ORDER })
  await expect(weight.locator('a.bn-datalink')).toHaveCount(0)
  await expect(weight.locator('.shipping-order')).toHaveText(WEIGHT_ORDER)
})

/* -------------------------------------------------------------------------------------- 12 */

test('on a phone every lane opens folded; off a phone every lane opens shown (UX-016/D292)', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await open(page, { batch: threeKinds() })
  await readExport(page)

  /* THE LANE ORDER IS UNCHANGED (the owner's ruling keeps it) — what changes is that the
     operator sees three counts before a 37,000 px scroll, not after one. */
  for (const chip of await page.locator('.shipping-chip').all()) {
    await expect(chip).toHaveAttribute('aria-pressed', 'false')
  }
  await expect(page.locator('.shipping-row')).toHaveCount(0)
})

test('at 1440 every lane still opens shown, the desktop default', async ({ page }) => {
  await open(page, { batch: threeKinds() })
  await readExport(page)

  for (const chip of await page.locator('.shipping-chip').all()) {
    await expect(chip).toHaveAttribute('aria-pressed', 'true')
  }
  await expect(page.locator('.shipping-row')).toHaveCount(3)
})
