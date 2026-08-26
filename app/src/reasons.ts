/* THE REVIEW QUEUE'S REASON VOCABULARY, IN ONE FILE BECAUSE TWO SCREENS READ IT.
 *
 * EXTRACTED FROM `ReviewQueue.tsx` ON 2026-08-25, unchanged, when `#/inventory`'s card panel
 * began saying whether the selected card has an open question. The docstring below is the whole
 * argument for why this may not be copied: it records that NOTHING keeps these labels in step
 * with `pipeline/variant.py` and `pipeline/routing.py`, and that the defence is making that
 * drift visible rather than silent. A second copy in one app defeats that defence completely —
 * the two would drift against each other as well as against the pipeline, and only one of them
 * would ever be looked at.
 *
 * `reasonLabel`'s `?? reason` fallback is part of the contract, not a guard: an unknown code
 * renders as ITSELF in both slots, so a reason the pipeline gained and this file did not shows
 * up as a machine string on screen rather than as a blank line.
 */

/* The FOURTEEN, transcribed from the two modules that emit them: seven from
 * `pipeline/variant.py` (the D3 ladder's review reasons, including D23's
 * `rarity_claim_mismatch`) and seven from `pipeline/routing.py` (v2 §5.4's routing reasons,
 * including D35's `number_unread_name_matched`). It read "twelve, six and six" until
 * 2026-08-25, having been written before either of those two landed. docs/DESIGN.md requires each on screen as a human label with
 * the machine string small beneath it, because a friendly label alone is a second vocabulary
 * that nothing audits and a raw string alone is honest and unreadable.
 *
 * NOTHING KEEPS THIS MAP IN STEP WITH THOSE MODULES, and pretending otherwise would be
 * worse than saying so. A TypeScript file cannot import a Python constant, and no check in
 * this repo compares the two — the same gap `docs/DEBTS.md` records for `tokens.css` against
 * docs/DESIGN.md. What this file does instead is make drift VISIBLE rather than silent: an
 * unknown code renders as itself in both slots, with a sentence saying the screen has no
 * label for it, so a reason added to the pipeline shows up here as a plain string rather
 * than as a blank line.
 *
 * The labels are still the least tested copy in the product, and Gate B narrowed that rather
 * than closing it. TWO of the fourteen have now fired against a photograph of a card:
 * `metadata_detection_disagreement`, 16 times out of 53 at Gate B, and `no_catalog_row`, which
 * box 2 left standing in the live queue — the case D35 and D37 were both written for. That is
 * two labels with evidence behind them and none at all for the other twelve. (`no_catalog_row`
 * ALSO fired 23 times at Gate B against a commons-only export and zero times against the full
 * one, which was a fact about that export rather than about the label; box 2's is not.) A label written for a code that fires weekly and one written
 * for a code that fires once a year are different pieces of copy, and after a real run the
 * only one this repo can tell apart is the first.
 */
export const REASON_LABELS: Readonly<Record<string, string>> = {
  // pipeline/variant.py — the ladder could not settle the finish.
  no_catalog_row: 'Not in the export',
  metadata_not_stocked: 'Toggle names a finish that is not stocked',
  metadata_detection_disagreement: 'Toggle and photo disagree',
  /* D23's stack claim contradicted the catalog: every candidate row's Rarity sits outside
   * what the operator claimed the stack holds. Deliberately NOT `metadata_*` — those three
   * are about the finish toggle, and a fourth reading as one at a glance is why the name
   * was rejected (D23 records it). */
  rarity_claim_mismatch: 'Claimed rarities match no row',
  detected_finish_not_stocked: 'Photo names a finish that is not stocked',
  ambiguous_no_signal: 'Nothing decided the finish',
  duplicate_condition: 'Two rows, one condition',

  // pipeline/routing.py — the answer exists but is not trusted enough to list.
  low_confidence: 'Low confidence read',
  no_position: 'No position recorded',
  identification_failed: 'Identification failed',
  set_ambiguous: 'Two sets share this number',
  card_not_detected: 'No card found in the photograph',
  /* D35. The one reason the JOIN writes over a successful ladder resolution — the row is
   * found and the entry offers it, and the card is queued anyway because the field that tells
   * one card from another is the field that could not be read. (Not the only reason sitting on
   * a resolved card: `low_confidence` and `no_market_data` do too, and they differ in reaching
   * `routing.route` still resolved, where this one arrives already un-resolved.) The label says what happened rather
   * than what failed, because nothing failed: a name was matched instead of a number. */
  number_unread_name_matched: 'Number unreadable, matched by name',
  /* Reachable on screen only if the route puts it in a queue. `cli/resolve.py:entries_for`
   * queues `routing.MAIN` and `routing.PARKED`, and `no_market_data` is neither — it is its
   * own destination, priced by hand in decisions.json. Kept because docs/DESIGN.md names
   * fourteen, and a map that quietly held thirteen would be the drift this comment is about. */
  no_market_data: 'No market price',
}

export function reasonLabel(reason: string): string {
  return REASON_LABELS[reason] ?? reason
}
