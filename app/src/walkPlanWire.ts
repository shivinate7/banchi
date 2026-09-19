/* TEMPORARY STUB — DELETE AT INTEGRATION.
 *
 * `docs/specs/order-walk-plan.md` §7 pins these wire types and a `walkPlan()` client function
 * as `app/src/types.ts` / `app/src/server.ts` additions, written on a parallel branch. Until
 * that branch merges, importing them from those files fails `tsc`, so this file declares the
 * SAME shapes and the SAME call, in one place, owned by this branch alone.
 *
 * `app/src/types.ts` IS THE ONLY WIRE-SHAPE FILE IN THIS PRODUCT. This file is not a second
 * one by intent — it is a cast held until the real declaration lands. At integration:
 *   1. delete this file,
 *   2. change every `from './orderWalkPlanWire'` in `OrdersWalk.tsx` to `from './types'`
 *      (types) and `from './server'` (the `walkPlan` function),
 *   3. re-run `cd app && npx tsc --noEmit`.
 * Never carry both declarations into the merged tree.
 */

import { ServerError } from './server'

export type WalkPlanCost = 'sections'

export type WalkPlanOrderRef = { readonly key: string; readonly number: string; readonly buyer: string | null }

export type WalkPlanCopy = {
  readonly box: number
  readonly index: number
  readonly slot: number | null
  readonly capture_id: string | null
  readonly cid: string | null
  readonly card: number | null
  readonly label: string | null
  readonly neighbors?: { prev: { slot: number; index: number; name: string | null; skipped?: number } | null; next: { slot: number; index: number; name: string | null; skipped?: number } | null } | null
}

export type WalkPlanTake = {
  readonly sku: string
  readonly name: string | null
  readonly number_display: string | null
  readonly wanted: number
  readonly for: readonly WalkPlanOrderRef[]
  readonly copies: readonly WalkPlanCopy[]
}

export type WalkPlanStop = {
  readonly key: string
  readonly box: number | null
  readonly box_name: string | null
  readonly section: number | null
  readonly section_name: string | null
  readonly pooled: boolean
  readonly game: string | null
  readonly game_display: string | null
  readonly order: number
  readonly span: { start: number; end: number } | null
  readonly takes: readonly WalkPlanTake[]
}

export type WalkPlanShort = {
  readonly sku: string
  readonly name: string | null
  readonly wanted: number
  readonly on_hand: number
  readonly short: number
  readonly for: readonly WalkPlanOrderRef[]
}

export type WalkPlanCounts = {
  readonly stops: number
  readonly boxes: number
  readonly copies: number
  readonly sections_considered: number
  readonly sections_candidate: number
  readonly exact: boolean
  readonly solve_ms: number
}

export type WalkPlan = {
  readonly cost: WalkPlanCost
  readonly stops: readonly WalkPlanStop[]
  readonly shortfall: readonly WalkPlanShort[]
  readonly counts: WalkPlanCounts
}

/** `POST /orders/walk-plan` — see §7. A minimal, direct call (not routed through this
 *  module's own `request()`, which is not exported) so this stub has no second copy of that
 *  machinery either; it is deleted along with the rest of this file at integration. */
export async function walkPlan(keys: readonly string[], cost: WalkPlanCost = 'sections'): Promise<WalkPlan> {
  let response: Response
  try {
    response = await fetch('/orders/walk-plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keys, cost }),
    })
  } catch {
    throw new ServerError('unreachable', 'No answer from the capture server for the walk plan.', 0)
  }
  const text = await response.text()
  let body: unknown = null
  try {
    body = text === '' ? null : JSON.parse(text)
  } catch {
    throw new ServerError('bad_response', `The walk-plan route returned something that was not JSON: ${text.slice(0, 200)}`, response.status)
  }
  if (!response.ok) {
    const wrapped = body !== null && typeof body === 'object' ? (body as { error?: { code?: string; message?: string } }).error : undefined
    if (wrapped && typeof wrapped.code === 'string' && typeof wrapped.message === 'string') {
      throw new ServerError(wrapped.code, wrapped.message, response.status)
    }
    throw new ServerError('http_error', `${response.status} ${response.statusText} from /orders/walk-plan.`, response.status)
  }
  return body as WalkPlan
}
