/* THE LIVE CHECK AFTER A SEND, AND WHEN IT RUNS (`D-one-press-sends-and-makes-live`, Q3).
 *
 * The owner's ruling: if the app is open when the 15-minute wait ends, it checks by itself
 * with no refresh; if the app is closed, it checks on the next visit to Pricing or Home. No
 * server job runs unattended. So the clock lives HERE, in the page, and nowhere else:
 *
 *  - A visit to Pricing or Home mounts `useLiveCheck`, which reads `GET /pipeline/sends`. If a
 *    receipt is due, the check runs at once (the "closed app" half).
 *  - Otherwise, if one will be due, ONE timer waits for that moment and runs the check (the
 *    "open app" half). The timer is module-level on purpose: it outlives the screen that
 *    started it, so the check still runs if the owner has moved to Orders when the wait ends.
 *
 * An automatic check that fails does not retry by itself until the next visit. A retry loop
 * against a signed-out session would open a socket to TCGplayer on every render. */

import { useEffect, useSyncExternalStore } from 'react'
import { describeFailure, liveCheck, sendsStatus } from './server'
import type { LiveCheckAnswer, SendsStatus } from './types'

export type LiveCheckState = {
  /** The newest status, or null before the first read (and always in the demo, which has none). */
  readonly status: SendsStatus | null
  readonly checking: boolean
  /** What the last check found, for the send card's one sentence. */
  readonly last: LiveCheckAnswer | null
  readonly failure: { code: string; message: string } | null
}

let state: LiveCheckState = { status: null, checking: false, last: null, failure: null }
const listeners = new Set<() => void>()
let timer: ReturnType<typeof setTimeout> | null = null
let autoFailed = false

/** The longest delay `setTimeout` honours; a later moment is re-read when this one fires. */
const MAX_DELAY_MS = 2_147_000_000

function publish(next: Partial<LiveCheckState>): void {
  state = { ...state, ...next }
  for (const listener of listeners) listener()
}

function schedule(status: SendsStatus): void {
  if (timer !== null) {
    clearTimeout(timer)
    timer = null
  }
  if (status.due) {
    if (!autoFailed) void run(false)
    return
  }
  if (status.check_at === null) return
  /* THE SERVER'S CLOCK, NOT THIS DEVICE'S: the gap is measured between two stamps the server
     wrote, so a phone whose clock is off by minutes still waits the right amount. */
  const wait = Date.parse(status.check_at) - Date.parse(status.now)
  if (!Number.isFinite(wait)) return
  timer = setTimeout(() => {
    timer = null
    autoFailed = false
    void refresh()
  }, Math.min(MAX_DELAY_MS, Math.max(1_000, wait + 1_000)))
}

/** Read the status and schedule what it asks for. A refusal (the demo, an offline server)
 *  leaves the status null and schedules nothing: there is nothing to wait for. */
export async function refresh(): Promise<void> {
  try {
    const status = await sendsStatus()
    publish({ status })
    schedule(status)
  } catch {
    publish({ status: null })
  }
}

/** Run the check. `force` is the manual press, which runs with nothing due. */
export async function run(force: boolean): Promise<LiveCheckAnswer | null> {
  if (state.checking) return null
  publish({ checking: true, failure: null })
  let answer: LiveCheckAnswer | null = null
  try {
    answer = await liveCheck(force)
    publish({ last: answer })
  } catch (err) {
    if (!force) autoFailed = true
    publish({ failure: describeFailure(err) })
  } finally {
    publish({ checking: false })
  }
  await refresh()
  return answer
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function snapshot(): LiveCheckState {
  return state
}

/** A visit: read the status once on mount (and run a due check), then follow every change. */
export function useLiveCheck(): LiveCheckState & {
  readonly checkNow: () => Promise<LiveCheckAnswer | null>
  readonly refresh: () => Promise<void>
} {
  const current = useSyncExternalStore(subscribe, snapshot, snapshot)
  useEffect(() => {
    /* A NEW VISIT IS A NEW ATTEMPT: a check that failed on the last visit may pass now. */
    autoFailed = false
    void refresh()
  }, [])
  return { ...current, checkNow: () => run(true), refresh }
}
