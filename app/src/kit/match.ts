/* ONE FORGIVING MATCHER FOR EVERY SEARCH IN THE APP (the owner's ruling, 2026-09-23).
 *
 * The filtering review found four search fields with four rules (FLT-06): Sales matched the
 * literal string in the name only, Graveyard the literal string over five fields, Orders a
 * number the row does not draw, and the store's own search wanted the leading zeros of a
 * collector number (FLT-04). A person types what they read off the card or the row. This
 * answers that one way everywhere a list is filtered in the browser.
 *
 * THE RULES, IN ORDER. They are stated here, not only coded, so that any other search that
 * must agree with this one can be checked against them.
 *
 *  1. FOLD. A string is NFKC-normalized (full-width `５４` is `54`), then NFKD-normalized, its
 *     combining marks are removed, and it is lower-cased. Apostrophes (' ’ ʼ ` ´) are removed,
 *     so `Farfetch'd` is `farfetchd`. Every other run of characters that is not a letter or a
 *     digit becomes one space: `Ho-Oh ex` is `ho oh ex`, `Akali, Deadly` is `akali deadly`.
 *     The COMPACT form of a string is its fold with the spaces removed: `hoohex`.
 *  2. SPLIT. The query is NFKC-normalized, commas become spaces, and it is cut on white space.
 *     Each token loses the punctuation at its ends, except a `#` or a `/` in front.
 *  3. EVERY TOKEN MUST MATCH, IN ANY ORDER. An empty query matches every row. Two tokens next
 *     to each other may match TOGETHER as one card number (rule 4), so `54 132` and `swsh 050`
 *     work. Every way to cover the tokens is tried.
 *  4. A CARD NUMBER is compared on its CANONICAL form: each `/` part is folded, its spaces are
 *     removed, and the zeros in front of its first digit run are removed. `054/132` is
 *     `54/132`, `SWSH050` is `swsh50`, `OP01-001` is `op1001`.
 *      - A token with a `/` matches a card number with the same canonical form.
 *      - A token with no `/` matches the whole number, or its first part: `54` finds `054/132`.
 *      - A hyphen between two digits may also stand for the `/`: `054-132` finds `054/132`.
 *      - A token that starts with `/` matches the second part: `/132` finds every `N/132`.
 *      - Two tokens next to each other match as one number joined by `/` or by nothing.
 *      - Never a substring: `54` does not find `154/200`.
 *  5. A BOX IS FOUND BY ITS NAME ONLY, which is text (rule 7). Its number is never shown and
 *     never searched (the owner's ruling, 2026-09-23): `4` and `B4` do not find a box named
 *     `Mixed Singles` whose number is 4. A box nobody named carries the stored name `Box 4`, so
 *     `box 4` still finds it, by name.
 *  6. A SKU. A token of three or more digits matches a SKU that STARTS with it, zeros kept.
 *  7. TEXT. Otherwise the token is folded (rule 1) into words, and every word must be found in
 *     some text field:
 *      - A word with a letter is found as a substring of a folded field. Mid-word works:
 *        `ventor` finds `Inventor`.
 *      - A word of digits only is found as a WHOLE word or the START of a word, zeros in front
 *        ignored. Typed with no zeros in front, it is the start of a word with its zeros
 *        dropped: `12` finds `00012` and `123`, never `112`. Typed with zeros in front, it is
 *        the start of the word as written, or equal once the zeros go: `0001` finds `00012`, so
 *        an order label narrows as it is typed, and `0002` never finds `26`. A word of only
 *        zeros (`0`, `00`) finds every word that starts with it.
 *     As a fallback, a token with a letter in it matches when its compact form is a substring
 *     of a field's compact form: `hooh` finds `Ho-Oh ex`, `porygonz` finds `Porygon-Z`.
 *     Text fields are what the row draws: a name, a set, a condition (`Damaged`), a buyer, a
 *     note, an order label, a box name.
 *
 * PURE. No React, no state, no network: the same function answers in a spec and on a screen. */

/** The fields of one row a search may match, grouped by how each is compared. */
export type MatchFields = {
  /** What the row draws as words: a name, a set, a condition, a buyer, a label. Rule 7. */
  readonly text?: readonly (string | null | undefined)[]
  /** Collector numbers, as the card prints them (`054/132`). Rule 4. */
  readonly numbers?: readonly (string | null | undefined)[]
  /** TCGplayer SKUs. Rule 6. */
  readonly skus?: readonly (string | number | null | undefined)[]
  /** The boxes the row is in. Only the NAME is matched, as text (rules 5 and 7); `box` is
   *  kept so a caller can hand the record over whole, and is never searched. */
  readonly boxes?: readonly { readonly box: number; readonly name?: string | null }[]
}

const APOSTROPHES = /['’ʼ`´]/gu

/** Rule 1: NFKC, NFKD, no marks, lower case, no apostrophes, other non-alphanumeric runs to
 *  one space. */
export function foldText(value: string): string {
  return value
    .normalize('NFKC')
    .normalize('NFKD')
    .replace(/\p{M}+/gu, '')
    .toLowerCase()
    .replace(APOSTROPHES, '')
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
}

/** Rule 1's compact form: the fold with no spaces. */
export function compactText(value: string): string {
  return foldText(value).replace(/ /gu, '')
}

/** The zeros in front of the first digit run go: `tg05` is `tg5`, `054` is `54`. */
function dropLeadingZeros(part: string): string {
  return part.replace(/^(\p{L}*?)0+(?=\d)/u, '$1')
}

/** Rule 4: a collector number's canonical form. `054/132` and `54/132` are both `54/132`. */
export function canonicalNumber(value: string): string {
  return value
    .normalize('NFKC')
    .split('/')
    .map((part) => dropLeadingZeros(compactText(part)))
    .join('/')
}

/** What a canonical card number may look like: letters, digits, an optional letter, and an
 *  optional second part of the same shape. */
const NUMBER_SHAPE = /^\p{L}{0,6}\d+\p{L}{0,2}(?:\/\p{L}{0,6}\d+\p{L}{0,2})?$/u
const SKU_SHAPE = /^\d{3,}$/u
const DIGITS = /^\d+$/u
const HAS_DIGIT = /\d/u
const HAS_LETTER = /\p{L}/u
/** The punctuation a token loses at its ends. `#` and `/` survive in front (rule 4). */
const EDGE_PUNCTUATION = /^[^\p{L}\p{N}#/]+|[^\p{L}\p{N}]+$/gu

/** Rule 2: the raw tokens of a query. */
export function queryTokens(query: string): string[] {
  /* Commas become spaces first, then one white-space split: a query is not a CSV row. */
  return query
    .normalize('NFKC')
    .replace(/,/gu, ' ')
    .split(/\s+/u)
    .map((token) => token.replace(EDGE_PUNCTUATION, ''))
    .filter((token) => token !== '' && token !== '#' && token !== '/')
}

function present<T>(value: T | null | undefined): value is T {
  return value !== null && value !== undefined
}

type NumberParts = { readonly whole: string; readonly first: string; readonly second: string | null }

/** A row, prepared once for many tokens. */
type Prepared = {
  readonly folded: readonly string[]
  readonly compact: readonly string[]
  /** Every digits-only word of every folded text field, as written and with its zeros in
   *  front dropped, for the digits-only rule. */
  readonly words: readonly { readonly raw: string; readonly bare: string }[]
  readonly numbers: readonly NumberParts[]
  readonly skus: readonly string[]
}

function prepare(fields: MatchFields): Prepared {
  const text = [...(fields.text ?? []).filter(present), ...(fields.boxes ?? []).map((one) => one.name).filter(present)]
  const folded = text.map(foldText).filter((one) => one !== '')
  const words: { raw: string; bare: string }[] = []
  for (const one of folded) {
    for (const word of one.split(' ')) if (DIGITS.test(word)) words.push({ raw: word, bare: dropLeadingZeros(word) })
  }
  return {
    folded,
    compact: folded.map((one) => one.replace(/ /gu, '')),
    words,
    numbers: (fields.numbers ?? [])
      .filter(present)
      .map(canonicalNumber)
      .filter((one) => one !== '')
      .map((whole) => {
        const [first = '', second] = whole.split('/')
        return { whole, first, second: second ?? null }
      }),
    skus: (fields.skus ?? []).filter(present).map((sku) => String(sku).trim()),
  }
}

/** Rule 4, for one raw token (a `#` or `/` in front allowed). */
function numberMatch(raw: string, row: Prepared): boolean {
  if (row.numbers.length === 0) return false
  if (raw.startsWith('/')) {
    const second = canonicalNumber(raw.slice(1))
    if (!HAS_DIGIT.test(second) || second.includes('/')) return false
    return row.numbers.some((number) => number.second === second)
  }
  const bare = raw.replace(/^#/u, '')
  if (!HAS_DIGIT.test(bare)) return false
  const forms = new Set([canonicalNumber(bare), canonicalNumber(bare.replace(/(\d)-(?=\d)/gu, '$1/'))])
  for (const form of forms) {
    if (!NUMBER_SHAPE.test(form)) continue
    const whole = form.includes('/')
    if (row.numbers.some((number) => number.whole === form || (!whole && number.first === form))) return true
  }
  return false
}

/** Rule 7's digits-only word: the start of a digits-only text word, as written or with the zeros
 *  in front of both dropped. */
function digitWordMatch(word: string, row: Prepared): boolean {
  /* Only zeros so far (`0`, `00`): the first keys of `09-03-26_…` or `00012`. Any word that
   * starts with them matches, so the first key never empties the list. */
  if (/^0+$/u.test(word)) return row.words.some((one) => one.raw.startsWith(word))
  const bare = dropLeadingZeros(word)
  /* A word typed WITH zeros in front is being typed as written, so it is the start of the word
   * as written (`0001` of `00012`), or equal once the zeros are dropped. A word typed without
   * them is the start of a word whose zeros are dropped (`12` of `00012`). So `0002` never
   * finds `26`, and `12` never finds `112`. */
  if (word !== bare) return row.words.some((one) => one.raw.startsWith(word) || one.bare === bare)
  return row.words.some((one) => one.bare.startsWith(bare))
}

/** Rule 7, for one raw token. */
function textMatch(raw: string, row: Prepared): boolean {
  const words = foldText(raw).split(' ').filter((word) => word !== '')
  if (words.length === 0) return false
  const each = words.every((word) =>
    DIGITS.test(word) ? digitWordMatch(word, row) : row.folded.some((field) => field.includes(word)),
  )
  if (each) return true
  const compact = words.join('')
  return HAS_LETTER.test(compact) && row.compact.some((field) => field.includes(compact))
}

/** Rules 4 to 7 for one token alone. */
function tokenMatch(raw: string, row: Prepared): boolean {
  if (SKU_SHAPE.test(raw) && row.skus.some((sku) => sku.startsWith(raw))) return true
  if (numberMatch(raw, row)) return true
  if (raw.startsWith('/')) return false
  return textMatch(raw, row)
}

/** Rule 3: two neighbouring tokens that match together as one card number. */
function pairMatch(left: string, right: string, row: Prepared): boolean {
  if (left.startsWith('/') || right.startsWith('/') || right.startsWith('#')) return false
  return numberMatch(`${left}/${right}`, row) || numberMatch(`${left}${right}`, row)
}

/** Can the tokens from `at` on all be matched, singly or in neighbouring pairs? */
function cover(tokens: readonly string[], at: number, row: Prepared): boolean {
  if (at >= tokens.length) return true
  const one = tokens[at] as string
  if (tokenMatch(one, row) && cover(tokens, at + 1, row)) return true
  const two = tokens[at + 1]
  return two !== undefined && pairMatch(one, two, row) && cover(tokens, at + 2, row)
}

/** Does this row match this query? Every token must match, in any order (rules 2 to 7). */
export function matchQuery(query: string, fields: MatchFields): boolean {
  const tokens = queryTokens(query)
  if (tokens.length === 0) return true
  return cover(tokens, 0, prepare(fields))
}

/** The rows that match, in their own order. `fieldsOf` says what each row draws. */
export function filterByQuery<T>(rows: readonly T[], query: string, fieldsOf: (row: T) => MatchFields): T[] {
  const tokens = queryTokens(query)
  if (tokens.length === 0) return [...rows]
  return rows.filter((row) => cover(tokens, 0, prepare(fieldsOf(row))))
}
