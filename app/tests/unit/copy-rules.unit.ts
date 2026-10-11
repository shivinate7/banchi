// Protects: the first-person and Title Case rules that the copy sweep applies are themselves right, and every reason label and review question headline is free of "I", "my", "me" and "mine" (R4, R4a).
// Governs: DESIGN.md "Copy rules" (R4, R4a, R5), D173
import { readFileSync, readdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from './unit'
import { REASON_LABELS, RETIRED_REASON_LABELS } from '../../src/reasons'
import { casingProblems, isSentence, isTypedData, voiceHits } from '../copyRules'
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

test('sentence: a label ending in . ? or ! is a sentence, and is not checked for casing', () => {
  expect(isSentence('Under your price.')).toBe(true)
  expect(isSentence('Which card is this?')).toBe(true)
  expect(isSentence('Nothing here yet!')).toBe(true)
  expect(isSentence('Show All')).toBe(false)
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

/* THE TYPED-DATA EXEMPTION (copy map row 31). It is the exact text only, so a label with the same words in
 * another casing is still a label and still goes red. */
test('casing: the typed box name is exempt by exact text only, and a label that reuses its words is not', () => {
  expect(isTypedData('SV commons')).toBe(true)
  expect(isTypedData('Sv commons')).toBe(false)
  expect(isTypedData('sv commons')).toBe(false)
  expect(isTypedData('SV commons Pick')).toBe(false)
  expect(casingProblems('sv commons')).not.toEqual([])
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
