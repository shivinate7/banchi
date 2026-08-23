/* The motion trigger — Gate C's auto-capture, behind the seam trigger.ts built for it.
 *
 * docs/specs/motion-trigger.md is the spec; docs/GATES.md's Gate C section carries the
 * measurements every constant below is derived from. The short form: the feeder presents a
 * card roughly every 660 ms (owner-stated, and the Gate B run's terminal press rate agreed
 * to 2 ms), jitter is ±34 ms robust, the capture round trip is bounded at 250 ms, and the
 * frame-difference signal-to-noise on this rig is at worst ~20x. Those four numbers are why
 * the parameters below are numbers and not adjectives.
 *
 * TWO HALVES, SPLIT FOR THE SAME REASON geometry/ SPLITS DETECTION FROM CROPPING:
 *
 *   MotionMachine   pure arithmetic over sampled frames. No DOM, no clock of its own, no
 *                   camera — `step(nowMs, cells)` in, event out. This is the half a test
 *                   can hold an exact answer key against (app/tests/motion.spec.ts does),
 *                   which matters because the other half cannot be tested without a rig.
 *
 *   motionTrigger   the DOM wrapper: samples the <video> down to a small grid on a reused
 *                   canvas, feeds the machine once per decoded frame, and translates `fire`
 *                   into the seam's onFire. It is deliberately thin, because everything in
 *                   it is untestable off the rig.
 *
 * WHAT THE TRIGGER DECIDES AND WHAT IT DOES NOT (trigger.ts's own contract): settling,
 * novelty, card-presence and the refractory are the trigger's business. "A request is
 * already in flight", "no box is selected" and "the run is halted" belong to the screen —
 * and in motion mode the screen COUNTS the fires it swallows instead of eating them
 * silently, because under a feeder every swallowed fire is a card past the lens with no
 * record. That is spec §5.5's rule, and the counter is what makes the failure loud.
 */

import type { RefObject } from 'react'

import type { Trigger } from './trigger'

/* ------------------------------------------------------------------ the sampled frame */

/* The whole 3840x2160 preview collapses to this grid before anything looks at it. Each
 * cell averages ~3,600 sensor pixels, which attenuates sensor noise ~60x — measured on the
 * 53 Gate B frames: the desk band's frame-to-frame mean-abs-diff is ~0.35 of 255 while the
 * weakest real card swap is 14.3. The grid is landscape because the PREVIEW is landscape:
 * rotation is applied at encode time and the preview is deliberately never rotated
 * (useCamera.ts's ROTATION_KEY comment).
 */
export const GRID_W = 64
export const GRID_H = 36

/* The region the machine actually watches, as insets into the grid. Derived from the Gate
 * B frames, not chosen: in 15 of 53 frames the feed path carried a SECOND card, out of
 * focus, whose band shows the same cross-run variance as the card itself (22 luma levels
 * vs the desk's 1.6) — so an unmasked metric reads the feed path as signal. In the
 * unrotated landscape preview that band and the flanking empty stands live at the frame
 * edges, so the watch region is the centre, inset 20% each side horizontally and 10%
 * vertically. The card spanned roughly x 0.20-0.82, y 0.07-0.91 of the landscape frame in
 * every Gate B shot (placement repeats to ~30 px at 4K), so the inset region sits inside
 * the card with margin for the ~90 px vertical walk the run showed.
 */
export const ROI_X0 = Math.round(GRID_W * 0.2)
export const ROI_X1 = Math.round(GRID_W * 0.8)
export const ROI_Y0 = Math.round(GRID_H * 0.1)
export const ROI_Y1 = Math.round(GRID_H * 0.9)
export const ROI_CELLS = (ROI_X1 - ROI_X0) * (ROI_Y1 - ROI_Y0)

/* ------------------------------------------------------------------------- parameters */

export type MotionParams = {
  /** Mean-abs-diff (0-255) above which the scene is MOVING. Fixed rather than adaptive:
   *  §10.0 mandates manual exposure, so there is no drift to adapt to, and an EMA floor
   *  that learns during slow motion is a way to go blind. 6.0 sits ~17x over the measured
   *  0.35 noise floor and ~2.4x under the weakest observed swap. */
  tHi: number
  /** Below this the scene is STILL. The gap between tLo and tHi is the Schmitt band — a
   *  single threshold chatters at the boundary and the still-counter never accumulates. */
  tLo: number
  /** Consecutive still frames that mean "settled". 2 frames = 67 ms at 30fps. The original
   *  guess of 6 (200 ms), plus a blinding 400 ms cooldown, summed to more than the 458 ms
   *  worst cycle Gate B measured — infeasible at the MEAN cycle, not just the worst. */
  stillFrames: number
  /** Floor on the spacing between fires, DEFERRING rather than blinding: a settle that
   *  completes inside the window fires when it expires instead of being dropped. Sized to
   *  the measured capture round trip (<250 ms), not to the card cycle. */
  refractoryMs: number
  /** A settled frame must differ from the LAST FIRED frame by this much, or it is the same
   *  card sitting there and the fire is suppressed. The gate that actually prevents
   *  double-captures — the refractory is a guess about time, this is a statement about the
   *  picture. 4.0 is ~11x the noise floor and ~3.5x under the weakest same-card repeat
   *  measured across the Gate B duplicates (14.3). */
  tNovel: number
  /** Mean ROI luma below which a settled scene is an empty stand, not a card. The Gate B
   *  frames measure the card region at ~172 and the empty desk/backdrop at 30-65. NOT
   *  geometry/detect.py's tone segmentation, which was measured at 0/53 on this rig —
   *  a brightness floor over a fixed region needs none of that method's premises. */
  cardLumaFloor: number
  /** Continuous motion this long without settling is a jam or a hand — surfaced as
   *  `stalled`, and the machine does NOT fire. Firing anyway was argued (never silently
   *  drop a card, §5.5) and rejected for v1: a hand in frame would capture-spam, and the
   *  stall is loud on screen, which is what §5.5 actually requires. Revisit at the rig —
   *  docs/specs/motion-trigger.md carries both sides. */
  maxMoveMs: number
}

/* ~660 ms cycle, <250 ms round trip, 34 ms jitter. See each field's own comment. */
export const DEFAULT_PARAMS: MotionParams = {
  tHi: 6.0,
  tLo: 3.0,
  stillFrames: 2,
  refractoryMs: 250,
  tNovel: 4.0,
  cardLumaFloor: 90,
  maxMoveMs: 1250,
}

/* ------------------------------------------------------------------------ the machine */

export type MotionPhase = 'watching' | 'moving' | 'settling'

export type MotionEvent =
  | 'fire'
  | 'suppressed:unchanged'
  | 'suppressed:no-card'
  | 'stalled'

/** What the HUD renders. Counters never reset while the trigger is armed — a rig-tuning
 *  session reads them as rates against the run's card count. */
export type MotionDiagnostics = {
  phase: MotionPhase
  /** Last frame-to-frame mean-abs-diff over the ROI, the number every threshold is set
   *  against. On screen so the noise floor and the swap signal can be SEEN during tuning
   *  instead of inferred afterwards. */
  d: number
  /** Mean ROI luma of the last frame — the card-present signal. */
  luma: number
  frames: number
  fires: number
  suppressedUnchanged: number
  suppressedNoCard: number
  stalled: number
}

export class MotionMachine {
  private readonly p: MotionParams

  private prev: Float32Array | null = null
  private lastFired: Float32Array | null = null
  private stillRun = 0
  private movingSince: number | null = null
  private stallFlagged = false
  private refractoryUntil = 0
  /* One verdict per settle episode. Without this, a card sitting still re-runs the gates
   * every frame: the novelty suppression would count thirty times a second and the counter
   * stops meaning "cards suppressed". Reset by the next motion above tHi. Starts FALSE so
   * a card already at the lens when the trigger is armed is captured — arming the trigger
   * is starting the run — while an EMPTY stand at arm time takes one no-card suppression
   * and then waits for motion, which is the correct pair of behaviours. */
  private episodeJudged = false

  readonly diag: MotionDiagnostics = {
    phase: 'watching',
    d: 0,
    luma: 0,
    frames: 0,
    fires: 0,
    suppressedUnchanged: 0,
    suppressedNoCard: 0,
    stalled: 0,
  }

  constructor(params: MotionParams = DEFAULT_PARAMS) {
    this.p = params
  }

  /** One decoded frame. `cells` is the ROI as luma values; the machine COPIES what it
   *  keeps, because the sampler reuses its buffer — holding the reference would make prev
   *  and current the same array and d identically zero: a trigger that never fires, with
   *  no error anywhere. */
  step(nowMs: number, cells: Uint8ClampedArray | Float32Array): MotionEvent | null {
    this.diag.frames += 1

    let luma = 0
    for (let i = 0; i < cells.length; i += 1) luma += cells[i] as number
    luma /= cells.length
    this.diag.luma = luma

    if (this.prev === null) {
      this.prev = Float32Array.from(cells)
      return null
    }

    let sum = 0
    for (let i = 0; i < cells.length; i += 1) {
      sum += Math.abs((cells[i] as number) - (this.prev[i] as number))
    }
    const d = sum / cells.length
    this.diag.d = d
    this.prev.set(cells)

    if (d > this.p.tHi) {
      // MOVING. A new episode: whatever verdict the last settle got, the next one is new.
      if (this.movingSince === null) this.movingSince = nowMs
      this.stillRun = 0
      this.episodeJudged = false
      this.diag.phase = 'moving'
      if (!this.stallFlagged && nowMs - this.movingSince > this.p.maxMoveMs) {
        this.stallFlagged = true
        this.diag.stalled += 1
        return 'stalled'
      }
      return null
    }

    if (d >= this.p.tLo) {
      /* The Schmitt band: not confidently still, not new motion. The still-counter does
       * not accumulate — and the stall clock RUNS, starting here if it has to, because a
       * hand hovering at d 3-6 forever is exactly as jammed as one at d 20. `movingSince`
       * therefore means "since the scene stopped being confidently still", not "since d
       * last crossed tHi": a stall that only armed above tHi would let the band hide a
       * jam silently, which the test named for this case proved before this line existed. */
      this.stillRun = 0
      if (this.movingSince === null) this.movingSince = nowMs
      if (!this.stallFlagged && nowMs - this.movingSince > this.p.maxMoveMs) {
        this.stallFlagged = true
        this.diag.stalled += 1
        return 'stalled'
      }
      return null
    }

    // STILL.
    this.movingSince = null
    this.stallFlagged = false
    this.stillRun += 1
    this.diag.phase = this.stillRun >= this.p.stillFrames ? 'watching' : 'settling'

    if (this.stillRun < this.p.stillFrames) return null
    if (this.episodeJudged) return null
    /* Inside the refractory the episode stays UNJUDGED and the still-counter keeps
     * counting, so the first step after expiry delivers the verdict. That is the whole
     * "deferring" property: a card that arrives and settles fast is captured late rather
     * than not at all. */
    if (nowMs < this.refractoryUntil) return null

    this.episodeJudged = true

    if (luma < this.p.cardLumaFloor) {
      this.diag.suppressedNoCard += 1
      return 'suppressed:no-card'
    }

    if (this.lastFired !== null) {
      let novelty = 0
      for (let i = 0; i < cells.length; i += 1) {
        novelty += Math.abs((cells[i] as number) - (this.lastFired[i] as number))
      }
      if (novelty / cells.length < this.p.tNovel) {
        this.diag.suppressedUnchanged += 1
        return 'suppressed:unchanged'
      }
    }

    this.lastFired = this.lastFired ?? new Float32Array(cells.length)
    this.lastFired.set(cells)
    this.refractoryUntil = nowMs + this.p.refractoryMs
    this.diag.fires += 1
    return 'fire'
  }
}

/* ---------------------------------------------------------------------- the DOM half */

/* Rec.601 luma from RGBA, integer arithmetic. */
function toLuma(rgba: Uint8ClampedArray, out: Float32Array): void {
  for (let i = 0, p = 0; i < out.length; i += 1, p += 4) {
    out[i] =
      ((rgba[p] as number) * 77 + (rgba[p + 1] as number) * 150 + (rgba[p + 2] as number) * 29) >>
      8
  }
}

/** How often the HUD callback fires when nothing eventful is happening. Events (fire,
 *  suppression, stall) report immediately; this is only the heartbeat that keeps the live
 *  `d` readout moving. 30 setState calls a second on a screen holding a live 4K preview is
 *  the kind of main-thread load b4aca0c exists to warn about. */
const DIAG_INTERVAL_MS = 200

export function motionTrigger(
  video: RefObject<HTMLVideoElement | null>,
  onDiagnostics?: (diag: MotionDiagnostics) => void,
  params: MotionParams = DEFAULT_PARAMS,
): Trigger {
  return {
    /* The machine string the screen renders — docs/DESIGN.md's idiom, and the one line of
     * UI trigger.ts promised would change when this module arrived. */
    name: 'motion',

    start(onFire) {
      const machine = new MotionMachine(params)

      /* ONE canvas for the session, reused every frame — 8e9a46b's lesson, which applies
       * here with 30x the frequency it applied to captures. At 64x36 the backing store is
       * trivial, but a per-frame allocation at 30fps is the same shape of leak. */
      const canvas = document.createElement('canvas')
      canvas.width = GRID_W
      canvas.height = GRID_H
      const context = canvas.getContext('2d', { willReadFrequently: true })
      const grid = new Float32Array(GRID_W * GRID_H)
      const roi = new Float32Array(ROI_CELLS)

      let stopped = false
      let lastDiagAt = 0
      /* rAF fallback only: a 60 Hz rAF over a 30 fps stream must not diff a frame against
       * itself — d would read zero on alternate ticks, the still-counter would
       * double-count, and the trigger would fire at half the configured settle time with
       * no symptom anywhere. The currentTime guard alone is NOT enough on a live
       * MediaStream, where currentTime advances continuously between frames rather than
       * stepping per frame — so a minimum spacing near the frame period backs it up.
       * rVFC engines never reach this: rVFC fires once per decoded frame by contract. */
      let lastMediaTime = -1
      let lastConsumeAt = 0
      const MIN_FRAME_SPACING_MS = 28

      const report = (now: number, always: boolean) => {
        if (onDiagnostics === undefined) return
        if (!always && now - lastDiagAt < DIAG_INTERVAL_MS) return
        lastDiagAt = now
        onDiagnostics({ ...machine.diag })
      }

      const consume = (nowMs: number) => {
        const element = video.current
        /* No element, no stream, or a stream with no decoded frame yet: idle, do not
         * error. The trigger is armed at mount, before any camera is open, and must pick
         * frames up whenever they start without being re-armed (the screen arms once and
         * dispatches through a ref, by design). */
        if (element === null || context === null) return
        if (element.videoWidth === 0 || element.videoHeight === 0) return
        if (element.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return

        context.drawImage(element, 0, 0, GRID_W, GRID_H)
        const rgba = context.getImageData(0, 0, GRID_W, GRID_H).data
        toLuma(rgba, grid)
        let w = 0
        for (let y = ROI_Y0; y < ROI_Y1; y += 1) {
          for (let x = ROI_X0; x < ROI_X1; x += 1) {
            roi[w] = grid[y * GRID_W + x] as number
            w += 1
          }
        }

        const event = machine.step(nowMs, roi)
        if (event === 'fire') onFire()
        report(nowMs, event !== null)
      }

      /* One callback per DECODED frame where the browser offers it; display-rate rAF with
       * a mediaTime guard where it does not. */
      const hasRvfc = 'requestVideoFrameCallback' in HTMLVideoElement.prototype

      const loopRvfc = () => {
        if (stopped) return
        const element = video.current
        if (element === null) {
          window.setTimeout(loopRvfc, DIAG_INTERVAL_MS)
          return
        }
        /* rVFC is used for its PACING — one callback per decoded frame — but the machine's
         * clock is performance.now(), not meta.mediaTime. mediaTime restarts near zero
         * whenever the stream is replaced (a device change, a retry after a halt), and the
         * machine holds absolute deadlines across frames: a refractoryUntil minted on the
         * old timeline would then sit minutes ahead of the new clock and silently block
         * every fire until it caught up. One monotonic clock, immune to stream swaps. */
        element.requestVideoFrameCallback(() => {
          /* A callback registered before teardown still fires once. Without this check
           * that last frame could fire the machine AFTER the mode toggled away, and the
           * dispatch ref — already rewired to manual — would treat it as a manual fire
           * and capture a card nobody asked for. */
          if (stopped) return
          consume(performance.now())
          loopRvfc()
        })
      }

      const loopRaf = () => {
        if (stopped) return
        const element = video.current
        const now = performance.now()
        if (
          element !== null &&
          element.currentTime !== lastMediaTime &&
          now - lastConsumeAt >= MIN_FRAME_SPACING_MS
        ) {
          lastMediaTime = element.currentTime
          lastConsumeAt = now
          consume(now)
        }
        window.requestAnimationFrame(loopRaf)
      }

      if (hasRvfc) loopRvfc()
      else window.requestAnimationFrame(loopRaf)

      return () => {
        stopped = true
      }
    },
  }
}
