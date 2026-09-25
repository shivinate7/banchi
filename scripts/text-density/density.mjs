#!/usr/bin/env node
// The on-demand text-density pass (D-text-shape-checks, the third piece of the owner's
// 2026-09-23 ruling: "kill ceilings ... use a different way ... I don't like keeping a
// stagnant static pin"). It prints a CUT TABLE: per route and width, the largest prose blocks
// with their word counts, the repeated sentences and facts, and the sentences over 25 words.
// It asserts nothing and is on no gate's path (`make text-density`, never `make check`), so
// D18 lets it write its one receipt, `.serve/text-density.json`, gitignored.
//
//     node scripts/text-density/density.mjs [--route '#/pricing'] [--top N] [--json]
//
// IT MEASURES THE SAME SCREENS, IN THE SAME STATE, AS THE TWO GATES. It does not open its own
// browser against a store. It runs `app/tests/text-shape.spec.ts` with `TEXT_DENSITY=1`, which
// sweeps every route through `app/tests/routeSweep.ts` (the populated fixture of
// `routeFixtures.ts`, at 1440 and 390, each screen read only once loaded) and writes each
// route's `textShape.ts:measureTextShape` result instead of asserting it. So a worktree with
// an empty store still reads a populated screen, and this table and the spec's failures are
// read off one measurement.
//
// THE REPORTER IS `line`, NAMED ON THE COMMAND LINE, which replaces the config's reporters.
// `app/design-check-reporter.ts` therefore never runs, and this pass never overwrites
// `.serve/design-check.json`, the suite's own verdict file.
//
// THE PORT IS `app/playwright.config.ts`'s own: it starts this checkout's Vite on the port
// `app/devPort.ts` derives (D43), or reuses the server already on it. Nothing here names a
// port, and every read the page sends is stubbed by `app/tests/shell.ts:sealEveryTest`, so no
// store is read, the owner's included.
import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync, rmSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..', '..')
const APP_DIR = resolve(ROOT, 'app')
const RECEIPT = resolve(ROOT, '.serve', 'text-density.json')

function parseArgs(argv) {
  const out = { route: null, top: 5, json: false }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a === '--route') out.route = argv[++i]
    else if (a === '--top') out.top = Number(argv[++i])
    else if (a === '--json') out.json = true
    else if (a === '--help' || a === '-h') {
      console.log("usage: node scripts/text-density/density.mjs [--route '#/pricing'] [--top N] [--json]")
      process.exit(0)
    } else {
      console.error(`text-density: unknown argument ${a}`)
      process.exit(2)
    }
  }
  return out
}

function measure() {
  if (existsSync(RECEIPT)) rmSync(RECEIPT)
  const run = spawnSync(
    'npx',
    ['playwright', 'test', 'tests/text-shape.spec.ts', '-g', 'repeats no sentence', '--workers=1', '--reporter=line'],
    { cwd: APP_DIR, env: { ...process.env, TEXT_DENSITY: '1' }, encoding: 'utf8' },
  )
  if (run.status !== 0 || !existsSync(RECEIPT)) {
    process.stderr.write(run.stdout ?? '')
    process.stderr.write(run.stderr ?? '')
    console.error(`text-density: the sweep did not finish (exit ${run.status}); no table to print.`)
    process.exit(1)
  }
  return JSON.parse(readFileSync(RECEIPT, 'utf8')).measured
}

function clip(text, n) {
  const flat = text.replace(/\s+/g, ' ').trim()
  return flat.length > n ? `${flat.slice(0, n - 1)}…` : flat
}

function printTable(measured, args) {
  const rows = args.route ? measured.filter((m) => m.route === args.route) : measured
  if (rows.length === 0) {
    console.error(`text-density: no route ${args.route} in the sweep.`)
    process.exit(1)
  }
  console.log('CUT TABLE — the largest prose blocks, then what repeats and what runs long.')
  console.log('A prose block is a block element with six or more visible words (textShape.ts).')
  console.log('Read each row on the screen itself before cutting. Nothing here is a verdict.\n')
  for (const m of rows) {
    console.log(`${m.route}  at ${m.width}  ${m.words} words in the view`)
    for (const p of m.prose.slice(0, args.top)) {
      console.log(`  ${String(p.words).padStart(4)}  ${clip(p.sample, 96)}`)
    }
    if (m.prose.length === 0) console.log('     -  no prose block')
    for (const r of m.repeatedSentences) console.log(`  REPEATS x${r.count}  "${clip(r.key, 80)}"`)
    for (const r of m.repeatedFacts) console.log(`  FACT x${r.count}  "${r.key}"`)
    for (const r of m.longSentences) console.log(`  LONG ${r.words}w  "${clip(r.sample, 80)}"`)
    for (const r of m.captionHeading) console.log(`  CAPTION ${r.overlap}%  "${clip(r.key, 80)}" under "${r.heading}"`)
    console.log('')
  }
  console.log(`text-density: receipt at ${RECEIPT} (gitignored, never a pin).`)
}

const args = parseArgs(process.argv.slice(2))
const measured = measure()
if (args.json) console.log(JSON.stringify(measured, null, 2))
else printTable(measured, args)
