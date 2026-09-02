import { test, expect, type Page } from '@playwright/test'

import type {
  OrderRow,
  OrdersPayload,
  PickRow,
  Place,
  ResolvedLine,
  ResolvedOrder,
} from '../src/types'

/* THE ORDER SCREEN, ASSERTED WHERE NOTHING ELSE CAN SEE IT.
 *
 * `make design-check` ONLY, AND NOT A HARNESS TEST — it must never become one. `docs/GATES.md`'s
 * harness contract is seven Python tests run at the Stop hook, and this starts a browser.
 *
 * WHY IT EXISTS AT ALL. `CLAUDE.md`'s hard rule is "A ROUTE IS NOT A FEATURE", and step 7's own
 * record is 7b shipping with three screens missing from `App.tsx`'s ROUTES table while harness,
 * lint, typecheck and docs-audit were ALL green. Nothing on the path that decides whether a
 * commit proceeds can tell whether a human can open a screen. This file is that check for
 * `#/orders`, which is why its first case is the dullest one in it: does the hash resolve, and
 * does the nav offer the chord.
 *
 * THE FOUR CASES THAT ARE NOT DULL, and each of them is a rule that would otherwise live only in
 * a comment:
 *
 *   ALL SIX REASONS RENDER, INCLUDING THE ZEROS. `Resolution.counts` returns every one and the
 *   route filters none, because reporting only what fired makes "nothing was short" and "nothing
 *   was checked" the same screen. `sku_unknown` is structurally unreachable from this route and
 *   is ALWAYS a zero — case 2 asserts it is drawn anyway, which is the assertion a later "hide
 *   the empties" tidy-up would fail.
 *
 *   A COPY ALREADY SPOKEN FOR IS NOT OFFERED TWICE. `held_by` is the request's own reverse index
 *   over `capture_id`; a screen that ignored it would walk the picker to one drawer for two
 *   envelopes and the second buyer would get a short envelope. Case 3 asserts the row draws the
 *   holder and offers no Pull.
 *
 *   THE PULL SENDS THE ROW'S OWN `capture_id`. That is the aim check the server refuses on
 *   (`capture_id_mismatch`), and it is what makes the press safe across a mid-box delete or a
 *   re-shoot. Case 4 reads the POST body and asserts the id came from the row that was pressed
 *   rather than from the first pick on the line.
 *
 *   THE RECEIPT READS THE PRE-WRITE PLACE. `places[]` comes back as it was BEFORE the write; a
 *   sale moves the box's occupancy (D58), so `sales[0].card.place.label` is already
 *   `Box 3 · departed` by the time the answer is composed. Case 5 answers with both and asserts
 *   the receipt shows the one the operator just walked to. This is the case that fails if
 *   somebody "simplifies" the receipt to read the sale.
 *
 * NO REAL REQUEST IS EVER MADE. Every route is intercepted and the POST is RECORDED rather than
 * performed, which is what lets case 4 assert the exact shape the screen would have sent.
 */

const VIEW_ROUTE = '/#/orders'
const VIEW = 'main.orders'

const ORDER_NUMBER = 'A2FFC195-0000F4-006AC'
const OTHER_ORDER = 'B31A0C7D-0001A2-00311'
const SKU = '9191486'

type Wire = { method: string; path: string; body: unknown }

/** A position block with every field the server sends. A partial fixture does not fail
 *  partially here — a missing `label` renders the pooled branch and the case reads as though the
 *  screen were broken, which is exactly the confusion `shipping.spec.ts` records paying for. */
function place(over: Partial<Place> = {}): Place {
  const base: Place = {
    label: 'Box 3 · Section 2 · Card 17',
    located: true,
    box: 3,
    index: 21,
    slot: 17,
    section: 2,
    card: 17,
    box_name: 'RB Epics',
    section_start: 12,
    section_end: null,
    box_total: 133,
    box_closed: false,
    fraction: 0.13,
    neighbors: null,
    section_gaps: 0,
  }
  return { ...base, ...over }
}

/** One copy the resolver offered. `capture_id` is the identity everything on this screen aims
 *  by, so it is the field every case varies. */
function pick(over: Partial<PickRow> = {}): PickRow {
  const base: PickRow = {
    box: 3,
    index: 21,
    capture_id: 'cap-a',
    source: 'card',
    run: null,
    card_name: 'Volcanion',
    card_number: '025',
    condition: 'Near Mint',
    state: 'listed',
    held_by: null,
    place: place(),
  }
  return { ...base, ...over }
}

function line(over: Partial<ResolvedLine> = {}): ResolvedLine {
  const base: ResolvedLine = {
    order: ORDER_NUMBER,
    order_key: `TCGplayer:${ORDER_NUMBER}`,
    sku: SKU,
    reason: 'resolved',
    wanted: 1,
    owed: 1,
    fulfilled: 1,
    outstanding: 0,
    on_hand: 1,
    sold: 0,
    retired: 0,
    pooled: 0,
    line: {
      sku: SKU,
      quantity: 1,
      name: 'Volcanion',
      number: '025',
      printing: 'Normal',
      condition: 'Near Mint',
      rarity: 'Rare',
      unit_price: '1.24',
      kind: 'single',
    },
    picks: [pick()],
  }
  return { ...base, ...over }
}

function order(over: Partial<OrderRow> = {}): OrderRow {
  const base: OrderRow = {
    key: `TCGplayer:${ORDER_NUMBER}`,
    source: 'TCGplayer',
    number: ORDER_NUMBER,
    placed_at: '2026-08-29T10:00:00+00:00',
    status: 'Ready to ship',
    first_seen: '2026-08-30T09:00:00+00:00',
    changed_at: null,
    wanted: 1,
    recorded: 0,
    open: true,
    lines: [line().line],
    progress: [
      { sku: SKU, wanted: 1, recorded: 0, outstanding: 1, over: 0, copies: [], pulled: [], at: null },
    ],
  }
  return { ...base, ...over }
}

/** The whole payload, with the counts derived from the lines rather than restated beside them —
 *  a fixture whose tally disagrees with its own list can make a broken breakdown look right. */
function payloadOf(orders: OrderRow[], resolved: ResolvedOrder[]): OrdersPayload {
  const all = resolved.flatMap((one) => one.lines)
  const tally = (reason: ResolvedLine['reason']) =>
    all.filter((one) => one.reason === reason).length
  return {
    summary: `${orders.length} order${orders.length === 1 ? '' : 's'}`,
    orders,
    resolution: {
      orders: resolved,
      counts: {
        resolved: tally('resolved'),
        short: tally('short'),
        no_copies_on_hand: tally('no_copies_on_hand'),
        sku_unknown: tally('sku_unknown'),
        sku_unseen: tally('sku_unseen'),
        not_a_single: tally('not_a_single'),
      },
    },
  }
}

/** The default world: one open order, one resolved line, one copy in box 3. */
function oneOpenOrder(): OrdersPayload {
  return payloadOf(
    [order()],
    [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] }],
  )
}

/**
 * Land on the screen with every route it can reach intercepted, and return the log of what it
 * sent. The order screen DOES read on mount — one call answers the list and the resolution out
 * of one snapshot — so `orders` is the payload that read answers with.
 */
async function open(
  page: Page,
  options: { orders?: OrdersPayload; pull?: unknown; preview?: unknown; fetched?: unknown } = {},
): Promise<Wire[]> {
  const wire: Wire[] = []

  await page.route(/\/orders\/pull$/, async (route) => {
    wire.push({
      method: route.request().method(),
      path: new URL(route.request().url()).pathname,
      body: route.request().postDataJSON(),
    })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(options.pull ?? { undone: false, order_key: '', sku: '', newly: 1, recorded: 1, outstanding: 0, places: [], sales: [] }),
    })
  })

  /* THE FETCH ROUTE, IN BOTH BODIES (D91). Registered before `/orders$` like every write-shaped
     route here: the read regex is the looser one. A preview body answers the window by status; a
     statuses body answers the ingest-shaped orders plus the four counts. Recorded, not performed
     — nothing here reaches TCGplayer, and nothing may: this file runs against whatever real
     server is listening on this checkout's port. */
  await page.route(/\/orders\/fetch$/, async (route) => {
    const body = route.request().postDataJSON() as { preview?: boolean }
    wire.push({ method: route.request().method(), path: new URL(route.request().url()).pathname, body })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        body.preview === true
          ? (options.preview ?? {
              range: 'LastThreeMonths',
              total: 370,
              by_status: [
                { status: 'Shipped', count: 280, known: 0 },
                { status: 'Cancelled', count: 88, known: 0 },
                { status: 'Ready to Ship', count: 2, known: 0 },
              ],
              writes_nothing: true,
            })
          : (options.fetched ?? {
              orders: [
                {
                  source: 'TCGplayer',
                  number: ORDER_NUMBER,
                  placed_at: '2026-08-30',
                  status: 'Ready to Ship',
                  lines: [{ sku: SKU, quantity: 1, name: 'Volcanion', unit_price: '11.88' }],
                },
              ],
              matched: 2,
              skipped_known: 0,
              detailed: 2,
              remaining: 0,
            }),
      ),
    })
  })

  await page.route(/\/orders\/ingest$/, async (route) => {
    wire.push({
      method: route.request().method(),
      path: new URL(route.request().url()).pathname,
      body: route.request().postDataJSON(),
    })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        added: 1,
        changed: 0,
        unchanged: 0,
        total: 1,
        wrote_nothing: false,
        summary: '1 order added.',
        keys: [`TCGplayer:${ORDER_NUMBER}`],
      }),
    })
  })

  await page.route(/\/orders$/, async (route) => {
    wire.push({ method: route.request().method(), path: new URL(route.request().url()).pathname, body: null })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(options.orders ?? oneOpenOrder()),
    })
  })

  await page.goto(VIEW_ROUTE)
  await expect(page.locator(VIEW)).toBeVisible()
  return wire
}

/* -------------------------------------------------------------------------------------- 1 */

test('the route resolves, and the nav offers it under its own chord', async ({ page }) => {
  await open(page)

  /* THE DULLEST ASSERTION IN THE FILE AND THE ONE THAT PAYS FOR IT. A screen absent from
     `App.tsx`'s ROUTES table renders the unresolved-hash page instead, which nothing else in
     this repo can tell — harness, lint, typecheck and docs-audit all stay green over it. */
  await expect(page.locator(VIEW)).toBeVisible()

  await expect(page.locator('a.app-nav-link[href="#/orders"] kbd.app-nav-key')).toHaveText(',O')
})

/* -------------------------------------------------------------------------------------- 2 */

test('all six reasons are drawn, including the ones that are zero', async ({ page }) => {
  await open(page)

  /* SIX, NOT "the ones that fired". `sku_unknown` cannot fire from this route at all — it needs
     a run's paperwork, which `do_orders` deliberately does not pass — so it is a permanent zero,
     and a build that stopped drawing the empties would look identical on a quiet day and be
     wrong on a busy one. */
  await expect(page.locator('.orders-count')).toHaveCount(6)
  for (const reason of [
    'resolved',
    'short',
    'no_copies_on_hand',
    'sku_unknown',
    'sku_unseen',
    'not_a_single',
  ]) {
    await expect(page.locator(`.orders-count-${reason} .orders-count-machine`)).toHaveText(reason)
  }
  await expect(page.locator('.orders-count-sku_unknown .orders-count-figure')).toHaveText('0')
  await expect(page.locator('.orders-count-resolved .orders-count-figure')).toHaveText('1')

  /* THE HUMAN LABEL BESIDE THE MACHINE STRING, docs/DESIGN.md's rule — and `sku_unknown` and
     `sku_unseen` are the pair that pays for it: one letter apart, two different situations. */
  await expect(page.locator('.orders-count-sku_unseen .orders-count-label')).toHaveText(
    'Nothing in the store has ever seen this SKU',
  )
})

/* -------------------------------------------------------------------------------------- 3 */

test('a copy another line already holds is drawn as spoken for, and is not offered', async ({
  page,
}) => {
  const held = line({
    wanted: 2,
    fulfilled: 2,
    outstanding: 0,
    on_hand: 2,
    picks: [
      pick({ capture_id: 'cap-a' }),
      pick({
        capture_id: 'cap-b',
        index: 22,
        place: place({ index: 22, slot: 18, card: 18, label: 'Box 3 · Section 2 · Card 18' }),
        held_by: { order: OTHER_ORDER, sku: SKU },
      }),
    ],
  })
  await open(page, {
    orders: payloadOf(
      [order({ wanted: 2 })],
      [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 0, lines: [held] }],
    ),
  })

  const rows = page.locator('.orders-pick')
  await expect(rows).toHaveCount(2)

  /* THE FREE COPY IS OFFERED AND THE PROMISED ONE IS NOT. Not "disabled": a greyed Pull would
     teach the operator that the press means nothing, and this copy is not unavailable — it is
     already going to somebody else, which is a sentence rather than a state. */
  await expect(rows.nth(0).locator('button.orders-pull')).toHaveCount(1)
  await expect(rows.nth(1).locator('button.orders-pull')).toHaveCount(0)
  await expect(rows.nth(1).locator('.orders-pick-held')).toContainText(OTHER_ORDER)
})

/* -------------------------------------------------------------------------------------- 4 */

test('the pull sends the capture_id of the row that was pressed, and its own position', async ({
  page,
}) => {
  const two = line({
    wanted: 1,
    fulfilled: 2,
    on_hand: 2,
    picks: [
      pick({ capture_id: 'cap-a' }),
      pick({
        capture_id: 'cap-b',
        index: 22,
        place: place({ index: 22, slot: 18, card: 18, label: 'Box 3 · Section 2 · Card 18' }),
      }),
    ],
  })
  const wire = await open(page, {
    orders: payloadOf(
      [order()],
      [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [two] }],
    ),
  })

  /* THE SECOND ROW, DELIBERATELY. Pressing the first would pass against a screen that sent
     `picks[0]` for every row — the exact bug this case exists to catch, and the one a mid-box
     delete turns into a sale of the wrong card. */
  await page.locator('.orders-pick').nth(1).locator('button.orders-pull').click()

  await expect
    .poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length)
    .toBeGreaterThan(0)
  const sent = wire.find((one) => one.path.endsWith('/orders/pull'))
  expect(sent?.body).toEqual({
    source: 'TCGplayer',
    number: ORDER_NUMBER,
    sku: SKU,
    targets: [{ box: 3, index: 22, capture_id: 'cap-b' }],
  })
})

/* -------------------------------------------------------------------------------------- 5 */

test('the receipt names where the card just was, never the departed label the sale answers with', async ({
  page,
}) => {
  await open(page, {
    pull: {
      undone: false,
      order_key: `TCGplayer:${ORDER_NUMBER}`,
      sku: SKU,
      newly: 1,
      recorded: 1,
      outstanding: 0,
      /* THE PRE-WRITE PLACE — where the operator just walked to. */
      places: [place()],
      /* AND THE POST-WRITE ONE BESIDE IT. A sale moves the box's occupancy (D58), so the card
         is departed by the time the answer is composed. A receipt reading this is a receipt
         telling the operator to walk to a slot that now holds a different card. */
      sales: [
        {
          card: { place: place({ label: 'Box 3 · departed', slot: null, section: null, card: null }) },
        },
      ],
    },
  })

  await page.locator('button.orders-pull').first().click()

  const receipt = page.locator('.orders-receipt-text')
  await expect(receipt).toContainText('Box 3 · Section 2 · Card 17')
  await expect(receipt).not.toContainText('departed')

  /* THE WAY BACK IS ON THE RECEIPT AND NOT IN THE ROW, and that is forced rather than chosen: a
     successful pull marks the copy sold, the resolver stops offering it, and an Undo drawn
     inside the row would unmount with it. */
  await expect(page.locator('.orders-receipt button.orders-plain')).toHaveText('Undo')
})

/* -------------------------------------------------------------------------------------- 6 */

test('a pooled copy is drawn as pooled rather than as a position (D24)', async ({ page }) => {
  /* `Place.label` IS NULL BY DESIGN FOR A POOLED CARD AND NEVER BY FAULT — `located: false` is
     what says so. A screen that fell back to `box/index` would print a slot number for a card
     that is in no slot, which is the one thing D24 rules out. */
  const pooled = line({
    picks: [
      pick({
        capture_id: 'cap-p',
        place: place({
          label: null,
          located: false,
          game: 'pokemon_code',
          game_display: 'Pokémon code cards',
          slot: null,
          section: null,
          card: null,
        }),
      }),
    ],
  })
  await open(page, {
    orders: payloadOf(
      [order()],
      [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [pooled] }],
    ),
  })

  await expect(page.locator('.orders-pick-pooled')).toContainText('pooled')

  /* AND NO PHOTOGRAPH ANYWHERE ON THIS SCREEN. A pooled capture's photo is a live code and a
     bearer instrument (D24, CLAUDE.md's opsec rule), and this screen draws no `<img>` at all —
     which is why `scripts/views.txt` may name `#/orders` without the exposure question the
     photo-drawing routes raise. */
  await expect(page.locator('main.orders img')).toHaveCount(0)
})

/* -------------------------------------------------------------------------------------- 7 */

test('a paste is projected before it is sent, and what was dropped is named', async ({ page }) => {
  const wire = await open(page)

  /* THE WAY IN IS SHUT WHILE THERE IS WORK ON SCREEN, AND ITS CONTROL IS IN THE HEADER EITHER
     WAY. A paste box drawn above the counts costs about 180px on every arrival for an errand
     that happens once a batch; the control never moves, only the panel. */
  await expect(page.locator('.orders-paste')).toHaveCount(0)
  await page.locator('.orders-controls button.orders-plain').click()
  await expect(page.locator('.orders-paste')).toHaveCount(1)

  /* AND THE FETCH IS INSIDE IT, not in the page header. It is the same errand with the copying
     done for you — `POST /orders/fetch` answers exactly the body the ingest accepts — so the
     screen has one way in and two sources rather than two ways in. Two presses since D91, and
     the first is the one drawn before anything is checked. */
  await expect(page.locator('.orders-paste button.orders-plain', { hasText: 'Check TCGplayer' })).toHaveCount(1)

  /* A BUYER, A STREET AND AN EMAIL AT THE TOP LEVEL — the shape a real console copy has. None
     of the three may reach the wire, and the screen has to SAY it dropped them: a silent strip
     is indistinguishable on screen from a feed that never carried the field, so the operator
     could not tell a working PII boundary from a broken one. */
  await page.locator('textarea.orders-paste-box').fill(
    JSON.stringify({
      source: 'TCGplayer',
      number: ORDER_NUMBER,
      buyerName: 'Ada Lovelace',
      shippingAddress: '1 Analytical Way',
      email: 'ada@example.com',
      lines: [{ sku: SKU, quantity: 1, name: 'Volcanion' }],
    }),
  )
  await page.locator('.orders-paste button.orders-plain', { hasText: 'Read this paste' }).click()

  await expect
    .poll(() => wire.filter((one) => one.path.endsWith('/orders/ingest')).length)
    .toBeGreaterThan(0)
  const sent = wire.find((one) => one.path.endsWith('/orders/ingest'))
  expect(sent?.body).toEqual({
    orders: [
      {
        source: 'TCGplayer',
        number: ORDER_NUMBER,
        lines: [{ sku: SKU, quantity: 1, name: 'Volcanion' }],
      },
    ],
  })

  const dropped = page.locator('.orders-paste-dropped')
  await expect(dropped).toContainText('buyerName')
  await expect(dropped).toContainText('shippingAddress')
  await expect(dropped).toContainText('email')
})

/* -------------------------------------------------------------------------------------- 8 */

test('the fetch is two presses: the window by status, then only the ticked statuses (D91)', async ({
  page,
}) => {
  const wire = await open(page)
  const reads = () => wire.filter((one) => one.path.endsWith('/orders') && one.method === 'GET').length
  const mounted = reads()
  await page.locator('.orders-controls button.orders-plain').click()
  await page.locator('.orders-paste button.orders-plain', { hasText: 'Check TCGplayer' }).click()

  /* THE FIRST PRESS DETAILS NOTHING AND DRAWS THE WINDOW AS THE WIRE SPELLED IT. 370 orders in
     three months was the measurement that made this two presses: the one-press fetch was refused
     on that account every time it was pressed. Every status is a verbatim string with its count
     and the ledger's count beside it, and NOTHING is pre-ticked — which strings mean "needs
     picking" is the one thing about this feed nobody has enumerated. */
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/fetch')).length).toBe(1)
  expect(wire.find((one) => one.path.endsWith('/orders/fetch'))?.body).toEqual({ preview: true })
  const rows = page.locator('.orders-status')
  await expect(rows).toHaveCount(3)
  await expect(rows.nth(0)).toContainText('Shipped')
  await expect(rows.nth(0)).toContainText('280')
  await expect(rows.nth(2)).toContainText('Ready to Ship')
  await expect(page.locator('.orders-status input:checked')).toHaveCount(0)
  await expect(page.locator('button.orders-fetch')).toBeDisabled()
  expect(wire.filter((one) => one.path.endsWith('/orders/ingest'))).toHaveLength(0)

  /* THE SECOND PRESS DETAILS ONLY WHAT WAS TICKED, SKIPPING WHAT THE LEDGER HOLDS, and the
     result enters through the one door the paste uses: the fetched `orders` array, sent on
     unaltered. The button says how many the ticks add up to before it is pressed. */
  await rows.nth(2).locator('input').check()
  const fetch = page.locator('button.orders-fetch')
  await expect(fetch).toHaveText('Fetch 2 orders')
  await fetch.click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/fetch')).length).toBe(2)
  expect(wire.filter((one) => one.path.endsWith('/orders/fetch'))[1]?.body).toEqual({
    statuses: ['Ready to Ship'],
    skip_known: true,
  })
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/ingest')).length).toBe(1)
  expect(wire.find((one) => one.path.endsWith('/orders/ingest'))?.body).toEqual({
    orders: [
      {
        source: 'TCGplayer',
        number: ORDER_NUMBER,
        placed_at: '2026-08-30',
        status: 'Ready to Ship',
        lines: [{ sku: SKU, quantity: 1, name: 'Volcanion', unit_price: '11.88' }],
      },
    ],
  })
  /* AND THE LEDGER IS RE-READ AFTER THE INGEST — one more read than the mount made. Counted
     relative to the mount rather than as an absolute, because React's StrictMode runs the
     mount effect twice in development and this spec runs against the dev server. */
  await expect.poll(reads).toBe(mounted + 1)
  await expect(page.locator('.orders-paste-note')).toContainText('2 of 2 matching orders detailed')
})

/* -------------------------------------------------------------------------------------- 9 */

test('a fetch the cap cut short says how many it left, and an empty one still re-reads', async ({
  page,
}) => {
  const wire = await open(page, {
    fetched: { orders: [], matched: 130, skipped_known: 30, detailed: 0, remaining: 100 },
  })
  const reads = () => wire.filter((one) => one.path.endsWith('/orders') && one.method === 'GET').length
  const mounted = reads()
  await page.locator('.orders-controls button.orders-plain').click()
  await page.locator('.orders-paste button.orders-plain', { hasText: 'Check TCGplayer' }).click()
  await expect(page.locator('.orders-status')).toHaveCount(3)
  await page.locator('.orders-status').nth(0).locator('input').check()
  await page.locator('button.orders-fetch').click()

  /* NOTHING TO INGEST IS NOT NOTHING TO SAY. The note names the cap's leftover as a number and
     tells the operator the next press picks it up; and the screen re-reads the ledger anyway,
     because "nothing new for me" and "nothing moved" are different facts. */
  await expect(page.locator('.orders-paste-note')).toContainText('100 remaining')
  await expect(page.locator('.orders-paste-note')).toContainText('30 already in the ledger')
  expect(wire.filter((one) => one.path.endsWith('/orders/ingest'))).toHaveLength(0)
  await expect.poll(reads).toBe(mounted + 1)
})
