import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { PositionLabel } from './PositionLabel'
import { readPaste, DEFAULT_ORDER_SOURCE } from './orderPaste'
import { ORDER_REASONS, orderReasonLabel, orderReasonRemedy } from './orderReasons'
import {
  describeFailure,
  fetchOrders,
  getOrders,
  ingestOrders,
  previewOrders,
  pullCopy,
  undoPull,
} from './server'
import type { Failure } from './server'
import type {
  OrderLineReason,
  OrderRow,
  OrdersFetched,
  OrdersPayload,
  OrdersPreview,
  PickRow,
  PullTarget,
  ResolvedLine,
  ResolvedOrder,
} from './types'
import './Orders.css'

/* THE ORDER SCREEN — which copies this buyer gets, and where they are (D69).
 *
 * ONE READ ANSWERS BOTH HALVES. `GET /orders` computes the order list and the resolution out of
 * ONE store snapshot, and this screen makes exactly one call for the pair. Two calls could
 * straddle a sale and draw a card both on hand and gone, and the server's own docstring records
 * that as the reason the route is shaped this way; a screen that fetched the two halves
 * separately would have thrown that guarantee away at the last inch.
 *
 * THE PULL IS ONE CARD AND ONE PRESS, AIMED BY THE ROW'S OWN `capture_id`. The route takes a
 * list because `record_pull` takes a sequence, not because a screen should offer a batch — and
 * the aim check is what makes the press safe: a mid-box delete, a capture undo or a re-shoot all
 * change which physical card sits at a slot (D10 ruling 1, D58), and the server refuses
 * `capture_id_mismatch` rather than selling whatever is there now. So the button sends the
 * `capture_id` the row was DRAWN from, never a re-read of the position.
 *
 * THE UNDO LIVES ON THE RECEIPT AND NOT ON THE ROW, and that is forced rather than chosen. A
 * successful pull marks the copy sold, so the next resolution does not offer it — the row
 * unmounts, and an Undo drawn inside it would go with it. The receipt outlives the list.
 *
 * THE RECEIPT READS `places[0]`, NEVER `sales[0].card.place.label`. The places come back AS THEY
 * WERE BEFORE THE WRITE, one per target in request order. A sale moves the box's occupancy (D58
 * — the numbers count the cards, not the slots), so by the time the answer is composed the card
 * has departed and its own label reads `Box 3 · departed`: the operator would be told where they
 * are about to be rather than where they just were.
 *
 * WHAT THIS SCREEN IS NOT:
 *
 *   IT DRAWS NO POSTAGE LANE. Which envelope an order ships in is D61's ruling and `#/shipping`'s
 *   answer, computed from a file TCGplayer exports and this ledger has never seen. An envelope
 *   badge here would be a second answer to a settled question, drawn from data that cannot
 *   answer it.
 *
 *   IT SPENDS NOTHING. `POST /pipeline/identify` is still the one route in this product that can
 *   cause a charge. The fetch below is a free read against the account's own order host.
 *
 *   IT KEEPS NOTHING. The paste lives in React state while the screen is open and nowhere else —
 *   no browser store of any kind, because an unsent paste is a buyer's order sitting in a
 *   browser and D13 puts the one truth on the Mac.
 */

/** How long a receipt's undo stays. Twenty seconds, which is `Inventory.tsx`'s number and
 *  `Fulfillment.tsx`'s before it — not a third opinion about the same question. If it is ever
 *  measured it moves in all three files together. */
const UNDO_WINDOW_MS = 20_000

/** One thing that happened, with its way back. `target` is what an undo sends, and it is the
 *  pre-write aim rather than anything re-read afterwards. */
type Receipt = {
  key: string
  /** The place AS IT WAS BEFORE THE WRITE — see the header. */
  place: string
  order: string
  sku: string
  target: PullTarget
  until: number
  /** False once the undo has been taken, so a second press cannot reverse a reversal. */
  reversible: boolean
  /** A refusal from this receipt's own undo, drawn on the receipt rather than screen-wide, so
   *  it cannot outlive the button it is about. */
  trouble: Failure | null
}

/** Everything a pick needs to be pulled, gathered where the row is drawn. A pick with no
 *  `capture_id` cannot be aimed at and is offered as a location rather than as a button — the
 *  server refuses `copy_not_identifiable` for exactly that record, and refusing it here says so
 *  before the press instead of after. */
function aimOf(line: ResolvedLine, pick: PickRow): PullTarget | null {
  if (pick.capture_id === null || pick.capture_id.trim() === '') return null
  if (line.reason !== 'resolved' && line.reason !== 'short') return null
  return { box: pick.box, index: pick.index, capture_id: pick.capture_id }
}

/** The counts a line carries beside its reason, as one line, with every part drawn including the
 *  zeros. A breakdown that hid its zeros would make "none were sold" and "nobody counted"
 *  the same sentence, which is the argument `Resolution.counts` makes one level up. */
function breakdownOf(line: ResolvedLine): string {
  return [
    `${line.on_hand} on hand`,
    `${line.sold} sold`,
    `${line.retired} retired`,
    `${line.pooled} pooled`,
  ].join(' · ')
}

/** The paste note after a fetch: what was added, what was detailed, and what the cap left.
 *  `remaining` is named rather than swallowed — the transport counted those orders and stopped
 *  detailing at its budget, and the next press picks them up (D91). */
function fetchNote(found: OrdersFetched, ingested: string | null): string {
  const parts = [ingested ?? 'Nothing new to add.']
  parts.push(
    `${found.detailed} of ${found.matched} matching ${found.matched === 1 ? 'order' : 'orders'} detailed` +
      (found.skipped_known > 0 ? `, ${found.skipped_known} already in the ledger.` : '.'),
  )
  if (found.remaining > 0) parts.push(`${found.remaining} remaining — press again for the rest.`)
  return parts.join(' ')
}

export function Orders() {
  const [payload, setPayload] = useState<OrdersPayload | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [paste, setPaste] = useState('')
  const [pasteNote, setPasteNote] = useState<string | null>(null)
  const [dropped, setDropped] = useState<string[]>([])
  const [receipts, setReceipts] = useState<Receipt[]>([])
  const [showDone, setShowDone] = useState(false)
  /* THE WINDOW BY STATUS, AND WHICH STATUSES ARE TICKED (D91). Both are this press's and are
     remembered nowhere: a status string is TCGplayer's word for an order's state, seen on the
     wire and drawn verbatim, and which of them mean "needs picking" is the operator's tick each
     time rather than a vocabulary this file holds. */
  const [preview, setPreview] = useState<OrdersPreview | null>(null)
  const [ticked, setTicked] = useState<string[]>([])
  /* THE WAY IN, OPEN OR SHUT. Its CONTROL is in the header at every state and never moves; only
     the panel's disclosure changes. What decides the initial state is whether the ledger has
     anything in it: an empty ledger has no work to do, so the screen draws its own way in
     rather than a blank, and a ledger with orders in it puts the WORK first — the six counts
     and the pick lists — because a paste box above them costs about 180px on every arrival for
     an errand that happens once a batch. `null` is "the read has not answered yet", which is
     what stops the panel flashing open before the first payload lands. */
  const [arriving, setArriving] = useState<boolean | null>(null)
  const live = useRef(true)

  useEffect(() => {
    live.current = true
    return () => {
      live.current = false
    }
  }, [])

  /* ONE CALL FOR BOTH HALVES — see the header. Every write on this screen ends by calling this
     again, because a pull changes the resolution of every OTHER line that wanted the same SKU:
     the resolver is a one-pass allocation over the whole open set, and re-drawing only the row
     that was pressed would leave two other buyers still being offered a card that has left. */
  const reread = useCallback(async () => {
    try {
      const answer = await getOrders()
      if (!live.current) return
      setPayload(answer)
      setArriving((was) => (was === null ? answer.orders.length === 0 : was))
      setFailure(null)
    } catch (err) {
      if (!live.current) return
      setFailure(describeFailure(err))
    }
  }, [])

  useEffect(() => {
    void reread()
  }, [reread])

  /* ONE TIMER FOR THE WHOLE LIST, armed at the soonest deadline — `Inventory.tsx`'s shape, slack
     and all. The 25ms is its finding rather than a rounding: a timer that fired a hair early
     drops nothing, returns an array of the same length, and React bails out on the identical
     reference, leaving the receipt up forever with nothing left to re-arm it. */
  useEffect(() => {
    if (receipts.length === 0) return
    const soonest = Math.min(...receipts.map((receipt) => receipt.until))
    const timer = window.setTimeout(
      () =>
        setReceipts((held) => {
          const standing = held.filter((receipt) => receipt.until > Date.now())
          return standing.length === held.length ? held : standing
        }),
      Math.max(0, soonest - Date.now()) + 25,
    )
    return () => window.clearTimeout(timer)
  }, [receipts])

  const remember = useCallback((receipt: Omit<Receipt, 'until'>) => {
    setReceipts((held) => [
      { ...receipt, until: Date.now() + UNDO_WINDOW_MS },
      ...held.filter((standing) => standing.key !== receipt.key),
    ])
  }, [])

  /* ---------------------------------------------------------------------- orders arrive */

  /* THE PASTE IS PROJECTED BEFORE IT IS SENT, AND THE PROJECTION IS `orderPaste.ts`'s ALONE.
     Nothing here composes an ingest body field by field: this reads what came back and hands
     `reading.orders` to `ingestOrders` verbatim, so there is exactly one place in the app that
     decides what leaves the browser about a purchase. What was DROPPED is drawn beside the
     press, because a silent strip is indistinguishable on screen from a feed that never carried
     the field — and the operator would have no way to tell a working PII boundary from a broken
     one. */
  const onRead = () => {
    const reading = readPaste(paste)
    if (!reading.ok) {
      setPasteNote(reading.problem)
      setDropped([])
      return
    }
    setPasteNote(null)
    setDropped(reading.dropped)
    void (async () => {
      setBusy('ingest')
      setFailure(null)
      try {
        const done = await ingestOrders(reading.orders)
        if (!live.current) return
        setPaste('')
        /* `wrote_nothing` IS THE HONEST ANSWER TO "did that work" for a second identical paste.
           `Ledger.ingest` carries `first_seen` across and stamps `changed_at` only where
           something moved, so the second press rewrites nothing at all — and a screen that said
           "3 orders ingested" both times would teach the operator to paste twice to be sure. */
        setPasteNote(done.summary)
        await reread()
      } catch (err) {
        if (!live.current) return
        setFailure(describeFailure(err))
      } finally {
        if (live.current) setBusy(null)
      }
    })()
  }

  /* THE FETCH IS TWO PRESSES SINCE D91, BECAUSE ONE PRESS NEVER WORKED ON THIS ACCOUNT. The
     three-month window holds 370 orders against a detail cap of 100, and the single-body fetch
     was refused every time it was pressed. `Check TCGplayer` walks the search pages — one
     request per 25 orders, no detail call, nothing written — and draws the window by the status
     STRING the wire returned, with how many of each the ledger already holds. `Fetch N orders`
     details only the statuses ticked, skipping what the ledger holds unchanged.

     THE RESULT STILL ENTERS THROUGH THE SAME ONE DOOR THE PASTE DOES. `POST /orders/fetch`
     answers EXACTLY the body `POST /orders/ingest` accepts in `orders`, so the array is sent on
     unaltered rather than adapted here — that shape is the whole reason the transport was given
     its own route instead of writing the ledger itself. Free: it reads the account's own order
     host with the session already in `.env` and writes nothing at all, not even the ledger. */
  const onCheck = () => {
    void (async () => {
      setBusy('check')
      setFailure(null)
      setPasteNote(null)
      setDropped([])
      try {
        const found = await previewOrders()
        if (!live.current) return
        setPreview(found)
        setTicked([])
        if (found.total === 0) setPasteNote(`The ${found.range} window holds no orders.`)
      } catch (err) {
        if (!live.current) return
        setFailure(describeFailure(err))
      } finally {
        if (live.current) setBusy(null)
      }
    })()
  }

  const onFetch = () => {
    void (async () => {
      setBusy('fetch')
      setFailure(null)
      setPasteNote(null)
      setDropped([])
      try {
        const found = await fetchOrders({ statuses: ticked, skip_known: true })
        if (!live.current) return
        const done = found.orders.length === 0 ? null : await ingestOrders(found.orders)
        if (!live.current) return
        setPasteNote(fetchNote(found, done?.summary ?? null))
        /* RE-READ EITHER WAY. An empty fetch used to return before this line, so a ledger
           another device had just moved stayed stale behind a note saying nothing happened. */
        await reread()
      } catch (err) {
        if (!live.current) return
        setFailure(describeFailure(err))
      } finally {
        if (live.current) setBusy(null)
      }
    })()
  }

  /* WHAT THE TICKS ADD UP TO, for the button's own label: the matching orders the ledger does
     not already hold at that status, which is exactly what `skip_known` will detail. */
  const toFetch = useMemo(
    () =>
      preview === null
        ? 0
        : preview.by_status
            .filter((row) => ticked.includes(row.status))
            .reduce((sum, row) => sum + Math.max(0, row.count - row.known), 0),
    [preview, ticked],
  )

  const onPull = (order: OrderRow, line: ResolvedLine, pick: PickRow, target: PullTarget) => {
    void (async () => {
      setBusy(`${line.order_key}/${line.sku}/${target.capture_id}`)
      setFailure(null)
      try {
        const done = await pullCopy(
          { source: order.source, number: order.number, sku: line.sku },
          [target],
        )
        if (!live.current) return
        remember({
          key: target.capture_id,
          /* `places[0]`, NEVER `sales[0].card.place.label` — see the header. The `?.` is what
             `noUncheckedIndexedAccess` requires of every index in this app, and the fallback is
             the pre-press label rather than an invented one: if the server ever answered a
             shorter array than it was sent, a receipt saying nothing at all is worse than the
             place the row was drawn at. */
          place: done.places[0]?.label ?? pick.place.label ?? `box ${target.box}, index ${target.index}`,
          order: order.number,
          sku: line.sku,
          target,
          reversible: true,
          trouble: null,
        })
        await reread()
      } catch (err) {
        if (!live.current) return
        setFailure(describeFailure(err))
      } finally {
        if (live.current) setBusy(null)
      }
    })()
  }

  /* THE UNDO NAMES NO LINE AND CANNOT. The server scans the ledger for whoever holds each
     `capture_id` — the one identity a renumber cannot move — and refuses a body that also names
     an order rather than obeying it with the order ignored. So this sends the target and
     nothing else. */
  const onUndo = (receipt: Receipt) => {
    void (async () => {
      setBusy(`undo/${receipt.key}`)
      try {
        await undoPull([receipt.target])
        if (!live.current) return
        setReceipts((held) =>
          held.map((one) => (one.key === receipt.key ? { ...one, reversible: false, trouble: null } : one)),
        )
        await reread()
      } catch (err) {
        if (!live.current) return
        const trouble = describeFailure(err)
        setReceipts((held) =>
          held.map((one) => (one.key === receipt.key ? { ...one, trouble } : one)),
        )
      } finally {
        if (live.current) setBusy(null)
      }
    })()
  }

  /* --------------------------------------------------------------------- what is drawn */

  const counts = payload?.resolution.counts ?? null

  /** The resolution, keyed so a row can find its own. `Map` rather than a `find` per row: the
   *  open set is the whole day's work and the list is drawn on every re-read. */
  const answers = useMemo(() => {
    const out = new Map<string, ResolvedOrder>()
    for (const one of payload?.resolution.orders ?? []) out.set(one.key, one)
    return out
  }, [payload])

  /* THE OPEN/DONE SPLIT IS `open`, WHICH IS THE LEDGER'S ANSWER — never the feed's `status`
     string. `store/orders.py` stores that string verbatim and unvalidated on purpose, because a
     marketplace that learns a new word must not be refused at the door, and NOTHING MAY BRANCH
     ON IT. Whether an order still owes copies is a question this store owns. */
  const orders = payload?.orders ?? []
  const open = orders.filter((one) => one.open)
  const done = orders.filter((one) => !one.open)

  return (
    <main className="screen orders">
      <header className="orders-head">
        <div className="orders-head-top">
          <h1 className="orders-title">Orders</h1>
          <div className="orders-controls">
            <span className="orders-scope">
              {payload === null ? 'Not read yet' : payload.summary}
            </span>
            <button
              type="button"
              className="orders-plain"
              aria-expanded={arriving === true}
              onClick={() => setArriving((was) => was !== true)}
            >
              {arriving === true ? 'Hide the way in' : 'Orders arrive'}
            </button>
          </div>
        </div>
        <p className="orders-lede">
          Which copies each buyer gets, and where in the boxes they are. Which envelope it ships
          in is the shipping screen&apos;s question.
        </p>
      </header>

      {failure === null ? null : (
        <div className="orders-note">
          <p className="orders-note-text">{failure.message}</p>
          <p className="orders-machine">{failure.code}</p>
        </div>
      )}

      {/* ------------------------------------------------------------------ the receipts */}
      {receipts.length === 0 ? null : (
        <ol className="orders-receipts">
          {receipts.map((receipt) => (
            <li key={receipt.key} className="orders-receipt">
              <span className="orders-receipt-text">
                {receipt.reversible
                  ? `Pulled from ${receipt.place} for order ${receipt.order}.`
                  : `Put back to ${receipt.place}.`}
              </span>
              {receipt.reversible ? (
                <button
                  type="button"
                  className="orders-plain"
                  onClick={() => onUndo(receipt)}
                  disabled={busy !== null}
                >
                  Undo
                </button>
              ) : null}
              {receipt.trouble === null ? null : (
                <span className="orders-machine">{receipt.trouble.code}</span>
              )}
            </li>
          ))}
        </ol>
      )}

      {/* --------------------------------------------------------------- orders arrive */}
      {arriving !== true ? null : (
      <section className="orders-paste">
        <p className="orders-paste-head">Paste an order</p>
        <textarea
          className="orders-paste-box"
          value={paste}
          onChange={(event) => setPaste(event.target.value)}
          disabled={busy !== null}
          rows={4}
          placeholder={'{"source": "TCGplayer", "number": "…", "lines": [{"sku": "…", "quantity": 1}]}'}
          aria-label="Order JSON"
        />
        <div className="orders-paste-row">
          <button type="button" className="orders-plain" onClick={onRead} disabled={busy !== null}>
            Read this paste
          </button>
          {/* THE FETCH IS BEHIND THE SAME CONTROL AS THE PASTE, because it is the same errand
              with the copying done for you: `POST /orders/fetch` answers EXACTLY the body the
              ingest accepts, and both arrive at the ledger through the one door
              `orderPaste.ts` owns. A fetch button in the page header would say this screen has
              two ways in when it has one way in and two sources. */}
          <button type="button" className="orders-plain" onClick={onCheck} disabled={busy !== null}>
            {busy === 'check' ? 'Checking…' : 'Check TCGplayer'}
          </button>
          <span className="orders-paste-source">
            Anything that does not name a source is stamped {DEFAULT_ORDER_SOURCE}.
          </span>
        </div>
        {/* THE WINDOW BY STATUS, TICKED BY HAND (D91). Every row is a string TCGplayer used,
            drawn verbatim — an empty one is drawn as the absence it is — with how many orders
            carry it and how many of those the ledger already holds. Nothing is pre-ticked: which
            statuses mean "needs picking" is the one thing about this feed nobody has enumerated,
            and a default here would be that guess made silently on every press. */}
        {preview === null ? null : (
          <div className="orders-statuses" role="group" aria-label="Which statuses to fetch">
            <p className="orders-statuses-head">
              {preview.total} {preview.total === 1 ? 'order' : 'orders'} in the {preview.range}{' '}
              window, by the status TCGplayer gave them. Tick the ones to fetch.
            </p>
            {preview.by_status.length === 0 ? null : (
              <ul className="orders-status-list">
                {preview.by_status.map((row) => (
                  <li key={row.status} className="orders-status">
                    <label className="orders-status-pick">
                      <input
                        type="checkbox"
                        checked={ticked.includes(row.status)}
                        disabled={busy !== null}
                        onChange={(event) =>
                          setTicked((was) =>
                            event.target.checked
                              ? [...was, row.status]
                              : was.filter((one) => one !== row.status),
                          )
                        }
                      />
                      <span className="orders-status-name">
                        {row.status === '' ? 'no status' : row.status}
                      </span>
                      <span className="orders-status-count">
                        {row.count} · {row.known} in the ledger
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            )}
            <button
              type="button"
              className="orders-plain orders-fetch"
              onClick={onFetch}
              disabled={busy !== null || ticked.length === 0}
            >
              {busy === 'fetch'
                ? 'Fetching…'
                : `Fetch ${toFetch} ${toFetch === 1 ? 'order' : 'orders'}`}
            </button>
          </div>
        )}
        {pasteNote === null ? null : <p className="orders-paste-note">{pasteNote}</p>}
        {/* WHAT WAS DROPPED, NAMED. A silent strip cannot be told apart on screen from a feed
            that never carried the field, and this line is how the operator sees the PII boundary
            working rather than trusting it. */}
        {dropped.length === 0 ? null : (
          <p className="orders-paste-dropped">
            Not sent: {dropped.join(', ')}. Only the SKU, the count and what the feed called the
            card leave this browser.
          </p>
        )}
      </section>
      )}

      {/* ------------------------------------------------------------------ the tally */}
      {counts === null ? null : (
        /* ALL SIX REASONS, INCLUDING THE ZEROS. `Resolution.counts` returns every one and
           nothing here filters them — reporting only what fired would make "nothing was short"
           and "nothing was checked" the same screen. `sku_unknown` is structurally unreachable
           from this route and always draws a zero; that is a limit of the route rather than a
           fact about the store, and the sentence below says so. */
        <div className="orders-counts" aria-label="Why each line answered as it did">
          {ORDER_REASONS.map((reason) => (
            <span key={reason} className={`orders-count orders-count-${reason}`}>
              <span className="orders-count-label">{orderReasonLabel(reason)}</span>
              <span className="orders-count-machine">{reason}</span>
              <span className="orders-count-figure">{counts[reason as OrderLineReason]}</span>
            </span>
          ))}
        </div>
      )}

      {orders.length === 0 ? (
        <p className="orders-empty">
          No orders in the ledger. Paste one in, or fetch this account&apos;s own from
          TCGplayer.
        </p>
      ) : (
        <>
          <ol className="orders-list">
            {open.length === 0 ? (
              <li className="orders-empty">Nothing outstanding. Every order has its copies.</li>
            ) : (
              open.map((order) => (
                <OrderCard
                  key={order.key}
                  order={order}
                  answer={answers.get(order.key) ?? null}
                  busy={busy}
                  onPull={onPull}
                />
              ))
            )}
          </ol>

          {/* THE DONE HALF IS COLLAPSED AND NOT DELETED. An order whose copies are all recorded
              is still the answer to "did I ship that", and the resolver does not compute one —
              `Ledger.unfulfilled` is what decides, and a fulfilled order is simply not in the
              resolution. So it is drawn as a row of facts with no pick list under it. */}
          <button
            type="button"
            className="orders-plain orders-done-toggle"
            aria-expanded={showDone}
            onClick={() => setShowDone((was) => !was)}
          >
            {showDone ? 'Hide' : 'Show'} {done.length} fulfilled
          </button>
          {showDone ? (
            <ol className="orders-list orders-list-done">
              {done.length === 0 ? (
                <li className="orders-empty">Nothing fulfilled yet.</li>
              ) : (
                done.map((order) => (
                  <li key={order.key} className="orders-order orders-order-done">
                    <div className="orders-order-top">
                      <span className="orders-order-number">{order.number}</span>
                      <span className="orders-order-source">{order.source}</span>
                      <span className="orders-order-figure">
                        {order.recorded} of {order.wanted} pulled
                      </span>
                    </div>
                  </li>
                ))
              )}
            </ol>
          ) : null}
        </>
      )}
    </main>
  )
}

/** One open order: what the buyer bought, and what the resolver could offer against it.
 *
 *  THE ANSWER MAY BE ABSENT AND THE ROW STILL DRAWS. Only `Ledger.unfulfilled()` orders are
 *  resolved, and the two lists are computed from one snapshot — but a row with no answer is a
 *  real possibility the type admits, and drawing nothing at all would make an unresolved order
 *  invisible rather than unexplained. */
function OrderCard({
  order,
  answer,
  busy,
  onPull,
}: {
  order: OrderRow
  answer: ResolvedOrder | null
  busy: string | null
  onPull: (order: OrderRow, line: ResolvedLine, pick: PickRow, target: PullTarget) => void
}) {
  return (
    <li className="orders-order">
      <div className="orders-order-top">
        <span className="orders-order-number">{order.number}</span>
        <span className="orders-order-source">{order.source}</span>
        <span className="orders-order-figure">
          {order.recorded} of {order.wanted} pulled
        </span>
        {order.placed_at === null ? null : (
          <span className="orders-order-placed">{order.placed_at}</span>
        )}
      </div>

      {answer === null ? (
        <p className="orders-line-remedy">
          This order is outstanding and was not resolved in this read. Re-read the screen.
        </p>
      ) : (
        <ol className="orders-lines">
          {answer.lines.map((line) => (
            <OrderLineRow
              key={`${line.order_key}/${line.sku}`}
              order={order}
              line={line}
              busy={busy}
              onPull={onPull}
            />
          ))}
        </ol>
      )}
    </li>
  )
}

/** One line, its reason, its remedy, and the copies it found. */
function OrderLineRow({
  order,
  line,
  busy,
  onPull,
}: {
  order: OrderRow
  line: ResolvedLine
  busy: string | null
  onPull: (order: OrderRow, line: ResolvedLine, pick: PickRow, target: PullTarget) => void
}) {
  const remedy = orderReasonRemedy(line.reason)
  return (
    <li className={`orders-line orders-line-${line.reason}`}>
      <div className="orders-line-top">
        <span className="orders-line-name">{line.line.name ?? line.sku}</span>
        <span className="orders-line-sku">{line.sku}</span>
        {/* FOUND OF OWED, THEN WHAT IS ALREADY PULLED. The resolver is asked for what the ledger
            still owes, so `fulfilled` is measured against `owed`; the buyer's number is the
            order's figure above, and the difference is what this line has already recorded. */}
        <span className="orders-line-figure">
          {line.fulfilled} of {line.owed}
          {line.owed < line.wanted ? ` · ${line.wanted - line.owed} pulled` : ''}
        </span>
      </div>

      {/* THE HUMAN LABEL LARGE, THE MACHINE STRING SMALL BENEATH IT — docs/DESIGN.md's rule, and
          `sku_unknown` / `sku_unseen` are the pair that pays for it: one letter apart as machine
          strings, and two completely different situations. */}
      <p className="orders-line-says">{orderReasonLabel(line.reason)}</p>
      <p className="orders-line-reason">{line.reason}</p>
      {remedy === '' ? null : <p className="orders-line-remedy">{remedy}</p>}
      <p className="orders-line-breakdown">{breakdownOf(line)}</p>

      {line.picks.length === 0 ? null : (
        <ol className="orders-picks">
          {line.picks.map((pick) => {
            const target = aimOf(line, pick)
            const key = pick.capture_id ?? `${pick.box}/${pick.index}`
            const pressing = target !== null && busy === `${line.order_key}/${line.sku}/${target.capture_id}`
            return (
              <li key={key} className="orders-pick">
                <span className="orders-pick-place">
                  {pick.place.label === null ? (
                    <span className="orders-pick-pooled">
                      {pick.place.game_display ?? 'pooled'} · pooled
                    </span>
                  ) : (
                    <PositionLabel label={pick.place.label} flow="run" lead="slot" />
                  )}
                </span>
                {pick.card_name === null ? null : (
                  <span className="orders-pick-card">{pick.card_name}</span>
                )}
                {/* SPOKEN FOR, DRAWN AS SUCH RATHER THAN OFFERED TWICE. `held_by` is the
                    request's own reverse index over `capture_id` and is never stored; it says
                    this exact card is already recorded against a line, and a screen that
                    offered it again would walk the picker to one drawer for two envelopes. */}
                {pick.held_by !== null ? (
                  <span className="orders-pick-held">
                    Spoken for by order {pick.held_by.order}
                  </span>
                ) : target === null ? (
                  <span className="orders-pick-held">
                    {pick.capture_id === null
                      ? 'No capture id, so this copy cannot be aimed at.'
                      : 'Not offered for this reason.'}
                  </span>
                ) : (
                  <button
                    type="button"
                    className="orders-plain orders-pull"
                    data-capture-id={target.capture_id}
                    onClick={() => onPull(order, line, pick, target)}
                    disabled={busy !== null}
                  >
                    {pressing ? 'Pulling…' : 'Pull this copy'}
                  </button>
                )}
              </li>
            )
          })}
        </ol>
      )}
    </li>
  )
}
