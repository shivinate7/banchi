import { test, expect, type Locator, type Page } from '@playwright/test'
import type { GameRegistry, ResolvedOrder } from '../src/types'
import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'
import { settled, whatMoved } from './motionSettled'

/* THE OWNER'S ONE VIEW OF STORED CARDS, asserted where nothing else can reach it.
 *
 * THIS FILE EXISTS BECAUSE OF `CLAUDE.md`'s NEWEST HARD RULE: "A ROUTE IS NOT A FEATURE.
 * Nothing is built until it is reachable from a screen." Three routes — whole-box delete,
 * mid-box delete-with-reindex, and retroactive box-level claims — shipped on 2026-08-23 with
 * full T7 coverage, `make harness` green, `make check` green, and no control anywhere. The
 * owner found them by looking for them and not finding them.
 *
 * That rule ends by saying it "has to be a rule someone reads, because it is not a check
 * anything runs". This is the check. It cannot cover every screen, and it does not try: what it
 * asserts is that each of the four client calls this screen owns is REACHABLE by a person and
 * sends what the route expects. `docs/GATES.md` records the same failure one layer up — 7b
 * shipping with three screens missing from the ROUTES table while four green checks said
 * nothing — and records that the only thing that could tell was a browser.
 *
 * IT IS NOT A HARNESS TEST AND MUST NOT BECOME ONE. `docs/GATES.md`'s contract is seven Python
 * tests run at the Stop hook; this starts a browser, which is a different weight of check.
 * `make design-check` runs it beside the Fulfillment table's assertions.
 *
 * EVERYTHING IS STUBBED AND THE REAL STORE IS NEVER TOUCHED. Every route the screen calls is
 * intercepted, including the writes — the point is that the request is CORRECT and reachable,
 * and issuing a real one would put a test's fixtures into the owner's 767-card inventory. The
 * write assertions read the intercepted body, which is the strongest thing a browser test can
 * say about a route it must not actually call.
 *
 * OWNER-SIDE, SO NO FLOOR FROM `docs/DESIGN.md`'s TABLE IS ASSERTED HERE. That table governs
 * `#/fulfillment` and `app/tests/fulfillment.spec.ts` is its instrument. This screen is the
 * dense end of the same system and borrowing his numbers would quietly make it his screen.
 */

/* Hash form, verbatim, for the reason the other two specs record at their own constants: a
 * path-style '/inventory' is served index.html by Vite, mounts the app with an empty hash and
 * renders the capture screen — a passing navigation to the wrong view. Every test below waits
 * for the view itself before measuring anything, so an unregistered route fails there and
 * loudly rather than as a run of confusing assertions about whatever Vite served. */
const VIEW_ROUTE = '/#/inventory'
const VIEW = 'main.inventory'

/** A 1x1 SVG, so the photograph resolves without a fixture file on disk. The Fulfillment spec
 *  makes the same choice and gives the reason: a PNG has to be handed to `route.fulfill` as a
 *  Buffer, and this only has to load. */
const PHOTO_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="63" height="88"><rect width="63" height="88" fill="#ccc"/></svg>'

/** Every write the screen made, in order. The assertions read this rather than the store,
 *  because there is no store: what is being checked is that a control exists and that pressing
 *  it produces the request the route documents. */
type Wire = { method: string; path: string; body: unknown }

/** One card in the shape `GET /inventory` answers with, decorations included.
 *
 *  `label`, `section`, `card` and `place` are what `server/capture_server.py:do_inventory` adds
 *  to each row from `pipeline/join.py:Position`. The screen renders them and computes none of
 *  them — types.ts forbids the arithmetic and D10 is why — so a fixture that omitted them would
 *  be testing the gap panel rather than the walk. */
/* BOTH SPACES, as the server sends them since D92: `slot` is D58's count and is what a
   nameless neighbour draws, `index` is the store key and is never drawn bare. The fixtures
   below keep them UNEQUAL on purpose — a box with a departure in front is the case that
   tells a renderer reading the wrong field from one reading the right one. */
type Neighbor = { index: number; slot: number; name: string | null; unread?: number }

function card(input: {
  index: number
  state: string
  name: string | null
  sku: string | null
  section: number
  sectionStart: number
  sectionEnd: number
  /** Which box the card is in. Defaults to the one box every case below walks; the jump tests
   *  are the only ones that need a second, because a walk-to is only interesting when it
   *  changes what the strip is pointing at. */
  box?: number
  boxName?: string
  /** The box's fill, for the place block's own fraction. A parameter so a one-card box does
   *  not claim a five-card denominator — the failure D20 spends its entry on, in a fixture. */
  boxTotal?: number
  captureId?: string | null
  /** D23's rarity claim, as a set. A list here is the shape `pipeline/games.py` authors. */
  rarity?: string[] | null
  /** D22's free-text operator note — the whole identity of a `misc` card. ONE LINE: the band
   *  assertion in 'the photograph is sized by its column' measures `.browse-facts`, and a note
   *  that wraps adds a row's height to it. */
  note?: string | null
  /** Which run identified this card, or null for a card no run has read. `pricing.json` is
   *  per-run, so this is the edge the Market row walks — card -> run -> that run's table. */
  run?: string | null
  /** D3 rung 1's finish claim as it comes off `inventory.json`. Defaults to the BARE STRING
   *  every record written before the amendment of 2026-08-23 carries — `_card_row` ships
   *  `asdict(card)` raw, so both shapes really do arrive here and the default is the one
   *  the store is mostly still full of. A row that passes a list is the new shape. */
  finish?: string | string[] | null
  /** D58's box-wide count, where it differs from `index`. Omit for a box nothing has left. */
  at?: number
  /** The two halves of the collector number, and the server's own composition of them (D67).
   *  Defaulted to Pokemon's shape — two halves that both arrive — because that is what every
   *  case written before D67 assumed. A game that prints ONE identifier passes `printedTotal:
   *  ''`, which is what the store really holds for 174 of the owner's 676 numbered records and
   *  what the two client copies of this composition tested for `null` instead.
   *
   *  `noDisplay` IS THE OLDER-SERVER ROW. `number_display` is optional on the wire, the
   *  contract every decoration in `types.ts` takes, and the blank-folding repair has to hold
   *  without it — so one fixture row omits it on purpose. */
  number?: string | null
  printedTotal?: string | null
  noDisplay?: boolean
  /** D30's neighbours, as the server sends them. NULL IS THE DEFAULT AND IS A REAL WIRE STATE
   *  — an older server, or a record whose position will not read — which the app draws as no
   *  block at all, so a fixture that only ever passed null could never render one. That was
   *  every fixture in this file until 2026-08-30, which is how the ranked block's whole
   *  vocabulary shipped unasserted. */
  neighbors?: { prev: Neighbor | null; next: Neighbor | null } | null
  /** D89: when this card's photograph was reclaimed after its sale, or null while the file is
   *  on disk — the default, and what every case written before D89 assumed. */
  reclaimed?: string | null
  /** D172's stable name for the card's photograph. OMITTED BY DEFAULT AND THAT IS THE POINT:
   *  `cid` is optional on the wire because a server predating it sends no key, and every case
   *  in this file was written against that server — so the fixture leaves the key OFF unless a
   *  case is about the name, and those cases keep drawing `GET /photo/<box>/<index>`. One test
   *  passes one, which is what makes the two addresses assertable side by side. */
  cid?: string
  /** D21's game claim. Defaulted to `'pokemon'` below — every case in this file predates
   *  D213 and was written against that one game — so a case is only asked for a second one
   *  when it is actually testing the game/set/rarity filter (D213). */
  game?: string
  /** D213's catalogue set, beside `set_hint` and never a replacement for it (see
   *  `types.ts:InventoryCard.set_name`'s own note). `undefined` is the default and means
   *  "not asserting on this field", which the fixture below reads as `null` — every case
   *  before D213 fixed no set, so this cannot change what any of them render. */
  setName?: string | null
  /** D213's catalogue rarity, same source and same write moment as `setName` above. */
  catalogRarity?: string | null
}) {
  const box = input.box ?? 2
  const boxTotal = input.boxTotal ?? 5

  /* `card` IS THE SLOT INSIDE THE SECTION AND `index` IS THE BOX-WIDE ALLOCATOR NUMBER, which
     is what the server sends and what this fixture used to conflate — it set `card: index`, so
     card 4 arrived as `Section 2 · Card 4` of a section that starts at 4. The two agree for the
     first section of a box and diverge after it (types.ts states exactly that on `Place.index`),
     and a fixture that never diverged could not tell a right answer from a wrong one for
     anything reading `card`. Checked against the live store: index 26 of box 1 comes back as
     `Section 2 · Card 1`, section_start 26. */
  /* `at` IS THE BOX-WIDE COUNT AND `index` IS THE STORE KEY (D58), and they diverge for every
     card behind a departed one. The server sends both — `Place.slot` and `Place.index` — so a
     fixture that conflated them could not tell a right answer from a wrong one for anything
     reading either. Defaulted to `index` so a box nothing has left is written exactly as it
     was before D58, which is also what the server answers for one. */
  const at = input.at ?? input.index
  const slot = at - input.sectionStart + 1
  /* A card with no name has no read at all, which is why both halves hang off it. */
  const number = input.number ?? (input.name === null ? null : '090')
  const printedTotal = input.printedTotal ?? (input.name === null ? null : '132')
  /* THE LABEL'S SHAPE SINCE THE OWNER'S BOX-NAME RULING (D259): the box,
     the section and the card within it, joined by commas; a departed card keeps the place it left.
     The box part stays `Box N` here (the name a backfilled box stores) so the cases below keep
     reading one address; the screen draws `box_name` where the fixture gives one. */
  const label = `Box ${box}, Section ${input.section}, Card ${slot}`

  /* A DEPARTED CARD IS IN NO SLOT (D58), and the fixture has to say so or it is asserting
     against a shape the server cannot produce: the number it used to hold belongs to the card
     that closed up behind it. `join.departed_label` is the one composer of this string. */
  const gone = input.state === 'sold' || input.state === 'retired'
  const place = gone
    ? {
        located: true,
        /* AND IT ENDS ON THE STORE KEY (D68). Two departed records in one box were otherwise
           the identical string — this file's own walk case expected `Box 2 · departed` twice —
           so the label carries the one number about a departed card that cannot lie about a
           shelf. `join.departed_label` is still the one composer of it. */
        label: `Box ${box}, Section ${input.section}, Card ${slot}`,
        box,
        index: input.index,
        slot: null,
        /* THE NUMBERS GO AND THE SECTION STAYS. A departed record belongs to a real part of
           a real box and the walk groups by it, so nulling `section` would file every sold
           card under a heading that is not a section. */
        section: input.section,
        card: null,
        box_name: input.boxName ?? 'ME01 commons',
        section_start: input.sectionStart,
        section_end: input.sectionEnd,
        box_total: boxTotal,
        fraction: null,
        neighbors: input.neighbors ?? null,
        section_gaps: 0,
      }
    : {
        located: true,
        label,
        box,
        index: input.index,
        slot: at,
        section: input.section,
        card: slot,
        box_name: input.boxName ?? 'ME01 commons',
        section_start: input.sectionStart,
        section_end: input.sectionEnd,
        box_total: boxTotal,
        fraction: (at - 1) / boxTotal,
        neighbors: input.neighbors ?? null,
        section_gaps: 0,
      }

  return {
    box,
    index: input.index,
    label: place.label,
    /* `section` STAYS AND `card` GOES for a departed record — `_flat_place` in the server
       omits the number and keeps the section, because the walk groups by the section and
       `rowSlot` tests `card !== undefined`. */
    section: input.section,
    ...(gone ? {} : { card: slot }),
    place,
    photo: `photos/${box}/${input.index}.jpg`,
    photo_sha256: input.reclaimed ? 'deadbeef00112233445566778899aabbccddeeff00112233445566778899aabb' : null,
    photo_reclaimed_at: input.reclaimed ?? null,
    set_hint: 'ME01',
    metadata_finish: input.finish === undefined ? 'normal' : input.finish,
    game: input.game ?? 'pokemon',
    set_name: input.setName ?? null,
    rarity: input.catalogRarity ?? null,
    /* D23's rarity claim and D22's operator note — the two the card panel could overwrite and
       never displayed until 2026-08-25. Optional inputs so most rows keep the nulls that make
       the fallbacks assertable, and one row carries real values. */
    rarity_claim: input.rarity ?? null,
    note: input.note ?? null,
    captured_at: '2026-08-22T12:34:00+00:00',
    capture_id: input.captureId === undefined ? `cap-${input.index}` : input.captureId,
    ...(input.cid === undefined ? {} : { cid: input.cid }),
    name: input.name,
    number: number,
    printed_total: printedTotal,
    ...(input.noDisplay === true
      ? {}
      : {
          number_display:
            number === null || number.trim() === ''
              ? null
              : printedTotal === null || printedTotal.trim() === ''
                ? number
                : `${number}/${printedTotal}`,
        }),
    confidence: null,
    sku: input.sku,
    condition: input.sku === null ? null : 'Near Mint',
    state: input.state,
    state_at: '2026-08-22T12:34:00+00:00',
    retire_reason: null,
    run: input.run ?? null,
  }
}

/* SEVEN RECORDS ACROSS TWO SECTIONS, FIVE OF THEM STILL IN THE BOX, chosen so that every
 * branch this screen draws has a row.
 *
 *   1, 3   one SKU, two copies — D7's map, and the two doors out of inventory on each
 *   2      captured, no name and no SKU — the 22% of the store the search cannot reach, and
 *          the case the lone-copy fallback exists for
 *   4      sold, 5 retired — the terminal states, which draw a word instead of the controls
 *          and which the mid-box delete must not offer itself on
 *   6, 7   section 2's live cards
 *
 * IT WAS FIVE RECORDS AND BOTH DEPARTURES WERE IN SECTION 2, WHICH D58 MADE UNTESTABLE. Once
 * a card's number counts the cards in the box, a section holding only departed records holds
 * nothing — so the three cases below that assert the SECTION scale had no section to assert
 * against, and the honest repair is to give the box live cards there rather than to weaken
 * what they check. Every string those cases expect is unchanged by this: the two departures
 * moved from section 2 to section 1, so the counts they land on are the same numbers.
 *
 * The divergence between `index` and `at` is the point of the shape: cards 6 and 7 are the
 * fourth and fifth cards in the box, and their store keys are 6 and 7.
 */
/** Whatever `GET /inventory` is answering with for one test — the default five, or a map a
 *  jump test hands in. Loose in its keys so a second box can be added without the default map's
 *  key union closing the door on it. */
type Cards = Record<string, ReturnType<typeof card>>

const CARDS: Cards = {
  '2/1': card({ index: 1, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3 }),
  /* THE MISC-SHAPED CARD: no name, no SKU, and the two claims that are the only thing telling it
     apart. D22 makes exactly this the case the note exists for — "it carries a free-text operator
     note instead, so it is findable by search" — and it is the row the fixture comment already
     describes as the part of the store the search cannot reach. */
  '2/2': card({ index: 2, state: 'captured', name: null, sku: null, section: 1, sectionStart: 1, sectionEnd: 3, finish: ['normal', 'reverse_holo'], rarity: ['Common', 'Uncommon'], note: 'japanese, no english print' }),
  '2/3': card({ index: 3, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3 }),
  '2/4': card({ index: 4, state: 'sold', name: 'Eiscue', sku: '8937371', section: 1, sectionStart: 1, sectionEnd: 3 }),
  '2/5': card({ index: 5, state: 'retired', name: 'Mantine', sku: '8937372', section: 1, sectionStart: 1, sectionEnd: 3 }),
  '2/6': card({ index: 6, at: 4, state: 'identified', name: 'Inteleon', sku: '8937373', section: 2, sectionStart: 4, sectionEnd: 5 }),
  '2/7': card({ index: 7, at: 5, state: 'identified', name: 'Pyroar', sku: '8937374', section: 2, sectionStart: 4, sectionEnd: 5 }),
}

const BOXES = {
  boxes: [
    {
      box: 2,
      name: 'ME01 commons',
      sections: [1, 4],
      state: 'open',
      capacity: null,
      /* `fill` AND `next_index` ARE THE ALLOCATOR'S AND `on_hand` IS THE SCREEN'S (D58). Seven
         records, two of them departed, so the box holds five — and `sections_detail` counts
         and bounds in that same space, which is what the dividers editor seeds from. */
      fill: 7,
      next_index: 8,
      cards: 7,
      on_hand: 5,
      sold: 1,
      retired: 1,
      /* D83's third door, which `BoxRecord` has carried since 2026-09-01 and this fixture did
         not. A field the route always sends and the fixture omits is not a smaller fixture — it
         is `undefined` where the screen reads a number, and the census panel threw on it. */
      moved: 0,
      listed: 0,
      sections_detail: [
        { section: 1, start: 1, end: 3, count: 3 },
        { section: 2, start: 4, end: 5, count: 2 },
      ],
    },
  ],
}

/** `GET /boxes/<box>/listings` (D34). Deliberately a SHARED case: `8937370` gives up 2 of its
 *  5 staged copies — the budget is this box's copies — and keeps 3 that box 7 holds, so the
 *  plan's `frees_box` is false. That is the state the panel has to say out loud BEFORE the
 *  press, and the fixture is built to exercise it rather than the easy case. */
const PLAN = {
  box: 2,
  skus: 2,
  releases: { staged: 3 },
  still_held: ['8937370'],
  also_in_boxes: [7],
  frees_box: false,
  listings: [
    {
      sku: '8937200',
      condition: 'Near Mint',
      copies_here: 1,
      before: { staged: 1 },
      releases: { staged: 1 },
      after: {},
      still_held: false,
      also_in_boxes: [],
    },
    {
      sku: '8937370',
      condition: 'Near Mint',
      copies_here: 2,
      before: { staged: 5 },
      releases: { staged: 2 },
      after: { staged: 3 },
      still_held: true,
      also_in_boxes: [{ box: 7, copies: 3 }],
    },
  ],
}

/* THE RUN THAT HAS A PRICING TABLE, and the table it has. Named constants because the stub in
   `open` and three assertions all read them, and a run name spelled two ways would look like a
   cache miss rather than like a typo.

   THE SHAPE IS `pricing.json`'s OWN, cut to what the Market row reads. `cli/cmd_join.py` writes
   every export cell verbatim under `row` and the four other price columns under `snap`; none of
   that reaches this panel, which asks the table two questions — which positions the join matched,
   and what the Market cell said — so the fixture answers those and does not pretend to be a
   whole table. `app/tests/pricing.spec.ts` is where the rest of it is exercised.

   THREE SKUS, ONE PER OUTCOME. `8937370` has a market and holds two positions, which is D7's
   fungible copies and the case that proves the lookup is by POSITION rather than by card:
   `2/2` carries no SKU at all on its record and is still found here. `8937371` matched a row
   whose Market cell is blank — D9's unknown price, which must never render as $0.00 — and
   `2/5` is in no SKU's positions, which is a card the join matched no catalog row for. */
const PRICED_RUN = '2026-08-29-box2-01'

/** Two days before the test runs, so the row's age is a stable `2 days` rather than a date that
 *  goes stale in the fixture. Seconds, because `written_at` is a UNIX second off the file's own
 *  mtime and the client multiplies. */
const PRICED_AT = Math.floor((Date.now() - 2 * 86400000) / 1000)

const PRICING = {
  run: PRICED_RUN,
  pricing: {
    run: PRICED_RUN,
    threshold: '0.40',
    floor: '0.40',
    rule: 'match',
    basis: 'market',
    presets: [],
    games: [],
    bands: [],
    skus: [
      {
        sku: '8937370',
        game: 'pokemon',
        row: {},
        bucket: 'listable',
        copies: 2,
        add_to_quantity: 2,
        backstock: 0,
        live_before: 0,
        committed: 0,
        at_cap: false,
        condition: 'Near Mint',
        set_name: 'ME01',
        name: 'Thievul',
        snap: { market: '5.47', direct_low: null, low: '5.47', low_with_shipping: null, now: null },
        presets: {},
        rule_price: '5.47',
        positions: [
          { box: 2, index: 1, label: 'Box 2, Section 1, Card 1' },
          { box: 2, index: 2, label: 'Box 2, Section 1, Card 2' },
        ],
        listing: null,
      },
      {
        sku: '8937371',
        game: 'pokemon',
        row: {},
        bucket: 'no_market_data',
        copies: 1,
        add_to_quantity: 0,
        backstock: 0,
        live_before: 0,
        committed: 0,
        at_cap: false,
        condition: 'Near Mint',
        set_name: 'ME01',
        name: 'Eiscue',
        snap: { market: null, direct_low: null, low: null, low_with_shipping: null, now: null },
        presets: {},
        rule_price: null,
        positions: [{ box: 2, index: 4, label: 'Box 2, Section 2, Card 1' }],
        listing: null,
      },
    ],
  },
  decisions: null,
  written_at: PRICED_AT,
}

/** The five cards again, every one of them read by `PRICED_RUN`. A separate map rather than a
 *  `run` on the default fixture, because that fixture's whole point is that its rows are null
 *  and the fallbacks are assertable — and because a run on it would put a pricing fetch behind
 *  every one of the fifty cases in this file. */
const JOINED: Cards = Object.fromEntries(
  Object.entries(CARDS).map(([key, held]) => [key, { ...held, run: PRICED_RUN }]),
)

const PRICED_STORE: Store = { cards: JOINED, search: (query) => searchAnswer(query, JOINED) }

/* THE ANNOTATION IS A GUARD, AND IT IS THE ONLY PART OF THIS THAT RUNS ON THE COMMIT PATH.
 *
 * The omission the block above the `products` key describes could happen at all because this
 * fixture was an object literal handed to `route.fulfill` through `JSON.stringify` — nothing
 * had ever compared it to the type it imitates. Naming that type here is what closes it:
 * `app/tsconfig.json` includes `tests`, so `make check`'s typecheck reads this file, and the
 * next field added to `GameRegistry` is a FAILED COMMIT rather than a crash in a browser
 * only `make design-check` starts. Mutation: delete `products` below and `tsc --noEmit`
 * reports `Property 'products' is missing in type ... but required in type 'GameRegistry'`.
 *
 * `capture-undo.spec.ts` and `capture-claims.spec.ts` carry the same annotation for the same
 * reason. Twelve of the eighteen spec files still do not; DEBT3 says so. */
const GAMES: GameRegistry = {
  default: 'pokemon',
  games: [
    {
      key: 'pokemon',
      display: 'Pokémon',
      product_line: 'Pokemon',
      rarities: ['Common', 'Uncommon', 'Rare'],
      finishes: ['normal', 'holo', 'reverse_holo'],
      condition_by_finish: { normal: 'Near Mint', holo: 'Near Mint Holofoil' },
      finish_by_rarity: { Common: ['normal'], Uncommon: ['normal'], Rare: ['normal', 'holo'] },
      located: true,
      join_key: 'number_over_printed_total',
      prompt: 'pokemon',
      crop_bands: ['title', 'number'],
      card_aspect: 0.716,
      unverified: false,
      catalogued: true,
    },
    /* THE SECOND GAME IS HERE BECAUSE THE PRODUCT CLAIM BELONGS TO IT AND TO NOTHING ELSE.
       `ClaimEditor` draws the product row only while the picked game equals `product_game`
       — `codes/products.py:GAME`, which is `pokemon_code` — so a one-game fixture could
       never reach the row D101 added, and did not: the row shipped with no case over it.
       Same shape as the entry above, transcribed from `pipeline/games.py`. */
    {
      key: 'pokemon_code',
      display: 'Pokémon code cards',
      product_line: 'Pokemon',
      rarities: ['Code Card'],
      finishes: ['normal'],
      condition_by_finish: { normal: 'Near Mint' },
      finish_by_rarity: { 'Code Card': ['normal'] },
      located: false,
      join_key: 'name_only',
      prompt: 'pokemon_code_v1',
      crop_bands: [],
      card_aspect: 0.716,
      unverified: false,
      catalogued: true,
    },
  ],
  /* `product_game` AND `products` ARE NOT OPTIONAL ON THIS WIRE, AND THIS FIXTURE OMITTED
     BOTH. `capture_server.py:do_games` has served them beside the registry since C10, and
     `types.ts:GameRegistry` declares both required — so `ClaimEditor` reads
     `registry.products` straight into state and calls `.find` on it every render.

     WHAT THE OMISSION COST: `undefined.find` threw inside the claims editor, the route's
     error boundary swallowed the whole screen, and the four box-claim cases below timed
     out for thirty seconds each on `locator.check` with `element was detached from the
     DOM` — a sentence that names neither the crash nor the field. `the walk keeps a floor`
     and `the re-shoot lives inside Correct claims` failed the same way, the second only
     sometimes, because it asserts before `GET /games` has resolved and the crash is one
     render later. Six cases, one absent key.

     `redeem_limit` and `premium` are carried even though this file reads neither: the
     fixture's job is to be the shape the route sends, and a projection here is the same
     class of lie as the omission it replaces. */
  product_game: 'pokemon_code',
  products: [
    { key: 'booster', display: 'Booster pack', premium: false, redeem_limit: 400 },
    { key: 'etb', display: 'Elite Trainer Box', premium: true, redeem_limit: 4 },
    { key: 'pc_etb', display: 'Pokémon Center ETB', premium: true, redeem_limit: 4 },
    { key: 'other', display: 'Other / unsure', premium: false, redeem_limit: 4 },
  ],
}

/** The per-SKU LISTING STAGES `GET /search` reports beside the copies. Only the two-copy SKU
 *  carries interesting numbers; the other two exist so that selecting a card in the SECOND
 *  section reaches a real group and therefore draws a real position bar.
 *
 *  `on_hand` IS NOT HERE, and used to be. It is D7's count of copies that have not left, which
 *  is a fact about the copies in the answer — so the answer counts them (see `searchAnswer`)
 *  rather than restating a number a differently-sized card map would contradict. The three
 *  literals it replaced all agreed with the count, which is why nothing below moved. */
const LISTED: Record<
  string,
  { pushed: number; staged: number; live: number; sold_here: number }
> = {
  '8937370': { pushed: 0, staged: 2, live: 1, sold_here: 0 },
  '8937371': { pushed: 0, staged: 0, live: 0, sold_here: 0 },
  '8937372': { pushed: 0, staged: 0, live: 0, sold_here: 0 },
}

/** The two doors out of inventory — `master.TERMINAL_STATES`. A copy behind either is not on
 *  hand, which is the one rule `on_hand` applies. */
const GONE = ['sold', 'retired']

/** Which store keys a query reaches, in the shape `do_search` matches with: the SKU, the name,
 *  or the set hint — three of the six fields the real matcher reads.
 *
 *  THE SET-HINT CASE IS WHY THIS STOPPED BEING TWO HARD-CODED KEYS. Every card in this fixture
 *  carries `ME01`, so that one query reaches copies in BOTH sections — which is the only shape
 *  that can test the owner's ask that a search make every match immediately findable. A query
 *  matching one section proves nothing about a match folded away in the other. */
function keysFor(query: string, cards: Cards = CARDS): string[] {
  const asked = query.trim().toLowerCase()
  if (asked === '') return []
  return Object.entries(cards)
    .filter(([, held]) =>
      [held.sku, held.name, held.set_hint].some(
        (field) => typeof field === 'string' && field.toLowerCase() === asked,
      ),
    )
    .map(([key]) => key)
}

/** The groups `GET /search` answers with. Grouped by SKU and WHOLE — every copy of a matched
 *  SKU, including copies that did not match the query themselves, because `do_search` renders a
 *  group by `positions_for_sku` and a screen built against a partial group would be built
 *  against a lie. A card with no SKU is in no group at all, which is the 22% of the store the
 *  lone-copy fallback exists for. */
function searchAnswer(query: string, cards: Cards = CARDS) {
  const reached = new Set(keysFor(query, cards))
  const skus = [
    ...new Set(
      [...reached]
        .map((key) => cards[key]?.sku ?? null)
        .filter((sku): sku is string => sku !== null),
    ),
  ]

  const copiesOf = (sku: string) =>
    Object.entries(cards)
      .filter(([, held]) => held.sku === sku)
      .map(([key, held]) => ({
        key,
        state: held.state,
        state_at: held.state_at,
        has_photo: true,
        place: held.place,
      }))

  return {
    query,
    groups: skus.map((sku) => {
      const copies = copiesOf(sku)
      const listed = LISTED[sku] ?? { pushed: 0, staged: 0, live: 0, sold_here: 0 }
      /* D7's count of copies that have not left, taken off the copies this answer is about to
         send — so `listable` below is derived from the same number the group reports and the
         fixture cannot claim a denominator its own rows contradict. */
      const on_hand = copies.filter((copy) => !GONE.includes(copy.state)).length
      return {
        sku,
        names: [
          ...new Set(
            Object.values(cards)
              .filter((row) => row.sku === sku && row.name !== null)
              .map((row) => row.name as string),
          ),
        ],
        number: '090',
        printed_total: '132',
        set_hint: 'ME01',
        condition: 'Near Mint',
        // THE STAGES AND THE COUNTER TRAVEL APART (D115), the way the wire sends them:
        // `listed` is a walk over `LISTING_STAGES` and `sold_here` deliberately is not a
        // stage, so the screen's estimate is `listed.live - sold_here` rather than a fourth
        // key inside `listed`.
        listed: { pushed: listed.pushed, staged: listed.staged, live: listed.live },
        sold_here: listed.sold_here,
        live_as_of: null,
        on_hand,
        /* D7's `min(cap, on hand)`, mirroring what `capture_server.py` computes — the shelf
           binds below a playset, which is most of the store. Derived here rather than written
           as a number so the fixture cannot claim a denominator its own `on_hand` contradicts. */
        listable: Math.min(4, on_hand),
        copies,
      }
    }),
  }
}

/** Stub the whole server and open the screen. Every route the view calls is intercepted; a
 *  request that reaches none of them would fail at the fetch, which is itself the assertion
 *  that this screen talks to the routes it claims to. */
/** What the server is holding for one test: the cards `GET /inventory` answers with, and what
 *  `GET /search` says about them. A pair rather than two parameters because they are one fixture
 *  — a search answer that described cards the walk does not hold would be a store contradicting
 *  itself, which is the shape of the bug the jump tests are about rather than a fixture to
 *  build. Defaulted, so every case written before this stays a one-argument `open(page)`. */
type Store = { cards: Cards; search: (query: string) => unknown }
const STORE: Store = { cards: CARDS, search: (query) => searchAnswer(query) }

/** What the pricing route answers, called per request. A THUNK rather than a value, because the
 *  reload case has to change the answer between two requests in one test — and a module-level
 *  mutable would leak between the tests Playwright runs in one worker. */
type Priced = () => unknown

/** What `POST /inventory/<box>/<index>/sold` answers, called per request so one test can send a
 *  sale and its reversal down different branches. D57 made this route reachable in one press, so
 *  it is the first thing on this screen a mis-stubbed test could get wrong quietly.
 *
 *  `restores_to` IS THE FIELD THE SCREEN BRANCHES ON, and a stub answering null draws no Undo
 *  anywhere — which is a real server case (`sold_origin_unknown`) and also the shape of a broken
 *  fixture. Both cases below say which one they are. */
type SaleStub = (box: number, index: number, undo: boolean) => { status: number; body: unknown }

/** The ordinary sale and the ordinary reversal. `identified` is what `_state_before_sale` reads
 *  back off the history line for a card that was identified before it sold, which is every card
 *  in this fixture; null on the reversal because there is then nothing left to reverse. */
const SALE: SaleStub = (box, index, undo) => ({
  status: 200,
  body: {
    position: `${box}/${index}`,
    box,
    index,
    undone: undo,
    state: undo ? 'identified' : 'sold',
    previous_state: undo ? 'sold' : 'identified',
    restores_to: undo ? null : 'identified',
    listing: null,
    card: null,
  },
})

/** THE STORE MOVES WHILE THE POST IS BEING ANSWERED, WHICH IS THE ONE MOMENT THAT CANNOT RACE.
 *
 *  A case that writes its fixture move on the line AFTER the press is racing the browser.
 *  `click()` resolves when the click is DISPATCHED, and the press triggers its own re-read —
 *  `Inventory.tsx:doSell` awaits the sale and then bumps `reloads`, which is `BoxBrowse`'s
 *  `reloadToken`. When that `GET /inventory` is served before Node reaches the next statement,
 *  the stub hands back the card still on hand, the screen draws that faithfully, and nothing
 *  re-reads again — so the assertion retries a STABLE wrong answer until it times out. No wait
 *  and no retry can fix that, because nothing is in flight to wait for.
 *
 *  MEASURED, NOT ARGUED. `inventory.spec.ts:5074` lost this race on CI four runs in five while
 *  passing on a Mac every time, and was carried as a design-check flake for a day; its trace
 *  (job 103412668362) holds the post-sale `GET /inventory` still answering all three cards
 *  `identified`. Inserting a 300ms wait between a click and its mutation reproduces it here on
 *  demand, and that probe is what says which cases below need this and which do not.
 *
 *  THE SALE HANDLER IS ORDERED AGAINST BOTH ENDS, which is the whole reason the move belongs
 *  here. It runs when the POST arrives — necessarily after the row's own fetch, and before the
 *  re-read that its response triggers — so the move is visible to every read the press causes
 *  and to none before it. Moving the fixture ABOVE the press is not the same fix and fails the
 *  other way where the row is selected by the press itself: that selection's fetch answers from
 *  an already-sold store, draws `Undo`, and `Mark sold` is never there to click. The one case
 *  that does move its store early (`a departed key is reserved...`) resolves and scrolls its
 *  press first, so nothing re-reads between the move and the click.
 *
 *  `move` IS HANDED THE DIRECTION, because a reversal is a move too: a stub that stayed sold
 *  through an undo answers the re-read with a card the server has just put back. */
function movesOnSale(move: (undo: boolean) => void, answers: SaleStub = SALE): SaleStub {
  return (box, index, undo) => {
    move(undo)
    return answers(box, index, undo)
  }
}

/** The three things one case below needs that every other case must not notice.
 *
 *  `route` is the hash to open, for the deep link — `#/inventory?box=<n>`, the form `#/codes`
 *  and the home screen link here by. `boxesDelayMs` holds `GET /boxes` back so the cards land
 *  first, which is the ORDERING THE DEFECT LIVES IN and is otherwise a race a test cannot pin.
 *  `settle` replaces the section-fold wait, because a box with no cards has no folds and
 *  waiting for one there would fail on the arrangement rather than on the claim. */
/** `hideSold` — the walk's `Hide sold` chip as this browser remembers it (D132). The PRODUCT
 *  defaults to hidden; this FIXTURE defaults to shown, because the store above carries a sold
 *  and a retired card in section 1 and forty cases in this file walk past them on purpose.
 *  `true` hides them; `null` writes nothing to storage, which is the one way a case reaches
 *  the product's own default and asserts it. */
type OpenOptions = {
  route?: string
  boxesDelayMs?: number
  settle?: string
  hideSold?: boolean | null
  /** Overrides `GET /orders`'s `resolution.orders` — the default fixture answers "no orders"
   *  (see the comment beside the route below), which is honest but means no case here ever
   *  drew the Wanted pill against a real claim. Passing this is how a test does. */
  ordersResolution?: readonly ResolvedOrder[]
}

async function open(
  page: Page,
  /* A plain fixture, or (D213) a function of the request's own query string — for a test
   * that has to answer `?game=riftbound&set=` differently from a bare `GET /boxes`, the
   * same way the real route's `matches`/`facets` fields do. */
  boxes: unknown | ((params: URLSearchParams) => unknown) = BOXES,
  store: Store = STORE,
  priced: Priced = () => PRICING,
  sale: SaleStub = SALE,
  options: OpenOptions = {},
): Promise<Wire[]> {
  const wire: Wire[] = []

  const record = (method: string, url: string, body: unknown) =>
    wire.push({ method, path: new URL(url).pathname, body })

  /* The writes first: the read regexes below are looser and a `/inventory` matcher would
     swallow `/inventory/2` if it were registered ahead of it. */

  /* D57's one-press sale, and both directions on it — `server.ts:sale` sends `{}` to record one
     and `{"undo": true}` to reverse it, on one path, so the body is the only thing telling them
     apart and `undo` is what this fixture reads. Registered up here with the other write for the
     ordering reason above: `/inventory\/\d+$/` would swallow nothing of this, but `/inventory$/`
     and the pattern for one card are both looser than it looks and the file already pays for
     that mistake once. */
  await page.route(/\/inventory\/\d+\/\d+\/sold$/, async (route) => {
    const request = route.request()
    const body = request.postDataJSON() as { undo?: boolean } | null
    record(request.method(), request.url(), body)
    const path = new URL(request.url()).pathname.split('/')
    const answer = sale(Number(path[2]), Number(path[3]), body?.undo === true)
    await route.fulfill({
      status: answer.status,
      contentType: 'application/json',
      body: JSON.stringify(answer.body),
    })
  })

  await page.route(/\/inventory\/\d+\/\d+\/remove$/, async (route) => {
    const request = route.request()
    record(request.method(), request.url(), request.postDataJSON())
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        deleted: '2/3',
        box: 2,
        index: 3,
        photo_deleted: true,
        sidecar_deleted: true,
        review_deleted: false,
        parked_deleted: false,
        cache_deleted: false,
        shifted: 2,
        next_index: 5,
      }),
    })
  })

  await page.route(/\/boxes\/\d+$/, async (route) => {
    const request = route.request()
    record(request.method(), request.url(), null)
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        deleted_box: 2,
        cards: 5,
        photos: 5,
        sidecars: 5,
        review_deleted: 0,
        parked_deleted: 0,
        cache_deleted: 0,
        registry_deleted: true,
        directory_removed: true,
      }),
    })
  })

  /* D89's two, the free count and the reclaim, registered here for the same prefix reason as
     D34's pair below them. The count answers two reclaimable photographs — the fixture's one
     sold card and one more — so the panel has a number to draw before the press exists. */
  await page.route(/\/boxes\/\d+\/photos$/, async (route) => {
    const request = route.request()
    record(request.method(), request.url(), null)
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        box: 2,
        reclaimable: { cards: 2, bytes: 3_612_000, indices: [3, 7] },
        reclaimed: { cards: 0, indices: [] },
        on_hand_photos: 3,
      }),
    })
  })

  await page.route(/\/boxes\/\d+\/photos\/reclaim$/, async (route) => {
    const request = route.request()
    record(request.method(), request.url(), request.postDataJSON())
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        box: 2,
        reclaimed: 2,
        bytes: 3_612_000,
        keys: ['2/3', '2/7'],
        already_reclaimed: 0,
      }),
    })
  })

  /* D34's two, registered before the `/boxes/<n>` delete stub they share a prefix with. That
     regex is anchored one segment shorter, so neither can be swallowed by it; they are
     separate handlers so the preflight READ and the release WRITE stay distinguishable in
     `wire`, which is what the "does not exist before the plan" case reads. */
  await page.route(/\/boxes\/\d+\/listings$/, async (route) => {
    const request = route.request()
    record(request.method(), request.url(), null)
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(PLAN),
    })
  })

  await page.route(/\/boxes\/\d+\/listings\/release$/, async (route) => {
    const request = route.request()
    record(request.method(), request.url(), request.postDataJSON())
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        box: 2,
        released: 2,
        listings: PLAN.listings,
        skus: ['8937200', '8937370'],
        given_up: { staged: 3 },
        still_held: ['8937370'],
        frees_box: false,
        also_in_boxes: [7],
        listings_after: { staged: 3 },
      }),
    })
  })

  /* PUT ONLY — box-level claims apply. D192 (store-scaling item 2) put a real GET
   * on this same path (`getInventoryBox`, called on every mount of this screen), and this
   * handler answered EITHER method before that route existed, silently returning the claims
   * shape for a card-map read. `route.fallback()` on a non-PUT request lets it cascade to
   * `shell.ts`'s box-scoped GET stub, registered earlier in the chain. */
  await page.route(/\/inventory\/\d+$/, async (route) => {
    const request = route.request()
    if (request.method() !== 'PUT') return route.fallback()
    record(request.method(), request.url(), request.postDataJSON())
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        box: 2,
        eligible: 2,
        applied: 2,
        unchanged: 0,
        skipped_terminal: 2,
        skipped: [{ index: 4, state: 'sold' }],
        sidecars_rewritten: 2,
      }),
    })
  })

  await page.route(/\/search\?/, async (route) => {
    const asked = new URL(route.request().url()).searchParams.get('q') ?? ''
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(store.search(asked)),
    })
  })

  await page.route(/\/games$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(GAMES) })
  })

  /* THE SIDEBAR'S CARD COUNT, OVER `sealEveryTest`'s DEFAULT OF ZERO. The shared seal answers
     `/status` for every spec in this directory and cannot know how big any one fixture is; a
     module-scope hook has no access to a per-call `store`. This is the documented override —
     registered later, so it wins, the same way every other handler in this file wins over the
     seal — and it is here because the count is drawn in the sidebar BESIDE the walk, and two
     numbers disagreeing on one screen is the class of lie this whole change is about. */
  await page.route(/\/status$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        captures_root: 'captures',
        store: 'inventory/store.sqlite',
        store_exists: true,
        cards: Object.keys(store.cards).length,
        states: {},
        queues: { review: 1, parked: 0 },
        next_index: {},
      }),
    })
  })

  /* THE WALK'S CLAIMS READ, WHICH IS THIS SCREEN'S AND NOT THE SHELL'S. `Inventory.tsx` asks
     `GET /orders` on mount for the open orders' claims on copies and swallows its own failure,
     which is exactly how it escaped a file that stubs everything its screen asks for: nothing
     went red when it went to the capture port instead. Answered by the owner's real server —
     what `:8000` is in the main checkout — the walk drew THEIR open orders over this fixture's
     seven cards. The shell's own `/status` is `sealEveryTest`'s now; this one stays here,
     because it belongs to the screen.

     EMPTY IS THE HONEST ANSWER. D63's ledger is `orders.spec.ts`'s subject; what this file
     needs from it is that no card in the walk carries a claim it would have to draw. */
  await page.route(/\/orders$/, async (route) => {
    const resolutionOrders = options.ordersResolution ?? []
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        summary: resolutionOrders.length === 0 ? 'no orders' : `${resolutionOrders.length} order`,
        orders: [],
        resolution: { orders: resolutionOrders, counts: {} },
      }),
    })
  })

  /* THE BOX ROW IS OVERRIDABLE, and D34's release is why. That control draws only when the
     row reports `listed > 0`, which is a state the default fixture is deliberately not in —
     most boxes never are. A parameter rather than a second `page.route` in the test, because
     Playwright matches handlers in reverse registration order and a test that re-registered
     this one would be relying on that rule to be read correctly by everyone who edits the
     file afterwards. */
  /* `(\?.*)?` SINCE D213: `getBoxes` now sends the game/set/rarity filter as query params
   * (`?game=riftbound&set=`), and a bare `$` anchor stopped matching the moment a filter
   * test asked for anything but the plain unfiltered call every case before this one made.
   * `boxes` (this function's own second parameter) may now be a function of the URL's
   * query string rather than a fixed body — a case answering `?game=` differently from a
   * bare `GET /boxes` passes one; every other case keeps passing a plain object. */
  await page.route(/\/boxes(\?.*)?$/, async (route) => {
    if (options.boxesDelayMs) await new Promise((resolve) => setTimeout(resolve, options.boxesDelayMs))
    const body =
      typeof boxes === 'function' ? boxes(new URL(route.request().url()).searchParams) : boxes
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  })

  await page.route(/\/inventory$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 2, cards: store.cards, boxes: {}, listings: {} }),
    })
  })

  /* D192 (store-scaling item 2): `BoxBrowse.tsx` no longer calls the bare
   * `/inventory` above at all — it calls `getInventoryBox(shelf)` for whichever box is on
   * screen, on every mount and every shelf switch. The `/\/inventory\/\d+$/` PUT stub above
   * (box claims) already falls back for a non-PUT method; this is what it falls back TO. */
  await page.route(/\/inventory\/\d+$/, async (route) => {
    if (route.request().method() !== 'GET') return route.fallback()
    const match = /\/inventory\/(\d+)$/.exec(route.request().url())
    const box = match ? Number(match[1]) : NaN
    const cards = Object.fromEntries(
      Object.entries(store.cards).filter(([, c]) => (c as { box: number }).box === box),
    )
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 2, cards, listings: {} }),
    })
  })

  /* BOTH ADDRESSES, because the app now mints both (D172): `GET /photo/by-card/<cid>` where the
     row carries a name and `GET /photo/<box>/<index>` where it does not. A stub matching only
     the slot would leave the named form unrouted — and `sealEveryTest` refuses an unrouted
     request, so the failure would arrive as a seal rather than as the assertion's own. */
  await page.route(/\/photo\/(by-card\/[0-9a-f]+|\d+\/\d+)/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'image/svg+xml', body: PHOTO_SVG })
  })

  /* THE RUN PANEL'S ONE READ ON MOUNT, stubbed like everything else and for the reason at the
     top of this file: nothing here may touch the real store. It is only a read — but an
     unstubbed read is a request to whatever is listening on port 8000, which in this repo is
     the owner's actual capture server over their actual 767-card inventory. It also makes the
     suite depend on `make server` being up, which no other test here does. Empty, because the
     run list is `app/tests/run-panel.spec.ts`'s subject and not this file's. */
  await page.route(/\/pipeline\/runs$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{"runs": []}' })
  })

  /* THE CARD PANEL'S PRICE READ (2026-08-29), stubbed for the reason every read here is: an
     unstubbed one is a request to whatever is listening on port 8000, which in this repo is the
     owner's real capture server over their real runs.

     KEYED ON THE RUN NAME so one handler covers both answers this row has to draw. `PRICED_RUN`
     gets a table; every other name refuses `pricing_not_written`, which is the real refusal for
     a run made before `pricing.json` existed or never joined — and the one refusal the panel
     tells apart from the rest, because its remedy is a join rather than a look at the server.

     THE DEFAULT FIXTURE NEVER REACHES IT. Every card in `CARDS` carries `run: null`, so the
     panel draws `not joined yet` and issues no request at all; this exists for the cases that
     hand in cards which do carry one. */
  await page.route(/\/pipeline\/runs\/[^/]+\/pricing$/, async (route) => {
    const name = decodeURIComponent(new URL(route.request().url()).pathname.split('/')[3] ?? '')
    if (name !== PRICED_RUN) {
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'pricing_not_written',
            message: `Run ${name} has no pricing.json — join this run and it will appear.`,
          },
        }),
      })
      return
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(priced()) })
  })

  /* THE CARD PANEL'S QUEUE READ, stubbed like everything else and for the reason at the top of
     this file: nothing here may touch the real store. It is only a read, but an unstubbed read is
     a request to whatever is listening on port 8000 — in this repo the owner's actual capture
     server over their actual inventory — and it would make this suite depend on `make server`.

     ONE ENTRY, ON THE CARD THE WALK SELECTS BY DEFAULT, shaped like the one live in the store
     right now: `no_catalog_row` with ZERO candidates, which is D37's black-frame card and the
     case the panel's sentence has to get right. Parked is empty, so a card in neither queue draws
     nothing — asserted by every other case in this file simply passing. */
  await page.route(/\/queues$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        review: [
          {
            position: 'Box 2, Section 1, Card 1',
            box: 2,
            index: 1,
            label: 'Box 2, Section 1, Card 1',
            photo: null,
            read: { name: 'Volcanion', number: '025', printed_total: '132', set_hint: 'ME01' },
            confidence: null,
            reason: 'no_catalog_row',
            candidates: [],
            first_seen: new Date(Date.now() - 2 * 86400000).toISOString(),
            market: null,
            cleared_by_human: false,
          },
        ],
        parked: [],
      }),
    })
  })

  /* The chip's memory, written before the first paint so the walk renders with it. `null`
     writes nothing, which is the one way to reach the product's own default. */
  const hideSold = options.hideSold === undefined ? false : options.hideSold
  if (hideSold !== null) {
    await page.addInitScript((hide: boolean) => {
      try {
        /* eslint-disable-next-line no-restricted-syntax -- SEEDING THE CHIP'S OWN DEVICE KEY
           before first paint, not introducing one. `banchi.inventory.hide-sold` lives in
           `app/src/deviceMemory.ts` where D27's argument for it is, which is what the rule
           exists to force; the fixture's store carries departed records that forty cases walk
           past, and the product's default would fold them away. `orders.spec.ts:remember` and
           `wide.spec.ts:withRail` are the other calls of this shape. */
        window.localStorage.setItem('banchi.inventory.hide-sold', hide ? 'hide' : 'show')
      } catch {
        /* storage blocked — the default applies */
      }
    }, hideSold)
  }

  await page.goto(options.route ?? VIEW_ROUTE)
  await settleFonts(page)
  await expect(page.locator(VIEW)).toBeVisible()
  /* THE SECTION HEADERS AND NOT A CARD ROW, because the walk arrives fully collapsed since
     2026-08-23 and there are no card rows until something asks for them. A header is the
     stronger wait anyway: it proves the inventory read landed AND that the walk grouped it,
     where a row only proves the first. */
  await expect(page.locator(options.settle ?? '.browse-sectfold').first()).toBeVisible()
  return wire
}

/** Open every section of the box being walked.
 *
 *  THE COLLAPSED DEFAULT'S COST, STATED IN A HELPER rather than smuggled into `open`. Exactly
 *  the shape `openBoxOps` above takes and for the same reason: a test that wants card rows says
 *  so, and the fold tests below can still assert the state every other test starts from. */
async function expandAll(page: Page) {
  /* EVERY SHUT FOLD, PRESSED, rather than the one control that says "expand all". That control
     is still there and still does this, but it now reads "collapse all" whenever ANY section is
     open — and one always is on arrival, because the walk opens the section its planted
     selection sits in. Pressing the folds themselves is the same act and does not depend on
     which word the summary is wearing. */
  const shut = page.locator('.browse-sectfold[aria-expanded="false"]')
  for (let guard = 0; guard < 40; guard += 1) {
    if ((await shut.count()) === 0) break
    await shut.first().click()
  }
  await expect(page.locator('.browse-sectfold[aria-expanded="false"]')).toHaveCount(0)
  await expect(page.locator('.browse-row').first()).toBeVisible()
}

/** Wait for the box's controls, which live at the bottom of the walk's own column.
 *
 *  THE CLICK IS GONE TOO NOW. This helper pressed a `<summary>` until D33 removed the
 *  disclosure, then went on pressing the `<p>` that replaced it — inert, and left in place
 *  because it was harmless. The `<p>` itself went on 2026-08-25: it read `Layout and controls`
 *  and labelled a sections list that was deleted for duplicating the walk beside it.
 *
 *  What is left is what this helper was always actually for — a sync point, so a test measuring
 *  a control cannot start before the controls have rendered. The name is kept because nothing
 *  opens and nothing ever did; renaming it would touch every call site to say the same thing. */
async function openBoxOps(page: Page) {
  /* AND THE CLICK IS BACK, because the controls moved. Everything that acts on the BOX rather
     than on a card — rename, seal, the claim editor, the three deletes, the release and the
     reclaim — lives in a Manage sheet now, opened from the box's own header. The sheet is a
     modal over the walk, so this is both the way in and the sync point the helper always was.
     Idempotent: a test that has already opened it may call this again. */
  if ((await page.getByRole('button', { name: 'Rename' }).count()) === 0) {
    await page.getByRole('button', { name: 'Manage' }).click()
  }
  await expect(page.getByRole('button', { name: 'Rename' })).toBeVisible()
}

/** Open the selected card's own actions.
 *
 *  THE CARD'S OPERATIONS ARE BEHIND ONE CONTROL NOW — `Card actions`, a menu beside the card —
 *  where they used to be buttons on the panel. What each one does is unchanged, and the cases
 *  below still assert every one of them; this is the press that reaches them. Idempotent, so a
 *  case may ask for the menu twice. */
async function openCardOps(page: Page) {
  if ((await page.getByRole('menuitem', { name: 'Correct claims' }).count()) === 0) {
    await page.getByRole('button', { name: 'Card actions' }).click()
  }
  await expect(page.getByRole('menuitem', { name: 'Correct claims' })).toBeVisible()
}

/** Shut the Manage sheet again. It is modal over the walk, so anything a case does to the walk
 *  — ticking rows, stepping the selection — has to happen with it shut. */
async function closeBoxOps(page: Page) {
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'Rename' })).toHaveCount(0)
}

/** One figure from the box's census, by the label above it. */
function censusValue(page: Page, label: string) {
  return page.locator('.boxops-census-cell', { hasText: label }).locator('dd')
}

// ------------------------------------------------------- one screen, not two modes (D31)

/* NOTHING HERE MAY REACH THE CAPTURE SERVER, AND THIS FILE PAID FOR THE RULE. Six cases below
   spent thirty seconds each on a detached switch, and two more failed as bare pixel counts,
   because the shell's `/status` went to whatever answers this checkout's capture port — the
   owner's real server in the main tree, nothing at all in a worktree, where the shell then drew
   its 44px offline banner above every measurement. Fixed by hand on 2026-09-05 and folded into
   the shared mechanism here, so there is one spelling of it rather than two.
   `app/tests/shell.ts` carries the argument, including the two invariants this call replaces:
   it asserts the banner is absent and that no route boundary is showing its crash page. */
sealEveryTest()

/* THE ZERO-BOX STORE NEVER LEAVES "Reading the inventory…" (D192, this item). `shelf` is set
 * only by the effect that runs once `shelves.length > 0`; a store with no boxes at all makes
 * `shelves` empty forever, so that effect returns on its first line, `shelf` stays `null`, the
 * box-scoped rows fetch (gated on a numeric shelf) never fires, `rows` stays `null`, and
 * `failure` is never set either — a fresh store has nothing to refuse. The lede branches only
 * on `rows`/`failure`, so it drew the loading sentence forever. The fix reads `boxesAnswered`
 * (the one signal that lands regardless of `shelves`) together with an empty box registry and
 * swaps the loading branch for a real empty state.
 *
 * NOT `open()`: that helper's own postcondition waits for `.browse-sectfold`, which a
 * zero-box store never renders — waiting for it here would just re-time-out inside the
 * helper instead of inside the assertion. This registers the same handful of GET routes the
 * screen fires with no shelf resolved — `/boxes`, `/queues`, `/orders` — and nothing else,
 * so an unstubbed read the fix accidentally starts would fail loudly through `sealCapture`. */
test('a zero-box store renders "No boxes yet" instead of loading forever', async ({ page }) => {
  await page.route(/\/boxes$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ boxes: [] }) }),
  )
  await page.route(/\/queues$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ review: [], parked: [] }),
    }),
  )
  await page.route(/\/orders$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ summary: 'no orders', orders: [], resolution: { orders: [], counts: {} } }),
    }),
  )

  await page.goto(VIEW_ROUTE)
  await settleFonts(page)
  await expect(page.locator(VIEW)).toBeVisible()

  await expect(page.locator('.bn-empty-title', { hasText: 'No boxes yet' })).toBeVisible({
    timeout: 4000,
  })
  await expect(page.getByText('Reading the inventory')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Capture a card' })).toBeVisible()

  /* ONE STATEMENT PER FACT: the header's own lede is silent here, so "No boxes yet" is said
     once, by the empty state's title, and not twice. */
  await expect(page.locator('.bn-lede')).toHaveCount(0)

  /* The loading skeleton is gone too — a stray `.browse-body-loading` here would mean the new
     branch is drawn ALONGSIDE the old one rather than instead of it. */
  await expect(page.locator('.browse-body-loading')).toHaveCount(0)
})

/* THE ORDINARY CASE, GUARDED BESIDE IT. `BOXES` (the fixture every other test in this file
 * shares) holds exactly one box, so this is the regression the fix above must not cause: a
 * store that DOES have a box still auto-selects it and walks straight past the empty state. */
test('a one-box store still auto-selects its first shelf, not the empty state', async ({ page }) => {
  await open(page)

  await expect(page.getByText('No boxes yet')).toHaveCount(0)
  await expect(page.locator('.browse-boxes')).toBeVisible()
  await expect(page.locator('.browse-list')).toBeVisible()
})

test('the walk is the screen — there is no mode switch to be on the wrong side of', async ({
  page,
}) => {
  await open(page)

  /* The owner's correction, asserted rather than remembered: "i imagined moreso in this merge
     that these wouldn't be two tabs, instead it's basically find a card in a box-based system
     if anything". The switch is gone and the box spine is what is left. */
  await expect(page.locator('.inventory-modes')).toHaveCount(0)
  // The spine is `.browse-boxes` since the rebuild — one cell per box, still the only way the
  // screen offers of choosing which box is being walked.
  await expect(page.locator('.browse-boxes')).toBeVisible()
  await expect(page.locator('.browse-list')).toBeVisible()
  await expect(page.locator('.search-field-input')).toHaveCount(1)
})

test('selecting a card shows every copy of it, each with both doors out of inventory', async ({
  page,
}) => {
  await open(page)

  // Card 1 is selected on arrival — the walk plants the selection on its first row.
  await expect(page.locator('.card-locations-owner')).toBeVisible()
  const rows = page.locator('.card-locations-owner .card-locations-row')
  await expect(rows).toHaveCount(2)

  /* D7's map: both copies of the SKU, each at its own position, and the one the walk is
     pointing at marked so a group of identical copies can still say which is which. */
  await expect(rows.nth(0)).toHaveAttribute('aria-current', 'true')
  await expect(rows.nth(1)).not.toHaveAttribute('aria-current', 'true')
  await expect(rows.nth(0).getByRole('button', { name: 'Mark sold' })).toBeVisible()
  await expect(rows.nth(0).getByRole('button', { name: 'Retire' })).toBeVisible()

  /* THE CEILING IS WHAT D7 PERMITS HERE, NOT THE BARE CAP. Two copies on hand against a cap of
     4, so `min(cap, on hand)` is 2 — and this asserted `of 4` until 2026-08-25, which is the
     string the owner caught on a card they had exactly one of: `listed 0 of 4` claims three
     copies of headroom the shelf does not hold. Still off the wire (`SearchGroup.listable`),
     which is what settles this screen's refusal to do the arithmetic in TypeScript.

     THE FIGURE IS DRAWN AS HEADROOM NOW, and the assertion keeps its whole bite: one live
     against a ceiling of two leaves room for ONE, where a screen reading the bare cap of 4
     would offer room for three. */
  await expect(page.locator('.card-locations-live .bn-stat-value')).toHaveText('1')
  // D218: pushed/staged/headroom are sibling spans now; the seam is CSS
  // (`.card-locations-counts > span::before`), never part of `textContent`.
  await expect(page.locator('.card-locations-counts')).toHaveText('2 waiting to go liveRoom for 1 more live')

  /* AND THE CARD'S NAME IS DRAWN ONCE ON THIS SCREEN. This header carried an `<h3>` with the same
     name the band's first fact row prints a few hundred pixels above — invisible while the two
     were 378px and a console apart, and plainly two renderings of one fact once the copies moved
     up under the band. It cost 54px of an 84px header, which is most of a copy row.

     The Fulfiller's skin is a different branch and keeps its own name at 32px; nothing in
     `fulfillment.spec.ts` reaches this selector, which is scoped to `.card-locations-owner`. */
  await expect(page.locator('.card-locations-owner .card-locations-name')).toHaveCount(0)
})

test('the Wanted pill links to the order that named this copy, not the hub\'s default view', async ({
  page,
}) => {
  /* The pill used to be a bare `href="#/orders"` — always the hub's default landing, never the
     order that actually claimed this copy. `Orders.tsx`'s own `groupForOrderKey` reads
     `?order=<order_key>` (the `source:number` composite, `ResolvedLine.order_key` — never the
     bare buyer-facing number `ResolvedLine.order`, which is a different string) and resolves it
     to whichever buyer group holds it; this is the read half of that link's other end. */
  await open(page, BOXES, STORE, () => PRICING, SALE, {
    ordersResolution: [
      {
        key: 'tcgplayer:90201',
        number: '90201',
        complete: false,
        outstanding: 1,
        lines: [
          {
            order: '90201',
            order_key: 'tcgplayer:90201',
            sku: '8937370',
            reason: 'resolved',
            wanted: 1,
            owed: 1,
            fulfilled: 0,
            outstanding: 1,
            on_hand: 1,
            sold: 0,
            retired: 0,
            pooled: 0,
            line: {} as never,
            picks: [
              {
                box: 2,
                index: 1,
                capture_id: null,
                source: 'card',
                run: null,
                card_name: 'Thievul',
                card_number: null,
                condition: null,
                state: 'identified',
                held_by: null,
                place: {} as never,
              },
            ],
          },
        ],
      },
    ],
  })

  await expect(page.locator('.card-locations-owner')).toBeVisible()
  const claimed = page.locator('.card-locations-owner .card-locations-claim').first()
  await expect(claimed).toBeVisible()
  await expect(claimed).toHaveAttribute('href', '#/orders?order=tcgplayer%3A90201')
})

test('a copy sold here since the reading is drawn beside it, and headroom follows', async ({
  page,
}) => {
  /* D115. `listed.live` is the export's READING and `sold_here` is what has sold here since it,
     so the figure a screen draws is the difference — the one that has to agree with the shelf
     the operator is standing at (D7's ordering, which D115 kept by deriving rather than by
     editing the reading).
     THE SISTER CASE IS THE ONE ABOVE, byte-identical with the counter at zero, which is what
     says this change is invisible on the 440 rows of the owner's store that have nothing
     pending and legible on the three that do. */
  const store: Store = {
    cards: STORE.cards,
    search: (query) => {
      const answer = searchAnswer(query, STORE.cards) as {
        groups: { sku: string; sold_here: number }[]
      }
      for (const group of answer.groups) {
        if (group.sku === '8937370') group.sold_here = 1
      }
      return answer as never
    },
  }
  await open(page, BOXES, store)
  // Card 1 is selected on arrival — the walk plants the selection on its first row, and that
  // is SKU 8937370, the row the sister case above asserts at zero sold.
  await expect(page.locator('.card-locations-owner')).toBeVisible()

  await expect(page.locator('.card-locations-live .bn-stat-value')).toHaveText('0')
  // D218: the seam is CSS now (`.card-locations-since > span::before`), never `textContent`.
  await expect(page.locator('.card-locations-since')).toHaveText('1 when read1 sold here since')
  /* AND HEADROOM MOVES WITH IT. Computing off the raw reading would say `Room for 1 more live`
     here and refuse a relist the shelf can support — the one-line bug the change would
     otherwise have left behind. */
  // D218: the seam is CSS now (`.card-locations-counts > span::before`), never `textContent`.
  await expect(page.locator('.card-locations-counts')).toHaveText('2 waiting to go liveRoom for 2 more live')
})

test('a card with no name and no SKU still offers both doors', async ({ page }) => {
  await open(page)

  // Card 2 — captured, never identified. `GET /search` cannot reach it, so the screen SYNTHESISES
  // a one-copy group rather than drawing a second kind of panel (D119); one copy and its two
  // controls, in the row shape every other copy on this screen draws.
  await expandAll(page)
  await page.locator('.browse-row', { hasText: 'Not identified yet' }).first().click()
  /* The list is drawn, and the screen still says why there is only one row in it. */
  await expect(page.locator('.inventory-lone')).toBeVisible()
  await expect(page.locator('.card-locations-owner')).toHaveCount(1)

  /* AND BOTH DOORS ARE STILL OFFERED — from the row itself, which is where this screen puts the
     copy it is standing on. A card the search cannot group is still one copy at one position,
     and the whole of this case is that it may still be sold and still be retired. */
  const doors = page.locator('.card-locations-row.is-current .card-locations-action')
  await expect(doors.getByRole('button', { name: 'Mark sold' })).toBeVisible()
  await expect(doors.getByRole('button', { name: 'Retire' })).toBeVisible()
})

test('a card with no name and no SKU is a one-copy list, not a special case', async ({ page }) => {
  /* THE BRANCH THAT USED TO BE A SECOND PANEL (D119). `GET /search` cannot reach a card with no
   * SKU and no name — it refuses an empty query, and such a card has none — so this screen builds
   * the one-copy group the server's own loose branch would have returned, and draws it through
   * the same component every identified card uses. */
  await open(page)
  await expandAll(page)
  await page.locator('.browse-row', { hasText: 'Not identified yet' }).first().click()

  const rows = page.locator('.card-locations-row')
  await expect(rows).toHaveCount(1)
  await expect(rows).toHaveClass(/is-current/)

  /* No SKU, said as a sentence in the meta line — and the listing figures are NOT drawn at all,
     because `emit` has written no listing record and every one of them would be a structural
     zero under a `Room for 1 more live` nothing can keep. */
  await expect(page.locator('.card-locations-meta')).toContainText('no SKU yet')
  await expect(page.locator('.card-locations-live')).toHaveCount(0)
  await expect(page.locator('.card-locations-counts')).toHaveCount(0)

  /* AND NO WALK-TO ON IT (D45): the lone copy IS the copy the walk is standing on, so there is
     nowhere to be sent — the branch threads no `onGoTo` at all, which makes a walk-to structurally
     impossible rather than merely absent.
     ASSERTED NOWHERE, AND THAT IS THE HONEST ANSWER RATHER THAN A LINE THAT CANNOT GO RED. A
     `toHaveCount(0)` here was written first and then mutation-tested: threading `onGoTo` onto this
     branch left it GREEN, because `OwnerRows` suppresses the walk-to on the current row anyway and
     the lone copy is always the current one. D45's real claim — the current row offers no walk-to
     while the others do — needs a group with more than one copy in it, and it is asserted where
     such a group exists: `a copy in another box is reached by pressing its position, and the walk goes there` below. */
})

test('a search that never returns this card gives a sentence, not an endless loader (B1)', async ({
  page,
}) => {
  /* `GET /search` can settle without ever finding this row's group — a card the store cannot
   * confirm any more, or (the review's own case) one FTS never indexed. `CopiesPanel` used to
   * spin forever on that answer: `group === null && (loading || !settled)` stays true once
   * `results` holds an answer for a DIFFERENT query than the one just asked, because `settled`
   * never catches up. `aria-busy="true"` then never clears, which is what stopped three whole
   * route sweeps at `#/inventory` (machine-words, text-shape, money-face). */
  // The query comes back empty every time — `settled` (`results.query === handle`) never
  // catches up, which is the exact shape the shared route-sweep fixture produces
  // (`app/tests/shell.ts`'s generic `/search` stub echoes `query: ''` regardless of `q`).
  const store: Store = { cards: STORE.cards, search: () => ({ query: '', groups: [] }) }
  await open(page, BOXES, store)

  // Card 1 is selected on arrival (SKU 8937370) — a named, SKUed card, so `CopiesPanel` takes
  // the search branch rather than the no-SKU lone-copy branch `D119` already covers.
  const panel = page.locator('.inventory-copies')
  await expect(panel).toBeVisible()

  // Long enough for the debounce (200ms) plus the stubbed fetch to land several times over.
  await page.waitForTimeout(1500)

  await expect(
    panel.locator('[aria-busy="true"]'),
    'the panel is still marked busy once the search has answered',
  ).toHaveCount(0)
  await expect(panel.locator('.inventory-looking')).toHaveCount(0)
  await expect(panel.locator('.bn-notice-warn')).toContainText("did not return this card's own row")
})

test('B2 — a sold card reached by a deep link stays drawn for the rest of this box load', async ({
  page,
}) => {
  /* FLT-22, "nothing jumps": land on an ALREADY-SOLD card by its `&card=<cid>` link (the way
   * Review's place pill links here) while Hide sold is on. `enteredLive`'s own snapshot keeps
   * only what was LIVE at this box's own fetch, so a row that arrived sold never entered it —
   * it stayed drawn only because `row.key === selected`, and the moment the walk steps off it
   * (D118's OTHER exception) it has nothing left to stand on and folds, moving every row below
   * it up under the very click that was meant to land on one of them. */
  const live = (index: number, at: number) =>
    card({ index, at, state: 'identified', name: 'Bashful Bloom', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 6 })
  const cards: Cards = {
    '2/1': live(1, 1),
    '2/2': card({ index: 2, state: 'sold', name: 'Eiscue', sku: '8937371', section: 1, sectionStart: 1, sectionEnd: 6, cid: 'eiscue-cid' }),
    '2/3': live(3, 2),
  }
  const store: Store = { cards, search: (query) => searchAnswer(query, cards) }
  await open(page, BOXES, store, () => PRICING, SALE, { hideSold: true, route: '/#/inventory?box=2&card=eiscue-cid' })
  await expandAll(page)

  const soldRow = page.locator('.browse-row', { hasText: 'Eiscue' })
  await expect(soldRow, 'the deep link did not land on the sold card').toHaveCount(1)
  await expect(soldRow).toHaveAttribute('aria-current', 'true')

  /* WHICH ROWS ARE DRAWN, IN ORDER — not their pixels, which the deep link's own arrival scroll
     moves on its own and would make this measure that scroll rather than the fold. `evaluateAll`
     rather than `allTextContents` so this reads the DOM the click just committed to, not a
     retried snapshot. */
  const order = () =>
    page.locator('.browse-row').evaluateAll((rows) => rows.map((row) => row.textContent?.replace(/\s+/g, ' ').trim().slice(0, 24)))
  const before = await order()

  // Step off the sold row onto a live one.
  await page.locator('.browse-row', { hasText: 'Bashful Bloom' }).first().click()

  await expect(soldRow, 'the row the walk arrived on folded the moment it left it (nothing jumps)').toHaveCount(1)
  expect(await order(), 'a row appeared, vanished or reordered when the walk stepped off the sold one').toEqual(before)
})

// -------------------------------------------- the sale is one press, and the row is the way back

/* D57. `Mark sold` opened a photo-confirm panel and wrote nothing; the owner ruled the photograph
 * redundant against the card band two inches away — "for my side i literally have the inventory
 * image in front of me already, it was redundant" — so the press IS the sale and the slot becomes
 * `Undo` for the window.
 *
 * NOTHING IN THIS FILE PRESSED `Mark sold` BEFORE TODAY. The two cases above assert the button is
 * visible and stop there, so the panel, the receipt, the undo window, `canUndo` and the
 * `already_sold` path on this screen were all unasserted — which is exactly the condition that
 * lets a control change what it does to a real card with every check still green. That is the
 * hole these close, and it is why `open()` had no `/sold` route to stub until now.
 *
 * WHAT IS DELIBERATELY NOT ASSERTED HERE: that the undo lasts twenty seconds. docs/DESIGN.md's
 * ">= 10s" is a row of the FULFILMENT constraints table and binds that view, where
 * `fulfillment.spec.ts` pays ten seconds of real wall time for it once. This screen is the
 * owner's and the floor does not reach it, so the property worth spending time on is the one
 * below: which control survives the rows being replaced. */

/** A mutable copy of the five-card fixture. `searchAnswer` reads whatever it is handed, so
 *  flipping a card to `sold` here is what makes the RE-READ after a write answer the way the
 *  server would — without it the row would be resting on the optimistic overlay alone and a test
 *  could pass against a stub that contradicts the wire.
 *
 *  WHEN TO MOVE THE STORE, WHICH IS THE PART THAT BITES. These three movers are safe to call
 *  before a press and inside a sale stub, and are a race when called on the line AFTER one —
 *  `movesOnSale` above carries the mechanism and the measurement. Whether a given case loses
 *  that race depends on what it asserts, and the two halves are worth telling apart:
 *
 *    THE OPTIMISTIC OVERLAY ANSWERS WITHOUT ANY RE-READ. `Inventory.tsx:doSell` adds the copy to
 *    `sold` before it bumps `reloads`, on the success path AND on `already_sold` — so the
 *    receipt, the row's `Undo`, the state pill and the wire log are all already right whatever
 *    the re-read says. Four cases below assert only those and pass with a 300ms wait wedged
 *    into the gap: `one press marks a copy sold`, `the receipt is the undo that survives`,
 *    `another device having sold the copy` and `a sale the store cannot put back`. They keep
 *    the plain shape deliberately — it is not a latent version of the same bug, it is a case
 *    whose subject is the overlay.
 *
 *    ANYTHING READ BACK OFF THE WIRE NEEDS THE MOVE ORDERED. `data-gone`, a neighbour's
 *    landmark, a slot number, and the row after an UNDO are all recomputed by the server, so a
 *    stale answer to the press's own re-read is the last word. The three cases that assert
 *    those take `movesOnSale`, and the same probe turns each of them red without it. */
function sellableStore(): {
  store: Store
  sell: (key: string) => void
  depart: (key: string) => void
  unsell: (key: string) => void
} {
  const cards: Cards = Object.fromEntries(
    Object.entries(CARDS).map(([key, held]) => [key, { ...held }]),
  )
  const was = new Map(Object.entries(CARDS).map(([key, held]) => [key, held.state]))
  return {
    store: { cards, search: (query) => searchAnswer(query, cards) },
    sell: (key) => {
      const held = cards[key]
      if (held !== undefined) held.state = 'sold'
    },
    /* AND THE OTHER DIRECTION, which the fixture did not have and now needs: the screen re-reads
       after an undo as well as after a sale, so a stub that stayed sold hands the re-read a card
       the server has just put back — and the row would go on offering `Undo` for a copy that is
       on the shelf. */
    /* AND THE PLACE THE STORE REWRITES WITH IT (D118). `sell` moves `state` and nothing else,
       which is what every case before this one needed — but the server does more than that: a
       departed copy comes back with `slot` and `card` null and `join.departed_label` in place of
       the address (D58, D68), and `card()` above builds that shape at construction time from the
       state it was handed. So a fixture that only moved `state` served a SOLD card that was
       still in its slot, and every case measuring what the sale does to the panel was measuring
       a state the server cannot produce. It cost the stability case its whole subject: deleting
       the departed lens outright left it green.

       SEPARATE FROM `sell` ON PURPOSE. The cases that came first assert on the row and the
       receipt, both of which are answered by the optimistic overlay before any re-read lands,
       and re-shaping the place under them would be changing what they test to fix a different
       case. A caller that wants the whole write calls both. */
    depart: (key) => {
      const held = cards[key]
      if (held === undefined) return
      const place = held.place
      const gone = {
        ...place,
        label: place.label,
        slot: null,
        card: null,
        fraction: null,
      }
      cards[key] = { ...held, label: gone.label, place: gone }
      delete (cards[key] as { card?: number }).card
    },
    unsell: (key) => {
      const held = cards[key]
      const before = was.get(key)
      if (held !== undefined && before !== undefined) held.state = before
    },
  }
}

/** The first card of the walked box, as `pipeline/join.py:Position.label` spells it. */
const CARD_1 = 'Box 2, Section 1, Card 1'

/** THE WAY BACK THAT OUTLIVES THE WALK. A write now leaves two things: the slot in the copy
 *  row turns into a RECEIPT for the window — its sentence, its draining clock and its `Undo`,
 *  which is where the location card's used to be until D119 — and a receipt is posted to the
 *  product's toast stack carrying the same window and the same Undo. The second is the one the
 *  owner's ruling keeps — receipts are toasts and expire — and it is the one that survives the
 *  walk moving on, which is what the old in-flow receipt panel was for. */
function receiptToast(page: Page) {
  return page.locator('.bn-toast')
}

/** The copy row for one position, scoped so the two `Undo` controls a standing sale draws — this
 *  one and the receipt's — can each be reached on their own. */
function copyRow(page: Page, place: string) {
  /* FOUND BY THE SERVER'S OWN LABEL, which `PositionLabel` carries verbatim on `aria-label` and
     guarantees it will go on carrying. The rendered TEXT is not that string and never was: the
     component draws the parts as separate spans, so the row reads `BOX 2SECTION 1CARD1` to
     anything that greps it — a substring match on `CARD 1` finds nothing, which is a locator
     that can only ever fail. The attribute is the label; the spans are the treatment. */
  return page
    .locator('.card-locations-owner .card-locations-row')
    .filter({ has: page.locator(`[aria-label="${place}"]`) })
}

test('one press marks a copy sold, with no panel in between', async ({ page }) => {
  const { store, sell } = sellableStore()
  const wire = await open(page, BOXES, store)

  const row = copyRow(page, CARD_1)
  await row.getByRole('button', { name: 'Mark sold' }).click()
  sell('2/1')

  /* THE PRESS IS THE WRITE. Red against the two-step, where this press only set `pending`.
     READ AS `Undo` AND NOT AS `Marked sold.` SINCE D119. The row's receipt is the draining clock
     and the button, at the size the button pair already reserved — a `bn-receipt` panel in that
     slot resizes it, which is the shake D118 ended. The SENTENCE is still asserted, on the two
     surfaces that draw it: the toast (below, and in `the sale posts a receipt to the toast
     stack`) and the phone's action bar. */
  await expect(page.locator('.inventory-receipt')).toContainText('Undo')
  const sales = wire.filter((call) => call.path.endsWith('/sold'))
  expect(sales.map((call) => [call.method, call.path, call.body])).toEqual([
    ['POST', '/inventory/2/1/sold', {}],
  ])

  /* AND ASSERTED AS AN ABSENCE, which is the discipline the run panel's spend button already
     keeps: a panel that is merely not visible is one CSS rule from being back, and a component
     that is not rendered has to be deliberately re-added. */
  await expect(page.locator('.bn-scrim')).toHaveCount(0)
  await expect(page.locator('[role="dialog"]')).toHaveCount(0)
})

/* ---------------------------------------------------------------------- the stability floor
 *
 * A PRESS CHANGES WHAT IS ON THE SCREEN. IT MAY NOT CHANGE WHERE THE REST OF IT IS.
 *
 * The owner's report, 2026-09-07: "I am getting a lot of screen shake when I am in inventory and
 * am marking something sold, things should not be moving around when I hit buttons". D118 is the
 * entry. `cursor.spec.ts` carries the half of the floor that can be read off the stylesheets — a
 * hover or a press that re-lays out a control — and it CANNOT see this half, because nothing here
 * is a CSS rule: it is what the panel does when the write lands.
 *
 * MEASURED BEFORE ANY OF IT WAS FIXED, at 1440x900 against a seeded store: one press of
 * `Mark sold` collapsed the card panel by 98px and moved 131 elements, and stepping the walk from
 * one card to the next moved 39, 66 or 98px depending on the two cards. Three things were doing
 * it and all three are now reserved — the position lens a departed copy stopped drawing (85px),
 * the action slot whose button pair became a 22px pill (18px), and the copies list whose length
 * is the card's rather than the box's.
 *
 * THE ANCHORS ARE OUTSIDE THE PANEL ON PURPOSE. What a press is allowed to change is what it
 * wrote; what it may never do is move the things a person was not looking at. So this sweeps
 * everything that is NOT inside the card panel and requires it to be where it was, and asserts
 * the document's own height on top — the one number that catches a change nothing else sees.
 *
 * `settled`/`whatMoved`, `./motionSettled`'s own shared copy since `confirm-identity.spec.ts`
 * carried a byte-identical pair. `settled` and not the bare `outsideThePanel` it wraps: this
 * file's own `open()` waits for `.browse-sectfold` to be VISIBLE, and visible is not settled —
 * the box rail's section-fold chevron (`.browse-sectmark`) keeps rotating for `.2s` after
 * mount, so a "before" sample taken right after `scrollIntoViewIfNeeded()` can still catch it
 * mid-flight on a slow enough runner. `motionSettled.ts`'s own comment carries the measurement
 * and the argument that a real move still fails every time. */

test('the press that sells a copy moves nothing outside the panel it lands in', async ({ page }) => {
  const { store, sell, depart } = sellableStore()
  /* THE STORE MOVES INSIDE THE SALE (see `movesOnSale`). This case reads `data-gone`, which is
     the re-read landing rather than the optimistic overlay — so it is one of the three here that
     the 300ms probe turns red when the move is written after the press. */
  await open(page, BOXES, store, () => PRICING, movesOnSale(() => {
    sell('2/1')
    depart('2/1')
  }))

  /* Bring the press into view BEFORE the sweep, so the click itself does not scroll. */
  /* THE ROW IS NAMED BY WHERE THE WALK STANDS AND NOT BY ITS LABEL (D119). `copyRow` filters on
     the server's position label, and the sale rewrites that label to the departed form — so a
     locator built from it stops matching the very row whose height this case is about, and
     `boundingBox()` returns null on the side of the comparison that matters. `is-current` is the
     one handle on this row that the write does not touch. */
  const row = page.locator('.card-locations-row.is-current')
  const press = row.getByRole('button', { name: 'Mark sold' })
  await press.scrollIntoViewIfNeeded()

  const before = await settled(page)
  const height = await page.evaluate(() => document.documentElement.scrollHeight)
  const at = await page.evaluate(() => window.scrollY)

  /* AND THE BOX INSIDE THE PANEL THAT THE WRITE ITSELF REDRAWS. The sweep above cannot see it —
     the panel holds one height (D118), so anything that changes inside it moves nothing outside
     it — and it is where the defect actually was: the row lost its position lens (85px) and its
     button pair became a 22px pill (18px). Mutating either fix passes the sweep and fails here,
     which is the whole reason it is asserted.
     ONE BOX AND NOT TWO SINCE D119. This measured the location card as well, and that card is
     deleted; the copy the walk stands on is this row. The claim is unchanged and now has one
     subject rather than the same subject twice. */
  const rowBox = await row.boundingBox()

  await press.click()
  await expect(page.locator('.inventory-receipt')).toContainText('Undo')

  /* AND THE RE-READ, WAITED FOR RATHER THAN ASSUMED. The receipt is optimistic — it is drawn from
     `soldKeys` in the same continuation as the write — so measuring on it alone measures a frame
     in which the store has not answered yet and the copy is still placed. The lens turning
     departed is the re-read landing, and it is the state whose height the case is actually about:
     without this wait, deleting the departed lens outright leaves this case green. */
  await expect(row.locator('.position-bar')).toHaveAttribute('data-gone', 'true')

  /* The panel itself keeps its height, which is what everything below it is standing on. */
  const band = page.locator('.browse-band')
  const after = await settled(page)
  const moved = whatMoved(before, after)
  expect(moved, `${moved.length} elements outside the panel moved on the press:\n${moved.slice(0, 12).join('\n')}`)
    .toHaveLength(0)
  expect(await page.evaluate(() => document.documentElement.scrollHeight),
    'the page changed height on a press').toBe(height)
  expect(await page.evaluate(() => window.scrollY),
    'the page scrolled under the press').toBe(at)
  await expect(band).toBeVisible()

  expect(Math.round((await row.boundingBox())?.height ?? -1),
    'the copy row changed height on the press').toBe(Math.round(rowBox?.height ?? -2))
})

/* D118, THE RE-READ HALF. The sweep above measures the SALE'S OWN move (the departed lens, the
 * button pill) and passes even on a slow re-read, because Playwright's `expect` retries until
 * `data-gone` lands — it never looks at the FRAME IN BETWEEN. What the owner did not report
 * until the answer was slowed down: `useSearch` sets `loading` true and KEEPS the old `results`
 * while the re-read is in flight, and `Inventory.tsx` used to draw an 86px skeleton (WHILE
 * `CardLocations` was still rendered under it) for exactly that gap — `.card-locations` jumps
 * from y=79 to y=181 and back the instant the answer lands. Measured at 1440 with `/search`
 * delayed 800ms. On the owner's own store the real gap is ~93ms, too fast to see without
 * slowing it down, which is why this needed a delayed stub rather than a real server. */
test('the press that sells a copy does not shift while the re-read is in flight', async ({ page }) => {
  const { store, sell, depart } = sellableStore()
  await open(page, BOXES, store, () => PRICING, movesOnSale(() => {
    sell('2/1')
    depart('2/1')
  }))

  /* SLOW THE SECOND `/search` ONLY. The first call is the mount's own read and must land
     normally, or nothing is on screen to sample; the second is the re-read `doSell`'s
     `setReloads` triggers, and delaying it is what makes the in-flight frame observable. This
     handler is registered AFTER `open()`'s, so it wins (this file's own convention, stated
     where `/search` is first stubbed). */
  let calls = 0
  await page.route(/\/search\?/, async (route) => {
    calls += 1
    const asked = new URL(route.request().url()).searchParams.get('q') ?? ''
    if (calls === 2) await new Promise((resolve) => setTimeout(resolve, 800))
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(store.search(asked)),
    })
  })

  const row = page.locator('.card-locations-row.is-current')
  const press = row.getByRole('button', { name: 'Mark sold' })
  await press.scrollIntoViewIfNeeded()

  const locations = page.locator('.card-locations')
  const topsBefore = Math.round((await locations.boundingBox())?.y ?? -1)

  await press.click()
  await expect(page.locator('.inventory-receipt')).toContainText('Undo')

  /* SAMPLE THROUGH THE GAP, not only before and after it. `data-gone` only ever reads `true`
     once the re-read has landed, so waiting on it alone (as the sweep above does) would let
     Playwright's retry skip straight past the frame this case is about. */
  const seenTops = new Set<number>()
  let sawSkeleton = false
  const deadline = Date.now() + 5000
  while (Date.now() < deadline) {
    const box = await locations.boundingBox()
    if (box !== null) seenTops.add(Math.round(box.y))
    if ((await page.locator('.inventory-looking').count()) > 0) sawSkeleton = true
    if ((await row.locator('.position-bar').getAttribute('data-gone')) === 'true') break
    await new Promise((resolve) => setTimeout(resolve, 50))
  }

  expect([...seenTops], 'the copies list moved while the re-read was in flight').toEqual([topsBefore])
  expect(sawSkeleton, 'a skeleton was drawn over the standing list').toBe(false)
})

/* A KEY WIDE ENOUGH TO BE SEEN. The fixture above walks box 2 card 1, whose departed key is
   `B2 #1` — five characters, 33px, and the slot column's floor is 34px, so the widening the case
   below is about is absorbed and nothing moves however wrong the CSS is. That is not a property
   of the product: it is the shortest key a store can produce. `B12 #133` is 46px, which is what
   the owner's own boxes are already writing, and it is what makes the reservation assertable. */
function wideKeyCard(state: string) {
  return card({
    index: 133,
    box: 12,
    boxName: 'RB epics',
    boxTotal: 1,
    state,
    name: 'Thievul',
    sku: '8937370',
    section: 1,
    sectionStart: 133,
    sectionEnd: 133,
  })
}

const WIDE_KEY_BOXES = {
  boxes: [
    {
      box: 12,
      name: 'RB epics',
      sections: [133],
      state: 'open',
      capacity: null,
      fill: 1,
      next_index: 134,
      cards: 1,
      on_hand: 1,
      sold: 0,
      retired: 0,
      moved: 0,
      listed: 0,
      sections_detail: [{ section: 1, start: 133, end: 133, count: 1 }],
    },
  ],
}

test('the slot column is already as wide as the key the sale will write into it', async ({ page }) => {
  /* WHY THIS IS A SECOND CASE AND NOT AN ASSERTION IN THE ONE ABOVE (D118). The sweep up there
     records position and height and deliberately not width, and the element that moves is the
     NAME — so the thing that actually grows, the slot column, is invisible to it, and the move it
     causes is invisible too whenever the growth stays under the column's 34px floor.

     THAT FLOOR IS WHY `make design-check` WAS GREEN ON THE RIG AND RED IN CI ON THE SAME TREE.
     `B2 #1` sets at 33.0px in macOS's monospace fallback and at over 34px in Linux's, so on one
     platform the floor swallowed the widening and on the other the name moved a pixel. The
     difference between the two was never the point: the movement is real on both, and `B12 #133`
     — which this store already writes — moves the name twelve pixels on either. */
  const cards: Cards = { '12/133': wideKeyCard('identified') }
  const store: Store = { cards, search: (query) => searchAnswer(query, cards) }
  await open(page, WIDE_KEY_BOXES, store)
  /* THIS CASE IS A RULER OVER TYPE, so it waits for the faces — `fontsReady.ts` has the whole
     argument, and the swap window is exactly the window in which the reservation and the label
     it reserves for would be measured in two different typefaces. */
  await settleFonts(page)

  const row = page.locator('.browse-row[aria-current="true"]')
  const slot = row.locator('.browse-row-position')
  const name = row.locator('.browse-row-name')

  const press = copyRow(page, 'Box 12, Section 1, Card 1').getByRole('button', { name: 'Mark sold' })
  await press.scrollIntoViewIfNeeded()

  const slotWas = (await slot.boundingBox())?.width ?? -1
  const nameWas = (await name.boundingBox())?.x ?? -1

  /* THE STORE IS MOVED BEFORE THE PRESS, NOT AFTER IT. Nothing re-reads until the press, so the
     measurements above are taken against the state the operator is looking at either way — and
     mutating afterwards is a race this case lost four times in five: the screen's re-read is in
     flight from the moment of the click, and a stub still holding the placed card answers it. */
  cards['12/133'] = wideKeyCard('sold')

  await press.click()
  /* `Undo` and not `Marked sold.`: the row's receipt is the clock and the button since D119, and
     the sentence is the toast's — the case at the top of this file says why. */
  await expect(page.locator('.inventory-receipt')).toContainText('Undo')
  /* The re-read, waited for rather than assumed — the same sync point the case above uses, and
     for the same reason: the receipt is optimistic and the lens turning departed is the answer
     landing, which is the state this measurement is about. */
  await expect(page.locator('.card-locations-row.is-current .position-bar')).toHaveAttribute('data-gone', 'true')

  /* SINCE THE OWNER'S BOX-NAME RULING (D259) A DEPARTED ROW KEEPS THE
     NUMBER OF THE PLACE IT LEFT, struck through, and no store key is written into the column. So
     the widening this case was built to catch cannot happen any more; the two equalities below
     still hold the column and the name still. */
  await expect(row.locator('.browse-row-slot')).toHaveText('#1')

  /* THE CASE READS ITS OWN SUBJECT BEFORE IT JUDGES IT. The key has to be wider than the
     column's 34px floor for any of this to be about anything, and that is a property of the
     fixture rather than of the fix — measured on the state the sale leaves, so a reservation
     that had been deleted cannot answer for it. */
  const slotNow = (await slot.boundingBox())?.width ?? -2

  expect(slotNow, 'the slot column grew on the press').toBe(slotWas)
  expect((await name.boundingBox())?.x ?? -2, 'the name slid right on the press').toBe(nameWas)
})

test('S5 — the slot ghost reserves what a departure actually draws, not the old store key', async ({
  page,
}) => {
  /* Two live rows in the same box (so the box digit count cannot confound this), each alone in
   * its own one-card section, so both draw the identical visible slot text `#1`. Their raw
   * `box/index` pair differs a lot — 12/1 against 12/133 — so `B12 #1` and `B12 #133`, the OLD
   * unconditional ghost reservation, differ by two characters while the two rows' OWN visible
   * text does not differ at all. If the ghost reserves the right string (S5), the two names
   * land at the same x; reserving the old store key instead pushes the wider one's name right
   * of the other's, though neither row has departed and both show the same "#1". */
  const cards: Cards = {
    '12/1': card({ index: 1, state: 'identified', name: 'Mantine', sku: '8937372', box: 12, boxName: 'RB epics', boxTotal: 2, section: 1, sectionStart: 1, sectionEnd: 1 }),
    '12/133': wideKeyCard('identified'),
  }
  const boxes = { boxes: [{ ...WIDE_KEY_BOXES.boxes[0], cards: 2, on_hand: 2, fill: 2, next_index: 134, sections: [1, 133], sections_detail: [{ section: 1, start: 1, end: 1, count: 1 }, { section: 2, start: 133, end: 133, count: 1 }] }] }
  const store: Store = { cards, search: (query) => searchAnswer(query, cards) }
  await open(page, boxes, store)
  await expandAll(page)
  await settleFonts(page)

  const narrowKeyRow = page.locator('.browse-row', { hasText: 'Mantine' })
  const wideKeyRow = page.locator('.browse-row', { hasText: 'Thievul' })
  await expect(narrowKeyRow.locator('.browse-row-slot')).toHaveText('#1')
  await expect(wideKeyRow.locator('.browse-row-slot')).toHaveText('#1')

  const narrowX = (await narrowKeyRow.locator('.browse-row-name').boundingBox())?.x ?? -1
  const wideX = (await wideKeyRow.locator('.browse-row-name').boundingBox())?.x ?? -2

  expect(wideX, 'a row with a wider store key had its name pushed right, though both show "#1"').toBe(narrowX)
})

test('the card panel holds one height for the whole walk', async ({ page }) => {
  await open(page)
  await expandAll(page)

  /* THE FIXTURE BOX HOLDS BOTH KINDS, WHICH IS WHY THIS CASE CAN FAIL AT ALL. Two of its seven
     records have left — card 4 sold, card 5 retired — so the walk crosses a departed copy and a
     placed one, which is exactly the pair whose lens differed by 85px. A box of live cards alone
     would pass this with the defect still in it. */
  const rows = page.locator('.browse-row')
  const count = await rows.count()
  expect(count, 'the walk drew no cards — the fixture is not the subject').toBeGreaterThan(4)

  const heights: string[] = []
  for (let i = 0; i < count; i++) {
    await rows.nth(i).click()
    await expect(page.locator('.browse-band')).toBeVisible()
    const box = await page.locator('.browse-band').boundingBox()
    const label = (await rows.nth(i).getAttribute('aria-label')) ?? `card ${i + 1}`
    heights.push(`${Math.round(box?.height ?? -1)}  ${label}`)
  }

  const distinct = [...new Set(heights.map((h) => h.split('  ')[0]))]
  expect(distinct, `the panel took ${distinct.length} different heights across the walk:\n${heights.join('\n')}`)
    .toHaveLength(1)
})

test('the row that sold the copy becomes the way to take it back', async ({ page }) => {
  const { store, sell, unsell } = sellableStore()
  /* BOTH DIRECTIONS MOVE INSIDE THE SALE (see `movesOnSale`), and the REVERSAL is the half that
     measurably needed it: the undo's own re-read, answered by a stub still holding the card
     sold, leaves the row offering `Undo` forever and `Mark sold` never comes back. */
  const wire = await open(page, BOXES, store, () => PRICING,
    movesOnSale((undo) => (undo ? unsell('2/1') : sell('2/1'))))

  const row = copyRow(page, CARD_1)
  await row.getByRole('button', { name: 'Mark sold' }).click()

  /* The slot draws `Undo` ALONE — no `Retire` beside it, because the server refuses the
     retirement of a sold card and a control that can only fail is not a control. */
  const rowUndo = row.getByRole('button', { name: 'Undo the sale at' })
  await expect(rowUndo).toBeVisible()
  await expect(row.getByRole('button', { name: 'Retire' })).toHaveCount(0)
  await expect(row.getByRole('button', { name: 'Mark sold' })).toHaveCount(0)

  /* THE TWO CONTROLS ARE REACHABLE APART, and they are in two different places rather than two
     different names: the slot's Undo names the position it undoes, and the receipt's rides the
     toast stack for the same window. Each is reached inside the thing that owns it. */
  const receiptUndo = receiptToast(page).getByRole('button', { name: 'Undo' })
  await expect(receiptUndo).toBeVisible()
  await expect(receiptToast(page)).toContainText('Marked sold')
  /* D218: the toast speaks the place as a sentence, never the server's typed `' · '` — see
     `Inventory.tsx:sayPlace`. `CARD_1` is `Position.label`'s own string; the toast's is that
     string read aloud. */
  await expect(receiptToast(page)).toContainText(CARD_1.replace(/ · /g, ', '))

  await rowUndo.click()
  const sales = wire.filter((call) => call.path.endsWith('/sold'))
  expect(sales.map((call) => call.body)).toEqual([{}, { undo: true }])

  // And the copy is sellable again, which is what a reversal means on this screen.
  await expect(row.getByRole('button', { name: 'Mark sold' })).toBeVisible()
  await expect(page.locator('.inventory-receipt')).toHaveCount(0)
  await expect(receiptToast(page).getByRole('button', { name: 'Undo' })).toHaveCount(0)
})

/* D218: A TYPED DOT IS A DEFECT WHEREVER IT IS TYPED. `Position.label` reaches this screen as
 * `Box 2, Section 1, Card 1` — real, server-composed, and never edited here — but the toast
 * body has no CSS to draw a separator with, so retyping the server's `' · '` into that plain
 * text would be exactly the defect D218 names. `Inventory.tsx:sayPlace` reads it as a sentence
 * instead. This is the ONE surface in this file a middle dot could still reach verbatim: every
 * other place this screen draws a position goes through `PositionLabel`, which never emits the
 * character as text at all (`.position-plain-parts`'s separator is CSS `content`). */
test('the sale toast speaks the place, and never types the server\'s middle dot', async ({
  page,
}) => {
  const { store, sell } = sellableStore()
  await open(page, BOXES, store)

  await copyRow(page, CARD_1).getByRole('button', { name: 'Mark sold' }).click()
  sell('2/1')

  const body = await receiptToast(page).innerText()
  expect(body).not.toContain('·')
  expect(body).not.toContain('•')
  expect(body).toContain(CARD_1.replace(/ · /g, ', '))
})

/* OWNER'S RULING, 2026-09-20: "Clearer icon only." A bare `—` read as unclear icon-only — the
 * hover `title` said `Retire`, but nothing stood in for it until the pointer arrived, and a
 * screen reader was never told which control this was without reading the icon's own SVG path.
 * The accessible name has to be real, not only a tooltip: `title` is the LAST source accname
 * computation falls back to, behind the element's own text content, so a name that depends on
 * `title` alone is one CSS rule (or one icon swap) from silence. */
test('the Retire control carries a real accessible name, not only a hover title', async ({
  page,
}) => {
  await open(page)

  const retire = copyRow(page, CARD_1).getByRole('button', { name: 'Retire' })
  await expect(retire).toBeVisible()
  await expect(retire).toHaveAttribute('aria-label', 'Retire')
})

/* `docs/specs/undo.md` §3: `U` IS THE ONE KEY FOR THE NEWEST REVERSIBLE WRITE, wherever one
 * stands — the owner's ruling, and the same letter `CaptureScreen.tsx` and `ReviewQueue.tsx`
 * already carry out. These two cases are the pair `CLAUDE.md`'s brief called for: the key
 * reaches the write, and a letter typed into the search field does not. Neither is a click —
 * `page.keyboard.press` is what dispatches a real `keydown` a window listener can see, which
 * `.fill()` on the searchbox elsewhere in this file does not. */
test('U undoes the newest sale, wherever the hand is', async ({ page }) => {
  const { store, sell, unsell } = sellableStore()
  const wire = await open(page, BOXES, store, () => PRICING,
    movesOnSale((undo) => (undo ? unsell('2/1') : sell('2/1'))))

  const row = copyRow(page, CARD_1)
  await row.getByRole('button', { name: 'Mark sold' }).click()
  await expect(row.getByRole('button', { name: 'Undo the sale at' })).toBeVisible()

  // The hand is nowhere in particular — on the page heading, not in any field.
  await page.getByRole('heading', { name: 'Inventory' }).click()
  await page.keyboard.press('u')

  const sales = wire.filter((call) => call.path.endsWith('/sold'))
  expect(sales.map((call) => call.body)).toEqual([{}, { undo: true }])
  await expect(row.getByRole('button', { name: 'Mark sold' })).toBeVisible()
})

test('u typed into the search field does not undo the sale', async ({ page }) => {
  const { store, sell } = sellableStore()
  const wire = await open(page, BOXES, store, () => PRICING,
    movesOnSale((undo) => (undo ? undefined : sell('2/1'))))

  const row = copyRow(page, CARD_1)
  await row.getByRole('button', { name: 'Mark sold' }).click()
  const rowUndo = row.getByRole('button', { name: 'Undo the sale at' })
  await expect(rowUndo).toBeVisible()

  await page.getByRole('searchbox').click()
  await page.keyboard.press('u')

  // No second `/sold` call — the field ate the key, the card is still sold, still reversible.
  const sales = wire.filter((call) => call.path.endsWith('/sold'))
  expect(sales.map((call) => call.body)).toEqual([{}])
  await expect(rowUndo).toBeVisible()
  await expect(page.getByRole('searchbox')).toHaveValue('u')
})

test('the receipt is the undo that survives the rows being replaced', async ({ page }) => {
  const { store, sell } = sellableStore()
  const wire = await open(page, BOXES, store)

  await copyRow(page, CARD_1).getByRole('button', { name: 'Mark sold' }).click()
  sell('2/1')
  await expect(page.locator('.inventory-receipt')).toContainText('Undo')

  /* STEP THE WALK. The copies panel is drawn for whichever card the walk points at, so this
     unmounts the row and its `Undo` with it — and the clock does not stop for that. This is the
     measurement that decides the owner's ruling to keep BOTH controls: without the receipt a
     twenty-second promise would be good only for as long as you stand still. */
  await expandAll(page)
  await page.locator('.browse-row', { hasText: 'Not identified yet' }).first().click()
  await expect(page.locator('.inventory-lone')).toBeVisible()
  /* THE ROW IS WHAT WENT, NOT THE PANEL. Since D119 the lone card draws a one-copy group of its
     own, so a count of `.card-locations-owner` no longer says the rows were replaced — the claim
     this case is making is that THIS card's row is gone, which is what it now asserts. */
  await expect(copyRow(page, CARD_1)).toHaveCount(0)

  /* The slot's Undo went with the row it was drawn in; the receipt's did not. */
  await expect(page.locator('.inventory-receipt')).toHaveCount(0)
  const receiptUndo = receiptToast(page).getByRole('button', { name: 'Undo' })
  await expect(receiptUndo).toBeVisible()
  await receiptUndo.click()
  expect(wire.filter((call) => call.path.endsWith('/sold')).map((call) => call.body)).toEqual([
    {},
    { undo: true },
  ])
})

test('another device having sold the copy draws a receipt and no undo anywhere', async ({
  page,
}) => {
  const { store, sell } = sellableStore()
  /* `already_sold` IS NOT THIS DEVICE'S SALE (D13: two devices, one store). Answered as a
     success it would offer an Undo, and that Undo would reverse the OTHER device's real sale —
     putting a card back on TCGplayer that a buyer has paid for. */
  const wire = await open(page, BOXES, store, () => PRICING, () => ({
    status: 409,
    body: {
      error: {
        code: 'already_sold',
        message: 'Box 2, card 1 is already sold. Send {"undo": true} to reverse that sale.',
      },
    },
  }))

  const row = copyRow(page, CARD_1)
  await row.getByRole('button', { name: 'Mark sold' }).click()
  sell('2/1')

  /* A sale this device did not make leaves a receipt and nothing to press. It is a toast rather
     than a slot, because the slot has nothing to offer: there is no undo to draw there. */
  await expect(receiptToast(page)).toContainText('Already sold')
  await expect(receiptToast(page)).toContainText(
    'Another device sold this copy first, so nothing was written here.',
  )
  await expect(page.getByRole('button', { name: /Undo/ })).toHaveCount(0)
  // `stateLabel` — the human word, which is the register every state pill on this screen uses.
  await expect(row).toContainText('Sold')

  // One request, and no reversal was ever attempted.
  expect(wire.filter((call) => call.path.endsWith('/sold'))).toHaveLength(1)
})

test('a sale the store cannot put back offers no undo, in the row or on the receipt', async ({
  page,
}) => {
  const { store, sell } = sellableStore()
  /* `restores_to: null` is `sold_origin_unknown` seen one step early — the history cannot say
     what state the card was in before the sale, so the route says so at the moment of the sale
     rather than at a tap that would have failed. */
  const wire = await open(page, BOXES, store, () => PRICING, (box, index, undo) => ({
    status: 200,
    body: {
      position: `${box}/${index}`,
      box,
      index,
      undone: undo,
      state: 'sold',
      previous_state: 'identified',
      restores_to: null,
      listing: null,
      card: null,
    },
  }))

  const row = copyRow(page, CARD_1)
  await row.getByRole('button', { name: 'Mark sold' }).click()
  sell('2/1')

  await expect(receiptToast(page)).toContainText('Marked sold')
  /* THE STORE'S REASON STAYS OFF THE SCREEN (UX-207, D196): the receipt says it in words. */
  await expect(receiptToast(page)).toContainText('No undo for this one.')
  await expect(receiptToast(page)).not.toContainText('origin_unknown')
  await expect(page.getByRole('button', { name: /Undo/ })).toHaveCount(0)
  // `stateLabel` — the human word, which is the register every state pill on this screen uses.
  await expect(row).toContainText('Sold')
  expect(wire.filter((call) => call.path.endsWith('/sold'))).toHaveLength(1)
})

test('the retirement keeps its panel, because the reason is the write', async ({ page }) => {
  await open(page)

  /* D57 IS ABOUT ONE OF THE TWO DOORS AND THIS IS THE OTHER. The asymmetry is the ruling: a
     retirement without a reason is refused, so the four reason buttons are not an
     acknowledgement to dismiss, they are the only input the write has. */
  await copyRow(page, CARD_1).getByRole('button', { name: 'Retire' }).click()
  /* The panel is portalled out of the view and focus-trapped now; what it still is, is a modal
     dialog over a scrim with the four reasons in it, and none of that is optional. */
  await expect(page.locator('.bn-scrim')).toHaveCount(1)
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.locator('.inventory-retire-reasons')).toBeVisible()
})

// ------------------------------------------------ the copies are a way back into the walk

/** A SECOND BOX, FORTY CARDS DEEP, holding a third copy of the two-copy SKU at its far end.
 *
 *  D7 keeps every copy at its own position and says nothing about them sharing a box — the
 *  owner's store spreads them — and a walk-to is only worth testing when it changes what the
 *  strip is pointing at.
 *
 *  THE DEPTH IS THE POINT AND NOT DECORATION. The copy is the LAST of forty so that it sits
 *  below the fold of the walk's own scroller, which is the only condition under which "the jump
 *  scrolls to what it landed on" can fail. Against a one-card box that assertion passes whatever
 *  the code does — and this fixture was one card until the mutation run proved exactly that.
 *
 *  The thirty-nine in front of it carry no SKU, so `GET /search` puts them in no group and the
 *  copies list stays three rows: they are the length of the box and nothing else. */
const SPARES: Cards = Object.fromEntries(
  Array.from({ length: 40 }, (_, at) => {
    const index = at + 1
    const isCopy = index === 40
    return [
      `7/${index}`,
      card({
        index,
        state: 'identified',
        name: isCopy ? 'Thievul' : `Filler ${index}`,
        sku: isCopy ? '8937370' : null,
        section: 1,
        sectionStart: 1,
        sectionEnd: 40,
        box: 7,
        boxName: 'ME01 spares',
        boxTotal: 40,
      }),
    ]
  }),
)

const ELSEWHERE: Cards = { ...CARDS, ...SPARES }

/** Where the third copy sits — named once, because three assertions and a button label read it. */
const FAR = 'Box 7, Section 1, Card 40'
/* D218: `Walk to ${FAR}` is an aria-label — a sentence built AROUND the server's label — so it
   reads through `sayPlace` (`CardLocations.tsx`'s `OwnerRows`) the same way the sale toast
   does. `.position-parts`'s OWN aria-label stays raw (D41's one exception, verbatim), which is
   why FAR itself is untouched and only the button's name below uses the spoken form. */
const FAR_SPOKEN = 'Box 7, Section 1, Card 40'

const TWO_BOXES = {
  boxes: [
    ...BOXES.boxes,
    {
      box: 7,
      name: 'ME01 spares',
      sections: [1],
      state: 'open',
      capacity: null,
      fill: 40,
      next_index: 41,
      cards: 40,
      sold: 0,
      retired: 0,
      listed: 0,
      moved: 0,
      sections_detail: [{ section: 1, start: 1, end: 40, count: 40 }],
    },
  ],
}

const ACROSS: Store = { cards: ELSEWHERE, search: (query) => searchAnswer(query, ELSEWHERE) }

test('a copy in another box is reached by pressing its position, and the walk goes there', async ({
  page,
}) => {
  /* `?box=2`: the rail sorts by the hand and cards on hand now (D132), and box 7 holds more —
     this case is about the walk-to, so it starts where it always started, by the deep link. */
  await open(page, TWO_BOXES, ACROSS, () => PRICING, SALE, { route: '/#/inventory?box=2' })

  /* Three copies of one SKU in two boxes, and the walk is standing on the first. The row it is
     standing on offers no walk-to — it is already here — which is what makes the button that
     does appear unambiguous about where it goes. */
  const rows = page.locator('.card-locations-owner .card-locations-row')
  await expect(rows).toHaveCount(3)
  await expect(page.getByRole('button', { name: 'Walk to Box 2, Section 1, Card 1' })).toHaveCount(0)

  await page.getByRole('button', { name: `Walk to ${FAR_SPOKEN}` }).click()

  /* THE BOX, THE CARD AND THE PHOTOGRAPH ALL FOLLOW, which is the whole of the feature: every
     one of them is drawn for whatever the walk points at, so moving the mark is the only thing
     the press has to do. */
  await expect(page.locator('.browse-boxcell[aria-current="true"]')).toHaveAttribute('aria-label', /^ME01 spares/)
  await expect(page.locator('.card-locations-row.is-current .card-locations-label .position-parts')).toHaveAttribute('aria-label', FAR)
  await expect(page.locator('.browse-photo')).toHaveAttribute('src', /\/photo\/7\/40(\?|$)/)

  /* THE LANDING'S SECTION IS OPEN AND THE MARK IS WHERE IT CAN BE SEEN, in a box that arrived
     collapsed like every other and is forty rows deep. Both halves are the jump's own work: it
     opens the landing's section in the same pass it moves the mark, which is what leaves a
     rendered row for the scroll effect to find — that effect runs a commit earlier than the
     mark-is-never-hidden rule and does not depend on the folds, so a jump that left the opening
     to it would land forty rows down a scroller showing the top of the box. */
  const landed = page.locator('.browse-row[aria-current="true"]')
  await expect(landed).toBeVisible()
  await expect(landed).toBeInViewport()

  /* And the offer is now the other way round: the copy just left has one, the copy landed on
     does not. */
  await expect(page.getByRole('button', { name: 'Walk to Box 2, Section 1, Card 1' })).toBeVisible()
  await expect(page.getByRole('button', { name: `Walk to ${FAR_SPOKEN}` })).toHaveCount(0)
})

/* D218: `CardLocations.tsx:OwnerRows`'s "Walk to" button composes a sentence AROUND the
 * server's `Position.label` — this is `sayPlace`'s own site, moved into `position.ts` so
 * `Inventory.tsx`'s toast and this button read the same function. No U+00B7 (the middle dot)
 * or U+2022 (bullet) may survive into the accessible name. */
test('the walk-to button speaks the place, and never types the server\'s middle dot', async ({
  page,
}) => {
  await open(page, TWO_BOXES, ACROSS, () => PRICING, SALE, { route: '/#/inventory?box=2' })

  const goTo = page.getByRole('button', { name: `Walk to ${FAR_SPOKEN}` })
  const name = await goTo.getAttribute('aria-label')
  expect(name).not.toMatch(/[·•]/)
  expect(name).toBe(`Walk to ${FAR_SPOKEN}`)
})

test('a walk-to scrolls the walk and never the page — the top bars stay put', async ({
  page,
}) => {
  /* THE OWNER'S REPORT, 2026-08-29: "picking from a copy of a card moves the screen down a
     little to where it hides the top bars." It did, and by the document's whole scroll range.

     `Element.scrollIntoView` scrolls every scrollable ancestor and the last one is the
     document — and `.browse-map` is `position: sticky`, so scrolling the page cannot move a
     row inside it. The browser computed a delta from the row's geometry, spent it on the page,
     and the row did not move: the press revealed nothing and cost the nav, the screen's header
     and the search field. `BoxBrowse.tsx:scrollWithin` is the fix and carries the argument.

     MEASURED BEFORE AND AFTER RATHER THAN ASSERTED AS A CLASS NAME. Against the old code this
     case reads y 0 -> 280 with the nav at -280; the assertion is that the press moves the page
     by nothing at all, which is the only version of it a later refactor cannot satisfy by
     accident. */
  await open(page, TWO_BOXES, ACROSS, () => PRICING, SALE, { route: '/#/inventory?box=2' })

  /* THE PAGE IS AT REST AND THE PRESS IS DISPATCHED RATHER THAN CLICKED. Playwright's own
     `.click()` scrolls its target into view first, which is a page scroll this test cannot tell
     from the app's — and it is the reason the first attempt at this measurement read 280 both
     before and after and proved nothing. */
  const at = () => page.evaluate(() => window.scrollY)
  const navTop = () =>
    page.evaluate(() => document.querySelector('.app-nav')?.getBoundingClientRect().top ?? null)

  expect(await at()).toBe(0)
  expect(await navTop()).toBe(0)

  await page
    .getByRole('button', { name: `Walk to ${FAR_SPOKEN}` })
    .evaluate((button: HTMLElement) => button.click())

  await expect(page.locator('.browse-boxcell[aria-current="true"]')).toHaveAttribute('aria-label', /^ME01 spares/)

  /* THE PAGE HAS NOT MOVED, AND THE CARD ASKED FOR IS ON SCREEN ANYWAY — both halves, because
     either alone is satisfiable by doing the wrong thing. A screen that scrolled nothing and
     landed nowhere would pass the first; the old code passed the second. */
  expect(await at()).toBe(0)
  expect(await navTop()).toBe(0)
  await expect(page.locator('.card-locations-row.is-current .card-locations-label .position-parts')).toHaveAttribute('aria-label', FAR)
  await expect(page.locator('.browse-row[aria-current="true"]')).toBeInViewport()
})

test('a filtered walk gives up the filter rather than swallowing the jump', async ({ page }) => {
  /* THE ONE WAY THE COPIES AND THE WALK CAN DISAGREE ABOUT WHAT EXISTS. `do_search` renders a
     SKU's group WHOLE — every copy, including ones that did not match — so a copy of a matched
     SKU is always in the walk's own filter. The `sku: null` group is the exception and is built
     from the cards that matched THEMSELVES, and a named, never-emitted card is most of this
     store today. This stub is that shape: the query answers with the group minus the copy in
     box 7.

     WITHOUT THE GUARD THIS LANDS ON THE WRONG CARD, SILENTLY. The two follows-the-filter effects
     move the mark to the first visible row whenever the selection is not among them, so the
     press would draw some other card's photograph under some other card's position with nothing
     saying the one asked for was not reached. */
  await open(page, TWO_BOXES, {
    cards: ELSEWHERE,
    search: (query) => {
      const answer = searchAnswer(query, ELSEWHERE)
      if (query.trim().toLowerCase() !== 'me01') return answer
      return {
        query,
        groups: answer.groups.map((group) => ({
          ...group,
          copies: group.copies.filter((copy) => copy.key !== '7/40'),
        })),
      }
    },
  })

  await page.locator('.search-field-input').fill('ME01')

  /* The filter reaches box 2 alone. Box 7 keeps a cell — the rail says what a query did to
     EVERY box now, which is a different answer to "where else could this be" — but it is not a
     box the filtered walk can be taken to: its cell is disabled, and only box 2 carries a match
     count. What must not happen is a row of box 7's in the walk, and there is none. */
  const cells = page.locator('.browse-boxcell')
  await expect(cells).toHaveCount(2)
  await expect(page.getByRole('button', { name: /^ME01 commons/ })).toBeEnabled()
  await expect(page.getByRole('button', { name: /^ME01 spares/ })).toBeDisabled()

  await page.getByRole('button', { name: `Walk to ${FAR_SPOKEN}` }).click()

  /* THE CARD ASKED FOR IS THE CARD REACHED — asserted before anything about the query, because
     this is the claim that matters and the wrong-card landing is what fails it: unguarded, the
     mark falls to the first row the filter still holds and this reads `Box 2 · Section 1 ·
     Card 1` under box 2's photograph. */
  await expect(page.locator('.card-locations-row.is-current .card-locations-label .position-parts')).toHaveAttribute('aria-label', FAR)
  await expect(page.locator('.browse-boxcell[aria-current="true"]')).toHaveAttribute('aria-label', /^ME01 spares/)

  // And the query goes, because it was a way of finding the card and the card has been found.
  await expect(page.locator('.search-field-input')).toHaveValue('')

  /* AND THE SECTION IS OPEN UNDERNEATH IT, which is the ordering claim `BoxBrowse.tsx` makes at
     the landing effect: clearing a query fires the collapse-everything effect in the same pass
     the jump lands in, and the jump is declared after it so the open is the final word. Swap the
     two and this row is drawn inside a shut section. */
  await expect(page.locator('.browse-row[aria-current="true"]')).toBeVisible()
})

// ------------------------------------------------------------------- collapsible sections

test('the walk arrives with only the planted selection\'s section open, and the control says which press does what', async ({
  page,
}) => {
  await open(page)

  const folds = page.locator('.browse-sectfold')
  await expect(folds).toHaveCount(2)

  /* THIS TEST USED TO BE `sections start collapsed, and the one holding the selection is open`,
   * and it asserted nth(0) expanded with three rows drawn. That was the bug, not the contract.
   * The loader plants a selection on the first row and an effect opened its section for it, so
   * the screen arrived PARTLY expanded while the control beside it offered `expand all` — the
   * first press expanded, and only the second reached the collapsed list the press was for.
   * Measured on box 1 (3 sections, 53 cards) before the fix: 25 rows on load, 53 after one
   * press, 0 after two. The owner reported it as "you gotta click it once or twice for it to be
   * working right".
   *
   * THE NEW ASSERTION IS STRICTLY STRONGER. The old one pinned one fold open and one shut and
   * said nothing about WHY, so it would have passed just as happily with a render-time override
   * as with an effect. This pins both folds and the row count, which is a state with exactly one
   * cause. The invariant the old behaviour defended — the mark is never on a row nobody can see
   * — did not go anywhere: it is asserted below against a selection that MOVES, which is the
   * only case it was ever about. */
  /* AND THE ANSWER TO IT CHANGED WITH THE REBUILD, WHICH IS A DIFFERENT ANSWER TO THE SAME
   * DEFECT rather than the defect coming back. The walk opens the section its planted selection
   * sits in — the rule this file asserts a few cases down, that the mark is never on a row
   * nobody can see, applied to the first mark as well as to a moved one — and everything else
   * arrives shut. What made the old behaviour a bug was not the open section: it was that the
   * control beside it said `expand all` while a section was already expanded, so the first press
   * did nothing a person could see and the second was the one that worked.
   *
   * SO THE CONTROL IS WHAT IS PINNED HERE, and that is the stronger half of the old assertion:
   * it names the press it is about to perform. One section open, every other shut, and a control
   * that says `collapse all` because collapsing is what pressing it does. */
  await expect(folds.nth(0)).toHaveAttribute('aria-expanded', 'true')
  await expect(folds.nth(1)).toHaveAttribute('aria-expanded', 'false')
  // Section 1 holds five of the seven records, and section 2's two are folded away.
  await expect(page.locator('.browse-row')).toHaveCount(5)
  await expect(page.locator('.browse-row[aria-current="true"]')).toBeVisible()

  const fold = page.getByRole('button', { name: /collapse all/i })
  await expect(fold).toBeVisible()
  await fold.click()
  await expect(page.locator('.browse-row')).toHaveCount(0)
  await expect(page.getByRole('button', { name: /expand all/i })).toBeVisible()

  /* And nothing is lost by shutting it: the selected card's copies, its photograph and its two
     doors out of inventory are all still drawn beside the list. Only its ROW is folded. */
  await expect(page.locator('.card-locations-owner')).toBeVisible()
})

test('the fold is presentation, never a filter — a step into a shut section opens it', async ({
  page,
}) => {
  await open(page)

  /* The rule this asserts is the one that keeps every other control working: `visible` is
     untouched by the fold, so End walks to the last card of the BOX and the section it lands in
     opens rather than hiding the mark. */
  await page.locator('.browse-list').focus()
  await page.keyboard.press('End')

  await expect(page.locator('.browse-sectfold').nth(1)).toHaveAttribute('aria-expanded', 'true')
  /* Named rather than numbered. This read `/5/` while the fixture set `card: index`; `card` is
     the slot inside its section now (as the server sends it), so the last row of this box draws
     `Card 2` of section 2 and a digit no longer identifies it. Pyroar is index 5 and nothing
     else, so this pins the same row at least as tightly. */
  await expect(page.locator('.browse-row[aria-current="true"]')).toContainText('Pyroar')
})

test('UX-227 — the walk keeps the row it steps onto in view, down to the last card of a forty-card box', async ({ page }) => {
  /* THE RAIL RAN PAST THE BOTTOM OF THE WINDOW AT REST: it is sticky, but under the page head its
     window-tall height ended below the fold, and the list's last rows with it. A step to the end
     of the box scrolled the list to its end and left the row out of sight. */
  await open(page, TWO_BOXES, ACROSS, () => PRICING, SALE, { route: '/#/inventory?box=7' })
  await expandAll(page)
  await page.locator('.browse-list').focus()
  await page.keyboard.press('End')
  const current = page.locator('.browse-row[aria-current="true"]')
  await expect(current).toBeInViewport({ ratio: 1 })
  expect(await page.evaluate(() => window.scrollY)).toBe(0)
})

test('expand all opens every section and collapse all shuts them', async ({ page }) => {
  await open(page)

  /* THE WALK ARRIVES WITH ONE SECTION OPEN — the planted selection's — so the roster begins by
     shutting it. The control names that press rather than offering `expand all` over a screen
     that is already partly expanded, which is the owner's own report and the case above. */
  await page.getByRole('button', { name: 'collapse all' }).click()
  await expect(page.locator('.browse-row')).toHaveCount(0)

  await page.getByRole('button', { name: 'expand all' }).click()
  /* SEVEN ROWS AND FIVE CARDS ON HAND (D58). The walk draws every RECORD the box holds,
     departed ones included — a sold card is still findable, still reversible past its
     twenty-second window, and still where the operator remembers it. What it does not draw
     for one is a number. */
  await expect(page.locator('.browse-row')).toHaveCount(7)

  /* COLLAPSE ALL SHUTS EVERY SECTION, INCLUDING THE ONE HOLDING THE SELECTION.
   *
   * This assertion used to read `toHaveCount(3)` and explained itself as the force-open
   * "which is what makes collapsed-by-default safe rather than hostile". It was neither: the
   * owner reported the fold as clickable and doing nothing, and this was half the reason —
   * `isOpen` re-opened the selected section on every render, so an explicit fold recorded a
   * close that the next paint discarded. A control whose label says `collapse all` and which
   * leaves a section open is not safe, it is lying.
   *
   * The invariant the override carried is real and did not go: the mark must never sit on a
   * row nobody can see. It moved to where it belongs, an effect that opens the landing
   * section when the selection MOVES — asserted below. Navigation is an automatic
   * consequence; folding is an act; they are not decided in the same expression. */
  await page.getByRole('button', { name: 'collapse all' }).click()
  await expect(page.locator('.browse-row')).toHaveCount(0)

  await page.getByRole('button', { name: 'expand all' }).click()
  await expect(page.locator('.browse-row')).toHaveCount(7)
  await page.getByRole('button', { name: 'collapse all' }).click()

  /* ONE PRESS FROM A PARTIAL STATE, which is the other half of the owner's report and the half
   * a collapsed default does not fix on its own. A step into a shut section opens it, so the
   * walk is partly expanded again a single arrow key later — and while the control read
   * `expand all` from there, reaching a collapsed list still cost two presses. It now reads ANY
   * rather than EVERY, so it always names what one press will do. */
  await page.locator('.browse-list').focus()
  await page.keyboard.press('End')
  await expect(page.locator('.browse-row')).toHaveCount(2)

  await expect(page.getByRole('button', { name: 'collapse all' })).toBeVisible()
  await page.getByRole('button', { name: 'collapse all' }).click()
  await expect(page.locator('.browse-row')).toHaveCount(0)
})

test('a search opens every section holding a match, and clearing it gives the walk back', async ({
  page,
}) => {
  await open(page)
  /* Shut, so what the query opens is the query's doing and not the walk's own planted
     selection. */
  await page.getByRole('button', { name: 'collapse all' }).click()
  await expect(page.locator('.browse-row')).toHaveCount(0)

  /* The owner's second ask, verbatim: "i want if i search for a card, all results of that card
   * in whatever/all section/box are expanded (immediately findable)". `ME01` is the set hint —
   * one of the six fields `do_search` matches on — and it reaches copies in BOTH of this box's
   * sections, which is the only shape that can test the ask: a match folded away in a section
   * the walk is not standing in is exactly what "immediately findable" rules out, and a query
   * confined to one section would prove nothing about it. */
  await page.locator('.search-field-input').fill('ME01')

  const folds = page.locator('.browse-sectfold')
  await expect(folds.nth(0)).toHaveAttribute('aria-expanded', 'true')
  await expect(folds.nth(1)).toHaveAttribute('aria-expanded', 'true')
  // Six matches — card 2 carries no SKU, so it is in no group — every one on screen, no press.
  await expect(page.locator('.browse-row')).toHaveCount(6)

  /* AND THE EXPANSION BELONGS TO THE QUERY. Cleared, the walk is back to the state it opens in
     rather than a half-open shape nobody chose — one resting state to learn instead of two.
     That state is the planted selection's section and nothing else, which is the case above. */
  await page.locator('.search-field-input').fill('')
  await expect(page.locator('.browse-sectfold').nth(0)).toHaveAttribute('aria-expanded', 'true')
  await expect(page.locator('.browse-sectfold').nth(1)).toHaveAttribute('aria-expanded', 'false')
  await expect(page.locator('.browse-row')).toHaveCount(5)
})

test('moving the selection opens the section it lands in, so the mark is never hidden', async ({
  page,
}) => {
  await open(page)

  /* The other half of the fold fix. With everything shut, a key that moves the selection has
   * to open whatever it lands in — otherwise collapsed-by-default would let the walk put the
   * mark on a row nobody can see, which is the failure the old render-time override was
   * written to prevent and the one thing that must survive its removal. */
  await page.getByRole('button', { name: 'collapse all' }).click()
  await expect(page.locator('.browse-row')).toHaveCount(0)

  await page.locator('.browse-list').focus()
  await page.keyboard.press('ArrowRight')

  await expect(page.locator('.browse-row').first()).toBeVisible()
  await expect(page.locator('.browse-row')).not.toHaveCount(0)
})

// ------------------------------------------------------- two depths on one row (D20, D30)

test('a copy row draws how far into the box AND how far into the section', async ({ page }) => {
  await open(page)

  /* THE OWNER'S SCREENSHOT IS THE ARGUMENT, and it was two rows of one card: `Section 1 · Card
   * 1` with the marker hard left and `Section 3 · Card 1` with it hard right — both of them the
   * FIRST card of their section, drawn as opposite ends of the box. The box scale is the one
   * that misleads at exactly the moment a divider matters, and the owner's ruling was "yes,
   * while retaining box depth too", so the second bar is additive and the first is untouched.
   *
   * Both captions are asserted on the same row, in order, which is what pins them as two scales
   * rather than one replaced by the other. */
  /* THE LENS IS ON EVERY ROW, WHICH IS WHAT D119 BOUGHT. This case used to count two bars — one
     in the location card, one in the list — and the TOTAL is still two for a two-copy card, for
     an entirely different reason. A total cannot tell those apart: two bars on one row and none
     on the other is the same number. So the claim is per row, and the total is asserted after
     it rather than instead of it. */
  const rows = page.locator('.card-locations-owner .card-locations-row')
  await expect(rows).toHaveCount(2)
  await expect(rows.nth(0).locator('.position-bar')).toHaveCount(1)
  await expect(rows.nth(1).locator('.position-bar')).toHaveCount(1)
  const bars = page.locator('.card-locations-owner .position-bar')
  await expect(bars).toHaveCount(2)

  const first = bars.nth(0).locator('.position-bar-text')
  /* NO "SO FAR" ON THE BOX LINE (owner's ruling, 2026-09-19 — see the case below this one for
     the full argument): `#1 of 5`, not `#1 of 5 so far`. */
  await expect(first.nth(0)).toHaveText('Section 1 of 2')
  /* SETTLED SECTION, SO THE DENOMINATOR IS SLOTS. Section 1 runs 1..3 and the box holds 5, so
     its far bound is a divider with cards behind it: three slots today and three next week. */
  await expect(first.nth(1)).toHaveText('Section 1card 1 of 3')

  const second = bars.nth(1).locator('.position-bar-text')
  await expect(second.nth(0)).toHaveText('Section 1 of 2')
  await expect(second.nth(1)).toHaveText('Section 1card 3 of 3')

  /* The section track carries no dividers of its own — a section is not divided by anything,
     and that absence is one of the three cues telling the two scales apart at a glance. */
  await expect(bars.nth(0).locator('.position-bar-sectiontrack .position-bar-segment')).toHaveCount(0)
})

test('the last section of an open box counts what is in it, and the box line drops "so far"', async ({ page }) => {
  await open(page)
  await expandAll(page)
  await page.locator('.browse-row', { hasText: 'Pyroar' }).click()

  /* THE OTHER DENOMINATOR, AND IT IS D20 AT SECTION SCALE. Section 2 is declared 4..5 in a box
   * that holds 5 and is not sealed, so its far bound is the end of an open box: it is where the
   * next capture lands and it will be wider tomorrow. Measured against its fill so far and
   * labelled `so far` — `sectionDepthOf`'s own growing-section word, UNTOUCHED by the ruling
   * below, which is about the BOX line only.
   *
   * NO "SO FAR" ON THE BOX LINE (owner's ruling, 2026-09-19: "this... needs to be removed
   * everywhere it exists" — `#20 of 34` stays). RE-AIMED, NOT DROPPED: this case used to be the
   * guard AGAINST dropping the two words from the box line, reasoning that an open box's own
   * denominator is honestly "so far" while the walk's is not. The owner's later ruling overrides
   * that argument outright — `sentenceOf`'s own `soFar` flag was never wired to `false` by any
   * caller in the first place, so the box line had been reading `so far` unconditionally on
   * EVERY open box, walk included, the whole time; the flag is deleted rather than fixed
   * forward. This case is now the opposite guard: neither line says it again. The owner's
   * second ruling the same evening — "drop it everywhere" — reached the section line too: a
   * growing section reads `card 2 of 2`, a settled one `card 2 of 2 slots`. */
  const bar = page.locator('.card-locations-row.is-current .position-bar')
  await expect(bar.locator('.position-bar-text').nth(0)).toHaveText('Section 2 of 2')
  await expect(bar.locator('.position-bar-text').nth(1)).toHaveText('Section 2card 2 of 2')

  /* One accessible name carrying both, because `role="img"` hides every descendant — a screen
     reader is told the second scale here or not at all. */
  await expect(bar).toHaveAttribute('aria-label', 'Card 2 of 2, Section 2 · card 2 of 2')
})

test('the card with no group gets both depths too', async ({ page }) => {
  await open(page)
  await expandAll(page)
  await page.locator('.browse-row', { hasText: 'Not identified yet' }).first().click()

  /* THE BRANCH THAT NEARLY MISSED OUT — a card with no SKU and no name, which `GET /search`
   * cannot reach at all, so it draws through the lone-copy fallback rather than through a group.
   *
   * ITS TITLE SAID `it is most of the store` UNTIL 2026-09-07, AND THAT HAD STOPPED BEING TRUE.
   * The figure this case was written against — 629 of 682 records captured and never identified,
   * 92% — was measured on the owner's Mac when the pipeline had not yet run over the boxes. Read
   * from `inventory/store.sqlite` on 2026-09-07: 1,625 cards, 1,553 carrying a SKU, 65 with a
   * name and no SKU (which the search reaches BY the name), and **7** with neither. Four tenths
   * of one percent. The branch is a real edge case and is still worth a case; what it is not is
   * the common screen, and a stale measurement arguing for coverage is worth less than the
   * coverage itself. Since D119 it draws a synthesised one-copy group through `CardLocations`,
   * so the bars below are the ROW's, in the same shape every identified card gets. */
  const bar = page.locator('.card-locations-row.is-current .position-bar')
  await expect(bar).toHaveCount(1)
  await expect(bar.locator('.position-bar-text').nth(0)).toHaveText('Section 1 of 2')
  await expect(bar.locator('.position-bar-text').nth(1)).toHaveText('Section 1card 2 of 3')

  /* AND ITS LABEL IS RANKED, WHICH IS THE HALF THIS CASE DID NOT LOOK AT (D71). This test reaches
   * the lone-copy branch and asserted only the two bars, so the label beside them went on being
   * the raw server string in the utility face — D41's treatment shipped to five sites and this
   * was not one of them. Nothing failed, because nothing here read it. */
  const lone = page.locator('.card-locations-row.is-current .card-locations-label .position-parts')
  await expect(lone).toHaveCount(1)
  await expect(lone).toHaveAttribute('aria-label', 'Box 2, Section 1, Card 2')
  await expect(page.locator('.card-locations-row.is-current .card-locations-label .position-num')).toHaveText('2')
  await expect(page.locator('.card-locations-row.is-current .card-locations-label .position-plain')).toHaveCount(0)
})

test('a sold card with no group is ranked too, and its lens keeps the box but loses the mark', async ({ page }) => {
  /* THE THIRD SCREEN THAT RENDERS "ONE COPY AND WHERE IT IS", AND THE ONE D68 MISSED (D71).
   * That entry deleted an empty track captioned `where this sits in the box is not known yet`
   * from the copies list, on the grounds that a bar cannot draw a card that is in no place and
   * that the walk has omitted it since D58 — two screens agreeing about one card. This panel is
   * the third, it kept drawing the bar, and its caption had by then become `no longer in the box`,
   * which is a true sentence under an empty track that still reads as a measurement that failed.
   *
   * BOTH HALVES WERE FOUND BY PRESSING THE BUTTON IN A BROWSER over a real store, not by a spec:
   * every fixture that reaches the lone panel had a live card in it, and every fixture with a
   * departed card had a name and a SKU and so drew a group instead. The two conditions had never
   * been in one record. This case is that record. */
  const shared: Cards = {
    ...CARDS,
    '2/4': card({
      index: 4,
      state: 'sold',
      name: null,
      sku: null,
      section: 1,
      sectionStart: 1,
      sectionEnd: 3,
    }),
  }
  await open(page, BOXES, { cards: shared, search: (query) => searchAnswer(query, shared) })
  await expandAll(page)
  await page.locator('.browse-row').nth(3).click()

  /* No name and no SKU, so there is no group to FETCH — the screen never asks, and the stub above
     is the type's, not this case's. That is the branch: this is the lone panel rather than the
     copies list, the same one the case above walks, with the card sold. */
  await expect(page.locator('.inventory-lone')).toHaveCount(1)

  const lone = page.locator('.card-locations-row.is-current .card-locations-label .position-parts')
  /* SINCE THE OWNER'S BOX-NAME RULING (D259) a departed card keeps the
     place it left (box, section, card within it), its figure struck through; no word and no
     store key. Its accessible name is in the past tense. */
  await expect(lone).toHaveAttribute('aria-label', 'Was at Box 2, Section 1, Card 4')
  /* THE BOX'S NAME RIDES THE FIRST PATH LINE, which is the copies list's own `boxNote` and is
     what every other row on this screen has always drawn (see the departed rows asserted near the
     end of this file, same string). The location card drew it as a separate element beside the
     `LOCATION` label; D119 did not lose it, it moved into the address — and since D132 the name
     LEADS and the index is the note beside it, on every row alike. */
  await expect(page.locator('.card-locations-row.is-current .card-locations-label .position-path')).toHaveText('BOX ME01 commonsSECTION 1')
  await expect(page.locator('.card-locations-row.is-current .card-locations-label .position-num')).toHaveText('4')
  await expect(page.locator('.card-locations-row.is-current .card-locations-label .position-parts')).toHaveAttribute('data-departed', 'true')
  await expect(page.locator('.card-locations-row.is-current .card-locations-label .position-plain')).toHaveCount(0)

  /* AND THE LENS, DRAWN AS A COPY THAT HAS LEFT (D118, amending D68). This assertion read
     `toHaveCount(0)` until the owner reported the screen shaking under the sale, and what was
     shaking was this: 85px of lens disappearing on the press collapsed the panel by 98 and moved
     131 elements. D68 deleted an EMPTY TRACK captioned `where this sits in the box is not known
     yet` — a measurement that had failed — and what stands here now is not that object. The
     section the copy left is drawn, the caption says `no longer in the box`, the second scale
     says the copy is in none of the section's slots, and the mark that would lie about a
     position is the one thing removed. D68's ruling was about drawing a card where it is not;
     this draws the box, which is still there.
     READ OFF THE ROW SINCE D119, which deleted the location card this used to name. */
  const lens = page.locator('.card-locations-row.is-current .position-bar')
  await expect(lens).toHaveCount(1)
  await expect(lens).toHaveAttribute('data-gone', 'true')
  /* Both scales, both unmarked — the box track and the section track it zooms into. */
  await expect(lens.locator('.position-bar-marker[data-gone]')).toHaveCount(2)

  /* THE TAIL IS SHORT AND NEVER CONTRADICTS THE RULER STILL DRAWN UNDER IT (the owner's box
     WB1 R2 defect: the old two facts read `3 slots · this copy is not in one`, long enough to
     force the section's own NAME to be the part that ellipsized). One neutral phrase — this
     `sectionDepthOf` has no sold/retired distinction to read off a bare `Place` — shorter than
     what it replaces (D194). */
  const sectionText = lens.locator('.position-bar-text-section')
  await expect(sectionText.locator('.position-bar-cap-head')).toHaveText('Section 1')
  await expect(sectionText.locator('.position-bar-cap-tail')).toHaveText('was card 4')

  /* AND THE TAIL IS THE PART THAT MAY CLIP, NEVER THE HEAD. `PositionBar.css` had this
     backwards; swapped, the section's own name is pinned at its full width (`flex: none`) and
     only the tail can shrink and ellipsize. */
  const flexStyles = await sectionText.evaluate((el) => {
    const head = el.querySelector('.position-bar-cap-head') as HTMLElement
    const tail = el.querySelector('.position-bar-cap-tail') as HTMLElement
    return {
      headFlexShrink: getComputedStyle(head).flexShrink,
      tailFlexShrink: getComputedStyle(tail).flexShrink,
      tailTextOverflow: getComputedStyle(tail).textOverflow,
    }
  })
  expect(flexStyles.headFlexShrink).toBe('0')
  expect(flexStyles.tailFlexShrink).toBe('1')
  expect(flexStyles.tailTextOverflow).toBe('ellipsis')
})

test('a departed card draws no number, and the cards behind it count past it', async ({
  page,
}) => {
  await open(page)
  await expandAll(page)

  /* D58 ON THE SCREEN. The fixture box holds seven records and two of them have left — card 4
   * sold, card 5 retired — so the box holds five cards and the numbers count those five.
   *
   * THE PAIR IS THE ASSERTION. A departed card must not draw the number it held, because that
   * number now belongs to the card that closed up behind it: draw both and the operator has
   * two `Card 3`s in one box and a way to open the wrong slot. So this reads the left cell of
   * every row in order — the number, or the departed fact where there is no number — and the
   * whole list is the claim rather than any one row of it. */
  /* AND THE OTHER HALF IS D68, WHICH THIS LIST WROTE THE ARGUMENT FOR BEFORE ANYONE READ IT.
   * The two expected values here were the identical string — `Box 2 · departed` twice, in a
   * spec asserting that the walk tells its rows apart — and on the owner's own store 11 of 12
   * departed records sit in a group that does exactly that. The store key is what separates
   * them; `join.departed_label` now ends on it and this cell drops the box, which the walk has
   * already named twice above it and which would otherwise ellipsise the key off the end at
   * 177px into a 169px cell. */
  const slots = page.locator('.browse-row .browse-row-position')
  await expect(slots).toHaveCount(7)
  /* THE FIGURE IS SIGILLED (`#3`) AND A DEPARTED ROW CARRIES ITS STORE KEY INSTEAD — the same
     two facts the old spelling carried, in the register the walk draws numbers in. What must
     hold is what it always was: no departed row shows a slot number, the two departed rows are
     told apart from each other, and the cards behind them count past rather than around. */
  /* A departed row keeps the number of the place it left, struck through (the owner's box-name
     ruling); the rows behind still count past it. */
  await expect(slots).toHaveText(['#1', '#2', '#3', '#4', '#5', '#1', '#2'])

  /* AND THE SECTION KEEPS THEM. A departed record belongs to a real part of a real box, so it
   * sits in the section it sat in rather than under a third heading that is not a section —
   * five rows in section 1, two in section 2. */
  await expect(page.locator('.browse-sectfold')).toHaveCount(2)

  /* THE STORE KEY IS UNTOUCHED AND IS WHAT EVERY WRITE STILL AIMS BY, which is the half of
   * D58 that is invisible on screen and load-bearing everywhere else: the sixth row draws
   * `Card 1` of section 2 and its photograph is still `/photo/2/6`. Nothing was renamed. */
  await page.locator('.browse-row').nth(5).click()
  await expect(page.locator('.browse-photo')).toHaveAttribute('src', /\/photo\/2\/6\?card=cap-6$/)
  await expect(page.locator('.card-locations-row.is-current .card-locations-label .position-parts')).toHaveAttribute(
    'aria-label',
    'Box 2, Section 2, Card 1',
  )

  /* A departed card's own panel says where the record belongs and that there is no slot —
   * `join.departed_label`'s string, and the one composer of it. The position bar cannot draw
   * a card that is in no place, so it is absent rather than drawn at zero. */
  await page.locator('.browse-row').nth(3).click()

  /* THE TREATMENT APPLIES, AND THIS CASE USED TO FLOOR THE OPPOSITE (D71). It read the raw
   * string as text and asserted `.position-parts` count ZERO — a floor on the component
   * REFUSING a departed label — and what that refusal actually drew was the pre-D41 plain
   * string: `Box 2 · departed` at 44px in the face the address is drawn in, wrapped onto two
   * lines, in the panel D41 exists to have unwrapped. A sold card was the only card left on
   * this screen rendered the old way, and the owner found it by selling one.
   *
   * WHAT THOSE ASSERTIONS WERE PROTECTING IS THE FIGURE, and it is asserted below unweakened:
   * the guard that refused the label was aimed at the word `departed` being promoted to 44px,
   * and refusing the whole treatment was never the only way to stop that. */
  const panel = page.locator('.card-locations-row.is-current .card-locations-label .position-parts')
  await expect(panel).toHaveCount(1)
  await expect(panel).toHaveAttribute('aria-label', 'Was at Box 2, Section 1, Card 4')
  await expect(page.locator('.card-locations-row.is-current .card-locations-label .position-plain')).toHaveCount(0)
  /* The lens stays and its mark leaves (D118, amending D68) — see the case above for the whole
     argument. What this case is about is the LABEL, and the lens is asserted here only so a
     later change cannot take it away again without one of these two saying so. */
  await expect(page.locator('.card-locations-row.is-current .position-bar[data-gone]')).toHaveCount(1)

  /* NO FIGURE AT ALL, WHICH IS D58 AND D68 IN ONE ASSERTION. D58 refuses the slot number for a
   * card that has left; D68 adds that the store key must not take that number's place. Both are
   * the same statement about this panel — nothing is drawn at `--pos-slot`'s 44px — and the void
   * is what holds the column open in its stead. */
  await expect(page.locator('.card-locations-row.is-current .card-locations-label .position-num')).toHaveText('4')
  await expect(page.locator('.card-locations-row.is-current .card-locations-label .position-parts')).toHaveAttribute('data-departed', 'true')

  /* AND THE STATE AND THE KEY ARE RANKED RATHER THAN LEFT AS A STRING WITH A NOTE UNDER IT.
   * `DEPARTED B2 #4` is the same key/value pair as the `BOX 2` above it and as the `SECTION 1` it
   * stands in for, which is what makes a departed row cost the same two path lines a live one
   * costs. */
  const path = page.locator('.card-locations-row.is-current .card-locations-label .position-path')
  await expect(path).toHaveText('BOX ME01 commonsSECTION 1')

  /* THE RE-RANK ITSELF IS ASSERTED ON `#/gallery` AND NOT HERE, AND THE MOVE IS D119's (see
   * `gallery.spec.ts`, `a label with no figure re-ranks its path`). `PositionLabel.css`'s rule
   * fires under `lead='path'` alone, and the location card that used to draw this label that way
   * is deleted: the copies list, the order picker and the walk are all `lead='slot'`, so no
   * screen in the product renders the combination any more and a comparison here would measure
   * 11px against 11px and pass for the wrong reason. The kit sheet is the only renderer left,
   * which is where a rule with one renderer has to be asserted. */
})

test('the census greps to the store, and the identity line says what the box holds', async ({
  page,
}) => {
  await open(page)
  await openBoxOps(page)

  /* A LIVE DEFECT THIS CATCHES, FOUND BY LOOKING AT THE SCREEN AND BY NOTHING ELSE. D58 moved
   * the identity line onto `on_hand` — what the box holds — and the two readings shared one
   * local called `fill`, so the CENSUS moved with it: box 3 drew `FILL 29` beside
   * `NEXT INDEX 40` over a store whose `fill` is 39. `BoxOps.tsx` promises in its own comment
   * that these key names grep to `inventory.json`, and 29 is under no key in that file.
   *
   * SO THE PAIR IS THE ASSERTION, on one screen at one moment: the census is the store's own
   * three numbers verbatim, and the identity line is the one the screen divides by. They are
   * equal until a card leaves the box, which is exactly why one variable could serve both and
   * why only a box with a departure can tell them apart. */
  /* THE CENSUS IS A LABELLED FIGURE PER FIELD NOW, and it says more of them than it did — so
     each is read by the label above it rather than by its place in a strip. The numbers are the
     store's own, verbatim, which is the whole of the claim: `Captured` is the record count,
     `Fill` the allocator's high-water mark, and neither is the five the box holds. */
  await expect(censusValue(page, 'Captured')).toHaveText('7')
  await expect(censusValue(page, 'On hand')).toHaveText('5')
  await expect(censusValue(page, 'Sold')).toHaveText('1')
  await expect(censusValue(page, 'Retired')).toHaveText('1')
  await expect(censusValue(page, 'Fill')).toHaveText('7')
  await expect(censusValue(page, 'Next capture')).toHaveText('8')

  /* THE NOTES UNDER FILL AND NEXT CAPTURE ARE CUT (UX-259, cut list #17): the figures stand on
     their labels, and the store's word "index" is not one of them (D196). */
  await expect(page.locator('.boxops-census-cell', { hasText: 'Fill' }).locator('.boxops-census-note')).toHaveCount(0)

  /* Five, not seven: two of the seven records have left. THE CENSUS TRIAD (D41) REACHED THIS
     PANEL — `on hand` is a `bn-stat` figure now, the same primitive `CardLocations`' own three
     figures use, so the assertion reads the figure and its label as the two spans they now
     are rather than one string. */
  await expect(
    page.locator('.boxops-identity-line .boxops-stat', { hasText: 'on hand' }).locator('.bn-stat-value'),
  ).toHaveText('5')
  await expect(
    page.locator('.boxops-identity-line .boxops-stat', { hasText: 'on hand' }).locator('.bn-stat-label'),
  ).toHaveText('on hand')
})

test('the box panel draws its census as bn-stat figures, not the old dotted line', async ({
  page,
}) => {
  /* THE OWNER'S RULING, 2026-09-19: this rail still drew the OLD dotted line — a muted string
     of `label value` parts joined by a CSS `::before` interpunct — while the card pane beside
     it already drew D41's census-triad, three `bn-stat` tiles. This is the receipt for the fix,
     asserted the way a mutation catches a reversion: the OLD markup (`.boxops-identity-part`,
     one interpunct-joined string per fact) must be GONE, and the new one (`.boxops-stat`, a
     `bn-stat-value`/`bn-stat-label` pair per fact) must be there, four figures for this fixture
     box — on hand, sold, retired, captured. Run against a `.bak` of the pre-fix `BoxOps.tsx`/
     `BoxOps.css` (never `git stash`, which is shared with every worktree of this clone), this
     case is RED: the pre-fix panel has zero `.boxops-stat` nodes and four `.boxops-identity-part`
     nodes instead. */
  await open(page)
  await openBoxOps(page)
  await page.keyboard.press('Escape')
  await expect(page.getByRole('button', { name: 'Rename' })).toHaveCount(0)

  await expect(page.locator('.boxops-identity-part')).toHaveCount(0)

  const stats = page.locator('.boxops-identity-line .boxops-stat')
  await expect(stats).toHaveCount(4)
  await expect(stats.locator('.bn-stat-value')).toHaveText(['5', '1', '1', '7'])
  await expect(stats.locator('.bn-stat-label')).toHaveText(['on hand', 'sold', 'retired', 'captured'])

  /* No state pill: a box has no lid (`D-sealed-boxes-removed`). */
  await expect(page.locator('.boxops-identity .boxops-state')).toHaveCount(0)

  /* AND THE FOUR FIGURES SIT ON ONE ROW AT 1440 — the rail is 300px and this is the width the
     brief named as the floor for it. */
  await page.setViewportSize({ width: 1440, height: 900 })
  const tops = await stats.evaluateAll((nodes) => nodes.map((n) => n.getBoundingClientRect().top))
  expect(new Set(tops.map((t) => Math.round(t))).size).toBe(1)
})

// ------------------------------------------------------- the box's operations, as rows (D20)

test('a box has no lid: Manage box offers no seal and no re-open (D-sealed-boxes-removed)', async ({
  page,
}) => {
  await open(page)
  await openBoxOps(page)
  /* The owner's ruling, 2026-09-25: "what was the point of sealed boxes? lets kill this". Red
     before the removal: the sheet drew `Seal box` with `freezes at 7`. */
  await expect(page.getByRole('button', { name: /^Seal box/ })).toHaveCount(0)
  await expect(page.getByRole('button', { name: /^Re-open box/ })).toHaveCount(0)
  await expect(page.locator('.boxops-sheet')).not.toContainText(/sealed/i)
})

test('the operations are rows on one edge, and the delete is the only bordered one', async ({
  page,
}) => {
  await open(page)
  await openBoxOps(page)

  /* THE DEFECT THIS PREVENTS IS THE ONE THE OWNER SENT A SCREENSHOT OF. These were
     shrink-to-fit chips at 79 / 110 / 109 / 267px inside a 360px column — six widths against a
     list, a meta line and two hairlines that all run the full measure. Asserted as ONE EDGE
     rather than as a width, so the track stays free to be re-cut. */

  /* THE ROSTER RATHER THAN A BARE COUNT, AND THIS FILE EARNED THE CHANGE. `toHaveCount(4)`
     stood here until 2026-09-01, when D83's `Move to box` made it five and turned
     `make design-check` red on main — the commit that added the control touched no file under
     `app/tests/` at all, and nothing on the commit path reads this spec (docs/GATES.md step 7).

     A COUNT CANNOT SAY WHAT MOVED. It failed with `Expected 4, Received 5`, which reports that
     a row appeared without naming it, and it is blind to the failure that matters more: five
     rows where one control has silently replaced another, or one of these going missing while
     a sixth arrives. The roster fails naming both sides, and it is the repair
     `app/tests/cursor.spec.ts` already took when its hand-typed list of routes was found to be
     sweeping three screens it did not know existed — a sweep that walks whatever it finds
     passes for the wrong reason.

     LABELS, NOT ACCESSIBLE NAMES: what belongs here is WHICH controls are drawn and in what
     order, which is D20's own — what the box is called, where its dividers are, whether the lid
     is on, then the two that act on cards rather than on the box. The details riding on them
     (`freezes at 7`, `7 cards`) are each asserted by the case that owns that promise, and
     repeating them here would make one number two tests to edit. */
  /* THE ROSTER IS THE BOX'S OWN OPERATIONS, and the destructive ones are now kept in a group of
     their own rather than mixed in — so this reads the operations group and the danger group
     apart, which is what the screen draws. The order inside each is still pinned: it is D20's
     own — what the box is called, where its dividers are, then the two
     that act on cards rather than on the box. */
  const rows = page.locator('.boxops-group:not(.boxops-group-danger) .boxops-op')
  await expect(rows.locator('.boxops-op-label')).toHaveText([
    'Rename',
    'Edit sections',
    'Name sections',
    'Set claims',
    'Move to box',
  ])
  await expect(rows).toHaveCount(5)

  /* FULL MEASURE, WHICH IS THE PROPERTY THE OLD LITERAL STOOD FOR. The panel is a sheet rather
     than the foot of the walk's own column, so the walk's left edge is no longer the measure to
     hold them to; every row filling its group is, and it is what stops one of them being read as
     a chip. It is also what the ticked-selection case leans on when it asserts the row does not
     resize as the selection changes. */
  const measures = await rows.evaluateAll((nodes) =>
    nodes.map((node) => {
      const own = node.getBoundingClientRect()
      const held = (node.parentElement as HTMLElement).getBoundingClientRect()
      return { dx: Math.abs(own.x - held.x), dw: Math.abs(own.width - held.width) }
    }),
  )
  expect(measures.length).toBe(5)
  for (const measure of measures) {
    expect(measure.dx).toBeLessThanOrEqual(1)
    expect(measure.dw).toBeLessThanOrEqual(1)
  }

  /* A row is not a chip: `--line` separates and does not enclose, so no row in the roster above
     carries a border of its own. The ink border is spent once, on the bar below them, and that
     step is bigger than it was when the delete was one bordered chip among six.

     THE SWEEP IS OVER `rows`, so an operation added later is held to this claim by arriving
     rather than by somebody remembering to add it — which is why the roster above has to pin
     what `rows` contains. D83's `Move to box` is the first control to reach this loop that way,
     and it passes: it is an `Op`, so it is the same element under the same rule. */
  for (const row of await rows.all()) {
    await expect(row).toHaveCSS('border-top-width', '0px')
    await expect(row).toHaveCSS('border-left-width', '0px')
    await expect(row).toHaveCSS('border-right-width', '0px')
  }

  /* THE DELETE IS SET APART BY BEING SOMEWHERE ELSE AND BY BEING RED, which is the same
     statement the bordered bar made and is measured the same way: against an ordinary row, on
     screen, rather than against a class name. */
  const bar = page.getByRole('button', { name: /^Delete this box…/ })
  await expect(bar).toHaveCount(1)
  await expect(bar).toHaveAttribute('aria-label', /^Delete this box…, no undo$/)
  const ordinary = await rows.first().evaluate((node) => window.getComputedStyle(node).color)
  const danger = await bar.evaluate((node) => window.getComputedStyle(node).color)
  expect(danger, 'the delete is drawn in the same ink as an ordinary operation').not.toBe(ordinary)
  await expect(page.locator('.boxops-group-danger')).toContainText('Danger')

  /* AND THE BAR IS BORDERED, which is the half of this case's own name that nothing asserted.
     The loop above proves the rows are bare and the lines below prove the bar says `no undo`;
     between them the title claims the delete is the ONLY bordered one, and `.boxops-bar` losing
     its `1px solid var(--ink)` would have left every assertion here green while the one step of
     emphasis this palette allows went missing. All four sides, because it encloses — that is
     the distinction the rows are measured against. */
  /* And it opens its own paragraph rather than firing: the press that spends is inside the
     confirmation, which is the case below. */
  await expect(bar).toHaveAttribute('aria-expanded', 'false')

  /* `no undo` is said BEFORE the panel that spends a paragraph on it, and it is what keeps a
     full-measure bordered control from being a short label beside 220px of white. */
  await expect(bar.locator('.boxops-op-detail')).toHaveText('no undo')
})

// ------------------------------------------------------------------------- the mass-select

test('ticking rows narrows what a box-wide claim will reach, and says so on the button', async ({
  page,
}) => {
  await open(page)
  await openBoxOps(page)

  /* THE SCOPE MOVED OFF THE LABEL AND ONTO THE ROW'S DETAIL (2026-08-26), and this case moved
     with it rather than being loosened. What it guards is unchanged and is the whole reason it
     exists: what a bulk write will reach is stated ON the control, before the press, and it
     narrows when rows are ticked. What changed is the register — the quantity is drawn in the
     utility face at the far edge of the row instead of set in bold body type inside a sentence
     — so the assertion reads the two spans rather than one concatenated string.

     THE ACCESSIBLE NAME IS ASSERTED BESIDE THE VISIBLE ONE, which the old shape got for free
     and this one does not: the label and the detail are grid items with no text node between
     them, so the computed name would concatenate to `Set claims5 cards` without the explicit
     `aria-label` that `Op` supplies. A promise that holds on screen and not in the accessibility
     tree is half a promise, and the number-on-the-control rule is D20's. */
  const claims = page.getByRole('button', { name: /^Set claims/ })
  await expect(claims.locator('.boxops-op-label')).toHaveText('Set claims')
  /* SEVEN, not the five on hand: the sweep is over RECORDS, and a departed card's claim is
     as correctable as any other — D58 changed which cards a NUMBER counts, not which cards a
     write reaches. */
  await expect(claims.locator('.boxops-op-detail')).toHaveText('7 cards')
  await expect(claims).toHaveAttribute('aria-label', 'Set claims, 7 cards')

  /* THE TICKING HAPPENS IN THE WALK AND THE CONTROL LIVES IN A SHEET OVER IT, so the sheet is
     shut to reach the rows and opened again to read what they did to the control. That is the
     operator's own sequence, and the promise it is being held to is unchanged: the scope is
     stated ON the control, before the press, and it narrows when rows are ticked. */
  await closeBoxOps(page)
  await expandAll(page)
  await page.locator('.browse-rowtick').nth(0).check()
  await page.locator('.browse-rowtick').nth(2).check()
  await expect(page.locator('.browse-status-picked')).toHaveText('2 ticked')

  await openBoxOps(page)
  await expect(claims.locator('.boxops-op-detail')).toHaveText('2 ticked')
  await expect(claims).toHaveAttribute('aria-label', 'Set claims, 2 ticked')

  /* AND THE ROW DID NOT CHANGE WIDTH WHILE IT SAID SO. The old label grew and shrank by ~150px
     with the selection, which is what `boxops-actions-lone` existed to keep off the delete's
     row; a full-measure row cannot, and only the detail moves. Asserted because it is the
     property that let that guard be retired. */
  /* THE LITERAL 360 WENT WHEN THE WALK'S TRACK DID (2026-08-29). It was the map column's width,
     and that column is now `minmax(285px, 22fr)` — 299px at 1440 and 285px at the 1280 this
     suite runs at. Pinning the number again would pin the RATIO to this case, so what is
     asserted is the property the number was standing in for: the row is a full measure, and it
     does not resize when the selection changes. That is stronger than the literal was, because a
     literal goes green on a row that happens to be 360px for a different reason. */
  const width = (await claims.boundingBox())?.width
  const opWidth = await page.locator('.boxops-op').first().evaluate((el: HTMLElement) => el.offsetWidth)
  /* `offsetWidth` is an integer and a bounding box is not, so they agree to the pixel and not to
     the sixteenth of one. Same claim: the row is exactly as wide as its siblings. */
  expect(width).toBeCloseTo(opWidth ?? -1, 0)

  /* THE STABILITY HALF, WHICH IS WHAT THE OLD LITERAL ACTUALLY BOUGHT. The label used to grow
     and shrink by ~150px with the selection; only `.boxops-op-detail` may move now. The sheet
     is shut to change the selection, for the reason above, and opened again to measure. */
  await closeBoxOps(page)
  await page.locator('.browse-rowtick').nth(2).uncheck()
  await openBoxOps(page)
  await expect(claims.locator('.boxops-op-detail')).toHaveText('1 ticked')
  await expect(page.locator('.boxops-op').first()).toHaveJSProperty('offsetWidth', opWidth)

  await closeBoxOps(page)
  await page.locator('.browse-rowtick').nth(2).check()

  /* A fold may hide a row but must never hide what a bulk write would reach, so the section
     header carries its own share of the count.
     `2/5` AND NOT `2/3`: the denominator counts RECORDS, and section 1 holds five of them —
     three cards and two departures. It is deliberately not the on-hand count, because what
     it is a share of is what the button beside it would write to, and a claim on a sold
     card is as correctable as any other (D58 moved which cards carry a NUMBER, not which
     cards a write reaches). */
  await expect(page.locator('.browse-sectcount').nth(0)).toHaveText('2/5')
})

test('the box claim sends only the ticked fields, over only the ticked indices', async ({
  page,
}) => {
  const wire = await open(page)
  /* The ticking is done in the walk, with the Manage sheet shut: it is modal over the screen,
     and a scrim between the operator and the rows is the point of one. */
  await expandAll(page)
  await page.locator('.browse-rowtick').nth(0).check()
  await page.locator('.browse-rowtick').nth(2).check()

  await openBoxOps(page)
  await page.getByRole('button', { name: /^Set claims/ }).click()

  // Nothing armed yet: an editor that opened with a field ticked would write to every card in
  // scope on the first press.
  await page.getByRole('button', { name: /^Apply to/ }).click()
  /* The refusal is a notice in the editor rather than a machine line, and it says the same two
     things: switch a field on, and nothing was sent. */
  await expect(page.locator('.bn-notice', { hasText: 'Switch on a field before applying' })).toBeVisible()
  await expect(page.locator('.bn-notice', { hasText: 'Nothing was sent' })).toBeVisible()
  expect(wire.filter((sent) => sent.method === 'PUT')).toHaveLength(0)

  await page.locator('.boxops-claim-row', { hasText: 'SET HINT' }).getByRole('switch').check()
  await page.getByRole('textbox', { name: 'Set hint' }).fill('SV09')
  await page.getByRole('button', { name: /^Apply to/ }).click()

  await expect(page.locator('.boxops-receipt')).toBeVisible()
  const put = wire.find((sent) => sent.method === 'PUT')
  expect(put?.path).toBe('/inventory/2')
  /* Exactly one claim and the two indices. `game`, `variant`, `rarity_claim` and `note` are
     ABSENT rather than null — absent leaves a claim alone and null clears it, and a form that
     sent all five would flatten a box the first time somebody fixed one field. */
  expect(put?.body).toEqual({ set_hint: 'SV09', indices: [1, 3] })
})

test('a claim with nothing ticked reaches the whole box, and never sends an empty list', async ({
  page,
}) => {
  const wire = await open(page)
  await openBoxOps(page)

  await page.getByRole('button', { name: /^Set claims/ }).click()
  await page.locator('.boxops-claim-row', { hasText: 'NOTE' }).getByRole('switch').check()
  await page.getByRole('textbox', { name: 'Note' }).fill('japanese')
  await page.getByRole('button', { name: /^Apply to/ }).click()

  const put = wire.find((sent) => sent.method === 'PUT')
  /* `indices` OMITTED, never `[]`. The server refuses an empty array on purpose — an emptied
     selection widening to every card in the box is the accident that refusal exists to stop —
     so the widening happens on the screen, where the button said which of the two it would
     do. */
  expect(put?.body).toEqual({ note: 'japanese' })
})

test('a set-valued finish claim renders as its members, never as an array coerced to text', async ({
  page,
}) => {
  await open(page)

  /* D3 rung 1's claim is a SET since 2026-08-23, and `server/capture_server.py:_card_row`
     ships `asdict(card)` straight to the browser — so a real JSON array arrives on a field
     `types.ts` used to declare `string | null`.

     THE FAILURE THIS CATCHES HAS NO ERROR ATTACHED. `{card.metadata_finish}` renders an
     array by JavaScript's coercion: `normal,reverse_holo`, comma and no spaces, on the
     screen the owner opens to find out what a run actually recorded. Nothing throws,
     nothing logs, and `tsc` could not see it while the type said `string`. */
  await expandAll(page)
  await page.locator('.browse-row').nth(1).click()
  const finish = page.locator('.browse-fact', { hasText: 'Finish' }).locator('dd')
  /* THE MEMBERS, EACH DRAWN AS A WORD — which is what this case is about: `normal,reverse_holo`
     is what JavaScript's coercion of an array looks like, lowercase and comma-packed with no
     space. `claimText` joins a real list with `, ` (D218: a list of members is a real list,
     never a typed bullet) — capitalized and spaced, which a coercion never produces. The
     failure this guards against is the bare, unspaced, lowercase comma. */
  await expect(finish).toHaveText('Normal, Reverse Holo')

  /* And a record written BEFORE the amendment still reads. There is no migration — a bare
     string is a one-member claim — so this is the shape most of the store still holds. */
  await page.locator('.browse-row').nth(0).click()
  await expect(page.locator('.browse-fact', { hasText: 'Finish' }).locator('dd')).toHaveText(
    'Normal',
  )
})

test('the box-claims finish control is a multi-select and sends a list', async ({ page }) => {
  const wire = await open(page)
  await openBoxOps(page)

  await page.getByRole('button', { name: /^Set claims/ }).click()
  await page.locator('.boxops-claim-row', { hasText: 'FINISH' }).getByRole('switch').check()

  /* Tapped in the REVERSE of the game's enum order, deliberately. The claim has to leave in
     the registry's order whatever order it was built in: `pipeline/variant.py:_check_claim`,
     `identify/sidecar.py:_check_variant` and the capture route all canonicalise to it, and a
     claim that arrived in tap order would diff as a change against the identical claim
     restated later — a `corrected` event and a rewritten sidecar for every card in the box,
     which is exactly what `do_put_box_claims` promises it does not do. */
  const chips = page.locator('.boxops-claim-row', { hasText: 'FINISH' }).locator('.boxops-chip')
  await chips.filter({ hasText: 'reverse_holo' }).click()
  await chips.filter({ hasText: /^normal$/ }).click()

  /* BOTH read as pressed — the control is a multi-select, not a picker where the second tap
     replaces the first. That is what a `<select>` could not express, and the reason a stack
     holding two finishes had no honest claim available before the amendment. */
  await expect(chips.filter({ hasText: /^normal$/ })).toHaveAttribute('aria-pressed', 'true')
  await expect(chips.filter({ hasText: 'reverse_holo' })).toHaveAttribute('aria-pressed', 'true')

  await page.getByRole('button', { name: /^Apply to/ }).click()

  const put = wire.find((sent) => sent.method === 'PUT')
  expect(put?.body).toEqual({ variant: ['normal', 'reverse_holo'] })
})

test('untapping the last finish clears the claim rather than sending an empty list', async ({
  page,
}) => {
  const wire = await open(page)
  await openBoxOps(page)

  await page.getByRole('button', { name: /^Set claims/ }).click()
  await page.locator('.boxops-claim-row', { hasText: 'FINISH' }).getByRole('switch').check()
  const chips = page.locator('.boxops-claim-row', { hasText: 'FINISH' }).locator('.boxops-chip')
  await chips.filter({ hasText: /^normal$/ }).click()
  await chips.filter({ hasText: /^normal$/ }).click()
  await page.getByRole('button', { name: /^Apply to/ }).click()

  /* `null`, never `[]`. An armed row that is empty CLEARS the claim, and null is how this
     wire says so; `[]` would be a second spelling of no-claim on a route where the store's
     own carry-over rule already has to treat the two alike. D3: an empty set is no claim at
     all, identical to the null this field has always allowed. */
  const put = wire.find((sent) => sent.method === 'PUT')
  expect(put?.body).toEqual({ variant: null })
})

test('the product row is drawn for the game that claims products, and for no other', async ({
  page,
}) => {
  const wire = await open(page)
  await openBoxOps(page)
  await page.getByRole('button', { name: /^Set claims/ }).click()

  /* THE NEGATIVE FIRST. `codes/products.py:GAME` says ONE game claims a product, `GET /games`
     serves that key as `product_game`, and `ClaimEditor` compares the picked game against it.
     The fixture's default is `pokemon`, which is not it, so the row is not drawn at all —
     nothing greyed, nothing disabled. The five rows around it are. */
  await expect(page.locator('.boxops-claim-row', { hasText: 'PRODUCT' })).toHaveCount(0)
  await expect(page.locator('.boxops-claim-row', { hasText: 'FINISH' })).toHaveCount(1)

  /* THE ROW'S OWN GAME PICK IS THE KIT'S `Select`, not a native combobox (BoxOps' three
     native `<select>`s moved to it, round 3). Its own accessible name is "Game" too — the
     same collision the old comment named against D213's inventory filter, now a button
     rather than a combobox either side, so this locator scopes to the claims editor's own
     row instead of disambiguating by exact name. */
  await page.locator('.boxops-claims .boxops-claim-row', { hasText: 'GAME' }).locator('.bn-pick').click()
  await page.locator('.bn-pick-opt', { hasText: 'Pokémon code cards' }).click()

  const row = page.locator('.boxops-claim-row', { hasText: 'PRODUCT' })
  await expect(row).toHaveCount(1)

  /* AND THE VOCABULARY IS THE REGISTRY'S, WHICH IS THE HALF THAT WAS ABSENT. `productList`
     comes from `GET /games`'s `products`, and a fixture that omitted the key put `undefined`
     into state and threw on the first render after the fetch resolved — taking the whole
     screen down behind the route boundary and timing out four cases above this one on a
     switch none of them could reach. A case that reads a product's display name cannot pass
     against that shape. `No claim` is the kit `Select`'s own PLACEHOLDER now (round 3):
     shown on the trigger while nothing is picked, never a real option in its open panel — the
     native `<select>` this replaced drew it as a real `<option value="">`. */
  await expect(row.locator('.bn-pick')).toContainText('No claim')
  await row.locator('.bn-pick').click()
  await expect(page.locator('.bn-pick-opt')).toHaveText([
    'Booster pack',
    'Elite Trainer Box',
    'Pokémon Center ETB',
    'Other / unsure',
  ])
  await page.keyboard.press('Escape')

  /* The premium lane is drawn off the registry's own flag rather than off the key's spelling —
     `codes/products.py`'s own header records a throwaway classifier putting four $0.06 blisters
     in the premium tier on the word "premium" alone. */
  await row.locator('.bn-pick').click()
  await page.locator('.bn-pick-opt', { hasText: 'Booster pack' }).click()
  await expect(row.locator('.bn-pill')).toHaveText('Bulk')
  await row.locator('.bn-pick').click()
  await page.locator('.bn-pick-opt', { hasText: 'Pokémon Center ETB' }).click()
  await expect(row.locator('.bn-pill')).toHaveText('Premium')

  await row.getByRole('switch').check()
  await page.locator('.boxops-claim-row', { hasText: 'GAME' }).getByRole('switch').check()
  await page.getByRole('button', { name: /^Apply to/ }).click()

  const put = wire.find((sent) => sent.method === 'PUT')
  expect(put?.body).toEqual({ game: 'pokemon_code', product: 'pc_etb' })
})

test('a product claim armed against the code game leaves with it, rather than riding a game that has no products', async ({
  page,
}) => {
  const wire = await open(page)
  await openBoxOps(page)
  await page.getByRole('button', { name: /^Set claims/ }).click()

  /* THE RULE `ClaimEditor` STATES AND NOTHING ASSERTED: a row that is not drawn is not armed.
     Arm Product against the code game, change the game back, and without the disarming effect
     the row is gone from the screen while its claim is still in the patch — a write nobody can
     see they asked for, over every card in the box. */
  /* THE ROW'S OWN GAME PICK IS THE KIT'S `Select` now (round 3), scoped to the claims
     editor's own row rather than disambiguated by an exact accessible name — see the sibling
     case above. */
  const gameRow = page.locator('.boxops-claims .boxops-claim-row', { hasText: 'GAME' })
  await gameRow.locator('.bn-pick').click()
  await page.locator('.bn-pick-opt', { hasText: 'Pokémon code cards' }).click()
  await page.locator('.boxops-claim-row', { hasText: 'PRODUCT' }).getByRole('switch').check()
  await page.locator('.boxops-claim-row', { hasText: 'PRODUCT' }).locator('.bn-pick').click()
  await page.locator('.bn-pick-opt', { hasText: 'Booster pack' }).click()

  await gameRow.locator('.bn-pick').click()
  await page.locator('.bn-pick-opt', { hasText: /^Pokémon$/ }).click()
  await expect(page.locator('.boxops-claim-row', { hasText: 'PRODUCT' })).toHaveCount(0)

  /* Something still has to be armed or the editor refuses and sends nothing, so the note row
     carries the apply — and the assertion is that `product` is not beside it. */
  await page.locator('.boxops-claim-row', { hasText: 'NOTE' }).getByRole('switch').check()
  await page.locator('.boxops-claim-row', { hasText: 'NOTE' }).getByRole('textbox', { name: 'Note' }).fill('mixed')
  await page.getByRole('button', { name: /^Apply to/ }).click()

  const put = wire.find((sent) => sent.method === 'PUT')
  expect(put?.body).toEqual({ note: 'mixed' })
})

// ---------------------------------------------------------------- the destructive controls

test('the mid-box delete aims with the target’s own capture id and reports the shift', async ({
  page,
}) => {
  const wire = await open(page)

  await expandAll(page)
  await page.locator('.browse-row', { hasText: 'Thievul' }).nth(1).click()
  await openCardOps(page)
  await page.getByRole('menuitem', { name: 'Remove this card…' }).click()
  await page.getByRole('button', { name: 'Delete this card' }).click()

  const removed = wire.find((sent) => sent.path.endsWith('/remove'))
  expect(removed?.method).toBe('POST')
  expect(removed?.path).toBe('/inventory/2/3/remove')
  /* The aim. The operation is not idempotent — after the shift a different physical card sits
     at that index — so a replay must refuse rather than delete the neighbour that slid in. */
  expect(removed?.body).toEqual({ capture_id: 'cap-3' })

  /* `shifted > 0` means every label above the deleted card has changed, and the receipt has to
     say so: it is the one operation in the product that renumbers. */
  await expect(page.locator('.bn-toast')).toContainText('the number before')
})

test('and the photograph follows the shift, because the URL names the capture', async ({
  page,
}) => {
  /* THE DEFECT THE OWNER REPORTED, AS A CASE. Their words, 2026-08-29: deleting a card
     "doesn't kick in super quickly and it makes you think you need to delete more but in
     reality it eventually ... shows that it really was deleted". Nothing was slow —
     measured against a copy of their store, the delete answered in 288 ms and the walk
     redrew in 500 ms. What stayed was the PICTURE: `/photo/<box>/<index>` names a SLOT, the
     renumber puts a different card in it, and the browser went on showing what it had. The
     screen then read as a delete that had not happened, over the facts of the card that
     had slid in — and the next press deletes that card, which is a real capture.

     THE ASSERTION IS THE URL AND NOT THE PIXELS, because a stubbed photo route serves one
     SVG for every slot and a browser test cannot see a stale bitmap. The URL carrying the
     occupant's id is the whole mechanism: it is what makes the two loads different
     requests, which is what Chrome's in-document memory cache needs before it will go and
     ask. A remount alone was built first and measured NOT sufficient — same URL, same
     bytes, no request — so a version of this case that asserted only `sameDomNode: false`
     would have passed against the broken screen.

     THE STORE SHIFTS UNDER THE RE-READ, which is what the real one does: `2/3` is deleted,
     the card behind it slides down into that key, and it brings its own capture id. */
  const AFTER: Cards = {
    '2/1': card({
      index: 1,
      state: 'identified',
      name: 'Thievul',
      sku: '8937370',
      section: 1,
      sectionStart: 1,
      sectionEnd: 3,
    }),
    '2/3': card({
      index: 3,
      state: 'identified',
      name: 'Eiscue',
      sku: '8937371',
      section: 1,
      sectionStart: 1,
      sectionEnd: 3,
      captureId: 'cap-slid-into-3',
    }),
  }
  let shifted = false
  page.on('request', (request) => {
    if (request.url().includes('/remove')) shifted = true
  })
  await open(page, BOXES, {
    get cards() {
      return shifted ? AFTER : CARDS
    },
    search: (query) => searchAnswer(query),
  })

  await expandAll(page)
  await page.locator('.browse-row', { hasText: 'Thievul' }).nth(1).click()

  /* Before: the slot's URL carries the id of the card standing in it. */
  const photo = page.locator('.browse-photo')
  await expect(photo).toHaveAttribute('src', /\/photo\/2\/3\?card=cap-3$/)

  await openCardOps(page)
  await page.getByRole('menuitem', { name: 'Remove this card…' }).click()
  await page.getByRole('button', { name: 'Delete this card' }).click()

  /* After: the SAME slot, a different card, and therefore a different URL — so the picture
     is re-fetched rather than reused. The facts beside it moved on their own and always
     did; it is the photograph that used to lie. */
  await expect(page.locator('.browse-about')).toContainText('Eiscue')
  await expect(photo).toHaveAttribute('src', /\/photo\/2\/3\?card=cap-slid-into-3$/)
})

/* AND WHERE THE ROW CARRIES A NAME, THE ADDRESS IS THE NAME (D172).
 *
 * THE CASE ABOVE IS THE HAZARD AND THIS IS THE FIX ONE LAYER DOWN. `?card=` made the URL
 * change when the occupant did; `GET /photo/by-card/<cid>` makes the URL NAME THE PHOTOGRAPH
 * outright — frozen at issue, UNIQUE in `cards_cid` — so a slot that changes hands cannot
 * produce one URL for two cards at all. The route landed with `#/inventory` drawing none of
 * it, which is `CLAUDE.md`'s route-is-not-a-feature rule exactly; this is the reader that
 * says the screen reaches it.
 *
 * THE STAMP IS ASSERTED ON PURPOSE AND IS NOT A LEFTOVER. `cid` is FROZEN, so D26's re-shoot
 * writes new bytes at the same name, and `/photo/by-card/` answers `immutable` for a year with
 * an ETag that is the NAME's own hex — so when the bytes change, neither the URL, the lifetime
 * nor the validator moves, and a browser that revalidates is answered 304 into the stale
 * picture. `capture_id` is the one field that moves when the bytes do. This screen owns the
 * re-shoot; deleting the stamp here would make a replaced photograph invisible on the screen
 * that replaced it, and this line is what goes red for it.
 *
 * THE FIXTURE PASSES A NAME FOR THIS CASE AND NO OTHER, which is why the case above still
 * reads `/photo/2/3` — `cid` is optional on the wire, a server predating D172 sends no key,
 * and both addresses have to keep working. */
test('a card whose row carries a name is addressed by the name, stamp and all', async ({
  page,
}) => {
  /* 64 hex, because `server.ts:PHOTO_CID` is what decides whether a name reaches the route at
     all — `moved:` and `nophoto:` names fall back to the slot, and a fixture carrying a
     plausible-looking short string would silently assert the fallback instead. */
  const NAME = '3f5a1c7e9b0d2468ace13579bdf02468ace13579bdf02468ace13579bdf02468'
  const NAMED: Cards = {
    ...CARDS,
    '2/1': card({
      index: 1,
      state: 'identified',
      name: 'Thievul',
      sku: '8937370',
      section: 1,
      sectionStart: 1,
      sectionEnd: 3,
      cid: NAME,
    }),
  }

  await open(page, BOXES, { cards: NAMED, search: (query) => searchAnswer(query, NAMED) })
  await expandAll(page)
  await page.locator('.browse-row', { hasText: 'Thievul' }).first().click()

  await expect(page.locator('.browse-photo')).toHaveAttribute(
    'src',
    new RegExp(`/photo/by-card/${NAME}\\?card=cap-1$`),
  )
})

/* AND A NAME THAT NAMES NO PHOTOGRAPH FALLS BACK TO THE SLOT (D172's four shapes).
 *
 * THE CASE ABOVE SAYS THIS IN A COMMENT AND NOTHING ASSERTED IT, which is the shape this repo
 * refuses: a claim with no reader has no way of ever being contradicted. A mutation arm that
 * replaced `server.ts:PHOTO_CID.test(cid)` with `true` left all 100 tests green.
 *
 * THE ASYMMETRY THAT MAKES IT REACHABLE IS ON THE WIRE, and it is deliberate on both sides.
 * `_copy_row` filters — it sends `cid` only when `photos.is_photo_cid` — but `_card_row` is
 * `asdict(card)` and `_card_summary` names the field outright, so an `InventoryCard` carries
 * the RAW name including `moved:<hex>` on a D83 tombstone and `nophoto:<key>@<stamp>` on a
 * record `emit` created for a position no camera ever saw. Two of D172's four shapes name no
 * file at all, and `photos.path` REFUSES to compose one from them — so a client that sent them
 * to `/photo/by-card/` would ask for a photograph that cannot exist, and the operator would
 * get a broken image on the walk rather than the card they are standing at.
 *
 * SO `PHOTO_CID` IS LOAD-BEARING RATHER THAN DEFENSIVE, and it is the client's half of a
 * predicate the server spells `is_photo_cid`. This is what goes red when it stops matching. */
test('a name that names no photograph falls back to the slot address', async ({ page }) => {
  /* Both shapes that name no file, against one that does — because a guard tested on one
     rejection is a guard that might be testing the prefix rather than the shape. */
  const TOMBSTONE = 'moved:3f5a1c7e9b0d2468ace13579bdf02468ace13579bdf02468ace13579bdf02468'
  const NOPHOTO = 'nophoto:2/2@2026-08-22T12:34:00+00:00'
  const SHAPED: Cards = {
    ...CARDS,
    '2/1': card({
      index: 1,
      state: 'identified',
      name: 'Thievul',
      sku: '8937370',
      section: 1,
      sectionStart: 1,
      sectionEnd: 3,
      cid: TOMBSTONE,
    }),
    '2/2': card({
      index: 2,
      state: 'identified',
      name: 'Nickit',
      sku: '8937371',
      section: 1,
      sectionStart: 1,
      sectionEnd: 3,
      cid: NOPHOTO,
    }),
  }

  await open(page, BOXES, { cards: SHAPED, search: (query) => searchAnswer(query, SHAPED) })
  await expandAll(page)

  await page.locator('.browse-row', { hasText: 'Thievul' }).first().click()
  await expect(page.locator('.browse-photo')).toHaveAttribute(
    'src',
    /\/photo\/2\/1\?card=cap-1$/,
  )

  await page.locator('.browse-row', { hasText: 'Nickit' }).first().click()
  await expect(page.locator('.browse-photo')).toHaveAttribute(
    'src',
    /\/photo\/2\/2\?card=cap-2$/,
  )
})

test('a sold or retired card is not offered the mid-box delete at all', async ({ page }) => {
  await open(page)

  await expandAll(page)
  await page.locator('.browse-row', { hasText: 'Eiscue' }).click()

  /* The `restores_to` lesson: never offer a control whose only behaviour is a refusal.
     `do_remove_card` refuses a sold card by name, because deleting it would erase the record of
     a departure D10 makes permanent. */
  await openCardOps(page)
  await expect(page.getByRole('menuitem', { name: 'Remove this card…' })).toHaveCount(0)
  await expect(page.getByRole('menuitem', { name: 'Correct claims' })).toBeVisible()
})

/* AN EMPTY BOX IS A BOX, AND FOR ONE COMMIT IT WAS UNREACHABLE.
 *
 * The box strip was built from the CARD ROWS (`shelvesOf`), so a registered box holding no
 * cards produced no row, therefore no shelf, therefore no cell — and the strip is the only way
 * to select one. `BoxIdentity` and `BoxOps` draw for the SELECTED shelf, so rename, dividers,
 * seal and the whole-box DELETE were all unreachable for it. Measured on the owner's own store
 * the day it was found: 12 of 13 boxes, including every box they had just created to test
 * with, and `Register a box` made another one you then could not get rid of.
 *
 * It is `CLAUDE.md`'s route-is-not-a-feature rule from the far side — the route, the client
 * function and the on-screen control all existed and all passed — and a regression with a
 * commit: `13c397a`, D31's merge, wrote this strip and retired `#/boxes`, whose whole content
 * was the registry list. The merge carried the cards over and not the registry.
 */
test('a registered box with no cards is still reachable, and can still be deleted', async ({
  page,
}) => {
  const wire = await open(page, {
    boxes: [
      ...BOXES.boxes,
      {
        box: 6,
        name: 'asdfkopas',
        sections: [],
        state: 'open',
        capacity: null,
        fill: 0,
        next_index: 1,
        cards: 0,
        sold: 0,
        retired: 0,
        listed: 0,
        moved: 0,
        sections_detail: [],
      },
    ],
  })

  /* THE CELL EXISTS. Box 6 owns no card in `CARDS`, so before the fix this count was 1. */
  await expect(page.locator('.browse-boxcell')).toHaveCount(2)
  const cell = page.locator('.browse-boxcell[aria-label^="asdfkopas"]')
  await expect(cell).toBeVisible()
  await cell.click()

  /* AND SELECTING IT REACHES THE OPERATIONS, which is the half that makes the cell worth
     having. Asserted through the delete specifically: it is the one this screen could not
     otherwise perform at all, and the one the owner went looking for. */
  await expect(page.locator('.browse-empty')).toContainText('Nothing in asdfkopas yet')
  await openBoxOps(page)
  await expect(page.getByRole('button', { name: /^Delete this box/ })).toBeVisible()

  /* The claim editor is NOT offered, because it is the one control here that writes CARDS and
     there are none — `Set claims on all 0 cards in box 6` was a real string on this screen for
     as long as it took to notice. Absent rather than disabled, per docs/DESIGN.md. */
  await expect(page.getByRole('button', { name: /^Set claims/ })).toHaveCount(0)

  await page.getByRole('button', { name: /^Delete this box/ }).click()
  await page.getByRole('button', { name: 'Delete this box permanently' }).click()
  const deleted = wire.find((sent) => sent.method === 'DELETE')
  expect(deleted?.path).toBe('/boxes/6')
})

test('a search still hides a box holding no match, which is the rule the fix did not touch', async ({
  page,
}) => {
  await open(page, {
    boxes: [
      ...BOXES.boxes,
      {
        box: 6, name: 'asdfkopas', sections: [], state: 'open', capacity: null, fill: 0,
        next_index: 1, cards: 0, sold: 0, retired: 0, moved: 0, listed: 0, sections_detail: [],
      },
    ],
  })
  await expect(page.locator('.browse-boxcell')).toHaveCount(2)

  /* THE BOUNDARY, AND IT IS THE POINT OF THE FIX RATHER THAN AN EXCEPTION TO IT. `shelvesOf`
     was written so a cell can never lead to an empty list, and that rule is RIGHT about a
     query — under one, a cell for a box holding no match is a dead end. It was wrong only as a
     rule about the STORE, where an empty box's empty list is the truth. So the registry is
     unioned in when nothing is being searched for, and not when something is. */
  await page.getByRole('searchbox').fill('Thievul')
  /* THE CELL SURVIVES AND THE DEAD END DOES NOT. The rail answers "where else could this be" for
     every box under a query now, so box 6 keeps a cell — and it is DISABLED, because a cell that
     could be pressed would still lead to the empty list the rule is about. The boundary is
     unchanged; what changed is whether a box with no match is drawn as absent or as unreachable. */
  const empty = page
    .locator('.browse-boxcell[aria-label^="asdfkopas"]')
  await expect(empty).toBeDisabled()
})

test('the whole-box delete takes two presses, and both of them name the box', async ({
  page,
}) => {
  const wire = await open(page)
  await openBoxOps(page)

  /* THE FIRST PRESS FIRES NOTHING, which is the half of the gate that survived the owner's
     2026-08-26 change. It used to be two presses plus the box number typed into a field; they
     traded the typing away after meeting eleven empty spam boxes and eleven typed numbers.

     WHAT IS ASSERTED HERE IS THE PART THAT STILL DOES THE WORK: the number is printed on BOTH
     controls, so neither press can be made without the target on screen. That is what keeps
     this out of docs/DESIGN.md's ban on "are you sure" — the banned dialog's confirm says
     nothing about what it is confirming, and both of these say the box. */
  await expect(page.getByRole('button', { name: /^Delete this box/ })).toBeVisible()
  expect(wire.filter((sent) => sent.method === 'DELETE')).toHaveLength(0)

  await page.getByRole('button', { name: /^Delete this box/ }).click()
  const fire = page.getByRole('button', { name: 'Delete this box permanently' })
  await expect(fire).toBeVisible()

  /* STILL NOTHING SENT until the second press. A panel that opened and fired in one gesture
     would be the momentum this control has always been designed against. */
  expect(wire.filter((sent) => sent.method === 'DELETE')).toHaveLength(0)

  /* Cancel is beside it and is not a no-op: the way out has to be as reachable as the way
     through, or the panel becomes a trap that the fastest escape from is the delete. */
  await expect(page.getByRole('button', { name: 'Cancel' })).toBeVisible()

  await fire.click()

  const deleted = wire.find((sent) => sent.method === 'DELETE')
  expect(deleted?.path).toBe('/boxes/2')

  // The receipt is per-kind and is the only evidence the operation did what it said: there is
  // nothing left to go and check.
  await expect(page.locator('.bn-toast')).toContainText('There is no undo')
})

// -------------------------------------------------------------- the listing release (D34)

/** The same box, holding a listing. `listed` is what draws the release control, and no other
 *  fixture in this file is in that state — which is the point: most boxes never are. */
const HELD_BOXES = {
  boxes: [{ ...BOXES.boxes[0], listed: 3 }, { ...BOXES.boxes[0], box: 7, name: 'ME01 spares', listed: 0 }],
}

test('a box with no listing hold is offered no release at all', async ({ page }) => {
  await open(page)
  await openBoxOps(page)

  /* ABSENT, NOT DISABLED, and the reason is `docs/DESIGN.md`'s about the run panel's spend
     button one register down: a disabled control is one attribute away from pressable. This
     one is cheap to render and would be chrome on every box that has never been listed. */
  await expect(page.getByRole('button', { name: /Release the listing hold/ })).toHaveCount(0)
})

// ----------------------------------------------------------- photo reclamation (D89)

test('a box that has sold nothing is offered no photo reclaim at all', async ({ page }) => {
  await open(page, { boxes: [{ ...BOXES.boxes[0], sold: 0 }] })
  await openBoxOps(page)

  /* ABSENT, NOT DISABLED — the same rule as the release above it. There is nothing a reclaim
     could take from a box holding no sold card, and a control saying so would be chrome on
     every box that has never sold. */
  await expect(page.getByRole('button', { name: /Reclaim the photographs/ })).toHaveCount(0)
})

test('the control that reclaims does not exist until the free count has answered', async ({
  page,
}) => {
  const wire = await open(page)
  await openBoxOps(page)

  /* D33's preflight-then-confirm, the third time on this panel: the count and the megabytes
     are on screen before the button that deletes appears. Held open by never fulfilling the
     read, which is the only way to observe the intermediate state. */
  await page.route(/\/boxes\/\d+\/photos$/, async () => {
    /* deliberately never fulfilled */
  })
  await page.getByRole('button', { name: /Reclaim the photographs of 1 sold card in ME01 commons/ }).click()
  await expect(page.locator('.boxops-confirm')).toContainText('No undo')
  await expect(page.getByRole('button', { name: /permanently$/ })).toHaveCount(0)
  expect(wire.filter((sent) => sent.path.endsWith('/photos/reclaim'))).toHaveLength(0)
})

test('the reclaim names the count and the bytes, sends confirm, and both presses name the box', async ({
  page,
}) => {
  const wire = await open(page)
  await openBoxOps(page)
  await page.getByRole('button', { name: /Reclaim the photographs of 1 sold card in ME01 commons/ }).click()

  const panel = page.locator('.boxops-confirm')
  /* THE NUMBER AND THE SIZE, BEFORE THE PRESS. `3_612_000` bytes is `3.6 MB`; the sentence
     also says what stays — the on-hand photographs and every retired card's — because the
     failure this panel guards against is an operator reading "reclaim" as "everything". */
  await expect(panel).toContainText('2 photographs, 3.6 MB, would go')
  await expect(panel).toContainText('the 3 photographs of cards still on hand')
  await expect(panel).toContainText("every retired card's")

  const read = wire.find((sent) => sent.path === '/boxes/2/photos')
  expect(read?.method).toBe('GET')
  expect(wire.filter((sent) => sent.path.endsWith('/photos/reclaim'))).toHaveLength(0)

  const fire = page.getByRole('button', { name: 'Delete 2 photographs from ME01 commons permanently' })
  await expect(fire).toBeVisible()
  await expect(page.getByRole('button', { name: 'Cancel' })).toBeVisible()
  await fire.click()

  const sent = wire.find((sent) => sent.path.endsWith('/photos/reclaim'))
  expect(sent?.method).toBe('POST')
  expect(sent?.path).toBe('/boxes/2/photos/reclaim')
  /* The server refuses without it: the route's whole content is a person's decision that
     these photographs are disposable, and a request must say so on purpose. */
  expect(sent?.body).toEqual({ confirm: true })

  /* The receipt names the keys, which is the only evidence left: the bytes are gone. */
  await expect(page.locator('.boxops-receipt')).toContainText('Reclaimed 2 photographs from ME01 commons')
  await expect(page.locator('.boxops-receipt')).toContainText('2/3, 2/7')
})

test('a reclaimed photograph is drawn as reclaimed, not as a photo the store lost', async ({
  page,
}) => {
  /* THE SOLD CARD, because only a sold card's photograph is ever reclaimed (D89): Eiscue at
     2/4, the same fixture row every departed-card case in this file walks to. */
  const cards: Cards = {
    ...CARDS,
    '2/4': card({
      index: 4, state: 'sold', name: 'Eiscue', sku: '8937371', section: 1, sectionStart: 1,
      sectionEnd: 3, reclaimed: '2026-09-01T21:00:00.000+00:00',
    }),
  }
  await open(page, BOXES, { ...STORE, cards })
  /* A departed row sits under the fold, as every other case that walks to one already knows. */
  await expandAll(page)
  await page.locator('.browse-row', { hasText: 'Eiscue' }).click()

  /* THREE ABSENCES, THREE SENTENCES. `photo: null` is a card never photographed; a 404 is a
     store that lost something; this is a store that gave a photograph up on purpose after the
     sale, and it says so with the stamp and the digest rather than calling itself broken. */
  await expect(page.locator('.browse-absent')).toContainText('Photograph reclaimed after the sale')
  await expect(page.locator('.browse-absent')).toContainText('sha256 deadbeef00112233')
  await expect(page.locator('.browse-absent')).not.toContainText('did not load')
})

test('a listing hold is named on the delete panel rather than discovered by pressing it', async ({
  page,
}) => {
  await open(page, HELD_BOXES)
  await openBoxOps(page)
  await page.getByRole('button', { name: /^Delete this box/ }).click()

  /* D134: a listed copy is the only remaining ground for `box_not_empty_of_commitments` — a
     sold or retired record no longer blocks and is named as something that will be BURIED
     instead, never as a reason the box is refused. This fixture's sold (1) and retired (1)
     read as "2 other departed records". */
  await expect(page.locator('.boxops-confirm')).toContainText('3 cards listed')
  await expect(page.locator('.boxops-confirm')).toContainText('2 other departed records')
  await expect(page.locator('.boxops-confirm')).toContainText('will be buried')
})

test('the control that releases does not exist until the free plan has answered', async ({
  page,
}) => {
  const wire = await open(page, HELD_BOXES)
  await openBoxOps(page)

  /* D33's preflight-then-confirm shape, one register down: there the free step puts the cost
     on screen before the button that spends appears, here it puts the SKUs, the copy counts
     and the other boxes on screen before the button that asserts appears. Held open here by
     never fulfilling the read, which is the only way to observe the intermediate state. */
  await page.route(/\/boxes\/\d+\/listings$/, async () => {
    /* deliberately never fulfilled */
  })
  await page.getByRole('button', { name: /Release the listing hold on 3 cards/ }).click()

  /* ABSENT, NOT DISABLED — docs/DESIGN.md's rule for the run panel's spend button, for the
     same reason: a disabled button is one attribute away from pressable, and that attribute
     is what a later refactor drops without noticing. */
  await expect(
    page.getByRole('button', { name: 'TCGplayer holds none of these — release' }),
  ).toHaveCount(0)
  expect(wire.filter((sent) => sent.path.endsWith('/listings/release'))).toHaveLength(0)
})

test('the plan names what each SKU gives up, what it keeps, and which box holds the rest', async ({
  page,
}) => {
  await open(page, HELD_BOXES)
  await openBoxOps(page)
  await page.getByRole('button', { name: /Release the listing hold on 3 cards/ }).click()

  const panel = page.locator('.boxops-confirm')
  await expect(panel).toContainText("you've checked TCGplayer and it holds none of them")

  /* THE BUDGET, VISIBLE. The owner's ruling of 2026-08-24: each SKU gives up at most the
     copies this box holds, so a release reached from box 2 can never give up what only box
     7's copies could account for. The line says both halves. */
  await expect(panel).toContainText('8937370 2 staged keeps 3 staged also ME01 spares (3)')

  /* AND THE OUTCOME A PERSON WOULD OTHERWISE READ AS A BUG. A shared SKU leaves a remainder,
     a remainder keeps the card listing-held, so the box stays refused after a release that
     did exactly what it said. The panel says so before the press, not after. */
  await expect(panel).toContainText('This will not free ME01 commons')
})

test('the release sends confirm, and only after the plan is on screen', async ({ page }) => {
  const wire = await open(page, HELD_BOXES)
  await openBoxOps(page)
  await page.getByRole('button', { name: /Release the listing hold on 3 cards/ }).click()

  const fire = page.getByRole('button', { name: 'TCGplayer holds none of these — release' })
  await expect(fire).toBeVisible()
  /* The free read landed first, and it is a GET: the plan and the write are two routes. */
  const read = wire.find((sent) => sent.path === '/boxes/2/listings')
  expect(read?.method).toBe('GET')
  expect(wire.filter((sent) => sent.path.endsWith('/listings/release'))).toHaveLength(0)

  await fire.click()

  const sent = wire.find((sent) => sent.path.endsWith('/listings/release'))
  expect(sent?.method).toBe('POST')
  expect(sent?.path).toBe('/boxes/2/listings/release')
  /* The server refuses without it, deliberately as a field: this route's whole content is a
     human's claim, so a request that did not say so on purpose must not make it by accident. */
  expect(sent?.body).toEqual({ confirm: true })
})

test('the receipt repeats that the box is still held rather than implying success', async ({
  page,
}) => {
  await open(page, HELD_BOXES)
  await openBoxOps(page)
  await page.getByRole('button', { name: /Release the listing hold on 3 cards/ }).click()
  await page.getByRole('button', { name: 'TCGplayer holds none of these — release' }).click()

  const receipt = page.locator('.boxops-receipt')
  /* BY NAME, NEVER BY NUMBER (D259), and the stage in words (D196). */
  await expect(receipt).toContainText('Released 2 SKUs in ME01 commons')
  await expect(receipt).toContainText('3 waiting to go live')
  /* The half that matters most on a partial release: the delete will go on refusing, and a
     receipt that only reported success would leave that looking like a broken gate. */
  await expect(receipt).toContainText('ME01 commons is still held')
  await expect(receipt).toContainText('ME01 spares')
  /* Every SKU by name — the list that makes the claim checkable against TCGplayer afterwards. */
  await expect(receipt).toContainText('8937370')
  await expect(receipt).toContainText('8937200')
})

// ----------------------------------------------------------------- what the merge kept (D26)

test('the re-shoot lives inside Correct claims, and nowhere else on the panel', async ({
  page,
}) => {
  await open(page)

  /* D31 requires this control to survive every move of the card panel — it was nearly lost once
     already. It has moved again (owner, 2026-08-25): out from under the photograph and into
     `Correct claims`, which is the panel that already exists for correcting what a card claims,
     and a re-shoot is the correction the other four cannot make.

     THE NEGATIVE HALF FIRST, because that is the half that says it MOVED rather than that it was
     merely added: it is not on the panel at rest. Under the photograph it was a permanent control
     for an occasional act, in the column whose width is the photograph's. */
  await expect(page.getByRole('button', { name: 'Re-shoot this photo' })).toHaveCount(0)

  await openCardOps(page)
  await page.getByRole('menuitem', { name: 'Correct claims' }).click()
  await expect(page.getByRole('button', { name: 'Re-shoot this photo' })).toBeVisible()
})

// ------------------------------ three columns, and where the box lives (D38, amended)

/* THE ONLY GEOMETRY ASSERTIONS IN THE REPO, and they are here because nothing else on the commit
   path can see what they see. Harness, lint, typecheck and docs-audit are blind to layout by
   construction; `docs/GATES.md` records that as the finding behind CLAUDE.md's
   route-is-not-a-feature rule, and a column that quietly stops holding what it should is the same
   class of defect one notch quieter.

   They run at Playwright's own 1280x720, inside the >= 1240 three-column layout. That was a
   reason for putting the breakpoint at 1240 rather than at the owner's 1440: a layout no test
   viewport renders is a layout nothing guards. */

test('the sections of a box are drawn once, by the walk that can open them', async ({ page }) => {
  await open(page)

  /* THE FINDING THAT MOVED THE BOX INTO THIS COLUMN, asserted as the negative it is. Until
     2026-08-25 `BoxOps` drew `Section 1  #1-#85  85 cards` as inert text in a panel on the far
     side of the screen while `.browse-secthead` drew the same five rows here, foldable, tickable
     and walkable. Two renderings of one fact; the inert one is gone.

     A count of zero rather than a snapshot of the walk's own rows: what may not come back is a
     SECOND list, whatever it is styled as. */
  await expect(page.locator('.boxops-section')).toHaveCount(0)
  await expect(page.locator('.boxops-sections')).toHaveCount(0)
  await expect(page.locator('.browse-secthead').first()).toBeVisible()

  /* And the walk's headers really are the box's sections — the section's own count, which is
     what the deleted panel's `85 cards` used to repeat. NOT its span: a header built from
     `section_start`/`section_end` counts across the whole BOX, a different scale than a row's
     own `#1`/`#2` — the mixed-units defect the owner found on box WB1 R2, fixed by stating the
     section's own count instead (`sectionCountOf`, `position.ts`). */
  const first = page.locator('.browse-secthead').first()
  await expect(first).toContainText('Section 1')
  await expect(first).toContainText('cards')
})

test('the box lives in the walk\'s column, and the run line lives in the header', async ({
  page,
}) => {
  await open(page)

  /* THE STRUCTURAL HALF OF THE MERGE (owner, 2026-08-25): "merge its functionality (so not visual
     merge, but rebuild type merge) and all exist on the left side". The box's readings sit under
     the strip that names it and its operations sit at the bottom of the walk, because that column
     IS the box — the strip picks it and the list is its cards. */
  await expect(page.locator('.browse-map .boxops-identity')).toHaveCount(1)

  /* AND ITS OPERATIONS ARE REACHED FROM THAT COLUMN AND FROM NOWHERE ELSE. They are a sheet over
     the screen now rather than a slab at the foot of the walk — which is a layout answer to the
     same requirement, and the requirement is what this asserts: the way in is on the box's own
     header, and everything that acts on the box is behind it. */
  await expect(page.locator('.browse-map').getByRole('button', { name: 'Manage' })).toBeVisible()
  await openBoxOps(page)
  await expect(page.getByRole('button', { name: 'Rename' })).toBeVisible()
  await expect(page.getByRole('button', { name: /^Delete this box/ })).toBeVisible()
  await closeBoxOps(page)

  /* AND NOTHING ON THIS SCREEN CREATES A BOX (owner, 2026-08-26: "delete register a new box from
     inventory screen"). `RegisterBox` used to be the last thing in this column.

     ASSERTED AS AN ABSENCE, which is what this repo does with a deliberate removal — the same
     shape as `.inventory-modes` after D31 deleted the mode switch, and as the run panel's spend
     button before its preflight has answered. A control deleted with nothing watching comes back
     the next time somebody reads D20 and notices the screen cannot register a box.

     THE CAPABILITY IS NOT GONE AND THIS CASE DOES NOT CLAIM IT IS. `CaptureScreen.tsx` creates
     an empty box by name or number through the same `POST /boxes`; what this asserts is only
     that the second entry point on this screen stays deleted. */
  await expect(page.getByRole('button', { name: /^Register/ })).toHaveCount(0)
  await expect(page.locator('.boxops-new')).toHaveCount(0)

  /* THE RUNS HAD A THIRD COLUMN UNTIL 2026-08-26, THE LAST ROW UNTIL 2026-08-29, AND NOW A ROUTE.
     The slot survives and what sits in it is one status line — `BoxRuns`, which says whether
     anything is running over this box and hands the ticked selection to `#/runs`. Every
     assertion here is the one it always was, re-pointed: the box is not in that slot, the slot
     is not inside the card's guard, and it is a direct child of the body. The ordering below
     stays a MEASUREMENT rather than a class name, because a class assertion goes green the
     moment somebody reintroduces a tall sibling in row 1 under a different name, and a tall
     sibling in row 1 is the entire defect this layout was rebuilt to remove. */
  /* THE RUN LINE LEFT THE CONTENT COLUMN FOR THE HEADER ON 2026-08-29, and the assertion moves
     with it rather than being dropped. What it guarded was that the line is about the SHELF and
     is not a sibling the card can push around; in the header that is structural — its y is set
     by the header, which is the same on every card. The old ordering check (`runs` after
     `copies`) is replaced by the stronger one the move buys: the line is ABOVE the card band, so
     nothing about the selection can move it at all. */
  /* THE RUN LINE IS THE BOX'S, SO IT SITS WITH THE BOX. It moved into the box's own header at
     the top of the walk's column — not into the card's column, and not below the card band —
     which is the same guarantee stated against the layout that exists: nothing about the
     SELECTION can move it. */
  await expect(page.locator('.browse-map .boxruns')).toHaveCount(1)
  await expect(page.locator('.browse-side .boxruns')).toHaveCount(0)
  await expect(page.locator('.browse-card .boxruns')).toHaveCount(0)

  const runs = await page.locator('.boxruns').boundingBox()
  const band0 = await page.locator('.browse-card').first().boundingBox()
  if (runs === null || band0 === null) throw new Error('the content column did not render')
  expect(runs.y).toBeLessThan(band0.y + band0.height)

  /* AND THE SCREEN CLEARS `docs/DESIGN.md`'s OWN FIRST-CONTENT FLOOR: "the first row of real
     content sits within 150px of the top of the viewport". The run line is not that row any
     more — it sits under the box it is about, in the box's column — so the floor is measured
     where it applies, on the first thing the operator can use. It missed that floor by
     1014-1422px in the content column once, which is why it is measured at all. */
  const firstUse = await page.locator('.search-field-input').boundingBox()
  if (firstUse === null) throw new Error('the search field did not render')
  expect(firstUse.y).toBeLessThan(150)

  /* AND NO RUN PANEL AT ALL, WHICH IS THE 2026-08-29 HALF. It moved to `#/runs`; this asserts it
     did not leave a copy behind. `run-panel.spec.ts` guards the money button with `toHaveCount(0)`
     four times and `toHaveCount(1)` once on ITS route, so a second panel rendered here would be
     invisible to that file entirely — and a spend control on a screen that never showed a
     preflight is what D33's money gate exists to prevent. */
  await expect(page.locator('.run-panel')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Check cost' })).toHaveCount(0)

  /* AND THE COPIES ARE A BODY CHILD RATHER THAN A CARD CHILD. `.browse-under` renders `{detail}`,
     which carries a receipt whose twenty-second undo may still be running, and the whole reason
     it lives outside `.browse-side` is that a query matching no card must not unmount it. That
     was a prose promise, then a column boundary, and is now a grid row — assert it as a place so
     a later edit has to move it between rows to break it. */
  /* AND THE COPIES ARE DRAWN WITH THE CARD, under its photograph, which is where the question
     they answer is asked. What the old column boundary was protecting — a receipt whose undo is
     still running must not be unmounted by a query that matches no card — is not this element's
     job any more: the receipt is a toast on the product's own stack, and the case above proves
     it survives the rows being replaced. */
  await expect(page.locator('.browse-card .browse-under')).toHaveCount(1)
})

test('the copies of a card cannot be positioned by the pipeline console', async ({ page }) => {
  await open(page)

  /* THE DEFECT THIS PREVENTS SHIPPED BECAUSE NOTHING ASSERTED IT (found by the owner, 2026-08-26:
     "the location data that scrolls away after whitespace").

     `.browse-body` put the card and the run panel in the SAME GRID ROW and the copies in the row
     beneath. A grid row is as tall as its tallest cell, so the copies — D7's SKU -> positions map,
     the answer to the question this route exists to ask — began wherever the console ended.
     Measured on the owner's store before the fix: y=938 with the console closed, 378px of white
     below the card; y=1599 with a run PICKED, 1039px of white on a 2214px page.

     THIS TEST WAS REWRITTEN ON 2026-08-29 AND THE MEASUREMENT IS THE SAME ONE INVERTED. It used
     to mock a run, click it, and assert the console was TALLER than the card — because that is
     what made the old grid's failure reachable at full size. The console is not on this screen
     any more (the owner gave it `#/runs`), so the fixture is gone and what is asserted instead
     is that the thing left in its slot is SHORTER than the card band. That is the property the
     old row order was fighting for, stated directly.

     THE OLD FIXTURE IS NOT MISSED AND THE OLD GUARANTEE IS NOT WEAKER. A console that cannot be
     rendered here cannot set this row's height; `run-panel.spec.ts` owns everything about the
     panel's own layout on its own route. What stays here is the gap and the viewport, because
     those catch ANYTHING growing between the band and the copies — including whatever is put in
     this slot next. */
  await expect(page.locator('.run-panel')).toHaveCount(0)

  /* REWRITTEN AGAIN ON 2026-08-29, AND THIS TIME THE DEFECT IS STRUCTURALLY UNREACHABLE. The
     copies are in a COLUMN of their own beside the card, not a row beneath it, so no sibling's
     height can set their y — which is what every earlier version of this case was measuring in a
     roundabout way. `.browse-boxrun` is `display: none` on a numbered shelf now (it holds only
     the pooled/unplaced note), so it has no box to measure and the old height comparison would
     throw rather than pass.

     WHAT IS ASSERTED INSTEAD IS THE PROPERTY ITSELF: the copies start level with the band, not
     below it. A regression that put anything back above them in their own column fails this,
     and so does one that restores the stacked row order. */
  /* The two are the two halves of one band — the photograph and, beside it, the copies — so
     they are measured against each other in ONE layout read. What must not come back is the
     stacked row order, where the copies began wherever the thing above them ended. */
  const level = await page.evaluate(() => {
    const shot = document.querySelector('.browse-shot')
    const under = document.querySelector('.browse-under')
    if (shot === null || under === null) return null
    return under.getBoundingClientRect().top - shot.getBoundingClientRect().top
  })
  if (level === null) throw new Error('the card panel did not render')
  expect(Math.abs(level)).toBeLessThanOrEqual(24)

  /* AND THE ANSWER IS ABOVE THE FOLD. What the operator opened this screen to learn is where the
     card they are standing on IS — its position, how far into the box it sits, and the two doors
     out of inventory — and that whole thing is on screen without scrolling at the width and
     height this suite runs at. THE ANSWER IS THE ROW ITSELF SINCE D119, rather than a card above
     the list, which is what that entry deleted. The copies below it are a list and are scrolled
     to like any other; what may never come back is the answer itself starting below the fold. */
  await expect(page.locator('.card-locations-row.is-current')).toBeInViewport({ ratio: 1 })
  await expect(page.locator('.card-locations-rows')).toBeVisible()
})

test('the ticked selection is handed to the runs screen, and never lost silently', async ({
  page,
}) => {
  await open(page)
  /* COLLAPSED IS THE RESTING STATE (D31), so there are no rows to tick until the sections are
     open. The same two lines every mass-select case in this file opens with. */
  await expandAll(page)

  /* THE CAPABILITY THIS PROTECTS IS OLDER THAN THE SCREEN IT NOW CROSSES. `RunPanel` can scope a
     run to a ticked subset — a real server route that builds a symlink directory — and the ONE
     mass-select in the product is on this screen. When the panel moved to `#/runs` on 2026-08-29
     that capability was one edit away from being reachable from nowhere, which is exactly
     `CLAUDE.md`'s route-is-not-a-feature rule pointing at the change that caused it.

     ASSERTED AT THE SEAM RATHER THAN END TO END, deliberately: what `#/runs` does with a handoff
     is `run-panel.spec.ts`'s subject, and what this file owns is that the selection leaves here
     with the right box and the right count on it. */
  const first = page.locator('.browse-rowtick').first()
  await expect(first).toBeVisible()
  await first.check()

  const go = page.locator('.boxruns-go')
  /* `Run 1 ticked` — the count of what is ticked, on the control that carries it. The wording
     changed; the promise is the one this case was written for and is unchanged: the scope of the
     next run is stated where the press is. */
  await expect(go).toContainText('1 ticked')
  await expect(go).toHaveAttribute('href', '#/runs')

  /* AND UNTICKING PUTS THE WHOLE BOX BACK ON THE CONTROL. The label is the only place the scope
     of the next run is stated on this screen, so a stale count here is a person pressing a link
     that says 1 card and arriving at a screen that says the whole box — or worse, the reverse. */
  await first.uncheck()
  await expect(go).toContainText('Run this box')
})

/* D30's NEIGHBOURS, WHICH NOTHING IN THIS FILE HAD EVER RENDERED.
 *
 * Every fixture here passed `neighbors: null` — a real wire state that draws no block at all —
 * so the sentence, its vocabulary, its face and its two sites were unasserted from the day they
 * shipped. The four fixtures that tried to pin the gap count spelled it `gaps_in_section`, a
 * field that exists in no server, no type and no component, so they set nothing and the app's
 * behaviour happened to match. That is the shape D57 records one screen over: the change was
 * makeable with every check green.
 *
 * A STORE OF ITS OWN rather than neighbours on `CARDS`, because the block is ~31px and the band
 * and copy-row measurements in this file are taken against a fixture that does not draw one. */
const NEIGHBORLY: Cards = {
  '2/1': card({
    index: 1,
    state: 'identified',
    name: 'Bashful Bloom',
    sku: '8937370',
    section: 1,
    sectionStart: 1,
    sectionEnd: 3,
    /* RIFTBOUND-SHAPED, WHICH IS THE WHOLE POINT OF THE CASE. `Champion, Epithet` is 494 of
       1368 real names, so the comma inside a name fires before the boundary between them —
       the reason the joined sentence could not be scanned and the reason the epithet has to
       demote rather than disappear. */
    neighbors: {
      prev: { index: 18, slot: 17, name: 'Galio, Indefaticable' },
      next: { index: 20, slot: 19, name: 'Evelynn, Entrancing' },
    },
  }),
  '2/3': card({
    index: 3,
    state: 'identified',
    name: 'Bashful Bloom',
    sku: '8937370',
    section: 1,
    sectionStart: 1,
    sectionEnd: 3,
    /* THE BOX'S FRONT: no card in front of it, so one row and not a pretend `between`. Its
       neighbour is also the case with NO comma, which must render whole rather than being cut
       at some other punctuation. */
    neighbors: { prev: null, next: { index: 4, slot: 3, name: 'Conscription' } },
  }),
  /* LOC-28'S ROW: two on-hand cards toward the back carry no name. The owner's ruling of
     2026-09-24 (amending D116) makes them the neighbour, said as "2 unread cards", where D116
     walked past them to Galio. `next` is a named card, in the same fixture, so a renderer that
     drew every side as unread fails too. */
  '2/5': card({
    index: 5,
    state: 'identified',
    name: 'Bashful Bloom',
    sku: '8937370',
    section: 1,
    sectionStart: 1,
    sectionEnd: 6,
    neighbors: {
      prev: { index: 20, slot: 19, name: null, unread: 2 },
      next: { index: 22, slot: 21, name: 'Conscription', unread: 0 },
    },
  }),
}

test('UX-190 — a sale says which card took its number, and the rows hold still', async ({ page }) => {
  const cards: Cards = Object.fromEntries(Object.entries(NEIGHBORLY).map(([key, held]) => [key, { ...held }]))
  await open(page, BOXES, { cards, search: (query) => searchAnswer(query, cards) }, () => PRICING, SALE, { hideSold: true })
  await expandAll(page)
  await page.locator('.browse-row').nth(2).click()
  const rects = async () =>
    page.locator('.browse-row').evaluateAll((rows) => rows.map((row) => Math.round(row.getBoundingClientRect().top)))
  /* THE PRESS IS BROUGHT INTO VIEW BEFORE THE ROWS ARE READ (DEBT36, the PR 2 CI trace). On the
     Ubuntu runner the copies panel loads the current copy's row below the 720px fold, so
     Playwright's own click scrolled the page 77px to reach Mark sold, and every row read 77px
     higher after the sale although the sale moved nothing. The scroll is the test's, so it now
     happens first, once the press is on screen, and only the sale lies between the two reads. */
  const markSold = page.locator('.card-locations-row.is-current').getByRole('button', { name: 'Mark sold' })
  await expect(markSold).toBeVisible()
  await markSold.scrollIntoViewIfNeeded()
  const before = await rects()
  await markSold.click()
  /* Card 5's neighbour in front, Conscription, takes its number. The receipt says so, since the
     list does not move to show it (FLT-22). */
  await expect(receiptToast(page)).toContainText('Conscription is now card')
  expect(await rects()).toEqual(before)
})

test('S1 — bringing a card back names the box, never its number', async ({ page }) => {
  /* `BoxBrowse.tsx:CardOps`'s resurrect toast used to say `B2 #4 is back in its box` off
   * `storeKeyText` — the server's own machine spelling of the store key, a raw box number,
   * on the owner's screen. The box's own name, off `place.box_name`, is what the fix reads. */
  const wire = await open(page)
  await expandAll(page)
  await page.locator('.browse-row', { hasText: 'Eiscue' }).click()
  await page.getByRole('button', { name: 'Card actions' }).click()
  const bring = page.getByRole('menuitem', { name: 'Bring this card back' })
  await expect(bring).toBeVisible()
  await bring.click()

  const toast = page.locator('.bn-toast', { hasText: 'Card brought back' })
  await expect(toast).toContainText('ME01 commons #4 is back in its box')
  await expect(toast).not.toContainText('B2 #4')

  const sent = wire.find((entry) => entry.path === '/inventory/2/4/sold')
  expect(sent?.body).toEqual({ undo: true })
})

test('S2 — a sold card says so once, not on the hero, the row and the phone bar all at once', async ({
  page,
}) => {
  /* `Eiscue` (2/4) arrives already sold — no undo window in play, so this is the CONFIRMED,
   * terminal state the hero's own chip, the row's own state pill and the phone's sticky bar
   * used to all draw `Sold` for at once. The struck number is the row's own mark now (S2). */
  await open(page)
  await expandAll(page)
  await page.locator('.browse-row', { hasText: 'Eiscue' }).click()

  const row = page.locator('.card-locations-row.is-current')
  await expect(row).toBeVisible()
  await expect(row.locator('.card-locations-state .bn-pill', { hasText: 'Sold' })).toHaveCount(0)
  await expect(row.locator('.card-locations-action .bn-pill', { hasText: 'Sold' })).toHaveCount(0)
  await expect(page.locator('.browse-hero-chips .bn-pill', { hasText: 'Sold' })).toHaveCount(1)
})

test('S2 — the phone sticky bar draws no second Sold pill beside the hero', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  // Deep-linked (`&card=`) rather than walked to, so this reaches Eiscue with no box-rail
  // drawer in the way — the same door a Review pill link or an order pull opens it by.
  const cards: Cards = { ...CARDS, '2/4': card({ index: 4, state: 'sold', name: 'Eiscue', sku: '8937371', section: 1, sectionStart: 1, sectionEnd: 3, cid: 'eiscue-cid' }) }
  const store: Store = { cards, search: (query) => searchAnswer(query, cards) }
  await open(page, BOXES, store, () => PRICING, SALE, {
    settle: '.card-locations-owner',
    route: '/#/inventory?box=2&card=eiscue-cid',
  })

  await expect(page.locator('.browse-hero-chips .bn-pill', { hasText: 'Sold' })).toHaveCount(1)
  await expect(page.locator('.browse-actionbar-slot .bn-pill', { hasText: 'Sold' })).toHaveCount(0)
})

test('S3 — with Hide sold on, a search count excludes what the fold already hides', async ({
  page,
}) => {
  /* `matchesByShelf`/`searchBoxes` used to count every matching copy, sold ones included, no
   * matter what Hide sold said — so a term matching only sold copies drew "1 match" on two rail
   * cells and "2 of 3 boxes" on the count line, while the pane itself said "Nothing matches".
   * Box 2 keeps a LIVE, unrelated card so the walk lands there naturally, the way the review's
   * own repro read: the two boxes the search over-counted were neither of them the open one. */
  const boxes = {
    boxes: [
      ...TWO_BOXES.boxes,
      { box: 9, name: 'Extra shelf', sections: [1], state: 'open', capacity: null, fill: 1, next_index: 2, cards: 1, sold: 1, retired: 0, listed: 0, moved: 0, sections_detail: [{ section: 1, start: 1, end: 1, count: 1 }] },
    ],
  }
  const cards: Cards = {
    '2/1': card({ index: 1, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3 }),
    '7/1': card({ index: 1, state: 'sold', name: 'Wobbuffet', sku: '9191919', box: 7, boxName: 'ME01 spares', section: 1, sectionStart: 1, sectionEnd: 1, boxTotal: 1 }),
    '9/1': card({ index: 1, state: 'sold', name: 'Wobbuffet', sku: '9191919', box: 9, boxName: 'Extra shelf', section: 1, sectionStart: 1, sectionEnd: 1, boxTotal: 1 }),
  }
  const store: Store = { cards, search: (query) => searchAnswer(query, cards) }
  await open(page, boxes, store, () => PRICING, SALE, { hideSold: true })

  await page.getByRole('searchbox').fill('Wobbuffet')
  await expect(page.getByText('Nothing matches')).toBeVisible()

  const meta = page.locator('.browse-boxcell-meta')
  await expect(meta).toHaveText(['No match', 'No match', 'No match'])

  await expect(page.locator('.browse-filterbar .bn-filtercount-figure')).toHaveText('0 of 3 boxes')
})

test('UX-244 — one copy moves to another box from its own row, and the receipt names the box', async ({ page }) => {
  await open(page, TWO_BOXES, ACROSS, () => PRICING, SALE, { route: '/#/inventory?box=2' })
  const sent: { path: string; body: unknown }[] = []
  await page.route(/\/inventory\/\d+\/\d+\/move$/, async (route) => {
    const url = new URL(route.request().url())
    sent.push({ path: url.pathname, body: route.request().postDataJSON() })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ moved: '2/1', to: '7/41', box: 2, index: 1, new_box: 7, new_index: 41 }),
    })
  })
  const row = page.locator('.card-locations-row.is-current')
  await row.getByRole('button', { name: 'Move to another box' }).click()
  const dialog = page.getByRole('dialog', { name: /^Move/ })
  await expect(dialog).toBeVisible()
  await dialog.locator('.bn-pick').click()
  await page.locator('.bn-pick-opt', { hasText: 'ME01 spares' }).click()
  await dialog.getByRole('button', { name: 'Move', exact: true }).click()
  await expect(page.locator('.bn-toast')).toContainText('Moved to ME01 spares')
  expect(sent).toHaveLength(1)
  expect(sent[0]?.path).toBe('/inventory/2/1/move')
  expect(sent[0]?.body).toMatchObject({ to_box: 7 })
})

test('the header holds one worded primary and the filter bar one line, at 390 and 720', async ({
  page,
}) => {
  /* LANES-ADDENDUM "Tighten headers and filters": a page header holds at most one worded
   * primary (the rest IconButtons or a More menu), and a filter bar is one line — search plus
   * one Filters press, facets and sort behind it. Inventory's own `<Page>` passes neither
   * `toolbar` nor `verdict` (Inventory.tsx), so the header carries zero worded primaries
   * already; this measures that it stays that way and that the filter bar's own height still
   * reads as one control row, at both widths the owner asked this measured at. */
  for (const width of [390, 720]) {
    await page.setViewportSize({ width, height: 900 })
    // Below 640 the rail is a phone drawer — `.browse-mobilebar` chip settles it; at 720 the
    // desk rail is on screen from the start and the usual section-fold wait applies.
    await open(page, BOXES, STORE, () => PRICING, SALE, {
      settle: width < 640 ? '.browse-mobilebar' : undefined,
    })

    // ZERO WORDED PRIMARIES IN THE HEADER: the toolbar slot Page.tsx would draw one in is
    // simply not there — `.bn-toolbar` never renders when `Inventory.tsx` passes no `toolbar`.
    await expect(page.locator('.bn-toolbar')).toHaveCount(0)

    if (width < 640) {
      // Below 640 the whole rail — search, filters, the box list — sits behind the phone's
      // own drawer chip (`.browse-mobilebar`), so there is no filter bar row to measure above
      // the walk at all: the chip IS the one line. `.browse-filterbar` is correctly ABSENT
      // here, not merely narrow — asserted so a change that started rendering it inline does
      // not silently pass this case for the wrong reason.
      await expect(page.locator('.browse-filterbar')).toHaveCount(0)
      // D117's own thumb floor (40px+) is why this ceiling is looser than the desk bar's —
      // the chip is still one line, of touch-sized controls.
      const chip = page.locator('.browse-mobilebar')
      const chipBox = await chip.boundingBox()
      expect(chipBox?.height ?? 999, `mobile bar is ${chipBox?.height}px tall at ${width}`).toBeLessThan(80)
    } else {
      // ONE LINE: `.bn-filterbar-controls` is the search+Filters row alone — the facet/sort/
      // hide row hides inside it under 480px of the bar's OWN width (a container query, not
      // the page's), and `FilterCount`'s "N of M boxes" line is a SEPARATE sibling below
      // `.bn-filterbar-controls`, not part of the one-line claim this measures.
      const controls = page.locator('.browse-filterbar .bn-filterbar-controls')
      await expect(controls).toBeVisible()
      const controlsBox = await controls.boundingBox()
      expect(controlsBox?.height ?? 999, `filter bar controls are ${controlsBox?.height}px tall at ${width}`).toBeLessThan(60)
    }

    // THE SPACE ABOVE THE WALK: from the page's own top to where the box rail / card panel
    // begins. Recorded as a measurement, not asserted against a guessed ceiling — the number
    // is what the owner asked for, not a pass/fail this case invents one for.
    const pageTop = (await page.locator('.bn-page').boundingBox())?.y ?? 0
    const walkTop = (await page.locator('.browse-body, .browse-mobilebar').first().boundingBox())?.y ?? 0
    console.log(`INFO space above the walk at ${width}px: ${Math.round(walkTop - pageTop)}px`)
  }
})

test('the value sort ranks boxes by their own dollar total, high to low by default', async ({
  page,
}) => {
  /* The owner's ruling, 2026-09-24: the value list (D159, `#/pricing?band=`) becomes an
   * Inventory sort through the shared `SortControl`, fetched lazily off the same aggregates
   * `ValueBands.tsx` reads — `GET /pipeline/value`'s per-box `total`, never re-derived here. */
  await page.route(/\/pipeline\/value\?/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        at: '2026-09-24T00:00:00+00:00',
        basis: 'market',
        threshold: '0.49',
        sources: [],
        boxes: [
          { box: 2, name: 'ME01 commons', cards: 7, valued: 5, unpriced: 2, under_cutoff: 2, at_or_over: 3, total: '12.50', per_card: '2.50', top: null },
          { box: 7, name: 'ME01 spares', cards: 40, valued: 30, unpriced: 10, under_cutoff: 5, at_or_over: 25, total: '340.00', per_card: '11.33', top: null },
        ],
        unrankable: { total: 0, never_identified: 0, read_nothing: 0, no_reading: 0, by_box: {} },
        totals: { cards: 47, valued: 35, value: '352.50', under_cutoff: 7, at_or_over: 28 },
      }),
    })
  })

  await open(page, TWO_BOXES, STORE)

  const names = page.locator('.browse-boxcell .browse-boxcell-name')
  await expect(names).toHaveText(['ME01 commons', 'ME01 spares'])

  await page.locator('.browse-filterbar .bn-filterbar-trigger:visible').click()
  await page.locator('.bn-filterbar-popover .bn-pick', { hasText: /^Sort/ }).click()
  await page.locator('.bn-pick-opt', { hasText: 'Value' }).click()
  await page.keyboard.press('Escape')

  await expect(names).toHaveText(['ME01 spares', 'ME01 commons'])
  await expect(
    page.locator('.browse-boxcell', { hasText: 'ME01 spares' }).locator('.browse-boxcell-meta'),
  ).toContainText('$340')
})

test('S4 — the move panel offers boxes most recent first, never by number', async ({ page }) => {
  /* S4: `MovePanel`'s own comment said "most recent first" while `others` was the server's
   * `GET /boxes` order — box number, since nothing sorted it. Box 9 is a lower recency than
   * box 7's stored visit but a HIGHER number, so number order and recency order disagree and
   * this case can tell them apart. */
  const boxes = {
    boxes: [
      ...TWO_BOXES.boxes,
      { box: 9, name: 'Extra shelf', sections: [1], state: 'open', capacity: null, fill: 3, next_index: 4, cards: 3, sold: 0, retired: 0, listed: 0, moved: 0, sections_detail: [{ section: 1, start: 1, end: 3, count: 3 }] },
    ],
  }
  await page.addInitScript(() => {
    /* eslint-disable-next-line no-restricted-syntax -- SEEDING THE KEY UNDER TEST (D132),
       `dataRules.ts:boxesMostRecentFirst`'s own subject. */
    window.localStorage.setItem('banchi.box-recency', JSON.stringify({ '9': '2026-09-09T10:00:00.000Z' }))
  })
  await open(page, boxes, ACROSS, () => PRICING, SALE, { route: '/#/inventory?box=2' })

  await page.locator('.card-locations-row.is-current').getByRole('button', { name: 'Move to another box' }).click()
  const dialog = page.getByRole('dialog', { name: /^Move/ })
  await expect(dialog).toBeVisible()
  await dialog.locator('.bn-pick').click()
  await expect(page.locator('.bn-pick-opt')).toHaveText(['Extra shelf', 'ME01 spares'])
})

test('S4 — the BoxOps "Move to box" select offers boxes most recent first, never by number', async ({
  page,
}) => {
  const boxes = {
    boxes: [
      ...TWO_BOXES.boxes,
      { box: 9, name: 'Extra shelf', sections: [1], state: 'open', capacity: null, fill: 3, next_index: 4, cards: 3, sold: 0, retired: 0, listed: 0, moved: 0, sections_detail: [{ section: 1, start: 1, end: 3, count: 3 }] },
    ],
  }
  await page.addInitScript(() => {
    /* eslint-disable-next-line no-restricted-syntax -- SEEDING THE KEY UNDER TEST (D132). */
    window.localStorage.setItem('banchi.box-recency', JSON.stringify({ '9': '2026-09-09T10:00:00.000Z' }))
  })
  await open(page, boxes, ACROSS, () => PRICING, SALE, { route: '/#/inventory?box=2' })
  await openBoxOps(page)
  await page.getByRole('button', { name: 'Move to box' }).click()
  await page.locator('.bn-field .bn-pick').click()
  await expect(page.locator('.bn-pick-opt')).toHaveText(['Extra shelf', 'ME01 spares'])
})

test('the neighbours are ranked, not joined — the names are the only thing drawn at ink', async ({
  page,
}) => {
  await open(page, BOXES, {
    cards: NEIGHBORLY,
    search: (query) => searchAnswer(query, NEIGHBORLY),
  })

  const band = page.locator('.card-locations-row.is-current .nb')
  await expect(band).toBeVisible()

  /* THE KEYS ARE THE COMPOSER'S OWN TWO WORDS. `in front` / `behind` was built first and reads
     better as a physical pair, and it takes the NEIGHBOUR as its subject where `placeParts`
     takes THIS CARD — so the row and the `aria-label` would have disagreed about which side
     the same name was on. */
  /* Back, this card, front: the owner's orientation, card 1 at the far back (LOC-07). */
  await expect(band.locator('.nb-key')).toHaveText(['back', 'this', 'front'])

  /* THE SPLIT, which is what makes two proper nouns findable in a column: the champion is the
     recognition token at ink and the epithet is the disambiguator, demoted and never dropped —
     61 of 99 champions carry more than one, so `Master Yi` alone names fourteen cards. */
  await expect(band.locator('.nb-name b')).toHaveText(['Galio', 'Evelynn'])
  await expect(band.locator('.nb-rest')).toHaveText([', Indefaticable', ', Entrancing'])

  /* THE JOINED SENTENCE SURVIVES ON `aria-label`, so a screen reader hears one sentence where
     the eye is given two rows — and it is `placeParts`' own composition, not a second author's,
     which is what the one-composer rule in server.ts is for. */
  await expect(band).toHaveAttribute(
    'aria-label',
    'It sits in front of Galio, Indefaticable and behind Evelynn, Entrancing.',
  )
})

test('the neighbour names are read as words, not as metadata', async ({ page }) => {
  await open(page, BOXES, {
    cards: NEIGHBORLY,
    search: (query) => searchAnswer(query, NEIGHBORLY),
  })

  /* THE TWO DEFECTS THIS REPLACED, ASSERTED AS THE PROPERTIES THEY ARE.
     `.card-locations-boxname` drew this at 10px UPPERCASE TRACKED MONO — the metadata register
     — which made the only running English in the product a row of rectangles. docs/DESIGN.md
     cuts on exactly this line: "Mono carries all metadata… the body face is reserved for
     sentences a human reads." Uppercase is the half that costs most, because word-shape is the
     fast route to a name last seen on a piece of cardboard.

     Asserted on the COPIES ROW and not the band, because the row is where the borrow was. */
  const name = page.locator('.card-locations-owner .nb-name').first()
  await expect(name).toBeVisible()
  const drawn = await name.evaluate((node) => {
    const style = getComputedStyle(node)
    return {
      transform: style.textTransform,
      tracking: style.letterSpacing,
      family: style.fontFamily,
      text: node.textContent ?? '',
    }
  })
  expect(drawn.transform).toBe('none')
  expect(drawn.tracking === 'normal' || drawn.tracking === '0px').toBe(true)
  /* THE READING FACE, WHICH IS THE PROPERTY — the product's body family rather than the machine
     one. The family itself changed with the rebrand and the rule did not: a name a person reads
     is not set in the face that carries SKUs and reason codes. Measured against the face the
     screen's own machine strings are drawn in, so it cannot go green by both moving together. */
  const machine = await page
    .locator('.card-locations-meta-mono')
    .first()
    .evaluate((node) => getComputedStyle(node).fontFamily)
  expect(drawn.family).not.toBe(machine)
  expect(drawn.family.toLowerCase()).not.toContain('mono')
  /* The name arrives with its own case intact rather than being uppercased by the stylesheet —
     which is the same fact from the DOM's side, and the one a `text-transform` regression
     would leave true while the screen went back to rectangles. */
  expect(drawn.text).toContain('Galio')

  /* THE KEY KEEPS THE TRACKING, and that is not an inconsistency. An isolated two-word token
     has no word boundary to protect; an eighty-eight-character sentence does. */
  const key = page.locator('.card-locations-owner .nb-key').first()
  await expect(key).toHaveCSS('text-transform', 'uppercase')
})

test('a card at the back of the box gets one row, not a pretend between', async ({ page }) => {
  await open(page, BOXES, {
    cards: NEIGHBORLY,
    search: (query) => searchAnswer(query, NEIGHBORLY),
  })

  /* READ OFF THE COPIES LIST RATHER THAN THE BAND, because both copies of this SKU are drawn
     there unconditionally — so the case needs no fold, no walk and no second selection, and it
     asserts the block at the site that draws it once per copy. */
  const front = page.locator('.card-locations-owner .nb').nth(1)
  await expect(front).toBeVisible()
  await expect(front.locator('.nb-row')).toHaveCount(2)
  await expect(front.locator('.nb-key')).toHaveText(['this', 'front'])

  /* A NAME WITH NO COMMA RENDERS WHOLE. The seam splits on the first `, ` and refuses any other
     punctuation — the same refusal `PositionLabel` makes for a label it cannot parse — so every
     Pokemon name takes this branch and is drawn exactly as the server sent it. */
  await expect(front.locator('.nb-name b')).toHaveText(['Conscription'])
  await expect(front.locator('.nb-rest')).toHaveCount(0)
  /* Nothing toward the back: card 1 is at the far back, so this card sits behind its one
     neighbour and in front of nothing (UX-186). */
  await expect(front).toHaveAttribute('aria-label', 'It sits behind Conscription.')
})

test('an unread neighbour is said in words, and counts as the neighbour (LOC-28)', async ({ page }) => {
  await open(page, BOXES, {
    cards: NEIGHBORLY,
    search: (query) => searchAnswer(query, NEIGHBORLY),
  })

  /* THE OWNER'S RULING, 2026-09-24 (amending D116): an unread card is a neighbour. D116 walked
     past it to the nearest named card and added "with 2 unidentified cards in between"; the
     owner read that as a real card dropped from the sentence (UX-264). Now the side IS the
     unread run, "2 unread cards", and never a bare figure (D116's own complaint).

     THE THIRD COPY IS THE SUBJECT and its two sides are the case: `prev` is two unread cards,
     `next` is a named card. A renderer that drew every side as unread fails on the second row,
     and one that dropped the unread side fails on the first. */
  const reached = page.locator('.card-locations-owner .nb').nth(2)
  await expect(reached).toBeVisible()
  await expect(reached.locator('.nb-row[data-side="back"] .nb-unread')).toHaveText('2 unread cards')
  await expect(reached.locator('.nb-name b')).toHaveText(['Conscription'])
  await expect(reached.locator('.nb-row[data-side="back"]')).not.toContainText(/#\d/)

  /* AND IN `said`, WHICH IS THE HALF THE EYE CANNOT SEE HERE AND THE FULFILLER READS AT 20px. */
  await expect(reached).toHaveAttribute('aria-label', 'It sits in front of 2 unread cards and behind Conscription.')

  /* A ROW WHOSE NEIGHBOURS ARE BOTH NAMED SAYS NO "unread", asserted on a DIFFERENT copy. */
  const adjacent = page.locator('.card-locations-owner .nb').first()
  await expect(adjacent.locator('.nb-unread')).toHaveCount(0)
  await expect(adjacent).toHaveAttribute(
    'aria-label',
    'It sits in front of Galio, Indefaticable and behind Evelynn, Entrancing.',
  )
})

/** THE LADDER AFTER A SALE, as a mutable store — `sellableStore`'s trick one field over.
 *
 *  Three copies of one SKU at indices 1, 3 and 5. Copy 5's `after` names copy 3, so selling
 *  copy 3 is a sale that MOVES ANOTHER ROW'S LANDMARK — and `sell` rewrites that landmark the
 *  way the server computes it, which harness T7 proves it does against a real `do_mark_sold`.
 *  Without the rewrite this case would rest on the optimistic overlay and pass against a stub
 *  that contradicts the wire, which is the trap `sellableStore` was written for. */
function laddersAfterSale(): { store: Store; sell: (key: string) => void } {
  const cards: Cards = {
    '2/1': card({
      index: 1,
      state: 'identified',
      name: 'Bashful Bloom',
      sku: '8937370',
      section: 1,
      sectionStart: 1,
      sectionEnd: 6,
      neighbors: { prev: { index: 0, slot: 0, name: 'Mantine', unread: 0 }, next: null },
    }),
    '2/3': card({
      index: 3,
      state: 'identified',
      name: 'Bashful Bloom',
      sku: '8937370',
      section: 1,
      sectionStart: 1,
      sectionEnd: 6,
      neighbors: { prev: { index: 1, slot: 1, name: 'Mantine', unread: 0 }, next: null },
    }),
    '2/5': card({
      index: 5,
      state: 'identified',
      name: 'Bashful Bloom',
      sku: '8937370',
      section: 1,
      sectionStart: 1,
      sectionEnd: 6,
      neighbors: {
        prev: { index: 3, slot: 2, name: 'Bashful Bloom', unread: 0 },
        next: null,
      },
    }),
  }
  return {
    store: { cards, search: (query) => searchAnswer(query, cards) },
    sell: (key) => {
      const held = cards[key]
      if (held !== undefined) held.state = 'sold'
      /* WHAT THE SERVER WOULD RECOMPUTE: copy 5's landmark was the card that just left, so it
         moves outward to the next one still in the drawer. */
      if (key === '2/3') {
        const behind = cards['2/5']
        if (behind !== undefined) {
          behind.place.neighbors = {
            prev: { index: 1, slot: 1, name: 'Mantine', unread: 0 },
            next: null,
          }
        }
      }
    },
  }
}

test('selling a card moves the landmark on the rows beside it, with no reload', async ({
  page,
}) => {
  const { store, sell } = laddersAfterSale()
  /* THE STORE MOVES INSIDE THE SALE (see `movesOnSale`). The landmark this case is about is
     recomputed by the server and read back by the press's own re-read, so a move written after
     the click is answered too late and the ladder never changes. */
  const sale = movesOnSale(() => sell('2/3'))

  /* COUNTED OFF THE REQUESTS THEMSELVES rather than off `open()`'s wire log, which records the
     writes and the reads it has an opinion about — `GET /inventory/<box>` is stubbed there and
     not recorded, and this case is about exactly that read happening a second time.
     D192 (item 2): the walk re-reads its OWN box, `GET /inventory/<box>`, rather
     than the whole-store `GET /inventory` this case originally counted — the box-scoped route
     is what replaced it, and re-reading the box is exactly the "no reload" claim this case
     makes. */
  const walkReads: string[] = []
  page.on('request', (request) => {
    const path = new URL(request.url()).pathname
    if (request.method() === 'GET' && /^\/inventory\/\d+$/.test(path)) walkReads.push(path)
  })

  await open(page, BOXES, store, () => PRICING, sale)

  /* Copy 5 counts from copy 3, which is about to be sold out from under it. */
  const behind = copyRow(page, 'Box 2, Section 1, Card 3')
  const ladder = page.locator('.card-locations-owner .nb').nth(2)
  await expect(ladder.locator('.nb-name b')).toHaveText(['Bashful Bloom'])

  const before = walkReads.length

  await behind.getByRole('button', { name: 'Mark sold' }).click()

  /* THE PRESS IS THE REFRESH. `Inventory.tsx:doSell` bumps `reloads`, which is `BoxBrowse`'s
     `reloadToken` — so `GET /inventory` and the copies search both run again and every place
     block on the screen is recomputed by the server. The operator presses nothing else and
     reloads nothing: this is the question "does the ladder update, or do I refresh?" asserted
     rather than reasoned about. */
  await expect(ladder.locator('.nb-name b')).toHaveText(['Mantine'])
  await expect(() => expect(walkReads.length).toBeGreaterThan(before)).toPass({ timeout: 5000 })

  /* AND THE SOLD CARD IS NOT NAMED ANYWHERE IN THE LADDER — the whole complaint, at the site
     it was made. Asserted over every ladder on the screen rather than the one row, because a
     landmark that moved on the row being looked at and stayed on its neighbour is the shape
     this would come back as. */
  const ladders = await page.locator('.card-locations-owner .nb').allTextContents()
  expect(ladders.join(' | ')).not.toContain('Bashful Bloom')
})

test('the gap clause is gone from every site that drew it', async ({ page }) => {
  await open(page, BOXES, {
    cards: NEIGHBORLY,
    search: (query) => searchAnswer(query, NEIGHBORLY),
  })

  /* "· 2 slots in this section are empty" (owner, 2026-08-30: deleted outright).
     D58 already claimed it was structurally empty — "`section_gaps` is structurally zero for a
     consolidated box" — and it is not: the server counts the terminal records between the
     section's bounds, so box 1 with two sold drew the clause on every card in it. Under D58 the
     box closes up, so `Card 19` is the nineteenth card a hand can count to and the clause's one
     stated job in D30, saying why a hand-count came out short, is void.

     ASSERTED OVER THE WHOLE DOCUMENT rather than on one node, because the string had three
     render sites and a fix that reached two of them is the one this case exists to catch. */
  const body = await page.locator('body').innerText()
  expect(body.toLowerCase()).not.toContain('slots in this section')
  expect(body.toLowerCase()).not.toContain('slot in this section')

  /* AND OUT OF `said`, WHICH IS THE HALF THE VISIBLE TEXT CANNOT SEE. The first version of
     this case asserted `innerText` alone and was mutation-tested by re-appending the clause
     inside `placeParts` — it PASSED, because on this screen `said` only ever reaches an
     `aria-label`. It is not decoration there: `#/fulfillment` renders the same string as
     visible 20px body text, so a clause that came back in the composer would be invisible
     here and on screen for the Fulfiller. Asserted where the composer puts it. */
  const label = (await page.locator('.nb').first().getAttribute('aria-label')) ?? ''
  expect(label.toLowerCase()).not.toContain('in this section')

  /* AND THE CLASS THAT USED TO CARRY THE SENTENCE IS RETIRED, not merely emptied — an empty
     rule left behind is what a later change re-populates without reading this one. */
  await expect(page.locator('.browse-between')).toHaveCount(0)
})

test('the photograph is sized by its column, not by the rows beside it', async ({ page }) => {
  await open(page)

  const photo = page.locator('.browse-photo')
  await expect(photo).toBeVisible()
  const shot = await photo.boundingBox()
  const rows = await page.locator('.browse-about').boundingBox()
  if (shot === null || rows === null) throw new Error('the band did not render')

  /* IT WAS PINNED TO THE ROWS FOR A FEW HOURS AND IS NOT ANY MORE (owner: "more space given to
     the middle (ie photo gets larger)"). What made that affordable is `capturedText` — the ISO
     stamp was the widest value on the card at ~234px and now reads `6:35pm · Aug 23`, so the
     facts need a fraction of the width they did and the photograph takes the rest.

     Asserted as a floor rather than an exact size: the track is a design value that may be
     re-cut, and what must not come back is a thumbnail. */
  expect(shot.width).toBeGreaterThan(200)

  /* THIS USED TO ASSERT THE PHOTOGRAPH WAS THE TALLER SIDE, and that stopped being true when the
     facts grew from seven rows to eleven. It flipped back on 2026-08-26 — the photograph is
     268x374 against 318 of facts — which is the second flip and the reason the property being
     guarded is a BAND rather than an ordering: which side is taller is an accident of how many
     rows the panel happens to draw. What must hold is that the two stay within reach of each
     other — neither a photograph towering over a short list (the 587 against 204 that started all
     of this) nor a thumbnail beside a long one. */
  /* THE BAND COMPARISON IS RETIRED, NOT WEAKENED, BECAUSE THE TWO ARE NO LONGER A BAND. The
     facts left this column on 2026-08-29 to cap the copies; the photograph now takes the whole
     middle third, so "the two stay within reach of each other" is a question about two different
     columns and answering it would pin the ratio to this case.

     WHAT REPLACES IT IS THE PROPERTY THAT ACTUALLY MATTERS NOW: the photograph FILLS its column.
     That is what the owner asked for ("the photo takes up more of the page") and it is what a
     regression would take away — a height cap, a max-width, or a re-introduced sibling track
     would all leave slack here. Measured at the time: 449px of a 449px track at 1440. */
  const mid = await page.locator('.browse-shot').boundingBox()
  if (mid === null) throw new Error('the card column did not render')
  expect(mid.width - shot.width).toBeLessThan(8)

  /* AND THE FACTS ARE STILL ON SCREEN, in their new home, which is the half of the move the
     owner asked for by name. Two columns at 1440 and one at 1280 — so this asserts presence and
     that no pair was split across a column break, never the count. */
  /* The facts moved again with the rebuild — under the band, in a disclosure of their own — so
     this asserts what it always asserted: they are on screen, drawn once, and no pair of them is
     split across a break. */
  await expect(page.locator('.browse-details .browse-facts').first()).toBeVisible()

  /* DEFECT 1, ASSERTED AT THE VIEWPORT design-check ACTUALLY RUNS. The facts' value track was
     `1fr`, so it was 260px at 1440 — 96 to 224px of trailing white on every one of eleven rows,
     1959px per card — and 100px at 1280, where `Captured`, `Rarity` and `Run` all wrapped to two
     lines. One declaration produced a surplus at one width and a shortage at the other. A fixed
     300px track (84 label + 12 gap + 204 value, against 164px of widest measured ink) is the same
     at both, and a wrapped row is what proves it has gone back to flexing.

     THE MUTATION THAT PROVES THIS IS A SQUEEZE, NOT A `1fr`, and the difference is worth writing
     down because the obvious mutation does not fail. Restoring `1fr` to track 2 now splits the
     remainder with track 3 and leaves the facts 274px at 1280 — wide enough not to wrap, so the
     case stays green against it. Setting track 2 to `minmax(0, 196px)` — the exact width the old
     two-track band produced at 1280 — takes a row to 48px and this red. Observed, both ways. */
  for (const row of await page.locator('.browse-fact').all()) {
    const box = await row.boundingBox()
    if (box === null) throw new Error('a fact row did not render')
    expect(box.height).toBeLessThan(40)
  }

  /* The ratio is the card's, and it is on the IMAGE — see the next case for why that matters. */
  expect(shot.height / shot.width).toBeGreaterThan(88 / 63 - 0.05)
  expect(shot.height / shot.width).toBeLessThan(88 / 63 + 0.05)

  /* TOP-ALIGNED IS NOW A STATEMENT ABOUT THE TWO COLUMNS, not about the photograph and the rows
     inside one. The facts moved to the head of the copies column on 2026-08-29, so they start at
     the body's top while the photograph starts below the card's headline — 58px lower, by
     design. Comparing those two would pin the headline's height into this case.

     What "flush" means here is that the card column and the copies column begin together, which
     is the grid property a regression would break (a stray margin, a row assignment, an
     `align-items` change).

     BOTH TOPS COME OUT OF ONE LAYOUT, and that is the whole of the fix for a red this case
     really did produce: `Received: 1.5` against this 1px allowance, twice in 80 loaded repeats
     on 2026-08-30. `mid` is read forty lines above, and eleven `boundingBox()` round-trips
     separate it from the read below — so the two numbers were being taken from two different
     moments and subtracted as though they were one. Anything that moves the grid inside that
     window (row 1 growing as a face swaps in) shows up here as a gap between two columns that
     never stopped being flush. One `evaluate` cannot be wrong about that, and it weakens
     nothing: same two elements, same tops, same allowance. */
  const tops = await page.evaluate(() => {
    const shot = document.querySelector('.browse-shot') as HTMLElement
    const copies = document.querySelector('.browse-under') as HTMLElement
    return Math.abs(copies.getBoundingClientRect().top - shot.getBoundingClientRect().top)
  })
  expect(tops).toBeLessThanOrEqual(1)

  /* And the facts sit BELOW the band rather than inside the photograph's column — the move that
     bought the photograph its width. */
  expect(rows.y).toBeGreaterThanOrEqual(mid.y + mid.height - 1)
})

test('a photo the store has lost gets a sentence, never a card-shaped hole', async ({ page }) => {
  await open(page)

  /* THE DEFECT THIS PREVENTS EXISTED FOR AN HOUR AND IS WORTH THE CASE. While the photograph took
     its height from the facts, the reservation had to live on a WRAPPER — and the wrapper holds
     whatever `PhotoPanel` returns, so a card whose file was gone got a 424x592 card-shaped box
     drawn around a 424x149 sentence and the re-shoot control pushed off the viewport. The ratio
     is back on the <img>, which cannot reach anything that is not an image.

     Routed rather than fixtured because no card in the real store lacks a photo: this is the 404
     branch, reached through the <img>'s own onError, which no fixture edit can produce. */
  await page.route(/\/photo\/\d+\/\d+/, (route) => route.fulfill({ status: 404, body: '' }))
  await page.reload()
  await expect(page.locator('.browse-sectfold').first()).toBeVisible()

  const panel = page.locator('.browse-absent')
  await expect(panel).toBeVisible()
  await expect(page.locator('.browse-photo')).toHaveCount(0)

  /* The sentence gets a measure to be read at, and no card-shaped box is reserved anywhere for a
     photograph that is not coming. A card box would be 1.4x taller than it is wide (63:88); this
     column is WIDER than it is tall, which is the shape of a paragraph. */
  const box = await panel.boundingBox()
  const shot = await page.locator('.browse-shot').boundingBox()
  if (box === null || shot === null) throw new Error('the absent panel did not render')
  /* THE PANEL IS THE SLOT, AND THE SENTENCE IS IN THE MIDDLE OF IT. The rebuild draws the absence
     as a hatched placeholder at the card's own ratio, which is a deliberate way of saying "no
     photograph here" and not the defect above: what that defect was is a tall box with the
     sentence stranded at the top of it and the remedy pushed off the viewport. So this asserts
     the two facts that tell them apart — the panel occupies the whole slot rather than sitting
     inside a second reserved box, and its text is centered in the panel rather than orphaned at
     the top. A 592px box around a 149px sentence puts that centre 37% out. */
  expect(shot.width - box.width).toBeLessThan(8)
  const centered = await panel.evaluate((node) => {
    const said = node.querySelector('p') as HTMLElement
    const own = node.getBoundingClientRect()
    const text = said.getBoundingClientRect()
    return Math.abs((text.top + text.height / 2 - own.top) / own.height - 0.5)
  })
  expect(centered).toBeLessThan(0.25)

  /* And the only thing the column holds beyond the sentence is the re-shoot control — 24px and a
     gap, not 440px of reserved nothing. */
  expect(shot.height - box.height).toBeLessThanOrEqual(48)

  /* And the remedy is still reachable, which is what the operator actually loses when a
     reservation swallows the column. One press further in since the control moved into
     `Correct claims` — the sentence above points at it, so what matters is that it is there and
     on screen, not that it is drawn before it is asked for. */
  await openCardOps(page)
  await page.getByRole('menuitem', { name: 'Correct claims' }).click()
  /* Still `Re-shoot this photo` and not `Add a photo`: the record CLAIMS a photo and the file is
     gone, which is the 404 branch. `Add a photo` is the other absent case — `photo: null`, a card
     `emit` recorded that was never photographed — and the control tells them apart. */
  /* Scoped to the sheet, because the absent panel now offers the same control in place as well —
     which is more remedy than this case asked for, not less. */
  const remedy = page.getByRole('dialog').getByRole('button', { name: 'Re-shoot this photo' })
  await expect(remedy).toBeVisible()
  await expect(remedy).toBeInViewport()
})

test('the box and the runs survive a query that selects no card', async ({ page }) => {
  await open(page)

  /* Both are about the SHELF, not the selection. Before the merge that was a prose promise on
     `{boxPanel}`; a query matching nothing is what actually tests it, and it is the same input
     `.browse-side`'s own comment names as the repro for a receipt vanishing mid-undo. */
  await page.locator('.search-field-input').fill('zzzz-no-such-card')
  await expect(page.locator('.browse-detail')).toHaveCount(0)

  /* EXACTLY ONE "no matches" MESSAGE, NOT TWO. A status-bar sentence
     (`nothing matches "…"`) and a full `EmptyState` ("Nothing matches here") used to render
     at the same time for the same empty result — two independent strings stacked vertically
     for one condition. The status-bar line is gone when this box's own matches are zero; the
     `EmptyState` carries the message (and a "Clear the search" way out) alone now. */
  await expect(page.locator('.browse-status-text', { hasText: 'nothing matches' })).toHaveCount(0)
  /* UX-260: and the list draws none either. The card pane's empty state says it once, with the
     one Clear. */
  await expect(page.getByText(/^Nothing matches/)).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Clear the search' })).toHaveCount(1)

  await expect(page.locator('.boxruns')).toBeVisible()
  await expect(page.locator('.browse-map .boxops-identity')).toHaveCount(1)
  await expect(page.locator('.browse-map').getByRole('button', { name: 'Manage' })).toBeVisible()

  /* AND THE ROWS THEY LEAVE BEHIND COST NOTHING. The card and the copies are grid rows above the
     console, and `grid-template-rows` is declared explicitly because the sticky map needs it — so
     the rows exist whether or not anything is in them, and a `row-gap` is drawn between declared
     rows even when both items are `display: none`. Measured before the fix: 48px of white above
     the console for two rows holding nothing. The row gap is a margin on the items now, so it
     leaves with them.

     24 RATHER THAN 0, and that is the console's own margin — one interval, which is what any
     first item on this page sits below. */
  /* THE ROWS THEY LEAVE BEHIND STILL COST NOTHING, and the check is re-pointed rather than
     dropped: the run line is in the header now, so what has to be true is that it sits ABOVE the
     body entirely and that the empty content rows collapse. `.browse-boxrun` is `display: none`
     when it holds no pooled/unplaced note, which is every numbered shelf — so it has no box, and
     asking for one is how this case would silently stop testing anything. */
  /* AND THE ROWS THEY LEAVE BEHIND COST NOTHING: with no card selected the card column draws
     nothing at all rather than an empty frame with a row gap under it. */
  await expect(page.locator('.browse-card')).toHaveCount(0)
  await expect(page.locator('.browse-under')).toHaveCount(0)
})

test('the address is drawn without a separator, and the server string survives on it', async ({
  page,
}) => {
  await open(page)

  /* THE OWNER'S COMPLAINT, ASSERTED AS AN ABSENCE (2026-08-29): "i didn't ever like the dot theme
     to separate". `PositionParts` used to paint the interpuncts muted so the parts would bind;
     the answer that shipped deletes them instead — the path is a stacked muted pair and the slot
     is a 44px figure beside it, so there is no seam left for a character to mark.

     An absence is the right shape for this case. A positive assertion about the new markup goes
     green on a treatment that also reintroduces the dots somewhere else in the block. */
  const position = page.locator('.card-locations-row.is-current .card-locations-label')
  await expect(position).toBeVisible()
  expect(await position.innerText()).not.toContain('·')
  await expect(page.locator('.position-joint')).toHaveCount(0)

  /* AND THE SERVER'S OWN STRING IS STILL THE ACCESSIBLE NAME. This is what makes splitting the
     label client-side legitimate rather than a quiet edit of what the store said: the visual
     rendering is a view, and `pipeline/join.py:Position.label` is still what is announced.
     `PositionParts`' own comment scopes the split to this screen for exactly this reason. */
  /* SCOPED TO THE ROW THE WALK IS STANDING ON. Several ranked labels are on this screen at once
     — one per copy in the list — and they all carry the same treatment; what this case is about
     is the address of the card the walk is standing on, which since D119 is one of those rows
     rather than a card above them. */
  const parts = page.locator('.card-locations-row.is-current .card-locations-label .position-parts')
  await expect(parts).toHaveAttribute('role', 'group')
  const label = await parts.getAttribute('aria-label')
  expect(label).toMatch(/^Box \d+, Section \d+, Card \d+$/)

  /* THE SLOT IS THE LAST PART AND IT IS THE ONE DRAWN AT SIZE. Anchored to the END of the
     address rather than to index 2, so a formula with a different number of parts still puts the
     finest thing said on the biggest step. */
  const num = page.locator('.card-locations-row.is-current .card-locations-label .position-num')
  await expect(num).toHaveText(/Card (\d+)$/.exec(String(label))?.[1] ?? '')
})

test('the address holds one line at both widths, including the longest label the store can emit', async ({
  page,
}) => {
  await open(page)

  /* THE DEFECT: 27 cells at Martian Mono's 0.70em advance is 453.6px in a 448.8px track, so the
     shipped label wrapped — and the comment that justified its size measured it against a 630px
     track a later layout change had already deleted. The worst label the formula can produce,
     `Box 100, Section 12, Card 543`, is 520.8px: 16% over at 1440 and 35% over at 1280.

     FORCED RATHER THAN FIXTURED, because no box in the store is numbered 100. What is being
     checked is the RENDERING's tolerance, not the data — so the label is set to the worst case
     and the block is measured for a second line.

     THE NUMBERS ABOVE ARE THE SITE THIS CASE WAS WRITTEN AGAINST, AND THAT SITE IS GONE (D119).
     They were a 44px figure in the location card's 448.8px track; the address is a row of the
     copies list now, at a 22px figure, so what is re-derived is the TOLERANCE and not the
     question. The block there is a two-line 11px path beside the figure — 33.9px, the same
     derivation `a narrow copies column shortens the bar, never the position label` states below
     and asserts at the same 36px — so a third line is what a wrap looks like here. The FORCED
     worst case is what this case still owns and that one does not. */

  /* WAIT FOR THE WEB FONT BEFORE MEASURING, AS HARDENING AND NOT AS A FIX FOR THE RECORDED
     FLAKE — that one was diagnosed properly on the branch that landed as `6c70d55`, by loading
     the rig and CAPTURING the error text: 9 of 80 loaded repeats failed in `open()` on a
     `toBeVisible()` timeout, none on an assertion, and the geometry case that remained was a
     case subtracting two layouts rather than a screen that moves. `docs/DEBTS.md` carries that
     reading; this comment does not restate it.

     WHY THIS AWAIT IS STILL WORTH ITS LINE. Every number this case asserts is an advance width
     — the comment above prices them against the mono face of the day, which was Martian Mono
     when the defect was measured and is JetBrains Mono now — and `app/src/fonts.css` declares
     that face with `font-display: swap`, which paints a fallback first and re-lays-out when the
     real one arrives. The face is served from this checkout since 2026-09-08 (D124) and the
     swap window is unchanged: what vendoring removed is the round trip, not the repaint. That same swap is what the other investigation names
     as the thing that moves the grid under a split measurement. Here the whole assertion is a
     font metric, so waiting for the face is a precondition of measuring the right typeface at
     all rather than a timing guess. It weakens nothing: the same numbers, on the font they were
     computed for.

     NOT PRESENTED AS MEASURED. This case has never been observed failing, so this is a latent
     correctness fix and not a reproduction. */
  await settleFonts(page)

  for (const width of [1440, 1280]) {
    await page.setViewportSize({ width, height: 900 })
    await page.locator('.card-locations-row.is-current .card-locations-label .position-parts').waitFor()

    const unwrapped = await page.locator('.card-locations-row.is-current .card-locations-label').evaluate((el) => {
      const shape = el.querySelector('.position-parts') as HTMLElement
      return shape.getBoundingClientRect().height <= 36
    })
    expect(unwrapped).toBe(true)

    /* The shape fits its track with the worst label in it. Measured on the SHAPE rather than on
       `.browse-position`, which is a full-width block and would always "fit". */
    const fits = await page.evaluate(() => {
      const label = document.querySelector('.card-locations-row.is-current .card-locations-label') as HTMLElement
      const path = label.querySelector('.position-path') as HTMLElement
      const slot = label.querySelector('.position-slot') as HTMLElement
      const track = document.querySelector('.card-locations-rows') as HTMLElement
      path.innerHTML = '<span>BOX <b>100</b></span><span>SECTION <b>12</b></span>'
      const numEl = slot.querySelector('.position-num') as HTMLElement
      numEl.textContent = '543'
      const used = path.getBoundingClientRect().width + slot.getBoundingClientRect().width + 24
      return used <= track.getBoundingClientRect().width
    })
    expect(fits).toBe(true)
  }
})

test("the box's census and its forecast are told apart, and the fill says which kind it is", async ({
  page,
}) => {
  await open(page)
  await openBoxOps(page)

  /* SAME COMPLAINT ONE COLUMN OVER, and the same absence. `cards 543 · sold 0 · fill 543 · next
     index 544` is 46 cells = 354.2px in a 299px track, so it wrapped — and it is not a digit
     count: box 1's shorter line wraps identically. It is four words and three interpuncts. */
  const meta = page.locator('.boxops-census')
  await expect(meta).toBeVisible()
  expect(await meta.innerText()).not.toContain('·')

  /* EVERY FIGURE CARRIES ITS OWN LABEL, which is what the interpunct-joined line could not do and
     is why it wrapped: the census is a definition list now, one label over one number. The names
     are the human ones the rebrand ruled for, and each still names exactly one store figure. */
  await expect(censusValue(page, 'Captured')).toHaveText('7')
  await expect(censusValue(page, 'Sold')).toHaveText('1')
  await expect(censusValue(page, 'Fill')).toHaveText('7')

  /* NEXT INDEX IS NOT A CENSUS FIGURE. `Captured`, `Sold` and `Fill` describe what is in the box;
     `Next index` is D10's high-water mark — what the allocator hands out next — and it is named
     apart from them rather than sitting in the row as a fourth count of cards. */
  await expect(censusValue(page, 'Next capture')).toHaveText('8')
  await expect(page.locator('.boxops-census-cell', { hasText: 'Next capture' })).toHaveCount(1)

  /* A box has no seal (`D-sealed-boxes-removed`), so no census figure can be a frozen one. */
  expect((await page.locator('.boxops-census-qual').allInnerTexts()).join(' ')).not.toMatch(/sealed/)

  /* And no figure wraps away from its own label at either width. */
  for (const width of [1440, 1280]) {
    await page.setViewportSize({ width, height: 900 })
    const cells = await page.locator('.boxops-census-cell').evaluateAll((nodes) =>
      nodes.map((node) => {
        const value = node.querySelector('dd') as HTMLElement
        return { h: value.getBoundingClientRect().height, line: Number.parseFloat(window.getComputedStyle(value).lineHeight) }
      }),
    )
    expect(cells.length).toBeGreaterThan(0)
    for (const cell of cells) expect(cell.h).toBeLessThan(cell.line * 1.6)
  }
})

test('a narrow copies column shortens the bar, never the position label', async ({ page }) => {
  await open(page)

  /* THE TRADE THIS PROTECTS, AND IT IS THE ONE D40 REFUSED FIRST. In the three-column layout the
     copies column gives this list ~586px, where the row was 144px: `8 + place 51 + gap 12 + bar
     65 + 8`. The obvious fix — lowering the 860px container threshold so the bar rejoins the row
     — does produce a 129px row, and it gets there by squeezing `.card-locations-place` to 231px,
     which WRAPS THE POSITION LABEL. `CardLocations.css` forbids that by name: the label is the
     string somebody carries to a shelf and it must not break.

     So the height comes out of the BAR's own dead space instead. This case asserts both halves,
     because either one alone can be satisfied by the wrong fix. */
  /* AT 1440, DELIBERATELY, AND THIS SUITE RUNS AT 1280 BY DEFAULT. The container is 528px at
     1280 and 612px at 1440, and the rejected fix's damage only exists in the second: with the
     threshold at 560 the narrow branch still applies at 528, so a case left at the default
     viewport passes against the very mutation it is written to catch. Observed — this case was
     kept only after it was seen to go red at 1440 and green at 1280 against that change. */
  await page.setViewportSize({ width: 1440, height: 900 })
  /* A ROW THAT DRAWS A BAR, which since D119 is the first one again — the copy the walk is
     standing on draws its lens in the list like every other row. The filter stays: a pooled or
     departed copy still carries no bar, and this case measures a row that has one. */
  const row = page.locator('.card-locations-row').filter({ has: page.locator('.position-bar') }).first()
  await expect(row).toBeVisible()
  await page.waitForTimeout(150)

  const geom = await row.evaluate((el) => {
    const bar = el.querySelector('.position-bar') as HTMLElement
    const caps = [...el.querySelectorAll('.position-bar-text')] as HTMLElement[]
    const boxTrack = el.querySelector('.position-bar-track') as HTMLElement
    const sect = el.querySelector('.position-bar-sectiontrack') as HTMLElement
    const parts = el.querySelector('.position-parts') as HTMLElement
    const pathEl = el.querySelector('.position-path') as HTMLElement
    const slotEl = el.querySelector('.position-slot') as HTMLElement
    return {
      barH: Math.round(bar.getBoundingClientRect().height),
      /* `getClientRects().length` WAS READ HERE AND IT IS BLIND. The node it was read off is a
         column-flex child, so it is blockified and returns exactly ONE rect however many lines
         of text it holds — measured on the shipped tree by forcing the place cell to 200/120/80px,
         which wraps the label to 2/3/4 real lines while the assertion read 1 and passed every
         time. The case only ever went red on its OTHER assertion, which hid this.

         The honest question is geometric, and it is the same shape as `capBesideTrack` two lines
         down: the parts block is the two-line path (33.9px) beside the figure, so anything past
         ~36px means a half of it wrapped. Height, not rect count. */
      partsH: parts === null ? 0 : Math.round(parts.getBoundingClientRect().height),
      pathSlotAligned:
        pathEl === null || slotEl === null
          ? false
          : Math.abs(pathEl.getBoundingClientRect().top - slotEl.getBoundingClientRect().top) < 40,
      capHeights: caps.map((c) => Math.round(c.getBoundingClientRect().height)),
      boxTrackH: Math.round(boxTrack.getBoundingClientRect().height),
      sectTrackH: sect === null ? null : Math.round(sect.getBoundingClientRect().height),
    }
  })

  /* THE LABEL DID NOT WRAP. This is the half the rejected fix broke, and it is asserted as a
     height rather than a rect count for the reason given inside the evaluate above. */
  expect(geom.partsH).toBeGreaterThan(0)
  expect(geom.partsH).toBeLessThanOrEqual(36)
  expect(geom.pathSlotAligned).toBe(true)

  /* THE CAPTIONS ARE ONE LINE EACH, which is the half of the old "beside its track" rule that
     was ever about this case. The rebuild stacks each caption over the track it describes — a
     deliberate change of the component's own shape, and one this file may not overrule — so what
     is asserted is what the height was ever protecting: neither caption wraps, and the bar stays
     inside the space two captions and two tracks need. A wrapped caption, or a third scale
     arriving unannounced, still fails it. */
  for (const h of geom.capHeights) expect(h).toBeLessThan(20)
  expect(geom.capHeights.length).toBe(2)
  expect(geom.barH).toBeLessThan(96)

  /* AND BOTH SCALES SURVIVE, WITH THE SECTION AS THE LARGER — REVERSED IN PLACE 2026-09-11 ON
     THE OWNER'S INSTRUCTION (D155). This assertion read
     `boxTrackH > sectTrackH`, which is the literal encoding of the priority the owner asked to
     flip: *"the interface/view of the box is nicer than section"*. The section is the ruler now
     — 26px, graduated, with a fill and a crossing pin — and the box is an 8px strip of chips
     beneath it. It is amended rather than deleted, per D118's own precedent, so a later session
     reads this as a reversal somebody made and not as drift.

     IT STILL REFUSES A FLATTENED BAR and now refuses a box-dominant one too, which is the claim
     that has to survive a re-tune: a "denser" row that collapsed the two into one would pass
     every height check above and lose the thing the bar is for.

     ITS OWN FIGURES WERE STALE WHEN IT WAS REVERSED. This comment said "the box track is 16px
     and the section track 8px"; the tree had shipped `--pb-track: 12px` since the rebrand, and
     docs/DESIGN.md carried the identical stale 16. Both were fixed in the same edit.

     AND THE HAZARD THE DESIGN IS SAVED FROM ONLY BY DISCIPLINE: `el.querySelector(
     '.position-bar-track')` above ALSO matches the section ruler, which carries both classes.
     Document order is the only thing that makes it return the box strip. The inversion is done
     entirely with CSS `order` — a later session that inverts it by reordering the JSX instead
     silently measures the wrong element and takes this assertion green over nothing. */
  /* The ruler stays the taller instrument. The strip under it grew from 8px to 14px to carry the
     section numbers before and after (the owner's ruling, amending D155), so the ratio is no
     longer two to one; what is kept is that the section is the instrument. */
  expect(geom.sectTrackH!).toBeGreaterThan(geom.boxTrackH)
  expect(geom.boxTrackH).toBeGreaterThan(0)
})

/* EVERY BAR IN THE LIST IS THE SAME HEIGHT, WHATEVER STATE ITS COPY IS IN (D118, and the repair
   D155 made to it). D118 kept the second scale mounted through a SALE so the
   row would not change height — and it covered exactly one of the three ways the depth can fail
   to resolve. `sectionDepthOf` also returns null on `place.section === null` (app/src/position.ts,
   the `section === null` guard) and on `box_total <= 0`, and the whole zoom block was gated on
   `depth !== null`, so a copy in either of those states drew a ~29px bar in a list of ~73px ones.

   MEASURED ON THE PRE-CHANGE TREE, ON #/gallery's OWN COPIES SPECIMEN: one bar at 73px and five
   at 29px. Two of the five are the states above; the other three are the `spans.length > 1` gate
   that this change also deletes. The design's own spec predicted two, which is why this is
   asserted as a SET of one rather than as a list of expected numbers.

   THE FIX IS STRUCTURAL, NOT ARITHMETIC: the zoom block mounts on the `sectionDepth` PROP and
   never on whether the depth resolved, so there is no branch left to take and a later fixture
   cannot reintroduce one. MUTATED TO CONFIRM THIS CASE CAN SEE ITS SUBJECT: re-gating the block
   on `depth !== null` takes it red with `bars disagreed on height: [73,73,29,73]`. */
test('every copy row draws the same bar height, located or not', async ({ page }) => {
  /* ONE SKU, FIVE COPIES, AND THREE DIFFERENT WAYS FOR THE SECOND SCALE TO HAVE NO ANSWER.
     2/1 and 2/3 are ordinary located copies of a DIVIDED box — the control. 2/4 is departed,
     which `sectionDepthOf` answers with its own branch. 6/1 is located in an UNDIVIDED box, so
     `spansOf` returns ONE span and the deleted `spans.length > 1` gate refused it. 7/1 is in a
     box the server could not size, so `sectionDepthOf` returns null on `box_total <= 0`. */
  const cards: Cards = {
    ...CARDS,
    '2/4': card({ index: 4, state: 'sold', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3 }),
    '6/1': card({ box: 6, boxTotal: 4, index: 1, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 4, boxName: 'Bulk, unsorted' }),
    '7/1': card({ box: 7, boxTotal: 0, index: 1, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 1, boxName: 'Just opened' }),
  }
  const boxes = {
    boxes: [
      { ...BOXES.boxes[0] },
      { ...BOXES.boxes[0], box: 6, name: 'Bulk, unsorted', cards: 4, on_hand: 4, fill: 4, next_index: 5, sold: 0, retired: 0, sections: [1], sections_detail: [{ section: 1, start: 1, end: 4, count: 4 }] },
      { ...BOXES.boxes[0], box: 7, name: 'Just opened', cards: 1, on_hand: 1, fill: 1, next_index: 2, sold: 0, retired: 0, sections: [], sections_detail: [] },
    ],
  }

  await open(page, boxes, { cards, search: (query) => searchAnswer(query, cards) })
  await page.setViewportSize({ width: 1440, height: 900 })
  await expandAll(page)
  await page.locator('.browse-row', { hasText: 'Thievul' }).first().click()
  await expect(page.locator('.card-locations-owner .position-bar').first()).toBeVisible()
  /* The bar's own transitions are 320ms and one of them is on `width`; measuring inside them
     reads a bar mid-ease. */
  await page.waitForTimeout(400)

  const hs = await page
    .locator('.card-locations-owner .position-bar')
    .evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().height)))
  /* The fixture really did produce every state — a count of one would satisfy the set below
     without proving anything, which is the way this case could pass while blind. */
  expect(hs.length).toBe(5)
  expect(new Set(hs).size, `bars disagreed on height: ${hs}`).toBe(1)
})

test('a wider copies column never makes its rows taller', async ({ page }) => {
  await open(page)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.locator('.card-locations-row').first().waitFor()

  /* THE DEFECT THIS CLOSES, AND IT WAS DORMANT RATHER THAN INVISIBLE. `CardLocations.css` switches
     the position bar into the row at a container threshold. That threshold was 860px, chosen when
     the bar took four stacked full-width lines and the narrow row was 144px. Folding each caption
     beside its track took the narrow row to 114px — and left the WIDE branch producing 126px at
     the exact width it engaged. Measured: 820 -> 114, 860 -> 126, 880 -> 85, 900 -> 82. Crossing
     into the "better" branch made the row twelve pixels taller.

     IT COULD NOT BE SEEN. The copies container is 612px at 1440 and 528px at 1280, so `min-width`
     needs roughly a 1980px viewport to fire at all — nothing in this suite or on the owner's
     display would ever have rendered it. A threshold that is wrong and dormant is worse than one
     that is wrong and visible, because nothing fails while it waits.

     SO THE ASSERTION IS THE PROPERTY, NOT THE NUMBER. Whatever the threshold is, a container that
     grows must never make a row taller — that is what "this branch is better" means, and it is
     the claim a future re-tune has to keep. Pinning 880 instead would go green on any later change
     that moves the cliff somewhere else. */
  const heights = await page.evaluate(() => {
    const host = document.querySelector('.browse-under') as HTMLElement
    const previous = host.style.cssText
    const out: { width: number; row: number }[] = []
    for (const width of [560, 640, 760, 820, 860, 870, 880, 900, 940, 1024]) {
      host.style.width = `${width}px`
      host.getBoundingClientRect()
      const row = document.querySelector('.card-locations-row') as HTMLElement
      out.push({ width, row: Math.round(row.getBoundingClientRect().height) })
    }
    host.style.cssText = previous
    return out
  })

  const taller = heights.filter((point, at) => at > 0 && point.row > heights[at - 1]!.row)
  expect(taller, `row grew as the container widened: ${JSON.stringify(taller)}`).toEqual([])

  /* And the wide branch really is better by the end of the sweep, so this cannot be satisfied by
     deleting the threshold and never switching at all. */
  expect(heights[heights.length - 1]!.row).toBeLessThan(heights[0]!.row)
})

test('the box fill is qualified once, on the identity line', async ({ page }) => {
  await open(page)
  await openBoxOps(page)

  /* D41 put D20's `so far` / `sealed` on `.boxops-meta`'s fill, and `BoxIdentity` sixteen pixels
     above already carried it — so for one commit `133 so far` rendered twice on one screen. D20's
     rule is that the number is unambiguous on screen, not that it is annotated at every site.

     THE FIELD STAYS AND ONLY THE QUALIFIER GOES, which is the half worth asserting: `BoxOps.tsx`
     promises these key names grep to `inventory.json`, so a fix that dropped `fill` outright would
     have broken a different promise to keep this one. */
  await expect(page.locator('.boxops-census-qual')).toHaveCount(0)
  await expect(censusValue(page, 'Fill')).toHaveText('7')

  /* A box has no lid (`D-sealed-boxes-removed`), so the sheet's head names no lid state at all:
     every fill is a fill so far. */
  const head = await page.locator('.boxops-sheet .inv-sheet-head').innerText()
  expect(head.toLowerCase()).not.toMatch(/\bopen\b|\bsealed\b/)
})

test('the walk keeps a floor when the box editors open beneath it', async ({ page }) => {
  await open(page)
  await openBoxOps(page)

  /* THE BUG THIS IS THE RECEIPT FOR: `.browse-map` is sticky and capped at the viewport, so
     anything past the cap renders below the fold and the page scroll cannot bring it back — the
     sticky element does not move. Putting the box's operations in this column made that real, and
     four box-claim cases above failed with "element is outside of the viewport" the moment the
     claims editor opened. The column scrolls itself now, and the walk keeps a floor so it cannot
     be squeezed to nothing by an editor below it. */
  await page.getByRole('button', { name: /^Set claims/ }).click()

  const apply = page.getByRole('button', { name: /^Apply to/ })
  await expect(apply).toBeVisible()

  /* THE ESCAPE HATCH EXISTS AND WORKS, which is the property — not that the button happens to
     land above the fold on this viewport. The editor is a sheet over the screen now rather than a
     slab at the foot of the sticky column, so the trap this case is the receipt for is gone by
     construction; what still has to be true is what it always asserted, that the control at the
     bottom of the editor can be reached and pressed. */
  await apply.scrollIntoViewIfNeeded()
  await expect(apply).toBeInViewport()

  /* And the walk was not squeezed to nothing to make room for the editor. */
  const list = await page.locator('.browse-list').boundingBox()
  if (list === null) throw new Error('the walk did not render')
  expect(list.height).toBeGreaterThanOrEqual(90)
})

// ------------------------------- what the panel can overwrite, it now shows (consult, 2026-08-25)

test('the two claims the correction button can overwrite are both on the panel', async ({
  page,
}) => {
  await open(page)
  await expandAll(page)

  /* THE DEFECT THIS CLOSES. `CardOps` -> `ClaimEditor` writes FIVE claims and the facts list drew
     three, so `Correct claims` — sitting directly under these rows — replaced two values that
     appeared nowhere on screen. Worse than silent: the editor opens with those fields EMPTY and
     reads armed-and-empty as a clear, so the correction was a blind overwrite. `rarity_claim` is
     set on 543 of 543 real records, so this was live rather than latent. */
  await page.locator('.browse-row', { hasText: 'Not identified yet' }).first().click()

  /* `Common, Uncommon` and never `common,uncommon` — the array-coercion guard, identical in kind
     to the finish case above, and the reason both rows go through one renderer. */
  const rarity = page.locator('.browse-fact', { hasText: 'Rarity' }).locator('dd')
  await expect(rarity).toHaveText('Common, Uncommon')

  const note = page.locator('.browse-fact', { hasText: 'Note' }).locator('dd')
  await expect(note).toHaveText('japanese, no english print')

  /* The fallbacks matter as much as the values: a row that vanished when empty would leave "this
     card has no note" and "this screen does not show notes" indistinguishable, which is the bug. */
  await page.locator('.browse-row', { hasText: 'Thievul' }).first().click()
  await expect(page.locator('.browse-fact', { hasText: 'Rarity' }).locator('dd')).toHaveText(
    'none recorded',
  )
  await expect(page.locator('.browse-fact', { hasText: 'Note' }).locator('dd')).toHaveText('none')
})

test('the card names the run that read it, and the model\'s own hedge', async ({ page }) => {
  await open(page)

  /* `run` joins this panel to the Runs panel one column right, which lists run directories and
     cannot say which cards each one touched. `confidence` is the only place a RESOLVED card's
     hedge is readable — `ReviewQueue.tsx` draws it only for a card that was queued. Both are
     asserted as their fallbacks here because the fixture leaves them null, which is the half
     that proves the rows are unconditional. */
  await expect(page.locator('.browse-fact', { hasText: 'Run' }).locator('dd')).toHaveText(
    'not identified yet',
  )
  await expect(page.locator('.browse-fact', { hasText: 'Confidence' }).locator('dd')).toHaveText(
    'none recorded',
  )
})

test('the card carries what its run said the market was, and how old that reading is', async ({
  page,
}) => {
  /* THE OWNER'S ASK, 2026-08-29: "if a join has happened on that set, can I get the TCG Market
     Price as part of the data summary on the top right of the card (with a note of how
     stale/fresh that data is?)".

     THE PRICE IS NOT ON THE RECORD AND CANNOT BE. D8 puts every figure in this product in the
     TCGplayer export and `store/master.py` holds no field shaped like money, so the row is a
     join: card -> `run` -> that run's `pricing.json` -> the SKU whose positions hold this card.

     BY POSITION, NEVER BY `card.sku`, and this fixture is built to prove it. `2/2` carries
     `sku: null` on its record — `emit` writes that field only for SKUs that reached an import
     file — and it is still priced here, because the join's table names the position. A lookup
     keyed on the card's own SKU would draw nothing for it and would be silently wrong for every
     sub-threshold and withheld card in the store. */
  await open(page, BOXES, PRICED_STORE)

  const market = page.locator('.browse-fact', { hasText: 'Market' }).locator('dd')
  /* THE FIGURE AND ITS AGE, IN THE SAME ROW — drawn as the listed row above it draws its own
     now (one `ReadingAge`, one weight), so the compact `· read 2d` is a spelt-out age instead.
     Both halves are still asserted, and separately: the price, and that the age names the
     reading rather than the market. */
  await expect(market.locator('.bn-tnum')).toHaveText('$5.47')
  await expect(market).toContainText('read 2 days ago')

  /* THE AGE IS NEVER OPTIONAL, which is the half that makes the row honest. `join` is free,
     re-runnable and routinely pointed at a refreshed export, so two cards on one shelf can carry
     prices read a week apart — a bare `$5.47` claims a currency the file cannot support.

     AND `read` SURVIVES THE COMPACTION, which is the other half. `2d` alone could be read as two
     days on the market; `read 2d` says the age is the JOIN's. The word is asserted separately
     from the string above so that shortening the duration again cannot quietly take the verb
     with it. */
  expect(await market.innerText()).toContain('read')

  /* THE SECOND COPY OF THE SAME SKU, reached through the walk and priced identically — D7's
     fungible copies, and the assertion that the table is indexed by every position rather than
     by the first. `2/2` is also the card with no SKU on its record. */
  await expandAll(page)
  await page.locator('.browse-row').nth(1).click()
  await expect(page.locator('.browse-fact', { hasText: 'Number' })).toBeVisible()
  const second = page.locator('.browse-fact', { hasText: 'Market' }).locator('dd')
  await expect(second.locator('.bn-tnum')).toHaveText('$5.47')
  await expect(second).toContainText('read 2 days ago')

  /* A BLANK MARKET CELL IS AN UNKNOWN PRICE AND SAYS SO — D9, in its own words, "a missing price
     is an unknown price, not a low one". The failure this forbids is rendering it as `$0.00` or
     as an empty row, which is what hands a chase card away at the floor. `no market data`
     UNDERSCORE AND ALL, because it is `pipeline/routing.py`'s own `NO_MARKET_DATA` and
     DESIGN.md's owner-screen rule is the machine string. Spelled `no market data` it would be
     neither the constant nor a human label — the second vocabulary D22 refuses — and would grep
     to nothing against the `no_market_data` block `GET .../pricing` serves, which is where a
     card in this state is actually priced. */
  await page.locator('.browse-row').nth(3).click()
  await expect(page.locator('.browse-fact', { hasText: 'Market' }).locator('dd')).toHaveText(
    'no_market_data',
  )

  /* A POSITION THE TABLE DOES NOT HOLD IS A CARD THE JOIN MATCHED NO ROW FOR, which is a
     different fact again from a blank cell and gets a different sentence. */
  await page.locator('.browse-row').nth(4).click()
  await expect(page.locator('.browse-fact', { hasText: 'Market' }).locator('dd')).toHaveText(
    'no row in this run',
  )
})

/** How many lines the Market row's value actually draws, measured rather than inferred from the
 *  string. A wrapped value is the defect this guards, and it is invisible from the text. */
async function marketLines(page: Page): Promise<number> {
  return page.evaluate(() => {
    const dd = [...document.querySelectorAll('.browse-fact')]
      .find((row) => row.querySelector('dt')?.textContent === 'Market')
      ?.querySelector('dd') as HTMLElement
    const line = parseFloat(getComputedStyle(dd).lineHeight)
    return Math.round(dd.getBoundingClientRect().height / line)
  })
}

test('the market row draws on one line at the width the owner works at', async ({ page }) => {
  /* THE OWNER'S REPORT, 2026-08-30, with a screenshot of a `Market` row wrapped onto two lines
     between `Run` and `Note`.

     IT IS A WIDTH GUARD AND NOT A COPY GUARD, which is the whole reason it measures instead of
     pinning a string. The four cases above already pin what the row SAYS; a sentence written
     past the track does not fail there, it silently costs the row a second line and pushes the
     panel down. What is asserted here is the rule — the value fits — so a future wording is
     free to change and is not free to overflow.

     1440x900 EXPLICITLY, AND THE DEFAULT VIEWPORT CANNOT SEE THIS. `.browse-facts` is
     `column-width: 260px`: at the owner's 1440 the list is 578px and takes TWO columns of 277px,
     leaving a 181px value track, and at this suite's default 1280 it is 506px and takes ONE
     column with a 410px track. Every string in this row fits at 1280. So the whole of the
     defect lives at a width nothing in this file had ever rendered — which is why it shipped,
     and why pinning this viewport is the case rather than an incidental setting.

     EVERY REACHABLE STATE, because the wrap is a property of the longest one rather than of the
     priced one. `no row matched by this run` was 236.6px against the 181px track — worse than
     the price it sits beside — and it would have gone on wrapping had only the priced form been
     fixed. */
  await page.setViewportSize({ width: 1440, height: 900 })
  await open(page, BOXES, PRICED_STORE)
  await expect(page.locator('.browse-fact', { hasText: 'Market' }).locator('dd')).toBeVisible()
  expect(await marketLines(page)).toBe(1)

  await expandAll(page)
  for (const row of [3, 4]) {
    await page.locator('.browse-row').nth(row).click()
    await expect(page.locator('.browse-fact', { hasText: 'Number' })).toBeVisible()
    expect(await marketLines(page)).toBe(1)
  }
})

test('Reload re-reads the price, because a join is what a reload is pressed after', async ({
  page,
}) => {
  /* A LIVE BUG, FOUND BY HAND AGAINST THE REAL STORE AND KEPT AS A CASE. The cache is cleared
     on the reload counter and the READ was keyed on the run NAME alone — which does not change
     when a box is re-read, so the cleared entry was never re-fetched and the row sat on
     `reading…` permanently. A clear and its re-read are one gesture and have to be triggered by
     the same thing.

     IT IS THE PRESS THAT MATTERS MOST HERE. Reload beside the walk is pressed precisely after
     something downstream has changed, and a join is the thing that rewrites a price — so the
     one moment this row is guaranteed to be stale is the one moment the operator is asking for
     it not to be. */
  let at = PRICED_AT
  await open(page, BOXES, PRICED_STORE, () => ({ ...PRICING, written_at: at }))

  const market = page.locator('.browse-fact', { hasText: 'Market' }).locator('dd')
  /* THE FIGURE AND ITS AGE, IN THE SAME ROW — drawn as the listed row above it draws its own
     now (one `ReadingAge`, one weight), so the compact `· read 2d` is a spelt-out age instead.
     Both halves are still asserted, and separately: the price, and that the age names the
     reading rather than the market. */
  await expect(market.locator('.bn-tnum')).toHaveText('$5.47')
  await expect(market).toContainText('read 2 days ago')

  /* THE PRESS MOVED AND THE GESTURE DID NOT. The owner ruled the header's manual Reload away;
     the re-read lives with the card's own operations now, which is where a person who has just
     changed something downstream looks for it. What is asserted is what it always was: one
     gesture clears the cache AND re-fetches, so the row cannot be left on a stale reading. */
  at = Math.floor((Date.now() - 9 * 86400000) / 1000)
  await openCardOps(page)
  await page.getByRole('menuitem', { name: 'Re-read the inventory' }).click()
  await expect(market).toContainText('read 9 days ago')
  await expect(market.locator('.bn-tnum')).toHaveText('$5.47')
})

test('the market row is drawn even for a card no run has read', async ({
  page,
}) => {
  /* NEVER CONDITIONAL, the rule the `Rarity` and `Note` rows above it already follow: a row that
     disappears leaves "this card has no price" and "this screen does not show prices"
     indistinguishable, which is the defect those two were added to fix. So every way there is no
     figure gets a sentence instead of an absence. */
  await open(page)
  await expect(page.locator('.browse-fact', { hasText: 'Market' }).locator('dd')).toHaveText(
    'not joined yet',
  )
})

test('a run with no pricing table names the remedy rather than reading as an unpriced card', async ({
  page,
}) => {
  /* THE ONE REFUSAL THE PANEL TELLS APART FROM THE REST. `pricing_not_written` means the run
     predates `pricing.json` or was never joined, and its remedy is a join — where a dead server
     or a run directory that has gone sends you somewhere else entirely. Naming the remedy on the
     row is what stops it reading as a card nobody has priced.

     ITS OWN TEST RATHER THAN A SECOND `open` IN THE ONE ABOVE. Two mounts in one case re-register
     every handler and re-`goto` a URL the page is already at, which is a same-document fragment
     navigation: the screen does not remount and the assertion measures the first fixture. That
     was observed, and it read as the feature being broken. */
  const stale: Cards = Object.fromEntries(
    Object.entries(CARDS).map(([key, held]) => [key, { ...held, run: '2026-08-22-box1-03' }]),
  )
  await page.setViewportSize({ width: 1440, height: 900 })
  await open(page, BOXES, { cards: stale, search: (query) => searchAnswer(query, stale) })
  await expect(page.locator('.browse-fact', { hasText: 'Market' }).locator('dd')).toHaveText(
    'join this run',
  )

  /* THE REMEDY WITHOUT THE STATE, and the width is why: `no pricing table — join this run` is
     291.2px in a 181px track and drew as two lines. Measured here beside the string rather than
     only in the case above, because this is the state that lost half its sentence to the track
     and it is reached from a fixture that case cannot mount. */
  expect(await marketLines(page)).toBe(1)
})

test('a card with an open question in the queue says so, and says whether it can be answered', async ({
  page,
}) => {
  /* THE FACT THAT TIES THE SCREEN'S THREE JOBS TOGETHER: the walk finds the card, this says
     whether anything is waiting on it, and the run panel is what would answer it. Before this a
     card sitting in `review.json` with zero candidates rendered `State: identified` and nothing
     else — and `state` there is not merely silent, it is MISLEADING, because it describes how far
     capture and identify got while the open question was raised by the JOIN. */
  await open(page)

  const block = page.locator('.browse-queued')
  await expect(block).toBeVisible()
  /* The notice's own title and body — the kit's slots, which is where this screen's warnings are
     drawn now. What is said is unchanged, and the machine string still rides its own slot. */
  await expect(block).toContainText('Waiting in the review queue')
  /* The reason's HUMAN label, from the shared map — not the raw code, which is the line below.
     D196 (UX-208): the label no longer names the export, the pipeline-internal noun for
     TCGplayer's own catalog. */
  await expect(block).toContainText('No listing on TCGplayer')

  /* ZERO CANDIDATES IS LOAD-BEARING, not decoration: it is the difference between "go and answer
     it" and "it cannot be answered as it stands", and it is what points at the re-shoot icon
     already on this panel. `POST /review/<box>/<index>/answer` refuses such an entry outright. */
  await expect(block).toContainText('cannot be answered')
  await expect(block.locator('.bn-notice-code')).toHaveText(
    'no_catalog_row, review, 0 candidates',
  )
})


// ------------------------------------------------ D67: the number a screen draws, drawn once

/* A GAME THAT PRINTS NO DENOMINATOR, WHICH IS A QUARTER OF THE STORE. Riftbound puts one
 * identifier on the card and the store writes `""` into `printed_total` for it — 174 of the
 * owner's 676 numbered records — where Pokemon writes both halves. The two rows below are the
 * same fixture twice, differing in that one field and in whether the server sent its own
 * composition, because those are the two things that were wrong at once. */
const NO_DENOMINATOR: Cards = {
  ...CARDS,
  '2/1': card({ index: 1, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3, number: '198', printedTotal: '' }),
  /* THE OLDER-SERVER ROW: no `number_display` at all, which is what every decoration in
     `types.ts` is typed for. `cardNumber.ts` composes the pair itself here, and it is the
     composition — not the server field — that has to fold the blank. */
  '2/3': card({ index: 3, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3, number: '198', printedTotal: '', noDisplay: true }),
}

test('a game with no printed total draws no trailing separator', async ({ page }) => {
  await open(page, BOXES, {
    cards: NO_DENOMINATOR,
    search: (query) => searchAnswer(query, NO_DENOMINATOR),
  })
  await expandAll(page)

  const number = page.locator('.browse-fact', { hasText: 'Number' }).locator('dd')

  /* THE DEFECT, EXACTLY. `BoxBrowse.tsx` tested `printed_total === null` one line below testing
   * `number` for null OR blank, so an empty string took the else branch and drew `198/` — a
   * separator with nothing behind it, on every Riftbound card in the store. */
  await page.locator('.browse-row').nth(0).click()
  await expect(number).toHaveText('198')

  /* AND THE SAME WITHOUT THE SERVER'S FIELD, because the two repairs are independent: the blank
   * is a client bug and `number_display` is a server field, and a screen held against a server
   * that predates the field still must not draw the separator. */
  await page.locator('.browse-row').nth(2).click()
  await expect(number).toHaveText('198')
})

/* THE GROUP'S NUMBER ROW, WHICH WENT SILENT ON THE CARDS THAT NEEDED IT MOST. `_agreed` returns
 * null the moment two copies of a SKU spell their number differently, correctly and by design —
 * and D55's set-code repair fires on the JOIN, so nothing ever applied it to a screen. Five
 * copies of Moonfall storing `198/219`, `UNL • 198/219` and `UNL - 198/219` are not disagreeing
 * about the card; the group is. Measured on the owner's store: 11 of 102 groups draw no number,
 * 7 of them recover under the fold, and the four that do not are real disagreements. */
const DISAGREEING = (query: string) => {
  const answer = searchAnswer(query, NO_DENOMINATOR) as {
    groups: Record<string, unknown>[]
  }
  for (const group of answer.groups) {
    group.number = null
    group.printed_total = null
    group.number_display = '198/219'
  }
  return answer
}

test('a group whose copies spell one number three ways still draws it', async ({ page }) => {
  await open(page, BOXES, { cards: NO_DENOMINATOR, search: DISAGREEING })
  await expandAll(page)
  await page.locator('.browse-row').nth(0).click()

  /* The raw pair is null on the wire and the row is drawn anyway, off the field the server
     agreed on after folding. A build that composed from `number`/`printed_total` here draws
     nothing at all, which is what the owner saw: one card, three strings, and the group between
     them silent. */
  await expect(page.locator('.card-locations-meta')).toContainText('198/219')
})

/* THE COPIES LIST, WHICH IS WHERE THIS WAS REPORTED FROM — *"I'm seeing two box 1's"*. There is
 * one box 1; there were two sold copies of one card in it, both drawing `Box 1 · departed` with
 * nothing beside them to tell them apart. The fixture's box 2 holds the same shape, one sold and
 * one retired, and the pair is the assertion for the same reason the walk's is: what a label must
 * guarantee is that no two records share one. */
test('two departed copies of one card draw two different rows', async ({ page }) => {
  const shared: Cards = {
    ...CARDS,
    '2/4': card({ index: 4, state: 'sold', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3 }),
    '2/5': card({ index: 5, state: 'retired', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3 }),
  }
  await open(page, BOXES, { cards: shared, search: (query) => searchAnswer(query, shared) })
  await expandAll(page)
  await page.locator('.browse-row').nth(0).click()

  /* Marked, not worded (D259): the row's own state class finds them. */
  const gone = page.locator('.card-locations-row.is-gone')
  await expect(gone).toHaveCount(2)
  /* RANKED, NOT PLAIN (D71), and the store key is the value of the thing that explains it. This
     read `.position-storekey` — the orphan sub-line under a raw string — and the raw string was
     the pre-D41 rendering, drawn here at 28px as the loudest thing in a list whose live rows are
     ranked. The pair is still what separates the two records, which is all D68 asked for. */
  await expect(gone.nth(0).locator('.position-path')).toHaveText('BOX ME01 commonsSECTION 1')
  await expect(gone.locator('.position-num')).toHaveText(['4', '5'])

  /* AND THE COLUMN HOLDS ACROSS A ROW THAT HAS NO FIGURE, which is the assertion the reserve in
     `PositionLabel.css` promises and cannot make about itself. `lead='slot'` exists so every
     row's path starts at one x; the shipped reserve held the DIGITS only, so these two rows —
     which have a key-less void where `CARD 1` sits — hung to the left of every live one by the
     width of the key they do not draw. That reservation is `--pos-slot-key`, declared by the
     list in `CardLocations.css` and spent as padding here, and it is 37.594px — `CARD` at
     33.594 plus the 4px slot gap, MEASURED on the real screen rather than derived. This said
     38.3px until 2026-09-05 and no two sites in the tree agreed on it. It is read
     as a coordinate rather than as a width because a width can be right while the row it is on
     is not: what matters is that a person's eye finds one edge down the list. */
  const livePath = await page.locator('.card-locations-row .position-path').first().boundingBox()
  const gonePath = await gone.nth(0).locator('.position-path').boundingBox()
  expect(gonePath?.x).toBeCloseTo(livePath?.x ?? -1, 0)

  /* AND NO BAR UNDER EITHER (D68). This list drew one — an empty track captioned `where this
   * sits in the box is not known yet`, which reads as the server having failed rather than as
   * the card having been sold, and which disagrees with the walk about the same card: that
   * screen has omitted the bar for a departed row since D58. Where those copies sat is known
   * exactly; it is the neighbours line still drawn above this. */
  /* Both rows keep a lens, both with the mark gone (D118, amending D68): a departed ROW that
     lost its bar lost a line's height at the moment a sale landed, so every row under the one
     just sold moved under the pointer that had pressed it. */
  await expect(gone.locator('.position-bar[data-gone]')).toHaveCount(2)
  await expect(gone.locator('.position-bar-marker[data-gone]')).toHaveCount(4)

  /* The live copies keep theirs UNMARKED, so the case cannot pass by every bar reading departed. */
  await expect(page.locator('.card-locations-row .position-bar').first()).toBeVisible()
  await expect(page.locator('.card-locations-row .position-bar:not([data-gone])').first()).toBeVisible()
})

/** A box past 999 cards. The owner's largest holds 723 and he says a thousand is imminent, so
 *  this is not a synthetic worst case — it is the box that is coming, at the size he named. The
 *  section is declared to 1400 because an undeclared box is ONE section (D10, amended) and the
 *  walk has to file index 1345 somewhere real. */
const BIG_BOX = {
  boxes: [
    {
      ...BOXES.boxes[0],
      fill: 1345,
      next_index: 1346,
      cards: 3,
      on_hand: 2,
      sold: 1,
      retired: 0,
      sections: [1],
      sections_detail: [{ section: 1, start: 1, end: 1400, count: 2 }],
    },
  ],
}

/** Three copies of one SKU in that box: a three-digit live row, a FOUR-digit live row, and a
 *  departed one, which is the row that draws no figure and therefore reserves the key rather
 *  than drawing it. */
const BIG_CARDS: Cards = {
  ...CARDS,
  '2/998': card({ index: 998, at: 998, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 1400, boxTotal: 1400 }),
  '2/1345': card({ index: 1345, at: 1345, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 1400, boxTotal: 1400 }),
  '2/1200': card({ index: 1200, at: 1200, state: 'sold', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 1400, boxTotal: 1400 }),
}

/* THE SLOT COLUMN HOLDS A FOUR-DIGIT CARD NUMBER, which nothing in this file had ever drawn.
 *
 * MEASURE THE INK, NOT THE BOX — and this is the whole reason the case is written the way it is.
 * `.position-num` is `flex: 0 1 auto` inside the slot, so when its text outgrows the space it is
 * SHRUNK to fit and its glyphs paint outside it (`overflow` is visible). Measured on the real
 * screen against the shipped 84px column: the element's own `getBoundingClientRect()` is byte for
 * byte identical at three, four AND five digits, while the ink runs 6.4px past the slot at four
 * and 19.6px past at five. An assertion built on the element box — which is what this case was
 * first drafted as — is GREEN against the defect it is written for. So the two things read here
 * are `scrollWidth` against `clientWidth`, and a Range over the text node.
 *
 * THE GAP IS THE ASSERTION, NOT THE COLLISION. At four digits the ink does not yet reach the path:
 * it eats `--pos-gap`, 18.8px of clearance down to 5.6px. Overlap only starts at five digits. A
 * case asserting "the figure does not cross the path" would therefore pass at four and this whole
 * class would ship again one digit later.
 *
 * FIXTURE AND NOT A DOM POKE, unlike the hero label's case above. `--pos-slot-digits` is computed
 * in `CardLocations.tsx` from `place.card`, so a `textContent` written after render would leave the
 * reservation at three and this case would go red against a CORRECT implementation. The four digits
 * have to arrive the way the server sends them. */
test('the slot column holds a four-digit card number, and the gap beside it survives', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await open(page, BIG_BOX, { cards: BIG_CARDS, search: (query) => searchAnswer(query, BIG_CARDS) })
  await settleFonts(page)
  await expandAll(page)
  await page.locator('.browse-row').nth(0).click()
  await expect(page.locator('.card-locations-rows .position-parts').first()).toBeVisible()

  const read = () =>
    page.evaluate(() => {
      const ink = (el: Element) => {
        const range = document.createRange()
        range.selectNodeContents(el)
        return range.getBoundingClientRect()
      }
      return [...document.querySelectorAll('.card-locations-rows .position-parts')].map((parts) => {
        const slot = parts.querySelector('.position-slot') as HTMLElement
        const path = parts.querySelector('.position-path') as HTMLElement
        const num = parts.querySelector('.position-num')
        return {
          figure: num?.textContent ?? null,
          overflow: slot.scrollWidth - slot.clientWidth,
          /* NULL ON A ROW WITH NO INK, and that is the whole of this field's contract. A
             departed row's figure is `.position-void`, whose em-dash comes from a `::before`,
             so the element has NO CHILD NODES and `selectNodeContents` over it returns an
             all-zero rect — measured: `width` 0 and `right` 0, which made `path.left - 0` read
             1003.25 against a floor of 11 and passed by a factor of ninety-one. The row was in
             the loop and testing nothing. What holds that row is `overflow` and `pathX` below,
             which do not need ink. */
          inkToPath:
            num === null
              ? null
              : +(path.getBoundingClientRect().left - ink(num).right).toFixed(2),
          pathX: +path.getBoundingClientRect().x.toFixed(2),
          height: +parts.getBoundingClientRect().height.toFixed(2),
        }
      })
    })

  const rows = await read()

  /* The fixture reached the screen. Without this every assertion below is vacuously true of a
     list that happens to hold no long number. */
  expect(rows.map((row) => row.figure)).toContain('1345')

  /* NOTHING OVERFLOWS ITS SLOT. 6px on the shipped column, at this exact row. */
  for (const row of rows) expect(row.overflow).toBeLessThanOrEqual(0)

  /* AND THE GAP SURVIVES, ON EVERY ROW THAT HAS INK TO MEASURE. 5.6px on the shipped column
     against 18.8px for a three-digit row; `--pos-gap` is 12px, and the floor is set below it
     because the column reserves in `ch`, which over-reserves against real digits by design.

     THE FIGURE-LESS ROW IS EXCLUDED RATHER THAN SILENTLY PASSING, which is the correction. It
     used to be in this loop scoring 1003.25 — an all-zero Range rect subtracted from the path's
     left edge — so it cleared a floor of 11 ninety-one times over while measuring nothing. It is
     held by `overflow` and by `pathX` instead, neither of which needs a glyph. The count below
     is what stops the exclusion quietly emptying the loop. */
  const inked = rows.filter((row) => row.inkToPath !== null)
  expect(inked.length).toBeGreaterThanOrEqual(2)
  for (const row of inked) expect(row.inkToPath).toBeGreaterThanOrEqual(11)

  /* THE COLUMN IS STILL ONE COLUMN, across a four-digit row and a row with no figure at all.
     This is `two departed copies` one digit-count further out: that case proves the reserve
     holds at three digits, and only this one proves it holds when the count MOVES. */
  const xs = rows.map((row) => row.pathX)
  for (const x of xs) expect(x).toBeCloseTo(xs[0] ?? -1, 0)

  /* AND NOTHING WRAPPED. The widened column takes 12.9px out of the path's track; this carries
     `a narrow copies column shortens the bar, never the position label` into the widened case. */
  for (const row of rows) expect(row.height).toBeLessThanOrEqual(36)
})

/* ------------------------------------------------------------ the hash's box, on a slow read
 *
 * `#/inventory?box=<n>` IS HONOURED FOR A BOX WITH NO CARDS IN IT, AND UNTIL 2026-09-05 IT WAS
 * NOT. `BoxBrowse`'s shelf list is built from the ROWS first and the box registry second, and
 * the two arrive on separate reads. A box with no located rows is therefore absent from the
 * first shelf list the effect sees — and that effect consumed and cleared the ref holding the
 * hash's box right there, so when the registry landed a tick later there was nothing left to
 * honour and the walk stayed on the first shelf.
 *
 * WHY THAT IS NOT AN EDGE CASE. Every box of code cards has no located rows, because D24 pools
 * them, so `#/codes`'s "Fix on Inventory" — which aims at the box holding the unclaimed codes
 * and is one of D101's two doors onto the `product` claim — could never arrive at the box it
 * named. It landed on box 1, whose claim editor draws no Product row at all because box 1 is
 * Pokemon, so the door led to a room with nothing in it.
 *
 * THE DELAY IS THE TEST AND NOT A SLEEP AROUND IT. Both reads are in flight at once in a
 * browser, so their order is a race and a test that did not force one would pass or fail on
 * timing. Holding `/boxes` back reproduces the ordering the defect needs, every time.
 *
 * OBSERVED RED BEFORE IT WAS KEPT. Mutation: restore the old body — clear `wanted.current`
 * unconditionally and put the `prev` branch back ahead of the asked-for one. This case then
 * reports box 2, the first shelf, in place of 6.
 */
test('a box with no cards is still the box the hash asked for', async ({ page }) => {
  /* Box 6 is in the registry and in no row of the store: `fill: 0`, which is what an empty box
     and a box of pooled code cards look like identically from this screen. */
  const withEmpty = {
    boxes: [
      ...BOXES.boxes,
      {
        box: 6,
        name: 'ETB codes',
        sections: [],
        state: 'open',
        capacity: null,
        fill: 0,
        next_index: 1,
        cards: 0,
        on_hand: 0,
        sold: 0,
        retired: 0,
        moved: 0,
        listed: 0,
        sections_detail: [],
      },
    ],
  }

  await open(page, withEmpty, STORE, () => PRICING, SALE, {
    route: '/#/inventory?box=6',
    boxesDelayMs: 300,
    /* The box strip, not a section fold: box 6 has no sections and never will draw one. */
    settle: '.browse-boxcell',
  })

  await expect(page.locator('.browse-boxcell[aria-current="true"]')).toHaveAttribute('aria-label', /^ETB codes/)
})

/* AND THE THREE PATHS THAT MUST NOT HAVE MOVED, in one case rather than three files of setup.
 * The fix widens the window in which the hash outranks the shelf already picked, so what has to
 * stay true is that the window CLOSES: a box that does not exist must not hold the request open
 * and must not yank the walk later. */
test('a hash naming no box falls back, and does not hold the walk open', async ({ page }) => {
  await open(page, BOXES, STORE, () => PRICING, SALE, {
    route: '/#/inventory?box=99',
    boxesDelayMs: 300,
    settle: '.browse-boxcell',
  })

  /* The only shelf there is. The point is not that it chose 2 — there was nothing else to
     choose — but that it chose at all rather than waiting for a box 99 that is never coming. */
  await expect(page.locator('.browse-boxcell[aria-current="true"]')).toHaveAttribute('aria-label', /^ME01 commons/)
})

/* ================================================================== D132: sold folded away,
 * the name leads, the rail is ordered by the hand, and a section can be named. Each case here
 * was run once against the shipped tree with its own arm reverted — the chip absent, the sort
 * numeric, the note in the corner, the name missing from the sentence — and failed there. */

test('D132 — the product hides sold by default, and the chip says how many it folded away', async ({ page }) => {
  /* `hideSold: null` writes NOTHING to storage: this is the product's own default, asserted. */
  await open(page, BOXES, STORE, () => PRICING, SALE, { hideSold: null })
  await expandAll(page)

  const chip = page.locator('.browse-hidesold')
  await expect(chip).toHaveAttribute('aria-pressed', 'true')
  await expect(chip.locator('.bn-hidetoggle-count')).toHaveText('2')

  /* Seven records, one sold and one retired; five rows drawn, none of them departed. */
  const slots = page.locator('.browse-row .browse-row-position')
  await expect(slots).toHaveText(['#1', '#2', '#3', '#1', '#2'])
  await expect(page.locator('.browse-rowline.is-departed')).toHaveCount(0)

  /* AND THE COPIES LIST FOLDS THE SAME WAY, with a line saying so. Thievul's group holds two
     live copies and none departed; Eiscue's holds the sold one alone — so walk to a live card
     whose SKU group carries a departed copy is not in this fixture, and the line is asserted
     off the shared-SKU case below. What holds here is the absence: no `is-gone` row. */
  await page.locator('.browse-row').nth(0).click()
  await expect(page.locator('.card-locations-row')).toHaveCount(2)
  await expect(page.locator('.card-locations-row.is-gone')).toHaveCount(0)
})

test('UX-189 — unticked, a departed row stays where it sat, so the list and the arrow keys follow one order, and the choice is remembered', async ({ page }) => {
  await open(page, BOXES, STORE, () => PRICING, SALE, { hideSold: null })
  await expandAll(page)
  await page.locator('.browse-hidesold').click()
  await expect(page.locator('.browse-hidesold')).toHaveAttribute('aria-pressed', 'false')

  /* The store below puts the sold card FIRST in its section, which is the shape a real box
     takes after its first card sells. D132 sank it to the section's foot while the arrow keys
     still stepped onto it in box order (UX-189). It stays first now (FLT-22, nothing jumps). */
  const store: Store = {
    cards: {
      '2/1': card({ index: 1, state: 'sold', name: 'Eiscue', sku: '8937371', section: 1, sectionStart: 1, sectionEnd: 3 }),
      '2/2': card({ index: 2, at: 1, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3 }),
      '2/3': card({ index: 3, at: 2, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3 }),
      '2/6': card({ index: 6, at: 3, state: 'identified', name: 'Inteleon', sku: '8937373', section: 2, sectionStart: 3, sectionEnd: 4 }),
    },
    search: (query) => searchAnswer(query, {
      '2/1': card({ index: 1, state: 'sold', name: 'Eiscue', sku: '8937371', section: 1, sectionStart: 1, sectionEnd: 3 }),
      '2/2': card({ index: 2, at: 1, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3 }),
      '2/3': card({ index: 3, at: 2, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3 }),
      '2/6': card({ index: 6, at: 3, state: 'identified', name: 'Inteleon', sku: '8937373', section: 2, sectionStart: 3, sectionEnd: 4 }),
    }),
  }
  /* A FRESH PAGE IN THE SAME CONTEXT, not a reload: a reload fires the first store's requests
     before the second `open()` has registered its routes, and under the full suite's load
     that answer sometimes landed last — 1 in 483 on 2026-09-11, then 2 in 5 alone. The
     context is what holds `localStorage`, so the remembered choice still carries over. */
  const again = await page.context().newPage()
  await open(again, BOXES, store, () => PRICING, SALE, { hideSold: null })
  await expandAll(again)
  /* REMEMBERED: the press above wrote `show`, and this open wrote nothing over it. */
  await expect(again.locator('.browse-hidesold')).toHaveAttribute('aria-pressed', 'false')
  await expect(again.locator('.browse-row .browse-row-name')).toHaveText(['Eiscue', 'Thievul', 'Thievul', 'Inteleon'])
  /* THE KEYS WALK THE SAME ORDER: from the sold Eiscue, → lands on the Thievul drawn under it. */
  await again.locator('.browse-row').nth(0).click()
  await again.keyboard.press('ArrowRight')
  await expect(again.locator('.browse-row[aria-current="true"]')).toHaveCount(1)
  await expect(again.locator('.browse-row').nth(1)).toHaveAttribute('aria-current', 'true')
  /* The section header the sold card led is still ONE section, folded open, not two. */
  await expect(again.locator('.browse-sectfold')).toHaveCount(2)
})

test('UX-181 — the row the walk stands on survives its own sale while sold is hidden, stays when the walk moves, and folds on the next box load', async ({ page }) => {
  /* A store whose sale LANDS on the re-read — the record comes back DEPARTED, place and all,
     which is the shape the fold rule has to look past. `laddersAfterSale` flips only `state`. */
  const live = (index: number, at: number) =>
    card({ index, at, state: 'identified', name: 'Bashful Bloom', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 6 })
  const cards: Cards = { '2/1': live(1, 1), '2/3': live(3, 2), '2/5': live(5, 3) }
  const store: Store = { cards, search: (query) => searchAnswer(query, cards) }
  /* THE STORE MOVES INSIDE THE SALE, WHICH IS THE ONLY PLACE IT CAN MOVE SAFELY, and this case
     is `design-check`'s second recurring red until it does. Written as two assignments on the
     line AFTER the press, it is a race the browser wins under load: `click()` resolves when the
     click is DISPATCHED, and the app's own post-sale re-read can reach this fixture before Node
     runs the next statement — which serialises the PRE-sale store and draws three live rows,
     `#1 #2 #3`, held for the full 15s because the app re-reads once. Reproduced on this Mac
     every time with a 500ms wait wedged into that gap, with CI's exact message.
     MOVING THEM ABOVE THE PRESS IS NOT THE FIX EITHER, and it fails the other way: selecting
     the row has its own fetch in flight, which then answers from the already-sold store and
     draws `Undo`, so `Mark sold` never appears and the press times out. Measured, both ways.
     The sale handler is the one moment ordered against both — it runs when the POST arrives,
     which is necessarily after the row's fetch and before the re-read. */
  const sale: SaleStub = (box, index, undo) => {
    cards['2/3'] = card({ index: 3, state: 'sold', name: 'Bashful Bloom', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 6 })
    cards['2/5'] = live(5, 2)
    return SALE(box, index, undo)
  }
  await open(page, BOXES, store, () => PRICING, sale, { hideSold: true })
  await expandAll(page)
  await expect(page.locator('.browse-row .browse-row-position')).toHaveText(['#1', '#2', '#3'])
  await page.locator('.browse-row').nth(1).click()
  await page.locator('.card-locations-row.is-current').getByRole('button', { name: 'Mark sold' }).click()

  /* The receipt lands where the sale was pressed (D119) — which needs the row to still exist,
     and to still be where it was (D118): the re-read draws it departed, in its place. */
  await expect(page.locator('.card-locations-row.is-current').getByRole('button', { name: /Undo/ })).toBeVisible()
  await expect(page.locator('.browse-row .browse-row-position')).toHaveText(['#1', '#3', '#2'])
  await expect(page.locator('.browse-row[aria-current="true"] .browse-row-position')).toHaveText('#3')

  /* NOTHING JUMPS (UX-181, FLT-22). Step off it and it STAYS, in its place, marked sold: the
     next press lands on the row it aimed at, and no row moves under the pointer. */
  const rects = async () =>
    page.locator('.browse-row').evaluateAll((rows) => rows.map((row) => Math.round(row.getBoundingClientRect().top)))
  const before = await rects()
  await page.locator('.browse-row').nth(2).click()
  await expect(page.locator('.browse-row').nth(2)).toHaveAttribute('aria-current', 'true')
  await expect(page.locator('.browse-row .browse-row-position')).toHaveText(['#1', '#3', '#2'])
  expect(await rects()).toEqual(before)

  /* The fold happens on the next box load, when no row is under the hand. */
  await page.reload()
  await expandAll(page)
  await expect(page.locator('.browse-row .browse-row-position')).toHaveText(['#1', '#2'])
})

test('UX-254 — the fold toggle is "In stock only", on by default, counting what left', async ({
  page,
}) => {
  /* The owner's own wording, 2026-09-24: "maybe in stock only should be the toggle name?".
   * The meaning is unchanged — checked still folds a departed copy off the shelf — only the
   * words on it, and this asserts them rather than the class alone every other case reads. */
  await open(page, BOXES, STORE, () => PRICING, SALE, { hideSold: null })
  await expandAll(page)

  const toggle = page.getByRole('button', { name: /^In stock only/ })
  await expect(toggle).toBeVisible()
  await expect(page.getByRole('button', { name: /^Hide sold/ })).toHaveCount(0)
  await expect(toggle).toHaveAttribute('aria-pressed', 'true')
  // Eiscue (sold) and Mantine (retired) are the fixture's own two departed cards (D89's own
  // reason there are two): the count is what the fold hides, not every departed row that ever
  // sat on this shelf — `D132 — the Hide sold chip counts...` proves that distinction; this
  // just reads the same figure under the new name.
  await expect(toggle.locator('.bn-hidetoggle-count')).toHaveText('2')
})

test('D132 — the Hide sold chip counts what the fold actually hides, not every departed row on the shelf', async ({ page }) => {
  /* THE OVERCOUNT (owner's screenshot, box WB1 R2): `departedHere` counted every departed row
     on the shelf, but `visible` keeps the row the walk stands on (D119) whatever its state — so
     a card that has JUST sold and is still selected stays drawn while the chip claimed it was
     one of the ones folded away. Two departed rows on the shelf and only one actually hidden is
     the shape that exposed it: a pre-existing sold record that is always hidden, and a live one
     this case sells while it is selected, which the fold has to keep. */
  const live = (index: number, at: number) =>
    card({ index, at, state: 'identified', name: 'Bashful Bloom', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 6 })
  const cards: Cards = {
    '2/1': live(1, 1),
    '2/2': card({ index: 2, state: 'sold', name: 'Eiscue', sku: '8937371', section: 1, sectionStart: 1, sectionEnd: 6 }),
    '2/3': live(3, 2),
  }
  const store: Store = { cards, search: (query) => searchAnswer(query, cards) }
  const sale: SaleStub = (box, index, undo) => {
    cards['2/3'] = card({ index: 3, state: 'sold', name: 'Bashful Bloom', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 6 })
    return SALE(box, index, undo)
  }
  await open(page, BOXES, store, () => PRICING, sale, { hideSold: true })
  await expandAll(page)

  const chip = page.locator('.browse-hidesold')
  /* One departed row (Eiscue) already on the shelf, nothing selected yet: the fold hides it and
     the chip says so — one, not zero, and not the two it would read if it counted every live row
     that could someday leave. */
  await expect(page.locator('.browse-row .browse-row-position')).toHaveText(['#1', '#2'])
  await expect(chip.locator('.bn-hidetoggle-count')).toHaveText('1')

  await page.locator('.browse-row').nth(1).click()
  await page.locator('.card-locations-row.is-current').getByRole('button', { name: 'Mark sold' }).click()
  await expect(page.locator('.card-locations-row.is-current').getByRole('button', { name: /Undo/ })).toBeVisible()

  /* TWO DEPARTED ROWS ON THE SHELF NOW, AND THE FOLD STILL HIDES ONLY ONE — the row the walk
     stands on survives its own sale (D119) and stays drawn as `B2 #3`. The old count
     (`departedHere`) would read 2 here; this is the 6-claimed-5-hidden defect at its smallest
     reproduction. */
  await expect(page.locator('.browse-row .browse-row-position')).toHaveText(['#1', '#3'])
  await expect(chip.locator('.bn-hidetoggle-count')).toHaveText('1')

  /* Step off the sold row and it stays drawn (UX-181, nothing jumps), so the fold still hides
     one. On the next box load it goes, and both departed rows are hidden and counted. */
  await page.locator('.browse-row').nth(0).click()
  await expect(page.locator('.browse-row .browse-row-position')).toHaveText(['#1', '#3'])
  await expect(chip.locator('.bn-hidetoggle-count')).toHaveText('1')
  await page.reload()
  await expandAll(page)
  await expect(page.locator('.browse-row .browse-row-position')).toHaveText(['#1'])
  await expect(chip.locator('.bn-hidetoggle-count')).toHaveText('2')
})

test('B3 — a sale does not reorder the rail, on a device that has never opened either box', async ({ page }) => {
  /* B3 (the review's own repro was 26 vs 25, this is the same shape at the smallest gap that
   * shows it): two boxes tied on recency — NEITHER stored, "every box the browser has not
   * opened, so every box on a new device" — and tied on-hand too, so the box number decides
   * and RB Epics (2) leads MEG Bulk (6). A sale in RB Epics takes it to 24 on hand; MEG Bulk's
   * 25 is now the bigger number, and the OLD comparator's on-hand term put MEG Bulk on top —
   * moving every row under the pointer with no press behind it.
   * `kit/dataRules.ts:boxesMostRecentFirst` ties on the box's own `bid`, then its number —
   * neither of which a sale ever touches. */
  const boxes = {
    boxes: [
      { ...BOXES.boxes[0], box: 2, name: 'RB Epics', cards: 25, on_hand: 25, sold: 0, retired: 0 },
      { ...BOXES.boxes[0], box: 6, name: 'MEG Bulk', cards: 25, on_hand: 25, sold: 0, retired: 0, sections: [], sections_detail: [] },
    ],
  }
  const sale = movesOnSale(() => {
    const rbEpics = boxes.boxes.find((record) => record.box === 2)
    if (rbEpics !== undefined) {
      rbEpics.on_hand -= 1
      rbEpics.sold += 1
    }
  })
  await open(page, boxes, STORE, () => PRICING, sale, { settle: '.browse-boxcell' })

  const names = page.locator('.browse-boxcell .browse-boxcell-name')
  await expect(names).toHaveText(['RB Epics', 'MEG Bulk'])

  /* WAITED FOR EXPLICITLY, not sampled after a guessed delay: `Mark sold`'s own re-read
     (`doSell`'s `setReloads`) re-fetches `GET /boxes`, and `toHaveText` above would otherwise
     pass on the PRE-refetch order and finish before the async reorder this case is about ever
     lands — the exact race this file's own `SaleStub` comment warns against, one layer up. */
  const boxesRefetched = page.waitForResponse((response) => /\/boxes(\?|$)/.test(response.url()))
  await page.locator('.card-locations-row.is-current').getByRole('button', { name: 'Mark sold' }).click()
  await boxesRefetched
  await expect(page.locator('.card-locations-row.is-current').getByRole('button', { name: /Undo/ })).toBeVisible()

  await expect(names, 'the rail reordered under a sale with no press on it').toHaveText(['RB Epics', 'MEG Bulk'])
})

test('D132 — the rail draws names and no numbers, ordered by this browser\'s recency, then the box\'s own index, then number', async ({ page }) => {
  const boxes = {
    boxes: [
      { ...BOXES.boxes[0] },
      { ...BOXES.boxes[0], box: 6, name: 'Bulk', cards: 40, on_hand: 40, fill: 40, next_index: 41, sold: 0, retired: 0, sections: [], sections_detail: [] },
      { ...BOXES.boxes[0], box: 7, name: null, cards: 12, on_hand: 12, fill: 12, next_index: 13, sold: 0, retired: 0, sections: [], sections_detail: [] },
      { ...BOXES.boxes[0], box: 9, name: 'Twelve too', cards: 12, on_hand: 12, fill: 12, next_index: 13, sold: 0, retired: 0, sections: [], sections_detail: [] },
    ],
  }
  /* Box 7 was opened here yesterday; nothing else ever was. */
  await page.addInitScript(() => {
    /* ONCE PER TAB, so the reload below is a real next visit and reads what the press wrote. The
       tab's own marker is `window.name`, which survives a reload and touches no browser store. */
    if (window.name === 'seeded') return
    window.name = 'seeded'
    /* eslint-disable-next-line no-restricted-syntax -- SEEDING THE VERY KEY UNDER TEST, in the
       one file whose subject it is: `banchi.box-recency` lives in `app/src/deviceMemory.ts`
       (D132), and asserting the order it produces means writing it. It was
       `banchi.inventory.box-recency` until the capture screen started sorting on the same
       fact (D142) — two screens read it now, so the name stopped saying
       which one wrote it. */
    window.localStorage.setItem('banchi.box-recency', JSON.stringify({ '7': '2026-09-09T10:00:00.000Z' }))
  })
  await open(page, boxes, STORE, () => PRICING, SALE, { settle: '.browse-boxcell' })

  const names = page.locator('.browse-boxcell .browse-boxcell-name')
  /* Recency first (7), then the box's own index (none of these four carries a `bid`, so this
     fixture cannot tell that term apart from the number that follows it — B3 dropped `on_hand`
     as the one thing here that a sale can move), then the number breaks every other tie. */
  await expect(names).toHaveText(['Box 7', 'ME01 commons', 'Bulk', 'Twelve too'])
  await expect(page.locator('.browse-boxcell-num')).toHaveCount(0)
  /* The number survives where it is READ rather than looked at. `, 40 captured` is S16's own
     fix, landed beside this test: the bare `.browse-boxcell-count` figure had no unit and no
     accessible name of its own, so the count is now named in the one aria-label the button
     already carries (Bulk holds 40 cards per its own fixture, above). */
  await expect(page.locator('.browse-boxcell').nth(2)).toHaveAttribute('aria-label', 'Bulk, 40 captured')

  /* A PAGE LOAD IS NOT AN OPENING: the walk landed on box 7 (recency put it first) and the
     order is exactly what storage said, untouched. A press IS one, and it is written at once.
     BUT THE RAIL DOES NOT MOVE UNDER THE POINTER (UX-215, "nothing jumps"): the pressed box
     keeps its row until the next visit, and then it leads. */
  await page.locator('.browse-boxcell', { hasText: 'Bulk' }).click()
  await expect(page.locator('.browse-boxcell', { hasText: 'Bulk' })).toHaveAttribute('aria-current', 'true')
  await expect(names).toHaveText(['Box 7', 'ME01 commons', 'Bulk', 'Twelve too'])
  const stored = await page.evaluate(
    /* eslint-disable-next-line no-restricted-syntax -- READING THE SAME KEY BACK, to see that a
       press wrote it and a page load did not. */
    () => JSON.parse(window.localStorage.getItem('banchi.box-recency') ?? '{}') as Record<string, string>,
  )
  expect(Object.keys(stored).sort()).toEqual(['6', '7'])
  expect((stored['6'] ?? '') > (stored['7'] ?? '')).toBe(true)

  /* THE NEXT VISIT. */
  await page.reload()
  await expect(names).toHaveText(['Bulk', 'Box 7', 'ME01 commons', 'Twelve too'])
})

test('N3 — pressing a box does not scroll the box rail', async ({ page }) => {
  /* A rail long enough to scroll, viewport short enough to force it — the shape the finding
   * was measured on. Box #4, pressed below, sits partly past the rail's own visible foot —
   * genuinely off by a few pixels, which is exactly the shape the old "nearest" scroll-into-
   * view answered by moving every OTHER row under a press that named only this one.
   *
   * `dispatchEvent('click')` RATHER THAN `.click()`: Playwright's own click performs its own
   * scroll-into-view first when a target is not fully in the (real, 700px-tall) viewport, which
   * would measure ITS scrolling rather than the product's — this element sits inside a much
   * shorter INNER scroller (`.browse-boxes`), so a native click on it, unlike Playwright's,
   * never needs a page-level scroll first. */
  const many = Array.from({ length: 20 }, (_, i) => ({
    ...BOXES.boxes[0],
    box: i + 1,
    name: `Box ${i + 1} name`,
    sections: [],
    sections_detail: [{ section: 1, start: 1, end: 5, count: 5 }],
  }))
  await page.setViewportSize({ width: 1440, height: 700 })
  await open(page, { boxes: many }, STORE, () => PRICING, SALE, {
    route: '/#/inventory?box=1',
    settle: '.browse-boxcell',
  })

  const rail = page.locator('.browse-boxes')
  const cells = page.locator('.browse-boxcell')
  await expect(cells).toHaveCount(20)
  const scrollTopBefore = await rail.evaluate((el) => el.scrollTop)

  await cells.nth(3).dispatchEvent('click')
  await expect(cells.nth(3)).toHaveAttribute('aria-current', 'true')

  const scrollTopAfter = await rail.evaluate((el) => el.scrollTop)
  expect(scrollTopAfter, 'the rail scrolled under a press').toBe(scrollTopBefore)
})

test('D132 — the address leads with the name and the index is its note, on the row the walk stands on and on every other', async ({ page }) => {
  await open(page)
  await expandAll(page)
  await page.locator('.browse-row').nth(0).click()

  /* THE ROW THE WALK STANDS ON IS THE ADDRESS (D119): there is no location card above the list
     to lead with anything, so the name leads on `.is-current` exactly as it leads on its siblings. */
  const label = page.locator('.card-locations-row.is-current .card-locations-label .position-parts')
  await expect(label.locator('.position-path')).toHaveText('BOX ME01 commonsSECTION 1')
  /* The server's string is untouched: this is a rendering, not an edit (D41's invariant). */
  await expect(label).toHaveAttribute('aria-label', 'Box 2, Section 1, Card 1')

  const rows = page.locator('.card-locations-row .position-path')
  await expect(rows.nth(0)).toHaveText('BOX ME01 commonsSECTION 1')
})

test('D132 — an unnamed box keeps the index in the address and draws no note beside it', async ({ page }) => {
  const store: Store = {
    cards: { '2/1': card({ index: 1, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3, boxName: '' }) },
    search: (query) => searchAnswer(query, { '2/1': card({ index: 1, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3, boxName: '' }) }),
  }
  await open(page, { boxes: [{ ...BOXES.boxes[0], name: null }] }, store)
  await expandAll(page)
  await page.locator('.browse-row').nth(0).click()
  /* An unnamed box reads its default name, which says Box itself, so no key rides in front. */
  await expect(page.locator('.card-locations-row.is-current .position-path')).toHaveText('Box 2SECTION 1')
  await expect(page.locator('.card-locations-row.is-current .position-note')).toHaveCount(0)
})


/** WHERE A SECTION TITLE'S COUNT IS DRAWN, against the title's own box — the box that clips it.
 *  Measured off the TEXT with a Range, not off a count element, so the same probe reads a title
 *  drawn as one span (the old shape, where the ellipsis cut the count) and as two. `overflow` is
 *  how far the whole sentence runs past the box: above 0 means the name really was cut, so a
 *  green count is not a title that simply fit. */
async function sectionTitleFit(title: Locator, count: string): Promise<{ countInside: boolean; overflow: number; text: string }> {
  return title.evaluate((el, needle) => {
    const box = el.getBoundingClientRect()
    const all = document.createRange()
    all.selectNodeContents(el)
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
    let countInside = false
    for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
      const at = (node.textContent ?? '').indexOf(needle)
      if (at < 0) continue
      const range = document.createRange()
      range.setStart(node, at)
      range.setEnd(node, at + needle.length)
      const r = range.getBoundingClientRect()
      countInside = r.width > 0 && r.left >= box.left - 0.5 && r.right <= box.right + 0.5
    }
    return { countInside, overflow: all.getBoundingClientRect().width - box.width, text: el.textContent ?? '' }
  }, count)
}

test('a long section name is drawn whole, and its count is said once, at 820', async ({ page }) => {
  /* The same title `#/orders` draws (`SectionTitle.tsx`): the NAME ellipsizes, `3 cards` stays
     whole. Verified red first: the one-span title cut the count, the end of the sentence. */
  await page.setViewportSize({ width: 820, height: 1180 })
  const named = (input: Parameters<typeof card>[0]) => {
    const one = card(input)
    return { ...one, place: { ...one.place, section_name: 'Holographic promos from the vintage binder' } }
  }
  const cards = {
    '2/1': named({ index: 1, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3 }),
    '2/2': named({ index: 2, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3 }),
  }
  const boxes = {
    boxes: [{
      ...BOXES.boxes[0],
      cards: 2, on_hand: 2, fill: 2, next_index: 3, sold: 0, retired: 0,
      sections_detail: [{ section: 1, start: 1, end: 3, count: 2, name: 'Holographic promos from the vintage binder' }],
    }],
  }
  await open(page, boxes, { cards, search: (query) => searchAnswer(query, cards) })
  await expandAll(page)

  const title = page.locator('.browse-secttitle').first()
  await expect(title).toHaveText('Section 1: Holographic promos from the vintage binder, 3 cards')
  /* THE OWNER'S RULING, LOC-21: the section's name is the label on its divider, so it is never cut;
     it wraps. The count is the pill's, and the title only speaks it (\`.bn-sr\`). */
  const fit = await sectionTitleFit(title.locator('.browse-secttitle-head'), 'vintage binder')
  expect(fit.overflow).toBeLessThanOrEqual(0.5)
  await expect(title.locator('.browse-secttitle-count')).toHaveClass(/bn-sr/)
})

test('D132 — a named section is said in the walk header, in the bar\'s sentence and on the label', async ({ page }) => {
  const named = (input: Parameters<typeof card>[0]) => {
    const one = card(input)
    return { ...one, place: { ...one.place, section_name: 'Rares' } }
  }
  const cards = {
    '2/1': named({ index: 1, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3 }),
    '2/2': named({ index: 2, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3 }),
  }
  const boxes = {
    boxes: [{
      ...BOXES.boxes[0],
      cards: 2, on_hand: 2, fill: 2, next_index: 3, sold: 0, retired: 0,
      sections_detail: [
        { section: 1, start: 1, end: 3, count: 2, name: 'Rares' },
        { section: 2, start: 4, end: 5, count: 0, name: null },
      ],
    }],
  }
  await open(page, boxes, { cards, search: (query) => searchAnswer(query, cards) })
  await expandAll(page)
  /* D218: the separator is punctuation in a real sentence, not a typed middle dot
     (`sectionTitleOf`, BoxBrowse.tsx). The section states its OWN count — 3 cards, not the
     box-wide `#1–#3` span, which is a different ruler than the row's own `#1`/`#2` (the fix
     this file's own photo-issues session found: a box-wide range over a within-section
     number read as out of range). */
  await expect(page.locator('.browse-secttitle').first()).toHaveText('Section 1: Rares, 3 cards')
  await page.locator('.browse-row').nth(0).click()
  await expect(page.locator('.card-locations-row.is-current .position-bar-text').nth(1)).toHaveText('Section 1Rarescard 1 of 3')
  await expect(page.locator('.card-locations-row.is-current .position-path')).toHaveText('BOX ME01 commonsSECTION 1Rares')

  /* AND THE NAME IS WRITTEN FROM THE MANAGE SHEET, keyed by the section's number. */
  await page.route(/\/boxes\/2$/, async (route) => {
    const body = route.request().postDataJSON() as { section_names?: Record<string, string> }
    expect(route.request().method()).toBe('PUT')
    /* Every section goes in the PUT, blanks included — a blank CLEARS (D132). */
    expect(body.section_names).toEqual({ '1': 'Top rares', '2': '' })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ...boxes.boxes[0], sections_detail: [{ section: 1, start: 1, end: 3, count: 2, name: 'Top rares' }, { section: 2, start: 4, end: 5, count: 0, name: null }] }),
    })
  })
  await openBoxOps(page)
  await page.getByRole('button', { name: /^Name sections/ }).click()
  const field = page.locator('.boxops-section-names input').first()
  await expect(field).toHaveValue('Rares')
  await field.fill('Top rares')
  await page.getByRole('button', { name: 'Save names' }).click()
  await expect(page.locator('.boxops-editor')).toHaveCount(0)
})

// ---------------------------------------------------------------------------------------
// D213 — the game/set/rarity filter. Two boxes, two games, and one UNCLASSIFIED card in
// each — the shape the decision itself measured (2,960 of 2,960 Riftbound cards resolve a
// set; 0 of 543 Pokemon cards do, because no Pokemon export has ever been fetched). The
// fixture's `boxes` answer is a FUNCTION of the request's own query string, because the
// assertion that matters is what the SCREEN renders under a real filter round-trip —
// `getBoxes` sending `?game=riftbound&set=`, this fixture reading it back — never a prop
// this test handed the component directly.

const FACET_CARDS: Cards = {
  '1/1': card({
    index: 1,
    state: 'identified',
    name: 'Calm Rune',
    sku: 'CR-UNL-001',
    section: 1,
    sectionStart: 1,
    sectionEnd: 2,
    box: 1,
    boxName: 'Riftbound box',
    boxTotal: 2,
    game: 'riftbound',
    setName: 'Unleashed',
    catalogRarity: 'Rare',
  }),
  '1/2': card({
    index: 2,
    state: 'identified',
    name: 'Mind Rune',
    sku: 'CR-UNL-002',
    section: 1,
    sectionStart: 1,
    sectionEnd: 2,
    box: 1,
    boxName: 'Riftbound box',
    boxTotal: 2,
    game: 'riftbound',
    // UNCLASSIFIED — no export has resolved this card's set or rarity. D213's own standing
    // rule: reachable under a filter, never dropped.
    setName: null,
    catalogRarity: null,
  }),
  '2/1': card({
    index: 1,
    state: 'identified',
    name: 'Pikachu',
    sku: 'PK-ME01-001',
    section: 1,
    sectionStart: 1,
    sectionEnd: 1,
    box: 2,
    boxName: 'Pokemon box',
    boxTotal: 1,
    game: 'pokemon',
    setName: null,
    catalogRarity: null,
  }),
}
const FACET_STORE: Store = { cards: FACET_CARDS, search: () => ({ groups: [] }) }

/** `GET /boxes` for the facet store. The facet vocabulary and every count now come off
 *  `facet_cells` (FLT-09), so the route ignores any filter query: a pick asks nothing. */
function facetBoxes() {
  const box = (n: number, name: string, cards: number) => ({
    ...BOXES.boxes[0],
    box: n,
    name,
    cards,
    on_hand: cards,
    fill: cards,
    next_index: cards + 1,
    sold: 0,
    retired: 0,
    sections: [1],
    sections_detail: [{ section: 1, start: 1, end: cards, count: cards }],
  })
  return {
    boxes: [box(1, 'Riftbound box', 2), box(2, 'Pokemon box', 1)],
    facets: { games: [], sets: {}, rarities: {} },
    facet_cells: [
      { box: 1, game: 'riftbound', set: 'Unleashed', rarity: 'Rare', gone: false, count: 1 },
      { box: 1, game: 'riftbound', set: null, rarity: null, gone: false, count: 1 },
      { box: 2, game: 'pokemon', set: null, rarity: null, gone: false, count: 1 },
    ],
  }
}

/** Pick one option of one facet in the rail's filter popover, opening it first. */
async function pickFacet(page: Page, facet: 'Game' | 'Set' | 'Rarity', option: string | RegExp) {
  const popover = page.locator('.bn-filterbar-popover')
  if ((await popover.count()) === 0) await page.locator('.browse-filterbar .bn-filterbar-trigger:visible').click()
  await popover.locator('.bn-pick', { hasText: new RegExp(`^${facet}`) }).click()
  await page.locator('.bn-pick-opt', { hasText: option }).first().click()
  await page.keyboard.press('Escape') // the pick list, not the popover
}

async function facetOptions(page: Page, facet: 'Game' | 'Set' | 'Rarity'): Promise<string[]> {
  const popover = page.locator('.bn-filterbar-popover')
  if ((await popover.count()) === 0) await page.locator('.browse-filterbar .bn-filterbar-trigger:visible').click()
  await popover.locator('.bn-pick', { hasText: new RegExp(`^${facet}`) }).click()
  const texts = (await page.locator('.bn-pick-opt').allInnerTexts()).map((text) => text.replace(/\s+/g, ' ').trim())
  await page.keyboard.press('Escape')
  return texts
}

test('N5 — the search placeholder fits the rail column at 720 and 820', async ({ page }) => {
  /* Measured with a canvas rather than `scrollWidth`: an EMPTY native `<input>` does not track
   * placeholder overflow in its own scroll metrics, so the only reliable read of "does this
   * text fit" is measuring it in the field's own font, the same way the browser lays it out. */
  const fitsColumn = () =>
    page.evaluate(() => {
      const input = document.querySelector<HTMLInputElement>(
        '.browse-filterbar input[type="search"], .browse-filterbar .search-field input',
      )
      if (input === null) return null
      const style = getComputedStyle(input)
      const canvas = document.createElement('canvas')
      const ctx = canvas.getContext('2d')
      if (ctx === null) return null
      ctx.font = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`
      const textWidth = ctx.measureText(input.placeholder).width
      const available = input.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)
      return { textWidth, available, placeholder: input.placeholder }
    })

  for (const width of [720, 820]) {
    await page.setViewportSize({ width, height: 900 })
    await open(page)
    const fit = await fitsColumn()
    expect(fit, `no search field found to measure at ${width}`).not.toBeNull()
    expect(
      (fit?.textWidth ?? Infinity) <= (fit?.available ?? 0),
      `"${fit?.placeholder}" (${fit?.textWidth}px) does not fit the field (${fit?.available}px) at ${width}`,
    ).toBe(true)
  }
})

test('D213 — filtering by game narrows the walk, and the menu is built off the store, not a hardcoded list', async ({
  page,
}) => {
  await open(page, facetBoxes, FACET_STORE, () => PRICING, SALE, { route: '/#/inventory?box=1' })

  await expect(page.locator('.browse-row')).toHaveCount(2)

  await pickFacet(page, 'Game', 'Riftbound')
  // Box 2 (Pokemon) holds no match, and the rail says so in the one "no match" label (UX-261).
  await expect(page.locator('.browse-boxcell', { hasText: 'Pokemon box' })).toContainText('No match')
  await expect(page.locator('.browse-row')).toHaveCount(2)

  // Every set the store holds, counted under the Game pick: Riftbound's two, and nothing for a
  // Pokemon card that the Game pick already left out.
  expect(await facetOptions(page, 'Set')).toEqual(['Unleashed 1', 'No set on file 1'])

  await pickFacet(page, 'Set', 'Unleashed')
  await expect(page.locator('.browse-row')).toHaveCount(1)
  await expect(page.locator('.browse-row')).toContainText('Calm Rune')
})

test('D213 — the unclassified bucket is reachable under a set filter, never dropped', async ({ page }) => {
  await open(page, facetBoxes, FACET_STORE, () => PRICING, SALE, { route: '/#/inventory?box=1' })

  await pickFacet(page, 'Game', 'Riftbound')
  await pickFacet(page, 'Set', 'No set on file')

  await expect(page.locator('.browse-row')).toHaveCount(1)
  await expect(page.locator('.browse-row')).toContainText('Mind Rune')
})

test('D213 — clearing the filter restores every card, and a fully-classified card resolves game AND rarity together', async ({
  page,
}) => {
  await open(page, facetBoxes, FACET_STORE, () => PRICING, SALE, { route: '/#/inventory?box=1' })

  await pickFacet(page, 'Game', 'Riftbound')
  await pickFacet(page, 'Rarity', 'Rare')
  await expect(page.locator('.browse-row')).toHaveCount(1)
  await expect(page.locator('.browse-row')).toContainText('Calm Rune')

  await page.keyboard.press('Escape') // the popover
  await page.locator('.browse-filterbar .bn-filtercount-clear').click()
  await expect(page).toHaveURL(/#\/inventory\?box=1$/)
  await expect(page.locator('.browse-row')).toHaveCount(2)
})

test('UX-176 — Set and Rarity work before Game, and a Game pick never wipes them (the owner: "only IN THAT ORDER")', async ({
  page,
}) => {
  await open(page, facetBoxes, FACET_STORE, () => PRICING, SALE, { route: '/#/inventory?box=1' })

  /* RARITY FIRST, with no game picked. Its menu lists every rarity in the store, across both
     games, each with a count. */
  expect(await facetOptions(page, 'Rarity')).toEqual(['Rare 1', 'No rarity on file 2'])
  await pickFacet(page, 'Rarity', 'Rare')
  await expect(page.locator('.browse-row')).toHaveCount(1)
  await expect(page.locator('.browse-boxcell', { hasText: 'Pokemon box' })).toContainText('No match')

  /* THEN GAME. The Rarity pick stands: the URL still carries it, and the walk still honours it. */
  await pickFacet(page, 'Game', 'Riftbound')
  await expect(page).toHaveURL(/rarity=Rare/)
  await expect(page).toHaveURL(/game=riftbound/)
  await expect(page.locator('.browse-row')).toHaveCount(1)
  await expect(page.locator('.browse-row')).toContainText('Calm Rune')

  /* A SECOND GAME ADDS, IT DOES NOT REPLACE: Pokemon's one card has no rarity, so the walk is
     unchanged, and nothing was cleared on the way. */
  await pickFacet(page, 'Game', 'Pokémon')
  await expect(page).toHaveURL(/rarity=Rare/)
  await expect(page.locator('.browse-row')).toHaveCount(1)

  /* AND NO FACET IS EVER DISABLED. */
  for (const trigger of await page.locator('.bn-filterbar-popover .bn-pick').all()) await expect(trigger).toBeEnabled()
})

test('D132 — a search lands on a box with a LIVE copy, never on the sold one the walk was standing beside', async ({ page }) => {
  /* THE OWNER'S REPORT, 2026-09-11: a search "pulled up a sold listing as the front runner".
     Box 2 is the box being walked and its only Eiscue is sold; box 7 holds a live one. The
     walk used to keep box 2 because it had A match, and then landed on the only row it had. */
  const cards: Cards = {
    ...CARDS,
    '7/40': card({ index: 40, state: 'identified', name: 'Eiscue', sku: '8937371', section: 1, sectionStart: 1, sectionEnd: 40, box: 7, boxName: 'ME01 spares', boxTotal: 40 }),
  }
  const store: Store = { cards, search: (query) => searchAnswer(query, cards) }
  await open(page, TWO_BOXES, store, () => PRICING, SALE, { route: '/#/inventory?box=2', hideSold: null })
  await expect(page.locator('.browse-boxcell[aria-current="true"]')).toHaveAttribute('aria-label', /^ME01 commons/)

  await page.getByRole('searchbox').fill('Eiscue')
  await expect(page.locator('.browse-boxcell[aria-current="true"]')).toHaveAttribute('aria-label', /^ME01 spares/)
  await expect(page.locator('.card-locations-row.is-current .position-parts')).toHaveAttribute('aria-label', 'Box 7, Section 1, Card 40')
  /* And the copy the walk stands on is the live one, not the departed one. */
  await expect(page.locator('.card-locations-row.is-current')).not.toHaveClass(/is-gone/)
})

test('D132 — the copies list, the rail and the landing lead with the section holding the most live copies', async ({ page }) => {
  /* THE OWNER'S RULE, 2026-09-11, repeated back and confirmed: "the largest quantity of
     whatever I searched, by section, is the order". One in box 2 section 1, two in box 2
     section 2, three in box 7 — and a sold one in box 2 section 1 that counts for nothing. */
  const thievul = (index: number, at: number, section: number, start: number, end: number, box = 2, state = 'identified') =>
    card({ index, at, state, name: 'Thievul', sku: '8937370', section, sectionStart: start, sectionEnd: end, box, boxName: box === 7 ? 'ME01 spares' : undefined, boxTotal: box === 7 ? 40 : 5 })
  const cards: Cards = {
    '2/1': thievul(1, 1, 1, 1, 3),
    '2/2': thievul(2, 2, 1, 1, 3, 2, 'sold'),
    '2/3': card({ index: 3, at: 2, state: 'identified', name: 'Eiscue', sku: '8937371', section: 1, sectionStart: 1, sectionEnd: 3 }),
    '2/6': thievul(6, 3, 2, 3, 5),
    '2/7': thievul(7, 4, 2, 3, 5),
    '7/38': thievul(38, 38, 1, 1, 40, 7),
    '7/39': thievul(39, 39, 1, 1, 40, 7),
    '7/40': thievul(40, 40, 1, 1, 40, 7),
  }
  const store: Store = { cards, search: (query) => searchAnswer(query, cards) }
  /* BOX 2 IS THE BIGGER BOX, so nothing but the answer's own count can put box 7 first in the
     rail — with the fixture's 5-against-40 the on-hand tie-breaker did that on its own, and the
     rail assertion below passed with the rank term deleted. */
  const boxes = { boxes: TWO_BOXES.boxes.map((box) => (box.box === 2 ? { ...box, cards: 60, on_hand: 60, fill: 60, next_index: 61 } : box)) }
  await open(page, boxes, store, () => PRICING, SALE, { route: '/#/inventory?box=2', hideSold: null })
  await expandAll(page)
  await page.locator('.browse-row').nth(0).click()

  /* The copies list: box 7's three, then box 2 section 2's two, then the lone one. */
  const labels = page.locator('.card-locations-row .position-parts')
  await expect(labels).toHaveCount(6)
  await expect(labels.nth(0)).toHaveAttribute('aria-label', 'Box 7, Section 1, Card 38')
  await expect(labels.nth(3)).toHaveAttribute('aria-label', 'Box 2, Section 2, Card 1')
  await expect(labels.nth(5)).toHaveAttribute('aria-label', 'Box 2, Section 1, Card 1')

  /* A search: the rail leads with box 7 and the walk lands on the first of its three. */
  await page.getByRole('searchbox').fill('Thievul')
  await expect(page.locator('.browse-boxcell').first()).toHaveAttribute('aria-label', /^ME01 spares/)
  await expect(page.locator('.browse-boxcell[aria-current="true"]')).toHaveAttribute('aria-label', /^ME01 spares/)
  await expect(page.locator('.card-locations-row.is-current .position-parts')).toHaveAttribute('aria-label', 'Box 7, Section 1, Card 38')

  /* And pressing box 2 under the same search lands in ITS fullest section, section 2. */
  await page.locator('.browse-boxcell[aria-label^="ME01 commons"]').click()
  await expect(page.locator('.card-locations-row.is-current .position-parts')).toHaveAttribute('aria-label', 'Box 2, Section 2, Card 1')
})

/* ------------------------------------------------------- the order stops moving under a sale
 *
 * THE OWNER'S REPORT: "i search a card it's ranked by the most of the card in a certain section,
 * this is awesome and i love it but i realized if i mark sold while on that sorta view it can
 * reorganize the rankings right in front of me, which feels unintuitive if im trying to mark
 * multiple as sold."
 *
 * D132's ranking is correct and stays; what it could not do is hold still. `frozenRank.ts` is the
 * mechanism and D28 is the precedent — "the review answer gets an undo window, and the list stops
 * moving under it", the same ruling on the other screen.
 *
 * BOTH DIRECTIONS, IN ONE CASE EACH, BECAUSE ONE DIRECTION PASSES ON THE BUG. A case that only
 * asserts "the order did not change" is green against a build that never ranks at all, and a case
 * that only asserts "the re-rank changed it" is green against a build that re-ranks on every
 * press. The pair is the claim.
 *
 * AND THE ROW KEYS, NEVER THE COUNT. The failure mode is a length-preserving reshuffle: five rows
 * before and five rows after, in a different order. `toHaveCount` cannot see it and neither can a
 * sweep of positions, because the rows are identical boxes with different contents. Every
 * assertion below compares the ORDERED LIST OF POSITION LABELS, which is each row's identity.
 */

/** The copies list as an ordered list of row identities — the server's own position label per
 *  row, which is the one string that names WHICH copy is drawn there. */
async function copyOrder(page: Page): Promise<string[]> {
  const labels = page.locator('.card-locations-row .position-parts')
  const n = await labels.count()
  const out: string[] = []
  for (let i = 0; i < n; i += 1) out.push((await labels.nth(i).getAttribute('aria-label')) ?? '')
  return out
}

/** The WALK as an ordered list of row identities — each row's slot cell, which is `#38` for a
 *  card in its slot and the store key `B7 #38` for one that has left (D68). The third list one
 *  press can move, and the one `Hide sold` empties a row out of. */
async function walkOrder(page: Page): Promise<string[]> {
  return await page.locator('.browse-row .browse-row-position').allTextContents()
}

/** The box rail as an ordered list of tiles, which is the other thing D132's rule ranks. */
async function railOrder(page: Page): Promise<string[]> {
  const cells = page.locator('.browse-boxcell')
  const n = await cells.count()
  const out: string[] = []
  for (let i = 0; i < n; i += 1) out.push((await cells.nth(i).getAttribute('aria-label')) ?? '')
  return out
}

/* WHAT THE COPIES COLUMN DID, FRAME BY FRAME, BECAUSE A POLL CANNOT SEE IT (D118).
 *
 * Every `expect(locator)` in this file retries until it is true and then stops asking, so a
 * list that empties and fills again between two polls is invisible to all of them — and that
 * is precisely the shape of the defect this guards: the column came back, so every assertion
 * about it passed, while the owner watched six rows turn into nothing under his hand.
 * `requestAnimationFrame` is the only sampler here that runs on the browser's own paint
 * schedule, so it cannot step over a frame the operator could have seen.
 *
 * THREE THINGS ARE WATCHED AND THEY FAIL DIFFERENTLY. `rows` is what the operator counts.
 * `column` is `.inventory-detail`, which goes to zero when the panel is TORN DOWN rather than
 * re-pointed. `skeleton` is the panel rebuilt from nothing and waiting on a fetch it should
 * never have had to make. A guard reading only the first would have called the rebuild a
 * blank and sent the next session looking in the wrong file. */
async function installCopiesWatch(page: Page): Promise<void> {
  await page.evaluate(() => {
    const seen: { rows: number; column: number; skeleton: number }[] = []
    ;(window as unknown as { __copiesWatch: typeof seen }).__copiesWatch = seen
    const tick = () => {
      seen.push({
        rows: document.querySelectorAll('.card-locations-row .position-parts').length,
        column: document.querySelectorAll('.inventory-detail').length,
        skeleton: document.querySelectorAll('.inventory-detail .bn-skeleton').length,
      })
      requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  })
}

/** The watch's verdict: the column was there, full, and never rebuilt. */
async function expectCopiesHeld(page: Page): Promise<void> {
  const seen = await page.evaluate(
    () =>
      (window as unknown as { __copiesWatch?: { rows: number; column: number; skeleton: number }[] })
        .__copiesWatch ?? [],
  )
  /* THE WATCH ITSELF IS CHECKED FIRST. An empty recording is a watch that never ran — a
     navigation, or an install after the work was already over — and that reads as a pass. */
  expect(seen.length, 'the frame watch recorded nothing').toBeGreaterThan(2)
  const lost = seen
    .map((frame, at) => ({ ...frame, at }))
    .filter((frame) => frame.rows === 0 || frame.column === 0 || frame.skeleton > 0)
  expect(
    lost.map(
      (frame) => `#${frame.at} rows=${frame.rows} column=${frame.column} skeleton=${frame.skeleton}`,
    ),
    `${seen.length} frames watched`,
  ).toEqual([])
}

/* THE FIXTURE THE OWNER'S COMPLAINT NEEDS, and it is D132's own with one copy moved.
 *
 * Six live Thievul: THREE in box 7 section 1, TWO in box 2 section 2, ONE in box 2 section 1. So
 * the ranking is box 7 first, and box 7's three are the top three rows. Selling ONE of box 7's
 * three drops it to two, which TIES box 2 section 2 — and a live re-rank moves box 2's pair up
 * past the two that are left. That tie is the point of the shape: a fixture where the leader
 * stays the leader after a sale cannot tell a frozen order from a recomputed one. */
function stackedThievul(): Cards {
  const thievul = (index: number, at: number, section: number, start: number, end: number, box = 2) =>
    card({
      index, at, state: 'identified', name: 'Thievul', sku: '8937370',
      section, sectionStart: start, sectionEnd: end, box,
      boxName: box === 7 ? 'ME01 spares' : undefined,
      boxTotal: box === 7 ? 40 : 5,
    })
  return {
    '2/1': thievul(1, 1, 1, 1, 3),
    /* `at` IS D58's BOX-WIDE COUNT and section 2 starts at slot 3, so these two are the box's
       third and fourth cards — `Section 2 · Card 1` and `Card 2`. Numbering them 2 and 3 draws
       `Card 0`, which is what a fixture that forgot the section's own start produces. */
    '2/6': thievul(6, 3, 2, 3, 5),
    '2/7': thievul(7, 4, 2, 3, 5),
    '7/38': thievul(38, 38, 1, 1, 40, 7),
    '7/39': thievul(39, 39, 1, 1, 40, 7),
    '7/40': thievul(40, 40, 1, 1, 40, 7),
  }
}

/** The box registry that fixture needs, with box 2 made the BIGGER box so nothing but the
 *  answer's own count can put box 7 first — the tie-breaker below the rank term is `on_hand`,
 *  and D132's own case records that leaving box 2 small let the rail assertion pass with the
 *  rank term deleted. */
const STACKED_BOXES = {
  boxes: TWO_BOXES.boxes.map((box) =>
    box.box === 7
      ? { ...box, cards: 3, on_hand: 3, fill: 40, next_index: 41, sections_detail: [{ section: 1, start: 1, end: 40, count: 3 }] }
      : { ...box, cards: 60, on_hand: 60, fill: 60, next_index: 61 },
  ),
}

/** The six-copy fixture, wired for a sale that really departs — `sell` alone moves `state` and
 *  the server also empties the place (D118's note on this fixture), and the ranking reads the
 *  place's section, so a half-move would be a store shape the server cannot produce. */
function stackedStore(): { store: Store; depart: (key: string) => void } {
  const cards = stackedThievul()
  const inner = sellableStore()
  return {
    store: { cards, search: (query) => searchAnswer(query, cards) },
    depart: (key) => {
      const held = cards[key]
      if (held === undefined) return
      const place = held.place
      cards[key] = {
        ...held,
        state: 'sold',
        label: place.label,
        place: { ...place, slot: null, card: null, fraction: null },
      }
      delete (cards[key] as { card?: number }).card
      void inner
    },
  }
}

test('a sale leaves every other row where it was, and the sold row in its own place', async ({ page }) => {
  const { store, depart } = stackedStore()
  await open(page, STACKED_BOXES, store, () => PRICING, movesOnSale((undo) => { if (!undo) depart('7/38') }), {
    route: '/#/inventory?box=2',
    /* THE PRODUCT'S OWN DEFAULT (D132), not the fixture's, because the fold is half the claim:
       a frozen row that vanishes is the same jump through the other door. */
    hideSold: true,
  })
  await expandAll(page)
  await page.getByRole('searchbox').fill('Thievul')

  /* The order D132's rule produces: box 7's three, then box 2 section 2's two, then the lone
     one. Waited for by its own first row, so nothing below measures a list mid-answer. */
  /* THE RAIL FIRST, AND THE ORDER OF THESE TWO WAITS IS THE WHOLE OF IT. They are separate
     components with separate `useSearch` hooks, and the rail settling MOVES THE WALK — which
     re-selects a card, which puts the copies list back into its skeleton. Waited for the other
     way round, the copies list was measured, the rail then landed, and the snapshot taken
     afterwards came back EMPTY. Measured both ways: `railBefore` recording `Box 2, Box 7` in
     one order, `before[0]` undefined in the other. */
  await expect(page.locator('.browse-boxcell').first()).toHaveAttribute('aria-label', /^ME01 spares/)
  const labels = page.locator('.card-locations-row .position-parts')
  await expect(labels).toHaveCount(6)
  await expect(labels.nth(0)).toHaveAttribute('aria-label', 'Box 7, Section 1, Card 38')
  const before = await copyOrder(page)
  const railBefore = await railOrder(page)
  const walkBefore = await walkOrder(page)
  expect(railBefore[0]).toMatch(/^ME01 spares/)
  expect(before[0]).toBe('Box 7, Section 1, Card 38')
  expect(before[3]).toBe('Box 2, Section 2, Card 1')

  /* Sell the row the list leads with. Its section drops from three to two and TIES box 2's
     pair, so a live re-rank would move box 2's two copies above the two box 7 has left. */
  await copyRow(page, 'Box 7, Section 1, Card 38').getByRole('button', { name: 'Mark sold' }).click()
  await expect(page.locator('.inventory-receipt')).toContainText('Undo')

  /* WAIT FOR THE RE-READ AND NOT FOR THE OPTIMISM. `.is-gone` lands off `soldKeys` before any
     request goes out, so an assertion gated on it measures the list the press has not yet
     changed — the answer is right, a beat early, and the snapshot below reads stale labels.
     The DEPARTED LABEL is the wire's own and cannot appear until the re-read has landed. */
  await expect(
    page.locator('.card-locations-row .position-parts[aria-label="Was at Box 7, Section 1, Card 38"]'),
  ).toHaveCount(1)

  /* THE SOLD ROW IS STILL DRAWN AND STILL AT THE TOP. `Hide sold` is on, so without the freeze
     this row is not in the list at all and every row below it has come up one. */
  await expect(page.locator('.card-locations-row.is-gone')).toHaveCount(1)
  const after = await copyOrder(page)
  expect(after).toHaveLength(6)
  /* The departed row carries `join.departed_label` in place of its address (D58, D68) — the
     product's existing rendering for a copy in no slot, not a second one invented here. */
  expect(after[0]).toBe('Was at Box 7, Section 1, Card 38')
  /* AND EVERY OTHER ROW IS THE ROW IT WAS, in the position it was in. */
  expect(after.slice(1)).toEqual(before.slice(1))
  expect(await railOrder(page)).toEqual(railBefore)

  /* AND THE WALK, WHICH IS THE SECOND LIST THE SAME PRESS COULD HAVE MOVED. `Hide sold` is on,
     so without the freeze the sold row leaves the box's own walk too and the two rows under it
     come up — a jump in the left rail while the hand is in the right pane. The walk's row keys
     are its slot cells, and the departed one reads as the store key (D68). */
  expect(walkBefore).toEqual(['#38', '#39', '#40'])
  expect(await walkOrder(page)).toEqual(['#38', '#39', '#40'])

  /* And the control says how stale the order is, rather than the list quietly reshuffling. */
  await expect(page.locator('.card-locations-rerank')).toContainText('Order is 1 copy stale')
})

test('and the re-rank is what moves it — the same sale, with the order taken again', async ({ page }) => {
  const { store, depart } = stackedStore()
  await open(page, STACKED_BOXES, store, () => PRICING, movesOnSale((undo) => { if (!undo) depart('7/38') }), {
    route: '/#/inventory?box=2',
    hideSold: true,
  })
  await expandAll(page)
  await page.getByRole('searchbox').fill('Thievul')
  /* The rail first, for the reason the case above measures: it moves the walk when it lands. */
  await expect(page.locator('.browse-boxcell').first()).toHaveAttribute('aria-label', /^ME01 spares/)
  const labels = page.locator('.card-locations-row .position-parts')
  await expect(labels).toHaveCount(6)
  await expect(labels.nth(0)).toHaveAttribute('aria-label', 'Box 7, Section 1, Card 38')
  const before = await copyOrder(page)

  await copyRow(page, 'Box 7, Section 1, Card 38').getByRole('button', { name: 'Mark sold' }).click()
  await expect(page.locator('.card-locations-rerank')).toBeVisible()
  /* The re-read, waited for by the one string only it can produce — see the case above. */
  await expect(
    page.locator('.card-locations-row .position-parts[aria-label="Was at Box 7, Section 1, Card 38"]'),
  ).toHaveCount(1)
  /* AND THE ORDER HAS NOT MOVED, which is what makes the press below the subject of this case
     rather than a second reading of the one above. */
  expect(await copyOrder(page)).toEqual(['Was at Box 7, Section 1, Card 38', ...before.slice(1)])

  /* THE PRESS THE OWNER CHOOSES, and the only thing in this screen that reshuffles the list. */
  await page.locator('.card-locations-rerank').click()

  /* The control goes with the staleness it was reporting — the order is current again. */
  await expect(page.locator('.card-locations-rerank')).toHaveCount(0)

  /* STILL SIX ROWS, AND THAT IS D132's RULE RATHER THAN THE FREEZE: a copy sold from THIS
     screen is drawn while its receipt stands, so the press that sold it is still on screen with
     its Undo (D119). What the re-rank changes is the ORDER, which is the whole claim — asserted
     as the identity of every row and never as a count, because the failure mode here is a
     list of the same length in a different order. */
  await expect(labels).toHaveCount(6)
  const after = await copyOrder(page)
  expect(after).not.toEqual(before)

  /* Box 2's pair has taken the lead. Box 7 is down to two live copies, which TIES box 2's
     section 2, and a tie falls to the server's own order — so the two box 2 copies come first
     and the sold one sits with the section it is no longer counted in. */
  expect(after).toEqual([
    'Box 2, Section 2, Card 1',
    'Box 2, Section 2, Card 2',
    'Was at Box 7, Section 1, Card 38',
    'Box 7, Section 1, Card 39',
    'Box 7, Section 1, Card 40',
    'Box 2, Section 1, Card 1',
  ])
})

test('and the row is still there when its receipt has run out, which is the half the optimism was hiding', async ({ page }) => {
  /* THE TWENTY SECONDS ARE NOT THE FREEZE, AND A CASE INSIDE THEM CANNOT TELL THE TWO APART.
     `stays` keeps a row for three reasons — it is the copy the walk stands on, this screen just
     sold it and is holding a receipt (D132/D119), or the order is frozen by it. Every assertion
     in the cases above lands inside the receipt window, so the SECOND reason answers them and
     the third is never exercised: measured, deleting the freeze from that predicate leaves the
     whole file green. What the owner is doing takes minutes, and the receipt takes twenty
     seconds — so this is the case that is actually about them.

     THE CLOCK IS FAKED AND ONLY ADVANCED (D136), for the reason `brand.spec.ts` records at
     length: a twenty-second sleep is the suite's longest case by a distance and buys nothing a
     jump does not. Installed before the first navigation. */
  await page.clock.install()
  const { store, depart } = stackedStore()
  await open(page, STACKED_BOXES, store, () => PRICING, movesOnSale((undo) => { if (!undo) depart('7/38') }), {
    route: '/#/inventory?box=2',
    hideSold: true,
  })
  await expandAll(page)
  await page.getByRole('searchbox').fill('Thievul')
  await expect(page.locator('.browse-boxcell').first()).toHaveAttribute('aria-label', /^ME01 spares/)
  const labels = page.locator('.card-locations-row .position-parts')
  await expect(labels).toHaveCount(6)
  await expect(labels.nth(0)).toHaveAttribute('aria-label', 'Box 7, Section 1, Card 38')
  const before = await copyOrder(page)

  await copyRow(page, 'Box 7, Section 1, Card 38').getByRole('button', { name: 'Mark sold' }).click()
  await expect(
    page.locator('.card-locations-row .position-parts[aria-label="Was at Box 7, Section 1, Card 38"]'),
  ).toHaveCount(1)

  /* PAST THE WINDOW. `UNDO_WINDOW_MS` is 20s and the receipt's own timer is armed for it, so
     this is the frame after the optimism lets go: `soldKeys` drops the copy, its Undo goes, and
     the only thing left holding the row is the freeze. */
  await page.clock.runFor(25_000)
  await expect(page.locator('.inventory-receipt')).toHaveCount(0)

  /* STILL SIX ROWS, STILL IN THE SAME ORDER, AND THE SOLD ONE STILL AT THE TOP. Without the
     freeze the row folds away here and the five beneath it come up one — the same jump the
     owner reported, arriving twenty seconds late. */
  await expect(labels).toHaveCount(6)
  expect(await copyOrder(page)).toEqual(['Was at Box 7, Section 1, Card 38', ...before.slice(1)])
  /* And the control is still offering the re-rank, because nothing has taken a new order. */
  await expect(page.locator('.card-locations-rerank')).toContainText('Order is 1 copy stale')
})

test('a retirement holds its row too, and it is the freeze alone that does it', async ({ page }) => {
  /* THE DOOR THAT HAS NO OPTIMISM BEHIND IT (D26). `Inventory.tsx` hands the copies list
     `soldKeys` and deliberately not `retiredKeys`, so a retired copy is drawn as departed off
     the WIRE and nothing local is holding its row — which makes this the case where the freeze
     is the only thing keeping the list still. Measured: with the freeze deleted from `stays`,
     the sale cases stay green (a sale's own `soldKeys` answers them) and this one goes red. */
  const cards = stackedThievul()
  const store: Store = { cards, search: (query) => searchAnswer(query, cards) }
  await open(page, STACKED_BOXES, store, () => PRICING, SALE, {
    route: '/#/inventory?box=2',
    hideSold: true,
  })

  /* `open` stubs the sale and not the retirement, so this case brings its own — registered
     after it, which is the one Playwright consults first. The store moves when the POST
     arrives, for the reason `movesOnSale` spends its docstring on. */
  await page.route(/\/inventory\/\d+\/\d+\/retire$/, async (route) => {
    const held = cards['7/39']
    if (held !== undefined) {
      const place = held.place
      cards['7/39'] = {
        ...held,
        state: 'retired',
        label: place.label,
        place: { ...place, slot: null, card: null, fraction: null },
      }
      delete (cards['7/39'] as { card?: number }).card
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        position: '7/39', box: 7, index: 39, undone: false,
        state: 'retired', previous_state: 'identified', restores_to: 'identified',
        reason: 'damaged', listing: null, card: null,
      }),
    })
  })

  await expandAll(page)
  await page.getByRole('searchbox').fill('Thievul')
  await expect(page.locator('.browse-boxcell').first()).toHaveAttribute('aria-label', /^ME01 spares/)
  const labels = page.locator('.card-locations-row .position-parts')
  await expect(labels).toHaveCount(6)
  await expect(labels.nth(0)).toHaveAttribute('aria-label', 'Box 7, Section 1, Card 38')
  const before = await copyOrder(page)
  const walkBefore = await walkOrder(page)

  /* A MID-LIST ROW, AND NOT THE ONE THE WALK IS STANDING ON — which is the difference between
     a case that exercises the freeze and one that does not. `stays` keeps a row for three
     reasons and the walk's own row is answered by the FIRST of them, so retiring card 38 (where
     the walk lands) is kept whatever the freeze does. Card 39 is neither current nor optimistic.
     Measured: with the freeze deleted from `stays`, retiring 38 leaves the suite green and
     retiring 39 turns it red. */
  await copyRow(page, 'Box 7, Section 1, Card 39').getByRole('button', { name: 'Retire' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Damaged' }).click()

  await expect(
    page.locator('.card-locations-row .position-parts[aria-label="Was at Box 7, Section 1, Card 39"]'),
  ).toHaveCount(1)
  await expect(labels).toHaveCount(6)
  expect(await copyOrder(page)).toEqual([before[0], 'Was at Box 7, Section 1, Card 39', ...before.slice(2)])
  /* AND THE WALK, which folds departed rows away under `Hide sold` and is held by the same set. */
  expect(walkBefore).toEqual(['#38', '#39', '#40'])
  expect(await walkOrder(page)).toEqual(['#38', '#39', '#40'])
  /* One sentence for both doors: a retirement is a copy leaving, and the order is stale by it. */
  await expect(page.locator('.card-locations-rerank')).toContainText('Order is 1 copy stale')
})

test('a new search takes a new order, so the staleness never carries across answers', async ({ page }) => {
  const cards: Cards = { ...stackedThievul(), '2/4': card({ index: 4, at: 4, state: 'identified', name: 'Eiscue', sku: '8937371', section: 1, sectionStart: 1, sectionEnd: 3 }) }
  const store: Store = { cards, search: (query) => searchAnswer(query, cards) }
  const depart = (key: string) => {
    const held = cards[key]
    if (held === undefined) return
    const place = held.place
    cards[key] = { ...held, state: 'sold', label: place.label, place: { ...place, slot: null, card: null, fraction: null } }
    delete (cards[key] as { card?: number }).card
  }
  await open(page, STACKED_BOXES, store, () => PRICING, movesOnSale((undo) => { if (!undo) depart('7/38') }), {
    route: '/#/inventory?box=2',
    hideSold: true,
  })
  await expandAll(page)
  await page.getByRole('searchbox').fill('Thievul')
  await expect(page.locator('.card-locations-row .position-parts').nth(0)).toHaveAttribute('aria-label', 'Box 7, Section 1, Card 38')
  await copyRow(page, 'Box 7, Section 1, Card 38').getByRole('button', { name: 'Mark sold' }).click()
  await expect(page.locator('.card-locations-rerank')).toBeVisible()
  /* The re-read, waited for by the one string only it can produce — the chip lands off the
     sale's own response and says nothing about whether the store has answered yet. */
  await expect(
    page.locator('.card-locations-row .position-parts[aria-label="Was at Box 7, Section 1, Card 38"]'),
  ).toHaveCount(1)

  /* A QUERY NOBODY HAS WORKED DOWN YET HAS NOTHING TO HOLD STILL.

     THE NEW QUERY REACHES THE SAME SKU, WHICH IS WHAT MAKES THIS OBSERVABLE AT ALL. The chip
     counts the copies THIS LIST draws, so searching a different card empties it whether or not
     the freeze was released — the case passed against a build that never released it, because
     an Eiscue list holds no Thievul. `8937370` is the same group under a different string, so
     the frozen copy is still on screen and the only thing that can take the chip down is the
     release. */
  /* THE WATCHER GOES UP BEFORE THE QUESTION IS ASKED (D118, amended 2026-09-19). Every
     assertion below retries on Playwright's own interval, so all of them can settle AFTER a
     blank has happened and healed — which is how this screen shipped a copies list that
     emptied under the hand for weeks. This samples every animation frame from here until the
     order has been read, and the read at the end is of what HELD, not of what is there now. */
  await installCopiesWatch(page)
  await page.getByRole('searchbox').fill('8937370')
  /* Waited for the NEW order's own first row, not for a count: six rows is true before the
     answer lands and after it, so a count gates nothing. */
  await expect(page.locator('.card-locations-row .position-parts').nth(0)).toHaveAttribute(
    'aria-label',
    'Box 2, Section 2, Card 1',
  )
  await expect(page.locator('.card-locations-row .position-parts')).toHaveCount(6)
  await expect(page.locator('.card-locations-rerank')).toHaveCount(0)
  /* And the order is the one a fresh answer computes: box 7 is down to two live copies, which
     ties box 2 section 2, so box 2's pair leads — the reshuffle that the freeze was holding off
     and that a new search is entitled to make. */
  expect(await copyOrder(page)).toEqual([
    'Box 2, Section 2, Card 1',
    'Box 2, Section 2, Card 2',
    'Was at Box 7, Section 1, Card 38',
    'Box 7, Section 1, Card 39',
    'Box 7, Section 1, Card 40',
    'Box 2, Section 1, Card 1',
  ])
  await expectCopiesHeld(page)
})

/* SHELVED 2026-09-19, ON THE OWNER'S EXPLICIT WORD. THIS IS A STANDING STATE THE OWNER
   CHOSE, NOT AN ACCIDENT LEFT ON. THE OWNER WILL REVISIT IT, NO DATE SET.
   THE OWNER'S OWN WORDS: "Turn the guard off for now on the repo. I give you explicit
   authority."
   THE DEFECT IT WAS CATCHING, IN ONE SENTENCE: during a deliberately delayed box fetch, on a
   search-driven re-rank from box 7 to box 2, the copies panel stayed on screen but its rows
   blanked to skeleton placeholders for 14 consecutive animation frames (about 230ms) before
   recovering, so the final page reads clean and only frame sampling can see the flash.
   THE MEASUREMENT: this test and its sibling below (`a press to another drawer dims…`) failed
   6 of the last 10 completed runs on main, always the same shard, always these two tests. It
   predates the most recent merge. Full record: DEBT30.
   WHAT MUST BE TRUE TO TURN IT BACK ON: `docs/debts/030-…md` names the condition. Do not
   delete this test and do not loosen `expectCopiesHeld`'s assertion or widen a timeout to make
   it pass — either hides the finding instead of shelving it. */
test.skip(
  'the copies list holds while a new answer moves the walk to another drawer',
  {
    annotation: {
      type: 'skip',
      description:
        'Shelved 2026-09-19 on the owner\'s explicit authority. Standing state, not temporary. ' +
        'Defect: the copies panel stayed on screen but its rows blanked to skeleton for 14 ' +
        'consecutive frames (about 230ms) during a delayed re-rank across drawers. Failed 6 of ' +
        '10 recent runs on main. See DEBT30 for the measurements and the condition to turn ' +
        'this back on.',
    },
  },
  async ({ page }) => {
  /* D118's FOURTH FLOOR OVER THE SLOWEST MOMENT THIS SCREEN HAS, AND THE ORDERING IS FORCED
     RATHER THAN HOPED FOR.
     The case above asserts the same continuity on whatever ordering the machine happens to
     produce, which on a fast rig is the easy one. This one makes the hard ordering certain:
     every `GET /inventory/<box>` answers 400ms late, so when a fresh answer re-ranks the
     drawers and the walk moves from box 7 to box 2, box 2's own cards are still in flight.
     For the length of that flight `BoxBrowse`'s `visible` — one drawer's rows, narrowed to
     the shelf — holds nothing at all for the shelf the walk is now on.
     WHAT THAT USED TO DO, measured on the rig at this delay: the walk's row was not in
     `visible`, so `selectedRow` read null, `Inventory.tsx` drew no `detail`, and the copies
     column was destroyed and built again 679ms later as a skeleton — six rows to none and
     back with no press, which is the report the owner made ("for I don't know how many
     weeks"). A second tear-down rode on `.browse-card`'s `key`, which rebuilt the same column
     on every change of selection.
     400ms IS A DELAY AND NOT AN ASSERTION. It cannot make a passing build fail: what it does
     is hold open a window the product must survive, and a product that survives it survives a
     window of any length. The runner reaches the same window through CPU contention at two
     workers, three runs in twenty. */
  const cards: Cards = stackedThievul()
  const store: Store = { cards, search: (query) => searchAnswer(query, cards) }
  const depart = (key: string) => {
    const held = cards[key]
    if (held === undefined) return
    const place = held.place
    cards[key] = { ...held, state: 'sold', label: place.label, place: { ...place, slot: null, card: null, fraction: null } }
    delete (cards[key] as { card?: number }).card
  }
  await open(page, STACKED_BOXES, store, () => PRICING, movesOnSale((undo) => { if (!undo) depart('7/38') }), {
    route: '/#/inventory?box=2',
    hideSold: true,
  })
  /* Registered AFTER `open`, so it is matched first and hands the request on to `open`'s own
     stubs when the delay is over. `route.fallback()` rather than a fulfilment of its own:
     what is being changed here is WHEN the answer lands, never what is in it. */
  await page.route(/\/inventory\/\d+$/, async (route) => {
    if (route.request().method() !== 'GET') return route.fallback()
    await new Promise((resolve) => setTimeout(resolve, 400))
    return route.fallback()
  })
  await expandAll(page)
  await page.getByRole('searchbox').fill('Thievul')
  await expect(page.locator('.card-locations-row .position-parts').nth(0)).toHaveAttribute('aria-label', 'Box 7, Section 1, Card 38')
  await copyRow(page, 'Box 7, Section 1, Card 38').getByRole('button', { name: 'Mark sold' }).click()
  await expect(
    page.locator('.card-locations-row .position-parts[aria-label="Was at Box 7, Section 1, Card 38"]'),
  ).toHaveCount(1)

  await installCopiesWatch(page)
  /* The same SKU under a different string, so the answer is a new one and the drawer it leads
     with is not the drawer the walk is on. */
  await page.getByRole('searchbox').fill('8937370')
  await expect(page.locator('.card-locations-row .position-parts').nth(0)).toHaveAttribute(
    'aria-label',
    'Box 2, Section 2, Card 1',
  )
  /* THE WALK ITSELF IS WAITED FOR, not just the copies list. Box 2's rows are the last thing
     to land, and the watch has to cover the whole flight rather than stop at the answer that
     started it — reading the verdict before the rows arrive is how a guard goes green over
     the exact window it was written for. */
  await expect(page.locator(`.browse-row`)).toHaveCount(3)
  await expect(page.locator('.card-locations-row .position-parts')).toHaveCount(6)
  await expectCopiesHeld(page)
})
test.skip(
  'a press to another drawer dims its predecessor’s rows rather than drawing them as the new box’s, or drawing nothing',
  {
    annotation: {
      type: 'skip',
      description:
        'Shelved 2026-09-19 on the owner\'s explicit authority. Standing state, not temporary. ' +
        'Guards the same mechanism as its sibling above, through the shared helper ' +
        'expectCopiesHeld. Same defect, same measurement: 14 consecutive frames of blanked ' +
        'copies rows, 6 of 10 recent runs on main. See DEBT30.',
    },
  },
  async ({ page }) => {
  /* THE REGRESSION PR #404 SHIPPED, caught in review before it merged, and the OWNER'S
     RULING THAT FOLLOWED IT, 2026-09-19. The fix in the review holds the walk's row across a
     fresh SEARCH answer that re-ranks the drawers on its own — but the code it changed could
     not tell that case apart from a PRESS to a different drawer, and a manual press produces
     the identical shape: `shelf` changes, `rows` still answers for the box before it,
     `visible` reads empty for the length of the fetch. Its own fix fell straight to BLANK for
     a press: no row, no rows, no sentence, no spinner, for as long as ~1.5s on a slow store.

     PROVED LIVE (the review's own reproduction): box 2 to box 7, `/inventory/7` delayed
     1500ms. The box header said Box 7. The walk list said "Nothing in box 7 yet" — false,
     it holds three cards. The detail column still drew box 2's Thievul, with `CardOps` live
     against it. An operator acting on that panel would sell or retire box 2's card while
     believing they stood in box 7.

     THE OWNER'S WORD ON THE BLANK ITSELF: keep the previous drawer's rows on screen, DIMMED,
     until the new answer lands — in both the walk list and the copies column. Dimmed is not
     a smaller version of the a4f3594b claim: `aria-busy` and `pointer-events: none`
     (BoxBrowse.css) say the content is a TRANSITION, and block every click a press could
     land on a card that is no longer where the header says it is.

     THIS CASE FORCES THAT ORDERING RATHER THAN HOPING FOR IT: `/inventory/7` is delayed, and
     every assertion below runs in the window the delay holds open, before waiting on the
     answer. `shelfSource` (BoxBrowse.tsx, beside `shelfAnswered`) is what tells this press
     apart from D132's own re-rank — only a fresh search answer may hold the outgoing row as
     the LIVE answer; a press or a walk-to holds it DIMMED instead, through `held`/
     `heldSections`/`heldDetail`, same as before the D118 fix existed except never blank. */
  const cards: Cards = stackedThievul()
  const store: Store = { cards, search: (query) => searchAnswer(query, cards) }
  await open(page, STACKED_BOXES, store, () => PRICING, SALE, {
    route: '/#/inventory?box=2',
  })
  await expect(page.locator('.browse-boxcell[aria-current="true"]')).toHaveAttribute('aria-label', /^Box 2/)
  await expect(page.locator('.browse-card')).toContainText('Thievul')
  const rowsBefore = await page.locator('.browse-row').count()
  /* THE LIST'S OWN HEIGHT, not its viewport top — box 7 carries a name box 2 does not
     (`stackedThievul` below: "ME01 spares"), so the HEADER above the list is a real
     content difference and the list's absolute position moves for a reason unrelated to
     this fix. Height is the fair measure: both boxes hold three rows, so a `.browse-list`
     that never collapsed reads the same height throughout, held or landed. */
  const listHeightBefore = await page.locator('.browse-list').first().evaluate((node) => node.getBoundingClientRect().height)

  /* Registered AFTER `open`, matched first, and narrowed to box 7 alone — box 2's own
     fetches (the initial load) are not slowed, only the box the press moves to. 800ms
     gives the one-shot snapshot below comfortable room over CI's own latency. */
  await page.route(/\/inventory\/7$/, async (route) => {
    if (route.request().method() !== 'GET') return route.fallback()
    await new Promise((resolve) => setTimeout(resolve, 800))
    return route.fallback()
  })

  await page.locator('.browse-boxcell[aria-label^="Box 7"]').click()

  /* THE WINDOW: box 7's own rows have not landed. A RETRYING `expect(locator)` CANNOT SEE
     IT — every one of them polls until it is true (or times out) and would happily settle
     AFTER the 800ms delay clears and the false state has healed on its own, which is
     precisely how this shipped once already (D118's frame-watch note applies just as much
     here). This reads the whole subject in ONE synchronous in-page snapshot instead, taken
     right after the click and before anything awaits the network. */
  const snap = await page.evaluate(() => {
    const list = document.querySelector('.browse-list')
    const card = document.querySelector('.browse-card') as (HTMLElement & { inert: boolean }) | null
    /* REVIEW OF PR #407, FINDING 1 (HIGH): `pointer-events: none` blocks the mouse alone.
       Tab still reached CardOps' "Card actions" button and Enter opened its menu on
       `held.current` — box 2's card, live, under the Box 7 header — the a4f3594b
       regression again, by keyboard. `inert` (BoxBrowse.tsx) is meant to remove the whole
       dimmed section from the tab order AND refuse activation. Proved here by calling
       `.focus()` on the button directly: an `inert` subtree refuses that call by spec, so
       `document.activeElement` stays put and this reads false. A real Tab walk would prove
       the same fact more slowly and no more certainly — `inert` governs both paths by one
       mechanism. */
    const cardActionsBtn = card === null
      ? null
      : [...card.querySelectorAll('button')].find((b) => b.textContent?.trim() === 'Card actions') ?? null
    const before = document.activeElement
    cardActionsBtn?.focus()
    const cardActionsFocused = cardActionsBtn !== null && document.activeElement === cardActionsBtn
    if (document.activeElement !== before && document.activeElement instanceof HTMLElement) {
      document.activeElement.blur()
    }
    return {
      current: document.querySelector('.browse-boxcell[aria-current="true"]')?.getAttribute('aria-label') ?? null,
      /* `.browse-card` is now HELD DIMMED rather than absent — box 2's rows are still ITS
         own, drawn under the same aria-busy/opacity contract as the list below, never as a
         claim that they are box 7's. Both spellings of the false sentence must still be
         absent: dimmed is a transition, not a claim either. */
      cardCount: document.querySelectorAll('.browse-card').length,
      cardAriaBusy: card?.getAttribute('aria-busy') ?? null,
      cardOpacity: card === null ? null : Number.parseFloat(getComputedStyle(card).opacity),
      cardPointerEvents: card === null ? null : getComputedStyle(card).pointerEvents,
      cardInert: card === null ? null : card.inert,
      cardActionsPresent: cardActionsBtn !== null,
      cardActionsFocusable: cardActionsFocused,
      /* Box 2's own photograph is still drawn (held, dimmed) — it is what proves the
         panel is showing the PREVIOUS drawer's card rather than nothing, and the
         aria-busy/opacity pair above is what proves it is marked as stale rather than
         claimed as box 7's. */
      box2Photo: document.querySelectorAll('img[alt*="Box 2 ·"]').length,
      /* REVIEW OF PR #407, FINDING 2 (MEDIUM): `panelDetail` must still be the HELD
         `{detail}` — `Inventory.tsx`'s `CopiesPanel` — not the live one (which is `null`
         while `dimPanel`, drawing nothing) and not some invented stand-in. `.browse-under`
         is `{panelDetail}`'s own wrapper; `.card-locations-owner` is `CopiesPanel`'s own
         top-level class (CardLocations.tsx) and `.card-locations-row` is one row of real
         copy data, so both counts prove the copies column is drawing REAL, HELD content,
         not an empty div. */
      underOwnerCount: document.querySelectorAll('.browse-under .card-locations-owner').length,
      underRowCount: document.querySelectorAll('.browse-under .card-locations-row').length,
      rowCount: document.querySelectorAll('.browse-row').length,
      listAriaBusy: list?.getAttribute('aria-busy') ?? null,
      listOpacity: list === null ? null : Number.parseFloat(getComputedStyle(list).opacity),
      listPointerEvents: list === null ? null : getComputedStyle(list).pointerEvents,
      listTabIndex: list === null ? null : list.getAttribute('tabindex'),
      /* THE LIST'S OWN HEIGHT, not its viewport top (see `listHeightBefore` above): held,
         it is drawing the SAME three rows it drew before the press, so a list that never
         collapsed reads the same height here as it did then. */
      listHeight: list === null ? null : list.getBoundingClientRect().height,
      falseClaim: document.body.innerText.includes('Nothing in box 7 yet') || document.body.innerText.includes('Nothing in Box 7 yet'),
      emptyCount: document.querySelectorAll('.browse-empty').length,
    }
  })
  expect(snap.current, 'box-cell aria-current').toMatch(/^Box 7/)
  expect(snap.cardCount, '.browse-card count').toBe(1)
  expect(snap.cardAriaBusy, '.browse-card aria-busy').toBe('true')
  expect(snap.cardOpacity, '.browse-card computed opacity').toBeLessThan(1)
  expect(snap.cardPointerEvents, '.browse-card computed pointer-events').toBe('none')
  expect(snap.cardInert, '.browse-card is inert while dimmed').toBe(true)
  expect(snap.cardActionsPresent, '"Card actions" button exists in the dimmed panel').toBe(true)
  expect(snap.cardActionsFocusable, '"Card actions" is NOT focusable while the panel is inert').toBe(false)
  expect(snap.box2Photo, "box 2's photo alt count, held dimmed").toBe(1)
  expect(snap.underOwnerCount, '.browse-under draws the held CopiesPanel, not nothing').toBe(1)
  expect(snap.underRowCount, '.browse-under draws real held copy rows, not an empty panel').toBeGreaterThan(0)
  expect(snap.rowCount, '.browse-row count, held dimmed').toBe(rowsBefore)
  expect(snap.listAriaBusy, '.browse-list aria-busy').toBe('true')
  expect(snap.listOpacity, '.browse-list computed opacity').toBeLessThan(1)
  expect(snap.listPointerEvents, '.browse-list computed pointer-events').toBe('none')
  expect(snap.listTabIndex, '.browse-list tabindex, out of the tab order while dimmed').toBe('-1')
  expect(snap.listHeight, "the list's own height, held, D118: nothing collapsed").toBe(listHeightBefore)
  expect(snap.falseClaim, '"Nothing in box 7 yet" shown before the answer').toBe(false)
  expect(snap.emptyCount, '.browse-empty count').toBe(0)

  /* AND ONCE THE ANSWER LANDS: the honest state, box 7's own three rows, and the walk
     settling on one of them — never a false claim, never a stale card. Its own height is
     NOT compared against `listHeightBefore` here: box 7 groups its three cards into one
     section where box 2 groups its three into two (`stackedThievul` above), so the two
     boxes' lists are never the same height by content alone. The held-vs-before compare
     above is the one that isolates the fix — same box, same content, before the press and
     during the wait — and it is the one D118's "nothing collapsed" claim is about. */
  await expect(page.locator('.browse-row')).toHaveCount(3)
  await expect(page.locator('.browse-card')).toBeVisible()
  await expect(page.locator('.browse-card')).toContainText('Thievul')
  await expect(page.locator('.browse-card')).not.toHaveAttribute('aria-busy', 'true')
  await expect(page.locator('.browse-list')).not.toHaveAttribute('aria-busy', 'true')
  await expect(page.locator('.browse-boxcell[aria-current="true"]')).toHaveAttribute('aria-label', /^Box 7/)
})

test('a box whose last live match departs keeps the walk, rather than handing it to another box', async ({ page }) => {
  /* THE SHELF POOL, which is the third thing D132's rule ranks and the one a sale can empty.
     `holdsLive` drops a box from the pool the moment it holds no LIVE match of the answer, and
     the walk then lands on the first box that does — so selling box 2's only Thievul used to
     move the operator to box 7 mid-press. One live match in box 2 is what makes that reachable;
     with three, the box never empties and the pool never changes. */
  const thievul = (index: number, at: number, section: number, start: number, end: number, box = 2) =>
    card({ index, at, state: 'identified', name: 'Thievul', sku: '8937370', section, sectionStart: start, sectionEnd: end, box, boxName: box === 7 ? 'ME01 spares' : undefined, boxTotal: box === 7 ? 40 : 5 })
  const cards: Cards = {
    '2/1': thievul(1, 1, 1, 1, 3),
    '7/38': thievul(38, 38, 1, 1, 40, 7),
    '7/39': thievul(39, 39, 1, 1, 40, 7),
    '7/40': thievul(40, 40, 1, 1, 40, 7),
  }
  const store: Store = { cards, search: (query) => searchAnswer(query, cards) }
  const depart = (key: string) => {
    const held = cards[key]
    if (held === undefined) return
    const place = held.place
    cards[key] = { ...held, state: 'sold', label: place.label, place: { ...place, slot: null, card: null, fraction: null } }
    delete (cards[key] as { card?: number }).card
  }
  await open(page, STACKED_BOXES, store, () => PRICING, movesOnSale((undo) => { if (!undo) depart('2/1') }), {
    route: '/#/inventory?box=2',
    hideSold: true,
  })
  await page.getByRole('searchbox').fill('Thievul')
  /* The fresh answer lands on box 7, which holds the most. Press box 2 to stand there. */
  await expect(page.locator('.browse-boxcell[aria-current="true"]')).toHaveAttribute('aria-label', /^ME01 spares/)
  await page.locator('.browse-boxcell[aria-label^="ME01 commons"]').click()
  await expect(page.locator('.browse-boxcell[aria-current="true"]')).toHaveAttribute('aria-label', /^ME01 commons/)

  await copyRow(page, 'Box 2, Section 1, Card 1').getByRole('button', { name: 'Mark sold' }).click()
  await expect(
    page.locator('.card-locations-row .position-parts[aria-label="Was at Box 2, Section 1, Card 1"]'),
  ).toHaveCount(1)

  /* STILL STANDING IN BOX 2. Without the freeze the box holds no live match any more, drops out
     of the pool, and the walk is handed to box 7 — a whole screen changing under the press. */
  await expect(page.locator('.browse-boxcell[aria-current="true"]')).toHaveAttribute('aria-label', /^ME01 commons/)
})

test('undoing the sale takes the staleness back with it', async ({ page }) => {
  const { store, depart } = stackedStore()
  const back = (key: string) => {
    const held = store.cards[key]
    if (held !== undefined) held.state = 'identified'
  }
  await open(page, STACKED_BOXES, store, () => PRICING, movesOnSale((undo) => (undo ? back('7/38') : depart('7/38'))), {
    route: '/#/inventory?box=2',
    hideSold: true,
  })
  await expandAll(page)
  await page.getByRole('searchbox').fill('Thievul')
  await expect(page.locator('.card-locations-row .position-parts').nth(0)).toHaveAttribute('aria-label', 'Box 7, Section 1, Card 38')

  await copyRow(page, 'Box 7, Section 1, Card 38').getByRole('button', { name: 'Mark sold' }).click()
  await expect(page.locator('.card-locations-rerank')).toContainText('Order is 1 copy stale')

  /* NOTHING LEFT THE BOX AFTER ALL, so there is nothing for a re-rank to recompute — a
     staleness figure that survived an undo would be offering to re-rank a store that never
     moved. */
  await page.locator('.inventory-receipt').getByRole('button', { name: 'Undo' }).click()

  /* THE RECEIPT GOES FIRST, which is what says the reversal was answered rather than merely
     dispatched. */
  await expect(page.locator('.inventory-receipt')).toHaveCount(0)

  /* AND THE HEADER IS ASSERTED PRESENT BEFORE THE CHIP IS ASSERTED ABSENT. The undo triggers a
     re-read and the copies list draws a skeleton with no header at all while that is in flight,
     so a bare `toHaveCount(0)` on the chip is satisfied by a frame in which NOTHING is drawn —
     it passes against a build that never releases the hold. The title renders only when the
     group does, so the pair can only be satisfied by a settled panel with no chip in it. */
  await expect(page.locator('.card-locations-title')).toBeVisible()
  await expect(page.locator('.card-locations-row')).toHaveCount(6)

  /* PROMPTLY, WHICH IS THE WHOLE OF WHAT THIS CASE ADDS. The chip has to be gone on the frame
     the undo lands, not eventually: with the release deleted the panel still settles without it
     inside the default fifteen seconds — measured by dumping the header, which showed the chip
     present at this point and absent by the time a default assertion gave up waiting. So the
     window is the assertion. */
  await expect(page.locator('.card-locations-rerank')).toHaveCount(0, { timeout: 2000 })
})

test('the control that re-ranks reserves its own room, so appearing moves no copy row', async ({ page }) => {
  /* D118 ON THE NEW CONTROL. It appears on the press that makes the order stale, inside a band
     whose height is fixed — so an unreserved slot sends every copy row down by the chip's
     height at the exact moment of the sale, which is the movement this whole change exists to
     stop. Measured on the FIRST ROW's own top edge, inside the scroller. */
  const { store, depart } = stackedStore()
  await open(page, STACKED_BOXES, store, () => PRICING, movesOnSale((undo) => { if (!undo) depart('7/38') }), {
    route: '/#/inventory?box=2',
    hideSold: true,
  })
  await expandAll(page)
  await page.getByRole('searchbox').fill('Thievul')
  const rows = page.locator('.card-locations-row')
  await expect(rows).toHaveCount(6)
  await expect(page.locator('.card-locations-rerank')).toHaveCount(0)
  /* BOXBROWSE'S OWN RAIL SEARCH IS A SEPARATE `useSearch()` FROM THE COPIES LIST'S, and the
     count above proves only the second one has settled. Waiting on it alone races the first:
     it can still be mid-debounce when the press below fires, and its FIRST real answer — which
     lands after the press purely by bad luck — is read as a re-rank the freeze failed to hold.
     It is not: D132's "a fresh answer goes to the fullest box" is correct for a landing that
     has never happened yet, and the box here is genuinely landing for the first time. Waiting
     for the rail to name box 7 is what the sibling cases already do, and this one had dropped
     it. Reproduced without this wait: the press lands before `filtered` ever turns true, the
     shelf's very first fresh landing coincides with the post-sale re-read, and the walk jumps
     box 2 -> box 7 — a real DOM remount, not a probe artifact, traced with a MutationObserver
     and confirmed line-by-line against the shelf effect's own state. */
  await expect(page.locator('.browse-boxcell').first()).toHaveAttribute('aria-label', /^ME01 spares/)

  /* `offsetTop` AND NOT A BOUNDING BOX, which is D118's own recorded trap one register over:
     Playwright scrolls a control into view before it clicks it, and this list is the thing that
     scrolls inside `.browse-band`. Viewport coordinates would report the SCROLL as movement and
     say nothing about the header — measured at 535px before the press and 390px after, on a
     build where the list itself had not moved at all. The offset within the scrolled content
     is the number the reservation is about.

     THE PROBE DISTINGUISHES "NOTHING IS KNOWN YET" FROM "NOTHING IS WRONG", and does so by
     POLLING rather than by sampling once. A single read that returns a sentinel on a missing
     node was this case's first defect: `-1` compared against a real measurement produced a
     message that read as a layout regression and sent the reader to the CSS. The second
     defect, found chasing the first: `.card-locations-owner` and `.card-locations-rows`
     genuinely are ABSENT for a frame or two as an ordinary part of this screen settling —
     traced with a mount/unmount log on `CardLocations` itself, and it happens on the INITIAL
     load, before any press, as many times as it happens after one. Nothing here is specific to
     a sale; this component's own lifecycle is not the claim this case exists to prove. So the
     read retries — `expect.poll`, the same tool Playwright hands you for "eventually true" —
     until both nodes are present, and only THEN takes the measurement this case is actually
     about. A press that genuinely left the panel gone still fails, past the poll's window,
     with the same detail a single throw would have given. */
  const listTop = async (): Promise<number> => {
    let last: number | null = null
    await expect
      .poll(
        async () => {
          last = await page.evaluate(() => {
            const list = document.querySelector('.card-locations-rows')
            const panel = document.querySelector('.card-locations-owner')
            if (list === null || panel === null) return null
            /* The HEADER's height, read as the gap between the panel's own top and the first
               row — two rects taken in the same frame, so the scroll cancels and no
               offsetParent is assumed. `offsetTop` was the first build and moved 535 -> 637 on
               a press that changed nothing about the header, because the scroller it is
               measured from is not the panel. */
            return Math.round(list.getBoundingClientRect().top - panel.getBoundingClientRect().top)
          })
          return last
        },
        {
          message: '.card-locations-rows and .card-locations-owner never settled together',
          intervals: [50, 100, 100],
          timeout: 3000,
        },
      )
      .not.toBeNull()
    // The poll above only resolves once `last` is non-null, so this cast is the assertion's
    // own guarantee, not a hope.
    return last as unknown as number
  }
  const before = await listTop()
  expect(before).toBeGreaterThan(0)

  await copyRow(page, 'Box 7, Section 1, Card 38').getByRole('button', { name: 'Mark sold' }).click()
  await expect(page.locator('.card-locations-rerank')).toBeVisible()
  const after = await listTop()
  expect(after).toBe(before)
})

test('the re-rank control clears the thumb floor on a phone', async ({ page }) => {
  /* D117's floor, on a control that did not exist when it was written: 40px under 767px, met by
     `--bn-control-h-sm` in the token file rather than by a number in `CardLocations.css`. */
  await page.setViewportSize({ width: 390, height: 844 })
  const { store, depart } = stackedStore()
  /* `settle` because a phone draws the walk inside a drawer and `open`'s default wait is a
     section fold, which is not on screen here — waiting for it would fail on the arrangement
     rather than on the claim.

     AND NO SEARCH, WHICH IS NOT A SHORTCUT. Below 768 the searchbox lives in the rail DRAWER
     and is not on screen until the drawer is opened, so typing into it here times out on the
     shell rather than on this control. It is also not needed: the copies list runs its own
     query off the selected card's SKU, so the sale makes the order stale exactly as it does at
     1440 and the chip is drawn the same way. */
  await open(page, STACKED_BOXES, store, () => PRICING, movesOnSale((undo) => { if (!undo) depart('7/38') }), {
    route: '/#/inventory?box=2',
    hideSold: true,
    settle: '.card-locations-owner',
  })
  await copyRow(page, 'Box 7, Section 1, Card 38').getByRole('button', { name: 'Mark sold' }).click()
  const chip = page.locator('.card-locations-rerank')
  await expect(chip).toBeVisible()
  const box = await chip.boundingBox()
  expect(box?.height ?? 0).toBeGreaterThanOrEqual(40)
})

/* ----------------------------------------------------------------------------------- D218 */

test('D218: this lane\'s own facts draw the separator, never type it', async ({ page }) => {
  /* A typed `·` (U+00B7) or `•` (U+2022) is a separator baked into a string; D218's rule is
     that a screen may only SHOW one, drawn by CSS beside a fact that is its own element
     (`.bn-facts` in `app/src/kit.css`) — never type one into text a component holds.

     SCOPED TO WHAT THIS LANE (`BoxOps.tsx`, `BoxBrowse.tsx`, `Inventory.tsx`, `BoxRuns.tsx`,
     `CardHero.tsx`) DRAWS, never the whole `.bn-view`: this route's own `.position-bar-text`
     (`PositionBar.tsx`, D41's accessible-name territory, a different file this sweep does not
     touch) still types one today, so a blanket assertion cannot pass until every lane on this
     route has landed. `.bn-filtercount` is the rail's store-wide count line (BoxBrowse.tsx);
     `.boxops-sheet` is the Manage sheet in full, including the Name-sections editor's example
     text and its own per-section Field labels (BoxOps.tsx) — both self-contained to this
     lane's components. */
  await open(page)

  /* The header's census pill is gone (the rail's count line says the boxes); that line is
     this lane's store-wide figure now. */
  const census = page.locator('.browse-filterbar .bn-filtercount')
  await expect(census).toBeVisible()
  expect(await census.innerText()).not.toMatch(/[·•]/)

  await openBoxOps(page)
  await page.getByRole('button', { name: /^Name sections/ }).click()
  const sheet = page.locator('.boxops-sheet')
  expect(await sheet.innerText()).not.toMatch(/[·•]/)
})

