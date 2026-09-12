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
 *  this is a list and never a set. */
type Wire = { deletes: string[]; captures: number }

async function open(
  page: Page,
  options: { refuseDeleteFrom?: number; nextIndex?: Record<string, number> } = {},
): Promise<Wire> {
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
      body: JSON.stringify({ cards: 0, next_index: options.nextIndex ?? {} }),
    }),
  )
  await page.route(/\/boxes$/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ boxes: [BOX, BOX4] }),
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
        label: `Box ${box} · Section 1 · Card ${index}`,
        section: 1,
        card: index,
        new_box: index === 1,
        created: true,
        photo: `/tmp/${box}-${index}.jpg`,
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
  /* The camera opens on an explicit press and not on load — the screen says so in the field
     itself ("Nothing on this screen reaches for it until you ask, so opening the app raises
     no permission prompt"), so a test that skipped the button would be skipping the design.
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
      new RegExp(`Box ${box} · Section 1 · Card ${first + at}$`),
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
 * (docs/DEBTS.md §9). Nothing in this suite reached the branch: the fix shipped in `42e6b96` with
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
  await expect(rows(page).nth(0)).toHaveAttribute('aria-label', /Box 4 · Section 1 · Card 2$/)
  await expect(rows(page).nth(1)).toHaveAttribute('aria-label', /Box 4 · Section 1 · Card 1$/)
  await expect(rows(page).nth(2)).toHaveAttribute('aria-label', /Box 3 · Section 1 · Card 3$/)
  await expect(rows(page).nth(4)).toHaveAttribute('aria-label', /Box 3 · Section 1 · Card 1$/)

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
  await expect(rows(page).first()).toHaveAttribute('aria-label', /Box 3 · Section 1 · Card 2$/)

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
  await expect(rows(page).nth(0)).toHaveAttribute('aria-label', /Box 3 · Section 1 · Card 2$/)
  await expect(rows(page).nth(1)).toHaveAttribute('aria-label', /Box 3 · Section 1 · Card 1$/)
  await expect(rows(page).nth(2)).toHaveAttribute('aria-label', /Box 4 · Section 1 · Card 2$/)
  await expect(rows(page).nth(3)).toHaveAttribute('aria-label', /Box 4 · Section 1 · Card 1$/)

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

  await expect(rows(page).first()).toHaveAttribute('aria-label', /Box 4 · Section 1 · Card 1$/)
})

test('the odometer counts the sitting and says which drawers it went to', async ({ page }) => {
  await open(page)
  await shoot(page, 3)

  const captured = page.locator('.capture-odo .bn-stat').first().locator('.bn-stat-value')
  await expect(captured).toHaveText('3')
  await expect(page.locator('.capture-odo-split')).toHaveText('Box 3 3')

  await switchBox(page, 4)

  /* THE FIGURE SURVIVES THE SWITCH. This is the moment it used to read 0 — on the owner's
     555-card sitting the stat went 394 → 0 → 56 → 0 → 105, three times claiming the work of
     the last twenty minutes had not happened. */
  await expect(captured).toHaveText('3')

  await shootInto(page, 4, 1, 2)
  await expect(captured).toHaveText('5')
  await expect(page.locator('.capture-odo-split')).toHaveText('Box 3 3 · Box 4 2')

  /* THE SPAN STAYS IN ONE DRAWER'S INDEX SPACE, because two drawers do not share one. `1–2`
     is box 4's; a sitting-wide span would read `1–3` and mean nothing. */
  const span = page.locator('.capture-odo .bn-stat').nth(2).locator('.bn-stat-value')
  await expect(span).toHaveText('1–2')
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
