import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

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

const GAMES = {
  default: 'pokemon',
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

/** Every DELETE the screen sent, in order. The ORDER is the assertion — newest first — so
 *  this is a list and never a set. */
type Wire = { deletes: string[]; captures: number }

async function open(page: Page, options: { refuseDeleteFrom?: number } = {}): Promise<Wire> {
  const wire: Wire = { deletes: [], captures: 0 }

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
      body: JSON.stringify({ cards: 0, next_index: {} }),
    }),
  )
  await page.route(/\/boxes$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ boxes: [BOX] }),
    }),
  )

  /* The store, as far as this screen can tell: an index that climbs by one per capture and
     the label `pipeline/join.py:Position` would render for an undeclared box — one section,
     card = index (D10, amended 2026-08-29). Composed here rather than imported because the
     app must never compose one; a fixture that got it wrong would be testing itself. */
  await page.route(/\/capture$/, (route) => {
    wire.captures += 1
    const index = wire.captures
    route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        box: 3,
        index,
        key: `3/${index}`,
        label: `Box 3 · Section 1 · Card ${index}`,
        section: 1,
        card: index,
        new_box: index === 1,
        created: true,
        photo: `/tmp/3-${index}.jpg`,
        capture_id: null,
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
            message: 'Box 3 · Section 1 · Card 4 is the newest card in box 3.',
          },
        }),
      })
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ deleted: path.replace('/inventory/', '') }),
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

  await page.goto('/#/')
  await expect(page.locator('.capture-row').filter({ hasText: /Finish/ })).toBeVisible()

  // The box, by name, then the camera, by its row. Both keyboard: this screen's own path.
  await page.keyboard.press('b')
  await expect(page.locator('.capture-opt').filter({ hasText: /S key/ })).toBeVisible()
  await page.keyboard.type('3')
  await page.keyboard.press('Enter')
  /* The camera opens on an explicit press and not on load — the screen says so in the field
     itself ("Nothing on this screen reaches for it until you ask, so opening the app raises
     no permission prompt"), so a test that skipped the button would be skipping the design.
     The device list only exists after it. */
  await page.keyboard.press('v')
  await page.getByRole('button', { name: 'Open the camera' }).click()
  await page.locator('.capture-opt').filter({ hasText: /Canvas Cam Link/ }).click()
  await page.keyboard.press('Escape')
  await expect(page.locator('.pull-confirm')).toBeEnabled()
  return wire
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
  for (let at = 1; at <= count; at += 1) {
    await page.keyboard.press('c')
    await expect(rows(page).first()).toHaveAttribute('aria-label', new RegExp(`Card ${at}$`))
  }
}

function rows(page: Page) {
  return page.locator('.capture-undo-row')
}

test('the stack is the session, newest first, capped at ten', async ({ page }) => {
  await open(page)
  await shoot(page, 12)

  /* TWELVE CAPTURES, TEN ROWS. `UNDO_DEPTH` is the owner's number and the list is capped at
     it — the two oldest cards are still in the store and simply out of reach of this
     control, which is what the cap means. */
  await expect(rows(page)).toHaveCount(10)

  // Newest first: card 12 on top, card 3 at the bottom of the ten.
  /* THE ADDRESS IS READ OFF `aria-label` AND NOT OFF THE TEXT — D41's repair, right twice
     over. `PositionLabel` draws the path as a muted stack and the slot as a figure, so no
     contiguous `Card N` survives in the text content; the label rides `aria-label`
     verbatim, which is what keeps the split a view of the server's string. That entry also
     records the trap in the other direction: a text assertion of this shape goes VACUOUS
     the day the DOM stops containing the string, and passes forever after. */
  await expect(rows(page).first()).toHaveAttribute('aria-label', /Card 12$/)
  await expect(rows(page).last()).toHaveAttribute('aria-label', /Card 3$/)

  /* THE TOP ROW CARRIES ITS KEY AND THE REST CARRY THEIR DEPTH. The number on row N is how
     many cards that press deletes, which is also its ordinal — the same number twice, which
     is what makes one chip able to say both. */
  await expect(rows(page).nth(0).locator('.capture-key')).toHaveText('U')
  await expect(rows(page).nth(1).locator('.capture-key')).toHaveText('2')
  await expect(rows(page).nth(9).locator('.capture-key')).toHaveText('10')

  // And the heading says how many rows there are, because the list is capped and scrolls.
  await expect(page.locator('.capture-undo-depth')).toHaveText('10 recent')
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
