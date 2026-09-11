# Motion trigger — execution spec and rig-tuning protocol (Gate C)

Written 2026-08-22, the day it was built. D19 is the decision; this file is the mechanism,
the derivations, and the protocol for the part no computer can do — tuning at the rig.
`docs/GATES.md`'s Gate C section carries the measurements every number here leans on.

## STATUS — CONFIRMED LIVE AT 85/85, REBUILT ON MEASUREMENTS 2026-08-31, CORRECTED 2026-09-01, THE RATCHET GIVEN AN ESCAPE 2026-09-11

The trigger exists: `app/src/motion.ts` behind `app/src/trigger.ts`'s seam, armed from a
mode toggle on the capture screen, with a live HUD, a swallowed-fire counter and a
`Re-baseline` control. Two specs cover it — `app/tests/motion.spec.ts` proves the machine's
arithmetic against an exact answer key, and `app/tests/motion-live.spec.ts` drives the real
screen in a real browser with a synthetic camera stream, from arming through firing to the
dropped-fire count. Both run in `make design-check`.

**The 85/85 feeder run stands and is not being re-litigated.** 2026-08-23, 72.5 s at a
620 ms period, 85 of 85 cycles fired with zero doubles and zero misses, one designed
`no-card` suppression at arm time, captured into a real box (95) through the full path. That
clears the 50-card bar for the trigger half of Gate C; the gate still owes the pipeline half
(identify → join → emit → reconcile on a feeder-paced box) and foil under this lamp.

**EVERY THRESHOLD IS NOW A MULTIPLE OF SOMETHING THE SESSION MEASURED (D81), and the reason
is that the constants were portable to exactly one rig.** Four saved traces re-scored with
`scripts/score-trace.py` say it plainly. The card-present gate was a brightness against the
constant 90; an empty stand on the reference rig reads 57 and a real card on the under-lit
rig reads 61, so **no constant separates those populations**, and that one refused **38 real
cards as an empty stand, silently** — 20 of 20 on 2026-08-29 21:34, 13 of 15 on 21:38, 5 of
24 on 2026-09-01 — against one correct refusal in the whole corpus. Presence is now the
distance from the watch region as it stood when the trigger was armed: an empty stand sits
1.10–1.38 from its own baseline and every card of every session sits 17.4–167.4, a 43× gap
where brightness gave 1.07×. `tLo` and `tHi` ride the median frame-to-frame difference of
the last 8 s of frames the machine already called still, and score **86, 86, 20, 15, 24**
across the five traces where the hand-tuned constants scored 72, 86, 20, 15, 24. The seed
reproduces 4.50 and 8.00 to the last digit.

**THE FIRST THREE SESSIONS RUN ON THAT MACHINE FOUND TWO MORE DEFECTS, AND D84 IS THE
CORRECTION.** 2026-09-01, three armed runs, 93 s of feeding, 69 fires — every one of which
reached disk, so the plumbing was never in question. What the traces and the photographs
together say is that **two fires photographed the bare stand** and **four cards were fed and
never photographed at all**, and that every one of those six sits in the first two seconds
after arming. After that the cadence is metronomic: 43 consecutive fires in the longest run
with no gap over 1.0 s.

Three changes, each with its own row in §2's table: a settle is `stillFrames` of the last
`stillWindow` rather than a consecutive run; the stall clock is cleared by a COMPLETED settle
rather than by any quiet frame; and `presenceMin` is 16.0, sized to a hand arriving with the
first card rather than to lamp drift. Together they turn the four silent losses into two
photographs and two stalls, and the two junk photographs into refusals — with **zero false
stalls across 67 good captures and the 217 verdicts of the five earlier traces**, which are
byte-identical under the new rule. D84 carries the argument and the measurements.

**One of the three walks a step BACK from D81 and the entry says so.** `presenceMin` at 16.0
binds over `presenceK` × the session's measurement on this rig, so the presence gate is
decided by a constant again. It is a debt rather than a design: what the floor must clear is
a HAND, and no session statistic measures how big a hand is in frame.

**§4's protocol changed shape because of D81.** The parameters are no longer what a rig
session tunes; the rig session now reads whether the machine's own measurements are sane and
whether the baseline was taken on an empty stand. Read §4 before treating any number here as
something to edit — and read D84's ruling 3 before treating `presenceMin` as re-derivable
from anything this machine measures for itself.

## 1. The two halves

**`MotionMachine` is pure**: `step(nowMs, cells)` in, event out. No DOM, no clock of its
own, no camera. That is what makes it testable to an answer key, and it is deliberately
the same split `geometry/` makes between detection and cropping.

**The DOM wrapper is thin and untestable off a browser**: it downsamples the `<video>` to
a 64×36 luma grid on one reused canvas (8e9a46b's lesson, at 30× the frequency), slices
the watch region, and feeds the machine once per decoded frame — `requestVideoFrameCallback`
where it exists, display-rate `requestAnimationFrame` behind a `currentTime` guard where it
does not, because rAF at 60 Hz over a 30 fps stream diffs alternate frames against
themselves and fires at half the configured settle time with no symptom.

## 2. The machine, and where each number came from

Phases: watching → moving → settling → (verdict) → watching, with a deferring refractory.

| parameter | value | what it is a multiple of, and where the number came from |
|---|---|---|
| grid | 64×36 | each cell averages ~3,600 sensor pixels; noise attenuates ~60× |
| watch region | centre, inset 20% x / 10% y | 15 of 53 Gate B frames carry a second card in the feed path; card placement repeats to ~30 px |
| `stillK` | 2.0 | `tLo` = this × the session's median STILL-frame difference. Swept over all five traces at q 0.5–0.95 and k 1.4–2.5: 2.0–2.5 is a plateau where every trace meets or beats what the constants scored live. 2.0 is chosen for the middle of it rather than the edge of a peak — the failure mode of the 2026-08-23 retune, which swept one run |
| `moveK` | 3.556 | `tHi` = this × the same measurement. 2.0 × 16/9, which holds `tHi`/`tLo` at the 1.78 the hand-tuned 4.5/8.0 pair had. The band is a ratio, not a difference: a fixed 3.5-wide band is wide on a quiet rig and absent on a noisy one |
| `dSeed` | 2.25 | what the still-frame difference is taken to be until 25 still frames have been seen. Chosen so the seeded thresholds are **4.50 and 8.00 exactly** — Gate C's own pair, so the machine boots on the confirmed run's numbers |
| `dFloor` | 1.0 | floor under the measurement, so a rock-steady mount cannot drive `tLo` toward zero. Sits under every session measured (1.75–3.22) without touching any |
| `noiseWindowMs` | 8000 | ~200 frames at the observed 25 fps and a dozen feeder cycles. **Only frames already judged still go in** — see below |
| `stillFrames` | 2 | frames under `tLo` that mean settled — counted over `stillWindow`, not consecutively (D84) |
| `stillWindow` | 4 (133 ms) | how many recent frames those 2 are counted over, and the window must be FULL. **A consecutive run is defeated absolutely by a two-frame alternation**, measured on a card motionless for 500 ms whose `d` read 2.71 5.40 2.63 5.54 2.83 5.14 against a `tLo` of 4.18 — five runs of one, no verdict, card lost. Swept over the three 2026-09-01 21:xx sessions, 2-of-4 recovers two of the four cards lost that way and changes no other verdict; 2-of-3 and 3-of-5 recover fewer. Fire latency (stillWindow+1)·f = 167 ms = 36% of the 458 ms worst observed cycle |
| `refractoryMs` | 250, deferring | sized to the <250 ms capture round trip, not the card cycle. A time, not a light level |
| `tNovel` | 4.0 | **deliberately still absolute.** Across all five traces and 217 verdicts the `suppressed:unchanged` count is zero, so there is no measurement to take a multiple of; and scaling it to session noise would push it DOWN on a quiet rig, making suppression more likely — the wrong direction, since a false pass is a duplicate `U` fixes and a false suppression is a silent §5.5 loss |
| `presenceK` | 3.0 | the presence floor is this × the session's still-frame difference. Against its own baseline an empty stand reads 1.10–1.38 and every card of every session reads 17.4–167.4; 3.0 puts the threshold at 5.5–9.7, four to seven times over the empty stand and three to ten times under the dimmest card |
| `presenceMin` | 16.0 | absolute floor, **set by a HAND rather than by drift** (D84, correcting D81). An undisturbed stand does not creep: it holds 2.0–2.5 for as long as it is left alone. What crosses 8.0 is the operator's hand arriving with the first card, which holds still for two frames on the way in — and at 8.0 that fired, twice, photographing the bare stand. 16.0 is 1.4× over the worst approach measured (11.15) and 2× under the quietest card in the same sessions (32.5). **It now BINDS over `presenceK` × the measurement, which is a debt** — see D84 |
| `maxMoveMs` | 1250 | ~2× the feeder period; a jam surfaces as `stalled` and does NOT fire. A time, like the refractory. **The clock is cleared by a COMPLETED settle** (D84): cleared by any quiet frame, as it was, the alternation above reset it every other frame and `stalled` could never expire — it did not fire once across three sessions and four cards left unphotographed |

### The measurement only admits frames it already called still, and that is the whole safety argument

This file used to say the thresholds were "fixed rather than adaptive" because "an EMA floor
that learns during slow motion is a way to go blind". That objection was right about a moving
average and
right about admitting motion, and it is answered rather than ignored: **a frame only enters
the window if `d < tLo`.** A hand resting half in frame, a jammed feeder, a card creeping —
every one of those sits above `tLo`, never reaches the estimate, and cannot teach the machine
that hovering is what quiet looks like. The estimate moves only on frames already judged
still, and the multiplier is what lets it climb: a session whose still noise reads 3.5 lands
`tLo` at 7.0, well clear of it.

**The one thing this cannot recover from is a session whose noise is entirely above the
seeded 4.5.** No frame is ever still, nothing enters the window, nothing adapts. That failure
is LOUD — not one capture is taken and the HUD sits in `moving` — which is the opposite of
the 2026-08-23 failure, where 14 of 86 cards vanished while everything looked normal. A
median over a window that admitted motion would have been quieter and wronger.

### The presence gate is a distance, and this is the third attempt at it

**Attempt one** compared the watch region's MEAN brightness against 90. **Attempt two**
(2026-08-29) compared its bright QUANTILE against 90, and its own table of "empty stand"
brightnesses was derived from twenty frames that were photographs of real cards — a refusal
had been read as evidence of what was on the stand, and nobody rendered them. **Attempt
three** compares nothing to a brightness at all.

| scene | rig / session | bright quantile |
|---|---|---|
| **empty stand** | reference rig, 2026-08-23 | **57** |
| card | under-lit rig, 2026-08-29 21:34 | **61**–134 |
| card | 2026-09-01 | 77–171 |
| card | reference rig, 2026-08-23 | 196–244 |

That table is why there is no fourth constant to try. `scripts/score-trace.py contact` draws
every verdict's frame as a labelled sheet, and it exists because the only thing that settles
what a frame contains is looking at it.

**What the change gives up, deliberately:** a card already at the lens when the trigger is
armed becomes the baseline and is refused rather than captured. That is forced rather than
chosen — the old machine captured it only because the card was bright and 90 sat under it —
and the loss is one photograph at the top of a run, ANNOUNCED: `noCardRun` counts consecutive
refusals and the screen renders three in a row as the sentence it means, with the
`Re-baseline` control under it.

Three gates on a fire, one verdict per settle episode: stillness (synchronisation — fire
once per card, not mid-swap; the sharpness justification was tested against the real
frames and failed an anisotropy test), novelty against the last-fired frame (the gate that
actually prevents double-captures), and presence — distance from the session's baseline.
All three are now statements about CHANGE and none is a statement about brightness, which
is also why `geometry/detect.py`'s tone segmentation is still not wanted here: it measured
0/53 on this rig, and a distance from a reference needs none of that method's premises
either.

**The buffer-copy rule is load-bearing**: the sampler reuses its arrays, so the machine
copies everything it keeps. Holding a reference makes prev and current the same array, d
reads identically zero, and the trigger never fires — with no error anywhere. The machine
spec pins this with a deliberately mutated shared buffer.

## 3. The screen's half of the contract

The seam's split (trigger.ts): settling, novelty, card-presence and the refractory are the
trigger's; in-flight, halt, no-box and camera-not-ready are the screen's. Motion mode adds
one obligation the manual mode never needed: **a declined fire is counted, by reason, in
state; the HUD surfaces the aggregate as `dropped`, and the one reason that carries its own
instruction — halted, with the feeder possibly still delivering — is rendered in the halt
banner as the sentence it means** ("that many cards may have passed the lens unrecorded —
set them aside and re-feed"). Counters are per accounting period, not per session: arming
resets all of them, and a resume clears the halted count the banner just spent.

How the operator knows it is on, threefold, all on the capture screen: the pressed chip
(`key` / `motion`), the machine string under the capture button (`manual:C` → `motion` —
the line trigger.ts always promised), and the HUD, which exists only while the machine is
armed and shows
`phase · d · tlo · thi · typ · dbase · floor · fires · same · empty · stall · dropped`.

**Every number on that row is one the machine decides on, and that is a rule the row earned.**
It carried `luma` for two rig sessions while the presence gate read a different statistic,
which is how a rig gets debugged against the wrong number; the bright quantile survives in
the trace, as evidence about lighting, and gates nothing. `d` is the live difference,
`typ` is what the session measured, `tlo`/`thi` are the multiples of it, and `dbase`/`floor`
are the presence decision's two halves. Arming is session-only (D19): every reload starts
manual.

**A run of refusals is a sentence, not a counter.** `empty` is a total and totals do not say
"this is happening right now" — on 2026-08-29 twenty settles in a row were refused while a
box went through the lens and the only sign was that total climbing beside six others.
Three consecutive refusals render as what they mean, naming the likely cause (a baseline
taken with something on the stand) and the remedy under it. **`Re-baseline` is a button
rather than a letter**: it is performed after clearing the stand, with a hand already off the
keyboard, and the letter it would want (`b`) is the box field's.

The C key is genuinely disarmed in motion mode — one trigger behind the seam at a time —
and its `kbd` chip leaves the capture button. The button itself stays live in both modes:
a manual fire past a hesitant machine is an override, not a mode. Undo never automates.

**The replay guard outranks the machine.** While a halted photograph's id is held
(`captureIdRef`), the next capture goes out under that id and, on a replay, the server
ignores the image — so a machine fire in that window would send the NEXT card's frame under
the halted card's id and let it pass the lens recorded-in-name-only. Machine fires are
swallowed as `held` until the id clears, the halt banner says to capture the held card with
the button, and the machine resumes on its own once the human has resolved the ambiguity
the id exists to resolve.

## 4. Rig-tuning protocol — the part that needs a person

**THIS IS NO LONGER A PARAMETER-TUNING PROTOCOL.** It was, and the reason it stopped is that
the tuning it asked for was portable to exactly one rig: the 2026-08-23 session swept one
trace, landed on `tLo` 4.5 and `tHi` 8.0, and the presence constant beside them then refused
38 real cards on two other rigs — 18 of which the 2026-08-29 "fix" left refused (§2). The machine takes its own measurements now. What a person still has to
do is **check that the measurements are sane and that the baseline is honest** — neither of
which any amount of arithmetic can decide from inside the frame.

Cost: ~10 minutes at the rig, one box of expendable commons, before the 50-card
confirmation run.

1. **Arm on an EMPTY STAND. This is the one step that cannot be got wrong.** The watch
   region as it stands when you arm is what the whole session will call "nothing". Expect
   exactly one `empty` verdict at arm and silence after. **If a card is on the stand when
   you arm, it becomes the baseline** and the machine will refuse it and every card that
   looks like it — which it says out loud, three refusals in a row, with the `Re-baseline`
   control under the sentence. Clear the stand and press it.
2. **Read the machine's own measurement, nothing moving.** `typ` is this session's median
   still-frame difference and `tlo`/`thi` are 2.0× and 3.556× it. On the reference rig `typ`
   idles near 2.2 and the pair lands near 4.5/8.0; the sessions traced since read 1.75–3.22.
   **A `typ` above ~4 is a rig problem, not a parameter problem** — mains flicker (pin the
   shutter to a multiple of the mains period, §10.0's list), an unstable lamp, or a mount
   that moves. Fix the rig; the thresholds will follow it on their own.
3. **Read the gap, not the absolute.** Place one card by hand and watch `dbase` against
   `floor`. A card should read tens; the empty stand reads under 1.5. Traced across four
   rigs the separation is 17.4 against 1.38 at worst. **A card that reads close to `floor`
   is a framing problem** — the card is barely inside the watch region — not a number to
   lower.

   **AND WATCH `dbase` WHILE YOUR HAND IS STILL MOVING IN, which is the reading D84 was
   missing.** The stand at rest is not what decides `presenceMin`; the approach is. Reach in
   as you would to place a card and read the peak before the card lands — measured on this
   rig it is 8–11, and the floor sits at 16 to clear it. **If your approach reads near 16,
   that is the number to raise**, and it is the one quantity in this file the machine cannot
   take for itself.
4. **Swap signal.** Hand-swap cards at feeder-ish pace. Every swap should spike `d` past
   `thi` and every settle should fire exactly once; `same` should stay at zero unless you
   re-present the same card, and then it should count exactly once per re-present.
5. **The feeder, empty run.** Feeder running, no captures consumed (no box selected —
   fires land in `dropped`, which is the point: count feeder cycles against `fires`).
   Agreement within one or two over a hopper is the pass. Watch `stall`: the feeder's own
   motion profile has never been measured, and if its advance reads as continuous motion
   longer than 1250 ms, `maxMoveMs` is the one constant here still worth raising by hand.

   **`stall` MEANS MORE SINCE D84 AND IS THE COUNTER TO READ FIRST.** It no longer only
   catches a jam: the clock is cleared by a completed settle rather than by any quiet frame,
   so a card that sits in the watch region without ever settling — the failure that lost four
   cards silently — now expires it. A stall during a feeder run is a card the machine did not
   photograph and is telling you about. Re-present it; it is not a number to raise.
6. **Save the trace before disarming — every step above, and this one, is in the file.**
   The `Save trace` button under the HUD downloads the whole armed session: every frame's
   `(t, d, dBase, luma)`, plus the exact watch-region pixels each fire/suppression/stall was
   decided on, plus once-a-second keyframes. It is self-describing (the parameters travel
   with the evidence) and lands in the browser's Downloads folder as
   `motion-trace-<timestamp>.json`. A trace survives disarming — it resets only when motion
   is armed again — so save late rather than early.
7. **The 50-card run** (Gate C's own bar), box selected, milliseconds now on every
   `captured_at`: reconcile `fires` against records, `dropped` against the halt story, and
   the cadence against the trace. Then a full box.

### Scoring a trace offline — `scripts/score-trace.py`

The promise that a saved trace makes another rig trip unnecessary was made in 2026-08-23 and
kept by hand three times, and **the second of those got it wrong**: the 2026-08-29 presence
fix derived its "empty stand" brightnesses from twenty frames that were photographs of real
cards, because a refusal was read as evidence of what was on the stand and nobody rendered
them. The pass is written down now.

```
scripts/score-trace.py summary  <trace.json> [more.json ...]
scripts/score-trace.py presence <trace.json>
scripts/score-trace.py sweep    <trace.json> [more.json ...]
scripts/score-trace.py contact  <trace.json> <out.png>
```

`summary` says what the machine did live and what today's form would do; `presence` re-runs
the card-present gate over each verdict's own pixels; `sweep` scores the stillness
thresholds across a grid **over every trace at once**, because one trace cannot choose a
parameter and choosing one from a single run is the mistake §2's table is a receipt for; and
`contact` writes the verdict frames out as a labelled PNG. **Look at the contact sheet before
believing any claim about what was on the stand.** `summary`, `presence` and `sweep` are
stdlib only; `contact` needs Pillow and says so.

A parameter that a sweep says should move is a decision entry, not an edit: the constants in
`app/src/motion.ts` are now ratios with derivations attached, and moving one without moving
its argument is how the file got into the state D81 found it in.

### The ratchet's escape, and one quiet frame of three (D131, 2026-09-11)

**The noise tracker could lower its idea of still and never raise it, and a bright lamp put
the rest above it.** Still frames were defined only by frames already under `tLo`, so on a
rig where a resting card reads d 5-8 — brightness jitter under the owner's lamp, |Δluma| p90
of 6-8 at rest against 2-3 on every earlier session — the tracker converged to 4.5-7 while the
rest sat at 7-9, and the settle rule fired on 5 of 29 cards with every readout looking normal.
D130 read that as a scene that was never still. It was still; the machine's word for still
was wrong in the one direction the ratchet could not move.

**The escape.** When the frames the machine calls still fall under `stillFractionMin` (0.30)
of the frames with a card in view over the noise window, the still level is taken from
`restQuantile` (0.25) of all of them, `tHi` keeping its ratio — and only when that quantile is
under the presence floor, because a frame-to-frame change no smaller than a card arriving is
not a rest. The fraction is over frames with a card in view because an empty stand is still on
every frame. **Measured in both directions**: the eight earlier sessions keep 46-83% of their
frames under `tLo` and change zero verdicts (the escape trips a handful of refreshes on the
three 2026-09-01 sessions and decides nothing); the four 2026-09-11 sessions replay **31, 21,
45, 85** against 5 and 5 live on the two the ratchet lost. The HUD's `escape` count is how a
session sees it happen.

**One quiet frame of the last three.** D84's two-of-four, amended: the bright-lamp feeder
rests a card two to four frames with calm frames around it, and a window of four never filled.
A frame under `tLo` is still by definition and is photographed on; a scene with NO quiet frame
still expires the stall clock, which is D84's silent-loss guard unchanged. Swept against every
old session it changes no count and recovers the cards D84 counted as stalls.

**The dim lamp was not a fix**, and the trace says so: 65 fires and 13 stalls live, ten real
misses on cards that slid for 1.7 s, seven gaps that were pauses — about 87%, with worse
photographs.

## 5. Known limits, and what this deliberately does not do

**A manual capture in motion mode does not update the machine's last-fired frame.** The
Capture button stays live as an override, but the machine has no path into `doCapture` —
by the seam's own design — so a card captured manually can later be captured AGAIN by the
machine if a wobble opens a new settle episode: the card is novel against a last-fired
frame the machine took before it. The remedy is the one D10 already provides — undo the
duplicate; the photo is of a card still at the lens — and the honest framing is that the
override is for rescuing one card, not for running mixed-mode. If the rig session shows
mixed-mode is a real workflow, the fix is a `Trigger.notice()` addition to the seam,
argued in a decision entry, not a quiet coupling.

**The sampler runs on the main thread, once per decoded frame.** drawImage into a small
CPU-backed canvas plus a 9KB getImageData — cheap on paper, but b4aca0c earned this repo
the right to distrust "cheap on paper" for per-frame main-thread work. §4's protocol
watches for it directly: if the preview stutters or `d`'s cadence hitches while motion is
armed, the sampling moves to a worker on an OffscreenCanvas, the same shape as the encode
fix. Not built pre-emptively, because the encode worker was built on a measurement and
this would be built on a guess.

The Tier-1 trace shipped after all — added 2026-08-22, hours after this section said it
would be "added if the rig session needs them", because the rig session arrived and asked.
That is the sentence working as written, not being overruled: `src/trace.ts` records the
signal and the gate-verdict frames, never continuous video, and nothing about it touches
the capture server or the store — the file goes to the browser's Downloads folder and
nowhere else. Whether it stays past Gate C or is deleted once the thresholds sit on a
plateau is decided when they do. Tier-2 video remains unbuilt and a rig-day debugging
instrument at most. No auto-advance of boxes, no feeder control, no second store. And no
persistence of the mode — see D19's "arming is an act".

## 6. When does this need recalibrating?

Asked by the owner after the confirmation run, and worth a section because the answer is
structural: **speed does not move these constants — light does.**

Nothing in the machine encodes the feeder's 623 ms. The predictive, clock-locked design
was rejected on day one (D19); this one fires on *settle*, so the pause between cards can
stretch arbitrarily — hand-placement is just the slow limiting case — and can shrink until
one of two physical walls, both of which announce themselves:

- **Faster**: the still window (measured 312–400 ms) must keep room for the ~120 ms settle
  read, so somewhere past roughly twice today's speed, verdicts start arriving late or
  never — and past ~3 cards/s the <250 ms capture round trip becomes the bottleneck and
  the `dropped` counter climbs on screen. Neither is silent.
- **Slower**: nothing, ever — unless the advance *motion itself* (measured ~217 ms)
  stretches past `maxMoveMs` 1250, which is a jam or a dying mechanism, and it surfaces as
  `stall` on the HUD rather than firing.

What DOES need attention is anything that changes the **picture**: a new lamp, a nudged
camera, changed exposure or ISO, a different backdrop, sleeved cards.

**Since D81 those no longer need a re-trace to fix — but they do need one to notice.** The
noise floor and the presence threshold both follow the session now, so a dimmer lamp or a
re-framed camera moves the thresholds with it rather than silently invalidating them; that
is the entire point of the change, and it is what the four saved traces demonstrate. What
adaptation cannot do is tell you the baseline was taken with a card on the stand, or that the
card has drifted half out of the watch region. **The two watchdogs are free and always on
screen**: `typ` idling near 2.2 with nothing moving is healthy and creeping past 4 is a rig
fault, and `dbase` reading tens with a card under the lens against under 1.5 with the stand
empty is the separation the presence gate lives on. Either one going wrong is the cue to run
one 60-second trace and score it — `scripts/score-trace.py`, §4 — *before* it costs cards.

## 7. The cadence trigger — trigger 2, for a feeder that never rests (D130)

Added 2026-09-11. The settle trigger the rest of this file describes fires on stillness; this
one fires on a beat, and the two live behind one seam with the operator choosing per run. D130
is the decision; this section is the mechanism and what the first rig run owes.

**Why it exists, in one measurement.** The owner ran the settle trigger over a re-arranged
feeder and it fired on **5 of 29 cards** one session and **5 of ~34** the next. Every fire
reached disk and photographed a card — the plumbing was never in question. The feeder now lays
a card down every **0.867 s** (29 luma cycles, p10-p90 0.85-0.92) and never lets one sit: the
longest run of frames under `tLo` per card has a **median of one**, and 13 of 28 cards never
had four consecutive frames under `tHi`. A settle is `stillFrames` of the last `stillWindow`
(§2, D84) and a feeder that never stills produces none. `scripts/score-trace.py sweep` reaches
9 of 29 at its best `stillK`. The two traces are banked in `harness/traces/` and are T9's third
corpus.

**What it does.** `app/src/cadence.ts`:

1. Waits for the first card on the settle machine's own presence gate (§2, the
   distance-from-baseline of D81).
2. Fires on it — first quiet frame, or blind after `firstWait` of a period.
3. Fires once per period thereafter. The period is **seeded at 870 ms** (`dSeed`'s sense — the
   boot value until measured) and **measured** from the autocorrelation of the motion signal
   over the last `windowMs` once `lockAfterMs` of feeding exist; a half/third-period peak is a
   harmonic and the shorter lag is taken.
4. Locked, it folds the window by the period to find the rest — the phase of least motion — and
   fires there, on the first still frame in a window opening `restLead` early, a calm frame at
   the rest, or blind at the deadline. Every non-still fire is counted `blind` on the HUD.
5. Same presence and novelty gates as the settle machine. Two `same` verdicts in a row is a
   stopped feeder; the beat goes idle and motion wakes it. A stand empty `lostAfter` periods
   drops the beat.

Replayed causally over the two traces: **27 fires over 29 cards, 20 over ~21**, against 5 and
5 live. `app/tests/cadence.spec.ts` pins those counts and the synthetic contract.

**The operator's control.** The Rig panel's Trigger track has a third cell, `cadence`. Arming
it shows a period field: blank measures the beat (the default, and what the traces say it does
well), a number pins the period while the phase is still measured.

**What the first rig run must measure, and this section is that run's checklist.** No
photograph has been taken by this machine at the rig. The replay says a fire lands on a frame
with median `d` of 3-4 on the faster session and higher on the slower one — moving, a little —
and only a photograph says whether that is a usable image or a blur. So the first armed run:

- Save the trace and score it: `scripts/score-trace.py summary` reports the trigger and the
  fire cadence; the HUD's `blind` count is how many fires were taken off a still frame.
- Downsample the run's own JPEGs to the 38x28 watch region and match frame against photograph,
  the way D84's four lost cards were only provable that way — a trace says what the machine
  decided, only the photograph says what was on the stand.
- If the blind fires blur, the lever is the camera's exposure, not a constant here: a shorter
  shutter freezes the motion the feeder never removes. That is a rig fact, and D130 says so.

**THE DUAL (D131, the same night).** The cadence trigger takes the settle machine's own fire
whenever it comes — at least half a period after the last, re-anchoring the beat on it — and
the scheduled fire runs only when a rest window has passed with no settle. Settle accuracy
where a card rests, the beat where it never does. Its first full run, before the dual and
before §2's escape, photographed 45 of ~47 cards with 6 on a moving frame and one double;
the owner called it 80-90% and was right.

The 85/85 confirmation in this file's STATUS is **trigger 1's**. Neither the escape nor the
dual has a rig run yet; that run is what §2's numbers are waiting on.
