import { test, expect, type Page, type Route } from '@playwright/test'
import { sealEveryTest } from './shell'
import { line, order, payloadOf, pick, place } from './routeFixtures'

import type { OrderRow, OrdersPayload, ResolvedLine, ResolvedOrder } from '../src/types'

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

/* `place`, `pick`, `line`, `order` and `payloadOf` moved to `./routeFixtures` (D194's copy-
 * ratchet fixtures) so `copy-budget.spec.ts` can build the same `#/orders` shapes without a
 * second, drifting copy. `ORDER_NUMBER`/`SKU` above still match the values baked into those
 * builders' defaults, which is what keeps every case below reading exactly as it did. */

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
    /* THE ALL-STATUSES, SKIP-KNOWN BODY (`D193`) — the ordinary press on
       a device that has never narrowed the picker. A function so a case can answer differently
       across the loop's batches (`remaining > 0` then `0`); the argument is which call this is,
       0-indexed. Defaults to one batch, nothing left, no names — the steady-state append. */
    allStatuses?: unknown | ((call: number) => unknown)
    /* `POST /orders/names` — never sent by the narrowed path, only by the all-statuses loop when
       a batch's `names` is non-empty. */
    names?: unknown
    /* THE CAPTURE SERVER'S BOOT ID, for the one case that is about a restart. A function so a case
       can change it between reads. See the route below for why it has to be every GET. */
    boot?: () => string
    /* `POST /orders/reconcile-backlog` (D203), `{preview: true}` half.
       Defaults to nothing to reconcile, so every case that does not ask for this stays exactly
       as it was before the route existed. */
    reconcilePreview?: unknown
    /* The same route's press half. */
    reconcile?: unknown
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

  /* THE FETCH ROUTE, IN THREE BODIES (D91, and `all_statuses` since `D193`).
     Registered before `/orders$` like every write-shaped route here: the read regex is
     the looser one. A preview body answers the window by status; a `statuses` body answers the
     ingest-shaped orders plus the four counts (the narrowed path); an `all_statuses` body is the
     ordinary press's own loop and answers the same shape plus `names`. Recorded, not performed —
     nothing here reaches TCGplayer, and nothing may: this file runs against whatever real server
     is listening on this checkout's port. */
  let allStatusesCalls = 0
  await page.route(/\/orders\/fetch$/, async (route) => {
    const body = route.request().postDataJSON() as { preview?: boolean; all_statuses?: boolean }
    wire.push({ method: route.request().method(), path: new URL(route.request().url()).pathname, body })
    const answer =
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
        : body.all_statuses === true
          ? (typeof options.allStatuses === 'function'
              ? (options.allStatuses as (call: number) => unknown)(allStatusesCalls++)
              : (options.allStatuses ?? { orders: [], matched: 0, skipped_known: 0, detailed: 0, remaining: 0, names: [] }))
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
            })
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(answer) })
  })

  await page.route(/\/orders\/names$/, async (route) => {
    wire.push({
      method: route.request().method(),
      path: new URL(route.request().url()).pathname,
      body: route.request().postDataJSON(),
    })
    const body = route.request().postDataJSON() as { names?: unknown[] }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        options.names ?? {
          named: body.names?.length ?? 0,
          unchanged: 0,
          unknown: 0,
          total: body.names?.length ?? 0,
          summary: '',
        },
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
  /* THE HUB'S OTHER READ, UNCONDITIONALLY. `OrdersHub` asks `POST /inventory/copies` after
     every `GET /orders` lands — it needs the cards to resolve a line to copies, scoped to the
     SKUs the ledger just named (DEBT27, site 1) — and this file stubbed the old
     whole-store `GET /inventory` only inside the `boot` branch below, so every case that did
     not ask for a boot header sent that read to the capture port. `sealEveryTest` named it.
     Registered BEFORE the branch, so the boot variant is the newer handler and still wins
     where it is asked for.

     A WRITE-SHAPED ROUTE, REGISTERED BEFORE THE LOOSER READ REGEXES — `/orders$/`'s own rule
     one register down. `/inventory\/copies$/` is a POST and could not collide with `/orders$/`
     regardless, but the ordering is kept uniform with every other route in this file rather
     than argued case by case. */
  await page.route(/\/inventory\/copies$/, async (route) => {
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
    await page.route(/\/inventory\/copies$/, withBoot(JSON.stringify({ cards: {} })))
  }

  /* D113's three writes. Registered BEFORE `/orders$` like every other write-shaped route here,
     because the read regex is the looser one and would otherwise swallow them. */
  for (const [pattern, answer] of [
    [/\/orders\/fill$/, { undone: false, order_key: '', sku: '', moved: 1, recorded: 1, by_hand: 1, outstanding: 0, reason: 'sealed' }],
    [/\/orders\/line-kind$/, { order_key: '', sku: '', kind: 'sealed' }],
    [/\/orders\/close$/, { undone: false, orders: 1, moved: 1, lines: 1, reason: 'shipped_elsewhere', still_open: 0 }],
  ] as const) {
    await page.route(pattern, async (route) => {
      wire.push({
        method: route.request().method(),
        path: new URL(route.request().url()).pathname,
        body: route.request().postDataJSON(),
      })
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(answer) })
    })
  }

  /* D203: registered BEFORE `/orders$`, `/orders/fetch$`'s own rule —
     the read regex is the looser one. Defaults to nothing to reconcile so `ReconcileBacklogPanel`
     draws nothing, keeping every case that does not ask for this one exactly as it was. */
  await page.route(/\/orders\/reconcile-backlog$/, async (route) => {
    const body = route.request().postDataJSON() as { preview?: boolean; cutoff?: string }
    wire.push({ method: route.request().method(), path: new URL(route.request().url()).pathname, body })
    const answer =
      body.preview === true
        ? (options.reconcilePreview ?? { cutoff: '2026-01-01', total: 0, breakdown: [], writes_nothing: true })
        : (options.reconcile ?? {
            cutoff: '2026-01-01',
            orders: 0,
            moved: 0,
            lines: 0,
            closed: [],
            reason: 'shipped_elsewhere',
            still_open: 0,
          })
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(answer) })
  })

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

  /* `POST /orders/picks` — the real-picks tier `Orders.tsx` fetches for the buyer or order
   *  actually open, and once for the whole walk. EVERY CASE IN THIS FILE ALREADY WRITES ITS
   *  `picks` INTO THE `/orders` FIXTURE ABOVE, so this stub answers from that SAME payload
   *  rather than needing a second one per case: it echoes back exactly the resolved orders
   *  whose key was asked for. A case testing the split itself stubs this route by hand,
   *  after `open()`, the same way any other default here is overridden. */
  await page.route(/\/orders\/picks$/, async (route) => {
    const body = route.request().postDataJSON() as { keys?: string[] }
    wire.push({ method: route.request().method(), path: new URL(route.request().url()).pathname, body })
    const chosen = typeof options.orders === 'function' ? options.orders() : options.orders
    const source = (chosen ?? oneOpenOrder()).resolution.orders
    const wanted = new Set(body.keys ?? [])
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ orders: source.filter((one) => wanted.has(one.key)) }),
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

/* ============================================================== D113: the three closes ==== */

test('a line no pull can reach offers the two presses that can, and each sends its own body', async ({
  page,
}) => {
  /* THE CASE THE WHOLE ENTRY IS ABOUT. A `sku_unseen` line has no card in the store and never
     will, so `POST /orders/pull` — which needs a capture_id — can never close it. Before D113
     the remedy row was the end of the road and three real orders sat open behind it. */
  const unseen = line({ reason: 'sku_unseen', fulfilled: 0, outstanding: 1, on_hand: 0, picks: [] })
  const wire = await open(page, {
    orders: payloadOf(
      [order()],
      [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [unseen] }],
    ),
  })

  const stand = page.locator('.orders-standdown').first()
  await expect(stand).toBeVisible()

  /* THE CLASSIFICATION IS A SEPARATE PRESS FROM THE FILL, and the shipping lane is why: a sealed
     product must be classifiable BEFORE it ships, or the routing answer arrives after it stopped
     mattering. Two controls here is the assertion, not an accident of layout. */
  await stand.getByRole('button', { name: 'Sealed product' }).click()
  await expect
    .poll(() => wire.filter((one) => one.path === '/orders/line-kind').length)
    .toBe(1)
  expect(wire.find((one) => one.path === '/orders/line-kind')?.body).toEqual({
    source: 'TCGplayer',
    number: ORDER_NUMBER,
    sku: SKU,
    kind: 'sealed',
  })

  /* The fill names a COUNT and a REASON and no copy at all — there is no capture id to send,
     which is the entire reason this route exists beside `/orders/pull`. */
  await stand.getByRole('button', { name: /shipped/i }).click()
  await expect.poll(() => wire.filter((one) => one.path === '/orders/fill').length).toBe(1)
  const fill = wire.find((one) => one.path === '/orders/fill')?.body as Record<string, unknown>
  expect(fill).toEqual({
    source: 'TCGplayer',
    number: ORDER_NUMBER,
    sku: SKU,
    count: 1,
    reason: 'off_system',
  })
  /* NO capture_id, NO targets, NO box, NO index. A hand-fill that carried a position would be
     claiming to know which physical card went, which is exactly what it does not know. */
  expect(Object.keys(fill)).not.toContain('targets')
  expect(Object.keys(fill)).not.toContain('capture_id')
})

test('a copy that left by the sale door can be recorded, and a line that will not ship can be closed', async ({
  page,
}) => {
  /* THE WALK'S OWN EDGE CASE, reproduced against the real store on 2026-09-06: mark one copy
     sold on `#/inventory` while an order wants three, pull the other two through the walk, and
     the line lands at `no_copies_on_hand` with `outstanding` 1 and no copy any pull can reach.
     `#/inventory`'s sale never touches the ledger (D63), so nothing counted the first copy.

     `no_copies_on_hand` carries THREE truths — this order's copy went out by the sale, another
     buyer took the last one, or it was retired damaged — so both answers are offered and
     neither is assumed. */
  const gone = line({ reason: 'no_copies_on_hand', fulfilled: 0, outstanding: 1, on_hand: 0, sold: 3, picks: [] })
  const wire = await open(page, {
    orders: payloadOf(
      [order()],
      [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [gone] }],
    ),
  })

  const stand = page.locator('.orders-standdown').first()
  await expect(stand).toBeVisible()

  await stand.getByRole('button', { name: /already sent/i }).click()
  await expect.poll(() => wire.filter((one) => one.path === '/orders/fill').length).toBe(1)
  expect(wire.find((one) => one.path === '/orders/fill')?.body).toEqual({
    source: 'TCGplayer',
    number: ORDER_NUMBER,
    sku: SKU,
    count: 1,
    /* NOT `off_system`. That means this store never photographed the card; this one it did, and
       the row has to say which so the next reader can tell a bookkeeping gap from a blind spot. */
    reason: 'sold_separately',
  })

  /* THE ONLY PLACE `not_shipping` IS REACHABLE. Without this press it is a server capability no
     screen can reach, which is the rule this whole change cites — broken by the change itself.

     IT SENDS `lines`, NOT `orders`, and that is the assertion rather than a detail: the
     order-shaped scope stands EVERY line of the order down, which on a multi-line order would
     close lines nobody answered for. */
  await stand.getByRole('button', { name: /isn.t shipping/i }).click()
  await expect.poll(() => wire.filter((one) => one.path === '/orders/close').length).toBe(1)
  expect(wire.find((one) => one.path === '/orders/close')?.body).toEqual({
    lines: [{ source: 'TCGplayer', number: ORDER_NUMBER, sku: SKU }],
    reason: 'not_shipping',
  })
})

test('a refunded line on a multi-line order is closed alone, and the siblings are not named', async ({
  page,
}) => {
  /* THE CASE THE FIRST BUILD HAD NO PRESS FOR. It drew "It isn't shipping" only where the order
     had ONE line, because the wire was order-shaped and closing a three-line order to answer for
     one refunded line is worse than offering nothing. Both scopes exist now, so the button is
     unconditional and the BODY is what keeps the siblings safe. */
  const gone = line({ reason: 'no_copies_on_hand', fulfilled: 0, outstanding: 1, on_hand: 0, sold: 2, picks: [] })
  const sibling = { ...line().line, sku: '9197754', name: 'Sunrise' }
  const wire = await open(page, {
    orders: payloadOf(
      [order({ lines: [gone.line, sibling] })],
      [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [gone] }],
    ),
  })

  const stand = page.locator('.orders-standdown').first()
  await expect(stand).toBeVisible()
  await stand.getByRole('button', { name: /isn.t shipping/i }).click()
  await expect.poll(() => wire.filter((one) => one.path === '/orders/close').length).toBe(1)

  const body = wire.find((one) => one.path === '/orders/close')?.body as { lines: { sku: string }[] }
  expect(body.lines).toHaveLength(1)
  expect(body.lines[0]?.sku).toBe(SKU)
  /* THE SIBLING IS NOT IN THE BODY AT ALL — not sent and refused, simply never named. */
  expect(JSON.stringify(body)).not.toContain('9197754')
  expect(Object.keys(body)).not.toContain('orders')
})

test('a short line offers no hand-fill, because its copies are still in the boxes', async ({ page }) => {
  /* THE BOUNDARY. `short` means copies are on hand or spoken for, and the remedy really is to
     pull them — a fill button here would invite closing a line whose cards are sitting in box 3,
     and `fulfilled` would then count a copy still on the shelf. */
  const short = line({ reason: 'short', fulfilled: 0, outstanding: 2, on_hand: 1 })
  await open(page, {
    orders: payloadOf(
      [order()],
      [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 2, lines: [short] }],
    ),
  })
  await expect(page.locator(VIEW)).toBeVisible()
  await expect(page.locator('.orders-standdown')).toHaveCount(0)
})

test('a resolved line offers no stand-down, because its remedy is the pick rows', async ({ page }) => {
  /* THE OTHER HALF OF THE RULE. The presses are drawn ONLY where the remedy is a dead end;
     offering "I shipped this by hand" beside a line whose copies are sitting in box 3 is an
     invitation to close it without the walk, and `fulfilled` would then count a copy that is
     still on the shelf. */
  await open(page)
  await expect(page.locator('.orders-standdown')).toHaveCount(0)
})

test('an order the marketplace already shipped is proposed for stand-down, and the status only proposes', async ({
  page,
}) => {
  /* MEASURED 2026-09-06: 69 of the owner's 83 open orders were ones TCGplayer had already
     shipped, and because `resolve_all` walks oldest-first they were holding 31 physical copies
     away from the orders that still needed picking. */
  const shipped = order({ status: 'Shipped - In Transit' })
  const wire = await open(page, {
    orders: payloadOf(
      [shipped],
      [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] }],
    ),
  })

  const prompt = page.locator('.orders-backlog')
  await expect(prompt).toBeVisible()
  /* THE STATUS IS NAMED IN THE SENTENCE RATHER THAN ASSERTED AS A CATEGORY. The vocabulary was
     never published, so a screen that said "shipped orders" while matching something else would
     be the guess `order_transport.py` refuses to make, one layer up. */
  await expect(prompt).toContainText('Shipped - In Transit')

  await prompt.getByRole('button', { name: /Stand down/ }).click()
  await expect.poll(() => wire.filter((one) => one.path === '/orders/close').length).toBe(1)
  expect(wire.find((one) => one.path === '/orders/close')?.body).toEqual({
    orders: [{ source: 'TCGplayer', number: ORDER_NUMBER }],
    reason: 'shipped_elsewhere',
  })
})

test('a Ready to Ship order is never proposed for stand-down', async ({ page }) => {
  /* THE PRESS MAY NOT REACH LIVE WORK. `open()`'s default order is Ready to ship, so the prompt
     must not draw at all — a bulk control that swept in the orders you still have to pick would
     be worse than the backlog it exists to clear. */
  await open(page)
  await expect(page.locator('.orders-backlog')).toHaveCount(0)
})

test('a status this rule does not recognise is left open rather than swept in', async ({ page }) => {
  /* THE FAIL-CLOSED PROPERTY, AND IT IS THE ONE THIS CONTROL LIVES OR DIES BY. The first build
     matched the NEGATIVE — `status !== 'Ready to Ship'` — which is the open-ended set D113
     refuses on the server, written by hand one layer up. It proposed a live order the moment a
     fixture spelled the status `Ready to ship` with a lower-case s.

     A word the marketplace has not used yet must land on the SAFE side by construction. The two
     directions are not symmetric: a shipped order left open is the status quo and is visible on
     screen, while a live order swept into a bulk close is a card that never gets picked. */
  for (const status of ['Cancelled', 'Pending', 'Awaiting Payment', 'ready to ship', '']) {
    const wire = await open(page, {
      orders: payloadOf(
        [order({ status })],
        [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] }],
      ),
    })
    await expect(page.locator(VIEW)).toBeVisible()
    await expect(page.locator('.orders-backlog')).toHaveCount(0)
    expect(wire.filter((one) => one.path === '/orders/close')).toEqual([])
  }
})

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

  /* A BUYER, A STREET AND AN EMAIL AT THE TOP LEVEL — the shape a real console copy has.
     `D193` moved ONE of the three across the boundary: the display
     NAME may cross, verbatim off the console's own `buyerName` spelling; the street and the
     email may not, and the screen has to SAY it dropped THOSE: a silent strip is
     indistinguishable on screen from a feed that never carried the field. */
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
        buyer: 'Ada Lovelace',
        lines: [{ sku: SKU, quantity: 1, name: 'Volcanion' }],
      },
    ],
  })

  /* THE NAME IS NOT DROPPED — ONLY THE STREET AND THE EMAIL ARE. */
  const dropped = page.locator('.orders-paste-dropped')
  await expect(dropped).not.toContainText('buyerName')
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

/* THE ORDINARY PRESS IS NOW ALL-STATUSES, SKIP-KNOWN, AND IT LOOPS
 * (`D193`). A device whose `statuses` filter is `null` — every device
 * that has never opened "Only these statuses…" — no longer previews at all: the owner's ruling
 * was that a one-time full backfill is followed forever after by an all-statuses append, so
 * `runFetch` asks `POST /orders/fetch {all_statuses: true, skip_known: true}` straight away and
 * repeats it while the wire reports `remaining > 0`. */

test('the ordinary press is one fetch, one ingest and one names call, with no preview', async ({
  page,
}) => {
  const wire = await open(page, {
    allStatuses: {
      orders: [{ source: 'TCGplayer', number: ORDER_NUMBER, placed_at: '2026-08-30', status: 'Ready to Ship', buyer: 'Ada Lovelace', lines: [{ sku: SKU, quantity: 1, name: 'Volcanion', unit_price: '11.88' }] }],
      matched: 1,
      skipped_known: 0,
      detailed: 1,
      remaining: 0,
      names: [{ source: 'TCGplayer', number: ORDER_NUMBER, buyer: 'Ada Lovelace' }],
    },
  })
  await page.locator('main.orders .bn-head-actions').getByRole('button', { name: 'Add orders' }).click()
  await page.locator('.orders-paste').getByRole('button', { name: 'Fetch from TCGplayer' }).click()

  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/fetch')).length).toBe(1)
  const sent = wire.find((one) => one.path.endsWith('/orders/fetch'))?.body as {
    all_statuses?: boolean
    skip_known?: boolean
    preview?: boolean
  }
  expect(sent.all_statuses).toBe(true)
  expect(sent.skip_known).toBe(true)
  expect(sent.preview).toBeUndefined()

  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/ingest')).length).toBe(1)
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/names')).length).toBe(1)
  expect(wire.find((one) => one.path.endsWith('/orders/names'))?.body).toEqual({
    names: [{ source: 'TCGplayer', number: ORDER_NUMBER, buyer: 'Ada Lovelace' }],
  })
})

test('a fetch the cap cut short loops, and the receipt names the batches and what is left', async ({
  page,
}) => {
  /* TWO BATCHES: the first reports `remaining: 2`, the second `remaining: 0` — the loop must
     fire a second call on its own rather than stopping at the first cap. */
  const wire = await open(page, {
    allStatuses: (call: number) =>
      call === 0
        ? { orders: [], matched: 25, skipped_known: 30, detailed: 0, remaining: 2, names: [] }
        : { orders: [], matched: 25, skipped_known: 30, detailed: 0, remaining: 0, names: [] },
  })
  const reads = () => wire.filter((one) => one.path.endsWith('/orders') && one.method === 'GET').length
  const mounted = reads()
  await page.locator('main.orders .bn-head-actions').getByRole('button', { name: 'Add orders' }).click()
  await page.locator('.orders-paste').getByRole('button', { name: 'Fetch from TCGplayer' }).click()

  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/fetch')).length).toBe(2)
  for (const call of wire.filter((one) => one.path.endsWith('/orders/fetch'))) {
    expect((call.body as { all_statuses?: boolean }).all_statuses).toBe(true)
  }

  /* THE RECEIPT NAMES THE BATCHES, AND SETTLES AT 0 REMAINING. */
  await expect(page.locator('.orders-receipt')).toContainText('2 batches')
  /* CUMULATIVE ACROSS BOTH BATCHES, like `detailed` and `named` — each batch skipped 30 already-
     known orders, so the receipt's running total is 60. */
  await expect(page.locator('.orders-receipt')).toContainText('60 already known')
  expect(wire.filter((one) => one.path.endsWith('/orders/ingest'))).toHaveLength(0)
  await expect.poll(reads).toBe(mounted + 1)
})

test('the two-years control sends the LastTwoYears range', async ({ page }) => {
  const wire = await open(page, {
    allStatuses: { orders: [], matched: 0, skipped_known: 0, detailed: 0, remaining: 0, names: [] },
  })
  await page.locator('main.orders .bn-head-actions').getByRole('button', { name: 'Add orders' }).click()
  await page.locator('.orders-paste').getByRole('button', { name: 'Fetch two years' }).click()

  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/fetch')).length).toBe(1)
  const sent = wire.find((one) => one.path.endsWith('/orders/fetch'))?.body as { range?: string }
  expect(sent.range).toBe('LastTwoYears')
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
    progress: [{ sku: SKU, wanted: 1, recorded: 1, outstanding: 0, over: 0, copies: [], pulled: [], at: null, by_hand: 0, reason: null, declared_kind: null, closed_at: null, closed_reason: null }],
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
  await page.locator('main.orders').getByRole('button', { name: 'By buyer' }).click()
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
  await page.locator('main.orders').getByRole('button', { name: 'By buyer' }).click()
  await page.locator('main.orders').getByRole('button', { name: 'Walk the boxes' }).click()
  await expect(page.locator('.orders-walk button.orders-pull').first()).toBeVisible()
  served = threeDone
  await page.locator('.orders-walk button.orders-pull').first().click()
  await expect(page.locator('.orders-walk-figure .bn-pill')).toHaveText('1 order complete in this pass')
})


/* ------------------------------------------------------------------------------------- 12
 *
 * D114: THE STATUS REQUIREMENT IS ANSWERED BY A TICK, AND THE TICK IS THIS DEVICE'S.
 *
 * Case 9 above pins the unchosen press — every status the preview answered, handed straight
 * back — and that is the behaviour an operator who never opens the picker keeps. What follows
 * is the other half: a device that HAS chosen, and the three things that go wrong quietly if
 * the narrowing is written the obvious way.
 *
 * THE TICK IS SEEDED THROUGH `localStorage` RATHER THAN CLICKED, on purpose. What is under test
 * is the press, and a case that ticked its way there would fail for a layout reason on the day
 * somebody moves the panel. The clicking half is the last case here.
 */

const FILTER_KEY = 'banchi.orders.fetch-filter'

/** A device that has already ticked. `statuses` is written exactly as the wire spelled them —
 *  D91's comparison is verbatim, and a case that folded them would be testing a fold that must
 *  never exist. */
async function remember(page: Page, statuses: string[] | null, skipKnown = false): Promise<void> {
  /* `asked: true` on every one of these: what they are about is the press a SETTLED device
     makes. The unsettled one is its own case at the end of this file, and the whole point of
     that flag is that these two are different presses. */
  await page.addInitScript(
    ([key, value]) => {
      try {
        /* eslint-disable-next-line no-restricted-syntax -- SEEDING THE VERY KEY UNDER TEST, in
           the one file whose subject it is. The rule bans the STORE so that a new device-local
           key lands in `app/src/deviceMemory.ts` in front of a reviewer, and this one did — see
           D114. Asserting how that key behaves means writing it, and a spec that reached it
           through the UI instead would be testing the panel's layout on the way past. One of
           a handful of `localStorage` calls in `app/tests`: `wide.spec.ts:withRail` seeds the
           shell's rail state before first paint (D123), and `inventory.spec.ts` seeds the
           walk's hide-sold chip and its box recency (D132). It said "the only" until
           2026-09-07 and "TWO" until 2026-09-10. */
        window.localStorage.setItem(key, value)
      } catch {
        /* a browser refusing storage reads as never chosen, which is the other case */
      }
    },
    [FILTER_KEY, JSON.stringify({ statuses, skipKnown, asked: true })] as [string, string],
  )
}

test('a remembered tick narrows the fetch, and the statuses go out as the wire spelled them', async ({
  page,
}) => {
  await remember(page, ['Cancelled', 'Ready to Ship'], true)
  const wire = await open(page)

  await page.locator('main.orders .bn-head-actions').getByRole('button', { name: 'Add orders' }).click()
  await page.locator('.orders-paste').getByRole('button', { name: 'Fetch from TCGplayer' }).click()

  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/fetch')).length).toBe(2)
  const asked = wire.filter((one) => one.path.endsWith('/orders/fetch'))
  expect((asked[0]?.body as { preview?: boolean }).preview).toBe(true)

  /* NARROWED, AND IN THE WINDOW'S OWN ORDER rather than the tick list's — the send is built by
     walking what the preview answered, which is the only thing that can be true about a window.
     `Shipped` is the window's largest status and is absent here, which is the whole point. */
  const sent = asked[1]?.body as { statuses?: string[]; skip_known?: boolean }
  expect(sent.statuses).toEqual(['Cancelled', 'Ready to Ship'])
  /* AND THE SECOND TOGGLE REACHES THE WIRE. `skip_known` has been on this route since D91 and
     nothing had ever sent it — a route no screen reached, which CLAUDE.md calls unfinished. */
  expect(sent.skip_known).toBe(true)
})

/* ------------------------------------------------------------------------------------- 13 */

test('a ticked status this window holds none of is named on screen, and is not sent', async ({ page }) => {
  /* `Awaiting Shipment` is not in the preview's three. The fetch cannot ask for it — a status no
     order carries matches nothing — so what is under test is that it is REPORTED rather than
     dropped on the floor, which is the same defect this entry exists to fix one register down. */
  await remember(page, ['Ready to Ship', 'Awaiting Shipment'])
  const wire = await open(page)

  await page.locator('main.orders .bn-head-actions').getByRole('button', { name: 'Add orders' }).click()
  await page.locator('.orders-paste').getByRole('button', { name: 'Fetch from TCGplayer' }).click()

  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/fetch')).length).toBe(2)
  const sent = wire.filter((one) => one.path.endsWith('/orders/fetch'))[1]?.body as { statuses?: string[] }
  expect(sent.statuses).toEqual(['Ready to Ship'])

  await expect(page.locator('.orders-receipt-absent')).toContainText('Awaiting Shipment')

  /* BOTH FIGURES, BECAUSE ONE OF THEM ALONE IS THE LIE. `matched` was drawn as "in the window"
     until D114, which is true only while a press takes the whole window; the preview's `total` is
     the denominator now and the filtered figure is a second clause beside it. */
  await expect(page.locator('.orders-receipt')).toContainText('370 in the window')
  await expect(page.locator('.orders-receipt')).toContainText('2 matched your statuses')
})

/* ------------------------------------------------------------------------------------- 14 */

test('every status ticked off refuses the press here, rather than letting the wire refuse it', async ({
  page,
}) => {
  /* An empty list is a real state and it is NOT the unchosen one. The wire answers it
     `statuses_required`, which is a true sentence about a body and a useless one about a choice
     somebody made on this screen — so the screen says what it is and points at the control. */
  await remember(page, [])
  const wire = await open(page)

  await page.locator('main.orders .bn-head-actions').getByRole('button', { name: 'Add orders' }).click()
  await page.locator('.orders-paste').getByRole('button', { name: 'Fetch from TCGplayer' }).click()

  await expect(page.locator('.orders-paste-note')).toContainText('Nothing to fetch')
  /* THE PREVIEW HAPPENED AND THE FETCH DID NOT. One free call, no detail call, nothing ingested. */
  const asked = wire.filter((one) => one.path.endsWith('/orders/fetch'))
  expect(asked).toHaveLength(1)
  expect((asked[0]?.body as { preview?: boolean }).preview).toBe(true)
  expect(wire.filter((one) => one.path.endsWith('/orders/ingest'))).toHaveLength(0)
})

/* ------------------------------------------------------------------------------------- 15 */

test('the picker is built from the preview alone, and unticking one narrows the next press', async ({
  page,
}) => {
  await remember(page, null)
  const wire = await open(page)
  await page.locator('main.orders .bn-head-actions').getByRole('button', { name: 'Add orders' }).click()

  /* UNCHOSEN SAYS SO. A device that has never opened this panel fetches everything, and the
     control names that rather than a count it would have to spend a call to know. */
  const control = page.locator('.orders-paste').getByRole('button', { name: /statuses/i })
  await expect(control).toHaveText(/All statuses/)
  await control.click()

  /* THREE ROWS AND NOT ONE MORE. Every string on this panel came off the preview; there is no
     status vocabulary anywhere in `app/`, and a row this test did not put on the wire would be
     one somebody coded here. */
  const rows = page.locator('.orders-statuses-list .orders-status')
  await expect(rows).toHaveCount(3)
  await expect(rows.nth(0)).toContainText('Shipped')
  await expect(rows.nth(1)).toContainText('Cancelled')
  await expect(rows.nth(2)).toContainText('Ready to Ship')

  /* THE FIRST UNTICK MATERIALISES THE LIST OUT OF THIS WINDOW — there is nowhere else strings
     could come from — and the two figures move together. */
  await rows.nth(0).locator('input[type=checkbox]').uncheck()
  await expect(page.locator('.orders-statuses-head')).toContainText('Taking 90 of 370')
  await expect(control).toHaveText(/2 of 3 statuses/)

  await page.locator('.orders-paste').getByRole('button', { name: 'Fetch from TCGplayer' }).click()
  /* THREE CALLS, NOT TWO, AND THAT IS THE PANEL PAYING ITS OWN WAY. Opening the picker counts the
     window once so the rows can be drawn; the press counts it again, because the send is built on
     the window as it stands at the moment of the press and never on what a panel saw earlier.
     Both are the free body — `writes_nothing: true`, no detail call — and the last of the three is
     the only one that details anything. */
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/fetch')).length).toBe(3)
  const calls = wire.filter((one) => one.path.endsWith('/orders/fetch'))
  expect(calls.slice(0, 2).every((one) => (one.body as { preview?: boolean }).preview === true)).toBe(true)
  const sent = calls[2]?.body as { statuses?: string[] }
  expect(sent.statuses).toEqual(['Cancelled', 'Ready to Ship'])
})

/* ------------------------------------------------------------------------------------- 16
 *
 * THE UNASKED DEVICE NO LONGER STOPS (`D193`, amending D114). D114's
 * measurement stands — 69 of 83 open orders were already shipped and held 31 physical copies —
 * but the owner's later ruling on the backfill (a one-time full history, then an all-statuses
 * append forever after) makes the picker's own ask moot for the ORDINARY press: an unasked
 * device gets exactly the same all-statuses, skip-known fetch an asked one gets, and the picker
 * is reached only by choice, from its own "Only these statuses…" control. */

test('an unasked device is never shown the picker on the ordinary press', async ({ page }) => {
  const wire = await open(page, {
    allStatuses: { orders: [], matched: 0, skipped_known: 0, detailed: 0, remaining: 0, names: [] },
  })
  await page.locator('main.orders .bn-head-actions').getByRole('button', { name: 'Add orders' }).click()
  await page.locator('.orders-paste').getByRole('button', { name: 'Fetch from TCGplayer' }).click()

  /* NO PANEL, NO PREVIEW. The picker is reached only by choosing to narrow, never by pressing
     the ordinary Fetch. */
  await expect(page.locator('.orders-statuses-ask')).toHaveCount(0)
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/fetch')).length).toBe(1)
  const sent = wire.find((one) => one.path.endsWith('/orders/fetch'))?.body as { preview?: boolean; all_statuses?: boolean }
  expect(sent.preview).toBeUndefined()
  expect(sent.all_statuses).toBe(true)
})

/* ------------------------------------------------------------------------------------- 17 */

test('the narrowing picker opens from its own control, and the ask is shown once', async ({ page }) => {
  const wire = await open(page)
  await page.locator('main.orders .bn-head-actions').getByRole('button', { name: 'Add orders' }).click()

  /* THE PICKER'S OWN CONTROL — separate from either fetch button. */
  const control = page.locator('.orders-paste').getByRole('button', { name: /statuses/i })
  await control.click()

  await expect(page.locator('.orders-statuses-ask')).toContainText('Which of these are worth fetching?')
  await expect(page.locator('.orders-statuses-list .orders-status')).toHaveCount(3)
  /* OPENING IT DID NOT FETCH ANYTHING — it is `previewOrders`, the free, write-nothing call. */
  expect(wire.filter((one) => one.path.endsWith('/orders/ingest'))).toHaveLength(0)

  /* THE ANSWER IS THE PRESS. Nothing was unticked, so `filter.statuses` is still `null` — the
     confirm only records that this device has been SHOWN the list (`asked: true`) — and the
     ordinary all-statuses press underneath fires exactly as it would have without ever opening
     the picker. */
  await page.locator('.orders-statuses-confirm').getByRole('button', { name: /Fetch these 370 orders/ }).click()

  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/fetch')).length).toBe(2)
  const sent = wire.filter((one) => one.path.endsWith('/orders/fetch'))[1]?.body as { all_statuses?: boolean }
  expect(sent.all_statuses).toBe(true)
  /* AND THE NEXT ORDINARY PRESS DOES NOT REOPEN THE ASK — answering settles the device. */
  await expect(page.locator('.orders-statuses-ask')).toHaveCount(0)
})

/* ------------------------------------------------------------------------------------- 18 */

test('a tick IS an answer, so unticking one settles the device without pressing the confirm', async ({
  page,
}) => {
  /* The confirm exists for the person whose answer is "all of them". Somebody who reads the list
     and unticks a status has already done the thing the ask is for, and being asked again next
     time would be the recurring step that was ruled out. */
  const wire = await open(page)
  await page.locator('main.orders .bn-head-actions').getByRole('button', { name: 'Add orders' }).click()
  await page.locator('.orders-paste').getByRole('button', { name: /statuses/i }).click()
  await expect(page.locator('.orders-statuses-ask')).toBeVisible()

  await page.locator('.orders-statuses-list .orders-status').first().locator('input[type=checkbox]').uncheck()
  /* The ask and its confirm are gone the moment the tick lands; the panel is a setting now. */
  await expect(page.locator('.orders-statuses-ask')).toHaveCount(0)
  await expect(page.locator('.orders-statuses-confirm')).toHaveCount(0)

  await page.locator('.orders-paste').getByRole('button', { name: 'Fetch from TCGplayer' }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/fetch')).length).toBe(3)
  const sent = wire.filter((one) => one.path.endsWith('/orders/fetch'))[2]?.body as { statuses?: string[] }
  expect(sent.statuses).toEqual(['Cancelled', 'Ready to Ship'])
})

/* ------------------------------------------------------------------------------------- 19
 *
 * GROUPED BY BUYER, NOT BY ORDER NUMBER (`D193`). The index pane and the
 * detail panel both key on the buyer now, and a buyer with more than one open order carries two
 * signals of that fact: the `N orders` pill in the index, and a chip per order in the detail
 * header. `buildWalk` is called with the UNION of the buyer's open orders, so a merged walk
 * shows rows from both. */

const SECOND_ORDER = 'B58DDD-24C44'
const secondOrderKey = `TCGplayer:${SECOND_ORDER}`

test('the index lists buyers, and a two-order buyer carries the N-orders pill and two bars', async ({
  page,
}) => {
  const secondLine = () =>
    line({
      order: SECOND_ORDER,
      order_key: secondOrderKey,
      sku: '9197754',
      picks: [pick({ index: 30, capture_id: 'cap-second', card_name: 'Sunrise', card_number: '030' })],
      line: { ...line().line, sku: '9197754', name: 'Sunrise', number: '030' },
    })
  const both = payloadOf(
    [order(), order({ key: secondOrderKey, number: SECOND_ORDER })],
    [
      { key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] },
      { key: secondOrderKey, number: SECOND_ORDER, complete: false, outstanding: 1, lines: [secondLine()] },
    ],
  )
  await open(page, { orders: both })

  /* ONE ROW FOR THE BUYER, NOT TWO — both orders carry the default fixture buyer. */
  const rows = page.locator('.orders-index-row')
  await expect(rows).toHaveCount(1)
  await expect(rows.first()).toContainText('Ada Lovelace')
  await expect(rows.first().locator('.orders-index-count')).toContainText('2 orders')

  await expect(rows.first()).toBeVisible()
  await rows.first().click()

  /* THE DETAIL HEADER ENUMERATES BOTH ORDERS, each with its own progress bar. */
  const chips = page.locator('.orders-buyer-chip')
  await expect(chips).toHaveCount(2)
  await expect(chips.nth(0)).toContainText(ORDER_NUMBER)
  await expect(chips.nth(1)).toContainText(SECOND_ORDER)
})

test('a nameless order groups on its own, as No name and the order number', async ({ page }) => {
  const nameless = order({ buyer: null })
  await open(page, { orders: payloadOf([nameless], [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] }]) })

  await expect(page.locator('.orders-index-row').first()).toContainText(`No name · #${ORDER_NUMBER}`)
})

test('a buyer with two open orders draws one merged walk carrying rows from both', async ({ page }) => {
  const secondLine = () =>
    line({
      order: SECOND_ORDER,
      order_key: secondOrderKey,
      sku: '9197754',
      picks: [pick({ index: 30, capture_id: 'cap-second', card_name: 'Sunrise', card_number: '030' })],
      line: { ...line().line, sku: '9197754', name: 'Sunrise', number: '030' },
    })
  const both = payloadOf(
    [order(), order({ key: secondOrderKey, number: SECOND_ORDER })],
    [
      { key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] },
      { key: secondOrderKey, number: SECOND_ORDER, complete: false, outstanding: 1, lines: [secondLine()] },
    ],
  )
  await open(page, { orders: both })
  await page.locator('.orders-index-row').first().click()

  /* BOTH CARDS ARE PULLABLE FROM ONE MERGED LIST — the walk built from the union of the buyer's
     open orders, not from either order alone. */
  const picks = page.locator('.orders-buyer-walk .orders-pick')
  await expect(picks).toHaveCount(2)
  await expect(page.locator('.orders-buyer-walk')).toContainText('Volcanion')
  await expect(page.locator('.orders-buyer-walk')).toContainText('Sunrise')

  /* AND THE BY-ORDER FOLD STILL HOLDS EACH ORDER SEPARATELY, so a per-order press (stand-down,
     close-line, declare-kind, hand-fill) stays reachable. */
  await expect(page.locator('.orders-buyer-byorder')).toContainText(ORDER_NUMBER)
  await expect(page.locator('.orders-buyer-byorder')).toContainText(SECOND_ORDER)
})

test('?order= resolves an old link to the buyer group that holds it', async ({ page }) => {
  const secondLine = () =>
    line({ order: SECOND_ORDER, order_key: secondOrderKey, sku: '9197754', picks: [pick({ index: 30, capture_id: 'cap-second' })] })
  const both = payloadOf(
    [order({ buyer: 'Ada Lovelace' }), order({ key: secondOrderKey, number: SECOND_ORDER, buyer: 'Someone Else' })],
    [
      { key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] },
      { key: secondOrderKey, number: SECOND_ORDER, complete: false, outstanding: 1, lines: [secondLine()] },
    ],
  )
  const wire: Wire[] = []
  await page.route(/\/inventory\/copies$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{"cards": {}}' })
  })
  await page.route(/\/orders$/, async (route) => {
    wire.push({ method: route.request().method(), path: new URL(route.request().url()).pathname, body: null })
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(both) })
  })
  /* THE BUYER OPENED BY THE LINK FETCHES ITS REAL PICKS — `open()`'s own default stub, laid
   *  out by hand here because this case does not call `open()`. */
  await page.route(/\/orders\/picks$/, async (route) => {
    const body = route.request().postDataJSON() as { keys?: string[] }
    const wanted = new Set(body.keys ?? [])
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ orders: both.resolution.orders.filter((one) => wanted.has(one.key)) }),
    })
  })
  await page.goto(`${VIEW_ROUTE}?order=${encodeURIComponent(secondOrderKey)}`)
  await expect(page.locator(VIEW)).toBeVisible()

  /* THE SECOND BUYER'S GROUP IS SELECTED, resolved through the order key the old link named. */
  await expect(page.locator('.orders-buyer-detail')).toContainText('Someone Else')
})

test('a buyer with nothing open and closed long ago sits under the Earlier fold', async ({ page }) => {
  const stale = order({
    buyer: 'Grace Hopper',
    open: false,
    recorded: 1,
    placed_at: '2020-01-01T00:00:00+00:00',
    progress: [{ sku: SKU, wanted: 1, recorded: 1, outstanding: 0, over: 0, copies: [], pulled: [], at: null, by_hand: 0, reason: null, declared_kind: null, closed_at: null, closed_reason: null }],
  })
  await open(page, { orders: payloadOf([order(), stale], [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] }]) })

  await page.locator('main.orders').getByRole('button', { name: 'Done' }).click()
  const earlier = page.locator('.orders-earlier')
  await expect(earlier).toBeVisible()
  await expect(earlier).toContainText('Grace Hopper')
})

/* ------------------------------------------------------------------------------------- 20
 *
 * SORT AND FILTER (`D209`). Ready to Ship leads, newest first within a group,
 * everything else stays reachable behind the status select — an ORDERING and never a hiding.
 *
 * THREE BUYERS, ONE FIXTURE. Alice (Ready to Ship, oldest), Carol (Ready to Ship, newest),
 * Bob (a status this file never hardcodes, in the middle). Default order is therefore
 * Carol, Alice, Bob — both Ready-to-Ship groups lead, newest of the two first, then Bob.
 * Carol's own line answers `sku_unseen`, which is what "Hide unknown SKUs" narrows on.
 */

function seededOrder(seed: {
  number: string
  buyer: string
  status: string
  placedAt: string
  reason: ResolvedLine['reason']
}): { row: OrderRow; resolved: ResolvedOrder } {
  const key = `TCGplayer:${seed.number}`
  const sku = `SKU-${seed.number}`
  const theLine = line({
    order: seed.number,
    order_key: key,
    sku,
    reason: seed.reason,
    picks: seed.reason === 'resolved' ? [pick({ capture_id: `cap-${seed.number}`, card_name: seed.buyer })] : [],
    line: { ...line().line, sku },
  })
  const row = order({
    key,
    number: seed.number,
    buyer: seed.buyer,
    status: seed.status,
    placed_at: seed.placedAt,
    lines: [theLine.line],
    progress: [
      {
        sku,
        wanted: 1,
        recorded: 0,
        outstanding: 1,
        over: 0,
        copies: [],
        pulled: [],
        at: null,
        by_hand: 0,
        reason: null,
        declared_kind: null,
        closed_at: null,
        closed_reason: null,
      },
    ],
  })
  const resolved: ResolvedOrder = { key, number: seed.number, complete: false, outstanding: 1, lines: [theLine] }
  return { row, resolved }
}

const ALICE = seededOrder({ number: 'A0001', buyer: 'Alice', status: 'Ready to Ship', placedAt: '2026-08-01T00:00:00+00:00', reason: 'resolved' })
const BOB = seededOrder({ number: 'B0002', buyer: 'Bob', status: 'Zorbo Pending', placedAt: '2026-08-15T00:00:00+00:00', reason: 'short' })
const CAROL = seededOrder({ number: 'C0003', buyer: 'Carol', status: 'Ready to Ship', placedAt: '2026-08-20T00:00:00+00:00', reason: 'sku_unseen' })

function threeBuyerPayload(): OrdersPayload {
  return payloadOf([ALICE.row, BOB.row, CAROL.row], [ALICE.resolved, BOB.resolved, CAROL.resolved])
}

/** Buyer names in the index pane, top to bottom. */
async function buyerOrder(page: Page): Promise<string[]> {
  return page.locator('.orders-index-row').allTextContents().then((rows) =>
    rows.map((text) => (text.includes('Alice') ? 'Alice' : text.includes('Bob') ? 'Bob' : text.includes('Carol') ? 'Carol' : text)),
  )
}

test('no row is unreachable at the default: every buyer is reachable with no control touched', async ({ page }) => {
  await open(page, { orders: threeBuyerPayload() })
  await expect(page.locator('main.orders')).toContainText('Alice')
  await expect(page.locator('main.orders')).toContainText('Bob')
  await expect(page.locator('main.orders')).toContainText('Carol')
})

test('the default ordering puts Ready to Ship first, newest within', async ({ page }) => {
  await open(page, { orders: threeBuyerPayload() })
  await expect(page.locator('.orders-index-row')).toHaveCount(3)
  expect(await buyerOrder(page)).toEqual(['Carol', 'Alice', 'Bob'])
})

test('the status options are built from the payload, with counts, including a status this file never hardcodes', async ({ page }) => {
  await open(page, { orders: threeBuyerPayload() })
  const options = page.locator('.orders-status-select option')
  await expect(options).toContainText(['All', 'Ready to Ship (2)', 'Zorbo Pending (1)'])
})

test('each control narrows; they compose', async ({ page }) => {
  await open(page, { orders: threeBuyerPayload() })
  const select = page.locator('.orders-status-select')

  /* STATUS ALONE. */
  await select.selectOption('Zorbo Pending')
  await expect(page.locator('.orders-index-row')).toHaveCount(1)
  await expect(page.locator('.orders-index-row')).toContainText('Bob')

  /* BACK TO ALL, THEN HIDE UNKNOWN SKUS — Carol's line is `sku_unseen`. */
  await select.selectOption('')
  await page.locator('.orders-hide-unknown input').check()
  await expect(page.locator('.orders-index-row')).toHaveCount(2)
  await expect(page.locator('main.orders')).not.toContainText('Carol')

  /* COMPOSED: Ready to Ship AND hide-unknown leaves only Alice (Carol is Ready to Ship too,
     but her line is unknown; Bob is not Ready to Ship at all). */
  await select.selectOption('Ready to Ship')
  await expect(page.locator('.orders-index-row')).toHaveCount(1)
  await expect(page.locator('.orders-index-row')).toContainText('Alice')
})

test('a changed filter reorders immediately', async ({ page }) => {
  await open(page, { orders: threeBuyerPayload() })
  expect(await buyerOrder(page)).toEqual(['Carol', 'Alice', 'Bob'])

  await page.locator('.orders-status-select').selectOption('Ready to Ship')
  /* Filtering is an explicit retake (D181): the two remaining rows land in current live
     order with no staleness offered. */
  await expect(page.locator('.orders-resort-slot .orders-resort')).toHaveCount(0)
  expect(await buyerOrder(page)).toEqual(['Carol', 'Alice'])
})

test('a re-sort mid-walk raises the stale count and does NOT reorder until pressed; the press reorders', async ({
  page,
}) => {
  await open(page, { orders: threeBuyerPayload() })
  expect(await buyerOrder(page)).toEqual(['Carol', 'Alice', 'Bob'])

  /* SORT NEVER REORDERS BY ITSELF (D181) — flip to Oldest and the rows must not move yet. */
  await page.locator('.orders-sort').getByRole('button', { name: 'Oldest' }).click()
  expect(await buyerOrder(page)).toEqual(['Carol', 'Alice', 'Bob'])

  const resort = page.locator('.orders-resort-slot .orders-resort')
  await expect(resort).toBeVisible()
  await expect(resort).toContainText('stale')
  await expect(resort).toContainText('re-sort')

  /* THE PRESS REORDERS. Ready-to-Ship still leads; oldest first within it is Alice then Carol. */
  await resort.click()
  await expect(page.locator('.orders-resort-slot .orders-resort')).toHaveCount(0)
  expect(await buyerOrder(page)).toEqual(['Alice', 'Carol', 'Bob'])
})

test('the device document round-trips and survives a reload', async ({ page }) => {
  await open(page, { orders: threeBuyerPayload() })

  await page.locator('.orders-status-select').selectOption('Ready to Ship')
  await page.locator('.orders-hide-unknown input').check()
  await page.locator('.orders-sort').getByRole('button', { name: 'Oldest' }).click()

  /* READING BACK THE VERY KEY UNDER TEST, the same exemption `remember()` above carries:
     asserting how this key round-trips means reading it, and going through the UI to confirm
     a write landed would be testing the panel's layout on the way past rather than the
     document itself. */
  const stored = await page.evaluate(
    // eslint-disable-next-line no-restricted-syntax -- see above
    (key) => window.localStorage.getItem(key),
    FILTER_KEY,
  )
  expect(stored).not.toBeNull()
  const parsed = JSON.parse(stored ?? '{}') as { view?: { status?: string; sort?: string; hideUnknown?: boolean } }
  expect(parsed.view).toEqual({ status: 'Ready to Ship', sort: 'oldest', hideUnknown: true })

  await page.reload()
  await expect(page.locator(VIEW)).toBeVisible()
  await expect(page.locator('.orders-status-select')).toHaveValue('Ready to Ship')
  await expect(page.locator('.orders-hide-unknown input')).toBeChecked()
  await expect(page.locator('.orders-sort').getByRole('button', { name: 'Oldest' })).toHaveAttribute('aria-pressed', 'true')
})

/* ============================================== D203 ==== */

/* THE PANEL COMPUTES ITS OWN CANDIDATES FROM `GET /orders`'S OWN ANSWER — `open`, `recorded`
   and `placed_at` are already on every `OrderRow`, so it asks the wire for nothing beyond what
   this screen already read. Only the PRESS reaches `/orders/reconcile-backlog`, so these cases
   drive the panel through the fixture's ORDER FIELDS rather than a canned preview body. */

test('the reconcile control is absent with nothing to reconcile', async ({ page }) => {
  /* PART-PULLED — `recorded: 1` on `oneOpenOrder()`'s own shape — is live work by the same
     test the route itself applies, so the screen is populated (one open order) and the panel
     still draws nothing. */
  const wire = await open(page, {
    orders: payloadOf(
      [order({ recorded: 1 })],
      [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] }],
    ),
  })
  await expect(page.locator('.orders-reconcile')).toHaveCount(0)
  /* AND NOTHING WAS EVER ASKED OF THE ROUTE — the whole point of computing this client-side. */
  expect(wire.filter((one) => one.path === '/orders/reconcile-backlog')).toEqual([])
})

test('the reconcile preview draws a breakdown by feed status, with the count in the button label', async ({
  page,
}) => {
  const OLD = '2020-01-01T00:00:00+00:00'
  const both = payloadOf(
    [
      order({ key: 'TCGplayer:A-1', number: 'A-1', status: 'Completed - Paid', recorded: 0, placed_at: OLD }),
      order({ key: 'TCGplayer:A-2', number: 'A-2', status: 'Ready to Ship', recorded: 0, placed_at: OLD }),
    ],
    [
      { key: 'TCGplayer:A-1', number: 'A-1', complete: false, outstanding: 1, lines: [line()] },
      { key: 'TCGplayer:A-2', number: 'A-2', complete: false, outstanding: 1, lines: [line()] },
    ],
  )
  const wire = await open(page, { orders: both })

  const panel = page.locator('.orders-reconcile')
  await expect(panel).toBeVisible()
  /* BOTH STATUSES DRAW, each with its own count — the whole safety this route offers is that a
     status this screen has never proposed closing before does not vanish into one figure. */
  await expect(panel).toContainText('Completed - Paid')
  await expect(panel).toContainText('Ready to Ship')

  /* THE COUNT IS IN THE BUTTON'S OWN LABEL — CLAUDE.md's money-moment register: danger is red,
     money moments are deliberate and carry the figure in the label. */
  await expect(panel.getByRole('button', { name: /Stand down 2 orders/ })).toBeVisible()

  /* AND STILL NOTHING WAS ASKED OF THE ROUTE — the breakdown above is computed, not fetched. */
  expect(wire.filter((one) => one.path === '/orders/reconcile-backlog')).toEqual([])
})

test('the reconcile press sends the cutoff shown on screen, and the receipt carries an undo', async ({ page }) => {
  const OLD = '2020-01-01T00:00:00+00:00'
  const both = payloadOf(
    [
      order({ key: 'TCGplayer:A-1', number: 'A-1', status: 'Completed - Paid', recorded: 0, placed_at: OLD }),
      order({ key: 'TCGplayer:A-2', number: 'A-2', status: 'Completed - Paid', recorded: 0, placed_at: OLD }),
    ],
    [
      { key: 'TCGplayer:A-1', number: 'A-1', complete: false, outstanding: 1, lines: [line()] },
      { key: 'TCGplayer:A-2', number: 'A-2', complete: false, outstanding: 1, lines: [line()] },
    ],
  )
  const wire = await open(page, {
    orders: both,
    reconcile: {
      cutoff: '2026-01-01',
      orders: 2,
      moved: 2,
      lines: 2,
      closed: [
        { source: 'TCGplayer', number: 'A-1' },
        { source: 'TCGplayer', number: 'A-2' },
      ],
      reason: 'shipped_elsewhere',
      still_open: 1,
    },
  })

  const panel = page.locator('.orders-reconcile')
  await panel.getByRole('button', { name: /Stand down 2 orders/ }).click()

  await expect.poll(() => wire.filter((one) => one.path === '/orders/reconcile-backlog').length).toBe(1)
  const press = wire.find((one) => one.path === '/orders/reconcile-backlog')
  /* THE ONLY FIELD SENT IS `cutoff` — the server recomputes the whole candidate set itself
     rather than trusting whatever this screen displayed a moment before the press. */
  expect(Object.keys(press?.body as object)).toEqual(['cutoff'])

  /* THE RECEIPT, AND ITS UNDO. `reconcileBacklog`'s `closed` rides straight into `reopenOrders`
     — the existing D113 reversal, which needed no new mechanism to put this route's writes
     back. */
  const receipt = page.locator('.bn-toast-receipt')
  await expect(receipt).toContainText('Stood down 2 orders')
  await expect(receipt.locator('button.bn-toast-action')).toHaveText('Undo')
  await receipt.locator('button.bn-toast-action').click()
  await expect.poll(() => wire.filter((one) => one.path === '/orders/close').length).toBe(1)
  expect(wire.find((one) => one.path === '/orders/close')?.body).toEqual({
    orders: [
      { source: 'TCGplayer', number: 'A-1' },
      { source: 'TCGplayer', number: 'A-2' },
    ],
    undo: true,
  })
})

/* ------------------------------------------------------------------------------------- 21
 *
 * THE BUYER SEARCH. Filters `.orders-index-row` by name or order number, folded the same way
 * `orderBuyers.ts:buyerKeyOf` folds a group key, composes as an AND with every other control,
 * and reaches the Earlier fold — the one place a name search actually earns its keep, since a
 * Done buyer past the 7-day cut is otherwise unreachable except by scrolling every row.
 */

test('the search narrows the buyer list by name, case- and space-insensitively', async ({ page }) => {
  await open(page, { orders: threeBuyerPayload() })
  await expect(page.locator('.orders-index-row')).toHaveCount(3)

  const search = page.locator('.orders-search-input')
  await search.fill('  ALICE ')
  await expect(page.locator('.orders-index-row')).toHaveCount(1)
  await expect(page.locator('.orders-index-row')).toContainText('Alice')

  await search.fill('')
  await expect(page.locator('.orders-index-row')).toHaveCount(3)
})

test('the search matches an order number too', async ({ page }) => {
  await open(page, { orders: threeBuyerPayload() })
  await page.locator('.orders-search-input').fill('c0003')
  await expect(page.locator('.orders-index-row')).toHaveCount(1)
  await expect(page.locator('.orders-index-row')).toContainText('Carol')
})

test('the search composes with the status select — an AND, never a second gate', async ({ page }) => {
  await open(page, { orders: threeBuyerPayload() })
  await page.locator('.orders-status-select').selectOption('Ready to Ship')
  await expect(page.locator('.orders-index-row')).toHaveCount(2) // Carol, Alice

  await page.locator('.orders-search-input').fill('bob')
  await expect(page.locator('.orders-index-row')).toHaveCount(0)
})

test('the search reaches the Earlier fold, so a Done buyer past the 7-day cut is findable by name', async ({
  page,
}) => {
  const stale = order({
    buyer: 'Grace Hopper',
    open: false,
    recorded: 1,
    placed_at: '2020-01-01T00:00:00+00:00',
    progress: [{ sku: SKU, wanted: 1, recorded: 1, outstanding: 0, over: 0, copies: [], pulled: [], at: null, by_hand: 0, reason: null, declared_kind: null, closed_at: null, closed_reason: null }],
  })
  await open(page, { orders: payloadOf([order(), stale], [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] }]) })

  await page.locator('main.orders').getByRole('button', { name: 'Done' }).click()
  await page.locator('.orders-search-input').fill('hopper')
  const earlier = page.locator('.orders-earlier')
  await expect(earlier).toBeVisible()
  await expect(earlier).toContainText('Grace Hopper')
})

test('a search with nothing left says so by name and offers to clear it', async ({ page }) => {
  await open(page, { orders: threeBuyerPayload() })
  await page.locator('.orders-search-input').fill('nobody named this')
  await expect(page.locator('main.orders')).toContainText('No buyer matches')
  await expect(page.locator('main.orders')).toContainText('nobody named this')

  const clear = page.locator('.bn-empty').getByRole('button', { name: 'Clear search' })
  await clear.click()
  await expect(page.locator('.orders-search-input')).toHaveValue('')
  await expect(page.locator('.orders-index-row')).toHaveCount(3)
})

test('a changed search is an explicit retake — no stale chip offered', async ({ page }) => {
  await open(page, { orders: threeBuyerPayload() })
  expect(await buyerOrder(page)).toEqual(['Carol', 'Alice', 'Bob'])

  await page.locator('.orders-search-input').fill('a')
  await expect(page.locator('.orders-resort-slot .orders-resort')).toHaveCount(0)
})

/* ------------------------------------------------------------------------------------- 22
 *
 * A DONE ORDER THAT STILL OWES COPIES OPENS BACK UP. `_order_row`'s `terminal` field, plus
 * what is still owed, is the discriminator — never the `status` string (D114). An order the
 * marketplace calls done because every copy already went stays exactly as closed as before.
 */

function terminalOwingOrder(over: Partial<OrderRow> = {}): OrderRow {
  return order({ open: false, wanted: 3, recorded: 1, status: 'Shipped', terminal: true, ...over })
}

test('a done order with nothing owed still draws nothing — unchanged from before this fix', async ({ page }) => {
  const closed = order({ open: false, wanted: 1, recorded: 1, status: 'Shipped', terminal: true })
  await open(page, { orders: payloadOf([closed], []) })
  await page.locator('main.orders').getByRole('button', { name: 'Done' }).click()
  await expect(page.locator('main.orders')).toContainText('Done')
  await expect(page.locator('.orders-lines')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Pull' })).toHaveCount(0)
})

test('a terminal order that still owes copies, with no answer yet, shows a way to try again rather than nothing', async ({
  page,
}) => {
  const owing = terminalOwingOrder()
  await open(page, { orders: payloadOf([owing], []) })
  await page.locator('main.orders').getByRole('button', { name: 'Done' }).click()
  await expect(page.locator('main.orders')).toContainText('Not resolved in this read.')
  await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible()
})

test('a terminal order that still owes copies, once resolved, draws its lines and a Pull button', async ({
  page,
}) => {
  const owing = terminalOwingOrder({ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, lines: [line().line] })
  const resolved: ResolvedOrder = { key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] }
  await open(page, { orders: payloadOf([owing], [resolved]) })

  await page.locator('main.orders').getByRole('button', { name: 'Done' }).click()
  await expect(page.locator('.orders-lines')).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Pull' })).toBeVisible()
})

/* ------------------------------------------------------------------------------------- 23
 *
 * "WALK THE BOXES" COVERS EVERY UNFULFILLED ORDER, NOT ONLY THE OPEN ONES. The owner's own
 * words opening this task: "I need the ability to walk orders even if it already shows
 * shipped ... when I do the order walk, I see all copies of the card". `buildWalk` now takes
 * `ownsAWalkableBody`'s union — open, or terminal-and-still-owing — at both call sites, and
 * `walkKeys`/`passComplete` are re-derived off the SAME predicate so a terminal order does not
 * read as "complete in this pass" the instant the pass opens.
 */

const TERM_NUMBER = 'T0001'
const TERM_KEY = `TCGplayer:${TERM_NUMBER}`
const TERM_SKU = '9000001'

/** A terminal-and-still-owing order, WITH a resolved answer carrying one pickable copy in a
 *  box distinct from the default fixture's, so the two never collide in the walk's own
 *  box/section grouping. */
function terminalOwingWalkable(over: Partial<OrderRow> = {}): { row: OrderRow; resolved: ResolvedOrder } {
  const theLine = line({
    order: TERM_NUMBER,
    order_key: TERM_KEY,
    sku: TERM_SKU,
    line: { ...line().line, sku: TERM_SKU, name: 'Terminal Treasure' },
    picks: [pick({ box: 5, index: 50, capture_id: 'cap-term', card_name: 'Terminal Treasure', place: place({ box: 5, box_name: 'Box Five', label: 'Box 5 · Section 1 · Card 1' }) })],
  })
  const row = terminalOwingOrder({ key: TERM_KEY, number: TERM_NUMBER, buyer: 'Nora Terminal', lines: [theLine.line], ...over })
  const resolved: ResolvedOrder = { key: TERM_KEY, number: TERM_NUMBER, complete: false, outstanding: 1, lines: [theLine] }
  return { row, resolved }
}

test('the walk includes a terminal-but-owing order once resolved, and counts it in the head figure', async ({
  page,
}) => {
  const term = terminalOwingWalkable()
  await open(page, {
    orders: payloadOf(
      [order(), term.row],
      [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] }, term.resolved],
    ),
  })
  await page.locator('main.orders').getByRole('button', { name: 'Walk the boxes' }).click()
  await expect(page.locator('.orders-walk-figure')).toContainText('2 unfulfilled orders')
  await expect(page.locator('.orders-walk')).toContainText('Terminal Treasure')
  await expect(page.getByRole('button', { name: 'Pull' })).toHaveCount(2)
})

test('a fully-pulled terminal order (nothing owed) never enters the walk', async ({ page }) => {
  const settled = order({ open: false, wanted: 1, recorded: 1, status: 'Shipped', terminal: true })
  await open(page, { orders: payloadOf([settled], []) })
  await page.locator('main.orders').getByRole('button', { name: 'Walk the boxes' }).click()
  await expect(page.locator('main.orders')).toContainText('Nothing left to walk')
  await expect(page.getByRole('button', { name: 'Pull' })).toHaveCount(0)
})

test('a terminal order does not read as complete the instant the pass opens, only once its copy is pulled', async ({
  page,
}) => {
  /* A SECOND, ALWAYS-OPEN ORDER IS NOT DECORATION (same reason as the older "capture server
     restart" case above): with only the terminal order, pulling its one copy leaves the walk
     with no rows at all, `WalkView` draws its EmptyState BEFORE the head, and the pill's absence
     would be indistinguishable from the head being gone entirely. */
  const term = terminalOwingWalkable()
  let served = payloadOf(
    [order(), term.row],
    [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] }, term.resolved],
  )
  await open(page, { orders: served })
  await page.route(/\/orders$/, async (route) => {
    if (route.request().method() !== 'GET') return route.fallback()
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(served) })
  })

  await page.locator('main.orders').getByRole('button', { name: 'Walk the boxes' }).click()
  /* NOTHING FINISHED YET — the pass just opened, and the order was terminal from the start. */
  await expect(page.locator('.orders-walk-figure .bn-pill')).toHaveCount(0)

  /* NOW ITS OWN COPY IS RECORDED, wanted <= recorded, and it drops out of `ownsAWalkableBody`. */
  served = payloadOf(
    [order(), { ...term.row, recorded: term.row.wanted }],
    [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] }],
  )
  await page.locator('.orders-walk li', { hasText: 'Terminal Treasure' }).getByRole('button', { name: 'Pull' }).click()
  await expect(page.locator('.orders-walk-figure .bn-pill')).toHaveText('1 order complete in this pass')
})

test('a terminal order sharing a buyer with nothing else draws exactly one Pull per copy, never two', async ({
  page,
}) => {
  const term = terminalOwingWalkable()
  await open(page, { orders: payloadOf([term.row], [term.resolved]) })

  /* THE GROUP IS DONE-ONLY (`group.open.length === 0`), so it sits behind the Done chip, same
     as any other terminal buyer. */
  await page.locator('main.orders').getByRole('button', { name: 'Done' }).click()
  await expect(page.locator('main.orders')).toContainText('Nora Terminal')

  /* THE MERGED WALK ITSELF MUST BE THE ONE DRAWING IT — not merely "one Pull button somewhere",
     which the "By order" fold alone could also produce if the widening regressed. */
  await expect(page.locator('.orders-buyer-walk')).toContainText('Terminal Treasure')
  await expect(page.getByRole('button', { name: 'Pull' })).toHaveCount(1)
})
