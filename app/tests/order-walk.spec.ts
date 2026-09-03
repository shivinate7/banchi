import { test, expect, type Page } from '@playwright/test'

import type {
  FillLine,
  OrderRow,
  OrdersPayload,
  PickRow,
  Place,
  ResolvedLine,
  ResolvedOrder,
} from '../src/types'
import { settleFonts } from './fontsReady'

/* AN ORDER DRIVING THE BOX WALK, ASSERTED WHERE NOTHING ELSE CAN SEE IT.
 *
 * `docs/specs/order-pipeline.md` §3 T6, and `CLAUDE.md`'s hard rule is why this file exists at
 * all: "A ROUTE IS NOT A FEATURE. Nothing is built until it is reachable from a screen."
 * `POST /orders/fill` shipped with T7 coverage and a green `make harness`; nothing on the commit
 * path can tell whether a person can press it. `make design-check` runs this, and it is the only
 * check in this repo that opens a browser over `#/inventory`.
 *
 * THE MODE ADDS NO ROUTE, WHICH IS THE FIRST THING TO KNOW ABOUT IT. `#/inventory?order=<key>`
 * and `#/inventory?orders=open` are the same screen with a parameter — `currentPath()` strips the
 * query — so nothing in `App.tsx`'s ROUTES table moves and no count in the prose changes. What
 * the parameter buys is D49's argument for `#/pricing?run=` verbatim: one source of truth, no
 * second `sessionStorage` key with its own clearing rules, and a reload that lands on the first
 * REMAINING stop.
 *
 * WHAT EACH CASE IS FOR is written above it, because this file's subject is a set of rules that
 * would otherwise live only in comments:
 *
 *   THE WALK WRITES NOTHING PER CARD. `Mark sold` is not offered on any row while an order
 *   drives — the plain sale writes card state and not the ledger, so a card sold under a walk
 *   leaves its line owed forever. Case 3 asserts the absence and case 5 asserts that the one
 *   press sends one `POST /orders/fill` and zero `/sold`. That is the owner's own ruling against
 *   their own failure at the drawer: "did i even mark the previous card sold?"
 *
 *   THE BANNER IS ONE ROW AND NEVER CHANGES HEIGHT. D28, applied to the strip above a list
 *   somebody is arrowing through. Case 2 measures `.browse-body`'s top across a step, which is
 *   the assertion the whole layout was designed around.
 *
 *   A COPY IS A COPY WHEREVER IT SITS. The owner's ruling of 2026-09-02 — "You're giving boxes
 *   too much independence" — said when told the swap would be fenced to the box under the
 *   photograph. D7 already says why there is no fence: every unsold copy is equally sellable.
 *   Case 7 crosses a box on purpose; a fence would fail it.
 *
 *   THE EXIT NEVER MOVES INTO THE PRESS'S RECTANGLE. Case 6 measures `Stop walking` across the
 *   fill. `.fulfillment-step` paid for this rule one screen over.
 *
 * NO REAL REQUEST IS EVER MADE. Every route is intercepted and every write is RECORDED rather
 * than performed — this suite runs against whatever server is listening on this checkout's port,
 * which in the main tree is the owner's real capture server over their real inventory.
 */

/* Hash form, verbatim, for the reason `inventory.spec.ts` records: a path-style '/inventory' is
 * served index.html by Vite, mounts the app with an empty hash and renders the capture screen —
 * a passing navigation to the wrong view. */
const VIEW = 'main.inventory'
const PLAIN_ROUTE = '/#/inventory'

/** A 1x1 SVG, so the photograph resolves without a fixture file on disk. */
const PHOTO_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="63" height="88"><rect width="63" height="88" fill="#ccc"/></svg>'

/** Every request the screen made, in order — reads included, because two of the cases below are
 *  about a re-read happening rather than about what it answered. */
type Wire = { method: string; path: string; body: unknown }

/* ------------------------------------------------------------------ the store this walk is over
 *
 * TWO BOXES, FOUR COPIES OF ONE SKU ACROSS BOTH, AND ONE COPY OF A SECOND. The shape is chosen so
 * that every mark the copies panel can draw has a row and the swap has somewhere to cross to:
 *
 *   2/1        A CARD NO ORDER WANTS, and it is the first row of the first box — so it is where
 *              the PLAIN walk plants its selection. Every landing assertion below would be
 *              vacuous without it: with the first stop at 2/1 the walk lands on the card the
 *              screen was going to select anyway, and a mode that drove nothing would pass.
 *   2/2, 2/3   SKU A, the resolver's picks for the order being walked
 *   2/4        SKU A, already recorded against that order and still on hand — the `pulled` mark
 *   7/40       SKU A in ANOTHER BOX, spoken for by a second open order — refused to the swap
 *   7/41       SKU A in that box and claimed by nothing — the copy the picker takes, in one
 *              press from the list and without the walk moving to it first (D93)
 *   7/3        SKU B, the walk's second stop, which is what makes the arrows cross a box
 */

const SOURCE = 'TCGplayer'
const ORDER_N = 'N7A21B03-0004C1-00901'
/* NO `D<n>` SUBSTRING IN EITHER NUMBER: `make docs-audit`'s `repo map` row scans a file for
 *  decision citations, and an order number carrying one would make this spec claim to be
 *  governed by an entry it never mentions. */
const ORDER_M = 'M3C88E17-0009B2-00742'
/** `store/orders.py:order_key` casefolds BOTH halves — the record keeps `source` and `number`
 *  verbatim beside it and only the key is folded. A fixture that sent an unfolded key would be
 *  testing a string the server cannot produce, and `doUndo` folds before comparing. */
const KEY_N = `${SOURCE}:${ORDER_N}`.toLowerCase()
const KEY_M = `${SOURCE}:${ORDER_M}`.toLowerCase()

const SKU_A = '8937370'
const SKU_B = '8937374'
/** The SKU no order in this fixture asks for. Its one copy is the plain walk's landing. */
const SKU_C = '8937371'

type Cards = Record<string, ReturnType<typeof card>>

/** One card in the shape `GET /inventory` answers with, decorations included — `label`,
 *  `section`, `card` and `place` are what `do_inventory` adds from `pipeline/join.py:Position`.
 *  The screen renders them and computes none of them, so a fixture that omitted them would be
 *  testing the gap panel rather than the walk.
 *
 *  NO DEPARTED BRANCH HERE, unlike `inventory.spec.ts`'s builder: every card in this walk is on
 *  hand, because a sold copy never reaches `Action`'s walk branch at all. */
function card(input: {
  box: number
  index: number
  name: string
  sku: string
  section: number
  sectionStart: number
  sectionEnd: number
  boxName: string
  boxTotal: number
}) {
  const slot = input.index - input.sectionStart + 1
  const label = `Box ${input.box} · Section ${input.section} · Card ${slot}`
  const place = {
    located: true,
    label,
    box: input.box,
    index: input.index,
    slot: input.index,
    section: input.section,
    card: slot,
    box_name: input.boxName,
    section_start: input.sectionStart,
    section_end: input.sectionEnd,
    box_total: input.boxTotal,
    box_closed: false,
    fraction: (input.index - 1) / input.boxTotal,
    neighbors: null,
    section_gaps: 0,
  }
  return {
    box: input.box,
    index: input.index,
    label,
    section: input.section,
    card: slot,
    place,
    photo: `photos/${input.box}/${input.index}.jpg`,
    photo_sha256: null,
    photo_reclaimed_at: null,
    set_hint: 'ME01',
    metadata_finish: 'normal',
    game: 'pokemon',
    rarity_claim: null,
    note: null,
    captured_at: '2026-08-22T12:34:00+00:00',
    /* THE AIM, AND THE ONE IDENTITY THAT SURVIVES A RENUMBER (D58). Every assertion about a fill
       body is an assertion about these strings arriving unmangled. */
    capture_id: `cap-${input.box}-${input.index}`,
    name: input.name,
    number: '090',
    printed_total: '132',
    number_display: '090/132',
    confidence: null,
    sku: input.sku,
    condition: 'Near Mint',
    state: 'identified',
    state_at: '2026-08-22T12:34:00+00:00',
    retire_reason: null,
    run: null,
  }
}

const CARDS: Cards = {
  '2/1': card({ box: 2, index: 1, name: 'Eiscue', sku: SKU_C, section: 1, sectionStart: 1, sectionEnd: 4, boxName: 'ME01 commons', boxTotal: 4 }),
  '2/2': card({ box: 2, index: 2, name: 'Thievul', sku: SKU_A, section: 1, sectionStart: 1, sectionEnd: 4, boxName: 'ME01 commons', boxTotal: 4 }),
  '2/3': card({ box: 2, index: 3, name: 'Thievul', sku: SKU_A, section: 1, sectionStart: 1, sectionEnd: 4, boxName: 'ME01 commons', boxTotal: 4 }),
  '2/4': card({ box: 2, index: 4, name: 'Thievul', sku: SKU_A, section: 1, sectionStart: 1, sectionEnd: 4, boxName: 'ME01 commons', boxTotal: 4 }),
  '7/3': card({ box: 7, index: 3, name: 'Pyroar', sku: SKU_B, section: 1, sectionStart: 1, sectionEnd: 41, boxName: 'RB Epics', boxTotal: 41 }),
  '7/40': card({ box: 7, index: 40, name: 'Thievul', sku: SKU_A, section: 1, sectionStart: 1, sectionEnd: 40, boxName: 'RB Epics', boxTotal: 41 }),
  '7/41': card({ box: 7, index: 41, name: 'Thievul', sku: SKU_A, section: 1, sectionStart: 1, sectionEnd: 41, boxName: 'RB Epics', boxTotal: 41 }),
}

const BOXES = {
  boxes: [
    {
      box: 2,
      name: 'ME01 commons',
      sections: [1],
      state: 'open',
      capacity: null,
      fill: 4,
      next_index: 5,
      cards: 4,
      on_hand: 4,
      sold: 0,
      retired: 0,
      listed: 0,
      sections_detail: [{ section: 1, start: 1, end: 4, count: 4 }],
    },
    {
      box: 7,
      name: 'RB Epics',
      sections: [1],
      state: 'open',
      capacity: null,
      fill: 41,
      next_index: 42,
      cards: 3,
      on_hand: 3,
      sold: 0,
      retired: 0,
      listed: 0,
      sections_detail: [{ section: 1, start: 1, end: 41, count: 3 }],
    },
  ],
}

const LISTED: Record<string, { pushed: number; staged: number; live: number }> = {
  [SKU_A]: { pushed: 0, staged: 0, live: 0 },
  [SKU_B]: { pushed: 0, staged: 0, live: 0 },
  [SKU_C]: { pushed: 0, staged: 0, live: 0 },
}

/** The two doors out of inventory — `master.TERMINAL_STATES`. */
const GONE = ['sold', 'retired']

/** The groups `GET /search` answers with. Grouped by SKU and WHOLE — every copy of a matched
 *  SKU, because `do_search` renders a group by `positions_for_sku`, and the copies panel's whole
 *  subject here is copies in boxes the query never named. */
function searchAnswer(query: string, cards: Cards) {
  const asked = query.trim().toLowerCase()
  const skus = [
    ...new Set(
      Object.values(cards)
        .filter((held) =>
          [held.sku, held.name, held.set_hint].some(
            (field) => typeof field === 'string' && field.toLowerCase() === asked,
          ),
        )
        .map((held) => held.sku),
    ),
  ]
  return {
    query,
    groups: skus.map((sku) => {
      const copies = Object.entries(cards)
        .filter(([, held]) => held.sku === sku)
        .map(([key, held]) => ({
          key,
          state: held.state,
          state_at: held.state_at,
          has_photo: true,
          /* THE AIM, ON EVERY COPY (D93). `GET /search` carries it since the panel became the
             picker; a fixture that omitted it would draw a screen where nothing can be taken and
             pass every assertion about the marks. */
          capture_id: held.capture_id,
          place: held.place,
        }))
      const on_hand = copies.filter((copy) => !GONE.includes(copy.state)).length
      return {
        sku,
        names: [...new Set(Object.values(cards).filter((row) => row.sku === sku).map((row) => row.name))],
        number: '090',
        printed_total: '132',
        set_hint: 'ME01',
        condition: 'Near Mint',
        listed: LISTED[sku] ?? { pushed: 0, staged: 0, live: 0 },
        on_hand,
        cap: 4,
        listable: Math.min(4, on_hand),
        copies,
      }
    }),
  }
}

const GAMES = {
  default: 'pokemon',
  games: [
    {
      key: 'pokemon',
      display: 'Pokémon',
      product_line: 'Pokemon',
      rarities: ['Common', 'Uncommon', 'Rare'],
      finishes: ['normal', 'holo', 'reverse_holo'],
      condition_by_finish: { normal: 'Near Mint' },
      finish_by_rarity: { Common: ['normal'] },
      located: true,
      join_key: 'number_over_printed_total',
      prompt: 'pokemon',
      crop_bands: ['title', 'number'],
      card_aspect: 0.716,
      unverified: false,
      catalogued: true,
    },
  ],
}

/* ------------------------------------------------------------------------- the orders payload */

/** The position block for one store key, taken off the card fixture rather than written out
 *  again — a pick whose `place` disagreed with the walk's own row would be a store contradicting
 *  itself, which is the shape of a bug rather than a fixture to build. */
function placeAt(key: string): Place {
  const held = CARDS[key]
  if (held === undefined) throw new Error(`no fixture card at ${key}`)
  return held.place as Place
}

/** One copy the resolver offered. `capture_id` is the identity everything aims by. */
function pick(key: string, over: Partial<PickRow> = {}): PickRow {
  const held = CARDS[key]
  if (held === undefined) throw new Error(`no fixture card at ${key}`)
  return {
    box: held.box,
    index: held.index,
    capture_id: held.capture_id,
    source: 'card',
    run: null,
    card_name: held.name,
    card_number: held.number,
    condition: 'Near Mint',
    state: held.state,
    held_by: null,
    place: placeAt(key),
    ...over,
  }
}

function wireLine(sku: string, quantity: number, name: string) {
  return {
    sku,
    quantity,
    name,
    number: '090',
    printing: 'Normal',
    condition: 'Near Mint',
    rarity: 'Common',
    unit_price: '1.24',
    kind: 'single',
  }
}

/** One resolved line. `wanted` is the buyer's number and `owed` is the LEDGER'S — commit 7be1b3b
 *  made the resolver ask for what is outstanding rather than for the whole quantity, and a
 *  fixture that set them equal on a partly-filled line could not tell the two apart. */
function resolvedLine(input: {
  orderKey: string
  order: string
  sku: string
  name: string
  wanted: number
  owed: number
  picks: PickRow[]
}): ResolvedLine {
  return {
    order: input.order,
    order_key: input.orderKey,
    sku: input.sku,
    reason: input.picks.length >= input.owed ? 'resolved' : 'short',
    wanted: input.wanted,
    owed: input.owed,
    fulfilled: input.wanted - input.owed,
    outstanding: input.owed,
    on_hand: input.picks.length,
    sold: 0,
    retired: 0,
    pooled: 0,
    line: wireLine(input.sku, input.wanted, input.name),
    picks: input.picks,
  }
}

/** The whole payload, with the counts derived from the lines rather than restated beside them —
 *  a fixture whose tally disagrees with its own list can make a broken breakdown look right. */
function payloadOf(orders: OrderRow[], resolved: ResolvedOrder[]): OrdersPayload {
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

/** ORDER N: three of SKU A with ONE ALREADY RECORDED AND STILL ON HAND, and one of SKU B.
 *
 *  The recorded copy is the whole reason `2/3` is in the fixture. `progress.pulled` is joined at
 *  read time off the capture id and stored nowhere (D36), and it is the only way the copies panel
 *  can say which slot a card recorded against an order came out of. */
function orderN(open: boolean): OrderRow {
  return {
    key: KEY_N,
    source: SOURCE,
    number: ORDER_N,
    placed_at: '2026-09-01T10:00:00+00:00',
    status: 'Ready to ship',
    first_seen: '2026-09-01T11:00:00+00:00',
    changed_at: null,
    wanted: 4,
    recorded: open ? 1 : 4,
    open,
    lines: [wireLine(SKU_A, 3, 'Thievul'), wireLine(SKU_B, 1, 'Pyroar')],
    progress: [
      {
        sku: SKU_A,
        wanted: 3,
        recorded: open ? 1 : 3,
        outstanding: open ? 2 : 0,
        over: 0,
        copies: ['cap-2-4'],
        pulled: [{ capture_id: 'cap-2-4', box: 2, index: 4 }],
        at: '2026-09-01T12:00:00+00:00',
      },
      {
        sku: SKU_B,
        wanted: 1,
        recorded: open ? 0 : 1,
        outstanding: open ? 1 : 0,
        over: 0,
        copies: [],
        pulled: [],
        at: null,
      },
    ],
  }
}

/** ORDER M: one of SKU A, and the only copy the resolver can offer it is in the OTHER box. */
function orderM(): OrderRow {
  return {
    key: KEY_M,
    source: SOURCE,
    number: ORDER_M,
    placed_at: '2026-09-01T10:30:00+00:00',
    status: 'Ready to ship',
    first_seen: '2026-09-01T11:00:00+00:00',
    changed_at: null,
    wanted: 1,
    recorded: 0,
    open: true,
    lines: [wireLine(SKU_A, 1, 'Thievul')],
    progress: [
      { sku: SKU_A, wanted: 1, recorded: 0, outstanding: 1, over: 0, copies: [], pulled: [], at: null },
    ],
  }
}

function resolvedN(): ResolvedOrder {
  return {
    key: KEY_N,
    number: ORDER_N,
    complete: false,
    outstanding: 3,
    lines: [
      resolvedLine({
        orderKey: KEY_N,
        order: ORDER_N,
        sku: SKU_A,
        name: 'Thievul',
        wanted: 3,
        owed: 2,
        picks: [pick('2/2'), pick('2/3')],
      }),
      resolvedLine({
        orderKey: KEY_N,
        order: ORDER_N,
        sku: SKU_B,
        name: 'Pyroar',
        wanted: 1,
        owed: 1,
        picks: [pick('7/3')],
      }),
    ],
  }
}

function resolvedM(): ResolvedOrder {
  return {
    key: KEY_M,
    number: ORDER_M,
    complete: false,
    outstanding: 1,
    lines: [
      resolvedLine({
        orderKey: KEY_M,
        order: ORDER_M,
        sku: SKU_A,
        name: 'Thievul',
        wanted: 1,
        owed: 1,
        picks: [pick('7/40')],
      }),
    ],
  }
}

/** Both orders open — what every case starts from. */
function bothOpen(): OrdersPayload {
  return payloadOf([orderN(true), orderM()], [resolvedN(), resolvedM()])
}

/** After the envelope: N is still IN the ledger and no longer open, so it is absent from
 *  `resolution.orders` (which is `Ledger.unfulfilled()`) and present in `orders`. That pair is
 *  what the banner's filled branch reads, and a payload that dropped the row outright would draw
 *  the fall-through note instead. */
function nFilled(): OrdersPayload {
  return payloadOf([orderN(false), orderM()], [resolvedM()])
}

/* ---------------------------------------------------------------------------- the walk's world */

/** `GET /orders` as a THUNK, because the advance and the fill both depend on the second read
 *  differing from the first — and a module-level mutable would leak between the tests Playwright
 *  runs in one worker. */
function world(first: OrdersPayload = bothOpen()) {
  let held = first
  return {
    read: () => held,
    set: (next: OrdersPayload) => {
      held = next
    },
  }
}

type World = ReturnType<typeof world>

/** What `POST /orders/fill` answers, called per request so one case can refuse. */
type FillStub = (body: {
  undo?: boolean
  source: string
  number: string
  lines: FillLine[]
}) => { status: number; body: unknown }

/** The ordinary envelope and its reversal.
 *
 *  `places` ARE THE PRE-WRITE PLACES, one per target across the lines IN REQUEST ORDER (D58: a
 *  sale moves the box's occupancy, so a post-write label already reads departed). Derived from
 *  the request rather than written out, so the receipt can never be asserted against a list the
 *  press did not actually send. */
const FILL: FillStub = (body) => ({
  status: 200,
  body: {
    undone: body.undo === true,
    order_key: `${body.source}:${body.number}`.toLowerCase(),
    complete: body.undo !== true,
    lines: body.lines.map((line) => ({
      sku: line.sku,
      newly: line.targets.length,
      recorded: body.undo === true ? 0 : line.targets.length,
      outstanding: 0,
    })),
    places: body.lines.flatMap((line) => line.targets.map((target) => placeAt(`${target.box}/${target.index}`))),
    sales: [],
  },
})

/**
 * Land on the walk with every route the screen can reach intercepted, and return the log of what
 * it sent.
 *
 * THE WRITES ARE REGISTERED FIRST, which is `inventory.spec.ts`'s hard ordering rule: the read
 * regexes are looser and a `/inventory` matcher would swallow `/inventory/2/1/sold`. `/sold` and
 * `/orders/pull` are stubbed here even though no case presses them — their ABSENCE from the wire
 * is the assertion in case 5, and a route that escaped to a real server would make that absence
 * meaningless.
 */
async function open(
  page: Page,
  options: { hash?: string; orders?: World; cards?: Cards; fill?: FillStub } = {},
): Promise<Wire[]> {
  const wire: Wire[] = []
  const cards = options.cards ?? CARDS
  const orders = options.orders ?? world()
  const fill = options.fill ?? FILL

  const record = (method: string, url: string, body: unknown) =>
    wire.push({ method, path: new URL(url).pathname, body })

  await page.route(/\/orders\/fill$/, async (route) => {
    const request = route.request()
    const body = request.postDataJSON() as Parameters<FillStub>[0]
    record(request.method(), request.url(), body)
    const answer = fill(body)
    await route.fulfill({
      status: answer.status,
      contentType: 'application/json',
      body: JSON.stringify(answer.body),
    })
  })

  await page.route(/\/orders\/pull$/, async (route) => {
    const request = route.request()
    record(request.method(), request.url(), request.postDataJSON())
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ undone: false, order_key: '', sku: '', newly: 0, recorded: 0, outstanding: 0, places: [], sales: [] }),
    })
  })

  await page.route(/\/inventory\/\d+\/\d+\/sold$/, async (route) => {
    const request = route.request()
    record(request.method(), request.url(), request.postDataJSON())
    const path = new URL(request.url()).pathname.split('/')
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        position: `${path[2]}/${path[3]}`,
        box: Number(path[2]),
        index: Number(path[3]),
        undone: false,
        state: 'sold',
        previous_state: 'identified',
        restores_to: 'identified',
        listing: null,
        card: null,
      }),
    })
  })

  await page.route(/\/inventory\/\d+\/\d+\/retire$/, async (route) => {
    const request = route.request()
    record(request.method(), request.url(), request.postDataJSON())
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
  })

  await page.route(/\/orders$/, async (route) => {
    record(route.request().method(), route.request().url(), null)
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(orders.read()),
    })
  })

  await page.route(/\/search\?/, async (route) => {
    const asked = new URL(route.request().url()).searchParams.get('q') ?? ''
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(searchAnswer(asked, cards)),
    })
  })

  await page.route(/\/games$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(GAMES) })
  })

  await page.route(/\/boxes$/, async (route) => {
    record(route.request().method(), route.request().url(), null)
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(BOXES) })
  })

  await page.route(/\/inventory$/, async (route) => {
    record(route.request().method(), route.request().url(), null)
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 2, cards, boxes: {}, listings: {} }),
    })
  })

  await page.route(/\/photo\/\d+\/\d+/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'image/svg+xml', body: PHOTO_SVG })
  })

  /* The two reads the walk makes on mount that have nothing to do with orders. Stubbed for the
     reason every read here is: an unstubbed one is a request to whatever is listening on this
     checkout's port, which in the main tree is the owner's real capture server. */
  await page.route(/\/pipeline\/runs$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{"runs": []}' })
  })

  await page.route(/\/queues$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '{"review": [], "parked": []}',
    })
  })

  await page.goto(options.hash ?? PLAIN_ROUTE)
  await settleFonts(page)
  await expect(page.locator(VIEW)).toBeVisible()
  return wire
}

/** The walk's entry link, composed the one way `orderWalk.ts:walkHash` composes it. The colon in
 *  `source:number` is why the key is encoded, and asserting against a hand-written `%3A` here is
 *  what would catch an encoding that silently stopped happening. */
function orderRoute(key: string): string {
  return `/#/inventory?order=${encodeURIComponent(key)}`
}
const WAVE_ROUTE = '/#/inventory?orders=open'

/** One copy row, found by the position label's own accessible name. `hasText` would work too and
 *  is weaker: `Card 3` sits in both boxes of this fixture. */
function copyRow(page: Page, label: string) {
  return page
    .locator('.card-locations-owner .card-locations-row')
    .filter({ has: page.locator(`[aria-label="${label}"]`) })
}

/** The picker's two presses, matched on the ACCESSIBLE NAME AND EXACTLY. Playwright's default
 *  name match is a case-insensitive substring, and `Take the copy at X` is a substring of
 *  `Don’t take the copy at X` — so a loose match here would find the wrong control and the two
 *  cases below would pass with the presses swapped. The apostrophe is the typographic one, which
 *  is what the label renders. */
function takeButton(page: Page, label: string) {
  return copyRow(page, label).getByRole('button', { name: `Take the copy at ${label}`, exact: true })
}

function dropButton(page: Page, label: string) {
  return copyRow(page, label).getByRole('button', { name: `Don’t take the copy at ${label}`, exact: true })
}

const AT_2_1 = 'Box 2 · Section 1 · Card 1'
const AT_2_2 = 'Box 2 · Section 1 · Card 2'
const AT_2_3 = 'Box 2 · Section 1 · Card 3'
const AT_2_4 = 'Box 2 · Section 1 · Card 4'
const AT_7_3 = 'Box 7 · Section 1 · Card 3'
const AT_7_40 = 'Box 7 · Section 1 · Card 40'
const AT_7_41 = 'Box 7 · Section 1 · Card 41'

/** The banner's two figures, in the order the row draws them: `stop k of n` then `take k of n`. */
function counts(page: Page) {
  return page.locator('.inventory-walk-row .inventory-walk-count')
}

/** Which box the strip is pointing at. */
function currentBox(page: Page) {
  return page.locator('.browse-boxcell[aria-current="true"]')
}

/** Wait for the walk to be standing on one card — the landing effect drives `goTo`, which opens
 *  the section, sets the shelf and marks the row, so this is the sync point every case needs. */
async function standingOn(page: Page, label: string) {
  await expect(page.locator('.browse-row[aria-current="true"]')).toBeVisible()
  await expect(copyRow(page, label)).toHaveAttribute('aria-current', 'true')
}

/* -------------------------------------------------------------------------------------- 1
 *
 * THE DULLEST CASE IN THE FILE AND THE ONE THAT PAYS FOR IT: does the parameter reach the screen
 * at all. `currentPath()` strips the query, so a router that compared the whole hash would render
 * `NoSuchView` — the route table right, the screen missing, and nothing else in this repo able to
 * tell. Everything after this assumes the landing works. */

test('an order in the URL lands the walk on the first copy it needs', async ({ page }) => {
  const wire = await open(page, { hash: orderRoute(KEY_N) })

  await standingOn(page, AT_2_2)

  /* AND IT SKIPPED THE CARD THE SCREEN WOULD OTHERWISE HAVE SELECTED. `2/1` is the first row of
     the first box and no order wants it, so this is what says the QUEUE drove the landing rather
     than the walk's own default doing it for free. Every landing assertion in this file rests on
     the fixture keeping that card there. */
  await expect(page.locator('.browse-row').first()).toContainText('Eiscue')
  await expect(page.locator('.browse-row').first()).not.toHaveAttribute('aria-current', 'true')

  /* THE PHOTOGRAPH FOLLOWS THE LANDING, which is the whole errand — "without me searching for
     each card". The `?card=` stamp is D52's, and it is the occupant's identity rather than a
     cache-buster, so the assertion is on the path and not on the whole string. */
  await expect(page.locator('.browse-photo')).toHaveAttribute('src', /\/photo\/2\/2(\?|$)/)

  await expect(page.locator('.inventory-walk')).toBeVisible()
  await expect(page.locator('.inventory-walk-order')).toHaveText(ORDER_N)
  /* The whole key on the title, which is the one place two marketplaces could ever be told
     apart — the row itself has no width for a source. */
  await expect(page.locator('.inventory-walk-order')).toHaveAttribute('title', KEY_N)
  await expect(counts(page).nth(0)).toHaveText('1 of 2')
  await expect(page.locator('.inventory-walk-name')).toHaveText('Thievul')

  /* THE CHIP SAYS WHAT THE ARROWS DO, and while an order drives that is not the box. A chip
     still reading `step one card` would be a true sentence about a key that no longer does it. */
  await expect(page.locator('.browse-keys')).toContainText('step one stop')
  await expect(page.locator('.browse-keys')).not.toContainText('step one card')

  /* THE READ HAPPENED, rather than a count of it: React re-runs an effect on a dev remount, so a
     literal here would be asserting the harness rather than the screen. What matters is that the
     mode fetches at all — a walk drawn off `GET /inventory` alone would have no ledger in it. */
  expect(wire.filter((call) => call.path === '/orders').length).toBeGreaterThan(0)
})

/* -------------------------------------------------------------------------------------- 2
 *
 * D28, AND THE ASSERTION THE WHOLE LAYOUT WAS DESIGNED AROUND. The banner is one row with
 * `flex-wrap: nowrap` and every child `flex: none` but the ellipsising name; a second row would
 * push the list under a finger already travelling toward it, at the pace somebody arrows a
 * drawer. Both tops are read the same way and the fonts are settled in `open`, so what moves is
 * the banner or nothing. */

test('the banner is one row and stepping it does not move the list', async ({ page }) => {
  await open(page, { hash: orderRoute(KEY_N) })
  await standingOn(page, AT_2_2)

  const body = page.locator('.browse-body')
  const before = await body.boundingBox()
  const rowBefore = await page.locator('.inventory-walk-row').boundingBox()

  await page.locator('.browse-list').focus()
  await page.keyboard.press('ArrowRight')
  await expect(counts(page).nth(0)).toHaveText('2 of 2')

  const after = await body.boundingBox()
  const rowAfter = await page.locator('.inventory-walk-row').boundingBox()

  expect(after?.y).toBe(before?.y)
  expect(rowAfter?.height).toBe(rowBefore?.height)
})

/* -------------------------------------------------------------------------------------- 3
 *
 * TWO TONES, AND `Mark sold` GONE FROM EVERY ROW (T6's second determination). The plain sale
 * writes card state and not the ledger, so a card sold here while an order drives leaves its line
 * owed forever — the envelope is the one write and the plain sale is one `Stop walking` away.
 * `Retire` stays, because a damaged copy is retired whoever it was promised to.
 *
 * The ink/muted split is the instruction rather than a ranking: ink where the mark tells the hand
 * what to do with THIS card, muted where it reports somebody else's fact. */

test('every copy carries whose it is, and no row offers the plain sale', async ({ page }) => {
  await open(page, { hash: orderRoute(KEY_N) })
  await standingOn(page, AT_2_2)

  await expect(page.locator('.card-locations-owner .card-locations-row')).toHaveCount(5)

  /* The two the envelope will record — ink, because they are what the hand is for. */
  await expect(copyRow(page, AT_2_2).locator('.inventory-copy-mark')).toHaveText('taking')
  await expect(copyRow(page, AT_2_2).locator('.inventory-copy-mark')).toHaveClass(/inventory-copy-mark-take/)
  await expect(copyRow(page, AT_2_3).locator('.inventory-copy-mark')).toHaveText('taking')

  /* Another open order's pick, outside this queue — muted, and not the take tone. */
  await expect(copyRow(page, AT_7_40).locator('.inventory-copy-mark')).toHaveText(`for order ${ORDER_M}`)
  await expect(copyRow(page, AT_7_40).locator('.inventory-copy-mark')).not.toHaveClass(/inventory-copy-mark-take/)

  /* THE SLOT A RECORDED CARD CAME OUT OF. A pulled copy is sold, so the resolver offers it in
     no pick and `progress.pulled` — joined at read time off the capture id, stored nowhere
     (D36) — is what marks this row. */
  await expect(copyRow(page, AT_2_4).locator('.inventory-copy-mark')).toHaveText(`pulled for order ${ORDER_N}`)

  /* AND A COPY NOBODY HAS CLAIMED CARRIES NO MARK AT ALL — an empty slot rather than a word
     saying nothing, because five rows of prose is what makes the ink ones unreadable. What it
     carries instead is the reason its take is missing: the line already has the two it is owed
     (D93), and the count is the remedy stated rather than a control that has gone quiet. */
  await expect(copyRow(page, AT_7_41).locator('.inventory-copy-mark')).toHaveCount(0)
  await expect(copyRow(page, AT_7_41).locator('.inventory-copy-note')).toHaveText('2 of 2 taken')
  await expect(counts(page).nth(1)).toHaveText('2 of 2')

  /* ASSERTED AS AN ABSENCE ACROSS THE WHOLE SCREEN, not row by row: a control that is merely not
     visible is one CSS rule from being back. */
  await expect(page.getByRole('button', { name: 'Mark sold' })).toHaveCount(0)
  await expect(page.locator('.card-locations-owner').getByRole('button', { name: 'Retire' })).toHaveCount(5)
})

/* -------------------------------------------------------------------------------------- 4
 *
 * THE ARROWS STEP THE QUEUE, NOT THE BOX — one table, one window listener, and only who answers
 * the key changes. The second stop is in ANOTHER BOX on purpose: a queue that stepped the box
 * would move one card and never cross a drawer, which is exactly the walk the owner asked not to
 * have to do by hand. Both ends stop; wrapping loses your place without saying so. */

test('the arrows step the queue across boxes, and both ends stop', async ({ page }) => {
  await open(page, { hash: orderRoute(KEY_N) })
  await standingOn(page, AT_2_2)
  await expect(currentBox(page)).toHaveAttribute('aria-label', 'Box 2')

  await page.locator('.browse-list').focus()
  await page.keyboard.press('ArrowRight')

  await expect(counts(page).nth(0)).toHaveText('2 of 2')
  await expect(page.locator('.inventory-walk-name')).toHaveText('Pyroar')
  await expect(currentBox(page)).toHaveAttribute('aria-label', 'Box 7')
  await standingOn(page, AT_7_3)

  /* THE FAR END STOPS. A further Right has nowhere to go, so the counter does not move — and the
     end is answered by moving focus to the envelope rather than by silence. */
  await page.keyboard.press('ArrowRight')
  await expect(counts(page).nth(0)).toHaveText('2 of 2')
  await expect(page.locator('.inventory-walk-fill')).toBeFocused()

  await page.keyboard.press('ArrowLeft')
  await expect(counts(page).nth(0)).toHaveText('1 of 2')
  await standingOn(page, AT_2_2)

  // And the near end stops too.
  await page.keyboard.press('ArrowLeft')
  await expect(counts(page).nth(0)).toHaveText('1 of 2')
})

/* -------------------------------------------------------------------------------------- 5
 *
 * THE ENVELOPE IS THE WHOLE WRITE, AND IT IS THE OWNER'S RULING ABOUT THEIR OWN FAILURE: "i'd
 * rather it be i can't move on from the envelope until I click a button saying the envelope is
 * filled all items mark sold". One press, every line of the order, one transaction — and every
 * target aimed by its own capture id, which is the check the server refuses on
 * (`capture_id_mismatch`) and what makes the press safe across a mid-box delete or a re-shoot.
 *
 * THE ABSENCES ARE THE POINT. Zero `/sold` and zero `/orders/pull`: a walk that also wrote card
 * state per copy, or that fell back to the per-line pull, would pass every visible assertion here
 * and be the defect the mode exists to prevent. */

test('one press records the whole envelope, and nothing else is written', async ({ page }) => {
  const w = world()
  const wire = await open(page, { hash: orderRoute(KEY_N), orders: w })
  await standingOn(page, AT_2_2)

  const readsBefore = {
    orders: wire.filter((call) => call.path === '/orders').length,
    inventory: wire.filter((call) => call.path === '/inventory').length,
  }

  /* The label carries the count, so the glance and the press cannot disagree: two copies of SKU A
     and one of SKU B against three the ledger still owes. */
  const fill = page.locator('.inventory-walk-fill')
  await expect(fill).toHaveText('Envelope filled — mark 3 of 3 sold')

  w.set(nFilled())
  await fill.click()

  await expect(page.locator('.inventory-receipt')).toContainText(
    `Envelope ${ORDER_N} filled — 3 copies marked sold.`,
  )

  const fills = wire.filter((call) => call.path === '/orders/fill')
  expect(fills.length).toBe(1)
  expect(fills[0]?.method).toBe('POST')
  expect(fills[0]?.body).toEqual({
    source: SOURCE,
    number: ORDER_N,
    lines: [
      {
        sku: SKU_A,
        targets: [
          { box: 2, index: 2, capture_id: 'cap-2-2' },
          { box: 2, index: 3, capture_id: 'cap-2-3' },
        ],
      },
      { sku: SKU_B, targets: [{ box: 7, index: 3, capture_id: 'cap-7-3' }] },
    ],
  })

  expect(wire.filter((call) => call.path.endsWith('/sold')).length).toBe(0)
  expect(wire.filter((call) => call.path === '/orders/pull').length).toBe(0)

  /* ONE PLACE LINE PER COPY, off the answer's PRE-write places (D58), so what was recorded can be
     checked off against what is in the hand. A receipt built from `sales[i].card.place.label`
     would read `departed` three times, which is the case `orders.spec.ts` records paying for. */
  const places = page.locator('.inventory-receipt .inventory-receipt-place')
  await expect(places).toHaveCount(3)
  await expect(places.nth(0)).toHaveText(AT_2_2)
  await expect(places.nth(1)).toHaveText(AT_2_3)
  await expect(places.nth(2)).toHaveText(AT_7_3)

  /* BOTH READS HAPPEN. A fill changes every other line competing for the same SKU, so nothing is
     patched locally — the queue re-derives from a fresh `GET /orders` and the walk re-reads the
     store it draws. */
  expect(wire.filter((call) => call.path === '/orders').length).toBeGreaterThan(readsBefore.orders)
  expect(wire.filter((call) => call.path === '/inventory').length).toBeGreaterThan(readsBefore.inventory)
})

/* -------------------------------------------------------------------------------------- 6
 *
 * THE EXIT NEVER MOVES INTO THE PRESS'S RECTANGLE. `.fulfillment-step` paid for this rule one
 * screen over — a control appearing under a finger already travelling toward the last one — so
 * `Stop walking` is always the last child of the right-packed end cluster and `Walk the next
 * order` is drawn on the LEFT. The envelope's rectangle is left empty rather than refilled. */

test('a filled order says so, and the way out has not moved', async ({ page }) => {
  const w = world()
  await open(page, { hash: orderRoute(KEY_N), orders: w })
  await standingOn(page, AT_2_2)

  const exit = page.getByRole('button', { name: 'Stop walking' })
  const exitBefore = await exit.boundingBox()
  const fillRect = await page.locator('.inventory-walk-fill').boundingBox()

  w.set(nFilled())
  await page.locator('.inventory-walk-fill').click()

  await expect(page.locator('.inventory-walk-said')).toHaveText(`Order ${ORDER_N} is filled.`)
  const next = page.getByRole('link', { name: 'Walk the next order' })
  await expect(next).toBeVisible()
  await expect(next).toHaveAttribute('href', `#/inventory?order=${encodeURIComponent(KEY_M)}`)

  /* TO THE PIXEL AND NOT TO THE BIT: a layout that re-runs can land a fraction of a device pixel
     away without anything having moved. What this refuses is a control SLIDING into the vacated
     rectangle, which is tens of pixels. */
  const exitAfter = await exit.boundingBox()
  expect(exitAfter?.x).toBeCloseTo(exitBefore?.x ?? 0, 1)
  expect(exitAfter?.width).toBeCloseTo(exitBefore?.width ?? 0, 1)

  /* NOTHING PRESSABLE IN THE VACATED RECTANGLE. The next order's link is on the far side of the
     row, which is the whole of the ruling. */
  await expect(page.locator('.inventory-walk-fill')).toHaveCount(0)
  const nextRect = await next.boundingBox()
  expect((nextRect?.x ?? 0) + (nextRect?.width ?? 0)).toBeLessThan(fillRect?.x ?? 0)
})

/* -------------------------------------------------------------------------------------- 7
 *
 * THE PANEL IS THE PICKER, AND THE COPY IS TAKEN WITHOUT WALKING TO IT (D93). The owner's
 * complaint is what this case is the answer to: "when I have an order of 2 cards and I have
 * inventory for 3, I basically should be able to pick which two I sell, instead currently it's
 * like predetermined". Every copy on the wire carries its own `capture_id` now, so the take is a
 * press on the row rather than a correction made after arriving at the drawer.
 *
 * A FULL LINE REFUSES THE TAKE (the owner's ruling, 2026-09-02). At `2 of 2` the third copy
 * draws the count where its control would be, and dropping one is what makes room — nothing
 * leaves the envelope on a press aimed at something else.
 *
 * AND THE WALK DOES NOT FOLLOW A TAKE. The list is appended to, so what the walk is standing on
 * is still the first copy the envelope records; a screen that jumped to box 7 because a row in
 * box 7 was ticked would move under the finger doing the ticking. Dropping the copy it is
 * standing on DOES move it, to the next copy the envelope is taking, which is the errand.
 *
 * WHAT IS DELIBERATELY REFUSED, in the same case so the two rules cannot drift apart: a copy
 * another open order's resolver has already been allocated. That is not a box fence — `7/40` and
 * `7/41` sit in the same drawer and only one of them is offered — it is `resolve_all`'s
 * allocation over the whole open set, which exists so two envelopes cannot name one card. */

test('a copy in another box is taken off the list, and the take does not move the walk', async ({ page }) => {
  const wire = await open(page, { hash: orderRoute(KEY_N) })
  await standingOn(page, AT_2_2)

  /* THE LINE IS FULL, SO THE FREE COPY CARRIES THE COUNT AND NO CONTROL. `7/40` in the same
     drawer carries a different reason: it is somebody else's. */
  await expect(takeButton(page, AT_7_41)).toHaveCount(0)
  await expect(copyRow(page, AT_7_41).locator('.inventory-copy-note')).toHaveText('2 of 2 taken')
  await expect(copyRow(page, AT_7_40).locator('.inventory-copy-note')).toHaveCount(0)

  /* MAKE ROOM. The walk moves to the copy that is now first in the envelope — one move, not two,
     which is why the take appends rather than inserting at the front. */
  await dropButton(page, AT_2_2).click()
  await standingOn(page, AT_2_3)
  await expect(copyRow(page, AT_2_2).locator('.inventory-copy-mark')).toHaveText('not taking')

  /* AND NOW THE COPY IN THE OTHER BOX IS ONE PRESS AWAY, from a row the walk has never been to.
     `7/40` is still refused with the drawer unchanged, which is what says the rule is about the
     allocation and not about the box. */
  await expect(takeButton(page, AT_7_40)).toHaveCount(0)
  await expect(copyRow(page, AT_7_40).locator('.inventory-copy-mark')).toHaveText(`for order ${ORDER_M}`)

  await takeButton(page, AT_7_41).click()

  await expect(copyRow(page, AT_7_41).locator('.inventory-copy-mark')).toHaveText('taking')
  await expect(copyRow(page, AT_7_41).locator('.inventory-copy-mark')).toHaveClass(/inventory-copy-mark-take/)
  await expect(counts(page).nth(1)).toHaveText('2 of 2')

  /* THE WALK STAYED WHERE IT WAS. The copy it is standing on is still the first the envelope
     records, and the box strip never left box 2. */
  await standingOn(page, AT_2_3)
  await expect(currentBox(page)).toHaveAttribute('aria-label', 'Box 2')

  await page.locator('.inventory-walk-fill').click()

  const sent = wire.find((call) => call.path === '/orders/fill')?.body as { lines: FillLine[] }
  const lineA = sent.lines.find((line) => line.sku === SKU_A)
  expect(lineA?.targets).toEqual([
    { box: 2, index: 3, capture_id: 'cap-2-3' },
    { box: 7, index: 41, capture_id: 'cap-7-41' },
  ])
})

/* -------------------------------------------------------------------------------------- 8
 *
 * TWO SHORTFALLS AND THEY ARE DIFFERENT FACTS. `short` is copies the resolver never found — the
 * ledger's problem — and `not taken` is copies it DID find that the operator has not put in the
 * envelope, which is the shelf's. One number covering both would send a person to the wrong
 * place. The line stays owed and the envelope reports `k of n`, and the walk moves to the next
 * copy of the same card on its own, which is the whole errand. */

test('a copy dropped from the envelope is counted, and the walk moves to the next one', async ({ page }) => {
  await open(page, { hash: orderRoute(KEY_N) })
  await standingOn(page, AT_2_2)

  await dropButton(page, AT_2_2).click()

  await expect(copyRow(page, AT_2_2).locator('.inventory-copy-mark')).toHaveText('not taking')
  await expect(takeButton(page, AT_2_2)).toBeVisible()
  await standingOn(page, AT_2_3)

  /* `take` FALLS AND THE OWED FIGURE DOES NOT, which is the pair the button and the banner are
     both drawn from — both off `targetsOf`, the same function the press sends, so neither can
     disagree with the other. Three owed across the two lines, two still in hand. */
  await expect(counts(page).nth(1)).toHaveText('1 of 2')
  await expect(page.locator('.inventory-walk-row')).toContainText('1 not taken')
  await expect(page.locator('.inventory-walk-fill')).toHaveText('Envelope filled — mark 2 of 3 sold')

  /* AND IT IS REVERSIBLE WITHOUT A SERVER. The take and its reversal share a rectangle, so the
     press that undoes an overshoot is the one that made it. */
  await takeButton(page, AT_2_2).click()
  await expect(counts(page).nth(1)).toHaveText('2 of 2')
  await expect(page.locator('.inventory-walk-row')).not.toContainText('not taken')
})

/* -------------------------------------------------------------------------------------- 9
 *
 * THE UNDO IS THE WHOLE ENVELOPE, AND IT NAMES ITS LINES. Unlike `undoPull`, the screen holds
 * what it sent and sends it back: the server refuses `fill_line_mismatch` if the ledger holds a
 * copy under a different line than the one named. And it is still not a sale — a reversal that
 * went through `/sold` would put the cards back without touching the ledger, which is the same
 * disagreement the mode exists to prevent, running backward. */

test('the receipt reverses the whole envelope, and never through the sale', async ({ page }) => {
  const w = world()
  const wire = await open(page, { hash: orderRoute(KEY_N), orders: w })
  await standingOn(page, AT_2_2)

  w.set(nFilled())
  await page.locator('.inventory-walk-fill').click()
  await expect(page.locator('.inventory-receipt')).toBeVisible()

  w.set(bothOpen())
  await page
    .locator('.inventory-receipt')
    .getByRole('button', { name: `Undo envelope ${ORDER_N} — 3 copies back on hand` })
    .click()

  await expect(page.locator('.inventory-receipt')).toHaveCount(0)

  const fills = wire.filter((call) => call.path === '/orders/fill')
  expect(fills.length).toBe(2)
  const sent = fills[1]?.body as { undo?: boolean; source: string; number: string; lines: FillLine[] }
  expect(sent.undo).toBe(true)
  expect(sent.source).toBe(SOURCE)
  expect(sent.number).toBe(ORDER_N)
  expect(sent.lines).toEqual((fills[0]?.body as { lines: FillLine[] }).lines)

  expect(wire.filter((call) => call.path.endsWith('/sold')).length).toBe(0)
})

/* ------------------------------------------------------------------------------------- 10
 *
 * WAVE MODE — "all the cards pulled either in one go across all orders". The stops are the same
 * line-stops sorted by where their landing sits, so the pass through the drawers is one
 * direction; because a landing is re-derived per read, this does not turn the queue into a list
 * of positions. Each order keeps its own envelope, because the press is still per order: a single
 * button over three orders would record copies into an envelope that is not in the hand. */

test('the wave walks every open order in box order, one envelope each', async ({ page }) => {
  await open(page, { hash: WAVE_ROUTE })
  await standingOn(page, AT_2_2)

  /* Three stops across two orders, ordered `(box, index)`: 2/1, then 7/3, then 7/40 — which
     interleaves the orders rather than finishing one before starting the next. */
  await expect(counts(page).nth(0)).toHaveText('1 of 3')
  await expect(page.locator('.inventory-walk-order').first()).toHaveText(ORDER_N)

  await page.locator('.browse-list').focus()
  await page.keyboard.press('ArrowRight')
  await standingOn(page, AT_7_3)
  await expect(counts(page).nth(0)).toHaveText('2 of 3')
  await expect(page.locator('.inventory-walk-order').first()).toHaveText(ORDER_N)

  await page.keyboard.press('ArrowRight')
  await standingOn(page, AT_7_40)
  await expect(counts(page).nth(0)).toHaveText('3 of 3')
  await expect(page.locator('.inventory-walk-order').first()).toHaveText(ORDER_M)

  const envelopes = page.locator('.inventory-walk-envelope')
  await expect(envelopes).toHaveCount(2)
  await expect(envelopes.nth(0)).toContainText(ORDER_N)
  await expect(envelopes.nth(1)).toContainText(ORDER_M)
  await expect(page.locator('.inventory-walk-envelope .inventory-walk-fill')).toHaveCount(2)

  /* The current order carries the rail, so the row the press belongs to is the one the walk is
     standing in. */
  await expect(envelopes.nth(1)).toHaveAttribute('aria-current', 'true')
})

/* ------------------------------------------------------------------------------------- 11
 *
 * THE FALL-THROUGH IS NOT A BANNER. A link naming an order the ledger does not hold has no order
 * to describe, so it draws the screen's own note — the same panel a refusal uses — and the walk
 * is the PLAIN walk beneath it. That last clause is the assertion that matters: a mode with no
 * order driving it must not go on suppressing the write the plain screen exists for, or a stale
 * bookmark silently takes `Mark sold` away from every card in the store. */

test('a key the ledger does not hold falls through to the plain walk', async ({ page }) => {
  await open(page, { hash: orderRoute('tcgplayer:not-an-order') })

  await expect(page.locator('.browse-banner .inventory-note')).toBeVisible()
  await expect(page.locator('.browse-banner .inventory-machine')).toHaveText('order_not_walkable')
  await expect(page.locator('.inventory-walk')).toHaveCount(0)

  /* AND THE SCREEN IS THE PLAIN SCREEN AGAIN. Nothing is driving, so nothing is owed, so there is
     no reason to withhold the sale. */
  await expect(page.locator('.card-locations-owner')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Mark sold' }).first()).toBeVisible()

  /* THE PLAIN WALK'S OWN LANDING, stated here because every other case in this file depends on it
     being a DIFFERENT card from the first stop: the walk plants its selection on the first row of
     the first box, which is `2/1` and which no order wants. If this ever became one of the
     resolver's picks, the landing assertions above would pass with the mode driving nothing. */
  await expect(copyRow(page, AT_2_1)).toHaveAttribute('aria-current', 'true')
})

/* ------------------------------------------------------------------------------------- 12
 *
 * THE WAY OUT IS THE URL, which is what makes it a way out at all: the parameter is the only
 * state the mode has, so dropping it drops the queue, the cursor, the marks and the two
 * corrections in one move — and the Back button works. */

test('stopping the walk gives the screen back', async ({ page }) => {
  await open(page, { hash: orderRoute(KEY_N) })
  await standingOn(page, AT_2_2)

  await page.getByRole('button', { name: 'Stop walking' }).click()

  await expect.poll(() => page.evaluate(() => window.location.hash)).toBe('#/inventory')
  await expect(page.locator('.inventory-walk')).toHaveCount(0)
  await expect(page.locator('.inventory-copy-mark')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Mark sold' }).first()).toBeVisible()
})

/* ------------------------------------------------------------------------------------- 13
 *
 * A REFUSAL WRITES NOTHING AND LEAVES NO RECEIPT. `POST /orders/fill` aggregates every entry's
 * refusal to `fill_entry_refused` and writes none of them, so a screen that drew a receipt over
 * it would be telling the operator that cards in their hand are recorded when they are not — the
 * exact error the envelope exists to remove. Both reads happen on the way out too, because every
 * refusal here says the screen is stale. */

test('a refused envelope draws the code and records nothing', async ({ page }) => {
  const wire = await open(page, {
    hash: orderRoute(KEY_N),
    fill: () => ({
      status: 409,
      body: {
        error: {
          code: 'fill_entry_refused',
          message: 'One entry of this envelope was refused, so none of it was written.',
        },
      },
    }),
  })
  await standingOn(page, AT_2_2)

  const before = {
    orders: wire.filter((call) => call.path === '/orders').length,
    inventory: wire.filter((call) => call.path === '/inventory').length,
  }

  await page.locator('.inventory-walk-fill').click()

  await expect(page.locator('.inventory-detail .inventory-note .inventory-machine')).toHaveText(
    'fill_entry_refused',
  )
  await expect(page.locator('.inventory-receipt')).toHaveCount(0)

  expect(wire.filter((call) => call.path === '/orders').length).toBeGreaterThan(before.orders)
  expect(wire.filter((call) => call.path === '/inventory').length).toBeGreaterThan(before.inventory)
})
