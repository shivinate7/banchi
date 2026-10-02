/* THROWAWAY MOCK for the graveyard rethink design pass. Never merged, never pushed. */
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { getGraveyard, photoUrl } from './server'
import type { DepartedCard } from './types'
import { CardThumb, EmptyState, Page, Pill, Segmented, Icon } from './kit'
import { readingAgo, stateTone } from './cardState'
import { reasonWord } from './Inventory'
import { SearchField } from './SearchField'
import { matchQuery } from './kit/match'
import { useViewParam } from './kit/viewState'
import './MockGrave.css'

export const MOCK = new URLSearchParams(window.location.search).get('mock')

export function useDeparted(): DepartedCard[] | null {
  const [rows, setRows] = useState<DepartedCard[] | null>(null)
  useEffect(() => { void getGraveyard().then((p) => setRows(p.departed)) }, [])
  return rows
}

function how(row: DepartedCard): ReactNode {
  if (row.how === 'retired') {
    return row.retire_reason ? <>Retired, {reasonWord(row.retire_reason).toLowerCase()}</> : 'Retired'
  }
  return 'Sold'
}

function hrefOf(row: DepartedCard): string {
  if (row.buried) return row.sku ? `#/product?sku=${row.sku}` : '#/graveyard'
  return `#/inventory?box=${row.box}&q=${encodeURIComponent(row.name ?? '')}`
}

export function LedgerRow({ row, i }: { readonly row: DepartedCard; readonly i: number }) {
  const tone = stateTone(row.how)
  const stamp = row.buried ? row.buried_at : row.left_at
  return (
    <a className="mg-row" href={hrefOf(row)} style={{ ['--i' as string]: i }}>
      <CardThumb size="sm" src={row.buried ? null : photoUrl(row.box, row.index)} alt={row.name ?? 'Card'} />
      <span className="mg-card">
        <span className="mg-name">{row.name || <span className="bn-muted">Unidentified</span>}</span>
        <span className="mg-sub bn-facts">
          {row.number ? <span>{row.number}</span> : null}
          {row.set_hint ? <span>{row.set_hint}</span> : null}
          {row.condition ? <span>{row.condition}</span> : null}
        </span>
      </span>
      <span className="mg-how"><Pill tone={tone === 'accent' ? 'default' : tone}>{how(row)}</Pill></span>
      <span className="mg-where">
        <span>{row.box_name ?? 'A box with no name'}</span>
        {row.buried ? <span className="mg-gone">Box deleted, no photograph</span> : null}
      </span>
      <span className="mg-when">{readingAgo(stamp) ?? ''}</span>
      <Icon name="chevronRight" size={14} className="mg-chev" />
    </a>
  )
}

type F = 'all' | 'sold' | 'retired' | 'deleted'

export function MockLedger({ slim }: { readonly slim: boolean }) {
  const all = useDeparted()
  const rows = useMemo(() => (all === null ? null : slim ? all.filter((r) => r.how === 'retired' || r.buried) : all), [all, slim])
  const [filter, setFilter] = useViewParam('how', 'all')
  const [q, setQ] = useViewParam('q', '')
  const counts = useMemo(() => {
    const c = { all: 0, sold: 0, retired: 0, deleted: 0 }
    for (const r of rows ?? []) { c.all++; c[r.how]++; if (r.buried) c.deleted++ }
    return c
  }, [rows])
  const visible = (rows ?? []).filter((r) =>
    (filter === 'all' || (filter === 'deleted' ? r.buried : r.how === filter)) &&
    matchQuery(q, { text: [r.name, r.box_name], numbers: [r.number], skus: [r.sku] }))
  const options: { value: F; label: string }[] = slim
    ? [{ value: 'all', label: `All (${counts.all})` }, { value: 'retired', label: `Retired (${counts.retired})` }, { value: 'deleted', label: `From deleted boxes (${counts.deleted})` }]
    : [{ value: 'all', label: `All (${counts.all.toLocaleString()})` }, { value: 'sold', label: `Sold (${counts.sold.toLocaleString()})` }, { value: 'retired', label: `Retired (${counts.retired})` }, { value: 'deleted', label: `From deleted boxes (${counts.deleted})` }]
  const standingSold = (all ?? []).filter((r) => r.how === 'sold' && !r.buried).length
  return (
    <Page
      title={slim ? 'Retired and deleted' : 'Graveyard'}
      icon="history"
      className="mg"
      lede={
        slim
          ? 'Cards you took out of a box, and cards whose box you deleted. Sold cards live in Sales and in each box.'
          : `Every card that left. ${standingSold.toLocaleString()} sold from boxes you still have, the same count as Home.`
      }
      loading={rows === null}
      toolbar={
        <div className="mg-toolbar">
          <Segmented value={filter as F} options={options} onChange={(v) => setFilter(v)} label="Filter by how a card left" />
          <span className="bn-spacer" />
          <SearchField value={q} onChange={setQ} persona="owner" label="Find a card" placeholder="Search" />
        </div>
      }
    >
      {visible.length === 0 ? (
        <EmptyState icon="search" title="Nothing matches" body="No card that left matches that search." />
      ) : (
        <div className="bn-panel mg-list bn-stagger">
          {visible.slice(0, 60).map((r, i) => <LedgerRow key={`${r.buried}:${r.box}/${r.index}`} row={r} i={i} />)}
        </div>
      )}
    </Page>
  )
}

/* Direction A: Inventory's rail gains a "Deleted boxes" shelf. */
export function DeletedShelfCell({ current, count }: { readonly current: boolean; readonly count: number | null }) {
  return (
    <a className="browse-boxcell mg-shelf" href="?mock=A&deleted=1#/inventory" aria-current={current ? 'true' : undefined}>
      <span className="browse-boxcell-glyph"><Icon name="history" size={14} /></span>
      <span className="browse-boxcell-text">
        <span className="browse-boxcell-name">Deleted boxes</span>
        <span className="browse-boxcell-meta">{count === null ? '' : `${count} records, no photographs`}</span>
      </span>
    </a>
  )
}

export function DeletedShelfWalk() {
  const all = useDeparted()
  const buried = (all ?? []).filter((r) => r.buried)
  const firstNamed = buried.find((r) => r.name)
  const boxes = [...new Set(buried.map((r) => r.box_name ?? 'A box with no name'))]
  return (
    <div className="browse-walk bn-panel mg-walk">
      <div className="browse-box-head">
        <div className="browse-shelfnote">
          <span className="boxops-identity-num">Deleted boxes</span>
          <p>Cards that had sold or been retired when their box was deleted. The record stays. The photograph went with the box.</p>
        </div>
      </div>
      {boxes.map((b) => (
        <div key={b}>
          <div className="mg-section">{b}</div>
          <ul className="mg-walklist">
            {buried.filter((r) => (r.box_name ?? 'A box with no name') === b).map((r) => (
              <li key={r.index} className={r === firstNamed ? 'is-current' : undefined}>
                <span className="mg-walk-name">{r.name || 'Unidentified'}</span>
                <span className="mg-walk-how">{r.how === 'sold' ? 'Sold' : 'Retired'}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

export function DeletedRecordPane() {
  const all = useDeparted()
  const r = (all ?? []).find((x) => x.buried && x.name)
  if (!r) return <div className="bn-panel" />
  return (
    <div className="bn-panel mg-record">
      <div className="mg-record-head">
        <CardThumb size="lg" src={null} alt={r.name ?? 'Card'} />
        <div>
          <h2 className="mg-record-name">{r.name}</h2>
          <div className="mg-sub bn-facts">
            {r.number ? <span>{r.number}</span> : null}
            {r.set_hint ? <span>{r.set_hint}</span> : null}
            {r.condition ? <span>{r.condition}</span> : null}
          </div>
          <dl className="mg-facts">
            <dt>How it left</dt><dd>{how(r)}, {readingAgo(r.left_at) ?? 'date unknown'}</dd>
            <dt>Where it sat</dt><dd>{r.box_name}, deleted {readingAgo(r.buried_at)}</dd>
            <dt>Captured</dt><dd>{readingAgo(r.captured_at) ?? 'Unknown'}</dd>
          </dl>
          <p className="bn-muted mg-note">This record cannot come back into stock. Its box no longer exists.</p>
          {r.sku ? <a className="mg-link" href={`#/product?sku=${r.sku}`}>Price history for this card</a> : null}
        </div>
      </div>
    </div>
  )
}

/* Direction B: Inventory's one way in to the slim log. */
export function SlimLogLink({ count }: { readonly count: number | null }) {
  return (
    <a className="mg-loglink" href="?mock=B#/graveyard">
      <Icon name="history" size={14} />
      <span>Retired and deleted</span>
      <span className="bn-muted">{count ?? ''}</span>
      <Icon name="chevronRight" size={14} />
    </a>
  )
}
