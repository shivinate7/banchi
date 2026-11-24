/* app/src/afterWrite.ts: the one home of "re-read after a write" for a screen that registers its reads.
 *
 * D73 (reworded): a screen re-reads after every write that settles, a refusal included, and on return. A refused write
 * still says the screen was behind (another tab sold the copy; the order moved on). A write that failed with a 5xx or a
 * network error may still have committed, so it re-reads too.
 *
 * `afterWrite(write)` runs the write and starts the re-reads in a `finally`, after every outcome (an answer, a refusal, a 5xx, a network error). It never awaits them: the person's next
 * press must not wait on a read, and the re-reads never refetch a list that reorders (D313). A screen registers its
 * reads once with `useRereadOnWrite`, and the registry is module-level, so a write pressed on a toast after the screen
 * unmounted still reaches whatever is mounted by the time it answers, or nothing, and the next mount re-reads anyway.
 *
 * THE RE-READS MERGE: at most one round in flight and one pending, because a burst of clients kills the capture server
 * (`CLAUDE.md`). Writes answered while a round runs fold into one more round after it, of the widest kind among them.
 */
import { useEffect, useRef } from 'react'

/** What a write was. A `sale` changes the copy, its box and the counts, the review queues and the order claims: it moves no
 *  price and buries no box, so a screen's registered read may leave its buried boxes and price tables as read. Any other
 *  write is `other`, which re-reads all of it. */
export type WriteKind = 'sale' | 'other'

type Reread = (kind: WriteKind) => Promise<void>

/** How long one round of re-reads may run before the next write's round may start. */
const ROUND_LIMIT_MS = 30_000

const registered = new Set<Reread>()
let inFlight = false
/** The round waiting behind the one in flight, or null. Writes folded into it keep the widest kind: one `other` makes it `other`. */
let pending: WriteKind | null = null

/** Start the registered re-reads, now, without waiting. A round already out takes this as one pending round. */
export function rereadNow(kind: WriteKind = 'other'): void {
  if (inFlight) {
    pending = pending === 'other' || kind === 'other' ? 'other' : 'sale'
    return
  }
  inFlight = true
  void (async () => {
    try {
      for (let round: WriteKind | null = kind; round !== null; ) {
        const now: WriteKind = round
        /* A ROUND THAT NEVER SETTLES (a request the server holds open) ends at the limit, so it cannot shut every later round out. */
        let timer: ReturnType<typeof setTimeout> | undefined
        const limit = new Promise<void>((resolve) => {
          timer = setTimeout(resolve, ROUND_LIMIT_MS)
        })
        try {
          await Promise.race([Promise.allSettled([...registered].map((reread) => reread(now))), limit])
        } finally {
          clearTimeout(timer)
        }
        round = pending
        pending = null
      }
    } finally {
      inFlight = false
    }
  })()
}

/** Run one write, then re-read what the screen shows, whatever the write came to: an answer, a refusal, a 5xx or a network
 *  error. A write that got no answer may still have committed (the server can fail after it writes), so the screen cannot
 *  know it is unchanged. A failure is rethrown for the caller to say. `kind` says which re-read the write is owed: a sale
 *  passes `'sale'`, and every other write re-reads all. */
export async function afterWrite<T>(write: () => Promise<T>, kind: WriteKind = 'other'): Promise<T> {
  try {
    return await write()
  } finally {
    rereadNow(kind)
  }
}

/** Register this screen's reads, in the order they must run (each reads what the one before it found), for as long as it
 *  is mounted. The latest closure runs, so the screen may pass a fresh function each render. The read is told the `WriteKind`
 *  that started its round, and may skip what a sale leaves as read. */
export function useRereadOnWrite(reread: Reread): void {
  const latest = useRef(reread)
  latest.current = reread
  useEffect(() => {
    const run: Reread = (kind) => latest.current(kind)
    registered.add(run)
    return () => void registered.delete(run)
  }, [])
}
