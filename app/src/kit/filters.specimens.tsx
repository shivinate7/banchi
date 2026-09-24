import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { FilterBar, HideToggle, SortHeader } from './filters'
import { countFacets, filterRows } from './facets'
import { Highlight } from './highlight'
import { matchQuery, type MatchFields } from './match'
import { Button } from './index'
import type { FilterFacet, FilterValue, SortValue } from './data'

/* `FilterBar`, `HideToggle`, `SortHeader` and `Highlight`, drawn on the kit page. Invented data
 * only: nothing here reads the store. The bar's counts are REAL arithmetic over the invented
 * rows below, through `kit/facets.ts` — the same call a screen makes — so a pick in one facet
 * visibly changes the counts in the others, and "N of M" is what the rows say. */

function Specimen({ name, children }: { readonly name: string; readonly children: ReactNode }) {
  return (
    <div className="bn-stack" style={{ gap: 'var(--bn-2)' }} data-specimen={name}>
      <p className="bn-label">{name}</p>
      <div className="bn-row" style={{ gap: 'var(--bn-3)', flexWrap: 'wrap', alignItems: 'center' }}>
        {children}
      </div>
    </div>
  )
}

type Row = {
  readonly name: string
  readonly number: string
  readonly sku: string
  readonly game: string
  readonly set: string
  readonly rarity: string
  readonly sold: boolean
}

/* Twenty-four invented cards over three games, four sets and three rarities. Deterministic: the
 * spec reads the counts these produce. */
const SEED: readonly (readonly [string, string, string, string, string])[] = [
  ['pokemon', 'sv1', 'Sprigatito', '001/198', 'common'],
  ['pokemon', 'sv1', 'Fuecoco', '024/198', 'common'],
  ['pokemon', 'sv1', 'Quaxly', '052/198', 'common'],
  ['pokemon', 'sv1', 'Pawmot', '076/198', 'rare'],
  ['pokemon', 'sv1', 'Miraidon ex', '081/198', 'double-rare'],
  ['pokemon', 'sv1', 'Koraidon ex', '125/198', 'double-rare'],
  ['pokemon', 'sv3', 'Charizard ex', '054/197', 'double-rare'],
  ['pokemon', 'sv3', 'Flabébé', '084/197', 'common'],
  ['pokemon', 'sv3', 'Ho-Oh ex', '110/197', 'rare'],
  ['pokemon', 'sv3', 'Tyranitar ex', '066/197', 'double-rare'],
  ['pokemon', 'sv3', 'Farfetch’d', '149/197', 'common'],
  ['pokemon', 'sv3', 'Pidgeot ex', '164/197', 'double-rare'],
  ['riftbound', 'ogn', 'Heimerdinger, Inventor', '112/298', 'rare'],
  ['riftbound', 'ogn', 'Jinx, Loose Cannon', '030/298', 'rare'],
  ['riftbound', 'ogn', 'Annie, Fiery', '001/298', 'common'],
  ['riftbound', 'ogn', 'Garen, Rugged', '171/298', 'common'],
  ['riftbound', 'ogn', 'Ahri, Alluring', '066/298', 'rare'],
  ['riftbound', 'ogn', 'Lux, Illuminated', '201/298', 'common'],
  ['onepiece', 'op01', 'Roronoa Zoro', 'OP01-001', 'rare'],
  ['onepiece', 'op01', 'Nami', 'OP01-016', 'common'],
  ['onepiece', 'op01', 'Trafalgar Law', 'OP01-047', 'rare'],
  ['onepiece', 'op01', 'Kaido', 'OP01-094', 'double-rare'],
  ['onepiece', 'op01', 'Sanji', 'OP01-013', 'common'],
  ['onepiece', 'op01', 'Usopp', 'OP01-004', 'common'],
]

export const FILTER_ROWS: readonly Row[] = SEED.map(([game, set, name, number, rarity], at) => ({
  name,
  number,
  sku: String(8607400 + at),
  game,
  set,
  rarity,
  /* Every fourth card has sold, so Hide sold always hides some. */
  sold: at % 4 === 3,
}))

export const FILTER_FACETS: readonly FilterFacet[] = [
  {
    key: 'game',
    label: 'Game',
    options: [
      { value: 'pokemon', label: 'Pokémon' },
      { value: 'riftbound', label: 'Riftbound' },
      { value: 'onepiece', label: 'One Piece' },
    ],
  },
  /* SINGLE-CHOICE, drawn beside the multi-choice facets on either side of it: a card is in one
   *  set, so `Set` is `multiple: false` while `Game` and `Rarity` may hold several at once — the
   *  two shapes side by side, honestly drawn (FLT-15, gripe 5's "one selection rule"). */
  {
    key: 'set',
    label: 'Set',
    multiple: false,
    options: [
      { value: 'sv1', label: 'Scarlet & Violet' },
      { value: 'sv3', label: 'Obsidian Flames' },
      { value: 'ogn', label: 'Origins' },
      { value: 'op01', label: 'Romance Dawn' },
    ],
  },
  {
    key: 'rarity',
    label: 'Rarity',
    options: [
      { value: 'common', label: 'Common' },
      { value: 'rare', label: 'Rare' },
      { value: 'double-rare', label: 'Double Rare' },
    ],
  },
]

export function filterValueOf(row: Row, key: string): string | null {
  if (key === 'game') return row.game
  if (key === 'set') return row.set
  if (key === 'rarity') return row.rarity
  return null
}

export function filterFieldsOf(row: Row): MatchFields {
  return { text: [row.name], numbers: [row.number], skus: [row.sku] }
}

/** The whole arithmetic a screen does around a `FilterBar`: the facet counts under the other
 *  filters, the rows shown, and how many rows Hide sold hides. Exported so the test page's URL
 *  demo draws the same bar from the URL. */
export function useFilteredRows(value: FilterValue, query: string, hideSold: boolean) {
  return useMemo(() => {
    const searched = (row: Row) => matchQuery(query, filterFieldsOf(row))
    const keep = (row: Row) => searched(row) && (!hideSold || !row.sold)
    const facets = countFacets(FILTER_ROWS, FILTER_FACETS, value, filterValueOf, keep)
    const shown = filterRows(FILTER_ROWS, FILTER_FACETS, value, filterValueOf, keep)
    const soldHere = filterRows(FILTER_ROWS, FILTER_FACETS, value, filterValueOf, (row) => searched(row) && row.sold).length
    return { facets, shown, soldHere }
  }, [value, query, hideSold])
}

const SORTS = [
  { key: 'recent', label: 'Captured', asc: 'Oldest first', desc: 'Newest first' },
  { key: 'price', label: 'Price' },
  { key: 'name', label: 'Name', asc: 'A to Z', desc: 'Z to A', first: 'asc' as const },
] as const

type SortKey = (typeof SORTS)[number]['key']

const TABLE = [
  { name: 'Heimerdinger, Inventor', price: 1.25 },
  { name: 'Ho-Oh ex', price: 4.1 },
  { name: 'Flabébé', price: 0.3 },
]

export function FilterSpecimens() {
  /* NO FACET WAITS ON ANOTHER (the owner's ruling, 2026-09-23, against Inventory's game-then-
   * set-then-rarity lock): every option below is offered from the first paint, none disabled,
   * and picking one never wipes another's choice. */
  const [filters, setFilters] = useState<FilterValue>({ game: ['pokemon'] })
  const [sort, setSort] = useState<SortValue<SortKey>>({ key: 'recent', dir: 'desc' })
  const [query, setQuery] = useState('')
  const [hideSold, setHideSold] = useState(true)
  const [tableSort, setTableSort] = useState<SortValue<'name' | 'price'>>({ key: 'price', dir: 'desc' })
  const [railFilters, setRailFilters] = useState<FilterValue>({})
  const [railQuery, setRailQuery] = useState('ho-oh')
  const { facets, shown, soldHere } = useFilteredRows(filters, query, hideSold)
  const rail = useFilteredRows(railFilters, railQuery, false)

  const table = [...TABLE].sort((a, b) => {
    const order = tableSort.key === 'name' ? a.name.localeCompare(b.name) : a.price - b.price
    return tableSort.dir === 'asc' ? order : -order
  })

  return (
    <div className="bn-stack" style={{ gap: 'var(--bn-6)' }} data-kit-filters>
      <Specimen name="FilterBar">
        <div style={{ width: '100%' }}>
          <FilterBar
            facets={facets}
            value={filters}
            onChange={setFilters}
            search={{ query, onChange: setQuery, placeholder: 'Card name, number or SKU' }}
            sort={{ options: SORTS, value: sort, onChange: setSort }}
            hide={{ checked: hideSold, onChange: setHideSold, label: 'Hide sold', count: soldHere, defaultChecked: true }}
            count={{ shown: shown.length, total: FILTER_ROWS.length }}
          />
        </div>
      </Specimen>

      {/* A BAR IN A RAIL: 280px, Inventory's own rail width. The bar asks its own width, so it
          is the compact trigger here even on a desk, with the rail's collapse press beside the
          search, and the search waiting on its answer. */}
      <Specimen name="Rail">
        <div style={{ width: '280px', maxWidth: '100%' }} data-specimen-rail>
          <FilterBar
            facets={rail.facets}
            value={railFilters}
            onChange={setRailFilters}
            search={{ query: railQuery, onChange: setRailQuery, loading: true }}
            beside={
              <Button iconOnly icon="chevronLeft" variant="ghost">
                Fold list
              </Button>
            }
            count={{ shown: rail.shown.length, total: FILTER_ROWS.length }}
          />
        </div>
      </Specimen>

      <Specimen name="HideToggle">
        <HideToggle checked={hideSold} onChange={setHideSold} count={soldHere}>
          Hide sold
        </HideToggle>
        <HideToggle checked={false} onChange={() => undefined} count={0}>
          Hide never-seen SKUs
        </HideToggle>
      </Specimen>

      <Specimen name="SortHeader">
        <table className="bn-table" style={{ width: 'min(100%, 420px)' }}>
          <thead>
            <tr>
              <SortHeader sortKey="name" value={tableSort} onChange={setTableSort} first="asc">
                Name
              </SortHeader>
              <SortHeader sortKey="price" value={tableSort} onChange={setTableSort} align="end">
                Price
              </SortHeader>
            </tr>
          </thead>
          <tbody>
            {table.map((row) => (
              <tr key={row.name}>
                <td>{row.name}</td>
                <td style={{ textAlign: 'right' }}>
                  <span className="bn-money">{`$${row.price.toFixed(2)}`}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Specimen>

      <Specimen name="Highlight">
        <span>
          <Highlight text="Heimerdinger, Inventor" query="heimerdinger-inventor" />
        </span>
        <span>
          <Highlight text="Flabébé" query="flabebe" />
        </span>
        <span data-specimen-number>
          <Highlight text="054/197" query="54/197" kind="number" />
        </span>
        {/* One word of the query is in the name, the other nowhere: the matcher refuses the
            row, so nothing is marked. */}
        <span data-specimen-refused>
          <Highlight text="Ho-Oh ex" query="ho-oh zzzz" />
        </span>
      </Specimen>
    </div>
  )
}
