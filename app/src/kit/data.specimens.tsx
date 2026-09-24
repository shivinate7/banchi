import { useState } from 'react'
import type { ReactNode } from 'react'

import {
  BoxLabel,
  CardLine,
  CardThumb,
  Count,
  FilterChips,
  FilterCount,
  Location,
  Money,
  OrderLink,
  ProductLink,
  Select,
  Sep,
  SortControl,
  StatusBadge,
  type FilterValue,
  type SortValue,
} from './data'
import { absoluteDate, relativeDate } from '../dates'
import { SearchField } from '../SearchField'
import type { Place } from '../types'

/* THE DATA PRIMITIVES, DRAWN ON THE KIT PAGE. Every one of them, in every state a screen can
 * put it in, so a new screen picks from what it can see here. The kit page mounts
 * `DataSpecimens` and owns where it sits. Invented data only: nothing here reads the store. */

/** A 1x1 transparent image, so the photo specimen draws a frame with no request. */
const BLANK_PHOTO = 'data:image/gif;base64,R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=='

/** A PLACE BLOCK AS THE SERVER SENDS IT, the same fixture shape `Gallery.tsx` keeps. Its
 *  `label` is wire data (`pipeline/join.py:Position.label`), never text this file writes for
 *  the eye: `Location` splits it and CSS draws the separators (D218). */
const WIRE_PLACE: Place = {
  label: 'RB Epics, Section 2, Card 15',
  box: 3,
  index: 40,
  slot: 40,
  section: 2,
  card: 15,
  box_name: 'RB Epics',
  section_start: 26,
  section_end: 50,
  box_total: 250,
  box_closed: true,
  fraction: 0.16,
}

/** The same place after its card left: the label keeps the place, the slot is gone. */
const GONE_PLACE: Place = { ...WIRE_PLACE, slot: null, card: null, fraction: null }

/** A fixed moment, so the date specimens read the same on every run. */
const NOW = new Date('2026-09-23T15:00:00')

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
  'Common', 'Uncommon', 'Rare', 'Holo Rare', 'Double Rare', 'Ultra Rare', 'Illustration Rare',
  'Special Illustration Rare', 'Hyper Rare',
].map((label, at) => ({ value: label.toLowerCase().replace(/ /g, '-'), label, count: 40 - at * 4 }))

const SETS = [
  { value: 'sv1', label: 'Scarlet & Violet', count: 12 },
  { value: 'sv3', label: 'Obsidian Flames', count: 9 },
  { value: 'ogn', label: 'Origins', count: 30 },
]

const SORTS = [
  { key: 'recent', label: 'Captured', asc: 'Oldest first', desc: 'Newest first' },
  { key: 'price', label: 'Price' },
  { key: 'name', label: 'Name', asc: 'A to Z', desc: 'Z to A', first: 'asc' as const },
] as const

export function DataSpecimens() {
  const [game, setGame] = useState<string | null>('pokemon')
  const [filters, setFilters] = useState<FilterValue>({ game: ['pokemon'] })
  const [sort, setSort] = useState<SortValue<'recent' | 'price' | 'name'>>({ key: 'recent', dir: 'desc' })
  const [query, setQuery] = useState('')
  const [submitted, setSubmitted] = useState<string | null>(null)

  const active = Object.entries(filters).flatMap(([key, picked]) => {
    const pool = key === 'game' ? GAMES : key === 'set' ? SETS : RARITIES
    return picked.map((value) => pool.find((option) => option.value === value)?.label ?? value)
  })

  return (
    <div className="bn-stack" style={{ gap: 'var(--bn-6)' }} data-kit-data>
      <Specimen name="Money">
        <Money value={1.23} />
        <Money value={66334.71} />
        <Money value={1.2} signed />
        <Money value={-0.35} signed />
        <Money value={null} />
      </Specimen>

      <Specimen name="Count">
        <span>
          Sold <Count value={19} label="sold" />
        </span>
        <span>
          All <Count value={1179} label="cards" />
        </span>
        <Count value={3} tone="strong" label="need you" />
      </Specimen>

      <Specimen name="Dates">
        <span>{relativeDate(new Date('2026-09-23T14:55:00'), NOW)}</span>
        <span>{relativeDate(new Date('2026-09-23T13:00:00'), NOW)}</span>
        <span>{relativeDate(new Date('2026-09-22T12:00:00'), NOW)}</span>
        <span>{absoluteDate(new Date('2026-09-04T12:00:00'))}</span>
      </Specimen>

      <Specimen name="Separator">
        <span>
          <span>Obsidian Flames</span>
          <Sep />
          <span>Near Mint</span>
        </span>
      </Specimen>

      <Specimen name="Status">
        <StatusBadge status="needs">Needs pricing</StatusBadge>
        <StatusBadge status="working">Reading</StatusBadge>
        <StatusBadge status="done">Listed</StatusBadge>
        <StatusBadge status="failed">Refused</StatusBadge>
        <StatusBadge status="waiting">At TCGplayer</StatusBadge>
        <StatusBadge status="neutral">Sealed</StatusBadge>
      </Specimen>

      <Specimen name="Card">
        <CardLine name="Charizard ex" sku="8607411" set="Obsidian Flames" number="125/197" condition="Near Mint" rarity="Double Rare" />
        <CardLine name="Charizard ex" sku="8607412" set="Obsidian Flames" number="125/197" condition="Near Mint Holofoil" rarity="Double Rare" />
        <CardLine name="Abra" set="Scarlet & Violet" number="054/132" finish="Reverse holo" layout="inline" />
        <CardLine name={null} />
      </Specimen>

      <Specimen name="Photo">
        <CardThumb src={BLANK_PHOTO} alt="Charizard ex" size="sm" />
        <CardThumb src={BLANK_PHOTO} alt="Charizard ex" size="md" />
        <CardThumb src={null} alt="Abra" size="sm" />
        <CardThumb src={null} alt="Abra" size="md" />
        <CardThumb src={null} alt="Abra" size="lg" />
      </Specimen>

      <Specimen name="Box">
        <BoxLabel box={3} name="RB Epics" />
        <BoxLabel box={4} name="Mixed Singles" />
        <BoxLabel box={7} />
      </Specimen>

      <Specimen name="Place">
        <Location place={WIRE_PLACE} />
        <Location place={WIRE_PLACE} flow="run" />
        <Location label={null} />
        <Location place={GONE_PLACE} />
      </Specimen>

      <Specimen name="Links">
        <ProductLink sku="8607411">Charizard ex</ProductLink>
        <OrderLink orderKey="tcgplayer:09-03-26_00012">09-03-26_00012</OrderLink>
      </Specimen>

      <Specimen name="Pick one">
        <Select label="Game" value={game} options={GAMES} onChange={setGame} />
        <Select label="Set" value={null} options={SETS} onChange={() => undefined} />
      </Specimen>

      <Specimen name="Filters">
        <FilterChips
          facets={[
            { key: 'game', label: 'Game', options: GAMES },
            { key: 'set', label: 'Set', options: SETS },
            { key: 'rarity', label: 'Rarity', options: RARITIES },
          ]}
          value={filters}
          onChange={setFilters}
        />
      </Specimen>

      <Specimen name="Filtered count">
        <FilterCount shown={active.length === 0 ? 122 : 37} total={122} filters={active} onClear={() => setFilters({})} />
      </Specimen>

      <Specimen name="Sort">
        <SortControl options={SORTS} value={sort} onChange={setSort} />
      </Specimen>

      <Specimen name="Search">
        <div style={{ width: 'min(100%, 480px)' }}>
          <SearchField persona="owner" value={query} onChange={setQuery} onSubmit={setSubmitted} submitLabel="Find" />
        </div>
        {submitted === null ? null : <span data-submitted>{submitted}</span>}
      </Specimen>
    </div>
  )
}
