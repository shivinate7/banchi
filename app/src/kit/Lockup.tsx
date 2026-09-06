import { useId } from 'react'

import {
  BLOCK, BRACKET_ARM, BRACKET_CAPS, BRACKET_SPIN, KANJI_PATH, PARAMS, ROMAN_PATH,
} from './lockupGeometry'
import { MARKS } from './markPalettes'

/* THE LOCKUP — 番地 over BANCHI inside the mark's own brackets.
 *
 * Nothing here is drawn. Every path comes from `lockupGeometry.ts`, which
 * `scripts/build-lockup.mjs` generates by reading docs/specs/logo.md section 13's settled table
 * and running `sheets/lockup-core.js` in a browser. To change the lockup: change section 13,
 * re-run the script. That is D102's rule for the mark, applied to its expanded form.
 *
 * ONE GEOMETRY, EVERY SIZE. The paths are drawn in a 319 x 233 box at kanji 100 and the viewBox
 * scales them. That is not only smaller than per-size data, it is more correct: a vector scaled by
 * a viewBox cannot re-layout, so the roman cannot reflow between the sidebar's 40 and the
 * gallery's larger draws. Live text could, and did — the width match had to be SOLVED per size.
 *
 * THE ACCESSIBILITY CONTRACT IS THE OPPOSITE OF `Logo`'s, AND THEN INVERTS AGAIN INSIDE A LINK.
 * `Logo` is `aria-hidden` always, because every call site names its own wrapper. The lockup IS
 * the word "Banchi" — standing alone at #/gallery it must carry `role="img"` and a name. But
 * inside the sidebar's `<a aria-label="Banchi home">` a named child would announce "Banchi Banchi
 * home", so that one call site passes `decorative`. Section 15 named only the first half of this.
 *
 * THREE CLASS HOOKS, ON PURPOSE. `.bn-lockup-bracket`, `.bn-lockup-kanji` and `.bn-lockup-roman`
 * exist so the shell can choreograph the collapse — the roman leaves first, then the kanji and the
 * frame. Without them the lockup could only fade as one lump.
 *
 * THE DARK BRACKET IS SWITCHED IN CSS, NOT HERE. Section 16 settles it as `bluesteel`'s own
 * four-stop chrome, so the lockup and the rail mark are one object in one metal. The gradient's id
 * is per-instance, which a stylesheet cannot name — so the instance publishes it as
 * `--bn-lockup-metal` and App.css decides, per theme, whether to use it or flat ink. */
export function Lockup({
  size = 40,
  className,
  decorative = false,
}: {
  readonly size?: number
  readonly className?: string
  /** Inside a wrapper that already carries the name — the sidebar's brand link. */
  readonly decorative?: boolean
}) {
  // Per instance: the sidebar and #/gallery can be mounted at once, and two lockups sharing
  // `url(#m)` is silent — both references resolve, to the first one's gradient. Same argument
  // `Logo` makes, and the same fix.
  const id = useId().replace(/:/g, '')
  const metal = MARKS.bluesteel.bracket

  const arm = (
    <>
      <path d={BRACKET_ARM} />
      {BRACKET_CAPS.map(([cx, cy, r]) => <circle key={`${cx},${cy}`} cx={cx} cy={cy} r={r} />)}
    </>
  )

  return (
    <svg
      className={className ? `bn-lockup ${className}` : 'bn-lockup'}
      width={(size * BLOCK.w) / BLOCK.ref}
      height={(size * BLOCK.h) / BLOCK.ref}
      viewBox={`0 0 ${BLOCK.w} ${BLOCK.h}`}
      style={{
        // read by App.css, which chooses between this and flat ink per theme
        ['--bn-lockup-metal' as string]: `url(#${id}m)`,
        // NEVER the literal 0.45 in a stylesheet. Section 13 settled it and its own history is
        // that a value typed a second time is how that sheet's captions went wrong, twice.
        ['--bn-lockup-roman-opacity' as string]: String(PARAMS.romanOpacity),
      }}
      {...(decorative ? { 'aria-hidden': true } : { role: 'img', 'aria-label': 'Banchi' })}
    >
      <defs>
        <linearGradient id={`${id}m`} x1=".75" y1=".067" x2=".25" y2=".933">
          {metal.map((c, i) => (
            <stop key={c + i} offset={[0, 0.33, 0.67, 1][i]} stopColor={c} />
          ))}
        </linearGradient>
      </defs>
      {/* the frame: one arm and its 180-degree twin, both taking their fill by inheritance */}
      <g className="bn-lockup-bracket">
        {arm}
        <g transform={BRACKET_SPIN}>{arm}</g>
      </g>
      <path className="bn-lockup-kanji" d={KANJI_PATH} />
      <path className="bn-lockup-roman" d={ROMAN_PATH} />
    </svg>
  )
}
