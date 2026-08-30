import { test, expect, type Page, type Route } from '@playwright/test'

/* THE SHELL'S KEYBOARD, AND THE FIRST TEST THIS APP HAS HAD OF THE STRIP AT THE TOP OF EVERY
 * SCREEN.
 *
 * `app/src/App.tsx` carries two keyboards — the `,` chord that JUMPS to a route by name, and
 * (D50, 2026-08-30) Cmd-arrow, which STEPS along the strip in the order it is drawn. Neither
 * had an assertion of any kind: `make design-check` covered the Fulfilment view, the review
 * queue, the run panel, the capture claims, the inventory walk and the pricing screen, and
 * nothing at all covered the chrome all of them sit under.
 *
 * THE STRONGEST CASES HERE ARE THE TWO ENDS AND THE THREE REFUSALS, because each is a rule
 * that would otherwise live only in a comment: the step never wraps, a bare arrow is not the
 * shell's, a held Cmd inside a text field belongs to the caret, and a screen with no chrome
 * has no keys at all. A step that quietly gained a wrap, or quietly started eating the caret
 * keys, would pass every other file in this directory.
 *
 * WHAT THIS CANNOT SEE, said plainly rather than left to be assumed. Playwright presses keys
 * through the debugging protocol, which never fires the BROWSER's own shortcuts — so a case
 * here proves the handler steps and that it calls `preventDefault`, and it cannot prove that
 * Chrome or Safari then declines to go Back. That half is one press at the rig, and D50 names
 * it as the thing to check first if the step ever appears to fire twice.
 *
 * NOT A HARNESS TEST AND MUST NOT BECOME ONE. `docs/GATES.md`'s contract is seven Python tests
 * at the Stop hook; this starts a browser.
 */

/** The ring, in the order `app/src/App.tsx` draws it: the run group, then the look group. The
 *  hash form verbatim, for the reason every other spec here records — a path-style
 *  '/inventory' is served index.html by Vite, mounts with an empty hash and renders the
 *  capture screen, which is a passing navigation to the wrong view. */
const RING = ['#/', '#/runs', '#/review', '#/pricing', '#/inventory'] as const

/** What each of those routes renders, so a step is asserted to have ARRIVED rather than
 *  merely to have changed a string. A hash the shell does not recognise still changes
 *  `location.hash`; only the view proves the route resolved. */
const VIEW: Record<(typeof RING)[number], string> = {
  '#/': 'main.capture',
  '#/runs': 'main.runs',
  '#/review': 'main.review',
  '#/pricing': 'main.pricing',
  '#/inventory': 'main.inventory',
}

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
  await page.route(/\/boxes$/, (route) => json(route, { boxes: [] }))
  await page.route(/\/queues$/, (route) => json(route, { review: [], parked: [] }))
  await page.route(/\/search\?/, (route) => json(route, { query: '', groups: [] }))
  await page.route(/\/games$/, (route) => json(route, { games: [] }))
  await page.route(/\/status$/, (route) => json(route, { boxes: [], next: null }))
  await page.route(/\/pipeline\/runs$/, (route) => json(route, { runs: [] }))
  await page.route(/\/photo\//, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="63" height="88"/>',
    }),
  )
}

/** One card, in the shape `GET /inventory` answers with — enough for `BoxBrowse` to draw its
 *  walk, which is what puts a text field on screen. The screen renders "No cards captured
 *  yet." and NO search field for an empty store, so the one case that needs a caret needs a
 *  card. Every decoration `server/capture_server.py:do_inventory` adds is here: the screen
 *  renders them and computes none of them, so a row missing one takes the panel down and the
 *  case fails as "element not found", which reads exactly like an unregistered route. */
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
    section: 1,
    card: 1,
    box_name: 'ME01 commons',
    section_start: 1,
    section_end: null,
    box_total: 1,
    box_closed: false,
    fraction: 1,
    neighbors: null,
    gaps_in_section: 0,
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

test('the step walks the strip in the order it is drawn, and the last screen is the last', async ({
  page,
}) => {
  await open(page, RING[0])

  for (const next of RING.slice(1)) {
    await page.keyboard.press('Meta+ArrowRight')
    await expect(page.locator(VIEW[next])).toBeVisible()
    expect(page.url()).toContain(next)
  }

  /* NEVER A WRAP — `BoxBrowse` says it in those words about its own arrows and D50 takes the
     rule: a row that starts again is a row you can no longer count along. The press is still
     consumed (see the case below on the Gallery for what "consumed" is worth), so what is
     asserted here is that it lands nowhere new.

     IT IS ALSO WHAT KEEPS THE FULFILLER OUT OF THE RING, which is why there is no case of its
     own for his view. The ring is every route with a `hotkey`, so the mistake that would put
     him in it is a hotkey added to his row in ROUTES — and this assertion goes red the moment
     that happens, because the step from the last owner screen would land on #/fulfillment.
     A case pressing the step ON his view could not: `enabled` refuses there AND the ring does,
     so no single mutation makes it fail, and docs/GATES.md's rule is that a case which cannot
     fail is not coverage. `app/tests/fulfillment.spec.ts` asserts the nav is not drawn. */
  await page.keyboard.press('Meta+ArrowRight')
  await expect(page.locator(VIEW['#/inventory'])).toBeVisible()
  expect(page.url()).toContain('#/inventory')
})

test('the step walks back, and the first screen is the first', async ({ page }) => {
  await open(page, '#/inventory')

  for (const previous of [...RING].reverse().slice(1)) {
    await page.keyboard.press('Meta+ArrowLeft')
    await expect(page.locator(VIEW[previous])).toBeVisible()
    expect(page.url()).toContain(previous)
  }

  await page.keyboard.press('Meta+ArrowLeft')
  await expect(page.locator(VIEW['#/'])).toBeVisible()
})

test('a bare arrow is not the shell’s', async ({ page }) => {
  await open(page, '#/runs')

  /* The screens own the unmodified arrows — `BoxBrowse` walks a box with them and `RunPanel`
     steps the crop preview — so the modifier is not decoration on this binding, it is what
     keeps the shell out of their key. */
  await page.keyboard.press('ArrowRight')
  await page.keyboard.press('ArrowLeft')
  await expect(page.locator(VIEW['#/runs'])).toBeVisible()
  expect(page.url()).toContain('#/runs')
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
  await expect(page.locator('.app-nav')).toBeVisible()

  /* The gallery has chrome, so the listener is mounted — and it is deliberately not a step in
     any loop, so there is no next one along from it and the press is left alone rather than
     given an invented landing. Playwright's key never triggers the browser's own Back, so
     what this asserts is the shell not moving; the browser keeping the key is the half only
     the rig can see. */
  await page.keyboard.press('Meta+ArrowRight')
  await page.keyboard.press('Meta+ArrowLeft')
  expect(page.url()).toContain('#/gallery')
})

test('the strip advertises the step once, at the end of the ring', async ({ page }) => {
  await open(page, RING[0])

  /* docs/DESIGN.md: "Every choice shows its key". One hint because there is one binding —
     `,C` is per route because the destination is what changes, and this reaches whichever
     screen is next. */
  const hint = page.locator('.app-nav-step')
  await expect(hint).toHaveCount(1)
  await expect(hint.locator('kbd')).toHaveText(['⌘←', '⌘→'])

  /* Trailing the ring rather than the bar: the last link before it is the last route the step
     can reach, and the two routes after it are the two it cannot. */
  const links = page.locator('.app-nav-link')
  const lastRing = links.nth(RING.length - 1)
  await expect(lastRing).toHaveAttribute('href', '#/inventory')
  const ring = await lastRing.boundingBox()
  const chips = await hint.boundingBox()
  const aside = await links.last().boundingBox()
  expect(ring && chips && aside).toBeTruthy()
  expect(chips!.x).toBeGreaterThan(ring!.x)
  expect(chips!.x).toBeLessThan(aside!.x)

  /* The chips are aria-hidden — two arrow glyphs announce as nothing anyone could act on — so
     the nav carries the same fact in the form a screen reader can use. */
  await expect(hint).toHaveAttribute('aria-hidden', 'true')
  await expect(page.locator('nav.app-nav')).toHaveAttribute(
    'aria-keyshortcuts',
    'Meta+ArrowLeft Meta+ArrowRight',
  )
})

test('the armed leader is disarmed by arriving somewhere', async ({ page }) => {
  await open(page, RING[0])

  /* A chord is spent on arriving, so an arm that survives an arrival is an arm nobody is
     holding — and the next key is then eaten on a screen the operator did not press it from.
     Arm the leader, step away with the other keyboard, and the strip must not still be
     claiming the next press.

     READ AT THE MOMENT OF ARRIVAL, AND THAT IS THE WHOLE OF WHY THIS CASE IS WRITTEN THIS WAY.
     The arm expires on its own after CHORD_MS, so an auto-retrying `not.toHaveAttribute` here
     passes as soon as that timer fires whatever the code does — observed: with the disarm
     deleted, the plain assertion went green. Two frames after the hash changes is long after
     React has committed the arrival and its effects, and ~30ms into a 1000ms window. */
  await page.evaluate(() => {
    ;(window as unknown as { __armed?: string | null }).__armed = 'not read'
    window.addEventListener(
      'hashchange',
      () => {
        requestAnimationFrame(() =>
          requestAnimationFrame(() => {
            ;(window as unknown as { __armed?: string | null }).__armed =
              document.querySelector('nav.app-nav')?.getAttribute('data-armed') ?? null
          }),
        )
      },
      { once: true },
    )
  })

  await page.keyboard.press(',')
  await expect(page.locator('nav.app-nav')).toHaveAttribute('data-armed', 'true')

  await page.keyboard.press('Meta+ArrowRight')
  await expect(page.locator(VIEW['#/runs'])).toBeVisible()
  await expect
    .poll(() => page.evaluate(() => (window as unknown as { __armed?: string | null }).__armed))
    .toBeNull()
})
