import { test, expect, type Locator, type Page } from '@playwright/test'

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
 * the capture screen — a passing navigation to the wrong view. The `beforeEach` below asserts
 * the view is actually on screen before any test runs, so a route that has not been
 * registered fails here and loudly rather than as nine confusing measurements of nothing.
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
}

function inventoryBody(cards: Record<string, FixtureCard>) {
  const rows: Record<string, unknown> = {}
  for (const [key, card] of Object.entries(cards)) {
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
      state: card.state,
      state_at: '2026-08-13T11:00:00+00:00',
      run: null,
      ...(card.label === undefined ? {} : { label: card.label, section: 1, card: card.index }),
    }
  }
  return { version: 1, cards: rows }
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
    state: 'live',
    name: 'Pidgeot ex',
    label: 'Box 3 · Section 2 · Card 1',
    photo: '/captures/3/026.jpg',
  },
  '3/7': {
    box: 3,
    index: 7,
    state: 'live',
    name: 'Charizard ex',
    label: 'Box 3 · Section 1 · Card 7',
    photo: '/captures/3/007.jpg',
  },
  '1/3': {
    box: 1,
    index: 3,
    state: 'live',
    name: 'Iono',
    label: 'Box 1 · Section 1 · Card 3',
    photo: '/captures/1/003.jpg',
  },
  // Captured but never listed. It must never appear: marking it sold would record a sale of
  // something no buyer could have ordered.
  '2/4': { box: 2, index: 4, state: 'captured', name: null, label: 'Box 2 · Section 1 · Card 4', photo: null },
  // For sale, and undecorated — `do_inventory` leaves a row bare when its box or index will
  // not coerce. It must be counted on screen rather than dropped in silence.
  '9/12': { box: 9, index: 12, state: 'live', name: 'Great Ball', photo: '/captures/9/012.jpg' },
}

/* The stand-in photo, drawn at a card's aspect ratio.
 *
 * SVG rather than a base64 PNG because a PNG has to be handed to `route.fulfill` as a Buffer,
 * and `app/tsconfig.json` declares `"types": ["vite/client"]` with no Node types — so `Buffer`
 * does not exist in this project's type world and adding it would be a dependency and a
 * tsconfig edit for a fixture. A string body needs neither, and this one is legible in the
 * diff besides. The photo assertion measures the element's box, which the stylesheet sizes
 * from the 63x88 card shape rather than from the file, so the bytes only have to decode. */
const PHOTO_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="63" height="88">' +
  '<rect width="63" height="88" fill="#52555b"/></svg>'

/** Sales the page recorded, in order, so a test can assert what the screen actually sent.
 *
 *  `undo` is the field `server/capture_server.py:do_mark_sold` reads: `{}` records a sale and
 *  `{"undo": true}` reverses one, on the same route in both directions. Recorded off the
 *  request body rather than off the method, because the method is `POST` either way and a
 *  test that read only the method would pass while the screen sold a card twice. */
type Wire = { method: string; url: string; undo: boolean }

/* How `GET /inventory` behaves, read at request time so a test can change its mind.
 *
 * MUTABLE RATHER THAN A COUNT OF READS, and that is not a style choice: `main.tsx` mounts
 * under StrictMode, which double-invokes every effect in dev, so the view reads the inventory
 * twice on one mount and discards the first answer through its own `livePage` flag. A stub
 * that refused "the first read" therefore refused the answer nobody was listening to and the
 * screen rendered as though nothing had gone wrong — measured, before this was written. A
 * flag the test flips is indifferent to how many times React asks. */
type Mood = { fail?: boolean; slow?: boolean }

async function stubServer(page: Page, wire: Wire[], mood: Mood = {}): Promise<void> {
  // The sold route first: nothing else may answer it, and a stub that quietly 404s would make
  // every mark-sold test measure the failure path while reading like the happy one.
  await page.route(/\/inventory\/\d+\/\d+\/sold$/, async (route) => {
    const request = route.request()
    const sent: unknown = request.postDataJSON()
    wire.push({
      method: request.method(),
      url: request.url(),
      undo: (sent as { undo?: unknown } | null)?.undo === true,
    })
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
  })
  await page.route(/\/inventory$/, async (route) => {
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
      body: JSON.stringify(inventoryBody(CARDS)),
    })
  })
  await page.route(/\/photo\/\d+\/\d+$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'image/svg+xml', body: PHOTO_SVG })
  })
}

// ------------------------------------------------------------------ reading the rendered page

type Rgb = { r: number; g: number; b: number; a: number }

/* Parsed with one regex and no `split(',')`. eslint bans that call across this app — v1 bug 2,
 * naive CSV parsing — and the pull-confirm spec needed a named exemption in
 * `app/eslint.config.js` to use it on a colour string. A regex needs no exemption, which is
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
type Run = { text: string; where: string; size: number; colour: string; ground: string }

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
    const groundOf = (start: Element): string => {
      let node: Element | null = start
      while (node !== null) {
        const colour = window.getComputedStyle(node).backgroundColor
        if (colour !== 'transparent' && !colour.startsWith('rgba(0, 0, 0, 0)')) return colour
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
          colour: style.color,
          ground: groundOf(parent),
        })
      }
      node = walker.nextNode()
    }
    return out
  })
}

/** Every visible thing on the whole page that can be pressed, with its box. Page-wide and not
 *  view-wide on purpose: a control outside this view is still under his thumb. */
async function targets(page: Page): Promise<{ where: string; box: DOMRect }[]> {
  return page.evaluate(() => {
    const out: { where: string; box: DOMRect }[] = []
    for (const element of document.querySelectorAll('button, a[href], input, select, textarea')) {
      if (!element.checkVisibility()) continue
      const classes = element.getAttribute('class')
      out.push({
        where: `${element.tagName.toLowerCase()}${classes === null ? '' : `.${classes}`}: ${(element.textContent ?? '').trim().slice(0, 40)}`,
        box: element.getBoundingClientRect().toJSON() as DOMRect,
      })
    }
    return out
  })
}

/** The shortest distance between two rectangles. Zero when they overlap on both axes, which
 *  is what two abutting rows are and what the 12px rule is written against. */
function apart(a: DOMRect, b: DOMRect): number {
  const dx = Math.max(a.x - (b.x + b.width), b.x - (a.x + a.width), 0)
  const dy = Math.max(a.y - (b.y + b.height), b.y - (a.y + a.height), 0)
  return Math.max(dx, dy)
}

const view = (page: Page): Locator => page.locator(VIEW)

/* The four checks that apply to EVERY screen this view has, rather than to the one a test
 * happens to be looking at.
 *
 * They are functions and not a `test.step` inside each test because of what the breaking
 * exercise found: run against the list and the card panel only, the walk never reads the
 * screen he sees while the cards load or the one he sees when they do not. A banned word
 * there would have been invisible — and the copy on a failure screen is exactly the copy
 * nobody proofreads. Every screen calls all four, and the argument for a new screen not
 * calling them has to be made out loud.
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
    const ink = parseRgb(run.colour)
    const ground = parseRgb(run.ground)
    expect(ink, `${where} ${run.where}: unreadable colour ${run.colour}`).not.toBeNull()
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

async function fatTargets(page: Page, where: string): Promise<void> {
  const found = await targets(page)
  expect(found.length, `${where}: no control on screen`).toBeGreaterThan(0)

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
      expect(apart(a.box, b.box), `${where}: ${a.where} -> ${b.where}`).toBeGreaterThanOrEqual(
        GAP_FLOOR,
      )
    }
  }
}

/** The list screen, loaded and rendered. */
async function openList(page: Page, wire: Wire[] = []): Promise<void> {
  await stubServer(page, wire)
  await page.goto(VIEW_ROUTE)
  await expect(
    view(page),
    `no Fulfillment view at ${VIEW_ROUTE} — is the route registered in App.tsx?`,
  ).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Cards to pull' })).toBeVisible()
}

/** The card panel for one card, photo loaded. */
async function openCard(page: Page, name: string): Promise<void> {
  await page.getByRole('button', { name }).click()
  await expect(view(page).locator('.fulfillment-photo')).toBeVisible()
}

// ------------------------------------------------------------------------------ the table

test('the cards for sale are listed in box-walk order, and nothing else is listed', async ({
  page,
}) => {
  await openList(page)
  // Box then index: 1/3, 3/7, 3/26. The fixture is written in another order, so this measures
  // the sort rather than the object it came from.
  await expect(view(page).locator('.fulfillment-row .fulfillment-place')).toHaveText([
    'Box 1 · Section 1 · Card 3',
    'Box 3 · Section 1 · Card 7',
    'Box 3 · Section 2 · Card 1',
  ])
  // Captured, not for sale, and therefore not his to sell.
  await expect(page.getByText('Box 2 · Section 1 · Card 4')).toHaveCount(0)
  // For sale but unplaced: counted on screen, never dropped in silence.
  await expect(view(page)).toContainText('1 card for sale is not shown here')
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

test(`every position label is at least ${PLACE_FLOOR}px and set in tabular figures`, async ({
  page,
}) => {
  await openList(page)

  const check = async (where: string) => {
    const places = view(page).locator('.fulfillment-place')
    const count = await places.count()
    expect(count, `${where}: no position label on screen`).toBeGreaterThan(0)

    for (let index = 0; index < count; index += 1) {
      const place = places.nth(index)
      const size = await place.evaluate(
        (node) => Number.parseFloat(window.getComputedStyle(node).fontSize),
      )
      expect(size, `${where}: position label ${index}`).toBeGreaterThanOrEqual(PLACE_FLOOR)

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
        const style = window.getComputedStyle(node)
        const probe = document.createElement('span')
        probe.style.font = style.font
        probe.style.fontFamily = style.fontFamily
        probe.style.fontSize = style.fontSize
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

  await check('list')
  await openCard(page, 'Charizard ex')
  await check('card')
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

    const box = await view(page).locator('.fulfillment-photo').boundingBox()
    expect(box, 'the photo has no layout box').not.toBeNull()
    expect(
      Math.min(box!.width, box!.height),
      `short edge at ${screen.width}px`,
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

test('no destructive action and no route out is reachable from this view', async ({ page }) => {
  const wire: Wire[] = []
  await openList(page, wire)

  /* A link is the route. The shell draws one to every other screen above every view, and the
   * capture screen those reach carries an undo that hard-deletes a record, a sidecar and a
   * photo (D10) — which is the destructive action this row of the table is about. Counting
   * VISIBLE links rather than links in the document is the honest form: `display: none` is
   * not clickable, not focusable and not reachable by a screen reader, and the rule in
   * Fulfillment.css that hides the nav is written to be replaced by App.tsx not rendering it
   * at all. Either way this number is zero, and it is what will notice if both go. */
  const links = await page.locator('a[href]').all()
  for (const link of links) {
    expect(await link.isVisible(), `a route out: ${await link.getAttribute('href')}`).toBe(false)
  }
  await expect(page.locator('.app-nav')).toBeHidden()

  // Nothing on screen offers to delete, remove, erase, or open a setting. Read off the
  // rendered controls rather than off a list of routes, because a button that does it without
  // navigating is the same hazard without the href.
  const wording = (await targets(page)).map((target) => target.where.toLowerCase())
  for (const label of wording) {
    expect(label, 'a destructive control is on screen').not.toMatch(
      /delete|remove|erase|discard|settings|import/,
    )
  }

  // And the view itself writes nothing until he presses the one thing it offers.
  expect(wire, 'the view wrote to the server without being asked').toEqual([])
})

test(`undo is offered on every mark-sold and stays for at least ${UNDO_FLOOR_MS / 1000}s`, async ({
  page,
}) => {
  test.setTimeout(60_000)
  const wire: Wire[] = []
  await openList(page, wire)

  await openCard(page, 'Charizard ex')
  await page.getByRole('button', { name: 'Pull' }).click()
  // The copy rule, asserted rather than assumed: the button that says Pull produces a
  // confirmation that says Pulled.
  await expect(view(page)).toContainText('Pulled.')

  await page.getByRole('button', { name: 'Mark sold' }).click()
  await expect(view(page)).toContainText('Marked sold.')
  expect(wire.map((call) => call.undo), 'the sale reached the server as a sale').toEqual([false])
  expect(wire[0]!.url, 'the sale named the card').toContain('/inventory/3/7/sold')

  const undo = page.getByRole('button', { name: 'Undo' })
  await expect(undo).toBeVisible()
  // The sold card leaves the list while the sale stands.
  await expect(page.getByRole('button', { name: 'Charizard ex' })).toHaveCount(0)

  /* Real time, not a fake clock. The window is a promise to a person who has just put a card
   * in an envelope and looked up, and the thing worth proving is that the control survives
   * ten seconds of that — including a React re-render, a timer, and anything else the page
   * does in between. A fake clock proves the arithmetic instead. Ten seconds of wall time is
   * the cost, once, in the one test that measures a duration. */
  await page.waitForTimeout(UNDO_FLOOR_MS + 500)
  await expect(undo, `undo left before ${UNDO_FLOOR_MS}ms`).toBeVisible()

  await undo.click()
  // It undoes: the sale is withdrawn at the server and the card is back where he can find it.
  await expect(page.getByRole('button', { name: 'Charizard ex' })).toBeVisible()
  // A sale then a reversal, in that order, on the one route that takes both.
  expect(wire.map((call) => call.undo), 'the withdrawal reached the server').toEqual([false, true])
  // Back in box-walk order rather than appended: he walks the boxes in this order.
  await expect(view(page).locator('.fulfillment-row .fulfillment-place')).toHaveText([
    'Box 1 · Section 1 · Card 3',
    'Box 3 · Section 1 · Card 7',
    'Box 3 · Section 2 · Card 1',
  ])
})

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

test('the copy carries no word from the system this is built out of', async ({ page }) => {
  await openList(page)
  await noJargon(page, 'list')
  await openCard(page, 'Charizard ex')
  await noJargon(page, 'card')
  await page.getByRole('button', { name: 'Pull' }).click()
  await noJargon(page, 'pulled')
  await page.getByRole('button', { name: 'Mark sold' }).click()
  await expect(view(page)).toContainText('Marked sold.')
  await noJargon(page, 'sold')
})

/* The two screens that come before the cards, held still long enough to be read.
 *
 * They are here because the breaking exercise found them missing: with the walks pointed only
 * at the list and the card, a banned word or a 12px line on either of these was invisible.
 * The failure screen is the more important of the two — it is the screen he sees on the
 * morning the Mac is asleep, it is the one carrying a sentence somebody will want to make
 * more informative, and the informative version of it is the server's own message.
 */
test('the screen while the cards load is his too', async ({ page }) => {
  await stubServer(page, [], { slow: true })
  await page.goto(VIEW_ROUTE)
  await expect(view(page)).toContainText('Getting the cards.')
  await noSmallText(page, 'loading')
  await noThinContrast(page, 'loading')
  await noJargon(page, 'loading')
  // And it does end. A loading state nothing clears is a broken screen that measures clean.
  await expect(page.getByRole('button', { name: 'Charizard ex' })).toBeVisible()
})

test('the screen when the cards do not load is his too, and trying again works', async ({
  page,
}) => {
  const mood: Mood = { fail: true }
  await stubServer(page, [], mood)
  await page.goto(VIEW_ROUTE)

  // What happened, and what to do next — in his words, and none of the server's.
  await expect(view(page)).toContainText('The cards did not load. Try again.')
  await expect(view(page)).not.toContainText('store_unreadable')
  await expect(view(page)).not.toContainText('inventory.json')

  await noSmallText(page, 'load failed')
  await noThinContrast(page, 'load failed')
  await noJargon(page, 'load failed')
  await fatTargets(page, 'load failed')

  // "Try again" tries again. A remedy that does not work is worse than none, because it is
  // the one he will press repeatedly before asking anyone.
  mood.fail = false
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(page.getByRole('button', { name: 'Charizard ex' })).toBeVisible()
})

test('a card the other device already sold reads as sold, not as a failure', async ({ page }) => {
  await openList(page)
  await page.unroute(/\/inventory\/\d+\/\d+\/sold$/)
  await page.route(/\/inventory\/\d+\/\d+\/sold$/, async (route) => {
    // What `do_mark_sold` answers when the card is already in the state being asked for —
    // the other device got there first, which D13 permits and neither device is told about.
    await route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({
        error: { code: 'already_sold', message: 'Box 3, card 7 is already sold.' },
      }),
    })
  })

  await openCard(page, 'Charizard ex')
  await page.getByRole('button', { name: 'Pull' }).click()
  await page.getByRole('button', { name: 'Mark sold' }).click()

  /* Asserted because it is behaviour this file invented rather than behaviour the design
   * specifies. Reporting the refusal would put him in a loop: the message would say press it
   * again, pressing it again would answer the same way, and the card is sold either way. The
   * screen says what is true instead. */
  await expect(view(page)).toContainText('Marked sold.')
  await expect(view(page)).not.toContainText('Nothing was saved')
  await expect(page.getByRole('button', { name: 'Undo' })).toBeVisible()
})

test('a refusal says what happened and what to do, in his words', async ({ page }) => {
  const wire: Wire[] = []
  await openList(page, wire)
  // The sale is refused by the server after the screen is up, so the failure lands where he
  // is rather than on a screen that never rendered.
  await page.unroute(/\/inventory\/\d+\/\d+\/sold$/)
  await page.route(/\/inventory\/\d+\/\d+\/sold$/, async (route) => {
    await route.fulfill({
      status: 409,
      contentType: 'application/json',
      // The server's own register, verbatim from the shape `_fail` sends. None of it may
      // reach the screen: it names a route, a state and a command, and every one of those is
      // correct and none of them is his.
      body: JSON.stringify({
        error: { code: 'store_busy', message: 'The staged import is locked; retry after batch.' },
      }),
    })
  })

  await openCard(page, 'Charizard ex')
  await page.getByRole('button', { name: 'Pull' }).click()
  await page.getByRole('button', { name: 'Mark sold' }).click()

  // What happened, and what to do next.
  await expect(view(page)).toContainText('Nothing was saved. Press Mark sold again.')
  // The card is still his to sell, because nothing was recorded.
  await expect(page.getByRole('button', { name: 'Mark sold' })).toBeVisible()
  // And none of the server's words are on screen — neither the code nor the sentence.
  await expect(view(page)).not.toContainText('store_busy')
  await expect(view(page)).not.toContainText('locked')
})
