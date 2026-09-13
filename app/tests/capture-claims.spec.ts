import { expect, test } from '@playwright/test'
import { sealEveryTest } from './shell'
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

/** The settings the capture screen now remembers on the DEVICE (D142), as `deviceMemory.ts`
 *  stores them — seven since `bid` joined them (D145). Partial, because a case seeds the one
 *  field it is about and the reader fills the rest from `NO_CAPTURE_SETUP`. */
type SeedSetup = {
  box?: number | null
  /** WHICH DRAWER that box number was, at the moment it was picked. Seeded apart from `box` on
   *  purpose: the cases worth having are the ones where the two disagree, and a browser that
   *  predates the field carries a box and no id at all — which is what seeding `box` alone
   *  reproduces exactly. */
  bid?: number | null
  game?: string | null
  setHint?: string
  finish?: readonly string[]
  rarityClaim?: readonly string[]
  product?: string | null
}

/** What `banchi.capture.setup` holds right now, parsed. `null` where the key is absent —
 *  which is what a clear leaves and what a browser that has never been here has. */
async function storedSetup(page: Page): Promise<Record<string, unknown> | null> {
  return page.evaluate(() => {
    /* eslint-disable-next-line no-restricted-syntax -- READING THE VERY KEY UNDER TEST.
       `banchi.capture.setup` lives in `app/src/deviceMemory.ts` where the argument for it is
       (D142); a spec that asserts what the screen stored has to open the
       store. `inventory.spec.ts` carries the same disable over `banchi.box-recency` for the
       same reason, and the rule's own message asks for exactly this rather than a file
       exemption — a waiver over everything this file will ever store. */
    const raw = window.localStorage.getItem('banchi.capture.setup')
    return raw === null ? null : (JSON.parse(raw) as Record<string, unknown>)
  })
}

async function open(
  page: Page,
  setup?: SeedSetup,
  games: unknown = GAMES,
  boxes: unknown = { boxes: [] },
  /** THE KEY PROBE, WHICH ONE STATE OF THIS SCREEN CANNOT ANSWER. See the probe itself below
   *  for why it exists. It presses `F`, and `F` reaches the key handler only while focus is
   *  NOT in a text field — `isEditableTarget` swallows letters typed into one, correctly and
   *  deliberately, or naming a set would photograph five cards.
   *
   *  D142's restored-box check opens the Box field with focus in its entry, which is exactly
   *  that state, so the probe presses `F` into a search box forever and times out. The two
   *  cases about that check press no keys at all, so the probe is buying them nothing: it is
   *  insurance for a case whose first act is a letter. `probe: false` is for those, and for
   *  nothing else — a case that presses a key and skips this is reintroducing the lost-press
   *  flake the probe was measured against. */
  opts: { probe?: boolean } = {},
): Promise<void> {
  await page.route(/\/games$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(games),
    })
  })
  /* THE TWO READS THE CAPTURE SCREEN MAKES ON MOUNT BESIDE THE REGISTRY, WHICH THIS HELPER
     NEVER STUBBED. `CaptureScreen.tsx`'s box-field effect fires on mount rather than when the
     field opens — its guard is `openField !== null && openField !== 'box'` and `openField`
     starts null — so `GET /boxes` went to the capture port from every case using this helper,
     nineteen of them. `openWithBox` below stubs it and the cases that used that helper were
     the only ones covered. `GET /tcg/sets` is deliberately NOT stubbed here beside
     it: `routeSets` is called by its cases BEFORE this helper, and Playwright takes the newest
     handler — so a stub here would shadow every one of their fixtures rather than back them up.

     EMPTY IS THE ANSWER THIS ONE WANTS. These cases are about the claim tracks and the keys
     that reach them; a box is what `openWithBox` is for.

     THE `/status` STUB THAT SAT HERE IS GONE, and it is `sealEveryTest`'s now. It answered
     `{cards: 0, next_index: {}}` — two of the eight keys `ServerStatus` carries — which is the
     shape `nav.spec.ts` records taking the whole shell down when `Sidebar` reads
     `status.cards` off a short payload. It survived here only because this screen renders no
     sidebar. */
  await page.route(/\/boxes$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(boxes) })
  })

  /* Seeded BEFORE the app script runs, because `storedCaptureSetup` is the `useState`
     initialiser — it reads once, on the first render, and a value written afterwards would
     never be seen.

     `localStorage` SINCE 2026-09-11 (D142). These six were seven
     `sessionStorage` keys under D27; the owner overruled the session scope for the SETTINGS,
     and `banchi.session.captureId` is the one key left on the old clock. Seeding a whole
     document rather than a key per field is what the app now writes, so a case that seeds one
     field is seeding the same shape the screen reads. */
  if (setup !== undefined) {
    await page.addInitScript((seed: SeedSetup) => {
      /* eslint-disable-next-line no-restricted-syntax -- SEEDING THE VERY KEY UNDER TEST; see
         `storedSetup` above for the argument. */
      window.localStorage.setItem(
        'banchi.capture.setup',
        JSON.stringify({
          box: null,
          bid: null,
          game: null,
          setHint: '',
          finish: [],
          rarityClaim: [],
          product: null,
          ...seed,
        }),
      )
    }, setup)
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
  if (opts.probe === false) return
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
 * `banchi.session.finish` back and name it, and the legacy-session case seeds the MEMBER
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

/* NOTHING HERE MAY REACH THE CAPTURE SERVER — `app/tests/shell.ts` carries the argument. This
   file already stubbed the shell's own `/status` by hand; the shared call replaces it so there
   is one spelling of the rule, and adds what a hand-written stub could not: a catch-all that
   REFUSES and names anything else that gets out. The call has to sit above the file's first
   `test.beforeEach`, which is what `make docs-audit`'s `spec seal` row checks. */
sealEveryTest()

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

  expect((await storedSetup(page))?.finish).toEqual(['normal', 'reverse_holo'])
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
     (owner's ruling, 2026-08-23) and no separate reset to learn. Empty is now stored as `[]`
     rather than as an absent key, and that is a consequence of the move to one document
     (D142): the old per-key store had to spell "cleared" as "absent" so a
     cleared field and an unwritten one read alike, and a document that is present or absent
     as a whole has nothing left for that trick to buy. What the wire carries is unchanged —
     an empty claim is still NO claim (D3), and the screen omits the key from the capture. */
  expect((await storedSetup(page))?.finish).toEqual([])

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
  await open(page, { finish: ['reverse_holo'] })

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
  expect((await storedSetup(page))?.finish).toEqual([])
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
  expect((await storedSetup(page))?.rarityClaim).toEqual([
    'Special Illustration Rare',
    'Hyper Rare',
  ])
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
  expect((await storedSetup(page))?.rarityClaim).toEqual([])

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
      bid: 3,
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
  /* THE BOX FIXTURE IS HANDED TO `open` RATHER THAN REGISTERED AHEAD OF IT. `open` stubs
     `GET /boxes` now — the capture screen reads it on mount and nineteen cases were sending
     that read to the capture port — and Playwright takes the NEWEST handler, so a second one
     here would be shadowed by the one registered later inside `open`. One parameter, one
     handler, and the case that wants a box says which. */
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
  await open(page, undefined, GAMES, ONE_BOX)

  await page.keyboard.press('b')
  /* WAIT FOR THE BOX TO BE OFFERED BEFORE TYPING AT IT. Under `fullyParallel` this raced:
     `GET /boxes` had not landed, the field read `0 boxes`, and Enter took `3` as the name of
     a NEW box — a `POST /boxes` no route in this file answers, which is the one request that
     could reach a real store from a spec whose header promises it never does. Waiting on the
     offered row is what makes the press land on the box the fixture describes. */
  await expect(page.locator('.capture-opt').filter({ hasText: /S key/ })).toBeVisible()
  await page.keyboard.type('3')
  await page.keyboard.press('Enter')
  /* THE ROW NAMES THE BOX AND NO LONGER NUMBERS IT (D142), so this asserts
     the NAME the fixture gives box 3. It read `toContainText('3')` against a row that opened
     `Box 3`; the owner's instruction was that the number comes off this screen, and the name
     is the stronger assertion anyway — `3` also matches a `next index 3`. */
  await expect(page.locator('.capture-row').filter({ hasText: /Box/ })).toContainText('S key')
  return bodies
}

function sectionButton(page: Page) {
  return page.locator('.capture-section button')
}

test('S is the divider and H is the set hint: the remap, both halves', async ({ page }) => {
  /* THE SET VOCABULARY, BECAUSE THIS CASE OPENS THE FIELD THAT FETCHES IT. Pressing `h` is
     what `CaptureScreen.tsx:loadSets` is gated on, so this case — which is about the KEYS and
     not about the list — was asking the capture port for the real set names. Named by
     `sealEveryTest`; empty is the answer, because nothing below reads a row. */
  await routeSets(page, { game: 'pokemon', sets: [], aliases: {}, reason: null })
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
  await open(page, { setHint: 'Spiritfoged' })

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

/* ---- THE SETUP THIS BROWSER REMEMBERS (D142) ------------------------
 *
 * THREE THINGS THE OWNER ASKED FOR ON 2026-09-11, and each fails in a way nothing else here
 * would catch. The setup outliving the browser is a STORE change, so it is asserted against
 * the store rather than against the screen alone. The box order is a SORT, so it is asserted
 * against a fixture whose fullness and recency disagree — a fixture where they agree would
 * pass under either rule and prove nothing. And the clear is a WRITE, so what it leaves
 * behind is read back.
 *
 * `banchi.session.captureId` IS THE ONE KEY THAT DID NOT MOVE, and the case for it is here
 * rather than in a comment: a stale in-flight id restored into a new shift asks the operator
 * to re-feed a card that was recorded hours ago, and D10's high-water mark then burns a
 * position. That is the carve-out D27 exists for and it has never had a test.
 */

/** Four boxes whose FULLNESS and NUMBER disagree, which is what makes the order falsifiable:
 *  sorted by number it is 1,2,3,4; by cards held it is 4,1,3,2. A fixture with the two in
 *  step would pass under the rule this replaced. */
const HAND_BOXES = {
  boxes: [
    { box: 1, bid: 21, name: 'Bulk', sections: [], state: 'open', capacity: null, fill: 10, next_index: 11,
      cards: 10, sold: 0, retired: 0, moved: 0, listed: 0, on_hand: 10,
      sections_detail: [{ section: 1, start: 1, end: 10, count: 10 }] },
    { box: 2, bid: 22, name: 'Slabs', sections: [], state: 'open', capacity: null, fill: 3, next_index: 4,
      cards: 3, sold: 0, retired: 0, moved: 0, listed: 0, on_hand: 3,
      sections_detail: [{ section: 1, start: 1, end: 3, count: 3 }] },
    { box: 3, bid: 23, name: 'Epics', sections: [], state: 'open', capacity: null, fill: 7, next_index: 8,
      cards: 7, sold: 0, retired: 0, moved: 0, listed: 0, on_hand: 7,
      sections_detail: [{ section: 1, start: 1, end: 7, count: 7 }] },
    { box: 4, bid: 24, name: 'Commons', sections: [], state: 'open', capacity: null, fill: 40, next_index: 41,
      cards: 40, sold: 0, retired: 0, moved: 0, listed: 0, on_hand: 40,
      sections_detail: [{ section: 1, start: 1, end: 40, count: 40 }] },
  ],
}

/* THE IDS ABOVE ARE DELIBERATELY NOT THE NUMBERS (D145). A fixture where box 2 carries id 2
   passes a comparison of the two even when the code compares the wrong pair, which is the one
   thing these cases exist to catch. 21-24 also keeps every id two digits, so a case that
   searches the picker for `2` gets a stable answer off the NUMBERS alone. */

/** The same four with box 2 SEALED, for the restore that has to fail softly. */
const HAND_BOXES_SEALED_2 = {
  boxes: HAND_BOXES.boxes.map((row) => (row.box === 2 ? { ...row, state: 'closed' } : row)),
}

/** The box rows as drawn, in order, each collapsed to one line. */
function boxOptionText(page: Page): Promise<string[]> {
  return page.locator('.capture-opt').evaluateAll((nodes) =>
    nodes.map((node) => (node as HTMLElement).innerText.replace(/\s+/g, ' ').trim()),
  )
}

test('the box list leads with the fullest box, and the number is last', async ({ page }) => {
  await open(page, undefined, GAMES, HAND_BOXES)
  await page.keyboard.press('b')
  await expect(page.locator('.capture-opt').first()).toBeVisible()

  /* NOTHING HAS BEEN REACHED FOR YET, so recency is silent everywhere and the second term
     decides: 40, 10, 7, 3. Sorted by NUMBER — which is what this field did until
     2026-09-11 — `Commons` would be LAST rather than first, so this assertion is the one
     the old rule fails. */
  /* AND NOT ONE OF THEM DRAWS ITS NUMBER (D145). Nothing is typed, so no row is an answer to
     a typed number and the number is doing no job on any of them — which is the owner's
     instruction, *"i shouldn't even need to see box. numbers here"*, asserted at rest. */
  expect(await boxOptionText(page)).toEqual([
    'Commons next index 41',
    'Bulk next index 11',
    'Epics next index 8',
    'Slabs next index 4',
  ])
})

test('the box picked last time leads, even when it is the emptiest', async ({ page }) => {
  await open(page, undefined, GAMES, HAND_BOXES)
  await page.keyboard.press('b')
  await expect(page.locator('.capture-opt').first()).toBeVisible()

  /* `Slabs` HOLDS THREE CARDS AND IS LAST ON FULLNESS. Picking it is what the owner means by
     "most recently selected", and the whole point of the rule is that the hand outranks the
     count — so this is the assertion that separates the two terms rather than testing them
     together. */
  await page.getByRole('button', { name: /^Slabs/ }).click()
  await expect(page.locator('.capture-row').filter({ hasText: /Box/ })).toContainText('Slabs')

  /* THE SAME STORE `#/inventory`'s RAIL SORTS ON, which is the shared-fact ruling: one
     operator, one hand, one record of which drawer it is in. A capture-only recency store
     would pass every assertion above and leave the two screens disagreeing. */
  const recency = await page.evaluate(() =>
    /* eslint-disable-next-line no-restricted-syntax -- READING `banchi.box-recency` to prove
       the two screens share ONE store, which is the ruling this case exists for. The key is
       `deviceMemory.ts`'s and `inventory.spec.ts` reads it back the same way. */
    JSON.parse(window.localStorage.getItem('banchi.box-recency') ?? '{}'),
  )
  expect(Object.keys(recency)).toEqual(['2'])

  await page.keyboard.press('b')
  await expect(page.locator('.capture-opt').first()).toBeVisible()
  expect((await boxOptionText(page))[0]).toBe('Slabs next index 4')
})

test('the setup survives a reload, and the in-flight capture id is not on the device', async ({
  page,
}) => {
  /* THE HINT FIELD FETCHES ITS VOCABULARY THE MOMENT IT OPENS (D65), and `open` deliberately
     does not stub `/tcg/sets` — see its own comment, which keeps that fixture with the cases
     that own it. Without this the press below reaches the capture port, which `sealEveryTest`
     catches in `afterEach` and which in the main checkout is the owner's real store. */
  await routeSets(page, { game: 'pokemon', sets: [], aliases: {}, reason: null })
  await open(page, undefined, GAMES, HAND_BOXES)

  /* A BOX AND A HINT, SET THE WAY THE OPERATOR SETS THEM — pressed, not seeded. A seeded value
     that came back would only prove the reader reads; what is under test is that a LIVE edit
     is written, so the write and the read are both exercised. */
  await page.keyboard.press('b')
  await page.getByRole('button', { name: /^Epics/ }).click()
  await page.keyboard.press('h')
  await page.getByLabel('Set hint').fill('MEG')
  await page.getByLabel('Set hint').press('Enter')

  /* A RELOAD IS WHAT THIS CAN TEST DIRECTLY, and it is a real one: the whole screen is torn
     down and every value comes back through `storedCaptureSetup` on a fresh mount. It is
     WEAKER than the owner's own test (close the tab, open a new one) only in that a tab is
     what `sessionStorage` dies with — and that is exactly why the second half below is
     asserted about the STORE rather than about survival. */
  await page.reload()
  await expect(finishRow(page)).toBeVisible()

  await expect(page.locator('.capture-row').filter({ hasText: /Box/ })).toContainText('Epics')
  await expect(page.locator('.capture-row').filter({ hasText: /Set hint/ })).toContainText('MEG')
  expect(await storedSetup(page)).toMatchObject({ box: 3, setHint: 'MEG' })

  /* AND `captureId` IS NOWHERE ON THE DEVICE, which is the half a reload cannot show by
     survival — `sessionStorage` survives a reload too, so planting one and finding it again
     would prove nothing at all. What IS falsifiable is the store it lives in: if a later
     session folded it in with the other six "for consistency", it would appear either as a
     field of this document or as a `localStorage` key of its own, and both are checked.
     That is the whole of D27's surviving carve-out, stated as a property rather than as a
     comment. */
  expect(Object.keys((await storedSetup(page)) ?? {})).not.toContain('captureId')
  /* eslint-disable-next-line no-restricted-syntax -- ENUMERATING the device store to prove a
     key is absent from it; see `storedSetup` above for the argument. */
  const deviceKeys = await page.evaluate(() => Object.keys(window.localStorage))
  expect(deviceKeys.filter((key) => key.toLowerCase().includes('capture'))).toEqual([
    'banchi.capture.setup',
  ])
})

test('a restored box that has been sealed since is let go of, by name', async ({ page }) => {
  /* SEEDED AS BOX 2, WHICH THE FIXTURE HAS SEALED. Between two sittings a box can be sealed,
     deleted, or deleted and its number reused by `next_box_number`'s lowest-free allocation —
     and the last of those is refused nowhere, because the box exists and takes cards. It is
     simply not the drawer the operator thinks they are looking at, which is why the restore
     falls back to NOTHING rather than to a guess. */
  await open(page, { box: 2 }, GAMES, HAND_BOXES_SEALED_2, { probe: false })

  /* THE STAGE FOOT AND NOT `.capture-box-val`, which is the RESTING row and does not exist
     while a field is open — and this check opens the box field on purpose. The foot is drawn
     in both states and is the screen's standing answer to "which drawer is this". */
  await expect(page.locator('.capture-foot-box-name')).toHaveText('No box')

  /* IT SAYS WHICH BOX AND WHY, and it says it by NAME — the screen's own vocabulary, not the
     number the operator no longer sees anywhere else on it. */
  const note = page.locator('.capture-refused').filter({ hasText: /sealed/ })
  await expect(note).toContainText('Slabs')

  /* AND THE REMEDY IS THE PRESS THEY WERE ABOUT TO MAKE: the field is open with focus in the
     entry, which is where `Pick a box` would have put them. */
  await expect(page.getByLabel(/Find a box by name or number/)).toBeFocused()
})

test('a restored box that is gone is let go of, and says so without naming a drawer', async ({
  page,
}) => {
  await open(page, { box: 99 }, GAMES, HAND_BOXES, { probe: false })

  await expect(page.locator('.capture-foot-box-name')).toHaveText('No box')
  await expect(page.locator('.capture-refused').filter({ hasText: /not in the store/ })).toBeVisible()
  await expect(page.getByLabel(/Find a box by name or number/)).toBeFocused()
})

/* ============================================================================================
   THE RESTORE COMPARES THE DRAWER'S ID, NOT ITS NUMBER (D145)

   D142 enumerated three ways a restored box goes stale and built two of them. The third — the
   number deleted and handed to a different physical drawer by `next_box_number`'s lowest-free
   allocation — passed `found !== undefined` and `state !== 'closed'` and kept the restore,
   because box 7 really does exist and really does take cards. Every photograph of that sitting
   then goes to an address that does not match the shelf, and nothing says a word.

   THE FIXTURE'S IDS ARE NOT ITS NUMBERS, on purpose (see `HAND_BOXES`). A case here that
   compared the wrong pair would pass against a fixture where box 2 wears id 2.
   ========================================================================================== */

/** The four boxes as a store that has never issued an id: every row's `bid` is null, which is
 *  what a box holding cards with no registry entry answers, and what a store an older build
 *  migrated answers for all of them. */
const HAND_BOXES_NO_IDS = {
  boxes: HAND_BOXES.boxes.map((row) => ({ ...row, bid: null })),
}

test('a restored box whose number now belongs to another drawer is let go of', async ({
  page,
}) => {
  /* THE OWNER'S OWN CASE, 2026-09-11: *"i deleted an old box 1, started writing into a new box
     (now new box 1)"*. This browser was set to box 3 when box 3 was the drawer with id 40; the
     store says box 3 is id 23 today, so the drawer they left is gone and this is not it. */
  await open(page, { box: 3, bid: 40 }, GAMES, HAND_BOXES, { probe: false })

  await expect(page.locator('.capture-foot-box-name')).toHaveText('No box')

  /* IT SAYS SO AS A FACT, because it holds one — D145 forbids an id softening what it knows.
     AND IT SAYS IT BY NUMBER, which is the one sentence on this screen that has to: the number
     is the only thing the two drawers share, and naming the box now at it (`Epics`) would be
     telling the operator their drawer is something it has never been. */
  const note = page.locator('.capture-refused').filter({ hasText: /different drawer now/ })
  await expect(note).toContainText('Box 3')
  await expect(note).not.toContainText('Epics')

  await expect(page.getByLabel(/Find a box by name or number/)).toBeFocused()
})

test('a restored box the store still calls the same drawer is kept', async ({ page }) => {
  /* THE ARM THAT STOPS THE GUARD BEING VACUOUS. A comparison that cleared unconditionally would
     satisfy every case above it, and the operator would lose their box on every single load. */
  await open(page, { box: 3, bid: 23 }, GAMES, HAND_BOXES)

  await expect(page.locator('.capture-foot-box-name')).toHaveText('Epics')
  await expect(page.locator('.capture-refused')).toHaveCount(0)
})

test('a box remembered before ids existed is let go of, and says it cannot tell', async ({
  page,
}) => {
  /* THE MIGRATION ARM. A browser holding a setup written before this landed has a number and no
     id, and the honest answer is that nothing can tell whether that number still means the same
     drawer. It clears — the same fallback D142 already chose for its other two cases — and the
     cost is one press, once, because the very next pick records an id. */
  await open(page, { box: 1 }, GAMES, HAND_BOXES, { probe: false })

  await expect(page.locator('.capture-foot-box-name')).toHaveText('No box')

  /* AND IT DOES NOT CLAIM THE DRAWER CHANGED, which would be a fact it does not hold. It names
     the box the operator would recognise, because that box probably IS theirs. */
  const note = page.locator('.capture-refused').filter({ hasText: /may not be the drawer/ })
  await expect(note).toContainText('Bulk')
  await expect(note).not.toContainText('different drawer now')
})

test('a store that issues no ids keeps the restore, rather than refusing it forever', async ({
  page,
}) => {
  /* THE OTHER SILENCE, AND IT IS NOT THE SAME SILENCE. A browser with no id is one press from
     having one. A STORE with no ids can never answer the question, so clearing here would empty
     a good box on every load for ever, over something the operator cannot fix from this screen.
     The rule that predates the id decides, unchanged — which is D145's own two-arm shape. */
  await open(page, { box: 1 }, GAMES, HAND_BOXES_NO_IDS)

  await expect(page.locator('.capture-foot-box-name')).toHaveText('Bulk')
  await expect(page.locator('.capture-refused')).toHaveCount(0)
})

test('picking a box records which drawer it was, so the next sitting can compare', async ({
  page,
}) => {
  /* THE HALF THAT MAKES THE REST WORK. Without this the id is never written, every restore falls
     down the "cannot tell" arm for ever, and that would look exactly like a working guard while
     throwing the whole feature away. */
  await open(page, undefined, GAMES, HAND_BOXES)
  await page.keyboard.press('b')
  await expect(page.locator('.capture-opt').first()).toBeVisible()
  await page.getByRole('button', { name: /^Slabs/ }).click()

  expect(await storedSetup(page)).toMatchObject({ box: 2, bid: 22 })
})

/* ============================================================================================
   THE PICKER DRAWS NAMES, AND A NUMBER ONLY WHERE ONE WAS TYPED (D145)
   ========================================================================================== */

test('a typed number puts the number back on the rows that answer it', async ({ page }) => {
  /* D142 KEPT THE NUMBER HERE FOR EXACTLY THIS, and the reason is still good: *"a row that hid
     the number would answer a search for `9` with nine rows that do not visibly contain a 9."*
     What changed is that the reason is spent where it applies instead of on every row always. */
  await open(page, undefined, GAMES, HAND_BOXES)
  await page.keyboard.press('b')
  await expect(page.locator('.capture-opt').first()).toBeVisible()

  await page.keyboard.type('2')
  await expect(page.locator('.capture-opt')).toHaveCount(1)
  expect(await boxOptionText(page)).toEqual(['Slabs Box 2 next index 4'])

  /* AND A NAME SEARCH BRINGS NO NUMBER BACK, because none of those rows matched on one. The
     second row is the create-box offer, which every non-exact entry draws last. */
  await page.keyboard.press('Backspace')
  await page.keyboard.type('om')
  await expect(page.locator('.capture-opt')).toHaveCount(2)
  expect(await boxOptionText(page)).toEqual(['Commons next index 41', 'om New'])
})

test('an unnamed box draws its number once, typed or not', async ({ page }) => {
  /* AN UNNAMED BOX IS NOT AN EXCEPTION TO THE INSTRUCTION — D20 leaves a name optional, so the
     number is the only thing such a drawer HAS to be called, and a placeholder would draw a
     fault where there is none (D56). The hazard is the other way round: `captureBoxLabel` has
     already put the number in the name's place, so a suffix drawn beside it reads `Box 6 Box 6`.
   */
  const UNNAMED = {
    boxes: [
      { ...HAND_BOXES.boxes[0], box: 6, bid: 26, name: null },
      /* A name that is only whitespace is unnamed to `captureBoxLabel`, which trims — and was
         NOT unnamed to the `name === null` test this replaced, so it doubled. */
      { ...HAND_BOXES.boxes[1], box: 7, bid: 27, name: '   ' },
    ],
  }
  await open(page, undefined, GAMES, UNNAMED)
  await page.keyboard.press('b')
  await expect(page.locator('.capture-opt')).toHaveCount(2)
  expect(await boxOptionText(page)).toEqual(['Box 6 next index 11', 'Box 7 next index 4'])

  await page.keyboard.type('6')
  await expect(page.locator('.capture-opt')).toHaveCount(1)
  expect(await boxOptionText(page)).toEqual(['Box 6 next index 11'])
})

test('clearing the setup empties every claim, forgets the key, and can be undone', async ({
  page,
}) => {
  /* `bid` SEEDED TO THE FIXTURE'S OWN, so the restore holds and this case is about the CLEAR
     (D145). Seeding `box` alone is a browser that remembered a number before it recorded which
     drawer that was, and the restore lets such a box go — correctly, and it would empty the
     screen before this case pressed anything. */
  await open(page, { box: 3, bid: 23, setHint: 'MEG', finish: ['normal'] }, GAMES, HAND_BOXES)

  const clear = page.getByRole('button', { name: 'Clear the setup' })
  await expect(clear).toBeEnabled()
  await clear.click()

  await expect(page.locator('.capture-box-val')).toContainText('No box yet')
  await expect(page.locator('.capture-row').filter({ hasText: /Set hint/ })).toContainText('None')
  await expect(finishRow(page)).toContainText('No claim')

  /* THE GAME GOES TO THE REGISTRY'S DEFAULT, not to null. A null game draws the blocked
     reason for a registry that has not ARRIVED — "Waiting for the game list from the server"
     — which after a successful load is a sentence that is simply untrue. */
  await expect(page.locator('.capture-row').filter({ hasText: /Game/ })).toContainText('Pokémon')

  /* AND NOTHING IN THE STORE WAS ASKED TO DO ANYTHING. `sealEveryTest` records every request
     that reached the capture origin and this spec's header promises none writes; the clear
     calling a route would be the one press here that could. */
  const receipt = page.locator('.bn-toast').filter({ hasText: 'Setup cleared' })
  await expect(receipt).toBeVisible()
  await expect(receipt).toContainText('untouched')

  await receipt.getByRole('button', { name: 'Undo' }).click()

  await expect(page.locator('.capture-row').filter({ hasText: /Box/ })).toContainText('Epics')
  await expect(page.locator('.capture-row').filter({ hasText: /Set hint/ })).toContainText('MEG')
  expect(await storedSetup(page)).toMatchObject({ box: 3, setHint: 'MEG', finish: ['normal'] })
})

test('the clear is disabled while there is nothing to clear, rather than absent', async ({
  page,
}) => {
  await open(page, undefined, GAMES, HAND_BOXES)

  /* DISABLED, NOT HIDDEN (D118). A control that appears and disappears with the state it acts
     on moves the rail's height under the operator's hand — and this one sits at the foot of
     the column, so everything above it would move too. */
  const clear = page.getByRole('button', { name: 'Clear the setup' })
  await expect(clear).toBeVisible()
  await expect(clear).toBeDisabled()
})

/* ------------------------------------------------------------------------------------------
 * A GAME WHOSE EXPORT NEEDS THE HINT SAYS SO AT THE RIG — AND STILL TAKES THE CLAIM
 *
 * `pokemon` carries `export_needs_hint` in the registry: its whole TCGplayer category is
 * 32,629,598 B, 97% of the ceiling the download is refused past, so a run whose own cards
 * under-specify the scope is refused at the fetch rather than quietly widened. That refusal
 * lives on the server. What lives HERE is telling the operator while it is still free to
 * fix, because the alternative is learning it an hour of captures later — which is the exact
 * defect `app/src/setHint.ts` was written for.
 *
 * THE LOAD-BEARING HALF IS THAT NOTHING IS REFUSED. D65's rule stands: the rig does not stop
 * for an autocomplete, and a shutter that refused mid-feeder at a 623 ms cadence would leave
 * a physical card in the drawer with no record and every card behind it renumbered. The
 * field still takes any text, the row still draws, and no control is disabled.
 *
 * THE STUB CARRIES THE FLAG BECAUSE THE REGISTRY DOES. `GET /games` serves the entry
 * verbatim, so this boolean is the same literal `_scope_for_run` refuses on — there is no
 * second threshold on this side to drift out of step with it.
 */
const NEEDS_HINT = {
  default: 'pokemon',
  games: [{ ...GAMES.games[0], export_needs_hint: true, export_category_bytes: 32629598 }],
}

test('a game whose export needs a set hint says so, in all three states of the field', async ({
  page,
}) => {
  /* THE VOCABULARY IS STUBBED BECAUSE `unchecked` OUTRANKS EVERY OTHER VERDICT, and rightly:
     a portal outage must read as "cannot tell" rather than as a judgement (D65). Without
     this the note under the field is the transport refusal and says nothing about hints. */
  await routeSets(page, RIFTBOUND_SETS)
  await open(page, { box: 3, bid: 23 }, NEEDS_HINT, HAND_BOXES)
  await page.keyboard.press('h')

  /* THREE PLACES, BECAUSE THE OPERATOR MEETS THIS FIELD IN THREE STATES: the head while it
     is open, the meta beside the cursor, and the row once it is shut. The row is the one
     that matters at the rig — it is where the screen sits for every card of a sitting
     nobody pressed H on, and `None` on its own reads as a choice that was made. */
  await expect(page.locator('.capture-open').filter({ hasText: /Set hint/ })).toContainText(
    'Needed for this game',
  )
  await expect(hintMeta(page)).toHaveText(/needed/i)
  await expect(hintNote(page)).toContainText('needs one')
  await expect(hintNote(page)).toContainText('will refuse the run')

  /* AND IT NAMES THE WAY BACK. A note saying only "this will be refused" leaves an operator
     who has already captured the box with nowhere to go; the retroactive claim editor is
     where a hint is set after the fact, and it is on the screen this sentence names. */
  await expect(hintNote(page)).toContainText('Manage box')

  /* THE RESTING ROW SAYS `Needed`, NEVER `None`. `None` beside a sub-line reading "needed
     for this game" read at a glance as "none needed for this game" — the opposite of what
     the row means — and the owner's screenshot showed exactly that, clipped mid-word by the
     chevron on top of it. The value now states the requirement directly and carries no
     sub-line for this state at all. */
  await page.keyboard.press('Escape')
  const row = page.locator('.capture-row').filter({ hasText: /Set hint/ })
  await expect(row).not.toContainText('None')
  await expect(row.locator('.capture-val')).toHaveText('Needed')
  await expect(row.locator('.capture-sub')).toHaveCount(0)
})

/* ------------------------------------------------------------------------------------------
 * NO SUB-LINE IN A CAPTURE ROW MAY EVER BE CLIPPED BY ITS CONTAINER
 *
 * `.capture-sub` used to live INSIDE `.capture-val`, which is `overflow: hidden`. The stack
 * card sits in a narrow column, so any row combining a value with a sub-line — the typed
 * hint beside "names no set" here, the resolution beside "under target" on the camera row —
 * clipped the sub-line the instant the row was narrower than value + sub, which on a real
 * rig it always is. The fix moved the sub-line out to be a sibling of the value inside
 * `.capture-right`, so only `.capture-val-name` is ever allowed to clip.
 *
 * THIS IS THE MUTATION-TESTED HALF: reverting the CSS fix alone (see the entry's own report)
 * turns this red while every other case in this file stays green, because nothing else here
 * measures a bounding box.
 */
test('a set hint that names no set never clips its sub-line, at every width this app is verified at', async ({
  page,
}) => {
  await routeSets(page, RIFTBOUND_SETS)
  await open(page, { box: 3, bid: 23 }, NEEDS_HINT, HAND_BOXES)
  await page.keyboard.press('h')

  const hint = page.getByLabel('Set hint')
  await hint.fill('Spiritfoged')
  await expect(hintMeta(page)).toHaveText(/names no set/i)

  await page.keyboard.press('Escape')
  const row = page.locator('.capture-row').filter({ hasText: /Set hint/ })
  await expect(row).toContainText('Spiritfoged')
  const sub = row.locator('.capture-sub')
  await expect(sub).toHaveText(/names no set/i)
  const value = row.locator('.capture-val')

  for (const width of [1440, 820, 390]) {
    await page.setViewportSize({ width, height: 900 })
    await expect(row).toContainText('Spiritfoged')
    await expect(sub).toHaveText(/names no set/i)

    const rowBox = await row.boundingBox()
    expect(rowBox).not.toBeNull()

    for (const el of [value, sub]) {
      const elBox = await el.boundingBox()
      expect(elBox).not.toBeNull()
      // Fully inside the row's own box, on both edges — a clipped element still reports its
      // full un-clipped bounding box in the accessibility tree, but not once its content has
      // actually overflowed a hidden ancestor, which is the next check.
      expect(elBox!.x).toBeGreaterThanOrEqual(rowBox!.x - 0.5)
      expect(elBox!.x + elBox!.width).toBeLessThanOrEqual(rowBox!.x + rowBox!.width + 0.5)
      expect(elBox!.y).toBeGreaterThanOrEqual(rowBox!.y - 0.5)
      expect(elBox!.y + elBox!.height).toBeLessThanOrEqual(rowBox!.y + rowBox!.height + 0.5)

      // And its own content is not overflowing ITS box — the direct symptom of being nested
      // inside an `overflow: hidden` ancestor narrower than it needs.
      const overflow = await el.evaluate((node) => node.scrollWidth - node.clientWidth)
      expect(overflow).toBeLessThanOrEqual(1)
    }
  }
})

test('the same blank field on a game that needs no hint reads Optional, and is not flagged', async ({
  page,
}) => {
  /* THE OTHER DIRECTION, AND IT IS THE ARM THAT MATTERS AS MUCH AS THE FIRST. A note that
     fired on every game would be a note nobody reads, and an outcome assertion cannot tell
     "drawn correctly" from "drawn always" — so this pair differs in exactly one boolean, on
     the same stub, at the same blank field, and asserts the opposite of each claim above. */
  await routeSets(page, RIFTBOUND_SETS)
  await open(page, { box: 3, bid: 23 }, GAMES, HAND_BOXES)
  await page.keyboard.press('h')

  await expect(page.locator('.capture-open').filter({ hasText: /Set hint/ })).toContainText(
    'Optional',
  )
  await expect(hintMeta(page)).toHaveText(/no hint/i)
  await expect(hintNote(page)).toContainText('Optional')
  await expect(hintNote(page)).not.toContainText('needs one')

  await page.keyboard.press('Escape')
  const row = page.locator('.capture-row').filter({ hasText: /Set hint/ })
  await expect(row.locator('.capture-sub')).toHaveCount(0)
})
