import { test, expect, type Page } from '@playwright/test'

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
 *  unregistered route. */
function sku(over: Record<string, unknown> = {}) {
  const base = {
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
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        runs: [
          {
            run: RUN,
            path: `/tmp/runs/${RUN}`,
            live: false,
            phase: 'emit',
            joined: true,
            collected: true,
            counts: { skus: 1, cards_in: 3, queued_main: 0, queued_parked: 0 },
            batch_ids: [],
            usage: {},
          },
        ],
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

  await page.goto(VIEW_ROUTE)
  await expect(page.locator(VIEW)).toBeVisible()
  return wire
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
    skus: [sku({ bucket: 'sub_threshold', market: '0.12' })],
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
     the run report at once — which is the only job that line has. */
  await expect(page.locator('.pricing-held .pricing-machine')).toHaveText('withheld: bullish')
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

test('a row is the same height whether or not it carries a note', async ({ page }) => {
  await open(page, {
    skus: [sku(), sku({ sku: '8608459', name: 'Dunsparce', at_cap: true, add_to_quantity: 0 })],
  })

  /* D28's other half — the list must not move under a finger. The note lands in a second grid
     row that every zone but the card leaves empty by construction, so a row that acquires a
     sentence costs no height and a hundred-row list cannot reflow when one does. */
  const rows = page.locator('.pricing-row')
  await expect(rows.nth(1).locator('.pricing-row-note')).toBeVisible()
  const heights = await rows.evaluateAll((nodes) =>
    nodes.map((node) => Math.round(node.getBoundingClientRect().height)),
  )
  expect(heights[0]).toBe(heights[1])
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
