/* A SALE DATE, SAID THE SAME WAY EVERYWHERE.
 *
 * EXTRACTED 2026-09-20, UX REVIEW FOLLOW-UP: `Revenue.tsx` padded its own "Last sold" column
 * (`5/2/2026` vs `12/13/2026` jittered the column's width) but `ProductHistory.tsx` was left
 * calling the identical bare `toLocaleDateString()` — the same defect, in a sibling file, that
 * a copy-instead-of-share always risks. `money.ts`'s own header states the reason this is a
 * separate file rather than a second copy: a second copy defeats the point of having one.
 *
 * BOTH month and day are asked for explicitly, `2-digit`, so `Sep 09, 2026` and `Sep 13, 2026`
 * take the same width — the month-only padding a first pass left in place still let the day
 * jitter by one character. */
export function saleDate(d: Date): string {
  return d.toLocaleDateString(undefined, { month: 'short', day: '2-digit', year: 'numeric' })
}
