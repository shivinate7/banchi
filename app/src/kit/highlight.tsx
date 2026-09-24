import type { ReactNode } from 'react'

import { queryTokens } from './match'

/* THE MATCH HIGHLIGHT (FLT-08: "no search result shows what matched"). A row that is in a
 * filtered list because a word in it matched should say which word, so a hit on a SKU, a set
 * hint or a note is not a mystery.
 *
 * BEST EFFORT, ON PURPOSE. `kit/match.ts` decides WHETHER a row matches, with rule 4's card-
 * number arithmetic (leading zeros, a hyphen standing in for a slash, two tokens joined) and
 * rule 6's SKU-prefix rule. Painting those exact spans back onto the printed text would need a
 * second copy of that arithmetic run in reverse, against text a caller already has to hand
 * whole. This file marks the plainer, and far more common, case instead: a token found as a
 * case- and accent-folded SUBSTRING of the text (rule 7), which is what FLT-08's own examples
 * are (`Hextech`, `premo`). A row that matched only on its number or its SKU draws no mark here,
 * same as before — no worse, and never a WRONG mark, which would be worse than none. */

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

/** `[start, end)` ranges of `text` (original indices) that a token of `query` matches, folded
 *  and merged. Numbers, `#`- and `/`-prefixed tokens are skipped: `kit/match.ts` may still match
 *  them, this file only never paints a span for them (see the file header). */
export function matchSpans(text: string, query: string): readonly (readonly [number, number])[] {
  if (text === '') return []
  const rawTokens = queryTokens(query).filter((token) => !token.startsWith('#') && !token.startsWith('/'))
  if (rawTokens.length === 0) return []

  const { folded, foldedAt, compact, compactAt } = indexedFolds(text)
  const spans: [number, number][] = []
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
  if (spans.length === 0) return []

  spans.sort((a, b) => a[0] - b[0] || a[1] - b[1])
  const merged: [number, number][] = [spans[0] as [number, number]]
  for (const span of spans.slice(1)) {
    const last = merged[merged.length - 1] as [number, number]
    if (span[0] <= last[1]) last[1] = Math.max(last[1], span[1])
    else merged.push(span)
  }
  return merged
}

/** `text`, with every word `query` matched drawn in a `<mark>`. Renders `text` unchanged when
 *  nothing matched, so a caller may wrap every row's text in this with no cost for the common
 *  case of an unfiltered list. */
export function Highlight({
  text,
  query,
  className,
}: {
  readonly text: string
  readonly query: string
  readonly className?: string
}): ReactNode {
  const spans = matchSpans(text, query)
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
