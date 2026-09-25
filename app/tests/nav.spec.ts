import { test, expect, type Page, type Route } from '@playwright/test'
import { sealEveryTest } from './shell'
import { CAPTURE_PORT } from '../devPort'

/* THE SHELL'S KEYBOARD, AND THE FIRST TEST THIS APP HAS HAD OF THE CHROME EVERY SCREEN SITS IN.
 *
 * `app/src/App.tsx` carries two keyboards — the `,` chord that JUMPS to a route by name, and
 * (D51, 2026-08-30) Cmd-arrow, which STEPS along the sidebar in the order it is drawn. Neither
 * had an assertion of any kind: `make design-check` covered the Fulfilment view, the review
 * queue, the run panel, the capture claims, the inventory walk and the pricing screen, and
 * nothing at all covered the chrome all of them sit under.
 *
 * RE-POINTED AT THE BANCHI SHELL, 2026-09-03. The strip along the top became a collapsible
 * sidebar with a phone tab bar and drawer, `#/` became Home and capture moved to `#/capture`,
 * the leader letters gained `H`, and the inline ⌘←/⌘→ keycaps were deliberately NOT restored —
 * the owner chose one keyboard reference sheet over chips on the chrome. So the case that used
 * to measure where the chips sat now asserts the two things that ruling leaves owing: the
 * binding is announced to a screen reader, and the sheet a person is sent to documents it.
 *
 * THE STRONGEST CASES HERE ARE STILL THE TWO ENDS AND THE THREE REFUSALS, because each is a
 * rule that would otherwise live only in a comment: the step never wraps, a bare arrow is not
 * the shell's, a held Cmd inside a text field belongs to the caret, and a screen outside the
 * ring is left alone. A step that quietly gained a wrap, or quietly started eating the caret
 * keys, would pass every other file in this directory.
 *
 * WHAT THIS CANNOT SEE, said plainly rather than left to be assumed. Playwright presses keys
 * through the debugging protocol, which never fires the BROWSER's own shortcuts — so a case
 * here proves the handler steps and that it calls `preventDefault`, and it cannot prove that
 * Chrome or Safari then declines to go Back. That half is one press at the rig, and D51 names
 * it as the thing to check first if the step ever appears to fire twice.
 *
 * NOT A HARNESS TEST AND MUST NOT BECOME ONE. `docs/GATES.md`'s contract is nine Python tests
 * at the Stop hook; this starts a browser.
 */

/** The sidebar, and the links inside it. Scoped to `.bn-side` on purpose: the phone drawer
 *  renders a SECOND `nav.bn-nav` off the same table when it is open, and the sidebar's own
 *  foot carries a `.bn-nav-link` to the Fulfiller that is not a route in the ring. `nav` is
 *  what separates them, and it is the element the shell hangs `aria-keyshortcuts` and
 *  `data-armed` off. */
const NAV = '.bn-side nav.bn-nav'
const NAV_LINK = `${NAV} a.bn-nav-link`

/** The ring, in the order `app/src/App.tsx` draws it: Home, then the workflow group, then the
 *  sell group, then the library. The hash form verbatim, for the reason every other spec here
 *  records — a path-style '/inventory' is served index.html by Vite, mounts with an empty hash
 *  and renders HOME, which is a passing navigation to the wrong view.
 *
 *  PINNED ON PURPOSE, AND RECONCILED AT THE COMMIT SINCE 2026-08-31. `App.tsx` derives its own
 *  ring — `hotkey !== undefined` over the ROUTES table — and this list is a hand typed copy of
 *  that, which is the shape that goes stale. It did: D70 added `#/codes` with a key and this
 *  array was not touched, so the ring under test was seven routes long while the product's was
 *  eight, and the "never a wrap" case below stepped off the end of THIS list onto a real
 *  screen. That failure was luck — a roster missing a route normally just walks the routes it
 *  has and stays green, which is what happened to `cursor.spec.ts` for two days.
 *
 *  So the copy stays (a derived ring could not assert the ORDER against anything independent —
 *  it would be `App.tsx`'s answer marked by `App.tsx`) and `scripts/docs-audit.py`'s
 *  `route rosters` row reads the marker below, reads the ROUTES table, and fails the commit
 *  when they disagree. */
/* ROUTE-ROSTER hotkey */
const RING = [
  '#/',
  '#/capture',
  '#/review',
  '#/pricing',
  '#/orders',
  '#/shipping',
  '#/revenue',
  '#/inventory',
  '#/graveyard',
  '#/codes',
] as const

/** What each of those routes renders, so a step is asserted to have ARRIVED rather than
 *  merely to have changed a string. A hash the shell does not recognise still changes
 *  `location.hash`; only the view proves the route resolved.
 *
 *  `#/orders` and `#/shipping` are one component in two stages (`OrdersHub`), and the class
 *  that separates them is the stage — which is exactly the fact worth asserting, since the
 *  two routes differ by nothing else. */
/* ROUTE-ROSTER hotkey */
const VIEW: Record<(typeof RING)[number], string> = {
  '#/': 'main.home',
  '#/capture': 'main.capture',
  '#/review': 'main.review',
  '#/pricing': 'main.pricing',
  '#/orders': 'main.orders-hub.orders',
  '#/shipping': 'main.orders-hub.shipping',
  '#/revenue': 'main.revenue',
  '#/inventory': 'main.inventory',
  '#/graveyard': 'main.graveyard',
  '#/codes': 'main.codes',
}

/** The end of the ring, read off the array rather than written out beside it. Three cases
 *  below assert something about "the last screen the step can reach", and each one naming
 *  `#/inventory` by hand is how the D70 miss survived a file that already had the route in
 *  front of it: the array grew and three string literals did not. */
/* The `!` is the tuple's own length used as an index, which the compiler widens to `number`
   and so cannot narrow; `RING` is `as const` and non-empty two lines up. */
const LAST = RING[RING.length - 1]!

/* Every read any of these screens makes on mount, answered with the smallest honest payload.
 * Nothing here may touch the real store: an unstubbed read is a request to whatever is
 * listening on this checkout's capture port, and in the main tree that is the owner's actual
 * server over their actual inventory. It also makes the suite depend on `make server` being
 * up, which no other test in this directory does. */
async function stub(page: Page, cards: unknown[] = []) {
  const json = async (route: Route, body: unknown) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  }

  await page.route(/\/inventory$/, (route) => json(route, { version: 2, cards, boxes: {}, listings: {} }))
  /* D192 (store-scaling item 2): Home (`#/`) no longer calls the bare `/inventory`
   * above — it calls `getRecentCards`, `GET /inventory/recent?limit=N`. Empty, matching this
   * ring's own `cards` default of `[]`: nothing here asserts on the hero deck's contents. */
  await page.route(/\/inventory\/recent(\?|$)/, (route) => json(route, { cards: {} }))
  /* `GET /boxes` IS THE UNION OF THE REGISTRY AND WHATEVER `cards` NAMES (D20's own rule —
   * "a box existed only because a card named one" — is what `do_boxes` answers with in
   * production). This fixture's registry is always empty, so deriving the boxes list from
   * `cards` here is what stands in for that union: `#/inventory`'s box-scoped fetch (D-per-
   * box-read, item 2) needs `shelves` to resolve to at least one box before it can fetch
   * anything at all, and with an empty `/boxes` AND no rows loaded yet (the fetch needs a
   * shelf to run), an empty registry over a non-empty `cards` argument left `#/inventory`
   * waiting on a shelf that would never come — the whole screen stuck on its loading
   * skeleton, which is what timed out the one case here that opens it with a card. */
  const boxNumbers = [
    ...new Set(cards.map((card) => (card as { box?: unknown }).box).filter((box): box is number => typeof box === 'number')),
  ]
  await page.route(/\/boxes$/, (route) =>
    json(route, {
      boxes: boxNumbers.map((box) => ({
        box,
        name: null,
        sections: [],
        state: 'open',
        capacity: null,
        fill: cards.length,
        next_index: cards.length + 1,
        cards: cards.length,
        on_hand: cards.length,
        sold: 0,
        retired: 0,
        moved: 0,
        listed: 0,
        sections_detail: [],
      })),
    }),
  )
  /* `#/inventory`'s own per-box read (D192, item 2), now that `/boxes` above can
   * resolve to a real shelf: `BoxBrowse` fetches `GET /inventory/<box>` for whichever box
   * that resolves to, keyed by index, in the same per-card shape `GET /inventory` answers
   * with — this ring's `cards` array narrowed to the requested box. */
  await page.route(/\/inventory\/(\d+)$/, (route) => {
    const match = /\/inventory\/(\d+)$/.exec(route.request().url())
    const box = match ? Number(match[1]) : NaN
    const forBox: Record<string, unknown> = {}
    for (const card of cards) {
      const c = card as { box?: unknown; index?: unknown }
      if (c.box === box) forBox[`${c.box}/${c.index}`] = card
    }
    return json(route, { version: 2, cards: forBox, listings: {} })
  })
  await page.route(/\/queues$/, (route) => json(route, { review: [], parked: [] }))
  await page.route(/\/search\?/, (route) => json(route, { query: '', groups: [] }))
  await page.route(/\/games$/, (route) => json(route, { games: [] }))
  /* D134's graveyard, the twelfth route this ring steps to. */
  await page.route(/\/graveyard$/, (route) => json(route, { departed: [] }))
  /* The markdown sheet reads its own history when its host screen mounts, closed or not, and
     holds nothing else until an export is uploaded. Empty is the honest answer here: this
     checkout has its own store (D43) and no markdown has ever been written into it. The host
     is `#/pricing` since D105 — this stub is global and so did not move, but the sentence
     naming a screen had to. */
  await page.route(/\/pipeline\/markdowns$/, (route) => json(route, { markdowns: [] }))
  /* `GET /status` IN THE SHAPE `ServerStatus` ACTUALLY HAS, which it was not: this stub
     answered `{boxes, next}` — a shape no version of that route has sent — and the shell reads
     `status.cards` off it into the sidebar's card count. `undefined.toLocaleString()` throws
     inside `Sidebar`, which sits outside every route boundary, so the whole shell would go
     down a beat after each `goto`. It did not show up as a failure only because every case
     here had already made its first assertion by then. */
  await page.route(/\/status$/, (route) =>
    json(route, {
      captures_root: 'captures',
      store: 'inventory/store.sqlite',
      store_exists: true,
      cards: cards.length,
      states: {},
      queues: { review: 0, parked: 0 },
      next_index: {},
    }),
  )
  await page.route(/\/pipeline\/runs$/, (route) => json(route, { runs: [] }))
  /* `#/runs` draws the claims panel on mount (D174), and this file
     opens every route — so the read is stubbed here with the rest of the screen's.
     Empty: a healthy store holds no claim, and the panel then draws nothing at all. */
  await page.route(/\/pipeline\/submissions$/, (route) =>
    json(route, { claims: [], counts: { claims: 0, keys: 0, stale: 0 } }),
  )
  /* THE CORPUS FIRST AND THE WORKLIST SECOND, AND THE ORDER IS THE MECHANISM. `/\/pricing$/`
     matches `…/pipeline/pricing` as happily as `…/pricing`, and Playwright takes the NEWEST
     handler — so registering the corpus second answers the WORKLIST with a corpus, `roster`
     comes back undefined, and `Home.tsx` goes down behind its route boundary on
     `undefined.filter`. The narrower route is registered last and therefore wins. D86 is why
     there are two: the corpus is the store's one pricing answer, the worklist is which cards
     are in front of the operator. */
  await page.route(/\/pricing$/, (route) =>
    json(route, {
      corpus: { rule: null, basis: null, sub_threshold: null, overrides: {} },
      path: 'inventory/prices.json',
      revision: 'r0',
    }),
  )
  /* Home and `#/pricing` both open on the pricing worklist (D86 made it one file for the
     store), so it is read on the way in to the ring rather than only on one screen. Every key
     present and empty, for the reason the two stubs below give at length. */
  await page.route(/\/pipeline\/pricing(\?|$)/, (route) =>
    json(route, {
      runs: [],
      roster: [],
      skus: [],
      decisions: {},
      written_at: {},
      skipped: [],
      asked: [],
      remembered_sub_threshold: null,
      defaults: {},
      threshold: null,
      floor: null,
    }),
  )
  /* The code-card screen reads its ledger on mount (D70), and an EMPTY one is the honest
     answer here: this checkout has its own store (D43) and no code has ever been scanned into
     it. Every field the screen indexes is present rather than short, for the reason the order
     stub below gives at length — a payload missing a key makes "none" and "not asked" the same
     answer, and a screen drawn from a short map is a screen this stub could break. */
  /* `#/codes` reads its lots beside its ledger, and that went to the capture port until
     `sealEveryTest` named it — the same gap this stub's own `/status` comment records being
     caught by hand once already. */
  await page.route(/\/codes\/lots$/, (route) => json(route, { lots: [] }))
  await page.route(/\/codes$/, (route) =>
    json(route, {
      counts: {},
      total: 0,
      lanes: { bulk: 0, premium: 0, unclaimed: 0 },
      by_product: [],
      duplicates: [],
      entries: [],
      products: [],
    }),
  )
  /* The order screen reads on mount and the shipping stage does not — it holds nothing until
     an export is uploaded — but both routes are the same component now, so one stub answers
     for the pair. The `counts` map carries all six reasons including the zeros, exactly as
     `GET /orders` does: a payload that filtered them would make "nothing was short" and
     "nothing was checked" the same answer, and a screen drawn from a short map is a screen
     this stub could break. */
  await page.route(/\/orders$/, (route) =>
    json(route, {
      summary: '0 orders',
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
    }),
  )
  await page.route(/\/photo\//, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="63" height="88"/>',
    }),
  )
}

/** One card, in the shape `GET /inventory` answers with — enough for `BoxBrowse` to draw its
 *  walk, which is what puts a text field on screen. The screen renders an empty state and NO
 *  search field for an empty store, so the one case that needs a caret needs a card. Every
 *  decoration `server/capture_server.py:do_inventory` adds is here: the screen renders them and
 *  computes none of them, so a row missing one takes the panel down and the case fails as
 *  "element not found", which reads exactly like an unregistered route. */
const CARD = {
  box: 2,
  index: 1,
  label: 'Box 2, Section 1, Card 1',
  section: 1,
  card: 1,
  place: {
    located: true,
    label: 'Box 2, Section 1, Card 1',
    box: 2,
    index: 1,
    section: 1,
    card: 1,
    box_name: 'ME01 commons',
    section_start: 1,
    section_end: null,
    box_total: 1,
    fraction: 1,
    neighbors: null,
    section_gaps: 0,
  },
  photo: 'photos/2/1.jpg',
  set_hint: 'ME01',
  metadata_finish: 'normal',
  game: 'pokemon',
  rarity_claim: null,
  note: null,
  captured_at: '2026-08-22T12:34:00+00:00',
  capture_id: 'cap-1',
  name: 'Volcanion',
  number: '025',
  printed_total: '132',
  confidence: null,
  sku: null,
  condition: null,
  state: 'captured',
  state_at: '2026-08-22T12:34:00+00:00',
  retire_reason: null,
}

/** Land on a route and wait for its view, so nothing below measures a screen that is still
 *  resolving. */
async function open(page: Page, hash: (typeof RING)[number], cards: unknown[] = []) {
  await stub(page, cards)
  await page.goto(`/${hash}`)
  await expect(page.locator(VIEW[hash])).toBeVisible()
}

/* NOTHING HERE MAY REACH THE CAPTURE SERVER — `app/tests/shell.ts` carries the argument. This
   file already stubbed the shell's own `/status` by hand; the shared call replaces it so there
   is one spelling of the rule, and adds what a hand-written stub could not: a catch-all that
   REFUSES and names anything else that gets out. The call has to sit above the file's first
   `test.beforeEach`, which is what `make docs-audit`'s `spec seal` row checks. */
sealEveryTest()

test('the step walks the sidebar in the order it is drawn, and the last screen is the last', async ({
  page,
}) => {
  await open(page, RING[0])

  for (const next of RING.slice(1)) {
    await page.keyboard.press('Meta+ArrowRight')
    await expect(page.locator(VIEW[next])).toBeVisible()
    expect(page.url()).toContain(next)
  }

  /* NEVER A WRAP — `BoxBrowse` says it in those words about its own arrows and D51 takes the
     rule: a row that starts again is a row you can no longer count along. The press is still
     consumed (see the case below on the Gallery for what "consumed" is worth), so what is
     asserted here is that it lands nowhere new.

     IT IS ALSO WHAT KEEPS THE FULFILLER OUT OF THE RING, which is why there is no case of its
     own for his view. The ring is every route with a `hotkey`, so the mistake that would put
     him in it is a hotkey added to his row in ROUTES — and this assertion goes red the moment
     that happens, because the step from the last owner screen would land on #/fulfillment.
     A case pressing the step ON his view could not: `chrome` refuses there AND the ring does,
     so no single mutation makes it fail, and docs/GATES.md's rule is that a case which cannot
     fail is not coverage. `app/tests/fulfillment.spec.ts` asserts the nav is not drawn. */
  await page.keyboard.press('Meta+ArrowRight')
  await expect(page.locator(VIEW[LAST])).toBeVisible()
  expect(page.url()).toContain(LAST)
})

test('the step walks back, and the first screen is the first', async ({ page }) => {
  await open(page, LAST)

  for (const previous of [...RING].reverse().slice(1)) {
    await page.keyboard.press('Meta+ArrowLeft')
    await expect(page.locator(VIEW[previous])).toBeVisible()
    expect(page.url()).toContain(previous)
  }

  await page.keyboard.press('Meta+ArrowLeft')
  await expect(page.locator(VIEW['#/'])).toBeVisible()
})

test('a bare arrow is not the shell’s', async ({ page }) => {
  /* `#/runs` itself now redirects into the fold (D-runs-folds-into-review), so the screen
     that owns the unmodified arrow is reached at its new address: the Runs sheet open over
     `#/review`. */
  await stub(page)
  await page.goto('/#/runs')
  await expect(page.locator('.review-runs-sheet .runs')).toBeVisible()

  /* The screens own the unmodified arrows — `BoxBrowse` walks a box with them and `RunPanel`
     steps the crop preview — so the modifier is not decoration on this binding, it is what
     keeps the shell out of their key. */
  await page.keyboard.press('ArrowRight')
  await page.keyboard.press('ArrowLeft')
  await expect(page.locator('.review-runs-sheet .runs')).toBeVisible()
  expect(page.url()).toContain('#/review')
})

test('a held Cmd inside a field belongs to the caret', async ({ page }) => {
  await open(page, '#/inventory', [CARD])

  const field = page.locator('.search-field-input')
  await field.click()
  await field.fill('volcanion')
  await page.keyboard.press('Meta+ArrowLeft')
  await page.keyboard.press('Meta+ArrowRight')

  /* Still on the same screen, and the query is untouched. In a text field Cmd-arrow is the
     caret going to the start or the end of the line, which is what the hands are doing when
     they are in one — a step here would move the screen out from under a search somebody is
     halfway through typing. */
  await expect(page.locator(VIEW['#/inventory'])).toBeVisible()
  expect(page.url()).toContain('#/inventory')
  await expect(field).toHaveValue('volcanion')
})

test('a screen outside the ring keeps the browser’s key', async ({ page }) => {
  await stub(page)
  await page.goto('/#/gallery')
  await expect(page.locator(NAV)).toBeVisible()

  /* The gallery has chrome, so the listener is mounted — and it is deliberately not a step in
     any loop, so there is no next one along from it and the press is left alone rather than
     given an invented landing. Playwright's key never triggers the browser's own Back, so
     what this asserts is the shell not moving; the browser keeping the key is the half only
     the rig can see. */
  await page.keyboard.press('Meta+ArrowRight')
  await page.keyboard.press('Meta+ArrowLeft')
  expect(page.url()).toContain('#/gallery')
})

/** Every letter the sidebar advertises, read off the sidebar. `NavLink` draws `,H` beside
 *  Home, `,C` beside Capture and so on, out of the same `hotkey` field the leader dispatches
 *  on — so a route added with a key arrives here with no edit to this file, and a link drawn
 *  without one fails the shape assertion below rather than being quietly skipped. */
async function lettersFromNav(page: Page): Promise<{ href: string; cap: string }[]> {
  const links = await page.evaluate((selector) => {
    return Array.from(document.querySelectorAll<HTMLAnchorElement>(selector)).map((a) => ({
      href: a.getAttribute('href') ?? '',
      cap: (a.querySelector('kbd')?.textContent ?? '').trim(),
    }))
  }, NAV_LINK)

  /* A FLOOR, because a selector that matched nothing would turn the two cases below into
     loops over an empty list — green, instantly, forever. */
  expect(links.length, `the sidebar drew no links — is \`${NAV_LINK}\` still it?`).toBe(RING.length)
  return links
}

test('the comma leader jumps to every screen the sidebar offers a letter for', async ({ page }) => {
  await open(page, RING[0])
  const links = await lettersFromNav(page)

  for (const link of links) {
    expect(link.cap, `${link.href} advertises no leader letter`).toMatch(/^,[A-Z0-9]$/)
    const letter = link.cap.slice(1).toLowerCase()

    /* Arrive from somewhere that is NOT the destination, or a chord that dispatched nowhere
       would be indistinguishable from one that worked. Home is the way in and is itself in the
       ring, so the letter that leads to it is pressed from the screen after it. */
    const from = link.href === '#/' ? '#/capture' : '#/'
    await page.goto(`/${from}`)
    await expect(page.locator(VIEW[from as (typeof RING)[number]])).toBeVisible()

    await page.keyboard.press(',')
    await page.keyboard.press(letter)
    await expect(
      page.locator(VIEW[link.href as (typeof RING)[number]]),
      `,${letter.toUpperCase()} did not arrive at ${link.href}`,
    ).toBeVisible()
    expect(page.url()).toContain(link.href)
  }
})

/* THE STEP IS ADVERTISED, AND WHERE IT IS ADVERTISED MOVED. Until the Banchi rebuild the nav
 * carried a pair of ⌘←/⌘→ keycaps at the end of the strip, and the case that stood here
 * measured their bounding box against the last link's. The owner ruled the chips out and chose
 * a single keyboard reference instead, so the layout fact is gone and the REQUIREMENT is not:
 * docs/DESIGN.md's "every choice shows its key" is still owed, and it is owed in the two
 * places a person can actually collect it — the accessibility tree, and the sheet.
 *
 * Nothing here asserts that the chips are absent. An absence is a layout choice too, and
 * pinning it would make this file an obstacle to the owner changing their mind. */
test('the step is announced on the sidebar and documented in the shortcuts sheet', async ({
  page,
}) => {
  await open(page, RING[0])

  /* The caps were aria-hidden even when they existed — two arrow glyphs announce as nothing
     anyone could act on — so this is the form the fact has always had to take, and it is now
     the only one on the chrome itself. */
  await expect(page.locator(NAV)).toHaveAttribute(
    'aria-keyshortcuts',
    'Meta+ArrowLeft Meta+ArrowRight',
  )

  await page.keyboard.press('?')
  const sheet = page.locator('.app-keys[role="dialog"]')
  await expect(sheet).toBeVisible()

  /* Both caps, in one row, described by a sentence rather than left as two glyphs. Read as
     text off the sheet's own rows: the keycaps there are bare `<kbd>` and NOT aria-hidden,
     which is the difference between a reference and a decoration. */
  const stepRow = sheet.locator('.app-keys-row', { has: page.locator('kbd', { hasText: '⌘←' }) })
  await expect(stepRow).toHaveCount(1)
  await expect(stepRow.locator('kbd')).toHaveText(['⌘←', '⌘→'])
  await expect(stepRow.locator('.app-keys-does')).not.toBeEmpty()

  await page.keyboard.press('Escape')
  await expect(sheet).toHaveCount(0)
})

test('the sheet is reachable from the palette, and lists every letter the sidebar draws', async ({
  page,
}) => {
  await open(page, RING[0])
  const links = await lettersFromNav(page)

  /* ⌘K, then the word a person would type for it. The owner's ruling is that the sheet is
     reachable from the palette AND from `?`; the other case presses `?`, so this one goes the
     long way deliberately. */
  await page.keyboard.press('Meta+k')
  const palette = page.locator('.bn-cmdk[role="dialog"]')
  await expect(palette).toBeVisible()
  await palette.locator('input').fill('keyboard shortcuts')
  await page.keyboard.press('Enter')

  const sheet = page.locator('.app-keys[role="dialog"]')
  await expect(sheet).toBeVisible()
  await expect(palette).toHaveCount(0)

  /* THE SHEET IS THE ONLY DOCUMENTATION OF THE LEADER NOW, so it has to hold every letter the
     sidebar hands out — including `H`, which arrived with Home and is the letter a stale sheet
     would be missing. Derived from the nav rather than typed out here, so a tenth screen with
     a key fails this case instead of quietly not being in it. */
  const caps = await sheet.evaluate((el) =>
    Array.from(el.querySelectorAll('kbd')).map((k) => (k.textContent ?? '').trim()),
  )
  for (const link of links) {
    expect(caps, `the sheet documents no ${link.cap} for ${link.href}`).toContain(link.cap)
  }
})

/* `App.tsx`'s own `CHORD_MS`, mirrored rather than imported — a spec that imports the shell
 * pulls React into the test process for one integer. What the case below needs from it is a
 * BOUND that separates the two ways an arm can end, and half the window does that with room to
 * spare. If `CHORD_MS` ever drops near this figure, move it. */
const CHORD_MS = 1000

test('the armed leader is disarmed by arriving somewhere', async ({ page }) => {
  await open(page, RING[0])

  /* A chord is spent on arriving, so an arm that survives an arrival is an arm nobody is
     holding — and the next key is then eaten on a screen the operator did not press it from.
     Arm the leader, step away with the other keyboard, and the sidebar must not still be
     claiming the next press.

     WHAT IS MEASURED IS WHEN THE ARM ENDED, NOT WHETHER IT HAS ENDED YET, and that is the whole
     of why this case is written this way. The arm expires on its own after CHORD_MS, so a plain
     auto-retrying `not.toHaveAttribute` passes the moment that timer fires whatever the code
     does — observed: with the disarm deleted, it went green. The first fix for that sampled at a
     FIXED POINT instead, two animation frames after the hash changed, on the reasoning that
     React would certainly have committed by then. IT IS NOT CERTAIN: measured on this tree, that
     read fails ~3% of runs at fourteen workers, because under load the arrival's effect has not
     committed two frames later and the case then reports a disarm that works as broken.

     A FRAME COUNT IS A DURATION IN DISGUISE. So this waits for the disarm to actually happen —
     no deadline of its own — and then asks the question the fixed sample was really asking:
     did it happen because we ARRIVED, or because the clock ran out? A disarm on arrival lands in
     a frame or two; an expiry lands at CHORD_MS. Half the window tells them apart, and the
     deleted-disarm mutation this case exists to catch still fails it. */
  await page.evaluate(
    ({ selector, chord }) => {
      const w = window as unknown as { __disarmMs?: number | null }
      w.__disarmMs = null
      window.addEventListener(
        'hashchange',
        () => {
          const nav = document.querySelector(selector)
          /* The shell going missing is not a disarm. Reported as a figure no bound can accept
             rather than as a silent null, which would hang the poll below on the wrong subject. */
          if (nav === null) {
            w.__disarmMs = chord * 10
            return
          }
          const t0 = performance.now()
          if (nav.getAttribute('data-armed') === null) {
            w.__disarmMs = 0
            return
          }
          const seen = new MutationObserver(() => {
            if (nav.getAttribute('data-armed') === null) {
              w.__disarmMs = performance.now() - t0
              seen.disconnect()
            }
          })
          seen.observe(nav, { attributes: true, attributeFilter: ['data-armed'] })
        },
        { once: true },
      )
    },
    { selector: NAV, chord: CHORD_MS },
  )

  await page.keyboard.press(',')
  await expect(page.locator(NAV)).toHaveAttribute('data-armed', 'true')

  await page.keyboard.press('Meta+ArrowRight')
  await expect(page.locator(VIEW['#/capture'])).toBeVisible()

  await expect
    .poll(() => page.evaluate(() => (window as unknown as { __disarmMs?: number | null }).__disarmMs), {
      message: 'the leader never disarmed at all after arriving',
    })
    .not.toBeNull()
  const ms = await page.evaluate(
    () => (window as unknown as { __disarmMs?: number | null }).__disarmMs as number,
  )
  expect(
    ms,
    `the arm outlived the arrival by ${Math.round(ms)}ms — at or near ${CHORD_MS}ms it was not ` +
      'spent on arriving at all, it expired on its own clock.',
  ).toBeLessThan(CHORD_MS / 2)
})

test('the palette ranks a label hit above a keyword hit', async ({ page }) => {
  /* Runs's own `keywords` carries "my pricing" (D109's one-press door into the live book), and
     Runs is declared before Pricing in ROUTES — so a plain substring filter over the whole
     joined string left Runs sitting above Pricing for "pricing" on declaration order alone. */
  await open(page, RING[0])
  await page.keyboard.press('Meta+k')
  const palette = page.locator('.bn-cmdk[role="dialog"]')
  await expect(palette).toBeVisible()

  await palette.locator('input').fill('pricing')
  await expect(palette.locator('.bn-cmdk-item').first()).toHaveText(/Pricing/)

  await palette.locator('input').fill('runs')
  await expect(palette.locator('.bn-cmdk-item').first()).toHaveText(/Runs/)
})

/* HOME'S REVIEW TILE MUST NOT SAY "NOTHING WAITING" WHILE A CARD SITS PARKED.
 *
 * `#/review`'s own headline counts both queues — `everyone.length + done`, where `everyone` is
 * `review` and `parked` merged by position (`ReviewQueue.tsx:rowsOf`/`oneCardPerPosition`) —
 * and draws `counts.parked` beside it whenever it is nonzero, unconditionally. Home's tile used
 * to gate its whole sentence on `review === 0` alone, so a parked-only queue (nothing in the
 * main queue, one card parked) painted green and said "nothing waiting" while `#/review` itself
 * offered that same card for an answer. This is CLAUDE.md's own rule — "every figure on Home is
 * the one that stage's own screen draws, read from the same source" — applied to the Review
 * tile specifically. */
test('the Review tile never says nothing waiting while a card is parked', async ({ page }) => {
  await stub(page)
  /* Registered AFTER `stub`'s own `/status` handler — Playwright takes the newest match, the
     same mechanism the pricing stub comment above documents — so this is the one `/status`
     the page actually receives. */
  await page.route(/\/status$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        captures_root: 'captures',
        store: 'inventory/store.sqlite',
        store_exists: true,
        cards: 0,
        states: {},
        queues: { review: 0, parked: 1 },
        next_index: {},
      }),
    }),
  )
  await page.goto('/#/')
  await expect(page.locator(VIEW['#/'])).toBeVisible()

  const tile = page.locator('a.home-stage[href="#/review"]')
  await expect(tile).toBeVisible()
  await expect(tile).not.toContainText('nothing waiting')
  await expect(tile.locator('.home-stage-figure')).not.toHaveText('0')
  await expect(tile).not.toHaveClass(/home-stage-ok/)
})

/* AN UNKNOWN HASH GETS THE OWNER'S SHELL, NOT NONE.
 *
 * `NoSuchView` used to draw chromeless — no sidebar, no nav, no way back but its own three
 * doors, one of which sent the OWNER to the FULFILLER's screen. A fat-fingered URL cost the
 * owner their whole nav, and the one spare door crossed personas for no reason. */
test('an unknown route keeps the owner’s shell, and offers no door to the Fulfiller', async ({
  page,
}) => {
  await stub(page)
  await page.goto('/#/no-such-screen')

  /* The sidebar is still on screen — this is the owner's shell, not a chromeless orphan. */
  await expect(page.locator(NAV)).toBeVisible()
  await expect(page.locator('.no-such-view')).toBeVisible()

  await expect(page.locator('.no-such-view-door[href="#/fulfillment"]')).toHaveCount(0)
  await expect(page.locator('.no-such-view-door[href="#/"]')).toBeVisible()
  await expect(page.locator('.no-such-view-door[href="#/inventory"]')).toBeVisible()
})

/* ================================================================================================
   ONE ROUTES ROW IS THE WHOLE REGISTRATION (the owner's durability rule, 2026-09-23; D275)
   ================================================================================================

   "Say a new page in the sidebar gets built tomorrow, it should be able to autocall/inherit the
   properties of the other pages." So a new screen is ONE `ROUTES` row plus a view that returns
   `<Page>`, and nothing else in the shell is edited.

   THE PROOF ADDS A ROW THE REPO DOES NOT HAVE, IN THE BROWSER, AND EDITS NOTHING. The dev server
   serves `App.tsx` as a module; this case intercepts that one response and inserts one row and a
   four-line view into it. Nothing else in the served app changes. If the row then has its nav
   link, its palette entry, its jump entry and its own keys in the sheet, its tab title and the
   page scaffold, the shell derived every one of them from the row. A shell that listed routes a
   second time anywhere would miss the row, and this case would go red naming what it missed.
   The row's view is built from `Page` and React's own `createElement`, both of which the served
   module already imports, so the view is exactly "a view that returns <Page>". */
/** Serve `App.tsx` with one row the repo does not have, inserted FIRST in `ROUTES`. First on
 *  purpose: its group is the library, which the nav draws after three other groups, so a shell
 *  that orders anything by declaration rather than by what it draws puts the row in the wrong
 *  place, and the ring case below goes red on that. The row carries a letter (`z`, which no screen takes), so it is in the
 *  ring and the `,` chord as well as the nav. */
async function serveThrowawayRow(page: Page): Promise<void> {
  await page.route(/\/src\/App\.tsx(\?|$)/, async (route) => {
    const response = await route.fetch()
    const body = await response.text()
    const react = /import (\w+) from "(\/node_modules\/\.vite\/deps\/react\.js[^"]*)"/.exec(body)
    expect(react, 'the served App.tsx no longer imports React the way this case reads it').not.toBeNull()
    const h = `${react![1]}.createElement`
    const view = `function __Throwaway() { return ${h}(Page, null, ${h}("p", null, "A throwaway screen.")) }\n`
    const row =
      '{ path: "/throwaway", label: "Throwaway", icon: "grid", view: __Throwaway, persona: "owner", group: "library", hotkey: "z", nav: true, ' +
      'keys: { rows: [{ keys: ["Z"], does: "Throw it away" }] } },\n'
    const anchor = 'export const ROUTES = [\n'
    expect(body.includes(anchor), 'the served App.tsx has no `export const ROUTES = [` line').toBe(true)
    await route.fulfill({ response, body: body.replace(anchor, `${view}${anchor}${row}`) })
  })
}

test('a throwaway ROUTES row gets its nav, palette, keys, title and scaffold with no other edit', async ({ page }) => {
  await stub(page)
  await serveThrowawayRow(page)

  await page.goto('/#/')
  await expect(page.locator(VIEW['#/'])).toBeVisible()

  // NAV: the row is a link in the sidebar
  await expect(page.locator(`${NAV_LINK}[href="#/throwaway"]`)).toHaveText(/Throwaway/)

  // PALETTE: its Screens group lists it, and Enter goes there
  await page.keyboard.press('Meta+k')
  const palette = page.getByRole('dialog', { name: 'Go to' })
  await expect(palette).toBeVisible()
  await palette.getByRole('combobox').fill('throwaway')
  await expect(palette.getByRole('option').first()).toHaveText(/Throwaway/)
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/#\/throwaway$/)

  // SCAFFOLD: one page, one h1 from the row's own label
  await expect(page.locator('[data-bn-page]')).toHaveCount(1)
  await expect(page.locator('h1')).toHaveText('Throwaway')
  await expect(page.getByText('A throwaway screen.')).toBeVisible()

  // TITLE: the fixed tab title
  await expect(page).toHaveTitle('番地 throwaway')

  // KEYS: a jump entry, and the screen's own group, open by default on its own screen
  await page.locator('h1').focus()
  await page.keyboard.press('?')
  const sheet = page.getByRole('dialog', { name: 'Keyboard shortcuts' })
  await expect(sheet).toBeVisible()
  await expect(sheet.locator('dd', { hasText: /^Throwaway/ })).toHaveCount(1)
  await expect(sheet.getByRole('heading', { name: 'Throwaway' })).toBeVisible()
  await expect(sheet.locator('dd', { hasText: 'Throw it away' })).toBeVisible()
})

/* THE RING IS THE ORDER THE NAV DRAWS, NOT THE ORDER ROUTES DECLARES (D51: the step walks the
   strip in the order it is drawn). The nav draws by group, so a row declared outside its group's
   block is drawn in its group, and the step must reach it there. The throwaway row is declared
   first and drawn in the library group, after the Sell group. */
test('a throwaway row with a letter takes its drawn place in the ring, and its chord works', async ({ page }) => {
  await stub(page)
  await serveThrowawayRow(page)
  await page.goto('/#/')
  await expect(page.locator(VIEW['#/'])).toBeVisible()

  const drawn = await page.evaluate(
    (selector) => Array.from(document.querySelectorAll<HTMLAnchorElement>(selector)).map((a) => a.getAttribute('href') ?? ''),
    NAV_LINK,
  )
  /* Drawn in its own group, after the Sell group, and not first where `ROUTES` declares it. */
  expect(drawn.filter((href) => href !== '#/throwaway'), 'the nav no longer draws the ring the roster pins').toEqual([...RING])
  expect(drawn.indexOf('#/throwaway'), 'the throwaway row is drawn first, in declaration order').toBeGreaterThan(drawn.indexOf('#/revenue'))

  /* Step from the first drawn row to the last. Each press must land on the NEXT DRAWN row. The
     wait is for the nav to mark the row current, not for the hash: the step reads the path the
     shell has RENDERED, so a press sent between the hash change and that render steps from the
     screen before. */
  const arrived = (href: string) => page.locator(`${NAV_LINK}[href="${href}"][aria-current="page"]`)
  for (const next of drawn.slice(1)) {
    await page.keyboard.press('Meta+ArrowRight')
    await expect(arrived(next), `the step did not go to ${next}`).toBeVisible()
  }
  // and back again, to the first
  for (const previous of [...drawn].reverse().slice(1)) {
    await page.keyboard.press('Meta+ArrowLeft')
    await expect(arrived(previous), `the step back did not go to ${previous}`).toBeVisible()
  }

  // THE CHORD: `,` then its letter arrives there
  await page.keyboard.press(',')
  await page.keyboard.press('z')
  await expect(arrived('#/throwaway')).toBeVisible()
  await expect(page.getByText('A throwaway screen.')).toBeVisible()
})

/* ---- the palette is "Go to", and it finds cards (D276, amends D95) ------------------ */

test('the palette lists every screen, off-nav ones included, and finds a card', async ({ page }) => {
  await open(page, RING[0])
  await page.route(/\/search\?/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        query: 'abra',
        groups: [
          {
            sku: '4242', names: ['Abra'], number: '63', printed_total: '102', number_display: '063/102',
            set_hint: null, set: 'Base Set', rarity: 'Common', condition: 'Near Mint',
            listed: { pushed: 0, staged: 0, live: 0 }, sold_here: 0, live_as_of: null, on_hand: 1, listable: 1, copies: [],
          },
        ],
      }),
    }),
  )
  await page.keyboard.press('Meta+k')
  const palette = page.getByRole('dialog', { name: 'Go to' })
  await expect(palette).toBeVisible()

  // every screen, the three off the nav included (UX-003)
  for (const label of ['Product history', 'Kit', 'Cards to pull']) {
    await expect(palette.getByRole('option', { name: new RegExp(`^${label}`) })).toHaveCount(1)
  }

  // a card (UX-022, FLT-28): typed, found, and opened as its product
  const input = palette.getByRole('combobox')
  await input.fill('abra')
  const card = palette.getByRole('option', { name: /Abra/ })
  await expect(card).toBeVisible()
  await expect(palette.locator('.bn-cmdk-group', { hasText: 'Cards' })).toBeVisible()
  /* The product it opens reads its own history. That is the product lane's screen and not this
     case's subject, so its reads are answered with a refusal here rather than left to the seal. */
  await page.route(new RegExp(`^[a-z+.-]+://[^/]+:${CAPTURE_PORT}/(?!search\\?|status$)`), (route) =>
    route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ error: { code: 'not_in_this_case', message: 'Not stubbed in this case.' } }) }),
  )
  await card.click()
  /* `openSheet('product', …)`: a registered product sheet opens over the page; with none, the
     product's own page opens. Either is the product, by its SKU. */
  await expect
    .poll(() => page.evaluate(() => window.location.hash.startsWith('#/product?sku=4242') || document.querySelector('[data-bn-sheet-host="product"]') !== null))
    .toBe(true)
})

test('a refused card search hides the Cards group and says so in one line', async ({ page }) => {
  await open(page, RING[0])
  await page.route(/\/search\?/, (route) =>
    route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ error: { code: 'demo_not_recorded', message: 'Not in this demo.' } }),
    }),
  )
  await page.keyboard.press('Meta+k')
  const palette = page.getByRole('dialog', { name: 'Go to' })
  await palette.getByRole('combobox').fill('abra')
  /* The line is the demo's own sentence in the published build (`__BN_DEMO__`); this dev build
     says the server did not answer. Either way it is ONE line, and no Cards group. "abra" matches
     no screen, so the palette's own "Nothing matches" line is the second line this could draw.
     It is counted too, and it must not show beside the refusal. */
  await expect(palette.locator('.bn-cmdk-note')).toHaveCount(1)
  await expect(palette.locator('.bn-cmdk-empty')).toHaveCount(0)
  await expect(palette.locator('.bn-cmdk-group', { hasText: 'Cards' })).toHaveCount(0)
  // and the screens still answer beside it, under the one refusal line and no empty line
  await palette.getByRole('combobox').fill('pricing')
  await expect(palette.getByRole('option').first()).toHaveText(/Pricing/)
  await expect(palette.locator('.bn-cmdk-note')).toHaveCount(1)
  await expect(palette.locator('.bn-cmdk-empty')).toHaveCount(0)
})

/* ---- focus: the layers hold it, and a navigation hands it to the screen ------------------------ */

/** Tab forward N times and collect whether each stop was inside `root`. */
async function tabStops(page: Page, root: string, n: number): Promise<boolean[]> {
  const inside: boolean[] = []
  for (let i = 0; i < n; i++) {
    await page.keyboard.press(i % 3 === 2 ? 'Shift+Tab' : 'Tab')
    inside.push(await page.evaluate((sel) => document.querySelector(sel)?.contains(document.activeElement) ?? false, root))
  }
  return inside
}

test('focus never escapes the open palette, keys sheet or phone drawer (UX-014)', async ({ page }) => {
  await open(page, RING[0])

  await page.keyboard.press('Meta+k')
  await expect(page.locator('.bn-cmdk[role="dialog"]')).toHaveAttribute('aria-modal', 'true')
  expect(await tabStops(page, '.bn-cmdk', 12)).not.toContain(false)
  await page.keyboard.press('Escape')
  await expect(page.locator('.bn-cmdk')).toHaveCount(0)

  await page.keyboard.press('?')
  await expect(page.locator('.app-keys[role="dialog"]')).toBeVisible()
  expect(await tabStops(page, '.app-keys', 12)).not.toContain(false)
  await page.keyboard.press('Escape')
  await expect(page.locator('.app-keys')).toHaveCount(0)

  await page.setViewportSize({ width: 390, height: 844 })
  const more = page.getByRole('button', { name: 'More' })
  await more.click()
  const drawer = page.locator('.bn-drawer[role="dialog"]')
  await expect(drawer).toHaveAttribute('aria-modal', 'true')
  await expect(more).toHaveAttribute('aria-expanded', 'true')
  await expect.poll(() => page.evaluate(() => document.querySelector('.bn-drawer')?.contains(document.activeElement))).toBe(true)
  expect(await tabStops(page, '.bn-drawer', 20)).not.toContain(false)
  await page.keyboard.press('Escape')
  await expect(drawer).toHaveCount(0)
  // and focus goes back to the one door it came from
  await expect(more).toBeFocused()
})

test('no global key acts under an open layer', async ({ page }) => {
  await open(page, RING[0])
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: 'More' }).click()
  await expect(page.locator('.bn-drawer')).toBeVisible()
  await expect.poll(() => page.evaluate(() => document.querySelector('.bn-drawer')?.contains(document.activeElement))).toBe(true)

  // the chord does not arm, the step does not step, and the rail does not move, behind the drawer
  /* Read, not assumed: at this width the rail starts folded, so "not folded" would pass on a
     press that unfolded it. */
  const railBefore = await page.locator('.bn-shell').getAttribute('data-rail')
  await page.keyboard.press(',')
  await page.keyboard.press('c')
  await page.keyboard.press('Meta+ArrowRight')
  await page.keyboard.press('Meta+.')
  await page.waitForTimeout(200)
  expect(await page.evaluate(() => window.location.hash)).toBe('#/')
  await expect(page.locator('.bn-drawer')).toBeVisible()
  expect(await page.locator('.bn-shell').getAttribute('data-rail'), 'Cmd-. moved the rail under the drawer').toBe(railBefore)
})

test('the first Tab reaches the skip link, and a navigation hands focus to the screen (UX-092)', async ({ page }) => {
  await open(page, RING[0])
  await page.keyboard.press('Tab')
  const skip = page.getByRole('button', { name: 'Skip to the screen' })
  await expect(skip).toBeFocused()
  await page.keyboard.press('Enter')
  await expect.poll(() => page.evaluate(() => document.activeElement?.closest('.bn-view') !== null)).toBe(true)

  // a sidebar link pressed from the keyboard: focus lands on the new screen, not on the link
  await page.locator(`${NAV_LINK}[href="#/codes"]`).focus()
  await page.keyboard.press('Enter')
  await expect(page.locator(VIEW['#/codes'])).toBeVisible()
  await expect.poll(() => page.evaluate(() => document.activeElement?.closest('.bn-view') !== null && document.activeElement?.closest('.bn-side') === null)).toBe(true)

  // a chord from nowhere: the same
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
  await page.keyboard.press(',')
  await page.keyboard.press('g')
  await expect(page.locator(VIEW['#/graveyard'])).toBeVisible()
  await expect.poll(() => page.evaluate(() => document.activeElement?.closest('.bn-view') !== null)).toBe(true)
})

test('the phone tab bar lights More when the screen is behind it (UX-046)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await open(page, '#/pricing')
  const more = page.getByRole('button', { name: 'More' })
  await expect(more).toHaveAttribute('aria-current', 'page')
  await expect(page.locator('.bn-topbar').getByRole('button', { name: 'Menu' }), 'one door to the drawer (UX-072)').toHaveCount(0)

  await open(page, '#/capture')
  await expect(more).not.toHaveAttribute('aria-current', 'page')
  await expect(page.locator('.bn-tabbar a[href="#/capture"]')).toHaveAttribute('aria-current', 'page')
})
