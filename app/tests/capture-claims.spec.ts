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

async function open(page: Page, session?: Record<string, string>): Promise<void> {
  await page.route(/\/games$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(GAMES),
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
