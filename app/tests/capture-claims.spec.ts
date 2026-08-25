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
 * ONLY READS ARE STUBBED, AND NO CAPTURE IS EVER TAKEN. `GET /games` is intercepted so the
 * vocabulary is fixed rather than whatever `pipeline/games.py` authors today, and no box is
 * ever selected — the same rule `motion-live.spec.ts` states for the same reason: with a box
 * a capture would POST into a real store. Every assertion here is about what the control
 * HOLDS, which is what decides what the wire would carry.
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
