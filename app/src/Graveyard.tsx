import { useCallback, useEffect, useMemo, useState } from 'react'

import { describeFailure, getGraveyard, type Failure } from './server'
import type { DepartedCard } from './types'
import { Button, EmptyState, Notice, PageHeader, Pill, Segmented, type PillTone } from './kit'
import { readingAgo, readingExact, stateLabel, stateTone } from './cardState'
import { storeKeyText } from './storeKey'
import './Graveyard.css'

/* GRAVEYARD — D134's whole reason for existing.
 *
 * A box goes when its cards have left it, sold or retired or moved — and until D134 that box
 * could never be deleted at all, because a departed record was the one thing `do_delete_box`
 * refused to touch. It no longer refuses: a sold, retired or moved record is BURIED, one
 * `buried` line per record in the store's own event log, before the box and everything in it
 * goes. This screen is where that line is read back.
 *
 * TWO SOURCES, ONE TABLE. A departed card is either still standing in a box nobody has
 * deleted — the same records `#/inventory` already draws as departed — or its box was deleted
 * and it survives only as a `buried` line. `GET /graveyard` merges both and this screen never
 * has to ask which door a row came from beyond the one pill that says so.
 *
 * WHAT IS LOST AND WHAT IS NOT (D134). A buried record cannot be undone — there is no route
 * back from a deleted box — and its photograph is gone with it. What survives is the record
 * itself: what the card was, how it left, when, and where. Nothing about pricing or an order
 * reads this screen; it is a ledger for looking, not a control.
 */

type HowFilter = 'all' | 'sold' | 'retired' | 'moved' | 'buried'

const FILTERS: readonly { readonly value: HowFilter; readonly label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'sold', label: 'Sold' },
  { value: 'retired', label: 'Retired' },
  { value: 'moved', label: 'Moved' },
  { value: 'buried', label: 'Buried' },
]

/** The same fallback `cardState.ts:stateLabel` uses for a word this table has no map for —
 *  raw_underscored becomes "Raw underscored" rather than printing the wire value whole. */
function gameLabel(game: string | null): string | null {
  if (game === null || game.trim() === '') return null
  const spaced = game.replace(/_/g, ' ')
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

function howIt(row: DepartedCard): string {
  if (row.how === 'moved') {
    return row.moved_to === null ? 'Moved' : `Moved to ${positionOf(row.moved_to)}`
  }
  if (row.how === 'retired' && row.retire_reason) {
    return `Retired · ${row.retire_reason}`
  }
  return stateLabel(row.how)
}

/** `"9/3"` → `"B9 #3"`, `storeKey.ts`'s own spelling (D68, D92): a departed record is in no
 *  slot to count to, so its `#` is the store key rather than D58's countable figure — the
 *  exemption `storeKeyText` carries, not a bare `#{index}` reaching for it by hand. A
 *  malformed key (there should never be one) falls back to the raw string rather than
 *  hiding where the card went. */
function positionOf(key: string): string {
  const [box, index] = key.split('/')
  const boxN = Number(box)
  const indexN = Number(index)
  if (!Number.isFinite(boxN) || !Number.isFinite(indexN)) return key
  return storeKeyText(boxN, indexN)
}

function cardTone(how: string): PillTone {
  const tone = stateTone(how)
  return tone === 'accent' ? 'default' : tone
}

export function Graveyard() {
  const [rows, setRows] = useState<DepartedCard[] | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [retrying, setRetrying] = useState(false)
  const [filter, setFilter] = useState<HowFilter>('all')
  const [query, setQuery] = useState('')

  const load = useCallback(async () => {
    try {
      const payload = await getGraveyard()
      setRows(payload.departed)
      setFailure(null)
    } catch (err) {
      setFailure(describeFailure(err))
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const retry = useCallback(async () => {
    setRetrying(true)
    try {
      await load()
    } finally {
      setRetrying(false)
    }
  }, [load])

  const counts = useMemo(() => {
    const base = { all: 0, sold: 0, retired: 0, moved: 0, buried: 0 }
    if (rows === null) return base
    for (const row of rows) {
      base.all += 1
      base[row.how] += 1
      if (row.buried) base.buried += 1
    }
    return base
  }, [rows])

  const visible = useMemo(() => {
    if (rows === null) return []
    const needle = query.trim().toLowerCase()
    return rows.filter((row) => {
      if (filter === 'buried' ? !row.buried : filter !== 'all' && row.how !== filter) return false
      if (needle === '') return true
      const haystack = [row.name, row.number, row.sku, row.box_name, row.order]
        .filter((v): v is string => v !== null)
        .join(' ')
        .toLowerCase()
      return haystack.includes(needle)
    })
  }, [rows, filter, query])

  return (
    <main className="graveyard bn-page">
      <PageHeader
        title="Graveyard"
        icon="history"
        lede="Every card that's left inventory — sold, retired, or moved. Read-only."
        actions={
          <Button variant="ghost" iconOnly icon="refresh" onClick={() => void load()} disabled={retrying}>
            Reload
          </Button>
        }
      />

      {failure !== null && rows !== null ? (
        <div className="graveyard-failure bn-anim-pop">
          <Notice tone="danger" title={failure.message} code={failure.code || undefined}>
            As last read.
          </Notice>
          <Button variant="ghost" size="sm" icon="refresh" busy={retrying} disabled={retrying} onClick={() => void retry()}>
            Try again
          </Button>
        </div>
      ) : null}

      {rows === null ? (
        failure === null ? (
          <div className="bn-panel graveyard-loading" aria-busy="true" aria-label="Reading the graveyard">
            {Array.from({ length: 6 }, (_, i) => (
              <div key={i} className="graveyard-skel-row">
                <div className="bn-skeleton" style={{ width: 72, height: 12 }} />
                <div className="bn-skeleton" style={{ width: '40%', height: 14 }} />
                <div className="bn-skeleton" style={{ width: 96, height: 20, borderRadius: 999 }} />
                <div className="bn-skeleton" style={{ width: 120, height: 12 }} />
              </div>
            ))}
          </div>
        ) : (
          <div className="bn-panel graveyard-unreadable">
            <EmptyState
              icon="alert"
              title="The graveyard could not be read"
              body={failure.message}
              actions={
                <Button icon="refresh" busy={retrying} disabled={retrying} onClick={() => void retry()}>
                  Try again
                </Button>
              }
            />
          </div>
        )
      ) : rows.length === 0 ? (
        <EmptyState
          icon="sparkles"
          title="Nothing has left yet"
          body="Nothing has left inventory yet."
        />
      ) : (
        <>
          <div className="graveyard-toolbar">
            <Segmented value={filter} options={FILTERS.map((f) => ({ value: f.value, label: `${f.label} (${counts[f.value]})` }))} onChange={setFilter} label="Filter by how a card left" />
            <span className="bn-spacer" />
            <input
              className="bn-input graveyard-search"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Find a card, SKU or box"
              aria-label="Find in the graveyard"
            />
          </div>

          {visible.length === 0 ? (
            <EmptyState icon="search" title="Nothing matches" body="No departed card matches those filters." />
          ) : (
            <div className="graveyard-table-wrap">
              <table className="bn-table graveyard-table">
                <thead>
                  <tr>
                    <th>Left</th>
                    <th>Card</th>
                    <th>SKU</th>
                    <th>How</th>
                    <th>Where</th>
                    <th>Order</th>
                    <th>Run</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((row, i) => {
                    const key = `${row.how}:${row.buried ? 'b' : 's'}:${row.box}/${row.index}`
                    const stamp = row.buried ? row.buried_at : row.left_at
                    return (
                      <tr key={key} className={`graveyard-row is-${row.how}`} style={{ animationDelay: `${Math.min(i, 24) * 16}ms` }}>
                        <td data-th="Left" className="graveyard-when" title={readingExact(stamp) ?? undefined}>
                          {readingAgo(stamp) ?? <span className="bn-faint">—</span>}
                        </td>
                        <td data-th="Card">
                          <span className="graveyard-card-cell">
                            <span className="graveyard-name">{row.name ?? <span className="bn-faint">Unidentified</span>}</span>
                            <span className="graveyard-sub">
                              {row.number ?? <span className="bn-faint">—</span>}
                              {gameLabel(row.game) !== null ? <Pill size="sm">{gameLabel(row.game)}</Pill> : null}
                            </span>
                          </span>
                        </td>
                        <td data-th="SKU" className="graveyard-mono" data-empty={row.sku ? undefined : ''}>
                          {row.sku ?? <span className="bn-faint">—</span>}
                          {row.condition ? <span className="graveyard-condition">{row.condition}</span> : null}
                        </td>
                        <td data-th="How">
                          <Pill tone={cardTone(row.how)}>{howIt(row)}</Pill>
                        </td>
                        <td data-th="Where">
                          <span className="graveyard-where">
                            {row.box_name !== null ? `${row.box_name} · ` : ''}
                            {storeKeyText(row.box, row.index)}
                            {row.buried ? <Pill tone="default" outline>Buried</Pill> : null}
                          </span>
                        </td>
                        <td data-th="Order" className="graveyard-mono" data-empty={row.order ? undefined : ''}>
                          {row.order ?? <span className="bn-faint">—</span>}
                        </td>
                        <td data-th="Run" className="graveyard-mono" data-empty={row.run ? undefined : ''}>
                          {row.run ?? <span className="bn-faint">—</span>}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </main>
  )
}
