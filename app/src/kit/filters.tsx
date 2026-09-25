import { useId, useState } from 'react'
import type { ReactNode } from 'react'

import { Icon } from './Icon'
import { FailureNotice } from './index'
import { Sheet } from './overlay'
import { FilterChips, FilterCount, SortControl, type FilterFacet, type FilterValue, type SortOption, type SortValue } from './data'
import { SearchField } from '../SearchField'
import './filters.css'

/* THE ONE FILTER BAR (FLT-15, and the owner's gripes: game-then-set-then-rarity locked in one
 * order on Inventory, and Orders' filters "aren't even the same widths"). `kit/data.tsx`
 * already builds the pieces this composes — `Select`, `FilterChips`, `FilterCount`,
 * `SortControl`, one control height, the kit's own panel, never the OS menu. This file is the
 * ONE PLACE a screen puts them together, so a screen built tomorrow gets a filter bar by
 * calling `FilterBar` once rather than inventing its own toolbar row (FLT-24: five controls of
 * four widths in four rows).
 *
 * FilterBar DRAWS "N of M" BY CONSTRUCTION (FLT-13): `count` is a required prop, and the
 * `FilterCount` line under the controls is not something a caller can leave out. The words
 * after "filtered by" are built here, from the facets, the search and the hide toggle, so a
 * caller never writes that sentence a second time. The line is also the bar's ONE clear-all:
 * `FilterChips`' own "Clear all" is not drawn inside a FilterBar (filters.css), so two clear
 * presses never sit side by side, and its reserved slot leaves no blank band in the sheet.
 *
 * EVERY FACET TRIGGER IN ONE BAR IS ONE WIDTH (the orchestrator's call on the owner's gripe,
 * 2026-09-24): the widest any of them needs, in one shared grid track (filters.css). Each
 * trigger already holds the width of its widest value (`PickTrigger`'s sizer), so a pick
 * changes no width (D118).
 *
 * A POPOVER ON THE DESK, A SHEET IN A NARROW COLUMN. Below `--bn-filterbar-stack` of the BAR'S
 * OWN WIDTH (a container query, not the viewport: Inventory's rail is 268-300px wide on a
 * 1440px desk) every facet, the sort and the hide toggle move into ONE sheet behind a single
 * "Filters" trigger. Opening it never pushes a row underneath (D118): a `Sheet` is an overlay.
 * BOTH TREES ARE ALWAYS MOUNTED, and CSS alone decides which one is visible and so which one is
 * in the tab order. No `matchMedia`, no width read in this file. */

export type FilterBarSearch = {
  readonly query: string
  readonly onChange: (next: string) => void
  readonly placeholder?: string
  readonly label?: string
  /** `useSearch`'s `loading`: the answer on screen is not yet the answer to the text. */
  readonly loading?: boolean
  /** `useSearch`'s `failure`, drawn under the controls in the kit's one failure shape. */
  readonly failure?: { readonly code: string; readonly message: string; readonly kind?: 'refusal' | 'retry' } | null
  /** Ask again (`useSearch`'s `reload`), offered when the failure may pass on a second press. */
  readonly onRetry?: () => void
}

export type FilterBarSort<K extends string = string> = {
  readonly options: readonly SortOption<K>[]
  readonly value: SortValue<K>
  readonly onChange: (next: SortValue<K>) => void
  readonly label?: string
  /** The screen's own resting order. The phone trigger's badge counts the sort only when it
   *  differs from this. Defaults to the first option in its first direction. */
  readonly defaultValue?: SortValue<K>
}

export type FilterBarHide = {
  readonly checked: boolean
  readonly onChange: (next: boolean) => void
  readonly label: string
  readonly count?: number
  /** The screen's resting state. Hide sold is ON at rest (D132), so its badge and its Clear
   *  treat `true` as nothing changed. Default `false`. */
  readonly defaultChecked?: boolean
}

export type FilterBarCount = {
  readonly shown: number
  readonly total: number
  readonly noun?: { readonly one: string; readonly many: string }
}

export type FilterBarProps<K extends string = string> = {
  readonly facets: readonly FilterFacet[]
  readonly value: FilterValue
  readonly onChange: (next: FilterValue) => void
  readonly count: FilterBarCount
  readonly search?: FilterBarSearch
  readonly sort?: FilterBarSort<K>
  readonly hide?: FilterBarHide
  /** A screen's own control, drawn beside the search at every width: the rail's collapse
   *  press, a reload. One control, not a toolbar. */
  readonly beside?: ReactNode
  /** The group's own label, for the facet row and the phone sheet's title. Defaults to
   *  "Filters". */
  readonly label?: string
  readonly className?: string
}

/** The words `FilterCount` reads after "filtered by": one per PICKED option the facet really
 *  has, across every facet, in the order `facets` is given in. A value no option carries (a
 *  hand-edited URL) is never a word here. */
function facetWords(facets: readonly FilterFacet[], value: FilterValue): string[] {
  const words: string[] = []
  for (const facet of facets) {
    for (const picked of value[facet.key] ?? []) {
      const option = facet.options.find((one) => one.value === picked)
      if (option === undefined) continue
      words.push(typeof option.label === 'string' ? option.label : (option.text ?? option.value))
    }
  }
  return words
}

function activeFacetCount(facets: readonly FilterFacet[], value: FilterValue): number {
  return facets.filter((facet) => (value[facet.key] ?? []).some((picked) => facet.options.some((one) => one.value === picked))).length
}

function sortAtRest<K extends string>(sort: FilterBarSort<K>): SortValue<K> | null {
  if (sort.defaultValue !== undefined) return sort.defaultValue
  const first = sort.options[0]
  return first === undefined ? null : { key: first.key, dir: first.first ?? 'desc' }
}

function FiltersAndSort<K extends string>({
  facets,
  value,
  onChange,
  sort,
  hide,
  label,
}: {
  readonly facets: readonly FilterFacet[]
  readonly value: FilterValue
  readonly onChange: (next: FilterValue) => void
  readonly sort?: FilterBarSort<K>
  readonly hide?: FilterBarHide
  readonly label: string
}) {
  return (
    <>
      {facets.length > 0 ? <FilterChips facets={facets} value={value} onChange={onChange} label={label} /> : null}
      {sort === undefined ? null : <SortControl options={sort.options} value={sort.value} onChange={sort.onChange} label={sort.label} />}
      {hide === undefined ? null : (
        <HideToggle checked={hide.checked} onChange={hide.onChange} count={hide.count}>
          {hide.label}
        </HideToggle>
      )}
    </>
  )
}

export function FilterBar<K extends string = string>({
  facets,
  value,
  onChange,
  count,
  search,
  sort,
  hide,
  beside,
  label = 'Filters',
  className,
}: FilterBarProps<K>) {
  const id = useId().replace(/:/g, '')
  const [sheetOpen, setSheetOpen] = useState(false)
  const active = activeFacetCount(facets, value)

  const rest = sort === undefined ? null : sortAtRest(sort)
  const sortMoved = sort !== undefined && rest !== null && (sort.value.key !== rest.key || sort.value.dir !== rest.dir)
  const hideMoved = hide !== undefined && hide.checked !== (hide.defaultChecked ?? false)
  /* The badge on the compact trigger: what inside the SHEET differs from the screen at rest.
   *  A Hide sold that is on because it is on by default is not a change (D132). */
  const badge = active + (sortMoved ? 1 : 0) + (hideMoved ? 1 : 0)

  const typed = search?.query.trim() ?? ''
  /* THE COUNT LINE NAMES EVERYTHING THAT NARROWS THE LIST: each picked option, the search's
   *  own words, and the hide toggle while it hides at least one row. */
  const words = [
    ...facetWords(facets, value),
    ...(typed === '' ? [] : [`“${typed}”`]),
    ...(hide !== undefined && hide.checked && (hide.count ?? 1) > 0 ? [hide.label] : []),
  ]
  const clearable = active > 0 || typed !== '' || hideMoved
  const clearAll = () => {
    onChange({})
    if (typed !== '') search?.onChange('')
    if (hideMoved) hide?.onChange(hide.defaultChecked ?? false)
  }

  return (
    <div className={['bn-filterbar', className].filter(Boolean).join(' ')} data-bn-filterbar>
      <div className="bn-filterbar-controls">
        {search === undefined && beside === undefined ? null : (
          <div className="bn-filterbar-lead">
            {search === undefined ? null : (
              <div className="bn-filterbar-search">
                <SearchField
                  persona="owner"
                  value={search.query}
                  onChange={search.onChange}
                  placeholder={search.placeholder}
                  label={search.label}
                  controlHeight="bar"
                  busy={search.loading === true}
                />
              </div>
            )}
            {beside === undefined ? null : <div className="bn-filterbar-beside">{beside}</div>}
          </div>
        )}

        {/* THE WIDE ROW: every facet, the sort and the hide toggle inline. Hidden in a narrow
            bar (filters.css, a container query). */}
        <div className="bn-filterbar-row" role="group" aria-label={label}>
          <FiltersAndSort facets={facets} value={value} onChange={onChange} sort={sort} hide={hide} label={label} />
        </div>

        {/* THE COMPACT ROW: one trigger, one sheet. Hidden in a wide bar. */}
        {facets.length > 0 || sort !== undefined || hide !== undefined ? (
          <div className="bn-filterbar-compact">
            <button
              type="button"
              className="bn-filterbar-trigger"
              aria-haspopup="dialog"
              aria-expanded={sheetOpen}
              data-active={badge > 0 ? 'true' : undefined}
              onClick={() => setSheetOpen(true)}
            >
              <Icon name="filter" size={14} />
              {label}
              {badge > 0 ? <span className="bn-filterbar-trigger-count">{badge}</span> : null}
            </button>
            <Sheet open={sheetOpen} onClose={() => setSheetOpen(false)} title={label} icon="filter">
              <div className="bn-filterbar-sheet-body" id={`${id}-sheet`}>
                <FiltersAndSort facets={facets} value={value} onChange={onChange} sort={sort} hide={hide} label={label} />
              </div>
            </Sheet>
          </div>
        ) : null}
      </div>

      {search?.failure === undefined || search.failure === null ? null : (
        <FailureNotice failure={search.failure} title="The search did not answer." onRetry={search.onRetry} compact />
      )}

      <FilterCount shown={count.shown} total={count.total} noun={count.noun} filters={words} onClear={clearable ? clearAll : undefined} />
    </div>
  )
}

/* ============================================================================================
 * HideToggle — one control for "hide or show a kind of row" (FLT-16: a black pill, a 13px
 * checkbox and a dimming chip were three shapes for the same idea on three screens).
 *
 * QUIET (the filtering review, round 2): the pressed `Chip` filled the whole pill black in
 * light and white in dark, the heaviest object in any bar it sat in, for a state that is on by
 * default on Inventory (D132). This is a field-edged control of the bar's own height, with a
 * small check mark that fills with the accent when on — the same mark the pick list's
 * multi-choice rows draw. Its name is its words and its count ("Hide sold 8"); its state is
 * `aria-pressed` alone, never also a word in the name.
 * ============================================================================================ */

export function HideToggle({
  checked,
  onChange,
  count,
  children,
  className,
}: {
  readonly checked: boolean
  readonly onChange: (next: boolean) => void
  /** How many rows this hides, drawn on the control itself (FLT-16: "with no count" was the
   *  defect on Orders' checkbox). A zero is drawn. Omit only when the count is not yet known. */
  readonly count?: number
  readonly children: ReactNode
  readonly className?: string
}) {
  return (
    <button
      type="button"
      className={['bn-hidetoggle', className].filter(Boolean).join(' ')}
      aria-pressed={checked}
      onClick={() => onChange(!checked)}
    >
      <span className="bn-hidetoggle-mark" aria-hidden="true">
        <Icon name="check" size={11} strokeWidth={3} />
      </span>
      <span className="bn-hidetoggle-label">{children}</span>
      {count === undefined ? null : <span className="bn-hidetoggle-count">{Number.isFinite(count) ? Math.round(count).toLocaleString('en-US') : '—'}</span>}
    </button>
  )
}

/* ============================================================================================
 * SortHeader — a table column that sorts itself, the active one marked (FLT-19: "every header
 * carries a chevron; only `aria-sort` tells which column is active").
 *
 * IT IS THE `<th>` ITSELF, with the press inside it. `aria-sort` belongs on the column header
 * (WAI-ARIA: the `columnheader` role), never on a button, where axe calls it an attribute the
 * role does not support. Only the ACTIVE column carries it.
 * ============================================================================================ */

export function SortHeader<K extends string>({
  sortKey,
  value,
  onChange,
  first = 'desc',
  align = 'start',
  children,
  className,
}: {
  readonly sortKey: K
  readonly value: SortValue<K>
  /** A sort press RE-SORTS AT ONCE (FLT-01, amending D209's freeze during a walk to the sort
   *  toggle only — the freeze still stops a SALE from re-ranking the list, never a press the
   *  owner made on purpose). */
  readonly onChange: (next: SortValue<K>) => void
  /** The direction this column starts in on its first press: a name reads A to Z (`asc`), a
   *  price or a date the largest first (`desc`, the default) — `SortOption.first`'s rule. */
  readonly first?: 'asc' | 'desc'
  readonly align?: 'start' | 'end'
  readonly children: ReactNode
  readonly className?: string
}) {
  const active = value.key === sortKey
  const dir = active ? value.dir : undefined
  /* Already the active column: flip its direction. Any other column: its own first direction. */
  const nextDir: 'asc' | 'desc' = active ? (value.dir === 'desc' ? 'asc' : 'desc') : first
  return (
    <th
      scope="col"
      className={['bn-sortth-cell', align === 'end' ? 'bn-sortth-cell-end' : '', className].filter(Boolean).join(' ')}
      aria-sort={active ? (dir === 'asc' ? 'ascending' : 'descending') : undefined}
    >
      <button
        type="button"
        className={['bn-sortth', align === 'end' ? 'bn-sortth-end' : ''].filter(Boolean).join(' ')}
        data-active={active ? 'true' : undefined}
        onClick={() => onChange({ key: sortKey, dir: nextDir })}
      >
        <span className="bn-sortth-label">{children}</span>
        <Icon name={dir === 'asc' ? 'chevronUp' : 'chevronDown'} size={12} className="bn-sortth-icon" />
      </button>
    </th>
  )
}
