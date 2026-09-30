/* app/src/OrdersWalkPane.tsx — the walk: the cards to pick for the buyers walked, in the order
 * the boxes are walked (`docs/specs/order-walk-plan.md` §13).
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
 * THE CARD PANE MOVED OUT (D304, lane A3): what
 * used to be `WalkCardPane` here is now `Orders.tsx`'s own use of `CardHero.tsx:CardPane` and
 * `CardLocations.tsx:CardLocations`, reused whole rather than forked — the walk-only pane and
 * its `orders-card-*` classes are deleted, not adapted. `pickFigureOf` and `RowAction` are
 * exported from here because `Orders.tsx` still needs them: the "Pick N of M" figure, and the
 * one press (Mark sold / Undo) `CardLocations`'s own `renderAction` slot calls per copy.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Icon, IconButton, Loading, Notice, Pill } from './kit'
import { toast } from './kit/toast'
import { sayPlace, sectionCountOf, sectionCountWords, sectionTitleText, type SectionTitleParts } from './position'
import { orderBuyerLabel } from './orderView'
import { SectionTitle } from './SectionTitle'
import { CardLocations, MarkSoldButton } from './CardLocations'
import { describeFailure, walkPlan } from './server'
import type { Failure } from './server'
import type {
  InventoryCard,
  OrderRow,
  Place,
  PullRefresh,
  PullTarget,
  SearchCopy,
  SearchGroup,
  SectionDetail,
  WalkPlan,
  WalkPlanCopy,
  WalkPlanStop,
  WalkPlanTake,
} from './types'

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

/** A take's `for` names every order sharing it, and `ref.owed` (from the plan's own snapshot,
 *  never re-read live) is what it still wants BEFORE this pass. The press goes to the ref
 *  whose remaining (`owed` minus what this pass has already recorded against it) is smallest
 *  and still positive — the fewest-remaining-first rule (owner's ruling 2026-09-25: "if we
 *  were to give it to someone, whoever it completes") — because the order closest to done is
 *  the one a single short copy is most likely to finish. Ties go to the order placed longest
 *  ago. AN ORDER WITH NOTHING LEFT OWED IS NEVER PICKED — no `for[0]` fallback
 *  (`docs/specs/order-walk-plan.md` §8): the caller who used to fall through to a
 *  full order now gets `null` and refuses the press before the server has to. */
function pickOrderFor(
  take: WalkPlanTake,
  ordersByKey: ReadonlyMap<string, OrderRow>,
  recordedForSku: ReadonlyMap<string, number>,
): OrderRow | null {
  let best: { order: OrderRow; remaining: number; placedAt: string } | null = null
  for (const ref of take.for) {
    const order = ordersByKey.get(ref.key)
    if (order === undefined) continue
    const remaining = ref.owed - (recordedForSku.get(ref.key) ?? 0)
    if (remaining <= 0) continue
    /* `\uFFFF` SORTS AFTER EVERY REAL TIMESTAMP, never before — `?? ''` was the review
       round's finding 4's second half: an empty string sorts BEFORE any real date, so an
       order with no `placed_at` read as the oldest possible order and won every tie it was
       in, which is backwards from "placed longest ago" (an unknown age is not a claim of
       great age). An order with no `placed_at` now loses every tie to one with a real date. */
    const placedAt = order.placed_at ?? '\uFFFF'
    if (
      best === null ||
      remaining < best.remaining ||
      (remaining === best.remaining && placedAt < best.placedAt)
    ) {
      best = { order, remaining, placedAt }
    }
  }
  return best === null ? null : best.order
}

/** What a row's "Pick X of Y" (or "Pick X" plus a short flag) should say.
 *
 *  `onHand` IS THE STORE-WIDE ON-HAND COUNT FOR THE SKU — `take.copies` already lists every
 *  on-hand copy, not only this stop's reach (D212/D93/D97), so its length is the true
 *  denominator. `owed` is the walked set's own demand (`owedBySku`, which excludes a
 *  stood-down line the same way the planner does). `Y` MUST NEVER COUNT A COPY THE STORE DOES
 *  NOT HAVE — the diagnosed defect (`docs/specs/order-walk-plan.md` §8): Rengar's "of
 *  8" implied 7 more copies waited elsewhere, and none did. Where `owed` outruns `onHand`,
 *  `of` is capped at what is really here and `short` carries the gap, so the row can say "7
 *  short" instead of a wrong count (the owner's wording ruling, 2026-09-25: "say what's short
 *  but it's not intuitive to use so much verbiage"). */
export function pickFigureOf(
  take: WalkPlanTake,
  owedBySku: ReadonlyMap<string, number>,
): { readonly of: number; readonly short: number } {
  const onHand = take.copies.length
  const owed = Math.max(take.wanted, owedBySku.get(take.sku) ?? take.wanted)
  return { of: Math.min(owed, onHand), short: Math.max(0, owed - onHand) }
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
 *  this stop's box and section. */
function stopTitle(stop: WalkPlanStop, place: Place): SectionTitleParts {
  if (stop.pooled) return { head: `Pooled: ${stop.game_display ?? 'cards'}`, count: null }
  const box = stop.box_name ?? ''
  if (stop.section === null) return { head: box, count: null }
  const named = stop.section_name ? `Section ${stop.section}: ${stop.section_name}` : `Section ${stop.section}`
  return { head: box ? `${box}, ${named}` : named, count: sectionCountWords(sectionCountOf(place)) }
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

/** `Inventory.tsx`'s own `loneGroup` and the old `TakeBlock`'s `group`, restated: a
 *  `SearchGroup` synthesised from one take's wire fields, over WHICHEVER copies the caller
 *  hands it — every on-hand copy for the pane's own `currentGroup`, or just this stop's `here`
 *  copies for one `WalkList` line (A4) — in the WIRE's own order, never re-sorted here, and
 *  drawn with `preserveOrder` below so `CardLocations` never re-sorts it either. `on_hand`
 *  stays the take's TRUE store-wide count regardless of which subset `copies` draws, because a
 *  line's own group still answers "how many are there", not "how many are here".
 *  `facts` OVERLAYS A COPY'S REFRESHED PLACE (D58's renumbering after a sale elsewhere in the
 *  same box) — the same map both callers share, off the one hook. */
function groupOf(take: WalkPlanTake, copies: readonly WalkPlanCopy[], facts: ReadonlyMap<string, Place>): SearchGroup {
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
    listed: take.listed ?? { pushed: 0, staged: 0, live: 0 },
    sold_here: take.sold_here ?? 0,
    on_hand: take.copies.length,
    listable: 0,
    live_as_of: take.live_as_of ?? null,
    // NEVER READ HERE. A synthesised group, one take and never ranked against another.
    rank: 0,
    copies: copies.map((copy): SearchCopy => {
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
}

/* ------------------------------------------------------------------ one receipt (a Mark sold) */

/** ONE PULL, RECORDED — no clock (`docs/specs/undo.md` §2-3, D164): a receipt names the write a
 *  copy's `Undo` would reverse, and `at` orders receipts against each other, never against a
 *  deadline. What ends a copy's OWN reversal is not this record aging out; it is a newer pull
 *  taking the "newest" rank away from it (below), or the walk itself resetting. */
type Receipt = { readonly at: number; readonly target: PullTarget; readonly place: string; readonly orderKey: string; readonly sku: string }

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
    return groupOf(currentRow.take, currentRow.take.copies, facts)
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

  const onSell = (copy: SearchCopy, forTake?: WalkPlanTake) => {
    if (busyCopy !== null) return
    /* THE CARD PANE OFFERS MARK SOLD ON EVERY COPY OF THE TAKE, D212's own copies list — not
       only the ones physically AT this stop (`here: true`). `rows` flattens only the `here`
       copies, one per physical reach, so looking THIS press up in `rows` by the pressed
       copy's own key silently dropped a press on any other copy (the review round's finding
       5, D171 again): no request, no toast, nothing. `currentRow` is the take the pane is
       standing on regardless of which of its copies was pressed, and every copy the pane
       draws a button for belongs to that one take (`currentGroup.copies` is `take.copies`
       whole) — so it is the right anchor for every press the PANE makes.

       A4 ADDS A SECOND CALLER: `WalkList`'s own rows, one per take, drawn beside the pane
       rather than only inside it. A row there can belong to a DIFFERENT take than the one the
       pane happens to be showing, so `currentRow.take` is the wrong anchor for it — `forTake`
       is how that caller names its own take explicitly. Omitted, the pane's own behaviour is
       unchanged. */
    const take = forTake ?? currentRow?.take
    if (take === undefined) return
    const order = pickOrderFor(take, ordersByKey, recorded.get(take.sku) ?? new Map())
    if (order === null) {
      /* D171: a refusal that reaches nobody did not happen. This pass's own tally may be
         stale (an undo made elsewhere, not yet synced here) or the plan may simply be behind
         a snapshot the store has already moved past — either way the operator pressed
         something and nothing may silently happen in response. */
      toast({
        kind: 'refusal',
        title: 'Nobody here still owes a copy',
        body: `${take.name ?? take.sku}: no order in this walk needs another one. Reload the walk to check.`,
      })
      return
    }
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
        /* UN-6's rebuild deletes the walk's own auto-advance (below), so the per-stop
           `satisfied` tally walk-fix computed here (finding 4: `take` is THIS STOP's own
           instance, never summed store-wide) has no `advanceAfter` left to feed. `sku` on
           the receipt stays: `undoCopy`/`noteExternalUndo` read it to lower the right tally. */
        setReceipts((prev) => new Map(prev).set(copy.key, { at: Date.now(), target, place: outcome.place, orderKey: order.key, sku: take.sku }))
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

  /** Lower this pass's own tally by one copy against `orderKey`/`sku` — the state half of an
   *  undo, shared by the row's own inline Undo (`undoCopy`, below) and an undo that happened
   *  OUTSIDE this hook (`noteExternalUndo`): a toast's own Undo or the `U` key, which write
   *  through `Orders.tsx:undoFromToast` and never touch this hook at all. Before this shared
   *  helper existed, only `undoCopy` lowered the tally, so a toast/`U` undo mid-walk left this
   *  pass believing a copy was still recorded that the ledger no longer held — `pickOrderFor`
   *  then returned `null` for an order that still owed one, and the next press did nothing
   *  and said nothing (the review round's finding 2, D171). */
  const lowerTally = (sku: string, orderKey: string) => {
    setRecorded((prev) => {
      const bySku = prev.get(sku)
      if (bySku === undefined) return prev
      const count = bySku.get(orderKey)
      if (count === undefined) return prev
      const nextBySku = new Map(bySku)
      if (count <= 1) nextBySku.delete(orderKey)
      else nextBySku.set(orderKey, count - 1)
      const next = new Map(prev)
      next.set(sku, nextBySku)
      return next
    })
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
        lowerTally(receipt.sku, receipt.orderKey)
      }
      setBusyCopy(null)
    })()
  }

  /** THE OTHER UNDO PATH — a toast's own Undo (`docs/specs/undo.md` §3) or the `U` key,
   *  neither of which goes through `undoCopy` above. Both write through
   *  `Orders.tsx:undoFromToast`, which calls the server directly and has no reason to know
   *  this hook exists. `Orders.tsx` calls this instead, once that write succeeds, keyed off
   *  the SAME `PullTarget` the toast already carries — never off `rows`, which may already be
   *  behind a re-plan. A copy this pass never recorded (an undo of a pull made outside the
   *  walk entirely) is a no-op: `receipts` holds nothing for it. */
  const noteExternalUndo = (target: PullTarget) => {
    const copyKey = `${target.box}/${target.index}`
    const receipt = receipts.get(copyKey)
    if (receipt === undefined) return
    setReceipts((prev) => {
      const next = new Map(prev)
      next.delete(copyKey)
      return next
    })
    lowerTally(receipt.sku, receipt.orderKey)
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
    noteExternalUndo,
    busyCopy,
    receipts,
    soldKeys,
    newestUndoKey,
    /** THE REFRESHED PLACES (A4), so `WalkList`'s own per-line groups can read the same
     *  post-sale facts the pane already does — `groupOf`'s own overlay, shared rather than
     *  copied. */
    facts,
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

/** Every copy the wanted count is asking for has a receipt against it. Shared by the press's
 *  own snapshot (below) and each line's `is-done` styling — one formula, not two. */
function pickedAllOf(line: WalkTakeLine, soldKeys: ReadonlySet<string>): boolean {
  return line.rows.filter((row) => soldKeys.has(row.copy.key)).length >= line.take.wanted
}

/** Every take key across every section, flat — what a press of Hide picked snapshots. */
function allTakeLinesOf(sections: readonly WalkSection[]): WalkTakeLine[] {
  return sections.flatMap((section) => takeLinesOf(section.rows))
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
  sections,
  onPick,
}: {
  readonly walk: OrderWalk
  readonly hideSold: boolean
  readonly collapsed?: boolean
  /** What the walked orders still want of each SKU, across every stop. The "of N". */
  readonly owedBySku: ReadonlyMap<string, number>
  readonly showBuyers: boolean
  /** Each box's own divider layout (A4), the SAME one `getBoxes()` read `Orders.tsx` already
   *  turns into a map for the pane's own `CardLocations` — never a second read for the walk
   *  list's copies. Optional; the strip is honest without it (`PositionBar`'s own contract). */
  readonly sections?: ReadonlyMap<number, readonly SectionDetail[]>
  /** LANE A5, Q4: on a phone, a tap opens the card in a sheet. `Orders.tsx` passes this only
   *  while its own column reads narrow — `WalkList` never reads a width itself. Undefined at a
   *  desk width, where the pane sits beside the walk already and needs no sheet to open. */
  readonly onPick?: () => void
}) {
  /* THE OWNER'S RULING, 2026-09-27: THE PRESS FOLDS, NOT THE SALE. Turning Hide picked ON is
   * itself allowed to fold every row picked SO FAR, right then — D118 permits this, because
   * the fold is the PRESS's own result, not a side effect of some other action. A sale made
   * while it is already on stays drawn, marked sold, until the NEXT press (off then on again
   * re-snapshots) or the walk's own next load (a fresh plan) — D263 ruling 2, unchanged from
   * this file's earlier fix. This is `BoxBrowse.tsx`'s `enteredLive` shape, ported again: a
   * snapshot taken at one deliberate moment, held fixed until that moment repeats, never
   * recomputed on every render — which is what made the previous `planTakeKeys` a tautology
   * (it recomputed from the very data it was meant to hold still against). */
  const [foldedKeys, setFoldedKeys] = useState<ReadonlySet<string>>(new Set())
  const wasHiding = useRef(hideSold)
  const planRef = useRef(walk.plan)
  useEffect(() => {
    if (walk.plan !== planRef.current) {
      planRef.current = walk.plan
      setFoldedKeys(new Set())
    } else if (hideSold && !wasHiding.current) {
      const picked = new Set<string>()
      for (const line of allTakeLinesOf(walk.sections)) {
        if (pickedAllOf(line, walk.soldKeys)) picked.add(line.takeKey)
      }
      setFoldedKeys(picked)
    }
    wasHiding.current = hideSold
  }, [hideSold, walk.plan, walk.sections, walk.soldKeys])

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
        const shown = hideSold ? lines.filter((line) => !foldedKeys.has(line.takeKey)) : lines
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
                  const figure = pickFigureOf(line.take, owedBySku)
                  const current = line.rows.some((row) => row.rowKey === walk.current)
                  const slots = line.rows.map((row) => row.copy.place.card).filter((card): card is number => card !== null)
                  const next = line.rows.find((row) => !walk.soldKeys.has(row.copy.key)) ?? line.rows[0]
                  return (
                    <li className={done ? 'orders-walk-line is-done' : 'orders-walk-line'} key={line.takeKey}>
                      <button
                        className="orders-walk-press"
                        type="button"
                        aria-current={current ? 'true' : undefined}
                        onClick={() => {
                          if (next === undefined) return
                          walk.select(next.rowKey)
                          onPick?.()
                        }}
                      >
                        <span className="orders-walk-slot">
                          {slots.length === 0 ? '—' : slots.map((slot) => `#${slot}`).join(', ')}
                          {/* MORE CANDIDATES HERE THAN THE TAKE WANTS: every copy is fungible
                           * (D212), so listing two card numbers for a "Pick 1" read as "take
                           * both" (review, finding 2 — Allen's #61/#62 row named neither copy
                           * as the one to pull). Saying so, tersely, is the fix the wording
                           * ruling asks for over a full explanation. */}
                          {slots.length > line.take.wanted ? <span className="orders-walk-slot-either"> (either)</span> : null}
                        </span>
                        <span className={line.take.name === null ? 'orders-walk-name is-unnamed' : 'orders-walk-name'}>
                          {line.take.name ?? 'Not identified yet'}
                        </span>
                        <span className="orders-walk-pick">
                          {done ? <Icon name="check" size={14} /> : null}
                          {done ? 'Picked' : 'Pick'} {line.take.wanted}
                          {figure.short > 0 ? null : ` of ${figure.of}`}
                          {figure.short > 0 ? (
                            <>
                              {' '}
                              <Pill tone="warn">{figure.short} short</Pill>
                            </>
                          ) : null}
                        </span>
                        {showBuyers ? <span className="orders-walk-for">{takeBuyers(line.take)}</span> : null}
                      </button>
                      {/* A4: EVERY here-COPY, AS INVENTORY DRAWS IT (the owner's Q3, "full
                       * detail on every row") — box, section and card, the neighbours, the
                       * strip and the ruler, and Mark sold, reused whole from `CardLocations`
                       * rather than forked (D304).
                       * `head={false}` draws the rows alone: the heading, the stats and the SKU
                       * line already sit above, in this same button. FINDING #16 (the Opus
                       * review round) is answered by THIS, not by a row-level Undo of its own
                       * any more — `renderAction` puts `RowAction` on every copy here exactly as
                       * it sits in the pane, so the struck-out copy's own Undo is drawn right
                       * where the copy is, never only in the pane above. */}
                      <CardLocations
                        group={groupOf(line.take, line.rows.map((row) => row.copy), walk.facts)}
                        persona="owner"
                        onSell={walk.onSell}
                        busyKey={walk.busyCopy}
                        soldKeys={walk.soldKeys}
                        sections={sections}
                        currentKey={walk.currentRow?.copy.key}
                        preserveOrder
                        head={false}
                        className="walk-pick-where"
                        renderAction={(copy) => <RowAction walk={walk} copy={copy} take={line.take} />}
                      />
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
 *  only on the newest sale (`newestUndoKey`). `take` names which take this copy is being sold
 *  against (A4): the pane omits it, since `onSell` falls back to the row it is showing, but a
 *  `WalkList` row names its own take explicitly — it may not be the one the pane is on. */
export function RowAction({ walk, copy, take }: { readonly walk: OrderWalk; readonly copy: SearchCopy; readonly take?: WalkPlanTake }) {
  const receipt = walk.receipts.get(copy.key)
  const busy = walk.busyCopy === copy.key
  const where = copy.place.label === null ? copy.key : sayPlace(copy.place.label)
  if (receipt !== undefined && copy.key !== walk.newestUndoKey) return <Pill tone="ok" icon="check">Sold</Pill>
  const undo = receipt !== undefined
  /* MARK SOLD IS INVENTORY'S OWN PRESS (`CardLocations.tsx:MarkSoldButton`), so a change to it
     reaches the walk with no second edit. Undo is the icon it always was. */
  if (!undo) {
    return (
      <MarkSoldButton
        name={`Mark sold: ${where}`}
        busy={busy}
        disabled={walk.busyCopy !== null && !busy}
        onClick={() => walk.onSell(copy, take)}
      />
    )
  }
  return (
    <IconButton
      icon="undo"
      label="Undo"
      name={`Undo: ${where}`}
      busy={busy}
      disabled={walk.busyCopy !== null && !busy}
      onClick={() => walk.undoCopy(copy.key)}
    />
  )
}
