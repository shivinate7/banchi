import { useCallback, useMemo, useSyncExternalStore } from 'react'

import type { FilterFacet, FilterValue, SortOption, SortValue } from './data'

/* A SCREEN'S FILTER, SORT, SEARCH AND HIDE STATE LIVES IN THE URL, ONE WAY, EVERYWHERE
 * (D-view-state-in-url, the owner's ruling 2026-09-23: "in the URL on every screen (link,
 * bookmark and back restore the view)").
 *
 * FLT-11 found five different answers on seven screens: Sales kept everything in the URL,
 * Orders kept some of it in `localStorage` and forgot the rest, Pricing forgot its own run
 * scope on reload, and Review, Graveyard and Shipping kept nothing at all. This file is the
 * one place that question is answered from here on: every value this module writes lives in
 * the query string of the screen's own hash (`#/inventory?game=pokemon&game=riftbound`), which
 * a reload re-reads, a copied link carries whole, and a route change (`go()` in `App.tsx`, a
 * push) leaves behind for the BACK button to return to.
 *
 * REPEATED KEYS, NEVER A JOINED STRING (`?game=pokemon&game=riftbound`, never
 * `?game=pokemon,riftbound`). A person can read a URL like this and edit it by hand, and it
 * never collides with a value that itself contains the joining character.
 *
 * `history.replaceState`, NEVER `pushState`, FOR A WRITE THIS MODULE MAKES. A filter picked, a
 * column sorted or a letter typed into a search field is not a new PLACE to visit; it is the
 * screen the owner is already looking at, filled in further. Pushing a history entry per
 * keystroke would make the back button retype the owner's own search one character at a time.
 * What gives Back somewhere real to land on is the PATH change a screen link already makes
 * (`App.tsx:go`, which assigns `location.hash` and so pushes): the query string this module
 * wrote onto the hash before that press travels with it into history right there.
 *
 * ONE INTERNAL STORE, READ BY `useSyncExternalStore` — the same idiom `kit/sheets.ts` already
 * uses for state that is not React's own. `replaceState` does not fire `hashchange`, so every
 * write here also notifies this module's own listeners; an external nav (Back, Forward, a
 * typed URL) still arrives through the real `hashchange` event, which this module also
 * subscribes to. */

const listeners = new Set<() => void>()

function emit(): void {
  for (const listener of listeners) listener()
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  window.addEventListener('hashchange', listener)
  return () => {
    listeners.delete(listener)
    window.removeEventListener('hashchange', listener)
  }
}

function pathOf(hash: string): string {
  return hash.replace(/^#/, '').split('?')[0] ?? '/'
}

/* ============================================================================================
 * THE URL IS TYPED BY HAND, SO IT IS READ AS UNTRUSTED (the filtering review, round 2). A link
 * the owner edited, pasted half of, or kept from an older build can carry a value no option
 * has, a second value for a single-choice facet, the same value twice, a sort key that no
 * longer exists, or a broken `%` escape. Every reader below takes from the URL what it can
 * prove and drops the rest. It never WRITES the correction back: reading a view never changes
 * the URL, only a press does.
 * ============================================================================================ */

/** One `key=value` pair, decoded, or null when its escape is malformed (`q=%E0%A4%A`).
 *  `URLSearchParams` decodes that into U+FFFD replacement characters, and a search field would
 *  show them. A pair that cannot be decoded is IGNORED instead. */
function decodePair(pair: string): readonly [string, string] | null {
  const at = pair.indexOf('=')
  const rawKey = at === -1 ? pair : pair.slice(0, at)
  const rawValue = at === -1 ? '' : pair.slice(at + 1)
  try {
    return [decodeURIComponent(rawKey.replace(/\+/g, ' ')), decodeURIComponent(rawValue.replace(/\+/g, ' '))]
  } catch {
    return null
  }
}

/** A hash's query string: every well-formed pair, in order. Every malformed one is dropped. */
export function parseViewQuery(queryString: string): URLSearchParams {
  const out = new URLSearchParams()
  for (const pair of queryString.split('&')) {
    if (pair === '') continue
    const decoded = decodePair(pair)
    if (decoded === null || decoded[0] === '') continue
    out.append(decoded[0], decoded[1])
  }
  return out
}

function queryOf(hash: string): URLSearchParams {
  const at = hash.indexOf('?')
  return parseViewQuery(at === -1 ? '' : hash.slice(at + 1))
}

/** A flag's raw value: `1` is on, `0` is off, and anything else (absent, `yes`, empty) is the
 *  default. */
export function readFlag(raw: string | null, defaultValue: boolean): boolean {
  if (raw === '1') return true
  if (raw === '0') return false
  return defaultValue
}

/** What a flag writes. At its default it writes NO key, so a screen at rest has a clean URL.
 *  Away from the default it writes `1` or `0` — never `null` for false: a flag whose default is
 *  `true` (Hide sold, D132) turned off must say so, or the next read finds no key and turns it
 *  back on. */
export function writeFlag(next: boolean, defaultValue: boolean): string | null {
  if (next === defaultValue) return null
  return next ? '1' : '0'
}

/** A facet bar's value, read against the facets it may hold. A value no option carries is
 *  dropped. A value given twice is kept once, in its first place. A single-choice facet keeps
 *  its first value only. A key this list does not name is never read. */
export function readFacets(query: URLSearchParams, facets: readonly FilterFacet[]): FilterValue {
  const value: Record<string, readonly string[]> = {}
  for (const facet of facets) {
    const known = new Set(facet.options.map((option) => option.value))
    const picked: string[] = []
    for (const one of query.getAll(facet.key)) {
      if (!known.has(one) || picked.includes(one)) continue
      picked.push(one)
    }
    const kept = facet.multiple === false ? picked.slice(0, 1) : picked
    if (kept.length > 0) value[facet.key] = kept
  }
  return value
}

/** A sort, read against its options. A key no option carries falls back to `defaultValue`. A
 *  direction that is neither `asc` nor `desc` falls back to the key's own first direction
 *  (`SortOption.first`), then to the default's. */
export function readSort<K extends string>(
  rawKey: string | null,
  rawDir: string | null,
  defaultValue: SortValue<K>,
  options?: readonly SortOption<K>[],
): SortValue<K> {
  const known = rawKey !== null && (options === undefined || options.some((option) => option.key === rawKey))
  if (!known) return defaultValue
  const key = rawKey as K
  if (rawDir === 'asc' || rawDir === 'desc') return { key, dir: rawDir }
  if (key === defaultValue.key) return defaultValue
  return { key, dir: options?.find((option) => option.key === key)?.first ?? defaultValue.dir }
}

/** `useSyncExternalStore`'s snapshot MUST BE THE SAME REFERENCE while nothing has changed, or
 *  React re-renders every render trying to reconcile a "new" value that reads identically —
 *  an infinite loop, not merely a waste ("The result of getSnapshot should be cached", caught
 *  rendering the phone sheet during this file's own build). `queryOf` builds a fresh
 *  `URLSearchParams` from a string, so the cache is keyed on the hash STRING itself. */
let cachedHash: string | null = null
let cachedQuery: URLSearchParams = new URLSearchParams()

function snapshotQuery(): URLSearchParams {
  const hash = window.location.hash
  if (hash !== cachedHash) {
    cachedHash = hash
    cachedQuery = queryOf(hash)
  }
  return cachedQuery
}

function emptyQuery(): URLSearchParams {
  return new URLSearchParams()
}

/** The current route's query string, live: it changes on every `patchViewQuery` this module
 *  makes, and on `hashchange` (Back, Forward, a typed URL, a link elsewhere in the app). */
export function useViewQuery(): URLSearchParams {
  return useSyncExternalStore(subscribe, snapshotQuery, emptyQuery)
}

/** Merge `patch` into the CURRENT route's query string, keeping its path. A `null` value removes
 *  the key. A `readonly string[]` writes one entry per value, in that order — repeated keys, see
 *  the file header. Does nothing when the result is unchanged, so a caller may call this on
 *  every keystroke with no needless history churn. */
export function patchViewQuery(patch: Readonly<Record<string, string | readonly string[] | null>>): void {
  const hash = window.location.hash
  const path = pathOf(hash)
  const query = queryOf(hash)
  for (const [key, value] of Object.entries(patch)) {
    query.delete(key)
    if (value === null) continue
    if (Array.isArray(value)) for (const one of value) query.append(key, one)
    else query.set(key, value as string)
  }
  const qs = query.toString()
  const next = `#${path}${qs === '' ? '' : `?${qs}`}`
  if (next === hash) return
  window.history.replaceState(window.history.state as unknown, '', next)
  emit()
}

/** One string field, in the URL. A search's text is the usual one: `useViewParam('q')`, handed
 *  to `FilterBar`'s `search`. `defaultValue` never itself appears in the query string, so a
 *  screen at its default state has a clean URL. */
export function useViewParam(key: string, defaultValue = ''): readonly [string, (next: string) => void] {
  const query = useViewQuery()
  const value = query.get(key) ?? defaultValue
  const set = useCallback((next: string) => patchViewQuery({ [key]: next === defaultValue ? null : next }), [key, defaultValue])
  return [value, set] as const
}

/** One flag. At its default it writes no key. Away from it, `1` or `0` (`writeFlag`). */
export function useViewFlag(key: string, defaultValue = false): readonly [boolean, (next: boolean) => void] {
  const query = useViewQuery()
  const value = readFlag(query.get(key), defaultValue)
  const set = useCallback((next: boolean) => patchViewQuery({ [key]: writeFlag(next, defaultValue) }), [key, defaultValue])
  return [value, set] as const
}

/** A `FilterBar`'s whole `FilterValue`, one repeated query key per facet
 *  (`?game=pokemon&game=riftbound&rarity=rare`), read through `readFacets` against the SAME
 *  facets the bar draws. So a value the URL carries that no option has never reaches the bar,
 *  its count line or the rows. While a screen's options still load, a pick waits unread in the
 *  URL, and it appears when its option does. */
export function useFacetParams(facets: readonly FilterFacet[]): readonly [FilterValue, (next: FilterValue) => void] {
  const query = useViewQuery()
  /* One reference while the picks read the same, so a caller may put the value in a hook's
   *  dependency list. A facet list is often rebuilt on each render with fresh counts. */
  const signature = JSON.stringify(readFacets(query, facets))
  const value = useMemo(() => JSON.parse(signature) as FilterValue, [signature])
  const keys = facets.map((facet) => facet.key).join('\n')
  const set = useCallback(
    (next: FilterValue): void => {
      const patch: Record<string, readonly string[] | null> = {}
      for (const key of keys.split('\n')) {
        const picked = next[key]
        patch[key] = picked !== undefined && picked.length > 0 ? picked : null
      }
      patchViewQuery(patch)
    },
    [keys],
  )
  return [value, set] as const
}

/** A `SortControl`'s value, as two keys (`?sort=name&dir=asc`) — the same shape `#/revenue`
 *  already reads (D217). Neither key appears while the sort sits at `defaultValue`. Give
 *  `options`, and a key in the URL that no option has falls back to the default (`readSort`). */
export function useSortParam<K extends string>(
  defaultValue: SortValue<K>,
  keys: { readonly sort?: string; readonly dir?: string; readonly options?: readonly SortOption<K>[] } = {},
): readonly [SortValue<K>, (next: SortValue<K>) => void] {
  const sortKey = keys.sort ?? 'sort'
  const dirKey = keys.dir ?? 'dir'
  const query = useViewQuery()
  const read = readSort(query.get(sortKey), query.get(dirKey), defaultValue, keys.options)
  const key = read.key
  const dir = read.dir
  const set = (next: SortValue<K>): void => {
    const atDefault = next.key === defaultValue.key
    patchViewQuery({
      [sortKey]: atDefault ? null : next.key,
      [dirKey]: atDefault && next.dir === defaultValue.dir ? null : next.dir,
    })
  }
  return [{ key, dir }, set] as const
}
