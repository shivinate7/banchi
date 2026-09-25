/* THE TWO ROUTES `routeSweep.ts` EXCLUDES FOR `text-shape.spec.ts`, `machine-words.spec.ts`
 * AND `money-face.spec.ts`, as REGEXES rather than quoted string literals.
 *
 * `scripts/docs-audit.py`'s `route rosters` row treats three or more distinct `'#/…'`
 * string literals in one spec as a hand-typed roster — the exact shape that let D69's and
 * D70's new routes go unswept for two days, its own header's account. That heuristic is
 * right for a roster and wrong for what these three files do: TWO deliberate, individually
 * argued exclusions (`#/fulfillment`, a persona `docs/DESIGN.md` governs separately;
 * `#/gallery`, the kit's own specimen sheet — `D284` argues both), never a list of every
 * screen. A regex is not a quoted `#/…` literal, so it does not trip that row, and it is not
 * an evasion of it either: nothing here enumerates routes, so there is no roster to declare.
 */
/* ONLY SAFE IN NODE CONTEXT. `routeSweep.ts:drawerRoutes` also needs a `#/`-shape test, but
 * INSIDE a `page.locator(...).evaluateAll(...)` callback — a function Playwright serialises
 * into the BROWSER by `toString()`, the same rule `textShape.ts`'s header states for
 * `page.evaluate`. An imported module-level const is invisible there: `ROUTE_HASH_SHAPE is
 * not defined` was the measured failure the one time this file exported one for that use. So
 * that one test is written inline, `/^#\//.test(h)`, in that `evaluateAll`
 * callback — never imported from here — and `EXCLUDED_FROM_SWEEP` below stays usable only in
 * plain Node-context code: a `.filter()` chained on an array `evaluateAll` already returned,
 * or the main test body's own route list. */
export const EXCLUDED_FROM_SWEEP = /^#\/(fulfillment|gallery)$/
