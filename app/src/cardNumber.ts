/* app/src/cardNumber.ts
 *
 * ONE COMPOSER OF THE COLLECTOR NUMBER FOR EVERY SCREEN THAT DRAWS ONE (D67). There were
 * three, one per screen, written from the same two fields and no two of them the same:
 * `ReviewQueue.tsx` folded blanks on both halves, `CardLocations.tsx` folded them on `number`
 * and tested `printed_total === null` on the line below, and `BoxBrowse.tsx` tested null on
 * both. The middle spelling is the one that cost something — the store writes `""` into
 * `printed_total` on 174 of its 676 numbered records, so a quarter of the store rendered
 * `198/219/`, a separator with nothing behind it.
 *
 * THE FOLD THAT REMOVES A GLUED SET CODE IS NOT HERE, AND THAT IS DELIBERATE. D55's shape rule
 * — two to five letters, no digits, then one separator — is `pipeline/join.py:strip_set_code`,
 * measured against 2,607 real export cells, and a TypeScript copy of it would be that rule
 * living in two dialects. `number_index_key`'s own docstring is the worked example of what that
 * costs: two spellings of one fold, agreeing until they did not, and a silent zero-join. So the
 * server folds and sends `number_display`, and this module PREFERS it.
 *
 * WHICH MAKES THIS THE FALLBACK AND THE FALLBACK IS STILL LOAD-BEARING. `number_display` is
 * optional on the wire — the contract every server decoration takes in `types.ts` — so a screen
 * held against a server that predates it still draws a number, and still draws it without the
 * trailing separator. The two repairs are independent on purpose: one is a client bug and one
 * is a server field.
 */

/** A field that is present, non-null and not blank, or null. The three-way test the two broken
 *  copies applied to one half and not the other. */
function text(field: string | null | undefined): string | null {
  const value = typeof field === 'string' ? field.trim() : ''
  return value === '' ? null : value
}

/** What a screen draws where a collector number goes, or null when the card has none.
 *
 *  NULL RATHER THAN A PLACEHOLDER, matching `pipeline/join.py:display_number`, which is the
 *  server-side twin of this function and the authority on the string when it sends one. A fact
 *  row wants the word `none` and a list wants nothing at all; a formatter that chose would put
 *  one of those into a cell that wanted the other.
 *
 *  NO `zfill`, ever. `pipeline/join.py:join_key` pads to three digits to match the export's
 *  `Number` column; padding here would put a string on screen that nothing in the run said. */
export function collectorNumber(read: {
  number?: string | null
  printed_total?: string | null
  /** The server's own composition (D67) — folded, and agreed across a group's copies where the
   *  caller is a group. Absent from `QueueRead` by design: the review queue is judging the read
   *  itself, so it composes the raw fields below and shows what the model actually returned. */
  number_display?: string | null
}): string | null {
  const sent = text(read.number_display)
  if (sent !== null) return sent

  const number = text(read.number)
  if (number === null) return null
  const total = text(read.printed_total)
  return total === null ? number : `${number}/${total}`
}
