/* THE ORDER-LINE VOCABULARY, DECLARED ONCE ON THIS SIDE OF THE WIRE.
 *
 * `pipeline/orders.py:LINE_REASONS` enumerates six machine strings and says in its own
 * comment why an empty result gets six words and not one: "we found nothing" has several
 * causes with different remedies, and a screen that cannot tell them apart sends the owner
 * to the wrong one every time. This file is the TypeScript half of that vocabulary, so a
 * screen LOOKS A REASON UP rather than re-deriving it from whatever the line happens to
 * carry beside it.
 *
 * WHY THIS IS ITS OWN FILE AND NOT AN ADDITION TO `app/src/reasons.ts`, which is where a
 * reader would look first. `scripts/docs-audit.py:check_reason_codes` reconciles
 * `REASON_LABELS` against exactly two modules — `pipeline/variant.py` and
 * `pipeline/routing.py` — and `pipeline/orders.py` is neither. Six strings added to that
 * map would fail that check as codes the pipeline does not emit, which is a true statement
 * about the two modules it reads and a false one about this repo. The precedent to copy is
 * `app/src/holds.ts`: a closed vocabulary in its own file, reconciled by its own check
 * against its own module.
 *
 * WHAT KEEPS IT HONEST IS TWO CHECKS, and neither one covers the other's half:
 *
 *  - The compiler, WITHIN THIS APP. `ORDER_REASONS` carries `satisfies readonly
 *    OrderLineReason[]`, so a string in the array that is not in the union is a build
 *    error, and the two records are annotated `Record<OrderLineReason, string>`, which the
 *    compiler refuses unless every member of the union has an entry and nothing else does.
 *    Between them the array cannot say a word the union does not and the records cannot
 *    miss one.
 *  - `scripts/docs-audit.py`, ACROSS THE WIRE, reconciling `ORDER_REASONS` against
 *    `pipeline/orders.py:LINE_REASONS` in both directions. That is the half the compiler
 *    cannot do at all: TypeScript cannot import a Python tuple, so a reason the pipeline
 *    gains and this file does not is invisible here until something compares the two files
 *    as text. This is why the array exists beside the records rather than the records
 *    standing alone — a `Record`'s keys are a type, and a text check needs a list.
 *
 * THE LOOKUPS TAKE A `string`, NOT THE UNION, and that is the contract rather than a guard.
 * A code the pipeline has and this file has not renders as ITSELF — the same `?? reason`
 * fallback `reasons.ts` argues for — so drift arrives on screen as a machine string rather
 * than as a blank row.
 */

import type { OrderLineReason } from './types'

/** The six reasons `pipeline/orders.py:LINE_REASONS` enumerates, in that module's own
 *  order — resolved first, then the five ways a line comes up short — because a screen
 *  listing them (a filter, a legend) should read in the order the resolver's docstring
 *  argues them. */
export const ORDER_REASONS = [
  'resolved',
  'short',
  'no_copies_on_hand',
  'sku_unknown',
  'sku_unseen',
  'not_a_single',
] as const satisfies readonly OrderLineReason[]

/** The array's own element type — the six words as the compiler sees them, which is what
 *  `isOrderReason` narrows to. It is deliberately NOT re-exported as the app's reason type:
 *  `OrderLineReason` in `app/src/types.ts` is that, and this one exists so a narrowing
 *  written here cannot quietly widen if the array and the union ever disagree. */
type ListedOrderReason = (typeof ORDER_REASONS)[number]

/** The human label beside each machine string.
 *
 *  BOTH ARE DRAWN, NEVER ONE — `docs/DESIGN.md`'s rule for the owner's screens, and the
 *  same one `holds.ts` and `reasons.ts` follow: the human label large, the machine string
 *  small beneath it. A friendly word alone is a second vocabulary nothing audits; the raw
 *  string alone is honest and unreadable. `sku_unknown` and `sku_unseen` are the pair that
 *  pays for this rule: they are one letter apart as machine strings and are two completely
 *  different situations, and only the labels tell them apart at a glance. */
export const ORDER_REASON_LABELS: Record<OrderLineReason, string> = {
  resolved: 'Every copy found',
  short: 'Fewer copies on hand than the order wants',
  no_copies_on_hand: 'Every copy has left the boxes',
  sku_unknown: 'A run priced this card and no record carries the SKU',
  sku_unseen: 'Nothing in the store has ever seen this SKU',
  not_a_single: 'Not a single — the boxes do not hold it',
}

/** All six get a remedy because an empty result has several causes with different repairs,
 *  and one blank row for all of them throws away the resolver's best work.
 *
 *  `resolved` is the empty string rather than a cheerful sentence: there is nothing to do
 *  about a line that worked, and a remedy slot that always has words in it is a slot a
 *  reader stops reading. The screen draws the row only where the string is non-empty.
 *
 *  `sku_unseen`'s remedy is the long one on purpose. It is the reason most likely to look
 *  like a defect and least likely to be one: a card below D9's $0.40 threshold was never
 *  listed, so it cannot have been ordered, so a line naming it is a SKU that came from
 *  somewhere else. Saying "and is correct" in the remedy is what stops the next session
 *  going looking through boxes for it. */
export const ORDER_REASON_REMEDY: Record<OrderLineReason, string> = {
  resolved: '',
  short: 'Pull what is here; the rest is a shortfall to answer to the buyer.',
  no_copies_on_hand: 'Sold, retired or pooled — the counts beside this line say which.',
  sku_unknown: 'Look at what happened to the box, not at the order.',
  sku_unseen:
    'Check the SKU against the order. A card that was never listed cannot be ordered, ' +
    'so a sub-threshold box is the usual answer and is correct.',
  not_a_single: 'Sealed or an accessory. It ships in a parcel and is picked by hand.',
}

/** Whether a string off the wire is one of the six.
 *
 *  This is the one runtime reader of `ORDER_REASONS`, and it is why the array exists at
 *  all rather than the two records standing alone: a membership test needs the words in a
 *  form that survives to run time, and a `Record`'s keys are erased. */
export function isOrderReason(value: string): value is ListedOrderReason {
  return (ORDER_REASONS as readonly string[]).includes(value)
}

/** The label for a reason, or the reason itself where this file has no label for it.
 *
 *  THE `?? reason` FALLBACK IS THE CONTRACT, NOT A GUARD, and it is lifted from
 *  `reasons.ts:reasonLabel` for the same argument: a code the pipeline has and this file
 *  has not renders as ITSELF, so drift arrives on screen as a machine string rather than
 *  as a blank row. It is also what `noUncheckedIndexedAccess` wants from any lookup whose
 *  key is a narrowed `string`, so one expression answers both. */
export function orderReasonLabel(reason: string): string {
  return isOrderReason(reason) ? ORDER_REASON_LABELS[reason] ?? reason : reason
}

/** The remedy for a reason, or the empty string where there is none to offer — both for
 *  `resolved`, which needs no repair, and for a code this file has not heard of, where
 *  inventing a remedy would be guessing at a situation nothing here understands. The screen
 *  draws the remedy row only where this is non-empty, so the two cases render alike. */
export function orderReasonRemedy(reason: string): string {
  return isOrderReason(reason) ? ORDER_REASON_REMEDY[reason] ?? '' : ''
}
