import { useCallback, useEffect, useMemo, useState, type CSSProperties } from 'react'

import { describeFailure, getOrders, getStockMix, type Failure } from './server'
import type { StockMixPayload } from './types'
import {
  Count, EmptyState, FailureNotice, FilterChips, Money, Page, Segmented, Select, SortControl,
  type FilterFacet, type FilterValue, type PickOption, type SortOption, type SortValue,
} from './kit'
import { patchViewQuery, useFacetParams, useSortParam, useViewParam } from './kit/viewState'
import { absoluteDate } from './dates'
import {
  ALL, DIMENSIONS, MEASURES, soldShare, dimValue, optionCounts, orderValues, pivot,
  type DimId, type MeasureId, type MixFilters, type PivotRow, type SalePrice,
} from './mixPivot'
import { salesOf } from './revenueMath'
import './MixView.css'

/* THE MIX VIEW (`#/revenue?lens=mix`): a pivot over what the owner captured, holds and sold, to
 * decide what to capture next. A lens on Sales and never a route, so `ROUTES` is untouched.
 *
 * EVERY CONTROL IS A KIT CONTROL, AND EVERY PRESS IS A LOCAL RECOMPUTE. The cards come from one
 * read (`GET /stock/mix`) and the orders from the one Sales already reads; `mixPivot.ts` does the
 * rest in the browser. Nothing here fetches on a press.
 *
 * ALL STATE IS IN THE URL (`kit/viewState.ts`), written with `replaceState`, and a key at its rest
 * value is omitted, so the rest view is `?lens=mix`. A cell is not a link: drill-down, saved
 * layouts and CSV export are deferred. Revenue is gross, never profit (D214). */

const SALES_KEYS = ['period', 'q', 'month', 'from', 'to', 'view', 'sort', 'dir'] as const
const MIX_KEYS = ['by', 'across', 'measure', 'sort', 'dir', ...DIMENSIONS.map((dim) => dim.id)] as const

const nullPatch = (keys: readonly string[]) => Object.fromEntries(keys.map((key) => [key, null]))

/** `Sales | Mix`. Writing `lens=mix` drops Sales' own keys; going back drops Mix's. */
export function LensSwitch({ lens }: { readonly lens: 'sales' | 'mix' }) {
  return (
    <Segmented
      label="View"
      value={lens}
      options={[{ value: 'sales', label: 'Sales' }, { value: 'mix', label: 'Mix' }]}
      onChange={(next) => {
        if (next === lens) return
        patchViewQuery(next === 'mix' ? { ...nullPatch(SALES_KEYS), lens: 'mix' } : { ...nullPatch(MIX_KEYS), lens: null })
      }}
    />
  )
}

const REST_BY: DimId = 'set'
const REST_ACROSS: DimId = 'rarity'
const NONE = 'none'
const REST_MEASURE: MeasureId = 'pct'
const REST_SORT: SortValue = { key: 'name', dir: 'asc' }

const isDim = (raw: string): raw is DimId => DIMENSIONS.some((dim) => dim.id === raw)

/** `riftbound` reads `Riftbound`, `one_piece` reads `One Piece`. */
const gameWords = (id: string) => id.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())

const DASH = '—'

type Loaded = { readonly mix: StockMixPayload; readonly salePrice: SalePrice }

function useMix() {
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [tries, setTries] = useState(0)
  useEffect(() => {
    let alive = true
    Promise.all([getStockMix(), getOrders()])
      .then(([mix, orders]) => {
        if (alive) setLoaded({ mix, salePrice: soldShare(mix.cards, salesOf(orders.orders).sales) })
      })
      .catch((err) => {
        if (alive) setFailure(describeFailure(err))
      })
    return () => {
      alive = false
    }
  }, [tries])
  const retry = useCallback(() => {
    setFailure(null)
    setLoaded(null)
    setTries((n) => n + 1)
  }, [])
  return { loaded, failure, retry }
}

export function MixView() {
  const { loaded, failure, retry } = useMix()
  const cards = loaded?.mix.cards
  const salePrice = loaded?.salePrice

  const [byRaw, setBy] = useViewParam('by', REST_BY)
  const [acrossRaw, setAcross] = useViewParam('across', REST_ACROSS)
  const by: DimId = isDim(byRaw) ? byRaw : REST_BY
  const across: DimId | null = acrossRaw === NONE ? null : isDim(acrossRaw) ? acrossRaw : REST_ACROSS

  /* THE OPTIONS OF EVERY FILTER, from every card and never from the filtered ones, so a pick
     that leaves a list empty can still be undone from the list itself. */
  const prices = salePrice ?? {}
  const values = useMemo(() => {
    const out = {} as Record<DimId, string[]>
    for (const dim of DIMENSIONS) out[dim.id] = orderValues(dim.id, (cards ?? []).map((card) => dimValue(card, dim.id, prices)))
    return out
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cards, salePrice])
  const topGame = useMemo(() => {
    const tally = new Map<string, number>()
    for (const card of cards ?? []) tally.set(card.game, (tally.get(card.game) ?? 0) + 1)
    return [...tally.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0]?.[0] ?? null
  }, [cards])

  /* The counts need the picks, and the picks are read against the facets: read once against the
     option lists with no counts, then count, then hand the counted facets to the bar. */
  const bareFacets: FilterFacet[] = DIMENSIONS.map((dim) => ({
    key: dim.id,
    label: dim.label,
    countOnly: true,
    defaultPicks: dim.id === 'game' && topGame !== null ? [topGame] : undefined,
    options: values[dim.id]?.map((value) => ({ value, label: dim.id === 'game' ? gameWords(value) : value })) ?? [],
  }))
  const [picks, setPicks] = useFacetParams(bareFacets)
  const filters = picks as MixFilters
  const facets = useMemo<FilterFacet[]>(() => {
    return bareFacets.map((facet) => {
      const counts = optionCounts(cards ?? [], filters, facet.key as DimId, prices)
      return { ...facet, options: facet.options.map((option) => ({ ...option, count: counts[option.value] ?? 0 })) }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cards, salePrice, picks, topGame])

  /* MEASURES: several with no column split, one with a split. A pick that would leave two
     under a split is cut to the first, and an empty pick falls back to the rest measure. */
  const split = across !== null
  const measureFacet: FilterFacet = {
    key: 'measure',
    label: 'Measures',
    multiple: !split,
    defaultPicks: [REST_MEASURE],
    options: MEASURES.map((measure) => ({ value: measure.id, label: measure.label })),
  }
  const [measurePicks, setMeasurePicks] = useFacetParams([measureFacet])
  const picked = (measurePicks.measure ?? [REST_MEASURE]) as readonly MeasureId[]
  const measures: MeasureId[] = split ? [picked[0] ?? REST_MEASURE] : picked.length > 0 ? [...picked] : [REST_MEASURE]
  const changeMeasures = (next: FilterValue) => {
    const nextPicks = next.measure ?? []
    setMeasurePicks({ measure: nextPicks.length === 0 ? [REST_MEASURE] : split ? nextPicks.slice(-1) : nextPicks })
  }
  const changeAcross = (next: string) => {
    const nextAcross = next === NONE ? null : (next as DimId)
    setAcross(next)
    // Splitting with several measures rewrites the picks to one, never leaving two.
    if (nextAcross !== null && measures.length > 1) setMeasurePicks({ measure: [measures[0]!] })
  }

  const sortOptions: SortOption[] = [
    { key: 'name', label: 'Row name', asc: 'A to Z', desc: 'Z to A', first: 'asc' },
    ...measures.map((id) => ({ key: id, label: MEASURES.find((measure) => measure.id === id)!.label, first: 'desc' as const })),
  ]
  const [sort, setSort] = useSortParam<string>(REST_SORT, { options: sortOptions })

  const table = useMemo(() => {
    if (cards === undefined) return null
    return pivot(cards, { by, across, measure: measures, filters, salePrice: prices })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cards, salePrice, by, across, measures.join(), picks])

  const rows = useMemo(() => {
    if (table === null) return []
    const list = [...table.rows]
    if (sort.key === 'name') return sort.dir === 'desc' ? list.reverse() : list
    const column = across === null ? sort.key : ALL
    const at = (row: PivotRow) => row.cells[column] ?? null
    return list.sort((a, b) => {
      const x = at(a)
      const y = at(b)
      if (x === null || y === null) return x === y ? 0 : x === null ? 1 : -1
      return sort.dir === 'desc' ? y - x : x - y
    })
  }, [table, sort, across])

  const dimOptions: PickOption<DimId>[] = DIMENSIONS.map((dim) => ({ value: dim.id, label: dim.label }))
  const acrossOptions: PickOption<string>[] = [{ value: NONE, label: 'Nothing' }, ...dimOptions]

  const loading = loaded === null && failure === null
  const bar = (
    <div className="mix-controls" data-held={loading ? 'true' : undefined} inert={loading ? true : undefined}>
      <LensSwitch lens="mix" />
      <FilterChips facets={facets} value={picks} onChange={setPicks} label="Filters" />
      <div className="mix-layout">
        <Select label="Rows" value={by} options={dimOptions} onChange={(next) => setBy(next)} />
        <Select label="Columns" value={across ?? NONE} options={acrossOptions} onChange={changeAcross} />
        <FilterChips facets={[measureFacet]} value={{ measure: measures }} onChange={changeMeasures} label="Measures" />
        <SortControl options={sortOptions} value={sort} onChange={setSort} />
      </div>
    </div>
  )

  if (failure !== null) {
    return (
      <Page title="Sales" icon="dollar" className="revenue mix" toolbar={bar} toolbarLabel="Mix controls"
        status={<FailureNotice failure={failure} title="Could not read your stock" onRetry={retry} />} />
    )
  }
  if (loaded === null || table === null) {
    return <Page title="Sales" icon="dollar" className="revenue mix" toolbar={bar} toolbarLabel="Mix controls" loading />
  }
  if (loaded.mix.cards.length === 0) {
    return (
      <Page title="Sales" icon="dollar" className="revenue mix" toolbar={bar} toolbarLabel="Mix controls">
        <EmptyState
          icon="camera"
          title="No cards captured yet. Capture a card and its mix shows here."
          actions={<a className="bn-btn bn-btn-primary" href="#/capture">Capture a card</a>}
        />
      </Page>
    )
  }
  const barClears = Object.values(picks).filter((one) => one.length > 0).length >= 2
  if (table.matched === 0) {
    return (
      <Page title="Sales" icon="dollar" className="revenue mix" toolbar={bar} toolbarLabel="Mix controls">
        <EmptyState
          icon="search"
          title="No cards match these filters."
          actions={barClears ? undefined : <button type="button" className="bn-btn" onClick={() => setPicks({})}>Clear all</button>}
        />
      </Page>
    )
  }

  const measure = MEASURES.find((one) => one.id === measures[0])!
  const columns = table.columns
  const labelOf = (column: string) => (across === null ? MEASURES.find((one) => one.id === column)?.label ?? column : column)
  const kindOf = (column: string) => (across === null ? MEASURES.find((one) => one.id === column)!.kind : measure.kind)
  const maxCell = Math.max(0, ...rows.flatMap((row) => columns.filter((c) => c !== ALL).map((c) => row.cells[c] ?? 0)))
  const heatOf = (column: string, value: number | null): number | undefined => {
    if (across === null || column === ALL || value === null) return undefined
    if (measure.kind === 'count' || measure.kind === 'money') return maxCell > 0 && measure.id !== 'median' ? Math.round((value / maxCell) * 30) + 4 : undefined
    return measure.id === 'pct' ? Math.round(Math.min(1, value) * 30) + 4 : undefined
  }
  const rowLabel = (key: string) => (by === 'game' ? gameWords(key) : key)
  const dimLabel = DIMENSIONS.find((dim) => dim.id === by)!.label
  const asOf = absoluteDate(new Date(loaded.mix.asOf))
  const rule =
    measures.includes('weeks')
      ? 'Weeks of stock shows a dash where nothing sold in the last 14 days.'
      : measures.includes('pct')
        ? 'Sold of captured counts every card captured, including cards not listed yet.'
        : null

  return (
    <Page title="Sales" icon="dollar" className="revenue mix" toolbar={bar} toolbarLabel="Mix controls">
      <div className="mix-frame" role="region" aria-label="Mix table" tabIndex={0}>
        <table className="bn-table mix-table">
          <thead>
            <tr>
              <th scope="col">{dimLabel}</th>
              {columns.map((column) => (
                <th key={column} scope="col" className="mix-num" data-total={column === ALL ? 'true' : undefined}>{labelOf(column)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key}>
                <th scope="row" className="mix-rowname">{rowLabel(row.key)}</th>
                {columns.map((column) => (
                  <MixCell key={column} value={row.cells[column] ?? null} kind={kindOf(column)} heat={heatOf(column, row.cells[column] ?? null)} total={column === ALL} />
                ))}
              </tr>
            ))}
            {rows.length > 1 ? (
              <tr className="mix-all">
                <th scope="row" className="mix-rowname">All</th>
                {columns.map((column) => (
                  <MixCell key={column} value={table.total[column] ?? null} kind={kindOf(column)} total={column === ALL} />
                ))}
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <p className="mix-note">
        {`${table.matched.toLocaleString()} ${table.matched === 1 ? 'card matches' : 'cards match'}, as of ${asOf}.`}
        {rule === null ? null : ` ${rule}`}
      </p>
    </Page>
  )
}

function MixCell({ value, kind, heat, total }: { readonly value: number | null; readonly kind: string; readonly heat?: number; readonly total?: boolean }) {
  const style = heat === undefined ? undefined : ({ '--mix-heat': heat } as CSSProperties)
  return (
    <td className="mix-num" data-total={total ? 'true' : undefined} data-heat={heat === undefined ? undefined : 'true'} style={style}>
      {value === null ? (
        <span className="mix-dash" role="img" aria-label="No figure">{DASH}</span>
      ) : kind === 'money' ? (
        <Money value={value} />
      ) : kind === 'ratio' ? (
        `${Math.round(value * 100)}%`
      ) : kind === 'weeks' ? (
        value.toFixed(1)
      ) : (
        <Count value={value} />
      )}
    </td>
  )
}
