/**
 * THE FLOATING PRICE-HISTORY CARD (`docs/specs/pricing-suggest.md` section 9c, mockup
 * `docs/design/pricing-suggest/history-float.html`). A price field taking focus, or the row's
 * history door, opens it over the list; it draws `ProductHistory.tsx:ProductChart` with the
 * owner's asking step line and the suggestion dot, and never a second chart.
 *
 * FOCUS BY MODE. `focus`: opened by a price field, the card takes no focus (its close button is
 * out of the tab order), so Tab goes on to the next price and the caller moves `anchor`/`sku`.
 * `door`: opened by the history door, the card takes focus and `restoreFocus` (the door) gets it
 * back when it closes. Esc and the close button call `onClose` in both modes. Focus leaving the
 * price fields is the caller's to see (`HistoryFloatSpecimen` shows how).
 *
 * NOTHING MOVES (D313). The card is `position: fixed`, so the list under it never shifts. Its
 * size is the same while the history loads: the chart box and the three facts are held, and a
 * dash stands in for a figure not read yet.
 *
 * PLACEMENT. Above the row when the viewport has room there, else below it. It aligns to the
 * row's left edge, which keeps it clear of the price column on the right (the caller's row
 * layout must leave the card's width between its left edge and the price field).
 */

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { describeFailure, failureTone, getProductHistory, type Failure } from './server'
import type { ProductHistoryPayload, ProductHistoryRange } from './types'
import { Icon, IconButton, Money, Notice, Section } from './kit'
import { ProductChart, type Fill } from './ProductHistory'
import './HistoryFloat.css'

export type HistoryFloatMode = 'focus' | 'door'

const GAP = 8
const EDGE = 8
/** The plot width that makes the chart's viewBox as wide as the card's inner width, per card width. */
const PLOT = { wide: 416, narrow: 240 } as const
const WIDE_QUERY = '(min-width: 1100px)'

function useWide(): boolean {
  const [wide, setWide] = useState(() => window.matchMedia(WIDE_QUERY).matches)
  useEffect(() => {
    const mql = window.matchMedia(WIDE_QUERY)
    const onChange = () => setWide(mql.matches)
    mql.addEventListener('change', onChange)
    return () => mql.removeEventListener('change', onChange)
  }, [])
  return wide
}

/** The 90-day range when the payload has it, else the first one. */
function pickRange(payload: ProductHistoryPayload): ProductHistoryRange | null {
  return payload.ranges.find((r) => r.range === 'quarter') ?? payload.ranges[0] ?? null
}

type Answer = { readonly sku: string; readonly payload: ProductHistoryPayload | null; readonly failure: Failure | null }

export function HistoryFloat({
  sku, anchor, mode, fills, suggestion, row, onClose, restoreFocus,
}: {
  readonly sku: string
  readonly anchor: HTMLElement
  readonly mode: HistoryFloatMode
  readonly fills: readonly Fill[]
  readonly suggestion?: string
  readonly row?: number | string
  readonly onClose: () => void
  readonly restoreFocus?: HTMLElement | null
}) {
  const wide = useWide()
  const cardRef = useRef<HTMLElement>(null)
  const [answer, setAnswer] = useState<Answer | null>(null)
  const [place, setPlace] = useState<{ top: number; left: number; side: 'above' | 'below' }>({ top: 0, left: 0, side: 'above' })

  // Read only this card's history. `ProductHistory.tsx:useProductHistory` also reads every order,
  // and the caller already hands this card its fills.
  useEffect(() => {
    let alive = true
    getProductHistory(sku)
      .then((payload) => alive && setAnswer({ sku, payload, failure: null }))
      .catch((error) => alive && setAnswer({ sku, payload: null, failure: describeFailure(error) }))
    return () => {
      alive = false
    }
  }, [sku])
  const mine = answer?.sku === sku ? answer : null
  const payload = mine?.payload ?? null
  const range = payload === null ? null : pickRange(payload)
  const postings = payload?.asking_postings
  const asking = postings?.length ? postings[postings.length - 1]!.price : null
  const suggested = suggestion === undefined ? null : Number(suggestion)

  useLayoutEffect(() => {
    const move = () => {
      const card = cardRef.current
      if (card === null) return
      const r = anchor.getBoundingClientRect()
      const above = r.top - GAP >= card.offsetHeight
      setPlace({
        side: above ? 'above' : 'below',
        top: above ? r.top - GAP - card.offsetHeight : r.bottom + GAP,
        left: Math.max(EDGE, Math.min(r.left, window.innerWidth - card.offsetWidth - EDGE)),
      })
    }
    move()
    window.addEventListener('resize', move)
    window.addEventListener('scroll', move, true)
    return () => {
      window.removeEventListener('resize', move)
      window.removeEventListener('scroll', move, true)
    }
  }, [anchor, wide])

  useEffect(() => {
    if (mode === 'door') cardRef.current?.focus({ preventScroll: true })
  }, [mode])

  const close = () => {
    onClose()
    if (mode === 'door') restoreFocus?.focus({ preventScroll: true })
  }
  const closeRef = useRef(close)
  closeRef.current = close
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeRef.current()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  const state = mine === null ? 'loading' : 'ready'
  // In the body, so no ancestor's transform can turn `position: fixed` into something else.
  return createPortal(
    <section
      ref={cardRef}
      className="hfloat"
      role="group"
      aria-label={`Price history for ${payload?.name ?? 'this card'}`}
      tabIndex={-1}
      style={{ top: place.top, left: place.left }}
      data-history-float=""
      data-mode={mode}
      data-placement={place.side}
      data-state={state}
      data-row={row}
      // A press on the card must not pull focus off the price field that opened it.
      onMouseDown={mode === 'focus' ? (e) => e.preventDefault() : undefined}
    >
      <header className="hfloat-head">
        <span className="bn-overlay-icon"><Icon name="history" size={18} /></span>
        <p className="hfloat-name">{payload?.name ?? 'Price history'}</p>
        <IconButton icon="x" label="Close" onClick={close} tabIndex={mode === 'focus' ? -1 : undefined} {...{ 'data-history-float-close': '' }} />
      </header>
      <p className="hfloat-legend">
        <span><i className="hfloat-sw" />Market</span>
        <span><i className="hfloat-sw hfloat-sw-ask" />Your price</span>
        <span><i className="hfloat-sw hfloat-sw-sale" />Your sale</span>
        <span><i className="hfloat-sw hfloat-sw-sug" />Suggested</span>
      </p>
      <div className="hfloat-chart">
        {mine?.failure ? (
          <Notice tone={failureTone(mine.failure)} code={mine.failure.code}>{mine.failure.message}</Notice>
        ) : range === null ? (
          state === 'ready' ? <p className="hfloat-none">No price history has been read for this card yet.</p> : null
        ) : (
          <ProductChart range={range} fills={fills} w={wide ? PLOT.wide : PLOT.narrow} asking={postings} suggestion={suggested} />
        )}
      </div>
      <footer className="hfloat-foot">
        <dl className="hfloat-facts">
          <div><dt>Market</dt><dd>{range?.latest_market ? <Money value={Number(range.latest_market)} /> : '—'}</dd></div>
          <div><dt>Your price</dt><dd>{asking === null ? '—' : <Money value={Number(asking)} />}</dd></div>
          <div><dt>Suggested</dt><dd>{suggested === null ? '—' : <Money value={suggested} />}</dd></div>
        </dl>
        <IconButton icon="external" label="Full history" href={`#/product?sku=${encodeURIComponent(sku)}`} tabIndex={mode === 'focus' ? -1 : undefined} />
      </footer>
    </section>,
    document.body,
  )
}

/* ---- the `#/gallery` specimen: three rows, one price field and one history door each -------- */

const SPECIMEN_ROWS = [
  { sku: 'GALLERY-0', name: 'Volcanion', price: '1.25' },
  { sku: 'GALLERY-1', name: 'Gardevoir ex', price: '4.50', suggestion: '4.90' },
  { sku: 'GALLERY-2', name: 'Charizard', price: '12.00' },
] as const

/** One specimen sale, dated inside the demo range so the chart has a mark to draw. */
const SPECIMEN_FILLS: readonly Fill[] = [{ at: new Date('2026-08-27T12:00:00Z'), orderNumber: 'SPECIMEN', quantity: 1, unitPrice: 1.25 }]

export function HistoryFloatSpecimen() {
  const [open, setOpen] = useState<{ row: number; mode: HistoryFloatMode; door: HTMLElement | null } | null>(null)
  const rowEls = useRef<(HTMLElement | null)[]>([])
  const shown = open === null ? undefined : SPECIMEN_ROWS[open.row]
  return (
    <Section
      id="kit-history-float"
      data-kit-section="history-float"
      className="kit-section"
      title="Price history card"
      lede="Opens above a row when its price field takes focus, and moves down the list with Tab. The door opens it and takes focus."
    >
      <div className="hfloat-specimen">
        {SPECIMEN_ROWS.map((r, i) => (
          <div key={r.sku} className="hfloat-specimen-row" data-float-row={i} ref={(el) => { rowEls.current[i] = el }}>
            <span className="hfloat-specimen-name">{r.name}</span>
            <input
              className="bn-input bn-input-mono hfloat-specimen-price"
              aria-label={`Price for ${r.name}`}
              defaultValue={r.price}
              data-float-price=""
              onFocus={() => setOpen({ row: i, mode: 'focus', door: null })}
              // Focus going to another price field moves the card (its onFocus); anywhere else closes it.
              onBlur={(e) => {
                if (!e.relatedTarget?.matches('[data-float-price]')) setOpen((o) => (o?.mode === 'focus' ? null : o))
              }}
            />
            <IconButton
              icon="history"
              label="Price history"
              name={`Price history for ${r.name}`}
              tabIndex={-1}
              onClick={(e) => setOpen({ row: i, mode: 'door', door: e.currentTarget })}
              {...{ 'data-float-door': '' }}
            />
          </div>
        ))}
      </div>
      {open !== null && shown !== undefined && rowEls.current[open.row] && (
        <HistoryFloat
          sku={shown.sku}
          anchor={rowEls.current[open.row]!}
          mode={open.mode}
          row={open.row}
          fills={SPECIMEN_FILLS}
          suggestion={'suggestion' in shown ? shown.suggestion : undefined}
          restoreFocus={open.door}
          onClose={() => setOpen(null)}
        />
      )}
    </Section>
  )
}
