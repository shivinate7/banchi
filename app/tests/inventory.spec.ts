import { test, expect, type Page } from '@playwright/test'

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
function card(input: {
  index: number
  state: string
  name: string | null
  sku: string | null
  section: number
  sectionStart: number
  sectionEnd: number
  captureId?: string | null
  /** D3 rung 1's finish claim as it comes off `inventory.json`. Defaults to the BARE STRING
   *  every record written before the amendment of 2026-08-23 carries — `_card_row` ships
   *  `asdict(card)` raw, so both shapes really do arrive here and the default is the one
   *  the store is mostly still full of. A row that passes a list is the new shape. */
  finish?: string | string[] | null
}) {
  const box = 2

  /* `card` IS THE SLOT INSIDE THE SECTION AND `index` IS THE BOX-WIDE ALLOCATOR NUMBER, which
     is what the server sends and what this fixture used to conflate — it set `card: index`, so
     card 4 arrived as `Section 2 · Card 4` of a section that starts at 4. The two agree for the
     first section of a box and diverge after it (types.ts states exactly that on `Place.index`),
     and a fixture that never diverged could not tell a right answer from a wrong one for
     anything reading `card`. Checked against the live store: index 26 of box 1 comes back as
     `Section 2 · Card 1`, section_start 26. */
  const slot = input.index - input.sectionStart + 1

  return {
    box,
    index: input.index,
    label: `Box ${box} · Section ${input.section} · Card ${slot}`,
    section: input.section,
    card: slot,
    place: {
      located: true,
      label: `Box ${box} · Section ${input.section} · Card ${slot}`,
      box,
      index: input.index,
      section: input.section,
      card: slot,
      box_name: 'ME01 commons',
      section_start: input.sectionStart,
      section_end: input.sectionEnd,
      box_total: 5,
      box_closed: false,
      fraction: input.index / 5,
      neighbors: null,
      gaps_in_section: 0,
    },
    photo: `photos/${box}/${input.index}.jpg`,
    set_hint: 'ME01',
    metadata_finish: input.finish === undefined ? 'normal' : input.finish,
    game: 'pokemon',
    rarity_claim: null,
    note: null,
    captured_at: '2026-08-22T12:34:00+00:00',
    capture_id: input.captureId === undefined ? `cap-${input.index}` : input.captureId,
    name: input.name,
    number: input.name === null ? null : '090',
    printed_total: input.name === null ? null : '132',
    confidence: null,
    sku: input.sku,
    condition: input.sku === null ? null : 'Near Mint',
    state: input.state,
    state_at: '2026-08-22T12:34:00+00:00',
    retire_reason: null,
    run: null,
  }
}

/* FIVE CARDS ACROSS TWO SECTIONS, chosen so that every branch this screen draws has a row.
 *
 *   1, 3   one SKU, two copies — D7's map, and the two doors out of inventory on each
 *   2      captured, no name and no SKU — the 22% of the store the search cannot reach, and
 *          the case the lone-copy fallback exists for
 *   4      sold, 5 retired — the terminal states, which draw a word instead of the controls
 *          and which the mid-box delete must not offer itself on
 */
const CARDS = {
  '2/1': card({ index: 1, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3 }),
  '2/2': card({ index: 2, state: 'captured', name: null, sku: null, section: 1, sectionStart: 1, sectionEnd: 3, finish: ['normal', 'reverse_holo'] }),
  '2/3': card({ index: 3, state: 'identified', name: 'Thievul', sku: '8937370', section: 1, sectionStart: 1, sectionEnd: 3 }),
  '2/4': card({ index: 4, state: 'sold', name: 'Eiscue', sku: '8937371', section: 2, sectionStart: 4, sectionEnd: 5 }),
  '2/5': card({ index: 5, state: 'retired', name: 'Pyroar', sku: '8937372', section: 2, sectionStart: 4, sectionEnd: 5 }),
}

const BOXES = {
  boxes: [
    {
      box: 2,
      name: 'ME01 commons',
      sections: [1, 4],
      state: 'open',
      capacity: null,
      fill: 5,
      next_index: 6,
      cards: 5,
      sold: 1,
      sections_detail: [
        { section: 1, start: 1, end: 3, count: 3 },
        { section: 2, start: 4, end: 5, count: 2 },
      ],
    },
  ],
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
  ],
}

/** The per-SKU facts `GET /search` reports beside the copies. Only the two-copy SKU carries
 *  interesting numbers; the other two exist so that selecting a card in the SECOND section
 *  reaches a real group and therefore draws a real position bar. */
const LISTED: Record<string, { listed: { pushed: number; staged: number; live: number }; on_hand: number }> = {
  '8937370': { listed: { pushed: 0, staged: 2, live: 1 }, on_hand: 2 },
  '8937371': { listed: { pushed: 0, staged: 0, live: 0 }, on_hand: 0 },
  '8937372': { listed: { pushed: 0, staged: 0, live: 0 }, on_hand: 0 },
}

/** Which store keys a query reaches, in the shape `do_search` matches with: the SKU, the name,
 *  or the set hint — three of the six fields the real matcher reads.
 *
 *  THE SET-HINT CASE IS WHY THIS STOPPED BEING TWO HARD-CODED KEYS. Every card in this fixture
 *  carries `ME01`, so that one query reaches copies in BOTH sections — which is the only shape
 *  that can test the owner's ask that a search make every match immediately findable. A query
 *  matching one section proves nothing about a match folded away in the other. */
function keysFor(query: string): string[] {
  const asked = query.trim().toLowerCase()
  if (asked === '') return []
  return Object.entries(CARDS)
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
function searchAnswer(query: string) {
  const reached = new Set(keysFor(query))
  const skus = [
    ...new Set(
      [...reached]
        .map((key) => CARDS[key as keyof typeof CARDS].sku)
        .filter((sku): sku is string => sku !== null),
    ),
  ]

  const copiesOf = (sku: string) =>
    Object.entries(CARDS)
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
      return {
        sku,
        names: [
          ...new Set(
            Object.values(CARDS)
              .filter((held) => held.sku === sku && held.name !== null)
              .map((held) => held.name as string),
          ),
        ],
        number: '090',
        printed_total: '132',
        set_hint: 'ME01',
        condition: 'Near Mint',
        ...(LISTED[sku] ?? { listed: { pushed: 0, staged: 0, live: 0 }, on_hand: 0 }),
        cap: 4,
        copies,
      }
    }),
  }
}

/** Stub the whole server and open the screen. Every route the view calls is intercepted; a
 *  request that reaches none of them would fail at the fetch, which is itself the assertion
 *  that this screen talks to the routes it claims to. */
async function open(page: Page): Promise<Wire[]> {
  const wire: Wire[] = []

  const record = (method: string, url: string, body: unknown) =>
    wire.push({ method, path: new URL(url).pathname, body })

  /* The writes first: the read regexes below are looser and a `/inventory` matcher would
     swallow `/inventory/2` if it were registered ahead of it. */
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

  await page.route(/\/inventory\/\d+$/, async (route) => {
    const request = route.request()
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
      body: JSON.stringify(searchAnswer(asked)),
    })
  })

  await page.route(/\/games$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(GAMES) })
  })

  await page.route(/\/boxes$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(BOXES) })
  })

  await page.route(/\/inventory$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 2, cards: CARDS, boxes: {}, listings: {} }),
    })
  })

  await page.route(/\/photo\/\d+\/\d+/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'image/svg+xml', body: PHOTO_SVG })
  })

  await page.goto(VIEW_ROUTE)
  await expect(page.locator(VIEW)).toBeVisible()
  /* THE SECTION HEADERS AND NOT A CARD ROW, because the walk arrives fully collapsed since
     2026-08-23 and there are no card rows until something asks for them. A header is the
     stronger wait anyway: it proves the inventory read landed AND that the walk grouped it,
     where a row only proves the first. */
  await expect(page.locator('.browse-sectfold').first()).toBeVisible()
  return wire
}

/** Open every section of the box being walked.
 *
 *  THE COLLAPSED DEFAULT'S COST, STATED IN A HELPER rather than smuggled into `open`. Exactly
 *  the shape `openBoxOps` above takes and for the same reason: a test that wants card rows says
 *  so, and the fold tests below can still assert the state every other test starts from. */
async function expandAll(page: Page) {
  await page.getByRole('button', { name: 'expand all' }).click()
  await expect(page.locator('.browse-row').first()).toBeVisible()
}

/** Open the box header's disclosure, where every box operation lives.
 *
 *  IT IS SHUT BY DEFAULT AND THAT IS THE MEASURED CHOICE `BoxOps.tsx` ARGUES: on the old
 *  `#/boxes` this panel drew every box at once at 304-355px each, so four boxes cost 1744px of
 *  scroll to say four things. What is always visible is the reading — number, name, lid, fill,
 *  track — and the operations are one press beneath it. Every test that presses a box control
 *  therefore presses this first, which is also the honest cost of the fold stated in a helper. */
async function openBoxOps(page: Page) {
  await page.locator('.boxops-more-head').click()
  await expect(page.getByRole('button', { name: 'Rename' })).toBeVisible()
}

// ------------------------------------------------------- one screen, not two modes (D31)

test('the walk is the screen — there is no mode switch to be on the wrong side of', async ({
  page,
}) => {
  await open(page)

  /* The owner's correction, asserted rather than remembered: "i imagined moreso in this merge
     that these wouldn't be two tabs, instead it's basically find a card in a box-based system
     if anything". The switch is gone and the box spine is what is left. */
  await expect(page.locator('.inventory-modes')).toHaveCount(0)
  await expect(page.locator('.browse-boxline')).toBeVisible()
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

  // The cap comes off the wire (SearchGroup.cap), which is what settled this screen's refusal
  // to write `of 4` in TypeScript.
  await expect(page.locator('.card-locations-listed')).toHaveText('listed 1 of 4')
})

test('a card with no name and no SKU still offers both doors', async ({ page }) => {
  await open(page)

  // Card 2 — captured, never identified. `GET /search` cannot reach it, so no group is invented
  // and no group numbers are drawn; one copy and its two controls.
  await expandAll(page)
  await page.locator('.browse-row', { hasText: 'captured' }).first().click()
  await expect(page.locator('.inventory-lone')).toBeVisible()
  await expect(page.locator('.card-locations-owner')).toHaveCount(0)
  await expect(page.locator('.inventory-lone').getByRole('button', { name: 'Mark sold' })).toBeVisible()
  await expect(page.locator('.inventory-lone').getByRole('button', { name: 'Retire' })).toBeVisible()
})

// ------------------------------------------------------------------- collapsible sections

test('the walk arrives fully collapsed, the planted selection included', async ({ page }) => {
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
  await expect(folds.nth(0)).toHaveAttribute('aria-expanded', 'false')
  await expect(folds.nth(1)).toHaveAttribute('aria-expanded', 'false')
  await expect(page.locator('.browse-row')).toHaveCount(0)

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

test('expand all opens every section and collapse all shuts them', async ({ page }) => {
  await open(page)

  await page.getByRole('button', { name: 'expand all' }).click()
  await expect(page.locator('.browse-row')).toHaveCount(5)

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
  await expect(page.locator('.browse-row')).toHaveCount(5)
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
  // Four matches — card 2 carries no SKU, so it is in no group — every one on screen, no press.
  await expect(page.locator('.browse-row')).toHaveCount(4)

  /* AND THE EXPANSION BELONGS TO THE QUERY. Cleared, the walk is back to the state it opens in
     rather than a half-open shape nobody chose — one resting state to learn instead of two. */
  await page.locator('.search-field-input').fill('')
  await expect(page.locator('.browse-row')).toHaveCount(0)
})

test('moving the selection opens the section it lands in, so the mark is never hidden', async ({
  page,
}) => {
  await open(page)

  /* The other half of the fold fix. With everything shut, a key that moves the selection has
   * to open whatever it lands in — otherwise collapsed-by-default would let the walk put the
   * mark on a row nobody can see, which is the failure the old render-time override was
   * written to prevent and the one thing that must survive its removal. */
  await page.getByRole('button', { name: 'expand all' }).click()
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
  const bars = page.locator('.card-locations-owner .position-bar')
  await expect(bars).toHaveCount(2)

  const first = bars.nth(0).locator('.position-bar-text')
  await expect(first.nth(0)).toHaveText('#1 of 5 so far')
  /* SETTLED SECTION, SO THE DENOMINATOR IS SLOTS. Section 1 runs 1..3 and the box holds 5, so
     its far bound is a divider with cards behind it: three slots today and three next week. */
  await expect(first.nth(1)).toHaveText('Section 1 · card 1 of 3 slots')

  const second = bars.nth(1).locator('.position-bar-text')
  await expect(second.nth(0)).toHaveText('#3 of 5 so far')
  await expect(second.nth(1)).toHaveText('Section 1 · card 3 of 3 slots')

  /* The section track carries no dividers of its own — a section is not divided by anything,
     and that absence is one of the three cues telling the two scales apart at a glance. */
  await expect(bars.nth(0).locator('.position-bar-sectiontrack .position-bar-segment')).toHaveCount(0)
})

test('the last section of an open box counts what is in it, and says so far', async ({ page }) => {
  await open(page)
  await expandAll(page)
  await page.locator('.browse-row', { hasText: 'Pyroar' }).click()

  /* THE OTHER DENOMINATOR, AND IT IS D20 AT SECTION SCALE. Section 2 is declared 4..5 in a box
   * that holds 5 and is not sealed, so its far bound is the end of an open box: it is where the
   * next capture lands and it will be wider tomorrow. Measured against its fill so far and
   * labelled `so far` — the same word, for the same reason, as the box line above it, because a
   * denominator that is different tomorrow is worse than no denominator.
   *
   * The pair also shows why both scales are wanted: the box line puts this card at the very
   * back of the box and the section line puts it at the back of a two-card section. */
  const bar = page.locator('.card-locations-owner .position-bar').first()
  await expect(bar.locator('.position-bar-text').nth(0)).toHaveText('#5 of 5 so far')
  await expect(bar.locator('.position-bar-text').nth(1)).toHaveText('Section 2 · card 2 of 2 so far')

  /* One accessible name carrying both, because `role="img"` hides every descendant — a screen
     reader is told the second scale here or not at all. */
  await expect(bar).toHaveAttribute('aria-label', '#5 of 5 so far · Section 2 · card 2 of 2 so far')
})

test('the card with no group gets both depths too — it is most of the store', async ({ page }) => {
  await open(page)
  await expandAll(page)
  await page.locator('.browse-row', { hasText: 'captured' }).first().click()

  /* THE BRANCH THAT NEARLY MISSED OUT, and the numbers are why it must not. On the Mac this was
   * built against, 629 of 682 records are captured-and-never-identified — 92% — so `GET /search`
   * cannot reach them and every one of them draws through the lone-copy fallback rather than
   * through a group. Both bars only in `CardLocations` would have answered "how far into the
   * section" for the 8% of the store that has been through the pipeline, and for none of the
   * boxes actually sitting on the desk. */
  const bar = page.locator('.inventory-lone .position-bar')
  await expect(bar).toHaveCount(1)
  await expect(bar.locator('.position-bar-text').nth(0)).toHaveText('#2 of 5 so far')
  await expect(bar.locator('.position-bar-text').nth(1)).toHaveText('Section 1 · card 2 of 3 slots')
})

// ------------------------------------------------------------------------- the mass-select

test('ticking rows narrows what a box-wide claim will reach, and says so on the button', async ({
  page,
}) => {
  await open(page)
  await openBoxOps(page)
  await expandAll(page)

  const claims = page.getByRole('button', { name: /^Set claims on/ })
  await expect(claims).toHaveText('Set claims on all 5 cards in box 2')

  await page.locator('.browse-rowtick').nth(0).check()
  await page.locator('.browse-rowtick').nth(2).check()

  await expect(page.locator('.browse-status-picked')).toHaveText('2 ticked')
  await expect(claims).toHaveText('Set claims on the 2 selected cards')

  /* A fold may hide a row but must never hide what a bulk write would reach, so the section
     header carries its own share of the count. */
  await expect(page.locator('.browse-sectcount').nth(0)).toHaveText('2/3')
})

test('the box claim sends only the ticked fields, over only the ticked indices', async ({
  page,
}) => {
  const wire = await open(page)
  await openBoxOps(page)
  await expandAll(page)

  await page.locator('.browse-rowtick').nth(0).check()
  await page.locator('.browse-rowtick').nth(2).check()
  await page.getByRole('button', { name: /^Set claims on/ }).click()

  // Nothing armed yet: an editor that opened with a field ticked would write to every card in
  // scope on the first press.
  await page.getByRole('button', { name: /^Apply to/ }).click()
  await expect(page.locator('.boxops-machine', { hasText: 'Tick a field' })).toBeVisible()
  expect(wire.filter((sent) => sent.method === 'PUT')).toHaveLength(0)

  await page.locator('.boxops-claim-row', { hasText: 'SET HINT' }).getByRole('checkbox').check()
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

  await page.getByRole('button', { name: /^Set claims on/ }).click()
  await page.locator('.boxops-claim-row', { hasText: 'NOTE' }).getByRole('checkbox').check()
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
  await expect(finish).toHaveText('normal · reverse_holo')

  /* And a record written BEFORE the amendment still reads. There is no migration — a bare
     string is a one-member claim — so this is the shape most of the store still holds. */
  await page.locator('.browse-row').nth(0).click()
  await expect(page.locator('.browse-fact', { hasText: 'Finish' }).locator('dd')).toHaveText(
    'normal',
  )
})

test('the box-claims finish control is a multi-select and sends a list', async ({ page }) => {
  const wire = await open(page)
  await openBoxOps(page)

  await page.getByRole('button', { name: /^Set claims on/ }).click()
  await page.locator('.boxops-claim-row', { hasText: 'FINISH' }).getByRole('checkbox').check()

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

  await page.getByRole('button', { name: /^Set claims on/ }).click()
  await page.locator('.boxops-claim-row', { hasText: 'FINISH' }).getByRole('checkbox').check()
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

// ---------------------------------------------------------------- the destructive controls

test('the mid-box delete aims with the target’s own capture id and reports the shift', async ({
  page,
}) => {
  const wire = await open(page)

  await expandAll(page)
  await page.locator('.browse-row', { hasText: 'Thievul' }).nth(1).click()
  await page.getByRole('button', { name: 'Remove this card…' }).click()
  await page.getByRole('button', { name: /^Remove this card and slide/ }).click()

  const removed = wire.find((sent) => sent.path.endsWith('/remove'))
  expect(removed?.method).toBe('POST')
  expect(removed?.path).toBe('/inventory/2/3/remove')
  /* The aim. The operation is not idempotent — after the shift a different physical card sits
     at that index — so a replay must refuse rather than delete the neighbour that slid in. */
  expect(removed?.body).toEqual({ capture_id: 'cap-3' })

  /* `shifted > 0` means every label above the deleted card has changed, and the receipt has to
     say so: it is the one operation in the product that renumbers. */
  await expect(page.locator('.browse-receipt')).toContainText('moved down one index')
})

test('a sold or retired card is not offered the mid-box delete at all', async ({ page }) => {
  await open(page)

  await expandAll(page)
  await page.locator('.browse-row', { hasText: 'Eiscue' }).click()

  /* The `restores_to` lesson: never offer a control whose only behaviour is a refusal.
     `do_remove_card` refuses a sold card by name, because deleting it would erase the record of
     a departure D10 makes permanent. */
  await expect(page.getByRole('button', { name: 'Remove this card…' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Correct claims' })).toBeVisible()
})

test('the whole-box delete will not fire until the box number is typed', async ({ page }) => {
  const wire = await open(page)
  await openBoxOps(page)

  await page.getByRole('button', { name: /^Delete box 2/ }).click()
  const fire = page.getByRole('button', { name: 'Delete box 2 permanently' })
  await expect(fire).toBeDisabled()
  expect(wire.filter((sent) => sent.method === 'DELETE')).toHaveLength(0)

  /* Typing the number is the gate, chosen over an "are you sure" for the reason that makes
     docs/DESIGN.md's ban worth having: a yes/no dialog is answered by the same reflex that
     pressed the button, and this control's risk is deleting box 9 while looking at box 95. */
  await page.getByLabel('Type 2 to confirm').fill('9')
  await expect(fire).toBeDisabled()

  await page.getByLabel('Type 2 to confirm').fill('2')
  await expect(fire).toBeEnabled()
  await fire.click()

  const deleted = wire.find((sent) => sent.method === 'DELETE')
  expect(deleted?.path).toBe('/boxes/2')

  // The receipt is per-kind and is the only evidence the operation did what it said: there is
  // nothing left to go and check.
  await expect(page.locator('.boxops-receipt')).toContainText('There is no undo')
})

// ----------------------------------------------------------------- what the merge kept (D26)

test('the re-shoot control came with the merge, as D31 requires', async ({ page }) => {
  await open(page)
  await expect(page.getByRole('button', { name: 'Re-shoot this photo' })).toBeVisible()
})
