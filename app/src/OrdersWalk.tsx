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
 * THE POSITIONAL FACTS ARE REAL, AND THEY REFRESH ON A PULL (§8's ruling of 2026-09-19).
 * `WalkPlanCopy` now carries the box's own `box_total`/`box_closed`/`fraction` and a real
 * `neighbors`, so `PositionBar` draws a ruler rather than its "a box the server could not
 * size" blank track and `PlaceNeighbors` draws the ladder. And because the solver packs a
 * pass into the fewest drawers, two cards at one stop are LIKELY to be physical neighbours:
 * pull the first and D58 renumbers the drawer behind it, so the second row's `#17` becomes
 * `#16` and its neighbour line names a card that has gone. `POST /orders/pull` answers
 * `refreshed` for the positions this screen names in `refresh`, POST-write, and `facts`
 * below is where they land.
 *
 * NOTHING RE-SOLVES AND NOTHING RE-RANKS. The plan is still fetched ONCE per pass and there
 * is still no `Re-plan` control. Which drawers, which cards, the stop order, the row order,
 * the copy order and the rule that packed sections rank higher are all frozen — what moves
 * is the DESCRIPTION of a card that is still the same card, at the same stop, in the same
 * place in the list. `facts` is a Map keyed by position and is never read for an ordering.
 *
 * WHAT THE WIRE STILL DOES NOT CARRY, STATED RATHER THAN PAPERED OVER:
 *   - `WalkPlanStop` has no `box_total`, so the stop's own "where in the drawer" chip cannot
 *     be the proportional ruler `PositionBar` draws elsewhere (that needs the box's total
 *     count to size the track) — it is not a "reach for the kit" miss, `PositionBar` was tried
 *     first and needs a number this wire does not send. Drawn instead as the honest span
 *     numbers alone (`#242–284`), never a fabricated proportion. The COPY now has the total;
 *     the STOP still does not, and the two are different questions.
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
import { PlaceNeighbors } from './PlaceNeighbors'
import { PositionBar } from './PositionBar'
import { describeFailure, photoUrl, walkPlan } from './server'
import type { Failure } from './server'
import type {
  OrderRow,
  Place,
  PullRefresh,
  PullTarget,
  WalkPlan,
  WalkPlanCopy,
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

export type WalkPullOutcome =
  | { readonly ok: true; readonly place: string; readonly refreshed: readonly Place[] }
  | { readonly ok: false; readonly failure: Failure }

export type WalkUndoOutcome =
  | { readonly ok: true; readonly refreshed: readonly Place[] }
  | { readonly ok: false }

/** The walk's own pull — real data, not a `ResolvedLine`/`PickRow` built to satisfy a type
 *  the walk's shape does not fill honestly. `Orders.tsx`'s `onPull` stays the buyer-list
 *  path; this is `OrdersHub`'s sibling call for the same underlying write.
 *
 *  `refresh` NAMES CARDS THIS PRESS IS NOT TOUCHING (§8's ruling of 2026-09-19) — the walk's
 *  other rows in the same drawer, whose numbers and neighbours the write is about to move
 *  (D58). It travels to `POST /orders/pull` and comes back as `refreshed`. */
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

/* ---- the copy's key, and the position/neighbour shim ---------------------------------------- */

function copyKeyOf(copy: WalkPlanCopy): string {
  return copy.capture_id ?? `${copy.box}/${copy.index}`
}

/** A position's key in `facts` — the STORE address (D58's `index`, not the slot a person
 *  counts to), because that is the one half of a card's identity a renumber cannot move. */
function factKeyOf(box: number, index: number): string {
  return `${box}/${index}`
}

/** `CopyRow`'s own `Place`, fed to BOTH `PositionBar` and `PlaceNeighbors` — the kit's own
 *  components, reused rather than a fourth hand-rolled rendering of a position.
 *
 *  THREE SOURCES, IN ONE ORDER, AND THE ORDER IS THE POINT.
 *
 *    `fresh`   the server's own post-write block for this position, when a pull in this
 *              drawer has since re-described it. It is a whole `Place` composed by the one
 *              renderer, so it is USED WHOLE rather than merged field by field — a merge
 *              would be this file deciding which half of a position to believe.
 *    the copy  the plan's own block, as fetched. Its `box_total`/`fraction`/`box_closed`
 *              are the box's real numbers since 2026-09-19, so `PositionBar` draws a ruler.
 *    the stop  the section the whole stop shares, for the two fields a copy does not carry.
 *
 *  `gone` BLANKS THE NEIGHBOURS AND NOTHING ELSE (§8). A copy the press found already pulled
 *  is not re-described by the server — nobody asked it to be — so the ladder it still holds
 *  names cards around a card that is no longer there. Blank is the honest answer, and the
 *  reserved height in `OrdersWalk.css` is why blanking moves nothing (D118). */
function placeOf(copy: WalkPlanCopy, stop: WalkPlanStop, fresh: Place | undefined, gone: boolean): Place {
  const base: Place =
    fresh ?? {
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
      box_total: copy.box_total,
      box_closed: copy.box_closed,
      fraction: copy.fraction,
      neighbors: copy.neighbors ?? null,
    }
  return gone ? { ...base, neighbors: null } : base
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
  fresh,
  taken,
  gone,
  locked,
  busy,
  pressing,
  onPull,
}: {
  readonly copy: WalkPlanCopy
  readonly stop: WalkPlanStop
  /** The server's own post-write block for this position, once a pull in this drawer has
   *  re-described it. Undefined until then — the plan's own block is what draws. */
  readonly fresh: Place | undefined
  readonly taken: TakenCopy | null
  readonly gone: boolean
  readonly locked: boolean
  readonly busy: string | null
  readonly pressing: boolean
  readonly onPull: () => void
}) {
  const [broken, setBroken] = useState(false)
  const where = copy.label ?? `Box ${stop.box ?? '?'}`
  const key = copyKeyOf(copy)
  /* THE STOP ALREADY NAMES THE DRAWER (§9a finding 1). Neither the box nor the section is drawn
   * again here as a labelled field — `PositionBar`'s own caption is the card's slot figure
   * alone, never `BOX <name>` / `SECTION <n>`. */
  const place = placeOf(copy, stop, fresh, gone)
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
        <PositionBar place={place} persona="owner" />
        {/* THE SLOT RESERVES THE LADDER'S TALLEST STATE (D118). Another row's press
            re-describes this one — a `skipped` line can appear, a side can lose its last
            named landmark, and a gone row blanks the block entirely — and not one of those
            may move the Pull button under it. The height is in `OrdersWalk.css`, derived
            from the ladder's own two line heights rather than guessed. */}
        <div className="walkplan-copy-neighbors">
          <PlaceNeighbors place={place} />
        </div>
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
  facts,
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
  /** Post-write position blocks, by `factKeyOf`. Read per copy and never for an order. */
  readonly facts: ReadonlyMap<string, Place>
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
  /* §9a finding 2: A NAME, NEVER THE ORDER'S OWN KEY OR NUMBER. `ref.number` is a machine
   *  string (`A2FFC195-0000F4-006AC`) and never stands in for a name a person did not give —
   *  an order with no buyer name on it is left out of the sentence rather than naming itself
   *  by its own key, the same refusal `PositionLabel`'s neighbour block makes for a card
   *  nobody has named (D116). */
  const buyerNames = useMemo(() => {
    const seen = new Map<string, string>()
    for (const ref of take.for) {
      const name = ref.buyer?.trim()
      if (name) seen.set(ref.key, name)
    }
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
        {!showBuyer || buyerNames.length === 0 ? null : <span className="walkplan-take-for">for {buyerNames.join(', ')}</span>}
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
              fresh={facts.get(factKeyOf(copy.box, copy.index))}
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
  facts,
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
  readonly facts: ReadonlyMap<string, Place>
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
            facts={facts}
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
  /** THE POSITIONAL FACTS A PULL HAS SINCE RE-DESCRIBED, by `factKeyOf` (§8's 2026-09-19
   *  ruling). Empty until the first press. It holds `Place` blocks the server composed AFTER
   *  its own write and is read ONLY by `CopyRow`, per copy — never by anything that decides
   *  which stop, which row or which copy comes first. Reset with the plan: a new plan is a
   *  new pass, and it arrives already current. */
  const [facts, setFacts] = useState<Map<string, Place>>(new Map())
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
    setFacts(new Map())
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

  /** THE CARDS THIS PRESS IS ABOUT TO MAKE STALE, AND NOT ONE IT IS TOUCHING.
   *
   *  Every copy in the plan that sits in the drawer `box` names, minus the one being pressed
   *  and minus the rows this pass has already finished with — a taken copy has left and a
   *  gone one was already claimed elsewhere, so neither is a card the screen is still telling
   *  somebody to count to. Scoped to the ONE box, because D58 renumbers the drawer that
   *  changed and no other, and a copy at another stop of the SAME box is in that drawer too.
   *
   *  It reads `plan` and `rows` and returns positions. It sorts nothing and decides nothing
   *  about order — the fence in this file's header. */
  const staleAfter = (box: number, pressedKey: string): PullRefresh[] => {
    if (plan === null) return []
    const out: PullRefresh[] = []
    const seen = new Set<string>()
    for (const stop of plan.stops) {
      for (const take of stop.takes) {
        const row = rows.get(rowKeyOf(stop, take)) ?? EMPTY_ROW
        const takenKeys = new Set(row.taken.map((t) => t.key))
        for (const copy of take.copies) {
          if (copy.box !== box) continue
          const key = copyKeyOf(copy)
          if (key === pressedKey || takenKeys.has(key) || row.gone.has(key)) continue
          const factKey = factKeyOf(copy.box, copy.index)
          if (seen.has(factKey)) continue
          seen.add(factKey)
          out.push({ box: copy.box, index: copy.index })
        }
      }
    }
    return out
  }

  /** The server's post-write blocks, folded in by position. A block for a position this pass
   *  is not drawing is simply never asked for, so nothing here filters. */
  const absorb = (blocks: readonly Place[]) => {
    if (blocks.length === 0) return
    setFacts((prev) => {
      const next = new Map(prev)
      for (const block of blocks) next.set(factKeyOf(block.box, block.index), block)
      return next
    })
  }

  const pullOne = (rowKey: string, sku: string, target: PullTarget, name: string, place: string | null, order: OrderRow, copyKey: string) => {
    void (async () => {
      const refresh = staleAfter(target.box, copyKey)
      const result = await onPull({ order, sku, name, target, place, refresh })
      if (!live.current) return
      if (result.ok) {
        absorb(result.refreshed)
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
      /* THE SAME LIST, THE OTHER WAY ROUND (§8). The copy returns to the drawer, so every
         card behind it takes its old number back (D58) and the rows still ahead need saying
         again. `copy.key` is excluded for the same reason it was on the way in: it is the
         card being written, not one being re-described. */
      const refresh = staleAfter(copy.target.box, copy.key)
      const result = await onUndo(copy.target, copy.place, rowKey, refresh)
      if (!live.current || !result.ok) return
      absorb(result.refreshed)
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
            facts={facts}
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
