import { useCallback, useEffect, useMemo, useState, type CSSProperties, type ReactNode } from 'react'

import { describeFailure, getBoxes, getGraveyard, type Failure } from './server'
import type { BoxRecord, DepartedCard } from './types'
import { Button, EmptyState, Notice, Page, Pill, ReloadButton, Segmented, type PillTone } from './kit'
import { readingAgo, readingExact, stateLabel, stateTone } from './cardState'
import { reasonWord } from './Inventory'
import { SearchField } from './SearchField'
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
 *
 * THE BOX SHOWS BY ITS NAME, NEVER ITS NUMBER (D-a-box-is-shown-by-its-name, superseding D68's
 * "Box 3 · departed · B3 #96" form and the store-key exemption D92 gave it). The Where column
 * reads `row.box_name` straight off the payload; the "Moved to" text resolves the destination
 * through `getBoxes()`. Neither draws the store key any more.
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

/** The box named in a `"box/index"` store key — `D-a-box-is-shown-by-its-name`: the number
 *  the key carries is never drawn, only the name it resolves to. A box the registry no longer
 *  has (deleted, or the list has not answered yet) falls back to "another box" rather than the
 *  number — the honest answer where there is genuinely no name to read. */
function movedToName(key: string, boxes: BoxRecord[] | null): string {
  const boxN = Number(key.split('/')[0])
  if (!Number.isFinite(boxN)) return 'another box'
  const name = boxes?.find((b) => b.box === boxN)?.name
  return typeof name === 'string' && name.trim() !== '' ? name : 'another box'
}

function howIt(row: DepartedCard, boxes: BoxRecord[] | null): ReactNode {
  if (row.how === 'moved') {
    return row.moved_to === null ? 'Moved' : `Moved to ${movedToName(row.moved_to, boxes)}`
  }
  if (row.how === 'retired' && row.retire_reason) {
    // D218: the reason is its own span; the seam is CSS. The word itself reads Inventory's
    // own label table (UX review, 2026-09-20) rather than the raw enum — "Retired · pulled"
    // read as an order-fulfilment term, not "taken out of the box".
    return (
      <>
        <span>Retired</span>
        <span className="graveyard-reason">{reasonWord(row.retire_reason)}</span>
      </>
    )
  }
  return stateLabel(row.how)
}

function cardTone(how: string): PillTone {
  const tone = stateTone(how)
  return tone === 'accent' ? 'default' : tone
}

/** Rows drawn before a "Show more" press, and added each further press (UX-036): the real
 *  store's 1,180 departed rows made an 86,935px page with every row drawn at once. Windowed
 *  rather than paged, matching `Codes.tsx`'s own `ROW_CAP`/`showAll` pattern for a long list. */
const ROW_WINDOW = 100

export function Graveyard() {
  const [rows, setRows] = useState<DepartedCard[] | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [retrying, setRetrying] = useState(false)
  const [filter, setFilter] = useState<HowFilter>('all')
  const [query, setQuery] = useState('')
  const [shown, setShown] = useState(ROW_WINDOW)
  // Names the "Moved to" text alone — read-only, so a stale list between reloads costs nothing.
  const [boxes, setBoxes] = useState<BoxRecord[] | null>(null)

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

  useEffect(() => {
    getBoxes()
      .then((summary) => setBoxes(summary.boxes))
      .catch(() => undefined)
  }, [])

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

  // A changed filter or search is a new list: the window starts over rather than keeping a
  // count sized for a different set of rows.
  useEffect(() => {
    setShown(ROW_WINDOW)
  }, [filter, query])

  const windowed = visible.slice(0, shown)

  const hasRows = rows !== null && rows.length > 0

  return (
    <Page
      title="Graveyard"
      icon="history"
      lede="Sold, retired and moved cards."
      actions={<ReloadButton onReload={() => void load()} busy={retrying} />}
      loading={rows === null && failure === null}
      status={
        failure !== null && rows !== null ? (
          <div className="graveyard-failure bn-anim-pop">
            <Notice tone="danger" title={failure.message} code={failure.code || undefined}>
              As last read.
            </Notice>
            <Button variant="ghost" size="sm" icon="refresh" busy={retrying} disabled={retrying} onClick={() => void retry()}>
              Try again
            </Button>
          </div>
        ) : undefined
      }
      toolbar={
        hasRows ? (
          <div className="graveyard-toolbar">
            <Segmented value={filter} options={FILTERS.map((f) => ({ value: f.value, label: `${f.label} (${counts[f.value]})` }))} onChange={setFilter} label="Filter by how a card left" />
            <span className="bn-spacer" />
            <SearchField value={query} onChange={setQuery} persona="owner" label="Find in the graveyard" placeholder="Find a card, SKU or box" />
          </div>
        ) : undefined
      }
      empty={
        rows === null ? (
          <div className="bn-panel graveyard-unreadable">
            <EmptyState
              icon="alert"
              title="The graveyard could not be read"
              body={failure?.message ?? ''}
              actions={
                <Button icon="refresh" busy={retrying} disabled={retrying} onClick={() => void retry()}>
                  Try again
                </Button>
              }
            />
          </div>
        ) : rows.length === 0 ? (
          <EmptyState icon="sparkles" title="Nothing has left yet" body="Nothing has left inventory yet." />
        ) : undefined
      }
    >
      {!hasRows ? null : visible.length === 0 ? (
        <EmptyState icon="search" title="Nothing matches" body="No departed card matches those filters." />
      ) : (
        <div className="graveyard-table-wrap">
          <table className="bn-table graveyard-table">
            <colgroup>
              <col className="graveyard-col-left" />
              <col className="graveyard-col-card" />
              <col className="graveyard-col-sku" />
              <col className="graveyard-col-how" />
              <col className="graveyard-col-where" />
              <col className="graveyard-col-order" />
              <col className="graveyard-col-captured" />
            </colgroup>
            <thead>
              <tr>
                <th>Left</th>
                <th>Card</th>
                <th>SKU</th>
                <th>How</th>
                <th>Where</th>
                <th>Order</th>
                <th>Captured</th>
              </tr>
            </thead>
            <tbody className="bn-stagger">
              {windowed.map((row, i) => {
                const key = `${row.how}:${row.buried ? 'b' : 's'}:${row.box}/${row.index}`
                const stamp = row.buried ? row.buried_at : row.left_at
                return (
                  /* THE SHARED CADENCE (UX review, 2026-09-20), not a hand-rolled one: this
                     row used to set its own `animationDelay` (16ms * min(i, 24)), a second
                     copy of the stagger every other list in the product reads off
                     `--bn-stagger`/`--bn-stagger-cap` (`kit.css:81`). `.bn-stagger` on the
                     body plus `--i` here is the same mechanism `Orders.tsx` already uses. */
                  <tr key={key} className={`graveyard-row is-${row.how}`} style={{ '--i': i } as CSSProperties}>
                    <td data-th="Left" className="graveyard-when" title={readingExact(stamp) ?? undefined}>
                      {readingAgo(stamp) ?? <span className="bn-faint">—</span>}
                    </td>
                    <td data-th="Card">
                      <span className="graveyard-card-cell">
                        <span className="graveyard-name" title={row.name ?? undefined}>
                          {row.name && row.name.trim() !== '' ? row.name : <span className="bn-muted">Unidentified</span>}
                        </span>
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
                      <Pill tone={cardTone(row.how)}>{howIt(row, boxes)}</Pill>
                    </td>
                    <td data-th="Where">
                      <span className="graveyard-where">
                        {/* D-a-box-is-shown-by-its-name: the box shows by name only. No
                            store key (D68's superseded "B3 #96" form) — a box with no
                            stored name yet is the honest "—" rather than the number. */}
                        <span className="graveyard-where-name">{row.box_name ?? <span className="bn-faint">—</span>}</span>
                        {row.buried ? <Pill tone="default" outline>Buried</Pill> : null}
                      </span>
                    </td>
                    <td data-th="Order" className="graveyard-mono" data-empty={row.order ? undefined : ''}>
                      {row.order ?? <span className="bn-faint">—</span>}
                    </td>
                    <td
                      data-th="Captured"
                      className="graveyard-when"
                      data-empty={row.captured_at ? undefined : ''}
                      title={readingExact(row.captured_at) ?? undefined}
                    >
                      {readingAgo(row.captured_at) ?? <span className="bn-faint">—</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {shown < visible.length ? (
            <div className="graveyard-more">
              <span className="bn-muted">
                Showing {windowed.length.toLocaleString()} of {visible.length.toLocaleString()}
              </span>
              <Button variant="ghost" size="sm" onClick={() => setShown((n) => n + ROW_WINDOW)}>
                Show {Math.min(ROW_WINDOW, visible.length - shown).toLocaleString()} more
              </Button>
            </div>
          ) : null}
        </div>
      )}
    </Page>
  )
}
