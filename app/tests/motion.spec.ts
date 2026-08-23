import { expect, test } from '@playwright/test'

import { DEFAULT_PARAMS, MotionMachine } from '../src/motion'
import type { MotionEvent } from '../src/motion'

/* The motion machine against synthetic frame sequences with an exact answer key — the
 * same trick T6 plays with synthetic composites, carrying the same honest limit: this
 * proves the arithmetic is self-consistent, NOT that the trigger works at the rig. The
 * rig half (sampling a real <video>, real lighting, the real feeder rhythm) is exactly
 * the part a browserless test cannot reach, and docs/specs/motion-trigger.md's tuning
 * protocol is what covers it.
 *
 * No page, no server: MotionMachine is pure — `step(nowMs, cells)` in, event out — which
 * is the whole reason it is a class apart from the DOM wrapper. Frames are small arrays
 * (the machine takes any length) built by `still()` with deterministic sub-threshold
 * noise, so every run of this file sees identical inputs.
 *
 * The clock is hand-fed at 30fps. Every threshold crossed below is crossed by a value
 * derived from the Gate B measurements the parameters came from: noise ~0.35, swaps
 * 14-92, card luma ~172 against an empty stand's 30-65.
 */

const F = 1000 / 30 // one frame at 30fps, ms
const CELLS = 128

/** A still scene at `base` luma with deterministic noise well under tLo. `phase` varies
 *  the noise pattern so two calls with the same base are the same SCENE but not the same
 *  bytes — consecutive frames of a real still card differ a little, and a test that feeds
 *  byte-identical frames would let d = 0 hide a broken diff. */
function still(base: number, phase: number): Float32Array {
  const cells = new Float32Array(CELLS)
  for (let i = 0; i < CELLS; i += 1) {
    cells[i] = base + (((i * 31 + phase * 17) % 7) - 3) * 0.2
  }
  return cells
}

/** Run a sequence through a fresh machine, returning every non-null event with its frame
 *  index. `frames` are (base, isCard-irrelevant) luma levels; motion is just consecutive
 *  frames whose bases differ by more than the thresholds. */
function run(
  machine: MotionMachine,
  bases: number[],
  startMs = 0,
): Array<{ at: number; event: MotionEvent }> {
  const events: Array<{ at: number; event: MotionEvent }> = []
  bases.forEach((base, index) => {
    const event = machine.step(startMs + index * F, still(base, index))
    if (event !== null) events.push({ at: index, event })
  })
  return events
}

test('a still empty scene is judged empty exactly once, then stays silent', () => {
  const machine = new MotionMachine()
  // 100 frames of dark desk. Below cardLumaFloor, but no-card suppression requires a
  // settle EPISODE to judge — and an empty scene at arm time is judged exactly once.
  const events = run(machine, Array<number>(100).fill(40))
  expect(events).toEqual([{ at: 2, event: 'suppressed:no-card' }])
  expect(machine.diag.fires).toBe(0)
})

test('a card already at the lens when the trigger is armed is captured once', () => {
  const machine = new MotionMachine()
  // Frame 0 seeds prev; frames 1-2 are the still run (stillFrames = 2); the verdict lands
  // on frame 2 and never re-fires while the card sits.
  const events = run(machine, Array<number>(60).fill(170))
  expect(events).toEqual([{ at: 2, event: 'fire' }])
})

test('swap, settle, fire — and the same card settling again is suppressed', () => {
  const machine = new MotionMachine()
  const events = run(machine, [
    // card A settles and fires (frame 2)
    170, 170, 170, 170, 170, 170, 170, 170, 170, 170,
    // the feeder bumps the tray: motion, then card A settles AGAIN — same picture,
    // so the novelty gate suppresses instead of double-capturing
    60, 190, 55, 185, 170, 170, 170, 170, 170, 170,
    // card B arrives: motion, then a genuinely different picture — fires
    60, 200, 50, 210, 120, 120, 120, 120, 120, 120,
  ])
  expect(events.map((e) => e.event)).toEqual(['fire', 'suppressed:unchanged', 'fire'])
  expect(machine.diag.fires).toBe(2)
  expect(machine.diag.suppressedUnchanged).toBe(1)
})

test('motion that settles on an empty stand is suppressed as no-card', () => {
  const machine = new MotionMachine()
  const events = run(machine, [
    170, 170, 170, 170, 170, // card fires at frame 2
    60, 200, 50, 210, // card pulled out: motion...
    40, 40, 40, 40, 40, // ...and the empty stand settles
  ])
  expect(events.map((e) => e.event)).toEqual(['fire', 'suppressed:no-card'])
})

test('continuous motion past maxMoveMs reports stalled exactly once, and never fires', () => {
  const machine = new MotionMachine()
  // Alternating bright/dark every frame: d stays huge. 1250ms at 33.3ms/frame is ~38
  // frames; give it 60 and expect one stall, zero fires.
  const bases: number[] = []
  for (let i = 0; i < 60; i += 1) bases.push(i % 2 === 0 ? 60 : 200)
  const events = run(machine, bases)
  expect(events.map((e) => e.event)).toEqual(['stalled'])
  expect(machine.diag.fires).toBe(0)
})

test('motion dwelling in the Schmitt band still stalls — the band cannot hide a jam', () => {
  const machine = new MotionMachine()
  const events: MotionEvent[] = []
  // Enter MOVING once, then hover in the band (d between tLo 3.0 and tHi 6.0) — a hand
  // resting half-in-frame. The stall clock must keep running even though d never crosses
  // tHi again. Base alternation of ±2.2 gives d ≈ 4.4, inside the band.
  let ms = 0
  const feed = (base: number, phase: number) => {
    const event = machine.step(ms, still(base, phase))
    if (event !== null) events.push(event)
    ms += F
  }
  feed(170, 0)
  feed(60, 1) // violent: MOVING starts
  for (let i = 0; i < 50; i += 1) feed(i % 2 === 0 ? 60 : 64.4, i + 2) // band hover
  expect(events).toEqual(['stalled'])
  expect(machine.diag.fires).toBe(0)
})

test('the refractory defers a fast settle instead of dropping it', () => {
  const machine = new MotionMachine()
  const events: Array<{ ms: number; event: MotionEvent }> = []
  const feed = (ms: number, base: number, phase: number) => {
    const event = machine.step(ms, still(base, phase))
    if (event !== null) events.push({ ms, event })
  }
  // Card A: seed, two stills — fires at ~67ms. Refractory runs to ~317ms.
  feed(0, 170, 0)
  feed(F, 170, 1)
  feed(2 * F, 170, 2)
  // Card B arrives IMMEDIATELY: motion at 100ms, settled from 133ms. The settle
  // completes inside the refractory window — the fire must arrive after the window
  // expires, not never.
  feed(3 * F, 60, 3)
  feed(4 * F, 120, 4)
  feed(5 * F, 120, 5)
  feed(6 * F, 120, 6) // still run complete at 200ms, refractory holds it
  feed(7 * F, 120, 7)
  feed(8 * F, 120, 8)
  feed(9 * F, 120, 9)
  feed(10 * F, 120, 10) // 333ms — past the refractory: the held fire lands here
  const fires = events.filter((e) => e.event === 'fire')
  expect(fires).toHaveLength(2)
  const second = fires[1]
  expect(second).toBeDefined()
  if (second !== undefined) {
    const first = fires[0]
    expect(first).toBeDefined()
    if (first !== undefined) {
      expect(second.ms - first.ms).toBeGreaterThanOrEqual(DEFAULT_PARAMS.refractoryMs)
    }
  }
})

test('the machine copies what it keeps — a reused, mutated buffer cannot zero the diff', () => {
  /* The sampler reuses one buffer for every frame, so a machine that held the reference
   * would compare the buffer to itself: d identically zero, a trigger that never fires,
   * no error anywhere. This feeds ONE array object, mutated in place between steps, and
   * expects the machine to behave exactly as if each frame had been a fresh array. */
  const machine = new MotionMachine()
  const buffer = new Float32Array(CELLS)
  const events: MotionEvent[] = []
  const feed = (ms: number, base: number, phase: number) => {
    buffer.set(still(base, phase))
    const event = machine.step(ms, buffer)
    if (event !== null) events.push(event)
  }
  feed(0, 170, 0)
  feed(F, 170, 1)
  feed(2 * F, 170, 2)
  expect(events).toEqual(['fire'])
})
