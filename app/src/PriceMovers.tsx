/**
 * Which live items moved more than a tenth in the market since they were first seen (DEBT69).
 *
 * A READ, NEVER A DECISION. It names the item, the direction and the amount, and opens the
 * product. Nothing here changes a price: the person decides, and the price field on the row
 * below is still theirs.
 *
 * IT HOLDS ITS SIZE FROM THE FIRST PAINT. Two lines are always drawn, whatever has loaded: the
 * summary, and how the last scheduled market read ended. The list opens only when the person
 * presses, so nothing under it moves on its own.
 */

import { useEffect, useState } from 'react'
import { Button, Icon, Money, ProductLink } from './kit'
import { getPriceMovers } from './server'
import { relativeDate } from './dates'
import type { PriceMover, PriceMoversPayload, TrendsPreloadNote } from './types'
import './PriceMovers.css'

/** A signed fraction the server computed, as a whole percentage. Ink, never arithmetic on money. */
function percent(fraction: string): string {
  const value = Math.abs(Number(fraction)) * 100
  return `${value >= 10 ? Math.round(value) : value.toFixed(1)}%`
}

function summary(read: PriceMoversPayload | null | 'failed'): string {
  if (read === null) return 'Reading price moves…'
  if (read === 'failed') return 'Price moves are not available right now.'
  const gone = read.movers.length
  const cut = Math.round(Number(read.threshold) * 100)
  if (gone === 0) {
    return read.listed === 0
      ? 'No live listings have been read yet.'
      : `No live price has moved more than ${cut}% since it was first seen.`
  }
  return `${gone} live ${gone === 1 ? 'item' : 'items'} moved more than ${cut}% since ${gone === 1 ? 'it was' : 'they were'} first seen.`
}

/** ONE LINE, always: the unchecked count comes before the free-form message so a clamp never
 *  cuts it, and the full text is on the title. */
function readLine(read: PriceMoversPayload | null | 'failed'): { text: string; failed: boolean } {
  if (read === null || read === 'failed') return { text: '\u00a0', failed: false }
  const unchecked =
    read.unmeasured === 0 ? '' : ` ${read.unmeasured} could not be checked for want of an earlier price.`
  const note = read.refresh
  if (note === null) return { text: `No daily price read has run yet.${unchecked}`, failed: false }
  const when = relativeDate(note.at * 1000)
  if (!note.ok) {
    return { text: `The daily price read failed ${when}, so these prices are older.${unchecked} ${note.message}`, failed: true }
  }
  return { text: `Prices were read ${when}.${unchecked}`, failed: false }
}

/** How the overnight Trends read ended, in one clamped line. A partial read says how many of how
 *  many, a failed one carries its sentence, and the date is relative. Empty while loading and on
 *  the live lens, so the line holds its height in every state. */
function trendsLine(note: TrendsPreloadNote | null, loading: boolean): { text: string; failed: boolean } {
  if (loading) return { text: '\u00a0', failed: false }
  if (note === null) return { text: 'No overnight trends read has run yet. Press Trends to read them now.', failed: false }
  const when = relativeDate(note.at * 1000)
  const partial = !note.ok || note.unreadable > 0
  const counts = [
    note.unreadable > 0 ? `${note.unreadable} could not be read.` : '',
    note.no_history > 0 ? `${note.no_history} ${note.no_history === 1 ? 'has' : 'have'} no history.` : '',
  ].filter(Boolean).join(' ')
  if (!partial) {
    return { text: `Trends were read ${when} for ${note.read} ${note.read === 1 ? 'card' : 'cards'}. ${counts} Press Trends to refresh.`.replace('  ', ' '), failed: false }
  }
  const failure = note.failed > 0 ? ` ${note.failed} ${note.failed === 1 ? 'step' : 'steps'} failed: ${note.message}` : ''
  return { text: `Trends were read ${when} for ${note.read} of ${note.asked} cards. ${counts}${failure}`, failed: true }
}

function MoverRow({ row }: { row: PriceMover }) {
  const label = row.name ?? row.sku
  const detail = [row.set, row.number, row.condition].filter(Boolean).join(', ')
  return (
    <li className="pricemovers-row" data-direction={row.direction}>
      <span className="pricemovers-what">
        <ProductLink sku={row.sku} name={label}>
          {label}
        </ProductLink>
        {detail === '' ? null : <span className="pricemovers-detail">{detail}</span>}
      </span>
      <span className="pricemovers-prices">
        <Money value={Number(row.then)} />
        <Icon name="arrowRight" size={14} />
        <Money value={Number(row.now)} />
      </span>
      <span className="pricemovers-change" aria-label={`${row.direction === 'up' ? 'Up' : 'Down'} ${percent(row.change)}`}>
        <Icon name={row.direction === 'up' ? 'trendUp' : 'trendDown'} size={14} />
        {row.direction === 'up' ? 'Up' : 'Down'} {percent(row.change)}
      </span>
    </li>
  )
}

export function PriceMovers({
  trendsNote,
  trendsLoading,
}: {
  readonly trendsNote: TrendsPreloadNote | null
  readonly trendsLoading: boolean
}) {
  const [read, setRead] = useState<PriceMoversPayload | null | 'failed'>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    let alive = true
    getPriceMovers()
      .then((payload) => {
        if (alive) setRead(payload)
      })
      .catch(() => {
        if (alive) setRead('failed')
      })
    return () => {
      alive = false
    }
  }, [])

  const moved = read !== null && read !== 'failed' ? read.movers : []
  const line = readLine(read)
  const trends = trendsLine(trendsNote, trendsLoading)
  return (
    <section className="pricemovers" aria-label="Price moves since first seen">
      <div className="pricemovers-head">
        <p className="pricemovers-says">{summary(read)}</p>
        {moved.length === 0 ? null : (
          <Button size="sm" variant="quiet" onClick={() => setOpen((on) => !on)} aria-expanded={open} words="word-only-control">
            {open ? 'Hide' : 'Show'}
          </Button>
        )}
      </div>
      <p className="pricemovers-read" data-failed={line.failed ? 'true' : undefined} title={line.text.trim() === '' ? undefined : line.text}>
        {line.failed ? <Icon name="alert" size={14} /> : null}
        <span className="pricemovers-read-text">{line.text}</span>
      </p>
      <p className="pricemovers-read" data-failed={trends.failed ? 'true' : undefined} title={trends.text.trim() === '' ? undefined : trends.text}>
        {trends.failed ? <Icon name="alert" size={14} /> : null}
        <span className="pricemovers-read-text">{trends.text}</span>
      </p>
      {open && moved.length > 0 ? (
        <ul className="pricemovers-list">
          {moved.map((row) => (
            <MoverRow key={row.sku} row={row} />
          ))}
        </ul>
      ) : null}
    </section>
  )
}
