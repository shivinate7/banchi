/* app/src/afterWrite.ts: the one home of "re-read after a write" for a screen that registers its reads.
 *
 * D73 (reworded): a screen re-reads after every write the server answers, a refusal included, and on return. A write
 * that was refused still says the screen was behind (another tab sold the copy; the order moved on), so a 4xx re-reads
 * as a success does. A write that got no answer (the server unreachable, a 5xx, a busy store) changed nothing the
 * screen can read, so it re-reads nothing.
 *
 * `afterWrite(write)` runs the write and starts the re-reads when it answers. It never awaits them: the person's next
 * press must not wait on a read, and the re-reads never refetch a list that reorders (D313). A screen registers its
 * reads once with `useRereadOnWrite`, and the registry is module-level, so a write pressed on a toast after the screen
 * unmounted still reaches whatever is mounted by the time it answers, or nothing, and the next mount re-reads anyway.
 *
 * THE RE-READS MERGE: at most one round in flight and one pending, because a burst of clients kills the capture server
 * (`CLAUDE.md`). Writes answered while a round runs fold into one more round after it.
 */
import { useEffect, useRef } from 'react'
import { describeFailure, isFinalUndoRefusal } from './server'

type Reread = () => Promise<void>

const registered = new Set<Reread>()
let inFlight = false
let pending = false

/** Start the registered re-reads, now, without waiting. A round already out takes this as one pending round. */
export function rereadNow(): void {
  if (inFlight) {
    pending = true
    return
  }
  inFlight = true
  void (async () => {
    try {
      do {
        pending = false
        await Promise.allSettled([...registered].map((reread) => reread()))
      } while (pending)
    } finally {
      inFlight = false
    }
  })()
}

/** Run one write, then re-read what the screen shows: on its answer, and on a refusal (a final 4xx), which is rethrown for the
 *  caller to say. A write that got no answer rethrows with nothing re-read. */
export async function afterWrite<T>(write: () => Promise<T>): Promise<T> {
  let done: T
  try {
    done = await write()
  } catch (err) {
    if (isFinalUndoRefusal(describeFailure(err))) rereadNow()
    throw err
  }
  rereadNow()
  return done
}

/** Register this screen's reads, in the order they must run (each reads what the one before it found), for as long as it
 *  is mounted. The latest closure runs, so the screen may pass a fresh function each render. */
export function useRereadOnWrite(reread: Reread): void {
  const latest = useRef(reread)
  latest.current = reread
  useEffect(() => {
    const run = () => latest.current()
    registered.add(run)
    return () => void registered.delete(run)
  }, [])
}
