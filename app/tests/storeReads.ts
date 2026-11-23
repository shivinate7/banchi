/** One wire entry as a spec records it: the method and the path, with the body left to the caller. */
export type WireEntry = { method: string; path: string }

/** THE STORE READS A SPEC'S WIRE HOLDS AFTER THE WRITE AT `at`: each GET the predicate names, sent after that entry.
 *
 *  A screen re-reads after a write by sending a GET the screen sends only because of that write, so a case asserts
 *  the write reached the wire first and then counts the reads after it. `isStoreRead` names the store's own paths for
 *  the screen under test (`/orders` on the Orders walk; `/search` and `/inventory/<n>` on `#/inventory`).
 *
 *  An `at` below zero means the write has not reached the wire. That is refused here rather than counted, because a
 *  count from index -1 would take the mount's own read for a re-read and pass. */
export function storeReadsAfter(
  wire: readonly WireEntry[],
  at: number,
  isStoreRead: (path: string) => boolean,
): number {
  if (at < 0) throw new Error('storeReadsAfter: the write has not reached the wire, so there is no read to count after it')
  return wire.slice(at + 1).filter((entry) => entry.method === 'GET' && isStoreRead(entry.path)).length
}
