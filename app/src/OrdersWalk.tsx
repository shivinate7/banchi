/* app/src/OrdersWalk.tsx — `Walk the boxes`, over the solver's own plan (D212, D93, D97).
 *
 * `docs/specs/order-walk-plan.md` §8-9 is this file's brief. It replaces `WalkView`,
 * `WalkCards`, `buildWalkPlan`/`PlanStop`/`PlanCard` and `WalkPlan` (see `Orders.tsx`'s own
 * deletions) but leaves `buildWalk`/`buildCopyMap`/`WalkGroups` alone — `By buyer`'s merged
 * walk is a different job and keeps them (D193, D209).
 *
 * ONE STOP, ONE REACH (§8). A stop is a drawer to open; a take is one card ordered, with a
 * counter and every candidate copy beneath it — never one candidate, D93/D97 unamended. A
 * copy is one physical card in one slot, and it is the COPY that gets the photograph, the
 * position and the neighbours (Inventory.tsx's and Fulfillment.tsx's own register): a take's
 * copies are different physical cards even where they are the same printing, and only a
 * photograph of THIS slot proves what a hand would actually pick up there.
 *
 * THE WIRE IS PINNED, NOT MINE — `app/src/types.ts`'s `WalkPlan` and its parts, `app/src/
 * server.ts:walkPlan()`, section 7's own branch, merged in. Nothing here invents a field the
 * wire does not carry.
 *
 * WHAT THE WIRE DOES NOT CARRY, STATED RATHER THAN PAPERED OVER:
 *   - `WalkPlanStop` has no `box_total`, so the "where in the drawer" bar cannot be the
 *     proportional ruler `PositionBar` draws elsewhere (that needs the box's total count to
 *     size the track) — it is not a "reach for the kit" miss, `PositionBar` was tried first
 *     and needs a number this wire does not send. Drawn instead as the honest span numbers
 *     alone (`#242–284`), never a fabricated proportion. Flagged in this branch's report as
 *     worth a look if a true ruler is wanted here.
 *   - `WalkPlanCopy.neighbors` is always null as shipped (`types.ts`'s own comment: the
 *     server's `_Places.for_keys` scoping degrades it) — so the neighbour sentence this file
 *     builds via `placeParts` never actually renders yet. Left in rather than cut, because it
 *     costs nothing idle and draws the moment the route stops degrading it.
 *   - `WalkPlanTake.for` names which orders share a take but not how the demand at THIS stop
 *     splits between them when there is more than one. `pickOrderFor` below picks the first
 *     one still owing, tracked against what this pass has itself recorded — a rendering-side
 *     choice forced by completing the write, not a second demand computation. Also flagged.
 *
 * ORDERING IS THE ROUTE'S, NEVER RE-SORTED HERE (the owner's ruling, 2026-09-18): cards
 * (`stop.takes`) densest-first, copies (`take.copies`) front to back ascending slot. This file
 * renders both arrays exactly as sent and contains no `.sort()` over either.
 */

import { useEffect, useMemo, useRef, useState } from 'react'

import { Button, EmptyState, Icon, Pill } from './kit'
import { PositionLabel } from './PositionLabel'
import { describeFailure, photoUrl, placeParts, walkPlan } from './server'
import type { Failure } from './server'
import type {
  OrderRow,
  Place,
  PullTarget,
  WalkPlan,
  WalkPlanCopy,
  WalkPlanRef,
  WalkPlanShort,
  WalkPlanStop,
  WalkPlanTake,
} from './types'
import './OrdersWalk.css'

/** `Inventory.tsx`'s and `Fulfillment.tsx`'s own number, restated here for the same reason
 *  each of those restates it rather than importing one another's: a shared constant across
 *  files that do not otherwise depend on each other is one more coupling than the number is
 *  worth. */
const UNDO_WINDOW_MS = 20_000

export type WalkPullOutcome = { readonly ok: true; readonly place: string } | { readonly ok: false; readonly failure: Failure }

/** The walk's own pull — real data, not a `ResolvedLine`/`PickRow` built to satisfy a type
 *  the walk's shape does not fill honestly. `Orders.tsx`'s `onPull` stays the buyer-list
 *  path; this is `OrdersHub`'s sibling call for the same underlying write. */
export type WalkPullFn = (args: {
  readonly order: OrderRow
  readonly sku: string
  readonly name: string
  readonly target: PullTarget
  readonly place: string | null
}) => Promise<WalkPullOutcome>

export type WalkUndoFn = (target: PullTarget, place: string, name: string) => Promise<boolean>

/* ---- the copy's key, and the neighbour-sentence reuse -------------------------------------- */

function copyKeyOf(copy: WalkPlanCopy): string {
  return copy.capture_id ?? `${copy.box}/${copy.index}`
}

/** `server.ts:placeParts` reused for its neighbour sentence, and for nothing else on this
 *  object. `Place` carries fields this wire does not send at the copy level (`box_total`,
 *  `fraction`, …) — `placeParts` reads only `.located` and `.neighbors`, so the rest are
 *  filled with values that satisfy the type and are NEVER DRAWN. This is a shim for one
 *  function's own logic, not a second `Place`, and it must never reach `PositionBar`. */
function neighborShim(copy: WalkPlanCopy, stop: WalkPlanStop): Place {
  return {
    label: copy.label,
    located: true,
    box: copy.box,
    index: copy.index,
    slot: copy.slot,
    section: stop.section,
    card: copy.card,
    box_name: stop.box_name,
    section_name: stop.section_name ?? undefined,
    section_start: stop.span?.start ?? 0,
    section_end: stop.span?.end ?? null,
    box_total: 0, // unread by placeParts; never drawn from this object
    box_closed: true, // unread by placeParts; never drawn from this object
    fraction: null,
    neighbors: copy.neighbors ?? null,
  }
}

/* ---- who a press should be recorded against ------------------------------------------------ */

/** A take's `for` names every order sharing it but not how this stop's `wanted` splits between
 *  them (the wire has no per-order share — see the file header). The first order still owing,
 *  by the LIVE ledger figure minus what THIS PASS has itself recorded for it on this sku, is
 *  the least-wrong reading with no server input to do better: it never sends a press at an
 *  order the ledger already shows full, and two orders sharing a take are split in the order
 *  the plan already lists them. */
function pickOrderFor(
  take: WalkPlanTake,
  ordersByKey: ReadonlyMap<string, OrderRow>,
  recordedForSku: ReadonlyMap<string, number>,
): OrderRow | null {
  for (const ref of take.for) {
    const order = ordersByKey.get(ref.key)
    if (order === undefined) continue
    const liveOutstanding = Math.max(0, order.wanted - order.recorded)
    const already = recordedForSku.get(ref.key) ?? 0
    if (already < liveOutstanding) return order
  }
  return ordersByKey.get(take.for[0]?.key ?? '') ?? null
}

/* ---- per-row state, kept for the pass and never rebuilt from a re-read --------------------- */

type TakenCopy = { readonly key: string; readonly target: PullTarget; readonly place: string; readonly orderKey: string }

type RowState = {
  readonly taken: readonly TakenCopy[]
  readonly gone: ReadonlySet<string>
  /** `Take another` was pressed at least once — the row stays unlocked for the rest of the
   *  pass rather than re-locking after one extra pull, which is D118's OWN rule applied to
   *  itself: a control that disables again the instant it is used is a worse trap than one
   *  that stays put. */
  readonly overpull: boolean
  /** When `taken.length` first reached `wanted` — null before then and reset to null by an
   *  undo that drops it back under. Drives the 20s window and the auto-collapse. */
  readonly satisfiedAt: number | null
  /** Forced open after an auto-collapse, by the chevron or by `Take another`. */
  readonly reopened: boolean
}

const EMPTY_ROW: RowState = { taken: [], gone: new Set(), overpull: false, satisfiedAt: null, reopened: false }

function rowKeyOf(stop: WalkPlanStop, take: WalkPlanTake): string {
  return `${stop.key}/${take.sku}`
}

/* ============================================================================== a copy row */

function CopyRow({
  copy,
  stop,
  taken,
  gone,
  locked,
  busy,
  pressing,
  onPull,
}: {
  readonly copy: WalkPlanCopy
  readonly stop: WalkPlanStop
  readonly taken: TakenCopy | null
  readonly gone: boolean
  readonly locked: boolean
  readonly busy: string | null
  readonly pressing: boolean
  readonly onPull: () => void
}) {
  const [broken, setBroken] = useState(false)
  const parts = placeParts(neighborShim(copy, stop))
  const where = copy.label ?? `Box ${stop.box ?? '?'}`
  const key = copyKeyOf(copy)
  return (
    <li className="walkplan-copy" data-state={gone ? 'gone' : taken !== null ? 'taken' : 'open'} data-capture-id={copy.capture_id ?? undefined}>
      {broken || copy.cid === null ? (
        <div className="bn-photo walkplan-copy-photo walkplan-copy-photo-blank">
          <Icon name="image" size={22} />
        </div>
      ) : (
        <div className="bn-photo walkplan-copy-photo">
          <img src={photoUrl(copy.box, copy.index, copy.cid)} alt={`The card at ${where}`} onError={() => setBroken(true)} />
        </div>
      )}
      <div className="walkplan-copy-body">
        <PositionLabel
          label={copy.label ?? `box ${copy.box}, index ${copy.index}`}
          lead="slot"
          boxName={stop.box_name}
          sectionName={stop.section_name}
        />
        {parts === null ? null : <p className="walkplan-copy-neighbors">{parts.said}</p>}
      </div>
      {gone ? (
        <span className="walkplan-copy-gone">
          <Icon name="x" size={13} /> Gone — skip
        </span>
      ) : taken !== null ? (
        <span className="walkplan-copy-taken">
          <Icon name="check" size={13} /> Taken
        </span>
      ) : (
        <Button
          variant="primary"
          size="sm"
          icon="hand"
          className="walkplan-pull"
          data-capture-id={copy.capture_id ?? key}
          busy={pressing}
          disabled={locked || (busy !== null && !pressing)}
          onClick={onPull}
        >
          Pull
        </Button>
      )}
    </li>
  )
}

/* ============================================================================== a take (card) */

function TakeBlock({
  stop,
  take,
  row,
  ordersByKey,
  recordedForSku,
  showBuyer,
  busy,
  now,
  onPull,
  onUndo,
  onSetRow,
}: {
  readonly stop: WalkPlanStop
  readonly take: WalkPlanTake
  readonly row: RowState
  readonly ordersByKey: ReadonlyMap<string, OrderRow>
  readonly recordedForSku: ReadonlyMap<string, number>
  readonly showBuyer: boolean
  readonly busy: string | null
  readonly now: number
  readonly onPull: (target: PullTarget, name: string, place: string | null, order: OrderRow, copyKey: string) => void
  readonly onUndo: (copy: TakenCopy) => void
  readonly onSetRow: (next: RowState) => void
}) {
  const takenCount = row.taken.length
  const satisfied = takenCount >= take.wanted
  const withinUndo = row.satisfiedAt !== null && now - row.satisfiedAt < UNDO_WINDOW_MS
  const locked = satisfied && !row.overpull
  const collapsed = satisfied && !withinUndo && !row.reopened
  const takenByKey = useMemo(() => new Map(row.taken.map((t) => [t.key, t])), [row.taken])
  const buyers = useMemo(() => {
    const seen = new Map<string, WalkPlanRef>()
    for (const ref of take.for) seen.set(ref.key, ref)
    return [...seen.values()]
  }, [take.for])

  const lastTaken = row.taken[row.taken.length - 1] ?? null

  const reopen = () => onSetRow({ ...row, reopened: true })
  const takeAnother = () => onSetRow({ ...row, overpull: true, reopened: true })

  if (collapsed) {
    return (
      <div className="walkplan-take walkplan-take-collapsed">
        <button type="button" className="walkplan-take-summary" onClick={reopen} aria-expanded={false}>
          <Icon name="chevronDown" size={14} />
          <span className="walkplan-take-name">{take.name ?? take.sku}</span>
          <span className="walkplan-take-summary-count">
            {takenCount} taken{takenCount === take.wanted ? '' : ` of ${take.wanted}`}
          </span>
        </button>
      </div>
    )
  }

  return (
    <div className={`walkplan-take${satisfied ? ' walkplan-take-done' : ''}`}>
      <div className="walkplan-take-head">
        <span className="walkplan-take-name">{take.name ?? take.sku}</span>
        {take.number_display === null ? null : <span className="walkplan-take-number">{take.number_display}</span>}
        {!showBuyer ? null : <span className="walkplan-take-for">for {buyers.map((b) => b.buyer ?? b.number).join(', ')}</span>}
        <span className="walkplan-take-counter">
          <b>{takenCount}</b> of {take.wanted} taken
        </span>
      </div>

      {!satisfied ? null : (
        <div className="walkplan-take-done-row">
          <Icon name="check" size={15} />
          <span>{takenCount === take.wanted ? 'Taken.' : `Taken — ${takenCount - take.wanted} extra.`}</span>
          {!withinUndo || lastTaken === null ? null : (
            <button type="button" className="walkplan-take-undo" onClick={() => onUndo(lastTaken)}>
              <Icon name="undo" size={14} /> Undo
            </button>
          )}
          <button type="button" className="walkplan-take-again" onClick={takeAnother}>
            Take another
          </button>
        </div>
      )}

      <ol className="walkplan-copies">
        {take.copies.map((copy) => {
          const key = copyKeyOf(copy)
          const takenCopy = takenByKey.get(key) ?? null
          const gone = row.gone.has(key)
          const target: PullTarget | null = copy.capture_id === null ? null : { box: copy.box, index: copy.index, capture_id: copy.capture_id }
          const pressing = busy === `walk/${take.sku}/${copy.capture_id ?? key}`
          return (
            <CopyRow
              key={key}
              copy={copy}
              stop={stop}
              taken={takenCopy}
              gone={gone}
              locked={locked || target === null}
              busy={busy}
              pressing={pressing}
              onPull={() => {
                if (target === null) return
                const order = pickOrderFor(take, ordersByKey, recordedForSku)
                if (order === null) return
                onPull(target, take.name ?? take.sku, copy.label, order, key)
              }}
            />
          )
        })}
      </ol>
    </div>
  )
}

/* ============================================================================== a stop */

function StopBlock({
  stop,
  rows,
  ordersByKey,
  recorded,
  busy,
  now,
  onPull,
  onUndo,
  onSetRow,
}: {
  readonly stop: WalkPlanStop
  readonly rows: ReadonlyMap<string, RowState>
  readonly ordersByKey: ReadonlyMap<string, OrderRow>
  readonly recorded: ReadonlyMap<string, ReadonlyMap<string, number>>
  readonly busy: string | null
  readonly now: number
  readonly onPull: (rowKey: string, sku: string, target: PullTarget, name: string, place: string | null, order: OrderRow, copyKey: string) => void
  readonly onUndo: (rowKey: string, sku: string, copy: TakenCopy) => void
  readonly onSetRow: (rowKey: string, next: RowState) => void
}) {
  const totalWanted = stop.takes.reduce((sum, take) => sum + take.wanted, 0)
  const distinctBuyers = useMemo(() => {
    const seen = new Set<string>()
    for (const take of stop.takes) for (const ref of take.for) seen.add(ref.key)
    return seen.size
  }, [stop.takes])
  const openTitle = stop.pooled ? (stop.game_display ?? 'the pool') : (stop.box_name ?? `Box ${stop.box}`)

  return (
    <section className="bn-panel walkplan-stop" aria-label={openTitle}>
      <header className="walkplan-stop-head">
        <p className="walkplan-stop-instruction">
          Open {openTitle}. Take {totalWanted}.
        </p>
        {stop.pooled ? (
          <span className="walkplan-stop-pooled">
            <Icon name="layers" size={13} /> pooled · no position
          </span>
        ) : stop.span === null ? null : (
          <span className="walkplan-stop-span" title="Where in this drawer">
            <Icon name="grid" size={13} />
            {`#${stop.span.start}–${stop.span.end}`}
          </span>
        )}
      </header>
      {stop.takes.map((take) => {
        const rowKey = rowKeyOf(stop, take)
        return (
          <TakeBlock
            key={take.sku}
            stop={stop}
            take={take}
            row={rows.get(rowKey) ?? EMPTY_ROW}
            ordersByKey={ordersByKey}
            recordedForSku={recorded.get(take.sku) ?? new Map()}
            showBuyer={distinctBuyers > 1}
            busy={busy}
            now={now}
            onPull={(target, name, place, order, copyKey) => onPull(rowKey, take.sku, target, name, place, order, copyKey)}
            onUndo={(copy) => onUndo(rowKey, take.sku, copy)}
            onSetRow={(next) => onSetRow(rowKey, next)}
          />
        )
      })}
    </section>
  )
}

/* ============================================================================== the shortfall */

function ShortfallBlock({ rows }: { readonly rows: readonly WalkPlanShort[] }) {
  if (rows.length === 0) return null
  return (
    <section className="bn-panel walkplan-shortfall" aria-label="Cannot be filled from what is on hand">
      <header className="walkplan-shortfall-head">
        <Icon name="alert" size={15} />
        <span className="bn-section-title">Not on hand</span>
      </header>
      <ul className="walkplan-shortfall-list">
        {rows.map((row) => (
          <li key={row.sku} className="walkplan-shortfall-row">
            <span className="walkplan-shortfall-name">{row.name ?? row.sku}</span>
            <span className="walkplan-shortfall-figure">
              wants <b>{row.wanted}</b>, <b>{row.on_hand}</b> on hand — short <b>{row.short}</b>
            </span>
            <span className="walkplan-shortfall-for">{row.for.map((f) => f.buyer ?? f.number).join(', ')}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

/* ============================================================================== the pass */

/** THE PASS ITSELF, AND THE ONLY THING THIS FILE EXPORTS AS A VIEW.
 *
 *  `WalkSelect` and the `OrdersWalk` wrapper around it are GONE (§12). The selection is the
 *  buyer list on `#/orders` itself, so there is no second list to choose between and no
 *  wrapper left to choose with: `Orders.tsx` draws this component directly the moment
 *  `hub.walkKeys` is set, in the column beside that list.
 *
 *  `onEnd` is how a pass stops. Deleting the mode strip deleted the thing that used to end one
 *  (tapping `By buyer`), so the header below carries the replacement — the owner's ruling,
 *  2026-09-19. Leaving `#/orders` still ends it, through `Orders.tsx`'s own unmount cleanup. */
export function WalkPass({
  walkKeys,
  ordersByKey,
  busy,
  onPull,
  onUndo,
  onEnd,
}: {
  readonly walkKeys: ReadonlySet<string>
  readonly ordersByKey: ReadonlyMap<string, OrderRow>
  readonly busy: string | null
  readonly onPull: WalkPullFn
  readonly onUndo: WalkUndoFn
  readonly onEnd: () => void
}) {
  const keysSig = useMemo(() => [...walkKeys].sort().join('\u0000'), [walkKeys])
  const [plan, setPlan] = useState<WalkPlan | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [loading, setLoading] = useState(true)
  const live = useRef(true)
  const [rows, setRows] = useState<Map<string, RowState>>(new Map())
  /** How many copies THIS PASS has recorded, per sku then per order key — `pickOrderFor`'s
   *  only input beyond the live ledger figure. Reset with the plan: a new plan is a new pass. */
  const [recorded, setRecorded] = useState<Map<string, Map<string, number>>>(new Map())
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    live.current = true
    return () => {
      live.current = false
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    setFailure(null)
    setPlan(null)
    setRows(new Map())
    setRecorded(new Map())
    walkPlan([...walkKeys])
      .then((got) => {
        if (live.current) setPlan(got)
      })
      .catch((err) => {
        if (live.current) setFailure(describeFailure(err))
      })
      .finally(() => {
        if (live.current) setLoading(false)
      })
    // The plan is fetched ONCE per pass — `docs/specs/order-walk-plan.md` §8's "no Re-plan
    // control". `keysSig` is the pass's own identity; a re-render that leaves it unchanged
    // must never re-solve.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keysSig])

  /* Ticks twice a second, ONLY while some row is still inside its own undo window — an idle
     pass with everything either untouched or already collapsed pays for no timer at all. */
  const anyPending = useMemo(() => {
    for (const row of rows.values()) {
      if (row.satisfiedAt !== null && now - row.satisfiedAt < UNDO_WINDOW_MS) return true
    }
    return false
  }, [rows, now])
  useEffect(() => {
    if (!anyPending) return
    const id = window.setInterval(() => setNow(Date.now()), 500)
    return () => window.clearInterval(id)
  }, [anyPending])

  const setRow = (rowKey: string, next: RowState) => setRows((prev) => new Map(prev).set(rowKey, next))

  const pullOne = (rowKey: string, sku: string, target: PullTarget, name: string, place: string | null, order: OrderRow, copyKey: string) => {
    void (async () => {
      const result = await onPull({ order, sku, name, target, place })
      if (!live.current) return
      if (result.ok) {
        setRecorded((prev) => {
          const next = new Map(prev)
          const bySku = new Map(next.get(sku) ?? [])
          bySku.set(order.key, (bySku.get(order.key) ?? 0) + 1)
          next.set(sku, bySku)
          return next
        })
        setRows((prev) => {
          const current = prev.get(rowKey) ?? EMPTY_ROW
          const taken = [...current.taken, { key: copyKey, target, place: result.place, orderKey: order.key }]
          const next = new Map(prev)
          next.set(rowKey, { ...current, taken, satisfiedAt: current.satisfiedAt ?? Date.now() })
          return next
        })
      } else {
        const code = result.failure.code
        const isGone = code === 'copy_already_pulled' || code === 'pull_entry_refused' || code === 'card_not_found' || code === 'capture_id_mismatch'
        if (isGone) {
          setRows((prev) => {
            const current = prev.get(rowKey) ?? EMPTY_ROW
            const gone = new Set(current.gone)
            gone.add(copyKey)
            const next = new Map(prev)
            next.set(rowKey, { ...current, gone })
            return next
          })
        }
      }
    })()
  }

  const handleUndo = (rowKey: string, sku: string, copy: TakenCopy) => {
    void (async () => {
      const ok = await onUndo(copy.target, copy.place, rowKey)
      if (!live.current || !ok) return
      setRows((prev) => {
        const current = prev.get(rowKey)
        if (current === undefined) return prev
        const taken = current.taken.filter((t) => t.key !== copy.key)
        const next = new Map(prev)
        next.set(rowKey, { ...current, taken, satisfiedAt: taken.length > 0 ? current.satisfiedAt : null })
        return next
      })
      setRecorded((prev) => {
        const bySku = prev.get(sku)
        if (bySku === undefined) return prev
        const count = bySku.get(copy.orderKey)
        if (count === undefined) return prev
        const nextBySku = new Map(bySku)
        if (count <= 1) nextBySku.delete(copy.orderKey)
        else nextBySku.set(copy.orderKey, count - 1)
        const next = new Map(prev)
        next.set(sku, nextBySku)
        return next
      })
    })()
  }

  if (loading) {
    return (
      <div className="orders-stage orders-skeleton" aria-busy="true" aria-label="Building the walk">
        <span className="bn-skeleton orders-skel-line" />
        <span className="bn-skeleton orders-skel-card" />
        <span className="bn-skeleton orders-skel-card" />
      </div>
    )
  }

  if (failure !== null || plan === null) {
    return (
      <div className="bn-panel">
        <EmptyState
          icon="alert"
          title="The walk could not be planned"
          body={
            failure === null ? undefined : (
              <>
                {failure.message} <code className="bn-mono">{failure.code}</code>
              </>
            )
          }
        />
      </div>
    )
  }

  return (
    <div className="orders-walk walkplan">
      <header className="walkplan-head">
        <p className="walkplan-figure">
          <strong>{plan.counts.boxes}</strong> {plan.counts.boxes === 1 ? 'drawer' : 'drawers'}. <strong>{plan.counts.copies}</strong>{' '}
          {plan.counts.copies === 1 ? 'card' : 'cards'}.
        </p>
        {plan.counts.exact ? null : (
          <span title="The solver ran out of time before it could prove this is the fewest possible drawers.">
            <Pill size="sm" icon="info">
              A good plan, not proven best
            </Pill>
          </span>
        )}
        {/* THE ONE WAY OUT OF A PASS THAT IS NOT LEAVING THE SCREEN (§12, the owner's ruling
            2026-09-19). Nothing else ends a pass: not a filter, not a sort, not a tick, not
            clicking a buyer in the list beside this. It sits in the head rather than at the
            foot so it is reachable on a phone without scrolling the whole walk. */}
        <Button className="walkplan-end" icon="x" onClick={onEnd}>
          End walk
        </Button>
      </header>

      {plan.stops.length === 0 ? (
        <div className="bn-panel">
          <EmptyState icon="check" title="Nothing to walk" body="Every ticked order's copies are either already pulled or nowhere on hand." />
        </div>
      ) : (
        plan.stops.map((stop) => (
          <StopBlock
            key={stop.key}
            stop={stop}
            rows={rows}
            ordersByKey={ordersByKey}
            recorded={recorded}
            busy={busy}
            now={now}
            onPull={pullOne}
            onUndo={handleUndo}
            onSetRow={setRow}
          />
        ))
      )}

      <ShortfallBlock rows={plan.shortfall} />
    </div>
  )
}
