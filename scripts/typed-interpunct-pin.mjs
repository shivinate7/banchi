// Pin scripts/typed-interpunct.json's ratchet ceiling from a real measurement.
//
//     node scripts/typed-interpunct-pin.mjs --pin
//
// Mirrors scripts/copy-budget.mjs's own discipline (D194), for the ratchet
// scripts/docs-audit.py's `typed interpunct` row asserts (D217):
// the ROW only ever READS scripts/typed-interpunct.json — D18 forbids it writing, since it
// runs on the commit path — and this generator is the one thing that may, run by a person
// choosing, on purpose, to accept today's count as the new ceiling. Never pin quietly:
// `git diff scripts/typed-interpunct.json` is the receipt, the same sentence
// `copy-budget.mjs` prints for the same reason.
//
// THE MEASUREMENT IS THE SAME EXTRACTION THE ROW READS: `scripts/user-strings.mjs`, run with
// `--join-literals --include-code-attr` (`TYPED_INTERPUNCT_EXTRACT_ARGS` in
// scripts/docs-audit.py — kept in step with this file's own ARGS constant below by naming
// both here and there, since a Node script cannot import a Python constant without a second
// subprocess hop this script has no other reason to pay for).
//
// THE MATCH ITSELF — U+00B7 (middle dot) and U+2022 (bullet) — is a two-code-point regex
// kept duplicated in scripts/docs-audit.py's `_INTERPUNCT_RE` rather than shared. That is a
// deliberate difference from D196's word list, which stays in one file (docs-audit.py) alone
// because it is a large, changing, semantic policy a session actually edits. This is two
// fixed code points from one ruling; the duplication cannot drift the way a growing list
// could, and importing a Python module from Node (or shelling out to Python from here) would
// cost more machinery than the two-character class it would save.
//
// What it writes: scripts/typed-interpunct.json, `{"count": <measured>}` — no slack added,
// for the same reason copy-budget.mjs's own header gives: slack is how a ratchet leaks.
import { spawnSync } from 'node:child_process'
import { writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const EXTRACTOR = resolve(ROOT, 'scripts', 'user-strings.mjs')
const PIN_PATH = resolve(ROOT, 'scripts', 'typed-interpunct.json')

// Kept identical, in the same order, to scripts/docs-audit.py's `TYPED_INTERPUNCT_EXTRACT_ARGS`.
const ARGS = ['--join-literals', '--include-code-attr']

// U+00B7, U+2022 — see the header. Matches scripts/docs-audit.py's `_INTERPUNCT_RE` exactly.
const INTERPUNCT_RE = /[·•]/

function main() {
  const args = process.argv.slice(2)
  if (!args.includes('--pin')) {
    console.error('usage: node scripts/typed-interpunct-pin.mjs --pin')
    process.exit(2)
  }

  console.log('typed-interpunct-pin: re-measuring app/src via scripts/user-strings.mjs ...')
  const result = spawnSync('node', [EXTRACTOR, ...ARGS], { cwd: ROOT, encoding: 'utf8' })

  if (result.error) {
    console.error(`typed-interpunct-pin: could not run the extractor: ${result.error.message}`)
    process.exit(1)
  }
  if (result.status !== 0) {
    console.error(
      `typed-interpunct-pin: the extractor exited ${result.status} — nothing was written.\n${result.stderr ?? ''}`,
    )
    process.exit(result.status ?? 1)
  }

  let strings
  try {
    strings = JSON.parse(result.stdout)
  } catch (err) {
    console.error(`typed-interpunct-pin: could not parse the extractor's output: ${err.message}`)
    process.exit(1)
  }

  const count = strings.filter((item) => INTERPUNCT_RE.test(String(item.text))).length
  writeFileSync(PIN_PATH, `${JSON.stringify({ count }, null, 2)}\n`)
  console.log(
    `typed-interpunct-pin: pinned at ${count}. \`git diff scripts/typed-interpunct.json\` shows what moved.`,
  )
}

main()
