/* The cadence trigger — trigger 2, behind the same seam as the settle machine (D130).
 *
 * WHY A SECOND MACHINE, IN ONE MEASUREMENT. On 2026-09-11 the owner ran the settle trigger
 * (`src/motion.ts`) over a re-arranged feeder and saved two traces. Every fire reached disk
 * and every fire photographed a card — the plumbing was never in question — and the machine
 * fired on **5 of 29 cards** in one session and **5 of 34** in the other. The traces say why
 * without ambiguity: the feeder puts a card down every **0.867 s** (p10-p90 0.85-0.92 across
 * 29 cycles), and from the moment the first one lands the watch region is never quiet for more
 * than a frame or two. The longest run of frames under `tLo` per card has a MEDIAN OF ONE.
 * The settle rule wants `stillFrames` of the last `stillWindow` — two of four, with the window
 * full — and 13 of 28 cards never had four consecutive frames under `tHi` at all. A rule that
 * fires on stillness cannot fire on a feeder that never stops, and no threshold recovers it:
 * `score-trace.py sweep` reaches 9 of 29 at its best setting.
 *
 * What the feeder has instead of stillness is a BEAT. The luma of the region is a square wave
 * at the feeder's period; frame-to-frame motion dips to its floor at one phase of every cycle
 * and nowhere else. So this machine does what the owner asked for in as many words — *"the
 * first card kinda just triggers you to then go on a timed cadence since they're coming out of
 * a machine at pretty set intervals"* — and does it on measurements rather than on a clock
 * somebody typed:
 *
 *   1. It waits for the first card, using the settle machine's own presence gate (D81): the
 *      watch region must move `presenceFloor` away from the empty-stand baseline.
 *   2. It fires on that card at the first quiet frame, or after `firstWait` of a period if no
 *      quiet frame comes — a card with no photograph is §5.5's failure, a blurred one is an
 *      undo.
 *   3. It then fires once per period. The period is SEEDED at 870 ms — tonight's feeder, and
 *      a seed in exactly `dSeed`'s sense: what the machine runs on until it has measured — and
 *      MEASURED from the autocorrelation of the motion signal over the last `windowMs` once
 *      `lockAfterMs` of feeding exist. The strongest lag between `minPeriodMs` and
 *      `maxPeriodMs` is the period; a lag whose half or third scores nearly as well is a
 *      harmonic and the shorter one is taken, because the first two seconds of tonight's
 *      trace read 1,770 ms for an 885 ms beat and a machine firing at that rate photographs
 *      every other card.
 *   4. Locked, it knows the PHASE too: fold the window's motion by the period and the bin with
 *      the least motion is where the card rests. Each fire is scheduled for the next rest,
 *      taken on the first quiet frame at or after it, or blind after `quietWait` of a period
 *      — counted as `blindFires`, so a session can see how many photographs were taken on a
 *      moving frame.
 *   5. The same two gates the settle machine has stand in front of every fire: no card (the
 *      presence gate) and same card (`tNovel` against the last fired frame). Two `same`
 *      verdicts in a row mean the feeder has stopped with a card at the lens, and the beat goes
 *      IDLE rather than photographing it every period until somebody notices; motion above
 *      `tHi` wakes it. A stand empty for `lostAfter` periods drops the beat entirely and the
 *      machine waits for a first card again.
 *
 * REPLAYED OVER THE TWO TRACES THAT CONVICTED THE SETTLE RULE, causally, with the period and
 * phase re-estimated every `refreshFrames`: 23 fires over the 25 cards the first session fed
 * after the beat was audible, and 16 over 17 in the second — against 5 and 5 live.
 * `app/tests/cadence.spec.ts` replays them the same way and pins those counts; the traces are
 * banked in `harness/traces/` and T9 carries the receipt for what the settle rule scored on them.
 *
 * WHAT IS NOT MEASURED YET, AND IS NAMED SO NOBODY READS THIS AS CONFIRMED. No photograph has
 * been taken by this machine at the rig. The replay says a fire lands on a frame with median
 * `d` of 5-8 against a still floor near 3 — moving, a little — and whether that reads as a
 * usable photograph or a blur is a fact about the camera's exposure that only the rig can
 * answer. The first armed run is the measurement, and its trace is what §7 of
 * `docs/specs/motion-trigger.md` asks for.
 *
 * WHAT IT SHARES AND WHAT IT DOES NOT. The sampler (`startWatchSampler`) and the signal
 * machine are `motion.ts`'s: `d`, `dBase`, the thresholds, the baseline and the presence gate
 * all come from a `MotionMachine` this one owns and steps every frame. Its VERDICTS are
 * ignored — a settle is not what this trigger fires on — and this file's own counters are
 * what the HUD shows. `DEFAULT_PARAMS` in motion.ts is untouched: `make docs-audit`'s
 * `motion params` row mirrors that block into the offline scorer, and the cadence's numbers
 * are not the settle machine's.
 */

import type { RefObject } from 'react'

import {
  DEFAULT_PARAMS,
  DIAG_INTERVAL_MS,
  MotionMachine,
  startWatchSampler,
} from './motion'
import type { MotionControls, MotionDiagnostics, MotionEvent, MotionParams } from './motion'
import type { Trigger } from './trigger'

export type CadenceParams = {
  /** The settle machine's own parameters, for the signal, the thresholds and the baseline. */
  motion: MotionParams
  /** What the beat runs at until it has been measured. 870 ms is the feeder on 2026-09-11,
   *  read off 29 luma cycles (median 867, p10 850, p90 920). A seed in `dSeed`'s sense:
   *  the machine boots on it and replaces it the moment the autocorrelation locks. The
   *  operator may PIN a period from the Rig panel, which overrides both. */
  periodSeedMs: number
  /** The band the period is searched in. 300 ms is three times the frame period at 24 fps,
   *  under which a beat could not be told from noise; 2,500 ms is past any feeder here and
   *  short enough that a hand-fed pace does not get called a beat. */
  minPeriodMs: number
  maxPeriodMs: number
  /** How much motion history the estimate reads. 8 s is `noiseWindowMs`, for the same
   *  reason: long enough to hold nine cycles at the seed, short enough to follow a feeder
   *  that changes speed. */
  windowMs: number
  /** How much card-present history must exist before an estimate is attempted. Three seeded
   *  periods: an autocorrelation over fewer cycles than that picks the window's own length. */
  lockAfterMs: number
  /** How often the period and phase are re-estimated, in frames. 12 is ~2 a second at the
   *  observed 24 fps — far faster than a feeder changes speed, far cheaper than every frame. */
  refreshFrames: number
  /** The normalised autocorrelation a lag must reach to be believed. Tonight's two traces
   *  lock at 0.44-0.75 on the fundamental; a hand-fed session with no beat scores under 0.3. */
  lockCoeff: number
  /** A lag whose half or third scores at least this fraction of the peak is a harmonic of
   *  it, and the shorter lag is the period. 0.8 separates tonight's 1,770/885 pair (0.54
   *  against 0.53) from a genuinely slower beat. */
  harmonicRatio: number
  /** The phase resolution of the fold that finds the rest. 16 bins over 870 ms is 54 ms, a
   *  frame and a third at 24 fps. */
  restBins: number
  /** How far AHEAD of the predicted rest a quiet frame is accepted, as a fraction of the
   *  period. The rest is a frame or two wide and the fold that predicts it is a bin wide, so
   *  a prediction that lands a frame late would never see the quiet frame and would fire
   *  blind every time — which the first replay did, on 20 of 27 fires. Opening the window
   *  a fifth of a period early puts the quiet frame inside it: median `d` at fire fell from
   *  12 to under 4 on the same trace. The half-period floor after the last fire is what
   *  keeps an early window from chaining two fires onto one card. */
  restLead: number
  /** How long past the predicted rest to wait for a quiet frame before firing blind, as a
   *  fraction of the period. A quarter: the rest is a frame or two wide and the next card is
   *  half a period away, so a fire any later is a photograph of the swap. */
  quietWait: number
  /** How long after the first card's arrival to wait for a quiet frame before firing blind
   *  on it, as a fraction of the period. */
  firstWait: number
  /** Periods of empty stand after which the beat is dropped and the machine waits for a
   *  first card again. Two: a feeder that skipped one card has not stopped. */
  lostAfter: number
}

export const DEFAULT_CADENCE: CadenceParams = {
  motion: DEFAULT_PARAMS,
  periodSeedMs: 870,
  minPeriodMs: 300,
  maxPeriodMs: 2500,
  windowMs: 8000,
  lockAfterMs: 2600,
  refreshFrames: 12,
  lockCoeff: 0.3,
  harmonicRatio: 0.8,
  restBins: 16,
  restLead: 0.2,
  quietWait: 0.25,
  firstWait: 0.6,
  lostAfter: 2,
}

/** Where the beat stands. `waiting` for a first card; `seeded` firing on the seed or the pin
 *  before the beat has been heard; `locked` on a measured period and phase; `idle` because the
 *  same card has sat at the lens through two fires. */
export type Beat = 'waiting' | 'seeded' | 'locked' | 'idle'

/** The settle machine's events, plus the two that are this machine's own. `fire` is `fire`
 *  whether quiet or blind — the screen dispatches on it and the trace counts it — and the
 *  blind ones are a counter beside it. */
export type CadenceEvent = MotionEvent | 'cadence:locked' | 'cadence:lost'

/** The settle machine's readout, with the beat's own fields beside it. `phase` stays the
 *  signal machine's phase — what the region is doing this frame — and `beat` is what THIS
 *  machine is doing about it. The HUD reads both. */
export type CadenceDiagnostics = MotionDiagnostics & {
  beat: Beat
  /** The period in force: the pin, else the measurement, else the seed. */
  periodMs: number
  /** The measured period, or null before the beat has locked. */
  measuredMs: number | null
  /** The autocorrelation the current lock stands on; 0 until one exists. */
  beatCoeff: number
  pinned: boolean
  /** Fires taken on a frame the machine could not call quiet. */
  blindFires: number
}

export type CadenceControls = MotionControls & {
  /** Hold the period at `ms`, or `null` to let the measurement decide again. The phase is
   *  still measured either way — a pin says how fast the feeder runs, not where in the
   *  cycle the card rests. */
  pinPeriod(ms: number | null): void
}

/* The resampling grid the autocorrelation runs on. 10 ms is a quarter of a frame at 24 fps,
 * so a lag resolves to better than a frame without the estimate costing anything. */
const ACF_STEP_MS = 10

export class CadenceMachine {
  private readonly p: CadenceParams
  private readonly inner: MotionMachine

  /* The motion signal, timestamped, as a ring — `windowMs` at 125 fps, `motion.ts`'s
   * capacity rule. Only frames with a card present are folded or correlated, and the
   * ring is cleared when the beat is lost, so an empty stand cannot teach it a period. */
  private readonly times: Float64Array
  private readonly ds: Float32Array
  private head = 0
  private count = 0
  private scratchT: Float64Array
  private scratchD: Float32Array
  private grid: Float32Array

  private beat: Beat = 'waiting'
  private pinnedMs: number | null = null
  private measuredMs: number | null = null
  private coeff = 0
  /** Absolute phase of the rest, in ms modulo the period, or null before a lock. */
  private restPhase: number | null = null
  /** The predicted rest this machine is waiting to fire on. */
  private nextAt: number | null = null
  private presentSince: number | null = null
  private absentSince: number | null = null
  private lastFireAt: number | null = null
  private lastFired: Float32Array | null = null
  private unchangedRun = 0
  private frameNo = 0
  /** The last signal decided on, live or replayed, so `publish` shows the numbers the
   *  decision was made on rather than an inner machine a replay never stepped. */
  private signal: {
    d: number
    dBase: number
    tLo: number
    tHi: number
    presenceFloor: number
    hasBaseline: boolean
  } | null = null

  readonly diag: CadenceDiagnostics

  constructor(params: CadenceParams = DEFAULT_CADENCE) {
    this.p = params
    this.inner = new MotionMachine(params.motion)
    const capacity = Math.max(64, Math.ceil((params.windowMs / 1000) * 125))
    this.times = new Float64Array(capacity)
    this.ds = new Float32Array(capacity)
    this.scratchT = new Float64Array(capacity)
    this.scratchD = new Float32Array(capacity)
    this.grid = new Float32Array(Math.ceil(params.windowMs / ACF_STEP_MS) + 1)
    this.diag = {
      ...this.inner.diag,
      beat: 'waiting',
      periodMs: params.periodSeedMs,
      measuredMs: null,
      beatCoeff: 0,
      pinned: false,
      blindFires: 0,
    }
  }

  /** The period in force this frame. */
  private get periodMs(): number {
    return this.pinnedMs ?? this.measuredMs ?? this.p.periodSeedMs
  }

  /** The settle machine's control, passed through: the baseline is its. Dropping the beat
   *  with it, because a baseline retaken with the stand empty means the run is starting
   *  over and the first card owes a fresh first fire. */
  rebaseline(): void {
    this.inner.rebaseline()
    this.dropBeat()
    this.signal = null
    this.publish()
  }

  pinPeriod(ms: number | null): void {
    const clean =
      ms === null || !Number.isFinite(ms)
        ? null
        : Math.min(this.p.maxPeriodMs, Math.max(this.p.minPeriodMs, ms))
    this.pinnedMs = clean
    if (this.beat === 'seeded' || this.beat === 'locked') this.schedule(this.lastFireAt)
    this.publish()
  }

  /** One decoded frame, the settle machine's own contract: `cells` is the sampler's reused
   *  buffer and anything kept is copied. */
  step(nowMs: number, cells: Uint8ClampedArray | Float32Array): CadenceEvent | null {
    /* The signal machine runs first and its verdict is discarded: what this frame needs
     * from it is `d`, `dBase`, `tLo`, `tHi`, the presence floor and whether a baseline
     * exists. Its counters are overwritten in `publish`, so the HUD shows this machine's
     * fires and not a settle count nobody acted on. */
    const settled = this.inner.step(nowMs, cells) === 'fire'
    return this.stepSignal(nowMs, cells, this.inner.diag, settled)
  }

  /** The decision alone, on a signal somebody else measured. `step` is the live path; this
   *  is the REPLAY path — a saved trace carries every frame's `d` and `dBase` and the
   *  watch-region pixels of the verdict frames only, so a replay has the signal and not the
   *  picture. `cells` here is whatever the replay can offer the novelty gate; the traces in
   *  `app/tests/cadence.spec.ts` hand it a frame counter, which disables that gate on
   *  purpose and says so there. */
  stepSignal(
    nowMs: number,
    cells: Uint8ClampedArray | Float32Array,
    signal: {
      d: number
      dBase: number
      tLo: number
      tHi: number
      presenceFloor: number
      hasBaseline: boolean
    },
    /** Whether the settle machine fired on this frame. THE DUAL (D131): a settle is the
     *  photograph of choice — it lands on a frame the machine could call still — and the
     *  beat is the backstop for the card that never rests. */
    settled = false,
  ): CadenceEvent | null {
    this.frameNo += 1
    const { d, dBase, tLo, tHi, presenceFloor, hasBaseline } = signal
    this.signal = { d, dBase, tLo, tHi, presenceFloor, hasBaseline }
    const event = this.decide(nowMs, cells, d, dBase, tLo, tHi, presenceFloor, hasBaseline, settled)
    this.publish()
    return event
  }

  private decide(
    nowMs: number,
    cells: Uint8ClampedArray | Float32Array,
    d: number,
    dBase: number,
    tLo: number,
    tHi: number,
    presenceFloor: number,
    hasBaseline: boolean,
    settled: boolean,
  ): CadenceEvent | null {
    /* No baseline, no opinion about presence, no fire — the fifty-millisecond window at
     * arm time while the settle machine takes its first still run. */
    if (!hasBaseline) return null

    const present = dBase >= presenceFloor
    if (!present) {
      this.presentSince = null
      if (this.absentSince === null) this.absentSince = nowMs
      if (this.beat !== 'waiting' && nowMs - this.absentSince > this.p.lostAfter * this.periodMs) {
        this.dropBeat()
        return 'cadence:lost'
      }
      /* A scheduled fire that lands on an empty stand is refused for the settle machine's
       * reason and counted the same way, and the schedule moves on a period rather than
       * waiting at the rest for a card that is not there. */
      if (this.nextAt !== null && nowMs >= this.nextAt + this.p.quietWait * this.periodMs) {
        this.nextAt += this.periodMs
        this.diag.suppressedNoCard += 1
        this.diag.noCardRun += 1
        return 'suppressed:no-card'
      }
      return null
    }
    this.absentSince = null
    if (this.presentSince === null) this.presentSince = nowMs
    this.push(nowMs, d)

    let event: CadenceEvent | null = null
    if (this.frameNo % this.p.refreshFrames === 0) {
      if (this.estimate(nowMs)) event = 'cadence:locked'
    }

    const quiet = d < tLo

    if (this.beat === 'waiting') {
      /* THE FIRST CARD. Quiet fires it; a card that never goes quiet is fired on anyway
       * after `firstWait` of a period, because the alternative is the loss this machine
       * exists to end. Either way this fire anchors the seeded schedule. */
      if (settled || quiet || nowMs - this.presentSince >= this.p.firstWait * this.periodMs) {
        this.beat = this.measuredMs !== null ? 'locked' : 'seeded'
        return this.fire(nowMs, cells, !(settled || quiet)) ?? event
      }
      return event
    }

    if (this.beat === 'idle') {
      /* The feeder stopped with a card at the lens. Motion above tHi means it started
       * again, and the next card is treated as a FIRST card — fired on its first quiet frame
       * — because the onset of motion says nothing about where the rest will fall. The
       * measurement is kept; the schedule resumes from that fire. */
      if (d > tHi) {
        this.beat = 'waiting'
        this.unchangedRun = 0
        this.presentSince = nowMs
        this.nextAt = null
      }
      return event
    }

    // SEEDED or LOCKED: fire at the rest.
    if (this.nextAt === null) this.schedule(this.lastFireAt)
    /* THREE TIERS INSIDE THE WINDOW. A quiet frame (under tLo) is taken from `restLead`
     * before the predicted rest; from the rest itself a frame merely under tHi — not still,
     * not swapping either — is taken rather than waited past, because on the first session
     * half the cards never showed a quiet frame at all and the deadline fire that followed
     * landed on the swap at d 16; and at the deadline whatever is there is taken. Every fire
     * above tLo counts as blind, so the HUD's number is the count of photographs taken on a
     * frame the machine could not call still, whichever tier took it. */
    const nextAt = this.nextAt as number
    const P = this.periodMs
    /* SETTLE FIRST (D131). A settle verdict from the signal machine is a card at rest,
     * photographed on a frame it could call still — the accuracy the settle trigger has on
     * a feeder that pauses. It is taken whenever it comes, at least half a period after the
     * last fire (the `schedule` floor, so a late settle cannot chain onto the beat's fire
     * for the same card), and it re-anchors the beat. The scheduled fire below is then the
     * BACKSTOP: it only runs when a whole rest window has passed with no settle. */
    if (settled && nowMs >= nextAt - 0.5 * P) {
      return this.fire(nowMs, cells, false) ?? event
    }
    if (nowMs >= nextAt - this.p.restLead * P) {
      const calm = d < tHi
      if (quiet || (nowMs >= nextAt && calm) || nowMs >= nextAt + this.p.quietWait * P) {
        return this.fire(nowMs, cells, !quiet) ?? event
      }
    }
    return event
  }

  /** The two gates, then the fire. Returns the verdict, or null when nothing was decided. */
  private fire(
    nowMs: number,
    cells: Uint8ClampedArray | Float32Array,
    blind: boolean,
  ): CadenceEvent | null {
    if (this.lastFired !== null) {
      let novelty = 0
      for (let i = 0; i < cells.length; i += 1) {
        novelty += Math.abs((cells[i] as number) - (this.lastFired[i] as number))
      }
      if (novelty / cells.length < this.p.motion.tNovel) {
        this.diag.suppressedUnchanged += 1
        this.unchangedRun += 1
        if (this.unchangedRun >= 2) {
          this.beat = 'idle'
          this.nextAt = null
        } else {
          this.nextAt = (this.nextAt ?? nowMs) + this.periodMs
        }
        return 'suppressed:unchanged'
      }
    }
    this.unchangedRun = 0
    this.diag.noCardRun = 0
    this.lastFired = this.lastFired ?? new Float32Array(cells.length)
    this.lastFired.set(cells)
    this.lastFireAt = nowMs
    this.diag.fires += 1
    if (blind) this.diag.blindFires += 1
    this.schedule(nowMs)
    return 'fire'
  }

  /** Set `nextAt` to the next rest after `after` (or now, with no anchor), never closer
   *  than half a period to the last fire so a late fire cannot chain into a second one on
   *  the same card. Locked, the rest is the measured phase; seeded, it is a period on from
   *  the anchor — which is the last fire, and so the last observed rest. */
  private schedule(after: number | null): void {
    const P = this.periodMs
    const anchor = after ?? this.lastFireAt
    if (anchor === null) {
      this.nextAt = null
      return
    }
    const floor = anchor + 0.5 * P
    if (this.beat === 'locked' && this.restPhase !== null) {
      const offset = (((this.restPhase - floor) % P) + P) % P
      this.nextAt = floor + offset
    } else {
      this.nextAt = anchor + P
    }
  }

  private dropBeat(): void {
    this.beat = 'waiting'
    this.nextAt = null
    this.restPhase = null
    this.measuredMs = null
    this.coeff = 0
    this.presentSince = null
    this.absentSince = null
    this.unchangedRun = 0
    this.lastFired = null
    this.lastFireAt = null
    this.head = 0
    this.count = 0
  }

  private push(t: number, d: number): void {
    const capacity = this.times.length
    this.times[this.head] = t
    this.ds[this.head] = d
    this.head = (this.head + 1) % capacity
    if (this.count < capacity) this.count += 1
  }

  /** Copy the window's card-present frames, oldest first, into the scratch arrays; returns
   *  how many. */
  private window(nowMs: number): number {
    const capacity = this.times.length
    const cutoff = nowMs - this.p.windowMs
    let n = 0
    for (let i = this.count - 1; i >= 0; i -= 1) {
      const at = (this.head - 1 - i + capacity * 2) % capacity
      const t = this.times[at] as number
      if (t < cutoff) continue
      this.scratchT[n] = t
      this.scratchD[n] = this.ds[at] as number
      n += 1
    }
    return n
  }

  /** Re-estimate the period and the rest phase. Returns true on the frame the beat LOCKS
   *  (seeded/idle to locked); a lock that merely refreshes returns false. */
  private estimate(nowMs: number): boolean {
    if (this.presentSince === null || nowMs - this.presentSince < this.p.lockAfterMs) return false
    const n = this.window(nowMs)
    if (n < 8) return false
    const span = (this.scratchT[n - 1] as number) - (this.scratchT[0] as number)
    if (span < this.p.lockAfterMs) return false

    /* Resample onto the grid — the frames are not evenly spaced and an autocorrelation
     * over indices would read a dropped frame as a shorter beat. */
    const t0 = this.scratchT[0] as number
    const points = Math.min(this.grid.length, Math.floor(span / ACF_STEP_MS))
    let j = 0
    let mean = 0
    for (let g = 0; g < points; g += 1) {
      const t = t0 + g * ACF_STEP_MS
      while (j + 1 < n && (this.scratchT[j + 1] as number) <= t) j += 1
      const v = this.scratchD[j] as number
      this.grid[g] = v
      mean += v
    }
    mean /= points
    let variance = 0
    for (let g = 0; g < points; g += 1) {
      const v = (this.grid[g] as number) - mean
      this.grid[g] = v
      variance += v * v
    }
    if (variance <= 0) return false

    /* Only lags the window can hold three of are believed: shorter windows pick their
     * own length. */
    const minLag = Math.floor(this.p.minPeriodMs / ACF_STEP_MS)
    const maxLag = Math.min(
      Math.floor(this.p.maxPeriodMs / ACF_STEP_MS),
      Math.floor(points / 3),
    )
    if (maxLag <= minLag) return false

    const corr = (lag: number): number => {
      let sum = 0
      for (let g = 0; g + lag < points; g += 1) {
        sum += (this.grid[g] as number) * (this.grid[g + lag] as number)
      }
      return (sum / variance) * (points / (points - lag))
    }

    /* THE PEAK MUST BE A PEAK. A single burst of motion correlates with itself at every
     * short lag and decays from there, so the strongest lag of a non-periodic window is
     * simply the shortest one allowed — a synthetic feeder that stopped after one card
     * locked at 300 ms this way. A beat has a trough between zero and its period; the lag
     * taken is an interior local maximum with a trough under half its height before it. */
    let bestLag = -1
    let best = -Infinity
    let trough = Infinity
    let prev = corr(minLag)
    let cur = corr(minLag + 1)
    for (let lag = minLag + 1; lag < maxLag; lag += 1) {
      const next = corr(lag + 1)
      trough = Math.min(trough, prev)
      if (cur > prev && cur >= next && cur > best && trough < 0.5 * cur) {
        best = cur
        bestLag = lag
      }
      prev = cur
      cur = next
    }
    if (bestLag < 0) return false
    /* THE HARMONIC. A square-wave beat correlates almost as well with itself two cycles
     * on as one, and a noisy window can rank the double higher. The shortest lag scoring
     * `harmonicRatio` of the peak is the fundamental. */
    for (const k of [3, 2]) {
      const sub = Math.round(bestLag / k)
      if (sub >= minLag && corr(sub) >= this.p.harmonicRatio * best) {
        bestLag = sub
        break
      }
    }
    if (best < this.p.lockCoeff) return false

    this.measuredMs = bestLag * ACF_STEP_MS
    this.coeff = best
    const P = this.periodMs
    this.restPhase = this.foldRest(n, P)

    const wasLocked = this.beat === 'locked'
    if (this.beat === 'seeded') this.beat = 'locked'
    if (this.beat === 'locked') this.schedule(this.lastFireAt)
    return this.beat === 'locked' && !wasLocked
  }

  /** The phase (ms modulo `P`, absolute clock) at which the window's motion is least. */
  private foldRest(n: number, P: number): number {
    const bins = this.p.restBins
    const sums = new Float64Array(bins)
    const counts = new Uint32Array(bins)
    for (let i = 0; i < n; i += 1) {
      const t = this.scratchT[i] as number
      const b = Math.min(bins - 1, Math.floor((((t % P) + P) % P) / P * bins))
      sums[b] = (sums[b] as number) + (this.scratchD[i] as number)
      counts[b] = (counts[b] as number) + 1
    }
    let bestBin = 0
    let bestMean = Infinity
    for (let b = 0; b < bins; b += 1) {
      if ((counts[b] as number) === 0) continue
      const m = (sums[b] as number) / (counts[b] as number)
      if (m < bestMean) {
        bestMean = m
        bestBin = b
      }
    }
    return ((bestBin + 0.5) / bins) * P
  }

  private publish(): void {
    const own = {
      fires: this.diag.fires,
      suppressedUnchanged: this.diag.suppressedUnchanged,
      suppressedNoCard: this.diag.suppressedNoCard,
      noCardRun: this.diag.noCardRun,
      blindFires: this.diag.blindFires,
    }
    Object.assign(this.diag, this.inner.diag, this.signal, own, {
      stalled: 0,
      beat: this.beat,
      periodMs: this.periodMs,
      measuredMs: this.measuredMs,
      beatCoeff: this.coeff,
      pinned: this.pinnedMs !== null,
    })
  }
}

export function cadenceTrigger(
  video: RefObject<HTMLVideoElement | null>,
  onDiagnostics?: (diag: CadenceDiagnostics) => void,
  params: CadenceParams = DEFAULT_CADENCE,
  onFrame?: (
    tMs: number,
    d: number,
    dBase: number,
    luma: number,
    event: CadenceEvent | null,
    cells: Float32Array,
  ) => void,
  controls?: RefObject<CadenceControls | null>,
): Trigger {
  return {
    name: 'cadence',

    start(onFire) {
      const machine = new CadenceMachine(params)
      if (controls !== undefined) {
        controls.current = {
          rebaseline: () => machine.rebaseline(),
          pinPeriod: (ms) => machine.pinPeriod(ms),
        }
      }

      let lastDiagAt = 0
      const report = (now: number, always: boolean) => {
        if (onDiagnostics === undefined) return
        if (!always && now - lastDiagAt < DIAG_INTERVAL_MS) return
        lastDiagAt = now
        onDiagnostics({ ...machine.diag })
      }

      const stop = startWatchSampler(video, (nowMs, roi) => {
        const event = machine.step(nowMs, roi)
        if (event === 'fire') onFire()
        if (onFrame !== undefined) {
          onFrame(nowMs, machine.diag.d, machine.diag.dBase, machine.diag.luma, event, roi)
        }
        report(nowMs, event !== null)
      })

      return () => {
        stop()
        if (controls !== undefined) controls.current = null
      }
    },
  }
}
