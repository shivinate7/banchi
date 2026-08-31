/* THE PII BOUNDARY. THIS IS THE ONLY PLACE IN THE APP THAT CONSTRUCTS AN INGEST BODY, AND
 * ITS WHOLE JOB IS TO KEEP THE BUYER OUT OF IT.
 *
 * An order as a marketplace hands it over carries a person: a name, a shipping address, an
 * email, a phone number. This repo needs none of them. What it needs is a SKU and a count —
 * `pipeline/orders.py` says so in its own first line, and everything it computes is a
 * position, which is a fact about a drawer rather than about a customer. So the paste is
 * PROJECTED rather than validated: a fixed list of keys is copied across and everything
 * else is left behind, which is the only shape that stays safe when the feed grows a field
 * nobody here has read.
 *
 * A WHITELIST AND NOT A BLACKLIST, and the difference is the whole design. A blacklist of
 * `buyer`, `email`, `address` is correct until TCGplayer adds `recipient` or a screenshot
 * of a console shows `shippingAddress` in camelCase, and then it is silently wrong — the
 * body still posts, the server still answers, and the personal data is on the wire with
 * nothing reporting it. The projection below cannot fail that way: a key nobody named is a
 * key nobody sends.
 *
 * WHAT IS DROPPED IS NAMED, and that is what makes this honest rather than merely quiet.
 * Every top-level key the projection refuses is collected into `dropped`, so the screen can
 * say "these are not being sent" before the press. A silent strip is indistinguishable on
 * screen from a feed that never carried the field, and the owner would have no way to tell
 * a working PII boundary from a broken one.
 *
 * WHAT IS NOT NAMED, said plainly so nobody reads more into `dropped` than it holds: keys
 * inside a LINE are dropped without being listed, because a feed with an odd extra field on
 * every one of forty lines would flood the list with one word repeated. They are dropped
 * exactly as firmly — the line projection is the same whitelist — and a screen that wanted
 * to name them would have to walk the lines itself.
 *
 * IT NEVER THROWS. A paste is a thing a human got wrong, not an exceptional condition:
 * `JSON.parse` is the one call here that can raise and it is wrapped, so every outcome is a
 * `PasteReading` the screen renders. A screen that has to wrap this in a `try` would end up
 * with two failure paths drawn two ways.
 *
 * NOTHING IS REMEMBERED. No browser store of any kind: a paste that has not been sent is a
 * buyer's order sitting in a browser, and D13's one truth lives on the Mac. The text lives
 * in React state for as long as the screen is open and nowhere else.
 */

import type { OrderIngestOrder, OrderIngestLine } from './types'

/** The reading of one paste: either a projection the screen may send, or a sentence saying
 *  what to fix. Deliberately not `orders | null` — "it did not work" with no reason is what
 *  sends a person back to a console to guess. */
export type PasteReading =
  | { ok: true; orders: OrderIngestOrder[]; dropped: string[] }
  | { ok: false; problem: string }

/** The source stamped on an order that does not name one.
 *
 *  DEFAULTED HERE AND SHOWN, NEVER APPLIED INVISIBLY ON THE SERVER. The projection carries
 *  the default out with it so the screen draws `TCGplayer` beside every order before the
 *  press — a default the operator can see is a default they can catch. A server-side one is
 *  a fact about the ledger that nothing on screen ever said. */
export const DEFAULT_ORDER_SOURCE = 'TCGplayer'

/* THE ORDER-LEVEL WHITELIST. `source`, `number`, `placed_at` and `status` are what the
 * ledger is keyed and sorted by; `lines` is the work. Nothing else crosses. `placed_at` in
 * particular is kept because `pipeline/orders.py:Order` sorts the one-pass resolution by it
 * and records that an order with no timestamp sorts LAST rather than first — dropping it
 * here would silently make every paste timestamp-less and hand stock to whichever order the
 * paste happened to list first. */
const ORDER_KEEP: ReadonlySet<string> = new Set([
  'source',
  'number',
  'placed_at',
  'status',
  'lines',
])

/* The LINE-level whitelist is not a set, because the line projection reads its nine fields
 * by name below: `sku` and `quantity` decide everything, and the other seven are what the
 * feed said, kept verbatim so a screen can show the buyer's own words beside the position.
 * `pipeline/orders.py:OrderLine` is the same nine and none of them is ever a join key. */

/** A plain JSON object — not null, not an array. Both exclusions matter: `typeof null` is
 *  `'object'`, and an array would let `Object.keys` return `'0'`, `'1'`, `'2'` as dropped
 *  key names, which is nonsense on screen. */
function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** A required identifier off the feed: a non-blank string, or a finite number written out.
 *
 *  The number case is real — an order number and a SKU both arrive as ints from a JSON
 *  console — and it is the same coercion `pipeline/orders.py` performs at its own boundary
 *  for the same reason. Anything else, an object included, is `null`: `String({})` would
 *  produce `'[object Object]'` and post it as an order number. */
function requiredText(value: unknown): string | null {
  if (typeof value === 'string') {
    const trimmed = value.trim()
    return trimmed === '' ? null : trimmed
  }
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  return null
}

/** An optional field the projection carries verbatim: `undefined` where the feed said
 *  nothing, `null` where it said null, the text otherwise.
 *
 *  AN OBJECT OR AN ARRAY BECOMES `undefined` RATHER THAN BEING STRINGIFIED, and that is a
 *  PII rule rather than a tidiness one: a nested object under `name` is exactly where a
 *  buyer's details would hide, and `String(...)`-ing it would smuggle the whole subtree
 *  through a slot the whitelist thought it had checked. */
function optionalText(value: unknown): string | null | undefined {
  if (value === undefined) return undefined
  if (value === null) return null
  if (typeof value === 'string') return value
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  if (typeof value === 'boolean') return String(value)
  return undefined
}

/** What went wrong, as a sentence rather than an exception object. */
function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

type LineReading = { ok: true; line: OrderIngestLine } | { ok: false; problem: string }

function readLine(raw: unknown, where: string): LineReading {
  if (!isRecord(raw)) {
    return { ok: false, problem: `${where} is not an object. Each line should be a { … } with a sku and a quantity.` }
  }

  const sku = requiredText(raw['sku'])
  if (sku === null) {
    return { ok: false, problem: `${where} has no sku. The sku is the number the store stamps on a card, and nothing can be found without it.` }
  }

  /* `Number(...)` and then an integer test, in that order and with both halves. `Number`
   * alone accepts `'3 '`, `3.0` and `true`; `Number.isInteger` refuses the fraction and the
   * NaN that `undefined`, `''` and any object produce. A quantity of 0 is refused rather
   * than skipped: a line asking for nothing is a paste that went wrong, and quietly
   * dropping it would send an envelope one card short of what the screen showed. */
  const quantity = Number(raw['quantity'])
  if (!Number.isInteger(quantity) || quantity < 1) {
    return { ok: false, problem: `${where} asks for ${JSON.stringify(raw['quantity'])} copies. A quantity has to be a whole number of one or more.` }
  }

  const line: OrderIngestLine = { sku, quantity }
  const name = optionalText(raw['name'])
  if (name !== undefined) line.name = name
  const number = optionalText(raw['number'])
  if (number !== undefined) line.number = number
  const printing = optionalText(raw['printing'])
  if (printing !== undefined) line.printing = printing
  const condition = optionalText(raw['condition'])
  if (condition !== undefined) line.condition = condition
  const rarity = optionalText(raw['rarity'])
  if (rarity !== undefined) line.rarity = rarity
  const unitPrice = optionalText(raw['unit_price'])
  if (unitPrice !== undefined) line.unit_price = unitPrice
  const kind = optionalText(raw['kind'])
  if (kind !== undefined) line.kind = kind

  return { ok: true, line }
}

type OrderReading = { ok: true; order: OrderIngestOrder } | { ok: false; problem: string }

function readOrder(entry: unknown, position: number, dropped: Set<string>): OrderReading {
  const where = `Order ${position + 1}`
  if (!isRecord(entry)) {
    return { ok: false, problem: `${where} is not an object. An order is a { … } carrying a number and a list of lines.` }
  }

  /* THE PROJECTION'S RECEIPT, taken before anything is read, so a refusal further down does
   * not decide whether the owner gets told what was in the paste. */
  for (const key of Object.keys(entry)) {
    if (!ORDER_KEEP.has(key)) dropped.add(key)
  }

  const number = requiredText(entry['number'])
  if (number === null) {
    return { ok: false, problem: `${where} has no order number. The number is what the ledger is keyed by, so an order without one cannot be recorded.` }
  }

  const rawLines = entry['lines']
  if (!Array.isArray(rawLines)) {
    return { ok: false, problem: `Order ${number} has no lines list. It should carry "lines": [ … ], one entry per thing bought.` }
  }
  if (rawLines.length === 0) {
    return { ok: false, problem: `Order ${number} has an empty lines list. There is nothing to pull.` }
  }

  const lines: OrderIngestLine[] = []
  for (const [index, raw] of rawLines.entries()) {
    const reading = readLine(raw, `Line ${index + 1} of order ${number}`)
    if (!reading.ok) return { ok: false, problem: reading.problem }
    lines.push(reading.line)
  }

  const declared = requiredText(entry['source'])
  const order: OrderIngestOrder = {
    source: declared ?? DEFAULT_ORDER_SOURCE,
    number,
    lines,
  }
  const placedAt = optionalText(entry['placed_at'])
  if (placedAt !== undefined) order.placed_at = placedAt
  const status = optionalText(entry['status'])
  if (status !== undefined) order.status = status

  return { ok: true, order }
}

/** Read a pasted blob into orders the app may send, or into a sentence saying what to fix.
 *
 *  THREE SHAPES ARE ACCEPTED — one order object, a bare array of them, or
 *  `{"orders": [ … ]}` — because a human copying out of a console produces all three and
 *  normalising them costs four lines. Refusing two of the three would be a rule the operator
 *  has to learn about a paste they already have in the clipboard, which buys nothing: the
 *  three are unambiguous to tell apart, and every one of them projects identically. */
export function readPaste(text: string): PasteReading {
  if (text.trim() === '') {
    return { ok: false, problem: 'Nothing pasted. Copy the order JSON and paste it in.' }
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch (error) {
    return {
      ok: false,
      problem: `That is not JSON: ${messageOf(error)}. Paste the order as it came out, braces and all.`,
    }
  }

  const dropped = new Set<string>()
  let entries: unknown[]
  if (Array.isArray(parsed)) {
    entries = parsed
  } else if (isRecord(parsed) && 'orders' in parsed) {
    const list = parsed['orders']
    if (!Array.isArray(list)) {
      return { ok: false, problem: 'The paste has an "orders" key but it is not a list. It should be "orders": [ … ].' }
    }
    /* The wrapper's own extra keys are dropped and named too. A payload with the buyer at
     * the top and the orders beneath it is a real shape, and a projection that only looked
     * inside each order would carry it straight through. */
    for (const key of Object.keys(parsed)) {
      if (key !== 'orders') dropped.add(key)
    }
    entries = list
  } else {
    entries = [parsed]
  }

  if (entries.length === 0) {
    return { ok: false, problem: 'That paste holds no orders. Copy the whole order, from its opening brace.' }
  }

  const orders: OrderIngestOrder[] = []
  for (const [position, entry] of entries.entries()) {
    const reading = readOrder(entry, position, dropped)
    if (!reading.ok) return { ok: false, problem: reading.problem }
    orders.push(reading.order)
  }

  /* Sorted and de-duplicated: a list of dropped keys is read, not walked in feed order, and
   * four orders carrying the same buyer field should say `buyer` once. */
  return { ok: true, orders, dropped: [...dropped].sort() }
}
