import { useEffect, useRef } from 'react'

import type { FillLine, OrderRow } from './types'
import type { Envelope, Queue, Stop, WalkAsk } from './orderWalk'
import './OrderWalkBanner.css'

/* THE BANNER OVER THE WALK WHILE AN ORDER DRIVES IT — presentation only.
 *
 * `Inventory.tsx` owns the queue, the cursor, the writes and the receipts; this draws what they
 * say and offers the presses the mode has. It holds no state but the one focus cue below, so the
 * shape of what the operator reads at the drawer can move without the machinery moving under it.
 *
 * WHAT IT ANSWERS AT A GLANCE, in this order, because that is the order the question comes at
 * the drawer: which order am I filling, where am I in it, what is this stop, how many copies is
 * the press about to record — and then the press. "Am I done with this order?" is two figures at
 * opposite ends of one line: `STOP 5 of 5` at the left, `mark 7 of 7 sold` at the right.
 *
 * THE ROW IS ONE ROW AND NEVER BECOMES TWO OR CHANGES HEIGHT — and the claim is about the ROW,
 * not about the whole banner. Wave mode draws an envelopes list beneath it whose height is the
 * number of open orders, and that number changes when a read changes the orders: an order filled
 * here keeps its row (`done`), but one another device fills, or one whose last copy leaves the
 * store, simply goes. So the walk below can move by 48px on a re-read in wave mode. Order mode is
 * the constant-height case and is the one the measurements in the stylesheet were taken in.
 *
 * WHAT THE ROW'S OWN RULE BUYS, which is D28's rule about a screen
 * moving under a finger, applied to the strip above a walk somebody is arrowing through. Every
 * child is `flex: none` except the card name, which ellipsises; `flex-wrap: nowrap` makes that
 * structural rather than a promise in a comment — the same ruling D39 made about the header row
 * one node above. Measured in a browser at 1280 on 2026-09-02: the banner is 50px in every
 * state and the row does not overflow. The stylesheet carries the numbers and what to re-measure.
 *
 * NO `--accent` FILL, AND THE ARGUMENT IS docs/DESIGN.md'S OWN. The fill is for a screen whose
 * state reduces to ONE action — D29's group confirm, D33's spending press that does not exist
 * until a preflight has answered. At no moment here is the state one action: `Not here`, `Take
 * this one instead`, `Retire`, the walk itself and `Stop walking` are all live beside the
 * envelope. A fill drawn from stop 1 on a button that should not yet be pressed teaches the
 * colour to mean "the important one", which is the drift that ends with accent meaning nothing.
 * The end of an order is carried structurally instead: the arrows stop, the counter reads `n of
 * n`, the envelope is the only bordered control on the row, and a further Right press moves
 * FOCUS to it (`atEnd` below) so the keyboard has a way to feel the end that the eye already has.
 */

/** One order's envelope as the screen counts it: the lines the press would send, how many copies
 *  that is, how many the ledger still owes, and the two shortfalls a person has to see before
 *  they press — copies the resolver never found, and copies they said were not in the drawer. */
export type EnvelopeView = {
  readonly envelope: Envelope
  readonly lines: readonly FillLine[]
  readonly count: number
  readonly owed: number
  readonly short: number
  readonly notHere: number
}

/** An envelope already recorded in this session, kept in the list rather than vanishing from
 *  under the hand. It leaves the queue the moment its lines are filled (they owe nothing), and a
 *  row disappearing at the instant it is pressed is the defect D28 is about. */
export type FilledEnvelope = { readonly orderKey: string; readonly order: string; readonly count: number }

/** What the banner needs about the stop the walk is standing on. Computed by the screen from the
 *  same `targetsOf` the press uses, so the figure on the banner and the figure in the button
 *  cannot disagree. */
export type StopFacts = { readonly take: number; readonly short: number; readonly notHere: number }

export function OrderWalkBanner({
  ask,
  queue,
  stop,
  facts,
  envelopes,
  done,
  sequence,
  filling,
  note,
  reading,
  failed,
  filled,
  next,
  busy,
  offStop,
  atEnd,
  onFill,
  onStop,
  onBackToStop,
}: {
  ask: NonNullable<WalkAsk>
  queue: Queue | null
  stop: Stop | null
  facts: StopFacts | null
  envelopes: readonly EnvelopeView[]
  done: readonly FilledEnvelope[]
  /** The order the envelope rows are drawn in, fixed for the session by the screen. A filled
   *  envelope must not slide the ones below it up into the rectangle a finger is travelling to. */
  sequence: readonly string[]
  /** Which envelope is being written, or null. NOT `busy`: that is screen-wide and set by every
   *  write on this screen, and a button that says `Marking 3 sold…` while a RETIREMENT is in
   *  flight is announcing a sale that is not happening, in the one register that must never be
   *  wrong. */
  filling: string | null
  /** The fall-through: the URL named an order the ledger does not hold. */
  note: string | null
  reading: boolean
  failed: boolean
  /** In order mode, the order once it owes nothing — filled through this walk or elsewhere. */
  filled: OrderRow | null
  next: { readonly href: string; readonly number: string } | null
  busy: boolean
  /** The walk is pointing at a card that is not this stop's copy — a click or a search took it
   *  there. The way back is one press rather than Right-then-Left, which nobody would find. */
  offStop: boolean
  /** Bumped when a Right press at the last stop had nowhere to go. Moves focus to the envelope,
   *  which is the one moment this mode moves focus at all. */
  atEnd: number
  onFill: (view: EnvelopeView) => void
  onStop: () => void
  onBackToStop: () => void
}) {
  const fillRef = useRef<HTMLButtonElement | null>(null)
  const cued = useRef(atEnd)
  useEffect(() => {
    if (cued.current === atEnd) return
    cued.current = atEnd
    fillRef.current?.focus()
  }, [atEnd])

  /* THE FALL-THROUGH IS NOT A BANNER. A link naming an order the ledger does not hold has no
     order to describe, so it draws the screen's own note — the same panel a refusal uses — and
     the walk is the plain walk beneath it. */
  if (note !== null) {
    return (
      <div className="inventory-note">
        <p className="inventory-note-text">{note}</p>
        <p className="inventory-machine">order_not_walkable</p>
      </div>
    )
  }

  const at = stop === null || queue === null ? 0 : queue.stops.findIndex((one) => one.id === stop.id) + 1
  const total = queue?.stops.length ?? 0
  const own = stop === null ? null : envelopes.find((view) => view.envelope.orderKey === stop.orderKey) ?? null
  const orderNumber = stop?.order ?? filled?.number ?? envelopes[0]?.envelope.order ?? null
  const orderKey = stop?.orderKey ?? filled?.key ?? envelopes[0]?.envelope.orderKey ?? ''
  const stranded = queue?.unfillable.length ?? 0

  /* THE ROWS, IN THE SCREEN'S FIXED ORDER. A key the sequence has not seen yet is appended rather
     than dropped, so a first paint never loses a row to a race. */
  const openBy = new Map(envelopes.map((view) => [view.envelope.orderKey, view] as const))
  const doneBy = new Map(done.map((one) => [one.orderKey, one] as const))
  const keys = [...sequence]
  for (const key of [...openBy.keys(), ...doneBy.keys()]) if (!keys.includes(key)) keys.push(key)
  const rows = keys
    .map((key) => ({ key, view: openBy.get(key) ?? null, done: doneBy.get(key) ?? null }))
    .filter((row) => row.view !== null || row.done !== null)

  return (
    <section className="inventory-walk" aria-label="Order walk" data-mode={ask.kind}>
      <div className="inventory-walk-row">
        {reading ? (
          <p className="inventory-walk-said">Reading the orders.</p>
        ) : failed ? (
          <p className="inventory-walk-said">The orders could not be read.</p>
        ) : filled !== null ? (
          <>
            <p className="inventory-walk-said">
              Order <span className="inventory-inline">{filled.number}</span> is filled
              {next === null ? ', and no other order is open.' : '.'}
            </p>
            {next === null ? null : (
              /* ON THE LEFT, NEVER WHERE THE ENVELOPE WAS. The Fulfiller's screen paid for this
                 rule once — a control appearing under a finger already travelling toward the last
                 one. The envelope's rectangle is left empty and `Stop walking` keeps the far edge
                 it has held all along. */
              <a className="inventory-plain inventory-walk-next" href={next.href}>
                Walk the next order
              </a>
            )}
          </>
        ) : (
          <>
            <span className="inventory-walk-key">
              {ask.kind === 'wave' ? (stop === null ? 'walking' : 'for order') : 'walking order'}
            </span>
            {ask.kind === 'wave' && stop === null ? (
              <>
                <span className="inventory-walk-count">{envelopes.length}</span>
                <span className="inventory-walk-key">open orders</span>
              </>
            ) : orderNumber === null ? null : (
              /* The number alone: the source is on `#/orders` and costs more of this row than a
                 second marketplace is worth today. The whole key is on the title, which is the
                 one place the two could ever be told apart. */
              <span className="inventory-walk-order" title={orderKey}>
                {orderNumber}
              </span>
            )}

            {total === 0 || stop === null ? null : (
              <>
                <span className="inventory-walk-key">stop</span>
                <span className="inventory-walk-count">
                  {at} of {total}
                </span>
                <span className="inventory-walk-name">{stop.name ?? stop.sku}</span>
                {offStop ? (
                  <button className="inventory-walk-quiet" type="button" onClick={onBackToStop}>
                    Back to the stop
                  </button>
                ) : null}
                <span className="inventory-walk-key">take</span>
                <span className="inventory-walk-count">{facts?.take ?? 0}</span>
                {facts !== null && facts.short > 0 ? (
                  <span className="inventory-walk-key">{facts.short} short</span>
                ) : null}
                {facts !== null && facts.notHere > 0 ? (
                  <span className="inventory-walk-key">{facts.notHere} not here</span>
                ) : null}
              </>
            )}

            {total === 0 && stop === null && envelopes.length === 0 && done.length > 0 ? (
              <p className="inventory-walk-said">Every open order is filled.</p>
            ) : null}
            {total === 0 && stop === null && ask.kind === 'order' && envelopes.length === 0 ? (
              <p className="inventory-walk-said">Nothing the walk can reach.</p>
            ) : null}

            {stranded === 0 ? null : (
              <a className="inventory-walk-quiet inventory-walk-stranded" href="#/orders">
                {stranded} {stranded === 1 ? 'line' : 'lines'} cannot be walked
              </a>
            )}
            {ask.kind === 'order' && next !== null && total === 0 && envelopes.length === 0 ? (
              <a className="inventory-plain inventory-walk-next" href={next.href}>
                Walk the next order
              </a>
            ) : null}
          </>
        )}

        {/* THE END CLUSTER, RIGHT-PACKED, AND `Stop walking` IS ALWAYS ITS LAST CHILD. The
            envelope sits to its left, so when the envelope goes the exit does not move into the
            rectangle a finger was aiming at. And the exit is QUIET rather than bordered: two
            bordered controls side by side put the way out one mis-press from the write. */}
        <span className="inventory-walk-end">
          {ask.kind === 'order' && own !== null ? (
            <FillButton
              view={own}
              busy={busy}
              filling={filling === own.envelope.orderKey}
              onFill={onFill}
              innerRef={fillRef}
            />
          ) : null}
          <button className="inventory-walk-quiet" type="button" onClick={onStop} disabled={busy}>
            Stop walking
          </button>
        </span>
      </div>

      {/* ------------------------------------------------------- wave mode: one row per envelope */}
      {ask.kind !== 'wave' || rows.length === 0 ? null : (
        <ol className="inventory-walk-envelopes" aria-label="Envelopes">
          {rows.map((row) =>
            row.view !== null ? (
              <li
                key={row.key}
                className="inventory-walk-envelope"
                aria-current={stop !== null && stop.orderKey === row.key ? 'true' : undefined}
              >
                <span className="inventory-walk-order" title={row.key}>
                  {row.view.envelope.order}
                </span>
                <span className="inventory-walk-key">
                  {row.view.envelope.stops.length} {row.view.envelope.stops.length === 1 ? 'line' : 'lines'}
                </span>
                <span className="inventory-walk-count">{row.view.count}</span>
                <span className="inventory-walk-key">in hand</span>
                {row.view.short > 0 ? (
                  <span className="inventory-walk-key">{row.view.short} short</span>
                ) : null}
                {row.view.notHere > 0 ? (
                  <span className="inventory-walk-key">{row.view.notHere} not here</span>
                ) : null}
                <span className="inventory-walk-end">
                  <FillButton
                    view={row.view}
                    busy={busy}
                    filling={filling === row.key}
                    onFill={onFill}
                    /* THE END-OF-QUEUE CUE LANDS ON THE ORDER BEING WALKED, which in wave mode is
                       this row rather than the main one — the main row draws no envelope there. */
                    innerRef={stop !== null && stop.orderKey === row.key ? fillRef : null}
                  />
                </span>
              </li>
            ) : (
              <li key={row.key} className="inventory-walk-envelope inventory-walk-envelope-done">
                <span className="inventory-walk-order" title={row.key}>
                  {row.done?.order}
                </span>
                <span className="inventory-walk-key">
                  {row.done?.count} {row.done?.count === 1 ? 'copy' : 'copies'} marked sold
                </span>
                {/* IN THE BUTTON'S OWN FOOTPRINT, so a second press lands on a word rather than on
                    whatever slid into the rectangle. The undo is on the receipt. */}
                <span className="inventory-walk-end">
                  <span className="inventory-walk-filled">filled</span>
                </span>
              </li>
            ),
          )}
        </ol>
      )}

    </section>
  )
}

/** The envelope press. Its label carries the count, so the glance and the press agree and the
 *  verb keeps its name from `Envelope filled` through `Marking…` to `filled`. Disabled with
 *  nothing to record, and the reason IS the label — a row this tight has no room for a second
 *  span, and every excluded copy already reads `not here` with a `Back in` beside it. */
function FillButton({
  view,
  busy,
  filling,
  onFill,
  innerRef,
}: {
  view: EnvelopeView
  busy: boolean
  filling: boolean
  onFill: (view: EnvelopeView) => void
  innerRef: React.RefObject<HTMLButtonElement | null> | null
}) {
  const nothing = view.count === 0
  return (
    <button
      ref={innerRef}
      className="inventory-plain inventory-walk-fill"
      type="button"
      /* DISABLED BY ANY WRITE, LABELLED BY THIS ONE. Every write on this screen takes the same
         screen-wide gate, so all of them must disable the press; only this envelope's own write
         may say it is marking anything. */
      disabled={busy || nothing}
      aria-busy={filling ? 'true' : undefined}
      onClick={() => onFill(view)}
      data-order={view.envelope.order}
    >
      {filling
        ? `Marking ${view.count} sold…`
        : nothing
          ? /* THE REASON IS THE LABEL, so it may not name the wrong one. `owed` is what the ledger
               wants, not what the operator excluded — a line owed three with one copy in the store
               that was then marked not-here read `all 3 not here` over one press. */
            'Nothing to mark — no copy in hand'
          : `Envelope filled — mark ${view.count} of ${view.owed} sold`}
    </button>
  )
}
