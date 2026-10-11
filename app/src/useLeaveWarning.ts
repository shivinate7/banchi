import { useEffect } from 'react'

let guarded = 0

/** The page asks before it unloads while `active`: typed work the person has not put anywhere yet.
 *  The one home of that guard; Pricing (unsaved prices) and Orders (a paste) both call it. The hash
 *  router asks `confirmLeave` for the in-app half, so one registration covers both. */
export function useLeaveWarning(active: boolean): void {
  useEffect(() => {
    if (!active) return undefined
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    guarded += 1
    return () => {
      window.removeEventListener('beforeunload', warn)
      guarded -= 1
    }
  }, [active])
}

/** True when the person may move to another screen: nothing is guarded, or they said leave. */
export function confirmLeave(): boolean {
  return guarded === 0 || window.confirm('Leave this screen? What you typed here is not saved yet.')
}
