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
  options: { skus?: unknown[]; decisions?: Record<string, unknown> | null } = {},
): Promise<Wire[]> {
  const wire: Wire[] = []

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
