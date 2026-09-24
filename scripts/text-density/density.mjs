#!/usr/bin/env node
// The on-demand text-density reviewer (D-text-shape-checks, the third piece of the owner's
// 2026-09-23 ruling: "kill ceilings ... use a different way ... I don't like keeping a
// stagnant static pin"). It prints a per-route word-density table. It writes nothing under
// version control (D18: nothing that writes may gate a commit, and this is not on the commit
// path at all — `make text-density`, never `make check` or `make design-check`). It writes
// one report to `.serve/text-density.json`, gitignored, the same shape `.serve/design-
// check.json` already uses for a run's own receipt.
//
//     node scripts/text-density/density.mjs [--width 1440] [--theme light] [--route /pricing]
//
// THIS TALKS TO THIS CHECKOUT'S OWN DEV SERVER, NEVER ANYTHING ELSE. `app/devPort.ts`'s
// `DEV_URL` is the one source every other tool in this repo (`playwright.config.ts`,
// `vite.config.ts`) already reads for the same reason: a hardcoded port or the published demo
// answers a DIFFERENT tree's code, or, on the primary checkout copied without its `.git`
// (the 2026-09-23 incident this repo's HAZARD note exists for), the owner's LIVE store. This
// script refuses to run unless it can reach that port — it does not fall back to :5173,
// :8000 or any other guess. `make dev` (or `make up`) must already be running.
//
// THE ROUTE ROSTER IS DISCOVERED, never typed. `node scripts/kit-adoption.mjs --routes` is
// the guards lane's own reader of `app/src/App.tsx`'s `ROUTES` table — the same discipline
// `app/tests/routes.ts:routesFromNav` argues for a browser sweep, applied here without a
// browser tab open yet to read a nav strip from.
//
// A "PROSE BLOCK" IS THE SAME RULER `app/tests/textShape.ts`'s repeated-fact check uses: a
// block element (the nearest non-inline ancestor of a text node) holding six or more visible
// words. One definition, so a session reading this tool's table and that check's findings is
// reading the same kind of thing both times.
import { execFileSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(HERE, '..', '..')
const APP_DIR = resolve(ROOT, 'app')

// `chromium` lives in `app/node_modules/@playwright/test` — this script is not itself under
// `app/`, so it resolves the module the way `scripts/build-lockup.mjs` resolves a browser
// dependency it does not have its own copy of: `createRequire` rooted at `app/package.json`.
const appRequire = createRequire(resolve(APP_DIR, 'package.json'))
const { chromium } = appRequire('@playwright/test')

function parseArgs(argv) {
  const out = { width: 1440, theme: 'light', route: null }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a === '--width') out.width = Number(argv[++i])
    else if (a === '--theme') out.theme = argv[++i]
    else if (a === '--route') out.route = argv[++i]
    else if (a === '--help' || a === '-h') {
      console.log('usage: node scripts/text-density/density.mjs [--width N] [--theme light|dark] [--route /path]')
      process.exit(0)
    }
  }
  return out
}

/** `app/devPort.ts`'s own derivation — `--experimental-strip-types` is how the rest of this
 *  repo's tooling already imports a `.ts` file from a plain Node script (`scripts/port-
 *  agreement.py`'s own `node_answers` does the identical thing, from Python). Importing it
 *  here, once, is the alternative to a second, hand-typed port formula that could drift from
 *  the real one — the exact failure `app/devPort.ts`'s own header spends most of a page on. */
async function devUrl() {
  const mod = await import(resolve(APP_DIR, 'devPort.ts'))
  return mod.DEV_URL
}

function discoverRoutes() {
  const out = execFileSync('node', [resolve(ROOT, 'scripts', 'kit-adoption.mjs'), '--routes'], {
    cwd: ROOT,
    encoding: 'utf8',
  })
  const routes = JSON.parse(out)
  return routes.map((r) => r.path)
}

// Runs INSIDE the page via `page.evaluate`. Self-contained — see `app/tests/textShape.ts`'s
// header for why a function passed to `page.evaluate` may not close over outer scope.
function measure() {
  const H = window.innerHeight
  function words(s) {
    return (s.match(/[A-Za-z0-9$][\w$.,'’%/-]*/g) || []).length
  }
  function visible(el) {
    for (let e = el; e; e = e.parentElement) {
      const s = getComputedStyle(e)
      if (s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0') return false
    }
    const r = el.getBoundingClientRect()
    return r.width > 0 && r.height > 0
  }
  function isSrOnly(el) {
    return !!el.closest('.bn-sr, .sr-only, [aria-hidden="true"]')
  }
  const main = document.querySelector('main') ?? document.body
  function blockOf(el) {
    let e = el
    while (e && e !== document.body) {
      const d = getComputedStyle(e).display
      if (!d.startsWith('inline') && d !== 'contents') return e
      e = e.parentElement
    }
    return document.body
  }
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
  const blocks = new Map()
  let total = 0
  let fold = 0
  let mainTotal = 0
  let mainFold = 0
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const t = (n.textContent || '').trim()
    if (!t) continue
    const p = n.parentElement
    if (!p || !visible(p) || isSrOnly(p)) continue
    const wc = words(t)
    if (!wc) continue
    const rr = n.parentElement.getBoundingClientRect()
    const inMain = main.contains(n)
    total += wc
    if (inMain) mainTotal += wc
    const above = rr.top < H && rr.bottom > 0
    if (above) {
      fold += wc
      if (inMain) mainFold += wc
    }
    const b = blockOf(p)
    const k = blocks.get(b) ?? { words: 0, text: '', tag: b.tagName.toLowerCase() }
    k.words += wc
    k.text += (k.text ? ' ' : '') + t
    blocks.set(b, k)
  }
  const list = [...blocks.values()]
  const prose = list.filter((b) => b.words >= 6)
  return {
    total,
    fold,
    mainTotal,
    mainFold,
    blocks: list.length,
    proseBlocks: prose.length,
    proseWords: prose.reduce((a, b) => a + b.words, 0),
    topProse: prose
      .sort((a, b) => b.words - a.words)
      .slice(0, 5)
      .map((b) => ({ words: b.words, sample: b.text.slice(0, 140) })),
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  const base = await devUrl()
  console.log(`text-density: targeting this checkout's own dev server at ${base}`)

  let probe
  try {
    probe = await fetch(base, { method: 'HEAD' })
  } catch (err) {
    console.error(
      `text-density: could not reach ${base} — is \`make dev\` (or \`make up\`) running in this checkout? (${err.message})`,
    )
    process.exit(1)
  }
  if (!probe.ok && probe.status !== 404) {
    console.error(`text-density: ${base} answered ${probe.status} — refusing to guess a fallback port.`)
    process.exit(1)
  }

  const routes = args.route ? [args.route] : discoverRoutes()
  const browser = await chromium.launch()
  const ctx = await browser.newContext({ viewport: { width: args.width, height: 900 } })
  await ctx.addInitScript((theme) => {
    try {
      localStorage.setItem('banchi.theme', theme)
    } catch {
      /* private window or blocked storage — the page still renders its default theme */
    }
  }, args.theme)
  const page = await ctx.newPage()

  const out = {}
  const rows = []
  for (const route of routes) {
    const hash = route === '/' ? '' : route
    await page.goto(`${base}/#${hash}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(800)
    const d = await page.evaluate(measure)
    out[route] = d
    rows.push({ route, total: d.total, main: d.mainTotal, fold: d.fold, prose: d.proseBlocks, proseWords: d.proseWords })
  }

  await ctx.close()
  await browser.close()

  rows.sort((a, b) => b.main - a.main)
  console.log('')
  console.log('route'.padEnd(16), 'main'.padStart(6), 'total'.padStart(6), 'fold'.padStart(6), 'prose'.padStart(6), 'proseWords'.padStart(11))
  for (const r of rows) {
    console.log(
      r.route.padEnd(16),
      String(r.main).padStart(6),
      String(r.total).padStart(6),
      String(r.fold).padStart(6),
      String(r.prose).padStart(6),
      String(r.proseWords).padStart(11),
    )
  }
  console.log('')
  console.log('main = words inside <main>. fold = words above the fold anywhere on the page.')
  console.log('prose = blocks with 6+ words (the same ruler app/tests/textShape.ts reads).')

  const outDir = resolve(ROOT, '.serve')
  mkdirSync(outDir, { recursive: true })
  const outPath = resolve(outDir, 'text-density.json')
  writeFileSync(outPath, `${JSON.stringify({ width: args.width, theme: args.theme, base, routes: out }, null, 2)}\n`)
  console.log(`\ntext-density: wrote ${outPath} (gitignored — a receipt for this run, not a pin).`)
}

main().catch((err) => {
  console.error('text-density: failed —', err.message)
  process.exit(1)
})
