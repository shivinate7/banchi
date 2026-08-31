/**
 * What one SKU has been selling for, drawn beside the hold that needs it.
 *
 * D49 records that the `bullish` withhold and its `watch_above` threshold are the only
 * things in the product that want a trend, and that they have never had one — "a hold is set
 * against the operator's memory of what a card used to cost". This panel is that memory
 * replaced by a reading, on the screen where the hold is set.
 *
 * ------------------------------------------------------------------------------------
 * THE VWAP IS THE ANCHOR AND THE BOUND IS A SANITY CHECK. NEVER PEERS.
 *
 * `pipeline/pricehistory.py`'s header spends a section on this and names the failure it is
 * guarding against: "If a caller ever reports the bound as the answer, or renders the two as
 * though they were a price and an error bar of comparable authority, that is this paragraph
 * being ignored." This component is that caller, so the rule is drawn rather than restated:
 *
 *   - `vwap` is the only figure on this panel at display size.
 *   - `bound` is one muted line at the metadata size, BELOW it, carrying its own width so it
 *     reads as "how much this estimate could be out" rather than as a second price.
 *
 * Why it cannot be tightened: we hold a per-bucket low and high, not fills. A true VWAP is a
 * mean over fills, so what is computable is a point estimate and the interval it must lie in
 * — measured on Moonfall at $12.54..$20.35 around $16.33, which is 48% of the estimate wide.
 * A bound that wide drawn with equal weight would make the panel useless and dishonest at the
 * same time.
 *
 * ------------------------------------------------------------------------------------
 * THE TWO RANGES SIT SIDE BY SIDE AND NOTHING ADDS THEM UP.
 *
 * `annual` is not the year before `month`; it is 357 days that INCLUDE the same recent days
 * at a coarser width, so concatenating them double-counts the recent window. Measured on
 * Vilemaw the day this was built, the two point OPPOSITE WAYS — up 71% over the month, down
 * 34% over the year — and that is the panel working rather than a contradiction to resolve:
 * a card recovering off a floor is exactly the case a hold is set on. There is deliberately
 * no combined figure and no "overall" row.
 *
 * AND THE WIDER RANGE IS THE STALER ONE, which nobody expects. Weekly buckets are stamped at
 * the start of their week, so `annual` ended 2026-08-24 while `month` ended 2026-08-30 on the
 * same card at the same moment. Each range therefore draws its own span; a shared caption
 * would be wrong for one of them.
 *
 * ------------------------------------------------------------------------------------
 * DIRECTION IS A SIGN AND A WORD, NEVER A COLOR.
 *
 * The palette has no red and no green — `docs/DESIGN.md` locks it, every value was chosen by
 * the owner from rendered alternatives, and D50 is the only token added against that lock.
 * Inventing a rise/fall pair here would be a second vocabulary nothing audits, and it would
 * fail exactly the reader this product is otherwise careful about: `accent` is spoken for
 * ("unsure", and the only-action fill), so a colored percentage would collide with a meaning
 * the app already has.
 *
 * ------------------------------------------------------------------------------------
 * THIS PANEL PRICES NOTHING AND WRITES NOTHING.
 *
 * D8 makes the TCGplayer export the pricing source. Every figure here is a READING taken
 * beside it — the export's own market price is drawn at the top for comparison and nothing
 * averages the two. There is no control on this panel that sets a price, and the day one is
 * wanted that is a change to D8 argued on its own terms.
 */

import { useMemo } from 'react'
import type { HistoryPoint, HistoryRange, PriceHistoryPayload } from './types'
import './PriceHistory.css'

/** How a range is captioned. The endpoint's own range names are machine strings and are drawn
 *  verbatim beside these, per `docs/DESIGN.md`'s owner-screen rule — human label large,
 *  machine string small — so the label here never becomes a second vocabulary. */
const RANGE_LABEL: Record<string, string> = {
  month: 'Daily',
  quarter: '3-day',
  semiannual: 'Weekly',
  annual: 'Weekly',
}

/** A ratio the SERVER computed, rendered as a percentage. THE ONLY ARITHMETIC ON THIS PANEL.
 *
 *  Safe where money arithmetic would not be, and the distinction is the reason this is
 *  allowed to exist at all: `app/src/server.ts` forbids the app computing rules the pipeline
 *  owns, and every such rule is about MONEY — a list price, a cap, a floor. This multiplies a
 *  already-computed dimensionless ratio by 100 to write it the way people read it. It cannot
 *  mis-price anything because nothing downstream reads it; it is ink. */
function percent(fraction: string | null): string | null {
  if (fraction === null) return null
  const value = Number(fraction)
  if (!Number.isFinite(value)) return null
  const shown = (value * 100).toFixed(1)
  return `${value > 0 ? '+' : ''}${shown}%`
}

/** POSITIVE IS RISING. Stated in the payload's own type and repeated here because this is
 *  where the word is chosen: the endpoint hands its buckets over newest-first, so a sign is
 *  one unsorted list away from meaning its opposite, and a WORD beside the number is what
 *  makes that visible to a person rather than only to a test. */
function direction(fraction: string | null): string {
  if (fraction === null) return 'not enough sales to say'
  const value = Number(fraction)
  if (!Number.isFinite(value) || value === 0) return 'flat'
  return value > 0 ? 'rising' : 'falling'
}

/** The sparkline. One polyline over each bucket's market price, oldest on the left.
 *
 *  IT DRAWS THE STANDING PRICE AND NOT THE SALES, and that is why it is captioned rather
 *  than left to speak for itself. A bucket that sold nothing still carries a `marketPrice` —
 *  TCGplayer's own figure — so the line is continuous where the sales are not, which is the
 *  honest shape for a trend and the wrong one for a volume reading. The volume is the
 *  `liquidity` row beneath; the two answer different questions and are never combined into a
 *  single decorated line.
 *
 *  A BUCKET WITH NO PRICE BREAKS THE LINE RATHER THAN INTERPOLATING ACROSS IT. Measured on
 *  Vilemaw's `annual`, whose oldest bucket is a card that had not been printed yet: joining
 *  through it would draw a year-long slope that never happened.
 *
 *  NO AXES AND NO GRID. This is a shape, not a chart — the numbers are printed beside it, at
 *  a size a person can read, and a 44px-tall sparkline with tick labels would be four
 *  illegible things instead of one legible one. `docs/DESIGN.md`'s hairline is the baseline
 *  and there is nothing else on it. */
function Spark({ points }: { points: HistoryPoint[] }) {
  const W = 260
  const H = 44
  const runs = useMemo(() => {
    const priced = points.map((p) => (p.market === null ? null : Number(p.market)))
    const known = priced.filter((v): v is number => v !== null && Number.isFinite(v))
    if (known.length < 2) return null
    const lo = Math.min(...known)
    const hi = Math.max(...known)
    // A FLAT SERIES IS DRAWN FLAT, down the middle, rather than divided by zero. A card whose
    // price has not moved is a real and useful reading, and it must not render as a NaN path.
    const span = hi - lo || 1
    const step = priced.length > 1 ? W / (priced.length - 1) : W
    const segments: string[][] = []
    let current: string[] = []
    priced.forEach((value, at) => {
      if (value === null || !Number.isFinite(value)) {
        if (current.length > 1) segments.push(current)
        current = []
        return
      }
      const x = (at * step).toFixed(1)
      // SVG's y grows DOWNWARD, so the high price is the small number. Inverted here rather
      // than by a transform, because a transform would also flip the stroke geometry.
      const y = (H - ((value - lo) / span) * (H - 4) - 2).toFixed(1)
      current.push(`${x},${y}`)
    })
    if (current.length > 1) segments.push(current)
    return segments.length ? segments : null
  }, [points])

  if (runs === null) return null
  return (
    <svg
      className="pricehistory-spark"
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      /* DECORATIVE BY DECLARATION. Every figure this shape carries is printed as text beside
         it, so a screen reader that announced a path would be repeating the panel rather than
         adding to it — and there is no honest short alt text for thirty buckets. */
      aria-hidden="true"
      focusable="false"
    >
      {runs.map((segment, at) => (
        <polyline key={at} points={segment.join(' ')} />
      ))}
    </svg>
  )
}

function Range({ range }: { range: HistoryRange }) {
  const label = RANGE_LABEL[range.range] ?? range.range
  const moved = percent(range.momentum.fraction)
  return (
    <section className="pricehistory-range">
      <header className="pricehistory-range-head">
        <h4>{label}</h4>
        {/* THE MACHINE STRING BENEATH THE LABEL, which is docs/DESIGN.md's owner-screen rule
            and the same shape `#/review` gives a reason code. `month` and `annual` are the
            endpoint's own range names, so what is on screen greps to the payload and to
            `pipeline/pricehistory.py:RANGES`. */}
        <p className="pricehistory-machine">{range.range}</p>
        <p className="pricehistory-span">
          {range.from ?? '?'} → {range.to ?? '?'}
        </p>
      </header>

      <Spark points={range.points} />

      {/* THE ANCHOR. The one figure on this panel at display size — see the header. */}
      <p className="pricehistory-vwap">
        {range.vwap === null ? (
          <span className="pricehistory-none">no sales in this range</span>
        ) : (
          <>
            <span className="pricehistory-figure">${range.vwap}</span>
            <span className="pricehistory-vwap-key">avg sale</span>
          </>
        )}
      </p>

      {/* THE SANITY CHECK. Muted, small, below the anchor, and carrying its own width so it
          reads as the estimate's slack rather than as a second price. `width_of_vwap` is the
          denominator to draw here of the two the payload offers: the question a reader has is
          "how far out could that number be", and that is the interval over the estimate. */}
      {range.bound === null ? null : (
        <p className="pricehistory-bound">
          could be ${range.bound.low}–${range.bound.high}
          {percent(range.bound.width_of_vwap) === null
            ? null
            : ` · ±${((Number(range.bound.width_of_vwap) / 2) * 100).toFixed(0)}%`}
        </p>
      )}

      <dl className="pricehistory-facts">
        <div>
          <dt>MOVED</dt>
          <dd>
            {moved === null ? '—' : moved}
            <span className="pricehistory-word">{direction(range.momentum.fraction)}</span>
          </dd>
        </div>
        <div>
          <dt>SOLD</dt>
          <dd>
            {range.liquidity}
            <span className="pricehistory-word">
              {range.transactions} order{range.transactions === 1 ? '' : 's'}
            </span>
          </dd>
        </div>
        <div>
          <dt>SPREAD</dt>
          <dd>
            {range.dispersion === null ? '—' : `$${range.dispersion}`}
            <span className="pricehistory-word">within a bucket</span>
          </dd>
        </div>
      </dl>
    </section>
  )
}

export type HistoryRead =
  | { kind: 'reading' }
  | { kind: 'read'; payload: PriceHistoryPayload }
  | { kind: 'refused'; why: string }

/**
 * TWO WAYS IN, AND THE PANEL IS TOLD WHICH ONE IT IS.
 *
 * `pinned` is the deliberate open — the `T` button's click, or this panel's own Keep — and it
 * stands until something closes it. Unpinned is a HELD `t` aimed by the pointer, and it ends
 * on the release. `Pricing.tsx` owns both states and the gesture; what is here is the one
 * difference a reader can see, which is the footer: a pin offers the press that ends it, a
 * held peek offers the press that stops it ending.
 */
export function PriceHistoryPanel({
  sku,
  name,
  read,
  pinned,
  onClose,
  onKeep,
  onRetry,
}: {
  sku: string
  name: string
  read: HistoryRead | undefined
  pinned: boolean
  onClose: () => void
  onKeep: () => void
  onRetry: () => void
}) {
  return (
    <aside className="pricehistory" aria-label={`Price history for ${name}`}>
      <header className="pricehistory-head">
        <h3>{name}</h3>
        {/* AIMED, AND THE PANEL SAYS AT WHAT. It does not follow the focused row the way the
            photograph beside it does, because a read is a request to two public mirrors and a
            follow-focus panel would fire one per arrow key. The SKU is printed so that a
            panel left open while the hands move down the list cannot be mistaken for a
            reading of whatever row is focused now — the pinned case, and equally the held one,
            where the row named is the one the pointer was over when the key went down. */}
        <p className="pricehistory-machine">sku {sku}</p>
      </header>

      {read === undefined || read.kind === 'reading' ? (
        <p className="pricehistory-state">reading…</p>
      ) : read.kind === 'refused' ? (
        <>
          <p className="pricehistory-state">{read.why}</p>
          <button type="button" className="pricing-plain" onClick={onRetry}>
            Try again
          </button>
        </>
      ) : read.payload.never_sold || read.payload.ranges.length === 0 ? (
        /* A REAL PRODUCT THE ENDPOINT HAS NEVER SEEN SELL. It answers HTTP 200 with a null
           result there — measured on two catalogued products — so this is not a failure and
           must not be drawn as one. Reading it as a broken join would send somebody to look
           for a defect over a card that is merely illiquid. */
        <p className="pricehistory-state">
          no recorded sales. The product resolved, so this is a card that has not traded
          rather than one we could not find.
        </p>
      ) : (
        <>
          {/* THE EXPORT'S OWN FIGURE, AT THE TOP AND LABELLED AS THE EXPORT'S. This is what
              the card is priced against today (D8) and the whole point of the panel is to put
              it beside what the card has been selling for. Nothing averages the two and
              nothing on this panel writes it. */}
          <p className="pricehistory-listed">
            <span className="pricehistory-listed-key">EXPORT MARKET</span>
            <span className="pricehistory-listed-value">
              {read.payload.market === null ? 'no_market_data' : `$${read.payload.market}`}
            </span>
          </p>
          <div className="pricehistory-ranges">
            {read.payload.ranges.map((range) => (
              <Range key={range.range} range={range} />
            ))}
          </div>
          {/* THE ONE SENTENCE THIS PANEL OWES A READER WHO DOES NOT KNOW THE SOURCE. Two
              ranges disagreeing is the ordinary case, not a fault, and without this a person
              reads "+71%" beside "−34%" as the panel being broken. */}
          {read.payload.ranges.length > 1 ? (
            <p className="pricehistory-note">
              The ranges overlap and are read separately — the wider one includes these same
              recent days at a coarser width, so they can point opposite ways.
            </p>
          ) : null}
        </>
      )}

      {/* THE FOOTER IS WHERE THE TWO OPENINGS DIFFER, and it is the only place they do.
          A pin ends on a press, so it offers that press. A held peek ends on the release,
          which is the whole point of it and needs no button — so what it offers instead is
          the way to STOP it ending, reachable because the other hand is still on the mouse. */}
      <div className="pricehistory-controls">
        {pinned ? (
          <button type="button" className="pricing-plain" onClick={onClose}>
            Close
          </button>
        ) : (
          <button type="button" className="pricing-plain" onClick={onKeep}>
            Keep open
          </button>
        )}
      </div>
    </aside>
  )
}
