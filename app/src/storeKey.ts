/* app/src/storeKey.ts
 *
 * ONE SPELLING OF A RECORD'S STORE KEY FOR EVERY SCREEN THAT DRAWS ONE, AND THE ONE READER OF
 * IT (D68, D92). There were two composers when D92's sweep went looking: `BoxBrowse.rowSlot`
 * for a departed row in the walk, and the capture screen's undo filmstrip for a record this
 * session never saw a capture response for — written independently, from the same two fields,
 * and one respelling away from disagreeing. This is `cardNumber.ts`'s lesson (D67) applied to
 * the other number a card carries, and it is deliberately a separate file from that one:
 * `join.departed_label`'s own docstring records the owner reading `3/96` as a collector number,
 * which is exactly what a module holding both would invite a reader to do.
 *
 * IT IS ITS OWN MODULE RATHER THAN AN EXPORT OF `PositionLabel.tsx`, WHICH IS WHERE IT FIRST
 * WENT. That file imports `PositionLabel.css`, so a screen reaching it for a string takes an
 * edge to a stylesheet it does not otherwise want and moves that sheet in the bundle's order —
 * `BoxBrowse.tsx` had no such edge before and does not need one now. This is why every
 * vocabulary on this side of the wire is a file of its own: `reasons.ts`, `holds.ts`,
 * `orderReasons.ts`, `cardNumber.ts`, and now this.
 *
 * THE PYTHON IS THE AUTHORITY AND THIS IS ITS READER AND ITS WRITER, kept in one file so a
 * respelling there lands on two adjacent lines rather than on however many screens had reached
 * for a template literal of their own.
 */

/* THE STORE KEY A LABEL MAY END ON — the `/inventory/<box>/<index>` path (D68), in the two
   spellings the two composers use. `B3 #96` is `join.departed_label`'s and `5/12` is
   `join.place_text`'s pooled one; that entry's amendment has why they differ, and the short of it
   is that a departed label is drawn beside printed card numbers and `3/96` was read as one.
   Neither shape is `<word> <number>`, which is what every part of a position label is — `Box 3`,
   `Section 1`, `Card 17` — and what `PositionLabel`'s seam is built on, so neither can be
   mistaken for a part. Anchored both ends: unanchored, the slash form would match a collector
   number that wandered in (`198/219`), which is why nothing composes one into a label and why
   this only ever reads the LAST part of a string the server built. A respelling in the Python
   that does not land here draws the key as a position part instead of failing, so the two
   move together. */
export const STORE_KEY = /^(?:B\d+ #\d+|\d+\/\d+)$/

/** `join.departed_label`'s store key, in the server's own spelling — `B3 #96`.
 *
 *  THE `#` HERE IS A KEY AND NOT A COUNT, AND THAT IS THE EXEMPTION D92 ALLOWS RATHER THAN A
 *  HOLE IN IT. Every other bare `#` in this product is D58's countable slot — the number a hand
 *  counts to, which moves as cards leave the box in front of it. A record drawn through this one
 *  has no slot to count to: it has left the box, or the session holds only the index the server
 *  addressed it by. There is no figure to draw instead, and the `B<box>` in front is the one
 *  shape no count on these screens carries. */
export function storeKeyText(box: number, index: number): string {
  // sigil-ok: the server's own spelling of a store key, for a record that is in no slot to count
  return `B${box} #${index}`
}
