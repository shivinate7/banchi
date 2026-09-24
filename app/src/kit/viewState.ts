import { useCallback } from 'react'
import { useSyncExternalStore } from 'react'

import type { FilterValue, SortValue } from './data'

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

function queryOf(hash: string): URLSearchParams {
  return new URLSearchParams(hash.split('?')[1] ?? '')
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

/** One string field, in the URL. `defaultValue` never itself appears in the query string, so a
 *  screen at its default state has a clean URL. */
export function useViewParam(key: string, defaultValue = ''): readonly [string, (next: string) => void] {
  const query = useViewQuery()
  const value = query.get(key) ?? defaultValue
  const set = useCallback((next: string) => patchViewQuery({ [key]: next === defaultValue ? null : next }), [key, defaultValue])
  return [value, set] as const
}

/** One flag, as `1` or absent (never `0`, so a screen at its default carries no key). */
export function useViewFlag(key: string, defaultValue = false): readonly [boolean, (next: boolean) => void] {
  const query = useViewQuery()
  const raw = query.get(key)
  const value = raw === null ? defaultValue : raw === '1'
  const set = useCallback((next: boolean) => patchViewQuery({ [key]: next === defaultValue ? null : next ? '1' : null }), [key, defaultValue])
  return [value, set] as const
}

/** A `FilterBar`'s whole `FilterValue`, one repeated query key per facet
 *  (`?game=pokemon&game=riftbound&rarity=rare`). `facetKeys` is every facet the bar may ever
 *  carry — pass a stable array (a module-level constant, or the same array reference every
 *  render), since a facet key this list leaves out is a key this hook never reads or writes. */
export function useFacetParams(facetKeys: readonly string[]): readonly [FilterValue, (next: FilterValue) => void] {
  const query = useViewQuery()
  const value: Record<string, readonly string[]> = {}
  for (const key of facetKeys) {
    const picked = query.getAll(key)
    if (picked.length > 0) value[key] = picked
  }
  /* NOT `useCallback`: its dependency would be `facetKeys` itself, an array a caller may pass
   *  as a fresh literal every render, so memoising here would either miss a change (a stale
   *  key list) or re-create on every render anyway (a join of it as the dep) — no cheaper than
   *  the plain function below, and this hook does nothing costly enough to memoise for. */
  const set = (next: FilterValue): void => {
    const patch: Record<string, readonly string[] | null> = {}
    for (const key of facetKeys) {
      const picked = next[key]
      patch[key] = picked !== undefined && picked.length > 0 ? picked : null
    }
    patchViewQuery(patch)
  }
  return [value, set] as const
}

/** A `SortControl`'s value, as two keys (`?sort=name&dir=asc`) — the same shape `#/revenue`
 *  already reads (D217). Neither key appears while the sort sits at `defaultValue`. */
export function useSortParam<K extends string>(
  defaultValue: SortValue<K>,
  keys: { readonly sort?: string; readonly dir?: string } = {},
): readonly [SortValue<K>, (next: SortValue<K>) => void] {
  const sortKey = keys.sort ?? 'sort'
  const dirKey = keys.dir ?? 'dir'
  const query = useViewQuery()
  const rawKey = query.get(sortKey)
  const key = (rawKey === null ? defaultValue.key : (rawKey as K)) as K
  const rawDir = query.get(dirKey)
  const dir = rawDir === 'asc' || rawDir === 'desc' ? rawDir : defaultValue.dir
  const set = (next: SortValue<K>): void => {
    const atDefault = next.key === defaultValue.key
    patchViewQuery({
      [sortKey]: atDefault ? null : next.key,
      [dirKey]: atDefault && next.dir === defaultValue.dir ? null : next.dir,
    })
  }
  return [{ key, dir }, set] as const
}
