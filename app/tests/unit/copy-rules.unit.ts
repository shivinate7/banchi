// Protects: the first-person and Title Case rules that the copy sweep applies are themselves right, and every reason label and review question headline is free of "I", "my", "me" and "mine" (R4, R4a).
// Governs: DESIGN.md "Copy rules" (R4, R4a, R5), D173
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { test, expect } from './unit'
import { REASON_LABELS, RETIRED_REASON_LABELS } from '../../src/reasons'
import { casingProblems, isSentence, voiceHits } from '../copyRules'
import { recordFromSource } from '../copySource'

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
