import { useId, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import { Icon } from './Icon'
import { FailureNotice, IconButton } from './index'
import { Popover, Sheet } from './overlay'
import { atRest, restPicks } from './viewState'
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
 * `FilterCount` line under the controls is always drawn, unless `count.quietAtRest` is set and
 * nothing narrows the list. The words
 * after "filtered by" are built here, from the facets, the search and the hide toggle, so a
 * caller never writes that sentence a second time. The line is also the bar's ONE clear-all:
 * `FilterChips`' own "Clear all" is not drawn inside a FilterBar (filters.css), so two clear
 * presses never sit side by side, and its reserved slot leaves no blank band in the sheet.
 *
 * ONE LINE, AT EVERY WIDTH (the owner, 2026-09-24, D270): "i question whether
 * they deserve all that real estate frankly it's egregious i imagined we had a plan to tighten
 * them up immensely". A filter bar is search plus one "Filters" trigger with a count badge.
 * Every facet, the sort and the hide toggle live behind that one press — never inline, at any
 * width. This SUPERSEDES the bar's earlier width-driven layout (a container query that showed
 * every facet inline above 480px of the bar's own width, and folded them below it): that
 * inline row is gone, in every direction, not only the narrow one.
 *
 * `compact` PICKS THE OVERLAY, NEVER WHETHER THERE IS ONE (default `'popover'`,
 * D270): `'popover'` opens a small floating panel anchored to the trigger (`kit/overlay`'s
 * `Popover`), the shape a desk press expects. `'sheet'` opens the kit's `Sheet` instead — a
 * phone's own thumb reach, which `BoxBrowse` (the inventory lane) passes explicitly
 * (`compact={phone ? 'sheet' : 'popover'}`) because a floating panel is the wrong shape once a
 * screen is phone width. No caller needs a third value: nothing here reads `matchMedia` or a
 * container query any more — the CALLER decides the shape, once, from what it already knows
 * about its own width. */

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
  /** The screen's resting state. Hide sold is ON at rest (D132), so its badge, its Clear and
   *  the count line's "filtered by" words all skip it while it stays `true`: only a change from
   *  this value is marked. Default `false`. */
  readonly defaultChecked?: boolean
}

export type FilterBarCount = {
  readonly shown: number
  readonly total: number
  readonly noun?: { readonly one: string; readonly many: string }
  /** The caller already says the total elsewhere (the search placeholder): draw the line only
   *  once something narrows the list, where it carries the "filtered by" words and the clear. */
  readonly quietAtRest?: boolean
}

export type FilterBarProps<K extends string = string> = {
  readonly facets: readonly FilterFacet[]
  readonly value: FilterValue
  readonly onChange: (next: FilterValue) => void
  readonly count: FilterBarCount
  readonly search?: FilterBarSearch
  readonly sort?: FilterBarSort<K>
  /** One hide toggle, or several (Orders: unpullable and unknown). */
  readonly hide?: FilterBarHide | readonly FilterBarHide[]
  /** A screen's own control, drawn beside the search at every width: the rail's collapse
   *  press, a reload. One control, not a toolbar. */
  readonly beside?: ReactNode
  /** A screen's own press for the rows the count counts (Orders' Walk), drawn after the Filters
   *  trigger and just before the count line. The count is last, so a count that changes width
   *  moves nothing. One control, not a toolbar. */
  readonly action?: ReactNode
  /** The group's own label, for the facet row and the phone sheet's title. Defaults to
   *  "Filters". */
  readonly label?: string
  /** WHICH OVERLAY the "Filters" trigger opens — never whether it opens one
   *  (D270, the owner, 2026-09-24): `'popover'` (the default) is a small panel anchored to
   *  the trigger, right for a desk press. `'sheet'` is the kit's full sheet, right for a
   *  phone's thumb reach — pass it explicitly when the screen already knows its own width is
   *  phone-sized (`compact={phone ? 'sheet' : 'popover'}`, the inventory lane's own call). */
  readonly compact?: 'popover' | 'sheet'
  /** A write is in flight: the trigger cannot be pressed and an open overlay closes. The one
   *  home for a screen's own busy gate, so no caller hand-rolls a second. */
  readonly disabled?: boolean
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
  return facets.filter((facet) => !atRest(facet, value[facet.key])).length
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
  readonly hide: readonly FilterBarHide[]
  readonly label: string
}) {
  return (
    <>
      {facets.length > 0 ? <FilterChips facets={facets} value={value} onChange={onChange} label={label} /> : null}
      {sort === undefined ? null : <SortControl options={sort.options} value={sort.value} onChange={sort.onChange} label={sort.label} />}
      {hide.map((one) => (
        <HideToggle key={one.label} checked={one.checked} onChange={one.onChange} count={one.count}>
          {one.label}
        </HideToggle>
      ))}
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
  hide: hideProp,
  beside,
  action,
  label = 'Filters',
  compact = 'popover',
  disabled = false,
  className,
}: FilterBarProps<K>) {
  const id = useId().replace(/:/g, '')
  const hides: readonly FilterBarHide[] = hideProp === undefined ? [] : Array.isArray(hideProp) ? hideProp : [hideProp as FilterBarHide]
  const [overlayOpen, setOverlayOpen] = useState(false)
  const trigger = useRef<HTMLButtonElement>(null)
  const active = activeFacetCount(facets, value)

  const rest = sort === undefined ? null : sortAtRest(sort)
  const sortMoved = sort !== undefined && rest !== null && (sort.value.key !== rest.key || sort.value.dir !== rest.dir)
  const hidesMoved = hides.filter((one) => one.checked !== (one.defaultChecked ?? false))
  const hideMoved = hidesMoved.length > 0
  /* The badge on the compact trigger: what inside the SHEET differs from the screen at rest.
   *  A Hide sold that is on because it is on by default is not a change (D132). */
  const badge = active + (sortMoved ? 1 : 0) + hidesMoved.length

  const typed = search?.query.trim() ?? ''
  /* THE COUNT LINE NAMES EVERYTHING THAT NARROWS THE LIST: each picked option, the search's
   *  own words, and a hide toggle while it hides at least one row, unless it sits at its
   *  `defaultChecked` (a resting state is not a narrowing the reader chose). */
  const words = [
    ...facetWords(facets, value),
    ...(typed === '' ? [] : [`“${typed}”`]),
    ...hides.filter((one) => one.checked && !(one.defaultChecked ?? false) && (one.count ?? 1) > 0).map((one) => one.label),
  ]
  const clearable = active > 0 || typed !== '' || hideMoved
  const clearAll = () => {
    onChange(Object.fromEntries(facets.map((facet) => [facet.key, restPicks(facet)])))
    if (typed !== '') search?.onChange('')
    for (const one of hidesMoved) one.onChange(one.defaultChecked ?? false)
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

        {/* ONE LINE, ALWAYS: one trigger, one overlay (D270). No wide inline
            row exists any more, at any width. */}
        {facets.length > 0 || sort !== undefined || hides.length > 0 ? (
          <div className="bn-filterbar-compact">
            <IconButton
              ref={trigger}
              icon="filter"
              label={label}
              /* The badge is aria-hidden (D118: its arrival moves nothing, kit.css), so the
                 active count only reaches a screen reader through `name` — round 2's own
                 finding: before IconButton, the count sat in the button's own text. */
              name={badge > 0 ? `${label}, ${badge} on` : label}
              badge={badge > 0 ? badge : undefined}
              /* Sized to the field beside it through the SAME inline `style` IconButton already
                 merges a caller's `style` into — never a CSS override (FLT-24), the same pattern
                 `SortControl`'s own direction button uses. Without it the trigger sat at its
                 default (smaller) size: 28px beside a 34px search field, under the 40px thumb
                 floor at 390 (the orders lane's own finding, ux/orders 555d6b62). */
              style={{ width: 'var(--bn-control-h)', height: 'var(--bn-control-h)' }}
              className="bn-filterbar-trigger"
              aria-haspopup="dialog"
              aria-expanded={overlayOpen && !disabled}
              disabled={disabled}
              onClick={() => setOverlayOpen(true)}
            />
            {compact === 'sheet' ? (
              <Sheet open={overlayOpen && !disabled} onClose={() => setOverlayOpen(false)} title={label} icon="filter">
                <div className="bn-filterbar-sheet-body" id={`${id}-sheet`}>
                  <FiltersAndSort facets={facets} value={value} onChange={onChange} sort={sort} hide={hides} label={label} />
                </div>
              </Sheet>
            ) : (
              <Popover open={overlayOpen && !disabled} onClose={() => setOverlayOpen(false)} anchor={trigger} label={label} className="bn-filterbar-popover">
                <div className="bn-filterbar-sheet-body" id={`${id}-sheet`}>
                  <FiltersAndSort facets={facets} value={value} onChange={onChange} sort={sort} hide={hides} label={label} />
                </div>
              </Popover>
            )}
          </div>
        ) : null}
        {action === undefined || action === null ? null : <div className="bn-filterbar-action">{action}</div>}
      </div>

      {search?.failure === undefined || search.failure === null ? null : (
        <FailureNotice failure={search.failure} title="The search did not answer." onRetry={search.onRetry} compact />
      )}

      {count.quietAtRest === true && words.length === 0 && count.shown === count.total ? null : (
        <FilterCount shown={count.shown} total={count.total} noun={count.noun} filters={words} onClear={clearable ? clearAll : undefined} />
      )}
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
      {count === undefined ? null : <span className="bn-hidetoggle-count bn-live-count">{Number.isFinite(count) ? Math.round(count).toLocaleString('en-US') : '—'}</span>}
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
  rest,
  grid = false,
  children,
  className,
}: {
  readonly sortKey: K
  readonly value: SortValue<K>
  /** A sort press RE-SORTS AT ONCE (FLT-01, amending D296's freeze during a walk to the sort
   *  toggle only — the freeze still stops a SALE from re-ranking the list, never a press the
   *  owner made on purpose). */
  readonly onChange: (next: SortValue<K>) => void
  /** The direction this column starts in on its first press: a name reads A to Z (`asc`), a
   *  price or a date the largest first (`desc`, the default) — `SortOption.first`'s rule. */
  readonly first?: 'asc' | 'desc'
  readonly align?: 'start' | 'end'
  /** A THREE-STATE CYCLE: given, a press on the active column's second direction returns to this
   *  value (the list's default order) instead of flipping back, so the cycle is first direction,
   *  the other direction, then `rest`. Omitted, a press flips the direction (the two-state cycle). */
  readonly rest?: SortValue<K>
  /** GRID-CAPTION MODE, for a `display: grid` caption row (give that row `role="row"`): the cell is a
   *  `columnheader` span, not a `<th>`, it carries `aria-sort` always (`none` when inactive), the
   *  press is the caption's own type at the thumb floor, and the direction mark has its slot at all
   *  times and draws only while active, so a press moves and resizes nothing (D313). */
  readonly grid?: boolean
  readonly children: ReactNode
  readonly className?: string
}) {
  const active = value.key === sortKey
  const dir = active ? value.dir : undefined
  /* Already the active column: flip its direction, or leave the cycle at `rest`. Any other column: its own first direction. */
  const press = (): void => {
    if (!active) onChange({ key: sortKey, dir: first })
    else if (rest !== undefined && value.dir !== first) onChange(rest)
    else onChange({ key: sortKey, dir: value.dir === 'desc' ? 'asc' : 'desc' })
  }
  const sorted = dir === undefined ? (grid ? 'none' : undefined) : dir === 'asc' ? 'ascending' : 'descending'
  const classes = ['bn-sortth-cell', align === 'end' ? 'bn-sortth-cell-end' : '', className].filter(Boolean).join(' ')
  const button = (
    <button
      type="button"
      className={['bn-sortth', align === 'end' ? 'bn-sortth-end' : '', grid ? 'bn-sortth-grid' : ''].filter(Boolean).join(' ')}
      data-active={active ? 'true' : undefined}
      onClick={press}
    >
      <span className="bn-sortth-label">
        {children}
        {grid ? <span className="bn-sortth-box" aria-hidden="true" /> : null}
      </span>
      {grid ? (
        <span className="bn-sortth-mark">{active ? <Icon name={dir === 'asc' ? 'chevronUp' : 'chevronDown'} size={12} /> : null}</span>
      ) : (
        <Icon name={dir === 'asc' ? 'chevronUp' : 'chevronDown'} size={12} className="bn-sortth-icon" />
      )}
    </button>
  )
  return grid ? (
    <span role="columnheader" className={classes} aria-sort={sorted}>
      {button}
    </span>
  ) : (
    <th scope="col" className={classes} aria-sort={sorted}>
      {button}
    </th>
  )
}
