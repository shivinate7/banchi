/* app/src/OrdersWalkPane.tsx — the walk: the cards to pick for the buyers walked, in the order
 * the boxes are walked (`docs/specs/order-walk-plan.md` §13), and the card pane beside it.
 *
 * THE WIRE IS UNCHANGED: `POST /orders/walk-plan` (`server.ts:walkPlan`), `WalkPlan` and its
 * parts, and the pull/undo write `Orders.tsx` already makes (`onWalkPull`/`onWalkUndo`,
 * `pullCopy`/`undoPull`). Nothing here edits `pipeline/walkplan.py`; which drawers, which
 * cards, and the density order are exactly what the solver already decided.
 *
 * A ROW IS A PICK COUNT (D212, D279, UX-198): one card in one section,
 * "Pick 1 of 2", never a list of chosen copies. The hook below still keeps one internal row per
 * copy of the solver's reach, because the press and its undo act on one physical copy; the list
 * folds them by take. `here` is the solver's own flag and this file does not recompute it.
 *
 * THE CARD PANE (UX-169) is the photograph, what the card is, and every copy of it with its place
 * and Mark sold, in the wire's own order (this stop's copies first, D212/D93/D97). Positions
 * patched from a pull's own post-write facts are folded into `facts` and never change which row
 * is first. The card's full inventory detail stays on `#/inventory`.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { marketTable, PhotoPanel, type MarketRead, type Row } from './CardHero'
import { forSale } from './cardState'
import { Dialog as Overlay } from './kit/overlay'
import { Icon, IconButton, Loading, Location, Money, Notice, Pill, ProductLink } from './kit'
import { sayPlace, sectionCountOf, sectionCountWords, sectionTitleText, type SectionTitleParts } from './position'
import { orderBuyerLabel } from './orderView'
import { SectionTitle } from './SectionTitle'
import { describeFailure, getPricing, photoUrl, walkPlan } from './server'
import type { Failure } from './server'
import type {
  InventoryCard,
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
  /* THE KEY SET WALKED NOW. An answer for any other set is dropped, whenever it lands: a stale
     answer drew another buyer's card with an active Mark sold (the re-review, round 3). */
  const currentSig = useRef(keysSig)
  currentSig.current = keysSig
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
    const asked = keysSig
    const current = () => live.current && currentSig.current === asked
    walkPlan([...walkedKeys])
      .then((got) => {
        if (current()) setPlan(got)
      })
      .catch((err) => {
        if (current()) setFailure(describeFailure(err))
      })
      .finally(() => {
        if (current()) setLoading(false)
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
    const { take } = row
    const order = pickOrderFor(take, ordersByKey, recorded.get(take.sku) ?? new Map())
    if (order === null) return
    const target: PullTarget | null = copy.capture_id === null ? null : { box: copy.place.box, index: copy.place.index, capture_id: copy.capture_id }
    if (target === null) return
    setBusyCopy(copy.key)
    void (async () => {
      const refresh = staleAfter(target.box, copy.key)
      const outcome = await onPull({
        order,
        sku: take.sku,
        name: take.name ?? take.sku,
        target,
        /* D218: `place` reaches a toast body as plain text (`onWalkPull`'s own receipt),
           never a component that splits it — sent through `sayPlace` here rather than left
           for the caller, since this is the one place the pre-write label crosses into text. */
        place: copy.place.label === null ? null : sayPlace(copy.place.label),
        refresh,
      })
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
        setReceipts((prev) => new Map(prev).set(copy.key, { at: Date.now(), target, place: outcome.place, orderKey: order.key }))
      }
      /* UN-6, REBUILT (`docs/specs/undo.md` §11.3, D57, D118): the walk no longer advances
         itself. The sold copy's own `RowAction` reads `receipts` fresh every render and turns
         into `Undo` in the exact row it was pressed from — nothing else on the pane is
         re-mounted, so no OTHER row's button can ever land under a repeated tap. The operator
         moves to the next card on their own press (J/K, or a row in the walk list), the same
         door every other screen's Undo leaves open. The earlier fix disabled the new card's
         button for `ADVANCE_GUARD_MS` after an automatic jump; the jump itself was the defect,
         so there is nothing left here to guard against. */
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

/** One card at one stop, as the walk draws it: every row of the solver's reach for that SKU at
 *  that stop, folded into one line. */
type WalkTakeLine = { readonly takeKey: string; readonly take: WalkPlanTake; readonly rows: readonly WalkRow[] }

function takeLinesOf(rows: readonly WalkRow[]): WalkTakeLine[] {
  const out: WalkTakeLine[] = []
  for (const row of rows) {
    const last = out[out.length - 1]
    if (last !== undefined && last.takeKey === row.takeKey) (last.rows as WalkRow[]).push(row)
    else out.push({ takeKey: row.takeKey, take: row.take, rows: [row] })
  }
  return out
}

/** Who a take is for, in words: the buyers' names, once each. */
export function takeBuyers(take: WalkPlanTake): string {
  const names: string[] = []
  for (const ref of take.for) {
    const name = orderBuyerLabel(ref)
    if (!names.includes(name)) names.push(name)
  }
  return names.join(', ')
}

/** THE WALK IS A PICK COUNT, NOT A LIST OF CHOSEN COPIES (D212, D279,
 *  UX-198). A row is one card in one section: where it is, what it is, how many to pick here of
 *  how many the walk's orders want, and, when the walk holds more than one buyer, for whom. The
 *  copies themselves, every one of them, are in the card pane beside it. No tick on a row: the
 *  ticks are on buyers (§13). */
export function WalkList({
  walk,
  hideSold,
  collapsed = false,
  owedBySku,
  showBuyers,
}: {
  readonly walk: OrderWalk
  readonly hideSold: boolean
  readonly collapsed?: boolean
  /** What the walked orders still want of each SKU, across every stop. The "of N". */
  readonly owedBySku: ReadonlyMap<string, number>
  readonly showBuyers: boolean
}) {
  if (walk.loading && walk.plan === null) {
    return (
      <Loading rows={4} label="Reading the walk" />
    )
  }
  if (walk.failure !== null) {
    return (
      <Notice tone="warn" title="Could not read where the copies are">
        Pick a buyer again, or reload the page.
      </Notice>
    )
  }
  if (walk.sections.length === 0) {
    return <p className="orders-walk-empty bn-muted">No copy of these cards is on hand.</p>
  }
  return (
    <ul className="orders-walk-list" aria-label="The cards to pick, in the order the boxes are walked">
      {walk.sections.map((section) => {
        const lines = takeLinesOf(section.rows)
        const pickedAll = (line: WalkTakeLine) =>
          line.rows.filter((row) => walk.soldKeys.has(row.copy.key)).length >= line.take.wanted
        const shown = hideSold ? lines.filter((line) => !pickedAll(line)) : lines
        if (shown.length === 0) return null
        return (
          <li className="orders-walk-group" key={section.key}>
            <div className="orders-walk-sect">
              <SectionTitle parts={section.parts} />
              <span className="orders-walk-sectcount">{shown.length}</span>
            </div>
            {collapsed ? null : (
              <ul className="orders-walk-rows">
                {shown.map((line) => {
                  const picked = line.rows.filter((row) => walk.soldKeys.has(row.copy.key)).length
                  const done = picked >= line.take.wanted
                  const of = Math.max(line.take.wanted, owedBySku.get(line.take.sku) ?? line.take.wanted)
                  const current = line.rows.some((row) => row.rowKey === walk.current)
                  const slots = line.rows.map((row) => row.copy.place.card).filter((card): card is number => card !== null)
                  const next = line.rows.find((row) => !walk.soldKeys.has(row.copy.key)) ?? line.rows[0]
                  return (
                    <li className={done ? 'orders-walk-line is-done' : 'orders-walk-line'} key={line.takeKey}>
                      <button
                        className="orders-walk-press"
                        type="button"
                        aria-current={current ? 'true' : undefined}
                        onClick={() => next !== undefined && walk.select(next.rowKey)}
                      >
                        <span className="orders-walk-slot">{slots.length === 0 ? '—' : slots.map((slot) => `#${slot}`).join(', ')}</span>
                        <span className={line.take.name === null ? 'orders-walk-name is-unnamed' : 'orders-walk-name'}>
                          {line.take.name ?? 'Not identified yet'}
                        </span>
                        <span className="orders-walk-pick">
                          {done ? <Icon name="check" size={14} /> : null}
                          {done ? 'Picked' : 'Pick'} {line.take.wanted} of {of}
                        </span>
                        {showBuyers ? <span className="orders-walk-for">{takeBuyers(line.take)}</span> : null}
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

/** The press on a copy row: an icon in every row (the iconography rule, a press repeated per
 *  row), its name carrying the place so thirty rows never announce the same word. `Undo` stands
 *  only on the newest sale (`newestUndoKey`). */
function RowAction({ walk, copy }: { readonly walk: OrderWalk; readonly copy: SearchCopy }) {
  const receipt = walk.receipts.get(copy.key)
  const busy = walk.busyCopy === copy.key
  const where = copy.place.label === null ? copy.key : sayPlace(copy.place.label)
  if (receipt !== undefined && copy.key !== walk.newestUndoKey) return <Pill tone="ok" icon="check">Sold</Pill>
  const undo = receipt !== undefined
  return (
    <IconButton
      icon={undo ? 'undo' : 'sold'}
      label={undo ? 'Undo' : 'Mark sold'}
      name={`${undo ? 'Undo' : 'Mark sold'}: ${where}`}
      busy={busy}
      disabled={walk.busyCopy !== null && !busy}
      onClick={() => (undo ? walk.undoCopy(copy.key) : walk.onSell(copy))}
    />
  )
}

/* ------------------------------------------------------------------------------ the card pane */

/** THE CARD THE WALK STANDS ON, AND WHERE EVERY COPY OF IT IS (UX-169). The photograph, what the
 *  card is, how many to pick, and one row per copy with its place and Mark sold: every copy, this
 *  stop's first, in the server's order (D212). The card's full inventory detail (stats, listing
 *  counts, the details table) is `#/inventory`'s, not this screen's. */
export function WalkCardPane({
  walk,
  owedBySku,
  showBuyers,
}: {
  readonly walk: OrderWalk
  readonly owedBySku: ReadonlyMap<string, number>
  readonly showBuyers: boolean
}) {
  const { currentRow, currentGroup, currentCard } = walk
  const [broken, setBroken] = useState(false)
  const [zoomed, setZoomed] = useState(false)
  useEffect(() => {
    setBroken(false)
    setZoomed(false)
  }, [currentRow?.copy.key])

  /* THE MARKET READING, ONE READ PER RUN (the owner's pick, 2026-09-24: B, one quiet line under
     the card). The same per-run cache the old pane kept. A failed read is a quiet dash. */
  const [priced, setPriced] = useState<Record<string, MarketRead>>({})
  const asked = useRef<Set<string>>(new Set())
  const pricedRun = currentCard?.run ?? null
  useEffect(() => {
    if (pricedRun === null || asked.current.has(pricedRun)) return
    asked.current.add(pricedRun)
    let live = true
    getPricing(pricedRun)
      .then((payload) => {
        if (live) setPriced((held) => ({ ...held, [pricedRun]: marketTable(payload) }))
      })
      .catch(() => {
        if (live) setPriced((held) => ({ ...held, [pricedRun]: { kind: 'absent', why: 'could not be read' } }))
      })
    return () => {
      live = false
    }
  }, [pricedRun])

  if (currentGroup === null || currentRow === null) return null
  const take = currentRow.take
  /* NEVER A PHOTOGRAPH OF A POOLED CARD: a code card's photo is a live code (D24, opsec). */
  const row: Row | null =
    currentCard === null || currentRow.copy.place.located === false ? null : { key: currentRow.copy.key, card: currentCard }
  const of =Math.max(take.wanted, owedBySku.get(take.sku) ?? take.wanted)
  const sub = [take.number_display, take.set].filter((part): part is string => Boolean(part))

  const here = currentGroup.copies.find((copy) => copy.key === currentRow.copy.key) ?? null
  const read = currentCard?.run == null ? undefined : priced[currentCard.run]
  const rawMarket = read?.kind === 'table' && currentCard !== null ? read.rows[`${currentCard.box}/${currentCard.index}`] : null
  const market = rawMarket === null || rawMarket === undefined || Number.isNaN(Number(rawMarket)) ? null : Number(rawMarket)
  const liveNow = take.listed === undefined ? null : forSale(take.listed.live, take.sold_here ?? 0)
  const hereWords = currentRow.copy.place.label === null ? null : sayPlace(currentRow.copy.place.label)

  return (
    <section className="orders-card-pane bn-panel" aria-label="The card to pick">
      <div className="orders-card-thin">
        <button
          type="button"
          className="orders-card-thumb"
          aria-label="Open the photograph"
          disabled={row === null}
          onClick={() => setZoomed(true)}
        >
          {row === null ? (
            <Icon name="image" size={18} />
          ) : (
            <img src={photoUrl(row.card.box, row.card.index, row.card.cid)} alt="" loading="lazy" />
          )}
        </button>
        <span className="orders-card-thin-text">
          <span className={take.name === null ? 'orders-card-thin-name is-unnamed' : 'orders-card-thin-name'}>
            {take.name ?? 'Not identified yet'}
          </span>
          <span className="orders-card-thin-place">
            {hereWords === null ? `Pick ${take.wanted} of ${of}` : `${hereWords}, pick ${take.wanted} of ${of}`}
          </span>
        </span>
        {here === null ? null : (
          <span className="orders-card-thin-action">
            <RowAction walk={walk} copy={here} />
          </span>
        )}
      </div>
      <div className="orders-card-top">
        <div className="orders-card-shot">
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
        <div className="orders-card-text">
          <h2 className={take.name === null ? 'orders-card-name is-unnamed' : 'orders-card-name'}>{take.name ?? 'Not identified yet'}</h2>
          {sub.length === 0 ? null : (
            <p className="orders-card-sub bn-facts">
              {sub.map((part, at) => (
                <span key={at}>{part}</span>
              ))}
            </p>
          )}
          <p className="orders-card-pick">
            Pick <strong>{take.wanted}</strong> of {of}
          </p>
          {showBuyers ? <p className="orders-card-for">For {takeBuyers(take)}</p> : null}
          <p className="orders-card-market">
            <ProductLink sku={take.sku} name={take.name ?? undefined}>
              {market === null ? '—' : <Money value={market} />} market, {liveNow === null ? '—' : liveNow} live
            </ProductLink>
          </p>
        </div>
      </div>
      <ul className="orders-card-copies" aria-label="Every copy of this card">
        {currentGroup.copies.map((copy) => {
          const here = copy.key === currentRow.copy.key
          return (
            <li className={here ? 'orders-card-copy is-current' : 'orders-card-copy'} key={copy.key} aria-current={here ? 'true' : undefined}>
              {copy.place.located === false ? (
                <span className="orders-card-place">Pooled: {copy.place.game_display ?? 'cards'}</span>
              ) : (
                <Location place={copy.place} className="orders-card-place" />
              )}
              <span className="orders-card-action">
                <RowAction walk={walk} copy={copy} />
              </span>
            </li>
          )
        })}
      </ul>
      {!zoomed || row === null ? null : (
        <Overlay kind="lightbox" label="The photograph, full size" onClose={() => setZoomed(false)}>
          <img
            src={photoUrl(row.card.box, row.card.index, row.card.cid)}
            alt={`The card at ${currentRow.copy.place.label === null ? row.key : sayPlace(currentRow.copy.place.label)}`}
          />
        </Overlay>
      )}
    </section>
  )
}
