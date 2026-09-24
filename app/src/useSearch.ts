import { useCallback, useEffect, useMemo, useState } from 'react'

import { filterByQuery, type MatchFields } from './kit/match'
import type { SearchResult } from './types'
import type { Failure } from './server'
import { describeFailure, search } from './server'

/* When a typed query becomes a request, and what comes back.
 *
 * THREE RULES ABOUT ASKING THE SERVER, IN ONE PLACE, BECAUSE THEY ARE ONE DECISION. An empty
 * query asks nothing. A query waits out the debounce before it is asked. An answer to a query
 * that is no longer the current one is discarded. Spread across a field component and a screen
 * those three drift apart, and the way you find out is a screen showing the results for
 * `pika` under the word `pikachu`.
 *
 * THIS IS WHERE THE DEBOUNCE LIVES, AND `SearchField.tsx` DEFAULTS ITS OWN TO ZERO. Both files
 * carry the knob and only one may spend it: two timers in series is 400ms of a person watching
 * a screen not change, and neither file would own the number. The timer belongs beside the
 * request it protects — which is here, next to the other two rules about asking.
 *
 * NO CACHE, NO KEEPING. Results are held for as long as the component is mounted and thrown
 * away with it, the same rule `Inventory.tsx` states: D13 has exactly one place inventory
 * lives, and a browser-side copy produces two answers to "where is this card" with one of them
 * stale and neither labelled. Coming back to the screen re-asks.
 *
 * `loading` IS TRUE THROUGH THE DEBOUNCE AND NOT ONLY THROUGH THE FETCH. It answers "is what is
 * on screen an answer to what is in the box", and during the debounce window it is not — the
 * results still belong to the previous query. Starting it at the fetch would leave a stale
 * result sitting there looking settled for the length of the debounce, which is exactly the
 * period a fast typist spends looking at it.
 */

/** The delay between the last keystroke and the request.
 *
 *  200ms IS AN ASSUMPTION AND IS MARKED AS ONE. It is the usual figure for this and nothing in
 *  this repo has measured it against the store's own latency: `Store.write()` waits up to 30
 *  seconds for the file lock, so a search issued while `./pkmnscan identify` is running can be
 *  slow for reasons no debounce affects. What would settle it is watching the owner use the
 *  screen with a real inventory behind it — the same instrument every other unmeasured number
 *  in this app is waiting on. */
export const SEARCH_DEBOUNCE_MS = 200

export type SearchState = {
  /** What is in the box, unmodified. Not trimmed and not lower-cased: it is what the person
   *  typed, and a field rendering it back has to show that. */
  query: string
  setQuery: (next: string) => void

  /** The server's answer to the most recent query it was asked, or null before there is one —
   *  including after a failure, and after the query is emptied. */
  results: SearchResult | null

  /** Re-run the CURRENT query without touching what is in the box.
   *
   *  For a screen that writes. A sale changes the SKU's `on_hand` and `listed` counts, and
   *  neither is derivable from the copy rows already on screen — so the header goes stale by
   *  one copy until something asks the server again. Calling this asks; nudging the query
   *  string would also ask, and would type into the owner's search field to do it. */
  reload: () => void

  /** True from the keystroke to the answer, debounce included. See the header. */
  loading: boolean

  /** A refusal as an owner-side screen draws it: the sentence it shows, and the code it prints
   *  small beneath. `server.ts:describeFailure` builds it and carries the server's own message
   *  verbatim — the Fulfiller's screens may not show one, and that is their caller's rule to
   *  keep, not this hook's. */
  failure: Failure | null
}

export function useSearch(options: { debounceMs?: number } = {}): SearchState {
  const { debounceMs = SEARCH_DEBOUNCE_MS } = options

  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [failure, setFailure] = useState<Failure | null>(null)

  /* RELOAD IS A COUNTER, NOT A REQUERY, and the distinction is the whole reason it exists.
   *
   * A screen that writes — marking a copy sold — needs the group header's `on_hand` and
   * `listed N of 4` to catch up, and those come off the SKU rather than off the copy rows,
   * so nothing in the response the screen already holds can be patched to show it. The
   * obvious workaround is to nudge the query string, and that is exactly what must not
   * happen: it puts text in a box the owner did not type, on a field they are mid-sentence
   * in. Bumping a counter the effect also depends on re-runs the same fetch for the same
   * query and leaves the input alone. */
  const [reloads, setReloads] = useState(0)

  useEffect(() => {
    const text = query.trim()

    /* An empty query is answered here rather than by the server. `GET /search` refuses one as
     * `query_required` — correctly, since a bare search returning the whole store is a denial
     * of service written by accident — and showing the owner that refusal for having deleted
     * his own text would be reporting a refusal he did not make. Trimmed, so a field holding
     * one space is empty too. */
    if (text === '') {
      setResults(null)
      setLoading(false)
      setFailure(null)
      return
    }

    setLoading(true)

    /* THE OUT-OF-ORDER GUARD IS THIS FLAG AND NOT A SEQUENCE NUMBER, and it is worth saying why
     * the simpler mechanism is sufficient. React runs this effect's cleanup before the next
     * run, so a query that changes while a request is in flight sets the in-flight run's `live`
     * to false on the way past — and a slow answer to `pika` arriving after a fast answer to
     * `pikachu` finds its own flag already down. The same flag covers unmount. A counter would
     * be a second thing to keep correct in exchange for a property this already has, and
     * `Inventory.tsx` established the idiom in this app. */
    let live = true

    const timer = window.setTimeout(() => {
      /* `.then(ok).catch(fail)`, NEVER `.then(ok, fail)`. The two-argument form does not
       * cover its own success handler, so a throw inside the first callback — a bad shape
       * reaching `setResults`, say — sails past the second one and lands nowhere. The
       * recorded symptom is in `Fulfillment.tsx`: "the screen sat on 'Getting the cards.'
       * for the rest of the morning with no failure shown and no control to press." Here it
       * would leave `loading` true forever and the search field spinning on a query that
       * had already come back. `app/eslint.config.js` bans the two-argument form outright. */
      search(text)
        .then((result) => {
          if (!live) return
          setResults(result)
          setFailure(null)
          setLoading(false)
        })
        .catch((err: unknown) => {
          if (!live) return
          /* Results cleared rather than left standing beside the failure. Two things on screen
           * — a list and a message saying the list could not be fetched — is a screen that
           * contradicts itself, and the list is the half that looks authoritative. Same choice
           * `Inventory.tsx` makes with its groups. */
          setResults(null)
          setFailure(describeFailure(err))
          setLoading(false)
        })
    }, debounceMs)

    return () => {
      live = false
      window.clearTimeout(timer)
    }
  }, [query, debounceMs, reloads])

  /* `useCallback` so a caller may hold it in a dependency array without re-arming a timer
   * on every render — `Inventory.tsx` reloads from inside a sale handler. */
  const reload = useCallback(() => setReloads((n) => n + 1), [])

  return { query, setQuery, results, loading, failure, reload }
}

/** A list the BROWSER already holds, narrowed by what is typed, by the one forgiving matcher in
 *  `kit/match.ts` (every word, any order, case, accents, punctuation and the zeros in front of
 *  a card number folded away). The store's own search above asks the server instead, and
 *  does not use this matcher.
 *
 *  `fieldsOf` says what each row DRAWS, because what the row shows is what the search must find
 *  (FLT-07). Keep it stable (a module-level function, or `useCallback`), or the list is
 *  filtered again on every render. */
export function useQueryFilter<T>(rows: readonly T[], query: string, fieldsOf: (row: T) => MatchFields): T[] {
  return useMemo(() => filterByQuery(rows, query, fieldsOf), [rows, query, fieldsOf])
}
