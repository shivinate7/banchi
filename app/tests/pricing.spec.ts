import { test, expect, type Locator, type Page } from '@playwright/test'
import { settleFonts } from './fontsReady'
import { settleMotion } from './motionSettled'
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

/** `GET /pipeline/sends` for a store that has sent nothing. */
const SENDS_NONE = { sends: [], unconfirmed: { copies: 0, stamps: [] }, due: false, check_at: null, now: '2026-09-24T12:00:00+00:00' }

/** One send receipt as `server/send_routes.py:_summary` shapes it. */
function sendSummary(over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    stamp: '20260924-120000',
    kind: 'send',
    state: 'waiting',
    at: '2026-09-24T12:00:00+00:00',
    copies: 3,
    prices: 0,
    price_check: null,
    rows: 2,
    published_at: '2026-09-24T12:00:05+00:00',
    check_after: '2026-09-24T12:15:05+00:00',
    checked_at: null,
    check: null,
    trimmed: [],
    trimmed_copies: 0,
    accepted: 2,
    turned_away: 0,
    failure: null,
    unknown: null,
    held: false,
    takeable: 0,
    take_back_after: null,
    files: ['import.csv'],
    taken_back_at: null,
    warning: null,
    prices_left: [],
    moves: [],
    ...over,
    /* THE SERVER SAYS `staged` WHENEVER `unknown.staged` DOES (`_maybe_staged`), and also for a
       press that died mid-push with no `unknown` (round 6, S2). A case names it only for that. */
    staged: over.staged ?? Boolean((over.unknown as { staged?: boolean } | null | undefined)?.staged),
  }
}

const sendPress = (page: Page) => page.getByRole('button', { name: /^Send (\d+ cop(y|ies) )?to TCGplayer$/ })
const sendPosts = (wire: Wire[]) => wire.filter((r) => r.method === 'POST' && r.path === '/pipeline/send')

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
      { box: 7, index: 1, label: 'Box 7, Section 1, Card 1' },
      { box: 7, index: 2, label: 'Box 7, Section 1, Card 2' },
      { box: 7, index: 3, label: 'Box 7, Section 1, Card 3' },
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
    /** What each run still owes, by run name, in the server's words. Absent reads as the
     *  default: nothing once emitted, and "never emitted" before. */
    owes?: Record<string, string[]>
    /** The machine code for each of those reasons, in the same order. */
    owed?: Record<string, { code: string; count: number | null }[]>
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
    /** What `POST /pipeline/send` answers, as a function of the body the card sent — the one
     *  press (`D273`). `status` other than 200 answers the server's
     *  refusal envelope with `code`. Default: a send that went live. */
    send?: (body: Record<string, unknown>) => { status: number; body?: unknown; code?: string; data?: unknown }
    /** HOLD `POST /pipeline/send` OPEN THIS LONG, so a case can measure the card WHILE the press
     *  runs (round 9, D118). */
    sendDelayMs?: number
    /** What `GET /pipeline/sends` answers, as a function of what the page has already sent (the
     *  wire so far). A function and not a queue: the page may read the status more than once on
     *  arrival, and a queue would hand the second read an answer meant for later. Default:
     *  nothing sent, nothing due. */
    sends?: (wire: Wire[]) => unknown
    /** What `POST /pipeline/live-check` answers. Default: ran, nothing to confirm. */
    liveCheck?: (body: Record<string, unknown>) => unknown
  } = {},
): Promise<Wire[]> {
  const wire: Wire[] = []

  /* THE ONE PRESS AND ITS STATUS, stubbed so no case can reach the server that would reach
     TCGplayer. Every body lands in `wire`, which is what the cases assert against. */
  await page.route(/\/pipeline\/sends$/, async (route) => {
    const next = options.sends?.(wire) ?? SENDS_NONE
    wire.push({ method: 'GET', path: '/pipeline/sends', body: null })
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(next) })
  })
  await page.route(/\/pipeline\/sends\/[^/]+\/take-back$/, async (route) => {
    wire.push({ method: 'POST', path: new URL(route.request().url()).pathname, body: route.request().postDataJSON() })
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ send: sendSummary({ kind: 'download', state: 'taken_back' }), moved: 4 }),
    })
  })
  await page.route(/\/pipeline\/sends\/[^/]+\/dismiss$/, async (route) => {
    wire.push({ method: 'POST', path: new URL(route.request().url()).pathname, body: route.request().postDataJSON() })
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ send: sendSummary({ state: 'taken_back' }) }) })
  })
  await page.route(/\/pipeline\/send$/, async (route) => {
    const body = (route.request().postDataJSON() ?? {}) as Record<string, unknown>
    wire.push({ method: 'POST', path: '/pipeline/send', body })
    if (options.sendDelayMs !== undefined) await new Promise((r) => setTimeout(r, options.sendDelayMs))
    const answer: { status: number; body?: unknown; code?: string; data?: unknown } = (
      options.send ?? (() => ({ status: 200, body: { send: sendSummary(), console: '' } }))
    )(body)
    await route.fulfill({
      status: answer.status,
      contentType: 'application/json',
      body: JSON.stringify(
        answer.status === 200
          ? answer.body
          : {
              error: {
                code: answer.code ?? 'refused',
                message: 'The server said no.',
                ...(answer.data === undefined ? {} : { data: answer.data }),
              },
            },
      ),
    })
  })
  await page.route(/\/pipeline\/live-check$/, async (route) => {
    const body = (route.request().postDataJSON() ?? {}) as Record<string, unknown>
    wire.push({ method: 'POST', path: '/pipeline/live-check', body })
    const answer = (options.liveCheck ?? (() => ({ ran: true, checked: [] })))(body)
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(answer) })
  })

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
          owes: options.owes?.[row.run] ?? (options.emitted === true ? [] : ['never emitted']),
          owed: options.owed?.[row.run] ?? (options.emitted === true ? [] : [{ code: 'never_emitted', count: null }]),
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
  /* THIS USED TO ASK `main` FOR ITS OWN ANIMATIONS, which is `main`'s slide and nothing inside
     it. `getAnimations()` on an element is not a subtree walk, so every staggered row under it
     was invisible to this wait. `motionSettled.ts` asks the DOCUMENT and excludes the looping
     ones, which is the same argument reaching the rest of the page; its header carries the
     measurement that earned it. Strictly more is waited for, so nothing that passed can start
     failing for having settled too little. */
  await settleMotion(page)
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
  await page.getByRole('button', { name: /^(Every run|\d+ runs?)$/ }).click()
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
  await expect(chips.nth(3).locator('.pricing-run-name')).toHaveText(/^Box 2\s*Aug 23, 2026$/)

  /* WHAT IS LEFT, WHICH THE CHIP COULD NOT SAY BEFORE D86. `counts.skus` is the SIZE of a job
     and never the job: box 2's 108 SKUs are one `floor` press. This fixture's runs have not
     emitted, so every chip says it was never sent. */
  await expect(chips.nth(0).locator('.pricing-run-owes')).toHaveText('Never sent')
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

  await page.getByRole('button', { name: /^(Every run|\d+ runs?)$/ }).click()
  const chips = page.locator('.pricing-run')
  await expect(chips).toHaveCount(2)
  await expect(chips.nth(1).locator('.pricing-run-owes')).toHaveText('148 unsent')
  await expect(chips.nth(0).locator('.pricing-run-owes')).toHaveText('All sent')
  await expect(page.locator('.pricing-runs-count')).toHaveText('Showing all 1 with work left')

  /* WHAT THE LIST CANNOT SEND IS NAMED ON THE DECK, each figure a door — AND THE FIGURE IS
     CARDS. The two zero-card husks and the zero-card reallocated run are withholding nothing,
     so they are not warned about; the one holding 99 sellable cards says the number. */
  const line = page.getByTestId('pricing-unreachable')
  await expect(line).toContainText('214 never identified')
  await expect(line).toContainText('1 in Review')
  await expect(line).toContainText('99 in 1 reading over a deleted box')
  await expect(line).not.toContainText('not matched')
  await expect(line).not.toContainText('2 readings over a deleted box')
  await expect(line.getByRole('link', { name: '1 in Review' })).toHaveAttribute('href', '#/review')
})

/* THE REVIEWER'S CASE (the delta review, R4 F2): a run that WAS sent and still owes a price
 * for a card with no market price. "Not sent yet" was false for it. The chip tells the two
 * apart, and says how many cards owe the price. */
test('a sent run that owes a price says so, apart from a run never sent', async ({ page }) => {
  await open(page, {
    noRun: true,
    emitted: true,
    runs: [
      { run: '2026-08-24-box2-01', box: 2, box_name: 'Pokemon bulk', skus: 3, created_at: '2026-08-24T18:00:00+00:00' },
      { run: '2026-09-02-box6-01', box: 6, box_name: 'Riftbound rares', skus: 2, created_at: '2026-09-02T18:00:00+00:00' },
    ],
    unsent: { '2026-08-24-box2-01': 1, '2026-09-02-box6-01': 2 },
    owes: {
      '2026-08-24-box2-01': ['1 card with no market price needs a price'],
      '2026-09-02-box6-01': ['never emitted'],
    },
    owed: {
      '2026-08-24-box2-01': [{ code: 'needs_price', count: 1 }],
      '2026-09-02-box6-01': [{ code: 'never_emitted', count: null }],
    },
  })
  await page.getByRole('button', { name: /^(Every run|\d+ runs?)$/ }).click()
  const chips = page.locator('.pricing-run')
  await expect(chips).toHaveCount(2)
  await expect(chips.nth(0).locator('.pricing-run-owes')).toHaveText('Never sent')
  await expect(chips.nth(1).locator('.pricing-run-owes')).toHaveText('Sent, 1 needs a price')
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
  await expect(line).toContainText('1 reading over a deleted box')
  await expect(line).not.toContainText('in 1 reading over a deleted box')
  await expect(line).not.toContainText('2 readings')
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

test('typing a price then pressing Send saves before it sends', async ({ page }) => {
  const wire = await open(page)

  await field(page).fill('19.99')
  await sendPress(page).click()

  await expect.poll(() => sendPosts(wire).length).toBe(1)

  /* THE WRITE RACE, ASSERTED AS AN ORDER. The click blurs the field, which commits and calls
     `setDoc`; a send fired in the same event would write the file from the prices as they were
     before the last answer. The press waits for the save loop to go quiet. */
  const order = wire
    .filter((r) => r.method === 'PUT' || (r.method === 'POST' && r.path === '/pipeline/send'))
    .map((r) => r.method)
  expect(order).toEqual(['PUT', 'POST'])
  /* ONE PRESS, CONFIRMED: the body carries `confirm` and the runs, and nothing that would stop
     at the file. */
  expect(sendPosts(wire)[0]?.body).toMatchObject({ runs: [RUN], confirm: true })
  expect(sendPosts(wire)[0]?.body).not.toHaveProperty('download')
})

test('one press sends and makes live, and says when the check comes', async ({ page }) => {
  const wire = await open(page, { sends: (seen) => (sendPosts(seen).length > 0 ? { ...SENDS_NONE, sends: [sendSummary()] } : SENDS_NONE) })
  await sendPress(page).click()
  await expect.poll(() => sendPosts(wire).length).toBe(1)

  /* THE CARD STANDS ON THE RECEIPT: live now, and when Banchi looks again. No second press
     exists to make it live (the owner's ruling: one press). */
  await expect(page.locator('.send-standing')).toContainText('3 copies went live at')
  await expect(page.locator('.send-standing')).toContainText('Banchi checks TCGplayer again after')
  await expect(page.getByRole('button', { name: /live$/i }).filter({ hasText: /^Put/ })).toHaveCount(0)
  expect(sendPosts(wire)).toHaveLength(1)
})

test('what the double-send guard held back is named, card by card', async ({ page }) => {
  const trimmed = sendSummary({
    trimmed: [{ sku: '8608459', name: 'Dunsparce', live: 2, on_hand: 3, would: 3, goes: 1 }],
    trimmed_copies: 2,
  })
  const wire = await open(page, {
    send: () => ({ status: 200, body: { send: trimmed, console: '' } }),
    sends: (seen) => (sendPosts(seen).length > 0 ? { ...SENDS_NONE, sends: [trimmed] } : SENDS_NONE),
  })
  await sendPress(page).click()
  await expect.poll(() => sendPosts(wire).length).toBe(1)
  const held = page.locator('.send-trimmed')
  await expect(held).toContainText('2 copies held back: TCGplayer already had them.')
  await expect(held).toContainText('Dunsparce')
  await expect(held).toContainText('2 of 3 already live')
})

/* ROUND 5, THE MIXED SEND (the owner's ruling, 2026-09-24: "Allow mixed"). One press lists new
   copies and reprices cards already live. A price change is a row this press adds no copy of,
   already live, whose TYPED price is not the live one. A rule price never counts, and a typed
   price TCGplayer already shows is no change. The press says both, apart. */
test('r6: a mixed press counts only the prices typed on this list, and names them', async ({ page }) => {
  const mixed = sendSummary({ copies: 3, prices: 1, rows: 2 })
  const wire = await open(page, {
    skus: [
      sku({ sku: '8608859', name: 'Articuno' }),
      sku({
        sku: '8608459',
        name: 'Dunsparce',
        at_cap: true,
        add_to_quantity: 0,
        live_before: 2,
        nothing_to_add: 'every copy in this run is already listed or has left the box',
        snap: { market: '10.00', direct_low: null, low: '9.50', low_with_shipping: '10.50', now: '9.99' },
        listing: { pushed: 2, staged: 0, live: 2 },
      }),
      sku({
        sku: '8608659',
        name: 'Wattrel',
        at_cap: true,
        add_to_quantity: 0,
        live_before: 1,
        nothing_to_add: 'every copy in this run is already listed or has left the box',
        snap: { market: '4.10', direct_low: null, low: '3.90', low_with_shipping: '4.90', now: '4.00' },
        listing: { pushed: 1, staged: 0, live: 1 },
      }),
      sku({
        sku: '8608959',
        name: 'Kled',
        at_cap: true,
        add_to_quantity: 0,
        live_before: 1,
        nothing_to_add: 'every copy in this run is already listed or has left the box',
        snap: { market: '6.00', direct_low: null, low: '5.50', low_with_shipping: '6.50', now: '7.00' },
        listing: { pushed: 1, staged: 0, live: 1 },
      }),
    ],
    decisions: {
      rule: 'match',
      basis: 'market',
      sub_threshold: null,
      /* Dunsparce typed over its live price: a change. Wattrel typed AT its live price: none.
         Kled carries no typed price, so the rule's figure never reaches its live listing. */
      overrides: { '8608459': '12.50', '8608659': '4.00' },
    },
    send: () => ({ status: 200, body: { send: mixed, console: '' } }),
    sends: (seen) => (sendPosts(seen).length > 0 ? { ...SENDS_NONE, sends: [mixed] } : SENDS_NONE),
  })
  /* ROUND 6 (B1, B2): A PRICE THE CORPUS HOLDS IS NOT ONE THE OWNER TYPED HERE. The stored
     12.50 may be a Live tab preset or a mark-down never sent; the button does not count it, so
     no send carries it. */
  await expect(page.getByRole('button', { name: 'Send 3 copies to TCGplayer' })).toBeVisible()
  const dunsparce = page.getByLabel('Price for Dunsparce')
  await dunsparce.fill('13.00')
  await dunsparce.press('Tab')
  const press = page.getByRole('button', { name: 'Send 3 copies and 1 price change' })
  await expect(press).toBeVisible()
  await press.click()
  await expect.poll(() => sendPosts(wire).length).toBe(1)
  /* THE PRESS NAMES THE PRICE IT COUNTED, AND THE LIVE PRICE THE ROW DREW: the server sends no
     other price row, and refuses this one if TCGplayer's price moved since. */
  expect(sendPosts(wire)[0]?.body).toMatchObject({ prices: [{ sku: '8608459', price: '13.00', was: '9.99' }] })
  await expect(page.locator('.send-standing')).toContainText('3 copies and 1 price change went live at')
})

/* ROUND 7, THE OWNER'S RULING (R6-3): A NEW COPY OF A CARD ALREADY LIVE CARRIES BANCHI'S STORED
   PRICE, and TCGplayer lists every copy of one card at one price, so the live copies move with
   it. The button names every live copy that moves and its new price, off the newest live
   export, and the press tells the server which moves it named. */
test('r7: the button names the live copies a new copy moves, and the press names them', async ({ page }) => {
  const wire = await open(page, {
    skus: [
      sku({
        sku: '8608859',
        name: 'Articuno',
        add_to_quantity: 1,
        copies: 1,
        live_before: 2,
        listing: { pushed: 2, staged: 0, live: 2 },
        live_now: { export: 'live-tcgplayer-20260924-120000.csv', copies: 2, price: '22.03' },
      }),
    ],
    decisions: { rule: 'match', basis: 'market', sub_threshold: null, overrides: { '8608859': '19.99' } },
  })
  const press = page.getByRole('button', { name: 'Send 1 copy, 2 live copies move to $19.99' })
  await expect(press).toBeVisible()
  await press.click()
  await expect.poll(() => sendPosts(wire).length).toBe(1)
  expect(sendPosts(wire)[0]?.body).toMatchObject({ moves: [{ sku: '8608859', price: '19.99' }] })
})

/* ROUND 7, R6-1: A PRICE THE LIST SHOWED AGAINST A LIVE FIGURE THAT HAS MOVED SINCE. The refusal
   carries the live price as data; the card says "TCGplayer shows $22.03 now. Send $30.00?", and
   one press sends again with that live price named. */
test('r7: a moved live price is offered back, and one press sends it at the owner price', async ({ page }) => {
  let presses = 0
  const wire = await open(page, {
    skus: [sku({ sku: '8608859', name: 'Articuno' }),
      sku({
        sku: '8608459',
        name: 'Dunsparce',
        at_cap: true,
        add_to_quantity: 0,
        live_before: 2,
        nothing_to_add: 'every copy in this run is already listed or has left the box',
        snap: { market: '10.00', direct_low: null, low: '9.50', low_with_shipping: '10.50', now: '11.00' },
        listing: { pushed: 2, staged: 0, live: 2 },
        live_now: { export: 'live-tcgplayer-20260924-120000.csv', copies: 2, price: '9.99' },
      }),
    ],
    decisions: { rule: 'match', basis: 'market', sub_threshold: null, overrides: {} },
    send: () => {
      presses += 1
      return presses === 1
        ? {
            status: 409,
            code: 'price_refused',
            data: {
              refused: [
                { sku: '8608459', name: 'Dunsparce', why: 'live_moved', price: '30.00', live: '22.03', shown: '9.99', copies: 2 },
              ],
            },
          }
        : { status: 200, body: { send: sendSummary({ copies: 3, prices: 1 }), console: '' } }
    },
  })
  const dunsparce = page.getByLabel('Price for Dunsparce')
  await dunsparce.fill('30.00')
  await dunsparce.press('Tab')
  await page.getByRole('button', { name: 'Send 3 copies and 1 price change' }).click()
  await expect.poll(() => sendPosts(wire).length).toBe(1)
  const offer = page.locator('.send-resend')
  await expect(offer).toContainText('TCGplayer shows $22.03 now. Send $30.00?')
  await offer.getByRole('button', { name: 'Send $30.00' }).click()
  await expect.poll(() => sendPosts(wire).length).toBe(2)
  expect(sendPosts(wire)[1]?.body).toMatchObject({ prices: [{ sku: '8608459', price: '30.00', was: '22.03' }] })
  await expect(page.locator('.send-resend')).toHaveCount(0)
})

/* ROUND 7, R6-2: UNDO TAKES A PRICE OUT OF THE NAMED ONES. The answer it restores may be a Live
   tab preset or a mark-down never sent, so it was not typed this visit and does not ride. */
test('r7: undo takes a typed price off the button', async ({ page }) => {
  await open(page, {
    skus: [sku({ sku: '8608859', name: 'Articuno' }),
      sku({
        sku: '8608459',
        name: 'Dunsparce',
        at_cap: true,
        add_to_quantity: 0,
        live_before: 2,
        nothing_to_add: 'every copy in this run is already listed or has left the box',
        snap: { market: '10.00', direct_low: null, low: '9.50', low_with_shipping: '10.50', now: '11.00' },
        listing: { pushed: 2, staged: 0, live: 2 },
        live_now: { export: 'live-tcgplayer-20260924-120000.csv', copies: 2, price: '9.99' },
      }),
    ],
    decisions: { rule: 'match', basis: 'market', sub_threshold: null, overrides: { '8608459': '12.50' } },
  })
  const dunsparce = page.getByLabel('Price for Dunsparce')
  await dunsparce.fill('13.00')
  await dunsparce.press('Tab')
  await expect(page.getByRole('button', { name: 'Send 3 copies and 1 price change' })).toBeVisible()
  await dunsparce.focus()
  await page.keyboard.press('u')
  await expect(page.getByRole('button', { name: 'Send 3 copies to TCGplayer' })).toBeVisible()
})

/* ROUND 8, R7-2: THE OWNER'S RULING NAMES THE COPIES THAT MOVE AND THEIR PRICE. When a press moves
   live copies to more than one price, the button keeps its short phrase and the card lists each
   card, its live copies, and its old and new price before the press. The press sends each
   move's count, and the server refuses a count that is not TCGplayer's. */
test('r8: moves to more than one price are listed card by card before the press', async ({ page }) => {
  const wire = await open(page, {
    skus: [
      sku({
        sku: '8608859',
        name: 'Articuno',
        add_to_quantity: 1,
        copies: 1,
        live_before: 2,
        listing: { pushed: 2, staged: 0, live: 2 },
        live_now: { export: 'live-tcgplayer-20260924-120000.csv', copies: 2, price: '22.03' },
      }),
      sku({
        sku: '8608459',
        name: 'Dunsparce',
        add_to_quantity: 1,
        copies: 1,
        live_before: 3,
        listing: { pushed: 3, staged: 0, live: 3 },
        live_now: { export: 'live-tcgplayer-20260924-120000.csv', copies: 3, price: '5.00' },
      }),
    ],
    decisions: { rule: 'match', basis: 'market', sub_threshold: null, overrides: { '8608859': '19.99', '8608459': '6.00' } },
  })
  const press = page.getByRole('button', { name: 'Send 2 copies, 5 live copies move to new prices' })
  await expect(press).toBeVisible()
  const list = page.locator('.send-moves')
  await expect(list).toContainText('Articuno')
  await expect(list).toContainText('2 live copies, $22.03 to $19.99')
  await expect(list).toContainText('Dunsparce')
  await expect(list).toContainText('3 live copies, $5.00 to $6.00')
  await press.click()
  await expect.poll(() => sendPosts(wire).length).toBe(1)
  expect(sendPosts(wire)[0]?.body).toMatchObject({
    moves: [
      { sku: '8608859', price: '19.99', copies: 2 },
      { sku: '8608459', price: '6.00', copies: 3 },
    ],
  })
})

/* ROUND 8, R7-4: A LIVE ROW WITH COPIES AND NO PRICE IS A MOVE. Whether TCGplayer can hold one is
   not known, so the button names it: the safe side. */
test('r8: live copies with no price are named as a move', async ({ page }) => {
  await open(page, {
    skus: [
      sku({
        sku: '8608859',
        name: 'Articuno',
        add_to_quantity: 1,
        copies: 1,
        live_before: 2,
        listing: { pushed: 2, staged: 0, live: 2 },
        live_now: { export: 'live-tcgplayer-20260924-120000.csv', copies: 2, price: null },
      }),
    ],
    decisions: { rule: 'match', basis: 'market', sub_threshold: null, overrides: { '8608859': '19.99' } },
  })
  await expect(page.getByRole('button', { name: 'Send 1 copy, 2 live copies move to $19.99' })).toBeVisible()
})

/* ROUND 8, R7-3: THE BUTTON COUNTED ANOTHER NUMBER OF LIVE COPIES THAN TCGPLAYER HOLDS. The refusal
   carries TCGplayer's count, and one press names the move at that count. */
test('r8: a refused count of live copies is offered back at TCGplayer count', async ({ page }) => {
  let presses = 0
  const wire = await open(page, {
    send: () => {
      presses += 1
      return presses === 1
        ? {
            status: 409,
            code: 'price_refused',
            data: {
              refused: [
                { sku: '8608859', name: 'Articuno', why: 'move_count', price: '19.99', live: '22.03', shown: '1', copies: 2 },
              ],
            },
          }
        : { status: 200, body: { send: sendSummary(), console: '' } }
    },
  })
  await sendPress(page).click()
  const offer = page.locator('.send-resend')
  await expect(offer).toContainText('2 live copies at $22.03 move to $19.99.')
  await offer.getByRole('button', { name: 'Send $19.99' }).click()
  await expect.poll(() => sendPosts(wire).length).toBe(2)
  expect(sendPosts(wire)[1]?.body).toMatchObject({ moves: [{ sku: '8608859', price: '19.99', copies: 2 }] })
})

/* ROUND 9, D118: A PRESS CHANGES WHAT IS ON THE SCREEN, NEVER WHERE THE REST OF IT IS. The press
   named its live copies on two lines at 390 and became the one-line "Checking TCGplayer, then
   sending…" under the finger, so the sticky bar shrank and the press moved. Measured before and
   during a press held open, at a phone and a tablet width: the press, and the door beside it,
   stay where they were. */
for (const width of [390, 820]) {
  test(`r9: the send press keeps its place and size while it runs (${width})`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 })
    const wire = await open(page, {
      skus: [
        sku({
          sku: '8608859',
          name: 'Articuno',
          add_to_quantity: 1,
          copies: 1,
          live_before: 2,
          listing: { pushed: 2, staged: 0, live: 2 },
          live_now: { export: 'live-tcgplayer-20260924-120000.csv', copies: 2, price: '22.03' },
        }),
      ],
      decisions: { rule: 'match', basis: 'market', sub_threshold: null, overrides: { '8608859': '19.99' } },
      sendDelayMs: 1500,
    })
    const press = page.locator('.send-press')
    /* BELOW 768 THE QUIET DOORS SIT BEHIND MORE (D277, Q4): opened first, then measured. */
    const more = page.getByRole('button', { name: 'More send options' })
    if (await more.isVisible()) await more.click()
    const door = page.locator('.send-act').getByRole('button', { name: /Download/ })
    await expect(press).toContainText('2 live copies move to')
    const before = { press: await press.boundingBox(), door: await door.boundingBox() }
    await press.click()
    await expect(press).toHaveAttribute('data-busy', 'true')
    await expect.poll(() => sendPosts(wire).length).toBe(1)
    const during = { press: await press.boundingBox(), door: await door.boundingBox() }
    for (const key of ['press', 'door'] as const) {
      const a = before[key]
      const b = during[key]
      expect(b, `${key} is drawn during the press`).not.toBeNull()
      expect(Math.abs((b?.x ?? 0) - (a?.x ?? 0)), `${key} x`).toBeLessThanOrEqual(0.5)
      expect(Math.abs((b?.y ?? 0) - (a?.y ?? 0)), `${key} y`).toBeLessThanOrEqual(0.5)
      expect(Math.abs((b?.width ?? 0) - (a?.width ?? 0)), `${key} width`).toBeLessThanOrEqual(0.5)
      expect(Math.abs((b?.height ?? 0) - (a?.height ?? 0)), `${key} height`).toBeLessThanOrEqual(0.5)
    }
  })
}

/* ROUND 6, S4: A ROLLBACK'S ANSWER IS NOT PROOF. A press TCGplayer turned away and Banchi rolled
   back offers no Try again, and keeps "check the Staged list" until the owner dismisses it. */
test('r6: a rolled-back send offers no retry and keeps the Staged check until dismissed', async ({ page }) => {
  const rolled = sendSummary({
    stamp: '20260924-120000-cccccc',
    state: 'failed',
    published_at: null,
    taken_back_at: '2026-09-24T12:00:09+00:00',
    failure: { code: 'send_rolled_back', message: 'rolled back' },
    warning: 'rolled_back',
  })
  const wire = await open(page, {
    send: () => ({ status: 409, code: 'send_rolled_back' }),
    sends: (seen) =>
      seen.some((r) => r.path.endsWith('/dismiss'))
        ? { ...SENDS_NONE, sends: [{ ...rolled, warning: null }] }
        : sendPosts(seen).length > 0
          ? { ...SENDS_NONE, sends: [rolled] }
          : SENDS_NONE,
  })
  await sendPress(page).click()
  const refusal = page.locator('.send-failure')
  await expect(refusal).toContainText('Check the Staged list before you send again.')
  await expect(refusal.getByRole('button', { name: 'Try again' })).toHaveCount(0)
  const warned = page.locator('.send-taken-back')
  await expect(warned).toContainText('Upload rolled back at')
  await expect(warned).toContainText('Check the Staged list')
  await warned.getByRole('button', { name: 'Dismiss' }).click()
  await expect.poll(() => wire.filter((r) => r.path.endsWith('/dismiss')).length).toBe(1)
  await expect(page.locator('.send-taken-back')).toHaveCount(0)
})

/* ROUND 6, S2: A PRESS THAT DIED MID-PUSH HAS NO `unknown`, and its upload may still wait in
   Staged. The card reads the server's `staged`, never `unknown` alone. */
test('r6: a send that stopped mid-push names the Staged list', async ({ page }) => {
  const crashed = sendSummary({ state: 'unknown', published_at: null, held: true, unknown: null, staged: true })
  await open(page, { sends: () => ({ ...SENDS_NONE, sends: [crashed] }) })
  await expect(page.locator('.send-unknown')).toContainText('may still wait in TCGplayer’s Staged list')
})

/* ROUND 5: TWO PRESSES IN ONE SECOND. A stamp is the second, then a random tail, so the card
   compared stamps and stood on its own older press whenever the newer one drew the smaller
   tail. The server lists receipts newest PRESS first, and the card stands on that. */
test('r5: two presses in one second: the card stands on the newest press, not the larger stamp', async ({ page }) => {
  const mine = sendSummary({ stamp: '20260924-120000-ffffff', copies: 3 })
  const later = sendSummary({ stamp: '20260924-120000-000000', copies: 5 })
  const wire = await open(page, {
    send: () => ({ status: 200, body: { send: mine, console: '' } }),
    sends: (seen) => (sendPosts(seen).length > 0 ? { ...SENDS_NONE, sends: [later, mine] } : SENDS_NONE),
  })
  await sendPress(page).click()
  await expect.poll(() => sendPosts(wire).length).toBe(1)
  await expect(page.locator('.send-standing')).toContainText('5 copies went live at')
})

/* ROUND 5: AT 390 WIDE, TWO TAKEN-BACK WARNINGS STOOD HALF THE SCREEN HIGH IN THE STICKY BAR.
   Each folds to one line: the warning's own imperative, a press that opens the rest, and
   Dismiss. It never folds away: only Dismiss takes it off the card (round 4). */
test('r5: at 390 two taken-back warnings fold to one line each, and stay until Dismiss', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const staged = sendSummary({
    stamp: '20260924-120000-aaaaaa',
    state: 'taken_back',
    taken_back_at: '2026-09-24T12:20:00+00:00',
    unknown: { stage: 'publish', upload_id: 'u-1', staged: true, file: 'import.csv', at: '2026-09-24T12:00:05+00:00' },
    warning: 'staged',
  })
  const file = sendSummary({
    stamp: '20260924-110000-bbbbbb',
    kind: 'download',
    state: 'taken_back',
    taken_back_at: '2026-09-24T12:21:00+00:00',
    warning: 'old_file',
  })
  const wire = await open(page, {
    sends: (seen) =>
      seen.some((r) => r.path.endsWith('/dismiss'))
        ? { ...SENDS_NONE, sends: [{ ...staged, warning: null }, file] }
        : { ...SENDS_NONE, sends: [staged, file] },
  })
  const warned = page.locator('.send-taken-back')
  await expect(warned).toHaveCount(2)
  for (const index of [0, 1]) {
    const box = await warned.nth(index).boundingBox()
    /* ONE LINE: the 40px press it opens by, and the notice's own padding. */
    expect(box?.height ?? 999).toBeLessThanOrEqual(72)
    await expect(warned.nth(index).locator('.bn-notice-body')).toBeHidden()
  }
  await expect(warned.nth(0).locator('.send-fold')).toHaveText('Do not publish the upload.')
  await expect(warned.nth(1).locator('.send-fold')).toHaveText('Do not upload the old file.')
  /* THE LINE IS READ WHOLE, never cut to an ellipsis: it is the warning while folded. */
  const cut = await page.locator('.send-fold-line').evaluateAll((lines) => lines.filter((line) => line.scrollWidth > line.clientWidth).length)
  expect(cut).toBe(0)

  const fold = warned.nth(0).locator('.send-fold')
  await fold.click()
  await expect(fold).toHaveAttribute('aria-expanded', 'true')
  await expect(warned.nth(0).locator('.bn-notice-body')).toBeVisible()
  await expect(warned.nth(0).locator('.bn-notice-body')).toContainText('Do not publish it there.')
  await fold.click()
  await expect(warned.nth(0).locator('.bn-notice-body')).toBeHidden()
  await expect(warned).toHaveCount(2)

  await warned.nth(0).getByRole('button', { name: 'Dismiss' }).click()
  await expect.poll(() => wire.filter((r) => r.path.endsWith('/dismiss')).length).toBe(1)
  await expect(page.locator('.send-taken-back')).toHaveCount(1)
})

test('a live check that cannot run refuses the send, says why, and offers Try again', async ({ page }) => {
  let presses = 0
  const wire = await open(page, {
    send: () => {
      presses += 1
      return presses === 1
        ? { status: 502, code: 'live_check_failed' }
        : { status: 200, body: { send: sendSummary(), console: '' } }
    },
  })
  await sendPress(page).click()
  const refusal = page.locator('.send-failure')
  await expect(refusal).toContainText('Banchi could not read what is live at TCGplayer, so nothing was sent.')
  /* THE SERVER'S OWN TEXT IS BEHIND "What the server said", never the title (D196). */
  await expect(refusal.locator('summary')).toHaveText('What the server said')

  await refusal.getByRole('button', { name: 'Try again' }).click()
  await expect.poll(() => sendPosts(wire).length).toBe(2)
  await expect(page.locator('.send-failure')).toHaveCount(0)
})

test('a send with nothing left to add is a refusal, and offers no retry', async ({ page }) => {
  await open(page, { send: () => ({ status: 409, code: 'nothing_to_send' }) })
  await sendPress(page).click()
  const refusal = page.locator('.send-failure')
  await expect(refusal).toContainText('Nothing to send. Every copy on this list is already at TCGplayer or held back.')
  await expect(refusal.getByRole('button', { name: 'Try again' })).toHaveCount(0)
})

/* THE TITLE STATES EVERY REASON (R6-2): a send emptied by a card with no price AND by cards the
 * guard found already live says both in the title, worded from the refusal's figures. The
 * server's own sentence stays behind "What the server said" (D269). */
test('an empty send titles every reason it had, never only the price', async ({ page }) => {
  await open(page, {
    send: () => ({
      status: 409,
      code: 'needs_price',
      data: { empty: { needs_price: 1, under_cut_off: 0, live: 2, live_names: ['Dunsparce', 'Dunsparce'] } },
    }),
  })
  await sendPress(page).click()
  const title = page.locator('.send-failure .bn-notice-title')
  await expect(title).toHaveText(
    'Nothing was sent. 1 card needs a price first. TCGplayer already had every copy of 2 cards (Dunsparce, Dunsparce).',
  )
})

test('Download the file instead writes the file, and its copies are named until they are found', async ({
  page,
}) => {
  const written = sendSummary({
    kind: 'download',
    state: 'written',
    published_at: null,
    check_after: '2026-09-24T12:17:00+00:00',
    take_back_after: '2026-09-24T12:17:00+00:00',
    copies: 4,
  })
  /* PAST THE WAIT, THE CHECK FOUND NONE OF THEM: now, and only now, they can come back. */
  const unfound = sendSummary({
    ...written,
    state: 'short',
    take_back_after: null,
    takeable: 4,
    checked_at: '2026-09-24T12:18:00+00:00',
    check: { export: 'live.csv', found: 0, expected: 4, missing: [{ sku: '8608459', name: 'Dunsparce', sent: 4, found: 0 }] },
  })
  let checked = false
  const wire = await open(page, {
    send: (body) => ({ status: 200, body: { send: { ...written, files: body.split_threshold ? ['import-listed.csv', 'import-subthreshold.csv'] : ['import.csv'] }, console: '' } }),
    sends: (seen) =>
      seen.some((r) => r.path.endsWith('/take-back'))
        ? SENDS_NONE
        : sendPosts(seen).length > 0
          ? { ...SENDS_NONE, sends: [checked ? unfound : written], unconfirmed: { copies: 4, stamps: [written.stamp] } }
          : SENDS_NONE,
  })

  /* THE SPLIT LIVES BEHIND THE DOOR, NOT BESIDE THE SEND (the Send-menu ruling). */
  await expect(page.getByLabel('Split in two files at the cut-off')).toHaveCount(0)
  await page.getByRole('button', { name: 'Download the file instead' }).click()
  await expect(page.getByLabel('Split in two files at the cut-off')).toBeVisible()
  await page.getByRole('button', { name: 'Write the file' }).click()
  await expect.poll(() => sendPosts(wire).length).toBe(1)
  expect(sendPosts(wire)[0]?.body).toMatchObject({ runs: [RUN], download: true })
  expect(sendPosts(wire)[0]?.body).not.toHaveProperty('confirm')

  const file = page.locator('.send-files a')
  await expect(file).toHaveAttribute('download', 'import.csv')
  expect(await file.getAttribute('href')).toContain('/pipeline/sends/20260924-120000/file?name=import.csv')

  /* Q8: WRITTEN, NOT CONFIRMED — AND NO WAY BACK UNTIL A CHECK HAS RUN PAST THE WAIT (the
     owner's ruling, 2026-09-24). The card says when it will be safe instead. */
  const unconfirmed = page.locator('.send-unconfirmed')
  await expect(unconfirmed).toContainText('4 copies written, not confirmed at TCGplayer')
  await expect(unconfirmed).toContainText('You can take them back after')
  await expect(page.getByRole('button', { name: /^Take .* back$/ })).toHaveCount(0)

  checked = true
  await page.getByRole('button', { name: 'Check what is live' }).click()
  const back = page.locator('.send-short-check')
  await expect(back).toContainText('0 of 4 found at TCGplayer')
  await back.getByRole('button', { name: 'Take 4 copies back' }).click()
  await expect.poll(() => wire.filter((r) => r.path.endsWith('/take-back')).length).toBe(1)
  await expect(page.locator('.send-short-check')).toHaveCount(0)
})

test('a send TCGplayer did not confirm is held, names the upload waiting, and offers no second send', async ({
  page,
}) => {
  const unknown = sendSummary({
    state: 'unknown',
    published_at: null,
    held: true,
    take_back_after: '2026-09-24T12:17:00+00:00',
    check_after: '2026-09-24T12:17:00+00:00',
    unknown: { stage: 'rollback', upload_id: 'u-1', staged: true, file: 'import.csv', at: '2026-09-24T12:00:05+00:00' },
  })
  const wire = await open(page, {
    send: () => ({ status: 409, code: 'send_unknown' }),
    sends: (seen) => (sendPosts(seen).length > 0 ? { ...SENDS_NONE, sends: [unknown] } : SENDS_NONE),
  })
  await sendPress(page).click()
  await expect.poll(() => sendPosts(wire).length).toBe(1)
  const refusal = page.locator('.send-failure')
  await expect(refusal).toContainText('TCGplayer did not confirm this send. Do not send these copies again.')
  await expect(refusal.getByRole('button', { name: 'Try again' })).toHaveCount(0)
  const held = page.locator('.send-unknown')
  await expect(held).toContainText('TCGplayer has not confirmed 3 copies.')
  await expect(held).toContainText('may still wait in TCGplayer’s Staged list')
  await expect(held).toContainText('stay out of every send')
  await expect(page.getByRole('button', { name: /^Take .* back$/ })).toHaveCount(0)
})

test('an unconfirmed send whose upload may wait in Staged keeps saying so after the check, beside Take back', async ({
  page,
}) => {
  /* THE ROUND-2 REVIEW, F3. Past the wait the check found none of the copies, so they can come
     back. The upload TCGplayer never confirmed may still wait in its Staged list: taking the
     copies back and then publishing that upload by hand would list them twice. The warning
     stays for as long as the receipt is drawn. */
  const staged = { stage: 'publish', upload_id: 'u-1', staged: true, file: 'import.csv', at: '2026-09-24T12:00:05+00:00' }
  const short = sendSummary({
    state: 'short',
    published_at: null,
    held: false,
    takeable: 3,
    checked_at: '2026-09-24T12:18:00+00:00',
    check: { export: 'live.csv', found: 0, expected: 3, missing: [{ sku: '8608459', name: 'Dunsparce', sent: 3, found: 0 }] },
    unknown: staged,
  })
  await open(page, { sends: () => ({ ...SENDS_NONE, sends: [short] }) })
  const card = page.locator('.send-short-check')
  await expect(card).toContainText('0 of 3 found at TCGplayer')
  await expect(card).toContainText('may still wait in TCGplayer’s Staged list')
  await expect(card).toContainText('Do not publish it there')
  await expect(card.getByRole('button', { name: 'Take 3 copies back' })).toBeVisible()
})

test('an unconfirmed send the check found whole still names the upload that may wait in Staged', async ({ page }) => {
  /* NOTHING HERE CAN SAY THE UPLOAD LEFT STAGED: the copies found live may be that upload, or a
     hand upload of the same file. The warning outlives the check (F3). Checked moments ago, so
     the card still draws it. */
  const found = sendSummary({
    state: 'checked',
    published_at: null,
    checked_at: new Date().toISOString(),
    check: { export: 'live.csv', found: 3, expected: 3, missing: [] },
    unknown: { stage: 'publish', upload_id: 'u-1', staged: true, file: 'import.csv', at: '2026-09-24T12:00:05+00:00' },
  })
  await open(page, { sends: () => ({ ...SENDS_NONE, sends: [found] }) })
  const card = page.locator('.send-standing')
  await expect(card).toContainText('3 of 3 found at TCGplayer')
  await expect(card).toContainText('may still wait in TCGplayer’s Staged list')
})

/* THE ROUND-3 REVIEW, H2: THE WARNING OUTLIVES TAKE BACK. Right after it the copies are on the
   list again, so the old upload published by hand, or the old file uploaded, would list them
   twice. The round-3 card drew no taken-back receipt at all, so the warning went at the one
   moment it matters most. It stays until the owner dismisses it. */
for (const [kind, warning, said] of [
  ['send', 'staged', 'may still wait in TCGplayer’s Staged list. Do not publish it there.'],
  ['download', 'old_file', 'Do not upload the file written at'],
] as const) {
  test(`a taken-back ${kind} keeps its warning until the owner dismisses it`, async ({ page }) => {
    const staged = kind === 'send' ? { stage: 'publish', upload_id: 'u-1', staged: true, file: 'import.csv', at: '2026-09-24T12:00:05+00:00' } : null
    const short = sendSummary({
      kind,
      state: 'short',
      published_at: null,
      takeable: 3,
      checked_at: '2026-09-24T12:18:00+00:00',
      check: { export: 'live.csv', found: 0, expected: 3, missing: [{ sku: '8608459', name: 'Dunsparce', sent: 3, found: 0 }] },
      unknown: staged,
    })
    const taken = sendSummary({ ...short, state: 'taken_back', takeable: 0, taken_back_at: '2026-09-24T12:20:00+00:00', warning })
    const wire = await open(page, {
      sends: (seen) =>
        seen.some((r) => r.path.endsWith('/dismiss'))
          ? { ...SENDS_NONE, sends: [{ ...taken, warning: null }] }
          : seen.some((r) => r.path.endsWith('/take-back'))
            ? { ...SENDS_NONE, sends: [taken] }
            : { ...SENDS_NONE, sends: [short] },
    })
    await page.locator('.send-short-check').getByRole('button', { name: 'Take 3 copies back' }).click()
    await expect.poll(() => wire.filter((r) => r.path.endsWith('/take-back')).length).toBe(1)
    const warned = page.locator('.send-taken-back')
    await expect(warned).toContainText('Copies taken back at')
    await expect(warned).toContainText(said)
    await warned.getByRole('button', { name: 'Dismiss' }).click()
    await expect.poll(() => wire.filter((r) => r.path.endsWith('/dismiss')).length).toBe(1)
    await expect(page.locator('.send-taken-back')).toHaveCount(0)
  })
}

test('a Take back that fails says so, and never offers a retry that would send', async ({ page }) => {
  /* THE ROUND-3 CARD PUT A FAILED TAKE BACK IN THE PRESS'S OWN FAILURE LINE: it read "the copies
     are back on the list", and a network failure there offered "Try again", which sends. */
  const short = sendSummary({
    state: 'short',
    takeable: 3,
    checked_at: '2026-09-24T12:18:00+00:00',
    check: { export: 'live.csv', found: 0, expected: 3, missing: [{ sku: '8608459', name: 'Dunsparce', sent: 3, found: 0 }] },
  })
  const wire = await open(page, { sends: () => ({ ...SENDS_NONE, sends: [short] }) })
  await page.route(/\/pipeline\/sends\/[^/]+\/take-back$/, (route) => route.abort())
  await page.locator('.send-short-check').getByRole('button', { name: 'Take 3 copies back' }).click()
  const failed = page.locator('.send-undo-failure')
  await expect(failed).toContainText('Banchi could not take these copies back.')
  await expect(page.getByRole('button', { name: 'Try again' })).toHaveCount(0)
  await expect(page.locator('.send-card')).not.toContainText('the copies are back on the list')
  expect(sendPosts(wire)).toHaveLength(0)
})

test('a send that stopped partway is held, says so, and leaves every press on', async ({ page }) => {
  /* THE ROUND-2 REVIEW, F1: a failure after the receipt used to leave it "sending", with both
     buttons off for as long as the server lived. Now it is unknown, and nothing is stuck. */
  const stopped = sendSummary({
    state: 'unknown',
    published_at: null,
    held: true,
    accepted: null,
    take_back_after: '2026-09-24T12:17:00+00:00',
    check_after: '2026-09-24T12:17:00+00:00',
    unknown: { stage: 'deciding', upload_id: null, staged: false, file: 'import.csv', at: '2026-09-24T12:00:05+00:00' },
  })
  await open(page, { sends: () => ({ ...SENDS_NONE, sends: [stopped] }) })
  const held = page.locator('.send-unknown')
  await expect(held).toContainText('Banchi stopped partway through this send.')
  await expect(held).toContainText('stay out of every send')
  await expect(sendPress(page)).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Check what is live' })).toBeEnabled()
})

test('a press over cards a price change holds is refused by name, with no retry', async ({ page }) => {
  await open(page, { send: () => ({ status: 409, code: 'price_change_held' }) })
  await sendPress(page).click()
  const refusal = page.locator('.send-failure')
  await expect(refusal).toContainText('Some of these cards wait on a price change TCGplayer has not confirmed, so nothing was sent.')
  await expect(refusal.getByRole('button', { name: 'Try again' })).toHaveCount(0)
})

test('a press over held cards is refused by name, with no retry', async ({ page }) => {
  await open(page, { send: () => ({ status: 409, code: 'send_held' }) })
  await sendPress(page).click()
  const refusal = page.locator('.send-failure')
  await expect(refusal).toContainText('Some of these cards wait on a send TCGplayer has not confirmed, so nothing was sent.')
  await expect(refusal.getByRole('button', { name: 'Try again' })).toHaveCount(0)
})

test('TCGplayer took fewer rows than were sent, and the card never says more went live', async ({ page }) => {
  const partial = sendSummary({ accepted: 1, rows: 2, turned_away: 1 })
  await open(page, {
    send: () => ({ status: 200, body: { send: partial, console: '' } }),
    sends: (seen) => (sendPosts(seen).length > 0 ? { ...SENDS_NONE, sends: [partial] } : SENDS_NONE),
  })
  await sendPress(page).click()
  const card = page.locator('.send-turned-away')
  await expect(card).toContainText('TCGplayer took 1 of 2 cards.')
  await expect(page.locator('.send-card')).not.toContainText('3 copies went live')
})

test('a dropped connection reads the receipt: a press still running shows, and no second press is offered', async ({
  page,
}) => {
  const running = sendSummary({ state: 'sending', published_at: null, check_after: null, held: true })
  const wire = await open(page, {
    sends: (seen) => (sendPosts(seen).length > 0 ? { ...SENDS_NONE, sends: [running] } : SENDS_NONE),
  })
  /* THE PRESS'S OWN ANSWER NEVER ARRIVES: the connection drops while the server still sends. */
  await page.route(/\/pipeline\/send$/, async (route) => {
    wire.push({ method: 'POST', path: '/pipeline/send', body: route.request().postDataJSON() })
    await route.abort('connectionreset')
  })
  await sendPress(page).click()
  await expect(page.locator('.send-sending')).toContainText('Sending 3 copies to TCGplayer.')
  await expect(page.locator('.send-failure')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Try again' })).toHaveCount(0)
  await expect(page.locator('.send-press')).toBeDisabled()
  expect(sendPosts(wire)).toHaveLength(1)
})

test('a check that is due runs on the visit, with no press', async ({ page }) => {
  const wire = await open(page, {
    sends: (seen) => (seen.some((r) => r.path === '/pipeline/live-check') ? SENDS_NONE : { ...SENDS_NONE, due: true }),
  })
  /* THE CLOSED-APP HALF OF Q3: the wait ended while nobody was here, so arriving is the cue. */
  await expect.poll(() => wire.filter((r) => r.path === '/pipeline/live-check').length).toBe(1)
  expect(wire.find((r) => r.path === '/pipeline/live-check')?.body).toEqual({})
})

test('the wait ends while the page is open, and the check runs with no refresh', async ({ page }) => {
  /* THE SERVER SAYS THE CHECK IS DUE FOUR SECONDS FROM ITS OWN NOW. Until the page asks again
     after that, nothing is due; the timer is what asks again. Timed from the FIRST read, so the
     time the page takes to load cannot eat into the window. */
  const soon = { ...SENDS_NONE, now: '2026-09-24T12:00:00+00:00', check_at: '2026-09-24T12:00:04+00:00' }
  let first = 0
  const wire = await open(page, {
    sends: (seen) => {
      if (first === 0) first = Date.now()
      if (seen.some((r) => r.path === '/pipeline/live-check')) return SENDS_NONE
      return Date.now() - first < 4000 ? soon : { ...SENDS_NONE, due: true }
    },
  })
  expect(wire.filter((r) => r.path === '/pipeline/live-check')).toHaveLength(0)
  /* THE OPEN-APP HALF: one timer, measured on the server's clock, and no reload. */
  await expect.poll(() => wire.filter((r) => r.path === '/pipeline/live-check').length, { timeout: 12000 }).toBe(1)
})

test('Check what is live is a manual press that always runs', async ({ page }) => {
  const wire = await open(page)
  await page.getByRole('button', { name: 'Check what is live' }).click()
  await expect.poll(() => wire.filter((r) => r.path === '/pipeline/live-check').length).toBe(1)
  expect(wire.find((r) => r.path === '/pipeline/live-check')?.body).toEqual({ force: true })
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

  /* `l` SNAPS TO LOWEST, THE COLUMN THE ROW DRAWS (D277): no toggle first. */
  await field(page).focus()
  await page.keyboard.press('l')
  await expect(field(page)).toHaveValue('21.98')

  /* A SNAP YOU CANNOT INSPECT IS A SNAP YOU CANNOT CHECK. It sets the field and stops there;
     the extra Enter is what makes `l`, look, Enter possible. */
  await page.waitForTimeout(150)
  expect(wire.filter((row) => row.method === 'PUT')).toHaveLength(0)
})

test('a snap onto a blank column refuses, says so, and writes nothing', async ({ page }) => {
  const wire = await open(page, {
    skus: [sku({ snap: { market: '22.03', direct_low: null, low: null, low_with_shipping: '22.98', now: null } })],
  })

  /* A ROW WITH NO LOWEST PRICE: `l` has nothing to snap to. */
  await field(page).focus()
  await page.keyboard.press('l')

  /* Writing "" would reach `_price` in decisions.py and raise `MalformedDecisions` at the
     next join, an hour later. The field is untouched and the refusal is on screen now. */
  await expect(field(page)).toHaveValue('22.03')
  await expect(page.locator('.pricing-refusal')).toContainText('No Lowest price on this row')
  await page.waitForTimeout(150)
  expect(wire.filter((row) => row.method === 'PUT')).toHaveLength(0)
})

// ----------------------------------------------------------------------- the hold

test('a hold writes a reason and a watch, and never a price', async ({ page }) => {
  const wire = await open(page)

  await page.locator('.pricing-hold').first().click()
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
  await expect(page.locator('.pricing-held')).toContainText('Held')
  /* docs/DESIGN.md's human-label-large, machine-string-small rule. The machine line is the
     JSON as it sits in the file, so grepping `withheld` finds the screen, the corpus and
     the run report at once — which is the only job that line has.

     THE MACHINE STRING IS ON HOVER NOW, NOT ON A LINE OF ITS OWN, and that is the owner's
     ruling for this rebuild: human labels, no monospace trailer, the raw value kept where it
     can still be read. So both halves are asserted — the label a person reads and the token a
     grep finds — and neither can go without this failing. */
  const state = page.locator('.pricing-state')
  await expect(state).toHaveText('Bullish')
  await expect(state).toHaveAttribute('title', 'withheld: bullish')
  await expect(page.locator('.pricing-why')).toContainText('waiting on rotation')
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
  await expect(page.locator('.pricing-photo-caption')).toContainText(/card\s*1/i)
  await expect(page.locator('.pricing-photo-caption')).toContainText('1 of 3')

  await page.getByRole('button', { name: 'Next copy' }).click()
  await expect(page.locator('.pricing-photo-caption')).toContainText('2 of 3')

  /* IT IS A SHEET NOW (the drawer folded, D278): Escape closes it, as every sheet. */
  await page.keyboard.press('Escape')
  await expect(page.locator('.pricing-photo')).toHaveCount(0)
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
  expect(filled.buttons).toHaveLength(1)
  expect(filled.buttons[0]).toMatch(/^Send (\d+ cop(y|ies) )?to TCGplayer$/)
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
  await expect(page.locator('.pricing-row .pricing-why')).toHaveCount(0)

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

  /* THE HEADING IS OVER THE ROWS IT NAMES: the two rows worth $5 or more need the owner (D277,
     Q2), and the row that adds nothing falls under the server's own sentence, last. */
  await expect(page.locator('.pricing-group-head .pricing-group-why')).toHaveText([
    'Needs you',
    'every copy in this run is already listed or has left the box',
  ])
  const lastGroup = page.locator('.pricing-group').last()
  await expect(lastGroup.locator('.pricing-name')).toHaveText(['Dunsparce'])

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
    'Needs you',
    'every copy in this run is already listed or has left the box',
  ])
  await expect(page.locator('.pricing-row').nth(1).locator('.pricing-state')).toHaveAttribute(
    'title',
    'withheld: keeping',
  )
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
  await expect(rows.nth(1).locator('.pricing-why')).toBeVisible()
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
        note: rect(node.querySelector('.pricing-why')),
      }
    }),
  )
  for (const box of boxes.slice(1)) {
    expect(box.held).not.toBeNull()
    expect(box.held?.top).toBeGreaterThanOrEqual(box.row?.top ?? 0)
    expect(box.held?.bottom).toBeLessThanOrEqual(box.row?.bottom ?? 0)
  }

  /* THE NOTE SITS ON THE CARD'S OWN LINE NOW, beside the held cell rather than under it: it
     only has to stay inside its own row. */
  const both = boxes.at(-1)
  expect(both?.note).not.toBeNull()
  expect(both?.note?.top).toBeGreaterThanOrEqual(both?.row?.top ?? 0)
  expect(both?.note?.bottom).toBeLessThanOrEqual(both?.row?.bottom ?? 0)
})

// ------------------------------------------------------ the save loop actually finishes

test('a committed answer lands and the indicator returns to saved', async ({ page }) => {
  const wire = await open(page)

  await field(page).focus()
  await page.keyboard.type('4.50')
  await page.keyboard.press('Enter')

  await expect.poll(() => wire.filter((row) => row.method === 'PUT').length).toBe(1)
  expect(sentAnswers(wire)).toEqual({ '8608859': '4.50' })
  /* THE SAVE LOOP FINISHES: no error is drawn, and the loop stays free for the next answer. It read
     `saving…` forever — on every save, from the first one. The effect depended on the
     `saving` STATE it raised itself, so raising it re-ran the effect and the re-run's cleanup
     killed the in-flight closure: the response landed on a dead one and neither the clear nor
     `setSaving(false)` ever fired. Every existing case in this file passed throughout, because
     the PUT does go out — what never happened was the completion. */
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
})

// ------------------------------------------------------- a preset reaches what emit reads

test('a preset writes the rule and the basis, which is what the pipeline reads', async ({
  page,
}) => {
  const wire = await open(page)

  await page.getByRole('button', { name: 'Change' }).click()
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

  await page.getByRole('button', { name: 'Change' }).click()
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
  await page.getByRole('button', { name: 'Change' }).click()

  for (const label of ['Match market', 'Market −5%', 'TCG Low −1%']) {
    await expect(page.getByRole('button', { name: label })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  }
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
  await expect(page.locator('.pricing-trend-says')).toHaveText('Trends for 1 card.')
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
          { box: 3, index: 4, label: 'Box 3, Section 1, Card 4' },
          { box: 3, index: 9, label: 'Box 3, Section 1, Card 9' },
          { box: 4, index: 2, label: 'Box 4, Section 1, Card 2' },
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

test('one answer is written once, for the store, however many runs hold the card', async ({
  page,
}) => {
  const wire = await open(page, { worklist: SPAN })

  await page.getByRole('textbox', { name: 'Price for LeBlanc, Everywhere At Once' }).focus()
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
})

test('the over-cap warning is visible with Compare off, and the toggle does not hide a refusal', async ({
  page,
}) => {
  await open(page, { worklist: SPAN })

  /* D156's OWN PROMISE — "what cannot go is named on the deck, with a door each" — MUST
     SURVIVE THE NEW TOGGLE (a regression pin, not a red-first case: nothing hides this
     today and it must stay that way). The over-cap row's warning badge is visible with no
     click at all. */
  await expect(page.locator('.pricing-row', { hasText: 'LeBlanc' }).locator('.pricing-cap')).toBeVisible()
  await expect(page.locator('.pricing-row', { hasText: 'LeBlanc' }).locator('.pricing-cap')).toHaveText('3 of 4 can go')

  /* AND IT STAYS AFTER THE TOGGLE, TOO — Compare only ever ADDS context, it never removes a
     warning. */
  await expect(page.getByRole('button', { name: 'Compare' })).toHaveCount(0)
})

/* NO TYPED MIDDLE DOT OR BULLET REACHES THE SCREEN (D218). A separator here is drawn by CSS
 * (`::after` content on `.bn-dotline` and its scoped siblings), never typed into a string a
 * component renders. `SPAN` plus Compare exercises the box/run join, the over-cap badge, the
 * run picker's own name/day and owes chip, and the header's progress legend — the sites this
 * sweep touched. */
test('no typed middle dot or bullet reaches the pricing worklist (D218)', async ({ page }) => {
  await open(page, { worklist: SPAN })

  const text = await page.locator(VIEW).innerText()
  expect(text).not.toMatch(/[·•]/)
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
  const qty = page.locator('.pricing-row', { hasText: 'LeBlanc' }).locator('.pricing-qty')
  await expect(qty.locator('.pricing-qty-input')).toHaveAttribute('placeholder', '3')
  await expect(page.locator('.pricing-row', { hasText: 'LeBlanc' }).locator('.pricing-cap')).toHaveText('3 of 4 can go')
})

test('a send of several runs is one press over every run, with nothing beside it', async ({
  page,
}) => {
  const wire = await open(page, { worklist: SPAN })

  /* ONE BAR, ONE PRESS, whatever the number of runs: the server writes one file over the union
     (D86) behind the double-send guard. The Send-menu ruling took the caps and the listed-only
     filter off the press, so none of them is drawn here. */
  await expect(page.getByRole('region', { name: 'Send to TCGplayer' })).toHaveCount(1)
  await expect(page.getByRole('checkbox', { name: /above the cut-off/ })).toHaveCount(0)
  await expect(page.getByLabel('Copies to keep live at TCGplayer')).toHaveCount(0)
  await sendPress(page).click()
  await expect.poll(() => sendPosts(wire).length).toBe(1)
  expect((sendPosts(wire)[0]?.body as Record<string, unknown>).runs).toEqual(SPAN.runs.map((row) => row.run))
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

  /* THE CONTROL IS THE CUT-OFF FIELD, AND THE FLOOR PRESS IT REPLACED IS RETIRED (D98). Main
     asserted a segmented row here offering "a flat price" or "the $0.40 floor"; the owner had
     the row deleted and the figure itself made the control, so stating the floor is typing the
     floor's own number. What the case is FOR is unchanged and is the reason it survived the
     rewrite: the store's policy must be reachable on the landing the screen opens on, which is
     every open run and not a single picked one. */
  await page.getByRole('button', { name: 'Change' }).click()
  const cut = page.getByLabel('Cut-off', { exact: true })
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

test('an undo returns the card to what it was, including to having no answer', async ({
  page,
}) => {
  const wire = await open(page, { worklist: SPAN })

  await page.getByRole('textbox', { name: 'Price for LeBlanc, Everywhere At Once' }).focus()
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
  await page.getByRole('textbox', { name: 'Price for LeBlanc, Everywhere At Once' }).focus()
  await page.keyboard.press('u')
  await expect.poll(() => sentAnswers(wire)).toEqual({})
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

  await page.getByRole('button', { name: 'Change' }).click()
  const stranded = page.locator('.pricing-stranded')
  await expect(stranded).toBeVisible()
  await expect(stranded).toContainText('$0.24')

  /* ONE PRESS RESOLVES IT, AND IT WRITES BOTH KEYS. Which of the two figures the operator meant
     is not a thing this screen can know, so it offers the cut-off and states what that does
     rather than choosing on their behalf. */
  await page.getByRole('button', { name: 'Use the cut-off for both' }).click()
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

  const notice = page.locator('.bn-status-slot')
  await expect(notice).toContainText('changed since this screen read it')

  /* AND A CONFLICT IS THE ONE REFUSAL ON THIS SCREEN WITH SOMEWHERE TO GO. The button says what
     it costs rather than presenting a re-read as free: whatever is typed and unsaved goes. */
  await expect(
    notice.getByRole('button', { name: /Read the file again, losing what is unsaved/ }),
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
  const before = (await page.locator('.pricing-bar-says').innerText()).match(/(\d+) cop/)
  const copiesBefore = Number(before?.[1])
  expect(Number.isFinite(copiesBefore)).toBe(true)

  await field.fill('2')
  /* THE DECK FOLLOWS THE FIELD, before anything is pressed: one fewer copy would go, and the
     sentence says a card is at a figure typed by hand — which is the account the operator reads
     before deciding to press. */
  await expect(page.locator('.pricing-bar-says')).toContainText(`${copiesBefore - 1} cop`)
  await expect(page.locator('.pricing-bar-says')).toContainText('1 at a quantity you typed')

  await sendPress(page).click()
  await expect.poll(() => sendPosts(wire).length).toBe(1)
  const body = sendPosts(wire)[0]?.body as Record<string, unknown>
  expect(body.quantities).toEqual({ '9191210': 2 })

  /* SPENT BY THE SEND. A figure that survived the press would send the same copies again on
     the next one, on top of what went. */
  await expect(field).toHaveValue('')
})

test('a blank Qty on every row sends no quantities key at all', async ({ page }) => {
  const wire = await open(page, { worklist: SPAN })
  await sendPress(page).click()
  await expect.poll(() => sendPosts(wire).length).toBe(1)
  const body = sendPosts(wire)[0]?.body as Record<string, unknown>
  /* `in`, for the reason the cap's own case gave: a dropped key and a sent-empty key read the
     same to a value assertion, and only the first is the ordinary press. */
  expect('quantities' in body).toBe(false)
})

test('a figure past what can go is clamped on the way out, 0 takes the row out of the count, and Escape clears one row', async ({
  page,
}) => {
  await open(page, { worklist: SPAN })
  const leblanc = page.getByLabel(LEBLANC_QTY)
  const dunsparce = page.getByLabel(DUNSPARCE_QTY)
  const outBefore = (await page.locator('.pricing-bar-says').innerText()).match(/(\d+) cop/)
  const copiesBefore = Number(outBefore?.[1])

  /* CLAMPED, NOT REFUSED: the server would name "asked 9, only 3 can go"; the screen does not
     draw a send that cannot happen. */
  await leblanc.fill('9')
  await leblanc.press('Tab')
  await expect(leblanc).toHaveValue('3')

  /* ZERO IS A REAL ANSWER and the row leaves the count of rows that would go, without a hold. */
  await leblanc.fill('0')
  await expect(page.locator('.pricing-bar-says')).toContainText(`${copiesBefore - 3} cop`)
  await expect(page.locator('.pricing-bar-says')).toContainText('1 at a quantity you typed')

  /* ESCAPE PUTS ONE ROW BACK, the way it puts a price field back. */
  await leblanc.focus()
  await leblanc.press('Escape')
  await expect(leblanc).toHaveValue('')
  await expect(page.locator('.pricing-bar-says')).toContainText(`${copiesBefore} cop`)
  await expect(dunsparce).toHaveValue('')
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
  await expect(page.getByRole('button', { name: 'Clear typed prices' })).toBeDisabled()
})

test('the sheet leads with the worklist, and the label carries the figure', async ({ page }) => {
  await open(page, { skus: CLEAR_ROWS, clearable: CLEARABLE })
  await page.getByRole('button', { name: 'Clear typed prices' }).click()

  const sheet = page.getByRole('dialog', { name: 'Clear typed prices' })
  await expect(sheet).toBeVisible()

  /* THE NARROW SCOPE IS SELECTED. The corpus is one file for the whole store (D86), so
     "everywhere" is the shape this act naturally has and is exactly why it may not be what a
     press lands on by default. */
  await expect(sheet.getByRole('button', { name: /On this list/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  /* AND THE FIGURE IS IN THE BUTTON, NOT IN A TOOLTIP. Four clearable answers, all four on
     this worklist, no window — the button says four. */
  await expect(sheet.getByRole('button', { name: /^(Clear \d+|Nothing to clear)/ })).toContainText(
    'Clear 4 typed prices',
  )
})

test('what the clear leaves alone is on the screen, not in a tooltip', async ({ page }) => {
  await open(page, { skus: CLEAR_ROWS, clearable: CLEARABLE })
  await page.getByRole('button', { name: 'Clear typed prices' }).click()

  /* THE HOLDS AND THE UNPRICED ROWS ARE NAMED BY COUNT. An operator asking "does this touch my
     holds" has to be able to answer it without pressing anything — D49's holds carry a reason
     and a watch, and removing one puts the card back into the next emit. */
  const spares = page.locator('.clearprices-spares')
  await expect(spares).toContainText('2')
  await expect(spares).toContainText('held back on purpose')
  await expect(spares).toContainText('no market price')
})

/* NO TYPED MIDDLE DOT OR BULLET REACHES THE MASS-CLEAR SHEET (D218). The eyebrow, both
 * numbered steps and the Segmented control's own two option labels are drawn by CSS now. */
test('no typed middle dot or bullet reaches the mass-clear sheet (D218)', async ({ page }) => {
  /* SEVERAL RUNS, ON PURPOSE. Over one run this sheet's `worklistName` reuses `scopeName`,
     which composes through `runScope.ts:boxLabel` — `Box 7 · Riftbound epics` — a typed dot
     in a file outside this sweep's lane; see the sweep's own report. Over several runs
     `worklistName` falls to "N runs" instead, which keeps this case about the sites this lane
     fixed rather than about that one. */
  await open(page, { worklist: SPAN, clearable: CLEARABLE })
  await page.getByRole('button', { name: 'Clear typed prices' }).click()

  const sheet = page.getByRole('dialog', { name: 'Clear typed prices' })
  await expect(sheet).toBeVisible()
  const text = await sheet.innerText()
  expect(text).not.toMatch(/[·•]/)
})

test('an age window narrows the label, and never takes an undated answer', async ({ page }) => {
  await open(page, { skus: CLEAR_ROWS, clearable: CLEARABLE })
  await page.getByRole('button', { name: 'Clear typed prices' }).click()
  const sheet = page.getByRole('dialog', { name: 'Clear typed prices' })
  const press = sheet.getByRole('button', { name: /^(Clear \d+|Nothing to clear)/ })

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
  await expect(page.locator('.clearprices-spares')).toContainText('with no date')

  /* A WINDOW THAT SELECTS NOTHING SAYS SO AND REFUSES THE PRESS, rather than offering a
     button that does nothing. */
  await sheet.locator('.clearprices-age', { hasText: '14+ days' }).click()
  await expect(press).toContainText('Nothing to clear')
  await expect(press).toBeDisabled()
})

test('the scope the operator chose is the scope that travels', async ({ page }) => {
  const wire = await open(page, { skus: CLEAR_ROWS, clearable: CLEARABLE })
  await page.getByRole('button', { name: 'Clear typed prices' }).click()
  const sheet = page.getByRole('dialog', { name: 'Clear typed prices' })

  /* THE WORKLIST SCOPE SENDS SKUS. This is the assertion the whole sheet exists for: the
     press an operator makes while looking at one run's rows must not reach the rest of the
     store, and the only thing that makes that true on the wire is this list. */
  await sheet.getByRole('button', { name: /^(Clear \d+|Nothing to clear)/ }).click()
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
  await page.getByRole('button', { name: 'Clear typed prices' }).click()
  const sheet = page.getByRole('dialog', { name: 'Clear typed prices' })

  await sheet.getByRole('button', { name: /Everywhere/ }).click()
  /* THE BLAST RADIUS IS IN THE LABEL AND IN A SENTENCE BESIDE IT. "Clear" over four hundred
     answers is the ambush this sheet exists to prevent. */
  await expect(sheet.getByRole('button', { name: /^(Clear \d+|Nothing to clear)/ })).toContainText(
    'everywhere',
  )
  await expect(sheet.locator('.clearprices-scope-says')).toContainText('Every run and box at once')

  await sheet.getByRole('button', { name: /^(Clear \d+|Nothing to clear)/ }).click()
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

  await page.getByRole('button', { name: 'Clear typed prices' }).click()
  await page.getByRole('dialog', { name: 'Clear typed prices' }).getByRole('button', { name: /^(Clear \d+|Nothing to clear)/ }).click()

  /* THE FIELD GOES BACK TO THE SUGGESTION. The row is not removed and nothing else moves —
     a press changes what is on the screen, never where the rest of it is (D118). */
  await expect(field).toHaveValue('')
  await expect(page.getByRole('dialog', { name: 'Clear typed prices' })).toHaveCount(0)

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
  await page.getByRole('button', { name: 'Clear typed prices' }).click()
  await expect(page.getByRole('dialog', { name: 'Clear typed prices' }).getByRole('button', { name: /^(Clear \d+|Nothing to clear)/ })).toContainText(
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
  await page.getByRole('button', { name: 'Clear typed prices' }).click()
  await expect(page.getByRole('dialog', { name: 'Clear typed prices' }).getByRole('button', { name: /^(Clear \d+|Nothing to clear)/ })).toBeDisabled()
  await expect(page.getByRole('dialog', { name: 'Clear typed prices' })).toContainText('Wait for your last price')
})

/* ============================================================================================
   UX-002 (S1) + UX-073: THE "LISTS AT" FIELD, AT DESK WIDTH.
 *
 * THE DEFECT, MEASURED: `.pricing-row` and `.pricing-caption` are one flat grid
 * (`.pricing-facts { display: contents }` in `Pricing.css`), and `--pricing-cols` reserves a
 * FIXED track count for the SNAPS ref columns Compare draws (one off, up to four on). With
 * Compare off — the screen's own default — only the Market column renders, so grid
 * auto-placement filled the price and actions tracks with the SPARE 68px tracks meant for a
 * Low/+Ship column nobody drew, and the real 132px track sat empty at the end. Verified
 * directly against `origin/main`'s CSS on this checkout's own dev server before this file
 * changed: `.pricing-input` measured 8.53px wide and 13.11 read as "$1" — the finding's own
 * repro, to the pixel. `Pricing.css` now anchors `.pricing-price` and `.pricing-actions` (and
 * the caption's matching cells) to the grid's LAST TWO LINES, so the child count stops
 * mattering.
 *
 * "LEGIBLE" IS MEASURED, NOT SCREENSHOTTED: `scrollWidth > clientWidth` is a real input
 * element clipping its own value — the same fact a person reads as "$1" instead of "$13.11".
 * `toHaveValue` alone would not have caught the original defect: the DOM value was always the
 * full string, typed or committed: only the box around it was too narrow to show it.
 *
 * THE GRID VARIANTS: data-trends and data-direct only vary `--pricing-cols`' track COUNT at
 * the table tier (>= roughly 940px of the row's own container, which this checkout's shell
 * measures at a 1440px viewport with the sidebar open — see the container-width figures this
 * case's own comments below were measured against). Below that the compact and card tiers
 * (`Pricing.css`'s own "TIERS" block) replace the grid with a fixed, explicit layout that does
 * not read `--pricing-cols` at all, which is why the finding itself reports 820 and 390 as
 * already correct. `data-copies='none'` is the fourth variant named in the lane's own brief;
 * it belongs to `pricing-markdown.spec.ts` and not here — that file's own header states "its
 * own file, and pricing.spec.ts is not touched" as the property that keeps the run-source path
 * byte-identical, and `data-copies` never varies within a run-sourced screen. The markdown-lens
 * width case lives beside it.
 * ============================================================================================ */

const LONG_PRICE = '1234.56'

/** No horizontal clipping: the content a real typed value needs (`scrollWidth`) fits inside
 *  what the box actually shows (`clientWidth`). This is what "$1" for "13.11" measures as —
 *  `toHaveValue` reads the same full string either way, so it cannot see this on its own. */
async function legible(input: Locator): Promise<void> {
  const clipped = await input.evaluate((el: HTMLInputElement) => el.scrollWidth > el.clientWidth + 1)
  expect(clipped).toBe(false)
}

/** Types a long price into the first row's field and reads it back in full at three moments:
 *  the row's OWN typed answer on arrival (before any edit), mid-edit while still focused
 *  (during), and once more after the blur commits it — a field that only grows on focus would
 *  pass the middle check and fail the first or the last. */
async function typeAndCheck(page: Page): Promise<void> {
  const input = field(page).first()
  await expect(input).toBeVisible()
  await legible(input) // before: whatever answer the row already carries
  await input.fill(LONG_PRICE)
  await expect(input).toHaveValue(LONG_PRICE)
  await legible(input) // during: focused, freshly typed, not yet committed
  await input.blur()
  await expect(input).toHaveValue(LONG_PRICE)
  await legible(input) // after: committed
}

/* ONE `open()` PER TEST, NOT TWO. A second `open()` against the same `#/pricing?run=…` hash
   is a same-document navigation — the SPA never remounts, `picked`/`stamp` do not change, and
   the effect that re-fetches never re-fires, so the second fixture is dead on arrival and the
   first render is asserted twice under a different name. Caught by this file's own DEBUG
   check before it shipped: a single `open()` with the direct-carrying fixture drew
   `data-direct='some'` correctly; the double-open version of the same case drew 'none' every
   time. Two variants, two tests. */
test('the "Lists at" field reads a long price in full at 1440, data-direct=none', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })

  /* No row in this fixture carries a Direct figure — the default shape `sku()` already
     builds. An existing typed answer seeds the "before" state. */
  await open(page, {
    decisions: { rule: 'match', basis: 'market', sub_threshold: null, overrides: { '8608859': '9876.54' } },
  })
  await expect(page.locator('.pricing-caption')).toBeVisible() // table tier, or this case proves nothing
  await typeAndCheck(page)

  /* LOADING TRENDS LAYS NOTHING OUT AGAIN (UX-070): the column is always reserved. */
  await loadTrends(page).click()
  await expect(strip(page).first().locator('svg')).toHaveCount(2)
  await typeAndCheck(page)
})

/* THE VIEWPORT IS SET BEFORE `open()`, NOT AFTER, and each width is its OWN test rather than
   one test resizing a single page five times in a row. The sidebar's rail state is read once
   at mount and then only from a live `matchMedia` listener (`App.tsx`) — resizing a page that
   already loaded wide can leave it open a beat longer than a fresh load at the same width
   would, which measured as a FALSE PASS at 820 during this case's own development: the stale
   open sidebar left the row more room than the width will actually give a person who arrives
   there. A fresh `open()` per width is what this file's own `open()` already assumes — see
   its own comment on why two navigations to the same hash do not even re-fetch. */
for (const width of [1024, 820, 720, 390, 360]) {
  test(`the "Lists at" field reads a long price in full at ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await open(page, {
      decisions: { rule: 'match', basis: 'market', sub_threshold: null, overrides: { '8608859': '9876.54' } },
    })
    await typeAndCheck(page)
  })
}

/* ---- UX-073: the focus ring is measured, not screenshotted -------------------------------------- */

/** `getComputedStyle` on a border returns an `rgb()` string; `--bn-accent` is a hex token. A
 *  probe element's own computed `color` is the browser's own conversion of the SAME token, in
 *  the SAME theme, so this compares like with like rather than a hand-copied rgb() literal that
 *  would silently stop meaning anything the day the token's value moves. */
async function accentRGB(page: Page): Promise<string> {
  return page.evaluate(() => {
    const probe = document.createElement('div')
    probe.style.color = 'var(--bn-accent)'
    document.body.appendChild(probe)
    const rgb = getComputedStyle(probe).color
    probe.remove()
    return rgb
  })
}

test('the focus ring on a TYPED price field is --bn-accent, not the halo alone (UX-073)', async ({
  page,
}) => {
  /* A TYPED ANSWER, NOT A SUGGESTION — the finding's own case, and the one the two-class
     `.pricing-price[data-answer='typed'] .pricing-field` rule outranked. `[data-answer='suggested']`
     had its own focus-within override already and was never broken. */
  await open(page, {
    decisions: { rule: 'match', basis: 'market', sub_threshold: null, overrides: { '8608859': '4.50' } },
  })
  const typedRow = page.locator(".pricing-price[data-answer='typed']").first()
  await expect(typedRow, 'the fixture answered this row, or the case proves nothing').toHaveCount(1)

  const input = field(page).first()
  await input.click()
  /* `.pricing-field`'s `border-color` EASES over `--bn-t-fast` (120ms). Read right after the
     click, the computed style is mid-transition — measured once as `rgb(122, 131, 153)`,
     neither the grey start nor the accent end. `settleMotion` (`motionSettled.ts`) is the
     same wait this file already uses before reading a position out of a moving page. */
  await settleMotion(page)

  const accent = await accentRGB(page)
  const border = await page
    .locator(".pricing-price[data-answer='typed'] .pricing-field")
    .first()
    .evaluate((el) => getComputedStyle(el).borderColor)
  expect(border, `the typed field's focused border is ${border}, not the accent ${accent}`).toBe(accent)
})

/* ============================================================================================
   THE RE-INTERVIEW (D277): one list with the rows that need the owner on top, one slim bar,
   the rule on one line, the drawer folded into the product view. The cases above keep the send,
   the save loop, the hold and the clear; these are the new shape.
   ============================================================================================ */

test('the screen is on its own route, on the kit page, and draws the run it was linked to', async ({ page }) => {
  await open(page)
  await expect(page.locator(`${VIEW} h1`)).toHaveText('Pricing')
  await expect(page.locator('.pricing-row')).toHaveCount(1)
  /* THE SLIM BAR IS THE VERDICT (D277, Q4): what is ready, in one sentence, beside the press. */
  await expect(page.locator('.pricing-bar-says')).toHaveText('3 copies ready')
  /* THE RULE AND THE CUT-OFF ARE ONE LINE (Q5), and the figure is stated once. */
  const line = page.locator('.pricing-rule-line')
  await expect(line).toContainText('New cards list at market')
  await expect(line.locator('.bn-money')).toHaveText('$0.40')
  await expect(line.getByRole('button', { name: 'Change' })).toBeVisible()
})

test('the rows that need the owner come first, each with its reason, and the rest by value', async ({ page }) => {
  await open(page, {
    skus: [
      sku({ sku: '1', name: 'Cheap on the cut-off', snap: { market: '0.30', direct_low: null, low: '0.20', low_with_shipping: '1.20', now: null }, bucket: 'sub_threshold' }),
      sku({ sku: '2', name: 'Ordinary', snap: { market: '2.00', direct_low: null, low: '1.80', low_with_shipping: '2.80', now: null } }),
      sku({ sku: '3', name: 'Drifted', snap: { market: '1.00', direct_low: null, low: '0.90', low_with_shipping: '1.90', now: null } }),
      sku({ sku: '4', name: 'Dear', snap: { market: '12.00', direct_low: null, low: '11.00', low_with_shipping: '12.50', now: null } }),
      sku({ sku: '5', name: 'Unpriced', bucket: 'no_market_data', snap: { market: null, direct_low: null, low: null, low_with_shipping: null, now: null } }),
    ],
    decisions: {
      rule: 'match',
      basis: 'market',
      threshold: '0.49',
      sub_threshold: { flat: '0.49' },
      overrides: { '1': '0.49', '3': '2.00' },
    },
  })

  /* Q2's three reasons, and the order: no market price first, then by value. The card at the
     cut-off is the floor at work, not a drift, so it is not flagged (the call in the decision
     entry). */
  await expect(page.locator('.pricing-group-head .pricing-group-why')).toHaveText(['Needs you', 'Ready'])
  await expect(page.locator('.pricing-group').nth(0).locator('.pricing-name')).toHaveText(['Unpriced', 'Dear', 'Drifted'])
  await expect(page.locator('.pricing-group').nth(1).locator('.pricing-name')).toHaveText(['Ordinary', 'Cheap on the cut-off'])
  const flags = page.locator('.pricing-group').nth(0).locator('.pricing-flag')
  await expect(flags.nth(0)).toHaveText('No market price')
  await expect(flags.nth(1)).toHaveText('Worth $5.00 or more')
  await expect(flags.nth(2)).toHaveText('Your price is 100% over market')
  await expect(page.locator('.pricing-group').nth(1).locator('.pricing-flag')).toHaveCount(0)
  /* THE BAR NAMES WHAT STAYS BACK (Q3). */
  await expect(page.locator('.pricing-bar-says')).toContainText('1 needs a price')
  /* AND ITS COPIES ARE NOT READY (the delta review, R3-1): four rows of three copies go, the
     unpriced row's three do not. The bar and the press both say twelve, which is what the file
     will carry. */
  await expect(page.locator('.pricing-bar-says')).toContainText('12 copies ready')
  await expect(sendPress(page)).toHaveText('Send 12 copies to TCGplayer')
})

test('a price typed far from market gives the row its flag, and the row does not move', async ({ page }) => {
  await open(page, {
    skus: [
      sku({ sku: '1', name: 'First', snap: { market: '3.00', direct_low: null, low: '2.80', low_with_shipping: '3.80', now: null } }),
      sku({ sku: '2', name: 'Second', snap: { market: '2.00', direct_low: null, low: '1.80', low_with_shipping: '2.80', now: null } }),
    ],
  })
  await expect(page.locator('.pricing-name')).toHaveText(['First', 'Second'])
  const second = page.getByRole('textbox', { name: 'Price for Second' })
  await second.focus()
  await page.keyboard.type('9.00')
  await second.blur()
  /* THE CHIP APPEARS ON THE ROW; THE ORDER WAS TAKEN ON ARRIVAL (D118, D181). */
  await expect(page.locator('.pricing-row').nth(1).locator('.pricing-flag')).toHaveText('Your price is 350% over market')
  await expect(page.locator('.pricing-name')).toHaveText(['First', 'Second'])
  await expect(page.locator('.pricing-group-head')).toHaveCount(0)
})

test('a hold taken now keeps its row where it is, and so does the next load', async ({ page }) => {
  const skus = [
    sku({ sku: '1', name: 'Articuno', snap: { market: '3.00', direct_low: null, low: '2.80', low_with_shipping: '3.80', now: null } }),
    sku({ sku: '2', name: 'Dunsparce', snap: { market: '2.00', direct_low: null, low: '1.80', low_with_shipping: '2.80', now: null } }),
    sku({ sku: '3', name: 'Wattrel', snap: { market: '1.00', direct_low: null, low: '0.80', low_with_shipping: '1.80', now: null } }),
  ]
  await open(page, { skus })
  await page.getByRole('button', { name: 'Hold back Dunsparce' }).click()
  await page.getByRole('button', { name: /Keeping this one/ }).click()
  await page.getByRole('button', { name: 'Hold it' }).click()
  await expect(page.locator('.pricing-row').nth(1).locator('.pricing-state')).toHaveAttribute('title', 'withheld: keeping')
  await expect(page.locator('.pricing-name')).toHaveText(['Articuno', 'Dunsparce', 'Wattrel'])
  /* A HELD ROW IS RANKED BY VALUE LIKE EVERY OTHER (UX-071): it does not sink on the reload. */
  await page.route(/\/pricing$/, async (route) => {
    if (route.request().method() === 'PUT') return route.fallback()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        corpus: { version: 1, policy: { rule: 'match', basis: 'market', sub_threshold: { flat: '0.49' } }, skus: { '2': { value: { withheld: 'keeping' } } } },
        path: '/tmp/prices.json',
        revision: 'rev-1',
      }),
    })
  })
  await page.reload()
  await settleFonts(page)
  await expect(page.locator('.pricing-name')).toHaveText(['Articuno', 'Dunsparce', 'Wattrel'])
})

test('Held shows only the held rows, and its count is the bar’s count', async ({ page }) => {
  await open(page, {
    skus: [sku({ sku: '1', name: 'Articuno' }), sku({ sku: '2', name: 'Dunsparce' })],
    decisions: { rule: 'match', basis: 'market', overrides: { '2': { withheld: 'bullish' } } },
  })
  await expect(page.locator('.pricing-bar-says')).toContainText('1 held')
  const held = page.getByRole('button', { name: 'Held 1' })
  await held.click()
  await expect(held).toHaveAttribute('aria-pressed', 'true')
  await expect(page.locator('.pricing-name')).toHaveText(['Dunsparce'])
  await held.click()
  await expect(page.locator('.pricing-row')).toHaveCount(2)
})

test('every control that answers a row is on the row, and the caption shares its tracks', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await open(page)
  await expect(field(page)).toBeVisible()
  await expect(page.locator('.pricing-row .pricing-hold')).toBeVisible()
  /* MARKET AND LOWEST ARE ON EVERY DESK ROW (the Compare toggle is gone). */
  await expect(page.locator('.pricing-row .pricing-col-market')).toContainText('$22.03')
  await expect(page.locator('.pricing-row .pricing-col-low')).toContainText('$21.98')
  await expect(page.getByRole('button', { name: 'Compare' })).toHaveCount(0)
  const [row, caption] = await Promise.all([
    page.locator('.pricing-row').first().evaluate((el) => getComputedStyle(el).gridTemplateColumns),
    page.locator('.pricing-caption').first().evaluate((el) => getComputedStyle(el).gridTemplateColumns),
  ])
  expect(row).toBe(caption)
})

test('Undo has a fixed place, and U undoes from anywhere on the screen', async ({ page }) => {
  const wire = await open(page)
  const undo = page.getByRole('button', { name: 'Undo' })
  /* DRAWN BEFORE THE FIRST WRITE, AND DISABLED (UX-135): the first answer moves nothing. */
  await expect(undo).toBeDisabled()
  const before = await undo.boundingBox()
  await field(page).focus()
  await page.keyboard.type('12.00')
  await page.keyboard.press('Enter')
  await expect.poll(() => sentAnswers(wire)['8608859']).toBe('12.00')
  await expect(undo).toBeEnabled()
  expect(await undo.boundingBox()).toEqual(before)
  /* U OUTSIDE ANY FIELD (UX-075): the key the tooltip names works where it says. */
  await page.locator(`${VIEW} h1`).click()
  await page.keyboard.press('u')
  await expect.poll(() => sentAnswers(wire)).toEqual({})
})

test('finding #2 (the Opus review round) — a hold toast\'s own Undo reverses that hold, never whatever a newer answer put on top', async ({
  page,
}) => {
  const skus = [
    sku({ sku: '1', name: 'Articuno', snap: { market: '3.00', direct_low: null, low: '2.80', low_with_shipping: '3.80', now: null } }),
    sku({ sku: '2', name: 'Dunsparce', snap: { market: '2.00', direct_low: null, low: '1.80', low_with_shipping: '2.80', now: null } }),
  ]
  const wire = await open(page, { skus })

  await page.getByRole('button', { name: 'Hold back Dunsparce' }).click()
  await page.getByRole('button', { name: /Keeping this one/ }).click()
  await page.getByRole('button', { name: 'Hold it' }).click()
  const holdToast = page.locator('.bn-toast', { hasText: 'Held Dunsparce' })
  await expect(holdToast).toBeVisible()

  /* A NEWER WRITE LANDS ON TOP OF THE STACK — the old code's toast called whatever `undoLast`
   * held by press time, which by then would be THIS one, not the hold it named. */
  await page.getByLabel('Price for Articuno').fill('9.00')
  await page.getByLabel('Price for Articuno').press('Enter')
  await expect.poll(() => sentAnswers(wire)['1']).toBe('9.00')

  await holdToast.getByRole('button', { name: 'Undo' }).click()

  /* THE HOLD IS GONE. THE NEWER ANSWER STANDS. */
  await expect(page.locator('.pricing-row', { hasText: 'Dunsparce' }).locator('.pricing-state')).toHaveCount(0)
  await expect.poll(() => sentAnswers(wire)['1']).toBe('9.00')
})

test('finding #6 (the Opus review round) — Enter commits once, not twice on the blur it triggers', async ({
  page,
}) => {
  /* THE PUT ITSELF DEBOUNCES, so two `onCommit` calls in one tick would coalesce into one
   * network write regardless — the visible symptom is the TOAST, which does not debounce:
   * the old code fired `onCommit` from Enter, then again from the blur Enter itself
   * triggers, stacking two "Cut-off changed" toasts for one keystroke. */
  await open(page)
  await page.getByRole('button', { name: 'Change' }).click()
  const cut = page.getByLabel('Cut-off', { exact: true })
  await cut.fill('0.45')
  await cut.press('Enter')
  await expect(page.locator('.bn-toast', { hasText: 'Cut-off changed' })).toHaveCount(1)
})

test('finding #9/#15 (the Opus review round) — a cut-off change gets its own "Cut-off changed" toast, with Undo', async ({
  page,
}) => {
  const wire = await open(page)
  await page.getByRole('button', { name: 'Change' }).click()
  const cut = page.getByLabel('Cut-off', { exact: true })
  await cut.fill('0.45')
  await cut.press('Enter')
  await expect.poll(() => sentPolicy(wire).threshold).toBe('0.45')

  const cutToast = page.locator('.bn-toast', { hasText: 'Cut-off changed' })
  await expect(cutToast).toBeVisible()
  await cutToast.getByRole('button', { name: 'Undo' }).click()
  await expect(cut).toHaveValue('0.40')
})

test('finding #11 (the Opus review round) — `U` still undoes a minute later, off the shared hook rather than a second copy', async ({
  page,
}) => {
  /* Pricing used to reimplement the whole window listener itself (`kit/undo.ts`'s own
   * comment: "a screen that still binds `U` itself is what `make kit-adoption` fails").
   * `useUndoHotkey` reads no clock, so this is the same proof `review.spec.ts`,
   * `fulfillment.spec.ts` and `orders.spec.ts` already carry, here too. */
  await page.clock.install()
  const wire = await open(page)
  await field(page).focus()
  await page.keyboard.type('12.00')
  await page.keyboard.press('Enter')
  await expect.poll(() => sentAnswers(wire)['8608859']).toBe('12.00')

  await page.clock.runFor(60_000)
  await page.locator(`${VIEW} h1`).click()
  await page.keyboard.press('u')
  await expect.poll(() => sentAnswers(wire)).toEqual({})
})

test('the rule sheet writes the cut-off to both keys, and says how many cards it splits', async ({ page }) => {
  const wire = await open(page, {
    skus: [
      sku({ sku: '1', bucket: 'sub_threshold', snap: { market: '0.12', direct_low: null, low: '0.10', low_with_shipping: '1.10', now: null } }),
      sku({ sku: '2', bucket: 'sub_threshold', snap: { market: '0.37', direct_low: null, low: '0.30', low_with_shipping: '1.30', now: null } }),
      sku({ sku: '3', bucket: 'listable', snap: { market: '0.41', direct_low: null, low: '0.38', low_with_shipping: '1.38', now: null } }),
    ],
  })
  await page.getByRole('button', { name: 'Change' }).click()
  const sheet = page.getByRole('dialog', { name: 'Pricing rule' })
  /* THE SERVER'S OWN FIGURE FOR A STORE THAT NEVER SET ONE (D99): $0.40, not a prettier default. */
  const cut = sheet.getByLabel('Cut-off', { exact: true })
  await expect(cut).toHaveValue('0.40')
  await expect(sheet.locator('.pricing-cheap-caption')).toContainText('2 under, 1 above')
  await cut.fill('0.45')
  await cut.press('Enter')
  await expect(sheet.locator('.pricing-cheap-caption')).toContainText('3 under, 0 above')
  await expect.poll(() => wire.filter((r) => r.method === 'PUT').length).toBeGreaterThan(0)
  /* ONE FIGURE, BOTH KEYS (the owner, 2026-09-03). */
  expect(sentPolicy(wire).threshold).toBe('0.45')
  expect(sentPolicy(wire).sub_threshold).toEqual({ flat: '0.45' })
})

test('a product name opens the one product view, and T opens it from the keyboard', async ({ page }) => {
  await page.route(/\/pipeline\/products\/[^/]+\/history$/, async (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ sku: '8608859', name: 'Articuno - 161/159', set_name: 'SV: Prismatic Evolutions', condition: 'Near Mint Holofoil', source: 'archive', history_begins: null, never_sold: true, ranges: [] }),
    }),
  )
  await page.route(/\/orders$/, async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: '{"orders":[]}' }))
  await page.route(/\/search\?/, async (route) => route.fulfill({ status: 200, contentType: 'application/json', body: '{"query":"","groups":[]}' }))
  await open(page)
  /* THE DRAWER FOLDED INTO THE PRODUCT VIEW (D278): the name is the door, by SKU. */
  await page.locator('.pricing-name').first().click()
  const sheet = page.getByRole('dialog', { name: 'Articuno - 161/159' })
  await expect(sheet).toBeVisible()
  await expect(sheet.getByRole('button', { name: 'Open as page' })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(sheet).toHaveCount(0)
  await field(page).focus()
  await page.keyboard.press('t')
  await expect(sheet).toBeVisible()
})

test('the slim bar stays at the top of the column while the list scrolls', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await open(page, {
    skus: Array.from({ length: 24 }, (_, at) => sku({ sku: String(1000 + at), name: `Card ${at}` })),
  })
  const bar = page.locator('.pricing-bar')
  const start = await bar.boundingBox()
  await page.mouse.move(700, 600)
  await page.mouse.wheel(0, 1200)
  await expect.poll(async () => (await page.locator('.pricing-row').first().boundingBox())?.y ?? 0).toBeLessThan(0)
  const after = await bar.boundingBox()
  /* STICKY AT THE TOP (Q4): the bar is still on screen, at the top edge of the column. */
  expect(after?.y ?? -1).toBeGreaterThanOrEqual(-1)
  expect(after?.y ?? 999).toBeLessThan(start?.y ?? 0)
  expect(after?.y ?? 999).toBeLessThanOrEqual(8)
})

test('on a phone the bar is one line pinned above the tab bar, and More opens the doors', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await open(page)
  const bar = page.locator('.pricing-bar')
  const box = await bar.boundingBox()
  const tabbar = await page.locator('.bn-tabbar').boundingBox()
  expect(box).not.toBeNull()
  /* ONE LINE (Q4): the press and More, and nothing wraps under them. */
  expect(box?.height ?? 999).toBeLessThanOrEqual(72)
  expect(Math.abs((box?.y ?? 0) + (box?.height ?? 0) - (tabbar?.y ?? 0))).toBeLessThanOrEqual(1)
  await expect(page.getByRole('button', { name: /^Download/ })).toBeHidden()
  await page.getByRole('button', { name: 'More send options' }).click()
  await expect(page.getByRole('button', { name: /^Download/ })).toBeVisible()
  const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  expect(over).toBeLessThanOrEqual(0)
})

test('Write the file keeps its words and its place while it writes', async ({ page }) => {
  const wire = await open(page, { sendDelayMs: 1500 })
  await page.getByRole('button', { name: /^Download (the file instead|file)$/ }).click()
  const press = page.getByRole('button', { name: 'Write the file' })
  const before = await press.boundingBox()
  await press.click()
  await expect(press).toHaveAttribute('data-busy', 'true')
  await expect(press).toHaveText('Write the file')
  const during = await press.boundingBox()
  for (const side of ['x', 'y', 'width', 'height'] as const) {
    expect(Math.abs((during?.[side] ?? 0) - (before?.[side] ?? 0)), side).toBeLessThanOrEqual(0.5)
  }
  await expect.poll(() => sendPosts(wire).length).toBe(1)
})

test('the 25% edge is exact: 25% away needs the owner, 24.5% does not, on either side', async ({ page }) => {
  /* Q2 SAYS "25% OR MORE". A ROUNDED PERCENTAGE TREATED THE TWO SIDES UNEVENLY (the delta review,
     R3-6): 24.5% over rounded up into the flag and 24.5% under rounded down out of it. */
  const at = (sku: string, name: string) =>
    ({ sku, name, snap: { market: '10.00', direct_low: null, low: '9.50', low_with_shipping: '10.50', now: null } }) as const
  await open(page, {
    skus: [
      sku(at('1', 'Over by 24.5')),
      sku(at('2', 'Under by 24.5')),
      sku(at('3', 'Over by 25')),
      sku(at('4', 'Under by 25')),
    ],
    decisions: { rule: 'match', basis: 'market', overrides: { '1': '12.45', '2': '7.55', '3': '12.50', '4': '7.50' } },
  })
  const flag = (name: string) => page.locator('.pricing-row', { hasText: name }).locator('.pricing-flag')
  /* A $10.00 CARD IS WORTH $5 OR MORE, so a row inside the band still carries that flag, and
     only the drift text tells the two cases apart. */
  await expect(flag('Over by 24.5')).toHaveText('Worth $5.00 or more')
  await expect(flag('Under by 24.5')).toHaveText('Worth $5.00 or more')
  await expect(flag('Over by 25')).toHaveText('Your price is 25% over market')
  await expect(flag('Under by 25')).toHaveText('Your price is 25% under market')
})

test('the keyboard sheet lists the keys the rows answer, and nothing the screen dropped', async ({ page }) => {
  await open(page)
  await page.locator(`${VIEW} h1`).click()
  await page.keyboard.press('?')
  const sheet = page.getByRole('dialog', { name: 'Keyboard shortcuts' })
  await expect(sheet).toBeVisible()
  /* THE SNAP KEYS ARE THE COLUMNS THE ROW DRAWS (m, l, and n on the Live tab), and T OPENS THE
     PRODUCT VIEW WITH ONE PRESS (the delta review, R3-4). */
  await expect(sheet).toContainText('Open the product view')
  await expect(sheet).toContainText('Snap the price to Lowest')
  await expect(sheet).not.toContainText('Low with shipping')
  await expect(sheet).not.toContainText('Direct low')
  await expect(sheet).not.toContainText('Hold to read')
})

/* THE REVIEWER'S STORE (the delta review, R4 F5): every row owes a price, so nothing is ready.
 * The press read "0 copies ready" and stayed live, and a press could only be refused. It is
 * disabled until a copy is ready. */
test('with nothing ready, the send press is disabled', async ({ page }) => {
  await open(page, {
    skus: [sku({ sku: '5', name: 'Unpriced', bucket: 'no_market_data', snap: { market: null, direct_low: null, low: null, low_with_shipping: null, now: null } })],
    decisions: { rule: 'match', basis: 'market', threshold: '0.49', sub_threshold: { flat: '0.49' }, overrides: {} },
  })
  await expect(page.locator('.pricing-bar-says')).toContainText('needs a price')
  await expect(page.locator('.send-press')).toBeDisabled()
})

/* THE CARD NUMBER IS WHAT THE OWNER READS (the delta review, R4), AND THE FACTS BESIDE IT KEEP
 * THEIR WIDTH (R6-1). At 390 a long box name cut the number off. The R4 fix shrank the copy
 * count and the cap note to nothing instead, leaving a loose separator. The line wraps now, and
 * each of the three is at least as wide as its own text, at 390 and at 820.
 *
 * AND THE LINE STAYS IN ITS COLUMN (R7 F1, F2, F3). The reviewer's long box name spilled 153px
 * into the price column at 390, "and 1 more" drew over the card number, and a wrap left a "·"
 * at a line end. Every part of the place line stays inside the card column, "and 1 more"
 * overlaps nothing beside it, and no part draws a separator glyph that a wrap can strand. */
const LONG_BOX = 'Riftbound Origins singles and Surging Sparks overflow'
for (const width of [390, 820]) {
  test(`at ${width} the place line keeps the card number, the copies and the cap note whole`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await open(page, {
      worklist: {
        runs: [{ run: RUN, box: 7, box_name: LONG_BOX, skus: 1 }],
        skus: [
          {
            ...sku({
              positions: [
                { box: 7, index: 107, label: `Box ${LONG_BOX}, Section 12, Card 107` },
                { box: 7, index: 108, label: `Box ${LONG_BOX}, Section 12, Card 108` },
              ],
              copies: 2,
              add_to_quantity: 1,
              /* R8-3: A LIVE COUNT WITH ITS SALES, "2 live (3 when read, 1 sold since)", which
                 ran 57px past the phone's card column. */
              listing: { pushed: 3, staged: 0, live: 3, sold_here: 1 },
            }),
            in: [{ run: RUN, add_to_quantity: 2 }],
            claimed_add: 2,
            over_cap: true,
          },
        ],
      },
    })
    const where = page.locator('.pricing-where').first()
    await expect(where.locator('.position-run-num')).toHaveText('107')
    const parts = await where.evaluate((el) => {
      const line = el.getBoundingClientRect()
      return ['.position-run-num', '.pricing-copies', '.pricing-cap'].map((selector) => {
        const node = el.querySelector(selector) as HTMLElement | null
        if (node === null) return { selector, found: false, width: 0, text: 0, right: 0, line: line.right }
        const box = node.getBoundingClientRect()
        return { selector, found: true, width: box.width, text: node.scrollWidth, right: box.right, line: line.right }
      })
    })
    for (const part of parts) {
      expect(part.found, `${part.selector} is drawn`).toBe(true)
      expect(part.width, `${part.selector} keeps its text width`).toBeGreaterThanOrEqual(part.text - 0.5)
      expect(part.right, `${part.selector} ends inside its line`).toBeLessThanOrEqual(part.line + 0.5)
    }

    const layout = await where.evaluate((el) => {
      const column = (el.closest('.pricing-id') as HTMLElement).getBoundingClientRect()
      const outside = [...el.querySelectorAll('*')]
        .map((node) => ({ node, box: node.getBoundingClientRect() }))
        .filter(({ box }) => box.width > 0 && (box.right > column.right + 0.5 || box.left < column.left - 0.5))
        .map(({ node, box }) => `${node.className || node.tagName} ${Math.round(box.left)}..${Math.round(box.right)}`)
      const more = el.querySelector('.pricing-more') as HTMLElement
      const mine = more.getBoundingClientRect()
      const overlaps = [...el.querySelectorAll('*')]
        .filter((node) => node !== more && !node.contains(more) && !more.contains(node))
        .filter((node) => {
          const box = node.getBoundingClientRect()
          const x = Math.min(box.right, mine.right) - Math.max(box.left, mine.left)
          const y = Math.min(box.bottom, mine.bottom) - Math.max(box.top, mine.top)
          return box.width > 0 && x > 0.5 && y > 0.5
        })
        .map((node) => String(node.className || node.tagName))
      const glyphs = [...el.querySelectorAll('*')]
        .flatMap((node) => ['::before', '::after'].map((pseudo) => getComputedStyle(node, pseudo).content))
        .filter((content) => content.includes('·'))
      return { outside, overlaps, glyphs, more: more.textContent }
    })
    expect(layout.more).toBe('and 1 more')
    await expect(where.locator('.pricing-live')).toContainText('2 live')
    expect(layout.outside, 'every part of the place line stays inside the card column').toEqual([])
    expect(layout.overlaps, '"and 1 more" overlaps nothing beside it').toEqual([])
    expect(layout.glyphs, 'no part draws a separator a wrap can strand').toEqual([])
  })
}

/* THE CHIP READS THE CODE, NEVER THE SENTENCE (the coordinator's ruling on R4): reworded
 * server words with the same codes draw the same chips. */
test('a reworded owed sentence draws the same chip while its code stays', async ({ page }) => {
  await open(page, {
    noRun: true,
    emitted: true,
    runs: [
      { run: '2026-08-24-box2-01', box: 2, box_name: 'Pokemon bulk', skus: 3, created_at: '2026-08-24T18:00:00+00:00' },
      { run: '2026-09-02-box6-01', box: 6, box_name: 'Riftbound rares', skus: 2, created_at: '2026-09-02T18:00:00+00:00' },
    ],
    unsent: { '2026-08-24-box2-01': 3, '2026-09-02-box6-01': 2 },
    owes: {
      '2026-08-24-box2-01': ['three cards still lack a market price'],
      '2026-09-02-box6-01': ['not written yet'],
    },
    owed: {
      '2026-08-24-box2-01': [{ code: 'needs_price', count: 3 }],
      '2026-09-02-box6-01': [{ code: 'never_emitted', count: null }],
    },
  })
  await page.getByRole('button', { name: /^(Every run|\d+ runs?)$/ }).click()
  const chips = page.locator('.pricing-run')
  await expect(chips.nth(0).locator('.pricing-run-owes')).toHaveText('Never sent')
  await expect(chips.nth(1).locator('.pricing-run-owes')).toHaveText('Sent, 3 need a price')
})
