import { useEffect, useRef } from 'react'

/* ONE POLLING PRIMITIVE, WHERE FIVE HAND-ROLLED TIMERS USED TO STAND (D-one-poller).
 *
 * `RunPanel.tsx` polled the run list and a run's own detail; `BoxRuns.tsx` copied the run
 * list's constants BY COMMENT (`4s / 20s, commented as copying RunPanel`); `SubmissionClaims.tsx`
 * polled at 8s while a claim was live; `App.tsx`'s `useServerPresence` polled `/status` at 15s
 * and on window focus. None of the five knew about tab visibility, none backed off on a
 * failing server, and none of them were counted against how many requests the capture server
 * can actually run at once — `server/capture_server.py:REQUEST_SLOTS` bounds that at 4
 * (`docs/DEBTS.md` §11: less concurrency is measurably BETTER on this rig, not more), and a
 * fifth timer added on top of the other four would have spent a slot nobody was watching.
 *
 * THE PRIMITIVE WAS UNFACTORED, NOT MISSING — CLAUDE.md's own test for reaching past a
 * workaround. This hook is what the five already wanted in common: a live/idle cadence pair
 * (three of the five already had exactly that pair), a pause while the document is hidden, a
 * backoff that lengthens the wait on a run of failures rather than hammering a server that
 * just went quiet, and one module-level counter every caller shares so the app never has more
 * requests in flight than the server has slots for.
 *
 * THE MIGRATION IS THE PROOF. If this hook could not express what `RunPanel` already did
 * (chained timeouts, "first failure announced and the rest swallowed", a poll that runs only
 * while a run is open and only while that run is live), it would be the wrong hook — so
 * `RunPanel.tsx`, `BoxRuns.tsx`, `SubmissionClaims.tsx` and `App.tsx` all migrate onto it in
 * the same change, and their existing specs staying green is what verifies the migration
 * rather than a new spec asserting the hook in isolation. */

/** How many requests this app will let itself have in flight against the capture server at
 *  once, mirroring `server/capture_server.py:REQUEST_SLOTS`. Declared here rather than read
 *  off the wire because `/status` does not publish it and a constant that never moves without
 *  a matching server-side change is the safer half of `docs/DEBTS.md` §11's own measurement:
 *  a slot beyond this one is not "faster", it is the GIL contention that measurement found. */
const REQUEST_SLOTS = 4

/** Shared across every `usePoll` in the app on purpose — the whole point is ONE accounting,
 *  not one per caller. A module-level counter rather than a context: nothing here renders,
 *  and threading a provider through the shell for a number no screen ever reads would be the
 *  second vocabulary D16 warns about. */
let inFlight = 0

/** A tick that is due but finds every slot spent backs off a beat rather than firing anyway —
 *  short, because this is a courtesy to the OTHER three slots and not a real interval of its
 *  own; the poll's own cadence is what governs how often it is willing to ask at all. */
const SLOT_WAIT_MS = 1000

/** A run of consecutive failures multiplies the idle cadence by up to this much, so a server
 *  that has gone quiet is asked less and less often rather than on the same clock a healthy
 *  one gets — capped, so a very long outage still notices a recovery inside a minute or two
 *  rather than backing off forever. */
const MAX_BACKOFF = 8

export type PollOptions<T> = {
  /** The request itself. Thrown errors are caught and reported through `onError`. */
  fn: () => Promise<T>
  /** Called with every successful answer. */
  onData: (data: T) => void
  /** Called on a failed request. Optional: `BoxRuns` has nowhere to draw a fault and simply
   *  reschedules, exactly as it always has. */
  onError?: (err: unknown) => void
  /** Cadence while `isLive` reads true off the last answer. */
  liveMs: number
  /** Cadence otherwise — and while the tab is hidden, this is what resumes on it becoming
   *  visible again rather than the live cadence, so a background tab never assumes it is
   *  still the busy case it was when it was last looked at. */
  idleMs: number
  /** Whether the last answer counts as "live" for cadence purposes. Defaults to always-idle,
   *  which is what a poll with no live/idle distinction at all wants (the run detail poll is
   *  driven by its own caller instead — see `stopWhenIdle` below). */
  isLive?: (data: T) => boolean
  /** `false` stops the poll outright — no request, no timer — the shape `RunPanel`'s detail
   *  poll needs for "only while a run is open". Defaults to `true`. */
  enabled?: boolean
  /** Stop polling the moment one answer reads not-live, rather than continuing on the idle
   *  cadence. This is `RunPanel`'s detail poll: once a run is no longer live there is nothing
   *  left to watch, and the caller's own `else` branch (a one-shot re-read of the list) is
   *  what used to run in its place. Requires `isLive`. */
  stopWhenNotLive?: boolean
  /** Restart the poll — an immediate tick on a fresh cadence — when this changes, even while
   *  `enabled` stays `true`. `RunPanel`'s detail poll is the caller that needs it: switching
   *  from one open run to another must ask about the new one right away rather than waiting
   *  out whatever was left of the old run's timer. Omit it for a poll with nothing to key on
   *  (the run list, the box's runs, the claims panel all poll one unchanging thing). */
  restartKey?: string | number | null
  /** Also ask immediately whenever the window regains focus — `App.tsx`'s status poll is the
   *  one caller that had this, on the theory that a phone or a laptop lid closing and
   *  reopening is exactly the moment the answer is most likely to have gone stale. */
  refreshOnFocus?: boolean
}

export type PollHandle = {
  /** Ask right now, on demand, outside the poll's own cadence — and reschedule the NEXT tick
   *  from this moment rather than from whenever the last one landed. `App.tsx` uses this for
   *  `onServerBoot`'s "the server just restarted" notice, which wants a fresh read at once
   *  rather than waiting out whatever was left of the 15s clock. */
  refresh: () => void
}

/** The five pollers' one primitive. Mount it, and it runs `fn` on the cadence its own answers
 *  imply until the component unmounts or `enabled` goes false — nothing more is asked of a
 *  caller than what `RunPanel`'s hand-rolled version already asked of itself. */
export function usePoll<T>(options: PollOptions<T>): PollHandle {
  const optsRef = useRef(options)
  optsRef.current = options
  const restartKey = options.restartKey ?? null
  const tickRef = useRef<() => void>(() => {})

  useEffect(() => {
    if (options.enabled === false) return
    let canceled = false
    let timer = 0
    let failures = 0
    let hiddenSkip = false

    const schedule = (ms: number) => {
      window.clearTimeout(timer)
      timer = window.setTimeout(() => void tick(), ms)
    }

    const tick = async () => {
      if (canceled) return
      /* PAUSED WHILE THE TAB IS HIDDEN. A background tab does not spend one of the four slots
       * on a screen nobody is looking at; `onVisible` below fires the next tick the moment
       * the tab comes back rather than waiting out whatever cadence was left running. */
      if (typeof document !== 'undefined' && document.hidden) {
        hiddenSkip = true
        return
      }
      if (inFlight >= REQUEST_SLOTS) {
        schedule(SLOT_WAIT_MS)
        return
      }
      inFlight++
      try {
        const data = await optsRef.current.fn()
        if (canceled) return
        failures = 0
        optsRef.current.onData(data)
        const live = optsRef.current.isLive?.(data) ?? false
        if (!live && optsRef.current.stopWhenNotLive === true) return
        schedule(live ? optsRef.current.liveMs : optsRef.current.idleMs)
      } catch (err) {
        if (canceled) return
        optsRef.current.onError?.(err)
        failures = Math.min(failures + 1, MAX_BACKOFF)
        schedule(optsRef.current.idleMs * failures)
      } finally {
        inFlight--
      }
    }
    tickRef.current = () => void tick()

    const onVisible = () => {
      if (typeof document !== 'undefined' && document.hidden) return
      if (!hiddenSkip) return
      hiddenSkip = false
      void tick()
    }
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', onVisible)
    }
    const onFocus = () => void tick()
    if (optsRef.current.refreshOnFocus === true) {
      window.addEventListener('focus', onFocus)
    }

    void tick()
    return () => {
      canceled = true
      window.clearTimeout(timer)
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', onVisible)
      }
      window.removeEventListener('focus', onFocus)
    }
  }, [options.enabled, restartKey])

  return { refresh: () => tickRef.current() }
}
