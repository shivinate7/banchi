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
 * identity-follows-sku.md §7.3 (lane 2) `listing_disputed` — opened directly by `./banchi
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
 * this repo compares the two — the same gap `docs/debts/` records for `tokens.css` against
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
  /* identity-follows-sku.md §7.3, lane 2. Opened directly by `./banchi cards identity
   * --write` for a held, identified card — the read disputes the listing it is under, on
   * name or on number, and nobody has looked. `#/review`'s own headline for it is longer
   * ("Is the listing the right card?", `ReviewQueue.tsx`'s `QUESTIONS` map); this is the
   * short sub-label the shared `reasonLabel()` draws beside the machine string. */
  listing_disputed: 'The listing may be the wrong card',
  /* `pipeline/routing.py:FREE_READER_DISAGREES`, opened by `./banchi match audit --write`. */
  free_reader_disagrees: 'The free reader sees another card',
  /* `pipeline/routing.py:READERS_DISAGREE` and `SECOND_LOOK_UNSURE`: a card the free reader
   * refused, held after the paid second look. */
  readers_disagree: 'The two readers name different cards',
  second_look_unsure: 'The second look is not sure',
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

/* THE FREE READER'S UNREAD CODES, IN PLAIN WORDS (`docs/specs/identify-engine-pick.md`, 10.3), for the Review band's
 * paid-look sheet. A code is one group; codes that read alike share a title, so they share a group. `fix` is the one free
 * way out, said once under the group's title as a sentence and never a control (the row's own press goes to the card).
 * `note` is an explanation where no free fix exists, only for the look-alike group. Every other group with no free fix shows
 * no line. An unknown code groups under "Another reason" (`unreadGroup`), never a blank and never the raw code. No title or hover shows a code. Every `UNREAD_*` code `identify.match` can emit is a key here (`harness/tests/t7/engine_sweep.py`). */
export type UnreadGroup = { readonly title: string; readonly fix: string | null; readonly note?: string }

const RARITY_FIX = 'Name the rarity on the card. A claim settles the printing.'
const SET_FIX = 'Name the set on the card. A narrower set gives a better match.'
const PHOTO_FIX = 'Shoot the card again.'
const SET_NOT_READ: UnreadGroup = { title: 'The set cannot be read free', fix: null }

export const UNREAD_GROUPS: Readonly<Record<string, UnreadGroup>> = {
  'margin_too_small': { title: 'Two printings too close to call', fix: RARITY_FIX },
  'match_too_weak': { title: 'A weak match', fix: SET_FIX },
  'lookalike_guard': { title: 'A look-alike with no photo of its own', fix: null, note: 'Only a paid look can tell these apart.' },
  'photo_unreadable': { title: 'A photo problem', fix: PHOTO_FIX },
  'no_card_found': { title: 'A photo problem', fix: PHOTO_FIX },
  'set_not_resolved': { title: 'The set named matches no set, or more than one', fix: 'Correct the set.' },
  'promo_set': SET_NOT_READ,
  'promo_held': SET_NOT_READ,
  'set_not_indexed': SET_NOT_READ,
  'no_index': SET_NOT_READ,
  'game_not_served': { title: 'This game is not read free', fix: null },
  'index_stale': { title: "The free reader's data is out of date", fix: 'Prepare matching on the runs sheet.' },
}

/* A card whose mark predates stored reasons: the free reader reads it again and fills the reason in. */
export const NO_REASON: UnreadGroup = { title: 'No reason kept', fix: 'A free read will fill it in.' }

/* A code this file has no words for: one group, never the raw code on screen. */
export const OTHER_REASON: UnreadGroup = { title: 'Another reason', fix: null }

export const NO_REASON_OFF = 'Turn on the reader to fill it in.'

export function unreadGroup(code: string | null): UnreadGroup {
  if (code === null || code === '') return NO_REASON
  return UNREAD_GROUPS[code] ?? OTHER_REASON
}
