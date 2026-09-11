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

/* HOW BRIGHT THE BRIGHTEST TENTH OF THE WATCH REGION IS.
 *
 * NOTHING GATES ON THIS ANY MORE — it is recorded into the trace and nowhere else, because
 * `presenceK` below carries the argument for why no brightness statistic can gate presence.
 * It stays because it is the one number that makes a session's LIGHTING legible offline: the
 * 2026-09-01 trace drifts 116 -> 98 over 23 seconds, and that drift is invisible in `d`,
 * which is a difference and cancels it. Evidence, not a gate.
 *
 * 0.9 rather than the mean or the maximum, for the reason the old presence gate gave at
 * length: a card that fills the region and a card that occupies a third of it against a dark
 * surround are the same card and only one of them has a usable mean, while a specular
 * highlight, a lamp in frame or one hot pixel all carry a maximum. */
export const CARD_QUANTILE = 0.9

/* ------------------------------------------------------------------------- parameters */

/* EVERY THRESHOLD HERE IS A MULTIPLE OF SOMETHING THIS SESSION MEASURED. That is the whole
 * change of 2026-08-31 (D81), and it is a change of KIND rather than of tuning.
 *
 * WHAT WENT WRONG. Until today `tHi`, `tLo` and `cardLumaFloor` were absolute numbers
 * compared against nothing: 8.0, 4.5, and a brightness of 90. `cardLumaFloor` is the one
 * that cost cards, and it cost them because NO CONSTANT CAN DO ITS JOB. Scored across the
 * four traces the owner has saved, the bright-quantile of the watch region reads:
 *
 *     EMPTY STAND, reference rig (2026-08-23)            57
 *     CARD,        under-lit rig (2026-08-29 21:34)   61-134
 *     CARD,        2026-09-01                         77-171
 *     CARD,        reference rig (2026-08-23)        196-244
 *
 * An empty stand at 57 and a real card at 61. Four luma levels apart, on different days,
 * with the floor at 90 sitting INSIDE the card population of three sessions out of four.
 *
 * TWO NUMBERS, AND THEY ARE NOT THE SAME NUMBER. 38 cards were refused across three LIVE
 * sessions, by two different versions of this gate — 20 and 13 under the mean, 5 under the
 * bright quantile. Re-scored through the version that was in the tree this morning, 18 of
 * them would STILL be refused: the 2026-08-29 quantile change rescued one session of three
 * and left the other two broken, which is the clearest statement available that a better
 * constant was never going to be the fix. `harness/tests/t9_traces.py` asserts both.
 * The bill: 20 of 20 cards refused on 2026-08-29 21:34, 13 of 15 on 21:38, 5 of 24 on
 * 2026-09-01 — 38 real cards called an empty stand, silently, against ONE correct refusal
 * (the genuinely empty stand at arm time on 2026-08-23). Moving 90 to some other number
 * moves which sessions it ruins. The quantile fix of 2026-08-29 was the same mistake one
 * layer in: it changed WHICH brightness statistic the constant was compared against, and a
 * constant was never the right shape of thing to compare a brightness against.
 *
 * WHAT REPLACES IT. `presenceK` below: a settled frame is a card when it DIFFERS FROM WHAT
 * THIS SESSION SAW WHEN IT WAS ARMED. Same scoring, same four traces: empty stand reads
 * 1.10-1.38 against that baseline and a card reads 17-167. A 43x gap where brightness gave
 * 1.07x. Nothing in it is a number about luma; everything in it is a number about change.
 *
 * `tLo`/`tHi` go the same way for the same reason, and the receipt is already in the repo's
 * own history: the 2026-08-23 retune (tLo 3.0 -> 4.5) was a person at a rig discovering that
 * the live preview's noise floor is eleven times the stored JPEGs' — a number the machine
 * could have measured for itself in eight seconds. Replayed against that same trace, a tLo
 * carried at `stillK` x the session's own median STILL-frame difference reaches 86 of 86
 * verdicts where the constant 3.0 reached 72.
 *
 * THE HAND-TUNED PAIR IS PRESERVED, NOT DISCARDED. At the seed (`dSeed`), `stillK` and
 * `moveK` reproduce tLo 4.50 and tHi 8.00 to the last digit, and the tHi/tLo ratio of 1.78
 * is carried unchanged. Gate C's 85/85 run is not being re-litigated; it is being made
 * portable to a rig that is not that one. Re-scored against all five saved traces the
 * adaptive machine reaches 86, 86, 20, 15 and 24 verdicts where the constants reached
 * 72, 86, 20, 15 and 24 — every trace met or beaten, including the one whose 14 silent
 * misses cost a rig trip to diagnose.
 */
export type MotionParams = {
  /** tLo = `stillK` x the session's own typical STILL-frame difference. Below tLo the
   *  scene is still. 2.0 chosen by sweep rather than by taste: replaying all five saved
   *  traces over q = 0.5-0.95 and k = 1.4-2.5, the region around the median at k = 2.0-2.2
   *  is a PLATEAU where every trace meets or beats what the hand-tuned constants scored
   *  live — 86, 86, 20, 15, 24 against 72, 86, 20, 15, 24 — rather than an edge where one
   *  trace is rescued and another falls off. `scripts/score-trace.py` reproduces the sweep. */
  stillK: number
  /** tHi = `moveK` x the same measurement. Above tHi the scene is MOVING. 3.556 = 2.0 x
   *  16/9, which holds tHi/tLo at the 1.78 the hand-tuned pair 4.5/8.0 had. The band is a
   *  RATIO rather than a difference on purpose: a Schmitt band that stayed a fixed 3.5 wide
   *  would be a wide band on a quiet rig and no band at all on a noisy one. */
  moveK: number
  /** What the session's typical still-frame difference is taken to be until the window has
   *  enough of THIS session to answer. 2.25 is chosen so the seeded thresholds are 4.50 and
   *  8.00 to the last digit — Gate C's own hand-tuned pair. The machine therefore boots at
   *  exactly the constants the 85/85 run was confirmed on and adapts away from them, rather
   *  than starting from a guess of its own. */
  dSeed: number
  /** Floor under the measured typical d, so a rig with a rock-steady mount and a quiet
   *  sensor cannot drive tLo toward zero and turn every sensor flicker into a settle
   *  episode. 1.0 sits under every session measured (1.75-3.22) without touching any. */
  dFloor: number
  /** How much of the recent past the typical-d estimate is taken over. 8 s is ~200 frames
   *  at the observed 25 fps and about a dozen feeder cycles — long enough that one card
   *  cannot define the session, short enough to follow a lamp being moved.
   *
   *  ONLY FRAMES THE MACHINE ALREADY CALLS STILL GO IN, and that restriction is the whole
   *  answer to this file's own former objection — "an EMA floor that learns during slow
   *  motion is a way to go blind". A hand resting half in frame, a jammed feeder, a card
   *  creeping: every one of those sits above tLo, never enters the estimate, and so cannot
   *  redefine what stillness is. The estimate can only be moved by frames that were already
   *  judged still, and the multiplier is what lets it climb: a session whose still noise
   *  reads 3.5 lands tLo at 7.0, well clear of it.
   *
   *  THE ONE THING THIS CANNOT RECOVER FROM is a session whose noise is entirely above the
   *  seeded tLo of 4.5 — no frame is ever still, so nothing enters the window and nothing
   *  adapts. That failure is LOUD rather than silent: not one capture is taken and the HUD
   *  sits in `moving` forever, which is the opposite of the 2026-08-23 failure where 14 of
   *  86 cards vanished while everything looked normal. A median over a window that admitted
   *  motion would have been quieter and wronger. */
  noiseWindowMs: number
  /** THE RATCHET'S ESCAPE, 2026-09-11 (D131). The tracker above admits only frames already
   *  under `tLo`, so it can lower the still level and never raise it: a rig whose rest sits
   *  ABOVE the seeded 4.5 — the owner's bright lamp, where a resting card reads d 5-8 from
   *  brightness jitter alone — is never learned, and the settle rule fires on 5 of 29 cards
   *  while everything looks normal. That is the exact shape of the 2026-08-23 loss with the
   *  sign flipped. When the frames the machine calls still fall below this FRACTION of the
   *  window, its idea of still is wrong, and `dTypical` is taken instead from `restQuantile`
   *  of ALL the window's frames. 0.30: every one of the eight earlier sessions keeps 46-83%
   *  of its frames under tLo and never trips this; the three bright-lamp sessions sit at
   *  9-18% and trip it at once. Measured in both directions — 0 quantile-mode refreshes on
   *  the old corpus, 100/95/94% coverage on the new. */
  stillFractionMin: number
  /** Which quantile of ALL window frames stands in for the still level when the ratchet
   *  has lost it. 0.25: on the bright-lamp sessions the rest phase is the lowest quarter of
   *  frames (p25 7-9 against a transit at 13-30), so this lands `tLo` in the gap between
   *  them. `stillK` is NOT applied on this path — the quantile is already a threshold, not a
   *  level — and `tHi` keeps its ratio to `tLo`. */
  restQuantile: number
  /** Still frames that mean "settled" — counted as `stillFrames` of the last
   *  `stillWindow`, not as a consecutive run. 2 frames = 67 ms at 30fps. The original
   *  guess of 6 (200 ms), plus a blinding 400 ms cooldown, summed to more than the 458 ms
   *  worst cycle Gate B measured — infeasible at the MEAN cycle, not just the worst. */
  stillFrames: number
  /** How many recent frames `stillFrames` is counted over. ONE OF THREE SINCE 2026-09-11
   *  (D131): the bright-lamp feeder rests a card for two to four frames, so a window of four
   *  never fills before the next card slides in — half the cards never completed a settle.
   *  One quiet frame among the last three, on a quiet frame, is what those rests can
   *  satisfy; swept against every old session it changes no count. 4 FROM 2026-09-01 (D84). It
   *  was effectively 2 until then, because the rule was a consecutive run.
   *
   *  A CONSECUTIVE RUN IS DEFEATED BY A TWO-FRAME ALTERNATION, and that is measured rather
   *  than feared. A card sitting motionless at the head of a feeder run, 500 ms, every
   *  frame, against a tLo of 4.18:
   *
   *      2.71  5.40  2.63  5.54  2.83  5.14  3.03  4.80  3.64  4.91
   *
   *  Five separate runs of ONE, never a run of two, no verdict — and the card was replaced
   *  unphotographed with nothing on the HUD. Two of the last four is satisfied by that
   *  pattern at its third frame. Swept over the three 2026-09-01 sessions it recovers two
   *  of the four cards lost this way and changes no other verdict; 2-of-3 and 3-of-5 both
   *  recover fewer. The other two recoveries are not this rule's job — those scenes had
   *  one quiet frame in ten and were genuinely still moving, which is what `maxMoveMs` is
   *  for and why D84 moves that too. */
  stillWindow: number
  /** Floor on the spacing between fires, DEFERRING rather than blinding: a settle that
   *  completes inside the window fires when it expires instead of being dropped. Sized to
   *  the measured capture round trip (<250 ms), not to the card cycle. A time, not a light
   *  level: nothing about it is a constant compared against a measurement. */
  refractoryMs: number
  /** A settled frame must differ from the LAST FIRED frame by this much, or it is the same
   *  card sitting there and the fire is suppressed. The gate that actually prevents
   *  double-captures — the refractory is a guess about time, this is a statement about the
   *  picture. 4.0 is ~11x the Gate B noise floor and ~3.5x under the weakest same-card
   *  repeat measured across the Gate B duplicates (14.3); the feeder trace re-measured it
   *  live at 7.6 for the closest pair of DIFFERENT fired cards.
   *
   *  DELIBERATELY STILL A CONSTANT, and this is not an oversight D81 missed. Two reasons.
   *  It has never suppressed anything: across all five saved traces, 217 verdicts, the
   *  `suppressed:unchanged` count is ZERO, so there is no measurement to derive a multiple
   *  from. And scaling it to session noise would push it DOWN on a quiet rig, making
   *  suppression more likely — the wrong direction, because a false pass is a duplicate
   *  undo fixes and a false suppression is a silent §5.5 loss. It stays absolute until a
   *  trace convicts it, and then it will be convicted with numbers like everything else. */
  tNovel: number
  /** A settled frame is A CARD when it differs from the session's BASELINE — the watch
   *  region as it stood when the trigger was armed — by more than `presenceK` x this
   *  session's typical d, floored at `presenceMin`.
   *
   *  THE MEASUREMENT, scored over the four saved traces with the baseline taken the way the
   *  machine now takes it. Against its own baseline the reference rig's genuinely empty
   *  stand reads 1.10-1.38 while its 85 cards read 58.9-167.4; the under-lit rig's cards
   *  read 17-32; 2026-09-01's read 23-35. Every card of every session sits above 17 and
   *  every empty frame below 1.4.
   *
   *  3.0 puts the threshold at 5.5-9.7 across those sessions: four to seven times over the
   *  empty stand and three to ten times under the dimmest card. Re-scored end to end, the
   *  38 cards the brightness floor refused all pass, and the only frames refused are the
   *  arm-time scene itself and, where it persisted, its repeat — which is the gate saying
   *  "nothing has changed since you armed", correctly.
   *
   *  IT IS ALSO THE RIGHT DIRECTION OF FAILURE. A baseline taken with a card on the stand
   *  makes the machine refuse that card and fire on everything after — a visible loss of
   *  one photograph at the top of a run, announced on the HUD, against the old gate's
   *  silent loss of twenty mid-run. */
  presenceK: number
  /** Absolute floor under the presence threshold, so a very quiet rig cannot drive it low
   *  enough that something which is not a card reads as one.
   *
   *  16.0 SINCE 2026-09-01 (D84), AND WHAT IT KEEPS OUT IS A HAND RATHER THAN DRIFT. 8.0
   *  was set by illumination drift — a static scene walking 7.94 away from a baseline 3.4 s
   *  old — and three fresh traces did not reproduce that. An undisturbed stand does not
   *  creep at all; per-second worst dBase, plate only:
   *
   *      21:10 run   0s 2.45  1s 2.26  2s 2.53 … 9s 2.36 │ 10s 8.12  11s 14.14  12s 17.91
   *      21:16 run   0s 2.13  1s 2.19  2s 2.20 … 5s 2.79 │  6s 6.81   7s 14.66   8s 11.64
   *                                                      ^ the operator's hand, arriving
   *
   *  Everything above 3 is the hand entering frame with the first card of the run. It holds
   *  still for two frames on the way in, and at 8.0 that FIRED: two of the three sessions
   *  photographed the bare stand at dBase 9.07 and 9.10 and put a junk row at the top of a
   *  box. 16.0 is 1.4x over the worst approach measured (11.15) and 2x under the quietest
   *  card in the same sessions (32.5); re-scored end to end it removes exactly those two
   *  fires and no others.
   *
   *  IT IS A CONSTANT AND IT IS NOW THE BINDING TERM, which is a debt and not a design.
   *  `presenceK * dTypical` sits at 6-10 on this rig, so this floor decides every verdict
   *  and the adaptive half decides none — the species D81 convicted in `cardLumaFloor`. It
   *  stays constant because what it has to clear is a HAND, whose size in frame no session
   *  statistic measures. Three quantities re-derive it on a new rig and they are the three
   *  above: the idle stand, the worst approach, the quietest card.
   *
   *  DRIFT ALONE STILL CANNOT FIRE, and that is the second line of defence, unchanged: a
   *  fire needs a settle EPISODE, an episode needs motion above tHi, and drift is slower
   *  than the still threshold by two orders of magnitude. */
  presenceMin: number
  /** THE RESCUE BAR, 2026-09-11 — how far above `tLo` a frame may sit and still settle an
   *  episode that has gone on too long, as a multiple of `tLo`.
   *
   *  4/3, AND IT IS NOT A NEW NUMBER: it is `sqrt(moveK / stillK)`, the GEOMETRIC CENTRE of
   *  the Schmitt band this session already measures. `moveK / stillK` is 16/9 by moveK's own
   *  definition, so its root is exactly 4/3 and the bar sits where a frame is equally far —
   *  in ratio — from "still" and "moving". Nothing above `tHi` can ever be rescued, because
   *  a frame above `tHi` ends the episode rather than settling it.
   *
   *  THE MEASUREMENT. Across the fourteen stall episodes of the four 21:xx/22:xx sessions,
   *  the quietest frame of every one sits between 1.02x and 1.25x `tLo` — nine of them are
   *  UNDER `tLo` and were refused by the window rule alone. 4/3 covers all fourteen with
   *  margin and is the largest value the corpus tolerates: swept at 1.40 the 21:16 session
   *  gains a fire it did not have, which is a change to a session nobody re-measured. */
  rescueK: number
  /** How long an episode must have run without a settle before `rescueK` applies, as a
   *  FRACTION of `maxMoveMs`. 0.60 — so the rescue bar is in force over the last two fifths
   *  of the stall clock, and the ordinary rule is untouched before that.
   *
   *  IT IS A STEP AND NOT A RAMP, AND THE RAMP WAS MEASURED. A bar rising smoothly from
   *  `tLo` at the episode's start to 4/3 at the deadline reaches `tLo` immediately, which
   *  retires `stillWindow` from the first frame — and `stillWindow` is what stops a dip
   *  during a card's transit from firing. Scored over the whole corpus the ramp takes the
   *  double count from 2 to between 20 and 55. The window rule has to stay in force until
   *  the transit can no longer be happening, and the episode's own age is the machine's
   *  only word for that.
   *
   *  0.60 IS WHERE TWO PLATEAUX MEET. Swept from 0.50 to 0.80 at 0.02: yield is FLAT at 295
   *  fires and 7 stalls over the six new sessions from 0.50 to 0.60 and falls away above it
   *  (280 and 21 by 0.80); the eight earlier sessions are untouched from 0.60 up and gain a
   *  fire and a double at 0.58 and below — 21:14's 6.21 s rescue lands 290 ms before its own
   *  6.50 s fire. Below 0.60 costs a session nobody re-measured; above it costs cards. */
  rescueAfter: number
  /** This long without a COMPLETED settle is a jam or a hand — surfaced as `stalled`, and
   *  the machine does NOT fire. Firing anyway was argued (never silently drop a card, §5.5)
   *  and rejected for v1: a hand in frame would capture-spam, and the stall is loud on
   *  screen, which is what §5.5 actually requires. A time, like the refractory.
   *
   *  "COMPLETED SETTLE" IS D84'S CORRECTION AND IT IS THE WHOLE VALUE OF THIS FIELD. The
   *  clock used to be cleared by any single frame under tLo while a fire needed two in a
   *  row, so the alternation `stillWindow` documents reset it every other frame and it
   *  could never expire. Across three sessions, 93 seconds and four cards left
   *  unphotographed, this never fired once. Cleared on a settle instead, it reports each of
   *  those and nothing else: one stall per session, every one on a real card, zero false
   *  positives over 67 good captures. */
  maxMoveMs: number
}

/* Measured off the first feeder trace, 2026-08-23: period 623 ms burst-to-burst, each
 * card ~217 ms moving and ~400 ms still (min still gap 132 ms), frames delivered at
 * ~25 fps. See each field's own comment for its derivation. */
export const DEFAULT_PARAMS: MotionParams = {
  stillK: 2.0,
  moveK: (2.0 * 16) / 9,
  dSeed: 2.25,
  dFloor: 1.0,
  noiseWindowMs: 8000,
  stillFractionMin: 0.3,
  restQuantile: 0.25,
  stillFrames: 1,
  stillWindow: 3,
  refractoryMs: 250,
  tNovel: 4.0,
  presenceK: 3.0,
  presenceMin: 16.0,
  rescueK: 4 / 3,
  rescueAfter: 0.6,
  maxMoveMs: 1250,
}

/* ------------------------------------------------------------------------ the machine */

export type MotionPhase = 'watching' | 'moving' | 'settling'

export type MotionEvent =
  | 'fire'
  /** A fire taken off a frame that never completed an ordinary settle — `rescueK` above.
   *  A SEPARATE VERDICT RATHER THAN A FLAG, because the photograph is different in kind:
   *  the frame is inside the Schmitt band rather than under `tLo`, so it may be softer than
   *  a card the machine waited out. The screen captures on it exactly as it does on `fire`;
   *  what the distinct string buys is that a trace, and the HUD, can say how many of a run's
   *  photographs were taken that way — which is the one question the first rig run under
   *  this rule has to answer, and it cannot be answered from a count of fires. */
  | 'fire:rescued'
  | 'suppressed:unchanged'
  | 'suppressed:no-card'
  | 'stalled'

/** How often the typical-d estimate is recomputed, in frames. Every 10 frames is ~2.5
 *  times a second at the observed 25 fps, which is far faster than a lamp or a mount can
 *  change and far cheaper than a select over the window on every frame. */
const NOISE_REFRESH_FRAMES = 10

/** What the HUD renders. Counters never reset while the trigger is armed — a rig-tuning
 *  session reads them as rates against the run's card count. */
export type MotionDiagnostics = {
  phase: MotionPhase
  /** Last frame-to-frame mean-abs-diff over the ROI, the number the stillness thresholds
   *  are now a MULTIPLE of. On screen so the noise floor and the swap signal can be SEEN
   *  during tuning instead of inferred afterwards. */
  d: number
  /** How far the last frame is from the session's baseline — the card-present signal, and
   *  the number `presenceK` decides against. On the HUD in the slot `luma` used to hold,
   *  because a HUD showing a statistic the machine does not use is how a rig got debugged
   *  against the wrong number for two sessions. */
  dBase: number
  /** The session's own typical frame-to-frame difference, and the measurement every
   *  threshold below is carried by. Shown so that "the thresholds moved" is visible rather
   *  than mysterious. */
  dTypical: number
  /** The live thresholds, derived from `dTypical` this frame. Shown because an operator
   *  reading `d` against a threshold needs the threshold to be a number they can see. */
  tLo: number
  tHi: number
  presenceFloor: number
  /** Whether a baseline has been taken yet, and how long ago. A machine with no baseline
   *  has judged nothing. */
  hasBaseline: boolean
  baselineAgeMs: number
  /** The ROI's bright quantile. RECORDED, NOT USED — see CARD_QUANTILE. It is in the
   *  diagnostics only so the trace can carry it. */
  luma: number
  frames: number
  fires: number
  suppressedUnchanged: number
  suppressedNoCard: number
  /** CONSECUTIVE no-card verdicts. The one counter that is not a total, and it exists
   *  because the failure mode this machine was rebuilt to end was SILENT: on 2026-08-29
   *  twenty settles in a row were refused as an empty stand while the operator fed a box
   *  through, and nothing anywhere said so. A run of these means the baseline is wrong —
   *  almost always because the stand was not empty when the trigger was armed — and the
   *  screen renders it as the sentence it means rather than as a number that goes up. */
  noCardRun: number
  stalled: number
  /** Fires taken under the rescue bar rather than off a completed settle. On the HUD beside
   *  `stall`, because the two are the two halves of one accounting: an episode that outlasts
   *  `rescueAfter` x `maxMoveMs` ends EITHER in a rescued photograph or in a stall, and a
   *  session reads them together to know how much of its run rested properly. */
  rescued: number
  /** Refreshes on which the ratchet was overruled by the quantile path (D131). */
  escapes: number
}

/** What the screen can ask the machine to do. Deliberately NOT on the `Trigger` seam:
 *  re-baselining is one implementation's business and trigger.ts's contract is that the
 *  screen never learns which trigger is behind it. The screen reaches it through a ref the
 *  wrapper fills in, the same way it reaches the camera element. */
export type MotionControls = {
  /** Forget the baseline; the next still run takes a new one. Pressed after clearing the
   *  stand, which is why it is a control and not an automatic re-take: only a person knows
   *  the stand is empty, and a machine that re-baselined on its own judgement would be
   *  making the same claim from nothing that `cardLumaFloor` made from a constant. */
  rebaseline(): void
}

export class MotionMachine {
  private readonly p: MotionParams

  private prev: Float32Array | null = null
  private lastFired: Float32Array | null = null
  /* THE LAST `stillWindow` FRAMES, as a ring of "was this one under tLo" plus a running
   * count, because a settle is `stillFrames` OF them and no longer a consecutive run. The
   * field `stillWindow` carries the alternation this exists to survive.
   *
   * `stillSeen` gates on the window being FULL. A partial window would let an episode
   * settle on fewer marks than the rule names — two marks out of two seen is the
   * consecutive rule wearing a new name — and the sweep that chose 2-of-4 was run with the
   * window full, so shipping it any other way would ship a rule nobody scored. */
  private readonly stillMarks: Uint8Array
  private stillHead = 0
  private stillCount = 0
  private stillSeen = 0
  private movingSince: number | null = null
  private stallFlagged = false
  private refractoryUntil = 0

  /* THE SESSION'S BASELINE: the watch region as it stood when the machine was armed and the
   * scene first went still. Everything the presence gate knows comes from here.
   *
   * Null until the first still run, and null again after `rebaseline()`. A machine with no
   * baseline has no opinion about presence and does not fire — which is a fifty-millisecond
   * window at arm time, not a state a run can sit in. */
  private baseline: Float32Array | null = null
  private baselineAt: number | null = null

  /* The rolling window of d, as a ring so nothing is allocated per frame. Capacity covers
   * `noiseWindowMs` at 125 fps, comfortably past any camera this rig will see; the window
   * is trimmed by TIME rather than by count, so a slower stream simply holds fewer. */
  private readonly dTimes: Float64Array
  private readonly dVals: Float32Array
  private dHead = 0
  private dCount = 0
  private dScratch: Float32Array
  /* EVERY frame's d over the window, still or not — the second population the ratchet's
   * escape reads (D131). The still ring above stays the first word; this is the check on it. */
  private readonly aTimes: Float64Array
  private readonly aVals: Float32Array
  /** Whether a card was in view on that frame. THE FRACTION IS TAKEN OVER FRAMES WITH A
   *  CARD IN VIEW (D131): an empty stand is still on every frame, and a window that had just
   *  watched thirty seconds of it called the first cards a still majority for six seconds
   *  after feeding began — 7 of 29 cards on the first bright-lamp session, before the escape
   *  could see the population it exists to judge. */
  private readonly aPresent: Uint8Array
  private aHead = 0
  private aCount = 0
  private aScratch: Float32Array
  /** How many refreshes took the quantile path — on the HUD as `escape`, so a session can
   *  see the ratchet was overruled. */
  private escapes = 0
  private dTypical: number
  private tLo: number
  private tHi: number
  private presenceFloor: number

  /* One verdict per settle episode. Without this, a card sitting still re-runs the gates
   * every frame: the novelty suppression would count thirty times a second and the counter
   * stops meaning "cards suppressed". Reset by the next motion above tHi. Starts FALSE so
   * the first still run after arming is judged — which is where the baseline is taken, and
   * where an unchanged stand takes its one no-card verdict. */
  private episodeJudged = false

  readonly diag: MotionDiagnostics = {
    phase: 'watching',
    d: 0,
    dBase: 0,
    dTypical: 0,
    tLo: 0,
    tHi: 0,
    presenceFloor: 0,
    hasBaseline: false,
    baselineAgeMs: 0,
    luma: 0,
    frames: 0,
    fires: 0,
    suppressedUnchanged: 0,
    suppressedNoCard: 0,
    noCardRun: 0,
    stalled: 0,
    rescued: 0,
    escapes: 0,
  }

  constructor(params: MotionParams = DEFAULT_PARAMS) {
    this.p = params
    /* Math.max, so a stillWindow set under stillFrames cannot make a settle unreachable —
     * a trigger that can never fire and says nothing is the failure class this whole file
     * is about, and it must not be one typo away in a params object. */
    this.stillMarks = new Uint8Array(Math.max(params.stillFrames, params.stillWindow))
    const capacity = Math.max(64, Math.ceil((params.noiseWindowMs / 1000) * 125))
    this.dTimes = new Float64Array(capacity)
    this.dVals = new Float32Array(capacity)
    this.dScratch = new Float32Array(capacity)
    this.aTimes = new Float64Array(capacity)
    this.aVals = new Float32Array(capacity)
    this.aPresent = new Uint8Array(capacity)
    this.aScratch = new Float32Array(capacity)
    this.dTypical = Math.max(params.dFloor, params.dSeed)
    this.tLo = this.dTypical * params.stillK
    this.tHi = this.dTypical * params.moveK
    this.presenceFloor = Math.max(params.presenceMin, this.dTypical * params.presenceK)
    this.publishThresholds()
  }

  /** Fold one frame's verdict into the stillness window. */
  private markStill(quiet: boolean): void {
    const slot = this.stillHead
    this.stillCount -= this.stillMarks[slot] as number
    this.stillMarks[slot] = quiet ? 1 : 0
    if (quiet) this.stillCount += 1
    this.stillHead = (slot + 1) % this.stillMarks.length
    if (this.stillSeen < this.stillMarks.length) this.stillSeen += 1
  }

  /** Throw the window away. Motion above tHi ends the episode the marks belonged to. */
  private clearStillMarks(): void {
    this.stillMarks.fill(0)
    this.stillHead = 0
    this.stillCount = 0
    this.stillSeen = 0
  }

  /** Forget the baseline. See `MotionControls.rebaseline`. */
  rebaseline(): void {
    this.baseline = null
    this.baselineAt = null
    this.diag.hasBaseline = false
    this.diag.baselineAgeMs = 0
    this.diag.dBase = 0
    this.diag.noCardRun = 0
    /* The episode is reopened as well as the baseline cleared: without this, pressing the
     * control while a card sits still would take the new baseline but never judge against
     * it until something moved. */
    this.episodeJudged = false
    this.clearStillMarks()
  }

  private publishThresholds(): void {
    this.diag.escapes = this.escapes
    this.diag.dTypical = this.dTypical
    this.diag.tLo = this.tLo
    this.diag.tHi = this.tHi
    this.diag.presenceFloor = this.presenceFloor
  }

  /** Fold this frame's d into the window and, every `NOISE_REFRESH_FRAMES`, re-derive the
   *  thresholds from its median. The median rather than a mean or an EMA: still frames are
   *  60-87% of every session measured, so the median IS the still level and a motion burst
   *  cannot pull it — which is precisely the objection this file used to raise against
   *  adapting at all. */
  private trackNoise(nowMs: number, d: number, present: boolean): void {
    const capacity = this.dVals.length
    /* ONLY STILL FRAMES DEFINE STILLNESS. See `noiseWindowMs` for the argument; the short
     * form is that this one comparison is what stops a hand hovering in frame from teaching
     * the machine that hovering is what quiet looks like. */
    if (d < this.tLo) {
      this.dTimes[this.dHead] = nowMs
      this.dVals[this.dHead] = d
      this.dHead = (this.dHead + 1) % capacity
      if (this.dCount < capacity) this.dCount += 1
    }
    this.aTimes[this.aHead] = nowMs
    this.aVals[this.aHead] = d
    this.aPresent[this.aHead] = present ? 1 : 0
    this.aHead = (this.aHead + 1) % capacity
    if (this.aCount < capacity) this.aCount += 1

    if (this.diag.frames % NOISE_REFRESH_FRAMES !== 0) return

    const cutoff = nowMs - this.p.noiseWindowMs
    let n = 0
    for (let i = 0; i < this.dCount; i += 1) {
      const at = (this.dHead - 1 - i + capacity * 2) % capacity
      if ((this.dTimes[at] as number) < cutoff) break
      this.dScratch[n] = this.dVals[at] as number
      n += 1
    }
    /* Under a second of still frames is not a measurement of anything; the seed stands
     * until it is. `dSeed` is chosen to reproduce Gate C's hand-tuned pair exactly, so the
     * machine boots at the constants that run was confirmed on. */
    if (n < 25) return

    /* THE RATCHET'S ESCAPE (D131). Count the whole window; if the still population is a
     * minority of it, the still level is being under-estimated and the quantile path
     * decides. `stillFractionMin` carries the measurement. */
    let all = 0
    let stillPresent = 0
    for (let i = 0; i < this.aCount; i += 1) {
      const at = (this.aHead - 1 - i + capacity * 2) % capacity
      if ((this.aTimes[at] as number) < cutoff) break
      if ((this.aPresent[at] as number) === 0) continue
      const v = this.aVals[at] as number
      this.aScratch[all] = v
      all += 1
      if (v < this.tLo) stillPresent += 1
    }
    const rest =
      all >= 25 && stillPresent / all < this.p.stillFractionMin
        ? Math.max(this.p.dFloor, quantileOf(this.aScratch.subarray(0, all), this.p.restQuantile))
        : null
    /* A REST MUST BE SMALLER THAN A CARD ARRIVING. The quantile of a window that is nothing
     * but motion — a jam, a hand, a synthetic churn — is a motion level, and taking it as
     * the still level would call everything still. The presence floor is the change a card
     * makes to the scene; a frame-to-frame change at or above it is not a resting card, and
     * the ratchet keeps the word. No new constant: on every session here rest sits 2-9
     * against a floor of 16. */
    if (rest !== null && rest < this.presenceFloor) {
      this.escapes += 1
      this.dTypical = rest
      this.tLo = rest
      this.tHi = Math.max(rest * (this.p.moveK / this.p.stillK), rest + 1)
      this.presenceFloor = Math.max(this.p.presenceMin, this.dTypical * this.p.presenceK)
      this.publishThresholds()
      return
    }

    /* The MEDIAN of the still frames, not their mean and not their p95. The sweep across
     * all five traces puts the median at the centre of the plateau; the high quantiles fall
     * off a cliff (q95 at k = 1.8 scores 37 of 85 on the trace the median scores 86 on),
     * because a truncated population's tail is the frames that were nearly not still. */
    const median = quantileOf(this.dScratch.subarray(0, n), 0.5)
    this.dTypical = Math.max(this.p.dFloor, median)
    this.tLo = this.dTypical * this.p.stillK
    this.tHi = this.dTypical * this.p.moveK
    this.presenceFloor = Math.max(this.p.presenceMin, this.dTypical * this.p.presenceK)
    this.publishThresholds()
  }

  /** One decoded frame. `cells` is the ROI as luma values; the machine COPIES what it
   *  keeps, because the sampler reuses its buffer — holding the reference would make prev
   *  and current the same array and d identically zero: a trigger that never fires, with
   *  no error anywhere. */
  step(nowMs: number, cells: Uint8ClampedArray | Float32Array): MotionEvent | null {
    this.diag.frames += 1

    /* Recorded, not used. `CARD_QUANTILE` carries the argument; the short form is that this
     * is the statistic the old presence gate compared against a constant, it is kept so a
     * trace can still show a session's lighting drift, and nothing branches on it. */
    this.diag.luma = quantileOf(cells, CARD_QUANTILE)

    if (this.baseline !== null) {
      let base = 0
      for (let i = 0; i < cells.length; i += 1) {
        base += Math.abs((cells[i] as number) - (this.baseline[i] as number))
      }
      this.diag.dBase = base / cells.length
      this.diag.baselineAgeMs = nowMs - (this.baselineAt ?? nowMs)
    }

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
    this.trackNoise(nowMs, d, this.baseline !== null && this.diag.dBase >= this.presenceFloor)

    if (d > this.tHi) {
      // MOVING. A new episode: whatever verdict the last settle got, the next one is new.
      if (this.movingSince === null) this.movingSince = nowMs
      this.clearStillMarks()
      this.episodeJudged = false
      this.diag.phase = 'moving'
      if (!this.stallFlagged && nowMs - this.movingSince > this.p.maxMoveMs) {
        this.stallFlagged = true
        this.diag.stalled += 1
        return 'stalled'
      }
      return null
    }

    /* UNDER tHi, so this frame is evidence about stillness whichever side of tLo it falls
     * on. The Schmitt band is a mark of ZERO here rather than a reset of the window, and
     * that is the D84 change: the alternation `stillWindow` documents is a card sitting
     * still whose every other frame lands in the band, and a rule that threw the window
     * away on each of those could never see it. */
    const quiet = d < this.tLo
    this.markStill(quiet)

    /* A settle may only COMPLETE on a quiet frame, because the fire photographs this one.
     * Measured over the three D84 traces: requiring it costs nothing — both cards the
     * window recovers land on a quiet frame anyway — and without it a capture could be
     * taken from a frame the machine had just called not-confidently-still. */
    const ordinary =
      quiet && this.stillSeen >= this.p.stillWindow && this.stillCount >= this.p.stillFrames

    /* THE RESCUE, 2026-09-11. An episode that has run `rescueAfter` x `maxMoveMs` without a
     * settle takes `rescueK` x tLo as its bar and drops the window requirement with it —
     * because the window is what refused nine of the fourteen misses measured, on frames the
     * machine had ALREADY called quiet. A card that lands two frames after a transit ends has
     * one quiet frame and then the next card's motion; `stillSeen` never reaches
     * `stillWindow` and the card is dropped in silence.
     *
     * IT OPENS LATE ON PURPOSE AND THE AGE IS THE WHOLE SAFETY ARGUMENT. `stillWindow` is
     * what stops a dip DURING a transit from firing, and retiring it from the first frame of
     * an episode takes the corpus's double count from 2 to 21. The episode's own age is the
     * machine's only statement that the transit cannot still be happening; `rescueAfter`
     * carries where that line was swept to.
     *
     * WHAT IS NOT RELAXED: presence, novelty and the refractory, all below and all unchanged.
     * A rescue is a statement about STILLNESS ONLY — it can photograph a card a little sooner
     * than the machine would like, and it can never photograph an empty stand or the same
     * card twice. */
    const rescued =
      !ordinary &&
      this.movingSince !== null &&
      nowMs - this.movingSince >= this.p.rescueAfter * this.p.maxMoveMs &&
      d < this.tLo * this.p.rescueK
    const settled = ordinary || rescued
    this.diag.phase = settled ? 'watching' : 'settling'

    if (!settled) {
      /* THE STALL CLOCK RUNS, and this frame does not clear it however quiet it was.
       * `movingSince` means "since the scene last SETTLED", not "since d last crossed tHi"
       * and no longer "since the last frame under tLo" — which is what makes a hand
       * hovering in the band, and an alternation that never completes, both expire. The
       * middle reading was already argued here; the third is D84's, and the count that
       * convicted the second is in `maxMoveMs`. */
      if (this.movingSince === null) this.movingSince = nowMs
      if (!this.stallFlagged && nowMs - this.movingSince > this.p.maxMoveMs) {
        this.stallFlagged = true
        this.diag.stalled += 1
        return 'stalled'
      }
      return null
    }

    // SETTLED.
    this.movingSince = null
    this.stallFlagged = false

    /* THE BASELINE IS TAKEN HERE, on the first still run after arming — "the watch region
     * as it stood when you armed", which is what the operator is asked to make an empty
     * stand. Taken before the verdict below rather than instead of it, so the arm-time
     * scene is judged against itself and reads dBase 0: an empty stand takes exactly one
     * no-card verdict and then waits for motion, unchanged from the behaviour this machine
     * has always had.
     *
     * A CARD ON THE STAND AT ARM TIME IS NOW THE BASELINE, and is therefore refused rather
     * than captured. That is a real behaviour change and it is forced rather than chosen:
     * the old machine captured it only because the card was bright and 90 happened to sit
     * under it, which is the exact mechanism the four traces convict. Nothing in the frame
     * distinguishes "the stand as it normally looks" from "the stand with a card on it"
     * without a reference, and at arm time the reference is what is being established. The
     * loss is one photograph, at the top of a run, announced by `noCardRun` on the HUD. */
    if (this.baseline === null) {
      this.baseline = Float32Array.from(cells)
      this.baselineAt = nowMs
      this.diag.hasBaseline = true
      this.diag.baselineAgeMs = 0
      this.diag.dBase = 0
    }

    if (this.episodeJudged) return null
    /* Inside the refractory the episode stays UNJUDGED and the still-counter keeps
     * counting, so the first step after expiry delivers the verdict. That is the whole
     * "deferring" property: a card that arrives and settles fast is captured late rather
     * than not at all. */
    if (nowMs < this.refractoryUntil) return null

    this.episodeJudged = true

    /* PRESENCE, AND IT IS A STATEMENT ABOUT CHANGE RATHER THAN ABOUT BRIGHTNESS. Measured
     * over the four saved traces: an empty stand sits 1.10-1.38 from its own baseline and
     * every card of every session sits above 17.4. The threshold rides this session's own
     * noise, so the same code is correct on a rig whose cards read 61 and on one whose
     * cards read 244 — which no value of the old `cardLumaFloor` was. */
    if (this.diag.dBase < this.presenceFloor) {
      this.diag.suppressedNoCard += 1
      this.diag.noCardRun += 1
      return 'suppressed:no-card'
    }
    this.diag.noCardRun = 0

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
    if (!rescued) return 'fire'
    this.diag.rescued += 1
    return 'fire:rescued'
  }
}

/* ---------------------------------------------------------------------- the DOM half */

/* The value at `q` through the sorted cells, without sorting them.
 *
 * QUICKSELECT, AND IT COPIES FIRST. The caller's `cells` is the sampler's reused buffer —
 * `step`'s own docstring is about exactly this hazard — and partitioning in place would
 * scramble the frame the diff loop below is about to read. The copy is 1064 floats.
 *
 * Ties and short buffers fall out of the loop rather than being special-cased: `lo === hi`
 * returns that element, and an empty buffer cannot reach here because `step` is only called
 * with the ROI. */
function quantileOf(cells: Uint8ClampedArray | Float32Array, q: number): number {
  const values = Float32Array.from(cells)
  const target = Math.min(values.length - 1, Math.max(0, Math.floor((values.length - 1) * q)))
  let lo = 0
  let hi = values.length - 1
  while (lo < hi) {
    const pivot = values[(lo + hi) >> 1] as number
    let i = lo
    let j = hi
    while (i <= j) {
      while ((values[i] as number) < pivot) i += 1
      while ((values[j] as number) > pivot) j -= 1
      if (i <= j) {
        const swap = values[i] as number
        values[i] = values[j] as number
        values[j] = swap
        i += 1
        j -= 1
      }
    }
    if (target <= j) hi = j
    else if (target >= i) lo = i
    else break
  }
  return values[target] as number
}

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
export const DIAG_INTERVAL_MS = 200

/** One decoded frame of the watch region, delivered to whoever is deciding on it.
 *
 *  THE SAMPLER IS SHARED AND THE MACHINES ARE NOT (D130). Two triggers read the lens now —
 *  the settle machine above and `src/cadence.ts`'s beat-locked one — and both want exactly
 *  this: one 64x36 luma grid per decoded frame, the watch region cut out of it, on one
 *  monotonic clock. Everything below the `onRoi` call is a fact about the <video> element
 *  and the browser's frame pacing, none of it about cards, which is why it lives once. */
export function startWatchSampler(
  video: RefObject<HTMLVideoElement | null>,
  onRoi: (nowMs: number, roi: Float32Array) => void,
): () => void {
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
    onRoi(nowMs, roi)
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
}

export function motionTrigger(
  video: RefObject<HTMLVideoElement | null>,
  onDiagnostics?: (diag: MotionDiagnostics) => void,
  params: MotionParams = DEFAULT_PARAMS,
  /** Every frame the machine sees, verbatim: the clock, both signals, the verdict, and the
   *  sampler's REUSED watch-region buffer — a receiver that keeps anything must copy it,
   *  the same rule the machine lives by. This is the whole seam the trace logger hangs
   *  from (src/trace.ts); the trigger itself records nothing. */
  onFrame?: (
    tMs: number,
    d: number,
    dBase: number,
    luma: number,
    event: MotionEvent | null,
    cells: Float32Array,
  ) => void,
  /** Filled in while the trigger is armed and nulled on teardown, so the screen can offer
   *  `Re-baseline` only while there is a machine to ask. A ref rather than a method on
   *  `Trigger`: the seam's contract is that the screen never learns which trigger is
   *  behind it, and one implementation's control does not belong in a shared interface. */
  controls?: RefObject<MotionControls | null>,
): Trigger {
  return {
    /* The machine string the screen renders — docs/DESIGN.md's idiom, and the one line of
     * UI trigger.ts promised would change when this module arrived. */
    name: 'motion',

    start(onFire) {
      const machine = new MotionMachine(params)
      if (controls !== undefined) controls.current = { rebaseline: () => machine.rebaseline() }

      let lastDiagAt = 0
      const report = (now: number, always: boolean) => {
        if (onDiagnostics === undefined) return
        if (!always && now - lastDiagAt < DIAG_INTERVAL_MS) return
        lastDiagAt = now
        onDiagnostics({ ...machine.diag })
      }

      const stop = startWatchSampler(video, (nowMs, roi) => {
        const event = machine.step(nowMs, roi)
        /* BOTH FIRING VERDICTS REACH THE SCREEN. `fire:rescued` differs from `fire` in what
         * it says about the frame, never in what the screen must do with it — a card that is
         * about to be replaced needs its photograph now. The distinction is for the trace and
         * the HUD; a `=== 'fire'` here would drop every rescued card in silence, which is the
         * failure the rescue exists to end. */
        if (event === 'fire' || event === 'fire:rescued') onFire()
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
