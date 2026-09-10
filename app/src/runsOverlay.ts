import { useEffect, useLayoutEffect, type RefObject } from 'react'

/* DIALOG FOCUS FOR THE RUNS OVERLAYS — the composer and the store-wide reconcile sheet.
 *
 * Three things a modal owes the keyboard: focus lands inside it when it opens, Tab and
 * Shift+Tab stay inside it while it is open, and focus goes back to the control that opened
 * it when it closes. Escape closes it. Worth promoting to a kit Dialog.
 *
 * ESCAPE HOLDS WHILE A REQUEST IS IN FLIGHT, and that is the ONLY thing it is gated on. These sheets stay mounted (`Runs.tsx` renders them with `hidden={!open}`), so a typed
 * field, a picked file, a preview and a written stamp are all still there when the sheet is
 * reopened — the cost of an accidental Escape is a reopen, not work. What does not survive is a
 * `fetch` nobody can see: nothing aborts it, and its receipt toasts for a sheet that is gone.
 * So the guard is exactly that case and NOT unfinished work, on the owner's ruling of
 * 2026-09-04. A sheet with nothing in flight closes on Escape as it always has.
 *
 * IT DELIBERATELY DOES NOT YIELD TO TYPING, and that was tried first. `keys.ts` is the question
 * every unmodified-key handler in this app asks, because those keys would otherwise be swallowed
 * by a field that wants the character — CLAUDE.md scopes it to exactly that: `?` is the one
 * unmodified key the shell takes. Escape types nothing. Gating it on `isEditableTarget` made it
 * dead in the four number fields of the markdown sheet, which is where Tab leaves you and where a
 * person is most likely to reach for it — `app/tests/markdown.spec.ts`'s focus-trap case is what
 * said so, by pressing Escape from inside the trap and never getting out. The typed values it
 * would have been protecting are not at risk anyway: the sheet stays mounted, so they are still
 * there on the next opening. Where a FIELD owns Escape for itself — `Pricing.tsx`'s price cell,
 * which reverts and blurs — the guard belongs on that field's own handler, and it is there. */

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), ' +
  'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function focusables(root: HTMLElement): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
    (node) => node.offsetParent !== null || node === document.activeElement,
  )
}

export function useOverlayFocus(
  node: RefObject<HTMLElement | null>,
  open: boolean,
  onClose: () => void,
  /** True while this overlay has a request in flight. Escape does nothing while it is set.
   *  Optional: an overlay that cannot be mid-request passes nothing and behaves as before. */
  hold = false,
): void {
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

  /* A LAYOUT EFFECT, NOT A PASSIVE ONE, BECAUSE THE HANDLER MUST MATCH WHAT IS PAINTED (D128).
     `hold` is in this effect's dependencies, and a passive effect re-registers AFTER the browser
     paints: for one task the screen shows the drop zone disabled while the listener still attached
     is the previous render's, whose closure has `hold === false` — and an Escape landing in that
     task closes a sheet with a request in flight, the one thing this argument says cannot happen.
     Nothing sees that window on a fast machine; the Ubuntu runner saw it three times in sixteen
     runs, the sheet gone under `toBeVisible` after an Escape pressed the moment `disabled` drew.
     A layout effect runs inside the commit, before paint, so a state the screen shows is a state
     the listener already has. */
  useLayoutEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        if (hold) return
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
  }, [node, open, onClose, hold])
}
