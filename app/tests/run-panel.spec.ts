import { test, expect, type Page } from '@playwright/test'

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
          gaps_in_section: 0,
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
    live: false,
    pid: null,
    phase: 'join',
    batch_ids: ['msgbatch_x'],
    collected: true,
    joined: false,
    counts: {},
    bypass_detection: false,
    bypassed: null,
    usage: {},
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
            /* A SECOND BOX, so a cart can be a cart of more than one. Named, because the
               strip draws `Box 12 · codes` and the cart row draws `Box 12` alone — two
               different renderings of one box that a one-box fixture cannot tell apart. */
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
  await expect(page.locator('.run-panel')).toBeVisible()

  /* SCOPED BEFORE ANYTHING ELSE, because on this route nothing is scoped on arrival and the
     spend gate reads `scope.box !== null`. On `#/inventory` the walk picked a shelf by itself
     and every test in this file inherited a box without asking for one; here the box is a
     deliberate press, which is what `Runs.tsx` chose — "a box chosen for the operator is a box
     they did not read, and the next press after it spends money". The unscoped state is worth
     a test of its own rather than a state every other test tiptoes around: see below. */
  await pickBox(page)
  return wire
}

/** Picks box 9 out of the strip.
 *
 *  SCOPED TO `.runs-boxes`, AND THE FIRST DRAFT WAS NOT — `getByRole('button', {name: 'Box 9'})`
 *  matched the chip AND a run row whose accessible name ends `box 9`, and Playwright's strict
 *  mode caught it as an ambiguity rather than clicking the wrong one. Worth a helper rather than
 *  a longer locator repeated twice: this is the one press that turns an unscoped screen into a
 *  scoped one, and every test in this file depends on it having happened. */
async function pickBox(page: Page, box = 9) {
  await page.locator('.runs-boxes').getByRole('button', { name: new RegExp(`^Box ${box}`) }).click()
}

/** Open the fold, where every pipeline control lives.
 *
 *  THE FOLD'S COST, STATED IN A HELPER rather than smuggled into `open` — exactly the shape
 *  `app/tests/inventory.spec.ts:openBoxOps` takes, and for the same reason: a test that wants
 *  a control says so, and the fold test below can still assert the state every other test
 *  starts from. */
/* THERE IS NOTHING TO OPEN ANY MORE. This helper clicked `.run-head` to unfold the panel;
 *  the fold was removed on 2026-08-24 at the owner's instruction — "both box and run, i don't
 *  want click in functionality, i want their buttons just there" — so it now only waits for
 *  the control every caller was really waiting for. Kept as a function rather than inlined so
 *  the call sites still read as "get to the point where the pipeline is usable". */
async function openPanel(page: Page) {
  await expect(page.getByRole('button', { name: 'Check cost' })).toBeVisible()
}

// -------------------------------------------------------------- present, not disclosed

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
  await expect(page.getByRole('button', { name: 'Check cost' })).toBeVisible()
  await expect(page.locator('.run-panel details, .run-panel summary')).toHaveCount(0)

  /* AND IT STILL SAYS WHAT IT HOLDS. `BoxOps` states the rule and it survives the fold:
     "a disclosure that under-sold its contents is exactly how three routes came to have no
     reachable control" — the pipeline being the largest instance this repo has had. It was
     `.run-hint` inside the panel until 2026-08-29 and is the page's lede now: on a route of its
     own the four command names are what the screen IS, not a caption on a panel inside it. The
     assertion follows the string rather than the element, which is the half that matters. */
  await expect(page.locator('.runs-lede')).toContainText('identify · join · emit · reconcile')
})

test('a live run is announced where the panel already is', async ({ page }) => {
  await open(page, { live: true })

  /* This used to assert that a live run OPENS the panel — the one thing that opened it
     without being asked. With nothing to open, what survives is the half that mattered: a
     batch takes minutes to hours and the operator did not necessarily start it in this tab
     (D13 puts one truth on one Mac, so a run started from a terminal is this screen's
     business too), and the screen has to say so on arrival. */
  await expect(page.locator('.run-list-head')).toContainText('1 running')
  await expect(page.locator('.run-phase-identifying').first()).toContainText('running')
})

// ------------------------------------------------------------------- reachable at all

test('the pipeline is on its own screen, with all four steps named', async ({ page }) => {
  await open(page)
  await openPanel(page)

  /* THE ASSERTION THE HARD RULE ASKS FOR. Four commands have existed since step 4; this is the
     first thing in the repo that says a person can reach them. */
  await expect(page.getByRole('button', { name: 'Check cost' })).toBeVisible()

  /* ALL FOUR STEPS ON ARRIVAL, WITH NOTHING CLICKED — and the click this used to need was the
     bug. `STEPS` is authored rather than derived from `phase` because "a screen that only drew
     the current step would leave the operator unable to see that emit exists until join had
     finished", and that promise was kept against `phase` and broken against `detail`: three of
     the four rendered only inside the open-run guard, so this test had to open a run before it
     could assert them, and with no runs at all they existed nowhere. */
  const titles = await page.locator('.run-step-title').allInnerTexts()
  expect(titles).toEqual(['Identify', 'Join', 'Emit', 'Reconcile'])

  /* THE NEGATIVE HALF, which is what stops a later refactor drawing dead controls to fill the
     column. A step's HEAD says what it is; its CONTROLS need a run to act on, and absent beats
     disabled for the reason `.run-button`'s own comment gives — a disabled button is one
     attribute away from being pressable. */
  await expect(page.getByRole('button', { name: 'Preview' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Write the import files' })).toHaveCount(0)
  await expect(page.locator('.run-needs')).toContainText('Pick a run above')

  // And they arrive the moment a run is picked.
  await page.locator('.run-row').first().click()
  await expect(page.locator('.run-open')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Preview' })).toHaveCount(1)
})

test('the four steps exist before any run does', async ({ page }) => {
  /* THE STATE THE OLD ARRANGEMENT COULD NOT DRAW AT ALL. With no runs on disk, join, emit and
     reconcile were not merely un-pressable — they were absent from the document, so a first-time
     operator could not learn the pipeline had four parts until after they had paid for one. */
  await open(page, { runs: [] })
  await openPanel(page)

  await expect(page.locator('.run-empty')).toHaveText('No runs yet.')
  const titles = await page.locator('.run-step-title').allInnerTexts()
  expect(titles).toEqual(['Identify', 'Join', 'Emit', 'Reconcile'])
  await expect(page.locator('.run-needs')).toContainText('Identify a box first')
})

test('which steps cost money is on the heading line, not buried in the prose', async ({
  page,
}) => {
  await open(page)
  await openPanel(page)
  await expect(page.locator('.run-step-money')).toHaveText('Costs money')

  /* `allTextContents` and not `allInnerTexts`: the stylesheet uppercases these labels, and
     `innerText` returns what is PAINTED while `textContent` returns what is written. The
     authored string is the claim worth asserting — a casing rule is a design choice this file
     has no business freezing, and `toHaveText` above reads textContent for the same reason. */
  const free = await page.locator('.run-step-free .run-step-cost').allTextContents()
  expect(free).toEqual(['Free · re-runnable', 'Free · re-runnable', 'Free · re-runnable'])
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
  await openPanel(page)

  /* Nothing has been pressed, so there is no preflight and no console — and the explanation is
     already there. That ordering is the point: the console's own crop line is a receipt, and a
     receipt arrives after the decision. */
  await expect(page.locator('.run-quote')).toHaveCount(0)

  const says = page.locator('.run-step .run-step-fine').first()
  await expect(says).toContainText('Finds the card in each photograph')
  await expect(says).toContainText('never touched')
  /* The measurement, in the house voice this class already uses one step down — the bypass
     switch's sentence cites box 2's 230 of 544 rather than asserting a rule. */
  await expect(says).toContainText('$0.62')
})

test('each reading sends the pair it names, never half of one', async ({ page }) => {
  const wire = await open(page)
  await openPanel(page)

  /* THE FAILURE THIS FORBIDS is the one D32 says it got wrong in public first: a crop at an
     unchanged 1568, which costs 26% MORE for asking for less. A preset sets both values or it
     is not a preset, so the assertion reads both out of one body. */
  await page.getByRole('button', { name: 'Cheapest' }).click()
  await page.getByRole('button', { name: 'Check cost' }).click()
  await expect(page.locator('.run-quote')).toBeVisible()

  const cheap = wire.filter((row) => row.path === '/pipeline/preflight').pop()
  expect(cheap?.body).toMatchObject({ scopes: [{ crop: true, max_edge: 900 }] })

  await page.getByRole('button', { name: 'Whole frame' }).click()
  await page.getByRole('button', { name: 'Check cost' }).click()
  await expect(page.locator('.run-quote')).toBeVisible()

  const whole = wire.filter((row) => row.path === '/pipeline/preflight').pop()
  expect(whole?.body).toMatchObject({ scopes: [{ crop: false, max_edge: 1568 }] })
})

test('the crop is drawn before it is paid for, and the cut is where the route put it', async ({
  page,
}) => {
  await open(page)
  await openPanel(page)

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
  await openPanel(page)
  await expect(page.locator('.run-preview-cut')).toHaveCount(1)

  /* ASSERTED AS AN ABSENCE, the same shape as the spend button's own case. A picture that kept
     drawing a rectangle after `Whole frame` was chosen would be a picture of a send that is
     not the one about to happen — D32's stale-estimate defect, in the medium the operator
     actually believes. */
  await page.getByRole('button', { name: 'Whole frame' }).click()
  await expect(page.locator('.run-preview-cut')).toHaveCount(0)
  await expect(page.locator('.run-preview-card')).toHaveCount(1)

  const whole = wire.filter((row) => row.path === '/pipeline/crop-preview').pop()
  expect(whole?.body).toMatchObject({ crop: false, max_edge: 1568 })

  await page.getByRole('button', { name: 'Cheapest' }).click()
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
  await openPanel(page)
  await expect(page.locator('.run-preview-count')).toContainText('card 1 of 543')

  await page.keyboard.press('ArrowRight')
  await expect(page.locator('.run-preview-count')).toContainText('card 2 of 543')
  expect(wire.filter((row) => row.path === '/pipeline/crop-preview').pop()?.body).toMatchObject({
    offset: 1,
  })

  /* THE GUARD IS THE HALF WORTH ASSERTING. This panel holds a number input and a textarea, and
     an unguarded window listener would steal the caret keys from both — the operator would be
     unable to move through a value they were editing. Reveal `Custom`, put the caret in its
     number field, and the walk must not move.

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
  await openPanel(page)

  await expect(page.locator('.run-preview')).toContainText('claims no number band')

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
  await openPanel(page)

  const box = page.getByRole('checkbox', { name: 'Crop to the card' })
  await expect(box).toHaveCount(0)

  await page.getByRole('button', { name: 'Custom' }).click()
  await expect(box).toBeVisible()
  await expect(page.getByRole('spinbutton', { name: 'Max edge' })).toBeVisible()

  /* DEMOTED, NOT DELETED — every pairing the three chips refuse to offer is reachable here,
     including the wrong one, so the sentence that replaces them has to name it. */
  const says = page.locator('.run-step .run-step-fine').first()
  await expect(says).toContainText('one decision')
  await expect(says).toContainText('BIGGER')
})

test('changing the reading voids the estimate, because it changes what would be sent', async ({
  page,
}) => {
  await open(page)
  await openPanel(page)
  await page.getByRole('button', { name: 'Check cost' }).click()
  await expect(page.locator('.run-button-money')).toHaveCount(1)

  /* THE MONEY GATE'S OWN RULE, APPLIED TO THE BYTES RATHER THAN TO THE CARDS. `scopeKey` was
     `box:indices` alone, so unticking the crop after Check cost left a stale figure standing
     above a live confirm — an estimate for a send that was no longer the one about to happen.
     Asserted as an ABSENCE for the same reason the case below it is. */
  await page.getByRole('button', { name: 'Cheapest' }).click()
  await expect(page.locator('.run-button-money')).toHaveCount(0)
  await expect(page.locator('.run-quote')).toHaveCount(0)
})

test('the cache line is drawn only where cards are already answered', async ({ page }) => {
  await open(page)
  await openPanel(page)
  await page.getByRole('button', { name: 'Check cost' }).click()

  /* D32's known cache gap, said as what it means rather than as a fact about a hash: the crop
     and the max edge are not part of the cache identity, so a box re-read at a different
     reading serves the answers it was first read with and reports them as hits. */
  await expect(page.locator('.run-quote .run-step-fine')).toContainText(
    'keep the answer they were first read with',
  )
})

test('nothing was cached, so the cache line says nothing', async ({ page }) => {
  await open(page, { cacheHits: 0 })
  await openPanel(page)
  await page.getByRole('button', { name: 'Check cost' }).click()
  await expect(page.locator('.run-quote')).toBeVisible()

  /* THE NEGATIVE HALF, and it is the half worth having. A sentence about answers that already
     exist, drawn over a box where none do, is a warning that trains the operator to skip it. */
  await expect(page.locator('.run-quote .run-step-fine')).toHaveCount(0)
})

// ------------------------------------------------------------------------- the money gate

test('the control that spends does not exist until the free preflight has answered', async ({
  page,
}) => {
  await open(page)
  await openPanel(page)

  /* ABSENT, NOT DISABLED. A disabled button is one attribute away from being pressable, and
     that attribute is exactly what a later refactor drops without noticing. */
  await expect(page.locator('.run-button-money')).toHaveCount(0)

  await page.getByRole('button', { name: 'Check cost' }).click()
  await expect(page.locator('.run-quote')).toBeVisible()
  await expect(page.locator('.run-button-money')).toHaveCount(1)
})

test('the estimate and the card count are on screen before the confirm is', async ({ page }) => {
  await open(page)
  await openPanel(page)
  await page.getByRole('button', { name: 'Check cost' }).click()
  await expect(page.locator('.run-quote')).toBeVisible()

  /* The numbers are the COMMAND'S, lifted out of its own preflight stdout — so this asserts
     the parse as well as the render. A panel that recomputed them could show a figure the log
     disagrees with, and the operator would have no way to tell which had drifted. */
  const figures = await page.locator('.run-figures dd').allInnerTexts()
  expect(figures).toEqual(['40', '4', '36', '$0.42'])

  /* And the command's own words beneath them, verbatim — docs/DESIGN.md's copy rule for the
     owner's screens. */
  await expect(page.locator('.run-console').first()).toContainText('estimated cost  $0.42')

  const confirm = page.locator('.run-button-money')
  await expect(confirm).toContainText('$0.42')
  await expect(confirm).toContainText('36')
})

test('the confirm sends confirm:true and the cart the picker is showing', async ({ page }) => {
  const wire = await open(page)
  await openPanel(page)
  await page.getByRole('button', { name: 'Check cost' }).click()
  await page.locator('.run-button-money').click()
  await expect(page.locator('.run-quote')).toHaveCount(0)

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
  await openPanel(page)
  await page.getByRole('button', { name: 'Check cost' }).click()
  await page.locator('.run-button-money').click()

  /* The quote is cleared on success rather than left standing. Without this, pressing the
     confirm twice would start two runs on one estimate — and the second would be a second
     invoice for a number the operator only agreed to once. */
  await expect(page.locator('.run-button-money')).toHaveCount(0)
})

test('nothing to send draws no confirm at all, and says why', async ({ page }) => {
  await open(page, { toSend: 0, estimate: 0 })
  await openPanel(page)
  await page.getByRole('button', { name: 'Check cost' }).click()
  await expect(page.locator('.run-quote')).toBeVisible()

  await expect(page.locator('.run-button-money')).toHaveCount(0)
  await expect(page.locator('.run-blocked')).toContainText('nothing to send and nothing to spend')
})

test('a live run over the same cards blocks the confirm rather than racing it', async ({
  page,
}) => {
  await open(page, { busyRun: '2026-08-24-box9-01' })
  await openPanel(page)
  await page.getByRole('button', { name: 'Check cost' }).click()

  /* Two live batches over one box is two invoices for one answer. The route refuses it as
     `run_already_live`; the screen refuses to draw the button, so the operator never presses
     something that is going to fail. */
  await expect(page.locator('.run-button-money')).toHaveCount(0)
  /* IT NAMES THE BOX NOW, because a cart can carry several and "these cards" would not say
     which of them is blocked. The run name is on the line for the same reason it always was:
     the answer is to open that run, and a refusal that does not name it is a dead end. */
  await expect(page.locator('.run-blocked')).toContainText('already identifying box 9')
  await expect(page.locator('.run-blocked')).toContainText('2026-08-24-box9-01')
})

// ------------------------------------------------------------------------- the free steps

test('join offers a preview that writes nothing, and the trust switch in plain English', async ({
  page,
}) => {
  const wire = await open(page)
  await openPanel(page)
  await page.locator('.run-row').first().click()

  /* D3's amendment, stated the way the owner asked for it — they said the question had not
     been put in plain English, and this is the sentence that answers it. */
  const trust = page.getByRole('checkbox', { name: 'Trust my finish claim over the photo' })
  await expect(trust).toBeVisible()
  await trust.check()

  await page.getByRole('button', { name: 'Preview' }).click()
  const join = wire.find((row) => row.path.endsWith('/join'))
  const body = join?.body as Record<string, unknown>
  expect(body.dry_run).toBe(true)
  expect(body.bypass).toBe(true)
})

test('this run\'s own receipts download here; the import CSVs do not', async ({ page }) => {
  await open(page)
  await openPanel(page)
  await page.locator('.run-row').first().click()

  /* THE FILES WRITTEN BY THE COMMANDS PRESSED ON THIS SCREEN. `report.txt` and
     `pricing.json` come from join, `reconcile.txt` from reconcile — each one screen-inch
     from the button that produced it, which is docs/GATES.md's gap answered for the half of
     the artefacts that stayed. */
  const file = page.locator('.run-file').filter({ hasText: 'reconcile.txt' })
  await expect(file).toBeVisible()
  await expect(file).toHaveAttribute('download', 'reconcile.txt')
  expect(await file.getAttribute('href')).toContain('/pipeline/runs/')

  /* AND THE IMPORT CSVs ARE NOT HERE, ASSERTED AS AN ABSENCE (D50). They went to
     `#/pricing` with the press that writes them; `app/tests/pricing.spec.ts` carries the
     Gate B case verbatim at its new address. A deliberate removal that a later edit must
     not quietly undo — which is what an absence is for, and why this is not a weakening of
     the case it replaces. */
  await expect(page.locator('.run-file-import')).toHaveCount(0)
})

test('a bypassed run says so on the run itself, not only in its log', async ({ page }) => {
  await open(page, { detail: { bypass_detection: true, bypassed: 209 } })
  await openPanel(page)
  await page.locator('.run-row').first().click()
  await expect(page.locator('.run-open')).toBeVisible()

  /* The owner's choice, in their words: "resolved by the claim, and the run report says so."
     A count that appeared only in a file nobody opened would not be that. */
  await expect(page.locator('.run-flagged')).toContainText('209 cards resolved by your finish claim')
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
  await pickBox(page, 12)

  /* TWO ROWS, ONE PER BOX, EACH WITH ITS OWN READING PICKER. The strip decides WHICH boxes and
     the cart decides how each is read — the reading is part of what the confirm is agreeing to
     buy, because the estimate is computed from the bytes each card is sent as. */
  await expect(page.locator('.run-leg')).toHaveCount(2)
  await expect(page.locator('.run-leg-box').first()).toHaveText('Box 9')
  await expect(page.locator('.run-leg-box').nth(1)).toHaveText('Box 12')
  await expect(page.locator('.runs-scope')).toContainText('2 boxes')

  await page.getByRole('button', { name: /^Check cost/ }).click()
  await expect(page.locator('.run-quote')).toBeVisible()

  const asked = wire.filter((row) => row.path === '/pipeline/preflight').pop()
  const body = asked?.body as { scopes?: { box: number }[] }
  expect(body.scopes?.map((leg) => leg.box)).toEqual([9, 12])

  /* THE CONFIRM QUOTES THE TOTAL, NOT A LEG. Two boxes at 36 each is 72 cards and $0.84 — a
     screen that read the first leg and called it the total would say 36 and $0.42 here, which
     is the one number the operator is agreeing to and the one that must not be understated. */
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
  await pickBox(page, 12)

  /* THE WHOLE REASON THIS IS A CART RATHER THAN ONE RUN ACROSS SEVERAL BOXES (D48). Which end
     of D32's measured frontier is right depends on what is IN the drawer, so a box of bulk
     commons and a box worth reading a collector number off must be able to disagree. Scoped
     per row, because `Cheapest` appears once per box and an unscoped locator would be
     ambiguous — which is the ambiguity that proves the control is per box. */
  await page.locator('.run-leg').nth(1).getByRole('button', { name: 'Cheapest' }).click()
  await page.getByRole('button', { name: /^Check cost/ }).click()
  await expect(page.locator('.run-quote')).toBeVisible()

  const asked = wire.filter((row) => row.path === '/pipeline/preflight').pop()
  const body = asked?.body as { scopes?: { box: number; crop: boolean; max_edge: number }[] }
  expect(body.scopes?.[0]).toMatchObject({ box: 9, crop: true, max_edge: 1200 })
  expect(body.scopes?.[1]).toMatchObject({ box: 12, crop: true, max_edge: 900 })
})

test('adding a box to the cart voids the estimate, exactly as changing a reading does', async ({
  page,
}) => {
  await open(page)
  await page.getByRole('button', { name: /^Check cost/ }).click()
  await expect(page.locator('.run-button-money')).toHaveCount(1)

  /* THE MONEY GATE'S RULE, APPLIED TO THE CART. "A confirm whose first step described a
     different set of cards is not a confirm at all" — and a second box is a different set of
     cards by the widest possible margin. Asserted as an ABSENCE, the same shape as the
     reading case above it, because that is the form no refactor can quietly satisfy. */
  await pickBox(page, 12)
  await expect(page.locator('.run-button-money')).toHaveCount(0)
  await expect(page.locator('.run-quote')).toHaveCount(0)
})

test('a box is untickable, and the last one out leaves nothing to price', async ({ page }) => {
  await open(page)
  await pickBox(page, 12)
  await expect(page.locator('.run-leg')).toHaveCount(2)

  await pickBox(page, 12)
  await expect(page.locator('.run-leg')).toHaveCount(1)
  await expect(page.locator('.run-leg-box')).toHaveText('Box 9')

  /* Back to the state the screen opens in, and the free preflight is disabled again rather
     than absent — the one control on this screen that gets to be disabled, because it is free
     and it is the next thing to press. */
  await pickBox(page, 9)
  await expect(page.locator('.run-leg')).toHaveCount(0)
  await expect(page.getByRole('button', { name: /^Check cost/ })).toBeDisabled()
})

test('a box the send could not start is named, not swallowed', async ({ page }) => {
  await open(page, {
    failed: [{ box: 12, code: 'spawn_failed', message: 'Could not start `pkmnscan identify`' }],
  })
  await pickBox(page, 12)
  await page.getByRole('button', { name: /^Check cost/ }).click()
  await page.locator('.run-button-money').click()

  /* THE ONE FAILURE NO VALIDATION CAN PRE-EMPT (D48). `Popen` can fail on the fourth leg after
     three have started, so the route answers with both halves. A partial send reported as a
     whole one is an invoice nobody can account for; reported honestly it is recoverable by
     pressing again for the box that did not go, which is what the sentence says. */
  const note = page.locator('.run-note')
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

     DISABLED RATHER THAN ABSENT, DELIBERATELY, and it is the one control on this screen that
     gets to be. docs/DESIGN.md's absent-not-disabled rule is about the control that COMMITS —
     the spend button, which still does not exist until the preflight has answered, asserted
     above. This one is free, it is the next thing to press, and a control that vanishes until
     an unrelated press elsewhere brings it back is a screen that looks broken. */
  await page.reload()
  await expect(page.locator(VIEW)).toBeVisible()
  await expect(page.locator('.runs-scope')).toContainText('Pick a box.')
  await expect(page.getByRole('button', { name: 'Check cost' })).toBeDisabled()

  // And it is one press away, with the scope said out loud before anything can be spent.
  await pickBox(page)
  await expect(page.locator('.runs-scope')).toContainText('Box 9 · the whole box')
  await expect(page.getByRole('button', { name: 'Check cost' })).toBeEnabled()
})
