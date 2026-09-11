import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

import { expect, test } from '@playwright/test'

import { CadenceMachine, DEFAULT_CADENCE } from '../src/cadence'
import type { CadenceEvent } from '../src/cadence'
import { DEFAULT_PARAMS } from '../src/motion'

/* The cadence machine (D130) — trigger 2 — against the two recordings that convicted the
 * settle rule, and against synthetic sequences with an exact answer key.
 *
 * TWO KINDS OF CASE, AND THE FIRST IS THE ONE THAT EARNS THE FILE. `harness/traces/`'s two
 * 2026-09-11 sessions are the owner's own feeder, re-arranged, saved from the HUD while the
 * settle trigger fired on 5 of 29 and 5 of 34 cards. Replayed here through the cadence
 * machine, causally — the period and the phase re-estimated every `refreshFrames` from
 * nothing but the frames already seen — with the coverage pinned. Those counts are a
 * tripwire in T9's sense: legitimately movable as a decision with the replay re-run, never as
 * a reflex. The synthetic cases prove the rest of the contract — the wait for a first card,
 * the idle on a stopped feeder, the lost beat on an emptied stand, the pin — the way
 * `motion.spec.ts` proves the settle machine's.
 *
 * WHAT THE REPLAY CANNOT SEE, SAID PLAINLY. A trace carries every frame's `d` and `dBase` and
 * the watch-region pixels of the VERDICT frames only, so the replay has the signal and not the
 * picture. `stepSignal` takes the signal directly, and the `cells` handed to it are a frame
 * counter — one cell that changes every frame — which disables the novelty gate. That gate is
 * proved on synthetic frames below, where the pixels exist. The thresholds are the ones the
 * scorer's summary reports for these two sessions (`tLo` 2.8-4.5, `tHi` 5-8) rather than
 * re-derived here, because what is under test is the schedule and not the noise tracker.
 *
 * NO PAGE, NO SERVER: `CadenceMachine` is pure, the same reason `motion.spec.ts` gives.
 */

const HERE = fileURLToPath(new URL('.', import.meta.url))

/** The two sessions, named as repo-relative paths so `make docs-audit`'s `tested_by reach`
 *  row can resolve them, and keyed to what the settle trigger did live on each — the number
 *  this machine exists to beat. `first` is when the feeder's first card reached the lens,
 *  read off the trace's own `dBase` crossing the floor. */
const TRACES = {
  'harness/traces/motion-trace-2026-09-11T01-48-49-706Z.json': { liveFires: 5, first: 31_500 },
  'harness/traces/motion-trace-2026-09-11T01-51-27-783Z.json': { liveFires: 5, first: 13_500 },
} as const

type Trace = { frames: Array<[number, number, number, number]> }

function load(rel: string): Trace {
  return JSON.parse(readFileSync(new URL(`../../${rel}`, `file://${HERE}`), 'utf8')) as Trace
}

/** Replay a saved trace through the machine, causally. Returns every verdict with its time
 *  and the frame's own `d`, and the machine for its readout. */
function replay(trace: Trace) {
  const machine = new CadenceMachine(DEFAULT_CADENCE)
  const counter = new Float32Array(1)
  const events: Array<{ t: number; event: CadenceEvent; d: number }> = []
  for (const [t, d, dBase] of trace.frames) {
    counter[0] = (counter[0] as number) + 1
    const event = machine.stepSignal(t, counter, {
      d,
      dBase,
      tLo: 3.5,
      tHi: 7.0,
      presenceFloor: DEFAULT_PARAMS.presenceMin,
      hasBaseline: true,
    })
    if (event !== null) events.push({ t, event, d })
  }
  return { machine, events }
}

for (const [rel, key] of Object.entries(TRACES)) {
  test(`replay ${rel.slice(-29, -5)}: the cadence photographs the cards the settle rule missed`, () => {
    const trace = load(rel)
    const { machine, events } = replay(trace)
    const fires = events.filter((e) => e.event === 'fire')
    const end = trace.frames[trace.frames.length - 1]?.[0] ?? 0

    /* Nothing fires on the empty stand: the first fire is the first card. */
    expect(fires[0]?.t ?? Infinity).toBeGreaterThanOrEqual(key.first)

    /* THE BEAT IS HEARD. Locked once feeding has run `lockAfterMs`, and the measured period
     * is the feeder's — 0.867 s off 29 luma cycles by hand. */
    expect(events.some((e) => e.event === 'cadence:locked')).toBe(true)
    expect(machine.diag.beat).toBe('locked')
    expect(machine.diag.measuredMs).toBeGreaterThanOrEqual(840)
    expect(machine.diag.measuredMs).toBeLessThanOrEqual(940)

    /* COVERAGE. One fire per beat from the first card to the end of the recording, within a
     * card or two of what the feeder fed, and several times what the settle rule scored. The
     * exact count is the tripwire. */
    const span = end - (fires[0]?.t ?? end)
    const cardsFed = Math.round(span / 867)
    expect(fires.length).toBeGreaterThanOrEqual(cardsFed - 2)
    expect(fires.length).toBeGreaterThanOrEqual(key.liveFires * 3)

    /* No two fires closer than half a period: one photograph per card, never a chain. */
    const gaps = fires.slice(1).map((f, i) => f.t - (fires[i]?.t ?? 0))
    expect(Math.min(...gaps)).toBeGreaterThanOrEqual(0.5 * 840)

    /* And a fire lands on a still frame where the feeder allows one. On the first session
     * half the cards never showed one — the longest quiet run per card has a median of ONE
     * frame — so the blind share is high there by the feeder's doing, not the machine's. What
     * the rig run measures is whether those frames are photographs or blurs; here the bound
     * is that a still frame is taken whenever one exists in the window. */
    expect(machine.diag.blindFires).toBeLessThanOrEqual(Math.ceil(fires.length * 0.55))
  })
}

test('the pinned counts: what the replay reaches on each session today', () => {
  /* Recorded on 2026-09-11, the day the machine was built, against the two sessions above.
   * Move these as a decision with the replay re-run, never as a reflex — and if a change
   * LOWERS one, it is a change that loses cards on a feeder that really ran. */
  const reached = Object.fromEntries(
    Object.keys(TRACES).map((rel) => {
      const { machine, events } = replay(load(rel))
      return [
        rel.slice(-29, -5),
        { fires: events.filter((e) => e.event === 'fire').length, blind: machine.diag.blindFires },
      ]
    }),
  )
  /* 29 and ~21 cards were fed; the settle trigger photographed 5 and 5. */
  expect(reached).toEqual({
    '2026-09-11T01-48-49-706Z': { fires: 27, blind: 14 },
    '2026-09-11T01-51-27-783Z': { fires: 20, blind: 7 },
  })
})

/* ------------------------------------------------------------- synthetic sequences */

const F = 1000 / 24 // one frame at the rig's 24 fps, ms
const CELLS = 128
const EMPTY = 30

/** A still scene at `base` with deterministic sub-threshold noise, `motion.spec.ts`'s helper. */
function still(base: number, phase: number): Float32Array {
  const cells = new Float32Array(CELLS)
  for (let i = 0; i < CELLS; i += 1) {
    cells[i] = base + (((i * 31 + phase * 17) % 7) - 3) * 0.2
  }
  return cells
}

/** A driver over the LIVE path — `step`, with the settle machine underneath measuring the
 *  signal — so these cases exercise presence, the baseline and novelty for real. */
class Feed {
  readonly machine = new CadenceMachine(DEFAULT_CADENCE)
  t = 0
  frame = 0
  readonly events: Array<{ t: number; event: CadenceEvent }> = []

  /** `n` frames of a still scene at `base`. */
  hold(base: number, n: number): this {
    for (let i = 0; i < n; i += 1) this.push(still(base, this.frame))
    return this
  }

  /** `n` frames of motion: the scene alternating between two bases so every frame differs
   *  from the last by well over tHi. */
  churn(a: number, b: number, n: number): this {
    for (let i = 0; i < n; i += 1) this.push(still(i % 2 === 0 ? a : b, this.frame))
    return this
  }

  /** One feeder cycle at `periodMs`: the card arrives over half the period (churn), then sits
   *  for `quietFrames` frames, then the rest of the period churns as the next card slides in.
   *  `base` is the card; a different base per card is a different picture. */
  card(base: number, periodMs: number, quietFrames: number): this {
    const total = Math.round(periodMs / F)
    const arrive = Math.floor((total - quietFrames) / 2)
    this.churn(base, base + 60, arrive)
    this.hold(base, quietFrames)
    this.churn(base + 60, base, total - arrive - quietFrames)
    return this
  }

  private push(cells: Float32Array): void {
    this.t += F
    this.frame += 1
    const event = this.machine.step(this.t, cells)
    if (event !== null) this.events.push({ t: this.t, event })
  }

  fires(): number {
    return this.events.filter((e) => e.event === 'fire').length
  }
}

test('arms on an empty stand, waits for the first card, and fires on its first quiet frame', () => {
  const feed = new Feed().hold(EMPTY, 40)
  expect(feed.fires()).toBe(0)
  expect(feed.machine.diag.beat).toBe('waiting')
  expect(feed.machine.diag.hasBaseline).toBe(true)

  // A card arrives and sits: the first quiet frame after presence is the fire.
  feed.churn(EMPTY, 150, 6).hold(150, 3)
  expect(feed.fires()).toBe(1)
  expect(feed.machine.diag.beat).toBe('seeded')
  expect(feed.machine.diag.blindFires).toBe(0)
})

test('a card that never goes quiet is still photographed, blind, and counted as such', () => {
  const feed = new Feed().hold(EMPTY, 40)
  // Motion that never stops, with a card present throughout (both bases far from EMPTY).
  feed.churn(150, 210, 30)
  expect(feed.fires()).toBe(1)
  expect(feed.machine.diag.blindFires).toBe(1)
})

test('on the seed, a feeder that allows three quiet frames a card gets one fire per card', () => {
  const feed = new Feed().hold(EMPTY, 40)
  const P = DEFAULT_CADENCE.periodSeedMs
  /* THREE quiet frames, not two: since D131 the settle machine underneath fires on one
   * quiet frame of the last three under tHi, and a synthetic card that switches from
   * violent churn to rest and back in two frames never fills that window — the real
   * feeder's rest is two to four frames with calm frames around it. Two would leave every
   * fire here to the beat's backstop, which is a different claim from the one this test
   * makes. */
  for (let i = 0; i < 12; i += 1) feed.card(120 + i * 8, P, 3)
  /* Twelve cards, twelve fires, give or take the first cycle's anchoring. */
  expect(feed.fires()).toBeGreaterThanOrEqual(11)
  expect(feed.fires()).toBeLessThanOrEqual(13)
  /* THE DUAL (D131): every one of those came from the settle machine underneath, on a frame
   * it could call still — none from the beat's backstop. The backstop's own proof is the
   * never-quiet card above, where it is the only path that fires. */
  expect(feed.machine.diag.blindFires).toBe(0)
  expect(feed.machine.diag.beat).toBe('locked')
  expect(feed.machine.diag.measuredMs).toBeGreaterThanOrEqual(P - 60)
  expect(feed.machine.diag.measuredMs).toBeLessThanOrEqual(P + 60)
})

test('the same card sitting through two beats puts the machine to sleep, and motion wakes it', () => {
  const feed = new Feed().hold(EMPTY, 40)
  const P = DEFAULT_CADENCE.periodSeedMs
  feed.card(150, P, 2)
  const after = feed.fires()
  expect(after).toBeGreaterThanOrEqual(1)
  // The feeder stops with the card at the lens: three periods of the same picture.
  feed.hold(150, Math.round((3 * P) / F))
  expect(feed.fires()).toBe(after)
  expect(feed.machine.diag.suppressedUnchanged).toBe(2)
  expect(feed.machine.diag.beat).toBe('idle')
  // It starts again: a new card, a new fire.
  feed.card(200, P, 2)
  expect(feed.fires()).toBe(after + 1)
  expect(feed.machine.diag.beat).not.toBe('idle')
})

test('a stand emptied for two beats loses the beat, and the next card is a first card again', () => {
  const feed = new Feed().hold(EMPTY, 40)
  const P = DEFAULT_CADENCE.periodSeedMs
  feed.card(150, P, 2)
  feed.churn(150, EMPTY, 4).hold(EMPTY, Math.round((2.5 * P) / F))
  expect(feed.events.some((e) => e.event === 'cadence:lost')).toBe(true)
  expect(feed.machine.diag.beat).toBe('waiting')
  const before = feed.fires()
  feed.churn(EMPTY, 180, 6).hold(180, 3)
  expect(feed.fires()).toBe(before + 1)
  expect(feed.machine.diag.beat).toBe('seeded')
})

test('a pinned period is clamped to the band and overrides the seed and the measurement', () => {
  const feed = new Feed().hold(EMPTY, 40)
  feed.machine.pinPeriod(50)
  expect(feed.machine.diag.periodMs).toBe(DEFAULT_CADENCE.minPeriodMs)
  expect(feed.machine.diag.pinned).toBe(true)
  feed.machine.pinPeriod(1200)
  expect(feed.machine.diag.periodMs).toBe(1200)
  feed.machine.pinPeriod(null)
  expect(feed.machine.diag.periodMs).toBe(DEFAULT_CADENCE.periodSeedMs)
  expect(feed.machine.diag.pinned).toBe(false)
})

test('re-baselining drops the beat with the baseline', () => {
  const feed = new Feed().hold(EMPTY, 40)
  feed.card(150, DEFAULT_CADENCE.periodSeedMs, 2)
  expect(feed.machine.diag.beat).not.toBe('waiting')
  feed.machine.rebaseline()
  expect(feed.machine.diag.beat).toBe('waiting')
  expect(feed.machine.diag.hasBaseline).toBe(false)
})
