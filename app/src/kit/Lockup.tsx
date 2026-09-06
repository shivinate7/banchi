import { useEffect, useId, useRef } from 'react'

import {
  BLOCK, BRACKET_ARM, BRACKET_CAPS, BRACKET_SPIN, KANJI_PATH, PARAMS, RAIL_ARM, RAIL_CAPS,
  ROMAN_PATH,
} from './lockupGeometry'
import { MARKS } from './markPalettes'

/* THE LOCKUP — 番地 over BANCHI inside the mark's own brackets, and the empty slot it collapses to.
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
 * THE ACCESSIBILITY CONTRACT IS THE OPPOSITE OF `Logo`'s, AND THEN INVERTS AGAIN INSIDE THE BRAND.
 * `Logo` is `aria-hidden` always, because every call site names its own wrapper. The lockup IS the
 * word "Banchi" — standing alone at #/gallery it must carry `role="img"` and a name. But the
 * sidebar's brand carries its own label ("Collapse the sidebar" on the button that is the rail
 * control, "Banchi home" on the anchor at the tablet breakpoint), and a named child would announce
 * the name over it. So that call site passes `decorative`. Section 15 named only the first half.
 *
 * THE DARK BRACKET IS SWITCHED IN CSS, NOT HERE. Section 16 settles it as `bluesteel`'s own
 * four-stop chrome, so the lockup and the rail are one object in one metal. The gradient's id is
 * per-instance, which a stylesheet cannot name — so the instance publishes it as
 * `--bn-lockup-metal` and `kit.css` decides, per theme.
 *
 * ---------------------------------------------------------------------------------------------
 * THE COLLAPSE IS A MORPH, AND SECTION 16 SAID IT COULD NOT BE.
 *
 * That section recorded: "a ~600-point filled taper against a 52-byte stroked wire — paths that
 * shape cannot interpolate", and shipped two drawings crossfading past each other instead. The
 * claim is true of how the two are EXPRESSED and false of what they are. Both are one L: a
 * vertical leg, a rounded elbow, a horizontal leg. `taperParts` is that L parametrically at a
 * fixed 301 samples, and the mark's small cut is the SAME CALL with `tip = 1` — section 11 removed
 * the taper and changed nothing else. So the generator emits both ends at identical topology and a
 * point-wise lerp is exact.
 *
 * NOTHING ABOUT WHAT THE RAIL DRAWS CHANGED. `RAIL_ARM` is rendered against markGeometry.ts's
 * shipped stroked wire at build time and the build is refused if they differ; measured, 0.30% of
 * inked pixels at 10x, which is the antialiased boundary. The rail is still the mark's own wire
 * (D102), reached by a path that can be interpolated rather than by a second component.
 *
 * THE CLOCK IS THE BOX, WHICH IS WHY THERE IS NO EASING FUNCTION HERE. The morph reads the slot's
 * own animating width and derives its progress from it, so it cannot drift from the panel it sits
 * in, it needs no copy of `--bn-ease`, and retuning that token retunes this. `prefers-reduced-
 * motion` is honoured for free: `base.css` crushes the width transition, the width jumps, and the
 * morph lands in the same frame. No `matchMedia`, no second code path.
 */

const CAPS = BRACKET_CAPS.length

/** `M x y L x y … Z` on both ends, same command count, so the numbers align 1:1. */
const nums = (d: string): number[] => (d.match(/-?\d+\.?\d*/g) ?? []).map(Number)

const OPEN_D = nums(BRACKET_ARM)
const RAIL_D = nums(RAIL_ARM)

/** Rebuild the path from a number array. The command letters never vary — that is what having
 *  one sampler emit both ends buys, and what a `d` transition would have required anyway. */
function draw(n: number[]): string {
  let s = `M${n[0]} ${n[1]}`
  for (let i = 2; i < n.length; i += 2) s += `L${n[i]} ${n[i + 1]}`
  return s + 'Z'
}

export function Lockup({
  size = 40,
  className,
  decorative = false,
  railSize = 32,
}: {
  readonly size?: number
  readonly className?: string
  /** Inside a wrapper that already carries the name — the sidebar's brand control. */
  readonly decorative?: boolean
  /** The px width the collapsed end must render at. The morph lands exactly on the mark at
   *  this size, which is what makes the rail's drawing `markGeometry.ts`'s and not a resemblance. */
  readonly railSize?: number
}) {
  // Per instance: the sidebar and #/gallery can be mounted at once, and two lockups sharing
  // `url(#m)` is silent — both references resolve, to the first one's gradient.
  const id = useId().replace(/:/g, '')
  const metal = MARKS.bluesteel.bracket
  const svg = useRef<SVGSVGElement>(null)

  /* THE RAIL END, MAPPED INTO THIS VIEWBOX. `RAIL_ARM` is emitted in the mark's own 100 x 100 box
     because the mapping needs the app's two size constants and those are a product decision that
     would go stale inside a generated file. One rail unit is `railSize / 100` px and one unit here
     is `size / BLOCK.ref` px, so the rail's box is `k * 100` units, centred. */
  const k = (railSize * BLOCK.ref) / (100 * size)
  const ox = (BLOCK.w - 100 * k) / 2
  const oy = (BLOCK.h - 100 * k) / 2
  const target = RAIL_D.map((v, i) => (i % 2 ? v * k + oy : v * k + ox))
  const targetCaps = RAIL_CAPS.map(([cx, cy, r]) => [cx * k + ox, cy * k + oy, r * k] as const)

  useEffect(() => {
    const el = svg.current
    const slot = el?.parentElement
    if (!el || !slot) return

    const arms = el.querySelectorAll<SVGPathElement>('.bn-lockup-arm')
    const discs = el.querySelectorAll<SVGCircleElement>('.bn-lockup-cap')
    const openW = (size * BLOCK.w) / BLOCK.ref

    const write = (t: number) => {
      const d = draw(OPEN_D.map((v, i) => v + ((target[i] ?? v) - v) * t))
      for (const a of arms) a.setAttribute('d', d)
      discs.forEach((c, i) => {
        const from = BRACKET_CAPS[i % CAPS]
        const to = targetCaps[i % CAPS]
        if (!from || !to) return
        for (const [n, j] of [['cx', 0], ['cy', 1], ['r', 2]] as const)
          c.setAttribute(n, String(from[j] + (to[j] - from[j]) * t))
      })
    }

    /* Progress is the SLOT's own width between its two resting sizes. It is measured rather than
       counted, so a transition the browser never ran (reduced motion, a background tab) lands the
       morph in one frame with no branch here, and a retuned `--bn-ease` is followed rather than
       duplicated. The loop stops when the width has stopped moving. */
    let raf = 0
    let last = -1
    let still = 0
    const sample = () => {
      const w = slot.getBoundingClientRect().width
      write(Math.min(1, Math.max(0, (openW - w) / (openW - railSize))))
      return w
    }
    const tick = () => {
      const w = sample()
      still = Math.abs(w - last) < 0.05 ? still + 1 : 0
      last = w
      raf = still > 2 ? 0 : requestAnimationFrame(tick)
    }
    tick()

    /* THE OBSERVER WRITES, IT DOES NOT ONLY SCHEDULE. A ResizeObserver callback runs after layout
       and before paint, so measuring and writing inside it lands in the SAME frame the box moved.
       Scheduling a rAF instead costs one frame — invisible during a 320ms ease and not invisible
       under `prefers-reduced-motion`, where the width jumps in one frame and that one frame is the
       whole animation: measured, the type had already gone while the frame still stood at full
       size. Which is a smaller version of the 200ms hole this design was built to remove. */
    const observed = () => {
      const w = sample()
      still = Math.abs(w - last) < 0.05 ? still + 1 : 0
      last = w
      if (!raf && still <= 2) raf = requestAnimationFrame(tick)
    }
    // `transitionrun` rather than `transitionstart`: it fires before the delay, so the first frame
    // of the width's own transition is already measured.
    slot.addEventListener('transitionrun', observed)
    const ro = new ResizeObserver(observed)
    ro.observe(slot)
    return () => {
      cancelAnimationFrame(raf)
      slot.removeEventListener('transitionrun', observed)
      ro.disconnect()
    }
  }, [size, railSize, target, targetCaps])

  const arm = (
    <>
      <path className="bn-lockup-arm" d={BRACKET_ARM} />
      {BRACKET_CAPS.map(([cx, cy, r]) => (
        <circle className="bn-lockup-cap" key={`${cx},${cy}`} cx={cx} cy={cy} r={r} />
      ))}
    </>
  )

  return (
    <svg
      ref={svg}
      className={className ? `bn-lockup ${className}` : 'bn-lockup'}
      width={(size * BLOCK.w) / BLOCK.ref}
      height={(size * BLOCK.h) / BLOCK.ref}
      viewBox={`0 0 ${BLOCK.w} ${BLOCK.h}`}
      style={{
        // read by kit.css, which chooses between this and flat ink per theme
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
      {/* the frame: one arm and its 180-degree twin, both taking their fill by inheritance. The
          spin is about the block's centre, and the rail's box is centred there too, so one
          transform serves both ends of the morph. */}
      <g className="bn-lockup-bracket">
        {arm}
        <g transform={BRACKET_SPIN}>{arm}</g>
      </g>
      <path className="bn-lockup-kanji" d={KANJI_PATH} />
      <path className="bn-lockup-roman" d={ROMAN_PATH} />
    </svg>
  )
}
