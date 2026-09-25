import { test, expect, type Page } from '@playwright/test'
import { sealEveryTest } from './shell'
import { line, order, payloadOf, pick, place } from './routeFixtures'

import type {
  OrdersPayload,
  Place,
  PlaceNeighbor,
  PullResult,
  WalkPlan,
  WalkPlanCopy,
  WalkPlanRef,
  WalkPlanShort,
  WalkPlanStop,
  WalkPlanTake,
} from '../src/types'

/* `app/src/OrdersWalkPane.tsx`'s OWN undo, over `docs/specs/undo.md` §2-3 and D164 — NOT the
 * rest of `#/orders`, which `orders.spec.ts` already covers and whose own header explains why
 * this file did not exist until now: the walk's OWN reversal used to be a hole this file did
 * not have to look through, a `UNDO_WINDOW_MS` clock local to the pane. It no longer is one.
 * This file exists for exactly that mechanism and nothing else `orders.spec.ts` already proves.
 *
 * THE DEFECT THIS FIXES. Before this change, `RowAction` dropped a copy's own `Undo` twenty
 * seconds after the pull, clock-timed, whether or not the operator was still mid-walk. That is
 * the shape `docs/specs/undo.md` rules out everywhere: "NO SERVER ANYWHERE ENFORCES A TIME
 * LIMIT... how long an undo stays offered is the screen's business," and §3's own ruling for
 * THIS screen is explicit — "the fast path undoes the newest pull. Anything older is the slow
 * path's job" — a RANK, never a countdown.
 *
 * THE REPLACEMENT. `newestUndoKey` (`OrdersWalkPane.tsx`) tracks which sold copy is newest by
 * `Receipt.at`, and `RowAction` draws `Undo` on that one copy alone, for as long as it stays
 * newest — D164's "the undo stack... counts the sitting," restated over one walk instead of one
 * capture session. An older sold copy draws `Sold`, a dead end IN THIS PANE ON PURPOSE (§4: the
 * way back for it is the card, on `#/inventory`'s own departed row, never a second control here
 * — the owner declined per-copy granularity in the walk).
 *
 * NOTHING ELSE MOVES: what a pull writes, which copy it claims, and what the walk contains are
 * all `Orders.tsx`'s territory and this file does not touch them — every case below asserts
 * only the ROW'S OWN CONTROL, never the wire body a pull sends (`orders.spec.ts` proves that).
 */

const ORDER_NUMBER = 'A2FFC195-0000F4-006AC'
const SKU = '9191486'
const VIEW_ROUTE = '/#/orders'
const VIEW = 'main.orders'

type Wire = { method: string; path: string; body: unknown }

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

/** `orders.spec.ts`'s own `walkPlanCopy`, restated — not imported, because that file exports
 *  nothing (its own fixtures are private on purpose, one screen's cases beside each other). */
function walkPlanCopy(over: WalkPlanCopyInput = {}): WalkPlanCopy {
  const box = over.box ?? 3
  const index = over.index ?? 21
  const builtPlace = place({
    box,
    index,
    slot: over.slot === undefined ? 17 : over.slot,
    card: over.card === undefined ? 17 : over.card,
    label: over.label === undefined ? 'Box 3, Section 2, Card 17' : over.label,
    section: 2,
    box_name: 'RB Epics',
    section_start: 12,
    section_end: null,
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

/** ONE TAKE, TWO PHYSICAL COPIES, BOTH `here: true` — the shape that puts two rows in the SAME
 *  `CardLocations` panel at once, which is what every case below needs: `wanted: 2` keeps the
 *  walk on this take after the first pull (`advanceAfter` only leaves a take once it is
 *  satisfied), so the second copy's row is still on screen to compare against the first. */
function twoCopyPlan(): WalkPlan {
  return walkPlanOf([
    walkPlanStop({
      takes: [
        walkPlanTake({
          wanted: 2,
          copies: [
            walkPlanCopy({ box: 3, index: 21, capture_id: 'cap-a', key: '3/21' }),
            walkPlanCopy({
              box: 5,
              index: 22,
              capture_id: 'cap-b',
              key: '5/22',
              slot: 18,
              card: 18,
              label: 'Box 5, Section 2, Card 18',
            }),
          ],
        }),
      ],
    }),
  ])
}

function pullResult(over: Partial<PullResult> = {}): PullResult {
  return {
    undone: false,
    order_key: `TCGplayer:${ORDER_NUMBER}`,
    sku: SKU,
    newly: 1,
    recorded: 1,
    outstanding: 1,
    places: [place()],
    sales: [],
    ...over,
  }
}

function oneOpenOrder(): OrdersPayload {
  return payloadOf(
    [order({ wanted: 2 })],
    [
      {
        key: `TCGplayer:${ORDER_NUMBER}`,
        number: ORDER_NUMBER,
        complete: false,
        outstanding: 2,
        lines: [line({ wanted: 2, owed: 2, fulfilled: 0, outstanding: 2, on_hand: 2, picks: [pick(), pick({ index: 22 })] })],
      },
    ],
  )
}

/** `twoCopyPlan()`'s first copy (`3/21`), in the shape `POST /inventory/copies` answers —
 *  `OrdersWalkPane.tsx`'s `rawCards`, and the ONE thing that makes `currentCard` (and so
 *  `CardDetailsSection`) render at all: without a real card at this key, `row` stays `null`
 *  and the Details panel — and the listing-correction control it may or may not carry — is
 *  never reached, which would make an absence assertion prove nothing. */
const WALK_CARD = {
  box: 3,
  index: 21,
  label: 'Box 3, Section 2, Card 17',
  section: 2,
  card: 17,
  photo: 'photos/3/21.jpg',
  photo_sha256: null,
  photo_reclaimed_at: null,
  set_hint: null,
  metadata_finish: 'normal',
  game: 'pokemon',
  set_name: null,
  rarity: null,
  rarity_claim: null,
  note: null,
  captured_at: '2026-08-22T12:34:00+00:00',
  capture_id: 'cap-a',
  name: 'Volcanion',
  number: '025',
  printed_total: null,
  number_display: '025',
  confidence: null,
  sku: SKU,
  condition: 'Near Mint',
  state: 'identified',
  state_at: '2026-08-22T12:34:00+00:00',
  retire_reason: null,
  run: null,
}

/** Land on `#/orders` with a two-copy walk already planned (the sole buyer selects itself on
 *  landing, `docs/specs/order-walk-plan.md` §13) — `open()`'s own `walkPlan`, not a stub called
 *  after, for the reason `orders.spec.ts`'s own `open()` gives at length: the FIRST
 *  `/orders/walk-plan` request fires from inside this call's own render. */
async function open(page: Page): Promise<Wire[]> {
  const wire: Wire[] = []

  await page.route(/\/orders\/pull$/, async (route) => {
    const body = route.request().postDataJSON() as { undo?: boolean }
    wire.push({ method: route.request().method(), path: new URL(route.request().url()).pathname, body })
    const answer = pullResult({ undone: body.undo === true })
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(answer) })
  })

  await page.route(/\/inventory\/copies$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ cards: { '3/21': WALK_CARD }, listings: {} }),
    })
  })

  // `WALK_CARD` makes `currentCard` real, which makes `PhotoPanel` ask for its photograph —
  // never stubbed here before because no card in this file ever rendered whole until now.
  await page.route(/\/photo\/(by-card\/[0-9a-f]+|\d+\/\d+)/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="63" height="88"><rect width="63" height="88" fill="#ccc"/></svg>',
    })
  })

  await page.route(/\/orders\/walk-plan$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(twoCopyPlan()) })
  })

  await page.route(/\/orders\/picks$/, async (route) => {
    const source = oneOpenOrder().resolution.orders
    const body = route.request().postDataJSON() as { keys?: string[] }
    const wanted = new Set(body.keys ?? [])
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ orders: source.filter((one) => wanted.has(one.key)) }),
    })
  })

  await page.route(/\/orders$/, async (route) => {
    wire.push({ method: route.request().method(), path: new URL(route.request().url()).pathname, body: null })
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(oneOpenOrder()) })
  })

  await page.goto(VIEW_ROUTE)
  await expect(page.locator(VIEW)).toBeVisible()
  return wire
}

sealEveryTest()

/* -------------------------------------------------------------------------------------- 1 */

test('only the newest pull in the walk offers Undo — the older one reads Sold', async ({ page }) => {
  const wire = await open(page)

  const rows = page.locator('.card-locations-row')
  await rows.nth(0).getByRole('button', { name: 'Mark sold' }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(1)

  // The copy just sold is the only one recorded so far, so it is the newest — and undoable.
  await expect(rows.nth(0).getByRole('button', { name: 'Undo' })).toBeVisible()

  await rows.nth(1).getByRole('button', { name: 'Mark sold' }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(2)

  /* THE SECOND PULL IS NOW THE NEWEST, WITH NO CLOCK INVOLVED — this assertion is true the
     instant the second write lands, not twenty seconds later or twenty seconds sooner. */
  await expect(rows.nth(1).getByRole('button', { name: 'Undo' })).toBeVisible()
  await expect(rows.nth(0).getByRole('button', { name: 'Undo' })).toHaveCount(0)
  await expect(rows.nth(0).locator('.bn-pill', { hasText: 'Sold' })).toBeVisible()
})

/* -------------------------------------------------------------------------------------- 2 */

test('a newer pull is what ends the older one’s Undo, not any span of time', async ({ page }) => {
  /* MUTATION PROOF, READ ALONGSIDE CASE 1: this is case 1's own claim, isolated to the single
     transition it depends on, so a change that made every row keep its own Undo (the bug this
     screen HAD before this fix — per-copy granularity the owner declined) would fail exactly
     here rather than being read as "the newest one also happens to work". */
  const wire = await open(page)
  const rows = page.locator('.card-locations-row')

  await rows.nth(0).getByRole('button', { name: 'Mark sold' }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(1)
  await expect(rows.nth(0).getByRole('button', { name: 'Undo' })).toBeVisible()

  await rows.nth(1).getByRole('button', { name: 'Mark sold' }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(2)

  await expect(rows.nth(0).getByRole('button', { name: 'Undo' })).toHaveCount(0)
})

/* -------------------------------------------------------------------------------------- 3 */

test('the newest pull stays undoable well past the old twenty-second window', async ({ page }) => {
  /* NO CLOCK IS A LIMIT HERE (`docs/specs/undo.md`, D136's own discipline: the clock is faked
     and only ever advanced). Before this fix, `UNDO_WINDOW_MS` (20s) turned this row's `Undo`
     into a `Sold` pill on its own, with nothing superseding it. This proves that no longer
     happens: 25 real seconds pass on the fake clock and the newest pull's `Undo` is untouched. */
  await page.clock.install()
  const wire = await open(page)
  const rows = page.locator('.card-locations-row')

  await rows.nth(0).getByRole('button', { name: 'Mark sold' }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(1)
  await expect(rows.nth(0).getByRole('button', { name: 'Undo' })).toBeVisible()

  await page.clock.runFor(25_000)

  await expect(rows.nth(0).getByRole('button', { name: 'Undo' })).toBeVisible()
  await expect(rows.nth(0).locator('.bn-pill', { hasText: 'Sold' })).toHaveCount(0)
})

/* -------------------------------------------------------------------------------------- 4 */

test('undoing the newest pull returns it to Mark sold, and the older copy stays Sold', async ({ page }) => {
  const wire = await open(page)
  const rows = page.locator('.card-locations-row')

  await rows.nth(0).getByRole('button', { name: 'Mark sold' }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(1)
  await rows.nth(1).getByRole('button', { name: 'Mark sold' }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(2)

  await rows.nth(1).getByRole('button', { name: 'Undo' }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(3)
  const undoBody = wire.filter((one) => one.path.endsWith('/orders/pull'))[2]?.body as { undo?: boolean; targets?: unknown }
  expect(undoBody?.undo).toBe(true)
  expect(undoBody?.targets).toEqual([{ box: 5, index: 22, capture_id: 'cap-b' }])

  await expect(rows.nth(1).getByRole('button', { name: 'Mark sold' })).toBeVisible()

  /* THE OLDER RECEIPT REGAINS "NEWEST" ONCE IT IS THE ONLY ONE LEFT — a rank, and ranks are
     recomputed each time the set of receipts changes, exactly as a stack's own top does when
     the item above it is popped. */
  await expect(rows.nth(0).getByRole('button', { name: 'Undo' })).toBeVisible()
})

/* -------------------------------------------------------------------------------------- 5 */

test('the walk\'s card pane carries no listing-correction control — Inventory only', async ({ page }) => {
  /* D252, the owner's ruling verbatim in intent: "Inventory only." This
   * pane is `CardHero.tsx`'s shared `CardDetailsSection`, the same component `#/inventory`
   * draws (§13, "Inventory's card pane, unchanged... reused whole") — `OrdersWalkPane.tsx`
   * passes `correctable={false}` at its one call site, so the control this file's sibling
   * (`correct-answer.spec.ts`) proves reachable on `#/inventory` must be absent here, and
   * absent WITHOUT a reserved gap in its place (D118: nothing rendered, not an empty box). */
  await open(page)

  const details = page.locator('.browse-details')
  await expect(details).toBeVisible()
  // The disclosure is open by default at this viewport (`CardDetailsSection`'s own default,
  // `!phone`), so the control would already be on screen if it were drawn at all.
  await expect(page.getByRole('button', { name: 'Wrong card?' })).toHaveCount(0)
  await expect(page.locator('.card-correction')).toHaveCount(0)
})
