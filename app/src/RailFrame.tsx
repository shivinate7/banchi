/* app/src/RailFrame.tsx — the rail's own frame, lifted out of `BoxBrowse.tsx` (lane A2b, on
 * `docs/reviews/ux-2026-09-23/orders-a/PLAN.md`'s component reuse map: "A `RailFrame` with the
 * rest-top measure and the fit-to-window height (D289 rule 2). Inventory passes its box list
 * and walk. Orders passes its buyer list."). WHAT MOVED: the sticky wrapper `<div
 * className="browse-map">` and its one effect, D289 rule 2's own measure ("`BoxBrowse.tsx`
 * measures the rail's top at rest, and the rail's height is the window less that top" — UX-227).
 * The effect is pure over the wrapper's own DOM node and its parent, with no closure over
 * `BoxBrowse.tsx`'s state, so it moves whole. `BoxBrowse.css`'s `.browse-map` rule is untouched
 * and still names the CSS var this file sets (`--browse-rail-rest`), so the default class name
 * below keeps `#/inventory` byte-for-byte on screen. `BoxBrowse.tsx` still needs the mounted
 * node itself, to scroll the selected box row into view within it (`scrollWithin`), so this
 * file takes `ref` as a normal prop (React 19) rather than exporting the node any other way. */

import { useCallback, useLayoutEffect, useState, type ReactNode, type Ref } from 'react'

export type RailFrameProps = {
  readonly ref?: Ref<HTMLDivElement>
  /** Defaults to `browse-map`, `#/inventory`'s own class in `BoxBrowse.css`. `#/orders`'s buyer
   *  list (lane A5) passes its own, over the same sticky/fit-to-window rule. */
  readonly className?: string
  /** `BoxBrowse.tsx` names its rail no other way today. `#/orders`'s buyer rail is a real
   *  landmark (`role="navigation" aria-label="Buyers"`), so these two are a passthrough, not a
   *  new rule — every existing caller that omits them is unchanged. */
  readonly role?: string
  readonly 'aria-label'?: string
  readonly children: ReactNode
}

export function RailFrame({ ref, className = 'browse-map', children, ...rest }: RailFrameProps) {
  /* The same node as state, so this effect runs when the frame mounts (it is not drawn on the
   * first render) — moved comment, `BoxBrowse.tsx`'s own reason, unchanged. */
  const [node, setNode] = useState<HTMLDivElement | null>(null)
  const setRef = useCallback(
    (el: HTMLDivElement | null) => {
      setNode(el)
      if (typeof ref === 'function') ref(el)
      else if (ref) ref.current = el
    },
    [ref],
  )

  /* THE RAIL'S TOP AT REST, for its height (BoxBrowse.css `.browse-map`, UX-227). Read off the
     rail's parent, which is never sticky, so a resize while the page is scrolled reads the same
     number as one at rest. */
  useLayoutEffect(() => {
    const body = node?.parentElement ?? null
    if (node === null || body === null) return
    const measure = () => {
      node.style.setProperty('--browse-rail-rest', `${Math.round(body.getBoundingClientRect().top + window.scrollY)}px`)
    }
    measure()
    window.addEventListener('resize', measure)
    return () => window.removeEventListener('resize', measure)
  }, [node])

  return (
    <div className={className} ref={setRef} {...rest}>
      {children}
    </div>
  )
}
