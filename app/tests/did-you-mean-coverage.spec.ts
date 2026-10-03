// Protects: Every screen that searches a list draws "Did you mean" on its zero-result state, so a new search cannot ship without it.
// Governs: D271
import { test, expect } from '@playwright/test'
import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

import { sealEveryTest } from './shell'
import { didYouMean } from '../src/kit/match'

sealEveryTest()

/* A screen file that runs the one matcher or the store's search (`matchQuery`, `filterByQuery`,
 * `useQueryFilter`, `useSearch(`) answers a typed query. Its zero-result state must carry the
 * hint (`didYouMean` on `EmptyState`, or `<DidYouMean>`). A file that is not a list search says
 * why here. Reads source only: no browser, no server. */
const SEARCHES = /\b(matchQuery|filterByQuery|useQueryFilter)\(|\buseSearch\(/u
const HINT = /\b(didYouMean|DidYouMean)\b/u

const NOT_A_LIST_SEARCH: Readonly<Record<string, string>> = {
  'App.tsx': 'the command palette and the shortcut sheet pick an action, not a list of named things',
  'CaptureScreen.tsx': 'the box picker is a typeahead whose choices are always on screen',
  'InventorySets.tsx': 'it holds a query seeded from Inventory and has no search field of its own',
  'Inventory.tsx': "the copies panel reads the search BoxBrowse draws; the zero state is BoxBrowse's",
}

export function unhinted(files: Readonly<Record<string, string>>): string[] {
  return Object.entries(files)
    .filter(([name, text]) => SEARCHES.test(text) && !HINT.test(text) && !(name in NOT_A_LIST_SEARCH))
    .map(([name]) => name)
    .sort()
}

const SRC = join(fileURLToPath(new URL('.', import.meta.url)), '..', 'src')
const screens = Object.fromEntries(
  readdirSync(SRC)
    .filter((name) => name.endsWith('.tsx'))
    .map((name) => [name, readFileSync(join(SRC, name), 'utf8')]),
)

test('every searchable screen draws the Did you mean hint', () => {
  expect(unhinted(screens)).toEqual([])
})

test('the check goes red on a searchable screen without the hint', () => {
  expect(unhinted({ 'New.tsx': 'const hit = matchQuery(q, f)' })).toEqual(['New.tsx'])
  expect(unhinted({ 'New.tsx': 'const hit = matchQuery(q, f); <EmptyState didYouMean={x} />' })).toEqual([])
})

test('every exemption still names a file that searches', () => {
  for (const name of Object.keys(NOT_A_LIST_SEARCH)) expect(SEARCHES.test(screens[name] ?? ''), name).toBe(true)
})

test('the hint the screens draw is the kit matcher\'s answer', () => {
  expect(didYouMean('Rekenton', ['Renekton'])).toBe('Renekton')
})
