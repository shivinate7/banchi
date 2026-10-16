/* THE COPY RULES, IN ONE FILE, READ BY THE SWEEP AND BY THE UNIT TIER (DESIGN.md "Copy rules", R4, R4a, R5).
 *
 * Functions only: no page, no import of Playwright. The one file it reads is `src/CardHero.tsx`, for its SMALL_WORDS
 * literal (`smallWordsOf`). `copy-checks.spec.ts` sends the rendered
 * strings in through `page.evaluate` and classifies them HERE, in Node, so the rule lives in exactly
 * one place and the unit tier can test the same function the sweep runs. A second copy of the word
 * list in a browser closure would drift the first time one of them changed.
 *
 * VOICE (R4, R4a). A user-visible string may not contain "I", "my", "me" or "mine" as a whole word,
 * in any case. "I'm" counts (the "I" stands alone before the apostrophe). "Inventory", "Mine" inside
 * "Mineral" and "Remember" do not, because the match must be bounded by non-letters on both sides.
 *
 * CASING (R5, Chicago style). A label takes Title Case: the first and last word capitalized, and every
 * word between them capitalized except the small words below, which stay lowercase. A number, a dollar
 * figure or a unit is not a word here, but a hyphenated word with a digit (`3-day`) reads its word part.
 * A hyphenated word must capitalize each part. A control's first line is a label whatever its punctuation: `Cards to pull.` is checked as
 * `Cards to pull`. Prose (a text node, or a description line under a title) is not read for casing.
 * A typed value carries a `data-typed` marker in the DOM and is skipped by the sweep, not by this file.
 */

/** Chicago's small words: lowercase in the middle of a title, capitalized first or last. */
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import ts from 'typescript'

/* THE ONE HOME FOR THE SMALL WORDS is `src/CardHero.tsx` (the list `titleCase` uses). This rule READS that literal with the
 * TypeScript parser, never a copy. CardHero.tsx itself cannot be imported here: its import chain reaches a stylesheet, which
 * the Node unit runner cannot load. A missing or non-literal list is a throw, not an empty set. */
const CARD_HERO = resolve(dirname(fileURLToPath(import.meta.url)), '../src/CardHero.tsx')

export function smallWordsOf(path: string): ReadonlySet<string> {
  const file = ts.createSourceFile(path, readFileSync(path, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  for (const statement of file.statements) {
    if (!ts.isVariableStatement(statement)) continue
    for (const decl of statement.declarationList.declarations) {
      if (!ts.isIdentifier(decl.name) || decl.name.text !== 'SMALL_WORDS' || decl.initializer === undefined) continue
      const set = decl.initializer
      const array = ts.isNewExpression(set) && set.arguments?.[0] ? set.arguments[0] : undefined
      if (array === undefined || !ts.isArrayLiteralExpression(array)) throw new Error(`SMALL_WORDS in ${path} is not a Set of a literal array`)
      return new Set(array.elements.map((element) => {
        if (!ts.isStringLiteral(element)) throw new Error(`SMALL_WORDS in ${path} holds a non-literal word`)
        return element.text
      }))
    }
  }
  throw new Error(`SMALL_WORDS not found in ${path}`)
}

export const SMALL_WORDS: ReadonlySet<string> = smallWordsOf(CARD_HERO)

/** "I", "my", "me", "mine" as whole words, any case. Lookarounds bound the match by non-letters. */
const FIRST_PERSON = /(?<![\p{L}\p{N}_])(?:i|my|me|mine)(?![\p{L}\p{N}_])/giu

/** Quoted names that carry a first-person word and are not the app's own voice. `My Pricing` is the name of
 *  TCGplayer's page, a proper name the owner ruled to keep (wave 2, copy map row 10). Only the quoted phrase
 *  is exempt, in straight or curly quotes. The same words unquoted still count. The exemption is DESIGN.md's R17. */
const NAMED_EXEMPT: readonly string[] = ['"My Pricing"', '“My Pricing”']

/** The text with each named exemption blanked out. The browser sweep and the source scan both call this. */
export function scrubNamed(text: string): string {
  let scrubbed = text
  for (const quoted of NAMED_EXEMPT) scrubbed = scrubbed.split(quoted).join(' ')
  return scrubbed
}

/** The first-person words a string contains, lower-cased, in order, one entry per occurrence. */
export function voiceHits(text: string): string[] {
  return Array.from(scrubNamed(text).matchAll(FIRST_PERSON), (match) => match[0].toLowerCase())
}

/** A full sentence: the trimmed text ends in . ? or ! (a closing quote or bracket may follow). Only a heading
 *  (h2, h3) or a title may be a sentence; a control or a page title (h1) is a label whatever its ending. */
export function isSentence(text: string): boolean {
  return /[.?!]["'”’)\]]*$/.test(text.trim())
}

/** A spoken accessible name of two or more sentences (`Order: High to low. Press to reverse.`). It is read aloud,
 *  not drawn as a label, so the casing rule does not read it. A one-sentence name is still read. */
export function isSpokenSentences(text: string): boolean {
  return /[.?!]["'”’)\]]*\s+\S/.test(text.trim())
}

/** The label with each typed value (a `data-typed` descendant's text) taken out. The rest is checked. A label that is
 *  only a typed value is left empty, and an empty label has nothing to check. */
export function stripTyped(text: string, typed: readonly string[]): string {
  let rest = text
  for (const value of typed) {
    // A WHOLE TOKEN ONLY: a letter or digit on either side keeps the match inside a longer word (`in` in `Waiting`).
    // THE PLACEHOLDER IS A CAPITALIZED WORD (`X`), so the words around a typed name grade as they would with a name there:
    // `Another Place in <box>` passes and `another place in <box>` fails. A label that is only typed values leaves nothing.
    if (value !== '') rest = rest.replace(new RegExp(`(?<![\\p{L}\\p{N}])${value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![\\p{L}\\p{N}])`, 'gu'), ' X ')
  }
  const out = rest.replace(/\s+/g, ' ').trim()
  return out.split(' ').every((word) => word === 'X') ? '' : out
}

/** The labels a control draws: every line that carries a letter, is not a key cap alone, and is not a sentence. A tile's
 *  figure carries no letter (`12` over `matched free`), so it is not a label, and a key cap is not one (`H` over
 *  `Set hint`). Every other line is graded, so a second label in a control (`New` over `Set Hint`) is not skipped.
 *  A sentence line is a description (`Tap a box to read every card in it.`) and is not graded. When every lettered
 *  line is a sentence, the first one is graded, so a one-line sentence control (`Cards to pull.`) is still checked.
 *  Empty when no line carries a letter, which makes the control a spoken name (its accessible name is read instead). */
export function labelsOf(lines: readonly string[], keyCaps: readonly string[]): string[] {
  const lettered = lines
    .map((line) => line.replace(/\s+/g, ' ').trim())
    .filter((text) => text !== '' && /\p{L}/u.test(text) && !keyCaps.includes(text))
  // A FULL SENTENCE IS A LINE THAT ENDS IN . ? OR ! AND HAS FIVE WORDS OR MORE. A shorter line ending in a period is a label
  // (`Cards to pull.`), so it is kept beside a second label. The five-word floor is a ceiling: a four-word caption is graded.
  const labels = lettered.filter((text) => !(isSentence(text) && text.split(' ').length >= 5))
  return labels.length > 0 ? labels : lettered.slice(0, 1)
}

/** Units that may follow a number unchanged: `10 ml`, `1 month`. A count noun such as `cards` is a word. */
export const UNIT_WORDS: ReadonlySet<string> = new Set([
  'ml', 'mm', 'cm', 'kg', 'g', 'oz', 'px', 'x',
  'second', 'seconds', 'minute', 'minutes', 'hour', 'hours',
  'day', 'days', 'week', 'weeks', 'month', 'months', 'year', 'years',
])

/** A token that is a number: `10`, `$184`, or a range of numbers (`1-2`). A hyphenated token with a word in it (`3-day`) is not,
 *  so its word part is read as a word. */
function isNumberToken(token: string): boolean {
  if (!/\d/.test(token)) return false
  if (!token.includes('-')) return true
  return token.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu, '').split('-').every((part) => !/\p{L}/u.test(part))
}

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
    // A token with a digit is a number (`10`, `$184`), unless it is hyphenated (`3-day`): a hyphenated compound is a word,
    // so its digit part is skipped and its word part is read below.
    if (isNumberToken(token)) {
      afterNumber = true
      return
    }
    const wasAfterNumber = afterNumber
    afterNumber = false
    const core = token.replace(/^[^\p{L}\p{N}]+/u, '').replace(/[^\p{L}\p{N}]+$/u, '')
    if (core === '') return
    if (wasAfterNumber && UNIT_WORDS.has(core.toLowerCase())) return

    const parts = core.split('-').map((part) => part.replace(/^[^\p{L}\p{N}]+/u, '')).filter((part) => part !== '')
    if (parts.length > 1) {
      for (const part of parts) {
        if (/\d/.test(part)) continue
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

/** A stat's label, graded by whether the stat is a press. `press` is true for a figure that is a button (the Review band
 *  tiles), and false for a caption under a figure (`copies owed`, `12 captured`, `to pick`), which is prose and not read.
 */
export function statProblems(text: string, press: boolean): string[] {
  return press ? casingProblems(text) : []
}

/** A tile's lead, graded as a sentence: the first word is capitalized and no later word is Title Case (`Every Card Is Priced`
 *  fails; `Every card is priced` passes). A word in capitals (`SKU`) or with a capital inside (`TCGplayer`) is a name, not read. */
export function sentenceProblems(text: string): string[] {
  const problems: string[] = []
  const words = text.trim().split(/\s+/).filter((word) => word !== '')
  words.forEach((word, index) => {
    const core = word.replace(/^[^\p{L}]+|[^\p{L}]+$/gu, '')
    if (core === '') return
    if (index === 0 && /^\p{Ll}/u.test(core)) problems.push(`"${core}" should be capitalized`)
    if (index > 0 && /^\p{Lu}\p{Ll}+$/u.test(core)) problems.push(`"${core}" should be lowercase in a sentence`)
  })
  return problems
}

/** A spoken name's value clause: a trailing comma clause that starts with a number (`Filters, 1 on`). The clause says the
 *  control's state, not a label word, so it is not graded, the way a screen reader's count clause is not drawn (`.bn-sr`). */
export function stripValueClause(text: string): string {
  return text.replace(/,\s*\d+\s+on$/, '')
}

/** A spoken name's Title Case problems, with its value clause left out (`Filters, 1 on` is the name of `Filters`, with 1 on). */
export function spokenNameProblems(text: string): string[] {
  return casingProblems(stripValueClause(text))
}

// UNENFORCED: a checkbox or radio label that is a sentence but Title Case passes here; no sentence grade is added for it.
/** A field label, graded by the control it names. A checkbox or radio label is an option sentence (`Split in two files at the
 *  cut-off`), which is prose and is not read. A text, search or select field's label takes Title Case. `control` is the input
 *  type the label names (`text`, `search`, `checkbox`, `radio`), `select` for a select, or '' when no control is named. */
export function fieldLabelProblems(text: string, control: string): string[] {
  return control === 'checkbox' || control === 'radio' ? [] : casingProblems(text)
}
