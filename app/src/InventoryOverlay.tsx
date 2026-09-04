import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import './InventoryOverlay.css'

/* One overlay primitive for the inventory screen: a right-side sheet, a bottom sheet, a centred
   dialog, or a lightbox. Portalled to <body> so no ancestor transform can pin it, focus-trapped,
   Escape closes it, and the body stops scrolling behind it. Focus returns to wherever it was. */

export type OverlayKind = 'sheet' | 'bottom' | 'dialog' | 'lightbox'

const FOCUSABLE =
  'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])'

const PANEL: Record<OverlayKind, string> = {
  sheet: 'bn-sheet inv-sheet',
  bottom: 'bn-sheet bn-sheet-bottom inv-sheet-bottom',
  dialog: 'bn-dialog inv-dialog',
  lightbox: 'inv-lightbox',
}

export function Overlay({
  kind,
  label,
  onClose,
  children,
  className,
  /** Let the walk's arrow keys through (the phone's box sheet wants them). Off by default so a
   *  sheet over the screen does not step the card behind it. */
  passKeys = false,
}: {
  readonly kind: OverlayKind
  readonly label: string
  readonly onClose: () => void
  readonly children: ReactNode
  readonly className?: string
  readonly passKeys?: boolean
}) {
  const panel = useRef<HTMLDivElement | null>(null)
  const close = useRef(onClose)
  useEffect(() => {
    close.current = onClose
  })

  useEffect(() => {
    const node = panel.current
    const before = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const first =
      node?.querySelector<HTMLElement>('[data-autofocus]') ??
      node?.querySelector<HTMLElement>(FOCUSABLE) ??
      node
    first?.focus({ preventScroll: true })

    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation()
        event.preventDefault()
        close.current()
        return
      }
      if (!passKeys && (event.key === 'ArrowLeft' || event.key === 'ArrowRight')) {
        event.stopPropagation()
        return
      }
      if (event.key !== 'Tab' || node === null) return
      const items = [...node.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
        (el) => el.offsetParent !== null || el === document.activeElement,
      )
      const head = items[0]
      const tail = items[items.length - 1]
      if (head === undefined || tail === undefined) {
        event.preventDefault()
        node.focus()
        return
      }
      const active = document.activeElement
      if (event.shiftKey && (active === head || !node.contains(active))) {
        event.preventDefault()
        tail.focus()
      } else if (!event.shiftKey && (active === tail || !node.contains(active))) {
        event.preventDefault()
        head.focus()
      }
    }
    document.addEventListener('keydown', onKey, true)
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey, true)
      document.body.style.overflow = overflow
      if (before !== null && document.contains(before)) before.focus({ preventScroll: true })
    }
  }, [passKeys])

  return createPortal(
    <>
      <div className="bn-scrim" onClick={() => close.current()} />
      <div
        ref={panel}
        className={[PANEL[kind], className].filter(Boolean).join(' ')}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        tabIndex={-1}
        onClick={kind === 'lightbox' ? () => close.current() : undefined}
      >
        {/* The lightbox closes on any press, which a mouse learns from `cursor: zoom-out` and a
            thumb learns from nothing. So it gets one visible control — which is also the only
            focusable thing inside it, so the focus trap has somewhere to land. */}
        {kind === 'lightbox' ? (
          <button type="button" className="inv-lightbox-close" aria-label="Close the photograph" onClick={() => close.current()}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" aria-hidden="true">
              <path d="M6 6l12 12 M18 6L6 18" />
            </svg>
          </button>
        ) : null}
        {children}
      </div>
    </>,
    document.body,
  )
}
