import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from 'react'

import { Button, Chip, EmptyState, Icon, Kbd, Notice, PageHeader, Pill, Segmented, type IconName, type PillTone } from './kit'
import { toast } from './kit/toast'
import { readPaste, DEFAULT_ORDER_SOURCE } from './orderPaste'
import { isOrderReason, ORDER_REASONS, orderReasonLabel, orderReasonRemedy } from './orderReasons'
import { rememberHideSold, rememberOrderFilter, storedHideSold, storedOrderFilter, type OrderFetchFilter } from './deviceMemory'
import { hubState, setHub, touchHub, useHub, type PullFilter, type Stage } from './OrdersHubStore'
import { isEditableTarget } from './keys'
import { PositionLabel } from './PositionLabel'
import { groupBuyers, groupForOrderKey, type BuyerGroup } from './orderBuyers'
import {
  applyTake,
  DEFAULT_ORDER_VIEW,
  orderStalenessSentence,
  passesHideUnknown,
  passesQuery,
  passesStatus,
  sortGroups,
  staleCount,
  statusVocabulary,
  takeOrder,
  TAKE_IS_CURRENT,
  type OrderSort,
  type OrderTake,
  type OrderView,
} from './orderView'
import {
  closeLines,
  closeOrders,
  declareLineKind,
  describeFailure,
  fetchOrderPicks,
  fetchOrders,
  fillLine,
  getInventoryCopies,
  getOrders,
  ingestOrders,
  nameOrders,
  previewOrders,
  pullCopy,
  reconcileBacklog,
  reopenLines,
  reopenOrders,
  undoFill,
  undoPull,
} from './server'
import type { Failure } from './server'
import { ShipStage } from './OrdersShipStage'
import { useOrderWalk, WalkList, WalkMainPane, type WalkPullFn, type WalkUndoFn } from './OrdersWalkPane'
import { Overlay } from './InventoryOverlay'
import './BoxBrowse.css'
import './BoxOps.css'
import type {
  IngestResult,
  Inventory,
  InventoryCard,
  NamesResult,
  OrderCloseReason,
  OrderFillReason,
  OrderLineProgress,
  OrderLineReason,
  OrderPicksPayload,
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
  /** How many looped calls this press made — the all-statuses, skip-known backfill
   *  (`D193`) can take several while `remaining > 0`. `null` for the
   *  narrowed (statuses-picked) path, which has always been one call. */
  readonly batches: number | null
  /** How many buyer names `/orders/names` actually wrote — never sent on the narrowed path. */
  readonly named: number | null
  /** Seconds until the next batch fires on its own, or `null` when nothing is queued — drawn as
   *  "continuing in Ns" so a loop that paces itself does not read as done between batches. */
  readonly continuingInS: number | null
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
  onStop,
}: {
  readonly receipt: FetchReceiptData
  readonly busy: boolean
  readonly onFetchMore: () => void
  /** Cancels a looped all-statuses backfill between batches — `null` where nothing is looping,
   *  which draws no Stop control at all. */
  readonly onStop?: () => void
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
    took.push(<Fig key="known" n={receipt.skippedKnown} of="already known" />)
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
  if (receipt.named !== null && receipt.named > 0) {
    took.push(<Fig key="named" n={receipt.named} of={plural(receipt.named, 'buyer named', 'buyers named')} />)
  }
  if (receipt.batches !== null && receipt.batches > 1) {
    took.push(<Fig key="batches" n={receipt.batches} of="batches" />)
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
        {/* THE LOOP PACES ITSELF, and a batch on its way says so rather than reading as
            finished mid-backfill: `continuingInS` is set only while another call is queued. */}
        {receipt.continuingInS !== null ? (
          <p className="orders-receipt-line orders-receipt-continuing" role="status">
            <Icon name="clock" size={14} />
            continuing in {receipt.continuingInS}s
            {onStop === undefined ? null : (
              <Button size="sm" icon="x" onClick={onStop}>
                Stop
              </Button>
            )}
          </p>
        ) : receipt.remaining !== null && receipt.remaining > 0 ? (
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
          <p className="orders-statuses-note">No orders in this window.</p>
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
                <b>Which of these are worth fetching?</b> Nothing fetched yet — remembered on this device.
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
                    <span className="orders-status-known">{row.known.toLocaleString()} already known</span>
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
            <span className="orders-status-name">Skip orders already held at that status</span>
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
            Remembered on this device.
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

function indexStore(inventory: Pick<Inventory, 'cards'>): StoreCopies {
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

/** Every SKU any open order's line names, deduped — the set `POST /inventory/copies` is asked
 *  about. `resolution.orders` is already in hand off `GET /orders`; nothing here re-derives it
 *  from a walk or a claim. */
function skusOf(payload: OrdersPayload | null): string[] {
  const out = new Set<string>()
  for (const order of payload?.resolution.orders ?? []) {
    for (const line of order.lines) out.add(line.sku)
  }
  return [...out]
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

function indexClaims(answers: ReadonlyMap<string, ResolvedOrder>): Claims {
  const out = new Map<string, string>()
  for (const order of answers.values()) {
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

/** Does this order still have a body worth drawing — a walk, its lines, a Pull button — even
 *  though `order.open` says no? An order the marketplace calls done for having every copy
 *  pulled already (`!open`, not `terminal`, nothing owed) has nothing left to walk, same as
 *  before. An order the marketplace calls done for its OWN reasons while copies are still
 *  owed (`terminal` and `wanted > recorded`) is the one the owner wants opened back up —
 *  `terminal` is `types.ts`'s own field now, off `server/capture_server.py:_order_row`. */
function ownsAWalkableBody(order: OrderRow): boolean {
  if (order.open) return true
  return order.terminal && order.wanted > order.recorded
}

function statusOf(order: OrderRow, answer: ResolvedOrder | null): Status {
  if (!order.open) return 'done'
  if (answer === null) return 'unresolved'
  const reasons = answer.lines.map((line) => line.reason)
  if (reasons.some((reason) => reason !== 'resolved' && reason !== 'short')) return 'look'
  if (reasons.some((reason) => reason === 'short')) return 'short'
  return 'ready'
}

const STATUS_PILL: Record<Status, { label: string; tone: PillTone; icon: IconName }> = {
  /* THE WORD IS "Ready" — one word, not "Ready to sell" (owner's ruling, 2026-09-19). */
  ready: { label: 'Ready', tone: 'ok', icon: 'check' },
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

/* The six reasons: a short label for the filter select's own options, a tone and an icon for
   the line's own reason banner, and a phrase for the summary sentence. The long human label
   (`orderReasonLabel`) and the remedy stay on the line that has the problem, and the machine
   string rides THERE as a tag — never on the filter. */
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
    /* Clear `lastPull` only if this is still the pull it names — a later pull may already
       have replaced it, and undoing THIS one must not erase THAT one's own way back. */
    setHub((current) => ({
      busy: null,
      lastPull: current.lastPull?.target.capture_id === target.capture_id ? null : current.lastPull,
    }))
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

/** THE INBOUND LINK — `#/orders?order=<order key>`, READ HERE AND WRITTEN ELSEWHERE.
 *
 *  A caller that knows WHICH ORDER but not WHOSE links with this: `CardLocations`' wanted
 *  pill is the first, and the shape was anticipated before the link existed — `ResolvedLine`
 *  carries `order_key` beside `order` for exactly this reason, because the resolver keys on
 *  the number alone and the store keys on `source:number`. Resolving a buyer here instead
 *  would make every such caller read the order ledger to build a URL.
 *
 *  THE VALUE MUST BE THE STORE KEY — `source:number`, `ResolvedLine.order_key`, never the
 *  bare number `ResolvedLine.order` holds. `groupForOrderKey` matches on the store key, so a
 *  bare number resolves to nothing, the effect marks the link handled and returns, and the
 *  press does NOTHING while looking like a link. A caller with only a number has not got
 *  what this parameter takes.
 *
 *  This screen does not write it: the selection is a BUYER, so what it mirrors back is
 *  `?buyer=`. Both are read, `?buyer=` first, and a link naming one order is resolved
 *  through `groupForOrderKey` to whichever group holds it (D193). */
const ORDER_PARAM = 'order'
/** THE OUTBOUND LINK — `#/orders?buyer=<group key>`, this screen's own selection, read and
 *  written together. */
const BUYER_PARAM = 'buyer'

function hashQuery(): URLSearchParams | null {
  const hash = window.location.hash
  const at = hash.indexOf('?')
  if (at === -1) return null
  return new URLSearchParams(hash.slice(at + 1))
}

function orderParam(): string | null {
  return hashQuery()?.get(ORDER_PARAM) ?? null
}

function buyerParam(): string | null {
  return hashQuery()?.get(BUYER_PARAM) ?? null
}

/** `#/orders?buyer=<key>`, written with `replaceState` so stepping through twenty buyers leaves
 *  one history entry and fires no `hashchange` — the shell's router keys on the path alone. */
function mirrorBuyerParam(key: string): void {
  const hash = window.location.hash
  const path = hash.replace(/^#/, '').split('?')[0] ?? ''
  if (path !== '/orders') return
  const next = `#/orders?${BUYER_PARAM}=${encodeURIComponent(key)}`
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
  /* THE SAME READ, KEPT WHOLE — every `InventoryCard` `getInventoryCopies` answered, keyed by
   *  `box/index`, alongside `store`'s own narrowed `PickRow` shape. `#/orders`' walk pane
   *  (§13, superseding this file's earlier plain `<img>`) needs the FULL card — its own
   *  identity, claims and provenance, the same three groups `#/inventory`'s Details section
   *  reads (`factGroupsOf`, moved to `CardHero.tsx` so both screens share it) — and `store`'s
   *  own `pickOfCard` narrows exactly those fields away. Covers every SKU any open order
   *  names (`skusOf`), which is always a superset of what a walk over open orders can stand
   *  on. */
  const [rawCards, setRawCards] = useState<ReadonlyMap<string, InventoryCard>>(new Map())
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

  /** Set to true by the receipt's Stop control, checked between batches of a looped
   *  all-statuses backfill. It never interrupts a call in flight — only the pacing wait and
   *  the next iteration. */
  const stopLoop = useRef(false)
  const [continuingInS, setContinuingInS] = useState<number | null>(null)

  const live = useRef(true)
  const pasteBox = useRef<HTMLTextAreaElement>(null)
  const phone = useMediaQuery('(max-width: 767px)')

  useEffect(() => {
    live.current = true
    return () => {
      live.current = false
    }
  }, [])

  /* `U` IS THE ONE KEY FOR THE NEWEST REVERSIBLE WRITE (`docs/specs/undo.md` §3) — here, the
   * newest pull this screen made that `hub.lastPull` still holds. Read live off `hubState()`
   * rather than a closed-over value, so a listener registered once on mount never goes stale;
   * `undoFromToast` is the same function the toast's own Undo button calls, so a key press and
   * a mouse click do exactly the same write. Scoped to the Pull stage — `U` on `#/shipping`
   * does nothing, because nothing is pulled there. Yields to typing, and to a write already in
   * flight. Where there is nothing to undo, or the receipt has expired, it does nothing and
   * says nothing. */
  useEffect(() => {
    if (stage !== 'pull') return
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.repeat) return
      if (event.metaKey || event.ctrlKey || event.altKey) return
      if (isEditableTarget(event.target)) return
      if (event.key.toLowerCase() !== 'u') return
      const pull = hubState().lastPull
      if (pull === null || pull.until <= Date.now()) return
      if (hubState().busy !== null) return
      event.preventDefault()
      void undoFromToast(pull.target, pull.place, pull.name)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [stage])

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

  /* NO LONGER THE WHOLE STORE (DEBT27, site 1, closed). This used to call
     `getInventory()` — the whole card map — for the reason `copiesOf`'s comment above still
     gives: a line stops drawing picks once it is filled, so the resolver's own picks are not
     the answer, and this screen needs EVERY on-hand copy of a card, including the ones sitting
     in boxes no pick names at all.

     `POST /inventory/copies` is the primitive that debt named and this branch builds: one
     unfiltered store-wide scan (no box guessed at, no box assumed) that DERIVES its own box
     set from what it actually finds, then decorates only those. `server/capture_server.py:
     do_inventory_copies` has the full argument for why that is sound where scoping the WALK
     to "the boxes an order's resolver picks name" is not — a copy in a box no pick names is
     the ordinary case this feature exists for, and that idea is exactly what was rejected.

     SEQUENCED AFTER `reread`, NOT RACED WITH IT, which is the one thing that changed about the
     shape of this call rather than what it fetches. The old whole-store fetch needed nothing
     from the ledger and so raced it; this one needs the SKUs `reread` just found, off
     `hubState().payload` rather than this render's own `payload` — reading the module's
     state directly rather than a closure lets every call site below, run from inside a
     `void (async () => ...)` body that has already `await`ed a fresh `reread()`, see that
     fresh answer regardless of whether React has re-rendered this component yet. */
  const rereadStore = useCallback(async () => {
    const skus = skusOf(hubState().payload)
    if (skus.length === 0) {
      /* Nothing open owes a copy, so there is nothing to widen — an empty map draws exactly
         what the resolver's own picks would have drawn alone, same as a failed fetch below
         except that this is not a failure. */
      if (live.current) {
        setStore(indexStore({ cards: {} }))
        setRawCards(new Map())
        setStoreFailed(false)
      }
      return
    }
    try {
      const inventory = await getInventoryCopies(skus)
      if (!live.current) return
      setStore(indexStore(inventory))
      setRawCards(new Map(Object.values(inventory.cards).map((card) => [`${card.box}/${card.index}`, card])))
      setStoreFailed(false)
    } catch {
      if (!live.current) return
      /* DROPPED RATHER THAN KEPT. A stale card map after a pull would draw a copy that has left
         the box as one you can still reach for, and a map that is quietly wrong is worse than a
         map that is quietly narrow. */
      setStore(null)
      setRawCards(new Map())
      setStoreFailed(true)
    }
  }, [])

  useEffect(() => {
    void (async () => {
      /* SEQUENCED: `rereadStore` reads its SKUs off the ledger `reread` just fetched, so it
         must run after — see `rereadStore`'s own comment. On the very first mount there is no
         payload yet at all, and racing them (the old shape) would have sent this call with an
         empty SKU set every time. */
      await reread()
      await rereadStore()
    })()
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
        /* A pasted order can name a SKU this SKU set has never asked the store about — see
           `rereadStore`'s own comment for why this must run AFTER `reread`, not beside it. */
        await rereadStore()
      } catch (err) {
        if (!live.current) return
        setFailure(describeFailure(err))
      } finally {
        if (live.current) setBusy(null)
      }
    })()
  }

  /** A wait between batches that a Stop press can cut short — polled at 250ms rather than a
   *  single `setTimeout`, so the loop notices `stopLoop` mid-pause instead of firing one more
   *  call it was already told to abandon. */
  const paceWait = async (seconds: number) => {
    const until = Date.now() + seconds * 1000
    while (Date.now() < until && !stopLoop.current && live.current) {
      const left = Math.max(0, Math.ceil((until - Date.now()) / 1000))
      setContinuingInS(left)
      await new Promise((resolve) => setTimeout(resolve, 250))
    }
    setContinuingInS(null)
  }

  /* THE FETCH ENTERS THROUGH THE SAME ONE DOOR THE PASTE DOES: `POST /orders/fetch` answers
     exactly the body the ingest accepts. Free, and it writes nothing by itself.

     TWO SHAPES, ONE PRESS EACH (`D193`). A DEVICE THAT HAS NEVER
     NARROWED THE PICKER (`filter.statuses === null`) SKIPS THE PREVIEW ENTIRELY and asks for
     `all_statuses` with `skip_known` — the ordinary press, after the owner's ruling that a
     one-time full backfill (`LastTwoYears`, every status, skip-known) is followed forever after
     by an all-statuses append. It LOOPS while the wire reports `remaining > 0`, naming buyers
     the ledger did not already have along the way (`nameOrders`), and paces itself between
     batches so this account's own rate limit is not what answers next. A device that HAS
     narrowed the picker keeps the original preview → intersect → fetch shape, one call, exactly
     as it always has. */
  const runFetch = (range?: string, using: OrderFetchFilter = filter) => {
    stopLoop.current = false
    void (async () => {
      setBusy('fetch')
      setFailure(null)
      setPasteNote(null)
      setDropped([])
      setReceipt(null)
      setContinuingInS(null)
      /* Read the previous check BEFORE this one is written, and hold it: it is what "new since"
         is measured against. */
      const previous = readLastCheck()
      try {
        if (using.statuses === null) {
          /* ---- the all-statuses, skip-known backfill: no preview, and it loops ---- */
          let batches = 0
          let detailedTotal = 0
          let skippedKnownTotal = 0
          let ingestTotal = 0
          let namedTotal = 0
          let remaining: number | null = null
          let at = Date.now()
          for (;;) {
            const found = await fetchOrders({
              all_statuses: true,
              skip_known: true,
              ...(range === undefined ? {} : { range }),
            })
            if (!live.current) return
            batches += 1
            at = Date.now()
            const counted = found as OrdersFetched & FetchCounts
            const detailed = wireCount(counted.detailed) ?? found.orders.length
            detailedTotal += detailed
            skippedKnownTotal += wireCount(counted.skipped_known) ?? 0
            const written = found.orders.length === 0 ? null : await ingestOrders(found.orders)
            if (!live.current) return
            if (written !== null) ingestTotal += written.added + written.changed
            if (found.names.length > 0) {
              const named = await nameOrders(found.names)
              if (!live.current) return
              namedTotal += (named as NamesResult).named
            }
            remaining = wireCount(counted.remaining)
            /* A LIVE RECEIPT, DRAWN AFTER EVERY BATCH — not only at the end. The loop can run for
               several minutes on a real backfill and a receipt that appeared only on completion
               would look, for that whole time, exactly like a press that had done nothing. */
            setReceipt({
              at,
              previous,
              windowTotal: null,
              matched: null,
              asked: null,
              absent: [],
              newSince: null,
              detailed: detailedTotal,
              skippedKnown: skippedKnownTotal > 0 ? skippedKnownTotal : null,
              remaining,
              fetched: detailedTotal,
              ingest:
                ingestTotal > 0
                  ? { added: ingestTotal, changed: 0, unchanged: 0, total: ingestTotal, wrote_nothing: false, summary: '', keys: [] }
                  : null,
              batches,
              named: namedTotal,
              continuingInS: null,
            })
            if (remaining === null || remaining <= 0 || stopLoop.current) break
            /* PACED, NOT FREE-WHEELING. The 120/min budget `MAX_ORDERS` argues for is a search-page
               plus per-order detail cost; the pause is sized off what THIS batch actually cost, so
               a small batch does not wait as long as a big one and neither ever waits past a
               minute. */
            const pace = Math.min(60, Math.ceil((Math.ceil((wireCount(counted.matched) ?? 0) / 25) + detailed) / 2))
            await paceWait(Math.max(0, pace))
            if (stopLoop.current || !live.current) break
          }
          writeLastCheck({ at, matched: null, statuses: null })
          await reread()
          /* A fetched batch can bring an order naming a SKU never asked about before — see
             `rereadStore`'s own comment. */
          await rereadStore()
          return
        }

        /* ---- the narrowed path: preview, intersect, one fetch — unchanged from before ---- */
        /* ONE PRESS, TWO CALLS, AND THE SECOND ONE IS NOT A QUESTION. D91 made the wire refuse
           a fetch that names no statuses — `statuses_required` — on the argument that this
           account's window holds hundreds of orders and one press taking all of them is what
           never worked. The owner ruled the two-press flow out: *"why would it ever say 1 of 3
           found"*, and the press asks and takes in the same gesture.

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
        /* THE OPERATOR'S TICK LIST, INTERSECTED WITH WHAT THIS WINDOW ACTUALLY HOLDS. Asking
           for a status no order carries is not an error on the wire — it matches nothing and
           costs a walk — but it is a fact worth reporting, so what falls out is kept and drawn
           rather than dropped. */
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
              ? 'Nothing to fetch — every status is unticked. Open Statuses and tick one.'
              : `This window holds no ${absent.join(', ')} orders — the only statuses ticked here. Nothing was fetched.`,
          )
          setBusy(null)
          return
        }
        const runOne = async (): Promise<void> => {
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
            batches: null,
            named: null,
            continuingInS: null,
          })
          writeLastCheck({ at, matched, statuses: wanted })
        }
        await runOne()
        if (!live.current) return
        /* RE-READ EITHER WAY. A fetch that brought nothing new still refreshes a ledger another
           device may have moved. */
        await reread()
        await rereadStore()
      } catch (err) {
        if (!live.current) return
        setFailure(describeFailure(err))
      } finally {
        if (live.current) {
          setBusy(null)
          setContinuingInS(null)
        }
      }
    })()
  }

  /** The Stop control on the receipt — cuts the all-statuses loop between batches, never a call
   *  already in flight. */
  const onStopFetch = () => {
    stopLoop.current = true
  }

  /** The narrowed picker's own confirm and "fetch the next batch" both still call this with no
   *  range — the backfill's `range` argument is for the two-years control alone. */
  const onFetch = (range?: string) => runFetch(range)

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

  /** The picker's own press: record that this device has narrowed the list, and fetch on it. The
   *  answered filter is passed to `runFetch` rather than left to the next render, because the
   *  state has not committed yet and the press must act on what was just agreed. */
  const onConfirmStatuses = () => {
    const answered = { ...filter, asked: true }
    setFilter(answered)
    rememberOrderFilter(answered)
    runFetch(undefined, answered)
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
          title: `Marked sold: ${name}`,
          body: `from ${place} · order ${order.number}`,
          ttlMs: UNDO_WINDOW_MS,
          action: { label: 'Undo', onPress: () => void undoFromToast(target, place, name) },
        })
        /* THE NEWEST PULL THIS SCREEN MADE THAT IS STILL UNDOABLE — `docs/specs/undo.md` §3's
           fast path, reached by `U`. Overwrites whatever `lastPull` held before, because a
           second pull inside the first one's window makes the first one the slow path's job. */
        setHub({ lastPull: { target, place, name, until: Date.now() + UNDO_WINDOW_MS } })
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

  /* THE WALK'S OWN PULL — same write (`pullCopy`), same toast, same `lastPull` fast-undo path,
     over the walk plan's OWN shape rather than a `ResolvedLine`/`PickRow` built to satisfy a
     type the plan does not fill honestly (`OrdersWalk.tsx`'s own header has the argument).
     Returns the outcome rather than throwing, because a walk row needs to know a `gone` copy
     from a real failure to draw `gone, skip` without ending the whole pass over it. */
  const onWalkPull: WalkPullFn = async ({ order, sku, name, target, place, refresh }) => {
    const busyKey = `walk/${sku}/${target.capture_id}`
    setBusy(busyKey)
    setFailure(null)
    try {
      /* `refresh` NAMES CARDS THIS PRESS DOES NOT TOUCH — the walk's other rows in the same
         drawer, whose numbers and neighbours this write moves (D58). It reaches the same
         route in the same request, and `refreshed` comes back POST-write. `places` below is
         still the PRE-write receipt and the two are never confused. */
      const done = await pullCopy({ source: order.source, number: order.number, sku }, [target], refresh)
      if (!live.current) return { ok: false, failure: { code: 'unmounted', message: '' } }
      const resolvedPlace = done.places[0]?.label ?? place ?? `box ${target.box}, index ${target.index}`
      /* D196: NO RAW ORDER KEY ON SCREEN. `order.number` is a machine string
         (`A2FFC195-0000F4-006AC`) — `TakeBlock`'s own `for <buyer>` line, five lines away,
         already refuses to say a nameless order's own key, and the receipt owes the same
         refusal. The buyer's name, when the order carries one; nothing beyond the place when
         it does not. */
      const buyer = order.buyer?.trim()
      toast({
        kind: 'receipt',
        icon: 'hand',
        title: `Marked sold: ${name}`,
        body: buyer ? `from ${resolvedPlace} · for ${buyer}` : `from ${resolvedPlace}`,
        ttlMs: UNDO_WINDOW_MS,
        action: { label: 'Undo', onPress: () => void undoFromToast(target, resolvedPlace, name) },
      })
      setHub({ lastPull: { target, place: resolvedPlace, name, until: Date.now() + UNDO_WINDOW_MS } })
      await Promise.all([reread(), rereadStore()])
      return { ok: true, place: resolvedPlace, refreshed: done.refreshed ?? [] }
    } catch (err) {
      const trouble = describeFailure(err)
      if (live.current) setFailure(trouble)
      return { ok: false, failure: trouble }
    } finally {
      if (live.current) setBusy(null)
    }
  }

  /** The walk row's own inline Undo (§8's 20s window) — a direct call rather than
   *  `undoFromToast`, because a row needs to know whether it succeeded to put its own copy
   *  back into the pressable state; `undoFromToast` only ever reports through a toast. */
  const onWalkUndo: WalkUndoFn = async (target, place, name, refresh) => {
    setHub({ busy: `undo/${target.capture_id}` })
    try {
      /* The copy goes back in the drawer, so the rows still ahead of it take their old
         numbers back too — the same `refresh` list the pull sent, answered the other way. */
      const done = await undoPull([target], refresh)
      toast({ kind: 'ok', icon: 'undo', title: `Put ${name} back`, body: `${place} holds it again.` })
      await Promise.all([reread(), rereadStore()])
      return { ok: true, refreshed: done.refreshed ?? [] }
    } catch (err) {
      const trouble = describeFailure(err)
      toast({ kind: 'refusal', title: 'The card was not put back', body: `${trouble.message} · ${trouble.code}` })
      return { ok: false }
    } finally {
      setHub((current) => ({ busy: null, lastPull: current.lastPull?.target.capture_id === target.capture_id ? null : current.lastPull }))
      touchHub()
    }
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

  /* -------------------------------------------------------- the one-time backlog reconcile */

  /* D203. A SECOND backlog `is_terminal_status` cannot see: orders
     TCGplayer settled to `Completed - Paid` two years before this screen existed, carrying
     zero recorded copies. `ReconcileBacklogPanel` computes WHICH ones from what this screen
     already read; the press sends only the cutoff, and the store recomputes the candidate set
     itself at that moment, closes every line of every match with `shipped_elsewhere`, and
     claims no copy. */
  const onReconcileBacklog = (cutoff: string) => {
    void (async () => {
      setBusy('reconcile')
      setFailure(null)
      try {
        const done = await reconcileBacklog(cutoff)
        if (!live.current) return
        toast({
          kind: 'receipt',
          icon: 'check',
          title: `Stood down ${done.moved} ${plural(done.moved, 'order', 'orders')}`,
          body: `${done.still_open} still open · nothing was marked sold`,
          ttlMs: UNDO_WINDOW_MS,
          action: {
            label: 'Undo',
            onPress: () => {
              void (async () => {
                try {
                  await reopenOrders(done.closed)
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
        {/* THE ONE-TIME FULL BACKFILL, AS ITS OWN CONTROL — `D193`. The
            ordinary press already asks for every status; this widens the RANGE to TCGplayer's
            own `LastTwoYears`, which is more than this store has ever existed for. A repeat costs
            nothing: skip-known means a second press after the first has finished re-checks
            everything and details nothing new. */}
        {withFetch ? (
          <Button icon="clock" onClick={() => onFetch('LastTwoYears')} busy={busy === 'fetch'} disabled={busy !== null}>
            Fetch two years
          </Button>
        ) : null}
        {/* THE NARROWING SITS BESIDE THE PRESS, NOT IN FRONT OF IT. D91's two-press flow was
            ruled out — *"why would it ever say 1 of 3 found"* — so this is a control the
            operator may never open, and the press works identically if they do not. */}
        {withFetch ? statusControl : null}
      </div>
      {withFetch ? (
        <p className="orders-paste-source">A repeat skips known orders.</p>
      ) : null}
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
            Not sent: <span className="bn-mono">{dropped.join(', ')}</span>. Only the SKU, count and card name left this browser.
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
      : "TCGplayer's shipping export, sorted into three lanes."

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
        icon={stage === 'pull' ? 'cart' : 'truck'}
        title={stage === 'pull' ? 'Orders' : 'Shipping'}
        lede={lede}
        actions={
          stage === 'pull' && populated ? (
            <>
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
          rawCards={rawCards}
          storeFailed={storeFailed}
          onRereadStore={() => void rereadStore()}
          failure={failure}
          busy={busy}
          filter={hub.filter}
          selected={hub.selected}
          phone={phone}
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
              <FetchReceipt
                receipt={{ ...receipt, continuingInS }}
                busy={busy === 'fetch'}
                onFetchMore={() => onFetch()}
                onStop={continuingInS === null ? undefined : onStopFetch}
              />
            )
          }
          onPull={onPull}
          onWalkPull={onWalkPull}
          onWalkUndo={onWalkUndo}
          onFill={onFill}
          onDeclareKind={onDeclareKind}
          onStandDown={onStandDown}
          onReconcileBacklog={onReconcileBacklog}
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
        copies went — still open here, holding copies back.
      </p>
      <p>
        Standing down marks <strong>nothing</strong> sold and claims no copy left. Any card shipped
        is still in its box — reconcile on <code>#/inventory</code>.
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

/** The one-time backlog reconcile (D203): every open order carrying
 *  NOTHING RECORDED, placed before a cutoff, closed with `shipped_elsewhere`. UNLIKE
 *  `BacklogPrompt` above, the predicate here is never a status word — age and "nothing
 *  recorded" alone — so the breakdown is what tells a live order sharing that shape apart from
 *  real backlog, drawn before the count ever moves.
 *
 *  IT ASKS THE WIRE FOR NOTHING BEYOND WHAT THIS SCREEN ALREADY READ. `GET /orders`'s own
 *  answer carries `open`, `recorded` and `placed_at` for every order in the store — exactly
 *  what `POST /orders/reconcile-backlog {preview: true}` would compute server-side — so a
 *  second network call to preview it would duplicate a primitive this screen already holds
 *  (`no-bandaids`'s own question, asked and answered). Only the PRESS reaches the wire, and
 *  the server recomputes the candidate set from its own store at that moment regardless of
 *  what this panel displayed, exactly as `BacklogPrompt`'s stand-down already works. */
function ReconcileBacklogPanel({
  orders,
  busy,
  onPress,
}: {
  readonly orders: readonly OrderRow[]
  readonly busy: string | null
  readonly onPress: (cutoff: string) => void
}) {
  /* TODAY, PLAIN. The server's own default (`store/orders.py:today()`) is the same UTC date;
     the one edge this can disagree with it on is an order placed in the last few hours of UTC
     yesterday read from a browser already into local today, which moves a single order's
     candidacy by at most one day and is corrected the moment the operator presses — the write
     always recomputes server-side. */
  const cutoff = useMemo(() => new Date().toISOString().slice(0, 10), [])
  const candidates = useMemo(
    () =>
      orders.filter(
        (row) =>
          row.open && row.recorded === 0 && row.placed_at !== null && row.placed_at.slice(0, 10) < cutoff,
      ),
    [orders, cutoff],
  )
  const breakdown = useMemo(() => {
    const counts = new Map<string, number>()
    for (const row of candidates) {
      const status = row.status ?? 'no status'
      counts.set(status, (counts.get(status) ?? 0) + 1)
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  }, [candidates])

  if (candidates.length === 0) return null
  const busyHere = busy === 'reconcile'

  return (
    <Notice
      className="orders-reconcile"
      tone="warn"
      title={`${candidates.length} ${plural(candidates.length, 'order', 'orders')}, nothing recorded`}
    >
      <p>{joinPhrases(breakdown.map(([status, count]) => `${count} “${status}”`))}. Nothing sold, nothing claimed.</p>
      <div className="orders-standdown-row">
        <Button
          variant="primary"
          icon="check"
          busy={busyHere}
          disabled={busy !== null}
          onClick={() => onPress(cutoff)}
        >
          Stand down {candidates.length} {plural(candidates.length, 'order', 'orders')}
        </Button>
      </div>
    </Notice>
  )
}

function PullStage({
  payload,
  store,
  rawCards,
  storeFailed,
  onRereadStore,
  failure,
  busy,
  filter,
  selected,
  phone,
  well,
  emptyWell,
  receipt,
  onPull,
  onWalkPull,
  onWalkUndo,
  onFill,
  onDeclareKind,
  onStandDown,
  onReconcileBacklog,
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
  /** The same read, whole — `InventoryCard` by `box/index`, for the walk pane's own
   *  `CardHeroHead`/`CardDetailsSection` (§13: inventory's card pane, unchanged). */
  readonly rawCards: ReadonlyMap<string, InventoryCard>
  readonly storeFailed: boolean
  readonly onRereadStore: () => void
  readonly failure: Failure | null
  readonly busy: string | null
  readonly filter: PullFilter
  readonly selected: string | null
  readonly phone: boolean
  readonly well: ReactNode
  readonly emptyWell: ReactNode
  /** The last fetch's receipt, or null before one has been pressed. */
  readonly receipt: ReactNode
  readonly onPull: PullHandler
  /** `Walk the boxes`' own pull and undo — `OrdersWalk.tsx`'s own shape, over the same
   *  underlying write `onPull` makes for `By buyer`. */
  readonly onWalkPull: WalkPullFn
  readonly onWalkUndo: WalkUndoFn
  readonly onFill: FillHandler
  readonly onDeclareKind: KindHandler
  readonly onStandDown: StandDownHandler
  readonly onReconcileBacklog: (cutoff: string) => void
  readonly onCloseLine: CloseLineHandler
  readonly onFetch: () => void
  readonly statusControl: ReactNode
  readonly statusPanel: ReactNode
  readonly onReread: () => void
}) {
  const hub = useHub()
  const counts = payload?.resolution.counts ?? null

  /* ------------------------------------------------------------- the buyer list's own view */

  /** Status / sort / hide-unknown, read from `banchi.orders.fetch-filter`'s own document
   *  (`app/src/deviceMemory.ts`) — not a new key. Read once on mount, the same habit as the
   *  fetch filter above it. */
  const [view, setViewState] = useState<OrderView>(() => storedOrderFilter().view ?? DEFAULT_ORDER_VIEW)
  const setView = (next: OrderView) => {
    setViewState(next)
    rememberOrderFilter({ ...storedOrderFilter(), view: next })
  }

  /* THE ORDER TAKEN, AND HELD UNTIL SOMEBODY ASKS FOR A NEW ONE (D181, on `frozenRank.ts`'s
   *  own ruling — a press may reorder, nothing else may). Empty is "current": nothing is
   *  frozen and the list draws whatever a fresh sort produces, which is both the opening
   *  state and what an explicit re-sort restores. */
  const [take, setTake] = useState<OrderTake>(TAKE_IS_CURRENT)

  /* THE BUYER SEARCH — transient component state, deliberately NOT `banchi.orders.fetch-filter`
   *  and NOT any `localStorage` key. A remembered query would hide orders on the next visit
   *  with no chip on screen saying why, which is exactly the hiding D103's anti-hiding floor
   *  refuses for staleness; this control gets the same rule. Cleared on unmount for free by
   *  being ordinary state. */
  const [query, setQuery] = useState('')
  const onQueryChange = (next: string) => {
    setQuery(next)
    /* A changed search is an explicit retake, the same rule `onStatusChange` and
       `onHideUnknownChange` already apply (D181 — narrowing the shown set is a request to see
       the shelf as it stands now, not a reason to hold last take's positions over rows the
       new query may not even include). */
    setTake(TAKE_IS_CURRENT)
  }

  /* THE SECOND TIER'S CACHE: real picks and places, fetched on demand for exactly the orders
   *  this screen is looking at (`POST /orders/picks`, `server/capture_server.py:do_orders`'s
   *  own comment). `GET /orders` answers `picks: []` on every line now — decorating one was
   *  52% of that route's wall time for a buyer nobody had opened — so this map is where the
   *  real thing lands once asked for, keyed by order key, and it is dropped whole every time
   *  `payload` changes: a pull, a fill or a close refetches `payload`, and a picks cache keyed
   *  to the last snapshot would go on showing a copy as free (or spoken for) after the write
   *  that changed it. */
  const [detail, setDetail] = useState<Map<string, ResolvedOrder>>(new Map())
  /* THE IN-FLIGHT SET, AND WHY `detail` ALONE CANNOT DO THIS JOB. React state does not settle
   *  inside one render pass: opening a buyer whose group is still assembling (the buyer effect
   *  below, `selectedGroup` moving from null to a group across the first few renders after
   *  mount) re-runs the effect several times before the first `fetchOrderPicks` promise has
   *  resolved, and every one of those renders sees the SAME empty `detail` — so the dedupe
   *  check `!detail.has(key)` passes every time and queues another identical request. Measured
   *  against the seeded server on :8265 (2026-09-17): a fresh `#/orders` load with a
   *  four-order buyer selected by default fired SEVEN identical `POST /orders/picks` calls,
   *  all carrying the same four keys, before any of them had landed.
   *
   *  `pendingPicks` marks a key SYNCHRONOUSLY, in the same tick the fetch is initiated —
   *  before the `await` — which is the one thing a ref can do that state cannot. It is
   *  checked ALONGSIDE `detail`, never instead of it: `detail` is what stops an ALREADY
   *  ANSWERED key from being asked again; the ref is what stops a key from being asked twice
   *  while its first answer is still on the wire.
   *
   *  CLEARED ON SETTLE, INCLUDING ON FAILURE — `.finally()`, not the `.then()` branch alone.
   *  A rejected fetch that left its key in the set would make that order unfetchable for the
   *  rest of the mount: a permanently empty panel, which is a worse defect than the duplicate
   *  calls this fixes.
   *
   *  AND CLEARED ON THE SAME TRANSITION THAT DROPS `detail` — a pull, a fill or a close
   *  refetches `payload`, and a stale in-flight entry surviving that transition would suppress
   *  the very refetch the `detail` reset exists to force, leaving the panel showing nothing
   *  after a write that changed what it should show. */
  const pendingPicks = useRef<Set<string>>(new Set())
  /* GUARDS AGAINST STRICTMODE'S OWN DOUBLE-FETCH, WHICH IS A SECOND REAL BUG THIS RESET
   *  EFFECT CAN CAUSE, AND A REFERENCE CHECK DOES NOT FIX. `main.tsx` mounts under
   *  `<StrictMode>`, and the mount effect above that calls `reread()` (`getOrders()`) has no
   *  guard of its own against StrictMode's double-invoke — so on mount it makes TWO separate
   *  `GET /orders` calls and lands TWO genuinely distinct `payload` objects, back to back,
   *  before this screen has done anything. Comparing `payload` BY REFERENCE (an earlier
   *  version of this effect did) treats that second, content-identical answer as a real
   *  change: it wipes `pendingPicks` out from under the buyer-fetch effect's first in-flight
   *  request, whose own dedupe then sees an empty set again and fires a second, fully
   *  redundant `POST /orders/picks` for the same keys. Measured: the spec case below caught
   *  this as TWO identical calls where the ref alone should have left one.
   *
   *  So this compares CONTENT, not identity: `JSON.stringify(payload)`. Two consecutive
   *  reads of an unchanged store serialize identically and are treated as no change at all
   *  — cheap correctness here, since this only runs when `payload`'s reference changes at
   *  all, never on every render. A REAL change — a pull, a fill, a close, or a poll that
   *  actually found something different — serializes differently and resets exactly as
   *  before. This is also why a coarser signature (say, just the resolved orders' KEYS) was
   *  rejected: a pull that records a copy without removing the order from `resolution`
   *  (still short, now for one fewer copy) would leave that narrower signature unchanged and
   *  suppress the very refetch the reset exists to force — the stale-picks-after-pull defect
   *  by another door. */
  const payloadSignature = useRef<string | null>(null)
  useEffect(() => {
    const signature = payload === null ? null : JSON.stringify(payload)
    if (payloadSignature.current === signature) return
    payloadSignature.current = signature
    setDetail(new Map())
    pendingPicks.current = new Set()
  }, [payload])

  /** Fetch real picks for exactly the keys not already answered and not already in flight,
   *  in one batched `POST /orders/picks` — the one door both fetch effects below use, so the
   *  dedupe rule lives in one place rather than twice. */
  const fetchMissingPicks = useCallback((keys: readonly string[]) => {
    const missing = keys.filter((key) => !detail.has(key) && !pendingPicks.current.has(key))
    if (missing.length === 0) return
    for (const key of missing) pendingPicks.current.add(key)
    fetchOrderPicks(missing)
      .then((found: OrderPicksPayload) => {
        setDetail((prev) => {
          const next = new Map(prev)
          for (const one of found.orders) next.set(one.key, one)
          return next
        })
      })
      .catch(() => {
        /* Best-effort: the lite tier already in `answers` is a safe fallback (an empty pick
         *  list, never a wrong one), so a failed fetch here leaves the detail view showing
         *  no copies rather than crashing it. Clearing the ref below (not skipped on this
         *  branch) is what lets the next render of this buyer or walk retry. */
      })
      .finally(() => {
        for (const key of missing) pendingPicks.current.delete(key)
      })
  }, [detail])

  /** The resolution, keyed so a row can find its own — the lite line from `payload` overlaid
   *  with the real one from `detail` wherever this screen has actually fetched it. Every
   *  consumer of `answers` gets real `picks` for an order once fetched and an honest empty
   *  list (never a guess) until then; the buyer list itself never notices the difference,
   *  because `statusOf`/`worstStatus`/`passesHideUnknown` read `line.reason` alone. */
  const answers = useMemo(() => {
    const out = new Map<string, ResolvedOrder>()
    for (const one of payload?.resolution.orders ?? []) out.set(one.key, detail.get(one.key) ?? one)
    return out
  }, [payload, detail])

  /** Which open order was offered which copy — over what THIS screen has fetched real picks
   *  for, never the whole resolution (which no longer carries any). A copy in an order this
   *  screen has not opened is not claimed here; it is not offered anything either, since
   *  nothing renders a copy map for it. */
  const claims = useMemo(() => indexClaims(answers), [answers])

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

  /* GROUPED BY BUYER, NOT BY ORDER NUMBER (`D193`). `groupBuyers` is
     pure and takes its own clock, so it is pinned to the render that saw this `payload` rather
     than re-run on every tick. */
  const groups = useMemo(() => groupBuyers(payload?.orders ?? [], Date.now()), [payload])
  const allGroups = useMemo(() => [...groups.recent, ...groups.earlier], [groups])

  /* THE FILTER SELECT NARROWS GROUPS, NOT ORDERS. 'all' is every group carrying an open order;
     a reason option narrows to groups whose open orders carry a line with that reason; 'done'
     is every group with nothing open — which is exactly `groups.recent`'s closed members plus the whole
     of `groups.earlier`, since a group with anything open can never be `earlier` (see
     `orderBuyers.ts`).

     THE STATUS SELECT AND "HIDE UNKNOWN SKUS" COMPOSE WITH IT (`orderView.ts`) — an AND over
     everything above, never a second gate. Both default to "show everything"
     (`status: null`, `hideUnknown: false`), so a device that has never touched either control
     drops nothing here: the anti-hiding floor D103 already set for staleness. */
  const filteredGroups = useMemo(
    () =>
      (filter === 'all'
        ? groups.recent.filter((group) => group.open.length > 0)
        : filter === 'done'
          ? groups.recent.filter((group) => group.open.length === 0)
          : groups.recent.filter(
              (group) =>
                group.open.length > 0 &&
                group.open.some((order) => (answers.get(order.key)?.lines ?? []).some((line) => line.reason === filter)),
            )
      ).filter(
        (group) =>
          passesStatus(group, view.status) && passesHideUnknown(group, view.hideUnknown, answers) && passesQuery(group, query),
      ),
    [filter, groups, answers, view.status, view.hideUnknown, query],
  )
  /* THE EARLIER FOLD IS DONE-ONLY. A closed buyer older than `RECENT_DAYS` has nothing an 'all'
     or reason filter would ever show, so it is drawn nowhere but under the "Done" option.
     THE SEARCH REACHES IT TOO — a Done buyer past the 7-day fold is exactly the one a name
     search has to find, since it is unreachable any other way (the owner's own case: cmd-F-ing
     the page for someone whose only order closed weeks ago). */
  const earlierGroups = useMemo(
    () =>
      filter === 'done'
        ? groups.earlier.filter(
            (group) =>
              passesStatus(group, view.status) && passesHideUnknown(group, view.hideUnknown, answers) && passesQuery(group, query),
          )
        : [],
    [filter, groups, answers, view.status, view.hideUnknown, query],
  )

  /* THE DEFAULT ORDER: Ready to Ship leads, newest first within a group, read as an ORDERING
     rather than a hiding — the owner's ruling, verbatim in intent. `liveSorted` is what a
     fresh take would produce RIGHT NOW; `shownGroups` is what is actually drawn, which keeps
     every known group at the position `take` gave it and appends anything new after them
     (D181). */
  const liveSorted = useMemo(() => sortGroups(filteredGroups, view.sort), [filteredGroups, view.sort])
  const shownGroups = useMemo(() => applyTake(liveSorted, take), [liveSorted, take])
  const staleGroups = staleCount(liveSorted, take)
  const staleSentence = orderStalenessSentence(staleGroups)

  /* ------------------------------------------------------------------- the walk's selection */

  /* WHICH BUYERS ARE TICKED FOR THE NEXT PASS — §12, and a WHITELIST where §8 had a blacklist.
   *  Keyed by `BuyerGroup.key`, the same key the rows are drawn under, so the prune below and
   *  the draw can never disagree about what a tick is about. One tick is one BUYER covering
   *  that buyer's walkable orders, which is D193's own shape: a hand walks
   *  drawers per person.
   *
   *  EMPTY AT FIRST RENDER, AND AN ORDER ARRIVING MID-SELECTION IS NOT TICKED (§12 answer 3,
   *  the owner's amendment of 2026-09-18). The blacklist this replaces existed precisely so a
   *  new order would arrive ticked; that argument is retired. Nothing is preselected, the same
   *  reading D93 and D97 already give the copies panel.
   *
   *  Local state rather than the hub: it must not outlive the tab the way `hub.walkKeys` (the
   *  frozen PASS) must not either. */
  const [walkTicked, setWalkTicked] = useState<ReadonlySet<string>>(new Set())

  /** THE ORDER PANEL'S OWN `Manage` SHEET (§13) — the one place left for the fetch/paste well,
   *  the fetch receipt, the status picker and both stand-down prompts once the mode strip that
   *  used to hold them at the top of the screen is gone. `BoxOps.tsx`'s own Manage sheet is the
   *  precedent: box-level operations reached from the box panel because the skeleton has no
   *  other slot for them; this is the same move for the ledger. */
  const [manageOpen, setManageOpen] = useState(false)

  /** THE PHONE RAIL SHEET (defect fix, this pass) — `BoxBrowse.tsx`'s own `railOpen`, over the
   *  buyer picker rather than the box list. Below 768px `.browse-body > .browse-map` is hidden
   *  by `BoxBrowse.css` (already imported here), so the search slot, the select bar and the
   *  buyer list — otherwise part of that column — would have no way onto the screen at all.
   *  This chip and bottom sheet are that way back in, exactly `BoxBrowse.css`'s
   *  `.browse-railsheet` styling, not a second stylesheet for the same shape. */
  const [railOpen, setRailOpen] = useState(false)

  /** Hide sold (D132) — `#/inventory`'s own persisted `banchi.inventory.hide-sold`, on the
   *  owner's word: same preference, same screen family, one key. No new key. */
  const [hideSold, setHideSoldState] = useState<boolean>(() => storedHideSold())
  const setHideSold = (next: boolean) => {
    setHideSoldState(next)
    rememberHideSold(next)
  }
  const toggleWalkTick = (key: string) =>
    setWalkTicked((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })


  /** A BUYER'S OWN WALKABLE ORDERS, and what the walk is over — never `open` alone (the
   *  owner's own words opening this task: "I need the ability to walk orders even if it
   *  already shows shipped"). `ownsAWalkableBody` is the one discriminator, shared with
   *  `OrderDetail`'s body gate, so a card that has a Pull button in the "By order" fold is
   *  never absent from the one pass built to walk a shelf in a single trip. Measured on the
   *  owner's store: 40 open against 235 terminal-and-still-owing — the walk covered 40 of 275
   *  orders that owe copies before this.
   *
   *  Per GROUP rather than one flat list, because the tick is per buyer (D193). A buyer with
   *  none of these draws no tick at all: there is nothing to select, and a disabled tick would
   *  be a control offering a press that can never mean anything. */
  const walkableOf = useMemo(() => {
    const out = new Map<string, readonly OrderRow[]>()
    for (const group of allGroups) out.set(group.key, group.orders.filter(ownsAWalkableBody))
    return out
  }, [allGroups])

  /** THE ROWS IN VIEW THAT CAN HOLD A TICK — both lists the current filter yields, because the
   *  `Earlier` fold is a disclosure and not a filter (it is drawn, and only ever under the
   *  Done option). This is the set `Tick all` and `Untick all` act on (§12 answer 1) and the
   *  set the prune below keeps the stored ticks inside. */
  const tickableKeys = useMemo(() => {
    const out = new Set<string>()
    for (const group of [...shownGroups, ...earlierGroups]) {
      if ((walkableOf.get(group.key)?.length ?? 0) > 0) out.add(group.key)
    }
    return out
  }, [shownGroups, earlierGroups, walkableOf])

  /* A TICK DOES NOT SURVIVE A FILTER THAT HIDES ITS ROW, AND FILTERING BACK DOES NOT BRING IT
   * BACK (§12 answer 1, the owner's ruling 2026-09-18). "The tick is a property of the list as
   * drawn, not a set held behind it."
   *
   * THIS IS A REAL PRUNE OF THE STORED SET AND NOT A RENDER-TIME INTERSECTION, and the
   * difference is the whole ruling: `ticked ∩ visible` computed at draw time would keep the
   * member in state and hand the tick straight back the moment the filter was cleared, which
   * is exactly what answer 1 says must not happen. The set only ever LOSES members here.
   *
   * It is an effect rather than a line in each of the six handlers that can change what is
   * drawn (four filter controls, the search, and a fresh `payload` retiring a buyer) — one
   * reader of one derived set cannot be the handler somebody forgets to amend. */
  useEffect(() => {
    setWalkTicked((prev) => {
      if (prev.size === 0) return prev
      const next = new Set<string>()
      for (const key of prev) if (tickableKeys.has(key)) next.add(key)
      return next.size === prev.size ? prev : next
    })
  }, [tickableKeys])

  const statusOptions = useMemo(() => statusVocabulary(payload?.orders ?? []), [payload])

  /** A control narrowed the shown set: retake immediately (D181 — "a changed filter is an
   *  explicit retake"). */
  const onStatusChange = (status: string | null) => {
    setView({ ...view, status })
    setTake(TAKE_IS_CURRENT)
  }
  const onHideUnknownChange = (hideUnknown: boolean) => {
    setView({ ...view, hideUnknown })
    setTake(TAKE_IS_CURRENT)
  }
  /** A change of SORT never reorders on its own (D181): whatever is on screen right now is
   *  frozen exactly where it sits, and the new direction is offered as a re-sort. */
  const onSortChange = (sort: OrderSort) => {
    setTake(takeOrder(shownGroups))
    setView({ ...view, sort })
  }
  const onReSort = () => setTake(TAKE_IS_CURRENT)

  /* The selection falls back to the first group shown, so a filter that hides the selected one
     never leaves the detail blank. */
  const selectedKey =
    selected !== null && allGroups.some((group) => group.key === selected)
      ? selected
      : (shownGroups[0]?.key ?? earlierGroups[0]?.key ?? null)
  const selectedGroup = allGroups.find((group) => group.key === selectedKey) ?? null

  /* FETCH REAL PICKS FOR THE BUYER ACTUALLY OPEN. `OrderDetail`'s body and `BuyerDetail`'s
   *  own per-buyer walk both read `line.picks` off `answers`; every other order's line reads
   *  `reason` alone off the lite tier `payload` already carries. `ownsAWalkableBody` is the
   *  exact set those two consumers draw from (`groupWalkable`, `OrderDetail`'s own gate), so
   *  fetching anything wider would pay for a picker no view here builds. Missing keys only —
   *  once `detail` holds an order it is not asked for again until `payload` changes (the
   *  effect above clears it then, and only then). This is deliberately a spinner-shaped cost:
   *  opening a buyer for the first time in a sitting waits on one small POST rather than on
   *  nothing, in exchange for `GET /orders` no longer paying for it on every poll regardless
   *  of whether anyone opened anything. */
  useEffect(() => {
    if (selectedGroup === null) return
    const keys = selectedGroup.orders.filter(ownsAWalkableBody).map((order) => order.key)
    fetchMissingPicks(keys)
  }, [selectedGroup, fetchMissingPicks])

  /* `docs/specs/order-walk-plan.md` §13 REPLACES THE WALK'S OWN FETCH AND ITS FREEZE. There is
   *  no more "Start" and no more frozen pass (§8/§12, superseded): selecting an order starts
   *  its walk at once, the same as clicking a box opens it — `useOrderWalk` below re-fetches
   *  `POST /orders/walk-plan` whenever the WALKED SET changes, and that is the whole of it.
   *  Nothing "ends" a walk any more than clicking away from a box "ends" looking at it; the
   *  hook's own state resets itself the moment the set changes, and unmounting `#/orders`
   *  unmounts it same as everything else on the screen. */

  const ordersByKey = useMemo(() => {
    const out = new Map<string, OrderRow>()
    for (const order of payload?.orders ?? []) out.set(order.key, order)
    return out
  }, [payload])

  /** THE WALKED SET (§13): the selected order's own walkable orders, plus every ticked buyer's.
   *  Selecting a buyer starts a walk over their own orders at once — a buyer with nothing
   *  walkable contributes nothing, so viewing a done buyer alone never opens an empty walk. */
  const walkedKeys = useMemo(() => {
    const out = new Set<string>()
    if (selectedGroup !== null) for (const order of walkableOf.get(selectedGroup.key) ?? []) out.add(order.key)
    for (const key of walkTicked) for (const order of walkableOf.get(key) ?? []) out.add(order.key)
    return out
  }, [selectedGroup, walkableOf, walkTicked])

  const walk = useOrderWalk({ walkedKeys, ordersByKey, rawCards, onPull: onWalkPull, onUndo: onWalkUndo })

  /* THE HASH NAMES A BUYER, OR — FOR AN OLD LINK — AN ORDER RESOLVED TO ITS BUYER, ONCE THE
     LEDGER HAS ACTUALLY ANSWERED; from then on the store leads and the hash follows. `?buyer=`
     is read first because it is this screen's own current spelling; `?order=` is kept only so
     a link written before this change still lands somewhere real.
     A MOUNT-ONLY EFFECT CANNOT DO THIS: `payload` is still null on the first render, so
     `groups` is empty and `groupForOrderKey` can never resolve anything — the read has to wait
     for the read it is reading. `linkHandled` makes it run once in EFFECT, the first time
     `groups` holds something (or `?buyer=`, which needs no group lookup at all and is applied
     the moment the effect first runs). */
  const linkHandled = useRef(false)
  useEffect(() => {
    if (linkHandled.current) return
    const buyerWanted = buyerParam()
    if (buyerWanted !== null) {
      linkHandled.current = true
      setHub({ selected: buyerWanted })
      return
    }
    const orderWanted = orderParam()
    if (orderWanted === null) {
      linkHandled.current = true
      return
    }
    if (allGroups.length === 0) return // wait for the read this link is about
    linkHandled.current = true
    const resolved = groupForOrderKey(groups, orderWanted)
    if (resolved !== null) setHub({ selected: resolved.key })
  }, [groups, allGroups])
  useEffect(() => {
    if (selectedKey !== null) mirrorBuyerParam(selectedKey)
  }, [selectedKey])

  /* THE ARROWS STEP THE LIST OF BUYERS where there is a list beside the detail. Never with a
   *  modifier (Cmd-arrow is the shell's, D51) and never out of a field.
   *
   *  `J`/`K` ARE THE WALK'S OWN KEYS NOW (§13, "Stepping"), not the buyer list's — a walk is
   *  always showing beside the buyer list once one is selected, and the two lists cannot both
   *  answer to the same bare letters. `↑`/`↓` keep doing what `J`/`K` used to for buyers; the
   *  reference sheet (`App.tsx`'s `SHORTCUTS`) says so. */
  useEffect(() => {
    if (phone || shownGroups.length === 0) return
    const onKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return
      const target = event.target as HTMLElement | null
      if (target !== null && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.isContentEditable)) return
      const step = event.key === 'ArrowDown' ? 1 : event.key === 'ArrowUp' ? -1 : 0
      if (step === 0) return
      const at = shownGroups.findIndex((one) => one.key === selectedKey)
      const next = shownGroups[Math.min(shownGroups.length - 1, Math.max(0, (at === -1 ? 0 : at) + step))]
      if (next === undefined) return
      event.preventDefault()
      setHub({ selected: next.key })
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [phone, shownGroups, selectedKey])

  /* `J`/`K` STEP THE WALK LIST (§13). Same guard rules as the buyer list's own arrows. */
  useEffect(() => {
    if (walk.rows.length === 0) return
    const onKey = (event: KeyboardEvent) => {
      if (event.metaKey || event.ctrlKey || event.altKey) return
      const target = event.target as HTMLElement | null
      if (target !== null && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT' || target.isContentEditable)) return
      const step = event.key === 'j' || event.key === 'J' ? 1 : event.key === 'k' || event.key === 'K' ? -1 : 0
      if (step === 0) return
      event.preventDefault()
      walk.step(step)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [walk])

  const setFilter = (next: PullFilter) => setHub({ filter: next })
  /* The phone's rail sheet closes once a buyer is chosen (`BoxBrowse.tsx`'s own `pickRow`) —
   *  picking a buyer is this sheet's one job, unlike the box picker it mirrors. */
  const select = (key: string) => {
    setHub({ selected: key })
    if (phone) setRailOpen(false)
  }

  if (failure !== null && payload === null) {
    return (
      <div className="orders-stage">
        <div className="bn-panel">
          <EmptyState
            icon="alert"
            title="Orders did not answer"
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
      <div className="orders-stage orders-skeleton" aria-busy="true" aria-label="Reading orders">
        <span className="bn-skeleton orders-skel-line" />
        <span className="bn-skeleton orders-skel-filter" />
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
            body="Fetch orders from TCGplayer, or paste one in."
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

  const filterOptions: { readonly value: PullFilter; readonly label: string; readonly count: number }[] = [
    { value: 'all', label: 'All open', count: open.length },
    ...ORDER_REASONS.filter((reason) => counts[reason] > 0).map((reason) => ({
      value: reason as PullFilter,
      label: REASON_SHORT[reason],
      count: counts[reason],
    })),
    { value: 'done', label: 'Done', count: done.length },
  ]

  const chips = (
    <select
      className="bn-select orders-filter-select"
      aria-label="Show orders by how their lines answered"
      value={filter}
      onChange={(event) => {
        const next = event.target.value
        setFilter(next === 'all' || next === 'done' || isOrderReason(next) ? next : 'all')
      }}
    >
      {filterOptions.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label} ({option.count})
        </option>
      ))}
    </select>
  )

  /* A SEARCH THAT LEAVES NOTHING GETS ITS OWN SENTENCE, ahead of the filter-shaped ones below
     — the query is the reason nothing is drawn regardless of which filter is chosen, and "Clear
     search" is the one action that actually restores something. */
  const nothingShown =
    query !== '' ? (
      <div className="bn-panel">
        <EmptyState
          icon="search"
          title="No buyer matches"
          body={`Nobody's name or order number contains “${query}”.`}
          actions={
            <Button icon="x" onClick={() => onQueryChange('')}>
              Clear search
            </Button>
          }
        />
      </div>
    ) : (
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

  /* ----------------------------------------------------------------- the walk, on one screen */

  /** THE TICK, BESIDE THE ROW AND NEVER INSIDE IT. `BuyerRow` is a `<button>`; a checkbox
   *  nested in one is invalid, and a screen reader would have two controls where the markup
   *  claims one. The `<li>` is the flex row and carries both.
   *
   *  A BUYER WITH NOTHING WALKABLE DRAWS NO TICK — not a disabled one (§12). There is nothing
   *  to select, and the row keeps its own full width where a dead control would sit. */
  const tickFor = (group: BuyerGroup) => {
    if ((walkableOf.get(group.key)?.length ?? 0) === 0) return null
    const on = walkTicked.has(group.key)
    return (
      <label className="bn-check orders-index-tick">
        <input
          type="checkbox"
          checked={on}
          onChange={() => toggleWalkTick(group.key)}
          aria-label={`Walk ${group.name ?? `order ${group.number ?? ''}`.trim()}`}
        />
      </label>
    )
  }

  /** TICK ALL / UNTICK ALL, OVER THE ROWS IN VIEW AND ONLY THOSE (§12 answer 1). Always drawn,
   *  so neither its arrival nor its departure can move the list beneath it (D118); disabled
   *  where the current filter leaves nothing that can hold a tick.
   *
   *  `Untick all` SUBTRACTS the rows in view rather than clearing the set. The prune above
   *  keeps the stored set inside the visible one, so the two are the same thing today — but
   *  the subtraction is the RULE, and a clear would only happen to agree with it. */
  const selectBar = (
    <div className="orders-select-bar" role="group" aria-label="Choose which buyers to walk">
      <Button
        size="sm"
        disabled={tickableKeys.size === 0}
        onClick={() => setWalkTicked((prev) => new Set([...prev, ...tickableKeys]))}
      >
        Tick all
      </Button>
      <Button
        size="sm"
        disabled={tickableKeys.size === 0}
        onClick={() => setWalkTicked((prev) => new Set([...prev].filter((key) => !tickableKeys.has(key))))}
      >
        Untick all
      </Button>
    </div>
  )

  /** THE RAIL'S SEARCH/STATUS/SORT SLOT (§13, point 1) — exactly section 12's own controls,
   *  restated as a fragment so both the rail and the phone rail sheet draw the same markup
   *  rather than two hand-kept copies. */
  const searchSlot = (
    <div className="orders-toolbar orders-rail-toolbar">
      {chips}
      <div className="orders-view-controls" role="group" aria-label="Sort and narrow the buyer list">
        <div className="bn-input-wrap orders-search">
          <Icon name="search" size={16} />
          <input
            type="search"
            className="bn-input orders-search-input"
            aria-label="Search buyers by name or order number"
            placeholder="Search buyers or order #"
            autoComplete="off"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
          />
          {query === '' ? null : (
            <button type="button" className="orders-search-clear" aria-label="Clear search" onClick={() => onQueryChange('')}>
              <Icon name="x" size={12} />
            </button>
          )}
        </div>
        <select
          className="bn-select orders-status-select"
          aria-label="Filter by status"
          value={view.status ?? ''}
          onChange={(event) => onStatusChange(event.target.value === '' ? null : event.target.value)}
        >
          <option value="">All</option>
          {statusOptions.map((option) => (
            <option key={option.status} value={option.status}>
              {option.status} ({option.count})
            </option>
          ))}
        </select>
        <Segmented<OrderSort>
          className="orders-sort"
          value={view.sort}
          label="Sort"
          options={[
            { value: 'newest', label: 'Newest' },
            { value: 'oldest', label: 'Oldest' },
          ]}
          onChange={onSortChange}
        />
        <label className="orders-hide-unknown">
          <input type="checkbox" checked={view.hideUnknown} onChange={(event) => onHideUnknownChange(event.target.checked)} />
          Hide unknown SKUs
        </label>
        <span className="orders-resort-slot">
          {staleSentence === null ? null : (
            <Chip icon="refresh" className="orders-resort" title="Sorted before this changed." onClick={onReSort}>
              {staleSentence} · re-sort
            </Chip>
          )}
        </span>
      </div>
    </div>
  )

  /** THE ORDERS LIST, EXACTLY BUYERROW'S SHAPE — `.browse-boxes.bn-panel`, where inventory
   *  lists its boxes (§13, point 2). */
  const ordersList =
    shownGroups.length === 0 && earlierGroups.length === 0 ? (
      nothingShown
    ) : (
      <>
        <ol className="orders-index bn-stagger">
          {shownGroups.map((group, at) => (
            <li key={group.key} className="orders-index-item" style={{ '--i': at } as CSSProperties}>
              {tickFor(group)}
              <BuyerRow group={group} answers={answers} selected={group.key === selectedKey} onSelect={() => select(group.key)} />
            </li>
          ))}
        </ol>
        {earlierGroups.length === 0 ? null : (
          <details className="orders-earlier">
            <summary>
              Earlier · {earlierGroups.length} {plural(earlierGroups.length, 'buyer', 'buyers')}
            </summary>
            <ol className="orders-index">
              {earlierGroups.map((group) => (
                <li key={group.key} className="orders-index-item">
                  {tickFor(group)}
                  <BuyerRow group={group} answers={answers} selected={group.key === selectedKey} onSelect={() => select(group.key)} />
                </li>
              ))}
            </ol>
          </details>
        )}
        <p className="orders-index-hint">
          <Kbd>↑</Kbd>
          <Kbd>↓</Kbd> step through the buyers
        </p>
      </>
    )

  /** WHERE INVENTORY SHOWS THE BOX PANEL AND ITS SECTION LIST (§13, points 3-5): the selected
   *  order's panel (mock A), the strip, and the walk. `.browse-walk.bn-panel`. */
  const railWalkPanel = (
    <div className="browse-walk bn-panel">
      <div className="browse-box-head">
        {selectedGroup === null ? (
          <div className="browse-shelfnote">
            <span className="boxops-identity-num">No buyer selected</span>
            <p>Choose a buyer on the left.</p>
          </div>
        ) : (
          <OrderPanel group={selectedGroup} answers={answers} onManage={() => setManageOpen(true)} />
        )}
      </div>

      <div className="browse-status">
        <span className="browse-status-text">
          {walk.sections.length} {plural(walk.sections.length, 'section', 'sections')}
        </span>
        <span className="bn-spacer" />
        <Chip pressed={hideSold} className="browse-hidesold" onClick={() => setHideSold(!hideSold)}>
          Hide sold
        </Chip>
      </div>

      <WalkList walk={walk} hideSold={hideSold} />

      {walk.rows.length === 0 ? null : (
        <p className="browse-listkeys">
          <span>
            <Kbd>J</Kbd>
            <Kbd>K</Kbd> card
          </span>
        </p>
      )}
    </div>
  )

  return (
    <div className="orders-stage">
      {failure === null ? null : <Notice tone="danger" title={failure.message} code={failure.code} />}

      {/* THE DEGRADED MAP, SAID ONCE. Every line is narrower when the card map did not answer, so
          the sentence belongs here and not repeated down eighty lines. Nothing else is affected:
          the ledger answered, the copies it offered are drawn, and every Mark sold still works. */}
      {storeFailed ? (
        <p className="orders-store-note" role="status">
          <Icon name="info" size={14} />
          <span>Showing only the copies this order was offered — not every copy in the store.</span>
          <button type="button" className="orders-fold-btn" onClick={onRereadStore}>
            <Icon name="refresh" size={13} />
            Read it again
          </button>
        </p>
      ) : null}

      {/* `#/orders` TAKES INVENTORY'S EXACT SKELETON (§13): `.browse-body`'s rail and pane, the
          same widths and breakpoints `BoxBrowse.css` already gives `#/inventory`. The rail is
          orders where inventory has boxes; the pane is the selected card's `CardLocations`,
          reused rather than rebuilt (`OrdersWalkPane.tsx`).

          ONE STRUCTURE, ALWAYS — never a second branch picked in JavaScript (D123: a screen
          asks its column, browser zoom is not the lever). `.browse-body`'s own breakpoints
          (`BoxBrowse.css:12-26`, already imported here) collapse the rail below 768px; there is
          no 1024px reader left in this file to disagree with them. */}
      {/* THE PHONE RAIL CHIP — below 768px `.browse-body > .browse-map` below is hidden by
          that same CSS, so the buyer picker needs its own way onto the screen: the chip
          `BoxBrowse.tsx`'s own `.browse-mobilebar` opens its rail sheet from, sibling to
          `.browse-body` for the same reason theirs is (the chip's sticky-top and bleed
          margin read the page's own padding, not a grid column's). */}
      {phone ? (
        <div className="browse-mobilebar">
          <button
            type="button"
            className="browse-boxchip"
            aria-haspopup="dialog"
            onClick={() => setRailOpen(true)}
          >
            <Icon name="list" size={16} />
            <span className="browse-boxchip-text">
              {selectedGroup === null ? 'Choose a buyer' : selectedGroup.name ?? `No name · #${selectedGroup.number}`}
            </span>
            <Icon name="chevronDown" size={14} className="browse-boxchip-chev" />
          </button>
        </div>
      ) : null}

      <div className="browse-body">
        <div className="browse-map">
          {searchSlot}
          <div className="browse-boxes bn-panel" role="group" aria-label="Choose an order to walk">
            {selectBar}
            {ordersList}
          </div>
          {railWalkPanel}
        </div>
        <div className="browse-side">
          <WalkMainPane walk={walk} phone={phone} />
          {why}
        </div>
      </div>

      {phone && railOpen ? (
        <Overlay kind="bottom" label="Choose a buyer" onClose={() => setRailOpen(false)} passKeys className="browse-railsheet">
          {searchSlot}
          <div className="browse-boxes bn-panel" role="group" aria-label="Choose an order to walk">
            {selectBar}
            {ordersList}
          </div>
        </Overlay>
      ) : null}

      {!manageOpen ? null : (
        <Overlay kind="sheet" label="Manage orders" onClose={() => setManageOpen(false)} className="orders-manage-sheet">
          <section className="bn-panel-body">
            <div className="bn-panel-head">
              <span className="bn-section-title">
                <Icon name="plus" size={16} /> Add orders
              </span>
            </div>
            {well}
          </section>
          {receipt}
          {/* FIXED, THIS PASS: `statusControl`/`statusPanel` were ALSO drawn here, a second time
              — `wellOf`'s own `{withFetch ? statusControl : null}` (inline in the paste row) and
              `{withFetch ? statusPanel : null}` right under it already put both on screen inside
              `.orders-paste`, `well`'s own section above. This second copy dated to the Manage
              sheet's first landing (5a42cb62) and every case that opened the picker got two
              `.orders-statuses-ask` elements — a Playwright strict-mode violation, not a screen
              a person had reason to look at differently, since the two copies were identical.
              Removing this block leaves the one inside `well`, which is also the one the
              narrowing control's own comment says is correct: "the narrowing sits beside the
              press, not in front of it." */}
          <BacklogPrompt open={open} busy={busy} onStandDown={onStandDown} />
          <ReconcileBacklogPanel orders={open} busy={busy} onPress={onReconcileBacklog} />

          {/* THE SELECTED BUYER'S OWN ORDERS — stand-down, close-line, declare-kind and
              hand-fill, still reachable per order (§13: "nothing lost"). `hidePicks`: the walk
              beside this sheet is the one place to Mark sold from, so this never draws a second
              set of pressable copy rows for the same card. */}
          {selectedGroup === null ? null : (
            <div className="orders-manage-orders">
              <span className="bn-section-title">{selectedGroup.name ?? `No name · #${selectedGroup.number}`}'s orders</span>
              {selectedGroup.orders.map((order) => (
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
                  variant="panel"
                  hidePicks
                />
              ))}
            </div>
          )}
        </Overlay>
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

/* ================================================================== a buyer, in the list */

/** Worst-of ordering over a group's open orders — `look` and `unresolved` outrank `short`,
 *  which outranks `ready`. A group with nothing open is `done`. Used only to pick the ONE dot
 *  colour a multi-order buyer's row shows; every order's own status still shows on its own
 *  chip beside it. */
const STATUS_RANK: Record<Status, number> = { look: 0, unresolved: 1, short: 2, ready: 3, done: 4 }

function worstStatus(group: BuyerGroup, answers: ReadonlyMap<string, ResolvedOrder>): Status {
  let worst: Status = 'done'
  for (const order of group.open) {
    const status = statusOf(order, answers.get(order.key) ?? null)
    if (STATUS_RANK[status] < STATUS_RANK[worst]) worst = status
  }
  return worst
}

/** The buyer's index row and phone accordion head — replaces `OrderSummaryRow`
 *  (`D193`). A nameless buyer draws "No name · #<number>"; a buyer with
 *  more than one order draws an `N orders` pill and a chip per open order, so a two-order
 *  buyer is visibly one that needs both counted rather than a single order in disguise. */
function BuyerRow({
  group,
  answers,
  selected,
  expanded,
  onSelect,
}: {
  readonly group: BuyerGroup
  readonly answers: ReadonlyMap<string, ResolvedOrder>
  readonly selected: boolean
  /** Set where the row is an accordion head rather than a list entry beside a detail. */
  readonly expanded?: boolean
  readonly onSelect: () => void
}) {
  const heading = group.name ?? `No name · #${group.number}`
  const status = worstStatus(group, answers)
  const placed = whenLabel(group.latest)
  const pct = group.wanted > 0 ? Math.min(100, Math.round((group.recorded / group.wanted) * 100)) : 0
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
      title={heading}
    >
      <span className={`orders-index-dot orders-index-dot-${STATUS_DOT[status]}`} aria-hidden="true" />
      <span className="orders-index-main">
        <span className="orders-index-number">{heading}</span>
        <span className="orders-index-meta">
          {/* THE SECOND >1 SIGNAL LIVES IN THE DETAIL HEADER; THIS ONE IS THE FIRST. Drawn only
              when there is something to count — a single order's row looks exactly as it always
              did. */}
          {group.orders.length > 1 ? (
            <Pill size="sm" className="orders-index-count">
              {group.orders.length} orders
            </Pill>
          ) : null}
          {placed === null ? null : <time>placed {placed}</time>}
          {group.open.map((order) => {
            const orderStatus = statusOf(order, answers.get(order.key) ?? null)
            if (orderStatus === 'ready') return null
            const pill = STATUS_PILL[orderStatus]
            return (
              <Pill key={order.key} size="sm" tone={pill.tone} icon={pill.icon}>
                {order.number}
              </Pill>
            )
          })}
        </span>
      </span>
      <span className="orders-index-side">
        <span className="orders-index-figure">
          {group.wanted === 0 ? 'nothing open' : group.recorded >= group.wanted ? 'all sold' : (
            <>
              <b>{group.wanted - group.recorded}</b> left
            </>
          )}
        </span>
        <span
          className={`bn-progress orders-index-bar${group.wanted > 0 && group.recorded >= group.wanted ? ' bn-progress-ok' : ''}`}
          role="progressbar"
          aria-valuenow={group.recorded}
          aria-valuemin={0}
          aria-valuemax={group.wanted}
          aria-label="Copies sold"
        >
          <span style={{ width: `${pct}%` }} />
        </span>
      </span>
      {expanded === true ? <Icon name="chevronDown" size={16} className="orders-index-chev" /> : null}
    </button>
  )
}

/* ============================================================== the selected order's panel */

/** WHERE INVENTORY SHOWS THE BOX PANEL, ORDERS SHOWS THIS (§13, mock A): `BoxOps.tsx`'s own
 *  `.boxops-identity` SHAPE — the small-caps label, the title, `Manage` top-right, the status
 *  pill — with the dotted `.boxops-identity-line` replaced by the kit's `bn-stat` triad, the
 *  same one `CardLocations.tsx`'s "Every copy of this card" draws (owed/sold/short in place of
 *  copies/on-hand/live). Classes only, never `BoxOps.tsx` itself — a second builder owns that
 *  file's own line on a separate branch. */
function OrderPanel({
  group,
  answers,
  onManage,
}: {
  readonly group: BuyerGroup
  readonly answers: ReadonlyMap<string, ResolvedOrder>
  readonly onManage: () => void
}) {
  const status = worstStatus(group, answers)
  const pill = STATUS_PILL[status]
  const owed = Math.max(0, group.wanted - group.recorded)
  const short = group.orders.reduce((sum, order) => {
    const lines = answers.get(order.key)?.lines ?? []
    return sum + lines.filter((line) => line.reason === 'short').reduce((s, line) => s + line.owed, 0)
  }, 0)
  const placed = whenLabel(group.latest)
  const pct = group.wanted > 0 ? Math.min(100, Math.round((group.recorded / group.wanted) * 100)) : 0
  /* MOCK A NAMES ONE ORDER; A BUYER MAY HOLD SEVERAL (D193). §13 does not resolve this case, so
   * this is this build's own call, kept for the owner to overrule: a two-order buyer's panel
   * reads `2 ORDERS` in the small-caps slot instead of a single id, and owed/sold/short
   * aggregate across every order the buyer holds — the same total `BuyerRow`'s own figure
   * already counts, not a second arithmetic. */
  const label = group.orders.length === 1 ? `ORDER ${group.orders[0]!.number}` : `${group.orders.length} ORDERS`

  return (
    <div className="boxops-identity">
      <div className="boxops-identity-top">
        <div className="boxops-identity-text">
          <span className="boxops-identity-num">{label}</span>
          <h2 className="boxops-identity-name">{group.name ?? `No name · #${group.number}`}</h2>
        </div>
        <Button variant="quiet" size="sm" icon="settings" className="browse-manage" aria-haspopup="dialog" onClick={onManage}>
          Manage
        </Button>
      </div>

      <p className="boxops-identity-line">
        <Pill tone={pill.tone} icon={pill.icon}>
          {pill.label}
        </Pill>
      </p>

      <div className="card-locations-stats">
        <div className="bn-stat card-locations-stat">
          <span className="bn-stat-value">{owed}</span>
          <span className="bn-stat-label">owed</span>
        </div>
        <div className="bn-stat card-locations-stat">
          <span className="bn-stat-value">{group.recorded}</span>
          <span className="bn-stat-label">sold</span>
        </div>
        <div className="bn-stat card-locations-stat">
          <span className="bn-stat-value">{short}</span>
          <span className="bn-stat-label">short</span>
        </div>
      </div>

      {group.wanted === 0 ? null : (
        <div
          className="bn-progress"
          role="progressbar"
          aria-valuenow={group.recorded}
          aria-valuemin={0}
          aria-valuemax={group.wanted}
          aria-label="Copies sold"
        >
          <span style={{ width: `${pct}%` }} />
        </div>
      )}

      {placed === null ? null : (
        <div className="boxruns">
          <span className="bn-dot" aria-hidden="true" />
          <p className="boxruns-said">placed {placed}</p>
        </div>
      )}
    </div>
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
  hidePicks,
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
  /** Set inside a buyer's "By order" fold when a merged walk above it already draws this
   *  order's pullable copies — never on a standalone `OrderDetail`. */
  readonly hidePicks?: boolean
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

  /* A DONE ORDER IS NOT ALWAYS A CLOSED BOOK (fix for the owner's report: a shipped order can
     still owe copies). `ownsAWalkableBody` is the discriminator — `terminal` plus what is
     still owed, never the `status` string (D114) — so an order closed because every copy was
     already pulled draws nothing here exactly as before, and one closed by the marketplace
     while copies remain open gets its lines and its Pull button back. */
  const body =
    !ownsAWalkableBody(order) ? null : answer === null ? (
      <div className="orders-reason orders-reason-warn">
        <Icon name="clock" size={16} />
        <div>
          <p className="orders-line-says">Not resolved in this read.</p>
          <p className="orders-line-remedy">Read again to resolve it.</p>
        </div>
        <Button icon="refresh" onClick={onReread}>
          Try again
        </Button>
      </div>
    ) : (
      <>
        <ol className="orders-lines">
          {answer.lines.map((line) => (
            <OrderLineRow
              key={`${line.order_key}/${line.sku}`}
              order={order}
              line={line}
              store={store}
              claims={claims}
              busy={busy}
              hidePicks={hidePicks}
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
            <>All {order.wanted} sold</>
          ) : (
            <>
              <b>{order.wanted - order.recorded}</b> {order.wanted - order.recorded === 1 ? 'copy' : 'copies'} still to sell
              {order.recorded === 0 ? null : <i>{order.recorded} already sold</i>}
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
            aria-label="Copies sold"
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
            Sealed product
          </Button>
        ) : (
          <Button
            icon="undo"
            busy={claiming}
            disabled={locked}
            onClick={() => onDeclareKind(order, line, null)}
          >
            Undo — not sealed
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
  hidePicks,
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
  /** Suppress the copy map and the pick rows — a buyer's merged walk already draws them. The
   *  reason banner, the remedy and the stand-down controls still render. */
  readonly hidePicks?: boolean
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

  /* WHEN A MERGED WALK ALREADY DRAWS THIS LINE'S PULLABLE COPIES, THIS ROW SHOWS ONLY THE REST.
     `takeable` (see `copiesOf`) is exactly `buildWalk`'s own admission test — aimable and not
     already held — so filtering it out here is filtering out precisely the rows duplicated
     above. A copy already spoken for by another line, or one the ledger already holds, is NOT
     takeable and has nowhere else on screen to be seen, so it stays. */
  const copies = hidePicks === true ? map.copies.filter((copy) => !copy.takeable) : map.copies

  /* The first six in the map's order, PLUS every copy this order was offered wherever it fell —
     the resolver's own choice is never the thing behind the fold. */
  const shown = useMemo(() => {
    if (unfolded || copies.length <= COPIES_SHOWN + 2) return copies
    const keep = new Set(copies.slice(0, COPIES_SHOWN).map((copy) => copy.key))
    for (const copy of copies) if (copy.offered) keep.add(copy.key)
    return copies.filter((copy) => keep.has(copy.key))
  }, [copies, unfolded])
  const folded = copies.length - shown.length
  /* Where the folded ones are, so the control names a drawer rather than a number alone. */
  const foldedIn = [...new Set(copies.filter((copy) => !shown.includes(copy)).map((copy) => copy.pick.box))]

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

      {hidePicks || single || map.stops.length === 0 ? null : (
        <CopyMapView map={map} whole={whole} onHand={line.on_hand} figure={figure} lit={lit} onLight={setLit} />
      )}

      {copies.length === 0 ? null : (
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
          {copies.length <= COPIES_SHOWN + 2 ? null : (
            <li className="orders-fold">
              <button
                type="button"
                className="orders-fold-btn"
                aria-expanded={unfolded}
                onClick={() => setUnfolded((was) => !was)}
              >
                <Icon name={unfolded ? 'chevronUp' : 'chevronDown'} size={14} />
                {unfolded ? (
                  <>Show fewer — all {copies.length} are on screen</>
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
              {figure.pulled} {figure.pulled === 1 ? 'copy has' : 'copies have'} already been sold for this order and left
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
          All {figure.wanted} sold
        </Pill>
      </span>
    )
  }
  return (
    <span className="orders-line-figure">
      <span className="orders-line-remaining">
        <b>{figure.remaining}</b> remaining
      </span>
      {figure.pulled === 0 ? null : <span className="orders-line-pulled">{figure.pulled} already sold</span>}
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
/** THE ONE SENTENCE THAT TIES THE THREE LIVE NUMBERS TOGETHER (the owner's own question,
 *  2026-09-17: "is it saying they ordered one and there's two places, or they need two and
 *  here's two places"). `figure.remaining` is how many are still owed, `total` is how many the
 *  store holds, `map.stops` is how many drawers hold them — and this line answers all three in
 *  one place, once, above the boxes it describes rather than on every button beneath them.
 *
 *  NEVER RETURNS NULL (D118). The element this fills stays mounted whether the line is still
 *  owed or already satisfied — dropping it the instant the last copy is pulled is exactly the
 *  press that would move every box row beneath it up the page. A satisfied line says so, plainly,
 *  rather than "Pull 0". */
function pullLedeOf(figure: LineFigure, map: CopyMap, whole: boolean, onHand: number): string {
  const total = whole ? onHand : map.total
  const drawers = map.stops.length
  const held = `${total} on hand`
  if (figure.remaining === 0) return `All ${figure.wanted} sold — ${held}.`
  const toSell = `${figure.remaining} to sell`
  if (drawers === 1) {
    const only = map.stops[0]
    if (only?.pooled) return `${toSell} — ${held}, pooled.`
    return `${toSell} — ${held}, 1 box.`
  }
  return `${toSell} — ${held} across ${drawers} boxes.`
}

function CopyMapView({
  map,
  whole,
  onHand,
  figure,
  lit,
  onLight,
}: {
  readonly map: CopyMap
  /** Whether the store index answered, so `All 14 copies` may be said. When it did not, the map
   *  is the resolver's picks alone and the sentence claims nothing about what it cannot see. */
  readonly whole: boolean
  readonly onHand: number
  readonly figure: LineFigure
  readonly lit: string | null
  readonly onLight: (key: string | null) => void
}) {
  const lede = pullLedeOf(figure, map, whole, onHand)
  const runnerUp = map.stops[1] ?? null

  return (
    <div className="orders-map" role="group" aria-label={`Where the ${map.total} ${map.total === 1 ? 'copy is' : 'copies are'}`}>
      <p className="orders-map-lede">
        <Icon name="layers" size={13} />
        {lede}
      </p>
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
                <span className="bn-sr">{runnerUp === null ? 'The box to walk to. ' : 'Most copies here. '}</span>
                <Icon name="pin" size={13} className="orders-map-pin" />
              </>
            ) : null}
            <span className="orders-map-name">
              <b>{stop.title}</b>
              {stop.name === null ? null : <em>{stop.name}</em>}
            </span>
            {/* A PER-BOX FIGURE, NOT THE BOX'S TOTAL — `stop.total` is `buildCopyMap`'s own count
               of THIS card in this drawer, never a whole-box card count, so "here" is read
               against the lede's "on hand" rather than against everything the drawer holds. */}
            <span className="orders-map-count">
              <b>{stop.total}</b> here
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
            onClick={() => setHub({ selected: order.key })}
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
          {pick.capture_id === null ? 'This copy has no capture record, so it cannot be marked sold from here.' : 'Not offered for this reason.'}
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
          Mark sold
        </Button>
      )}
    </li>
  )
}

