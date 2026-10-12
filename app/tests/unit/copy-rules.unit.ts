// Protects: the first-person and Title Case rules that the copy sweep applies are themselves right, and every reason label and review question headline is free of "I", "my", "me" and "mine" (R4, R4a).
// Governs: DESIGN.md "Copy rules" (R4, R4a, R5), D173
import { readFileSync, readdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from './unit'
import { REASON_LABELS, RETIRED_REASON_LABELS } from '../../src/reasons'
import { casingProblems, isSentence, isSpokenSentences, labelsOf, stripTyped, voiceHits } from '../copyRules'
import { attrText, firstPersonInSource, jsxOpeningsIn, recordFromSource } from '../copySource'

const HERE = dirname(fileURLToPath(import.meta.url))
const REVIEW_QUEUE = resolve(HERE, '..', '..', 'src', 'ReviewQueue.tsx')

test('voice: "I", "my", "me" and "mine" match as whole words, in any case', () => {
  expect(voiceHits('Under my price')).toEqual(['my'])
  expect(voiceHits('I already sent it')).toEqual(['i'])
  expect(voiceHits("I'm done")).toEqual(['i'])
  expect(voiceHits('Tell me when market is above')).toEqual(['me'])
  expect(voiceHits('Mine, not yours')).toEqual(['mine'])
  expect(voiceHits('ME AND MY BOX')).toEqual(['me', 'my'])
})

test('voice: words that only contain those letters do not match', () => {
  expect(voiceHits('Inventory, Mineral, Remember, Medicine, Pricing, Dimension')).toEqual([])
  expect(voiceHits("Don't stop, it's yours")).toEqual([])
  expect(voiceHits('Set II and box 9')).toEqual([])
})

test('casing: Chicago Title Case passes, and each small word in the middle must be lower-case', () => {
  expect(casingProblems('Price the Answers')).toEqual([])
  expect(casingProblems('Cards to Pull')).toEqual([])
  expect(casingProblems('Go to Pricing')).toEqual([])
  expect(casingProblems('Set Up')).toEqual([])
  expect(casingProblems('Back To')).toEqual([])
  expect(casingProblems('Pull 12 Cards')).toEqual([])
  expect(casingProblems('Pick N')).toEqual([])
  expect(casingProblems('Sold In Box')).toEqual(['"In" should be lowercase'])
  expect(casingProblems('Show all')).toEqual(['"all" should be capitalized'])
  expect(casingProblems('Back to')).toEqual(['"to" should be capitalized'])
  expect(casingProblems('Refresh now on Pricing')).toEqual(['"now" should be capitalized'])
  // The review tile's proposed wording: `at` is a small word, so Chicago lowercases it mid-title.
  expect(casingProblems('Not Looked At Yet')).toEqual(['"At" should be lowercase'])
  expect(casingProblems('Not Looked at Yet')).toEqual([])
})

test('casing: a hyphenated word capitalizes each part, and a number or unit is not a word', () => {
  expect(casingProblems('Pre-Sorted Box')).toEqual([])
  expect(casingProblems('Pre-sorted Box')).toEqual(['"Pre-sorted": "sorted" should be capitalized'])
  expect(casingProblems('Box 9 Ready at 10 ml Left')).toEqual([])
  expect(casingProblems('Box 9 Ready at 10 ml')).toEqual([])
  expect(casingProblems('$184 Listed')).toEqual([])
  expect(casingProblems('1 month')).toEqual([])
  expect(casingProblems('#17 Volcanion Pick 1 of 1')).toEqual([])
  expect(casingProblems('0 matched free')).toEqual(['"matched" should be capitalized', '"free" should be capitalized'])
  expect(casingProblems('Pull 12 cards')).toEqual(['"cards" should be capitalized'])
})

test('sentence: a closing period or question mark marks a sentence, which the sweep reads only under a heading or title', () => {
  expect(isSentence('Nothing captured yet.')).toBe(true)
  expect(isSentence('Which listing is this card?')).toBe(true)
  expect(isSentence('Cards to pull')).toBe(false)
})

/* THE SPOKEN NAME (copy map row 58). A two-sentence accessible name is read aloud, so the casing rule skips it; a
 * one-sentence label with bad casing still fails. */
test('typed name: the marked text comes out of the label, and the rest is still checked', () => {
  expect(stripTyped('SV commons card', ['SV commons'])).toBe('X card')
  expect(casingProblems(stripTyped('SV commons card', ['SV commons']))).not.toEqual([])
  expect(stripTyped('SV commons', ['SV commons'])).toBe('')
  expect(casingProblems(stripTyped('SV Commons Card', ['SV commons']))).toEqual([])
})

test('spoken name: two sentences pass unread, and a one-sentence label with bad casing still fails', () => {
  expect(isSpokenSentences('Order: High to low. Press to reverse.')).toBe(true)
  expect(isSpokenSentences('Cards to pull.')).toBe(false)
  expect(casingProblems('Show all cards.')).not.toEqual([])
  expect(isSpokenSentences('Show all cards.')).toBe(false)
})

test('label: a closing period on a control label does not skip the casing check', () => {
  expect(casingProblems('Cards to pull.')).not.toEqual([])
  expect(casingProblems('Which Card Is This?')).toEqual([])
  expect(casingProblems('Under Your Price.')).toEqual([])
})

/* THE PREPOSITION (Chicago lowercases every preposition in the middle of a title). `with` is the one the label corpus uses
 * mid-title (`Lowest with Shipping`); the capitalized form is the defect. */
test('casing: a preposition in the middle of a title stays lower-case, so "with" passes lower and fails capitalized', () => {
  expect(casingProblems('Lowest with Shipping')).toEqual([])
  expect(casingProblems('Lowest With Shipping')).toEqual(['"With" should be lowercase'])
})

/* THE LABEL LINES. A tile draws its figure above its label, and a row draws its key cap before its name: neither is a
 * label. Every other lettered line that is not a sentence is a label and is graded, so a second label is not skipped. */
test('label lines: a figure and a key cap are not labels; the lettered lines that are, are', () => {
  expect(labelsOf(['12', 'matched free', '›'], [])).toEqual(['matched free'])
  expect(labelsOf(['H', 'Set hint', 'Needed'], ['H'])).toEqual(['Set hint', 'Needed'])
})

/* THE BYPASS. A control with two label lines (`New` over `Set hint`) must grade both: the second line's casing problem is
 * found. On the old first-line rule (`labelOf`, now removed) only `New` was graded, so this case went green on a lower-case label. */
test('label lines: every label line is graded, so a lower-case second label is found and a Title Case one passes', () => {
  expect(labelsOf(['New', 'Set hint'], []).flatMap((label) => casingProblems(label))).toEqual(['"hint" should be capitalized'])
  expect(labelsOf(['New', 'Set Hint'], []).flatMap((label) => casingProblems(label))).toEqual([])
})

/* A CAPTION IS NOT A LABEL. The description under a title is a sentence, so it is not graded; the title still is. */
test('label lines: a description sentence under a title is not graded, and a one-sentence control is still graded', () => {
  expect(labelsOf(['Read a box', 'Tap a box to read every card in it.'], [])).toEqual(['Read a box'])
  expect(labelsOf(['Cards to pull.'], [])).toEqual(['Cards to pull.'])
  /* A SHORT LINE THAT ENDS IN A PERIOD IS A LABEL, NOT A SENTENCE: it is kept beside a second label. */
  expect(labelsOf(['Cards to pull.', 'Set Hint'], [])).toEqual(['Cards to pull.', 'Set Hint'])
  expect(labelsOf(['Tap a box to read every card in it.', 'Set Hint'], [])).toEqual(['Set Hint'])
})

test('small words: the short Chicago prepositions stay lower-case in the middle of a title', () => {
  expect(casingProblems('Learn about Pricing')).toEqual([])
  expect(casingProblems('Learn About Pricing')).toEqual(['"About" should be lowercase'])
  expect(casingProblems('Costs under Ten')).toEqual([])
  expect(casingProblems('Costs Under Ten')).toEqual(['"Under" should be lowercase'])
})

test('typed name is a placeholder word: the words around it grade as they would with a name there', () => {
  expect(casingProblems(stripTyped('Another Place in SV commons', ['SV commons']))).toEqual([])
  expect(casingProblems(stripTyped('another place in SV commons', ['SV commons']))).toEqual(['"another" should be capitalized', '"place" should be capitalized'])
})

test('typed value: only a whole token comes out of a label, so a word that contains it stays whole', () => {
  expect(stripTyped('Waiting in Line', ['in'])).toBe('Waiting X Line')
  expect(stripTyped('Waiting in Line', ['in'])).not.toMatch(/Wait\s+g/)
})

test('label lines: a control with only key caps, or only a figure, has no label, so its accessible name is read instead', () => {
  expect(labelsOf(['⌘K'], ['⌘K'])).toEqual([])
  expect(labelsOf(['12'], [])).toEqual([])
})

/* THE NINE STRINGS THAT WENT UNREAD ON ee5b389a. Each one must be a casing problem under the rule, and a caption or an
 * instruction sentence must not be one. The state reads in `copy-checks.spec.ts` show each string on its own screen. */
test('the nine casing misses: each label is a Title Case problem, and a caption is prose the rule does not read', () => {
  for (const label of ['Set hint', 'Price the answers', 'Run another box', 'matched free', 'Lowest with shipping', 'Can be sent', 'Listed now', 'Your price', 'Take 6 copies back', 'Send all 3 SKUs to TCGplayer']) {
    expect(casingProblems(label), label).not.toEqual([])
  }
  expect(isSentence('Started at 9:15 PM. The result shows here when TCGplayer answers.')).toBe(true)
  expect(isSpokenSentences('Order: High to low. Press to reverse.')).toBe(true)
})

test('voice: the quoted page name is exempt in voiceHits, and the unquoted words are not (browser path)', () => {
  expect(voiceHits('Drop the \u201cMy Pricing\u201d export here')).toEqual([])
  expect(voiceHits('Drop the "My Pricing" export here')).toEqual([])
  expect(voiceHits('Drop the My Pricing export here')).toEqual(['my'])
})

/* A SOURCE SCANNER MUST RESPECT STRINGS. These fixtures put a comment opener inside a string, a
 * multi-line template literal, and a lone quote in JSX text, each where a naive line scan would
 * mis-read the rest of the file. The parser must still return exactly the record's values. */
test('source: the record reader respects comment openers in strings, template literals and lone quotes', () => {
  const source = [
    "// const QUESTIONS = { wrong: 'not this one' }",
    '/* a block comment naming QUESTIONS */',
    'const note = `a template',
    '  running on, with // and /* inside`',
    'const QUESTIONS: Readonly<Record<string, string>> = {',
    "  alpha: 'Is this // the card?',",
    "  beta: 'Keep /* the open marker',",
    '  gamma: "Don\'t stop",',
    '  delta: `Template // inside`,',
    '}',
    'export const view = <p>Don\'t</p>',
  ].join('\n')
  expect(recordFromSource(source, 'QUESTIONS')).toEqual({
    alpha: 'Is this // the card?',
    beta: 'Keep /* the open marker',
    gamma: "Don't stop",
    delta: 'Template // inside',
  })
})

test('source: a value that is not a plain string throws rather than being skipped', () => {
  const source = "const QUESTIONS = { alpha: 'a', beta: `b ${'c'}` }"
  expect(() => recordFromSource(source, 'QUESTIONS')).toThrow(/not a plain string/)
})

test('labels: every reason label on screen is free of "I", "my", "me" and "mine"', () => {
  const offenders = [
    ...Object.entries(REASON_LABELS).map(([code, label]) => ({ code, label, words: voiceHits(label) })),
    ...Object.entries(RETIRED_REASON_LABELS).map(([code, label]) => ({ code, label, words: voiceHits(label) })),
  ].filter((one) => one.words.length > 0)
  const problems = offenders.map((one) => `${one.code}: "${one.label}" has ${one.words.map((w) => `"${w}"`).join(', ')}`)
  expect(problems, problems.join('\n')).toEqual([])
})

test('labels: every review question headline is free of "I", "my", "me" and "mine"', () => {
  const questions = recordFromSource(readFileSync(REVIEW_QUEUE, 'utf8'), 'QUESTIONS')
  expect(Object.keys(questions).length, 'the QUESTIONS record read as too short to be the real one').toBeGreaterThan(15)
  const problems = Object.entries(questions).flatMap(([code, headline]) =>
    voiceHits(headline).map((word) => `${code}: "${headline}" has "${word}"`),
  )
  expect(problems, problems.join('\n')).toEqual([])
})

/* THE INPUT CHECK (A12). One line per offender, `file:line what`. A spread `{...props}` can supply the
 * attribute, so the element is skipped, and a computed type is skipped too. It reads every `.tsx` under
 * app/src and app/src/kit. (A11 placeholders and A4 img sizes are NOT added: each has more than 30
 * offenders on the wave-2 head, so they are reported, not gated.) */
const RAW_INPUT_TYPES: ReadonlySet<string> = new Set(['', 'text', 'search', 'email', 'tel', 'url', 'number', 'password'])

function inputProblems(source: string, file: string): string[] {
  const out: string[] = []
  for (const element of jsxOpeningsIn(source, file)) {
    if (element.spread || element.tag !== 'input') continue
    const type = element.attrs.get('type')
    const kind = type === undefined ? '' : attrText(type)
    const named = element.attrs.has('name') || element.attrs.has('autocomplete') || element.attrs.has('autoComplete')
    if (kind !== null && RAW_INPUT_TYPES.has(kind) && !named) {
      out.push(`${file}:${element.line} <input> type "${kind}" has no name or autocomplete`)
    }
  }
  return out
}

function screenSourceFiles(): string[] {
  const src = resolve(HERE, '..', '..', 'src')
  return [
    ...readdirSync(src).filter((f) => f.endsWith('.tsx')).map((f) => resolve(src, f)),
    ...readdirSync(resolve(src, 'kit')).filter((f) => f.endsWith('.tsx')).map((f) => resolve(src, 'kit', f)),
  ]
}

test('A12: every raw text input carries a name or an autocomplete attribute', () => {
  const problems = screenSourceFiles().flatMap((file) => inputProblems(readFileSync(file, 'utf8'), file.slice(resolve(HERE, '..', '..', 'src').length - 3)))
  expect(problems, problems.join('\n')).toEqual([])
})

test('A12: the input rule reads a raw input, skips typed controls and spreads, and accepts autoComplete', () => {
  const source = [
    '<input placeholder="Search cards…" />',
    '<input placeholder="Search cards…" name="q" />',
    '<input type="checkbox" />',
    '<input {...props} />',
    '<input type="text" autoComplete="off" />',
    '<input type="text" />',
  ].join('\n')
  expect(inputProblems(source, 'View.tsx')).toEqual([
    'View.tsx:1 <input> type "" has no name or autocomplete',
    'View.tsx:6 <input> type "text" has no name or autocomplete',
  ])
})

/* THE NAMED EXEMPTION (copy map row 10). The quoted page name is exempt; the same words unquoted are not. */
test('source scan: the quoted TCGplayer page name is exempt, and the unquoted words still go red', () => {
  const source = [
    'export const View = () => (',
    '  <button title={\'Drop the "My Pricing" export here\'}>x</button>',
    '  <button title="Drop the \u201cMy Pricing\u201d export here">x</button>',
    '  <button title="Drop the My Pricing export here">x</button>',
    ')',
  ].join('\n')
  const found = firstPersonInSource(source, 'View.tsx').map((one) => `${one.line} ${one.where}: ${one.words.join(',')}`)
  expect(found).toEqual(['4 attribute title: My'])
})

/* THE TYPED BOX NAME IS READ AS A LABEL HERE (copy map row 31). The data-typed marker that exempts it lives in the
 * DOM, so the sweep skips it there; this rule still reads the words, and the same casing in a label goes red. */
test('casing: the box name is a label to this rule, and only the data-typed marker exempts it in the sweep', () => {
  expect(casingProblems('sv commons')).not.toEqual([])
  expect(casingProblems('SV commons')).not.toEqual([])
  expect(casingProblems('Export read')).not.toEqual([])
})

/* THE SOURCE SCAN RESPECTS STRINGS AND COMMENTS. A comment opener inside a string, a multi-line template
 * literal and a lone apostrophe in JSX text each sit where a line scan would mis-read the rest. Only the
 * rendered positions are read: the comment and the template body below must not produce a finding. */
test('source scan: comments, template bodies and lone apostrophes give no finding', () => {
  const source = [
    "// a comment: label: 'my' and I",
    '/* block: <p>I already sent it</p> */',
    'const note = `a template',
    "  spanning lines with // and label: 'me' inside`",
    "const path = '/* not a comment, but my path */'",
    'export const View = () => (',
    '  <p title="Don\'t stop">Don\'t stop, it\'s fine</p>',
    "  <span label='Pick a box'>Pick it</span>",
    ')',
  ].join('\n')
  expect(firstPersonInSource(source, 'View.tsx')).toEqual([])
})

test('source scan: rendered text, rendered props and rendered object keys are read, with their lines', () => {
  const source = [
    'const options = [',
    "  { value: 'cut', label: 'Under my price' },",
    '  { value: `m`, label: `Keep me on it` },',
    ']',
    'export const View = () => (',
    '  <p>Kept // my note</p>',
    '  <dt>I already sent it</dt>',
    '  <input placeholder="Tell me when" />',
    "  <span>{ok ? 'Mine, mine' : 'Pick a box'}</span>",
    ')',
  ].join('\n')
  const found = firstPersonInSource(source, 'View.tsx').map((one) => `${one.line} ${one.where}: ${one.text}`)
  expect(found).toEqual([
    '2 key label: Under my price',
    '3 key label: Keep me on it',
    '6 JSX text: Kept // my note',
    '7 JSX text: I already sent it',
    '8 attribute placeholder: Tell me when',
    '9 JSX expression: Mine, mine',
  ])
})

/* THE RENDERED COPY OF EVERY SCREEN COMPONENT. Gallery and Codes are skipped. Every other .tsx under
 * app/src and app/src/kit is read; each hit is a finding the sheet pass owes. */
test('source scan: no rendered string in app/src carries "I", "my", "me" or "mine"', () => {
  const src = resolve(HERE, '..', '..', 'src')
  const files = [
    ...readdirSync(src).filter((f) => f.endsWith('.tsx')).map((f) => resolve(src, f)),
    ...readdirSync(resolve(src, 'kit')).filter((f) => f.endsWith('.tsx')).map((f) => resolve(src, 'kit', f)),
  ].filter((file) => !/(Gallery|Codes)\.tsx$/.test(file))
  expect(files.length, 'the source list read as too short').toBeGreaterThan(50)
  const problems = files.flatMap((file) =>
    firstPersonInSource(readFileSync(file, 'utf8'), file.slice(src.length - 3)).map(
      (one) => `${one.file}:${one.line} [${one.where}] "${one.text}" has ${one.words.map((w) => `"${w}"`).join(', ')}`,
    ),
  )
  expect(problems, problems.join('\n')).toEqual([])
})
