/* THE COPY RULES, IN ONE FILE, READ BY THE SWEEP AND BY THE UNIT TIER (DESIGN.md "Copy rules", R4, R4a, R5).
 *
 * Pure functions only: no page, no import of Playwright. `copy-checks.spec.ts` sends the rendered
 * strings in through `page.evaluate` and classifies them HERE, in Node, so the rule lives in exactly
 * one place and the unit tier can test the same function the sweep runs. A second copy of the word
 * list in a browser closure would drift the first time one of them changed.
 *
 * VOICE (R4, R4a). A user-visible string may not contain "I", "my", "me" or "mine" as a whole word,
 * in any case. "I'm" counts (the "I" stands alone before the apostrophe). "Inventory", "Mine" inside
 * "Mineral" and "Remember" do not, because the match must be bounded by non-letters on both sides.
 *
 * CASING (R5, Chicago style). A label takes Title Case: the first and last word capitalized, and every
 * word between them capitalized except the small words below, which stay lowercase. A word with a
 * digit, a number, a dollar figure or a unit is not a word here. A hyphenated word must capitalize
 * each part. A full sentence (ends in . ? ! ) is not a label and is skipped by `isSentence`.
 */

/** Chicago's small words: lowercase in the middle of a title, capitalized first or last. */
export const SMALL_WORDS: ReadonlySet<string> = new Set([
  'a', 'an', 'the', 'and', 'but', 'or', 'nor', 'for', 'so', 'yet',
  'as', 'at', 'by', 'in', 'of', 'on', 'to', 'up', 'via', 'per', 'unless',
])

/** "I", "my", "me", "mine" as whole words, any case. Lookarounds bound the match by non-letters. */
const FIRST_PERSON = /(?<![\p{L}\p{N}_])(?:i|my|me|mine)(?![\p{L}\p{N}_])/giu

/** The first-person words a string contains, lower-cased, in order, one entry per occurrence. */
export function voiceHits(text: string): string[] {
  return Array.from(text.matchAll(FIRST_PERSON), (match) => match[0].toLowerCase())
}

/** A full sentence: the trimmed text ends in . ? or ! (a closing quote or bracket may follow). */
export function isSentence(text: string): boolean {
  return /[.?!]["'”’)\]]*$/.test(text.trim())
}

/** Units that may follow a number unchanged: `10 ml`, `1 month`. A count noun such as `cards` is a word. */
export const UNIT_WORDS: ReadonlySet<string> = new Set([
  'ml', 'mm', 'cm', 'kg', 'g', 'oz', 'px', 'x',
  'second', 'seconds', 'minute', 'minutes', 'hour', 'hours',
  'day', 'days', 'week', 'weeks', 'month', 'months', 'year', 'years',
])

/** Each Title Case problem in one label, as a sentence a reader can act on. Empty means it passes.
 *  Numbers do not count as words, but they still END a title: in `Pick 1 of 1` the word `of` is in
 *  the middle, so it stays lower-case. */
export function casingProblems(text: string): string[] {
  const tokens = text.trim().split(/\s+/).filter((token) => token !== '')
  const carriers = tokens.flatMap((token, index) => (/[\p{L}\p{N}]/u.test(token) ? [index] : []))
  if (carriers.length === 0) return []
  const firstIndex = carriers[0]
  const lastIndex = carriers[carriers.length - 1]

  const problems: string[] = []
  let afterNumber = false
  tokens.forEach((token, index) => {
    if (/\d/.test(token)) {
      afterNumber = true
      return
    }
    const wasAfterNumber = afterNumber
    afterNumber = false
    const core = token.replace(/^[^\p{L}]+/u, '').replace(/[^\p{L}]+$/u, '')
    if (core === '') return
    if (wasAfterNumber && UNIT_WORDS.has(core.toLowerCase())) return

    const parts = core.split('-').map((part) => part.replace(/^[^\p{L}]+/u, '')).filter((part) => part !== '')
    if (parts.length > 1) {
      for (const part of parts) {
        if (!/^\p{Lu}/u.test(part)) problems.push(`"${core}": "${part}" should be capitalized`)
      }
      return
    }

    const edge = index === firstIndex || index === lastIndex
    const capitalized = /^\p{Lu}/u.test(core)
    if (edge || !SMALL_WORDS.has(core.toLowerCase())) {
      if (!capitalized) problems.push(`"${core}" should be capitalized`)
    } else if (capitalized) {
      problems.push(`"${core}" should be lowercase`)
    }
  })
  return problems
}
