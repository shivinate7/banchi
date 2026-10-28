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
 * size is the same while the history loads: the chart box and the four prices are held, and a
 * dash stands in for a figure not read yet.
 *
 * THE FOUR PRICES. Market comes off the history's 90-day range. The history route carries no
 * listing price, so Lowest, Lowest shipped and Direct Low come off `getPriceFacts` (the figures
 * the product sheet's "Prices Now" draws). A price neither read carries shows "not carried".
 *
 * PLACEMENT. Above the row when the viewport has room there, else on the side with more room,
 * held inside the viewport. Wholly above the row, its right edge sits on the row's
 * `[data-float-door]` (the row itself when it has none). Anywhere else it may overlap a price
 * column, its own row's or the next row's, so its right edge sits left of the row's
 * `[data-float-price]`, read off the real row and never a fixed offset.
 */

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { describeFailure, failureTone, getPriceFacts, getProductHistory, type Failure } from './server'
import type { PriceFacts, ProductHistoryPayload, ProductHistoryRange } from './types'
import { Button, CardThumb, Icon, IconButton, Money, Notice, Section } from './kit'
import { ProductChart, type Fill } from './ProductHistory'
import './HistoryFloat.css'

export type HistoryFloatMode = 'focus' | 'door'

const GAP = 8
const EDGE = 8
/** Per card width: the plot width that makes the chart's viewBox as wide as the card's inner
 * width, and the plot height (`.hfloat-chart`'s height less the chart's 20px date gutter). The
 * narrow card is shorter, so it fits above a row in the middle of a 900px viewport. */
const PLOT = { wide: { w: 416, h: 160 }, narrow: { w: 240, h: 120 } } as const
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
  const [facts, setFacts] = useState<{ readonly sku: string; readonly prices: PriceFacts['prices'] } | null>(null)
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
  // A failed price read leaves the prices as dashes; the history read above reports its own failure.
  useEffect(() => {
    let alive = true
    getPriceFacts(sku)
      .then((f) => alive && setFacts({ sku, prices: f.prices }))
      .catch(() => alive && setFacts({ sku, prices: null }))
    return () => {
      alive = false
    }
  }, [sku])
  const mine = answer?.sku === sku ? answer : null
  const payload = mine?.payload ?? null
  const range = payload === null ? null : pickRange(payload)
  const postings = payload?.asking_postings
  const suggested = suggestion === undefined ? null : Number(suggestion)
  const read = mine !== null && facts?.sku === sku
  const prices = read ? facts.prices : null
  const price = (v: string | null | undefined) => (!read ? '—' : v ? <Money value={Number(v)} /> : <span className="hfloat-quiet">not carried</span>)

  useLayoutEffect(() => {
    const move = () => {
      const card = cardRef.current
      if (card === null) return
      const r = anchor.getBoundingClientRect()
      const h = card.offsetHeight
      const w = card.offsetWidth
      const clear = r.top - GAP - EDGE >= h
      const above = clear || (r.bottom + GAP + h + EDGE > window.innerHeight && r.top >= window.innerHeight - r.bottom)
      const right = clear
        ? (anchor.querySelector('[data-float-door]') ?? anchor).getBoundingClientRect().right
        : (anchor.querySelector('[data-float-price]') ?? anchor).getBoundingClientRect().left - GAP
      const top = above ? r.top - GAP - h : r.bottom + GAP
      setPlace({
        side: above ? 'above' : 'below',
        top: Math.max(EDGE, Math.min(top, window.innerHeight - h - EDGE)),
        left: Math.max(EDGE, Math.min(right - w, window.innerWidth - w - EDGE)),
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
      <h3 className="hfloat-h">Last 90 days</h3>
      <p className="hfloat-legend">
        <span><i className="hfloat-sw" />Market</span>
        <span><i className="hfloat-sw hfloat-sw-spread" />Low to high, each week</span>
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
          <ProductChart range={range} fills={fills} {...(wide ? PLOT.wide : PLOT.narrow)} asking={postings} suggestion={suggested} />
        )}
      </div>
      <footer className="hfloat-foot">
        <dl className="hfloat-facts">
          <div><dt>Market</dt><dd>{price(range?.latest_market ?? prices?.market)}</dd></div>
          <div><dt>Lowest</dt><dd>{price(prices?.low)}</dd></div>
          <div><dt>Lowest, shipped</dt><dd>{price(prices?.low_with_shipping)}</dd></div>
          <div><dt>Direct Low</dt><dd>{price(prices?.direct_low)}</dd></div>
        </dl>
        <Button icon="external" tabIndex={mode === 'focus' ? -1 : undefined} onClick={() => { window.location.hash = `#/product?sku=${encodeURIComponent(sku)}` }}>Full history</Button>
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
            <span className="hfloat-specimen-thumb" data-float-thumb=""><CardThumb src={null} alt="" size="sm" /></span>
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
