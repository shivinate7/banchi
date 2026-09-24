import { test, expect, type Locator, type Page } from '@playwright/test'
import { sealEveryTest } from './shell'
import { settleFonts } from './fontsReady'

/* docs/DESIGN.md's Fulfillment constraints table, every row of it, as assertions.
 *
 * That table opens with the reason this file exists rather than a paragraph of prose: "The
 * agent cannot see its own output, so these are Playwright assertions, not prose." It is the
 * only instrument this project has on the view D5 calls the entire product for a retired,
 * non-technical user — and the requirement underneath the table, "if a flow needs explaining
 * twice, redesign the flow", has no instrument at all except him using it. So the numbers are
 * what can be checked, and they are checked here without exception.
 *
 * `app/tests/pull-confirm.spec.ts` covers three of these rows against step 6's one component.
 * This file covers all nine against the view, and follows that spec's one methodological
 * rule: EVERY RATIO IS COMPUTED FROM THE RENDERED COLOURS, never compared against a number
 * published in docs/DESIGN.md. A test that reads its expected value out of the thing it is
 * checking checks nothing, and a token edited in tokens.css without being re-argued in the
 * doc has to break something. This is that something.
 *
 * EVERY SCREEN, NOT THE TWO THAT WERE EASY TO REACH. The walks below used to run against the
 * list and the card panel, which left the loading screen, the failure screen, the empty list,
 * the missing-photo screen, the receipts and the refusal lines unmeasured — and the copy on a
 * screen nobody renders is exactly the copy nobody proofreads. `battery` is the whole table
 * applied at once, and a screen that does not call it needs an argument made out loud.
 *
 * The floors below are quoted from the table and are the only literals here that come from a
 * document rather than from the page.
 */

const BODY_FLOOR = 20 // "Body text  font-size >= 20px on every text node in the view"
const PLACE_FLOOR = 32 // "Position label  font-size >= 32px, tabular figures"
const PHOTO_FLOOR = 320 // "Card photo in pull modal  >= 320px on the short edge"
const TARGET_FLOOR = 44 // "Tap targets  >= 44 x 44 px"
const GAP_FLOOR = 12 // "...  >= 12px apart"
const CONTRAST_FLOOR = 7 // "Contrast  >= 7:1 for body text (WCAG AAA)"
const UNDO_FLOOR_MS = 10_000 // "Undo  present on every mark-sold, >= 10s window"

/* THE ROUTE THIS VIEW IS MOUNTED AT, and the one thing in this file a compiler cannot check.
 *
 * `App.tsx` owns the ROUTES table and is not this session's to edit. Hash form, verbatim,
 * for the reason the pull-confirm spec records at its own constant: a path-style
 * '/fulfillment' is served index.html by Vite, mounts the app with an empty hash and renders
 * the capture screen — a passing navigation to the wrong view. The `openList` helper below
 * asserts the view is actually on screen before any test measures anything, so a route that
 * has not been registered fails there and loudly rather than as nine confusing measurements
 * of nothing.
 */
const VIEW_ROUTE = '/#/fulfillment'
const VIEW = 'main.fulfillment'

/* One card the fixture serves, in the shape `GET /inventory` answers with — the server's own
 * field names, because types.ts keeps them and the first thing anyone debugging a run does is
 * hold the screen against `inventory.json`.
 *
 * `label`, `section` and `card` are the decoration `server/capture_server.py:do_inventory`
 * adds to every row it can, from `pipeline/join.py:Position`. They are optional there and
 * optional here, which is what lets the last fixture row below exercise the undecorated case.
 */
type FixtureCard = {
  box: number
  index: number
  state: string
  name: string | null
  label?: string
  photo: string | null

  /** A pooled card — `pipeline/games.py`'s `located: false`, the ruling that a code card
   *  is a count with no box, section or card position. The server sends its row with NO
   *  flat label and a `place` block carrying `located: false` and the game's display name
   *  (`server/capture_server.py:_Places`), and `pooledPlace` below is that shape. */
  pooled?: true
}

/** The place block the server builds for a pooled card, field for field. The key stays —
 *  it names the photo and sidecar — and everything location-shaped answers null. */
function pooledPlace(card: FixtureCard) {
  return {
    located: false,
    label: null,
    box: card.box,
    index: card.index,
    section: null,
    card: null,
    box_name: null,
    section_start: null,
    section_end: null,
    box_total: 0,
    box_closed: false,
    fraction: null,
    game: 'pokemon_code',
    game_display: 'Pokémon code cards',
  }
}

/* Three cards for sale in two boxes, one card that is not for sale, and one for sale that the
 * server could not give a position to.
 *
 * The names are ordinary on purpose. The banned-word walk below reads every string this view
 * renders, and a fixture card called "Sync Ball" would fail it for a reason that has nothing
 * to do with the copy under test.
 *
 * Box-walk order is 1/3, then 3/7, then 3/26 — deliberately not the order they are written
 * in, so the sort is measured rather than inherited from the fixture.
 */
const CARDS: Record<string, FixtureCard> = {
  '3/26': {
    box: 3,
    index: 26,
    state: 'identified',
    name: 'Pidgeot ex',
    label: 'Box 3 · Section 2 · Card 1',
    photo: '/captures/3/026.jpg',
  },
  '3/7': {
    box: 3,
    index: 7,
    state: 'identified',
    name: 'Charizard ex',
    label: 'Box 3 · Section 1 · Card 7',
    photo: '/captures/3/007.jpg',
  },
  '1/3': {
    box: 1,
    index: 3,
    state: 'identified',
    name: 'Iono',
    label: 'Box 1 · Section 1 · Card 3',
    photo: '/captures/1/003.jpg',
  },
  /* TWO COPIES OF ONE CARD, IN TWO BOXES, and they are the whole reason the search path can be
   * measured at all. D7 keeps every copy as its own position with its own photo, and the
   * owner's ruling is that the screen must offer him all of them so he walks to whichever slot
   * is nearest — which cannot be asserted against a fixture where every name is unique.
   *
   * The store has real ones: Thievul, Eiscue and Pyroar each have two copies in it after Gate
   * B. This is that shape, at the size a fixture can carry.
   *
   * ONE OF THEM IS `captured`, deliberately. D7's amendment made `captured` a perfectly
   * pullable card — it is on the shelf and nothing physically distinguishes it from the copy
   * beside it — and a fixture where every sellable copy is `identified` would pass while the
   * screen quietly filtered on a state it is not allowed to filter on. */
  '4/2': {
    box: 4,
    index: 2,
    state: 'captured',
    name: 'Eiscue',
    label: 'Box 4 · Section 1 · Card 2',
    photo: '/captures/4/002.jpg',
  },
  '2/9': {
    box: 2,
    index: 9,
    state: 'identified',
    name: 'Eiscue',
    label: 'Box 2 · Section 1 · Card 9',
    photo: '/captures/2/009.jpg',
  },
  // ALREADY SOLD, and it must never appear. This row used to be `captured` and carry the
  // comment "captured but never listed — marking it sold would record a sale of something no
  // buyer could have ordered". D7's amendment retired that reasoning rather than this case:
  // copies are fungible, every UNSOLD copy is sellable, and `captured` now means a card that
  // is on the shelf and perfectly pullable. `sold` is what "must not appear" is made of now.
  '2/4': { box: 2, index: 4, state: 'sold', name: null, label: 'Box 2 · Section 1 · Card 4', photo: null },
  // For sale, and undecorated — `do_inventory` leaves a row bare when its box or index will
  // not coerce. It must be counted on screen rather than dropped in silence.
  '9/12': { box: 9, index: 12, state: 'identified', name: 'Great Ball', photo: '/captures/9/012.jpg' },
  /* POOLED, AND IT MUST NEVER APPEAR — the assertion the pooled ruling asks this file for
   * by name ("asserted in app/tests/fulfillment.spec.ts rather than left to prose"). A
   * `pokemon_code` card is a count, not a location: unsold, photographed, searchable on the
   * owner's screens — and never on this view, because there is nothing to walk to. It is
   * deliberately NOT in the unplaced count either: that count is a fault count whose
   * sentence ends "Ask for help", and a pooled card is working as designed. The name is
   * distinctive so a leak anywhere on this view is caught by one string. */
  '5/2': { box: 5, index: 2, state: 'identified', name: 'Trade Token', photo: '/captures/5/002.jpg', pooled: true },
}

/** The state of each card as the stub store holds it right now, keyed the way
 *  `store.master.position_key` keys them. Handed back by `stubServer` so a test can play the
 *  OTHER device — D13 puts two of them on one store with no session between, and every
 *  staleness bug on this screen is that fact arriving while a list is on screen. */
type Store = Record<string, string>

function inventoryBody(states: Store) {
  const rows: Record<string, unknown> = {}
  for (const [key, card] of Object.entries(CARDS)) {
    rows[key] = {
      box: card.box,
      index: card.index,
      photo: card.photo,
      set_hint: null,
      metadata_finish: null,
      captured_at: '2026-08-13T10:00:00+00:00',
      capture_id: null,
      name: card.name,
      number: '006',
      printed_total: '197',
      confidence: 'high',
      sku: '1234567',
      condition: 'Near Mint',
      state: states[key] ?? card.state,
      state_at: '2026-08-13T11:00:00+00:00',
      run: null,
      // A pooled row carries the block and no flat keys; a located row the flat keys; the
      // coerce-failure row neither — the three shapes `do_inventory` actually serves.
      ...(card.pooled === true
        ? { game: 'pokemon_code', place: pooledPlace(card) }
        : card.label === undefined
          ? {}
          : { label: card.label, section: 1, card: card.index }),
    }
  }
  return { version: 1, cards: rows }
}

/* THE STAND-IN PHOTO IS LANDSCAPE, AND THAT IS THE FIXTURE'S WHOLE JOB.
 *
 * It was drawn at 63x88 — the card's own shape, which is exactly the shape the stylesheet
 * gives the element — so `object-fit: cover` had nothing to crop, and the one cropped image in
 * this app was measured with its crop switched off. A rig frame is a landscape video frame
 * with a portrait card inside it, so this is 4:3 and the fit rule does real work: swap `cover`
 * for `contain` and the painted card drops to 270px on its short edge while the element's own
 * box stays 360. The old fixture could not tell those two apart, which made the ">= 320px"
 * row a measurement of a CSS rule rather than of a photograph.
 *
 * SVG rather than a base64 PNG because a PNG has to be handed to `route.fulfill` as a Buffer,
 * and `app/tsconfig.json` declares `"types": ["vite/client"]` with no Node types — so `Buffer`
 * does not exist in this project's type world and adding it would be a dependency and a
 * tsconfig edit for a fixture. A string body needs neither, and this one is legible in the
 * diff besides. */
const PHOTO_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="160" height="120">' +
  '<rect width="160" height="120" fill="#e6e7ea"/>' +
  '<rect x="57" y="4" width="46" height="112" fill="#52555b"/></svg>'

/** Sales the page recorded, in order, so a test can assert what the screen actually sent.
 *
 *  `undo` is the field `server/capture_server.py:do_mark_sold` reads: `{}` records a sale and
 *  `{"undo": true}` reverses one, on the same route in both directions. Recorded off the
 *  request body rather than off the method, because the method is `POST` either way and a
 *  test that read only the method would pass while the screen sold a card twice. */
type Wire = { method: string; url: string; undo: boolean }

/** One answer from the mark-sold route. */
type Sold = { status: number; body: unknown }

/** How the stub answers a mark-sold, given the direction, the position and the store as it
 *  stands. Overridable per test so a refusal is one line rather than an `unroute` dance. */
type SoldAnswer = (undo: boolean, key: string, states: Store) => Sold

/* The default answer is a MODEL of `do_mark_sold` rather than a fixed 200, and the difference
 * matters now that the view re-reads the cards after every sale. A stub that always answered
 * 200 and never moved its own store would hand the re-read a card it had just sold, so the
 * screen would put it straight back on his list — the test would then be measuring a
 * contradiction the real server cannot produce. Both refusals below are the two-device case
 * (D13) and are reached by a test setting a state, not by stubbing a status code. */
const soldModel: SoldAnswer = (undo, key, states) => {
  const was = states[key]
  if (!undo && was === 'sold') {
    return {
      status: 409,
      body: {
        error: {
          code: 'already_sold',
          message: `Box ${key} is already sold. Send {"undo": true} to reverse that sale.`,
        },
      },
    }
  }
  if (undo && was !== 'sold') {
    return {
      status: 409,
      body: {
        error: {
          code: 'not_sold',
          message: `Box ${key} is ${was ?? 'missing'}, not sold, so there is no sale to reverse.`,
        },
      },
    }
  }
  /* `restores_to` is what an undo of THIS call would put back — null on a reversal, because
   * there is then nothing left to reverse.
   *
   * `identified` AND NOT `live`, WHICH IS WHAT THIS LINE SAID. D7's 2026-08-23 amendment took
   * `pushed`, `staged` and `live` off the card and made them quantities against the SKU, so
   * `store/master.py:check_state` refuses all three and `history.jsonl` cannot record one as
   * the state a sale came out of. A fixture answering with a word the store will not accept
   * teaches every test built on it a vocabulary the server no longer speaks. */
  return {
    status: 200,
    body: { position: key, undone: undo, restores_to: undo ? null : 'identified' },
  }
}

/** A refusal in the server's own shape, for the cases no state can produce. */
function refuses(code: string, message: string): Sold {
  return { status: 409, body: { error: { code, message } } }
}

/* `GET /search?q=` AS `do_search` ANSWERS IT: one group per card, every copy of it inside,
 * each copy carrying its own `Place`.
 *
 * MODELLED RATHER THAN CANNED, for the same reason `soldModel` above is. The screen filters
 * the answer against sales it has just made, and a fixed body would let a test pass while the
 * screen re-offered a card the stub's own store says is sold. This reads `states`, so the
 * search and the inventory cannot disagree about a card inside one test.
 *
 * A CARD WITH NO POSITION IS NOT IN A SEARCH RESULT. `do_inventory` leaves a row undecorated
 * when its box or index will not coerce, and a `Place` is exactly what that row does not have
 * — so `9/12` is in the inventory fixture, counted on the list screen, and absent here. That
 * is the server's shape and not a convenience: the whole of what a search result does is say
 * where a card is.
 *
 * Matched on a lower-cased substring of the name, which is `_matches`'s own rule for the name
 * field. The other three things that route searches on — number, SKU and set hint — are the
 * server's business and not this view's; nothing on his screen offers him a way to type one.
 */
function searchAnswer(q: string, states: Store, soldHere = 0) {
  const text = q.trim().toLowerCase()

  const byName = new Map<string, FixtureCard[]>()
  for (const card of Object.values(CARDS)) {
    // A pooled card IS in a search result — the server serves it whole, because the
    // owner's screens search and count it — and the view under test is what must filter
    // it. Only the coerce-failure row (no label, not pooled) is absent server-side.
    if ((card.label === undefined && card.pooled !== true) || card.name === null) continue
    if (!card.name.toLowerCase().includes(text)) continue
    byName.set(card.name, [...(byName.get(card.name) ?? []), card])
  }

  const groups = [...byName.entries()].map(([name, held], at) => {
    const copies = [...held]
      // Box-walk order inside a group as well. Two copies arriving in fixture order would let
      // an assertion about which copy is first pass for the wrong reason.
      .sort((a, b) => a.box - b.box || a.index - b.index)
      .map((card) => {
        const key = `${card.box}/${card.index}`
        return {
          key,
          state: states[key] ?? card.state,
          state_at: '2026-08-13T11:00:00+00:00',
          has_photo: card.photo !== null,
          place:
            card.pooled === true
              ? pooledPlace(card)
              : {
                  located: true,
                  label: card.label,
                  box: card.box,
                  index: card.index,
                  section: 1,
                  card: card.index,
                  box_name: null,
                  section_start: 1,
                  section_end: 25,
                  box_total: 25,
                  box_closed: true,
                  fraction: card.index / 25,
                },
        }
      })

    // D7: on hand is a count of UNSOLD positions, and never `copies.length` — the sold ones
    // ride along so nothing silently drops a card.
    const onHand = copies.filter((copy) => copy.state !== 'sold').length
    return {
      sku: String(1234560 + at),
      names: [name],
      number: '006',
      printed_total: '197',
      set_hint: null,
      condition: 'Near Mint',
      listed: { pushed: 0, staged: 0, live: onHand },
      // D115: the stages and the counter travel apart, the way the wire sends them. Zero here
      // keeps every existing case drawing exactly what it drew; the case at the end of this
      // file overrides it.
      sold_here: soldHere,
      live_as_of: null,
      on_hand: onHand,
      /* D7's `min(cap, on hand)`, mirroring `capture_server.py`. Derived from `onHand` above so
         the fixture cannot promise a denominator its own copy count contradicts. */
      listable: Math.min(4, onHand),
      copies,
    }
  })

  return { query: q, groups }
}

/* How the stubbed server behaves, read at request time so a test can change its mind.
 *
 * MUTABLE RATHER THAN A COUNT OF READS, and that is not a style choice: `main.tsx` mounts
 * under StrictMode, which double-invokes every effect in dev, so the view reads the inventory
 * twice on one mount and discards the first answer through its own `livePage` flag. A stub
 * that refused "the first read" therefore refused the answer nobody was listening to and the
 * screen rendered as though nothing had gone wrong — measured, before this was written. A
 * flag the test flips is indifferent to how many times React asks. */
type Mood = {
  fail?: boolean
  slow?: boolean
  /** Nothing is for sale, which is a screen with its own copy and no controls. */
  empty?: boolean
  /** Every photo 404s, which is the other screen the card panel can be. */
  noPhoto?: boolean
  sold?: SoldAnswer
  /** How many times `GET /inventory` has been answered. The instrument for "the list is read
   *  again", which is the only defence a client has against the other device. */
  reads?: number
  /** `GET /search` refuses. Its own flag rather than `fail`, because the two failures land on
   *  two different parts of one screen: the cards can load while the search does not, and the
   *  list he already has must survive that. */
  searchFail?: boolean
  /** Copies sold HERE since the store's last reading of `live` (D115). The instrument for the
   *  one sentence this view gained: his count is the estimate, so it moves the moment a copy
   *  is pulled, and the sentence is what says why. */
  soldHere?: number
  /** THE LEDGER, WHICH THIS VIEW NOW READS BESIDE THE CARDS. `GET /orders` names what is open;
   *  `resolution` on this fixture is field-for-field what `do_orders` answers, but as of
   *  2026-09-16 it is never what draws a card here (`OrdersPayload.resolution.orders[].lines[]
   *  .picks` is always `[]` on the wire, and `Fulfillment.tsx` never reads it) — `plan`, below,
   *  is the real source, over `POST /orders/walk-plan`. It defaults to a ledger with nothing
   *  open — the world every case below was written in, where the boxes ARE the walk — so a
   *  case that wants an order says so. Stubbed rather than left to fall through: an unrouted
   *  `/orders` reaches the real capture server, and this file would then be measuring the
   *  owner's real open orders. */
  orders?: unknown
  /** THE REAL PICKS, `plan` being `WalkPlan`-shaped over `POST /orders/walk-plan` (D212/D93,
   *  the owner's own ruling — see `Fulfillment.tsx`'s file header). Every open order named in
   *  `orders` above should have a matching take here, or the screen draws an order with
   *  nothing under it, which is the S1 defect this file exists to catch (UX-001). Defaults to
   *  an empty plan, matching `orders` defaulting to none open. */
  plan?: unknown
}

/** THE ONE OPEN ORDER, waiting for the copy the fixture holds at 3/7.
 *
 *  Field for field the shape `do_orders` answers with. `resolution` here is realistic but
 *  UNREAD by the screen (see `Mood.orders`'s own comment); `ONE_OPEN_ORDER_PLAN`, below, is
 *  what the screen actually draws from. */
const ORDER_NUMBER = 'A2FFC195-0000F4-006AC'
const ORDER_SKU = '9191486'
const ORDER_KEY = `TCGplayer:${ORDER_NUMBER}`

const ORDER_LINE = {
  sku: ORDER_SKU,
  quantity: 1,
  name: 'Charizard ex',
  number: '006',
  printing: 'Normal',
  condition: 'Near Mint',
  rarity: 'Rare',
  unit_price: '1.24',
  kind: 'single',
}

const ORDER_BUYER = 'Maria Lopez'

const ONE_OPEN_ORDER = {
  summary: '1 order',
  orders: [
    {
      key: ORDER_KEY,
      source: 'TCGplayer',
      number: ORDER_NUMBER,
      buyer: ORDER_BUYER,
      placed_at: '2026-08-29T10:00:00+00:00',
      status: 'Ready to ship',
      first_seen: '2026-08-30T09:00:00+00:00',
      changed_at: null,
      wanted: 1,
      recorded: 0,
      open: true,
      lines: [ORDER_LINE],
      progress: [
        { sku: ORDER_SKU, wanted: 1, recorded: 0, outstanding: 1, over: 0, copies: [], at: null },
      ],
    },
  ],
  resolution: {
    orders: [
      {
        key: ORDER_KEY,
        number: ORDER_NUMBER,
        complete: false,
        outstanding: 1,
        lines: [
          {
            order: ORDER_NUMBER,
            order_key: ORDER_KEY,
            sku: ORDER_SKU,
            reason: 'resolved',
            wanted: 1,
            fulfilled: 1,
            outstanding: 0,
            on_hand: 1,
            sold: 0,
            retired: 0,
            pooled: 0,
            line: ORDER_LINE,
            // THE REAL SHAPE SINCE 2026-09-16: `GET /orders` answers no picks at all, on
            // ANY server — `do_orders`'s own docstring, `OrdersPayload`'s own comment. A
            // fixture that sent `[ORDER_PICK]` here was exercising a read this screen no
            // longer makes, which is why the old walk-based tests passed against a bug the
            // real server has had for a week: they proved the mock, not the app.
            picks: [],
          },
        ],
      },
    ],
    counts: {
      resolved: 1,
      short: 0,
      no_copies_on_hand: 0,
      sku_unknown: 0,
      sku_unseen: 0,
      not_a_single: 0,
    },
  },
}

/** The same order, plus a second line the boxes cannot fill at all (no picks) — the
 *  `group.elsewhere` count fulfiller.md's finding 5 named as "a dead end". */
const ELSEWHERE_SKU = '9191487'
const ORDER_WITH_ELSEWHERE = {
  ...ONE_OPEN_ORDER,
  orders: [
    {
      ...ONE_OPEN_ORDER.orders[0]!,
      lines: [ORDER_LINE, { ...ORDER_LINE, sku: ELSEWHERE_SKU, quantity: 8 }],
      progress: [
        ...ONE_OPEN_ORDER.orders[0]!.progress,
        { sku: ELSEWHERE_SKU, wanted: 8, recorded: 0, outstanding: 8, over: 0, copies: [], at: null },
      ],
    },
  ],
  resolution: {
    ...ONE_OPEN_ORDER.resolution,
    orders: [
      {
        ...ONE_OPEN_ORDER.resolution.orders[0]!,
        lines: [
          ...ONE_OPEN_ORDER.resolution.orders[0]!.lines,
          {
            order: ORDER_NUMBER,
            order_key: ORDER_KEY,
            sku: ELSEWHERE_SKU,
            reason: 'no_copies_on_hand',
            wanted: 8,
            fulfilled: 0,
            outstanding: 8,
            on_hand: 0,
            sold: 0,
            retired: 0,
            pooled: 0,
            line: { ...ORDER_LINE, sku: ELSEWHERE_SKU, quantity: 8 },
            picks: [],
          },
        ],
      },
    ],
  },
}

/** A ledger with nothing open. Field for field the shape `do_orders` answers with. */
const NO_ORDERS = {
  summary: 'No open orders',
  orders: [],
  resolution: {
    orders: [],
    counts: {
      resolved: 0,
      short: 0,
      no_copies_on_hand: 0,
      sku_unknown: 0,
      sku_unseen: 0,
      not_a_single: 0,
    },
  },
}

/** `POST /orders/walk-plan`'s own empty answer — no keys asked, nothing to plan. The screen
 *  never sends this request with no order open (`Fulfillment.tsx`'s own effect skips the
 *  call), so this is only ever the stub's DEFAULT for a case that sets `orders` without `plan`
 *  and has no order that owes anything, and for `NO_ORDERS`. */
const EMPTY_PLAN = {
  cost: 'sections',
  stops: [],
  shortfall: [],
  counts: { stops: 0, boxes: 0, copies: 0, sections_considered: 0, sections_candidate: 0, exact: true, solve_ms: 0 },
}

/** The real place `ONE_OPEN_ORDER`'s SKU resolves to — the box and index the store holds it
 *  at, the only fixture that carries it now that `GET /orders`'s own `picks` are `[]`. */
const ORDER_COPY_PLACE = {
  label: 'Box 3 · Section 1 · Card 7',
  located: true,
  box: 3,
  index: 7,
  slot: 7,
  section: 1,
  card: 7,
  box_name: null,
  section_start: 1,
  section_end: 25,
  box_total: 25,
  box_closed: true,
  fraction: 0.28,
  neighbors: null,
  section_gaps: 0,
}

/** One `WalkPlanCopy` — `_walk_plan_copy`'s own shape, field for field: `_copy_row` plus
 *  `here`. NO PRESELECTION READS THIS SHAPE AS SPECIAL: `here` says whether the solver would
 *  reach it from the stop it is filed under, never whether it is offered — the screen offers
 *  every copy in the list the same way (D212, D93). */
const ORDER_WALK_COPY = {
  key: '3/7',
  state: 'identified',
  has_photo: true,
  capture_id: 'cap-charizard',
  cid: null,
  place: ORDER_COPY_PLACE,
  here: true,
}

/** One `WalkPlanTake` — the SKU `ONE_OPEN_ORDER` owes, one copy wide, one order owing it. */
const ORDER_TAKE = {
  sku: ORDER_SKU,
  name: 'Charizard ex',
  number_display: '006',
  set: null,
  rarity: null,
  condition: 'Near Mint',
  wanted: 1,
  for: [{ key: ORDER_KEY, number: ORDER_NUMBER, buyer: ORDER_BUYER }],
  copies: [ORDER_WALK_COPY],
  listed: { pushed: 0, staged: 0, live: 0 },
  sold_here: 0,
  live_as_of: null,
}

/** `ONE_OPEN_ORDER`'s own plan — one stop, one take, one copy, fully fillable. */
const ONE_OPEN_ORDER_PLAN = {
  cost: 'sections',
  stops: [
    {
      key: 'box/3/section/1',
      box: 3,
      box_name: null,
      section: 1,
      section_name: null,
      pooled: false,
      game: null,
      game_display: null,
      order: 1,
      span: { start: 1, end: 25 },
      box_total: 25,
      takes: [ORDER_TAKE],
    },
  ],
  shortfall: [],
  counts: { stops: 1, boxes: 1, copies: 1, sections_considered: 1, sections_candidate: 1, exact: true, solve_ms: 1 },
}

/** `ORDER_WITH_ELSEWHERE`'s own plan — the same fillable take, plus a SKU the store holds
 *  none of at all: `on_hand: 0`, so it is `shortfall` and never a stop (`pipeline/walkplan.py:
 *  plan`'s own doc comment — demand is capped at availability before the solve). This is the
 *  shape UX-001's own direction asks for: "if the screen cannot place a copy, it says how
 *  many" — never a card drawn with nothing under it. */
const ORDER_WITH_ELSEWHERE_PLAN = {
  ...ONE_OPEN_ORDER_PLAN,
  shortfall: [
    {
      sku: ELSEWHERE_SKU,
      name: 'Charizard ex',
      wanted: 8,
      on_hand: 0,
      short: 8,
      for: [{ key: ORDER_KEY, number: ORDER_NUMBER, buyer: ORDER_BUYER }],
    },
  ],
}

/** THE OWNER'S OWN CASE, VERBATIM (2026-09-23 ruling): "if an order has 2 of card X but I
 *  have 14 in inventory, I shouldn't just see 2 cards that are preselected — I should be told
 *  I need to pick 2, and here's where all the copies are." One SKU, wanted 2, THREE copies on
 *  hand in three different places — the fixture the ruling itself describes, at a size a test
 *  can hold. */
const MULTI_ORDER_NUMBER = 'M-PICK-2'
const MULTI_ORDER_KEY = `TCGplayer:${MULTI_ORDER_NUMBER}`
const MULTI_SKU = '9199001'

function multiCopy(key: string, box: number, section: number, card: number, sectionEnd: number): {
  key: string
  state: string
  has_photo: boolean
  capture_id: string
  cid: null
  place: Record<string, unknown>
  here: boolean
} {
  return {
    key,
    state: 'identified',
    has_photo: true,
    capture_id: `cap-${key.replace('/', '-')}`,
    cid: null,
    place: {
      label: `Box ${box} · Section ${section} · Card ${card}`,
      located: true,
      box,
      index: card,
      slot: card,
      section,
      card,
      box_name: null,
      section_start: 1,
      section_end: sectionEnd,
      box_total: sectionEnd,
      box_closed: true,
      fraction: 0.4,
      neighbors: null,
      section_gaps: 0,
    },
    here: box === 1,
  }
}

const MULTI_COPIES = [
  multiCopy('1/5', 1, 1, 5, 20),
  multiCopy('2/9', 2, 1, 9, 15),
  multiCopy('4/2', 4, 2, 2, 10),
]

const MULTI_ORDER = {
  summary: '1 order',
  orders: [
    {
      key: MULTI_ORDER_KEY,
      source: 'TCGplayer',
      number: MULTI_ORDER_NUMBER,
      buyer: 'Priya Nair',
      placed_at: '2026-09-20T10:00:00+00:00',
      status: 'Ready to ship',
      first_seen: '2026-09-21T09:00:00+00:00',
      changed_at: null,
      wanted: 2,
      recorded: 0,
      open: true,
      lines: [{ ...ORDER_LINE, sku: MULTI_SKU, quantity: 2, name: 'Promising Future' }],
      progress: [
        { sku: MULTI_SKU, wanted: 2, recorded: 0, outstanding: 2, over: 0, copies: [], at: null },
      ],
    },
  ],
  resolution: { orders: [], counts: { resolved: 0, short: 0, no_copies_on_hand: 0, sku_unknown: 0, sku_unseen: 0, not_a_single: 0 } },
}

const MULTI_PLAN = {
  cost: 'sections',
  stops: [
    {
      key: 'box/1/section/1',
      box: 1,
      box_name: null,
      section: 1,
      section_name: null,
      pooled: false,
      game: null,
      game_display: null,
      order: 1,
      span: { start: 1, end: 20 },
      box_total: 20,
      takes: [
        {
          sku: MULTI_SKU,
          name: 'Promising Future',
          number_display: '115/298',
          set: 'Riftbound',
          rarity: null,
          condition: 'Near Mint',
          wanted: 2,
          for: [{ key: MULTI_ORDER_KEY, number: MULTI_ORDER_NUMBER, buyer: 'Priya Nair' }],
          copies: MULTI_COPIES,
          listed: { pushed: 0, staged: 0, live: 0 },
          sold_here: 0,
          live_as_of: null,
        },
      ],
    },
  ],
  shortfall: [],
  counts: { stops: 1, boxes: 1, copies: 2, sections_considered: 1, sections_candidate: 1, exact: true, solve_ms: 1 },
}

async function stubServer(page: Page, wire: Wire[], mood: Mood = {}): Promise<Store> {
  const states: Store = {}
  for (const [key, card] of Object.entries(CARDS)) {
    // `sold` is what empties the list, not `captured`. Under D7 as amended a captured card is
    // sellable — it is a real card at a real position — so the old spelling of "empty" now
    // fills the screen instead of clearing it.
    states[key] = mood.empty === true ? 'sold' : card.state
  }

  // The sold route first: nothing else may answer it, and a stub that quietly 404s would make
  // every mark-sold test measure the failure path while reading like the happy one.
  await page.route(/\/inventory\/\d+\/\d+\/sold$/, async (route) => {
    const request = route.request()
    const sent: unknown = request.postDataJSON()
    const undo = (sent as { undo?: unknown } | null)?.undo === true
    const found = /\/inventory\/(\d+)\/(\d+)\/sold$/.exec(new URL(request.url()).pathname)
    const key = found === null ? '' : `${found[1] ?? ''}/${found[2] ?? ''}`
    wire.push({ method: request.method(), url: request.url(), undo })

    const answer = (mood.sold ?? soldModel)(undo, key, states)
    // A sale the stub accepted is a sale the next GET /inventory has to show. This is the
    // store the other device would be looking at.
    // Back to `identified`, the state it was sold out of — see `soldModel` for why not `live`.
    if (answer.status < 400 && key !== '') states[key] = undo ? 'identified' : 'sold'
    await route.fulfill({
      status: answer.status,
      contentType: 'application/json',
      body: JSON.stringify(answer.body),
    })
  })

  /* `POST /orders/pull` — a card an owed take names is sold THROUGH the order (`claim`,
     `Fulfillment.tsx`), never through `/inventory/<box>/<index>/sold` above. One target at a
     time is all this screen ever sends (D93: one press per copy), so the stub answers for
     the first and only one, field for field what a real pull returns on success. */
  await page.route(/\/orders\/pull$/, async (route) => {
    const request = route.request()
    const sent = request.postDataJSON() as {
      undo?: unknown
      targets?: { box: number; index: number; capture_id: string }[]
    } | null
    const undo = sent?.undo === true
    const target = sent?.targets?.[0]
    const key = target === undefined ? '' : `${target.box}/${target.index}`
    wire.push({ method: request.method(), url: request.url(), undo })
    if (key !== '') states[key] = undo ? 'identified' : 'sold'
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        undone: undo,
        order_key: ORDER_KEY,
        sku: ORDER_SKU,
        newly: undo ? 0 : 1,
        recorded: undo ? 0 : 1,
        outstanding: undo ? 1 : 0,
        places: target === undefined ? [] : [ORDER_COPY_PLACE],
        sales:
          target === undefined
            ? []
            : [{ position: key, undone: undo, restores_to: undo ? null : 'identified', order_released: null }],
      }),
    })
  })

  /* Before `/inventory`, because a regex that reaches this URL first would swallow it. The
   * search route is the only one in this server with a query string, which is what makes it
   * safe to match on `?` at all. */
  await page.route(/\/search\?/, async (route) => {
    if (mood.searchFail === true) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        // The server's register again, and again none of it may reach him. Two banned words
        // and a filename, which is what makes it the right fixture for this path.
        body: JSON.stringify({
          error: {
            code: 'store_unreadable',
            message: 'inventory.json will not parse; the staged import may be mid-sync.',
          },
        }),
      })
      return
    }
    const asked = new URL(route.request().url()).searchParams.get('q') ?? ''
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(searchAnswer(asked, states, mood.soldHere ?? 0)),
    })
  })

  /* Before `/inventory`, and its own route: `/orders` is read on the same trigger the cards
     are, so a sale re-reads both. */
  await page.route(/\/orders$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mood.orders ?? NO_ORDERS),
    })
  })

  /* The second tier `GET /orders` names in its own comment (S1, UX-001): the screen's real
     picks. `POST` because a key is `source:number` and a number may legally carry a colon —
     the same reason the real route takes a body rather than a query string. */
  await page.route(/\/orders\/walk-plan$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(mood.plan ?? EMPTY_PLAN),
    })
  })

  await page.route(/\/inventory$/, async (route) => {
    mood.reads = (mood.reads ?? 0) + 1
    // Long enough to read the screen and short enough not to be the test's runtime. The
    // loading state is the one screen here that nothing else can hold still.
    if (mood.slow === true) await new Promise((done) => setTimeout(done, 1200))
    if (mood.fail === true) {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        // The server's own register again, and again none of it may reach him: this one is
        // three banned words in one sentence, which is what makes it the right fixture.
        body: JSON.stringify({
          error: {
            code: 'store_unreadable',
            message: 'inventory.json will not parse; the staged import may be mid-sync.',
          },
        }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(inventoryBody(states)),
    })
  })

  await page.route(/\/photo\/\d+\/\d+$/, async (route) => {
    if (mood.noPhoto === true) {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({
          error: { code: 'photo_not_found', message: 'No photo for that position.' },
        }),
      })
      return
    }
    await route.fulfill({ status: 200, contentType: 'image/svg+xml', body: PHOTO_SVG })
  })

  return states
}

// ------------------------------------------------------------------ reading the rendered page

type Rgb = { r: number; g: number; b: number; a: number }

/* Parsed with one regex and no `split(',')`. eslint bans that call across this app — v1 bug 2,
 * naive CSV parsing — and the pull-confirm spec needed a named exemption in
 * `app/eslint.config.js` to use it on a color string. A regex needs no exemption, which is
 * the better shape for a rule whose whole point is that nobody should have to decide when it
 * does not apply. */
const RGB = /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:[\s,/]+([\d.]+))?\s*\)$/

function parseRgb(value: string): Rgb | null {
  const match = RGB.exec(value.trim())
  if (match === null) return null
  const [, r, g, b, a] = match
  if (r === undefined || g === undefined || b === undefined) return null
  return { r: Number(r), g: Number(g), b: Number(b), a: a === undefined ? 1 : Number(a) }
}

/** WCAG 2.1 relative luminance. */
function luminance({ r, g, b }: Rgb): number {
  const channel = (raw: number) => {
    const c = raw / 255
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
  }
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

function contrastRatio(one: Rgb, two: Rgb): number {
  const a = luminance(one)
  const b = luminance(two)
  const [hi, lo] = a > b ? [a, b] : [b, a]
  return (hi + 0.05) / (lo + 0.05)
}

/** One run of text on screen, with everything needed to judge it and to find it again. */
type Run = { text: string; where: string; size: number; color: string; ground: string }

/* Every text node the view renders, with the computed style of the element that carries it.
 *
 * A TreeWalker over text nodes rather than a list of selectors, because the constraint says
 * "every text node in the view" and a selector list only ever covers the elements somebody
 * remembered. A future contributor's new `<span>` is caught by this and would be invisible to
 * the other shape.
 *
 * `checkVisibility` rather than a display/visibility comparison: an element inside a hidden
 * subtree computes its own `display` as whatever it was given, so the naive check reports a
 * hidden node as visible. Hidden text is excluded because it is not in the view — that is the
 * same call the nav rule in Fulfillment.css relies on, and the destructive-route test below
 * is where it is made honest.
 *
 * The ground is resolved by walking up to the first opaque background, which is what the eye
 * does: `.pull-confirm-label` is white on nothing, sitting on a button filled with --accent.
 */
async function runsIn(view: Locator): Promise<Run[]> {
  return view.evaluate((root) => {
    /* THE GROUND, COMPOSITED RATHER THAN THE FIRST COLOUR FOUND.
     *
     * A translucent layer is a real ground — what the eye reads is it painted over whatever is
     * behind it — and this view has one that is only ever translucent for 120ms: a disclosure
     * head with a hover transition from nothing to a surface color. Read at the wrong instant,
     * the first-color-found form returned `rgba(247, 248, 250, 0.96)` and the opacity guard
     * below failed on a screen that is fine, intermittently, under load. Compositing answers
     * the same color once the transition lands and the right one while it is running.
     *
     * THE GUARD IS UNTOUCHED: the walk still ends at a fully transparent answer when NOTHING
     * behind the text is opaque, which is what a stylesheet that did not load looks like, and
     * `noThinContrast` still refuses to measure that. */
    const READ = /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:[\s,/]+([\d.]+))?\s*\)$/
    const groundOf = (start: Element): string => {
      // Front to back: each layer is painted over the one after it.
      const layers: { r: number; g: number; b: number; a: number }[] = []
      let node: Element | null = start
      while (node !== null) {
        const found = READ.exec(window.getComputedStyle(node).backgroundColor.trim())
        if (found !== null) {
          const a = found[4] === undefined ? 1 : Number(found[4])
          if (a > 0) {
            layers.push({ r: Number(found[1]), g: Number(found[2]), b: Number(found[3]), a })
            if (a === 1) {
              // Composite back to front onto the opaque layer we just reached.
              let out = layers[layers.length - 1]!
              for (let at = layers.length - 2; at >= 0; at -= 1) {
                const over = layers[at]!
                out = {
                  r: over.r * over.a + out.r * (1 - over.a),
                  g: over.g * over.a + out.g * (1 - over.a),
                  b: over.b * over.a + out.b * (1 - over.a),
                  a: 1,
                }
              }
              return `rgb(${Math.round(out.r)}, ${Math.round(out.g)}, ${Math.round(out.b)})`
            }
          }
        }
        node = node.parentElement
      }
      // The page ground itself is painted on <body>; reaching past it means the walk found
      // nothing opaque at all, which is a stylesheet that did not load.
      return 'rgba(0, 0, 0, 0)'
    }

    const describe = (element: Element): string => {
      const classes = element.getAttribute('class')
      return `${element.tagName.toLowerCase()}${classes === null ? '' : `.${classes}`}`
    }

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
    const out: Run[] = []
    let node = walker.nextNode()
    while (node !== null) {
      const text = (node.textContent ?? '').trim()
      const parent = node.parentElement
      if (text !== '' && parent !== null && parent.checkVisibility()) {
        const style = window.getComputedStyle(parent)
        out.push({
          text,
          where: describe(parent),
          size: Number.parseFloat(style.fontSize),
          color: style.color,
          ground: groundOf(parent),
        })
      }
      node = walker.nextNode()
    }
    return out
  })
}

/** Every visible thing on the whole page that can be pressed, with its box. Page-wide and not
 *  view-wide on purpose: a control outside this view is still under his thumb.
 *
 *  The label carries the accessible name as well as the visible text, because the receipts
 *  put the position in an `aria-label` — and the destructive-wording check below reads these
 *  labels, so a control whose only name is an attribute must not be invisible to it. */
async function targets(page: Page): Promise<{ where: string; box: DOMRect; floating: boolean }[]> {
  return page.evaluate(() => {
    /* WHICH LAYER THE CONTROL IS ON. A receipt sheet is `position: fixed` over the page and
       takes every tap inside its own footprint, so a row it happens to be covering is not the
       Undo's NEIGHBOUR — it is behind it, and the 12px rule is about two things a thumb can
       land between. Recorded here rather than decided here: `fatTargets` is where it is used,
       and every size check below still runs on every control whichever layer it is on. */
    const onAnOverlay = (start: Element): boolean => {
      let node: Element | null = start
      while (node !== null) {
        if (window.getComputedStyle(node).position === 'fixed') return true
        node = node.parentElement
      }
      return false
    }
    const out: { where: string; box: DOMRect; floating: boolean }[] = []
    for (const element of document.querySelectorAll('button, a[href], input, select, textarea')) {
      if (!element.checkVisibility()) continue
      const classes = element.getAttribute('class')
      const named = element.getAttribute('aria-label')
      const text = `${(element.textContent ?? '').trim()} ${named ?? ''}`.trim()
      out.push({
        where: `${element.tagName.toLowerCase()}${classes === null ? '' : `.${classes}`}: ${text.slice(0, 120)}`,
        box: element.getBoundingClientRect().toJSON() as DOMRect,
        floating: onAnOverlay(element),
      })
    }
    return out
  })
}

/** A rectangle in DOCUMENT coordinates. Playwright scrolls an element into view before
 *  clicking it, so two viewport-relative boxes taken either side of a click can be measured
 *  against different scroll positions — which would make the overlap test below quietly
 *  meaningless. */
type Box = { x: number; y: number; width: number; height: number }

async function boxOf(target: Locator): Promise<Box> {
  return target.evaluate((node) => {
    const rect = node.getBoundingClientRect()
    return {
      x: rect.x + window.scrollX,
      y: rect.y + window.scrollY,
      width: rect.width,
      height: rect.height,
    }
  })
}

function overlaps(a: Box, b: Box): boolean {
  return (
    a.x < b.x + b.width && b.x < a.x + a.width && a.y < b.y + b.height && b.y < a.y + a.height
  )
}

/** The shortest distance between two rectangles. Zero when they overlap on both axes, which
 *  is what two abutting rows are and what the 12px rule is written against. */
function apart(a: DOMRect, b: DOMRect): number {
  const dx = Math.max(a.x - (b.x + b.width), b.x - (a.x + a.width), 0)
  const dy = Math.max(a.y - (b.y + b.height), b.y - (a.y + a.height), 0)
  return Math.max(dx, dy)
}

const view = (page: Page): Locator => page.locator(VIEW)

/** The photo AS PAINTED, not as laid out.
 *
 *  `boundingBox()` measures the element, and the element carries `aspect-ratio` and a width
 *  from the stylesheet — so it answers 360x503 whether the image decoded, decoded and was
 *  cropped to fill, or letterboxed inside its own box with ground showing either side. The
 *  constraints table says "card photo >= 320px on the short edge", and the thing that has to
 *  be 320px is the card he is looking at. So this resolves `object-fit` the way the browser
 *  does and returns the rectangle actually covered by image pixels, along with the natural
 *  short edge — zero when nothing decoded, which no layout box can tell you. */
async function paintedPhoto(
  page: Page,
  /* The card panel's photo by default, and the search result's when asked for. One function
   * rather than two, because the constraint is one row of the table and the arithmetic that
   * resolves `object-fit` is the part worth having in one place — the two elements are drawn
   * by different stylesheets and are held to the same 320px. */
  selector = '.fulfillment-photo',
): Promise<{ width: number; height: number; natural: number }> {
  return view(page)
    .locator(selector)
    .first()
    .evaluate((node) => {
      const img = node as HTMLImageElement
      const box = img.getBoundingClientRect()
      const wide = img.naturalWidth
      const tall = img.naturalHeight
      if (wide === 0 || tall === 0) return { width: 0, height: 0, natural: 0 }

      const fit = window.getComputedStyle(img).objectFit
      const natural = Math.min(wide, tall)
      let scale: number
      if (fit === 'cover') scale = Math.max(box.width / wide, box.height / tall)
      else if (fit === 'contain') scale = Math.min(box.width / wide, box.height / tall)
      else if (fit === 'scale-down') scale = Math.min(1, box.width / wide, box.height / tall)
      else if (fit === 'none') scale = 1
      // `fill` stretches to the box, so the painted area is the box.
      else return { width: box.width, height: box.height, natural }

      // Default `object-position` is 50% 50%, so what survives on each axis is whichever is
      // smaller: the scaled image, or the box that clips it.
      return {
        width: Math.min(wide * scale, box.width),
        height: Math.min(tall * scale, box.height),
        natural,
      }
    })
}

/* THE CHECKS THAT APPLY TO EVERY SCREEN THIS VIEW HAS, rather than to the one a test happens
 * to be looking at.
 *
 * They are functions and not a `test.step` inside each test because of what the breaking
 * exercise found: run against the list and the card panel only, the walk never reads the
 * screen he sees while the cards load, the one he sees when they do not, the one with nothing
 * to pull, the one whose photo is missing, or the receipt above any of them. A banned word or
 * a 12px line on any of those was invisible.
 */

async function noSmallText(page: Page, where: string): Promise<void> {
  const runs = await runsIn(view(page))
  expect(runs.length, `${where}: nothing rendered, so nothing was measured`).toBeGreaterThan(0)
  const small = runs.filter((run) => run.size < BODY_FLOOR)
  expect(small, `${where}: below the ${BODY_FLOOR}px floor`).toEqual([])
}

async function noThinContrast(page: Page, where: string): Promise<void> {
  const runs = await runsIn(view(page))
  expect(runs.length, `${where}: nothing rendered`).toBeGreaterThan(0)
  for (const run of runs) {
    const ink = parseRgb(run.color)
    const ground = parseRgb(run.ground)
    expect(ink, `${where} ${run.where}: unreadable color ${run.color}`).not.toBeNull()
    expect(ground, `${where} ${run.where}: unreadable ground ${run.ground}`).not.toBeNull()
    // A see-through ground makes the ratio below a measurement of nothing, and is exactly
    // what a stylesheet that failed to load looks like.
    expect(ground!.a, `${where} ${run.where}: the ground is not opaque`).toBe(1)
    expect(ink!.a, `${where} ${run.where}: the text is not opaque`).toBe(1)
    expect(
      contrastRatio(ink!, ground!),
      `${where} ${run.where}: "${run.text.slice(0, 30)}"`,
    ).toBeGreaterThanOrEqual(CONTRAST_FLOOR)
  }
}

/** `hasControls` is false ONLY for a screen that legitimately offers nothing to press — the
 *  loading sentence is the one, and it is named at its call site. It is not an escape hatch:
 *  the size and spacing assertions below run either way, and defaulting to true keeps a
 *  screen that has quietly lost its controls failing. */
async function fatTargets(page: Page, where: string, hasControls = true): Promise<void> {
  const found = await targets(page)
  if (hasControls) expect(found.length, `${where}: no control on screen`).toBeGreaterThan(0)

  for (const target of found) {
    expect(target.box.width, `${where} ${target.where}: width`).toBeGreaterThanOrEqual(TARGET_FLOOR)
    expect(target.box.height, `${where} ${target.where}: height`).toBeGreaterThanOrEqual(
      TARGET_FLOOR,
    )
  }

  // Every pair, not just the vertically adjacent ones. Two controls side by side are the case
  // the pull-confirm spec could not reach with one component, and the case a list of rows plus
  // a panel above them creates as soon as anything is laid out in a row.
  for (let i = 0; i < found.length; i += 1) {
    for (let j = i + 1; j < found.length; j += 1) {
      const a = found[i]!
      const b = found[j]!
      /* ONE LAYER AT A TIME. The receipt sheet floats over the list, so at any scroll position
         it lies across rows it is not beside — and a rule read across that boundary reports a
         0px gap between a control and something the sheet is sitting on top of, which is not a
         mis-tap he can make. Both halves are still measured in full against their own layer:
         every control in the sheet against every other control in the sheet, and every control
         on the page against every other control on the page. */
      if (a.floating !== b.floating) continue
      expect(apart(a.box, b.box), `${where}: ${a.where} -> ${b.where}`).toBeGreaterThanOrEqual(
        GAP_FLOOR,
      )
    }
  }
}

/* THE BANNED-WORD LIST, which is the one assertion here written against a future contributor
 * rather than against a layout.
 *
 * docs/DESIGN.md: "copy passes a banned-word list: SKU, CSV, import, sync, batch, queue,
 * staged". Every one of those is a word this repo uses constantly and correctly everywhere
 * else — the specs, the owner's screens, the run report — which is exactly why the slip is
 * plausible. It will not arrive as a mistake; it will arrive as somebody being helpful in a
 * hurry.
 *
 * Matched case-insensitively with the common inflections and nothing more. A bare substring
 * match reads "important" as "import" and fails on a word this screen might legitimately
 * want; requiring a whole word misses "importing" and "queued", which are the same offence
 * conjugated. The suffix set below is the narrow middle, and it is deliberately not clever:
 * the failure it must not have is the one where it goes quiet.
 *
 * It reads attribute copy as well as text. `alt` and `aria-label` are what he hears if he
 * ever turns a screen reader on, and copy nobody proofreads is exactly where a system word
 * survives.
 */
const BANNED = ['sku', 'csv', 'import', 'sync', 'batch', 'queue', 'staged']
const BANNED_RE = new RegExp(`\\b(${BANNED.join('|')})(s|d|es|ed|ing)?\\b`, 'i')

async function copyIn(view: Locator): Promise<{ text: string; where: string }[]> {
  return view.evaluate((root) => {
    const describe = (element: Element): string => {
      const classes = element.getAttribute('class')
      return `${element.tagName.toLowerCase()}${classes === null ? '' : `.${classes}`}`
    }
    const out: { text: string; where: string }[] = []

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
    let node = walker.nextNode()
    while (node !== null) {
      const text = (node.textContent ?? '').trim()
      const parent = node.parentElement
      if (text !== '' && parent !== null && parent.checkVisibility()) {
        out.push({ text, where: describe(parent) })
      }
      node = walker.nextNode()
    }

    for (const element of root.querySelectorAll('[alt], [aria-label], [title], [placeholder]')) {
      for (const attribute of ['alt', 'aria-label', 'title', 'placeholder']) {
        const value = element.getAttribute(attribute)
        if (value !== null && value.trim() !== '') {
          out.push({ text: value, where: `${describe(element)}[${attribute}]` })
        }
      }
    }
    return out
  })
}

async function noJargon(page: Page, where: string): Promise<void> {
  const copy = await copyIn(view(page))
  expect(copy.length, `${where}: no copy to read`).toBeGreaterThan(0)
  for (const line of copy) {
    const found = BANNED_RE.exec(line.text)
    expect(
      found === null,
      `${where} ${line.where}: "${found?.[0] ?? ''}" is on the banned list — "${line.text}"`,
    ).toBe(true)
  }
}

/* "Destructive actions: zero reachable from this view; assert no route to settings or import."
 *
 * A ROW ABOUT THE VIEW, WHICH MEANS EVERY SCREEN THE VIEW CAN BE. It was asserted on the list
 * alone, which reduced it to "no visible anchor on the list screen" — and the screens it did
 * not look at are the ones that gained controls: the card panel, the pulled step, and the
 * receipts that now sit above both. So this is a function, and every screen calls it.
 *
 * A link is the route. The shell draws one to every other screen above every view, and the
 * capture screen those reach carries an undo that hard-deletes a record, a sidecar and a
 * photo (D10) — which is the destructive action this row is about. Counting VISIBLE links
 * rather than links in the document is the honest form: `display: none` is not clickable, not
 * focusable and not reachable by a screen reader.
 *
 * The wording check is read off the rendered controls rather than off a list of routes,
 * because a button that deletes without navigating is the same hazard without the href.
 */
async function noWayOut(page: Page, where: string): Promise<void> {
  for (const link of await page.locator('a[href]').all()) {
    expect(
      await link.isVisible(),
      `${where}: a route out — ${await link.getAttribute('href')}`,
    ).toBe(false)
  }
  await expect(page.locator('.app-nav'), `${where}: the shell drew chrome here`).toBeHidden()

  for (const target of await targets(page)) {
    expect(target.where.toLowerCase(), `${where}: a destructive control is on screen`).not.toMatch(
      /delete|remove|erase|discard|settings|import/,
    )
  }
}

/** The whole table, at one screen. `hasControls` is passed straight through to `fatTargets`. */
async function battery(page: Page, where: string, hasControls = true): Promise<void> {
  await noSmallText(page, where)
  await noThinContrast(page, where)
  await noJargon(page, where)
  await noWayOut(page, where)
  await fatTargets(page, where, hasControls)
}

/** The list screen, loaded and rendered. Returns the stub's store so a test can play the
 *  other device against it. */
async function openList(page: Page, wire: Wire[] = [], mood: Mood = {}): Promise<Store> {
  const states = await stubServer(page, wire, mood)
  await page.goto(VIEW_ROUTE)
  await settleFonts(page)
  await expect(
    view(page),
    `no Fulfillment view at ${VIEW_ROUTE} — is the route registered in App.tsx?`,
  ).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Cards to pull' })).toBeVisible()
  return states
}

/* THE LAYOUT HAS TO HAVE STOPPED MOVING BEFORE A RULER TOUCHES IT.
 *
 * `fontsReady.ts` says why the faces matter and closes the case where every face is already
 * loading when the promise is made. It does not close this one: the card panel draws the
 * display family at a WEIGHT NO OTHER SCREEN USES, so the load starts when the panel opens —
 * after `document.fonts.ready` has already been asked and answered. Measured on the case the
 * overshoot rule turns on: the place label wrapped to three lines in the fallback and to one in
 * Manrope, moving the control under it by 86px between two reads of one screen.
 *
 * So this waits for the faces AND then for the view's own height to stop changing — the same
 * "wait for a true statement to become true" the config's timeout note describes. It weakens
 * nothing: no assertion or allowance moves, and a layout that is genuinely wrong is still
 * wrong when it settles. The frame cap keeps a page that never settles from hanging the run;
 * a measurement taken after it is no worse than one taken without any of this. */
async function settleLayout(page: Page): Promise<void> {
  /* EVERY DECLARED FACE, FETCHED, and not merely the ones already in flight.
     `document.fonts.ready` answers about the load cycle that is RUNNING; a weight this screen
     is the first to use has not started loading when the promise is asked for, so the swap
     lands after the wait is over. Asking each declared face to load leaves nothing that can
     arrive later. Failures are swallowed: a face that cannot be fetched is a page drawn in the
     fallback, which is a layout this file is entitled to measure — it just has to be the SAME
     layout at both reads. */
  // The faces are declared by a stylesheet fetched over the network, so there is a window in
  // which NOTHING is declared and the loop below has nothing to force. Bounded: a run with no
  // network draws in the fallback throughout, which is a layout this file may measure — it
  // just has to be the same one at both reads.
  await page
    .waitForFunction(() => document.fonts.size > 0, undefined, { timeout: 5_000 })
    .catch(() => undefined)
  await page.evaluate(async () => {
    const faces = [...(document.fonts as unknown as Iterable<FontFace>)]
    await Promise.all(faces.map((face) => face.load().catch(() => undefined)))
    await document.fonts.ready
  })
  /* AND THE FACES THIS SCREEN'S OWN TEXT IS SET IN, asked for by the elements themselves.
     `document.fonts.check` answers false while a face is still arriving and true when it has —
     or when nothing declares it, which is the no-network case going straight through. Reading
     the family off the rendered element keeps the wait honest if the tokens change their
     minds about which family that is. */
  await page
    .waitForFunction(
      () => {
        for (const element of document.querySelectorAll('main.fulfillment *')) {
          if ((element.textContent ?? '').trim() === '') continue
          const style = window.getComputedStyle(element)
          const face = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`
          if (!document.fonts.check(face)) return false
        }
        return true
      },
      undefined,
      { timeout: 5_000 },
    )
    .catch(() => undefined)
  /* TWICE, WITH THE FACES RE-ASKED IN BETWEEN. A face can land AFTER a run of three quiet frames
     — the check above is about the faces the screen declares it needs, and the browser decides
     when it has them — so one settling pass can end just before the reflow it exists to wait
     for. The second pass costs three frames on a page that is already still. */
  for (let pass = 0; pass < 2; pass += 1) {
    await settleFonts(page)
    await page.evaluate(
      () =>
        new Promise<void>((done) => {
          const read = () => document.querySelector('main.fulfillment')?.scrollHeight ?? 0
          let last = read()
          let same = 0
          let frames = 0
          const tick = () => {
            const now = read()
            same = now === last ? same + 1 : 0
            last = now
            frames += 1
            if (same >= 3 || frames > 180) done()
            else requestAnimationFrame(tick)
          }
          requestAnimationFrame(tick)
        }),
    )
  }
}

/* THE BOXES ARE SHUT WHEN HE ARRIVES, and that is the screen's own answer to a store of 229
 * cards: the browse list is folded one box per row and opens on a tap. So a case that wants to
 * SEE the walk has to do what he does and open them. Every box, in the order they are drawn,
 * which is what leaves the rows in box-walk order for the assertion that reads them.
 *
 * It is deliberately not a `data-testid` and not a click on the first box: `aria-expanded` is
 * the state a screen reader announces, so opening by it asserts in passing that the disclosure
 * says what it is doing. */
async function openEveryBox(page: Page): Promise<void> {
  /* WAITED FOR FIRST. The cards can still be on their way — a re-read after "Try again" is the
     ordinary case — and a loop that ran then would find nothing to open, break, and leave the
     caller looking for a row on a screen that has not drawn one yet. */
  /* SHORT WAITS, because this runs INSIDE a retried block (`expectWalk`): a re-read landing
     mid-loop puts a shut box back, and a fifteen-second wait on that would spend the whole
     retry budget of the case above rather than letting it start again. Long enough for a render,
     short enough to be re-run. */
  await expect(view(page).locator('.ff-box-head')).not.toHaveCount(0, { timeout: 5_000 })
  const heads = view(page).locator('.ff-box-head[aria-expanded="false"]')
  for (let guard = 0; guard < 40; guard += 1) {
    const shut = await heads.count()
    if (shut === 0) break
    await heads.first().click()
  }
  await expect(view(page).locator('.ff-box-head[aria-expanded="false"]')).toHaveCount(0, {
    timeout: 2_000,
  })
}

/** His row for one card. The rows live inside the boxes, and the boxes arrive shut — so
 *  finding one means opening them, which is what he does. */
async function cardRow(page: Page, name: string): Promise<Locator> {
  await openEveryBox(page)
  return page.getByRole('button', { name })
}

/** The walk as HE can see it: every box opened, then every row's position label, in the order
 *  the rows are drawn.
 *
 *  RETRIED AS ONE ACT, because the boxes arrive shut AND the list is re-read after every write:
 *  a box that comes back with an undo comes back SHUT, after an opening pass that could not
 *  have seen it, and its cards would then be missing from a walk that is in fact complete. So
 *  the opening and the reading are one retried block rather than an opening followed by a
 *  web-first assertion that can only wait for the second half. */
/** D218: the seam between `PlaceText`'s parts is CSS now (`.ff-place-elem::before`), which
 *  `allTextContents` never sees — generated content is not part of an element's `textContent`.
 *  `expected` keeps the server's own spelling, dot and all, because that is still what a caller
 *  reads and what `aria-label` would carry; this strips the same seam from it before comparing,
 *  so the assertion is about which PARTS are drawn and in what order, not about a character this
 *  component was told to stop typing. */
async function expectWalk(page: Page, expected: readonly string[]): Promise<void> {
  await expect(async () => {
    await openEveryBox(page)
    const drawn = await view(page).locator('.fulfillment-row .fulfillment-place').allTextContents()
    expect(drawn.map((one) => one.replace(/\s+/g, ' ').trim())).toEqual(
      expected.map((one) => one.replace(/\s*·\s*/g, '')),
    )
  }).toPass({ timeout: 20_000 })
}

/** The card panel for one card, photo loaded.
 *
 *  VISIBLE IS NOT DECODED, and the difference showed up as a real flake: `naturalWidth` was 0
 *  on the wider viewport while the same measurement on the phone read a true number. So this
 *  waits for `complete`, which is the browser saying the load attempt finished — either way.
 *  It deliberately does NOT wait for success: a broken image is `complete` with a natural size
 *  of zero, which is exactly the state the photo assertion has to be able to fail on. */
async function openCard(page: Page, name: string): Promise<void> {
  // His row is inside a box, and the boxes arrive shut. Opening them is how he reaches it.
  await openEveryBox(page)
  await page.getByRole('button', { name }).click()
  // The panel opens a face no other screen uses; see `settleLayout` for what that does to a
  // ruler that reads before it lands.
  await settleLayout(page)
  const photo = view(page).locator('.fulfillment-photo')
  await expect(photo).toBeVisible()
  await photo.evaluate(
    (node) =>
      new Promise<void>((settled) => {
        const img = node as HTMLImageElement
        if (img.complete) {
          settled()
          return
        }
        img.addEventListener('load', () => settled(), { once: true })
        img.addEventListener('error', () => settled(), { once: true })
      }),
  )
}

/* ------------------------------------------------------------------------------ the search
 *
 * THE SECOND WAY INTO THE SAME CARDS, and the reason it needed one: the store holds 229 cards,
 * 176 of them with no name recorded, and the box-walk list has no filter and no photo on the
 * row. Everything below asserts the same nine rows of the table against that path — a screen
 * he can reach is a screen the table binds, and the walk-only version of this file was the
 * shape docs/DESIGN.md warns about when it says the copy on a screen nobody renders is the
 * copy nobody proofreads.
 */

/** The field, by its own visible label. `getByLabel` rather than a class, because the label
 *  being real and associated is half of what makes the control usable — a lookup that would
 *  still pass with the `<label>` deleted is not measuring the thing it looks like it does. */
function searchBox(page: Page): Locator {
  return page.getByLabel('Type the name of the card')
}

/** The list screen with a name typed into it, waited out to the given number of copies.
 *
 *  WAITED ON THE COPIES AND NOT ON A TIMEOUT. `useSearch` holds a 200ms debounce and reports
 *  `loading` through it, so there is a real window in which the screen says it is looking and
 *  a `waitForTimeout` would be a guess at when that ends. */
async function openSearch(
  page: Page,
  text: string,
  copies: number,
  wire: Wire[] = [],
  mood: Mood = {},
): Promise<Store> {
  const states = await openList(page, wire, mood)
  await searchBox(page).fill(text)
  /* THE FIRST COPY IN WALK ORDER IS DRAWN IN FULL AND THE REST FOLD UNDER ONE CONTROL — the
     store's common cards carry a dozen, and a search that drew nineteen photographs down the
     page is the screen this fold exists to prevent. The owner's ruling is that a copy he can
     reach is still every copy he can reach, so this opens the fold the way he does and the
     cases below go on asserting that all of them are there, each whole. */
  await showEveryCopy(page)
  // The copies draw the heavy display face too — see `settleLayout`.
  await settleLayout(page)
  await expect(view(page).locator('.card-locations-copy')).toHaveCount(copies)
  return states
}

/** Every copy of every card the search found, on screen. See `openSearch` for why they are
 *  not all drawn at once, and why opening the fold is what HE does rather than a workaround. */
async function showEveryCopy(page: Page): Promise<void> {
  // The field is debounced, so the first copy has to be on screen before the fold under it
  // can be opened — a loop that ran while the search was still looking would find nothing to
  // open and leave the rest of the copies folded.
  await expect(view(page).locator('.card-locations-copy')).not.toHaveCount(0)
  for (let guard = 0; guard < 20; guard += 1) {
    const shut = view(page).locator('.ff-more-head[aria-expanded="false"]')
    if ((await shut.count()) === 0) break
    await shut.first().click()
  }
}

/** One copy's card in a search result, found by the position it names — the same scoping the
 *  receipts need and for the same reason: several copies of one card put several identical
 *  controls on screen, and a bare role lookup is ambiguous exactly when the thing under test
 *  is that all of them are there. */
function copyCard(page: Page, place: string): Locator {
  return view(page).locator('.card-locations-copy', { hasText: place })
}

/** Pull, then mark sold, on one copy in a search result. The two steps, in the two places. */
async function sellCopy(page: Page, place: string): Promise<void> {
  const card = copyCard(page, place)
  await card.getByRole('button', { name: 'Pull' }).click()
  await expect(card).toContainText('Pulled.')
  await card.getByRole('button', { name: 'Mark it sold' }).click()
}

/** Pull, then mark sold, on the card already open. */
async function sellOpenCard(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Pull' }).click()
  await expect(view(page)).toContainText('Pulled.')
  await page.getByRole('button', { name: 'Mark it sold' }).click()
}

/** The receipt panel for one card, found by the position it names. Scoped, because two sales
 *  standing at once put two Undo buttons on screen and a bare role lookup is ambiguous
 *  exactly when the thing under test is that both of them are there. */
/** D218: `hasText` matches literal `textContent`, which no longer carries the seam between
 *  `.ff-receipt-place`'s own parts (`.ff-receipt-place > span::before`) — every caller here
 *  still passes the server's own spelling, dot and all, so it reads like the label everywhere
 *  else in this file; this is the one place that strips it before the match. */
function receiptFor(page: Page, place: string): Locator {
  return view(page).locator('.fulfillment-panel', { hasText: place.replace(/\s*·\s*/g, '') })
}

// ------------------------------------------------------------------------------ the table

/** Every card for sale, in the order he walks the boxes. Box then index — `2/4` is sold and
 *  `9/12` has no position, so neither is in it.
 *
 *  ONE COPY OF THIS LIST, because three tests assert it and one of them asserts it after
 *  putting a card back. Three hand-written copies of the same five strings is three places for
 *  a fixture row to be added to two of them. */
const WALK = [
  'Box 1 · Section 1 · Card 3',
  'Box 2 · Section 1 · Card 9',
  'Box 3 · Section 1 · Card 7',
  'Box 3 · Section 2 · Card 1',
  'Box 4 · Section 1 · Card 2',
]

/* NOTHING HERE MAY REACH THE CAPTURE SERVER — `app/tests/shell.ts` carries the argument. The
   Fulfiller's route is `persona: 'fulfiller'`, so `App.tsx` renders no chrome over it and
   `useServerPresence` never polls: this file leaks no `/status` and never did. What it takes
   the seal for is the other half — a read this screen makes that nothing here stubs would
   otherwise go to the owner's real store, and the only thing that would say so is a
   Fulfillment view drawing cards nobody put in this checkout. */
sealEveryTest()

test("the owner's position treatment never reaches the Fulfiller", async ({ page }) => {
  /* ONE HELPER CALL, and that is a property of the helpers rather than a shortcut. `openSearch`
     calls `openList` itself, and `openList` calls `stubServer` — routing a page twice leaves the
     second stub unable to answer, so the heading never renders and the failure reads as a missing
     view. `openSearch` covers both surfaces in one navigation: the list is rendered on the way in
     and `.card-locations-place-large` is what the search results draw. */
  await openSearch(page, 'Eiscue', 2)

  /* THE FIREWALL, ASSERTED AS A CAUSE. `PositionLabel` redraws the position string for the
     OWNER's five sites — muted stacked path, promoted slot figure, interpuncts deleted. His
     labels must go on rendering the server string as plain text, floored by this file at >=32px
     with tabular figures, which D31 keeps unweakened.

     THE GUARD IS THE COMPONENT GRAPH, NOT A SELECTOR. `Fulfillment.tsx` and
     `CardLocations.tsx:FulfillerCard` do not import the component, so no `.position-*` rule can
     reach a node here — which is why stripping a class prefix cannot breach it and why lifting
     the call out of `OwnerCard` into a shared render path is the breach that would actually
     happen.

     THE REST OF THIS FILE ALREADY FIRES ON THAT BREACH, BY CONSEQUENCE: `BODY_FLOOR` would report
     sixteen nodes under 20px, because `.position-path` sets its own 11px and that wins over the
     container's 32px; and the `toHaveText` cases would fail on text that had become
     `BOX 2SECTION 19`, uppercased and de-dotted. Those are symptoms. This is the cause, so a
     breach names itself instead of being diagnosed from a font size. */
  await expect(view(page).locator('.position-parts')).toHaveCount(0)
  await expect(view(page).locator('.position-run')).toHaveCount(0)

  /* And his label is really on screen, so the count-zero above is a firewall rather than an empty
     view agreeing with everything. */
  await expect(view(page).locator('.card-locations-place-large')).not.toHaveCount(0)
})


test('the cards for sale are listed in box-walk order, and nothing else is listed', async ({
  page,
}) => {
  await openList(page)
  // Box then index: 1/3, 2/9, 3/7, 3/26, 4/2. The fixture is written in another order, so this
  // measures the sort rather than the object it came from — and the boxes are drawn in box
  // order too, so opening all of them leaves the rows in exactly the order he walks them.
  await expectWalk(page, WALK)
  // Captured, not for sale, and therefore not his to sell.
  // D218: `getByText` matches literal `textContent`, which no longer carries the seam — a dot
  // in this call would go vacuous (every place string looks like this to a raw substring match)
  // rather than red the moment the sold card leaked back in.
  await expect(page.getByText('Box 2Section 1Card 4')).toHaveCount(0)
  // For sale but unplaced: counted on screen, never dropped in silence.
  await expect(view(page)).toContainText('1 card for sale is not shown here')
})

/* THE ORDERS, WHICH ARE THE SCREEN'S FIRST ANSWER NOW. `POST /orders/walk-plan` resolves every
 * open order's own demand to every on-hand copy of each SKU, and those copies are drawn above
 * the boxes as "Cards to pick" -- one entry per SKU, "Pick N", and every copy the store holds,
 * NONE PRESELECTED (the owner's own ruling, 2026-09-23: "I shouldn't just see 2 cards that are
 * preselected. I should be told I need to pick 2, and here's where all the copies are." D212,
 * D93). This is the S1 defect's own test (UX-001): the screen used to build this list from
 * `GET /orders`'s `picks`, which have answered `[]` since 2026-09-16 -- so it showed a green
 * "No orders are waiting" while 71 open orders on the owner's real store owed 216 copies. This
 * case asserts the list ACTUALLY DRAWS what the orders owe, and it holds the whole floor table
 * to it, for the reason the file's header gives: the copy on a screen nobody renders is the
 * copy nobody proofreads.
 *
 * The rest of this file runs against a ledger with nothing open, which is the same screen with
 * that section absent; this case is the one that renders it.
 */
test('a card an open order owes is drawn as "Pick N" with every copy the store holds, none preselected', async ({
  page,
}) => {
  await openList(page, [], { orders: ONE_OPEN_ORDER, plan: ONE_OPEN_ORDER_PLAN })

  // The figure he reads first, and it counts copies rather than orders.
  await expect(view(page)).toContainText('1 copy to pick')

  /* The card is on screen WITHOUT opening a box: an order's demand is the list, and the boxes
     below it are the other way in. */
  const card = view(page).locator('.ff-owed-card', { hasText: 'Charizard ex' })
  await expect(card.locator('.ff-owed-pick')).toContainText('Pick 1')
  /* NONE PRESELECTED: this is `CardLocations`' own copies list, the same one a search result
     draws, with a two-step Pull/Mark-sold control on the copy itself -- not a single card that
     opens on its own screen. D218: the seam is CSS now (`.ff-place-elem::before` /
     `.card-locations-place-large`'s own render), never part of `textContent`. */
  // `CardLocations`' own place text is the server's raw label, dots and all — unlike
  // `PlaceText`'s CSS seam, this component has never stripped it.
  await expect(card.locator('.card-locations-place-large')).toHaveText('Box 3 · Section 1 · Card 7')
  await expect(card.getByRole('button', { name: 'Pull' })).toBeVisible()
  await battery(page, 'cards to pick')

  // And pulling it sells THROUGH the order, so the owner's ledger counts it.
  await card.getByRole('button', { name: 'Pull' }).click()
  await card.getByRole('button', { name: 'Mark it sold' }).click()
  await expect(view(page)).toContainText('Marked sold.')
  // D193: the buyer's name leads, and the raw order id never stands alone.
  await expect(view(page)).toContainText(`Order ${ORDER_NUMBER}`)
  await battery(page, 'sold through an order')
})

/* THE OWNER'S OWN CASE. `MULTI_PLAN`'s own comment has the ruling verbatim: two wanted,
 * three on hand, three different boxes -- and the screen must say "Pick 2" and offer every
 * one of the three, never two preselected copies standing in for the SKU. */
test('a SKU owed 2 with 3 copies on hand shows "Pick 2" and every copy, none preselected', async ({
  page,
}) => {
  await openList(page, [], { orders: MULTI_ORDER, plan: MULTI_PLAN })

  const card = view(page).locator('.ff-owed-card', { hasText: 'Promising Future' })
  await expect(card.locator('.ff-owed-pick')).toContainText('Pick 2')

  // ALL THREE, not two -- the wanted count never caps the copies list (D212, D93).
  await expect(card.locator('.card-locations-copy')).toHaveCount(3)
  await expect(card.locator('.card-locations-place-large')).toHaveText([
    'Box 1 · Section 1 · Card 5',
    'Box 2 · Section 1 · Card 9',
    'Box 4 · Section 2 · Card 2',
  ])

  // NONE PRESELECTED: every one of the three offers the same first-step control, none of
  // them already "Pulled." or otherwise singled out.
  await expect(card.getByRole('button', { name: 'Pull' })).toHaveCount(3)
  await expect(card.locator('.card-locations-copy', { hasText: 'Pulled.' })).toHaveCount(0)
  await battery(page, 'owed SKU with 3 copies')
})

/* THE SORT, PROVED AGAINST THE WIRE'S OWN DELIVERY ORDER, not against a fixture that already
 * happens to agree with it. `pipeline/walkplan.py:plan` sorts stops by the solver's own cost,
 * never by box number (`docs/specs/order-walk-plan.md` §7 — sections counted flat, boxes
 * free), so a plan naming Box 5 before Box 1 is a real, legal answer the solver can send.
 * This plan does exactly that; the screen must still draw Box 1 first. */
const WALK_ORDER_PLAN = {
  cost: 'sections',
  stops: [
    {
      key: 'box/5/section/1', box: 5, box_name: null, section: 1, section_name: null,
      pooled: false, game: null, game_display: null, order: 1,
      span: { start: 1, end: 10 }, box_total: 10,
      takes: [{
        sku: '9199010', name: 'Xerneas', number_display: null, set: null, rarity: null,
        condition: null, wanted: 1,
        for: [{ key: ORDER_KEY, number: ORDER_NUMBER, buyer: ORDER_BUYER }],
        copies: [{
          key: '5/1', state: 'identified', has_photo: true, capture_id: 'cap-x', cid: null,
          place: {
            label: 'Box 5 · Section 1 · Card 1', located: true, box: 5, index: 1, slot: 1,
            section: 1, card: 1, box_name: null, section_start: 1, section_end: 10,
            box_total: 10, box_closed: true, fraction: 0.1, neighbors: null, section_gaps: 0,
          },
          here: true,
        }],
        listed: { pushed: 0, staged: 0, live: 0 }, sold_here: 0, live_as_of: null,
      }],
    },
    {
      key: 'box/1/section/1', box: 1, box_name: null, section: 1, section_name: null,
      pooled: false, game: null, game_display: null, order: 2,
      span: { start: 1, end: 10 }, box_total: 10,
      takes: [{
        sku: '9199011', name: 'Aerodactyl', number_display: null, set: null, rarity: null,
        condition: null, wanted: 1,
        for: [{ key: ORDER_KEY, number: ORDER_NUMBER, buyer: ORDER_BUYER }],
        copies: [{
          key: '1/1', state: 'identified', has_photo: true, capture_id: 'cap-a', cid: null,
          place: {
            label: 'Box 1 · Section 1 · Card 1', located: true, box: 1, index: 1, slot: 1,
            section: 1, card: 1, box_name: null, section_start: 1, section_end: 10,
            box_total: 10, box_closed: true, fraction: 0.1, neighbors: null, section_gaps: 0,
          },
          here: true,
        }],
        listed: { pushed: 0, staged: 0, live: 0 }, sold_here: 0, live_as_of: null,
      }],
    },
  ],
  shortfall: [],
  counts: { stops: 2, boxes: 2, copies: 2, sections_considered: 2, sections_candidate: 2, exact: true, solve_ms: 2 },
}

test('two owed cards delivered out of walk order are drawn IN walk order', async ({ page }) => {
  await openList(page, [], { orders: ONE_OPEN_ORDER, plan: WALK_ORDER_PLAN })
  // The wire named Box 5 (Xerneas) before Box 1 (Aerodactyl); the screen draws Box 1 first.
  await expect(view(page).locator('.ff-owed-card h2')).toHaveText(['Aerodactyl', 'Xerneas'])
})

/* A card the same order also claims, reached by browsing a box instead of through "Cards to
 * pick" -- the walk-in case (`claim`, `Fulfillment.tsx`): a copy an order is waiting for is
 * sold through the order however he reaches it. This is also where "No name" is asserted now:
 * the buyer's name is not drawn on the owed card itself (D212 -- the card is fungible, not
 * "for" one buyer to look at), but the card he opens from a box still says which order is
 * waiting, so he can match the packing slip. */
test('a card an order is waiting for still says which order, opened from a box', async ({
  page,
}) => {
  const noBuyerOrder = {
    ...ONE_OPEN_ORDER,
    orders: [{ ...ONE_OPEN_ORDER.orders[0], buyer: null }],
  }
  const noBuyerPlan = {
    ...ONE_OPEN_ORDER_PLAN,
    stops: [
      { ...ONE_OPEN_ORDER_PLAN.stops[0]!, takes: [{ ...ORDER_TAKE, for: [{ ...ORDER_TAKE.for[0]!, buyer: null }] }] },
    ],
  }
  await openList(page, [], { orders: noBuyerOrder, plan: noBuyerPlan })
  await openCard(page, 'Charizard ex')
  await expect(view(page)).toContainText('For No name')
  await expect(view(page).locator('.ff-card-order-id')).toContainText(ORDER_NUMBER)
  await expect(view(page).locator('.fulfillment-photo')).toBeVisible()
  await battery(page, 'card for an order, no buyer name')
})

/* fulfiller.md finding 5, restated for D212: "8 things on this order are not in the boxes"
 * named a real gap and answered nothing. UX-001's own direction: "if the screen cannot place a
 * copy, it says how many" -- a SKU the store holds none of at all is `plan.shortfall`, drawn as
 * a warm note beside the figure rather than a dead end, and `noWayOut` inside `battery` still
 * asserts nothing here routes him off this screen. */
test('a SKU the boxes cannot fill at all gets a count, not a dead end', async ({ page }) => {
  await openList(page, [], { orders: ORDER_WITH_ELSEWHERE, plan: ORDER_WITH_ELSEWHERE_PLAN })
  await expect(view(page)).toContainText('8 more copies are not in the boxes')
  await battery(page, 'order with a shortfall SKU')
})

/* fulfiller.md finding 2: "Charizard" names a game (Pokemon) that may hold none of this
 * store's cards -- D21 makes game a per-card claim, not a fixed catalog, and this store's
 * fixture is Iono/Eiscue/Pidgeot ex/Charizard ex on purpose so no one name can stand for the
 * whole thing. The placeholder now has to be drawn from `cards`, in box-walk order, rather
 * than a name typed into the component. */
test('the search hint names a real card from this store, not a fixed example', async ({ page }) => {
  await openList(page)
  await expect(page.getByPlaceholder(/^For example, /)).toHaveAttribute(
    'placeholder',
    'For example, Iono',
  )
})

/* UX-055: the placeholder is a card's own name and has no length ceiling — "Promising Future"
 * measured long enough at 390px, 24px font, to hard-clip mid-word ("Piercing Li") before this
 * fix. `overflow`/`text-overflow: ellipsis` reaches a placeholder the same way it reaches
 * typed text, so this asserts the computed style directly rather than a screenshot: the fix
 * is the STYLE, and it holds regardless of which card's name happens to be the example. */
test('the search placeholder ends in an honest ellipsis at 390px, never a raw mid-word cut', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openList(page, [], { orders: MULTI_ORDER, plan: MULTI_PLAN })
  const input = page.getByPlaceholder(/^For example, /)
  await expect(input).toHaveAttribute('placeholder', 'For example, Promising Future')
  const style = await input.evaluate((node) => {
    const computed = window.getComputedStyle(node)
    return { overflow: computed.overflow, textOverflow: computed.textOverflow }
  })
  // Chromium normalizes a text `<input>`'s COMPUTED `overflow` to `clip` regardless of the
  // author's declared value — a browser quirk over form controls' own internal scrolling,
  // not a sign the rule did not apply. `hidden` is what was written; `clip` is what a
  // Chromium `getComputedStyle` answers for it here, and `text-overflow: ellipsis` still
  // renders correctly under either (proved live: `scratchpad/lanes/fulfillment/ff-*.png`).
  expect(['hidden', 'clip']).toContain(style.overflow)
  expect(style.textOverflow).toBe('ellipsis')
})

/* UX-101: this screen has no shell (D5), so the owner's own `?` sheet (`App.tsx`) cannot open
 * here at all -- and the dead `/` row that once claimed otherwise for this screen is deleted
 * from `App.tsx`'s own `SHORTCUTS` table. This is the screen's own small answer to `?`,
 * proved end to end: it opens, it names what this screen actually takes, and it closes. */
test('"?" opens this screen\'s own keyboard reference, and closes it again', async ({ page }) => {
  await openList(page)
  await expect(view(page).locator('.ff-keys')).toHaveCount(0)

  await page.keyboard.press('?')
  const sheet = view(page).locator('.ff-keys')
  await expect(sheet).toBeVisible()
  await expect(sheet).toContainText('Esc')
  await expect(sheet).toContainText('Close the enlarged photograph')
  // THE FLOOR TABLE REACHES THE SHEET TOO — its key caps and text are on screen exactly
  // like any other card, and `battery` holds them to the same nine rows while it is open.
  await battery(page, 'keyboard shortcuts sheet')

  await page.keyboard.press('Escape')
  await expect(view(page).locator('.ff-keys')).toHaveCount(0)

  // And the close button works the same way.
  await page.keyboard.press('?')
  await expect(view(page).locator('.ff-keys')).toBeVisible()
  await view(page).getByRole('button', { name: 'Close' }).click()
  await expect(view(page).locator('.ff-keys')).toHaveCount(0)
})

test(`every text node is at least ${BODY_FLOOR}px, on the list and on the card`, async ({
  page,
}) => {
  await openList(page)
  await noSmallText(page, 'list')
  await openCard(page, 'Charizard ex')
  await noSmallText(page, 'card')
  // The step the fill moves on. Also the state where a stray key chip would show up: the
  // pull-confirm draws one at 10px when it is given a keyHint, and his screens are touch and
  // show none — this walk is what would catch one being passed.
  await page.getByRole('button', { name: 'Pull' }).click()
  await noSmallText(page, 'pulled')
})

test(`every text run clears ${CONTRAST_FLOOR}:1 against its own ground`, async ({ page }) => {
  await openList(page)
  await noThinContrast(page, 'list')
  await openCard(page, 'Charizard ex')
  await noThinContrast(page, 'card')
  await page.getByRole('button', { name: 'Pull' }).click()
  await noThinContrast(page, 'pulled')
})

/* "Position label: font-size >= 32px, tabular figures", wherever one is drawn.
 *
 * A HELPER RATHER THAN A CLOSURE INSIDE ONE TEST, because there are now two stylesheets
 * drawing a position label into this view — `.fulfillment-place` on the browse list and the
 * card panel, and `.card-locations-place-large` on a searched copy. The row of the table is
 * one row; a second copy of the probe below would be a second place for it to be relaxed. */
async function bigTabularPlaces(
  page: Page,
  where: string,
  selector = '.fulfillment-place',
): Promise<void> {
  {
    const places = view(page).locator(selector)
    const count = await places.count()
    expect(count, `${where}: no position label on screen`).toBeGreaterThan(0)

    for (let index = 0; index < count; index += 1) {
      const place = places.nth(index)
      /* EVERY PART OF THE LABEL, not just its container: the words and the figure are separate
         elements now, and a figure shrunk inside a 32px block is the regression the row of the
         table is about. The container's own size is measured first, then every span in it. */
      const sizes = await place.evaluate((node) => {
        const read = (element: Element) =>
          Number.parseFloat(window.getComputedStyle(element).fontSize)
        return [read(node), ...[...node.querySelectorAll('*')].map(read)]
      })
      for (const size of sizes) {
        expect(size, `${where}: position label ${index}`).toBeGreaterThanOrEqual(PLACE_FLOOR)
      }

      /* Tabular figures, measured rather than asserted from the font name.
       *
       * docs/DESIGN.md's reason for giving every number to Martian Mono is that a position
       * "must not shift width between cards — which a mono gives for free rather than by
       * remembering to set `tnum`". So the property to check is the width, not the family: a
       * probe carrying the label's own computed font renders two digit strings of equal
       * length and they must measure the same. This also survives the font failing to load,
       * because the fallback in the token is `monospace` and a proportional fallback is
       * exactly the regression worth catching. */
      const widths = await place.evaluate((node) => {
        /* MEASURED ON THE ELEMENT THAT CARRIES THE DIGITS. The label is drawn in parts now —
           the words in one span and the figure in another — so the font that renders `17` is
           the figure's, not the container's. A probe wearing the container's style would be
           measuring a string this screen never draws.

           AND `font-variant-numeric` IS COPIED, which the shorthand does not carry. The label
           is set in the display face with `tabular-nums` rather than in a mono, so a probe
           that dropped the property would report a proportional face and fail a screen that
           is fine. What is asserted is unchanged and is still the thing the table asks for:
           two digit strings of equal length measure the same width. */
        const digits = node.querySelector('.ff-place-num') ?? node
        const style = window.getComputedStyle(digits)
        const probe = document.createElement('span')
        probe.style.font = style.font
        probe.style.fontFamily = style.fontFamily
        probe.style.fontSize = style.fontSize
        probe.style.fontWeight = style.fontWeight
        probe.style.fontVariantNumeric = style.fontVariantNumeric
        probe.style.fontFeatureSettings = style.fontFeatureSettings
        probe.style.letterSpacing = style.letterSpacing
        probe.style.position = 'absolute'
        probe.style.whiteSpace = 'pre'
        document.body.appendChild(probe)
        const measure = (text: string) => {
          probe.textContent = text
          return probe.getBoundingClientRect().width
        }
        const out = { ones: measure('11111111'), mixed: measure('10473608') }
        probe.remove()
        return out
      })
      expect(
        Math.abs(widths.ones - widths.mixed),
        `${where}: label ${index} shifts width between digits, so it is not tabular`,
      ).toBeLessThan(0.5)
    }
  }
}

test(`every position label is at least ${PLACE_FLOOR}px and set in tabular figures`, async ({
  page,
}) => {
  await openList(page)
  await openEveryBox(page)
  await bigTabularPlaces(page, 'list')
  await openCard(page, 'Charizard ex')
  await bigTabularPlaces(page, 'card')
})

/* fulfiller.md finding 6 / the plan's item 8: at exactly 768px the two-column layout gave the
 * 380px photo column priority and left the 32px-floor position label ("Box 3 · Section 1 ·
 * Card 7") only ~300px to draw in, wrapping it to three cramped lines. NEITHER `WIDTHS` entry
 * above is 768 -- 1280 and 375 both miss it -- so this is a viewport this suite never took
 * before. The fix moved the two-column breakpoint to 900px (the ladder's own step, not a new
 * one); 768-899 now draws the place at the page's full width, the same single-column layout
 * the phone already uses. */
test('the position label does not wrap to three lines at 768px', async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 })
  // Browsed from a box, not from an order: `.fulfillment-place-large` is the single-card
  // panel's own class, unchanged by the Owed rebuild, and drawn on every card that flow opens
  // regardless of whether an order is waiting for it.
  await openList(page)
  await openCard(page, 'Charizard ex')
  const place = view(page).locator('.fulfillment-place-large')
  await expect(place).toBeVisible()
  const lines = await place.evaluate((node) => {
    const style = window.getComputedStyle(node)
    const lineHeight = parseFloat(style.lineHeight)
    return Math.round(node.getBoundingClientRect().height / lineHeight)
  })
  expect(lines, 'position label line count at 768px').toBeLessThanOrEqual(2)
})

/* THE COORDINATOR'S OWN CHECK ON THIS FIX: 820px is one of the three widths docs/DESIGN.md's
 * "Verifying a screen" section names, and a first attempt at this fix moved the breakpoint to
 * exactly 820px -- which measured fine on the store's ORDINARY labels and still wrapped to
 * three lines on the longest one the store can emit ("Box 9999 · Section 99 · Card 50000":
 * docs/specs/store-scaling.md's 50,000-card target, in one undeclared box with no dividers,
 * D10 -- so a single section holding that many cards is a real shape and not a fabricated
 * string). The breakpoint moved again, to 900 -- the ladder's own "a two-column body becomes
 * one" step -- specifically because 900 clears this label at two lines where 820 did not. */
test('the longest label the store can emit does not wrap to three lines at 820px', async ({
  page,
}) => {
  const MAX_LABEL = 'Box 9999 · Section 99 · Card 50000'
  // Drawn on an owed card's own copy now (`CardLocations`' `.card-locations-place-large`),
  // since that is the live path a long label reaches this screen through — the Owed section
  // draws every on-hand copy of a SKU, ranked, and the label is whatever the store composed
  // for that copy's position.
  const maxLabelPlan = {
    ...ONE_OPEN_ORDER_PLAN,
    stops: [
      {
        ...ONE_OPEN_ORDER_PLAN.stops[0]!,
        takes: [
          {
            ...ORDER_TAKE,
            copies: [{ ...ORDER_WALK_COPY, place: { ...ORDER_WALK_COPY.place, label: MAX_LABEL } }],
          },
        ],
      },
    ],
  }
  await page.setViewportSize({ width: 820, height: 1024 })
  await openList(page, [], { orders: ONE_OPEN_ORDER, plan: maxLabelPlan })
  const place = view(page).locator('.card-locations-place-large')
  await expect(place).toHaveText(MAX_LABEL)
  const lines = await place.evaluate((node) => {
    const style = window.getComputedStyle(node)
    const lineHeight = parseFloat(style.lineHeight)
    return Math.round(node.getBoundingClientRect().height / lineHeight)
  })
  expect(lines, 'maximal position label line count at 820px').toBeLessThanOrEqual(2)
})

/* mobile.md finding 3: a phone laid flat (844x390) kept the landing list at its narrow
 * `--ff-col` (720px) centered under an 844px-wide, 390px-tall viewport -- the width he has
 * the most of on the orientation where he has the least height to scroll through. This does
 * not claim the whole scroll problem is gone (a real side-by-side reflow is a larger change
 * than this batch), only that the column stops wasting the width it already has. */
test('the landing column widens in short landscape rather than staying at the narrow column width', async ({
  page,
}) => {
  await page.setViewportSize({ width: 844, height: 390 })
  await openList(page)
  const column = view(page).locator('.ff-column')
  const width = await column.evaluate((node) => node.getBoundingClientRect().width)
  expect(width, 'landing column width at 844x390').toBeGreaterThan(720)
})

/* Measured at two widths, and the narrow one is not padding on the test.
 *
 * This is the default view on his device, which the project has never said is a desktop —
 * D13 puts the OWNER in a desktop browser and says only that the two devices share one truth
 * through the server. Measured at 1280 alone, the photo cleared the floor with room to spare
 * while a 375px phone rendered it at 311px: under the floor, on the device most likely to be
 * his, invisible to a suite that only ever looked at one viewport. The 375 is an iPhone SE
 * and a mini, which is the narrowest thing worth designing for and the case that failed. */
const WIDTHS = [
  { name: 'desktop', width: 1280, height: 900 },
  { name: 'phone', width: 375, height: 812 },
]

for (const screen of WIDTHS) {
  test(`the card photo is at least ${PHOTO_FLOOR}px on its short edge — ${screen.name}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width: screen.width, height: screen.height })
    await openList(page)
    await openCard(page, 'Charizard ex')

    const painted = await paintedPhoto(page)
    // A broken image still has a layout box, so the box alone cannot say whether there is a
    // photograph in it. This is the difference between measuring a CSS rule and measuring a
    // card.
    expect(painted.natural, 'the photo did not decode, so nothing was measured').toBeGreaterThan(0)
    expect(
      Math.min(painted.width, painted.height),
      `painted short edge at ${screen.width}px`,
    ).toBeGreaterThanOrEqual(PHOTO_FLOOR)
  })

  test(`the floors hold on the card at ${screen.name} width`, async ({ page }) => {
    await page.setViewportSize({ width: screen.width, height: screen.height })
    await openList(page)
    await fatTargets(page, `${screen.name} list`)
    await openCard(page, 'Charizard ex')
    await noSmallText(page, `${screen.name} card`)
    await fatTargets(page, `${screen.name} card`)
  })
}

test(`every tap target is at least ${TARGET_FLOOR}x${TARGET_FLOOR}px and ${GAP_FLOOR}px from its neighbours`, async ({
  page,
}) => {
  await openList(page)
  await fatTargets(page, 'list')
  await openCard(page, 'Charizard ex')
  await fatTargets(page, 'card')
  await page.getByRole('button', { name: 'Pull' }).click()
  await fatTargets(page, 'pulled')
})

test('no destructive action and no route out is reachable from any screen of this view', async ({
  page,
}) => {
  const wire: Wire[] = []
  const mood: Mood = {}
  await openList(page, wire, mood)
  await noWayOut(page, 'list')

  await openCard(page, 'Charizard ex')
  await noWayOut(page, 'card')

  await page.getByRole('button', { name: 'Pull' }).click()
  await noWayOut(page, 'pulled')

  // And the view itself writes nothing until he presses the one thing it offers.
  expect(wire, 'the view wrote to the server without being asked').toEqual([])

  await page.getByRole('button', { name: 'Mark it sold' }).click()
  await expect(view(page)).toContainText('Marked sold.')
  await noWayOut(page, 'sold')
})

test(`undo is offered on every mark-sold and stays for at least ${UNDO_FLOOR_MS / 1000}s`, async ({
  page,
}) => {
  await page.clock.install()   // before the first navigation; see the note at the wait below
  const wire: Wire[] = []
  await openList(page, wire)

  await openCard(page, 'Charizard ex')
  await page.getByRole('button', { name: 'Pull' }).click()
  // The copy rule, asserted rather than assumed: the button that says Pull produces a
  // confirmation that says Pulled.
  await expect(view(page)).toContainText('Pulled.')

  await page.getByRole('button', { name: 'Mark it sold' }).click()
  await expect(view(page)).toContainText('Marked sold.')
  expect(wire.map((call) => call.undo), 'the sale reached the server as a sale').toEqual([false])
  expect(wire[0]!.url, 'the sale named the card').toContain('/inventory/3/7/sold')

  const undo = receiptFor(page, 'Box 3 · Section 1 · Card 7').getByRole('button', { name: 'Undo' })
  await expect(undo).toBeVisible()
  // The sold card leaves the list while the sale stands, and stays gone across the re-read
  // the sale triggers — the stub store moved with the sale, so this is the server agreeing.
  await expect(page.getByRole('button', { name: 'Charizard ex' })).toHaveCount(0)

  /* A FAKE CLOCK, ADVANCED PAST THE FLOOR, AND THIS COMMENT ARGUED THE OPPOSITE UNTIL
   * 2026-09-11 (D136). It said real time was the point: that the control has to survive ten
   * seconds of a React re-render, a timer and whatever else the page does, and that a fake
   * clock proves the arithmetic instead. The owner ruled the sleep may go, and the reasoning
   * that lets it go is that `runFor` fires EVERY timer the page holds inside the span — the
   * 500ms tick that redraws the receipt's seconds, the expiry timeout that would take the
   * control away, and each re-render those cause — in order, with `Date.now()` moving in step.
   * What it no longer proves is that wall time passes, and that is the browser's promise, not
   * this screen's. The clock starts at the real time and is never set, only advanced, so the
   * dates this view draws are today's. Mutation-tested: with the window cut to five seconds in
   * Fulfillment.tsx this assertion fails on the faked wait exactly as it did on the real one. */
  await page.clock.runFor(UNDO_FLOOR_MS + 500)
  await expect(undo, `undo left before ${UNDO_FLOOR_MS}ms`).toBeVisible()

  await undo.click()
  // It undoes: the sale is withdrawn at the server and the card is back where he can find it.
  await expect(page.getByRole('button', { name: 'Charizard ex' })).toBeVisible()
  // A sale then a reversal, in that order, on the one route that takes both.
  expect(wire.map((call) => call.undo), 'the withdrawal reached the server').toEqual([false, true])
  // Back in box-walk order rather than appended: he walks the boxes in this order.
  await expectWalk(page, WALK)
})

/* "Undo present on EVERY mark-sold" — the word that was not honoured, and the two ways it
 * was not. A real order pull is two or three cards in a row, so both of these are the
 * ordinary flow rather than an edge case.
 */

test('a second sale does not take the first sale undo away', async ({ page }) => {
  const wire: Wire[] = []
  await openList(page, wire)

  await openCard(page, 'Charizard ex')
  await sellOpenCard(page)
  await expect(receiptFor(page, 'Box 3 · Section 1 · Card 7')).toBeVisible()

  await openCard(page, 'Iono')
  await sellOpenCard(page)

  // Both receipts stand, each with its own Undo. One slot held one of these and dropped the
  // other with no trace, on a screen whose only other route to recovery is the owner.
  const first = receiptFor(page, 'Box 3 · Section 1 · Card 7')
  const second = receiptFor(page, 'Box 1 · Section 1 · Card 3')
  await expect(first.getByRole('button', { name: 'Undo' })).toBeVisible()
  await expect(second.getByRole('button', { name: 'Undo' })).toBeVisible()

  // The older one still works, and reaches the server for the card it names rather than for
  // the most recent sale.
  await first.getByRole('button', { name: 'Undo' }).click()
  await expect(page.getByRole('button', { name: 'Charizard ex' })).toBeVisible()
  expect(wire.at(-1)!.undo, 'the last call was a reversal').toBe(true)
  expect(wire.at(-1)!.url, 'the reversal named the older card').toContain('/inventory/3/7/sold')
  // And the newer sale is untouched: still sold, still offering its own undo.
  await expect(page.getByRole('button', { name: 'Iono' })).toHaveCount(0)
  await expect(second.getByRole('button', { name: 'Undo' })).toBeVisible()
})

test('the undo is still there after walking into another card', async ({ page }) => {
  const wire: Wire[] = []
  await openList(page, wire)

  await openCard(page, 'Charizard ex')
  await sellOpenCard(page)
  const receipt = receiptFor(page, 'Box 3 · Section 1 · Card 7')
  await expect(receipt.getByRole('button', { name: 'Undo' })).toBeVisible()

  // The card panel used to return before the receipt was rendered, so this navigation hid the
  // control while its clock kept running — a ten-second promise visible for two of them.
  await openCard(page, 'Pidgeot ex')
  await expect(receipt.getByRole('button', { name: 'Undo' })).toBeVisible()
  await battery(page, 'receipt over the card panel')

  await receipt.getByRole('button', { name: 'Undo' }).click()
  expect(wire.at(-1)!.url, 'the reversal named the sold card').toContain('/inventory/3/7/sold')
  await expect(receipt).toHaveCount(0)
})

/* `restores_to`, which the route computes deliberately and which reached no screen: the wire
 * typed the answer as `{ position }` and this view typed its own wrapper as `Promise<void>`.
 * The Undo was then drawn unconditionally, and pressing it on a card the server had already
 * said it could not restore produced an instruction that fails identically forever.
 */

test('a sale the server cannot reverse offers no undo, and says why', async ({ page }) => {
  const wire: Wire[] = []
  const mood: Mood = {
    // `history.jsonl` holds no earlier state for this card, so the route answers the sale with
    // `restores_to: null` — the advance warning that a reversal would refuse.
    sold: (undo, key) => ({
      status: 200,
      body: { position: key, undone: undo, restores_to: null },
    }),
  }
  await openList(page, wire, mood)

  await openCard(page, 'Charizard ex')
  await sellOpenCard(page)

  const receipt = receiptFor(page, 'Box 3 · Section 1 · Card 7')
  await expect(receipt).toContainText('Marked sold.')
  await expect(
    receipt.getByRole('button', { name: 'Undo' }),
    'an undo was offered for a sale the server said it cannot reverse',
  ).toHaveCount(0)
  await expect(receipt).toContainText('You cannot take this one back here.')
  await battery(page, 'sale with no undo')
})

test('an undo the server refuses with no remedy stops asking', async ({ page }) => {
  const wire: Wire[] = []
  const mood: Mood = {
    /* The sale reports a reversible card and the reversal then refuses anyway — the race the
     * advance warning above cannot cover, and the one the old copy handled worst: the message
     * said press Undo again, and pressing it again answered the same way, forever, on the one
     * screen with nobody in the room. */
    sold: (undo, key) =>
      undo
        ? refuses(
            'sold_origin_unknown',
            'Box 3, card 7 is sold, but history.jsonl records no earlier state for it.',
          )
        : { status: 200, body: { position: key, undone: false, restores_to: 'identified' } },
  }
  await openList(page, wire, mood)

  await openCard(page, 'Charizard ex')
  await sellOpenCard(page)

  const receipt = receiptFor(page, 'Box 3 · Section 1 · Card 7')
  await receipt.getByRole('button', { name: 'Undo' }).click()

  await expect(receipt).toContainText('This card stays sold. Ask for help to put it back.')
  await expect(
    receipt.getByRole('button', { name: 'Undo' }),
    'the screen still asks him to press a control that answers the same way every time',
  ).toHaveCount(0)
  // None of the server's own words, which name a file and a state.
  await expect(view(page)).not.toContainText('sold_origin_unknown')
  await expect(view(page)).not.toContainText('history.jsonl')
  await battery(page, 'undo refused')
})

/* The other device (D13), which is the reason the list is read again at all.
 */

test('a card the other device already sold is not this device sale, and gets no undo', async ({
  page,
}) => {
  const wire: Wire[] = []
  const store = await openList(page, wire)

  // The other device sells it while his list is on screen. Nothing tells him.
  store['3/7'] = 'sold'

  await openCard(page, 'Charizard ex')
  await sellOpenCard(page)

  /* Answered as success this printed "Marked sold." and offered an Undo — and that Undo would
   * have reached the server and reversed somebody else's real sale, putting a card a buyer has
   * paid for back on TCGplayer. It is a receipt for a card leaving his list, not for anything
   * he did, so it says so and offers nothing to press. */
  const receipt = receiptFor(page, 'Box 3 · Section 1 · Card 7')
  await expect(receipt).toContainText('Already sold.')
  await expect(receipt).toContainText('Somebody else sold this card')
  await expect(view(page), 'a sale this device did not make was reported as one').not.toContainText(
    'Marked sold.',
  )
  await expect(
    receipt.getByRole('button', { name: 'Undo' }),
    'an undo of the other device real sale was on screen',
  ).toHaveCount(0)

  // One call, and never a reversal. This is the assertion the bug would have failed.
  expect(wire.map((call) => call.undo)).toEqual([false])
  // And the card is off his list, because the re-read agreed with the refusal.
  await expect(page.getByRole('button', { name: 'Charizard ex' })).toHaveCount(0)
  await expect(view(page)).not.toContainText('already_sold')
  await battery(page, 'already sold elsewhere')
})

test('an undo of a sale the other device already reversed reads as done', async ({ page }) => {
  const wire: Wire[] = []
  const store = await openList(page, wire)

  await openCard(page, 'Charizard ex')
  await sellOpenCard(page)
  const receipt = receiptFor(page, 'Box 3 · Section 1 · Card 7')
  await expect(receipt.getByRole('button', { name: 'Undo' })).toBeVisible()

  // The other device puts it back first. `not_sold` then means the card is in the state the
  // tap asked for, which is the one refusal this screen may read as success.
  store['3/7'] = 'identified'
  await receipt.getByRole('button', { name: 'Undo' }).click()

  await expect(page.getByRole('button', { name: 'Charizard ex' })).toBeVisible()
  await expect(receipt).toHaveCount(0)
  await expect(view(page)).not.toContainText('not_sold')
})

test('the cards are read again when he comes back to them, and after a sale', async ({ page }) => {
  const wire: Wire[] = []
  const mood: Mood = {}
  await openList(page, wire, mood)
  await expect(await cardRow(page, 'Charizard ex')).toBeVisible()

  const beforeWalk = mood.reads ?? 0
  await openCard(page, 'Charizard ex')
  await page.getByRole('button', { name: 'Back to the cards' }).click()
  await expect
    .poll(() => mood.reads ?? 0, { message: 'the list was not read again on the way back' })
    .toBeGreaterThan(beforeWalk)

  const beforeSale = mood.reads ?? 0
  await openCard(page, 'Charizard ex')
  await sellOpenCard(page)
  await expect(view(page)).toContainText('Marked sold.')
  await expect
    .poll(() => mood.reads ?? 0, { message: 'the list was not read again after the sale' })
    .toBeGreaterThan(beforeSale)

  // The re-read is the point: the sold card does not come back on the answer that follows it.
  await expect(page.getByRole('button', { name: 'Charizard ex' })).toHaveCount(0)
})

/* The step that is one tap from a recorded sale.
 */

test('the sale is not one tap of overshoot from the pull', async ({ page }) => {
  await openList(page)
  await openCard(page, 'Charizard ex')

  /* BOTH RECTS ARE READ AT REST. The panel enters on `bn-page-in` and the control that replaces
     Pull pops in on a spring, so a rect read while either is running is a frame of an animation
     and not a place a finger can land — measured on Playwright 1.58.0's Chromium: Pull's width
     read 427px in one run and 403px in the next, on identical code, and the overlap this case
     forbids appeared in two runs of five. `settleLayout` was built for this rule's own case
     (its comment says so) and this test was one of the two that never called it. */
  await settleLayout(page)
  const pull = await boxOf(page.getByRole('button', { name: 'Pull' }))
  await page.getByRole('button', { name: 'Pull' }).click()
  await settleLayout(page)
  const sell = await boxOf(page.getByRole('button', { name: 'Mark it sold' }))

  /* Pull and Mark sold were one control in one place, one state apart. A finger that lands
   * twice — the ordinary way a person presses a button that did not seem to respond — pulled
   * the card and sold it, with a photo he never looked at. Measured rather than argued: the
   * second control may not occupy any part of the first one's footprint. */
  expect(
    overlaps(pull, sell),
    `Mark sold overlaps where Pull was, so a double-tap on Pull sells the card — pull ${JSON.stringify(pull)}, sale ${JSON.stringify(sell)}`,
  ).toBe(false)
  expect(sell.y, 'Mark sold begins above where Pull ended').toBeGreaterThanOrEqual(
    pull.y + pull.height,
  )
})

/* Every screen that is not the list or the card panel. Each was reachable and unmeasured.
 */

test('the copy carries no word from the system this is built out of', async ({ page }) => {
  await openList(page)
  await noJargon(page, 'list')
  await openCard(page, 'Charizard ex')
  await noJargon(page, 'card')
  await page.getByRole('button', { name: 'Pull' }).click()
  await noJargon(page, 'pulled')
  await page.getByRole('button', { name: 'Mark it sold' }).click()
  await expect(view(page)).toContainText('Marked sold.')
  await noJargon(page, 'sold')
})

test('the ordinary flow passes the whole table at every step', async ({ page }) => {
  await openList(page)
  await battery(page, 'list')
  await openCard(page, 'Charizard ex')
  await battery(page, 'card')
  await page.getByRole('button', { name: 'Pull' }).click()
  await battery(page, 'pulled')
  await page.getByRole('button', { name: 'Mark it sold' }).click()
  await expect(view(page)).toContainText('Marked sold.')
  await battery(page, 'sold')
})

test('the screen while the cards load is his too', async ({ page }) => {
  await stubServer(page, [], { slow: true })
  await page.goto(VIEW_ROUTE)
  await settleFonts(page)
  await expect(view(page)).toContainText('Getting the cards.')
  // The one screen that offers nothing to press, and the only call site that says so.
  await battery(page, 'loading', false)
  // And it does end. A loading state nothing clears is a broken screen that measures clean.
  await expect(await cardRow(page, 'Charizard ex')).toBeVisible()
})

test('the screen when the cards do not load is his too, and trying again works', async ({
  page,
}) => {
  const mood: Mood = { fail: true }
  await stubServer(page, [], mood)
  await page.goto(VIEW_ROUTE)
  await settleFonts(page)

  // What happened, and what to do next — in his words, and none of the server's.
  await expect(view(page)).toContainText('The cards did not load. Try again.')
  await expect(view(page)).not.toContainText('store_unreadable')
  await expect(view(page)).not.toContainText('inventory.json')

  await battery(page, 'load failed')

  // "Try again" tries again. A remedy that does not work is worse than none, because it is
  // the one he will press repeatedly before asking anyone.
  mood.fail = false
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(await cardRow(page, 'Charizard ex')).toBeVisible()
})

test('a body this screen cannot read fails the same way a dead server does', async ({ page }) => {
  /* The loader answered failures with `.then(ok, fail)`, which does not cover its own success
   * handler: a 200 whose body has no `cards` threw inside it, became an unhandled rejection,
   * and left the screen on "Getting the cards." with nothing shown and nothing to press. */
  await page.route(/\/inventory$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 1 }),
    })
  })
  /* THE LEDGER TOO, BECAUSE THIS CASE NAVIGATES ITSELF RATHER THAN GOING THROUGH `openList`.
     `Fulfillment.tsx` reads both on mount; only the one this case is about was stubbed, so the
     other went to the capture port — the owner's real ledger in the main checkout, on the one
     screen in this product a second person looks at. Named by `sealEveryTest`. */
  await page.route(/\/orders$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(NO_ORDERS) })
  })
  await page.goto(VIEW_ROUTE)
  await settleFonts(page)

  await expect(view(page)).toContainText('The cards did not load. Try again.')
  await expect(view(page), 'the screen is still waiting for an answer it already had').not.toContainText(
    'Getting the cards.',
  )
  await battery(page, 'unreadable body')
})

test('the screen with nothing to pull is his too', async ({ page }) => {
  await openList(page, [], { empty: true })
  await expect(view(page)).toContainText('No cards are for sale right now.')
  // No rows, so no controls except the ones the shell might draw — which is zero, and
  // `noWayOut` inside the battery is what says so.
  await battery(page, 'nothing to pull', false)
})

test('the screen when the photo is missing is his too', async ({ page }) => {
  await openList(page, [], { noPhoto: true })
  await (await cardRow(page, 'Charizard ex')).click()

  // The photo is gone and the card is not, so the screen says where it still is.
  await expect(view(page)).toContainText('The photo is missing. The card is still in the place shown here.')
  await expect(view(page).locator('.fulfillment-photo')).toHaveCount(0)
  // D218: the seam is CSS now (`.ff-place-elem::before`), never part of `textContent`.
  await expect(view(page)).toContainText('Box 3Section 1Card 7')
  await battery(page, 'photo missing')
})

test('a refusal says what happened and what to do, in his words', async ({ page }) => {
  const wire: Wire[] = []
  const mood: Mood = {
    sold: () => refuses('store_busy', 'The staged import is locked; retry after batch.'),
  }
  await openList(page, wire, mood)

  await openCard(page, 'Charizard ex')
  await sellOpenCard(page)

  // What happened, and what to do next.
  await expect(view(page)).toContainText('Nothing was saved. Press Mark it sold again.')
  // The card is still his to sell, because nothing was recorded.
  await expect(page.getByRole('button', { name: 'Mark it sold' })).toBeVisible()
  // And none of the server's words are on screen — neither the code nor the sentence.
  await expect(view(page)).not.toContainText('store_busy')
  await expect(view(page)).not.toContainText('locked')
  await battery(page, 'sale refused')
})

test('a failed re-read keeps the cards he has and says the list may have moved', async ({
  page,
}) => {
  const mood: Mood = {}
  await openList(page, [], mood)
  await expect(await cardRow(page, 'Charizard ex')).toBeVisible()

  // The Mac goes to sleep between the first read and the walk back to the list.
  mood.fail = true
  await openCard(page, 'Charizard ex')
  await page.getByRole('button', { name: 'Back to the cards' }).click()

  await expect(view(page)).toContainText('These cards may have changed since they were last checked.')
  // The list he was using is still there. Taking it away because a re-read did not answer
  // leaves him with less than he had.
  await expect(await cardRow(page, 'Charizard ex')).toBeVisible()
  await battery(page, 'stale list')

  mood.fail = false
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(view(page)).not.toContainText('These cards may have changed')
})

test('the failed-undo message leaves with the undo it tells him to press', async ({ page }) => {
  test.setTimeout(90_000)
  const wire: Wire[] = []
  const mood: Mood = {
    sold: (undo, key) =>
      undo
        ? refuses('store_busy', 'The staged import is locked; retry after batch.')
        : { status: 200, body: { position: key, undone: false, restores_to: 'identified' } },
  }
  await openList(page, wire, mood)

  await openCard(page, 'Charizard ex')
  await sellOpenCard(page)
  const receipt = receiptFor(page, 'Box 3 · Section 1 · Card 7')
  await receipt.getByRole('button', { name: 'Undo' }).click()

  /* Held in screen-wide state, this sentence outlived the control it named: the window closed,
   * the panel went, and the instruction stayed on screen pointing at a button that was no
   * longer there. The structural half of the fix is asserted first — the sentence is INSIDE
   * the panel that carries the Undo, so neither can outlive the other by construction. */
  await expect(receipt).toContainText('The card did not come back. Press Undo again.')
  await expect(receipt.getByRole('button', { name: 'Undo' })).toBeVisible()

  // And then the window really closes, in real time, and they go together.
  await expect(view(page).locator('.fulfillment-panel')).toHaveCount(0, { timeout: 60_000 })
  await expect(view(page)).not.toContainText('The card did not come back')
})

/* ------------------------------------------------------------------ finding a card by name
 *
 * THE TABLE BINDS THIS PATH EXACTLY AS HARD AS THE WALK. The row that says "every text node in
 * the view" says the view, not the screen that was easy to reach — which is the lesson this
 * file already records once, about the loading screen and the empty list going unmeasured for
 * as long as the walks only visited two screens. The search is four more screens: results,
 * no match, the search that did not answer, and a copy past its first step. Each is below.
 *
 * WHY IT EXISTS AT ALL, since a test file should say what it is defending. The store holds 229
 * cards, 176 of them with no name recorded, in box-walk order, with no photo on the row and no
 * filter over it. Reading down that list to find the card an order names is not a thing this
 * person can be asked to do, and the copy above `sellable` in Fulfillment.tsx called it a
 * haystack in as many words.
 */

/** Every photo in a search result, load attempted.
 *
 *  VISIBLE IS NOT DECODED, the same flake `openCard` records: `naturalWidth` reads 0 on a
 *  wide viewport while the identical measurement on a phone reads a true number. This waits
 *  for `complete`, which is the browser saying the attempt finished — and deliberately not for
 *  success, because a broken image is `complete` with a natural size of zero and that is the
 *  state the photo assertion has to be able to fail on. */
async function settlePhotos(page: Page): Promise<void> {
  const photos = view(page).locator('.card-locations-photo')
  const count = await photos.count()
  for (let index = 0; index < count; index += 1) {
    await photos.nth(index).evaluate(
      (node) =>
        new Promise<void>((settled) => {
          const img = node as HTMLImageElement
          if (img.complete) {
            settled()
            return
          }
          img.addEventListener('load', () => settled(), { once: true })
          img.addEventListener('error', () => settled(), { once: true })
        }),
    )
  }
}

/** The two copies of the fixture's one repeated card, in box-walk order. */
const EISCUE = ['Box 2 · Section 1 · Card 9', 'Box 4 · Section 1 · Card 2']
const [EISCUE_FIRST, EISCUE_SECOND] = EISCUE as [string, string]

test('the search narrows to the copies of one card, and clearing it gives the whole walk back', async ({
  page,
}) => {
  await openSearch(page, 'Eiscue', 2)

  // Narrowed, not sat beside: the walk is not on screen while a name is in the field.
  await expect(view(page).locator('.fulfillment-row')).toHaveCount(0)
  await expect(view(page).locator('.card-locations-place-large')).toHaveText(EISCUE)

  /* THE HALF THAT MATTERS MOST, because it is what the owner asked for by name: clearing the
   * field gives him back exactly the list he had before this session existed. A search that
   * cost him the walk would be a feature that took one away, on the one screen nobody has ever
   * watched him use. */
  await page.getByRole('button', { name: 'Show every card' }).click()
  await expect(searchBox(page), 'the field kept the name after showing every card').toHaveValue('')
  await expectWalk(page, WALK)
  await expect(view(page).locator('.card-locations-copy')).toHaveCount(0)

  // And emptying the field by hand is the same door. Two ways out, one destination.
  await searchBox(page).fill('Eiscue')
  await showEveryCopy(page)
  await expect(view(page).locator('.card-locations-copy')).toHaveCount(2)
  await searchBox(page).fill('')
  await expectWalk(page, WALK)
})

test('every copy the search finds is its own card, with its own photo, place, bar and action', async ({
  page,
}) => {
  /* The owner's ruling, asserted rather than described: a card with copies in four places
   * gives him four cards to scroll, so he walks to whichever slot is nearest. Copies are
   * fungible (D7), so the choice is his — and a screen that picked one for him is wrong every
   * time the box it picked is the one across the room. */
  await openSearch(page, 'Eiscue', 2)
  await settlePhotos(page)

  await expect(view(page).locator('.card-locations-copy .card-locations-photo')).toHaveCount(2)
  await expect(view(page).locator('.card-locations-copy .position-bar')).toHaveCount(2)
  await expect(view(page).getByRole('button', { name: 'Pull' })).toHaveCount(2)

  // One of the two is `captured` and the other `identified`. Both are on screen, which is D7's
  // "every unsold copy is sellable" — there is no per-position listing flag left to filter on.
  for (const place of EISCUE) {
    const card = copyCard(page, place)
    await expect(card.locator('.card-locations-photo')).toHaveCount(1)
    await expect(card.getByRole('button', { name: 'Pull' })).toBeVisible()
  }
})

test('the sale is not one tap of overshoot from the pull, on a search result too', async ({
  page,
}) => {
  await openSearch(page, 'Eiscue', 2)
  const card = copyCard(page, EISCUE_FIRST)

  const pull = await boxOf(card.getByRole('button', { name: 'Pull' }))
  await card.getByRole('button', { name: 'Pull' }).click()
  const sell = await boxOf(card.getByRole('button', { name: 'Mark it sold' }))

  /* `CardLocations` gives every copy a single one-press "Mark sold" and says in its own header
   * that the overshoot is the thing it does not cover. This is the cover: the same two steps in
   * the same two places the card panel uses, wired in through `renderAction`. A finger that
   * lands twice — the ordinary way a person presses a button that did not seem to respond —
   * must not sell the card, so the second control may not occupy any part of the first one's
   * footprint. Measured, not argued. */
  expect(
    overlaps(pull, sell),
    `Mark sold overlaps where Pull was, so a double-tap on Pull sells the card — pull ${JSON.stringify(pull)}, sale ${JSON.stringify(sell)}`,
  ).toBe(false)
  expect(sell.y, 'Mark sold begins above where Pull ended').toBeGreaterThanOrEqual(
    pull.y + pull.height,
  )
})

test('only one copy is ever past its first step, so only one fill is on screen', async ({
  page,
}) => {
  /* docs/DESIGN.md reserves the solid accent for a screen with exactly one thing to do. A
   * search can put four copies of one card on screen, so the rule has to survive that: pulling
   * a second copy moves the pull rather than adding a second loud button. */
  await openSearch(page, 'Eiscue', 2)
  await expect(view(page).locator('.pull-confirm')).toHaveCount(0)

  await copyCard(page, EISCUE_FIRST).getByRole('button', { name: 'Pull' }).click()
  await expect(view(page).locator('.pull-confirm')).toHaveCount(1)

  await copyCard(page, EISCUE_SECOND).getByRole('button', { name: 'Pull' }).click()
  await expect(view(page).locator('.pull-confirm')).toHaveCount(1)
  await expect(copyCard(page, EISCUE_SECOND)).toContainText('Pulled.')
  // And the first copy has gone back to offering its first step.
  await expect(copyCard(page, EISCUE_FIRST)).not.toContainText('Pulled.')
  await expect(copyCard(page, EISCUE_FIRST).getByRole('button', { name: 'Pull' })).toBeVisible()
})

/* D218: this card's own `.card-locations-place-large` paragraph keeps the server's raw
 * `Position.label` on purpose — `PositionLabel.tsx`'s header names this firewall and
 * `docs/DESIGN.md`'s hard floors are why it stays untouched. The two ACCESSIBLE NAMES this
 * same card carries are not that paragraph: the photo's `alt` (`CardLocations.tsx:FulfillerCard`)
 * and the Pull button's `aria-label` (`Fulfillment.tsx:actionFor`) each compose a SENTENCE
 * around the label, and neither has a `::before` to draw a separator with — both read through
 * `sayPlace` before they reach a screen reader. */
test('the card speaks its place without the server\'s middle dot, in what a screen reader hears', async ({
  page,
}) => {
  await openSearch(page, 'Eiscue', 2)

  const card = copyCard(page, EISCUE_FIRST)
  const photoAlt = await card.locator('img.card-locations-photo').getAttribute('alt')
  expect(photoAlt).not.toMatch(/[·•]/)
  expect(photoAlt).toBe(`The card in ${EISCUE_FIRST.replace(/ · /g, ', ')}`)

  const pullName = await card.getByRole('button', { name: 'Pull' }).getAttribute('aria-label')
  expect(pullName).not.toMatch(/[·•]/)
  expect(pullName).toBe(`Pull ${EISCUE_FIRST.replace(/ · /g, ', ')}`)

  // AND THE DISPLAYED PARAGRAPH IS UNTOUCHED — the one exception this sweep leaves alone.
  await expect(card.locator('.card-locations-place-large')).toHaveText(EISCUE_FIRST)
})

test(`a copy sold from a search result leaves both lists, and keeps its undo for ${UNDO_FLOOR_MS / 1000}s`, async ({
  page,
}) => {
  await page.clock.install()   // before the first navigation, as in the list case above
  const wire: Wire[] = []
  await openSearch(page, 'Eiscue', 2, wire)

  await sellCopy(page, EISCUE_FIRST)

  // The sale names the copy, not the card: D7 keeps a position per copy precisely so that a
  // pull can mark ONE of them and leave the rest alone.
  expect(wire.map((call) => call.undo), 'the sale reached the server as a sale').toEqual([false])
  expect(wire[0]!.url, 'the sale named the copy he pulled').toContain('/inventory/2/9/sold')

  /* IT LEAVES THE SEARCH RESULT. The copies in hand were fetched before the sale and cannot
   * know about it, and `CardLocations` draws each copy's own state from the wire — so a copy
   * left standing would read "In the boxes." beside a receipt reading "Marked sold.", which is
   * the screen contradicting itself in front of the one person who cannot ask which half is
   * true. The other copy stays: it is a different physical card. */
  await expect(copyCard(page, EISCUE_FIRST)).toHaveCount(0)
  await expect(copyCard(page, EISCUE_SECOND)).toBeVisible()

  const undo = receiptFor(page, EISCUE_FIRST).getByRole('button', { name: 'Undo' })
  await expect(undo, 'a sale made from a search result was offered no undo').toBeVisible()

  // And it leaves the walk underneath, which is the same physical card seen the other way in.
  await page.getByRole('button', { name: 'Show every card' }).click()
  await expectWalk(page, WALK.filter((place) => place !== EISCUE_FIRST))

  /* The same fake clock as the list case, for the same reason (D136), and the receipt has
   * survived clearing the search since it is rendered above every screen this view has. The
   * window is a promise to a person who has just put a card in an envelope and looked up. */
  await page.clock.runFor(UNDO_FLOOR_MS + 500)
  await expect(undo, `undo left before ${UNDO_FLOOR_MS}ms`).toBeVisible()

  await undo.click()
  expect(wire.map((call) => call.undo), 'the withdrawal reached the server').toEqual([false, true])
  await expectWalk(page, WALK)

  // And back into the search results too, because it is back in the boxes.
  await searchBox(page).fill('Eiscue')
  await showEveryCopy(page)
  await expect(view(page).locator('.card-locations-place-large')).toHaveText(EISCUE)
})

test('the ordinary search passes the whole table at every step', async ({ page }) => {
  await openSearch(page, 'Eiscue', 2)
  await battery(page, 'search results')

  await copyCard(page, EISCUE_FIRST).getByRole('button', { name: 'Pull' }).click()
  await expect(copyCard(page, EISCUE_FIRST)).toContainText('Pulled.')
  await battery(page, 'search pulled')

  await copyCard(page, EISCUE_FIRST).getByRole('button', { name: 'Mark it sold' }).click()
  await expect(view(page)).toContainText('Marked sold.')
  await battery(page, 'search sold')
})

test(`every position label in a search result is at least ${PLACE_FLOOR}px and tabular`, async ({
  page,
}) => {
  await openSearch(page, 'Eiscue', 2)
  await bigTabularPlaces(page, 'search results', '.card-locations-place-large')
})

for (const screen of WIDTHS) {
  test(`a searched copy's photo is at least ${PHOTO_FLOOR}px on its short edge — ${screen.name}`, async ({
    page,
  }) => {
    /* The phone is the case this row keeps failing on, and it failed here too before the
     * stylesheet was changed for it: the group's own bordered box and the copy's, nested,
     * spend 96px of a 375px screen on padding and left the photo at 227px. Measured at 1280
     * alone it cleared the floor with room to spare — which is the shape of the miss this
     * whole two-width loop exists for. */
    await page.setViewportSize({ width: screen.width, height: screen.height })
    await openSearch(page, 'Eiscue', 2)
    await settlePhotos(page)

    const painted = await paintedPhoto(page, '.card-locations-photo')
    // A broken image still has a layout box, so the box alone cannot say whether there is a
    // photograph in it — the difference between measuring a CSS rule and measuring a card.
    expect(painted.natural, 'the photo did not decode, so nothing was measured').toBeGreaterThan(0)
    expect(
      Math.min(painted.width, painted.height),
      `painted short edge at ${screen.width}px`,
    ).toBeGreaterThanOrEqual(PHOTO_FLOOR)

    await noSmallText(page, `${screen.name} search`)
    await fatTargets(page, `${screen.name} search`)
  })
}

test('the screen with no card of that name is his too', async ({ page }) => {
  await openList(page)
  await searchBox(page).fill('Zamazenta')

  // What is true, and the one thing he can do about it. No count, no "0 results", no empty
  // panel — none of those tell him anything he can act on.
  await expect(view(page)).toContainText('No card here has that name. Check the spelling.')
  await battery(page, 'no match')

  // And the way out is still there, which is the whole reason it sits above the results.
  await page.getByRole('button', { name: 'Show every card' }).click()
  await expectWalk(page, WALK)
})

/* UX-049: the old sentence, "Type the name again," was a remedy that cannot work — the
 * search FAILED, and retyping asks the same broken thing again. It also read the same for a
 * real failure and for a genuine no-match ("zzzz"), which `found.total === 0`'s own branch
 * already answers correctly and is untouched here. The fix says the search itself could not
 * run and points at the one control on screen that helps: clearing it. */
test('a search that cannot run says so and offers a step that helps, in his words', async ({
  page,
}) => {
  const mood: Mood = { searchFail: true }
  await openList(page, [], mood)
  await searchBox(page).fill('Eiscue')

  await expect(view(page)).toContainText(
    'The search could not run right now. Clear it to look through a box instead.',
  )
  /* None of the server's own words. `useSearch` hands this screen a `Failure` carrying the
   * server's sentence and its code, and `server.ts:describeFailure` says in its own comment
   * that this view does not use it — those strings name a file and a state, and every one of
   * them is correct and none of them is his. */
  await expect(view(page)).not.toContainText('store_unreadable')
  await expect(view(page)).not.toContainText('inventory.json')
  await battery(page, 'search failed')

  /* And the remedy is a real one. A sentence telling him to type the name again, on a screen
   * where typing the name again cannot work, is worse than no sentence — it is the one he will
   * follow repeatedly before asking anyone. */
  mood.searchFail = false
  await searchBox(page).fill('Eiscu')
  await showEveryCopy(page)
  await expect(view(page).locator('.card-locations-place-large')).toHaveText(EISCUE)
})

test('a refused sale from a search result says so beside the control it names', async ({
  page,
}) => {
  const mood: Mood = {
    sold: () => refuses('store_busy', 'The staged import is locked; retry after batch.'),
  }
  await openSearch(page, 'Eiscue', 2, [], mood)
  await sellCopy(page, EISCUE_FIRST)

  /* THE SENTENCE IS ON THE COPY HE PRESSED, not at the top of a list he has scrolled past.
   * `trouble` is screen-wide state and the browse list draws it under the heading, which is
   * right there and wrong here — a search can be four copies long, and an instruction to press
   * a button he cannot see is an instruction to press nothing. */
  const card = copyCard(page, EISCUE_FIRST)
  await expect(card).toContainText('Nothing was saved. Press Mark it sold again.')
  await expect(card.getByRole('button', { name: 'Mark it sold' })).toBeVisible()

  // Nothing was recorded, so the copy did not leave either list.
  await expect(view(page).locator('.card-locations-copy')).toHaveCount(2)
  await expect(view(page)).not.toContainText('Marked sold.')
  // And none of the server's words are on screen — neither the code nor the sentence.
  await expect(view(page)).not.toContainText('store_busy')
  await expect(view(page)).not.toContainText('locked')
  await battery(page, 'search sale refused')
})

/* ------------------------------------------------------------------ pooled, not located
 *
 * The owner's ruling ("Code cards are pooled inventory, not located", docs/DECISIONS.md;
 * `pipeline/games.py`'s `located` flag) asks for exactly this assertion by name: non-located
 * cards never enter the Fulfillment view or the pull flow, "asserted in
 * app/tests/fulfillment.spec.ts rather than left to prose". A pooled card is a count with
 * no box, section or card position — there is nothing for this screen to send him to — and
 * the server keeps serving its row everywhere because the OWNER's screens still count and
 * search it, so the view is what filters, and the view is what this measures.
 */

test('a pooled card is never on his screen — not on the walk, not in a search, not in a count', async ({
  page,
}) => {
  await openList(page)

  /* THE BROWSE. `5/2` is unsold, photographed and named, and must be nowhere: not a row
   * (the walk is asserted whole, so an extra row fails above too), not its name, not the
   * pooled fact's words — and NOT in the unplaced count, which stays at the one
   * coerce-failure row. That count's sentence ends "Ask for help", and a pooled card is
   * working as designed: counting it there sends someone to fix nothing. */
  await expectWalk(page, WALK)
  await expect(view(page)).not.toContainText('Trade Token')
  await expect(view(page)).not.toContainText('pooled')
  await expect(view(page)).toContainText('1 card for sale is not shown here')

  /* THE SEARCH — the second way in, held to the same rule. The stub serves the pooled
   * card's group exactly as `GET /search` would (the server filters nothing), so what this
   * measures is the view dropping it: no copy card, no photo, no Pull, no position bar,
   * and no fill anywhere on the screen. */
  await searchBox(page).fill('Trade Token')
  await expect(view(page)).toContainText(
    'That card is not kept in the boxes, so there is nothing to pull.',
  )
  await expect(view(page).locator('.card-locations-copy')).toHaveCount(0)
  await expect(view(page).getByRole('button', { name: 'Pull' })).toHaveCount(0)
  await expect(view(page).locator('.position-bar')).toHaveCount(0)
  /* Not the sold sentence: "every copy is sold" is a lie about a card that was never in
   * the boxes, and the difference matters to the person who reads it — sold means gone,
   * this means never his. */
  await expect(view(page)).not.toContainText('Every copy of that card is sold.')

  /* And the sentence he does see is held to the whole table, like every other screen. */
  await battery(page, 'pooled search')

  // The way back is intact, and the walk comes back without the pooled card, as always.
  await page.getByRole('button', { name: 'Show every card' }).click()
  await expectWalk(page, WALK)
})

test('a copy sold here since the count is said in his words', async ({ page }) => {
  /* THE OWNER'S RULING, OVER MY OBJECTION (D115). I argued the Fulfiller should see the
     estimate alone — `docs/DESIGN.md` bans jargon on this view and D5 says he gets no vote on
     owner-side bookkeeping — and was overruled: both figures are drawn everywhere.

     It earns its place. The count beside "for sale" is the ESTIMATE, so it moves the instant a
     copy is pulled; without this sentence the number simply changes under him with no reason
     given, which is the one thing this view's constraints table will not have. One sentence,
     so D5's "nothing is explained twice" holds, and every word of it clears the banned-word
     walk this file already runs. */
  await openSearch(page, 'Eiscue', 2, [], { soldHere: 1 })
  await expect(view(page)).toContainText('1 copy sold here since we last counted.')
  /* AND THE COUNT BESIDE "for sale" IS THE ESTIMATE — two copies on hand, two read live, one
     sold here since, so one is for sale. Drawing the raw reading would say two while he holds
     one, which is the shelf disagreement D7 exists to prevent, on the one screen where a
     person is standing at the shelf. */
  await expect(view(page)).toContainText('1 for sale')
})
