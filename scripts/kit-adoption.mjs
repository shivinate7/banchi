#!/usr/bin/env node
/**
 * `make kit-adoption`: does every screen inherit the page scaffold, and does no screen hand-roll
 * a primitive the kit owns?
 *
 * WHY THIS EXISTS. The owner, 2026-09-23: "say a new page in the sidebar gets built tomorrow,
 * it should be able to autocall/inherit the properties of the other pages". `app/src/kit/Page.tsx`
 * is where those properties live: one width, one top gap, one h1, one verdict slot, one toolbar,
 * one status slot, one loading shape. A screen inherits them only if it renders `<Page>`. A
 * screen that draws its own `role="dialog"`, its own `<select>` or its own `bn-money` span has
 * stepped around the kit, and the next change to the kit will not reach it. D173: a rule that
 * can be enforced mechanically must be. This is the mechanism. D-page-scaffold is the argument.
 *
 * TWO RULES, READ FROM THE TYPESCRIPT AST (the same reader `scripts/user-strings.mjs` and
 * `scripts/screen-freshness.mjs` use, for their reason: a regex reads JSX, ternaries and
 * template literals wrong).
 *
 *   R1         Every `ROUTES` view in `app/src/App.tsx` renders `<Page>` imported from the kit
 *              (`./kit` or `./kit/Page`). The view may reach it through its own components: the
 *              reader follows a JSX tag into a local component, or into a component imported
 *              (named or default) from another screen file, AT ANY DEPTH. `Shipping` renders
 *              `OrdersHub` from `./Orders`, so if `OrdersHub` renders `<Page>`, both routes pass.
 *              It never follows a tag into the kit itself: a kit wrapper is not a screen's
 *              `<Page>`. THERE IS NO DEPTH CAP. A cap plus one visited set made the answer
 *              depend on JSX order: a component first met at the cap was marked visited and
 *              cut, so a shorter path to it was never tried. The visited set alone ends a cycle,
 *              and whether a path exists does not depend on the order the graph is walked.
 *   R2-*       Outside `app/src/kit/**`, no screen hand-rolls a kit primitive:
 *                R2-dialog   `role="dialog"` or `role="alertdialog"`, or a native `<dialog>`
 *                            element (the kit has Sheet, Modal, Popover and ConfirmSheet in
 *                            `kit/overlay.tsx`)
 *                R2-search   `<input type="search">` outside `app/src/SearchField.tsx`, which is
 *                            that primitive. ALSO, BY HEURISTIC: an `<input>` whose type is
 *                            `text` or absent (a text input either way) and whose literal
 *                            `placeholder` or `aria-label` matches SEARCHISH below (search, find,
 *                            filter, look up). A search box labelled some other way is not seen.
 *                R2-select   a raw `<select>` (the kit's Select)
 *                R2-class    a kit-reserved class name in `className`, `.className =` or
 *                            `classList.add(...)`: RESERVED_EXACT and RESERVED_PREFIX below.
 *                            `app/src/Gallery.tsx` is exempt from this one rule: it is the kit's
 *                            specimen sheet and draws each kit class raw on purpose
 *                R2-date     `toLocaleDateString`, `toLocaleTimeString` or `Intl.DateTimeFormat`
 *                            outside `app/src/dates.ts`. ALSO, BY HEURISTIC: `.toLocaleString(...)`
 *                            with an object-literal argument that names a date or time option
 *                            (DATE_OPTIONS below). A bare `d.toLocaleString()` on a Date is NOT
 *                            seen: without the type checker a Date and a number read the same,
 *                            and a number's `toLocaleString()` is a count, not a date.
 *                R2-money    a hand-rolled dollar amount outside `app/src/money.ts`, in any of
 *                            these shapes:
 *                              - a template literal whose text before an interpolation ends in
 *                                `$` or `$ ` (`$${x}`, `-$ ${n.toFixed(2)}`)
 *                              - a `+` whose left side ends in a string literal that ends in `$`
 *                                or `$ ` (`'$' + x.toFixed(2)`)
 *                              - JSX text that ends in `$` (then optional white space) directly
 *                                before a `{...}` child, or a `{'$'}` child directly before one
 *                              - `Intl.NumberFormat(...)` or `.toLocaleString(...)` with an
 *                                object-literal option `style: 'currency'` or a `currency` key
 *                            HEURISTIC, said plainly: a `$` before an interpolation is read as a
 *                            price, which it is in this product. An options object held in a
 *                            variable is not seen.
 *
 * THE EXCEPTIONS ARE A SHRINKING OFFENDER LIST, NEVER A PINNED COUNT (the owner's ruling on Q3,
 * 2026-09-23). `scripts/kit-adoption-allow.json`'s `static` block is file -> rule -> lane: the
 * lane that owes the migration. It FAILS on a violation it does not list, and it FAILS on an
 * entry that no longer matches a violation (a stale entry), so a lane that migrates a screen
 * deletes its own entries in the same commit. An entry covers every occurrence of that rule in
 * that file. It is a per-file debt, never a count.
 *
 * ONLY SHRINKS, AND THAT IS CHECKED. The stale-entry rule stops an entry outliving its debt, but
 * it cannot stop a branch ADDING an entry to excuse a new screen. So the check also reads the
 * allow list as it stood at the merge-base with `origin/main` (`git merge-base HEAD origin/main`,
 * then `git show <base>:scripts/kit-adoption-allow.json`: two plain reads, so D18 holds) and
 * REFUSES every key the branch added for a rule that EXISTS AT THE MERGE-BASE: a new file -> rule
 * pair in `static`, or a new route -> assertion pair in `runtime`. A removed key passes: that is
 * the list shrinking. A new lane on a key that already existed is not growth.
 * ONE EXCEPTION, the orchestrator's call (option b, 2026-09-23): a new key is ALLOWED when its
 * rule is NOT defined at the merge-base, because a rule born on this branch finds offenders
 * nobody could have listed before it existed. "Defined at the merge-base" is read, never
 * assumed: the keys of `RULES` in this file for `static`, and the members of `PER_ROUTE` and
 * `SHELL_WIDE` in `app/tests/scaffold.spec.ts` for `runtime`, each by `git show <base>:<file>`.
 * Each allowed key is PRINTED with the rule that allowed it and why. A definition that cannot be
 * read at the merge-base allows nothing. Once the branch merges, its new rule exists at every
 * later merge-base, so from then on that rule only shrinks too. IT FAILS OPEN, AND PRINTS WHY: no git, no
 * `origin/main`, no merge-base, or no allow list at the merge-base. The last is the branch that
 * gives the list its birth, where every entry is new by definition.
 *
 * `runtime` in the same file belongs to `app/tests/scaffold.spec.ts`, which validates it. This
 * script checks that the block is an object, and that it grows only by the rule above.
 *
 * WHAT IS NOT SEEN, said here so nobody reads green as more than it is:
 *   - a class name, role or type that reaches JSX through a variable (`const c = 'bn-money'`,
 *     `<div className={c}>`) and not as a literal inside the attribute. The same data-flow gap
 *     `user-strings.mjs` names.
 *   - a view that renders `<Page>` on one branch and something else on another. R1 asks whether
 *     the view reaches `<Page>` at all. `scaffold.spec.ts` asserts what a browser actually drew.
 *   - a view assigned to a variable and rendered through it (`const V = a ? A : B; <V/>`).
 *   - each HEURISTIC above, past the edge it states.
 *
 *     node scripts/kit-adoption.mjs              the check (exit 1 on any finding)
 *     node scripts/kit-adoption.mjs --self-test  the checker against in-memory fixtures
 *     node scripts/kit-adoption.mjs --routes     ROUTES as JSON, for scaffold.spec.ts
 *
 * NEVER WRITES (D18). The self-test builds its fixtures as in-memory maps of path -> source. Its
 * one read of the disk is the only-shrinks case that reads the committed list and rules at HEAD with
 * `git merge-base` and `git show`, which write nothing.
 */

import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.dirname(HERE)

const TYPESCRIPT = path.join(ROOT, 'app', 'node_modules', 'typescript', 'lib', 'typescript.js')
if (!fs.existsSync(TYPESCRIPT)) {
  console.error(
    'kit-adoption: app/node_modules/typescript is missing, so nothing was read, which is not ' +
      'the same as nothing being wrong. Run `npm --prefix app install` first.',
  )
  process.exit(1)
}
const ts = (await import(pathToFileURL(TYPESCRIPT).href)).default

const APP_SRC = 'app/src'
const APP_FILE = 'app/src/App.tsx'
const KIT_DIR = 'app/src/kit/'
const KIT_MODULES = new Set(['app/src/kit/index.tsx', 'app/src/kit/Page.tsx'])
/** THE ONE FILE OUTSIDE THE KIT THAT MAY DO WHAT A RULE FORBIDS, because it is the primitive the
 *  rule points everyone else at. `SearchField.tsx` is the kit's search field and draws the one
 *  `<input type="search">`; `dates.ts` and `money.ts` are the one date and money format. */
export const HOME = {
  'R2-search': 'app/src/SearchField.tsx',
  'R2-date': 'app/src/dates.ts',
  'R2-money': 'app/src/money.ts',
}
/** THE KIT'S OWN SPECIMEN SHEET. `#/gallery` draws each kit class raw so a person can see it
 *  (a `bn-skeleton` bar, a `bn-money` figure, the `bn-title` size), which is its whole job. It is
 *  exempt from R2-class only. R1 and every other R2 rule still apply to it. */
export const SPECIMEN_FILES = ['app/src/Gallery.tsx']
const ALLOW_FILE = 'scripts/kit-adoption-allow.json'

/** Every rule id the allow list may name. An entry naming anything else is refused. */
export const RULES = {
  R1: 'the route view never renders <Page> from the kit',
  'R2-dialog': 'role="dialog", role="alertdialog" or a native <dialog> outside the kit (use Sheet, Modal, Popover)',
  'R2-search': '<input type="search">, or a text input labelled like a search box, outside SearchField (use SearchField)',
  'R2-select': 'a raw <select> outside the kit (use Select)',
  'R2-class': 'a kit-reserved class name outside the kit',
  'R2-date': 'a hand-rolled date format outside app/src/dates.ts',
  'R2-money': 'a hand-rolled $ amount outside app/src/money.ts (use the kit\'s Money, or money() from money.ts)',
}

/** The class names only the kit may write. A token equal to one of these is reserved. */
export const RESERVED_EXACT = ['bn-page', 'bn-head', 'bn-title', 'bn-lede', 'bn-money', 'bn-skeleton', 'bn-select']
/** The class-name families only the kit may write: any token that starts with one of these. */
export const RESERVED_PREFIX = ['bn-empty', 'bn-notice', 'bn-sheet', 'bn-modal']

function reserved(token) {
  if (RESERVED_EXACT.includes(token)) return true
  return RESERVED_PREFIX.some((prefix) => token.startsWith(prefix))
}

/* ---- reading ------------------------------------------------------------------------------- */

function makeReader(files) {
  const cache = new Map()
  function parse(rel) {
    if (!cache.has(rel)) {
      const text = files.get(rel)
      if (text === undefined) return null
      const kind = rel.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS
      cache.set(rel, ts.createSourceFile(rel, text, ts.ScriptTarget.Latest, true, kind))
    }
    return cache.get(rel)
  }
  function resolve(fromRel, spec) {
    if (!spec.startsWith('.')) return null
    const base = path.posix.normalize(path.posix.join(path.posix.dirname(fromRel), spec))
    for (const ext of ['', '.tsx', '.ts', '/index.tsx', '/index.ts']) {
      if (files.has(base + ext) && /\.tsx?$/.test(base + ext)) return base + ext
    }
    return null
  }
  return { parse, resolve }
}

function lineOf(sf, node) {
  return sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1
}

function unwrap(expr) {
  let e = expr
  while (e && (ts.isAsExpression(e) || ts.isSatisfiesExpression(e) || ts.isParenthesizedExpression(e) || ts.isTypeAssertionExpression(e))) {
    e = e.expression
  }
  return e
}

/** `import { A as B } from './x'` -> B: { file, imported: 'A' }; `import D from './x'` -> D:
 *  { file, imported: 'default' }; `import * as K` -> K: { file, ns }. */
function importsOf(sf, rel, reader) {
  const named = new Map()
  const namespaces = new Map()
  for (const st of sf.statements) {
    if (!ts.isImportDeclaration(st) || !st.importClause || !ts.isStringLiteral(st.moduleSpecifier)) continue
    const file = reader.resolve(rel, st.moduleSpecifier.text)
    if (st.importClause.name) named.set(st.importClause.name.text, { file, imported: 'default' })
    const bindings = st.importClause.namedBindings
    if (bindings && ts.isNamedImports(bindings)) {
      for (const el of bindings.elements) {
        named.set(el.name.text, { file, imported: (el.propertyName ?? el.name).text })
      }
    } else if (bindings && ts.isNamespaceImport(bindings)) {
      namespaces.set(bindings.name.text, file)
    }
  }
  return { named, namespaces }
}

const hasModifier = (node, kind) => (ts.canHaveModifiers(node) ? ts.getModifiers(node) ?? [] : []).some((m) => m.kind === kind)

/** A top-level component named `name`: a function declaration, or `const name = <function>`,
 *  or `const name = memo(<function>)`. Or a re-export `export { name } from './x'`, or a local
 *  alias `export { local as name }`. `name` may be 'default': `export default function X`,
 *  `export default X`, `export default memo(...)` or `export { X as default }`. */
function findComponent(sf, name, depth = 0) {
  if (depth > 8) return null
  for (const st of sf.statements) {
    if (name === 'default') {
      if (ts.isFunctionDeclaration(st) && hasModifier(st, ts.SyntaxKind.DefaultKeyword)) return { node: st }
      if (ts.isExportAssignment(st) && !st.isExportEquals) {
        let e = unwrap(st.expression)
        if (ts.isIdentifier(e)) return findComponent(sf, e.text, depth + 1)
        if (ts.isCallExpression(e) && e.arguments.length > 0) e = unwrap(e.arguments[0])
        return { node: e }
      }
    }
    if (ts.isExportDeclaration(st) && !st.moduleSpecifier && st.exportClause && ts.isNamedExports(st.exportClause)) {
      for (const el of st.exportClause.elements) {
        if (el.name.text === name && el.propertyName && el.propertyName.text !== name) return findComponent(sf, el.propertyName.text, depth + 1)
      }
    }
    if (ts.isFunctionDeclaration(st) && st.name?.text === name) return { node: st }
    if (ts.isVariableStatement(st)) {
      for (const decl of st.declarationList.declarations) {
        if (!ts.isIdentifier(decl.name) || decl.name.text !== name || !decl.initializer) continue
        let init = unwrap(decl.initializer)
        if (ts.isCallExpression(init) && init.arguments.length > 0) init = unwrap(init.arguments[0])
        return { node: init }
      }
    }
    if (ts.isExportDeclaration(st) && st.moduleSpecifier && ts.isStringLiteral(st.moduleSpecifier) && st.exportClause && ts.isNamedExports(st.exportClause)) {
      for (const el of st.exportClause.elements) {
        if (el.name.text === name) return { reexport: st.moduleSpecifier.text, imported: (el.propertyName ?? el.name).text }
      }
    }
  }
  return null
}

function jsxTags(node) {
  const tags = []
  const visit = (n) => {
    if (ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n)) {
      const t = n.tagName
      if (ts.isIdentifier(t)) tags.push(t.text)
      else if (ts.isPropertyAccessExpression(t) && ts.isIdentifier(t.expression)) tags.push(`${t.expression.text}.${t.name.text}`)
    }
    ts.forEachChild(n, visit)
  }
  visit(node)
  return tags
}

/** Does component `name` in `rel` render `<Page>` from the kit, directly or through a component
 *  it renders, at any depth? Returns the chain that reached it, or null. `seen` is the one
 *  visited set for this question: it ends a cycle, and because there is no depth cap, a node
 *  marked visited has had every path out of it tried, so the walk's order cannot change the
 *  answer. */
function rendersPage(rel, name, reader, seen = new Set()) {
  const key = `${rel}#${name}`
  if (seen.has(key) || rel.startsWith(KIT_DIR)) return null
  seen.add(key)
  const sf = reader.parse(rel)
  if (sf === null) return null
  const found = findComponent(sf, name)
  if (found === null) return null
  if (found.reexport !== undefined) {
    const next = reader.resolve(rel, found.reexport)
    return next === null ? null : rendersPage(next, found.imported, reader, seen)
  }
  const { named, namespaces } = importsOf(sf, rel, reader)
  const tags = jsxTags(found.node)
  for (const tag of tags) {
    const imp = named.get(tag)
    if (imp && KIT_MODULES.has(imp.file) && imp.imported === 'Page') return [`${rel}#${name}`]
    const dot = tag.indexOf('.')
    if (dot > 0 && tag.slice(dot + 1) === 'Page' && KIT_MODULES.has(namespaces.get(tag.slice(0, dot)))) return [`${rel}#${name}`]
  }
  for (const tag of new Set(tags)) {
    if (!/^[A-Z]/.test(tag) || tag.includes('.')) continue
    const imp = named.get(tag)
    let chain = null
    if (imp) {
      if (imp.file !== null && !imp.file.startsWith(KIT_DIR)) chain = rendersPage(imp.file, imp.imported, reader, seen)
    } else if (findComponent(sf, tag) !== null) {
      chain = rendersPage(rel, tag, reader, seen)
    }
    if (chain !== null) return [`${rel}#${name}`, ...chain]
  }
  return null
}

/** `ROUTES` out of App.tsx: path, label, title, persona, view, and the file the view lives in.
 *  Throws on a shape it cannot read, so a reworded table is a loud failure and never a pass. */
export function readRoutes(files) {
  const reader = makeReader(files)
  const sf = reader.parse(APP_FILE)
  if (sf === null) throw new Error(`${APP_FILE} is missing`)
  let table = null
  const find = (n) => {
    if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === 'ROUTES' && n.initializer) table = unwrap(n.initializer)
    else ts.forEachChild(n, find)
  }
  find(sf)
  if (table === null) throw new Error(`${APP_FILE} declares no ROUTES`)
  if (!ts.isArrayLiteralExpression(table)) throw new Error(`${APP_FILE}: ROUTES is not an array literal, so this reader cannot see the routes`)
  const { named } = importsOf(sf, APP_FILE, reader)
  const routes = []
  for (const el of table.elements) {
    if (!ts.isObjectLiteralExpression(el)) throw new Error(`${APP_FILE}:${lineOf(sf, el)}: a ROUTES entry is not an object literal`)
    const props = {}
    for (const p of el.properties) {
      if (!ts.isPropertyAssignment(p) || !ts.isIdentifier(p.name)) continue
      const v = unwrap(p.initializer)
      if (ts.isStringLiteral(v) || ts.isNoSubstitutionTemplateLiteral(v)) props[p.name.text] = v.text
      else if (ts.isIdentifier(v)) props[p.name.text] = { ident: v.text }
    }
    const where = `${APP_FILE}:${lineOf(sf, el)}`
    if (typeof props.path !== 'string' || typeof props.label !== 'string' || typeof props.view !== 'object') {
      throw new Error(`${where}: a ROUTES entry without a literal path, a literal label and a view identifier`)
    }
    const viewName = props.view.ident
    const imp = named.get(viewName)
    let file = null
    /* `view` is the name App.tsx uses, so a message names what a person reads there; `exported`
       is the name the view's own file exports it under, which is what the reader looks up. For a
       default import (`import Home from './Home'`) the two differ: `Home` and 'default'. */
    let exported = viewName
    if (imp) {
      file = imp.file
      exported = imp.imported
    } else if (findComponent(sf, viewName) !== null) {
      file = APP_FILE
    }
    if (file === null) throw new Error(`${where}: the view ${viewName} resolves to no file under ${APP_SRC}`)
    routes.push({
      path: props.path,
      label: props.label,
      title: typeof props.title === 'string' ? props.title : null,
      persona: typeof props.persona === 'string' ? props.persona : null,
      view: viewName,
      exported,
      file,
      line: lineOf(sf, el),
    })
  }
  if (routes.length === 0) throw new Error(`${APP_FILE}: ROUTES is empty, so R1 would pass over nothing`)
  return routes
}

/* ---- the rules ----------------------------------------------------------------------------- */

/** The literal strings an expression can evaluate to, through ternaries, `??`, `||`, `&&`. */
function literalsOf(expr) {
  const e = unwrap(expr)
  if (!e) return []
  if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) return [e.text]
  if (ts.isJsxExpression(e)) return literalsOf(e.expression)
  if (ts.isConditionalExpression(e)) return [...literalsOf(e.whenTrue), ...literalsOf(e.whenFalse)]
  if (ts.isBinaryExpression(e)) {
    const k = e.operatorToken.kind
    if (k === ts.SyntaxKind.QuestionQuestionToken || k === ts.SyntaxKind.BarBarToken) return [...literalsOf(e.left), ...literalsOf(e.right)]
    if (k === ts.SyntaxKind.AmpersandAmpersandToken) return literalsOf(e.right)
  }
  return []
}

/** Every string fragment anywhere inside a class-name expression: literals, template parts,
 *  array members joined later. Split on whitespace into class tokens. */
function classTokens(expr) {
  const out = []
  const visit = (n) => {
    if (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)) out.push(n.text)
    else if (ts.isTemplateExpression(n)) {
      out.push(n.head.text)
      for (const span of n.templateSpans) out.push(span.literal.text)
    }
    ts.forEachChild(n, visit)
  }
  visit(expr)
  return out.flatMap((s) => s.split(/\s+/)).filter(Boolean)
}

function callsToFixed(node) {
  let hit = false
  const visit = (n) => {
    if (hit) return
    if (ts.isCallExpression(n) && ts.isPropertyAccessExpression(n.expression) && n.expression.name.text === 'toFixed') hit = true
    else ts.forEachChild(n, visit)
  }
  visit(node)
  return hit
}

/** R2-search's heuristic: a text input labelled like a search box. Read from a literal
 *  `placeholder` or `aria-label` only. */
export const SEARCHISH = /\b(search|find|filter|look ?up)/i
/** R2-date's heuristic: an options object with any of these keys is asking for a date or a time. */
export const DATE_OPTIONS = ['dateStyle', 'timeStyle', 'year', 'month', 'day', 'weekday', 'hour', 'minute', 'second', 'era', 'timeZoneName', 'hour12', 'hourCycle', 'dayPeriod']
/** R2-money: text that ends in a dollar sign, then at most white space, right before a value. */
const DOLLAR_END = /\$\s?$/
const DOLLAR_END_JSX = /\$\s*$/

/** The object literals among a call's arguments, as a map of key -> initializer. */
function optionObjects(args) {
  const out = []
  for (const arg of args ?? []) {
    const a = unwrap(arg)
    if (!a || !ts.isObjectLiteralExpression(a)) continue
    const keys = new Map()
    for (const p of a.properties) {
      if ((ts.isPropertyAssignment(p) || ts.isShorthandPropertyAssignment(p)) && p.name && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name))) {
        keys.set(p.name.text, ts.isPropertyAssignment(p) ? p.initializer : null)
      }
    }
    out.push(keys)
  }
  return out
}

const asksCurrency = (args) =>
  optionObjects(args).some((o) => o.has('currency') || (o.get('style') !== undefined && o.get('style') !== null && literalsOf(o.get('style')).includes('currency')))
const asksDate = (args) => optionObjects(args).some((o) => DATE_OPTIONS.some((k) => o.has(k)))

/** Does this expression END in a string literal that ends in `$` (then one optional space)?
 *  `'$'`, `'Total: $'`, and `a + '$'` (the right end of a `+` chain) do. */
function endsInDollar(expr) {
  const e = unwrap(expr)
  if (!e) return false
  if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) return DOLLAR_END.test(e.text)
  if (ts.isTemplateExpression(e)) return false
  if (ts.isBinaryExpression(e) && e.operatorToken.kind === ts.SyntaxKind.PlusToken) return endsInDollar(e.right)
  return false
}

const isIntlNumberFormat = (callee) =>
  ts.isPropertyAccessExpression(callee) && callee.name.text === 'NumberFormat' && ts.isIdentifier(callee.expression) && callee.expression.text === 'Intl'

function attr(element, name) {
  const attrs = ts.isJsxSelfClosingElement(element) || ts.isJsxOpeningElement(element) ? element.attributes.properties : []
  return attrs.find((a) => ts.isJsxAttribute(a) && a.name.getText() === name)
}

function attrLiterals(a) {
  if (!a || !a.initializer) return []
  return ts.isStringLiteral(a.initializer) ? [a.initializer.text] : literalsOf(a.initializer)
}

/** Every R2 violation in one file: `{ rule, line, detail }`. */
function scanFile(rel, sf) {
  const hits = []
  const add = (rule, node, detail) => {
    if (HOME[rule] === rel) return
    if (rule === 'R2-class' && SPECIMEN_FILES.includes(rel)) return
    hits.push({ rule, line: lineOf(sf, node), detail })
  }
  const visit = (n) => {
    if (ts.isJsxAttribute(n)) {
      const name = n.name.getText(sf)
      if (name === 'role') {
        for (const v of attrLiterals(n)) if (v === 'dialog' || v === 'alertdialog') add('R2-dialog', n, `role="${v}"`)
      } else if (name === 'className' && n.initializer) {
        for (const t of classTokens(n.initializer)) if (reserved(t)) add('R2-class', n, t)
      }
    } else if (ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n)) {
      const tag = n.tagName.getText(sf)
      if (tag === 'select') add('R2-select', n, '<select>')
      if (tag === 'dialog') add('R2-dialog', n, '<dialog>')
      if (tag === 'input') {
        const typeAttr = attr(n, 'type')
        const types = attrLiterals(typeAttr)
        if (types.includes('search')) add('R2-search', n, '<input type="search">')
        else if (typeAttr === undefined || types.includes('text')) {
          const label = [...attrLiterals(attr(n, 'placeholder')), ...attrLiterals(attr(n, 'aria-label'))].find((t) => SEARCHISH.test(t))
          if (label !== undefined) add('R2-search', n, `a text <input> labelled "${label}"`)
        }
      }
    } else if (ts.isJsxElement(n) || ts.isJsxFragment(n)) {
      /* A `$` in JSX text, or a `{'$'}` child, directly before a `{...}` child. */
      const kids = n.children
      for (let i = 0; i + 1 < kids.length; i += 1) {
        const k = kids[i]
        const next = kids[i + 1]
        if (!ts.isJsxExpression(next) || !next.expression) continue
        const dollar = ts.isJsxText(k) ? DOLLAR_END_JSX.test(k.text) : ts.isJsxExpression(k) && k.expression !== undefined && endsInDollar(k.expression)
        if (dollar) add('R2-money', next, 'a `$` in JSX before `{...}`')
      }
    } else if (ts.isBinaryExpression(n) && n.operatorToken.kind === ts.SyntaxKind.PlusToken && endsInDollar(n.left)) {
      add('R2-money', n, "`'$' + ...`")
    } else if ((ts.isNewExpression(n) || ts.isCallExpression(n)) && isIntlNumberFormat(n.expression) && asksCurrency(n.arguments)) {
      add('R2-money', n, "Intl.NumberFormat with style 'currency'")
    } else if (ts.isCallExpression(n) && ts.isPropertyAccessExpression(n.expression) && n.expression.name.text === 'toLocaleString') {
      if (asksCurrency(n.arguments)) add('R2-money', n, "toLocaleString with style 'currency'")
      else if (asksDate(n.arguments)) add('R2-date', n, 'toLocaleString with a date or time option')
    } else if (ts.isBinaryExpression(n) && n.operatorToken.kind === ts.SyntaxKind.EqualsToken && ts.isPropertyAccessExpression(n.left) && n.left.name.text === 'className') {
      for (const t of classTokens(n.right)) if (reserved(t)) add('R2-class', n, t)
    } else if (ts.isCallExpression(n) && ts.isPropertyAccessExpression(n.expression) && n.expression.name.text === 'add' && ts.isPropertyAccessExpression(n.expression.expression) && n.expression.expression.name.text === 'classList') {
      for (const arg of n.arguments) for (const t of classTokens(arg)) if (reserved(t)) add('R2-class', n, t)
    } else if (ts.isPropertyAccessExpression(n)) {
      const prop = n.name.text
      if (prop === 'toLocaleDateString' || prop === 'toLocaleTimeString') add('R2-date', n, prop)
      if (prop === 'DateTimeFormat' && ts.isIdentifier(n.expression) && n.expression.text === 'Intl') add('R2-date', n, 'Intl.DateTimeFormat')
    } else if (ts.isTemplateExpression(n)) {
      let before = n.head.text
      for (const span of n.templateSpans) {
        if (DOLLAR_END.test(before)) add('R2-money', span.expression, callsToFixed(span.expression) ? '`$${... .toFixed(...)}`' : '`$${...}`')
        before = span.literal.text
      }
    }
    ts.forEachChild(n, visit)
  }
  visit(sf)
  return hits
}

/** Every violation of R1 and R2 in a tree of `path -> source`. */
export function analyze(files) {
  const reader = makeReader(files)
  const routes = readRoutes(files)
  const violations = []
  for (const route of routes) {
    if (rendersPage(route.file, route.exported, reader) === null) {
      const sf = reader.parse(route.file)
      const found = sf === null ? null : findComponent(sf, route.exported)
      const line = found?.node ? lineOf(sf, found.node) : 1
      const how = route.exported === 'default' ? ' (the default export)' : ''
      violations.push({ file: route.file, rule: 'R1', line, detail: `the view ${route.view}${how} for ${route.path}` })
    }
  }
  for (const rel of [...files.keys()].sort()) {
    if (!rel.startsWith(`${APP_SRC}/`) || rel.startsWith(KIT_DIR) || !/\.tsx?$/.test(rel) || rel.endsWith('.d.ts')) continue
    const sf = reader.parse(rel)
    for (const hit of scanFile(rel, sf)) violations.push({ file: rel, ...hit })
  }
  return { routes, violations }
}

/** The shrinking list: what the allow list does not cover, and what it covers that is gone. */
export function judge(violations, allow) {
  const errors = []
  const listed = new Map()
  if (allow === null || typeof allow !== 'object' || Array.isArray(allow)) {
    return { errors: ['the allow list is not a JSON object'], unlisted: [], stale: [], listed }
  }
  for (const key of Object.keys(allow)) {
    if (!['_about', 'static', 'runtime'].includes(key)) errors.push(`unknown top-level key "${key}" (only _about, static, runtime)`)
  }
  const stat = allow.static ?? {}
  if (typeof stat !== 'object' || Array.isArray(stat)) errors.push('"static" is not an object of file -> rule -> lane')
  if (allow.runtime !== undefined && (typeof allow.runtime !== 'object' || Array.isArray(allow.runtime))) errors.push('"runtime" is not an object')
  for (const [file, rules] of Object.entries(stat)) {
    if (typeof rules !== 'object' || rules === null || Array.isArray(rules)) {
      errors.push(`static["${file}"] is not an object of rule -> lane`)
      continue
    }
    for (const [rule, lane] of Object.entries(rules)) {
      if (!(rule in RULES)) errors.push(`static["${file}"] names rule "${rule}", which is not one of ${Object.keys(RULES).join(', ')}`)
      else if (typeof lane !== 'string' || lane.trim() === '') errors.push(`static["${file}"]["${rule}"] names no lane`)
      else listed.set(`${file}\u0000${rule}`, lane)
    }
  }
  const seen = new Set(violations.map((v) => `${v.file}\u0000${v.rule}`))
  const unlisted = violations.filter((v) => !listed.has(`${v.file}\u0000${v.rule}`))
  const stale = [...listed.entries()].filter(([key]) => !seen.has(key)).map(([key, lane]) => {
    const [file, rule] = key.split('\u0000')
    return { file, rule, lane }
  })
  return { errors, unlisted, stale, listed }
}

/** Every key of a two-level block, `outer -> inner`, as `{ key: 'outer -> inner', rule: inner }`. */
function pairs(block) {
  const out = new Map()
  if (block === null || typeof block !== 'object' || Array.isArray(block)) return out
  for (const [outer, inner] of Object.entries(block)) {
    if (inner === null || typeof inner !== 'object' || Array.isArray(inner)) continue
    for (const rule of Object.keys(inner)) out.set(`${outer} -> ${rule}`, rule)
  }
  return out
}

/** ONLY SHRINKS, WITH ONE EXCEPTION (the orchestrator's call, option b, 2026-09-23). Every key
 *  `head` holds in `static` or `runtime` that `base` did not is growth. Growth is REFUSED for a
 *  rule that exists at the merge-base, and ALLOWED only for a rule born on this branch: a new
 *  rule finds offenders nobody could have listed before it existed. `baseRules` is
 *  `{ static, runtime }`, each the Set of rule ids defined at the merge-base (RULES in this file;
 *  PER_ROUTE and SHELL_WIDE in scaffold.spec.ts), or null when that definition could not be read.
 *  A null set allows nothing: an unread definition never excuses growth. `base` null means there
 *  was nothing to compare against: the caller fails open and prints why.
 *  Returns `{ refused, allowed }`, each a list of `{ block, key, rule, why }`, or null. */
export function growth(base, head, baseRules = { static: null, runtime: null }) {
  if (base === null) return null
  const refused = []
  const allowed = []
  for (const block of ['static', 'runtime']) {
    const before = pairs(base?.[block])
    const known = baseRules?.[block] ?? null
    for (const [key, rule] of pairs(head?.[block])) {
      if (before.has(key)) continue
      if (known !== null && !known.has(rule)) {
        allowed.push({ block, key, rule, why: `rule "${rule}" is not defined at the merge-base, so it was born on this branch and its first offenders may be listed` })
      } else {
        const why = known === null
          ? `the merge-base's ${block} rule definitions could not be read, so "${rule}" cannot be shown to be new`
          : `rule "${rule}" exists at the merge-base, and a rule that exists only shrinks`
        refused.push({ block, key, rule, why })
      }
    }
  }
  return { refused, allowed }
}

/** The ids a source defines: the keys of an object literal named `objectName`, or the string
 *  members of array literals named in `arrayNames`. Null when none of them is found. */
export function definedIds(source, { objectName = null, arrayNames = [] } = {}) {
  const sf = ts.createSourceFile('x.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const ids = new Set()
  let found = false
  const visit = (n) => {
    if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.initializer) {
      const init = unwrap(n.initializer)
      if (n.name.text === objectName && ts.isObjectLiteralExpression(init)) {
        found = true
        for (const p of init.properties) {
          if (p.name && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name))) ids.add(p.name.text)
        }
      } else if (arrayNames.includes(n.name.text) && ts.isArrayLiteralExpression(init)) {
        found = true
        for (const el of init.elements) if (ts.isStringLiteral(el)) ids.add(el.text)
      }
    }
    ts.forEachChild(n, visit)
  }
  visit(sf)
  return found ? ids : null
}

const SPEC_FILE = 'app/tests/scaffold.spec.ts'
const SELF_FILE = 'scripts/kit-adoption.mjs'

/** The allow list, and the rule ids defined, as they stood at the merge-base with `reference`,
 *  or the reason there is none. Plain reads (`git merge-base`, `git show`), so nothing is
 *  written (D18). */
function allowAtBase(reference = 'origin/main') {
  const git = (...args) => execFileSync('git', args, { cwd: ROOT, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim()
  let base
  try {
    base = git('merge-base', 'HEAD', reference)
  } catch {
    return { allow: null, reason: `no merge-base between HEAD and ${reference} (no git, no ${reference}, or no shared history)` }
  }
  let text
  try {
    text = git('show', `${base}:${ALLOW_FILE}`)
  } catch {
    return { allow: null, reason: `${ALLOW_FILE} does not exist at the merge-base ${base.slice(0, 8)}, so this branch gives it its birth and every entry is new` }
  }
  let allow
  try {
    allow = JSON.parse(text)
  } catch (err) {
    return { allow: null, reason: `${ALLOW_FILE} at the merge-base ${base.slice(0, 8)} is not JSON (${err.message})` }
  }
  const idsAt = (file, shape) => {
    try {
      return definedIds(git('show', `${base}:${file}`), shape)
    } catch {
      return null
    }
  }
  const rules = {
    static: idsAt(SELF_FILE, { objectName: 'RULES' }),
    runtime: idsAt(SPEC_FILE, { arrayNames: ['PER_ROUTE', 'SHELL_WIDE'] }),
  }
  return { allow, base, rules }
}

/* ---- the real tree ------------------------------------------------------------------------- */

function readTree() {
  const files = new Map()
  const walk = (dir) => {
    for (const entry of fs.readdirSync(path.join(ROOT, dir), { withFileTypes: true })) {
      const rel = `${dir}/${entry.name}`
      if (entry.isDirectory()) walk(rel)
      else if (/\.tsx?$/.test(entry.name)) files.set(rel, fs.readFileSync(path.join(ROOT, rel), 'utf8'))
    }
  }
  walk(APP_SRC)
  return files
}

function run() {
  const files = readTree()
  let result
  try {
    result = analyze(files)
  } catch (err) {
    console.error(`kit-adoption: ${err.message}`)
    process.exit(1)
  }
  let allow
  try {
    allow = JSON.parse(fs.readFileSync(path.join(ROOT, ALLOW_FILE), 'utf8'))
  } catch (err) {
    console.error(`kit-adoption: ${ALLOW_FILE} could not be read as JSON: ${err.message}`)
    process.exit(1)
  }
  const { errors, unlisted, stale, listed } = judge(result.violations, allow)
  for (const e of errors) console.error(`kit-adoption: ${ALLOW_FILE}: ${e}`)
  for (const v of unlisted) {
    console.error(`kit-adoption: ${v.file}:${v.line}: ${v.rule}: ${v.detail}. ${RULES[v.rule]}.`)
  }
  for (const s of stale) {
    console.error(
      `kit-adoption: ${ALLOW_FILE}: stale entry ${s.file} -> ${s.rule} -> ${s.lane}. That file no longer ` +
        `breaks ${s.rule}. Delete the entry: the list only shrinks.`,
    )
  }
  if (unlisted.length > 0) {
    console.error(
      `kit-adoption: ${unlisted.length} violation(s) the allow list does not name. Fix the screen: render ` +
        `<Page> from ./kit, or use the kit's primitive. D-page-scaffold says why.`,
    )
  }
  const atBase = allowAtBase()
  const grown = growth(atBase.allow, allow, atBase.rules)
  if (grown === null) {
    console.log(`kit-adoption: only-shrinks not compared: ${atBase.reason}. Failing open.`)
  } else {
    for (const g of grown.allowed) {
      console.log(
        `kit-adoption: ${ALLOW_FILE}: ${g.block} gained "${g.key}", ALLOWED by rule ${g.rule}: ${g.why} ` +
          `(merge-base ${atBase.base.slice(0, 8)}).`,
      )
    }
    for (const g of grown.refused) {
      console.error(
        `kit-adoption: ${ALLOW_FILE}: ${g.block} gained "${g.key}", which the merge-base ` +
          `${atBase.base.slice(0, 8)} with origin/main does not hold. Refused: ${g.why}. Fix the ` +
          `screen instead of excusing it.`,
      )
    }
  }
  const lanes = {}
  for (const lane of listed.values()) lanes[lane] = (lanes[lane] ?? 0) + 1
  const byLane = Object.entries(lanes).sort().map(([l, n]) => `${l} ${n}`).join(', ')
  if (errors.length || unlisted.length || stale.length || (grown !== null && grown.refused.length > 0)) process.exit(1)
  console.log(
    `kit-adoption: ${result.routes.length} routes, ${result.violations.length} violations, every one ` +
      `listed; ${listed.size} allow-list entries still owed (${byLane || 'none'}).`,
  )
}

/* ---- the self-test ------------------------------------------------------------------------- */

const KIT_INDEX = "export { Page } from './Page'\n"
const KIT_PAGE = 'export function Page({ children }) { return <main data-bn-page="">{children}</main> }\n'

function tree(extra, routes = "{ path: '/', label: 'Home', view: Home, persona: 'owner' }", imports = "import { Home } from './Home'") {
  const files = new Map([
    ['app/src/App.tsx', `${imports}\nexport const ROUTES: readonly Route[] = [\n  ${routes},\n]\n`],
    ['app/src/kit/index.tsx', KIT_INDEX],
    ['app/src/kit/Page.tsx', KIT_PAGE],
    ['app/src/Home.tsx', "import { Page } from './kit'\nexport function Home() { return <Page title=\"Home\"><p>hi</p></Page> }\n"],
  ])
  for (const [k, v] of Object.entries(extra)) {
    if (v === null) files.delete(k)
    else files.set(k, v)
  }
  return files
}

function selfTest() {
  const cases = []
  const add = (name, fn) => cases.push({ name, fn })
  const outcome = (files, allow = { static: {} }) => {
    const { violations } = analyze(files)
    return { violations, ...judge(violations, allow) }
  }
  const has = (list, file, rule) => list.some((v) => v.file === file && v.rule === rule)
  const green = (r) => r.errors.length === 0 && r.unlisted.length === 0 && r.stale.length === 0

  add('a route view that renders <Page> from ./kit is green', () => green(outcome(tree({}))))
  add('a route view without <Page> is red (R1, unlisted)', () => {
    const r = outcome(tree({ 'app/src/Home.tsx': 'export function Home() { return <main><h1>Home</h1></main> }\n' }))
    return has(r.unlisted, 'app/src/Home.tsx', 'R1')
  })
  add('the same view, listed file -> R1 -> lane, is green', () =>
    green(outcome(tree({ 'app/src/Home.tsx': 'export function Home() { return <main /> }\n' }), { static: { 'app/src/Home.tsx': { R1: 'home' } } })))
  add('<Page> imported from ./kit/Page is green', () =>
    green(outcome(tree({ 'app/src/Home.tsx': "import { Page } from './kit/Page'\nexport const Home = () => <Page />\n" }))))
  add('<Page> reached through a component imported from another screen is green', () =>
    green(outcome(tree({
      'app/src/Ship.tsx': "import { Hub } from './Orders'\nexport function Ship() { return <Hub stage=\"ship\" /> }\n",
      'app/src/Orders.tsx': "import { Page } from './kit'\nexport function Hub() { return <Page /> }\n",
    }, "{ path: '/', label: 'Home', view: Home }, { path: '/ship', label: 'Shipping', view: Ship }",
    "import { Home } from './Home'\nimport { Ship } from './Ship'"))))
  add('<Page> reached through a local component in the same file is green', () =>
    green(outcome(tree({ 'app/src/Home.tsx': "import { Page } from './kit'\nfunction Body() { return <Page /> }\nexport function Home() { return <Body /> }\n" }))))
  add('a component called Page that is not the kit\'s is red', () => {
    const r = outcome(tree({ 'app/src/Home.tsx': "import { Page } from './MyPage'\nexport function Home() { return <Page /> }\n", 'app/src/MyPage.tsx': 'export function Page() { return <main /> }\n' }))
    return has(r.unlisted, 'app/src/Home.tsx', 'R1')
  })
  add('role="dialog" in a screen is red (R2-dialog)', () => {
    const r = outcome(tree({ 'app/src/Screen.tsx': 'export const S = () => <div role="dialog" />\n' }))
    return has(r.unlisted, 'app/src/Screen.tsx', 'R2-dialog')
  })
  add("role={open ? 'alertdialog' : undefined} in a screen is red", () => {
    const r = outcome(tree({ 'app/src/Screen.tsx': "export const S = ({ open }) => <div role={open ? 'alertdialog' : undefined} />\n" }))
    return has(r.unlisted, 'app/src/Screen.tsx', 'R2-dialog')
  })
  add('role="dialog" inside app/src/kit/ is green', () =>
    green(outcome(tree({ 'app/src/kit/overlay.tsx': 'export const Sheet = () => <div role="dialog" className="bn-sheet" />\n' }))))
  add('a stale allow entry is red (the file no longer breaks the rule)', () => {
    const r = outcome(tree({}), { static: { 'app/src/Home.tsx': { 'R2-dialog': 'home' } } })
    return r.stale.some((s) => s.file === 'app/src/Home.tsx' && s.rule === 'R2-dialog')
  })
  add('an allow entry for a file that does not exist is red (stale)', () => {
    const r = outcome(tree({}), { static: { 'app/src/Gone.tsx': { R1: 'home' } } })
    return r.stale.some((s) => s.file === 'app/src/Gone.tsx')
  })
  add('an unlisted violation is red even when the same file lists another rule', () => {
    const r = outcome(tree({ 'app/src/Screen.tsx': 'export const S = () => <><div role="dialog" /><select /></>\n' }), { static: { 'app/src/Screen.tsx': { 'R2-dialog': 'x' } } })
    return has(r.unlisted, 'app/src/Screen.tsx', 'R2-select') && !has(r.unlisted, 'app/src/Screen.tsx', 'R2-dialog')
  })
  add('<input type="search"> is red; <input type="text"> is green', () => {
    const red = outcome(tree({ 'app/src/S.tsx': 'export const S = () => <input type="search" />\n' }))
    const ok = outcome(tree({ 'app/src/S.tsx': 'export const S = () => <input type="text" />\n' }))
    return has(red.unlisted, 'app/src/S.tsx', 'R2-search') && green(ok)
  })
  add('<input type="search"> inside SearchField.tsx, the primitive itself, is green', () =>
    green(outcome(tree({ 'app/src/SearchField.tsx': 'export const SearchField = () => <input type="search" />\n' }))))
  add('Gallery.tsx may draw kit classes (specimens) but not a raw <select>', () => {
    const r = outcome(tree({ 'app/src/Gallery.tsx': 'export const G = () => <><span className="bn-money" /><select /></>\n' }))
    return !has(r.unlisted, 'app/src/Gallery.tsx', 'R2-class') && has(r.unlisted, 'app/src/Gallery.tsx', 'R2-select')
  })
  add('a raw <select> is red', () => has(outcome(tree({ 'app/src/S.tsx': 'export const S = () => <select><option /></select>\n' })).unlisted, 'app/src/S.tsx', 'R2-select'))
  add('a reserved class in className, a template, a ternary, .className= and classList.add is red', () => {
    const src = [
      'export const A = () => <span className="bn-money x" />',
      "export const B = ({ on }) => <p className={`row ${on ? 'bn-empty-state' : ''}`} />",
      "export const C = () => <div className={['bn-notice', 'y'].join(' ')} />",
      "export function d(el) { el.className = 'bn-skeleton'; el.classList.add('bn-sheet-left') }",
    ].join('\n')
    const hits = analyze(tree({ 'app/src/S.tsx': src })).violations.filter((v) => v.rule === 'R2-class').map((v) => v.detail)
    return ['bn-money', 'bn-empty-state', 'bn-notice', 'bn-skeleton', 'bn-sheet-left'].every((t) => hits.includes(t))
  })
  add('a class that only shares a prefix with an exact reservation is green (bn-page-head, bn-money-ish)', () =>
    green(outcome(tree({ 'app/src/S.tsx': 'export const S = () => <div className="bn-page-head bn-money-ish bn-headline" />\n' }))))
  add('toLocaleDateString and Intl.DateTimeFormat in a screen are red; in dates.ts green', () => {
    const red = outcome(tree({ 'app/src/S.tsx': "export const s = (d) => d.toLocaleDateString() + new Intl.DateTimeFormat('en').format(d)\n" }))
    const ok = outcome(tree({ 'app/src/dates.ts': "export const s = (d) => d.toLocaleTimeString() + new Intl.DateTimeFormat('en').format(d)\n" }))
    return red.violations.filter((v) => v.rule === 'R2-date').length === 2 && green(ok)
  })
  add('`$${n.toFixed(2)}` in a screen is red; in money.ts green; `${n.toFixed(1)}%` green', () => {
    const red = outcome(tree({ 'app/src/S.tsx': 'export const s = (n) => `-$${Math.abs(n).toFixed(2)}`\n' }))
    const ok = outcome(tree({ 'app/src/money.ts': 'export const s = (n) => `$${n.toFixed(2)}`\n', 'app/src/P.tsx': 'export const p = (n) => `${n.toFixed(1)}%`\n' }))
    return has(red.unlisted, 'app/src/S.tsx', 'R2-money') && green(ok)
  })
  add('an allow entry naming an unknown rule is refused', () => outcome(tree({}), { static: { 'app/src/Home.tsx': { R9: 'home' } } }).errors.length === 1)
  add('an allow entry with no lane is refused', () => outcome(tree({}), { static: { 'app/src/Home.tsx': { R1: '' } } }).errors.length === 1)
  add('a ROUTES table this reader cannot read is a loud failure, never a pass', () => {
    try {
      analyze(tree({ 'app/src/App.tsx': 'export const ROUTES = makeRoutes()\n' }))
      return false
    } catch (err) {
      return /not an array literal/.test(err.message)
    }
  })
  add('an empty ROUTES table is a loud failure, never a pass over nothing', () => {
    try {
      analyze(tree({ 'app/src/App.tsx': 'export const ROUTES = []\n' }))
      return false
    } catch (err) {
      return /empty/.test(err.message)
    }
  })
  add('readRoutes carries path, label, title, persona and the view\'s own file', () => {
    const routes = readRoutes(tree({}, "{ path: '/k', label: 'Kit', title: 'The kit', view: Home, persona: 'owner' }"))
    const r = routes[0]
    return routes.length === 1 && r.path === '/k' && r.label === 'Kit' && r.title === 'The kit' && r.persona === 'owner' && r.file === 'app/src/Home.tsx'
  })

  /* R1: order, depth and cycles (F6). */
  const chain = (n, last) => Array.from({ length: n }, (_, i) => `function L${i}() { return <${i + 1 < n ? `L${i + 1}` : last} /> }`).join('\n')
  add('R1 does not depend on JSX order: a component first met deep in one branch is still found through a short one', () => {
    /* Home renders <L0/> first. L0, L1, L2 lead to C at depth 4, the old cap: the old reader
       looked at C's own tags, found no <Page>, marked C visited and stopped. Then Home renders
       <P/>, and P renders C at depth 2, but C was already visited. C renders D, and D renders
       <Page>. The old reader said R1 (measured against the old file); the answer is green. */
    const src = [
      "import { Page } from './kit'",
      chain(3, 'C'),
      'function D() { return <Page /> }',
      'function C() { return <D /> }',
      'function P() { return <C /> }',
      'export function Home() { return <><L0 /><P /></> }',
    ].join('\n')
    return green(outcome(tree({ 'app/src/Home.tsx': src })))
  })
  add('R1 follows a chain deeper than four levels to <Page>', () =>
    green(outcome(tree({ 'app/src/Home.tsx': `import { Page } from './kit'\n${chain(7, 'Page')}\nexport function Home() { return <L0 /> }\n` }))))
  add('R1 ends a cycle that never reaches <Page>, and says R1', () => {
    const src = 'function A() { return <B /> }\nfunction B() { return <A /> }\nexport function Home() { return <A /> }\n'
    return has(outcome(tree({ 'app/src/Home.tsx': src })).unlisted, 'app/src/Home.tsx', 'R1')
  })

  /* R1: a view imported as a default export. */
  const defaultRoute = ["{ path: '/', label: 'Home', view: Home }", "import Home from './Home'"]
  add('a view imported as a default export (`export default function`) that renders <Page> is green', () =>
    green(outcome(tree({ 'app/src/Home.tsx': "import { Page } from './kit'\nexport default function Home() { return <Page /> }\n" }, ...defaultRoute))))
  add('a view imported as a default export (`export default Home`, and memo) is green', () =>
    green(outcome(tree({ 'app/src/Home.tsx': "import { Page } from './kit'\nfunction Home() { return <Page /> }\nexport default Home\n" }, ...defaultRoute))) &&
    green(outcome(tree({ 'app/src/Home.tsx': "import { memo } from 'react'\nimport { Page } from './kit'\nexport default memo(() => <Page />)\n" }, ...defaultRoute))))
  add('a default-export view without <Page> is R1, and the message names the view, not "default"', () => {
    const r = outcome(tree({ 'app/src/Home.tsx': 'export default function Home() { return <main /> }\n' }, ...defaultRoute))
    const v = r.unlisted.find((x) => x.rule === 'R1')
    return v !== undefined && v.file === 'app/src/Home.tsx' && v.detail.includes('Home (the default export)')
  })
  add('a screen component imported as a default export is followed', () =>
    green(outcome(tree({
      'app/src/Home.tsx': "import Body from './Body'\nexport function Home() { return <Body /> }\n",
      'app/src/Body.tsx': "import { Page } from './kit'\nexport default function Body() { return <Page /> }\n",
    }))))

  /* R2: the shapes F4 added. Each red in a screen; the money and date ones green in their home. */
  const rule = (src, r, file = 'app/src/S.tsx') => outcome(tree({ [file]: src })).violations.filter((v) => v.file === file && v.rule === r).length
  add('a native <dialog> in a screen is R2-dialog', () => rule('export const S = () => <dialog open />\n', 'R2-dialog') === 1)
  add('a text input labelled like a search box is R2-search (type text or none; placeholder or aria-label)', () =>
    rule('export const S = () => <input type="text" placeholder="Search cards" />\n', 'R2-search') === 1 &&
    rule('export const S = () => <input aria-label="Filter the rows" />\n', 'R2-search') === 1 &&
    rule("export const S = () => <input placeholder={x ? 'Find a box' : 'Look up a card'} />\n", 'R2-search') === 1)
  add('a text input labelled otherwise, or a number input, is not R2-search', () =>
    rule('export const S = () => <><input type="text" placeholder="Name" /><input type="number" aria-label="Search depth" /></>\n', 'R2-search') === 0)
  add('toLocaleString with a date or time option is R2-date; bare or with number options is not', () =>
    rule("export const s = (d) => d.toLocaleString(undefined, { month: 'short', day: 'numeric' })\n", 'R2-date') === 1 &&
    rule("export const s = (n) => n.toLocaleString() + n.toLocaleString('en-US', { maximumFractionDigits: 2 })\n", 'R2-date') === 0)
  add("Intl.NumberFormat or toLocaleString with style 'currency' is R2-money, and green in money.ts", () =>
    rule("export const f = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })\n", 'R2-money') === 1 &&
    rule("export const f = (n) => Intl.NumberFormat('en-US', { currency: 'USD' }).format(n)\n", 'R2-money') === 1 &&
    rule("export const s = (n) => n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })\n", 'R2-money') === 1 &&
    rule("export const f = new Intl.NumberFormat('en-US', { style: 'percent' })\n", 'R2-money') === 0 &&
    green(outcome(tree({ 'app/src/money.ts': "export const f = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })\n" }))))
  add("`'$' + x.toFixed(2)`, `'Total: $' + x` and `a + '$' + x` are R2-money; a regex's `+ '$'` is not", () =>
    rule("export const s = (x) => '$' + x.toFixed(2)\n", 'R2-money') === 1 &&
    rule("export const s = (x) => 'Total: $' + x\n", 'R2-money') === 1 &&
    rule("export const s = (a, x) => a + '$ ' + x\n", 'R2-money') === 1 &&
    rule("export const r = (x) => new RegExp('^' + x + '$')\n", 'R2-money') === 0)
  add('a template `$` or `$ ` before any interpolation is R2-money, with or without toFixed; `${n}%` is not', () =>
    rule('export const s = (x) => `$${x}`\n', 'R2-money') === 1 &&
    rule('export const s = (x) => `Over $ ${x} each`\n', 'R2-money') === 1 &&
    rule('export const s = (n) => `${n}% and ${n} items`\n', 'R2-money') === 0)
  add("a `$` in JSX text, or a {'$'} child, before {...} is R2-money; `{n} items` is not", () =>
    rule('export const S = ({ p }) => <span>${p}</span>\n', 'R2-money') === 1 &&
    rule('export const S = ({ p }) => <span>could be $ {p}</span>\n', 'R2-money') === 1 &&
    rule("export const S = ({ p }) => <span>{'$'}{p}</span>\n", 'R2-money') === 1 &&
    rule('export const S = ({ n }) => <span>{n} items, $5 flat</span>\n', 'R2-money') === 0)
  add('every money shape is green inside money.ts, its home', () =>
    green(outcome(tree({ 'app/src/money.ts': "export const a = (x) => `$${x}`\nexport const b = (x) => '$' + x\n" }))))

  /* ONLY SHRINKS (F3): the growth read against the merge-base. */
  const base = { static: { 'app/src/A.tsx': { R1: 'home', 'R2-class': 'home' } }, runtime: { '/': { page: 'home' } } }
  /* The rules defined at the merge-base: every rule this file knows today, minus R2-new, which
     stands for a rule born on the branch. */
  const baseRules = { static: new Set(Object.keys(RULES)), runtime: new Set(['page', 'h1', 'width', 'top', 'scroll', 'title', 'palette', 'keys']) }
  const clone = (o) => JSON.parse(JSON.stringify(o))
  const refusedOnly = (g, block, key) => g.refused.length === 1 && g.allowed.length === 0 && g.refused[0].block === block && g.refused[0].key === key
  add('a new static key (a new file) for an existing rule is refused, so red', () => {
    const head = clone(base)
    head.static['app/src/B.tsx'] = { R1: 'x' }
    return refusedOnly(growth(base, head, baseRules), 'static', 'app/src/B.tsx -> R1')
  })
  add('a new key for an existing rule under a file the list already names is refused, so red', () => {
    const head = clone(base)
    head.static['app/src/A.tsx']['R2-date'] = 'home'
    return refusedOnly(growth(base, head, baseRules), 'static', 'app/src/A.tsx -> R2-date')
  })
  add('a new runtime key for an existing assertion is refused, so red', () => {
    const head = clone(base)
    head.runtime['/']['width'] = 'home'
    return refusedOnly(growth(base, head, baseRules), 'runtime', '/ -> width')
  })
  add('a new key for a rule born on this branch (not defined at the merge-base) is allowed, so green, and says why', () => {
    const head = clone(base)
    head.static['app/src/B.tsx'] = { 'R2-new': 'x' }
    head.runtime['/']['focus'] = 'shell'
    const g = growth(base, head, baseRules)
    return g.refused.length === 0 && g.allowed.length === 2 &&
      g.allowed.some((a) => a.rule === 'R2-new' && /born on this branch/.test(a.why)) && g.allowed.some((a) => a.rule === 'focus')
  })
  add('a rule definition the merge-base read could not parse excuses nothing: growth is refused', () => {
    const head = clone(base)
    head.static['app/src/B.tsx'] = { 'R2-new': 'x' }
    const g = growth(base, head, { static: null, runtime: null })
    return g.refused.length === 1 && /could not be read/.test(g.refused[0].why)
  })
  add('a removed key is the list shrinking, so green; a changed lane is not growth', () => {
    const head = clone(base)
    delete head.static['app/src/A.tsx']['R2-class']
    delete head.runtime['/']
    head.static['app/src/A.tsx'].R1 = 'capture'
    const g = growth(base, head, baseRules)
    return g.refused.length === 0 && g.allowed.length === 0
  })
  add('no allow list at the merge-base fails open (null), never a silent pass', () => growth(null, base) === null)
  add('the git read sees its subject: the committed list and both rule definitions at HEAD', () => {
    const at = allowAtBase('HEAD')
    if (at.allow === null) throw new Error(`nothing to read: ${at.reason}`)
    const head = clone(at.allow)
    head.static['app/src/NotARealScreen.tsx'] = { R1: 'x' }
    const same = growth(at.allow, at.allow, at.rules)
    const more = growth(at.allow, head, at.rules)
    return at.rules.static !== null && Object.keys(RULES).every((r) => at.rules.static.has(r)) &&
      at.rules.runtime !== null && ['page', 'title', 'palette', 'keys'].every((a) => at.rules.runtime.has(a)) &&
      same.refused.length === 0 && same.allowed.length === 0 && more.refused.length === 1
  })

  let failed = 0
  for (const c of cases) {
    let ok = false
    let why = ''
    try {
      ok = c.fn() === true
    } catch (err) {
      why = ` (threw: ${err.message})`
    }
    if (!ok) failed += 1
    console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${c.name}${why}`)
  }
  console.log(`kit-adoption self-test: ${cases.length - failed} of ${cases.length} cases pass`)
  if (failed > 0) process.exit(1)
}

/* ---- entry --------------------------------------------------------------------------------- */

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)
if (isMain) {
  const args = process.argv.slice(2)
  if (args.includes('--self-test')) selfTest()
  else if (args.includes('--routes')) {
    try {
      process.stdout.write(JSON.stringify(readRoutes(readTree())))
    } catch (err) {
      console.error(`kit-adoption: ${err.message}`)
      process.exit(1)
    }
  } else run()
}
