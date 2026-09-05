import { useSyncExternalStore } from 'react'

import { onServerBoot } from './server'
import type { OrderLineReason, OrdersPayload, ShippingBatch, ShippingLane } from './types'

/* THE HUB'S MEMORY ACROSS A STAGE SWITCH.
 *
 * `#/orders` and `#/shipping` are one screen with two stages, but the shell keys its view on the
 * hash, so switching stages unmounts and remounts the hub. Everything a person would be annoyed
 * to lose on that switch lives here rather than in component state: the ledger's last answer,
 * an unsent paste, the filter, and above all the export the capture server is holding — which
 * the server cannot list back, so a client that forgot it would have no way to find it again.
 *
 * Nothing here touches the browser's storage. It lives as long as the tab does, which is the
 * same lifetime as the batch it remembers. */

export type Stage = 'pull' | 'ship'
export type PullFilter = 'all' | 'done' | OrderLineReason
/** How the Pull stage is worked: one order at a time, or every open order's copies in one pass
 *  through the boxes. */
export type PullMode = 'orders' | 'walk'

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
  readonly filter: PullFilter
  readonly mode: PullMode
  /** THE ORDERS THIS WALK WAS STARTED OVER — `OrderRow.key`s, frozen when the walk is entered
   *  and cleared when it is left. `null` outside a walk.
   *
   *  It exists so the walk's "N of M orders fully pulled" counts progress through the work in
   *  front of you rather than the ledger's lifetime. Counted over `done` against `open + done`
   *  the figure was correct on the day it was measured (20 open, 0 done) and inflates for ever:
   *  a store with 200 completed orders and 3 open reads `200 of 203` on a three-order walk.
   *
   *  IT IS HERE AND NOT IN THE URL, on the owner's ruling of 2026-09-04. This store's whole
   *  argument is a lifetime as long as the tab, and a walk is a sitting at the boxes. A reload
   *  mid-walk resets the figure, which is honest — you are starting the walk again. */
  readonly walkKeys: ReadonlySet<string> | null
  /** The order the Pull stage has open — an `OrderRow.key`. `null` means the first one shown.
   *  Mirrored into the hash as `#/orders?order=<key>` so a selection is linkable. */
  readonly selected: string | null
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
}

let state: HubState = {
  payload: null,
  arriving: null,
  paste: '',
  filter: 'all',
  mode: 'orders',
  walkKeys: null,
  selected: null,
  batch: null,
  lanes: new Set(SHIP_LANES),
  gone: null,
  busy: null,
  version: 0,
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
  /* AND THE WALK'S PASS GOES WITH IT. `walkKeys` is the orders a pass was started over (D96,
     amended), and a capture server that restarted may have taken orders since — so a figure counted
     against the old set describes a sitting that is over. Unlike a stale batch it is not visibly
     broken: it is a smaller number that looks fine. Cleared rather than recounted, for the reason
     the batch is: this listener knows the server changed and nothing here knows what it changed to.
     The next walk freezes a fresh set from whatever `GET /orders` answers.

     SEPARATELY FROM THE BATCH, because the two are not one fact. A restart with no batch held says
     nothing to the operator — there is no export to be gone — but it still ends a pass. */
  if (state.walkKeys !== null) setHub({ walkKeys: null })
  if (state.batch === null) return
  setHub({ batch: null, gone: BATCH_GONE_NOTICE })
})
