import { expect, test } from '@playwright/test'

import { DEFAULT_PARAMS, MotionMachine } from '../src/motion'
import type { MotionEvent } from '../src/motion'

/* The motion machine against synthetic frame sequences with an exact answer key — the
 * same trick T6 plays with synthetic composites, carrying the same honest limit: this
 * proves the arithmetic is self-consistent, NOT that the trigger works at the rig. The
 * rig half (sampling a real <video>, real lighting, the real feeder rhythm) is exactly
 * the part a browserless test cannot reach, and docs/specs/motion-trigger.md's tuning
 * protocol is what covers it. What DOES speak for the rig is `scripts/score-trace.py`,
 * which re-scores the owner's four saved traces offline; the numbers quoted below come
 * from it rather than from anybody's intuition.
 *
 * No page, no server: MotionMachine is pure — `step(nowMs, cells)` in, event out — which
 * is the whole reason it is a class apart from the DOM wrapper. Frames are small arrays
 * (the machine takes any length) built by `still()` with deterministic sub-threshold
 * noise, so every run of this file sees identical inputs.
 *
 * EVERY SEQUENCE HERE ARMS ON AN EMPTY STAND, and that is the contract rather than a
 * fixture convention (D81). The machine takes its BASELINE from the first still run after
 * arming and judges presence as distance from it, so what is on the stand at arm time is
 * what the session will call "nothing". The tuning protocol asks the operator for an empty
 * stand at arm for exactly this reason, and `armEmpty` below is that instruction in code.
 *
 * The clock is hand-fed at 30fps. Every threshold crossed below is crossed by a value
 * derived from real measurements: still noise well under tLo, swaps of 50-140 luma levels
 * against a tHi of 8.0, and card-versus-empty distances of 90-140 against a presence floor
 * of 16.0.
 *
 * A SETTLE TAKES `stillWindow` FRAMES TO REACH, NOT `stillFrames` (D84). The rule is
 * `stillFrames` of the last `stillWindow` and the window must be full, so every settle
 * below is four frames after the motion that opened the episode rather than two. That is
 * why the arm block is five frames and not three: one to seed `prev`, four to fill the
 * window. Feeding fewer is the commonest way to write a case here that proves nothing —
 * it produces no verdict at all, and an empty event list compares equal to an empty
 * expectation.
 */

const F = 1000 / 30 // one frame at 30fps, ms
const CELLS = 128

/** The empty stand these sequences arm against. Dark, like the real one: the reference
 *  rig's empty region measured a mean of 38 and the under-lit rig's 27-30. */
const EMPTY = 30

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

/** The frames every sequence starts with: an empty stand, still, at arm time. One seeds
 *  `prev` and the next `stillWindow` fill the stillness window, so the machine takes its
 *  baseline on the LAST of them and judges that first episode against itself — worth
 *  exactly one `suppressed:no-card`, the same single verdict an empty stand at arm has
 *  always been worth. Derived from the params rather than typed, because the two moved
 *  together in D84 and a hand-typed 5 would silently stop arming if either moved again. */
const ARM_FRAMES = DEFAULT_PARAMS.stillWindow + 1
function armEmpty(): number[] {
  return Array<number>(ARM_FRAMES).fill(EMPTY)
}

/** Run a sequence through a fresh machine, returning every non-null event with its frame
 *  index. `frames` are luma levels; motion is just consecutive frames whose bases differ
 *  by more than the thresholds. */
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
  /* 100 frames of dark desk. The verdict is not "this is dark" any more — it is "this is
     indistinguishable from the baseline I just took", which is the same claim about the
     same scene reached without a constant. One verdict per settle episode, and nothing
     opens a new one. */
  const events = run(machine, Array<number>(100).fill(EMPTY))
  expect(events).toEqual([{ at: DEFAULT_PARAMS.stillWindow, event: 'suppressed:no-card' }])
  expect(machine.diag.fires).toBe(0)
  expect(machine.diag.hasBaseline).toBe(true)
})

test('a card already at the lens when the trigger is armed BECOMES the baseline', () => {
  /* THE ONE BEHAVIOUR D81 TOOK AWAY, recorded here so it cannot be lost by accident and
     re-argued if it is ever wanted back.

     The old machine captured a card that was already at the lens when motion was armed,
     on the reasoning that arming the trigger is starting the run. It could only do that
     because the card was BRIGHT and the presence floor happened to sit under it — which is
     the exact mechanism the four saved traces convict, where an empty stand read 57 and a
     real card on another rig read 61. Nothing in a single frame distinguishes "the stand as
     it normally looks" from "the stand with a card on it"; that distinction needs a
     reference, and at arm time the reference is what is being established.

     So the arm-time scene is now the baseline whatever it is, and a card sitting in it is
     refused rather than captured. The cost is one photograph at the top of a run, and it is
     ANNOUNCED — `noCardRun` climbs and the screen renders the sentence. The old cost was
     twenty cards mid-run and silence. */
  const machine = new MotionMachine()
  const events = run(machine, Array<number>(60).fill(170))
  expect(events).toEqual([{ at: DEFAULT_PARAMS.stillWindow, event: 'suppressed:no-card' }])
  expect(machine.diag.fires).toBe(0)
})

test('swap, settle, fire — and the same card settling again is suppressed', () => {
  const machine = new MotionMachine()
  const events = run(machine, [
    ...armEmpty(),
    // card A arrives, settles and fires
    170, 170, 170, 170, 170, 170, 170, 170,
    // the feeder bumps the tray: motion, then card A settles AGAIN — same picture,
    // so the novelty gate suppresses instead of double-capturing
    60, 190, 55, 185, 170, 170, 170, 170, 170, 170,
    // card B arrives: motion, then a genuinely different picture — fires
    60, 200, 50, 210, 120, 120, 120, 120, 120, 120,
  ])
  expect(events.map((e) => e.event)).toEqual([
    'suppressed:no-card',
    'fire',
    'suppressed:unchanged',
    'fire',
  ])
  expect(machine.diag.fires).toBe(2)
  expect(machine.diag.suppressedUnchanged).toBe(1)
})

test('motion that settles back onto the empty stand is suppressed as no-card', () => {
  const machine = new MotionMachine()
  const events = run(machine, [
    ...armEmpty(),
    170, 170, 170, 170, 170, // card arrives and fires
    60, 200, 50, 210, // card pulled out: motion...
    EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, // ...and the stand settles empty
  ])
  expect(events.map((e) => e.event)).toEqual(['suppressed:no-card', 'fire', 'suppressed:no-card'])
})

test('a dim card on an under-lit rig is a card — no brightness floor could say so', () => {
  /* THE BUG THIS IS THE RECEIPT FOR, AND IT COST TWO REAL SESSIONS. The presence gate was a
     brightness compared against the constant 90. Scored over the owner's four saved traces
     (`scripts/score-trace.py`), the watch region's bright quantile reads:

         EMPTY STAND, reference rig  2026-08-23             57
         CARD,        under-lit rig  2026-08-29 21:34    61-134
         CARD,                       2026-09-01          77-171
         CARD,        reference rig  2026-08-23         196-244

     An empty stand at 57 and a real card at 61: four luma levels apart, on different days.
     No constant separates those populations, and the one in the file cut through the middle
     of three of them — 20 of 20 cards refused on 2026-08-29 21:34, 13 of 15 on 21:38, 5 of
     24 on 2026-09-01. 38 real cards called an empty stand, silently, by TWO versions of the
     gate — and 18 of them were still refused by the version that replaced the mean with the
     bright quantile, which is why this is not a fourth constant.

     THE NUMBERS BELOW ARE THE UNDER-LIT RIG'S. A card at 61 against a desk at 27 is a card
     the old gate could not fire on at any exposure, and the distance form fires on it
     without knowing anything about lamps. */
  const machine = new MotionMachine()
  const events = run(machine, [
    27, 27, 27, 27, 27, // the under-lit empty stand, at arm
    45, // the swap: motion
    61, 61, 61, 61, 61, 61, 61, // a dim card, settled
  ])

  /* The premise, asserted so a later reader does not have to trust the prose: this card is
     DARKER than the empty stand the old floor was tuned against (57), so a brightness gate
     with any constant that admits it also admits that empty stand. If the fixture ever
     drifts so the card is brighter than 57, the case below stops testing anything. */
  expect(61).toBeLessThan(90)
  expect(events.map((e) => e.event)).toEqual(['suppressed:no-card', 'fire'])
})

test('a run of no-card verdicts is counted consecutively, and a fire clears it', () => {
  /* `noCardRun` is the counter the 2026-08-29 sessions needed and did not have: twenty
     settles refused in a row while a box went through the lens, with nothing on screen but
     a total climbing beside six other totals. The screen renders three-in-a-row as the
     sentence it means. A TOTAL cannot say this — only a run can — which is why this is the
     one counter here that goes back down. */
  const machine = new MotionMachine()
  run(machine, [
    ...armEmpty(),
    // three swaps that each settle back onto the empty stand: nothing was ever presented
    60, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY,
    60, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY,
  ])
  expect(machine.diag.noCardRun).toBe(3)
  expect(machine.diag.suppressedNoCard).toBe(3)

  run(machine, [60, 170, 170, 170, 170, 170, 170, 170], 40 * F)
  expect(machine.diag.fires).toBe(1)
  expect(machine.diag.noCardRun).toBe(0)
})

test('rebaseline moves the session baseline to whatever is on the stand now', () => {
  /* The remedy the HUD's sentence points at. Arm on a card by mistake — the case above —
     then clear the stand and press it: the machine forgets, re-takes on the next still run,
     and the next real card fires. Without this the only cure for a bad baseline is
     disarming and re-arming, which throws away the trace and every counter with it. */
  const machine = new MotionMachine()
  const armedOnACard = run(machine, Array<number>(10).fill(170))
  expect(armedOnACard.map((e) => e.event)).toEqual(['suppressed:no-card'])

  machine.rebaseline()
  expect(machine.diag.hasBaseline).toBe(false)

  // The stand, now cleared, becomes the baseline; the card that follows is a card.
  const after = run(machine, [...armEmpty(), 90, 170, 170, 170, 170, 170, 170], 10 * F)
  expect(after.map((e) => e.event)).toEqual(['suppressed:no-card', 'fire'])
  expect(machine.diag.fires).toBe(1)
})

test('the thresholds are multiples of what THIS session measures, not constants', () => {
  /* THE OTHER HALF OF D81, and the receipt is the repo's own history. The 2026-08-23 retune
     (tLo 3.0 -> 4.5) was a person at a rig discovering that the live preview's noise floor is
     eleven times the stored JPEGs' one — after 14 of 86 cards had gone past the lens without
     ever reaching a verdict, silently. That is a measurement the machine can take in eight
     seconds, and now does: replayed against that same trace it reaches 86 of 86.

     THE SEED IS GATE C'S OWN PAIR, to the last digit, so nothing about the confirmed 85/85
     run is being re-litigated — the machine boots on it and adapts away from it. */
  const machine = new MotionMachine()
  expect(machine.diag.tLo).toBeCloseTo(4.5, 5)
  expect(machine.diag.tHi).toBeCloseTo(8.0, 5)

  /* A rig noisier than the one the constants came from: an empty stand whose frame-to-frame
     difference idles at ~3.5 rather than the reference rig's ~2.2. Under a constant tLo of
     4.5 that leaves barely a luma level of headroom, which is exactly the condition where a
     settle is reached late or not at all. The floor must climb off it by itself. */
  let ms = 0
  for (let i = 0; i < 150; i += 1) {
    machine.step(ms, still(i % 2 === 0 ? EMPTY : EMPTY + 3.5, i))
    ms += F
  }
  expect(machine.diag.dTypical).toBeGreaterThan(3)
  expect(machine.diag.tLo).toBeGreaterThan(6)
  expect(machine.diag.tHi).toBeGreaterThan(machine.diag.tLo)

  /* ONLY FRAMES ALREADY JUDGED STILL FEED THE ESTIMATE, which is what stops it learning
     that motion is quiet. Drive a burst well above tHi for longer than the window and the
     thresholds must not follow it up. */
  const before = machine.diag.tHi
  for (let i = 0; i < 60; i += 1) {
    machine.step(ms, still(i % 2 === 0 ? 40 : 200, 300 + i))
    ms += F
  }
  expect(machine.diag.tHi).toBeLessThanOrEqual(before)
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
  // Enter MOVING once, then hover in the band (d between tLo 4.5 and tHi 8.0) — a hand
  // resting half-in-frame. The stall clock must keep running even though d never crosses
  // tHi again. Base alternation of ±3.0 gives d ≈ 6.0, inside the band.
  let ms = 0
  const feed = (base: number, phase: number) => {
    const event = machine.step(ms, still(base, phase))
    if (event !== null) events.push(event)
    ms += F
  }
  feed(170, 0)
  feed(60, 1) // violent: MOVING starts
  for (let i = 0; i < 50; i += 1) feed(i % 2 === 0 ? 60 : 66, i + 2) // band hover
  expect(events).toEqual(['stalled'])
  expect(machine.diag.fires).toBe(0)
})

test('a card whose every other frame lands in the band still settles and fires', () => {
  /* D84'S FIRST HALF, AND IT IS A REGRESSION TEST FOR FOUR REAL CARDS. The rule used to be
     `stillFrames` CONSECUTIVE frames under tLo, and a two-frame alternation defeats that
     absolutely — a run of one, forever. Measured, not imagined: a card sitting motionless
     at the head of the 2026-09-01 21:10 session, 500 ms, against a tLo of 4.18:

         2.71  5.40  2.63  5.54  2.83  5.14  3.03  4.80  3.64  4.91

     Five separate runs of one, no verdict, and the card was replaced unphotographed with
     nothing on the HUD. `stillFrames` of the last `stillWindow` is satisfied by that
     pattern; the fixture below is that pattern, with the scene held still and only the
     sub-threshold noise moving. */
  const machine = new MotionMachine()
  const card: number[] = []
  // Pairs: 170,170,176,176,... so every step is alternately ~0 (under tLo) and ~6 (inside
  // the Schmitt band). The SCENE never changes — this is a still card, jittering.
  for (let i = 0; i < 12; i += 1) card.push(Math.floor(i / 2) % 2 === 0 ? 170 : 176)
  const events = run(machine, [...armEmpty(), ...card])
  expect(events.map((e) => e.event)).toEqual(['suppressed:no-card', 'fire'])
  expect(machine.diag.fires).toBe(1)
  expect(machine.diag.stalled).toBe(0)
})

test('a scene that never completes a settle is STALLED, however quiet its odd frame', () => {
  /* D84'S SECOND HALF, and the failure it closes was silent by construction. The stall
     clock used to be cleared by ANY single frame under tLo while a fire needed two in a
     row, so a scene quiet often enough to reset the clock but never often enough to settle
     could sit in front of the lens forever: no fire, no stall, nothing on screen. Across
     the three 2026-09-01 sessions — 93 seconds, four cards left unphotographed — the live
     machine raised not one `stalled`.

     One quiet frame in every four here: enough to have cleared the old clock every time,
     never enough for `stillFrames` of `stillWindow`. Cleared by a COMPLETED SETTLE instead,
     the clock expires and says so. */
  const machine = new MotionMachine()
  const bases: number[] = [60]
  for (let i = 1; i < 60; i += 1) {
    const last = bases[i - 1] as number
    bases.push(i % 4 === 0 ? last : last === 60 ? 66 : 60)
  }
  const events = run(machine, [...armEmpty(), ...bases])
  expect(events.map((e) => e.event)).toEqual(['suppressed:no-card', 'stalled'])
  expect(machine.diag.fires).toBe(0)
  expect(machine.diag.stalled).toBe(1)
})

test('the refractory defers a fast settle instead of dropping it', () => {
  const machine = new MotionMachine()
  const events: Array<{ ms: number; event: MotionEvent }> = []
  const feed = (ms: number, base: number, phase: number) => {
    const event = machine.step(ms, still(base, phase))
    if (event !== null) events.push({ ms, event })
  }
  // The empty stand at arm, which is where the baseline comes from (D81).
  let at = 0
  for (; at < ARM_FRAMES; at += 1) feed(at * F, EMPTY, at)
  // Card A: the swap, then a full window of stills — fires on the last of them, and the
  // refractory runs 250 ms from there.
  feed(at * F, 170, at)
  at += 1
  for (let i = 0; i < DEFAULT_PARAMS.stillWindow; i += 1, at += 1) feed(at * F, 170, at)
  // Card B arrives IMMEDIATELY. Its settle completes inside the refractory window — the
  // fire must arrive after the window expires, not never, which is the whole property.
  feed(at * F, 60, at)
  at += 1
  for (let i = 0; i < 12; i += 1, at += 1) feed(at * F, 120, at)
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
  let at = 0
  for (let i = 0; i < ARM_FRAMES; i += 1, at += 1) feed(at * F, EMPTY, at)
  feed(at * F, 170, at) // the swap
  at += 1
  for (let i = 0; i < DEFAULT_PARAMS.stillWindow; i += 1, at += 1) feed(at * F, 170, at)
  expect(events).toEqual(['suppressed:no-card', 'fire'])
})
