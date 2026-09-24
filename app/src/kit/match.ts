/* ONE FORGIVING MATCHER FOR EVERY SEARCH IN THE APP (the owner's ruling, 2026-09-23).
 *
 * The filtering review found four search fields with four rules (FLT-06): Sales matched the
 * literal string in the name only, Graveyard the literal string over five fields, Orders a
 * number the row does not draw, and the store's own search wanted the leading zeros of a
 * collector number (FLT-04). A person types what they read off the card or the row. This
 * answers that one way everywhere a list is filtered in the browser.
 *
 * THE RULES, IN ORDER. The server's search must fold its own side the same way, so these are
 * stated as rules and not left to be read out of the code:
 *
 *  1. FOLD. A string is NFKD-normalized, its combining marks are removed, it is lower-cased,
 *     and every run of characters that is not a letter or a digit becomes one space. So
 *     `Flabébé` is `flabebe`, `heimerdinger-inventor` is `heimerdinger inventor`, and
 *     `Akali, Deadly` is `akali deadly`.
 *  2. SPLIT. The query is cut on white space and commas into raw tokens, and each token loses
 *     leading and trailing punctuation (a `#` in front is kept for rule 4).
 *  3. EVERY TOKEN MUST MATCH, IN ANY ORDER. A row matches when each token matches at least one
 *     of its fields. An empty query matches every row.
 *  4. A CARD NUMBER. A token with a digit in it that has the shape of a collector number
 *     (`54`, `054/132`, `#54`, `TG05/TG30`, `SWSH050`) is compared on its CANONICAL form: folded,
 *     spaces and hyphens removed, cut on `/`, and each part stripped of the zeros in front of its
 *     first digit run (`054/132` is `54/132`, `tg05` is `tg5`). It matches a card number with
 *     the same canonical form. With no `/`, it also matches a card number whose first part is
 *     the same (`54` finds `054/132`). It is never a substring match on a number, so `54` does
 *     not find `154/200`.
 *  5. A BOX. A token `B4`, `box4` or `box-4` matches box 4. The words `box 4` also match, by
 *     rule 7, because every box is searchable as the text `box <n>` and its name.
 *  6. A SKU. A token of three or more digits matches a SKU that STARTS with it, zeros kept.
 *  7. TEXT. Otherwise, and also as a fallback for rules 4 to 6, the token is folded (rule 1),
 *     and every word of it must be a substring of some folded text field. A token that folds to
 *     several words (`heimerdinger-inventor`) is that many words. Mid-word text matches
 *     (`ventor` finds `Inventor`). Text fields are what the row draws: a name, a set, a
 *     condition (`Damaged`, `Near Mint Foil`), a buyer, a note, an order label.
 *
 * PURE. No React, no state, no network: the same function answers in a spec and on a screen. */

/** The fields of one row a search may match, grouped by how each is compared. */
export type MatchFields = {
  /** What the row draws as words: a name, a set, a condition, a buyer, a label. Rules 1 and 7. */
  readonly text?: readonly (string | null | undefined)[]
  /** Collector numbers, as the card prints them (`054/132`). Rule 4. */
  readonly numbers?: readonly (string | null | undefined)[]
  /** TCGplayer SKUs. Rule 6. */
  readonly skus?: readonly (string | number | null | undefined)[]
  /** The boxes the row is in, with their names. Rules 5 and 7. */
  readonly boxes?: readonly { readonly box: number; readonly name?: string | null }[]
}

/** Rule 1: NFKD, no marks, lower case, every non-letter-non-digit run to one space. */
export function foldText(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/\p{M}+/gu, '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
}

/** Rule 4: a collector number's canonical form. `054/132` and `54/132` are both `54/132`. */
export function canonicalNumber(value: string): string {
  return value
    .split('/')
    .map((part) => foldText(part).replace(/ /g, '').replace(/^(\p{L}*?)0+(?=\d)/u, '$1'))
    .join('/')
}

const NUMBER_SHAPE = /^#?[\p{L}]{0,6}-?\d+[\p{L}]?(?:\/[\p{L}]{0,6}-?\d+[\p{L}]?)?$/u
const BOX_SHAPE = /^b(?:ox)?-?(\d+)$/iu
const SKU_SHAPE = /^\d{3,}$/u
const EDGE_PUNCTUATION = /^[^\p{L}\p{N}#]+|[^\p{L}\p{N}]+$/gu

/** Rule 2: the raw tokens of a query. */
export function queryTokens(query: string): string[] {
  /* Commas become spaces first, then one white-space split: a query is not a CSV row. */
  return query
    .replace(/,/gu, ' ')
    .split(/\s+/u)
    .map((token) => token.replace(EDGE_PUNCTUATION, ''))
    .filter((token) => token !== '' && token !== '#')
}

function present<T>(value: T | null | undefined): value is T {
  return value !== null && value !== undefined
}

/** A row, prepared once for many tokens. */
type Prepared = {
  readonly haystack: readonly string[]
  readonly numbers: readonly string[]
  readonly skus: readonly string[]
  readonly boxes: ReadonlySet<number>
}

function prepare(fields: MatchFields): Prepared {
  const boxes = fields.boxes ?? []
  const haystack = [
    ...(fields.text ?? []).filter(present),
    ...boxes.flatMap((one) => [`box ${one.box}`, one.name ?? '']),
  ]
    .map(foldText)
    .filter((text) => text !== '')
  return {
    haystack,
    numbers: (fields.numbers ?? []).filter(present).map(canonicalNumber).filter((n) => n !== ''),
    skus: (fields.skus ?? []).filter(present).map((sku) => String(sku).trim()),
    boxes: new Set(boxes.map((one) => one.box)),
  }
}

/** Rule 7 alone: every folded word of `token` is inside some folded text field. */
function textMatch(token: string, row: Prepared): boolean {
  const words = foldText(token).split(' ').filter((word) => word !== '')
  if (words.length === 0) return true
  return words.every((word) => row.haystack.some((text) => text.includes(word)))
}

function tokenMatch(token: string, row: Prepared): boolean {
  const box = BOX_SHAPE.exec(token)
  if (box !== null && row.boxes.has(Number.parseInt(box[1] ?? '', 10))) return true

  if (SKU_SHAPE.test(token) && row.skus.some((sku) => sku.startsWith(token))) return true

  if (/\d/u.test(token) && NUMBER_SHAPE.test(token)) {
    const wanted = canonicalNumber(token.replace(/^#/u, ''))
    const whole = wanted.includes('/')
    if (row.numbers.some((number) => number === wanted || (!whole && number.split('/')[0] === wanted))) return true
  }

  return textMatch(token, row)
}

/** Does this row match this query? Every token must match some field, in any order. */
export function matchQuery(query: string, fields: MatchFields): boolean {
  const tokens = queryTokens(query)
  if (tokens.length === 0) return true
  const row = prepare(fields)
  return tokens.every((token) => tokenMatch(token, row))
}

/** The rows that match, in their own order. `fieldsOf` says what each row draws. */
export function filterByQuery<T>(rows: readonly T[], query: string, fieldsOf: (row: T) => MatchFields): T[] {
  if (queryTokens(query).length === 0) return [...rows]
  return rows.filter((row) => matchQuery(query, fieldsOf(row)))
}
