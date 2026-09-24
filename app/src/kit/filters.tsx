import { useId, useState } from 'react'
import type { ReactNode } from 'react'

import { Icon } from './Icon'
import { Chip } from './index'
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
 * after "filtered by" are built here, from `facets` and `value`, so a caller never writes that
 * sentence a second time in its own screen (data.specimens.tsx's `active` computation, done
 * once).
 *
 * A POPOVER ON THE DESK, A SHEET ON THE PHONE (the filtering review, gripe 5's own verdict).
 * `FilterChips` already opens each facet in the kit's own floating panel — that is the desktop
 * case. Below `--bn-filterbar-stack` (639px, `FilterChips`' own phone breakpoint) every facet,
 * the sort and the hide toggle move into ONE bottom sheet behind a single "Filters" trigger,
 * so a phone never has to lay out five controls of different widths in a row (FLT-24) and
 * opening it never pushes a card in the list underneath (D118) — a `Sheet` is an overlay, not
 * a thing anchored to where the list currently is. BOTH TREES ARE ALWAYS MOUNTED; CSS alone
 * (`@media`, `display: none`) decides which one is visible and, so, which one is in the tab
 * order — the same technique the shell's own rail and phone tab bar already use
 * (`App.css`). No `matchMedia`, no viewport read in this file. */

export type FilterBarSearch = {
  readonly query: string
  readonly onChange: (next: string) => void
  readonly placeholder?: string
  readonly label?: string
}

export type FilterBarSort<K extends string = string> = {
  readonly options: readonly SortOption<K>[]
  readonly value: SortValue<K>
  readonly onChange: (next: SortValue<K>) => void
  readonly label?: string
}

export type FilterBarHide = {
  readonly checked: boolean
  readonly onChange: (next: boolean) => void
  readonly label: string
  readonly count?: number
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
  /** The group's own label, for the facet row and the phone sheet's title. Defaults to
   *  "Filters". */
  readonly label?: string
  readonly className?: string
}

/** The words `FilterCount` reads after "filtered by": one per PICKED option, across every
 *  facet, in the facet order `facets` itself is given in. */
function activeWords(facets: readonly FilterFacet[], value: FilterValue): string[] {
  const words: string[] = []
  for (const facet of facets) {
    for (const picked of value[facet.key] ?? []) {
      const option = facet.options.find((one) => one.value === picked)
      words.push(option === undefined ? picked : typeof option.label === 'string' ? option.label : picked)
    }
  }
  return words
}

function activeFacetCount(facets: readonly FilterFacet[], value: FilterValue): number {
  return facets.filter((facet) => (value[facet.key] ?? []).length > 0).length
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
      {hide === undefined ? null : <HideToggle checked={hide.checked} onChange={hide.onChange} count={hide.count}>{hide.label}</HideToggle>}
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
  label = 'Filters',
  className,
}: FilterBarProps<K>) {
  const id = useId().replace(/:/g, '')
  const [sheetOpen, setSheetOpen] = useState(false)
  const active = activeFacetCount(facets, value)
  /* The badge on the phone trigger. `sort` has no notion of its own "default" here, so its
   *  first option stands in for one — a caller whose initial `sort.value` is not its own first
   *  option will see the badge count a sort that has not, from the owner's point of view,
   *  changed. The badge is a hint, not a source of truth: `count`'s "N of M" line is. */
  const otherActive = (sort !== undefined && sort.value.key !== sort.options[0]?.key ? 1 : 0) + (hide?.checked === true ? 1 : 0)

  return (
    <div className={['bn-filterbar', className].filter(Boolean).join(' ')} data-bn-filterbar>
      <div className="bn-filterbar-controls">
        {search === undefined ? null : (
          <div className="bn-filterbar-search">
            <SearchField
              persona="owner"
              value={search.query}
              onChange={search.onChange}
              placeholder={search.placeholder}
              label={search.label}
              controlHeight="bar"
            />
          </div>
        )}

        {/* THE WIDE ROW: every facet, the sort and the hide toggle inline. Hidden below
            `--bn-filterbar-stack` (data-driven by CSS alone; see the file header). */}
        <div className="bn-filterbar-row" role="group" aria-label={label}>
          <FiltersAndSort facets={facets} value={value} onChange={onChange} sort={sort} hide={hide} label={label} />
        </div>

        {/* THE COMPACT ROW: one trigger, one sheet. Hidden at and above the same breakpoint. */}
        {facets.length > 0 || sort !== undefined || hide !== undefined ? (
          <div className="bn-filterbar-compact">
            <button
              type="button"
              className="bn-filterbar-trigger"
              aria-haspopup="dialog"
              aria-expanded={sheetOpen}
              data-active={active + otherActive > 0 ? 'true' : undefined}
              onClick={() => setSheetOpen(true)}
            >
              <Icon name="filter" size={14} />
              {label}
              {active + otherActive > 0 ? <span className="bn-filterbar-trigger-count">{active + otherActive}</span> : null}
            </button>
            <Sheet open={sheetOpen} onClose={() => setSheetOpen(false)} title={label} icon="filter">
              <div className="bn-filterbar-sheet-body" id={`${id}-sheet`}>
                <FiltersAndSort facets={facets} value={value} onChange={onChange} sort={sort} hide={hide} label={label} />
              </div>
            </Sheet>
          </div>
        ) : null}
      </div>

      <FilterCount
        shown={count.shown}
        total={count.total}
        noun={count.noun}
        filters={activeWords(facets, value)}
        onClear={active > 0 ? () => onChange({}) : undefined}
      />
    </div>
  )
}

/* ============================================================================================
 * HideToggle — one control for "hide or show a kind of row" (FLT-16: a black pill, a 13px
 * checkbox and a dimming chip were three shapes for the same idea on three screens).
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
  /** How many rows this hides, drawn on the pill itself (FLT-16: "with no count" was the
   *  defect on Orders' checkbox). Omit only when the count is not yet known. */
  readonly count?: number
  readonly children: ReactNode
  readonly className?: string
}) {
  return (
    <Chip
      pressed={checked}
      count={count}
      onClick={() => onChange(!checked)}
      className={['bn-hidetoggle', className].filter(Boolean).join(' ')}
      aria-label={typeof children === 'string' ? `${children}, ${checked ? 'on' : 'off'}` : undefined}
    >
      {children}
    </Chip>
  )
}

/* ============================================================================================
 * SortHeaderButton — a table column that sorts itself, the active one marked (FLT-19: "every
 * header carries a chevron; only `aria-sort` tells which column is active").
 * ============================================================================================ */

export function SortHeaderButton<K extends string>({
  sortKey,
  value,
  onChange,
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
  readonly align?: 'start' | 'end'
  readonly children: ReactNode
  readonly className?: string
}) {
  const active = value.key === sortKey
  const dir = active ? value.dir : undefined
  /* Already the active column: flip its direction. Any other column: start at `desc`, the same
   *  first direction `SortControl`'s own default (`data.tsx:SortOption.first`) picks. */
  const nextDir: 'asc' | 'desc' = active && value.dir === 'desc' ? 'asc' : 'desc'
  return (
    <button
      type="button"
      className={['bn-sortth', align === 'end' ? 'bn-sortth-end' : '', className].filter(Boolean).join(' ')}
      data-active={active ? 'true' : undefined}
      aria-sort={active ? (dir === 'asc' ? 'ascending' : 'descending') : 'none'}
      onClick={() => onChange({ key: sortKey, dir: nextDir })}
    >
      <span className="bn-sortth-label">{children}</span>
      <Icon name={dir === 'asc' ? 'chevronUp' : 'chevronDown'} size={12} className="bn-sortth-icon" />
    </button>
  )
}
