import { test, expect, type Page, type Route } from '@playwright/test'
import { sealEveryTest } from './shell'
import { line, order, payloadOf, pick, place } from './routeFixtures'

import type {
  InventoryCard,
  OrderRow,
  OrdersPayload,
  Place,
  PlaceNeighbor,
  ResolvedLine,
  ResolvedOrder,
  WalkPlan,
  WalkPlanCopy,
  WalkPlanRef,
  WalkPlanShort,
  WalkPlanStop,
  WalkPlanTake,
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
 *
 * §13 REPLACES SECTIONS 8, 9, 9a AND 12'S OWN BUILD WHOLE (`docs/specs/order-walk-plan.md`,
 * ruled 2026-09-19): "Orders is inventory's screen with orders in the rail." The cases for
 * `OrdersWalk.tsx`'s `.walkplan-*` markup, the `Tick all` → `Walk N orders` two-press flow and
 * the merged `By buyer` walk are replaced, not adapted — see the banner above that block, deep
 * in this file, for exactly which claims were superseded and why. There is no
 * `order-walk.spec.ts`: an earlier draft of this file's own header named one that was never
 * built; the walk's own cases live in this file, beside the rest of the screen.
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

/* ---- `WalkPlan` fixtures, for `OrdersWalk.tsx`'s own `POST /orders/walk-plan` (§7-8) ---------
 *
 * `Orders.tsx`'s client-side `buildWalk` never left the browser, so no case above ever needed a
 * route for it. `OrdersWalk.tsx` fetches the solver's plan from the server (§8, "no `Re-plan`
 * control" — one fetch per pass), so a case that presses "Walk N orders" now needs this stubbed
 * or the request reaches `sealEveryTest`'s own refusal. Shapes echo `pick`/`line`/`order`'s
 * defaults above so a case can mix the two without two different Volcanions. */

/** The convenience shape every case in this file already writes — the flat fields the FIRST
 *  build's `WalkPlanCopy` carried, kept here as the FIXTURE's own vocabulary even though the
 *  real wire type dropped them 2026-09-19 (§8, "the stop, rebuilt"): every one of them now
 *  lives inside `place`, the same block `place()` below already builds for `pick()`. Composing
 *  it here, once, is what let every existing `walkPlanCopy({ box: 5, index: 50, slot: 1, ... })`
 *  call in this file go on reading exactly as it did rather than rewriting ~30 call sites by
 *  hand for a shape the tests never needed to see. `over.place` is the escape hatch for a case
 *  that needs a field this convenience shape does not name. */
type WalkPlanCopyInput = {
  box?: number
  index?: number
  slot?: number | null
  capture_id?: string | null
  cid?: string | null
  card?: number | null
  label?: string | null
  neighbors?: { prev: PlaceNeighbor | null; next: PlaceNeighbor | null } | null
  box_total?: number
  box_closed?: boolean
  fraction?: number | null
  state?: string
  has_photo?: boolean
  here?: boolean
  key?: string
  place?: Partial<Place>
}

function walkPlanCopy(over: WalkPlanCopyInput = {}): WalkPlanCopy {
  const box = over.box ?? 3
  const index = over.index ?? 21
  const builtPlace = place({
    box,
    index,
    slot: over.slot === undefined ? 17 : over.slot,
    card: over.card === undefined ? 17 : over.card,
    label: over.label === undefined ? 'Box 3 · Section 2 · Card 17' : over.label,
    section: 2,
    box_name: 'RB Epics',
    section_start: 12,
    section_end: null,
    /* THE BOX'S OWN THREE, real since 2026-09-19 (§8's ruling). A copy used to carry none of
       them and `PositionBar` drew its "a box the server could not size" blank track on every
       row for ever (§9a finding 4). A fixture that kept sending 0 would make that defect
       untestable, so the default is a real drawer. */
    box_total: over.box_total ?? 133,
    box_closed: over.box_closed ?? false,
    fraction: over.fraction === undefined ? 0.12 : over.fraction,
    neighbors: over.neighbors === undefined ? null : over.neighbors,
    ...over.place,
  })
  return {
    key: over.key ?? `${box}/${index}`,
    state: over.state ?? 'identified',
    has_photo: over.has_photo ?? false,
    capture_id: over.capture_id === undefined ? 'cap-a' : over.capture_id,
    cid: over.cid === undefined ? null : over.cid,
    place: builtPlace,
    here: over.here ?? true,
  }
}

/** One `GET /inventory`-shaped card — `options.inventoryCards`' own value type. Defaults to
 *  box 3 / index 21 / cap-a, matching `walkPlanCopy()`'s own default, so a case that walks to
 *  the default row and wants the REUSED pane (`CardHeroHead`/`PhotoPanel`/`CardDetailsSection`,
 *  §13) to actually resolve — rather than fall back to the pre-`rawCards` synthesised header —
 *  can pass `{ [\`${box}/${index}\`]: inventoryCard() }` as `inventoryCards` with no further
 *  argument. Every field `InventoryCard` requires is here; only the few a case actually reads
 *  ever need overriding. */
function inventoryCard(over: Partial<InventoryCard> = {}): InventoryCard {
  const base: InventoryCard = {
    box: 3,
    index: 21,
    label: 'Box 3 · Section 2 · Card 17',
    section: 2,
    card: 17,
    number_display: '025',
    place: place(),
    photo: '/photo/3/21',
    photo_sha256: null,
    set_hint: null,
    set_name: null,
    rarity: 'Rare',
    metadata_finish: 'Normal',
    game: 'pokemon',
    rarity_claim: null,
    note: null,
    captured_at: '2026-08-29T10:00:00+00:00',
    capture_id: 'cap-a',
    cid: null,
    photo_reclaimed_at: null,
    name: 'Volcanion',
    number: '025',
    printed_total: '219',
    confidence: 'high',
    sku: SKU,
    condition: 'Near Mint',
    state: 'listed',
    state_at: null,
    retire_reason: null,
    run: null,
  }
  return { ...base, ...over }
}

function walkPlanTake(over: Partial<WalkPlanTake> = {}): WalkPlanTake {
  const forRef: WalkPlanRef = { key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, buyer: 'Ada Lovelace' }
  return {
    sku: SKU,
    name: 'Volcanion',
    number_display: '025',
    set: null,
    rarity: null,
    condition: 'Near Mint',
    wanted: 1,
    for: [forRef],
    copies: [walkPlanCopy()],
    ...over,
  }
}

function walkPlanStop(over: Partial<WalkPlanStop> = {}): WalkPlanStop {
  return {
    key: 'box/3/section/2',
    box: 3,
    box_name: 'RB Epics',
    section: 2,
    section_name: null,
    pooled: false,
    game: null,
    game_display: null,
    order: 1,
    span: { start: 12, end: 30 },
    takes: [walkPlanTake()],
    ...over,
  }
}

/** The whole plan, `counts` derived from `stops` unless overridden. */
function walkPlanOf(stops: readonly WalkPlanStop[], shortfall: readonly WalkPlanShort[] = []): WalkPlan {
  const copies = stops.reduce((sum, stop) => sum + stop.takes.reduce((s, take) => s + take.copies.length, 0), 0)
  return {
    cost: 'default',
    stops: [...stops],
    shortfall: [...shortfall],
    counts: {
      stops: stops.length,
      boxes: new Set(stops.filter((s) => !s.pooled).map((s) => s.box)).size,
      copies,
      sections_considered: stops.length,
      sections_candidate: stops.length,
      exact: true,
      solve_ms: 4,
    },
  }
}

/** Answers every `POST /orders/walk-plan` with the same plan — one call per pass (§8), so one
 *  stub per case is enough.
 *
 *  IT COUNTS THE CALLS, because "the plan is fetched once per pass" is a rule and not a habit:
 *  a press that re-solved would still LOOK right in a stub that answers the same plan twice. */
async function stubWalkPlan(page: Page, plan: WalkPlan): Promise<{ readonly calls: () => number }> {
  let calls = 0
  await page.route(/\/orders\/walk-plan$/, async (route) => {
    calls += 1
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(plan) })
  })
  return { calls: () => calls }
}

/** SELECT THE FIRST BUYER ROW — §13 supersedes §12's own "Tick all, then Start": there is no
 *  Start button and no frozen pass any more. Clicking a buyer selects it and its walk starts
 *  at once, the same as clicking a box opens it (`useOrderWalk`'s `walkedKeys`). "Tick all"
 *  still exists (it JOINS every walkable buyer's orders to the live walk, `Untick all` drops
 *  them), which is a different thing from starting one. */
async function startWalk(page: Page): Promise<void> {
  await page.locator('.orders-index-row').first().click()
}

/** OPEN THE SELECTED ORDER'S `Manage` SHEET — where the fetch/paste well, the receipt, the
 *  status picker and both stand-down prompts live now (§13: "Inventory's skeleton has no other
 *  place for them"), retired from the page header's own "Add orders" toggle. Needs a selected
 *  order on screen already, which every fixture in this file provides by default. */
async function openManage(page: Page): Promise<void> {
  await page.locator('main.orders .browse-manage').first().click()
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
    /* A FUNCTION SEES THE REQUEST, WHICH IS WHAT `refreshed` NEEDS. The pull's post-write
       blocks are an answer to the body's own `refresh` list, so a case proving the walk
       re-describes its other rows has to compose the answer from what was asked. A static
       object still works and is what every older case passes.
       Mutating a stub AFTER the click is the race this repo has recorded (DEBTS 23) — this
       is the stub answering the press it is handed, which is not that. */
    pull?: unknown | ((body: unknown, call: number) => unknown)
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
    /* `POST /orders/walk-plan`'s INITIAL answer — see the route below, registered
       unconditionally, for why this exists at all. Omit it for a case that does not care about
       the walk (an empty plan, the honest default); pass it for a case that presses `Mark sold`
       on landing, which `stubWalkPlan` called AFTER `open()` cannot reliably reach — see that
       comment for the race this closes. */
    walkPlan?: WalkPlan
    /* `POST /inventory/copies`'s answer — see the route below for why this exists. Keyed
       `box/index`, matching `getInventoryCopies`'s own wire shape. */
    inventoryCards?: Record<string, InventoryCard>
  } = {},
): Promise<Wire[]> {
  const wire: Wire[] = []

  let pullCalls = 0
  await page.route(/\/orders\/pull$/, async (route) => {
    const body = route.request().postDataJSON()
    wire.push({
      method: route.request().method(),
      path: new URL(route.request().url()).pathname,
      body,
    })
    const answer =
      typeof options.pull === 'function'
        ? (options.pull as (body: unknown, call: number) => unknown)(body, pullCalls++)
        : (options.pull ?? { undone: false, order_key: '', sku: '', newly: 1, recorded: 1, outstanding: 0, places: [], sales: [] })
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(answer) })
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
     than argued case by case.

     `options.inventoryCards`, keyed `box/index`, FOR A CASE THAT NEEDS `rawCards` TO RESOLVE —
     `OrdersWalkPane.tsx`'s `currentCard`, which is what turns on the REUSED pane
     (`CardHeroHead`/`PhotoPanel`/`CardDetailsSection`, §13) rather than the synthesised
     fallback header it draws before this read answers. Empty by default, matching every case
     that never asks. */
  await page.route(/\/inventory\/copies$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ cards: options.inventoryCards ?? {} }),
    })
  })

  /* THE WALK'S OWN READ, ALSO UNCONDITIONALLY (§13): selecting a buyer starts their walk at
   * once, so `POST /orders/walk-plan` now fires on ordinary mount, for any fixture that carries
   * a walkable order — not only for a case that presses "Walk N orders", which no longer
   * exists. An EMPTY plan by default, so a case that does not care about the walk never leaks
   * this read to the capture server.
   *
   * `options.walkPlan`, NOT `stubWalkPlan(page, …)` CALLED AFTER `open()`, FOR A CASE THAT
   * WALKS ON LANDING. The sole buyer a single-order fixture draws is auto-selected the moment
   * `GET /orders` answers — `selectedKey`'s own fallback to `shownGroups[0]`, §13's "clicking a
   * buyer selects it and its walk starts at once" applied to the buyer the page lands on
   * already — so the FIRST `walk-plan` request fires from inside `open()`'s own render, before
   * a case's own `await` returns control to it. A `stubWalkPlan` call made after that has
   * already lost the race: Playwright's routes still register in the order added, but the
   * request this file's browser needs answered has often already been sent and fulfilled by
   * this default by the time the call lands, and `useOrderWalk`'s fetch effect is keyed on the
   * WALKED SET, not on time — an unchanged set never asks again. Measured, not assumed: three
   * cases (`the receipt names…`, `Mark sold records…`, `a pooled copy…`, this file's own
   * history) hung 15s on a `Mark sold` button that a stubbed-after plan never populated.
   * `stubWalkPlan` stays correct for a case that changes the SET after landing (ticking a
   * second buyer, replacing the selection) — it is only the FIRST fetch this cannot reach. */
  await page.route(/\/orders\/walk-plan$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(options.walkPlan ?? walkPlanOf([])),
    })
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

  await openManage(page)
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

  await openManage(page)
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

  await openManage(page)
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
  await openManage(page)

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

/* THE FOUR CASES BELOW (this one plus the pull-body, the receipt and the two undo cases) ALL
 * PRESSED `button.orders-pull` DIRECTLY, WHICH NO LONGER EXISTS TO PRESS. `OrderDetail` inside
 * the Manage sheet passes `hidePicks` UNCONDITIONALLY (§13: "the walk beside this sheet is the
 * one place to Mark sold from"), and `hidePicks` filters out every TAKEABLE copy — exactly the
 * ones a `.orders-pull`/`Mark sold` button would ever appear on (`copiesOf`'s own `takeable`,
 * `aimOf(line, pick) !== null && pick.held_by === null`). A copy nobody holds can now be pressed
 * in exactly one place: the walk's own `CardLocations` (`OrdersWalkPane.tsx`), which is
 * `#/inventory`'s own card pane and draws the identical `Mark sold` button
 * (`CardLocations.tsx`'s `renderAction`/`RowAction`) over the SAME write (`onWalkPull` calls the
 * same `pullCopy`, so the wire body these cases assert is unchanged). This is a real change to
 * WHERE the product draws a pressable copy, not a test bug to paper over — the PRODUCT decided
 * it (§13's own ruling), so every case below is re-aimed at the walk rather than at Manage. A
 * copy already spoken for is the opposite case: NOT takeable, so `hidePicks` leaves it alone and
 * it is still exactly where it always was, in `OrderDetail`'s own list. */

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
    /* THE FREE COPY, OFFERED — IN THE WALK, the one place a takeable copy is drawn now. The
       sole buyer selects itself on landing (§13), so this is `open()`'s own `walkPlan` rather
       than a `stubWalkPlan` call after — see that option's comment for the race it closes. */
    walkPlan: walkPlanOf([walkPlanStop({ takes: [walkPlanTake({ copies: [walkPlanCopy({ capture_id: 'cap-a' })] })] })]),
  })
  await expect(page.getByRole('button', { name: 'Mark sold' })).toBeVisible()

  /* THE PROMISED ONE IS NOT — it is not takeable, so `hidePicks` never touches it, and it is
     right where `OrderDetail`'s own list always drew it. ONE ROW, not two: the free copy above
     is gone from this list entirely now, which is the change from the deleted `By order` fold
     this case used to open — hidePicks removes exactly what the walk now offers instead. */
  await openManage(page)
  const rows = page.locator('.orders-pick')
  await expect(rows).toHaveCount(1)
  await expect(rows.first().locator('button.orders-pull')).toHaveCount(0)
  await expect(rows.first().locator('.orders-pick-held')).toContainText(OTHER_ORDER)
})

/* -------------------------------------------------------------------------------------- 4 */

test('the pull sends the capture_id of the row that was pressed, and its own position', async ({
  page,
}) => {
  /* TWO COPIES IN DIFFERENT BOXES, DELIBERATELY — same reason the old fixture used two picks:
     pressing the first would pass against a screen that sent the wrong row's capture_id, and
     the one a mid-box delete turns into a sale of the wrong card. Different boxes (rather than
     two slots of the same box, the old shape) keep the assertion below reading exactly the old
     body: same-box, `onWalkPull`'s own `refresh` list would name the OTHER row's own box/index
     too (D58 — the walk tells the server about every other card whose number the write is about
     to move), which is a real and separate claim this case is not about.

     `open()`'s own `walkPlan`, not `stubWalkPlan` after it — the sole buyer selects itself on
     landing (§13), so the plan has to be this screen's FIRST answer (see that option's comment
     for the race a later stub loses). */
  const wire = await open(page, {
    walkPlan: walkPlanOf([
      walkPlanStop({
        takes: [
          walkPlanTake({
            copies: [
              walkPlanCopy({ capture_id: 'cap-a' }),
              walkPlanCopy({ box: 5, index: 22, slot: 18, card: 18, label: 'Box 5 · Section 2 · Card 18', capture_id: 'cap-b' }),
            ],
          }),
        ],
      }),
    ]),
  })

  /* THE SECOND ROW, DELIBERATELY. Pressing the first would pass against a screen that sent
     `picks[0]` for every row — the exact bug this case exists to catch. */
  await page.locator('.card-locations-row').nth(1).getByRole('button', { name: 'Mark sold' }).click()

  await expect
    .poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length)
    .toBeGreaterThan(0)
  const sent = wire.find((one) => one.path.endsWith('/orders/pull'))
  expect(sent?.body).toEqual({
    source: 'TCGplayer',
    number: ORDER_NUMBER,
    sku: SKU,
    targets: [{ box: 5, index: 22, capture_id: 'cap-b' }],
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
    /* THE SOLE BUYER SELECTS ITSELF ON LANDING (§13's fallback), so the plan has to be this
       screen's FIRST answer — see `open()`'s own comment on `options.walkPlan` for the race a
       `stubWalkPlan` call made after `open()` loses here. */
    walkPlan: walkPlanOf([walkPlanStop()]),
  })

  await page.getByRole('button', { name: 'Mark sold' }).click()

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

/* `docs/specs/undo.md` §3: `U` IS THE ONE KEY FOR THE NEWEST REVERSIBLE WRITE — here, the
 * newest pull this screen made, held in `OrdersHubStore.lastPull` and reached by
 * `undoFromToast`, the same function the toast's own Undo button calls. `page.keyboard.press`
 * is what dispatches a real `keydown` a window listener can see; `.fill()` elsewhere in this
 * file does not. */
test('U undoes the newest pull, on the Pull stage', async ({ page }) => {
  const wire = await open(page, {
    pull: {
      undone: false,
      order_key: `TCGplayer:${ORDER_NUMBER}`,
      sku: SKU,
      newly: 1,
      recorded: 1,
      outstanding: 0,
      places: [place()],
      sales: [{ card: { place: place({ label: 'Box 3 · departed', slot: null, section: null, card: null }) } }],
    },
    walkPlan: walkPlanOf([walkPlanStop()]),
  })

  await page.getByRole('button', { name: 'Mark sold' }).click()
  await expect
    .poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length)
    .toBe(1)

  // The hand is on the page heading, not in any field.
  await page.getByRole('heading', { name: 'Orders' }).click()
  await page.keyboard.press('u')

  await expect
    .poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length)
    .toBe(2)
  const pulls = wire.filter((one) => one.path.endsWith('/orders/pull'))
  expect(pulls[1]?.body).toEqual({ undo: true, targets: [{ box: 3, index: 21, capture_id: 'cap-a' }] })
  await expect(page.locator('.bn-toast', { hasText: 'Put Volcanion back' })).toBeVisible()
})

test('u typed into the buyer search field does not undo the pull', async ({ page }) => {
  const wire = await open(page, {
    pull: {
      undone: false,
      order_key: `TCGplayer:${ORDER_NUMBER}`,
      sku: SKU,
      newly: 1,
      recorded: 1,
      outstanding: 0,
      places: [place()],
      sales: [{ card: { place: place({ label: 'Box 3 · departed', slot: null, section: null, card: null }) } }],
    },
    walkPlan: walkPlanOf([walkPlanStop()]),
  })

  await page.getByRole('button', { name: 'Mark sold' }).click()
  await expect
    .poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length)
    .toBe(1)

  await page.getByRole('searchbox', { name: 'Search buyers by name or order number' }).click()
  await page.keyboard.press('u')

  // No second `/orders/pull` call — the field ate the key.
  await expect(page.locator('.bn-toast', { hasText: 'Put Volcanion back' })).toHaveCount(0)
  expect(wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(1)
  await expect(page.getByRole('searchbox', { name: 'Search buyers by name or order number' })).toHaveValue('u')
})

/* -------------------------------------------------------------------------------------- 6 */

test('a pooled copy is drawn as pooled rather than as a position (D24)', async ({ page }) => {
  /* `Place.label` IS NULL BY DESIGN FOR A POOLED CARD AND NEVER BY FAULT — `located: false` is
     what says so. A screen that fell back to `box/index` would print a slot number for a card
     that is in no slot, which is the one thing D24 rules out.

     RE-AIMED, THE SAME REASON AS THE BANNER ABOVE: a pooled copy with a capture id and no
     `held_by` is takeable, so `hidePicks` removes it from Manage's own list too — this is drawn
     in the walk now, over `CardLocations`'s own pooled row (`isPooled`,
     `.card-locations-boxname`), the identical component and class `#/inventory` draws a pooled
     code card with. `open()`'s own `walkPlan`, not `stubWalkPlan` after it — the sole buyer
     selects itself on landing (§13), so the plan has to be this screen's FIRST answer. */
  await open(page, {
    walkPlan: walkPlanOf([
      walkPlanStop({
        pooled: true,
        box: null,
        section: null,
        takes: [
          walkPlanTake({
            copies: [
              walkPlanCopy({
                capture_id: 'cap-p',
                place: {
                  label: null,
                  located: false,
                  game: 'pokemon_code',
                  game_display: 'Pokémon code cards',
                  slot: null,
                  section: null,
                  card: null,
                },
              }),
            ],
          }),
        ],
      }),
    ]),
  })

  await expect(page.locator('.card-locations-boxname')).toContainText('pooled')

  /* AND NO PHOTOGRAPH ANYWHERE ON THIS SCREEN. A pooled capture's photo is a live code and a
     bearer instrument (D24, CLAUDE.md's opsec rule), and this screen draws no `<img>` at all —
     which is why `scripts/views.txt` may name `#/orders` without the exposure question the
     photo-drawing routes raise. */
  await expect(page.locator('main.orders img')).toHaveCount(0)
})

/* -------------------------------------------------------------------------------------- 7 */

test('a paste is projected before it is sent, and what was dropped is named', async ({ page }) => {
  const wire = await open(page)

  /* THE WAY IN IS SHUT WHILE THERE IS WORK ON SCREEN, AND ITS CONTROL IS THE SELECTED ORDER'S
     OWN `Manage` (§13: "Inventory's skeleton has no other place for them" — the same reason
     `BoxOps` is the box's Manage sheet). RE-AIMED from the header's own "Add orders" toggle,
     retired with it. */
  await expect(page.locator('.orders-paste')).toHaveCount(0)
  await openManage(page)
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
  await openManage(page)
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
  await openManage(page)
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
  await openManage(page)
  await page.locator('.orders-paste').getByRole('button', { name: 'Fetch two years' }).click()

  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/fetch')).length).toBe(1)
  const sent = wire.find((one) => one.path.endsWith('/orders/fetch'))?.body as { range?: string }
  expect(sent.range).toBe('LastTwoYears')
})

/* -------------------------------------------------------------------------------------- 10-11
 *
 * DELETED: `.orders-walk-figure`'s "N unfulfilled orders" head and its "N orders complete in
 * this pass" pill, and the capture-server-restart clear that reset it. `WalkView`/`buildWalk`'s
 * own head is gone with the component (`docs/specs/order-walk-plan.md` §9, "`buildWalk`'s
 * grouping goes"); `OrdersWalk.tsx`'s `WalkPass` fetches the solver's plan ONCE per pass and
 * never re-reads `/orders` while it runs (§8, "no `Re-plan` control"), so there is no live
 * `open`-vs-`walkKeys` comparison left to drive a pass-scoped completion count, and no boot
 * listener to clear one.
 *
 * THIS IS FLAGGED, NOT QUIETLY ACCEPTED. The figure was D96's own twice-amended, hard-won
 * result — a real defect (a lifetime total pretending to be a progress figure) measured on the
 * owner's own store, fixed twice, and reasoned through the ONE way it can be `true` (a count,
 * never a fraction; the pass's own frozen set, not `open`; no re-freeze on a mode toggle). None
 * of that argument is answered here — it just has nothing left to attach to. Reported under
 * "Input Needed" rather than rebuilt, because building it is a product change this brief's
 * fence puts out of reach (`OrdersWalk.tsx` may only gain a test hook), and deleting it without
 * saying so is exactly the "quiet regression" `make docs-audit`'s `recorded deletions` row
 * exists to catch.
 *
 * ONE PIECE OF D96 IS SUPERSEDED, NOT LOST: §8's "leaving the walk ends the pass" (the owner's
 * ruling, 2026-09-17 — tapping `By buyer` IS tapping another screen) directly reverses D96
 * amended's "a toggle is not the end of a pass, and freezing on every entry made it one." That
 * reversal is cited and deliberate; the rest of the figure's argument is not.
 */


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

  await openManage(page)
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

  await openManage(page)
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

  await openManage(page)
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
  await openManage(page)

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
  await openManage(page)
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
  await openManage(page)

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
  await openManage(page)
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

test('the index lists buyers, and a two-order buyer carries the N-orders pill and the aggregated triad', async ({
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

  /* THE ORDER PANEL READS "2 ORDERS" AND AGGREGATES OWED/SOLD ACROSS BOTH (§13; RE-AIMED off
     the deleted `BuyerDetail`'s two order chips — one order-detail header is gone with it, see
     the banner deep in this file for the claims that replace it). */
  await expect(page.locator('.boxops-identity-num')).toHaveText('2 ORDERS')
  const stats = page.locator('.card-locations-stats .bn-stat')
  await expect(stats.nth(0).locator('.bn-stat-value')).toHaveText('2')
})

test('a nameless order groups on its own, as No name and the order number', async ({ page }) => {
  const nameless = order({ buyer: null })
  await open(page, { orders: payloadOf([nameless], [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] }]) })

  await expect(page.locator('.orders-index-row').first()).toContainText(`No name · #${ORDER_NUMBER}`)
})

test('a buyer with two open orders walks both at once — one selection, one plan, both cards', async ({ page }) => {
  /* RE-AIMED off the deleted `BuyerDetail`'s own merged walk (`buildWalk`): selecting a buyer
     now starts the SAME union directly (`useOrderWalk`'s `walkedKeys`, §13), which is why this
     needs its own `stubWalkPlan` — the default fixture answers an empty plan otherwise. */
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
  /* `open()`'s OWN `walkPlan`, not `stubWalkPlan` after it: the sole buyer selects itself on
     landing (§13) and the plan is fetched before a later stub can register — CI lost that race
     on 2026-09-20 (`.browse-list` never drew), the same race `open()`'s option exists for. */
  await open(page, {
    orders: both,
    walkPlan: walkPlanOf([
      walkPlanStop(),
      walkPlanStop({
        key: 'box/5/section/1',
        box: 5,
        box_name: 'Box Five',
        section: 1,
        order: 2,
        span: { start: 1, end: 10 },
        takes: [
          walkPlanTake({
            sku: '9197754',
            name: 'Sunrise',
            number_display: '030',
            for: [{ key: secondOrderKey, number: SECOND_ORDER, buyer: 'Ada Lovelace' }],
            copies: [walkPlanCopy({ box: 5, index: 30, slot: 1, card: 1, capture_id: 'cap-second', label: 'Box 5 · Section 1 · Card 1' })],
          }),
        ],
      }),
    ]),
  })
  await page.locator('.orders-index-row').first().click()

  /* BOTH CARDS ARE IN ONE WALK LIST — the plan built from the union of the buyer's open
     orders, not from either order alone. */
  await expect(page.locator('.browse-list')).toContainText('Volcanion')
  await expect(page.locator('.browse-list')).toContainText('Sunrise')

  /* AND EACH ORDER'S OWN STAND-DOWN/CLOSE-LINE/DECLARE-KIND/HAND-FILL STAYS REACHABLE — behind
     `Manage` now, not a "By order" fold (deleted with `BuyerDetail`). */
  await openManage(page)
  await expect(page.locator('.orders-manage-orders')).toContainText(ORDER_NUMBER)
  await expect(page.locator('.orders-manage-orders')).toContainText(SECOND_ORDER)
})

test('selecting a two-order buyer sends exactly one batched POST /orders/picks, never one per key', async ({ page }) => {
  /* THE REGRESSION THIS CATCHES: `detail` (React state) does not settle inside one render
   *  pass, so a dedupe check reading only `detail` sees the SAME empty map across every
   *  render that happens before the first fetch resolves and fires a fresh identical POST
   *  each time. Measured against the seeded server on :8265 (2026-09-17): a fresh load with
   *  a four-order buyer selected by default sent SEVEN identical calls before the fix
   *  (`pendingPicks`, a ref marked synchronously before the fetch's own `await`); one after.
   *  This fixture's buyer holds two orders, which is enough to prove the batching — both
   *  keys travel in ONE call, never two single-key ones. RE-AIMED to wait on the order
   *  panel's own short figure settling (fed by `answers`, the same map `/orders/picks`
   *  answers into) rather than the deleted merged walk. */
  const secondLine = () =>
    line({
      order: SECOND_ORDER,
      order_key: secondOrderKey,
      sku: '9197754',
      reason: 'short',
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
  const wire = await open(page, { orders: both })
  await page.locator('.orders-index-row').first().click()

  /* Wait for the real picks to have landed — the short figure only reads non-zero once
     `answers` carries the real (not lite) tier for both orders — before counting the wire, so
     this does not race the fetch. */
  await expect(page.locator('.card-locations-stats .bn-stat').nth(2).locator('.bn-stat-value')).not.toHaveText('0')

  const picksCalls = wire.filter((one) => one.path.endsWith('/orders/picks'))
  expect(picksCalls).toHaveLength(1)
  expect(new Set((picksCalls[0]?.body as { keys: string[] }).keys)).toEqual(
    new Set([`TCGplayer:${ORDER_NUMBER}`, secondOrderKey]),
  )
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
  /* THE WALK'S OWN READ, ALSO HAND-LAID because this case does not call `open()` (see that
   *  helper's own comment on `options.walkPlan`): resolving `?order=` selects a buyer the same
   *  as a click does, and selecting a buyer starts their walk at once (§13) — an unstubbed
   *  `POST /orders/walk-plan` would otherwise reach the real capture server and trip
   *  `sealEveryTest`'s refusal. Empty is enough; this case is about which buyer resolves, not
   *  the walk itself. */
  await page.route(/\/orders\/walk-plan$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(walkPlanOf([])) })
  })
  await page.goto(`${VIEW_ROUTE}?order=${encodeURIComponent(secondOrderKey)}`)
  await expect(page.locator(VIEW)).toBeVisible()

  /* THE SECOND BUYER'S GROUP IS SELECTED, resolved through the order key the old link named —
   *  RE-AIMED off the deleted `BuyerDetail`'s own `.orders-buyer-detail` onto the order panel's
   *  own buyer name heading, `OrderPanel`'s `.boxops-identity-name` (§13, the pane `#/inventory`
   *  already draws for a box). */
  await expect(page.locator('.boxops-identity-name')).toContainText('Someone Else')
})

test('a buyer with nothing open and closed long ago sits under the Earlier fold', async ({ page }) => {
  const stale = order({
    buyer: 'Grace Hopper',
    open: false,
    recorded: 1,
    placed_at: '2020-01-01T00:00:00+00:00',
    progress: [{ sku: SKU, wanted: 1, recorded: 1, outstanding: 0, over: 0, copies: [], at: null, by_hand: 0, reason: null, declared_kind: null, closed_at: null, closed_reason: null }],
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

/** Enough buyers that `.orders-index` must scroll inside `.browse-boxes`'s own 264px band
 *  (`BoxBrowse.css`) rather than draw every row flat — the shape Task 2's own case needs. */
function manyBuyerPayload(n: number): OrdersPayload {
  const rows = Array.from({ length: n }, (_, i) => {
    const num = `BUYER-${String(i).padStart(3, '0')}`
    return order({
      key: `TCGplayer:${num}`,
      number: num,
      buyer: `Buyer ${i}`,
      lines: [line({ order: num, order_key: `TCGplayer:${num}` }).line],
    })
  })
  const resolved = rows.map((one) => ({
    key: one.key,
    number: one.number,
    complete: false,
    outstanding: 1,
    lines: [line({ order: one.number, order_key: one.key })],
  }))
  return payloadOf(rows, resolved)
}

/* THE ORDERS-FOLLOWUPS FIX, TASK 2: `.orders-index` (the buyer list) shrinks to fit inside
 * `.browse-boxes`'s 264px band and scrolls internally — that half already worked. What did
 * not: `.orders-index` carries `padding: 3px; margin: -3px` so a row's own hover shadow (which
 * bleeds 3px past its border box, `--bn-shadow-1`'s own reach) is not clipped by the list's
 * `overflow-y: auto` — and that same negative margin bleeds the list's OWN box 3px past its
 * flow position on every side, including the bottom, where `.orders-index-hint` (the
 * "step through the buyers" line, `.browse-boxes` declares no `gap` at all) sits immediately
 * after it. Measured at 820 with 20 buyers scrolled to the end, before this fix: the list's
 * own box bottom sat 3px BELOW the hint's own top — the last visible row's bottom padding is
 * what that 3px reached into. */
test('at 820, the last buyer row clears the step-through hint rather than sitting under it', async ({ page }) => {
  await page.setViewportSize({ width: 820, height: 1180 })
  await open(page, { orders: manyBuyerPayload(20) })

  await page.locator('.orders-index').evaluate((el) => {
    el.scrollTop = el.scrollHeight
  })
  const hint = await page.locator('.orders-index-hint').boundingBox()
  const items = page.locator('.orders-index-item')
  const count = await items.count()
  const last = await items.nth(count - 1).boundingBox()
  if (hint === null || last === null) throw new Error('the hint or the last buyer row did not lay out')

  expect(
    Math.round(last.y + last.height),
    `the last buyer row (bottom=${last.y + last.height}) sits under the hint (top=${hint.y})`,
  ).toBeLessThanOrEqual(Math.round(hint.y))
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
  /* RE-AIMED: `ReconcileBacklogPanel` moved into the Manage sheet with the rest of D203's own
     family (§13, "Inventory's skeleton has no other place for them") — it draws beside
     `BacklogPrompt`, not on the page directly. */
  await openManage(page)

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
  await openManage(page)

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
    progress: [{ sku: SKU, wanted: 1, recorded: 1, outstanding: 0, over: 0, copies: [], at: null, by_hand: 0, reason: null, declared_kind: null, closed_at: null, closed_reason: null }],
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
  /* RE-AIMED: `OrderDetail`'s own body — where this sentence lives — moved into the Manage
     sheet with the rest of the per-order controls (§13). */
  await openManage(page)
  await expect(page.locator('.orders-manage-sheet')).toContainText('Not resolved in this read.')
  await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible()
})


/* ======================================================================================
 * §13 — "ORDERS IS INVENTORY'S SCREEN WITH ORDERS IN THE RAIL", RULED 2026-09-19.
 *
 * EVERYTHING FROM HERE DOWN REPLACES THE CASES THIS FILE CARRIED FOR SECTIONS 8, 9, 9a AND
 * 12's OWN "Start"/tick/pass/stop/take BUILD, which §13 supersedes whole. `OrdersWalk.tsx`
 * and its `.walkplan-*` markup, the `Tick all` → `Walk N orders` two-press flow, the frozen
 * pass (`hub.walkKeys`), `End walk`, and the merged `.orders-buyer-walk` `By buyer` fold are
 * all DELETED, not adapted — this file's own cases for them go with them, named here rather
 * than left to rot quietly:
 *
 *   - "a terminal order that still owes copies, once resolved, draws its lines and a Pull
 *     button", "the walk includes a terminal-but-owing order once resolved", "a fully-pulled
 *     terminal order never enters the walk", "a terminal order sharing a buyer with nothing
 *     else draws exactly one Pull per copy" and every "By buyer" merged-walk case — the
 *     capability (a buyer's open+terminal-but-owing orders walked as one) is UNCHANGED and now
 *     proved by `useOrderWalk`'s own `walkedKeys` (a selected buyer's `ownsAWalkableBody`
 *     orders) rather than `buildWalk`.
 *   - every `.walkplan-stop` / `.walkplan-take` / `.walkplan-row` case (line header sentences,
 *     span bars, neighbour ladders, photo-once-per-take, re-description on a pull, gone-copy
 *     handling, the "no re-sort" fence) — the CLAIMS survive under `CardLocations`'s own
 *     `preserveOrder`, which is `#/inventory`'s own component and carries its own coverage in
 *     `app/tests/inventory.spec.ts`; the cases below prove `#/orders` reaches it correctly
 *     rather than re-proving `CardLocations` itself.
 *   - `Tick all`/`Untick all`/tick-survival-under-a-filter — UNCHANGED (the tick still selects
 *     which OTHER buyers join a walk); no case here repeats `app/tests/orders.spec.ts`'s own
 *     surviving assertions for them above this line.
 *
 * WHAT REPLACES THEM is organised the same way `useOrderWalk`/`OrdersWalkPane.tsx` is: the
 * walked set (select, tick, replace), the rail's own order panel and walk list, the pane
 * (inventory's, reused), the write (Mark sold), the no-re-sort fence, stepping, the word ban,
 * and one proof that `#/inventory` did not move under any of it.
 */

const SECOND_BUYER_ORDER = 'B31A0C7D-0001A2-00311'
const secondBuyerKey = `TCGplayer:${SECOND_BUYER_ORDER}`
const SECOND_SKU = '9197754'

/** A second buyer, own SKU, own box — so a case can tick or select them independently of the
 *  default fixture's Ada Lovelace / Volcanion / box 3. */
function secondBuyerPayload(): { payload: OrdersPayload; resolved: ResolvedOrder } {
  const theLine = line({
    order: SECOND_BUYER_ORDER,
    order_key: secondBuyerKey,
    sku: SECOND_SKU,
    line: { ...line().line, sku: SECOND_SKU, name: 'Sunrise' },
    picks: [pick({ box: 5, index: 9, capture_id: 'cap-second', card_name: 'Sunrise', card_number: '030', place: place({ box: 5, box_name: 'Box Five', section: 1, label: 'Box 5 · Section 1 · Card 9' }) })],
  })
  const row = order({ key: secondBuyerKey, number: SECOND_BUYER_ORDER, buyer: 'Nora Second', lines: [theLine.line] })
  const resolved: ResolvedOrder = { key: secondBuyerKey, number: SECOND_BUYER_ORDER, complete: false, outstanding: 1, lines: [theLine] }
  return {
    payload: payloadOf(
      [order(), row],
      [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] }, resolved],
    ),
    resolved,
  }
}

/** The default fixture's own plan: one stop, box 3, one take (Volcanion, wanted 1). */
function volcanionPlan(): WalkPlan {
  return walkPlanOf([walkPlanStop()])
}

/** The second buyer's own plan: one stop, box 5, one take (Sunrise, wanted 1). */
function sunrisePlan(): WalkPlan {
  return walkPlanOf([
    walkPlanStop({
      key: 'box/5/section/1',
      box: 5,
      box_name: 'Box Five',
      section: 1,
      span: { start: 1, end: 10 },
      takes: [
        walkPlanTake({
          sku: SECOND_SKU,
          name: 'Sunrise',
          number_display: '030',
          for: [{ key: secondBuyerKey, number: SECOND_BUYER_ORDER, buyer: 'Nora Second' }],
          copies: [walkPlanCopy({ box: 5, index: 9, slot: 1, card: 1, capture_id: 'cap-second', label: 'Box 5 · Section 1 · Card 1' })],
        }),
      ],
    }),
  ])
}

/** Both buyers' orders in one plan — what the walked union asks for once the second buyer is
 *  ticked alongside the first, which is already selected. */
function bothPlan(): WalkPlan {
  return walkPlanOf([volcanionPlan().stops[0]!, sunrisePlan().stops[0]!])
}

/* -------------------------------------------------------- selecting starts, ticking joins */

test('clicking a buyer selects it and its walk starts at once — no Start button', async ({ page }) => {
  /* RE-AIMED: the ORIGINAL premise here was that NOTHING is walked before a click —
     `.browse-walk` asserted `toHaveCount(0)` ahead of `startWalk`. That was never true once a
     buyer exists: `selectedKey`'s own fallback to `shownGroups[0]` (pre-dating this pass, D193's
     own reasoning — a status filter that hides the selected buyer must never leave the detail
     blank) selects the sole buyer on the very FIRST render, before any click, and selecting
     starts the walk at once (§13). It passed before only because `stubWalkPlan` called after
     `open()` loses the race for that first fetch (see `open()`'s own `walkPlan` comment) and the
     walk stayed empty for the wrong reason. The claim this case actually owns — there is no
     separate `Start`/`Walk N orders` control anywhere on the screen — is real and kept. */
  await open(page, { orders: oneOpenOrder(), walkPlan: volcanionPlan() })

  await expect(page.getByRole('button', { name: /Walk \d+ orders?/ })).toHaveCount(0)
  await expect(page.locator('.browse-walk')).toContainText('Volcanion')
})

test('ticking a second buyer joins the walk live, and it re-plans with no press but the tick', async ({ page }) => {
  /* `open()`'s own `walkPlan`, not `stubWalkPlan` alone — the sole selected buyer (Ada) starts
     her walk on landing (§13), which raced the `stubWalkPlan` call below often enough to flake
     (see that option's own comment). `bothPlan()` up front, `stubWalkPlan` still registered
     after for its own `calls()` counter, which only needs to prove a SECOND fetch happens once
     the tick changes the walked set — a claim the initial fetch's own timing cannot affect. */
  const { payload } = secondBuyerPayload()
  await open(page, { orders: payload, walkPlan: bothPlan() })
  const planned = await stubWalkPlan(page, bothPlan())
  await expect(page.locator('.browse-walk')).toContainText('Volcanion')
  const callsAfterSelect = planned.calls()

  await page.locator('.orders-index-item', { hasText: 'Nora Second' }).locator('.orders-index-tick input').check()

  await expect(page.locator('.browse-walk')).toContainText('Sunrise')
  await expect(page.locator('.browse-walk')).toContainText('Volcanion')
  expect(planned.calls()).toBeGreaterThan(callsAfterSelect)
})

test('clicking buyer B while A is selected replaces A — the walk is over B alone', async ({ page }) => {
  /* `open()`'s own `walkPlan` for A's plan — A selects herself on landing (§13), which races a
     `stubWalkPlan` call made after `open()` (see that option's comment). B's own re-plan below,
     triggered by an explicit click that changes the walked set, is not raced the same way and
     keeps its `stubWalkPlan` call as before. */
  const { payload } = secondBuyerPayload()
  await open(page, { orders: payload, walkPlan: volcanionPlan() })
  await expect(page.locator('.browse-walk')).toContainText('Volcanion')

  await stubWalkPlan(page, sunrisePlan())
  await page.locator('.orders-index-row', { hasText: 'Nora Second' }).click()

  await expect(page.locator('.browse-walk')).toContainText('Sunrise')
  await expect(page.locator('.browse-walk')).not.toContainText('Volcanion')
})

/* ------------------------------------------------------------------------ the order panel */

test('the selected order\'s panel is mock A\'s shape: label, title, Manage, pill, the bn-stat triad', async ({ page }) => {
  const owing = order({ wanted: 4, recorded: 1 })
  const resolvedLine = line({ reason: 'short', owed: 2, wanted: 2 })
  await open(page, {
    orders: payloadOf([owing], [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 2, lines: [resolvedLine] }]),
  })
  await startWalk(page)

  const panel = page.locator('.boxops-identity')
  await expect(panel.locator('.boxops-identity-num')).toContainText(ORDER_NUMBER)
  await expect(panel.locator('.boxops-identity-name')).toContainText('Ada Lovelace')
  await expect(panel.getByRole('button', { name: 'Manage' })).toBeVisible()
  await expect(panel.locator('.bn-pill')).toBeVisible()

  const stats = panel.locator('.card-locations-stats .bn-stat')
  await expect(stats).toHaveCount(3)
  await expect(stats.nth(0).locator('.bn-stat-label')).toHaveText('owed')
  await expect(stats.nth(1).locator('.bn-stat-label')).toHaveText('sold')
  await expect(stats.nth(2).locator('.bn-stat-label')).toHaveText('short')
  await expect(stats.nth(0).locator('.bn-stat-value')).toHaveText('3')
  await expect(stats.nth(1).locator('.bn-stat-value')).toHaveText('1')

  /* NO TYPED MIDDLE DOT anywhere in the panel (§13, mock A). */
  await expect(panel).not.toContainText(' · ')
})

test('a buyer holding two orders reads N ORDERS in the label, aggregated across both', async ({ page }) => {
  const second = order({ key: secondBuyerKey, number: SECOND_BUYER_ORDER, buyer: 'Ada Lovelace', wanted: 1, recorded: 0 })
  await open(page, {
    orders: payloadOf(
      [order(), second],
      [
        { key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] },
        { key: secondBuyerKey, number: SECOND_BUYER_ORDER, complete: false, outstanding: 1, lines: [line({ order: SECOND_BUYER_ORDER, order_key: secondBuyerKey })] },
      ],
    ),
  })
  await startWalk(page)
  await expect(page.locator('.boxops-identity-num')).toHaveText('2 ORDERS')
})

/* --------------------------------------------------------------------------- the Manage sheet */

test('Manage opens a sheet carrying the fetch/paste well, the status picker and both stand-down prompts', async ({ page }) => {
  const owing = terminalOwingOrder()
  await open(page, { orders: payloadOf([owing, order()], [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [line()] }]) })

  await expect(page.locator('.orders-paste')).toHaveCount(0)
  await openManage(page)

  const sheet = page.locator('.orders-manage-sheet')
  await expect(sheet.locator('.orders-paste')).toHaveCount(1)
  await expect(sheet.getByRole('button', { name: /statuses/i })).toBeVisible()
  /* The shipped-but-owing backlog prompt (D113) is reachable inside the sheet. */
  await expect(sheet).toContainText('Shipped')
})

test('the selected buyer\'s own orders stay reachable in Manage for stand-down, close-line and declare-kind', async ({ page }) => {
  const shortLine = line({ reason: 'no_copies_on_hand', owed: 1, wanted: 1, picks: [] })
  await open(page, { orders: payloadOf([order()], [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 1, lines: [shortLine] }]) })
  await startWalk(page)
  await openManage(page)

  const sheet = page.locator('.orders-manage-sheet')
  await expect(sheet.locator('.orders-manage-orders')).toContainText(ORDER_NUMBER)
  await expect(sheet.locator('.orders-manage-orders')).toContainText('Volcanion')
})

/* --------------------------------------------------------------------------- the pane is inventory's */

test('the walk pane is inventory\'s own card pane: the same header, photo, copies and Details classes', async ({ page }) => {
  /* THE REUSED PANE ONLY DRAWS ONCE `rawCards` RESOLVES THE CURRENT ROW'S REAL `InventoryCard`
     (`OrdersWalkPane.tsx`'s own `currentCard`) — before that it falls back to a synthesised
     header with no photo and no Details at all, which is what made this case's photo and
     Details assertions time out. `inventoryCards`, keyed to the plan's own box/index, is what
     makes the read answer with a real card instead of the empty default. */
  await page.route(/\/photo\/\d+\/\d+/, (route) => route.fulfill({ status: 404, body: '' }))
  await open(page, {
    orders: oneOpenOrder(),
    walkPlan: volcanionPlan(),
    inventoryCards: { '3/21': inventoryCard() },
  })

  const pane = page.locator('.orders-walk-card')
  /* THE HERO HEAD, `CardHeroHead` — `BoxBrowse.tsx`'s own classes. */
  await expect(pane.locator('.browse-hero-head .browse-hero-name')).toContainText('Volcanion')
  /* THE PHOTOGRAPH, `PhotoPanel`. */
  await expect(pane.locator('.bn-photo, .browse-photo-frame')).toBeVisible()
  /* "EVERY COPY OF THIS CARD" — `CardLocations`, unmodified. */
  await expect(pane.locator('.card-locations-title')).toHaveText('Every copy of this card')
  await expect(pane.getByRole('button', { name: 'Mark sold' })).toBeVisible()
  /* DETAILS — `CardDetailsSection`, moved whole from `BoxBrowse.tsx`, and — since the
     orders-followups fix — a SIBLING of `pane` (`.orders-walk-card`) rather than a child of
     it, mirroring `BoxBrowse.tsx`'s own `</section>` / `<CardDetailsSection .../>` pair
     exactly: nesting it inside the section let the section's `.bn-panel` `overflow: hidden`
     clip it into the same box as an overflowing copies list (D118, D220). Read off `page`
     rather than `pane` for that reason; it is still the one `.browse-details` this screen
     draws. */
  await expect(page.locator('.browse-details .browse-details-hint')).toHaveText('identity · claims · provenance')

  /* AND NONE OF INVENTORY'S OWN EDITING ACTIONS: no Card actions menu, no Retire, no re-shoot —
     left out by name (§13's override): retire, move and re-shoot are Inventory-only. */
  await expect(pane.getByRole('button', { name: 'Card actions' })).toHaveCount(0)
  await expect(pane.getByRole('button', { name: 'Retire' })).toHaveCount(0)
})

/* THE ORDERS-FOLLOWUPS FIX: `.inventory-detail` reached `.card-locations` only through
 * `.inventory-copies > .card-locations { flex: 1 1 auto; min-height: 0 }` (`Inventory.css`),
 * and `WalkMainPane` skipped the `.inventory-copies` wrapper `CopiesPanel` always draws. With
 * enough copies for a card, `.card-locations` kept its block default (`min-height: auto`,
 * sized to its OWN content) instead of shrinking to `.browse-band`'s fixed height (D118), so
 * the list grew past the band and `Details` — a child of `.orders-walk-card` at the time,
 * drawn right after `.browse-band` closed — landed inside the overflow rather than below it.
 * Measured at 1440 with 9 copies, before this fix: band 313.6-933.6, Details.y 933.6 (flush
 * with the band's OWN box, never accounting for the 1600px the list actually wanted), rows
 * `scrollHeight === clientHeight === 1600` (no internal scroll at all). This case is that
 * measurement, as an assertion, over a plan built for it (`viewport(1440, 900)` is this
 * file's own default, restated here because the case cares which height 720/620/520 the
 * `min(720px, max(520px, calc(100dvh - 280px)))` band rule lands on). */
test('the copies list scrolls inside the band, and Details never lands inside the overflow (D118, D220)', async ({ page }) => {
  await page.route(/\/photo\/\d+\/\d+/, (route) => route.fulfill({ status: 404, body: '' }))
  const n = 9
  const copies: WalkPlanCopy[] = Array.from({ length: n }, (_, i) =>
    walkPlanCopy({ index: 21 + i, card: 17 + i, capture_id: `cap-${i}`, label: `Box 3 · Section 2 · Card ${17 + i}` }),
  )
  const cards: Record<string, InventoryCard> = {}
  for (let i = 0; i < n; i++) {
    cards[`3/${21 + i}`] = inventoryCard({ index: 21 + i, card: 17 + i, label: `Box 3 · Section 2 · Card ${17 + i}` })
  }
  await page.setViewportSize({ width: 1440, height: 900 })
  await open(page, {
    orders: oneOpenOrder(),
    /* `open()`'s own `walkPlan`, never `stubWalkPlan` after it — the sole buyer selects itself
       on landing (§13), so the plan has to be this screen's FIRST answer. */
    walkPlan: walkPlanOf([walkPlanStop({ takes: [walkPlanTake({ copies })] })]),
    inventoryCards: cards,
  })

  const band = page.locator('.browse-band')
  const details = page.locator('.browse-details')
  await expect(details).toBeVisible()
  const bandBox = await band.boundingBox()
  const detailsBox = await details.boundingBox()
  if (bandBox === null || detailsBox === null) throw new Error('band or Details did not lay out')

  /* THE OVERLAP ITSELF: `Details`' own top may never sit above the band's own bottom edge —
     that gap, not the DOM position, is what an owner actually sees. */
  expect(
    Math.round(detailsBox.y),
    `Details (y=${detailsBox.y}) sits inside the band (bottom=${bandBox.y + bandBox.height}), not below it`,
  ).toBeGreaterThanOrEqual(Math.round(bandBox.y + bandBox.height))

  /* THE LIST IS WHAT GIVES (D118): with more copies than the band can show at once, the rows
     list scrolls INSIDE its own box rather than growing past it. */
  const rowsScroll = await page.locator('.card-locations-rows').evaluate((el) => ({
    scrollHeight: el.scrollHeight,
    clientHeight: el.clientHeight,
  }))
  expect(rowsScroll.scrollHeight, 'the copies list grew past what the band can show, uncontained').toBeGreaterThan(
    rowsScroll.clientHeight,
  )
})

/* --------------------------------------------------------------------------------- Mark sold */

test('Mark sold records the copy against the owing order, and the order panel updates', async ({ page }) => {
  /* `open()`'s own `walkPlan`, not `stubWalkPlan` after it — the sole buyer selects itself on
     landing (§13), so the plan has to be this screen's FIRST answer (see that option's
     comment for the race a later stub loses).

     `orders` IS A FUNCTION, ANSWERING THE SOLD FIGURE ON THE SECOND READ. The order panel's own
     `sold` stat is `group.recorded`, off `GET /orders`'s own answer — not the walk's local
     tally — so `onWalkPull`'s post-write `Promise.all([reread(), rereadStore()])` has to see
     the copy recorded for the panel to move at all. A static payload here would leave `sold`
     at 0 forever, which is a fixture gap this case's own claim depends on closing, not a
     product one. */
  let readCalls = 0
  const wire = await open(page, {
    orders: () =>
      readCalls++ === 0
        ? oneOpenOrder()
        : payloadOf(
            [order({ recorded: 1 })],
            [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: true, outstanding: 0, lines: [line({ fulfilled: 1, outstanding: 0, sold: 1 })] }],
          ),
    pull: { undone: false, order_key: `TCGplayer:${ORDER_NUMBER}`, sku: SKU, newly: 1, recorded: 1, outstanding: 0, places: [place()], sales: [] },
    walkPlan: volcanionPlan(),
  })

  await page.locator('.orders-walk-card').getByRole('button', { name: 'Mark sold' }).click()

  await expect
    .poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length)
    .toBeGreaterThan(0)
  const sent = wire.find((one) => one.path.endsWith('/orders/pull'))
  expect(sent?.body).toMatchObject({
    source: 'TCGplayer',
    number: ORDER_NUMBER,
    sku: SKU,
    targets: [{ box: 3, index: 21, capture_id: 'cap-a' }],
  })

  const stats = page.locator('.boxops-identity .card-locations-stats .bn-stat')
  await expect(stats.nth(1).locator('.bn-stat-value')).toHaveText('1')
})

/* ------------------------------------------------------------------- the trap: no re-sort */

test('a sale does not re-sort the walk list, and this section leads', async ({ page }) => {
  /* THE TRAP THIS SCREEN'S OWN BRIEF NAMED FIRST: `CardLocations` re-sorts by fullest section
     on every render UNLESS `preserveOrder` is passed. This case builds a plan whose SECOND
     section (box 5) would sort ahead of the first (box 3) under that rule — box 5's take
     starts with more on-hand copies — then sells the first row's own copy and asserts the
     section order and the row order are both exactly as the plan sent them, before and after.
     Verified red first: dropping `preserveOrder` from `WalkMainPane`'s `CardLocations` call
     turns this case red, because the sale then sorts the just-sold copy's section behind the
     section that still has more on hand. */
  const denseSecondSection = walkPlanOf([
    walkPlanStop({ key: 'box/3/section/2', box: 3, box_name: 'RB Epics', section: 2 }),
    walkPlanStop({
      key: 'box/5/section/1',
      box: 5,
      box_name: 'Box Five',
      section: 1,
      order: 2,
      span: { start: 1, end: 10 },
      takes: [
        walkPlanTake({
          sku: SECOND_SKU,
          name: 'Sunrise',
          for: [{ key: secondBuyerKey, number: SECOND_BUYER_ORDER, buyer: 'Nora Second' }],
          copies: [walkPlanCopy({ box: 5, index: 9, slot: 1, card: 1, capture_id: 'cap-second', label: 'Box 5 · Section 1 · Card 1' })],
        }),
      ],
    }),
  ])
  const { payload } = secondBuyerPayload()
  await open(page, {
    orders: payload,
    pull: { undone: false, order_key: `TCGplayer:${ORDER_NUMBER}`, sku: SKU, newly: 1, recorded: 1, outstanding: 0, places: [place()], sales: [] },
  })
  await stubWalkPlan(page, denseSecondSection)
  await startWalk(page)
  await page.locator('.orders-index-item', { hasText: 'Nora Second' }).locator('.orders-index-tick input').check()
  await expect(page.locator('.browse-list')).toContainText('Sunrise')

  /* HIDE SOLD DEFAULTS ON (D132, reused for the walk by §13's override — no new key). Turned
     off here on purpose: this case is about ORDER, not visibility, and the sold row disappearing
     under the default is a second, true, and unrelated claim that would otherwise make `before`
     and `after` differ for a reason this case is not naming. */
  await page.locator('.browse-hidesold').click()

  const before = await page.locator('.browse-list .browse-secttitle, .browse-list .browse-row-name').allTextContents()

  await page.locator('.orders-walk-card').getByRole('button', { name: 'Mark sold' }).click()
  await expect
    .poll(async () => (await page.locator('.orders-walk-card .browse-hero-name').textContent()) ?? '')
    .not.toBe('Volcanion')

  const after = await page.locator('.browse-list .browse-secttitle, .browse-list .browse-row-name').allTextContents()
  expect(after).toEqual(before)
})

/* --------------------------------------------------------------------------- J/K, auto-advance */

test('J steps to the next card in the walk list, K steps back', async ({ page }) => {
  await open(page, { orders: secondBuyerPayload().payload })
  await stubWalkPlan(page, bothPlan())
  await startWalk(page)
  await page.locator('.orders-index-item', { hasText: 'Nora Second' }).locator('.orders-index-tick input').check()
  await expect(page.locator('.browse-list')).toContainText('Sunrise')

  /* THE HAND IS ON THE PAGE HEADING, NOT ON THE TICK CHECKBOX — `check()` leaves focus on the
     checkbox `<input>` it clicked, and `J`/`K`'s own listener yields to ANY `INPUT`, checkbox
     included, the same guard `U`'s own case moves off a field for. */
  await page.getByRole('heading', { name: 'Orders' }).click()

  const first = await page.locator('.orders-walk-card .browse-hero-name').textContent()
  await page.keyboard.press('j')
  await expect
    .poll(async () => page.locator('.orders-walk-card .browse-hero-name').textContent())
    .not.toBe(first)
  const second = await page.locator('.orders-walk-card .browse-hero-name').textContent()

  await page.keyboard.press('k')
  await expect(page.locator('.orders-walk-card .browse-hero-name')).toHaveText(first ?? '')
  expect(second).not.toBe(first)
})

test('when a card\'s owed copies are all sold, the next card in the walk lights', async ({ page }) => {
  const wire = await open(page, {
    orders: secondBuyerPayload().payload,
    pull: { undone: false, order_key: `TCGplayer:${ORDER_NUMBER}`, sku: SKU, newly: 1, recorded: 1, outstanding: 0, places: [place()], sales: [] },
  })
  await stubWalkPlan(page, bothPlan())
  await startWalk(page)
  await page.locator('.orders-index-item', { hasText: 'Nora Second' }).locator('.orders-index-tick input').check()
  await expect(page.locator('.orders-walk-card .browse-hero-name')).toHaveText('Volcanion')

  await page.locator('.orders-walk-card').getByRole('button', { name: 'Mark sold' }).click()
  await expect
    .poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length)
    .toBeGreaterThan(0)

  /* Volcanion's own `wanted: 1` is now satisfied by the one sale, so the pane lights the next
     card — Sunrise — without a press beyond the sale itself. */
  await expect(page.locator('.orders-walk-card .browse-hero-name')).toHaveText('Sunrise')
})

/* --------------------------------------------------------------------------------- the words */

test('drawer, pull, stop and take do not appear anywhere on the screen — Mark sold and all pulled do', async ({ page }) => {
  const satisfied = order({ wanted: 2, recorded: 2 })
  await open(page, {
    orders: payloadOf([satisfied, order({ key: secondBuyerKey, number: SECOND_BUYER_ORDER })], [
      { key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: true, outstanding: 0, lines: [line({ reason: 'resolved', owed: 0 })] },
      { key: secondBuyerKey, number: SECOND_BUYER_ORDER, complete: false, outstanding: 1, lines: [line({ order: SECOND_BUYER_ORDER, order_key: secondBuyerKey })] },
    ]),
  })
  await stubWalkPlan(page, volcanionPlan())
  await startWalk(page)

  const text = (await page.locator('main.orders').innerText()).toLowerCase()
  for (const banned of ['drawer', 'stop', 'take']) {
    expect(text, `"${banned}" must not appear on #/orders`).not.toMatch(new RegExp(`\\b${banned}\\b`))
  }
  /* "pull" survives only inside the Fulfiller hand-off's own name, "Cards to pull" — that
     screen's real title, quoted rather than reworded. Nowhere else. */
  const pullMatches = text.match(/\bpull\w*/g) ?? []
  for (const match of pullMatches) {
    expect(['pull'].includes(match) && text.includes('cards to pull'), `unexpected "${match}"`).toBe(true)
  }
  expect(text).not.toContain('all pulled')
})

test('a buyer row whose orders are all recorded reads "all sold", never "all pulled"', async ({ page }) => {
  const satisfied = order({ wanted: 2, recorded: 2 })
  await open(page, { orders: payloadOf([satisfied], [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: true, outstanding: 0, lines: [line({ reason: 'resolved', owed: 0 })] }]) })
  await expect(page.locator('.orders-index-row')).toContainText('all sold')
  await expect(page.locator('.orders-index-row')).not.toContainText('all pulled')
})

/* ------------------------------------------------------------------------- #/inventory, unchanged */

test('#/inventory renders its own known shell unchanged by any of this', async ({ page }) => {
  /* NOT A FULL RE-PROOF OF #/inventory — `app/tests/inventory.spec.ts` is that, and it is
     asserted to pass UNCHANGED alongside this file (`make design-check`'s own report). This is
     the light DOM-signature this file owns: the route resolves, and the exact class names
     `CardHero.tsx`'s extraction reads back off `BoxBrowse.tsx` are still the ones on screen —
     proof the shared file did not change what `#/inventory` draws, only where the code that
     draws it lives. */
  /* THE SHELL'S OWN BACKGROUND READS, on every route — `/queues` and `/orders` feed the sidebar's
     own badges, unrelated to this screen, and a landed box fetches its own detail
     (`/inventory/<n>`). None of this is `open()`'s own helper (this case does not carry a
     fixture worth one route table), so they are stubbed by hand here, the same way `?order=`'s
     own case above does for `#/orders`. */
  await page.route(/\/queues$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"review":[],"parked":[]}' }),
  )
  await page.route(/\/orders$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(oneOpenOrder()) }),
  )
  await page.route(/\/boxes(\?.*)?$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        boxes: [{ box: 1, name: 'Box 1', state: 'open', cards: 1, sold: 0, retired: 0, moved: 0 }],
        facets: { games: [], sets: {}, rarities: {} },
      }),
    }),
  )
  /* ONE CARD, IN BOX 1 — `BoxBrowse.tsx` draws its own "No cards captured yet" empty state
     over zero cards, which is a real and different screen from the one this case checks. */
  const oneCard = inventoryCard({ box: 1, index: 1, label: 'Box 1 · Section 1 · Card 1', section: 1, card: 1 })
  await page.route(/\/inventory$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ version: 2, cards: { '1/1': oneCard } }) }),
  )
  await page.route(/\/inventory\/\d+$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ version: 2, cards: { '1/1': oneCard } }) }),
  )
  await page.route(/\/photo\/\d+\/\d+/, (route) => route.fulfill({ status: 404, body: '' }))
  await page.route(/\/pipeline\/runs$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{"runs":[]}' }),
  )
  await page.goto('/#/inventory')
  await expect(page.locator('main.inventory')).toBeVisible()
  await expect(page.locator('.browse-body')).toHaveCount(1)
  await expect(page.locator('.browse-map')).toHaveCount(1)
  await expect(page.locator('.browse-boxes.bn-panel')).toHaveCount(1)
})
