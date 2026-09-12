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
 *  byte-identical frames would let d = 0 hide a broken diff.
 *
 *  AND TEXTURED, SINCE 2026-09-12. Every cell carries a fixed `TEXTURE` around the level, the
 *  same on every frame, because a FLAT scene at a new level is the old scene TIMES ONE NUMBER
 *  — which is what an exposure step is, and what the machine now refuses as
 *  `suppressed:uniform`. Until this, every "card" in this file was exactly that, and ten
 *  cases went red the moment the machine could tell. A real stand has texture (a disc, a tray
 *  edge) and a real card has art; a level change over texture is not a rescale of it, so
 *  these stay cards, while a frame that IS the scene times one number — the gain-step cases
 *  at the foot of this file — is still uniform. Under `presenceMin`, so the texture alone
 *  never decides presence. */
const TEXTURE = 12
function still(base: number, phase: number): Float32Array {
  const cells = new Float32Array(CELLS)
  for (let i = 0; i < CELLS; i += 1) {
    cells[i] = base + (i % 2 === 0 ? TEXTURE : -TEXTURE) + (((i * 31 + phase * 17) % 7) - 3) * 0.2
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
  /* THE HOVER IS ABOVE THE RESCUE BAR, AND THAT IS NOW THE POINT OF THE NUMBER. The bar is
     `rescueK` x tLo — 6.0 at the seeded tLo of 4.5 — and an alternation of ±6 would sit ON
     it, which is a test decided by a float. ±10 gives d ~ 10, clear of the bar and clear of
     tHi 8.0, so this stays what it was written to be: a jam the machine must report rather
     than a landing it must rescue. */
  for (let i = 0; i < 50; i += 1) feed(i % 2 === 0 ? 60 : 70, i + 2) // band... and above it
  expect(events).toEqual(['stalled'])
  expect(machine.diag.fires).toBe(0)
  expect(machine.diag.rescued).toBe(0)
})

test('a card that never quite settles is RESCUED once the episode has run long enough', () => {
  /* THE OWNER'S COMPLAINT, IN CODE: "it's really bad when the cards are coming a little
     slower or aren't landing perfectly". Six sessions on 2026-09-11 carried 19 stall
     episodes between them and the quietest frame of EVERY ONE sat between 1.02x and 1.25x
     tLo — nine of the first fourteen were UNDER tLo and were refused by `stillWindow` alone,
     because the card landed one or two frames after a transit ended and the next card's
     motion threw the window away before it could fill.

     The fixture is the second, harder kind: a scene that comes to rest just ABOVE tLo and
     stays there. It must NOT fire while the episode is young — `stillWindow` is what stops a
     dip mid-transit from firing, and retiring it from the first frame takes the trace
     corpus's double count from 2 to 21 — and it MUST fire once the episode has outlasted
     `rescueAfter` x `maxMoveMs`. Both halves are asserted, because a rescue that fired
     immediately would pass a test that only checked the fire. */
  const machine = new MotionMachine()
  const events: Array<{ ms: number; event: MotionEvent }> = []
  let at = 0
  const feed = (base: number) => {
    const event = machine.step(at * F, still(base, at))
    if (event !== null) events.push({ ms: at * F, event })
    at += 1
  }
  for (let i = 0; i < ARM_FRAMES; i += 1) feed(EMPTY)
  const opened = at * F
  feed(170) // the card arrives: MOVING
  /* A rest in the band: ±5 against tLo 4.5 and the bar at 6.0, so every frame is "not still"
     by the ordinary rule and inside the rescue's reach. */
  const deadline = opened + DEFAULT_PARAMS.rescueAfter * DEFAULT_PARAMS.maxMoveMs
  for (let i = 0; i < 60; i += 1) feed(i % 2 === 0 ? 170 : 175)
  const fires = events.filter((e) => e.event === 'fire:rescued')
  expect(fires).toHaveLength(1)
  expect(events.map((e) => e.event)).toEqual(['suppressed:no-card', 'fire:rescued'])
  const rescue = fires[0]
  expect(rescue).toBeDefined()
  if (rescue !== undefined) expect(rescue.ms).toBeGreaterThanOrEqual(deadline)
  expect(machine.diag.fires).toBe(1)
  expect(machine.diag.rescued).toBe(1)
  // And it is a real settle, so the stall clock was cleared by it: no stall, ever.
  expect(machine.diag.stalled).toBe(0)
})

test('a rescue is a statement about stillness only — presence still refuses an empty stand', () => {
  /* WHAT THE RESCUE RELAXES AND WHAT IT DOES NOT. The bar and the window are stillness; the
     presence gate, the novelty gate and the refractory are untouched, and this is the one
     that matters most — a rescue that could photograph the bare stand would put D84's two
     junk rows back at the top of a box for the sake of a card that was never there. The
     scene here never leaves the arm-time stand: it jitters in the band around EMPTY, which
     the ordinary rule cannot settle and the rescue can, and every verdict is `no-card`
     because `dBase` never reaches the floor. */
  const machine = new MotionMachine()
  const events: MotionEvent[] = []
  let at = 0
  const feed = (base: number) => {
    const event = machine.step(at * F, still(base, at))
    if (event !== null) events.push(event)
    at += 1
  }
  for (let i = 0; i < ARM_FRAMES; i += 1) feed(EMPTY)
  feed(EMPTY + 60) // something crosses the region and leaves
  for (let i = 0; i < 60; i += 1) feed(i % 2 === 0 ? EMPTY : EMPTY + 5)
  expect(machine.diag.fires).toBe(0)
  expect(machine.diag.rescued).toBe(0)
  expect(new Set(events)).toEqual(new Set(['suppressed:no-card']))
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

test('one quiet frame in four is a settle now, and a scene with none still stalls', () => {
  /* D84'S SECOND HALF, AMENDED BY D131. The clock is still cleared only by a COMPLETED
     settle — that half stands, and the band-hover case above proves it. What moved is what
     completes one: `stillFrames` of `stillWindow` is ONE OF THREE since 2026-09-11, because
     the bright-lamp feeder rests a card for two to four frames and a window of four never
     filled. Under that rule the scene D84 used here — one frame under tLo in every four —
     SETTLES on its quiet frame and is photographed there: a frame under tLo is still by
     definition, and on the bright-lamp sessions it is the only kind of rest there is. The
     2026-09-01 21:10 card this fixture was modelled on is captured now rather than stalled.

     The silent failure D84 closed cannot come back through this door: a scene with NO quiet
     frame at all — the band hover two tests up — still expires the clock and says so. */
  const machine = new MotionMachine()
  const bases: number[] = [60]
  for (let i = 1; i < 60; i += 1) {
    const last = bases[i - 1] as number
    bases.push(i % 4 === 0 ? last : last === 60 ? 66 : 60)
  }
  const events = run(machine, [...armEmpty(), ...bases])
  expect(events[0]?.event).toBe('suppressed:no-card')
  expect(machine.diag.fires).toBeGreaterThanOrEqual(1)
  expect(machine.diag.stalled).toBe(0)
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

/* ---------------------------------------------------------------- the gain step (2026-09-12) */

/** A brighter stand than `EMPTY`, because the presence floor is where the uniformity test
 *  starts to matter: at 30 a 1/3 EV step is 3.3 luma and never clears 16, so the floor refuses
 *  it as it always did. At 150 the same step is 17 — over the floor, and until 2026-09-12 a
 *  junk photograph of the bare stand. The corpus's plates run 24-192. */
const PLATE = 150
const STEP = 2 ** (1 / 3 / 2.2) // one 1/3 EV step in display code, `score-trace.py camera`'s model

test('an exposure step on the bare stand is refused as uniform and becomes the baseline', () => {
  const machine = new MotionMachine()
  const events = run(machine, [
    ...Array<number>(ARM_FRAMES).fill(PLATE),
    PLATE * STEP, PLATE * STEP, PLATE * STEP, PLATE * STEP, PLATE * STEP, // the camera re-levels
    PLATE * STEP * STEP, 60, PLATE * STEP, PLATE * STEP, PLATE * STEP, PLATE * STEP, // wobble, same stand
  ])
  /* The step clears the floor (17 > 16) and is the plate times one number: refused, and the
     next settle on the same stand is judged against the NEW baseline — at zero distance,
     the ordinary empty verdict, not a second uniform one and never a fire. */
  expect(events.map((e) => e.event)).toEqual([
    'suppressed:no-card',
    'suppressed:uniform',
    'suppressed:no-card',
  ])
  expect(machine.diag.uniform).toBe(1)
  expect(machine.diag.fires).toBe(0)
  expect(machine.diag.dBase).toBeLessThan(1)
})

test('a card is not a scaled plate — it fires with the step present, and a hand is still refused after it', () => {
  const machine = new MotionMachine()
  /* A card is a PATTERN: half the region much brighter than the plate, the rest darker.
     `still` adds the same deterministic noise as everywhere else. */
  const card = (phase: number): Float32Array => {
    const cells = still(PLATE, phase)
    for (let i = 0; i < CELLS; i += 1) cells[i] = (i % 3 === 0 ? 40 : 230) + ((cells[i] as number) - PLATE)
    return cells
  }
  const events: MotionEvent[] = []
  const feed = (frames: Float32Array[]) => {
    for (const frame of frames) {
      const event = machine.step(events.length * F + frames.indexOf(frame) * F + machine.diag.frames * F, frame)
      if (event !== null) events.push(event)
    }
  }
  feed(Array.from({ length: ARM_FRAMES }, (_, i) => still(PLATE, i)))
  // the step lands on the empty stand: refused, baseline re-taken at the new gain
  feed(Array.from({ length: 5 }, (_, i) => still(PLATE * STEP, i + 10)))
  // the card arrives at the new gain: a card
  feed([still(90, 20), ...Array.from({ length: 8 }, (_, i) => card(i + 30))])
  expect(events).toEqual(['suppressed:no-card', 'suppressed:uniform', 'fire'])
  // the card leaves; the stand at the new gain settles at zero distance from the new baseline
  feed([still(60, 40), ...Array.from({ length: 5 }, (_, i) => still(PLATE * STEP, i + 50))])
  expect(events.at(-1)).toBe('suppressed:no-card')
  expect(machine.diag.fires).toBe(1)
})

test('a step over a card already photographed is the same card, not a second one', () => {
  const machine = new MotionMachine()
  const card = (level: number, phase: number): Float32Array => {
    const cells = still(level, phase)
    /* 0.3x and 1.4x, not 1.5x: at 150 x 1.11 x 1.5 the bright cells sit at 250, over the
       shoulder, and the COMPARABLE set is then only the dark third — which is a flat level
       times one number, and the test would rightly call that uniform. A real card's dark
       parts carry pattern; this fixture's do not, so it is kept under the shoulder. */
    for (let i = 0; i < CELLS; i += 1) cells[i] = (i % 3 === 0 ? level * 0.3 : level * 1.4) + ((cells[i] as number) - level)
    return cells
  }
  const events: MotionEvent[] = []
  let t = 0
  const feed = (frames: Float32Array[]) => {
    for (const frame of frames) {
      const event = machine.step(t, frame)
      t += F
      if (event !== null) events.push(event)
    }
  }
  feed(Array.from({ length: ARM_FRAMES }, (_, i) => still(PLATE, i)))
  feed([still(90, 20), ...Array.from({ length: 5 }, (_, i) => card(PLATE, i + 30))])
  expect(events).toEqual(['suppressed:no-card', 'fire'])
  /* The camera re-levels while the card sits there. Against the baseline the frame is a
     card (not uniform); against the last fired frame it IS uniform — the same card at a new
     gain — so the novelty gate, scaled, calls it unchanged. Raw novelty would have read the
     step (a fifth of the card's level, well over tNovel) and photographed it twice. */
  /* Twelve frames: the re-settle lands inside the 250 ms refractory of the fire before it and
     is judged, deferred, on the first frame after it — the same deferral the refractory case
     above pins. */
  feed(Array.from({ length: 12 }, (_, i) => card(PLATE * STEP, i + 40)))
  expect(events).toEqual(['suppressed:no-card', 'fire', 'suppressed:unchanged'])
  expect(machine.diag.fires).toBe(1)
  expect(machine.diag.uniform).toBe(0)
})

test('a weak pattern over the floor is a card — the bound is the session noise, not the floor', () => {
  /* The bound the uniformity test compares against is `presenceK` x the session's still-frame
     difference (6.75 seeded), NOT `presenceMin` (16). A frame at 1.2x the plate with a ±10
     pattern on it is 30 from the baseline and leaves a residual of 10 once the scaling is
     divided out: over the bound, so a card; a machine that compared the residual against the
     floor instead would call it the stand at a new gain and photograph nothing. */
  const machine = new MotionMachine()
  const weak = (phase: number): Float32Array => {
    const cells = still(PLATE * 1.2, phase)
    for (let i = 0; i < CELLS; i += 1) cells[i] = (cells[i] as number) + (i % 2 === 0 ? 10 : -10)
    return cells
  }
  const events: MotionEvent[] = []
  let t = 0
  const feed = (frames: Float32Array[]) => {
    for (const frame of frames) {
      const event = machine.step(t, frame)
      t += F
      if (event !== null) events.push(event)
    }
  }
  feed(Array.from({ length: ARM_FRAMES }, (_, i) => still(PLATE, i)))
  feed([still(90, 20), ...Array.from({ length: 6 }, (_, i) => weak(i + 30))])
  expect(events).toEqual(['suppressed:no-card', 'fire'])
  expect(machine.diag.uniform).toBe(0)
})

test('a dark card on a bright plate is judged in the plate\'s units, not its own', () => {
  /* The 03:25 session's shape: a bright plate, a card at a fifth of its light with a faint
     pattern of its own. In the card's units the residual is 3.3 — under the seeded bound of
     6.75, and a machine reading it there calls the card the stand at a new gain. In the
     brighter frame's units it is 3.3 / 0.18 = 18.5: a card. `uniformResidual` divides by
     min(k, 1) for exactly this frame, and the reverse case — a bright card on a dark plate —
     is the 85/85 run's, where the baseline's units would fail the same way. */
  const machine = new MotionMachine()
  const dark = (phase: number): Float32Array => {
    const stand = still(PLATE, phase)
    const cells = new Float32Array(CELLS)
    for (let i = 0; i < CELLS; i += 1) cells[i] = 0.2 * (stand[i] as number) + (i % 2 === 0 ? 3 : -3)
    return cells
  }
  const events: MotionEvent[] = []
  let t = 0
  const feed = (frames: Float32Array[]) => {
    for (const frame of frames) {
      const event = machine.step(t, frame)
      t += F
      if (event !== null) events.push(event)
    }
  }
  feed(Array.from({ length: ARM_FRAMES }, (_, i) => still(PLATE, i)))
  feed([still(90, 20), ...Array.from({ length: 6 }, (_, i) => dark(i + 30))])
  expect(events).toEqual(['suppressed:no-card', 'fire'])
  expect(machine.diag.uniform).toBe(0)
})

test('a step that clips half the plate is still uniform — the clipped cells are left out on BOTH sides', () => {
  /* A bright stand: half its cells at 242, half at 218. A 1/3 EV step puts the bright half at
     255 — over the shoulder — and the dark half at 242. Judged over the unclipped half alone
     the frame is the stand times one number; judged over every cell the clipped half reads a
     different ratio (255/242 against 242/218) and the residual, 7, crosses the seeded bound.
     `uniformShoulder` applies to the CURRENT frame as well as the baseline for exactly this
     frame: a cell that has clipped cannot report what the gain did. */
  const machine = new MotionMachine()
  const bright = (phase: number): Float32Array => still(230, phase) // 242 / 218 with TEXTURE
  const events: MotionEvent[] = []
  let t = 0
  const feed = (frames: Float32Array[]) => {
    for (const frame of frames) {
      const event = machine.step(t, frame)
      t += F
      if (event !== null) events.push(event)
    }
  }
  feed(Array.from({ length: ARM_FRAMES }, (_, i) => bright(i)))
  feed(Array.from({ length: 6 }, (_, i) => bright(i + 10).map((v) => Math.min(255, v * STEP))))
  expect(events).toEqual(['suppressed:no-card', 'suppressed:uniform'])
  expect(machine.diag.uniform).toBe(1)
})

test('a step that clips more than three quarters of the plate is DECLINED, and the floor alone decides', () => {
  /* Four cells in five at 225, which a 1/3 EV step lifts to 250 — past the shoulder — and one
     in five at 60, lifted to 67. Comparable cells are a fifth of the region, under
     `uniformMinShare`, so the question is declined: the frame is 20 from the baseline, over the
     floor, and the machine before 2026-09-12 fired on it, so this one does too. A machine that
     never declined would judge the fifth it can see, find it uniform, and refuse — which is
     the right answer on this frame and an answer it has no standing to give: four cells in
     five are unreadable, and a card can hide in cells the gain has saturated. */
  const machine = new MotionMachine()
  const plate = (phase: number): Float32Array => {
    const cells = new Float32Array(CELLS)
    for (let i = 0; i < CELLS; i += 1) cells[i] = (i % 5 === 0 ? 60 : 225) + (((i * 31 + phase * 17) % 7) - 3) * 0.2
    return cells
  }
  const events: MotionEvent[] = []
  let t = 0
  const feed = (frames: Float32Array[]) => {
    for (const frame of frames) {
      const event = machine.step(t, frame)
      t += F
      if (event !== null) events.push(event)
    }
  }
  feed(Array.from({ length: ARM_FRAMES }, (_, i) => plate(i)))
  feed(Array.from({ length: 6 }, (_, i) => plate(i + 10).map((v) => Math.min(255, v * STEP))))
  expect(events).toEqual(['suppressed:no-card', 'fire'])
  expect(machine.diag.uniform).toBe(0)
})
