import { expect, test } from '@playwright/test'
import { sealEveryTest } from './shell'
import type { Page } from '@playwright/test'
import type { GameRegistry } from '../src/types'

/* THE UNDO STACK ON THE CAPTURE SCREEN — the owner's ask of 2026-08-29: "a list of 10 rather
 * than the one I can see right now", with `U` still undoing the most recent.
 *
 * WHY THIS IS ITS OWN FILE, AND NOT MORE CASES IN `capture-claims.spec.ts`. That file states
 * in its header that no capture is ever taken and no box is ever selected, because a capture
 * against a dev server would POST into a real store. This one has to capture — the stack IS
 * the session's captures — so it does the opposite and says why it is safe: `POST /capture`
 * and `DELETE /inventory/...` are both intercepted, so nothing reaches a store, and the
 * camera is a canvas rather than a device.
 *
 * WHAT ONLY A BROWSER CAN CATCH HERE. The walk-back is N sequential requests where the
 * (N+1)th is only legal because the Nth succeeded — `store/master.py` deletes the newest
 * card in a box and refuses anything else (D10). Nothing in the type system says the
 * requests must be ordered, sequential, and abandoned at the first refusal; a Promise.all
 * would type-check, pass every unit test that could exist for it, and delete one card of
 * three while reporting three.
 *
 * THE CAMERA IS A CANVAS, `motion-live.spec.ts`'s trick with the seam moved one step
 * earlier: that file injects a stream into the <video> because it only needs pixels, and
 * this one stubs `getUserMedia` because it needs `useCamera` to reach `ready` — which is
 * what `canCapture` gates the shutter on.
 */

/* TYPED AGAINST THE WIRE, so a field added to `GameRegistry` is a failed commit here rather
 * than a crash in a browser nothing on the commit path runs. `app/tests/inventory.spec.ts`
 * carries the whole account: D101's `products` was added to that type and to the screens and
 * omitted from every one of these fixtures, and four of its cases died on it silently.
 * `tsconfig.json` includes `tests`, so this annotation is checked by `make check`. */
const GAMES: GameRegistry = {
  default: 'pokemon',
  /* C10's vocabulary, as `GET /games` really answers it — see the annotation note above. */
  products: [
    { key: 'booster', display: 'Booster pack', premium: false, redeem_limit: 400 },
    { key: 'pc_etb', display: 'Pokémon Center ETB', premium: true, redeem_limit: 4 },
  ],
  product_game: 'pokemon_code',
  games: [
    {
      key: 'pokemon',
      display: 'Pokémon',
      product_line: 'Pokemon',
      rarities: ['Common', 'Uncommon', 'Rare'],
      finishes: ['normal', 'holo', 'reverse_holo'],
      condition_by_finish: {
        normal: 'Near Mint',
        holo: 'Near Mint Holofoil',
        reverse_holo: 'Near Mint Reverse Holofoil',
      },
      finish_by_rarity: {
        Common: ['normal'],
        Uncommon: ['normal', 'reverse_holo'],
        Rare: ['normal', 'holo', 'reverse_holo'],
      },
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

/** Box 3, undeclared and empty, so the first capture lands at index 1 and the labels this
 *  file asserts are the ones D10's amendment renders: one section, card = index. */
const BOX = {
  box: 3,
  bid: 13,
  name: 'S key',
  sections: [],
  state: 'open',
  capacity: null,
  fill: 0,
  next_index: 1,
  cards: 0,
  sold: 0,
  retired: 0,
  listed: 0,
  sections_detail: [],
}

/** A SECOND DRAWER, and the whole reason the cases below this file's original five exist.
 *  Undeclared and empty like box 3, so the labels are D10's amendment's again. Its name
 *  shares no digit with either box number, so typing `4` into the Box field can only mean
 *  this one. */
const BOX4 = {
  box: 4,
  bid: 14,
  name: 'Next drawer',
  sections: [],
  state: 'open',
  capacity: null,
  fill: 0,
  next_index: 1,
  cards: 0,
  sold: 0,
  retired: 0,
  listed: 0,
  sections_detail: [],
}

/** Every DELETE the screen sent, in order. The ORDER is the assertion — newest first — so
 *  this is a list and never a set. `sections` is every `PUT /boxes/<box>` the screen sent
 *  with a `sections` field — UN-15's own undo, `updateBox({ sections })`. */
type Wire = {
  deletes: string[]
  removes: string[]
  captures: number
  sections: { box: string; sections: number[] }[]
}

async function open(
  page: Page,
  options: {
    refuseDeleteFrom?: number
    nextIndex?: Record<string, number>
    /** The `GET /boxes` roster this screen reads on mount. Defaults to `[BOX, BOX4]` — a
     *  case that needs a box shaped differently (a sold card, D58) passes its own. */
    boxes?: readonly unknown[]
    /** Section 6: the index a single-card remove refuses over (`renumber_blocked`). */
    blockRemoveOf?: number
    /** D58: the box's on-hand count BEFORE this sitting, keyed by box. Defaults to 0 — a
     *  fresh box, where on-hand after the Nth capture is simply N. A box carrying a
     *  departed card starts here above 0, so the stub's on_hand answers stay correct
     *  through a sitting that captures on top of one. */
    onHandStart?: Record<string, number>
  } = {},
): Promise<Wire> {
  const wire: Wire = { deletes: [], removes: [], captures: 0, sections: [] }

  /* A canvas camera, installed before the app script runs. `useCamera` reads
     `navigator.mediaDevices` at call time, so replacing the two methods is enough — and the
     stream is a real MediaStream, so the <video> gets metadata and `ready` flips exactly as
     it does with a Cam Link. */
  await page.addInitScript(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 640
    canvas.height = 360
    const context = canvas.getContext('2d')
    if (context !== null) {
      context.fillStyle = 'rgb(180,180,180)'
      context.fillRect(0, 0, 640, 360)
    }
    const stream = canvas.captureStream(30)
    const media = navigator.mediaDevices as unknown as {
      enumerateDevices: () => Promise<unknown[]>
      getUserMedia: () => Promise<MediaStream>
    }
    media.enumerateDevices = async () => [
      { deviceId: 'canvas', kind: 'videoinput', label: 'Canvas Cam Link', groupId: 'g' },
    ]
    media.getUserMedia = async () => stream
  })

  await page.route(/\/games$/, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(GAMES) }),
  )
  await page.route(/\/status$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ cards: 0, next_index: options.nextIndex ?? {} }),
    }),
  )
  await page.route(/\/boxes$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ boxes: options.boxes ?? [BOX, BOX4] }),
    }),
  )

  /* The store, as far as this screen can tell: an index that climbs by one per capture and
     the label `pipeline/join.py:Position` would render for an undeclared box — one section,
     card = index (D10, amended 2026-08-29). Composed here rather than imported because the
     app must never compose one; a fixture that got it wrong would be testing itself. */
  /* THE ALLOCATOR IS PER BOX, as `store/master.py:next_index` is: a drawer's indices are its
     own, and a second drawer starts at 1 while the first is at 394. Modelling this as one
     global counter would make every cross-drawer case below assert against an index space the
     store does not have — and the `serverNewest` comparison the blind arm turns on reads one
     drawer's high-water mark, so a shared counter would quietly change which arm fires. */
  const allocated: Record<string, number> = { ...(options.nextIndex ?? {}) }
  /* D58: this sitting's own capture COUNT per box, separate from `allocated`'s stored
   * index — the two only coincide when nothing was ever departed. On-hand after the Nth
   * capture into a box is `onHandStart + N`. */
  const capturedThisSitting: Record<string, number> = {}
  const onHandAfterCapture = (box: string): number => {
    capturedThisSitting[box] = (capturedThisSitting[box] ?? 0) + 1
    return (options.onHandStart?.[box] ?? 0) + capturedThisSitting[box]
  }
  await page.route(/\/capture$/, (route) => {
    wire.captures += 1
    const asked = route.request().postDataJSON() as { box?: number }
    const box = asked.box ?? 3
    const index = allocated[String(box)] ?? 1
    allocated[String(box)] = index + 1
    route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        box,
        index,
        key: `${box}/${index}`,
        label: `Box ${box}, Section 1, Card ${index}`,
        section: 1,
        card: index,
        new_box: index === 1,
        created: true,
        photo: `/tmp/${box}-${index}.jpg`,
        capture_id: null,
        // D58, R1d: `place.box_total`, the box's on-hand count after this capture —
        // `onHandStart` plus this sitting's own capture count, never the stored index.
        place: { box_total: onHandAfterCapture(String(box)) },
      }),
    })
  })

  await page.route(/\/inventory\/\d+\/\d+\/remove$/, (route) => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() !== 'POST') return route.fallback()
    wire.removes.push(path)
    const match = /\/inventory\/(\d+)\/(\d+)\/remove$/.exec(path)
    if (match === null) return route.fallback()
    const box = match[1] ?? ''
    const index = match[2] ?? ''
    if (options.blockRemoveOf !== undefined && Number(index) === options.blockRemoveOf) {
      return route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'renumber_blocked',
            message: `Deleting box ${box}, card ${index} would renumber every higher card in the box, and that shift is blocked: card 6 is sold.`,
          },
        }),
      })
    }
    const higher = Number(allocated[box] ?? 1) - 1 - Number(index)
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        deleted: `${box}/${index}`,
        box: Number(box),
        index: Number(index),
        photo_deleted: true,
        sidecar_deleted: true,
        review_deleted: false,
        parked_deleted: false,
        cache_deleted: true,
        shifted: Math.max(0, higher),
        next_index: Number(allocated[box] ?? 1) - 1,
        // D58, R1d: on-hand after this remove. Removing any one card (middle or newest)
        // drops the on-hand count by exactly one, from the same fixture-shape argument the
        // undo stub's own comment makes.
        on_hand: Number(allocated[box] ?? 1) - 2,
      }),
    })
  })

  await page.route(/\/inventory\/\d+\/\d+$/, (route) => {
    const path = new URL(route.request().url()).pathname
    if (route.request().method() !== 'DELETE') return route.fallback()
    wire.deletes.push(path)
    /* A refusal partway down the plan, which is the case the walk-back exists to survive.
       `undo_not_newest` is the real code and the real shape — `_fail` writes the error as a
       nested object and `describeFailure` reads it there. */
    if (
      options.refuseDeleteFrom !== undefined &&
      wire.deletes.length >= options.refuseDeleteFrom
    ) {
      return route.fulfill({
        status: 409,
        contentType: 'application/json',
        body: JSON.stringify({
          error: {
            code: 'undo_not_newest',
            message: 'Box 3, Section 1, Card 4 is the newest card in box 3.',
          },
        }),
      })
    }
    // D58, R1d: `on_hand` after this undo. Every box this file captures into is a plain
    // append with nothing ever departed, so deleting the newest card (index `N`) always
    // leaves `N - 1` on hand — the same number `store/master.py`'s own `_Places.total`
    // would answer for this fixture's shape.
    const deletedIndex = Number(path.split('/').pop())
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        deleted: path.replace('/inventory/', ''),
        on_hand: deletedIndex - 1,
      }),
    })
  })

  /* UN-15: dividers, tracked the way the store keeps them — one divider list per box. The
     section route APPENDS (`openSection`'s own contract, `server.ts`); the box route
     REPLACES wholesale (`updateBox({ sections })`), which is UN-15's undo. */
  const sectionsByBox: Record<string, number[]> = {}
  const boxRecord = (box: string): Record<string, unknown> => {
    const base =
      (options.boxes ?? [BOX, BOX4]).find(
        (entry) => (entry as { box: number }).box === Number(box),
      ) ?? BOX
    const sections = sectionsByBox[box] ?? []
    return {
      ...base,
      box: Number(box),
      sections,
      sections_detail: sections.map((start, at) => ({
        section: at + 1,
        start,
        end: sections[at + 1] === undefined ? start : sections[at + 1]! - 1,
        count: (sections[at + 1] ?? start) - start,
        name: null,
      })),
    }
  }
  await page.route(/\/boxes\/\d+\/sections$/, (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    const path = new URL(route.request().url()).pathname
    const box = /\/boxes\/(\d+)\/sections$/.exec(path)![1]!
    const at = allocated[box] ?? 1
    sectionsByBox[box] = [...(sectionsByBox[box] ?? []), at]
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(boxRecord(box)),
    })
  })
  await page.route(/\/boxes\/\d+$/, (route) => {
    if (route.request().method() !== 'PUT') return route.fallback()
    const path = new URL(route.request().url()).pathname
    const box = /\/boxes\/(\d+)$/.exec(path)![1]!
    const patch = route.request().postDataJSON() as { sections?: number[] }
    if (patch.sections !== undefined) {
      wire.sections.push({ box, sections: patch.sections })
      sectionsByBox[box] = patch.sections
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(boxRecord(box)),
    })
  })

  /* The photo service. Every row in the stack draws one, and an unrouted image request
     would reach the dev server as a 404 — noise in the console rather than a failure, but
     the kind that makes a real failure hard to see. */
  await page.route(/\/photo\/\d+\/\d+/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'image/gif',
      body: Buffer.from('R0lGODlhAQABAAAAACw=', 'base64'),
    }),
  )

  await page.goto('/#/capture')
  await expect(page.locator('.capture-row').filter({ hasText: /Finish/ })).toBeVisible()

  /* The box, by name, then the camera, by its row. Both keyboard: this screen's own path.

     PRESSED UNTIL IT LANDS. A visible row is not a subscribed handler: `CaptureScreen.tsx`
     registers its key listener in an effect whose dependencies include `gameEntry`, React runs
     passive effects after paint, and Playwright sees the paint — so the first press of a run
     can reach a document nobody is listening to and simply vanish. The retry is over this
     file's timing and not over the screen's behaviour: `B` still has to open the box field and
     offer the fixture's box, or this never returns. */
  await expect(async () => {
    await page.keyboard.press('b')
    await expect(page.locator('.capture-opt').filter({ hasText: /S key/ })).toBeVisible({
      timeout: 1_000,
    })
  }).toPass({ timeout: 15_000 })
  await page.keyboard.type('3')
  await page.keyboard.press('Enter')
  /* The camera opens on an explicit press and not on load — the field opens with an "Open the
     camera" button and nothing else, so a test that skipped it would be skipping the design.
     The device list only exists after it. */
  await page.keyboard.press('v')
  /* SCOPED TO THE RIG, because the sentence is on the screen three times now: the stage draws
     it over the dead viewfinder, the blocked-capture list draws it as a shortcut, and the
     Camera field draws it where `V` just put the operator. All three call `camera.retry`, so
     the choice is about which control this file drives rather than about which one works —
     and the field is the one the keypress above opened. */
  await page.getByLabel('Rig').getByRole('button', { name: 'Open the camera' }).click()
  await page.locator('.capture-opt').filter({ hasText: /Canvas Cam Link/ }).click()
  await page.keyboard.press('Escape')
  /* THE SHUTTER, BY ITS NAME. It was `.pull-confirm` — a class borrowed from another screen's
     confirm button — and the rebuild gave it the kit `Button`. The class is gone; the claim it
     stood for is not, and it is the precondition every case below rests on: with a box picked
     and a camera ready, the shutter is LIVE. Asserted by role and name rather than by class,
     so the next restyle cannot take it out again. */
  await expect(shutter(page)).toBeEnabled()
  return wire
}

/** The capture button. `Capture card` is its whole accessible name — the `C` keycap is
 *  `aria-hidden`, and in motion mode there is no keycap at all. */
function shutter(page: Page) {
  return page.getByRole('button', { name: 'Capture card', exact: true })
}

/** N captures, awaited one at a time. The shutter is held while a capture is in flight, so
 *  pressing faster than the screen commits is how a test loses a card — the same property
 *  the feeder has, arrived at for the same reason.
 *
 *  IT WAITS ON THE TOP ROW'S CARD, NOT ON A ROW COUNT, and the count is what it waited on
 *  first: past the tenth capture the count stops moving, so the wait was satisfied by the
 *  PREVIOUS card and the next press landed while the shutter was still held. The screen
 *  swallowed it — correctly — and the twelfth capture never happened. A test that presses
 *  faster than the screen commits measures the test. */
async function shoot(page: Page, count: number): Promise<void> {
  await shootInto(page, 3, 1, count)
}

/** The same, into whatever drawer the Box field is on. `first` is the index the next capture
 *  lands at in THAT drawer, because the stub allocates per box as the store does — so after a
 *  switch to a fresh drawer this is 1 again while box 3 sits at 3.
 *
 *  IT WAITS ON THE DRAWER AS WELL AS THE CARD. `Card 1$` alone matches box 3's first card and
 *  box 4's, so a wait written that way is satisfied by a stack that never moved — which is the
 *  precise defect these cases are for, and it would make them pass against it. */
async function shootInto(page: Page, box: number, first: number, count: number): Promise<void> {
  for (let at = 0; at < count; at += 1) {
    await page.keyboard.press('c')
    await expect(rows(page).first()).toHaveAttribute(
      'aria-label',
      new RegExp(`Box ${box}, Section 1, Card ${first + at}$`),
    )
  }
}

/** Change the Box field — one keystroke, `B`, a digit and Enter, which is the whole of what
 *  it used to take to refill the undo stack from another drawer. */
async function switchBox(page: Page, box: number): Promise<void> {
  await expect(async () => {
    await page.keyboard.press('b')
    await expect(page.locator('.capture-opts')).toBeVisible({ timeout: 1_000 })
  }).toPass({ timeout: 10_000 })
  await page.keyboard.type(String(box))
  await page.keyboard.press('Enter')
  // The field is closed and shows the new drawer, so nothing below races the change.
  await expect(page.locator('.capture-opts')).toBeHidden()
}

function rows(page: Page) {
  return page.locator('.capture-undo-row')
}

/* NOTHING HERE MAY REACH THE CAPTURE SERVER — `app/tests/shell.ts` carries the argument. This
   file already stubbed the shell's own `/status` by hand; the shared call replaces it so there
   is one spelling of the rule, and adds what a hand-written stub could not: a catch-all that
   REFUSES and names anything else that gets out. The call has to sit above the file's first
   `test.beforeEach`, which is what `make docs-audit`'s `spec seal` row checks. */
sealEveryTest()

/* UN-1: THE CAP IS GONE (D164, Q1). The owner's own example — "undo the 24th capture in my
 * capturing run when i'm on capture 36" — is the case this proves: with the old `UNDO_DEPTH`
 * of 10, capture 24 was the 13th newest and had no row at all. */
test('the stack is the whole sitting, newest first, and reaches the 13th row', async ({
  page,
}) => {
  const wire = await open(page)
  await shoot(page, 36)

  // Every capture is a row. Nothing is out of reach.
  await expect(rows(page)).toHaveCount(36)
  await expect(rows(page).first()).toHaveAttribute('aria-label', /Card 36$/)
  await expect(rows(page).last()).toHaveAttribute('aria-label', /Card 1$/)

  /* THE ADDRESS IS READ OFF `aria-label` AND NOT OFF THE TEXT — D41's repair, right twice
     over. `PositionLabel` draws the path as a muted stack and the slot as a figure, so no
     contiguous `Card N` survives in the text content; the label rides `aria-label`
     verbatim, which is what keeps the split a view of the server's string. That entry also
     records the trap in the other direction: a text assertion of this shape goes VACUOUS
     the day the DOM stops containing the string, and passes forever after. */
  // Capture 24 is the 13th newest (36, 35, …, 25, 24) — row index 12.
  await expect(rows(page).nth(12)).toHaveAttribute('aria-label', /Card 24$/)
  await expect(rows(page).nth(12).locator('.capture-key')).toHaveText('13')

  // "Undo back to 24" — the row's own click walks the plan back to it.
  await rows(page).nth(12).click()
  // 36 rows, 13 deleted (36 down to 24): 23 remain.
  await expect(rows(page)).toHaveCount(23)
  expect(wire.deletes.length).toBe(13)
  expect(wire.deletes[0]).toBe('/inventory/3/36')
  expect(wire.deletes[12]).toBe('/inventory/3/24')

  // And the heading counts the whole sitting, not a capped figure.
  await expect(page.locator('.capture-undo-depth')).toHaveText('23 recent')
})

/* UN-15: A DIVIDER'S OWN UNDO. `S`/"New section" writes through `set_sections`
 * (`openSection`), which is not an append the store can reverse on its own — so `U` puts the
 * layout back through the same route Manage box's own editor calls (`updateBox({ sections })`),
 * "while no card is behind it" (undo.md 11.1). */
test('U undoes a divider while no card is behind it', async ({ page }) => {
  const wire = await open(page)
  await shoot(page, 2)

  await page.getByRole('button', { name: 'New section' }).click()
  await expect(page.locator('.capture-refused, .capture-note-ok').last()).toContainText(
    'New section',
  )

  await page.keyboard.press('u')

  // The layout is back to what it was — no divider — through the box route, not a delete.
  expect(wire.sections).toEqual([{ box: '3', sections: [] }])
  expect(wire.deletes).toEqual([])
  // Neither capture was touched.
  await expect(rows(page)).toHaveCount(2)
})

/* THE OTHER HALF: ONCE A CARD IS CAPTURED BEHIND IT, THE DIVIDER IS "BUILT ON" and `U` reaches
 * the capture instead — undo.md 11.1's own table row for Divider. */
test('a capture behind the divider is built on it, and U reaches the capture instead', async ({
  page,
}) => {
  const wire = await open(page)
  await shoot(page, 2)
  await page.getByRole('button', { name: 'New section' }).click()
  // The third card, into the same box the divider was opened in — the fixture's own
  // allocator is already at 3, and `shoot`'s helper assumes a fresh box starting at 1.
  await shootInto(page, 3, 3, 1)

  await page.keyboard.press('u')

  expect(wire.deletes).toEqual(['/inventory/3/3'])
  expect(wire.sections).toEqual([])
})

/* UN-2: A RELOAD KEEPS THE SITTING. `GET /capture/sitting` is the read this proves — the
 * strip appears with NO capture made in this browser at all, which is the one thing
 * `shoot()` could never demonstrate on its own. */
test('a reload rebuilds the strip from the store (UN-2)', async ({ page }) => {
  await page.route(/\/capture\/sitting$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        open: true,
        gap_minutes: 30,
        cards: [1, 2].map((index) => ({
          box: 3,
          index,
          key: `3/${index}`,
          label: `Box 3, Section 1, Card ${index}`,
          section: 1,
          card: index,
          new_box: index === 1,
          created: true,
          photo: `/tmp/3-${index}.jpg`,
          capture_id: null,
          place: { box_total: index },
          captured_at: '2026-09-25T12:00:00+00:00',
          set_hint: null,
          metadata_finish: null,
          game: 'pokemon',
          state: 'captured',
        })),
      }),
    }),
  )
  const wire = await open(page)

  // Two rows, newest first, with no capture pressed in this browser.
  await expect(rows(page)).toHaveCount(2)
  await expect(rows(page).first()).toHaveAttribute('aria-label', /Card 2$/)
  await expect(rows(page).last()).toHaveAttribute('aria-label', /Card 1$/)

  // And the undo still reaches it — a hydrated row is not a read-only picture.
  await page.keyboard.press('u')
  expect(wire.deletes).toEqual(['/inventory/3/2'])
})

/* UN-2's fix-after: once the sitting has ended (or a run has identified it), the ordinary
 * undo route refuses `capture_built_on` (undo.md 11.1's own table row for Capture), and the
 * strip offers the route that DOES still reach the card — Manage box. */
test('a capture built on its sitting refuses, and offers Manage box', async ({ page }) => {
  const wire = await open(page)
  await shoot(page, 1)
  // Registered after `open()`'s own DELETE stub, so it wins (Playwright matches newest first).
  await page.route(/\/inventory\/\d+\/\d+$/, (route) => {
    if (route.request().method() !== 'DELETE') return route.fallback()
    wire.deletes.push(new URL(route.request().url()).pathname)
    return route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({
        error: {
          code: 'capture_built_on',
          message: 'This sitting has ended. Manage box removes the card instead.',
        },
      }),
    })
  })

  await page.keyboard.press('u')

  await expect(page.locator('.capture-refused')).toContainText('This sitting has ended')
  await expect(page.locator('.capture-halt-code')).toHaveText('capture_built_on')
  const fix = page.getByRole('button', { name: 'Manage box' })
  await expect(fix).toBeVisible()
  await fix.click()
  await expect.poll(() => page.evaluate(() => window.location.hash)).toBe('#/inventory?box=3')
})

test('U undoes the most recent one, and only that one', async ({ page }) => {
  const wire = await open(page)
  await shoot(page, 4)

  await page.keyboard.press('u')
  await expect(rows(page)).toHaveCount(3)

  expect(wire.deletes).toEqual(['/inventory/3/4'])
  await expect(rows(page).first()).toHaveAttribute('aria-label', /Card 3$/)
  await expect(page.locator('.capture-undo .capture-quiet').last()).toContainText('Undone')
})

test('a row undoes that card and everything after it, newest first', async ({ page }) => {
  const wire = await open(page)
  await shoot(page, 5)

  // Row 3 is `Card 3`: pressing it deletes 5, 4 and 3, in that order.
  await rows(page).nth(2).click()
  await expect(rows(page)).toHaveCount(2)

  /* THE ORDER IS THE ASSERTION. Each of these is only legal because the one before it
     succeeded — the route deletes the newest card in a box and refuses anything else (D10),
     so a set-equality check here would pass for an implementation that fired all three at
     once and deleted one. */
  expect(wire.deletes).toEqual(['/inventory/3/5', '/inventory/3/4', '/inventory/3/3'])

  await expect(rows(page).first()).toHaveAttribute('aria-label', /Card 2$/)
  const note = page.locator('.capture-undo .capture-quiet').last()
  await expect(note).toContainText('3 captures, back to')
  /* `.position-run`, not `.position-parts`: the inline form keeps D41's RANK and drops the
     geometry, so it sits inside a sentence rather than stacking a path above a figure —
     and it is its own element with its own class. Both carry the server's string on
     `aria-label`, which is the half that matters here. */
  await expect(note.locator('.position-run')).toHaveAttribute('aria-label', /Card 3$/)
})

test('a walk that is refused partway says how far it got, in the server’s own words', async ({
  page,
}) => {
  // The third DELETE refuses, so cards 5 and 4 go and card 3 stays.
  const wire = await open(page, { refuseDeleteFrom: 3 })
  await shoot(page, 5)

  await rows(page).nth(2).click()

  /* IT STOPS AT THE REFUSAL rather than carrying on down the plan: the next card is only
     undoable because this one was going to be gone. Four requests would mean the screen
     kept aiming after the store said no. */
  await expect(page.locator('.capture-undo-partial')).toHaveText('Undid 2 of 3.')
  expect(wire.deletes).toEqual(['/inventory/3/5', '/inventory/3/4', '/inventory/3/3'])

  // The two that went are gone from the list; the one that refused is still on it, on top.
  await expect(rows(page)).toHaveCount(3)
  await expect(rows(page).first()).toHaveAttribute('aria-label', /Card 3$/)

  // The server's sentence, verbatim, and its machine string beside it (docs/DESIGN.md).
  await expect(page.locator('.capture-refused')).toContainText('is the newest card in box 3')
  await expect(page.locator('.capture-halt-code')).toHaveText('undo_not_newest')
})

/* THE ONE UNDO TARGET THIS SESSION NEVER SAW A CAPTURE RESPONSE FOR, which is the only row in
 * this screen that can carry no label at all — and, until 2026-09-04, the only one that drew the
 * store key wearing the count's sigil.
 *
 * `undoStack` composes it from `GET /status`'s `next_index` rather than from a capture it made:
 * `serverNewest = next_index[box] - 1`, taken whenever the server's high-water mark is ahead of
 * anything this session shot (`CaptureScreen.tsx`). That is every reload mid-run — the operator
 * refreshes, the session's own list is empty, and the newest card in the drawer is still undoable.
 * The record has a box and an index and NOTHING ELSE, so `positionText` and `undoFigure` both fall
 * through to `storeKey.ts`'s `storeKeyText`.
 *
 * WHAT IT GUARDS. `undoFigure` used to draw `#{slotNumber(target)}` here, and `slotNumber` returned
 * the raw index — D58's countable number spelled over the store key, three functions away from the
 * `#`, which is why `make sigil-check` was green over that line from the day it was written
 * (DEBT9). Nothing in this suite reached the branch: the fix shipped in `42e6b96` with
 * no test file touched at all, and its only evidence was a render somebody looked at once.
 *
 * `toHaveText` and an anchored `aria-label` rather than a `contains`: `B3 #7` contains `#7`, so a
 * loose assertion here passes against the exact defect it is written for. */
test('an undo target the session never captured draws the store key, not a card number', async ({
  page,
}) => {
  /* Shoot nothing. The server says box 3 is at index 8, so the newest card in it is 7 — a card
     this session has no capture response for and therefore no label. */
  await open(page, { nextIndex: { '3': 8 } })

  await expect(rows(page)).toHaveCount(1)
  await expect(rows(page).first().locator('.capture-undo-pos')).toHaveText('B3 #7')
  await expect(rows(page).first()).toHaveAttribute(
    'aria-label',
    'Undo the newest capture, B3 #7',
  )
})

/* ════════════════════════════════════════════════════════════════════════════════════════
 * THE SITTING, NOT THE DRAWER (2026-09-12)
 *
 * Everything above this line was written against one box, which is why none of it could see
 * the defect these five are for: `undoStack` and `runCount` both filtered `shots` on
 * `shot.card.box === box` — the CURRENT value of a field the operator changes with one
 * keystroke. Switch drawers mid-sitting and the stack refilled from the new drawer, and
 * capture-undo deletes the record AND the photograph (D10 ruling 1).
 *
 * NOT HYPOTHETICAL. Clustering the owner's `captured_at` at `storeHistory.ts`'s own
 * `GAP_MINUTES` gives ten sittings, two of them across drawers: 2026-09-01 ran 555 cards in
 * 23.9 minutes across boxes 3 → 4 → 5, and 2026-09-11 ran 536 in 46.2 minutes across boxes 4
 * and 1. 1,091 of 2,535 cards — 43% of the store — were photographed in a sitting where this
 * was live end to end.
 *
 * EVERY ONE OF THESE WAS RUN AGAINST THE OLD CODE AND OBSERVED TO FAIL before it was kept.
 * The arms are in the decision entry; a sweep that goes green because the fixture never drew
 * the control is this repo's standing trap, which is why each case asserts a DRAWER and not
 * only a card number — `Card 1` alone is true of both drawers' first card.
 * ════════════════════════════════════════════════════════════════════════════════════════ */

test('the stack keeps this sitting’s cards when the drawer changes', async ({ page }) => {
  await open(page)
  await shoot(page, 3)
  await switchBox(page, 4)
  await shootInto(page, 4, 1, 2)

  /* FIVE ROWS, NOT TWO. Under the box filter this read two — the new drawer's own — and the
     three cards the hand had taken a minute earlier were not reachable by any control on the
     screen. */
  await expect(rows(page)).toHaveCount(5)

  // The order the hand took them, newest first, straight across the seam.
  await expect(rows(page).nth(0)).toHaveAttribute('aria-label', /Box 4, Section 1, Card 2$/)
  await expect(rows(page).nth(1)).toHaveAttribute('aria-label', /Box 4, Section 1, Card 1$/)
  await expect(rows(page).nth(2)).toHaveAttribute('aria-label', /Box 3, Section 1, Card 3$/)
  await expect(rows(page).nth(4)).toHaveAttribute('aria-label', /Box 3, Section 1, Card 1$/)

  /* AND EVERY ROW NAMES ITS DRAWER, including the ones in the drawer the Box field is on. A
     label on only the rows that differ would make the unlabelled ones read as "the current
     drawer" — the exact inference the filter used to invite. */
  await expect(page.locator('.capture-undo-drawer')).toHaveCount(5)
  await expect(rows(page).nth(0).locator('.capture-undo-drawer')).toHaveText('Box 4')
  await expect(rows(page).nth(2).locator('.capture-undo-drawer')).toHaveText('Box 3')
})

test('a drawer already fed is not offered for undo when this sitting has shots', async ({
  page,
}) => {
  /* THE SHARP ARM, and the one that costs a card. Box 4 already holds 543 cards from an
     earlier sitting, so its high-water mark is #543. Under the old code, switching to it with
     no shots of this sitting in it fell through to `serverNewest` and offered THAT card —
     labelless, days old, one `U` press from a hard delete. On the owner's store box 2 has
     stood at #543 through nine consecutive sittings with exactly this exposure. */
  await open(page, { nextIndex: { '4': 544 } })
  await shoot(page, 2)
  await switchBox(page, 4)

  // Still this sitting's two cards, and the top of the stack is still box 3's newest.
  await expect(rows(page)).toHaveCount(2)
  await expect(rows(page).first()).toHaveAttribute('aria-label', /Box 3, Section 1, Card 2$/)

  /* NOTHING IN THE STRIP ADDRESSES BOX 4. Asserted as an absence over the whole list rather
     than as a property of the top row: an implementation that offered #543 second, or third,
     would still put it under a press. */
  await expect(page.locator('.capture-undo-pos')).toHaveCount(2)
  await expect(page.locator('.capture-undo-list')).not.toContainText('543')
})

test('the walk crosses the seam in order, and every delete is legal where it lands', async ({
  page,
}) => {
  /* THE HIGHER DRAWER FIRST, WHICH IS THE OWNER'S OWN 2026-09-11 SITTING — box 4 for 214
     cards, then box 1 for 322 — and it is deliberate rather than incidental. Ascending (their
     2026-09-01 sitting, boxes 3 → 4 → 5, which the case above uses) is the one shape where the
     hand's order and a sort by box NUMBER happen to agree, so a stack that had quietly sorted
     itself would pass every assertion written over it. Mutation-tested: sorting the stack by
     `(box, index)` survived this case until it was turned around. */
  const wire = await open(page)
  await switchBox(page, 4)
  await shootInto(page, 4, 1, 2)
  await switchBox(page, 3)
  await shootInto(page, 3, 1, 2)

  /* THE ORDER THE HAND TOOK THEM, WHICH HERE RUNS DOWNWARD THROUGH THE DRAWER NUMBERS. A sort
     by box would put B4 #2 on top; the hand put B3 #2 there. */
  await expect(rows(page).nth(0)).toHaveAttribute('aria-label', /Box 3, Section 1, Card 2$/)
  await expect(rows(page).nth(1)).toHaveAttribute('aria-label', /Box 3, Section 1, Card 1$/)
  await expect(rows(page).nth(2)).toHaveAttribute('aria-label', /Box 4, Section 1, Card 2$/)
  await expect(rows(page).nth(3)).toHaveAttribute('aria-label', /Box 4, Section 1, Card 1$/)

  // Row 3 is box 4's card 2: pressing it undoes B3 #2, B3 #1 and B4 #2, in that order.
  await rows(page).nth(2).click()

  /* THE DOM FIRST, THE WIRE SECOND, and the order of these two lines is not a style choice.
     `click()` resolves when the press is DISPATCHED, and the walk is three awaited requests
     after that — so reading `wire.deletes` first reads it one round-trip in, and this
     assertion failed on `['/inventory/4/2']` alone when it was written the other way round.
     The row count is the walk's own completion signal, which is why every case above waits on
     it before touching the wire. */
  await expect(rows(page)).toHaveCount(1)

  /* THE ORDER IS THE WHOLE ASSERTION, and it is what makes a cross-drawer stack safe at all.
     The route removes only the newest card in a box and refuses anything else (D10), so each
     of these is legal only because the one before it succeeded — reverse-chronological over
     the sitting preserves reverse-chronological WITHIN each drawer. A stack that sorted by
     box, or by index, would put `/inventory/3/2` before `/inventory/4/1` and earn a refusal
     from a store that was perfectly consistent. */
  expect(wire.deletes).toEqual(['/inventory/3/2', '/inventory/3/1', '/inventory/4/2'])

  await expect(rows(page).first()).toHaveAttribute('aria-label', /Box 4, Section 1, Card 1$/)
})

test('the odometer counts the sitting and says which drawers it went to', async ({ page }) => {
  await open(page)
  await shoot(page, 3)

  const captured = page.locator('.capture-odo .bn-stat').first().locator('.bn-stat-value')
  await expect(captured).toHaveText('3')
  /* THE LEAD-IN IS `bn-sr` (UX-096): visually hidden, absolutely positioned so it costs the
     paragraph no height, but still part of its textContent — hence the prefix here. It
     replaced an `aria-label` on a plain `<p>`, which axe's `aria-prohibited-attr` flags. */
  await expect(page.locator('.capture-odo-split')).toHaveText('Where this sitting went: Box 3 3')

  await switchBox(page, 4)

  /* THE FIGURE SURVIVES THE SWITCH. This is the moment it used to read 0 — on the owner's
     555-card sitting the stat went 394 → 0 → 56 → 0 → 105, three times claiming the work of
     the last twenty minutes had not happened. */
  await expect(captured).toHaveText('3')

  await shootInto(page, 4, 1, 2)
  await expect(captured).toHaveText('5')
  /* THE DOT IS CSS NOW, NOT TYPED TEXT (D218) — `.capture-odo-drawer + .capture-odo-drawer::before`
     draws it, so the two drawers' own text runs together with no separator character. */
  await expect(page.locator('.capture-odo-split')).toHaveText(
    'Where this sitting went: Box 3 3Box 4 2',
  )

  /* THE "INDEX SPAN" STAT IS GONE (UX-052, density): it duplicated the drawer split line a
     few pixels below it, in "index" language the owner called wasted space (D153), and this
     odometer now has exactly two stats — captured, and the next card. */
  await expect(page.locator('.capture-odo .bn-stat')).toHaveCount(2)
})

test('a box with a sold card shows the counted number, never the stored slot (D58, R1c)', async ({
  page,
}) => {
  /* THE TWO NUMBERS DISAGREE ON PURPOSE. `next_index` is the store's high-water mark over
   * every index the box has ever handed out (`store/master.py:next_index`) — 10 cards
   * captured, one later sold, so the mark still reads 11. `on_hand` is what D58 counts: 9
   * cards on hand, so the CARD a fresh capture gets is 10, not 11. A screen that showed 11
   * anywhere would be showing the slot the sold card's replacement will never occupy — D10
   * never reuses a stored index — as if it were the count. */
  const SOLD_BOX = {
    ...BOX,
    cards: 10,
    sold: 1,
    on_hand: 9,
    next_index: 11,
  }
  await open(page, { boxes: [SOLD_BOX, BOX4], nextIndex: { '3': 11 } })

  /* THE BOX ROW, CLOSED. `10`, never `11`, and the word is "card", never "index" (D196). */
  const boxRow = page.locator('.capture-row').filter({ hasText: /Box/ })
  await expect(boxRow).toContainText('card 10')
  await expect(boxRow).not.toContainText('11')
  await expect(boxRow).not.toContainText(/index/i)

  /* THE ODOMETER'S "NEXT CARD" STAT, THE SAME NUMBER. Two stats — captured, next card — so
   * the second one is the one this reads. */
  await expect(page.locator('.capture-odo .bn-stat').nth(1).locator('.bn-stat-value')).toHaveText(
    '10',
  )

  /* THE STAGE FOOT, THE THIRD PLACE THIS FACT IS DRAWN. Camera opened by `open()` already,
   * so the foot is live. */
  await expect(page.locator('.capture-foot-next')).toContainText('card 10')
  await expect(page.locator('.capture-foot-next')).not.toContainText('11')
})

/** Reads the same number off all three surfaces (Box row, odometer, stage foot) and fails
 *  loudly if they disagree — the R1d bug's own shape. */
async function nextCardEverywhere(page: Page): Promise<number> {
  const boxText = await page
    .locator('.capture-row')
    .filter({ hasText: /Box/ })
    .innerText()
  const boxMatch = /card (\d+)/.exec(boxText)
  const odoText = await page
    .locator('.capture-odo .bn-stat')
    .nth(1)
    .locator('.bn-stat-value')
    .innerText()
  const footText = await page.locator('.capture-foot-next').innerText()
  const footMatch = /card (\d+)/.exec(footText)
  if (boxMatch === null || footMatch === null) {
    throw new Error(`"next card N" not found: box="${boxText}" foot="${footText}"`)
  }
  expect(boxMatch[1], 'box row vs odometer').toBe(odoText)
  expect(footMatch[1], 'stage foot vs odometer').toBe(odoText)
  return Number(odoText)
}

test('the counted number stays true across a sitting: every capture, every undo (D58, R1d)', async ({
  page,
}) => {
  /* THE BUG THIS CASE CATCHES: `on_hand` is a fact off `GET /boxes`, and nothing re-fetches
   * it on a capture or an undo — only a field open/close, a box creation or a divider do.
   * So three captures with no field touched, using the R1c fix alone, drew the SAME "next
   * card N" three times running: the number came from a `boxRecords` entry that never
   * moved. Red on d452b5c4 for exactly that reason. */
  await open(page)

  await page.keyboard.press('c')
  await expect(rows(page).first()).toHaveAttribute('aria-label', /Box 3, Section 1, Card 1$/)
  const afterFirst = await nextCardEverywhere(page)

  await page.keyboard.press('c')
  await expect(rows(page).first()).toHaveAttribute('aria-label', /Box 3, Section 1, Card 2$/)
  const afterSecond = await nextCardEverywhere(page)
  expect(afterSecond).toBe(afterFirst + 1)

  await page.keyboard.press('c')
  await expect(rows(page).first()).toHaveAttribute('aria-label', /Box 3, Section 1, Card 3$/)
  const afterThird = await nextCardEverywhere(page)
  expect(afterThird).toBe(afterFirst + 2)

  await page.keyboard.press('u')
  await expect(rows(page)).toHaveCount(2)
  const afterUndo = await nextCardEverywhere(page)
  expect(afterUndo).toBe(afterSecond)
})

test('a departed card in the box and several live captures in the same sitting (D58, R2)', async ({
  page,
}) => {
  /* THE TWO BUGS TOGETHER, NOT SEPARATELY. R1c proved the STATIC divergence (a box that
   * already carries a sold card shows the counted number, not the stored slot) and R1d
   * proved the DYNAMIC tracking (the number moves with every capture). Neither alone
   * proves the box starts already offset AND keeps counting correctly on top of that
   * offset — a box with a departed card, on_hand 4 of 5 stored, where three fresh
   * captures must read 5, 6, 7, never 6, 7, 8 (which is what the stored slot, still
   * climbing from 6, would answer) and never 5, 5, 5 (which is what a `boxRecords` read
   * with no per-capture patch — the R1d bug — would answer). */
  const DEPARTED_BOX = {
    ...BOX,
    cards: 5,
    sold: 1,
    on_hand: 4,
    next_index: 6,
  }
  await open(page, {
    boxes: [DEPARTED_BOX, BOX4],
    nextIndex: { '3': 6 },
    onHandStart: { '3': 4 },
  })

  // BEFORE ANY CAPTURE: on_hand 4, so the upcoming card — the 5th on hand — reads 5.
  expect(await nextCardEverywhere(page)).toBe(5)

  await page.keyboard.press('c')
  await expect(rows(page).first()).toHaveAttribute('aria-label', /Box 3, Section 1, Card 6$/)
  expect(await nextCardEverywhere(page)).toBe(6)

  await page.keyboard.press('c')
  await expect(rows(page).first()).toHaveAttribute('aria-label', /Box 3, Section 1, Card 7$/)
  expect(await nextCardEverywhere(page)).toBe(7)

  await page.keyboard.press('c')
  await expect(rows(page).first()).toHaveAttribute('aria-label', /Box 3, Section 1, Card 8$/)
  expect(await nextCardEverywhere(page)).toBe(8)
})

test('the strip does not change height when the drawer label appears (D118)', async ({
  page,
}) => {
  await open(page)

  /* DOCUMENT-RELATIVE, NEVER `boundingBox()`. That returns VIEWPORT coordinates, and opening
     the Box field scrolls the page — so the naive version of this test compared a `y` of -151
     against one of 56 and reported a 207px move that was entirely the scrollbar. What D118
     forbids is a change in the DOCUMENT's layout, so that is what is measured: `rect.top +
     scrollY`, which no scroll can move. */

  /* THE SPLIT LINE BEFORE ANY CAPTURE AT ALL, which is the state its `min-height` exists for
     and the one the first version of this test never visited — it measured at three captures,
     where the line already has a drawer in it and holds its own height for free. Deleting the
     floor SURVIVED that. The transition that binds is empty → occupied, on the very first
     card, and the height is asserted rather than the top: the odometer's verdict pill appears
     in the same instant (`runCount` stops being null) and that is a pre-existing part of the
     header, not this line's business. */
  const splitEmpty = await place(page, '.capture-odo-split')
  await shoot(page, 3)
  const splitFilled = await place(page, '.capture-odo-split')
  expect(splitFilled.height).toBe(splitEmpty.height)

  // One drawer, so no row carries a label yet.
  await expect(page.locator('.capture-undo-drawer')).toHaveCount(0)
  const before = await place(page, '.capture-undo-list')
  const splitBefore = await place(page, '.capture-odo-split')

  await switchBox(page, 4)
  await shootInto(page, 4, 1, 1)

  // Now every row carries one, and the caption it lives in is absolute over the thumbnail.
  await expect(page.locator('.capture-undo-drawer')).toHaveCount(4)
  const after = await place(page, '.capture-undo-list')
  const splitAfter = await place(page, '.capture-odo-split')

  /* THE STRIP IS THE SAME HEIGHT AND IN THE SAME PLACE. The row's height is the thumbnail's
     `aspect-ratio` and the drawer label lives in a caption that is absolute against it, so the
     label grows UPWARD over the photograph and reaches no layout at all. A label added as a
     normal-flow line would add ~15px per row here and push the whole page down. */
  expect(after).toEqual(before)

  /* AND THE SPLIT LINE HELD ITS HEIGHT AND ITS PLACE while going from one drawer to two — it
     is floored by `min-height` for exactly this, so the header does not grow under the
     operator's hands at the moment they change drawers. */
  expect(splitAfter).toEqual(splitBefore)
})

/** Where an element sits in the DOCUMENT and how big it is — scroll-independent, which
 *  `boundingBox()` is not. Rounded, because a fractional layout that differs in the sixth
 *  decimal is not a thing a person can see and not what D118 is about. */
async function place(page: Page, selector: string): Promise<{ top: number; height: number }> {
  return page.locator(selector).evaluate((el) => {
    const rect = el.getBoundingClientRect()
    return { top: Math.round(rect.top + window.scrollY), height: Math.round(rect.height) }
  })
}

/** The corner control on each row — section 6, `removeCardInPlace`, beside `undoBack` and
 *  never instead of it. */
function drops(page: Page) {
  return page.locator('.capture-undo-drop')
}

/* ════════════════════════════════════════════════════════════════════════════════════════
 * SECTION 6: THE GRANULARITY THE OWNER ASKED FOR UNPROMPTED (docs/specs/undo.md §6) —
 * "there's currently no way to undo an image that's in the middle of the capturings without
 * losing all the subsequent capturings from that session." `removeCardInPlace` is D10 ruling
 * 1's OTHER route: it deletes one card anywhere in a box and slides every higher card down
 * one, and it already exists (`BoxBrowse.tsx:2418`). This is reach, not a build — a second
 * control on each row, beside the one `undoBack` already owns. `U` and a whole-row click are
 * untouched by every case below.
 * ════════════════════════════════════════════════════════════════════════════════════════ */

/* UN-3 (Q2, "keep the confirm here only"): "never ask" holds everywhere else, and this press
 * is the one exception the owner named — so its words carry the whole weight of that
 * exception. The dialog has to say plainly what the recommended undo-and-set-aside would have
 * made unnecessary to say: this is permanent, and the photograph goes with the record. */
test('the one confirm this screen keeps says plainly that the removal is permanent and deletes the photo', async ({
  page,
}) => {
  await open(page)
  await shoot(page, 3)

  await drops(page).nth(1).click()
  const body = page.locator('.inv-dialog-body')
  await expect(body).toContainText('permanently deletes')
  await expect(body).toContainText('photograph')
})

test('removing a middle row deletes that card alone, and the later ones survive shifted', async ({
  page,
}) => {
  const wire = await open(page)
  await shoot(page, 5)

  // Row 2 is Card 3 (newest-first: 5, 4, 3, 2, 1).
  await expect(rows(page).nth(2)).toHaveAttribute('aria-label', /Card 3$/)
  await drops(page).nth(2).click()

  await expect(page.getByRole('heading', { name: 'Remove just this card?' })).toBeVisible()
  await page.getByRole('button', { name: 'Remove this card' }).click()

  await expect(rows(page)).toHaveCount(4)
  expect(wire.removes).toEqual(['/inventory/3/3/remove'])
  // ONLY THE ONE REQUEST — not a walk, not a second delete for the row that slid into its
  // place. That is what distinguishes this from `undoBack`'s own multi-row press.
  expect(wire.deletes).toEqual([])

  /* CARD 3 IS GONE. Cards 4 and 5 are not — they SLID to 3 and 4, which is the physical truth
     D10 ruling 1 permits the renumber for. Cards 1 and 2, below the cut, are untouched and
     keep their server-rendered labels; the two that shifted fall back to the bare store key,
     because `pipeline/join.py:Position.label` composed the old string against an index that
     is no longer theirs and this screen never composes a second one (D67). */
  await expect(rows(page).nth(0)).toHaveAttribute('aria-label', /B3 #4$/)
  await expect(rows(page).nth(1)).toHaveAttribute('aria-label', /B3 #3$/)
  await expect(rows(page).nth(2)).toHaveAttribute('aria-label', /Card 2$/)
  await expect(rows(page).nth(3)).toHaveAttribute('aria-label', /Card 1$/)

  // The receipt says how many labels just changed — the honesty `BoxBrowse.tsx`'s own remove
  // toast already carries, matched rather than reworded.
  await expect(page.locator('.capture-undo .capture-quiet').last()).toContainText('2 cards')
})

test('removing the newest row costs nothing else — no shift, and the note says so', async ({
  page,
}) => {
  const wire = await open(page)
  await shoot(page, 2)

  await drops(page).nth(0).click()
  await page.getByRole('button', { name: 'Remove this card' }).click()

  await expect(rows(page)).toHaveCount(1)
  expect(wire.removes).toEqual(['/inventory/3/2/remove'])
  await expect(page.locator('.capture-undo .capture-quiet').last()).toContainText(
    'nothing else moved',
  )
})

test('a blocked removal reaches the operator as a sentence naming what blocked it', async ({
  page,
}) => {
  const wire = await open(page, { blockRemoveOf: 3 })
  await shoot(page, 5)

  await drops(page).nth(2).click()
  await page.getByRole('button', { name: 'Remove this card' }).click()

  // NOTHING LEFT THE LIST. The refusal changed nothing, which is the whole point of a route
  // that checks before it writes a single file.
  await expect(rows(page)).toHaveCount(5)
  expect(wire.removes).toEqual(['/inventory/3/3/remove'])

  // THE DIALOG CLOSED, so the sentence is not trapped behind its own overlay.
  await expect(page.getByRole('heading', { name: 'Remove just this card?' })).toBeHidden()

  // AND THE SENTENCE NAMES WHAT BLOCKED IT — the server's own words, which is what "reaches
  // the operator" means on this screen (`describe()`, matched by every other refusal here).
  const refusal = page.locator('.capture-undo .capture-refused')
  await expect(refusal).toContainText('card 6 is sold')
  await expect(page.locator('.capture-halt-code')).toHaveText('renumber_blocked')

  // NO REGISTERED WORD FOR THE MECHANISM (D196): the sentence the operator reads never says
  // "capture id" or names the route, only what blocked it and why.
  await expect(refusal).not.toContainText('capture_id')
  await expect(refusal).not.toContainText('/inventory/')
})

/* ------------------------------------------------------------------------------------------
 * THE PAUSE/PLAY OVERLAY (owner, 2026-09-24, verbatim): "we shouldn't change any actions from
 * how it operates now, this pause button should literally be like if i switched it off motion
 * mode and play being switching it back onto motion mode." It calls the exact `switchTrigger`
 * the Trigger field's own track calls, through a button on the pane and through Space — no new
 * state, no new hold, no behaviour of its own. This is the file that captures for real
 * (capture-claims.spec.ts's own rule is the opposite), so it is the one that can prove the
 * manual key genuinely fires while paused and genuinely does not once resumed.
 * ------------------------------------------------------------------------------------------ */

/** Arms motion on the box `open()` already picked. D211 folds the Rig once a box is known;
 *  unfolded here defensively, the way the odometer test above does it. */
async function armMotion(page: Page): Promise<void> {
  const rigSummary = page.locator('.capture-rig-summary')
  if ((await rigSummary.getAttribute('aria-expanded')) === 'false') await rigSummary.click()
  await page.getByRole('button', { name: /Trigger/ }).click()
  await page.getByRole('button', { name: 'motion', exact: true }).click()
  await page.keyboard.press('Escape')
  await expect(page.locator('.capture-trigger')).toHaveAttribute('data-trigger', 'motion')
}

function pauseplay(page: Page) {
  return page.locator('.capture-pauseplay')
}

test('the pause button switches motion off, and the manual key fires while it is down', async ({
  page,
}) => {
  const wire = await open(page)
  await armMotion(page)
  await expect(pauseplay(page)).toHaveClass(/is-running/)

  await pauseplay(page).click()
  await expect(pauseplay(page)).toHaveClass(/is-paused/)
  await expect(pauseplay(page)).toHaveAccessibleName(/Resume motion/)
  // `switchTrigger('manual')` is the same call the track's own `key` cell makes — the machine
  // string is `manual:c`, not a name this button invented.
  await expect(page.locator('.capture-trigger')).toHaveAttribute('data-trigger', 'manual:c')

  // C is disarmed in motion mode and live in manual (map.py's own rule); firing it for real
  // is the proof that pausing switched the mode rather than only redrawing the button.
  await page.keyboard.press('c')
  await expect.poll(() => wire.captures).toBe(1)
})

test('the play button switches motion back on, and the manual key stops firing again', async ({
  page,
}) => {
  const wire = await open(page)
  await armMotion(page)
  await pauseplay(page).click()
  await expect(page.locator('.capture-trigger')).toHaveAttribute('data-trigger', 'manual:c')

  await pauseplay(page).click()
  await expect(pauseplay(page)).toHaveClass(/is-running/)
  await expect(pauseplay(page)).toHaveAccessibleName(/Pause motion/)
  await expect(page.locator('.capture-trigger')).toHaveAttribute('data-trigger', 'motion')

  await page.keyboard.press('c')
  // Asserted against something that DOES change on a real fire (the odometer's own count),
  // rather than a fixed pause after a negative — the wait this repo refuses elsewhere.
  await expect(page.locator('.capture-odo .bn-stat-value').first()).toHaveText('0')
  expect(wire.captures).toBe(0)
})

test('Space is the same toggle, and does nothing while typing', async ({ page }) => {
  await open(page)
  await armMotion(page)
  await page.keyboard.press(' ')
  await expect(page.locator('.capture-trigger')).toHaveAttribute('data-trigger', 'manual:c')
  await page.keyboard.press(' ')
  await expect(page.locator('.capture-trigger')).toHaveAttribute('data-trigger', 'motion')

  // Typing a space into the Box field's own entry must type a space, not toggle the trigger.
  await page.keyboard.press('b')
  const entry = page.locator('.capture-filter')
  await entry.fill('New')
  await entry.press(' ')
  await expect(entry).toHaveValue('New ')
  await expect(page.locator('.capture-trigger')).toHaveAttribute('data-trigger', 'motion')
  await page.keyboard.press('Escape')
})

test('pressing the pause button moves nothing else on the screen (D118)', async ({ page }) => {
  await open(page)
  await armMotion(page)
  const before = await shutter(page).boundingBox()
  await pauseplay(page).click()
  const after = await shutter(page).boundingBox()
  expect(after).toEqual(before)
})

/* ------------------------------------------------------------------------------------------
 * UX-076 (owner, 2026-09-24): "do we have that data? if so name the reason." `halt.code`
 * already carried the server's own code; `CaptureScreen.tsx`'s `HALT_CODE_INFO` now maps
 * each one `POST /capture`'s call chain can answer with to its own headline, never the raw
 * code (D196) — that still shows only behind "What the server said". One case per code, plus
 * the fallback for a code this roster does not know.
 * ------------------------------------------------------------------------------------------ */

const HALT_CODES: readonly { code: string; headline: string }[] = [
  { code: 'server_busy', headline: 'the server is answering too many requests right now' },
  { code: 'origin_not_allowed', headline: 'this page is not the one the server trusts to write' },
  { code: 'box_closed', headline: 'that box was sealed just now' },
  { code: 'store_busy', headline: 'the store is busy' },
  { code: 'store_unavailable', headline: 'the store could not be reached' },
  { code: 'inventory_conflict', headline: 'the store disagreed with what this screen expected' },
  { code: 'game_invalid', headline: 'capturing as a game the server does not know' },
  { code: 'game_unverified', headline: 'this game has no export to join against' },
  { code: 'rarity_claim_invalid', headline: 'the Rarity claim no longer matches this game' },
  { code: 'variant_invalid', headline: 'the Finish claim no longer matches this game' },
  { code: 'box_required', headline: 'no box reached the server' },
  { code: 'box_invalid', headline: 'the box number did not reach the server whole' },
  { code: 'image_required', headline: 'no photograph reached the server' },
  { code: 'image_invalid', headline: 'the photograph did not reach the server intact' },
  { code: 'image_too_large', headline: 'the photograph was too large to send' },
  { code: 'image_not_jpeg', headline: 'the camera sent a frame the server will not store' },
  { code: 'server_error', headline: 'the server hit a bug' },
]

/** Overrides `open()`'s own always-succeeds `/capture` stub with one refusal, carrying the
 *  code a case names. Playwright takes the newest handler, so this shadows it without
 *  needing a second `open()` variant. */
async function refuseCapture(page: Page, code: string): Promise<void> {
  await page.route(/\/capture$/, (route) =>
    route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({ error: { code, message: `refused: ${code}` } }),
    }),
  )
}

for (const { code, headline } of HALT_CODES) {
  test(`a ${code} halt reads its own headline, never the raw code`, async ({ page }) => {
    await open(page)
    await refuseCapture(page, code)
    await page.keyboard.press('c')

    const title = page.locator('.capture-halt-title')
    await expect(title).toContainText(headline)
    // D196: the code itself is never the headline — it is only behind the disclosure.
    await expect(title).not.toContainText(code)
    await expect(page.locator('.capture-halt-code')).toHaveText(code)
  })
}

test('an unmapped code falls back to the honest, hedged sentence', async ({ page }) => {
  await open(page)
  await refuseCapture(page, 'a_code_this_roster_does_not_know')
  await page.keyboard.press('c')

  await expect(page.locator('.capture-halt-title')).toHaveText(
    'Captures are paused — check whether that card was recorded.',
  )
  await expect(page.locator('.capture-halt-code')).toHaveText('a_code_this_roster_does_not_know')
})

/* F5, THE PR 2 INTEGRATION REVIEW: A DEGRADED PLACE CARRIES `box_total: 0`, AND THAT IS "NO
 * COUNT", NEVER "AN EMPTY BOX". The server answers a pooled card's place, and a place whose
 * position will not read, with `box_total: 0` beside `located: false` or a null label. The
 * capture used to write that 0 onto the box row, so the next card read "1" in a box holding 9.
 * The row keeps its last known count now. */
test('a capture whose place is unlabeled never writes a zero count onto the box', async ({ page }) => {
  const SOLD_BOX = { ...BOX, cards: 10, sold: 1, on_hand: 9, next_index: 11 }
  await open(page, { boxes: [SOLD_BOX, BOX4], nextIndex: { '3': 11 } })
  expect(await nextCardEverywhere(page)).toBe(10)

  await page.route(/\/capture$/, (route) =>
    route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        box: 3,
        index: 11,
        key: '3/11',
        label: 'Box 3, Section 1, Card 11',
        section: 1,
        card: 11,
        new_box: false,
        created: true,
        photo: '/tmp/3-11.jpg',
        capture_id: null,
        place: { box_total: 0, label: null, located: true },
      }),
    }),
  )
  await shootInto(page, 3, 11, 1)
  expect(await nextCardEverywhere(page), 'the box row keeps its count, never "next card 1"').toBe(10)
})
