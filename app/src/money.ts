/* A DOLLAR AMOUNT, SAID THE SAME WAY EVERYWHERE.
 *
 * EXTRACTED FROM `RunsComposer.tsx` ON 2026-09-11, UNCHANGED, when the run panel began
 * reporting what a finished run cost — the same move `reasons.ts` records for itself, and for
 * the same reason its header gives: a second copy defeats the point of having one.
 *
 * AND IT HAD TO LEAVE THAT FILE ANYWAY. `position.ts` states the mechanical half: React
 * Refresh only updates a module in place when EVERY export it has is a component, so one
 * exported function beside one component reloads the whole page on every edit.
 *
 * NOTHING HERE COMPUTES MONEY, WHICH IS THE RULE THIS REPO WRITES DOWN THREE TIMES.
 * `types.ts:RunPreflightTotal`, `pipeline_routes.py:_parse_preflight` and `_total` all say the
 * figure is the SERVER'S: `identify/cost.py` holds the only rate sheet in the repo. These are
 * formatters over a number that already arrived.
 *
 * NOT THE KIT. `kit/` is components, and `#/gallery` renders all of it; a formatter renders
 * nothing there. The kit owns the money VISUAL — `.bn-money` in `kit.css`, over the
 * `--bn-money` token — and the app owns the string. */

/** `$1.23`, or `—` where there is no figure. The one place a dollar amount becomes a string. */
export function money(value: number | null | undefined): string {
  return typeof value === 'number' ? `$${value.toFixed(2)}` : '—'
}

/** `$66,334.71`, or `—` where there is no figure — `money()`'s own grouped sibling, never a
 *  replacement for it. A card's price is one glance at three or four digits and a thousands
 *  separator there would be noise; a STORE-WIDE TOTAL is a headline read at five or six
 *  figures, where the same comma is the difference between reading it and counting zeros.
 *  `toLocaleString` is locale-aware by design — this repo has one owner and one locale, and
 *  the day that stops being true is the day this earns an explicit `en-US`. */
export function moneyGrouped(value: number | null | undefined): string {
  if (typeof value !== 'number') return '—'
  const [whole, cents = '00'] = value.toFixed(2).split('.')
  return `$${Number(whole).toLocaleString()}.${cents}`
}

/** True where a figure is REAL MONEY and still rounds to `$0.00`.
 *
 *  IT IS A FACT ABOUT `toFixed(2)` AND THAT IS WHY IT LIVES HERE RATHER THAN IN PYTHON. A run
 *  that spent a third of a cent spent something, and a screen drawing `$0.00` over it has said
 *  the opposite of what happened — while a run that spent nothing at all, because the cache
 *  owned every card, is a different sentence again. Both are indistinguishable once a figure is
 *  rounded to money's own unit, which is why the server sends six places and not two. */
export function roundsToNothing(value: number | null | undefined): boolean {
  return typeof value === 'number' && value > 0 && value < 0.005
}
