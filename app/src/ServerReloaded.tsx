/* "The server just reloaded" — the client half of `GET /status`'s `boot_id` (D53).
 *
 * WHY IT EXISTS. `make up` restarts the capture server whenever a watched Python file changes,
 * which is many times in a working session. That is the point of it — `docs/GATES.md` records
 * box 95's run writing whole-second timestamps two hours after the millisecond fix landed,
 * because the server process predated the fix and nothing on any screen could say so. Making
 * the restart automatic removes the defect; making it VISIBLE is what stops the operator
 * wondering whether the code they are looking at is the code that is running.
 *
 * WHAT IT IS NOT: an acknowledgement to dismiss. `docs/DESIGN.md` bans those outright, and the
 * ban is why this demands nothing, blocks nothing, takes no keystroke and expires on its own.
 * It is the shape of the review queue's answer receipt rather than the shape of a dialog.
 *
 * IT NEVER SPEAKS ON FIRST SIGHT. The first response establishes the baseline; only a CHANGE is
 * worth a word. Without that rule every page load would announce a reload that did not happen,
 * and a notice that cries wolf on load is one nobody reads on the day it matters.
 *
 * A SERVER THAT SENDS NO BOOT HEADER IS SILENT, NOT SUSPICIOUS — a server older than D53, or,
 * far more often, a stubbed route in a spec. Inventing a reload from a missing header would
 * make every test that stubs the wire report one.
 *
 * IT GENERATES NO TRAFFIC. `app/src/server.ts` reads the header off responses the screens were
 * already fetching and calls the listener registered here. The first build polled `/status`
 * every five seconds instead, and the cost was not the requests themselves — it was that every
 * owner-side spec inherited an unstubbed call to whatever real server was listening, which is
 * the hazard `app/tests/inventory.spec.ts` documents by name. */

import { useEffect, useRef, useState } from 'react'
import { onServerBoot } from './server'
import './ServerReloaded.css'

/* Long enough to be read if you happen to look up, short enough that it is gone before it
 * becomes furniture. */
const SHOW_MS = 6000

export function ServerReloaded() {
  const [shown, setShown] = useState(false)
  const timer = useRef<number | undefined>(undefined)

  useEffect(() => {
    /* SUBSCRIBES; IT DOES NOT POLL. The first build polled `/status` every five seconds, which
     * worked and which made every owner-side screen issue a request nothing had asked for — in
     * every Playwright spec, against whatever real server was listening. `app/src/server.ts`
     * observes a response header instead, on requests the screens were already making, so this
     * component now generates no traffic of its own at all. */
    const stop = onServerBoot(() => {
      setShown(true)
      window.clearTimeout(timer.current)
      timer.current = window.setTimeout(() => setShown(false), SHOW_MS)
    })
    return () => {
      stop()
      window.clearTimeout(timer.current)
    }
  }, [])

  if (!shown) return null
  return (
    /* `status` rather than `alert`: this is not an error and must not interrupt whatever a
     * screen reader is in the middle of. Polite by construction. */
    <div className="server-reloaded" role="status">
      <span className="server-reloaded-dot" aria-hidden="true" />
      the capture server reloaded — it is running your latest code
    </div>
  )
}
