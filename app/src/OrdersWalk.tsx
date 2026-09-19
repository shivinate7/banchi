/* app/src/OrdersWalk.tsx — `Walk the boxes`, over the solver's own plan (D212, D93, D97).
 *
 * `docs/specs/order-walk-plan.md` §8-9, and its "The stop, rebuilt" ruling of 2026-09-19, are
 * this file's brief. It replaces `WalkView`, `WalkCards`, `buildWalkPlan`/`PlanStop`/`PlanCard`
 * and `WalkPlan` (see `Orders.tsx`'s own deletions) but leaves `buildWalk`/`buildCopyMap`/
 * `WalkGroups` alone — `By buyer`'s merged walk is a different job and keeps them (D193, D209).
 *
 * ONE STOP, ONE REACH (§8). A stop is a drawer to open; a take is one card ordered, with a
 * counter and every on-hand copy of it IN THE WHOLE STORE beneath it, this stop's own copies
 * leading (D93/D97, widened by D212).
 *
 * THE ROW IS `CardLocations`'s OWN OWNER-DENSE ROW, REUSED, NOT REBUILT. The first build of
 * this screen hand-rolled a row — a 220px photograph on every COPY, so two copies of one card
 * drew the same photograph twice, and only the copies the solver chose at this stop, so the
 * operator could not see where the rest of the card's copies were. Three independent reviews
 * reached one cause: `#/inventory`'s copies panel (`CardLocations`, D93's "picker") already IS
 * this row. This file now assembles a `SearchGroup` per take — exactly the synthesis
 * `Inventory.tsx`'s `loneGroup` and `Fulfillment.tsx`'s per-card slice already do — and hands
 * it to `CardLocations` with `preserveOrder` and `hideHeader` (both added to that file for this
 * reuse; see its own header). Pull reaches the server through `renderAction`, the same hook
 * `#/inventory` uses to draw its own undo.
 *
 * THE PHOTOGRAPH BELONGS TO THE CARD, ONCE, AT THE TAKE HEADER — 76×106, every width. Every
 * copy under a take is the same card; `CardLocations` draws none per row (this reuse never asks
 * it to).
 *
 * THE WIRE IS PINNED, NOT MINE — `app/src/types.ts`'s `WalkPlan` and its parts, `app/src/
 * server.ts:walkPlan()`. `WalkPlanCopy` carries a full `place: Place` now (the same block
 * `SearchCopy.place` carries) and nothing flat — `box`/`index`/`slot`/`card`/`label`/
 * `neighbors`/`box_total`/`box_closed`/`fraction` are GONE from it. The old `neighborShim`/
 * `placeOf` composition this file used to carry is deleted with them: the wire already sends
 * the assembled block.
 *
 * `WalkPlanTake.copies` IS EVERY ON-HAND COPY OF THE SKU IN THE STORE (D212, D93, D97), not
 * only this stop's picks — this stop's own copies first, then every other ascending (box,
 * index). ORDERING IS THE ROUTE'S, NEVER RE-SORTED HERE: `CardLocations`'s own re-rank by
 * fullest section is bypassed by `preserveOrder`, and this file's own map over `take.copies`
 * contains no `.sort()`.
 *
 * THE POSITIONAL FACTS ARE REAL, AND THEY REFRESH ON A PULL (§8's ruling of 2026-09-19).
 * Because the solver packs a pass into the fewest drawers, two cards at one stop are LIKELY to
 * be physical neighbours: pull the first and D58 renumbers the drawer behind it, so the second
 * row's `#17` becomes `#16` and its neighbour line names a card that has gone. `POST
 * /orders/pull` answers `refreshed` for the positions this screen names in `refresh`,
 * POST-write, and `facts` below is where they land — folded into a copy's own `place` before it
 * ever reaches `CardLocations`, which reads `place` and nothing else.
 *
 * NOTHING RE-SOLVES AND NOTHING RE-RANKS. The plan is still fetched ONCE per pass and there is
 * still no `Re-plan` control. Which drawers, which cards, the stop order, the row order, the
 * copy order and the rule that packed sections rank higher are all frozen — what moves is the
 * DESCRIPTION of a card that is still the same card, at the same stop, in the same place in the
 * list. `facts` is a Map keyed by a copy's own `key` and is never read for an ordering.
 *
 * A PULLED COPY COLLAPSES TO ONE LINE (§8's ruling): "a card in the hand has no position...
 * that is the whole of what it draws." `CardLocations`'s own `rowOverride` (added for this
 * reuse) replaces that one row's usual place/bar/state/action cells with a single line —
 * the card's own last-known label, `taken`, and its own `Undo` — inside the same reserved
 * height every other row gets, so nothing around it moves (D118). Undo is PER COPY: each
 * pulled copy carries its own 20s window, tracked by its own timestamp rather than by the
 * take's.
 *
 * WHAT THE WIRE STILL DOES NOT CARRY, STATED RATHER THAN PAPERED OVER:
 *   - `WalkPlanTake.for` names which orders share a take but not how the demand at THIS stop
 *     splits between them when there is more than one. `pickOrderFor` below picks the first
 *     ref this pass has not yet recorded a copy against, tracked against `recorded` alone —
 *     never the live ledger (§8's 2026-09-19 ruling) — and falls back to the first resolvable
 *     ref once every one has at least one. A rendering-side heuristic standing in for a fact
 *     the route could carry, flagged as an open question in `docs/specs/order-walk-plan.md`
 *     §9a rather than solved here.
 *
 * ORDERING IS THE ROUTE'S, NEVER RE-SORTED HERE (the owner's ruling, 2026-09-18): cards
 * (`stop.takes`) densest-first, copies (`take.copies`) as the wire sends them. This file
 * renders both arrays exactly as sent and contains no `.sort()` over either.
 */

import { useEffect, useMemo, useRef, useState } from 'react'

import { stateLabel, stateTone } from './cardState'
import { CardLocations } from './CardLocations'
import { Button, EmptyState, Icon, Pill } from './kit'
import { PlaceNeighbors } from './PlaceNeighbors'
import { PositionBar } from './PositionBar'
import { clamp } from './position'
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

/* ---- who a press should be recorded against ------------------------------------------------ */

/** A take's `for` names every order sharing it but not how this stop's `wanted` splits between
 *  them (the wire has no per-order share — see the file header). NEVER THE LIVE LEDGER (§8's
 *  2026-09-19 ruling): the first ref this pass has not yet recorded a copy against, by this
 *  pass's own tally alone — and once every ref has at least one, the first resolvable ref
 *  again, so a press still has somewhere to bank to. `record_pull` is the actual refusal if a
 *  specific order's line turns out to be full. */
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

/* ---- per-row state, kept for the pass and never rebuilt from a re-read --------------------- */

type TakenCopy = {
  readonly key: string
  readonly target: PullTarget
  readonly place: string
  readonly orderKey: string
  /** When THIS copy was pulled — Undo is per copy (§8's 2026-09-19 ruling), not per take. */
  readonly at: number
}

type RowState = {
  readonly taken: readonly TakenCopy[]
  readonly gone: ReadonlySet<string>
  /** `Take another` was pressed at least once — the row stays unlocked for the rest of the
   *  pass rather than re-locking after one extra pull, which is D118's OWN rule applied to
   *  itself: a control that disables again the instant it is used is a worse trap than one
   *  that stays put. */
  readonly overpull: boolean
  /** Forced open after an auto-collapse, by the chevron or by `Take another`. */
  readonly reopened: boolean
}

const EMPTY_ROW: RowState = { taken: [], gone: new Set(), overpull: false, reopened: false }

function rowKeyOf(stop: WalkPlanStop, take: WalkPlanTake): string {
  return `${stop.key}/${take.sku}`
}

/* ---- one copy of a take, as the wire's own `place` plus what this pass has learned ---------- */

/** `CardLocations`'s row reads `copy.place` and nothing else, so refreshing a description is
 *  folding the server's post-write block into it — never composing one by hand. THREE SOURCES,
 *  IN ONE ORDER: `fresh` (this drawer's own post-write block, when a pull here has since
 *  re-described it), else the plan's own block, as fetched. `gone` blanks the neighbours and
 *  nothing else (§8): a copy the press found already pulled is not re-described by the server
 *  — nobody asked it to be — so the ladder it still holds names cards around a card that is no
 *  longer there. */
function searchCopyOf(copy: WalkPlanCopy, fresh: Place | undefined, gone: boolean): SearchCopy {
  const base = fresh ?? copy.place
  return {
    key: copy.key,
    /* A GONE COPY SAYS SO IN ITS OWN STATE CELL (§8) rather than whatever it read at fetch
       time — `stateLabel`'s fallback capitalises an unrecognised word, so `'gone'` draws
       `Gone` with no further vocabulary needed here. A copy this pass itself pulled never
       reaches this branch: `rowOverride` replaces its row before `state` is ever drawn. */
    state: gone ? 'gone' : copy.state,
    state_at: null,
    has_photo: copy.has_photo,
    capture_id: copy.capture_id,
    cid: copy.cid,
    place: gone ? { ...base, neighbors: null } : base,
  }
}

/** THE COMPACT ADDRESS — `#44 WB1 R3` — never `PositionLabel`'s own `lead='slot'` stack.
 *
 *  §9a finding 1 named the defect directly: "each card draws `BOX <name> · Box <n>` and
 *  `SECTION <n> · <name>` as labelled fields... the stop header already names the drawer, so
 *  the row repeats it." `PositionLabel` composes exactly that pair for any label with a `Box`
 *  and a `Section` part — it is the right component for `#/inventory`, whose whole job is
 *  saying which box, and the wrong one here, where the stop already has. This draws the same
 *  two facts `PositionLabel` would — the slot figure (D58's count, never the store key) and
 *  the drawer's own name — as one line with neither word `BOX` nor `SECTION` in it, which is
 *  what `app/tests/orders.spec.ts`'s finding-1 case asserts directly. A copy in another drawer
 *  draws that drawer's own name here, automatically — it is always THIS copy's own `place`. */
function CopyAddress({ place }: { readonly place: Place }) {
  const figure = place.slot
  const drawer = [place.box_name, place.section_name].filter((s): s is string => Boolean(s?.trim())).join(' ')
  return (
    <span className="walkplan-address">
      {figure === null ? null : <span className="walkplan-address-num">#{figure}</span>}
      {drawer === '' ? null : <span className="walkplan-address-drawer">{drawer}</span>}
    </span>
  )
}

/* ============================================================================== a take (card) */

function TakeBlock({
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
  readonly take: WalkPlanTake
  readonly row: RowState
  /** Post-write position blocks, by the copy's own `key`. Read per copy and never for an
   *  order. */
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
  const [photoBroken, setPhotoBroken] = useState(false)
  const takenCount = row.taken.length
  const satisfied = takenCount >= take.wanted
  const takenByKey = useMemo(() => new Map(row.taken.map((t) => [t.key, t])), [row.taken])
  const copiesByKey = useMemo(() => new Map(take.copies.map((c) => [c.key, c])), [take.copies])
  const lastTaken = row.taken[row.taken.length - 1] ?? null
  const withinUndo = lastTaken !== null && now - lastTaken.at < UNDO_WINDOW_MS

  /* THE COPY LIST ONLY DRAWS WHILE THE TAKE IS OPEN. Satisfied, it becomes one strip; the
     strip itself collapses to one line once its own undo window has closed and nobody has
     reopened it (§8's 2026-09-19 ruling — "the copy list becomes one strip... then one
     summary line"). `overpull` (`Take another`) is the one way back to the full list. */
  const openList = !satisfied || row.overpull
  const collapsed = satisfied && !row.overpull && !withinUndo && !row.reopened

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

  const reopen = () => onSetRow({ ...row, reopened: true })
  const takeAnother = () => onSetRow({ ...row, overpull: true, reopened: true })

  /* ONE PHOTOGRAPH, ONCE, FOR THE CARD — never per copy (the defect this rebuild removes).
     The first ranked copy stands in for the card; every copy under this take is the same
     printing. */
  const leadCopy = take.copies[0]
  const showPhoto = leadCopy !== undefined && leadCopy.cid !== null && !photoBroken

  /* EVERY HOOK ABOVE THE COLLAPSED RETURN, ON PURPOSE. React's own rule: a component may not
     call fewer hooks on one render than another. The collapsed state used to return before
     this `useMemo` ran, so a take reaching its own collapse crashed the whole screen with
     "Rendered fewer hooks than expected" — found by rendering the met-take strip past its own
     20s window, the state no click in this file's own test suite had reached before. */
  const group: SearchGroup = useMemo(
    () => ({
      sku: take.sku,
      names: take.name === null ? [] : [take.name],
      number: null,
      printed_total: null,
      number_display: take.number_display,
      set_hint: null,
      set: take.set,
      rarity: take.rarity,
      condition: take.condition,
      /* NONE OF THESE FIVE ARE EVER DRAWN: `hideHeader` suppresses the panel's own header,
         which is the only place `CardLocations` reads them (`brief`: "the panel's listing
         header would lie with zeros — suppress it, do not feed it fake scalars"). Present
         only because the type demands a value. */
      listed: { pushed: 0, staged: 0, live: 0 },
      sold_here: 0,
      live_as_of: null,
      on_hand: take.copies.length,
      listable: 0,
      copies: take.copies.map((copy) => searchCopyOf(copy, facts.get(copy.key), row.gone.has(copy.key))),
    }),
    [take, facts, row.gone],
  )

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

  const locked = satisfied && !row.overpull

  return (
    <div className={`walkplan-take${satisfied ? ' walkplan-take-done' : ''}`}>
      <div className="walkplan-take-head">
        <div className="walkplan-take-photo">
          {showPhoto ? (
            <img
              src={photoUrl(leadCopy.place.box, leadCopy.place.index, leadCopy.cid)}
              alt={`The card ${take.name ?? take.sku}`}
              onError={() => setPhotoBroken(true)}
            />
          ) : (
            <Icon name="image" size={20} />
          )}
        </div>
        <div className="walkplan-take-identity">
          <span className="walkplan-take-name">{take.name ?? take.sku}</span>
          {take.number_display === null ? null : <span className="walkplan-take-number">{take.number_display}</span>}
          {!showBuyer || buyerNames.length === 0 ? null : <span className="walkplan-take-for">for {buyerNames.join(', ')}</span>}
        </div>
        <span className="walkplan-take-counter">
          <b>{takenCount}</b> of {take.wanted} taken
        </span>
      </div>

      {openList ? (
        <CardLocations
          persona="owner"
          group={group}
          onSell={() => {}}
          busyKey={null}
          soldKeys={new Set()}
          preserveOrder
          hideHeader
          className="card-locations-walk"
          rowAttrs={(copy) => ({
            state: takenByKey.has(copy.key) ? 'taken' : row.gone.has(copy.key) ? 'gone' : 'open',
            'capture-id': copy.capture_id ?? undefined,
          })}
          /* EVERY ROW IS OVERRIDDEN, NOT ONLY THE TAKEN ONE. `PositionLabel`'s own `lead='slot'`
             stack — what `CardLocations`'s default row draws — composes `Box 3 · Section 2`
             into a labelled `BOX <name>` / `SECTION <n>` pair, which is §9a finding 1 itself:
             the stop header already names the drawer, and a row repeating it as a standalone
             field is the taxonomy the mandate forbids, one register down. `CopyAddress` below
             draws the same fact `PositionLabel` would — the slot figure and the drawer's own
             name — as one plain compact line with neither word in it, matched against
             `app/tests/orders.spec.ts`'s own assertion that no row carries `.position-path`,
             `BOX` or `SECTION`. */
          rowOverride={(copy) => {
            const wire = copiesByKey.get(copy.key)
            if (wire === undefined) return undefined
            const taken = takenByKey.get(copy.key)
            const gone = row.gone.has(copy.key)

            if (taken !== undefined) {
              const stillWithin = now - taken.at < UNDO_WINDOW_MS
              return (
                <span className="walkplan-taken-line">
                  <CopyAddress place={wire.place} />
                  <span className="walkplan-taken-word">taken</span>
                  {!stillWithin ? null : (
                    <button type="button" className="walkplan-taken-undo" onClick={() => onUndo(taken)}>
                      <Icon name="undo" size={13} /> Undo
                    </button>
                  )}
                </span>
              )
            }

            const displayPlace = gone ? { ...copy.place, neighbors: null } : copy.place
            const target: PullTarget | null = wire.capture_id === null ? null : { box: wire.place.box, index: wire.place.index, capture_id: wire.capture_id }
            const pressing = busy === `walk/${take.sku}/${copy.key}`
            return (
              <div className="walkplan-row">
                <div className="walkplan-row-place">
                  <CopyAddress place={displayPlace} />
                  {/* THE LADDER'S OWN SLOT RESERVES ITS TALLEST STATE (D118), independent of
                      the row's overall `min-height`. A refresh can put a `skipped` line under
                      a name that had none, growing the ladder in place — and without this the
                      row's TOTAL height staying fixed was not enough: the state/action cells
                      below still slid down by exactly what the ladder gained, because they
                      flow after it. Reserving the ladder's own height keeps them at a constant
                      offset too. */}
                  <div className="walkplan-row-neighbors">
                    <PlaceNeighbors place={displayPlace} />
                  </div>
                </div>
                {/* NEVER "SO FAR" (§8's "The stop, rebuilt" ruling, owner, 2026-09-19): `so
                    far` is the caption's own word for a box still being FILLED, meaningless in
                    the middle of a PULL. `#/capture` and `#/inventory` keep it; this is the
                    walk's own opt-out and nobody else's. */}
                <PositionBar place={displayPlace} persona="owner" soFar={false} />
                <span className="walkplan-row-state">
                  <Pill tone={gone ? 'default' : stateTone(copy.state)}>{gone ? 'Gone' : stateLabel(copy.state)}</Pill>
                </span>
                <span className="walkplan-row-action">
                  {gone ? null : (
                    <Button
                      variant="primary"
                      size="sm"
                      icon="hand"
                      className="walkplan-pull"
                      data-capture-id={wire.capture_id ?? copy.key}
                      busy={pressing}
                      disabled={locked || target === null || (busy !== null && !pressing)}
                      onClick={() => {
                        if (target === null) return
                        const order = pickOrderFor(take, ordersByKey, recordedForSku)
                        if (order === null) return
                        onPull(target, take.name ?? take.sku, wire.place.label, order, copy.key)
                      }}
                    >
                      Pull
                    </Button>
                  )}
                </span>
              </div>
            )
          }}
        />
      ) : (
        <div className="walkplan-take-done-row">
          <Icon name="check" size={15} />
          <span>{takenCount === take.wanted ? 'Taken.' : `Taken — ${takenCount - take.wanted} extra.`}</span>
          {!withinUndo || lastTaken === null ? null : (
            <button type="button" className="walkplan-take-undo" onClick={() => onUndo(lastTaken)}>
              <Icon name="undo" size={14} /> Undo {Math.max(0, Math.ceil((UNDO_WINDOW_MS - (now - lastTaken.at)) / 1000))}s
            </button>
          )}
          <button type="button" className="walkplan-take-again" onClick={takeAnother}>
            Take another
          </button>
        </div>
      )}
    </div>
  )
}

/* ============================================================================== a stop */

/** THE STOP'S OWN SPAN BAR — `#242–284 of 987`, over `WalkPlanStop.box_total` (added to the
 *  wire 2026-09-19). The caption differs from `PositionBar`'s own (a span, not a slot), so this
 *  draws the same three markup classes by hand rather than the component itself — the honest
 *  span numbers alone when `box_total` is absent, never a fabricated proportion. */
function StopSpanBar({ span, boxTotal }: { readonly span: { start: number; end: number | null }; readonly boxTotal: number | null | undefined }) {
  const end = span.end
  if (boxTotal === null || boxTotal === undefined || !Number.isFinite(boxTotal) || boxTotal <= 0) {
    return (
      <span className="walkplan-stop-span" title="Where in this drawer">
        <Icon name="grid" size={13} />
        {end === null ? `#${span.start}` : `#${span.start}–${end}`}
      </span>
    )
  }
  const start = clamp(span.start, 1, boxTotal)
  const stop = clamp(end ?? boxTotal, start, boxTotal)
  const segments: { start: number; end: number; here: boolean }[] = []
  if (start > 1) segments.push({ start: 1, end: start - 1, here: false })
  segments.push({ start, end: stop, here: true })
  if (stop < boxTotal) segments.push({ start: stop + 1, end: boxTotal, here: false })
  const caption = `#${start}–${stop} of ${boxTotal}`
  return (
    <div className="position-bar position-bar-owner walkplan-stop-bar" role="img" aria-label={caption}>
      <p className="position-bar-text position-bar-text-box">{caption}</p>
      <div className="position-bar-track">
        {segments.map((seg) => (
          <span
            key={`${seg.start}-${seg.end}`}
            className={seg.here ? 'position-bar-segment position-bar-here' : 'position-bar-segment'}
            style={{ flexGrow: seg.end - seg.start + 1 }}
          />
        ))}
      </div>
    </div>
  )
}

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
          <StopSpanBar span={stop.span} boxTotal={stop.box_total} />
        )}
      </header>
      {stop.takes.map((take) => {
        const rowKey = rowKeyOf(stop, take)
        return (
          <TakeBlock
            key={take.sku}
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
  const keysSig = useMemo(() => [...walkKeys].sort().join(' '), [walkKeys])
  const [plan, setPlan] = useState<WalkPlan | null>(null)
  const [failure, setFailure] = useState<Failure | null>(null)
  const [loading, setLoading] = useState(true)
  const live = useRef(true)
  const [rows, setRows] = useState<Map<string, RowState>>(new Map())
  /** How many copies THIS PASS has recorded, per sku then per order key — `pickOrderFor`'s
   *  only input. Reset with the plan: a new plan is a new pass. */
  const [recorded, setRecorded] = useState<Map<string, Map<string, number>>>(new Map())
  /** THE POSITIONAL FACTS A PULL HAS SINCE RE-DESCRIBED, keyed by a copy's own `key` (§8's
   *  2026-09-19 ruling). Empty until the first press. It holds `Place` blocks the server
   *  composed AFTER its own write and is folded into a copy's `place` before it reaches
   *  `CardLocations` — never read by anything that decides which stop, which row or which
   *  copy comes first. Reset with the plan: a new plan is a new pass, and it arrives already
   *  current. */
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

  /* Ticks twice a second, ONLY while some copy is still inside its OWN undo window — an idle
     pass with everything either untouched or already past every window pays for no timer at
     all. Undo is per copy now (§8), so this scans every row's own `taken` list rather than a
     single per-take timestamp. */
  const anyPending = useMemo(() => {
    for (const row of rows.values()) {
      for (const taken of row.taken) {
        if (now - taken.at < UNDO_WINDOW_MS) return true
      }
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
   *  and minus the rows this pass has already finished with — a taken copy has left and a gone
   *  one was already claimed elsewhere, so neither is a card the screen is still telling
   *  somebody to count to. Scoped to the ONE box, because D58 renumbers the drawer that changed
   *  and no other, and a copy at another stop of the SAME box is in that drawer too.
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
          if (copy.place.box !== box) continue
          if (copy.key === pressedKey || takenKeys.has(copy.key) || row.gone.has(copy.key)) continue
          if (seen.has(copy.key)) continue
          seen.add(copy.key)
          out.push({ box: copy.place.box, index: copy.place.index })
        }
      }
    }
    return out
  }

  /** The server's post-write blocks, folded in by the copy's own key (`box/index`, matching
   *  `WalkPlanCopy.key`). A block for a position this pass is not drawing is simply never
   *  asked for, so nothing here filters. */
  const absorb = (blocks: readonly Place[]) => {
    if (blocks.length === 0) return
    setFacts((prev) => {
      const next = new Map(prev)
      for (const block of blocks) next.set(`${block.box}/${block.index}`, block)
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
          const taken = [...current.taken, { key: copyKey, target, place: result.place, orderKey: order.key, at: Date.now() }]
          const next = new Map(prev)
          next.set(rowKey, { ...current, taken })
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
        next.set(rowKey, { ...current, taken })
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
