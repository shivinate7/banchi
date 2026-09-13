#!/usr/bin/env node
/**
 * Extract every USER-VISIBLE string literal from app/src, and nothing else.
 *
 * WHY THIS EXISTS. The owner ruled 2026-09-13 that the front end must be minimal and never
 * explain mechanism on screen — no decision citation, no repository file path, no
 * pipeline-internal noun in anything a person reading the app actually sees. Enforcing that
 * needs a reader that knows the difference between a string a person reads and a string that
 * is merely IN the source — a code comment arguing about `D134`, a `request('/inventory/...')`
 * call, a `console.error` — none of which are on screen. A regex over raw text cannot tell
 * those apart; `scripts/docs-audit.py`'s own `check_raw_color` strips comments first for
 * exactly this reason and this problem is harder, because the false-positive surface is not
 * just comments but every non-visible string literal in a 31,000-line tree.
 *
 * SO THIS READS THE AST, the same way `scripts/screen-freshness.mjs` does and for the same
 * reason stated there: a hand-rolled matcher is a second opinion about what TypeScript means,
 * and this tree is thick with JSX, template literals and ternaries a regex reads wrong.
 *
 * WHAT COUNTS AS VISIBLE, and nothing else:
 *   - JSX text nodes (`<p>Like this</p>`)
 *   - string/template-literal values of JSX attributes named `title`, `aria-label`,
 *     `placeholder`, `label`, `alt`, or `body` — the last because `EmptyState`'s own text
 *     prop is not one of the other five and needs its own carve-out (`app/src/kit/index.tsx`)
 *   - a string/template literal used directly as a JSX child expression (`{'…'}`,
 *     `{cond ? 'a' : 'b'}`, `{`… ${x} …`}`), including through `??`, `&&`, `+` and
 *     parentheses — the shapes actually found in this tree (see ReviewQueue.tsx's ternaries,
 *     CaptureScreen.tsx's `+`-built sentences)
 *   - `title` / `body` / `action.label` passed to `toast(...)` (`app/src/kit/toast.tsx`) —
 *     the one kit call that is not a JSX attribute at all
 *
 * WHAT IS DELIBERATELY NOT READ: code comments (`/* … *\/`, `//`), `console.*` arguments,
 * `data-*` attributes, class names, import specifiers, and any string that is not reachable
 * through one of the four shapes above — including a string returned by an arbitrary
 * function and interpolated by reference (`{formatLabel(x)}`), which this cannot see without
 * tracing data flow the AST alone does not carry. That is a real gap and it is the reason the
 * auditor's own docstring calls the count a floor, not a census.
 *
 * `.tsx` files only, under `app/src` — `.ts` files in this tree render no JSX (confirmed:
 * every `toast(` call site outside a `.bak` file is in a `.tsx`), and `app/tests` is a
 * different tree entirely.
 *
 * Prints one JSON array to stdout: `[{file, line, text}, …]`, file relative to the repo root.
 * Never writes. `--self-test` is not here — the auditor's own `--self-test` drives this
 * script by shelling out to it over synthetic fixtures, the same split
 * `scripts/screenshot.mjs` and `scripts/docs-audit.py` already keep.
 */

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.dirname(HERE)
const APP_SRC = path.join(ROOT, 'app', 'src')

const TYPESCRIPT = path.join(ROOT, 'app', 'node_modules', 'typescript', 'lib', 'typescript.js')
if (!fs.existsSync(TYPESCRIPT)) {
  console.error(
    'user-strings: app/node_modules/typescript is missing, so nothing was read — which is ' +
      'not the same as nothing being wrong. Run `npm install` in app/ first.',
  )
  process.exit(1)
}
const ts = (await import(pathToFileURL(TYPESCRIPT).href)).default

// The five attribute names the row was asked for, plus `body` for EmptyState's own prop —
// see the header. Kept as a Set here; the FORBIDDEN-word list lives in the Python auditor,
// on purpose, so there is exactly one place either list is edited.
const VISIBLE_ATTRS = new Set(['title', 'aria-label', 'placeholder', 'label', 'alt', 'body'])
const TOAST_PROPS = new Set(['title', 'body', 'label'])

/** The literal text of a template literal, substitutions dropped. A citation or a path lives
 *  in the literal part of a sentence, never inside `${…}` — every example measured against
 *  this tree bears that out — so the substitutions can be discarded rather than traced. */
function templateText(node) {
  if (ts.isNoSubstitutionTemplateLiteral(node)) return node.text
  let text = node.head.text
  for (const span of node.templateSpans) text += ' ' + span.literal.text
  return text
}

/** A JSX child expression's literal text(s), through the handful of shapes this tree actually
 *  uses to build one (ternary, `??`, `&&`, `+`, parens). Anything else — a bare call, a
 *  variable — returns nothing: tracing those is the data-flow gap the header names. */
function literalsIn(expr) {
  if (!expr) return []
  if (ts.isStringLiteral(expr)) return [{ node: expr, text: expr.text }]
  if (ts.isNoSubstitutionTemplateLiteral(expr) || ts.isTemplateExpression(expr)) {
    return [{ node: expr, text: templateText(expr) }]
  }
  if (ts.isParenthesizedExpression(expr)) return literalsIn(expr.expression)
  if (ts.isConditionalExpression(expr)) {
    return [...literalsIn(expr.whenTrue), ...literalsIn(expr.whenFalse)]
  }
  if (ts.isBinaryExpression(expr)) {
    const k = expr.operatorToken.kind
    if (k === ts.SyntaxKind.QuestionQuestionToken || k === ts.SyntaxKind.PlusToken) {
      return [...literalsIn(expr.left), ...literalsIn(expr.right)]
    }
    if (k === ts.SyntaxKind.AmpersandAmpersandToken || k === ts.SyntaxKind.BarBarToken) {
      return literalsIn(expr.right)
    }
  }
  return []
}

function walkFile(file, text) {
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const hits = []
  const lineOf = (pos) => sf.getLineAndCharacterOfPosition(pos).line + 1

  function push(node, raw) {
    const trimmed = raw.replace(/\s+/g, ' ').trim()
    if (trimmed === '') return
    hits.push({ line: lineOf(node.getStart(sf)), text: trimmed })
  }

  function collectObjectStrings(node) {
    if (!node || !ts.isObjectLiteralExpression(node)) return
    for (const prop of node.properties) {
      if (!ts.isPropertyAssignment(prop) || !ts.isIdentifier(prop.name)) continue
      const name = prop.name.text
      if (TOAST_PROPS.has(name)) {
        for (const lit of literalsIn(prop.initializer)) push(lit.node, lit.text)
      }
      if (name === 'action') collectObjectStrings(prop.initializer)
    }
  }

  function visit(node) {
    if (ts.isJsxText(node)) {
      push(node, node.getText(sf))
    } else if (ts.isJsxAttribute(node)) {
      const name = node.name.getText(sf)
      const init = node.initializer
      if (VISIBLE_ATTRS.has(name) && init) {
        if (ts.isStringLiteral(init)) {
          push(init, init.text)
        } else if (ts.isJsxExpression(init) && init.expression) {
          for (const lit of literalsIn(init.expression)) push(lit.node, lit.text)
        }
      }
    } else if (
      ts.isJsxExpression(node) &&
      node.parent &&
      !ts.isJsxAttribute(node.parent) &&
      node.expression
    ) {
      // A JSX CHILD expression — `{…}` between tags, not an attribute value. Attribute
      // values are handled above; this branch is the direct-child shape (`{'…'}`, a
      // ternary, a `+`-built sentence).
      for (const lit of literalsIn(node.expression)) push(lit.node, lit.text)
    } else if (
      ts.isCallExpression(node) &&
      ts.isIdentifier(node.expression) &&
      node.expression.text === 'toast'
    ) {
      for (const arg of node.arguments) collectObjectStrings(arg)
    }
    ts.forEachChild(node, visit)
  }

  visit(sf)
  return hits
}

function collectFiles(dir) {
  const out = []
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name)
    if (entry.isDirectory()) out.push(...collectFiles(p))
    else if (entry.name.endsWith('.tsx')) out.push(p)
  }
  return out
}

function extract(srcDir, rootDir) {
  const files = collectFiles(srcDir).sort()
  const out = []
  for (const file of files) {
    const text = fs.readFileSync(file, 'utf8')
    for (const hit of walkFile(file, text)) {
      out.push({ file: path.relative(rootDir, file).split(path.sep).join('/'), line: hit.line, text: hit.text })
    }
  }
  return out
}

// `--dir <path>` lets the auditor's own self-test point this at a throwaway fixture tree
// instead of app/src, the same way `scripts/screen-freshness.mjs --self-test` builds its own
// temp tree rather than trusting the real one to hold a case.
const args = process.argv.slice(2)
const dirFlagIndex = args.indexOf('--dir')
const targetDir = dirFlagIndex >= 0 ? path.resolve(args[dirFlagIndex + 1]) : APP_SRC
const rootForRel = dirFlagIndex >= 0 ? targetDir : ROOT

process.stdout.write(JSON.stringify(extract(targetDir, rootForRel)))
