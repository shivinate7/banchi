import { useEffect } from 'react'

/** The page asks before it unloads while `active`: typed work the person has not put anywhere yet.
 *  The one home of that guard; Pricing (unsaved prices) and Orders (a paste) both call it. */
export function useLeaveWarning(active: boolean): void {
  useEffect(() => {
    if (!active) return undefined
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [active])
}
