import type {
  CardSummary,
  Finish,
  Inventory,
  QueueSnapshot,
  ReviewAnswer,
  SaleResult,
  ServerStatus,
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

/* Vite substitutes this at build time. The default is the rig's own Mac; the variable
 * exists so the Fulfiller's device can be pointed at that Mac by address later, which is
 * the one thing the capture-app spec leaves open (section 11). */
const DEFAULT_BASE = 'http://localhost:8000'
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
  setHint?: string
  variant?: Finish
  captureId: string
}): Promise<CardSummary> {
  const payload: Record<string, string | number> = {
    box: input.box,
    image: input.imageBase64,
    capture_id: input.captureId,
  }

  /* Omitted rather than sent empty, matching `sidecar_payload`'s rule on the other side:
   * the file stays a record of claims the operator actually made (D3 rung 1). The server
   * treats absent and null alike, so this costs nothing and keeps the two in step. */
  const hint = input.setHint?.trim()
  if (hint) payload.set_hint = hint
  if (input.variant) payload.variant = input.variant

  /* 201 on a new card, 200 on a replay. Neither is inspected: `created` in the body says
   * the same thing in the shape the screen already reads. */
  return (await request('/capture', {
    method: 'POST',
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
 */
export async function answerReview(answer: ReviewAnswer): Promise<{ answered: string }> {
  const { box, index, sku, condition } = answer
  /* Named for what it answered, the same subset `undoCapture` takes of a much larger body:
   * the route also reports which queues it cleared and the whole card record, and no screen
   * reads either. `server/capture_server.py:do_review_answer` holds the full shape. */
  return (await request(`/review/${box}/${index}/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sku, condition }),
  })) as { answered: string }
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
