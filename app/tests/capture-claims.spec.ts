import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import type { GameRegistry } from '../src/types'

/* THE CAPTURE SCREEN'S CLAIM CONTROLS, IN A BROWSER — the screen the owner spends the most
 * hours in, and the one whose controls nothing ran until this file existed.
 *
 * `motion-live.spec.ts` is the other spec on this screen and it is about the trigger: it
 * takes the screen as it comes and never touches a field. So when D3 rung 1's finish claim
 * became a SET on 2026-08-23 and the Finish track went from single-select to multi-select,
 * `tsc`, `eslint` and every Playwright spec in the tree stayed green over a control that
 * had never been pressed by anything but a human. That is the same shape as the failure
 * `docs/GATES.md` records for 7b — four green checks and three screens nobody could open —
 * and this file is the check for this control.
 *
 * NO CAPTURE IS EVER TAKEN. `GET /games` is intercepted so the vocabulary is fixed rather
 * than whatever `pipeline/games.py` authors today, and the shutter is never pressed — the
 * same rule `motion-live.spec.ts` states for the same reason: a capture would POST into a
 * real store. Every assertion here is about what the control HOLDS, which is what decides
 * what the wire would carry.
 *
 * "ONLY READS ARE STUBBED, AND NO BOX IS EVER SELECTED" WAS THE RULE AND HALF OF IT MOVED on
 * 2026-08-29, when the divider act arrived: `S` writes to a BOX, so its cases have to have
 * one selected and have to stub `POST /boxes/<box>/sections`. The property that mattered is
 * kept and is stated as itself — nothing here reaches a store — and `/capture` is stubbed to
 * FAIL in those cases, so a stray press says so instead of writing a card. The spec that
 * genuinely captures is `capture-undo.spec.ts`, which is a separate file for exactly this
 * reason.
 *
 * IT IS NOT A HARNESS TEST AND MUST NOT BECOME ONE. `docs/GATES.md`'s contract is seven
 * Python tests at the Stop hook; this starts a browser, which `make design-check` runs.
 */

/** Pokemon's three finishes and a rarity matrix that narrows: `Common` stocks `normal`
 *  alone, so claiming it excludes the other two. Verbatim from the registry's shape, cut to
 *  what these cases read — a fixture that invented a fourth finish would be testing itself. */
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

/** Pokemon's THIRTEEN rarities, verbatim from `pipeline/games.py` — stack order and matrix
 *  both. The three-rarity fixture above cannot see the case these last cases are about: the
 *  option alphabet only runs past the digits when a vocabulary does, and Pokemon's is the
 *  longest one any game authors. Copied rather than trimmed for the header's reason — a
 *  fixture that invented a rarity would be testing itself. */
const THIRTEEN = {
  default: 'pokemon',
  games: [
    {
      ...GAMES.games[0],
      rarities: [
        'Common',
        'Uncommon',
        'Rare',
        'Holo Rare',
        'Double Rare',
        'Radiant Rare',
        'ACE SPEC Rare',
        'Illustration Rare',
        'Ultra Rare',
        'Special Illustration Rare',
        'Hyper Rare',
        'Secret Rare',
        'Rainbow Rare',
      ],
      finish_by_rarity: {
        Common: ['normal', 'holo', 'reverse_holo'],
        Uncommon: ['normal', 'holo', 'reverse_holo'],
        Rare: ['normal', 'holo', 'reverse_holo'],
        'Holo Rare': ['holo', 'reverse_holo'],
        'Double Rare': ['holo'],
        'Radiant Rare': ['holo'],
        'ACE SPEC Rare': ['holo'],
        'Illustration Rare': ['holo'],
        'Ultra Rare': ['holo'],
        'Special Illustration Rare': ['holo'],
        'Hyper Rare': ['holo'],
        'Secret Rare': ['holo'],
        'Rainbow Rare': ['holo'],
      },
    },
  ],
}

async function open(
  page: Page,
  session?: Record<string, string>,
  games: unknown = GAMES,
): Promise<void> {
  await page.route(/\/games$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(games),
    })
  })
  await page.route(/\/status$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ cards: 0, next_index: {} }),
    })
  })

  /* Seeded BEFORE the app script runs, because `readSessionFinish` is the `useState`
     initialiser — it reads once, on the first render, and a value written afterwards would
     never be seen. This is how a tab that was already open when the claim shape changed is
     reproduced (D27). */
  if (session !== undefined) {
    await page.addInitScript((entries: Record<string, string>) => {
      for (const [key, value] of Object.entries(entries)) {
        window.sessionStorage.setItem(key, value)
      }
    }, session)
  }

  await page.goto('/#/capture')
  await expect(finishRow(page)).toBeVisible()

  /* AND THE SCREEN IS PROVABLY LISTENING BEFORE THIS RETURNS. Every case below presses a
     letter the moment this helper hands back, and a visible row is not the same fact as a
     subscribed handler: `CaptureScreen.tsx`'s key listener is registered in an effect whose
     dependencies include `gameEntry`, React runs passive effects AFTER paint, and Playwright
     sees the paint. A press dispatched inside that window reaches a document with nobody
     listening and is gone — there is no queue for it to sit in. Measured on this tree: 1
     whole-file run in 4 lost the very first press of the first case to start, always in
     `openFinish`, and it read as the Finish track never existing.

     SO IT PRESSES UNTIL ONE LANDS, and the retry is over the TEST's timing rather than the
     screen's behaviour. `F` opens the Finish field, `Escape` puts the screen back exactly as
     it was, and no case reaches its own first press without a listener behind it. It weakens
     nothing: `F` still has to open that field for this to return at all, and the case that is
     ABOUT the field letters presses once and asserts once, with no retry of its own. */
  await expect(async () => {
    await page.keyboard.press('f')
    await expect(finishCells(page).first()).toBeVisible({ timeout: 1_000 })
  }).toPass({ timeout: 15_000 })
  await page.keyboard.press('Escape')
  await expect(finishCells(page)).toHaveCount(0)
}

/** The Finish row, open or collapsed. `capture-trackline` is the open track's wrapper, so
 *  this matches the row by its label either way. */
function finishRow(page: Page) {
  return page.locator('.capture-row, .capture-open').filter({ hasText: /Finish/ }).first()
}

function finishCells(page: Page) {
  return page.locator('.capture-track[aria-label="Finish"] .capture-cell')
}

/* THE CELLS ARE NAMED BY THEIR LABEL NOW, AND THE ENUM IS ASSERTED ONE LAYER DOWN.
 * `CaptureScreen.tsx:finishLabel` draws `reverse_holo` as `Reverse holo`, and the owner
 * ruled for the label (2026-09-03) — the raw member is no longer text on the cell and is
 * not on its accessible name either, so a text selector for `reverse_holo` can only be a
 * selector for a string the product deliberately stopped drawing.
 *
 * WHAT THAT WOULD COST IF IT WERE ALL THAT MOVED: the label is a rendering and the MEMBER is
 * what the wire carries, so pointing a click at a label and asserting nothing else would
 * leave `Reverse holo` free to store `holo`. It is not all that moved, and the join is
 * asserted in BOTH directions rather than assumed — the cases that claim a member read
 * `pkmnscan.session.finish` back and name it, and the legacy-session case seeds the MEMBER
 * and asserts the labelled cell it presses. */
const FINISH = {
  normal: /^Normal$/,
  holo: /^Holo$/,
  reverse_holo: /^Reverse holo$/,
} as const

function finishCell(page: Page, member: keyof typeof FINISH) {
  return finishCells(page).filter({ hasText: FINISH[member] })
}

async function openFinish(page: Page): Promise<void> {
  await page.keyboard.press('f')
  await expect(finishCells(page).first()).toBeVisible()
}

test('the finish claim is a SET: two cells read as pressed at once', async ({ page }) => {
  await open(page)
  await openFinish(page)

  /* THE STATE THE PRODUCT HAD NO WAY TO EXPRESS BEFORE. D3: a stack that genuinely holds two
     finishes could either name one and be wrong about half the cards, or claim nothing and
     throw away the half of the truth the operator did know. Both are worse than saying what
     is true, and a single-select track is what made them the only options. */
  await finishCell(page, 'normal').click()
  await finishCell(page, 'reverse_holo').click()

  await expect(finishCell(page, 'normal')).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(finishCell(page, 'reverse_holo')).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  /* And an unclaimed member is not pressed — a multi-select, not a track that latches on. */
  await expect(finishCell(page, 'holo')).toHaveAttribute(
    'aria-pressed',
    'false',
  )
})

test('the claim is stored in the game’s enum order, never the order it was tapped', async ({
  page,
}) => {
  await open(page)
  await openFinish(page)

  /* Tapped backwards through the enum on purpose. `pipeline/variant.py:_check_claim`,
     `identify/sidecar.py:_check_variant` and the capture route all canonicalise to the
     game's own order so that two identical claims are ONE value; the screen doing it too is
     what makes the value the wire carries already canonical, so a restated correction diffs
     as no change instead of churning a sidecar and a history line. */
  await finishCell(page, 'reverse_holo').click()
  await finishCell(page, 'normal').click()

  const stored = await page.evaluate(() =>
    window.sessionStorage.getItem('pkmnscan.session.finish'),
  )
  expect(stored).toBe(JSON.stringify(['normal', 'reverse_holo']))
})

test('re-tapping the last claimed cell clears the claim, and stores nothing', async ({
  page,
}) => {
  await open(page)
  await openFinish(page)

  await finishCell(page, 'holo').click()
  await finishCell(page, 'holo').click()

  await expect(finishCell(page, 'holo')).toHaveAttribute(
    'aria-pressed',
    'false',
  )
  /* Toggling the last member off IS the clear — there is no "no claim" cell to return to
     (owner's ruling, 2026-08-23) and no separate reset to learn. Empty is stored as ABSENT
     rather than as `[]`: an empty claim is no claim (D3), and a stored `[]` would be a
     record of nothing that still has to be read back. */
  expect(
    await page.evaluate(() => window.sessionStorage.getItem('pkmnscan.session.finish')),
  ).toBeNull()

  /* And the collapsed row says so IN WORDS, at full contrast. The removed "no claim" cell
     handed that job to this row; a bitfield would say it only in an aria-label.
     `No claim` rather than `no claim`: `CaptureScreen.tsx:NO_CLAIM_LABEL` is a sentence-case
     label now, which is the same words in the register the rest of the screen was rebuilt in.
     What is asserted is unchanged — the row says it, rather than leaving the row blank. */
  await page.keyboard.press('Escape')
  await expect(finishRow(page)).toContainText('No claim')
})

test('a session written before the claim was a set reads back as ONE member, not as nothing', async ({
  page,
}) => {
  /* D27's key held a BARE STRING until 2026-08-23, so every capture tab open at that moment
     has one under it right now. Without the read-side backfill in `readSessionFinish` the
     first reload after the change starts a run with the claim silently gone — on the screen
     where a lost claim costs a review-queue tap per card for the rest of the stack, and with
     nothing on screen saying anything was dropped.

     The value is UNQUOTED, which is what the old writer wrote: `JSON.parse` throws on it,
     and the salvage has to be in the `catch` rather than only in the array branch. */
  await open(page, { 'pkmnscan.session.finish': 'reverse_holo' })

  /* The ROW draws the label and the STORE held the member, which is the whole of the
     backfill: the seeded string is `reverse_holo` and the cell it presses below is the one
     labelled `Reverse holo`. Read the two lines together and the salvage is asserted end to
     end — a `catch` that dropped the value would leave the row saying `No claim`. */
  await expect(finishRow(page)).toContainText('Reverse holo')
  await openFinish(page)
  await expect(finishCell(page, 'reverse_holo')).toHaveAttribute(
    'aria-pressed',
    'true',
  )
})

test('narrowing a two-member claim down to one CLEARS it rather than promoting it', async ({
  page,
}) => {
  await open(page)
  await openFinish(page)
  await finishCell(page, 'normal').click()
  await finishCell(page, 'reverse_holo').click()
  await page.keyboard.press('Escape')

  /* `Common` stocks `normal` alone in this registry, so claiming it excludes `reverse_holo`
     and would leave the survivor `{normal}` — a ONE-MEMBER claim, which DETERMINES: it
     outranks the catalog at rung 2 and is what detection is cross-checked against at rung 3.
     The operator said "this stack is normals and reverse holos"; nothing here is entitled to
     turn that into "the operator said normal". D23 refuses auto-selection in words for this
     exact reason, and keeping a manufactured survivor is auto-selection by the back door. */
  await page.keyboard.press('r')
  /* BY NAME ALONE, because the keycap left the accessible name: `kit/Kbd` renders
     `aria-hidden`, so the option that read as `1 Common` to a screen reader now reads as
     `Common`. `exact` is what keeps it off `Uncommon`, which is the row directly under it.
     The key itself is still asserted — off `.capture-k`, by the option-alphabet cases. */
  await page.getByRole('button', { name: 'Common', exact: true }).click()
  await page.keyboard.press('Escape')

  await expect(finishRow(page)).toContainText('No claim')
  expect(
    await page.evaluate(() => window.sessionStorage.getItem('pkmnscan.session.finish')),
  ).toBeNull()
})

/* ---- THE OPTION ALPHABET (owner's ruling, 2026-08-24) --------------------------------
 *
 * The chips ran `1`-`9` and stopped, so Pokemon's last four rarities — `Special
 * Illustration Rare`, `Hyper Rare`, `Secret Rare`, `Rainbow Rare` — could be claimed only
 * with a mouse, on the screen whose whole keyboard argument is that a claim costs one
 * press. `CaptureScreen.tsx:OPTION_KEYS` carries the replacement: digits, then `0`, then
 * every letter this screen has not already spent.
 *
 * THE THIRD CASE IS THE ONE THAT MATTERS AND IT IS NEGATIVE. A literal `a`-`z` would have
 * put `Rainbow Rare` on `c`, which is the shutter, at a 623 ms feeder cadence — so the
 * alphabet SKIPS the eleven keys this screen has spent. Nothing in the type system says so
 * and nothing in the render says so; a later session widening the string by hand would
 * break it silently, one card at a time, which is why it is asserted rather than argued.
 */

/** One row of the open rarity list, by its rendered name. `.capture-opt-name` is stem plus
 *  a de-emphasised ` Rare` in two spans, which normalises to the whole cell. */
function rarityOpt(page: Page, name: string) {
  return page
    .locator('.capture-opts .capture-opt')
    .filter({ has: page.locator('.capture-opt-name', { hasText: name }) })
}

async function openRarity(page: Page): Promise<void> {
  await page.keyboard.press('r')
  await expect(rarityOpt(page, 'Rainbow Rare')).toBeVisible()
}

test('the tenth rarity rides 0 and the eleventh rides A — past the digits, by key', async ({
  page,
}) => {
  await open(page, undefined, THIRTEEN)
  await openRarity(page)

  /* The chips first, because the operator never computes the alphabet — they read it off
     the row. The DOM text is lower case; `text-transform` in CaptureScreen.css is what
     draws `A`, which is how the owner named this key. */
  await expect(rarityOpt(page, 'Special Illustration Rare').locator('.capture-k')).toHaveText(
    '0',
  )
  await expect(rarityOpt(page, 'Hyper Rare').locator('.capture-k')).toHaveText('a')

  await page.keyboard.press('0')
  await page.keyboard.press('a')

  await expect(rarityOpt(page, 'Special Illustration Rare')).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(rarityOpt(page, 'Hyper Rare')).toHaveAttribute('aria-pressed', 'true')

  /* Stored in the game's stack order (D22), not the order the keys were pressed — the same
     canonicalisation the finish claim above asserts, over a different control. */
  expect(
    await page.evaluate(() => window.sessionStorage.getItem('pkmnscan.session.rarityClaim')),
  ).toBe(JSON.stringify(['Special Illustration Rare', 'Hyper Rare']))
})

test('the alphabet skips the keys this screen has spent: the last two ride D and E, not B and C', async ({
  page,
}) => {
  await open(page, undefined, THIRTEEN)
  await openRarity(page)

  await expect(rarityOpt(page, 'Secret Rare').locator('.capture-k')).toHaveText('d')
  await expect(rarityOpt(page, 'Rainbow Rare').locator('.capture-k')).toHaveText('e')

  await page.keyboard.press('e')
  await expect(rarityOpt(page, 'Rainbow Rare')).toHaveAttribute('aria-pressed', 'true')
})

test('C stays the shutter and B stays the box: an option key never shadows one already spent', async ({
  page,
}) => {
  await open(page, undefined, THIRTEEN)
  await openRarity(page)

  /* `c` with the rarity field open. Under a literal `a`-`z` alphabet this is position 13,
     `Rainbow Rare` — the claim would move and the operator, whose finger is on the shutter
     at feeder pace, would have no way to know which act fired. No box is selected here, so
     the capture itself refuses before it reaches the wire (CaptureScreen: `box === null`);
     what is asserted is that the press did not land on the list. */
  await page.keyboard.press('c')
  await expect(rarityOpt(page, 'Rainbow Rare')).toHaveAttribute('aria-pressed', 'false')
  expect(
    await page.evaluate(() => window.sessionStorage.getItem('pkmnscan.session.rarityClaim')),
  ).toBeNull()

  /* And `b` — position 12 under a literal alphabet — still opens the Box field, which is
     the other half of "every existing key keeps the meaning it had". The field letters are
     tested before the option lookup and are excluded from it, so neither can win a press
     the other wanted. */
  await page.keyboard.press('b')
  await expect(rarityOpt(page, 'Secret Rare')).toHaveCount(0)
  await expect(page.locator('.capture-open').filter({ hasText: /Box/ })).toBeVisible()
})

/* ---- THE DIVIDER ACT (owner, 2026-08-29) ---------------------------------------------
 *
 * "just like C is capture, I want S for Sectioning (remap S for set hint to H)". Two
 * things nothing else in the tree can catch:
 *
 * THE REMAP IS A SWAP, and a swap has two halves that fail independently. `FIELD_KEYS`
 * losing `s` without gaining `h` leaves the set hint mouse-only; gaining `h` without the
 * act taking `s` leaves the letter dead. `tsc` sees a record of strings either way.
 *
 * THE ACT IS THE ONLY CONTROL ON THIS SCREEN THAT WRITES TO A BOX RATHER THAN TO A CARD,
 * so the request it sends is worth pinning: no index in the body, because the store reads
 * `next_index` inside its own lock (D10 amended, `server.ts:openSection`). A client that
 * started sending one would still pass a type check and would still look right on screen.
 *
 * THE STORE IS STILL NEVER TOUCHED, which is this file's own rule. The box list and the
 * section route are both stubbed, and `/capture` is stubbed to FAIL — so if a press ever
 * reached the shutter with a box selected, this spec says so instead of writing a card.
 */

/** One box, as `GET /boxes` renders it. Every field of `BoxRecord`, because `RunPanel`'s
 *  spec records what a short fixture costs: the screen reads `sections_detail` and a record
 *  missing it crashes the render rather than failing an assertion. */
const ONE_BOX = {
  boxes: [
    {
      box: 3,
      name: 'S key',
      sections: [],
      state: 'open',
      capacity: null,
      fill: 40,
      next_index: 41,
      cards: 40,
      sold: 0,
      retired: 0,
      listed: 0,
      sections_detail: [{ section: 1, start: 1, end: 40, count: 40 }],
    },
  ],
}

/** The box row the section route answers with: the same box, now divided at 41. */
const DIVIDED = {
  ...ONE_BOX.boxes[0],
  sections: [1, 41],
  sections_detail: [
    { section: 1, start: 1, end: 40, count: 40 },
    { section: 2, start: 41, end: null, count: 0 },
  ],
}

/** The screen with a box selected and every write stubbed. Returns the bodies the section
 *  route was called with, so a case can assert what went over the wire. */
async function openWithBox(page: Page): Promise<string[]> {
  const bodies: string[] = []
  await page.route(/\/boxes$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(ONE_BOX),
    })
  })
  await page.route(/\/boxes\/\d+\/sections$/, async (route) => {
    bodies.push(route.request().postData() ?? '')
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(DIVIDED),
    })
  })
  /* A tripwire, not a stub: nothing in these cases should ever reach the shutter, and a
     404 with a body the screen would render is how this file finds out if one does. */
  await page.route(/\/capture$/, async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'no capture may happen in this spec' }),
    })
  })
  await open(page)

  await page.keyboard.press('b')
  /* WAIT FOR THE BOX TO BE OFFERED BEFORE TYPING AT IT. Under `fullyParallel` this raced:
     `GET /boxes` had not landed, the field read `0 boxes`, and Enter took `3` as the name of
     a NEW box — a `POST /boxes` no route in this file answers, which is the one request that
     could reach a real store from a spec whose header promises it never does. Waiting on the
     offered row is what makes the press land on the box the fixture describes. */
  await expect(page.locator('.capture-opt').filter({ hasText: /S key/ })).toBeVisible()
  await page.keyboard.type('3')
  await page.keyboard.press('Enter')
  await expect(page.locator('.capture-row').filter({ hasText: /Box/ })).toContainText('3')
  return bodies
}

function sectionButton(page: Page) {
  return page.locator('.capture-section button')
}

test('S is the divider and H is the set hint: the remap, both halves', async ({ page }) => {
  await open(page)

  /* `s` no longer opens a field. Asserted as an ABSENCE of the set hint's open state rather
     than as the presence of something else, because that is the half a partial remap
     breaks: `FIELD_KEYS` still carrying `s` would open this and nothing would say so. */
  await page.keyboard.press('s')
  await expect(page.locator('.capture-open').filter({ hasText: /Set hint/ })).toHaveCount(0)

  await page.keyboard.press('h')
  await expect(page.locator('.capture-open').filter({ hasText: /Set hint/ })).toBeVisible()

  /* And the chip says so. The operator never computes a key — they read it off the row, the
     same rule the option alphabet above is asserted by. */
  await expect(page.locator('.capture-open').locator('.capture-k').first()).toHaveText('H')
  await page.keyboard.press('Escape')
  /* The keycap is the kit `Button`'s own `kbd` now rather than a hand-rolled `.capture-key`
     span, so the assertion follows the control to the element that carries the letter. The
     claim is unchanged and is still the one that matters: the divider act ADVERTISES `S`, so
     the operator reads the key off the button instead of computing it. */
  await expect(sectionButton(page).locator('kbd')).toHaveText('S')
})

test('with no box the divider is disabled — not absent, and it writes nothing', async ({
  page,
}) => {
  await open(page)

  /* docs/DESIGN.md's absent-not-disabled rule is about the control that COMMITS to
     something irreversible; this one is free and reversible, and a control that vanished
     until a box was picked would read as a missing feature on the screen the owner cannot
     afford to hunt on. So: present, named, disabled. */
  await expect(sectionButton(page)).toBeVisible()
  await expect(sectionButton(page)).toBeDisabled()

  await page.keyboard.press('s')
  await expect(page.locator('.capture-section p')).toHaveCount(0)
})

test('S puts a divider in front of the next card, and sends no index', async ({ page }) => {
  const bodies = await openWithBox(page)
  await expect(sectionButton(page)).toBeEnabled()

  await page.keyboard.press('s')

  /* The receipt names the section the SERVER rendered and the card it starts at — read off
     `sections_detail`, never off `sections.length`, which is the section arithmetic D10
     keeps out of the app. */
  await expect(page.locator('.capture-section p')).toContainText('New section')
  await expect(page.locator('.capture-section .capture-inline-label')).toHaveText(
    'Section 2 · from card 41',
  )

  /* THE BODY IS EMPTY, and that is the contract rather than a detail. The divider goes
     where the store's own high-water mark says the next card lands; an index on the wire
     would be one read across a round trip, which at a 623 ms feeder cadence is a real race
     (`server.ts:openSection`). `{}` and not nothing: every write in the capture server
     refuses an absent body as `body_required`. */
  expect(bodies).toEqual(['{}'])
})

test('a refused divider is a sentence beside the control, and never a halt', async ({
  page,
}) => {
  await openWithBox(page)
  await page.route(/\/boxes\/\d+\/sections$/, async (route) => {
    await route.fulfill({
      status: 409,
      contentType: 'application/json',
      /* The server's own envelope — `_fail` writes `{"error": {"code", "message"}}` and
         `server.ts:describeFailure` reads exactly that. A flatter fixture reaches the
         screen as a bare "409 Conflict ... http_error", which is what this spec caught the
         first time it ran and is precisely the sentence the operator must never get. */
      body: JSON.stringify({
        error: {
          code: 'section_empty',
          message: 'section 2 of box 3 already starts at card 41 and holds nothing yet.',
        },
      }),
    })
  })

  await page.keyboard.press('s')

  /* The server's own sentence, verbatim, beside the button — docs/DESIGN.md's copy rule for
     the owner's screens, and the shape the undo refusal already takes. The machine string
     rides with it so what was seen on screen is greppable. */
  await expect(page.locator('.capture-section .capture-refused')).toContainText(
    'already starts at card 41',
  )
  await expect(page.locator('.capture-section .capture-halt-code')).toHaveText('section_empty')

  /* AND THE RUN IS NOT HALTED. Spec 5.5 stops the run when a card may have gone past
     unrecorded; a refused divider changed nothing at all. The halt banner is the thing that
     must not be here. */
  await expect(page.locator('.capture-halt')).toHaveCount(0)
})

// ------------------------------------ the hint offers a real vocabulary (D65)

async function routeSets(page: Page, body: unknown) {
  await page.route(/\/tcg\/sets/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    })
  })
}

test('the set hint offers the real set names, and still takes free text', async ({ page }) => {
  await routeSets(page, {
    game: 'pokemon',
    sets: [{ name: 'SV09: Journey Together', id: '4242' }],
    aliases: { JTG: 'SV09' },
    reason: null,
  })
  await open(page)
  await page.keyboard.press('h')

  const hint = page.getByLabel('Set hint')
  await expect(hint).toBeVisible()

  /* A DATALIST AND NOT A SELECT, which is what makes this safe on the rig's own screen: it
     suggests without constraining. The alias is offered beside the name because the operator
     types `JTG` and TCGplayer publishes `SV09: Journey Together` — two vocabularies for one
     set, which is the whole reason the hint needed a list. */
  await expect(hint).toHaveAttribute('list', 'capture-set-names')
  await expect(page.locator('#capture-set-names option[value="SV09: Journey Together"]')).toHaveCount(1)
  await expect(page.locator('#capture-set-names option[value="JTG"]')).toHaveCount(1)

  await hint.fill('something nobody listed')
  await expect(hint).toHaveValue('something nobody listed')
})

test('a set vocabulary that could not be fetched leaves the hint field working', async ({
  page,
}) => {
  await routeSets(page, { game: 'pokemon', sets: [], aliases: {}, reason: 'tcg_cookie_missing' })
  await open(page)
  await page.keyboard.press('h')

  /* THE RIG DOES NOT STOP FOR AN AUTOCOMPLETE. No cookie, no network, the portal down — the
     control is the plain text input it was before D65 and a capture is unaffected. Asserted
     as the ABSENCE of options plus a working input, because the failure worth forbidding is
     a field that will not open. */
  const hint = page.getByLabel('Set hint')
  await expect(hint).toBeVisible()
  await expect(page.locator('#capture-set-names option')).toHaveCount(0)
  await hint.fill('sv09')
  await expect(hint).toHaveValue('sv09')
})

test('an expired session says so where the suggestions would have been', async ({ page }) => {
  await routeSets(page, {
    game: 'pokemon',
    sets: [],
    aliases: {},
    reason: 'tcg_session_expired',
  })
  await open(page)
  await page.keyboard.press('h')

  /* DEGRADING TO EMPTY IS CORRECT; DEGRADING INVISIBLY IS NOT. An expired session and a game
     with no sets produce the identical empty list, and the operator has no way to tell them
     apart from silence — so the reason is drawn where the suggestions would have been. It
     names the file to fix, because that is the one case they can act on. */
  /* REPOINTED, AND ONE CLAIM IS GENUINELY GONE. The reason is still drawn where the
     suggestions would have been and still names THIS cause rather than emptiness, which is
     the behaviour. What it no longer does is name `.env`: `CaptureScreen.tsx:hintReason`
     draws sentences and argues the file is a fact for whoever sets the rig up rather than for
     the operator at the lens, and the owner ruled for sentences over machine strings
     (2026-09-03). That is a deliberate product change, so the assertion over it is dropped
     rather than re-pointed at a string nothing prints. */
  await expect(page.locator('.capture-open')).toContainText('TCGplayer session has expired')

  /* And it is still only a note: the field takes text exactly as before. */
  const hint = page.getByLabel('Set hint')
  await hint.fill('sv09')
  await expect(hint).toHaveValue('sv09')
})

// ------------------------------- the vocabulary is drawn as a RULE, not only offered (D65)

/* THE FIELD ALWAYS HAD RULES AND DREW NONE OF THEM. A `datalist` offers the real set names
   and says nothing at all about the string typed, so `Spiritforge` and `Spiritforged` look
   identical at the rig and part company an hour of captures later at the fetch: one scopes
   the export to that set, the other resolves to nothing and widens to the whole category.
   These cases are that verdict, in the two registers the box field beside it already uses —
   a terse meta pinned to the entry, and a sentence under the field.

   EVERY ONE OF THEM ALSO ASSERTS THAT NOTHING IS REFUSED. That is not politeness about
   coverage: D65's rule is that the rig does not stop for an autocomplete, and a verdict that
   grew teeth would break it. So each case types its string and reads it back. */

const RIFTBOUND_SETS = {
  game: 'riftbound',
  sets: [
    { name: 'Origins', id: '24000' },
    { name: 'Origins: Proving Grounds', id: '24001' },
    { name: 'Spiritforged', id: '24020' },
    /* A TWO-WORD SET, so the abbreviation rule is exercised across a space and not only
       inside one word — `SEC` is Secret Garden the same way `SFD` is Spiritforged. */
    { name: 'Secret Garden', id: '24040' },
  ],
  aliases: { OGN: 'Origins' },
  reason: null,
}

/** The live state pinned to the right of the entry — the box field's `next 60` / `new box`,
 *  one field over. */
function hintMeta(page: Page) {
  return page.locator('.capture-open .capture-entrymeta')
}

/** The sentence under the field: what that state MEANS. */
function hintNote(page: Page) {
  return page.locator('.capture-open .capture-opennote')
}

test('a hint that names no set says so, and the capture screen still takes it', async ({
  page,
}) => {
  await routeSets(page, RIFTBOUND_SETS)
  await open(page)
  await page.keyboard.press('h')

  const hint = page.getByLabel('Set hint')
  await hint.fill('Spiritfoged')

  /* THE TYPO THIS EXISTS FOR, and it is a DROPPED MIDDLE LETTER rather than a truncation on
     purpose: `Spiritforge` is a unique PREFIX of `Spiritforged` and resolves, which is the
     completion case below. This one resolves to nothing, and before the verdict the two were
     indistinguishable until the export came back wide. */
  await expect(hintMeta(page)).toHaveText(/names no set/i)
  await expect(hintNote(page)).toContainText('No set of')
  await expect(hintNote(page)).toContainText('widens to the whole game')

  /* NOT A REFUSAL. The string is still what the field holds, and the note says what will
     happen to it rather than asking for a different one. */
  await expect(hint).toHaveValue('Spiritfoged')

  /* And it is visible from the ROW, so a stack captured against a typo does not need the
     field opened to be found. */
  await page.keyboard.press('Escape')
  const row = page.locator('.capture-row').filter({ hasText: /Set hint/ })
  await expect(row).toContainText('Spiritfoged')
  await expect(row.locator('.capture-sub')).toHaveText(/names no set/i)
})

test('a hint that names a set says that instead, and says nothing at rest', async ({ page }) => {
  await routeSets(page, RIFTBOUND_SETS)
  await open(page)
  await page.keyboard.press('h')

  const hint = page.getByLabel('Set hint')
  await hint.fill('spiritforged')

  /* FOLDED, because `match_sets` folds: the operator types what is on the divider and the
     case it is written in is not a claim about anything. */
  await expect(hintMeta(page)).toHaveText(/names a set/i)
  await expect(hintNote(page)).toContainText('Spiritforged')

  /* The ordinary case is drawn as the ordinary case — the row carries the value and no
     annotation, so the mark on a bad hint means something. */
  await page.keyboard.press('Escape')
  const row = page.locator('.capture-row').filter({ hasText: /Set hint/ })
  await expect(row).toContainText('spiritforged')
  await expect(row.locator('.capture-sub')).toHaveCount(0)
})

test('a three-letter set code names its set, and the typo one letter away still does not', async ({
  page,
}) => {
  await routeSets(page, RIFTBOUND_SETS)
  await open(page)
  await page.keyboard.press('h')

  const hint = page.getByLabel('Set hint')

  /* `SFD` IS SPIRITFORGED AND NOTHING IN THE STRING SAYS SO. It is not a prefix, not a colon
     code, and had no row in `pipeline/games.py:set_aliases` — before the abbreviation rule it
     resolved to nothing and silently widened the export to all of Riftbound. The rule is the
     hint's own letters, in order, through the set's name. */
  await hint.fill('SFD')
  await expect(hintMeta(page)).toHaveText(/enter completes/i)
  await expect(hintNote(page)).toContainText('Spiritforged')

  /* THE CAP IS WHAT KEEPS THIS OFF MISSPELLED NAMES, and it is the half worth asserting:
     uncapped, the same subsequence rule reads `Spiritfoged` as Spiritforged too, and then
     almost every string "names a set" and the warning above never fires again. Eleven
     characters is a name that is wrong, not a code. */
  await hint.fill('Spiritfoged')
  await expect(hintMeta(page)).toHaveText(/names no set/i)

  /* And a code answering to two sets resolves to neither, the same as any other tie. */
  await hint.fill('SEC')
  await expect(hintMeta(page)).toHaveText(/enter completes/i)
  await expect(hintNote(page)).toContainText('Secret Garden')
})

test('Enter completes a hint that resolved to one set but is not its name', async ({ page }) => {
  await routeSets(page, RIFTBOUND_SETS)
  await open(page)
  await page.keyboard.press('h')

  const hint = page.getByLabel('Set hint')
  await hint.fill('Spirit')

  /* A UNIQUE PREFIX RESOLVES THE EXPORT AND IS STILL NOT THE SET'S NAME, which is the form
     `pipeline/join.py:set_matches` needs at join time — one fold, no shape rules. So the
     keystroke that leaves the field is the one that makes the stored string exact. */
  await expect(hintMeta(page)).toHaveText(/enter completes/i)
  await hint.press('Enter')

  const row = page.locator('.capture-row').filter({ hasText: /Set hint/ })
  await expect(row).toContainText('Spiritforged')
})

test('an ambiguous hint names the sets it could be, and resolves to none of them', async ({
  page,
}) => {
  await routeSets(page, RIFTBOUND_SETS)
  await open(page)
  await page.keyboard.press('h')

  const hint = page.getByLabel('Set hint')

  /* `Origins` AND `Origins: Proving Grounds` ARE THE REAL SHAPE, and the hint that cannot
     choose between them is one letter short of both — `Origins` itself is a set's own name
     and resolves outright on rule one. A prefix answering to two sets answers to neither, so
     `match_sets` calls it a MISS and widens. The screen says which two it is between, because
     that is the fact that lets the operator choose; `match_sets` cannot. */
  await hint.fill('Origin')
  await expect(hintMeta(page)).toHaveText(/2 sets/i)
  await expect(hintNote(page)).toContainText('Origins: Proving Grounds')
  await expect(hintNote(page)).toContainText('widens to all of')

  /* Enter does not complete what did not resolve. */
  await hint.press('Enter')
  const row = page.locator('.capture-row').filter({ hasText: /Set hint/ })
  await expect(row).toContainText('Origin')
  await expect(row.locator('.capture-sub')).toHaveText(/names no set/i)
})

test('a hint is never accused while there is no list to check it against', async ({ page }) => {
  await routeSets(page, { game: 'pokemon', sets: [], aliases: {}, reason: 'tcg_cookie_missing' })
  await open(page, { 'pkmnscan.session.setHint': 'Spiritfoged' })

  /* THE VERDICT IS `unchecked`, WHICH IS NOT `unmatched`. No cookie, no network, the portal
     down — this screen cannot tell, and D65's whole rule is that it degrades to the control
     it was before rather than to an accusation. The row carries the hint and no mark. */
  const row = page.locator('.capture-row').filter({ hasText: /Set hint/ })
  await expect(row).toContainText('Spiritfoged')
  await expect(row.locator('.capture-sub')).toHaveCount(0)

  await page.keyboard.press('h')
  await expect(hintMeta(page)).toHaveText(/not checked/i)
  await expect(hintNote(page)).toContainText('stored exactly as typed')
})
