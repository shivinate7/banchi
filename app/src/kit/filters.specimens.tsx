import { useState } from 'react'
import type { ReactNode } from 'react'

import { FilterBar, HideToggle, SortHeaderButton } from './filters'
import { Highlight } from './highlight'
import type { FilterValue, SortValue } from './data'

/* `FilterBar`, `HideToggle`, `SortHeaderButton` and `Highlight`, drawn on the kit page. Invented
 * data only: nothing here reads the store. Mirrors `data.specimens.tsx`'s own shape and fixture
 * style, one level up: the composed bar rather than each of its pieces alone. */

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

const GAMES = [
  { value: 'pokemon', label: 'Pokémon', count: 37 },
  { value: 'riftbound', label: 'Riftbound', count: 85 },
  { value: 'onepiece', label: 'One Piece', count: 0 },
]

const RARITIES = [
  { value: 'common', label: 'Common', count: 40 },
  { value: 'rare', label: 'Rare', count: 12 },
  { value: 'double-rare', label: 'Double Rare', count: 3 },
]

const SETS = [
  { value: 'sv1', label: 'Scarlet & Violet', count: 12 },
  { value: 'sv3', label: 'Obsidian Flames', count: 9 },
]

const SORTS = [
  { key: 'recent', label: 'Captured', asc: 'Oldest first', desc: 'Newest first' },
  { key: 'price', label: 'Price' },
  { key: 'name', label: 'Name', asc: 'A to Z', desc: 'Z to A', first: 'asc' as const },
] as const

type SortKey = (typeof SORTS)[number]['key']

const ROWS = [
  { name: 'Heimerdinger, Inventor', sku: '8607411' },
  { name: 'Ho-Oh ex', sku: '8607412' },
  { name: 'Flabébé', sku: '8607413' },
]

export function FilterSpecimens() {
  /* NO FACET WAITS ON ANOTHER (the owner's ruling, 2026-09-23, against Inventory's game-then-
   * set-then-rarity lock): every option below is offered from the first paint, none disabled,
   * and picking one never wipes another's choice. */
  const [filters, setFilters] = useState<FilterValue>({ game: ['pokemon'] })
  const [sort, setSort] = useState<SortValue<SortKey>>({ key: 'recent', dir: 'desc' })
  const [query, setQuery] = useState('')
  const [hideSold, setHideSold] = useState(true)
  const [tableSort, setTableSort] = useState<SortValue<'name' | 'sku'>>({ key: 'name', dir: 'asc' })

  const activeFacets = Object.values(filters).reduce((n, picked) => n + (picked.length > 0 ? 1 : 0), 0)
  const shown = activeFacets === 0 ? 122 : 37

  return (
    <div className="bn-stack" style={{ gap: 'var(--bn-6)' }} data-kit-filters>
      <Specimen name="FilterBar">
        <div style={{ width: '100%' }}>
          <FilterBar
            facets={[
              { key: 'game', label: 'Game', options: GAMES },
              /* SINGLE-CHOICE, drawn beside the multi-select facets on either side of it: a
               *  card is in exactly one set, so `Set` is `multiple: false` while `Game` and
               *  `Rarity` may hold several at once — the two shapes side by side, honestly
               *  drawn (FLT-15, gripe 5's "one selection rule, drawn honestly"). */
              { key: 'set', label: 'Set', options: SETS, multiple: false },
              { key: 'rarity', label: 'Rarity', options: RARITIES },
            ]}
            value={filters}
            onChange={setFilters}
            search={{ query, onChange: setQuery, placeholder: 'Card name, number or SKU' }}
            sort={{ options: SORTS, value: sort, onChange: setSort }}
            hide={{ checked: hideSold, onChange: setHideSold, label: 'Hide sold', count: 8 }}
            count={{ shown, total: 122 }}
          />
        </div>
      </Specimen>

      <Specimen name="HideToggle">
        <HideToggle checked={hideSold} onChange={setHideSold} count={8}>
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
              <th>
                <SortHeaderButton sortKey="name" value={tableSort} onChange={setTableSort}>
                  Name
                </SortHeaderButton>
              </th>
              <th>
                <SortHeaderButton sortKey="sku" value={tableSort} onChange={setTableSort} align="end">
                  SKU
                </SortHeaderButton>
              </th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.sku}>
                <td>{row.name}</td>
                <td>{row.sku}</td>
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
        <span data-specimen-nomatch>
          <Highlight text="Ho-Oh ex" query="zzzz" />
        </span>
      </Specimen>
    </div>
  )
}
