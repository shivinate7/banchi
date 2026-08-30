import type { RunSummary } from './types'

/* WHICH DRAWER A RUN WAS OVER, AND WHAT THE OWNER CALLS IT — one answer, three screens.
 *
 * THE COMPLAINT THAT PRODUCED THIS (D56): *"I need the pricing tab to include the name of
 * the box that i gave it, not just the date and the raw box number."* `#/pricing`'s run
 * picker drew `2026-08-30-box3-01` over `15 SKUs` — a directory name and a count — while the
 * store had been holding `RB Epics` the whole time. Every screen that mentions a run had the
 * same hole, and each was one lookup away from filling it.
 *
 * THE BOX IS THE SERVER'S ANSWER NOW. `server/pipeline_routes.py:_summary` sends `box` and
 * `box_name` on every run: the first by `_run_box`, which reads the manifest's scope block
 * and falls back to the capture directory's own name; the second by joining that number
 * against the box registry AT READ TIME, so a rename lands on the next poll rather than on
 * the next run. Neither is stored on the run, and `box_name` must never be — D20 makes a
 * rename a live edit that relabels every card in the box on every screen that draws one, so a
 * name copied into a manifest would go stale the first time the drawer is relabelled.
 *
 * WHAT THIS REPLACES IS A SECOND IMPLEMENTATION OF `_run_box` IN TYPESCRIPT. `boxOf` used to
 * derive the box itself, with `/box(\d+)/` over the whole capture path where the server
 * anchors `^box(\d+)` on its BASENAME — so a parent directory with a number after `box` in it
 * would have answered differently on the two sides. It agreed on every run on this machine and
 * was one oddly-named folder from not agreeing, which is the kind of disagreement that shows
 * up as a run filed under the wrong box and nothing else. The derivation survives only as the
 * fallback below.
 */

/** Which box a run was over.
 *
 *  THE SERVER'S ANSWER FIRST, THE OLD DERIVATION SECOND, and the second half is kept for one
 *  reason: this payload is cast rather than validated, so a server predating `box` answers
 *  without it and the screens must not lose their grouping over a field that is merely
 *  absent. Same shape `PricingPayload.written_at` takes for the same reason. */
export function boxOf(row: RunSummary): number | null {
  if (typeof row.box === 'number') return row.box
  if (row.scope != null) return row.scope.box
  const found = /box(\d+)/.exec(row.capture_dir ?? '')
  return found === null ? null : Number(found[1])
}

/** `Box 3 · RB Epics`, or `Box 3` where the owner has not named it.
 *
 *  BOTH HALVES, NEVER ONE. `CLAUDE.md` is explicit that the name travels BESIDE the number
 *  rather than replacing it, and both are load-bearing on these screens: the name is what the
 *  operator recognises, and the number is the shelf they walk to, the directory the
 *  photographs are in, and what every refusal in `server/pipeline_routes.py` names.
 *
 *  AN UNNAMED BOX DRAWS NO SEPARATOR AND NO PLACEHOLDER. D20 makes a name unique and
 *  deliberately NOT required, so unnamed is an ordinary box rather than a defect, and `Box 3 ·
 *  —` would draw a fault where there is none. Same for a box that has since been deleted:
 *  the run remembers a number the registry no longer has, and the number alone is the honest
 *  rendering of that. */
export function boxLabel(
  box: number | null | undefined,
  name: string | null | undefined,
): string | null {
  if (typeof box !== 'number') return null
  const named = typeof name === 'string' ? name.trim() : ''
  return named === '' ? `Box ${box}` : `Box ${box} · ${named}`
}

/** The same, for a run, which carries both fields itself. `null` where the run names no box —
 *  which no run on this machine does, and which a manifest with neither a scope block nor a
 *  box-shaped capture directory would. */
export function runBoxLabel(row: RunSummary): string | null {
  return boxLabel(boxOf(row), row.box_name)
}
