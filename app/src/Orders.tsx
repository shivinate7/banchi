import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react'

import { Button, EmptyState, Icon, Kbd, Notice, PageHeader, Pill, Segmented, type IconName, type PillTone } from './kit'
import { toast } from './kit/toast'
import { readPaste, DEFAULT_ORDER_SOURCE } from './orderPaste'
import { ORDER_REASONS, orderReasonLabel, orderReasonRemedy } from './orderReasons'
import { rememberOrderFilter, storedOrderFilter, type OrderFetchFilter } from './deviceMemory'
import { setHub, touchHub, useHub, type PullFilter, type PullMode, type Stage } from './OrdersHubStore'
import { PositionLabel } from './PositionLabel'
import {
  closeLines,
  closeOrders,
  declareLineKind,
  describeFailure,
  fetchOrders,
  fillLine,
  getInventory,
  getOrders,
  ingestOrders,
  previewOrders,
  pullCopy,
  reopenLines,
  reopenOrders,
  undoFill,
  undoPull,
} from './server'
import type { Failure } from './server'
import { ShipStage } from './OrdersShipStage'
import type {
  IngestResult,
  Inventory,
  InventoryCard,
  OrderCloseReason,
  OrderFillReason,
  OrderLineProgress,
  OrderLineReason,
  OrderRow,
  OrdersFetched,
  OrdersPayload,
  OrdersPreview,
  PickRow,
  Place,
  PullTarget,
  ResolvedLine,
  ResolvedOrder,
  ShippingLane,
} from './types'
import './Orders.css'

/* THE ORDERS HUB — one screen, two stages (D69).
 *
 *   ORDERS   which copies each buyer gets and where they are; one press per copy, aimed by the
 *            row's own `capture_id`, with twenty seconds to take it back. Worked one order at a
 *            time (a list beside the open order) or as one walk through the boxes.
 *   SHIPPING TCGplayer's Export Shipping file sorted into three lanes, and the Pirate Ship import.
 *
 * `#/orders` renders the hub with the first selected and `#/shipping` with the second; the tabs
 * move the hash, so bookmarks, the nav and the `,O` / `,S` chords all keep working. What each
 * stage knows of the other is a client-side join by order number and nothing is written across
 * the seam.
 *
 * ONE READ ANSWERS BOTH HALVES OF THE LEDGER. `GET /orders` computes the order list and the
 * resolution out of ONE store snapshot, and this screen makes exactly one call for the pair.
 *
 * THE PULL IS ONE CARD AND ONE PRESS, AIMED BY `capture_id`. A mid-box delete, a capture undo or
 * a re-shoot all change which physical card sits at a slot (D10, D58), and the server refuses
 * `capture_id_mismatch` rather than selling whatever is there now — so the button sends the id
 * the row was DRAWN from, never a re-read of the position.
 *
 * THE RECEIPT READS `places[0]`, NEVER `sales[0].card.place.label`. The places come back AS THEY
 * WERE BEFORE THE WRITE; by the time the answer is composed the card has departed and its own
 * label reads `Box 3 · departed`. The receipt is a toast because a successful pull unmounts the
 * row it was pressed on: the undo has to outlive the list.
 *
 * IT SPENDS NOTHING AND KEEPS NOTHING IN THE BROWSER'S STORAGE. The fetch is a free read of the
 * account's own order host; the paste and the selection live in the hub store while the tab is
 * open. */

/** How long a receipt's undo stays — `Inventory.tsx`'s number and `Fulfillment.tsx`'s. */
const UNDO_WINDOW_MS = 20_000

/* ---- what the fetch checked, took, and left ------------------------------------------- */

/* THE WINDOW HOLDS MORE THAN ONE CALL RETURNS, and until this receipt existed the remainder was
 * silent: the screen reported what it INGESTED, so 370 matching orders behind a cap of 100 read
 * as "100 orders" and a second press was a guess. The receipt is two parts — what was checked,
 * and what this press took out of it — and the control to take the next batch is drawn only
 * while the wire says something is left.
 *
 * IT IS A RECEIPT, NOT A WARNING. Nothing here went wrong; a cap is how the transport works.
 *
 * IT IS DRAWN IN PLACE RATHER THAN TOASTED, which is the one departure from "receipts are
 * toasts": this one carries the control that finishes the errand, and a receipt that expires
 * would put the remainder back in the dark it was built to leave.
 *
 * THE COUNTS ARE NOT ON THIS BRANCH'S WIRE. The merge brings them on `OrdersFetched` beside
 * `orders`: `matched` (the window), `skipped_known` (already in the ledger), `detailed` (what
 * this call detailed) and `remaining` (what its cap left). Each is read defensively below, and
 * a figure that is absent leaves its clause out rather than drawing a zero. */
type FetchCounts = {
  readonly matched?: number
  readonly skipped_known?: number
  readonly detailed?: number
  readonly remaining?: number
}

/** A count off the wire, or null where the wire does not carry one. Never a zero stood in for
 *  an absence: a drawn `0 remaining` is a claim, and this branch cannot make it. */
function wireCount(value: number | undefined): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? Math.max(0, Math.round(value)) : null
}

/** THIS DEVICE'S PREVIOUS CHECK, and nothing else, ever.
 *
 *  It is a per-device convenience — "how many are new since I last looked" is a question about
 *  this browser's own habit, not about the store — so `localStorage` is its right home and the
 *  ledger is not. No order, no SKU, no card: a timestamp and the size of the window as it was.
 *  Every read and write is guarded; a browser that refuses storage loses the "new since" clause
 *  and nothing else. */
const LAST_CHECK_KEY = 'banchi.orders.last-check'

/** `statuses` IS THE QUESTION THAT WAS ASKED, not the list that was sent. Null is "every
 *  status the window holds", which is what an operator who has never opened the picker is
 *  asking; the strings a window actually returns drift, and a comparison suppressed by that
 *  drift would be suppressed on most presses. What has to match for "new since" to mean
 *  anything is the SCOPE — 128 completed orders against 128 of everything is not a delta. */
type LastCheck = {
  readonly at: number
  readonly matched: number | null
  readonly statuses: readonly string[] | null
}

/** Whether two remembered scopes are the same question. Order-insensitive; null is its own
 *  value and never equal to a list, because "everything this window holds" is a different
 *  question from a list that happens to name everything today. */
function sameScope(a: readonly string[] | null, b: readonly string[] | null): boolean {
  if (a === null || b === null) return a === b
  if (a.length !== b.length) return false
  const held = new Set(a)
  return b.every((one) => held.has(one))
}

function readLastCheck(): LastCheck | null {
  try {
    /* eslint-disable-next-line no-restricted-syntax -- the owner's ruling of 2026-09-03: the
       "new since" comparison is a per-device convenience and belongs here. It is NOT inventory —
       no card, no position, no order — so the ban this rule enforces (D13/D27: one truth about a
       card, on the Mac) is not the thing being done. */
    const raw = window.localStorage.getItem(LAST_CHECK_KEY)
    if (raw === null) return null
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) return null
    const at = (parsed as { at?: unknown }).at
    if (typeof at !== 'number' || !Number.isFinite(at)) return null
    const matched = (parsed as { matched?: unknown }).matched
    const scope = (parsed as { statuses?: unknown }).statuses
    return {
      at,
      matched: typeof matched === 'number' && Number.isFinite(matched) ? matched : null,
      /* A check written before D114 carries no scope. Absent reads as null — "everything" —
         which is exactly what that press asked for, so an upgrade does not invent a mismatch. */
      statuses: Array.isArray(scope) ? scope.filter((one): one is string => typeof one === 'string') : null,
    }
  } catch {
    /* Private mode, a blocked origin, a half-written value: no previous check, which the receipt
       draws as the first one on this device. */
    return null
  }
}

function writeLastCheck(next: LastCheck): void {
  try {
    /* eslint-disable-next-line no-restricted-syntax -- see `readLastCheck`. */
    window.localStorage.setItem(LAST_CHECK_KEY, JSON.stringify(next))
  } catch {
    /* Quota or a blocked origin. The receipt this press drew is already right; only the NEXT
       one loses its comparison. */
  }
}

/** What one press of the fetch learned. `previous` is the check this device made before it. */
type FetchReceiptData = {
  readonly at: number
  readonly previous: LastCheck | null
  /** EVERY order the window held, filter or no filter — the preview's own `total`. It is the
   *  denominator the filtered figure is honest against: before D114 there was only one number
   *  here and it was drawn as "in the window", which a filtered press would have made a lie. */
  readonly windowTotal: number | null
  /** How many of those the statuses this press asked for matched — the wire's own `matched`. */
  readonly matched: number | null
  /** The statuses this press asked for, or null where it asked for everything the window held.
   *  Drawn, so a press that came back thin says whether that was the window or the filter. */
  readonly asked: readonly string[] | null
  /** Statuses this device remembers ticking that THIS window returned none of. Never dropped
   *  silently: the operator ticked them once, and a window holding none of one is a fact about
   *  the window worth seeing. */
  readonly absent: readonly string[]
  /** How many of those are new since this device's previous check. */
  readonly newSince: number | null
  /** How many this call detailed, how many it skipped as already known, what its cap left. */
  readonly detailed: number | null
  readonly skippedKnown: number | null
  readonly remaining: number | null
  /** How many orders came back on the wire, and what the ledger did with them. */
  readonly fetched: number
  readonly ingest: IngestResult | null
}

/** When something happened, in the words a person would use. */
function whenWord(at: number, now: number): string {
  const seconds = Math.max(0, Math.round((now - at) / 1000))
  if (seconds < 45) return 'just now'
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`
  const then = new Date(at)
  const time = then.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  if (then.toDateString() === new Date(now).toDateString()) return `today at ${time}`
  if (then.toDateString() === new Date(now - 86_400_000).toDateString()) return `yesterday at ${time}`
  return `${then.toLocaleDateString([], { month: 'short', day: 'numeric' })} at ${time}`
}

function plural(n: number, one: string, many: string): string {
  return n === 1 ? one : many
}

/** One figure in a receipt line: the number, then the words for it. */
function Fig({ n, of }: { readonly n: number; readonly of: string }) {
  return (
    <span className="orders-receipt-clause">
      <b className="orders-receipt-fig">{n.toLocaleString()}</b> {of}
    </span>
  )
}

/** The two-part receipt: what the window held, and what this press took out of it. */
function FetchReceipt({
  receipt,
  busy,
  onFetchMore,
}: {
  readonly receipt: FetchReceiptData
  readonly busy: boolean
  readonly onFetchMore: () => void
}) {
  const now = Date.now()

  /* PART ONE — what was checked. The window figure comes off the wire; the comparison comes off
     this device's own previous check, and says so plainly when there has not been one. */
  const checked: ReactNode[] = []
  if (receipt.windowTotal !== null) checked.push(<Fig key="window" n={receipt.windowTotal} of="in the window" />)
  /* THE FILTERED FIGURE IS A SECOND CLAUSE AND NEVER A REPLACEMENT. "40 in the window" alone,
     off a window of 370, is the number a filter makes wrong; the two side by side are what say
     the filter did something. Where nothing is filtered the second clause would restate the
     first, so it is not drawn. */
  if (receipt.asked !== null && receipt.matched !== null) {
    checked.push(<Fig key="matched" n={receipt.matched} of="matched your statuses" />)
  }
  if (receipt.newSince !== null && receipt.previous !== null) {
    checked.push(
      <span className="orders-receipt-clause" key="new">
        {receipt.newSince === 0 ? (
          'nothing new'
        ) : (
          <>
            <b className="orders-receipt-fig">{receipt.newSince.toLocaleString()}</b> new
          </>
        )}{' '}
        since {whenWord(receipt.previous.at, now)}
      </span>,
    )
  } else if (receipt.previous !== null) {
    checked.push(
      <span className="orders-receipt-clause" key="last">
        last checked {whenWord(receipt.previous.at, now)}
        {/* A comparison this press cannot honestly make says so, rather than going quiet. The
            two figures are counts of different questions and subtracting them is nonsense. */}
        {sameScope(receipt.previous.statuses, receipt.asked) ? null : ' · different statuses'}
      </span>,
    )
  } else {
    checked.push(
      <span className="orders-receipt-clause" key="first">
        the first check on this device
      </span>,
    )
  }

  /* PART TWO — what this press took, and what it left. */
  const took: ReactNode[] = []
  /* `detailed` is drawn only where it happened: "0 detailed" under "Nothing new to fetch" is
     the same sentence twice. */
  if (receipt.detailed !== null && receipt.detailed > 0) {
    took.push(<Fig key="detailed" n={receipt.detailed} of="detailed" />)
  }
  if (receipt.skippedKnown !== null && receipt.skippedKnown > 0) {
    took.push(<Fig key="known" n={receipt.skippedKnown} of="already in the ledger" />)
  }
  if (receipt.ingest !== null) {
    took.push(
      receipt.ingest.wrote_nothing ? (
        <span className="orders-receipt-clause" key="wrote">
          nothing new to write
        </span>
      ) : (
        <Fig key="wrote" n={receipt.ingest.added + receipt.ingest.changed} of="written to the ledger" />
      ),
    )
  }
  if (receipt.remaining !== null && receipt.remaining > 0) {
    took.push(<Fig key="remaining" n={receipt.remaining} of="remaining" />)
  }

  /* THE NEXT BATCH IS THE SAME ONE PRESS. The size named is what this call managed, capped by
     what is actually left; where the wire named no batch size the button says "the rest" rather
     than inventing one. */
  const next =
    receipt.remaining !== null && receipt.remaining > 0
      ? receipt.detailed !== null && receipt.detailed > 0
        ? Math.min(receipt.detailed, receipt.remaining)
        : null
      : null

  return (
    <section className="orders-receipt bn-anim-pop" aria-label="What the fetch checked and took" role="status">
      <div className="orders-receipt-part">
        <p className="orders-receipt-head">
          <Icon name="search" size={15} />
          Checked TCGplayer <span className="orders-receipt-when">· {whenWord(receipt.at, now)}</span>
        </p>
        <p className="orders-receipt-line">{checked}</p>
        {/* TICKED, AND THE WINDOW HELD NONE OF IT. The alternative was to drop these strings on
            the floor — the fetch cannot ask for a status the window does not contain, and the
            wire would answer nothing for it — which is the one thing this screen may not do
            with an operator's own tick. Named, in the wire's own spelling. */}
        {receipt.absent.length === 0 ? null : (
          <p className="orders-receipt-absent">
            <Icon name="info" size={14} />
            <span>
              This window held no <span className="bn-mono">{receipt.absent.join(', ')}</span> orders. Still
              ticked, for a window that does.
            </span>
          </p>
        )}
      </div>

      <div className="orders-receipt-part">
        <p className="orders-receipt-head">
          <Icon name="download" size={15} />
          {/* THE HEADING COUNTS THE CALL, NOT THE LEDGER. `fetched` is how many orders came
              back new; `detailed` is how many the call actually read. Heading them both
              "Fetched" put "Fetched 1 order" directly above "100 detailed", which reads as a
              contradiction. The call's own figure leads, and what reached the ledger is a
              clause below with the rest of the outcome. */}
          {receipt.fetched === 0 && (receipt.detailed ?? 0) === 0
            ? 'Nothing new to fetch'
            : `Fetched ${(receipt.detailed ?? receipt.fetched).toLocaleString()} ${plural(receipt.detailed ?? receipt.fetched, 'order', 'orders')}`}
        </p>
        {took.length === 0 ? null : <p className="orders-receipt-line">{took}</p>}
        {receipt.remaining !== null && receipt.remaining > 0 ? (
          <div className="orders-receipt-more">
            <Button icon="refresh" onClick={onFetchMore} busy={busy} disabled={busy}>
              {next === null ? 'Fetch the rest' : `Fetch the next ${next.toLocaleString()}`}
            </Button>
          </div>
        ) : null}
      </div>
    </section>
  )
}

/* ============================================================ which orders the press fetches */

/** Which statuses this window holds, and which of them the operator has ticked.
 *
 *  THE VOCABULARY IS READ, NEVER DECLARED. Every string on this panel came off
 *  `POST /orders/fetch {preview: true}` — a free call that walks the search pages, details
 *  nothing and writes nothing — and goes back to `fetchOrders` byte for byte.
 *  `server/order_transport.py` argues the ban on a coded vocabulary at length: TCGplayer never
 *  published these strings, the comparison there is `status.strip() in wanted`, and a status
 *  this file folded or renamed would be an order that never gets an envelope. So there is no
 *  list of statuses in this app, and this panel cannot be drawn until the preview has answered.
 *
 *  UNCHOSEN IS NOT "ALL TICKED". `filter.statuses === null` is the state of a device that has
 *  never opened this panel, and the press it makes is the press this screen has always made:
 *  every status the window returned. The rows are drawn ticked to say so, and the first
 *  untick materialises the list out of the window rather than out of anything remembered. */
function StatusPicker({
  preview,
  loading,
  failure,
  filter,
  busy,
  onChange,
  onConfirm,
  onRetry,
}: {
  readonly preview: OrdersPreview | null
  readonly loading: boolean
  readonly failure: Failure | null
  readonly filter: OrderFetchFilter
  readonly busy: boolean
  readonly onChange: (next: OrderFetchFilter) => void
  readonly onConfirm: () => void
  readonly onRetry: () => void
}) {
  const rows = preview?.by_status ?? []
  const inWindow = rows.map((row) => row.status)
  const ticked = (status: string) => filter.statuses === null || filter.statuses.includes(status)

  /* A remembered tick this window returned nothing for. It stays on the panel, and its row says
     the window held none — the operator ticked it, and taking it away silently is the defect
     this whole entry is about one register down. */
  const absent = (filter.statuses ?? []).filter((one) => !inWindow.includes(one))

  const toggle = (status: string) => {
    /* THE FIRST UNTICK MATERIALISES THE LIST OUT OF THIS WINDOW. There is nothing else it could
       come from: null carries no strings, and inventing a vocabulary here is the one thing this
       panel may not do. Any status this window does not hold is therefore not in the list a
       first untick writes, which is correct — it was not being asked for either. */
    const base = filter.statuses ?? inWindow
    const next = base.includes(status) ? base.filter((one) => one !== status) : [...base, status]
    /* Back to the unchosen state when every status in the window is ticked and nothing else is
       remembered, so a device that ticks its way back to everything stops carrying a list that
       the next window would narrow against. */
    const everything = next.length === inWindow.length && inWindow.every((one) => next.includes(one))
    onChange({ ...filter, statuses: everything ? null : next })
  }

  const total = rows.reduce((sum, row) => sum + row.count, 0)
  const picked = rows.filter((row) => ticked(row.status)).reduce((sum, row) => sum + row.count, 0)

  return (
    <div className="orders-statuses bn-well" role="group" aria-label="Which orders to fetch">
      {failure !== null ? (
        <div className="orders-statuses-state">
          <Notice tone="danger" title={failure.message} code={failure.code} />
          <Button size="sm" icon="refresh" onClick={onRetry}>
            Count them again
          </Button>
        </div>
      ) : loading ? (
        <div className="orders-statuses-state" aria-busy="true">
          <span className="bn-skeleton orders-statuses-skel" />
          <span className="bn-skeleton orders-statuses-skel" />
          <span className="bn-skeleton orders-statuses-skel" />
          <p className="orders-statuses-note">Counting this account&rsquo;s window. Nothing is being fetched.</p>
        </div>
      ) : rows.length === 0 && absent.length === 0 ? (
        <div className="orders-statuses-state">
          <p className="orders-statuses-note">TCGplayer returned no orders in this window, so there is nothing to
            narrow. The press will say the same.</p>
        </div>
      ) : (
        <>
          {/* THE ASK, AND IT HAPPENS ONCE ON THIS DEVICE. Measured on the owner's store the day
              this was written: 69 of 83 open orders were ones TCGplayer had already shipped, and
              because `resolve_all` serves oldest-first out of one pool they held 31 physical
              copies — three Ready-to-Ship lines read `short` while the cards sat in boxes. A
              default of "everything" reproduces that wherever nobody opens this panel, and a
              default of "everything except the shipped ones" would need a status vocabulary this
              product may not have. So a person is shown the real list, once. */}
          {filter.asked ? null : (
            <p className="orders-statuses-ask">
              <Icon name="info" size={15} />
              <span>
                <b>Which of these are worth fetching?</b> An order TCGplayer has already shipped still
                holds its copies here, so a live order can be told a card is short while it sits in a
                box. Nothing has been fetched yet, and this is remembered on this device.
              </span>
            </p>
          )}
          <div className="orders-statuses-head">
            <p className="orders-statuses-note">
              {/* The two figures are the whole point of the panel: what the press will take, out
                  of what is there. Drawn from the preview, which spent nothing to get them. */}
              Taking <b>{picked.toLocaleString()}</b> of <b>{total.toLocaleString()}</b>{' '}
              {plural(total, 'order', 'orders')} in this window.
            </p>
            <Button
              size="sm"
              icon="check"
              onClick={() => onChange({ ...filter, statuses: null })}
              disabled={filter.statuses === null}
            >
              Every status
            </Button>
          </div>

          <ul className="orders-statuses-list">
            {rows.map((row) => (
              <li key={row.status}>
                <label className="orders-status">
                  <input
                    type="checkbox"
                    className="orders-status-box"
                    checked={ticked(row.status)}
                    onChange={() => toggle(row.status)}
                  />
                  {/* The status STRING, in mono, because it is the wire's word and not this
                      product's. `orderReasonLabel` sentence-cases the reasons this repo owns;
                      there is deliberately no equivalent here. */}
                  <span className="orders-status-name bn-mono">{row.status}</span>
                  <span className="orders-status-count">{row.count.toLocaleString()}</span>
                  {row.known > 0 ? (
                    <span className="orders-status-known">{row.known.toLocaleString()} in the ledger</span>
                  ) : null}
                </label>
              </li>
            ))}
            {absent.map((status) => (
              <li key={status}>
                <label className="orders-status orders-status-absent">
                  <input type="checkbox" className="orders-status-box" checked onChange={() => toggle(status)} />
                  <span className="orders-status-name bn-mono">{status}</span>
                  <span className="orders-status-none">none in this window</span>
                </label>
              </li>
            ))}
          </ul>

          {/* THE SECOND TOGGLE, AND IT IS A ROUTE THAT NO SCREEN REACHED. `skip_known` has been
              on `POST /orders/fetch` since D91 and `fetchOrders` has always carried it; nothing
              ever sent it, which CLAUDE.md's "a route is not a feature" names as unfinished
              rather than as a follow-up. It is the same kind of narrowing as the statuses above
              — what is this press worth bothering with — so it is ticked in the same panel. */}
          <label className="orders-status orders-status-known-toggle">
            <input
              type="checkbox"
              className="orders-status-box"
              checked={filter.skipKnown}
              onChange={(event) => onChange({ ...filter, skipKnown: event.target.checked })}
            />
            <span className="orders-status-name">Skip orders the ledger already holds at that status</span>
          </label>
          {/* THE CONFIRM EXISTS ONLY WHILE THE DEVICE IS UNANSWERED. Afterwards the panel is a
              setting and the Fetch button beside it is the press; a second primary here would be
              two doors to one act. */}
          {filter.asked ? null : (
            <div className="orders-statuses-confirm">
              <Button variant="primary" icon="refresh" onClick={onConfirm} busy={busy} disabled={busy || picked === 0}>
                {picked === 0
                  ? 'Tick at least one'
                  : `Fetch these ${picked.toLocaleString()} ${plural(picked, 'order', 'orders')}`}
              </Button>
            </div>
          )}
          <p className="orders-statuses-note orders-statuses-foot">
            The strings are TCGplayer&rsquo;s own, counted by a free call that details nothing. This choice is
            remembered on this device.
          </p>
        </>
      )}
    </div>
  )
}

/** Everything a pick needs to be pulled. A pick with no `capture_id` cannot be aimed at and is
 *  offered as a location rather than as a button — the server would refuse it as
 *  `copy_not_identifiable`, and refusing it here says so before the press. */
function aimOf(line: ResolvedLine, pick: PickRow): PullTarget | null {
  if (pick.capture_id === null || pick.capture_id.trim() === '') return null
  if (line.reason !== 'resolved' && line.reason !== 'short') return null
  return { box: pick.box, index: pick.index, capture_id: pick.capture_id }
}

/* ---- every copy the store holds, not only the ones the resolver offered ------------------- */

/* THE RESOLVER OFFERS A LINE ONLY AS MANY COPIES AS IT WANTS, and that is not a bug to route
 * around — `pipeline/orders.py:LinePass.line` breaks out of its walk the moment
 * `len(picks) >= line.quantity`, because its job is to answer "can this envelope be filled".
 * The consequence is that its answer is not a map: on 42 of the owner's 59 real lines the picks
 * are FEWER than the copies the store holds, and one line wanting two copies of a card there are
 * fourteen of arrives here carrying two.
 *
 * The owner's requirement is the other way round — see where every copy lies, and choose which
 * one to reach for — so this screen reads the store itself and the map is the UNION of the two.
 * `GET /inventory` is the whole card map keyed `"<box>/<index>"`, every row carrying its sku,
 * its state, its capture id and its place. Deduped on box+index: a copy the resolver offered and
 * a copy found in the snapshot are the same copy.
 *
 * A COPY FOUND THIS WAY IS A LEGAL PULL TARGET AND IS AIMED IDENTICALLY. `do_order_pull`
 * validates that a card exists at the position and that its `capture_id` matches what was sent;
 * it never asks whether the resolver mentioned it. So the press carries the id the row was drawn
 * from, exactly as an offered copy's does.
 *
 * ON HAND IS THE SERVER'S OWN RULE RESTATED, NOT A NEW ONE INVENTED HERE.
 * `pipeline/orders.py:_Draw.available` keeps a copy whose state is none of
 * `master.TERMINAL_STATES` — sold, retired, moved — and which is at a place at all, a pooled
 * card being a count rather than a location (D24). `Fulfillment.tsx:forSale` and
 * `Inventory.tsx:wantedOf` are the same sentence in TypeScript. Held against the owner's real
 * store, this reproduces the server's own `on_hand` figure on all 59 lines, exactly. */
const GONE = new Set(['sold', 'retired', 'moved'])

/** The store's on-hand copies keyed by sku, each already shaped as the pick it would have been —
 *  so nothing downstream can tell a resolver's copy from the store's. */
type StoreCopies = ReadonlyMap<string, readonly PickRow[]>

function copyKeyOf(at: { readonly box: number; readonly index: number }): string {
  return `${at.box}/${at.index}`
}

/** One inventory row as a `PickRow`. `card_number` is the RAW number because that is what
 *  `server/capture_server.py:_pick_row` puts on a resolver pick, and the two must agree. */
function pickOfCard(card: InventoryCard, place: Place): PickRow {
  return {
    box: card.box,
    index: card.index,
    capture_id: card.capture_id,
    source: 'card',
    run: card.run,
    card_name: card.name,
    card_number: card.number,
    condition: card.condition,
    state: card.state,
    /* `held_by` is the SERVER's reverse index over the ledger and is not recomputable here. It
       costs nothing: a copy the ledger holds was sold by the pull that recorded it, so it is not
       on hand and never reaches this function. */
    held_by: null,
    place,
  }
}

function indexStore(inventory: Inventory): StoreCopies {
  const out = new Map<string, PickRow[]>()
  for (const card of Object.values(inventory.cards)) {
    const sku = card.sku
    if (!text(sku)) continue
    if (GONE.has(card.state)) continue
    const place = card.place
    /* No place block at all is a row whose box or index would not coerce — the server leaves it
       bare rather than naming a position that does not exist, and a location this screen cannot
       name is one it must not draw. `located: false` is D24's pooled card, which `available`
       excludes for the same reason the pull flow does. */
    if (place === undefined || place.located === false) continue
    const rows = out.get(sku)
    if (rows === undefined) out.set(sku, [pickOfCard(card, place)])
    else rows.push(pickOfCard(card, place))
  }
  return out
}

/** Which open order was offered which copy, across the WHOLE resolution — this client's read of
 *  the server's own `_taken` set, which is global to the pass and is why a second order wanting
 *  the same card comes back `short` while the copies are physically there.
 *
 *  IT IS A MARK AND NOT A LOCK. A copy another order was offered is drawn, said, and still
 *  pressable: taking it means that order re-resolves onto a different copy, or goes short, and
 *  that is the operator's call to make with the fact in front of him. The map ranks; it never
 *  picks. */
type Claims = ReadonlyMap<string, string>

function indexClaims(payload: OrdersPayload | null): Claims {
  const out = new Map<string, string>()
  for (const order of payload?.resolution.orders ?? []) {
    for (const line of order.lines) {
      for (const pick of line.picks) {
        const key = copyKeyOf(pick)
        if (!out.has(key)) out.set(key, line.order)
      }
    }
  }
  return out
}

/** The counts a line carries beside its reason, every part drawn including the zeros. */
function breakdownOf(line: ResolvedLine): string {
  return [`${line.on_hand} on hand`, `${line.sold} sold`, `${line.retired} retired`, `${line.pooled} pooled`].join(' · ')
}

/** Relative time in the product's one vocabulary — the strings `RunsStage.whenLabel` draws
 *  (`18h ago`, `yesterday`, `3 days ago`), kept local so this screen does not import a sibling
 *  another group is rebuilding at the same time. */
function whenLabel(iso: string | null): string | null {
  if (iso === null) return null
  const at = new Date(iso)
  const t = at.getTime()
  if (Number.isNaN(t)) return null
  const mins = Math.max(0, Math.floor((Date.now() - t) / 60000))
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'yesterday'
  if (days < 7) return `${days} days ago`
  return at.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function text(value: string | null | undefined): value is string {
  return typeof value === 'string' && value.trim() !== ''
}

function pctOf(order: OrderRow): number {
  return order.wanted > 0 ? Math.min(100, Math.round((order.recorded / order.wanted) * 100)) : 0
}

/* ---- the feed's product string, read into the parts a person reads ------------------------ */

type FeedName = {
  readonly game: string | null
  readonly set: string | null
  readonly name: string
  readonly number: string | null
  readonly condition: string | null
}

/** `Riftbound League of Legends Trading Card Game - Vendetta: Cataclysmic Duel - #090/166 - Near
 *  Mint Foil` → game, set, name, number, condition. Anything this cannot read comes back whole
 *  as the name; the raw string is kept beside it wherever it is drawn. */
function feedName(raw: string): FeedName {
  const parts = raw
    .split(' - ')
    .map((part) => part.trim())
    .filter((part) => part !== '')
  if (parts.length < 2) return { game: null, set: null, name: raw, number: null, condition: null }
  const game = parts[0] ?? null
  const numberAt = parts.findIndex((part, at) => at > 0 && part.startsWith('#'))
  const middle = numberAt === -1 ? parts.slice(1) : parts.slice(1, numberAt)
  const number = numberAt === -1 ? null : (parts[numberAt] ?? null)
  const tail = numberAt === -1 ? [] : parts.slice(numberAt + 1)
  let set: string | null = null
  let name: string
  if (middle.length >= 2) {
    set = middle.slice(0, -1).join(' - ')
    name = middle[middle.length - 1] as string
  } else {
    const one = middle[0] ?? raw
    const colon = one.indexOf(': ')
    if (colon > 0) {
      set = one.slice(0, colon)
      name = one.slice(colon + 2)
    } else name = one
  }
  return { game, set, name, number, condition: tail.length === 0 ? null : tail.join(' · ') }
}

type Headline = { readonly name: string; readonly detail: string[]; readonly raw: string | null; readonly condition: string | null }

/** The line's heading is the STORE'S name for the card where a pick carries one, and the feed's
 *  string only where nothing resolved — and then split, never drawn whole as a title. The raw
 *  string stays greppable in the `title` and the SKU tag. */
function headlineOf(line: ResolvedLine): Headline {
  const raw = line.line.name
  const parsed = raw === null ? null : feedName(raw)
  const fromPick = line.picks.find((pick) => text(pick.card_name))?.card_name ?? null
  const name = fromPick ?? parsed?.name ?? line.sku
  const number = [line.line.number, line.picks.find((pick) => text(pick.card_number))?.card_number, parsed?.number].find(text) ?? null
  const condition = [line.line.condition, parsed?.condition].find(text) ?? null
  const detail = [parsed?.set, number, line.line.printing, condition].filter(text)
  return { name, detail, raw, condition: text(condition) ? condition : null }
}

/* ---- status ---------------------------------------------------------------------------------- */

type Status = 'ready' | 'short' | 'look' | 'unresolved' | 'done'

function statusOf(order: OrderRow, answer: ResolvedOrder | null): Status {
  if (!order.open) return 'done'
  if (answer === null) return 'unresolved'
  const reasons = answer.lines.map((line) => line.reason)
  if (reasons.some((reason) => reason !== 'resolved' && reason !== 'short')) return 'look'
  if (reasons.some((reason) => reason === 'short')) return 'short'
  return 'ready'
}

const STATUS_PILL: Record<Status, { label: string; tone: PillTone; icon: IconName }> = {
  ready: { label: 'Ready to pull', tone: 'ok', icon: 'check' },
  short: { label: 'Short', tone: 'warn', icon: 'alert' },
  look: { label: 'Needs a look', tone: 'warn', icon: 'eye' },
  unresolved: { label: 'Not resolved', tone: 'default', icon: 'clock' },
  done: { label: 'Done', tone: 'default', icon: 'check' },
}

const STATUS_DOT: Record<Status, 'ok' | 'warn' | 'default'> = {
  ready: 'ok',
  short: 'warn',
  look: 'warn',
  unresolved: 'default',
  done: 'default',
}

const LANE_TONE: Record<ShippingLane, PillTone> = { envelope: 'ok', parcel: 'default', unjudged: 'warn' }
const LANE_ICON: Record<ShippingLane, IconName> = { envelope: 'mail', parcel: 'package', unjudged: 'alert' }
/* On an order the lane sits beside the pull STATUS, so the unjudged lane is named for what it is
   here — a lane not yet decided — rather than with the Ship stage's "Needs a look", which would
   draw two identical pills meaning two different things. */
const ORDER_LANE_LABEL: Record<ShippingLane, string> = { envelope: 'Envelope', parcel: 'Parcel', unjudged: 'Lane undecided' }

/* The six reasons: a short chip label, a tone, an icon, and a phrase for the summary sentence.
   The long human label (`orderReasonLabel`) and the remedy stay on the line that has the
   problem, and the machine string rides THERE as a tag — never on the chips. */
const REASON_SHORT: Record<OrderLineReason, string> = {
  resolved: 'Every copy found',
  short: 'Short',
  no_copies_on_hand: 'None left',
  sku_unknown: 'No record',
  sku_unseen: 'Never seen',
  not_a_single: 'Sealed, not a single',
}

const REASON_TONE: Record<OrderLineReason, 'ok' | 'warn' | 'danger' | 'info'> = {
  resolved: 'ok',
  short: 'warn',
  no_copies_on_hand: 'danger',
  sku_unknown: 'info',
  sku_unseen: 'info',
  not_a_single: 'info',
}

const REASON_ICON: Record<OrderLineReason, IconName> = {
  resolved: 'check',
  short: 'alert',
  no_copies_on_hand: 'box',
  sku_unknown: 'info',
  sku_unseen: 'search',
  not_a_single: 'package',
}

function phraseOf(reason: OrderLineReason, n: number): string {
  const one = n === 1
  switch (reason) {
    case 'resolved':
      return `${n} found every copy`
    case 'short':
      return `${n} ${one ? 'is' : 'are'} short`
    case 'no_copies_on_hand':
      return `${n} ${one ? 'has' : 'have'} no copies left in the boxes`
    case 'sku_unknown':
      return `${n} name${one ? 's' : ''} a SKU no record carries`
    case 'sku_unseen':
      return `${n} name${one ? 's' : ''} a SKU the store has never seen`
    case 'not_a_single':
      return `${n} ${one ? 'is' : 'are'} not a single`
  }
}

function joinPhrases(parts: string[]): string {
  if (parts.length <= 1) return parts.join('')
  return `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}`
}

/** The summary, drawn as the page's lede once the ledger has answered. */
function summaryOf(open: OrderRow[], done: OrderRow[], counts: Record<OrderLineReason, number>): ReactNode {
  const lineTotal = ORDER_REASONS.reduce((sum, reason) => sum + counts[reason], 0)
  const phrases = ORDER_REASONS.filter((reason) => counts[reason] > 0).map((reason) => phraseOf(reason, counts[reason]))
  if (open.length === 0) {
    return (
      <>
        Nothing outstanding — every one of the <strong>{done.length}</strong> order{done.length === 1 ? '' : 's'} has its copies.
      </>
    )
  }
  return (
    <>
      <strong>{open.length}</strong> open order{open.length === 1 ? '' : 's'}
      {done.length > 0 ? ` and ${done.length} done` : ''}. Of <strong>{lineTotal}</strong> line{lineTotal === 1 ? '' : 's'},{' '}
      {joinPhrases(phrases)}.
    </>
  )
}

/** The undo, pressed on a toast after the hub may have unmounted. It sends the target and
 *  nothing else — the server finds whoever holds the `capture_id` — and bumps the hub so any
 *  mounted screen re-reads. */
async function undoFromToast(target: PullTarget, place: string, name: string): Promise<void> {
  /* The lock lives on the HUB, not in a component: the toast outlives the list, and whichever hub
     is mounted by the time the undo answers must see every Pull disabled until it does. */
  setHub({ busy: `undo/${target.capture_id}` })
  try {
    await undoPull([target])
    toast({ kind: 'ok', icon: 'undo', title: `Put ${name} back`, body: `${place} holds it again.` })
  } catch (err) {
    const trouble = describeFailure(err)
    toast({ kind: 'refusal', title: 'The card was not put back', body: `${trouble.message} · ${trouble.code}` })
  } finally {
    setHub({ busy: null })
    touchHub()
  }
}

type PullHandler = (order: OrderRow, line: ResolvedLine, pick: PickRow, target: PullTarget) => void

/* D113's three. They travel the same prop chain as `onPull` and for the same reason: the hub owns
   every write on this screen, so the busy lock, the toast and the re-read are in one place and a
   row cannot half-refresh the list it is drawn from. */
type FillHandler = (order: OrderRow, line: ResolvedLine, count: number, reason: OrderFillReason) => void
type KindHandler = (order: OrderRow, line: ResolvedLine, kind: 'sealed' | 'accessory' | null) => void
type StandDownHandler = (rows: readonly OrderRow[], reason: OrderCloseReason) => void
type CloseLineHandler = (order: OrderRow, line: ResolvedLine, reason: OrderCloseReason) => void

/* ---- the selection, mirrored in the hash ----------------------------------------------------- */

const ORDER_PARAM = 'order'

function orderParam(): string | null {
  const hash = window.location.hash
  const at = hash.indexOf('?')
  if (at === -1) return null
  return new URLSearchParams(hash.slice(at + 1)).get(ORDER_PARAM)
}

/** `#/orders?order=<key>`, written with `replaceState` so stepping through twenty orders leaves
 *  one history entry and fires no `hashchange` — the shell's router keys on the path alone. */
function mirrorOrderParam(key: string): void {
  const hash = window.location.hash
  const path = hash.replace(/^#/, '').split('?')[0] ?? ''
  if (path !== '/orders') return
  const next = `#/orders?${ORDER_PARAM}=${encodeURIComponent(key)}`
  if (hash === next) return
  window.history.replaceState(window.history.state, '', next)
}

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => (typeof window === 'undefined' ? false : window.matchMedia(query).matches))
  useEffect(() => {
    const media = window.matchMedia(query)
    const onChange = () => setMatches(media.matches)
    media.addEventListener('change', onChange)
    setMatches(media.matches)
    return () => media.removeEventListener('change', onChange)
  }, [query])
  return matches
}

/* ---- the walk: every open order's copies, in the order the boxes hold them ------------------ */

type WalkRow = {
  readonly key: string
  readonly order: OrderRow
  readonly line: ResolvedLine
  readonly pick: PickRow
  readonly target: PullTarget
}

type WalkGroup = { readonly key: string; readonly title: string; readonly note: string | null; readonly rows: WalkRow[] }

type Walk = { readonly groups: WalkGroup[]; readonly rows: WalkRow[] }

/** Pure UI over the resolution already on the client: the picks that can be pulled, deduped on
 *  the copy (two orders offered one card keep the first), sorted box → index, pooled copies last,
 *  and grouped under the box and section a person walks to. */
function buildWalk(open: OrderRow[], answers: Map<string, ResolvedOrder>): Walk {
  const rows: WalkRow[] = []
  const seen = new Set<string>()
  for (const order of open) {
    const answer = answers.get(order.key)
    if (answer === undefined) continue
    for (const line of answer.lines) {
      for (const pick of line.picks) {
        if (pick.held_by !== null) continue
        const target = aimOf(line, pick)
        if (target === null) continue
        const key = pick.capture_id ?? `${pick.box}/${pick.index}`
        if (seen.has(key)) continue
        seen.add(key)
        rows.push({ key, order, line, pick, target })
      }
    }
  }
  rows.sort((a, b) => {
    const pooledA = a.pick.place.label === null
    const pooledB = b.pick.place.label === null
    if (pooledA !== pooledB) return pooledA ? 1 : -1
    return a.pick.box - b.pick.box || a.pick.index - b.pick.index
  })
  const groups: WalkGroup[] = []
  for (const row of rows) {
    const place = row.pick.place
    const pooled = place.label === null
    const key = pooled ? `pooled/${place.game ?? ''}` : `${place.box}/${place.section ?? 0}`
    let group = groups[groups.length - 1]
    if (group === undefined || group.key !== key) {
      group = {
        key,
        title: pooled ? (text(place.game_display) ? place.game_display : 'Pooled') : `Box ${place.box}`,
        note: pooled
          ? 'Pooled · no position'
          : [place.box_name, place.section === null ? null : `Section ${place.section}`].filter(text).join(' · ') || null,
        rows: [],
      }
      groups.push(group)
    }
    group.rows.push(row)
  }
  return { groups, rows }
}

/* ---- the copy map: where a card's copies are, ranked by density ---------------------------- */

/* THE MAP RANKS, IT NEVER PICKS (the owner's ruling, 2026-09-03).
 *
 * A line's copies — EVERY copy the store holds of that card, not only the ones the resolver
 * offered — are grouped into the boxes that hold them and, inside a box, into the sections they
 * sit in. The box holding the most copies OF THIS CARD leads and is marked as the stop worth
 * walking to; ties break to the lower box number, and sections rank the same way one register
 * down. NOTHING IS PRESELECTED and nothing is hidden: every copy is drawn beneath the map, in the
 * map's own order, with its own Pull — including the ones in far boxes, including a copy another
 * open order was offered, and including a copy the ledger has already recorded, which is drawn,
 * marked and left untakeable.
 *
 * THE RANK IS OVER FREE COPIES, not over copies held. A box holding three copies of which two are
 * already recorded against somebody is a worse stop than a box holding two nobody is counting on,
 * and a recommendation that walked you to the first would be recommending a wasted trip. The held
 * count is still drawn on the block — it is a true thing about that drawer — it just does not get
 * a vote. */

/** One copy on a line's map. A resolver pick and a card found in the store snapshot are the same
 *  shape here, because they are the same object: a card, in a drawer, that can be taken. */
type LineCopy = {
  readonly key: string
  readonly pick: PickRow
  /** This line's own resolver pick — the copy the machine would have reached for. */
  readonly offered: boolean
  /** Another open order was offered this one. A mark, not a lock (see `Claims`). */
  readonly claimedBy: string | null
  /** Already recorded against a line in the ledger. Drawn, marked, and NOT pressable. */
  readonly spokenFor: string | null
  /** Pressable: aimable from this line, and not already recorded against somebody. */
  readonly takeable: boolean
  /** Takeable AND nobody else is counting on it — what the density rank is over. */
  readonly free: boolean
}

/** A copy is takeable when this line can be aimed at it and nothing has spoken for it. */
function takeableOf(line: ResolvedLine, pick: PickRow): boolean {
  return pick.held_by === null && aimOf(line, pick) !== null
}

/** The union: this line's picks, then every on-hand copy of the same sku the store holds. Deduped
 *  on box+index, the resolver's own row winning — it is the one carrying `held_by`. */
function copiesOf(line: ResolvedLine, store: StoreCopies | null, claims: Claims): LineCopy[] {
  const byKey = new Map<string, LineCopy>()
  const add = (pick: PickRow, offered: boolean) => {
    const key = copyKeyOf(pick)
    if (byKey.has(key)) return
    const spokenFor = pick.held_by?.order ?? null
    const claimedBy = offered ? null : (claims.get(key) ?? null)
    const takeable = takeableOf(line, pick)
    byKey.set(key, { key, pick, offered, claimedBy, spokenFor, takeable, free: takeable && claimedBy === null })
  }
  for (const pick of line.picks) add(pick, true)
  for (const pick of store?.get(line.sku) ?? []) add(pick, false)
  return [...byKey.values()]
}

type MapSection = {
  readonly key: string
  readonly label: string
  readonly total: number
  readonly free: number
}

/** One box on a line's map: what it holds of THIS card, and where inside it. */
type MapStop = {
  readonly key: string
  readonly title: string
  readonly name: string | null
  readonly box: number | null
  readonly pooled: boolean
  readonly total: number
  readonly free: number
  readonly spoken: number
  readonly claimed: number
  readonly sections: MapSection[]
  readonly copies: LineCopy[]
}

type CopyMap = {
  readonly stops: MapStop[]
  /** Every copy, in the map's order — the order the rows beneath the map are drawn in. */
  readonly copies: LineCopy[]
  readonly total: number
  readonly free: number
}

/** Densest first, ties to the lower box number, a pooled bucket always last — it is a count
 *  rather than a place (D24), so it can never be a stop on a walk. */
function byDensity(a: { pooled: boolean; free: number; total: number; box: number | null }, b: typeof a): number {
  if (a.pooled !== b.pooled) return a.pooled ? 1 : -1
  if (a.free !== b.free) return b.free - a.free
  if (a.total !== b.total) return b.total - a.total
  return (a.box ?? Number.MAX_SAFE_INTEGER) - (b.box ?? Number.MAX_SAFE_INTEGER)
}

/** The slot a hand counts to (D58), falling back to the store key where the card has left the
 *  box and has no slot. Only ever an ORDER, never drawn. */
function walkOrderOf(pick: PickRow): number {
  return pick.place.slot ?? pick.index
}

function buildCopyMap(line: ResolvedLine, store: StoreCopies | null, claims: Claims): CopyMap {
  type SectionDraft = { key: string; label: string; section: number | null; total: number; free: number; copies: LineCopy[] }
  type StopDraft = {
    key: string
    title: string
    name: string | null
    box: number | null
    pooled: boolean
    total: number
    free: number
    spoken: number
    claimed: number
    sections: Map<string, SectionDraft>
  }

  const drafts = new Map<string, StopDraft>()
  for (const copy of copiesOf(line, store, claims)) {
    const pick = copy.pick
    const place = pick.place
    /* A POOLED COPY HAS NO POSITION (D24): its `box`/`index` are the store key, so it is bucketed
       by game and never drawn as a drawer to walk to. */
    const pooled = place.label === null
    const key = pooled ? `pooled/${place.game ?? ''}` : `box/${pick.box}`
    let stop = drafts.get(key)
    if (stop === undefined) {
      stop = {
        key,
        title: pooled ? (text(place.game_display) ? place.game_display : 'Pooled') : `Box ${pick.box}`,
        name: pooled ? 'no position' : (text(place.box_name) ? place.box_name : null),
        box: pooled ? null : pick.box,
        pooled,
        total: 0,
        free: 0,
        spoken: 0,
        claimed: 0,
        sections: new Map(),
      }
      drafts.set(key, stop)
    }
    stop.total += 1
    if (copy.free) stop.free += 1
    if (copy.spokenFor !== null) stop.spoken += 1
    if (copy.claimedBy !== null) stop.claimed += 1

    const section = pooled ? null : place.section
    const sectionKey = section === null ? 'none' : `s${section}`
    let bucket = stop.sections.get(sectionKey)
    if (bucket === undefined) {
      bucket = {
        key: sectionKey,
        label: section === null ? (pooled ? 'Pooled' : 'No section') : `Section ${section}`,
        section,
        total: 0,
        free: 0,
        copies: [],
      }
      stop.sections.set(sectionKey, bucket)
    }
    bucket.total += 1
    if (copy.free) bucket.free += 1
    bucket.copies.push(copy)
  }

  const stops: MapStop[] = [...drafts.values()]
    .sort(byDensity)
    .map((draft) => {
      const sections = [...draft.sections.values()].sort((a, b) =>
        byDensity(
          { pooled: false, free: a.free, total: a.total, box: a.section },
          { pooled: false, free: b.free, total: b.total, box: b.section },
        ),
      )
      for (const bucket of sections) bucket.copies.sort((a, b) => walkOrderOf(a.pick) - walkOrderOf(b.pick))
      return {
        key: draft.key,
        title: draft.title,
        name: draft.name,
        box: draft.box,
        pooled: draft.pooled,
        total: draft.total,
        free: draft.free,
        spoken: draft.spoken,
        claimed: draft.claimed,
        sections: sections.map(({ key, label, total, free }) => ({ key, label, total, free })),
        copies: sections.flatMap((bucket) => bucket.copies),
      }
    })

  const copies = stops.flatMap((stop) => stop.copies)
  return {
    stops,
    copies,
    total: copies.length,
    free: copies.filter((copy) => copy.free).length,
  }
}

/* ---- the walk plan: the same rule one register up, over a whole order ----------------------- */

/** One stop on an order's walk: what this box satisfies of the WHOLE order, so a buyer wanting
 *  four different singles is walked in one pass rather than four. */
type PlanStop = {
  readonly key: string
  readonly title: string
  readonly name: string | null
  readonly box: number | null
  readonly pooled: boolean
  readonly copies: number
  readonly free: number
  readonly cards: number
  readonly sections: string[]
}

function buildWalkPlan(answer: ResolvedOrder): { readonly stops: PlanStop[]; readonly copies: number } {
  type Draft = {
    key: string
    title: string
    name: string | null
    box: number | null
    pooled: boolean
    copies: number
    free: number
    skus: Set<string>
    sections: Map<number | null, number>
  }
  const drafts = new Map<string, Draft>()
  let copies = 0
  for (const line of answer.lines) {
    for (const pick of line.picks) {
      const place = pick.place
      const pooled = place.label === null
      const key = pooled ? `pooled/${place.game ?? ''}` : `box/${pick.box}`
      let stop = drafts.get(key)
      if (stop === undefined) {
        stop = {
          key,
          title: pooled ? (text(place.game_display) ? place.game_display : 'Pooled') : `Box ${pick.box}`,
          name: pooled ? 'no position' : (text(place.box_name) ? place.box_name : null),
          box: pooled ? null : pick.box,
          pooled,
          copies: 0,
          free: 0,
          skus: new Set(),
          sections: new Map(),
        }
        drafts.set(key, stop)
      }
      stop.copies += 1
      copies += 1
      if (takeableOf(line, pick)) stop.free += 1
      stop.skus.add(line.sku)
      const section = pooled ? null : place.section
      stop.sections.set(section, (stop.sections.get(section) ?? 0) + 1)
    }
  }
  const stops = [...drafts.values()]
    .sort((a, b) => byDensity({ ...a, total: a.copies }, { ...b, total: b.copies }))
    .map((draft) => ({
      key: draft.key,
      title: draft.title,
      name: draft.name,
      box: draft.box,
      pooled: draft.pooled,
      copies: draft.copies,
      free: draft.free,
      cards: draft.skus.size,
      /* Ascending, and deliberately NOT by density: at the plan's register this is which parts of
         the drawer the walk passes through, and a hand goes front to back. The density ranking
         that decides what to reach for first is the per-line map's, one register down. */
      sections: [...draft.sections.keys()]
        .sort((a, b) => (a ?? Number.MAX_SAFE_INTEGER) - (b ?? Number.MAX_SAFE_INTEGER))
        .map((section) => (section === null ? '—' : String(section))),
    }))
  return { stops, copies }
}

/* ---- the figure on a line ------------------------------------------------------------------- */

type LineFigure = { readonly wanted: number; readonly pulled: number; readonly remaining: number }

/** WHAT IS LEFT TO PULL, and never `1 of 3 found` (the owner's ruling, 2026-09-03). The buyer's
 *  original quantity is not a progress denominator on this screen.
 *
 *  THE PULLED COUNT IS THE LEDGER'S, NOT THE RESOLVER'S. `ResolvedLine.fulfilled` is `len(picks)`
 *  — the copies the resolver could OFFER right now — and `outstanding` beside it is the same
 *  arithmetic over that same quantity, so neither can answer "how many have I already taken".
 *  `OrderRow.progress` carries the ledger's own `recorded` per SKU, which is that answer.
 *  (The merge brings `ResolvedLine.recorded`; read it here the moment it lands, and this lookup
 *  goes.) */
function figureOf(order: OrderRow, line: ResolvedLine): LineFigure {
  const progress = order.progress.find((row) => row.sku === line.sku) ?? null
  const wanted = progress?.wanted ?? line.wanted
  const pulled = Math.min(wanted, Math.max(0, progress?.recorded ?? 0))
  return { wanted, pulled, remaining: Math.max(0, wanted - pulled) }
}

/* ======================================================================================= hub */

export function OrdersHub({ stage }: { readonly stage: Stage }) {
  const hub = useHub()
  const payload = hub.payload
  const [failure, setFailure] = useState<Failure | null>(null)
  /* THE STORE'S OWN COPIES, read beside the ledger rather than through it. Null until the first
     read lands and null again if one fails: the map then draws the resolver's picks alone, which
     is what this screen did before the store was read at all. A second read is issued after every
     write for the same reason the ledger is — a pull sells the card, and a sold card must leave
     every other line's map on the same frame it leaves its own. */
  const [store, setStore] = useState<StoreCopies | null>(null)
  const [storeFailed, setStoreFailed] = useState(false)
  const [localBusy, setBusy] = useState<string | null>(null)
  /* A write pressed here locks from inside; an undo pressed on a toast locks from outside, through
     the hub (`hub.busy`). Either one disables every Pull and both wells. */
  const busy = hub.busy ?? localBusy
  const [pasteNote, setPasteNote] = useState<string | null>(null)
  const [dropped, setDropped] = useState<string[]>([])
  /** The last fetch's receipt. It outlives the well it was pressed from, because the remainder
   *  it names is the reason to press again. */
  const [receipt, setReceipt] = useState<FetchReceiptData | null>(null)

  /* ---------------------------------------------------------- the fetch filter (D114) ---- */

  /** What this device narrows the fetch to. Read from `localStorage` ONCE, on mount: it is a
   *  habit and not a subscription, and re-reading it per render would fight the panel. */
  const [filter, setFilter] = useState<OrderFetchFilter>(() => storedOrderFilter())
  const [pickerOpen, setPickerOpen] = useState(false)
  /** The last window the free preview counted, held so the panel can be drawn without asking
   *  again — and so a press can reuse it if it is fresh enough to be the same window. It is
   *  never a substitute for the preview a press makes: that one is what the fetch is built on. */
  const [vocab, setVocab] = useState<OrdersPreview | null>(null)
  const [vocabBusy, setVocabBusy] = useState(false)
  const [vocabFailure, setVocabFailure] = useState<Failure | null>(null)
  /** The panel, so a press that OPENS it can bring it into view. On a phone the well is taller
   *  than the viewport and the picker lands below the fold, so the ask — which the operator did
   *  not go looking for — would be an answered press that appears to have done nothing. */
  const pickerBox = useRef<HTMLDivElement>(null)

  const live = useRef(true)
  const pasteBox = useRef<HTMLTextAreaElement>(null)
  const phone = useMediaQuery('(max-width: 767px)')
  const wide = useMediaQuery('(min-width: 1024px)')

  useEffect(() => {
    live.current = true
    return () => {
      live.current = false
    }
  }, [])

  /* ONE CALL FOR BOTH HALVES. Every write ends by calling this again, because a pull changes the
     resolution of every OTHER line that wanted the same SKU. */
  const reread = useCallback(async () => {
    try {
      const answer = await getOrders()
      setHub((was) => ({
        payload: answer,
        arriving: was.arriving === null ? answer.orders.length === 0 : was.arriving,
      }))
      if (live.current) setFailure(null)
    } catch (err) {
      if (!live.current) return
      setFailure(describeFailure(err))
    }
  }, [])

  /* A SEPARATE READ, AND DELIBERATELY NOT FOLDED INTO `reread`. The ledger's answer is what the
     screen is FOR; the store index only widens each line's map. Awaiting them together would let
     a slow or broken `/inventory` hold the orders off the screen, so they race and the map fills
     in when its half lands.

     STILL ON THE FULL WALK, ON PURPOSE (D192/item 2 — verified against the tree, correcting the
     playbook this item was written from). `copiesOf`'s own comment above says the whole of what
     `indexStore` is for: "EVERY copy the store holds of that card, not only the ones the resolver
     offered... including the ones in FAR BOXES" — copies sitting in boxes no resolver pick names
     at all. There is no separate "Walk the boxes" call site to leave behind either: `buildWalk`
     (below) is built entirely from `answer.lines[].picks`, the resolver's own already-resolved
     rows off `GET /orders`, and never touches `store`. So the one real question is whether THIS
     call can be scoped to "the boxes an order's resolver picks name" (Fulfillment's order-
     resolution case, and this item's own playbook's stated aim for this file) — and it cannot,
     safely: a SKU's other copies are, by the feature's own design, expected to live in boxes no
     pick names, and narrowing the fetch to only named boxes would silently hide them from the
     density map and from Pull, which is a correctness regression and not merely a slower screen.
     Building a lean "on-hand copies by SKU, store-wide" route is real work `#/pricing`'s D159
     `?band=` lens and item 6's own `do_orders` rebuild are the closer candidates for, named here
     as the debt CLAUDE.md's "fix the cause… first ask whether the primitive already exists" rule
     asks to be named rather than patched around under this item's own budget.
     `docs/DEBTS.md` §27 is the named debt: the measured cost, why this cannot be box-scoped,
     and the candidate primitive. */
  const rereadStore = useCallback(async () => {
    try {
      const inventory = await getInventory()
      if (!live.current) return
      setStore(indexStore(inventory))
      setStoreFailed(false)
    } catch {
      if (!live.current) return
      /* DROPPED RATHER THAN KEPT. A stale card map after a pull would draw a copy that has left
         the box as one you can still reach for, and a map that is quietly wrong is worse than a
         map that is quietly narrow. */
      setStore(null)
      setStoreFailed(true)
    }
  }, [])

  useEffect(() => {
    void reread()
    void rereadStore()
  }, [reread, rereadStore, hub.version])

  /* ---------------------------------------------------------------------- orders arrive */

  /* THE PASTE IS PROJECTED BEFORE IT IS SENT, and the projection is `orderPaste.ts`'s alone. What
     was DROPPED is drawn beside the press, because a silent strip is indistinguishable on screen
     from a feed that never carried the field. */
  const onRead = () => {
    const reading = readPaste(hub.paste)
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
        setHub({ paste: '' })
        /* `wrote_nothing` is the honest answer to "did that work" for a second identical paste. */
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

  /* THE FETCH ENTERS THROUGH THE SAME ONE DOOR THE PASTE DOES: `POST /orders/fetch` answers
     exactly the body the ingest accepts. Free, and it writes nothing by itself.

     ONE PRESS, AND THE RECEIPT SAYS WHAT IT LEFT. The button asks and takes in the same press —
     there is no status step in front of it — and what the call could not carry is reported
     afterwards, with the control to take the next batch. */
  const onFetch = (using: OrderFetchFilter = filter) => {
    void (async () => {
      setBusy('fetch')
      setFailure(null)
      setPasteNote(null)
      setDropped([])
      setReceipt(null)
      /* AND THE WALK'S PASS ENDS HERE. Orders arriving off TCGplayer are a new sitting, and it is
         the only boundary the operator actually draws — a stage switch is not one, and neither is
         a toggle (see the mode control). Without this the frozen set would outlive the work it
         describes for as long as the tab is open. */
      setHub({ walkKeys: null })
      /* Read the previous check BEFORE this one is written, and hold it: it is what "new since"
         is measured against. */
      const previous = readLastCheck()
      try {
        /* ONE PRESS, TWO CALLS, AND THE SECOND ONE IS NOT A QUESTION. D91 made the wire refuse
           a fetch that names no statuses — `statuses_required` — on the argument that this
           account's window holds hundreds of orders and one press taking all of them is what
           never worked. The owner ruled the two-press flow out: *"why would it ever say 1 of 3
           found"*, and the press asks and takes in the same gesture.

           BOTH SURVIVE, because the thing D91 actually needed was for somebody to NAME the
           statuses rather than for a human to tick them. The vocabulary is not enumerable on
           this side — `order_transport.py` says so at length: it was never published, and a
           guess that drops an order is an envelope that never ships — so the press reads it off
           the preview, which writes nothing, and sends back exactly what came out. Nothing is
           guessed and nothing is asked.

           The detail cap is unchanged and is not what this works around: a press still details
           at most its limit and reports `remaining`, which the receipt below already draws with
           the control to take the next batch. */
        const seen = await previewOrders()
        if (live.current) setVocab(seen)
        const inWindow = seen.by_status.map((row) => row.status)
        if (inWindow.length === 0) {
          if (!live.current) return
          setPasteNote('TCGplayer returned no orders in this window.')
          setBusy(null)
          return
        }
        /* THE FIRST PRESS ON THIS DEVICE STOPS HERE AND SHOWS THE LIST. It has cost one free
           call — the preview details nothing and writes nothing — and it details nothing now
           either: the panel opens with every status ticked and its own press finishes the
           errand. Once. `asked` is what makes it once, and it is set by answering rather than
           by arriving, so a press interrupted here asks again rather than silently defaulting.

           THIS IS NOT D91's TWO-PRESS FLOW. That asked on every press, which is what the owner
           ruled out. What is being bought is the one thing a default cannot buy: somebody has
           looked at the actual strings, which is the only place in this product where a status
           may be judged (D114). */
        if (!using.asked) {
          if (!live.current) return
          setPickerOpen(true)
          setBusy(null)
          /* After the paint that opens it. `block: 'nearest'` and no smooth behaviour: this is a
             correction to where the press left the page, not motion carrying meaning, and the
             reduced-motion floor should not have to have an opinion about it. */
          window.requestAnimationFrame(() => pickerBox.current?.scrollIntoView({ block: 'nearest' }))
          return
        }
        /* THE OPERATOR'S TICK LIST, INTERSECTED WITH WHAT THIS WINDOW ACTUALLY HOLDS. Asking
           for a status no order carries is not an error on the wire — it matches nothing and
           costs a walk — but it is a fact worth reporting, so what falls out is kept and drawn
           rather than dropped. `filter.statuses === null` is a device that has never opened the
           picker, and it takes the whole vocabulary: today's press, unchanged. */
        const wanted = using.statuses
        const statuses = (wanted === null ? inWindow : inWindow.filter((one) => wanted.includes(one))).slice(0, 50)
        const absent = wanted === null ? [] : wanted.filter((one) => !inWindow.includes(one))
        if (statuses.length === 0) {
          if (!live.current) return
          /* NOTHING IS FETCHED AND THE REASON IS THE FILTER, said in those words. The wire would
             refuse an empty `statuses` with `statuses_required`, which is a true sentence about
             a body and a useless one about a choice the operator made on this screen. */
          setPasteNote(
            absent.length === 0
              ? 'Every status is ticked off, so this press would fetch nothing. Open Statuses and tick at least one.'
              : `This window holds no ${absent.join(', ')} orders — the only statuses ticked here. Nothing was fetched.`,
          )
          setBusy(null)
          return
        }
        const found = await fetchOrders({
          statuses,
          ...(using.skipKnown ? { skip_known: true } : {}),
        })
        if (!live.current) return
        /* The four counts the merge brings on `OrdersFetched` — see `FetchCounts` above. Absent
           on this branch's wire, and each absence omits its clause rather than drawing a zero. */
        const counted = found as OrdersFetched & FetchCounts
        const matched = wireCount(counted.matched)
        const at = Date.now()
        const written = found.orders.length === 0 ? null : await ingestOrders(found.orders)
        if (!live.current) return
        /* THE COMPARISON IS ONLY DRAWN WHERE THE QUESTION DID NOT CHANGE. Two `matched` figures
           taken under different status filters are counts of different things, and subtracting
           them would put a confident "12 new" under a press that merely narrowed. */
        const comparable = sameScope(previous?.statuses ?? null, wanted)
        setReceipt({
          at,
          previous,
          windowTotal: wireCount(seen.total),
          matched,
          asked: wanted === null ? null : statuses,
          absent,
          newSince:
            comparable && matched !== null && previous?.matched != null
              ? Math.max(0, matched - previous.matched)
              : null,
          detailed: wireCount(counted.detailed),
          skippedKnown: wireCount(counted.skipped_known),
          remaining: wireCount(counted.remaining),
          fetched: found.orders.length,
          ingest: written,
        })
        writeLastCheck({ at, matched, statuses: wanted })
        /* RE-READ EITHER WAY. A fetch that brought nothing new still refreshes a ledger another
           device may have moved. */
        await reread()
      } catch (err) {
        if (!live.current) return
        setFailure(describeFailure(err))
      } finally {
        if (live.current) setBusy(null)
      }
    })()
  }

  /* ------------------------------------------------------- the filter's own free read ---- */

  /** Count the window by status. FREE, and it details nothing — `writes_nothing: true` comes
   *  back on the answer. Called when the panel is opened and on its retry, never on a timer:
   *  it is fifteen search pages on this account's three-month window, which is cheap enough to
   *  press and not cheap enough to poll. */
  const loadVocabulary = useCallback(() => {
    setVocabBusy(true)
    setVocabFailure(null)
    void (async () => {
      try {
        const seen = await previewOrders()
        if (!live.current) return
        setVocab(seen)
      } catch (err) {
        if (!live.current) return
        setVocabFailure(describeFailure(err))
      } finally {
        if (live.current) setVocabBusy(false)
      }
    })()
  }, [])

  const onTogglePicker = () => {
    const next = !pickerOpen
    setPickerOpen(next)
    /* Opened with nothing counted yet — including after a failure, so the panel is never a
       dead end. An already-counted window is reused; the press makes its own preview anyway. */
    if (next && !vocabBusy && (vocab === null || vocabFailure !== null)) loadVocabulary()
  }

  /** THE CHOICE IS WRITTEN AS IT IS MADE, not on a Save. There is no version of this panel with
   *  an unsaved state worth having: every tick is idempotent, the fetch reads the same value the
   *  panel draws, and a Save button would be a second source of truth for one boolean each. */
  const onFilterChange = (next: OrderFetchFilter) => {
    /* TOUCHING A TICK IS ANSWERING. Somebody reading the list and unticking a status has done
       the thing the ask exists for, so the panel stops asking from that moment — the confirm
       below is for the person whose answer is "all of them, yes". */
    const answered = { ...next, asked: true }
    setFilter(answered)
    rememberOrderFilter(answered)
  }

  /** The ask's own press: record that this device has been shown the list, and fetch on it. The
   *  answered filter is passed to `onFetch` rather than left to the next render, because the
   *  state has not committed yet and the press must act on what was just agreed. */
  const onConfirmStatuses = () => {
    const answered = { ...filter, asked: true }
    setFilter(answered)
    rememberOrderFilter(answered)
    onFetch(answered)
  }

  /* WHAT THE CONTROL SAYS BEFORE IT IS OPENED. An unchosen device says "All statuses" — which is
     what it will fetch — rather than a count it would have to run a preview to know.

     BOTH FIGURES ARE COUNTED OVER THE SAME WINDOW, which took a correction: `n of 5` off the
     raw tick list read "3 of 5" beside a panel saying "taking 47 of 370", because one of the
     three was a status this window returned none of. A ratio whose halves are counted over
     different sets is the defect this entry is about. Where no window has been counted yet
     there is no denominator to be honest against, so the bare tick count is drawn instead. */
  const statusSummary =
    filter.statuses === null
      ? 'All statuses'
      : filter.statuses.length === 0
        ? 'No statuses'
        : vocab === null
          ? `${filter.statuses.length} ${plural(filter.statuses.length, 'status', 'statuses')}`
          : `${filter.statuses.filter((one) => vocab.by_status.some((row) => row.status === one)).length} of ${
              vocab.by_status.length
            } statuses`

  const statusControl = (
    <Button
      icon="filter"
      iconRight={pickerOpen ? 'minus' : 'plus'}
      onClick={onTogglePicker}
      disabled={busy !== null}
      aria-expanded={pickerOpen}
      aria-controls="orders-status-picker"
      className={filter.statuses === null && !filter.skipKnown ? undefined : 'orders-status-btn-on'}
    >
      {statusSummary}
      {filter.skipKnown ? ' · skipping known' : ''}
    </Button>
  )

  const statusPanel = pickerOpen ? (
    <div id="orders-status-picker" ref={pickerBox}>
      <StatusPicker
        preview={vocab}
        loading={vocabBusy}
        failure={vocabFailure}
        filter={filter}
        busy={busy === 'fetch'}
        onChange={onFilterChange}
        onConfirm={onConfirmStatuses}
        onRetry={loadVocabulary}
      />
    </div>
  ) : null

  /* ------------------------------------------------------------------------ the pull */

  const onPull: PullHandler = (order, line, pick, target) => {
    void (async () => {
      setBusy(`${line.order_key}/${line.sku}/${target.capture_id}`)
      setFailure(null)
      try {
        const done = await pullCopy({ source: order.source, number: order.number, sku: line.sku }, [target])
        if (!live.current) return
        /* `places[0]`, NEVER `sales[0].card.place.label` — see the header. The fallback is the
           pre-press label rather than an invented one. */
        const place = done.places[0]?.label ?? pick.place.label ?? `box ${target.box}, index ${target.index}`
        const name = pick.card_name ?? line.line.name ?? line.sku
        toast({
          kind: 'receipt',
          icon: 'hand',
          title: `Pulled ${name}`,
          body: `from ${place} · order ${order.number}`,
          ttlMs: UNDO_WINDOW_MS,
          action: { label: 'Undo', onPress: () => void undoFromToast(target, place, name) },
        })
        /* BOTH READS, because the card this press sold has to leave every other line's map at the
           same moment it leaves this one. The undo goes the other way through `touchHub`, which
           bumps the version the effect above watches, so it re-reads both as well. */
        await Promise.all([reread(), rereadStore()])
      } catch (err) {
        if (!live.current) return
        setFailure(describeFailure(err))
      } finally {
        if (live.current) setBusy(null)
      }
    })()
  }

  /* ------------------------------------------------------- the two lines that cannot be pulled */

  /* D113. A line whose SKU no card carries can never be closed by a pull — `record_pull` needs a
     `capture_id` and there is no card to mint one. These two presses are the only way such a line
     moves, and before them three real orders sat open with nothing on any screen able to touch
     them. Both re-read on success for `onPull`'s reason: the figure the lede draws is the one this
     press just moved. */

  const onFill = (order: OrderRow, line: ResolvedLine, count: number, reason: OrderFillReason) => {
    void (async () => {
      setBusy(`fill/${line.order_key}/${line.sku}`)
      setFailure(null)
      try {
        const aim = { source: order.source, number: order.number, sku: line.sku }
        const done = await fillLine(aim, count, reason)
        if (!live.current) return
        const name = line.line.name ?? line.sku
        toast({
          kind: 'receipt',
          icon: 'hand',
          title: `Closed ${plural(done.moved, 'copy', 'copies')} of ${name}`,
          body: `by hand · ${reason === 'sealed' ? 'not a single' : 'not photographed here'} · order ${order.number}`,
          ttlMs: UNDO_WINDOW_MS,
          /* The reversal names a COUNT and not a copy, because the fill never held one. It
             reverses exactly what this press recorded — `done.moved` — rather than the line's
             whole hand-filled total, which may include an earlier press the operator meant. */
          action: {
            label: 'Undo',
            onPress: () => {
              void (async () => {
                try {
                  await undoFill(aim, done.moved)
                  touchHub()
                } catch (err) {
                  toast({ kind: 'refusal', icon: 'alert', title: describeFailure(err).message })
                }
              })()
            },
          },
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

  const onDeclareKind = (order: OrderRow, line: ResolvedLine, kind: 'sealed' | 'accessory' | null) => {
    void (async () => {
      setBusy(`kind/${line.order_key}/${line.sku}`)
      setFailure(null)
      try {
        await declareLineKind({ source: order.source, number: order.number, sku: line.sku }, kind)
        if (!live.current) return
        toast({
          kind: 'ok',
          icon: 'package',
          title: kind === null ? 'Claim withdrawn' : `Marked ${kind === 'sealed' ? 'sealed' : 'an accessory'}`,
          body:
            kind === null
              ? 'The feed\'s own word stands again.'
              : 'It ships in a parcel and is picked by hand. It still owes its copies until it is filled.',
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

  /* ------------------------------------------------------------------- the backlog stand-down */

  /* D113. Orders the marketplace has already shipped, which this store never tracked the copies
     of. They are not a fill — many of them went out using copies still sitting in the boxes — so
     nothing is counted and the reason carries the whole meaning. The STATUS proposes the set and
     the operator presses; nothing here branches on it by itself. */
  const onStandDown = (rows: readonly OrderRow[], reason: OrderCloseReason) => {
    void (async () => {
      setBusy('close')
      setFailure(null)
      try {
        const aim = rows.map((row) => ({ source: row.source, number: row.number }))
        const done = await closeOrders(aim, reason)
        if (!live.current) return
        toast({
          kind: 'receipt',
          icon: 'check',
          title: `Stood down ${plural(done.moved, 'order', 'orders')}`,
          body: `${done.still_open} still open · nothing was marked sold`,
          ttlMs: UNDO_WINDOW_MS,
          action: {
            label: 'Undo',
            onPress: () => {
              void (async () => {
                try {
                  await reopenOrders(aim)
                  touchHub()
                } catch (err) {
                  toast({ kind: 'refusal', icon: 'alert', title: describeFailure(err).message })
                }
              })()
            },
          },
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

  /* D113. A line that is not shipping at all — refunded, cancelled, or the copy retired damaged
     and the buyer refunded. IT IS LINE-SHAPED, so one refunded line on a three-line order never
     takes the other two with it. The first build sent the order-shaped call and drew the button
     only where the order had ONE line, which left the multi-line case with no press at all; the
     wire has both scopes now and this is simply the line one. */
  const onCloseLine = (order: OrderRow, line: ResolvedLine, reason: OrderCloseReason) => {
    void (async () => {
      setBusy(`close/${line.order_key}/${line.sku}`)
      setFailure(null)
      try {
        const aim = [{ source: order.source, number: order.number, sku: line.sku }]
        await closeLines(aim, reason)
        if (!live.current) return
        toast({
          kind: 'receipt',
          icon: 'check',
          title: `Closed ${line.line.name ?? line.sku}`,
          body: 'Nothing was marked sold and no copy is claimed to have gone.',
          ttlMs: UNDO_WINDOW_MS,
          action: {
            label: 'Undo',
            onPress: () => {
              void (async () => {
                try {
                  await reopenLines(aim)
                  touchHub()
                } catch (err) {
                  toast({ kind: 'refusal', icon: 'alert', title: describeFailure(err).message })
                }
              })()
            },
          },
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

  /* --------------------------------------------------------------------- what is drawn */

  const setStage = (next: Stage) => {
    window.location.hash = next === 'pull' ? '#/orders' : '#/shipping'
  }

  const orders = payload?.orders ?? []
  const open = orders.filter((one) => one.open)
  const done = orders.filter((one) => !one.open)
  const arriving = hub.arriving === true
  const counts = payload?.resolution.counts ?? null
  const populated = payload !== null && orders.length > 0

  /* The well: the textarea, "Read this paste", and — beside the list — "Fetch from TCGplayer".
     Under the empty state the fetch is the EmptyState's own action, so the well there carries
     only the paste button rather than drawing the same control twice. */
  const wellOf = (withFetch: boolean) => (
    <section className="orders-paste" aria-label="Add orders">
      <label className="bn-field">
        <span className="bn-field-label">Paste the order as JSON</span>
        <textarea
          ref={pasteBox}
          className="bn-textarea bn-input-mono orders-paste-box"
          value={hub.paste}
          onChange={(event) => setHub({ paste: event.target.value })}
          disabled={busy !== null}
          rows={6}
          placeholder={'{"source": "TCGplayer", "number": "…", "lines": [{"sku": "…", "quantity": 1}]}'}
          aria-label="Order JSON"
          spellCheck={false}
        />
      </label>
      <div className="orders-paste-row">
        <Button icon="paste" onClick={onRead} busy={busy === 'ingest'} disabled={busy !== null}>
          Read this paste
        </Button>
        {/* The fetch is behind the same well as the paste: the same errand with the copying done
            for you, arriving at the ledger through the one door `orderPaste.ts` owns. */}
        {withFetch ? (
          <Button icon="refresh" onClick={() => onFetch()} busy={busy === 'fetch'} disabled={busy !== null}>
            Fetch from TCGplayer
          </Button>
        ) : null}
        {/* THE NARROWING SITS BESIDE THE PRESS, NOT IN FRONT OF IT. D91's two-press flow was
            ruled out — *"why would it ever say 1 of 3 found"* — so this is a control the
            operator may never open, and the press works identically if they do not. */}
        {withFetch ? statusControl : null}
      </div>
      {withFetch ? statusPanel : null}
      <p className="orders-paste-source">
        Only the SKU, the count and what the feed called the card leave this browser. An order that names no source is
        stamped {DEFAULT_ORDER_SOURCE}.
      </p>
      {pasteNote === null ? null : (
        <p className="orders-paste-note" role="status">
          <Icon name="info" size={14} />
          {pasteNote}
        </p>
      )}
      {dropped.length === 0 ? null : (
        <p className="orders-paste-dropped" role="status">
          <Icon name="lock" size={14} />
          <span>
            Not sent: <span className="bn-mono">{dropped.join(', ')}</span>. Only the SKU, the count and what the feed
            called the card left this browser.
          </span>
        </p>
      )}
    </section>
  )

  /* The lede carries the ledger's summary once it has answered, so the count pills and the
     sentence that used to sit under the header are one line here. */
  const lede =
    stage === 'pull'
      ? populated && counts !== null
        ? summaryOf(open, done, counts)
        : 'Which copies each buyer gets, and where in the boxes they are. One press per copy, with twenty seconds to take it back.'
      : "TCGplayer's Export Shipping file, sorted into three lanes. The orders it cannot judge are kept apart, for you to decide."

  /* THE TWO ROUTES ARE TABS, NAMED AS THE NAV NAMES THEM. Each is a real link (the hash is the
     router), and the leader chords ride as hover hints where there is a keyboard. */
  const tabs = (
    <div className="bn-tabs orders-tabs" role="tablist" aria-label="Orders and shipping">
      <a
        role="tab"
        className="bn-tab orders-tab"
        href="#/orders"
        aria-selected={stage === 'pull'}
        aria-current={stage === 'pull' ? 'page' : undefined}
        onClick={(event) => {
          event.preventDefault()
          setStage('pull')
        }}
      >
        <Icon name="cart" size={14} />
        Orders
        {payload === null ? null : open.length > 0 ? (
          <Pill size="sm" tone="accent">
            {open.length} open
          </Pill>
        ) : (
          <Pill size="sm">{done.length} done</Pill>
        )}
        {phone ? null : <Kbd>,O</Kbd>}
      </a>
      <a
        role="tab"
        className="bn-tab orders-tab"
        href="#/shipping"
        aria-selected={stage === 'ship'}
        aria-current={stage === 'ship' ? 'page' : undefined}
        onClick={(event) => {
          event.preventDefault()
          setStage('ship')
        }}
      >
        <Icon name="truck" size={14} />
        Shipping
        {hub.batch === null ? (
          <Pill size="sm" outline>
            No export
          </Pill>
        ) : (
          <Pill size="sm" tone="accent">
            {hub.batch.shipments} orders
          </Pill>
        )}
        {phone ? null : <Kbd>,S</Kbd>}
      </a>
    </div>
  )

  return (
    <main className={`orders-hub bn-page ${stage === 'pull' ? 'orders' : 'shipping'}`}>
      <PageHeader
        eyebrow="Sell"
        icon={stage === 'pull' ? 'cart' : 'truck'}
        title={stage === 'pull' ? 'Orders' : 'Shipping'}
        lede={lede}
        actions={
          stage === 'pull' && populated ? (
            <>
              <Button
                icon={arriving ? 'x' : 'plus'}
                aria-expanded={arriving}
                onClick={() => setHub((was) => ({ arriving: was.arriving !== true }))}
              >
                {arriving ? 'Hide' : 'Add orders'}
              </Button>
              {/* The hand-off the sidebar makes, made here too: the Fulfiller's page, in its own tab. */}
              <a className="bn-btn orders-handoff" href="#/fulfillment" target="_blank" rel="noopener">
                <Icon name="hand" size={16} />
                Cards to pull
                <Icon name="external" size={14} />
              </a>
            </>
          ) : undefined
        }
      />

      {tabs}

      {stage === 'ship' ? (
        <ShipStage payload={payload} />
      ) : (
        <PullStage
          payload={payload}
          store={store}
          storeFailed={storeFailed}
          onRereadStore={() => void rereadStore()}
          failure={failure}
          busy={busy}
          filter={hub.filter}
          mode={hub.mode}
          selected={hub.selected}
          wide={wide}
          arriving={arriving}
          well={wellOf(true)}
          emptyWell={wellOf(false)}
          /* The empty state draws its own primary Fetch, so it needs the narrowing beside it —
             the populated path gets both inside `wellOf(true)`, and only one of the two paths
             renders, so the panel is never on screen twice. */
          statusControl={statusControl}
          statusPanel={statusPanel}
          /* The receipt is drawn by the STAGE and not by the well, so closing "Add orders" — or
             arriving at a populated ledger from an empty one — cannot take the remainder away
             with it. */
          receipt={
            receipt === null ? null : (
              <FetchReceipt receipt={receipt} busy={busy === 'fetch'} onFetchMore={onFetch} />
            )
          }
          onPull={onPull}
          onFill={onFill}
          onDeclareKind={onDeclareKind}
          onStandDown={onStandDown}
          onCloseLine={onCloseLine}
          onFetch={onFetch}
          onReread={() => void reread()}
        />
      )}
    </main>
  )
}

/** `#/orders`: the hub with the order list selected. */
export function Orders() {
  return <OrdersHub stage="pull" />
}

/* ================================================================================= pull */

/** The backlog prompt: open orders the marketplace itself reports as already gone (D113).
 *
 *  WHY THIS IS A PROMPT AND NOT A RULE. `store/orders.py`'s two maps exist so `ingest` cannot
 *  write fulfilment at all, and `_order_row` states that `open` is the ledger's answer and never
 *  the feed's `status` string — the vocabulary was never published, so "everything that is not
 *  Ready to Ship" would swallow a `Cancelled` the day that word first appears and record it as
 *  handled. The status PROPOSES the set here and the operator presses. That is `make merge`'s
 *  bargain: automate the lookup, never the decision.
 *
 *  IT IS NOT COSMETIC, WHICH IS WHY IT LEADS RATHER THAN HIDING IN A MENU. `resolve_all` walks
 *  open orders oldest first and `_Draw._taken` stops two orders claiming one copy, so a shipped
 *  order that is still open takes copies away from one that still needs picking. Measured on the
 *  owner's store on 2026-09-06: 69 of 83 open orders were already shipped, holding 31 physical
 *  copies, and three live lines read `short` while their copies sat on the shelf.
 *
 *  THE STATUS STRINGS ARE READ, NEVER MATCHED AGAINST A LIST THIS FILE HOLDS. A hard-coded
 *  roster here would be the same guess the server refuses to make, one layer up. What this knows
 *  is the negative — an order whose status this operator has NOT got queued for picking — and it
 *  shows the strings it found so the sentence names them. */
function BacklogPrompt({
  open,
  busy,
  onStandDown,
}: {
  readonly open: readonly OrderRow[]
  readonly busy: string | null
  readonly onStandDown: StandDownHandler
}) {
  /* IT MATCHES THE POSITIVE AND FAILS CLOSED, AND THE FIRST BUILD DID THE OPPOSITE.
     `status !== 'Ready to Ship'` is the open-ended negative D113 argues against for the SERVER,
     and writing it here was that same guess one layer up: `app/tests/orders.spec.ts` fixes an
     order at `Ready to ship` — a lower-case `s` — and the negative proposed it for stand-down
     immediately. A live order swept into a bulk close is the one outcome this control must never
     produce, and the vocabulary was never published, so a case a future status invents must land
     on the SAFE side by construction rather than by someone remembering to add it.

     So: an order is a candidate only where TCGplayer's own word SAYS it has gone. A status this
     rule does not recognise is left open — the status quo, and visible — where the negative would
     have swept it in. `Cancelled`, whenever that word first appears, is not proposed here at all,
     which is right: a cancellation is `not_shipping` and a decision, not a backlog. */
  const candidates = useMemo(
    /* A NULL STATUS IS NOT A CANDIDATE EITHER, which falls out of the positive match rather than
       needing its own guard: the feed said nothing, so nothing here says it has gone. */
    () => open.filter((row) => (row.status ?? '').trim().toLowerCase().startsWith('shipped')),
    [open],
  )
  const statuses = useMemo(
    () => [...new Set(candidates.map((row) => row.status))].sort(),
    [candidates],
  )
  if (candidates.length === 0) return null
  const busyHere = busy === 'close'

  return (
    <Notice className="orders-backlog" tone="warn" title={`${candidates.length} open ${plural(candidates.length, 'order is', 'orders are')} already gone`}>
      <p>
        TCGplayer reports {candidates.length === 1 ? 'it' : 'them'} as{' '}
        {joinPhrases(statuses.map((status) => `“${status}”`))}, but this store never recorded which
        copies went — so {candidates.length === 1 ? 'it is' : 'they are'} still counted as open, and{' '}
        {candidates.length === 1 ? 'it holds' : 'they hold'} copies away from the orders you still
        have to pick.
      </p>
      <p>
        Standing them down marks <strong>nothing</strong> sold and claims no copy left the building
        — it records only that this store is no longer accounting for them. Any card they shipped
        with is still in its box, and reconciling that is <code>#/inventory</code>&apos;s job.
      </p>
      <div className="orders-standdown-row">
        <Button
          variant="primary"
          icon="check"
          busy={busyHere}
          disabled={busy !== null}
          onClick={() => onStandDown(candidates, 'shipped_elsewhere')}
        >
          Stand down {candidates.length} shipped {plural(candidates.length, 'order', 'orders')}
        </Button>
      </div>
    </Notice>
  )
}

function PullStage({
  payload,
  store,
  storeFailed,
  onRereadStore,
  failure,
  busy,
  filter,
  mode,
  selected,
  wide,
  arriving,
  well,
  emptyWell,
  receipt,
  onPull,
  onFill,
  onDeclareKind,
  onStandDown,
  onCloseLine,
  onFetch,
  statusControl,
  statusPanel,
  onReread,
}: {
  readonly payload: OrdersPayload | null
  /** Every on-hand copy the store holds, keyed by sku. Null while the first read is in flight and
   *  null again when one fails — the maps then draw the resolver's picks alone. */
  readonly store: StoreCopies | null
  readonly storeFailed: boolean
  readonly onRereadStore: () => void
  readonly failure: Failure | null
  readonly busy: string | null
  readonly filter: PullFilter
  readonly mode: PullMode
  readonly selected: string | null
  readonly wide: boolean
  readonly arriving: boolean
  readonly well: ReactNode
  readonly emptyWell: ReactNode
  /** The last fetch's receipt, or null before one has been pressed. */
  readonly receipt: ReactNode
  readonly onPull: PullHandler
  readonly onFill: FillHandler
  readonly onDeclareKind: KindHandler
  readonly onStandDown: StandDownHandler
  readonly onCloseLine: CloseLineHandler
  readonly onFetch: () => void
  readonly statusControl: ReactNode
  readonly statusPanel: ReactNode
  readonly onReread: () => void
}) {
  const hub = useHub()
  const counts = payload?.resolution.counts ?? null

  /** The resolution, keyed so a row can find its own. */
  const answers = useMemo(() => {
    const out = new Map<string, ResolvedOrder>()
    for (const one of payload?.resolution.orders ?? []) out.set(one.key, one)
    return out
  }, [payload])

  /** Which open order was offered which copy, over the whole resolution. */
  const claims = useMemo(() => indexClaims(payload), [payload])

  /** The Ship stage's lane for an order, when an export is loaded. View-only. */
  const lanesByOrder = useMemo(() => {
    const out = new Map<string, ShippingLane>()
    for (const row of hub.batch?.rows ?? []) out.set(row.order, row.lane)
    return out
  }, [hub.batch])

  /* THE OPEN/DONE SPLIT IS `open`, the ledger's answer — never the feed's `status` string. */
  const { open, done } = useMemo(() => {
    const all = payload?.orders ?? []
    return { open: all.filter((one) => one.open), done: all.filter((one) => !one.open) }
  }, [payload])

  const shown = useMemo(
    () =>
      filter === 'all'
        ? open
        : filter === 'done'
          ? done
          : open.filter((one) => (answers.get(one.key)?.lines ?? []).some((line) => line.reason === filter)),
    [filter, open, done, answers],
  )

  /* The selection falls back to the first order shown, so a filter that hides the selected one
     never leaves the detail blank. */
  const selectedKey = selected !== null && shown.some((one) => one.key === selected) ? selected : (shown[0]?.key ?? null)
  const selectedOrder = shown.find((one) => one.key === selectedKey) ?? null

  /* The hash names an order once, on mount; from then on the store leads and the hash follows. */
  useEffect(() => {
    const wanted = orderParam()
    if (wanted !== null) setHub({ selected: wanted })
  }, [])
  useEffect(() => {
    if (mode === 'orders' && selectedKey !== null) mirrorOrderParam(selectedKey)
  }, [mode, selectedKey])

  /* j / k and the arrows step the list where there is a list beside the detail. Never with a
     modifier (Cmd-arrow is the shell's, D51) and never out of a field. */
  useEffect(() => {
    if (!wide || mode !== 'orders' || shown.length === 0) return
    const onKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return
      const target = event.target as HTMLElement | null
      if (target !== null && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.isContentEditable)) return
      const step = event.key === 'j' || event.key === 'ArrowDown' ? 1 : event.key === 'k' || event.key === 'ArrowUp' ? -1 : 0
      if (step === 0) return
      const at = shown.findIndex((one) => one.key === selectedKey)
      const next = shown[Math.min(shown.length - 1, Math.max(0, (at === -1 ? 0 : at) + step))]
      if (next === undefined) return
      event.preventDefault()
      setHub({ selected: next.key })
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [wide, mode, shown, selectedKey])

  const walk = useMemo(() => buildWalk(open, answers), [open, answers])

  const setFilter = (next: PullFilter) => setHub({ filter: next })
  const select = (key: string) => setHub({ selected: key })

  if (failure !== null && payload === null) {
    return (
      <div className="orders-stage">
        <div className="bn-panel">
          <EmptyState
            icon="alert"
            title="The ledger did not answer"
            body={
              <>
                {failure.message} <code className="bn-mono orders-failure-code">{failure.code}</code>
              </>
            }
            actions={
              <Button icon="refresh" onClick={onReread}>
                Try again
              </Button>
            }
          />
        </div>
      </div>
    )
  }

  if (payload === null || counts === null) {
    return (
      <div className="orders-stage orders-skeleton" aria-busy="true" aria-label="Reading the ledger">
        <span className="bn-skeleton orders-skel-line" />
        <span className="bn-skeleton orders-skel-chips" />
        <span className="bn-skeleton orders-skel-card" />
        <span className="bn-skeleton orders-skel-card" />
      </div>
    )
  }

  /* ---------------------------------------------------------------------------- empty */

  if (open.length + done.length === 0) {
    return (
      <div className="orders-stage">
        {failure === null ? null : <Notice tone="danger" title={failure.message} code={failure.code} />}
        <div className="bn-panel orders-empty">
          <EmptyState
            icon="cart"
            title="No orders yet"
            body="Fetch this account's own orders from TCGplayer, or paste one in. Nothing on this screen spends money; the pull is the only write, and it can be taken back."
            actions={
              <>
                <Button variant="primary" size="lg" icon="refresh" onClick={() => onFetch()} busy={busy === 'fetch'} disabled={busy !== null}>
                  Fetch from TCGplayer
                </Button>
                {statusControl}
              </>
            }
          />
          {statusPanel === null ? null : <div className="orders-empty-picker">{statusPanel}</div>}
          {receipt === null ? null : <div className="orders-empty-receipt">{receipt}</div>}
          <div className="bn-rule">or paste one</div>
          {emptyWell}
        </div>
      </div>
    )
  }

  /* -------------------------------------------------------------------------- populated */

  const why = <WhyPanel counts={counts} openByDefault={open.length === 0} />

  const chips = (
    <div className="orders-chips" role="group" aria-label="Show orders by how their lines answered">
      <button type="button" className="orders-chip" aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>
        <Icon name="list" size={13} />
        All open
        <span className="orders-chip-count">{open.length}</span>
      </button>
      {ORDER_REASONS.filter((reason) => counts[reason] > 0).map((reason) => (
        <button
          key={reason}
          type="button"
          className={`orders-chip orders-chip-${REASON_TONE[reason]}`}
          aria-pressed={filter === reason}
          onClick={() => setFilter(reason)}
          title={orderReasonLabel(reason)}
        >
          <Icon name={REASON_ICON[reason]} size={13} />
          {REASON_SHORT[reason]}
          <span className="orders-chip-count">{counts[reason]}</span>
        </button>
      ))}
      <button type="button" className="orders-chip" aria-pressed={filter === 'done'} onClick={() => setFilter('done')}>
        <Icon name="check" size={13} />
        Done
        <span className="orders-chip-count">{done.length}</span>
      </button>
    </div>
  )

  const nothingShown = (
    <div className="bn-panel">
      <EmptyState
        icon={filter === 'done' ? 'check' : 'sparkles'}
        title={filter === 'all' ? 'Nothing outstanding' : filter === 'done' ? 'Nothing fulfilled yet' : `Nothing left under “${REASON_SHORT[filter]}”`}
        body={filter === 'all' ? 'Every order has its copies.' : 'Pick another filter, or show every open order.'}
        actions={
          filter === 'all' ? undefined : (
            <Button icon="list" onClick={() => setFilter('all')}>
              Show all open
            </Button>
          )
        }
      />
    </div>
  )

  const detailOf = (order: OrderRow, variant: 'panel' | 'inline') => (
    <OrderDetail
      key={order.key}
      order={order}
      answer={answers.get(order.key) ?? null}
      lane={lanesByOrder.get(order.number) ?? null}
      store={store}
      claims={claims}
      busy={busy}
      onPull={onPull}
      onFill={onFill}
      onDeclareKind={onDeclareKind}
      onCloseLine={onCloseLine}
      onReread={onReread}
      variant={variant}
    />
  )

  return (
    <div className="orders-stage">
      {failure === null ? null : <Notice tone="danger" title={failure.message} code={failure.code} />}

      {arriving ? (
        <section className="bn-panel orders-arrive" aria-label="Add orders">
          <div className="bn-panel-head">
            <span className="bn-section-title">
              <Icon name="plus" size={16} /> Add orders
            </span>
            <span className="bn-muted orders-arrive-note">paste, or fetch</span>
          </div>
          <div className="bn-panel-body">{well}</div>
        </section>
      ) : null}

      {receipt}

      {/* D113. IT LEADS, ABOVE THE TOOLBAR AND THE LIST, because what it is about is the list
          being wrong — an already-shipped order sitting open takes copies from one that still
          needs picking, so a prompt tucked below the rows would be advice arriving after the
          walk it should have changed. It draws nothing when there is nothing to propose. */}
      <BacklogPrompt open={open} busy={busy} onStandDown={onStandDown} />

      <div className="orders-toolbar">
        <Segmented<PullMode>
          className="orders-mode"
          value={mode}
          label="How to work the orders"
          options={[
            { value: 'orders', label: 'By order', icon: 'cart' },
            { value: 'walk', label: 'Walk the boxes', icon: 'box' },
          ]}
          /* ENTERING THE WALK FREEZES WHAT IT IS A WALK OVER, and only if no pass is already
             held. The set is taken from `open` at that instant, so the figure below counts
             orders leaving it rather than the ledger's whole history.

             A TOGGLE IS NOT THE END OF A PASS, and freezing on every entry made it one. Because
             `walkKeys` is drawn from `open` and an order leaves `open` the moment its last copy
             is recorded, a fresh freeze can never contain an order this pass has finished — so
             stepping out to `By order` and back reset the figure to nothing, ZERO BY
             CONSTRUCTION, which is the same shape as the defect this whole change is about.
             Measured: after one pull the pill read `1 of 2`, and after `By order` → `Walk the
             boxes` it was gone. The pass is held instead, and `onFetch` ends it — new orders off
             TCGplayer are a new sitting, and that is the only boundary the operator draws. */
          onChange={(next) =>
            setHub((current) => ({
              mode: next,
              walkKeys:
                next === 'walk'
                  ? (current.walkKeys ?? new Set(open.map((order) => order.key)))
                  : current.walkKeys,
            }))
          }
        />
        {mode === 'walk' ? (
          <p className="orders-toolbar-note">Every open order&apos;s copies in one pass, in the order the boxes hold them.</p>
        ) : (
          chips
        )}
      </div>

      {/* THE DEGRADED MAP, SAID ONCE. Every line is narrower when the card map did not answer, so
          the sentence belongs here and not repeated down eighty lines. Nothing else is affected:
          the ledger answered, the copies it offered are drawn, and every Pull still works. */}
      {storeFailed ? (
        <p className="orders-store-note" role="status">
          <Icon name="info" size={14} />
          <span>
            The card map did not answer, so each line is showing only the copies this order was offered — not every copy
            the store holds.
          </span>
          <button type="button" className="orders-fold-btn" onClick={onRereadStore}>
            <Icon name="refresh" size={13} />
            Read it again
          </button>
        </p>
      ) : null}

      {mode === 'walk' ? (
        <>
          <WalkView walk={walk} open={open} done={done} walkKeys={hub.walkKeys} busy={busy} onPull={onPull} />
          {why}
        </>
      ) : shown.length === 0 ? (
        <>
          {nothingShown}
          {why}
        </>
      ) : wide ? (
        <div className="orders-layout">
          <nav className="orders-index-pane" aria-label="Orders">
            <ol className="orders-index bn-stagger">
              {shown.map((order, at) => (
                <li key={order.key} style={{ '--i': at } as CSSProperties}>
                  <OrderSummaryRow
                    order={order}
                    answer={answers.get(order.key) ?? null}
                    lane={lanesByOrder.get(order.number) ?? null}
                    selected={order.key === selectedKey}
                    onSelect={() => select(order.key)}
                  />
                </li>
              ))}
            </ol>
            <p className="orders-index-hint">
              <Kbd>J</Kbd>
              <Kbd>K</Kbd> step through the orders
            </p>
          </nav>
          <div className="orders-detail">
            {selectedOrder === null ? null : detailOf(selectedOrder, 'panel')}
            {why}
          </div>
        </div>
      ) : (
        <>
          <ol className="orders-list">
            {shown.map((order, at) => {
              const opened = order.key === selectedKey
              return (
                <li
                  key={order.key}
                  className={`bn-panel orders-acc${opened ? ' orders-acc-open' : ''}`}
                  style={{ '--delay': `${Math.min(at, 8) * 40}ms` } as CSSProperties}
                >
                  <OrderSummaryRow
                    order={order}
                    answer={answers.get(order.key) ?? null}
                    lane={lanesByOrder.get(order.number) ?? null}
                    selected={opened}
                    expanded
                    onSelect={() => select(order.key)}
                  />
                  {opened ? <div className="orders-acc-body">{detailOf(order, 'inline')}</div> : null}
                </li>
              )
            })}
          </ol>
          {why}
        </>
      )}
    </div>
  )
}

/* ================================================================ why each line answered */

function WhyPanel({ counts, openByDefault }: { readonly counts: Record<OrderLineReason, number>; readonly openByDefault: boolean }) {
  /* ALL SIX REASONS, INCLUDING THE ZEROS. `Resolution.counts` returns every one and nothing here
     filters them — reporting only what fired would make "nothing was short" and "nothing was
     checked" the same screen. `sku_unknown` is structurally unreachable from this route and
     always draws a zero; the note says so. */
  return (
    <details className="bn-panel orders-why" open={openByDefault}>
      <summary className="orders-why-summary">
        <Icon name="info" size={16} />
        Why each line answered as it did
        <Icon name="chevronDown" size={14} className="orders-why-chev" />
      </summary>
      <ul className="orders-counts" aria-label="Why each line answered as it did">
        {ORDER_REASONS.map((reason) => (
          <li key={reason} className={`orders-count orders-count-${reason}${counts[reason] === 0 ? ' orders-count-zero' : ''}`}>
            <span className="orders-count-figure">{counts[reason]}</span>
            <span className="orders-count-text">
              <span className="orders-count-label">{orderReasonLabel(reason)}</span>
              <code className="orders-count-machine">{reason}</code>
              {reason === 'sku_unknown' ? <span className="orders-count-note">Not asked on this screen; always 0.</span> : null}
            </span>
          </li>
        ))}
      </ul>
    </details>
  )
}

/* ================================================================== an order, in the list */

function OrderSummaryRow({
  order,
  answer,
  lane,
  selected,
  expanded,
  onSelect,
}: {
  readonly order: OrderRow
  readonly answer: ResolvedOrder | null
  readonly lane: ShippingLane | null
  readonly selected: boolean
  /** Set where the row is an accordion head rather than a list entry beside a detail. */
  readonly expanded?: boolean
  readonly onSelect: () => void
}) {
  const status = statusOf(order, answer)
  const pill = STATUS_PILL[status]
  const placed = whenLabel(order.placed_at)
  const ref = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (selected && expanded !== true) ref.current?.scrollIntoView({ block: 'nearest' })
  }, [selected, expanded])

  return (
    <button
      ref={ref}
      type="button"
      className="orders-index-row"
      aria-current={expanded === true ? undefined : selected ? 'true' : undefined}
      aria-expanded={expanded === true ? selected : undefined}
      onClick={onSelect}
      title={pill.label}
    >
      <span className={`orders-index-dot orders-index-dot-${STATUS_DOT[status]}`} aria-hidden="true" />
      <span className="orders-index-main">
        <span className="orders-index-number">{order.number}</span>
        <span className="orders-index-meta">
          {placed === null ? null : <time dateTime={order.placed_at ?? undefined}>placed {placed}</time>}
          {status === 'ready' || status === 'done' ? null : (
            <Pill size="sm" tone={pill.tone} icon={pill.icon}>
              {pill.label}
            </Pill>
          )}
          {lane === null ? null : (
            <Pill size="sm" tone={LANE_TONE[lane]} icon={LANE_ICON[lane]} outline>
              {ORDER_LANE_LABEL[lane]}
            </Pill>
          )}
        </span>
      </span>
      <span className="orders-index-side">
        <span className="orders-index-figure">
          {order.recorded >= order.wanted ? (
            'all pulled'
          ) : (
            <>
              <b>{order.wanted - order.recorded}</b> left
            </>
          )}
        </span>
        <span
          className={`bn-progress orders-index-bar${order.recorded >= order.wanted ? ' bn-progress-ok' : ''}`}
          role="progressbar"
          aria-valuenow={order.recorded}
          aria-valuemin={0}
          aria-valuemax={order.wanted}
          aria-label="Copies pulled"
        >
          <span style={{ width: `${pctOf(order)}%` }} />
        </span>
      </span>
      {expanded === true ? <Icon name="chevronDown" size={16} className="orders-index-chev" /> : null}
    </button>
  )
}

/* ================================================================== an order, opened */

function OrderDetail({
  order,
  answer,
  lane,
  store,
  claims,
  busy,
  onPull,
  onFill,
  onDeclareKind,
  onCloseLine,
  onReread,
  variant,
}: {
  readonly order: OrderRow
  readonly answer: ResolvedOrder | null
  readonly lane: ShippingLane | null
  readonly store: StoreCopies | null
  readonly claims: Claims
  readonly busy: string | null
  readonly onPull: PullHandler
  readonly onFill: FillHandler
  readonly onDeclareKind: KindHandler
  readonly onCloseLine: CloseLineHandler
  readonly onReread: () => void
  /** `panel` is the detail beside the list; `inline` is the body under an accordion head, which
   *  already drew the number, the date and the bar. */
  readonly variant: 'panel' | 'inline'
}) {
  const status = statusOf(order, answer)
  const pill = STATUS_PILL[status]
  const placed = whenLabel(order.placed_at)

  /* THE FEED'S WORD IS LABELLED AS THEIRS. `status` is TCGplayer's own string, verbatim; drawn
     bare beside our status pill it read as a second opinion from us. */
  const meta = (
    <span className="orders-order-meta">
      {placed === null ? null : (
        <time dateTime={order.placed_at ?? undefined} title={order.placed_at ?? undefined}>
          placed {placed}
        </time>
      )}
      <span className="orders-feed-word">
        {order.status === null ? (
          order.source
        ) : (
          <>
            {order.source} says <q>{order.status}</q>
          </>
        )}
      </span>
    </span>
  )

  const body =
    status === 'done' ? null : answer === null ? (
      <div className="orders-reason orders-reason-warn">
        <Icon name="clock" size={16} />
        <div>
          <p className="orders-line-says">This order is outstanding and was not resolved in this read.</p>
          <p className="orders-line-remedy">Read the ledger again; the resolver answers every open order out of one snapshot.</p>
        </div>
        <Button icon="refresh" onClick={onReread}>
          Try again
        </Button>
      </div>
    ) : (
      <>
        {/* THE WALK PLAN SITS ABOVE THE LINES AND CHANGES NONE OF THEM. It is the density rule one
            register up: which drawers satisfy the most of THIS order, so four different singles
            are fetched in one pass. */}
        <WalkPlan answer={answer} />
        <ol className="orders-lines">
          {answer.lines.map((line) => (
            <OrderLineRow
              key={`${line.order_key}/${line.sku}`}
              order={order}
              line={line}
              store={store}
              claims={claims}
              busy={busy}
              onPull={onPull}
              onFill={onFill}
              onDeclareKind={onDeclareKind}
              onCloseLine={onCloseLine}
            />
          ))}
        </ol>
      </>
    )

  if (variant === 'inline') {
    return (
      <>
        <div className="orders-order-metarow">
          {meta}
          <Pill tone={pill.tone} icon={pill.icon}>
            {pill.label}
          </Pill>
        </div>
        {body}
      </>
    )
  }

  return (
    <article className={`bn-panel orders-order orders-order-${status}`} aria-label={`Order ${order.number}`}>
      <header className="orders-order-head">
        <div className="orders-order-id">
          <h2 className="orders-order-number">{order.number}</h2>
          {meta}
        </div>
        <div className="orders-order-side">
          {lane === null ? null : (
            <Pill tone={LANE_TONE[lane]} icon={LANE_ICON[lane]} outline>
              {ORDER_LANE_LABEL[lane]}
            </Pill>
          )}
          <Pill tone={pill.tone} icon={pill.icon}>
            {pill.label}
          </Pill>
        </div>
      </header>

      {/* THE FIGURE IS THE WHOLE ZERO STATE. An unstarted order — eighteen of the owner's twenty —
          drew a capped grey line with no fill under it, which is a rule with a progressbar role
          rather than progress. The track appears when the first copy is pulled, so it arrives as
          a change rather than sitting there as furniture. */}
      <div className="orders-order-progress">
        <span className="orders-order-figure">
          {order.recorded >= order.wanted ? (
            <>All {order.wanted} pulled</>
          ) : (
            <>
              <b>{order.wanted - order.recorded}</b> {order.wanted - order.recorded === 1 ? 'copy' : 'copies'} still to pull
              {order.recorded === 0 ? null : <i>{order.recorded} already pulled</i>}
            </>
          )}
        </span>
        {order.recorded === 0 ? null : (
          <span
            className={`bn-progress${order.recorded >= order.wanted ? ' bn-progress-ok' : ''}`}
            role="progressbar"
            aria-valuenow={order.recorded}
            aria-valuemin={0}
            aria-valuemax={order.wanted}
            aria-label="Copies pulled"
          >
            <span style={{ width: `${pctOf(order)}%` }} />
          </span>
        )}
      </div>

      {body}
    </article>
  )
}

/* ============================================================================== a line */

/* HOW MANY COPIES ARE DRAWN BEFORE THE REST FOLD. The owner's store holds up to fourteen copies
 * of one card (SKU 9027355, all fourteen in box 3 section 4) and fourteen identical rows, each
 * with its own button, is a wall rather than a choice. Six is the number: it is more candidates
 * than any line on the owner's screen needs — the largest `remaining` across his twenty orders is
 * four — and it leaves 51 of his 59 lines drawing every copy with no fold at all. The eight lines
 * that do fold say how many they hold and where.
 *
 * THE MAP BLOCKS NEVER FOLD. What folds is the pressable rows; the drawers a card sits in are the
 * primary read and every one of them is always on screen. */
const COPIES_SHOWN = 6

/** The two presses for a line no pull can reach (D113).
 *
 *  IT IS DRAWN ONLY WHERE THE REMEDY IS OTHERWISE A DEAD END. `sku_unseen` and `not_a_single`
 *  are the reasons where the resolver has correctly found nothing and no amount of walking the
 *  boxes will change that — the card is not in this store and was never photographed here, or it
 *  is not a card at all. Every other reason has a real remedy already on the row: `short` waits
 *  for stock, `no_copies_on_hand` says stop looking, `resolved` has the pick rows.
 *
 *  THE CLASSIFICATION AND THE FILL ARE TWO PRESSES, NOT ONE, and the shipping lane is why: a
 *  sealed product must be classifiable BEFORE it goes out, because that is what routes it to a
 *  parcel rather than an envelope it does not fit. Folding them together would make the routing
 *  answer unavailable until the moment it stopped mattering.
 *
 *  THE FILL'S REASON IS DERIVED FROM THE CLAIM RATHER THAN ASKED FOR TWICE. A line the operator
 *  has called sealed fills as `sealed`; anything else fills as `off_system`. Both say a copy
 *  WENT — neither is the way to close a refund, which `store/orders.py` refuses to spell through
 *  a count at all and which `POST /orders/close` answers instead. */
function LineStandDown({
  order,
  line,
  progress,
  busy,
  onFill,
  onDeclareKind,
  onCloseLine,
}: {
  readonly order: OrderRow
  readonly line: ResolvedLine
  readonly progress: OrderLineProgress | null
  readonly busy: string | null
  readonly onFill: FillHandler
  readonly onDeclareKind: KindHandler
  readonly onCloseLine: CloseLineHandler
}) {
  const claimed = progress?.declared_kind ?? null
  const sealed = claimed === 'sealed' || claimed === 'accessory' || line.line.kind !== 'single'
  const owed = line.outstanding
  const filling = busy === `fill/${line.order_key}/${line.sku}`
  const claiming = busy === `kind/${line.order_key}/${line.sku}`
  const locked = busy !== null

  /* THE COPIES WERE HERE AND HAVE LEFT, which is a different situation from a SKU this store has
     never seen and takes a different pair of presses. `no_copies_on_hand` covers three truths at
     once — this order's copy went out through `#/inventory`'s sale, another buyer took the last
     one, or it was retired damaged — and `_reason`'s own comment says so. Only the operator knows
     which, so both answers are offered and neither is assumed. */
  const gone = line.reason === 'no_copies_on_hand'
  if (gone) {
    return (
      <div className="orders-standdown">
        {progress !== null && progress.by_hand > 0 ? (
          <p className="orders-standdown-said">
            {plural(progress.by_hand, 'copy', 'copies')} already closed by hand.
          </p>
        ) : null}
        <div className="orders-standdown-row">
          {owed < 1 ? null : (
            <Button
              variant="primary"
              icon="hand"
              busy={filling}
              disabled={locked}
              onClick={() => onFill(order, line, owed, 'sold_separately')}
            >
              I already sent {owed === 1 ? 'it' : `these ${owed}`}
            </Button>
          )}
          {/* THE ONE PLACE `not_shipping` IS REACHABLE, and it is LINE-shaped: on a three-line
              order this closes this line and leaves the other two exactly as they were. */}
          <Button
            icon="undo"
            busy={busy === `close/${line.order_key}/${line.sku}`}
            disabled={locked}
            onClick={() => onCloseLine(order, line, 'not_shipping')}
          >
            It isn&apos;t shipping
          </Button>
        </div>
        <p className="orders-standdown-note">
          {/* THE COUNTS ARE THE EVIDENCE and they are already on the breakdown row above, so this
              says what each press MEANS rather than repeating them. */}
          “I already sent it” records that the copy went out for this order but left through the
          sale on <code>#/inventory</code>, so nothing counted it here — it adds to the order&apos;s
          count and marks nothing sold, because it already is. “It isn’t shipping” closes this line
          claiming no copy went at all — a refund, a cancellation, or a card retired damaged
          {order.lines.length === 1 ? '' : ', leaving the order’s other lines alone'}.
        </p>
      </div>
    )
  }

  return (
    <div className="orders-standdown">
      {/* WHAT IS ALREADY RECORDED, DRAWN BEFORE THE CONTROL THAT ADDS TO IT. The fill is the one
          write on this screen that is not idempotent — it has no capture id to compare — so the
          only thing that can stop a double press is the operator seeing the first one. */}
      {progress !== null && progress.by_hand > 0 ? (
        <p className="orders-standdown-said">
          {plural(progress.by_hand, 'copy', 'copies')} already closed by hand
          {progress.reason === 'sealed' ? ' as a sealed product' : progress.reason === 'off_system' ? ', shipped from outside this store' : ''}.
        </p>
      ) : null}

      <div className="orders-standdown-row">
        {claimed === null ? (
          <Button
            icon="package"
            busy={claiming}
            disabled={locked}
            onClick={() => onDeclareKind(order, line, 'sealed')}
          >
            Not a single
          </Button>
        ) : (
          <Button
            icon="undo"
            busy={claiming}
            disabled={locked}
            onClick={() => onDeclareKind(order, line, null)}
          >
            Not sealed after all
          </Button>
        )}
        {owed < 1 ? null : (
          <Button
            variant="primary"
            icon="hand"
            busy={filling}
            disabled={locked}
            onClick={() => onFill(order, line, owed, sealed ? 'sealed' : 'off_system')}
          >
            {/* THE FIGURE IS IN THE LABEL. This press closes a line the store cannot corroborate,
                so the number it will write belongs where the thumb is rather than in a sentence
                above it — `CLAUDE.md`'s money-moment rule applied to a count. */}
            I shipped {owed === 1 ? 'this' : `these ${owed}`} by hand
          </Button>
        )}
      </div>
      <p className="orders-standdown-note">
        {sealed
          ? 'Recorded as a sealed product picked by hand. Nothing is marked sold — there is no card here to sell.'
          : 'Recorded as shipped from stock this store never photographed. Nothing is marked sold — there is no card here to sell.'}
      </p>
    </div>
  )
}

function OrderLineRow({
  order,
  line,
  store,
  claims,
  busy,
  onPull,
  onFill,
  onDeclareKind,
  onCloseLine,
}: {
  readonly order: OrderRow
  readonly line: ResolvedLine
  readonly store: StoreCopies | null
  readonly claims: Claims
  readonly busy: string | null
  readonly onPull: PullHandler
  readonly onFill: FillHandler
  readonly onDeclareKind: KindHandler
  readonly onCloseLine: CloseLineHandler
}) {
  const remedy = orderReasonRemedy(line.reason)
  const head = headlineOf(line)
  const figure = figureOf(order, line)
  const map = useMemo(() => buildCopyMap(line, store, claims), [line, store, claims])
  /* Pure emphasis, and deliberately not a selection: pointing at a block lights the copies it
     holds so a map of four drawers can be read against twelve rows. It picks nothing, it
     disables nothing, and every row stays pressable while it is lit. */
  const [lit, setLit] = useState<string | null>(null)
  const [unfolded, setUnfolded] = useState(false)
  const leadKey = map.stops.length > 1 ? (map.stops[0]?.key ?? null) : null
  /* A MAP OF ONE COPY IS NOT A MAP. Where the store holds exactly one copy there is nothing to
     rank, and a block saying `Box 3 · 1 copy · Section 1` above a row saying the same thing costs
     two rows to repeat itself — so the map is dropped and the row keeps its whole path.
     Everything with two copies, two sections or two drawers still gets the map. */
  const single = map.copies.length === 1
  /* THE STORE'S OWN FIGURE IS WHAT THE LEDE CLAIMS AGAINST. `on_hand` is `len(available(sku))` on
     the server; drawing this many means the map is the whole truth and may say so. It falls short
     only when the store index did not answer, and then the lede stops saying "all". */
  const whole = map.total >= line.on_hand

  /* The first six in the map's order, PLUS every copy this order was offered wherever it fell —
     the resolver's own choice is never the thing behind the fold. */
  const shown = useMemo(() => {
    if (unfolded || map.copies.length <= COPIES_SHOWN + 2) return map.copies
    const keep = new Set(map.copies.slice(0, COPIES_SHOWN).map((copy) => copy.key))
    for (const copy of map.copies) if (copy.offered) keep.add(copy.key)
    return map.copies.filter((copy) => keep.has(copy.key))
  }, [map, unfolded])
  const folded = map.copies.length - shown.length
  /* Where the folded ones are, so the control names a drawer rather than a number alone. */
  const foldedIn = [...new Set(map.copies.filter((copy) => !shown.includes(copy)).map((copy) => copy.pick.box))]

  return (
    <li className={`orders-line orders-line-${line.reason}`}>
      <div className="orders-line-top">
        <div className="orders-line-text">
          <span className="orders-line-name" title={head.raw ?? undefined}>
            {head.name}
          </span>
          <span className="orders-line-desc">
            {head.detail.map((part) => (
              <span key={part}>{part}</span>
            ))}
          </span>
        </div>
        <LineFigureView figure={figure} />
        <code className="orders-tag orders-line-sku" title={head.raw === null ? 'SKU' : `SKU · ${head.raw}`}>
          {line.sku}
        </code>
      </div>

      {/* A resolved line shows no reason row — the map and the pick rows ARE the answer. Every
          other reason gets a banner: the human label, the remedy, the breakdown, and the machine
          string as a tag at the trailing edge, still greppable and no longer a headline. */}
      {line.reason === 'resolved' ? null : (
        <div className={`orders-reason orders-reason-${REASON_TONE[line.reason]}`}>
          <Icon name={REASON_ICON[line.reason]} size={16} />
          <div>
            <p className="orders-line-says">{orderReasonLabel(line.reason)}</p>
            {remedy === '' ? null : <p className="orders-line-remedy">{remedy}</p>}
            <p className="orders-line-breakdown">{breakdownOf(line)}</p>
            {/* D113. The THREE reasons whose remedy is otherwise a dead end get the presses that
                can actually move them. `short` is deliberately not among them: while copies are
                still on hand the remedy really is to pull them, and a fill button there would
                invite closing a line whose cards are sitting in box 3. */}
            {line.reason === 'sku_unseen' ||
            line.reason === 'not_a_single' ||
            line.reason === 'no_copies_on_hand' ? (
              <LineStandDown
                order={order}
                line={line}
                progress={order.progress.find((row) => row.sku === line.sku) ?? null}
                busy={busy}
                onFill={onFill}
                onDeclareKind={onDeclareKind}
                onCloseLine={onCloseLine}
              />
            ) : null}
          </div>
          <code className="orders-tag orders-line-reason">{line.reason}</code>
        </div>
      )}

      {single || map.stops.length === 0 ? null : <CopyMapView map={map} whole={whole} lit={lit} onLight={setLit} />}

      {map.copies.length === 0 ? null : (
        <ol
          className="orders-picks orders-line-picks"
          /* THE MAP IS THE ROWS' HEADING. Where every copy of this line sits in one box and one
             section, the block above has already said which — and the path down every row is then
             the same string repeated in front of the only part that differs, the card figure.
             `.orders-walk-list` makes the identical argument for a walk group. */
          data-one-place={
            !single && map.stops.length === 1 && (map.stops[0]?.sections.length ?? 0) === 1 ? 'true' : undefined
          }
        >
          {shown.map((copy, at) => (
            <PickLine
              key={copy.key}
              order={order}
              line={line}
              pick={copy.pick}
              offered={copy.offered}
              claimedBy={copy.claimedBy}
              busy={busy}
              onPull={onPull}
              /* The heading already names the card; the row repeats it only where the store's
                 name for THIS copy differs from it. */
              name={
                text(copy.pick.card_name) && copy.pick.card_name.toLowerCase() !== head.name.toLowerCase()
                  ? copy.pick.card_name
                  : null
              }
              /* Same rule the name follows: the heading has already said what the buyer bought, so
                 the row repeats the condition only where THIS copy's differs from it. */
              hideCondition={
                head.condition !== null && (copy.pick.condition ?? '').toLowerCase() === head.condition.toLowerCase()
              }
              stopKey={copy.pick.place.label === null ? `pooled/${copy.pick.place.game ?? ''}` : `box/${copy.pick.box}`}
              lit={lit}
              lead={leadKey}
              delay={Math.min(at, 8) * 24}
            />
          ))}
          {/* ONE CONTROL, BOTH WAYS. Collapsed it names how many it holds and which drawer they
              are in; open it says how many are now on screen, so the figure is never lost. */}
          {map.copies.length <= COPIES_SHOWN + 2 ? null : (
            <li className="orders-fold">
              <button
                type="button"
                className="orders-fold-btn"
                aria-expanded={unfolded}
                onClick={() => setUnfolded((was) => !was)}
              >
                <Icon name={unfolded ? 'chevronUp' : 'chevronDown'} size={14} />
                {unfolded ? (
                  <>Show fewer — all {map.copies.length} are on screen</>
                ) : (
                  <>
                    Show the other {folded} {folded === 1 ? 'copy' : 'copies'}
                    {foldedIn.length === 1 ? ` in Box ${foldedIn[0]}` : ''}
                  </>
                )}
              </button>
            </li>
          )}
          {/* ALREADY PULLED, AND NOT DRAWN AS A PLACE. A pulled copy is sold, so it has left the
              box and has no drawer to walk to; the ledger's own count is the honest form of it,
              and hiding it entirely would leave the remaining figure unexplained. */}
          {figure.pulled === 0 ? null : (
            <li className="orders-pulled-note">
              <Icon name="check" size={13} />
              {figure.pulled} {figure.pulled === 1 ? 'copy has' : 'copies have'} already been pulled for this order and left
              the box.
            </li>
          )}
        </ol>
      )}
    </li>
  )
}

/* ---------------------------------------------------------------- the figure on a line */

/** `2 remaining`, with `1 already pulled` kept quiet beside it. Never `1 of 3 found`, and the
 *  buyer's quantity is never a denominator here (the owner's ruling, 2026-09-03). */
function LineFigureView({ figure }: { readonly figure: LineFigure }) {
  if (figure.remaining === 0) {
    return (
      <span className="orders-line-figure orders-line-figure-done">
        <Pill tone="ok" icon="check">
          All {figure.wanted} pulled
        </Pill>
      </span>
    )
  }
  return (
    <span className="orders-line-figure">
      <span className="orders-line-remaining">
        <b>{figure.remaining}</b> remaining
      </span>
      {figure.pulled === 0 ? null : <span className="orders-line-pulled">{figure.pulled} already pulled</span>}
    </span>
  )
}

/* ------------------------------------------------------------------------- the copy map */

/** The boxes that hold this card, densest first. It RANKS — the leader wears a quiet marker and
 *  nothing else changes: no copy is hidden, none is preselected, and the rows beneath are drawn
 *  in this same order.
 *
 *  WHAT IT DRAWS IS EVERY COPY THE STORE HOLDS, not the handful the resolver offered. The apology
 *  that used to sit here — "the store holds 3 copies, this is the one this order was offered" —
 *  is deleted with the defect it described: the copies come from `GET /inventory` now, the map is
 *  the union, and the lede states the total as a fact again. */
function CopyMapView({
  map,
  whole,
  lit,
  onLight,
}: {
  readonly map: CopyMap
  /** Whether the store index answered, so `All 14 copies` may be said. When it did not, the map
   *  is the resolver's picks alone and the sentence claims nothing about what it cannot see. */
  readonly whole: boolean
  readonly lit: string | null
  readonly onLight: (key: string | null) => void
}) {
  const lead = map.stops[0] ?? null
  const runnerUp = map.stops[1] ?? null

  /* THE RECOMMENDATION IS SAID AS WELL AS DRAWN, and it says WHY it leads — a drawer holding two
     of three copies is a different recommendation from four drawers holding one each, where the
     only thing separating them is the box number. */
  const head = `${whole ? 'All ' : ''}${map.total} ${map.total === 1 ? 'copy' : 'copies'}`
  const lede = ((): string | null => {
    if (lead === null) return null
    if (runnerUp === null) {
      if (lead.pooled) return `${head} of this card are pooled — a count, not a place.`
      const section = lead.sections[0] ?? null
      if (lead.sections.length > 1 && section !== null) {
        return `${head} of this card sit in ${lead.title} — ${section.label} holds ${section.total} of them.`
      }
      const where = section === null || section.label === 'No section' ? '' : `, ${section.label}`
      return `${head} of this card sit in ${lead.title}${where}.`
    }
    const spread = `${head} across ${map.stops.length} boxes — `
    if (lead.total > runnerUp.total) return `${spread}${lead.title} holds ${lead.total} of them.`
    if (lead.free > runnerUp.free) return `${spread}${lead.title} leads, because copies elsewhere are spoken for.`
    return `${spread}no drawer holds more, so ${lead.title} leads on the lower number.`
  })()

  return (
    <div className="orders-map" role="group" aria-label={`Where the ${map.total} ${map.total === 1 ? 'copy is' : 'copies are'}`}>
      {lede === null ? null : (
        <p className="orders-map-lede">
          <Icon name="layers" size={13} />
          {lede}
        </p>
      )}
      <ol className="orders-map-stops bn-stagger">
        {map.stops.map((stop, at) => (
          <li
            key={stop.key}
            className="orders-map-stop"
            /* ONE VISUAL LANGUAGE FOR EVERY LINE. A line whose copies all sit in one drawer has a
               leader too — trivially, that drawer — and marking it only when a second box turned
               up made the commonest map a flat grey pill while the rare one carried a pin. The
               pooled bucket is the exception and stays unmarked: it is a count, not a stop. */
            data-lead={at === 0 && !stop.pooled ? 'true' : undefined}
            data-lit={lit === stop.key ? 'true' : undefined}
            data-pooled={stop.pooled ? 'true' : undefined}
            style={{ '--i': at } as CSSProperties}
            onMouseEnter={() => onLight(stop.key)}
            onMouseLeave={() => onLight(null)}
          >
            {at === 0 && !stop.pooled ? (
              <>
                <span className="bn-sr">{runnerUp === null ? 'The drawer to walk to. ' : 'Most copies here. '}</span>
                <Icon name="pin" size={13} className="orders-map-pin" />
              </>
            ) : null}
            <span className="orders-map-name">
              <b>{stop.title}</b>
              {stop.name === null ? null : <em>{stop.name}</em>}
            </span>
            <span className="orders-map-count">
              <b>{stop.total}</b> {stop.total === 1 ? 'copy' : 'copies'}
            </span>
            {stop.spoken === 0 ? null : (
              <span className="orders-map-spoken">
                <Icon name="lock" size={11} />
                {stop.spoken} spoken for
              </span>
            )}
            {/* Copies in this drawer that another OPEN order was offered. They stay pressable —
                the rank is what moves, not the button — so this is said, not enforced. */}
            {stop.claimed === 0 ? null : (
              <span className="orders-map-claimed">
                <Icon name="cart" size={11} />
                {stop.claimed} wanted elsewhere
              </span>
            )}
            <span className="orders-map-sections">
              {stop.sections.map((section, sectionAt) => (
                <span
                  key={section.key}
                  className="orders-map-sect"
                  aria-label={`${section.label}, ${section.total} ${section.total === 1 ? 'copy' : 'copies'}`}
                  /* The leading section is marked whether or not there is a second BOX to rank
                     against: a card sitting twice in section 1 and once in section 5 of one
                     drawer still has a section worth reaching into first. */
                  data-lead={at === 0 && stop.sections.length > 1 && sectionAt === 0 ? 'true' : undefined}
                >
                  {section.label}
                  <b>×{section.total}</b>
                </span>
              ))}
            </span>
          </li>
        ))}
      </ol>
    </div>
  )
}

/* ------------------------------------------------------------------------- the walk plan */

/** The whole order in one pass: the boxes ranked by how much of it each satisfies. Additive —
 *  every line's own map is unchanged by what this says. */
function WalkPlan({ answer }: { readonly answer: ResolvedOrder }) {
  const plan = useMemo(() => buildWalkPlan(answer), [answer])
  if (plan.stops.length === 0 || answer.lines.length < 2) return null
  return (
    <section className="orders-plan" aria-label="Walk plan for this order">
      <header className="orders-plan-head">
        <span className="bn-label">Walk plan</span>
        <span className="orders-plan-note">
          {plan.stops.length === 1 ? 'One box holds this whole order.' : `${plan.stops.length} boxes, fullest first — one pass does it.`}
        </span>
      </header>
      <ol className="orders-plan-stops bn-stagger">
        {plan.stops.map((stop, at) => (
          <li key={stop.key} className="orders-plan-stop" data-lead={at === 0 ? 'true' : undefined} style={{ '--i': at } as CSSProperties}>
            <span className="orders-plan-rank" aria-hidden="true">
              {at + 1}
            </span>
            <span className="orders-plan-text">
              <span className="orders-plan-name">
                <b>{stop.title}</b>
                {stop.name === null ? null : <em>{stop.name}</em>}
              </span>
              <span className="orders-plan-count">
                {stop.copies} {stop.copies === 1 ? 'copy' : 'copies'} · {stop.cards} {stop.cards === 1 ? 'card' : 'cards'}
              </span>
              {stop.pooled ? null : (
                <span className="orders-plan-sect">
                  {stop.sections.length === 1 ? 'Section' : 'Sections'} {stop.sections.join(', ')}
                </span>
              )}
            </span>
          </li>
        ))}
      </ol>
    </section>
  )
}

/* ============================================================================== a copy */

function PickLine({
  order,
  line,
  pick,
  busy,
  onPull,
  name,
  showOrder,
  delay,
  hideCondition,
  stopKey,
  lit,
  lead,
  offered,
  claimedBy,
}: {
  readonly order: OrderRow
  readonly line: ResolvedLine
  readonly pick: PickRow
  readonly busy: string | null
  readonly onPull: PullHandler
  readonly name: string | null
  readonly showOrder?: boolean
  readonly delay?: number
  /** Set where the line's heading already carries this copy's condition. */
  readonly hideCondition?: boolean
  /** Which block of the line's map this copy belongs to, so the block and its rows can be read
   *  against each other. Absent in the walk, which has no map. */
  readonly stopKey?: string
  readonly lit?: string | null
  readonly lead?: string | null
  /** This copy is one the resolver offered THIS line — the machine's own choice, marked so the
   *  operator can take it or ignore it. Absent in the walk, where every row is an offered copy. */
  readonly offered?: boolean
  /** Another open order was offered this copy. Said, never enforced. */
  readonly claimedBy?: string | null
}) {
  const target = aimOf(line, pick)
  const pressing = target !== null && busy === `${line.order_key}/${line.sku}/${target.capture_id}`
  const full = `${pick.card_name ?? line.line.name ?? line.sku}${pick.condition === null ? '' : ` · ${pick.condition}`}`
  return (
    <li
      className={`orders-pick${pick.held_by !== null ? ' orders-pick-is-held' : ''}`}
      data-offered={offered === true ? 'true' : undefined}
      data-box={pick.box}
      data-index={pick.index}
      data-capture-id={pick.capture_id ?? undefined}
      data-pressing={pressing ? 'true' : undefined}
      data-lit={stopKey !== undefined && lit === stopKey ? 'true' : undefined}
      data-lead={stopKey !== undefined && lead === stopKey ? 'true' : undefined}
      style={delay === undefined ? undefined : ({ '--delay': `${delay}ms` } as CSSProperties)}
    >
      <span className="orders-pick-place">
        {pick.place.label === null ? (
          /* A POOLED COPY HAS NO POSITION AND SAYS SO (D24). */
          <span className="orders-pick-pooled">
            <Icon name="layers" size={14} />
            {text(pick.place.game_display) ? `${pick.place.game_display} · pooled` : 'Pooled'}
          </span>
        ) : (
          /* The place is a way into the box: `#/inventory?box=` is what the inventory reads. */
          <a className="orders-pick-link" href={`#/inventory?box=${pick.box}`} title={`Open box ${pick.box} in the inventory`}>
            <PositionLabel label={pick.place.label} lead="slot" boxNote={pick.place.box_name ?? null} />
          </a>
        )}
      </span>
      <span className="orders-pick-card" title={full}>
        {name === null ? null : <span className="orders-pick-name">{name}</span>}
        {pick.condition === null || hideCondition === true ? null : <span className="orders-pick-cond">{pick.condition}</span>}
        {/* WHICH COPY THE MACHINE WOULD HAVE TAKEN, said and not acted on. It is a mark on an
            ordinary row: same ground, same button, same place in the order — the operator's eye
            is told where the resolver landed and nothing is decided for him. */}
        {offered === true ? <span className="orders-pick-offered">Offered</span> : null}
        {/* ANOTHER OPEN ORDER WAS OFFERED THIS ONE. Take it and that order re-resolves onto a
            different copy, or goes short — worth knowing before the press, not after it. The
            button stays: this is the fact, not a veto. */}
        {text(claimedBy) ? (
          <span className="orders-pick-claim" title={`Order ${claimedBy} was offered this copy`}>
            <Icon name="cart" size={11} />
            wanted by <span className="bn-mono">{claimedBy}</span>
          </span>
        ) : null}
        {showOrder === true ? (
          <button
            type="button"
            className="orders-pick-order"
            onClick={() => setHub({ mode: 'orders', selected: order.key })}
            title={`Show order ${order.number}`}
          >
            <Icon name="cart" size={11} />
            {order.number}
          </button>
        ) : null}
      </span>
      {/* SPOKEN FOR, DRAWN AS A FACT RATHER THAN A DISABLED BUTTON. `held_by` says this exact
          card is already recorded against a line; offering it again would walk the picker to one
          drawer for two envelopes. */}
      {pick.held_by !== null ? (
        <span className="orders-pick-held">
          <Icon name="lock" size={13} />
          Spoken for by <span className="bn-mono">{pick.held_by.order}</span>
        </span>
      ) : target === null ? (
        <span className="orders-pick-held">
          <Icon name="info" size={13} />
          {pick.capture_id === null ? 'This copy has no capture record, so it cannot be pulled from here.' : 'Not offered for this reason.'}
        </span>
      ) : (
        <Button
          /* THE ONE PLACE THE MAP'S RANK REACHES THE BUTTON, and it is a state rather than a
             recommendation: a copy another order is counting on is quieter than one nobody is.
             Every other copy — offered or found in the store, near drawer or far — carries the
             same primary Pull, because ranking is not picking. */
          variant={text(claimedBy) ? 'default' : 'primary'}
          size="sm"
          icon="hand"
          className="orders-pull"
          data-capture-id={target.capture_id}
          onClick={() => onPull(order, line, pick, target)}
          busy={pressing}
          disabled={busy !== null && !pressing}
        >
          Pull
        </Button>
      )}
    </li>
  )
}

/* ============================================================================ the walk */

function WalkView({
  walk,
  open,
  done,
  walkKeys,
  busy,
  onPull,
}: {
  readonly walk: Walk
  readonly open: OrderRow[]
  readonly done: OrderRow[]
  readonly walkKeys: ReadonlySet<string> | null
  readonly busy: string | null
  readonly onPull: PullHandler
}) {
  const wanted = open.reduce((sum, order) => sum + order.wanted, 0)
  const recorded = open.reduce((sum, order) => sum + order.recorded, 0)
  const pct = wanted > 0 ? Math.min(100, Math.round((recorded / wanted) * 100)) : 0
  /* THE SECOND FIGURE IS IN THE OTHER UNIT, and that is the whole reason it is here. The
     figure above counts CARDS and a card is what the walk hands you; what you pack is an
     ENVELOPE, and an order two copies short is as unpackable as one nothing has been pulled
     for. So the walk also says how many orders are whole.

     IT IS COUNTED OVER `done` AND NOT OVER `open`, WHICH IS NOT A DETAIL. `open` is the
     ledger's answer to "does this still owe copies" (`server/capture_server.py:_order_row`,
     which refuses to read the feed's `status` string for it), so the moment an order's last
     copy is pulled it LEAVES `open` — a count of finished orders taken over `open` is zero
     by construction, always, and the walk is where that is least visible because the rows
     vanish with it. Measured on this store: pulling the one copy of order A47CCC-13B33
     moved the page header from `20 open orders` to `19 open orders and 1 done`.

     AND THERE IS NO DENOMINATOR AT ALL ANY MORE (D96, amended 2026-09-04). It was `open + done`
     — the pair the page header prints, chosen so the two could not disagree — and `done` is
     every order the ledger has EVER completed, with no window and nothing pruned
     (`capture_server.do_orders` sorts the whole of `ledger.orders`). Correct on the day it was
     measured, at 20 open and 0 done, and wrong for ever after: a store with 200 completed and
     3 open read `200 of 203` on a three-order walk, a lifetime statistic wearing a progress
     figure's clothes.

     FREEZING THE DENOMINATOR TO THIS PASS FIXED THAT AND BOUGHT A WORSE STATE. Orders arrive
     while you walk — the screen re-reads after every pull — so a pass over {A, B} with both
     pulled draws `2 of 2 orders fully pulled` beside a head reading `3 still to pull across 1
     open order`. A fraction that has reached its own denominator says FINISHED, over a screen
     with work on it, and no wording rescues that: the figure is complete and the work is not.

     SO IT IS A COUNT. `2 orders complete in this pass` cannot claim completion, because it never
     had a total to reach. `walkKeys` is still what makes `in this pass` mean anything — the set
     frozen when the walk began — and the count is its members that have LEFT `open`, which
     starts at 0 and only rises, and is therefore NOT the zero-by-construction figure this
     comment rejects above.

     `complete` AND NOT `fully pulled`, WHICH IS WHAT IT SAID. An order reaches `done` by any
     route — a sale marked on `#/inventory`, an ingest, another device — and this screen sees
     none of them. The old verb claimed presses the figure cannot account for.

     WHAT IS GIVEN UP IS NAMED: the walk's figure and the page's headline can now disagree, and
     that agreement is what the old denominator was bought for. It is the right trade because
     they answer different questions — the headline is about the ledger, this is about the
     sitting you are in. A `null` set draws nothing rather than falling back to the lifetime
     figure: a fallback that silently restores it is how it would come back. */
  const passComplete = walkKeys === null ? 0 : done.filter((order) => walkKeys.has(order.key)).length
  const next = walk.rows[0] ?? null

  if (walk.rows.length === 0) {
    return (
      <div className="bn-panel">
        <EmptyState
          icon="check"
          title="Nothing left to walk"
          body={open.length === 0 ? 'Every order has its copies.' : 'No open order has a copy this screen can pull from here; each order says why.'}
        />
      </div>
    )
  }

  return (
    <div className="orders-walk">
      <div className="orders-walk-head">
        <div className="orders-walk-progress">
          {/* THE SAME REGISTER AS A LINE'S FIGURE: what is left to fetch, with what has already
              gone kept quiet beside it. */}
          <p className="orders-walk-figure">
            <strong>{Math.max(0, wanted - recorded)}</strong>
            <span>
              still to pull across {open.length} open order{open.length === 1 ? '' : 's'}
              {recorded === 0 ? '' : ` · ${recorded} already pulled`}
            </span>
            {/* Drawn only once one is whole, by the bar's own rule beside it: none finished is
                the state every walk starts in, and a figure that reads 0 on arrival is not one
                anybody acts on. It says `orders` in the label because the figure it sits next
                to counts cards. */}
            {passComplete === 0 ? null : (
              <Pill size="sm" icon="check">
                {passComplete} order{passComplete === 1 ? '' : 's'} complete in this pass
              </Pill>
            )}
          </p>
          {/* The same rule as an order's own meter: nothing pulled yet is a figure, not a track. */}
          {recorded === 0 ? null : (
            <span
              className={`bn-progress orders-walk-bar${recorded >= wanted ? ' bn-progress-ok' : ''}`}
              role="progressbar"
              aria-valuenow={recorded}
              aria-valuemin={0}
              aria-valuemax={wanted}
              aria-label="Copies pulled"
            >
              <span style={{ width: `${pct}%` }} />
            </span>
          )}
        </div>
        {next === null ? null : (
          <div className="orders-walk-next">
            <span className="orders-walk-next-label">Next</span>
            <span className="orders-walk-next-place">
              {next.pick.place.label ?? (text(next.pick.place.game_display) ? `${next.pick.place.game_display} · pooled` : 'Pooled')}
            </span>
            <span className="orders-walk-next-card">
              {next.pick.card_name ?? next.line.line.name ?? next.line.sku}
              {next.pick.condition === null ? '' : ` · ${next.pick.condition}`}
            </span>
          </div>
        )}
      </div>

      {walk.groups.map((group) => (
        <section key={group.key} className="bn-panel orders-walk-group" aria-label={group.title}>
          <header className="orders-walk-group-head">
            <span className="orders-walk-group-title">{group.title}</span>
            {group.note === null ? null : <span className="orders-walk-group-note">{group.note}</span>}
            <span className="orders-walk-group-count">
              {group.rows.length} {group.rows.length === 1 ? 'card' : 'cards'}
            </span>
          </header>
          <ol className="orders-picks orders-walk-list">
            {group.rows.map((row, at) => (
              <PickLine
                key={row.key}
                order={row.order}
                line={row.line}
                pick={row.pick}
                busy={busy}
                onPull={onPull}
                name={row.pick.card_name ?? row.line.line.name ?? row.line.sku}
                showOrder
                delay={Math.min(at, 12) * 30}
              />
            ))}
          </ol>
        </section>
      ))}
    </div>
  )
}
