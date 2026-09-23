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

import { CardDetailsSection, CardHeroHead, marketTable, PhotoPanel, type MarketRead, type Row } from './CardHero'
import { CardLocations } from './CardLocations'
import { Overlay } from './InventoryOverlay'
import { Button, Icon, Pill } from './kit'
import { sectionCountOf, sectionCountWords, sectionTitleText, type SectionTitleParts } from './position'
import { SectionTitle } from './SectionTitle'
import { describeFailure, getPricing, photoUrl, walkPlan } from './server'
import type { Failure } from './server'
import type {
  InventoryCard,
  Listing,
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
 *  stop reads `Pooled: <game>`, same as `#/inventory`'s pooled shelf; a physical one leads
 *  with the box (the walk crosses boxes, which a single box's own section list never has to
 *  say) and then the section, exactly as `#/inventory` composes it. D218: the separators are
 *  punctuation in a real sentence, never a typed middle dot.
 *
 *  THE TITLE STATES THE SECTION'S OWN COUNT, NEVER THE STOP'S BOX-WIDE `span`. The rows under
 *  it read `#${place.card}`, the number WITHIN THE SECTION (`pipeline/join.py:Position.card`);
 *  `span` is `section_start`/`section_end`, counted across the whole box. `#54–#93` over a row
 *  reading `#37` is two rulers on one screen, the defect `sectionCountOf` already fixed on
 *  `#/inventory`. `place` is the section's first row's copy — a `here` copy, so it stands in
 *  this stop's box and section and carries the `box_closed` the stop itself does not. */
function stopTitle(stop: WalkPlanStop, place: Place): SectionTitleParts {
  if (stop.pooled) return { head: `Pooled: ${stop.game_display ?? 'cards'}`, count: null }
  const box = stop.box_name ?? (stop.box === null ? 'Box' : `Box ${stop.box}`)
  if (stop.section === null) return { head: box, count: null }
  const named = stop.section_name ? `Section ${stop.section}: ${stop.section_name}` : `Section ${stop.section}`
  return { head: `${box}, ${named}`, count: sectionCountWords(sectionCountOf(place)) }
}

export type WalkSection = { readonly key: string; readonly title: string; readonly parts: SectionTitleParts; readonly rows: readonly WalkRow[] }

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
    const parts: SectionTitleParts = stop === undefined ? { head: row.stopKey, count: null } : stopTitle(stop, row.copy.place)
    out.push({ key: row.stopKey, title: sectionTitleText(parts), parts, rows: [row] })
  }
  return out
}

/* ------------------------------------------------------------------ one receipt (a Mark sold) */

/** ONE PULL, RECORDED — no clock (`docs/specs/undo.md` §2-3, D164): a receipt names the write a
 *  copy's `Undo` would reverse, and `at` orders receipts against each other, never against a
 *  deadline. What ends a copy's OWN reversal is not this record aging out; it is a newer pull
 *  taking the "newest" rank away from it (below), or the walk itself resetting. */
type Receipt = { readonly at: number; readonly target: PullTarget; readonly place: string; readonly orderKey: string }

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
  rawCards,
  onPull,
  onUndo,
}: {
  readonly walkedKeys: ReadonlySet<string>
  readonly ordersByKey: ReadonlyMap<string, OrderRow>
  /** Every `InventoryCard` `Orders.tsx` has read, by `box/index` — the walk pane's own
   *  `CardHeroHead`/`CardDetailsSection` (§13: inventory's card pane, unchanged) read the
   *  CURRENT row's card off this map. */
  readonly rawCards: ReadonlyMap<string, InventoryCard>
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

  useEffect(() => {
    setFacts(new Map())
    setRecorded(new Map())
    setReceipts(new Map())
    setBusyCopy(null)
  }, [keysSig])

  const soldKeys = useMemo(() => new Set(receipts.keys()), [receipts])

  /** NO CLOCK (`docs/specs/undo.md` §3, D164): only the NEWEST pull this walk made stays
   *  undoable from its own row — the owner declined per-copy granularity here, so an older
   *  sold copy is drawn `Sold` and its way back is the card, on `#/inventory`'s departed row
   *  (§4), never a second Undo left standing beside it. A pull loses "newest" the instant a
   *  later one is recorded, not after any span of time. */
  const newestUndoKey = useMemo(() => {
    let key: string | null = null
    let latest = -Infinity
    for (const [candidate, receipt] of receipts) {
      if (receipt.at <= latest) continue
      latest = receipt.at
      key = candidate
    }
    return key
  }, [receipts])

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

  /** THE CURRENT CARD, WHOLE (§13: inventory's card pane, unchanged) — the real `InventoryCard`
   *  for the row the walk stands on, looked up by the copy's own (possibly refreshed) place,
   *  never by the take's synthesised `SearchGroup`, which carries only what the wire needs for
   *  the copies list and nothing an identity/claims/provenance panel would read. Null exactly
   *  when `Orders.tsx` has not read this card yet (`rawCards` covers every SKU any open order
   *  names, so this is only ever transiently null on a fresh plan). */
  const currentCard: InventoryCard | null = useMemo(() => {
    if (currentRow === null) return null
    const place = facts.get(currentRow.copy.key) ?? currentRow.copy.place
    return rawCards.get(`${place.box}/${place.index}`) ?? null
  }, [currentRow, facts, rawCards])

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
        setReceipts((prev) => new Map(prev).set(copy.key, { at: Date.now(), target, place: outcome.place, orderKey: order.key }))
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
    /* Only the newest pull is undoable from its own row (no clock, see `newestUndoKey` above).
       `RowAction` only ever wires this to the newest copy's own button, and this guard is the
       same rule enforced a second time, defensively, rather than trusted to the caller. */
    if (receipt === undefined || busyCopy !== null || copyKey !== newestUndoKey) return
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
    currentCard,
    select,
    step,
    onSell,
    undoCopy,
    busyCopy,
    receipts,
    soldKeys,
    newestUndoKey,
  }
}

export type OrderWalk = ReturnType<typeof useOrderWalk>

/* ------------------------------------------------------------------------------ the walk list */

/** `BoxBrowse.tsx`'s own `.browse-list` / `.browse-group` / `.browse-row` shape, over the
 *  plan's rows instead of a box's cards. NO TICK IS DRAWN ON A ROW HERE, on the owner's own
 *  word (§13): the ticks are on ORDERS, in the rail above ("hit ticks to the side so I can
 *  select multiple") — the mock carried a tick here only by fidelity to inventory's own
 *  markup, and a checkbox with nothing to do is worse than none. */
export function WalkList({
  walk,
  hideSold,
  collapsed = false,
}: {
  readonly walk: OrderWalk
  readonly hideSold: boolean
  /** S5 — folds every section's rows at once. No per-section state: the fold chevron in each
   *  section head stays decorative, as it always has, and this one flag hides every
   *  `.browse-group-rows` list rather than tracking which sections are individually open. */
  readonly collapsed?: boolean
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
                <Icon name={collapsed ? 'chevronRight' : 'chevronDown'} size={14} className="browse-sectmark" />
                <SectionTitle parts={section.parts} />
                <span className="browse-sectcount">{shown.length}</span>
              </span>
            </div>
            {collapsed ? null : (
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
            )}
          </li>
        )
      })}
    </ul>
  )
}

/* -------------------------------------------------------------------------------- the main pane */

/** The action every row in the pane offers — `Mark sold`, an `Undo` on the newest pull this walk
 *  made, or a `Sold` pill on an older one. NO CLOCK (`docs/specs/undo.md` §3, D164): the row that
 *  carries `Undo` is picked by RANK, not by a countdown — it is whichever sold copy is newest,
 *  and it stops being that the instant a later pull is recorded, never after any span of time.
 *  An older `Sold` copy's way back is the card, on `#/inventory`'s departed row (§4) — this pane
 *  offers only the one door the owner kept here. */
function RowAction({ walk, copy }: { readonly walk: OrderWalk; readonly copy: SearchCopy }) {
  const receipt = walk.receipts.get(copy.key)
  const busy = walk.busyCopy === copy.key
  if (receipt !== undefined) {
    if (copy.key !== walk.newestUndoKey) return <Pill tone="ok" icon="check">Sold</Pill>
    return (
      <span className="inventory-copy-actions inventory-receipt">
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
/** INVENTORY'S CARD PANE, UNCHANGED (§13) — the header, the pills, the photograph as
 *  `#/inventory` frames it (`PhotoPanel`, `CardHero.tsx`), "Every copy of this card"
 *  (`CardLocations`, `preserveOrder`), and `Details` (`CardDetailsSection`). Reused, not
 *  rebuilt: all three come off `CardHero.tsx`, the same file `BoxBrowse.tsx` reads them from.
 *
 *  LEFT OUT, BY NAME, AND ONLY BECAUSE THEY EDIT: `CardOps`'s menu (correct claims, retire,
 *  remove) and the re-shoot control. Both change a card's own record — identification,
 *  position, the stored photograph — which is Inventory's job and not a fulfillment walk's;
 *  neither is passed to `CardHeroHead` or `PhotoPanel` here.
 *
 *  `market` AND `listings` REACH `CardDetailsSection` THE SAME PATH `BoxBrowse.tsx` USES,
 *  COPIED RATHER THAN REINVENTED (the market-and-listings parity task, queued after D220 —
 *  the owner reversed D220's own "ships with its empty states" call). `listings` arrives from
 *  `Orders.tsx`, the free third face of the same `POST /inventory/copies` read that already
 *  answers `rawCards` — never a second fetch. `market` is a per-run cache, `BoxBrowse.tsx`'s
 *  own `priced`/`asked` pair restated here over `currentCard.run` instead of a selected box
 *  row's: a run is asked for AT MOST ONCE per mount, and never asked for at all when the
 *  current card has no run yet (`marketText` already draws "not joined yet" for that case, so
 *  asking would only spend a fetch on an answer this pane already knows). D62/D79 keep price
 *  TREND on the pricing screen — this wires the single reading and the live-listing fact only.
 *
 *  BEFORE `rawCards` HAS ANSWERED FOR THIS ROW (the first render of a freshly landed plan),
 *  there is no full `InventoryCard` yet — the synthesised take-level header stands in, off the
 *  same wire fields the old `TakeBlock` used, so the pane is never blank while the read
 *  catches up. `market`/`listings` are drawn only once a real card has landed (`row !== null`),
 *  same as `CardDetailsSection` itself. */
export function WalkMainPane({
  walk,
  phone,
  listings,
}: {
  readonly walk: OrderWalk
  readonly phone: boolean
  /** `Orders.tsx`'s own read — `POST /inventory/copies`' `listings`, narrowed server-side to
   *  the SKUs any open order names. */
  readonly listings: Readonly<Record<string, Listing>>
}) {
  const { currentRow, currentGroup, currentCard } = walk
  const [broken, setBroken] = useState(false)
  const [zoomed, setZoomed] = useState(false)
  useEffect(() => {
    setBroken(false)
    setZoomed(false)
  }, [currentRow?.copy.key])

  /* THE PER-RUN MARKET CACHE, COPIED FROM `BoxBrowse.tsx` (see this component's own docstring
   *  above). `pricedRun` is read off `currentCard` — the real `InventoryCard`, never the
   *  synthesised take — so a row with no `InventoryCard` yet asks for nothing rather than
   *  guessing. */
  const [priced, setPriced] = useState<Record<string, MarketRead>>({})
  const asked = useRef<Set<string>>(new Set())
  const pricedRun = currentCard?.run ?? null
  useEffect(() => {
    if (pricedRun === null) return
    if (asked.current.has(pricedRun)) return
    asked.current.add(pricedRun)
    let live = true
    getPricing(pricedRun)
      .then((payload) => {
        if (live) setPriced((held) => ({ ...held, [pricedRun]: marketTable(payload) }))
      })
      .catch((error: unknown) => {
        const why =
          describeFailure(error).code === 'pricing_not_written' ? 'join this run' : 'could not be read'
        if (live) setPriced((held) => ({ ...held, [pricedRun]: { kind: 'absent', why } }))
      })
    return () => {
      live = false
    }
  }, [pricedRun])

  if (currentGroup === null || currentRow === null) return null

  const take = currentRow.take
  const row: Row | null = currentCard === null ? null : { key: currentRow.copy.key, card: currentCard }

  return (
    <>
      <section className="bn-panel browse-card orders-walk-card">
      {row === null ? (
        <div className="browse-hero-head">
          <div className="browse-hero-text">
            <h2 className={take.name === null ? 'browse-hero-name is-unnamed' : 'browse-hero-name'}>{take.name ?? 'Not identified yet'}</h2>
            <p className="browse-hero-sub">
              {[take.number_display, take.set].filter((part): part is string => Boolean(part)).map((part, i) => (
                <span key={`${part}-${i}`}>{part}</span>
              ))}
            </p>
            <div className="browse-hero-chips">{take.rarity === null ? null : <Pill>{take.rarity}</Pill>}</div>
          </div>
        </div>
      ) : (
        <CardHeroHead card={row.card} game={row.card.place?.game_display ?? null} />
      )}
      <div className="browse-band">
        <div className="browse-shot">
          {row === null ? (
            <div className="orders-walk-photo">
              <Icon name="image" size={28} />
            </div>
          ) : (
            <PhotoPanel
              row={row}
              label={currentRow.copy.place.label}
              absent={broken}
              onAbsent={() => setBroken(true)}
              nonce={null}
              onZoom={() => setZoomed(true)}
              reshoot={null}
            />
          )}
        </div>
        <div className="browse-under">
          {/* THE VISIBLE DEFECT, FOUND RENDERING THIS PASS OVER THE DEMO STORE: without this
              wrapper, `CardLocations`' own row never opens the `copies` NAMED CONTAINER
              (`CardLocations.css`'s `@container copies (max-width: 619px)` — the narrow, place-
              spans-the-row template that keeps `BOX <name> Box <n>` on one line). No open
              container means the query cannot match at all, so the row fell through to the
              WIDE, side-by-side `'place state action'` template regardless of how much room it
              actually had — 236px of a 587px row at 1440, a third of what `#/inventory` gives
              the identical row (576px) — and the box's own name wrapped under `BOX 1` twice
              over before truncating. `Inventory.tsx`'s own `.inventory-detail` is the ONE place
              in the app that opens this container (`Inventory.css`); `OrdersWalkPane.tsx` reused
              its class rather than inventing a second name for the same contract, since its
              rules — `container-type: inline-size`, the flex chain that carries `.browse-band`'s
              fixed height down to a list that scrolls in it — are exactly what this pane needs
              too, and `./Inventory.css` was already imported here.

              THE SAME CHAIN'S SECOND LINK (the orders-followups task): `.inventory-detail`'s
              CSS reaches `.card-locations` only through `.inventory-copies > .card-locations
              { flex: 1 1 auto; min-height: 0 }` (`Inventory.css`). `CopiesPanel`
              (`Inventory.tsx`) always wraps `CardLocations` in
              `<section className="inventory-copies">`; this pane skipped that wrapper, so the
              rule never matched and `.card-locations` kept its block default (`min-height:
              auto`, sized to its own content) instead of shrinking to the band. Measured at
              1440 with 9 copies: the rows list grew to 1600px inside a 620px band, and
              `Details` — a child of THIS section, drawn right after `.browse-band` closed —
              sat at y=933, squarely inside the overflow (933-1913px), because the overflow
              paints past the band's own box while `Details` still lands in normal flow right
              after it. Adding the wrapper is the whole fix for the scroll: the list is what
              gives (D118), and it now does. */}
          <div className="inventory-detail">
            <section className="inventory-copies">
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
            </section>
          </div>
        </div>
      </div>
      </section>
      {/* `Details` MOVED HERE, A SIBLING OF THE SECTION RATHER THAN A CHILD OF IT — mirroring
          `BoxBrowse.tsx`'s own `</section>` / `<CardDetailsSection .../>` pair exactly (§13:
          this pane is inventory's card pane, reused whole). `.bn-panel`'s `overflow: hidden`
          was clipping hero, band and Details together to one box; the scroll fix above means
          that box no longer has to stretch to fit an overflowing list, but the DOM shape still
          owed inventory's own, one section shallower than this pane drew it. */}
      {row === null ? null : (
        <CardDetailsSection
          card={row.card}
          market={row.card.run === null ? undefined : priced[row.card.run]}
          listings={listings}
          phone={phone}
          // "Inventory only" — the owner's ruling on D-correct-a-listed-answer, now
          // `correctable`'s OWN default: an allow-list of one screen, so this call site needs
          // no flag at all. The walk here is a mode of inventory's own pane (§13), not
          // inventory itself, and omitting the prop IS the "no control" answer.
        />
      )}
      {!zoomed || row === null ? null : (
        <Overlay kind="lightbox" label="The photograph, full size" onClose={() => setZoomed(false)}>
          <img src={photoUrl(row.card.box, row.card.index, row.card.cid)} alt={`The card at ${currentRow.copy.place.label ?? row.key}`} />
        </Overlay>
      )}
    </>
  )
}
