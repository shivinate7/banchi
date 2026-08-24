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
}) {
  const box = 2
  return {
    box,
    index: input.index,
    label: `Box ${box} · Section ${input.section} · Card ${input.index}`,
    section: input.section,
    card: input.index,
    place: {
      located: true,
      label: `Box ${box} · Section ${input.section} · Card ${input.index}`,
      box,
      index: input.index,
      section: input.section,
      card: input.index,
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
    metadata_finish: 'normal',
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
  '2/2': card({ index: 2, state: 'captured', name: null, sku: null, section: 1, sectionStart: 1, sectionEnd: 3 }),
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

/** The group `GET /search` answers with for the two-copy SKU. Whole, including the copies that
 *  did not match the query themselves — `do_search` renders a group by `positions_for_sku`, and
 *  a screen built against a partial group would be built against a lie. */
function searchAnswer(query: string) {
  const copies = ['2/1', '2/3'].map((key) => {
    const held = CARDS[key as keyof typeof CARDS]
    return {
      key,
      state: held.state,
      state_at: held.state_at,
      has_photo: true,
      place: held.place,
    }
  })
  const matched = query === '8937370' || query.toLowerCase() === 'thievul'
  return {
    query,
    groups: matched
      ? [
          {
            sku: '8937370',
            names: ['Thievul'],
            number: '090',
            printed_total: '132',
            set_hint: 'ME01',
            condition: 'Near Mint',
            listed: { pushed: 0, staged: 2, live: 1 },
            on_hand: 2,
            cap: 4,
            copies,
          },
        ]
      : [],
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
  await expect(page.locator('.browse-row').first()).toBeVisible()
  return wire
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
  await page.locator('.browse-row', { hasText: 'captured' }).first().click()
  await expect(page.locator('.inventory-lone')).toBeVisible()
  await expect(page.locator('.card-locations-owner')).toHaveCount(0)
  await expect(page.locator('.inventory-lone').getByRole('button', { name: 'Mark sold' })).toBeVisible()
  await expect(page.locator('.inventory-lone').getByRole('button', { name: 'Retire' })).toBeVisible()
})

// ------------------------------------------------------------------- collapsible sections

test('sections start collapsed, and the one holding the selection is open', async ({ page }) => {
  await open(page)

  const folds = page.locator('.browse-sectfold')
  await expect(folds).toHaveCount(2)
  // Section 1 holds card 1, which is where the walk plants its selection.
  await expect(folds.nth(0)).toHaveAttribute('aria-expanded', 'true')
  await expect(folds.nth(1)).toHaveAttribute('aria-expanded', 'false')
  await expect(page.locator('.browse-row')).toHaveCount(3)
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
  await expect(page.locator('.browse-row[aria-current="true"]')).toHaveText(/5/)
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

// ------------------------------------------------------------------------- the mass-select

test('ticking rows narrows what a box-wide claim will reach, and says so on the button', async ({
  page,
}) => {
  await open(page)
  await openBoxOps(page)

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

// ---------------------------------------------------------------- the destructive controls

test('the mid-box delete aims with the target’s own capture id and reports the shift', async ({
  page,
}) => {
  const wire = await open(page)

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

  await page.getByRole('button', { name: 'expand all' }).click()
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
