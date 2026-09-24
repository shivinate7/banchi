/* A DATE, SAID THE SAME WAY EVERYWHERE.
 *
 * EXTRACTED 2026-09-20, UX REVIEW FOLLOW-UP: `Revenue.tsx` padded its own "Last sold" column
 * (`5/2/2026` vs `12/13/2026` jittered the column's width) but `ProductHistory.tsx` was left
 * calling the identical bare `toLocaleDateString()` — the same defect, in a sibling file, that
 * a copy-instead-of-share always risks. `money.ts`'s own header states the reason this is a
 * separate file rather than a second copy: a second copy defeats the point of having one.
 *
 * TWO FORMATS AND NO MORE (UX review, 2026-09-23: the app drew seven). `relativeDate` is how
 * long ago something happened — `just now`, `5 minutes ago`, `yesterday`, `3 days ago` — and
 * past a week it hands over to `absoluteDate`, which is `Sep 9, 2026`: a short month, the day
 * with NO leading zero, and always the year. A screen picks one of the two. It never builds a
 * third. The full stamp a person may want on hover is `absoluteDate` too.
 *
 * `en-US` BY NAME, NOT THE RUNTIME'S LOCALE. The owner has one locale, and a formatter that
 * follows the machine made a spec true on one Mac only (see `playwright.config.ts`, which pins
 * the zone for the same reason). The ZONE still follows the runtime: a person sees their own
 * day. */

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR
const WEEK = 7 * DAY

const ABSOLUTE = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric' })

/** A stamp in any shape the wire sends it, as a `Date`, or null where it will not read. */
export function toDate(at: Date | string | number | null | undefined): Date | null {
  if (at === null || at === undefined) return null
  if (typeof at === 'string' && at.trim() === '') return null
  const when = at instanceof Date ? at : new Date(at)
  return Number.isNaN(when.getTime()) ? null : when
}

/** `Sep 9, 2026`, or `—` where there is no date. THE one absolute date format. */
export function absoluteDate(at: Date | string | number | null | undefined): string {
  const when = toDate(at)
  return when === null ? '—' : ABSOLUTE.format(when)
}

/** `just now`, `5 minutes ago`, `2 hours ago`, `yesterday`, `3 days ago`; a week or more, or a
 *  moment in the future, reads as `absoluteDate`. `—` where there is no date. THE one relative
 *  format. `now` is a parameter so a spec can pin it. */
export function relativeDate(at: Date | string | number | null | undefined, now: Date = new Date()): string {
  const when = toDate(at)
  if (when === null) return '—'
  const elapsed = now.getTime() - when.getTime()
  if (elapsed < -MINUTE || elapsed >= WEEK) return absoluteDate(when)
  if (elapsed < MINUTE) return 'just now'
  if (elapsed < HOUR) {
    const minutes = Math.floor(elapsed / MINUTE)
    return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
  }
  if (elapsed < DAY) {
    const hours = Math.floor(elapsed / HOUR)
    return `${hours} hour${hours === 1 ? '' : 's'} ago`
  }
  const days = Math.floor(elapsed / DAY)
  return days === 1 ? 'yesterday' : `${days} days ago`
}

/** THE OLD SALE-DATE SHAPE, `Sep 09, 2026`, kept only so `Revenue.tsx` and `ProductHistory.tsx`
 *  draw what they drew until their own lanes move them to `absoluteDate`. Do not call it from
 *  new code: the zero-padded day is one of the seven formats the review counted.
 *
 *  BOTH month and day are asked for explicitly, `2-digit`, so `Sep 09, 2026` and `Sep 13, 2026`
 *  take the same width — the month-only padding a first pass left in place still let the day
 *  jitter by one character. A column that moves to `absoluteDate` loses that fixed width, and
 *  its lane decides how the column aligns. */
export function saleDate(d: Date): string {
  return d.toLocaleDateString(undefined, { month: 'short', day: '2-digit', year: 'numeric' })
}
