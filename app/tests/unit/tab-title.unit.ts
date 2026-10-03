// Protects: Every screen's tab title is one fixed string, the screen's name in lowercase, and the Fulfiller's carries no brand.
import { execFileSync } from 'node:child_process'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from './unit'
import { tabTitle } from '../../src/tabTitle'

/* THE FUNCTION HALF OF THE TAB TITLE, over every `ROUTES` entry, read from `ROUTES` by the same
 * reader the static check uses (`kit-adoption.mjs --routes`). A route added tomorrow is covered
 * with no edit here. The browser half, that the shell's effect stamps `document.title` with this
 * function's answer, is one case in `scaffold.spec.ts`. The expected string is spelled out here
 * and never read from `tabTitle`: a test that reads the value it checks passes when it is wrong. */

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', '..')

type Row = { readonly path: string; readonly label: string; readonly title: string | null; readonly persona: string | null }

const ROWS = JSON.parse(
  execFileSync(process.execPath, [resolve(ROOT, 'scripts/kit-adoption.mjs'), '--routes'], { encoding: 'utf8' }),
) as Row[]

test('the route table is read', () => {
  expect(ROWS.length, 'kit-adoption --routes returned almost nothing').toBeGreaterThan(3)
})

for (const row of ROWS) {
  test(`${row.path} has the fixed tab title`, () => {
    const name = (row.title ?? row.label).toLowerCase()
    const want = row.persona === 'fulfiller' ? name : `番地 ${name}`
    expect(tabTitle({ label: row.label, title: row.title, persona: row.persona ?? undefined })).toBe(want)
  })
}

test('an unknown route reads as not found, with the brand', () => {
  expect(tabTitle(undefined)).toBe('番地 not found')
})
