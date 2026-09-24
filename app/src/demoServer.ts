/**
 * The capture server, frozen — what `request()` talks to when this is a published demo.
 *
 * WHY THIS MODULE IS SMALL AND WHY IT COULD BE. `app/src/server.ts` makes exactly ONE
 * `fetch`, inside `request()`, and all 84 of its client functions funnel through it. So the
 * entire boundary between this product and its Python server is one function, and standing
 * a recording behind it turns the real app into a static one without mocking anything above
 * it. Every screen, the kit, the shell, the router and the keyboard map are the SAME CODE
 * the owner runs at the desk. Only the wire is frozen.
 *
 * NOT IN THE PRODUCTION BUNDLE. `server.ts` reaches this through a dynamic `import()` inside
 * `if (DEMO)`, and `DEMO` folds to `false` at build time unless `VITE_DEMO=1`. Rollup drops
 * the branch and never emits the chunk, so an ordinary build carries neither this file nor
 * the fixture bundle it imports.
 *
 * READS ARE RECORDED. WRITES ARE REAL, WITHIN REASON.
 *
 * A demo where every button is inert argues against the product it is demonstrating: the
 * whole claim here is that one press writes, advances and comes back with a receipt. So the
 * presses that CARRY that claim are implemented against a mutable copy of the recording —
 * the sale, the review answer, the stand-down, the price, the hold, the rename, the divider.
 * Press them and the store changes underneath, exactly as the counters, the queues and the
 * box walk say it does.
 *
 * WHAT IS REFUSED, AND WHY IT IS REFUSED OUT LOUD. Identification spends money at a paid
 * API. The export fetch, the live reconcile and the order sync need a logged-in TCGplayer
 * session. Capture needs the camera and a disk to write a photograph to. None of those can
 * exist in a published page, so each answers with a `ServerError` naming the reason rather
 * than failing silently — a refusal a screen already knows how to draw, and one that tells
 * the viewer something true about the product instead of looking broken.
 *
 * IT DOES NOT RE-IMPLEMENT THE SERVER, and the line is deliberate. `server/capture_server.py`
 * is ~10,000 lines and a second copy of its rules in TypeScript would be a copy that drifts —
 * the exact defect `CLAUDE.md` refuses everywhere else. What is here instead is a patch per
 * write: the documents a press would have changed, changed. Anything subtler than that is a
 * refusal, not a guess.
 */

// `#demo-bundle` is the recording when one exists and a type-only stub when it does not.
// See src/demoBundle.stub.ts: the recording is generated and gitignored, so a static path
// here made `tsc` — and therefore `make check` — depend on a build artefact nothing makes.
import bundle from '#demo-bundle'
import { ServerError } from './server'

type Recorded = { status: number; body: unknown }

/* The recording, as a MUTABLE map. Cloned on load so a write patches this session's copy and
 * a reload starts the demo over — which is the behaviour somebody clicking through a shared
 * link wants, and the reason no attempt is made to persist any of it. */
const responses: Record<string, Recorded> = structuredClone(
  bundle.responses as Record<string, Recorded>,
)

/** The wire contract this recording was made against. Surfaced for the staleness check. */
export const WIRE = String((bundle as { wire?: unknown }).wire ?? '')

// ---------------------------------------------------------------------------- documents

type Dict = Record<string, unknown>

function doc(path: string): Dict | null {
  const entry = responses[path]
  if (entry === undefined) return null
  return entry.body as Dict
}

function inventory(): Dict | null {
  return doc('/inventory')
}

function cards(): Record<string, Dict> {
  const inv = inventory()
  return (inv?.cards as Record<string, Dict>) ?? {}
}

function card(box: string, index: string): Dict | null {
  return cards()[`${box}/${index}`] ?? null
}

/**
 * `/status`'s state histogram, recomputed from the cards.
 *
 * Recomputed rather than incremented: an increment has to know which state the card left,
 * and every caller that got that wrong would leave a counter that drifts further from the
 * truth with each press. Walking 122 cards costs nothing and cannot drift.
 */
function restat(): void {
  const status = doc('/status')
  if (status === null) return
  const states: Record<string, number> = {}
  for (const record of Object.values(cards())) {
    const state = String(record.state ?? 'captured')
    states[state] = (states[state] ?? 0) + 1
  }
  status.states = states
  status.cards = Object.keys(cards()).length
  const queues = doc('/queues')
  if (queues !== null) {
    status.queues = {
      review: ((queues.review as unknown[]) ?? []).length,
      parked: ((queues.parked as unknown[]) ?? []).length,
    }
  }
}

// ------------------------------------------------------------------------------ refusals

/** A refusal in the server's own envelope, so screens draw it the way they draw a real one. */
function refuse(code: string, message: string, status = 409): never {
  throw new ServerError(code, message, status)
}

/** EVERY DEMO REFUSAL SAYS THIS AND NOTHING ELSE (TXT-46). The longer sentences these replaced
 *  printed a request path with twenty SKUs in it and a repository command to a demo visitor. The
 *  code under it still names which refusal it was, behind the kit's "What the server said". */
const NOT_IN_DEMO = 'Not in this demo.'

/**
 * The things a published page genuinely cannot do. The third field is WHY, for the reader of
 * this file; the screen is told `NOT_IN_DEMO` and the code, never the reason.
 *
 * Keyed by the path prefix that reaches them. Ordered longest-first at the call site so a
 * specific path wins over a general one.
 */
const CANNOT: ReadonlyArray<readonly [string, string, string]> = [
  [
    '/pipeline/identify',
    'demo_costs_money',
    'Identification is a paid Batch API call against Claude, so it is frozen in this demo. ' +
      'The run below was identified for real — its answers, its confidences and its review ' +
      'queue are what came back.',
  ],
  [
    '/pipeline/emit',
    'demo_no_export',
    'Emit writes an import CSV from a TCGplayer export this demo has no live copy of. The ' +
      'pricing table and the copies-out arithmetic beside it are real.',
  ],
  [
    '/pipeline/reconcile-live',
    'demo_no_export',
    'Reconciling against live quantities needs a My Pricing export from a signed-in ' +
      'TCGplayer account, which a published page has no way to fetch.',
  ],
  [
    '/pipeline/live-export',
    'demo_no_session',
    'Fetching the live export needs a signed-in TCGplayer session. Frozen in this demo.',
  ],
  [
    '/orders/fetch',
    'demo_no_session',
    'Fetching orders needs a signed-in TCGplayer session. The orders already in this ' +
      'ledger are what the screen resolves against.',
  ],
  [
    '/capture',
    'demo_no_camera',
    'Capture writes a photograph to disk on the machine at the rig. This demo has no disk ' +
      'behind it — the boxes below hold cards captured earlier.',
  ],
  [
    '/codes/scan',
    'demo_no_camera',
    'Scanning reads QR codes out of photographs on disk. Frozen in this demo.',
  ],
]

// -------------------------------------------------------------------------------- writes

/** `PUT/POST /inventory/<box>/<index>/sold` — D57's one press. */
function sell(box: string, index: string): unknown {
  const record = card(box, index)
  if (record === null) refuse('card_not_found', `No card at ${box}/${index}.`, 404)
  record.state = 'sold'
  record.state_at = new Date().toISOString()
  restat()
  return { ok: true, place: { box: Number(box), index: Number(index) }, state: 'sold' }
}

/** `POST /inventory/<box>/<index>/retire` — D26's departure, with its reason. */
function retire(box: string, index: string, body: Dict): unknown {
  const record = card(box, index)
  if (record === null) refuse('card_not_found', `No card at ${box}/${index}.`, 404)
  record.state = 'retired'
  record.retire_reason = String(body.reason ?? 'damaged')
  record.state_at = new Date().toISOString()
  restat()
  return { ok: true, state: 'retired', reason: record.retire_reason }
}

/** Undo, for both of the above — D28's window, which the screens offer on every write. */
function unretire(box: string, index: string, to: string): unknown {
  const record = card(box, index)
  if (record === null) refuse('card_not_found', `No card at ${box}/${index}.`, 404)
  record.state = to
  record.retire_reason = null
  record.state_at = new Date().toISOString()
  restat()
  return { ok: true, state: to }
}

/**
 * `POST /review/<box>/<index>/answer` — the answer writes AND advances (D28).
 *
 * Two documents move together: the queue loses the entry, and the card gains what the
 * operator said it is. A demo that dropped the entry without settling the card would show
 * the queue emptying into nothing.
 */
function answer(box: string, index: string, body: Dict): unknown {
  const queues = doc('/queues')
  const position = `${box}/${index}`
  if (queues !== null) {
    const review = (queues.review as Dict[]) ?? []
    queues.review = review.filter((entry) => entry.position !== position)
  }
  const record = card(box, index)
  if (record !== null) {
    const chosen = (body.candidate ?? body.answer ?? {}) as Dict
    record.state = 'identified'
    record.state_at = new Date().toISOString()
    if (chosen.sku !== undefined) record.sku = chosen.sku
    if (chosen.name !== undefined) record.name = chosen.name
    if (chosen.number !== undefined) record.number = chosen.number
    if (chosen.condition !== undefined) record.condition = chosen.condition
    record.confidence = 'high'
  }
  restat()
  return { ok: true, position, remaining: ((doc('/queues')?.review as unknown[]) ?? []).length }
}

/** `POST /review/<box>/<index>/stand-down` — D37: closed without answering, card untouched. */
function standDown(box: string, index: string, body: Dict): unknown {
  const queues = doc('/queues')
  const position = `${box}/${index}`
  if (queues !== null) {
    const review = (queues.review as Dict[]) ?? []
    const entry = review.find((row) => row.position === position)
    queues.review = review.filter((row) => row.position !== position)
    if (entry !== undefined) {
      entry.reason = String(body.reason ?? 'stood_down')
      queues.parked = [...((queues.parked as Dict[]) ?? []), entry]
    }
  }
  restat()
  return { ok: true, position, reason: body.reason ?? 'stood_down' }
}

/** `PUT /pricing` — D86's one answer file for the whole store, prices and holds alike. */
function writePricing(body: Dict): unknown {
  const pricing = doc('/pricing')
  if (pricing === null) refuse('no_corpus', 'This demo recorded no pricing corpus.', 404)
  const corpus = (pricing.corpus as Dict) ?? {}
  const answers = (corpus.answers as Dict) ?? {}
  for (const [sku, value] of Object.entries((body.answers as Dict) ?? {})) {
    answers[sku] = value
  }
  corpus.answers = answers
  if (body.rule !== undefined) corpus.rule = body.rule
  if (body.basis !== undefined) corpus.basis = body.basis
  pricing.corpus = corpus
  /* The revision is what `--corpus-revision` compares (D103). Moving it on every write is
   * what makes the guard observable in the demo rather than a paragraph in the docs. */
  pricing.revision = Math.random().toString(16).slice(2, 18)
  return { ok: true, revision: pricing.revision, written: Object.keys((body.answers as Dict) ?? {}).length }
}

/** `PUT /boxes/<box>` — the rename (D20). Two documents name a box; both move. */
function renameBox(box: string, body: Dict): unknown {
  const inv = inventory()
  const boxes = (inv?.boxes as Record<string, Dict>) ?? {}
  const record = boxes[box]
  if (record === undefined) refuse('box_unknown', `No box ${box}.`, 404)
  const name = body.name === null || body.name === undefined ? null : String(body.name)
  const taken = Object.entries(boxes).some(
    ([key, other]) =>
      key !== box &&
      typeof other.name === 'string' &&
      name !== null &&
      other.name.trim().toLowerCase() === name.trim().toLowerCase(),
  )
  /* D20's uniqueness rule, folded and stripped — the one piece of server logic worth
   * carrying, because the refusal it produces is a thing the screen is built to show. */
  if (taken) refuse('name_taken', `Another box is already called “${name}”.`, 409)
  record.name = name
  const list = doc('/boxes')
  if (list !== null) {
    for (const entry of (list.boxes as Dict[]) ?? []) {
      if (String(entry.box) === box) entry.name = name
    }
  }
  return { ok: true, box: Number(box), name }
}

/** `POST /boxes/<box>/sections` — a divider goes in where the real one just did (D10). */
function openSection(box: string): unknown {
  const inv = inventory()
  const record = ((inv?.boxes as Record<string, Dict>) ?? {})[box]
  if (record === undefined) refuse('box_unknown', `No box ${box}.`, 404)
  const at = Object.values(cards()).filter((c) => String(c.box) === box).length + 1
  const sections = ((record.sections as number[]) ?? []).slice()
  if (!sections.includes(at)) sections.push(at)
  sections.sort((a, b) => a - b)
  record.sections = sections
  return { ok: true, box: Number(box), sections, at }
}

// -------------------------------------------------------------------------------- trends

/**
 * Every recorded trend reading, indexed by SKU.
 *
 * WHY AN INDEX AND NOT A URL MATCH. `Pricing.tsx` asks for trends in CHUNKS of
 * `TREND_CHUNK = 8` — `?sku=a&sku=b&…` eight at a time, in whatever order the rows are sorted
 * on screen — while the recorder asks once for every SKU in the run. So no chunk request can
 * ever equal a recorded URL, and matching on the URL meant "Load trends" answered
 * `demo_not_recorded` on the first chunk, every time. Reproducing the client's chunking and
 * its sort order in the recorder would be a second copy of a rule that lives in the screen,
 * and it would break the next time a filter changed which rows are on screen.
 *
 * The data is the same real reading either way; this just re-slices it to whatever was asked
 * for. Built once, lazily, from every recorded `/trends?` response.
 */
let trendIndex: Record<string, unknown> | null = null

function trendsBySku(): Record<string, unknown> {
  if (trendIndex !== null) return trendIndex
  const index: Record<string, unknown> = {}
  for (const [path, entry] of Object.entries(responses)) {
    if (!path.includes('/trends?')) continue
    const body = entry.body as Dict
    for (const [sku, reading] of Object.entries((body.skus as Dict) ?? {})) {
      index[sku] = reading
    }
  }
  trendIndex = index
  return index
}

/** `GET /pipeline/runs/<run>/trends?sku=…` for any subset, out of the index above. */
function trendsFor(run: string, wanted: string[]): unknown {
  const index = trendsBySku()
  const skus: Record<string, unknown> = {}
  let refused = 0
  for (const sku of wanted) {
    const reading = index[sku]
    if (reading === undefined) {
      /* A SKU THE RECORDING DOES NOT HOLD IS REFUSED, NOT INVENTED. The screen draws a
       * refused row as "no reading", which is true; a fabricated series would be a lie
       * about a real card's price. */
      refused += 1
      continue
    }
    skus[sku] = reading
  }
  return { run, asked: wanted.length, skipped: 0, refused, skus }
}

// ------------------------------------------------------------------------------ dispatch

const SOLD = /^\/inventory\/(\d+)\/(\d+)\/sold$/
const RETIRE = /^\/inventory\/(\d+)\/(\d+)\/retire$/
const REVIEW_ANSWER = /^\/review\/(\d+)\/(\d+)\/answer$/
const REVIEW_STAND_DOWN = /^\/review\/(\d+)\/(\d+)\/stand-down$/
const BOX = /^\/boxes\/(\d+)$/
const BOX_SECTIONS = /^\/boxes\/(\d+)\/sections$/

/* `noUncheckedIndexedAccess` types a capture group as `string | undefined`, which is right:
 * a group can be optional. These patterns have no optional groups, but the compiler cannot
 * know that, so the pair is pulled out once here rather than asserted at eight call sites. */
function pair(match: RegExpExecArray): readonly [string, string] {
  return [match[1] ?? '', match[2] ?? '']
}

function parseBody(init?: RequestInit): Dict {
  if (init?.body === undefined || init.body === null) return {}
  try {
    return JSON.parse(String(init.body)) as Dict
  } catch {
    return {}
  }
}

/**
 * One request against the frozen store.
 *
 * Deliberately async and deliberately not instant: `await Promise.resolve()` alone would
 * resolve inside the same tick and every screen's loading state would be dead code a viewer
 * never sees. A few milliseconds is enough for the skeletons, the busy rings and the
 * optimistic updates to be the thing they are on real hardware.
 */
export async function demoRequest(path: string, init?: RequestInit): Promise<unknown> {
  await new Promise((resume) => setTimeout(resume, 45 + Math.random() * 90))

  const method = (init?.method ?? 'GET').toUpperCase()
  const body = parseBody(init)

  if (method === 'GET') {
    const entry = responses[path]
    if (entry !== undefined) return entry.body

    /* The one GET answered by computation rather than by lookup — see `trendsBySku`. */
    const trend = /^\/pipeline\/runs\/([^/]+)\/trends\?(.*)$/.exec(path)
    if (trend !== null) {
      const wanted = new URLSearchParams(trend[2] ?? '').getAll('sku').filter((s) => s !== '')
      if (wanted.length > 0) {
        return trendsFor(decodeURIComponent(trend[1] ?? ''), wanted)
      }
    }
    /* A GET the recording does not hold. Named as such rather than dressed up as an empty
     * result: an empty list is an answer, and answering a question this bundle cannot
     * answer with one is how a demo tells a confident lie. */
    refuse('demo_not_recorded', NOT_IN_DEMO, 404)
  }

  for (const [prefix, code] of CANNOT) {
    if (path === prefix || path.startsWith(`${prefix}/`)) refuse(code, NOT_IN_DEMO)
  }

  let match: RegExpExecArray | null
  if ((match = SOLD.exec(path)) !== null) {
    const [box, index] = pair(match)
    return method === 'DELETE' ? unretire(box, index, 'identified') : sell(box, index)
  }
  if ((match = RETIRE.exec(path)) !== null) {
    const [box, index] = pair(match)
    return method === 'DELETE' ? unretire(box, index, 'identified') : retire(box, index, body)
  }
  if ((match = REVIEW_ANSWER.exec(path)) !== null) {
    const [box, index] = pair(match)
    return answer(box, index, body)
  }
  if ((match = REVIEW_STAND_DOWN.exec(path)) !== null) {
    const [box, index] = pair(match)
    return standDown(box, index, body)
  }
  if ((match = BOX_SECTIONS.exec(path)) !== null) return openSection(match[1] ?? '')
  if ((match = BOX.exec(path)) !== null && method === 'PUT') {
    return renameBox(match[1] ?? '', body)
  }
  if (path === '/pricing' && (method === 'PUT' || method === 'POST')) return writePricing(body)

  /* THE ONE RECORDED WRITE, and it is recorded because there is nothing else to read.
   * `server/shipping_routes.py` holds a read export in memory and keeps no list of batches,
   * so `GET /shipping/batches` does not exist — the only way to see the lanes is the answer
   * to the request that made them. Replaying it for any upload is honest here: reading an
   * export is a pure function of the file, and the whole store behind this page is frozen.
   * The recorded batch is `fixtures/orders-shipping.csv`, which is anonymised at rest. */
  if (path === '/shipping/batches' && method === 'POST') {
    const made = responses['POST /shipping/batches']
    if (made !== undefined) return made.body
    refuse('demo_not_recorded', NOT_IN_DEMO, 404)
  }

  /* Everything else. Not an error page and not a crash: a named refusal, which every screen
   * in this app already draws as a sentence with the code small beneath it. */
  /* What does write for real here: selling a card, answering the review queue, pricing a card,
   * holding one back, renaming a box and dropping a divider. */
  refuse('demo_read_only', NOT_IN_DEMO)
}
