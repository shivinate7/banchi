import { expect, test, type Page, type Route } from '@playwright/test'
import { CAPTURE_PORT, DEV_PORT } from '../devPort'

/* NOTHING IN THIS DIRECTORY MAY REACH THE CAPTURE SERVER, AND UNTIL THIS FILE EXISTED TEN
 * SPECS DID — WHICH TURNED OUT TO BE THE SMALL HALF.
 *
 * Every spec here stubs the routes ITS OWN SCREEN calls. The shell's reads belong to no
 * screen: `App.tsx:useServerPresence(chrome)` polls `GET /status` on mount, every fifteen
 * seconds and on every window focus, for every route but the Fulfiller's — so a file that
 * stubbed everything its screen asked for still missed it, and ten of them did.
 *
 * SEALING ALL SEVENTEEN FOUND SIX MORE FILES LEAKING SOMETHING ELSE, none of them the shell's:
 * `#/shipping` is the Ship stage of `OrdersHub` and was sending that hub's `/orders` and
 * `/inventory`; `Pricing.tsx:pumpCrops` POSTs `/pipeline/crop-preview` once per row it draws,
 * so seventy-one cases were sending a POST per row and measuring the UNCROPPED fallback the
 * failure left behind; the capture screen reads `/boxes` on mount rather than when the field
 * opens, which nineteen cases in `capture-claims` never stubbed; `nav` walked the ring past
 * `/pricing` and `/codes/lots`; `orders` stubbed `/inventory` only inside its boot branch; and
 * one `fulfillment` case navigates itself and stubbed only the half it was about. None of the
 * six was findable by reading — each was found by a catch-all naming it.
 *
 * WHAT AN UNSTUBBED READ ACTUALLY REACHES. `app/src/server.ts` composes its base as
 * `${location.protocol}//${location.hostname}:${CAPTURE_PORT}`, a DIFFERENT ORIGIN from the
 * Vite server the page came off. In the main checkout that port is answered by the owner's
 * real capture server over their real store, kept alive at login by `make launch-agent`. So
 * `cursor.spec.ts` read their boxes, their inventory and their run list; `gallery.spec.ts`
 * fetched four real card photographs onto the kit sheet; and every one of the ten polled
 * their `/status` for the life of every test. In a worktree, whose capture port has nothing
 * on it (D43), the same absence draws the shell's 44px offline banner above the view — which
 * is what failed `the box lives in the walk's column` and `answering a card costs no
 * scrolling` on 2026-09-05, as a bare pixel count that named neither the banner nor the
 * missing stub. A design floor whose verdict depends on a process outside the test is the
 * defect D43 exists about, one level up. `docs/DEBTS.md` carried this as its section 13 until
 * this file discharged it; the measurements are here and in `docs/map.py`'s entry now, which is
 * where a claim with a reader belongs.
 *
 * AND NOTHING HERE MAY REACH THE PUBLIC INTERNET EITHER, WHICH IS THE SECOND SEAL AND ARRIVED
 * THREE WEEKS LATER (D124, 2026-09-08). `sealCapture` matches on the capture PORT, so it was
 * blind by construction to the largest outside dependency this directory had: `app/index.html`
 * pulled Inter, Manrope and JetBrains Mono from `fonts.googleapis.com` on every page load, and
 * every test opens a fresh context — order a thousand round trips to a third party per
 * `make design-check` run, on the suite that decides whether the design floors hold. Nothing in
 * a ten-run survey was ever traced to it, and that is the point: with `&display=swap` a stalled
 * fetch DEGRADES a measurement instead of failing it, so a rate limit and a slow render are the
 * same red. `sealOutside` below refuses everything that is not this checkout's two ports; the
 * faces themselves are vendored into `app/src/fonts.css`.
 *
 * THE SEAL IS A CATCH-ALL THAT REFUSES, NOT A STUB THAT ANSWERS, and the difference is the
 * whole design. A shared handler that answered every route would make the traffic stop and
 * the ignorance permanent: a spec missing a stub would silently get the shared answer, and
 * nobody could tell a deliberate fixture from an accident. This one aborts and RECORDS, and
 * `sealEveryTest` asserts the record is empty when the test ends — so an unstubbed read is
 * named, by method and path, in the file that made it.
 *
 * `abort()` RATHER THAN A 503, because abort is exactly what a worktree's dead capture port
 * already produces: `server.ts:request()` raises `ServerError` with code `unreachable`, the
 * failure every screen already handles, and no screen in this app branches on the code. Sealing
 * therefore changes nothing a screen renders. The only new thing in the room is the report.
 *
 * AND NEVER `continue()` OR `fetch()`, WHICH THIS REPO HAS ALREADY PAID FOR ONCE.
 * `app/tests/orders.spec.ts` records it: a catch-all matched by PORT that forwarded also caught
 * `POST /orders/pull` — newest-first meant it shadowed the stub `open()` had installed — and
 * sent the write to the real capture server. A forwarding seal is strictly worse than no seal.
 *
 * THE ASSERTION IS IN `afterEach` AND NOT IN THE HANDLER, and that is not a style choice. An
 * `expect()` that throws inside a route handler rejects a promise nothing awaits: Playwright
 * reports it as an unhandled rejection, fails whichever test is current at that moment rather
 * than the one that made the request, and STOPS THE WORKER. The record survives all of that and
 * reports every leak in one list.
 *
 * THE ORDER OF REGISTRATION IS LOAD-BEARING. Playwright matches `page.route` handlers
 * NEWEST-FIRST — `playwright-core/lib/client/page.js` does `this._routes.unshift(...)` — so
 * the catch-all has to be registered FIRST to be the last resort. That is why `sealEveryTest`
 * installs a `beforeEach` rather than exporting something each spec calls inside its own
 * `open()`: hooks run before the test body, so the seal is always the oldest handler and
 * every stub a spec registers wins over it.
 *
 * WHICH IS ALSO THE ONE WAY THIS CAN FAIL SILENTLY, so it is checked rather than asked for.
 * `gallery`, `pull-confirm` and `brand` navigate INSIDE a `test.beforeEach` of their own, and
 * within one suite Playwright runs `beforeEach` hooks in DECLARATION order — so a
 * `sealEveryTest()` written below one of those would install the seal after the navigation it
 * was meant to catch, those requests would reach the real port unrecorded, and the assertion
 * would pass over an empty list. `make docs-audit`'s `spec seal` row requires the call to come
 * before the file's first `test.beforeEach(`.
 *
 * THE ANCHOR IS THAT HOOK AND NOT `page.goto(`, WHICH WOULD BE WRONG IN FOUR FILES. A spec's
 * `open()` helper is DEFINED above the seal call and RUNS inside the test body, long after
 * every hook has registered — `live-reconcile`, `markdown`, `pricing` and `run-panel` are all
 * shaped that way and all correct. Only a hook can register before the seal does.
 *
 * WHAT THE RECORD IS AND IS NOT. A request the browser started whose `route` event has not
 * crossed the wire when `afterEach` reads the list is not in it, so an empty roster is not a
 * proof that nothing leaked. THE ABORT IS THE GUARANTEE AND THE RECORD IS THE DIAGNOSTIC:
 * nothing can reach the real server whether or not it was named in time.
 *
 * THE LEAK RECORD IS KEYED BY `Page` IN A `WeakMap`, which is the one non-obvious line here,
 * and the tidier answer was declined for a reason worth stating. `test.extend` with an
 * `{ auto: true }` fixture needs no fixtures file and no config change — it would remove the
 * WeakMap and the ordering hazard together, because the after-phase is guaranteed to pair with
 * the before-phase. What it also removes is the CALL: every spec would import `test` from here
 * instead of from `@playwright/test`, and the seal would run invisibly. A guard that can
 * silently stop running is the failure `scripts/docs-audit.py:check_dispatch` exists about, and
 * `spec seal` can only read a call somebody can grep for. An explicit line beats a tidy one.
 */

/** Everything that reached the capture port on this page, in order, as `GET /status`. */
const leaked = new WeakMap<Page, string[]>()

/** Everything that tried to leave this machine on this page, in order, as `GET https://…`. */
const escaped = new WeakMap<Page, string[]>()

/** This checkout's capture server, whatever hostname the page was opened at.
 *
 *  A RegExp RATHER THAN A GLOB, and the glob it replaces was misleading rather than wrong:
 *  Playwright treats `**` as a deep wildcard only when the next character is `/` or the end of
 *  the pattern, so `**://*:PORT/**` compiles to exactly what `*://*:PORT/**` does. Every other
 *  route in this directory is a RegExp; this one being a glob was the odd one out, and glob
 *  semantics have moved once already (`*` stopped crossing `/` in 1.53).
 *
 *  THE HOST IS A WILDCARD BECAUSE `server.ts` FOLLOWS THE ADDRESS BAR — it composes its base
 *  from `location.hostname`, so the same page opened at `pkmnscan.lan` asks a different host on
 *  the same port. The PORT is what identifies the capture server, and `devPort.ts` derives it
 *  from this checkout alone (D43). */
const CAPTURE_ORIGIN = new RegExp(`^[a-z+.-]+://[^/]+:${CAPTURE_PORT}(/|$)`)

/** An inline SVG, the same answer every spec here already serves for `/photo/<box>/<index>`.
 *  A photograph is never fetched from a store in this directory — see the header. */
const PHOTO_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="60" height="84" viewBox="0 0 60 84">' +
  '<rect width="60" height="84" fill="#2b2b31"/></svg>'

const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

/** One card, in the shape `GET /inventory` answers with, and the four the small store holds.
 *
 *  EVERY DECORATION `server/capture_server.py:do_inventory` ADDS IS PRESENT. The screens render
 *  these and compute none of them, so a row missing one takes a panel down and the failure
 *  reads as an unregistered route rather than as a short fixture. Written to the same rule as
 *  `nav.spec.ts`'s own `CARD`, which states it at length.
 *
 *  ONE OF THE FOUR HAS LEFT (D58), because a box that closes up behind a departed card is the
 *  state most of this product's labelling logic is about, and a fixture where every card is on
 *  hand cannot draw it. */
function card(over: {
  box: number
  index: number
  section: number
  card: number
  name: string | null
  state?: string
  sku?: string | null
  boxName?: string | null
  boxTotal: number
}) {
  const gone = over.state === 'sold' || over.state === 'retired'
  return {
    box: over.box,
    index: over.index,
    label: `${over.boxName ?? `Box ${over.box}`}, Section ${over.section}, Card ${over.card}`,
    section: over.section,
    card: over.card,
    place: {
      located: true,
      /* THE SERVER'S LABEL (D259): the box's name, the section and the card
         within it, a departed card naming the place it left. `slot` null is what marks it gone. */
      label: `${over.boxName ?? `Box ${over.box}`}, Section ${over.section}, Card ${over.card}`,
      box: over.box,
      index: over.index,
      section: over.section,
      card: gone ? null : over.card,
      box_name: over.boxName ?? null,
      section_start: 1,
      section_end: null,
      box_total: over.boxTotal,
      box_closed: false,
      fraction: over.card,
      neighbors: null,
      section_gaps: 0,
    },
    photo: `photos/${over.box}/${over.index}.jpg`,
    set_hint: 'ME01',
    metadata_finish: 'normal',
    game: 'pokemon',
    rarity_claim: null,
    note: null,
    captured_at: '2026-08-22T12:34:00+00:00',
    capture_id: `cap-${over.box}-${over.index}`,
    name: over.name,
    number: '025',
    printed_total: '132',
    confidence: null,
    sku: over.sku ?? null,
    condition: null,
    state: over.state ?? 'captured',
    state_at: '2026-08-22T12:34:00+00:00',
    retire_reason: null,
  }
}

const CARDS = {
  '2/1': card({ box: 2, index: 1, section: 1, card: 1, name: 'Volcanion', boxName: 'SV commons', boxTotal: 3 }),
  '2/2': card({ box: 2, index: 2, section: 1, card: 2, name: 'Thievul', state: 'identified', sku: '8937370', boxName: 'SV commons', boxTotal: 3 }),
  '2/3': card({ box: 2, index: 3, section: 2, card: 3, name: 'Eiscue', state: 'sold', sku: '8937371', boxName: 'SV commons', boxTotal: 3 }),
  '5/1': card({ box: 5, index: 1, section: 1, card: 1, name: null, boxTotal: 1 }),
}

/* ---------------------------------------------------------------------------- the seal */

/** Is this request bound for somewhere that is not this machine's two servers?
 *
 *  AN ALLOW-LIST OF TWO PORTS, AND THE BLOCK-LIST IT REFUSES TO BE. The thing that prompted
 *  this guard was three typefaces on `fonts.googleapis.com`, and a rule naming that host would
 *  be satisfied by the next person reaching for jsdelivr. What the suite is entitled to talk
 *  to is knowable and short — the Vite server the page came off, and the capture port
 *  `sealCapture` already owns — so the rule is stated as those two and everything else is
 *  refused. `docs/DEBTS.md` carries this repo's own receipt for the other shape: a dry-run
 *  guard built as a block-list of guessed endpoint names let a real TCGplayer import through.
 *
 *  THE PORT IS THE WHOLE TEST, for the reason `CAPTURE_ORIGIN` above gives: `server.ts`
 *  composes its base from `location.hostname`, so the same page opened at `pkmnscan.lan` asks
 *  a different host on the same two ports, and both are still this Mac. A hostname allow-list
 *  would have to guess at that set; the ports are derived from this checkout (D43).
 *
 *  ONLY `http:` AND `https:`. `data:` and `blob:` never leave the process — the capture
 *  screen's encoder and every inline SVG fixture in this file are blobs and data URIs — and
 *  Playwright does not route them anyway. */
function isOutside(url: URL): boolean {
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return false
  return url.port !== String(DEV_PORT) && url.port !== String(CAPTURE_PORT)
}

/** Refuse and record every request that would leave this machine.
 *
 *  REGISTERED BEFORE `sealCapture`, SO IT IS THE LAST RESORT UNDER EVERYTHING — Playwright
 *  matches newest-first, and this one has to lose to every stub including the capture seal.
 *  `isOutside` already excludes the capture port, so the two cannot both fire; the order is
 *  what keeps that true if either predicate is ever widened.
 *
 *  WHY IT EXISTS WHEN NOTHING IS LEAKING TODAY. `app/index.html` fetched three typefaces from
 *  Google Fonts until 2026-09-08, on every page load, in every one of the fresh contexts these
 *  specs open — order a thousand round trips to the public internet per `make design-check`
 *  run, none of it visible to `sealCapture`, which matches on the capture port alone. Vendoring
 *  the faces (`app/src/fonts.css`) UNDID that; this is what stops it being re-done. A guard
 *  against an outside dependency is worth more than the absence of one, because the absence is
 *  a fact about today and the guard is a fact about every commit after it.
 *
 *  IT ABORTS AS `blockedbyclient` rather than `addressunreachable`. Nothing in `app/src` reads
 *  the code, so this changes no rendering; what it changes is the sentence in a trace, which
 *  for an escaped request is a policy refusal and not a dead server. */
async function sealOutside(page: Page): Promise<void> {
  const seen: string[] = []
  escaped.set(page, seen)
  await page.route(
    (url) => isOutside(url),
    async (route) => {
      const request = route.request()
      seen.push(`${request.method()} ${request.url()}`)
      await route.abort('blockedbyclient')
    },
  )
}

/** Refuse and record every request to this checkout's capture port.
 *
 *  MUST BE REGISTERED BEFORE ANY OTHER HANDLER on the page — see the header. `sealEveryTest`
 *  is the supported way to call it. */
async function sealCapture(page: Page): Promise<void> {
  const seen: string[] = []
  leaked.set(page, seen)
  await page.route(CAPTURE_ORIGIN, async (route) => {
    const request = route.request()
    seen.push(`${request.method()} ${new URL(request.url()).pathname}`)
    /* NAMED RATHER THAN THE DEFAULT `failed`, so the line in a trace says what happened. It
       reaches the app as the same `ServerError('unreachable')` either way. */
    await route.abort('addressunreachable')
  })
}

/* --------------------------------------------------------------------------- the shell */

/** `GET /status`, in the shape `ServerStatus` actually has.
 *
 *  `nav.spec.ts` records what a wrong shape costs: `status.cards` is read straight into
 *  `Sidebar`, which sits outside every route boundary, so a missing key takes the whole shell
 *  down a beat after the screen renders — and every case had already made its first assertion
 *  by then. `cards` is a parameter because the sidebar draws it beside a walk that has its own
 *  count, and two numbers disagreeing on one screen is the class of lie this file is fixing. */
async function stubShell(page: Page, cards: number): Promise<void> {
  await page.route(/\/status$/, (route) =>
    json(route, {
      captures_root: 'captures',
      store: 'inventory/store.sqlite',
      store_exists: true,
      cards,
      states: {},
      queues: { review: 0, parked: 0 },
      next_index: {},
    }),
  )
  /* THE SEND STATUS, BESIDE `/status` AND FOR ITS REASON (`D273`,
     Q3). Every visit to Home and to Pricing reads it to learn whether the live check after a
     send is due, so it is as much a shell read as `/status` is. The answer is the empty one —
     nothing sent, nothing due — so no spec sees a check it did not ask for. A spec about sends
     registers its own handler after this one, and Playwright matches most-recent first. */
  /* THE AUTOMATIC MATCH (flow interview, Q4). `#/runs` calls it for every run it sees waiting
     for a match, and the shared fixtures' default run IS one — so every spec that draws the
     list would otherwise meet the seal over a press nobody made. The answer is "not waiting",
     which changes nothing on screen; a spec about the match registers its own handler after
     this one, and Playwright matches most-recent first. */
  await page.route(/\/pipeline\/runs\/[^/]+\/match$/, (route) =>
    json(route, { ran: false, reason: 'not_waiting', summary: {} }),
  )
  await page.route(/\/pipeline\/sends$/, (route) =>
    json(route, { sends: [], unconfirmed: { copies: 0, stamps: [] }, due: false, check_at: null, now: '2026-09-24T12:00:00+00:00' }),
  )
  /* THE PALETTE'S CARD SEARCH IS THE SHELL'S OWN READ NOW (D276): typing two letters
     into "Go to" asks `GET /search`. It is answered EMPTY, and ONLY while the palette is open.
     A screen's own search falls back to the seal, so a spec that forgot to stub its screen's
     search is still named rather than handed a shared answer. A spec that wants cards in the
     palette registers its own `/search` handler, which is newer and wins. */
  await page.route(/\/search\?/, async (route) => {
    const fromPalette = await route
      .request()
      .frame()
      .evaluate(() => document.querySelector('.bn-cmdk') !== null)
      .catch(() => false)
    if (!fromPalette) return route.fallback()
    const q = new URL(route.request().url()).searchParams.get('q') ?? ''
    return json(route, { query: q, groups: [] })
  })
}

/* ---------------------------------------------------------------------- the small store */

/** The whole read surface, small and coherent, for the specs that carry no fixtures of their
 *  own — `cursor`, `gallery`, `pull-confirm`, `brand`, `motion-live`.
 *
 *  WHY THESE SPECS GET ONE AND THE OTHERS DO NOT. A spec with its own fixtures gets the seal
 *  alone, so a gap in it is REPORTED; handing it a shared answer would close the gap and the
 *  report together. These five register no handlers at all and are not about the data — they
 *  sweep cursors, render the kit sheet, or drive the motion trigger — so what they need is for
 *  every screen to draw its POPULATED controls, the same way, in every checkout.
 *
 *  `cursor.spec.ts` is the reason it is populated rather than empty. Its header says it sweeps
 *  "this worktree's empty store", and in the main tree it swept the owner's 767 cards instead —
 *  so the number of controls it looked at was a property of which checkout ran it. Small real
 *  fixtures make that number the same everywhere, and larger than the empty answer.
 *
 *  EVERY ROUTE HERE IS A READ. Nothing in this module answers a write: a spec that means to
 *  write says so with its own handler, and one that writes by accident is named by the seal. */

/* THE CROP WINDOW, WHICH IS A POST AND STILL A READ. The Home hero and `#/pricing`'s row
 * thumbnails ask for a rectangle, and it is stubbed here rather than in their specs because the
 * seal reported it, not because anybody remembered the screens made it.
 *
 * IT WAS EXPORTED FOR A WEEK. D125 put the crop on four more screens, `inventory.spec.ts` and
 * `fulfillment.spec.ts` carry their own `stubServer` rather than calling `stubStore`, and both
 * needed it; the owner reverted those four on 2026-09-10 and it has one caller again. Left
 * exported it would be a seam nothing crosses, which is the shape this file's own header warns
 * about elsewhere.
 *
 * THE RECTANGLE IS A BELIEVABLE ONE ON PURPOSE. `[216, 384, 1944, 3456]` sits inside its
 * 2160x3840 frame, so the specs measure the CROPPED render — the one the product draws. A
 * rectangle that overran the frame would be refused, the screens would fall back, and the suite
 * would go green over the fallback while believing it had looked at the crop. */
async function stubCropPreview(page: Page): Promise<void> {
  await page.route(/\/pipeline\/crop-preview$/, (route) =>
    json(route, {
      scope: { box: 2, whole_box: false, cards: [1] },
      capture_dir: '/tmp/captures/cards/box2',
      crop: true,
      max_edge: 256,
      total: 4,
      offset: 0,
      sample: {
        box: 2,
        index: 1,
        game: 'pokemon',
        frame: [2160, 3840],
        sent: [144, 256],
        rect: [216, 384, 1944, 3456],
        method: 'edges',
        crop_refused: null,
      },
    }),
  )
}

async function stubStore(page: Page): Promise<void> {
  await page.route(/\/photo\/\d+\/\d+/, (route) =>
    route.fulfill({ status: 200, contentType: 'image/svg+xml', body: PHOTO_SVG }),
  )
  /* THE FREE COST CHECK, WHICH IS A POST AND STILL A READ (the crop window's reason, below).
     The Identify sheet runs it the moment it opens (the owner's Q5 ruling), so a spec that only
     opens the sheet reaches it. The answer is a small, believable quote; nothing here spends —
     `POST /pipeline/identify` stays unstubbed, so the seal reports any spec that presses it. */
  await page.route(/\/pipeline\/preflight$/, (route) =>
    json(route, {
      ok: true,
      exit_code: 0,
      selection: { state: 'captured' },
      sentence: '14 cards waiting to be identified',
      scope: null,
      capture_dirs: [],
      console: '',
      claimed: null,
      total: { photographs: 14, cache_hits: 3, to_send: 11, estimate_usd: 0.46, cards: 14 },
    }),
  )

  /* TWO BOXES, SO A PICKER HAS SOMETHING TO PICK BETWEEN. One named and one not — a name is
     optional and `runScope.ts` draws `Box 3` alone where there is none (D56), so a fixture
     with names on everything cannot exercise the branch a real store spends most of its time
     in. Box 2 carries dividers; box 5 declares none, which since D10's amendment renders as
     the one undivided section it physically is. */
  await page.route(/\/boxes$/, (route) =>
    json(route, {
      boxes: [
        {
          box: 2,
          bid: 12,
          name: 'SV commons',
          sections: [1, 3],
          state: 'open',
          capacity: 100,
          fill: 4,
          next_index: 5,
          cards: 4,
          on_hand: 3,
          sold: 1,
          retired: 0,
          moved: 0,
          listed: 0,
          sections_detail: [
            { section: 1, start: 1, end: 2, count: 2 },
            { section: 2, start: 3, end: 4, count: 2 },
          ],
        },
        {
          box: 5,
          bid: 15,
          name: null,
          sections: [],
          state: 'open',
          capacity: 100,
          fill: 1,
          next_index: 2,
          cards: 1,
          on_hand: 1,
          sold: 0,
          retired: 0,
          moved: 0,
          listed: 0,
          sections_detail: [{ section: 1, start: 1, end: 1, count: 1 }],
        },
      ],
    }),
  )

  /* FOUR CARDS ACROSS THE TWO BOXES, WHICH IS WHAT PUTS CONTROLS ON A SCREEN AT ALL. The walk
     renders an empty state and no search field for an empty store, so an empty fixture would
     have swept a screen with almost nothing on it — and `cursor.spec.ts` measured 418 elements
     against the owner's real store, which is the number this has to be judged against rather
     than against zero. Every decoration `server/capture_server.py:do_inventory` adds is
     present: the screens render them and compute none of them, so a row missing one takes a
     panel down and the failure reads as an unregistered route. Shape borrowed verbatim from
     `nav.spec.ts`'s own `CARD`, which is the one fixture in this directory already written to
     that rule. */
  await page.route(/\/inventory$/, (route) => json(route, { version: 2, cards: CARDS, boxes: {}, listings: {} }))
  /* DEBT27, site 1: `Orders.tsx` no longer calls the bare `/inventory` above —
   * it calls `POST /inventory/copies` with the SKU set its own ledger read just named, and
   * a spec seeding real orders (`routeFixtures.ts:seedPopulatedOrders`) alongside `stubStore`
   * would otherwise leak that write to the real capture port. Filtered the same way the real
   * route filters: on-hand copies of an asked-about SKU only, `sold`/`retired`/`moved`
   * excluded — the same predicate `Orders.tsx`'s own `GONE` set names. */
  await page.route(/\/inventory\/copies$/, (route) => {
    const gone = new Set(['sold', 'retired', 'moved'])
    const body = route.request().postDataJSON() as { skus?: unknown }
    const wanted = new Set(Array.isArray(body.skus) ? body.skus : [])
    const cards = Object.fromEntries(
      Object.entries(CARDS).filter(([, c]) => {
        const row = c as { sku?: string | null; state: string }
        return row.sku != null && wanted.has(row.sku) && !gone.has(row.state)
      }),
    )
    return json(route, { cards })
  })
  /* D192 (store-scaling item 2): `#/inventory` and Home's hero deck no longer call
   * the bare `/inventory` above — `getInventoryBox`/`getRecentCards` reach these two instead.
   * `/\/inventory$/` above is anchored and never matches either (a box number or `recent`
   * follows the slash), so both need their own stub or a walk over `#/inventory`/`#/` reaches
   * the real capture server and `sealOutside` refuses it. Same per-card shape as `GET
   * /inventory`, narrowed the way the real routes narrow it: `do_inventory_box` carries no
   * `boxes` key and only the requested box's own cards and listings; `do_inventory_recent`
   * carries only `cards`, filtered to on-hand/named/photographed. */
  await page.route(/\/inventory\/(\d+)$/, (route) => {
    const match = /\/inventory\/(\d+)$/.exec(route.request().url())
    const box = match ? Number(match[1]) : NaN
    const cards = Object.fromEntries(
      Object.entries(CARDS).filter(([, c]) => (c as { box: number }).box === box),
    )
    return json(route, { version: 2, cards, listings: {} })
  })
  await page.route(/\/inventory\/recent(\?|$)/, (route) => {
    const gone = new Set(['sold', 'retired', 'moved'])
    const cards = Object.fromEntries(
      Object.entries(CARDS).filter(
        ([, c]) =>
          !gone.has((c as { state: string }).state) &&
          (c as { name: string | null }).name !== null &&
          (c as { photo: string | null }).photo !== null,
      ),
    )
    return json(route, { cards })
  })
  await page.route(/\/search\?/, (route) => json(route, { query: '', groups: [] }))

  /* THE QUEUES, THE RUNS, THE WORKLIST, THE LEDGER AND THE ORDERS, each empty and each with
     every key its screen indexes PRESENT. A payload missing a key makes "none" and "not asked"
     the same answer, and a screen drawn from a short map is a screen this fixture could break —
     `nav.spec.ts` states that rule at length over the same five routes and this is the same
     answer, shared rather than transcribed a second time. Empty rather than populated because
     each of these is another spec's subject: D63's ledger is `orders.spec.ts`'s, D70's codes
     are `#/codes`'s, and a fixture here that disagreed with one of those would be a second
     opinion about the wire with nothing reconciling them. */
  /* ONE QUEUED CARD RATHER THAN NONE, because `#/review` draws an empty state and no answer
     controls over an empty queue — and the sweep is measuring controls. `no_catalog_row` with
     zero candidates is D37's black-frame card and the live shape on the owner's store, so this
     is the queue's ordinary state rather than its happy one. */
  await page.route(/\/queues$/, (route) =>
    json(route, {
      review: [
        {
          position: 'Box 2, Section 1, Card 1',
          box: 2,
          index: 1,
          label: 'Box 2, Section 1, Card 1',
          photo: 'photos/2/1.jpg',
          read: { name: 'Volcanion', number: '025', printed_total: '132', set_hint: 'ME01' },
          confidence: null,
          reason: 'no_catalog_row',
          candidates: [],
          first_seen: '2026-09-01T12:00:00+00:00',
          market: null,
          cleared_by_human: false,
        },
      ],
      parked: [],
    }),
  )
  await page.route(/\/pipeline\/runs$/, (route) => json(route, { runs: [] }))
  /* THE CLAIMS PANEL'S READ, IN THE SEAL RATHER THAN IN EACH SWEEP (D174).
     `#/runs` draws `SubmissionClaims`, which reads this on mount — so every spec that WALKS
     EVERY OWNER SCREEN makes it: `wide.spec.ts`, `cursor.spec.ts` and `phone.spec.ts` each
     failed on `reads reached the capture server` the day the panel landed, seven failures from
     one unstubbed route, none of them about anything those files assert. This is where
     `/status` lives for the same reason, and the nav spec's own comment records that move.

     EMPTY, AND THAT IS THE STATE WORTH SWEEPING. A claim exists only between a press and the
     collection it paid for, so a healthy store holds none and the panel draws nothing — which
     is what the floors above should be measuring on this screen. A sweep that met a drawn
     panel here would be measuring a fixture nobody chose. The cases that need it drawn pass
     `claims` to `run-panel.spec.ts`'s own `open`. */
  await page.route(/\/pipeline\/submissions$/, (route) =>
    json(route, { claims: [], counts: { claims: 0, keys: 0, stale: 0 } }),
  )
  await page.route(/\/pipeline\/markdowns$/, (route) => json(route, { markdowns: [] }))
  /* THE ORDER OF THESE TWO IS THE MECHANISM, NOT A TIDY-UP. `/\/pricing$/` matches
     `…/pipeline/pricing` as happily as `…/pricing`, and Playwright takes the NEWEST handler
     first — so registering the corpus last answered the WORKLIST with a corpus, `roster` came
     back undefined, and `Home.tsx:241` took the whole screen down behind its route boundary
     with `undefined.filter`. The narrower route is registered second and therefore wins. D86
     is why there are two at all: the corpus is the store's one pricing answer and the worklist
     is which cards are in front of the operator. */
  await page.route(/\/pricing$/, (route) =>
    json(route, { corpus: { rule: null, basis: null, sub_threshold: null, overrides: {} }, path: 'inventory/prices.json', revision: 'r0' }),
  )
  await page.route(/\/pipeline\/pricing(\?|$)/, (route) =>
    json(route, {
      runs: [],
      roster: [],
      skus: [],
      decisions: {},
      written_at: {},
      skipped: [],
      asked: [],
      remembered_sub_threshold: null,
      defaults: {},
      threshold: null,
      floor: null,
    }),
  )
  /* `?band=` (store-scaling item 7) — a default so a spec that navigates to `#/pricing?band=`
     without its own stub (every case today is `value-bands.spec.ts`, which overrides this with
     its own fixture-driven handler) still gets a real response rather than a hung request.
     `(\?|$)` covers both the unpaginated `do_pipeline_value()` shape (no query string, still
     answered by any direct caller) and the paginated `?band=...` form — the same anchor fix
     `value-bands.spec.ts`'s own `open()` needed for the identical reason. */
  await page.route(/\/pipeline\/value(\?|$)/, (route) =>
    json(route, {
      at: '2026-01-01T00:00:00.000+00:00',
      basis: 'market',
      threshold: null,
      sources: [],
      rows: [],
      copies: [],
      next: null,
      total: 0,
      boxes: [],
      unrankable: { total: 0, never_identified: 0, read_nothing: 0, no_reading: 0, by_box: {} },
      totals: { cards: 0, valued: 0, value: '0.00', under_cutoff: 0, at_or_over: 0 },
    }),
  )
  await page.route(/\/codes$/, (route) =>
    json(route, {
      counts: {},
      total: 0,
      lanes: { bulk: 0, premium: 0, unclaimed: 0 },
      by_product: [],
      duplicates: [],
      entries: [],
      products: [],
    }),
  )
  await page.route(/\/codes\/lots$/, (route) => json(route, { lots: [] }))
  /* D134's graveyard: empty, because this fixture's departed cards belong to `#/inventory`
     and its own copies list, not to a screen these five specs never navigate to. */
  await page.route(/\/graveyard$/, (route) => json(route, { departed: [] }))
  await page.route(/\/orders$/, (route) =>
    json(route, {
      summary: '0 orders',
      orders: [],
      resolution: {
        orders: [],
        counts: {
          resolved: 0,
          short: 0,
          no_copies_on_hand: 0,
          sku_unknown: 0,
          sku_unseen: 0,
          not_a_single: 0,
        },
      },
    }),
  )
  /* THE PICKS TIER — `GET /orders` above answers zero orders, so there is nothing any key
   *  asked here could ever name. `/\/orders$/`'s regex does not match this path (no `$`
   *  collision, `orders/picks` is a longer string), so without this a spec that merely
   *  visits `#/orders` sends an unstubbed POST straight into `sealCapture`'s catch-all,
   *  which ABORTS AND RECORDS rather than answering — `sealEveryTest` then fails the test
   *  for a leaked request that was never a bug in the screen. The seal refuses; this
   *  answers, matching what `do_order_picks` actually returns for a key it holds nothing
   *  for. `orders.spec.ts`'s own `open()` overrides this per case with real fixtures. */
  await page.route(/\/orders\/picks$/, (route) => json(route, { orders: [] }))

  await stubCropPreview(page)

  /* D46's CATALOG LOOKUP, WHICH THE QUEUE ENTRY ABOVE IS WHAT ASKS FOR. A `no_catalog_row`
     card with zero candidates is offered rows out of the export on arrival, unasked — so
     populating the queue at all brings this route with it. The seal is how that was learned:
     the entry went in, and `GET /review/2/1/catalog` was named on the next run. */
  await page.route(/\/review\/\d+\/\d+\/catalog/, (route) =>
    json(route, {
      box: 2,
      index: 1,
      game: 'pokemon',
      query: 'Volcanion',
      searched: false,
      rows: [],
      found: 0,
      truncated: false,
    }),
  )

  /* THE REGISTRY, TWO GAMES DEEP, and the second one is not decoration: `product_game` and
     `products` are what `ClaimEditor` reads straight into state, and a registry that omitted
     them threw `undefined.find` behind a route boundary and cost six cases thirty seconds
     each on 2026-09-05. The vocabulary is transcribed from `pipeline/games.py` and
     `codes/products.py`. */
  await page.route(/\/games$/, (route) =>
    json(route, {
      default: 'pokemon',
      games: [
        {
          key: 'pokemon',
          display: 'Pokémon',
          product_line: 'Pokemon',
          rarities: ['Common', 'Uncommon', 'Rare'],
          finishes: ['normal', 'holo', 'reverse_holo'],
          condition_by_finish: { normal: 'Near Mint', holo: 'Near Mint Holofoil' },
          finish_by_rarity: { Common: ['normal'], Uncommon: ['normal'], Rare: ['normal', 'holo'] },
          located: true,
          join_key: 'number_over_printed_total',
          prompt: 'pokemon',
          crop_bands: ['title', 'number'],
          card_aspect: 0.716,
          /* THE REGISTRY SAYS THIS AND SO MUST THE STUB. `pokemon` cannot be fetched
             without a set hint — its whole category is 97% of the download's ceiling — and
             a stub that omitted the flag would leave every guard over the capture screen's
             hint note blind to the state it exists to draw. `pokemon_code` carries neither
             field, exactly as the real entry does: same category, but it joins by name, so
             a hint would narrow nothing. */
          export_needs_hint: true,
          export_category_bytes: 32629598,
          unverified: false,
          catalogued: true,
        },
        {
          key: 'pokemon_code',
          display: 'Pokémon code cards',
          product_line: 'Pokemon',
          rarities: ['Code Card'],
          finishes: ['normal'],
          condition_by_finish: { normal: 'Near Mint' },
          finish_by_rarity: { 'Code Card': ['normal'] },
          located: false,
          join_key: 'name_only',
          prompt: 'pokemon_code_v1',
          crop_bands: [],
          card_aspect: 0.716,
          unverified: false,
          catalogued: true,
        },
      ],
      product_game: 'pokemon_code',
      products: [
        { key: 'booster', display: 'Booster pack', premium: false, redeem_limit: 400 },
        { key: 'etb', display: 'Elite Trainer Box', premium: true, redeem_limit: 4 },
        { key: 'other', display: 'Other / unsure', premium: false, redeem_limit: 4 },
      ],
    }),
  )
}

/* ------------------------------------------------------------------------ the entry point */

/** Seal the capture port for every test in the calling spec, and answer the shell.
 *
 *  CALL IT AT MODULE SCOPE, ABOVE EVERYTHING — above any `test.beforeEach`, above any `test()`.
 *  The header says why, and `make docs-audit`'s `spec seal` row enforces it.
 *
 *  `store: true` adds the small read surface for a spec that registers no handlers of its own.
 *  Leave it off and the spec gets the seal and `/status` only, which is what makes a missing
 *  fixture fail by name. */
export function sealEveryTest(opts?: { store?: boolean; cards?: number }): void {
  test.beforeEach(async ({ page }) => {
    await sealOutside(page)
    await sealCapture(page)
    await stubShell(page, opts?.cards ?? 0)
    if (opts?.store === true) await stubStore(page)
  })

  test.afterEach(async ({ page }) => {
    const seen = leaked.get(page)
    expect(seen, 'sealCapture never ran for this page — `sealEveryTest` is mis-wired').toBeDefined()
    expect(
      seen ?? [],
      'reads reached the capture server — in the main checkout that is the owner’s real store.\n' +
        'Stub them in this spec, or pass `{ store: true }` if this spec carries no fixtures.',
    ).toEqual([])

    const out = escaped.get(page)
    expect(out, 'sealOutside never ran for this page — `sealEveryTest` is mis-wired').toBeDefined()
    expect(
      out ?? [],
      'a request left this machine. The suite talks to this checkout’s Vite and capture ports\n' +
        'and to nothing else — see `sealOutside`. If this is a web font, vendor it the way\n' +
        '`app/src/fonts.css` vendors the three the app already uses.',
    ).toEqual([])

    /* TWO INVARIANTS OVER THE SHELL, because both of the failures they name were invisible at
       the point they were caused and loud somewhere else entirely.

       THE BANNER is a 44px strip above the view whenever `/status` does not answer. It shifts
       every absolute measurement below it, so a floor asserted under it is asserted against a
       screen the operator does not have. It failed two cases in `inventory.spec.ts` as bare
       numbers and nothing said the word "offline". It cannot appear while the stub above holds,
       which is exactly why its return should fail as itself.

       THE CRASH PAGE: `RouteBoundary` swallows a throw and renders in the view's place, so the
       control a case reaches for is simply not there. Playwright reports that as `element was
       detached from the DOM` after a thirty-second timeout — six cases in `inventory.spec.ts`,
       every one naming a switch and none naming `undefined.find` in `ClaimEditor`. Asserted on
       the HEADING, not on `.no-such-view`, which the 404 view shares.

       AT THE END RATHER THAN AFTER THE NAVIGATION, which is stronger than the hand-written
       version this replaces: a screen that crashes halfway through a case is caught too. */
    await expect(page.locator('.bn-banner')).toHaveCount(0)
    await expect(page.getByRole('heading', { name: 'This screen stopped.' })).toHaveCount(0)
  })

  /* AND THE APP IS TORN DOWN WHILE THE SEAL IS STILL INSTALLED, which is the last hole and a
     MEASURED one rather than a theoretical tidy-up.

     Playwright disposes the page AFTER the `afterEach` hooks, and a request the browser had
     already started at that moment is released by Chromium rather than routed — so it reaches
     the real capture port, and the roster the hook just read cannot contain it. Measured over
     three full 380-case runs against a logging server on this worktree's capture port: nine
     requests got out that way, every one a poll a panel had in flight when its case ended —
     `/boxes/2/listings`, `/boxes/2/photos`, `/pipeline/runs/<name>`, `/orders`. Small, not
     zero, and a POST would get out by the same door.

     `about:blank` ENDS THE DOCUMENT while the handlers are still there, so the app's pending
     fetches are cancelled in the renderer and never reach the network at all. Same instrument,
     four full runs with this hook in place: zero.

     ONLY WHEN THE CASE PASSED, because otherwise this would destroy every failure diagnostic
     in the suite. `only-on-failure` screenshots and the `error-context.md` snapshot are taken
     during fixture teardown — after these hooks — so blanking unconditionally would hand every
     red case a picture of nothing. `status` here is the test body's own outcome: a case that
     failed keeps its evidence, and a case that passed has none worth keeping. */
  test.afterEach(async ({ page }, testInfo) => {
    if (testInfo.status !== 'passed') return
    await page.goto('about:blank').catch(() => {
      /* The page can already be gone; there is nothing left to tear down if it is. */
    })
  })
}
