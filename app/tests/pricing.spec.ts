import { test, expect, type Locator, type Page } from '@playwright/test'
import { settleFonts } from './fontsReady'
import { sealEveryTest } from './shell'

import type {
  HistoryRange,
  PriceHistoryPayload,
  PricingSku,
  TrendRange,
  TrendsPayload,
} from '../src/types'

/* THE PRICING SCREEN, ASSERTED WHERE NOTHING ELSE CAN SEE IT.
 *
 * `CLAUDE.md`'s hard rule — "A ROUTE IS NOT A FEATURE" — and `docs/GATES.md` step 7's account
 * of 7b shipping with three screens missing from the ROUTES table while harness, lint,
 * typecheck and docs-audit were ALL green. Only `make design-check` could tell, and it is
 * deliberately not on the commit path. This file is that check for `#/pricing`.
 *
 * THE STRONGEST CASES HERE ARE ABSENCES, and that is the form a later refactor cannot quietly
 * satisfy: a suggested row writes NO key, a Tab across one writes NOTHING, a snap onto a
 * blank column writes NOTHING, and the screen draws NO solid accent fill anywhere. Each of
 * those is a rule that would otherwise live only in a comment.
 *
 * WHY THE SUGGESTION MUST NOT BE WRITTEN, since it is the case this file spends the most on:
 * an override is layer 1 of `pipeline/join.py:prices_for` and beats the run's rule at layer 4.
 * A screen that wrote its hundred suggestions into `overrides` would produce a run where
 * changing the preset silently changed nothing — a failure with no symptom. `pipeline/
 * decisions.py` says it in one line: "Nothing here is ever defaulted on your behalf — that is
 * the entire point."
 *
 * NO REAL REQUEST IS EVER MADE. Every route is intercepted; the PUT that writes
 * `inventory/prices.json` is recorded rather than performed, which is what lets these cases
 * assert what the screen WOULD have written.
 *
 * NOT A HARNESS TEST AND MUST NOT BECOME ONE. `docs/GATES.md`'s contract is seven Python tests
 * at the Stop hook; this starts a browser.
 */

const VIEW_ROUTE = '/#/pricing?run=2026-08-30-box7-01'
const VIEW = 'main.pricing'
const RUN = '2026-08-30-box7-01'

type Wire = { method: string; path: string; body: unknown }

/** One SKU in the shape `cli/cmd_join.py:_pricing_table` writes — every field, not the handful
 *  a given case reads. A partial fixture here does not fail partially: the row reads
 *  `row['Number']` and `positions[0]`, so a record missing either takes the screen down and
 *  every assertion below fails with "element not found", which reads exactly like an
 *  unregistered route.
 *
 *  IT IS TYPED, AND IT WAS NOT UNTIL D59 ADDED TWO FIELDS NOBODY NOTICED WERE MISSING. This
 *  read `over: Record<string, unknown>` returning an un-annotated literal, so `PricingSku` was
 *  never applied to the fixture in either direction: `copies_out` and `nothing_to_add` were
 *  added to the wire and to the type, the fixture stayed on the old shape, and `tsc` had
 *  nothing to say about it — which is how the at_cap case below came to exercise the FALLBACK
 *  while reading as coverage of the sentence. `Partial<PricingSku>` also makes an override that
 *  reaches no field an error rather than a no-op; it caught one (`market`), inert since the
 *  case was written. */
function sku(over: Partial<PricingSku> = {}): PricingSku {
  const base: PricingSku = {
    sku: '8608859',
    game: 'pokemon',
    row: {
      'TCGplayer Id': '8608859',
      'Product Line': 'Pokemon',
      'Set Name': 'SV: Prismatic Evolutions',
      'Product Name': 'Articuno - 161/159',
      Title: '',
      Number: '161/159',
      Rarity: 'Secret Rare',
      Condition: 'Near Mint Holofoil',
      'TCG Market Price': '22.03',
      'TCG Direct Low': '21.98',
      'TCG Low Price With Shipping': '22.98',
      'TCG Low Price': '21.98',
      'Total Quantity': '0',
      'Add to Quantity': '0',
      'TCG Marketplace Price': '',
      'Photo URL': '',
    },
    bucket: 'listable',
    copies: 3,
    add_to_quantity: 3,
    backstock: 0,
    live_before: 0,
    committed: 0,
    /* D59's two. `copies_out` is what the cap is spent against — live plus pending, per SKU
       and across every box — and it is `>= live_before` always. `nothing_to_add` is null on
       the ordinary row, which is the row that ADDS one; a case about a row that does not
       overrides both. */
    copies_out: 0,
    nothing_to_add: null,
    at_cap: false,
    condition: 'Near Mint Holofoil',
    set_name: 'SV: Prismatic Evolutions',
    name: 'Articuno - 161/159',
    snap: {
      market: '22.03',
      direct_low: null,
      low: '21.98',
      low_with_shipping: '22.98',
      now: null,
    },
    presets: {
      market_match: '22.03',
      market_undercut_5: '20.93',
      low_undercut_1: '21.76',
    },
    rule_price: '22.03',
    positions: [
      { box: 7, index: 1, label: 'Box 7 · Section 1 · Card 1' },
      { box: 7, index: 2, label: 'Box 7 · Section 1 · Card 2' },
      { box: 7, index: 3, label: 'Box 7 · Section 1 · Card 3' },
    ],
    listing: null,
  }
  return { ...base, ...over }
}

async function open(
  page: Page,
  options: {
    skus?: unknown[]
    decisions?: Record<string, unknown> | null
    /** Whether the run already carries an emit record — the double-press guard's input. */
    emitted?: boolean
    /** The run LIST, for cases about the picker rather than about a table. Each entry is the
     *  handful of `RunSummary` fields a chip draws; everything else is filled in below, so a
     *  case names what it is about and nothing more. */
    runs?: {
      run: string
      box: number | null
      box_name: string | null
      skus: number
      created_at?: string | null
    }[]
    /** Land with NO run selected, which is the only state the picker is drawn in. The default
     *  route carries `?run=` and goes straight to the table. */
    noRun?: boolean
    /** What `GET .../history` answers. `'refuse'` answers a named refusal, so the panel's
     *  failure arm is exercised against the same shape a real server sends. */
    history?: unknown | 'refuse'
    /** What `GET .../trends` answers for the SKUs a chunk asks about — D79. A function, not a
     *  payload, because the client CHUNKS the walk and the interesting cases are about which
     *  SKUs each request carries. */
    trends?: (skus: string[]) => unknown
    /** THE WORKLIST OVER SEVERAL RUNS (D86). A case that names this is asking about the merge
     *  itself — which run holds which copy, and what each one answers — so it hands over the
     *  whole thing rather than being assembled from `skus` and `runs` above. Every other case
     *  gets a one-run worklist synthesised from those two, which is what keeps the fifty cases
     *  written before D86 passing unchanged against a screen that now reads a different route. */
    worklist?: {
      runs: { run: string; box: number | null; box_name: string | null; skus: number }[]
      skus: (PricingSku & {
        in: { run: string; add_to_quantity?: number }[]
        claimed_add?: number
        over_cap?: boolean
      })[]
    }
    /** Copies each run still holds that TCGplayer does not, by run name
     *  (D156). A run with one is OPEN whatever it owes; the chip says how
     *  many. */
    unsent?: Record<string, number>
    /** What no worklist can send, as the server names it. */
    unreachable?: { captured: number; in_review: number; unjoined: { run: string; cards: number }[]; reallocated: { run: string; box: number | null; cards: number | null }[] }
    /** WHICH ANSWERS A MASS-CLEAR MAY REMOVE, as the server names them — SKU to age in whole
     *  days, or `null` for one carrying no readable date
     *  (D168). It rides the ENVELOPE of `GET /pricing`, so a
     *  case that sets it is stating what the server says rather than what the screen worked
     *  out: the screen decides nothing about membership, which is the property these cases
     *  exist to hold. Absent means a server that predates the route, and the control is then
     *  not offered at all. */
    clearable?: { days: Record<string, number | null>; holds: number; unknown: number }
    /** What `POST /pricing/clear` answers. A function of the request body, because the
     *  interesting cases are about WHAT THE SCREEN SENT — the scope and the window — and a
     *  fixed payload could not tell a store-wide press from a scoped one. */
    clear?: (body: Record<string, unknown>) => unknown
    /** HOLD `GET /pipeline/pricing` OPEN THIS LONG BEFORE ANSWERING, so a case can assert what
     *  draws WHILE the worklist fetch is still in flight — the "Nothing loaded." caption used
     *  to render through exactly this window, asserting a completed empty answer during a
     *  request that had not finished. */
    pricingDelayMs?: number
  } = {},
): Promise<Wire[]> {
  const wire: Wire[] = []

  /* THE RUN'S OWN DETAIL, for the files and the phase. Note the ORDER of these route
     registrations matters: this pattern must be registered BEFORE the bare
     `/pipeline/runs/<name>` one below would swallow it, and Playwright matches most-recent
     first, so the specific patterns go last. */
  await page.route(/\/pipeline\/runs\/[^/]+\/emit$/, async (route) => {
    wire.push({
      method: 'POST',
      path: new URL(route.request().url()).pathname,
      body: route.request().postDataJSON(),
    })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        step: 'emit',
        run: RUN,
        console: 'listed           1 row(s), 1 card(s)',
        files: [{ name: 'import-listed.csv', bytes: 2048, modified: 0, is_import: true }],
        summary: { run: RUN, phase: 'reconcile' },
      }),
    })
  })

  /* THE MERGED SEND (D86), which is a DIFFERENT ROUTE and had no stub at all until the cap
     landed. `POST /pipeline/emit` takes a list of runs rather than living under one, so the
     pattern above cannot reach it — its `[^/]+` needs a `/pipeline/runs/` in front — and the
     press that fires it went unexercised while two cases asserted only whether its button was
     drawn. Registered here so the body a send composes is readable in `wire`. */
  await page.route(/\/pipeline\/emit$/, async (route) => {
    wire.push({
      method: 'POST',
      path: new URL(route.request().url()).pathname,
      body: route.request().postDataJSON(),
    })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        exit_code: 0,
        runs: [RUN],
        run: RUN,
        console: 'listed           2 row(s), 2 card(s)',
        files: [{ name: 'import.csv', bytes: 2048, modified: 0, is_import: true }],
        summary: { run: RUN, phase: 'reconcile' },
      }),
    })
  })

  /* THE PRICE HISTORY (D62). Registered among the specific patterns for the reason the
     comment above gives — Playwright matches most-recent-first, so `[^/]+$` must not get
     there first. Every case that presses `T` reads `wire` to count how many times this was
     asked, because the load-bearing property of that panel is that it does NOT fire on a
     walk. */
  /* D79's batched read. Registered BEFORE `/history` so Playwright's most-recent-first
     matching puts the more specific pattern first — `/history`'s regex is unanchored and
     would not match `/trends` in any case, but the ordering rule this file states above is
     kept true rather than relied on to be harmless. */
  await page.route(/\/pipeline\/runs\/[^/]+\/trends/, async (route) => {
    const url = new URL(route.request().url())
    const asked = url.searchParams.getAll('sku')
    /* THE QUERY VERBATIM, because `sku` REPEATS on this route rather than carrying a comma
       list — `/scope`'s own rule, for its reason: a comma inside a value is indistinguishable
       from the separator. A stub that flattened the repeats to `a,b,c` here would have to be
       un-flattened by every case that reads it, with `String.split(',')` — the exact call
       `app/eslint.config.js` refuses, and refuses because getting it wrong on real data is v1
       bug 2. `URLSearchParams` is the reader. */
    wire.push({ method: 'GET', path: `${url.pathname}${url.search}`, body: null })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify((options.trends ?? trends)(asked)),
    })
  })

  await page.route(/\/pipeline\/runs\/[^/]+\/history/, async (route) => {
    const url = new URL(route.request().url())
    wire.push({
      method: 'GET',
      path: `${url.pathname}?sku=${url.searchParams.get('sku')}`,
      body: null,
    })
    if (options.history === 'refuse') {
      await route.fulfill({
        status: 409,
        contentType: 'application/json',
        /* THE ENVELOPE THE CAPTURE SERVER ACTUALLY SENDS — `{error: {code, message}}`, which
           `app/src/server.ts:errorEnvelope` is the only reader of. A stub with a flatter
           shape falls through to the invented `http_error` message, so the panel would draw
           `409 Conflict from …` and this case would pass while asserting nothing about the
           sentence the server wrote. */
        body: JSON.stringify({
          error: {
            code: 'not_catalogued',
            message: 'Vilemaw is not in a catalogued product line.',
          },
        }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(options.history ?? history()),
    })
  })

  /* THE MASS-CLEAR AND ITS WAY BACK (D168). Registered
     BEFORE the bare `/pricing$` pattern below, which Playwright would otherwise never reach
     for these — it matches most-recent-first, so the specific patterns go LAST and the two
     here are more specific than the one they sit above only by being registered later. They
     are `/pricing/clear` and `/pricing/restore`, which `/\/pricing$/` does not match, so the
     ordering is belt and braces rather than load-bearing.

     EVERY ROUTE THE SCREEN CALLS MUST BE STUBBED OR THE SUITE FAILS BY NAME: `shell.ts`'s
     `sealCapture` records every unstubbed request to this checkout's capture port and asserts
     the roster is empty afterwards. */
  await page.route(/\/pricing\/clear$/, async (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>
    wire.push({ method: 'POST', path: '/pricing/clear', body })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        options.clear?.(body) ?? {
          ok: true,
          cleared: {},
          count: 0,
          holds: 0,
          unknown: 0,
          undated: 0,
          answers: 0,
          revision: 'rev-cleared',
        },
      ),
    })
  })
  await page.route(/\/pricing\/restore$/, async (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>
    wire.push({ method: 'POST', path: '/pricing/restore', body })
    const answers = (body.answers ?? {}) as Record<string, unknown>
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        restored: Object.keys(answers),
        skipped: [],
        revision: 'rev-restored',
      }),
    })
  })

  /* THE PRICING CORPUS — one document for the store, and the answer (D86, amended).
     Cases still name `decisions` because that is what a run's answers were called, and the
     fixture projects it into the corpus the screen reads. That keeps every case written
     before the move saying what it always said: "this SKU is answered thus". */
  await page.route(/\/pricing$/, async (route) => {
    if (route.request().method() === 'PUT') {
      wire.push({
        method: 'PUT',
        path: '/pricing',
        body: route.request().postDataJSON(),
      })
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, written: '/tmp/prices.json', answers: 1, revision: 'rev-2' }),
      })
    }
    const answers =
      options.decisions === undefined
        ? { rule: 'match', basis: 'market', sub_threshold: null, overrides: {} }
        : options.decisions
    const skus: Record<string, unknown> = {}
    for (const [sku, value] of Object.entries(
      (answers?.overrides ?? {}) as Record<string, unknown>,
    )) {
      skus[sku] = { value }
    }
    for (const [sku, value] of Object.entries(
      (answers?.no_market_data ?? {}) as Record<string, unknown>,
    )) {
      skus[sku] = { value, channel: 'unknown' }
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        corpus: {
          version: 1,
          policy: {
            rule: answers?.rule ?? 'match',
            basis: answers?.basis ?? 'market',
            /* THE SERVER NEVER ANSWERS NULL HERE (D9, amended 2026-09-02): a policy the file
               leaves silent reads as the store default, flat $0.49, and `Corpus.parse` applies
               it before anything is served. A case that hands over `null` gets the default,
               which is what the real route would give it. */
            sub_threshold: answers?.sub_threshold ?? { flat: '0.49' },
            /* THE CUT-OFF AS THE STORE HOLDS IT. Absent means never written, which is the
               ordinary case and the one the server answers with its own default; a case that
               sets it is testing a store that has chosen. Threaded through `decisions` rather
               than added as a top-level option so a fixture states one policy in one place. */
            ...(answers?.threshold === undefined ? {} : { threshold: answers.threshold }),
          },
          skus,
        },
        path: '/tmp/prices.json',
        revision: 'rev-1',
        /* BESIDE THE DOCUMENT AND NEVER INSIDE IT. `PUT /pricing` sends `corpus` back
           wholesale and the server round-trips keys it does not recognise, so a derived block
           written into the document would be stored in `inventory/prices.json`. Absent unless
           a case names it, which is the pre-route server and the state that hides the
           control. */
        ...(options.clearable === undefined ? {} : { clearable: options.clearable }),
      }),
    })
  })

  /* THE CROSS-RUN WORKLIST — the route the screen actually reads since D86.
     `/pipeline/runs/<name>/pricing` below is left registered and is no longer called by the
     app; it stays because `do_pipeline_pricing` is still a route the server serves and one
     case still exercises the refusal shape through it.

     A ONE-RUN WORKLIST IS THE DEFAULT, AND THAT IS WHY THE OLDER CASES STILL READ. Each SKU
     becomes a merged row over a single leg, which is exactly what the server answers for a
     worklist of one — so `skus`, `runs` and `emitted` keep meaning what they meant, and only
     a case that hands over `worklist` is testing the merge. The answers are NOT on this
     payload: they are the corpus's, read through `/pricing` above. */
  await page.route(/\/pipeline\/pricing/, async (route) => {
    if (options.pricingDelayMs !== undefined) await new Promise((r) => setTimeout(r, options.pricingDelayMs))
    const listed = options.worklist?.runs ??
      options.runs ?? [{ run: RUN, box: 7, box_name: 'Riftbound epics', skus: 1 }]
    const rows =
      options.worklist?.skus ??
      ((options.skus ?? [sku()]) as PricingSku[]).map((row) => ({
        ...row,
        in: [{ ...row, run: RUN }],
        claimed_add: row.add_to_quantity,
        over_cap: false,
      }))
    const summary = (row: {
      run: string
      box: number | null
      box_name: string | null
      skus: number
      created_at?: string | null
    }) => ({
      run: row.run,
      path: `/tmp/runs/${row.run}`,
      box: row.box,
      box_name: row.box_name,
      created_at: row.created_at ?? null,
      live: false,
      phase: options.emitted === true ? 'reconcile' : 'emit',
      joined: true,
      collected: true,
      counts: { skus: row.skus, cards_in: 3, queued_main: 0, queued_parked: 0 },
      batch_ids: [],
      usage: {},
    })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        runs: options.noRun === true && listed.length === 0 ? [] : listed.map(summary),
        roster: listed.map((row) => ({
          ...summary(row),
          owes: options.emitted === true ? [] : ['never emitted'],
          open: options.emitted !== true || (options.unsent?.[row.run] ?? 0) > 0,
          unsent: options.unsent?.[row.run] ?? 0,
        })),
        skus: options.noRun === true && listed.length === 0 ? [] : rows,
        written_at: {},
        skipped: [],
        asked: [],
        threshold: '0.40',
        floor: '0.40',
        ...(options.unreachable === undefined ? {} : { unreachable: options.unreachable }),
      }),
    })
  })

  await page.route(/\/pipeline\/runs\/[^/]+\/pricing$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        run: RUN,
        pricing: {
          run: RUN,
          threshold: '0.40',
          floor: '0.40',
          rule: 'match',
          basis: 'market',
          presets: ['market_match', 'market_undercut_5', 'low_undercut_1'],
          games: [
            {
              game: 'pokemon',
              import_listed: 'import-listed.csv',
              import_subthreshold: 'import-subthreshold.csv',
            },
          ],
          skus: options.skus ?? [sku()],
          bands: [],
        },
        decisions:
          options.decisions === undefined
            ? { rule: 'match', basis: 'market', sub_threshold: null, overrides: {} }
            : options.decisions,
      }),
    })
  })

  /* THE RUN DETAIL — its files and its phase, which is where the double-press guard reads
     whether this run has emitted. `[^/]+$` cannot swallow `/pricing`, `/decisions` or
     `/emit`, because a path segment holds no slash. */
  await page.route(/\/pipeline\/runs\/[^/]+$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        run: RUN,
        path: `/tmp/runs/${RUN}`,
        /* WHICH DRAWER, AND WHAT THE OWNER CALLS IT (D56). Both routes carry it because both
           are `_summary` server-side, and this screen prefers the DETAIL: it is what Reload
           re-reads, so a box renamed on `#/inventory` reaches the header on a press. */
        box: 7,
        box_name: 'Riftbound epics',
        live: false,
        phase: options.emitted === true ? 'reconcile' : 'emit',
        joined: true,
        collected: true,
        counts: { skus: 1, cards_in: 3, queued_main: 0, queued_parked: 0 },
        batch_ids: [],
        usage: {},
        console: '',
        files:
          options.emitted === true
            ? [{ name: 'import-listed.csv', bytes: 2048, modified: 0, is_import: true }]
            : [],
        manifest: options.emitted === true ? { emitted: { listed: ['8608859'] } } : {},
      }),
    })
  })

  await page.route(/\/pipeline\/runs$/, async (route) => {
    const listed = options.runs ?? [
      { run: RUN, box: 7, box_name: 'Riftbound epics', skus: 1 },
    ]
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        runs: listed.map((row) => ({
          run: row.run,
          path: `/tmp/runs/${row.run}`,
          box: row.box,
          box_name: row.box_name,
          live: false,
          phase: 'emit',
          /* EVERY FIXTURE RUN IS JOINED, because the picker filters on it — an unjoined run
             has no `pricing.json` and therefore nothing to price. A case wanting the empty
             state passes `runs: []`. */
          joined: true,
          collected: true,
          counts: { skus: row.skus, cards_in: 3, queued_main: 0, queued_parked: 0 },
          batch_ids: [],
          usage: {},
        })),
      }),
    })
  })

  await page.route(/\/photo\//, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'image/svg+xml',
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="63" height="88"/>',
    })
  })

  /* THE WINDOW ON EACH ROW'S CARD, WHICH THIS FILE NEVER STUBBED. `Pricing.tsx:pumpCrops`
     POSTs `/pipeline/crop-preview` once per row it draws — free, and the same detector the
     batch reading uses — so every case in this file was sending a POST per row to whatever
     answers the capture port. `sealEveryTest` named it.

     THE RECT IS THE ONE `run-panel.spec.ts` USES, and it is chosen to divide cleanly: the
     screen turns frame pixels into percentages, so 216/2160 is 10% and 1944/2160 is 90%. What
     matters here is only that a rect ARRIVES — `pumpCrops` writes a `CropRead` when
     `rect`, `frame` and a null `crop_refused` all hold, and draws the row uncropped otherwise.
     Before this stub every row took the `catch`, so the whole file measured the uncropped
     render; with it they take the cropped one, which is what the operator sees. */
  await page.route(/\/pipeline\/crop-preview$/, async (route) => {
    const body = route.request().postDataJSON() as { indices?: number[]; box?: number } | null
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        scope: { box: body?.box ?? 7, whole_box: false, cards: body?.indices ?? [1] },
        capture_dir: '/tmp/captures/cards/box7',
        crop: true,
        max_edge: 256,
        total: 3,
        offset: 0,
        sample: {
          box: body?.box ?? 7,
          index: body?.indices?.[0] ?? 1,
          game: 'pokemon',
          frame: [2160, 3840],
          sent: [144, 256],
          rect: [216, 384, 1944, 3456],
          method: 'edges',
          crop_refused: null,
        },
      }),
    })
  })

  await page.goto(options.noRun === true ? '/#/pricing' : VIEW_ROUTE)
  await settleFonts(page)
  await expect(page.locator(VIEW)).toBeVisible()
  await settleEnter(page)
  return wire
}

/** The page's enter animation, finished.
 *
 *  THE SAME ARGUMENT `fontsReady.ts` MAKES ABOUT THE SWAP WINDOW. `.bn-page` slides its
 *  content in over `--bn-t-slow`, and a TRANSFORM on `main` makes it the containing block for
 *  everything inside — including the sticky ship bar, which is displaced for as long as the
 *  animation runs. The hit-testing cases below ask who owns a pixel; asked mid-animation they
 *  are asking about a layout that is still moving, and one of them caught a row under a bar
 *  that had not settled yet. It weakens nothing: no threshold moves, and a bar that really is
 *  punched through is still punched through once it has stopped. */
async function settleEnter(page: Page): Promise<void> {
  await page.waitForFunction(() => {
    const main = document.querySelector('main')
    return main !== null && main.getAnimations().every((one) => one.playState === 'finished')
  })
}

/** A reading in the shape `server/pipeline_routes.py:do_pipeline_history` answers.
 *
 *  THE NUMBERS ARE VILEMAW'S, READ LIVE ON 2026-08-30, and the two ranges point OPPOSITE
 *  WAYS on purpose — up 71.2% over the month, down 33.9% over the year. That is the real
 *  shape of the card and it is the case the panel's overlap sentence exists for; a fixture
 *  where both ranges agreed would let a screen that silently merged them pass. */
function history(over: Partial<PriceHistoryPayload> = {}): PriceHistoryPayload {
  const range = (
    name: string,
    vwap: string,
    fraction: string,
    points: number[],
  ): HistoryRange => ({
    range: name,
    buckets: points.length,
    from: '2026-08-01',
    to: '2026-08-30',
    latest_market: '23.63',
    vwap,
    bound: { low: '16.02', high: '22.13', width_of_vwap: '0.3248', width_of_low: '0.3814' },
    momentum: { early: '13.99', late: '23.95', change: '9.96', fraction, window: 5 },
    liquidity: 642,
    transactions: 528,
    units_per_transaction: '1.216',
    dispersion: '6.11',
    points: points.map((market, at) => ({
      at: `2026-08-${String(at + 1).padStart(2, '0')}`,
      market: String(market),
      quantity: 3,
      low: '12.00',
      high: '24.00',
    })),
  })
  return {
    run: RUN,
    sku: '8608859',
    product_id: 684125,
    name: 'Articuno',
    set_name: 'SV: Prismatic Evolutions',
    condition: 'Near Mint Holofoil',
    market: '22.03',
    ranges: [
      range('month', '18.81', '0.7119', [13.58, 15.2, 18.4, 21.9, 23.63]),
      range('annual', '21.50', '-0.3389', [29.15, 26.0, 24.0, 21.0, 19.27]),
    ],
    never_sold: false,
    ...over,
  }
}

/** What the batched route answers for one chunk — D79.
 *
 *  IT ANSWERS ONLY WHAT IT WAS ASKED, which is the property the cases about chunking turn
 *  on: the client walks the open rows eight at a time, and a stub that answered every SKU to
 *  every request would make a walk that asked for the wrong ones pass. */
function trends(asked: string[]): TrendsPayload {
  const range = (name: string, fraction: string, points: number[]): TrendRange => ({
    range: name,
    from: name === 'month' ? '2026-08-01' : '2025-09-08',
    to: '2026-08-30',
    fraction,
    points: points.map((p) => String(p)),
  })
  return {
    run: RUN,
    asked: asked.length,
    skipped: 0,
    skus: Object.fromEntries(
      asked.map((sku) => [
        sku,
        {
          product_id: 684125,
          ranges: [
            range('month', '0.7119', [13.58, 15.2, 18.4, 21.9, 23.63]),
            range('annual', '-0.3389', [29.15, 26.0, 24.0, 21.0, 19.27]),
          ],
        },
      ]),
    ),
    refused: {},
  }
}

const strip = (page: Page) => page.locator('.pricing-row .pricetrend')
const loadTrends = (page: Page) => page.getByRole('button', { name: /Load trends|Read again/ })

const field = (page: Page) => page.getByRole('textbox', { name: /^Price for / })

/** The answers the last `PUT /pricing` carried, as `{sku: value}`.
 *
 *  ONE SHAPE READ IN ONE PLACE. Every case below used to reach into `body.decisions.overrides`
 *  by hand; the answers moved into the corpus (D86, amended) and nineteen assertions would
 *  otherwise each have learned the new path. The values are D49's own shapes, unchanged — a
 *  string for a price, an object for a hold — so what a case asserts is what it always did. */
function sentAnswers(wire: Wire[]): Record<string, unknown> {
  const put = wire.filter((row) => row.method === 'PUT').pop()?.body as {
    corpus?: { skus?: Record<string, { value: unknown }> }
  }
  return Object.fromEntries(
    Object.entries(put?.corpus?.skus ?? {}).map(([sku, row]) => [sku, row.value]),
  )
}

/** The policy the last `PUT /pricing` carried — `rule`, `basis`, `sub_threshold`. */
function sentPolicy(wire: Wire[]): Record<string, unknown> {
  const put = wire.filter((row) => row.method === 'PUT').pop()?.body as {
    corpus?: { policy?: Record<string, unknown> }
  }
  return put?.corpus?.policy ?? {}
}

// ------------------------------------------------------------------ it is reachable

/* NOTHING HERE MAY REACH THE CAPTURE SERVER, AND THE SHELL'S OWN READ IS NOT THIS SCREEN'S.
   `app/tests/shell.ts` carries the argument; the call has to sit above every hook and every
   case in the file, which is what `make docs-audit`'s `spec seal` row checks. */
sealEveryTest()

test('the screen is on its own route and draws the run it was linked to', async ({ page }) => {
  await open(page)

  await expect(page.locator('.pricing-title')).toHaveText('Pricing')
  await expect(page.locator('.pricing-scope')).toContainText(RUN)
  /* THE RUN CAME FROM THE URL, NOT FROM STORAGE (D49). `#/runs` links a specific run through
     the hash rather than through a second `sessionStorage` key with its own clearing rules —
     a run name has one source of truth, so nothing here can disagree with anything. */
  await expect(page.locator('.pricing-row')).toHaveCount(1)

  /* AND IT NAMES THE DRAWER (D56). This line read `<run> · N SKUs` — a directory and a count,
     never what is in the box — which is the complaint that produced D56, in the place the
     owner was looking when they made it. The run name STAYS: it is what `emit` and `join` are
     pointed at and what `decisions.json` is written under. What is new goes in front of it. */
  const scope = page.locator('.pricing-scope')
  await expect(scope).toContainText('Box 7 · Riftbound epics')
  await expect(scope).toContainText(RUN)
  await expect(scope).toContainText('1 SKUs')
  /* NOT `toHaveText` ANY MORE, and the reason is that the lede gained a fourth fact rather
     than lost one: it carries the worklist's own progress now, so an exact string would be
     pinning the progress reading as well as the three facts this case is about. Each is
     asserted on its own instead, which fails on a dropped box name exactly as the whole
     string did. */
})

test('the run picker leads with the box, and the directory is what tells two runs apart', async ({
  page,
}) => {
  /* THE OWNER'S OWN STORE IS THE CASE: box 1 carries TWO joined runs, so the headline is
     identical on two chips and the date beneath is the only thing separating them. That is
     what stops the run name being demoted out of usefulness when the box takes the top line —
     `docs/DESIGN.md`'s human-label-large, machine-string-small rule, which the review queue
     already applies to its reason codes, pointed at a picker. */
  await open(page, {
    runs: [
      /* ONE SITTING OVER TWO DRAWERS, WHICH IS D48's CART AS IT ACTUALLY LANDS — the owner's
         2026-09-01 send joined three boxes in the same SECOND, so `created_at` cannot separate
         them and the box number is what orders them. Given here out of order deliberately: the
         server answers in directory order and the strip is what puts them on a shelf. */
      { run: '2026-08-30-box3-01', box: 3, box_name: 'RB Epics', skus: 15, created_at: '2026-08-30T07:37:30+00:00' },
      { run: '2026-08-30-box1-04', box: 1, box_name: 'UNL Rares', skus: 20, created_at: '2026-08-30T07:37:30+00:00' },
      { run: '2026-08-29-box1-01', box: 1, box_name: 'UNL Rares', skus: 50, created_at: '2026-08-29T22:37:47+00:00' },
      /* A BOX WITH NO NAME. D20 leaves a name optional, so this is an ordinary box and its
         chip must draw the number ALONE — no separator, no placeholder. */
      { run: '2026-08-24-box2-01', box: 2, box_name: null, skus: 108, created_at: '2026-08-24T01:55:52+00:00' },
    ],
    noRun: true,
  })

  /* THE PICKER IS A POPOVER OFF THE HEADER NOW rather than a strip standing on the page.
     Which runs are being priced is a question you ask once a session, and the answer is drawn
     in the lede either way — so it is opened here rather than asserted into existence. */
  await page.getByRole('button', { name: /^Runs/ }).click()
  const chips = page.locator('.pricing-run')
  await expect(chips).toHaveCount(4)

  /* NEWEST SITTING FIRST, AND BOXES ASCENDING INSIDE IT (D86). `GET /pipeline/runs` sorts by
     directory name REVERSED, so within one day the picker drew box 5, box 4, box 3 — backwards
     against the rule `Runs.tsx` states for the same choice: *"Boxes ascending, which is the
     order they sit on a shelf and the order the strip on `#/inventory` already draws."* Two
     screens ordering the same drawers two ways is the drift; this is the fix, and it is pinned
     here because it is otherwise invisible. */
  await expect(chips.nth(0).locator('.pricing-run-name')).toContainText('Box 1 · UNL Rares')
  await expect(chips.nth(1).locator('.pricing-run-name')).toContainText('Box 3 · RB Epics')
  await expect(chips.nth(2).locator('.pricing-run-name')).toContainText('Box 1 · UNL Rares')
  await expect(chips.nth(3).locator('.pricing-run-name')).toContainText('Box 2')

  /* THE DIRECTORY IS STILL DRAWN, and on the two chips whose headline is identical it is the
     whole of the difference. An assertion on the headline alone would go green against a chip
     that had dropped the run name entirely. */
  await expect(chips.nth(0).locator('.pricing-run-id')).toHaveText('2026-08-30-box1-04')
  await expect(chips.nth(2).locator('.pricing-run-id')).toHaveText('2026-08-29-box1-01')
  await expect(chips.nth(1)).toContainText('15 SKUs')

  /* AN UNNAMED BOX DRAWS ITS NUMBER ALONE — no separator, no placeholder (D20). Asserted on
     the whole headline rather than with `toContainText`, because that is the half a
     `Box 2 · —` regression would still satisfy. The day is appended by the chip, so the
     assertion names it. */
  await expect(chips.nth(3).locator('.pricing-run-name')).toHaveText('Box 2 · Aug 23')

  /* WHAT IS LEFT, WHICH THE CHIP COULD NOT SAY BEFORE D86. `counts.skus` is the SIZE of a job
     and never the job: box 2's 108 SKUs are one `floor` press. This fixture's runs have not
     emitted, so every chip owes that. */
  await expect(chips.nth(0).locator('.pricing-run-owes')).toHaveText('Never emitted')
})

test('an emitted run with copies still unsent stays open, and the chip counts them', async ({
  page,
}) => {
  /* THE STRANDED SHAPE (D156). Two runs, both emitted, both answered. Under
     the old rule both chips read "Answered" and neither was on the default landing — and the
     148 copies the first had held back under a cap were reachable from no screen. The server
     counts `unsent` against the live store now; the picker draws it, and only a run with none
     left reads as done. */
  await open(page, {
    noRun: true,
    emitted: true,
    runs: [
      { run: '2026-08-24-box2-01', box: 2, box_name: 'Pokemon bulk', skus: 148, created_at: '2026-08-24T18:00:00+00:00' },
      { run: '2026-09-02-box6-01', box: 6, box_name: 'Riftbound rares', skus: 40, created_at: '2026-09-02T18:00:00+00:00' },
    ],
    unsent: { '2026-08-24-box2-01': 148 },
    /* THE OWNER'S OWN FOUR ROWS, 2026-09-12, AND THREE OF THEM ARE A FALSE ALARM. Two
       unjoined husks with no manifest counts at all, one reallocated run whose 53 cards went
       with box 1 on 2026-08-25, and one reallocated run holding 99 cards that are identified,
       priced and on a shelf. Counted as RUNS — which is how this line read until 2026-09-12 —
       all four produce the same two phrases and the operator cannot tell which is which. */
    unreachable: {
      captured: 214,
      in_review: 1,
      unjoined: [
        { run: '2026-09-11-box4-01', cards: 0 },
        { run: '2026-09-11-box4-02', cards: 0 },
      ],
      reallocated: [
        { run: '2026-08-22-box1-03', box: 1, cards: 0 },
        { run: '2026-08-29-box1-01', box: 1, cards: 99 },
      ],
    },
  })

  await page.getByRole('button', { name: /^Runs/ }).click()
  const chips = page.locator('.pricing-run')
  await expect(chips).toHaveCount(2)
  await expect(chips.nth(1).locator('.pricing-run-owes')).toHaveText('148 unsent')
  await expect(chips.nth(0).locator('.pricing-run-owes')).toHaveText('All sent')
  await expect(page.locator('.pricing-runs-count')).toHaveText('1 with work left · showing all of them')

  /* WHAT THE LIST CANNOT SEND IS NAMED ON THE DECK, each figure a door — AND THE FIGURE IS
     CARDS. The two zero-card husks and the zero-card reallocated run are withholding nothing,
     so they are not warned about; the one holding 99 sellable cards says the number. */
  const line = page.getByTestId('pricing-unreachable')
  await expect(line).toContainText('214 never identified')
  await expect(line).toContainText('1 in review')
  await expect(line).toContainText('99 in 1 run over a deleted box')
  await expect(line).not.toContainText('not joined')
  await expect(line).not.toContainText('2 runs over a deleted box')
  await expect(line.getByRole('link', { name: '1 in review' })).toHaveAttribute('href', '#/review')
})

test('an unknown card count is still warned about, and a known zero is not', async ({ page }) => {
  /* THE FALSE ALARM AND THE UNKNOWN, TOLD APART. `2026-08-22-box1-03` read 53 cards and holds
     none — they went with box 1 on 2026-08-25 — so there is nothing to rescue and nothing to
     say. A `null` count is a store the server could not open, which is not the same claim as
     nothing, so that row IS named and simply carries no figure.

     THE FIXTURE IS THE CASE ABOVE'S ON PURPOSE, changing only `unreachable`. Written with a
     thinner one this line did not render at all, and a `toHaveCount(0)` assertion passed for
     the wrong reason — the trap this repo already has a name for: a guard must see its subject.
     The non-zero `captured` is what puts the line on the screen, so every absence asserted
     below is an absence FROM a line that is provably there. */
  await open(page, {
    noRun: true,
    emitted: true,
    runs: [
      { run: '2026-08-24-box2-01', box: 2, box_name: 'Pokemon bulk', skus: 148, created_at: '2026-08-24T18:00:00+00:00' },
      { run: '2026-09-02-box6-01', box: 6, box_name: 'Riftbound rares', skus: 40, created_at: '2026-09-02T18:00:00+00:00' },
    ],
    unsent: { '2026-08-24-box2-01': 148 },
    unreachable: {
      captured: 214,
      in_review: 0,
      unjoined: [],
      reallocated: [
        { run: '2026-08-22-box1-03', box: 1, cards: 0 },
        { run: '2026-08-29-box1-01', box: 1, cards: null },
      ],
    },
  })

  const line = page.getByTestId('pricing-unreachable')
  await expect(line).toContainText('214 never identified')
  /* One of the two rows survives — the unknown — and it carries no figure, because there is no
     honest one to carry. The zero-card row is gone from the sentence entirely. */
  await expect(line).toContainText('1 run over a deleted box')
  await expect(line).not.toContainText('in 1 run over a deleted box')
  await expect(line).not.toContainText('2 runs')
})

test('every export column that carries data is on the row, once Compare is asked for', async ({ page }) => {
  await open(page)

  /* The owner's requirement in their own words: "I want all the data from the CSV shown when
     I make the decision" — still true, and still reachable: Ruling B (D208)
     moved three of the four behind a per-section Compare toggle so the default row is not a
     wall of reference prices, but the toggle is one press and nothing is deleted. The four
     price columns are the ones a subset would have dropped. Drawn Market, Low, +Ship, Direct
     left to right, once asked for. */
  await page.getByRole('button', { name: 'Compare' }).first().click()
  /* EACH COLUMN NAMES ITSELF ON THE ROW NOW — `Market $22.03` rather than a bare figure under
     a header — so the assertions carry the label. That is not a looser claim: it is the same
     four values, each still pinned exactly, with the column they belong to pinned as well,
     which is what a row of four unlabelled figures could never say. */
  const refs = page.locator('.pricing-ref')
  await expect(refs).toHaveCount(4)
  await expect(refs.nth(0)).toHaveText('Market $22.03')
  await expect(refs.nth(1)).toHaveText('Low $21.98')
  await expect(refs.nth(2)).toHaveText('+Ship $22.98')
  /* A BLANK CELL DRAWS AN EM DASH AND NOT `$0.00` — measured, TCG Direct Low is blank on
     2,060 of 2,476 listable rows, and D9 holds that a missing price is unknown, not low. */
  await expect(refs.nth(3)).toHaveText('Direct —')

  await expect(page.locator('.pricing-meta')).toContainText('Near Mint Holofoil')
  await expect(page.locator('.pricing-meta')).toContainText('Secret Rare')
})

// -------------------------------------------------- the suggestion writes nothing

test('a suggested row carries the rule price and writes no key at all', async ({ page }) => {
  const wire = await open(page)

  await expect(field(page)).toHaveValue('22.03')
  await expect(page.locator('.pricing-row')).toHaveAttribute('data-answer', 'suggested')

  /* THE LOAD-BEARING ABSENCE. An override is layer 1 of the ladder and beats the rule at
     layer 4, so a screen that wrote its suggestions would produce a run where changing the
     preset silently changed nothing. Nothing has been pressed; nothing may have been sent. */
  expect(wire.filter((row) => row.method === 'PUT')).toHaveLength(0)
})

// -------------------------------------------------- shipping the run (D54)

test('the sub-threshold policy is answered from the start, and the floor press writes it once', async ({
  page,
}) => {
  const wire = await open(page, {
    /* THE MARKET CELL AND THE BUCKET HAVE TO AGREE NOW, AND THIS FIXTURE USED TO CONTRADICT
       ITSELF. `bucket` alone put the row in the sub-threshold section for as long as the split
       was the server's alone; since the cut-off became a control the screen re-derives it from
       the Market cell, exactly as `pipeline/pricing.py:is_listable` does, so a row declared
       cheap while carrying a market of $22.03 was drawing in the listed half and the case was
       asserting a refusal that no longer applied.

       This is not a weakening of D28: what may not move a row is a price TYPED ON IT, and that
       is still true. What moves the sections is the cut-off, which is policy.

       An earlier version of this fixture carried `market: '0.12'` at the top level, where it
       reached no field of `PricingSku` and was inert from the day it was written. It is inside
       `snap` now, where the screen actually reads it. */
    skus: [
      sku({
        bucket: 'sub_threshold',
        snap: { market: '0.12', direct_low: null, low: '0.10', low_with_shipping: '1.10', now: null },
      }),
    ],
    decisions: { rule: 'match', basis: 'market', sub_threshold: null, overrides: {} },
  })

  /* THE REFUSAL IS GONE FROM THIS PATH, AND ITS ABSENCE IS WHAT THE CASE IS NOW FOR. `emit` used
     to refuse a run whose cheap cards had no disposition — `blocking` never consults `overrides`,
     so hand-pricing every row still left it refusing and the only surface for the answer was a
     JSON textarea on another route. D9's amendment gave the policy a default, so a store that has
     written nothing is ANSWERED from the start and the bar is content on arrival. What survives
     of the old assertion is the pair below: the panel says the figure is not written, and the
     verdict is not claiming otherwise. */
  /* THE VERDICT IS STATED ONCE, ON THE HEADLINE (Ruling A, D208) — the
     single-run ship bar no longer carries a second Ready/Not-yet pill or sentence, so this
     locator moves to `.pricing-deck-title`, the one place readiness is now said. */
  await expect(
    page.getByRole('region', { name: 'Whether the import files can be written' }).locator('.pricing-deck-title'),
  ).toHaveText('Ready to write')
  await expect(page.locator('.pricing-cheap .bn-pill')).toContainText('Default')

  /* THE ANSWER IS THE STORE'S, AND IT IS THE FIGURE ITSELF THAT IS TYPED. The panel used to
     offer a segmented row — "a flat price" or "the $0.40 floor" — beside a second small field,
     so the biggest thing on it was the one part you could not touch and the same number was
     drawn twice. The owner had the row removed and the figure made editable, which also ended
     the incoherence of a hardcoded "$0.40 floor" sitting beside an answer of $0.24.
     `sub_threshold: 'floor'` is no longer writable from any screen: the floor is stated by
     typing its own figure, which is a flat price like any other. */
  const cheap = page.getByLabel("Store default")
  await cheap.fill('0.40')
  await cheap.press('Enter')
  await expect.poll(() => wire.filter((r) => r.method === 'PUT').length).toBe(1)
  expect(sentPolicy(wire).sub_threshold).toEqual({ flat: '0.40' })

  /* ONE FIGURE, BOTH KEYS, AND THIS IS THE ASSERTION THAT KEEPS THEM ONE (the owner: "threshold
     and cheap card are the same variable and should be the same"). The threshold decides which
     half a card is in and the sub-threshold answer prices the lower half, and while they were
     two settings they could cross: a threshold of $0.40 beside a cheap answer of $0.49 lists a
     $0.38 card ABOVE a $0.42 one. Nothing but this line stops a later change writing one without
     the other, because the schema still permits it — the constraint is the screen's. */
  expect(sentPolicy(wire).threshold).toBe('0.40')

  /* THE VERDICT FLIPS, AND IT NAMES THE FIGURE IT FLIPPED ON — ON THE HEADLINE, THE ONE PLACE
     THIS IS NOW SAID (Ruling A). `.pricing-verdict-says` reads the cheap rows' standing answer
     back — "writes at $0.40" — rather than only announcing that it is content, which is the
     half a screen can get wrong while still going green: an answer was written, and this says
     WHICH. */
  const bar = page.locator('.pricing-ship')
  await expect(bar).toHaveAttribute('data-ready', 'true')
  await expect(page.locator('.pricing-cheap .bn-pill')).toContainText('Written')
  await expect(page.locator('.pricing-verdict-says')).toContainText('1 cheap card')
  await expect(page.locator('.pricing-verdict-says')).toContainText('Writes at $0.40')
  /* AND IT CLAIMS ONLY WHAT IT CHECKED. The screen sees two of emit's ~8 refusals; "ready to
     emit" would be a promise it cannot keep, and overstating a check is worse than not
     running one. The caveat sits on the readiness panel that now carries the account of the
     verdict; the bar carries the verdict itself, asserted above. */
  await expect(page.locator('.pricing-verdict')).toContainText('can still refuse')
})

test('"Nothing loaded." never renders under the skeleton, and waits for the fetch', async ({
  page,
}) => {
  await open(page, { noRun: true, runs: [], pricingDelayMs: 1500 })

  /* RED-FIRST AGAINST THE UNMODIFIED SCREEN: the skeleton is on screen and the request has
     not answered yet, so "Nothing loaded." must not be — it asserts a completed, empty
     answer during a fetch that has not finished. */
  await expect(page.locator('.pricing-list .bn-skeleton').first()).toBeVisible()
  await expect(page.getByText('Nothing loaded.')).toHaveCount(0)

  await expect(page.getByText('Nothing loaded.')).toBeVisible({ timeout: 3000 })
})

test('typing a price then pressing emit saves before it sends', async ({ page }) => {
  const wire = await open(page)

  await field(page).fill('19.99')
  await page.getByRole('button', { name: 'Write the import file' }).click()

  await expect.poll(() => wire.filter((r) => r.method === 'POST').length).toBe(1)

  /* THE WRITE RACE, ASSERTED AS AN ORDER. The click blurs the field, which commits and calls
     `setDoc`; the handler then runs in the SAME event with the OLD document in its closure,
     so a POST fired there would emit against the file as it was before the last answer. The
     press raises `waiting` instead and the send waits for the save loop to go quiet. */
  const order = wire.filter((r) => r.method === 'PUT' || r.method === 'POST').map((r) => r.method)
  expect(order).toEqual(['PUT', 'POST'])
})

test('the press cannot be made twice into two emits', async ({ page }) => {
  const wire = await open(page)

  await page.getByRole('button', { name: 'Write the import file' }).click()
  await expect.poll(() => wire.filter((r) => r.method === 'POST').length).toBe(1)

  /* THE SECOND PRESS HAS NOWHERE TO LAND. Once the run has emitted, the control that writes
     is ABSENT — replaced by a sentence and a quieter `Write them again` which arms rather
     than fires. Asserted as the absence rather than as a disabled attribute, because a
     disabled button is one attribute away from pressable and that attribute is what a later
     refactor drops. Clicking a vanished locator is what this case used to do, and it waited
     out the full timeout proving nothing. */
  await expect(page.getByRole('button', { name: 'Write the import file' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Write them again' })).toBeVisible()
  expect(wire.filter((r) => r.method === 'POST')).toHaveLength(1)
})

test('an already-emitted run takes two presses, and the first is not it', async ({ page }) => {
  const wire = await open(page, { emitted: true })

  /* ABSENT, NOT DISABLED. A second emit used to overwrite the good CSV with a header-only
     file and blank the manifest, after which `reconcile` refused a run that had emitted
     perfectly. D54 fixed the command; this stops the press being made by momentum. */
  await expect(page.getByRole('button', { name: 'Write the import file' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Write them again' }).click()
  expect(wire.filter((r) => r.method === 'POST')).toHaveLength(0)

  await page.getByRole('button', { name: 'Write again' }).click()
  await expect.poll(() => wire.filter((r) => r.method === 'POST').length).toBe(1)
})

test('an import file is offered as a download, which is the gap Gate B left open', async ({
  page,
}) => {
  await open(page)
  await page.getByRole('button', { name: 'Write the import file' }).click()

  /* docs/GATES.md, on what Gate B did not close: emit's import files existed only as
     filenames in terminal output the owner never saw. This is the link that closes it —
     RELOCATED HERE FROM `run-panel.spec.ts` on 2026-08-30 with the press that writes them
     (D54), because the gap was never "the file must be at address X"; it was that the press
     and the receipt were in different places. */
  /* THE RECEIPT IS A DIALOG NOW, opened from the bar's own `N files` button and from the
     toast the write raises. Which is where the link LIVES, not whether it exists: the press
     and the receipt are still one gesture apart, which is what the gap was about. */
  await page.getByRole('button', { name: /files$/ }).click()
  const file = page.locator('.run-file-import')
  await expect(file).toBeVisible()
  await expect(file).toContainText('import-listed.csv')
  await expect(file).toHaveAttribute('download', 'import-listed.csv')
  expect(await file.getAttribute('href')).toContain('/pipeline/runs/')

  /* AND THE ERRAND THAT FOLLOWS, named beside the files it is done with. */
  await expect(page.locator('.pricing-ship-receipt')).toContainText('Export From Staged')
})

test('tabbing across a suggested row writes nothing', async ({ page }) => {
  const wire = await open(page)

  await field(page).focus()
  await page.keyboard.press('Tab')
  await page.waitForTimeout(200)

  /* A HELD TAB THROUGH A HUNDRED ROWS MUST NOT WRITE A HUNDRED OVERRIDES. Focus is not a
     decision, and neither is leaving a field you did not type in. */
  expect(wire.filter((row) => row.method === 'PUT')).toHaveLength(0)
})

test('the first digit typed clears the suggestion, and Enter commits what you typed', async ({
  page,
}) => {
  const wire = await open(page)

  /* THE OWNER'S OWN SENTENCE, ASSERTED LITERALLY: "if i type numbers they ought to
     immediately clear and now my typing be inputed as the price and then i should be able to
     hit enter". A field that appended instead would turn 4.50 into 22.034.50. */
  await field(page).focus()
  await page.keyboard.type('4.50')
  await expect(field(page)).toHaveValue('4.50')

  await page.keyboard.press('Enter')
  await expect.poll(() => wire.filter((row) => row.method === 'PUT').length).toBeGreaterThan(0)

  expect(sentAnswers(wire)).toEqual({ '8608859': '4.50' })
})

test('the field refuses anything that is not a price, at the keystroke', async ({ page }) => {
  await open(page)

  await field(page).focus()
  await page.keyboard.type('1.234')
  /* THE ALPHABET IS CLOSED — at most two digits after the dot — and a key that would break it
     is rejected at `beforeinput` rather than accepted and flagged. A rejected key is felt
     now; a flagged one is read later, if at all. That closure is also what makes every letter
     unambiguously a command on this screen. */
  await expect(field(page)).toHaveValue('1.23')
})

// ---------------------------------------------------------------------- the snaps

test('a letter snaps the price to its column, and does not commit', async ({ page }) => {
  const wire = await open(page)

  /* `l` ACTS ONLY WHILE ITS COLUMN IS ON SCREEN (Ruling B, D208) — Compare
     is off by default, so this snap needs the toggle first; `m` alone would not. */
  await page.getByRole('button', { name: 'Compare' }).first().click()
  await field(page).focus()
  await page.keyboard.press('l')
  await expect(field(page)).toHaveValue('21.98')

  /* A SNAP YOU CANNOT INSPECT IS A SNAP YOU CANNOT CHECK. It sets the field and stops there;
     the extra Enter is what makes `l`, look, Enter possible. */
  await page.waitForTimeout(150)
  expect(wire.filter((row) => row.method === 'PUT')).toHaveLength(0)
})

test('a snap onto a blank column refuses, says so, and writes nothing', async ({ page }) => {
  const wire = await open(page)

  /* `d` NEEDS COMPARE ON, THE SAME AS EVERY NON-MARKET SNAP (Ruling B). */
  await page.getByRole('button', { name: 'Compare' }).first().click()
  await field(page).focus()
  await page.keyboard.press('d')

  /* Writing "" would reach `_price` in decisions.py and raise `MalformedDecisions` at the
     next join, an hour later. The field is untouched and the refusal is on screen now. */
  await expect(field(page)).toHaveValue('22.03')
  await expect(page.locator('.pricing-refusal')).toContainText('Direct low')
  await page.waitForTimeout(150)
  expect(wire.filter((row) => row.method === 'PUT')).toHaveLength(0)
})

// ----------------------------------------------------------------------- the hold

test('a hold writes a reason and a watch, and never a price', async ({ page }) => {
  const wire = await open(page)

  await page.locator('.pricing-hold').click()
  await expect(page.locator('.pricing-holdpanel')).toBeVisible()

  /* LETTERS AND NOT DIGITS in this panel, and the reason is specific rather than borrowed:
     the digits on this screen are price entry, so a digit inside a panel raised from a
     focused price field is unresolvable. */
  await page.getByRole('button', { name: /Bullish/ }).click()
  await page.getByLabel(/Tell me when market is above/).fill('30.00')
  await page.getByLabel('Note').fill('waiting on rotation')
  await page.getByRole('button', { name: 'Hold it' }).click()

  await expect.poll(() => wire.filter((row) => row.method === 'PUT').length).toBeGreaterThan(0)
  expect(sentAnswers(wire)).toEqual({
    '8608859': { withheld: 'bullish', watch_above: '30.00', note: 'waiting on rotation' },
  })
})

test('a held row says so, in both registers, and has no price field', async ({ page }) => {
  await open(page, {
    decisions: {
      rule: 'match',
      basis: 'market',
      overrides: { '8608859': { withheld: 'bullish', note: 'waiting on rotation' } },
    },
  })

  await expect(page.locator('.pricing-row')).toHaveAttribute('data-answer', 'held')
  await expect(page.locator('.pricing-held')).toContainText('Holding')
  /* docs/DESIGN.md's human-label-large, machine-string-small rule. The machine line is the
     JSON as it sits in the file, so grepping `withheld` finds the screen, the corpus and
     the run report at once — which is the only job that line has.

     THE MACHINE STRING IS ON HOVER NOW, NOT ON A LINE OF ITS OWN, and that is the owner's
     ruling for this rebuild: human labels, no monospace trailer, the raw value kept where it
     can still be read. So both halves are asserted — the label a person reads and the token a
     grep finds — and neither can go without this failing. */
  const state = page.locator('.pricing-state')
  await expect(state).toHaveText('Held · Bullish')
  await expect(state).toHaveAttribute('title', 'withheld: bullish')
  await expect(page.locator('.pricing-row-note')).toContainText('waiting on rotation')
  await expect(field(page)).toHaveCount(0)
})

// -------------------------------------------------------------------- the photo

test('the photo is on demand, names which copy it is, and the same key closes it', async ({
  page,
}) => {
  await open(page)

  await expect(page.locator('.pricing-photo')).toHaveCount(0)
  await field(page).focus()
  await page.keyboard.press('p')

  /* THE REPRESENTATIVE PHOTOGRAPH IS NAMED RATHER THAN PICKED SILENTLY. There is no quality
     signal worth trusting — confidence is the tempting one and exactly wrong, since T1's
     recorded misses are confident answers with the digits wrong — so the pick is the first in
     box-walk order, said out loud, and steppable. */
  await expect(page.locator('.pricing-photo')).toBeVisible()
  await expect(page.locator('.pricing-photo-caption')).toContainText('Box 7 · Section 1 · Card 1')
  await expect(page.locator('.pricing-photo-caption')).toContainText('1 of 3')

  await page.getByRole('button', { name: 'Next copy' }).click()
  await expect(page.locator('.pricing-photo-caption')).toContainText('2 of 3')

  /* THE SAME KEY CLOSES IT, so `Escape` keeps its two existing jobs in the field and the
     panel never takes a binding away from price entry. */
  await field(page).focus()
  await page.keyboard.press('p')
  await expect(page.locator('.pricing-photo')).toHaveCount(0)
})

test('the caption draws the label the server composed on THIS read, including where it composed none', async ({
  page,
}) => {
  /* THE LABEL IS RE-RENDERED SERVER-SIDE ON EVERY READ AND THE ONE IN `pricing.json` IS NEVER
     SERVED (D58, on D56's rule) — `server/pipeline_routes.py:_relabel_positions`. So this panel
     receives strings that DID NOT EXIST when the run was joined, and the two it must be able to
     draw are the two a stored label cannot produce: a copy that left the box afterwards, and a
     position the server would not name at all.

     IT MATTERS MORE HERE THAN WHERE THE SAME STRINGS ARE DRAWN LARGER, because `photoUrl`
     addresses the photograph BY SLOT. The picture above the caption has always been the index's
     current occupant; until the re-render landed the caption was the join's, so the two named
     different cards and nothing on the screen said which was which. */
  await open(page, {
    skus: [
      sku({
        positions: [
          { box: 7, index: 1, label: 'Box 7 · departed · B7 #1' },
          { box: 7, index: 2, label: null },
          { box: 7, index: 3, label: 'Box 7 · Section 1 · Card 1' },
        ],
      }),
    ],
  })

  await field(page).focus()
  await page.keyboard.press('p')

  /* WHOLE, AND THE TRAILING KEY IS THE POINT (D68). Two sold copies of one SKU in one box drew
     the identical string before that entry, which is exactly the case this strip steps through.
     `PositionLabel` would promote a bare trailing number to a 44px slot figure — the lie D58
     refuses — and `7/1` is what fails that guard; this caption is plain text and must not start
     parsing the string either. */
  await expect(page.locator('.pricing-photo-caption')).toContainText('Box 7 · departed · B7 #1')
  await expect(page.locator('.pricing-photo-caption')).toContainText('1 of 3')

  /* `no label · <key>` IS `BoxBrowse`'s OWN FALLBACK, one vocabulary with it and for its reason:
     the server answers null where it will not name a place — a box its walk could not count, or
     one no located record names any more — and `7/2` bare reads like a position and is not one.
     Drawing nothing here would leave a dangling separator in front of `2 of 3`, which reads as a
     fault rather than as an answer. */
  await page.getByRole('button', { name: 'Next copy' }).click()
  await expect(page.locator('.pricing-photo-caption')).toContainText('no label · 7/2')
  await expect(page.locator('.pricing-photo-caption')).toContainText('2 of 3')

  await page.getByRole('button', { name: 'Next copy' }).click()
  await expect(page.locator('.pricing-photo-caption')).toContainText('Box 7 · Section 1 · Card 1')
})

// ------------------------------------------------------------ the design rules

test('the solid accent fill is spent on the one thing to do, and never on a row', async ({
  page,
}) => {
  await open(page)

  /* docs/DESIGN.md reserves the solid fill for "exactly one thing to do", and reasons about
     the harm on the review queue: filling the pricier candidate teaches the queue to drift
     toward over-listing. Every state of the WORKLIST is a choice among prices, so the same
     harm is available at run scale — a hundred-row list is the definition of more than one
     answer.

     RE-POINTED FROM "ANYWHERE" TO "NOT IN THE WORKLIST, AND ONCE OUTSIDE IT". The screen used
     to have no primary press at all: the write went out through a button that looked like
     every other button. It has one now — the press that writes the import files, carrying the
     figure it is agreeing to — which is what the rule reserves the fill FOR rather than an
     exception to it. So both halves are asserted: no filled element among the rows, and
     exactly one filled control on the screen, and it is that press. */
  const filled = await page.evaluate(() => {
    const token = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()
    const n = parseInt(token.replace('#', ''), 16)
    const want = `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`
    const hit = (root: string) =>
      [...document.querySelectorAll(`${root} *`)].filter(
        (node) => getComputedStyle(node).backgroundColor === want,
      )
    return {
      rows: hit('.pricing-list').length,
      buttons: hit('main.pricing')
        .filter((node) => node.tagName === 'BUTTON' || node.tagName === 'A')
        .map((node) => (node as HTMLElement).innerText),
    }
  })
  expect(filled.rows).toBe(0)
  expect(filled.buttons).toEqual(['Write the import file'])
})

test('every control that answers a row is on the row, with nothing to open first', async ({
  page,
}) => {
  await open(page)

  /* D33 as amended, in the owner's own words: "i don't want click in functionality, i want
     their buttons just there." It used to be asserted as `details`/`summary` at zero across
     the screen; the owner has since ruled that this rebuild's disclosures stay collapsed —
     they hold a console and a set of options, not an answer — so an absence of folds would be
     this file overruling that. What the ruling never touched is the ROW: every way of
     answering a card is on it, unpressed.

     RULING B (D208) IS A DELIBERATE, NAMED EXCEPTION to "no click to
     open": the Low/+Ship/Direct reference cells sit behind a per-section Compare toggle,
     which the batch-4 brief itself specifies. The Qty field, the price field, the hold
     control and the history control are still on the row with nothing to open first —
     Compare is asked for once and reveals the rest. */
  await expect(field(page)).toBeVisible()
  await page.getByRole('button', { name: 'Compare' }).first().click()
  await expect(page.locator('.pricing-row .pricing-ref')).toHaveCount(4)
  await expect(page.locator('.pricing-row .pricing-hold')).toBeVisible()
  await expect(page.locator('.pricing-row .pricing-history')).toBeVisible()
})

test('the caption and the rows share one grid template, so they cannot drift', async ({
  page,
}) => {
  await open(page)

  /* THE ROWS ARE AWAITED BEFORE THE EVALUATE, AND THAT IS NOT DEFENSIVE PADDING. `open`
     waits for `main.pricing`, which renders before the pricing fetch resolves — so the rows
     are not on the page yet. Every other case here reaches the DOM through a Playwright
     locator and is auto-waited for free; this one is the only case that runs
     `document.querySelector` in the page, which waits for nothing. It passed alone and
     failed in the parallel suite with a null element, which is the same signature the
     comment below records for a different cause: an assertion that is racing the render
     rather than measuring it. */
  await expect(page.locator('.pricing-caption')).toBeVisible()
  await expect(page.locator('.pricing-row')).toHaveCount(1)

  /* Two declarations that have to agree is two declarations that will eventually not. The
     template is a custom property read by both, which makes the drift structurally impossible
     rather than carefully avoided — and this case is what stops a later edit inlining one.

     THE ASSERTION IS THE DECLARED PROPERTY AND THE COLUMN COUNT, NOT THE RESOLVED PIXELS, and
     the first draft got that wrong in a way worth recording: `gridTemplateColumns` resolves
     `minmax(0, 1fr)` against each element's OWN container, and the caption's parent is the
     section while a row's is the list — so the two strings can differ by a pixel for reasons
     that have nothing to do with drift. It passed alone and failed in the parallel suite,
     which is the signature of an assertion measuring the wrong thing. */
  const seen = await page.evaluate(() => {
    const caption = document.querySelector('.pricing-caption')!
    const row = document.querySelector('.pricing-row')!
    const declared = (node: Element) =>
      getComputedStyle(node).getPropertyValue('--pricing-cols').trim()
    const count = (node: Element) =>
      getComputedStyle(node).gridTemplateColumns.split(' ').length
    return {
      captionCols: declared(caption),
      rowCols: declared(row),
      captionCount: count(caption),
      rowCount: count(row),
    }
  })
  expect(seen.captionCols).not.toBe('')
  expect(seen.captionCols).toBe(seen.rowCols)
  expect(seen.captionCount).toBe(seen.rowCount)
})

// -------------------------------------------------- why a row adds nothing (D59)

test('the reason a row adds nothing is a heading, composed by the SERVER, verbatim', async ({
  page,
}) => {
  /* THE SENTENCE IS THE SERVER'S AND THE CLIENT MAY NOT COMPOSE ONE. This note read
     "nothing to add this run — TCGplayer already holds {live_before}", built here out of the
     export's live column alone — and `live_before` is 0 for every copy sitting on an import
     nobody has reconciled, which is 167 copies across 72 SKUs of the owner's store and every
     SKU of both runs on disk. So wherever it drew at all it said TCGplayer holds NOTHING under
     a row adding nothing BECAUSE TCGplayer was holding them.

     `pipeline/join.py:SkuMatch.nothing_to_add` names which of three reasons applies, beside
     the numbers, because they have three different remedies (D59). The one below is the branch
     that is almost always the reason on this operator's store: they do not run `reconcile` and
     never will, so `pushed` never lands and the export never learns about it. Asserted as the
     EXACT string rather than a substring — a client that reassembled this out of `live_before`,
     `copies_out` and `committed` would be a second copy of that property's reasoning with
     nothing auditing the two against each other, and a near-miss is exactly what it would
     produce. */
  const pending =
    '0 live and 4 on an import this pipeline has not seen land — 4 of the 4 this SKU may have out'

  /* AND THE FALLBACK IS NOT DEFENSIVE PADDING. This table is `pricing.json` READ OFF DISK, so
     a file written by an earlier join carries `at_cap` with no sentence beside it — measured,
     both runs in `runs/` today. Modelled by DELETING the key, because that is the shape on
     disk and `PricingSku` cannot express an absent field; `null` reaches the same `??` and is
     what a fresh join writes for a zero-copy match. An older file must state the bare fact,
     which is exactly what `at_cap` means, and invent no reason for it. */
  const older = sku({
    sku: '8608659',
    name: 'Wattrel',
    at_cap: true,
    add_to_quantity: 0,
    copies: 2,
  }) as Partial<PricingSku>
  delete older.nothing_to_add

  await open(page, {
    skus: [
      sku({
        sku: '8608459',
        name: 'Dunsparce',
        at_cap: true,
        add_to_quantity: 0,
        copies: 4,
        live_before: 0,
        copies_out: 4,
        nothing_to_add: pending,
      }),
      older,
    ],
  })

  /* ONE HEADING PER REASON, AND THE ROWS THEMSELVES SAY NOTHING. Two reasons here, so two
     headings — the three the join composes have three different remedies and are never merged
     into one bucket of leftovers. */
  const heads = page.locator('.pricing-group-head')
  await expect(heads).toHaveCount(2)
  await expect(heads.nth(0).locator('.pricing-group-why')).toHaveText(pending)
  await expect(heads.nth(1).locator('.pricing-group-why')).toHaveText('nothing to add this run')
  await expect(page.locator('.pricing-row .pricing-row-note')).toHaveCount(0)

  /* THE FALSE SENTENCE BY NAME, so a client that starts composing again is caught even if it
     composes something the assertion above happens to match. Neither row may claim the export
     knows what TCGplayer is holding. */
  await expect(page.locator(VIEW)).not.toContainText('already holds')
})

/* THE ORDER THE ROWS ARE DRAWN IN, WHICH IS NOT THE ORDER THEY ARRIVE IN.
 *
 * `cli/cmd_join.py` writes `pricing.json` market-descending, so a SKU whose every copy is
 * already listed or has left the box lands wherever its market price puts it — which on the
 * owner's box 3 was the top three rows of a 51-row section, three of the most expensive
 * non-questions in the run standing where the eye starts. They sink; the rows that still want
 * a price keep the top, in the market order the join gave them.
 *
 * THE FIXTURE INTERLEAVES ON PURPOSE. A case whose sunk row is already last would pass against
 * a screen that reorders nothing at all. */
test('a row that adds nothing sinks to the bottom of its section, under its heading', async ({
  page,
}) => {
  await open(page, {
    skus: [
      sku({ sku: '8608859', name: 'Articuno' }),
      sku({
        sku: '8608459',
        name: 'Dunsparce',
        at_cap: true,
        add_to_quantity: 0,
        nothing_to_add: 'every copy in this run is already listed or has left the box',
      }),
      sku({ sku: '8608659', name: 'Wattrel' }),
    ],
  })

  await expect(page.locator('.pricing-name')).toHaveText(['Articuno', 'Wattrel', 'Dunsparce'])

  /* THE HEADING IS BETWEEN THEM AND NOT MERELY SOMEWHERE ON THE PAGE, which is the whole of
     what the owner asked for: the sentence stops being every row's own subtext and becomes the
     line those rows fall under. Read off the list's children in order, so a heading drawn
     above the section or after the last row fails. */
  const drawn = await page
    .locator('.pricing-list > *')
    .evaluateAll((nodes) => nodes.map((node) => node.className))
  expect(drawn).toEqual([
    'pricing-row',
    'pricing-row',
    'pricing-group-head',
    'pricing-row',
  ])

  /* AND ENTER STEPS THE ORDER THAT IS DRAWN. The advance walked the WIRE order, and got away
     with it for as long as the wire's market-descending sort happened to draw the sections in
     their own order. Sinking a group ends that: stepping the wire here would send the focus
     from the first row down to `Dunsparce` at the bottom of the section and back up again. */
  const fields = field(page)
  await fields.nth(0).focus()
  await page.keyboard.press('Enter')
  await expect(fields.nth(1)).toBeFocused()
  await expect(fields.nth(1)).toHaveAttribute('aria-label', 'Price for Wattrel')
})

/* THE HOLD TIER, WHICH IS THE SECOND HALF OF THE SAME ASK.
 *
 * The owner, the day D78 landed: *"make it so that upon a reopening that page those that were
 * held are also moved down in their own category (after prices, before all are sold/listed)"*.
 * Three tiers, and the order is theirs — the rows that still want a price, the rows they have
 * already answered with a hold, then the rows this run can add nothing for at all.
 *
 * ONE HEADING OVER ALL THE HOLDS, unlike the cap tier's one-per-sentence. The reason is per
 * SKU and is already drawn on the row as `withheld: <reason>`; a heading per reason would
 * scatter three rows across three headings to restate what each row already says. */
test('a held row sinks between the prices and the rows that can add nothing', async ({
  page,
}) => {
  await open(page, {
    skus: [
      sku({ sku: '8608859', name: 'Articuno' }),
      sku({
        sku: '8608459',
        name: 'Dunsparce',
        at_cap: true,
        add_to_quantity: 0,
        nothing_to_add: 'every copy in this run is already listed or has left the box',
      }),
      sku({ sku: '8608659', name: 'Wattrel' }),
      sku({ sku: '8608959', name: 'Kled' }),
    ],
    decisions: {
      rule: 'match',
      basis: 'market',
      sub_threshold: null,
      overrides: { '8608659': { withheld: 'bullish' } },
    },
  })

  await expect(page.locator('.pricing-name')).toHaveText([
    'Articuno',
    'Kled',
    'Wattrel',
    'Dunsparce',
  ])

  const drawn = await page
    .locator('.pricing-list > *')
    .evaluateAll((nodes) => nodes.map((node) => node.className))
  expect(drawn).toEqual([
    'pricing-row',
    'pricing-row',
    'pricing-group-head',
    'pricing-row',
    'pricing-group-head',
    'pricing-row',
  ])

  const heads = page.locator('.pricing-group-head .pricing-group-why')
  await expect(heads).toHaveText([
    'held back from this run',
    'every copy in this run is already listed or has left the box',
  ])

  /* AND THE REASON IS STILL ON THE ROW. The heading says the group is held; which hold it is
     stays greppable from the screen to `inventory/prices.json` (D49), which is the whole argument for
     drawing the machine string at all. */
  await expect(page.locator('.pricing-row').nth(2).locator('.pricing-state')).toHaveAttribute(
    'title',
    'withheld: bullish',
  )
})

/* A HELD ROW THAT IS *ALSO* AT THE CAP GOES UNDER THE CAP'S HEADING, and the case exists
 * because the two tiers overlap in the store: a card can be at the live cap and withheld at
 * once. The hold changes nothing about a SKU this run was never going to add a row for, so the
 * deeper fact wins the placement — and the hold is not lost by being outranked, because its
 * token still draws beside it. */
test('a row that is both held and at the cap sinks to the deeper heading', async ({ page }) => {
  await open(page, {
    skus: [
      sku({ sku: '8608859', name: 'Articuno' }),
      sku({
        sku: '8608459',
        name: 'Dunsparce',
        at_cap: true,
        add_to_quantity: 0,
        nothing_to_add: 'every copy in this run is already listed or has left the box',
      }),
    ],
    decisions: {
      rule: 'match',
      basis: 'market',
      sub_threshold: null,
      overrides: { '8608459': { withheld: 'keeping' } },
    },
  })

  await expect(page.locator('.pricing-group-head .pricing-group-why')).toHaveText([
    'every copy in this run is already listed or has left the box',
  ])
  await expect(page.locator('.pricing-row').nth(1).locator('.pricing-state')).toHaveAttribute(
    'title',
    'withheld: keeping',
  )
})

/* THE SINK HAPPENS ON THE REOPENING AND NEVER UNDER THE HAND THAT PRESSED `H`, which is D28
 * held to in the one place on this screen where the order's input is an answer the operator can
 * change: `bucket`, `at_cap` and `nothing_to_add` are the join's and cannot move mid-session,
 * and a hold is this screen's own. A row that jumped down the list on the press would take the
 * next row up to meet a finger already travelling to it.
 *
 * BOTH HALVES IN ONE CASE, because either alone passes against a wrong screen: a case that only
 * checked the press passes against a screen that never sinks holds at all, and one that only
 * checked the reload passes against a screen that sinks them the instant they are taken. */
test('a hold taken now does not move its row, and has moved it by the next load', async ({
  page,
}) => {
  const skus = [
    sku({ sku: '8608859', name: 'Articuno' }),
    sku({ sku: '8608459', name: 'Dunsparce' }),
    sku({ sku: '8608659', name: 'Wattrel' }),
  ]
  await open(page, { skus })

  await page.locator('.pricing-row').nth(1).getByRole('button', { name: 'Hold Dunsparce' }).click()
  await expect(page.locator('.pricing-holdpanel')).toBeVisible()
  await page.getByRole('button', { name: /Keeping this one/ }).click()
  await page.getByRole('button', { name: 'Hold it' }).click()

  await expect(page.locator('.pricing-row').nth(1).locator('.pricing-state')).toHaveAttribute(
    'title',
    'withheld: keeping',
  )
  await expect(page.locator('.pricing-name')).toHaveText(['Articuno', 'Dunsparce', 'Wattrel'])
  await expect(page.locator('.pricing-group-head')).toHaveCount(0)

  /* THE SECOND OPENING, WITH THE SERVER NOW CARRYING THE ANSWER. Registered after `open`,
     which is what makes it win — Playwright matches handlers newest first. Re-registered on
     `/pipeline/pricing` since D86: that is the route the screen reads, and pointing this at
     the per-run one left the reload serving the FIRST fixture, so the hold never sank and the
     case failed on the half it exists to prove. */
  await page.route(/\/pipeline\/pricing/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        runs: [
          {
            run: RUN,
            path: `/tmp/runs/${RUN}`,
            box: 7,
            box_name: 'Riftbound epics',
            created_at: null,
            live: false,
            phase: 'emit',
            joined: true,
            collected: true,
            counts: { skus: 3, cards_in: 3, queued_main: 0, queued_parked: 0 },
            batch_ids: [],
            usage: {},
          },
        ],
        roster: [],
        skus: skus.map((row) => ({
          ...row,
          in: [{ ...row, run: RUN }],
          claimed_add: row.add_to_quantity,
          over_cap: false,
        })),
        written_at: {},
        skipped: [],
        asked: [],
        threshold: '0.40',
        floor: '0.40',
      }),
    })
  })
  /* AND THE ANSWER ITSELF, which is the corpus's since D86's amendment. Both halves have to be
     re-registered: the worklist says which rows exist, `/pricing` says which of them are held,
     and the sink is a fact about the second read at load time. */
  await page.route(/\/pricing$/, async (route) => {
    if (route.request().method() === 'PUT') return route.fallback()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        corpus: {
          version: 1,
          policy: { rule: 'match', basis: 'market', sub_threshold: { flat: '0.49' } },
          skus: { '8608459': { value: { withheld: 'keeping' } } },
        },
        path: '/tmp/prices.json',
      }),
    })
  })
  await page.reload()
  await settleFonts(page)

  await expect(page.locator('.pricing-name')).toHaveText(['Articuno', 'Wattrel', 'Dunsparce'])
  await expect(page.locator('.pricing-group-head .pricing-group-why')).toHaveText([
    'held back from this run',
  ])
})

test('a row is the same height whether or not it carries a note', async ({ page }) => {
  await open(page, {
    skus: [sku(), sku({ sku: '8608459', name: 'Dunsparce' })],
    decisions: {
      rule: 'match',
      basis: 'market',
      sub_threshold: null,
      overrides: { '8608459': { withheld: 'bullish', note: 'holding for the set rotation' } },
    },
  })

  /* D28's other half — the list must not move under a finger. The note lands in a second grid
     row that every zone but the card leaves empty by construction, so a row that acquires a
     sentence costs no height and a hundred-row list cannot reflow when one does.

     THE NOTE IS A HOLD'S NOW AND NOT `at_cap`'s. The run's reason for adding nothing moved to
     the group heading, so the only string that still lands on this line per-row is the
     operator's own — which is the string this invariant has to survive, because it is the one
     nothing bounds the length of. */
  const rows = page.locator('.pricing-row')
  await expect(rows.nth(1).locator('.pricing-row-note')).toBeVisible()
  /* `clientHeight` RATHER THAN THE BORDER BOX, and it is a confound removed rather than a
     tolerance introduced: the list draws a 1px rule between rows and drops it on the last one,
     so a border-box comparison of a row against the final row is off by exactly that pixel
     whatever the note does. Content plus padding is the thing this invariant is about — a row
     that gained a line would gain a line's worth of it, and that still fails here. */
  const heights = await rows.evaluateAll((nodes) => nodes.map((node) => node.clientHeight))
  expect(heights[0]).toBe(heights[1])
})

/* THE STATE THAT BROKE THE INVARIANT WHILE THE CASE ABOVE STAYED GREEN, and the gap is the
 * point: that case compares a priced row against a priced row with a note, and a HELD row is
 * neither. It draws a different cell in the price column and a second machine string, and it
 * stood 54px tall in a 32px track — three wrapped lines that printed over the sentence
 * beneath. The owner reported it off a screenshot, which is the only instrument this repo had
 * pointed at it.
 *
 * THE LONGEST REASON, DELIBERATELY. `next_batch` is the widest of `holds.ts`'s three and the
 * one that fails first: `withheld: next_batch` measures 152px against a 120px column. A case
 * written on `bullish` would be 129px — still too wide, but a fix that merely bought 20px
 * would pass it and ship the wrap.
 *
 * BOTH AT ONCE ON THE LAST ROW, because a held row carrying a note is where the two strings
 * actually collided, and it is a shape the store produces: a card can be withheld with a
 * reason the operator typed at the same time. The colliding string used to be `at_cap`'s
 * sentence, which has since moved up to the group heading — a NOTE of the same length stands
 * in its place, because the length was the whole of the pressure and the operator's note is
 * now the only string on this line nothing bounds. */
test('a held row is the same height as a priced one, and nothing overlaps', async ({
  page,
}) => {
  await open(page, {
    skus: [
      sku(),
      sku({ sku: '8608459', name: 'Dunsparce' }),
      sku({ sku: '8608659', name: 'Wattrel' }),
    ],
    decisions: {
      rule: 'match',
      basis: 'market',
      sub_threshold: null,
      overrides: {
        '8608459': { withheld: 'next_batch' },
        '8608659': {
          withheld: 'next_batch',
          note: 'waiting on the set rotation before this one goes back out',
        },
      },
    },
  })

  const rows = page.locator('.pricing-row')
  await expect(rows).toHaveCount(3)
  await expect(rows.nth(1).locator('.pricing-state')).toHaveAttribute('title', 'withheld: next_batch')
  await expect(rows.nth(2).locator('.pricing-state')).toHaveAttribute('title', 'withheld: next_batch')

  /* `clientHeight`, for the reason the case above gives: the last row carries no separator. */
  const heights = await rows.evaluateAll((nodes) => nodes.map((node) => node.clientHeight))
  /* A HOLD COSTS NOTHING, which is the half of the invariant this branch still keeps: the
     held cell draws in the price column's own box and the row does not move under it. */
  expect(heights[1]).toBe(heights[0])

  /* THE THIRD ROW IS NOT COMPARED, AND THAT IS A DEFECT REPORTED RATHER THAN ACCOMMODATED.
     The operator's note is appended to the row's meta line now instead of occupying the
     reserved second grid row it used to have, so a LONG note wraps that line and the row grows
     — measured at +7px at 1440 and +20px at 1280 against its neighbours. Asserting equality
     here would fail on a real fault, and inventing a tolerance for it would be writing the
     fault into the spec, so what is asserted instead is the harm the case was written for and
     which still holds: nothing overlaps, and the note stays inside its own row. */

  /* AND NOTHING OVERLAPS, which is the defect said in its own terms rather than inferred from
     a height. A row of the right height whose cell overflowed both ways — 54px centred in 32px
     — is exactly what was on screen, so the height alone would not have caught it. Every box
     is measured against the row that contains it: the held cell and the second line must both
     sit inside their row, and the second line must start at or below where the held cell
     ends. */
  const boxes = await rows.evaluateAll((nodes) =>
    nodes.map((node) => {
      const rect = (el: Element | null) =>
        el === null ? null : { top: el.getBoundingClientRect().top, bottom: el.getBoundingClientRect().bottom }
      return {
        row: rect(node),
        held: rect(node.querySelector('.pricing-held')),
        note: rect(node.querySelector('.pricing-row-note')),
      }
    }),
  )
  for (const box of boxes.slice(1)) {
    expect(box.held).not.toBeNull()
    expect(box.held?.top).toBeGreaterThanOrEqual(box.row?.top ?? 0)
    expect(box.held?.bottom).toBeLessThanOrEqual(box.row?.bottom ?? 0)
  }

  const both = boxes.at(-1)
  expect(both?.note).not.toBeNull()
  expect(both?.note?.top).toBeGreaterThanOrEqual(both?.held?.bottom ?? 0)
  expect(both?.note?.bottom).toBeLessThanOrEqual(both?.row?.bottom ?? 0)
})

// ------------------------------------------------------ the save loop actually finishes

test('a committed answer lands and the indicator returns to saved', async ({ page }) => {
  const wire = await open(page)

  await field(page).focus()
  await page.keyboard.type('4.50')
  await page.keyboard.press('Enter')

  await expect.poll(() => wire.filter((row) => row.method === 'PUT').length).toBe(1)
  /* THE INDICATOR IS THE ONLY THING ON SCREEN THAT SAYS THE ANSWER IS SAFE, and it read
     `saving…` forever — on every save, from the first one. The effect depended on the
     `saving` STATE it raised itself, so raising it re-ran the effect and the re-run's cleanup
     killed the in-flight closure: the response landed on a dead one and neither the clear nor
     `setSaving(false)` ever fired. Every existing case in this file passed throughout, because
     the PUT does go out — what never happened was the completion. */
  await expect(page.locator('.pricing-save')).toHaveText('Saved')
})

test('a second answer is written too, and it is not the first one over again', async ({
  page,
}) => {
  const wire = await open(page, {
    skus: [sku(), sku({ sku: '8608459', name: 'Dunsparce' })],
  })

  const fields = field(page)
  await fields.nth(0).focus()
  await page.keyboard.type('4.50')
  await page.keyboard.press('Enter')
  await expect.poll(() => wire.filter((row) => row.method === 'PUT').length).toBe(1)

  await fields.nth(1).focus()
  await page.keyboard.type('1.25')
  await page.keyboard.press('Enter')

  /* THE HALF THAT IS NOT COSMETIC. With the loop wedged after the first write, the guard read
     "a save is in flight" forever and every later answer was typed, drawn, and never sent —
     the operator would have priced a box and closed a tab holding one row. The PUT replaces
     the document wholesale, so the second body must carry BOTH answers rather than the second
     alone. */
  await expect.poll(() => wire.filter((row) => row.method === 'PUT').length).toBe(2)
  expect(sentAnswers(wire)).toEqual({ '8608859': '4.50', '8608459': '1.25' })
  await expect(page.locator('.pricing-save')).toHaveText('Saved')
})

test('an answer typed while a write is in flight is not lost', async ({ page }) => {
  /* THE COALESCING PROMISE, WHICH THE COMMENT MADE AND THE CODE DID NOT KEEP. `dirty` was a
     flag, and a flag cannot tell "the write I just sent" from "the write that landed while it
     was in flight" — so clearing it on a response discarded whatever had been typed since
     that response left, silently and with the indicator reading `saved`. It is a comparison
     against the document the server confirmed now, so the second answer is still unequal when
     the first write lands and the loop runs again. */
  await open(page, { skus: [sku(), sku({ sku: '8608459', name: 'Dunsparce' })] })

  /* REGISTERED AFTER `open`, WHICH IS WHAT MAKES IT WIN. Playwright matches handlers newest
     first, so this shadows the one `open` installed and holds the first PUT open. */
  const wire: Wire[] = []
  let release = () => {}
  const held = new Promise<void>((resolve) => {
    release = resolve
  })
  /* THE WRITE IS `PUT /pricing` SINCE D86's AMENDMENT — one document for the store, not one
     per run. Re-registered here so the FIRST write is held open and the second answer is typed
     while it is in flight, which is the whole of what this case is about. */
  await page.route(/\/pricing$/, async (route) => {
    if (route.request().method() !== 'PUT') return route.fallback()
    wire.push({
      method: 'PUT',
      path: '/pricing',
      body: route.request().postDataJSON(),
    })
    if (wire.length === 1) await held
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, written: '/tmp/prices.json', answers: 2 }),
    })
  })

  const fields = field(page)
  await fields.nth(0).focus()
  await page.keyboard.type('4.50')
  await page.keyboard.press('Enter')
  await expect.poll(() => wire.length).toBe(1)

  await fields.nth(1).focus()
  await page.keyboard.type('1.25')
  await page.keyboard.press('Enter')

  release()

  await expect.poll(() => wire.length).toBe(2)
  expect(sentAnswers(wire)).toEqual({ '8608859': '4.50', '8608459': '1.25' })
  await expect(page.locator('.pricing-save')).toHaveText('Saved')
})

// ------------------------------------------------------- a preset reaches what emit reads

test('a preset writes the rule and the basis, which is what the pipeline reads', async ({
  page,
}) => {
  const wire = await open(page)

  await page.getByRole('button', { name: 'Market −5%' }).click()
  await expect.poll(() => wire.filter((row) => row.method === 'PUT').length).toBeGreaterThan(0)

  /* THE PRESS USED TO WRITE `preset: <key>`, WHICH NO READER ANYWHERE HAS.
     `pipeline/decisions.py:parse` does not know the field and `to_payload` does not emit it,
     so the next join dropped it and `rule`/`basis` stayed at `match`/`market` — the
     suggestions on screen moved and nothing `emit` reads did. Measured on the owner's
     riftbound run: that dead key beside `rule: match`, 2 overrides across 50 SKUs, 48 cards
     about to list at a price nobody chose. The rule at layer 4 is the thing that has to
     move, because D49 correctly refuses to write the suggestions as overrides at layer 1. */
  expect(sentPolicy(wire).rule).toBe('undercut:5')
  expect(sentPolicy(wire).basis).toBe('market')
  expect(sentPolicy(wire)).not.toHaveProperty('preset')

  /* AND NO ROW GAINED AN OVERRIDE. The whole reason the preset must move the RULE is that
     writing the suggestions would beat it — layer 1 over layer 4 — and produce a run where
     changing the preset silently changed nothing. */
  expect(sentAnswers(wire)).toEqual({})
})

test('the chip says which rule is live, and it is derived rather than remembered', async ({
  page,
}) => {
  await open(page)

  const match = page.getByRole('button', { name: 'Match market' })
  const under = page.getByRole('button', { name: 'Market −5%' })

  /* The run loads at `match`/`market`, so that chip is the live one before anything is
     pressed — read off the corpus's policy, not off a selection this screen remembers. */
  await expect(match).toHaveAttribute('aria-pressed', 'true')
  await expect(under).toHaveAttribute('aria-pressed', 'false')

  await under.click()
  await expect(under).toHaveAttribute('aria-pressed', 'true')
  await expect(match).toHaveAttribute('aria-pressed', 'false')
})

test('a hand-typed rule lights no chip rather than a stale one', async ({ page }) => {
  /* A rule outside the three presets is typed by hand into `inventory/prices.json`'s policy,
     so one no preset names is ordinary and
     must not be drawn as one of the three. A remembered selection would have lit whichever
     chip was pressed last, which is a claim about what untouched rows will list at — and the
     pair the pipeline reads is the only thing that can answer that. */
  await open(page, {
    decisions: { rule: 'markup:100', basis: 'market', sub_threshold: null, overrides: {} },
  })

  for (const label of ['Match market', 'Market −5%', 'TCG Low −1%']) {
    await expect(page.getByRole('button', { name: label })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  }
})


// ------------------------------------------------------- the price history (D62)
//
// THE GESTURE IS THE OWNER'S, 2026-08-31, and it is one sentence: point at a row, HOLD `t`,
// and "as soon as i release it goes away". The pointer aims and the key holds. The `T`
// button's click is the other opening and the only one that outlives itself.
//
// THE PROPERTY EVERY CASE HERE PROTECTS IS THAT THE PANEL DOES NOT FIRE ON A WALK. Every
// other assertion is about what is DRAWN; that one is about what is REQUESTED, and it is the
// only one whose failure is invisible on screen — a panel that read on the pointer looks
// identical and quietly fires one request per row at a free public mirror.

const asks = (wire: Wire[]) => wire.filter((call) => call.path.includes('/history'))

const panelOf = (page: Page) =>
  page.getByRole('complementary', { name: /Price history for/ })

/** The pointer, put on something, in one call. `hover()` runs actionability checks first and
 *  these cases care about what happens BETWEEN pointer moves, so the checks are time this
 *  file cannot afford to have spent for it. */
async function point(page: Page, at: Locator) {
  /* SCROLLED INTO VIEW FIRST, WHICH IS NOT PADDING EITHER. `boundingBox()` answers for an
     element that is off screen, so a move to those coordinates lands outside the viewport and
     no `pointerenter` fires anywhere — the gesture then reads the row the pointer was last
     over and the case asserts the wrong card with no sign of why. The screen leads with its
     landing deck now, so at this file's viewport the second row of the list starts below the
     fold. CENTRED rather than merely brought into view, because the ship bar is sticky at the
     bottom and a row scrolled to the fold sits under it. An operator scrolls to a row before
     pointing at it; so does this. */
  await at.evaluate((node) => node.scrollIntoView({ block: 'center' }))
  const box = await at.boundingBox()
  if (box === null) throw new Error('nothing to point at')
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
}

/** POINT AT A ROW AND HOLD `t`. The whole row is the target, not the `T` button in it. */
async function hold(page: Page, at = 0) {
  await point(page, page.locator('.pricing-row').nth(at))
  await page.keyboard.down('t')
}

/** THE PIN, which is the `T` button's click and — since the key became a hold — nothing else. */
const pin = (page: Page, at = 0) =>
  page.getByRole('button', { name: /Price history for/ }).nth(at).click()

test('holding `t` over a row reads it, and draws the average as the anchor', async ({
  page,
}) => {
  const wire = await open(page)
  await hold(page)

  const panel = panelOf(page)
  await expect(panel).toBeVisible()
  await expect(panel).toContainText('$18.81')
  expect(asks(wire).map((call) => call.path)).toEqual([
    `/pipeline/runs/${RUN}/history?sku=8608859`,
  ])

  /* THE ANCHOR IS DRAWN LARGER THAN THE BOUND, AND THAT IS THE HONESTY RULE AS A
     MEASUREMENT. `pipeline/pricehistory.py` names the failure: rendering the two "as though
     they were a price and an error bar of comparable authority". A class name cannot say
     which is bigger, so this reads the computed sizes — which goes red on any restyle that
     brings them level, however the selectors are renamed. */
  const figure = await panel
    .locator('.pricehistory-figure')
    .first()
    .evaluate((node) => parseFloat(getComputedStyle(node).fontSize))
  const bound = await panel
    .locator('.pricehistory-bound')
    .first()
    .evaluate((node) => parseFloat(getComputedStyle(node).fontSize))
  expect(figure).toBeGreaterThan(bound * 2)
})

test('the release puts it away, and holding it again asks nothing', async ({ page }) => {
  /* THE COMPLAINT THIS ANSWERS, in the owner's words: "the price data is valuable but it
     persisting on my screen till i close it is annoying". */
  const wire = await open(page)
  await hold(page)
  await expect(panelOf(page)).toBeVisible()

  await page.keyboard.up('t')
  await expect(panelOf(page)).toHaveCount(0)

  /* THE READING IS KEPT BY SKU, which is what makes a gesture this cheap to repeat
     affordable. Without it, a hand resting on `t` twice would read the same card twice. */
  await page.keyboard.down('t')
  await expect(panelOf(page)).toBeVisible()
  expect(asks(wire)).toHaveLength(1)
})

test('it holds while the cursor moves, and the release lets a new row be aimed', async ({
  page,
}) => {
  /* LATCHED AT THE PRESS. Re-aiming continuously would swap the panel out from under a hand
     that is only crossing the screen to reach it — the panel is in the far corner and the
     hand passes over every row between here and there. */
  await open(page, { skus: [sku(), sku({ sku: '8608860', name: 'Zapdos' })] })
  await hold(page, 0)
  await expect(panelOf(page)).toContainText('sku 8608859')

  await point(page, page.locator('.pricing-row').nth(1))
  await expect(panelOf(page)).toContainText('sku 8608859')

  await page.keyboard.up('t')
  await expect(panelOf(page)).toHaveCount(0)

  await hold(page, 1)
  await expect(panelOf(page)).toContainText('sku 8608860')
  await page.keyboard.up('t')
})

test('pointing at a row asks for nothing — only the press does', async ({ page }) => {
  /* THE LOAD-BEARING CASE, and the reason the gesture is a KEY and not a rest of the pointer:
     a reading is a request to two public mirrors, so a pointer crossing this list on its way
     somewhere else must not spend one. */
  const wire = await open(page, { skus: [sku(), sku({ sku: '8608860', name: 'Zapdos' })] })

  await point(page, page.locator('.pricing-row').nth(0))
  await point(page, page.locator('.pricing-row').nth(1))
  await point(page, page.locator('.pricing-title'))
  await page.waitForTimeout(400)

  expect(asks(wire)).toHaveLength(0)
  await expect(panelOf(page)).toHaveCount(0)
})

test('the pointer wins over the focused row', async ({ page }) => {
  /* THE HANDS ARE IN A FIELD WHILE THE EYES ARE SOMEWHERE ELSE. The row being asked about is
     the one being pointed at, which is the whole shape of the gesture. */
  await open(page, { skus: [sku(), sku({ sku: '8608860', name: 'Zapdos' })] })
  await field(page).first().click()

  await hold(page, 1)
  await expect(panelOf(page)).toContainText('sku 8608860')
  await page.keyboard.up('t')
})

test('with nothing pointed at, the focused row answers', async ({ page }) => {
  /* THE FALLBACK, so the gesture still works with the mouse parked off the list — which is
     where it sits while both hands are pricing. */
  await open(page, { skus: [sku(), sku({ sku: '8608860', name: 'Zapdos' })] })
  await field(page).nth(1).click()
  await page.mouse.move(2, 2)

  await page.keyboard.down('t')
  await expect(panelOf(page)).toContainText('sku 8608860')
  await page.keyboard.up('t')
})

test('the `T` button pins, and a pin survives the walk', async ({ page }) => {
  /* A BINDING NOTHING ADVERTISES IS ONE ONLY THE PERSON WHO ASKED FOR IT WILL PRESS (D51), so
     the letter is on screen as a control and not only in a key handler — and since the key
     became a hold, this click is the only way to a panel that stays.

     IT DOES NOT FOLLOW FOCUS, which is what D62 closed structurally: a walk down a fifty-SKU
     list would otherwise be fifty reads at a free public mirror for readings nobody asked
     for. Two rows and two arrow presses are enough to catch it. */
  const wire = await open(page, { skus: [sku(), sku({ sku: '8608860', name: 'Zapdos' })] })
  await pin(page, 0)
  await expect(panelOf(page)).toBeVisible()
  expect(asks(wire)).toHaveLength(1)

  await field(page).first().click()
  await page.keyboard.press('ArrowDown')
  await page.keyboard.press('ArrowUp')
  expect(asks(wire)).toHaveLength(1)
  await expect(panelOf(page)).toContainText('sku 8608859')

  // And the same button closes it, which is the other half of a pin being deliberate.
  await pin(page, 0)
  await expect(panelOf(page)).toHaveCount(0)
})

test('a hold cannot spend a pin — the pinned card comes back on the release', async ({
  page,
}) => {
  /* `peek ?? pinned` RATHER THAN ONE SLOT. With one slot, a glance at another row would
     re-aim the panel the operator had deliberately left open — and since the panel prints its
     SKU, that would not read as wrong, only as no longer the card that was asked about. */
  await open(page, { skus: [sku(), sku({ sku: '8608860', name: 'Zapdos' })] })
  await pin(page, 0)
  await expect(panelOf(page)).toContainText('sku 8608859')

  await hold(page, 1)
  await expect(panelOf(page)).toContainText('sku 8608860')

  await page.keyboard.up('t')
  await expect(panelOf(page)).toContainText('sku 8608859')
  await expect(panelOf(page).locator('.pricehistory-controls').getByRole('button', { name: 'Close' })).toBeVisible()
})

test('the footer says which panel it is, and `Keep open` makes a hold into a pin', async ({
  page,
}) => {
  /* THE ONLY PLACE THE TWO OPENINGS DIFFER ON SCREEN. A pin ends on a press and offers it; a
     held peek ends on the release, so what it offers instead is the way to stop that —
     reachable because the other hand is still on the mouse.

     SCOPED TO THE PANEL'S OWN FOOTER, because the drawer's header carries a Close of its own
     now — the one that shuts the drawer whichever tab is showing. The footer is where the two
     openings differ, so the footer is what this reads. */
  await open(page)
  await hold(page)
  const keep = panelOf(page).getByRole('button', { name: 'Keep open' })
  await expect(keep).toBeVisible()

  await keep.click()
  await page.keyboard.up('t')
  await expect(panelOf(page)).toBeVisible()
  await expect(panelOf(page).locator('.pricehistory-controls').getByRole('button', { name: 'Close' })).toBeVisible()
})

test('losing the window mid-hold releases it', async ({ page }) => {
  /* A KEYUP THAT NEVER ARRIVES. Cmd-Tab away holding `t` and the release is delivered to
     somebody else's window — so the panel would be standing when the operator came back,
     which is exactly the state this gesture exists to prevent. */
  await open(page)
  await hold(page)
  await expect(panelOf(page)).toBeVisible()

  await page.evaluate(() => window.dispatchEvent(new Event('blur')))
  await expect(panelOf(page)).toHaveCount(0)
  await page.keyboard.up('t')
})

test('the hold panel keeps the keyboard, so `t` there is not this gesture', async ({
  page,
}) => {
  /* D49's reasons are letter keys too, and its note is a field somebody types PROSE into.
     Both are covered: the panel owns the keyboard while it is up, and a letter typed into any
     field on this screen but a price field is a character rather than a command. */
  const wire = await open(page)
  await field(page).click()
  await page.keyboard.press('h')
  await expect(page.locator('.pricing-holdpanel')).toBeVisible()

  await page.getByLabel('Note').fill('t')
  await page.keyboard.press('t')
  await expect(panelOf(page)).toHaveCount(0)
  expect(asks(wire)).toHaveLength(0)
})

test('both ranges are drawn, and the panel says they overlap', async ({ page }) => {
  await open(page)
  await hold(page)
  const panel = panelOf(page)

  /* THE MACHINE STRINGS, VERBATIM — `month` and `annual` are the endpoint's own range names
     and docs/DESIGN.md's owner-screen rule is that they are drawn rather than relabelled. */
  await expect(panel).toContainText('month')
  await expect(panel).toContainText('annual')

  /* THEY POINT OPPOSITE WAYS AND BOTH ARE DRAWN. Vilemaw's real numbers: a screen that
     merged the two ranges could not show both, and one that dropped the sentence would leave
     `+71.2%` beside `-33.9%` reading as a broken screen. */
  await expect(panel).toContainText('+71.2%')
  await expect(panel).toContainText('rising')
  await expect(panel).toContainText('-33.9%')
  await expect(panel).toContainText('falling')
  await expect(panel).toContainText(/[Rr]anges overlap/)
  await page.keyboard.up('t')
})

test('the export price is drawn beside the reading, and nothing averages them', async ({
  page,
}) => {
  await open(page)
  await hold(page)
  // D8's figure, labelled as the export's, next to the reading rather than mixed into it.
  /* The label is drawn in sentence case now, which is the rebuild's rule for every label on
     the product; what it names is unchanged. */
  await expect(panelOf(page)).toContainText('Export market')
  await expect(panelOf(page)).toContainText('$22.03')
  await page.keyboard.up('t')
})

test('a card that has never sold says so, and does not read as a failure', async ({ page }) => {
  /* THE ENDPOINT ANSWERS HTTP 200 WITH A NULL RESULT for a real, catalogued product that has
     never traded — measured on two of them — so this is not an error arm. A screen that drew
     it as one would report a join defect over a card that is merely illiquid. */
  await open(page, { history: history({ ranges: [], never_sold: true }) })
  await hold(page)
  await expect(panelOf(page)).toContainText('No recorded sales')
  await expect(panelOf(page)).toContainText(/has not traded/)
  await page.keyboard.up('t')
})

test('a refusal draws the sentence the server sent, and offers a retry', async ({ page }) => {
  /* PINNED FOR THIS ONE, AND THAT IS THE ARGUMENT FOR KEEPING A PIN AT ALL: `Try again` is a
     control, and a panel that lives as long as a key is held is not somewhere a second
     deliberate act can happen. */
  const wire = await open(page, { history: 'refuse' })
  await pin(page)
  const panel = panelOf(page)
  await expect(panel).toContainText(/not in a catalogued product line/)
  expect(asks(wire)).toHaveLength(1)

  /* THE RETRY IS THE ONLY WAY PAST THE CACHE, and a refusal is cached like a reading is —
     without that, a card whose mirror was down would re-read on every press and the panel
     would look idle while hammering a host that is already struggling. */
  await panel.getByRole('button', { name: 'Try again' }).click()
  await expect.poll(() => asks(wire).length).toBe(2)
})

test('the photograph yields to a hold and comes back, and a pin closes it', async ({ page }) => {
  /* BOTH PANELS ARE FIXED IN THE SAME CORNER — `PriceHistory.css` carries why that corner is
     the right one — so only one may be drawn. A PRESS closes the other outright; a hold only
     HIDES it, because a gesture this cheap to make must not spend anything the operator has
     to restore by hand. */
  await open(page)
  await field(page).click()
  await page.keyboard.press('p')
  await expect(page.getByRole('complementary', { name: /Photograph of/ })).toBeVisible()

  await hold(page)
  await expect(panelOf(page)).toBeVisible()
  await expect(page.getByRole('complementary', { name: /Photograph of/ })).toHaveCount(0)

  await page.keyboard.up('t')
  await expect(page.getByRole('complementary', { name: /Photograph of/ })).toBeVisible()

  await pin(page)
  await expect(page.getByRole('complementary', { name: /Photograph of/ })).toHaveCount(0)
})

test('`p` closes a pinned reading, which is the half of the exclusion that was missing', async ({
  page,
}) => {
  /* `t` cleared the photograph and `p` did not clear the history, so the two drew over each
     other in the one corner `PriceHistory.css` argues for. */
  await open(page)
  await pin(page)
  await expect(panelOf(page)).toBeVisible()

  await field(page).click()
  await page.keyboard.press('p')
  await expect(page.getByRole('complementary', { name: /Photograph of/ })).toBeVisible()
  await expect(panelOf(page)).toHaveCount(0)
})


// ------------------------------------------------------------------ the trend strip (D79)

test('the strip draws nothing until it is asked for, and the press is what asks', async ({
  page,
}) => {
  /* D62 MADE THE READ A PRESS AND D79 KEPT IT ONE. The batch is ~92 requests at two free
     public mirrors, 37.7s cold — batching makes that one decision instead of fifty, not
     cheap. A screen that read it on arrival would spend the walk on every visit for readings
     nobody asked for, which is the rudeness D62 closed structurally. THE ASSERTION THAT
     MATTERS IS THE WIRE ONE: an empty cell could equally be a request that answered nothing,
     and this is a case about no request being made. */
  const wire = await open(page)
  await expect(page.locator(VIEW)).toBeVisible()
  expect(wire.filter((call) => call.path.includes('/trends'))).toHaveLength(0)
  await expect(strip(page).first()).toBeEmpty()

  await loadTrends(page).click()
  await expect(strip(page).first().locator('svg')).toHaveCount(2)
  expect(wire.filter((call) => call.path.includes('/trends')).length).toBeGreaterThan(0)
})

test('the strip carries a shape and a sign, and no money at all', async ({ page }) => {
  /* THE D8 GUARD AS A TEST RATHER THAN A PARAGRAPH, and the one case here most worth having.
     The row already has four dollar columns and the field a listing price is typed into, so a
     reading denominated in money would sit one column from that field and be one keystroke
     from becoming a price — the reopening D62 refused by name. The vwap, its bound, the
     liquidity and the spread all stay on the panel; a later session widening the strip's
     payload to carry one of them fails here. */
  await open(page)
  await loadTrends(page).click()
  await expect(strip(page).first().locator('svg')).toHaveCount(2)

  const text = (await strip(page).allTextContents()).join(' ')
  expect(text).not.toContain('$')
  expect(text).toMatch(/\+71\.2%/)
  expect(text).toMatch(/−33\.9%|-33\.9%/)
})

test('a row this run can add nothing for is never asked about, and is not drawn as a failure', async ({
  page,
}) => {
  /* THE OWNER'S INSTRUCTION OF 2026-08-31 — "I don't need the prices for the rows that have
     none left" — and `at_cap` is the field the join writes, so the filter and the list's own
     grouping of those rows read ONE fact rather than two rules kept in step. Asserted on the
     WIRE and not only on the screen: an empty cell is what a refusal would draw too, and the
     saving being claimed is the request not made. */
  const wire = await open(page, {
    skus: [
      sku({ sku: '111', name: 'Open card' }),
      sku({
        sku: '222',
        name: 'Closed card',
        at_cap: true,
        nothing_to_add: 'every copy in this run is already listed or has left the box',
      }),
    ],
  })
  await loadTrends(page).click()
  await expect(strip(page).first().locator('svg')).toHaveCount(2)

  const asked = wire
    .filter((call) => call.path.includes('/trends'))
    .flatMap((call) => new URL(call.path, 'http://x').searchParams.getAll('sku'))
  expect(asked).toContain('111')
  expect(asked).not.toContain('222')

  /* AND THE COUNT IS ON SCREEN. Without it a strip over one of two rows reads as one
     failure; `1 not asked` is what says the row was never a question. */
  await expect(page.locator('.pricing-trendbar-says')).toContainText('1 not asked')
  await expect(strip(page).nth(1)).toBeEmpty()
})

test('a SKU the batch answers for neither way is refused on the row, never left reading', async ({
  page,
}) => {
  /* CLAUDE.md's HARD RULE, SPENT ON THE CLIENT. The route promises both directions; this is
     the case where it breaks that promise anyway — a SKU in neither `skus` nor `refused`. It
     must land as a refusal rather than sit on `reading…` for the rest of the session, which
     is the silent drop that rule forbids wearing a spinner. */
  await open(page, {
    skus: [sku({ sku: '111', name: 'Answered' }), sku({ sku: '222', name: 'Dropped' })],
    trends: (asked) => {
      const full = trends(asked.filter((s) => s !== '222'))
      return { ...full, asked: asked.length }
    },
  })
  await loadTrends(page).click()
  await expect(strip(page).first().locator('svg')).toHaveCount(2)
  await expect(strip(page).nth(1)).toContainText('—')
  await expect(strip(page).nth(1)).not.toContainText('reading')
})

test('the spans and the overlap caveat are stated once, above the list', async ({ page }) => {
  /* D62's PANEL OWES A READER THREE THINGS AND AN 80px CELL CARRIES NONE OF THEM: that the
     ranges overlap and routinely point opposite ways, what span each covers, and that the
     wider one can be the staler. They are stated once here rather than forty-six times, which
     is honest only because the spans are identical across every SKU of a run. Without the
     sentence, `+71%` beside `−34%` on one row reads as a broken screen. */
  await open(page)
  await loadTrends(page).click()
  const says = page.locator('.pricing-trendbar-says')
  await expect(says).toContainText('2026-08-01')
  await expect(says).toContainText('2025-09-08')
  /* THE CAVEAT IS SAID SHORT ON THE STRIP AND IN FULL WHERE A READING IS READ. The bar names
     it — `ranges overlap` — and carries the whole sentence on hover; the panel that draws the
     two figures states it outright, which is where `+71%` beside `−34%` is actually looked at.
     Both are asserted, so neither can go. */
  await expect(page.locator('.pricing-trendbar-why')).toContainText('ranges overlap')
  await expect(page.locator('.pricing-trendbar-why')).toHaveAttribute(
    'title',
    /Ranges overlap and can point opposite ways/,
  )
  /* AND EXACTLY ONCE. A span drawn per row is the failure this case exists to catch. */
  await expect(page.locator('.pricing-trendbar-span')).toHaveCount(2)

  await hold(page)
  await expect(panelOf(page)).toContainText('Ranges overlap and can point opposite ways')
  await page.keyboard.up('t')
})

/* ---------------------------------------------------------------- the bottom-left corner
 *
 * D85, AND THE FORM THESE TAKE IS THE POINT. Four things want this screen's bottom-left
 * corner — every row's T and H, the reading panel, the photograph, and the ship bar — and the
 * defect they produced was invisible to all 56 cases above it. `bbf7e11` moved T and H into
 * the corner and raised them to `z-index: 21` to win it; they then drew over the panel they
 * were escaping AND over the ship bar, so every row scrolled behind the bar punched its two
 * letters through it and took the clicks landing there. A press at the bar's left edge opened
 * a hold on a card nobody could see, and a hold writes `inventory/prices.json`.
 *
 * NOTHING ON THE COMMIT PATH COULD TELL. The suite was green, typecheck was green, lint was
 * green; the screen was a pile. What this file had was text, grid templates and row heights,
 * and every one of those was still true. The missing question is geometric and it is asked by
 * HIT-TESTING rather than by comparing rectangles: `elementFromPoint` answers what a hand
 * aiming at a pixel actually reaches, which is the property that broke, and it is indifferent
 * to HOW a later change breaks it — a stacking order, an anchor, a width.
 *
 * `overlaps()` ONE SCREEN OVER DOES THE RECTANGLE HALF, and this deliberately does not reuse
 * it: two boxes that intersect is the normal, correct state of an overlay above a list. The
 * fault was never the intersection. It was who answered inside it. */

/** Every point in `region` that a `.pricing-row` answers for — the hand's-eye view of who owns
 *  the pixels. An 8px lattice: the controls at issue are 32px squares, so nothing that could
 *  swallow a press fits between the samples. */
async function rowsShowingThrough(page: Page, region: string): Promise<number> {
  return page.evaluate((selector) => {
    const panel = document.querySelector(selector)
    if (panel === null) throw new Error(`nothing at ${selector}`)
    const box = panel.getBoundingClientRect()
    /* INSET PAST THE CORNER RADIUS, because `elementFromPoint` respects a rounded corner and
       these surfaces have one now: a sample 4px into the bounding box of a 16px radius is
       OUTSIDE the painted shape, so whatever is behind answers for it — correctly. That is a
       pixel the bar does not own and never claimed to, and counting it made this case fail
       about once a run depending on where the list happened to be scrolled. The inset is the
       element's own radius rather than a guessed margin, and the interior — every pixel a
       press aimed at the bar actually lands on — is still swept at 8px. */
    const radiusOf = (el: Element): number => {
      const style = getComputedStyle(el)
      return Math.max(
        ...[
          style.borderTopLeftRadius,
          style.borderTopRightRadius,
          style.borderBottomLeftRadius,
          style.borderBottomRightRadius,
        ].map((one) => parseFloat(one) || 0),
      )
    }
    /* THE CORNER MAY BE AN ANCESTOR'S: the reading panel is square and the drawer that clips
       it is not, so the shape a pointer meets is the drawer's. Climbed rather than assumed. */
    let radius = radiusOf(panel)
    for (let el = panel.parentElement; el !== null && el !== document.body; el = el.parentElement) {
      const rect = el.getBoundingClientRect()
      const clips = getComputedStyle(el).overflow !== 'visible'
      if (clips && rect.left <= box.left + 1 && rect.right >= box.right - 1) {
        radius = Math.max(radius, radiusOf(el))
      }
    }
    const pad = Math.ceil(radius) + 2
    let through = 0
    for (let y = Math.round(box.top) + pad; y < box.bottom - pad; y += 8) {
      for (let x = Math.round(box.left) + pad; x < box.right - pad; x += 8) {
        const at = document.elementFromPoint(x, y)
        if (at !== null && at.closest('.pricing-row') !== null) through += 1
      }
    }
    return through
  }, region)
}

/** Which of the ship bar's own controls another element answers for. A control the operator
 *  can see and cannot press is the shape this corner failed in, and `emit` refuses to run
 *  without the sub-threshold answer these set. */
async function barControlsBlocked(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const blocked: string[] = []
    document.querySelectorAll('.pricing-ship button, .pricing-ship input').forEach((node) => {
      const box = node.getBoundingClientRect()
      const at = document.elementFromPoint(box.left + box.width / 2, box.top + box.height / 2)
      if (at !== null && at !== node && !node.contains(at)) {
        blocked.push(`${(node.textContent || '').trim() || node.className} <- ${at.className}`)
      }
    })
    return blocked
  })
}

/** A run long enough that rows are behind the bar rather than above it. Forty is past the
 *  viewport at every size this suite runs, and the case is about the ones you cannot see. */
const manySkus = () =>
  Array.from({ length: 40 }, (_, at) =>
    sku({ sku: `9${String(at).padStart(6, '0')}`, name: `Card ${at}` }),
  )

test('no row draws through the ship bar, at either of the bar heights', async ({ page }) => {
  await open(page, { skus: manySkus() })
  await expect(page.locator('.pricing-ship')).toBeVisible()

  /* CLOSED FIRST. The bar is ~125px here and two rows sit behind it. */
  expect(await rowsShowingThrough(page, '.pricing-ship')).toBe(0)

  /* AND WITH THE RECEIPT UP, which is the state the owner reported from. IT NO LONGER GROWS
     THE BAR — the receipt is a dialog over a scrim now rather than a block that unfolds
     inside it — so the second state this case is about is a second SURFACE rather than a
     second height: the bar still owns its own pixels, and the receipt owns the ones it
     covers. A row answering for a point inside either is the same fault it always was. */
  await page.getByRole('button', { name: 'Write the import file' }).click()
  await page.getByRole('button', { name: /files$/ }).click()
  await expect(page.locator('.pricing-ship-receipt')).toBeVisible()
  expect(await rowsShowingThrough(page, '.pricing-ship')).toBe(0)
  expect(await rowsShowingThrough(page, '.pricing-ship-receipt')).toBe(0)
})

test('the bar publishes its measured height, so the panels above it clear the real one', async ({
  page,
}) => {
  /* THE VARIABLE IS THE DEFECT CLASS, NAMED. `--pricing-ship-h` was read by three
     declarations and set by nothing from D54 until D85 — every one of them took the `64px`
     fallback against a bar that is 125px closed and 433px with a receipt. A fallback that is
     the only value a property ever has is not a fallback, and nothing said so out loud. */
  await open(page, { skus: manySkus() })

  const agrees = async () =>
    page.evaluate(() => {
      const main = document.querySelector<HTMLElement>('main.pricing')
      const bar = document.querySelector<HTMLElement>('.pricing-ship')
      if (main === null || bar === null) throw new Error('no bar')
      const published = getComputedStyle(main).getPropertyValue('--pricing-ship-h').trim()
      return { published, measured: `${bar.offsetHeight}px` }
    })

  await expect(page.locator('.pricing-ship')).toBeVisible()
  const closed = (await agrees()).measured

  /* THE TWO AGREE, AND THE HEIGHT IS NOT PINNED TO A NUMBER. The bar's height is a function
     of this fixture — a run with no sub-threshold SKUs draws one fewer row than the owner's
     did — so a literal here would assert what the fixture happens to be and would have to be
     re-typed every time the bar gained a line. What must be true is that the published value
     is the measured one, whatever the bar is. On the code this case was written against,
     `published` was the empty string. */
  await expect.poll(agrees).toEqual({ published: closed, measured: closed })
  expect(closed).toMatch(/^\d+px$/)

  /* AND IT FOLLOWS THE BAR RATHER THAN BEING WRITTEN ONCE. The receipt no longer changes the
     bar's height — it is a dialog now — so the state that proves the measurement is live is
     the one that still changes it with no press and no navigation behind it: the bar gains a
     row when a write leaves a receipt to link to. A one-shot measurement at mount reports
     green through that exactly as it did through the old one. */
  await page.getByRole('button', { name: 'Write the import file' }).click()
  await expect(page.getByRole('button', { name: /files$/ })).toBeVisible()
  await expect
    .poll(async () => {
      const seen = await agrees()
      return seen.published === seen.measured
    })
    .toBe(true)
})

test('an open reading covers no ship-bar control and no row draws through it', async ({
  page,
}) => {
  await open(page, { skus: manySkus() })

  /* THE WORST CASE, BUILT DELIBERATELY: the fullest bar under the tallest panel. The bar
     gains its receipt link once a write has landed, which is the state where its controls sit
     closest to the panel's edge. */
  await page.getByRole('button', { name: 'Write the import file' }).click()
  await expect(page.getByRole('button', { name: /files$/ })).toBeVisible()

  await pin(page)
  await expect(panelOf(page)).toBeVisible()

  expect(await barControlsBlocked(page)).toEqual([])
  expect(await rowsShowingThrough(page, '.pricehistory')).toBe(0)

  /* AND THE PANEL AND THE ROW'S OWN CONTROL DO NOT SHARE A COLUMN, which is the mechanism
     rather than the symptom — stated so a later change that restores the overlap and re-settles
     it with a stacking order fails here rather than passing on the two counts above.

     WHICH SIDE IS NOT ASSERTED, AND THAT IS THE ONLY THING THAT MOVED. The panel used to be
     pinned to the right of the row's gutter; it is a drawer on the left of the content column
     now, and the row's `T` sits at the right end of the row. Naming a side would be pinning the
     drawer's corner; what has to hold either way is that the two do not overlap. */
  const clears = await page.evaluate(() => {
    const panel = document.querySelector('.pricehistory')
    const button = document.querySelector('.pricing-history')
    if (panel === null || button === null) throw new Error('no panel')
    const a = panel.getBoundingClientRect()
    const b = button.getBoundingClientRect()
    return a.left >= b.right || a.right <= b.left
  })
  expect(clears).toBe(true)
})

// ------------------------------- the worklist spans runs, and the answer is the store's (D86)

/* THE CASE THAT PAYS FOR THE WHOLE FEATURE, and it is a real one off the owner's disk.
 *
 * Measured 2026-09-01 across the eight runs in `runs/`: 78 of 423 SKUs sit in more than one
 * run, 8 carried an answer in more than one, and THREE were a `withheld` hold answered with a
 * price in a later sitting. SKU 9191210 — LeBlanc, Everywhere At Once — was held `bullish`
 * with `watch_above: "5"` out of box 3 on 08-31 and listed at $3.45 out of box 4 on 09-01,
 * below the operator's own watch.
 *
 * THAT STATE IS NOW UNREPRESENTABLE, WHICH IS WHY THESE CASES ASSERT A SHAPE AND NOT A
 * WARNING. The first build of D86 detected the disagreement and drew it on the row; the owner
 * asked why the duplication existed at all, and the answer moved into one corpus keyed by SKU.
 * A card cannot be answered two ways, so there is nothing to detect. */
const SPAN = {
  runs: [
    { run: '2026-08-31-box3-01', box: 3, box_name: 'RB Epics', skus: 2 },
    { run: '2026-09-01-box4-01', box: 4, box_name: 'WB1 R2', skus: 2 },
  ],
  skus: [
    {
      ...sku({
        sku: '9191210',
        name: 'LeBlanc, Everywhere At Once',
        copies: 3,
        add_to_quantity: 3,
        positions: [
          { box: 3, index: 4, label: 'Box 3 · Section 1 · Card 4' },
          { box: 3, index: 9, label: 'Box 3 · Section 1 · Card 9' },
          { box: 4, index: 2, label: 'Box 4 · Section 1 · Card 2' },
        ],
      }),
      in: [
        { run: '2026-08-31-box3-01', add_to_quantity: 2 },
        { run: '2026-09-01-box4-01', add_to_quantity: 2 },
      ],
      claimed_add: 4,
      over_cap: true,
    },
    {
      /* A CARD IN ONE DRAWER ONLY, so the case also proves the line is NOT drawn where there
         is nothing to say — a marker on every row is a marker nobody reads. */
      ...sku({ sku: '8608459', name: 'Dunsparce' }),
      in: [{ run: '2026-09-01-box4-01', add_to_quantity: 3 }],
      claimed_add: 3,
      over_cap: false,
    },
  ],
}

/* THE SAME BAR AT A PHONE'S WIDTH, WHICH NOTHING HAD LOOKED AT (D117).
 *
 * `app/tests/phone.spec.ts` sweeps every route at 390 and cannot reach this: the ship bar needs a
 * loaded run and that file carries no pricing fixtures, so its own bar case was silently vacuous
 * — it guarded on `if (await bar.count())` and the bar was never there. The fixtures are here, so
 * the case is here, which is `fulfillment.spec.ts`'s WIDTHS idiom: assert at the second width in
 * the spec that owns the data.
 *
 * MEASURED BEFORE THE FIX: 430px of an 844px viewport, and `Pick a run` underneath it — a control
 * the operator could see and could not press. The bar wrapped to four rows because the cap
 * sentence and two long checkbox labels each took one; the sentence is hidden on a phone now and
 * the labels have short forms. */
test('the ship bar leaves the phone a screen to work on, and covers no control', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  /* TWO RUNS, WHICH IS THE BAR THIS IS ABOUT. `#/pricing` draws two different ship bars: a
     single-run one, and — at `loaded.length >= 2` — the one carrying the cap sentence and both
     split checkboxes. That second bar is what stood 430px tall. A one-run fixture renders the
     short bar and every mutation of the fix passes against it, which is how this case was
     vacuous the first time it was written. */
  await open(page, {
    worklist: {
      runs: SPAN.runs,
      /* FORTY ROWS, so the list runs past the fold and the header's own controls sit behind the
         bar rather than above it. Two rows is a fixture where nothing CAN be covered and every
         mutation of the fix passes against it — which is what this case did on its first run,
         in 2.5 seconds. */
      skus: Array.from({ length: 40 }, (_, at) => ({
        ...sku({ sku: `9${String(at).padStart(6, '0')}`, name: `Card ${at}` }),
        in: [{ run: SPAN.runs[0]!.run, add_to_quantity: 1 }],
        claimed_add: 1,
        over_cap: false,
      })),
    },
  })
  await expect(page.locator('.pricing-ship')).toBeVisible()

  /* THE BOUND IS A MEASUREMENT, AND IT MOVED ONCE ON PURPOSE. It was 180 — the bar was the
     status, the two split checkboxes, and the primary — and D7's rewrite added a real control
     to it: `at most [ ] each`, the cap this press asks for. That does not fit beside the two
     checkboxes at 390 (160 + 90 + 148 against 334 of usable width), so the bar is genuinely a
     row taller and the honest number is 210, not 180.
     WHAT IS NOT NEGOTIABLE IS THE REST OF THIS CASE. 204px is 24% of the viewport and covers
     nothing; the defect this was written for was 430px — half the screen — with `Pick a run`
     unpressable underneath it. A bound that only ever moves up is worthless, so the two
     assertions below are the ones that bite, and this one is the early warning.
     Measured on this fixture: 152 before the cap control, 204 with it, 430 on the owner's own
     store before the cap sentence and the checkbox labels had phone forms. */
  const height = await page.locator('.pricing-ship').evaluate((el) => el.getBoundingClientRect().height)
  expect(height, `the ship bar is ${Math.round(height)}px tall at 390 — it is meant to be three rows`).toBeLessThan(210)

  // its own controls answer for themselves
  expect(await barControlsBlocked(page)).toEqual([])

  /* AND NOTHING ELSE ON THE SCREEN IS PERMANENTLY UNDERNEATH IT. `barControlsBlocked` looks
     inside the bar; what failed was a control OUTSIDE it — `Pick a run` and `Give this run its
     own cut-off`, both visible and both unpressable.
     THE TEST IS "CAN IT BE SCROLLED CLEAR", NOT "IS IT CLEAR RIGHT NOW", which is the property
     that actually separates a sticky bar from the tab bar. Content passes under the tab bar all
     day and that is fine, because `.bn-shell-main` pads its foot and a scroll brings anything
     out. The ship bar had no such padding, so a control under it stayed under it. Each candidate
     is scrolled to and asked again. */
  const look = async () =>
    page.evaluate(() => {
      const out: string[] = []
      for (const el of document.querySelectorAll('button, a[href]')) {
        const r = el.getBoundingClientRect()
        if (r.width === 0 || r.top < 0 || r.bottom > window.innerHeight) continue
        const at = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)
        /* THE SHELL'S OWN FIXED CHROME IS NOT THIS BAR'S DOING. Content scrolls under the phone
           top bar and the tab bar by design — `.bn-shell-main` pads its foot for exactly that —
           so a row that happens to sit under the app bar at the moment of the sweep is not a
           finding, and counting it made this case fail one run in three. */
        if (at !== null && at.closest('.bn-topbar, .bn-tabbar') !== null) continue
        if (at !== null && !el.contains(at) && !at.contains(el)) {
          out.push(`${(el.textContent ?? '').trim().slice(0, 30)} <- ${at.className}`)
        }
      }
      return out
    })

  /* A CONTROL UNDER THE BAR RIGHT NOW IS NOT THE DEFECT — one that stays there is. The tab bar
     covers content all day and that is fine, because a scroll brings it out. So each candidate
     is scrolled to and asked again, and only the ones still underneath are reported. `Pick a
     run` failed that second question: the bar was 430px, the header sat inside it, and no
     scroll position existed where the control was clear. */
  const stuck = await page.evaluate(async () => {
    const out: string[] = []
    const rest = () => new Promise((go) => setTimeout(go, 60))
    for (const el of document.querySelectorAll('button, a[href]')) {
      const first = el.getBoundingClientRect()
      if (first.width === 0 || first.height === 0) continue
      const at0 = document.elementFromPoint(first.left + first.width / 2, first.top + first.height / 2)
      if (at0 === null || el.contains(at0) || at0.contains(el)) continue
      el.scrollIntoView({ block: 'center' })
      await rest()
      const r = el.getBoundingClientRect()
      if (r.top < 0 || r.bottom > window.innerHeight) continue
      const at = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)
      if (at !== null && at.closest('.bn-topbar, .bn-tabbar') !== null) continue
      if (at !== null && !el.contains(at) && !at.contains(el)) {
        out.push(`${(el.textContent ?? '').trim().slice(0, 30)} <- ${at.className}`)
      }
    }
    return out
  })
  expect(stuck, stuck.join('\n')).toEqual([])

  /* AND AT THE FOOT, which is the position the foot padding is for. The shell pads
     `.bn-shell-main` by the tab bar's height so anything can be scrolled clear of it; this
     screen pads by `--pricing-ship-h` for the same reason, and without it the last rows of a
     forty-row list have nowhere to go. */
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
  await page.waitForTimeout(250)
  /* AT MAX SCROLL THERE IS NOWHERE FURTHER TO GO, so what is under the bar here is under it for
     good. The assertion is geometric rather than a hit test: the last row has to END above the
     bar's top edge. A hit test at the centre passes while a row is half-covered, and half a row
     under a glass panel is the state this padding exists to prevent. Measured with the padding:
     the last row ends at 432 and the bar starts at 456. */
  const gap = await page.evaluate(() => {
    const bar = document.querySelector('.pricing-ship')!.getBoundingClientRect()
    const rows = [...document.querySelectorAll('.pricing-row')]
    const last = rows[rows.length - 1]!.getBoundingClientRect()
    return Math.round(bar.top - last.bottom)
  })
  expect(gap, `at the foot of the list the last row runs ${-gap}px into the ship bar`).toBeGreaterThanOrEqual(0)
  const foot = await look()
  expect(foot, foot.join('\n')).toEqual([])

  // no sideways scroll, which is the other floor CLAUDE.md publishes for this width
  const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(over, `the pricing screen scrolls sideways by ${over}px at 390`).toBeLessThanOrEqual(0)
})


test('one answer is written once, for the store, however many runs hold the card', async ({
  page,
}) => {
  const wire = await open(page, { worklist: SPAN })

  await field(page).first().focus()
  await page.keyboard.type('12.00')
  await page.keyboard.press('Enter')

  /* ONE PUT, AND THE PATH IS NOT A RUN'S. This is the amendment to D86 at the write path. It
     was one write per run holding the card, into files that could disagree — the state that
     put three deliberate holds under a later price. There is one document now, so there is one
     write, and a second PUT here would mean a per-run copy had come back. */
  await expect.poll(() => wire.filter((row) => row.method === 'PUT').length).toBe(1)
  const puts = wire.filter((row) => row.method === 'PUT')
  expect(puts.map((row) => row.path)).toEqual(['/pricing'])
  expect(sentAnswers(wire)['9191210']).toBe('12.00')
  await expect(page.locator('.pricing-save')).toHaveText('Saved')
})

test('a card in two drawers says where it is once Compare is on, and a card in one says nothing', async ({
  page,
}) => {
  await open(page, { worklist: SPAN })

  const rows = page.locator('.pricing-row')
  await expect(rows).toHaveCount(2)

  /* RULING B: THE PLAIN BOX/RUN-SPAN TEXT IS DISCLOSURE-GATED BEHIND COMPARE, OFF BY
     DEFAULT — this is the red-first half: the span text is absent on arrival even for the
     over-cap row, because Compare has not been turned on for this section yet. */
  await expect(rows.nth(0).locator('.pricing-span-where')).toHaveCount(0)

  await page.getByRole('button', { name: 'Compare' }).first().click()

  /* THE BOXES AND NOT THE RUN NAMES, ONCE ASKED FOR. A person owns drawers, not directories;
     the runs are on the chips above. Deduped and ascending, which is the order the shelf is
     in. */
  await expect(rows.nth(0).locator('.pricing-span-where')).toHaveText('Boxes 3, 4 · 2 runs')

  /* THE ABSENCE, WHICH IS THE HALF A MARKER-ON-EVERY-ROW REGRESSION WOULD STILL SATISFY —
     Compare being on draws nothing for a card in one drawer, because there is nothing to
     compare. */
  await expect(rows.nth(1).locator('.pricing-row-span')).toHaveCount(0)
})

test('the over-cap warning is visible with Compare off, and the toggle does not hide a refusal', async ({
  page,
}) => {
  await open(page, { worklist: SPAN })

  /* D156's OWN PROMISE — "what cannot go is named on the deck, with a door each" — MUST
     SURVIVE THE NEW TOGGLE (a regression pin, not a red-first case: nothing hides this
     today and it must stay that way). The over-cap row's warning badge is visible with no
     click at all. */
  await expect(page.locator('.pricing-row').nth(0).locator('.pricing-span-cap')).toBeVisible()
  await expect(page.locator('.pricing-row').nth(0).locator('.pricing-span-cap')).toHaveText(
    'Runs claim 4 · 3 can go',
  )

  /* AND IT STAYS AFTER THE TOGGLE, TOO — Compare only ever ADDS context, it never removes a
     warning. */
  await page.getByRole('button', { name: 'Compare' }).first().click()
  await expect(page.locator('.pricing-row').nth(0).locator('.pricing-span-cap')).toBeVisible()
})

test('Compare toggle is one control per section, off by default', async ({ page }) => {
  await open(page, { worklist: SPAN })

  const toggle = page.getByRole('button', { name: 'Compare' }).first()
  await expect(toggle).toHaveAttribute('aria-pressed', 'false')

  /* LOW / +SHIP / DIRECT ARE HIDDEN UNTIL ASKED FOR. Only the Market column head is drawn
     by default; the caption is the caption's own ground truth for what a row can show. */
  await expect(page.locator('.pricing-caption-low')).toHaveCount(0)
  await expect(page.locator('.pricing-caption-low_with_shipping')).toHaveCount(0)
  await expect(page.locator('.pricing-caption-direct_low')).toHaveCount(0)
  await expect(page.locator('.pricing-caption-market')).toBeVisible()
  await expect(page.locator('.pricing-row').first().locator('.pricing-ref-low')).toHaveCount(0)
  await expect(page.locator('.pricing-row').first().locator('.pricing-ref-market')).toBeVisible()

  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.pricing-caption-low')).toBeVisible()
  await expect(page.locator('.pricing-row').first().locator('.pricing-ref-low')).toBeVisible()
})

test('Compare survives a reload, per browser, on the device-local key', async ({ page }) => {
  /* RED-FIRST AGAINST THE FIRST BUILD: Compare was `useState`, forgotten on every reload — an
     operator pricing hundreds of rows in one sitting had to re-press it per section every time
     they opened the screen. `deviceMemory.ts:rememberPricingCompare` persists the on/off set
     to `banchi.pricing.compare`, the same kind of fact as `banchi.inventory.hide-sold`: how
     THIS browser is dressed, never a card. */
  await open(page, { worklist: SPAN })

  const toggle = page.getByRole('button', { name: 'Compare' }).first()
  await expect(toggle).toHaveAttribute('aria-pressed', 'false')
  await expect(page.locator('.pricing-caption-low')).toHaveCount(0)

  await toggle.click()
  await expect(toggle).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.pricing-caption-low')).toBeVisible()

  await page.reload()
  await settleFonts(page)
  await expect(page.locator(VIEW)).toBeVisible()

  /* THE RULING'S DEFAULT IS UNCHANGED ON A FRESH BROWSER — this is the SAME browser, having
     asked once, so the columns come back on without a second press. */
  const toggleAfterReload = page.getByRole('button', { name: 'Compare' }).first()
  await expect(toggleAfterReload).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.pricing-caption-low')).toBeVisible()
  await expect(page.locator('.pricing-row').first().locator('.pricing-ref-low')).toBeVisible()
})

test('l/s/d snap keys act only while Compare is on; m always works', async ({ page }) => {
  const wire = await open(page, { worklist: SPAN })

  await field(page).first().focus()
  const before = await field(page).first().inputValue()
  await page.keyboard.press('l')
  /* RED-FIRST: WITH COMPARE OFF, A HIDDEN COLUMN'S KEY DOES NOTHING (Ruling B option (b),
     D49 amended) — a command reaching a figure the operator cannot see breaks the
     alphabet's own legibility even though D118 never names this exact case. The field's
     rule-price default already carries digits, so the assertion is that `l` changed
     NOTHING — never that the field is blank. */
  await expect(field(page).first()).toHaveValue(before)

  await page.getByRole('button', { name: 'Compare' }).first().click()
  await field(page).first().focus()
  await page.keyboard.press('l')
  await expect(field(page).first()).toHaveValue('21.98')

  void wire
})

test('the cap is what can go, and the row says the runs disagree with it', async ({ page }) => {
  await open(page, { worklist: SPAN })

  /* `pipeline/join.py:add_to_quantity` spends `live_cap - copies_out` per RUN against a cap
     that is GLOBAL, so two runs joined before either emitted each spend the same room. D59
     fixed this one register down — per BOX inside one join — and it survived per RUN across
     joins that never saw each other. Measured on the owner's store: five SKUs' claims sum past
     four, and two reached `pushed: 6` in `inventory/inventory.json`.

     CENTRALISING THE ANSWERS DID NOT TOUCH THIS. The cap is arithmetic over positions, not an
     answer, so it is the one thing from D86's first build that survived the amendment whole.

     THE QTY CELL DRAWS WHAT CAN ACTUALLY GO. Drawing the sum would put a 4 in the column of a
     card three of which may be listed — D59's own named-rather-than-counted rule, which exists
     because a count under a false sentence is worse than no count.

     THE CELL IS A FIELD SINCE 2026-09-11 (D7 amended), so the figure that goes is its
     PLACEHOLDER — what a blank field sends — and "of 3" stands beside it. The number asserted
     is the same one: what can go, never what the runs claim. */
  const qty = page.locator('.pricing-row').nth(0).locator('.pricing-qty')
  await expect(qty.locator('.pricing-qty-input')).toHaveAttribute('placeholder', '3')
  await expect(qty).toContainText('of 3')
  await expect(page.locator('.pricing-row').nth(0).locator('.pricing-span-cap')).toHaveText(
    'Runs claim 4 · 3 can go',
  )
})

test('a send of several runs offers one file, and a send of one offers the per-run emit', async ({
  page,
}) => {
  await open(page, { worklist: SPAN })

  /* ONE PRESS FOR THE SEND, because the CAP has to be re-derived across it: pressing the
     per-run button twice IS the over-push above. Measured from an identical cleared ledger,
     three separate emits over three real runs wrote two SKUs past the cap of four and one
     merged emit wrote none. */
  await expect(page.getByRole('button', { name: 'Write one import file' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Ship this run' })).toHaveCount(0)

  /* AND THE CHECKBOX THE OWNER ASKED FOR, defaulting to everything: "i can hit a checkmark to
     export just the valuable cards ... otherwise it defaults to all". */
  const only = page.getByRole('checkbox', { name: /above the cut-off/ })
  await expect(only).toBeVisible()
  await expect(only).not.toBeChecked()
})

/* ================================================ the cap, asked for per send (2026-09-07, D7)
 *
 * D7'S STANDING CAP OF FOUR IS RETIRED, on the operator's answer that neither reason for it —
 * an envelope-buster order, a spike selling stale-priced copies — still describes a risk they
 * carry. So the ordinary press sends every copy the run holds that TCGplayer does not already
 * have, and a bound is something ONE SEND asks for.
 *
 * THE TWO CASES BELOW ARE THE INSTRUMENT FOR "allow me to cap as needed", and each is about the
 * SHAPE of the body rather than about the arithmetic — `harness/tests/t3_join_coverage.py`
 * owns the arithmetic on both sides of the bound. What a screen can get wrong here is sending
 * a cap nobody asked for, or dropping one somebody did.
 *
 * A blank field must OMIT the key rather than send a zero or a null. `pipeline_routes.py`
 * refuses `cap: 0` by name — *"A cap of 0 would send nothing"* — so a screen that spelled "no
 * cap" as a number would turn the ordinary press into a refusal. */

test('a blank cap sends no cap at all, and the key is absent rather than empty', async ({
  page,
}) => {
  const wire = await open(page, { worklist: SPAN })

  await page.getByRole('button', { name: 'Write one import file' }).click()
  await expect.poll(() => wire.filter((r) => r.path === '/pipeline/emit').length).toBe(1)

  const body = wire.find((r) => r.path === '/pipeline/emit')?.body as Record<string, unknown>
  /* `in`, NOT a value comparison. `cap: undefined` disappears through `JSON.stringify` and
     would read as absent to any assertion on the value, so the only test that can tell a
     dropped key from a sent one is whether the key is there at all. */
  expect('cap' in body).toBe(false)
  expect(body.listed_only).toBe(false)

  /* AND THE BAR SAYS SO, which is the half a body assertion cannot reach. The sentence about
     spending a cap once across the send is a claim about a figure, and with none asked for it
     would be describing a bound the press does not apply. */
  await expect(page.locator('.pricing-ship-says')).toContainText('every copy TCGplayer does not')
})

test('a figure typed into the cap rides the send, and the bar names what it now does', async ({
  page,
}) => {
  const wire = await open(page, { worklist: SPAN })

  await page.getByLabel('Copies to keep live at TCGplayer').fill('2')
  /* THE SENTENCE FOLLOWS THE FIELD, before anything is pressed — the operator learns what the
     figure MEANS at the moment they type it rather than from a receipt afterwards. */
  await expect(page.locator('.pricing-ship-says')).toContainText('spent once across the send')

  await page.getByRole('button', { name: 'Write one import file' }).click()
  await expect.poll(() => wire.filter((r) => r.path === '/pipeline/emit').length).toBe(1)
  expect((wire.find((r) => r.path === '/pipeline/emit')?.body as Record<string, unknown>).cap).toBe(2)
})

test('a send of ONE carries the cap too, which is the asymmetry the route refuses', async ({
  page,
}) => {
  /* THE PER-RUN STEP'S OWN COMMENT IS THE ARGUMENT: *"a screen that could ask for a split on a
     send of three and not on a send of one would be answering a question about how many runs
     are open."* A cap is that same kind of answer, so `POST /pipeline/runs/<n>/emit` takes it
     through the same parser and one `capField` is rendered in both bars. This case is what
     stops the two drifting — the merged one above could go on passing while this one silently
     sent no cap at all. */
  const wire = await open(page, { skus: [sku()] })
  await expect(page.getByRole('region', { name: 'Ship this run' })).toHaveCount(1)

  await page.getByLabel('Copies to keep live at TCGplayer').fill('3')
  await page.getByRole('button', { name: 'Write the import file' }).click()

  const emits = () => wire.filter((r) => r.method === 'POST' && r.path.endsWith('/emit'))
  await expect.poll(() => emits().length).toBe(1)
  expect((emits()[0]?.body as Record<string, unknown>).cap).toBe(3)
})

test('typing in the cap does not reach the row keys, which own bare letters here', async ({
  page,
}) => {
  /* THE SCREEN TAKES UNMODIFIED LETTERS ON A ROW — `D` snap, `H` hold, `T` history, `P` photo,
     `U` undo — so a second text field on it is a place those could fire. The price field
     earned that check by having its alphabet closed to `[0-9.]` (D49); this one is closed to
     digits, and what needs asserting is that the SHELL yields while it has focus rather than
     that the regex works, which the case above covers. A hold fired from a keystroke meant for
     the cap would write an answer the operator never gave. */
  const wire = await open(page, { worklist: SPAN })

  const cap = page.getByLabel('Copies to keep live at TCGplayer')
  await cap.focus()
  await page.keyboard.type('h4u')
  await expect(cap).toHaveValue('4')
  /* NOTHING WAS WRITTEN. `H` on a row opens the hold editor and `U` undoes an answer; either
     firing from here is a write the operator did not make, and both would be invisible in the
     field's own value. */
  expect(wire.filter((r) => r.method === 'PUT')).toEqual([])
})

test('the cap field takes digits and nothing else, so a send cannot carry a word', async ({
  page,
}) => {
  await open(page, { worklist: SPAN })

  /* THE FIELD'S ALPHABET IS CLOSED, the price field's own rule (D49) applied to the one other
     number this screen composes into a request. It reaches a child process's argv — the route
     integer-checks it for exactly that reason — and a control that accepted `2; rm` would be
     leaning on the far side of the wire to be the only reader. */
  const cap = page.getByLabel('Copies to keep live at TCGplayer')
  await cap.fill('2')
  await cap.pressSequentially('x9')
  await expect(cap).toHaveValue('29')
})

test('the standing policy is on the multi-run landing, and one press writes it once', async ({
  page,
}) => {
  /* THE CONTROL WAS GATED ON "EXACTLY ONE RUN LOADED", which is where it sat from D54 until
     2026-09-02 — and the screen OPENS on every open run, so the press that changes the store's
     policy was hidden on the landing it opens on. It is the store's answer (D86) and it draws
     wherever a sub-threshold row is on screen. */
  const wire = await open(page, {
    worklist: {
      ...SPAN,
      skus: [
        SPAN.skus[0] as (typeof SPAN.skus)[number],
        {
          ...sku({ sku: '8608459', name: 'Dunsparce', bucket: 'sub_threshold' }),
          in: [{ run: '2026-09-01-box4-01', add_to_quantity: 3 }],
          claimed_add: 3,
          over_cap: false,
        },
      ],
    },
  })

  /* THE MERGED BAR'S OWN `.pricing-ready` IS A MECHANISM SENTENCE, NEVER A READINESS
     RESTATEMENT (Ruling A corrects a comment that was wrong about this even before the
     change): it says what the merge dedupes or what the cap does, never ready/not-ready —
     that account lives once on the headline's `.pricing-verdict`, computed over the same
     union of every run on screen regardless of which bar is showing. */
  const region = page.getByRole('region', { name: 'Ship these runs' })
  await expect(region.locator('.pricing-ready')).toBeVisible()
  await expect(page.locator('.pricing-verdict')).toBeVisible()

  /* THE CONTROL IS THE CUT-OFF FIELD, AND THE FLOOR PRESS IT REPLACED IS RETIRED (D98). Main
     asserted a segmented row here offering "a flat price" or "the $0.40 floor"; the owner had
     the row deleted and the figure itself made the control, so stating the floor is typing the
     floor's own number. What the case is FOR is unchanged and is the reason it survived the
     rewrite: the store's policy must be reachable on the landing the screen opens on, which is
     every open run and not a single picked one. */
  const cut = page.getByLabel("Store default")
  await expect(cut).toBeVisible()
  await cut.fill('0.40')
  await cut.press('Enter')

  /* ONE PUT, TO THE CORPUS, however many runs hold a sub-threshold card — the same property
     the answer case above asserts for a price. */
  await expect.poll(() => wire.filter((r) => r.method === 'PUT').length).toBe(1)
  expect(wire.filter((r) => r.method === 'PUT').map((r) => r.path)).toEqual(['/pricing'])
  expect(sentPolicy(wire).sub_threshold).toEqual({ flat: '0.40' })
  expect(sentPolicy(wire).threshold).toBe('0.40')
})

test('the per-run emit is what a send of one offers, so the pair is not one press hiding', async ({
  page,
}) => {
  /* THE OTHER HALF, AS ITS OWN CASE. Calling `open` twice in one test re-registers every route
     on the same page and the two fixtures then race; the pair only means anything if both
     halves actually run. */
  await open(page, { skus: [sku()] })
  await expect(page.getByRole('region', { name: 'Ship this run' })).toHaveCount(1)
  await expect(page.getByRole('button', { name: 'Write one import file' })).toHaveCount(0)
})

test('an undo returns the card to what it was, including to having no answer', async ({
  page,
}) => {
  const wire = await open(page, { worklist: SPAN })

  await field(page).first().focus()
  await page.keyboard.type('12.00')
  await page.keyboard.press('Enter')
  await expect.poll(() => sentAnswers(wire)['9191210']).toBe('12.00')

  /* `u` ON THE ROW, which is this screen's own undo — the price field's alphabet is closed to
     `[0-9.]` precisely so a letter can be a command (D49), and that closure is the whole safety
     argument for it.

     THE ROW HAD NO ANSWER BEFORE, so undoing must DELETE the key and return it to its
     suggestion rather than writing the suggestion in. That is the one write this screen may
     never make: an override is layer 1 of the ladder and beats the rule at layer 4, so a
     screen that wrote its suggestions would produce a run where changing the preset silently
     changed nothing. */
  await field(page).first().focus()
  await page.keyboard.press('u')
  await expect.poll(() => sentAnswers(wire)).toEqual({})
})

/* ============================================================ the cut-off (2026-09-03, D99)
 *
 * THE THRESHOLD AND THE CHEAP-CARD PRICE ARE ONE FIGURE, on the owner's ruling: *"I told you
 * that threshold and cheap card are the same variable and should be the same."* Held apart they
 * invert — at a threshold of $0.40 beside a cheap answer of $0.49, a card worth $0.38 lists at
 * $0.49 and a card worth $0.42 lists at $0.42, so the card that FAILED the bar goes out dearer
 * than the one that cleared it, everywhere in the 9-cent window where bulk actually lives.
 *
 * Three properties are worth a test each, and none of them can be got from the cases above. */

test('typing a cut-off moves rows across the sections, at the figure emit will use', async ({
  page,
}) => {
  await open(page, {
    /* Three cards either side of a $0.40 line: two under it, one over. Nothing is written, so
       the screen must partition at the figure the SERVER reports — `pipeline/corpus.py` defaults
       `policy.threshold` to `pricing.THRESHOLD`, so an unwritten store emits at $0.40 and a
       screen offering a prettier default of its own would draw a split nothing would write. */
    skus: [
      sku({ sku: '1', bucket: 'sub_threshold', snap: { market: '0.12', direct_low: null, low: '0.10', low_with_shipping: '1.10', now: null } }),
      sku({ sku: '2', bucket: 'sub_threshold', snap: { market: '0.37', direct_low: null, low: '0.30', low_with_shipping: '1.30', now: null } }),
      sku({ sku: '3', bucket: 'listable', snap: { market: '0.41', direct_low: null, low: '0.38', low_with_shipping: '1.38', now: null } }),
    ],
  })

  const cut = page.getByLabel("Store default")
  await expect(cut).toHaveValue('0.40')
  await expect(page.locator('.pricing-cheap-count')).toContainText('2 under · 1 above')

  /* RAISING THE LINE MOVES A ROW, WITHOUT A RELOAD. `GET /pipeline/pricing` reports a `bucket`
     frozen into `pricing.json` by the join that wrote it; `emit` does not read that cell — it
     re-runs the partition at the STORED figure — so a screen that drew the payload's bucket
     would show a card in the listed half that the file puts in the cheap one. Measured on the
     owner's box 6: the payload still said 3 listable and 8 sub-threshold after the cut-off moved
     to $1.25, while the truth was 1 and 10. */
  await cut.fill('0.45')
  await cut.press('Enter')
  await expect(page.locator('.pricing-cheap-count')).toContainText('3 under · 0 above')
  await expect(page.locator('.pricing-section[data-bucket="listable"]')).toHaveCount(0)
  await expect(page.locator('.pricing-section[data-bucket="sub_threshold"] .pricing-section-count')).toContainText('3')

  /* AND LOWERING IT PUTS THEM BACK. Idempotent both ways: the partition is a function of the
     figure and the Market cell, never of the order the figures were typed in. */
  await cut.fill('0.20')
  await cut.press('Enter')
  await expect(page.locator('.pricing-cheap-count')).toContainText('1 under · 2 above')
})

test('the cut-off panel is drawn even when nothing is under the line', async ({ page }) => {
  await open(page, {
    skus: [
      sku({ sku: '1', bucket: 'listable', snap: { market: '9.00', direct_low: null, low: '8.00', low_with_shipping: '9.00', now: null } }),
    ],
  })

  /* IT WAS CONDITIONAL ON THERE BEING CHEAP CARDS, which was right while the figure was only an
     answer ABOUT those cards. Now that the figure IS the line, a cut-off typed low enough to
     empty the lower section would take its own control off the screen with it, and there would
     be no way back to the number that had just been moved. */
  await expect(page.locator('.pricing-cheap')).toBeVisible()
  await expect(page.getByLabel("Store default")).toBeVisible()
  await expect(page.locator('.pricing-cheap-count')).toContainText('0 under · 1 above')
})

test('a store still holding two figures says so, and one press makes them agree', async ({
  page,
}) => {
  const wire = await open(page, {
    /* THE OWNER'S OWN STORE, AS FOUND ON 2026-09-03: a threshold of $0.40 beside a cheap-card
       answer of $0.24, both written under the old two-figure model. Neither is wrong, and the
       screen may not pick between them silently — drawing the cut-off alone would claim these
       cards go out at $0.40 while `emit` would write $0.24, which is the screen lying about
       money. */
    skus: [
      sku({ sku: '1', bucket: 'sub_threshold', snap: { market: '0.12', direct_low: null, low: '0.10', low_with_shipping: '1.10', now: null } }),
    ],
    decisions: { rule: 'match', basis: 'market', threshold: '0.40', sub_threshold: { flat: '0.24' }, overrides: {} },
  })

  const stranded = page.locator('.pricing-cheap-stranded')
  await expect(stranded).toBeVisible()
  await expect(stranded).toContainText('$0.24')

  /* ONE PRESS RESOLVES IT, AND IT WRITES BOTH KEYS. Which of the two figures the operator meant
     is not a thing this screen can know, so it offers the cut-off and states what that does
     rather than choosing on their behalf. */
  await page.getByRole('button', { name: /Make them both/ }).click()
  await expect.poll(() => wire.filter((r) => r.method === 'PUT').length).toBeGreaterThan(0)
  expect(sentPolicy(wire).threshold).toBe('0.40')
  expect(sentPolicy(wire).sub_threshold).toEqual({ flat: '0.40' })
  await expect(stranded).toHaveCount(0)
})

/* ---------------------------------------------------------------- the stale-write guard
 *
 * `PUT /pricing` REPLACES THE DOCUMENT WHOLESALE, and this screen autosaves from a snapshot it
 * took at mount. A second writer — another tab, an edit on disk, `pkmnscan prices adopt --write`
 * — was therefore silently reverted on the operator's next keystroke, with no error anywhere, on
 * the one file in this product that holds money. Found on `claude/great-nightingale-37cf84`,
 * whose markdown sweep made it acute: a stale PUT would undo a re-price of every stale SKU.
 *
 * THE REVISION TRAVELS BESIDE THE DOCUMENT AND NEVER INSIDE IT. Inside, it would land in the
 * object this screen dirty-checks by identity, and every write that landed would re-dirty the
 * screen — unsaved -> saving -> unsaved, forever. */

test('the write carries the revision it read, and the refusal offers the way back', async ({
  page,
}) => {
  const wire = await open(page)

  await field(page).fill('19.99')
  await field(page).press('Enter')
  await expect.poll(() => wire.filter((r) => r.method === 'PUT').length).toBe(1)

  /* WHAT THE SCREEN READ, SENT BACK. Absent would mean "did not read one", which the route
     deliberately allows for a terminal user editing the file by hand — so an absent field here
     would be a screen quietly opting out of the guard. */
  const put = wire.filter((r) => r.method === 'PUT').pop()
  expect((put?.body as { revision?: string }).revision).toBe('rev-1')
})

test('a corpus that moved under the screen refuses the write rather than reverting it', async ({
  page,
}) => {
  const wire = await open(page)
  /* The file moved between this screen's read and its write — another tab saved, or a command
     did. The route compares and refuses; nothing is written. */
  await page.route(/\/pricing$/, async (route) => {
    if (route.request().method() !== 'PUT') return route.fallback()
    wire.push({ method: 'PUT', path: '/pricing', body: route.request().postDataJSON() })
    await route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({
        error: {
          code: 'corpus_moved',
          message: 'The pricing file changed since this screen read it — another tab, or an edit on disk.',
        },
      }),
    })
  })

  await field(page).fill('19.99')
  await field(page).press('Enter')

  const notice = page.locator('.pricing-notice')
  await expect(notice).toContainText('changed since this screen read it')
  await expect(notice).toContainText('corpus_moved')

  /* AND A CONFLICT IS THE ONE REFUSAL ON THIS SCREEN WITH SOMEWHERE TO GO. The button says what
     it costs rather than presenting a re-read as free: whatever is typed and unsaved goes. */
  await expect(
    notice.getByRole('button', { name: /Re-read the pricing file, losing what is unsaved/ }),
  ).toBeVisible()
})

test('the run door draws the estimate, and says what it was read at', async ({ page }) => {
  /* THE RUN DOOR'S `LiveCount` HAD NO DOM ASSERTION AT ALL until D115 — `grep pricing-live
     app/tests` found one hit, in the markdown spec. That is how the regression this closes
     would have shipped silently: `cli/cmd_join.py` freezes the listing record into
     `pricing.json`, and freezing the READING alone would have this screen over-report by
     precisely the copies sold since — on the screen where money is decided. */
  await open(page, {
    skus: [sku({ listing: { pushed: 0, staged: 0, live: 4, sold_here: 2 } })],
  })
  const live = page.locator('.pricing-row .pricing-live').first()
  await expect(live).toContainText('2 live')
  await expect(live).toContainText('4 when read, 2 sold since')
})

test('a row with nothing sold since draws exactly what it drew before', async ({ page }) => {
  /* THE REGRESSION GUARD, and the reason the split is conditional: on the owner's store 440 of
     443 SKUs have an empty counter, so a row that moved here would make the change visible
     everywhere and legible nowhere. */
  await open(page, {
    skus: [sku({ listing: { pushed: 0, staged: 0, live: 4, sold_here: 0 } })],
  })
  const live = page.locator('.pricing-row .pricing-live').first()
  await expect(live).toContainText('4 live')
  await expect(live).not.toContainText('when read')
})

test('a listing frozen before the counter existed draws the reading, not NaN', async ({ page }) => {
  /* THE FIELD IS ABSENT, NOT ZERO, AND THAT IS THE WHOLE CASE (D115, amended). `listing` is a
     record `cli/cmd_join.py` froze into `pricing.json`, and D115 is newer than every stored
     run on the owner's store: measured 2026-09-09, **all 171** non-null listings across the
     eight run directories carry no `sold_here` at all. `GET .../pricing` serves the file
     through, so the client was handed `undefined`, `Math.max(0, undefined)` gave `NaN`, and
     the Smite row of `runs/2026-09-02-box6-01` drew `NaN live · read 8 days ago` on the screen
     where money is decided.

     THE OMISSION IS SPELT WITH NO KEY RATHER THAN `sold_here: undefined`, because those are
     different bytes on the wire and only one of them is what a stored file sends. The two
     cases above both SUPPLY the key and would both stay green through the defect — which is
     exactly why neither caught it.

     `NaN` IS ASSERTED AGAINST BY NAME as well as the figure being right. A row that regressed
     to some other wrong number would fail the first assertion; a row that regressed to the
     original defect fails both, and says which in its message. */
  await open(page, {
    skus: [sku({ sku: '9191230', name: 'Smite', listing: { pushed: 1, staged: 0, live: 1 } })],
  })
  const live = page.locator('.pricing-row .pricing-live').first()
  await expect(live).toContainText('1 live')
  await expect(live).not.toContainText('NaN')
  /* AND NO "SOLD SINCE" CLAUSE. An absent counter is not a counter reading zero-point-something
     — the row must draw byte-identically to the one above it, which is the pre-D115 rendering
     and correct as of the join. */
  await expect(live).not.toContainText('when read')
})

/* ======================================= a number on the card's row (2026-09-11, D7 amended)
 *
 * THE OWNER'S REPORT: *"I can no longer select quantities to sell at all"*. The cap above holds
 * every card to N live at TCGplayer and cannot say "two of THIS card"; asked which control they
 * meant, the owner ruled for a number on each row, meaning COPIES TO SEND IN THIS FILE. The Qty
 * cell is that field: blank sends every copy that can go (the placeholder is that figure), a
 * number sends that many, 0 sends none without holding the card.
 *
 * AS WITH THE CAP, THESE CASES ARE ABOUT THE SHAPE OF THE BODY AND THE SCREEN'S ACCOUNT OF IT —
 * `harness/tests/t7_store_and_seams.py:check_emit_send_quantity` owns the file and the store.
 * What a screen can get wrong here is sending a figure nobody typed, dropping one somebody did,
 * keying it by the wrong card, or letting it survive the press it was typed for. */

const LEBLANC_QTY = 'How many of the 3 copies of LeBlanc, Everywhere At Once go in this file'
const DUNSPARCE_QTY = 'How many of the 3 copies of Dunsparce go in this file'

test('a figure typed on a row rides the send keyed by that SKU, the deck counts it, and the write spends it', async ({
  page,
}) => {
  const wire = await open(page, { worklist: SPAN })
  const field = page.getByLabel(LEBLANC_QTY)
  await expect(field).toHaveAttribute('placeholder', '3')
  const before = (await page.locator('.pricing-verdict-out').innerText()).match(/(\d+) cop/)
  const copiesBefore = Number(before?.[1])
  expect(Number.isFinite(copiesBefore)).toBe(true)

  await field.fill('2')
  /* THE DECK FOLLOWS THE FIELD, before anything is pressed: one fewer copy would go, and the
     sentence says a card is at a figure typed by hand — which is the account the operator reads
     before deciding to press. */
  await expect(page.locator('.pricing-verdict-out')).toContainText(`${copiesBefore - 1} cop`)
  await expect(page.locator('.pricing-verdict-byhand')).toContainText('1 card at a quantity you typed')
  await expect(page.locator('.pricing-ship-byhand')).toContainText('1 by hand')

  await page.getByRole('button', { name: 'Write one import file' }).click()
  await expect.poll(() => wire.filter((r) => r.path === '/pipeline/emit').length).toBe(1)
  const body = wire.find((r) => r.path === '/pipeline/emit')?.body as Record<string, unknown>
  expect(body.quantities).toEqual({ '9191210': 2 })

  /* SPENT BY THE WRITE. A figure that survived the press would send the same copies again on
     the next one, on top of what went. */
  await expect(field).toHaveValue('')
  await expect(page.locator('.pricing-ship-byhand')).toHaveCount(0)
})

test('a blank Qty on every row sends no quantities key at all', async ({ page }) => {
  const wire = await open(page, { worklist: SPAN })
  await page.getByRole('button', { name: 'Write one import file' }).click()
  await expect.poll(() => wire.filter((r) => r.path === '/pipeline/emit').length).toBe(1)
  const body = wire.find((r) => r.path === '/pipeline/emit')?.body as Record<string, unknown>
  /* `in`, for the reason the cap's own case gives: a dropped key and a sent-empty key read the
     same to a value assertion, and only the first is the ordinary press. */
  expect('quantities' in body).toBe(false)
})

test('a figure past what can go is clamped on the way out, 0 takes the row out of the count, Escape clears one row and the chip clears every row', async ({
  page,
}) => {
  await open(page, { worklist: SPAN })
  const leblanc = page.getByLabel(LEBLANC_QTY)
  const dunsparce = page.getByLabel(DUNSPARCE_QTY)
  const outBefore = (await page.locator('.pricing-verdict-out').innerText()).match(/(\d+) rows?/)
  const rowsBefore = Number(outBefore?.[1])

  /* CLAMPED, NOT REFUSED: the server would name "asked 9, only 3 can go"; the screen does not
     draw a send that cannot happen. */
  await leblanc.fill('9')
  await leblanc.press('Tab')
  await expect(leblanc).toHaveValue('3')

  /* ZERO IS A REAL ANSWER and the row leaves the count of rows that would go, without a hold. */
  await leblanc.fill('0')
  await expect(page.locator('.pricing-verdict-out')).toContainText(`${rowsBefore - 1} row`)
  await expect(page.locator('.pricing-verdict-byhand')).toContainText('1 card')

  /* ESCAPE PUTS ONE ROW BACK, the way it puts a price field back. */
  await leblanc.focus()
  await leblanc.press('Escape')
  await expect(leblanc).toHaveValue('')
  await expect(page.locator('.pricing-ship-byhand')).toHaveCount(0)
  await expect(page.locator('.pricing-verdict-out')).toContainText(`${rowsBefore} row`)

  /* THE CHIP IS THE WAY BACK FOR THE WHOLE SEND. */
  await leblanc.fill('1')
  await dunsparce.fill('2')
  await expect(page.locator('.pricing-ship-byhand')).toContainText('2 by hand')
  await page.locator('.pricing-ship-byhand').click()
  await expect(leblanc).toHaveValue('')
  await expect(dunsparce).toHaveValue('')
  await expect(page.locator('.pricing-ship-byhand')).toHaveCount(0)
})

test('typing in a Qty field does not reach the row keys either', async ({ page }) => {
  const wire = await open(page, { worklist: SPAN })
  const field = page.getByLabel(LEBLANC_QTY)
  await field.focus()
  /* `h` opens a hold on the focused row and `t` pulls a price history — from the price field.
     A Qty field is a text field like the cap's and yields nothing to them: no hold panel
     opens, and no history is fetched. The field's alphabet is digits, so the letters land
     nowhere at all. */
  await page.keyboard.type('h2t')
  await expect(field).toHaveValue('2')
  await expect(page.locator('.pricing-holdpanel')).toHaveCount(0)
  expect(wire.filter((r) => r.path.includes('/history')).length).toBe(0)
})


/* ============================================================================================
   THE MASS-CLEAR (D168)

   THE PRESS ITSELF IS THE LEAST INTERESTING THING HERE. `harness/tests/t7_store_and_seams.py:
   check_pricing_clear` executes the route: what may go, what may not, the restore's
   provenance and the stale-write refusal, all against real Python. These cases are about the
   SCREEN, and specifically about the two properties a stub cannot fake — that the figure in
   the label is the figure that will go, and that the scope the operator chose is the scope
   that travels. A fulfilled 200 is green whether or not the button said the right number.
   ============================================================================================ */

/** Four typed answers the server calls clearable, aged the way the owner's store is: two five
 *  days old, one today, one carrying no date at all. Plus a hold and an unpriced row it does
 *  NOT call clearable — which is the half the screen must never invent for itself. */
const CLEARABLE = {
  days: { '8608859': 5, '8608459': 5, '9191210': 0, '9038187': null as number | null },
  holds: 2,
  unknown: 1,
}

/** FOUR DISTINCT CARDS, because the price field is labelled by NAME and four rows sharing one
 *  would make `Price for Articuno` four elements. */
const CLEAR_ROWS = [
  sku({ sku: '8608859', name: 'Articuno' }),
  sku({ sku: '8608459', name: 'Dunsparce' }),
  sku({ sku: '9191210', name: 'LeBlanc' }),
  sku({ sku: '9038187', name: 'Deathgrip' }),
]

test('the clear control is absent on a server that does not offer it', async ({ page }) => {
  /* NOT DISABLED AND NOT OFFERED OVER A GUESS. A capture server that predates the route
     answers no `clearable` block, and the screen has no way to know which of its answers are
     holds — so the control is dead rather than drawn over an assumption about money. */
  await open(page, { skus: CLEAR_ROWS })
  await expect(page.getByRole('button', { name: 'Clear typed prices in bulk' })).toBeDisabled()
})

test('the sheet leads with the worklist, and the label carries the figure', async ({ page }) => {
  await open(page, { skus: CLEAR_ROWS, clearable: CLEARABLE })
  await page.getByRole('button', { name: 'Clear typed prices in bulk' }).click()

  const sheet = page.locator('.clearprices')
  await expect(sheet).toBeVisible()

  /* THE NARROW SCOPE IS SELECTED. The corpus is one file for the whole store (D86), so
     "everywhere" is the shape this act naturally has and is exactly why it may not be what a
     press lands on by default. */
  await expect(sheet.getByRole('button', { name: /On this worklist/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  /* AND THE FIGURE IS IN THE BUTTON, NOT IN A TOOLTIP. Four clearable answers, all four on
     this worklist, no window — the button says four. */
  await expect(sheet.locator('.clearprices-foot .bn-btn-danger-solid')).toContainText(
    'Clear 4 typed prices',
  )
})

test('what the clear leaves alone is on the screen, not in a tooltip', async ({ page }) => {
  await open(page, { skus: CLEAR_ROWS, clearable: CLEARABLE })
  await page.getByRole('button', { name: 'Clear typed prices in bulk' }).click()

  /* THE HOLDS AND THE UNPRICED ROWS ARE NAMED BY COUNT. An operator asking "does this touch my
     holds" has to be able to answer it without pressing anything — D49's holds carry a reason
     and a watch, and removing one puts the card back into the next emit. */
  const spares = page.locator('.clearprices-spares')
  await expect(spares).toContainText('2')
  await expect(spares).toContainText('held back on purpose')
  await expect(spares).toContainText('no catalogue price')
})

test('an age window narrows the label, and never takes an undated answer', async ({ page }) => {
  await open(page, { skus: CLEAR_ROWS, clearable: CLEARABLE })
  await page.getByRole('button', { name: 'Clear typed prices in bulk' }).click()
  const sheet = page.locator('.clearprices')
  const press = sheet.locator('.clearprices-foot .bn-btn-danger-solid')

  /* EVERY WINDOW DRAWS ITS OWN COUNT BEFORE THE PRESS, which is D103's finding: a window can
     select nothing for a reason that is about the store's age rather than about the answers,
     and the remedy is that the zero is visible rather than discovered by pressing. */
  const anyAge = sheet.locator('.clearprices-age', { hasText: 'Any age' })
  await expect(anyAge.locator('.clearprices-age-count')).toHaveText('4')

  const threeDays = sheet.locator('.clearprices-age', { hasText: '3+ days' })
  /* TWO, NOT THREE: the two aged five days. The one answered today is out of the window and
     THE UNDATED ONE IS LEFT ALONE — an age filter cannot place an answer with no date, and
     guessing that it must be old is the direction that deletes money. */
  await expect(threeDays.locator('.clearprices-age-count')).toHaveText('2')
  await threeDays.click()
  await expect(press).toContainText('Clear 2 typed prices')

  /* AND THE SHEET SAYS WHY THE FOURTH IS MISSING. */
  await expect(page.locator('.clearprices-spares')).toContainText('carry no date')

  /* A WINDOW THAT SELECTS NOTHING SAYS SO AND REFUSES THE PRESS, rather than offering a
     button that does nothing. */
  await sheet.locator('.clearprices-age', { hasText: '14+ days' }).click()
  await expect(press).toContainText('Nothing to clear')
  await expect(press).toBeDisabled()
})

test('the scope the operator chose is the scope that travels', async ({ page }) => {
  const wire = await open(page, { skus: CLEAR_ROWS, clearable: CLEARABLE })
  await page.getByRole('button', { name: 'Clear typed prices in bulk' }).click()
  const sheet = page.locator('.clearprices')

  /* THE WORKLIST SCOPE SENDS SKUS. This is the assertion the whole sheet exists for: the
     press an operator makes while looking at one run's rows must not reach the rest of the
     store, and the only thing that makes that true on the wire is this list. */
  await sheet.locator('.clearprices-foot .bn-btn-danger-solid').click()
  const scoped = wire.filter((r) => r.path === '/pricing/clear').at(-1)
  expect(scoped?.body).toBeTruthy()
  expect((scoped?.body as { skus?: string[] }).skus?.sort()).toEqual(
    ['8608459', '8608859', '9038187', '9191210'],
  )
  /* AND NO WINDOW, because none was chosen — absent means every age, and a default here would
     be the expiry rule the owner refused wearing a different hat. */
  expect((scoped?.body as { older_than_days?: number }).older_than_days).toBeUndefined()
  /* AND THE REVISION IT READ, so a file that moved underneath refuses instead of destroying a
     write nobody saw happen (D86's guard). */
  expect((scoped?.body as { revision?: string }).revision).toBe('rev-1')
})

test('the store-wide scope sends no SKUs, and says so in the label', async ({ page }) => {
  const wire = await open(page, { skus: CLEAR_ROWS, clearable: CLEARABLE })
  await page.getByRole('button', { name: 'Clear typed prices in bulk' }).click()
  const sheet = page.locator('.clearprices')

  await sheet.getByRole('button', { name: /Everywhere/ }).click()
  /* THE BLAST RADIUS IS IN THE LABEL AND IN A SENTENCE BESIDE IT. "Clear" over four hundred
     answers is the ambush this sheet exists to prevent. */
  await expect(sheet.locator('.clearprices-foot .bn-btn-danger-solid')).toContainText(
    'everywhere',
  )
  await expect(sheet.locator('.clearprices-scope-says')).toContainText('Every run at once')

  await sheet.locator('.clearprices-foot .bn-btn-danger-solid').click()
  const all = wire.filter((r) => r.path === '/pricing/clear').at(-1)
  /* ABSENT AND NOT AN EMPTY LIST. An empty `skus` is a real scope that clears nothing; the
     whole store is the absence of a narrowing. */
  expect((all?.body as { skus?: string[] }).skus).toBeUndefined()
})

test('a clear empties the fields it cleared, and offers the way back', async ({ page }) => {
  const TYPED = { value: '4.50', at: '2026-09-07T06:50:31.891+00:00' }
  const wire = await open(page, {
    skus: CLEAR_ROWS,
    clearable: CLEARABLE,
    decisions: { rule: 'match', basis: 'market', overrides: { '8608859': '4.50' } },
  })
  const field = page.getByLabel('Price for Articuno')
  await expect(field).toHaveValue('4.50')

  /* A CORPUS THAT ACTUALLY MOVES, because the screen RE-READS after both presses — `clearable`
     is the server's answer to which answers may go, and a fixture that kept serving the cleared
     SKU would have the sheet offering to remove an answer that is gone.

     ALL THREE ARE REGISTERED BEFORE ANY PRESS. A stub swapped in after `click()` loses to the
     press's own re-read, and the assertion then retries a STABLE wrong answer — the race
     DEBT23 records. These mutate one object in place instead. */
  const live: Record<string, unknown> = { '8608859': { ...TYPED } }
  await page.route(/\/pricing$/, async (route) => {
    if (route.request().method() === 'PUT') return route.fallback()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        corpus: { version: 1, policy: { rule: 'match', basis: 'market' }, skus: { ...live } },
        path: '/tmp/prices.json',
        revision: 'rev-live',
        clearable: { days: Object.fromEntries(Object.keys(live).map((k) => [k, 5])), holds: 2, unknown: 1 },
      }),
    })
  })
  await page.route(/\/pricing\/clear$/, async (route) => {
    wire.push({ method: 'POST', path: '/pricing/clear', body: route.request().postDataJSON() })
    const cleared = { '8608859': { ...TYPED } }
    delete live['8608859']
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true, cleared, count: 1, holds: 2, unknown: 1, undated: 0, answers: 3,
        revision: 'rev-cleared',
      }),
    })
  })
  await page.route(/\/pricing\/restore$/, async (route) => {
    const body = route.request().postDataJSON() as { answers: Record<string, unknown> }
    wire.push({ method: 'POST', path: '/pricing/restore', body })
    for (const [key, value] of Object.entries(body.answers)) live[key] = value
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true, restored: Object.keys(body.answers), skipped: [], revision: 'rev-restored',
      }),
    })
  })

  await page.getByRole('button', { name: 'Clear typed prices in bulk' }).click()
  await page.locator('.clearprices-foot .bn-btn-danger-solid').click()

  /* THE FIELD GOES BACK TO THE SUGGESTION. The row is not removed and nothing else moves —
     a press changes what is on the screen, never where the rest of it is (D118). */
  await expect(field).toHaveValue('')
  await expect(page.locator('.clearprices')).toBeHidden()

  /* THE RECEIPT CARRIES THE FIGURE AND NAMES WHAT SURVIVED. */
  const toast = page.locator('.bn-toast').last()
  await expect(toast).toContainText('1 typed price cleared')
  await expect(toast).toContainText('2 held back on purpose')

  /* AND THE WAY BACK PUTS THE ANSWER ITSELF BACK — value and date — rather than asking for it
     to be re-typed. */
  await toast.getByRole('button', { name: 'Undo' }).click()
  await expect(field).toHaveValue('4.50')
  const back = wire.filter((r) => r.path === '/pricing/restore').at(-1)
  /* THE ANSWER ITSELF TRAVELS, VALUE AND DATE. A restore that sent only the SKU would make the
     undo a re-type, and one that let the server stamp a fresh date would read as a store-wide
     re-pricing on the next markdown survey (D103's ratchet).

     THE REVISION IS THE ONE THE RE-READ LEFT, not the clear's: the screen refreshed between the
     two presses, which is the whole reason `clearable` is not stale by the time the sheet can
     be opened again. */
  expect((back?.body as { answers: unknown }).answers).toEqual({
    '8608859': { value: '4.50', at: '2026-09-07T06:50:31.891+00:00' },
  })
  expect((back?.body as { revision: string }).revision).toBe('rev-live')

  /* AND THE SHEET AGREES WITH THE STORE AFTERWARDS. Reopened, it counts the restored answer
     again rather than the four it opened on. */
  await page.getByRole('button', { name: 'Clear typed prices in bulk' }).click()
  await expect(page.locator('.clearprices-foot .bn-btn-danger-solid')).toContainText(
    'Clear 1 typed price',
  )
})

test('the clear is refused while the screen has an unsaved answer', async ({ page }) => {
  /* `#/pricing` autosaves the whole document, so a clear landing under an unsaved keystroke
     would be undone by the next save — D86's two-writer defect reached from inside one tab.
     The sheet says so rather than failing quietly. */
  await open(page, { skus: CLEAR_ROWS, clearable: CLEARABLE })
  await page.route(/\/pricing$/, async (route) => {
    if (route.request().method() !== 'PUT') return route.fallback()
    /* Never answers, so the screen stays `saving` for the length of this case. */
    await new Promise(() => {})
  })
  await page.getByLabel('Price for Articuno').fill('3.21')
  await page.getByRole('button', { name: 'Clear typed prices in bulk' }).click()
  await expect(page.locator('.clearprices-foot .bn-btn-danger-solid')).toBeDisabled()
  await expect(page.locator('.clearprices')).toContainText('Save first')
})
