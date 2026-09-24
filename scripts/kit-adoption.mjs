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
 *              from another screen file, up to MAX_DEPTH levels. `Shipping` renders `OrdersHub`
 *              from `./Orders`, so if `OrdersHub` renders `<Page>`, both routes pass. It never
 *              follows a tag into the kit itself: a kit wrapper is not a screen's `<Page>`.
 *   R2-*       Outside `app/src/kit/**`, no screen hand-rolls a kit primitive:
 *                R2-dialog   `role="dialog"` or `role="alertdialog"` (the kit has Sheet, Modal,
 *                            Popover and ConfirmSheet in `kit/overlay.tsx`)
 *                R2-search   `<input type="search">` outside `app/src/SearchField.tsx`, which is
 *                            that primitive
 *                R2-select   a raw `<select>` (the kit's Select)
 *                R2-class    a kit-reserved class name in `className`, `.className =` or
 *                            `classList.add(...)`: RESERVED_EXACT and RESERVED_PREFIX below.
 *                            `app/src/Gallery.tsx` is exempt from this one rule: it is the kit's
 *                            specimen sheet and draws each kit class raw on purpose
 *                R2-date     `toLocaleDateString`, `toLocaleTimeString` or `Intl.DateTimeFormat`
 *                            outside `app/src/dates.ts`
 *                R2-money    a template literal with `$` immediately before a `${...}` that calls
 *                            `.toFixed(`, outside `app/src/money.ts`
 *
 * THE EXCEPTIONS ARE A SHRINKING OFFENDER LIST, NEVER A PINNED COUNT (the owner's ruling on Q3,
 * 2026-09-23). `scripts/kit-adoption-allow.json`'s `static` block is file -> rule -> lane: the
 * lane that owes the migration. It FAILS on a violation it does not list, and it FAILS on an
 * entry that no longer matches a violation (a stale entry), so the list can only shrink, and a
 * lane that migrates a screen must delete its own entries in the same commit. An entry covers
 * every occurrence of that rule in that file. It is a per-file debt, never a count.
 *
 * `runtime` in the same file belongs to `app/tests/scaffold.spec.ts`, which validates it. This
 * script only checks that the block is an object.
 *
 * WHAT IS NOT SEEN, said here so nobody reads green as more than it is:
 *   - a class name, role or type that reaches JSX through a variable (`const c = 'bn-money'`,
 *     `<div className={c}>`) and not as a literal inside the attribute. The same data-flow gap
 *     `user-strings.mjs` names.
 *   - a view that renders `<Page>` on one branch and something else on another. R1 asks whether
 *     the view reaches `<Page>` at all. `scaffold.spec.ts` asserts what a browser actually drew.
 *   - a view assigned to a variable and rendered through it (`const V = a ? A : B; <V/>`).
 *
 *     node scripts/kit-adoption.mjs              the check (exit 1 on any finding)
 *     node scripts/kit-adoption.mjs --self-test  the checker against in-memory fixtures
 *     node scripts/kit-adoption.mjs --routes     ROUTES as JSON, for scaffold.spec.ts
 *
 * NEVER WRITES (D18). The self-test builds its fixtures as in-memory maps of path -> source and
 * touches no disk.
 */

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
const MAX_DEPTH = 4

/** Every rule id the allow list may name. An entry naming anything else is refused. */
export const RULES = {
  R1: 'the route view never renders <Page> from the kit',
  'R2-dialog': 'role="dialog" or role="alertdialog" outside the kit (use Sheet, Modal, Popover)',
  'R2-search': '<input type="search"> outside SearchField (use SearchField)',
  'R2-select': 'a raw <select> outside the kit (use Select)',
  'R2-class': 'a kit-reserved class name outside the kit',
  'R2-date': 'a hand-rolled date format outside app/src/dates.ts',
  'R2-money': 'a hand-rolled $ amount (`$${x.toFixed(...)}`) outside app/src/money.ts',
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

/** `import { A as B } from './x'` -> B: { file, imported: 'A' }; `import * as K` -> K: { file, ns }. */
function importsOf(sf, rel, reader) {
  const named = new Map()
  const namespaces = new Map()
  for (const st of sf.statements) {
    if (!ts.isImportDeclaration(st) || !st.importClause || !ts.isStringLiteral(st.moduleSpecifier)) continue
    const file = reader.resolve(rel, st.moduleSpecifier.text)
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

/** A top-level component named `name`: a function declaration, or `const name = <function>`,
 *  or `const name = memo(<function>)`. Or a re-export `export { name } from './x'`. */
function findComponent(sf, name) {
  for (const st of sf.statements) {
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
 *  it renders? Returns the chain that reached it, or null. */
function rendersPage(rel, name, reader, depth = 0, seen = new Set()) {
  const key = `${rel}#${name}`
  if (seen.has(key) || rel.startsWith(KIT_DIR)) return null
  seen.add(key)
  const sf = reader.parse(rel)
  if (sf === null) return null
  const found = findComponent(sf, name)
  if (found === null) return null
  if (found.reexport !== undefined) {
    const next = reader.resolve(rel, found.reexport)
    return next === null ? null : rendersPage(next, found.imported, reader, depth, seen)
  }
  const { named, namespaces } = importsOf(sf, rel, reader)
  const tags = jsxTags(found.node)
  for (const tag of tags) {
    const imp = named.get(tag)
    if (imp && KIT_MODULES.has(imp.file) && imp.imported === 'Page') return [`${rel}#${name}`]
    const dot = tag.indexOf('.')
    if (dot > 0 && tag.slice(dot + 1) === 'Page' && KIT_MODULES.has(namespaces.get(tag.slice(0, dot)))) return [`${rel}#${name}`]
  }
  if (depth >= MAX_DEPTH) return null
  for (const tag of new Set(tags)) {
    if (!/^[A-Z]/.test(tag) || tag.includes('.')) continue
    const imp = named.get(tag)
    let chain = null
    if (imp) {
      if (imp.file !== null && !imp.file.startsWith(KIT_DIR)) chain = rendersPage(imp.file, imp.imported, reader, depth + 1, seen)
    } else if (findComponent(sf, tag) !== null) {
      chain = rendersPage(rel, tag, reader, depth + 1, seen)
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
    let view = viewName
    if (imp) {
      file = imp.file
      view = imp.imported
    } else if (findComponent(sf, viewName) !== null) {
      file = APP_FILE
    }
    if (file === null) throw new Error(`${where}: the view ${viewName} resolves to no file under ${APP_SRC}`)
    routes.push({
      path: props.path,
      label: props.label,
      title: typeof props.title === 'string' ? props.title : null,
      persona: typeof props.persona === 'string' ? props.persona : null,
      view,
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
      if (tag === 'input' && attrLiterals(attr(n, 'type')).includes('search')) add('R2-search', n, '<input type="search">')
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
        if (before.endsWith('$') && callsToFixed(span.expression)) add('R2-money', span.expression, '`$${... .toFixed(...)}`')
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
    if (rendersPage(route.file, route.view, reader) === null) {
      const sf = reader.parse(route.file)
      const found = sf === null ? null : findComponent(sf, route.view)
      const line = found?.node ? lineOf(sf, found.node) : 1
      violations.push({ file: route.file, rule: 'R1', line, detail: `the view ${route.view} for ${route.path}` })
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
  const lanes = {}
  for (const lane of listed.values()) lanes[lane] = (lanes[lane] ?? 0) + 1
  const byLane = Object.entries(lanes).sort().map(([l, n]) => `${l} ${n}`).join(', ')
  if (errors.length || unlisted.length || stale.length) process.exit(1)
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
