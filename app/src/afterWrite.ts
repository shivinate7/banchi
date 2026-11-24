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
 * (`CLAUDE.md`). Writes answered while a round runs fold into one more round after it, of their kind, or of `other` when they differ.
 */
import { useEffect, useRef } from 'react'

/** What a write was, so a screen re-reads only what it touched (a burst of clients kills the capture server). A `sale`
 *  changes the copy, its box and the counts, the review queues and the order claims: it moves no price and buries no box.
 *  A `tick` is a kept suggestion tick, and moves only the ticks on the worklist. A `corpus` write is a price save, a clear
 *  or its Undo, and moves the saved prices alone. A `refresh` is a Refresh Now press: it moves the refresh state and the
 *  saved prices. A `send` is a Send that answered: the screen's own reload reads the worklist and the saved prices, so
 *  a send re-reads only what that reload does not. Any other write is `other`, which re-reads all of it. */
export type WriteKind = 'sale' | 'tick' | 'corpus' | 'refresh' | 'send' | 'other'

type Reread = (kind: WriteKind) => Promise<void>

/** WHICH RE-READ A PRICE WRITE OWES (`afterWrite`, D73). A save, a clear or an Undo that answered owes the saved prices, and its re-read may take
 *  the digest it reads (D86). One the server refused (`corpus_moved`) or never answered wrote nothing the screen knows of, so its re-read is `other`:
 *  it reads all, and takes no digest, or the next save would overwrite the writer that moved the file. */
export const corpusKind = (failed: boolean): WriteKind => (failed ? 'other' : 'corpus')

/** How long one round of re-reads may run before the next write's round may start. */
const ROUND_LIMIT_MS = 30_000

const registered = new Set<Reread>()
let inFlight = false
/** The round waiting behind the one in flight, or null. Writes folded into it of one kind keep it; two kinds make it `other`. */
let pending: WriteKind | null = null

/** Start the registered re-reads, now, without waiting. A round already out takes this as one pending round. */
export function rereadNow(kind: WriteKind = 'other'): void {
  if (inFlight) {
    pending = pending === null || pending === kind ? kind : 'other'
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
 *  know it is unchanged. A failure is rethrown for the caller to say. `kind` says which re-read the write is owed, or, as a
 *  function of whether the write failed, which one: a Send that answered leaves the worklist to its own reload, and one
 *  that did not has no reload coming. Every write that names no kind re-reads all. */
export async function afterWrite<T>(write: () => Promise<T>, kind: WriteKind | ((failed: boolean) => WriteKind) = 'other'): Promise<T> {
  let failed = true
  try {
    const answer = await write()
    failed = false
    return answer
  } finally {
    rereadNow(typeof kind === 'function' ? kind(failed) : kind)
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
