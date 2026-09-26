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

/* The FIFTEEN, transcribed from the two modules that emit them: six from
 * `pipeline/variant.py` (the D3 ladder's review reasons, including D23's
 * `rarity_claim_mismatch`) and NINE from `pipeline/routing.py` (v2 §5.4's routing reasons,
 * including D35's `number_unread_name_matched`, since 2026-09-11 `name_disputed`, and since
 * identity-follows-sku.md §7.3 (lane 2) `listing_disputed` — opened directly by `./pkmnscan
 * cards identity --write`, never by `routing.route()`, the same shape `no_market_data`
 * already carries in this tuple). It
 * read "fourteen, six and eight" until that lane landed, "thirteen, six and seven" before
 * that, and "twelve, six and six" until
 * 2026-08-25, having been written before either of those two landed, and "fourteen, seven and
 * seven" until 2026-09-02, when D3's amendment retired `metadata_detection_disagreement` —
 * see `RETIRED_REASON_LABELS` below for where that one went. docs/DESIGN.md requires each on
 * screen as a human label with the machine string small beneath it, because a friendly label
 * alone is a second vocabulary that nothing audits and a raw string alone is honest and
 * unreadable.
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
 * than closing it. TWO codes have now fired against a photograph of a card:
 * `metadata_detection_disagreement`, 16 times out of 53 at Gate B — and retired since, because
 * all 16 rulings went to the toggle — and `no_catalog_row`, which box 2 left standing in the
 * live queue — the case D35 and D37 were both written for. That is one live label with
 * evidence behind it and none at all for the other twelve. (`no_catalog_row`
 * ALSO fired 23 times at Gate B against a commons-only export and zero times against the full
 * one, which was a fact about that export rather than about the label; box 2's is not.) A label written for a code that fires weekly and one written
 * for a code that fires once a year are different pieces of copy, and after a real run the
 * only one this repo can tell apart is the first.
 */
export const REASON_LABELS: Readonly<Record<string, string>> = {
  // pipeline/variant.py — the ladder could not settle the finish.
  no_catalog_row: 'No listing on TCGplayer',
  metadata_not_stocked: 'Toggle names a finish that is not stocked',
  /* D23's stack claim contradicted the catalog: every candidate row's Rarity sits outside
   * what the operator claimed the stack holds. Deliberately NOT `metadata_*` — those three
   * are about the finish toggle, and a fourth reading as one at a glance is why the name
   * was rejected (D23 records it). */
  rarity_claim_mismatch: 'Claimed rarities match no listing',
  detected_finish_not_stocked: 'Photo names a finish that is not stocked',
  ambiguous_no_signal: 'Nothing decided the finish',
  duplicate_condition: 'Two listings, one condition',

  // pipeline/routing.py — the answer exists but is not trusted enough to list.
  low_confidence: 'Low confidence read',
  no_position: 'No position recorded',
  identification_failed: 'Identification failed',
  set_ambiguous: 'Two sets share this number',
  card_not_detected: 'No card found in the photograph',
  /* The mirror of D23's cross-check: the number found rows and the name read off the same
   * photograph matches none of them. Like D35's below, the JOIN writes it over a ladder
   * resolution that succeeded — the row is found, the entry offers it, and a human is asked
   * anyway because the two things read off one card disagree. */
  name_disputed: 'The read name matches no listing',

  /* D35. The one reason the JOIN writes over a successful ladder resolution — the row is
   * found and the entry offers it, and the card is queued anyway because the field that tells
   * one card from another is the field that could not be read. (Not the only reason sitting on
   * a resolved card: `low_confidence` and `no_market_data` do too, and they differ in reaching
   * `routing.route` still resolved, where this one arrives already un-resolved.) The label says what happened rather
   * than what failed, because nothing failed: a name was matched instead of a number. */
  number_unread_name_matched: 'Number unreadable, matched by name',
  /* Reachable on screen only if the route puts it in a queue. `cli/resolve.py:entries_for`
   * queues `routing.MAIN` and `routing.PARKED`, and `no_market_data` is neither — it is its
   * own destination, priced by hand on #/pricing. Kept because docs/DESIGN.md names
   * thirteen, and a map that quietly held twelve would be the drift this comment is about. */
  no_market_data: 'No market price',
  /* identity-follows-sku.md §7.3, lane 2. Opened directly by `./pkmnscan cards identity
   * --write` for a held, identified card — the read disputes the listing it is under, on
   * name or on number, and nobody has looked. `#/review`'s own headline for it is longer
   * ("Is the listing the right card?", `ReviewQueue.tsx`'s `QUESTIONS` map); this is the
   * short sub-label the shared `reasonLabel()` draws beside the machine string. */
  listing_disputed: 'The listing may be the wrong card',
}

/* CODES THE PIPELINE NO LONGER EMITS AND THE STORE STILL HOLDS. A separate map on purpose:
 * `make docs-audit`'s `reason codes` row reconciles `REASON_LABELS` against the two Python
 * modules, and a retired code left in that map would be reported as a label for a string the
 * pipeline cannot emit — which is exactly the finding it should be. But the owner's store
 * carries 16 `answered` events under `metadata_detection_disagreement`, and the history they
 * belong to renders the reason; the raw-string fallback would draw those as drift when they
 * are a record. So the label says "retired", with the date, and the audit does not read
 * this map.
 *
 * Read AFTER the live map and never before it, so a code that ever comes back is live again
 * by being put back above rather than by anybody remembering this list exists. */
export const RETIRED_REASON_LABELS: Readonly<Record<string, string>> = {
  /* D3, amended 2026-09-02: the photograph may no longer contradict a finish claim. Every one
   * of the 16 Gate B rulings under this code went to the toggle, which is what made it a
   * question not worth a person's attention rather than a question with no data. */
  metadata_detection_disagreement: 'Toggle and photo disagreed (retired 2026-09-02)',
}

/* Whether a reason is one the product has stopped asking about. `#/review` asks this before
 * it draws a question: a card queued before the retirement is still in the queue and still
 * has to be answered, but the sentence over it is the retirement rather than the question. */
export function isRetiredReason(reason: string): boolean {
  return RETIRED_REASON_LABELS[reason] !== undefined
}

export function reasonLabel(reason: string): string {
  return REASON_LABELS[reason] ?? RETIRED_REASON_LABELS[reason] ?? reason
}
