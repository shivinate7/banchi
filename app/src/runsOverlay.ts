import { useEffect, useLayoutEffect, useRef, type RefObject } from 'react'

import { useOverlayLayer } from './kit/overlay'

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

export function useOverlayFocus(
  node: RefObject<HTMLElement | null>,
  open: boolean,
  onClose: () => void,
  /** True while this overlay has a request in flight. Escape does nothing while it is set.
   *  Optional: an overlay that cannot be mid-request passes nothing and behaves as before. */
  hold = false,
  /** The sheet's own scrim. Registered with the stack, so it sits one step under this sheet and
   *  ABOVE any layer this sheet was opened from, and dims it (F3, PR 2 integration review). */
  scrim?: RefObject<HTMLElement | null>,
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

  /* THESE SHEETS JOIN THE KIT'S ONE STACK (`kit/overlay.tsx:useOverlayLayer`), found at the PR 2
     integration. The review lane opens the runs screen inside a kit `Sheet`, and this hook used to
     keep its own key handler and its own static z-index. So a reconcile or rescue sheet opened
     from there painted UNDER the kit sheet it was opened from, and the kit sheet's body took every
     press ("Match the store" could not be clicked). The stack now decides which layer is on top,
     traps Tab in the top layer only, and gives Escape to the top layer only.

     ESCAPE STILL MATCHES WHAT IS PAINTED (D128). The stack reads its `onEscape` through a ref that
     a passive effect refreshes, which would reopen the window D128 closed: for one task the drop
     zone draws disabled while the handler still holds the old `hold === false`. So the function
     handed to it is one stable closure that reads `hold` and `onClose` from refs this hook sets in
     a LAYOUT effect, inside the commit and before paint. */
  const holdNow = useRef(hold)
  const closeNow = useRef(onClose)
  useLayoutEffect(() => {
    holdNow.current = hold
    closeNow.current = onClose
  })
  const escape = useRef(() => {
    if (!holdNow.current) closeNow.current()
  })
  useOverlayLayer(node, { active: open, onEscape: escape.current, scrim })
}
