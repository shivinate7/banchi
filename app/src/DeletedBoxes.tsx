import { count } from './kit/dataRules'
import { useEffect, useMemo, useState } from 'react'

import { describeFailure, getGraveyard, type Failure } from './server'
import type { DepartedCard, InventoryCard } from './types'
import { Icon } from './kit'
import { CardPane, gameWord, type Row } from './CardHero'
import { SectionTitle } from './SectionTitle'
import { relativeDate } from './dates'
import { reasonWord, stateLabel } from './cardState'

/* THE DELETED BOXES SHELF (D134 point 5, as the owner's ruling "delete the tab" amended it).
 *
 * A sold or retired record outlives its box as one `buried` line in the event log, and this
 * shelf is the only place that line is read back: where the owner already looks for where a card
 * is. Sold cards in a box that stands stay on Sales and on Inventory's own shelves, retired ones
 * on Inventory's, so this holds the buried half of `GET /graveyard` and nothing else.
 *
 * IT IS INVENTORY'S OWN WALK AND CARD PANE. The rows draw with `BoxBrowse.css`'s own classes and
 * the pane is `CardHero.tsx`'s `CardPane`, handed a card built from the record. Two things the
 * live pane offers are absent, by omission: the card's actions, because a buried record cannot
 * come back into stock (D134, "What is lost"), and the Details disclosure, because it would
 * repeat what the facts beside the photograph already say. `BoxBrowse.tsx` owns which record is
 * open, so the walk and the pane never hold two ideas of it. */

/** A buried record as an `InventoryCard`, so the pane that draws every other card draws it.
 *  `photo` is null because the photograph went with the box. */
function cardOf(record: DepartedCard): InventoryCard {
  return {
    box: record.box,
    index: record.index,
    photo: null,
    set_hint: record.set_hint,
    moved_from: null,
    set_name: null,
    rarity: null,
    metadata_finish: null,
    game: record.game,
    rarity_claim: null,
    note: null,
    captured_at: record.captured_at,
    capture_id: null,
    photo_sha256: record.photo_sha256,
    photo_reclaimed_at: null,
    name: record.name,
    number: record.number,
    printed_total: null,
    confidence: null,
    sku: record.sku,
    condition: record.condition,
    state: record.how,
    state_at: record.left_at,
    retire_reason: record.retire_reason,
    run: null,
  }
}

const keyOf = (record: DepartedCard) => `${record.box}/${record.index}`

/** The buried records as walk rows, grouped by the box they sat in, in the order the groups first
 *  appear (newest departure first), each group in its own slot order. */
function rowsOf(buried: readonly DepartedCard[]): { box: string; record: DepartedCard; row: Row }[] {
  const boxes = [...new Set(buried.map((record) => record.box_name ?? ''))]
  return boxes.flatMap((name) =>
    buried
      .filter((record) => (record.box_name ?? '') === name)
      .sort((a, b) => a.index - b.index)
      .map((record) => ({ box: name, record, row: { key: keyOf(record), card: cardOf(record) } })),
  )
}

/** The keys of the records in the walk's own order, so the walk, the pane and the arrow keys agree
 *  on which record is first and which is next. */
export function buriedKeys(buried: readonly DepartedCard[]): string[] {
  return rowsOf(buried).map((entry) => entry.row.key)
}

/** The records from deleted boxes, or null until the read lands. A failed read is `failure`, which
 *  the screen draws with a Try again that calls `retry`. */
export function useBuried(reloadToken: number): {
  readonly buried: readonly DepartedCard[] | null
  readonly failure: Failure | null
  readonly retry: () => void
} {
  const [buried, setBuried] = useState<readonly DepartedCard[] | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [tries, setTries] = useState(0)
  useEffect(() => {
    let live = true
    getGraveyard({ buriedOnly: true })
      .then((payload) => {
        if (!live) return
        setBuried(payload.departed.filter((record) => record.buried))
        setFailure(null)
      })
      .catch((err: unknown) => {
        if (live) setFailure(describeFailure(err))
      })
    return () => {
      live = false
    }
  }, [reloadToken, tries])
  return { buried, failure, retry: () => setTries((n) => n + 1) }
}

function howLeft(record: DepartedCard): string {
  return record.how === 'retired' && record.retire_reason
    ? `Retired, ${reasonWord(record.retire_reason).toLowerCase()}`
    : stateLabel(record.how)
}

/** The shelf's walk, in place of a box's. */
export function DeletedWalk({
  buried,
  selected,
  onPick,
  dimmed = false,
}: {
  readonly buried: readonly DepartedCard[]
  readonly selected: string | null
  readonly onPick: (key: string) => void
  /** The next box is being read: the shelf stays, dimmed and out of reach, as a box's own walk does. */
  readonly dimmed?: boolean
}) {
  const rows = useMemo(() => rowsOf(buried), [buried])
  const [closed, setClosed] = useState<readonly string[]>([])
  const names = [...new Set(rows.map((entry) => entry.box))]
  return (
    <div className="browse-walk bn-panel">
      <div className="browse-box-head">
        <div className="browse-shelfnote">
          <span className="boxops-identity-num">Deleted boxes</span>
          <p>Cards sold or retired before their box was deleted.</p>
        </div>
      </div>
      <div className="browse-status">
        <span className="browse-status-text">
          {count(rows.length, 'record')}
        </span>
      </div>
      <ul
        className="browse-list"
        aria-label="Records from deleted boxes"
        aria-busy={dimmed ? 'true' : undefined}
        data-dimmed={dimmed ? 'true' : undefined}
      >
        {names.map((name) => {
          const key = `deleted @ ${name}`
          const open = !closed.includes(key)
          return (
            <li className="browse-group" key={key}>
              <div className="browse-secthead">
                <button
                  className="browse-sectfold"
                  type="button"
                  aria-expanded={open}
                  onClick={() => setClosed((held) => (open ? [...held, key] : held.filter((k) => k !== key)))}
                >
                  <Icon name="chevronRight" size={14} className="browse-sectmark" />
                  <SectionTitle parts={{ head: name === '' ? 'A box with no name' : name, count: null }} />
                </button>
              </div>
              {!open ? null : (
                <ul className="browse-group-rows">
                  {rows
                    .filter((entry) => entry.box === name)
                    .map((entry) => (
                      <li className="browse-rowline is-departed" key={entry.row.key}>
                        <button
                          className="browse-row"
                          type="button"
                          aria-current={entry.row.key === selected ? 'true' : undefined}
                          onClick={() => onPick(entry.row.key)}
                        >
                          <span className="browse-row-position">
                            <Icon name="headstone" size={12} />
                          </span>
                          <span className={entry.row.card.name ? 'browse-row-name' : 'browse-row-name is-unnamed'}>
                            {entry.row.card.name || 'Not identified yet'}
                          </span>
                          <span className="browse-row-how">{stateLabel(entry.row.card.state)}</span>
                        </button>
                      </li>
                    ))}
                </ul>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

/** The card pane, in place of a card's. */
export function DeletedPane({
  buried,
  selected,
  dimmed = false,
}: {
  readonly buried: readonly DepartedCard[]
  readonly selected: string | null
  readonly dimmed?: boolean
}) {
  const rows = useMemo(() => rowsOf(buried), [buried])
  const at = rows.find((entry) => entry.row.key === selected) ?? rows[0]
  if (at === undefined) return null
  const { record } = at
  const when = (stamp: string | null) => (stamp === null ? 'not recorded' : relativeDate(stamp))
  return (
    <CardPane
      row={at.row}
      game={gameWord(at.row.card)}
      dimmed={dimmed}
      photo={{
        label: null,
        absent: false,
        onAbsent: () => undefined,
        nonce: null,
        onZoom: () => undefined,
        reshoot: null,
        gone: 'The photograph went with the box.',
      }}
      detail={
        <dl className="browse-facts">
          <div className="browse-fact"><dt>How it left</dt><dd>{howLeft(record)}, {when(record.left_at)}</dd></div>
          <div className="browse-fact"><dt>Where it sat</dt><dd>{record.box_name ?? 'A box with no name'}</dd></div>
          <div className="browse-fact"><dt>Box deleted</dt><dd>{when(record.buried_at)}</dd></div>
          <div className="browse-fact"><dt>Captured</dt><dd>{when(record.captured_at)}</dd></div>
          {record.sku === null ? null : (
            <div className="browse-fact">
              <dt>Price history</dt>
              <dd><a href={`#/product?sku=${encodeURIComponent(record.sku)}`}>Open this card's price history</a></dd>
            </div>
          )}
        </dl>
      }
    />
  )
}
