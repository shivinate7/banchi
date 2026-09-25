import { test, expect, type Page } from '@playwright/test'
import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'

/* THE CONFIRM CONTROL — identity-follows-sku.md §8.1, the sibling `correct-answer.spec.ts`
 * cannot reach. `app/src/CardHero.tsx:ListingCorrection` gains a second press, "The listing
 * is right", for the case the D252 correction does not answer: a HELD card
 * (`identity_source: 'read'`) whose SKU is already right and whose drawn name is only the
 * camera's — the owner's own examples are a misread "Rell" and "Jax" (this fixture's own
 * `Rell, Noxus`/`Rell, Magnetic` pair echoes §5.5's own worked example). `CLAUDE.md`'s hard
 * rule once more: "a route is not a feature... nothing is built until it is reachable from a
 * screen."
 *
 * ITS OWN MINIMAL BOOT, `correct-answer.spec.ts`'s own precedent and for the same reason:
 * importing that file would re-run every `test()` it registers as a module side effect, so
 * this file stubs the same small slice of the shell and the walk a single held card needs to
 * render, with its own fixture rather than a shared one.
 *
 * EVERYTHING IS STUBBED AND THE REAL STORE IS NEVER TOUCHED — every route is intercepted,
 * including `POST /inventory/2/1/confirm`, so issuing a real one never reaches the owner's
 * store.
 */

const VIEW_ROUTE = '/#/inventory'

/** A HELD card: `sku` already set, `identity_source: 'read'` (§3.1 — "the card has no SKU, or
 *  it is a held card... or its SKU is absent from the table. In each case the identity fields
 *  equal the evidence fields"), so `name`/`number`/`printed_total` mirror `read_name`/
 *  `read_number`/`read_printed_total` exactly, and `read_disputes` is true.
 *
 *  `listing`/`listing_differs`/`reading_differs` are the review-round fields (§5.4/§8.1, the
 *  owner's ruling: "show listing name and/or hide when identical i dont think it's an or
 *  situation"). `listing_differs: true` because the SKU's own catalog row ("Rell, Magnetic
 *  024/221") disagrees with what `name`/`number` already show — "Listed as" draws.
 *  `reading_differs: false` because `read_name`/`read_number` are byte-identical to
 *  `name`/`number` on a held card by construction — "Read as" stays hidden, which is the fix
 *  for the defect this fixture used to reproduce: the line repeating "Card:"/"Number:" word
 *  for word. */
const CARD = {
  box: 2,
  index: 1,
  label: 'Box 2 · Section 1 · Card 1',
  section: 1,
  card: 1,
  place: {
    located: true,
    label: 'Box 2 · Section 1 · Card 1',
    box: 2,
    index: 1,
    slot: 1,
    section: 1,
    card: 1,
    box_name: 'Riftbound singles',
    section_start: 1,
    section_end: 2,
    box_total: 2,
    fraction: 0,
    neighbors: null,
    section_gaps: 0,
  },
  photo: 'photos/2/1.jpg',
  photo_sha256: null,
  photo_reclaimed_at: null,
  set_hint: null,
  metadata_finish: 'normal',
  game: 'riftbound',
  set_name: 'Origins',
  rarity: null,
  rarity_claim: null,
  note: null,
  captured_at: '2026-09-20T12:34:00+00:00',
  capture_id: 'cap-1',
  name: 'Rell, Noxus',
  number: '037',
  printed_total: '298',
  number_display: '037/298',
  confidence: null,
  sku: '8925897',
  condition: 'Near Mint',
  identity_source: 'read',
  bound_by: 'answer',
  bound_at: '2026-09-20T12:35:00+00:00',
  read_disputes: true,
  listing: { name: 'Rell, Magnetic', number: '024/221', printed_total: null },
  listing_differs: true,
  reading_differs: false,
  read_name: 'Rell, Noxus',
  read_number: '037',
  read_printed_total: '298',
  state: 'identified',
  state_at: '2026-09-20T12:35:00+00:00',
  retire_reason: null,
  run: null,
}

const BOXES = {
  boxes: [
    {
      box: 2,
      name: 'Riftbound singles',
      sections: [1],
      state: 'open',
      capacity: null,
      fill: 1,
      next_index: 2,
      cards: 1,
      on_hand: 1,
      sold: 0,
      retired: 0,
      moved: 0,
      listed: 0,
      sections_detail: [{ section: 1, start: 1, end: 2, count: 1 }],
    },
  ],
}

const GAMES = {
  games: [{ key: 'riftbound', display: 'Riftbound', located: true, products: [] }],
  default: 'riftbound',
}

/** The row `POST /inventory/2/1/confirm` hands back on the write direction — `ConfirmResult`
 *  (`types.ts`), the shape `CardHero.tsx:ListingCorrection` reads. Confirming binds the
 *  card's OWN current SKU (§8.1: "the SKU does not move"): `identity_source` turns `'sku'`,
 *  `bound_by` turns `'confirm'`, and the identity fields become the catalog's own — the name
 *  changes even though the SKU does not, which is the whole point of this press.
 *
 *  `listing_differs` drops to `false` — the shown name/number now equal the listing by
 *  construction. `reading_differs` turns `true` — the camera's own read (`Rell, Noxus`) still
 *  disagrees with the now-bound catalog name, which is exactly the case "Read as" exists for
 *  (§5.4/§8.1). */
function confirmedBody() {
  return {
    position: '2/1',
    box: 2,
    index: 1,
    confirmed: true,
    undone: false,
    sku: '8925897',
    condition: 'Near Mint',
    card: {
      ...CARD,
      identity_source: 'sku',
      bound_by: 'confirm',
      bound_at: '2026-09-24T09:00:00+00:00',
      name: 'Rell, Magnetic',
      number: '024/221',
      printed_total: null,
      number_display: '024/221',
      listing_differs: false,
      reading_differs: true,
    },
  }
}

function unconfirmedBody() {
  return {
    position: '2/1',
    box: 2,
    index: 1,
    confirmed: false,
    undone: true,
    sku: '8925897',
    condition: 'Near Mint',
    card: { ...CARD },
  }
}

async function open(page: Page, card: Record<string, unknown> = CARD): Promise<void> {
  await page.route(/\/status$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        captures_root: 'captures',
        store: 'inventory/store.sqlite',
        store_exists: true,
        cards: 1,
        states: {},
        queues: { review: 0, parked: 0 },
        next_index: {},
      }),
    })
  })
  await page.route(/\/orders$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ summary: 'no orders', orders: [], resolution: { orders: [], counts: {} } }),
    })
  })
  await page.route(/\/games$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(GAMES) })
  })
  await page.route(/\/boxes(\?.*)?$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(BOXES) })
  })
  await page.route(/\/search\?/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ q: '', groups: [] }),
    })
  })
  await page.route(/\/inventory\/\d+$/, async (route) => {
    const request = route.request()
    if (request.method() !== 'GET') return route.fallback()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 2, cards: { '2/1': card }, boxes: {}, listings: {} }),
    })
  })
  await page.route(/\/inventory$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 2, cards: { '2/1': card }, boxes: {}, listings: {} }),
    })
  })
  await page.route(/\/pipeline\/runs\/[^/]+\/pricing$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({}) })
  })
  await page.route(/\/pipeline\/runs$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ runs: [] }) })
  })
  await page.route(/\/queues$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ review: [], parked: [] }),
    })
  })
  await page.route(/\/photo\/(by-card\/[0-9a-f]+|\d+\/\d+)/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="63" height="88"><rect width="63" height="88" fill="#ccc"/></svg>',
    })
  })

  await page.goto(VIEW_ROUTE)
  await settleFonts(page)
  await expect(page.locator('.browse-hero-name')).toHaveText(card.name as string)
}

sealEveryTest()

test('the confirm control is reachable on #/inventory for a held card, and its undo works', async ({ page }) => {
  await open(page)

  let confirmed: { method: string; body: unknown } | null = null
  let unconfirmed: { method: string; body: unknown } | null = null
  await page.route(/\/inventory\/2\/1\/confirm$/, async (route) => {
    const request = route.request()
    const body = request.postDataJSON() as { undo?: boolean } | null
    if (body?.undo === true) {
      unconfirmed = { method: request.method(), body }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(unconfirmedBody()) })
    } else {
      confirmed = { method: request.method(), body }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(confirmedBody()) })
    }
  })

  // Both presses share one reserved slot (D118) — the correction's own "Wrong card?" stays
  // beside this one, never replaced by it.
  const rightCard = page.getByRole('button', { name: 'The listing is right' })
  const wrongCard = page.getByRole('button', { name: 'Wrong card?' })
  await expect(rightCard).toBeVisible()
  await expect(wrongCard).toBeVisible()

  await rightCard.click()

  await expect.poll(() => confirmed).not.toBeNull()
  // NEVER TAKES A `sku` — the listing already on the card is what gets confirmed (§8.1).
  expect((confirmed as unknown as { body: Record<string, unknown> }).body).toEqual({})

  const toast = page.locator('.bn-toast', { hasText: 'Listing confirmed' })
  await expect(toast).toBeVisible()
  await expect(toast).toContainText('8925897')

  await toast.getByRole('button', { name: 'Undo' }).click()

  await expect.poll(() => unconfirmed).not.toBeNull()
  expect((unconfirmed as unknown as { body: { undo: boolean } }).body.undo).toBe(true)
  const undoneToast = page.locator('.bn-toast', { hasText: 'Confirmation undone' })
  await expect(undoneToast).toBeVisible()
  // The body names the place from the card's own label (read as a sentence), never the box
  // and store index alone.
  await expect(undoneToast).toContainText("Box 2, Section 1, Card 1 — back to the camera's read.")
  await expect(undoneToast).not.toContainText('Box 2, Card 1')
})

/* THE D118 SWEEP OVER THIS PRESS, `inventory.spec.ts`'s own shape (the file's own header
 * explains why this is not an import of it) over the smallest fixture that draws the confirm
 * control: pressing "The listing is right" writes its own receipt inside `.card-correction`'s
 * reserved slot, inside `.browse-card`, and that growth may move nothing OUTSIDE the card
 * panel — the same floor `inventory.spec.ts`'s "the press that sells a copy moves nothing
 * outside the panel it lands in" proves for Mark sold. */
async function outsideThePanel(page: Page): Promise<Record<string, string>> {
  return await page.evaluate(() => {
    const out: Record<string, string> = {}
    const stamp = () => `n${Math.random().toString(36).slice(2)}`
    for (const el of Array.from(document.querySelectorAll<HTMLElement>('body *'))) {
      if (el.closest('.browse-card') !== null) continue
      let fixed = false
      for (let a: HTMLElement | null = el; a !== null && a !== document.body; a = a.parentElement) {
        if (getComputedStyle(a).position === 'fixed') {
          fixed = true
          break
        }
      }
      if (fixed) continue
      const r = el.getBoundingClientRect()
      if (r.width === 0 && r.height === 0) continue
      if (el.dataset.stableId === undefined) el.dataset.stableId = stamp()
      const cls =
        typeof el.className === 'string' && el.className !== '' ? `.${el.className.trim().split(/\s+/)[0]}` : ''
      out[el.dataset.stableId] = `${el.tagName.toLowerCase()}${cls} @ ${Math.round(r.x)},${Math.round(r.y)} h${Math.round(r.height)}`
    }
    return out
  })
}

function whatMoved(before: Record<string, string>, after: Record<string, string>): string[] {
  const moved: string[] = []
  for (const [id, was] of Object.entries(before)) {
    const now = after[id]
    if (now === undefined || now === was) continue
    moved.push(`${was}   ->   ${now}`)
  }
  return moved
}

/** `outsideThePanel`, held until two reads 75ms apart agree, or `tries` runs out.
 *
 *  THE RACE THIS CLOSES: the box rail opens the walk's first section as a consequence of
 *  landing on it (`BoxBrowse.tsx`, the effect keyed on `selected`) — including on the very
 *  first render, so the walk never arrives with its own selection hidden. That fold's chevron
 *  (`.browse-sectmark`) rotates in over `.2s`, entirely on MOUNT and independent of the
 *  confirm press. This file's `open()` waits only for the card hero's name, not for
 *  `.browse-sectfold` the way `inventory.spec.ts`'s own `open()` does, so on a slow enough
 *  runner a "before" sample taken right after can still catch that rotation mid-flight.
 *  MEASURED (CI run 36089115485's trace, reproduced locally by throttling the CPU 6x): the
 *  chevron's own svg and path, unsettled — `svg @ 303,477 h16 -> svg @ 304,478 h14` — settled
 *  into the SAME shape by the next sample, and the confirm press never touched it. Sampling
 *  twice and requiring agreement reads the chevron once it has stopped moving, on its own,
 *  never on the press's schedule — so a press that genuinely moves something still fails this
 *  every time, because two samples of a REAL move never agree either. */
async function settled(page: Page, tries = 40): Promise<Record<string, string>> {
  let last = await outsideThePanel(page)
  for (let i = 0; i < tries; i += 1) {
    await page.waitForTimeout(75)
    const next = await outsideThePanel(page)
    if (JSON.stringify(next) === JSON.stringify(last)) return next
    last = next
  }
  return last
}

test('the confirm press moves nothing outside the panel it lands in', async ({ page }) => {
  await open(page)

  await page.route(/\/inventory\/2\/1\/confirm$/, async (route) => {
    const request = route.request()
    const body = request.postDataJSON() as { undo?: boolean } | null
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body?.undo === true ? unconfirmedBody() : confirmedBody()),
    })
  })

  const rightCard = page.getByRole('button', { name: 'The listing is right' })
  await rightCard.scrollIntoViewIfNeeded()

  const before = await settled(page)
  const height = await page.evaluate(() => document.documentElement.scrollHeight)
  const at = await page.evaluate(() => window.scrollY)

  await rightCard.click()
  await expect(page.locator('.bn-toast', { hasText: 'Listing confirmed' })).toBeVisible()

  const after = await settled(page)
  const moved = whatMoved(before, after)
  expect(moved, `${moved.length} elements outside the panel moved on the press:\n${moved.slice(0, 12).join('\n')}`)
    .toHaveLength(0)
  expect(
    await page.evaluate(() => document.documentElement.scrollHeight),
    'the page changed height on a press',
  ).toBe(height)
  expect(await page.evaluate(() => window.scrollY), 'the page scrolled under the press').toBe(at)
})

/* --------------------------------------- Details' two identity lines (§5.4/§8.1, review round)
 *
 * The owner's ruling, verbatim: "show listing name and/or hide when identical i dont think
 * it's an or situation" — BOTH `listing_differs` ("Listed as") and `reading_differs`
 * ("Read as") are independent gates, never a single either/or, so each gets its own shown
 * case and its own hidden case below. The server computes both (`_listing_decoration`);
 * these four cases prove `CardHero.tsx` draws exactly what the booleans say and nothing it
 * infers on its own. */

/** `dt`/`dd` locator for one fact row in the Identity group — `factGroupsOf`'s own shape. */
function fact(page: Page, label: string) {
  return page.locator('.browse-fact', { has: page.locator('dt', { hasText: label }) })
}

test('"Listed as" draws when the listing disputes the shown name/number', async ({ page }) => {
  // CARD itself: held, `listing_differs: true` — the review round's own reproduction of the
  // defect ("Read as Rell, Noxus 037/298" repeating Card:/Number: word for word) now fixed
  // by drawing "Listed as" instead.
  await open(page, CARD)

  const listedAs = fact(page, 'Listed as')
  await expect(listedAs).toBeVisible()
  await expect(listedAs.locator('dd')).toHaveText('Rell, Magnetic 024/221')
})

test('"Listed as" hides once the listing agrees with the shown name/number', async ({ page }) => {
  const bound = {
    ...CARD,
    identity_source: 'sku',
    bound_by: 'confirm',
    name: 'Rell, Magnetic',
    number: '024/221',
    printed_total: null,
    number_display: '024/221',
    // The listing equals what Card/Number now show — `listing_differs` is false, computed
    // server-side off exactly this comparison (never a raw string compare on screen).
    listing_differs: false,
    reading_differs: true,
  }
  await open(page, bound)

  await expect(fact(page, 'Listed as')).toHaveCount(0)
})

test('"Read as" stays hidden on a held card, even though its own read_disputes flag is set — the fix for the line repeating Card:/Number: word for word', async ({ page }) => {
  // CARD: `read_disputes: true` (the stored, bind-time flag) but `reading_differs: false`
  // (the fresh, shown-pair comparison) — the two answer different questions, and only the
  // second one gates this line (§5.4/§8.1).
  await open(page, CARD)

  await expect(fact(page, 'Read as')).toHaveCount(0)
})

test('"Read as" draws when the camera\'s read disputes the shown name/number', async ({ page }) => {
  const disputed = {
    ...CARD,
    identity_source: 'sku',
    bound_by: 'confirm',
    name: 'Rell, Magnetic',
    number: '024/221',
    printed_total: null,
    number_display: '024/221',
    listing_differs: false,
    // The read ("Rell, Noxus" 037/298) still disagrees with the now-bound catalog name —
    // exactly the case §8.1's own confirm press produces, and §5.4's worked example.
    reading_differs: true,
  }
  await open(page, disputed)

  const readAs = fact(page, 'Read as')
  await expect(readAs).toBeVisible()
  await expect(readAs.locator('dd')).toHaveText('Rell, Noxus 037/298')
})
