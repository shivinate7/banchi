/* THE WITHHOLD VOCABULARY, DECLARED ONCE ON THIS SIDE OF THE WIRE (D49).
 *
 * `app/src/reasons.ts` is the precedent and its argument transfers exactly: the pipeline
 * authors a closed set of machine strings, a screen has to offer them, and the only honest
 * way to have them in two languages is to make the drift VISIBLE rather than to hope. So
 * this file is the single TypeScript declaration, and `scripts/docs-audit.py` reconciles it
 * against `pipeline/decisions.py:WITHHOLD_REASONS` — blocking, because a mismatch is
 * provably wrong rather than a question of judgement.
 *
 * WHY THE SCREEN NEEDS THEM AT ALL, given that `PUT /pipeline/runs/<name>/decisions` writes
 * the document with no validation: because that is exactly why. The route says in its own
 * comment that it does not validate, `cli/cmd_emit.py` and `cli/cmd_join.py` both record in
 * code that this lets a screen put a run into a state where a command answers with a
 * refusal — so the defence is that the screen BUILDS the document from typed state and
 * cannot construct a shape its own code does not know. A free-text reason field would hand
 * that guarantee back.
 *
 * THE WORDS ARE DELIBERATELY DISJOINT from `master.RETIRE_REASONS` (the card left inventory)
 * and `queues.STAND_DOWN_REASONS` (the question was closed). No word appears in two of the
 * three, and `next_batch` is spelled that way rather than the obvious `not_yet` because
 * `not_listing` is already a stand-down reason and the two read as one word at the 10px a
 * machine string is drawn at.
 */

export const WITHHOLD_REASONS = ['bullish', 'keeping', 'next_batch'] as const

export type WithholdReason = (typeof WITHHOLD_REASONS)[number]

/** The human label beside each machine string.
 *
 *  BOTH ARE DRAWN, NEVER ONE. `docs/DESIGN.md`'s rule for the owner's screens is the human
 *  label large and the machine string small beneath it — showing only the friendly word
 *  creates a second vocabulary nothing audits, and showing only the raw string is honest and
 *  unreadable. One line of chrome buys a word you can grep from the screen to `decisions.json`
 *  to the run report. */
export const WITHHOLD_LABELS: Record<WithholdReason, string> = {
  bullish: 'Bullish — waiting for the price to move',
  keeping: 'Keeping this one',
  next_batch: 'Listing it in a later batch',
}

/** The keys the hold panel answers on.
 *
 *  LETTERS AND NOT DIGITS, and the reason is specific to this screen rather than borrowed
 *  from `#/review`'s panel. The digits here are price entry: a digit pressed inside a panel
 *  raised from a focused price field is unresolvable, because it is a plausible character in
 *  the thing the operator was just typing. `b`, `k` and `x` are free on this screen and are
 *  the initials of the words they choose, except `x` — `next_batch` has no free initial. */
export const WITHHOLD_KEYS: Record<WithholdReason, string> = {
  bullish: 'b',
  keeping: 'k',
  next_batch: 'x',
}
