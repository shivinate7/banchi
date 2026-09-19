/* app/src/OrdersWalkPane.tsx — the walked cards, drawn as `#/inventory` draws a box (`docs/
 * specs/order-walk-plan.md` §13, "Orders is inventory's screen with orders in the rail — RULED
 * 2026-09-19"). It replaces `OrdersWalk.tsx` (deleted whole, not adapted): there is no more
 * "stop", "take" (as a screen word) or "pull" here — a physical pick is a CARD in a WALK LIST,
 * shaped exactly like `BoxBrowse.tsx`'s own section list, and the card a person is standing on
 * gets `CardLocations` — the same panel `#/inventory` draws over a box's card — with `Mark
 * sold` as the one write.
 *
 * THE WIRE IS UNCHANGED: `POST /orders/walk-plan` (`server.ts:walkPlan`), `WalkPlan` and its
 * parts, and the pull/undo write `Orders.tsx` already makes (`onWalkPull`/`onWalkUndo`,
 * `pullCopy`/`undoPull`). Nothing here edits `pipeline/walkplan.py`; which drawers, which
 * cards, and the density order are exactly what the solver already decided.
 *
 * ONE ROW PER PHYSICAL PICK. A `WalkPlanTake` can need more than one copy out of the SAME
 * stop (`take.wanted` more than one, several of `take.copies` carrying `here: true`); each such
 * copy is its own row, because that is a physical spot a hand has to visit, even though every
 * row under one take shares the take's own name and lands on the take's own `CardLocations`
 * group. `here` is the solver's own flag and this file does not recompute it.
 *
 * THE CURRENT CARD'S GROUP IS BUILT EXACTLY AS `Inventory.tsx`'s `loneGroup` AND THE OLD
 * `TakeBlock` BUILT ONE: a `SearchGroup` synthesised from the take's own wire fields, with
 * `copies: take.copies` IN THE WIRE'S OWN ORDER (this stop's copies first, D212/D93/D97), and
 * `CardLocations` reads it with `preserveOrder` so its own fullest-section re-rank never runs
 * over it — the trap the first build of this screen fell into. Positions patched from a pull's
 * own post-write facts are folded into `facts` and never change which row is first.
 */

import { useEffect, useMemo, useRef, useState } from 'react'

import { CardLocations } from './CardLocations'
import { Button, Icon, Pill } from './kit'
import { describeFailure, photoUrl, walkPlan } from './server'
import type { Failure } from './server'
import type {
  OrderRow,
  Place,
  PullRefresh,
  PullTarget,
  SearchCopy,
  SearchGroup,
  WalkPlan,
  WalkPlanCopy,
  WalkPlanStop,
  WalkPlanTake,
} from './types'
import './Inventory.css'
import './OrdersWalkPane.css'

/** `Inventory.tsx`'s own number, restated here for the reason every late-decorated file in
 *  this product restates it rather than importing across screens for one constant. */
const UNDO_WINDOW_MS = 20_000

export type WalkPullOutcome =
  | { readonly ok: true; readonly place: string; readonly refreshed: readonly Place[] }
  | { readonly ok: false; readonly failure: Failure }

export type WalkUndoOutcome =
  | { readonly ok: true; readonly refreshed: readonly Place[] }
  | { readonly ok: false }

/** `Orders.tsx`'s own pull for this screen — the write `onPull` already makes for the "By
 *  order" fold, over the walk's own shape. `Mark sold` is the button; this is what it calls. */
export type WalkPullFn = (args: {
  readonly order: OrderRow
  readonly sku: string
  readonly name: string
  readonly target: PullTarget
  readonly place: string | null
  readonly refresh: readonly PullRefresh[]
}) => Promise<WalkPullOutcome>

export type WalkUndoFn = (
  target: PullTarget,
  place: string,
  name: string,
  refresh: readonly PullRefresh[],
) => Promise<WalkUndoOutcome>

/** A take's `for` names every order sharing it but not how this stop's `wanted` splits between
 *  them. NEVER THE LIVE LEDGER: the first ref this pass has not yet recorded a copy against, by
 *  this pass's own tally alone, and once every ref has at least one, the first resolvable ref
 *  again. `record_pull` is the actual refusal if a specific order's line turns out full. */
function pickOrderFor(
  take: WalkPlanTake,
  ordersByKey: ReadonlyMap<string, OrderRow>,
  recordedForSku: ReadonlyMap<string, number>,
): OrderRow | null {
  for (const ref of take.for) {
    const order = ordersByKey.get(ref.key)
    if (order !== undefined && (recordedForSku.get(ref.key) ?? 0) === 0) return order
  }
  for (const ref of take.for) {
    const order = ordersByKey.get(ref.key)
    if (order !== undefined) return order
  }
  return null
}

/* ---------------------------------------------------------------------- the walk list's rows */

/** One physical pick — one row in the walk list, one card a hand can go stand at. */
export type WalkRow = {
  readonly rowKey: string
  readonly takeKey: string
  readonly stopKey: string
  readonly take: WalkPlanTake
  readonly copy: WalkPlanCopy
}

function rowKeyOf(stopKey: string, sku: string): string {
  return `${stopKey}/${sku}`
}

/** Flat, in the solver's own order: stops as given, takes as given, and — within a take — only
 *  the copies THIS stop reaches (`here: true`), in the wire's own order. Nothing here sorts. */
function rowsOf(plan: WalkPlan | null): WalkRow[] {
  if (plan === null) return []
  const out: WalkRow[] = []
  for (const stop of plan.stops) {
    for (const take of stop.takes) {
      for (const copy of take.copies) {
        if (!copy.here) continue
        out.push({ rowKey: `${stop.key}/${take.sku}/${copy.key}`, takeKey: rowKeyOf(stop.key, take.sku), stopKey: stop.key, take, copy })
      }
    }
  }
  return out
}

/** `BoxBrowse.tsx`'s own `sectionTitleOf`, restated for a stop rather than a `Row` — a pooled
 *  stop reads `Pooled · <game>`, same as `#/inventory`'s pooled shelf; a physical one leads
 *  with the box (the walk crosses boxes, which a single box's own section list never has to
 *  say) and then the section, exactly as `#/inventory` composes it. */
function stopTitle(stop: WalkPlanStop): string {
  if (stop.pooled) return `Pooled · ${stop.game_display ?? 'cards'}`
  const box = stop.box_name ?? (stop.box === null ? 'Box' : `Box ${stop.box}`)
  if (stop.section === null) return box
  const named = stop.section_name ? `Section ${stop.section} · ${stop.section_name}` : `Section ${stop.section}`
  const span = stop.span
  const withSpan =
    span === null ? named : span.end === null ? `${named} · #${span.start} onward` : `${named} · #${span.start}–#${span.end}`
  return `${box} · ${withSpan}`
}

export type WalkSection = { readonly key: string; readonly title: string; readonly rows: readonly WalkRow[] }

/** Run-length over the flat rows, the same trick `BoxBrowse.tsx:sectionsOf` uses, keyed by the
 *  stop rather than by a title string so a re-plan cannot merge two stops that only happen to
 *  print the same words. */
function sectionsOf(plan: WalkPlan | null, rows: readonly WalkRow[]): WalkSection[] {
  if (plan === null) return []
  const stopByKey = new Map(plan.stops.map((stop) => [stop.key, stop] as const))
  const out: WalkSection[] = []
  for (const row of rows) {
    const open = out[out.length - 1]
    if (open !== undefined && open.key === row.stopKey) {
      ;(open.rows as WalkRow[]).push(row)
      continue
    }
    const stop = stopByKey.get(row.stopKey)
    out.push({ key: row.stopKey, title: stop === undefined ? row.stopKey : stopTitle(stop), rows: [row] })
  }
  return out
}

/* ------------------------------------------------------------------ one receipt (a Mark sold) */

type Receipt = { readonly at: number; readonly canUndo: boolean; readonly target: PullTarget; readonly place: string; readonly orderKey: string }

/* ------------------------------------------------------------------------ the walk, as a hook */

/** THE WALK, OVER THE UNION `#/orders`' rail hands it — the selected order plus every ticked
 *  one, re-solved every time that set changes (§13: "each tick re-plans"). There is no frozen
 *  pass any more (§13 supersedes §8/§12's "Start"): selecting an order starts its walk at once,
 *  the same as clicking a box opens it, so the plan is simply a live read of the current
 *  selection — `POST /orders/walk-plan` fetched again whenever the KEY SET changes, never on a
 *  press. */
export function useOrderWalk({
  walkedKeys,
  ordersByKey,
  onPull,
  onUndo,
}: {
  readonly walkedKeys: ReadonlySet<string>
  readonly ordersByKey: ReadonlyMap<string, OrderRow>
  readonly onPull: WalkPullFn
  readonly onUndo: WalkUndoFn
}) {
  const keysSig = useMemo(() => [...walkedKeys].sort().join(' '), [walkedKeys])
  const [plan, setPlan] = useState<WalkPlan | null>(null)
  const [loading, setLoading] = useState(false)
  const [failure, setFailure] = useState<Failure | null>(null)
  const live = useRef(true)
  useEffect(() => {
    live.current = true
    return () => {
      live.current = false
    }
  }, [])

  useEffect(() => {
    if (walkedKeys.size === 0) {
      setPlan(null)
      setLoading(false)
      setFailure(null)
      return
    }
    setLoading(true)
    setFailure(null)
    walkPlan([...walkedKeys])
      .then((got) => {
        if (live.current) setPlan(got)
      })
      .catch((err) => {
        if (live.current) setFailure(describeFailure(err))
      })
      .finally(() => {
        if (live.current) setLoading(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keysSig])

  const rows = useMemo(() => rowsOf(plan), [plan])
  const sections = useMemo(() => sectionsOf(plan, rows), [plan, rows])

  const [current, setCurrent] = useState<string | null>(null)
  /* LANDING, THE SAME MOMENT INVENTORY'S OWN BOX WALK PICKS ITS FIRST CARD: the first row of a
     freshly landed plan. Keyed off the plan's own identity (a new object from a new fetch),
     never off `rows`'s content, so re-deriving `rows` from an unchanged plan cannot reset where
     the operator is standing. */
  const planRef = useRef<WalkPlan | null>(null)
  useEffect(() => {
    if (plan === planRef.current) return
    planRef.current = plan
    setCurrent(rowsOf(plan)[0]?.rowKey ?? null)
  }, [plan])

  const [facts, setFacts] = useState<ReadonlyMap<string, Place>>(new Map())
  const [recorded, setRecorded] = useState<ReadonlyMap<string, ReadonlyMap<string, number>>>(new Map())
  const [receipts, setReceipts] = useState<ReadonlyMap<string, Receipt>>(new Map())
  const [busyCopy, setBusyCopy] = useState<string | null>(null)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    setFacts(new Map())
    setRecorded(new Map())
    setReceipts(new Map())
    setBusyCopy(null)
  }, [keysSig])

  /* Ticks twice a second, only while some receipt's own undo window is still open — an idle
     walk pays for no timer. */
  const anyPending = useMemo(() => {
    for (const receipt of receipts.values()) if (now - receipt.at < UNDO_WINDOW_MS) return true
    return false
  }, [receipts, now])
  useEffect(() => {
    if (!anyPending) return
    const id = window.setInterval(() => setNow(Date.now()), 500)
    return () => window.clearInterval(id)
  }, [anyPending])

  const soldKeys = useMemo(() => new Set(receipts.keys()), [receipts])

  const currentRow = rows.find((row) => row.rowKey === current) ?? rows[0] ?? null

  /** `Inventory.tsx`'s own `loneGroup` and the old `TakeBlock`'s `group`, restated: a
   *  `SearchGroup` synthesised from one take's wire fields, `copies` in the WIRE's own order —
   *  never re-sorted here, and drawn with `preserveOrder` below so `CardLocations` never
   *  re-sorts it either. */
  const currentGroup: SearchGroup | null = useMemo(() => {
    if (currentRow === null) return null
    const { take } = currentRow
    return {
      sku: take.sku,
      names: take.name === null ? [] : [take.name],
      number: null,
      printed_total: null,
      number_display: take.number_display,
      set_hint: null,
      set: take.set,
      rarity: take.rarity,
      condition: take.condition,
      listed: { pushed: 0, staged: 0, live: 0 },
      sold_here: 0,
      on_hand: take.copies.length,
      listable: 0,
      live_as_of: null,
      copies: take.copies.map((copy): SearchCopy => {
        const fresh = facts.get(copy.key)
        return {
          key: copy.key,
          state: copy.state,
          state_at: null,
          has_photo: copy.has_photo,
          capture_id: copy.capture_id,
          cid: copy.cid,
          place: fresh ?? copy.place,
        }
      }),
    }
  }, [currentRow, facts])

  const totalRecorded = (sku: string): number => {
    let sum = 0
    for (const n of (recorded.get(sku) ?? new Map()).values()) sum += n
    return sum
  }

  /** Every copy in the plan sitting in `box`, minus the one being pressed and minus a copy
   *  already recorded here — `OrdersWalk.tsx`'s own `staleAfter`, restated over the flat
   *  `rows` this file keeps instead of a `RowState` map per take. */
  const staleAfter = (box: number, pressedKey: string): PullRefresh[] => {
    if (plan === null) return []
    const out: PullRefresh[] = []
    const seen = new Set<string>()
    for (const stop of plan.stops) {
      for (const take of stop.takes) {
        for (const copy of take.copies) {
          if (copy.place.box !== box) continue
          if (copy.key === pressedKey || soldKeys.has(copy.key)) continue
          if (seen.has(copy.key)) continue
          seen.add(copy.key)
          out.push({ box: copy.place.box, index: copy.place.index })
        }
      }
    }
    return out
  }

  const absorb = (blocks: readonly Place[]) => {
    if (blocks.length === 0) return
    setFacts((prev) => {
      const next = new Map(prev)
      for (const block of blocks) next.set(`${block.box}/${block.index}`, block)
      return next
    })
  }

  /** Step to the next row after a sale — `#387 of 675 so far` moving on. While the take is not
   *  yet fully recorded, the next UNSOLD copy of the SAME take leads, so the operator keeps
   *  marking that card; once it is, the first row of the next take lights (§13: "when a card's
   *  owed copies are all sold, the next card lights"). */
  const advanceAfter = (soldRowKey: string, satisfied: boolean, justSold: ReadonlySet<string>) => {
    const at = rows.findIndex((row) => row.rowKey === soldRowKey)
    if (at === -1) return
    if (!satisfied) {
      const next = rows.find((row, i) => i > at && row.takeKey === rows[at]!.takeKey && !justSold.has(row.copy.key))
      if (next !== undefined) {
        setCurrent(next.rowKey)
        return
      }
    }
    const next = rows.find((row, i) => i > at && row.takeKey !== rows[at]!.takeKey)
    if (next !== undefined) setCurrent(next.rowKey)
  }

  const select = (rowKey: string) => setCurrent(rowKey)

  const step = (direction: 1 | -1) => {
    if (rows.length === 0) return
    const at = rows.findIndex((row) => row.rowKey === current)
    const next = rows[Math.min(rows.length - 1, Math.max(0, (at === -1 ? 0 : at) + direction))]
    if (next !== undefined) setCurrent(next.rowKey)
  }

  const onSell = (copy: SearchCopy) => {
    if (busyCopy !== null) return
    const row = rows.find((candidate) => candidate.copy.key === copy.key)
    if (row === undefined) return
    const { take, stopKey } = row
    const order = pickOrderFor(take, ordersByKey, recorded.get(take.sku) ?? new Map())
    if (order === null) return
    const target: PullTarget | null = copy.capture_id === null ? null : { box: copy.place.box, index: copy.place.index, capture_id: copy.capture_id }
    if (target === null) return
    setBusyCopy(copy.key)
    void (async () => {
      const refresh = staleAfter(target.box, copy.key)
      const outcome = await onPull({ order, sku: take.sku, name: take.name ?? take.sku, target, place: copy.place.label, refresh })
      if (!live.current) return
      if (outcome.ok) {
        absorb(outcome.refreshed)
        setRecorded((prev) => {
          const next = new Map(prev)
          const bySku = new Map(next.get(take.sku) ?? [])
          bySku.set(order.key, (bySku.get(order.key) ?? 0) + 1)
          next.set(take.sku, bySku)
          return next
        })
        const justSold = new Set([...soldKeys, copy.key])
        setReceipts((prev) => new Map(prev).set(copy.key, { at: Date.now(), canUndo: true, target, place: outcome.place, orderKey: order.key }))
        const satisfied = totalRecorded(take.sku) + 1 >= take.wanted
        /* `stopKey` names which stop this row belongs to, kept for a future refinement that
           needs it; the advance itself only reads `rows`. */
        void stopKey
        advanceAfter(row.rowKey, satisfied, justSold)
      }
      setBusyCopy(null)
    })()
  }

  const undoCopy = (copyKey: string) => {
    const receipt = receipts.get(copyKey)
    if (receipt === undefined || busyCopy !== null) return
    const row = rows.find((candidate) => candidate.copy.key === copyKey)
    if (row === undefined) return
    setBusyCopy(copyKey)
    void (async () => {
      const refresh = staleAfter(receipt.target.box, copyKey)
      const outcome = await onUndo(receipt.target, receipt.place, row.take.name ?? row.take.sku, refresh)
      if (!live.current) return
      if (outcome.ok) {
        absorb(outcome.refreshed)
        setReceipts((prev) => {
          const next = new Map(prev)
          next.delete(copyKey)
          return next
        })
        setRecorded((prev) => {
          const bySku = prev.get(row.take.sku)
          if (bySku === undefined) return prev
          const count = bySku.get(receipt.orderKey)
          if (count === undefined) return prev
          const nextBySku = new Map(bySku)
          if (count <= 1) nextBySku.delete(receipt.orderKey)
          else nextBySku.set(receipt.orderKey, count - 1)
          const next = new Map(prev)
          next.set(row.take.sku, nextBySku)
          return next
        })
      }
      setBusyCopy(null)
    })()
  }

  return {
    loading,
    failure,
    plan,
    rows,
    sections,
    current,
    currentRow,
    currentGroup,
    select,
    step,
    onSell,
    undoCopy,
    busyCopy,
    receipts,
    soldKeys,
    now,
  }
}

export type OrderWalk = ReturnType<typeof useOrderWalk>

/* ------------------------------------------------------------------------------ the walk list */

/** `BoxBrowse.tsx`'s own `.browse-list` / `.browse-group` / `.browse-row` shape, over the
 *  plan's rows instead of a box's cards. No tick is drawn on a row here: `BoxBrowse`'s own tick
 *  feeds a pipeline run scope (`./pkmnscan identify --box`), which has no meaning over a
 *  buyer's walk, and a checkbox with nothing to do is a control nobody can reach — see the
 *  report for the open question this leaves for the owner's word. */
export function WalkList({
  walk,
  hideSold,
}: {
  readonly walk: OrderWalk
  readonly hideSold: boolean
}) {
  if (walk.loading) {
    return (
      <div className="browse-empty">
        <span className="bn-skeleton" style={{ width: '100%', height: 64 }} />
      </div>
    )
  }
  if (walk.failure !== null) {
    return (
      <div className="browse-empty">
        <p className="bn-muted">{walk.failure.message}</p>
      </div>
    )
  }
  if (walk.sections.length === 0) {
    return (
      <div className="browse-empty">
        <p className="bn-muted">Nothing to walk. Every ticked order's copies are either already sold or nowhere on hand.</p>
      </div>
    )
  }
  return (
    <ul className="browse-list" aria-label="The cards this walk covers, in box-walk order">
      {walk.sections.map((section) => {
        const shown = hideSold ? section.rows.filter((row) => !walk.soldKeys.has(row.copy.key)) : section.rows
        if (shown.length === 0) return null
        return (
          <li className="browse-group" key={section.key}>
            <div className="browse-secthead">
              <span className="browse-sectfold" aria-hidden="true">
                <Icon name="chevronDown" size={14} className="browse-sectmark" />
                <span className="browse-secttitle">{section.title}</span>
                <span className="browse-sectcount">{shown.length}</span>
              </span>
            </div>
            <ul className="browse-group-rows">
              {shown.map((row) => {
                const sold = walk.soldKeys.has(row.copy.key)
                return (
                  <li className={sold ? 'browse-rowline is-departed' : 'browse-rowline'} key={row.rowKey}>
                    <button
                      className="browse-row"
                      type="button"
                      aria-current={row.rowKey === walk.current ? 'true' : undefined}
                      onClick={() => walk.select(row.rowKey)}
                    >
                      <span className="browse-row-position">
                        <span className="browse-row-slot">{row.copy.place.card === null ? '—' : `#${row.copy.place.card}`}</span>
                      </span>
                      <span className={row.take.name === null ? 'browse-row-name is-unnamed' : 'browse-row-name'}>
                        {row.take.name ?? row.take.sku}
                      </span>
                      {sold ? (
                        <span className="browse-row-badge is-out" aria-hidden="true">
                          <Icon name="check" size={12} />
                        </span>
                      ) : null}
                    </button>
                  </li>
                )
              })}
            </ul>
          </li>
        )
      })}
    </ul>
  )
}

/* -------------------------------------------------------------------------------- the main pane */

/** The action every row in the pane offers — `Mark sold`, an `Undo` inside its own window, or a
 *  `Sold` pill past it, the same three states `Inventory.tsx`'s own `Action` draws, restated
 *  because this screen's write is `WalkPullFn`/`WalkUndoFn` rather than `markSold`/`undoSale`. */
function RowAction({ walk, copy }: { readonly walk: OrderWalk; readonly copy: SearchCopy }) {
  const receipt = walk.receipts.get(copy.key)
  const busy = walk.busyCopy === copy.key
  if (receipt !== undefined) {
    const within = walk.now - receipt.at < UNDO_WINDOW_MS
    if (!within) return <Pill tone="ok" icon="check">Sold</Pill>
    return (
      <span className="inventory-copy-actions inventory-receipt" style={{ ['--receipt-ms' as string]: `${UNDO_WINDOW_MS}ms` }}>
        <span className="bn-receipt-bar" aria-hidden="true" />
        <Button
          size="sm"
          icon="undo"
          busy={busy}
          disabled={walk.busyCopy !== null && !busy}
          onClick={() => walk.undoCopy(copy.key)}
        >
          Undo
        </Button>
      </span>
    )
  }
  return (
    <Button size="sm" busy={busy} disabled={walk.busyCopy !== null && !busy} onClick={() => walk.onSell(copy)}>
      Mark sold
    </Button>
  )
}

/** `CardLocations`, over the current card's copies — inventory's own card pane, unadapted
 *  beyond `preserveOrder` (the trap this screen's brief names first): the walk's density order
 *  leads, this stop's own copies first, and a sale never re-sorts it. */
export function WalkMainPane({ walk }: { readonly walk: OrderWalk }) {
  const { currentRow, currentGroup } = walk

  if (currentGroup === null || currentRow === null) return null

  const take = currentRow.take
  const showPhoto = currentRow.copy.cid !== null

  return (
    <section className="bn-panel browse-card orders-walk-card">
      <div className="browse-hero-head">
        <div className="browse-hero-text">
          <h2 className={take.name === null ? 'browse-hero-name is-unnamed' : 'browse-hero-name'}>{take.name ?? 'Not identified yet'}</h2>
          <p className="browse-hero-sub">
            {[take.number_display, take.set].filter((part): part is string => Boolean(part)).map((part, i) => (
              <span key={`${part}-${i}`}>{part}</span>
            ))}
          </p>
          <div className="browse-hero-chips">
            {take.rarity === null ? null : <Pill>{take.rarity}</Pill>}
          </div>
        </div>
      </div>
      <div className="browse-band">
        <div className="browse-shot">
          <div className="orders-walk-photo">
            {showPhoto ? (
              <img
                src={photoUrl(currentRow.copy.place.box, currentRow.copy.place.index, currentRow.copy.cid)}
                alt={`The card ${take.name ?? take.sku}`}
              />
            ) : (
              <Icon name="image" size={28} />
            )}
          </div>
        </div>
        <div className="browse-under">
          <CardLocations
            persona="owner"
            group={currentGroup}
            currentKey={currentRow.copy.key}
            preserveOrder
            onSell={walk.onSell}
            busyKey={walk.busyCopy}
            soldKeys={walk.soldKeys}
            renderAction={(copy) => <RowAction walk={walk} copy={copy} />}
          />
        </div>
      </div>
    </section>
  )
}
