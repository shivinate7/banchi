/**
 * The two drawing helpers the row trend (`PriceTrend.tsx`), the product view and Sales share:
 * the range captions and the spark geometry. The pricing drawer that used to live here folded
 * into the one product view (D278, D277), so only these remain.
 */

/** How a range is captioned. The endpoint's own range names are drawn beside these, small. */
export const RANGE_LABEL: Record<string, string> = {
  month: 'Daily',
  quarter: '3-day',
  semiannual: 'Weekly',
  annual: 'Weekly',
}

/** A series of prices as polyline point-lists, oldest on the left. `null` where a bucket
 *  carries no price at all; the line BREAKS there rather than interpolating across it.
 *  Shared with `PriceTrend.tsx` so the panel and the row cannot disagree on the geometry. */
export function sparkSegments(
  priced: (number | null)[],
  W: number,
  H: number,
): Point[][] | null {
  const known = priced.filter((v): v is number => v !== null && Number.isFinite(v))
  if (known.length < 2) return null
  const lo = Math.min(...known)
  const hi = Math.max(...known)
  const span = hi - lo || 1
  const step = priced.length > 1 ? W / (priced.length - 1) : W
  /* POINTS, NOT STRINGS. A segment used to be an array of `"x,y"` and the renderer read a
     point's x back out of it with `split(',')` — which is the shape `app/eslint.config.js`
     bans on sight, for a good reason that happens not to apply here and a rule that cannot
     tell. Carrying the pair and formatting once at the edge is better anyway: the renderer
     stops parsing something this function just built. */
  const segments: Point[][] = []
  let current: Point[] = []
  priced.forEach((value, at) => {
    if (value === null || !Number.isFinite(value)) {
      if (current.length > 1) segments.push(current)
      current = []
      return
    }
    current.push([at * step, H - ((value - lo) / span) * (H - 4) - 2])
  })
  if (current.length > 1) segments.push(current)
  return segments.length ? segments : null
}

/** One plotted point, in the viewBox's own units. */
type Point = readonly [number, number]
