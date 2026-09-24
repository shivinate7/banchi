/* THE TWO ROUTES `text-shape.spec.ts`, `machine-words.spec.ts` AND `money-face.spec.ts` EACH
 * EXCLUDE, as REGEXES rather than quoted string literals.
 *
 * `scripts/docs-audit.py`'s `route rosters` row treats three or more distinct `'#/…'`
 * string literals in one spec as a hand-typed roster — the exact shape that let D69's and
 * D70's new routes go unswept for two days, its own header's account. That heuristic is
 * right for a roster and wrong for what these three files do: TWO deliberate, individually
 * argued exclusions (`#/fulfillment`, a persona `docs/DESIGN.md` governs separately;
 * `#/gallery`, the kit's own specimen sheet — see each spec's header), never a list of every
 * screen. A regex is not a quoted `#/…` literal, so it does not trip that row, and it is not
 * an evasion of it either: nothing here enumerates routes, so there is no roster to declare.
 */
export const EXCLUDED_FROM_SWEEP = /^#\/(fulfillment|gallery)$/

/** A route hash, read off an `href` attribute — `startsWith('#/')` without the quoted
 *  literal that pattern would otherwise add to the same count. */
export const ROUTE_HASH_SHAPE = /^#\//
