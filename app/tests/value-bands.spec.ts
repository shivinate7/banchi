import { test, expect, type Page } from '@playwright/test'
import { sealEveryTest } from './shell'

import type { ValueBox, ValueCopy, ValueTable } from '../src/types'

/* `#/pricing?band=…` — WHAT IS WORTH PULLING (D159).
 *
 * ITS OWN FILE, AND `pricing.spec.ts` IS NOT TOUCHED — `pricing-markdown.spec.ts`'s rule for
 * the other lens on this screen, and for its reason: the worklist suite is the gate that proves
 * a second lens cost the first one nothing, and a case added there would make that claim
 * unfalsifiable.
 *
 * EVERY FIXTURE HERE IS A SHAPE THE OWNER'S STORE ACTUALLY HAS, which is why the numbers look
 * odd for a fixture. One SKU in three slots is Rengar, Trophy Hunter. A drawer that is bulk
 * except for two cards is box 2. A drawer whose every priced card is cheap and which still has
 * unread cards in it is box 5 — and that last one is the case the verdict pill is suppressed
 * for, which no rounder fixture contains.
 *
 * THE STRONGEST CASES HERE ARE ABOUT WHAT IS NOT RANKED. 390 of 2,245 cards on that store carry
 * no market price, and a screen that quietly left 17% of the store out of a ranking would be
 * the silent drop this repo forbids by name. Three cases below are about those rows and none of
 * them can pass by drawing a zero.
 */

const VIEW = 'main.value-page'

function copy(over: Partial<ValueCopy> = {}): ValueCopy {
  const box = over.box ?? 4
  const index = over.index ?? 1
  return {
    box,
    index,
    label: `Box ${box} · Section 1 · Card ${index}`,
    sku: '9027460',
    name: 'Last Rites',
    set_name: 'Spiritforged',
    condition: 'Near Mint Foil',
    game: 'riftbound',
    state: 'identified',
    market: '47.57',
    answer: null,
    live: 0,
    read_at: 1789100000,
    source: '2026-09-11-box4-04',
    why: null,
    ...over,
  }
}

function drawer(over: Partial<ValueBox> = {}): ValueBox {
  return {
    box: 4,
    name: 'WB1 R2',
    cards: 3,
    valued: 3,
    unpriced: 0,
    under_cutoff: 0,
    at_or_over: 3,
    total: '142.71',
    per_card: '47.57',
    top: '47.57',
    ...over,
  }
}

/* `totals` alone accepts a PARTIAL override — `under_cutoff`/`at_or_over` (store-scaling item
 * 7) default to 0 so none of this file's existing `totals: {...}` fixtures need updating; a
 * case that cares about either figure sets it explicitly, same as any other field here. */
type TableOverride = Omit<Partial<ValueTable>, 'totals'> & { totals?: Partial<ValueTable['totals']> }

function table(over: TableOverride = {}): ValueTable {
  const { totals: totalsOver, ...rest } = over
  return {
    at: '2026-09-12T00:00:00.000+00:00',
    basis: 'market',
    threshold: '0.29',
    sources: [
      { kind: 'run', name: '2026-09-11-box4-04', at: 1789153374, skus: 129 },
      { kind: 'live', name: 'live-tcgplayer-20260910-034806.csv', at: 1789055286, skus: 774 },
    ],
    copies: [],
    boxes: [],
    unrankable: { total: 0, never_identified: 0, read_nothing: 0, no_reading: 0, by_box: {} },
    totals: { cards: 0, valued: 0, value: '0.00', under_cutoff: 0, at_or_over: 0, ...totalsOver },
    ...rest,
  } as ValueTable
}

/** A row's position in the SAME sort order the server's `_value_sort_key` produces — a literal
 *  TypeScript port of `server/pipeline_routes.py:_value_sort_key`/`_value_sort_key_reversed`,
 *  kept deliberately separate from the Python rather than shared with it (the file header's own
 *  rule for `valuePageFrom` below). */
function sortKey(row: ValueCopy, reversed: boolean): [boolean, number, number, number] {
  const market = Number(row.market ?? 0)
  const present = row.market !== null
  return reversed ? [!present, market, row.box, row.index] : [!present, -market, row.box, row.index]
}

function compareKeys(a: readonly number[] | readonly [boolean, number, number, number], b: typeof a): number {
  for (let i = 0; i < a.length; i += 1) {
    const av = a[i] as number | boolean
    const bv = b[i] as number | boolean
    const an = typeof av === 'boolean' ? (av ? 1 : 0) : av
    const bn = typeof bv === 'boolean' ? (bv ? 1 : 0) : bv
    if (an !== bn) return an - bn
  }
  return 0
}

type CursorRow = { market: string | null; box: number; index: number }

function encodeCursor(row: CursorRow | undefined): string | null {
  if (row === undefined) return null
  return Buffer.from(JSON.stringify({ market: row.market, box: row.box, index: row.index }), 'utf-8').toString(
    'base64url',
  )
}

function decodeCursor(token: string | null): CursorRow | null {
  if (token === null || token === '') return null
  try {
    return JSON.parse(Buffer.from(token, 'base64url').toString('utf-8')) as CursorRow
  } catch {
    return null
  }
}

/** `GET /pipeline/value?band=...` reshaped out of the SAME `table: ValueTable` fixture every
 *  existing test already builds — a literal TypeScript port of `do_pipeline_value_page`'s
 *  shape, not shared code with the Python (per this file's own rule below `open`). Every
 *  aggregate field (`boxes`, `unrankable`, `totals`, `sources`, `threshold`) is copied through
 *  UNCHANGED regardless of `band`/`box`, matching the real route: the aggregates are computed
 *  over the whole store and never over what one page could see. */
function valuePageFrom(answer: ValueTable, params: URLSearchParams): Record<string, unknown> {
  const band = params.get('band')
  const boxRaw = params.get('box')
  const box = boxRaw === null || boxRaw === '' ? null : Number(boxRaw)
  const limitRaw = params.get('limit')
  const limit = limitRaw === null || limitRaw === '' ? 200 : Number(limitRaw)
  const after = decodeCursor(params.get('after'))

  const scopedCopies = answer.copies.filter((row) => box === null || row.box === box)
  let scoped: ValueCopy[]
  let reversed = false
  if (band === 'gaps') {
    scoped = scopedCopies
      .filter((row) => row.market === null)
      .sort((a, b) => a.box - b.box || a.index - b.index)
  } else {
    reversed = band === 'bottom'
    const priced = scopedCopies.filter((row) => row.market !== null)
    /* STACK FIELDS, over this box-scoped priced set, exactly as `do_pipeline_value_page` adds
       them — needed because `ValueRow` no longer groups by SKU itself. */
    const totals = new Map<string, number>()
    for (const row of priced) {
      if (row.sku !== null) totals.set(row.sku, (totals.get(row.sku) ?? 0) + 1)
    }
    const seen = new Map<string, number>()
    const withStacks = priced.map((row) => {
      if (row.sku === null) return { ...row, stack_index: null, stack_of: null }
      const next = (seen.get(row.sku) ?? 0) + 1
      seen.set(row.sku, next)
      return { ...row, stack_index: next, stack_of: totals.get(row.sku) ?? 1 }
    })
    scoped = withStacks.sort((a, b) => compareKeys(sortKey(a, reversed), sortKey(b, reversed)))
  }

  let start = 0
  if (after !== null) {
    const markerKey = band === 'gaps' ? [after.box, after.index] : sortKey(after as ValueCopy, reversed)
    start = scoped.length
    for (let i = 0; i < scoped.length; i += 1) {
      const rowKey = band === 'gaps' ? [scoped[i]!.box, scoped[i]!.index] : sortKey(scoped[i]!, reversed)
      if (compareKeys(rowKey, markerKey) > 0) {
        start = i
        break
      }
    }
  }
  const page = scoped.slice(start, start + limit)
  const next = page.length > 0 && start + limit < scoped.length ? encodeCursor(page[page.length - 1]) : null

  return {
    at: answer.at,
    basis: answer.basis,
    threshold: answer.threshold,
    sources: answer.sources,
    rows: page,
    next,
    total: scoped.length,
    boxes: answer.boxes,
    unrankable: answer.unrankable,
    totals: answer.totals,
  }
}

/** The page's enter animation has to FINISH before anything measures it.
 *
 *  `.bn-page` enters on `bn-page-in`, a 6px `translateY` over `--bn-t-slow`. A rect read while
 *  that is still running is a rect of a page mid-flight, and the difference lands in exactly the
 *  range a real layout shift would — 3.78px, measured, on the D118 case below, which failed
 *  against a screen that had not moved at all. */
async function settled(page: Page): Promise<void> {
  await page.evaluate(
    () => Promise.all(document.getAnimations().map((one) => one.finished.catch(() => undefined))),
  )
}

async function open(page: Page, answer: ValueTable, end: 'top' | 'bottom' = 'top'): Promise<string[]> {
  const asked: string[] = []
  /* `(\?|$)` RATHER THAN `$` ALONE — store-scaling item 7 adds a query string
     (`?band=top&limit=200`) to every fetch this screen makes, and the old `$`-anchored regex
     stops matching the instant one is appended, breaking every test in this file before any
     assertion runs. */
  await page.route(/\/pipeline\/value(\?|$)/, async (route) => {
    asked.push(route.request().method())
    const url = new URL(route.request().url())
    const band = url.searchParams.get('band')
    /* BUILD THE PAGE/AGGREGATES SHAPE OUT OF THE SAME `answer: ValueTable` FIXTURE EVERY
       EXISTING TEST ALREADY PASSES, so no test has to be rewritten to construct two different
       fixture shapes — one helper does the reshaping once. `band === null` never actually
       fires from this client any more (it always asks for a band), kept only because
       `do_pipeline_value()`'s own no-args shape is what `answer` already is. */
    const body = band === null ? answer : valuePageFrom(answer, url.searchParams)
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })
  /* THE WORKLIST ANSWERS NOTHING, ON PURPOSE. The lens reads the whole STORE, so every case
     here runs on a machine with no joined run — which is the state D109's defect was found in
     and the one this lens has to work in. */
  await page.route(/\/pipeline\/pricing/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ runs: [], skus: [], roster: [], skipped: [], asked: [], written_at: {}, threshold: '0.29', floor: '0.29' }),
    })
  })
  await page.route(/\/pricing$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 1, policy: { threshold: '0.29' }, skus: {} }),
    })
  })
  await page.goto(`/#/pricing?band=${end}`)
  await expect(page.locator(VIEW)).toBeVisible()
  return asked
}

/** Put every priced card in the band, by pressing the cut-off chip.
 *
 *  THE DEFAULT IS THE TOP 5% AND THAT IS CORRECT — 92 rows of the owner's store, a list you read
 *  to the end. It is the wrong band for a case whose subject is every row of a three-row
 *  fixture, and a case that quietly changed the default to suit itself would stop testing the
 *  default. */
async function everyCard(page: Page): Promise<void> {
  await page.getByRole('button', { name: /^(Over|Under) \$/ }).click()
}

sealEveryTest({ store: true })

test('one SKU in three slots draws three rows, and each says which copy it is', async ({ page }) => {
  /* THE UNIT IS THE COPY AND NEVER THE SKU, which is the measurement this whole screen turns
     on: the owner's 122 cards at or above $5 are 38 SKUs. A per-SKU list draws a third of the
     rows and sends a hand to a third of the drawers it has to open. */
  await open(
    page,
    table({
      copies: [copy({ index: 61 }), copy({ index: 102 }), copy({ index: 163 })],
      boxes: [drawer()],
      totals: { cards: 3, valued: 3, value: '142.71', at_or_over: 3 },
    }),
  )

  await everyCard(page)
  await expect(page.locator('.value-row')).toHaveCount(3)
  /* AND SEVEN IDENTICAL ROWS READ AS SEVEN REACHES RATHER THAN AS A REPETITION only because
     the row says so. Without this clause three identical Rengar rows look like a defect. */
  await expect(page.locator('.value-meta').nth(0)).toContainText('copy 1 of 3')
  await expect(page.locator('.value-meta').nth(2)).toContainText('copy 3 of 3')
})

/* NO TYPED MIDDLE DOT OR BULLET REACHES THE LENS (D218). `.value-meta`'s set/condition/copy
 * join and the live badge's own separator are drawn by CSS now (`.value-meta > span::after`),
 * never typed into the row's text. */
test('no typed middle dot or bullet reaches the value lens (D218)', async ({ page }) => {
  await open(
    page,
    table({
      copies: [copy({ index: 61, live: 3 }), copy({ index: 102 }), copy({ index: 163 })],
      boxes: [drawer()],
      totals: { cards: 3, valued: 3, value: '142.71', at_or_over: 3 },
    }),
  )
  await everyCard(page)
  await expect(page.locator('.value-row')).toHaveCount(3)

  const text = await page.locator(VIEW).innerText()
  expect(text).not.toMatch(/[·•]/)
})

test('a card with no price is counted, named and never ranked', async ({ page }) => {
  /* 390 of 2,245 cards on the owner's store carry no market price. This case is the no-silent-
     drop rule: they are out of the ranking, they are IN the count, and each of the three causes
     keeps its own sentence because each has a different remedy. */
  await open(
    page,
    table({
      copies: [
        copy(),
        copy({ index: 2, sku: null, name: null, market: null, why: 'never_identified', state: 'captured', source: null, read_at: null }),
        copy({ index: 3, sku: null, name: null, market: null, why: 'read_nothing', source: null, read_at: null }),
        copy({ index: 4, market: null, why: 'no_reading', source: null, read_at: null }),
      ],
      boxes: [drawer({ cards: 4, valued: 1, unpriced: 3, at_or_over: 1, total: '47.57', per_card: '11.89' })],
      unrankable: { total: 3, never_identified: 1, read_nothing: 1, no_reading: 1, by_box: { '4': 3 } },
      totals: { cards: 4, valued: 1, value: '47.57' },
    }),
  )

  await expect(page.locator('.value-row')).toHaveCount(1)
  await expect(page.locator('.value-gapline')).toContainText('3 cards have no price yet and are not in this list')
  /* NEVER A ZERO. A card ranked at $0.00 because nothing priced it lands at the bottom of the
     cheap band and into a bulk pull — the wrong answer wearing the shape of a confident one. */
  await expect(page.locator('.value-row')).not.toContainText('$0.00')

  const causes = page.locator('.value-cause')
  await expect(causes).toHaveCount(3)
  await expect(causes.nth(0)).toContainText('Never identified')
  await expect(causes.nth(1)).toContainText('Nothing was read off the photograph')
  await expect(causes.nth(2)).toContainText('No export prices them')
  /* THREE CAUSES, THREE DOORS. A screen that offered one remedy for three problems would be
     sending the operator to a run for a card a run has already looked at. */
  await expect(causes.nth(0).getByRole('button', { name: 'Start a run' })).toBeVisible()
  await expect(causes.nth(1).getByRole('button', { name: 'Look at them' })).toBeVisible()
  await expect(causes.nth(2).getByRole('button', { name: 'Fetch an export' })).toBeVisible()
})

test('the three causes are drawn even at zero, so the panel height is not a fact about the store', async ({ page }) => {
  await open(
    page,
    table({
      copies: [copy(), copy({ index: 2, sku: null, name: null, market: null, why: 'never_identified', state: 'captured' })],
      boxes: [drawer({ cards: 2, valued: 1, unpriced: 1, at_or_over: 1 })],
      unrankable: { total: 1, never_identified: 1, read_nothing: 0, no_reading: 0, by_box: { '4': 1 } },
      totals: { cards: 2, valued: 1, value: '47.57' },
    }),
  )
  await expect(page.locator('.value-cause')).toHaveCount(3)
  await expect(page.locator('.value-cause').nth(1).locator('.value-cause-count')).toHaveText('0')
  /* A CAUSE AT ZERO CARRIES NO DOOR — there is nothing to go and do about it. */
  await expect(page.locator('.value-cause').nth(1).getByRole('button')).toHaveCount(0)
})

test('the cheap end opens on drawers and the rich end on cards', async ({ page }) => {
  /* THE CONTIGUITY MEASUREMENT, AS A DEFAULT. The band at or above $5 is 1.40 cards per reach —
     a pick list — and the band under the cut-off is 6.51, of which two whole drawers are 646 of
     the 1,042 cards. The two ends want different artefacts, so direction re-defaults the view. */
  await open(
    page,
    table({
      copies: [copy(), copy({ index: 2, market: '0.03' })],
      boxes: [drawer({ cards: 2, valued: 2, at_or_over: 1, under_cutoff: 1 })],
      totals: { cards: 2, valued: 2, value: '47.60' },
    }),
  )

  await expect(page.locator('.value-list')).toBeVisible()
  await expect(page.locator('.value-drawers')).toHaveCount(0)

  await page.getByRole('button', { name: 'Worth the least' }).click()
  await expect(page.locator('.value-drawers')).toBeVisible()
  await expect(page.locator('.value-list')).toHaveCount(0)
})

test("a drawer holding an unpriced card is worth AT LEAST its total, and earns no bulk verdict", async ({ page }) => {
  /* BOX 5's OWN SHAPE: 104 cards, 102 priced, every one of those under the cut-off, and two
     nobody has read. `at_or_over` is 0 and the drawer is still not provably bulk — its errand
     is "read those two, then the drawer goes". A pill drawn here would be a claim about cards
     nothing has looked at. */
  await open(
    page,
    table({
      copies: [copy({ box: 5, market: '0.18' })],
      boxes: [
        drawer({ box: 5, name: 'UNL BBOX C/UC 1', cards: 104, valued: 102, unpriced: 2, under_cutoff: 102, at_or_over: 0, total: '7.97', per_card: '0.08', top: '0.18' }),
      ],
      unrankable: { total: 2, never_identified: 2, read_nothing: 0, no_reading: 0, by_box: { '5': 2 } },
      totals: { cards: 104, valued: 102, value: '7.97' },
    }),
    'bottom',
  )

  const card = page.locator('.value-drawer')
  await expect(card.locator('.value-atleast')).toHaveText('at least')
  await expect(card).toContainText('$7.97')
  await expect(card.locator('.bn-pill')).toHaveCount(0)
  await expect(card.locator('.value-drawer-gap')).toContainText('2 of its cards have never been priced')
})

test('a drawer with nothing unread and nothing over the cut-off says so as a verdict', async ({ page }) => {
  await open(
    page,
    table({
      copies: [copy({ box: 2, market: '0.11' })],
      boxes: [drawer({ box: 2, name: 'ME01 C/UC', cards: 542, valued: 542, unpriced: 0, under_cutoff: 542, at_or_over: 0, total: '58.72', per_card: '0.11', top: '0.28' })],
      totals: { cards: 542, valued: 542, value: '58.72' },
    }),
    'bottom',
  )
  await expect(page.locator('.value-drawer .bn-pill')).toContainText('Nothing in it is over $0.29')
  await expect(page.locator('.value-atleast')).toHaveCount(0)
})

test('a drawer that is bulk except for N cards offers those N as one press', async ({ page }) => {
  /* THE STRONGEST MOVE ON THE SCREEN and it falls straight out of the real numbers: box 2 is
     540 of 542 cards under the cut-off. One reach for the two that are not, and then the drawer
     goes whole. */
  await open(
    page,
    table({
      copies: [
        copy({ box: 2, index: 2, market: '0.36', name: "Lillie's Determination - 119/132" }),
        copy({ box: 2, index: 9, market: '0.11', name: 'Something cheap' }),
      ],
      boxes: [drawer({ box: 2, name: 'ME01 C/UC', cards: 542, valued: 542, unpriced: 0, under_cutoff: 540, at_or_over: 2, total: '58.72', per_card: '0.11', top: '0.36' })],
      totals: { cards: 542, valued: 542, value: '58.72' },
    }),
    'bottom',
  )

  await page.getByRole('button', { name: 'Show the 2 worth listing' }).click()
  await expect(page.locator('.value-scope')).toContainText('Only ME01 C/UC')
  await expect(page.locator('.value-list')).toBeVisible()
  /* SCOPED TO THAT DRAWER, AT THE CUT-OFF, AT THE RICH END — one press answers the whole
     question rather than setting three controls. */
  await expect(page.locator('.value-row')).toHaveCount(1)
  await expect(page.locator('.value-row')).toContainText("Lillie's Determination")
})

test('a listed card is in the band with no distinction, and the count is a fact on the row', async ({ page }) => {
  /* THE OWNER'S RULING, made on the figure: 70% of the copies under their cut-off are live at
     TCGplayer. Hiding or dimming them would grey out most of the cheap band. */
  await open(
    page,
    table({
      copies: [copy({ live: 3 }), copy({ index: 2, live: 0, market: '20.00' })],
      boxes: [drawer({ cards: 2, valued: 2, total: '67.57', per_card: '33.79' })],
      totals: { cards: 2, valued: 2, value: '67.57', at_or_over: 2 },
    }),
  )
  await everyCard(page)
  await expect(page.locator('.value-row')).toHaveCount(2)
  await expect(page.locator('.value-row').nth(0).locator('.value-live')).toHaveText('3 listed')
  /* A ZERO DRAWS NOTHING — a column of "0 listed" is noise, and the absence is the information. */
  await expect(page.locator('.value-row').nth(1).locator('.value-live')).toHaveCount(0)
})

test('a press on a band chip does not move the bar', async ({ page }) => {
  /* D118: a press changes WHAT is on the screen and never where the rest of it is. This one
     replaces the whole body, which is exactly why the bar has to be the fixed frame. */
  await open(
    page,
    table({
      copies: Array.from({ length: 20 }, (_, at) => copy({ index: at + 1, market: `${40 - at}.00` })),
      boxes: [drawer({ cards: 20, valued: 20, at_or_over: 20, total: '610.00', per_card: '30.50', top: '40.00' })],
      totals: { cards: 20, valued: 20, value: '610.00' },
    }),
  )

  const bar = page.locator('.value-bar')
  await settled(page)
  const before = await bar.boundingBox()
  await page.getByRole('button', { name: /^Top 1%/ }).click()
  await expect(page.locator('.value-row')).toHaveCount(1)
  await settled(page)
  const after = await bar.boundingBox()
  expect(after?.y).toBe(before?.y)
  expect(after?.height).toBe(before?.height)
  expect(after?.width).toBe(before?.width)
})

test('the lens draws on a store with no joined run at all', async ({ page }) => {
  /* D109's DEFECT, WHICH THIS SCREEN MUST NOT REPEAT. `#/pricing` used to send an operator with
     2,245 cards on hand away to Runs because none of them came out of a run they had picked.
     The lens reads the store, so it answers on exactly that machine — and the branch that
     renders it sits AHEAD of every worklist empty state for this reason. */
  const asked = await open(
    page,
    table({
      copies: [copy()],
      boxes: [drawer({ cards: 1, valued: 1, total: '47.57', per_card: '47.57' })],
      totals: { cards: 1, valued: 1, value: '47.57' },
    }),
  )
  /* READS ONLY, AND ONLY THIS ROUTE. Not a count — `StrictMode` double-invokes an effect in
     development and the suite runs against the dev server, so a fixed number here would be
     asserting a React build flag rather than this screen's behaviour. What matters is that
     nothing on this path writes. */
  expect(asked.length).toBeGreaterThan(0)
  expect(asked.every((method) => method === 'GET')).toBe(true)
  await expect(page.getByRole('heading', { name: "What's worth pulling" })).toBeVisible()
  await expect(page.locator('.value-row')).toHaveCount(1)
})

test('an empty band names the extreme it could not reach', async ({ page }) => {
  await open(
    page,
    table({
      copies: [copy({ market: '47.57' })],
      boxes: [drawer({ cards: 1, valued: 1, total: '47.57', per_card: '47.57' })],
      totals: { cards: 1, valued: 1, value: '47.57' },
    }),
  )
  await page.locator('.value-field-input').fill('50.00')
  /* "NOTHING IS WORTH $50 OR MORE" IS HALF AN ANSWER. The other half is what the most valuable
     card actually is, which is the question the operator was really asking. */
  await expect(page.locator('.bn-empty-title')).toContainText('Nothing is worth $50.00 or more')
  await expect(page.locator('.bn-empty-body')).toContainText('Last Rites at $47.57')
})

test('the unrankable list pages, and says how much of it is on screen', async ({ page }) => {
  /* THE ONE PANEL ON THIS SCREEN THAT MAY NOT DROP ANYTHING QUIETLY. It paged at 200 with no
     line saying so, which on the owner's 390 unrankable cards is 190 silently missing from the
     one place they are accounted for — inside the feature built to stop exactly that. */
  const gaps = Array.from({ length: 260 }, (_, at) =>
    copy({ index: at + 2, sku: null, name: null, market: null, why: 'read_nothing', source: null, read_at: null }),
  )
  await open(
    page,
    table({
      copies: [copy(), ...gaps],
      boxes: [drawer({ cards: 261, valued: 1, unpriced: 260, at_or_over: 1 })],
      unrankable: { total: 260, never_identified: 0, read_nothing: 260, no_reading: 0, by_box: { '4': 260 } },
      totals: { cards: 261, valued: 1, value: '47.57' },
    }),
  )
  await page.getByRole('button', { name: 'Show them' }).click()
  await expect(page.locator('.value-gap-row')).toHaveCount(200)
  await expect(page.locator('.value-gaps .value-more-says')).toHaveText('200 of 260 shown')
  await page.locator('.value-gaps').getByRole('button', { name: 'Show 60 more' }).click()
  await expect(page.locator('.value-gap-row')).toHaveCount(260)
})

test('a store with nothing in a box says so and offers the camera', async ({ page }) => {
  await open(page, table())
  await expect(page.locator('.bn-empty-title')).toContainText('Nothing is in a box yet')
  await expect(page.getByRole('button', { name: 'Capture a box' })).toBeVisible()
})

test('leaving the lens puts the screen back on the worklist', async ({ page }) => {
  await open(
    page,
    table({
      copies: [copy()],
      boxes: [drawer({ cards: 1, valued: 1 })],
      totals: { cards: 1, valued: 1, value: '47.57' },
    }),
  )
  await page.getByRole('button', { name: 'Back to pricing' }).click()
  /* THE LENS FOLLOWS THE HASH IN BOTH DIRECTIONS, exactly as the markdown stamp does — or it
     would survive the operator navigating out of it. */
  await expect(page.locator(VIEW)).toHaveCount(0)
  expect(new URL(page.url()).hash).toBe('#/pricing')
})

test('a mount that outlives its own fetch does not win over a fresher one (w1b)', async ({ page }) => {
  /* THE PLANNER'S PROBABLE CAUSE, INSTRUMENTED AND NARROWED. The bug report — a cold
   * navigation to `#/pricing?band=top` shows the tab badge but "Nothing sits in that band" —
   * was chased by delaying `getValueAggregates()` alone (it shares `getValuePage`'s endpoint
   * at `limit=0`) under React's StrictMode double-invoke, which DOES double-fire this effect
   * on every mount (confirmed by instrumenting `ValueBands.tsx` directly): `readAggregates`
   * runs twice, `liveAgg.current` is armed by the SECOND mount before the FIRST mount's
   * response lands, and both responses are applied. Under `sealEveryTest`'s mocks — which
   * answer every duplicate request with IDENTICAL data — this self-corrects: the rows effect
   * re-runs on every `aggregates` change and lands on the right count regardless of which of
   * the two identical responses wins. A production build (no StrictMode) never double-mounts
   * on a single cold `goto` at all, and could not be made to reproduce the reported symptom
   * either — confirmed by building `app/dist`, serving it, and watching the same
   * instrumentation log exactly one mount.
   *
   * WHAT INSTRUMENTATION DID FIND, and what this case pins down directly: `readAggregates`'s
   * only guard is `liveAgg.current` — true for "still mounted", with no notion of WHICH
   * in-flight request started most recently. `getValuePage`'s own rows effect two cursors
   * down protects against exactly this with a monotonic `generation` ref; the aggregates
   * fetch has no equivalent. So a mount that is still alive when a SLOW, STALE response lands
   * will apply it over a FASTER, FRESHER response that already resolved and already drew
   * rows — the reverse of "latest request wins". This does not need StrictMode: unmounting
   * the lens before its fetch resolves and re-entering it (the "Worth the least" / "Worth the
   * most" toggle, or leaving and pressing "Find by value" again) is a real, everyday trigger
   * for two overlapping requests, and it is deterministic here rather than timing-dependent. */
  const stale = table({
    copies: [copy({ index: 1, market: '1.00' })],
    boxes: [drawer({ cards: 1, valued: 1, at_or_over: 1, under_cutoff: 0, total: '1.00' })],
    totals: { cards: 1, valued: 1, value: '1.00' },
  })
  const fresh = table({
    copies: Array.from({ length: 100 }, (_, at) => copy({ index: at + 1, market: `${(100 - at).toFixed(2)}` })),
    boxes: [drawer({ cards: 100, valued: 100, at_or_over: 100, under_cutoff: 0, total: '5050.00' })],
    totals: { cards: 100, valued: 100, value: '5050.00' },
  })

  let aggregatesCalls = 0
  await page.route(/\/pipeline\/value(\?|$)/, async (route) => {
    const url = new URL(route.request().url())
    if (url.searchParams.get('limit') === '0') {
      // THE FIRST aggregates call (mounted, then abandoned before it answers) is SLOW and
      // STALE. The SECOND (the remount that stays on screen) is FAST and FRESH — the shape a
      // real "leave, then come straight back" always takes, since the abandoned mount's
      // request keeps running on the wire even after React has stopped listening.
      aggregatesCalls += 1
      const first = aggregatesCalls === 1
      await new Promise((resolve) => setTimeout(resolve, first ? 400 : 20))
      const body = valuePageFrom(first ? stale : fresh, url.searchParams)
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
      return
    }
    // Every ROWS fetch answers instantly, off whichever table is CURRENTLY on screen — a real
    // server has one current answer, never two.
    const body = valuePageFrom(aggregatesCalls <= 1 ? stale : fresh, url.searchParams)
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.route(/\/pipeline\/pricing/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ runs: [], skus: [], roster: [], skipped: [], asked: [], written_at: {}, threshold: '0.29', floor: '0.29' }),
    })
  })
  await page.route(/\/pricing$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 1, policy: { threshold: '0.29' }, skus: {} }),
    })
  })

  // A SINGLE COLD `goto`. `StrictMode` (`app/src/main.tsx`) double-invokes every mount
  // effect in dev, so `ValueBands`'s aggregates effect fires twice on this one navigation —
  // confirmed by instrumenting it directly. Both calls share ONE `liveAgg` ref (StrictMode's
  // simulated unmount/remount reuses the fiber's hook state, unlike a real unmount), so
  // whichever of the two responses lands LAST wins, regardless of which was slower or which
  // request started more recently.
  await page.goto('/#/pricing?band=top')
  await expect(page.locator(VIEW)).toBeVisible()
  await expect(page.locator('.value-row')).toHaveCount(5, { timeout: 5000 })

  // Give the FIRST (stale, slow) response time to land after the fresh one already drew —
  // the whole point of the case.
  await page.waitForTimeout(700)

  // THE FRESH READING MUST STILL BE ON SCREEN. A stale response that answers after a fresher
  // one already resolved must never overwrite it.
  await expect(page.getByRole('button', { name: /Top 5%/ }).locator('.bn-chip-count')).toHaveText('5')
  await expect(page.locator('.value-row')).toHaveCount(5)
})
