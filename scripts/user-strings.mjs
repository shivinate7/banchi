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
 * TWO EXTRACTIONS ARE OFF BY DEFAULT, and stay off for `scripts/docs-audit.py`'s own
 * `no mechanism on screen` row, which reads this script with no flags and whose fixtures
 * assert both stay unreached without one — widening the default would retroactively change
 * a row this file did not touch. `typed interpunct` (D218) opts
 * into both, because it reads a different thing (a typed separator character) over a wider
 * notion of "visible" than D196's mechanism-naming policy needs:
 *
 *   - `--include-code-attr` adds `code` to the tracked attribute set for this run only —
 *     `Notice`'s own `code` prop (CLAUDE.md's Register paragraph: "the pipeline's own string
 *     stays available on hover and in the run log"). That prop DOES render, on hover and in
 *     the run log, so a typed dot inside it reaches a person exactly the way JSX text does,
 *     even though D196 deliberately does not police what mechanism-shaped words it may carry.
 *   - `--join-literals` extracts the literal separator argument of any `<expr>.join(<literal>)`
 *     call, anywhere in the file — not only where the call's OWN return value is used
 *     directly as JSX. This is the direct-literal check for the gap the header above already
 *     names: `parts.join(' · ')` fed to a local helper (`PositionLabel.tsx`'s `whole()`) or
 *     stored on an object field read back later (`Fulfillment.tsx`'s `sellable().about`) never
 *     becomes a JsxText, a tracked attribute or a toast argument, so the walk above cannot see
 *     it — but the separator LITERAL passed to `.join()` is a fact about the string that call
 *     is about to build, independent of where the result travels, and grabbing it there is
 *     cheap and precise: it fires on the two known roots and on every other `.join(<literal>)`
 *     call in the tree alike, which is the honest scope of what became visible once this was
 *     built, not a hand-picked pair of file:line citations that the next rename invalidates.
 *     Still unreached: a named helper that builds a separator WITHOUT `.join` (string
 *     concatenation into a `const`, then returned and interpolated by reference elsewhere) —
 *     the same data-flow gap the header names, one call shape narrower.
 *
 * Prints one JSON array to stdout: `[{file, line, text, scope}, …]`, file relative to the repo
 * root. `scope` is the nearest named function, class or binding around the string (see
 * `scopeOf`).
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

// `--include-code-attr` and `--join-literals` — see the header for what each widens and why
// neither is on by default. Read once, at module load, off the raw argv rather than the
// `--dir` parsing below, so a caller can pass either in any order alongside `--dir`.
const RAW_ARGS = process.argv.slice(2)
const INCLUDE_CODE_ATTR = RAW_ARGS.includes('--include-code-attr')
const INCLUDE_JOIN_LITERALS = RAW_ARGS.includes('--join-literals')
if (INCLUDE_CODE_ATTR) VISIBLE_ATTRS.add('code')

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

/** The name of the nearest NAMED declaration around `node`: a function, a method, a class,
 *  a `const X = () => …` binding (a component or helper written as an arrow), or a
 *  module-level `const X = …` (a table). A local variable inside a function is NOT a scope,
 *  so renaming one moves nothing. Anonymous callbacks are passed through to the name around
 *  them. `(module)` when nothing names it. `typed interpunct` keys an entry by this and the text together, so a listed bare
 *  separator such as `·` excuses that string in that one function, never the same string
 *  typed anywhere else in the file. A line number would do the same job and rot on the next
 *  edit above it. */
function scopeOf(node) {
  for (let cur = node.parent; cur; cur = cur.parent) {
    if (
      (ts.isFunctionDeclaration(cur) || ts.isClassDeclaration(cur) || ts.isMethodDeclaration(cur)) &&
      cur.name
    ) {
      return cur.name.getText()
    }
    if (ts.isVariableDeclaration(cur) && ts.isIdentifier(cur.name)) {
      const init = cur.initializer
      const isFunction = init && (ts.isArrowFunction(init) || ts.isFunctionExpression(init))
      const atModule = cur.parent?.parent && ts.isSourceFile(cur.parent.parent.parent)
      if (isFunction || atModule) return cur.name.text
    }
  }
  return '(module)'
}

function walkFile(file, text) {
  const sf = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const hits = []
  const lineOf = (pos) => sf.getLineAndCharacterOfPosition(pos).line + 1

  function push(node, raw) {
    const trimmed = raw.replace(/\s+/g, ' ').trim()
    if (trimmed === '') return
    hits.push({ line: lineOf(node.getStart(sf)), text: trimmed, scope: scopeOf(node) })
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
    } else if (
      INCLUDE_JOIN_LITERALS &&
      ts.isCallExpression(node) &&
      ts.isPropertyAccessExpression(node.expression) &&
      node.expression.name.text === 'join' &&
      node.arguments.length === 1 &&
      (ts.isStringLiteral(node.arguments[0]) || ts.isNoSubstitutionTemplateLiteral(node.arguments[0]))
    ) {
      // `<expr>.join(<literal>)` — the separator ITSELF, never the joined array. Reached
      // regardless of where the call's return value goes (a JSX child, a local variable, an
      // object field read back three functions later): see the header for why this is scoped
      // to `.join()` specifically rather than every call expression in the tree.
      push(node.arguments[0], node.arguments[0].text)
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
      out.push({
        file: path.relative(rootDir, file).split(path.sep).join('/'),
        line: hit.line,
        text: hit.text,
        scope: hit.scope,
      })
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
