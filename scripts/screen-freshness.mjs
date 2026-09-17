#!/usr/bin/env node
/**
 * Prove every server WRITE the React app makes has a way back to the server.
 *
 * WHY THIS EXISTS. `app/src/server.ts` is the only module that talks to the capture server,
 * and it says so in its own header: one owner, one failure behaviour. What it deliberately
 * does NOT own is what happens AFTER a write lands. D13 puts exactly one place inventory
 * lives — the store on this Mac — and every screen in this app is a view of it that holds no
 * second copy. So a write that changes the store and leaves the screen alone has produced a
 * screen that disagrees with the store, silently, with nothing on it that says so. That
 * failure has a shape this repo already knows: `Fulfillment.tsx` says in its own comment that
 * its card list "was read once at mount and never again, which is what let him tap Mark sold
 * on a card the other device had already sold — the stale row was still on screen an hour
 * later." One missing re-read, one wrong sale, no error anywhere.
 *
 * Nothing checks for the next one. `make lint` has no rule for it, `tsc` cannot see it, the
 * harness tests the SERVER, and `make design-check` asserts the Fulfillment view's geometry.
 * A screen that never re-reads type-checks, lints, renders, and passes every one of them.
 *
 * WHAT IT CHECKS, in two passes.
 *
 *   1. IT CLASSIFIES `app/src/server.ts` ITSELF, by following `request(path, init)` and the
 *      `method` literal in `init`. A read has no method (or GET); a write has POST, PUT,
 *      DELETE or PATCH. THE LITERAL IS OFTEN NOT IN THE EXPORTED FUNCTION'S OWN BODY: five
 *      module-private helpers — `answerCall`, `standDownCall`, `sale`, `retirement`, `pull` —
 *      carry the method for ten exported writes between them, because each pair is one route
 *      in both directions. A classifier that reads only the exported body drops all ten. That
 *      is not a hypothetical: it was measured on this tree before this script existed, and it
 *      is why the classification is a transitive call-graph closure and not a grep.
 *
 *   2. IT FINDS EVERY CALL SITE OF EVERY WRITE, in every `.tsx` under `app/src`, and asks
 *      whether a freshness mechanism covers it. Thirteen mechanisms are already in the tree
 *      and each has a recogniser here, named after what it does rather than after the file it
 *      was found in. A site covered by none of them is a finding.
 *
 * TWO INDIRECTIONS IT FOLLOWS, because a call-site scan that does not follow them reports a
 * clean tree while missing writes entirely — which is worse than a false positive, since a
 * false positive gets looked at:
 *
 *   THE WRITE STORED AS A VALUE. `ReviewQueue.tsx` puts `undoAnswer` / `undoStandDown` /
 *   `undoRetire` into a receipt's `reverse` field and later calls `receipt.reverse(box, index)`.
 *   A scan for the imported NAME finds nothing at that line. So any object-literal property
 *   whose value mentions a write is remembered, and a call through a property of that name is
 *   a write site.
 *
 *   THE WRITE BEHIND A WRAPPER. `Fulfillment.tsx:unsell` is a module-level helper over
 *   `undoSale`; `BoxOps.tsx` hands `() => updateBox(...)` to `useBoxWrite`'s `write`. In the
 *   first the evidence lives at the CALLER, so the analysis is retried at each caller; in the
 *   second the evidence lives inside the HOOK, so the hook's body joins the evidence scope and
 *   its parameters are mapped back to the arguments the component passed in.
 *
 * WHAT A GREEN RUN MEANS, AND WHAT IT DOES NOT — this is the part worth being exact about.
 *
 *   IT FOUND ZERO FINDINGS ON THE TREE IT WAS WRITTEN AGAINST. All 29 writes and every one of
 *   their call sites were read by hand first, and not one of them was stale. This script did
 *   not find a bug and was never going to: it is a REGRESSION GUARD for write site number 30.
 *   Its whole value is the day somebody adds a write and forgets the re-read, and the value is
 *   zero on any day nobody does.
 *
 *   GREEN MEANS "EVERY WRITE HAS A WAY BACK". IT DOES NOT MEAN "NO SCREEN IS STALE". Those are
 *   different claims and only the first one is checkable from the AST. A re-read that fetches
 *   the wrong thing, a reload counter listed in the wrong effect's dependency array, an
 *   optimistic patch that computes the new row incorrectly — all of them present here as
 *   covered, because the mechanism is THERE. Whether it is RIGHT is a question for a test that
 *   runs the screen, and `app/tests/` is where that lives.
 *
 *   IT IS BLIND TO THE CROSS-DEVICE CASE ENTIRELY, and that is not a gap that can be closed by
 *   trying harder. D13 puts two devices on one store with no session between them. A sale made
 *   on the phone is not a call site in this tree at all — there is no node to walk — so no
 *   static pass over `app/src` can ever see it. Only a poll, a subscription, or a re-read on
 *   focus answers that, and this script cannot tell you that you needed one.
 *
 *   IT IS SCOPED TO THE SINGLES TRACK. `server.ts` carries the code-card track's five
 *   functions behind its own `the code-card track` banner (D14: two tracks, one rig, separate
 *   schema and separate channel — see `code-card-fork/CLAUDE.md`), and `Codes.tsx` is the
 *   screen that spends them. That region is excluded from both passes, by the banner and not
 *   by a list of names, and the summary line prints how many exports it skipped so the
 *   exclusion is visible on every run rather than only in this comment. `Codes.tsx` is
 *   therefore unaudited: its writes were read by hand once and every one of them ends
 *   `await load()`, and nothing keeps that true.
 *
 *   THE RECOGNISERS ARE SHAPE MATCHERS, NOT PROOFS. Each one names a structure — a counter
 *   bumped and listed as a read effect's dependency, a response threaded into a setState, a
 *   callback prop invoked and bound at the parent to something that re-reads. A screen that
 *   writes and then calls `setSomething(prev => prev.filter(...))` on state that has nothing to
 *   do with the write reads as covered. The `--self-test` is the guard against that decaying
 *   into a rubber stamp: it asserts BOTH directions, that a synthetic stale write IS flagged
 *   and that each idiom is NOT, so a recogniser that widened until it could never fire fails
 *   its own test rather than quietly passing the tree.
 *
 *   ONE BLIND SPOT IS KNOWN, MEASURED, AND PINNED BY ITS OWN SELF-TEST CASE: A RECEIPT READS AS
 *   A REFRESH. Three regressions were injected into a COPY of `app/src` and the script was run
 *   over it. Two were caught and printed: a brand-new `await deleteBox(b)` with nothing after
 *   it, and `BoxOps.tsx:DeleteBox` with both its `onChanged()` and its `setReceipt(result)`
 *   removed. The third was NOT: `onChanged()` deleted with the receipt left in place reported
 *   clean, covered as "the response carries the new state", because `setReceipt(result)` is
 *   idiom 4 by shape. It is idiom 4 in `CaptureScreen.tsx` too, where the created box row
 *   genuinely IS the row `GET /boxes` would return; the difference is what the state MEANS and
 *   nothing in the AST carries that. So a lost `onChanged` beside a receipt is still a person
 *   reading the diff. What this catches is the plainer and far likelier regression — a new
 *   write with nothing after it at all — which is what write site number 30 will look like.
 *
 *   IT IS NOT ON THE COMMIT PATH, and that is a tier decision rather than an oversight. The
 *   pre-commit hook runs a bare `python3` with nothing installed; this needs node AND
 *   `app/node_modules/typescript`. `scripts/port-agreement.py` states the rule this follows:
 *   "a check that needs a toolchain would fail on a machine that has none rather than on a
 *   defect". So it lives in `make check` beside `port-agreement`, `lint` and `typecheck`.
 *
 * It never writes outside the temporary directory `--self-test` creates and destroys. Exit 0
 * when clean, 1 when a finding stands.
 *
 *     scripts/screen-freshness.mjs              audit app/src
 *     scripts/screen-freshness.mjs --self-test  prove the recognizers before trusting a report
 */

import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.dirname(HERE)
const APP_SRC = path.join(ROOT, 'app', 'src')
const SERVER_TS = path.join(APP_SRC, 'server.ts')

/* The compiler the app itself builds with, never a copy and never a second parser. A hand
 * rolled matcher over this source would be a second opinion about what TypeScript means, and
 * `app/src` is 31,000 lines of it — including JSX, `satisfies`, `as const` and generic arrows
 * that a regex reads as comparison operators. Loaded from `app/node_modules` because that is
 * where it is; a machine with no `npm install` has no business running this check and the
 * error below says so in one line instead of throwing a module-resolution stack. */
const TYPESCRIPT = path.join(ROOT, 'app', 'node_modules', 'typescript', 'lib', 'typescript.js')
if (!fs.existsSync(TYPESCRIPT)) {
  console.error(
    'screen freshness: app/node_modules/typescript is missing, so nothing was checked — ' +
      'which is not the same as nothing being wrong. Run `npm install` in app/ first.',
  )
  process.exit(1)
}
const ts = (await import(pathToFileURL(TYPESCRIPT).href)).default

/* The three exports that carry a method literal and mutate NOTHING. They are write-SHAPED —
 * `POST` with a JSON body — because each asks the server a question too big for a query string,
 * and a classifier that goes by the verb alone reports all three as unfreshened writes.
 *
 * NAMED HERE RATHER THAN INFERRED, and then the naming is checked: `assertAllowlistIsEarned`
 * refuses any entry whose own doc comment does not claim in words that it writes nothing. That
 * is the difference between an allowlist and a suppression — this one cannot be extended by
 * adding a line here, only by adding a line here AND making the source say why. */
const NON_MUTATING = new Set([
  'preflightRun', 'cropPreview', 'fetchOrders', 'previewOrders', 'previewReconcileBacklog',
  'getInventoryCopies',
])
const NON_MUTATING_CLAIM = /writes nothing|creates no run directory|creates nothing/i

/* The classification this script was written against, asserted by `--self-test` as SETS and
 * not as counts — three reads becoming three writes keeps every count identical.
 *
 * IT LIVES IN THE SELF-TEST AND NOT ON THE AUDIT PATH ON PURPOSE. A legitimate write number 30,
 * properly freshened, must not fail `make check` merely for being new; what it must do is fail
 * `--self-test` until somebody updates this record, which is a deliberate act with a diff. The
 * ordinary run prints the counts in its summary line instead, so drift is visible without being
 * fatal. */
/* D89's pair — `getBoxPhotos` (a read) and `reclaimBoxPhotos` (a write) — were added the day
 * they landed, 2026-09-01, which is the deliberate act the paragraph below asks for. D86's
 * amendment had left three unrecorded the same day (`getPricingCorpus`, `putPricingCorpus`,
 * `emitMerged`) and D87's reconcile a fourth (`reconcileLive`), so `--self-test` was red on
 * main while the ordinary run printed the drift line; they are recorded here too, and the
 * `check` target is what runs the self-test — TRUE SINCE 2026-09-12 AND FALSE FOR AS LONG AS
 * IT HAD BEEN WRITTEN. `make screen-freshness-selftest` is a target of its own and is in both
 * `check` and `ci-check`; until then no recipe, hook or workflow passed `--self-test` at all.
 *
 * FIVE NAMES ARRIVED IN ONE UPDATE ON 2026-09-01, AND FOUR OF THEM WERE ALREADY OVERDUE.
 * `getPriceTrends` (D79), `getExportScope` (D76), `moveCard` and `moveCards` (D83) all landed
 * before `getPricingWorklist` (D86) and none of them updated this record, so the ordinary run
 * had been printing "classification has moved since it was recorded" for days with nobody
 * acting on it. That is exactly the drift the comment above predicts and the reason the record
 * is not on the audit path — it is meant to be updated by a deliberate act, and this is one.
 *
 * AND IT HAPPENED AGAIN ACROSS TWO COMMITS OF ONE BRANCH, WHICH IS THE CASE THE PARAGRAPH ABOVE
 * DOES NOT COVER: a deletion updated this record and an addition did not. `fillEnvelope` and
 * `undoEnvelope` were struck from `writes` the hour the envelope walk they reached was deleted
 * (D96, amended), so that half was the deliberate act; D100's four — `getMarkdowns`,
 * `markdownListings`, `applyMarkdown` and `markdownFileUrl`, one per bucket but `writes` — landed
 * two commits later against a record nobody re-read, and `--self-test` went from green to
 * `3 FAILED` while every `make check` on the branch stayed green, because the Makefile ran this
 * script WITHOUT `--self-test` — the gap closed on 2026-09-12 by `make screen-freshness-selftest`,
 * which is why this paragraph is a record rather than a live hazard. A record that is only ever pruned drifts in
 * one direction. The four are recorded here now, in the buckets the classifier already puts
 * them in. */
const RECORDED = {
  reads: [
    'getStatus', 'getInventory', 'getQueues', 'reviewCatalog', 'search', 'getGames', 'getBoxes',
    'getBoxListings', 'getPricing', 'getPriceHistory', 'getRuns', 'getRun', 'getTcgSets',
    'getOrders', 'getPriceTrends', 'getExportScope', 'getPricingWorklist', 'getPricingCorpus',
    'getBoxPhotos', 'getMarkdowns',
    // The graveyard's one read (D134). Its own line, for the reason the writes below give.
    'getGraveyard',
    // The markdown lens's three (D103) — the survey table, and D62's history and trends
    // strip re-addressed at a stamp instead of a run.
    'getMarkdownTable', 'markdownHistory', 'markdownTrends',
    // The band lens's whole input (D159): every card on hand, ranked, one row per copy.
    // Split in two by store-scaling item 7 — `getValueAggregates` (the store-wide totals,
    // boxes and unrankable counts) and `getValuePage` (one band's rows, cursor-paginated) —
    // where `getValueTable` used to fetch the whole unpaginated shape in one call.
    'getValueAggregates', 'getValuePage',
    // The claims panel's free count (D174): what a live send is holding.
    // It is the step that comes BEFORE the release below, which is why it is a read at all.
    'getSubmissions',
    // D192 (store-scaling item 2): the per-box read replacing the whole-store
    // `getInventory` on `#/inventory`, and the lean top-K deck read for Home's hero.
    'getInventoryBox', 'getRecentCards',
  ],
  writes: [
    'capture', 'updateCard', 'undoCapture', 'reshootPhoto', 'answerReview', 'standDown',
    'undoStandDown', 'undoAnswer', 'answerReviewGroup', 'markSold', 'undoSale', 'retireCard',
    'undoRetire', 'createBox', 'updateBox', 'openSection', 'applyBoxClaims', 'removeCardInPlace',
    'deleteBox', 'releaseBoxListings', 'startRun', 'fetchExport', 'runStep',
    'ingestOrders', 'pullCopy', 'undoPull', 'readShippingExport', 'forgetShippingExport',
    'moveCard', 'moveCards', 'putPricingCorpus', 'emitMerged', 'reconcileLive', 'reclaimBoxPhotos',
    'markdownListings', 'applyMarkdown',
    // The mass-clear and its inverse (D168), recorded by the
    // deliberate act this table's header asks for rather than left to widen the drift it
    // already names. On their own line so a branch adding its own writes does not conflict
    // with this one over the same line — the failure mode the header records happening twice.
    'clearPricingAnswers', 'restorePricingAnswers',
    // AND THE ONE-DIRECTION DRIFT THE HEADER ABOVE PREDICTED RAN FOR A THIRD TIME, LONGER AND
    // WIDER THAN EITHER EARLIER ONE: eighteen exports — five reads and thirteen writes —
    // accumulated with nothing removed, so `--self-test` reported `2 FAILED` with `missing:
    // (none)` in both buckets while every `make check` stayed green, because the Makefile
    // runs this script WITHOUT `--self-test`. Every one of the eighteen is recorded here in
    // the bucket the classifier already puts it in; not one recogniser was touched, because
    // the ordinary run was clean throughout — what was stale is this table, never the
    // analysis. Grouped by the decision that landed them, each group on its own line, so two
    // branches adding writes in the same week conflict over neither.
    'refreshQueues',                                              // D167, the store-wide re-resolve
    'pushMarkdown', 'rollbackMarkdown', 'publishMarkdown',        // D106, the two presses and the undo
    'fetchLiveExport',                                            // D104, the second document
    'fillLine', 'undoFill', 'declareLineKind',                    // D113, a line closes three ways
    'closeOrders', 'closeLines', 'reopenLines', 'reopenOrders',   // D113, the stand-down and its inverse
    'fillShippingStamps',                                         // order-pipeline.md §3 T2b
    'releaseSubmission',                                          // D174, the stuck claim's way out
    'nameOrders',                            // D193, the all-statuses
                                              // backfill naming a buyer the fetch found unnamed
    'reconcileBacklog',                      // D203, the one-time
                                              // stand-down over the historical backlog
    'rescueRun',                              // D165/D210, the run rebind
  ],
  // `previewReconcileBacklog` is the reconcile's press-nothing half and says so in its own
  // docstring — "FREE and WRITES NOTHING" — which is what earns a place on this list.
  // `getInventoryCopies` (DEBT27, site 1) is the same shape: a POST because the
  // SKU list is too big for a query string, over `Store().read()` alone.
  nonMutating: [
    'preflightRun', 'cropPreview', 'fetchOrders', 'previewOrders', 'previewReconcileBacklog',
    'getInventoryCopies',
  ],
  nonRequests: [
    'describeFailure', 'photoUrl', 'positionLabel', 'isDeparted', 'placeParts', 'placeSentence',
    'onServerBoot', 'newCaptureId', 'runFileUrl', 'shippingFileUrl', 'markdownFileUrl',
    // D207: listener-shaped exactly like `onServerBoot` above — it registers a
    // callback and returns an unsubscribe function, and makes no request of its own.
    'onServerReachable',
  ],
}

const MUTATING_METHODS = new Set(['POST', 'PUT', 'DELETE', 'PATCH'])

// --------------------------------------------------------------------------- AST plumbing

/** Depth-first over every node, self included. `ts.forEachChild` alone visits one level. */
function walk(node, visit) {
  visit(node)
  ts.forEachChild(node, (child) => walk(child, visit))
}

function collect(node, predicate) {
  const found = []
  walk(node, (n) => {
    if (predicate(n)) found.push(n)
  })
  return found
}

function parse(file, text) {
  return ts.createSourceFile(
    file,
    text,
    ts.ScriptTarget.Latest,
    /* setParentNodes */ true,
    file.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  )
}

function lineOf(src, node) {
  return src.getLineAndCharacterOfPosition(node.getStart(src)).line + 1
}

function isFunctionLike(node) {
  return (
    ts.isFunctionDeclaration(node) ||
    ts.isFunctionExpression(node) ||
    ts.isArrowFunction(node) ||
    ts.isMethodDeclaration(node)
  )
}

/** True for a node sitting anywhere inside a type annotation.
 *
 *  `RunPanel.tsx` writes `Parameters<typeof runStep>[2]` to type an argument default, and a
 *  naive scan for references to a write name counts that as the write being handed somewhere.
 *  It is a type query: it produces no call, at run time it does not exist. */
function inTypePosition(node) {
  for (let n = node.parent; n !== undefined; n = n.parent) {
    if (ts.isTypeNode(n) || ts.isTypeQueryNode(n)) return true
    if (isFunctionLike(n) || ts.isSourceFile(n)) return false
  }
  return false
}

/** The declared name of a function-like node, whether it is declared or assigned. */
function functionName(fn) {
  if (ts.isFunctionDeclaration(fn)) return fn.name?.text ?? null
  let n = fn.parent
  if (n !== undefined && ts.isCallExpression(n)) n = n.parent // useCallback(fn, deps)
  if (n !== undefined && ts.isVariableDeclaration(n) && ts.isIdentifier(n.name)) return n.name.text
  return null
}

/** Whether this function is declared at module scope — `function F() {}` or `const F = () => {}`.
 *
 *  This is what separates a COMPONENT (or a module helper) from a HANDLER inside one, and every
 *  scope decision below turns on it. */
function isTopLevelDeclared(fn) {
  if (ts.isFunctionDeclaration(fn)) return ts.isSourceFile(fn.parent)
  let n = fn.parent
  if (n !== undefined && ts.isCallExpression(n)) n = n.parent
  if (n === undefined || !ts.isVariableDeclaration(n)) return false
  const list = n.parent
  const statement = list?.parent
  return statement !== undefined && ts.isSourceFile(statement.parent)
}

// ------------------------------------------------------- pass 1: classify app/src/server.ts

/**
 * Split `server.ts` at its own section banners.
 *
 * The file marks its regions with `// ----- the orders` and `/* ----- the code-card track *␝/`
 * lines. Cutting at those rather than at a list of names means the code-card exclusion follows
 * the file: move a function across the banner and this follows it, add one inside the region
 * and it is excluded without anybody remembering to say so.
 */
function sectionBanners(text) {
  const banners = []
  const shape = /^(?:\/\/|\/\*) -{4,}\s*(.*?)\s*(?:\*\/)?$/gm
  let hit
  while ((hit = shape.exec(text)) !== null) banners.push({ at: hit.index, title: hit[1] })
  return banners
}

/** The half-open offset range of the region whose banner names the code-card track, or null. */
function codeCardRegion(text) {
  const banners = sectionBanners(text)
  const index = banners.findIndex((banner) => /code-card/i.test(banner.title))
  if (index === -1) return null
  const next = banners[index + 1]
  return { from: banners[index].at, to: next === undefined ? text.length : next.at }
}

/**
 * Every exported function in `server.ts`, sorted into reads, writes, write-shaped-but-not, and
 * things that never reach the wire at all.
 *
 * THE METHOD IS FOUND TRANSITIVELY. `undoSale` has no method literal in its body; it calls
 * `sale(box, index, true)`, and `sale` posts. Ten of the twenty-nine writes are that shape, in
 * five pairs, because a route reachable in both directions gets one private helper and two
 * exported names rather than two copies of the same `fetch`. So this builds the module's own
 * call graph and closes over it.
 */
function classifyServer(text) {
  const src = parse('server.ts', text)
  const region = codeCardRegion(text)

  const functions = new Map()
  walk(src, (node) => {
    if (!ts.isFunctionDeclaration(node) || node.name === undefined) return
    functions.set(node.name.text, {
      node,
      name: node.name.text,
      exported: (node.modifiers ?? []).some((m) => m.kind === ts.SyntaxKind.ExportKeyword),
      start: node.getStart(src),
      calls: new Set(),
      methods: new Set(),
    })
  })

  for (const record of functions.values()) {
    walk(record.node, (n) => {
      if (!ts.isCallExpression(n) || !ts.isIdentifier(n.expression)) return
      record.calls.add(n.expression.text)
      if (n.expression.text !== 'request') return
      const init = n.arguments[1]
      /* No init at all, or `NO_CACHE` (which is `{ cache: 'no-store' }` and carries no method),
       * both mean GET. Anything else must be an object literal with a string `method`. */
      if (init === undefined || !ts.isObjectLiteralExpression(init)) {
        record.methods.add('GET')
        return
      }
      const method = init.properties.find(
        (p) => p.name !== undefined && p.name.getText(src) === 'method',
      )
      record.methods.add(
        method === undefined ? 'GET' : method.initializer.getText(src).replace(/['"`]/g, ''),
      )
    })
  }

  const methodsOf = (name, seen = new Set()) => {
    if (seen.has(name)) return new Set()
    seen.add(name)
    const record = functions.get(name)
    if (record === undefined) return new Set()
    const out = new Set(record.methods)
    for (const callee of record.calls) for (const m of methodsOf(callee, seen)) out.add(m)
    return out
  }

  const result = { reads: [], writes: [], nonMutating: [], nonRequests: [], codeCard: [] }
  for (const record of functions.values()) {
    if (!record.exported) continue
    if (region !== null && record.start >= region.from && record.start < region.to) {
      result.codeCard.push(record.name)
      continue
    }
    const methods = [...methodsOf(record.name)]
    if (methods.length === 0) result.nonRequests.push(record.name)
    else if (!methods.some((m) => MUTATING_METHODS.has(m))) result.reads.push(record.name)
    else if (NON_MUTATING.has(record.name)) result.nonMutating.push(record.name)
    else result.writes.push(record.name)
  }
  return result
}

/**
 * Refuse an allowlist entry the source does not vouch for.
 *
 * A name in `NON_MUTATING` silences a whole class of finding for that function forever. The
 * only thing standing between that and a suppression is whether the function itself says, in
 * the comment a human reads, that it writes nothing — so that is checked rather than assumed.
 * All three earn it today: "creates no run directory at all", "FREE, writes nothing, shells out
 * to nothing", "it writes nothing at all, not even the ledger".
 */
function allowlistNotEarned(text) {
  const src = parse('server.ts', text)
  const unearned = []
  for (const name of NON_MUTATING) {
    const decl = collect(
      src,
      (n) => ts.isFunctionDeclaration(n) && n.name?.text === name,
    )[0]
    if (decl === undefined) {
      unearned.push(`${name} is allowlisted but no longer exists in server.ts`)
      continue
    }
    const leading = text.slice(decl.getFullStart(), decl.getStart(src))
    if (!NON_MUTATING_CLAIM.test(leading)) {
      unearned.push(`${name} is allowlisted but its own comment never says it writes nothing`)
    }
  }
  return unearned
}

// ---------------------------------------------------------------- pass 2: the screens

/**
 * Everything about one `.tsx` that more than one recogniser needs, worked out once.
 *
 * Building this per file rather than per call site is not only speed: several recognizers ask
 * questions ACROSS files — a callback prop is invoked in the child and bound in the parent, a
 * reload counter is bumped in `Inventory.tsx` and listed as a dependency in `BoxBrowse.tsx` —
 * and they can only be answered from the whole set at once.
 */
function readScreen(file, text, classification) {
  const src = parse(file, text)
  const screen = {
    file,
    name: path.basename(file),
    src,
    /** Local name -> server export name, for reads and writes separately. */
    reads: new Map(),
    writes: new Map(),
    /** Object-literal property names whose value is (or contains) a write. See the header. */
    writeProps: new Set(),
    /** Local declarations by name: function declarations, `const f = ...`, destructured hooks. */
    declarations: new Map(),
    /** `useState` setter name -> the state name beside it. */
    stateOf: new Map(),
    /** Component name -> { node, props:Set }. */
    components: new Map(),
  }

  walk(src, (node) => {
    if (ts.isImportDeclaration(node) && /['"]\.\/server['"]/.test(node.moduleSpecifier.getText(src))) {
      const bindings = node.importClause?.namedBindings
      if (bindings !== undefined && ts.isNamedImports(bindings)) {
        for (const element of bindings.elements) {
          const origin = (element.propertyName ?? element.name).text
          if (classification.writes.includes(origin)) screen.writes.set(element.name.text, origin)
          if (classification.reads.includes(origin)) screen.reads.set(element.name.text, origin)
        }
      }
    }

    if (ts.isFunctionDeclaration(node) && node.name !== undefined) {
      screen.declarations.set(node.name.text, { node, aliases: new Map() })
    }

    if (ts.isVariableDeclaration(node)) {
      // `const f = () => {}` / `const f = useCallback(fn, deps)` / `const f = function () {}`
      if (ts.isIdentifier(node.name) && node.initializer !== undefined) {
        const init = node.initializer
        if (isFunctionLike(init)) {
          screen.declarations.set(node.name.text, { node: init, aliases: new Map() })
        } else if (ts.isCallExpression(init) && isFunctionLike(init.arguments[0] ?? {})) {
          screen.declarations.set(node.name.text, { node: init.arguments[0], aliases: new Map() })
        }
      }
      // `const [value, setValue] = useState(...)`
      if (
        ts.isArrayBindingPattern(node.name) &&
        node.initializer !== undefined &&
        ts.isCallExpression(node.initializer) &&
        node.initializer.expression.getText(src) === 'useState'
      ) {
        const [value, setter] = node.name.elements
        if (
          value !== undefined && ts.isBindingElement(value) && ts.isIdentifier(value.name) &&
          setter !== undefined && ts.isBindingElement(setter) && ts.isIdentifier(setter.name)
        ) {
          screen.stateOf.set(setter.name.text, value.name.text)
        }
      }
      /* `const { busy, trouble, write } = useBoxWrite(onChanged)`.
       *
       * The write in `BoxOps.tsx` is a thunk handed to `write`, and every piece of the
       * freshness discipline — the lock, the refusal, the `onChanged()` — is inside the hook.
       * So each destructured name resolves to the HOOK'S body, and the hook's parameters are
       * mapped back to the arguments the component passed, which is what lets the callback
       * recogniser see that the thing being invoked in there is this component's own prop. */
      if (
        ts.isObjectBindingPattern(node.name) &&
        node.initializer !== undefined &&
        ts.isCallExpression(node.initializer) &&
        ts.isIdentifier(node.initializer.expression)
      ) {
        const hookName = node.initializer.expression.text
        const args = node.initializer.arguments
        for (const element of node.name.elements) {
          if (!ts.isIdentifier(element.name)) continue
          screen.declarations.set(element.name.text, { hook: hookName, args, aliases: new Map() })
        }
      }
    }

    if (
      ts.isPropertyAssignment(node) &&
      node.name !== undefined &&
      (ts.isIdentifier(node.name) || ts.isStringLiteral(node.name))
    ) {
      const mentionsWrite = collect(
        node.initializer,
        (n) =>
          ts.isIdentifier(n) &&
          screen.writes.has(n.text) &&
          !inTypePosition(n) &&
          !(ts.isCallExpression(n.parent) && n.parent.expression === n),
      )
      if (mentionsWrite.length > 0) screen.writeProps.add(node.name.text)
    }

    if (isFunctionLike(node) && isTopLevelDeclared(node)) {
      const name = functionName(node)
      if (name !== null && /^[A-Z]/.test(name)) {
        const props = new Set()
        const first = node.parameters[0]
        if (first !== undefined && ts.isObjectBindingPattern(first.name)) {
          for (const element of first.name.elements) {
            if (ts.isIdentifier(element.name)) props.add(element.name.text)
          }
        }
        screen.components.set(name, { node, props })
      }
    }
  })

  return screen
}

/** Every write call site on one screen — direct, and through a remembered `reverse`-style property. */
function writeSites(screen) {
  const sites = []
  walk(screen.src, (node) => {
    if (!ts.isCallExpression(node)) return
    if (ts.isIdentifier(node.expression) && screen.writes.has(node.expression.text)) {
      sites.push({ node, write: screen.writes.get(node.expression.text), through: null })
      return
    }
    if (
      ts.isPropertyAccessExpression(node.expression) &&
      screen.writeProps.has(node.expression.name.text)
    ) {
      sites.push({
        node,
        write: `.${node.expression.name.text}`,
        through: node.expression.name.text,
      })
    }
  })
  return sites
}

/**
 * The handler a write belongs to: the outermost function around it that is NOT declared at
 * module scope.
 *
 * That is the unit a person actually reasons about — one press, one effect, one async block —
 * and it is where the freshness discipline lives in every one of the ten screens. Widening past
 * it to the whole component would make the component's own mount-time read count as evidence
 * for every write in the file, which is exactly the rubber stamp this check must not become:
 * `Fulfillment.tsx` had that mount-time read the whole time it was serving stale rows.
 */
function handlerOf(site) {
  const chain = []
  for (let n = site.parent; n !== undefined; n = n.parent) if (isFunctionLike(n)) chain.push(n)
  if (chain.length === 0) return null
  const top = chain.findIndex(isTopLevelDeclared)
  if (top === -1) return chain[chain.length - 1]
  return top === 0 ? chain[0] : chain[top - 1]
}

/** The innermost enclosing component (an uppercase module-scope function), or null. */
function componentOf(screen, site) {
  for (let n = site.parent; n !== undefined; n = n.parent) {
    if (!isFunctionLike(n) || !isTopLevelDeclared(n)) continue
    const name = functionName(n)
    if (name !== null && screen.components.has(name)) return { name, ...screen.components.get(name) }
  }
  return null
}

/**
 * The nodes a recogniser may read as evidence for one write site.
 *
 * The handler, plus the body of every local function it calls, two levels deep. The second part
 * is not a convenience: `Fulfillment.tsx` ends its sale handler with `reread()`, `Orders.tsx`
 * with `await reread()`, and `RunPanel.tsx` with `await loadRuns()` — in all three the evidence
 * is one hop away, and a scan that stops at the handler's own body calls three correct screens
 * defective.
 */
function evidenceScope(screen, handler) {
  const nodes = [handler]
  const aliases = new Map()
  const seen = new Set()

  const expand = (node, depth) => {
    if (depth > 2) return
    walk(node, (n) => {
      if (!ts.isCallExpression(n) || !ts.isIdentifier(n.expression)) return
      const name = n.expression.text
      if (seen.has(name)) return
      seen.add(name)
      const declaration = screen.declarations.get(name)
      if (declaration === undefined) return
      if (declaration.hook !== undefined) {
        const hook = screen.declarations.get(declaration.hook)
        if (hook === undefined || hook.node === undefined) return
        // The hook's parameters, bound to what this component actually handed it.
        hook.node.parameters.forEach((parameter, index) => {
          const argument = declaration.args[index]
          if (
            ts.isIdentifier(parameter.name) &&
            argument !== undefined &&
            ts.isIdentifier(argument)
          ) {
            aliases.set(parameter.name.text, argument.text)
          }
        })
        nodes.push(hook.node)
        expand(hook.node, depth + 1)
        return
      }
      if (declaration.node === undefined) return
      nodes.push(declaration.node)
      expand(declaration.node, depth + 1)
    })
  }

  expand(handler, 0)
  return { nodes, aliases }
}

// ------------------------------------------------------------------- shape helpers

const isSetter = (node) =>
  ts.isCallExpression(node) && ts.isIdentifier(node.expression) && /^set[A-Z]/.test(node.expression.text)

/** `setX((n) => n + 1)` — a counter bump, matched by SHAPE and never by the identifier.
 *
 *  The counter is called `reloads` in `BoxBrowse.tsx` and `Inventory.tsx`, `reads` in
 *  `Fulfillment.tsx`, and `revision` in `CaptureScreen.tsx`, and the bump is sometimes behind a
 *  `useCallback` named `reread`. Matching a name would have found two of the four. */
function isCounterBump(node) {
  if (!isSetter(node)) return false
  const updater = node.arguments[0]
  if (updater === undefined || !ts.isArrowFunction(updater)) return false
  const parameter = updater.parameters[0]
  if (parameter === undefined || !ts.isIdentifier(parameter.name)) return false
  const body = ts.isBlock(updater.body) ? null : updater.body
  if (body === null || !ts.isBinaryExpression(body)) return false
  return (
    body.operatorToken.kind === ts.SyntaxKind.PlusToken &&
    ts.isIdentifier(body.left) &&
    body.left.text === parameter.name.text &&
    ts.isNumericLiteral(body.right)
  )
}

/** `setX((prev) => ...prev...)` — a local patch of held state against what just happened. */
function isFunctionalUpdate(node) {
  if (!isSetter(node)) return false
  const updater = node.arguments[0]
  if (updater === undefined || !ts.isArrowFunction(updater)) return false
  const parameter = updater.parameters[0]
  if (parameter === undefined || !ts.isIdentifier(parameter.name)) return false
  return collect(updater.body, (n) => ts.isIdentifier(n) && n.text === parameter.name.text).length > 0
}

const LIST_SURGERY = new Set(['filter', 'map', 'flatMap', 'concat', 'slice', 'some', 'every'])

/** The root identifier of `target.card.box` — `target`. Null for anything that has none.
 *
 *  THE CASTS ARE PEELED OFF FIRST, and that is not tidiness. `Pricing.tsx` once sent
 *  `putDecisions(run, sent as Record<string, unknown>)` (the per-run write, deleted with D86's
 *  amendment), and an `as` is a node in the tree: a version of this that stopped at it saw no
 *  argument named `sent`, could not match the `savedDoc.current = sent` two lines below, and
 *  reported the most carefully argued write on that screen as having no way back. A cast
 *  changes the type and nothing else, and `putPricingCorpus` is sent the same way. */
function rootIdentifier(node) {
  let n = node
  for (;;) {
    if (
      ts.isAsExpression(n) ||
      ts.isParenthesizedExpression(n) ||
      ts.isNonNullExpression(n) ||
      ts.isTypeAssertionExpression(n) ||
      (ts.isSatisfiesExpression !== undefined && ts.isSatisfiesExpression(n))
    ) {
      n = n.expression
      continue
    }
    if (ts.isPropertyAccessExpression(n) || ts.isElementAccessExpression(n)) {
      n = n.expression
      continue
    }
    break
  }
  return ts.isIdentifier(n) ? n.text : null
}

/** Whether this subtree reaches a server read: an imported read, or a raw `fetch`.
 *
 *  `RunPanel.tsx:openDecisions` was the raw one — `fetch(runFileUrl(openRun,'decisions.json'))`,
 *  the single request in this app that bypassed `server.ts`, deleted with the per-run editor
 *  (D86, amended 2026-09-02). `fetch` stays recognised here so the next raw read, if one is
 *  ever written, is a read to this scan rather than an unfreshened write beside it. */
function reachesRead(screen, node, depth = 0, seen = new Set()) {
  if (depth > 3) return false
  let found = false
  walk(node, (n) => {
    if (found || !ts.isCallExpression(n) || !ts.isIdentifier(n.expression)) return
    const name = n.expression.text
    if (screen.reads.has(name) || name === 'fetch') {
      found = true
      return
    }
    if (seen.has(name)) return
    seen.add(name)
    const declaration = screen.declarations.get(name)
    if (declaration?.node === undefined) return
    if (reachesRead(screen, declaration.node, depth + 1, seen)) found = true
  })
  return found
}

/** Every `useEffect` in a screen whose dependency array names `dep` and whose body re-reads. */
function readEffectDependsOn(screen, dep) {
  return collect(screen.src, (n) => {
    if (!ts.isCallExpression(n) || n.expression.getText(screen.src) !== 'useEffect') return false
    const deps = n.arguments[1]
    if (deps === undefined || !ts.isArrayLiteralExpression(deps)) return false
    if (!deps.elements.some((e) => ts.isIdentifier(e) && e.text === dep)) return false
    return reachesRead(screen, n.arguments[0] ?? n)
  }).length > 0
}

/** JSX attribute values, everywhere in the scanned set, for `<Component prop={...}>`. */
function jsxBindings(screens, component, prop) {
  const found = []
  for (const screen of screens) {
    walk(screen.src, (n) => {
      const opening = ts.isJsxSelfClosingElement(n)
        ? n
        : ts.isJsxOpeningElement(n)
          ? n
          : null
      if (opening === null || opening.tagName.getText(screen.src) !== component) return
      for (const attribute of opening.attributes.properties) {
        if (!ts.isJsxAttribute(attribute) || attribute.name.getText(screen.src) !== prop) continue
        const value = attribute.initializer
        if (value === undefined || !ts.isJsxExpression(value) || value.expression === undefined) continue
        found.push({ screen, node: value.expression, host: n })
      }
    })
  }
  return found
}

/** The component that owns a JSX node, so a forwarded prop can be chased to its real binding. */
function ownerComponent(screen, node) {
  for (let n = node.parent; n !== undefined; n = n.parent) {
    if (!isFunctionLike(n) || !isTopLevelDeclared(n)) continue
    const name = functionName(n)
    if (name !== null && screen.components.has(name)) return { name, ...screen.components.get(name) }
  }
  return null
}

/**
 * Whether a counter, once bumped, actually causes a read — here or in a child it is handed to.
 *
 * `Inventory.tsx` bumps `reloads` and never reads it: it passes it down as `reloadToken` to
 * `BoxBrowse` and to its own `CopiesPanel`, and the effects that list it as a dependency are
 * over there. Following that is the whole difference between "a counter moved" and "somebody
 * asked the server again".
 */
function counterCausesRead(screens, screen, stateName, seen = new Set()) {
  const key = `${screen.name}:${stateName}`
  if (seen.has(key)) return null
  seen.add(key)
  if (readEffectDependsOn(screen, stateName)) {
    return { idiom: 'reload counter, read effect in the same file', where: screen.name }
  }
  for (const other of screens) {
    for (const [component, meta] of other.components) {
      // Where is this identifier handed down as a prop?
      const handed = []
      walk(screen.src, (n) => {
        const opening = ts.isJsxSelfClosingElement(n) ? n : ts.isJsxOpeningElement(n) ? n : null
        if (opening === null || opening.tagName.getText(screen.src) !== component) return
        for (const attribute of opening.attributes.properties) {
          if (!ts.isJsxAttribute(attribute)) continue
          const value = attribute.initializer
          if (value === undefined || !ts.isJsxExpression(value)) continue
          const expression = value.expression
          if (expression !== undefined && ts.isIdentifier(expression) && expression.text === stateName) {
            handed.push(attribute.name.getText(screen.src))
          }
        }
      })
      for (const prop of handed) {
        if (!meta.props.has(prop)) continue
        if (readEffectDependsOn(other, prop)) {
          return {
            idiom: 'reload counter passed down as a prop',
            where: `${other.name}:<${component} ${prop}>`,
          }
        }
      }
    }
  }
  return null
}

/**
 * Whether a callback prop, invoked by the child, is bound at the parent to something that
 * re-reads.
 *
 * "The child said it told someone" is not the check. `BoxOps.tsx` is emphatic that the re-read
 * "belongs to the caller" and says nothing about what it re-reads; the claim is only true if a
 * caller exists and does. Forwarding is followed — `BoxOps` hands its own `onChanged` straight
 * down to `ReleaseListings` and `DeleteBox` — until it reaches an expression that bumps a
 * counter or calls a read. NO BINDING SITE ANYWHERE is a finding, not a pass: an orphan
 * callback is a re-read nobody performs.
 */
function callbackBindingReReads(screens, component, prop, depth = 0, seen = new Set()) {
  if (depth > 4) return null
  const key = `${component}.${prop}`
  if (seen.has(key)) return null
  seen.add(key)

  for (const binding of jsxBindings(screens, component, prop)) {
    const { screen, node, host } = binding
    const where = `${screen.name}:<${component} ${prop}>`

    /** The two mechanisms a binding may carry, asked of whatever expression really holds it. */
    const verdict = (expression) => {
      if (reachesRead(screen, expression)) return { where, how: 're-reads' }
      const bump = collect(expression, isCounterBump)[0]
      if (bump !== undefined) {
        const stateName = screen.stateOf.get(bump.expression.text)
        if (stateName !== undefined && counterCausesRead(screens, screen, stateName) !== null) {
          return { where, how: 'bumps a reload counter' }
        }
      }
      return null
    }

    if (ts.isIdentifier(node)) {
      const owner = ownerComponent(screen, host)
      if (owner !== null && owner.props.has(node.text)) {
        const deeper = callbackBindingReReads(screens, owner.name, node.text, depth + 1, seen)
        if (deeper !== null) return deeper
        continue
      }
      /* A BARE IDENTIFIER NAMING A LOCAL HANDLER — `onCleared={onCleared}` — AND IT WAS
       * INVISIBLE HERE UNTIL 2026-09-12. Every case in this script's own self-test binds an
       * inline arrow (`onChanged={() => setReloads(...)}`), and `reachesRead` walks for CALL
       * expressions: an identifier contains none, so it answered false without resolving
       * anything. A parent that re-reads through a named `useCallback` — the commonest binding
       * in this app — therefore read as NO MECHANISM AT ALL, while the identical handler
       * written inline was recognised. Found by a write whose parent folds and re-reads in a
       * named callback; the two cases below pin both directions.
       *
       * IT DOES NOT WIDEN WHAT COUNTS AS A MECHANISM, only where the script looks for one: the
       * handler still has to reach a read or bump a counter that does. */
      const local = screen.declarations.get(node.text)
      if (local?.node !== undefined) {
        const found = verdict(local.node)
        if (found !== null) return found
        continue
      }
    }
    const found = verdict(node)
    if (found !== null) return found
  }
  return null
}

// -------------------------------------------------------------------- the twelve recognizers

/**
 * Each recogniser answers one question about one write site and returns a sentence naming what
 * it found, or null. A site is covered if ANY of them fires, so the order changes only which
 * sentence gets printed — and that sentence is what somebody reads when they come back to ask
 * how this write stays fresh, so it is worth getting right.
 *
 * THE PER-WRITE MECHANISMS RUN FIRST AND THE PER-SCREEN ONES LAST. A boot subscription, a
 * background poller and a field nothing renders are all facts about the FILE: once one of them
 * holds, it holds for every write in it, so putting them early would relabel writes that have a
 * mechanism of their own. Measured: with the boot subscription checked second, `Shipping.tsx`'s
 * read of an export — which folds the answer straight into `batch` — was reported as being kept
 * fresh by `onServerBoot`, which is true of the file and not of that line.
 */
function recognizers(screens) {
  return [
    /* 10. OPTIMISTIC AUTOSAVE. `Pricing.tsx` never re-reads its document: the document on
     *     screen IS the intent, and staleness is `doc !== savedDoc.current` — a comparison,
     *     not a fetch. What makes that honest rather than a shortcut is that the write reports
     *     back into the same ref it is compared against, so a refused write leaves the screen
     *     dirty and the loop retries. Recognised by that reporting-back and by the comparison
     *     existing; without both it would be a screen that forgot to re-read. */
    ['optimistic autosave, reconciled against the sent document', (ctx) => {
      const sent = new Set(
        ctx.site.node.arguments.map(rootIdentifier).filter((name) => name !== null),
      )
      /* THE SENT DOCUMENT REACHES THE REF EITHER WHOLE OR KEYED, AND BOTH ARE THE SAME
       * MECHANISM. One screen holding one document assigns `ref.current = sent`. `Pricing.tsx`
       * has held one document PER RUN since D86 — the worklist merges the view and never the
       * file — so it folds the same value into a map: `ref.current = { ...ref.current, [run]:
       * sent }`. The evidence this recogniser wants is unchanged: the exact object that was
       * sent is what the ref ends up holding, and the ref is compared with `===`.
       *
       * DELIBERATELY NOT "ANY ASSIGNMENT TO `.current`". The spread of the ref's own current
       * value and a property whose value IS the sent identifier are both required, so a screen
       * that assigned something else — a fresh object, a server echo, a boolean — is still a
       * finding. Loosening this to any right-hand side would retire the check rather than
       * extend it, which is the one thing a guard must never do to get a commit through. */
      const foldsSent = (right) => {
        if (ts.isIdentifier(right)) return sent.has(right.text)
        if (!ts.isObjectLiteralExpression(right)) return false
        const spreadsSelf = right.properties.some(
          (prop) =>
            ts.isSpreadAssignment(prop) &&
            ts.isPropertyAccessExpression(prop.expression) &&
            prop.expression.name.text === 'current',
        )
        const carriesSent = right.properties.some(
          (prop) =>
            ts.isPropertyAssignment(prop) &&
            ts.isIdentifier(prop.initializer) &&
            sent.has(prop.initializer.text),
        )
        return spreadsSelf && carriesSent
      }
      for (const node of ctx.scope.nodes) {
        const assignments = collect(node, (n) =>
          ts.isBinaryExpression(n) &&
          n.operatorToken.kind === ts.SyntaxKind.EqualsToken &&
          ts.isPropertyAccessExpression(n.left) &&
          n.left.name.text === 'current' &&
          foldsSent(n.right))
        for (const assignment of assignments) {
          const ref = rootIdentifier(assignment.left)
          /* THE COMPARISON READS THE REF WHOLE OR BY KEY, matching the two shapes the fold
           * above accepts: `doc !== ref.current` for one document, and `docs[run] !==
           * ref.current[run]` for one per run. Both are the same claim — staleness is a
           * comparison against what the server confirmed, not a fetch — and a screen that
           * stored into the ref and never compared it is still a finding either way. */
          const readsRef = (side) => {
            const target = ts.isElementAccessExpression(side) ? side.expression : side
            return (
              ts.isPropertyAccessExpression(target) &&
              target.name.text === 'current' &&
              rootIdentifier(target) === ref
            )
          }
          const compared = collect(ctx.screen.src, (n) =>
            ts.isBinaryExpression(n) &&
            (n.operatorToken.kind === ts.SyntaxKind.ExclamationEqualsEqualsToken ||
              n.operatorToken.kind === ts.SyntaxKind.EqualsEqualsEqualsToken) &&
            [n.left, n.right].some(readsRef))
          if (compared.length > 0) return `against ${ref}.current`
        }
      }
      return null
    }],

    /* 3. onChanged-STYLE CALLBACK PROP. The child writes, the parent reads. Both halves are
     *    checked: invoked here, and bound at the parent to something that actually re-reads. */
    ['callback prop, re-read owned by the parent', (ctx) => {
      if (ctx.component === null) return null
      const invoked = new Set()
      for (const node of ctx.scope.nodes) {
        for (const call of collect(node, (n) => ts.isCallExpression(n) && ts.isIdentifier(n.expression))) {
          const name = call.expression.text
          invoked.add(ctx.scope.aliases.get(name) ?? name)
        }
      }
      for (const name of invoked) {
        if (!ctx.component.props.has(name)) continue
        const bound = callbackBindingReReads(ctx.screens, ctx.component.name, name)
        if (bound !== null) return `${name}() -> ${bound.where} ${bound.how}`
      }
      return null
    }],

    /* 1 and 2. RELOAD COUNTER OWNED BY THE READER, whether the reader is this component or a
     *    child it hands the counter to. The bump is matched by shape; the counter is then
     *    followed to whichever effect lists it. */
    ['reload counter', (ctx) => {
      for (const node of ctx.scope.nodes) {
        for (const bump of collect(node, isCounterBump)) {
          const stateName = ctx.screen.stateOf.get(bump.expression.text)
          if (stateName === undefined) continue
          const causes = counterCausesRead(ctx.screens, ctx.screen, stateName)
          if (causes !== null) return `${bump.expression.text} -> ${causes.idiom} (${causes.where})`
        }
      }
      return null
    }],

    /* 5. DIRECT REFETCH IN THE SAME ASYNC BLOCK. `await reread()`, `await loadRuns()`,
     *    `setDetail(await getRun(openRun))`. The plainest mechanism in the tree and the one
     *    that needs the evidence scope to reach one hop past the handler, because the refetch
     *    is nearly always a local function rather than the read itself. */
    ['direct refetch after the write', (ctx) => {
      for (const node of ctx.scope.nodes) {
        if (reachesRead(ctx.screen, node)) return 'a read runs in the same block'
      }
      return null
    }],

    /* 4. THE WRITE'S OWN RESPONSE CARRIES THE NEW STATE. `CaptureScreen.tsx` folds the created
     *    box row straight into `boxRecords` — "the answer IS the row `GET /boxes` would
     *    return, so a round trip would buy nothing and would put a second await between the
     *    press and the box being current". Recognised by the result binding reaching a
     *    setState, which is what separates it from a response that was merely received. */
    ['the response carries the new state', (ctx) => {
      const bound = resultBinding(ctx.site.node)
      if (bound === null) return null
      for (const node of ctx.scope.nodes) {
        for (const setter of collect(node, isSetter)) {
          const uses = collect(setter, (n) => ts.isIdentifier(n) && n.text === bound)
          if (uses.length > 0) return `${bound} -> ${setter.expression.text}(...)`
        }
      }
      return null
    }],

    /* 8. LOCAL PATCH FROM THE WRITE'S OWN ARGUMENTS, response deliberately discarded.
     *    `CaptureScreen.tsx:undoBack` says why in full: the response's `deleted` is the store's
     *    own key, "not a thing the operator has ever seen on this screen", so the patch is
     *    computed from `target` — the plan entry the delete was aimed at. Restricted to
     *    FUNCTIONAL updaters, which is what keeps a receipt that merely quotes an argument
     *    ("Note saved on <label>") from reading as a state patch. */
    ['local patch from the write\'s own arguments', (ctx) => {
      const roots = new Set(
        ctx.site.node.arguments.map(rootIdentifier).filter((name) => name !== null),
      )
      if (roots.size === 0) return null
      for (const node of ctx.scope.nodes) {
        for (const setter of collect(node, isFunctionalUpdate)) {
          for (const root of roots) {
            if (collect(setter.arguments[0], (n) => ts.isIdentifier(n) && n.text === root).length > 0) {
              return `${root} -> ${setter.expression.text}((prev) => ...)`
            }
          }
        }
      }
      return null
    }],

    /* 12. CACHE-BUSTING NONCE ON A PHOTO URL. A position can hold different bytes than it did
     *     five seconds ago — undo hard-deletes the photo and releases the index — so the URL
     *     is identical for two different cards and the cached image is the deleted one. The
     *     re-read alone does not fix that; the nonce is the other half. */
    ['cache-busting nonce on the photo URL', (ctx) => {
      const nonced = new Set()
      walk(ctx.screen.src, (n) => {
        if (ts.isTemplateExpression(n) && /\?v=|&v=/.test(n.getText(ctx.screen.src))) {
          for (const id of collect(n, (x) => ts.isIdentifier(x))) nonced.add(id.text)
        }
      })
      if (nonced.size === 0) return null
      for (const node of ctx.scope.nodes) {
        for (const setter of collect(node, (n) => isCounterBump(n) || isFunctionalUpdate(n))) {
          const stateName = ctx.screen.stateOf.get(setter.expression.text)
          if (stateName !== undefined && nonced.has(stateName)) return `${stateName} bumped`
        }
      }
      return null
    }],

    /* 9. OPTIMISTIC LIST SURGERY. The queue drops the row before the server answers because
     *    docs/DESIGN.md says answering advances with no acknowledgement to dismiss, and then
     *    reconciles against what came back — `clearedQueues` puts back any row whose queue the
     *    server did not name. The recognisable half is the surgery; the reconciliation is a
     *    correctness question this script cannot answer and does not claim to. */
    ['optimistic list surgery', (ctx) => {
      for (const node of ctx.scope.nodes) {
        for (const setter of collect(node, isFunctionalUpdate)) {
          const updater = setter.arguments[0]
          const parameter = updater.parameters[0].name.text
          const surgery = collect(updater.body, (n) =>
            (ts.isCallExpression(n) &&
              ts.isPropertyAccessExpression(n.expression) &&
              LIST_SURGERY.has(n.expression.name.text) &&
              rootIdentifier(n.expression) === parameter) ||
            (ts.isSpreadElement(n) && ts.isIdentifier(n.expression) && n.expression.text === parameter) ||
            (ts.isSpreadAssignment(n) && ts.isIdentifier(n.expression) && n.expression.text === parameter))
          if (surgery.length > 0) return `${setter.expression.text}((prev) => ...)`
        }
      }
      return null
    }],

    /* 11. THE WRITE CLOSES THE VIEW THAT SHOWED THE STATE. `Shipping.tsx` forgets the batch and
     *     sets it to null — "the export is gone, and the screen showing no export IS the
     *     receipt". `RunPanel.tsx` drops the decisions textarea the same way, and the button
     *     that fetches it again is right there. Only counts for state that is populated from a
     *     request somewhere in the file, which is what makes clearing it a way BACK rather than
     *     a way of hiding the disagreement. */
    ['the write clears the view that showed the state', (ctx) => {
      for (const node of ctx.scope.nodes) {
        for (const setter of collect(node, isSetter)) {
          const argument = setter.arguments[0]
          /* A STORE SETTER CLEARS A FIELD, WHICH IS THE SAME ACT ONE LEVEL IN. This read
             `setX(null)` and nothing else, and it was right while every screen held its own
             `useState`. `OrdersHubStore` put the shipping stage's batch in a shared store, so the
             clear is `setHub({ batch: null })` — the identical statement, made about a named
             field instead of about the whole of the state, and invisible to a check looking for
             a bare `null` argument. Found by this row firing on `OrdersShipStage.tsx`'s forget,
             which IS covered: the export is gone at the operator's own instruction, and the
             screen showing no export is the receipt.

             The narrowing that keeps it honest is unchanged and now applies per FIELD: the field
             must be one something in this file populates from an await, which is what makes
             clearing it a way back rather than a way of hiding the disagreement. */
          const cleared = []
          if (argument !== undefined && argument.kind === ts.SyntaxKind.NullKeyword) {
            cleared.push(null)
          } else if (argument !== undefined && ts.isObjectLiteralExpression(argument)) {
            for (const property of argument.properties) {
              if (!ts.isPropertyAssignment(property)) continue
              if (property.initializer.kind !== ts.SyntaxKind.NullKeyword) continue
              if (!ts.isIdentifier(property.name)) continue
              cleared.push(property.name.text)
            }
          }
          if (cleared.length === 0) continue
          const field = cleared.find((name) => name !== null)
          if (field !== undefined) {
            const filledField = collect(ctx.screen.src, (n) =>
              isSetter(n) &&
              n.expression.text === setter.expression.text &&
              n.arguments[0] !== undefined &&
              ts.isObjectLiteralExpression(n.arguments[0]) &&
              n.arguments[0].properties.some(
                (q) =>
                  ts.isPropertyAssignment(q) &&
                  ts.isIdentifier(q.name) &&
                  q.name.text === field &&
                  (collect(q.initializer, (x) => ts.isAwaitExpression(x)).length > 0 ||
                    (ts.isIdentifier(q.initializer) && awaitBoundNames(ctx.screen).has(q.initializer.text)))))
            if (filledField.length > 0) return `${setter.expression.text}({ ${field}: null }), re-fetched elsewhere`
          }
          if (!cleared.includes(null)) continue
          const stateName = ctx.screen.stateOf.get(setter.expression.text)
          if (stateName === undefined) continue
          const filled = collect(ctx.screen.src, (n) =>
            isSetter(n) &&
            n.expression.text === setter.expression.text &&
            n.arguments[0] !== undefined &&
            (collect(n.arguments[0], (x) => ts.isAwaitExpression(x)).length > 0 ||
              (ts.isIdentifier(n.arguments[0]) && awaitBoundNames(ctx.screen).has(n.arguments[0].text))))
          if (filled.length > 0) return `${setter.expression.text}(null), re-fetched elsewhere`
        }
      }
      return null
    }],

    /* 13 IS NOT HERE, AND ITS ABSENCE IS THE MOST IMPORTANT LINE IN THIS LIST.
     *
     * A `onServerBoot` subscription WAS a recogniser. It was written from a survey that listed
     * it beside the other twelve, and it is the only one that never looked at the write site:
     * it asked whether the FILE anywhere subscribes to the boot id, so every write in
     * `Shipping.tsx` was cleared by a fact about a different function.
     *
     * MEASURED, on the day this script was written. A bare `void forgetShippingExport('probe')`
     * with nothing after it — the exact regression this whole file exists to catch — was
     * injected into `Shipping.tsx` and the run reported "39 call sites, every one has a way
     * back". The self-test did not catch it either, because its fixture for this idiom asserted
     * the bug as the intended answer. A green run and a green self-test, over a defect.
     *
     * The idiom is real and the inference was wrong. `onServerBoot` fires when the boot id
     * changes, which is when the server PROCESS restarted — so it says "the thing the server
     * was holding in memory is gone", which is why `Shipping.tsx` uses it to drop a batch. It
     * has never said anything about whether a write this screen just made has been re-read.
     * Those are two different questions and only the second one is this file's.
     *
     * Nothing regressed by removing it: `Shipping.tsx`'s two real write sites are covered by
     * idiom 4 at :172 and idiom 11 at :200, both of which look at the handler. The self-test
     * keeps the fixture and inverts its expectation, so the shape that produced this hole is
     * now the case that proves it closed.
     */

    /* 7. WRITE-ONLY FIELD — the documented reason none is owed. `CaptureScreen.tsx` saves a
     *    note against the last capture and never renders `card.note` anywhere; there is
     *    nothing on screen for the write to have made stale. LAST BUT ONE deliberately: it is
     *    an argument from absence, and an absence is only worth trusting once every positive
     *    mechanism has been looked for and not found. */
    ['write-only field: nothing on screen renders it', (ctx) => {
      if (resultBinding(ctx.site.node) !== null) return null
      const payload = ctx.site.node.arguments.find((a) => ts.isObjectLiteralExpression(a))
      if (payload === undefined || payload.properties.length === 0) return null
      const keys = []
      for (const property of payload.properties) {
        if (property.name === undefined || !ts.isIdentifier(property.name)) return null
        keys.push(property.name.text)
      }
      const read = keys.filter((key) => fieldIsRead(ctx.screen, key, payload))
      return read.length === 0 ? `${keys.join(', ')} never read on this screen` : null
    }],

    /* 6. BACKGROUND POLLER. `RunPanel.tsx` and `BoxRuns.tsx` chain a dependency-free
     *    `setTimeout`, so some writes are fresh with NO per-write mechanism at all — the panel
     *    catches up on the next tick, and `RunPanel.tsx`'s one missing `loadRuns()` self-heals
     *    within four seconds. TRUE, AND THE WEAKEST THING IN THIS LIST, which is why it is last:
     *    "it will be right shortly" is a different promise from "it is right now", and a screen
     *    that leans on it shows the operator a stale row for as long as the interval. */
    ['a background poller re-reads this screen', (ctx) => {
      const pollers = collect(ctx.screen.src, (n) => {
        if (!ts.isCallExpression(n) || n.expression.getText(ctx.screen.src) !== 'useEffect') return false
        const body = n.arguments[0]
        if (body === undefined) return false
        const rearms = collect(body, (x) =>
          ts.isCallExpression(x) && /setTimeout|setInterval/.test(x.expression.getText(ctx.screen.src)))
        return rearms.length > 0 && reachesRead(ctx.screen, body)
      })
      return pollers.length > 0 ? 'a chained setTimeout keeps re-reading' : null
    }],
  ]
}

/** The name the write's answer was bound to — `const card = await capture(...)`, `.then((r) => ...)`. */
function resultBinding(call) {
  let node = call.parent
  if (node !== undefined && ts.isAwaitExpression(node)) node = node.parent
  if (node !== undefined && ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
    return node.name.text
  }
  // `W(...).then((answer) => ...)` — the answer is the callback's own parameter.
  if (
    node !== undefined &&
    ts.isPropertyAccessExpression(node) &&
    node.name.text === 'then' &&
    ts.isCallExpression(node.parent)
  ) {
    const handler = node.parent.arguments[0]
    if (handler !== undefined && isFunctionLike(handler)) {
      const parameter = handler.parameters[0]
      if (parameter !== undefined && ts.isIdentifier(parameter.name)) return parameter.name.text
    }
  }
  return null
}

/** Names bound from an await anywhere in the file — `const answer = await readShippingExport(...)`. */
function awaitBoundNames(screen) {
  if (screen._awaitBound !== undefined) return screen._awaitBound
  const names = new Set()
  walk(screen.src, (n) => {
    if (
      ts.isVariableDeclaration(n) &&
      ts.isIdentifier(n.name) &&
      n.initializer !== undefined &&
      collect(n.initializer, (x) => ts.isAwaitExpression(x)).length > 0
    ) {
      names.add(n.name.text)
    }
  })
  screen._awaitBound = names
  return names
}

/** Whether a payload key is read anywhere on this screen, ignoring the payload literal itself. */
function fieldIsRead(screen, key, exclude) {
  let read = false
  walk(screen.src, (n) => {
    if (read) return
    for (let up = n; up !== undefined; up = up.parent) if (up === exclude) return
    if (ts.isPropertyAccessExpression(n) && n.name.text === key) read = true
    else if (ts.isBindingElement(n) && ts.isIdentifier(n.name) && n.name.text === key) read = true
    else if (ts.isJsxAttribute(n) && n.name.getText(screen.src) === key) read = true
    else if (
      ts.isElementAccessExpression(n) &&
      n.argumentExpression !== undefined &&
      ts.isStringLiteral(n.argumentExpression) &&
      n.argumentExpression.text === key
    ) read = true
  })
  return read
}

// ------------------------------------------------------------------------- the audit itself

/**
 * Audit one write site, widening to its callers when the handler is a module-level wrapper.
 *
 * `Fulfillment.tsx:unsell` is the case: a module helper over `undoSale` that reads `not_sold` as
 * success, with no state of its own to patch and nothing to re-read. The freshness lives at its
 * one caller, and a check that stopped at the wrapper would report the file's most carefully
 * argued write as its only defect.
 */
function auditSite(screens, screen, site, checks, depth = 0) {
  const handler = handlerOf(site.node)
  if (handler === null) return { covered: null, handler: '(module scope)' }

  const scope = evidenceScope(screen, handler)
  const component = componentOf(screen, site.node)
  const context = { screens, screen, site, scope, component }
  for (const [idiom, check] of checks) {
    const detail = check(context)
    if (detail !== null) return { covered: { idiom, detail }, handler: functionName(handler) }
  }

  /* Nothing here. If this handler is itself a module-level helper — lowercase, module scope —
   * the evidence is at whoever calls it, so try each caller with the same question. */
  const name = functionName(handler)
  if (depth < 2 && name !== null && isTopLevelDeclared(handler) && !/^[A-Z]/.test(name)) {
    const callers = collect(screen.src, (n) =>
      ts.isCallExpression(n) && ts.isIdentifier(n.expression) && n.expression.text === name)
    for (const caller of callers) {
      if (handlerOf(caller) === handler) continue // a recursive call, not a caller
      const widened = auditSite(screens, screen, { ...site, node: caller }, checks, depth + 1)
      if (widened.covered !== null) {
        return {
          covered: {
            idiom: widened.covered.idiom,
            detail: `${widened.covered.detail} (at the caller, via ${name})`,
          },
          handler: widened.handler,
        }
      }
    }
  }
  return { covered: null, handler: name ?? '(anonymous)' }
}

function audit(files, classification) {
  const screens = files.map((file) => readScreen(file, fs.readFileSync(file, 'utf8'), classification))
  const checks = recognizers(screens)
  const findings = []
  const covered = []

  for (const screen of screens) {
    for (const site of writeSites(screen)) {
      const line = lineOf(screen.src, site.node)
      const result = auditSite(screens, screen, site, checks)
      const where = `${screen.name}:${line}`
      if (result.covered === null) {
        findings.push({
          where,
          write: site.write,
          handler: result.handler,
          message:
            `${site.write} is written in ${result.handler}() and nothing on this screen asks ` +
            'the server again, folds the answer in, or says in the code why none is owed',
        })
      } else {
        covered.push({ where, write: site.write, ...result.covered })
      }
    }
  }
  return { screens, findings, covered }
}

function tsxFiles(dir) {
  return fs
    .readdirSync(dir)
    .filter((name) => name.endsWith('.tsx'))
    .map((name) => path.join(dir, name))
    .sort()
}

function main() {
  const text = fs.readFileSync(SERVER_TS, 'utf8')
  const classification = classifyServer(text)

  const unearned = allowlistNotEarned(text)
  if (unearned.length > 0) {
    console.log('screen freshness: FAILED')
    for (const line of unearned) console.log(`  ${line}`)
    return 1
  }

  const { screens, findings, covered } = audit(tsxFiles(APP_SRC), classification)

  if (findings.length > 0) {
    console.log('screen freshness: FAILED')
    for (const finding of findings) console.log(`  ${finding.where}  ${finding.message}`)
    console.log('')
    console.log(
      '  A write with no way back leaves this screen disagreeing with the store and nothing ' +
        'on it saying so.',
    )
    console.log(
      '  Add the re-read, fold the answer in, or write the reason none is owed where the ' +
        'write is — the twelve shapes this recognises are listed in the header.',
    )
    return 1
  }

  const drift =
    setsMatch(classification.reads, RECORDED.reads) &&
    setsMatch(classification.writes, RECORDED.writes) &&
    setsMatch(classification.nonMutating, RECORDED.nonMutating)
  const touched = new Set(covered.map((c) => c.where.split(':')[0]))

  /* THE POLLER IS THE WEAK PASS AND A GREEN RUN HAS TO SAY SO OUT LOUD.
   *
   * Idiom 6 clears a write because a timer on the same screen will re-read within its interval.
   * That is TRUE, and it is the only recogniser whose promise is "it will be right shortly"
   * rather than "it is right now" — every other one names something that has already happened
   * by the time the handler returns. It is also, unavoidably, evaluated per FILE rather than per
   * handler, because a poller really does cover every write beside it.
   *
   * The consequence is that a polled screen is effectively exempt from this guard: a write added
   * there with nothing after it passes, and the operator sees a stale row for up to the interval.
   *
   * MEASURED rather than reasoned. A bare write was injected into each of the ten screens in
   * turn; nine reported it and `RunPanel.tsx` did not, which is this, working as designed.
   * Printing the roll is how a reader of a green run learns that without opening this file —
   * the same reason `scripts/port-agreement.py` prints what it did NOT cover. */
  const polled = [...new Set(
    covered.filter((c) => /poller/.test(c.idiom)).map((c) => c.where.split(':')[0]),
  )].sort()

  console.log(
    `screen freshness: ${classification.writes.length} writes, ${covered.length} call sites ` +
      `over ${touched.size} screens, every one has a way back` +
      (drift ? '' : ' (classification has moved since it was recorded — run --self-test)'),
  )
  if (polled.length > 0) {
    console.log(
      `  ${polled.join(', ')}: covered only by a background poller — right within its interval ` +
        'rather than right now, and a write added there would pass unexamined',
    )
  }
  console.log(
    `  server.ts: ${classification.reads.length} reads, ${classification.writes.length} writes, ` +
      `${classification.nonMutating.length} write-shaped and non-mutating, ` +
      `${classification.nonRequests.length} not requests, ` +
      `${classification.codeCard.length} in the code-card track and out of scope`,
  )
  return 0
}

const setsMatch = (a, b) =>
  a.length === b.length && [...a].sort().join(',') === [...b].sort().join(',')

// ------------------------------------------------------------------------------ self-test

/**
 * Prove the recognizers before trusting a report, in BOTH directions.
 *
 * One direction alone is worthless. A checker that only proves it accepts the tree degrades
 * into one that accepts everything — widen a recogniser far enough and every write looks
 * covered, the run stays green, and the guard is gone with nothing to show it went. So every
 * idiom gets a synthetic screen that must NOT be flagged AND a synthetic stale twin that MUST
 * be, built in a temporary directory and thrown away.
 */
function selfTest() {
  const failures = []
  const ok = (condition, label, detail = '') => {
    console.log(`  ${condition ? 'ok  ' : 'FAIL'} ${label}`)
    if (!condition) {
      failures.push(label)
      for (const line of String(detail).split('\n')) if (line !== '') console.log(`       ${line}`)
    }
  }

  console.log('screen-freshness self-test')
  console.log('='.repeat(72))

  console.log('\nserver.ts classifies into the sets this was written against')
  const text = fs.readFileSync(SERVER_TS, 'utf8')
  const classification = classifyServer(text)
  for (const bucket of ['reads', 'writes', 'nonMutating', 'nonRequests']) {
    const missing = RECORDED[bucket].filter((n) => !classification[bucket].includes(n))
    const extra = classification[bucket].filter((n) => !RECORDED[bucket].includes(n))
    ok(
      missing.length === 0 && extra.length === 0,
      `${bucket}: ${RECORDED[bucket].length} exactly`,
      `missing: ${missing.join(' ') || '(none)'}\nunexpected: ${extra.join(' ') || '(none)'}`,
    )
  }

  console.log('\nthe five private helpers still carry the method for ten exported writes')
  for (const pair of [
    ['answerReview', 'undoAnswer'],
    ['standDown', 'undoStandDown'],
    ['markSold', 'undoSale'],
    ['retireCard', 'undoRetire'],
    ['pullCopy', 'undoPull'],
  ]) {
    ok(
      pair.every((name) => classification.writes.includes(name)),
      `${pair.join(' / ')} are writes, though neither body holds the method`,
    )
  }

  console.log('\nthe non-mutating allowlist is earned by the source, not asserted here')
  const unearned = allowlistNotEarned(text)
  ok(unearned.length === 0, 'each allowlisted export says it writes nothing', unearned.join('\n'))

  console.log('\nthe code-card track is excluded by its banner, not by a list of names')
  ok(
    classification.codeCard.includes('scanCodes') && classification.codeCard.includes('buildLot'),
    'the code-card writes are out of scope (D14)',
    classification.codeCard.join(' '),
  )
  ok(
    !classification.writes.includes('scanCodes'),
    'and are not counted among the singles track\'s writes',
  )

  /* The synthetic screens. Two imports stand in for the whole of `server.ts` — `doWrite` and
   * `doRead` — so the cases are about the SHAPE of a screen and never about which route it
   * calls. Each pair is the idiom and its stale twin: identical but for the mechanism.
   *
   * THE SECOND ELEMENT IS THE RECOGNISER THAT MUST FIRE, NOT A BOOLEAN, and the difference is
   * what keeps this honest. "Was it flagged?" is answerable by a recogniser that has widened
   * until it covers everything, and a run of twenty-four green lines would say nothing about
   * whether idiom 12 is still recognised — case 12 would be passing on idiom 9's shape, and
   * nobody would know until the day a nonce-only screen went stale. `null` means the case MUST
   * be flagged; anything else is the exact label the audit has to return. */
  const synthetic = {
    reads: ['doRead'],
    writes: ['doWrite'],
    nonMutating: [],
    nonRequests: [],
    codeCard: [],
  }
  const head = "import { doRead, doWrite } from './server'\nimport { useCallback, useEffect, useState } from 'react'\n"

  const cases = [
    ['a bare write with nothing after it', null, `
      export function Bare() {
        const [rows, setRows] = useState(null)
        useEffect(() => { void doRead().then(setRows) }, [])
        const press = async () => { await doWrite(1, 2); setBusy(false) }
        return <button onClick={press}>{rows}</button>
      }`],
    ['1. reload counter owned by the reader', 'reload counter', `
      export function Counter() {
        const [rows, setRows] = useState(null)
        const [reloads, setReloads] = useState(0)
        useEffect(() => { void doRead().then(setRows) }, [reloads])
        const press = async () => { await doWrite(1, 2); setReloads((n) => n + 1) }
        return <button onClick={press}>{rows}</button>
      }`],
    ['1b. the same counter under another name, bumped behind a callback', 'reload counter', `
      export function Aliased() {
        const [rows, setRows] = useState(null)
        const [reads, setReads] = useState(0)
        const reread = useCallback(() => setReads((count) => count + 1), [])
        useEffect(() => { void doRead().then(setRows) }, [reads])
        const press = async () => { await doWrite(1, 2); reread() }
        return <button onClick={press}>{rows}</button>
      }`],
    ['1c. a counter bumped but listed in no read effect', null, `
      export function Orphaned() {
        const [rows, setRows] = useState(null)
        const [reloads, setReloads] = useState(0)
        useEffect(() => { void doRead().then(setRows) }, [])
        const press = async () => { await doWrite(1, 2); setReloads((n) => n + 1) }
        return <button onClick={press}>{reloads}{rows}</button>
      }`],
    ['2. reload counter passed down as a prop', 'reload counter', `
      export function Child({ reloadToken }: { reloadToken: number }) {
        const [rows, setRows] = useState(null)
        useEffect(() => { void doRead().then(setRows) }, [reloadToken])
        return <p>{rows}</p>
      }
      export function Parent() {
        const [reloads, setReloads] = useState(0)
        const press = async () => { await doWrite(1, 2); setReloads((n) => n + 1) }
        return <div><Child reloadToken={reloads} /><button onClick={press} /></div>
      }`],
    ['3. onChanged-style callback prop, bound at the parent', 'callback prop, re-read owned by the parent', `
      export function Ops({ onChanged }: { onChanged: () => void }) {
        const press = async () => { await doWrite(1, 2); onChanged() }
        return <button onClick={press} />
      }
      export function Owner() {
        const [rows, setRows] = useState(null)
        const [reloads, setReloads] = useState(0)
        useEffect(() => { void doRead().then(setRows) }, [reloads])
        return <div>{rows}<Ops onChanged={() => setReloads((n) => n + 1)} /></div>
      }`],
    ['3d. the callback bound as a bare identifier naming a local handler', 'callback prop, re-read owned by the parent', `
      export function Named({ onChanged }: { onChanged: () => void }) {
        const press = async () => { await doWrite(1, 2); onChanged() }
        return <button onClick={press} />
      }
      export function NamedOwner() {
        const [rows, setRows] = useState(null)
        const refresh = useCallback(async () => { setRows(await doRead()) }, [])
        useEffect(() => { void refresh() }, [refresh])
        return <div>{rows}<Named onChanged={refresh} /></div>
      }`],
    ['3e. the same bare identifier where the handler re-reads nothing', null, `
      export function Inert({ onChanged }: { onChanged: () => void }) {
        const press = async () => { await doWrite(1, 2); onChanged() }
        return <button onClick={press} />
      }
      export function InertOwner() {
        const [rows, setRows] = useState(null)
        const shrug = useCallback(() => { setRows(null) }, [])
        return <div>{rows}<Inert onChanged={shrug} /></div>
      }`],
    ['3b. the same callback with no binding site anywhere', null, `
      export function Loose({ onChanged }: { onChanged: () => void }) {
        const press = async () => { await doWrite(1, 2); onChanged() }
        return <button onClick={press} />
      }`],
    ['3c. the callback forwarded one level and then bound', 'callback prop, re-read owned by the parent', `
      export function Leaf({ onChanged }: { onChanged: () => void }) {
        const press = async () => { await doWrite(1, 2); onChanged() }
        return <button onClick={press} />
      }
      export function Middle({ onChanged }: { onChanged: () => void }) {
        return <Leaf onChanged={onChanged} />
      }
      export function Top() {
        const [rows, setRows] = useState(null)
        const [reloads, setReloads] = useState(0)
        useEffect(() => { void doRead().then(setRows) }, [reloads])
        return <div>{rows}<Middle onChanged={() => setReloads((n) => n + 1)} /></div>
      }`],
    ['4. the write\'s own response carries the new state', 'the response carries the new state', `
      export function Folded() {
        const [rows, setRows] = useState([])
        const press = async () => {
          const row = await doWrite(1, 2)
          setRows((prev) => [...prev.filter((k) => k.id !== row.id), row])
        }
        return <button onClick={press}>{rows.length}</button>
      }`],
    ['5. direct refetch in the same async block', 'direct refetch after the write', `
      export function Refetch() {
        const [rows, setRows] = useState(null)
        const reread = useCallback(async () => { setRows(await doRead()) }, [])
        const press = async () => { await doWrite(1, 2); await reread() }
        return <button onClick={press}>{rows}</button>
      }`],
    ['6. a background poller with no per-write mechanism', 'a background poller re-reads this screen', `
      export function Polled() {
        const [rows, setRows] = useState(null)
        useEffect(() => {
          let timer = 0
          const tick = async () => { setRows(await doRead()); timer = window.setTimeout(() => void tick(), 4000) }
          void tick()
          return () => window.clearTimeout(timer)
        }, [])
        const press = async () => { await doWrite(1, 2) }
        return <button onClick={press}>{rows}</button>
      }`],
    ['7. write-only field: nothing on screen renders it', 'write-only field: nothing on screen renders it', `
      export function NoteOnly() {
        const [said, setSaid] = useState(null)
        const press = async () => { await doWrite(1, 2, { scribble: 'x' }); setSaid('saved') }
        return <button onClick={press}>{said}</button>
      }`],
    ['7b. the same write when the field IS rendered', null, `
      export function NoteShown({ card }: { card: { scribble: string } }) {
        const [said, setSaid] = useState(null)
        const press = async () => { await doWrite(1, 2, { scribble: 'x' }); setSaid('saved') }
        return <button onClick={press}>{card.scribble}{said}</button>
      }`],
    ['8. local patch from the write\'s own arguments', "local patch from the write's own arguments", `
      export function Patched() {
        const [rows, setRows] = useState([])
        const press = async (target: { box: number; index: number }) => {
          await doWrite(target.box, target.index)
          setRows((prev) => prev.filter((r) => r.box !== target.box))
        }
        return <button onClick={() => void press({ box: 1, index: 2 })}>{rows.length}</button>
      }`],
    ['9. optimistic list surgery', 'optimistic list surgery', `
      export function Optimistic() {
        const [rows, setRows] = useState([])
        const press = async (key: string) => {
          setRows((prev) => prev.filter((r) => r.key !== key))
          await doWrite(1, 2)
        }
        return <button onClick={() => void press('k')}>{rows.length}</button>
      }`],
    ['10. optimistic autosave, reconciled against the sent document', 'optimistic autosave, reconciled against the sent document', `
      export function Autosave() {
        const [doc, setDoc] = useState(null)
        const saved = useRef(null)
        const dirty = doc !== null && doc !== saved.current
        useEffect(() => {
          if (!dirty) return
          const sent = doc
          void (async () => { await doWrite('run', sent); saved.current = sent })()
        }, [dirty, doc])
        return <textarea value={doc ?? ''} onChange={(e) => setDoc(e.target.value)} />
      }`],
    ['11. the write clears the view that showed the state', 'the write clears the view that showed the state', `
      export function Cleared() {
        const [batch, setBatch] = useState(null)
        const open = async () => { const answer = await doRead(); setBatch(answer) }
        const forget = async () => { await doWrite(1, 2); setBatch(null) }
        return <div>{batch === null ? <button onClick={open} /> : <button onClick={forget} />}</div>
      }`],
    ['12. cache-busting nonce on the photo URL', 'cache-busting nonce on the photo URL', `
      export function Nonced() {
        const [revision, setRevision] = useState(0)
        const src = \`/photo/1/2?v=\${revision}\`
        const press = async () => { await doWrite(1, 2); setRevision((prev) => prev + 1) }
        return <div><img src={src} /><button onClick={press} /></div>
      }`],
    ['13b. a boot subscription alone does NOT cover a write — see the note where 13 was', null, `
      export function Booted() {
        const [batch, setBatch] = useState(null)
        useEffect(() => onServerBoot(() => setBatch(null)), [])
        const press = async () => { await doWrite(1, 2) }
        return <button onClick={press}>{batch}</button>
      }`],
    ['the write stored as a value and called through a property', 'reload counter', `
      export function Stored() {
        const [rows, setRows] = useState([])
        const [reloads, setReloads] = useState(0)
        useEffect(() => { void doRead().then(setRows) }, [reloads])
        const receipt = { reverse: doWrite }
        const press = async () => { await receipt.reverse(1, 2); setReloads((n) => n + 1) }
        return <button onClick={press}>{rows.length}</button>
      }`],
    ['the same stored write with nothing after it', null, `
      export function StoredStale() {
        const [rows, setRows] = useState([])
        useEffect(() => { void doRead().then(setRows) }, [])
        const receipt = { reverse: doWrite }
        const press = async () => { await receipt.reverse(1, 2) }
        return <button onClick={press}>{rows.length}</button>
      }`],
    ['the write behind a module-level wrapper, evidence at the caller', 'reload counter', `
      async function quietly(box: number, index: number) {
        try { await doWrite(box, index) } catch { return }
      }
      export function Wrapped() {
        const [rows, setRows] = useState(null)
        const [reloads, setReloads] = useState(0)
        useEffect(() => { void doRead().then(setRows) }, [reloads])
        const press = async () => { await quietly(1, 2); setReloads((n) => n + 1) }
        return <button onClick={press}>{rows}</button>
      }`],
    ['the same wrapper when no caller re-reads either', null, `
      async function quietly(box: number, index: number) {
        try { await doWrite(box, index) } catch { return }
      }
      export function WrappedStale() {
        const [rows, setRows] = useState(null)
        useEffect(() => { void doRead().then(setRows) }, [])
        const press = async () => { await quietly(1, 2) }
        return <button onClick={press}>{rows}</button>
      }`],
    ['the write inside a thunk handed to a hook that calls the callback', 'callback prop, re-read owned by the parent', `
      function useWrite(onChanged: () => void) {
        const write = useCallback(async (run) => { const answer = await run(); onChanged(); return answer }, [onChanged])
        return { write }
      }
      export function Thunked({ onChanged }: { onChanged: () => void }) {
        const { write } = useWrite(onChanged)
        const press = () => write(() => doWrite(1, 2))
        return <button onClick={press} />
      }
      export function ThunkOwner() {
        const [rows, setRows] = useState(null)
        const [reloads, setReloads] = useState(0)
        useEffect(() => { void doRead().then(setRows) }, [reloads])
        return <div>{rows}<Thunked onChanged={() => setReloads((n) => n + 1)} /></div>
      }`],
  ]

  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pkmnscan-freshness.'))
  try {
    console.log('\na stale write is flagged, and each idiom is recognised as ITSELF')
    cases.forEach(([label, expected, body], index) => {
      const file = path.join(tmp, `Case${index}.tsx`)
      fs.writeFileSync(file, head + body + '\n', 'utf8')
      const { findings, covered } = audit([file], synthetic)
      if (expected === null) {
        ok(
          findings.length > 0,
          `flagged        ${label}`,
          covered.map((c) => `covered instead by: ${c.idiom} (${c.detail})`).join('\n'),
        )
      } else {
        const fired = covered.map((c) => c.idiom)
        ok(
          findings.length === 0 && fired.includes(expected),
          `${expected === covered[0]?.idiom ? 'recognised as' : 'MISATTRIBUTED '} ${label}`,
          findings.length > 0
            ? findings.map((f) => f.message).join('\n')
            : `wanted: ${expected}\ngot:    ${fired.join(' | ') || '(nothing)'}`,
        )
      }
      fs.rmSync(file)
    })

    /* THE KNOWN BLIND SPOT, ASSERTED RATHER THAN LEFT TO BE REDISCOVERED. This case documents
     * a FALSE NEGATIVE on purpose: a write whose answer is shown as a receipt reads as idiom 4,
     * because "the response went into state" is the only thing the AST offers and a receipt and
     * a refreshed row are the same shape. Pinned so that a future tightening of idiom 4 shows
     * up here as a changed expectation — a deliberate act with a diff — instead of a limit that
     * quietly stopped or started applying. The header states it in the same words. */
    console.log('\nthe known blind spot, pinned so it cannot change silently')
    const receipt = path.join(tmp, 'Receipt.tsx')
    fs.writeFileSync(receipt, head + `
      export function Receipted({ onChanged }: { onChanged: () => void }) {
        const [got, setGot] = useState(null)
        const press = async () => { const result = await doWrite(1); setGot(result) }
        return <div><button onClick={press} />{got}</div>
      }` + '\n', 'utf8')
    const receipted = audit([receipt], synthetic)
    ok(
      receipted.findings.length === 0 &&
        receipted.covered[0]?.idiom === 'the response carries the new state',
      'a receipt still reads as a refresh — the one regression this cannot catch',
      receipted.findings.map((f) => f.message).join('\n'),
    )

    console.log('\na screen that only reads is never visited at all')
    const readOnly = path.join(tmp, 'ReadOnly.tsx')
    fs.writeFileSync(readOnly, head + '\nexport function R() { void doRead(); return null }\n', 'utf8')
    const quiet = audit([readOnly], synthetic)
    /* NON-VACUOUS, AND IT WAS NOT BEFORE. `findings.length === 0 && covered.length === 0`
     * is the same answer whether this screen genuinely has no writes or whether nothing was
     * READ AT ALL — a clean subject and an empty subject printing one word. That is this
     * repo's signature defect (a guard that cannot tell "nothing is wrong" from "nothing is
     * known yet"), and it matters more now that `make check` gates this self-test: the case
     * that certifies "no writes here" was the one case that would also have certified a
     * classifier which had stopped reading files. So the SUBJECT is asserted too. */
    ok(
      quiet.screens.length === 1 &&
        quiet.screens[0].src !== undefined &&
        writeSites(quiet.screens[0]).length === 0 &&
        quiet.findings.length === 0 &&
        quiet.covered.length === 0,
      'a read-only screen is READ and holds no write site — the subject asserted, not inferred from silence',
      `screens=${quiet.screens.length} sites=${quiet.screens.length === 1 ? writeSites(quiet.screens[0]).length : '?'} findings=${quiet.findings.length} covered=${quiet.covered.length}`,
    )
  } finally {
    fs.rmSync(tmp, { recursive: true, force: true })
  }

  console.log('\nthe real tree is clean, which is the state this was written against')
  const live = audit(tsxFiles(APP_SRC), classification)
  ok(
    live.findings.length === 0,
    `${live.covered.length} write call sites, every one covered`,
    live.findings.map((f) => `${f.where}  ${f.message}`).join('\n'),
  )

  console.log('')
  if (failures.length > 0) {
    console.log(`${failures.length} FAILED`)
    return 1
  }
  console.log('all checks passed')
  return 0
}

const argument = process.argv[2]
if (argument === '--self-test') process.exit(selfTest())
else if (argument !== undefined) {
  console.error('usage: scripts/screen-freshness.mjs [--self-test]')
  process.exit(64)
} else process.exit(main())
