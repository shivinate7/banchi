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
 *  `read_number`/`read_printed_total` exactly, and `read_disputes` is true. */
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
    box_closed: false,
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
 *  changes even though the SKU does not, which is the whole point of this press. */
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

async function open(page: Page): Promise<void> {
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
      body: JSON.stringify({ version: 2, cards: { '2/1': CARD }, boxes: {}, listings: {} }),
    })
  })
  await page.route(/\/inventory$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ version: 2, cards: { '2/1': CARD }, boxes: {}, listings: {} }),
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
  await expect(page.locator('.browse-hero-name')).toHaveText('Rell, Noxus')
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
  await expect(page.locator('.bn-toast', { hasText: 'Confirmation undone' })).toBeVisible()
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

  const before = await outsideThePanel(page)
  const height = await page.evaluate(() => document.documentElement.scrollHeight)
  const at = await page.evaluate(() => window.scrollY)

  await rightCard.click()
  await expect(page.locator('.bn-toast', { hasText: 'Listing confirmed' })).toBeVisible()

  const after = await outsideThePanel(page)
  const moved = whatMoved(before, after)
  expect(moved, `${moved.length} elements outside the panel moved on the press:\n${moved.slice(0, 12).join('\n')}`)
    .toHaveLength(0)
  expect(
    await page.evaluate(() => document.documentElement.scrollHeight),
    'the page changed height on a press',
  ).toBe(height)
  expect(await page.evaluate(() => window.scrollY), 'the page scrolled under the press').toBe(at)
})
