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
 *                                `$`, then any white space (`$${x}`, `-$ ${n.toFixed(2)}`)
 *                              - a `+` whose left side ends in a string literal that ends in `$`,
 *                                then any white space (`'$' + x.toFixed(2)`)
 *                              - JSX text that ends in `$` (then any white space) directly
 *                                before a `{...}` child, or a `{'$'}` child directly before one
 *                              - `Intl.NumberFormat(...)` or `.toLocaleString(...)` with an
 *                                object-literal option `style: 'currency'` or a `currency` key
 *                            HEURISTIC, said plainly: a `$` before an interpolation is read as a
 *                            price, which it is in this product. An options object held in a
 *                            variable is not seen.
 *                R2-icon-only-button
 *                            a hand-rolled icon-only control (owner's ruling, 2026-09-24,
 *                            ICONOGRAPHY; D-icon-buttons): a native `<button>` whose only
 *                            non-blank child is an `<Icon>`, or any element carrying the
 *                            `iconOnly` JSX attribute (the kit's own `Button` prop, read by
 *                            presence, never by its value) — the kit has `IconButton` for
 *                            this now, with a required label and a tooltip.
 *                R2-header-actions
 *                            the owner's tighten ruling, 2026-09-24 ("i question whether they
 *                            deserve all that real estate... egregious"): a `<Page>` or
 *                            `<PageHeader>`'s `actions` prop holding MORE THAN ONE worded
 *                            `<Button>` (not `iconOnly`, not an `<IconButton>`, real visible
 *                            text by R2-icon-only-button's own `isIconLike`/`aggregate`
 *                            reader). A `<Button>` inside a `Sheet`/`Modal`/`Popover`/
 *                            `ConfirmSheet` reached from the header is not counted — it opens a
 *                            dialog, which is not the header row itself.
 *                R2-filter-row
 *                            the same ruling: a screen that renders `SearchField` beside a
 *                            facet control (`Select`, `FilterChips`, `SortControl`,
 *                            `HideToggle`) with no `FilterBar` anywhere in the file hand-built
 *                            the row `FilterBar` exists to be. FILE-LEVEL, not per-element: it
 *                            answers "does this file's toolbar go through FilterBar at all",
 *                            not "is this exact SearchField beside that exact Select".
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
 * read, at the merge-base or at HEAD, allows nothing. AND ONLY WHILE NO RULE WAS REMOVED (the
 * orchestrator's option a, 2026-09-23): if any rule the merge-base defines, in either block, is
 * missing at HEAD, ALL growth is refused, and the message names the missing rule. Otherwise a
 * rename (R2-money -> R2-cash) would pass as a born rule and bring every old debt back under
 * the new name. Once the branch merges, its new rule exists at every later merge-base, so from
 * then on that rule only shrinks too. IT FAILS OPEN, AND PRINTS WHY: no git, no
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
 *   - each HEURISTIC above, past the edge it states. Named, because each is a real shape:
 *       - a `$` inside its own element before a value (`<b>$</b>{x}`): the `$` is not the text
 *         directly before the `{...}`.
 *       - `'$'.concat(x)`, and any other join that is not `+`, a template or JSX.
 *       - `Intl` reached by destructuring (`const { NumberFormat } = Intl`), through
 *         `globalThis.Intl` or `window.Intl`, or by a bracket (`Intl['NumberFormat']`).
 *       - `Intl.RelativeTimeFormat`, and every other `Intl` formatter than DateTimeFormat and
 *         NumberFormat: a relative date ("3 days ago") is a date format R2-date does not see.
 *       - a date method called by a bracket (`d['toLocaleDateString']()`).
 *       - `role="searchbox"` (or `role="search"`) on an element: only `<input>` is read.
 *       - R2-header-actions: a custom component that renders a `<Button>` inside itself
 *         (`<SendButton/>`) is not resolved — only a literal `<Button>` in the `actions` JSX is
 *         counted. A `<Menu>`/trigger pattern already reads as one control either way.
 *       - R2-filter-row: a facet built as a bare `<Chip>` row rather than through
 *         `FilterChips`/`Select` is not seen — the rule reads the kit's own facet tag names,
 *         not "any control that behaves like a facet".
 *       - a role or an input type given by a spread (`<div {...props}>`, `<input {...p}>`):
 *         only a named attribute is read.
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
/** THE FULFILLER'S OWN FILES (`docs/specs/iconography.md` section 2, rule 1): the rule does
 *  not apply there. Exempt from `R2-icon-only-button` only, alongside `SPECIMEN_FILES`. This
 *  cannot reach `CardLocations.tsx`'s `FulfillerCard` branch, which shares a file with the
 *  owner's own rows — a component-level exemption is not this reader's shape, so that branch
 *  is read by the owner's rule like any other, a known gap named here rather than hidden. */
export const FULFILLER_FILES = ['app/src/Fulfillment.tsx', 'app/src/PullConfirm.tsx']
const ALLOW_FILE = 'scripts/kit-adoption-allow.json'
/** R2-icon-only-button's clause (c): a `Button` whose literal label starts with one of these,
 *  and whose `variant` cannot be shown to be always `primary` or `danger-solid` — the two
 *  variants the ICONOGRAPHY rule always leaves as words (`docs/specs/iconography.md` section
 *  2, rules 2 and 4). Longer phrases first, so `Mark sold` is not shadowed by nothing shorter.
 *  Hold, Release, Reveal, Hide and Clear were missing (round 2's review): section 2 step 6
 *  names all five. Matched case-insensitively (round 2): a screen's own `undo` reads the same
 *  as `Undo` to a person, and the check should too. */
export const VOCAB_VERBS = [
  'Mark sold', 'Undo', 'Retire', 'Edit', 'Rename', 'Delete', 'Forget', 'Copy', 'Download',
  'Open as page', 'Close', 'Dismiss', 'Reload', 'Manage', 'Options', 'Hold', 'Release',
  'Reveal', 'Hide', 'Clear',
]
const VOCAB_VERB_RE = new RegExp(`^(${VOCAB_VERBS.map((v) => v.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})\\b`, 'i')
/** The variants clause (c) never flags: the vocabulary word IS the label there on purpose
 *  (Mark sold as the only primary in its sector, Delete behind a `danger-solid` confirm). */
const WORDED_VARIANTS = new Set(['primary', 'danger-solid'])

/** Every rule id the allow list may name. An entry naming anything else is refused. */
export const RULES = {
  R1: 'the route view never renders <Page> from the kit',
  'R2-dialog': 'role="dialog", role="alertdialog" or a native <dialog> outside the kit (use Sheet, Modal, Popover)',
  'R2-search': '<input type="search">, or a text input labelled like a search box, outside SearchField (use SearchField)',
  'R2-select': 'a raw <select> outside the kit (use Select)',
  'R2-class': 'a kit-reserved class name outside the kit',
  'R2-date': 'a hand-rolled date format outside app/src/dates.ts',
  'R2-money': 'a hand-rolled $ amount outside app/src/money.ts (use the kit\'s Money, or money() from money.ts)',
  'R2-icon-only-button': 'a hand-rolled icon-only control outside the kit (use IconButton)',
  'R2-header-actions': 'more than one worded <Button> in a <Page>/<PageHeader> actions slot (the rest must be IconButtons or a More menu)',
  'R2-filter-row': 'a hand-built filter row (a SearchField beside a facet control) that does not go through the kit FilterBar',
}

/** R2-header-actions: the tags whose `actions` prop draws a page header (`Page.tsx`'s and
 *  `kit/index.tsx`'s `PageHeader`, both `<div className="bn-head-actions">{actions}</div>`).
 *  A `<Button>` inside is opaque once it is inside one of these: a dialog opened FROM the
 *  header is not a second header, so its own buttons (Save/Cancel) are not counted. */
export const HEADER_TAGS = ['Page', 'PageHeader']
const OVERLAY_TAGS = new Set(['Sheet', 'Modal', 'Popover', 'ConfirmSheet'])
/** R2-filter-row: the kit's own facet controls. A screen assembling any of these beside a
 *  `SearchField`, without a `FilterBar` anywhere in the file, hand-built the row FilterBar
 *  already is. */
export const FACET_TAGS = ['Select', 'FilterChips', 'SortControl', 'HideToggle']

/** R2-header-actions: how many `<Button>` elements inside `node` read as a WORDED press — not
 *  `iconOnly` (attribute or spread), and whose visible content is not purely an icon (reuse
 *  R2-icon-only-button's own `isIconLike`/`aggregate`: 'other' means real words are there).
 *  `<IconButton>` is a different tag and is never counted. A node inside an OVERLAY_TAGS
 *  container is not walked into: its buttons belong to the dialog it opens, not the header. */
function countWordedButtons(node, sf) {
  let count = 0
  const visit = (n) => {
    if (ts.isJsxElement(n) || ts.isJsxSelfClosingElement(n)) {
      const opening = ts.isJsxElement(n) ? n.openingElement : n
      const tag = opening.tagName.getText(sf)
      if (OVERLAY_TAGS.has(tag)) return
      if (tag === 'Button' && ts.isJsxElement(n)) {
        const iconOnly = attr(opening, 'iconOnly') !== undefined || hasSpreadIconOnly(opening)
        if (!iconOnly && aggregate(n.children.map((k) => isIconLike(k, sf))) === 'other') count += 1
      }
    }
    ts.forEachChild(n, visit)
  }
  visit(node)
  return count
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
const DOLLAR_END = /\$\s*$/

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

/** Does this expression END in a string literal that ends in `$` (then any white space)?
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

/* ---- R2-icon-only-button's clauses (b) and (c), round 2 -----------------------------------
 * A round-2 review found the first cut narrow both ways: it dropped every `{expression}`
 * sibling before counting a `<button>`'s children, so `<Icon/>{label}` (a REAL word beside
 * the glyph) read as icon-only; and it missed the shapes an icon-only control actually takes
 * once a screen is asked to hide one — a wrapper `<span>`, `{<Icon/>}`, a ternary of two
 * icons for a chevron toggle, an `aria-label`-only button with no children at all, a bare
 * `×` character standing in for a real icon, and `<a role="button">` wearing the same shape
 * as a `<button>`. Both functions below answer one question, over a JSX child: is this
 * ICON-LIKE (an `<Icon>`, an `<svg>`, or the literal `×`/`✕`/`✖`), BLANK (whitespace, or an
 * empty expression), or something else (real content, or a shape this reader cannot resolve)?
 * `aggregate` folds a list of those answers: all-icon (ignoring blanks) is `'icon'`, no
 * non-blank answer at all is `'blank'`, anything else is `'other'` — real content, which
 * clears the control. */
const FAKE_GLYPHS = new Set(['×', '✕', '✖'])

function aggregate(results) {
  const nonBlank = results.filter((r) => r !== 'blank')
  if (nonBlank.length === 0) return 'blank'
  return nonBlank.every((r) => r === 'icon') ? 'icon' : 'other'
}

function isIconLikeExpr(expr, sf) {
  const e = unwrap(expr)
  if (!e) return 'blank'
  if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) {
    const t = e.text.trim()
    if (t === '') return 'blank'
    return FAKE_GLYPHS.has(t) ? 'icon' : 'other'
  }
  if (ts.isJsxElement(e) || ts.isJsxSelfClosingElement(e) || ts.isJsxFragment(e)) return isIconLike(e, sf)
  if (ts.isConditionalExpression(e)) return aggregate([isIconLikeExpr(e.whenTrue, sf), isIconLikeExpr(e.whenFalse, sf)])
  if (ts.isBinaryExpression(e)) {
    const k = e.operatorToken.kind
    if (k === ts.SyntaxKind.QuestionQuestionToken || k === ts.SyntaxKind.BarBarToken) {
      return aggregate([isIconLikeExpr(e.left, sf), isIconLikeExpr(e.right, sf)])
    }
    if (k === ts.SyntaxKind.AmpersandAmpersandToken) return isIconLikeExpr(e.right, sf)
  }
  return 'other' // an identifier, a call, a member access: cannot be resolved, and is not seen
}

/** Is this one JSX child icon-like, blank, or other? A wrapper element (a `<span>`, a `<div>`)
 *  is transparent: its own children are read the same way, so `<span><Icon/></span>` is
 *  still `'icon'`. */
function isIconLike(node, sf) {
  if (ts.isJsxText(node)) {
    const t = node.text.trim()
    if (t === '') return 'blank'
    return FAKE_GLYPHS.has(t) ? 'icon' : 'other'
  }
  if (ts.isJsxExpression(node)) return node.expression ? isIconLikeExpr(node.expression, sf) : 'blank'
  if (ts.isJsxSelfClosingElement(node)) {
    const tag = node.tagName.getText(sf)
    return tag === 'Icon' || tag === 'svg' ? 'icon' : 'other'
  }
  if (ts.isJsxElement(node)) {
    const tag = node.openingElement.tagName.getText(sf)
    if (tag === 'Icon' || tag === 'svg') return 'icon'
    return aggregate(node.children.map((k) => isIconLike(k, sf)))
  }
  if (ts.isJsxFragment(node)) return aggregate(node.children.map((k) => isIconLike(k, sf)))
  return 'other'
}

/** Does this JSX opening tag carry a literal `role="button"`? Only a literal is seen, like
 *  every other heuristic here. */
function isRoleButton(opening, sf) {
  return attrLiterals(attr(opening, 'role')).includes('button')
}

/** Every string fragment a `<Button>`'s children start with, stopping at the first child
 *  that is not plain JSX text or a string-literal expression. `{'Undo'}` and `Undo {n}` both
 *  resolve to `"Undo"` this way — round 2's own finding: the count after "Undo" does not
 *  need to be read, only the word before it does, and `VOCAB_VERB_RE` is anchored at the
 *  start. */
function leadingLabelText(kids) {
  let text = ''
  for (const k of kids) {
    if (ts.isJsxText(k)) {
      text += k.text
      continue
    }
    if (ts.isJsxExpression(k) && k.expression) {
      const e = unwrap(k.expression)
      if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) {
        text += e.text
        continue
      }
    }
    break
  }
  return text.replace(/\s+/g, ' ').trim()
}

/** R2-icon-only-button clause (c)'s own `variant` reader: every possible literal value, or
 *  `null` when ANY branch cannot be resolved to a literal. Round 2's own finding: the
 *  general-purpose `literalsOf` silently DROPS an unresolvable branch of a `??`/`||`/`&&`/
 *  ternary and reports only the literal side it found, which let `variant={x ?? 'primary'}`
 *  read as safely `'primary'` when `x` could be anything at runtime. Here, one unresolved
 *  branch makes the whole expression unresolved — "unknown means not provably primary." */
function resolveVariantLiterals(expr) {
  const e = unwrap(expr)
  if (!e) return []
  if (ts.isStringLiteral(e) || ts.isNoSubstitutionTemplateLiteral(e)) return [e.text]
  if (ts.isJsxExpression(e)) return e.expression ? resolveVariantLiterals(e.expression) : []
  if (ts.isConditionalExpression(e)) {
    const a = resolveVariantLiterals(e.whenTrue)
    const b = resolveVariantLiterals(e.whenFalse)
    return a === null || b === null ? null : [...a, ...b]
  }
  if (ts.isBinaryExpression(e)) {
    const k = e.operatorToken.kind
    if (k === ts.SyntaxKind.QuestionQuestionToken || k === ts.SyntaxKind.BarBarToken || k === ts.SyntaxKind.AmpersandAmpersandToken) {
      /* BOTH SIDES, FOR ALL THREE OPERATORS (round 2's own finding, `c && 'primary'`): a
         non-literal left side of `&&` is not provably truthy, so the whole expression can
         still evaluate to that non-literal value, not to the literal right side. */
      const a = resolveVariantLiterals(e.left)
      const b = resolveVariantLiterals(e.right)
      return a === null || b === null ? null : [...a, ...b]
    }
  }
  return null
}

/** Clause (a), the spread shape: `<Button {...{ iconOnly: true }} icon="x">Close</Button>`.
 *  Round 2's own finding. Read by presence of the property name, never its value, matching
 *  the plain-attribute form. */
function hasSpreadIconOnly(opening) {
  const attrs = ts.isJsxSelfClosingElement(opening) || ts.isJsxOpeningElement(opening) ? opening.attributes.properties : []
  return attrs.some((a) => {
    if (!ts.isJsxSpreadAttribute(a)) return false
    const e = unwrap(a.expression)
    return ts.isObjectLiteralExpression(e) && e.properties.some((p) => p.name && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)) && p.name.text === 'iconOnly')
  })
}

/** Every R2 violation in one file: `{ rule, line, detail }`. */
function scanFile(rel, sf) {
  const hits = []
  const add = (rule, node, detail) => {
    if (HOME[rule] === rel) return
    if (rule === 'R2-class' && SPECIMEN_FILES.includes(rel)) return
    if (rule === 'R2-icon-only-button' && (SPECIMEN_FILES.includes(rel) || FULFILLER_FILES.includes(rel))) return
    if (rule === 'R2-filter-row' && SPECIMEN_FILES.includes(rel)) return
    hits.push({ rule, line: lineOf(sf, node), detail })
  }
  /* R2-filter-row is a FILE-LEVEL question (does this file's own toolbar go through FilterBar
   *  at all?), read once: every tag the file renders, anywhere. A `<SearchField>` beside a
   *  facet control with no `<FilterBar>` tag anywhere in the file is a bar FilterBar was built
   *  to replace, assembled by hand instead. */
  const fileTags = new Set(jsxTags(sf))
  const handBuiltFilterRow = fileTags.has('SearchField') && FACET_TAGS.some((t) => fileTags.has(t)) && !fileTags.has('FilterBar')
  const visit = (n) => {
    if (ts.isJsxAttribute(n)) {
      const name = n.name.getText(sf)
      if (name === 'role') {
        for (const v of attrLiterals(n)) if (v === 'dialog' || v === 'alertdialog') add('R2-dialog', n, `role="${v}"`)
      } else if (name === 'className' && n.initializer) {
        for (const t of classTokens(n.initializer)) if (reserved(t)) add('R2-class', n, t)
      } else if (name === 'iconOnly') {
        add('R2-icon-only-button', n, 'iconOnly')
      }
    } else if (ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n)) {
      const tag = n.tagName.getText(sf)
      if (tag === 'select') add('R2-select', n, '<select>')
      if (tag === 'dialog') add('R2-dialog', n, '<dialog>')
      if (tag === 'Button' && hasSpreadIconOnly(n)) add('R2-icon-only-button', n, 'iconOnly (spread)')
      if (HEADER_TAGS.includes(tag)) {
        const actions = attr(n, 'actions')
        if (actions && actions.initializer) {
          const count = countWordedButtons(actions.initializer, sf)
          if (count > 1) add('R2-header-actions', n, `${count} worded <Button> presses in one <${tag}> (cap is 1)`)
        }
      }
      if (tag === 'SearchField' && handBuiltFilterRow) {
        add('R2-filter-row', n, `<SearchField> beside a facet control (${FACET_TAGS.filter((t) => fileTags.has(t)).join(', ')}), with no <FilterBar> in the file`)
      }
      /* Clause (b), the self-closing shape: `<button aria-label="Close" />` has no children at
         all, so the `JsxElement` visitor below never sees it — this is the one blank-by-
         construction case that reader cannot reach. */
      if (ts.isJsxSelfClosingElement(n) && (tag === 'button' || isRoleButton(n, sf)) && attrLiterals(attr(n, 'aria-label')).length > 0) {
        add('R2-icon-only-button', n, `<${tag} aria-label> with no visible content`)
      }
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
        const dollar = ts.isJsxText(k) ? DOLLAR_END.test(k.text) : ts.isJsxExpression(k) && k.expression !== undefined && endsInDollar(k.expression)
        if (dollar) add('R2-money', next, 'a `$` in JSX before `{...}`')
      }
      /* Clause (b): a <button> (or an <a role="button">) whose whole visible content resolves
         to nothing but an icon — an <Icon>, an <svg>, or a bare ×/✕/✖ — including through a
         wrapper element, a `{<Icon/>}` expression, or a ternary of two icons (the common
         chevron-toggle shape); OR one with NO visible content at all, carrying only an
         `aria-label`. `aria-label`-with-no-children names a control with nothing to read
         except that label, the same problem an icon-only control has (round 2's review). A
         REAL word anywhere in the content — even a dynamic one this reader cannot itself
         read, like `{label}` — clears it: `aggregate` reports `'other'`, not `'icon'`. */
      const tag0 = ts.isJsxElement(n) ? n.openingElement.tagName.getText(sf) : null
      if (tag0 === 'button' || (tag0 !== null && isRoleButton(n.openingElement, sf))) {
        const content = aggregate(kids.map((k) => isIconLike(k, sf)))
        if (content === 'icon') add('R2-icon-only-button', n.openingElement, `<${tag0}> whose only visible content is an icon`)
        else if (content === 'blank' && attrLiterals(attr(n.openingElement, 'aria-label')).length > 0) {
          add('R2-icon-only-button', n.openingElement, `<${tag0} aria-label> with no visible content`)
        }
      }
      /* Clause (c): a <Button> whose literal label starts with a vocabulary verb, and whose
         `variant` cannot be shown to always be `primary` or `danger-solid` — the ICONOGRAPHY
         rule's own two words-only variants. `leadingLabelText` reads through `{'Undo'}` and
         `Undo {n}` (round 2's review); `resolveVariantLiterals` refuses to call a `??`/`||`/
         `&&`/ternary variant provably worded unless EVERY branch resolves to a literal. */
      if (ts.isJsxElement(n) && n.openingElement.tagName.getText(sf) === 'Button') {
        const label = leadingLabelText(kids)
        const verb = label === '' ? null : VOCAB_VERB_RE.exec(label)
        if (verb !== null) {
          const variantLiterals = resolveVariantLiterals(attr(n.openingElement, 'variant')?.initializer)
          const provenWorded = variantLiterals !== null && variantLiterals.length > 0 && variantLiterals.every((v) => WORDED_VARIANTS.has(v))
          if (!provenWorded) add('R2-icon-only-button', n.openingElement, `<Button>${label}</Button>, variant not provably primary/danger-solid`)
        }
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
 *  AND ONLY WHILE NO RULE WAS REMOVED (the orchestrator's option a, 2026-09-23): `headRules` is
 *  the same shape, read at HEAD. If any rule the merge-base defines, in either block, is missing
 *  at HEAD, ALL growth is refused and the message names the missing rule. Otherwise a rename
 *  (R2-money -> R2-cash) would pass as a born rule, and every old debt could come back under
 *  the new name. A null set, at either end, allows nothing: an unread definition never excuses
 *  growth. `base` null means there was nothing to compare against: the caller fails open and
 *  prints why.
 *  Returns `{ refused, allowed }`, each a list of `{ block, key, rule, why }`, or null. */
export function growth(base, head, baseRules = { static: null, runtime: null }, headRules = { static: null, runtime: null }) {
  if (base === null) return null
  const missing = []
  let unread = null
  for (const block of ['static', 'runtime']) {
    const before = baseRules?.[block] ?? null
    const now = headRules?.[block] ?? null
    if (before === null) unread = unread ?? `the merge-base's ${block} rule definitions could not be read`
    else if (now === null) unread = unread ?? `HEAD's ${block} rule definitions could not be read`
    else for (const rule of before) if (!now.has(rule)) missing.push(rule)
  }
  const blocked = missing.length > 0
    ? `${missing.map((r) => `"${r}"`).join(', ')}, defined at the merge-base, ${missing.length > 1 ? 'are' : 'is'} missing at HEAD (removed or renamed), so no growth is allowed`
    : unread === null ? null : `${unread}, so no rule can be shown to be new`
  const refused = []
  const allowed = []
  for (const block of ['static', 'runtime']) {
    const before = pairs(base?.[block])
    const known = baseRules?.[block] ?? null
    for (const [key, rule] of pairs(head?.[block])) {
      if (before.has(key)) continue
      if (blocked !== null) refused.push({ block, key, rule, why: blocked })
      else if (!known.has(rule)) {
        allowed.push({ block, key, rule, why: `rule "${rule}" is not defined at the merge-base, so it was born on this branch and its first offenders may be listed` })
      } else {
        refused.push({ block, key, rule, why: `rule "${rule}" exists at the merge-base, and a rule that exists only shrinks` })
      }
    }
  }
  return { refused, allowed }
}

/** The rule ids defined at HEAD: RULES in this file, and the spec's PER_ROUTE and SHELL_WIDE as
 *  they stand in the working tree. A spec that cannot be read gives null, which allows nothing. */
function rulesAtHead() {
  let spec = null
  try {
    spec = definedIds(fs.readFileSync(path.join(ROOT, SPEC_FILE), 'utf8'), { arrayNames: ['PER_ROUTE', 'SHELL_WIDE'] })
  } catch {
    spec = null
  }
  return { static: new Set(Object.keys(RULES)), runtime: spec }
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

/* ---- the icon vocabulary has a meaning for every icon it names (docs/specs/iconography.md
   section 3: "Also add ICON_MEANINGS rows for the icons that exist"). Read from the AST, like
   everything else here, never by importing Icon.tsx (it is TypeScript; this file only parses
   it). A vocabulary icon `IconButton` can draw but `ICON_MEANINGS` cannot explain is a call
   site with no way to check its own glyph is right. */
const ICON_FILE = 'app/src/kit/Icon.tsx'
/** Every icon name `docs/specs/iconography.md` section 2, step 6 draws from. */
export const VOCAB_ICON_NAMES = [
  'sold', 'undo', 'archive', 'pencil', 'trash', 'eraser', 'copy', 'download', 'external', 'x',
  'filter', 'sortAsc', 'sortDesc', 'refresh', 'settings', 'more', 'moveTo', 'lock', 'unlock',
  'eye', 'eyeOff', 'chevronLeft', 'chevronRight', 'chevronUp', 'chevronDown', 'search', 'grip',
]

/** The string-literal-keyed property names of `export const <varName> = { ... }`, or `null`
 *  if that declaration is not there or is not an object literal. */
function objectKeys(sf, varName) {
  let keys = null
  const visit = (n) => {
    if (keys !== null) return
    if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === varName && n.initializer) {
      const init = unwrap(n.initializer)
      if (ts.isObjectLiteralExpression(init)) {
        keys = init.properties
          .filter((p) => (ts.isPropertyAssignment(p) || ts.isShorthandPropertyAssignment(p)) && (ts.isIdentifier(p.name) || ts.isStringLiteral(p.name)))
          .map((p) => p.name.text)
      }
    }
    ts.forEachChild(n, visit)
  }
  visit(sf)
  return keys
}

/** `{ missing, unknown, reason }`: `missing` is every vocabulary icon `PATHS` carries with no
 *  `ICON_MEANINGS` row; `unknown` is every vocabulary icon `PATHS` does not carry at all (the
 *  vocabulary named an icon nobody drew). `reason` is set, and both arrays are `null`, only
 *  when `Icon.tsx` could not be read as expected — never a silent pass over nothing. */
export function iconMeaningsGap(files) {
  const text = files.get(ICON_FILE)
  if (text === undefined) return { missing: null, unknown: null, reason: `${ICON_FILE} is missing` }
  const sf = ts.createSourceFile(ICON_FILE, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
  const paths = objectKeys(sf, 'PATHS')
  const meanings = objectKeys(sf, 'ICON_MEANINGS')
  if (paths === null) return { missing: null, unknown: null, reason: `${ICON_FILE}: PATHS is not a readable object literal` }
  if (meanings === null) return { missing: null, unknown: null, reason: `${ICON_FILE}: ICON_MEANINGS is not a readable object literal` }
  const pathSet = new Set(paths)
  const meaningSet = new Set(meanings)
  return {
    missing: VOCAB_ICON_NAMES.filter((name) => pathSet.has(name) && !meaningSet.has(name)),
    unknown: VOCAB_ICON_NAMES.filter((name) => !pathSet.has(name)),
    reason: null,
  }
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
  const grown = growth(atBase.allow, allow, atBase.rules, rulesAtHead())
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

  const iconGap = iconMeaningsGap(files)
  if (iconGap.reason !== null) {
    console.error(`kit-adoption: ${iconGap.reason}. Failing closed: the vocabulary cannot be checked.`)
  } else {
    for (const name of iconGap.missing) {
      console.error(`kit-adoption: ${ICON_FILE}: "${name}" is in the icon vocabulary (docs/specs/iconography.md section 2) but ICON_MEANINGS has no row for it.`)
    }
    for (const name of iconGap.unknown) {
      console.error(`kit-adoption: ${ICON_FILE}: the icon vocabulary names "${name}", which PATHS does not draw.`)
    }
  }
  const iconGapFails = iconGap.reason !== null || iconGap.missing.length > 0 || iconGap.unknown.length > 0

  if (errors.length || unlisted.length || stale.length || (grown !== null && grown.refused.length > 0) || iconGapFails) process.exit(1)
  console.log(
    `kit-adoption: ${result.routes.length} routes, ${result.violations.length} violations, every one ` +
      `listed; ${listed.size} allow-list entries still owed (${byLane || 'none'}). Icon vocabulary: ` +
      `${VOCAB_ICON_NAMES.length} icons, every one has a meaning.`,
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
  add('a template `$`, then any white space, before any interpolation is R2-money, with or without toFixed; `${n}%` is not', () =>
    rule('export const s = (x) => `$${x}`\n', 'R2-money') === 1 &&
    rule('export const s = (x) => `Over $ ${x} each`\n', 'R2-money') === 1 &&
    rule('export const s = (x) => `Over $  ${x} each`\n', 'R2-money') === 1 &&
    rule("export const s = (x) => 'Total: $  ' + x\n", 'R2-money') === 1 &&
    rule('export const s = (n) => `${n}% and ${n} items`\n', 'R2-money') === 0)
  add("a `$` in JSX text, or a {'$'} child, before {...} is R2-money; `{n} items` is not", () =>
    rule('export const S = ({ p }) => <span>${p}</span>\n', 'R2-money') === 1 &&
    rule('export const S = ({ p }) => <span>could be $ {p}</span>\n', 'R2-money') === 1 &&
    rule("export const S = ({ p }) => <span>{'$'}{p}</span>\n", 'R2-money') === 1 &&
    rule('export const S = ({ n }) => <span>{n} items, $5 flat</span>\n', 'R2-money') === 0)
  add('every money shape is green inside money.ts, its home', () =>
    green(outcome(tree({ 'app/src/money.ts': "export const a = (x) => `$${x}`\nexport const b = (x) => '$' + x\n" }))))

  /* R2-icon-only-button (F-icons): a hand-rolled icon-only control outside the kit. */
  add('a <button> whose only child is <Icon> is red', () =>
    rule('export const S = () => <button onClick={f}><Icon name="x" /></button>\n', 'R2-icon-only-button') === 1)
  add('a <button> with an <Icon> AND visible text is green (a labelled button, not icon-only)', () =>
    rule('export const S = () => <button onClick={f}><Icon name="x" />Close</button>\n', 'R2-icon-only-button') === 0)
  add('a <button> whose only child is <Icon>, wrapped in whitespace, is still red', () =>
    rule('export const S = () => <button onClick={f}>\n  <Icon name="x" />\n</button>\n', 'R2-icon-only-button') === 1)
  add('a <Button iconOnly icon="x">Preview</Button> is red (iconOnly, by presence)', () =>
    rule('export const S = () => <Button iconOnly icon="x">Preview</Button>\n', 'R2-icon-only-button') === 1)
  add('a conditional iconOnly={cond} is still red (read by presence, not value)', () =>
    rule('export const S = ({ small }) => <Button iconOnly={small} icon="x">Preview</Button>\n', 'R2-icon-only-button') === 1)
  add('a <Button icon="x">Preview</Button> with no iconOnly, and no vocabulary word, is green', () =>
    rule('export const S = () => <Button icon="x">Preview</Button>\n', 'R2-icon-only-button') === 0)
  add('an <IconButton icon="x" label="Close" /> is green: the kit primitive itself is not a violation', () =>
    rule('export const S = () => <IconButton icon="x" label="Close" />\n', 'R2-icon-only-button') === 0)
  add('a <button><Icon /></button> inside app/src/kit/ is green', () =>
    green(outcome(tree({ 'app/src/kit/Toast.tsx': 'export const T = () => <button onClick={f}><Icon name="x" /></button>\n' }))))

  /* Clause (b): a native <button> whose only child is an inline <svg>. */
  add('a <button><svg>...</svg></button> is red', () =>
    rule('export const S = () => <button onClick={f}><svg><path d="M0 0" /></svg></button>\n', 'R2-icon-only-button') === 1)

  /* Clause (c): a <Button> whose literal label starts with a vocabulary verb, unless its
     variant is provably `primary` or `danger-solid`. */
  add('a <Button>Mark sold</Button> with no variant (default) is red', () =>
    rule('export const S = () => <Button icon="check">Mark sold</Button>\n', 'R2-icon-only-button') === 1)
  add('a <Button variant="primary">Mark sold</Button> is green', () =>
    rule('export const S = () => <Button variant="primary" icon="check">Mark sold</Button>\n', 'R2-icon-only-button') === 0)
  add('a <Button variant="danger-solid">Delete</Button> is green', () =>
    rule('export const S = () => <Button variant="danger-solid" icon="trash">Delete</Button>\n', 'R2-icon-only-button') === 0)
  add('a <Button variant="ghost">Undo</Button> is red', () =>
    rule('export const S = () => <Button variant="ghost" icon="undo">Undo</Button>\n', 'R2-icon-only-button') === 1)
  add('a dynamic variant that CAN be default (`primary ? "primary" : "default"`) is red — the map\'s own "must split into two branches" case', () =>
    rule('export const S = ({ primary }) => <Button variant={primary ? "primary" : "default"} icon="check">Mark sold</Button>\n', 'R2-icon-only-button') === 1)
  add('a fully dynamic label ({label}) is not seen: not a literal', () =>
    rule('export const S = ({ label }) => <Button icon="check">{label}</Button>\n', 'R2-icon-only-button') === 0)
  add('a label that does not START with a vocabulary verb is green (a verb mid-sentence does not match)', () =>
    rule('export const S = () => <Button icon="check">The row can be retired</Button>\n', 'R2-icon-only-button') === 0)

  /* The Fulfiller's own files, and Gallery, are exempt from this rule alone. */
  add('R2-icon-only-button is green in app/src/Fulfillment.tsx and app/src/PullConfirm.tsx', () =>
    green(outcome(tree({
      'app/src/Fulfillment.tsx': 'export const F = () => <button onClick={f}><Icon name="x" /></button>\n',
      'app/src/PullConfirm.tsx': 'export const P = () => <Button icon="check">Mark sold</Button>\n',
    }))))
  add('R2-icon-only-button is green in app/src/Gallery.tsx (the specimen sheet)', () => {
    const r = outcome(tree({ 'app/src/Gallery.tsx': 'export const G = () => <button onClick={f}><Icon name="x" /></button>\n' }))
    return !has(r.unlisted, 'app/src/Gallery.tsx', 'R2-icon-only-button')
  })

  /* R2-icon-only-button, round 2 — the review's own evasion fixtures
     (SD/review/kit-icons/evade.mjs), kept here so the finding stays proven. */
  add('an Icon wrapped in a <span> is red', () =>
    rule('export const S = () => <button onClick={f}><span><Icon name="x" /></span></button>\n', 'R2-icon-only-button') === 1)
  add('{<Icon/>} as the only child is red', () =>
    rule('export const S = () => <button onClick={f}>{<Icon name="x" />}</button>\n', 'R2-icon-only-button') === 1)
  add('a ternary of two Icons (a chevron toggle) is red', () =>
    rule('export const S = ({ open }) => <button onClick={f}>{open ? <Icon name="chevronUp" /> : <Icon name="chevronDown" />}</button>\n', 'R2-icon-only-button') === 1)
  add('spread props plus an Icon child is still red', () =>
    rule('export const S = (p) => <button {...p}><Icon name="x" /></button>\n', 'R2-icon-only-button') === 1)
  add('an aria-label-only button with no children at all is red', () =>
    rule('export const S = () => <button aria-label="Close" className="x" onClick={f} />\n', 'R2-icon-only-button') === 1)
  add('a bare × character standing in for an icon is red', () =>
    rule('export const S = () => <button aria-label="Close" onClick={f}>×</button>\n', 'R2-icon-only-button') === 1)
  add('<a role="button"> wrapping an icon is red, same as <button>', () =>
    rule('export const S = () => <a role="button" onClick={f}><Icon name="x" /></a>\n', 'R2-icon-only-button') === 1)
  add('an icon plus a dynamic label ({label}) is green: real content clears it', () =>
    rule('export const S = ({ label }) => <button onClick={f}><Icon name="x" />{label}</button>\n', 'R2-icon-only-button') === 0)
  add('an icon plus {" "} plus a dynamic label is green', () =>
    rule('export const S = ({ t }) => <button onClick={f}><Icon name="x" />{\' \'}{t.label}</button>\n', 'R2-icon-only-button') === 0)
  add('iconOnly spread as an object literal ({...{ iconOnly: true }}) is red', () =>
    /* >= 1, not === 1: "Close" is itself a vocabulary word with no provable variant, so
       clause (c) also fires on the same element — two true findings, not a double-count. */
    rule('export const S = () => <Button {...{ iconOnly: true }} icon="x">Close</Button>\n', 'R2-icon-only-button') >= 1)
  add('a spread-only Button with a vocabulary label is red: no variant attr to read at all', () =>
    rule('export const S = (p) => <Button {...p}>Undo</Button>\n', 'R2-icon-only-button') === 1)
  add('{\'Undo\'} as the label is red', () =>
    rule('export const S = () => <Button icon="undo">{\'Undo\'}</Button>\n', 'R2-icon-only-button') === 1)
  add('"Undo {n}" as the label is red: the leading literal text is enough', () =>
    rule('export const S = ({ n }) => <Button icon="undo">Undo {n}</Button>\n', 'R2-icon-only-button') === 1)
  add('a lowercase "undo" label is red: matched case-insensitively', () =>
    rule('export const S = () => <Button icon="undo">undo</Button>\n', 'R2-icon-only-button') === 1)
  add('Hold, Release, Reveal, Hide and Clear are all in the vocabulary', () =>
    rule('export const S = () => <Button icon="lock">Hold</Button>\n', 'R2-icon-only-button') === 1 &&
    rule('export const S = () => <Button icon="unlock">Release</Button>\n', 'R2-icon-only-button') === 1 &&
    rule('export const S = () => <Button icon="eye">Reveal</Button>\n', 'R2-icon-only-button') === 1 &&
    rule('export const S = () => <Button icon="eyeOff">Hide</Button>\n', 'R2-icon-only-button') === 1 &&
    rule('export const S = () => <Button icon="eraser">Clear</Button>\n', 'R2-icon-only-button') === 1)

  /* R2-header-actions (the tighten ruling, 2026-09-24): at most one worded <Button> in a
     <Page>/<PageHeader> actions slot. */
  add('two worded <Button>s in <Page actions> is red (R2-header-actions)', () =>
    rule('export const S = () => <Page actions={<><Button>Save</Button><Button>Cancel</Button></>} />\n', 'R2-header-actions') === 1)
  add('two worded <Button>s in <PageHeader actions> is red too', () =>
    rule('export const S = () => <PageHeader actions={<><Button>Save</Button><Button>Cancel</Button></>} />\n', 'R2-header-actions') === 1)
  add('one worded <Button> plus an <IconButton> in actions is green', () =>
    rule('export const S = () => <Page actions={<><Button>Save</Button><IconButton icon="x" label="Close" /></>} />\n', 'R2-header-actions') === 0)
  add('one worded <Button> alone in actions is green', () =>
    rule('export const S = () => <Page actions={<Button variant="primary">Send</Button>} />\n', 'R2-header-actions') === 0)
  add('two icon-only <Button>s in actions is green: neither is worded', () =>
    rule('export const S = () => <Page actions={<><Button icon="x" iconOnly>Close</Button><IconButton icon="y" label="Sort" /></>} />\n', 'R2-header-actions') === 0)
  add('worded Buttons inside a Sheet reached from the header are not counted (opaque overlay)', () =>
    rule('export const S = () => <Page actions={<><Button>Save</Button><Sheet><Button>Confirm</Button><Button>Cancel</Button></Sheet></>} />\n', 'R2-header-actions') === 0)
  add('a screen with no actions prop at all is green', () => rule('export const S = () => <Page title="X" />\n', 'R2-header-actions') === 0)

  /* R2-filter-row (the same ruling): a hand-built SearchField-plus-facet row with no FilterBar
     in the file at all — FILE-LEVEL, so it does not matter how far apart the two tags sit. */
  add('SearchField beside a Select with no FilterBar in the file is red (R2-filter-row)', () =>
    rule('export const S = () => <><SearchField /><Select /></>\n', 'R2-filter-row') === 1)
  add('SearchField beside FilterChips with no FilterBar is red', () =>
    rule('export const S = () => <><SearchField /><FilterChips /></>\n', 'R2-filter-row') === 1)
  add('SearchField and a Select, both inside a FilterBar tag, is green', () =>
    rule('export const S = () => <FilterBar><SearchField /><Select /></FilterBar>\n', 'R2-filter-row') === 0)
  add('SearchField and a Select elsewhere in a file that also renders FilterBar is green: the file has adopted it', () =>
    rule('export const S = () => <><FilterBar /><SearchField /><Select /></>\n', 'R2-filter-row') === 0)
  add('a bare SearchField with no facet control beside it is green', () => rule('export const S = () => <SearchField />\n', 'R2-filter-row') === 0)
  add('a bare Select with no SearchField is green: nothing to combine into a bar', () => rule('export const S = () => <Select />\n', 'R2-filter-row') === 0)
  add('Gallery.tsx is exempt from R2-filter-row (the specimen sheet demos each piece separately)', () => {
    const r = outcome(tree({ 'app/src/Gallery.tsx': 'export const G = () => <><SearchField /><Select /></>\n' }))
    return !has(r.unlisted, 'app/src/Gallery.tsx', 'R2-filter-row')
  })

  /* ONLY SHRINKS (F3): the growth read against the merge-base. */
  const base = { static: { 'app/src/A.tsx': { R1: 'home', 'R2-class': 'home' } }, runtime: { '/': { page: 'home' } } }
  /* The rules defined at the merge-base: every rule this file knows today, minus R2-new, which
     stands for a rule born on the branch. */
  const baseRules = { static: new Set(Object.keys(RULES)), runtime: new Set(['page', 'h1', 'width', 'top', 'scroll', 'title', 'palette', 'keys']) }
  const clone = (o) => JSON.parse(JSON.stringify(o))
  const refusedOnly = (g, block, key) => g.refused.length === 1 && g.allowed.length === 0 && g.refused[0].block === block && g.refused[0].key === key && /exists at the merge-base/.test(g.refused[0].why)
  add('a new static key (a new file) for an existing rule is refused, so red', () => {
    const head = clone(base)
    head.static['app/src/B.tsx'] = { R1: 'x' }
    return refusedOnly(growth(base, head, baseRules, baseRules), 'static', 'app/src/B.tsx -> R1')
  })
  add('a new key for an existing rule under a file the list already names is refused, so red', () => {
    const head = clone(base)
    head.static['app/src/A.tsx']['R2-date'] = 'home'
    return refusedOnly(growth(base, head, baseRules, baseRules), 'static', 'app/src/A.tsx -> R2-date')
  })
  add('a new runtime key for an existing assertion is refused, so red', () => {
    const head = clone(base)
    head.runtime['/']['width'] = 'home'
    return refusedOnly(growth(base, head, baseRules, baseRules), 'runtime', '/ -> width')
  })
  add('a new key for a rule born on this branch (not defined at the merge-base) is allowed, so green, and says why', () => {
    const head = clone(base)
    head.static['app/src/B.tsx'] = { 'R2-new': 'x' }
    head.runtime['/']['focus'] = 'shell'
    const g = growth(base, head, baseRules, { static: new Set([...baseRules.static, 'R2-new']), runtime: new Set([...baseRules.runtime, 'focus']) })
    return g.refused.length === 0 && g.allowed.length === 2 &&
      g.allowed.some((a) => a.rule === 'R2-new' && /born on this branch/.test(a.why)) && g.allowed.some((a) => a.rule === 'focus')
  })
  add('renaming a rule (R2-money -> R2-cash) refuses all growth, and names the missing rule', () => {
    /* The branch renames R2-money to R2-cash. R2-cash is not defined at the merge-base, so under
       option (b) alone it would pass as "born on the branch", and every old R2-money debt could
       come back under the new name as growth. */
    const b = clone(base)
    b.static['app/src/A.tsx']['R2-money'] = 'home'
    const head = clone(b)
    delete head.static['app/src/A.tsx']['R2-money']
    head.static['app/src/A.tsx']['R2-cash'] = 'home'
    head.static['app/src/C.tsx'] = { 'R2-cash': 'x' }
    const headRules = { static: new Set([...baseRules.static].filter((r) => r !== 'R2-money').concat('R2-cash')), runtime: baseRules.runtime }
    const g = growth(b, head, baseRules, headRules)
    return g.allowed.length === 0 && g.refused.length === 2 && g.refused.every((r) => /R2-money/.test(r.why) && /missing at HEAD/.test(r.why))
  })
  add('removing a runtime assertion (keys) refuses growth for a born static rule too', () => {
    const head = clone(base)
    head.static['app/src/B.tsx'] = { 'R2-new': 'x' }
    const headRules = { static: new Set([...baseRules.static, 'R2-new']), runtime: new Set([...baseRules.runtime].filter((a) => a !== 'keys')) }
    const g = growth(base, head, baseRules, headRules)
    return g.allowed.length === 0 && g.refused.length === 1 && /"keys"/.test(g.refused[0].why)
  })
  add('a rule definition the merge-base or HEAD read could not parse excuses nothing: growth is refused', () => {
    const head = clone(base)
    head.static['app/src/B.tsx'] = { 'R2-new': 'x' }
    const g = growth(base, head, { static: null, runtime: null }, baseRules)
    const h = growth(base, head, baseRules, { static: baseRules.static, runtime: null })
    return g.refused.length === 1 && /could not be read/.test(g.refused[0].why) && h.refused.length === 1 && /HEAD's runtime/.test(h.refused[0].why)
  })
  add('a removed key is the list shrinking, so green; a changed lane is not growth', () => {
    const head = clone(base)
    delete head.static['app/src/A.tsx']['R2-class']
    delete head.runtime['/']
    head.static['app/src/A.tsx'].R1 = 'capture'
    const g = growth(base, head, baseRules, baseRules)
    return g.refused.length === 0 && g.allowed.length === 0
  })
  add('no allow list at the merge-base fails open (null), never a silent pass', () => growth(null, base) === null)

  /* iconMeaningsGap: every icon the vocabulary draws has a row in ICON_MEANINGS. */
  const iconFixture = (paths, meanings) =>
    new Map([[
      'app/src/kit/Icon.tsx',
      `const PATHS = { ${paths.map((p) => `${p}: 'M0 0'`).join(', ')} } as const\n` +
        `export const ICON_MEANINGS = { ${meanings.map((m) => `${m}: 'a meaning'`).join(', ')} }\n`,
    ]])
  add('every vocabulary icon carrying a PATHS entry AND an ICON_MEANINGS row is green', () => {
    const g = iconMeaningsGap(iconFixture(VOCAB_ICON_NAMES, VOCAB_ICON_NAMES))
    return g.reason === null && g.missing.length === 0 && g.unknown.length === 0
  })
  add('a vocabulary icon with a PATHS entry but no ICON_MEANINGS row is in `missing`', () => {
    const meanings = VOCAB_ICON_NAMES.filter((n) => n !== 'sold')
    const g = iconMeaningsGap(iconFixture(VOCAB_ICON_NAMES, meanings))
    return g.missing.includes('sold') && g.missing.length === 1 && g.unknown.length === 0
  })
  add('a vocabulary icon with no PATHS entry at all is in `unknown`, never `missing`', () => {
    const paths = VOCAB_ICON_NAMES.filter((n) => n !== 'grip')
    const g = iconMeaningsGap(iconFixture(paths, paths))
    return g.unknown.includes('grip') && g.unknown.length === 1 && g.missing.length === 0
  })
  add('a missing Icon.tsx fails closed with a reason, never a silent pass', () => {
    const g = iconMeaningsGap(new Map())
    return g.reason !== null && g.missing === null && g.unknown === null
  })
  add('the git read sees its subject: the committed list and both rule definitions at HEAD', () => {
    const at = allowAtBase('HEAD')
    if (at.allow === null) throw new Error(`nothing to read: ${at.reason}`)
    const head = clone(at.allow)
    head.static['app/src/NotARealScreen.tsx'] = { R1: 'x' }
    const same = growth(at.allow, at.allow, at.rules, rulesAtHead())
    const more = growth(at.allow, head, at.rules, rulesAtHead())
    return at.rules.static !== null && Object.keys(RULES).every((r) => at.rules.static.has(r)) &&
      at.rules.runtime !== null && ['page', 'title', 'palette', 'keys'].every((a) => at.rules.runtime.has(a)) &&
      rulesAtHead().runtime !== null && ['page', 'title', 'keys'].every((a) => rulesAtHead().runtime.has(a)) &&
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
