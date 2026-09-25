import { test, expect, type Page } from '@playwright/test'
import { sealEveryTest } from './shell'

import type { MarkdownSku } from '../src/types'

/* `#/pricing` AS A LENS OVER LIVE TCGPLAYER LISTINGS (D103): the Live tab (D277, Q6).
 *
 * ITS OWN FILE, AND `pricing.spec.ts` IS NOT TOUCHED. That suite is the gate the source seam
 * was built against: the run path had to keep passing it UNEDITED through every commit of this
 * work, which is the only thing that proves the second source cost the first one nothing. A
 * case added there would have made that claim unfalsifiable.
 *
 * THE STRONGEST CASES HERE ARE ABSENCES, which is this screen's own house style: no quantity
 * cell and no thumbnail exist in the DOM at all — not hidden, not zeroed — because a live
 * listing is not a copy in a drawer and CLAUDE.md's rule is that a control a persona may not
 * use is not focusable and not reachable by a screen reader. And the write press does not
 * EXIST until a check has answered.
 *
 * NO REAL REQUEST IS EVER MADE. The apply is recorded rather than performed, which is what
 * lets these cases assert what the screen WOULD have sent — and on this path that is the whole
 * question, because what it sends is the file that moves money at a marketplace.
 */

const STAMP = '20260906-000001'
const ROUTE = `/#/pricing?markdown=${STAMP}`
const VIEW = 'main.pricing'

type Wire = { method: string; path: string; body: unknown }

/** One live listing in the shape `cli/cmd_reprice.py:_surveyed` writes — every field, because a
 *  partial fixture here does not fail partially: the adapter reads `row['Set Name']` and the row
 *  reads `row['Number']`, so a record missing either takes the screen down and every assertion
 *  reads as "element not found", which looks exactly like an unregistered route. */
function live(over: Partial<MarkdownSku> = {}): MarkdownSku {
  const sku = over.sku ?? '8608859'
  return {
    sku,
    standing: 'offered',
    skip: null,
    name: 'Articuno - 161/159',
    condition: 'Near Mint Holofoil',
    live: 3,
    asking: '20.0000',
    market: '22.03',
    above_market: '-9',
    at_risk: '60.00',
    proposed: '18.00',
    cut: '2.00',
    given_up: '6.00',
    owned_since: '2026-08-01T00:00:00.000+00:00',
    presets: {
      market_match: '22.03',
      market_undercut_5: '20.93',
      low_undercut_1: '19.79',
    },
    listed_since: null,
    held_here: true,
    last_sold: null,
    priced_at: null,
    ...over,
    row: {
      'TCGplayer Id': sku,
      'Product Line': 'Pokemon',
      'Set Name': 'SV09: Journey Together',
      'Product Name': 'Articuno',
      Number: '161/159',
      Rarity: 'Illustration Rare',
      Condition: 'Near Mint Holofoil',
      'TCG Market Price': '22.03',
      'TCG Direct Low': '',
      'TCG Low Price With Shipping': '22.98',
      'TCG Low Price': '21.98',
      'Total Quantity': '3',
      'Add to Quantity': '0',
      'TCG Marketplace Price': '20.0000',
      'Photo URL': '',
      ...(over.row ?? {}),
    },
  }
}

async function open(
  page: Page,
  options: {
    skus?: MarkdownSku[]
    counts?: Record<string, number>
    /** What the apply route answers. A function so a case can differ between the check and
     *  the write, which is the pair this screen's two presses are about. */
    apply?: (body: Record<string, unknown>) => Record<string, unknown>
    /** What `POST /pipeline/markdowns/<stamp>/send` answers: 200 with a receipt that went
     *  live, or a refusal code. Nothing here reaches TCGplayer. */
    send?: () => { status: number; code?: string }
    /** HOLD THE SEND OPEN THIS LONG, so a case can measure the bar while the press runs
     *  (round 9, D118). */
    sendDelayMs?: number
  } = {},
): Promise<Wire[]> {
  const wire: Wire[] = []
  const skus = options.skus ?? [live()]

  await page.route(/\/pipeline\/markdowns\/[^/]+\/send$/, async (route) => {
    wire.push({ method: 'POST', path: new URL(route.request().url()).pathname, body: route.request().postDataJSON() })
    if (options.sendDelayMs !== undefined) await new Promise((r) => setTimeout(r, options.sendDelayMs))
    const answer = options.send?.() ?? { status: 200 }
    await route.fulfill({
      status: answer.status,
      contentType: 'application/json',
      body: JSON.stringify(
        answer.status === 200
          ? {
              stamp: STAMP,
              published: { upload_id: 'u-1', rows: 1, accepted: 1, messages: [], pushed_at: '2026-09-24T12:00:00+00:00', published_at: '2026-09-24T12:00:05+00:00' },
            }
          : { error: { code: answer.code ?? 'refused', message: 'The server said no.' } },
      ),
    })
  })

  await page.route(/\/pipeline\/markdowns\/[^/]+\/apply$/, async (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>
    wire.push({ method: 'POST', path: new URL(route.request().url()).pathname, body })
    const answer = options.apply?.(body) ?? {
      ok: true,
      exit_code: 0,
      wrote: Boolean(body.write),
      console: body.write === true ? 'wrote import.csv' : 'DRY RUN — nothing written.',
      stamp: STAMP,
      revision: 'rev-after',
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(answer) })
  })

  await page.route(/\/pipeline\/markdowns\/[^/]+\/trends/, async (route) => {
    const url = new URL(route.request().url())
    /* THE QUERY VERBATIM, because `sku` REPEATS on this route rather than carrying a comma
       list. The count of those repeats is the assertion that the press is scoped to the
       filter, which is what keeps a 441-row survey from being a five-minute walk. */
    wire.push({ method: 'GET', path: `${url.pathname}${url.search}`, body: null })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ markdown: STAMP, asked: 0, skipped: 0, skus: {}, refused: {} }),
    })
  })

  await page.route(/\/pipeline\/markdowns\/[^/]+\/table$/, async (route) => {
    wire.push({ method: 'GET', path: new URL(route.request().url()).pathname, body: null })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        stamp: STAMP,
        at: '2026-09-06T00:00:00.000+00:00',
        asked: { days: 7, rule: 'undercut:10' },
        counts: options.counts ?? { considered: skus.length, offered: 1, deferred: 0, refused: 0 },
        source: {},
        skus,
        says: { too_young: 'owned for less than the window', sold_out: 'TCGplayer holds no copies' },
        unpriceable: ['not_this_store', 'sold_out'],
        /* THE SAME FIGURE AS `policy.threshold` BELOW, because the server cannot send anything
           else (D9, amended 2026-09-09): the cut-off IS the floor, and `do_markdown_table` reads
           one key for both. This said '0.40' beside a threshold of '0.49' — a wire shape that had
           stopped being producible, which is the way a stub quietly stops testing the product. */
        floor: '0.49',
      }),
    })
  })

  await page.route(/\/pricing$/, async (route) => {
    if (route.request().method() === 'PUT') {
      wire.push({ method: 'PUT', path: '/pricing', body: route.request().postDataJSON() })
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, written: '/tmp/prices.json', answers: 1, revision: 'rev-2' }),
      })
    }
    wire.push({ method: 'GET', path: '/pricing', body: null })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        corpus: {
          version: 1,
          policy: { rule: 'match', basis: 'market', sub_threshold: { flat: '0.49' }, threshold: '0.49' },
          skus: {},
        },
        path: '/tmp/prices.json',
        revision: 'rev-1',
      }),
    })
  })

  /* THE LIVE TAB READS THE LIST OF READS (D277, Q6): it names the newest one on its line. */
  await page.route(/\/pipeline\/markdowns$/, async (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        markdowns: [{ stamp: STAMP, at: '2026-09-06T00:00:00.000+00:00', asked: { days: 7, percent: '10' }, source: null, skus: skus.length, files: [] }],
      }),
    }),
  )

  await page.route(/\/pipeline\/runs$/, async (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ runs: [] }) }),
  )

  await page.goto(ROUTE)
  await page.locator(VIEW).waitFor()
  await page.locator('.pricing-row').first().waitFor()
  return wire
}

sealEveryTest()

test('the lens draws every live listing the survey saw, and no run-shaped cell exists at all', async ({
  page,
}) => {
  await open(page, {
    skus: [live(), live({ sku: '8608464', name: 'Dunsparce', standing: 'deferred', asking: '5.0000' })],
    counts: { considered: 2, offered: 1, deferred: 1, refused: 0 },
  })

  await expect(page.locator('.pricing-row')).toHaveCount(2)

  /* THE TWO ABSENCES. A live listing is not a copy this store holds — it may never have held
     it at all — so there is no photograph to draw and no quantity going into a file. NOT
     HIDDEN: `toHaveCount(0)` is out of the accessibility tree, which is what CLAUDE.md's rule
     asks for and what `display: none` would not give. */
  await expect(page.locator('.pricing-thumb')).toHaveCount(0)
  await expect(page.locator('.pricing-qty')).toHaveCount(0)
  await expect(page.locator('.pricing-caption .pricing-col-qty')).toHaveCount(0)

  /* AND THE GRID FOLLOWS: the list says it holds no copies, and the caption and the rows share
     one template, so a cell removed from one and not the other would shear every column. */
  await expect(page.locator('.pricing-list')).toHaveAttribute('data-copies', 'none')
  const [row, caption] = await Promise.all([
    page.locator('.pricing-row').first().evaluate((el) => getComputedStyle(el).gridTemplateColumns),
    page.locator('.pricing-caption').first().evaluate((el) => getComputedStyle(el).gridTemplateColumns),
  ])
  expect(row).toBe(caption)

  await expect(page.locator(`${VIEW} .pricing-caption .pricing-col-price`)).toHaveText('New price')
})

/* NO TYPED MIDDLE DOT OR BULLET REACHES THE LENS (D218). `Live listings, read <date>` and the
 * meta row's condition/set/number join are the same components `pricing.spec.ts` covers, drawn
 * here over the markdown SOURCE rather than a run — the separator is CSS either way. */
test('no typed middle dot or bullet reaches the pricing lens (D218)', async ({ page }) => {
  await open(page, {
    skus: [live(), live({ sku: '8608464', name: 'Dunsparce', standing: 'deferred', asking: '5.0000' })],
    counts: { considered: 2, offered: 1, deferred: 1, refused: 0 },
  })
  await expect(page.locator('.pricing-row')).toHaveCount(2)

  const text = await page.locator(VIEW).innerText()
  expect(text).not.toMatch(/[·•]/)
})

test('a live count is drawn and it is TCGplayer’s own, never a copy count', async ({ page }) => {
  await open(page, { skus: [live({ live: 4 })] })
  await expect(page.locator('.pricing-row .pricing-live')).toContainText('4')
})

test('staleness is a filter and All is the default, which is the whole of the lens', async ({
  page,
}) => {
  /* THE OWNER'S RULING, AND THE MEASUREMENT BEHIND IT: on their own export a seven-day gate
     selects 109 of 441 rows and a ten-day gate selects NONE, because the oldest capture in the
     store is nine days old. A gate hands back an empty screen for a reason about the store's
     age rather than about the listings, so the terms narrow what is already loaded instead. */
  await open(page, {
    skus: [
      live(),
      live({ sku: '8608464', name: 'Dunsparce', standing: 'refused', skip: 'too_young' }),
    ],
    counts: { considered: 2, offered: 1, deferred: 0, refused: 1 },
  })

  await expect(page.locator('.pricing-row')).toHaveCount(2)
  await page.getByRole('button', { name: /Not selling/ }).click()
  await expect(page.locator('.pricing-row')).toHaveCount(1)
  await expect(page.locator('.pricing-name').first()).toContainText('Articuno')

  await page.getByRole('button', { name: /^All/ }).click()
  await expect(page.locator('.pricing-row')).toHaveCount(2)
})

test('the trends press asks about the rows on screen, not about the whole survey', async ({
  page,
}) => {
  const wire = await open(page, {
    skus: [
      live(),
      live({ sku: '8608464', name: 'Dunsparce', standing: 'refused', skip: 'too_young' }),
    ],
    counts: { considered: 2, offered: 1, deferred: 0, refused: 1 },
  })

  await page.getByRole('button', { name: /Not selling/ }).click()
  await page.getByRole('button', { name: 'Load trends' }).click()
  await expect.poll(() => wire.filter((row) => row.path.includes('/trends')).length).toBeGreaterThan(0)

  const asked = wire
    .filter((row) => row.path.includes('/trends'))
    .flatMap((row) => new URLSearchParams(row.path.split('?')[1] ?? '').getAll('sku'))
  /* ONE SKU AND NOT TWO. The run route measured 46 SKUs at ~34s of courtesy delay; a real
     survey is ~441 rows, about five and a half minutes at a free public mirror. D62's rule is
     that this is a PRESS, and a walk that big would make the press meaningless. */
  expect(asked).toEqual(['8608859'])
})

test('a raise is named on the row and sent, not refused', async ({ page }) => {
  await open(page)

  /* THIS CASE OUTLIVED THE RULE IT WAS WRITTEN FOR, AND THE TITLE HAD TO MOVE WITH IT (D107).
     It read "a raise is refused on the row, before the press rather than by it", because
     `Application.fatal` used to refuse the whole file over one raised row. The owner asked for
     raises; the refusal is gone and the LABEL is not — the rule only ever proposes a cut, so a
     row pointing up is one a person typed, and inside a screen called a markdown that is the
     row most worth a second look. What changed is that it is a notice rather than a warning of
     a refusal to come. */
  const field = page.locator('.pricing-input').first()
  await field.click()
  await field.fill('')
  await field.type('25.00')
  await field.blur()
  await expect(page.locator('.pricing-state').first()).toHaveText('Above the live price')

  /* NO REFUSAL IS PROMISED ANYWHERE: the raise is sent as typed (D107). */
  await expect(page.locator(VIEW)).not.toContainText('only lowers')
  await expect(page.locator(VIEW)).not.toContainText('refuses the whole upload')

  await field.click()
  await field.fill('')
  await field.type('17.50')
  await field.blur()
  await expect(page.locator('.pricing-state').first()).toHaveText('Down from $20.00')
})

test('the press sends only the rows a hand priced, and carries the revision it read', async ({
  page,
}) => {
  const wire = await open(page, {
    skus: [live(), live({ sku: '8608464', name: 'Dunsparce', asking: '5.0000' })],
  })

  const field = page.locator('.pricing-input').first()
  await field.click()
  await field.fill('')
  await field.type('17.50')
  await field.blur()
  await expect.poll(() => wire.filter((row) => row.method === 'PUT').length).toBeGreaterThan(0)

  await page.getByRole('button', { name: 'Send 1 price to TCGplayer' }).click()
  await expect.poll(() => wire.filter((row) => row.path.includes('/apply')).length).toBe(1)

  const sent = wire.find((row) => row.path.includes('/apply'))?.body as Record<string, unknown>
  /* ONE ROW, NOT TWO. The untouched listing is simply absent, which `read_back` reports as
     `dropped` — "left alone, which is what deleting a line means". */
  expect(sent.edits).toEqual([{ sku: '8608859', price: '17.50' }])
  expect(sent.write).toBe(true)
  /* AND NO `worklist`. This client writes no CSV — `app/package.json` carries two runtime
     dependencies and PapaParse is not one — so the pairs go as JSON and the ROUTE materialises
     them with the repo's own writer. */
  expect(sent.worklist).toBeUndefined()
  /* THE DIGEST TRAVELS, because `apply --write` writes the corpus from a subprocess and would
     otherwise refuse a screen that is already current. */
  expect(typeof sent.revision).toBe('string')
})

test('one press writes the file, sends it and makes it live', async ({ page }) => {
  const wire = await open(page)

  const field = page.locator('.pricing-input').first()
  await field.click()
  await field.fill('')
  await field.type('17.50')
  await field.blur()

  /* ONE PRESS (`D273`, Q7): the file is written, then the server
     reads what is live, sends it and makes it live. No check press and no second press. */
  await expect(page.getByRole('button', { name: 'Check these prices' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Send 1 price to TCGplayer' }).click()
  await expect.poll(() => wire.filter((row) => row.path.endsWith('/send')).length).toBe(1)
  const order = wire.filter((row) => row.path.includes('/apply') || row.path.endsWith('/send')).map((row) => row.path.split('/').pop())
  expect(order).toEqual(['apply', 'send'])
  expect(wire.find((row) => row.path.endsWith('/send'))?.body).toEqual({ confirm: true })
})

test('Download the file instead writes it and sends nothing', async ({ page }) => {
  const wire = await open(page)
  const field = page.locator('.pricing-input').first()
  await field.click()
  await field.fill('')
  await field.type('17.50')
  await field.blur()

  await page.getByRole('button', { name: 'Download the file instead' }).click()
  await expect(page.getByRole('link', { name: 'import.csv' })).toHaveCount(1)
  expect(wire.filter((row) => row.path.endsWith('/send'))).toHaveLength(0)
})

test('a refused write sends nothing and says so', async ({ page }) => {
  const wire = await open(page, {
    apply: () => ({
      ok: false,
      exit_code: 1,
      wrote: false,
      console: 'REFUSED — the whole file, not the row:\n  8608859 above the live price',
      stamp: STAMP,
      revision: 'rev-after',
    }),
  })

  const field = page.locator('.pricing-input').first()
  await field.click()
  await field.fill('')
  await field.type('17.50')
  await field.blur()
  await page.getByRole('button', { name: 'Send 1 price to TCGplayer' }).click()

  await expect(page.getByRole('region', { name: 'Send these prices' })).toContainText('These prices could not be written, so nothing was sent.')
  expect(wire.filter((row) => row.path.endsWith('/send'))).toHaveLength(0)
})

test('a send the live read refuses says nothing changed, and offers Try again', async ({ page }) => {
  await open(page, { send: () => ({ status: 502, code: 'live_check_failed' }) })
  const field = page.locator('.pricing-input').first()
  await field.click()
  await field.fill('')
  await field.type('17.50')
  await field.blur()
  await page.getByRole('button', { name: 'Send 1 price to TCGplayer' }).click()
  await expect(page.getByText('Nothing was sent. The prices at TCGplayer did not change.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Try again' })).toHaveCount(1)
})

test('the cut-off is the run\'s own control, and on a lens it is spent by a press', async ({
  page,
}) => {
  /* D103 AMENDED. The cut-off was drawn on the run door only, because "it decides which import
     file a row is bound for and a live listing is bound for none" — right about the FILE and
     wrong about the FIGURE, which D99 made one variable with the cheap price. So the same
     panel, the same `policy.threshold` and the same `bucketAt` partition serve both doors, and
     the ONLY difference is when the figure is spent: `emit` prices a run's cheap half at write
     time, and a lens has no emit, so a press writes real answers. */
  await open(page, {
    skus: [
      live({ sku: '8608859', name: 'Articuno', market: '22.03' }),
      live({ sku: '8608464', name: 'Dunsparce', market: '0.20' }),
    ],
    counts: { considered: 2, offered: 2, deferred: 0, refused: 0 },
  })

  /* THE PRESS LIVES IN THE LIVE TAB'S ONE SHEET (D277, Q5 and Q6). No run's own cut-off is
     offered here: a lens is not a lot, so there is no run to give one (D101). */
  await page.getByRole('button', { name: 'Change' }).click()
  const sheet = page.getByRole('dialog', { name: 'What to mark down' })
  await expect(sheet.getByRole('button', { name: 'Give this run its own cut-off' })).toHaveCount(0)

  const press = sheet.getByRole('button', { name: /at the cut-off/ })
  await expect(press).toHaveText('Price 1 at the cut-off')

  /* ADDRESSED BY CARD AND NEVER BY INDEX: the cut-off MOVES a row between the sections, which
     is the whole point of the partition, so an index here would assert against wherever the
     row happened to land. */
  const cheap = page.getByRole('textbox', { name: 'Price for Dunsparce' })
  const dear = page.getByRole('textbox', { name: 'Price for Articuno' })

  await press.click()
  /* ONE ROW, AND IT IS THE ONE UNDER THE LINE. The $22.03 row is above the cut-off and must be
     untouched: a press that priced the whole book would be a bulk write nobody asked for. */
  await expect(cheap).toHaveValue('0.49')
  await expect(dear).toHaveValue('')
  await expect(press).toHaveText('Price 0 at the cut-off')
  await expect(press).toBeDisabled()

  /* ONE ACT, ONE REVERSAL, on the receipt. The per-SKU undo stack is ten deep (D28), so a press
     moving ninety rows could not be undone through it at all. */
  await sheet.getByRole('button', { name: 'Close' }).click()
  await page.locator('.bn-toasts').getByRole('button', { name: 'Undo' }).click()
  await expect(cheap).toHaveValue('')
})

test('an untouched lens field ghosts the price the listing is live at', async ({ page }) => {
  /* THE OPERATOR'S ASK: the current price in faint gray, replaced whole by the first digit
     typed. A PLACEHOLDER and not a value, so there is nothing to select and nothing to
     backspace — and nothing is written by looking at it. */
  await open(page, { skus: [live({ sku: '8608859', asking: '20.0000' })] })
  const field = page.locator('.pricing-input').first()
  await expect(field).toHaveValue('')
  await expect(field).toHaveAttribute('placeholder', '20.0000')
})

test('a preset writes answers on a lens, and never the standing rule', async ({ page }) => {
  /* THE DEFECT THIS PINS, MEASURED ON THE OWNER'S OWN STORE 2026-09-07. A lens row carried
     `presets: {}`, so pressing `Market −5%` filled NOTHING — and still wrote `policy.rule` to
     `inventory/prices.json`, which is the store-wide setting every future joined run lists by.
     Both halves were wrong and the wrong one was the one that persisted: repricing a live book
     silently repriced the next box out of the camera.

     A RUN AND A LENS NEED OPPOSITE THINGS FROM ONE PRESS. `emit` prices a run's unanswered
     rows BY the standing rule at write time, so a run writes the rule and no per-SKU answer —
     writing 300 answers there would freeze a rule into figures (D54's staleness). A lens has
     no emit: `reprice apply` sends typed answers and nothing else, so the press must write
     answers and must not touch the rule. */
  const wire = await open(page, {
    skus: [
      live({ sku: '8608859', name: 'Articuno' }),
      live({ sku: '8608464', name: 'Dunsparce', presets: { market_match: '2.06', market_undercut_5: '1.96', low_undercut_1: null } }),
    ],
    counts: { considered: 2, offered: 2, deferred: 0, refused: 0 },
  })

  await page.getByRole('button', { name: 'Change' }).click()
  await page.getByRole('dialog', { name: 'What to mark down' }).getByRole('button', { name: 'Market −5%' }).click()
  await page.getByRole('dialog', { name: 'What to mark down' }).getByRole('button', { name: 'Close' }).click()

  /* BOTH ROWS TAKE THE PRESET'S OWN FIGURE — server-priced, so the client performs no
     arithmetic on money and the two doors cannot compute a different number for one card. */
  await expect(page.getByRole('textbox', { name: 'Price for Articuno' })).toHaveValue('20.93')
  await expect(page.getByRole('textbox', { name: 'Price for Dunsparce' })).toHaveValue('1.96')

  /* AND THE STORE'S STANDING RULE IS UNTOUCHED. This is the half that persisted past the
     screen, so it is asserted over the bytes rather than over what is drawn. */
  const writes = wire.filter((row) => row.method === 'PUT' && row.path === '/pricing')
  expect(writes.length).toBeGreaterThan(0)
  for (const write of writes) {
    const policy = (write.body as { policy?: Record<string, unknown> })?.policy ?? {}
    expect(policy.rule ?? 'match').toBe('match')
  }

  /* ONE ACT, ONE REVERSAL — the per-SKU undo stack is ten deep (D28) and a press over a real
     book moves hundreds. The receipt carries it. */
  await page.locator('.bn-toasts').getByRole('button', { name: 'Undo' }).click()
  await expect(page.getByRole('textbox', { name: 'Price for Articuno' })).toHaveValue('')
  await expect(page.getByRole('textbox', { name: 'Price for Dunsparce' })).toHaveValue('')
})

test('a preset leaves a row it cannot price, and says how many', async ({ page }) => {
  /* `null` IS A REAL ANSWER: 394 of 2,476 rows on the wide Pokemon export carry a blank
     `TCG Low Price`, so a Low-based preset has nothing to price them from. The screen prices
     what it can and names the rest rather than writing a row with no price. */
  await open(page, {
    skus: [
      live({ sku: '8608859', name: 'Articuno', presets: { market_match: '22.03', market_undercut_5: '20.93', low_undercut_1: null } }),
      live({ sku: '8608464', name: 'Dunsparce', presets: { market_match: '2.06', market_undercut_5: '1.96', low_undercut_1: '1.90' } }),
    ],
    counts: { considered: 2, offered: 2, deferred: 0, refused: 0 },
  })

  await page.getByRole('button', { name: 'Change' }).click()
  await page.getByRole('dialog', { name: 'What to mark down' }).getByRole('button', { name: 'TCG Low −1%' }).click()
  await page.getByRole('dialog', { name: 'What to mark down' }).getByRole('button', { name: 'Close' }).click()
  await expect(page.getByRole('textbox', { name: 'Price for Dunsparce' })).toHaveValue('1.90')
  await expect(page.getByRole('textbox', { name: 'Price for Articuno' })).toHaveValue('')
})

test('neither run ship bar is drawn on a lens', async ({ page }) => {
  await open(page)
  /* BY CONSTRUCTION RATHER THAN BY CARE: `loaded` derives from `work.runs`, which a lens never
     fetches, so both run bars hide themselves with no edit. Asserted because "the run path is
     untouched" is the claim this whole build rests on. */
  await expect(page.getByRole('region', { name: 'Ship these runs' })).toHaveCount(0)
  await expect(page.getByRole('region', { name: 'Send these prices' })).toHaveCount(1)
  await expect(page.getByRole('region', { name: 'Send to TCGplayer' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /Write the import file/ })).toHaveCount(0)
})

/* ---- UX-002, THE LENS'S OWN THIRD GRID AXIS: `data-copies='none'` --------------------------------
 *
 * `Pricing.css`'s `--pricing-cols` templates are shared with `pricing.spec.ts`'s run path, and
 * `data-copies='none'` is the one variant only this screen ever draws — a live listing carries no
 * thumbnail and no quantity cell (see this file's own header), so the section drops those two
 * tracks. TWO SEPARATE BUGS lived in that variant, at two tiers, and this file is the only one
 * that can catch either: the table tier's `--pricing-cols` still ended in the same `132px 68px`
 * pair UX-002's anchor fixed for every source, but the COMPACT tier (600-939px) hard-coded
 * `.pricing-price { grid-column: 3 }` / `.pricing-actions { grid-column: 4 }` against the
 * FOUR-track `data-copies='some'` template, and never noticed the three-track `none` one two
 * lines above it — price landed in the actions track, actions fell into an implicit fourth
 * column the template never declared, and the row grew past its own container by about the
 * width of a price field. Fixed the same way UX-002 was: anchored to the grid's last two
 * lines, which both templates share.
 */

const LONG_PRICE = '1234.56'

/** No horizontal clipping — the same measurement `pricing.spec.ts`'s own `legible()` makes,
 *  duplicated rather than imported: this file's own header states its independence from that
 *  suite on purpose. */
async function legible(page: Page, name: string): Promise<void> {
  const clipped = await page
    .getByRole('textbox', { name })
    .evaluate((el: HTMLInputElement) => el.scrollWidth > el.clientWidth + 1)
  expect(clipped, `the ${name} field clips its own value`).toBe(false)
}

test('the row and caption tracks agree at the table tier, and the price is not clipped (data-copies=none)', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await open(page)
  await expect(page.locator(VIEW)).toBeVisible()
  await expect(page.locator('.pricing-list')).toHaveAttribute('data-copies', 'none')
  await expect(page.locator('.pricing-thumb')).toHaveCount(0) // the absence this screen's own header states

  const [row, caption] = await Promise.all([
    page.locator('.pricing-row').first().evaluate((el) => getComputedStyle(el).gridTemplateColumns),
    page.locator('.pricing-caption').first().evaluate((el) => getComputedStyle(el).gridTemplateColumns),
  ])
  expect(row, `row tracks "${row}" disagree with caption tracks "${caption}"`).toBe(caption)

  const field = page.getByRole('textbox', { name: 'Price for Articuno' })
  await field.click()
  await field.fill(LONG_PRICE)
  await expect(field).toHaveValue(LONG_PRICE)
  await legible(page, 'Price for Articuno')
})

test('at 700 the row and caption tracks still agree, and the price is not clipped (data-copies=none)', async ({
  page,
}) => {
  /* 700 IS THE OWNER'S HALF-SCREEN DESK (D197's 720 width, minus a scrollbar): the column is
     under the 900px step, so Lowest and the trend leave the row, and both the caption and the
     rows drop them together. */
  await page.setViewportSize({ width: 700, height: 900 })
  await open(page)
  await expect(page.locator('.pricing-list')).toHaveAttribute('data-copies', 'none')
  await expect(page.locator('.pricing-caption .pricing-col-low')).toBeHidden()
  const [row, caption] = await Promise.all([
    page.locator('.pricing-row').first().evaluate((el) => getComputedStyle(el).gridTemplateColumns),
    page.locator('.pricing-caption').first().evaluate((el) => getComputedStyle(el).gridTemplateColumns),
  ])
  expect(row, `row tracks "${row}" disagree with caption tracks "${caption}"`).toBe(caption)

  const field = page.getByRole('textbox', { name: 'Price for Articuno' })
  await field.click()
  await field.fill(LONG_PRICE)
  await expect(field).toHaveValue(LONG_PRICE)
  await legible(page, 'Price for Articuno')
})

async function boxesOf(locators: Record<string, import('@playwright/test').Locator>) {
  const out: Record<string, { x: number; y: number; width: number; height: number } | null> = {}
  /* A SHORT WAIT, AND GONE IS NULL: an element that vanished during the press is the finding,
     never a timeout. */
  for (const [key, locator] of Object.entries(locators)) {
    out[key] = await locator.boundingBox({ timeout: 1000 }).catch(() => null)
  }
  return out
}

function expectStill(
  before: Record<string, { x: number; y: number; width: number; height: number } | null>,
  during: Record<string, { x: number; y: number; width: number; height: number } | null>,
) {
  for (const key of Object.keys(before)) {
    const a = before[key]
    const b = during[key]
    expect(b, `${key} is drawn during the press`).not.toBeNull()
    for (const side of ['x', 'y', 'width', 'height'] as const) {
      expect(Math.abs((b?.[side] ?? 0) - (a?.[side] ?? 0)), `${key} ${side}`).toBeLessThanOrEqual(0.5)
    }
  }
}

/* ROUND 9, D118: A PRESS CHANGES WHAT IS ON THE SCREEN, NEVER WHERE THE REST OF IT IS. The lens's
   press read "Send 1 price to TCGplayer" and became "Checking TCGplayer, then sending…" while it
   ran, so it changed its size under the finger and moved the door beside it. Measured before and
   during a press held open. */
for (const width of [390, 820]) {
  test(`r9: the lens press keeps its place and size while it runs (${width})`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    const wire = await open(page, { sendDelayMs: 1500 })
    const field = page.locator('.pricing-input').first()
    await field.click()
    await field.fill('')
    await field.type('17.50')
    await field.blur()
    const bar = page.getByRole('region', { name: 'Send these prices' })
    await expect(bar.getByRole('button', { name: 'Send 1 price to TCGplayer' })).toBeVisible()
    /* BY ITS PLACE AND NOT ITS NAME: the name is what changed under the finger. */
    const press = bar.locator('.pricing-emit')
    const locators = { press, door: bar.getByRole('button', { name: /Download/ }) }
    const before = await boxesOf(locators)
    await press.click()
    await expect.poll(() => wire.filter((row) => row.path.endsWith('/send')).length).toBe(1)
    await expect(press).toHaveAttribute('data-busy', 'true')
    expectStill(before, await boxesOf(locators))
  })
}

/* ROUND 9, R9-1: THE FILE'S LINK ALREADY ON SCREEN STAYS THROUGH THE PRESS. "Download the file
   instead" first puts the link beside the press; the link used to vanish when Send started, and
   the bar, set to the right, moved the press under the finger. */
for (const width of [390, 820]) {
  test(`r9: a file link already on screen holds its place through the send (${width})`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    const wire = await open(page, { sendDelayMs: 1500 })
    const field = page.locator('.pricing-input').first()
    await field.click()
    await field.fill('')
    await field.type('17.50')
    await field.blur()
    const bar = page.getByRole('region', { name: 'Send these prices' })
    await bar.getByRole('button', { name: 'Download the file instead' }).click()
    await expect(bar.getByRole('link', { name: 'import.csv' })).toBeVisible()
    const press = bar.locator('.pricing-emit')
    const locators = { press, door: bar.getByRole('button', { name: /Download/ }), link: bar.getByRole('link', { name: 'import.csv' }) }
    const before = await boxesOf(locators)
    await press.click()
    await expect.poll(() => wire.filter((row) => row.path.endsWith('/send')).length).toBe(1)
    await expect(press).toHaveAttribute('data-busy', 'true')
    expectStill(before, await boxesOf(locators))
  })
}


/* THE LIVE TAB (D277, Q6): the Mark-down sheet is gone, and the lens is a tab on Pricing. */

test('the Live tab with no read yet says so and offers the read, and nothing is fetched by itself', async ({ page }) => {
  const wire: Wire[] = []
  await page.route(/\/pipeline\/markdowns$/, async (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ markdowns: [] }) }),
  )
  await page.route(/\/pipeline\/live-export$/, async (route) => {
    wire.push({ method: 'POST', path: '/pipeline/live-export', body: null })
    await route.fulfill({ status: 409, contentType: 'application/json', body: '{"error":{"code":"tcg_cookie_missing","message":"No session."}}' })
  })
  await page.route(/\/pipeline\/runs$/, async (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ runs: [] }) }),
  )
  await page.goto('/#/pricing?live')
  await expect(page.getByText('Nothing read from TCGplayer yet').first()).toBeVisible()
  await expect(page.getByRole('button', { name: 'Live' })).toHaveAttribute('aria-pressed', 'true')
  /* THE READ IS A PRESS (D62's rule for anything that asks a remote host): opening the tab
     asks TCGplayer for nothing. */
  expect(wire).toHaveLength(0)
  await page.getByRole('button', { name: 'Read what is live' }).first().click()
  await expect(page.getByRole('dialog', { name: 'What to mark down' })).toBeVisible()
  expect(wire).toHaveLength(0)
})

test('the Live tab opens the newest read, and its line says how the read was taken', async ({ page }) => {
  await open(page)
  await page.goto('/#/pricing?live')
  /* THE TAB WITH NO STAMP LANDS ON THE NEWEST READ, which is the only one `open` lists. */
  await expect(page).toHaveURL(new RegExp(`markdown=${STAMP}`))
  await expect(page.locator('.pricing-rule-line')).toContainText('Not sold in 7 days, 10% under your asking price')
})

test('Read again keeps its words and its place while it reads', async ({ page }) => {
  await page.route(/\/pipeline\/live-export$/, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1500))
    await route.fulfill({ status: 409, contentType: 'application/json', body: '{"error":{"code":"tcg_cookie_missing","message":"No session."}}' })
  })
  await open(page)
  const press = page.getByRole('button', { name: 'Read again' })
  const before = await press.boundingBox()
  await press.click()
  await expect(press).toHaveAttribute('data-busy', 'true')
  await expect(press).toHaveText('Read again')
  const during = await press.boundingBox()
  for (const side of ['x', 'y', 'width', 'height'] as const) {
    expect(Math.abs((during?.[side] ?? 0) - (before?.[side] ?? 0)), side).toBeLessThanOrEqual(0.5)
  }
})

test('the Live tab’s Download keeps its words and its place while it writes', async ({ page }) => {
  await page.route(/\/pipeline\/markdowns\/[^/]+\/apply$/, async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1500))
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, exit_code: 0, wrote: true, console: 'wrote import.csv', stamp: STAMP, revision: 'rev-after' }),
    })
  })
  await open(page)
  const field = page.locator('.pricing-input').first()
  await field.click()
  await field.fill('')
  await field.type('17.50')
  await field.blur()
  const press = page.getByRole('region', { name: 'Send these prices' }).getByRole('button', { name: /^Download/ })
  await expect(press).toBeEnabled()
  const before = await press.boundingBox()
  await press.click()
  await expect(press).toHaveAttribute('data-busy', 'true')
  await expect(press).not.toContainText('Writing')
  const during = await press.boundingBox()
  for (const side of ['x', 'y', 'width', 'height'] as const) {
    expect(Math.abs((during?.[side] ?? 0) - (before?.[side] ?? 0)), side).toBeLessThanOrEqual(0.5)
  }
})
