import { useEffect, type RefObject } from 'react'

/* DIALOG FOCUS FOR THE RUNS OVERLAYS — the composer and the store-wide reconcile sheet.
 *
 * Three things a modal owes the keyboard: focus lands inside it when it opens, Tab and
 * Shift+Tab stay inside it while it is open, and focus goes back to the control that opened
 * it when it closes. Escape closes it, exactly as before. Worth promoting to a kit Dialog. */

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), ' +
  'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function focusables(root: HTMLElement): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
    (node) => node.offsetParent !== null || node === document.activeElement,
  )
}

export function useOverlayFocus(node: RefObject<HTMLElement | null>, open: boolean, onClose: () => void): void {
  /* Land inside on open; hand focus back on close. Keyed on `open` alone so a changed
     `onClose` identity mid-open cannot yank focus back to the opener. */
  useEffect(() => {
    if (!open) return
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
    node.current?.focus()
    return () => {
      if (opener !== null && opener.isConnected) opener.focus()
    }
  }, [node, open])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
        return
      }
      if (event.key !== 'Tab') return
      const root = node.current
      if (root === null) return
      const items = focusables(root)
      if (items.length === 0) {
        event.preventDefault()
        root.focus()
        return
      }
      const first = items[0]!
      const last = items[items.length - 1]!
      const active = document.activeElement
      const inside = active !== null && root.contains(active)
      if (event.shiftKey) {
        if (!inside || active === first || active === root) {
          event.preventDefault()
          last.focus()
        }
      } else if (!inside || active === last) {
        event.preventDefault()
        first.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [node, open, onClose])
}
