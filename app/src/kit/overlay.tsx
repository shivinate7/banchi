import { createContext, useContext, useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import type { ComponentType, ReactNode, RefObject } from 'react'
import { createPortal } from 'react-dom'
import { Icon, type IconName } from './Icon'
import { Button, IconButton, useLeave } from './index'
import { usePageRoute } from './Page'
import { closeSheet, useOpenSheet, type OpenSheet } from './sheets'
import './dialog.css'

/* ONE SHEET, ONE MODAL, ONE POPOVER, AND ONE STACK OF LAYERS (UX-057, UX-090, UX-091).
 *
 * Seeded from `Codes.tsx`'s own local sheet, the one overlay in the product that already
 * portalled itself out of the page and gave focus back. What every overlay here shares:
 *
 *   - ONE HEADER: an h2 title and one "Close" button. A footer's dismiss word is "Cancel".
 *   - ONE SIDE: a sheet enters from the right; on a phone every sheet and modal rises from the
 *     bottom (kit.css). No overlay opens from the left.
 *   - ONE STACK: every open layer, the kit's and the shell's (the palette, the keys sheet, the
 *     drawer), joins it through `useOverlayLayer`. ONLY THE TOP LAYER traps focus and takes
 *     Escape, so a layer opened over another closes first and gives focus back to the control
 *     inside the layer beneath it.
 *   - WHICHEVER OPENED LAST PAINTS ON TOP: `useOverlayLayer` sets each layer's own z-index — and
 *     its own SCRIM's, one step below it — from its position in the stack at the moment it
 *     joins, so a caller elsewhere in the tree (Fulfillment's own photo zoom, the first caller
 *     that is not a kit primitive, and not a portal sibling either) still stacks correctly, and
 *     a SECOND scrimmed layer's own scrim actually dims the first layer's panel rather than
 *     sitting under it — which every scrim sharing one class-wide number cannot do.
 *   - FOCUS GOES BACK to the control that opened the layer. If that control has left the page,
 *     focus goes to the page's h1, never to body. If the person has moved focus somewhere else
 *     on purpose, it stays there.
 *   - PORTALLED TO <body>: `main.bn-page` animates a transform, and a transformed ancestor is
 *     the containing block for a fixed box, so a sheet drawn inline hangs off the page column.
 *
 * `SheetHost` is the one place a registered sheet is drawn (`openSheet`, kit/sheets.ts). */

/* `[tabindex="-1"]` IS EXCLUDED FROM EVERY CLAUSE, NOT ONLY ITS OWN (kit-frame-2, 2026-09-24,
 * the shell lane's finding: focus escaped the palette). `button:not([disabled])` and its
 * siblings below match an element by TAG, and a tag that is naturally focusable stays a match
 * even when `tabindex="-1"` has explicitly pulled it out of the tab order — the old selector's
 * own `[tabindex]:not([tabindex="-1"])` clause only ever governed an element focusable BECAUSE
 * of its `tabindex`, never one focusable for some other reason that also carries `tabindex="-1"`
 * to opt out. A programmatically-focusable-but-not-tabbable control (the shell's palette marks
 * its own selected row this way) was therefore still offered as a Tab stop inside a trapped
 * layer. */
const FOCUSABLE =
  'a[href]:not([tabindex="-1"]), area[href]:not([tabindex="-1"]), button:not([disabled]):not([tabindex="-1"]), input:not([disabled]):not([type="hidden"]):not([tabindex="-1"]), select:not([disabled]):not([tabindex="-1"]), textarea:not([disabled]):not([tabindex="-1"]), iframe:not([tabindex="-1"]), summary:not([tabindex="-1"]), [tabindex]:not([tabindex="-1"]), [contenteditable="true"]:not([tabindex="-1"])'

function focusables(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => {
    if (el.closest('[inert]') !== null) return false
    const box = el.getBoundingClientRect()
    return box.width > 0 || box.height > 0 || el === document.activeElement
  })
}

/* ---- the layer stack ------------------------------------------------------------------------ */

/* The open layers, innermost last, blocking and not. */
const stack: HTMLElement[] = []

function isTop(root: HTMLElement): boolean {
  return stack[stack.length - 1] === root
}

/** `.bn-scrim`/`.bn-dialog`'s own z-index (kit.css) — the floor a layer's inline z-index never
 *  goes below, and what a layer falls back to for the instant before this hook's first paint.
 *  Each layer takes TWO numbers, its own scrim then its own panel, so a later layer's scrim
 *  sits above every earlier layer's panel (actually dims it) and below its own. At depth 0 this
 *  is exactly 60/61, the pair the static stylesheet already used for one layer. */
const BASE_LAYER_Z = 60

/** THE CEILING ON SIMULTANEOUS LAYERS THIS SCHEME CLIMBS FOR. The shell reserves 65 upward for
 *  its own chrome above every kit overlay — `.bn-whichkey` at 65, `.bn-cmdk` at 70, `.bn-toasts`
 *  at 80 (App.css) — so depth 2's pair (64/65) would already tie the first of those. Nothing
 *  this product opens goes three layers deep at once (a confirm over a sheet, or two stacked
 *  modals, are both two): a depth past this ceiling REUSES the ceiling's own pair rather than
 *  climbing into the shell's range, which loses correct ordering only past a depth nothing here
 *  reaches.
 *  THAT LAST CLAIM IS NOW ENFORCED, NOT ONLY ARGUED (kit-frame-2, 2026-09-24). A layer past this
 *  ceiling that also carries a SCRIM reuses the ceiling pair too, and its scrim then sits BELOW
 *  the layer beneath it — undimmed, silently, the exact defect the stack-position scheme exists
 *  to prevent (see the big comment at the top of this file). A layer with no scrim (`Popover`,
 *  Fulfillment's own photo zoom) has nothing to dim and is unaffected, so only a THIRD scrimmed
 *  layer is refused — see `scrimmedStack` below. */
const MAX_LAYER_DEPTH = 2

function layerZ(depth: number): { readonly scrim: number; readonly panel: number } {
  const at = Math.min(depth, MAX_LAYER_DEPTH - 1)
  return { scrim: BASE_LAYER_Z + 2 * at, panel: BASE_LAYER_Z + 2 * at + 1 }
}

/** Currently open layers that carry a scrim, oldest first — a narrower view of `stack` that
 *  leaves out the ones that do not (`Popover`, Fulfillment's own photo zoom: see `scrim` on
 *  `OverlayLayerOptions`). Its length is what `MAX_LAYER_DEPTH` actually bounds. */
const scrimmedStack: HTMLElement[] = []

/** TEST-ONLY OVERRIDE for whether a third scrimmed layer throws (below) — `null` (the default)
 *  reads `import.meta.env.DEV`, Vite's own build-time constant. That constant is inlined at
 *  build time, so no page script can flip it at runtime to drive the production branch from a
 *  test running against a dev server (`make design-check` always is one). Set only by
 *  `gallery.spec.ts` through `window.__overlaySetDevModeForTest`, registered below ONLY while
 *  `import.meta.env.DEV` is true — which a real production bundle never is, so this whole block
 *  is dead code a bundler drops there, and nothing about it ships to a real build regardless of
 *  who calls the setter. */
let devOverride: boolean | null = null
if (import.meta.env.DEV) {
  ;(window as unknown as { __overlaySetDevModeForTest?: (v: boolean | null) => void }).__overlaySetDevModeForTest = (v) => {
    devOverride = v
  }
}
function overlayIsDevMode(): boolean {
  return devOverride ?? import.meta.env.DEV
}

/** True while an overlay layer is open. The shell asks this before it takes a key of its own. */
export function overlayOpen(): boolean {
  return stack.length > 0
}

export type OverlayLayerOptions = {
  /** The layer is open. */
  readonly active: boolean
  /** Escape closes it. Called only while this layer is the top one. Leave it out for a layer
   *  Escape must not close (a confirm that is busy writing). */
  readonly onEscape?: () => void
  /** Tab and Shift-Tab stay inside it, and focus that leaves it is pulled back. A blocking layer
   *  traps; a popover does not. Default true. */
  readonly trap?: boolean
  /** The layer's own scrim, if it has one — a `Popover` and Fulfillment's own photo zoom do
   *  not. Given the SAME stack-position z-index treatment as the panel (`layerZ` above), one
   *  step below it, so a SECOND scrimmed layer's scrim actually sits above the FIRST layer's
   *  panel and dims it — which a shared static number across every scrim (kit.css) cannot do,
   *  because two scrims never differ by which one opened later. */
  readonly scrim?: RefObject<HTMLElement | null>
}

/** JOIN THE ONE STACK. Every layer that sits over the page calls this: the kit's `Sheet`,
 *  `Modal` and `Popover`, and the shell's own palette, keys sheet and drawer. Only the top layer
 *  traps focus and takes Escape, and nothing beneath it sees that Escape. */
export function useOverlayLayer(ref: RefObject<HTMLElement | null>, { active, onEscape, trap = true, scrim }: OverlayLayerOptions): void {
  useLayoutEffect(() => {
    const root = ref.current
    if (!active || root === null) return
    const scrimEl = scrim?.current ?? null
    /* A THIRD SCRIMMED LAYER IS A MISTAKE IN THAT SCREEN, NEVER A LIVE CONDITION TO CRASH ON
     * (coordinator review, 2026-09-24, amending kit-frame-2's first cut of this). `layerZ` clamps
     * at `MAX_LAYER_DEPTH`, so a scrimmed layer past it reuses the ceiling pair — its own scrim
     * landing BELOW the panel it is meant to dim, the exact defect the stack-position scheme
     * exists to prevent, quietly this time because nothing else would notice. Nothing this
     * product opens goes three scrimmed layers deep (this file's own argument, above).
     *   IN DEVELOPMENT this throws, loud, caught by the nearest route's own error boundary
     *   (App.tsx) — the same door a real crash uses — because a developer building a new screen
     *   should see the mistake the moment they make it, not a subtle dim.
     *   IN PRODUCTION a crash is worse than the dim it is refusing: `RouteBoundary` unmounts the
     *   WHOLE screen, discarding whatever the person had not yet saved, over a defect that only
     *   ever misorders which layer a scrim shades. So it logs once and lets the layer open —
     *   the SAME clamp `layerZ` already computes for it — rather than crashing a real session
     *   over a stacking glitch nobody but this file's own review has ever produced. */
    if (scrimEl !== null && scrimmedStack.length >= MAX_LAYER_DEPTH) {
      if (overlayIsDevMode()) {
        throw new Error('Too many things tried to open on this screen at once.')
      }
      console.error(
        'kit/overlay.tsx: a third scrimmed layer opened. layerZ has no pair left for it and is reusing the ceiling pair — dimming may land on the wrong layer.',
      )
    }
    stack.push(root)
    if (scrimEl !== null) scrimmedStack.push(root)
    /* WHICHEVER OPENED LAST PAINTS ON TOP. `.bn-dialog`/`.bn-sheet`/`.bn-popover`/`.bn-scrim`'s
     * own static z-index (kit.css) ties two layers that are not siblings in DOM paint order —
     * a portalled panel and a plain fixed-position overlay elsewhere in the tree (Fulfillment's
     * own photo zoom, `useOverlayLayer`'d for exactly this) do not share a DOM-order tiebreak
     * the way two portals of the same kind do — and it ties a SECOND scrimmed layer's own scrim
     * to the FIRST layer's panel, which needs the second to win, always, and a shared constant
     * cannot express "always the second". The inline style set here beats the stylesheet's
     * number for this one element, and reads `stack`'s length AT THIS PUSH, so it only ever
     * compares layers that are open AT THE SAME TIME — a layer that closed and reopened later
     * still lands above whatever was already open, without the count ever growing unbounded
     * across a long session. */
    const { scrim: scrimZ, panel: panelZ } = layerZ(stack.length - 1)
    root.style.zIndex = String(panelZ)
    if (scrimEl !== null) scrimEl.style.zIndex = String(scrimZ)
    return () => {
      const at = stack.lastIndexOf(root)
      if (at >= 0) stack.splice(at, 1)
      if (scrimEl !== null) {
        const sat = scrimmedStack.lastIndexOf(root)
        if (sat >= 0) scrimmedStack.splice(sat, 1)
      }
      root.style.zIndex = ''
      if (scrimEl !== null) scrimEl.style.zIndex = ''
    }
  }, [ref, active, scrim])

  /* BOTH ARE LAYOUT EFFECTS, SO A LAYER THAT IS PAINTED ALREADY HEARS ITS KEYS (D128, applied
     here at the PR 2 integration). As passive effects they attached after paint, so an Escape
     pressed the moment a Sheet drew was lost, and the Sheet stayed open (`filters.spec.ts`'s
     compact-overlay case, once, under the full suite's load). */
  const escape = useRef(onEscape)
  useLayoutEffect(() => {
    escape.current = onEscape
  })

  useLayoutEffect(() => {
    const root = ref.current
    if (!active || root === null) return
    const onKey = (event: KeyboardEvent) => {
      if (!isTop(root)) return
      if (event.key === 'Escape') {
        // A busy layer swallows Escape without closing: the shell must not see it either.
        event.preventDefault()
        event.stopImmediatePropagation()
        escape.current?.()
        return
      }
      if (event.key !== 'Tab' || !trap) return
      const items = focusables(root)
      if (items.length === 0) {
        event.preventDefault()
        root.focus({ preventScroll: true })
        return
      }
      const first = items[0]
      const last = items[items.length - 1]
      const at = document.activeElement
      if (event.shiftKey && (at === first || at === root || !root.contains(at))) {
        event.preventDefault()
        last?.focus()
      } else if (!event.shiftKey && (at === last || !root.contains(at))) {
        event.preventDefault()
        first?.focus()
      }
    }
    const onFocusIn = (event: FocusEvent) => {
      if (!trap || !isTop(root)) return
      const target = event.target
      if (target instanceof Node && root.contains(target)) return
      // A toast sits above every layer and may be pressed; everything else is behind.
      if (target instanceof HTMLElement && target.closest('.bn-toasts') !== null) return
      const items = focusables(root)
      ;(items[0] ?? root).focus({ preventScroll: true })
    }
    window.addEventListener('keydown', onKey, true)
    document.addEventListener('focusin', onFocusIn)
    return () => {
      window.removeEventListener('keydown', onKey, true)
      document.removeEventListener('focusin', onFocusIn)
    }
  }, [ref, active, trap])
}

/** Keeps Tab inside `ref` while `active`. The same trap `useOverlayLayer` sets, for a caller that
 *  owns its own Escape. Prefer `useOverlayLayer`, which also joins the stack. */
export function useFocusTrap(ref: RefObject<HTMLElement | null>, active = true): void {
  useOverlayLayer(ref, { active })
}

/* ---- focus given back ------------------------------------------------------------------------ */

/** The page's own h1: where focus goes when the control that opened a layer is gone. */
function pageHeading(): HTMLElement | null {
  return document.querySelector<HTMLElement>('[data-bn-page-title]') ?? document.querySelector<HTMLElement>('main h1')
}

function restore(opener: HTMLElement | null): void {
  window.requestAnimationFrame(() => {
    // Focus the person moved somewhere else on purpose stays where they put it. Focus that was
    // inside the layer (now gone, or leaving) is the focus this gives back.
    const now = document.activeElement
    const stranded = now === null || now === document.body || (now instanceof HTMLElement && now.closest('[data-bn-overlay]') !== null)
    if (!stranded) return
    if (opener !== null && document.contains(opener) && opener.closest('[inert]') === null) {
      opener.focus({ preventScroll: true })
      if (document.activeElement === opener) return
    }
    const heading = pageHeading()
    if (heading !== null) {
      if (!heading.hasAttribute('tabindex')) heading.setAttribute('tabindex', '-1')
      heading.focus({ preventScroll: true })
    }
  })
}

/** Reads the focused control on the render that opens, and gives focus back to it when `active`
 *  turns false or the component unmounts. Read during render, not in an effect: a field's
 *  `autoFocus` inside the layer has already moved focus by the time an effect runs. `to` names
 *  the control explicitly (a popover's trigger), for a browser that does not focus a pressed
 *  button. */
export function useReturnFocus(active = true, to?: RefObject<HTMLElement | null>): void {
  const opener = useRef<HTMLElement | null>(null)
  const armed = useRef(false)
  if (active && !armed.current) {
    armed.current = true
    const now = document.activeElement
    opener.current = now instanceof HTMLElement && now !== document.body ? now : null
  }
  const target = () => to?.current ?? opener.current
  useEffect(() => {
    if (active || !armed.current) return
    armed.current = false
    restore(to?.current ?? opener.current)
    opener.current = null
  }, [active, to])
  const latest = useRef(target)
  useEffect(() => {
    latest.current = target
  })
  useEffect(
    () => () => {
      if (armed.current) restore(latest.current())
    },
    [],
  )
}

function useScrollLock(active: boolean): void {
  useLayoutEffect(() => {
    if (!active) return
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = previous
    }
  }, [active])
}

/** First focus: the element inside marked `data-autofocus`, else one that took focus by itself
 *  (`autoFocus`), else the panel. Never the page behind. */
function useFirstFocus(ref: RefObject<HTMLElement | null>, active: boolean): void {
  useEffect(() => {
    if (!active) return
    const frame = window.requestAnimationFrame(() => {
      const root = ref.current
      if (root === null || root.contains(document.activeElement)) return
      const marked = root.querySelector<HTMLElement>('[data-autofocus]')
      ;(marked ?? root).focus({ preventScroll: true })
    })
    return () => window.cancelAnimationFrame(frame)
  }, [ref, active])
}

/* ---- which heading a section inside a layer draws ----------------------------------------------- */

/** True inside a `Sheet` or `Modal`. `Section` reads it: the layer's own title is the h2, so a
 *  section inside it is an h3. */
export const OverlayContext = createContext(false)

export function useInOverlay(): boolean {
  return useContext(OverlayContext)
}

/* ---- Dialog: the bare panel, for a caller that builds its own head -------------------------------- */

/** PROMOTED FROM `InventoryOverlay.tsx` (round 4, docs/map.py's own note on `runsOverlay.ts`:
 *  "the behavior `InventoryOverlay` has, waiting to be promoted to a kit Dialog so the product
 *  has one of these rather than two"). Unlike `Sheet`/`Modal`, `Dialog` owns no title, no icon
 *  and no Close of its own — every caller here already builds its own head (BoxOps' sheet
 *  title, Inventory's Move dialog, the lightbox's own single control) and mounting IS opening:
 *  a caller renders it only while its own `open` state is true, so there is no `open` prop and
 *  no leave animation, matching what `InventoryOverlay.tsx` always did. Four kinds: a
 *  right-side sheet, the phone's bottom sheet, a centred dialog, and the photograph's
 *  lightbox — the fourth closes on any press and carries one visible control, the kit's own
 *  `IconButton` now rather than an inline `<svg>`. Joins the ONE STACK above through the same
 *  `useOverlayLayer` every other layer here does, which `InventoryOverlay.tsx` never did — a
 *  nested kit `Popover` opened from inside one of these did not z-index above it correctly
 *  before this promotion. */
export type DialogKind = 'sheet' | 'bottom' | 'dialog' | 'lightbox'

const DIALOG_PANEL: Record<DialogKind, string> = {
  sheet: 'bn-sheet inv-sheet',
  bottom: 'bn-sheet bn-sheet-bottom inv-sheet-bottom',
  dialog: 'bn-dialog inv-dialog',
  lightbox: 'inv-lightbox',
}

export function Dialog({
  kind,
  label,
  onClose,
  children,
  className,
  /** Let the walk's arrow keys through (the phone's box sheet wants them). Off by default so a
   *  sheet over the screen does not step the card behind it. */
  passKeys = false,
}: {
  readonly kind: DialogKind
  readonly label: string
  readonly onClose: () => void
  readonly children: ReactNode
  readonly className?: string
  readonly passKeys?: boolean
}) {
  const panel = useRef<HTMLDivElement | null>(null)
  const scrim = useRef<HTMLDivElement | null>(null)
  const close = useRef(onClose)
  useEffect(() => {
    close.current = onClose
  })
  useReturnFocus()
  useOverlayLayer(panel, { active: true, onEscape: () => close.current(), scrim })
  useScrollLock(true)
  useFirstFocus(panel, true)

  /* passKeys is this component's own concern, outside what useOverlayLayer covers: it stops
     ArrowLeft/ArrowRight reaching the walk behind the panel, except where a caller says the
     panel itself wants them through. */
  useEffect(() => {
    if (passKeys) return
    const onKey = (event: KeyboardEvent) => {
      const root = panel.current
      if ((event.key === 'ArrowLeft' || event.key === 'ArrowRight') && root !== null && isTop(root)) {
        event.stopPropagation()
      }
    }
    document.addEventListener('keydown', onKey, true)
    return () => document.removeEventListener('keydown', onKey, true)
  }, [passKeys])

  return createPortal(
    <>
      <div ref={scrim} className="bn-scrim" onClick={() => close.current()} />
      <div
        ref={panel}
        className={[DIALOG_PANEL[kind], className].filter(Boolean).join(' ')}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        tabIndex={-1}
        data-bn-overlay={kind}
        onClick={kind === 'lightbox' ? () => close.current() : undefined}
      >
        {/* The lightbox closes on any press, which a mouse learns from `cursor: zoom-out` and a
            thumb learns from nothing. So it gets one visible control — which is also the only
            focusable thing inside it, so the focus trap has somewhere to land. */}
        {kind === 'lightbox' ? (
          <IconButton
            icon="x"
            label="Close photo"
            className="inv-lightbox-close"
            /* The 44px circular face, the backdrop blur and the stage-palette colors are
               `dialog.css`'s own (`.inv-lightbox-close`) — sized here, not at a kit face size,
               the same escape hatch `BoxBrowse.css`'s stepper buttons use. */
            style={{ width: 44, height: 44 }}
            onClick={() => close.current()}
          />
        ) : null}
        {children}
      </div>
    </>,
    document.body,
  )
}

/* ---- sheet and modal ---------------------------------------------------------------------------- */

type OverlayProps = {
  readonly open: boolean
  readonly onClose: () => void
  readonly title: ReactNode
  readonly icon?: IconName
  /** Actions at the foot: the verb, then "Cancel". */
  readonly footer?: ReactNode
  readonly children?: ReactNode
  readonly className?: string
  /** False while the layer must not close: its Close is disabled, and Escape and the scrim do
   *  nothing. A confirm is not dismissible while it writes. */
  readonly dismissible?: boolean
}

type FrameProps = OverlayProps & {
  readonly kind: 'sheet' | 'modal'
  readonly role?: 'dialog' | 'alertdialog'
}

function OverlayFrame({ kind, role = 'dialog', dismissible = true, open, onClose, title, icon, footer, children, className }: FrameProps) {
  const { mounted, leaving } = useLeave(open)
  /* THE FULFILLER GETS WORDS, ALWAYS (D288, spec rule 1; DESIGN.md's 20px floor).
     A Sheet or Modal is portalled to <body>, so it cannot read its persona from where it
     sits in the DOM — `usePageRoute()` is a React context read, which a portal does not
     break, since context follows the component tree rather than the DOM tree. */
  const fulfiller = usePageRoute()?.persona === 'fulfiller'
  const panel = useRef<HTMLDivElement>(null)
  const scrim = useRef<HTMLDivElement>(null)
  const titleId = useId()
  const live = open && !leaving && mounted
  useReturnFocus(open)
  useOverlayLayer(panel, { active: live, onEscape: dismissible ? onClose : undefined, scrim })
  useScrollLock(mounted)
  useFirstFocus(panel, live)
  if (!mounted) return null
  const base = kind === 'sheet' ? 'bn-sheet bn-overlay' : 'bn-dialog bn-overlay'
  return createPortal(
    <>
      <div ref={scrim} className="bn-scrim" data-leaving={leaving ? 'true' : undefined} onClick={dismissible ? onClose : undefined} />
      <div
        ref={panel}
        className={[base, className].filter(Boolean).join(' ')}
        role={role}
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        data-leaving={leaving ? 'true' : undefined}
        data-bn-overlay={kind}
        onKeyDownCapture={(event) => {
          /* A HELD KEY NEVER PRESSES A BUTTON IN A LAYER. Enter held on the control that opened
             the layer repeats into it; only a fresh press counts. */
          if (event.repeat && (event.key === 'Enter' || event.key === ' ')) event.preventDefault()
        }}
      >
        {/* a `div`, not a `header`: portalled to <body>, a header is a second banner */}
        <div className="bn-overlay-head">
          {icon ? (
            <span className="bn-overlay-icon">
              <Icon name={icon} size={18} />
            </span>
          ) : null}
          <h2 className="bn-overlay-title" id={titleId}>
            {title}
          </h2>
          {fulfiller ? (
            <Button
              variant="ghost"
              icon="x"
              onClick={onClose}
              disabled={!dismissible}
              className="bn-overlay-close bn-overlay-close-worded"
            >
              Close
            </Button>
          ) : (
            <IconButton icon="x" label="Close" onClick={onClose} disabled={!dismissible} className="bn-overlay-close" />
          )}
        </div>
        <OverlayContext.Provider value>
          <div className="bn-overlay-body">{children}</div>
        </OverlayContext.Provider>
        {footer ? <div className="bn-overlay-foot">{footer}</div> : null}
      </div>
    </>,
    document.body,
  )
}

/** A panel from the right edge (the bottom, on a phone). For work beside the page: a form, a
 *  detail, a list to pick from. */
export function Sheet(props: OverlayProps) {
  return <OverlayFrame kind="sheet" {...props} />
}

/** A centred panel (the bottom, on a phone). For one decision that stops the page. */
export function Modal(props: OverlayProps) {
  return <OverlayFrame kind="modal" {...props} />
}

/** ASK FIRST, ONLY FOR A PRESS THAT CANNOT BE UNDONE (docs/DESIGN.md, "Ask first, or undo
 *  after"). It says what will happen and to how many, and the verb is the button. A press that
 *  CAN be undone never comes here: it acts, and its receipt toast carries Undo.
 *  FIRST FOCUS IS "CANCEL", and it is an `alertdialog`. WHILE `busy`, nothing closes it: its
 *  Close is disabled and Escape and the scrim do nothing, so a write in flight is never hidden. */
export function ConfirmSheet({
  open,
  onClose,
  onConfirm,
  title,
  children,
  confirmLabel,
  tone = 'danger',
  busy,
}: {
  readonly open: boolean
  readonly onClose: () => void
  readonly onConfirm: () => void
  readonly title: ReactNode
  readonly children?: ReactNode
  readonly confirmLabel: string
  readonly tone?: 'danger' | 'primary'
  readonly busy?: boolean
}) {
  return (
    <OverlayFrame
      kind="modal"
      role="alertdialog"
      dismissible={busy !== true}
      open={open}
      onClose={onClose}
      title={title}
      className="bn-confirm"
      footer={
        <>
          <Button variant={tone === 'danger' ? 'danger-solid' : 'primary'} busy={busy} disabled={busy} onClick={onConfirm}>
            {confirmLabel}
          </Button>
          <Button variant="ghost" onClick={onClose} disabled={busy} data-autofocus="">
            Cancel
          </Button>
        </>
      }
    >
      {children}
    </OverlayFrame>
  )
}

/* ---- popover ------------------------------------------------------------------------------------ */

/** The lowest y a popover may reach: the viewport, or the top of the phone's tab bar. */
function floorY(): number {
  const bar = document.querySelector<HTMLElement>('.bn-tabbar')
  const top = bar !== null && bar.getClientRects().length > 0 ? bar.getBoundingClientRect().top : window.innerHeight
  return Math.min(window.innerHeight, top)
}

/** A small panel under the control that opened it. Not blocking: no scrim, and the page stays
 *  live. Escape, a press outside, focus leaving it, or Tab past its last item closes it, and
 *  focus goes back to the control. It opens ABOVE the control when there is no room below, and
 *  shifts to stay inside the viewport and above the phone's tab bar. */
export function Popover({
  open,
  onClose,
  anchor,
  label,
  children,
  className,
}: {
  readonly open: boolean
  readonly onClose: () => void
  readonly anchor: RefObject<HTMLElement | null>
  readonly label: string
  readonly children?: ReactNode
  readonly className?: string
}) {
  const { mounted, leaving } = useLeave(open)
  const panel = useRef<HTMLDivElement>(null)
  const [at, setAt] = useState<{ readonly top: number; readonly left: number; readonly maxHeight: number } | null>(null)
  const live = open && !leaving && mounted
  useReturnFocus(open, anchor)
  useOverlayLayer(panel, { active: live, onEscape: onClose, trap: false })
  useFirstFocus(panel, live)
  useLayoutEffect(() => {
    if (!mounted) return
    const place = () => {
      const a = anchor.current?.getBoundingClientRect()
      const p = panel.current
      if (a === undefined || p === null) return
      const gap = 6
      const edge = 8
      const floor = floorY() - edge
      const width = p.offsetWidth
      const height = p.scrollHeight
      const left = Math.max(edge, Math.min(a.left, window.innerWidth - width - edge))
      const below = Math.max(floor - (a.bottom + gap), 0)
      const above = Math.max(a.top - gap - edge, 0)
      // below when it fits; above when only that fits; else the roomier side, scrolling
      const down = height <= below || (height > above && below >= above)
      const maxHeight = down ? below : above
      const top = down ? a.bottom + gap : a.top - gap - Math.min(height, above)
      setAt({ top, left, maxHeight })
    }
    place()
    window.addEventListener('resize', place)
    window.addEventListener('scroll', place, true)
    return () => {
      window.removeEventListener('resize', place)
      window.removeEventListener('scroll', place, true)
    }
  }, [mounted, anchor])
  useEffect(() => {
    if (!live) return
    /* A CONTROL INSIDE THE POPOVER THAT OPENS ITS OWN NESTED LAYER (a `Select`/`FilterChips`
     * pick list, `PickPanel` in `kit/data.tsx`) portals to `document.body` too, as a SIBLING of
     * this panel, never a DOM descendant of it. Read alone, `panel.current?.contains(target)`
     * calls that click OUTSIDE and closes the popover under the list that is still open (FilterBar's
     * own popover mode found this: opening a facet inside it closed the popover at once). Every
     * layer that has joined `stack` ABOVE this panel (this file's own layering, above) is part
     * of the CURRENT foreground regardless of DOM nesting, so a target inside one of them is
     * never outside — the same idea `isTop` already reads `stack` for.
     * ONLY LAYERS ABOVE IT, NEVER BELOW (the PR 2 integration review). The first build counted
     * every layer in the stack, so a popover opened inside a `Sheet` treated the whole Sheet as
     * "inside" and never closed on a press elsewhere in it. */
    const outside = (target: EventTarget | null) => {
      if (!(target instanceof Node)) return false
      if (panel.current?.contains(target) === true || anchor.current?.contains(target) === true) return false
      const at = panel.current === null ? -1 : stack.indexOf(panel.current)
      const above = at < 0 ? [] : stack.slice(at + 1)
      return !above.some((root) => root.contains(target))
    }
    const onDown = (event: PointerEvent) => {
      if (outside(event.target)) onClose()
    }
    const onFocusIn = (event: FocusEvent) => {
      if (outside(event.target)) onClose()
    }
    document.addEventListener('pointerdown', onDown)
    document.addEventListener('focusin', onFocusIn)
    return () => {
      document.removeEventListener('pointerdown', onDown)
      document.removeEventListener('focusin', onFocusIn)
    }
  }, [live, onClose, anchor])
  if (!mounted) return null
  return createPortal(
    <div
      ref={panel}
      className={['bn-menu bn-popover', className].filter(Boolean).join(' ')}
      role="dialog"
      aria-label={label}
      tabIndex={-1}
      data-leaving={leaving ? 'true' : undefined}
      data-bn-overlay="popover"
      style={at === null ? { visibility: 'hidden', top: 0, left: 0 } : { top: at.top, left: at.left, maxHeight: at.maxHeight }}
      onKeyDown={(event) => {
        /* TAB PAST THE LAST ITEM (or Shift-Tab past the first) CLOSES IT, and focus goes back to
           the control that opened it, not on into the page (UX-091). */
        if (event.key !== 'Tab' || panel.current === null) return
        const items = focusables(panel.current)
        const first = items[0]
        const last = items[items.length - 1]
        const now = document.activeElement
        const pastEnd = !event.shiftKey && (now === last || items.length === 0)
        const pastStart = event.shiftKey && (now === first || now === panel.current || items.length === 0)
        if (!pastEnd && !pastStart) return
        event.preventDefault()
        onClose()
      }}
    >
      {children}
    </div>,
    document.body,
  )
}

/* ---- the sheet host -----------------------------------------------------------------------------
   THE ONE PLACE A REGISTERED SHEET IS DRAWN. The shell mounts `<SheetHost/>` once, and it draws
   whatever `openSheet(kind, props)` opened (kit/sheets.ts), handing it `open` and `closeSheet` as
   its `onClose`. When the sheet closes, the host keeps it mounted with `open={false}` for one
   leave beat, so the sheet's own leave animation runs before it goes. The registry decides WHAT
   opens; this decides only WHERE it is drawn. A kind with no registered sheet never reaches here:
   `openSheet` sends it to its own page instead. */
type HostedComponent = ComponentType<{ readonly open: boolean; readonly onClose: () => void }>

export function SheetHost() {
  const current = useOpenSheet()
  const last = useRef<OpenSheet | null>(null)
  if (current !== null) last.current = current
  // one beat longer than the kit's leave (`useLeave`'s 140ms), so the sheet finishes its own
  const { mounted } = useLeave(current !== null, 180)
  const shown = current ?? (mounted ? last.current : null)
  if (shown === null) return null
  const { Component, props, kind } = shown as unknown as {
    readonly kind: string
    readonly props: object
    readonly Component: HostedComponent
  }
  return (
    <div data-bn-sheet-host={kind}>
      <Component {...props} open={current !== null} onClose={closeSheet} />
    </div>
  )
}
