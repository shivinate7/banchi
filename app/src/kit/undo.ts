import { useEffect, useRef } from 'react'
import { isEditableTarget } from '../keys'

/* THE ONE `U` PRIMITIVE (`docs/specs/undo.md` §11.3, UN-10). Five screens each wrote their own
 * copy of this listener — repeat/modifier/editable-target guards, a ref so a key pressed
 * between a write and its effect never closes over stale data, `window`-level so a phone
 * reaches it the same as a keyboard. This is that copy, once. A screen that still binds `U`
 * itself is what `make kit-adoption` fails (UN-10's own check).
 *
 * SAME LETTER, SAME MEANING EVERYWHERE: the newest reversible write on the screen, wherever one
 * stands (`docs/specs/undo.md` §3). Nothing about WHICH write that is lives here — that is the
 * screen's own receipt or session stack, read fresh through `getUndo`. */
export const UNDO_KEY = 'u'
export const UNDO_KEY_LABEL = 'U'

/** Arms `U` for the newest reversible write on this screen.
 *
 *  `getUndo` returns the function to call, or `null` when there is nothing to undo right now —
 *  read through a ref on every keypress, never a dependency list, so the listener is
 *  registered exactly once and still sees this render's freshest answer. Where there is
 *  nothing to undo, the key does nothing: no beep, no navigation. Yields to a repeat, a
 *  modifier and typing, the same guard every prior copy carried. */
export function useUndoHotkey(getUndo: () => (() => void) | null): void {
  const ref = useRef(getUndo)
  ref.current = getUndo
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.repeat) return
      if (event.metaKey || event.ctrlKey || event.altKey) return
      if (isEditableTarget(event.target)) return
      if (event.key.toLowerCase() !== UNDO_KEY) return
      const fire = ref.current()
      if (fire === null) return
      event.preventDefault()
      fire()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])
}
