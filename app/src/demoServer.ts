/**
 * The capture server, frozen — what `request()` talks to when this is a published demo.
 *
 * WHY THIS MODULE IS SMALL AND WHY IT COULD BE. `app/src/server.ts` makes exactly ONE
 * `fetch`, inside `request()`, and all of its client functions funnel through it. So the
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
 * READS ARE RECORDED. SOME ARE RE-SLICED. WRITES ARE REAL, WITHIN REASON.
 *
 * A read is answered from `scripts/demo-record.py`'s recording, looked up under one canonical
 * spelling of its path (`canonical`), so a query the screen builds in a different order than
 * the recorder did still finds its answer. Four reads take a set the screen chooses — copies
 * of some SKUs, picks for some orders, today's price of some SKUs, a page of a value band —
 * and each is RE-SLICED out of recordings made one member at a time, never invented: the
 * routes answer a subset exactly as they answer the whole (their own docstrings say so). A
 * search is answered by the kit's own one matcher over the recorded search groups (see
 * `search`). A walk plan does not merge — it is a solver over the whole ticked set — so every
 * set a person can tick was recorded on its own.
 *
 * A demo where every button is inert argues against the product it is demonstrating: the
 * whole claim here is that one press writes, advances and comes back with a receipt. So the
 * presses that CARRY that claim are implemented against a mutable copy of the recording —
 * the sale, the retirement, the review answer, the stand-down, each with its undo; the price,
 * the hold, the rename, the divider. Press them and the store changes underneath, exactly as
 * the counters, the queues and the box walk say it does.
 *
 * WHAT IS REFUSED, AND WHY IT IS REFUSED OUT LOUD. Identification spends money at a paid
 * API. The export fetch, the live reconcile and the order sync need a logged-in TCGplayer
 * session. Capture needs the camera and a disk to write a photograph to. None of those can
 * exist in a published page, so each answers with a `ServerError` naming the reason rather
 * than failing silently — a refusal a screen already knows how to draw, and one that tells
 * the viewer something true about the product instead of looking broken.
 *
 * IT DOES NOT RE-IMPLEMENT THE SERVER, and the line is deliberate. `server/capture_server.py`
 * is over thirteen thousand lines and a second copy of its rules in TypeScript would be a
 * copy that drifts — the exact defect `CLAUDE.md` refuses everywhere else. What is here
 * instead is a patch per write: the documents a press would have changed, changed. Anything
 * subtler than that is a refusal, not a guess. `docs/specs/demo.md` §8 lists what a press does
 * NOT reach.
 */

// `#demo-bundle` is the recording when one exists and a type-only stub when it does not.
// See src/demoBundle.stub.ts: the recording is generated and gitignored, so a static path
// here made `tsc` — and therefore `make check` — depend on a build artifact nothing makes.
import bundle from '#demo-bundle'
import { filterByQuery } from './kit/match'
import { ServerError } from './server'

type Recorded = { status: number; body: unknown }
type Dict = Record<string, unknown>

// ------------------------------------------------------------------------- canonical keys

/**
 * One spelling of a recorded key, whichever side composed it.
 *
 * A GET is its path plus its query pairs SORTED, re-encoded by `URLSearchParams`. The
 * recorder builds `/boxes?game=riftbound&set=Origins` with Python's `urlencode`; the screen
 * builds the same filter with `URLSearchParams` in whatever order its object keys happen to
 * be — and the two encoders even disagree on which characters to escape. Sorting and
 * re-encoding BOTH sides is what makes the lookup exact.
 *
 * A POST read is `POST <path> <body>`, the body re-serialized with its keys sorted — the
 * string `demo-record.py:post_key` writes, re-derived here rather than trusted byte for byte.
 */
export function canonical(key: string): string {
  if (key.startsWith('POST ')) {
    const rest = key.slice(5)
    const space = rest.indexOf(' ')
    if (space < 0) return key
    try {
      return postKey(rest.slice(0, space), JSON.parse(rest.slice(space + 1)) as unknown)
    } catch {
      return key
    }
  }
  const mark = key.indexOf('?')
  if (mark < 0) return key
  const pairs = [...new URLSearchParams(key.slice(mark + 1)).entries()].sort((a, b) =>
    a[0] === b[0] ? (a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0) : a[0] < b[0] ? -1 : 1,
  )
  const query = new URLSearchParams(pairs).toString()
  return query === '' ? key.slice(0, mark) : `${key.slice(0, mark)}?${query}`
}

function sortedJson(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortedJson)
  if (value !== null && typeof value === 'object') {
    const out: Dict = {}
    for (const name of Object.keys(value as Dict).sort()) out[name] = sortedJson((value as Dict)[name])
    return out
  }
  return value
}

/** The recorded key of a POST read: the verb, the path and the body with its keys sorted. */
export function postKey(path: string, body: unknown): string {
  return `POST ${path} ${JSON.stringify(sortedJson(body))}`
}

/* The recording, as a MUTABLE map under canonical keys. Cloned on load so a write patches
 * this session's copy and a reload starts the demo over — which is the behaviour somebody
 * clicking through a shared link wants, and the reason no attempt is made to persist it. */
const responses: Record<string, Recorded> = {}
for (const [key, entry] of Object.entries(
  structuredClone(bundle.responses as Record<string, Recorded>),
)) {
  responses[canonical(key)] = entry
}

/** The wire contract this recording was made against. Surfaced for the staleness check. */
export const WIRE = String((bundle as { wire?: unknown }).wire ?? '')

// ---------------------------------------------------------------------------- documents

function doc(path: string): Dict | null {
  const entry = responses[canonical(path)]
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
export const NOT_IN_DEMO = 'Not in this demo.'

/** A read this recording does not hold. Named as such rather than dressed up as an empty
 *  result: an empty list is an answer, and answering a question this bundle cannot answer with
 *  one is how a demo tells a confident lie. */
function notRecorded(): never {
  refuse('demo_not_recorded', NOT_IN_DEMO, 404)
}

/**
 * The things a published page genuinely cannot do. The third field is WHY, for the reader of
 * this file; the screen is told `NOT_IN_DEMO` and the code, never the reason.
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

// ------------------------------------------------------------------- one card, everywhere

/** States that are not on hand. `_box_row` counts `on_hand` as every card not in one. */
const DEPARTED: ReadonlySet<string> = new Set(['sold', 'retired', 'moved'])

/** Box-row counters a state lives in; `identified` and `captured` live in none but `on_hand`. */
const COUNTER: Readonly<Record<string, string>> = { sold: 'sold', retired: 'retired', moved: 'moved' }

/**
 * A card moved from one state to another: patch EVERY recorded document that holds it.
 *
 * WHY EVERY DOCUMENT AND NOT `/inventory` ALONE. The same card is drawn out of a dozen
 * recordings: the whole-store read, its box's read, Home's recent deck, every search group
 * and every copies answer that lists it, the order walk's copies. Patching only `/inventory`
 * is what left the box walk at "34 on hand" after a sale and Home's box rows at their old
 * counts (FLT-23, DC-08). So two passes:
 *
 *  1. The card itself, wherever it is spelled: a `cards` map keyed by its position, or a copy
 *     object carrying `key === position` and a `state` (a search copy, a walk-plan copy).
 *  2. The counters that count it: each `/boxes` row for its box (`on_hand`, `sold`, `retired`,
 *     `moved`, and its section's `count`), and each search group's `on_hand`.
 *
 * WHAT IS NOT REPLAYED, ON PURPOSE. D58 renumbers the cards after a sale on the next read, and
 * the place labels are composed by the server; this does not recompose them. That matches the
 * owner's "nothing jumps" ruling for a press (a sold row keeps its place until the next load),
 * and the next load of a published demo is a reload, which starts it over.
 */
function moveCard(position: string, patch: Dict): void {
  const before = String(cards()[position]?.state ?? '')
  const after = String(patch.state ?? before)
  const box = position.split('/')[0] ?? ''
  const section = cards()[position]?.section

  const seen = new Set<unknown>()
  const walk = (node: unknown): void => {
    if (node === null || typeof node !== 'object' || seen.has(node)) return
    seen.add(node)
    if (Array.isArray(node)) {
      for (const item of node) walk(item)
      return
    }
    const object = node as Dict
    const held = object.cards
    if (held !== null && typeof held === 'object' && !Array.isArray(held)) {
      const record = (held as Record<string, Dict>)[position]
      if (record !== undefined) Object.assign(record, patch)
    }
    if (object.key === position && 'state' in object) {
      object.state = after
      if ('state_at' in patch) object.state_at = patch.state_at
    }
    for (const value of Object.values(object)) walk(value)
  }
  for (const entry of Object.values(responses)) walk(entry.body)

  if (before === after) return
  const wasOnHand = !DEPARTED.has(before)
  const isOnHand = !DEPARTED.has(after)
  for (const [key, entry] of Object.entries(responses)) {
    if (key === '/boxes' || key.startsWith('/boxes?')) {
      for (const row of ((entry.body as Dict).boxes as Dict[]) ?? []) {
        if (String(row.box) !== box) continue
        bump(row, 'on_hand', (isOnHand ? 1 : 0) - (wasOnHand ? 1 : 0))
        const left = COUNTER[before]
        const joined = COUNTER[after]
        if (left !== undefined) bump(row, left, -1)
        if (joined !== undefined) bump(row, joined, 1)
        for (const span of (row.sections_detail as Dict[]) ?? []) {
          if (span.section === section) bump(span, 'count', (isOnHand ? 1 : 0) - (wasOnHand ? 1 : 0))
        }
      }
    }
    if (key.startsWith('/search?')) {
      for (const group of ((entry.body as Dict).groups as Dict[]) ?? []) {
        const copies = (group.copies as Dict[]) ?? []
        if (!copies.some((copy) => copy.key === position)) continue
        bump(group, 'on_hand', (isOnHand ? 1 : 0) - (wasOnHand ? 1 : 0))
        if (before === 'sold' || after === 'sold') bump(group, 'sold_here', after === 'sold' ? 1 : -1)
      }
    }
  }
  restat()
}

function bump(row: Dict, field: string, by: number): void {
  if (by === 0 || typeof row[field] !== 'number') return
  row[field] = Math.max(0, (row[field] as number) + by)
}

/* What each undoable press put back, keyed by position — what the real server reads out of
 * `history.jsonl` to answer `restores_to`, kept here for this session only. */
const saleOrigins = new Map<string, string>()
const retireOrigins = new Map<string, string>()
const answerOrigins = new Map<string, { card: Dict; entry: Dict | null }>()
const standDowns = new Map<string, Dict>()

// -------------------------------------------------------------------------------- writes

/** `POST /inventory/<box>/<index>/sold` — D57's one press, and `{"undo": true}` reverses it. */
function sold(box: string, index: string, undo: boolean): unknown {
  const position = `${box}/${index}`
  const record = card(box, index)
  if (record === null) refuse('card_not_found', NOT_IN_DEMO, 404)
  const was = String(record.state ?? 'captured')
  const stamp = new Date().toISOString()
  if (undo) {
    const origin = saleOrigins.get(position)
    if (was !== 'sold') refuse('not_sold', NOT_IN_DEMO)
    if (origin === undefined) refuse('sold_origin_unknown', NOT_IN_DEMO)
    saleOrigins.delete(position)
    moveCard(position, { state: origin, state_at: stamp })
    return { position, undone: true, restores_to: null, order_released: null }
  }
  if (was === 'sold') refuse('already_sold', NOT_IN_DEMO)
  if (was === 'retired') refuse('card_retired', NOT_IN_DEMO)
  if (was === 'moved') refuse('card_moved', NOT_IN_DEMO)
  saleOrigins.set(position, was)
  moveCard(position, { state: 'sold', state_at: stamp })
  return { position, undone: false, restores_to: was, order_released: null }
}

/** `POST /inventory/<box>/<index>/retire` — D26's departure, with its reason, both ways. */
function retire(box: string, index: string, body: Dict): unknown {
  const position = `${box}/${index}`
  const record = card(box, index)
  if (record === null) refuse('card_not_found', NOT_IN_DEMO, 404)
  const was = String(record.state ?? 'captured')
  const stamp = new Date().toISOString()
  if (body.undo === true) {
    const origin = retireOrigins.get(position)
    if (was !== 'retired') refuse('not_retired', NOT_IN_DEMO)
    if (origin === undefined) refuse('retired_origin_unknown', NOT_IN_DEMO)
    retireOrigins.delete(position)
    moveCard(position, { state: origin, state_at: stamp, retire_reason: null })
    return { position, undone: true, restores_to: null }
  }
  if (was === 'retired') refuse('already_retired', NOT_IN_DEMO)
  if (was === 'sold') refuse('already_sold', NOT_IN_DEMO)
  retireOrigins.set(position, was)
  moveCard(position, { state: 'retired', state_at: stamp, retire_reason: String(body.reason ?? 'damaged') })
  return { position, undone: false, restores_to: was }
}

/**
 * `POST /review/<box>/<index>/answer` — the answer writes AND advances (D28), and
 * `{"undo": true}` takes it back.
 *
 * Two documents move together: the queue loses the entry, and the card gains what the
 * operator said it is — the candidate row the queue offered under that SKU, so the name and
 * number are the export's, never typed here. A demo that dropped the entry without settling
 * the card would show the queue emptying into nothing.
 */
function answer(box: string, index: string, body: Dict): unknown {
  const position = `${box}/${index}`
  const queues = doc('/queues')
  const review = ((queues?.review as Dict[]) ?? [])
  const record = card(box, index)
  if (body.undo === true) {
    const origin = answerOrigins.get(position)
    if (origin === undefined || record === null) refuse('not_answered', NOT_IN_DEMO)
    answerOrigins.delete(position)
    moveCard(position, { ...origin.card, state_at: new Date().toISOString() })
    if (queues !== null && origin.entry !== null) queues.review = [...review, origin.entry]
    restat()
    return { position, undone: true, restores_to: null }
  }
  const entry = review.find((row) => row.position === position) ?? null
  if (entry === null) refuse('not_in_queue', NOT_IN_DEMO)
  const sku = String(body.sku ?? '')
  const chosen = ((entry.candidates as Dict[]) ?? []).find((row) => String(row.sku) === sku)
  if (chosen === undefined) refuse('not_a_candidate', NOT_IN_DEMO)
  if (queues !== null) queues.review = review.filter((row) => row.position !== position)
  if (record !== null) {
    const prior: Dict = {}
    for (const field of ['state', 'sku', 'name', 'number', 'condition', 'confidence', 'rarity']) {
      prior[field] = record[field] ?? null
    }
    answerOrigins.set(position, { card: prior, entry })
    moveCard(position, {
      sku,
      name: chosen.name ?? null,
      number: chosen.number ?? null,
      condition: body.condition ?? chosen.condition ?? null,
      rarity: chosen.rarity ?? null,
      confidence: 'high',
      state: 'identified',
      state_at: new Date().toISOString(),
    })
    return {
      position,
      undone: false,
      restores_to: { sku: (prior.sku as string | null) ?? null, condition: (prior.condition as string | null) ?? null },
    }
  }
  restat()
  return { position, undone: false, restores_to: null }
}

/** `POST /review/<box>/<index>/stand-down` — D37: closed without answering, card untouched,
 *  and `{"undo": true}` puts the question back. */
function standDown(box: string, index: string, body: Dict): unknown {
  const position = `${box}/${index}`
  const queues = doc('/queues')
  if (queues === null) notRecorded()
  const review = (queues.review as Dict[]) ?? []
  const parked = (queues.parked as Dict[]) ?? []
  if (body.undo === true) {
    const entry = standDowns.get(position)
    if (entry === undefined) refuse('not_stood_down', NOT_IN_DEMO)
    standDowns.delete(position)
    queues.parked = parked.filter((row) => row !== entry)
    queues.review = [...review, entry]
    restat()
    return { position, undone: true, reason: null }
  }
  const entry = review.find((row) => row.position === position)
  if (entry === undefined) refuse('not_in_queue', NOT_IN_DEMO)
  const queueReason = entry.reason
  queues.review = review.filter((row) => row.position !== position)
  queues.parked = [...parked, entry]
  standDowns.set(position, entry)
  restat()
  return {
    position,
    undone: false,
    reason: body.reason ?? 'stood_down',
    queue_reason: queueReason,
    reversible: true,
  }
}

/** `PUT /pricing` — D86's one answer file for the whole store, prices and holds alike. */
function writePricing(body: Dict): unknown {
  const pricing = doc('/pricing')
  if (pricing === null) notRecorded()
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

/** `PUT /boxes/<box>` — the rename (D20). Every document that names a box moves. */
function renameBox(box: string, body: Dict): unknown {
  const inv = inventory()
  const boxes = (inv?.boxes as Record<string, Dict>) ?? {}
  const record = boxes[box]
  if (record === undefined) refuse('box_unknown', NOT_IN_DEMO, 404)
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
  for (const [key, entry] of Object.entries(responses)) {
    if (key !== '/boxes' && !key.startsWith('/boxes?')) continue
    for (const row of ((entry.body as Dict).boxes as Dict[]) ?? []) {
      if (String(row.box) === box) row.name = name
    }
  }
  return { ok: true, box: Number(box), name }
}

/** `POST /boxes/<box>/sections` — a divider goes in where the real one just did (D10). */
function openSection(box: string): unknown {
  const inv = inventory()
  const record = ((inv?.boxes as Record<string, Dict>) ?? {})[box]
  if (record === undefined) refuse('box_unknown', NOT_IN_DEMO, 404)
  const at = Object.values(cards()).filter((c) => String(c.box) === box).length + 1
  const sections = ((record.sections as number[]) ?? []).slice()
  if (!sections.includes(at)) sections.push(at)
  sections.sort((a, b) => a - b)
  record.sections = sections
  return { ok: true, box: Number(box), sections, at }
}

// ------------------------------------------------------------------------ re-sliced reads

/**
 * Every recorded trend reading, indexed by SKU.
 *
 * WHY AN INDEX AND NOT A URL MATCH. `Pricing.tsx` asks for trends in CHUNKS of
 * `TREND_CHUNK = 8`, in whatever order the rows are sorted on screen, while the recorder asks
 * once for every SKU in the run. So no chunk request can ever equal a recorded URL.
 * Reproducing the client's chunking in the recorder would be a second copy of a rule that
 * lives in the screen. The data is the same real reading either way; this re-slices it.
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

/**
 * `GET /pipeline/value?band=&box=&after=&limit=` — one page of a band recorded whole.
 *
 * `ValueBands.tsx` asks many page sizes (`min(PAGE, wanted)`), so the recorder asked for each
 * band whole, once per box, and this cuts the page. The cursor is this module's own
 * (`demo:<offset>`) — the screen hands `next` back unread, which is all a cursor promises.
 */
function valuePage(params: URLSearchParams): unknown {
  const band = params.get('band') ?? 'top'
  const box = params.get('box')
  const whole = new URLSearchParams({ band, limit: '5000' })
  if (box !== null && box !== '') whole.set('box', box)
  const recorded = doc(`/pipeline/value?${whole.toString()}`)
  if (recorded === null) notRecorded()
  const rows = (recorded.rows as unknown[]) ?? []
  const after = params.get('after')
  const start = after !== null && after.startsWith('demo:') ? Number(after.slice(5)) || 0 : 0
  const limitText = params.get('limit')
  const limit = limitText === null ? 200 : Math.max(0, Number(limitText) || 0)
  const end = start + limit
  return { ...recorded, rows: rows.slice(start, end), next: end < rows.length ? `demo:${end}` : null }
}

/** `GET /pipeline/price-now?sku=…` for any set of SKUs, merged out of per-SKU recordings. */
function priceNow(skus: string[]): unknown {
  const prices: Dict = {}
  for (const sku of skus) {
    const one = doc(`/pipeline/price-now?sku=${encodeURIComponent(sku)}`)
    if (one === null) notRecorded()
    Object.assign(prices, (one.prices as Dict) ?? {})
  }
  return { prices }
}

/**
 * `GET /search?q=…` for a query nobody recorded, answered by the kit's ONE matcher.
 *
 * The recorder asked `/search` once per SKU the store holds, so between them the recorded
 * answers hold every search group this store can produce. A typed query — `Crowd Favorite`,
 * a number without its zeros — is answered by filtering those groups through
 * `kit/match.ts:filterByQuery`, the rules the owner ruled every search in the app follows
 * (one forgiving matcher). Nothing is invented: every group returned is one the server
 * composed. What is NOT reproduced is the server's ranking; the groups come back in name
 * order, which is the demo's own choice and says so here.
 */
function search(query: string): unknown {
  if (query.trim() === '') notRecorded()
  const groups = new Map<string, Dict>()
  for (const [path, entry] of Object.entries(responses)) {
    if (!path.startsWith('/search?')) continue
    for (const group of ((entry.body as Dict).groups as Dict[]) ?? []) {
      const key = `${String(group.sku)}|${String(group.condition)}`
      if (!groups.has(key)) groups.set(key, group)
    }
  }
  const rows = [...groups.values()].sort((a, b) => {
    const left = String(((a.names as string[]) ?? [])[0] ?? '')
    const right = String(((b.names as string[]) ?? [])[0] ?? '')
    return left.localeCompare(right)
  })
  const matched = filterByQuery(rows, query, (group) => ({
    text: [
      ...((group.names as string[]) ?? []),
      group.set as string | null,
      group.condition as string | null,
    ],
    numbers: [group.number as string | null, group.number_display as string | null],
    skus: [group.sku as string | null],
    boxes: ((group.copies as Dict[]) ?? []).map((copy) => {
      const place = (copy.place as Dict | undefined) ?? {}
      return { box: Number(place.box ?? 0), name: (place.box_name as string | null) ?? null }
    }),
  }))
  return { query, groups: matched }
}

/** `POST /inventory/copies` — every on-hand copy of the named SKUs, merged per SKU. */
function copies(body: Dict): unknown {
  const skus = (body.skus as unknown[]) ?? []
  if (skus.length === 0) refuse('skus_required', NOT_IN_DEMO, 400)
  const out = { cards: {} as Dict, listings: {} as Dict }
  for (const sku of skus) {
    const one = doc(postKey('/inventory/copies', { skus: [String(sku)] }))
    if (one === null) notRecorded()
    Object.assign(out.cards, (one.cards as Dict) ?? {})
    Object.assign(out.listings, (one.listings as Dict) ?? {})
  }
  return out
}

/** `POST /orders/picks` — the named orders' picks, merged per order. A key the ledger does
 *  not hold is SKIPPED, the route's own rule; the recorder asked for every key it holds. */
function picks(body: Dict): unknown {
  const keys = (body.keys as unknown[]) ?? []
  if (keys.length === 0) refuse('keys_required', NOT_IN_DEMO, 400)
  const orders: unknown[] = []
  for (const key of keys) {
    const one = doc(postKey('/orders/picks', { keys: [String(key)] }))
    if (one !== null) orders.push(...((one.orders as unknown[]) ?? []))
  }
  return { orders }
}

/** Every order key the ledger held when the walk plans were recorded. */
function ledgerKeys(): Set<string> {
  const orders = (doc('/orders')?.orders as Dict[]) ?? []
  return new Set(orders.map((order) => String(order.key)))
}

/** `POST /orders/walk-plan` — the recorded plan for exactly this ticked set. Keys the ledger
 *  does not hold are dropped first, as the solver's own `demand` skips them. */
function walkPlan(body: Dict): unknown {
  if (body.cost !== undefined) notRecorded()
  const known = ledgerKeys()
  const keys = [...new Set(((body.keys as unknown[]) ?? []).map(String))].filter((key) => known.has(key)).sort()
  if (keys.length === 0) refuse('keys_required', NOT_IN_DEMO, 400)
  const plan = doc(postKey('/orders/walk-plan', { keys }))
  if (plan === null) notRecorded()
  return plan
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
 * know that, so the pair is pulled out once here rather than asserted at every call site. */
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

/** Every GET: the recording under its canonical key, or one of the re-sliced reads. */
function read(path: string): unknown {
  const entry = responses[canonical(path)]
  if (entry !== undefined) return entry.body

  const mark = path.indexOf('?')
  const route = mark < 0 ? path : path.slice(0, mark)
  const params = new URLSearchParams(mark < 0 ? '' : path.slice(mark + 1))

  const trend = /^\/pipeline\/runs\/([^/]+)\/trends$/.exec(route)
  if (trend !== null) {
    const wanted = params.getAll('sku').filter((s) => s !== '')
    if (wanted.length > 0) return trendsFor(decodeURIComponent(trend[1] ?? ''), wanted)
  }
  if (route === '/pipeline/value') return valuePage(params)
  if (route === '/pipeline/price-now') return priceNow(params.getAll('sku').filter((s) => s !== ''))
  if (route === '/search') return search(params.get('q') ?? '')
  notRecorded()
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

  if (method === 'GET') return read(path)

  for (const [prefix, code] of CANNOT) {
    if (path === prefix || path.startsWith(`${prefix}/`)) refuse(code, NOT_IN_DEMO)
  }

  /* THE WRITE-SHAPED READS. A POST because the list is too long for a query string, and each
   * route opens the store read-only — so the answer is a recording, never a patch. */
  if (method === 'POST') {
    if (path === '/inventory/copies') return copies(body)
    if (path === '/orders/picks') return picks(body)
    if (path === '/orders/walk-plan') return walkPlan(body)
  }

  let match: RegExpExecArray | null
  if ((match = SOLD.exec(path)) !== null) {
    const [box, index] = pair(match)
    return sold(box, index, body.undo === true)
  }
  if ((match = RETIRE.exec(path)) !== null) {
    const [box, index] = pair(match)
    return retire(box, index, body)
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
    notRecorded()
  }

  /* Everything else. Not an error page and not a crash: a named refusal, which every screen
   * in this app already draws as a sentence with the code small beneath it. The pull, the
   * order close and the fill are among these on purpose: each writes the order ledger, whose
   * arithmetic (`_line_answer`) is server logic this module does not copy. */
  refuse('demo_read_only', NOT_IN_DEMO)
}
