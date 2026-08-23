/* The one question every keyboard handler in this app asks first: is the person typing?
 *
 * HOISTED AT ITS FOURTH COPY. `trigger.ts` wrote it for the capture keys, `ReviewQueue.tsx`
 * copied it for the digits, `PullPreview.tsx` for the arrows, `App.tsx` for the leader chord
 * — four identical functions, each one drift away from a screen where holding an arrow key
 * in a search field walks the selection. `server.ts:describeFailure` set the precedent: a
 * third copy is when a helper moves to a shared module, and this one got a fourth before
 * anyone moved it (recorded in `PullPreview.tsx` at the time, deliberately, because the
 * hoist needed a new file and a map entry — this file and its entry are that debt paid).
 *
 * `isContentEditable` and not the attribute: the property resolves `inherit`, which the
 * attribute string does not. */
export function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) return true
  if (target instanceof HTMLSelectElement) return true
  return target.isContentEditable
}
