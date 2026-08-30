import type {
  AnswerResult,
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
  BoxDeleteResult,
  BoxListingPlan,
  ListingReleaseResult,
  CropPreview,
  CsvUpload,
  RunDetail,
  PricingPayload,
  RunLeg,
  RunPreflight,
  RunStarted,
  RunStepResult,
  RunSummary,
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
 * the right guess when nothing has told us which tree this is. */
const FALLBACK_BASE = 'http://localhost:8000'
const derived: unknown = import.meta.env.VITE_CAPTURE_DEFAULT
const DEFAULT_BASE =
  typeof derived === 'string' && derived.trim() !== ''
    ? derived.trim().replace(/\/+$/, '')
    : FALLBACK_BASE
const configured: unknown = import.meta.env.VITE_CAPTURE_SERVER

/* Trailing slashes stripped so `${base}/status` cannot become `//status`, which some
 * servers route and this one answers with `no_such_route` — a confusing failure to debug
 * for a stray character in a `.env` file nobody is looking at. */
const base =
  typeof configured === 'string' && configured.trim() !== ''
    ? configured.trim().replace(/\/+$/, '')
    : DEFAULT_BASE

/**
 * Every failure out of this module, without exception — a refusal the server named, a
 * network that did not answer, a body that did not parse. Components catch one type and
 * show `message`; anything that wants to branch reads `code`.
 */
export class ServerError extends Error {
  /** The server's own code (`box_invalid`, `store_busy`, `card_not_found`, …), or one of
   *  the two this client invents when there is no server answer to quote: `unreachable`
   *  and `bad_response`. Codes are stable strings and are worth branching on; messages are
   *  worth showing. */
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
 * Known hazard, recorded rather than worked around: undo deletes a photo and releases its
 * index, so the next capture reuses this exact URL for different bytes. The server sends no
 * validators, so if a browser ever does hold one of these, the fix is a cache header on
 * the server — not a cache-busting query parameter minted here, which would have to be
 * threaded through every caller and would defeat caching for the pull preview too.
 *
 * ONE EXCEPTION STANDS, AND IT IS NOT THIS FUNCTION'S: after `reshootPhoto` below succeeds,
 * the screen that sent the new bytes appends a nonce to its own `<img>`'s src. That is a
 * different case from the one this paragraph rejects — not a nonce minted here for every
 * caller on every load, but one screen, at the one moment it KNOWS the bytes behind the
 * stable URL changed, refusing to show the photograph it just replaced. PullPreview.tsx
 * argues it where it happens; the general repair stays a response header on the server.
 */
export function photoUrl(box: number, index: number): string {
  return `${base}/photo/${box}/${index}`
}

/**
 * The position label the server rendered, or null when it sent none.
 *
 * `pipeline/join.py:Position.label` composes `Box 3 · Section 2 · Card 17` at 25 cards per
 * section (D10) and `do_inventory` decorates every row it can with the result. The rule
 * types.ts states on that field is that the app displays this string and never composes a
 * second one — a client-side renderer is a copy of D10's divider size that nothing keeps in
 * step with the pipeline's.
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

/**
 * D30's sentence, or null when there is nothing true to say — never a guess.
 *
 * "between Mantine and Thievul · 2 slots in this section are empty". `Card 17` is the
 * seventeenth SLOT, not the seventeenth card you can count, and once a section has permanent
 * gaps (every sale and retirement makes one — D10) the two stop being the same number. The
 * neighbours make the label countable by hand again without anyone learning that rule; the
 * gap count says why a hand-count came out short.
 *
 * ONE COMPOSER, BESIDE `positionLabel` AND FOR ITS REASON: two screens draw this sentence
 * (the pull preview's detail panel and `CardLocations`' copy rows), and two compositions of
 * one wire fact are the drift this module's one-owner rule exists to prevent. It lives here
 * rather than in either screen because the third screen is predictable, and the threshold
 * `describeFailure` was held to was met by the second copy never being written.
 *
 * WHAT IT REFUSES TO SAY, in order: nothing for a pooled card (no slot, no neighbours);
 * nothing when the server sent no decoration (an older server) or nulled it (a record in the
 * store whose position will not read — the same event that nulls the denominator, and a
 * sentence naming a possibly-wrong neighbour would send a hand to the wrong slot, the one
 * thing a position claim may never do); no gap phrase at zero, because a countable section
 * needs no explaining and the sentence is meant to be quiet. A neighbour nothing has
 * identified degrades to its index — `#41`, a slot a hand can count to — never to a blank.
 *
 * At the box's ends there is one neighbour, and the sentence says which side it is on
 * (`after Mantine` / `before Thievul`) rather than pretending a between. The one card whose
 * box holds nothing else says nothing at all — a sentence with no neighbours and no gaps has
 * no content, and null lets the screen render nothing rather than chrome.
 */
export function placeSentence(place: Place | undefined): string | null {
  if (place === undefined || place.located === false) return null

  const said: string[] = []
  const name = (side: PlaceNeighbor): string => side.name ?? `#${side.index}`

  const neighbors = place.neighbors
  if (neighbors !== undefined && neighbors !== null) {
    const { prev, next } = neighbors
    if (prev !== null && next !== null) said.push(`between ${name(prev)} and ${name(next)}`)
    else if (prev !== null) said.push(`after ${name(prev)}`)
    else if (next !== null) said.push(`before ${name(next)}`)
  }

  const gaps = place.section_gaps
  if (typeof gaps === 'number' && gaps > 0) {
    said.push(
      gaps === 1 ? '1 slot in this section is empty' : `${gaps} slots in this section are empty`,
    )
  }

  return said.length === 0 ? null : said.join(' · ')
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

async function request(path: string, init?: RequestInit): Promise<unknown> {
  const url = `${base}${path}`

  let response: Response
  try {
    response = await fetch(url, init)
  } catch {
    /* INVENTED MESSAGE #1. `fetch` rejects without detail for a dead server, a wrong
     * address and a CORS refusal alike — the browser withholds which on purpose — so this
     * names the likeliest cause and the command that fixes it. Worth knowing while step 7a
     * is being built: a preflight refusal reads exactly like this, so a new method that
     * the server's `Access-Control-Allow-Methods` does not list will present as the server
     * being down. */
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
    note?: string | null
  },
): Promise<CardSummary> {
  const payload: Record<string, string | readonly string[] | null> = {}
  if ('setHint' in fields) payload.set_hint = fields.setHint ?? null
  if ('variant' in fields) payload.variant = fields.variant ?? null
  if ('game' in fields && fields.game !== undefined) payload.game = fields.game
  if ('rarityClaim' in fields) payload.rarity_claim = fields.rarityClaim ?? null
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
  patch: { name?: string; sections?: number[]; state?: BoxState },
): Promise<BoxRecord> {
  /* Built key by key rather than spread, so an `undefined` cannot reach `JSON.stringify` and
   * be dropped there instead. Both routes end at the same place today; the difference is that
   * this one is readable — a reader can see that omitted means untouched without knowing what
   * `JSON.stringify` does with an undefined value. */
  const payload: Record<string, string | number[]> = {}
  if (patch.name !== undefined) payload.name = patch.name
  if (patch.sections !== undefined) payload.sections = patch.sections
  if (patch.state !== undefined) payload.state = patch.state

  return (await request(`/boxes/${box}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
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
    note?: string | null
  },
  indices?: number[],
): Promise<BoxClaimResult> {
  const payload: Record<string, string | readonly string[] | number[] | null> = {}
  if ('setHint' in fields) payload.set_hint = fields.setHint ?? null
  if ('variant' in fields) payload.variant = fields.variant ?? null
  if ('game' in fields && fields.game !== undefined) payload.game = fields.game
  if ('rarityClaim' in fields) payload.rarity_claim = fields.rarityClaim ?? null
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
 * Delete a whole box — records, photos, sidecars, queue entries, cache, registry entry
 * (D10 ruling 3).
 *
 * THE MOST DESTRUCTIVE ACTION IN THE PRODUCT, and the one place `docs/DESIGN.md`'s
 * "genuinely destructive actions may still gate" clause is meant to bite. There is no undo:
 * unlike capture-undo, the cards are not in your hand.
 *
 * It refuses `box_not_empty_of_commitments` while the box holds anything sold, retired or
 * listing-held, naming up to eight of them. That refusal is the guard rail — those records
 * are history and commitments, not clutter — so a screen should show what it says rather
 * than reducing it to "cannot delete".
 *
 * The result is a per-kind receipt and should be drawn as one. `directory_removed: false`
 * is not a failure; see `BoxDeleteResult`.
 */
export async function deleteBox(box: number): Promise<BoxDeleteResult> {
  return (await request(`/boxes/${box}`, { method: 'DELETE' })) as BoxDeleteResult
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
export async function preflightRun(cart: readonly RunLeg[]): Promise<RunPreflight> {
  return (await request('/pipeline/preflight', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scopes: cart.map(onTheWire) }),
  })) as RunPreflight
}

/** One cart row in the shape the route reads. Named rather than inlined because BOTH
 *  functions below send it and the money one must not be able to send a different shape from
 *  the one that was quoted — a preflight and a confirm describing different sends is the
 *  exact failure the two-step gate exists to prevent. */
function onTheWire(leg: RunLeg): Record<string, unknown> {
  return {
    box: leg.box,
    // Absent rather than empty, because those mean different things to the route: absent is
    // the whole box and `[]` is refused outright rather than read as one.
    indices: leg.indices !== undefined && leg.indices.length > 0 ? leg.indices : undefined,
    crop: leg.crop,
    max_edge: leg.maxEdge,
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
export async function cropPreview(input: {
  box: number
  indices?: number[]
  crop?: boolean
  maxEdge?: number
  offset?: number
}): Promise<CropPreview> {
  return (await request('/pipeline/crop-preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      box: input.box,
      indices: input.indices,
      crop: input.crop,
      max_edge: input.maxEdge,
      offset: input.offset,
    }),
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
 * Refusals worth branching on: `run_already_live` (a live run is already reading these
 * cards — two batches over one box is two invoices), and every scope refusal the preflight
 * would have shown first.
 */
export async function startRun(cart: readonly RunLeg[]): Promise<RunStarted> {
  return (await request('/pipeline/identify', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ confirm: true, scopes: cart.map(onTheWire) }),
  })) as RunStarted
}

/**
 * The per-SKU pricing table for one run, with this run's answers and the last run's
 * sub-threshold choice. FREE and read-only: it creates nothing and prices nothing.
 *
 * TWO FILES IN ONE CALL, WHICH IS THE WHOLE REASON THIS IS A ROUTE. `pricing.json` and
 * `decisions.json` are both downloadable through `GET .../file` already, so a screen could
 * fetch them separately and need no server change at all — but two fetches can straddle a
 * re-join, and a table describing one join beside answers written against another is a
 * screen quietly pricing the wrong set of cards.
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
 */
export async function runStep(
  name: string,
  step: 'join' | 'emit' | 'reconcile',
  options: {
    exports?: CsvUpload[]
    stagedExport?: CsvUpload
    rule?: string
    basis?: 'market' | 'low'
    reviewBelowConfidence?: 'none' | 'low' | 'medium'
    dryRun?: boolean
    bypass?: boolean
  } = {},
): Promise<RunStepResult> {
  return (await request(`/pipeline/runs/${encodeURIComponent(name)}/${step}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      exports: options.exports,
      staged_export: options.stagedExport,
      rule: options.rule,
      basis: options.basis,
      review_below_confidence: options.reviewBelowConfidence,
      dry_run: options.dryRun,
      bypass: options.bypass,
    }),
  })) as RunStepResult
}

/**
 * Where a run artefact can be downloaded. The import CSVs, the report, `decisions.json`.
 *
 * A URL rather than a fetch, because the browser's own download is what the operator wants
 * — this is the file that goes into TCGplayer's Import to Staged, and a string in a text
 * area is not that. `docs/GATES.md` names the gap this closes: emit's import files existed
 * only as filenames in terminal output the owner never saw.
 */
export function runFileUrl(name: string, file: string): string {
  return `${base}/pipeline/runs/${encodeURIComponent(name)}/file?name=${encodeURIComponent(file)}`
}

/**
 * D9's sub-threshold answer, which gates `emit` and nothing else.
 *
 * Replaces the whole document, because it is one file the operator is editing and a merge
 * would need this route to understand a schema it deliberately does not own — `emit` owns
 * what a disposition MEANS and refuses on it. Read the current file through `runFileUrl`
 * first; that is the same read-modify-write the run report tells a terminal user to do.
 */
export async function putDecisions(
  name: string,
  decisions: Record<string, unknown>,
): Promise<{ ok: boolean; run: string; written: string }> {
  return (await request(`/pipeline/runs/${encodeURIComponent(name)}/decisions`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decisions }),
  })) as { ok: boolean; run: string; written: string }
}
