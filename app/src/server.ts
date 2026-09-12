import type {
  AnswerResult,
  CodeExportResult,
  CodeLedger,
  LotReceipt,
  LotResult,
  CodeScanResult,
  StandDownReason,
  StandDownResult,
  BoxRecord,
  BoxState,
  BoxSummary,
  CardSummary,
  Finish,
  GameRegistry,
  GroupAnswerResult,
  Inventory,
  PhotoReclaimResult,
  Place,
  PlaceNeighbor,
  QueueSnapshot,
  RetireReason,
  RetireResult,
  CatalogLookup,
  ReviewAnswer,
  SaleResult,
  SearchResult,
  ServerStatus,
  BoxClaimResult,
  RemoveResult,
  MoveResult,
  MoveCardsResult,
  BoxDeleteResult,
  GraveyardPayload,
  BoxListingPlan,
  BoxPhotoPlan,
  ListingReleaseResult,
  CropPreview,
  CsvUpload,
  ExportFetched,
  ExportScope,
  MarkdownAnswer,
  MarkdownPublish,
  MarkdownPush,
  LiveExportFetched,
  MarkdownTable,
  MarkdownAsk,
  MarkdownSummary,
  RunDetail,
  PriceHistoryPayload,
  PricingPayload,
  PricingCorpus,
  PricingClearable,
  PricingClearResult,
  PricingWorklist,
  RunSend,
  RunPreflight,
  RunStarted,
  RunStepResult,
  TcgSets,
  RunSummary,
  IngestResult,
  OrderIngestOrder,
  OrdersFetched,
  OrdersPreview,
  OrdersPayload,
  PullResult,
  PullTarget,
  ShippingBatch,
  ShippingForgotten,
  TrendsPayload,
  OrderFillReason,
  OrderFillResult,
  OrderLineKind,
  OrderLineKindResult,
  OrderCloseReason,
  OrderCloseResult,
  ValueTable,
  SubmissionClaims,
  ClaimRelease,
} from './types'

/* The only module in this app that talks to the capture server.
 *
 * ONE OWNER, deliberately (capture-app spec section 4): the failure behaviour in section
 * 5.5 — a failed capture stops the run and says so, loudly — is one decision, and a
 * decision spread across four components is four decisions that drift. Every function here
 * fails the same way, with the same class, carrying the server's own words.
 *
 * THE MESSAGES ARE THE SERVER'S, VERBATIM. `server/capture_server.py:_fail` already obeys
 * docs/DESIGN.md's copy rule — what happened, and what to do next — and it does it holding
 * facts this side of the wire does not have ("box 3 has no card 18; the newest is 17").
 * Paraphrasing one into something friendlier deletes exactly the part the operator acts on.
 * The only strings this module writes itself are for failures the server never got to
 * report; there are two, and they are marked where they are thrown.
 *
 * NO AUTH, NO TLS, NO LOGIN SCREEN. Recorded in docs/specs/capture-server.md and restated
 * in the capture-app spec so it is not "fixed" here. CORS is answered server-side for any
 * origin with no credentials.
 *
 * NO CLIENT-SIDE TIMEOUT, and this one is worth being explicit about because adding one
 * looks like an obvious improvement. `Store.write()` waits up to 30 seconds for the file
 * lock, so a capture posted while `./pkmnscan identify` holds it can legitimately take that
 * long and then answer `store_busy` — a true statement naming the process to wait for. Any
 * AbortController shorter than the server's own lock timeout converts that into
 * `unreachable`, which is a lie about the server being down, and it does so at the moment
 * the operator most needs a straight answer. If a timeout is ever added it belongs above
 * 30s, not below it.
 */

/* Vite substitutes both of these at build time. VITE_CAPTURE_SERVER is the operator's
 * explicit override — it exists so the Fulfiller's device can be pointed at this Mac by
 * address later, which is the one thing the capture-app spec leaves open (section 11).
 *
 * VITE_CAPTURE_DEFAULT is THIS CHECKOUT'S server, derived in `app/devPort.ts` from the same
 * slot as the Vite port and injected by `vite.config.ts` (D46). It replaced a hardcoded
 * `http://localhost:8000`, which was wrong in every tree but one: `store/files.py:home()`
 * gives each checkout its own inventory, so a shared port meant this UI could be answered by
 * another tree's server over another tree's store — in one direction driving the owner's real
 * inventory from a branch, in the other writing real capture photographs into a directory
 * that is deleted with the worktree.
 *
 * The literal below is the last-resort fallback for a bundle built without that define — a
 * bare `tsc`, a test harness, an editor's type server. It is the main tree's port, which is
 * the right guess when nothing has told us which tree this is.
 *
 * THE HOST IS RESOLVED AT RUNTIME AND ONLY THE PORT IS BAKED, WHICH IS WHAT LETS THIS PAGE BE
 * OPENED FROM ANOTHER DEVICE. `VITE_CAPTURE_DEFAULT` is a whole URL and its host is
 * `localhost`, which is correct at the desk and catastrophic anywhere else: on a phone,
 * `localhost` IS THE PHONE, so every request goes to a server that is not there. The capture
 * server has bound `0.0.0.0` since it was written and was reachable the whole time — the
 * client was the half that could not be told.
 *
 * So the derived default is composed here from `location` plus the checkout's port. It keeps
 * every property the injected URL had — the port still comes from the same slot as the Vite
 * port, so a worktree's UI still cannot be answered by another tree's server — and adds the
 * one it lacked: it follows the address bar. Opened at `localhost` it resolves to
 * `localhost`; opened at `pkmnscan.lan` it resolves to `pkmnscan.lan`. Any hostname works,
 * with no rebuild and nothing to configure.
 *
 * This HONOURS the note above about VITE_CAPTURE_SERVER rather than overriding it. That knob
 * exists because the default could not follow the address bar; it still wins, and it is still
 * the answer for pointing a device at a DIFFERENT machine. What it is no longer needed for is
 * the ordinary case of reaching this one by its own name. */
const FALLBACK_BASE = 'http://localhost:8000'
const derivedUrl: unknown = import.meta.env.VITE_CAPTURE_DEFAULT
const derivedPort: unknown = import.meta.env.VITE_CAPTURE_PORT

/* `typeof window` rather than a bundler flag, because the non-browser callers are real and
 * varied — `tsc`, the Playwright specs' module imports, an editor's type server — and none of
 * them can be enumerated reliably. Where there is no `location` there is no address bar to
 * follow, and the injected URL is the honest answer. */
const sameHostBase = (): string | null => {
  if (typeof window === 'undefined' || !window.location) return null
  const port = typeof derivedPort === 'number' ? derivedPort : Number(derivedPort)
  if (!Number.isInteger(port) || port < 1 || port > 65535) return null
  return `${window.location.protocol}//${window.location.hostname}:${port}`
}

const DEFAULT_BASE =
  sameHostBase() ??
  (typeof derivedUrl === 'string' && derivedUrl.trim() !== ''
    ? derivedUrl.trim().replace(/\/+$/, '')
    : FALLBACK_BASE)
const configured: unknown = import.meta.env.VITE_CAPTURE_SERVER

/* Trailing slashes stripped so `${base}/status` cannot become `//status`, which some
 * servers route and this one answers with `no_such_route` — a confusing failure to debug
 * for a stray character in a `.env` file nobody is looking at. */
const base =
  typeof configured === 'string' && configured.trim() !== ''
    ? configured.trim().replace(/\/+$/, '')
    : DEFAULT_BASE

/**
 * Whether this bundle is the published demo rather than a client for a real capture server.
 *
 * Set only by `make demo-static`, which builds with `VITE_DEMO=1`. Everywhere else
 * `vite.config.ts` defines `__BN_DEMO__` as the literal `false`, so this branch reads
 * `if (false)` in the source Rollup sees and goes away with the dynamic
 * `import('./demoServer')` inside it — an ordinary build carries no reference to it and no
 * `demoServer` chunk, which is the one worth caring about at 1.3 MB of recorded fixtures.
 * `src/demoFlag.d.ts` records the three forms of this flag that did NOT fold, and the one
 * orphan chunk that is still emitted.
 *
 * A BUILD-TIME CONSTANT AND NOT A RUNTIME FLAG, deliberately. A runtime switch would mean the
 * real app carries a code path that answers from a recording, one misconfiguration away from
 * showing the owner a frozen store while their real one sat behind it — and D43 exists
 * because a UI answering from the wrong store is this repo's most expensive class of bug.
 */
const DEMO = __BN_DEMO__

/* NOT EXPORTED, AND THAT IS LOAD-BEARING. Two other modules need this same flag —
 * `useCamera.ts` and `OrdersShipStage.tsx`, both driven by hardware or by a file a viewer
 * does not have — and each declares its own from `import.meta.env.VITE_DEMO` rather than
 * importing this one. An imported constant stays a live binding across the module boundary
 * and does not fold, so the guarded branch survives and its chunk is emitted: exporting this
 * put `demoCamera-*.js` into an ordinary production build, measured. Keep every guard
 * local. */

/* Resolved once, on first use. `demoRequest` is reached only through this, so the chunk is
 * fetched when the demo makes its first call and never in a build where DEMO is false. */
let demoModule: Promise<typeof import('./demoServer')> | null = null

/**
 * Every failure out of this module, without exception — a refusal the server named, a
 * network that did not answer, a body that did not parse. Components catch one type and
 * show `message`; anything that wants to branch reads `code`.
 */
export class ServerError extends Error {
  /** The server's own code (`box_invalid`, `store_busy`, `card_not_found`, …), or one of
   *  the three this client invents when there is no server answer to quote: `unreachable`,
   *  `origin_blocked` and `bad_response`. Codes are stable strings and are worth branching
   *  on; messages are worth showing.
   *
   *  `origin_blocked` is the newest and the only one that is a CLAIM ABOUT THE SERVER rather
   *  than about this client: it is raised when a request was refused by the browser before it
   *  was sent, AND a plain read still answers — so the server is up and this page's address
   *  is what it will not accept. It was `unreachable` until 2026-09-06, which sent the
   *  operator to restart a server that was running. */
  readonly code: string

  /** The HTTP status, or 0 when no response arrived at all. Zero rather than a plausible
   *  502: an invented status would be indistinguishable from one the server sent, and this
   *  is the case where nothing was sent. */
  readonly status: number

  constructor(code: string, message: string, status: number) {
    super(message)
    this.name = 'ServerError'
    this.code = code
    this.status = status
  }
}

/** A refusal in the shape an owner-side screen draws it: the sentence it shows, and the code
 *  it prints small beneath — docs/DESIGN.md's human-label-large, machine-string-small rule. */
export type Failure = { code: string; message: string }

/**
 * Any thrown thing, as an owner-side screen shows it.
 *
 * THE SERVER'S OWN MESSAGE, VERBATIM, which is the rule this whole module is built on:
 * `server/capture_server.py:_fail` already says what happened and what to do next, holding
 * facts this side of the wire does not have. The second branch is for something that threw
 * inside the client before the server could answer — and it deliberately does NOT point at
 * `make server`, because `request()` above has already converted a dead server, a wrong
 * address and a CORS refusal alike into `ServerError('unreachable', …)`. Anything reaching
 * the fallback is a bug in the app, and sending the operator to the terminal for it sends him
 * to the one place the fault is not. It keeps a branch rather than being dropped, because a
 * screen that renders nothing while something is broken is worse than one that names it, and
 * `client_bug` greps to this line and to no server route.
 *
 * THREE SCREENS CARRIED A BYTE-IDENTICAL COPY OF THIS UNTIL 2026-08-13. PullPreview.tsx wrote
 * it; ReviewQueue.tsx and Inventory.tsx copied it, and both named this file as where it
 * belonged and another group's ownership as why it could not go there that session.
 * Inventory.tsx set the threshold as well — "worth doing when a third screen needs it, not
 * before". A third screen needed it, and both conditions were met at once, so it moved here
 * rather than gaining a fourth copy.
 *
 * FULFILLMENT.TSX DOES NOT USE IT, and that is a policy difference rather than an oversight.
 * That view may not show a server message at all: those strings name routes, states and
 * `make` commands, every one of them correct and none of them the Fulfiller's (D5). It writes
 * its own sentences and the register note at the top of that file argues why. Do not
 * "finish the job" by wiring this into it.
 */
export function describeFailure(err: unknown): Failure {
  if (err instanceof ServerError) return { code: err.code, message: err.message }
  const detail = err instanceof Error ? err.message : String(err)
  return {
    code: 'client_bug',
    message:
      `The app failed before the capture server could answer: ${detail}. That is a bug in ` +
      'the app rather than a refusal — check the browser console.',
  }
}

/**
 * Where a stored capture can be seen. D6's route, and the reason it exists.
 *
 * `CardSummary.photo` and `InventoryCard.photo` are paths on the Mac's disk — a browser
 * cannot load one, and building a `file://` URL from it fails silently in a way that looks
 * like a missing photo. This is the only way to display a capture.
 *
 * THE HAZARD THAT SHAPED THIS FUNCTION IS ANSWERED BY THE ADDRESS NOW (D172), AND THE
 * MEASUREMENT THAT PROVED IT STAYS. What D52 recorded is not rewritten: the owner reported a
 * delete that "doesn't kick in super quickly ... it makes you think you need to delete more",
 * and measured against a copy of their store, deleting box 2's card 180 shifted 363 cards in
 * 288 ms while the screen went on drawing the DELETED card's photograph at `transferSize: 0`
 * — served out of Chrome's in-document memory cache, which consults neither the ETag nor
 * `no-cache`. Three operations put a different card in one slot: D10 ruling 1's mid-box delete
 * slides every higher card down an index, D10's undo releases an index the next capture reuses,
 * and D26's re-shoot replaces the bytes outright.
 *
 * WHAT CHANGED IS NOT THE HEADER BUT THE NAME. This paragraph used to argue that a caller
 * "may say so in the URL" with `?card=<capture_id>`, because a header cannot make an `<img>`
 * React keeps in the document ask again and does not reach that memory cache. That was a
 * client-side patch over a server-side conflation, and the conflation is gone: the photograph
 * is FILED under the card's own name and `GET /photo/by-card/<cid>` serves it. The URL means
 * one thing forever — a mid-box delete does not change it, an undo does not change it, and two
 * cards cannot share it because `cards_cid` is UNIQUE — so a cache hit is always the right
 * bytes and the validator is a formality rather than the only defence. No caller has to know
 * which capture it is drawing, because the address says.
 *
 * THE SLOT ROUTE IS THE FALLBACK AND IT IS NOT DEPRECATION THEATRE. `runs/<n>/pricing.json`
 * holds 3,629 position records across 12 immutable files, 0 of which carry a cid, and
 * `#/pricing?run=<n>` is the screen that draws them — so a row whose cid the wire did not
 * carry (a run's frozen positions, a queue entry, a code-card ledger line, an order pick, a
 * deck built from box records alone) addresses the slot, exactly as it always did. The call
 * sites that do that say so in a comment beside the call; none of them is an oversight.
 *
 * A `cid` THE ROUTE CANNOT SERVE FALLS BACK RATHER THAN 404ING, and the test is the route's
 * own pattern rather than a second copy of `store/photos.py:is_photo_cid`. A cid comes in four
 * shapes and only two name a photograph: `<64 hex>` and `<64 hex>-<n>` do, `moved:<…>` (a D83
 * tombstone) and `nophoto:<box>/<index>@<stamp>` do not. `_copy_row` applies that predicate
 * server-side before it puts a cid on a `SearchCopy`; `_card_row` does NOT, because it ships
 * `asdict(card)` raw — so an `InventoryCard` really can arrive carrying `moved:…`, which
 * `_PHOTO_BY_CARD_RE` refuses at the router. Both populations are 0 today, which is exactly
 * why the guard is written down instead of discovered. One place, so no caller has to know the
 * four shapes.
 */
const PHOTO_CID = /^[0-9a-f]{64}(?:-[1-9][0-9]*)?$/

export function photoUrl(box: number, index: number, cid?: string | null): string {
  /* THE DEMO BUILD HAS NO PHOTO SERVICE, so the same address resolves to a bundled file.
   * `BASE_URL` rather than a leading slash: a static host serves the demo from a
   * subdirectory (`/banchi/` on GitHub Pages), and an absolute path would 404 on every
   * photograph there while working perfectly at the root — the failure that only appears
   * once it is published. `.jpg` is appended here and nowhere else; the seed writes the
   * store index undecorated, so this stays D52's contract exactly.
   *
   * THE CID IS IGNORED HERE, DELIBERATELY AND FIRST. `scripts/demo-seed.py` writes
   * `demo/photos/<box>/<index>.jpg` and nothing else, so addressing a name in the demo would
   * 404 every photograph on the published page. Moving the demo onto the name is a
   * coordinated change to the seed and the recorded bundle, not a change to this line. */
  if (DEMO) return `${import.meta.env.BASE_URL}demo/photos/${box}/${index}.jpg`
  if (cid !== undefined && cid !== null && PHOTO_CID.test(cid)) {
    return `${base}/photo/by-card/${cid}`
  }
  return `${base}/photo/${box}/${index}`
}

/**
 * The position label the server rendered, or null when it sent none.
 *
 * `pipeline/join.py:Position.label` composes `Box 3 · Section 2 · Card 17` against the
 * box's own dividers (D10) and `do_inventory` decorates every row it can with the result.
 * The rule types.ts states on that field is that the app displays this string and never
 * composes a second one — a client-side renderer is a copy of a rule that nothing keeps in
 * step with the pipeline's, and the rule has now moved once: the 25-cards-per-divider
 * default an undeclared box used to render with was deleted on 2026-08-29, and every screen
 * drawing the server's string followed it without an edit.
 *
 * MISSING IS RETURNED AS NULL, NEVER FILLED IN, and what a caller shows instead is the
 * caller's decision: the pull preview and the inventory view both print the store key with
 * the words `no label` in front of it, because `3/30` bare reads like a position and is not
 * one. `do_inventory` leaves a row undecorated when its box or index will not coerce, on the
 * grounds that a placeholder would name a position that does not exist; this function is
 * where that refusal survives the trip.
 *
 * THE `typeof` CHECK IS NOT REDUNDANT WITH `label?: string` AND MUST NOT BE DELETED AS THOUGH
 * IT WERE. The type describes the contract; this describes the process actually answering on
 * :8000, and during an upgrade — an older capture server still running on the Mac — those are
 * different things. This module casts rather than validates, by the decision recorded below,
 * so a field the running server omits arrives under a type that says otherwise. It also does
 * work the type cannot: `''` is a `string` and not a label.
 *
 * Two screens carried identical copies of this until 2026-08-13. It is one rule about one
 * field, so it is one function.
 */
export function positionLabel(card: { label?: string }): string | null {
  const { label } = card
  return typeof label === 'string' && label.trim() !== '' ? label : null
}

/** A record that has left its box — sold or retired — as its place block says it (D68).
 *
 *  TWO TESTS, BECAUSE `Place.slot` HAS TWO CAUSES AND ONLY ONE OF THEM IS THIS ONE. `types.ts`
 *  states both on the field: it is null for a card that has left, and null for one the server
 *  could not count. The second answers `label: null` with it — there is no honest label when the
 *  cards could not be counted — so the label is exactly what tells a design fact from a fault,
 *  and every screen has a different thing to draw for each. `located` keeps a pooled block out:
 *  D24 gives one no slot at all, and it has never had one to lose.
 *
 *  ONE PREDICATE FOR THREE READERS, and the reason it is here rather than in any of them is
 *  `isPooled` two screens over — that one IS written twice, once in `BoxBrowse.tsx` and once in
 *  `CardLocations.tsx`, because neither could import the other's on the day it was written. This
 *  module is what both already import for `positionLabel` above, so the third copy is not
 *  written. */
export function isDeparted(place?: { located?: boolean; slot?: number | null; label?: string | null }): boolean {
  if (place === undefined) return false
  return place.located !== false && place.slot === null && positionLabel({
    label: place.label ?? undefined,
  }) !== null
}

/** D30's neighbours, as records rather than as substrings of an English sentence.
 *
 * `Card 19` is the nineteenth card in the box, and the neighbours are what let a hand count
 * to it without anyone learning that rule. `prev` is the card in front of this one and `next`
 * the card behind it; either is null past the box's ends, and both null together when the
 * server sent no decoration (an older server) or nulled it — a record in the store whose
 * position will not read, the same event that nulls the denominator. A sentence naming a
 * possibly-wrong neighbour would send a hand to the wrong slot, which is the one thing a
 * position claim may never do, so that case renders nothing at all.
 *
 * `said` IS THE SAME FACT JOINED, AND IT IS COMPOSED IN THIS BODY SO THE TWO CANNOT DISAGREE.
 * The Fulfiller's card draws it verbatim at `.card-locations-say`, and the owner's ranked
 * block carries it on `aria-label` — so what a screen reader announces is one sentence even
 * where the eye is given two rows. That is `PositionLabel`'s split against `Position.label`,
 * one line down: the renderer takes GEOMETRY and never VOCABULARY.
 *
 * WHY PARTS AT ALL. The connectives are the separators and the names are the payload, and a
 * screen cannot rank what it can only read as a run of words. Splitting `said` in the
 * renderer was the alternative and is worse: `PositionLabel` may parse `Position.label`
 * because that string comes off the WIRE, and this one is composed here — parsing your own
 * output is a second author of the same words wearing a regex.
 *
 * THE GAP CLAUSE IS GONE (owner, 2026-08-30). It read "2 slots in this section are empty",
 * counted from `Place.section_gaps`, and D58 already claimed it was structurally empty:
 * "`section_gaps` is structurally zero for a consolidated box and `placeSentence` already
 * omits the phrase at zero". It is not zero — `_company` counts the terminal records between
 * the section's bounds — so box 1, which has sold two, drew the clause on EVERY card in it.
 * Under D58 the box closes up, so `Card 19` really is the nineteenth card a hand can count
 * to, and the clause's one stated job in D30 — saying why a hand-count came out short — is
 * void. Measured on the owner's store before it went: it cost 15px on every copy row in a box
 * that had ever had a sale, and it was the reason the line wrapped to three lines at all.
 *
 * A NEIGHBOUR NOTHING HAS IDENTIFIED IS NO LONGER A NEIGHBOUR AT ALL (D116). It used to
 * degrade to its slot — `#41`, and to its INDEX before D92 — which is a live card at a real
 * count and was read as a sold card leaking into the ladder. It is neither: it is a card on
 * the shelf that no identification ever named, seven of them on the owner's store, all seven
 * queued and closed under D37. The server now walks past it to the nearest card it CAN name
 * and says how many it passed, so the fallback below fires only for an older server.
 *
 * THE SKIP IS SAID RATHER THAN SWALLOWED. A landmark two cards away instead of one is a
 * sentence somebody counts slots against and comes out one short, which is the one thing
 * D30 says this sentence may never cause — so `said` carries the count, in the joined form
 * the Fulfiller reads at 20px, and the ranked block draws it per side. */
export type PlaceParts = {
  prev: PlaceNeighbor | null
  next: PlaceNeighbor | null
  said: string
}

export function placeParts(place: Place | undefined): PlaceParts | null {
  if (place === undefined || place.located === false) return null

  const neighbors = place.neighbors
  if (neighbors === undefined || neighbors === null) return null

  const { prev, next } = neighbors
  const name = (side: PlaceNeighbor): string => side.name ?? `#${side.slot}`

  let said: string
  if (prev !== null && next !== null) said = `between ${name(prev)} and ${name(next)}`
  else if (prev !== null) said = `after ${name(prev)}`
  else if (next !== null) said = `before ${name(next)}`
  /* The one card whose box holds nothing else — and, since D116, a card with no NAMED card
     either side of it. No neighbours is no content, and null lets a screen render nothing
     rather than chrome. */
  else return null

  /* THE SKIPPED CARDS ARE STATED, AND ONE CLAUSE COVERS BOTH SIDES: every card the walk
     passed over lies strictly between the two landmarks named above, whichever side it was
     on, so "with 1 unidentified card in between" is exact for a one-sided skip and for a
     two-sided one alike. Drawn only when it fires — 27 rows on the owner's store — because a
     clause on every row is the gap clause the owner had removed in 2026-08-30. */
  const skipped = (prev?.skipped ?? 0) + (next?.skipped ?? 0)
  if (skipped > 0) {
    said += `, with ${skipped} unidentified card${skipped === 1 ? '' : 's'} in between`
  }

  return { prev, next, said }
}

/** The joined sentence, for the caller that wants one.
 *
 * `#/fulfillment` renders this at `.card-locations-say` — 20px body, one size, no muted
 * variant — and `app/tests/fulfillment.spec.ts` floors it, so the string form is load-bearing
 * and may not be deleted in favour of the parts. It is also every ranked block's
 * `aria-label`. Kept as its own export rather than inlined at the call sites: it is the shape
 * three screens have imported since 2026-08-13.
 *
 * At the box's ends there is one neighbour and it says which side (`after Mantine` /
 * `before Thievul`) rather than pretending a between. */
export function placeSentence(place: Place | undefined): string | null {
  return placeParts(place)?.said ?? null
}

// ------------------------------------------------------------------------------ the wire

/* A sentinel rather than `undefined` or `null` for "did not parse", because `null` is a
 * legitimate JSON document and the two must not collapse into one branch. */
const NOT_JSON = Symbol('not-json')

function parseJson(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return NOT_JSON
  }
}

/* `{"error": {"code", "message"}}` — the shape EVERY refusal from this server takes.
 *
 * Read defensively field by field rather than cast, because this runs on the error path:
 * a `body.error.code` on a body that is a bare string throws a TypeError, and a second
 * failure raised inside the handler for the first is how a `store_busy` gets reported to
 * the operator as "undefined is not an object". Returns null and lets the caller fall back
 * to the status line instead.
 */
function errorEnvelope(body: unknown): { code: string; message: string } | null {
  if (typeof body !== 'object' || body === null) return null
  const wrapped: unknown = (body as { error?: unknown }).error
  if (typeof wrapped !== 'object' || wrapped === null) return null
  const { code, message } = wrapped as { code?: unknown; message?: unknown }
  if (typeof code !== 'string' || typeof message !== 'string') return null
  return { code, message }
}

/* WHICH PROCESS IS ANSWERING, observed on traffic the app is already making (D73).
 *
 * D73 AND NOT D53, WHICH IS THE ENTRY THIS COMMENT CITED UNTIL 2026-08-30. D53 is the
 * supervisor, the watcher and the restart — the thing this header lets you SEE. It never
 * ruled on the header, and D73 checked that three ways before repointing seven comments.
 *
 * `make up` restarts the capture server on every Python edit, and a restart is otherwise
 * invisible from here — same port, same store. The alternative was a component polling
 * `/status` on a timer, and it was built that way first: it worked, and it made every
 * owner-side screen issue a request nothing had asked for in every Playwright spec, against
 * whatever real server happened to be listening. `app/tests/inventory.spec.ts` documents that
 * hazard in its own comment. A header rides requests that were happening anyway, so it costs
 * nothing and contaminates no test.
 *
 * THIS MODULE IS THE RIGHT HOME because it is the only one that talks to the capture server —
 * the same reason the failure vocabulary lives here. One observation point, and no screen has
 * to remember to participate.
 *
 * Listeners rather than a returned value: every caller of `request` wants its body, and
 * threading a second concern through forty call sites to serve one notice is the coupling this
 * avoids. */
type BootListener = (bootId: string) => void
const bootListeners = new Set<BootListener>()
let lastBoot: string | null = null

export function onServerBoot(listener: BootListener): () => void {
  bootListeners.add(listener)
  return () => {
    bootListeners.delete(listener)
  }
}

function noteBoot(response: Response): void {
  const seen = response.headers.get('X-Pkmnscan-Boot')
  /* A server that does not send it says nothing. Absent means either a server predating the header
   * or — far more likely in a test — a stubbed route, and inventing a reload from a missing
   * header would make every spec that stubs the wire report one. */
  if (seen === null || seen === '') return
  if (lastBoot === null) {
    lastBoot = seen
    return
  }
  if (lastBoot === seen) return
  lastBoot = seen
  for (const listener of bootListeners) listener(seen)
}

/* Is the server up at all? Deliberately RAW `fetch` rather than `request()` — this is called
 * from inside `request()`'s own failure path, and routing it back through would recurse. No
 * headers and no init: anything else (a `Content-Type`, a cache directive) would make it a
 * preflighted request and it would fail for the very reason it exists to rule out. */
async function serverAnswersReads(): Promise<boolean> {
  try {
    const response = await fetch(`${base}/status`)
    return response.ok
  } catch {
    return false
  }
}

/* The address in the phone's address bar, which is the thing being refused and the thing the
 * operator has to recognise. Guarded for the non-browser callers `sameHostBase` already names
 * — `tsc`, the specs' module imports, an editor's type server — where there is no address bar
 * to quote. */
const pageOrigin = (): string =>
  typeof window !== 'undefined' && window.location ? window.location.origin : 'this page'

async function request(path: string, init?: RequestInit): Promise<unknown> {
  /* THE ONE SEAM. Every client function in this module funnels through here, so this branch
   * is the whole of what makes a published demo possible — no screen, no hook and no kit
   * component knows which of the two it is talking to. Folded away entirely when DEMO is
   * false; see its declaration above. */
  if (DEMO) {
    demoModule ??= import('./demoServer')
    return (await demoModule).demoRequest(path, init)
  }

  const url = `${base}${path}`

  let response: Response
  try {
    response = await fetch(url, init)
    noteBoot(response)
  } catch {
    /* INVENTED MESSAGE #1. `fetch` rejects without detail for a dead server, a wrong
     * address and a CORS refusal alike — the browser withholds which on purpose — so this
     * used to name the likeliest cause and the command that fixes it. The comment that stood
     * here predicted the defect below and shipped it anyway: "a preflight refusal reads
     * exactly like this, so a new method that the server's `Access-Control-Allow-Methods`
     * does not list will present as the server being down."
     *
     * IT IS NOT A GUESS ANY MORE, BECAUSE THE SERVER IS STILL ASKABLE. The browser withholds
     * the reason for THIS request; it does not stop us asking a different question. A write
     * from an origin the server does not know is refused by the BROWSER at the preflight —
     * measured on the rig, an unknown origin is answered `Access-Control-Allow-Methods:
     * GET, HEAD, OPTIONS` — so the request is never sent and the 403's own message, which names
     * the remedy, is never delivered to the page.
     *
     * `GET /status` settles it, and it is the one probe that can: no custom headers, so it
     * is a SIMPLE request and exempt from preflight, and reads are ungated and answered
     * `Access-Control-Allow-Origin: *` (D43). It therefore answers whenever the server is up
     * AT ALL — including from an origin that may not write. An answer here means the server
     * is alive and it is this ADDRESS that is being refused.
     *
     * The distinction is worth a round trip on a path that has already failed, because the
     * two remedies point at different places. `unreachable` sends the operator to start a
     * server; on the phone that server is already running, and the shell's own status dot
     * is saying `Server online` — off the very same ungated read — while the write claims it
     * is down. The app was contradicting itself at the moment it was least able to explain. */
    const answering = await serverAnswersReads()
    if (answering) {
      throw new ServerError(
        'origin_blocked',
        `The capture server at ${base} is running, but it will not accept changes from ` +
          `${pageOrigin()}. Nothing was saved. Restarting the server will not help — the ` +
          'address this page was opened at has to be one it allows. On the Mac, set ' +
          'PKMNSCAN_LAN_NAME in .env to this address\u2019s host name and start it again.',
        0,
      )
    }
    throw new ServerError(
      'unreachable',
      `No answer from the capture server at ${base}. It may not be running — ` +
        'start it with `make server`, then try again.',
      0,
    )
  }

  let text: string
  try {
    text = await response.text()
  } catch {
    /* The same code, because the remedy is the same one: the exchange did not complete and
     * the request should be repeated. For a capture, repeat it with the SAME capture_id —
     * this is precisely the lost-response case the retry guard exists for. */
    throw new ServerError(
      'unreachable',
      `The connection to the capture server dropped while reading its answer to ${path}. ` +
        'Retry the request.',
      response.status,
    )
  }

  const body = parseJson(text)

  if (!response.ok) {
    const named = errorEnvelope(body)
    if (named !== null) throw new ServerError(named.code, named.message, response.status)
    /* Not from this server, then — a proxy, or a dev-server 404 from a misconfigured base
     * URL. The status line is all there is, so quote it with the URL that produced it
     * rather than inventing an explanation for a response nobody in this repo wrote. */
    throw new ServerError(
      'http_error',
      `${response.status} ${response.statusText} from ${url}.`,
      response.status,
    )
  }

  if (body === NOT_JSON) {
    /* INVENTED MESSAGE #2. A 2xx whose body is not JSON is a bug in the server or in
     * something sitting in front of it. Loud, per section 5.5, rather than returned as an
     * empty object that a screen renders as blanks. */
    throw new ServerError(
      'bad_response',
      `The capture server answered ${response.status} for ${path} with a body that is not ` +
        'JSON. This is a bug — check the server log.',
      response.status,
    )
  }
  return body
}

/* The reads are polled — the box list comes from /status — so they must not be answered
 * from the HTTP cache. The server sends no cache headers at all, which leaves the decision
 * to a heuristic; this takes it back. */
const NO_CACHE: RequestInit = { cache: 'no-store' }

/* Every function below casts rather than validating field by field.
 *
 * The alternative — a runtime schema check per route — was rejected because it is a second
 * copy of a contract that lives one directory away in this same repo, and a second copy is
 * a thing that drifts. What it would catch is the server changing shape, which is a bug in
 * `server/capture_server.py` that T7 is the right place to catch; what it would cost is a
 * validator to maintain in step with every field the pipeline adds to a card. This is a LAN
 * tool talking to a process on the same Mac, not a client parsing input from a stranger.
 */

/** Counts, store health, and the boxes already in use. */
export async function getStatus(): Promise<ServerStatus> {
  return (await request('/status', NO_CACHE)) as ServerStatus
}

/** The whole card map. Keyed `"<box>/<index>"`. */
export async function getInventory(): Promise<Inventory> {
  return (await request('/inventory', NO_CACHE)) as Inventory
}

/**
 * Take a photo into the next position in a box.
 *
 * The argument is camelCase and the wire is snake_case; the mapping happens here and only
 * here. That inconsistency is deliberate — the wire types in types.ts keep the server's own
 * field names so a screen can be held against `inventory.json`, while this is an ordinary
 * TypeScript call site with no record on the other side of it.
 *
 * `imageBase64` is RAW base64 with no `data:` prefix, which is what
 * `useCamera.grabFrameJpeg()` returns. This module does not helpfully strip a prefix if one
 * arrives: the server refuses it as `image_invalid`, loudly and at the first capture, and a
 * client that quietly accepted both shapes would let the wrong one spread to every caller.
 *
 * `captureId` is REQUIRED, not defaulted. Minting one inside this function would be worse
 * than not having the guard at all, because every call would carry a different id and the
 * replay path would never fire while looking like it was covered. The id must be held by
 * the caller across a retry of the SAME photo — that is what makes a lost response
 * recoverable: the server returns the original card with `created: false` and burns no
 * index. It is one request retried, never a queue (section 5.5), and the retry is the
 * operator pressing again rather than anything this module does on its own.
 */
export async function capture(input: {
  box: number
  imageBase64: string
  /* REQUIRED, unlike the two claims below it, and the asymmetry is D21's. A finish or a
   * set hint the operator did not set is a real state — no claim — with a ladder underneath
   * it that infers one. There is no ladder that infers a game, so a missing game is not "no
   * claim", it is "no export", and every consumer downstream would have nothing to join
   * against. The picker always has an answer, so this argument always has one too.
   *
   * `string` and not a union: the registry is served by `GET /games` and never mirrored on
   * this side, so the app has no compile-time list of games to narrow against. The server
   * refuses an unregistered key as `game_invalid`. */
  game: string
  setHint?: string
  /* D3 rung 1's finish claim, and A LIST since the amendment of 2026-08-23 — one member
   * determines, two or more filter the candidate rows and let the rungs below choose within
   * what survives. The server still accepts a bare string and reads it as one member (every
   * record written before the amendment carries one, and there is no migration), but nothing
   * on this side sends one any more: `FinishClaim` is the array, so the one shape the screen
   * can hold is the one shape the wire gets. An empty or absent claim is no claim at all. */
  variant?: readonly Finish[]
  /* D23's multi-select stack claim: the exact Rarity cells of the chosen game, as `GET
   * /games` spells them. A LIST on the wire — the server refuses a bare string as
   * `rarity_claim_invalid` rather than iterating it into six one-letter rarities, and an
   * empty or absent list is no claim at all: no key is sent, nothing lands on the record,
   * and the ladder walks exactly as it did before the field existed. */
  rarityClaim?: readonly string[]
  captureId: string
  /* C10's product claim: which sealed product this code card came out of. Optional and
   * NEVER defaulted — `undefined` sends no key at all, so the sidecar records no product and
   * the Codes screen counts the card as unclaimed rather than filing it as a booster. Only
   * the game named by `GameRegistry.product_game` uses it; sending it for another game is
   * refused by the server as `product_invalid` rather than ignored. */
  product?: string
}): Promise<CardSummary> {
  const payload: Record<string, string | number | readonly string[]> = {
    box: input.box,
    image: input.imageBase64,
    capture_id: input.captureId,
    game: input.game,
  }

  /* Omitted rather than sent empty, matching `sidecar_payload`'s rule on the other side:
   * the file stays a record of claims the operator actually made (D3 rung 1). The server
   * treats absent and null alike, so this costs nothing and keeps the two in step.
   *
   * `note` IS NOT SENT HERE AT ALL, and its absence is a decision rather than an omission.
   * It is free text a human types, the feeder emits a card every ~623 ms, and a control
   * that had to be filled in before the shutter would put a keyboard on the critical path
   * of the run. It goes through `updateCard` afterwards, against a position that exists. */
  const hint = input.setHint?.trim()
  if (hint) payload.set_hint = hint
  if (input.variant && input.variant.length > 0) payload.variant = input.variant
  if (input.rarityClaim && input.rarityClaim.length > 0) payload.rarity_claim = input.rarityClaim
  if (input.product) payload.product = input.product

  /* 201 on a new card, 200 on a replay. Neither is inspected: `created` in the body says
   * the same thing in the shape the screen already reads. */
  return (await request('/capture', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })) as CardSummary
}

/**
 * Correct a capture claim on one card that already exists.
 *
 * THIS ROUTE CORRECTS AND NEVER CREATES. A position with no record answers `card_not_found`
 * rather than being invented, which is what makes it safe to call from a screen holding a
 * position it read a moment ago.
 *
 * A FIELD LEFT OUT IS LEFT ALONE; A FIELD SENT `null` IS CLEARED. Those are two different
 * requests and this function keeps them apart with `in` rather than a truthiness test — a
 * screen clearing a set hint back to no claim sends `null` and means it, and folding that
 * into "absent" would make the claim unclearable. `game` has no null form: D21 makes it
 * required, so there is nothing to clear it to.
 *
 * `note` IS THE ONE CLAIM THAT IS ONLY EVER SET HERE. The capture body does not carry it,
 * deliberately: the operator types it AFTER the shutter, against a card that is already
 * photographed and recorded, so a keyboard never sits on the critical path of a feeder run.
 * A card whose note arrives a minute later — or never — is a perfectly good record.
 *
 * IT REWRITES THE SIDECAR TOO, server-side, and that is why a correction made here reaches
 * the variant ladder: `cli/cmd_identify.py` builds its card from the sidecar and not from
 * `inventory.json`.
 */
export async function updateCard(
  box: number,
  index: number,
  fields: {
    setHint?: string | null
    /** D3's finish claim, a list since 2026-08-23. `null` CLEARS it, which is why the union
     *  keeps a null the capture argument above does not need: `'variant' in fields` is what
     *  decides whether the key is sent at all, and a key present with null is the clear. */
    variant?: readonly Finish[] | null
    game?: string
    /** D23's stack claim. IT WAS MISSING HERE while the route had always accepted it —
     *  `PUT_FIELDS` is built from `master.CAPTURE_CLAIM_FIELDS`, which has carried
     *  `rarity_claim` since the claim shipped, so the one claim a correction is most likely
     *  to be ABOUT was the one no screen could correct. */
    rarityClaim?: string[] | null
    /** C10/D70's product claim: which sealed product this code card came out of. A key out of
     *  `GET /games`'s `products`, and `null` CLEARS it back to no claim.
     *
     *  IT WAS SETTABLE AT CAPTURE AND CORRECTABLE NOWHERE, which is `rarityClaim`'s note one
     *  claim later and with more riding on it: the route has accepted `product` since D70,
     *  `#/codes` draws a banner counting the codes that carry none, and neither lane will
     *  take one — so the claim the product most needs corrected was the one no screen could
     *  write.
     *
     *  A KEY OUTSIDE THE VOCABULARY IS THE SERVER'S REFUSAL TO MAKE (`product_invalid`, 400),
     *  not this function's. Checking it here would give the vocabulary a second home that has
     *  to agree with `codes/products.py`, and every screen that offers the picker is served
     *  the real one by `GET /games`. */
    product?: string | null
    note?: string | null
  },
): Promise<CardSummary> {
  const payload: Record<string, string | readonly string[] | null> = {}
  if ('setHint' in fields) payload.set_hint = fields.setHint ?? null
  if ('variant' in fields) payload.variant = fields.variant ?? null
  if ('game' in fields && fields.game !== undefined) payload.game = fields.game
  if ('rarityClaim' in fields) payload.rarity_claim = fields.rarityClaim ?? null
  if ('product' in fields) payload.product = fields.product ?? null
  if ('note' in fields) payload.note = fields.note ?? null

  return (await request(`/inventory/${box}/${index}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })) as CardSummary
}

/**
 * Undo: remove one card's record, sidecar and photo.
 *
 * Takes the position explicitly rather than meaning "the newest". The server refuses
 * anything but the newest card in that box, and names in the refusal which position IS
 * undoable — but the screen has to show what it is about to delete before it is pressed
 * (section 5.4: an undo you can aim, not one you fire hopefully), and a call that could
 * only say "newest" gives it nothing to show.
 *
 * Repeated calls walk backwards one card at a time. That falls out of the newest-only rule
 * rather than needing anything here.
 *
 * It deletes; it does not tombstone (D10). One tap and no dialog is the owner's ruling, on
 * the grounds that the card is still physically in your hand — the remedy for a wrong undo
 * is to photograph it again.
 */
export async function undoCapture(box: number, index: number): Promise<{ deleted: string }> {
  return (await request(`/inventory/${box}/${index}`, { method: 'DELETE' })) as {
    deleted: string
  }
}

/**
 * Replace the photo and sidecar at an existing position. The record is untouched.
 *
 * D26's re-shoot in place: a bad photograph discovered later than D10's undo can reach —
 * undo walks back only the newest capture — gets new bytes at the SAME position, position
 * label unchanged, allocator never involved. NOT A DELETE, NOT A CAPTURE, and irreversible
 * in one specific way: the old bytes are replaced, not archived (an archived copy under the
 * capture root would be scanned as a capture and billed as one), so the remedy for a wrong
 * re-shoot is another re-shoot.
 *
 * IT CANNOT CARRY A CORRECTION, by the server's own refusal (`field_not_settable`): the
 * sidecar is rebuilt from the RECORD, never from the request, so changing what the operator
 * said about the card stays `updateCard`'s job with its `corrected` history line. This call
 * changes the picture and nothing else.
 *
 * `imageBase64` is RAW base64 with no `data:` prefix, exactly as `capture` takes it and for
 * its reason: the server refuses a prefixed blob as `image_invalid`, loudly, rather than
 * letting two shapes spread. `captureId` is REQUIRED and is the NEW photograph's — one id
 * per photograph, minted fresh (`newCaptureId`) and held by the caller across any retry of
 * the SAME bytes, which is what makes a lost response a recognisable replay instead of a
 * second write.
 *
 * The refusals worth branching on are `card_sold` and `card_retired` — a photo of a card
 * that left is a photo of nothing, and for a sold card the stored photo is the dispute
 * record — but the screen that offers this control should not draw it for either state in
 * the first place, for the reason `restores_to` taught twice: a control whose only
 * behaviour is a refusal. `capture_id_in_use` means the id names another card's photograph;
 * mint a new one rather than retrying with it.
 */
export async function reshootPhoto(
  box: number,
  index: number,
  imageBase64: string,
  captureId: string,
): Promise<CardSummary> {
  return (await request(`/inventory/${box}/${index}/photo`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ image: imageBase64, capture_id: captureId }),
  })) as CardSummary
}

// --------------------------------------------------------- the standing queues, and D4's answer

/**
 * Both standing queues, in the order they are meant to be worked.
 *
 * THE ORDER IS THE PAYLOAD'S WHOLE POINT AND IS NEVER RECOMPUTED ON THIS SIDE.
 * `store/queues.py:Queue.open_entries` sorts priced first and descending, unpriced last, then
 * box-walk order — the same sort every run report has already printed. An app-side re-sort
 * would be a second copy of `QueueEntry.sort_key` one edit away from disagreeing with the
 * report the owner read before he opened the screen.
 *
 * Cleared entries are absent rather than flagged: the route serves `open_entries`, which is
 * "what is left to do", and an answered card is not that.
 *
 * Two lists and not one. The split is the point (`store/queues.py`): main is work, parked is
 * the low-value queue an unidentifiable card may never be worth a tap on. Concatenating them
 * here would put the merge in the one module that cannot see why they are separate — the
 * screen does it, deliberately and in one function it can argue for.
 */
export async function getQueues(): Promise<QueueSnapshot> {
  return (await request('/queues', NO_CACHE)) as QueueSnapshot
}

/**
 * D4's one-tap choice: one candidate row, chosen, written onto the card.
 *
 * `condition` TRAVELS WITH `sku` EVEN THOUGH THE SKU IMPLIES IT, and this client does not
 * derive it. The route checks the pair against the row it offered, so that a screen drawn
 * from a queue file a later join has rewritten is caught rather than obeyed; a condition
 * composed here would be self-consistent every time and would turn a stale click into a
 * wrong finish on a real card. Both values are copied off the row that was pressed.
 *
 * The refusals worth branching on are `already_answered` and `not_in_queue` — the two-device
 * case (D5, D13) and a client asking about the wrong card. They are two codes rather than one
 * because the remedies differ, and the screen reads `ServerError.code` to tell them apart.
 *
 * Answers one entry, never a batch. `Store.write()` takes the file lock per call, so a caller
 * that fires several at once stacks writes against a lock and gets their failures back out of
 * order — the review screen serialises for exactly that reason.
 *
 * READ `restores_to` ON THE ANSWER BEFORE DRAWING AN UNDO, which is the whole reason this now
 * returns a named type rather than the one field it used to. Null is the server saying in
 * advance that `undoAnswer` below will refuse. Present is the pair the reversal puts back, and
 * both of its members are null for the ordinary case of a card that carried no SKU before —
 * so it is read as present-or-null and never for its contents.
 */
export async function answerReview(answer: ReviewAnswer): Promise<AnswerResult> {
  const { box, index, sku, condition, fromCatalog } = answer
  // `from_catalog` is sent only when it is true. The route allowlists the field either way,
  // but an ordinary answer that carried `from_catalog: false` would put a flag about D46 on
  // every one of the thousands of answers that have nothing to do with it.
  return answerCall(
    box,
    index,
    fromCatalog ? { sku, condition, from_catalog: true } : { sku, condition },
  )
}

/**
 * What this card COULD be, out of the export it was actually joined against (D46).
 *
 * FREE, READ-ONLY, AND IT ANSWERS THE DEAD END. A queue entry with no candidate rows could
 * not be answered at all — the route refuses it as `no_candidates` — so the only moves were
 * skip, which writes nothing and asks again next session, and stand-down, which closes the
 * question rather than answering it. The row was in the export the whole time.
 *
 * AN EMPTY QUERY IS LEGAL AND IS THE ARRIVING-AT-THE-CARD CASE: the server suggests from the
 * card's own read, so the screen shows what it could have been before anyone types. A query
 * searches by name, collector number or SKU.
 *
 * IT OFFERS AND NEVER WRITES. Choosing one of these rows still goes through `answerReview`,
 * and the server still re-reads the row before it writes anything.
 */
export async function reviewCatalog(
  box: number,
  index: number,
  query: string,
): Promise<CatalogLookup> {
  const at = `/review/${box}/${index}/catalog?q=${encodeURIComponent(query)}`
  return (await request(at, NO_CACHE)) as CatalogLookup
}

/* One route in both directions — `POST /review/<box>/<index>/answer`, with `{"undo": true}` to
 * take the answer back. The same shape `sale()` below has, deliberately: two exported functions
 * over one private call, because a boolean at the call site reads as `answerCall(box, index,
 * true)` and the reader has to come here to learn which way that goes.
 *
 * A BODY IS ALWAYS SENT AND IS NEVER EMPTY. `_body()` refuses an empty request as
 * `body_required` uniformly for every write this server answers; the undo's is two characters
 * of flag.
 *
 * THE TWO DIRECTIONS TAKE DIFFERENT BODIES AND THE SERVER ENFORCES THAT. An undo carrying a SKU
 * refuses as `field_not_settable` rather than being obeyed with the SKU ignored, so a client
 * that has confused the two is told rather than being handed a write it did not mean. That is
 * why this takes a body rather than a flag: there is no one shape to compose here.
 *
 * THE RESULT IS TYPED FOR BOTH, and `restores_to` is the field that makes it worth typing at
 * all — see `AnswerResult` in types.ts. It was `{ answered: string }` until the undo existed,
 * which is `SaleResult`'s own history repeating: a route computing a field deliberately, and a
 * cast on this side quietly discarding it. */
async function answerCall(
  box: number,
  index: number,
  body: Record<string, unknown>,
): Promise<AnswerResult> {
  return (await request(`/review/${box}/${index}/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })) as AnswerResult
}

/* One route in both directions — `POST /review/<box>/<index>/stand-down`, with
 * `{"undo": true}` to put the question back. `answerCall`'s shape on the control
 * docs/DESIGN.md asked for by name and D37 settles: close a queued question WITHOUT
 * answering it, leaving the card untouched in its slot.
 *
 * THE TWO DIRECTIONS TAKE DIFFERENT BODIES AND THE SERVER ENFORCES THAT, as everywhere else
 * in this module: an undo carrying a reason refuses as `field_not_settable` rather than being
 * obeyed with the reason ignored.
 *
 * THE REFUSAL WORTH BRANCHING ON IS `not_stood_down` ON A REVERSAL, and it carries two
 * different facts under one code. Either the entry is already waiting — success in the same
 * sense `not_sold` is — or the question was closed by an ANSWER rather than a stand-down, and
 * this control may not reach it: taking back a real identification through the un-dismiss
 * button is the one thing this route refuses on principle. The message says which. */
async function standDownCall(
  box: number,
  index: number,
  body: Record<string, unknown>,
): Promise<StandDownResult> {
  return (await request(`/review/${box}/${index}/stand-down`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })) as StandDownResult
}

/**
 * Close a queued question without answering it: the card is untouched, only the flag drops.
 *
 * D37. NOT AN ANSWER AND NOT A RETIREMENT — the card keeps its slot, its photograph and its
 * place in the box walk, and stays sellable if it is ever identified properly. What ends is
 * the queue asking about it, permanently, across every future join: `Queue.upsert` refuses to
 * re-queue a position a human has cleared.
 *
 * THE REASON IS REQUIRED, which is docs/DESIGN.md's wording and not a preference — "a real
 * defer that RECORDS A REASON". It is also the instrument that file says has never been read:
 * without it, nothing can ever say which questions get waved off or why.
 */
export async function standDown(
  box: number,
  index: number,
  reason: StandDownReason,
): Promise<StandDownResult> {
  return standDownCall(box, index, { reason })
}

/**
 * Put a stood-down question back on the screen. The twenty-second window's other half.
 *
 * It puts back nothing but the flag, because the flag is all the stand-down wrote — no SKU,
 * no state, no count. Refuses `not_stood_down` when the question was closed by an answer.
 */
export async function undoStandDown(
  box: number,
  index: number,
): Promise<StandDownResult> {
  return standDownCall(box, index, { undo: true })
}

/**
 * Take one review answer back. D28's twenty-second undo, server side.
 *
 * READ `restores_to` ON THE ANSWER BEFORE DRAWING THE CONTROL THAT CALLS THIS. It is null when
 * the server has already decided the reversal will refuse — the answered SKU is out of this Mac
 * (`undo_too_late`), or `history.jsonl` cannot say what the answer replaced
 * (`answer_origin_unknown`) — and offering an undo whose only behaviour is that refusal is the
 * defect `SaleResult` records as having shipped twice.
 *
 * THERE IS NO EXPIRY ON THE ROUTE AND NONE HERE. The twenty seconds are how long the control
 * stays on screen, which is `ReviewQueue.tsx`'s decision and is made there — the same split
 * `undoSale` describes below, and the owner's ruling for this screen: screen-held now,
 * server-enforced only if it bites.
 *
 * WHAT COMES BACK IS THE CARD WAITING AGAIN. Every queue entry the answer cleared is reopened,
 * so the position is in `GET /queues` once more; the SKU and condition on the card go back to
 * whatever they were before the answer, which for most queued cards is nothing at all. The two
 * refusals worth branching on are `not_answered` — the reversal already happened, here or on
 * the other device — and `not_in_queue`, where a later run released the entry entirely.
 */
export function undoAnswer(box: number, index: number): Promise<AnswerResult> {
  return answerCall(box, index, { undo: true })
}

/**
 * Answer a homogeneous group of queued cards in one write — `POST /review/group-answer`,
 * docs/DECISIONS.md's "A homogeneous queue may be answered as a group" (the entry that
 * reopens D4's one-card-at-a-time, narrowly).
 *
 * EACH CARD IS ANSWERED WITH ITS OWN SINGLE CANDIDATE, and every element's pair is copied
 * off that card's own lone row exactly as `answerReview` copies a single one — the route
 * re-validates each against its own queue entry with the single answer's own refusals, so
 * a group drawn from a queue file a later join has rewritten is caught rather than obeyed.
 *
 * ALL OR NOTHING, WHICH IS THE PART A CALLER MUST NOT PAPER OVER. A group with one refused
 * member refuses whole with nothing written: `group_entry_refused` when the store has moved
 * past the screen (reload and re-filter — every failing position is named with its own code
 * in the message), `group_not_uniform` when the group never qualified (mixed reasons, an
 * entry with more than one row, mixed conditions — those cards are answered one at a time).
 * So a resolved promise means every position landed, and a rejected one means none did;
 * there is no partial state for a screen to reconcile.
 *
 * THE REVERSAL IS NOT ON THIS ROUTE. Every member gets its own `answered` history line, so
 * `undoAnswer` above reverses any of them exactly as if it had been answered alone — the
 * screen holding the group receipt loops it per position, which is what lets a partial
 * REVERSAL report per position instead of pretending a group has one outcome. Read each
 * member's `restores_to` before drawing that receipt: the contract is `answerReview`'s,
 * per member.
 */
export async function answerReviewGroup(
  answers: readonly ReviewAnswer[],
): Promise<GroupAnswerResult> {
  return (await request('/review/group-answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      /* Rebuilt field by field rather than passed through, so a caller's wider object —
       * a row with its label, say — cannot leak extra keys onto the wire, where the route
       * refuses them as `answer_invalid` and the whole group with them. */
      answers: answers.map(({ box, index, sku, condition }) => ({ box, index, sku, condition })),
    }),
  })) as GroupAnswerResult
}

// ------------------------------------------------------------------------------ mark sold

/* One route in both directions — `POST /inventory/<box>/<index>/sold`, with `{"undo": true}`
 * to reverse. Two exported functions over one private call, because a boolean at the call
 * site reads as `sale(box, index, true)` and the reader has to come here to learn which way
 * that goes.
 *
 * A body is sent even for the sale, which carries nothing: `_body()` refuses an empty request
 * as `body_required`, uniformly for every write this server answers. Two characters on the
 * wire buys one set of rules about request size and encoding rather than two.
 *
 * NO REFUSAL IS SOFTENED HERE, and `already_sold` is the one that proves the rule rather than
 * the one that bends it. It reads like `not_sold`'s twin — both are the server saying the card
 * is already in some state — but they are not twins, and the Fulfillment view's ruling covers
 * only one of them. `not_sold` on a reversal means the card is not sold, which is what the
 * caller wanted. `already_sold` on a SALE means somebody else sold that copy, and answering it
 * as success hands the caller an undo that would reverse the other device's real sale (D13:
 * two devices, one store). That distinction belongs to the screen that draws the undo, so this
 * module does what it does for every other route — throws `ServerError` carrying the server's
 * own code and message — and each caller applies its own reading where the reason for it is
 * written down.
 *
 * `restores_to` COMES BACK WITH THE ANSWER AND IS THE CALLER'S TO ACT ON. See `SaleResult` in
 * types.ts for what it means and for the two casts that used to discard it.
 */
async function sale(box: number, index: number, undo: boolean): Promise<SaleResult> {
  return (await request(`/inventory/${box}/${index}/sold`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(undo ? { undo: true } : {}),
  })) as SaleResult
}

/**
 * Mark one copy sold. D10: sold is a state, never a removal — the record stays, the position
 * stays, and the position is never reused, so a printed label is still true a year later.
 *
 * ONE COPY, NOT ONE SKU. D7 keeps every copy as its own position with its own photo precisely
 * so an order pull can mark one of them sold and leave the rest listed. The position in the
 * path is the whole of the selection.
 *
 * READ `restores_to` ON THE ANSWER BEFORE DRAWING AN UNDO. It is null when the store's history
 * cannot say what state this card was in before the sale, and a null there is the server
 * telling the caller in advance that the reversal below will refuse.
 */
export function markSold(box: number, index: number): Promise<SaleResult> {
  return sale(box, index, false)
}

/**
 * Put a sold copy back to the state it was in. The server half of docs/DESIGN.md's undo.
 *
 * There is no expiry on the route and none here: a server-side deadline would fail the
 * reversal exactly when the network was slow. What the design's ">= 10s" governs is how long
 * the control stays on screen, which is the calling screen's decision and is made there.
 *
 * The state that comes back is read out of `history.jsonl` rather than guessed — a card sold
 * out of `pushed` returns to `pushed`. When the log cannot say, the route refuses as
 * `sold_origin_unknown` rather than defaulting to `live`. That refusal is predictable at the
 * moment of the sale: `markSold` answers `restores_to: null` for exactly the cards this will
 * refuse, so a screen that reads it never draws a control whose only outcome is that message.
 *
 * `restores_to` on THIS answer is always null, and means nothing beyond "there is nothing left
 * to reverse". Do not read it as a second undo being available.
 */
export function undoSale(box: number, index: number): Promise<SaleResult> {
  return sale(box, index, true)
}

// ---------------------------------------------------------------------------- retire, both ways

/* One route in both directions — `POST /inventory/<box>/<index>/retire`, with
 * `{"undo": true}` to reverse. `sale()`'s shape on `sold`'s sibling (D26: a copy that left
 * inventory WITHOUT a sale — pulled, damaged, lost or given away — record kept, gap
 * permanent), and a private call under two exported functions for `sale()`'s own reason: a
 * boolean at the call site reads as `retirement(box, index, true)` and the reader has to
 * come here to learn which way that goes.
 *
 * THE TWO DIRECTIONS TAKE DIFFERENT BODIES AND THE SERVER ENFORCES THAT. The recording
 * direction carries the reason and nothing else; the reversal carries the flag and nothing
 * else. An undo that also names a reason refuses as `field_not_settable` rather than being
 * obeyed with the reason ignored — the same rule the review answer's undo applies, and the
 * reason this takes a body rather than composing one shape for both.
 *
 * NO REFUSAL IS SOFTENED HERE, matching every other route in this module. The codes worth
 * branching on: `already_retired` on a retirement is the other device's retirement (D13) —
 * the sibling of `already_sold`'s ruling, and no undo may be offered because it would
 * reverse a departure this device never recorded; `not_retired` on a reversal is success in
 * the same sense `not_sold` is — the card is not retired, which is what the tap asked for;
 * `already_sold` on a retirement means the copy left by the other door, and the remedy the
 * message names is the sale route's own undo. Each caller applies its reading where the
 * reason for it is written down. */
async function retirement(
  box: number,
  index: number,
  body: Record<string, unknown>,
): Promise<RetireResult> {
  return (await request(`/inventory/${box}/${index}/retire`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })) as RetireResult
}

/**
 * Mark one copy retired: it left inventory without a sale, and why. D26, and D10's shape —
 * retired is a state, never a removal, so the record stays, the position stays, and the gap
 * it leaves is permanent. One copy, not one SKU, exactly as `markSold`.
 *
 * THE REASON IS REQUIRED AND IS ONE OF FOUR — the `RetireReason` union, refused server-side
 * as `retire_reason_invalid` outside it. It is the one fact about the departure the record
 * cannot re-derive later, which is why there is no reasonless overload of this call.
 *
 * READ `restores_to` ON THE ANSWER BEFORE DRAWING AN UNDO. Null means the store's history
 * cannot say what state this copy was in before the retirement, and the reversal below will
 * refuse as `retired_origin_unknown` — the same contract `markSold` states, learned the
 * same expensive way.
 *
 * A retirement touches no listing count, deliberately: it is invisible to TCGplayer, so the
 * SKU's `live` estimate is honestly unchanged. Pulling a live listing down is a TCGplayer
 * action the next join then observes — the route's own docstring carries the argument.
 */
export function retireCard(
  box: number,
  index: number,
  reason: RetireReason,
): Promise<RetireResult> {
  return retirement(box, index, { reason })
}

/**
 * Put a retired copy back to the state it was in. The reversal half of the same control.
 *
 * There is no expiry on the route and none here — the same split every undo in this product
 * keeps: what the screen's window governs is how long the control stays visible, and it is
 * the calling screen's decision. The state that comes back is read out of `history.jsonl`
 * rather than guessed, and the card's `retire_reason` is cleared with it — the history line
 * is where the reason of a reversed retirement survives.
 *
 * `restores_to` on THIS answer is always null and means only "nothing left to reverse".
 */
export function undoRetire(box: number, index: number): Promise<RetireResult> {
  return retirement(box, index, { undo: true })
}

// ------------------------------------------------------------------ search, and the boxes

/**
 * Every copy of every card whose name matches, grouped by SKU, each copy carrying where it is.
 *
 * ONE ROUTE FOR A QUESTION THAT USED TO COST THE WHOLE INVENTORY. `Inventory.tsx` answers the
 * same question by pulling `GET /inventory` and grouping it in the browser, which is right for
 * a screen whose job is to show everything; it is the wrong shape for a screen the owner opens
 * because one card just sold, where the whole store is downloaded to look at four rows of it.
 * The grouping is the server's here, and `SearchGroup` carries two numbers the app is
 * forbidden from computing — the live cap (D7) and the position of each copy in its box (D10).
 *
 * `q` IS SENT AS TYPED, TRIMMED BY NOBODY HERE. `useSearch.ts` decides when a query is worth
 * asking about and refuses to ask about an empty one; this function's job is to ask. A client
 * that also trimmed would put the rule in two places and neither would own it.
 *
 * `encodeURIComponent` RATHER THAN `URLSearchParams`, because the base URL is a string and
 * building a `URL` around it would resolve a relative `VITE_CAPTURE_SERVER` against the page
 * — a silent redirection to the Vite dev server, answered with index.html, reported as
 * `bad_response`. Card names carry `&` (`Billy & O'Nare`) and apostrophes, so the encoding
 * itself is not optional: T3 keeps those in the fixture set precisely because they break
 * naive string handling.
 *
 * Refuses an empty query as `query_required` rather than answering with everything. That is the
 * server's ruling and it is the right one — a bare `GET /search` returning the whole store is a
 * denial of service you write by accident — and it is why the hook below never sends one.
 */
export async function search(q: string): Promise<SearchResult> {
  return (await request(`/search?q=${encodeURIComponent(q)}`, NO_CACHE)) as SearchResult
}

/**
 * Every box, with its divider layout and how full it is.
 *
 * THE REASON A SCREEN WANTS THIS AND NOT JUST `Place`: a `Place` describes one card's own
 * section, and nothing else about the box it is in. Drawing the whole box divided into all of
 * its sections needs `sections_detail`, and reconstructing those spans from one section's
 * width is the section arithmetic types.ts forbids — see `PositionBar.tsx:spansOf`, which
 * takes them as an optional argument for exactly this reason.
 *
 * `/status` ALREADY LISTS THE BOXES IN USE AND THIS DOES NOT REPLACE IT. That field is
 * `next_index` per box, which is what the capture screen's box picker is built from and is a
 * different question — where does the next card go, versus how is this box laid out. Two
 * routes because the capture screen polls one of them and must not start pulling divider
 * layouts at capture pace.
 */
/**
 * The per-game registry, exactly as `pipeline/games.py` authors it.
 *
 * THE ONLY COPY ON THIS SIDE OF THE WIRE, AND THAT IS THE POINT. An `app/src/games.ts`
 * holding the same four keys, their rarity ladders and their finish matrices was considered
 * and rejected: it is a second hand-authored copy of a hand-authored file, nothing keeps the
 * two in step, and it buys the app nothing this route does not already hand it. The screens
 * learn what a game is at runtime, from the one place the pipeline learns it.
 *
 * READ ONCE PER SCREEN, NOT POLLED. The registry changes when somebody edits a Python file
 * and restarts the server, which is not something a capture session needs to watch for. It
 * carries `NO_CACHE` all the same, for the reason every read here does: the server sends no
 * cache headers, which leaves the decision to a heuristic.
 *
 * `default` COMES BACK WITH IT rather than being assumed. A screen that hardcoded `pokemon`
 * would be a second decision that has to agree with `games.DEFAULT_GAME`, and would stop
 * agreeing silently.
 */
export async function getGames(): Promise<GameRegistry> {
  return (await request('/games', NO_CACHE)) as GameRegistry
}

export async function getBoxes(): Promise<BoxSummary> {
  return (await request('/boxes', NO_CACHE)) as BoxSummary
}

/**
 * Declare a box: its number, optionally what it is called and where its dividers are.
 *
 * A BOX IS CREATED BY CAPTURING INTO IT AND THIS ROUTE DOES NOT CHANGE THAT.
 * `Inventory.allocate_capture` makes a box the first time a card lands in one — that is what
 * `CardSummary.new_box` reports — so this is for declaring a box *before* or *beside* that,
 * with a name and a layout. It is not on the capture path and nothing about capture waits for
 * it.
 *
 * `sections` IS A LIST OF DIVIDER INDICES (D10), never a count. `[1, 31, 56]` means section 2
 * starts at card 31. Omitted is not the same as `[]`: omitted leaves the box's layout alone,
 * and `[]` declares it undeclared, which D10 says the 25-rule then renders. Both are real
 * requests and this module sends what it is given rather than normalising one into the other.
 *
 * Refuses `box_exists` on a number already declared — take that as a fact rather than an
 * error to retry through, and reach for `updateBox` if the intent was to rename or re-divide.
 *
 * `box` IS OPTIONAL, AND A NAME ALONE IS A COMPLETE REQUEST. The owner addresses a box by
 * what it is called and does not care what number it carries, so the server takes the lowest
 * free one — see `store/master.py:next_box_number` for why that is the lowest rather than a
 * high-water mark. Sending neither refuses `box_or_name_required`: a body with no number and
 * no name does not describe a box, and inventing both halves of an object nobody named is
 * how a registry fills with rows no one meant to make.
 *
 * A DUPLICATE NAME REFUSES `name_taken`, which is new with the same change. Two boxes
 * answering to one name is an ambiguous physical address the moment a name is how a box is
 * reached, and the refusal names the box that already holds it.
 */
export async function createBox(input: {
  box?: number
  name?: string
  sections?: number[]
}): Promise<BoxRecord> {
  const payload: Record<string, string | number | number[]> = {}
  if (input.box !== undefined) payload.box = input.box

  /* Omitted rather than sent empty, the same rule `capture()` applies to `set_hint`: the
   * record stays a record of what was actually declared. A name trimmed to nothing is no name,
   * and sending `""` would set one — which then renders as an empty caption beside a position
   * label and looks like a bug in the label. */
  const name = input.name?.trim()
  if (name) payload.name = name
  if (input.sections !== undefined) payload.sections = input.sections

  return (await request('/boxes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })) as BoxRecord
}

/**
 * Rename a box, re-divide it, or open and close it. Any subset of the three.
 *
 * A PATCH AND NOT A WHOLE RECORD, and the distinction matters more here than anywhere else in
 * this module. D13 has two devices sharing one store; a PUT that carried the whole box would
 * make every edit a last-writer-wins overwrite of fields the caller never looked at, so the
 * Fulfiller's device could silently undo a divider the owner moved thirty seconds earlier by
 * renaming the box. Send the fields being changed.
 *
 * RE-DIVIDING RELABELS EVERY CARD BEHIND THE DIVIDER, and no card moves. D10 is explicit that
 * the index is the identity and Section/Card are a *view* of it against the current layout, so
 * this call rewrites labels and touches no position. The same entry records what that costs
 * and declines to design it away: "a mis-tap relabels a filled box and nothing flags it", and
 * the mitigation the owner chose is a `resectioned` history event rather than a restriction.
 * A screen calling this on a box with cards in it is doing something the owner ruled is
 * allowed — it is not this module's place to add the confirm D10 says to reach for *first if
 * that failure ever actually happens*, and it is worth knowing that it has not yet.
 *
 * `box_closed` IS A REFUSAL ABOUT THE BOX, NOT ABOUT THIS CALL BEING WRONG. It means the box
 * is closed and the edit asked for is one a closed box does not take. Branch on it if a screen
 * can offer to reopen; do not paraphrase it into "something went wrong".
 */
export async function updateBox(
  box: number,
  patch: {
    name?: string
    sections?: number[]
    state?: BoxState
    /** Section names by ORDINAL, as the screen numbers them (D132). A blank clears one. */
    section_names?: Record<number, string>
  },
): Promise<BoxRecord> {
  /* Built key by key rather than spread, so an `undefined` cannot reach `JSON.stringify` and
   * be dropped there instead. Both routes end at the same place today; the difference is that
   * this one is readable — a reader can see that omitted means untouched without knowing what
   * `JSON.stringify` does with an undefined value. */
  const payload: Record<string, string | number[] | Record<number, string>> = {}
  if (patch.name !== undefined) payload.name = patch.name
  if (patch.sections !== undefined) payload.sections = patch.sections
  if (patch.state !== undefined) payload.state = patch.state
  if (patch.section_names !== undefined) payload.section_names = patch.section_names

  return (await request(`/boxes/${box}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })) as BoxRecord
}

/**
 * Put ONE divider in front of the next card in a box. The capture screen's `S`.
 *
 * SENDS NO INDEX, AND THAT IS THE CONTRACT RATHER THAN A CONVENIENCE. The divider goes where
 * `store/master.py:next_index` says the next card will land, read inside the store lock. A
 * caller that computed it from `BoxRecord.next_index` and sent it back would be re-deriving
 * a high-water mark across a round trip, which at a feeder's 623 ms cadence is a real race:
 * one capture between the read and the write and the divider lands behind the card it was
 * meant to be in front of. There is no parameter to get that wrong with.
 *
 * `updateBox({ sections })` IS THE OTHER OPERATION AND IS NOT A SUBSTITUTE. That one declares
 * a whole layout, from a screen, after the fact — the caller has to hold every divider the
 * box already has and append to it, so two devices editing one box last-writer-wins the way
 * that function's own note describes. This one appends, in the store, from the physical act.
 *
 * REFUSALS WORTH BRANCHING ON, all three of them facts about the box rather than about the
 * request. `section_empty`: the last section was opened and nothing has been captured into
 * it yet, so the divider asked for is already there — the two-presses-in-a-row case, and the
 * one an operator will actually hit. `section_ahead`: a divider is already declared past the
 * next card, so this one cannot go in front of it; the remedy is the dividers editor.
 * `box_closed`: a sealed box takes no more cards. Show the server's sentence — each names
 * the divider or the box that is in the way, and this module has nothing to add to it.
 *
 * Answers with the whole `BoxRecord`, so `sections_detail` comes back with it. Read the
 * section that was opened off the LAST entry of that array rather than off `sections.length`
 * — same reason `BoxOps.tsx` gives at `renderedSections`: the server renders spans and the
 * app does not do section arithmetic.
 */
export async function openSection(box: number): Promise<BoxRecord> {
  return (await request(`/boxes/${box}/sections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    /* `{}` and not an empty body: every write in the capture server reads its body the same
     * way and refuses an absent one as `body_required`, which `markSold` documents as the
     * convention rather than an oversight. Two characters. */
    body: JSON.stringify({}),
  })) as BoxRecord
}

// --------------------------------------------------------------------------- capture ids

/**
 * A fresh capture id. One per photograph, held by the caller across any retry of it.
 *
 * `crypto.randomUUID` is unavailable outside a secure context, and this app has a planned
 * insecure one: served over plain http from the Mac's LAN address to the Fulfiller's device
 * (D13, and the capture-app spec's reason for making the base URL configurable). It would
 * be `undefined` there and throw at the first capture, on the device hardest to debug on.
 * So it is used where it exists and reconstructed where it does not.
 *
 * `crypto.getRandomValues` carries no such restriction and is the fallback. `Math.random`
 * is NOT an acceptable substitute here even though a capture id only has to be unique: a
 * collision does not degrade gracefully, it lands as a `DuplicateCaptureId` conflict that
 * reads exactly like a replay, which is to say a capture silently answered with a different
 * card's position.
 */
export function newCaptureId(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()

  const bytes = crypto.getRandomValues(new Uint8Array(16))
  const digits: string[] = []
  bytes.forEach((byte, i) => {
    let value = byte
    if (i === 6) value = (value & 0x0f) | 0x40 // version 4
    if (i === 8) value = (value & 0x3f) | 0x80 // variant 10xx
    digits.push(value.toString(16).padStart(2, '0'))
  })

  /* Formatted as a UUID rather than left as 32 hex characters, so an id read out of
   * `inventory.json` is recognisably the same kind of thing whichever path produced it. */
  const hex = digits.join('')
  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20),
  ].join('-')
}

/**
 * Apply capture claims to many cards in one box, in ONE write.
 *
 * THE ROUTE EXISTED WITH NO CLIENT FUNCTION AND NO CONTROL, which is the failure
 * `CLAUDE.md` now has a hard rule about: a route is not a feature. It was built and covered
 * by T7 on 2026-08-23 and could not be reached from any screen.
 *
 * `indices` is the mass-select. OMIT IT for the whole box; pass the selection to narrow it.
 * An EMPTY array is refused server-side rather than treated as the whole box — the two read
 * alike and mean opposite things, and widening an emptied selection to every card in the
 * box is the accident that refusal exists to stop. Never send `[]`; send nothing.
 *
 * All-or-nothing, like D29's group answer: every card is validated before any is written,
 * and a claim outside one card's game (D21/D23 make the vocabulary per-game) refuses the
 * whole call with the offenders named. Sold and retired cards are skipped and reported, not
 * silently passed over — their records are history (D10, D26).
 */
export async function applyBoxClaims(
  box: number,
  fields: {
    setHint?: string | null
    /* A list, and `null` clears — `updateCard`'s rule at box scale (D3 rung 1's set). */
    variant?: readonly Finish[] | null
    game?: string
    rarityClaim?: string[] | null
    /** C10/D70's product claim at box scope — `updateCard`'s rule over many positions. A
     *  code-card stack came out of ONE sealed product (that premise is the whole of why this
     *  track has no OCR), so the box, or a selection inside it, is the natural unit to
     *  correct: the claim is per card and the mistake is per stack. */
    product?: string | null
    note?: string | null
  },
  indices?: number[],
): Promise<BoxClaimResult> {
  const payload: Record<string, string | readonly string[] | number[] | null> = {}
  if ('setHint' in fields) payload.set_hint = fields.setHint ?? null
  if ('variant' in fields) payload.variant = fields.variant ?? null
  if ('game' in fields && fields.game !== undefined) payload.game = fields.game
  if ('rarityClaim' in fields) payload.rarity_claim = fields.rarityClaim ?? null
  if ('product' in fields) payload.product = fields.product ?? null
  if ('note' in fields) payload.note = fields.note ?? null
  if (indices !== undefined) payload.indices = indices

  return (await request(`/inventory/${box}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })) as BoxClaimResult
}

/**
 * Delete one capture mid-box and slide every higher card down one index (D10 ruling 1).
 *
 * NOT `undoCapture`, and the difference is the whole reason this is a separate call. Undo
 * reaches only the newest card in a box and only while it is still `captured`; this reaches
 * a junk capture anywhere in the stack, and it RENUMBERS — which D10 otherwise forbids
 * outright. It is permitted here because it is the physical truth: pull a card out of a
 * contiguous stack and the ones behind it really do slide forward.
 *
 * `captureId` IS THE AIM, and it is required rather than optional. The operation is not
 * idempotent — after the shift a DIFFERENT physical card sits at that index — so a replayed
 * or stale request must refuse (`capture_id_mismatch`) instead of deleting the neighbour
 * that slid in. Pass the target's own `capture_id`, or `null` for a record written before
 * capture ids existed.
 *
 * It refuses `renumber_blocked` when any higher card in the box is sold, retired or
 * listing-held: shifting across a permanent gap would close a gap that means something, and
 * a listed card's position is already written into a file somebody will read.
 */
export async function removeCardInPlace(
  box: number,
  index: number,
  captureId: string | null,
): Promise<RemoveResult> {
  return (await request(`/inventory/${box}/${index}/remove`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capture_id: captureId }),
  })) as RemoveResult
}

/**
 * Move one card to a fresh index in another box (D83) — the third door out of a box, and
 * not a shift: unlike `removeCardInPlace`, nothing else in either box renumbers. The
 * source position becomes a permanent tombstone, the same shape a sale or a retirement
 * leaves, and the card is recorded fresh at the answer's `new_box`/`new_index`.
 *
 * `captureId` IS THE AIM, exactly as `removeCardInPlace` takes it and for the identical
 * reason: a replayed or stale request must refuse (`capture_id_mismatch`) rather than
 * move whatever card now happens to sit at this position — which, after a first
 * successful move, is nothing at all. Pass the target's own `capture_id`, or `null` for
 * a record written before capture ids existed.
 *
 * No listing-hold guard: a card carrying an active listing stage is free to move (D7 —
 * which physical copy backs a stage is deliberately unrecorded, so a box change cannot
 * disagree with it). Undo is this same call again, aimed at the transplant, in the other
 * direction — it lands at a fresh index in the original box rather than reclaiming the
 * tombstoned one.
 */
export async function moveCard(
  box: number,
  index: number,
  captureId: string | null,
  toBox: number,
): Promise<MoveResult> {
  return (await request(`/inventory/${box}/${index}/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capture_id: captureId, to_box: toBox }),
  })) as MoveResult
}

/**
 * Move several cards from one box to another in one write (D83). `indices: null` moves
 * every on-hand card — a whole-box move, which is what a merge is from this call's side;
 * there is no separate merge endpoint. Pass an explicit list for a ticked selection or a
 * section (computed from the box's own `sections_detail`, the same source the dividers
 * editor reads).
 *
 * One write for the whole list: a refusal partway through — a card already sold, retired
 * or moved by another session — discards every earlier card's move in the same request
 * rather than leaving it half migrated. Order is preserved at the destination: cards
 * arrive in the order their indices were sent, landing contiguously.
 */
export async function moveCards(
  box: number,
  indices: number[] | null,
  toBox: number,
): Promise<MoveCardsResult> {
  return (await request(`/inventory/${box}/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ indices, to_box: toBox }),
  })) as MoveCardsResult
}

/**
 * Delete a whole box — records, photos, sidecars, queue entries, cache, registry entry
 * (D10 ruling 3, amended D134).
 *
 * THE MOST DESTRUCTIVE ACTION IN THE PRODUCT, and the one place `docs/DESIGN.md`'s
 * "genuinely destructive actions may still gate" clause is meant to bite. There is no undo:
 * unlike capture-undo, the cards are not in your hand.
 *
 * It refuses `box_not_empty_of_commitments` only while the box holds an on-hand card with an
 * active listing hold, naming up to eight. A sold, retired or moved record no longer blocks
 * this (D134) — it is buried instead, readable afterward from `graveyard()`, so a screen
 * should show the refusal as naming only what still stands in the way.
 *
 * The result is a per-kind receipt and should be drawn as one. `buried` is the subset of
 * `cards` that left through a departure door rather than as ordinary on-hand junk.
 * `directory_removed: false` is not a failure; see `BoxDeleteResult`.
 */
export async function deleteBox(box: number): Promise<BoxDeleteResult> {
  return (await request(`/boxes/${box}`, { method: 'DELETE' })) as BoxDeleteResult
}

/**
 * Every departed card the store still knows about, newest departure first (D134).
 *
 * TWO SOURCES, ONE SHAPE. A sold, retired or moved record can be standing in a box nobody
 * has deleted — the same records `#/inventory` already draws as departed — or it can be the
 * retained half of a record whose box WAS deleted, read back from the `buried` history line.
 * `DepartedCard.buried` is which one a row came from; nothing else about the shape differs,
 * and a record is never counted from both sources at once.
 *
 * Free and read-only. `#/graveyard` is the one screen that calls this.
 */
export async function getGraveyard(): Promise<GraveyardPayload> {
  return (await request('/graveyard')) as GraveyardPayload
}

/**
 * What this box's SKUs are believed to be holding, and what a release would give up.
 * FREE and read-only (D34).
 *
 * THE STEP THAT COMES FIRST, and the release control must not be drawn until it has answered.
 * D33's preflight-then-confirm shape one register down: there the free step shows what a run
 * would cost before the button that spends appears; here it shows which SKUs, how many copies,
 * and WHICH OTHER BOXES the release reaches before the button that asserts appears.
 *
 * It exists because the first build put the blast radius in the receipt — reported honestly,
 * and reported after the write. An operator releasing from box 1's header learned box 3 was
 * involved once it was already done.
 *
 * `frees_box` IS THE FIELD TO DRAW MOST LOUDLY. The budget is per box, so a shared SKU leaves
 * a remainder and the box stays refused afterwards. That is the intended behaviour and it is
 * the one thing a person would otherwise assume had gone wrong.
 *
 * Zero rows is ordinary — most boxes have never been listed — and is not an error.
 */
export async function getBoxListings(box: number): Promise<BoxListingPlan> {
  return (await request(`/boxes/${box}/listings`)) as BoxListingPlan
}

/**
 * What a photo reclaim over this box would delete: the sold cards whose photograph is still
 * on disk, and the bytes. FREE and read-only (D89).
 *
 * THE STEP THAT COMES FIRST, exactly as `getBoxListings` is for the release: the control that
 * deletes is not drawn until this has answered, so the count and the megabytes are on screen
 * before anything can be pressed. Zero reclaimable is ordinary — a box that has sold nothing,
 * or one reclaimed already — and is not an error.
 */
export async function getBoxPhotos(box: number): Promise<BoxPhotoPlan> {
  return (await request(`/boxes/${box}/photos`)) as BoxPhotoPlan
}

/**
 * Delete the photographs of every sold card in this box. The records stay, sold, each keeping
 * the digest of the photograph it had (D89).
 *
 * THERE IS NO UNDO — the bytes are gone and the card is not in your hand — so this sits with
 * `deleteBox` under docs/DESIGN.md's "genuinely destructive actions may still gate" clause.
 * The server refuses without `confirm: true`, and refuses `nothing_to_reclaim` when no sold
 * card in the box still has a photograph, which is what a second press meets.
 *
 * THE WAY BACK IS THE BOX ROW AND THE WALK, both of which the caller re-reads: `has_photo`
 * flips on every copy row and the card band draws "reclaimed" off `photo_reclaimed_at`.
 */
export async function reclaimBoxPhotos(box: number): Promise<PhotoReclaimResult> {
  return (await request(`/boxes/${box}/photos/reclaim`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm: true }),
  })) as PhotoReclaimResult
}

/**
 * Give up what this box's copies could account for, on the operator's word (D34).
 *
 * THE OTHER HALF OF `box_not_empty_of_commitments`, and the reason `deleteBox` above could
 * refuse forever. That refusal has two grounds. A sold or retired card can be freed: both
 * reverse on their own routes and the refusal says so. A LISTING could not be, at all —
 * `staged` is drawn down in one place, by the rise in live quantity a fresh export reports, so
 * an import staged and then cleared by hand on TCGplayer leaves counts nothing in the pipeline
 * can ever take back down. Box 1's 53 cards sat behind 45 such records.
 *
 * IT RECORDS A CLAIM RATHER THAN MEASURING ANYTHING, which is why it is the only function in
 * this module whose argument is the operator's own knowledge. No export this pipeline reads can
 * say "nothing is staged" — a Filtered Export reports live quantity, and an Export From Staged
 * lists the rows that ARE there, so absence proves nothing. The server requires `confirm: true`
 * and writes a history line either way.
 *
 * EACH SKU GIVES UP AT MOST THE UNSOLD COPIES THIS BOX HOLDS. A release reached from box 1
 * therefore cannot give up a commitment only box 3's copies could account for — structurally,
 * not by care. Call `getBoxListings` first and draw its plan; both come from one function
 * server-side, so the preview and the write are the same arithmetic.
 *
 * It refuses `nothing_to_release` when no SKU in the box holds a stage — reachable only from a
 * stale screen or a replayed request, and a refusal rather than a cheerful no-op precisely so
 * those two stay distinguishable from a release that worked.
 */
export async function releaseBoxListings(box: number): Promise<ListingReleaseResult> {
  return (await request(`/boxes/${box}/listings/release`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm: true }),
  })) as ListingReleaseResult
}

/* ---------------------------------------------------------------------- the pipeline
 *
 * The four commands, reachable from a screen for the first time. `server/pipeline_routes.py`
 * carries the argument for why one of them is spawned and the rest answer in the request;
 * what matters on this side is that ONE of these functions can cost money and it is named
 * for it.
 *
 * NO CLIENT-SIDE TIMEOUT HERE EITHER, and the reason is stronger than it is above. A
 * preflight decodes and crops every photograph in a box — measured at about a minute for
 * 544 cards — and a join parses a 30,000-row export. An AbortController shorter than either
 * would convert a working command into `unreachable`, which is the same lie this module
 * already refuses to tell about the store lock.
 */

/**
 * What a run would cost. FREE, and creates no run directory at all.
 *
 * THIS IS WHAT THE SCREEN MUST SHOW BEFORE IT MAY ASK TO SPEND, and it is the whole of the
 * first step of the two-step confirm. `to_send` and `estimate_usd` are lifted out of the
 * command's own preflight stdout rather than recomputed anywhere, so the figure on the
 * screen and the figure in the run's log are the same string produced by the same code.
 */
export async function preflightRun(send: RunSend): Promise<RunPreflight> {
  return (await request('/pipeline/preflight', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(onTheWire(send)),
  })) as RunPreflight
}

/** ONE PRESS IN THE SHAPE THE ROUTE READS, and the selection is the payload rather than a field
 *  inside one. Named rather than inlined because BOTH functions below send it and the money one
 *  must not be able to send a different shape from the one that was quoted — a preflight and a
 *  confirm describing different sends is the exact failure the two-step gate exists to prevent.
 *
 *  EVERY TERM IS OMITTED WHERE IT IS UNSET, never sent as null or empty. The route reads absence
 *  as "this term does not narrow" and refuses an empty array outright rather than reading it as
 *  everything — so a tick list that failed to load must not arrive as `keys: []`, which would be
 *  a refusal, or as `keys` omitted, which would be a press over the whole drawer. */
function onTheWire(send: RunSend): Record<string, unknown> {
  const { selection } = send
  const some = <T,>(list: readonly T[] | undefined): T[] | undefined =>
    list !== undefined && list.length > 0 ? [...list] : undefined
  return {
    paths: some(selection.paths),
    state: selection.state,
    box: some(selection.box),
    bid: some(selection.bid),
    section: selection.section,
    game: selection.game,
    since: selection.since,
    keys: some(selection.keys),
    run: selection.run,
    crop: send.crop,
    max_edge: send.maxEdge,
  }
}

/**
 * What this reading actually sends: where the crop cuts, and the collector-number strip at
 * the resolution it delivers. FREE, writes nothing, shells out to nothing.
 *
 * IT IS PRESSED BEFORE `preflightRun`, NOT AFTER IT, and that ordering is the point. D32
 * gave the crop three named pairs and a sentence each because the controls alone could not
 * be read; this is the same answer as a picture, and it has to be on screen while the pair
 * is being CHOSEN. The estimate comes after, over a reading the operator has now seen.
 *
 * `offset` steps the sample. Three cards, evenly spaced and deterministic, so that changing
 * the reading redraws the same three — see the route for why one card cannot stand for a box.
 */
export async function cropPreview(
  send: RunSend,
  offset?: number,
): Promise<CropPreview> {
  return (await request('/pipeline/crop-preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...onTheWire(send), offset }),
  })) as CropPreview
}

/**
 * START A RUN. THE ONE FUNCTION IN THIS MODULE THAT SPENDS MONEY.
 *
 * `confirm: true` is not decoration and is not something to default. The server refuses
 * without it, deliberately as a field rather than a typed string — the owner ruled against
 * typing on this control, and `docs/DESIGN.md`'s destructive-action clause is satisfied by
 * the two-step the screen draws, with this field as its second step.
 *
 * It answers as soon as the child is running, with the run's name and nothing about the
 * result. Everything after that is `getRun` polling the run directory, which is what lets a
 * run outlive a restart of the server that started it — or of this browser tab.
 *
 * Refusals worth branching on: `cards_already_claimed` (a live submission is already paying to
 * read cards in this press — two live batches over one card is two invoices for one answer,
 * D174), and every selection refusal the preflight would have shown first. `run_already_live`
 * is gone with the box guard that raised it: that check compared BOX numbers and this route no
 * longer takes one.
 */
/**
 * What cards a live run has already claimed and is paying to read. FREE, reads the store and
 * holds nothing.
 *
 * THE STEP THAT COMES FIRST, exactly as `getBoxPhotos` is for the reclaim: the control that
 * releases a claim is not drawn until this has answered, so the receipt, the run, the number
 * of cards and whether the holder is still alive are all on screen before anything can be
 * pressed. An empty list is the ordinary state of a healthy store and is not an error.
 *
 * `counts` IS THE WORK, NOT THE OUTCOME. Rows live, CARDS locked, and how many are held by a
 * process that is gone — the three figures that say whether this guard is doing anything.
 * They are the server's, summed there, for `preflightRun`'s reason: the screen does not
 * recompute a figure the pipeline owns.
 */
export async function getSubmissions(): Promise<SubmissionClaims> {
  return (await request('/pipeline/submissions', NO_CACHE)) as SubmissionClaims
}

/**
 * Give up a claim's hold on its cards, on the operator's word.
 *
 * THE NAMED WAY OUT, and the reason a claim is allowed not to self-heal. `_busy_run` recovered
 * from a wedge by itself because the server's table of children empties on a restart; a row in
 * the store does not, and that is deliberate — a run killed after it submitted has a batch in
 * flight at Anthropic that nobody collected, so a guard that dropped the row on finding the
 * pid gone would offer a green button over an invoice already rung up.
 *
 * IT SPENDS NOTHING AND IT CAN COST SOMETHING, which is why the server requires `confirm:
 * true` here exactly as `startRun` does. Releasing a claim whose holder is still submitting
 * re-opens those cards to a second press, and that press is the double invoice the claim
 * existed to prevent — so call `getSubmissions` first and draw `holder_alive`.
 *
 * Refusals worth branching on: `no_such_claim` (404 — a claim released earlier is gone from
 * the list by design, so this is a stale screen). An already-released claim is NOT a refusal:
 * it answers `released: false`, which is what a replayed request lands on.
 */
export async function releaseSubmission(receipt: string): Promise<ClaimRelease> {
  return (await request(`/pipeline/submissions/${encodeURIComponent(receipt)}/release`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm: true }),
  })) as ClaimRelease
}

export async function startRun(send: RunSend): Promise<RunStarted> {
  return (await request('/pipeline/identify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm: true, ...onTheWire(send) }),
  })) as RunStarted
}

/**
 * The per-SKU pricing table for one run, with the corpus's answers scoped to it. FREE and
 * read-only: it creates nothing and prices nothing.
 *
 * THE TABLE AND THE ANSWERS IN ONE CALL, WHICH IS THE WHOLE REASON THIS IS A ROUTE.
 * `pricing.json` is downloadable through `GET .../file` and the corpus has `getPricingCorpus`,
 * so a screen could fetch them separately and need no server change at all — but two fetches
 * can straddle a re-join, and a table describing one join beside answers written against
 * another is a screen quietly pricing the wrong set of cards.
 *
 * Refusals worth branching on: `pricing_not_written` (the run predates the file, or has not
 * been joined — the remedy is a re-join and the message says so) and `no_such_run`.
 */
export async function getPricing(name: string): Promise<PricingPayload> {
  return (await request(
    `/pipeline/runs/${encodeURIComponent(name)}/pricing`,
    NO_CACHE,
  )) as PricingPayload
}

/**
 * The whole store against one live TCGplayer export — the fourth command, unscoped (D87).
 *
 * FREE, AND IT WRITES ONLY WHEN `write` IS TRUE. The preview is the default: it moves the
 * quantities the cap arithmetic reads, over every SKU at once.
 *
 * NOT `runStep(name, 'reconcile')`, WHICH STAYS. That answers one import against one Export
 * From Staged; this answers the store against a full live export, which is the only document
 * that can report the other direction — what TCGplayer holds that this pipeline never sent.
 */
export async function reconcileLive(
  /** The bytes an operator dropped, or `null` when `options.fetched` names a file this server
   *  already holds (D104). Never both — the route refuses rather than guessing. */
  file: CsvUpload | null,
  options: { write?: boolean; fetched?: string } = {},
): Promise<{ ok: boolean; exit_code: number; wrote: boolean; console: string }> {
  return (await request('/pipeline/reconcile-live', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...(file === null ? {} : { export: file }),
      ...(options.fetched === undefined ? {} : { fetched: options.fetched }),
      write: Boolean(options.write),
    }),
  })) as { ok: boolean; exit_code: number; wrote: boolean; console: string }
}

/* --------------------------------------------- the standing queues, refreshed store-wide */

/**
 * Re-resolve every OPEN queue entry against a current export, across every box.
 *
 * FREE, RE-RUNNABLE, AND THE PREVIEW IS THE DEFAULT — `reconcileLive`'s shape, because it
 * rewrites every open entry at once. Pass `{ write: true }` only after a preview has been
 * read.
 *
 * NO FILE IS UPLOADED, which is where this differs from `reconcileLive`: the exports are the
 * ones the joined runs already recorded. What a frozen entry needs is the LADDER as it stands
 * now, and that repairs it against the very file it was joined against.
 *
 * AN ANSWERED ENTRY IS NEVER RE-QUEUED. `store/queues.py:upsert` refuses a cleared position
 * and `release` refuses to drop one, so D28's undo stays the only door back out of an answer.
 */
export async function refreshQueues(
  options: { write?: boolean } = {},
): Promise<{ ok: boolean; exit_code: number; wrote: boolean; console: string }> {
  return (await request('/queues/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ write: Boolean(options.write) }),
  })) as { ok: boolean; exit_code: number; wrote: boolean; console: string }
}

/* ------------------------------------------------- the stale-listing markdown (D100) */

/**
 * Which live listings are not selling, and what each would be re-priced to.
 *
 * FREE, AND `write` PRODUCES A WORKLIST RATHER THAN AN UPLOAD. Nothing on this path talks to
 * TCGplayer: the operator downloads the worklist, edits it or does not, and hands it back to
 * `applyMarkdown`, which is what writes the file they upload.
 *
 * NOTHING HERE CAN CHANGE A QUANTITY. Every row of every file this pair writes carries
 * `Add to Quantity` 0 — the price column edits the live listing in place and the quantity
 * column is a delta, so a price-only push adds nothing and deletes nothing. Uploading one of
 * these files twice is a no-op the second time, which is not true of an import from `emit`.
 *
 * `stamp` NAMES THE DIRECTORY A WRITE MADE, and is null on a preview. It is what
 * `applyMarkdown` and `markdownFileUrl` address.
 *
 * Refusals worth branching on: `export_required`, `export_empty`, `export_not_csv`,
 * `rule_invalid`, `basis_invalid`, `number_invalid`.
 */
export async function markdownListings(
  /** The bytes an operator dropped, or `null` when `options.fetched` names a file this server
   *  already holds (D104). Never both — the route refuses a request carrying two documents
   *  rather than guessing which one it meant. */
  file: CsvUpload | null,
  options: MarkdownAsk = {},
): Promise<MarkdownAnswer> {
  return (await request('/pipeline/markdowns', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(file === null ? { ...options } : { export: file, ...options }),
  })) as MarkdownAnswer
}

/**
 * The edited worklist back, and — with `write` — the price-only import CSV.
 *
 * SENDING NO `worklist` MEANS "the one you wrote", which is the flow for an operator who did
 * not want to edit anything: the worklist already carries a proposed price on every row.
 *
 * Refusals worth branching on: `stamp_invalid`, `no_such_markdown`, `no_worklist`. A
 * worklist the command itself refuses — a raised price, a duplicated SKU — comes back as a
 * 200 with `ok: false` and the reason in `console`, the way every other command seam does.
 */
export async function applyMarkdown(
  stamp: string,
  options: {
    worklist?: CsvUpload
    /** The pairs `#/pricing` holds, materialised into the two-column instruction sheet BY THE
     *  SERVER (D103). This client writes no CSV: `app/package.json` carries two runtime
     *  dependencies and PapaParse — the library CLAUDE.md requires for the job — is not one,
     *  and hand-rolling `join(',')` is the rule that lint exists to state. Mutually exclusive
     *  with `worklist`; both together is a refusal rather than a guess. */
    edits?: { sku: string; price: string }[]
    /** The corpus digest this screen last read. Refuses the WHOLE file if the pricing file has
     *  moved since — `apply --write` writes the corpus from a subprocess, which `emit` never
     *  did, so without this the operator's next keystroke is refused for a write they just
     *  made. Omit to say "did not read one", which the command allows. */
    revision?: string
    write?: boolean
  } = {},
): Promise<MarkdownAnswer> {
  return (await request(`/pipeline/markdowns/${encodeURIComponent(stamp)}/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      worklist: options.worklist,
      edits: options.edits,
      revision: options.revision,
      write: Boolean(options.write),
    }),
  })) as MarkdownAnswer
}

/**
 * Push this markdown's `import.csv` into TCGplayer's STAGED inventory.
 *
 * NOTHING A BUYER CAN SEE CHANGES HERE. Staged is the operator's own working copy —
 * measured 2026-09-06, a 100-row push moved 0 of 759 live prices and 0 live quantities.
 * `publishMarkdown` is what publishes, and it is a separate call for that reason.
 *
 * `confirm` IS NOT A FORMALITY AND IS NOT DEFAULTED TRUE HERE. The route refuses without it,
 * the same way `POST /pipeline/identify` refuses without one, because both reach outside this
 * machine and change something there.
 */
export async function pushMarkdown(stamp: string): Promise<MarkdownPush> {
  return (await request(`/pipeline/markdowns/${encodeURIComponent(stamp)}/push`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm: true }),
  })) as MarkdownPush
}

/**
 * Discard this markdown's staged upload at TCGplayer — the undo for a push.
 *
 * ONLY BEFORE IT IS PUBLISHED, and the route enforces that rather than this client. Once the
 * rows are live TCGplayer no longer holds them staged, and a live price goes back the way it
 * came down: another markdown (D100 — nothing is deleted to change a price).
 */
export async function rollbackMarkdown(stamp: string): Promise<{ rolled_back: string; stamp: string }> {
  return (await request(`/pipeline/markdowns/${encodeURIComponent(stamp)}/rollback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm: true }),
  })) as { rolled_back: string; stamp: string }
}

/**
 * Move this markdown's staged upload LIVE. **This changes what buyers pay.**
 *
 * IT SENDS NO UPLOAD ID. The server reads that off the push receipt on disk, so a replayed or
 * mistyped body cannot publish an upload this markdown never made — and TCGplayer's `scope` is
 * pinned to "this upload" server-side, so the id IS the scope.
 */
export async function publishMarkdown(stamp: string): Promise<MarkdownPublish> {
  return (await request(`/pipeline/markdowns/${encodeURIComponent(stamp)}/publish`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm: true }),
  })) as MarkdownPublish
}

/**
 * Fetch the operator's own live listings from TCGplayer, and keep the file (D104).
 *
 * FREE. It starts no child and can put no number on an invoice — but it reads a secret and
 * opens a socket, which is the property `POST /pipeline/runs/<name>/export` already had and
 * almost nothing else does.
 *
 * THE SECOND DOCUMENT, NOT A SECOND SCOPE. `fetchExport` on a run brings the CATALOGUE, at
 * `MyInventory: False`, narrowed to that run's sets — the cards NOT listed. This brings the
 * opposite: everything live, every product line, which is what the markdown and the store-wide
 * reconcile both read. Hand the returned `fetched` name to either instead of an upload.
 *
 * Refusals worth branching on are the fetch family — `tcg_cookie_missing`,
 * `tcg_session_expired`, `tcg_request_rejected`, `tcg_unreachable` — each of which carries a
 * sentence saying whether the credential, the request or the host is the problem.
 */
export async function fetchLiveExport(): Promise<LiveExportFetched> {
  return (await request('/pipeline/live-export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
  })) as LiveExportFetched
}

/**
 * Every live listing one markdown's survey saw, refused rows included (D103).
 *
 * FREE, AND IT READS ONE FILE. This is the lens's whole input: `#/pricing?markdown=<stamp>`
 * draws the operator's entire live inventory out of it and lets staleness be a filter they
 * loosen rather than a decision taken before the data arrived.
 */
export async function getMarkdownTable(stamp: string): Promise<MarkdownTable> {
  return (await request(
    `/pipeline/markdowns/${encodeURIComponent(stamp)}/table`,
    NO_CACHE,
  )) as MarkdownTable
}

/**
 * The same reading `getPriceHistory` serves, addressed at a markdown instead of a run.
 *
 * ONE BODY, TWO ADDRESSES. The catalogue walk reads five identity cells off a verbatim export
 * row and a My Pricing export carries all five, so what a markdown needed was an address. It
 * LEAVES THE MACHINE exactly as the run route does — public hosts, nothing spent, one press.
 */
export async function markdownHistory(stamp: string, sku: string): Promise<PriceHistoryPayload> {
  return (await request(
    `/pipeline/markdowns/${encodeURIComponent(stamp)}/history?sku=${encodeURIComponent(sku)}`,
    NO_CACHE,
  )) as PriceHistoryPayload
}

/**
 * The strip, over the SKUs named — and the list is REQUIRED here where it is optional on a run.
 *
 * A survey is the whole live inventory. The run route measured 46 SKUs at ~34s of courtesy
 * delay, so an unfiltered walk over 441 rows is about five and a half minutes at a free public
 * mirror — which would make D62's press meaningless rather than merely slow. Send the rows the
 * operator is actually looking at, in chunks.
 */
export async function markdownTrends(stamp: string, skus: string[]): Promise<TrendsPayload> {
  const query = skus.map((sku) => `sku=${encodeURIComponent(sku)}`).join('&')
  return (await request(
    `/pipeline/markdowns/${encodeURIComponent(stamp)}/trends${query === '' ? '' : `?${query}`}`,
    NO_CACHE,
  )) as TrendsPayload
}

/** Every markdown this store has written, newest first. A read. */
export async function getMarkdowns(): Promise<{ markdowns: MarkdownSummary[] }> {
  return (await request('/pipeline/markdowns', NO_CACHE)) as { markdowns: MarkdownSummary[] }
}

/**
 * Where a markdown's files can be downloaded — the worklist to edit, the import to upload.
 *
 * A URL rather than a fetch, for `runFileUrl`'s reason: the browser's own download is what
 * the operator wants, and this is the file that goes into TCGplayer's My Pricing upload.
 */
export function markdownFileUrl(stamp: string, file: string): string {
  return `${base}/pipeline/markdowns/${encodeURIComponent(stamp)}/file?name=${encodeURIComponent(file)}`
}

/**
 * The pricing corpus — every listing answer this operator has given, and the policy (D86).
 *
 * ONE READ AND ONE WRITE FOR THE WHOLE SCREEN, whatever is on it. `#/pricing` used to fetch a
 * `decisions.json` per run it was showing and fan every answer back out to each of them; there
 * is one document now, so there is one of each.
 *
 * SEPARATE FROM `getPricingWorklist` BELOW ON PURPOSE. That answers which cards are in front
 * of the operator, out of which runs, with which export rows — it changes as the selection
 * does. This answers what has been decided, and it is the same document either way.
 */
export async function getPricingCorpus(): Promise<{
  corpus: PricingCorpus
  path: string
  revision: string
  /* WHICH ANSWERS A MASS-CLEAR MAY REMOVE, AND HOW OLD EACH ONE IS — IN THE ENVELOPE, beside
     `revision` and never inside `corpus`. `putPricingCorpus` sends the document back wholesale
     and the server round-trips every key it does not recognise, so a derived block written into
     the document would be carried into `inventory/prices.json` and read by the next screen as
     a stored fact. It is a reading of the file, not part of it.

     THE SERVER SAYS WHICH, THE SCREEN ONLY COUNTS. `#/pricing` has to put the figure in the
     label before the press — per scope and per age window — which means counting; it does that
     by intersecting this list with the rows it drew. Deciding *which answers are clearable*
     here instead would be `pipeline/corpus.py:clearable` written a second time in TypeScript,
     against the one file in this product that holds money. */
  clearable?: PricingClearable
}> {
  return (await request('/pricing', NO_CACHE)) as {
    corpus: PricingCorpus
    path: string
    revision: string
    clearable?: PricingClearable
  }
}

/**
 * Clear typed prices in bulk — the operator's own ask (D168):
 * *"after several emits a lot of pricing is pre typed but stale and there's no way to mass
 * clear"*.
 *
 * IT IS DESTRUCTIVE AND IT IS THE ONLY CALL IN THIS FILE THAT REMOVES A PRICING ANSWER. What
 * comes back is `cleared` — the answers themselves, with the dates they were typed on — which
 * is what `restorePricingAnswers` below puts back. A press that hands back a list of SKUs would
 * make the undo a re-type.
 *
 * `skus` IS A SCOPE AND NEVER A PREDICATE. Omit it for the whole store; pass the worklist's own
 * SKUs to hold the blast radius to what is on screen. Either way the server re-derives what may
 * go from the file as it stands, so this list can narrow the act and can never widen it: name a
 * hold here and it is reported as a hold, not cleared.
 *
 * `olderThanDays` IS A FILTER THE OPERATOR POINTS AND NOT A POLICY THE STORE CARRIES. Offered an
 * expiry rule — a typed price ageing out by itself — the owner said *"Just give me a mass-clear
 * button."* Omitted means every age.
 */
export async function clearPricingAnswers(options: {
  revision?: string
  skus?: readonly string[]
  olderThanDays?: number
}): Promise<PricingClearResult> {
  return (await request('/pricing/clear', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...(options.revision === undefined ? {} : { revision: options.revision }),
      ...(options.skus === undefined ? {} : { skus: [...options.skus] }),
      ...(options.olderThanDays === undefined
        ? {}
        : { older_than_days: options.olderThanDays }),
    }),
  })) as PricingClearResult
}

/**
 * Put back exactly what a clear removed — the way back, and the inverse of the call above.
 *
 * IT WRITES ONLY A SKU THE CORPUS NO LONGER ANSWERS, so an undo can never overwrite a price
 * typed since the clear; those come back named in `skipped`. And it writes each answer's `at`
 * verbatim rather than stamping it, because a restore is the assertion that an answer given
 * five days ago was never withdrawn — stamping would make the undo of a clear read as a
 * store-wide re-pricing on the next markdown survey (D103's ratchet).
 *
 * HAND IT A CLEAR'S OWN `cleared` MAP AND NOTHING ELSE. It is not a general write path — that
 * is `putPricingCorpus`, unchanged.
 */
export async function restorePricingAnswers(
  answers: PricingClearResult['cleared'],
  revision?: string,
): Promise<{ ok: boolean; restored: string[]; skipped: string[]; revision: string }> {
  return (await request('/pricing/restore', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(revision === undefined ? { answers } : { answers, revision }),
  })) as { ok: boolean; restored: string[]; skipped: string[]; revision: string }
}

/**
 * Replace the corpus. Wholesale, for D49's reason: the screen round-trips every key it does
 * not understand, so a hand-written `_note` survives a client that never heard of it. This is
 * the ONE pricing write in the app — the per-run `PUT .../decisions` it replaced is deleted
 * (D86, amended 2026-09-02).
 */
export async function putPricingCorpus(
  corpus: PricingCorpus,
  revision?: string,
): Promise<{ ok: boolean; written: string; answers: number; revision: string }> {
  /* `revision` IS THE STALE-WRITE GUARD AND IT TRAVELS BESIDE THE DOCUMENT, NEVER IN IT. This
     route replaces `inventory/prices.json` wholesale, so a screen holding a snapshot from mount
     silently reverts anything written underneath it on the next keystroke — no error anywhere,
     on the one file in this product that holds money. Two tabs on `#/pricing` reach that today,
     and so does `pkmnscan prices adopt --write` while one is open.

     Sending it INSIDE the corpus would put it in the object `Pricing.tsx` dirty-checks by
     identity, and every landed write would then rebuild that object and re-dirty the screen —
     an endless unsaved -> saving -> unsaved oscillation. Omitted means "did not read one",
     which the route allows for the terminal user editing the file by hand. */
  return (await request('/pricing', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(revision === undefined ? { corpus } : { corpus, revision }),
  })) as { ok: boolean; written: string; answers: number; revision: string }
}

/**
 * One import file over several runs — free, and it writes the CSV and raises `pushed` (D86).
 *
 * A LIST AND NOT N PRESSES OF THE PER-RUN EMIT, because the cap is re-derived across the send:
 * `pipeline/join.py` spends `live_cap - copies_out` per run against a cap that is global, so N
 * separate presses ARE the over-push this prevents. Measured, three separate emits over three
 * real runs wrote two SKUs past the cap of four; one merged emit wrote none.
 */
export async function emitMerged(
  runs: readonly string[],
  /* `splitThreshold` restores the old pair of files — `import-listed.csv` and
     `import-subthreshold.csv` — around D9's cut-off. Emit writes ONE `import.csv` without it. */
  /* `cap` IS THIS SEND'S OWN BOUND AND ORDINARILY ABSENT (D7, rewritten 2026-09-07). There is no
     standing cap any more: every copy this run holds that TCGplayer does not already have
     goes out, and this is how one press says otherwise. Omitted rather than sent as a
     sentinel, so "no cap" is the absence of a claim rather than a number meaning none. */
  /* `quantities` IS THE OPERATOR'S OWN FIGURE FOR A CARD, THIS PRESS ONLY (D7, amended 2026-09-11):
     SKU -> how many of its copies go in this file, bounded server-side by the copies on hand
     that are not already listed. A send quantity and not a ceiling, which is what `cap` is.
     Omitted when empty, for the reason `cap` is: a press that named no card sends no claim. */
  options: {
    listedOnly?: boolean
    splitGames?: boolean
    splitThreshold?: boolean
    cap?: number | null
    quantities?: Record<string, number>
  } = {},
): Promise<RunStepResult & { runs: string[] }> {
  return (await request('/pipeline/emit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      runs,
      listed_only: Boolean(options.listedOnly),
      split_games: Boolean(options.splitGames),
      split_threshold: Boolean(options.splitThreshold),
      ...(typeof options.cap === 'number' ? { cap: options.cap } : {}),
      ...quantitiesClaim(options.quantities),
    }),
  })) as RunStepResult & { runs: string[] }
}

/**
 * The cross-run pricing worklist — one list of cards over several runs (D86).
 *
 * WITH NO ARGUMENT IT ASKS FOR THE WORK, NOT FOR EVERYTHING. The server picks every run that
 * still has pricing in it: joined and never emitted, or emitted and still blocking `emit`.
 * That is the state `#/pricing` opens in, and it is why the screen needs no scope on arrival.
 *
 * `run` REPEATS rather than carrying a comma list, matching `getPriceTrends` above and
 * `/scope` beside it, for their reason: a comma inside a value is indistinguishable from the
 * separator. A named run is drawn whether or not the server would have chosen it — asking for
 * one has already answered the question the filter exists to ask.
 *
 * IT IS A READ AND IT SPENDS NOTHING. The write path is `putPricingCorpus` above — one
 * document for the store, however many runs are on screen.
 */
export async function getPricingWorklist(runs: readonly string[] = []): Promise<PricingWorklist> {
  const query = runs.map((run) => `run=${encodeURIComponent(run)}`).join('&')
  return (await request(
    `/pipeline/pricing${query === '' ? '' : `?${query}`}`,
    NO_CACHE,
  )) as PricingWorklist
}

/**
 * Every card on hand, ranked by what TCGplayer says it is worth, with the drawer each one
 * sits in — so the operator can take a band out of the boxes.
 *
 * IT TAKES NO BAND, AND THAT IS THE DESIGN RATHER THAN AN OMISSION. Four ways of choosing one
 * were asked for — a typed price, the store's own cut-off, a top-N percentile and the drawers
 * ranked by value — and every one is a slice of the single ranked list this answers with. A
 * percentile cannot be taken without the whole list anyway, and a `?band=` would be a second
 * place for the sort's tie-break to be decided.
 *
 * THE PAYLOAD IS THE WHOLE STORE, WHICH IS WHY IT IS FETCHED ONCE AND NOT POLLED. Measured on
 * the owner's store: 2,245 rows, ~739KB, 0.11s server-side — the same order as
 * `getPricingWorklist` above (~909KB across eight tables) and for the same reason. It reads
 * and presses nothing: no child, no socket, no lock, no write.
 */
export async function getValueTable(): Promise<ValueTable> {
  return (await request('/pipeline/value', NO_CACHE)) as ValueTable
}

/**
 * What one SKU has actually been selling for — a volume-weighted mean, a momentum reading
 * and the buckets behind them, over a daily range and a weekly one.
 *
 * THE ONE CALL IN THIS FILE THAT LEAVES THE MACHINE, and it is worth knowing at the call
 * site rather than only in the server. The capture server fetches from `tcgcsv.com` and
 * `infinite-api.tcgplayer.com` to answer it: both public, no key, no account, nothing spent.
 * What it costs is TIME — about 1.3s cold and 5ms warm, measured — because the walk is
 * sku -> product -> history across two hosts, cached on disk with the module's own TTLs.
 *
 * SO IT MAY NEVER BE FIRED BY A WALK. This is not a preference and it is the reason the
 * control on `#/pricing` is a press rather than an effect on the focused row: arrowing down
 * fifty SKUs with a follow-focus panel open would be fifty requests at a free public mirror,
 * which is the one way this feature could become rude. One press, one card.
 *
 * IT PRICES NOTHING. D8 makes the TCGplayer export the pricing source and this reopens none
 * of it — the payload carries the export's own `market` beside the reading so the two can be
 * put side by side, and nothing here is written back or fed to a rule.
 *
 * Refusals worth branching on: `not_catalogued` (a `misc` card has no product line to look a
 * category up by, which D22 makes permanent rather than a missing export),
 * `history_unresolved` (no single product matched — it refuses rather than guessing),
 * `history_unreachable` (a mirror did not answer; nothing is wrong with the run),
 * `sku_not_in_run` and `pricing_not_written`.
 */
export async function getPriceHistory(
  run: string,
  sku: string,
): Promise<PriceHistoryPayload> {
  return (await request(
    `/pipeline/runs/${encodeURIComponent(run)}/history?sku=${encodeURIComponent(sku)}`,
    NO_CACHE,
  )) as PriceHistoryPayload
}

/**
 * The same reading for MANY SKUs at once — a shape and a sign each, for the strip on the row.
 *
 * D62 NAMED THIS CALL AND THE CONDITION FOR MAKING IT. That entry made the history a press
 * per card precisely so a walk down fifty rows could not fire fifty requests, and it named
 * what would reopen the question: the panel being wanted on every card, answered by a
 * BATCHED route and a column on the row. The owner asked for exactly that on 2026-08-31, and
 * D79 is the answer.
 *
 * SO IT IS STILL A PRESS AND MAY NEVER BECOME AN EFFECT. Nothing about this being one call
 * instead of forty-six makes it cheap: it is ~92 requests at two free public mirrors, 37.7s
 * cold and 0.15s warm, measured on `2026-08-31-box3-01`. A `useEffect` that fired it on mount
 * would spend that on every visit to `#/pricing` for readings nobody asked for, which is the
 * one way D62 said this feature could become rude — and the reason it is rude has nothing to
 * do with how many HTTP calls the browser makes.
 *
 * `skus` IS THE CHUNK AND IT IS WHY THE STRIP FILLS IN WAVES. With none, the route walks the
 * run's own table and skips the rows it can add nothing for; with a list, it fetches exactly
 * those. The caller splits the open rows into small groups so 37 seconds arrives as six
 * partial answers rather than one blank half-minute.
 *
 * IT PRICES NOTHING. Every field it carries is dimensionless or a date — see `TrendRange`,
 * which says why the dollars stayed on the panel.
 */
export async function getPriceTrends(run: string, skus: string[] = []): Promise<TrendsPayload> {
  /* `sku` REPEATS rather than carrying a comma list, matching `/scope`'s `set_ids` one route
     down and for its reason: a comma inside a value is indistinguishable from the separator. */
  const query = skus.map((sku) => `sku=${encodeURIComponent(sku)}`).join('&')
  return (await request(
    `/pipeline/runs/${encodeURIComponent(run)}/trends${query === '' ? '' : `?${query}`}`,
    NO_CACHE,
  )) as TrendsPayload
}

/** Every run, newest first. A read; costs nothing and holds nothing, so a run started from
 *  a terminal appears here exactly as one started from this app does. */
export async function getRuns(): Promise<RunSummary[]> {
  const body = (await request('/pipeline/runs', NO_CACHE)) as { runs: RunSummary[] }
  return body.runs
}

/** One run, with its console tail and its artefacts. This is the poll. */
export async function getRun(name: string): Promise<RunDetail> {
  return (await request(`/pipeline/runs/${encodeURIComponent(name)}`, NO_CACHE)) as RunDetail
}

/**
 * A free step: `join`, `emit` or `reconcile`. Runs inside the request and returns its own
 * stdout.
 *
 * A NON-ZERO EXIT IS NOT A THROW. The promise resolves with `ok: false` and the console
 * attached, because `emit` refusing while a price is unanswered is the most useful thing
 * that command does and the screen needs the sentence naming the SKU, not an error class.
 * Only a refusal the ROUTE made — a bad rule, a file that is not a CSV, a run that does not
 * exist — arrives as a `ServerError`.
 *
 * `exports` absent means re-use whatever this run was last joined against, which is what
 * keeps `join` free and re-runnable from a screen: change the rule, clear a review, press
 * it again. An empty array is refused rather than read as that, because a selection that
 * failed to send must not silently become "use the old file".
 *
 * `fetched` names files this run already holds, put there by `fetchExport` (D64). A name
 * rather than a re-upload: the server has the bytes. The two compose, which is what a
 * mixed-game run needs — one game fetched beside another uploaded.
 */
/**
 * Fetch this run's Filtered Export from TCGplayer instead of downloading and uploading it
 * (D64). Free: it spends nothing, and `POST /pipeline/identify` is still the only route that
 * can. Reported separately from the join so a failure is attributable to one or the other.
 *
 * EVERY REFUSAL IS A SENTENCE WITH NOTHING TO PRESS. `tcg_cookie_missing`,
 * `tcg_session_expired`, `tcg_blocked`, `export_wrong_game` and `export_scope_incomplete`
 * each arrive as a `ServerError` carrying a sentence to read, and each is fixed somewhere
 * other than this screen. The two acknowledgements this once took — `acceptUnverified` and
 * `acceptNarrower` — went with the delta guard they answered (D64, amended 2026-09-02): D65
 * names the scope, so the file is checked for what was asked, and the receipt's `previous`
 * says what the last join used beside what arrived.
 */
/**
 * The real set names for a game (D65), for the capture screen's hint field.
 *
 * NEVER THROWS FOR A MISSING LIST. The server answers 200 with an empty `sets` and a `reason`
 * whenever it could not fetch — no cookie, no network, the portal down — because the capture
 * screen is the rig and D19 measures its cadence in milliseconds. A hint field that refused to
 * open because an autocomplete failed would be a worse product than one with no autocomplete.
 */
export async function getTcgSets(game: string): Promise<TcgSets> {
  return (await request(`/tcg/sets?game=${encodeURIComponent(game)}`, NO_CACHE)) as TcgSets
}

/**
 * What a fetch WOULD ask TCGplayer for, before one is pressed (D76).
 *
 * FREE, AND IT PRESSES NOTHING. The same three fields `fetchExport` takes go out here, so the
 * panel describes the scope the button is about to send rather than a second guess at it.
 *
 * NEVER THROWS FOR A MIXED-GAME RUN. `POST .../export` refuses one with `game_required`
 * because a category is scalar; this answers 200 with the list, because the screen that has
 * to ask which game cannot draw the picker from a route that refuses without one.
 */
export async function getExportScope(
  name: string,
  options: { game?: string; scope?: 'category' | 'sets'; setIds?: number[] } = {},
): Promise<ExportScope> {
  const query = new URLSearchParams()
  if (options.game !== undefined) query.set('game', options.game)
  if (options.scope !== undefined) query.set('scope', options.scope)
  /* REPEATED rather than comma-joined, which is the shape the dispatcher reads with
     `parse_qs`. A comma list is one value away from a set name that contains a comma. */
  for (const id of options.setIds ?? []) query.append('set_ids', String(id))
  const tail = query.toString()
  return (await request(
    `/pipeline/runs/${encodeURIComponent(name)}/scope${tail === '' ? '' : `?${tail}`}`,
    NO_CACHE,
  )) as ExportScope
}

export async function fetchExport(
  name: string,
  options: {
    /** Which category to ask for. Required only where the run holds more than one game —
     *  one fetch answers for one category, because `CategoryId` is scalar in the portal. */
    game?: string
    /** D76's axis. Absent uses the game's own rule from the registry. */
    scope?: 'category' | 'sets'
    /** TCGplayer set ids, ticked by hand. Outranks both the rule and the cards' own hints:
     *  the unanimity rule guesses at what the box is, and this is somebody saying. */
    setIds?: number[]
  } = {},
): Promise<ExportFetched> {
  return (await request(`/pipeline/runs/${encodeURIComponent(name)}/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      game: options.game,
      scope: options.scope,
      set_ids: options.setIds,
    }),
  })) as ExportFetched
}

export async function runStep(
  name: string,
  step: 'join' | 'emit' | 'reconcile',
  options: {
    exports?: CsvUpload[]
    fetched?: string[]
    stagedExport?: CsvUpload
    rule?: string
    basis?: 'market' | 'low'
    reviewBelowConfidence?: 'none' | 'low' | 'medium'
    dryRun?: boolean
    /* The emit options, on the per-run step for the same reason `emitMerged` above takes
       them: one press writes ONE `import.csv`, and either split is asked for rather than
       arrived at by default. `bypass` sat here until D3's amendment retired the finish
       cross-check — there is no claim left for a flag to override. */
    listedOnly?: boolean
    splitGames?: boolean
    splitThreshold?: boolean
    /* THIS SEND'S CAP, ORDINARILY ABSENT (D7, rewritten 2026-09-07) — and here for the same
       reason the three flags above are: a send of one and a send of three are the same
       command, so an option offered on one and not the other would be answering a question
       about how many runs happen to be open. */
    cap?: number | null
    /* THE PER-CARD FIGURES, for the same reason — one card or three runs, one control. */
    quantities?: Record<string, number>
  } = {},
): Promise<RunStepResult> {
  return (await request(`/pipeline/runs/${encodeURIComponent(name)}/${step}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      exports: options.exports,
      fetched: options.fetched,
      staged_export: options.stagedExport,
      rule: options.rule,
      basis: options.basis,
      review_below_confidence: options.reviewBelowConfidence,
      dry_run: options.dryRun,
      listed_only: options.listedOnly,
      split_games: options.splitGames,
      split_threshold: options.splitThreshold,
      /* Spread rather than sent as `undefined`, so "no cap" is the ABSENCE of a claim. The
         route refuses `cap: 0` by name, and a screen spelling "none" as a number would turn
         the ordinary press into a refusal. */
      ...(typeof options.cap === 'number' ? { cap: options.cap } : {}),
      ...quantitiesClaim(options.quantities),
    }),
  })) as RunStepResult
}

/** The `quantities` key for an emit body, or nothing at all when no card was given a figure.
 *  The route refuses a malformed map by name; an empty one would be a claim about nothing,
 *  so — as with `cap` — the ordinary press carries no key rather than an empty object. */
function quantitiesClaim(asked: Record<string, number> | undefined): { quantities?: Record<string, number> } {
  if (asked === undefined || Object.keys(asked).length === 0) return {}
  return { quantities: asked }
}

/**
 * Where a run artefact can be downloaded. The import CSVs, the report, `pricing.json`.
 *
 * A URL rather than a fetch, because the browser's own download is what the operator wants
 * — this is the file that goes into TCGplayer's Import to Staged, and a string in a text
 * area is not that. `docs/GATES.md` names the gap this closes: emit's import files existed
 * only as filenames in terminal output the owner never saw.
 */
export function runFileUrl(name: string, file: string): string {
  return `${base}/pipeline/runs/${encodeURIComponent(name)}/file?name=${encodeURIComponent(file)}`
}

/* ------------------------------------------------------------------ the code-card track */

/** The whole code ledger. A read — reserves nothing, commits nothing. */
export async function getCodes(): Promise<CodeLedger> {
  return (await request('/codes', NO_CACHE)) as CodeLedger
}

/**
 * Decode one box's photographs into the ledger.
 *
 * FREE, AND UNLIKE `startIdentify` THERE IS NO MONEY GATE HERE. The code-card primary path
 * makes no model call and no network call of any kind — the redemption code IS the QR's
 * payload — so there is nothing to confirm and nothing to spend. `preview` exists anyway,
 * for the reason a dry run always exists: seeing what a write would do before it happens is
 * worth having even when the write is cheap.
 */
export async function scanCodes(input: {
  box: number
  preview?: boolean
}): Promise<CodeScanResult> {
  return (await request('/codes/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ box: input.box, preview: Boolean(input.preview) }),
  })) as CodeScanResult
}

/**
 * Preview a channel export, or COMMIT one to an order.
 *
 * THE TWO-STEP IS D33's SHAPE FOR A DIFFERENT IRREVERSIBLE THING. D33 gates the route that
 * spends money; this gates the one that hands over a bearer instrument. Without `confirm`
 * nothing is reserved and the call is a pure read. With `confirm` and an `orderId` every
 * code returned is reserved permanently and can never be offered to anybody else — which is
 * C3's atomic dequeue and the structural defence against double-selling a code.
 *
 * ALL OR NOTHING: asking for more than the lane holds reserves NOTHING and refuses as
 * `not_enough_codes`, rather than filling what it can.
 */
export async function exportCodes(input: {
  lane: 'bulk' | 'premium'
  product?: string | null
  count?: number | null
  confirm?: boolean
  orderId?: string
  buyer?: string | null
}): Promise<CodeExportResult> {
  const payload: Record<string, unknown> = { lane: input.lane }
  if (input.product) payload.product = input.product
  if (typeof input.count === 'number') payload.count = input.count
  if (input.confirm) {
    payload.confirm = true
    payload.order_id = input.orderId
    if (input.buyer) payload.buyer = input.buyer
  }
  return (await request('/codes/export', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })) as CodeExportResult
}


/** Every lot built so far, newest first. Receipts only — no codes cross this wire. */
export async function getLots(): Promise<{ lots: LotReceipt[] }> {
  return (await request('/codes/lots', NO_CACHE)) as { lots: LotReceipt[] }
}

/**
 * Plan a lot, or BUILD one.
 *
 * THE SAME TWO-STEP AS `exportCodes`, and for the same reason: building reserves every code
 * in the lot permanently. Without `confirm` nothing is reserved and nothing is written.
 *
 * A PHYSICAL LOT MUST BE BOX-SCOPED, and the server refuses otherwise rather than trusting
 * this call site. Chosen by count, the codes reserved and the cards pulled off the shelf are
 * two different piles — and a physical lot is additionally refused unless it takes the
 * WHOLE box, because "pull all of them except these three" is not an instruction anyone
 * executes reliably against a thousand identical cards.
 */
export async function buildLot(input: {
  scope: 'box' | 'count'
  delivery: 'physical' | 'digital'
  venue: string
  box?: number | null
  count?: number | null
  premium?: boolean
  confirm?: boolean
  lotId?: string
  buyer?: string | null
}): Promise<LotResult> {
  const payload: Record<string, unknown> = {
    scope: input.scope,
    delivery: input.delivery,
    venue: input.venue,
    premium: Boolean(input.premium),
  }
  if (typeof input.box === 'number') payload.box = input.box
  if (typeof input.count === 'number') payload.count = input.count
  if (input.confirm) {
    payload.confirm = true
    if (input.lotId) payload.lot_id = input.lotId
    if (input.buyer) payload.buyer = input.buyer
  }
  return (await request('/codes/lots', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })) as LotResult
}

// ---------------------------------------------------------------------------- the orders

/**
 * Every order, and where the copies for the open ones are (D63, D69).
 *
 * ONE SNAPSHOT ON THE SERVER, WHICH IS WHY THIS IS ONE CALL AND NOT TWO. The list and the
 * resolution are computed from the same read, so they cannot disagree; two fetches could
 * straddle a sale and show a card both on hand and gone. A screen that wants either half
 * calls this.
 *
 * A READ. It writes nothing, holds nothing and spends nothing, and it may be polled.
 */
export async function getOrders(): Promise<OrdersPayload> {
  return (await request('/orders', NO_CACHE)) as OrdersPayload
}

/**
 * Take the feed's word for what was bought. D63's one map: it touches `orders.json` and
 * cannot touch `inventory.json`, because `Ledger.ingest` holds no `Inventory`.
 *
 * THIS FUNCTION DOES NOT PROJECT, AND THAT IS THE WHOLE DESIGN. Its argument is ALREADY the
 * projection, minted by `app/src/orderPaste.ts` — so exactly one place in this app decides
 * what leaves the browser about a purchase, and a reviewer asking "where does the buyer's
 * name get dropped" has one file to read. A second module composing an ingest body would be
 * a second door onto the same wire, and the whitelist guarantee would be gone. The server's
 * three allowlist tuples are the backstop, not the boundary: an unprojected paste refuses by
 * name (`field_not_settable`) rather than being stored with the extra fields trimmed.
 *
 * A SECOND IDENTICAL PASTE IS A NO-OP DOWN TO THE BYTE and answers `wrote_nothing: true`.
 * Refusals worth branching on: `orders_required` (an empty list, which is not the same
 * answer as "learned nothing"), `too_many_orders`, `duplicate_line` (409 — two lines sharing
 * a SKU would make "how many have we pulled" a question with two answers), and
 * `order_key_invalid`, whose only real cause is a colon in the SOURCE.
 */
export async function ingestOrders(orders: readonly OrderIngestOrder[]): Promise<IngestResult> {
  return (await request('/orders/ingest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    /* `{ orders }` AND NOTHING ELSE. The array is passed through rather than rebuilt field
     * by field — the opposite of `answerGroup` above — because rebuilding it here would be
     * this module owning a second copy of the projection `orderPaste.ts` owns. What makes
     * that safe is that the argument's type is the projection: a wider object cannot reach
     * this line without being typed as one first. */
    body: JSON.stringify({ orders }),
  })) as IngestResult
}

/**
 * Ask TCGplayer for this account's own orders, instead of pasting them (D69).
 *
 * FREE, AND IT IS NOT THE MONEY GATE. `POST /pipeline/identify` is still the one route in
 * this product that can cause a charge. This is a read against
 * `order-management-api.tcgplayer.com` with the session cookie already in `.env` — the same
 * account session `fetchExport` uses one host over — and it writes nothing at all, not even
 * the ledger.
 *
 * IT ANSWERS EXACTLY WHAT `ingestOrders` TAKES, so the result's `orders` array is sent on
 * unaltered. That is the shape's whole purpose: no adapter between the two, and the fetch
 * enters the app through the same one door the paste does.
 *
 * TWO PRESSES SINCE D91, BECAUSE ONE NEVER WORKED ON THIS ACCOUNT: the three-month window
 * holds 370 orders against a detail cap of 100, and the single-body fetch was refused on every
 * press. `previewOrders` below walks the cheap search pages and counts the window by status;
 * this call details only the `statuses` the operator ticked — the strings the preview returned,
 * verbatim, no vocabulary on either side — and, with `skip_known`, only the orders the ledger
 * does not already hold at that status. Past the transport's cap the rest comes back as
 * `remaining`, and the next press picks it up.
 *
 * `range` is one of the transport's `KNOWN_RANGES`; omit it for its default. Refusals worth
 * branching on are the transport's own codes — `order_cookie_missing`,
 * `order_seller_key_rejected` (a 403, which reads exactly like an expired session and is
 * not one: `PKMNSCAN_TCG_SELLER_KEY` is missing), `order_session_expired` — each carrying a
 * sentence naming what to fix.
 */
export async function fetchOrders(options: {
  statuses: readonly string[]
  skip_known?: boolean
  range?: string
}): Promise<OrdersFetched> {
  return (await request('/orders/fetch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      statuses: [...options.statuses],
      ...(options.skip_known === undefined ? {} : { skip_known: options.skip_known }),
      ...(options.range === undefined ? {} : { range: options.range }),
    }),
  })) as OrdersFetched
}

/**
 * Count this account's orders by status before fetching any (D91). Writes nothing and details
 * nothing: one search page per 25 orders in the window, and the status strings TCGplayer used,
 * verbatim, each with how many of its orders the ledger already holds. The tick list
 * `fetchOrders` takes is drawn from this and from nothing in this file.
 */
export async function previewOrders(range?: string): Promise<OrdersPreview> {
  return (await request('/orders/fetch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(range === undefined ? { preview: true } : { preview: true, range }),
  })) as OrdersPreview
}

/* One route in both directions — `POST /orders/pull`, with `{"undo": true}` to reverse — and
 * two exported wrappers over it, for `sale()`'s own reason above: a boolean at the call site
 * reads as `pull(target, true)` and the reader has to come here to learn which way that goes.
 *
 * BODY-ADDRESSED AND NOT PATH-ADDRESSED, which is forced rather than chosen. An order key is
 * `source:number` and a NUMBER may legally contain a colon — `store/orders.py` splits on the
 * FIRST one for exactly that reason — so a key in a path segment would need an escaping rule
 * that the one place it is composed does not have.
 */
async function pull(body: Record<string, unknown>): Promise<PullResult> {
  return (await request('/orders/pull', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })) as PullResult
}

/**
 * Close copies of an order line with NO card behind them (D113).
 *
 * THE WRITE `pullCopy` CANNOT MAKE, and the reason it exists. That one records `capture_id`s
 * and sells the cards they name; a sealed Holiday Calendar has no card record and never will,
 * and neither has a single that shipped from a pile this rig never photographed. Three real
 * orders on the owner's store were permanently open for exactly that, with no control on any
 * screen able to move them.
 *
 * NOT IDEMPOTENT, UNLIKE `pullCopy`. A capture id is an identity, so a repeated pull is a
 * no-op by construction; a hand-fill has no identity to compare and two presses are two
 * claims. It ADDS, `over_fulfilled` is the ceiling, and `undoFill` is how a mis-press is
 * reversed. Draw what is already recorded rather than trusting the press to be safe twice.
 *
 * It sells nothing and touches no card — `Ledger` holds no `Inventory`, so the capability is
 * absent rather than guarded. Refusals: `reason_required`, `fill_reason_invalid`,
 * `count_invalid`, `count_too_large`, `order_not_ingested`, `sku_not_on_order`,
 * `over_fulfilled`.
 */
export async function fillLine(
  line: { source: string; number: string; sku: string },
  count: number,
  reason: OrderFillReason,
): Promise<OrderFillResult> {
  return (await request('/orders/fill', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source: line.source, number: line.number, sku: line.sku, count, reason }),
  })) as OrderFillResult
}

/** `fillLine`'s reversal. It can only reach the hand-filled copies: a line carrying two
 *  pulled copies and one hand-filled one reverses to two pulled copies. Reversing a PULL is
 *  `undoPull`, which needs the capture ids this route never had. */
export async function undoFill(
  line: { source: string; number: string; sku: string },
  count: number,
): Promise<OrderFillResult> {
  return (await request('/orders/fill', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source: line.source, number: line.number, sku: line.sku, count, undo: true }),
  })) as OrderFillResult
}

/**
 * Record what the OPERATOR says a line is (D113). `null` withdraws the claim.
 *
 * SEPARATE FROM `fillLine` ON PURPOSE, AND THE SHIPPING LANE IS WHY. A sealed product needs
 * classifying BEFORE it goes out — that is what routes it to the parcel lane rather than an
 * envelope it does not fit — and it is filled only once it has. One call doing both would
 * make the routing answer unavailable until the moment it stopped mattering.
 *
 * The claim lives in the fulfilment map, so it survives the next sync: `ingest` replaces the
 * order record wholesale, and a kind written onto the feed's copy would die the moment the
 * marketplace moved the status string. Refuses `line_kind_invalid` for a kind the resolver
 * does not know — the raise it prevents happens at RESOLVE time and takes the whole screen
 * down for one bad write.
 */
export async function declareLineKind(
  line: { source: string; number: string; sku: string },
  kind: OrderLineKind | null,
): Promise<OrderLineKindResult> {
  return (await request('/orders/line-kind', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source: line.source, number: line.number, sku: line.sku, kind }),
  })) as OrderLineKindResult
}

/**
 * Stand whole orders down: they need nothing further from this store (D113).
 *
 * THE THIRD WAY A LINE STOPS OWING, AND IT COUNTS NOTHING. `pullCopy` records copies and
 * sells them, `fillLine` records a count for copies that went without a card record, this
 * records NEITHER. Measured 2026-09-06 on the owner's store: 69 of 83 open orders were ones
 * TCGplayer had already shipped, and the ledger had no way to say so — they sorted oldest
 * first and took 31 physical copies away from the orders that still needed picking.
 *
 * WHY NOT `fillLine` FOR THOSE, WHICH IS THE TEMPTING ONE-CALL ANSWER: many shipped using
 * copies STILL in the boxes as `identified`, because the sale never went through this store.
 * A fill would make the count read right while the card stayed on the shelf and got offered
 * to the next buyer.
 *
 * A BULK CALL, UNLIKE EVERY OTHER WRITE ON THIS SCREEN. The backlog it exists for was 69
 * orders on its first use, and 69 presses is not a control. Validate-all-then-write-all, so
 * a refusal leaves nothing written and names which orders were wrong.
 */
export async function closeOrders(
  orders: readonly { source: string; number: string }[],
  reason: OrderCloseReason,
): Promise<OrderCloseResult> {
  return (await request('/orders/close', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ orders: orders.map((o) => ({ source: o.source, number: o.number })), reason }),
  })) as OrderCloseResult
}

/**
 * Stand individual LINES down, leaving their siblings alone (D113).
 *
 * `closeOrders`' other scope, and the one a multi-line order needs. One refunded line on a
 * three-line order must not take the other two with it — the order-shaped call stands every line
 * down, which is right for a backlog of whole orders that already shipped and wrong for a single
 * line nobody is sending.
 *
 * ONE ROUTE, TWO SCOPES, because only the scope differs — both call `Ledger.close_line` and a
 * second route would be two spellings of one write. Sending `orders` AND `lines` in one body
 * refuses as `close_scope_ambiguous` rather than picking one, and a SKU the buyer did not order
 * refuses the whole press before any line moves.
 */
export async function closeLines(
  lines: readonly { source: string; number: string; sku: string }[],
  reason: OrderCloseReason,
): Promise<OrderCloseResult> {
  return (await request('/orders/close', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      lines: lines.map((l) => ({ source: l.source, number: l.number, sku: l.sku })),
      reason,
    }),
  })) as OrderCloseResult
}

/** `closeLines`' reversal. It reopens only the lines it names — a sibling the same press never
 *  touched stays exactly as it was. */
export async function reopenLines(
  lines: readonly { source: string; number: string; sku: string }[],
): Promise<OrderCloseResult> {
  return (await request('/orders/close', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      lines: lines.map((l) => ({ source: l.source, number: l.number, sku: l.sku })),
      undo: true,
    }),
  })) as OrderCloseResult
}

/** `closeOrders`' reversal. Puts the orders back on the open list exactly as they were; it
 *  touches no count, so a line that was also hand-filled keeps its fill. */
export async function reopenOrders(
  orders: readonly { source: string; number: string }[],
): Promise<OrderCloseResult> {
  return (await request('/orders/close', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ orders: orders.map((o) => ({ source: o.source, number: o.number })), undo: true }),
  })) as OrderCloseResult
}

/**
 * Record copies against one order line and mark them sold (D63).
 *
 * ONE CARD, ONE PRESS. The route takes a LIST because `record_pull` takes a sequence and
 * validate-all-then-write-all is the same code either way — not because a screen should
 * offer a batch control. Nothing in this product picks two cards at once.
 *
 * READ `places[0]?.label` FOR THE RECEIPT, NEVER `sales[0]?.card.place.label`. The places
 * come back AS THEY WERE BEFORE THE WRITE, one per target in request order; a sale moves the
 * box's occupancy (D58), so by the time the answer is composed the card is departed and its
 * own label reads `Box 3 · departed`.
 *
 * Refusals worth branching on: `pull_entry_refused` aggregates the per-target ones
 * (`duplicate_target`, `capture_id_mismatch` — the row on screen is aimed at a card that is
 * no longer at that slot, so re-read before retrying — `card_not_found`, `sku_mismatch`),
 * and `order_not_ingested`, `sku_not_on_order`, `copy_already_pulled` and `over_fulfilled`
 * are the ledger's. A refusal anywhere leaves `orders.json` AND `inventory.json` unmoved.
 */
export async function pullCopy(
  line: { source: string; number: string; sku: string },
  targets: readonly PullTarget[],
): Promise<PullResult> {
  return pull({
    /* camelCase in the argument, snake_case on the wire, HERE AND ONLY HERE — this module's
     * standing rule. The line is named field by field so a caller's wider row cannot put an
     * extra key on the wire, where `_reject_unknown` refuses the whole request. */
    source: line.source,
    number: line.number,
    sku: line.sku,
    targets: targets.map(({ box, index, capture_id }) => ({ box, index, capture_id })),
  })
}

/**
 * Put pulled copies back: un-record them against the line and reverse the sale.
 *
 * IT SENDS `{ undo: true, targets }` AND NOTHING ELSE. The caller does not name the line and
 * CANNOT — the server scans the ledger for whoever holds each `capture_id`, which is the one
 * identity a renumber cannot move. An undo that also named an order is refused rather than
 * obeyed with the order ignored, which is why this wrapper cannot take one.
 *
 * Two refusals worth telling apart: `pull_not_recorded` means the ledger has no record of
 * this copy at all, and the remedy is `#/inventory`'s own sale undo rather than this route;
 * `pull_spans_lines` means the targets belong to two different lines, and the remedy is to
 * undo them separately.
 */
export async function undoPull(targets: readonly PullTarget[]): Promise<PullResult> {
  return pull({
    undo: true,
    targets: targets.map(({ box, index, capture_id }) => ({ box, index, capture_id })),
  })
}

// -------------------------------------------------------------------------- the shipping

/**
 * Read TCGplayer's `Orders → Export Shipping` file into D61's three lanes.
 *
 * THE BATCH LIVES IN THE CAPTURE SERVER'S MEMORY AND TOUCHES NO DISK. D61 rules that buyer
 * PII passes through and is not persisted, so what comes back is a handle with a half-hour
 * TTL — not a run artefact, not a cache entry, not a log line. A server restart drops it,
 * and `make up` reloads on any Python edit under `server/`, so an edit during a session IS a
 * restart. Two devices do not share a batch either: the phone that read the export cannot
 * download the import file from the laptop.
 *
 * WHAT COMES BACK CARRIES NO BUYER. No name, no address, no city, no postcode — see
 * `ShippingRow` in types.ts, where the absence is the design. Those details cross this wire
 * exactly once, as the CSV `shippingFileUrl` downloads.
 *
 * The body is the `CsvUpload` object itself and nothing more.
 */
export async function readShippingExport(upload: CsvUpload): Promise<ShippingBatch> {
  // NAME AND CONTENT ONLY — `modified` is `CsvUpload`'s newest field (D59/D87 amended), added
  // for a fetched or uploaded PRICING export so `live` can be arbitrated by which reading is
  // newer. This batch touches no disk and settles nothing against `live`; carrying the file's
  // timestamp here would be a field this route reads for no reason, which is exactly the
  // opsec argument above the read side of this wire ("what comes back carries no buyer" —
  // the same discipline applies to what goes out).
  return (await request('/shipping/batches', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: upload.name, content: upload.content }),
  })) as ShippingBatch
}

/**
 * Where a batch's import CSV can be downloaded — the file that goes into Pirate Ship.
 *
 * A URL RATHER THAN A FETCH, because the browser's own download is what the operator wants.
 * The same idiom as `runFileUrl` above and for the same argument: a CSV in a text area is
 * not a file anybody can import.
 *
 * It is a GET, so it is not behind the origin gate every write on this server sits behind —
 * which is why the batch id is 128 random bits rather than a counter.
 */
export function shippingFileUrl(batch: string, file: string): string {
  return `${base}/shipping/batches/${encodeURIComponent(batch)}/file?name=${encodeURIComponent(file)}`
}

/**
 * Fill the three Rubber Stamp corners on a batch's rows, out of the order ledger (T2b).
 *
 * FREE, RE-RUNNABLE AND IDEMPOTENT, so it needs no gate and no confirmation: it spends
 * nothing, opens no socket and writes no file. The server re-asks the store on every press
 * and SETS the stamps rather than adding to them, which is what makes a second press a
 * no-op rather than a four-stamp refusal — the property `do_shipping_stamps`'s own check
 * had to be corrected once before it was true.
 *
 * IT ANSWERS THE SAME OBJECT `readShippingExport` DOES, so the caller replaces its batch
 * wholesale rather than merging counts into one it already holds. `stamp` on every row and
 * `stamps` on the batch have been on the wire as nulls since the seam was cut, so filling
 * them changes no type and no component — `OrdersShipStage.tsx` already draws both.
 *
 * WHAT IT DOES NOT DO IS RE-UPLOAD ANYTHING. The batch is held in the server's memory for
 * its TTL and the operator downloads the file again; nothing about this reaches Pirate Ship
 * or TCGplayer, and an order the ledger does not hold simply keeps its corners empty.
 */
export async function fillShippingStamps(batch: string): Promise<ShippingBatch> {
  return (await request(`/shipping/batches/${encodeURIComponent(batch)}/stamps`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  })) as ShippingBatch
}

/**
 * Drop a batch now rather than in half an hour.
 *
 * THE WAY BACK CLAUDE.md's HARD RULE ASKS OF ANYTHING THAT HOLDS A BUYER'S ADDRESS, and the
 * reason the TTL is a backstop rather than the only release. The answer names what was
 * removed, matching every other delete this server answers; a later `shippingFileUrl` for
 * that batch is a 404 with a sentence saying it was forgotten.
 */
export async function forgetShippingExport(batch: string): Promise<ShippingForgotten> {
  return (await request(`/shipping/batches/${encodeURIComponent(batch)}`, {
    method: 'DELETE',
  })) as ShippingForgotten
}
