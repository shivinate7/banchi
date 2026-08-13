import type { CardSummary, Finish, Inventory, ServerStatus } from './types'

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
