# Motion trigger — execution spec and rig-tuning protocol (Gate C)

Written 2026-08-22, the day it was built. D19 is the decision; this file is the mechanism,
the derivations, and the protocol for the part no computer can do — tuning at the rig.
`docs/GATES.md`'s Gate C section carries the measurements every number here leans on.

## STATUS — CONFIRMED LIVE AT 85/85, REBUILT ON MEASUREMENTS 2026-08-31, CORRECTED 2026-09-01, THE RATCHET GIVEN AN ESCAPE AND THE CARD THAT WILL NOT SETTLE A RESCUE 2026-09-11

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

**THE RESCUE IS THE EVENING OF 2026-09-11 AND §7 IS ALL OF IT.** A card that never settles is
photographed off the quietest frame it manages rather than dropped, once the episode has run
`rescueAfter` × `maxMoveMs`; six sessions go from 268 photographs and 20 stalls to 295 and 7,
and the eight earlier sessions do not move. **It is SPECIFIED and BUILT and NOT VALIDATED**:
the replay says the machine fires on more cards, and only the rig says whether those
photographs are readable. §7's last block is that run's checklist.

**AND THERE IS ONE TRIGGER AGAIN.** D130's beat-locked cadence machine and D131's dual are
deleted, on the owner's word — *"motion is better. always."* — once the settle machine reached
their cards without a beat. The cadence module under `app/src/` and its spec under
`app/tests/` are gone — named in prose because the paths no longer resolve — and so are the
third Trigger cell, the period pin and the beat's HUD spans. The sessions recorded under it
stay banked in `harness/traces/`, because a recording is evidence about a rig rather than
about a trigger.

**AND §4 NOW LOCKS THE CAMERA, WHICH IS D81'S BARGAIN COMING DUE (2026-09-12).** Every
threshold being a multiple of a session measurement is what makes a setting that DRIFTS
mid-session dangerous, and nothing in `motion.ts` can see one. Measured over all twenty banked
traces: one 1/3 EV auto-exposure step moves the watch region 8.5-22.5 luma levels and reads as a
CARD on nine of the fifteen sessions that carry a baseline, and a mid-session gain step is a
cliff rather than a gradient — one session stops firing altogether at +1.5 stops. The shutter and
the picture profile came back NULL and are recorded as findings. `scripts/score-trace.py camera`
re-derives all of it. **SPECIFIED and RECORDED, NOT BUILT and NOT VALIDATED** — no parameter
moves, and §4's last block is the checklist that is owed.

**AND SINCE THE SAME EVENING THE MACHINE SURVIVES THE STEP THE LOCK PREVENTS (2026-09-12,
D183).** A settled frame over the presence floor is asked one
more question — is it the baseline TIMES ONE NUMBER? — and a frame that is (a gain step on the
bare stand) is refused as `suppressed:uniform` and becomes the baseline, while a card, which is
a pattern and not a level, never is: zero of the 748 fired frames in the corpus, every one 3.6×
or more clear of the bound, the 85/85 run 5.3×. No threshold moved and no new constant decides
anything. **BUILT and RECORDED, NOT VALIDATED**: no banked trace holds a real exposure step or a
pixel outside the watch region, so the step is a model over real plates, and §4's "the gain step"
block is the measurement and the checklist. The lock stays the recommendation.

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
| `stillFrames` | 1 | frames under `tLo` that mean settled — counted over `stillWindow`, not consecutively (D84). **2 until D131**, and this table said so until 2026-09-11: a frame under `tLo` is still by definition, and on the bright-lamp feeder it is the only kind of rest there is |
| `stillWindow` | 3 (100 ms) | how many recent frames that 1 is counted over, and the window must be FULL. **4 until D131**, and the rest of this row is the argument for the rule rather than for the number. **A consecutive run is defeated absolutely by a two-frame alternation**, measured on a card motionless for 500 ms whose `d` read 2.71 5.40 2.63 5.54 2.83 5.14 against a `tLo` of 4.18 — five runs of one, no verdict, card lost. Swept over the three 2026-09-01 21:xx sessions, 2-of-4 recovers two of the four cards lost that way and changes no other verdict; 2-of-3 and 3-of-5 recover fewer. Fire latency (stillWindow+1)·f = 167 ms = 36% of the 458 ms worst observed cycle |
| `refractoryMs` | 250, deferring | sized to the <250 ms capture round trip, not the card cycle. A time, not a light level |
| `tNovel` | 4.0 | **deliberately still absolute.** Across all five traces and 217 verdicts the `suppressed:unchanged` count is zero, so there is no measurement to take a multiple of; and scaling it to session noise would push it DOWN on a quiet rig, making suppression more likely — the wrong direction, since a false pass is a duplicate `U` fixes and a false suppression is a silent §5.5 loss |
| `presenceK` | 3.0 | the presence floor is this × the session's still-frame difference. Against its own baseline an empty stand reads 1.10–1.38 and every card of every session reads 17.4–167.4; 3.0 puts the threshold at 5.5–9.7, four to seven times over the empty stand and three to ten times under the dimmest card |
| `presenceMin` | 16.0 | absolute floor, **set by a HAND rather than by drift** (D84, correcting D81). An undisturbed stand does not creep: it holds 2.0–2.5 for as long as it is left alone. What crosses 8.0 is the operator's hand arriving with the first card, which holds still for two frames on the way in — and at 8.0 that fired, twice, photographing the bare stand. 16.0 is 1.4× over the worst approach measured (11.15) and 2× under the quietest card in the same sessions (32.5). **It now BINDS over `presenceK` × the measurement, which is a debt** — see D84 |
| `rescueK` | 4/3 | the RESCUE BAR, as a multiple of `tLo`: how far above it a frame may sit and still settle an episode that has gone on too long. Not a new number — `sqrt(moveK / stillK)`, the geometric centre of the Schmitt band, exactly 4/3 because `moveK/stillK` is 16/9 by `moveK`'s own definition. Across the nineteen stall episodes of the six 2026-09-11 evening sessions the quietest frame of every one sits 1.02–1.25× `tLo`; 4/3 covers them all and is the largest value the corpus tolerates — at 1.40 the 2026-09-01 21:16 session gains a fire it did not have |
| `rescueAfter` | 0.60 | how long an episode must have run without a settle before `rescueK` applies, as a FRACTION of `maxMoveMs` (750 ms). **A STEP, NOT A RAMP, AND THE RAMP WAS MEASURED**: a bar rising smoothly from `tLo` to 4/3 over the stall clock is at `tLo` from the first frame, which retires `stillWindow` immediately — and `stillWindow` is what stops a dip mid-transit from firing. Scored over the whole corpus that takes the double count from 2 to between 20 and 55. **0.60 is where two plateaux meet**: swept 0.50–0.80 at 0.02, yield is flat at 295 fires and 7 stalls over the six evening sessions from 0.50 to 0.60 and falls away above it (280 and 21 by 0.80), while the eight earliest sessions are untouched from 0.60 up and gain a fire and a double at 0.58 and below |
| `maxMoveMs` | 1250 | ~2× the feeder period; a jam surfaces as `stalled` and does NOT fire. A time, like the refractory. **The clock is cleared by a COMPLETED settle** (D84): cleared by any quiet frame, as it was, the alternation above reset it every other frame and `stalled` could never expire — it did not fire once across three sessions and four cards left unphotographed. **It is now the LAST resort rather than the first**: an episode reaching it has already had the rescue bar in force for 500 ms, so a stall means a scene that never came near still |

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

   **AND SINCE 2026-09-11 IT IS A SENTENCE ON THE STAGE, NOT A NUMBER IN THE READOUT.** It sat
   between `empty` and `escape` inside a collapsed `Tuning` disclosure while the operator
   watched the stage — the one event that costs a card was the one event nothing said out
   loud, which is exactly what `noCardRun` was given a sentence for. It now renders as what it
   means, with a `Set aside` press that spends the count, the halt banner's own idiom.

   **READ `rescue` BESIDE IT.** The two are one accounting: an episode that outlasts
   `rescueAfter` × `maxMoveMs` ends in a rescued photograph or in a stall, never in nothing. A
   run reading high on `rescue` is landing its cards badly even though the photographs
   arrived — the feeder, not a number here — and a run reading high on `stall` after that is
   a scene that never came near still at all.
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

### The camera is an input to the arithmetic, and these settings are locked by measurement

**Added 2026-09-12. The rig is a Sony RX100 VII over micro-HDMI into an Elgato Cam Link 4K**
(`app/src/useCamera.ts`'s header), so the browser sees a plain UVC device and every setting
below lives in the camera's own menus — there is no Sony USB-streaming layer in this path and
nothing on the Cam Link to configure.

**WHY THIS SECTION EXISTS, AND IT IS D81'S OWN BARGAIN COMING DUE.** Since D81 every threshold
is a multiple of something the session measures: presence is the distance from the watch region
as it stood at arming, and `tLo`/`tHi` ride the session's own median still-frame difference.
That buys portability to a rig this code has never seen, and it buys with it a new exposure —
**a camera setting that moves WHILE a session runs moves the baseline those thresholds were
derived from, mid-run, and nothing reports it.** No constant in `motion.ts` can defend against
that. Only the camera configuration can, which is why it is written down here rather than left
to whatever the body was last set to.

**Every figure below was measured on the twenty traces banked in `harness/traces/` and is
re-derivable with `scripts/score-trace.py camera`.** Where a number is a derivation rather than
a measurement it says so in the row. **Two of the questions came back NULL and the null is the
answer** — sharpening and shutter speed — and they are recorded as findings rather than omitted.

#### The locked settings

| setting | lock to | the measurement behind it |
|---|---|---|
| **Exposure mode** | `Movie` → **Manual Exposure** | **the single most consequential row.** One 1/3 EV step — the smallest a Sony AE can take — moves the watch region by **8.5 to 22.5 luma levels** across the fifteen traces that carry a baseline. That is over `tLo` on **15 of 15** and over `presenceMin` on **9 of 15**: on more than half this corpus, one AE step on an empty stand reads as **a card arriving**. **That figure is a DERIVATION on the baseline under a multiplicative model, not a recorded step — no banked trace contains one — and since 2026-09-12 the machine refuses the step it describes as `suppressed:uniform` ("the gain step" below). The lock is still what keeps the floor meaning one thing for a whole box** |
| **ISO** | a **fixed** value. Never `ISO AUTO` | a gain step taken mid-session is **a cliff, not a gradient**. On the 2026-09-11 03:25 session, **+1/3 stop costs 48% of the fires after it** and **+1.5 stops stops the session firing at all** for its remaining 75 seconds. Mechanism in "the cliff" below |
| **Shutter** | **1/60 or slower**, as slow as the feeder allows — spend it on keeping ISO down | **NULL RESULT.** At the instant the trigger fires the card is moving at **184 sensor px/s** (median) and 367 at p90, so 1/60 smears it **3.1 px of a 3840-px frame** (6.1 at p90, 4.6 at the rescue bar). Blur is not the binding constraint at the fire phase; noise is. Derivation below |
| **Aperture** | **fixed**, wherever the lamp allows the ISO above | it is half the same exposure budget, and a body left in `A` re-levels when the scene changes |
| **White balance** | a **preset or Custom WB**, not `AWB` | **DERIVED, not measured** — a trace carries luma and no chroma. Rec.601 puts a `±3%` gain wobble at **1.1 luma levels** on the median plate and a full `±10%` preset jump at **3.6**, so WB sits at `tLo` at worst and never near `presenceMin`. Second-order against exposure, and free to lock |
| **Focus mode** | **Manual Focus** | the RX100 VII offers **only Continuous AF and Manual Focus when shooting movies** — there is no single-shot lock to reach for, so MF is the only way to stop a hunt. A hunt costs: **1% of focus breathing reads `d` 3.03** and 2% reads 5.83, both over `tLo` and neither near `presenceMin`, so a hunt opens or extends a motion episode rather than firing one |
| **SteadyShot** | **Off** | `Active` is a 1.19× crop plus a digital warp, and a warp is exactly the geometric change the breathing row prices. Sony's own guidance is `Off` on a tripod, and this mount is a tripod that never moves |
| **4K Output Select** | **`HDMI Only(30p)`** | the corpus is **24p** and 30p is one menu item away. Frames are the currency: **halving the rate costs 8.7% of the corpus's fires and multiplies stalls 6.3×**. See "the frame rate" below, including what is NOT known about going higher |
| **Creative Style / Picture Profile** | **fixed** — any value, not changed mid-run | **NULL RESULT.** In-camera sharpening and noise reduction act at a few sensor pixels, and a blur out to a **12-pixel radius costs `d` 0.000** on 84 real card regions. The 60×60-pixel cell average destroys it. What matters is only that the setting does not CHANGE while a session runs |
| **Auto Power OFF Temp** | **High** | not a trigger fact. A body that shuts down mid-box ends the run, and `HDMI Only` writes no card, which is the other half of the thermal budget |

#### The cliff — why `ISO AUTO` is the row that can lose a whole box

The still-frame floor is **sensor and codec noise**, and this is measurable rather than assumed.
Over **299 quiet keyframe pairs** across all twenty sessions the delta field's **lag-1 spatial
correlation is +0.009 across and +0.008 down**, against a shuffled control of +0.001 — that is
independent cell to cell, which flicker, an AE micro-adjustment and a lamp ripple are not. The
same pairs put the **global brightness move at p50 0.00, p90 1.00 and max 4.00 luma levels per
second**, so during quiet stretches nothing in the picture is moving as a whole.

So gain reaches `typ` directly, and `typ` carries `tLo`, `tHi` and the adaptive half of the
presence floor with it. **A slow drift is absorbed — that is D81 working.** A STEP is not:

| gain step at the session midpoint | corpus fires | corpus stalls | sessions that stop firing entirely |
|---|---|---|---|
| none | 915 | 12 | — |
| +1 stop | 879 | 18 | 0 of 20 |
| +2 stops | 864 | 17 | 1 of 20 |
| +3 stops | 789 | 22 | 2 of 20 |

**The corpus totals understate it, and the per-session column is the one to read.** Two sessions
do not degrade, they STOP: 03:25 loses 48% of its post-step fires at **+1/3 stop**, 82% at +1
stop, and **all** of them at +1.5; 03:20 survives +2 stops intact and fires **zero** times in its
last 65 seconds at +3.

**The mechanism is D131's ratchet, and the escape only half covers it.** Only frames already
under `tLo` enter the noise window, so a sudden rise in the floor means no frame qualifies, the
estimate cannot climb, and `tLo` freezes — measured freezing at the seeded **4.50** for the rest
of the session. D131 gave that ratchet an escape, and the escape refuses to act when its own
quantile sits at or above the presence floor, which is exactly where a large gain step puts it.
**This is not a reason to change D131.** It is the reason `ISO AUTO` is banned: the failure is
in the camera's gift and not in the machine's.

**What does NOT move, at any usable gain**: `presenceFloor` is `max(16.0, 3 × typ)`, so the
adaptive term only binds past `typ` 5.33 — **3.8 stops above the quietest session in the corpus**.
`presenceMin` stays the binding term through anything a camera can be set to, which is D84's
debt neither widened nor closed by this section.

**And the lamp is nearly no lever here, which is the useful surprise.** On one rig over twelve
sessions the floor tracks the plate level as **log(typ) = −0.125 × log(level), r = −0.868** —
halving the light raises the floor **9%**. Shot noise under a FIXED gain predicts −0.10 after the
display gamma, and the measured −0.125 is that. So a brighter lamp does not buy a quieter
trigger; a lower ISO does, at **√2 per stop**. Reach for the lamp to buy shutter and aperture
headroom, and then spend that headroom on ISO.

#### The frame rate — 24p is the floor, and it is being run AT the floor

**The stream is 24p, on 20 of 20 traces.** The modal frame gap is **41.5–42.5 ms** everywhere
and **69.7% of all 26,943 intervals** fall in 40.5–42.5 ms. That is the source rate rather than a
browser dropping a 30p feed: a dropped 30p stream is bimodal at 33.3 and 66.7 ms, and only
**0.13%** of the corpus sits near 66.7.

`stillWindow` is a **frame count**, so the rate decides how much TIME a settle needs and how
finely a card's rest is sampled. Decimating the real frame series — which is faithful, because
taking real frames further apart is what a lower rate delivers:

| rate | fires | doubles | stalls |
|---|---|---|---|
| 24 fps, as recorded | 915 | 36 | 12 |
| 12 fps | 835 | 25 | **76** |
| 8 fps | 728 | 11 | **118** |

The hand-fed sessions barely move; the feeder sessions carry all of it, which is the mechanism
D131 already named — the bright-lamp feeder rests a card **two to four frames**, and three of
those must fill `stillWindow`.

**GOING UP IS NOT MEASURED AND MUST NOT BE READ AS MEASURED.** Only the RISK half can be scored
offline: raising the rate shrinks the window's time width, which is reproduced by shortening the
window at the recorded rate. Doing that gains **+11 fires for +8 doubles** at a two-frame window
and +19 for +7 at one frame, with no session losing a fire. The BENEFIT half — finer sampling of
the rest that `stillWindow` is failing to fill — cannot be synthesised from 24 fps frames and is
step 5 of the checklist below. **The doubles counted here use this section's own definition (a
fire with no fresh `tHi` crossing since the previous fire) and are not comparable to section 7's
count.**

**Dropped frames are real and worst where the stalls are.** Per session the drop share runs
**0.00% to 4.95%**, and the 4.95% session (22:12) is one of the four carrying live stalls. A drop
inside a settle widens the window in time and can lose it.

#### The shutter derivation, and why it is a null result

`d` is a mean-abs luma change per frame, so for a small rigid displacement `u` in cells the
change per cell is `u × |spatial gradient|`. Measured on **756 real fired-card watch regions**
the region's own mean abs gradient is **20.93 luma/cell** (p10 15.31, p90 28.70). One cell is 60
sensor pixels and the frame period is 41.7 ms:

| phase | `d` | cells/frame | sensor px/s | blur at 1/60 | at 1/125 | at 1/250 |
|---|---|---|---|---|---|---|
| median fire | 2.66 | 0.127 | 184 | **3.1 px** | 1.5 px | 0.7 px |
| p90 fire | 5.32 | 0.254 | 367 | 6.1 px | 2.9 px | 1.5 px |
| the rescue bar, 4/3 × `tLo` | 4.00 | 0.191 | 276 | 4.6 px | 2.2 px | 1.1 px |
| peak transit | 53.26 | 2.544 | 3679 | 61.3 px | 29.4 px | 14.7 px |

**The last row is why the first three are so small**: the trigger fires at the phase of least
motion, and the phase of most motion is twenty times faster. Three pixels of smear on a 3840-px
frame is **1.3 px after `identify/images.py` resamples to its 1568-px long edge**. So section 7's
line — *"if the rescued frames blur, the lever is the camera's exposure"* — is answered: at the
fire phase it is not, and a rescued frame is only 1.5 px worse than an ordinary one. **Spend the
shutter on ISO.** If a rig run does show blurred rescues, the cause is a card still in transit
and the reading to check is `rescue` against `fires`, not the shutter.

#### D84's three quantities, re-derived for this camera

D84 names three quantities that re-derive `presenceMin` on a new rig — the idle stand, the worst
approach, the quietest card. **The pipeline that produced the table below reproduces D84's own
published figures exactly** (its two bare-stand fires at `dBase` 9.07 and 9.10, and its quietest
card at 32.53), which is what licenses the rest of it.

| quantity | 2026-09-01 rig | 2026-09-11 rig | `presenceMin` = 16.0 |
|---|---|---|---|
| **1. the idle stand** | 2.01–2.18 | **1.41–1.55** (p99 6.45, max 19.96 over 5,436 frames) | 10× clear at the median |
| **2. the worst approach** | 11.15 (D84's) | **NOT MEASURABLE FROM THESE TRACES** — bounded at 12–23 | **straddled** |
| **3. the quietest card** | 32.53 | **25.81** (median 107.67 over 578 fires) | 1.6× clear at worst |

**Quantity 2 is the honest gap and it is the reason step 3 of the protocol still needs a person.**
On the 2026-09-01 rig the hand took about two seconds to arrive and the ramp is legible frame by
frame. On the 2026-09-11 rig **the whole hand-to-card ramp is four to six frames, about 200 ms** —
under the trace's 1 Hz keyframe grid — so nothing in the file separates the hand from the card,
and the contact sheet of every session's approach shows no frame that is unambiguously a bare
plate with a hand over it. The per-frame `dBase` bounds it at **12 to 23**, which **straddles 16.0
rather than sitting under it**. What keeps this from being D84's defect returning is that a
200 ms ramp cannot settle: the settle rule is doing the work on this rig, not presence. **That is
a fact about this feeder's speed and not a margin, so it is measured again at the rig, by eye,
whenever the feed changes.**

The two rigs are not the same picture and the contact sheet says so plainly: 2026-09-01 is a
dark textured stand with a specular hot-spot (plate level 74–77), 2026-09-11 is a **bright white
plate with a dark card landing on it** (plate level 128–218). The second arrangement is much the
better one — cards read `dBase` 26–128 against 9–45 — **and it is also what makes the exposure
row above bite hardest**, because an exposure step costs luma levels in proportion to the plate's
own level. With exposure locked that trade does not exist, and the bright plate is pure gain.

**Clipping has headroom on cards and almost none on the plate.** Card frames put **0.00–0.22%**
of cells at 250 or above on the twelve newest sessions (against 1.89% and 0.97%, worst frame
16.4%, on the 2026-08-23 pair). The plate itself reaches a bright quantile of 255 on **0.1–2.9%**
of frames in five sessions, so an exposure step DOWN is fully visible and a step UP is partly
absorbed — one more reason not to leave the decision to the camera.

**One thing the corpus cannot settle, and it is named rather than glossed.** Every drift figure
here is measured on stretches where nothing was moving, and **auto exposure only steps when the
scene changes** — which on this rig is exactly when a card is in flight and `d` is dominated by
the card. So these traces bound the drift of whatever the body was set to; they cannot prove the
body was in manual. **Step 2 of the checklist is what decides that**, and it takes thirty seconds.

#### The gain step — refused as the stand rescaled, and what the recordings could and could not prove (2026-09-12)

**Added the evening the owner asked whether the lock was essential or "just coding bad".** The
lock is a correct fix and not the only one. This block is the version that does not need their
hand, built over recordings alone; D183 is the decision.

**What the corpus holds, and does not.** Every trace stores the watch region and nothing outside
it — 1,064 cells at 38×28, keyframes and verdict frames alike — so a reference region outside the
region, the shape first proposed, cannot be derived from it. A scan of all 20 sessions' consecutive
keyframe pairs for a global gain change (median ratio ≥ 5% off unity with the pattern preserved)
found none; the three candidates are quantisation on a 16-level plate. **The 8.5–22.5 figure in
the exposure row is arithmetic on the baseline, and it is now labelled as such.**

**The surround was measured from the owner's photographs instead**, read-only, 2,535 stored 4K
frames over five boxes, the stored rotation undone and each downsampled to the machine's 64×36
grid. The mapping is proven: the 22:12 session's 51 fires match box 1's photographs 93–143 in
order (50 of 50 consecutive, median correlation 0.86) under one rotation and 0.22 under the
other. Across a card swap the reference rig's corners hold to 0.6–1.3 luma (543 swaps); the
feeder rig's left third moves 27–47 every cycle (the tray) and its right side holds at 1.3–3.3.
A median per-cell ratio over the surround cancels an injected 1/3 EV step to 0.00 on every
box. **Against the ARM-TIME surround it does not hold**: fewer than half the surround's cells
agree with the session's first frame on 87–99% of frames, 95% of them within 3.5 minutes on
box 5 — so a uniformity guard would decline nearly every verdict, and without one the factor is
wrong by up to 2.5× (worst pairs: a hand, the tray) and invents a 170-luma change. **Refused.**

**Normalizing the watch region by its own median ratio, always — refused in one run over the
corpus**: 77 of 661 fired cards fall under the floor and the 85/85 run's quietest card goes from
58.8 to 11.0. A bright card on a dark plate divided by its own ratio is scaled to plate
amplitude, and with amplitude gone the hand (8.3–9.1) and the weakest cards overlap.

**What survives is a test.** `k` = the median per-cell ratio of the frame to the baseline over
cells both hold between a toe (8) and a shoulder (247); the residual = mean |frame − k × baseline|
in the units of the brighter of the two frames; UNIFORM when the residual is under `presenceK` ×
the session's still-frame difference — the multiple the presence floor already rides. The units
were measured three ways: the baseline's put sixteen of the 85/85 run's cards at 1.4× the bound;
the frame's put the 03:25 session's closest real card at 1.8×; the brighter frame's keeps every
real card on every session at **3.6× or more** (2026-09-01 03:06 at 22.5 s is the closest).

| reading, all twenty sessions | value |
|---|---|
| fired frames over the floor | 748 |
| refused as uniform | **0** |
| closest real card to the bound | **3.65×** (85/85 run: 5.3×) |
| the closest frame of any kind | 03:25 at 74.0 s, **1.02×** — the plate's dark disc displaced, NOT a card (contact sheet); its twin at 73.0 s reads 2.29× |
| injected 1/3, 1/2, 1 EV on every baseline | uniform, or under the floor — never a card |
| injected 1.5 EV | declined on six bright plates (fewer than a quarter of the region unclipped), the floor alone deciding as before |
| the hand D84 photographed the stand with | 7.61 and 8.68 against bounds 7.41 and 8.09 — not uniform; refused by the floor as before |
| the reference rig's genuine empty stand | k = 1, residual = raw, 1.70–1.78 |
| scaled novelty between consecutive fires | ≥ 5.28 against `tNovel` 4.0 (raw minimum 7.0) |

**The novelty gate asks the same question of the last fired frame**, so a step over a card
already photographed is `suppressed:unchanged` rather than a second photograph. **`d` is not
touched**: a step is one spurious episode that resolves as uniform; a slow ramp under `tLo` per
frame — 1/3 EV over half a second at level 150 is about 1.3 a frame — enters the noise window
for its duration and is the limit §5 names.

**The two 03:25 frames are a finding about T9 as much as about this test.** They cleared the
floor at 25.8 and 26.6 from the baseline, so the bright-lamp block's "the fired frame is a card
(≥ 17 from baseline)" passed on them; the contact sheet says they photographed the bright plate
with its disc moved. Distance is not content. T9 pins them by time now.

**The second candidate, priced.** `geometry.detect_card` is exposure-invariant by construction:
timed on an eval image, 42 ms at full size and 18–21 ms downsampled, which is 45–100% of one core
at 24 fps — and it runs in Python on the server, while the trigger runs in the browser. Not the
cost but the process boundary rules it out as a per-frame gate; it stays the per-capture crop.

**Mutation-tested, fifteen arms, one survivor.** Over the scorer, read by T9: frame units only
(03:25 falls to 1.8×), baseline units (the 85/85 run to 1.4×), no shoulder on the current frame
(26 injected steps become cards), never decline, `k` as a mean rather than a median (the disc
frames move), the toe at 40 (cards refused), and the scorer's toe drifting from the machine's
(`motion params` row) — all red. **The survivor is the step model without clipping**: the
shoulder excludes any cell over 247 whether the model clipped it or not, so the clip in
`_step` is invisible to every verdict; what it models is the camera, and nothing here can see
the camera. Over the machine, read by `motion.spec.ts` in a browser: the branch removed, the
bound replaced by the floor, novelty unscaled, the baseline not adopted, frame units only, no
shoulder on the current frame, never decline — all red, the last two only after two clipping
cases were added because the first pass showed them surviving. Ten of the file's older cases
went red the moment the machine landed, because every card in them was a flat level at a new
luma — the stand times one number — and the fixture now carries texture on every frame.

**NOT VALIDATED, and this is the whole of what the recordings cannot do.** The step here is
`2 ** (EV / 2.2)` applied to a real plate; its noise is the plate's own. The first trace saved
with the body in `P` or with `ISO AUTO`, scored with `scripts/score-trace.py gain`, and the HUD's
`uniform` count over one box are what validate it — one sitting, after the checklist below.

#### The rig checklist — one sitting, before the next feeder run

Cost: about fifteen minutes, one box of expendable commons, and it ends with a saved trace.
Steps 1 to 4 are the camera; 5 to 7 are what only the rig can answer.

1. **Set the body, movie side, in this order.** `MENU → Movie2 → Exposure Mode → Manual
   Exposure`. Then on the body: **shutter 1/60**, **aperture** wherever the lamp allows,
   **ISO a fixed number** — raise the lamp until a fixed ISO gives a correct exposure rather
   than raising ISO to meet the lamp. Then `MENU → Camera Settings1 → Focus Mode → Manual
   Focus`, `MENU → Camera Settings2 → SteadyShot → Off`, and white balance to a **preset or
   Custom WB**. Leave Creative Style and Picture Profile wherever they are; only stop changing
   them.
2. **Prove the exposure is locked, which the traces cannot.** With the stand empty, sweep your
   hand right through the frame and out again, twice. Watch `typ` on the HUD. **If `typ` and the
   plate's own brightness come back to where they were within a frame or two, exposure is
   locked**; if the picture visibly re-levels after your hand leaves, the body is still in an
   auto mode and step 1 did not take.
3. **Set 30p and confirm it arrived.** `MENU → Setup → 4K Output Select → HDMI Only(30p)` — the
   camera must be in movie mode with the Cam Link connected for the item to be selectable. Then
   arm, take a ten-second trace of nothing, and run `scripts/score-trace.py camera <trace>`: the
   `delivery` line must read **30 fps and a modal gap near 33.4 ms**. If it still reads 24, the
   body did not take the setting and everything after this step is being measured at the old rate.
4. **Read the plate.** The same `camera` output prints the plate level and what one exposure step
   would have cost on it. That row is now hypothetical — it is the size of the mistake step 1
   prevents — and it is the number to quote if anyone proposes putting the body back in `P`.
5. **The frame-rate question the corpus could not answer.** Feed one hopper at 30p with no box
   selected, then one at 24p, and compare `fires` and `stall` between them. The prediction is
   more fires and fewer stalls at 30p, because a card rests two to four frames at 24 and three
   must fill `stillWindow`. **The counter-risk is doubles**, which the offline proxy put at
   +8 for +11 fires, so **count the doubles by hand on this run** — it is the only place they
   can be counted honestly.
6. **The approach, by eye, because quantity 2 above has no other instrument.** Stand empty and
   armed, reach in as if placing a card and stop short — do not put one down. Watch `dbase`
   against `floor`. It must not reach 16 while your hand alone is in frame. **If it does, that is
   the number to raise**, and it is the one quantity in this file no session statistic measures.
7. **Then a 50-card run**, box selected, and save the trace before disarming. Reconcile `fires`
   against records, `rescue` against the roughly one-in-nine of section 7, and `stall` against
   cards you had to re-feed. Run `camera` on it last: `delivery` says whether 30p held under
   load, and the drop share is the number to watch — the corpus's worst session dropped **4.95%**
   of its frames and was one of the four carrying live stalls.

**What this section is: SPECIFIED and RECORDED. Nothing in it is BUILT — no parameter in
`motion.ts` moves — and nothing in it is VALIDATED at the rig.** Every figure is arithmetic over
recordings, which is exactly as far as a trace can go, and the checklist above is the part that
is owed.

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

**An exposure RAMP is not a step, and the noise tracker can see it.** The uniformity test
(§4) answers a step: one frame over `tHi`, a settle, a verdict. A body that re-levels smoothly
over half a second moves `d` by about 1.3 a frame at level 150 — under `tLo` — so those frames
are called still, enter the noise window, and lift `typ` for eight seconds; no episode opens and
no verdict is taken until the next card, which is judged correctly against a baseline the ramp
has moved. The cost is a slightly raised `tLo` for one window, measured nowhere because no trace
holds a ramp; the remedy is the lock, which is why it stays the recommendation.

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

## 7. The rescue — the card that will not settle (2026-09-11)

Added the evening D130's cadence trigger was deleted, and it is what replaced it. The owner's
complaint is the whole subject: *"it's really bad when the cards are coming a little slower or
aren't landing perfectly, the engine is then bad at picking those up"*. Six saved sessions say
what that looked like — 268 photographs against 20 stalls, about 93% — and what each miss was.

**A stall is a card, and until this the answer was to drop it.** The trigger fires on a settle;
a card that never settles inside `maxMoveMs` was reported and left unphotographed. That refusal
is defensible on its own terms — the point of a settle trigger is a still card, and firing on a
moving one buys a blurred photograph — so the real question was never "can it fire anyway" but
**which of a soft photograph and no photograph is worth more**. On a feeder the answer is the
photograph: the card is about to be replaced, nothing comes back for it, and `U` undoes a bad
one in one press while a lost card is found weeks later in a box that does not match its run.

**What the nineteen stall episodes actually are.** Scored with `scripts/score-trace.py` over
the six sessions, every one of them has a quietest frame between **1.02× and 1.25× `tLo`** —
and **nine of the first fourteen are UNDER `tLo`**, frames the machine had already judged
still. Those nine were refused by `stillWindow` alone: the card landed one or two frames after
its transit ended, the window needs three to fill, and the next card's motion threw it away
first. The rest came to rest just above the line.

**So the rescue is a bar and an age, and neither is a new number.** `rescueK` (4/3) is
`sqrt(moveK / stillK)` — the geometric centre of the Schmitt band the session already measures.
`rescueAfter` (0.60) is a fraction of `maxMoveMs`, the machine's own statement of how long is
too long. Past that age a frame under `rescueK` × `tLo` settles the episode, window requirement
dropped with it, and the fire is a distinct verdict: `fire:rescued`, counted as `rescue` on the
HUD beside `stall`.

**Three things are deliberately NOT relaxed**, and the third is why the rescue is safe:

- **Presence.** A rescue cannot photograph the bare stand — `presenceMin` decides it exactly as
  it decides an ordinary fire, which is D84's two junk rows staying fixed.
- **Novelty and the refractory.** A rescue cannot photograph the same card twice.
- **The age.** `stillWindow` is what stops a dip DURING a transit from firing, and the age is
  the only word the machine has for "the transit cannot still be happening". Retiring the window
  from the first frame of an episode — the obvious ramp — takes the corpus's double count from
  **2 to between 20 and 55**. That measurement is why this is a step and not a ramp.

**The corpus, before and after** (`scripts/score-trace.py summary`, pinned in T9):

| session | live | with the rescue | of those rescued | stalls |
|---|---|---|---|---|
| 21:52 | 55 | 59 | 6 | 2 → 0 |
| 21:54 | 53 | 60 | 7 | 5 → 3 |
| 22:10 | 40 | 44 | 6 | 3 → 0 |
| 22:12 | 51 | 56 | 6 | 4 → 1 |
| 22:25 | 17 | 23 | 7 | 5 → 2 |
| 22:29 | 52 | 53 | 2 | 1 → 1 |
| **six** | **268** | **295** | **34** | **20 → 7** |

**And the eight earliest sessions do not move**, which is the half with teeth: 86, 86, 20, 15,
24, 49, 16, 12 before and after. A stillness rule that buys cards on one rig by spending them
on another is this subsystem's entire history — D81's brightness floor rescued one session of
three and broke the other two — so the sweep was constrained by those eight rather than scored
against the new six. `rescueAfter` below 0.60 gains the 21:14 session a fire 290 ms before its
own next one, and that is the value the corpus refused.

**What still stalls is the finding, not the residue.** The seven survivors are episodes whose
quietest frame never came near the bar. The clearest is 22:25 at 27.9 s: 1.25 s inside the
Schmitt band with **not one crossing of `tHi`** — a card sliding the entire time, quietest
frame at 3.4× `tLo`. Extending a deadline for that one would photograph a moving card; the
machine is right to refuse it and say so.

### Glare, and why there is no `stalled:flare`

The owner diagnosed the remaining misses as specular glare — a mirror flash off a tilted card —
and dimmed the lamp between runs (scene p90 111 → 89) while the flares still hit 176 and 198.
The obvious next step is a verdict that names it. **Three candidate discriminators were measured
over the whole corpus and every one failed:**

| discriminator | what the traces say |
|---|---|
| saturation | the share of watch-region cells at ≥250 is ~0 on every stall frame, worst 6 of 1,064 — **and that is not evidence of no glare**: each cell averages ~3,600 sensor pixels, so a fully clipped streak reaches the trace as a cell reading 214. The instrument destroys the evidence before the file is written |
| spike shape | a flash should be brief, so peak ÷ own-median bright quantile ought to separate. It goes the **wrong way**: stall episodes read 1.19 median against 1.36 for episodes ending in a fire |
| absolute level | "brighter than any card this session fired on" flags 6 of the 11 surviving stalls — and **14% to 55% of the ordinary episodes too** |

So `scripts/score-trace.py stalls` prints the **reading** — each surviving episode's peak bright
quantile against this session's own fired cards — and names nothing. That is the comparison the
owner made by eye off a contact sheet, offered offline where a human is already looking. A
verdict string asserting `flare` would be `cardLumaFloor`'s mistake in a third costume: a
brightness compared against a line that does not separate the populations.

**The fix for glare is optical and stays optical** — the lamp off-axis, a diffuser, a polariser.
No code recovers detail that was gone before the detector saw it, and the session that tries to
threshold its way out of this one should read D81 first.

### What the first rig run under this rule must measure

**NOTHING HERE IS VALIDATED AT THE RIG.** The replay proves the machine fires on more cards;
that is arithmetic over recordings and it is exactly as far as a trace can go.

**Five of the new fires were rendered, because five is how many the trace can show.** A trace
stores pixels for verdict frames and once-a-second keyframes only, so of the 28 rescues that
are a new card rather than an existing fire taken a frame sooner, five land within one frame of
a stored one. Drawn at 38x28 beside the nearest ordinary fires of the same session: each holds a
card-shaped object with structure, none is obviously worse than its neighbours, and the 03:20
rescue at 101.29 s is visibly cleaner than the ordinary fire 0.13 s after it — which is a
blown-out flare, and a reminder that glare lands on ordinary fires too. One (21:54 at 19.36 s)
is dimmer than its neighbour, consistent with a card not yet fully down. **A 38x28 grid can say
a card is there and cannot say it is in focus**, so this is a sanity check and the run below is
still the measurement. **Whether the
extra photographs are readable is a fact about the JPEGs**, and this repo has been burned there
twice — two earlier motion fixes were derived from frames nobody rendered, which is why
`score-trace.py contact` exists. So the first armed run:

- **Read `rescue` against `fires` on the HUD.** On the saved corpus 34 of 295 photographs are
  rescues, about one in nine. A run far above that is landing cards badly.
- **Look at the rescued photographs, not the trace.** They are the ones taken on a frame between
  `tLo` and 4/3 × `tLo`. Downsample the run's own JPEGs to the 38×28 watch region and match
  frame against photograph, the way D84's four lost cards were only ever provable — a trace says
  what the machine decided, only the photograph says what was on the stand.
- **If the rescued frames blur, the lever is the camera's exposure**, not `rescueK`: a shorter
  shutter freezes motion the feeder never removes. That is a rig fact, and the same one D130 got
  right about its own blind fires.
- **Save the trace and score it**: `summary` reports the rescued count beside the replayed one,
  and `stalls` prints what the rescue could not save.
