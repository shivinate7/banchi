import type { FilterFacet, FilterValue } from './data'

/* THE FACET COUNTS, COMPUTED ONE WAY (the filtering review, round 2: "each option shows a count
 * under the OTHER active filters"). A screen hands over its rows, its facets and what is picked,
 * and gets its facets back with every option's `count` filled in. So no screen writes that loop
 * again, and no screen gets it subtly wrong.
 *
 * THE RULE, in full:
 *  - Inside one facet, several picks are OR: `Pokémon` or `Riftbound`.
 *  - Across facets, picks are AND: a Pokémon card AND a Rare one.
 *  - An option's count is how many rows the list would show if this facet held that option
 *    alone, with every OTHER facet as it is now, and the screen's own `keep` (its search, its
 *    Hide sold) applied. So picking a game changes the counts in Set and Rarity, and never the
 *    counts in Game itself: a count answers "what would I see if I picked this instead".
 *  - A row can carry several values for one facet (a card in two boxes). It counts once under
 *    each of them, and it passes a facet when ANY of its values is picked.
 *  - A zero is a count like any other. It is drawn, never hidden (FLT-10).
 *
 * `withCounts` is the same result for a screen whose counts come from the server: it copies the
 * server's figures onto the options, and it writes a zero where the server named none.
 *
 * PURE. No React: the same function answers in a spec and on a screen. */

/** What one row carries for one facet: one value, several, or none. */
export type FacetValueOf<R> = (row: R, facetKey: string) => string | readonly string[] | null | undefined

function valuesOf<R>(row: R, key: string, valueOf: FacetValueOf<R>): readonly string[] {
  const raw = valueOf(row, key)
  if (raw === null || raw === undefined) return []
  return typeof raw === 'string' ? [raw] : raw
}

/** The picks of `value` that are real, per facet: unknown facets are ignored. */
function activePicks(facets: readonly FilterFacet[], value: FilterValue): Map<string, ReadonlySet<string>> {
  const active = new Map<string, ReadonlySet<string>>()
  for (const facet of facets) {
    const picked = value[facet.key] ?? []
    if (picked.length > 0) active.set(facet.key, new Set(picked))
  }
  return active
}

function passes<R>(row: R, active: Map<string, ReadonlySet<string>>, skip: string | null, valueOf: FacetValueOf<R>): boolean {
  for (const [key, picked] of active) {
    if (key === skip) continue
    if (!valuesOf(row, key, valueOf).some((one) => picked.has(one))) return false
  }
  return true
}

/** The rows every active facet lets through, and `keep` too, in their own order. */
export function filterRows<R>(
  rows: readonly R[],
  facets: readonly FilterFacet[],
  value: FilterValue,
  valueOf: FacetValueOf<R>,
  keep?: (row: R) => boolean,
): R[] {
  const active = activePicks(facets, value)
  return rows.filter((row) => (keep === undefined || keep(row)) && passes(row, active, null, valueOf))
}

/** `facets`, each option's `count` computed from `rows` under the OTHER active facets and
 *  `keep`. The facets and options keep their order and every other field. */
export function countFacets<R>(
  rows: readonly R[],
  facets: readonly FilterFacet[],
  value: FilterValue,
  valueOf: FacetValueOf<R>,
  keep?: (row: R) => boolean,
): FilterFacet[] {
  const active = activePicks(facets, value)
  const kept = keep === undefined ? rows : rows.filter(keep)
  return facets.map((facet) => {
    const tally = new Map<string, number>()
    for (const row of kept) {
      if (!passes(row, active, facet.key, valueOf)) continue
      for (const one of new Set(valuesOf(row, facet.key, valueOf))) tally.set(one, (tally.get(one) ?? 0) + 1)
    }
    return { ...facet, options: facet.options.map((option) => ({ ...option, count: tally.get(option.value) ?? 0 })) }
  })
}

/** Counts the server computed, by facet key then option value, copied onto `facets`. An option
 *  the server did not name counts zero. */
export function withCounts(
  facets: readonly FilterFacet[],
  counts: Readonly<Record<string, Readonly<Record<string, number>>>>,
): FilterFacet[] {
  return facets.map((facet) => ({
    ...facet,
    options: facet.options.map((option) => ({ ...option, count: counts[facet.key]?.[option.value] ?? 0 })),
  }))
}
