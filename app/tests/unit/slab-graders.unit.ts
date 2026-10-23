// Protects: The grader list the Slabs screen offers is the one the server accepts, in the same order.
// Governs: D320
import { execFileSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { expect, test } from './unit'
import { SLAB_GRADERS } from '../../src/slabGraders'

/* NO ROUTE SENDS THE GRADER LIST YET, so the screen carries a copy (`my-slabs.md` 4.8) and this
 * is the check that the copy has not drifted. Python's list is read by running Python, the
 * repo's own when it has one, and never by reading its source: a regex over `store/slabs.py`
 * passes when the dict is rebuilt in another shape. `GRADERS` is a dict, so `list()` is its keys
 * in insertion order: every name the route accepts (`psa`, `beckett`, `bgs`, `bvg`, `sgc`, `cgc`). */

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..', '..')
const VENV = resolve(ROOT, '.venv', 'bin', 'python')

function pythonGraders(): string[] {
  const out = execFileSync(existsSync(VENV) ? VENV : 'python3', ['-c', 'import json; from store import slabs; print(json.dumps(list(slabs.GRADERS)))'], {
    cwd: ROOT,
    encoding: 'utf8',
  })
  return JSON.parse(out) as string[]
}

test('the server names its graders, so the comparison below is not empty', () => {
  expect(pythonGraders().length, 'the Python list is nearly empty: the one-liner read the wrong thing').toBeGreaterThan(3)
})

test('the screen offers the graders store/slabs.GRADERS holds, in its order', () => {
  expect([...SLAB_GRADERS]).toEqual(pythonGraders())
})

test('a grader appears once in the list the screen offers', () => {
  expect(new Set(SLAB_GRADERS).size).toBe(SLAB_GRADERS.length)
})
