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

const VIEW_ROUTE = '/#/inventory'
const VIEW = 'main.inventory'

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
    busyRun?: string | null
    /** Fields to override on the OPEN run's detail. Passed through here rather than by
     *  registering a competing `page.route` before the call — Playwright matches handlers in
     *  reverse registration order, so a route set up first is the one that loses, which made a
     *  test that looked correct silently assert against this function's fixture. */
    detail?: Record<string, unknown>
    /** The run list reports a live run, which is the one state that opens the fold by itself. */
    live?: boolean
  } = {},
): Promise<Wire[]> {
  const wire: Wire[] = []
  const record = (method: string, url: string, body: unknown) =>
    wire.push({ method, path: new URL(url).pathname, body })

  /* THE SPEND ROUTE, INTERCEPTED AND NEVER CALLED. The body is recorded so the assertion can
     read what the screen would have sent — the strongest thing a browser test can say about a
     route it must not actually reach. */
  await page.route(/\/pipeline\/identify$/, async (route) => {
    record('POST', route.request().url(), route.request().postDataJSON())
    await route.fulfill({
      status: 202,
      contentType: 'application/json',
      body: JSON.stringify({
        run: '2026-08-24-box9-02',
        path: '/tmp/runs/2026-08-24-box9-02',
        pid: 4242,
        scope: { box: 9, whole_box: true, cards: null },
        argv: [],
      }),
    })
  })

  await page.route(/\/pipeline\/preflight$/, async (route) => {
    record('POST', route.request().url(), route.request().postDataJSON())
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        exit_code: 0,
        scope: { box: 9, whole_box: true, cards: null },
        capture_dir: '/tmp/captures/cards/box9',
        console: PREFLIGHT_CONSOLE,
        photographs: 40,
        cache_hits: 4,
        to_send: options.toSend ?? 36,
        estimate_usd: options.estimate ?? 0.42,
        busy_run: options.busyRun ?? null,
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
        files: [{ name: 'import-listed.csv', bytes: 2048, modified: 0, is_import: true }],
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
        runs: [
          runRow(options.live ? { live: true, pid: 999, phase: 'identifying' } : {}),
        ],
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
            sections_detail: [{ section: 1, start: 1, end: 1, count: 1 }],
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
  return wire
}

/** Open the fold, where every pipeline control lives.
 *
 *  THE FOLD'S COST, STATED IN A HELPER rather than smuggled into `open` — exactly the shape
 *  `app/tests/inventory.spec.ts:openBoxOps` takes, and for the same reason: a test that wants
 *  a control says so, and the fold test below can still assert the state every other test
 *  starts from. */
async function openPanel(page: Page) {
  await page.locator('.run-head').click()
  await expect(page.getByRole('button', { name: 'Check cost' })).toBeVisible()
}

// ------------------------------------------------------------------------------ the fold

test('the panel is shut on arrival, and names all four commands from the outside', async ({
  page,
}) => {
  await open(page)

  /* SHUT BY DEFAULT because this screen's question is "where is this card" and the card detail
     is what answers it. The panel is ~250px and is reached once a box; drawn open it would
     spend a quarter of the viewport on every arrival. `BoxOps` on this same screen made the
     identical trade against a measurement. */
  await expect(page.locator('.run-panel')).not.toHaveAttribute('open', '')
  await expect(page.getByRole('button', { name: 'Check cost' })).toBeHidden()

  /* AND IT SAYS WHAT IS INSIDE. `BoxOps` states the rule: "a disclosure that under-sold its
     contents is exactly how three routes came to have no reachable control" — and the pipeline
     is the largest instance of that failure this repo has had, so all four are named. */
  await expect(page.locator('.run-hint')).toContainText('identify · join · emit · reconcile')

  await openPanel(page)
  await expect(page.locator('.run-panel')).toHaveAttribute('open', '')
})

test('a live run opens the panel on its own, and says one is running', async ({ page }) => {
  await open(page, { live: true })

  /* The one thing that opens it without being asked. A batch takes minutes to hours and the
     operator did not necessarily start it in this tab — D13 puts one truth on one Mac, so a run
     started from a terminal is this screen's business too. */
  await expect(page.locator('.run-panel')).toHaveAttribute('open', '')
  await expect(page.locator('.run-hint')).toContainText('1 running')
  await expect(page.locator('.run-phase-identifying').first()).toContainText('running')
})

// ------------------------------------------------------------------- reachable at all

test('the pipeline is on the inventory screen, with all four steps named', async ({ page }) => {
  await open(page)
  await openPanel(page)

  /* THE ASSERTION THE HARD RULE ASKS FOR. Four commands have existed since step 4; this is the
     first thing in the repo that says a person can reach them. */
  await expect(page.getByRole('button', { name: 'Check cost' })).toBeVisible()

  await page.locator('.run-row').first().click()
  await expect(page.locator('.run-open')).toBeVisible()

  /* All four steps are drawn, not just the one the run is waiting for. A screen that showed
     only the current phase would leave the operator unable to see that emit exists until join
     had finished — and the four together are what makes D1's two-phase split legible. */
  const titles = await page.locator('.run-step-title').allInnerTexts()
  expect(titles).toEqual(['Identify', 'Join', 'Emit', 'Reconcile'])
})

test('which steps cost money is on the heading line, not buried in the prose', async ({
  page,
}) => {
  await open(page)
  await openPanel(page)
  await expect(page.locator('.run-step-money')).toHaveText('Costs money')

  await page.locator('.run-row').first().click()
  await expect(page.locator('.run-open')).toBeVisible()
  /* `allTextContents` and not `allInnerTexts`: the stylesheet uppercases these labels, and
     `innerText` returns what is PAINTED while `textContent` returns what is written. The
     authored string is the claim worth asserting — a casing rule is a design choice this file
     has no business freezing, and `toHaveText` above reads textContent for the same reason. */
  const free = await page.locator('.run-step-free .run-step-cost').allTextContents()
  expect(free).toEqual(['Free · re-runnable', 'Free · re-runnable', 'Free · re-runnable'])
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

test('the confirm sends confirm:true and the scope the walk is showing', async ({ page }) => {
  const wire = await open(page)
  await openPanel(page)
  await page.getByRole('button', { name: 'Check cost' }).click()
  await page.locator('.run-button-money').click()
  await expect(page.locator('.run-quote')).toHaveCount(0)

  const spend = wire.find((row) => row.path === '/pipeline/identify')
  expect(spend).toBeTruthy()
  const body = spend?.body as Record<string, unknown>
  expect(body.confirm).toBe(true)
  expect(body.box).toBe(9)
  /* No ticked cards, so the run is the whole box and `indices` is absent — which the route
     reads as the whole box. An empty ARRAY would be refused there, deliberately, and the
     screen must never send one. */
  expect(body.indices).toBeUndefined()
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
  await expect(page.locator('.run-blocked')).toContainText('already identifying these cards')
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

test('an import file is offered as a download, which is the gap Gate B left open', async ({
  page,
}) => {
  await open(page)
  await openPanel(page)
  await page.locator('.run-row').first().click()

  /* docs/GATES.md, on what Gate B did not close: emit's import files existed only as filenames
     in terminal output the owner never saw. This is the link that closes it. */
  const file = page.locator('.run-file-import')
  await expect(file).toBeVisible()
  await expect(file).toContainText('import-listed.csv')
  await expect(file).toHaveAttribute('download', 'import-listed.csv')
  expect(await file.getAttribute('href')).toContain('/pipeline/runs/')
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
