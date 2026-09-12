import { test, expect, type Page } from '@playwright/test'
import { sealEveryTest } from './shell'

/* THE PIPELINE IS REACHABLE FROM A SCREEN, ASSERTED WHERE NOTHING ELSE CAN SEE IT.
 *
 * `CLAUDE.md`'s hard rule — "A ROUTE IS NOT A FEATURE. Nothing is built until it is reachable
 * from a screen" — was written after three tested routes turned out to have no control
 * anywhere. The pipeline was the larger instance of the same thing and nobody had counted it:
 * `./pkmnscan identify | join | emit | reconcile` has existed since step 4, has been through a
 * real 53-card run and a real 544-card run, and until now could only be reached by somebody
 * typing at a terminal. `docs/GATES.md` records what that cost — "the owner had no visibility
 * into emitted import files; their names exist only in CLI output the owner never sees when
 * someone else drives the commands."
 *
 * THE MONEY GATE IS WHAT THIS FILE MOSTLY ASSERTS, and the strongest assertion in it is a
 * NEGATIVE one: before the free preflight has answered, the control that spends does not
 * exist. Not disabled — absent. A disabled button is one attribute away from being pressable
 * and it is the kind of attribute a later refactor removes without noticing; an element that
 * is not rendered has to be deliberately re-added.
 *
 * NO REAL REQUEST IS EVER MADE, which matters more here than on any other screen in the
 * product: one of these routes spends money. Every route is intercepted, the spend route is
 * intercepted with a body assertion rather than a call, and the test would fail at the fetch
 * if the screen reached a route this file does not name.
 *
 * OWNER-SIDE, so no floor from `docs/DESIGN.md`'s Fulfillment table is asserted — that table
 * governs `#/fulfillment` and `app/tests/fulfillment.spec.ts` is its instrument.
 *
 * NOT A HARNESS TEST AND MUST NOT BECOME ONE. `docs/GATES.md`'s contract is seven Python tests
 * at the Stop hook; this starts a browser. `make design-check` runs it.
 */

/* `#/runs` SINCE 2026-08-29, AND IT WAS `#/inventory` FOR EVERY ASSERTION IN THIS FILE BEFORE
 * THAT. The owner gave the pipeline a route of its own between Capture and the review queue;
 * `Runs.tsx` is the screen and `RunPanel` is unchanged inside it. What moved in this file is
 * two constants and one new step in `open` — the box is picked from a strip here instead of
 * being whatever shelf the walk happened to land on, which is the visible half of the trade
 * D33 argued against and the owner accepted. */
const VIEW_ROUTE = '/#/runs'
const VIEW = 'main.runs'

/** What `identify --dry-run` prints, cut to the lines the panel parses out of it.
 *
 *  THE REAL SHAPE, because the parse is `server/pipeline_routes.py`'s and it is a regex over
 *  this exact layout. A fixture that invented a friendlier format would assert that the panel
 *  can render numbers, which was never in doubt, instead of that it can read the ones the
 *  command actually prints. */
const PREFLIGHT_CONSOLE = [
  'capture dir     /tmp/box9',
  'photographs     40',
  'cache hits      4',
  'to send         36',
  'payload         12.1 MB in 1 batch chunk(s)',
  'estimated cost  $0.42',
  'prompt          1ef974bf511d',
  '',
  '--dry-run: nothing submitted, nothing written.',
].join('\n')

type Wire = { method: string; path: string; body: unknown }

/** One card, in the shape `GET /inventory` answers with — every field, not the handful this
 *  file reads.
 *
 *  A PARTIAL FIXTURE HERE DOES NOT FAIL PARTIALLY, it crashes the screen: `BoxOps` reads
 *  `sections_detail.length` and the walk reads `set_hint.trim()`, so a record missing either
 *  takes the whole route down and every assertion below fails with "element not found" —
 *  which reads exactly like an unregistered route and sent this file's first draft looking in
 *  the wrong place. `app/tests/inventory.spec.ts:card` is the reference shape. */
function inventoryPayload() {
  const box = 9
  return {
    cards: {
      '9/1': {
        box,
        index: 1,
        label: `Box ${box} · Section 1 · Card 1`,
        section: 1,
        card: 1,
        place: {
          located: true,
          label: `Box ${box} · Section 1 · Card 1`,
          box,
          index: 1,
          section: 1,
          card: 1,
          box_name: null,
          section_start: 1,
          section_end: 1,
          box_total: 1,
          box_closed: false,
          fraction: 0,
          neighbors: null,
          section_gaps: 0,
        },
        photo: `photos/${box}/1.jpg`,
        set_hint: 'ME01',
        metadata_finish: 'normal',
        game: 'pokemon',
        rarity_claim: null,
        note: null,
        captured_at: '2026-08-24T01:00:00+00:00',
        capture_id: 'cap-1',
        name: 'Thievul',
        number: '090',
        printed_total: '132',
        confidence: null,
        sku: null,
        condition: null,
        state: 'captured',
        state_at: '2026-08-24T01:00:00+00:00',
        retire_reason: null,
        run: null,
      },
    },
  }
}

function runRow(overrides: Record<string, unknown> = {}) {
  return {
    run: '2026-08-24-box9-01',
    path: '/tmp/runs/2026-08-24-box9-01',
    capture_dir: '/tmp/captures/cards/box9',
    scope: { box: 9, whole_box: true, cards: null },
    /* THE SERVER'S OWN ANSWER TO WHICH BOX, AND WHAT IT IS CALLED (D56). `box` is what
       `RunPanel` groups and labels on now; `runScope.ts:boxOf` keeps the scope/capture-dir
       derivation only for a server that predates the field. Box 9 is UNNAMED in this file's
       registry fixture and this row agrees with it — the two would be a disagreement about the
       same box otherwise, which is exactly the drift the server-side join exists to prevent. */
    box: 9,
    box_name: null,
    live: false,
    pid: null,
    phase: 'join',
    batch_ids: ['msgbatch_x'],
    collected: true,
    joined: false,
    counts: {},
    /* A RECORDED RUN, BECAUSE `{}` IS THE DEGENERATE SHAPE AND NOT THE ORDINARY ONE. These are
       the owner's own 2026-09-11 run — 290,470 in, 3,761 out, $0.154638 at identify/cost.py's
       rates — which is the run that made the money pill a defect: it drew `Costs money` beside a
       six-figure token count and no dollar figure at all, four minutes after finishing. A
       fixture that is a RECORDING is the same argument T9 makes against frames a test drew for
       itself. `usage: {}` still has a case of its own below; that is what a run written before
       the field looks like, which is every run on the owner's machine. */
    usage: { input_tokens: 290470, output_tokens: 3761, cost_usd: 0.154638 },
    ...overrides,
  }
}

/** A 1x1 GIF, standing in for the sent bytes. The assertions here are about GEOMETRY and
 *  about which reading was asked for, never about what a photograph looks like — so the
 *  smallest decodable image is the honest fixture, and a real JPEG would be a large constant
 *  nothing reads. It differs per reading so a case can assert the picture CHANGED. */
const PIXEL = 'data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=='

/** What `POST /pipeline/crop-preview` answers, in the shape the route really returns.
 *
 *  ONE CARD, WALKED BY `offset`. `rect` is in the ORIGINAL frame's pixels and the screen turns
 *  it into percentages, so the numbers here are chosen to divide cleanly: 216/2160 is 10%, and
 *  1728/2160 is 80%. An assertion that reads the rendered `left` back out is then checking the
 *  mapping rather than restating a magic string.
 *
 *  `band_absent` is the registry's refusal, and it has a fixture because it is a real state
 *  this route shipped without: `pipeline/games.py` holds which bands a game claims and only
 *  `pokemon` claims a number band, so a Riftbound card gets a cut and no strip. */
function cropPreviewPayload(crop: boolean, maxEdge: number, offset: number, game = 'pokemon') {
  const claimsBand = game === 'pokemon'
  return {
    scope: { box: 9, whole_box: true, cards: null },
    capture_dir: '/tmp/captures/cards/box9',
    crop,
    max_edge: maxEdge,
    total: 543,
    offset,
    sample: {
      box: 9,
      index: offset + 1,
      game,
      frame: [2160, 3840],
      sent: crop ? [859, maxEdge] : [882, maxEdge],
      rect: crop ? [216, 384, 1944, 3456] : null,
      method: 'edges',
      sent_image: `${PIXEL}#${crop ? 'crop' : 'whole'}-${maxEdge}`,
      band_rect: claimsBand ? [59, 931, 800, 1117] : null,
      band_px: claimsBand ? (crop ? [741, 186] : [704, 177]) : null,
      band_absent: claimsBand
        ? null
        : `\`${game}\` claims no number band. \`geometry/crop.py\`'s bands are fractions measured on a Pokemon card.`,
    },
  }
}

/** Stub the whole server and open the screen.
 *
 *  `to_send` and `estimate_usd` are parameters because the two most interesting states of this
 *  panel are "there is something to spend on" and "everything is cached, so there is nothing to
 *  spend" — and the second is the one a screen gets wrong by drawing a confirm anyway. */
async function open(
  page: Page,
  options: {
    toSend?: number
    estimate?: number
    /** How many of the box's cards the cache already owns. Its own option because the sentence
     *  about the cache is drawn ONLY above zero, and a fixture that could not say zero could
     *  only ever assert the visible half of that. */
    cacheHits?: number
    busyRun?: string | null
    /** Fields to override on the OPEN run's detail. Passed through here rather than by
     *  registering a competing `page.route` before the call — Playwright matches handlers in
     *  reverse registration order, so a route set up first is the one that loses, which made a
     *  test that looked correct silently assert against this function's fixture. */
    detail?: Record<string, unknown>
    /** The run list reports a live run, which is the one state that opens the fold by itself. */
    live?: boolean
    /** The game the previewed card claims. `riftbound` is the state where the registry
     *  refuses a band — a cut with no strip, and a sentence saying why. */
    previewGame?: string
    /** An EMPTY run list, which is the state the panel could not draw its own steps in until
     *  2026-08-25. Distinct from omitting the option: `[]` means "no runs on disk", where
     *  `undefined` means "the ordinary one-run fixture". */
    runs?: unknown[]
    /** Boxes whose child could not be spawned, in the shape `POST /pipeline/identify` answers
     *  with. A partial send is the one failure no validation can pre-empt (D48), so it is the
     *  one the screen has to draw rather than swallow. */
    failed?: { box: number; code: string; message: string }[]
    /** Live submission claims, in the shape `GET /pipeline/submissions` answers with
     *  (D-a-claim-on-the-cards). Empty by default: nothing in this file is about a claim, and
     *  a healthy store holds none. It is an option rather than a constant so the one case
     *  below that needs the panel drawn can have it. */
    claims?: {
      receipt: string
      run: string | null
      pid: number
      started_at: string
      cards: number
      sample: string[]
      capture_dir: string | null
      holder_alive: boolean
    }[]
  } = {},
): Promise<Wire[]> {
  const wire: Wire[] = []
  const record = (method: string, url: string, body: unknown) =>
    wire.push({ method, path: new URL(url).pathname, body })

  /* THE SPEND ROUTE, INTERCEPTED AND NEVER CALLED. The body is recorded so the assertion can
     read what the screen would have sent — the strongest thing a browser test can say about a
     route it must not actually reach. */
  await page.route(/\/pipeline\/identify$/, async (route) => {
    const body = route.request().postDataJSON() as { scopes?: { box: number }[] }
    record('POST', route.request().url(), body)
    /* ONE STARTED RUN PER SCOPE SENT, because a send is a cart and the answer names both
       halves (D48). Echoing the request rather than returning a fixed run is what lets the
       cart cases assert that N boxes produce N children — a constant here would pass whether
       the screen sent one box or five. */
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        started: (body.scopes ?? [{ box: 9 }]).map((leg, n) => ({
          run: `2026-08-24-box${leg.box}-0${n + 2}`,
          path: `/tmp/runs/2026-08-24-box${leg.box}-0${n + 2}`,
          pid: 4242 + n,
          scope: { box: leg.box, whole_box: true, cards: null },
          argv: [],
        })),
        failed: options.failed ?? [],
      }),
    })
  })

  /* THE PREVIEW, WHICH IS FREE AND IS FIRED ON EVERY CHIP PRESS. Recorded like the rest so an
     assertion can read WHICH reading the picture was drawn for — the failure worth forbidding
     is a strip that keeps describing the previous pair, which is the estimate's stale-figure
     defect one control higher up. */
  await page.route(/\/pipeline\/crop-preview$/, async (route) => {
    const body = route.request().postDataJSON()
    record('POST', route.request().url(), body)
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        cropPreviewPayload(
          Boolean(body?.crop),
          Number(body?.max_edge),
          Number(body?.offset ?? 0),
          options.previewGame ?? 'pokemon',
        ),
      ),
    })
  })

  /* ONE LEG PER SCOPE, AND THE TOTAL SUMMED THE WAY THE SERVER SUMS IT (D48). The response
     is always a list — a single box answers as a cart of one — and the total is what the
     confirm is gated on, so a fixture that returned a fixed one-box body could not tell a
     screen that reads the total from one that reads the first leg and calls it the total. */
  await page.route(/\/pipeline\/preflight$/, async (route) => {
    const body = route.request().postDataJSON() as { scopes?: { box: number }[] }
    record('POST', route.request().url(), body)
    const asked = body.scopes ?? [{ box: 9 }]
    const perBox = options.toSend ?? 36
    const perBoxMoney = options.estimate ?? 0.42
    const legs = asked.map((leg) => ({
      ok: true,
      exit_code: 0,
      scope: { box: leg.box, whole_box: true, cards: null },
      capture_dir: `/tmp/captures/cards/box${leg.box}`,
      console: PREFLIGHT_CONSOLE,
      photographs: 40,
      cache_hits: options.cacheHits ?? 4,
      to_send: perBox,
      estimate_usd: perBoxMoney,
      busy_run: options.busyRun ?? null,
    }))
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        scopes: legs,
        total: {
          photographs: 40 * legs.length,
          cache_hits: (options.cacheHits ?? 4) * legs.length,
          to_send: perBox * legs.length,
          estimate_usd: Number((perBoxMoney * legs.length).toFixed(2)),
          boxes: legs.length,
          busy: legs
            .filter((leg) => leg.busy_run !== null)
            .map((leg) => ({ box: leg.scope.box, run: leg.busy_run })),
        },
      }),
    })
  })

  await page.route(/\/pipeline\/runs\/[^/]+\/(join|emit|reconcile)$/, async (route) => {
    record('POST', route.request().url(), route.request().postDataJSON())
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        exit_code: 0,
        step: 'join',
        run: '2026-08-24-box9-01',
        console: 'would queue      3 card(s)',
        dry_run: true,
        files: [],
        summary: runRow(),
      }),
    })
  })

  await page.route(/\/pipeline\/runs\/[^/]+$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ...runRow(),
        console: 'identified      40/40',
        files: [
          { name: 'import-listed.csv', bytes: 2048, modified: 0, is_import: true },
          // A NON-IMPORT ARTEFACT, so the absence asserted above is not vacuous: the
          // list still renders here, it just does not carry the CSVs any more.
          { name: 'reconcile.txt', bytes: 900, modified: 0, is_import: false },
        ],
        manifest: {},
        ...(options.detail ?? {}),
      }),
    })
  })

  await page.route(/\/pipeline\/runs$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        runs:
          options.runs ??
          [runRow(options.live ? { live: true, pid: 999, phase: 'identifying' } : {})],
      }),
    })
  })

  /* THE CLAIMS PANEL'S OWN READ (D-a-claim-on-the-cards). `#/runs` draws
     `SubmissionClaims`, which reads this on mount — and the spec seal means an unstubbed read
     is a FAILURE rather than a missing panel, which is how every case in this file went red
     the first time the panel landed. An EMPTY list is the right default here: nothing in this
     file is about a live claim, and a panel that draws nothing is the state a healthy store is
     in. `claims-panel.spec.ts` is where the panel itself is asserted. */
  await page.route(/\/pipeline\/submissions$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        claims: options.claims ?? [],
        counts: {
          claims: (options.claims ?? []).length,
          keys: (options.claims ?? []).reduce((sum, claim) => sum + claim.cards, 0),
          stale: (options.claims ?? []).filter((claim) => !claim.holder_alive).length,
        },
      }),
    })
  })

  await page.route(/\/boxes$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        boxes: [
          {
            box: 9,
            name: null,
            /* THE FULL `BoxRecord`, including `sections_detail`. A fixture missing it crashes
               `BoxOps` on `.length` and takes the whole screen down — which is what happened
               while this file was being written, and is a fair warning that a partial fixture
               tests the gap panel rather than the screen. */
            sections: [],
            state: 'open',
            capacity: null,
            fill: 1,
            next_index: 2,
            cards: 1,
            sold: 0,
            retired: 0,
            listed: 0,
            sections_detail: [{ section: 1, start: 1, end: 1, count: 1 }],
          },
          {
            /* A SECOND BOX, so a cart can be a cart of more than one. NAMED WHERE BOX 9
               IS NOT, which is what makes this fixture cover both arms of `boxLabel` (D56):
               a named box draws `Box 12 · codes` everywhere it appears and an unnamed one
               draws `Box 9` with no separator and no placeholder — D20 leaves a name optional,
               so unnamed is an ordinary box rather than a fault to mark. */
            box: 12,
            name: 'codes',
            sections: [],
            state: 'open',
            capacity: null,
            fill: 4,
            next_index: 5,
            cards: 4,
            sold: 0,
            retired: 0,
            listed: 0,
            sections_detail: [{ section: 1, start: 1, end: 4, count: 4 }],
          },
        ],
      }),
    })
  })

  await page.route(/\/games$/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{"games": []}' })
  })

  /* D76's scope preview. Registered panel-wide because EVERY case that opens a run now draws
     it, and a case that wanted a different scope re-registers over this one — AFTER calling
     `open`, because Playwright's LAST matching route wins and one declared above this is
     silently shadowed by it. */
  await page.route(/\/pipeline\/runs\/[^/]+\/scope/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        run: '2026-08-30-box3-01',
        games: [
          {
            game: 'riftbound',
            display: 'Riftbound',
            category_id: 89,
            cards: 200,
            hinted: 1,
            unhinted: 199,
            hints: ['OGN'],
            policy: 'category',
          },
        ],
        scopes: ['category', 'sets'],
        asked: {
          game: 'riftbound',
          category_id: 89,
          hints: ['OGN'],
          set_ids: [],
          unresolved_hints: [],
          sets: [],
          widened: true,
          scope: 'category',
          policy: 'category',
          chosen_by: 'policy',
          reason: 'game_policy',
          cards: 200,
          hinted: 1,
          unhinted: 199,
        },
        reason: null,
        message: null,
      }),
    })
  })

  await page.route(/\/search\?/, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{"groups": []}' })
  })

  await page.route(/\/inventory$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(inventoryPayload()),
    })
  })

  await page.route(/\/photo\/\d+\/\d+/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="63" height="88"/>',
    })
  })

  await page.goto(VIEW_ROUTE)
  await expect(page.locator(VIEW)).toBeVisible()
  await expect(page.locator('.runs-master')).toBeVisible()
  return wire
}

/* WHERE THE MONEY GATE LIVES NOW. The screen is master-detail — every run on the left, the
 * picked run's four steps on the right — and the paid press moved into a staged dialog off
 * the header: which boxes, how each is read, what it costs, a receipt. Every step of that is
 * still one press with no typing, which is what D33 asked for; what changed is that the
 * stages are a sequence rather than a column, so the helpers below name the stage they leave
 * the screen on and each case says which one it needs. */

/** The header's primary, which opens the identify dialog.
 *
 *  SCOPED TO THE PAGE HEADER, because the empty run list draws an `Identify a box` button of
 *  its own — two controls doing the same job is not an ambiguity to route around with a
 *  looser locator, it is two call sites this helper must not confuse. */
async function openComposer(page: Page) {
  await page.locator('.bn-head-actions').getByRole('button', { name: /^Identify/ }).click()
  await expect(page.locator('.runs-composer')).toBeVisible()
}

/** Ticks a box on the dialog's first stage.
 *
 *  SCOPED TO `.runs-boxes`, AND THE FIRST DRAFT WAS NOT — `getByRole('button', {name: 'Box 9'})`
 *  matched the chip AND a run row whose accessible name ends `box 9`, and Playwright's strict
 *  mode caught it as an ambiguity rather than clicking the wrong one. */
async function pickBox(page: Page, box = 9) {
  await page.locator('.runs-boxes').getByRole('button', { name: new RegExp(`^Box ${box}\\b`) }).click()
}

/** Forward from the boxes stage to the reading stage. */
async function toReading(page: Page) {
  await page.getByRole('button', { name: /^Next · how they are read$/ }).click()
  await expect(page.locator('.run-readings').first()).toBeVisible()
}

/** Back to the reading stage from the cost stage, by the footer's own way back. */
async function backToReading(page: Page) {
  await page.locator('.runs-composer-foot').getByRole('button', { name: 'Reading' }).click()
  await expect(page.locator('.run-readings').first()).toBeVisible()
}

/** The state most of this file's cases start from: the dialog open on box 9's reading, one
 *  press from the free preflight. This is what `openPanel` used to mean before the panel
 *  became a dialog — a scoped screen with `Check cost` on it. */
async function atReading(page: Page, box = 9) {
  await openComposer(page)
  await pickBox(page, box)
  await toReading(page)
}

/** The free preflight — step one of the two-press money gate. */
async function checkCost(page: Page) {
  await page.getByRole('button', { name: /^Check cost/ }).click()
  await expect(page.locator('.run-quote')).toBeVisible()
}

/** Opens the first run in the list and waits for its detail panel. */
async function openRun(page: Page) {
  await page.locator('.run-row').first().click()
  await expect(page.locator('.runs-detail-panel')).toBeVisible()
}

/** Opens the Join step's options well, where the routing lever and the export scope live.
 *
 *  BEHIND A PRESS BY THE OWNER'S RULING for this rebuild — "disclosures stay collapsed,
 *  including the Runs scope options that hold a refusal". So the cases below press it rather
 *  than asserting it should not be there. */
async function openJoinOptions(page: Page) {
  await page.getByRole('button', { name: 'Options' }).click()
  await expect(page.locator('.runs-options')).toBeVisible()
}

// -------------------------------------------------------------- present, not disclosed

/* NOTHING HERE MAY REACH THE CAPTURE SERVER, AND THE SHELL'S OWN READ IS NOT THIS SCREEN'S.
   `app/tests/shell.ts` carries the argument; the call has to sit above every hook and every
   case in the file, which is what `make docs-audit`'s `spec seal` row checks. */
sealEveryTest()

test('the panel is open on arrival, with all four commands named and reachable', async ({
  page,
}) => {
  await open(page)

  /* THIS ASSERTION IS THE REVERSE OF THE ONE IT REPLACES, AND THE REVERSAL IS THE OWNER'S.
     It read "the panel is shut on arrival" and argued the trade D33 made: ~250px, reached
     once a box, so drawn open it spends a quarter of the viewport on every arrival.

     The owner overruled it. The counter-argument, now in D33: reached once a box IS every
     box, which is the definition of the primary task rather than an exception to it, and a
     collapsed panel costs five accumulating substeps — scroll, scan, decide, target, wait —
     before the first click of real work.

     WHAT REPLACES THE FOLD'S SAVING HAS BEEN REWRITTEN THREE TIMES AND THIS IS THE THIRD: a
     shared grid ROW with BoxOps, then a COLUMN of its own, and since 2026-08-26 the panel's own
     MEASURE. Given the content column's full width it draws 799px rather than 1461px with a run
     open, because 1024px unwraps its head, its step notes and its free steps — no code change,
     no disclosure, no cap. The column went because its HEIGHT set the grid row that positioned
     the card's copies; `BoxBrowse.css` carries that measurement.

     ASSERTED AS AN ABSENCE, WHICH IS THE ONE FORM NO RELOCATION CAN FALSIFY. `toBeVisible` on a
     control is a claim about this arrangement; `<details>`/`<summary>` at zero is D33's actual
     ruling — nothing is behind a press — and it stays true wherever the panel is put next. */
  /* THE FOLD ARGUMENT IS SETTLED THE OTHER WAY NOW, BY THE OWNER, AND THIS CASE STOPS MAKING
     IT. It used to assert `details, summary` at zero across the panel — "nothing is behind a
     press". The owner's ruling on this rebuild is that the disclosures stay collapsed, the
     Runs scope options included, and they will say so if it proves subpar in use. Asserting
     the absence of a disclosure would be this file overruling that.

     WHAT SURVIVES IS THE HALF THE RULE ACTUALLY PROTECTS: the four commands are named where a
     person arrives, and the press that reaches them is on the screen rather than behind
     anything. That is `CLAUDE.md`'s route-is-not-a-feature test, and it is what the fold
     assertion was ever standing in for. */
  await expect(page.locator('.bn-lede')).toContainText('Identify, join, emit and reconcile')

  const identify = page.locator('.bn-head-actions').getByRole('button', { name: /^Identify/ })
  await expect(identify).toBeVisible()
  await identify.click()
  await expect(page.getByRole('dialog', { name: /Which boxes/ })).toBeVisible()
})

test('a live run is announced where the panel already is', async ({ page }) => {
  await open(page, { live: true })

  /* This used to assert that a live run OPENS the panel — the one thing that opened it
     without being asked. With nothing to open, what survives is the half that mattered: a
     batch takes minutes to hours and the operator did not necessarily start it in this tab
     (D13 puts one truth on one Mac, so a run started from a terminal is this screen's
     business too), and the screen has to say so on arrival. */
  await expect(page.locator('.run-list-head')).toContainText('1 running')
  /* AND ON THE RUN ITSELF, not only in the list's tally: `RunsStage.stageOf` gives a live run
     a pill of its own that says how long it has been going. The class it used to be found by
     was named after the phase; the pill is found by what it says, which is the thing an
     operator reads. */
  await expect(page.locator('.run-row .runs-pill-live').first()).toContainText('Running')
})

// ------------------------------------------------------------------- reachable at all

test('the pipeline is on its own screen, with all four steps named', async ({ page }) => {
  await open(page)

  /* THE ASSERTION THE HARD RULE ASKS FOR. Four commands have existed since step 4; this is the
     first thing in the repo that says a person can reach them. */
  await expect(page.locator('.bn-head-actions').getByRole('button', { name: /^Identify/ })).toBeVisible()

  /* THE FOUR STEPS BELONG TO A RUN NOW, AND THE SCREEN IS MASTER-DETAIL, so they are drawn
     against the run they would act on rather than standing empty beside a list. The old form
     of this case asserted the four titles on ARRIVAL; the property under it — that an operator
     can see the pipeline has four parts, and that a step's controls do not exist until there
     is something for them to act on — is asserted in both states instead, here and in the case
     below for a store with no runs at all. */
  await expect(page.getByRole('button', { name: 'Preview' })).toHaveCount(0)
  await expect(page.locator('.runs-detail-empty')).toContainText('Pick a run')

  await openRun(page)
  /* COUNTED BEFORE IT IS READ. `allInnerTexts` auto-waits for nothing, so read against a panel
     that has only just mounted it answers `[]` and the failure reads as four missing steps. */
  await expect(page.locator('.run-step-title')).toHaveCount(4)
  const titles = await page.locator('.run-step-title').allInnerTexts()
  expect(titles).toEqual(['Identify', 'Join', 'Emit', 'Reconcile'])
  await expect(page.getByRole('button', { name: 'Preview' })).toHaveCount(1)
})

test('the four steps are named before any run exists', async ({ page }) => {
  /* THE STATE THE OLD ARRANGEMENT COULD NOT DRAW AT ALL. With no runs on disk, join, emit and
     reconcile were not merely un-pressable — they were absent from the document, so a first-time
     operator could not learn the pipeline had four parts until after they had paid for one.

     RE-POINTED AT THE WORDS RATHER THAN AT FOUR STEP CARDS, because that is where the four
     names live in this arrangement: the page's lede and the empty detail both name them, and
     the empty detail also says which of them has to happen first. A screen that stopped naming
     them fails this exactly as it failed the old form. */
  await open(page, { runs: [] })

  await expect(page.locator('.run-empty')).toContainText('No runs yet')
  await expect(page.locator('.bn-lede')).toContainText('Identify, join, emit and reconcile')
  const empty = page.locator('.runs-detail-empty')
  await expect(empty).toContainText('Identify a box first')
  await expect(empty).toContainText('Join, emit and reconcile')
})

test('which steps cost money is on the heading line, not buried in the prose', async ({
  page,
}) => {
  await open(page)
  await openRun(page)

  /* AND THE FIGURE IS THE LABEL, which is this case's amendment rather than a second assertion
     beside it. docs/DESIGN.md's register — "money moments are deliberate and carry the figure in
     the label" — was satisfied by `Costs money` only for as long as there was no figure to
     carry. The fixture's run is a collected, recorded one, so there is. */
  await expect(page.locator('.run-step-money')).toHaveText('Cost $0.15')

  /* `allTextContents` and not `allInnerTexts`: the stylesheet uppercases these labels, and
     `innerText` returns what is PAINTED while `textContent` returns what is written. The
     authored string is the claim worth asserting — a casing rule is a design choice this file
     has no business freezing, and `toHaveText` above reads textContent for the same reason. */
  await expect(page.locator('.runs-step .runs-step-cost')).toHaveCount(4)
  const costs = await page.locator('.runs-step .runs-step-cost').allTextContents()
  expect(costs).toEqual([
    'Cost $0.15',
    'Free · re-runnable',
    'Free · re-runnable',
    'Free · re-runnable',
  ])
})

/* THE MONEY PILL SETTLES, AND UNTIL 2026-09-11 IT NEVER DID.
 *
 * `Costs money` was hardcoded on the Identify step in every state, which is a warning about a
 * decision this screen does not offer: a run directory exists only because the spend route
 * already spawned a child (D33 — the preflight creates none), so the money on this card is
 * always already spent, in flight, or dead in the water. The owner read it on a FINISHED run
 * beside `290,470 tokens in · 3,761 out` and no dollar figure at all, while the console inside
 * the same card said `estimated cost $0.14`. The run cost $0.15 and had finished four minutes
 * earlier.
 *
 * ONE CASE PER STATE, AND NOT ONE CASE WITH FOUR `open()` CALLS IN IT. Every route in this file
 * is registered inside `open`, and a second call would register a competing handler that
 * Playwright resolves in reverse order — the exact trap `open`'s own `detail` option exists to
 * keep a test out of.
 *
 * OBSERVED FAILING FIRST. Four mutations of `RunPanel.tsx`, all red:
 *
 *   the pill reverts to a hardcoded `Costs money`   3 red — and NOT the fourth case below,
 *                                                     which is the one that expects it
 *   the body figure dropped                         1 red, the beside-the-tokens case
 *   the live state loses its tone                   1 red, the in-flight case
 *   `Already paid` falls back to the warning        1 red, the predates-the-figure case
 */

test('the cost is beside the tokens too, which is where a phone still sees it', async ({
  page,
}) => {
  await open(page)
  await openRun(page)

  /* THE IDENTIFY STEP HAS TO BE OPENED FIRST, and which one is open is derived rather than
     fixed: `setOpenStep(COMMANDS[min(stageOf(detail).step, 3)])`, so the fixture's `phase:
     'join'` opens JOIN and the identify body is not in the document at all. A test that read
     `.runs-kv-row` without this click was asserting against an element that had never been
     rendered — which is the shape that makes a new sweep go green for the wrong reason. */
  await page.locator('.runs-step').first().locator('.runs-step-head').click()

  /* NOT A DUPLICATE OF THE PILL — the narrow-width copy of it. `.runs-step-cost` is
     `display: none` below a 640px container (RunPanel.css), and the same rule drops the head
     from four grid columns to three, so the head's figure is gone on a phone and this row is
     what remains. */
  const row = page.locator('.runs-step').first().locator('.runs-kv-row')
  await expect(row).toContainText('290,470 tokens in · 3,761 out')
  await expect(row).toContainText('Cost $0.15')
})

test('a run still in flight says the money is moving, in the live register', async ({ page }) => {
  /* `live` ON THE LIST ROW IS NOT ENOUGH — the steps are drawn against the DETAIL, so this
     passes `detail` rather than the `live` option, which is a different fixture. */
  await open(page, {
    detail: { live: true, pid: 999, phase: 'identifying', collected: false, usage: {} },
  })
  await openRun(page)
  await expect(page.locator('.run-step-money')).toHaveText('Spending now')
  await expect(page.locator('.run-step-money')).toHaveClass(/bn-pill-live/)
})

test('a run that predates the recorded figure does not warn about money already spent', async ({
  page,
}) => {
  /* THE STATE EVERY RUN ON THE OWNER'S MACHINE WAS IN: collected, with no usable `usage` block.
     The server fills the figure in from the token counts where it has them (`_usage`) and
     cannot where it does not — and a finished run with nothing to report must still not claim
     the spend is ahead of it. */
  await open(page, { detail: { usage: {} } })
  await openRun(page)
  await expect(page.locator('.run-step-money')).toHaveText('Already paid')
  await expect(page.locator('.run-step-money')).not.toHaveClass(/bn-pill-warn/)
})

test('the warning survives for the one state that has not spent anything', async ({ page }) => {
  /* A CHILD THAT DIED BEFORE IT SUBMITTED — `phase: 'ready'` is a manifest with no batch ids
     (server/pipeline_routes.py:_phase) — is the only state this card can be drawn in where
     nothing has been bought. Deleting the warning outright would have been the easy repair and
     the wrong one: the pill is not noise, it was lit in the wrong three states out of four. */
  await open(page, { detail: { collected: false, batch_ids: [], phase: 'ready', usage: {} } })
  await openRun(page)
  await expect(page.locator('.run-step-money')).toHaveText('Costs money')
  await expect(page.locator('.run-step-money')).toHaveClass(/bn-pill-warn/)
})

// --------------------------------------------------------------------------- the reading

/* WHAT THE OPERATOR IS ACTUALLY DECIDING WHEN THEY DECIDE THE CROP.
 *
 * The owner's question was "walk me through how im supposed to understand crop with just this
 * dialog box", and the honest answer was that they could not: the step drew a checkbox reading
 * `Crop to the card` and a number reading `Max edge`, and every other user-visible string in
 * the block was one of those two labels. D32's whole argument — that the two are ONE decision,
 * and that cropping at an unchanged max edge sends MORE pixels rather than fewer — lived in a
 * decision entry and a code comment.
 *
 * These cases assert the repair where it matters: the pair cannot be split, and the sentence
 * is on screen BEFORE the press rather than inside the console the press produces. */

test('the reading is explained before Check cost is pressed, not after', async ({ page }) => {
  await open(page)
  await atReading(page)

  /* Nothing has been pressed, so there is no preflight and no console — and the explanation is
     already there. That ordering is the point: the console's own crop line is a receipt, and a
     receipt arrives after the decision. */
  await expect(page.locator('.run-quote')).toHaveCount(0)

  /* One box, so the three legs share a reading and the sentence is said once for the cart
     rather than once per row — the sentence is the same either way, and it is the sentence
     that is under test. */
  const says = page.locator('.runs-reading-says')
  await expect(says).toContainText('Crops to the card')
  await expect(says).toContainText('never touched')
  /* The measurement, in the house voice: box 2's own figure rather than an asserted rule. */
  await expect(says).toContainText('$0.62')
})

test('each reading sends the pair it names, never half of one', async ({ page }) => {
  const wire = await open(page)
  await atReading(page)

  /* THE FAILURE THIS FORBIDS is the one D32 says it got wrong in public first: a crop at an
     unchanged 1568, which costs 26% MORE for asking for less. A preset sets both values or it
     is not a preset, so the assertion reads both out of one body. */
  await page.getByRole('button', { name: /^Cheapest/ }).click()
  await checkCost(page)

  const cheap = wire.filter((row) => row.path === '/pipeline/preflight').pop()
  expect(cheap?.body).toMatchObject({ scopes: [{ crop: true, max_edge: 900 }] })

  await backToReading(page)
  await page.getByRole('button', { name: /^Whole frame/ }).click()
  await checkCost(page)

  const whole = wire.filter((row) => row.path === '/pipeline/preflight').pop()
  expect(whole?.body).toMatchObject({ scopes: [{ crop: false, max_edge: 1568 }] })
})

test('the crop is drawn before it is paid for, and the cut is where the route put it', async ({
  page,
}) => {
  await open(page)
  await atReading(page)

  /* D32's amendment answered "walk me through how im supposed to understand crop with just
     this dialog box" with three named pairs and a sentence each. The sentences are prose about
     pixels; this is the same answer as a picture, and it has to be on screen while the pair is
     being CHOSEN — which is why it is asserted beside the chips rather than beside a run. */
  await expect(page.locator('.run-preview-card')).toHaveCount(1)
  await expect(page.locator('.run-preview-cut')).toHaveCount(1)

  /* THE OVERLAY IS THE ROUTE'S RECTANGLE, MAPPED — not decoration. 216 of 2160 is 10% and
     1728 of 2160 is 80%, so reading the style back out asserts the arithmetic that makes the
     picture true rather than that a blue box exists. */
  const cut = page.locator('.run-preview-cut')
  await expect(cut).toHaveAttribute('style', /left:\s*10%/)
  await expect(cut).toHaveAttribute('style', /width:\s*80%/)

  /* THE PICTURE IS THE PAYLOAD, WHICH IS THE HALF THAT MAKES ANY OF IT VISIBLE. The frame
     drew the stored photograph until 2026-08-29 — the same bytes at every reading, so the one
     thing being changed was the one thing it could not show. */
  const sent = page.locator('.run-preview-sent')
  await expect(sent).toHaveAttribute('src', /crop-1200$/)

  /* AND THE 1:1 WINDOW READS THE SAME FILE, which is why the two can never disagree about
     what is being sent: there is no second file to disagree with. */
  const detail = page.locator('.run-preview-detail')
  await expect(detail).toHaveAttribute('style', /crop-1200/)
  await expect(page.locator('.run-preview')).toContainText('1:1')
})

test('the picture follows the reading, and a whole-frame run draws no cut at all', async ({
  page,
}) => {
  const wire = await open(page)
  await atReading(page)
  await expect(page.locator('.run-preview-cut')).toHaveCount(1)

  /* ASSERTED AS AN ABSENCE, the same shape as the spend button's own case. A picture that kept
     drawing a rectangle after `Whole frame` was chosen would be a picture of a send that is
     not the one about to happen — D32's stale-estimate defect, in the medium the operator
     actually believes. */
  await page.getByRole('button', { name: /^Whole frame/ }).click()
  await expect(page.locator('.run-preview-cut')).toHaveCount(0)
  await expect(page.locator('.run-preview-card')).toHaveCount(1)

  const whole = wire.filter((row) => row.path === '/pipeline/crop-preview').pop()
  expect(whole?.body).toMatchObject({ crop: false, max_edge: 1568 })

  await page.getByRole('button', { name: /^Cheapest/ }).click()
  await expect(page.locator('.run-preview-cut')).toHaveCount(1)
  const cheap = wire.filter((row) => row.path === '/pipeline/crop-preview').pop()
  expect(cheap?.body).toMatchObject({ crop: true, max_edge: 900 })

  /* THE PICTURE ITSELF CHANGED, not just the figures under it. This is the assertion the
     owner's report earns: "the crop preview should also show the depixelation reflected as
     you change the options". */
  await expect(page.locator('.run-preview-sent')).toHaveAttribute('src', /crop-900$/)
})

test('arrow keys walk the box, and a text field keeps its own caret keys', async ({ page }) => {
  const wire = await open(page)
  await atReading(page)
  await expect(page.locator('.run-preview-count')).toContainText('card 1 of 543')

  await page.keyboard.press('ArrowRight')
  await expect(page.locator('.run-preview-count')).toContainText('card 2 of 543')
  expect(wire.filter((row) => row.path === '/pipeline/crop-preview').pop()?.body).toMatchObject({
    offset: 1,
  })

  /* THE GUARD IS THE HALF WORTH ASSERTING. This panel holds a number input, and an unguarded
     window listener would steal the caret keys from it — the operator would be unable to move
     through a value they were editing. Reveal `Custom`, put the caret in its number field, and
     the walk must not move.

     WAITED FOR RATHER THAN ASSERTED IMMEDIATELY, and the first draft of this case got that
     wrong in a way worth recording: `toContainText` passes the instant the text matches, so
     "still card 2" was true a millisecond after the keypress whatever the guard did — the
     fetch is debounced at 140ms. The case passed against a build with the guard deleted. It
     waits past the debounce now, and then asserts BOTH the caption and the wire, because the
     wire is the half that cannot be true by accident. */
  await page.getByRole('button', { name: 'Custom' }).click()
  const edge = page.getByRole('spinbutton', { name: 'Max edge' })
  await edge.click()
  const before = wire.filter((row) => row.path === '/pipeline/crop-preview').length
  await page.keyboard.press('ArrowRight')
  await page.waitForTimeout(500)
  await expect(page.locator('.run-preview-count')).toContainText('card 2 of 543')
  expect(wire.filter((row) => row.path === '/pipeline/crop-preview').length).toBe(before)
})

test('a game that claims no number band gets the cut and a reason, never a wrong strip', async ({
  page,
}) => {
  /* THE DEFECT THIS ROUTE SHIPPED WITH, found by the owner on box 1. It cut `geometry/crop.py`'s
     number band over every game, and `pipeline/games.py` refuses that in writing — the bands are
     fractions measured on a Pokemon card. The strip drew a Riftbound card's RULES TEXT as though
     it were a collector number. */
  await open(page, { previewGame: 'riftbound' })
  await atReading(page)

  /* THE FACT, NOT THE SERVER'S SENTENCE. The route answers with a paragraph naming
     `pipeline/games.py` and `geometry/crop.py`; the screen says the thing that is true about
     the card in front of the operator and what to do about it, which is this rebuild's rule
     for a raw string with a person on the other end. The refusal is still stated. */
  await expect(page.locator('.run-preview')).toContainText('No number band on this game')
  await expect(page.locator('.run-preview')).toContainText('point at the card')

  /* AND THE 1:1 VIEW STILL WORKS. The registry cannot say where a Riftbound card prints its
     identifier and it does not have to — the operator points at it. A refusal that took the
     magnifier away with it would have made this game strictly worse off than before. */
  await expect(page.locator('.run-preview-detail')).toHaveCount(1)

  /* AND THE CUT IS UNAFFECTED. A card is 63x88mm whatever is printed on it, so the crop is
     right for every game even where no band has ever been measured. */
  await expect(page.locator('.run-preview-cut')).toHaveCount(1)
})

test('the raw controls are behind Custom, and that is where the mistake is named', async ({
  page,
}) => {
  await open(page)
  await atReading(page)

  const box = page.getByRole('checkbox', { name: 'Crop to the card' })
  await expect(box).toHaveCount(0)

  await page.getByRole('button', { name: 'Custom' }).click()
  await expect(box).toBeVisible()
  await expect(page.getByRole('spinbutton', { name: 'Max edge' })).toBeVisible()

  /* DEMOTED, NOT DELETED — every pairing the three chips refuse to offer is reachable here,
     including the wrong one, so the sentence that replaces them has to name it. The wrong
     pairing is named by its measurement rather than by a shouted word now, which is the same
     claim: a crop at an unchanged 1568 cost 26% MORE. */
  const says = page.locator('.runs-reading-says')
  await expect(says).toContainText('one decision')
  await expect(says).toContainText('26% more')
})

test('changing the reading voids the estimate, because it changes what would be sent', async ({
  page,
}) => {
  const wire = await open(page)
  await atReading(page)
  await checkCost(page)
  await expect(page.locator('.run-button-money')).toHaveCount(1)

  /* THE MONEY GATE'S OWN RULE, APPLIED TO THE BYTES RATHER THAN TO THE CARDS. `scopeKey` was
     `box:indices` alone, so unticking the crop after Check cost left a stale figure standing
     above a live confirm — an estimate for a send that was no longer the one about to happen.

     RE-POINTED FROM "THE BUTTON GOES" TO "THE COST STAGE CANNOT BE GOT BACK TO", because the
     dialog reaches the confirm through a sequence: the reading is changed on the stage before
     the cost, so the confirm is already off screen while it is being changed and its absence
     there would prove nothing. What has to hold is that the walk back does not carry the old
     figure with it — the Cost stage is not a place the operator can return to, and the confirm
     they eventually press was quoted for the reading now chosen. A dialog that let the stages
     be walked freely over a stale quote fails this. */
  await backToReading(page)
  await page.getByRole('button', { name: /^Cheapest/ }).click()

  await expect(page.locator('.runs-stages').getByRole('button', { name: 'Cost' })).toHaveCount(0)
  await expect(page.locator('.run-button-money')).toHaveCount(0)

  await checkCost(page)
  expect(wire.filter((row) => row.path === '/pipeline/preflight')).toHaveLength(2)
  expect(wire.filter((row) => row.path === '/pipeline/preflight').pop()?.body).toMatchObject({
    scopes: [{ crop: true, max_edge: 900 }],
  })
})

test('the cache line is drawn only where cards are already answered', async ({ page }) => {
  await open(page)
  await atReading(page)
  await checkCost(page)

  /* D32's known cache gap, said as what it means rather than as a fact about a hash: the crop
     and the max edge are not part of the cache identity, so a box re-read at a different
     reading serves the answers it was first read with and reports them as hits. */
  await expect(page.locator('.run-quote .run-step-fine')).toContainText(
    'keep the answer they were first read with',
  )
})

test('nothing was cached, so the cache line says nothing', async ({ page }) => {
  await open(page, { cacheHits: 0 })
  await atReading(page)
  await checkCost(page)

  /* THE NEGATIVE HALF, and it is the half worth having. A sentence about answers that already
     exist, drawn over a box where none do, is a warning that trains the operator to skip it. */
  await expect(page.locator('.run-quote .run-step-fine')).toHaveCount(0)
})

// ------------------------------------------------------------------------- the money gate

test('the control that spends does not exist until the free preflight has answered', async ({
  page,
}) => {
  await open(page)
  await atReading(page)

  /* ABSENT, NOT DISABLED. A disabled button is one attribute away from being pressable, and
     that attribute is exactly what a later refactor drops without noticing. */
  await expect(page.locator('.run-button-money')).toHaveCount(0)

  await checkCost(page)
  await expect(page.locator('.run-button-money')).toHaveCount(1)
})

test('the estimate and the card count are on screen before the confirm is', async ({ page }) => {
  await open(page)
  await atReading(page)
  await checkCost(page)

  /* The numbers are the COMMAND'S, lifted out of its own preflight stdout — so this asserts
     the parse as well as the render. A panel that recomputed them could show a figure the log
     disagrees with, and the operator would have no way to tell which had drifted. The four
     used to be a definition list; they are the money figure and the line under it now, and
     every one of them is still on screen before the confirm is. */
  await expect(page.locator('.runs-quote-money')).toHaveText('$0.42')
  const line = page.locator('.runs-quote-line')
  await expect(line).toContainText('36 cards')
  await expect(line).toContainText('4 already answered')
  await expect(line).toContainText('40 photographs')

  /* And the command's own words, verbatim — docs/DESIGN.md's copy rule for the owner's
     screens. Behind a press since the rebuild, which the owner ruled on: the disclosures stay
     collapsed. What this asserts is that it is REACHABLE and unedited, which is the half D33
     was ever about. */
  await page.getByRole('button', { name: 'What the preflight printed' }).click()
  await expect(page.locator('.run-console').first()).toContainText('estimated cost  $0.42')

  const confirm = page.locator('.run-button-money')
  await expect(confirm).toContainText('$0.42')
  await expect(confirm).toContainText('36')
})

test('the confirm sends confirm:true and the cart the picker is showing', async ({ page }) => {
  const wire = await open(page)
  await atReading(page)
  await checkCost(page)
  await page.locator('.run-button-money').click()
  /* The cost stage is left behind by the press, and what replaces it is the receipt. */
  await expect(page.locator('.run-quote')).toHaveCount(0)
  await expect(page.locator('.runs-receipt')).toBeVisible()

  const spend = wire.find((row) => row.path === '/pipeline/identify')
  expect(spend).toBeTruthy()
  const body = spend?.body as { confirm?: unknown; scopes?: Record<string, unknown>[] }
  expect(body.confirm).toBe(true)
  /* ONE ROUTE, ONE CONFIRM, ONE CART — D48. A single box is a cart of ONE rather than a
     different request shape, which is what keeps the money behind one door with one refusal
     path instead of two. */
  expect(body.scopes).toHaveLength(1)
  expect(body.scopes?.[0]).toMatchObject({ box: 9 })
  /* No ticked cards, so the run is the whole box and `indices` is absent — which the route
     reads as the whole box. An empty ARRAY would be refused there, deliberately, and the
     screen must never send one. */
  expect(body.scopes?.[0]?.indices).toBeUndefined()
})

test('the estimate is spent by the confirm, so a second run needs a second preflight', async ({
  page,
}) => {
  await open(page)
  await atReading(page)
  await checkCost(page)
  await page.locator('.run-button-money').click()

  /* The quote is cleared on success rather than left standing. Without this, pressing the
     confirm twice would start two runs on one estimate — and the second would be a second
     invoice for a number the operator only agreed to once. */
  await expect(page.locator('.run-button-money')).toHaveCount(0)
  await expect(page.locator('.runs-composer-foot')).toContainText('The quote is spent')
})

test('nothing to send draws no confirm at all, and says why', async ({ page }) => {
  await open(page, { toSend: 0, estimate: 0 })
  await atReading(page)
  await checkCost(page)

  await expect(page.locator('.run-button-money')).toHaveCount(0)
  const quote = page.locator('.run-quote')
  await expect(quote).toContainText('Nothing to send')
  await expect(quote).toContainText('nothing to spend')
})

test('a live run over the same cards blocks the confirm rather than racing it', async ({
  page,
}) => {
  await open(page, { busyRun: '2026-08-24-box9-01' })
  await atReading(page)
  await checkCost(page)

  /* Two live batches over one box is two invoices for one answer. The route refuses it as
     `run_already_live`; the screen refuses to draw the button, so the operator never presses
     something that is going to fail. */
  await expect(page.locator('.run-button-money')).toHaveCount(0)
  /* IT NAMES THE BOX, because a cart can carry several and "these cards" would not say which
     of them is blocked. The run name is on the line for the same reason it always was: the
     answer is to open that run, and a refusal that does not name it is a dead end. */
  const quote = page.locator('.run-quote')
  await expect(quote).toContainText('Box 9 is already being identified')
  await expect(quote).toContainText('2026-08-24-box9-01')
})

// ------------------------------------------------------------------------- the free steps

test('join offers a preview that writes nothing', async ({ page }) => {
  const wire = await open(page)
  await openRun(page)


  /* THE TRUST SWITCH IS GONE, ASSERTED AS AN ABSENCE. "Trust my finish claim over the photo"
     was a checkbox here until D3's amendment of 2026-09-02 made its rule the ladder's own;
     a body carrying `bypass` again would mean the choice had come back. */
  await expect(
    page.getByRole('checkbox', { name: 'Trust my finish claim over the photo' }),
  ).toHaveCount(0)

  /* THE TRUST SWITCH IS GONE AND SO IS THE HALF OF THIS CASE THAT PRESSED IT. The finish-claim
     bypass was deleted from the screen on the owner's ruling for this rebuild, and `bypass` is
     no longer sent from anywhere in `app/src`. Asserting it here would be asserting a control
     the owner removed; asserting its absence would be a claim about a control rather than
     about behaviour. What is left is the property the case was named for. */
  await page.getByRole('button', { name: 'Preview' }).click()
  const join = wire.find((row) => row.path.endsWith('/join'))
  const body = join?.body as Record<string, unknown>
  expect(body.dry_run).toBe(true)
  expect(body.bypass).toBeUndefined()
})

test('this run\'s own receipts download here; the import CSVs do not', async ({ page }) => {
  await open(page)
  await openRun(page)

  /* THE FILES WRITTEN BY THE COMMANDS PRESSED ON THIS SCREEN. `report.txt` and
     `pricing.json` come from join, `reconcile.txt` from reconcile — each one screen-inch
     from the button that produced it, which is docs/GATES.md's gap answered for the half of
     the artefacts that stayed. */
  const file = page.locator('.run-file').filter({ hasText: 'reconcile.txt' })
  await expect(file).toBeVisible()
  await expect(file).toHaveAttribute('download', 'reconcile.txt')
  expect(await file.getAttribute('href')).toContain('/pipeline/runs/')

  /* AND THE IMPORT CSVs ARE NOT HERE, ASSERTED AS AN ABSENCE (D54). They went to
     `#/pricing` with the press that writes them; `app/tests/pricing.spec.ts` carries the
     Gate B case verbatim at its new address. A deliberate removal that a later edit must
     not quietly undo — which is what an absence is for, and why this is not a weakening of
     the case it replaces. */
  await expect(page.locator('.run-file-import')).toHaveCount(0)
})

/* THE BYPASSED-RUN CASE IS DELETED WITH THE FEATURE IT COVERED. It asserted `.run-flagged`
   reading "209 cards resolved by your finish claim" on a run started with the finish-claim
   bypass; the owner deleted the bypass control from this rebuild, nothing in `app/src` sends
   `bypass` any more, and no screen draws the count. Rewriting it to assert something else
   would have been a case about a feature this branch does not have. */

// ------------------------------------------------------------- which drawer a run was over

test('a run row names the drawer, and takes the name from the server', async ({ page }) => {
  await open(page, {
    runs: [
      runRow({ run: '2026-08-24-box12-01', box: 12, box_name: 'codes', phase: 'emit' }),
      runRow(),
    ],
  })

  /* D56. The list drew `box 9` — a digit, on a screen whose whole question is which box you
     are about to spend money on. The name comes off `GET /pipeline/runs`, joined against the
     registry at read time, so it is current rather than whatever the manifest happened to
     record; the number stays beside it because the number is the shelf and the directory the
     photographs are in.

     BOTH ARMS, and the second one is the assertion that matters: an unnamed box draws the
     number ALONE. D20 leaves a name optional, so `Box 9 · —` would draw a fault where there
     is none. */
  const rowScope = (run: string) =>
    page.locator('.run-row').filter({ hasText: run }).locator('.run-row-scope')

  /* SELECTED BY RUN NAME AND NOT BY INDEX, because this list is PARTITIONED: box 9 is the
     picked box, so its run sorts above box 12's whatever order the server sent them in. An
     index here would be asserting the grouping by accident and would move the day either
     fixture's box changed. */
  await expect(rowScope('2026-08-24-box12-01')).toHaveText('Box 12 · codes')
  await expect(rowScope('2026-08-24-box9-01')).toHaveText('Box 9')
})

test('a run over a deleted drawer says so, and the drawer on the shelf does not', async ({
  page,
}) => {
  /* D145. THE OWNER'S REPORT: *"i deleted an old box 1, started writing into a new
     box (now new box 1) and if i go on say my runs tab it shows that i'd run a 'Box 1' run a
     long time ago etc. it's confusing."*

     The store could already tell — D36 refuses the join and D56 withholds the name, both on
     `box_disowns_run` — and withholding a name is not a sentence: the departed drawer drew
     `Box 1`, which on this screen is indistinguishable from a live box nobody named. The
     server decides it (`box_former`, off the run's own `box_bid` where it has one) and this is
     the half a person reads.

     BOTH ROWS, AND THE SECOND IS THE ONE THAT WOULD HAVE CAUGHT A BLUNT FIX. Marking every run
     over a reused number would have traded one confusing row for two; the drawer on the shelf
     is an ordinary row with an ordinary name.

     THE NUMBER SURVIVES THE MARKER. `Box 1 (deleted)` and never a bare id: the number is the
     run directory's own name, the directory its photographs are in, and what every refusal in
     `server/pipeline_routes.py` names — D56's argument for carrying both halves. And the TRUE
     INDEX is drawn nowhere, which is the owner's ruling in their own words: *"an index # not
     visible anywhere in the app"*. */
  await open(page, {
    runs: [
      runRow({
        run: '2026-08-22-box1-03',
        box: 1,
        box_bid: 1,
        box_former: true,
        box_name: 'Pokemon shakedown',
      }),
      runRow({ run: '2026-08-29-box1-01', box: 1, box_bid: 2, box_former: false, box_name: 'RB Epics' }),
    ],
  })

  const rowScope = (run: string) =>
    page.locator('.run-row').filter({ hasText: run }).locator('.run-row-scope')

  await expect(rowScope('2026-08-22-box1-03')).toHaveText('Box 1 (deleted) · Pokemon shakedown')
  await expect(rowScope('2026-08-29-box1-01')).toHaveText('Box 1 · RB Epics')

  /* AND THE TRUE INDEX IS DRAWN NOWHERE. `toHaveText` is exact, so these two assertions ARE
     that proof for this row: both runs carry a `box_bid` and neither label contains it. A
     separate sweep over the page for the word would pass whether or not the id were rendered
     as a bare number, which is the shape it would actually take. */
})

test('a run that predates the true index is still marked, and has no name to recover', async ({
  page,
}) => {
  /* THE ARM THE OWNER'S OWN MACHINE TAKES, and it needs its own `test` rather than a second
     `open` inside the one above: `open` re-stubs the wire, and the list the first fixture
     already painted is what `.first()` would read. That is the click-then-mutate race
     docs/DEBTS.md section 23 names, one register up — and it cost this case a red on its first
     run, which is the guard working.

     Every run on the owner's machine predates `box_bid`, so the server answers by the older
     rule (`box_disowns_run`, D36/D56). It can say THAT the drawer departed and not WHICH, so
     there is no name to recover — and `(deleted)` alone is already the whole of what the
     complaint asked for. A placeholder in the name's place would draw a fault where there is
     none (D56). */
  await open(page, {
    runs: [runRow({ run: '2026-08-22-box1-03', box: 1, box_bid: null, box_former: true, box_name: null })],
  })

  await expect(page.locator('.run-row-scope').first()).toHaveText('Box 1 (deleted)')
})

test('a run predating the box field still finds its box, and is grouped by it', async ({
  page,
}) => {
  /* THE FALLBACK, WHICH IS NOT DEAD CODE: `_summary` sends `box` today, and this payload is
     CAST rather than validated, so a client talking to a server that predates the field must
     not silently lose which box every run was over. Two of the four runs on the owner's own
     machine carry no `scope` block either — `identify captures/cards/box3` writes none — so
     the capture-directory derivation is the only thing that can place them.

     GROUPING IS WHAT THIS ACTUALLY GUARDS. `boxOf` decides which runs are filed under the box
     in the cart, and a null there would push a run about the box you are standing in down into
     `Other boxes`. The old form asserted the ABSENCE of a caption, which said what it meant
     while an unscoped list drew no groups at all; it does not any more — the list is ungrouped
     until there IS a cart, so an absence there would now pass whatever `boxOf` returned. So
     the box is put in the cart and the caption is read: this run belongs to the picked box. */
  await open(page, {
    runs: [runRow({ box: undefined, box_name: undefined, scope: null })],
  })

  await expect(page.locator('.run-row-scope').first()).toHaveText('Box 9')

  await openComposer(page)
  await pickBox(page, 9)
  await page.keyboard.press('Escape')
  await expect(page.locator('.runs-composer')).toHaveCount(0)

  await expect(page.locator('.run-group')).toHaveText(/Picked boxes/)
})

// -------------------------------------------------------------------------- the cart
//
// D48. A SEND IS A CART OF BOXES AND A RUN IS STILL ONE BOX. The owner asked to multi-select
// and send together, and asked for the boxes to be "individualized" — so the request carries
// several scopes, each with its own reading, and the route spawns one child per box. What
// these cases hold is that the screen sends what it drew, that the confirm is gated on the
// TOTAL rather than on a leg, and that a partial send is visible.

test('several boxes are one cart, one estimate and one confirm', async ({ page }) => {
  const wire = await open(page)
  await openComposer(page)
  await pickBox(page, 9)
  await pickBox(page, 12)
  await toReading(page)

  /* TWO ROWS, ONE PER BOX, EACH WITH ITS OWN READING PICKER. The strip decides WHICH boxes and
     the cart decides how each is read — the reading is part of what the confirm is agreeing to
     buy, because the estimate is computed from the bytes each card is sent as. */
  await expect(page.locator('.run-leg')).toHaveCount(2)
  /* THE DRAWER BY NAME ON THE ROW THAT DECIDES WHAT READING IT COSTS (D56). Until then this
     row could only call a box by its digit, on the one screen in the product that spends —
     and the name is what the operator recognises the drawer by. Both arms are asserted here
     because the fixture carries one of each: an unnamed box draws the number ALONE, with no
     separator and no placeholder, since D20 makes a name optional rather than expected. */
  await expect(page.locator('.run-leg-box').first()).toHaveText('Box 9')
  await expect(page.locator('.run-leg-box').nth(1)).toHaveText('Box 12 · codes')
  /* The header behind the dialog carries the same scope, which is what the operator is left
     looking at when the dialog closes. */
  await expect(page.locator('.runs-scope')).toContainText('2 boxes')

  await checkCost(page)

  const asked = wire.filter((row) => row.path === '/pipeline/preflight').pop()
  const body = asked?.body as { scopes?: { box: number }[] }
  expect(body.scopes?.map((leg) => leg.box)).toEqual([9, 12])

  /* THE CONFIRM QUOTES THE TOTAL, NOT A LEG. Two boxes at 36 each is 72 cards and $0.84 — a
     screen that read the first leg and called it the total would say 36 and $0.42 here, which
     is the one number the operator is agreeing to and the one that must not be understated. */
  /* THE PER-BOX BREAKDOWN NAMES THE BOX TOO, and it is a different source from the row above
     it: the preflight answers per leg with a scope block carrying a number and no name, so
     this line is the cart's own name looked up by box. Worth asserting separately for exactly
     that reason — the leg head could be right while this stayed a bare digit. */
  await expect(page.locator('.run-legs dt').nth(1)).toHaveText('Box 12 · codes')

  const confirm = page.locator('.run-button-money')
  await expect(confirm).toContainText('72')
  await expect(confirm).toContainText('$0.84')
  await expect(confirm).toContainText('2 boxes')

  await confirm.click()
  const spend = wire.find((row) => row.path === '/pipeline/identify')
  const sent = spend?.body as { confirm?: unknown; scopes?: { box: number }[] }
  expect(sent.confirm).toBe(true)
  expect(sent.scopes?.map((leg) => leg.box)).toEqual([9, 12])
})

test('each box carries its own reading, and one press sends both', async ({ page }) => {
  const wire = await open(page)
  await openComposer(page)
  await pickBox(page, 9)
  await pickBox(page, 12)
  await toReading(page)

  /* THE WHOLE REASON THIS IS A CART RATHER THAN ONE RUN ACROSS SEVERAL BOXES (D48). Which end
     of D32's measured frontier is right depends on what is IN the drawer, so a box of bulk
     commons and a box worth reading a collector number off must be able to disagree. Scoped
     per row, because `Cheapest` appears once per box and an unscoped locator would be
     ambiguous — which is the ambiguity that proves the control is per box. */
  await page.locator('.run-leg').nth(1).getByRole('button', { name: /^Cheapest/ }).click()
  await checkCost(page)

  const asked = wire.filter((row) => row.path === '/pipeline/preflight').pop()
  const body = asked?.body as { scopes?: { box: number; crop: boolean; max_edge: number }[] }
  expect(body.scopes?.[0]).toMatchObject({ box: 9, crop: true, max_edge: 1200 })
  expect(body.scopes?.[1]).toMatchObject({ box: 12, crop: true, max_edge: 900 })
})

test('adding a box to the cart voids the estimate, exactly as changing a reading does', async ({
  page,
}) => {
  const wire = await open(page)
  await atReading(page)
  await checkCost(page)
  await expect(page.locator('.run-button-money')).toHaveCount(1)

  /* THE MONEY GATE'S RULE, APPLIED TO THE CART. "A confirm whose first step described a
     different set of cards is not a confirm at all" — and a second box is a different set of
     cards by the widest possible margin.

     ASSERTED AS THE CART CASE'S OWN SHAPE: the boxes stage is walked back to, a second box is
     ticked, and the cost stage cannot be returned to — the operator has to buy a new estimate
     for the cards they have now got in the cart, and it is quoted for both boxes. */
  await page.locator('.runs-stages').getByRole('button', { name: 'Boxes' }).click()
  await pickBox(page, 12)
  await expect(page.locator('.runs-stages').getByRole('button', { name: 'Cost' })).toHaveCount(0)
  await expect(page.locator('.run-button-money')).toHaveCount(0)

  await toReading(page)
  await checkCost(page)
  const asked = wire.filter((row) => row.path === '/pipeline/preflight').pop()
  expect((asked?.body as { scopes?: { box: number }[] }).scopes?.map((leg) => leg.box)).toEqual([
    9, 12,
  ])
})

test('a box is untickable, and the last one out leaves nothing to price', async ({ page }) => {
  await open(page)
  await openComposer(page)
  await pickBox(page, 9)
  await pickBox(page, 12)
  await toReading(page)
  await expect(page.locator('.run-leg')).toHaveCount(2)

  await page.locator('.runs-stages').getByRole('button', { name: 'Boxes' }).click()
  await pickBox(page, 12)
  await toReading(page)
  await expect(page.locator('.run-leg')).toHaveCount(1)
  await expect(page.locator('.run-leg-box')).toHaveText('Box 9')

  /* Back to the state the dialog opens in, and the way forward is disabled again rather than
     absent — the one control here that gets to be disabled, because it is free, it is the next
     thing to press, and a control that vanishes until an unrelated press brings it back is a
     screen that looks broken. The COMMITTING control is the one that must be absent, and it is
     two stages away and asserted above. */
  await page.locator('.runs-stages').getByRole('button', { name: 'Boxes' }).click()
  await pickBox(page, 9)
  await expect(page.getByRole('button', { name: /^Next · how they are read$/ })).toBeDisabled()
})

test('a box the send could not start is named, not swallowed', async ({ page }) => {
  await open(page, {
    failed: [{ box: 12, code: 'spawn_failed', message: 'Could not start `pkmnscan identify`' }],
  })
  await openComposer(page)
  await pickBox(page, 9)
  await pickBox(page, 12)
  await toReading(page)
  await checkCost(page)
  await page.locator('.run-button-money').click()

  /* THE ONE FAILURE NO VALIDATION CAN PRE-EMPT (D48). `Popen` can fail on the fourth leg after
     three have started, so the route answers with both halves. A partial send reported as a
     whole one is an invoice nobody can account for; reported honestly it is recoverable by
     pressing again for the box that did not go, which is what the sentence says. */
  const note = page.locator('.runs-composer')
  await expect(note).toContainText('did not start')
  await expect(note).toContainText('spawn_failed')
  await expect(note).toContainText('box 12')
})

// ------------------------------------------------------ the state the old address never had

test('nothing is scoped on arrival, and the free preflight refuses until a box is picked', async ({
  page,
}) => {
  await open(page)

  /* A STATE THAT DID NOT EXIST BEFORE 2026-08-29 AND NOW DOES, which is the honest cost of the
     move and the reason it is asserted rather than mentioned. On `#/inventory` the walk had
     always picked a shelf by the time this panel drew, so `scope.box` was never null in
     practice; on a route of its own the first thing an operator sees is a picker with nothing
     picked.

     `Runs.tsx` REFUSES TO DEFAULT IT, and that is the behaviour under test: a box chosen for
     the operator is a box they did not read, and the next press after it is the one that
     spends money. So the screen says `Pick a box.` and the preflight — free, and the first
     step of the money gate — is not pressable.

     DISABLED RATHER THAN ABSENT, DELIBERATELY, and it is the one control here that gets to be.
     docs/DESIGN.md's absent-not-disabled rule is about the control that COMMITS — the spend
     button, which still does not exist until the preflight has answered, asserted above. This
     one is free, it is the next thing to press, and a control that vanishes until an unrelated
     press elsewhere brings it back is a screen that looks broken.

     THE SENTENCE MOVED INTO THE DIALOG WITH THE PICKER. The header pill says what the scope IS
     and is drawn only once there is one; the dialog's own footer is where the screen asks for
     one, which is the place a person is standing when they need to be asked. */
  await openComposer(page)
  await expect(page.locator('.runs-composer-note')).toContainText('Pick a box.')
  const next = page.getByRole('button', { name: /^Next · how they are read$/ })
  await expect(next).toBeDisabled()
  await expect(page.locator('.runs-scope')).toHaveCount(0)

  // And it is one press away, with the scope said out loud before anything can be spent.
  await pickBox(page)
  await expect(page.locator('.runs-composer-note')).toContainText('Box 9 · the whole box')
  await expect(page.locator('.runs-scope')).toContainText('Box 9 · the whole box')
  await expect(next).toBeEnabled()
})

// ----------------------------------------- the export, fetched rather than downloaded (D64)

/** The control that fetches. A helper because several cases press it. */
function fetchButton(page: Page) {
  return page.getByRole('button', { name: 'Fetch from TCGplayer' })
}

/** A receipt in the shape `POST /pipeline/runs/<name>/export` answers with. */
function fetchedBody(over: Record<string, unknown> = {}) {
  return {
    ok: true,
    run: '2026-08-24-box9-01',
    file: 'export-tcgplayer-20260830-121500-a1b2c3d4.csv',
    bytes: 26192,
    rows: 153,
    skus: 153,
    games: ['riftbound'],
    sets: ['Origins', 'Unleashed'],
    conditions: ['Near Mint', 'Near Mint Foil'],
    product_lines: ['Riftbound League of Legends Trading Card Game'],
    previous: {
      riftbound: { file: 'export-tcgplayer-20260829-100000-9f9f9f9f.csv', rows: 2008, skus: 1900 },
    },
    source: 'https://store.tcgplayer.com/admin/pricing/downloadexportcsv',
    asked: {
      game: 'riftbound',
      category_id: 89,
      hints: ['UNL'],
      set_ids: [24560],
      unresolved_hints: [],
      sets: ['Unleashed'],
      widened: false,
      scope: 'sets',
      policy: 'sets',
      chosen_by: 'cards',
      reason: null,
      cards: 40,
      hinted: 40,
      unhinted: 0,
    },
    ...over,
  }
}

/** Register the fetch route for one case. Not in `open()`: every case here wants a different
 *  answer from it, and registering per case avoids depending on Playwright's precedence
 *  between two patterns that could both match. Pushes into `wire` so an assertion can read
 *  what the screen SENT, which is what the join-by-name case reads. */
async function routeFetch(
  page: Page,
  wire: { method: string; path: string; body: unknown }[],
  answer: { status: number; body: unknown },
) {
  await page.route(/\/pipeline\/runs\/[^/]+\/export$/, async (route) => {
    wire.push({
      method: 'POST',
      path: new URL(route.request().url()).pathname,
      body: route.request().postDataJSON(),
    })
    await route.fulfill({
      status: answer.status,
      contentType: 'application/json',
      body: JSON.stringify(answer.body),
    })
  })
}

test('the export is fetched, and the join is handed the file rather than the bytes', async ({
  page,
}) => {
  const wire = await open(page)
  await routeFetch(page, wire, { status: 200, body: fetchedBody() })
  await openRun(page)

  await fetchButton(page).click()

  /* The receipt names the file, because that name is what the join is then handed and what
     `GET .../file` will serve if the operator wants to read the bytes themselves. */
  await expect(page.locator('.run-receipt')).toContainText(
    'export-tcgplayer-20260830-121500-a1b2c3d4.csv',
  )
  await expect(page.locator('.run-receipt')).toContainText('153')

  /* ONE PRESS IS TWO CALLS, and the join must take the file BY NAME. Sending `exports` here
     would mean the browser had read a megabyte back off the server and posted it again to
     arrive at bytes the server already had. */
  const join = wire.filter((row) => row.path.endsWith('/join')).pop()
  expect(join?.body).toMatchObject({
    fetched: ['export-tcgplayer-20260830-121500-a1b2c3d4.csv'],
  })
  expect((join?.body as { exports?: unknown }).exports).toBeUndefined()
})

/* BOTH "Fetch anyway" CASES ARE GONE WITH THE BUTTON. The export delta guard is retired on
   this branch — `RunPanel.tsx` says so by name — so a fetch no longer asks a question the
   operator has to press past; it answers both acknowledgements up front and draws a receipt.
   The case that asserted the control's absence before a refusal is deleted rather than kept:
   an absence that can no longer be earned is an assertion that cannot fail. What the
   acknowledgement now does instead is asserted on the wire, in the fetch case above, and the
   refusal cases below keep every half of themselves that is still about behaviour. */

test('a refusal says why, in the server\'s own words, and never joins', async ({ page }) => {
  const wire = await open(page)
  await routeFetch(page, wire, {
    status: 409,
    body: {
      error: {
        code: 'export_unverified',
        message:
          'This run has never been joined against a riftbound export, so there is nothing '
          + 'to check this one against.',
      },
    },
  })
  await openRun(page)
  await fetchButton(page).click()

  /* The server's sentence verbatim, which is `docs/DESIGN.md`'s copy rule for owner screens,
     with the machine string beneath it so what was seen can be grepped. */
  await expect(page.locator('.run-result-refused')).toContainText('nothing to check this one')
  await expect(page.locator('.run-result-refused')).toContainText('export_unverified')

  /* A REFUSED FETCH MUST NOT JOIN. It wrote nothing, so joining after one would silently
     re-use the previous export and look exactly like the fetch had worked. */
  expect(wire.filter((row) => row.path.endsWith('/join'))).toHaveLength(0)

  /* AND NO RECEIPT FOR A FETCH THAT DID NOT HAPPEN, which is the other half of the same
     property: the receipt is the evidence the join is about to read. */
  await expect(page.locator('.run-receipt')).toHaveCount(0)
})

test('a refusal an operator cannot answer draws a sentence and nothing to press', async ({
  page,
}) => {
  const wire = await open(page)
  await routeFetch(page, wire, {
    status: 502,
    body: {
      error: {
        code: 'tcg_session_expired',
        message:
          'TCGplayer redirected the download to its login page, which means the session in '
          + 'TCGPLAYER_STORE_COOKIE has expired.',
      },
    },
  })
  await openRun(page)
  await fetchButton(page).click()

  await expect(page.locator('.run-result-refused')).toContainText('has expired')
  await expect(page.locator('.run-result-refused')).toContainText('tcg_session_expired')

  /* An expired session, a WAF block and an export for the wrong product line are all fixed
     somewhere other than this screen, so there is nothing here to press past it — and, as
     above, no receipt for an export that never arrived. */
  expect(wire.filter((row) => row.path.endsWith('/join'))).toHaveLength(0)
  await expect(page.locator('.run-receipt')).toHaveCount(0)
})


/* PORTED FROM MAIN, AGAINST THIS BRANCH'S RECEIPT. D64's delta guard is retired on both
   branches — a fetch no longer asks a question the operator has to press past — and what the
   guard used to compare is drawn as a receipt instead. Main asserted it against `.run-fetched`
   and raw digits; this branch draws it in `.run-receipt-was` and formats row counts with
   `toLocaleString`, so the figures carry a separator. The FILE NAME is asserted because the
   owner's ruling was that the receipt NAMES the previous export: a figure with no file beside
   it says a number changed and not which export to go and look at. */
test('the receipt says what the last export held beside what this one holds', async ({
  page,
}) => {
  const wire = await open(page)
  await openRun(page)
  await routeFetch(page, wire, { status: 200, body: fetchedBody() })
  await fetchButton(page).click()

  const was = page.locator('.run-receipt-was')
  await expect(was).toContainText('2,008')
  await expect(was).toContainText('1,900')
  await expect(was).toContainText('153')
  await expect(was).toContainText('export-tcgplayer-20260829-100000-9f9f9f9f.csv')
  /* AND THERE IS NOTHING TO PRESS. Nothing refused, so the receipt carries no control — the
     absence is the whole of what the retirement bought. */
  await expect(page.locator('.run-receipt-said button')).toHaveCount(0)
})

test('a first fetch says there is nothing earlier to set beside it', async ({ page }) => {
  const wire = await open(page)
  await openRun(page)
  await routeFetch(page, wire, { status: 200, body: fetchedBody({ previous: {} }) })
  await fetchButton(page).click()

  /* A run directory is new per run, so every run's first fetch has no previous export. That
     used to be `export_unverified`, a refusal the operator answered with a press and a second
     download of the same file; it is a sentence on the receipt now. */
  await expect(page.locator('.run-receipt-was')).toContainText('The first export this run has fetched')
  await expect(page.locator('.run-result-refused')).toHaveCount(0)
})

/* EVERY FETCH REFUSAL IS A SENTENCE WITH NOTHING TO PRESS. An expired session is fixed in
 * `.env`; a set that was asked for and did not arrive is fixed in the capture claims or the
 * registry. Neither is fixed on this screen, so a button here would be offering to wave
 * through a refusal the screen does not understand. The two refusals that once drew one —
 * `export_unverified` and `export_narrower` — are gone with the delta guard they answered
 * (D64, amended 2026-09-02), so the absence is asserted over EVERY refusal rather than over
 * the ones a list happened to omit. */
for (const refusal of [
  {
    status: 502,
    code: 'tcg_session_expired',
    message:
      'TCGplayer redirected the download to its login page, which means the session in '
      + 'TCGPLAYER_STORE_COOKIE has expired.',
    shown: 'has expired',
  },
  {
    status: 409,
    code: 'export_scope_incomplete',
    message:
      'This export was asked for Unleashed and came back without Unleashed. Every card of a '
      + 'missing set would queue as no_catalog_row. Nothing was kept.',
    shown: 'came back without',
  },
]) {
  test(`a refusal draws a sentence and nothing to press: ${refusal.code}`, async ({ page }) => {
    const wire = await open(page)
    await openRun(page)
    await routeFetch(page, wire, {
      status: refusal.status,
      body: { error: { code: refusal.code, message: refusal.message } },
    })
    await fetchButton(page).click()

    /* The server's sentence verbatim, which is `docs/DESIGN.md`'s copy rule for owner
       screens, with the machine string beneath it so what was seen can be grepped. */
    await expect(page.locator('.run-result-refused')).toContainText(refusal.shown)
    await expect(page.locator('.run-result-refused')).toContainText(refusal.code)

    /* A REFUSED FETCH MUST NOT JOIN. It wrote nothing, so joining after one would silently
       re-use the previous export and look exactly like the fetch had worked. */
    expect(wire.filter((row) => row.path.endsWith('/join'))).toHaveLength(0)

    await expect(page.locator('.run-result-refused button')).toHaveCount(0)
    await expect(page.getByRole('button', { name: /Fetch anyway/ })).toHaveCount(0)
  })
}

test('the receipt says what was asked for, not only what arrived', async ({ page }) => {
  const wire = await open(page)
  await routeFetch(page, wire, { status: 200, body: fetchedBody() })
  await openRun(page)
  await fetchButton(page).click()

  /* THE SCOPE IS THE OPERATOR'S OWN CAPTURE CLAIMS READ BACK (D65). A receipt showing only
     the result cannot be read for whether the request was right, and the request is the half
     they can correct — a set hint that resolved to the wrong set is invisible otherwise. The
     game is drawn by its display name rather than its machine string, which is this rebuild's
     rule everywhere and does not change what the line says. */
  const receipt = page.locator('.run-receipt')
  await expect(receipt).toContainText('Riftbound')
  await expect(receipt).toContainText('Unleashed')

  /* AND THE EXPORT THIS RUN HELD BEFORE THIS ONE, which is what makes the row count above
     readable: 153 rows is only reassuring beside the number it replaced. */
  await expect(page.locator('.run-receipt-was')).toContainText('Last time:')
})

/* TWO CASES DELETED HERE, BOTH WITH THE THING THEY ASSERTED.

   `the fetch answers both acknowledgements itself rather than asking` sent `accept_unverified`
   and `accept_narrower` on every fetch, because the server refused without them. D64's
   amendment RETIRED the delta guard and deleted both fields from the wire, so the case now
   asserts a request shape no route reads — and the workaround it was defending (answering the
   two questions up front so the operator never sees them) has nothing left to answer.

   `the receipt names the export this run held before it` is covered by the ported case above,
   against the REAL payload. This one built `previous` as `{rows, fetched_at}`, a shape this
   branch guessed before the merge brought main's `Record<game, {file, rows, skus}>`; asserting
   a stub nothing sends proves the stub. */

test('a hint that resolved to nothing says so, because the export silently widened', async ({
  page,
}) => {
  const wire = await open(page)
  await routeFetch(page, wire, {
    status: 200,
    body: fetchedBody({
      asked: {
        game: 'riftbound', category_id: 89, hints: ['OGN'], set_ids: [],
        unresolved_hints: ['OGN'], sets: [], widened: true,
      },
    }),
  })
  await openRun(page)
  await fetchButton(page).click()

  /* WIDENING IS SAFE AND SILENT, WHICH IS EXACTLY WHY IT IS DRAWN. `OGN` is a community set
     code and TCGplayer calls that set `Origins`, so it resolves to nothing and the fetch
     takes the whole category — correct, larger, and indistinguishable from a hint that
     worked unless the screen says which happened. */
  await expect(page.locator('.run-receipt')).toContainText('OGN')
  await expect(page.locator('.run-receipt')).toContainText('covered by the wider ask')
})

/* ------------------------------------------------------------------ D76: the scope as a lever
 *
 * THE PROPERTY IS THAT A HUMAN CAN SEE AND CHANGE THE SCOPE BEFORE PRESSING. `CLAUDE.md`'s
 * route-is-not-a-feature rule is the whole reason these three exist rather than the server
 * tests alone: `_scope_for_run` can be perfect and the operator still unable to reach it. */

test('the scope panel draws what the fetch will ask for, and why', async ({ page }) => {
  const wire = await open(page)
  await routeFetch(page, wire, { status: 200, body: fetchedBody() })
  await openRun(page)

  /* THE EVIDENCE THE RULE READS, WHICH IS THE FACT THAT WAS INVISIBLE. `1 of 200 carry a set
     hint` is what decides whether a set filter is safe, and while it could not be seen, one
     hinted card scoped a whole box's export and the receipt reported success. */
  await openJoinOptions(page)
  await expect(page.locator('.run-scope')).toContainText('1 of 200 cards carry a set hint')
  await expect(page.locator('.run-scope')).toContainText('category')

  /* AND THE REASON IN A SENTENCE, not the machine string. A scope is only correctable by
     somebody who can see which of the three voices chose it. */
  await expect(page.locator('.run-scope-says')).toContainText(
    'whole catalogue comes down in one file',
  )
})

test('choosing the whole category sends it, rather than only redrawing the sentence', async ({
  page,
}) => {
  const wire = await open(page)
  await routeFetch(page, wire, { status: 200, body: fetchedBody() })
  await openRun(page)

  await openJoinOptions(page)
  /* A BUTTON GROUP RATHER THAN RADIOS, which is a widget choice and not a behaviour: one of
     three is chosen, the choice is announced (`aria-pressed`), and what it changes is the
     request below. */
  await page.getByRole('button', { name: 'Every set in the category' }).click()
  await expect(page.locator('.run-scope-says')).toContainText('you asked for the whole category')

  await fetchButton(page).click()

  /* THE CONTROL AND THE REQUEST ARE ONE DECISION READ TWICE. A panel that drew a scope the
     button did not send would be worse than no panel — it would be a lie the operator acts on,
     which is exactly the failure D65's after-the-fact receipt made possible. */
  const sent = wire.filter((row) => row.path.endsWith('/export')).pop()
  expect(sent?.body).toMatchObject({ scope: 'category' })
})

test('the routing lever reaches join', async ({ page }) => {
  const wire = await open(page)
  await openRun(page)
  await openJoinOptions(page)

  await page.getByLabel('Send to review at or below').selectOption('medium')
  await page.getByRole('button', { name: 'Join again' }).click()

  /* `--review-below-confidence` was reachable only from a terminal. `--rule` and `--basis`
     are deliberately NOT here: D49 makes `inventory/prices.json` the one place a pricing answer is
     written, and a second place to say `rule` already cost 48 cards a price nobody chose. */
  const join = wire.filter((row) => row.path.endsWith('/join')).pop()
  expect(join?.body).toMatchObject({ review_below_confidence: 'medium' })
  expect((join?.body as { rule?: unknown }).rule).toBeUndefined()
})

/* ---------------------------------------- the rarity correction, and why it needs two steps */

test('a joined run says how to correct a whole stack, and that the box alone is not enough', async ({
  page,
}) => {
  /* THE STEP THAT MAKES THE PRESS REAL, and the one an operator cannot guess. `#/inventory`'s
     Manage box → Rarity rewrites a whole box's claim and its capture sidecars, and on its own
     it changes NOTHING here: `cli/resolve.py` reads the claim off the RUN record with no store
     fallback, so a join over the old run reads the old claim. The re-identify is what rewrites
     it, and it is free — the cache is keyed on the photograph and the claim never reaches the
     model. Without this sentence the operator corrects the box, re-joins, sees the same 141
     questions, and concludes the correction did not work. */
  await open(page, { detail: { joined: true, counts: { cards_in: 40, skus: 30, queued_main: 12, queued_parked: 3 } } })
  await openRun(page)

  const note = page.locator('.runs-correction')
  await expect(note).toBeVisible()
  await expect(note).toContainText('Manage box')
  await expect(note).toContainText('correcting the box alone changes nothing')
  await expect(note).toContainText('costs nothing')
  await expect(note.getByRole('link', { name: /Inventory/i })).toHaveAttribute('href', '#/inventory')
})

test('and it is not drawn on a run that has never been joined', async ({ page }) => {
  /* The note is about a queue this run produced. A run with no join has no queue, so the
     sentence would be advice about nothing — which is how standing advice becomes furniture. */
  await open(page)
  await openRun(page)
  /* The figures block is the sibling under the same `joined` test, so asserting it is absent
     too keeps this from passing merely because the fold never opened. */
  await expect(page.locator('.runs-figures')).toHaveCount(0)
  await expect(page.locator('.runs-correction')).toHaveCount(0)
})

/* ===================== THE EXPORT IS THE GAME'S, AND THE PRESS MAY NOT LIE ABOUT IT
   (D166)

   THE WHOLE POINT OF THESE FIVE IS THAT THE RECEIPT'S OTHER FIGURES CANNOT CARRY THEM. A
   reuse and a fetch answer with the same file, the same rows, the same SKUs and the same
   sets — so `Export reused` and the width line are the only places the difference exists on
   screen. T7 proves the server skipped the request; these prove a human is told. */

test('a reused export says so, because every other figure on the receipt is identical', async ({
  page,
}) => {
  const wire = await open(page)
  await routeFetch(page, wire, {
    status: 200,
    body: fetchedBody({ reused: true, age_s: 240, store: '/x/inventory/.exports/riftbound' }),
  })
  await openRun(page)
  await fetchButton(page).click()

  const receipt = page.locator('.run-receipt')
  await expect(receipt).toContainText('Export reused')
  await expect(receipt).not.toContainText('Export fetched')
  /* THE AGE IS THE ACTIONABLE HALF. "Reused" alone does not say whether the reading is four
     minutes or four hours old, and the operator's next decision is whether to refresh. */
  await expect(receipt).toContainText('taken 4 minutes ago')
  await expect(receipt).toContainText('nothing was downloaded')
})

test('a reuse seconds old reads as a sentence, not as a missing figure', async ({ page }) => {
  /* THE BRANCH THE FIRST BUILD OF THIS GOT WRONG, and no assertion here read it: with the
     helper returning a bare duration, `age_s: 12` rendered "Read just taken ago" on the
     receipt and "just taken old" on the scope line. Both went past a green spec, because
     every case above uses a minutes-old fixture. Found by rendering the screen and looking
     at it, which is why the round number is not the only age tested. */
  const wire = await open(page)
  await routeFetch(page, wire, { status: 200, body: fetchedBody({ reused: true, age_s: 12 }) })
  await openRun(page)
  await fetchButton(page).click()

  const receipt = page.locator('.run-receipt')
  await expect(receipt).toContainText('taken moments ago')
  await expect(receipt).not.toContainText('ago and already')
  await expect(receipt).not.toContainText('old —')
  await expect(receipt).not.toContainText('0 minutes')
})

test('and an hours-old reuse says hours, because minutes stop being readable', async ({
  page,
}) => {
  /* A WHOLE NUMBER OF HOURS, because the first version of this asserted `2 hours` against
     9000s and the screen correctly said 3 — `Math.round(2.5)` is 3. The fixture was wrong
     and the code was right, which is the only kind of red worth having. */
  const wire = await open(page)
  await routeFetch(page, wire, { status: 200, body: fetchedBody({ reused: true, age_s: 7200 }) })
  await openRun(page)
  await fetchButton(page).click()

  await expect(page.locator('.run-receipt')).toContainText('taken 2 hours ago')
})

test('and a real fetch still says fetched, so the word is not decoration', async ({ page }) => {
  const wire = await open(page)
  await routeFetch(page, wire, { status: 200, body: fetchedBody({ reused: false, age_s: 0 }) })
  await openRun(page)
  await fetchButton(page).click()

  const receipt = page.locator('.run-receipt')
  await expect(receipt).toContainText('Export fetched')
  await expect(receipt).not.toContainText('Export reused')
  await expect(receipt).not.toContainText('nothing was downloaded')
})

test('a widened scope carries its measured width against the cap, before the press', async ({
  page,
}) => {
  /* MEASURED 2026-09-12, AND THESE ARE THE REAL FIGURES: one fetch of the whole Pokemon
     category is 32,629,598 B against a 33,554,432 B ceiling — 97% — while the one set the
     owner's 543 Pokemon cards name is 238,482 B. A widening is 137x and lands two per cent
     short of a refusal, which is not a figure to meet by pressing. */
  const wire = await open(page)
  /* REGISTERED AFTER `open`, AND THE ORDER IS THE ASSERTION'S WHOLE VALIDITY.
     Playwright's LAST matching route wins and `open()` registers the panel-wide scope stub,
     so a stub declared above it is silently shadowed. Both of the cases that read a figure
     were doing that and failed on the panel's own riftbound payload; the one that asserts an
     ABSENCE was doing it too and PASSED, which is a green tick over the wrong page. */
  await page.route(/\/pipeline\/runs\/[^/]+\/scope/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        run: '2026-08-30-box3-01',
        games: [
          {
            game: 'pokemon',
            display: 'Pokemon',
            category_id: 3,
            cards: 200,
            hinted: 1,
            unhinted: 199,
            hints: ['ME01'],
            policy: 'sets',
          },
        ],
        scopes: ['category', 'sets'],
        asked: {
          game: 'pokemon',
          category_id: 3,
          hints: ['ME01'],
          set_ids: [],
          unresolved_hints: [],
          sets: [],
          widened: true,
          scope: 'category',
          policy: 'sets',
          chosen_by: 'cards',
          reason: 'partial_hints',
          cards: 200,
          hinted: 1,
          unhinted: 199,
        },
        reason: null,
        message: null,
        width: {
          bytes: 32629598,
          max_bytes: 33554432,
          headroom: 924834,
          of_max: 0.9724,
          near_cap: true,
          measured: '2026-09-12T07:00:00Z',
          from: 'export-tcgplayer-20260912-070000-deadbeef.csv',
          widened: true,
        },
        reusable: null,
      }),
    })
  })
  await routeFetch(page, wire, { status: 200, body: fetchedBody() })
  await openRun(page)

  const says = page.locator('.run-scope-says')
  await expect(says).toContainText('31 MB')
  await expect(says).toContainText('97%')
  /* AND THE REMEDY, not just the alarm. A figure with nothing to do about it is a figure an
     operator learns to skip. */
  await expect(says).toContainText('Hint the cards')
})

/** The scope route's answer when `_scope_for_run` refused it: `asked` is null, the code and
 *  the sentence are data, and the counts on the game row still draw. `do_pipeline_scope`
 *  reads a `PipelineRefusal` this way on purpose (D76) — the preview is the one place an
 *  operator can correct a scope before spending anything. */
const REFUSED_SCOPE = {
  run: '2026-08-30-box3-01',
  games: [
    {
      game: 'pokemon',
      display: 'Pokemon',
      category_id: 3,
      cards: 200,
      hinted: 153,
      unhinted: 47,
      hints: ['ME01'],
      policy: 'sets',
    },
  ],
  scopes: ['category', 'sets'],
  asked: null,
  reason: 'export_needs_set_hint',
  /* VERBATIM FROM THE SERVER, INCLUDING THE DISPLAY NAME. `Pokémon` and not `pokemon`: the
     refusal is rendered as-is on this screen, and CLAUDE.md's register rule is that an enum
     value is labelled rather than printed raw — so the sentence reads the game's own display
     name off the registry. A stub carrying the key would be asserting the defect. */
  message:
    'Every Pokémon card in a run has to name its set, and 47 of its 200 do not. Without one '
    + 'the export asks for the whole Pokémon category — about 32.6 MB, 97% of the 32 MB this '
    + 'download is refused past. Set the hint on the cards that lack one from #/inventory — '
    + 'open the box, Manage box, Set claims — or tick the sets on #/runs to ask for them '
    + 'anyway.',
  width: null,
  reusable: null,
}

test('a scope that could not be decided is drawn beside the press, not inside the well', async ({
  page,
}) => {
  /* THE REFUSAL THIS EXISTS FOR. A Pokemon run whose own cards widened the scope is refused
     rather than fetched — its whole category is 97% of the download's ceiling — and the
     operator meets that on this screen. It used to be drawn ONLY inside the Options well,
     which is shut by default: a refusal nobody can see reads as a broken button.

     THE OWNER'S RULING THAT DISCLOSURES STAY COLLAPSED IS NOT REVERSED BY THIS, and the
     distinction is worth stating because the well's own docstring names it. What stays
     collapsed is a complaint ABOUT the options that well holds — a tick the portal does not
     know, a vocabulary that would not load, all of which arrive with `asked` still answered.
     What moves out is the case where there is no scope AT ALL, which blocks the primary
     press; `asked === null` is exactly that partition. */
  const wire = await open(page)
  await page.route(/\/pipeline\/runs\/[^/]+\/scope/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(REFUSED_SCOPE),
    })
  })
  await routeFetch(page, wire, { status: 200, body: fetchedBody() })
  await openRun(page)

  /* VISIBLE WITH NOTHING PRESSED. The well is shut, so a locator that only resolves after
     `openJoinOptions` would pass over a refusal the operator cannot read. */
  await expect(page.locator('.runs-options')).toHaveCount(0)
  const notice = page.locator('.bn-notice').filter({ hasText: 'has to name its set' })
  await expect(notice).toBeVisible()

  /* THE COUNTS AND THE WIDTH, because "refused" on its own is not actionable — 47 of 200 is
     what sends somebody looking, and 32.6 MB is why it matters. */
  await expect(notice).toContainText('47 of its 200')
  await expect(notice).toContainText('32.6 MB')

  /* AND THE WAY FORWARD. The retroactive claim editor is where a hint is set after the fact,
     and a refusal that named no screen would strand the cards it protects. */
  await expect(notice).toContainText('Manage box')

  /* THE SCOPE SENTENCE IS ABSENT RATHER THAN GUESSING. `asked` is null, so there is no width
     to describe, and a "Will ask TCGplayer for…" line here would be describing a request
     that is not going to be made. */
  await expect(page.locator('.run-scope-says')).toHaveCount(0)

  /* AND IT IS NOT DRAWN TWICE. Opening the well must not repeat the same sentence — the two
     places partition on `asked`, they do not both render it. */
  await openJoinOptions(page)
  await expect(page.locator('.bn-notice').filter({ hasText: 'has to name its set' })).toHaveCount(1)
})

test('a scope that WAS decided keeps its complaint inside the well', async ({ page }) => {
  /* THE OTHER SIDE OF THE PARTITION, and the arm that keeps the one above honest: a notice
     hoisted for every message would have emptied the well and reversed the owner's ruling by
     accident. Here `asked` is answered and a message rides beside it, so the sentence stays
     where the control it is about lives. */
  const wire = await open(page)
  await page.route(/\/pipeline\/runs\/[^/]+\/scope/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ...REFUSED_SCOPE,
        asked: {
          game: 'pokemon',
          category_id: 3,
          hints: ['ME01'],
          set_ids: [4242],
          unresolved_hints: [],
          sets: ['SV09: Journey Together'],
          widened: false,
          scope: 'sets',
          policy: 'sets',
          chosen_by: 'cards',
          reason: null,
          cards: 200,
          hinted: 200,
          unhinted: 0,
        },
        reason: 'set_ids_unknown',
        message: 'TCGplayer’s pokemon category has no set with id 9999.',
      }),
    })
  })
  await routeFetch(page, wire, { status: 200, body: fetchedBody() })
  await openRun(page)

  await expect(page.locator('.bn-notice').filter({ hasText: 'no set with id' })).toHaveCount(0)
  await openJoinOptions(page)
  await expect(page.locator('.bn-notice').filter({ hasText: 'no set with id' })).toBeVisible()
})

test('a narrow measurement is NOT drawn beside a widened scope', async ({ page }) => {
  /* IT WOULD DESCRIBE A DIFFERENT REQUEST. 238 KB is the truth about one set and a lie about
     the whole category, and drawing it under a `widened` scope reassures about the ask that
     is not being made. `width.widened` is the field that separates them, and without this
     case nothing reads it. */
  const wire = await open(page)
  /* REGISTERED AFTER `open`, AND THE ORDER IS THE ASSERTION'S WHOLE VALIDITY.
     Playwright's LAST matching route wins and `open()` registers the panel-wide scope
     stub, so a stub declared above it is silently shadowed — two of these read the
     panel's own riftbound payload, and the one that asserts an ABSENCE passed while
     doing it, which is a green tick over the wrong page. */
  await page.route(/\/pipeline\/runs\/[^/]+\/scope/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        run: '2026-08-30-box3-01',
        games: [
          {
            game: 'pokemon',
            display: 'Pokemon',
            category_id: 3,
            cards: 200,
            hinted: 1,
            unhinted: 199,
            hints: ['ME01'],
            policy: 'sets',
          },
        ],
        scopes: ['category', 'sets'],
        asked: {
          game: 'pokemon',
          category_id: 3,
          hints: ['ME01'],
          set_ids: [],
          unresolved_hints: [],
          sets: [],
          widened: true,
          scope: 'category',
          policy: 'sets',
          chosen_by: 'cards',
          reason: 'partial_hints',
          cards: 200,
          hinted: 1,
          unhinted: 199,
        },
        reason: null,
        message: null,
        width: {
          bytes: 238482,
          max_bytes: 33554432,
          headroom: 33315950,
          of_max: 0.0071,
          near_cap: false,
          measured: '2026-09-12T07:00:00Z',
          from: 'export-tcgplayer-20260912-070000-cafef00d.csv',
          widened: false,
        },
        reusable: null,
      }),
    })
  })
  await routeFetch(page, wire, { status: 200, body: fetchedBody() })
  await openRun(page)

  const says = page.locator('.run-scope-says')
  await expect(says).toContainText('Will ask TCGplayer for')
  await expect(says).not.toContainText('0.2 MB')
  await expect(says).not.toContainText('refused past')
})

test('a scope already on disk says the press will not ask TCGplayer at all', async ({ page }) => {
  const wire = await open(page)
  /* REGISTERED AFTER `open`, AND THE ORDER IS THE ASSERTION'S WHOLE VALIDITY.
     Playwright's LAST matching route wins and `open()` registers the panel-wide scope
     stub, so a stub declared above it is silently shadowed — two of these read the
     panel's own riftbound payload, and the one that asserts an ABSENCE passed while
     doing it, which is a green tick over the wrong page. */
  await page.route(/\/pipeline\/runs\/[^/]+\/scope/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        run: '2026-08-30-box3-01',
        games: [
          {
            game: 'riftbound',
            display: 'Riftbound',
            category_id: 89,
            cards: 200,
            hinted: 1,
            unhinted: 199,
            hints: ['OGN'],
            policy: 'category',
          },
        ],
        scopes: ['category', 'sets'],
        asked: {
          game: 'riftbound',
          category_id: 89,
          hints: ['OGN'],
          set_ids: [],
          unresolved_hints: [],
          sets: [],
          widened: true,
          scope: 'category',
          policy: 'category',
          chosen_by: 'policy',
          reason: 'game_policy',
          cards: 200,
          hinted: 1,
          unhinted: 199,
        },
        reason: null,
        message: null,
        /* NO WIDTH, so the width line is absent and the reuse line is what is being read.
           A case that drew both would pass on either. */
        width: null,
        reusable: {
          file: 'export-tcgplayer-20260912-070000-deadbeef.csv',
          age_s: 120,
          window_s: 900,
        },
      }),
    })
  })
  await routeFetch(page, wire, { status: 200, body: fetchedBody() })
  await openRun(page)

  const says = page.locator('.run-scope-says')
  await expect(says).toContainText('Already have this one')
  await expect(says).toContainText('taken 2 minutes ago')
  await expect(says).toContainText('reuses it')
  /* The width half is genuinely not drawn here — measured nothing, said nothing. */
  await expect(says).not.toContainText('refused past')
})

test('and a scope with nothing on disk promises neither', async ({ page }) => {
  const wire = await open(page)
  await routeFetch(page, wire, { status: 200, body: fetchedBody() })
  await openRun(page)

  /* THE PANEL-WIDE STUB CARRIES NEITHER FIELD, which is also every client written before
     this landed: the guards must read a missing field as "say nothing" rather than crash.
     `undefined !== null` is true, and that is exactly how this would have thrown. */
  const says = page.locator('.run-scope-says')
  await expect(says).toContainText('Will ask TCGplayer for')
  await expect(says).not.toContainText('Already have this one')
  await expect(says).not.toContainText('refused past')
})

/* ------------------------------------------------------------------ the claims panel
 *
 * WHAT A LIVE SEND IS HOLDING, AND THE ONE WAY OUT OF A STUCK CLAIM
 * (D-a-claim-on-the-cards). The guard itself is proved by `make submission-selftest`, which
 * races two real processes over one card; what these cases are for is the half that suite
 * cannot see — whether a human can reach any of it, which is the failure `docs/GATES.md`
 * step 7 records at length and which nothing on the commit path can tell.
 *
 * THE FIXTURE IS `open`'s `claims` OPTION, so the panel is drawn from the wire rather than
 * from a hand-built DOM: a spec that mounted the component directly would pass over a route
 * the screen never calls, which is exactly the shape of the 7b defect.
 */

/** One live claim, in the shape `GET /pipeline/submissions` answers with — EVERY FIELD.
 *
 *  A PARTIAL FIXTURE HERE DOES NOT FAIL PARTIALLY, IT CRASHES THE SCREEN, which is the rule
 *  `card()` at the top of this file already states and which this function had to learn: it
 *  omitted `sample`, the panel does `claim.sample.join(', ')`, and all three cases below died
 *  in `open()` on `main.runs` never becoming visible — the route's error boundary doing its
 *  job, and nothing at all about the panel. The failure named the wrong subject, which is the
 *  whole cost of a fixture that is not the wire's real shape. */
function claimRow(
  over: Partial<{
    receipt: string
    run: string | null
    pid: number
    started_at: string
    cards: number
    sample: string[]
    capture_dir: string | null
    holder_alive: boolean
  }> = {},
) {
  return {
    receipt: 'sub-20260912T090000-aaaaaa',
    run: '2026-09-12-box3-01',
    pid: 4242,
    started_at: '2026-09-12T09:00:00+00:00',
    cards: 14,
    sample: ['3/1', '3/2', '3/3'],
    capture_dir: 'captures/cards/box3',
    holder_alive: true,
    ...over,
  }
}

test('no claim draws no panel at all, which is what a healthy store looks like', async ({ page }) => {
  await open(page)
  /* NOT "hidden" — NOT RENDERED. A claim exists only between a press and the collection it
     paid for, so this is the state the screen is in almost always, and a panel that took
     height to say nothing would be on this screen forever. */
  await expect(page.locator('.claims')).toHaveCount(0)
})

test('a live send says what it is holding, and is NOT offered a release', async ({ page }) => {
  await open(page, { claims: [claimRow()] })
  const panel = page.locator('.claims')
  await expect(panel).toBeVisible()
  /* THE FIGURE IS THE CARDS, NOT THE ROWS. One claim over fourteen cards and fourteen claims
     over one card each are the same row count and completely different situations. */
  await expect(panel).toContainText('14 cards held by 1 send')
  await expect(panel).toContainText('2026-09-12-box3-01')
  await expect(panel.getByText('Running')).toBeVisible()
  /* THE SAFETY PROPERTY, AND THE REASON THIS CASE EXISTS. Releasing a claim whose run is
     still submitting re-opens those cards to a second press — the double invoice the claim
     was written to prevent — so the control is NOT DRAWN, rather than drawn and disabled. */
  await expect(panel.getByRole('button', { name: /Release/ })).toHaveCount(0)
  /* And no warning: nothing here is stuck. */
  await expect(panel.locator('.bn-notice')).toHaveCount(0)
})

test('a send whose holder is gone keeps its cards, says so, and offers the way out', async ({ page }) => {
  await open(page, { claims: [claimRow({ holder_alive: false, cards: 3, run: '2026-09-12-box7-01' })] })
  const panel = page.locator('.claims')
  await expect(panel).toContainText('3 cards held by 1 send')
  await expect(panel.getByText('Holder gone')).toBeVisible()
  /* THE SENTENCE HAS TO SAY WHY THE CARDS ARE STILL HELD, because a dead holder looks like a
     bug until you know a killed send has already been billed. */
  await expect(panel.locator('.bn-notice')).toContainText('already been billed')
  await expect(panel.getByRole('button', { name: /^Release 3 cards/ })).toBeVisible()
})

test('the release names its receipt and confirms, and the page does not move under the press', async ({ page }) => {
  const wire = await open(page, {
    claims: [
      claimRow({ receipt: 'sub-live-1', run: '2026-09-12-box3-01', cards: 14, holder_alive: true }),
      claimRow({ receipt: 'sub-dead-1', run: '2026-09-12-box7-01', cards: 3, holder_alive: false }),
    ],
  })
  await page.route(/\/pipeline\/submissions\/[^/]+\/release$/, async (route) => {
    wire.push({
      method: 'POST',
      path: new URL(route.request().url()).pathname,
      body: route.request().postDataJSON(),
    })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ receipt: 'sub-dead-1', run: '2026-09-12-box7-01', released: true, cards: 3, claims: [] }),
    })
  })

  const panel = page.locator('.claims')
  const below = page.locator('.runs-body')
  const beforeBox = await below.boundingBox()
  const beforeHeight = await page.evaluate(() => document.documentElement.scrollHeight)

  await panel.getByRole('button', { name: /^Release 3 cards/ }).click()

  /* THE CONTROL BECOMES ITS OWN RESULT, IN THE SLOT IT STOOD IN (D57). */
  await expect(panel.getByText('Released 3 cards')).toBeVisible()

  /* D118 — A PRESS CHANGES WHAT IS ON THE SCREEN AND NEVER WHERE THE REST OF IT IS, and this
     is the assertion the panel was rebuilt for. Adopting the answer's list straight away
     removed the row and moved everything below the panel 156px, with the page 60px shorter;
     the row now stays and the poll drops it a beat later. Both halves are asserted, because
     the height alone went right while the row was still leaving. */
  const afterBox = await below.boundingBox()
  expect(Math.round((afterBox?.y ?? 0) - (beforeBox?.y ?? 0))).toBe(0)
  expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBe(beforeHeight)

  /* THE HEADLINE COUNTS WHAT IS STILL HELD, never the rows on screen — a row kept for its
     receipt is holding nothing, and counting it would overstate the lock at the one moment
     the operator is watching it fall. */
  await expect(panel).toContainText('14 cards held by 1 send')

  const release = wire.filter((call) => call.path.endsWith('/release'))
  expect(release).toHaveLength(1)
  /* THE RECEIPT IS IN THE PATH and the confirm is in the body: the route refuses without it,
     because releasing a claim whose holder is still submitting is the second invoice. */
  expect(release.map((call) => [call.path, call.body])).toEqual([
    ['/pipeline/submissions/sub-dead-1/release', { confirm: true }],
  ])
})
