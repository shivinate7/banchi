// Protects: Undo in the order walk stays on the newest pull and never expires on a clock.
// Governs: D118, D136, D164, D252
import { test, expect, type Page } from '@playwright/test'
import { sealEveryTest } from './shell'
import { showDoneOnly, showOpenOnly } from './ordersFilterSheet'
import { line, order, payloadOf, pick, place } from './routeFixtures'
import { describeShifts, markNow, readShifts, sumOf, watchShifts } from './layoutShift'
import { heldFocus } from './focusHeld'

import { afterPaint, settleMotion } from './motionSettled'
import type {
  OrderRow,
  OrdersPayload,
  Place,
  ResolvedOrder,
  PlaceNeighbor,
  PullResult,
  PullTarget,
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
  // The default ref's `owed` tracks THIS take's own `wanted` (post-override), not a fixed 1 —
  // a case that raises `wanted` without naming its own `for` (`twoCopyPlan`'s two presses
  // against one order) needs the sole ref to still owe enough for every press `pickOrderFor`
  // makes against it.
  const wanted = over.wanted ?? 1
  const forRef: WalkPlanRef = { key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, buyer: 'Ada Lovelace', owed: wanted }
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
function twoCopyPlan(gone: ReadonlySet<string> = new Set()): WalkPlan {
  /* `gone` names the copies a sale has taken off the server's plan: a sold copy leaves `copies`, and `wanted` and the
     order's `owed` both fall by it (`docs/specs/order-walk-plan.md` §8, the ledger's `outstanding`). With none named the
     plan is exactly the one every existing case is built on. */
  const copies = [
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
  ].filter((copy) => !gone.has(copy.key))
  if (copies.length === 0) return walkPlanOf([])
  return walkPlanOf([walkPlanStop({ takes: [walkPlanTake({ wanted: copies.length, copies })] })])
}

/** The place the plan's copy stands at for one pulled target, matched on box, index and capture id.
 *  A target the plan does not hold gets a place with no label, so a toast that reads it says so. */
function placeOfTarget(plan: WalkPlan, target: PullTarget): Place {
  for (const stop of plan.stops) {
    for (const take of stop.takes) {
      for (const copy of take.copies) {
        if (copy.place.box === target.box && copy.place.index === target.index && copy.capture_id === target.capture_id) return copy.place
      }
    }
  }
  return place({ box: target.box, index: target.index, label: null, located: false, slot: null, card: null, section: null })
}

/** The answer to one pull or undo: one `places` entry per target in request order, each the place that
 *  copy stood at before the write (`PullResult.places`), read off the plan the walk was served. */
function pullResult(over: Partial<PullResult> = {}, targets: readonly PullTarget[] = [], plan: WalkPlan = twoCopyPlan()): PullResult {
  return {
    undone: false,
    order_key: `TCGplayer:${ORDER_NUMBER}`,
    sku: SKU,
    newly: 1,
    recorded: 1,
    outstanding: 1,
    places: targets.map((target) => placeOfTarget(plan, target)),
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
 *  `/orders/walk-plan` request fires from inside this call's own render. `plan` and `orders`
 *  default to this file's own fixtures, so every existing case reads exactly as before; A4's own
 *  case below is the one caller that names both. */
/** A fixture one call serves: a value, or a function of what the test has done so far (a sale,
 *  then a re-read of the same route). Every route asks again on each request, so a re-read sees it. */
type Served<T> = T | (() => T)

function served<T>(value: Served<T> | undefined, fallback: () => T): T {
  if (value === undefined) return fallback()
  return typeof value === 'function' ? (value as () => T)() : value
}

async function open(
  page: Page,
  options: {
    plan?: Served<WalkPlan>
    orders?: Served<OrdersPayload>
    cards?: Served<Record<string, object>>
    /** Runs when the walk posts a pull, before the answer goes back: a test counts its own sales here. */
    onPull?: () => void
    /** Answers a sale's pull with this failure while it returns non-null: the write did not stand, so the walk drops it. */
    pullFailure?: () => { status: number; body: unknown } | null
  } = {},
): Promise<Wire[]> {
  const planAt = () => served(options.plan, twoCopyPlan)
  const ordersAt = () => served(options.orders, oneOpenOrder)
  const cardsAt = () => served(options.cards, () => ({ '3/21': WALK_CARD }))
  const wire: Wire[] = []

  await page.route(/\/orders\/pull$/, async (route) => {
    const body = route.request().postDataJSON() as { undo?: boolean; targets?: PullTarget[] }
    wire.push({ method: route.request().method(), path: new URL(route.request().url()).pathname, body })
    const failure = body.undo === true ? null : (options.pullFailure?.() ?? null)
    if (failure !== null) {
      await route.fulfill({ status: failure.status, contentType: 'application/json', body: JSON.stringify(failure.body) })
      return
    }
    // The places are read before the write, as the server answers them: a sale takes its copy out of the plan.
    const answer = pullResult({ undone: body.undo === true }, body.targets ?? [], planAt())
    if (body.undo !== true) options.onPull?.()
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(answer) })
  })

  await page.route(/\/inventory\/copies$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ cards: cardsAt(), listings: {} }),
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
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(planAt()) })
  })

  await page.route(/\/orders\/picks$/, async (route) => {
    const source = ordersAt().resolution.orders
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
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(ordersAt()) })
  })

  // THE BOX REGISTRY (lane A3): the pane's own copies list reads it for the section strip and
  // the ruler, the way `Inventory.tsx` does — never stubbed here before this lane's `getBoxes()`
  // read. Empty is honest: `PositionBar` draws without a layout, and no case in this file needs
  // a real one.
  await page.route(/\/boxes(\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ boxes: [], facet_cells: [] }),
    })
  })

  await page.goto(`${VIEW_ROUTE}?pullable=0`)
  await expect(page.locator(VIEW)).toBeVisible()
  return wire
}

/* The pick the walk stands on: its copies' rows and their presses are in the card pane, beside the
   photograph. The rail's line carries the card and its count only. */
const CURRENT_PICK = '.orders-cardcol'

sealEveryTest()

/* ux-w2 B16 (order-walk-plan.md section 14). Asserts each figure chip beside the card names carries a
   text box that explains it. The box opens on hover and on keyboard focus, so a chip is reachable without a pointer.
   The walk's On Hand is the lead figure now, not a band chip (.claude/rules/app.md, One count, one name), so only the band's chips are checked here. */
test('ux-w2 B16: each Hidden and Sent chip opens a text box on hover and on keyboard focus', async ({ page }) => {
  await open(page)
  const side = page.locator('.browse-hero-side').first()
  await expect(side, 'the card figures are drawn').toBeVisible()
  for (const name of [/^\s*Hidden/i, /^\s*Sent/i]) {
    const chip = side.locator(':scope > *').filter({ hasText: name })
    await expect(chip, `a chip for ${name} is drawn`).toHaveCount(1)
    await chip.hover()
    const box = page.getByRole('tooltip')
    await expect(box, `hovering the ${name} chip opens its text box`).toBeVisible()
    await expect(box).toHaveText(/\S/)
    await page.mouse.move(0, 0)
    await chip.focus()
    await expect(chip, `the ${name} chip takes keyboard focus`).toBeFocused()
    await expect(box, `focusing the ${name} chip opens its text box`).toBeVisible()
    await page.keyboard.press('Escape')
  }
})

/* ux-w2 B17 (order-walk-plan.md section 15 rail). Asserts the walk control is a button whose name starts
   with a verb, "Start Walk", and a caption beside it gives the buyer count, "10 buyers". */
/* Two tickable buyers, so the walk control draws (it shows only at two or more). Both buyers take the same on-hand copies. */
function twoBuyersOpen(): OrdersPayload {
  const base = oneOpenOrder()
  const first = base.resolution.orders[0]!
  const second = { ...first, key: 'TCGplayer:ORD-B1', number: 'ORD-B1', lines: first.lines.map((one) => ({ ...one, order: 'ORD-B1', order_key: 'TCGplayer:ORD-B1' })) }
  return {
    ...base,
    summary: '2 orders',
    orders: [base.orders[0]!, { ...base.orders[0]!, key: 'TCGplayer:ORD-B1', number: 'ORD-B1', buyer: 'Ben Franklin' }],
    resolution: { ...base.resolution, orders: [first, second] },
  }
}

test('ux-w2 B17: the walk control is a verb-led button with a buyer-count caption', async ({ page }) => {
  await open(page, { orders: twoBuyersOpen() })
  const control = page.getByRole('button', { name: /^start walk/i })
  await expect(control, 'the walk control is a button whose name starts with a verb').toBeVisible()
  const bar = page.locator('.orders-filterbar')
  await expect(bar.getByRole('button', { name: /^start walk/i }), 'the verb button sits in the filter bar').toHaveCount(1)
  await expect(bar, 'the caption gives the buyer count').toContainText(/\b\d+\s+buyers?\b/i)
})

/* -------------------------------------------------------------------------------------- 1 */

test('only the newest pull in the walk offers Undo — the older one reads Sold', async ({ page }) => {
  const wire = await open(page)

  /* `.card-locations-row` is `CardLocations.tsx`'s own copy row, reused whole
   * (D304, lane A3) — the old `.orders-card-copy`
   * pane forked its own rows, and that fork is deleted. */
  const rows = page.locator(`${CURRENT_PICK} .card-locations-row`)
  /* THE SLOT HOLDS EVERY STATE (D118): the Mark sold icon, the Undo icon and the Sold pill all
     fit the one reserved width, so a press never moves the place beside it. */
  const slotWidth = () => rows.nth(0).locator('.card-locations-action').evaluate((el) => Math.round(el.getBoundingClientRect().width))
  const atRest = await slotWidth()
  await rows.nth(0).getByRole('button', { name: /^Mark Sold/ }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(1)

  // The copy just sold is the only one recorded so far, so it is the newest — and undoable.
  await expect(rows.nth(0).getByRole('button', { name: 'Undo' })).toBeVisible()

  await rows.nth(1).getByRole('button', { name: /^Mark Sold/ }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(2)

  /* THE SECOND PULL IS NOW THE NEWEST, WITH NO CLOCK INVOLVED — this assertion is true the
     instant the second write lands, not twenty seconds later or twenty seconds sooner. */
  await expect(rows.nth(1).getByRole('button', { name: 'Undo' })).toBeVisible()
  await expect(rows.nth(0).getByRole('button', { name: 'Undo' })).toHaveCount(0)
  await expect(rows.nth(0).locator('.bn-pill', { hasText: 'Sold' })).toBeVisible()
  expect(await slotWidth(), 'the Sold pill widened the action slot').toBe(atRest)
})

/* A PULL PRESS MOVES NOTHING, MEASURED BY THE BROWSER (D118, D313). The
   cases here compare widths; this one reads the browser's own `layout-shift` entries over the
   500 ms after the press, with no input exclusion, so a line that a new string re-flows is seen. */
test('a pull press causes no layout shift in the half second after it', async ({ page }) => {
  await watchShifts(page)
  const wire = await open(page)
  const rows = page.locator(`${CURRENT_PICK} .card-locations-row`)
  await expect(rows.nth(0)).toBeVisible()
  await settleMotion(page)
  await afterPaint(page)

  const from = await markNow(page)
  await rows.nth(0).getByRole('button', { name: /^Mark Sold/ }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(1)
  await expect(rows.nth(0).getByRole('button', { name: 'Undo' })).toBeVisible()
  await page.waitForTimeout(600) // keep: shifts are read over the 500ms window after the press

  const inWindow = (await readShifts(page)).shifts.filter((s) => s.at >= from && s.at < from + 500)
  expect(sumOf(inWindow), `the press moved ${describeShifts(inWindow)}`).toBeLessThan(0.0005)
})

/* -------------------------------------------------------------------------------------- 2 */

test('a newer pull is what ends the older one’s Undo, not any span of time', async ({ page }) => {
  /* MUTATION PROOF, READ ALONGSIDE CASE 1: this is case 1's own claim, isolated to the single
     transition it depends on, so a change that made every row keep its own Undo (the bug this
     screen HAD before this fix — per-copy granularity the owner declined) would fail exactly
     here rather than being read as "the newest one also happens to work". */
  const wire = await open(page)
  const rows = page.locator(`${CURRENT_PICK} .card-locations-row`)

  await rows.nth(0).getByRole('button', { name: /^Mark Sold/ }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(1)
  await expect(rows.nth(0).getByRole('button', { name: 'Undo' })).toBeVisible()

  await rows.nth(1).getByRole('button', { name: /^Mark Sold/ }).click()
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
  const rows = page.locator(`${CURRENT_PICK} .card-locations-row`)

  await rows.nth(0).getByRole('button', { name: /^Mark Sold/ }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(1)
  await expect(rows.nth(0).getByRole('button', { name: 'Undo' })).toBeVisible()

  await page.clock.runFor(25_000)

  await expect(rows.nth(0).getByRole('button', { name: 'Undo' })).toBeVisible()
  await expect(rows.nth(0).locator('.bn-pill', { hasText: 'Sold' })).toHaveCount(0)
})

/* -------------------------------------------------------------------------------------- 4 */

test('undoing the newest pull returns it to Mark sold, and the older copy stays Sold', async ({ page }) => {
  const wire = await open(page)
  const rows = page.locator(`${CURRENT_PICK} .card-locations-row`)

  await rows.nth(0).getByRole('button', { name: /^Mark Sold/ }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(1)
  await rows.nth(1).getByRole('button', { name: /^Mark Sold/ }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(2)

  await rows.nth(1).getByRole('button', { name: 'Undo' }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(3)
  const undoBody = wire.filter((one) => one.path.endsWith('/orders/pull'))[2]?.body as { undo?: boolean; targets?: unknown }
  expect(undoBody?.undo).toBe(true)
  expect(undoBody?.targets).toEqual([{ box: 5, index: 22, capture_id: 'cap-b' }])

  await expect(rows.nth(1).getByRole('button', { name: /^Mark Sold/ })).toBeVisible()

  /* THE OLDER RECEIPT REGAINS "NEWEST" ONCE IT IS THE ONLY ONE LEFT — a rank, and ranks are
     recomputed each time the set of receipts changes, exactly as a stack's own top does when
     the item above it is popped. */
  await expect(rows.nth(0).getByRole('button', { name: 'Undo' })).toBeVisible()
})

/* -------------------------------------------------------------------------------------- 5 */

test('the walk\'s card pane carries no listing-correction control — Inventory only', async ({ page }) => {
  /* D252, the owner's ruling verbatim in intent: "Inventory only." The walk's card pane is the
   * photograph, the pick and every copy (UX-169). The card's details, and the correction control
   * `correct-answer.spec.ts` proves on `#/inventory`, are never drawn here. */
  await open(page)

  await expect(page.locator('.browse-card')).toBeVisible()
  // The details table is #/inventory's (UX-169): the walk's pane never draws it, nor its control.
  await expect(page.locator('.browse-details')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Correct' })).toHaveCount(0)
  await expect(page.locator('.card-correction')).toHaveCount(0)
})

/* -------------------------------------------------------------------------------------- 6 */

test('a walk row fills the pane with the hero head, the photo, and every on-hand copy — the chosen one first, no Details fold', async ({
  page,
}) => {
  /* PLAN.md's point 4 test, answered by D304's
   * Q6 (the owner: "we don't need details on this screen") rather than PLAN.md's own
   * recommendation — the whole Details fold is never drawn here. `twoCopyPlan()` puts two
   * on-hand copies on the current row's take, both `here: true`, `3/21` first. */
  await open(page)

  // The hero head — `CardHero.tsx:CardHeroHead`, reused whole.
  await expect(page.getByRole('heading', { name: 'Volcanion' })).toBeVisible()
  // The photo — `CardHero.tsx:PhotoPanel`.
  await expect(page.locator('img.browse-photo')).toBeVisible()

  // Every on-hand copy, in `CardLocations`, the walk's chosen copy first and marked current.
  const rows = page.locator(`${CURRENT_PICK} .card-locations-row`)
  await expect(rows).toHaveCount(2)
  await expect(rows.nth(0)).toHaveAttribute('aria-current', 'true')
  await expect(rows.nth(1)).not.toHaveAttribute('aria-current', 'true')

  // No Details fold on this screen.
  await expect(page.locator('.browse-details')).toHaveCount(0)
})

/* -------------------------------------------------------------------------------------- 7 */

/* PLAN.md's point 3 test (A4): every walk row carries its own here-copies as `CardLocations`
 * rows — box, section and card, the neighbours, the strip and the ruler — and Mark sold on one
 * of THEM records against THAT row's own take, never the pane's current one.
 *
 * TWO STOPS, TWO SKUs, DELIBERATELY: the walk lands on the FIRST stop's take by default
 * (`useOrderWalk`'s own landing rule), so a press on the SECOND stop's own row is the one case
 * that can tell the fix from the bug it replaces. Before A4's `onSell(copy, forTake)`, every
 * press anywhere in the walk list sent `currentRow.take` regardless of which row's button was
 * pressed — this would have sent Volcanion's SKU for a copy that is Tricksy Tentacles. */
function twoStopTwoSkuPlan(): WalkPlan {
  return walkPlanOf([
    walkPlanStop({
      key: 'box/3/section/2',
      box: 3,
      box_name: 'RB Epics',
      section: 2,
      order: 1,
      takes: [
        walkPlanTake({
          wanted: 1,
          copies: [
            walkPlanCopy({
              box: 3,
              index: 21,
              capture_id: 'cap-a',
              key: '3/21',
              neighbors: { prev: { slot: 16, index: 20, name: 'Alpha Strike' }, next: { slot: 18, index: 22, name: 'Keeper of Masks' } },
            }),
          ],
        }),
      ],
    }),
    walkPlanStop({
      key: 'box/5/section/4',
      box: 5,
      box_name: 'WB1 R2',
      section: 4,
      order: 2,
      takes: [
        walkPlanTake({
          sku: '9191487',
          name: 'Tricksy Tentacles',
          number_display: '008',
          wanted: 1,
          for: [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, buyer: 'Ada Lovelace', owed: 1 }],
          copies: [
            walkPlanCopy({
              box: 5,
              index: 40,
              capture_id: 'cap-b',
              key: '5/40',
              slot: 30,
              card: 30,
              label: 'WB1 R2, Section 4, Card 30',
              box_total: 60,
              neighbors: { prev: { slot: 29, index: 39, name: 'Piercing Light' }, next: { slot: 31, index: 41, name: 'Shadow Veil' } },
              place: { box_name: 'WB1 R2', section: 4, section_start: 25, section_end: 40 },
            }),
          ],
        }),
      ],
    }),
  ])
}

const SKU_B = '9191487'

/** The two-line order `twoStopTwoSkuPlan()` walks: Volcanion (`SKU`) and Tricksy Tentacles (`SKU_B`). */
function twoSkuOrders(): OrdersPayload {
  const lineB = line({
    sku: SKU_B,
    wanted: 1,
    owed: 1,
    fulfilled: 0,
    outstanding: 1,
    on_hand: 1,
    line: { sku: SKU_B, quantity: 1, name: 'Tricksy Tentacles', number: '008', printing: 'Normal', condition: 'Near Mint', rarity: 'Rare', unit_price: '1.24', kind: 'single' },
    picks: [
      pick({
        card_name: 'Tricksy Tentacles',
        card_number: '008',
        box: 5,
        index: 40,
        capture_id: 'cap-b',
        place: place({ box: 5, index: 40, slot: 30, card: 30, label: 'WB1 R2, Section 4, Card 30' }),
      }),
    ],
  })
  return payloadOf(
    [
      order({
        wanted: 2,
        lines: [line().line, lineB.line],
        progress: [
          ...order().progress,
          { sku: SKU_B, wanted: 1, recorded: 0, outstanding: 1, over: 0, copies: [], at: null, by_hand: 0, reason: null, declared_kind: null, closed_at: null, closed_reason: null },
        ],
      }),
    ],
    [{ key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, complete: false, outstanding: 2, lines: [line(), lineB] }],
  )
}

test('a walk row draws no copies, a press shows its card in the pane, and Mark sold there sends that row\'s own take', async ({
  page,
}) => {
  const wire = await open(page, { plan: twoStopTwoSkuPlan(), orders: twoSkuOrders() })

  // THE RAIL LINE IS ONE LINE A CARD: the copies, with box, section, neighbours and ruler, are the pane's
  // (`CardLocations`, reused whole), for the card the walk stands on.
  await expect(page.locator('.orders-walk-list .card-locations-row')).toHaveCount(0)
  const paneRows = page.locator('.orders-cardcol .card-locations-row')
  await expect(paneRows).toHaveCount(1)
  await expect(paneRows.first()).toContainText('RB Epics')
  await expect(paneRows.first().locator('.card-locations-identity')).toBeVisible()
  await expect(paneRows.first().locator('.position-bar[data-depth="on"]')).toBeVisible()

  // THE WALK LANDS ON THE FIRST STOP (Volcanion). A press on the SECOND row shows Tricksy Tentacles in
  // the pane, and Mark sold there must record THAT take's own SKU and THAT copy's own target.
  await page.locator('.orders-walk-press', { hasText: 'Tricksy Tentacles' }).click()
  await expect(paneRows).toHaveCount(1)
  await expect(paneRows.first()).toContainText('WB1 R2')
  await paneRows.first().getByRole('button', { name: /^Mark Sold/ }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(1)
  const sent = wire.find((one) => one.path.endsWith('/orders/pull'))
  expect(sent?.body).toMatchObject({
    sku: SKU_B,
    targets: [{ box: 5, index: 40, capture_id: 'cap-b' }],
  })
})

/* -------------------------------------------------------------------------------------- 8 */

/* The strip above the card detail (`OrdersWalkPane.tsx:WalkStrip`) draws each card's STOCK image
 * (`docs/specs/stock-images.md`) in place of the owner's cropped photograph, and falls back
 * to that photograph on a join miss (`image_url: null`) or a load failure, the way
 * `Pricing.tsx:PricingThumb` does. The big photo below it stays the owner's own. The image rides
 * on `POST /inventory/copies`' per-card entry, the same `rawCards` the strip already reads.
 *
 * TWO STOPS, TWO SKUs: the strip draws only with two or more cards. The takes want 3 and 2, so
 * the count badges are told apart from a bare "1". The image is told from the photograph by its
 * `src`: a photograph is always served from `/photo/`. */
const STOCK_A = 'https://tcgplayer-cdn.tcgplayer.com/product/705996_200w.jpg'
const STOCK_B = 'https://tcgplayer-cdn.tcgplayer.com/product/705997_200w.jpg'
const STOCK_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="63" height="88"><rect width="63" height="88" fill="#ccc"/></svg>'

function stripPlan(): WalkPlan {
  const plan = twoStopTwoSkuPlan()
  return walkPlanOf(plan.stops.map((stop, at) => ({ ...stop, takes: stop.takes.map((take) => ({ ...take, wanted: at === 0 ? 3 : 2 })) })))
}

function stripCards(imageA: string | null, imageB: string | null): Record<string, object> {
  return {
    '3/21': { ...WALK_CARD, image_url: imageA },
    '5/40': {
      ...WALK_CARD,
      box: 5,
      index: 40,
      label: 'WB1 R2, Section 4, Card 30',
      section: 4,
      card: 30,
      photo: 'photos/5/40.jpg',
      capture_id: 'cap-b',
      name: 'Tricksy Tentacles',
      number: '008',
      number_display: '008',
      sku: SKU_B,
      image_url: imageB,
    },
  }
}

async function stubStock(page: Page, url: string, status = 200): Promise<{ hits: () => number }> {
  let hits = 0
  await page.route(url, (route) => {
    hits += 1
    return status === 200
      ? route.fulfill({ status, contentType: 'image/svg+xml', body: STOCK_SVG })
      : route.fulfill({ status, contentType: 'text/plain', body: 'gone' })
  })
  return { hits: () => hits }
}

const STRIP_CARD = '.orders-strip-card'

test('the strip draws each card\'s stock image, keeps its count badge, and leaves the big photo the owner\'s own', async ({ page }) => {
  await stubStock(page, STOCK_A)
  await stubStock(page, STOCK_B)
  await open(page, { plan: stripPlan(), orders: twoSkuOrders(), cards: stripCards(STOCK_A, STOCK_B) })

  const thumbs = page.locator(STRIP_CARD)
  await expect(thumbs).toHaveCount(2)
  await expect(thumbs.nth(0).locator('img')).toHaveAttribute('src', STOCK_A)
  await expect(thumbs.nth(1).locator('img')).toHaveAttribute('src', STOCK_B)
  await expect(thumbs.nth(0).locator('.orders-strip-count')).toHaveText('3')
  await expect(thumbs.nth(1).locator('.orders-strip-count')).toHaveText('2')
  // The big photo below the strip is the owner's own, though its card carries a stock image too.
  await expect(page.locator('img.browse-photo')).toHaveAttribute('src', /\/photo\//)
})

test('a join miss draws the owner\'s own photograph in the strip, and the count badge stays', async ({ page }) => {
  await open(page, { plan: stripPlan(), orders: twoSkuOrders(), cards: stripCards(null, null) })

  const thumbs = page.locator(STRIP_CARD)
  await expect(thumbs).toHaveCount(2)
  await expect(thumbs.nth(0).locator('img')).toHaveAttribute('src', /\/photo\//)
  await expect(thumbs.nth(1).locator('img')).toHaveAttribute('src', /\/photo\//)
  await expect(thumbs.nth(0).locator('.orders-strip-count')).toHaveText('3')
  await expect(thumbs.nth(1).locator('.orders-strip-count')).toHaveText('2')
})

test('a stock image that fails to load falls back to the owner\'s photograph, and the other thumbnail keeps its own', async ({ page }) => {
  const gone = await stubStock(page, STOCK_A, 404)
  await stubStock(page, STOCK_B)
  await open(page, { plan: stripPlan(), orders: twoSkuOrders(), cards: stripCards(STOCK_A, STOCK_B) })

  const thumbs = page.locator(STRIP_CARD)
  await expect(thumbs).toHaveCount(2)
  // The strip asked for the stock image (a 404 is only a failure once it was requested), then gave up on it.
  await expect.poll(gone.hits).toBeGreaterThan(0)
  await expect(thumbs.nth(0).locator('img')).toHaveAttribute('src', /\/photo\//)
  await expect(thumbs.nth(1).locator('img')).toHaveAttribute('src', STOCK_B)
  await expect(thumbs.nth(0).locator('.orders-strip-count')).toHaveText('3')
  await expect(thumbs.nth(1).locator('.orders-strip-count')).toHaveText('2')
})

/* ------------------------------------------------- a shipped order that still owes copies

   A TCGplayer order already at "Shipped - In Transit" when Banchi first fetches it: one line, 4 of
   SKU `SKU`, with 3 copies on hand at stop A (box 3, section 2) and 1 at stop B (box 5, section 1).
   The feed closes the order (`open: false`), but `ownsAWalkableBody` still walks it while copies
   are owed (`terminal && wanted > recorded`). `recorded` is how many of the four are already sold.

   The pick chip, the order panel and the head each read one of these figures. The walk is drawn
   for the buyer only while the buyer has an open order, so the chip cases hold a second, open order
   for the same buyer (another SKU, no copies on hand). A lone shipped order draws its done banner
   instead of the walk, which is the defect the panel case below names. */

const SHIPPED_STATUS = 'Shipped - In Transit'
const SIBLING_NUMBER = 'ORD-OPEN'

/** The four copies, store-wide. `stop` is the stop whose take reaches the copy (its `here`). */
const FOUR_COPIES = [
  { key: '3/21', box: 3, index: 21, card: 17, slot: 17, capture_id: 'cap-a', section: 2, stop: 'A' },
  { key: '3/22', box: 3, index: 22, card: 18, slot: 18, capture_id: 'cap-c', section: 2, stop: 'A' },
  { key: '3/23', box: 3, index: 23, card: 19, slot: 19, capture_id: 'cap-d', section: 2, stop: 'A' },
  { key: '5/22', box: 5, index: 22, card: 18, slot: 18, capture_id: 'cap-b', section: 1, stop: 'B' },
] as const

/** The copies still on hand, as one stop's take lists them: every copy in the store, `here` where it stands at that stop. */
function shippedCopies(gone: ReadonlySet<string>, stop: 'A' | 'B'): WalkPlanCopy[] {
  return FOUR_COPIES.filter((copy) => !gone.has(copy.key)).map((copy) =>
    walkPlanCopy({
      box: copy.box,
      index: copy.index,
      slot: copy.slot,
      card: copy.card,
      capture_id: copy.capture_id,
      label: `Box ${copy.box}, Section ${copy.section}, Card ${copy.card}`,
      here: copy.stop === stop,
      place: { section: copy.section },
    }),
  )
}

/** The walk plan for the shipped order's copies still owed: `aWanted` to take at stop A and `bWanted`
 *  at stop B, with the copies in `gone` already sold. A stop the plan does not visit is left out. */
function shippedPlan(gone: ReadonlySet<string>, aWanted: number, bWanted: number): WalkPlan {
  const forRef: WalkPlanRef = { key: `TCGplayer:${ORDER_NUMBER}`, number: ORDER_NUMBER, buyer: 'Ada Lovelace', owed: aWanted + bWanted }
  const stops = [
    walkPlanStop({
      key: 'box/3/section/2',
      box: 3,
      section: 2,
      order: 1,
      span: { start: 12, end: 30 },
      takes: [walkPlanTake({ wanted: aWanted, for: [forRef], copies: shippedCopies(gone, 'A') })],
    }),
    walkPlanStop({
      key: 'box/5/section/1',
      box: 5,
      box_name: 'RB Epics',
      section: 1,
      order: 2,
      span: { start: 1, end: 11 },
      takes: [walkPlanTake({ wanted: bWanted, for: [forRef], copies: shippedCopies(gone, 'B') })],
    }),
  ].filter((stop) => stop.takes[0]!.wanted > 0)
  return walkPlanOf(stops)
}

/** `POST /inventory/copies` for the copies still on hand. A sold copy has no card in the answer. */
function shippedCards(gone: ReadonlySet<string>): Record<string, object> {
  const out: Record<string, object> = {}
  for (const copy of FOUR_COPIES) {
    if (gone.has(copy.key)) continue
    out[copy.key] = {
      ...WALK_CARD,
      box: copy.box,
      index: copy.index,
      capture_id: copy.capture_id,
      card: copy.card,
      section: copy.section,
      label: `Box ${copy.box}, Section ${copy.section}, Card ${copy.card}`,
      photo: `photos/${copy.box}/${copy.index}.jpg`,
      metadata_finish: 'foil',
    }
  }
  return out
}

/** The shipped order with `recorded` of its four copies already sold. */
function shippedOrder(recorded: number): OrderRow {
  return order({
    status: SHIPPED_STATUS,
    open: false,
    terminal: true,
    wanted: 4,
    recorded,
    lines: [{ ...line().line, quantity: 4 }],
    progress: [
      {
        sku: SKU,
        wanted: 4,
        recorded,
        outstanding: 4 - recorded,
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
}

function shippedResolved(recorded: number): ResolvedOrder {
  return {
    key: `TCGplayer:${ORDER_NUMBER}`,
    number: ORDER_NUMBER,
    complete: false,
    outstanding: 0,
    lines: [line({ wanted: 4, owed: 4 - recorded, fulfilled: recorded, outstanding: 0, on_hand: 4 - recorded })],
  }
}

/** The buyer's second order: still open, for another SKU with no copies on hand. It is not walked. */
function siblingOrder(): OrderRow {
  return order({
    key: `TCGplayer:${SIBLING_NUMBER}`,
    number: SIBLING_NUMBER,
    status: 'Ready to ship',
    open: true,
    terminal: false,
    wanted: 1,
    recorded: 0,
    lines: [{ ...line().line, sku: SKU_B, name: 'Dragonite', number: '090' }],
    progress: [],
  })
}

function siblingResolved(): ResolvedOrder {
  return {
    key: `TCGplayer:${SIBLING_NUMBER}`,
    number: SIBLING_NUMBER,
    complete: false,
    outstanding: 1,
    lines: [
      line({
        order: SIBLING_NUMBER,
        order_key: `TCGplayer:${SIBLING_NUMBER}`,
        line: { ...line().line, sku: SKU_B, name: 'Dragonite', number: '090' },
        sku: SKU_B,
        reason: 'no_copies_on_hand',
        wanted: 1,
        owed: 1,
        fulfilled: 0,
        outstanding: 1,
        on_hand: 0,
        picks: [],
      }),
    ],
  }
}

/** The buyer's orders with the shipped order and its open sibling. */
function withSibling(recorded: number): OrdersPayload {
  return payloadOf([shippedOrder(recorded), siblingOrder()], [shippedResolved(recorded), siblingResolved()])
}

/* ---------------------------------------------------------------- 1. the pick chip counts what is still owed */

test('the pick chip says the copies still to pick, and the ones at this stop beside them', async ({ page }) => {
  await open(page, { plan: shippedPlan(new Set(), 3, 1), orders: withSibling(0), cards: shippedCards(new Set()) })
  const chip = page.locator('.orders-pick-chip .orders-pick-live')
  await expect(chip, 'the pick chip is drawn at stop A').toBeVisible()
  await expect(chip, 'four copies are still to pick, three of them here').toHaveText('Pick 4 3 here')
})

test('after one sale at this stop the chip reads Pick 3 and 2 here', async ({ page }) => {
  let gone = new Set<string>()
  const wire = await open(page, {
    plan: () => shippedPlan(gone, gone.has('3/21') ? 2 : 3, 1),
    orders: () => withSibling(gone.size),
    cards: () => shippedCards(gone),
    onPull: () => {
      gone = new Set(['3/21'])
    },
  })
  const chip = page.locator('.orders-pick-chip .orders-pick-live')
  await expect(chip, 'the pick chip is drawn before the sale').toBeVisible()
  await page.locator(`${CURRENT_PICK} .card-locations-row`).nth(0).getByRole('button', { name: /^Mark Sold/ }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(1)
  await expect(chip, 'three copies still to pick, two of them here').toHaveText('Pick 3 2 here')
})

test('one copy left, at this stop, reads Pick 1 alone', async ({ page }) => {
  const gone = new Set(['3/21', '3/22', '3/23'])
  await open(page, { plan: shippedPlan(gone, 0, 1), orders: withSibling(3), cards: shippedCards(gone) })
  await expect(page.locator('.orders-pick-chip .orders-pick-live'), 'the last copy reads alone').toHaveText('Pick 1')
})

test('a copy sold at stop A leaves stop B\'s line and chip unpicked: a sale counts against the stop it was made at', async ({ page }) => {
  let gone = new Set<string>()
  const wire = await open(page, {
    plan: () => shippedPlan(gone, gone.has('3/21') ? 2 : 3, 1),
    orders: () => withSibling(gone.size),
    cards: () => shippedCards(gone),
    onPull: () => {
      gone = new Set(['3/21'])
    },
  })
  // Stop B's line is the one whose only slot is #18, its copy in box 5. Stop A's line lists #17 to #19.
  const stopB = page.locator('.orders-walk-line', { has: page.locator('.orders-walk-slot', { hasText: /^#18$/ }) })
  await expect(stopB, 'stop B\'s line is drawn before the sale').toHaveCount(1)
  await expect(stopB.locator('.orders-walk-pick'), 'stop B reads unpicked before the sale').toHaveText(/^Pick /)
  await page.locator(`${CURRENT_PICK} .card-locations-row`).nth(0).getByRole('button', { name: /^Mark Sold/ }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(1)
  await expect(stopB, 'stop B is not struck through: the copy sold was stop A\'s pick').not.toHaveClass(/is-done/)
  await expect(stopB.locator('.orders-walk-pick'), 'stop B still reads Pick, not Picked').toHaveText(/^Pick /)
  await stopB.locator('.orders-walk-press').click()
  await expect(page.locator('.orders-pick-chip .orders-pick-live'), 'the chip at stop B reads Pick, not Picked').toHaveText(/^Pick /)
})

/* ---------------------------------------------------------------- 2. the order panel does not say Done while copies are owed */

/** The lone shipped buyer (no open sibling), with one of its four copies already sold. F1 lists a
 *  shipped buyer that still owes copies under Open, the default filter, and not under Done: the
 *  comment on `ownsAWalkableBody` in `app/src/orderBuyers.ts` says an order the marketplace calls
 *  done while copies are still owed is opened back up. So the case finds the buyer in the default
 *  list, checks that Done shows no buyer, then opens the buyer's row. */
async function openLoneShipped(page: Page): Promise<void> {
  const gone = new Set(['3/21'])
  await open(page, { plan: shippedPlan(gone, 2, 1), orders: payloadOf([shippedOrder(1)], [shippedResolved(1)]), cards: shippedCards(gone) })
  const row = page.locator('.orders-index-row', { hasText: 'Ada Lovelace' })
  await expect(row, 'the buyer lists under Open, the default filter').toHaveCount(1)
  await showDoneOnly(page)
  /* The empty title is drawn only for a Done-only view, so it states both the view and the buyer's absence. */
  await expect(page.getByText('Nothing done yet'), 'Done shows no buyer, so the buyer is not under Done').toBeVisible()
  await showOpenOnly(page)
  await row.click()
}

test('a shipped order that still owes copies draws no done banner', async ({ page }) => {
  await openLoneShipped(page)
  await expect(page.locator('.orders-walk-done'), 'three copies are still owed, so there is no Shipped or All Sold banner').toHaveCount(0)
})

test('the order panel shows no Done pill while a shipped order still owes copies', async ({ page }) => {
  await openLoneShipped(page)
  const panel = page.locator('.orders-panel-facts')
  await expect(panel, 'the order panel is drawn').toHaveCount(1)
  await expect(panel, 'the status is not Done').not.toContainText('Done')
})

test('to pick counts the copies still owed on a shipped order, not zero', async ({ page }) => {
  await openLoneShipped(page)
  const toPick = page.locator('.orders-panel-figures .bn-stat').nth(0)
  await expect(toPick.locator('.bn-stat-label')).toHaveText('to pick')
  await expect(toPick.locator('.bn-stat-value'), 'three of the four are still owed').toHaveText('3')
})

/* ---------------------------------------------------------------- 3. the head keeps the card it stands on after a sale */

test('control: the walk head draws the shipped order\'s card before any sale', async ({ page }) => {
  await open(page, { plan: shippedPlan(new Set(), 3, 1), orders: withSibling(0), cards: shippedCards(new Set()) })
  const head = page.locator('.browse-card')
  await expect(head, 'the head is drawn with the card').toContainText('Volcanion')
  await expect(head, 'the head shows its finish').toContainText('Foil')
  await expect(head, 'the head draws a photograph').not.toContainText('No photo was stored')
})

test('after a sale on the copy the head stands on, the head keeps its photograph and finish', async ({ page }) => {
  let gone = new Set<string>()
  let sold = false
  let rereads = 0
  // The copies read that follows the sale: the head is judged once it has landed, never during the
  // gap before it, when the sold copy's card is still the one on screen.
  page.on('request', (request) => {
    if (sold && /\/inventory\/copies$/.test(request.url())) rereads += 1
  })
  const wire = await open(page, {
    plan: () => shippedPlan(gone, gone.has('3/21') ? 2 : 3, 1),
    orders: () => withSibling(gone.size),
    cards: () => shippedCards(gone),
    onPull: () => {
      gone = new Set(['3/21'])
      sold = true
    },
  })
  const head = page.locator('.browse-card')
  await expect(head, 'the head shows its finish before the sale (control)').toContainText('Foil')
  await expect(head, 'the head draws a photograph before the sale (control)').not.toContainText('No photo was stored')
  await page.locator(`${CURRENT_PICK} .card-locations-row`).nth(0).getByRole('button', { name: /^Mark Sold/ }).click()
  await expect.poll(() => wire.filter((one) => one.path.endsWith('/orders/pull')).length).toBe(1)
  await expect.poll(() => rereads, 'the copies are read again after the sale').toBeGreaterThan(0)
  // The read has answered and the head has taken it: the settled head, not a frame of the gap.
  await page.waitForLoadState('networkidle')
  await expect(head, 'the head keeps its finish after the sale').toContainText('Foil')
  await expect(head, 'the head keeps its photograph after the sale').not.toContainText('No photo was stored')
})

/* ---------------------------------------------------------------- 4. each receipt names the place its own copy stood at */

test('three digit presses on copies at three places give three receipts, each naming its own place', async ({ page }) => {
  // Three copies of one take, all at stop A: boxes and slots 17, 18 and 19, so three places a receipt can name.
  const wire = await open(page, { plan: shippedPlan(new Set(), 3, 0), orders: withSibling(0), cards: shippedCards(new Set()) })
  const pulls = () => wire.filter((one) => one.path.endsWith('/orders/pull')).length
  // The digits are drawn beside the current pick's presses once the walk has landed; a key pressed before that reaches nothing.
  await expect.poll(() => page.locator(`${CURRENT_PICK} .card-locations-sell`).evaluateAll((els) => els.map((el) => el.getAttribute('aria-keyshortcuts'))), 'the three copies carry their digits').toEqual(['1', '2', '3'])
  for (const [at, key] of (['1', '2', '3'] as const).entries()) {
    await page.keyboard.press(key)
    await expect.poll(pulls, `digit ${key} sent its own pull`).toBe(at + 1)
  }
  const receipts = page.locator('.bn-toast-receipt')
  await expect(receipts, 'one receipt per digit press').toHaveCount(3)
  const cardsNamed = async () => (await receipts.allTextContents()).map((text) => text.match(/Card \d+/)?.[0] ?? text).sort()
  await expect.poll(cardsNamed, 'the three receipts name three different cards, each its own copy\'s place').toEqual(['Card 17', 'Card 18', 'Card 19'])
})

/* ------------------------------------------------------------------ the return read and its tally */

/* THE RETURN READ AND THE TALLY IT LEAVES. `useOrderWalk`'s `reread` puts the server's plan in place
 * whenever the window regains focus or the tab becomes visible. That plan already nets the walk's own sales out of
 * `owed`, while `tallyRef` still counts them, so `pickOrderFor` takes each sale away twice. With one copy sold the
 * order's `owed` is 1 and the tally is 1, so `remaining` is 0 and the next press is refused, though the order still
 * wants a copy. The control below is the same walk with no return read: the second sale is accepted there. */

/** The copies in the order the rows draw them: row 0 is `3/21`, and a press takes them in this order. */
const PRESS_ORDER = ['3/21', '5/22'] as const

/** Every `/orders/pull` on the wire, in the order it was sent. */
function pullsOf(wire: readonly Wire[]): Wire[] {
  return wire.filter((one) => one.path.endsWith('/orders/pull'))
}

test('a return read after a sale does not refuse the next sale of the same order', async ({ page }) => {
  let pressed = 0
  const wire = await open(page, {
    plan: () => twoCopyPlan(new Set(PRESS_ORDER.slice(0, pressed))),
    onPull: () => {
      pressed += 1
    },
  })
  const rows = page.locator(`${CURRENT_PICK} .card-locations-row`)
  await expect(rows, 'before the return read the pane holds both copies').toHaveCount(2)

  await rows.nth(0).getByRole('button', { name: /^Mark Sold/ }).click()
  await expect.poll(() => pullsOf(wire).length, 'the first sale reaches the server').toBe(1)

  // A real return fires both events, and the walk's 300ms debounce makes them one read.
  await page.evaluate(() => {
    window.dispatchEvent(new Event('focus'))
    document.dispatchEvent(new Event('visibilitychange'))
  })
  await expect(rows, 'the return read drops the sold copy from the pane').toHaveCount(1)

  await rows.nth(0).getByRole('button', { name: /^Mark Sold/ }).click()
  const refusal = page.locator('.bn-toast', { hasText: 'Nobody here still owes a copy' })
  await expect(rows.nth(0).getByRole('button', { name: 'Undo' }).or(refusal), 'the second press answers with a sale or a refusal').toBeVisible()
  expect(await refusal.count(), 'after a return read the next press is refused: pickOrderFor subtracts the sold copy a second time').toBe(0)

  await expect.poll(() => pullsOf(wire).length, 'the second sale reaches the server').toBe(2)
  expect(pullsOf(wire).map((one) => (one.body as { targets?: unknown }).targets)).toEqual([
    [{ box: 3, index: 21, capture_id: 'cap-a' }],
    [{ box: 5, index: 22, capture_id: 'cap-b' }],
  ])
  await expect(page.locator('.orders-pick-chip .orders-pick-live'), 'both copies are picked, so the chip reads Picked').toHaveText(/^Picked/)
})

test('control: with no return read, the next sale of the same order is accepted', async ({ page }) => {
  let pressed = 0
  const wire = await open(page, {
    plan: () => twoCopyPlan(new Set(PRESS_ORDER.slice(0, pressed))),
    onPull: () => {
      pressed += 1
    },
  })
  const rows = page.locator(`${CURRENT_PICK} .card-locations-row`)
  await expect(rows, 'before any sale the pane holds both copies').toHaveCount(2)

  await rows.nth(0).getByRole('button', { name: /^Mark Sold/ }).click()
  await expect.poll(() => pullsOf(wire).length, 'the first sale reaches the server').toBe(1)
  await expect(rows, 'with no return read the pane still holds both copies').toHaveCount(2)

  await rows.nth(1).getByRole('button', { name: /^Mark Sold/ }).click()
  await expect.poll(() => pullsOf(wire).length, 'the second sale reaches the server').toBe(2)
  expect(await page.locator('.bn-toast', { hasText: 'Nobody here still owes a copy' }).count(), 'no refusal is raised').toBe(0)
  await expect(page.locator('.orders-pick-chip .orders-pick-live'), 'both copies are picked, so the chip reads Picked').toHaveText(/^Picked/)
})

/* ------------------------------------------------------------------ focus after a swap */

/* FOCUS AFTER A SWAP. `RowAction` replaces `MarkSoldButton` with `UndoSaleButton` on a press, and back
 * again on an Undo. The button that is removed held focus, so focus drops to the page unless the button that
 * replaces it takes it. Each case waits for the write to settle before it reads focus, because the write disables
 * the button while it is out. */

test('a Mark sold press leaves focus on the Undo that replaces it, never on the body', async ({ page }) => {
  const wire = await open(page)
  const rows = page.locator(`${CURRENT_PICK} .card-locations-row`)

  await rows.nth(0).getByRole('button', { name: /^Mark Sold/ }).click()
  await expect.poll(() => pullsOf(wire).length, 'the sale reaches the server').toBe(1)
  await expect(rows.nth(0).locator('.card-locations-undo'), 'the row draws Undo after the sale').toHaveCount(1)
  await expect(rows.nth(0).locator('.card-locations-undo'), 'the Undo is enabled again once its write lands').toBeEnabled()

  expect(await heldFocus(page), 'focus lands on the Undo that replaced Mark sold').toContain('card-locations-undo')
})

test('an Undo press leaves focus on the Mark sold that replaces it, never on the body', async ({ page }) => {
  const wire = await open(page)
  const rows = page.locator(`${CURRENT_PICK} .card-locations-row`)

  await rows.nth(0).getByRole('button', { name: /^Mark Sold/ }).click()
  await expect.poll(() => pullsOf(wire).length, 'the sale reaches the server').toBe(1)
  const undo = rows.nth(0).locator('.card-locations-undo')
  await expect(undo, 'the row draws Undo after the sale').toHaveCount(1)
  await expect(undo, 'the Undo is enabled before it is pressed').toBeEnabled()

  await undo.click()
  await expect.poll(() => pullsOf(wire).length, 'the undo reaches the server').toBe(2)
  const sell = rows.nth(0).locator('.card-locations-sell')
  await expect(sell, 'the row draws Mark sold again after the undo').toHaveCount(1)
  await expect(sell, 'the Mark sold is enabled once the undo lands').toBeEnabled()

  expect(await heldFocus(page), 'focus lands on the Mark sold that replaced Undo').toContain('card-locations-sell')
})

/* -------------------------------------------------------------------------------------- 8 */

/* FOCUS ACROSS THE KEYS. A digit key sells the current pick and `U` undoes the newest sale. Neither passes through a
 * button's own press, so neither reaches the note that press leaves for the button that replaces it. */

test('a digit-key sale leaves focus on the pick row that held it, and does not take it for the Undo', async ({ page }) => {
  const wire = await open(page)
  const rows = page.locator(`${CURRENT_PICK} .card-locations-row`)
  await expect(rows, 'the pane holds both copies').toHaveCount(2)

  await page.locator('.orders-walk-line .orders-walk-press').first().click()
  expect(await heldFocus(page), 'a pick row holds focus before the digit').toContain('orders-walk-press')

  await page.keyboard.press('1')
  await expect.poll(() => pullsOf(wire).length, 'the digit sends its sale').toBe(1)
  await expect(rows.nth(0).locator('.card-locations-undo'), 'the copy the digit sold draws Undo').toHaveCount(1)
  await expect(rows.nth(0).locator('.card-locations-undo'), 'the Undo is enabled once its write lands').toBeEnabled()

  expect(await heldFocus(page), 'a digit sale does not take focus from the control that holds it').toContain('orders-walk-press')
})

test('control: a digit-key sale with no control holding focus draws focus onto its Undo', async ({ page }) => {
  const wire = await open(page)
  const rows = page.locator(`${CURRENT_PICK} .card-locations-row`)
  await expect(rows, 'the pane holds both copies').toHaveCount(2)
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
  expect(await heldFocus(page), 'nothing holds focus before the digit').toBe('BODY')

  await page.keyboard.press('1')
  await expect.poll(() => pullsOf(wire).length, 'the digit sends its sale').toBe(1)
  await expect(rows.nth(0).locator('.card-locations-undo'), 'the copy the digit sold draws Undo').toHaveCount(1)
  await expect(rows.nth(0).locator('.card-locations-undo'), 'the Undo is enabled once its write lands').toBeEnabled()

  expect(await heldFocus(page), 'focus lands on the Undo the digit drew').toContain('card-locations-undo')
})

test('U after a Mark sold leaves focus on the Mark sold that replaces the Undo, never on the body', async ({ page }) => {
  const wire = await open(page)
  const rows = page.locator(`${CURRENT_PICK} .card-locations-row`)

  await rows.nth(0).getByRole('button', { name: /^Mark Sold/ }).click()
  await expect.poll(() => pullsOf(wire).length, 'the sale reaches the server').toBe(1)
  const undo = rows.nth(0).locator('.card-locations-undo')
  await expect(undo, 'the row draws Undo after the sale').toHaveCount(1)
  await expect(undo, 'the Undo is enabled once its write lands').toBeEnabled()
  expect(await heldFocus(page), 'the Undo holds focus before U is pressed').toContain('card-locations-undo')

  await page.keyboard.press('u')
  await expect.poll(() => pullsOf(wire).length, 'U sends the reversal').toBe(2)
  const sell = rows.nth(0).locator('.card-locations-sell')
  await expect(sell, 'the row draws Mark sold again after U').toHaveCount(1)
  await expect(sell, 'the Mark sold is enabled once the reversal lands').toBeEnabled()

  expect(await heldFocus(page), 'focus lands on the Mark sold that replaced the Undo, never on the body').toContain('card-locations-sell')
})

test('a failed sale leaves no focus note: a later re-render does not move focus', async ({ page }) => {
  let failing = true
  const wire = await open(page, {
    pullFailure: () => (failing ? { status: 500, body: { error: 'the write did not stand' } } : null),
  })
  const rows = page.locator(`${CURRENT_PICK} .card-locations-row`)

  await rows.nth(0).getByRole('button', { name: /^Mark Sold/ }).click()
  await expect.poll(() => pullsOf(wire).length, 'the failed sale reaches the server').toBe(1)
  await expect(page.locator('.bn-toast', { hasText: 'Not marked sold' }), 'the refusal says the sale did not stand').toBeVisible()
  failing = false
  await expect(rows.nth(0).locator('.card-locations-sell'), 'the row is back to Mark sold after the failure').toHaveCount(1)

  await page.locator('.orders-walk-line .orders-walk-press').first().click()
  expect(await heldFocus(page), 'a pick row holds focus after the failure').toContain('orders-walk-press')

  // A LATER RE-RENDER: the return read re-plans the walk, and the answer is the same plan.
  const reread = page.waitForResponse(/\/orders\/walk-plan$/)
  await page.evaluate(() => {
    window.dispatchEvent(new Event('focus'))
    document.dispatchEvent(new Event('visibilitychange'))
  })
  await reread

  expect(await heldFocus(page), 'focus stays on the pick row: nothing from the failed sale takes it').toContain('orders-walk-press')

  // The pick row lets go, and a second return read re-renders the walk. A note the failed sale left must not take focus then.
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
  const again = page.waitForResponse(/\/orders\/walk-plan$/)
  await page.evaluate(() => {
    window.dispatchEvent(new Event('focus'))
    document.dispatchEvent(new Event('visibilitychange'))
  })
  await again
  expect(await heldFocus(page), 'focus stays on the page after the second re-render: nothing takes it').toBe('BODY')
})
