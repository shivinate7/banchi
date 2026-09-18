import type { Page } from '@playwright/test'

import type {
  CodeEntry,
  CodeLedger,
  DepartedCard,
  OrderRow,
  OrdersPayload,
  PickRow,
  Place,
  ResolvedLine,
  ResolvedOrder,
  ShippingBatch,
  ShippingRow,
} from '../src/types'

/* THE BUILDER FUNCTIONS `run-panel.spec.ts`, `orders.spec.ts` AND `shipping.spec.ts` ALREADY
 * WROTE, MOVED HERE SO A FOURTH FILE CAN REUSE THEM RATHER THAN INVENT A COMPETING SHAPE
 * (`D194`'s own gap, closed in the same PR that names it).
 *
 * `app/tests/copy-budget.spec.ts` renders `#/runs`, `#/orders`, `#/shipping`, `#/codes` and
 * `#/graveyard` off `sealEveryTest({ store: true, cards: 122 })` alone, which draws no run, no
 * order, no export, no code and no departed record for any of the five — so their pinned
 * word ceilings bound an EMPTY-ISH state rather than the busiest one a real store draws, and a
 * session could add a sentence to any of the five without the ratchet ever seeing it in its
 * populated form. This module is what those five routes' POPULATED fixtures are built from:
 * the same shapes `run-panel.spec.ts`'s `runRow`, `orders.spec.ts`'s `place`/`pick`/`line`/
 * `order`/`payloadOf` and `shipping.spec.ts`'s `row`/`batchOf` already prove render correctly,
 * plus two new ones — `codeEntry`/`codeLedgerOf` and `departedCard` — for the two screens no
 * existing spec seeds at all.
 *
 * THE THREE SPECS IMPORT FROM HERE NOW INSTEAD OF DEFINING THEIR OWN COPY. A second copy of
 * `runRow` in `copy-budget.spec.ts` is exactly the drift this repo's own rule against a second
 * implementation warns about — see `pipeline/join.py:number_index_key` in `CLAUDE.md`, the
 * same argument one register down.
 */

/* ---------------------------------------------------------------------------- the runs */

/** One run row, in the shape `GET /pipeline/runs` answers with — `run-panel.spec.ts`'s own
 *  fixture, moved here whole. See that file for why each field is what it is; nothing about
 *  the shape changed in the move. */
export function runRow(overrides: Record<string, unknown> = {}) {
  return {
    run: '2026-08-24-box9-01',
    path: '/tmp/runs/2026-08-24-box9-01',
    capture_dir: '/tmp/captures/cards/box9',
    scope: { box: 9, whole_box: true, cards: null },
    box: 9,
    box_name: null,
    live: false,
    pid: null,
    phase: 'join',
    batch_ids: ['msgbatch_x'],
    collected: true,
    joined: false,
    counts: {},
    usage: { input_tokens: 290470, output_tokens: 3761, cost_usd: 0.154638 },
    ...overrides,
  }
}

/** Several real-shaped runs across a few boxes and phases, so `#/runs` draws its list rather
 *  than the empty "no runs yet" state — reasoning, review, and a spent one. */
export function severalRuns(): unknown[] {
  return [
    runRow({
      run: '2026-09-10-box9-01',
      box: 9,
      box_name: null,
      phase: 'join',
      collected: true,
      joined: false,
      counts: { queued: 3 },
    }),
    runRow({
      run: '2026-09-09-box12-01',
      box: 12,
      box_name: 'codes',
      path: '/tmp/runs/2026-09-09-box12-01',
      capture_dir: '/tmp/captures/cards/box12',
      scope: { box: 12, whole_box: true, cards: null },
      phase: 'emit',
      collected: true,
      joined: true,
      counts: { listed: 44, sub_threshold: 6 },
      usage: { input_tokens: 41220, output_tokens: 612, cost_usd: 0.0206 },
    }),
    runRow({
      run: '2026-08-22-box1-03',
      box: 1,
      box_name: null,
      box_bid: null,
      box_former: true,
      path: '/tmp/runs/2026-08-22-box1-03',
      capture_dir: '/tmp/captures/cards/box1',
      scope: { box: 1, whole_box: true, cards: null },
      phase: 'identifying',
      live: true,
      pid: 5150,
      collected: false,
      joined: false,
      usage: {},
    }),
  ]
}

/** Stub `GET /pipeline/runs` with a populated list, so `#/runs`'s list state (no run opened)
 *  draws several real rows instead of the "no runs yet" empty state. Every OTHER route `#/runs`
 *  reads — `/boxes`, `/games`, `/search`, `/inventory`, `/pipeline/submissions` — is already
 *  answered by `shell.ts:stubStore`; this is the one route that fixture leaves empty. */
export async function seedPopulatedRuns(page: Page): Promise<void> {
  await page.route(/\/pipeline\/runs$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ runs: severalRuns() }),
    }),
  )
}

/* -------------------------------------------------------------------------- the orders */

/** A position block with every field the server sends — `orders.spec.ts`'s own `place`. */
export function place(over: Partial<Place> = {}): Place {
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

/** One copy the resolver offered — `orders.spec.ts`'s own `pick`. */
export function pick(over: Partial<PickRow> = {}): PickRow {
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

/** One resolved line — `orders.spec.ts`'s own `line`. */
export function line(over: Partial<ResolvedLine> = {}): ResolvedLine {
  const base: ResolvedLine = {
    order: 'A2FFC195-0000F4-006AC',
    order_key: 'TCGplayer:A2FFC195-0000F4-006AC',
    sku: '9191486',
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
      sku: '9191486',
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

/** One order row — `orders.spec.ts`'s own `order`. */
export function order(over: Partial<OrderRow> = {}): OrderRow {
  const base: OrderRow = {
    key: 'TCGplayer:A2FFC195-0000F4-006AC',
    source: 'TCGplayer',
    number: 'A2FFC195-0000F4-006AC',
    placed_at: '2026-08-29T10:00:00+00:00',
    status: 'Ready to ship',
    first_seen: '2026-08-30T09:00:00+00:00',
    changed_at: null,
    buyer: 'Ada Lovelace',
    wanted: 1,
    recorded: 0,
    open: true,
    terminal: false,
    lines: [line().line],
    progress: [
      {
        sku: '9191486',
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
  }
  return { ...base, ...over }
}

/** The whole `GET /orders` payload, tallied from the lines rather than restated beside them —
 *  `orders.spec.ts`'s own `payloadOf`. */
export function payloadOf(orders: OrderRow[], resolved: ResolvedOrder[]): OrdersPayload {
  const all = resolved.flatMap((one) => one.lines)
  const tally = (reason: ResolvedLine['reason']) => all.filter((one) => one.reason === reason).length
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

/** A few open orders with different buyers, statuses and reasons, so `#/orders` draws a real
 *  list rather than "0 orders". Three orders: one fully resolved, one short on hand, one with
 *  no buyer name (D20's optional field, one register up). */
export function severalOrders(): OrdersPayload {
  const shortLine = line({
    order: 'B31A0C7D-0001A2-00311',
    order_key: 'TCGplayer:B31A0C7D-0001A2-00311',
    sku: '9191210',
    reason: 'short',
    wanted: 3,
    owed: 3,
    fulfilled: 1,
    outstanding: 2,
    on_hand: 1,
    line: {
      sku: '9191210',
      quantity: 3,
      name: 'Eiscue',
      number: '112',
      printing: 'Normal',
      condition: 'Near Mint',
      rarity: 'Common',
      unit_price: '0.49',
      kind: 'single',
    },
    picks: [pick({ box: 5, index: 1, capture_id: 'cap-b', card_name: 'Eiscue', card_number: '112' })],
  })
  const noBuyerLine = line({
    order: 'C99E4410-0002B8-004F0',
    order_key: 'TCGplayer:C99E4410-0002B8-004F0',
    sku: '8937370',
    line: {
      sku: '8937370',
      quantity: 1,
      name: 'Thievul',
      number: '090',
      printing: 'Normal',
      condition: 'Near Mint',
      rarity: 'Uncommon',
      unit_price: '0.60',
      kind: 'single',
    },
    picks: [pick({ box: 9, index: 1, capture_id: 'cap-c', card_name: 'Thievul', card_number: '090' })],
  })

  const resolvedOrder = order()
  const shortOrder = order({
    key: 'TCGplayer:B31A0C7D-0001A2-00311',
    number: 'B31A0C7D-0001A2-00311',
    buyer: 'Grace Hopper',
    status: 'Awaiting shipment',
    wanted: 3,
    recorded: 1,
    lines: [shortLine.line],
    progress: [
      {
        sku: '9191210',
        wanted: 3,
        recorded: 1,
        outstanding: 2,
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
  const noBuyerOrder = order({
    key: 'TCGplayer:C99E4410-0002B8-004F0',
    number: 'C99E4410-0002B8-004F0',
    buyer: null,
    status: 'Ready to ship',
    lines: [noBuyerLine.line],
    progress: [
      {
        sku: '8937370',
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

  return payloadOf([resolvedOrder, shortOrder, noBuyerOrder], [
    { key: resolvedOrder.key, number: resolvedOrder.number, complete: false, outstanding: 1, lines: [line()] },
    { key: shortOrder.key, number: shortOrder.number, complete: false, outstanding: 2, lines: [shortLine] },
    { key: noBuyerOrder.key, number: noBuyerOrder.number, complete: false, outstanding: 1, lines: [noBuyerLine] },
  ])
}

/** Stub `GET /orders` with several real orders, so `#/orders` draws its populated list. */
export async function seedPopulatedOrders(page: Page): Promise<void> {
  await page.route(/\/orders$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(severalOrders()),
    }),
  )
}

/* ------------------------------------------------------------------------- the shipping */

/** One shipping row — `shipping.spec.ts`'s own `row`. */
export function shippingRow(over: Partial<ShippingRow> = {}): ShippingRow {
  const base: ShippingRow = {
    order: 'A2FFC195-0000F4-006AC',
    lane: 'parcel',
    reason: 'value_at_threshold',
    certain: true,
    value: '1750.00',
    weight_per_item_oz: null,
    item_count: 1,
    stamp: null,
  }
  return { ...base, ...over }
}

/** The batch, tallied from the rows rather than restated beside them — `shipping.spec.ts`'s
 *  own `batchOf`. */
export function batchOf(rows: ShippingRow[], over: Partial<ShippingBatch> = {}): ShippingBatch {
  const count = (lane: ShippingRow['lane']) => rows.filter((one) => one.lane === lane).length
  const base: ShippingBatch = {
    /* `shipping.spec.ts`'s own constant, kept as the default here too — that file's cases
       assert this literal id in a download `href` and a `DELETE` path without overriding it,
       so a different default here would be a second batch id quietly disagreeing with the
       first. */
    batch: 'b-2026-08-30-01',
    name: 'TCGplayer_ShippingExport_20260830.csv',
    expires_in: 1800,
    shipments: rows.length,
    rows,
    lane_counts: {
      envelope: count('envelope'),
      parcel: count('parcel'),
      unjudged: count('unjudged'),
    },
    reason_counts: {
      value_at_threshold: rows.filter((one) => one.reason === 'value_at_threshold').length,
      non_card_signal: rows.filter((one) => one.reason === 'non_card_signal').length,
      cards_only: rows.filter((one) => one.reason === 'cards_only').length,
      no_weight_data: rows.filter((one) => one.reason === 'no_weight_data').length,
      no_value_data: rows.filter((one) => one.reason === 'no_value_data').length,
      sub_single_weight: rows.filter((one) => one.reason === 'sub_single_weight').length,
    },
    parcel_count: count('parcel'),
    file: { name: 'pirateship-import.csv', bytes: 2048 },
    stamps: null,
  }
  return { ...base, ...over }
}

/** Rows in all three lanes — envelope, parcel, unjudged — with a certain, an inferred and an
 *  abstained reason among them, so `#/shipping`'s populated state draws every lane it can. */
export function threeLaneBatch(): ShippingBatch {
  return batchOf([
    shippingRow({
      order: 'A2FFC195-0000F4-006AC',
      lane: 'envelope',
      reason: 'cards_only',
      certain: true,
      value: '4.20',
      weight_per_item_oz: '0.1800',
      item_count: 3,
    }),
    shippingRow({
      order: 'B31A0C7D-0001A2-00311',
      lane: 'parcel',
      reason: 'non_card_signal',
      certain: false,
      value: '12.40',
      weight_per_item_oz: '2.5000',
      item_count: 1,
    }),
    shippingRow({
      order: 'C99E4410-0002B8-004F0',
      lane: 'unjudged',
      reason: 'no_weight_data',
      certain: false,
      value: '18.00',
      weight_per_item_oz: null,
      item_count: 2,
    }),
  ])
}

/** A real `File` for the drop zone, the way `shipping.spec.ts:readExport` builds one — a CSV
 *  body with no meaning of its own, since the route that would parse it is stubbed. */
export const SHIPPING_EXPORT_CSV = 'Order #,FirstName\nA2FFC195-0000F4-006AC,Ada\n'

/** Stub the shipping upload route with a three-lane batch. Registering the stub alone does not
 *  populate the screen — `#/shipping` fetches nothing on mount (`shipping.spec.ts`'s own
 *  header), so the caller must still hand the screen a file through the drop zone, the way
 *  `readExport` does, before counting words. */
export async function seedPopulatedShipping(page: Page): Promise<void> {
  await page.route(/\/shipping\/batches$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(threeLaneBatch()),
    }),
  )
}

/* ---------------------------------------------------------------------------- the codes */

/** One code, in the shape `GET /codes` answers with. No existing spec seeds this route
 *  richly — `#/codes` has no dedicated spec yet — so this is a fresh fixture rather than an
 *  extraction, built off `types.ts:CodeEntry`'s own field list. */
export function codeEntry(over: Partial<CodeEntry> = {}): CodeEntry {
  const base: CodeEntry = {
    code: 'ME01-AB12-CD34-EF56',
    state: 'held',
    product: 'booster',
    product_display: 'Booster pack',
    premium: false,
    set_hint: 'ME01',
    box: 12,
    index: 1,
    photo: 'photos/12/1.jpg',
    source: 'scan',
    scanned_at: '2026-09-10T12:00:00+00:00',
    state_at: '2026-09-10T12:00:00+00:00',
    order_id: null,
    buyer: null,
    delivered_at: null,
    dead_reason: null,
    well_formed: true,
    duplicate_positions: [],
  }
  return { ...base, ...over }
}

/** A handful of codes across both lanes, so `#/codes` draws its tier table and lane counts
 *  instead of the zero-code empty state. */
export function severalCodes(): CodeEntry[] {
  return [
    codeEntry({ code: 'ME01-AB12-CD34-EF56', product: 'booster', product_display: 'Booster pack', premium: false }),
    codeEntry({
      code: 'ME01-1234-5678-90AB',
      box: 12,
      index: 2,
      photo: 'photos/12/2.jpg',
      product: 'etb',
      product_display: 'Elite Trainer Box',
      premium: true,
    }),
    codeEntry({
      code: 'ME01-9988-7766-5544',
      box: 12,
      index: 3,
      photo: 'photos/12/3.jpg',
      state: 'delivered',
      order_id: 'A2FFC195-0000F4-006AC',
      buyer: 'Ada Lovelace',
      delivered_at: '2026-09-11T09:00:00+00:00',
    }),
  ]
}

/** The whole `GET /codes` ledger, tallied from the entries rather than restated beside them. */
export function codeLedgerOf(entries: CodeEntry[]): CodeLedger {
  const byProduct = new Map<string, { product: string; display: string; premium: boolean; count: number }>()
  for (const one of entries) {
    if (one.product === null) continue
    const existing = byProduct.get(one.product)
    if (existing) existing.count += 1
    else
      byProduct.set(one.product, {
        product: one.product,
        display: one.product_display ?? one.product,
        premium: one.premium,
        count: 1,
      })
  }
  const lanes = { bulk: 0, premium: 0, unclaimed: 0 }
  for (const one of entries) {
    if (one.product === null) lanes.unclaimed += 1
    else if (one.premium) lanes.premium += 1
    else lanes.bulk += 1
  }
  const counts: Record<string, number> = {}
  for (const one of entries) counts[one.state] = (counts[one.state] ?? 0) + 1
  return {
    counts,
    total: entries.length,
    lanes,
    by_product: [...byProduct.values()].map((row) => ({ ...row, lane: row.premium ? 'premium' : 'bulk' })),
    duplicates: entries.filter((one) => one.duplicate_positions.length > 0),
    entries,
    products: [
      { key: 'booster', display: 'Booster pack', premium: false, redeem_limit: 400 },
      { key: 'etb', display: 'Elite Trainer Box', premium: true, redeem_limit: 4 },
      { key: 'other', display: 'Other / unsure', premium: false, redeem_limit: 4 },
    ],
  }
}

/** Stub `GET /codes` and `GET /codes/lots` with a populated ledger, so `#/codes` draws its
 *  tier table and lane chips instead of the zero-code empty state. */
export async function seedPopulatedCodes(page: Page): Promise<void> {
  const entries = severalCodes()
  await page.route(/\/codes$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(codeLedgerOf(entries)),
    }),
  )
  await page.route(/\/codes\/lots$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ lots: [] }) }),
  )
}

/* ----------------------------------------------------------------------- the graveyard */

/** One departed card, in the shape `GET /graveyard` answers with. No existing spec seeds this
 *  route — `#/graveyard` has no dedicated spec yet — so this is a fresh fixture off
 *  `types.ts:DepartedCard`'s own field list. */
export function departedCard(over: Partial<DepartedCard> = {}): DepartedCard {
  const base: DepartedCard = {
    left_at: '2026-09-10T15:00:00+00:00',
    how: 'sold',
    box: 2,
    index: 3,
    box_name: 'SV commons',
    name: 'Eiscue',
    number: '112',
    game: 'pokemon',
    set_hint: 'ME01',
    sku: '8937371',
    condition: 'Near Mint',
    retire_reason: null,
    moved_to: null,
    order: 'A2FFC195-0000F4-006AC',
    run: '2026-08-24-box9-01',
    captured_at: '2026-08-22T12:34:00+00:00',
    photo_sha256: 'a1b2c3',
    buried: false,
    buried_at: null,
  }
  return { ...base, ...over }
}

/** A few departed rows across the three doors D83 names — sold, retired, moved — plus one
 *  buried row from a deleted box (D134), so `#/graveyard` draws its merged list instead of
 *  "nothing has left this store yet". */
export function severalDeparted(): DepartedCard[] {
  return [
    departedCard(),
    departedCard({
      left_at: '2026-09-08T11:00:00+00:00',
      how: 'retired',
      box: 5,
      index: 4,
      box_name: null,
      name: 'Corviknight',
      number: '198',
      sku: null,
      retire_reason: 'miscut',
      order: null,
      run: null,
      photo_sha256: 'd4e5f6',
    }),
    departedCard({
      left_at: '2026-09-05T09:00:00+00:00',
      how: 'moved',
      box: 9,
      index: 2,
      box_name: null,
      name: 'Thievul',
      number: '090',
      sku: null,
      moved_to: 'Box 12',
      order: null,
      run: null,
      photo_sha256: 'g7h8i9',
    }),
    departedCard({
      left_at: '2026-08-29T08:00:00+00:00',
      how: 'sold',
      box: 1,
      index: 12,
      box_name: null,
      name: 'Volcanion',
      number: '025',
      sku: '9191210',
      order: 'B31A0C7D-0001A2-00311',
      run: '2026-08-22-box1-03',
      photo_sha256: null,
      buried: true,
      buried_at: '2026-09-01T00:00:00+00:00',
    }),
  ]
}

/** Stub `GET /graveyard` with a populated list. */
export async function seedPopulatedGraveyard(page: Page): Promise<void> {
  await page.route(/\/graveyard$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ departed: severalDeparted() }),
    }),
  )
}

/* ------------------------------------------------------------------------- the roster */

/** The five routes `shell.ts:stubStore` leaves empty-ish, each mapped to the seed that
 *  populates it — `copy-budget.spec.ts`'s own use, kept here rather than in that file.
 *
 *  DELIBERATELY NOT IN A `*.spec.ts` FILE. `scripts/docs-audit.py`'s `route rosters` row
 *  reconciles a hand-typed list of THREE OR MORE route hashes found in a spec against
 *  `App.tsx`'s `all`/`hotkey` rosters, because that is the shape that goes silently stale —
 *  a sweep that is missing a route walks the routes it has and nothing goes red. This map is
 *  a different thing: it is not a sweep roster (every route is still discovered at run time
 *  off `routesFromNav`), it is which five of those discovered routes get a second, richer
 *  seed on top of the small store everything else reads. Keeping it in this module, which the
 *  check does not scan, says that plainly rather than asking the check to special-case a
 *  literal that is not the failure it exists for. */
export const POPULATED_ROUTE_SEEDS: Record<string, (page: Page) => Promise<void>> = {
  '#/runs': seedPopulatedRuns,
  '#/orders': seedPopulatedOrders,
  '#/shipping': seedPopulatedShipping,
  '#/codes': seedPopulatedCodes,
  '#/graveyard': seedPopulatedGraveyard,
}
