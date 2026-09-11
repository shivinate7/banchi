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
/*  A REAL BOX NUMBER GETS A STRING BACK. Every caller but `runBoxLabel` passes a number the
 *  types already guarantee — `CartBox.box` and `RunScope.box` are both plain `number` — so a
 *  nullable return had three call sites each answering a state none of them can be in, and
 *  answering it three different ways.
 *
 *  IT IS NOT A COMPILE-TIME PROOF, AND CLAIMING SO WAS THE FIRST DRAFT'S MISTAKE. Removing
 *  this signature produces no type error anywhere: JSX renders a `null` child as nothing and a
 *  template literal stringifies it, so both shapes these values arrive in swallow it silently.
 *  TypeScript never had a stake in this.
 *
 *  WHAT THE DELETED FALLBACKS WERE WORTH IS ZERO, MEASURED. Two of the three carried
 *  `?? Box ${box}`, which on a null box renders the string `Box null` — the same garbage one
 *  step later. The third carried nothing and rendered empty. They read as defensiveness and
 *  were noise: there is nothing honest to draw from a box number the server failed to send,
 *  and the guard against that belongs at the source — T7's subset-scope case — not here.
 *
 *  The nullable arm stays for `runBoxLabel`, whose `boxOf` can genuinely answer null: a
 *  payload with no `box` field and no box-shaped capture directory to fall back to. */
export function boxLabel(box: number, name: string | null | undefined): string
export function boxLabel(
  box: number | null | undefined,
  name: string | null | undefined,
): string | null
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

/** What the capture screen calls the drawer in front of the operator: its NAME, and its number
 *  only where the owner has not given it one (D-capture-setup-memory).
 *
 *  THE OWNER'S INSTRUCTION, 2026-09-11: *"i dont need to see box number in capture screen"*.
 *  D20 is why that is answerable at all — a box is addressed by its name and names are unique,
 *  so `RB Epics` identifies a drawer as completely as `Box 3` does and identifies it in the word
 *  the operator actually thinks in. At the lens they are not walking a shelf or reading a path;
 *  they are putting cards into the box that is open on the desk, and they named it.
 *
 *  AN UNNAMED BOX STILL DRAWS ITS NUMBER, AND THAT IS NOT AN EXCEPTION TO THE INSTRUCTION. D20
 *  makes a name unique and deliberately NOT required, so a box with none is an ordinary box; its
 *  number is then the only thing it HAS to be called, and `boxLabel`'s own rule applies — a
 *  placeholder in the name's place would draw a fault where there is none (D56). The number is
 *  removed as the thing the operator has to read PAST, never as the thing a box IS.
 *
 *  `boxLabel` IS UNCHANGED AND IS STILL WHAT EVERY OTHER SCREEN USES. `Box 3 · RB Epics` is
 *  correct on `#/runs`, `#/pricing` and the run receipts for the reason written there: the
 *  number is the shelf, the photograph directory and what every refusal in
 *  `server/pipeline_routes.py` names, and those screens are read next to all three. The capture
 *  screen is the one place the operator is holding the physical box, which is why it is the one
 *  place that can drop the number — and why this is a second function rather than an argument to
 *  the first. The position LABEL (`pipeline/join.py:Position`) is untouched everywhere, this
 *  screen's own filmstrip and receipts included: the Fulfiller reads those, and he is walking a
 *  shelf he did not pack. */
export function captureBoxLabel(box: number, name: string | null | undefined): string {
  const named = typeof name === 'string' ? name.trim() : ''
  return named === '' ? `Box ${box}` : named
}
