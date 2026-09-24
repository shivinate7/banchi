import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react'
import type { ComponentType, ReactNode, RefObject } from 'react'
import { createPortal } from 'react-dom'
import { Icon, type IconName } from './Icon'
import { Button, useLeave } from './index'
import { closeSheet, useOpenSheet } from './sheets'

/* ONE SHEET, ONE MODAL, ONE POPOVER (UX-057, UX-090, UX-091).
 *
 * Seeded from `Codes.tsx`'s own local sheet, the one overlay in the product that already
 * portalled itself out of the page and gave focus back. What every overlay here shares:
 *
 *   - ONE HEADER: an h2 title and one "Close" button. A footer's dismiss word is "Cancel".
 *   - ONE SIDE: a sheet enters from the right; on a phone every sheet and modal rises from the
 *     bottom (kit.css). No overlay opens from the left.
 *   - FOCUS STAYS INSIDE a blocking overlay until it closes, and GOES BACK to the control that
 *     opened it. If that control has left the page, focus goes to the page's h1, never to body.
 *   - ESCAPE CLOSES THE TOP OVERLAY ONLY, and the shell never sees that Escape.
 *   - PORTALLED TO <body>: `main.bn-page` animates a transform, and a transformed ancestor is
 *     the containing block for a fixed box, so a sheet drawn inline hangs off the page column.
 *
 * `SheetHost` is the one place a registered sheet is drawn (`openSheet`, kit/sheets.ts). */

const FOCUSABLE =
  'a[href], area[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), iframe, summary, [tabindex]:not([tabindex="-1"]), [contenteditable="true"]'

function focusables(root: HTMLElement): HTMLElement[] {
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => {
    if (el.closest('[inert]') !== null) return false
    const box = el.getBoundingClientRect()
    return box.width > 0 || box.height > 0 || el === document.activeElement
  })
}

/* The open overlays, innermost last, blocking and not. Escape acts for the top one only, and a
   focus trap acts only while its overlay is on top. */
const stack: HTMLElement[] = []

function isTop(root: HTMLElement): boolean {
  return stack[stack.length - 1] === root
}

/** Puts `ref` on the overlay stack while `active`. */
function useStacked(ref: RefObject<HTMLElement | null>, active: boolean): void {
  useLayoutEffect(() => {
    const root = ref.current
    if (!active || root === null) return
    stack.push(root)
    return () => {
      const at = stack.lastIndexOf(root)
      if (at >= 0) stack.splice(at, 1)
    }
  }, [ref, active])
}

/** Keeps Tab and Shift-Tab inside `ref` while `active`, and pulls focus back if anything moves
 *  it outside (a press on the scrim, a script). Escape is not this hook's. */
export function useFocusTrap(ref: RefObject<HTMLElement | null>, active = true): void {
  useEffect(() => {
    const root = ref.current
    if (!active || root === null) return
    // A trap nobody put on the stack (a caller outside this file) acts as if it were on top.
    const blocked = () => stack.includes(root) && !isTop(root)
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Tab' || blocked()) return
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
      if (blocked()) return
      const target = event.target
      if (target instanceof Node && root.contains(target)) return
      // A toast sits above every overlay and may be pressed; everything else is behind.
      if (target instanceof HTMLElement && target.closest('.bn-toasts') !== null) return
      const items = focusables(root)
      ;(items[0] ?? root).focus({ preventScroll: true })
    }
    document.addEventListener('keydown', onKey, true)
    document.addEventListener('focusin', onFocusIn)
    return () => {
      document.removeEventListener('keydown', onKey, true)
      document.removeEventListener('focusin', onFocusIn)
    }
  }, [ref, active])
}

/** The page's own h1: where focus goes when the control that opened an overlay is gone. */
function pageHeading(): HTMLElement | null {
  return document.querySelector<HTMLElement>('[data-bn-page-title]') ?? document.querySelector<HTMLElement>('main h1')
}

function restore(opener: HTMLElement | null): void {
  window.requestAnimationFrame(() => {
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

/** Reads the focused control on the render that opens, and gives focus back to it when
 *  `active` turns false or the component unmounts. Read during render, not in an effect: a
 *  field's `autoFocus` inside the overlay has already moved focus by the time an effect runs. */
export function useReturnFocus(active = true): void {
  const opener = useRef<HTMLElement | null>(null)
  const armed = useRef(false)
  if (active && !armed.current) {
    armed.current = true
    const now = document.activeElement
    opener.current = now instanceof HTMLElement && now !== document.body ? now : null
  }
  useEffect(() => {
    if (active || !armed.current) return
    armed.current = false
    restore(opener.current)
    opener.current = null
  }, [active])
  useEffect(
    () => () => {
      if (armed.current) restore(opener.current)
    },
    [],
  )
}

/** Escape closes the top overlay, and nothing else sees that Escape. */
function useEscape(ref: RefObject<HTMLElement | null>, active: boolean, onClose: () => void): void {
  useEffect(() => {
    if (!active) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      const root = ref.current
      if (root === null || !isTop(root)) return
      event.preventDefault()
      event.stopImmediatePropagation()
      onClose()
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [ref, active, onClose])
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

/** First focus: the element inside marked `data-autofocus`, else one that took focus by
 *  itself (`autoFocus`), else the panel. Never the page behind. */
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

type OverlayProps = {
  readonly open: boolean
  readonly onClose: () => void
  readonly title: ReactNode
  readonly icon?: IconName
  /** Actions at the foot: the verb, then "Cancel". */
  readonly footer?: ReactNode
  readonly children?: ReactNode
  readonly className?: string
}

function OverlayFrame({
  kind,
  open,
  onClose,
  title,
  icon,
  footer,
  children,
  className,
}: OverlayProps & { readonly kind: 'sheet' | 'modal' }) {
  const { mounted, leaving } = useLeave(open)
  const panel = useRef<HTMLDivElement>(null)
  const titleId = useId()
  const live = open && !leaving && mounted
  useReturnFocus(open)
  useStacked(panel, live)
  useFocusTrap(panel, live)
  useEscape(panel, live, onClose)
  useScrollLock(mounted)
  useFirstFocus(panel, live)
  if (!mounted) return null
  const base = kind === 'sheet' ? 'bn-sheet bn-overlay' : 'bn-dialog bn-overlay'
  return createPortal(
    <>
      <div className="bn-scrim" data-leaving={leaving ? 'true' : undefined} onClick={onClose} />
      <div
        ref={panel}
        className={[base, className].filter(Boolean).join(' ')}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        data-leaving={leaving ? 'true' : undefined}
        data-bn-overlay={kind}
      >
        <header className="bn-overlay-head">
          {icon ? (
            <span className="bn-overlay-icon">
              <Icon name={icon} size={18} />
            </span>
          ) : null}
          <h2 className="bn-overlay-title" id={titleId}>
            {title}
          </h2>
          <Button variant="ghost" iconOnly icon="x" onClick={onClose} className="bn-overlay-close">
            Close
          </Button>
        </header>
        <div className="bn-overlay-body">{children}</div>
        {footer ? <footer className="bn-overlay-foot">{footer}</footer> : null}
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
 *  CAN be undone never comes here: it acts, and its receipt toast carries Undo. */
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
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      className="bn-confirm"
      footer={
        <>
          <Button variant={tone === 'danger' ? 'danger-solid' : 'primary'} busy={busy} disabled={busy} onClick={onConfirm} data-autofocus="">
            {confirmLabel}
          </Button>
          <Button variant="ghost" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
        </>
      }
    >
      {children}
    </Modal>
  )
}

/** A small panel under the control that opened it. Not blocking: no scrim, and the page stays
 *  live. Escape, a press outside, or focus leaving it closes it, and focus goes back to the
 *  control. */
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
  const [at, setAt] = useState<{ readonly top: number; readonly left: number } | null>(null)
  const live = open && !leaving && mounted
  useReturnFocus(open)
  useStacked(panel, live)
  useEscape(panel, live, onClose)
  useFirstFocus(panel, live)
  useLayoutEffect(() => {
    if (!mounted) return
    const place = () => {
      const a = anchor.current?.getBoundingClientRect()
      if (a === undefined) return
      const width = panel.current?.getBoundingClientRect().width ?? 0
      const left = Math.max(8, Math.min(a.left, window.innerWidth - width - 8))
      setAt({ top: a.bottom + 6, left })
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
    const outside = (target: EventTarget | null) =>
      target instanceof Node && panel.current?.contains(target) !== true && anchor.current?.contains(target) !== true
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
      style={at === null ? { visibility: 'hidden' } : { top: at.top, left: at.left }}
    >
      {children}
    </div>,
    document.body,
  )
}

/* ---- the sheet host -----------------------------------------------------------------------
   THE ONE PLACE A REGISTERED SHEET IS DRAWN. The shell mounts `<SheetHost/>` once, and it draws
   whatever `openSheet(kind, props)` opened (kit/sheets.ts), handing it `closeSheet` as its
   `onClose`. The registry decides WHAT opens; this decides only WHERE it is drawn, so the two
   cannot drift apart. A kind with no registered sheet never reaches here: `openSheet` sends it
   to its own page instead. */
export function SheetHost() {
  const open = useOpenSheet()
  if (open === null) return null
  const { Component, props, kind } = open as unknown as {
    readonly kind: string
    readonly props: object
    readonly Component: ComponentType<{ readonly onClose: () => void }>
  }
  return (
    <div data-bn-sheet-host={kind}>
      <Component {...props} onClose={closeSheet} />
    </div>
  )
}
