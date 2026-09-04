import { test, expect, type Page } from '@playwright/test'

import type { ShippingBatch, ShippingRow } from '../src/types'

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

/** One order in the shape `pipeline/shipping.py:Routing` is serialised in. Every field, not the
 *  handful a given case reads: a partial fixture does not fail partially here — a row missing
 *  `reason` indexes the reason table with `undefined` and takes the screen down, which reads
 *  exactly like an unregistered route. */
function row(over: Partial<ShippingRow> = {}): ShippingRow {
  const base: ShippingRow = {
    order: 'A2FFC195-0000F4-006AC',
    lane: 'parcel',
    reason: 'value_at_threshold',
    certain: true,
    value: '1750.00',
    weight_per_item_oz: null,
    item_count: 1,
    stamp: null,
  }
  return { ...base, ...over }
}

/** The batch, with the tallies computed from the rows rather than restated beside them — a
 *  fixture whose counts disagree with its own list is a fixture that can make a broken chip
 *  look right. `parcel_count` and `shipments` come from the same place for the same reason. */
function batchOf(rows: ShippingRow[], over: Partial<ShippingBatch> = {}): ShippingBatch {
  const count = (lane: ShippingRow['lane']) => rows.filter((one) => one.lane === lane).length
  const base: ShippingBatch = {
    batch: BATCH,
    name: 'TCGplayer_ShippingExport_20260830.csv',
    expires_in: 1800,
    shipments: rows.length,
    rows,
    lane_counts: {
      envelope: count('envelope'),
      parcel: count('parcel'),
      unjudged: count('unjudged'),
    },
    reason_counts: {
      value_at_threshold: rows.filter((one) => one.reason === 'value_at_threshold').length,
      non_card_signal: rows.filter((one) => one.reason === 'non_card_signal').length,
      cards_only: rows.filter((one) => one.reason === 'cards_only').length,
      no_weight_data: rows.filter((one) => one.reason === 'no_weight_data').length,
      no_value_data: rows.filter((one) => one.reason === 'no_value_data').length,
      sub_single_weight: rows.filter((one) => one.reason === 'sub_single_weight').length,
    },
    parcel_count: count('parcel'),
    file: { name: 'pirateship-import.csv', bytes: 2048 },
    stamps: null,
  }
  return { ...base, ...over }
}

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
  options: { batch?: ShippingBatch; refuse?: { code: string; message: string } } = {},
): Promise<Wire[]> {
  const wire: Wire[] = []

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

test('every row says it in words and in a machine reason, and only judged rows are qualified', async ({
  page,
}) => {
  await open(page, { batch: threeKinds() })
  await readExport(page)

  const value = page.locator('.shipping-row').filter({ hasText: VALUE_ORDER })
  const weight = page.locator('.shipping-row').filter({ hasText: WEIGHT_ORDER })
  const unjudged = page.locator('.shipping-row').filter({ hasText: UNJUDGED_ORDER })

  /* THE SENTENCE AND THE CODE, ON EVERY ROW. docs/DESIGN.md's human-label-large,
     machine-string-small rule: the operator reads the sentence, and greps the code. */
  await expect(value.locator('.shipping-says')).toHaveText(
    'Worth $50 or more, so tracking is required.',
  )
  await expect(value.locator('.shipping-reason')).toHaveText('value_at_threshold')
  await expect(weight.locator('.shipping-says')).toHaveText(
    'Heavier per item than cards run, so something in it is not a card.',
  )
  await expect(weight.locator('.shipping-reason')).toHaveText('non_card_signal')

  /* THE THREE ABSTENTIONS DO NOT SHARE A SENTENCE, and this is the one of them a real export
     produces most: the row has a value but no usable weight, so what is IN the order is
     unknown. A single "could not judge" string would throw away the only thing that says what
     to do about it. */
  await expect(unjudged.locator('.shipping-says')).toHaveText(
    'No usable weight on the row, so what is in it is unknown.',
  )
  await expect(unjudged.locator('.shipping-reason')).toHaveText('no_weight_data')

  await expect(value.locator('.shipping-quality')).toHaveText('Certain')
  await expect(weight.locator('.shipping-quality')).toHaveText('Inferred')

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
  await expect(ship).toContainText('2 orders in the parcel lane')

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
  await expect(caveats).toContainText('No insurance column is written')
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
