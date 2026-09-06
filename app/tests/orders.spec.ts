import { test, expect, type Page, type Route } from '@playwright/test'
import { sealEveryTest } from './shell'

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
  options: {
    orders?: OrdersPayload | (() => OrdersPayload)
    pull?: unknown
    preview?: unknown
    fetched?: unknown
    /* THE CAPTURE SERVER'S BOOT ID, for the one case that is about a restart. A function so a case
       can change it between reads. See the route below for why it has to be every GET. */
    boot?: () => string
  } = {},
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

  /* ONE BOOT ID ACROSS EVERY READ, WITHOUT TOUCHING THE LIVE SERVER, and only for the case that
   * asks for one.
   *
   * `noteBoot` fires `onServerBoot` when the header CHANGES between two non-empty values. An absent
   * header is a no-op by design, so every other case here is unaffected. But a case stubbing
   * `/orders` with an id of its own, while the routes it does NOT stub reach the real capture server
   * with a different one, makes the value alternate and fires the listener on nearly every read.
   *
   * `/status` AND `/inventory` ARE THE ROUTES THIS FILE DOES NOT OTHERWISE CLAIM, and `/inventory`
   * is not optional: `onPull` re-reads BOTH the ledger and the store
   * (`Orders.tsx`: `await Promise.all([reread(), rereadStore()])`), so stubbing only `/orders` still
   * lets the real server answer with its own id on the same press.
   *
   * STUBBED RATHER THAN FORWARDED, AND THE FIRST DRAFT FORWARDED. A catch-all matched by PORT that
   * called `route.fetch()` also caught `POST /orders/pull` — Playwright matches the most recent
   * route first, so it shadowed the stub `open()` had installed — and sent the write to the real
   * capture server. It was refused there, a fixture's order not existing in a real store, so
   * `pullCopy` threw; `onPull` re-reads only on its success path, so nothing re-read and the payload
   * never moved. The case failed for a reason unrelated to what it tested, and a write came one
   * refusal from a live store. These stubs reach nothing. */
  /* THE HUB'S OTHER READ, UNCONDITIONALLY. `OrdersHub` asks `GET /inventory` on mount beside
     `GET /orders` — it needs the cards to resolve a line to copies — and this file stubbed it
     only inside the `boot` branch below, so every case that did not ask for a boot header sent
     that read to the capture port. `sealEveryTest` named it. Registered BEFORE the branch, so
     the boot variant is the newer handler and still wins where it is asked for. */
  await page.route(/\/inventory$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{"cards": {}}' })
  })

  if (options.boot !== undefined) {
    const withBoot = (body: string) => async (route: Route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        /* Cross-origin, so the browser hides the id from JS without the second header. The real
           server sends both; sending only the value reproduces a server that never announced its
           restart. */
        headers: {
          'X-Pkmnscan-Boot': options.boot!(),
          'Access-Control-Expose-Headers': 'X-Pkmnscan-Boot',
        },
        body,
      })
    }
    await page.route(/\/status$/, withBoot(JSON.stringify({ cards: 0, next_index: {} })))
    await page.route(/\/inventory$/, withBoot(JSON.stringify({ cards: {} })))
  }

  await page.route(/\/orders$/, async (route) => {
    wire.push({ method: route.request().method(), path: new URL(route.request().url()).pathname, body: null })
    const chosen = typeof options.orders === 'function' ? options.orders() : options.orders
    const boot = options.boot?.()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers:
        boot === undefined
          ? undefined
          : { 'X-Pkmnscan-Boot': boot, 'Access-Control-Expose-Headers': 'X-Pkmnscan-Boot' },
      body: JSON.stringify(chosen ?? oneOpenOrder()),
    })
  })

  await page.goto(VIEW_ROUTE)
  await expect(page.locator(VIEW)).toBeVisible()
  return wire
}

/* -------------------------------------------------------------------------------------- 1 */

/* NOTHING HERE MAY REACH THE CAPTURE SERVER — `app/tests/shell.ts` carries the argument. This
   file already stubbed the shell's own `/status` by hand; the shared call replaces it so there
   is one spelling of the rule, and adds what a hand-written stub could not: a catch-all that
   REFUSES and names anything else that gets out. The call has to sit above the file's first
   `test.beforeEach`, which is what `make docs-audit`'s `spec seal` row checks. */
sealEveryTest()

test('the route resolves, and the nav offers it under its own chord', async ({ page }) => {
  await open(page)

  /* THE DULLEST ASSERTION IN THE FILE AND THE ONE THAT PAYS FOR IT. A screen absent from
     `App.tsx`'s ROUTES table renders the unresolved-hash page instead, which nothing else in
     this repo can tell — harness, lint, typecheck and docs-audit all stay green over it. */
  await expect(page.locator(VIEW)).toBeVisible()

  /* The chord is still `,O`, and it is still printed on the nav link — the keycap's own class
     went with the rebuild, so this reads the `kbd` inside the link for this route. */
  await expect(page.locator('a.app-nav-link[href="#/orders"] kbd')).toHaveText(',O')
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

  /* THE RECEIPT IS A TOAST NOW, which is the owner's ruling and changes nothing this case is
     about: it is still composed at the moment of the press, it still has to name the place the
     operator just walked to, and the way back still has to be on it. */
  const receipt = page.locator('.bn-toast-receipt')
  await expect(receipt).toContainText('Box 3 · Section 2 · Card 17')
  await expect(receipt).not.toContainText('departed')

  /* THE WAY BACK IS ON THE RECEIPT AND NOT IN THE ROW, and that is forced rather than chosen: a
     successful pull marks the copy sold, the resolver stops offering it, and an Undo drawn
     inside the row would unmount with it. */
  await expect(receipt.locator('button.bn-toast-action')).toHaveText('Undo')
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
  const openWell = page.locator('main.orders .bn-head-actions').getByRole('button', { name: 'Add orders' })
  await expect(openWell).toHaveAttribute('aria-expanded', 'false')
  await openWell.click()
  await expect(page.locator('.orders-paste')).toHaveCount(1)

  /* AND THE FETCH IS INSIDE IT, not in the page header. It is the same errand with the copying
     done for you — `POST /orders/fetch` answers exactly the body the ingest accepts — so the
     screen has one way in and two sources rather than two ways in. */
  await expect(page.locator('.orders-paste').getByRole('button', { name: 'Fetch from TCGplayer' })).toHaveCount(1)

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
  await page.locator('.orders-paste').getByRole('button', { name: 'Read this paste' }).click()

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

/* THREE OF MAIN'S CASES ARE DELETED HERE, WITH THE FEATURES THEY COVERED (D96).

   `the fetch is two presses: the window by status, then only the ticked statuses (D91)` — the
   owner ruled the two-press flow out: the press asks and takes in the same gesture. D91's real
   requirement, that somebody NAME the statuses rather than the server guess them, is kept: the
   single press reads them off the preview and sends back exactly what came out. The case that
   survives is the one below, over the cap and what a press leaves behind.

   `every open order offers the walk, and the header offers all of them at once` and `a ledger
   with nothing open offers no walk at all` — both assert the entry points into D90's envelope
   walk on `#/inventory?order=`, a screen mode this product does not draw. They went with
   `order-walk.spec.ts` and for its reason: a spec that can never pass is not coverage.

   All three are in main's history and come back whole if the walk is ever built here. */



/* -------------------------------------------------------------------------------------- 9 */

test('a fetch the cap cut short says how many it left, and an empty one still re-reads', async ({
  page,
}) => {
  const wire = await open(page, {
    fetched: { orders: [], matched: 130, skipped_known: 30, detailed: 0, remaining: 100 },
  })
  const reads = () => wire.filter((one) => one.path.endsWith('/orders') && one.method === 'GET').length
  const mounted = reads()
  /* The way in is the header's control, as every other case on this screen opens it. */
  await page.locator('main.orders .bn-head-actions').getByRole('button', { name: 'Add orders' }).click()
  /* ONE PRESS, DRIVEN AS ONE. Main reached this state through a status step — check, tick, fetch
     — and the owner ruled that step out. What the press does underneath is still two calls, and
     the assertion below is what keeps the second one honest: the statuses it sends are the ones
     the preview answered, never a list this screen composed. */
  await page.locator('.orders-paste').getByRole('button', { name: 'Fetch from TCGplayer' }).click()

  await expect
    .poll(() => wire.filter((one) => one.path.endsWith('/orders/fetch')).length)
    .toBe(2)
  const asked = wire.filter((one) => one.path.endsWith('/orders/fetch'))
  expect((asked[0]?.body as { preview?: boolean }).preview).toBe(true)
  expect((asked[1]?.body as { statuses?: string[] }).statuses).toEqual([
    'Shipped',
    'Cancelled',
    'Ready to Ship',
  ])

  /* NOTHING TO INGEST IS NOT NOTHING TO SAY. The note names the cap's leftover as a number and
     tells the operator the next press picks it up; and the screen re-reads the ledger anyway,
     because "nothing new for me" and "nothing moved" are different facts. */
  /* THE COUNTS MOVED OUT OF THE PASTE NOTE AND INTO A RECEIPT OF THEIR OWN. Same figures, same
     rule about absence — a clause is drawn only where its number is real, because a rendered
     `0 remaining` is a claim this wire cannot always make. */
  await expect(page.locator('.orders-receipt')).toContainText('100 remaining')
  await expect(page.locator('.orders-receipt')).toContainText('30 already in the ledger')
  expect(wire.filter((one) => one.path.endsWith('/orders/ingest'))).toHaveLength(0)
  await expect.poll(reads).toBe(mounted + 1)
})

/* -------------------------------------------------------------------------------------- 10
 *
 * THE WALK'S SECOND FIGURE, OVER THE ONLY PAIR OF ARRAYS THAT CAN ANSWER IT.
 *
 * This case exists because the figure was written the obvious way first and the obvious way is
 * ALWAYS ZERO. `open` is the ledger's answer to "does this still owe copies"
 * (`server/capture_server.py:_order_row`), so an order leaves `open` the instant its last copy is
 * pulled — a count of finished orders taken over `open` can never be anything but 0, and the walk
 * is where that is least visible, because the rows vanish along with it. It was caught by pulling
 * a real copy on the owner's own store and watching the pill stay away, which is a measurement
 * nothing on the commit path can repeat. This is that measurement, made repeatable.
 *
 * BOTH DIRECTIONS ARE ASSERTED. A store with one order finished draws `1 of 2`, and a store with
 * none finished draws no pill at all rather than `0 of 1` — the walk starts in the none-finished
 * state every single time, and a figure that reads zero on arrival is not one anybody acts on. */

test('the walk counts the orders it was started over, and the figure moves as one is finished', async ({
  page,
}) => {
  const SECOND = 'B58DDD-24C44'
  const secondKey = `TCGplayer:${SECOND}`
  const secondLine = () => line({ order: SECOND, order_key: secondKey, picks: [pick({ index: 22, capture_id: 'cap-b' })] })

  /* TWO OPEN ORDERS AND ONE THE LEDGER FINISHED BEFORE ANY OF THIS, and the third one is the
     whole point of the fixture. Without it a frozen denominator and the ledger's lifetime pair
     agree — two orders, one done, `1 of 2` either way — and this case would pass against the
     figure it was written to replace. With it they part: the walk is over TWO, and the ledger
     knows THREE. A store with sales history is the normal case and the one nothing had ever
     rendered here. It carries no resolution entry, because a finished order has nothing left for
     the resolver to offer, which is what one really looks like on this wire. */
  const HISTORY = 'C99EEE-31A77'
  const history = order({
    key: `TCGplayer:${HISTORY}`,
    number: HISTORY,
    recorded: 1,
    open: false,
    progress: [{ sku: SKU, wanted: 1, recorded: 1, outstanding: 0, over: 0, copies: [], pulled: [], at: null }],
  })

  const both = payloadOf(
    [order(), order({ key: secondKey, number: SECOND }), history],
    [
      { key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] },
      { key: secondKey, number: SECOND, complete: false, outstanding: 1, lines: [secondLine()] },
    ],
  )

  /* AND THE SAME WORLD WITH THE FIRST ONE PULLED. `open` is the ledger's answer to "does this
     still owe copies", so the moment its last copy is recorded the order LEAVES `open` — which
     is exactly what the numerator has to survive. */
  const afterPull = payloadOf(
    [order({ recorded: 1, open: false }), order({ key: secondKey, number: SECOND }), history],
    [{ key: secondKey, number: SECOND, complete: false, outstanding: 1, lines: [secondLine()] }],
  )

  let served = both
  await open(page, { orders: both })
  /* Registered after `open`, so it wins: Playwright matches the most recent route first. */
  await page.route(/\/orders$/, async (route) => {
    if (route.request().method() !== 'GET') return route.fallback()
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(served) })
  })

  await page.locator('main.orders').getByRole('button', { name: 'Walk the boxes' }).click()

  /* NONE FINISHED IS WHERE EVERY WALK STARTS, and a figure that reads 0 on arrival is not one
     anybody acts on — so there is no pill yet. */
  await expect(page.locator('.orders-walk-figure')).toContainText('still to pull')
  await expect(page.locator('.orders-walk-figure .bn-pill')).toHaveCount(0)

  served = afterPull
  await page.locator('.orders-walk button.orders-pull').first().click()

  /* ONE, OUT OF THE PASS AND NOT OUT OF THE LEDGER. Counted over `open` this reads 0 by
     construction — the order left `open` the instant its copy was recorded — which is the defect
     the previous denominator was chosen to avoid. Counted over the ledger's lifetime it would say
     2, because the third order was finished before any of this began. The set frozen when the walk
     was entered is what makes it neither, and the third order is what makes those two answers
     different enough for this line to tell them apart.

     A COUNT AND NOT A FRACTION, deliberately (D96, amended). Orders arrive while you walk, so a
     pass with everything in it pulled would draw `2 of 2` beside a head still naming work to do —
     a figure that has reached its own denominator says finished, and no wording rescues that.
     `complete` and not `fully pulled` because an order reaches `done` by routes this screen never
     sees: a sale on `#/inventory`, an ingest, another device. */
  await expect(page.locator('.orders-walk-figure .bn-pill')).toHaveText('1 order complete in this pass')

  /* AND A TOGGLE IS NOT THE END OF THE PASS. `walkKeys` is drawn from `open`, and an order leaves
     `open` the instant its last copy is recorded — so a set frozen again on re-entry can never
     contain an order this pass has already finished, and the figure would reset to nothing, zero
     by construction, which is the same shape as the defect this whole case is about. Measured
     before the pass was held: the pill was GONE after this round trip. `By order` is a reachable
     press, not a hypothetical: it is on the toolbar, and `Orders.tsx`'s own order rows use it. */
  await page.locator('main.orders').getByRole('button', { name: 'By order' }).click()
  await page.locator('main.orders').getByRole('button', { name: 'Walk the boxes' }).click()
  await expect(page.locator('.orders-walk-figure .bn-pill')).toHaveText('1 order complete in this pass')
})

/* The other direction, and its own world rather than a second navigation inside the case above:
   `open` registers this screen's routes on the page it is given, so a case that calls it twice is
   asserting against whichever handler won, not against the payload it just named. */
test('the walk draws no finished-order figure before one is finished', async ({ page }) => {
  await open(page)
  await page.locator('main.orders').getByRole('button', { name: 'Walk the boxes' }).click()

  await expect(page.locator('.orders-walk-figure')).toContainText('still to pull')
  await expect(page.locator('.orders-walk-figure .bn-pill')).toHaveCount(0)
})


/* -------------------------------------------------------------------------------------- 11 */

/* A CAPTURE SERVER THAT RESTARTED ENDS THE WALK'S PASS, and this is the only case in the suite that
 * drives the boot header at all.
 *
 * `server.ts:noteBoot` reads `X-Pkmnscan-Boot` off every response: the first non-empty value seeds
 * `lastBoot` silently, and a DIFFERENT one fires every `onServerBoot` listener. Two reads with two
 * ids is the whole mechanism, and no spec had ever served one — so the listener that clears the
 * shipping batch (D73) had never been exercised on purpose either.
 *
 * WHY THE PASS MUST GO. `walkKeys` is the orders the walk was started over. A server that restarted
 * may have taken orders since, so a figure counted against the old set describes a sitting that is
 * over — and unlike a stale batch it is not visibly broken, it is a smaller number that looks fine.
 *
 * THE THIRD ORDER IS NOT DECORATION. With only two, pulling the second leaves nothing open,
 * `buildWalk` returns no rows, and `WalkView` draws its EmptyState BEFORE the head — so the figure
 * would be absent because the whole head is, and the assertion would pass with the clear reverted.
 * Observed doing exactly that. */
test('a capture server restart ends the walk pass, so the figure stops describing an old sitting', async ({
  page,
}) => {
  const SECOND = 'B58DDD-24C44'
  const secondKey = `TCGplayer:${SECOND}`
  const secondLine = () => line({ order: SECOND, order_key: secondKey, picks: [pick({ index: 22, capture_id: 'cap-b' })] })
  const THIRD = 'D71FFF-52B99'
  const thirdKey = `TCGplayer:${THIRD}`
  const thirdLine = () => line({ order: THIRD, order_key: thirdKey, picks: [pick({ index: 23, capture_id: 'cap-c' })] })
  const thirdResolved = { key: thirdKey, number: THIRD, complete: false, outstanding: 1, lines: [thirdLine()] }
  /* A FOURTH ORDER, so the walk survives the pull that happens AFTER the restart. `WalkView` returns
     its EmptyState before the head when `walk.rows` is empty, so a pull leaving nothing open takes
     `.orders-walk-figure` off the screen — and the new-pass assertion at the end would then be
     asserting about a head that is not there. Three orders survive the restart; the fourth is what
     gives the new pass something to be a pass over. */
  const FOURTH = 'E82AAA-63C11'
  const fourthKey = `TCGplayer:${FOURTH}`
  const fourthLine = () => line({ order: FOURTH, order_key: fourthKey, picks: [pick({ index: 24, capture_id: 'cap-e' })] })
  const fourthResolved = { key: fourthKey, number: FOURTH, complete: false, outstanding: 1, lines: [fourthLine()] }

  const all = payloadOf(
    [order(), order({ key: secondKey, number: SECOND }), order({ key: thirdKey, number: THIRD }), order({ key: fourthKey, number: FOURTH })],
    [
      { key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] },
      { key: secondKey, number: SECOND, complete: false, outstanding: 1, lines: [secondLine()] },
      thirdResolved,
      fourthResolved,
    ],
  )
  const oneDone = payloadOf(
    [order({ recorded: 1, open: false }), order({ key: secondKey, number: SECOND }), order({ key: thirdKey, number: THIRD }), order({ key: fourthKey, number: FOURTH })],
    [{ key: secondKey, number: SECOND, complete: false, outstanding: 1, lines: [secondLine()] }, thirdResolved, fourthResolved],
  )
  const twoDone = payloadOf(
    [
      order({ recorded: 1, open: false }),
      order({ key: secondKey, number: SECOND, recorded: 1, open: false }),
      order({ key: thirdKey, number: THIRD }),
      order({ key: fourthKey, number: FOURTH }),
    ],
    [thirdResolved, fourthResolved],
  )
  const threeDone = payloadOf(
    [
      order({ recorded: 1, open: false }),
      order({ key: secondKey, number: SECOND, recorded: 1, open: false }),
      order({ key: thirdKey, number: THIRD, recorded: 1, open: false }),
      order({ key: fourthKey, number: FOURTH }),
    ],
    [fourthResolved],
  )

  let served = all
  let boot = 'boot-one'
  /* THE MOUNT READ CARRIES THE SEED, which is why the id goes through `open` rather than a route
     registered after it: `noteBoot` says nothing about the first header it sees, so a seed attached
     later would make the first press of this case the silent one. */
  await open(page, { orders: () => served, boot: () => boot })

  /* WAIT FOR THE ORDERS, NOT THE SHELL. The freeze reads `open` at the instant the mode flips, so a
     toggle pressed before `GET /orders` has answered captures an EMPTY set — and every figure after
     it is 0, which reads exactly like the clear working and made this case flap 1 run in 3. */
  await expect(page.locator('main.orders')).toContainText('open orders')

  await page.locator('main.orders').getByRole('button', { name: 'Walk the boxes' }).click()
  await expect(page.locator('.orders-walk button.orders-pull').first()).toBeVisible()
  served = oneDone
  await page.locator('.orders-walk button.orders-pull').first().click()

  /* The pass survives a read carrying the SAME id — which is what makes the next assertion about the
     restart rather than about re-reading at all. */
  await expect(page.locator('.orders-walk-figure .bn-pill')).toHaveText('1 order complete in this pass')

  /* AND THE SECOND PULL IS WHERE THE RESTART LANDS. A mode toggle is client-side and costs no
     request, so it can never carry a new id; the read after a PULL is the one that does, and it is
     the realistic moment — the server went away while the operator was working. */
  boot = 'boot-two'
  served = twoDone
  await page.locator('.orders-walk button.orders-pull').first().click()

  /* THE FIGURE IS ABSENT, NOT ZERO. `walkKeys` is null and a null set draws nothing rather than
     falling back to a lifetime count. Without the clear this reads `2 orders complete in this pass`:
     a true count over a sitting that ended, against a server that is no longer the one it started
     against. The head is still on screen — the third order keeps it there — so the absence is about
     the pass and not about the walk. */
  /* THE RESTART WAS NOTICED, asserted POSITIVELY and before anything about the figure. `App.tsx`
     raises this toast from the same `onServerBoot` the clear hangs off, so it is independent
     evidence that the listener ran. Without it every assertion below is about an ABSENCE, and an
     absence has many causes — a case reading only "the pill is gone" passes when it is gone for a
     reason nobody intended. */
  await expect(page.getByText('Server restarted')).toBeVisible()

  await expect(page.locator('.orders-walk-figure')).toContainText('still to pull')
  await expect(page.locator('.orders-walk-figure .bn-pill')).toHaveCount(0)

  /* AND A NEW PASS COUNTS FROM ZERO, which is the positive form of the same claim. The cleared pass
     is not merely absent: the next walk freezes a fresh set over what is open NOW, and the first
     order finished inside it reads one. Without this the case proves a figure can vanish and says
     nothing about the operator getting a working one back. */
  await page.locator('main.orders').getByRole('button', { name: 'By order' }).click()
  await page.locator('main.orders').getByRole('button', { name: 'Walk the boxes' }).click()
  await expect(page.locator('.orders-walk button.orders-pull').first()).toBeVisible()
  served = threeDone
  await page.locator('.orders-walk button.orders-pull').first().click()
  await expect(page.locator('.orders-walk-figure .bn-pill')).toHaveText('1 order complete in this pass')
})

