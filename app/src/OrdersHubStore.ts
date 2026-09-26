import { useSyncExternalStore } from 'react'

import { onServerBoot } from './server'
import type { OrdersPayload, PullTarget, ShippingBatch, ShippingLane } from './types'

/* THE HUB'S MEMORY ACROSS A STAGE SWITCH.
 *
 * `#/orders` and `#/shipping` are two screens over one state, and the shell keys its view on the
 * hash, so moving between them unmounts and remounts the hub. Everything a person would be
 * annoyed to lose on that move lives here rather than in component state: the ledger's last
 * answer, an unsent paste, and above all the export the capture server is holding — which
 * the server cannot list back, so a client that forgot it would have no way to find it again.
 *
 * Nothing here touches the browser's storage. It lives as long as the tab does, which is the
 * same lifetime as the batch it remembers. */

export type Stage = 'pull' | 'ship'

/** The lanes, in the order the columns draw them and `pipeline/shipping.py:LANES` declares
 *  them: envelope first because most orders land there, unjudged last because it is the pile
 *  that needs a person. */
export const SHIP_LANES: readonly ShippingLane[] = ['envelope', 'parcel', 'unjudged']

export type HubState = {
  readonly payload: OrdersPayload | null
  /** Whether the "add orders" well is open. `null` until the first read answers, which is what
   *  stops the well flashing open before the ledger has said whether it is empty. */
  readonly arriving: boolean | null
  readonly paste: string
  readonly batch: ShippingBatch | null
  readonly lanes: ReadonlySet<ShippingLane>
  /** The server-restart notice for the Ship stage. */
  readonly gone: string | null
  /** A write in flight from OUTSIDE any mounted hub — an undo pressed on a toast — so every Pull
   *  stays disabled while it runs, in whichever hub is mounted by the time it answers. */
  readonly busy: string | null
  /** Bumped by anything that wrote to the ledger from outside a mounted hub (an undo pressed
   *  on a toast), so the next mounted hub re-reads. */
  readonly version: number
  /** THE NEWEST PULL THIS SCREEN MADE THAT IS STILL UNDOABLE — `docs/specs/undo.md` §3's fast
   *  path, `U`, reached from `OrdersHub` regardless of which stage or order is on screen. It
   *  lives here rather than in a component because the pull's own toast outlives the row it
   *  was pressed from. Overwritten by the next pull, cleared by its own undo, and NO CLOCK
   *  (UN-5, `docs/specs/undo.md` §11.1, D28/D57 amended 2026-09-25): rank replaces it, the same
   *  ruling every other undo in this store answers to. It was called that already before UN-5
   *  and still carried an `until` the `U` handler gated on — this field's own removal is what
   *  makes the comment true. */
  readonly lastPull: { readonly target: PullTarget; readonly place: string; readonly name: string } | null
  /** THE MOST RECENT SUCCESSFUL UNDO MADE FROM A TOAST OR `U` — `undoFromToast` in
   *  `Orders.tsx` sets this beside clearing `lastPull`, and `PullStage` watches `undoneAt` to
   *  tell its own mounted walk (`useOrderWalk`'s `noteExternalUndo`) that this copy is no
   *  longer recorded. Neither of those undo paths goes through the walk's own `undoCopy`, so
   *  before this existed the walk's tally never moved for them (the review round's finding
   *  2). `undoneAt` is a COUNTER, never a boolean or a timestamp compared to `Date.now()`: two
   *  undos of the same copy in one session must both be seen, and a stale one must never be
   *  read as fresh by a clock that moved. */
  readonly undoneTarget: PullTarget | null
  readonly undoneAt: number
  /** WALK MODE'S ONE LINE (the owner's ruling, 2026-09-24): who is walked, how many cards to
   *  pick, what is next. The Orders screen writes it and the page header draws it. Null when
   *  nothing is walked. */
  readonly walkLine: readonly string[] | null
  /** The buyer list as a sheet, opened from the walk line or the chip. */
  readonly buyersOpen: boolean
}

let state: HubState = {
  payload: null,
  arriving: null,
  paste: '',
  batch: null,
  lanes: new Set(SHIP_LANES),
  gone: null,
  busy: null,
  version: 0,
  lastPull: null,
  undoneTarget: null,
  undoneAt: 0,
  walkLine: null,
  buyersOpen: false,
}

const listeners = new Set<() => void>()

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function hubState(): HubState {
  return state
}

export function setHub(patch: Partial<HubState> | ((current: HubState) => Partial<HubState>)): void {
  const next = typeof patch === 'function' ? patch(state) : patch
  state = { ...state, ...next }
  for (const listener of listeners) listener()
}

export function touchHub(): void {
  setHub((current) => ({ version: current.version + 1 }))
}

export function useHub(): HubState {
  return useSyncExternalStore(subscribe, hubState, hubState)
}

/* THE BOOT NOTICE (D73), RAISED WHERE THE BATCH LIVES. The export is held in the capture
 * server's memory and nowhere else, so a restart takes it with it — and a download link would go
 * on pointing at a batch that no longer exists. `onServerBoot` fires ONCE, at the request that
 * first sees the new boot id, and that request can come from any screen: the Pull stage's own
 * `GET /orders`, the inventory, the capture screen. A listener mounted with the Ship stage missed
 * every one of those and drew the stale batch again on the way back. This one outlives every
 * stage, and it says nothing while no batch is held — there is no export to be gone. */
export const BATCH_GONE_NOTICE =
  'The capture server restarted, so the export it was holding is gone. Read the file again.'

onServerBoot(() => {
  /* THE WALK NO LONGER HAS A FROZEN SET TO CLEAR HERE (§13 supersedes D96's own note): it is a
     live read of the selected order plus every ticked one, held in `Orders.tsx`'s own component
     state, and a server restart simply means its next `POST /orders/walk-plan` re-solves over
     whatever the store holds now — the same as any other re-read after a boot. */
  if (state.batch === null) return
  setHub({ batch: null, gone: BATCH_GONE_NOTICE })
})
