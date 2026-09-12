/* THE ORDER IS TAKEN ONCE AND HELD UNTIL SOMEBODY ASKS FOR A NEW ONE.
 *
 * `#/inventory` ranks under a search: the copies list leads with the section holding the most
 * live copies of the answer, the box rail leads with the box whose best section holds the most,
 * and the walk lands in that section (D132, amended on the owner's rule of 2026-09-11). All
 * three read the copies' CURRENT state, so a sale changes the arithmetic and every one of them
 * re-ranks on the press — under the hand of somebody marking a run of copies sold.
 *
 * The owner's report: "i search a card it's ranked by the most of the card in a certain
 * section, this is awesome and i love it but i realized if i mark sold while on that sorta view
 * it can reorganize the rankings right in front of me, which feels unintuitive if im trying to
 * mark multiple as sold."
 *
 * D28 SETTLED THIS SHAPE ON THE OTHER SCREEN — "the review answer gets an undo window, and the
 * list stops moving under it". This is that ruling on `#/inventory`, and the mechanism is
 * deliberately the same one rather than a parallel invention: the thing that would move is held
 * still until the operator is done with it.
 *
 * WHAT IS FROZEN IS A FACT ABOUT THE COPIES AND NOT A LIST OF POSITIONS. The obvious build is
 * to snapshot the rendered order as an array of keys and re-apply it; that array is a fourth
 * copy of an ordering three call sites already compute, and the day one of them gains a term
 * the snapshot silently disagrees with it. What is snapshotted instead is the only INPUT that
 * moves under a press: which copies counted as live when the order was taken. Every ranking
 * goes on computing itself, from the state the order was ranked against.
 *
 * SO THE SET HOLDS THE DEPARTURES, NOT THE SURVIVORS. A copy captured after the order was taken
 * is new evidence and no key of it is held, which is correct — nothing was ranked around it. A
 * copy that LEFT since the order was taken is held, and every reader below treats it as it was:
 * still counting for its section, still drawn where it was, still shown with `Hide sold` on.
 *
 * THAT LAST CLAUSE IS LOAD-BEARING AND IS D132's OTHER DOOR (see `ranksAsShown`). Freezing the
 * arithmetic while letting the fold delete the row puts the jump straight back: the row vanishes
 * and everything under it comes up one. A frozen departure stays in place and is struck, which
 * is the only one of D132's two behaviours that moves nothing — sinking it under the live rows
 * is itself the movement this exists to stop.
 */

/** The copies that have left since the order on screen was taken, by store key (`"3/17"`).
 *
 *  EMPTY MEANS THE ORDER IS CURRENT, which is both the opening state and what the re-rank press
 *  restores — so `size` is the staleness figure a screen draws, with no second counter to keep
 *  in step with it. */
export type FrozenRank = ReadonlySet<string>

/** No departures held: rank everything by what the store says now. */
export const RANK_IS_CURRENT: FrozenRank = new Set<string>()

/** Does this copy still count toward the order it was ranked into?
 *
 *  The one predicate every ranking under a query asks, so the copies list, the box rail and the
 *  walk's landing cannot drift apart on it. `departed` is the caller's own reading of the copy —
 *  `isDeparted`/`hasDeparted` on the wire shape it happens to hold — because the two surfaces
 *  carry two different row types over the same keys. */
export function ranksAsLive(key: string, departed: boolean, frozen: FrozenRank): boolean {
  return !departed || frozen.has(key)
}

/** Is this copy still drawn, with the departed rows folded away (D132)?
 *
 *  Same answer, named separately because it is a different question with a different reason: the
 *  first keeps a row's WEIGHT in the arithmetic, this keeps its PLACE on the screen. A build that
 *  answered one and not the other would still move the list. */
export function ranksAsShown(key: string, departed: boolean, frozen: FrozenRank): boolean {
  return !departed || frozen.has(key)
}

/** The sentence the control says, or null while the order is current.
 *
 *  TAKES THE COUNT AND NOT THE SET, because the two readers count different things out of one
 *  set: the box rail is stale by every departure the screen has recorded, and a copies list is
 *  stale only by the ones it is drawing — `3 copies stale` over a list holding one of them
 *  would be counting somebody else's cards.
 *
 *  `COPIES` AND NOT `SALES`, WHICH IS ONE WORD OFF THE OWNER'S OWN PHRASING AND IS DELIBERATE.
 *  They wrote "N sales stale", and a sale is what they will nearly always have pressed — but
 *  D26's other door counts here too: a RETIREMENT takes a copy out of the boxes, changes the
 *  same arithmetic, and is held by the same set. This screen does not record which door a hold
 *  came through, and inventing that distinction to keep one word would be a field carried
 *  through three components for a label. `copy` is the product's own word for these rows
 *  everywhere else on the panel — `Every copy of this card`, `5 in the boxes`.
 *
 *  Said as a fact and not as a warning: nothing is wrong, the operator has simply moved cards
 *  since the ranking was computed and may or may not want it recomputed. */
export function stalenessSentence(copies: number): string | null {
  if (copies <= 0) return null
  return `Order is ${copies} ${copies === 1 ? 'copy' : 'copies'} stale`
}
