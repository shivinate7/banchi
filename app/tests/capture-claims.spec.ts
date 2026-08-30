import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

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

  await page.goto('/#/')
  await expect(finishRow(page)).toBeVisible()
}

/** The Finish row, open or collapsed. `capture-trackline` is the open track's wrapper, so
 *  this matches the row by its label either way. */
function finishRow(page: Page) {
  return page.locator('.capture-row, .capture-open').filter({ hasText: /Finish/ }).first()
}

function finishCells(page: Page) {
  return page.locator('.capture-track[aria-label="Finish"] .capture-cell')
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
  await finishCells(page).filter({ hasText: /^normal$/ }).click()
  await finishCells(page).filter({ hasText: 'reverse_holo' }).click()

  await expect(finishCells(page).filter({ hasText: /^normal$/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await expect(finishCells(page).filter({ hasText: 'reverse_holo' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  /* And an unclaimed member is not pressed — a multi-select, not a track that latches on. */
  await expect(finishCells(page).filter({ hasText: /^holo$/ })).toHaveAttribute(
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
  await finishCells(page).filter({ hasText: 'reverse_holo' }).click()
  await finishCells(page).filter({ hasText: /^normal$/ }).click()

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

  await finishCells(page).filter({ hasText: /^holo$/ }).click()
  await finishCells(page).filter({ hasText: /^holo$/ }).click()

  await expect(finishCells(page).filter({ hasText: /^holo$/ })).toHaveAttribute(
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
     handed that job to this row; a bitfield would say it only in an aria-label. */
  await page.keyboard.press('Escape')
  await expect(finishRow(page)).toContainText('no claim')
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

  await expect(finishRow(page)).toContainText('reverse_holo')
  await openFinish(page)
  await expect(finishCells(page).filter({ hasText: 'reverse_holo' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
})

test('narrowing a two-member claim down to one CLEARS it rather than promoting it', async ({
  page,
}) => {
  await open(page)
  await openFinish(page)
  await finishCells(page).filter({ hasText: /^normal$/ }).click()
  await finishCells(page).filter({ hasText: 'reverse_holo' }).click()
  await page.keyboard.press('Escape')

  /* `Common` stocks `normal` alone in this registry, so claiming it excludes `reverse_holo`
     and would leave the survivor `{normal}` — a ONE-MEMBER claim, which DETERMINES: it
     outranks the catalog at rung 2 and is what detection is cross-checked against at rung 3.
     The operator said "this stack is normals and reverse holos"; nothing here is entitled to
     turn that into "the operator said normal". D23 refuses auto-selection in words for this
     exact reason, and keeping a manufactured survivor is auto-selection by the back door. */
  await page.keyboard.press('r')
  await page.getByRole('button', { name: '1 Common' }).click()
  await page.keyboard.press('Escape')

  await expect(finishRow(page)).toContainText('no claim')
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
  await expect(sectionButton(page).locator('.capture-key')).toHaveText('S')
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
