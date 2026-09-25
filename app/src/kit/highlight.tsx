import type { ReactNode } from 'react'

import { canonicalNumber, matchQuery, queryTokens, type MatchFields } from './match'

/* THE MATCH HIGHLIGHT (FLT-08: "no search result shows what matched"). A row that is in a
 * filtered list because a word in it matched should say which word, so a hit on a SKU, a set
 * hint or a note is not a mystery.
 *
 * THE MATCHER DECIDES, THE HIGHLIGHT ONLY PAINTS. `kit/match.ts:matchQuery` says WHETHER a row
 * matches. A row it refuses gets no mark at all, even where one word of the query is a
 * substring of the text: a mark on a row the list would not show is a lie about why it is
 * there. A caller passes the row's whole `MatchFields` as `row`. Without one, the text alone is
 * the row.
 *
 * TWO KINDS OF TEXT, TWO WAYS TO PAINT:
 *  - `text` (the default): a token found as a case- and accent-folded SUBSTRING of the text
 *    (rule 7), or, when that finds nothing, of its compact form, so `heimerdinger-inventor`
 *    marks "Heimerdinger, Inventor".
 *  - `number`: a card number is compared on its CANONICAL form (rule 4), never as a substring,
 *    so `54/132` marks the whole of `054/132`, `54` marks its `054` part, and `/132` its `132`
 *    part. A hyphen between digits and two neighbouring tokens (`54 132`) work as they do in
 *    the matcher.
 * A token that matched only a SKU draws no mark: the SKU is not in the text. */

const APOSTROPHES = /['’ʼ`´]/gu

/** One character, folded the same way `kit/match.ts:foldText` folds a whole string, MINUS the
 *  punctuation-to-space step: this file needs the fold to keep the text's own length and
 *  character order, one input character producing zero or more output characters, so a span it
 *  finds in the folded copy maps straight back to the ORIGINAL string's positions. */
function foldChar(ch: string): string {
  return ch
    .normalize('NFKD')
    .replace(/\p{M}+/gu, '')
    .toLowerCase()
    .replace(APOSTROPHES, '')
}

/** One text, folded two ways at once, each character mapped back to where it came from in
 *  `text`: `folded` keeps every character but the marks, the case and the apostrophes (rule 1
 *  minus its punctuation-to-space step); `compact` drops every non-alphanumeric character too
 *  (rule 7's own fallback, `compactText`). A span found in either maps straight back onto
 *  `text` untouched. */
function indexedFolds(text: string): {
  readonly folded: string
  readonly foldedAt: readonly number[]
  readonly compact: string
  readonly compactAt: readonly number[]
} {
  let folded = ''
  const foldedAt: number[] = []
  let compact = ''
  const compactAt: number[] = []
  for (let i = 0; i < text.length; i++) {
    for (const piece of foldChar(text[i] as string)) {
      folded += piece
      foldedAt.push(i)
      if (/[\p{L}\p{N}]/u.test(piece)) {
        compact += piece
        compactAt.push(i)
      }
    }
  }
  return { folded, foldedAt, compact, compactAt }
}

/** Every `[start, end)` a folded `needle` finds in a folded `haystack`, mapped back through
 *  `at` onto the original string's indices. */
function findAll(haystack: string, at: readonly number[], needle: string): [number, number][] {
  if (needle === '') return []
  const spans: [number, number][] = []
  let from = 0
  while (from <= haystack.length - needle.length) {
    const found = haystack.indexOf(needle, from)
    if (found === -1) break
    spans.push([at[found] as number, (at[found + needle.length - 1] as number) + 1])
    from = found + 1
  }
  return spans
}

type Span = [number, number]

/** Overlapping or touching spans, merged, in order. */
function mergeSpans(spans: Span[]): readonly (readonly [number, number])[] {
  if (spans.length === 0) return []
  spans.sort((a, b) => a[0] - b[0] || a[1] - b[1])
  const merged: Span[] = [spans[0] as Span]
  for (const span of spans.slice(1)) {
    const last = merged[merged.length - 1] as Span
    if (span[0] <= last[1]) last[1] = Math.max(last[1], span[1])
    else merged.push(span)
  }
  return merged
}

/** Rule 7's spans: every word of the query found in the text, folded. */
function textSpans(text: string, tokens: readonly string[]): Span[] {
  const rawTokens = tokens.filter((token) => !token.startsWith('#') && !token.startsWith('/'))
  const { folded, foldedAt, compact, compactAt } = indexedFolds(text)
  const spans: Span[] = []
  for (const raw of rawTokens) {
    const folded_ = [...raw].map(foldChar).join('')
    if (folded_ === '' || !/\p{L}/u.test(folded_)) continue
    /* Rule 7's own order: a direct fold match first (a plain word, or one that folds onto the
     *  text as written), and only when that finds NOTHING does the compact fallback run — the
     *  one that lets `heimerdinger-inventor` find "Heimerdinger, Inventor" the way
     *  `kit/match.ts`'s own fallback does. */
    const direct = findAll(folded, foldedAt, folded_)
    if (direct.length > 0) {
      spans.push(...direct)
      continue
    }
    const compactToken = [...folded_].filter((ch) => /[\p{L}\p{N}]/u.test(ch)).join('')
    spans.push(...findAll(compact, compactAt, compactToken))
  }
  return spans
}

/** Rule 4's spans, on a card number: the whole number when a token's canonical form is the
 *  number's, its first part when a token without a `/` equals that part, its second part for a
 *  `/`-led token. Each token alone, and each two neighbours joined, as the matcher tries them. */
function numberSpans(text: string, tokens: readonly string[]): Span[] {
  const canonical = canonicalNumber(text)
  if (canonical === '') return []
  const [first = '', second = null] = canonical.split('/')
  const slash = text.indexOf('/')
  const whole: Span = [0, text.length]
  const firstPart: Span = slash === -1 ? whole : [0, slash]
  const secondPart: Span | null = slash === -1 ? null : [slash + 1, text.length]

  const tries: string[] = [...tokens]
  for (let at = 0; at + 1 < tokens.length; at++) {
    const left = tokens[at] as string
    const right = tokens[at + 1] as string
    if (left.startsWith('/') || right.startsWith('/') || right.startsWith('#')) continue
    tries.push(`${left}/${right}`, `${left}${right}`)
  }

  const spans: Span[] = []
  for (const token of tries) {
    if (token.startsWith('/')) {
      if (secondPart !== null && second !== null && canonicalNumber(token.slice(1)) === second) spans.push(secondPart)
      continue
    }
    const bare = token.replace(/^#/u, '')
    if (!/\d/u.test(bare)) continue
    for (const form of new Set([canonicalNumber(bare), canonicalNumber(bare.replace(/(\d)-(?=\d)/gu, '$1/'))])) {
      if (form === canonical) spans.push(whole)
      else if (!form.includes('/') && form === first) spans.push(firstPart)
    }
  }
  return spans
}

export type HighlightKind = 'text' | 'number'

/** `[start, end)` ranges of `text` (original indices) that `query` matches, merged. Empty when
 *  `kit/match.ts:matchQuery` refuses the row: `row` is the row's whole `MatchFields`, and
 *  without it the text alone is the row (as a text field, or as a card number when `kind` is
 *  `number`). */
export function matchSpans(
  text: string,
  query: string,
  { row, kind = 'text' }: { readonly row?: MatchFields; readonly kind?: HighlightKind } = {},
): readonly (readonly [number, number])[] {
  if (text === '') return []
  const tokens = queryTokens(query)
  if (tokens.length === 0) return []
  const fields: MatchFields = row ?? (kind === 'number' ? { numbers: [text] } : { text: [text] })
  if (!matchQuery(query, fields)) return []
  return mergeSpans(kind === 'number' ? numberSpans(text, tokens) : textSpans(text, tokens))
}

/** `text`, with every part `query` matched drawn in a `<mark>`, on a row the matcher accepts
 *  (see `matchSpans`). Renders `text` unchanged when nothing matched, so a caller may wrap
 *  every row's text in this with no cost for an unfiltered list. */
export function Highlight({
  text,
  query,
  row,
  kind,
  className,
}: {
  readonly text: string
  readonly query: string
  /** The row's whole `MatchFields`, the same a screen hands `matchQuery`. */
  readonly row?: MatchFields
  /** `number` for a card number (`054/132`). */
  readonly kind?: HighlightKind
  readonly className?: string
}): ReactNode {
  const spans = matchSpans(text, query, { row, kind })
  if (spans.length === 0) return text

  const marked = ['bn-highlight', className].filter(Boolean).join(' ')
  const out: ReactNode[] = []
  let cursor = 0
  spans.forEach(([start, end], at) => {
    if (start > cursor) out.push(text.slice(cursor, start))
    out.push(
      <mark key={at} className={marked}>
        {text.slice(start, end)}
      </mark>,
    )
    cursor = end
  })
  if (cursor < text.length) out.push(text.slice(cursor))
  return out
}
