import { test, expect, type Locator, type Page } from '@playwright/test'
import { settleFonts } from './fontsReady'

import type { HistoryRange, PriceHistoryPayload, PricingSku } from '../src/types'

/* THE PRICING SCREEN, ASSERTED WHERE NOTHING ELSE CAN SEE IT.
 *
 * `CLAUDE.md`'s hard rule — "A ROUTE IS NOT A FEATURE" — and `docs/GATES.md` step 7's account
 * of 7b shipping with three screens missing from the ROUTES table while harness, lint,
 * typecheck and docs-audit were ALL green. Only `make design-check` could tell, and it is
 * deliberately not on the commit path. This file is that check for `#/pricing`.
 *
 * THE STRONGEST CASES HERE ARE ABSENCES, and that is the form a later refactor cannot quietly
 * satisfy: a suggested row writes NO key, a Tab across one writes NOTHING, a snap onto a
 * blank column writes NOTHING, and the screen draws NO solid accent fill anywhere. Each of
 * those is a rule that would otherwise live only in a comment.
 *
 * WHY THE SUGGESTION MUST NOT BE WRITTEN, since it is the case this file spends the most on:
 * an override is layer 1 of `pipeline/join.py:prices_for` and beats the run's rule at layer 4.
 * A screen that wrote its hundred suggestions into `overrides` would produce a run where
 * changing the preset silently changed nothing — a failure with no symptom. `pipeline/
 * decisions.py` says it in one line: "Nothing here is ever defaulted on your behalf — that is
 * the entire point."
 *
 * NO REAL REQUEST IS EVER MADE. Every route is intercepted; the PUT that writes
 * `decisions.json` is recorded rather than performed, which is what lets these cases assert
 * what the screen WOULD have written.
 *
 * NOT A HARNESS TEST AND MUST NOT BECOME ONE. `docs/GATES.md`'s contract is seven Python tests
 * at the Stop hook; this starts a browser.
 */

const VIEW_ROUTE = '/#/pricing?run=2026-08-30-box7-01'
const VIEW = 'main.pricing'
const RUN = '2026-08-30-box7-01'

type Wire = { method: string; path: string; body: unknown }

/** One SKU in the shape `cli/cmd_join.py:_pricing_table` writes — every field, not the handful
 *  a given case reads. A partial fixture here does not fail partially: the row reads
 *  `row['Number']` and `positions[0]`, so a record missing either takes the screen down and
 *  every assertion below fails with "element not found", which reads exactly like an
 *  unregistered route.
 *
 *  IT IS TYPED, AND IT WAS NOT UNTIL D59 ADDED TWO FIELDS NOBODY NOTICED WERE MISSING. This
 *  read `over: Record<string, unknown>` returning an un-annotated literal, so `PricingSku` was
 *  never applied to the fixture in either direction: `copies_out` and `nothing_to_add` were
 *  added to the wire and to the type, the fixture stayed on the old shape, and `tsc` had
 *  nothing to say about it — which is how the at_cap case below came to exercise the FALLBACK
 *  while reading as coverage of the sentence. `Partial<PricingSku>` also makes an override that
 *  reaches no field an error rather than a no-op; it caught one (`market`), inert since the
 *  case was written. */
function sku(over: Partial<PricingSku> = {}): PricingSku {
  const base: PricingSku = {
    sku: '8608859',
    game: 'pokemon',
    row: {
      'TCGplayer Id': '8608859',
      'Product Line': 'Pokemon',
      'Set Name': 'SV: Prismatic Evolutions',
      'Product Name': 'Articuno - 161/159',
      Title: '',
      Number: '161/159',
      Rarity: 'Secret Rare',
      Condition: 'Near Mint Holofoil',
      'TCG Market Price': '22.03',
      'TCG Direct Low': '21.98',
      'TCG Low Price With Shipping': '22.98',
      'TCG Low Price': '21.98',
      'Total Quantity': '0',
      'Add to Quantity': '0',
      'TCG Marketplace Price': '',
      'Photo URL': '',
    },
    bucket: 'listable',
    copies: 3,
    add_to_quantity: 3,
    backstock: 0,
    live_before: 0,
    committed: 0,
    /* D59's two. `copies_out` is what the cap is spent against — live plus pending, per SKU
       and across every box — and it is `>= live_before` always. `nothing_to_add` is null on
       the ordinary row, which is the row that ADDS one; a case about a row that does not
       overrides both. */
    copies_out: 0,
    nothing_to_add: null,
    at_cap: false,
    condition: 'Near Mint Holofoil',
    set_name: 'SV: Prismatic Evolutions',
    name: 'Articuno - 161/159',
    snap: {
      market: '22.03',
      direct_low: null,
      low: '21.98',
      low_with_shipping: '22.98',
      now: null,
    },
    presets: {
      market_match: '22.03',
      market_undercut_5: '20.93',
      low_undercut_1: '21.76',
    },
    rule_price: '22.03',
    positions: [
      { box: 7, index: 1, label: 'Box 7 · Section 1 · Card 1' },
      { box: 7, index: 2, label: 'Box 7 · Section 1 · Card 2' },
      { box: 7, index: 3, label: 'Box 7 · Section 1 · Card 3' },
    ],
    listing: null,
  }
  return { ...base, ...over }
}

async function open(
  page: Page,
  options: {
    skus?: unknown[]
    decisions?: Record<string, unknown> | null
    /** Whether the run already carries an emit record — the double-press guard's input. */
    emitted?: boolean
    /** The run LIST, for cases about the picker rather than about a table. Each entry is the
     *  handful of `RunSummary` fields a chip draws; everything else is filled in below, so a
     *  case names what it is about and nothing more. */
    runs?: { run: string; box: number | null; box_name: string | null; skus: number }[]
    /** Land with NO run selected, which is the only state the picker is drawn in. The default
     *  route carries `?run=` and goes straight to the table. */
    noRun?: boolean
    /** What `GET .../history` answers. `'refuse'` answers a named refusal, so the panel's
     *  failure arm is exercised against the same shape a real server sends. */
    history?: unknown | 'refuse'
  } = {},
): Promise<Wire[]> {
  const wire: Wire[] = []

  /* THE RUN'S OWN DETAIL, for the files and the phase. Note the ORDER of these route
     registrations matters: this pattern must be registered BEFORE the bare
     `/pipeline/runs/<name>` one below would swallow it, and Playwright matches most-recent
     first, so the specific patterns go last. */
  await page.route(/\/pipeline\/runs\/[^/]+\/emit$/, async (route) => {
    wire.push({
      method: 'POST',
      path: new URL(route.request().url()).pathname,
      body: route.request().postDataJSON(),
    })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        step: 'emit',
        run: RUN,
        console: 'listed           1 row(s), 1 card(s)',
        files: [{ name: 'import-listed.csv', bytes: 2048, modified: 0, is_import: true }],
        summary: { run: RUN, phase: 'reconcile' },
      }),
    })
  })

  await page.route(/\/pipeline\/runs\/[^/]+\/decisions$/, async (route) => {
    wire.push({
      method: 'PUT',
      path: new URL(route.request().url()).pathname,
      body: route.request().postDataJSON(),
    })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, run: RUN, written: 'decisions.json' }),
    })
  })

  /* THE PRICE HISTORY (D62). Registered among the specific patterns for the reason the
     comment above gives — Playwright matches most-recent-first, so `[^/]+$` must not get
     there first. Every case that presses `T` reads `wire` to count how many times this was
     asked, because the load-bearing property of that panel is that it does NOT fire on a
     walk. */
  await page.route(/\/pipeline\/runs\/[^/]+\/history/, async (route) => {
    const url = new URL(route.request().url())
    wire.push({
      method: 'GET',
      path: `${url.pathname}?sku=${url.searchParams.get('sku')}`,
      body: null,
    })
    if (options.history === 'refuse') {
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        /* THE ENVELOPE THE CAPTURE SERVER ACTUALLY SENDS — `{error: {code, message}}`, which
           `app/src/server.ts:errorEnvelope` is the only reader of. A stub with a flatter
           shape falls through to the invented `http_error` message, so the panel would draw
           `409 Conflict from …` and this case would pass while asserting nothing about the
           sentence the server wrote. */
        body: JSON.stringify({
          error: {
            code: 'not_catalogued',
            message: 'Vilemaw is not in a catalogued product line.',
          },
        }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(options.history ?? history()),
    })
  })

  await page.route(/\/pipeline\/runs\/[^/]+\/pricing$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        run: RUN,
        pricing: {
          run: RUN,
          threshold: '0.40',
          floor: '0.40',
          rule: 'match',
          basis: 'market',
          presets: ['market_match', 'market_undercut_5', 'low_undercut_1'],
          games: [
            {
              game: 'pokemon',
              import_listed: 'import-listed.csv',
              import_subthreshold: 'import-subthreshold.csv',
            },
          ],
          skus: options.skus ?? [sku()],
          bands: [],
        },
        decisions:
          options.decisions === undefined
            ? { rule: 'match', basis: 'market', sub_threshold: null, overrides: {} }
            : options.decisions,
        remembered_sub_threshold: null,
      }),
    })
  })

  /* THE RUN DETAIL — its files and its phase, which is where the double-press guard reads
     whether this run has emitted. `[^/]+$` cannot swallow `/pricing`, `/decisions` or
     `/emit`, because a path segment holds no slash. */
  await page.route(/\/pipeline\/runs\/[^/]+$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        run: RUN,
        path: `/tmp/runs/${RUN}`,
        /* WHICH DRAWER, AND WHAT THE OWNER CALLS IT (D56). Both routes carry it because both
           are `_summary` server-side, and this screen prefers the DETAIL: it is what Reload
           re-reads, so a box renamed on `#/inventory` reaches the header on a press. */
        box: 7,
        box_name: 'Riftbound epics',
        live: false,
        phase: options.emitted === true ? 'reconcile' : 'emit',
        joined: true,
        collected: true,
        counts: { skus: 1, cards_in: 3, queued_main: 0, queued_parked: 0 },
        batch_ids: [],
        usage: {},
        console: '',
        files:
          options.emitted === true
            ? [{ name: 'import-listed.csv', bytes: 2048, modified: 0, is_import: true }]
            : [],
        manifest: options.emitted === true ? { emitted: { listed: ['8608859'] } } : {},
      }),
    })
  })

  await page.route(/\/pipeline\/runs$/, async (route) => {
    const listed = options.runs ?? [
      { run: RUN, box: 7, box_name: 'Riftbound epics', skus: 1 },
    ]
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        runs: listed.map((row) => ({
          run: row.run,
          path: `/tmp/runs/${row.run}`,
          box: row.box,
          box_name: row.box_name,
          live: false,
          phase: 'emit',
          /* EVERY FIXTURE RUN IS JOINED, because the picker filters on it — an unjoined run
             has no `pricing.json` and therefore nothing to price. A case wanting the empty
             state passes `runs: []`. */
          joined: true,
          collected: true,
          counts: { skus: row.skus, cards_in: 3, queued_main: 0, queued_parked: 0 },
          batch_ids: [],
          usage: {},
        })),
      }),
    })
  })

  await page.route(/\/photo\//, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="63" height="88"/>',
    })
  })

  await page.goto(options.noRun === true ? '/#/pricing' : VIEW_ROUTE)
  await settleFonts(page)
  await expect(page.locator(VIEW)).toBeVisible()
  return wire
}

/** A reading in the shape `server/pipeline_routes.py:do_pipeline_history` answers.
 *
 *  THE NUMBERS ARE VILEMAW'S, READ LIVE ON 2026-08-30, and the two ranges point OPPOSITE
 *  WAYS on purpose — up 71.2% over the month, down 33.9% over the year. That is the real
 *  shape of the card and it is the case the panel's overlap sentence exists for; a fixture
 *  where both ranges agreed would let a screen that silently merged them pass. */
function history(over: Partial<PriceHistoryPayload> = {}): PriceHistoryPayload {
  const range = (
    name: string,
    vwap: string,
    fraction: string,
    points: number[],
  ): HistoryRange => ({
    range: name,
    buckets: points.length,
    from: '2026-08-01',
    to: '2026-08-30',
    latest_market: '23.63',
    vwap,
    bound: { low: '16.02', high: '22.13', width_of_vwap: '0.3248', width_of_low: '0.3814' },
    momentum: { early: '13.99', late: '23.95', change: '9.96', fraction, window: 5 },
    liquidity: 642,
    transactions: 528,
    units_per_transaction: '1.216',
    dispersion: '6.11',
    points: points.map((market, at) => ({
      at: `2026-08-${String(at + 1).padStart(2, '0')}`,
      market: String(market),
      quantity: 3,
      low: '12.00',
      high: '24.00',
    })),
  })
  return {
    run: RUN,
    sku: '8608859',
    product_id: 684125,
    name: 'Articuno',
    set_name: 'SV: Prismatic Evolutions',
    condition: 'Near Mint Holofoil',
    market: '22.03',
    ranges: [
      range('month', '18.81', '0.7119', [13.58, 15.2, 18.4, 21.9, 23.63]),
      range('annual', '21.50', '-0.3389', [29.15, 26.0, 24.0, 21.0, 19.27]),
    ],
    never_sold: false,
    ...over,
  }
}

const field = (page: Page) => page.getByRole('textbox', { name: /^Price for / })

// ------------------------------------------------------------------ it is reachable

test('the screen is on its own route and draws the run it was linked to', async ({ page }) => {
  await open(page)

  await expect(page.locator('.pricing-title')).toHaveText('Pricing')
  await expect(page.locator('.pricing-scope')).toContainText(RUN)
  /* THE RUN CAME FROM THE URL, NOT FROM STORAGE (D49). `#/runs` links a specific run through
     the hash rather than through a second `sessionStorage` key with its own clearing rules —
     a run name has one source of truth, so nothing here can disagree with anything. */
  await expect(page.locator('.pricing-row')).toHaveCount(1)

  /* AND IT NAMES THE DRAWER (D56). This line read `<run> · N SKUs` — a directory and a count,
     never what is in the box — which is the complaint that produced D56, in the place the
     owner was looking when they made it. The run name STAYS: it is what `emit` and `join` are
     pointed at and what `decisions.json` is written under. What is new goes in front of it. */
  await expect(page.locator('.pricing-scope')).toHaveText(
    `Box 7 · Riftbound epics · ${RUN} · 1 SKUs`,
  )
})

test('the run picker leads with the box, and the directory is what tells two runs apart', async ({
  page,
}) => {
  /* THE OWNER'S OWN STORE IS THE CASE: box 1 carries TWO joined runs, so the headline is
     identical on two chips and the date beneath is the only thing separating them. That is
     what stops the run name being demoted out of usefulness when the box takes the top line —
     `docs/DESIGN.md`'s human-label-large, machine-string-small rule, which the review queue
     already applies to its reason codes, pointed at a picker. */
  await open(page, {
    runs: [
      { run: '2026-08-30-box3-01', box: 3, box_name: 'RB Epics', skus: 15 },
      { run: '2026-08-29-box1-01', box: 1, box_name: 'UNL Rares', skus: 50 },
      { run: '2026-08-22-box1-03', box: 1, box_name: 'UNL Rares', skus: 45 },
      /* A BOX WITH NO NAME. D20 leaves a name optional, so this is an ordinary box and its
         chip must draw the number ALONE — no separator, no placeholder. */
      { run: '2026-08-24-box2-01', box: 2, box_name: null, skus: 108 },
    ],
    noRun: true,
  })

  const chips = page.locator('.pricing-run')
  await expect(chips).toHaveCount(4)
  await expect(chips.nth(0).locator('.pricing-run-name')).toHaveText('Box 3 · RB Epics')
  await expect(chips.nth(1).locator('.pricing-run-name')).toHaveText('Box 1 · UNL Rares')
  await expect(chips.nth(2).locator('.pricing-run-name')).toHaveText('Box 1 · UNL Rares')
  await expect(chips.nth(3).locator('.pricing-run-name')).toHaveText('Box 2')

  /* THE DIRECTORY IS STILL DRAWN, and on the two chips whose headline is identical it is the
     whole of the difference. An assertion on the headline alone would go green against a chip
     that had dropped the run name entirely. */
  await expect(chips.nth(1).locator('.pricing-run-id')).toHaveText('2026-08-29-box1-01')
  await expect(chips.nth(2).locator('.pricing-run-id')).toHaveText('2026-08-22-box1-03')
  await expect(chips.nth(0)).toContainText('15 SKUs')
})

test('every export column that carries data is on the row', async ({ page }) => {
  await open(page)

  /* The owner's requirement in their own words: "I want all the data from the CSV shown when
     I make the decision". The four price columns are the ones a subset would have dropped. */
  const refs = page.locator('.pricing-ref')
  await expect(refs).toHaveCount(4)
  await expect(refs.nth(0)).toHaveText('$22.03')
  await expect(refs.nth(2)).toHaveText('$21.98')
  await expect(refs.nth(3)).toHaveText('$22.98')
  /* A BLANK CELL DRAWS AN EM DASH AND NOT `$0.00` — measured, TCG Direct Low is blank on
     2,060 of 2,476 listable rows, and D9 holds that a missing price is unknown, not low. */
  await expect(refs.nth(1)).toHaveText('—')

  await expect(page.locator('.pricing-meta')).toContainText('Near Mint Holofoil')
  await expect(page.locator('.pricing-meta')).toContainText('Secret Rare')
  await expect(page.locator('.pricing-sku')).toHaveText('8608859')
})

// -------------------------------------------------- the suggestion writes nothing

test('a suggested row carries the rule price and writes no key at all', async ({ page }) => {
  const wire = await open(page)

  await expect(field(page)).toHaveValue('22.03')
  await expect(page.locator('.pricing-row')).toHaveAttribute('data-answer', 'suggested')

  /* THE LOAD-BEARING ABSENCE. An override is layer 1 of the ladder and beats the rule at
     layer 4, so a screen that wrote its suggestions would produce a run where changing the
     preset silently changed nothing. Nothing has been pressed; nothing may have been sent. */
  expect(wire.filter((row) => row.method === 'PUT')).toHaveLength(0)
})

// -------------------------------------------------- shipping the run (D54)

test('the sub-threshold answer is settable here, and emit says what it still owes', async ({
  page,
}) => {
  const wire = await open(page, {
    /* `bucket` alone puts the row in the sub-threshold section — it is decided by the Market
       cell at join time and nothing the screen does can move a row between sections (D28).
       This carried a `market: '0.12'` beside it that reached no field of `PricingSku` and was
       therefore inert from the day it was written; the annotation on `sku()` is what found
       it. */
    skus: [sku({ bucket: 'sub_threshold' })],
    decisions: { rule: 'match', basis: 'market', sub_threshold: null, overrides: {} },
  })

  /* THE REFUSAL EMIT MAKES, ON THE SCREEN WHERE IT CAN BE ANSWERED. `blocking` never consults
     `overrides`, so hand-pricing every row still left emit refusing and the only surface for
     this answer was a JSON textarea on another route. Two of the three runs on disk are
     parked on exactly this. */
  await expect(page.locator('.pricing-ready')).toContainText('Emit will refuse')

  await page.getByRole('button', { name: /At the \$0.40 floor/ }).click()
  await expect.poll(() => wire.filter((r) => r.method === 'PUT').length).toBe(1)
  const body = wire.filter((r) => r.method === 'PUT')[0]?.body as {
    decisions: Record<string, unknown>
  }
  /* THE BARE STRING `pipeline/decisions.py` COMPARES AGAINST, never a value derived from the
     button's label — that comparison is a `==` with no trim and no case fold. */
  expect(body.decisions.sub_threshold).toBe('floor')

  await expect(page.locator('.pricing-ready')).toContainText('Pricing is answered')
  /* AND IT CLAIMS ONLY WHAT IT CHECKED. The screen sees two of emit's ~8 refusals; "ready to
     emit" would be a promise it cannot keep, and overstating a check is worse than not
     running one. */
  await expect(page.locator('.pricing-ready')).toContainText('can still refuse')
})

test('typing a price then pressing emit saves before it sends', async ({ page }) => {
  const wire = await open(page)

  await field(page).fill('19.99')
  await page.getByRole('button', { name: 'Write the import files' }).click()

  await expect.poll(() => wire.filter((r) => r.method === 'POST').length).toBe(1)

  /* THE WRITE RACE, ASSERTED AS AN ORDER. The click blurs the field, which commits and calls
     `setDoc`; the handler then runs in the SAME event with the OLD document in its closure,
     so a POST fired there would emit against the file as it was before the last answer. The
     press raises `waiting` instead and the send waits for the save loop to go quiet. */
  const order = wire.filter((r) => r.method === 'PUT' || r.method === 'POST').map((r) => r.method)
  expect(order).toEqual(['PUT', 'POST'])
})

test('the press cannot be made twice into two emits', async ({ page }) => {
  const wire = await open(page)

  await page.getByRole('button', { name: 'Write the import files' }).click()
  await expect.poll(() => wire.filter((r) => r.method === 'POST').length).toBe(1)

  /* THE SECOND PRESS HAS NOWHERE TO LAND. Once the run has emitted, the control that writes
     is ABSENT — replaced by a sentence and a quieter `Write them again` which arms rather
     than fires. Asserted as the absence rather than as a disabled attribute, because a
     disabled button is one attribute away from pressable and that attribute is what a later
     refactor drops. Clicking a vanished locator is what this case used to do, and it waited
     out the full timeout proving nothing. */
  await expect(page.getByRole('button', { name: 'Write the import files' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Write them again' })).toBeVisible()
  expect(wire.filter((r) => r.method === 'POST')).toHaveLength(1)
})

test('an already-emitted run takes two presses, and the first is not it', async ({ page }) => {
  const wire = await open(page, { emitted: true })

  /* ABSENT, NOT DISABLED. A second emit used to overwrite the good CSV with a header-only
     file and blank the manifest, after which `reconcile` refused a run that had emitted
     perfectly. D54 fixed the command; this stops the press being made by momentum. */
  await expect(page.getByRole('button', { name: 'Write the import files' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Write them again' }).click()
  expect(wire.filter((r) => r.method === 'POST')).toHaveLength(0)

  await page.getByRole('button', { name: 'Write again' }).click()
  await expect.poll(() => wire.filter((r) => r.method === 'POST').length).toBe(1)
})

test('an import file is offered as a download, which is the gap Gate B left open', async ({
  page,
}) => {
  await open(page)
  await page.getByRole('button', { name: 'Write the import files' }).click()

  /* docs/GATES.md, on what Gate B did not close: emit's import files existed only as
     filenames in terminal output the owner never saw. This is the link that closes it —
     RELOCATED HERE FROM `run-panel.spec.ts` on 2026-08-30 with the press that writes them
     (D54), because the gap was never "the file must be at address X"; it was that the press
     and the receipt were in different places. */
  const file = page.locator('.run-file-import')
  await expect(file).toBeVisible()
  await expect(file).toContainText('import-listed.csv')
  await expect(file).toHaveAttribute('download', 'import-listed.csv')
  expect(await file.getAttribute('href')).toContain('/pipeline/runs/')

  /* AND THE ERRAND THAT FOLLOWS, named where it starts. */
  await expect(page.locator('.pricing-ship')).toContainText('Export From Staged')
})

test('tabbing across a suggested row writes nothing', async ({ page }) => {
  const wire = await open(page)

  await field(page).focus()
  await page.keyboard.press('Tab')
  await page.waitForTimeout(200)

  /* A HELD TAB THROUGH A HUNDRED ROWS MUST NOT WRITE A HUNDRED OVERRIDES. Focus is not a
     decision, and neither is leaving a field you did not type in. */
  expect(wire.filter((row) => row.method === 'PUT')).toHaveLength(0)
})

test('the first digit typed clears the suggestion, and Enter commits what you typed', async ({
  page,
}) => {
  const wire = await open(page)

  /* THE OWNER'S OWN SENTENCE, ASSERTED LITERALLY: "if i type numbers they ought to
     immediately clear and now my typing be inputed as the price and then i should be able to
     hit enter". A field that appended instead would turn 4.50 into 22.034.50. */
  await field(page).focus()
  await page.keyboard.type('4.50')
  await expect(field(page)).toHaveValue('4.50')

  await page.keyboard.press('Enter')
  await expect.poll(() => wire.filter((row) => row.method === 'PUT').length).toBeGreaterThan(0)

  const sent = wire.filter((row) => row.method === 'PUT').pop()?.body as {
    decisions?: { overrides?: Record<string, unknown> }
  }
  expect(sent.decisions?.overrides).toEqual({ '8608859': '4.50' })
})

test('the field refuses anything that is not a price, at the keystroke', async ({ page }) => {
  await open(page)

  await field(page).focus()
  await page.keyboard.type('1.234')
  /* THE ALPHABET IS CLOSED — at most two digits after the dot — and a key that would break it
     is rejected at `beforeinput` rather than accepted and flagged. A rejected key is felt
     now; a flagged one is read later, if at all. That closure is also what makes every letter
     unambiguously a command on this screen. */
  await expect(field(page)).toHaveValue('1.23')
})

// ---------------------------------------------------------------------- the snaps

test('a letter snaps the price to its column, and does not commit', async ({ page }) => {
  const wire = await open(page)

  await field(page).focus()
  await page.keyboard.press('l')
  await expect(field(page)).toHaveValue('21.98')

  /* A SNAP YOU CANNOT INSPECT IS A SNAP YOU CANNOT CHECK. It sets the field and stops there;
     the extra Enter is what makes `l`, look, Enter possible. */
  await page.waitForTimeout(150)
  expect(wire.filter((row) => row.method === 'PUT')).toHaveLength(0)
})

test('a snap onto a blank column refuses, says so, and writes nothing', async ({ page }) => {
  const wire = await open(page)

  await field(page).focus()
  await page.keyboard.press('d')

  /* Writing "" would reach `_price` in decisions.py and raise `MalformedDecisions` at the
     next join, an hour later. The field is untouched and the refusal is on screen now. */
  await expect(field(page)).toHaveValue('22.03')
  await expect(page.locator('.pricing-refusal')).toContainText('direct low')
  await page.waitForTimeout(150)
  expect(wire.filter((row) => row.method === 'PUT')).toHaveLength(0)
})

// ----------------------------------------------------------------------- the hold

test('a hold writes a reason and a watch, and never a price', async ({ page }) => {
  const wire = await open(page)

  await page.locator('.pricing-hold').click()
  await expect(page.locator('.pricing-holdpanel')).toBeVisible()

  /* LETTERS AND NOT DIGITS in this panel, and the reason is specific rather than borrowed:
     the digits on this screen are price entry, so a digit inside a panel raised from a
     focused price field is unresolvable. */
  await page.getByRole('button', { name: /Bullish/ }).click()
  await page.getByLabel(/Tell me when market is above/).fill('30.00')
  await page.getByLabel('Note').fill('waiting on rotation')
  await page.getByRole('button', { name: 'Hold it' }).click()

  await expect.poll(() => wire.filter((row) => row.method === 'PUT').length).toBeGreaterThan(0)
  const sent = wire.filter((row) => row.method === 'PUT').pop()?.body as {
    decisions?: { overrides?: Record<string, unknown> }
  }
  expect(sent.decisions?.overrides).toEqual({
    '8608859': { withheld: 'bullish', watch_above: '30.00', note: 'waiting on rotation' },
  })
})

test('a held row says so, in both registers, and has no price field', async ({ page }) => {
  await open(page, {
    decisions: {
      rule: 'match',
      basis: 'market',
      overrides: { '8608859': { withheld: 'bullish', note: 'waiting on rotation' } },
    },
  })

  await expect(page.locator('.pricing-row')).toHaveAttribute('data-answer', 'held')
  await expect(page.locator('.pricing-held')).toContainText('Holding')
  /* docs/DESIGN.md's human-label-large, machine-string-small rule. The machine line is the
     JSON as it sits in the file, so grepping `withheld` finds the screen, decisions.json and
     the run report at once — which is the only job that line has.

     IT IS ON THE ROW'S SECOND LINE AND NOT INSIDE THE HELD CELL, which is where it used to
     be drawn and could not fit: that column is 120px and `withheld: next_batch` measures
     152px in this face, so the token wrapped and the cell overprinted the sentence beneath
     it. Asserted through `.pricing-row-note` deliberately — the selector names the line the
     token has to be on, so a change that put it back in the 120px cell fails here rather
     than in a screenshot nobody takes. */
  await expect(page.locator('.pricing-row-note .pricing-machine')).toHaveText('withheld: bullish')
  await expect(page.locator('.pricing-row-note')).toContainText('waiting on rotation')
  await expect(field(page)).toHaveCount(0)
})

// -------------------------------------------------------------------- the photo

test('the photo is on demand, names which copy it is, and the same key closes it', async ({
  page,
}) => {
  await open(page)

  await expect(page.locator('.pricing-photo')).toHaveCount(0)
  await field(page).focus()
  await page.keyboard.press('p')

  /* THE REPRESENTATIVE PHOTOGRAPH IS NAMED RATHER THAN PICKED SILENTLY. There is no quality
     signal worth trusting — confidence is the tempting one and exactly wrong, since T1's
     recorded misses are confident answers with the digits wrong — so the pick is the first in
     box-walk order, said out loud, and steppable. */
  await expect(page.locator('.pricing-photo')).toBeVisible()
  await expect(page.locator('.pricing-photo-caption')).toContainText('Box 7 · Section 1 · Card 1')
  await expect(page.locator('.pricing-photo-caption')).toContainText('1 of 3')

  await page.getByRole('button', { name: 'Next copy' }).click()
  await expect(page.locator('.pricing-photo-caption')).toContainText('2 of 3')

  /* THE SAME KEY CLOSES IT, so `Escape` keeps its two existing jobs in the field and the
     panel never takes a binding away from price entry. */
  await field(page).focus()
  await page.keyboard.press('p')
  await expect(page.locator('.pricing-photo')).toHaveCount(0)
})

test('the caption draws the label the server composed on THIS read, including where it composed none', async ({
  page,
}) => {
  /* THE LABEL IS RE-RENDERED SERVER-SIDE ON EVERY READ AND THE ONE IN `pricing.json` IS NEVER
     SERVED (D58, on D56's rule) — `server/pipeline_routes.py:_relabel_positions`. So this panel
     receives strings that DID NOT EXIST when the run was joined, and the two it must be able to
     draw are the two a stored label cannot produce: a copy that left the box afterwards, and a
     position the server would not name at all.

     IT MATTERS MORE HERE THAN WHERE THE SAME STRINGS ARE DRAWN LARGER, because `photoUrl`
     addresses the photograph BY SLOT. The picture above the caption has always been the index's
     current occupant; until the re-render landed the caption was the join's, so the two named
     different cards and nothing on the screen said which was which. */
  await open(page, {
    skus: [
      sku({
        positions: [
          { box: 7, index: 1, label: 'Box 7 · departed · 7/1' },
          { box: 7, index: 2, label: null },
          { box: 7, index: 3, label: 'Box 7 · Section 1 · Card 1' },
        ],
      }),
    ],
  })

  await field(page).focus()
  await page.keyboard.press('p')

  /* WHOLE, AND THE TRAILING KEY IS THE POINT (D68). Two sold copies of one SKU in one box drew
     the identical string before that entry, which is exactly the case this strip steps through.
     `PositionLabel` would promote a bare trailing number to a 44px slot figure — the lie D58
     refuses — and `7/1` is what fails that guard; this caption is plain text and must not start
     parsing the string either. */
  await expect(page.locator('.pricing-photo-caption')).toContainText('Box 7 · departed · 7/1')
  await expect(page.locator('.pricing-photo-caption')).toContainText('1 of 3')

  /* `no label · <key>` IS `BoxBrowse`'s OWN FALLBACK, one vocabulary with it and for its reason:
     the server answers null where it will not name a place — a box its walk could not count, or
     one no located record names any more — and `7/2` bare reads like a position and is not one.
     Drawing nothing here would leave a dangling separator in front of `2 of 3`, which reads as a
     fault rather than as an answer. */
  await page.getByRole('button', { name: 'Next copy' }).click()
  await expect(page.locator('.pricing-photo-caption')).toContainText('no label · 7/2')
  await expect(page.locator('.pricing-photo-caption')).toContainText('2 of 3')

  await page.getByRole('button', { name: 'Next copy' }).click()
  await expect(page.locator('.pricing-photo-caption')).toContainText('Box 7 · Section 1 · Card 1')
})

// ------------------------------------------------------------ the design rules

test('the screen draws no solid accent fill anywhere', async ({ page }) => {
  await open(page)

  /* docs/DESIGN.md reserves the solid fill for "exactly one thing to do", and reasons about
     the harm on the review queue: filling the pricier candidate teaches the queue to drift
     toward over-listing. Every state of this screen is a choice among prices, so the same
     harm is available at run scale. A hundred-row worklist is the definition of more than one
     answer. */
  const accent = await page.evaluate(() => {
    const token = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()
    const rgb = (hex: string) => {
      const n = parseInt(hex.replace('#', ''), 16)
      return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`
    }
    const want = rgb(token)
    return [...document.querySelectorAll('main.pricing *')].filter(
      (node) => getComputedStyle(node).backgroundColor === want,
    ).length
  })
  expect(accent).toBe(0)
})

test('nothing folds — no disclosure anywhere in the screen', async ({ page }) => {
  await open(page)

  /* D33 as amended, in the owner's own words: "i don't want click in functionality, i want
     their buttons just there." Asserted as an absence for the reason `run-panel.spec.ts`
     gives: it is the one form of that ruling no future relocation can quietly falsify. */
  await expect(page.locator('main.pricing details')).toHaveCount(0)
  await expect(page.locator('main.pricing summary')).toHaveCount(0)
})

test('the caption and the rows share one grid template, so they cannot drift', async ({
  page,
}) => {
  await open(page)

  /* THE ROWS ARE AWAITED BEFORE THE EVALUATE, AND THAT IS NOT DEFENSIVE PADDING. `open`
     waits for `main.pricing`, which renders before the pricing fetch resolves — so the rows
     are not on the page yet. Every other case here reaches the DOM through a Playwright
     locator and is auto-waited for free; this one is the only case that runs
     `document.querySelector` in the page, which waits for nothing. It passed alone and
     failed in the parallel suite with a null element, which is the same signature the
     comment below records for a different cause: an assertion that is racing the render
     rather than measuring it. */
  await expect(page.locator('.pricing-caption')).toBeVisible()
  await expect(page.locator('.pricing-row')).toHaveCount(1)

  /* Two declarations that have to agree is two declarations that will eventually not. The
     template is a custom property read by both, which makes the drift structurally impossible
     rather than carefully avoided — and this case is what stops a later edit inlining one.

     THE ASSERTION IS THE DECLARED PROPERTY AND THE COLUMN COUNT, NOT THE RESOLVED PIXELS, and
     the first draft got that wrong in a way worth recording: `gridTemplateColumns` resolves
     `minmax(0, 1fr)` against each element's OWN container, and the caption's parent is the
     section while a row's is the list — so the two strings can differ by a pixel for reasons
     that have nothing to do with drift. It passed alone and failed in the parallel suite,
     which is the signature of an assertion measuring the wrong thing. */
  const seen = await page.evaluate(() => {
    const caption = document.querySelector('.pricing-caption')!
    const row = document.querySelector('.pricing-row')!
    const declared = (node: Element) =>
      getComputedStyle(node).getPropertyValue('--pricing-cols').trim()
    const count = (node: Element) =>
      getComputedStyle(node).gridTemplateColumns.split(' ').length
    return {
      captionCols: declared(caption),
      rowCols: declared(row),
      captionCount: count(caption),
      rowCount: count(row),
    }
  })
  expect(seen.captionCols).not.toBe('')
  expect(seen.captionCols).toBe(seen.rowCols)
  expect(seen.captionCount).toBe(seen.rowCount)
})

// -------------------------------------------------- why a row adds nothing (D59)

test('the reason a row adds nothing is a heading, composed by the SERVER, verbatim', async ({
  page,
}) => {
  /* THE SENTENCE IS THE SERVER'S AND THE CLIENT MAY NOT COMPOSE ONE. This note read
     "nothing to add this run — TCGplayer already holds {live_before}", built here out of the
     export's live column alone — and `live_before` is 0 for every copy sitting on an import
     nobody has reconciled, which is 167 copies across 72 SKUs of the owner's store and every
     SKU of both runs on disk. So wherever it drew at all it said TCGplayer holds NOTHING under
     a row adding nothing BECAUSE TCGplayer was holding them.

     `pipeline/join.py:SkuMatch.nothing_to_add` names which of three reasons applies, beside
     the numbers, because they have three different remedies (D59). The one below is the branch
     that is almost always the reason on this operator's store: they do not run `reconcile` and
     never will, so `pushed` never lands and the export never learns about it. Asserted as the
     EXACT string rather than a substring — a client that reassembled this out of `live_before`,
     `copies_out` and `committed` would be a second copy of that property's reasoning with
     nothing auditing the two against each other, and a near-miss is exactly what it would
     produce. */
  const pending =
    '0 live and 4 on an import this pipeline has not seen land — 4 of the 4 this SKU may have out'

  /* AND THE FALLBACK IS NOT DEFENSIVE PADDING. This table is `pricing.json` READ OFF DISK, so
     a file written by an earlier join carries `at_cap` with no sentence beside it — measured,
     both runs in `runs/` today. Modelled by DELETING the key, because that is the shape on
     disk and `PricingSku` cannot express an absent field; `null` reaches the same `??` and is
     what a fresh join writes for a zero-copy match. An older file must state the bare fact,
     which is exactly what `at_cap` means, and invent no reason for it. */
  const older = sku({
    sku: '8608659',
    name: 'Wattrel',
    at_cap: true,
    add_to_quantity: 0,
    copies: 2,
  }) as Partial<PricingSku>
  delete older.nothing_to_add

  await open(page, {
    skus: [
      sku({
        sku: '8608459',
        name: 'Dunsparce',
        at_cap: true,
        add_to_quantity: 0,
        copies: 4,
        live_before: 0,
        copies_out: 4,
        nothing_to_add: pending,
      }),
      older,
    ],
  })

  /* ONE HEADING PER REASON, AND THE ROWS THEMSELVES SAY NOTHING. Two reasons here, so two
     headings — the three the join composes have three different remedies and are never merged
     into one bucket of leftovers. */
  const heads = page.locator('.pricing-group-head')
  await expect(heads).toHaveCount(2)
  await expect(heads.nth(0).locator('.pricing-group-why')).toHaveText(pending)
  await expect(heads.nth(1).locator('.pricing-group-why')).toHaveText('nothing to add this run')
  await expect(page.locator('.pricing-row .pricing-row-note')).toHaveCount(0)

  /* THE FALSE SENTENCE BY NAME, so a client that starts composing again is caught even if it
     composes something the assertion above happens to match. Neither row may claim the export
     knows what TCGplayer is holding. */
  await expect(page.locator(VIEW)).not.toContainText('already holds')
})

/* THE ORDER THE ROWS ARE DRAWN IN, WHICH IS NOT THE ORDER THEY ARRIVE IN.
 *
 * `cli/cmd_join.py` writes `pricing.json` market-descending, so a SKU whose every copy is
 * already listed or has left the box lands wherever its market price puts it — which on the
 * owner's box 3 was the top three rows of a 51-row section, three of the most expensive
 * non-questions in the run standing where the eye starts. They sink; the rows that still want
 * a price keep the top, in the market order the join gave them.
 *
 * THE FIXTURE INTERLEAVES ON PURPOSE. A case whose sunk row is already last would pass against
 * a screen that reorders nothing at all. */
test('a row that adds nothing sinks to the bottom of its section, under its heading', async ({
  page,
}) => {
  await open(page, {
    skus: [
      sku({ sku: '8608859', name: 'Articuno' }),
      sku({
        sku: '8608459',
        name: 'Dunsparce',
        at_cap: true,
        add_to_quantity: 0,
        nothing_to_add: 'every copy in this run is already listed or has left the box',
      }),
      sku({ sku: '8608659', name: 'Wattrel' }),
    ],
  })

  await expect(page.locator('.pricing-name')).toHaveText(['Articuno', 'Wattrel', 'Dunsparce'])

  /* THE HEADING IS BETWEEN THEM AND NOT MERELY SOMEWHERE ON THE PAGE, which is the whole of
     what the owner asked for: the sentence stops being every row's own subtext and becomes the
     line those rows fall under. Read off the list's children in order, so a heading drawn
     above the section or after the last row fails. */
  const drawn = await page
    .locator('.pricing-list > *')
    .evaluateAll((nodes) => nodes.map((node) => node.className))
  expect(drawn).toEqual([
    'pricing-row',
    'pricing-row',
    'pricing-group-head',
    'pricing-row',
  ])

  /* AND ENTER STEPS THE ORDER THAT IS DRAWN. The advance walked the WIRE order, and got away
     with it for as long as the wire's market-descending sort happened to draw the sections in
     their own order. Sinking a group ends that: stepping the wire here would send the focus
     from the first row down to `Dunsparce` at the bottom of the section and back up again. */
  const fields = field(page)
  await fields.nth(0).focus()
  await page.keyboard.press('Enter')
  await expect(fields.nth(1)).toBeFocused()
  await expect(fields.nth(1)).toHaveAttribute('aria-label', 'Price for Wattrel')
})

/* THE HOLD TIER, WHICH IS THE SECOND HALF OF THE SAME ASK.
 *
 * The owner, the day D78 landed: *"make it so that upon a reopening that page those that were
 * held are also moved down in their own category (after prices, before all are sold/listed)"*.
 * Three tiers, and the order is theirs — the rows that still want a price, the rows they have
 * already answered with a hold, then the rows this run can add nothing for at all.
 *
 * ONE HEADING OVER ALL THE HOLDS, unlike the cap tier's one-per-sentence. The reason is per
 * SKU and is already drawn on the row as `withheld: <reason>`; a heading per reason would
 * scatter three rows across three headings to restate what each row already says. */
test('a held row sinks between the prices and the rows that can add nothing', async ({
  page,
}) => {
  await open(page, {
    skus: [
      sku({ sku: '8608859', name: 'Articuno' }),
      sku({
        sku: '8608459',
        name: 'Dunsparce',
        at_cap: true,
        add_to_quantity: 0,
        nothing_to_add: 'every copy in this run is already listed or has left the box',
      }),
      sku({ sku: '8608659', name: 'Wattrel' }),
      sku({ sku: '8608959', name: 'Kled' }),
    ],
    decisions: {
      rule: 'match',
      basis: 'market',
      sub_threshold: null,
      overrides: { '8608659': { withheld: 'bullish' } },
    },
  })

  await expect(page.locator('.pricing-name')).toHaveText([
    'Articuno',
    'Kled',
    'Wattrel',
    'Dunsparce',
  ])

  const drawn = await page
    .locator('.pricing-list > *')
    .evaluateAll((nodes) => nodes.map((node) => node.className))
  expect(drawn).toEqual([
    'pricing-row',
    'pricing-row',
    'pricing-group-head',
    'pricing-row',
    'pricing-group-head',
    'pricing-row',
  ])

  const heads = page.locator('.pricing-group-head .pricing-group-why')
  await expect(heads).toHaveText([
    'held back from this run',
    'every copy in this run is already listed or has left the box',
  ])

  /* AND THE REASON IS STILL ON THE ROW. The heading says the group is held; which hold it is
     stays greppable from the screen to `decisions.json` (D49), which is the whole argument for
     drawing the machine string at all. */
  await expect(page.locator('.pricing-row').nth(2).locator('.pricing-machine')).toHaveText(
    'withheld: bullish',
  )
})

/* A HELD ROW THAT IS *ALSO* AT THE CAP GOES UNDER THE CAP'S HEADING, and the case exists
 * because the two tiers overlap in the store: a card can be at the live cap and withheld at
 * once. The hold changes nothing about a SKU this run was never going to add a row for, so the
 * deeper fact wins the placement — and the hold is not lost by being outranked, because its
 * token still draws beside it. */
test('a row that is both held and at the cap sinks to the deeper heading', async ({ page }) => {
  await open(page, {
    skus: [
      sku({ sku: '8608859', name: 'Articuno' }),
      sku({
        sku: '8608459',
        name: 'Dunsparce',
        at_cap: true,
        add_to_quantity: 0,
        nothing_to_add: 'every copy in this run is already listed or has left the box',
      }),
    ],
    decisions: {
      rule: 'match',
      basis: 'market',
      sub_threshold: null,
      overrides: { '8608459': { withheld: 'keeping' } },
    },
  })

  await expect(page.locator('.pricing-group-head .pricing-group-why')).toHaveText([
    'every copy in this run is already listed or has left the box',
  ])
  await expect(page.locator('.pricing-row').nth(1).locator('.pricing-machine')).toHaveText(
    'withheld: keeping',
  )
})

/* THE SINK HAPPENS ON THE REOPENING AND NEVER UNDER THE HAND THAT PRESSED `H`, which is D28
 * held to in the one place on this screen where the order's input is an answer the operator can
 * change: `bucket`, `at_cap` and `nothing_to_add` are the join's and cannot move mid-session,
 * and a hold is this screen's own. A row that jumped down the list on the press would take the
 * next row up to meet a finger already travelling to it.
 *
 * BOTH HALVES IN ONE CASE, because either alone passes against a wrong screen: a case that only
 * checked the press passes against a screen that never sinks holds at all, and one that only
 * checked the reload passes against a screen that sinks them the instant they are taken. */
test('a hold taken now does not move its row, and has moved it by the next load', async ({
  page,
}) => {
  const skus = [
    sku({ sku: '8608859', name: 'Articuno' }),
    sku({ sku: '8608459', name: 'Dunsparce' }),
    sku({ sku: '8608659', name: 'Wattrel' }),
  ]
  await open(page, { skus })

  await page.locator('.pricing-row').nth(1).getByRole('button', { name: 'Hold Dunsparce' }).click()
  await expect(page.locator('.pricing-holdpanel')).toBeVisible()
  await page.getByRole('button', { name: /Keeping this one/ }).click()
  await page.getByRole('button', { name: 'Hold it' }).click()

  await expect(page.locator('.pricing-row').nth(1).locator('.pricing-machine')).toHaveText(
    'withheld: keeping',
  )
  await expect(page.locator('.pricing-name')).toHaveText(['Articuno', 'Dunsparce', 'Wattrel'])
  await expect(page.locator('.pricing-group-head')).toHaveCount(0)

  /* THE SECOND OPENING, WITH THE SERVER NOW CARRYING THE ANSWER. Registered after `open`,
     which is what makes it win — Playwright matches handlers newest first. */
  await page.route(/\/pipeline\/runs\/[^/]+\/pricing$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        run: RUN,
        pricing: {
          run: RUN,
          threshold: '0.40',
          floor: '0.40',
          rule: 'match',
          basis: 'market',
          presets: ['market_match', 'market_undercut_5', 'low_undercut_1'],
          games: [
            {
              game: 'pokemon',
              import_listed: 'import-listed.csv',
              import_subthreshold: 'import-subthreshold.csv',
            },
          ],
          skus,
          bands: [],
        },
        decisions: {
          rule: 'match',
          basis: 'market',
          sub_threshold: null,
          overrides: { '8608459': { withheld: 'keeping' } },
        },
        remembered_sub_threshold: null,
      }),
    })
  })
  await page.reload()
  await settleFonts(page)

  await expect(page.locator('.pricing-name')).toHaveText(['Articuno', 'Wattrel', 'Dunsparce'])
  await expect(page.locator('.pricing-group-head .pricing-group-why')).toHaveText([
    'held back from this run',
  ])
})

test('a row is the same height whether or not it carries a note', async ({ page }) => {
  await open(page, {
    skus: [sku(), sku({ sku: '8608459', name: 'Dunsparce' })],
    decisions: {
      rule: 'match',
      basis: 'market',
      sub_threshold: null,
      overrides: { '8608459': { withheld: 'bullish', note: 'holding for the set rotation' } },
    },
  })

  /* D28's other half — the list must not move under a finger. The note lands in a second grid
     row that every zone but the card leaves empty by construction, so a row that acquires a
     sentence costs no height and a hundred-row list cannot reflow when one does.

     THE NOTE IS A HOLD'S NOW AND NOT `at_cap`'s. The run's reason for adding nothing moved to
     the group heading, so the only string that still lands on this line per-row is the
     operator's own — which is the string this invariant has to survive, because it is the one
     nothing bounds the length of. */
  const rows = page.locator('.pricing-row')
  await expect(rows.nth(1).locator('.pricing-row-note')).toBeVisible()
  const heights = await rows.evaluateAll((nodes) =>
    nodes.map((node) => Math.round(node.getBoundingClientRect().height)),
  )
  expect(heights[0]).toBe(heights[1])
})

/* THE STATE THAT BROKE THE INVARIANT WHILE THE CASE ABOVE STAYED GREEN, and the gap is the
 * point: that case compares a priced row against a priced row with a note, and a HELD row is
 * neither. It draws a different cell in the price column and a second machine string, and it
 * stood 54px tall in a 32px track — three wrapped lines that printed over the sentence
 * beneath. The owner reported it off a screenshot, which is the only instrument this repo had
 * pointed at it.
 *
 * THE LONGEST REASON, DELIBERATELY. `next_batch` is the widest of `holds.ts`'s three and the
 * one that fails first: `withheld: next_batch` measures 152px against a 120px column. A case
 * written on `bullish` would be 129px — still too wide, but a fix that merely bought 20px
 * would pass it and ship the wrap.
 *
 * BOTH AT ONCE ON THE LAST ROW, because a held row carrying a note is where the two strings
 * actually collided, and it is a shape the store produces: a card can be withheld with a
 * reason the operator typed at the same time. The colliding string used to be `at_cap`'s
 * sentence, which has since moved up to the group heading — a NOTE of the same length stands
 * in its place, because the length was the whole of the pressure and the operator's note is
 * now the only string on this line nothing bounds. */
test('a held row is the same height as a priced one, reason and note together', async ({
  page,
}) => {
  await open(page, {
    skus: [
      sku(),
      sku({ sku: '8608459', name: 'Dunsparce' }),
      sku({ sku: '8608659', name: 'Wattrel' }),
    ],
    decisions: {
      rule: 'match',
      basis: 'market',
      sub_threshold: null,
      overrides: {
        '8608459': { withheld: 'next_batch' },
        '8608659': {
          withheld: 'next_batch',
          note: 'waiting on the set rotation before this one goes back out',
        },
      },
    },
  })

  const rows = page.locator('.pricing-row')
  await expect(rows).toHaveCount(3)
  await expect(rows.nth(1).locator('.pricing-machine')).toHaveText('withheld: next_batch')
  await expect(rows.nth(2).locator('.pricing-machine')).toHaveText('withheld: next_batch')

  const heights = await rows.evaluateAll((nodes) =>
    nodes.map((node) => Math.round(node.getBoundingClientRect().height)),
  )
  expect(heights[1]).toBe(heights[0])
  expect(heights[2]).toBe(heights[0])

  /* AND NOTHING OVERLAPS, which is the defect said in its own terms rather than inferred from
     a height. A row of the right height whose cell overflowed both ways — 54px centred in 32px
     — is exactly what was on screen, so the height alone would not have caught it. Every box
     is measured against the row that contains it: the held cell and the second line must both
     sit inside their row, and the second line must start at or below where the held cell
     ends. */
  const boxes = await rows.evaluateAll((nodes) =>
    nodes.map((node) => {
      const rect = (el: Element | null) =>
        el === null ? null : { top: el.getBoundingClientRect().top, bottom: el.getBoundingClientRect().bottom }
      return {
        row: rect(node),
        held: rect(node.querySelector('.pricing-held')),
        note: rect(node.querySelector('.pricing-row-note')),
      }
    }),
  )
  for (const box of boxes.slice(1)) {
    expect(box.held).not.toBeNull()
    expect(box.held?.top).toBeGreaterThanOrEqual(box.row?.top ?? 0)
    expect(box.held?.bottom).toBeLessThanOrEqual(box.row?.bottom ?? 0)
  }

  const both = boxes.at(-1)
  expect(both?.note).not.toBeNull()
  expect(both?.note?.top).toBeGreaterThanOrEqual(both?.held?.bottom ?? 0)
  expect(both?.note?.bottom).toBeLessThanOrEqual(both?.row?.bottom ?? 0)
})

// ------------------------------------------------------ the save loop actually finishes

test('a committed answer lands and the indicator returns to saved', async ({ page }) => {
  const wire = await open(page)

  await field(page).focus()
  await page.keyboard.type('4.50')
  await page.keyboard.press('Enter')

  await expect.poll(() => wire.filter((row) => row.method === 'PUT').length).toBe(1)
  /* THE INDICATOR IS THE ONLY THING ON SCREEN THAT SAYS THE ANSWER IS SAFE, and it read
     `saving…` forever — on every save, from the first one. The effect depended on the
     `saving` STATE it raised itself, so raising it re-ran the effect and the re-run's cleanup
     killed the in-flight closure: the response landed on a dead one and neither the clear nor
     `setSaving(false)` ever fired. Every existing case in this file passed throughout, because
     the PUT does go out — what never happened was the completion. */
  await expect(page.locator('.pricing-save')).toHaveText('saved')
})

test('a second answer is written too, and it is not the first one over again', async ({
  page,
}) => {
  const wire = await open(page, {
    skus: [sku(), sku({ sku: '8608459', name: 'Dunsparce' })],
  })

  const fields = field(page)
  await fields.nth(0).focus()
  await page.keyboard.type('4.50')
  await page.keyboard.press('Enter')
  await expect.poll(() => wire.filter((row) => row.method === 'PUT').length).toBe(1)

  await fields.nth(1).focus()
  await page.keyboard.type('1.25')
  await page.keyboard.press('Enter')

  /* THE HALF THAT IS NOT COSMETIC. With the loop wedged after the first write, the guard read
     "a save is in flight" forever and every later answer was typed, drawn, and never sent —
     the operator would have priced a box and closed a tab holding one row. The PUT replaces
     the document wholesale, so the second body must carry BOTH answers rather than the second
     alone. */
  await expect.poll(() => wire.filter((row) => row.method === 'PUT').length).toBe(2)
  const sent = wire.filter((row) => row.method === 'PUT').pop()?.body as {
    decisions?: { overrides?: Record<string, unknown> }
  }
  expect(sent.decisions?.overrides).toEqual({ '8608859': '4.50', '8608459': '1.25' })
  await expect(page.locator('.pricing-save')).toHaveText('saved')
})

test('an answer typed while a write is in flight is not lost', async ({ page }) => {
  /* THE COALESCING PROMISE, WHICH THE COMMENT MADE AND THE CODE DID NOT KEEP. `dirty` was a
     flag, and a flag cannot tell "the write I just sent" from "the write that landed while it
     was in flight" — so clearing it on a response discarded whatever had been typed since
     that response left, silently and with the indicator reading `saved`. It is a comparison
     against the document the server confirmed now, so the second answer is still unequal when
     the first write lands and the loop runs again. */
  await open(page, { skus: [sku(), sku({ sku: '8608459', name: 'Dunsparce' })] })

  /* REGISTERED AFTER `open`, WHICH IS WHAT MAKES IT WIN. Playwright matches handlers newest
     first, so this shadows the one `open` installed and holds the first PUT open. */
  const wire: Wire[] = []
  let release = () => {}
  const held = new Promise<void>((resolve) => {
    release = resolve
  })
  await page.route(/\/pipeline\/runs\/[^/]+\/decisions$/, async (route) => {
    wire.push({
      method: 'PUT',
      path: new URL(route.request().url()).pathname,
      body: route.request().postDataJSON(),
    })
    if (wire.length === 1) await held
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, run: RUN, written: 'decisions.json' }),
    })
  })

  const fields = field(page)
  await fields.nth(0).focus()
  await page.keyboard.type('4.50')
  await page.keyboard.press('Enter')
  await expect.poll(() => wire.length).toBe(1)

  await fields.nth(1).focus()
  await page.keyboard.type('1.25')
  await page.keyboard.press('Enter')

  release()

  await expect.poll(() => wire.length).toBe(2)
  const sent = wire.pop()?.body as { decisions?: { overrides?: Record<string, unknown> } }
  expect(sent.decisions?.overrides).toEqual({ '8608859': '4.50', '8608459': '1.25' })
  await expect(page.locator('.pricing-save')).toHaveText('saved')
})

// ------------------------------------------------------- a preset reaches what emit reads

test('a preset writes the rule and the basis, which is what the pipeline reads', async ({
  page,
}) => {
  const wire = await open(page)

  await page.getByRole('button', { name: 'Market −5%' }).click()
  await expect.poll(() => wire.filter((row) => row.method === 'PUT').length).toBeGreaterThan(0)

  const sent = wire.filter((row) => row.method === 'PUT').pop()?.body as {
    decisions?: Record<string, unknown>
  }
  /* THE PRESS USED TO WRITE `preset: <key>`, WHICH NO READER ANYWHERE HAS.
     `pipeline/decisions.py:parse` does not know the field and `to_payload` does not emit it,
     so the next join dropped it and `rule`/`basis` stayed at `match`/`market` — the
     suggestions on screen moved and nothing `emit` reads did. Measured on the owner's
     riftbound run: that dead key beside `rule: match`, 2 overrides across 50 SKUs, 48 cards
     about to list at a price nobody chose. The rule at layer 4 is the thing that has to
     move, because D49 correctly refuses to write the suggestions as overrides at layer 1. */
  expect(sent.decisions?.rule).toBe('undercut:5')
  expect(sent.decisions?.basis).toBe('market')
  expect(sent.decisions).not.toHaveProperty('preset')

  /* AND NO ROW GAINED AN OVERRIDE. The whole reason the preset must move the RULE is that
     writing the suggestions would beat it — layer 1 over layer 4 — and produce a run where
     changing the preset silently changed nothing. */
  expect(sent.decisions?.overrides).toEqual({})
})

test('the chip says which rule is live, and it is derived rather than remembered', async ({
  page,
}) => {
  await open(page)

  const match = page.getByRole('button', { name: 'Match market' })
  const under = page.getByRole('button', { name: 'Market −5%' })

  /* The run loads at `match`/`market`, so that chip is the live one before anything is
     pressed — read off `decisions.json`, not off a selection this screen remembers. */
  await expect(match).toHaveAttribute('aria-pressed', 'true')
  await expect(under).toHaveAttribute('aria-pressed', 'false')

  await under.click()
  await expect(under).toHaveAttribute('aria-pressed', 'true')
  await expect(match).toHaveAttribute('aria-pressed', 'false')
})

test('a hand-typed rule lights no chip rather than a stale one', async ({ page }) => {
  /* `#/runs` edits `decisions.json` as text (D33), so a rule no preset names is ordinary and
     must not be drawn as one of the three. A remembered selection would have lit whichever
     chip was pressed last, which is a claim about what untouched rows will list at — and the
     pair the pipeline reads is the only thing that can answer that. */
  await open(page, {
    decisions: { rule: 'markup:100', basis: 'market', sub_threshold: null, overrides: {} },
  })

  for (const label of ['Match market', 'Market −5%', 'TCG Low −1%']) {
    await expect(page.getByRole('button', { name: label })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  }
})


// ------------------------------------------------------- the price history (D62)
//
// THE GESTURE IS THE OWNER'S, 2026-08-31, and it is one sentence: point at a row, HOLD `t`,
// and "as soon as i release it goes away". The pointer aims and the key holds. The `T`
// button's click is the other opening and the only one that outlives itself.
//
// THE PROPERTY EVERY CASE HERE PROTECTS IS THAT THE PANEL DOES NOT FIRE ON A WALK. Every
// other assertion is about what is DRAWN; that one is about what is REQUESTED, and it is the
// only one whose failure is invisible on screen — a panel that read on the pointer looks
// identical and quietly fires one request per row at a free public mirror.

const asks = (wire: Wire[]) => wire.filter((call) => call.path.includes('/history'))

const panelOf = (page: Page) =>
  page.getByRole('complementary', { name: /Price history for/ })

/** The pointer, put on something, in one call. `hover()` runs actionability checks first and
 *  these cases care about what happens BETWEEN pointer moves, so the checks are time this
 *  file cannot afford to have spent for it. */
async function point(page: Page, at: Locator) {
  const box = await at.boundingBox()
  if (box === null) throw new Error('nothing to point at')
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
}

/** POINT AT A ROW AND HOLD `t`. The whole row is the target, not the `T` button in it. */
async function hold(page: Page, at = 0) {
  await point(page, page.locator('.pricing-row').nth(at))
  await page.keyboard.down('t')
}

/** THE PIN, which is the `T` button's click and — since the key became a hold — nothing else. */
const pin = (page: Page, at = 0) =>
  page.getByRole('button', { name: /Price history for/ }).nth(at).click()

test('holding `t` over a row reads it, and draws the average as the anchor', async ({
  page,
}) => {
  const wire = await open(page)
  await hold(page)

  const panel = panelOf(page)
  await expect(panel).toBeVisible()
  await expect(panel).toContainText('$18.81')
  expect(asks(wire).map((call) => call.path)).toEqual([
    `/pipeline/runs/${RUN}/history?sku=8608859`,
  ])

  /* THE ANCHOR IS DRAWN LARGER THAN THE BOUND, AND THAT IS THE HONESTY RULE AS A
     MEASUREMENT. `pipeline/pricehistory.py` names the failure: rendering the two "as though
     they were a price and an error bar of comparable authority". A class name cannot say
     which is bigger, so this reads the computed sizes — which goes red on any restyle that
     brings them level, however the selectors are renamed. */
  const figure = await panel
    .locator('.pricehistory-figure')
    .first()
    .evaluate((node) => parseFloat(getComputedStyle(node).fontSize))
  const bound = await panel
    .locator('.pricehistory-bound')
    .first()
    .evaluate((node) => parseFloat(getComputedStyle(node).fontSize))
  expect(figure).toBeGreaterThan(bound * 2)
})

test('the release puts it away, and holding it again asks nothing', async ({ page }) => {
  /* THE COMPLAINT THIS ANSWERS, in the owner's words: "the price data is valuable but it
     persisting on my screen till i close it is annoying". */
  const wire = await open(page)
  await hold(page)
  await expect(panelOf(page)).toBeVisible()

  await page.keyboard.up('t')
  await expect(panelOf(page)).toHaveCount(0)

  /* THE READING IS KEPT BY SKU, which is what makes a gesture this cheap to repeat
     affordable. Without it, a hand resting on `t` twice would read the same card twice. */
  await page.keyboard.down('t')
  await expect(panelOf(page)).toBeVisible()
  expect(asks(wire)).toHaveLength(1)
})

test('it holds while the cursor moves, and the release lets a new row be aimed', async ({
  page,
}) => {
  /* LATCHED AT THE PRESS. Re-aiming continuously would swap the panel out from under a hand
     that is only crossing the screen to reach it — the panel is in the far corner and the
     hand passes over every row between here and there. */
  await open(page, { skus: [sku(), sku({ sku: '8608860', name: 'Zapdos' })] })
  await hold(page, 0)
  await expect(panelOf(page)).toContainText('sku 8608859')

  await point(page, page.locator('.pricing-row').nth(1))
  await expect(panelOf(page)).toContainText('sku 8608859')

  await page.keyboard.up('t')
  await expect(panelOf(page)).toHaveCount(0)

  await hold(page, 1)
  await expect(panelOf(page)).toContainText('sku 8608860')
  await page.keyboard.up('t')
})

test('pointing at a row asks for nothing — only the press does', async ({ page }) => {
  /* THE LOAD-BEARING CASE, and the reason the gesture is a KEY and not a rest of the pointer:
     a reading is a request to two public mirrors, so a pointer crossing this list on its way
     somewhere else must not spend one. */
  const wire = await open(page, { skus: [sku(), sku({ sku: '8608860', name: 'Zapdos' })] })

  await point(page, page.locator('.pricing-row').nth(0))
  await point(page, page.locator('.pricing-row').nth(1))
  await point(page, page.locator('.pricing-title'))
  await page.waitForTimeout(400)

  expect(asks(wire)).toHaveLength(0)
  await expect(panelOf(page)).toHaveCount(0)
})

test('the pointer wins over the focused row', async ({ page }) => {
  /* THE HANDS ARE IN A FIELD WHILE THE EYES ARE SOMEWHERE ELSE. The row being asked about is
     the one being pointed at, which is the whole shape of the gesture. */
  await open(page, { skus: [sku(), sku({ sku: '8608860', name: 'Zapdos' })] })
  await field(page).first().click()

  await hold(page, 1)
  await expect(panelOf(page)).toContainText('sku 8608860')
  await page.keyboard.up('t')
})

test('with nothing pointed at, the focused row answers', async ({ page }) => {
  /* THE FALLBACK, so the gesture still works with the mouse parked off the list — which is
     where it sits while both hands are pricing. */
  await open(page, { skus: [sku(), sku({ sku: '8608860', name: 'Zapdos' })] })
  await field(page).nth(1).click()
  await page.mouse.move(2, 2)

  await page.keyboard.down('t')
  await expect(panelOf(page)).toContainText('sku 8608860')
  await page.keyboard.up('t')
})

test('the `T` button pins, and a pin survives the walk', async ({ page }) => {
  /* A BINDING NOTHING ADVERTISES IS ONE ONLY THE PERSON WHO ASKED FOR IT WILL PRESS (D51), so
     the letter is on screen as a control and not only in a key handler — and since the key
     became a hold, this click is the only way to a panel that stays.

     IT DOES NOT FOLLOW FOCUS, which is what D62 closed structurally: a walk down a fifty-SKU
     list would otherwise be fifty reads at a free public mirror for readings nobody asked
     for. Two rows and two arrow presses are enough to catch it. */
  const wire = await open(page, { skus: [sku(), sku({ sku: '8608860', name: 'Zapdos' })] })
  await pin(page, 0)
  await expect(panelOf(page)).toBeVisible()
  expect(asks(wire)).toHaveLength(1)

  await field(page).first().click()
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('ArrowUp')
  expect(asks(wire)).toHaveLength(1)
  await expect(panelOf(page)).toContainText('sku 8608859')

  // And the same button closes it, which is the other half of a pin being deliberate.
  await pin(page, 0)
  await expect(panelOf(page)).toHaveCount(0)
})

test('a hold cannot spend a pin — the pinned card comes back on the release', async ({
  page,
}) => {
  /* `peek ?? pinned` RATHER THAN ONE SLOT. With one slot, a glance at another row would
     re-aim the panel the operator had deliberately left open — and since the panel prints its
     SKU, that would not read as wrong, only as no longer the card that was asked about. */
  await open(page, { skus: [sku(), sku({ sku: '8608860', name: 'Zapdos' })] })
  await pin(page, 0)
  await expect(panelOf(page)).toContainText('sku 8608859')

  await hold(page, 1)
  await expect(panelOf(page)).toContainText('sku 8608860')

  await page.keyboard.up('t')
  await expect(panelOf(page)).toContainText('sku 8608859')
  await expect(panelOf(page).getByRole('button', { name: 'Close' })).toBeVisible()
})

test('the footer says which panel it is, and `Keep open` makes a hold into a pin', async ({
  page,
}) => {
  /* THE ONLY PLACE THE TWO OPENINGS DIFFER ON SCREEN. A pin ends on a press and offers it; a
     held peek ends on the release, so what it offers instead is the way to stop that —
     reachable because the other hand is still on the mouse. */
  await open(page)
  await hold(page)
  const keep = panelOf(page).getByRole('button', { name: 'Keep open' })
  await expect(keep).toBeVisible()

  await keep.click()
  await page.keyboard.up('t')
  await expect(panelOf(page)).toBeVisible()
  await expect(panelOf(page).getByRole('button', { name: 'Close' })).toBeVisible()
})

test('losing the window mid-hold releases it', async ({ page }) => {
  /* A KEYUP THAT NEVER ARRIVES. Cmd-Tab away holding `t` and the release is delivered to
     somebody else's window — so the panel would be standing when the operator came back,
     which is exactly the state this gesture exists to prevent. */
  await open(page)
  await hold(page)
  await expect(panelOf(page)).toBeVisible()

  await page.evaluate(() => window.dispatchEvent(new Event('blur')))
  await expect(panelOf(page)).toHaveCount(0)
  await page.keyboard.up('t')
})

test('the hold panel keeps the keyboard, so `t` there is not this gesture', async ({
  page,
}) => {
  /* D49's reasons are letter keys too, and its note is a field somebody types PROSE into.
     Both are covered: the panel owns the keyboard while it is up, and a letter typed into any
     field on this screen but a price field is a character rather than a command. */
  const wire = await open(page)
  await field(page).click()
  await page.keyboard.press('h')
  await expect(page.locator('.pricing-holdpanel')).toBeVisible()

  await page.getByLabel('Note').fill('t')
  await page.keyboard.press('t')
  await expect(panelOf(page)).toHaveCount(0)
  expect(asks(wire)).toHaveLength(0)
})

test('both ranges are drawn, and the panel says they overlap', async ({ page }) => {
  await open(page)
  await hold(page)
  const panel = panelOf(page)

  /* THE MACHINE STRINGS, VERBATIM — `month` and `annual` are the endpoint's own range names
     and docs/DESIGN.md's owner-screen rule is that they are drawn rather than relabelled. */
  await expect(panel).toContainText('month')
  await expect(panel).toContainText('annual')

  /* THEY POINT OPPOSITE WAYS AND BOTH ARE DRAWN. Vilemaw's real numbers: a screen that
     merged the two ranges could not show both, and one that dropped the sentence would leave
     `+71.2%` beside `-33.9%` reading as a broken screen. */
  await expect(panel).toContainText('+71.2%')
  await expect(panel).toContainText('rising')
  await expect(panel).toContainText('-33.9%')
  await expect(panel).toContainText('falling')
  await expect(panel).toContainText(/ranges overlap/)
  await page.keyboard.up('t')
})

test('the export price is drawn beside the reading, and nothing averages them', async ({
  page,
}) => {
  await open(page)
  await hold(page)
  // D8's figure, labelled as the export's, next to the reading rather than mixed into it.
  await expect(panelOf(page)).toContainText('EXPORT MARKET')
  await expect(panelOf(page)).toContainText('$22.03')
  await page.keyboard.up('t')
})

test('a card that has never sold says so, and does not read as a failure', async ({ page }) => {
  /* THE ENDPOINT ANSWERS HTTP 200 WITH A NULL RESULT for a real, catalogued product that has
     never traded — measured on two of them — so this is not an error arm. A screen that drew
     it as one would report a join defect over a card that is merely illiquid. */
  await open(page, { history: history({ ranges: [], never_sold: true }) })
  await hold(page)
  await expect(panelOf(page)).toContainText('no recorded sales')
  await expect(panelOf(page)).toContainText(/has not traded/)
  await page.keyboard.up('t')
})

test('a refusal draws the sentence the server sent, and offers a retry', async ({ page }) => {
  /* PINNED FOR THIS ONE, AND THAT IS THE ARGUMENT FOR KEEPING A PIN AT ALL: `Try again` is a
     control, and a panel that lives as long as a key is held is not somewhere a second
     deliberate act can happen. */
  const wire = await open(page, { history: 'refuse' })
  await pin(page)
  const panel = panelOf(page)
  await expect(panel).toContainText(/not in a catalogued product line/)
  expect(asks(wire)).toHaveLength(1)

  /* THE RETRY IS THE ONLY WAY PAST THE CACHE, and a refusal is cached like a reading is —
     without that, a card whose mirror was down would re-read on every press and the panel
     would look idle while hammering a host that is already struggling. */
  await panel.getByRole('button', { name: 'Try again' }).click()
  await expect.poll(() => asks(wire).length).toBe(2)
})

test('the photograph yields to a hold and comes back, and a pin closes it', async ({ page }) => {
  /* BOTH PANELS ARE FIXED IN THE SAME CORNER — `PriceHistory.css` carries why that corner is
     the right one — so only one may be drawn. A PRESS closes the other outright; a hold only
     HIDES it, because a gesture this cheap to make must not spend anything the operator has
     to restore by hand. */
  await open(page)
  await field(page).click()
  await page.keyboard.press('p')
  await expect(page.getByRole('complementary', { name: /Photograph of/ })).toBeVisible()

  await hold(page)
  await expect(panelOf(page)).toBeVisible()
  await expect(page.getByRole('complementary', { name: /Photograph of/ })).toHaveCount(0)

  await page.keyboard.up('t')
  await expect(page.getByRole('complementary', { name: /Photograph of/ })).toBeVisible()

  await pin(page)
  await expect(page.getByRole('complementary', { name: /Photograph of/ })).toHaveCount(0)
})

test('`p` closes a pinned reading, which is the half of the exclusion that was missing', async ({
  page,
}) => {
  /* `t` cleared the photograph and `p` did not clear the history, so the two drew over each
     other in the one corner `PriceHistory.css` argues for. */
  await open(page)
  await pin(page)
  await expect(panelOf(page)).toBeVisible()

  await field(page).click()
  await page.keyboard.press('p')
  await expect(page.getByRole('complementary', { name: /Photograph of/ })).toBeVisible()
  await expect(panelOf(page)).toHaveCount(0)
})
