# Motion trigger — mechanism, derivations and rig-tuning protocol (Gate C)

D19 (auto-capture fires live) is the decision. This file is the mechanism, the derivations, and
the protocol for the part no computer can do: checking the rig. The gates corpus's `GateC` record
carries the measurements that the numbers here lean on.

## STATUS

The trigger exists. `app/src/motion.ts` sits behind `app/src/trigger.ts`'s seam. A mode toggle on
the capture screen arms it. The screen shows a live HUD, a swallowed-fire counter and a
`Re-baseline` control. Two specs cover it, and both run in `make design-check`.

- `app/tests/motion.spec.ts` proves the machine's arithmetic against an exact answer key.
- `app/tests/motion-live.spec.ts` drives the real screen in a real browser with a synthetic camera
  stream, from arming through firing to the dropped-fire count.

`harness/tests/t9_traces.py` (T9) replays the ten real sessions in `harness/traces/` through the
machine.

**The 85/85 feeder run stands.** 72.5 s at a 620 ms period, 85 of 85 cycles fired, with zero doubles
and zero misses, into a real box through the full path. One designed `no-card` suppression happened
at arm time. That clears the 50-card bar for the trigger half of Gate C. The gate still owes the
pipeline half (identify, join, emit and reconcile on a feeder-paced box) and foil under this lamp.
The rig's measured cadence is 0.6095 s a card (`app/src/storeHistory.ts`'s `RIG_CEILING_PER_HOUR`).

**Not validated at the rig:**

- **The rescue (§7).** The replay says the machine fires on more cards. Only the rig says whether
  those photographs are readable. §7's last block is the checklist.
- **The uniformity refusal (§4, "the gain step").** No banked trace holds a real exposure step. The
  step is a model over real plates.
- **The camera lock (§4).** It is specified and recorded, and no parameter in `motion.ts` moves.

There is one trigger. D144's beat-locked cadence machine and D131's dual were deleted on the
owner's word, "motion is better. always", once the settle machine reached their cards without a
beat. The recorded sessions stay in `harness/traces/`, because a recording is evidence about a rig
and not about a trigger.

**D81 (every threshold is a multiple of a measurement) changed the shape of §4.** The parameters are
no longer what a rig session tunes. A rig session now reads whether the machine's own measurements
are sane and whether the baseline was taken on an empty stand. Read §4 before you treat any number
here as something to edit. Read D84's ruling 3 before you treat `presenceMin` as re-derivable from
anything this machine measures for itself.

## 1. The two halves

`MotionMachine` is pure: `step(nowMs, cells)` in, event out. It has no DOM, no clock of its own and
no camera. That makes it testable to an answer key. It is the same split `geometry/` makes between
detection and cropping.

The DOM wrapper is thin and untestable off a browser. It downsamples the `<video>` to a 64x36 luma
grid on one reused canvas, slices the watch region, and feeds the machine once per decoded frame. It
uses `requestVideoFrameCallback` where it exists. Elsewhere it uses display-rate
`requestAnimationFrame` behind a `currentTime` guard. Without the guard, rAF at 60 Hz over a 30 fps
stream diffs alternate frames against themselves. The machine then fires at half the configured
settle time, with no symptom.

## 2. The machine, and where each number came from

Phases: watching, moving, settling, then a verdict, then watching again, with a deferring refractory.

| parameter | value | what it is a multiple of, and where the number came from |
|---|---|---|
| grid | 64x36 | each cell averages about 3,600 sensor pixels, so noise attenuates about 60x |
| watch region | center, inset 20% x and 10% y | 15 of 53 Gate B frames carry a second card in the feed path. Card placement repeats to about 30 px |
| `stillK` | 2.0 | `tLo` = this x the session's median still-frame difference. A sweep over all traces (q 0.5 to 0.95, k 1.4 to 2.5) gives a plateau at 2.0 to 2.5 where every trace meets or beats the live constants. 2.0 is the middle of the plateau and not the edge of a peak |
| `moveK` | 3.556 | `tHi` = this x the same measurement. It is 2.0 x 16/9, which holds `tHi`/`tLo` at 1.78, the ratio of the hand-tuned 4.5 and 8.0 pair. The band is a ratio and not a difference. A fixed 3.5-wide band is wide on a quiet rig and absent on a noisy one |
| `dSeed` | 2.25 | what the still-frame difference is taken to be until 25 still frames have been seen. It seeds the thresholds at exactly 4.50 and 8.00, Gate C's own pair, so the machine boots on the confirmed run's numbers |
| `dFloor` | 1.0 | a floor under the measurement, so a rock-steady mount cannot drive `tLo` toward zero |
| `noiseWindowMs` | 8000 | about 200 frames and a dozen feeder cycles. Only frames already judged still go in (below) |
| `stillFrames` | 1 | frames under `tLo` that mean settled, counted over `stillWindow` and not consecutively (D84, D131). A frame under `tLo` is still by definition, and on the bright-lamp feeder it is the only kind of rest there is |
| `stillWindow` | 3 | how many recent frames `stillFrames` is counted over. The window must be full. A consecutive run is defeated absolutely by a two-frame alternation: a card motionless for 500 ms read `d` 2.71 5.40 2.63 5.54 against a `tLo` of 4.18, which is five runs of one and no verdict |
| `refractoryMs` | 250, deferring | sized to the capture round trip and not the card cycle. A time and not a light level |
| `tNovel` | 4.0 | deliberately still absolute. The `suppressed:unchanged` count is zero across the corpus, so there is no measurement to take a multiple of. Scaling it to session noise would push it down on a quiet rig, which makes suppression more likely. That is the wrong direction. A false pass is a duplicate that `U` fixes. A false suppression is a silent §5.5 loss |
| `presenceK` | 3.0 | the presence floor is this x the session's still-frame difference. An empty stand reads 1.10 to 1.38 against its own baseline, and every card of every session reads 17.4 to 167.4 |
| `presenceMin` | 16.0 | an absolute floor, set by a hand and not by drift (D84). An undisturbed stand holds 2.0 to 2.5. What crosses 8.0 is the operator's hand arriving with the first card. 16.0 is 1.4x over the worst approach measured (11.15) and 2x under the quietest card in the same sessions (32.5). It binds over `presenceK` x the measurement, which is a debt (D84) |
| `rescueK` | 4/3 | the rescue bar, as a multiple of `tLo`. It is `sqrt(moveK / stillK)`, the geometric center of the Schmitt band, and not a new number. The quietest frame of every stall episode in the six evening sessions sat 1.02 to 1.25x `tLo`. 4/3 covers them all and is the largest value the corpus tolerates |
| `rescueAfter` | 0.60 | how long an episode must run without a settle before `rescueK` applies, as a fraction of `maxMoveMs`. It is a step and not a ramp, and the ramp was measured (§7). 0.60 is where two plateaux meet |
| `maxMoveMs` | 1250 | about 2x the feeder period. A jam surfaces as `stalled` and does not fire. The clock is cleared by a completed settle (D84). It is the last resort: an episode reaching it has had the rescue bar in force for 500 ms |
| `stillFractionMin` | 0.30 | the ratchet's escape trigger (D131, §4) |
| `restQuantile` | 0.25 | the quantile the escape takes the still level from (D131, §4) |
| `uniformMinShare`, `uniformToe`, `uniformShoulder` | 0.25, 8, 247 | the uniformity test's comparable-cell rules (D184, §4) |

### The measurement only admits frames it already called still

A frame enters the noise window only if `d < tLo`. A hand resting half in frame, a jammed feeder and
a card creeping all sit above `tLo`. They never reach the estimate and cannot teach the machine that
hovering is what quiet looks like. The estimate moves only on frames already judged still, and the
multiplier lets it climb. An adaptive floor that learned during slow motion would go blind. This one
cannot.

The one thing this cannot recover from is a session whose noise is entirely above the seeded 4.5. No
frame is ever still, nothing enters the window, and nothing adapts. That failure is loud. Not one
capture is taken and the HUD sits in `moving`. A median over a window that admitted motion would be
quieter and wronger.

### The presence gate is a distance

Presence is the distance of the watch region from its own baseline, taken when the trigger was armed.
No constant separates the populations that a brightness gate has to tell apart:

| scene | rig and session | bright quantile |
|---|---|---|
| empty stand | reference rig | 57 |
| card | under-lit rig | 61 to 134 |
| card | second rig | 77 to 171 |
| card | reference rig | 196 to 244 |

A brightness constant refused 38 real cards as an empty stand, silently, on two rigs. One earlier
"fix" derived its "empty stand" brightnesses from twenty frames that were photographs of real cards.
A refusal had been read as evidence of what was on the stand, and nobody rendered the frames.
`scripts/score-trace.py contact` draws every verdict's frame as a labeled sheet, because only
looking settles what a frame contains.

A card already at the lens when the trigger arms becomes the baseline and is refused. That is forced.
The loss is one photograph at the top of a run, and the screen announces it. `noCardRun` counts
consecutive refusals, and three in a row render as the sentence it means, with the `Re-baseline`
control under it.

There are three gates on a fire, with one verdict per settle episode:

- **Stillness** synchronizes the fire, so it fires once per card and not mid-swap.
- **Novelty** against the last-fired frame prevents double captures.
- **Presence** is the distance from the session's baseline.

All three are statements about change and none is a statement about brightness. That is also why
`geometry/detect.py`'s tone segmentation is not wanted here.

**The buffer-copy rule is load-bearing.** The sampler reuses its arrays, so the machine copies
everything it keeps. A held reference makes prev and current the same array. Then `d` reads zero and
the trigger never fires, with no error anywhere. The machine spec pins this with a deliberately
mutated shared buffer.

## 3. The screen's half of the contract

The seam's split (`trigger.ts`): settling, novelty, card presence and the refractory belong to the
trigger. In-flight, halt, no-box and camera-not-ready belong to the screen. Motion mode adds one
obligation that manual mode never needed. A declined fire is counted by reason, in state. The HUD
shows the aggregate as `dropped`. The one reason that carries its own instruction is a halt with the
feeder possibly still delivering. The halt banner renders it as the sentence it means: "that many
cards may have passed the lens unrecorded — set them aside and re-feed". Counters are per accounting
period. Arming resets all of them, and a resume clears the halted count the banner just spent.

The operator can tell it is on in three ways, all on the capture screen. The pressed chip shows `key` or `motion`. The machine string under the capture button changes from `manual:C` to `motion`. The HUD is the third.
The HUD exists only while the machine is armed. It shows `phase`, `d`, `tlo`, `thi`, `typ`, `dbase`,
`floor`, `fires`, `same`, `empty`, `stall`, `rescue`, `escape`, `uniform` and `dropped`. Arming is
session-only (D19), so every reload starts manual.

**Every number on that row is one the machine decides on.** The row once carried `luma` while the
presence gate read a different statistic, which is how a rig gets debugged against the wrong number.
`d` is the live difference. `typ` is what the session measured. `tlo` and `thi` are the multiples of
it. `dbase` and `floor` are the presence decision's two halves. The bright quantile survives in the
trace as evidence about lighting and gates nothing.

**A run of refusals is a sentence and not a counter.** `empty` is a total, and a total does not say
"this is happening right now". Three consecutive refusals render as what they mean, with the likely
cause (a baseline taken with something on the stand) and the remedy under it. `Re-baseline` is a
button and not a letter. The operator presses it after clearing the stand, with a hand already off the keyboard. The letter it would want (`b`) is the box field's.

The `C` key is disarmed in motion mode, so one trigger sits behind the seam at a time. The capture
button stays live in both modes. A manual fire past a hesitant machine is an override and not a mode.
`Space` pauses and resumes the machine. Undo never automates.

**The replay guard outranks the machine.** While a halted photograph's id is held (`captureIdRef`),
the next capture goes out under that id. On a replay, the server ignores the image. A machine fire in that window would send the next card's frame under the halted card's id. The card would then pass the lens recorded in name only. Machine fires are swallowed as `held` until the id clears. The halt banner
says to capture the held card with the button. The machine resumes once the human has resolved the
ambiguity.

## 4. Rig-tuning protocol — the part that needs a person

This is not a parameter-tuning protocol. Tuning was portable to exactly one rig. One session swept one
trace and landed on `tLo` 4.5 and `tHi` 8.0. The presence constant beside them then refused 38 real
cards on two other rigs. The machine takes its own measurements now. A person still has to check that
the measurements are sane and that the baseline is honest. No arithmetic inside the frame can decide
either.

The cost is about ten minutes at the rig, with one box of expendable commons, before the 50-card
confirmation run.

1. **Arm on an empty stand.** This step cannot be got wrong. The watch region as it stands when you arm
   is what the whole session will call "nothing". Expect exactly one `empty` verdict at arm and silence
   after. A card on the stand at arm becomes the baseline. The machine then refuses it and every card
   that looks like it. It says so out loud after three refusals in a row, with the `Re-baseline`
   control under the sentence. Clear the stand and press it.
2. **Read the machine's own measurement, with nothing moving.** `typ` is this session's median
   still-frame difference. `tlo` and `thi` are 2.0x and 3.556x it. On the reference rig `typ` idles near
   2.2 and the pair lands near 4.5 and 8.0. Sessions traced since read 1.75 to 3.22. A `typ` above about
   4 is a rig problem and not a parameter problem: mains flicker, an unstable lamp or a mount that
   moves. Fix the rig, and the thresholds follow it on their own.
3. **Read the gap and not the absolute.** Place one card by hand and watch `dbase` against `floor`. A
   card should read tens. The empty stand reads under 1.5. A card that reads close to `floor` is a
   framing problem, because the card is barely inside the watch region. It is not a number to lower.
   Also watch `dbase` while your hand is still moving in. The approach decides `presenceMin`, and the
   stand at rest does not. Reach in as you would to place a card and read the peak before the card
   lands. If your approach reads near 16, that is the number to raise. It is the one quantity here that
   the machine cannot take for itself.
4. **Swap signal.** Hand-swap cards at feeder-ish pace. Every swap should spike `d` past `thi`. Every
   settle should fire exactly once. `same` should stay at zero unless you re-present the same card, and
   then it counts exactly once per re-present.
5. **The feeder, empty run.** Run the feeder with no box selected. Fires then land in `dropped`, which
   is the point: count feeder cycles against `fires`. Agreement within one or two over a hopper is the
   pass. Watch `stall` and `rescue` together. An episode that outlasts `rescueAfter` x `maxMoveMs` ends
   in a rescued photograph or in a stall, never in nothing. A run reading high on `rescue` is landing
   its cards badly even though the photographs arrived. The cause is the feeder and not a number here.
   A run reading high on `stall` after that is a scene that never came near still. A stall is a card
   the machine did not photograph and is telling you about. Re-present it. It is not a number to raise.
   `stall` renders as a sentence on the stage, with a `Set aside` press that spends the count. It is not only a number in the collapsed `Tuning` readout.
6. **Save the trace before disarming.** The `Save trace` button under the HUD downloads the whole armed
   session. The file holds every frame's `(t, d, dBase, luma)`, the exact watch-region pixels each fire,
   suppression and stall was decided on, and once-a-second keyframes. It is self-describing, because
   the parameters travel with the evidence. It lands in Downloads as `motion-trace-<timestamp>.json`.
   A trace survives disarming and resets only when motion is armed again, so save late and not early.
7. **The 50-card run** (Gate C's own bar), with a box selected. Reconcile `fires` against records,
   `dropped` against the halt story, and the cadence against the trace. Then run a full box.

### Scoring a trace offline — `scripts/score-trace.py`

```
scripts/score-trace.py summary  <trace.json> [more.json ...]
scripts/score-trace.py presence <trace.json>
scripts/score-trace.py sweep    <trace.json> [more.json ...]
scripts/score-trace.py stalls   <trace.json> [more.json ...]
scripts/score-trace.py camera   <trace.json> [more.json ...]
scripts/score-trace.py gain     <trace.json> [more.json ...]
scripts/score-trace.py contact  <trace.json> <out.png>
```

- `summary` says what the machine did live and what today's form would do.
- `presence` re-runs the card-present gate over each verdict's own pixels.
- `sweep` scores the stillness thresholds across a grid over every trace at once. One trace cannot
  choose a parameter, and choosing from a single run is the mistake §2's table is a receipt for.
- `stalls` prints every episode the rescue could not save, with its brightness against this
  session's own fired cards. It is a reading and not a verdict (§7).
- `camera` reports what the camera did: it reports how frames were paced and how bright the plate is, so it shows what one exposure step would cost. It also reports whether the still-frame floor is noise or the whole picture moving.
- `gain` runs the uniformity test over each trace's own pixels (see "the gain step").
- `contact` writes the verdict frames out as a labeled PNG. Look at the contact sheet before you
  believe any claim about what was on the stand.

`summary`, `presence`, `sweep` and `stalls` are stdlib only. `contact` needs Pillow and says so.

A parameter that a sweep says should move is a decision entry and not an edit. The constants in
`app/src/motion.ts` are ratios with derivations attached. Moving one without moving its argument is how
the file got into the state D81 found it in.

### The ratchet's escape, and one quiet frame of three (D131)

The noise tracker could lower its idea of still and never raise it. On a bright-lamp rig a resting
card reads `d` 5 to 8, against 2 to 3 on earlier sessions. The tracker converged to 4.5 to 7 while the rest sat at 7 to 9. The settle rule fired on only 5 of 29 cards, with every readout looking normal.
The scene was still. The machine's word for still was wrong in the one direction the ratchet could not
move.

**The escape.** Take the frames with a card in view over the noise window. When the frames the machine calls still fall under `stillFractionMin` (0.30) of them, the still level comes from `restQuantile` (0.25) of all of them. `tHi` keeps its ratio. The escape applies only when that quantile is under the presence floor. A frame-to-frame change no smaller than a card arriving is not a rest. The fraction is
over frames with a card in view, because an empty stand is still on every frame. Earlier sessions keep
46 to 83% of their frames under `tLo` and change zero verdicts. The HUD's `escape` count shows the
escape happening.

**One quiet frame of the last three.** The bright-lamp feeder rests a card two to four frames, with
calm frames around it, and a window of four never filled. A frame under `tLo` is still by definition
and is photographed on. A scene with no quiet frame still expires the stall clock, which is D84's
silent-loss guard unchanged.

A dimmer lamp was not a fix. That trace fired about 87% with worse photographs.

### The camera is an input to the arithmetic, and these settings are locked by measurement

The rig is a Sony RX100 VII over micro-HDMI into an Elgato Cam Link 4K (`app/src/useCamera.ts`'s
header). The browser sees a plain UVC device. Every setting below lives in the camera's own menus.
Nothing on the Cam Link needs configuring.

Since D81, every threshold is a multiple of something the session measures. That buys portability to a
rig this code has never seen. It also buys an exposure. **A camera setting that moves while a session runs moves the baseline those thresholds came from. Nothing reports it.** No constant in
`motion.ts` can defend against that. Only the camera configuration can.

The figures below were measured before `harness/traces/` was cut to ten. They are history unless a row says T9 pins it. A row is marked unmeasured on the ten kept traces where a lock rests on such a figure.
`scripts/score-trace.py camera` re-derives them. Two questions came back null, sharpening and shutter
speed, and the null is the answer.

#### The locked settings

| setting | lock to | the measurement behind it |
|---|---|---|
| Exposure mode | `Movie`, then Manual Exposure | The single most consequential row. One 1/3 EV step moves the watch region by 8.5 to 22.5 luma levels across the traces that carry a baseline (unmeasured on the ten kept). That is over `tLo` and over `presenceMin` on most of them. The figure is a derivation on the baseline under a multiplicative model and not a recorded step, because no banked trace contains one. The machine now refuses the step it describes as `suppressed:uniform` (below). The lock keeps the floor meaning one thing for a whole box |
| ISO | a fixed value, never `ISO AUTO` | A gain step taken mid-session is a cliff and not a gradient. On one session, +1/3 stop costs 48% of the fires after it, and +1.5 stops stops the session firing at all (see "the cliff") |
| Shutter | 1/60 or slower, as slow as the feeder allows | Null result. At the instant of the fire the card moves at 184 sensor px/s (median), so 1/60 smears it 3.1 px of a 3840-px frame. Noise is the binding constraint, and blur is not. Spend the budget on keeping ISO down |
| Aperture | fixed, wherever the lamp allows the ISO above | It is half the same exposure budget, and a body left in `A` re-levels when the scene changes |
| White balance | a preset or Custom WB, never `AWB` | Derived and not measured. A trace carries luma and no chroma. A 3% gain wobble is 1.1 luma levels on the median plate and a 10% preset jump is 3.6. WB sits at `tLo` at worst, and it is free to lock |
| Focus mode | Manual Focus | The RX100 VII offers only Continuous AF and Manual Focus when shooting movies. 1% of focus breathing reads `d` 3.03 and 2% reads 5.83, over `tLo` and under `presenceMin`. So a hunt opens or extends a motion episode and does not fire one |
| SteadyShot | Off | `Active` is a 1.19x crop plus a digital warp, which is the geometric change the breathing row prices. The mount is a tripod that never moves |
| 4K Output Select | `HDMI Only(30p)` | The corpus is 24p. Halving the rate costs 8.7% of the corpus's fires and multiplies stalls 6.3x (unmeasured on the ten kept) |
| Creative Style, Picture Profile | fixed, any value | Null result. In-camera sharpening acts at a few sensor pixels, and a 12-pixel blur costs `d` 0.000 on 84 real card regions. The 60-pixel cell average destroys it. What matters is that the setting does not change mid-run |
| Auto Power OFF Temp | High | A body that shuts down mid-box ends the run, and `HDMI Only` writes no card |

#### The cliff — why `ISO AUTO` can lose a whole box

The still-frame floor is sensor and codec noise. Over quiet keyframe pairs, the delta field's lag-1
spatial correlation is +0.009 across and +0.008 down, against a shuffled control of +0.001. It is
independent cell to cell, which flicker, an AE micro-adjustment and a lamp ripple are not. The global
brightness move is p50 0.00, p90 1.00 and max 4.00 luma levels per second. So gain reaches `typ`
directly, and `typ` carries `tLo`, `tHi` and the adaptive half of the presence floor with it.

A slow drift is absorbed, and that is D81 working. A step is not. Sessions do not degrade. They stop.
One session loses 48% of its post-step fires at +1/3 stop, 82% at +1 stop, and all of them at +1.5.

The mechanism is D131's ratchet. Only frames already under `tLo` enter the noise window. A sudden rise
in the floor means no frame qualifies, the estimate cannot climb, and `tLo` freezes. It was measured
freezing at the seeded 4.50 for the rest of the session. D131's escape refuses to act when its own quantile sits at or above the presence floor. A large gain step puts it exactly there. That is
not a reason to change D131. It is the reason `ISO AUTO` is banned. The failure is in the camera's gift
and not in the machine's.

At any usable gain, `presenceMin` stays the binding term. `presenceFloor` is `max(16.0, 3 x typ)`, so
the adaptive term binds only past `typ` 5.33, which is 3.8 stops above the quietest session in the
corpus.

The lamp is nearly no lever. On one rig, `log(typ) = -0.125 x log(level)` (r = -0.868), so halving the
light raises the floor by 9%. A lower ISO buys a quieter trigger at a factor of the square root of 2 per
stop. Use the lamp to buy shutter and aperture headroom, and spend that headroom on ISO.

#### The frame rate — 24p is the floor, and it is being run at the floor

The stream is 24p. The modal frame gap is 41.5 to 42.5 ms everywhere. That is the source rate. A browser dropping a 30p feed would show a bimodal gap at 33.3 and 66.7 ms.

`stillWindow` is a frame count, so the rate decides how much time a settle needs. Decimating the real
frame series is faithful, because taking real frames further apart is what a lower rate delivers.
Halving the rate to 12 fps costs 8.7% of the fires and takes stalls from 12 to 76 (unmeasured on the ten kept, and the 30p lock rests on it). The hand-fed sessions barely move. The feeder sessions carry all of it.
The bright-lamp feeder rests a card two to four frames, and three of those must fill `stillWindow`.

Going up is not measured and must not be read as measured. Only the risk half can be scored offline.
Shortening the window at the recorded rate gains +11 fires for +8 doubles at a two-frame window. The
benefit half, finer sampling of the rest that `stillWindow` fails to fill, cannot be synthesized from
24 fps frames. Step 5 of the checklist below answers it. The doubles counted here use this section's own
definition (a fire with no fresh `tHi` crossing since the previous fire) and are not comparable to §7's
count.

Dropped frames are real, and worst where the stalls are. Per session the drop share runs 0.00% to 4.95%.
The 4.95% session is one of the four carrying live stalls. A drop inside a settle widens the window in
time and can lose it.

#### The shutter derivation, and why it is a null result

`d` is a mean-abs luma change per frame. For a small rigid displacement `u` in cells, the change per cell
is `u x |spatial gradient|`. Measured on 756 real fired-card watch regions, the region's own mean abs
gradient is 20.93 luma per cell (p10 15.31, p90 28.70). One cell is 60 sensor pixels and the frame period
is 41.7 ms.

| phase | `d` | cells/frame | sensor px/s | blur at 1/60 | at 1/125 | at 1/250 |
|---|---|---|---|---|---|---|
| median fire | 2.66 | 0.127 | 184 | 3.1 px | 1.5 px | 0.7 px |
| p90 fire | 5.32 | 0.254 | 367 | 6.1 px | 2.9 px | 1.5 px |
| the rescue bar, 4/3 x `tLo` | 4.00 | 0.191 | 276 | 4.6 px | 2.2 px | 1.1 px |
| peak transit | 53.26 | 2.544 | 3679 | 61.3 px | 29.4 px | 14.7 px |

The trigger fires at the phase of least motion, and the phase of most motion is twenty times faster.
Three pixels of smear on a 3840-px frame is 1.3 px after `identify/images.py` resamples to its 1568-px
long edge. A rescued frame is only 1.5 px worse than an ordinary one. So blur at the fire phase is not
where the exposure lever is. If a rig run shows blurred rescues, the cause is a card still in transit.
Check `rescue` against `fires` and not the shutter.

#### D84's three quantities, re-derived for this camera

D84 names three quantities that re-derive `presenceMin` on a new rig: the idle stand, the worst approach
and the quietest card. The pipeline that produced the table below reproduces D84's own published figures
exactly, which licenses the rest.

| quantity | first rig | second rig | `presenceMin` = 16.0 |
|---|---|---|---|
| 1. the idle stand | 2.01 to 2.18 | 1.41 to 1.55 (p99 6.45, max 19.96 over 5,436 frames) | 10x clear at the median |
| 2. the worst approach | 11.15 (D84's) | not measurable from these traces, bounded at 12 to 23 | straddled |
| 3. the quietest card | 32.53 | 25.81 (median 107.67 over 578 fires) | 1.6x clear at worst |

Quantity 2 is the honest gap, and it is why protocol step 3 still needs a person. On the first rig the
hand took about two seconds to arrive, and the ramp is legible frame by frame. On the second rig the
whole hand-to-card ramp is four to six frames, about 200 ms. That is under the trace's 1 Hz keyframe
grid, so nothing in the file separates the hand from the card. The per-frame `dBase` bounds it at 12 to
23, which straddles 16.0 and does not sit under it. A 200 ms ramp cannot settle, so the settle rule is
doing the work on this rig and not presence. That is a fact about this feeder's speed and not a margin.
Measure it again at the rig, by eye, whenever the feed changes.

The two rigs are not the same picture. The first is a dark textured stand with a specular hot-spot (plate
level 74 to 77). The second is a bright white plate with a dark card landing on it (plate level 128 to
218). The second is much the better arrangement. Cards read `dBase` 26 to 128 against 9 to 45. It is
also what makes the exposure row bite hardest, because an exposure step costs luma levels in proportion to
the plate's own level. With exposure locked, the bright plate is pure gain.

Card frames put 0.00 to 0.22% of cells at 250 or above on the newest sessions. The plate itself reaches a
bright quantile of 255 on 0.1 to 2.9% of frames in five sessions. So an exposure step down is fully
visible, and a step up is partly absorbed.

Every drift figure here is measured on stretches where nothing was moving. Auto exposure only steps when
the scene changes, which on this rig is when a card is in flight. So these traces bound the drift of
whatever the body was set to. They cannot prove the body was in manual. Step 2 of the checklist decides
that, and it takes thirty seconds.

#### The gain step — refused as the stand rescaled, and what the recordings could and could not prove

D184 is the decision. The lock is a correct fix and not the only one. This block is the version that
does not need the operator's hand, built over recordings alone.

**What the corpus holds.** Every trace stores the watch region and nothing outside it: 1,064 cells at
38x28, keyframes and verdict frames alike. A reference region outside the watch region cannot be derived
from it. A scan of every banked session's consecutive keyframe pairs for a global gain change (median
ratio at least 5% off unity with the pattern preserved) found none. The 8.5 to 22.5 figure in the
exposure row is arithmetic on the baseline.

**Refused: a surround reference region.** The surround was measured from the owner's photographs
instead: 2,535 stored 4K frames over five boxes, each downsampled to the machine's 64x36 grid. A median
per-cell ratio over the surround cancels an injected 1/3 EV step to 0.00 on every box. Against the
arm-time surround it does not hold. Fewer than half the surround's cells agree with the session's first
frame on 87 to 99% of frames. A uniformity guard would decline nearly every verdict. Without one, the
factor is wrong by up to 2.5x (worst pairs: a hand, the tray) and invents a 170-luma change.

**Refused: normalizing the watch region by its own median ratio, always.** In one run over the corpus, 77 of 661 fired cards fall under the floor. The 85/85 run's quietest card goes from 58.8 to 11.0. A
bright card on a dark plate divided by its own ratio is scaled to plate amplitude. With amplitude gone,
the hand (8.3 to 9.1) and the weakest cards overlap.

**What survives is a test.** `k` is the median per-cell ratio of the frame to the baseline over cells
both hold between a toe (8) and a shoulder (247). The residual is mean `|frame - k x baseline|` in the
units of the brighter of the two frames. The frame is UNIFORM when the residual is under `presenceK` x
the session's still-frame difference, the multiple the presence floor already rides. A settled frame over
the presence floor is asked this one more question. A frame that is the baseline times one number (a gain
step on the bare stand) is refused as `suppressed:uniform` and becomes the baseline. A card is a pattern
and not a level, so it never is. Units were measured three ways. The baseline's units put sixteen of the
85/85 run's cards at 1.4x the bound. The frame's units put the closest real card at 1.8x. The brighter
frame's units keep every real card on every session at 4.1x or more.

| reading, all ten sessions | value |
|---|---|
| fired frames over the floor | 353 |
| refused as uniform | 0 |
| closest real card to the bound | 4.1x (85/85 run: 5.3x) |
| the closest frame of any kind | 03:25 at 74.0 s, 1.02x. It is the plate's dark disc displaced and not a card (contact sheet). Its twin at 73.0 s reads 2.29x |
| injected 1/3, 1/2, 1 EV on every baseline | uniform, or under the floor, and never a card |
| injected 1.5 EV | declined on three bright plates (fewer than a quarter of the region unclipped). The floor alone decides, as before |
| the hand D84 photographed the stand with | 8.96 against a bound of 8.09. Not uniform, and refused by the floor as before |
| the reference rig's genuine empty stand | k = 1, residual = raw, 1.70 to 1.78 |
| scaled novelty between consecutive fires | at least 6.89 against `tNovel` 4.0 |

The novelty gate asks the same question of the last fired frame. So a step over a card already photographed is `suppressed:unchanged`, and it is not a second photograph. `d` is not touched. A step is one
spurious episode that resolves as uniform.

The two 03:25 frames are a finding about T9. They cleared the floor at 25.8 and 26.6 from the baseline, so
the bright-lamp block's "the fired frame is a card (at least 17 from baseline)" passed on them. The
contact sheet says they photographed the bright plate with its disc moved. Distance is not content. T9
pins them by time now.

The second candidate, `geometry.detect_card`, is exposure-invariant by construction. It takes 42 ms at
full size and 18 to 21 ms downsampled, which is 45 to 100% of one core at 24 fps. It runs in Python on
the server, and the trigger runs in the browser. The process boundary rules it out as a per-frame gate. It
stays the per-capture crop.

**Mutation testing.** The uniformity arms were mutation-tested over the scorer (read by T9) and over the
machine (read by `motion.spec.ts` in a browser). One survivor is known: the step model without clipping.
The shoulder excludes any cell over 247 whether the model clipped it or not, so the clip in `_step` is
invisible to every verdict. It models the camera, and nothing here can see the camera.

**Not validated.** The step here is `2 ** (EV / 2.2)` applied to a real plate, and its noise is the
plate's own. Two things validate it. One is the first trace saved with the body in `P` or with `ISO AUTO`, scored with `scripts/score-trace.py gain`. The other is the HUD's `uniform` count over one box. That is
one sitting, after the checklist below.

#### The rig checklist — one sitting, before the next feeder run

The cost is about fifteen minutes and one box of expendable commons. It ends with a saved trace. Steps 1
to 4 are the camera. Steps 5 to 7 are what only the rig can answer.

1. **Set the body, movie side, in this order.** `MENU → Movie2 → Exposure Mode → Manual Exposure`. Then
   set shutter 1/60, aperture wherever the lamp allows, and ISO a fixed number. Raise the lamp until a
   fixed ISO gives a correct exposure, and do not raise ISO to meet the lamp. Then set `MENU → Camera Settings1 → Focus Mode → Manual Focus`. Set `MENU → Camera Settings2 → SteadyShot → Off`. Set white balance to a preset or Custom WB. Leave Creative Style and Picture Profile where they are, and stop
   changing them.
2. **Prove the exposure is locked, which the traces cannot.** With the stand empty, sweep your hand
   through the frame and out again, twice. Watch `typ` on the HUD. If `typ` and the plate's brightness
   return to where they were within a frame or two, exposure is locked. If the picture visibly re-levels after your hand leaves, the body is still in an auto mode. Step 1 did not take.
3. **Set 30p and confirm it arrived.** `MENU → Setup → 4K Output Select → HDMI Only(30p)`. The camera
   must be in movie mode with the Cam Link connected for the item to be selectable. Arm, take a
   ten-second trace of nothing, and run `scripts/score-trace.py camera <trace>`. The `delivery` line must
   read 30 fps and a modal gap near 33.4 ms. If it still reads 24, the body did not take the setting.
4. **Read the plate.** The same `camera` output prints the plate level and what one exposure step would
   cost on it. That number is the size of the mistake step 1 prevents. Quote it if anyone proposes
   putting the body back in `P`.
5. **The frame-rate question the corpus could not answer.** Feed one hopper at 30p with no box selected,
   then one at 24p, and compare `fires` and `stall`. The prediction is more fires and fewer stalls at
   30p. The counter-risk is doubles, which the offline proxy put at +8 for +11 fires. Count the doubles by
   hand on this run. It is the only place they can be counted honestly.
6. **The approach, by eye.** Quantity 2 above has no other instrument. With the stand empty and armed,
   reach in as if placing a card and stop short. Watch `dbase` against `floor`. It must not reach 16 while
   your hand alone is in frame. If it does, that is the number to raise.
7. **Then a 50-card run,** with a box selected. Save the trace before disarming. Reconcile `fires` against records. Reconcile `rescue` against the roughly one in nine of §7. Reconcile `stall` against cards you had to re-feed.
   Run `camera` on it last. `delivery` says whether 30p held under load. The drop share is the number to
   watch, because the corpus's worst session dropped 4.95% of its frames.

## 5. Known limits, and what this deliberately does not do

**A manual capture in motion mode does not update the machine's last-fired frame.** The capture button
stays live as an override, but the machine has no path into `doCapture`, by the seam's own design. A card
captured manually can later be captured again by the machine if a wobble opens a new settle episode. The
remedy is D10's: undo the duplicate. The photo is of a card still at the lens. The override is for
rescuing one card and not for running mixed-mode. If a rig session shows that mixed-mode is a real workflow, the fix is a `Trigger.notice()` addition to the seam. Argue it in a decision entry. Do not add a quiet coupling.

**An exposure ramp is not a step, and the noise tracker can see it.** The uniformity test answers a step:
one frame over `tHi`, a settle, a verdict. A body that re-levels smoothly over half a second moves `d` by
about 1.3 a frame at level 150, which is under `tLo`. Those frames are called still, enter the noise
window and lift `typ` for eight seconds. No episode opens. The cost is a slightly raised `tLo` for one
window, and it is measured nowhere, because no trace holds a ramp. The remedy is the lock.

**The sampler runs on the main thread, once per decoded frame.** It uses `drawImage` into a small
CPU-backed canvas plus a 9 KB `getImageData`. That is cheap on paper. If the preview stutters or the cadence of `d` hitches while motion is armed, move the sampling to a worker on an `OffscreenCanvas`. That is the same shape as the encode fix. It is not built pre-emptively. The encode worker was built on a measurement,
and this would be built on a guess.

**The trace is Tier 1.** `app/src/trace.ts` records the signal and the gate-verdict frames and never
continuous video. Nothing about it touches the capture server or the store. The file goes to the
browser's Downloads folder and nowhere else. Tier-2 video is unbuilt and would be a rig-day debugging
instrument at most. There is no auto-advance of boxes and no second store. The one feeder control is the dispenser button (D-dispenser-button), which starts and stops the dispenser and never touches the trigger. Nothing
persists the mode, because arming is an act (D19).

## 6. When does this need recalibrating?

Speed does not move these constants. Light does.

Nothing in the machine encodes the feeder's 623 ms. The clock-locked design was rejected (D19). This one
fires on settle, so the pause between cards can stretch arbitrarily. Hand placement is the slow limiting
case. The pause can shrink until one of two physical walls, and both announce themselves:

- **Faster.** The still window (measured 312 to 400 ms) must keep room for the roughly 120 ms settle
  read. Somewhere past roughly twice today's speed, verdicts start arriving late or never. Past about 3
  cards a second, the capture round trip becomes the bottleneck and the `dropped` counter climbs on
  screen. Neither is silent.
- **Slower.** Nothing, ever, unless the advance motion itself (measured about 217 ms) stretches past
  `maxMoveMs`. That is a jam or a dying mechanism, and it surfaces as `stall` on the HUD and does not fire.

Anything that changes the picture needs attention. Examples are a new lamp, a nudged camera, changed exposure or ISO, a different backdrop, or sleeved cards.

Since D81 those changes no longer need a re-trace to fix, but they do need one to notice. The noise floor
and the presence threshold both follow the session, so a dimmer lamp or a re-framed camera moves the
thresholds with it. Adaptation cannot tell you that the baseline was taken with a card on the stand. It cannot tell you that the card has drifted half out of the watch region. Two watchdogs are free and always on screen. `typ`
idling near 2.2 with nothing moving is healthy, and creeping past 4 is a rig fault. `dbase` reading tens
with a card under the lens, against under 1.5 with the stand empty, is the separation the presence gate
lives on. If either goes wrong, run one 60-second trace and score it with `scripts/score-trace.py` (§4)
before it costs cards.

## 7. The rescue — the card that will not settle

A stall is a card, and dropping it was the wrong answer. The trigger fires on a settle. A card that never
settles inside `maxMoveMs` used to be reported and left unphotographed. That refusal is defensible on its
own terms, because a settle trigger exists to photograph a still card. The real question is which of a soft
photograph and no photograph is worth more. On a feeder, the photograph wins. The card is about to be
replaced and nothing comes back for it. `U` undoes a bad photograph in one press, and a lost card is found
weeks later in a box that does not match its run.

**What the stall episodes are.** Scored over the six sessions then banked, every one of nineteen episodes has
a quietest frame between 1.02x and 1.25x `tLo`. Nine of the first fourteen are under `tLo`, frames the
machine had already judged still. `stillWindow` alone refused those nine. The card landed one or two frames after its transit ended. The window needs three frames to fill. The next card's motion threw it away first. The
rest came to rest just above the line.

**The rescue is a bar and an age, and neither is a new number.** `rescueK` (4/3) is `sqrt(moveK / stillK)`,
the geometric center of the Schmitt band the session already measures. `rescueAfter` (0.60) is a fraction of
`maxMoveMs`, the machine's own statement of how long is too long. Past that age, a frame under `rescueK` x
`tLo` settles the episode, and the window requirement drops with it. The fire is a distinct verdict,
`fire:rescued`, counted as `rescue` on the HUD beside `stall`.

Three things are deliberately not relaxed, and the third is why the rescue is safe:

- **Presence.** A rescue cannot photograph the bare stand. `presenceMin` decides it exactly as it decides an
  ordinary fire.
- **Novelty and the refractory.** A rescue cannot photograph the same card twice.
- **The age.** `stillWindow` is what stops a dip during a transit from firing. The age is the only word the
  machine has for "the transit cannot still be happening". A ramp retires the window from the first frame of
  an episode. A bar rising smoothly from `tLo` to 4/3 over the stall clock takes the corpus's double count
  from 2 to between 20 and 55. That measurement is why this is a step and not a ramp.

`rescueAfter` 0.60 is where two plateaux meet. Swept 0.50 to 0.80 at 0.02, yield is flat at 295 fires and 7 stalls over the six evening sessions from 0.50 to 0.60. It falls away above that (280 and 21 by 0.80). The
eight earliest sessions are untouched from 0.60 up. Below 0.60 the 21:14 session gains a fire 290 ms before
its own next one, and that is the value the corpus refused.

**The corpus, before and after** (`scripts/score-trace.py summary`, pinned in T9):

| session | live | with the rescue | of those rescued | stalls |
|---|---|---|---|---|
| 21:54 | 53 | 60 | 7 | 5 to 3 |
| 22:25 | 17 | 23 | 7 | 5 to 2 |
| 22:29 | 52 | 53 | 2 | 1 to 1 |
| three | 122 | 136 | 16 | 11 to 6 |

The pre-rescue sessions do not move: 86, 13 and 10 live, and 86, 16 and 12 replayed. A stillness rule that
buys cards on one rig by spending them on another is this subsystem's entire history. D81's brightness floor
rescued one session of three and broke the other two. So the sweep was constrained by those sessions and not
scored against the new three.

**What still stalls is the finding.** The six survivors are episodes whose quietest frame never came near the
bar. The clearest is 22:25 at 27.9 s. It sits 1.25 s inside the Schmitt band with not one crossing of `tHi`. A card slides the entire time, and its quietest frame is at 3.4x `tLo`. Extending a deadline for that one
would photograph a moving card. The machine is right to refuse it and say so.

### Glare, and why there is no `stalled:flare`

The owner diagnosed the remaining misses as specular glare, a mirror flash off a tilted card. The obvious
next step is a verdict that names it. Three candidate discriminators were measured over the whole corpus, and
every one failed:

| discriminator | what the traces say |
|---|---|
| saturation | The share of watch-region cells at 250 or above is about 0 on every stall frame (worst 6 of 1,064). That is not evidence of no glare. Each cell averages about 3,600 sensor pixels, so a fully clipped streak reaches the trace as a cell reading 214. The instrument destroys the evidence before the file is written |
| spike shape | A flash should be brief, so peak divided by own-median bright quantile ought to separate. It goes the wrong way: stall episodes read 1.19 median against 1.36 for episodes ending in a fire |
| absolute level | "Brighter than any card this session fired on" flags 6 of the 11 surviving stalls, and 14% to 55% of the ordinary episodes too |

So `scripts/score-trace.py stalls` prints the reading, each surviving episode's peak bright quantile against
this session's own fired cards, and names nothing. A verdict string asserting `flare` would repeat the
brightness-floor mistake: a brightness compared against a line that does not separate the populations. The
fix for glare is optical: the lamp off-axis, a diffuser, a polarizer. No code recovers detail that was gone
before the detector saw it.

### What the first rig run under this rule must measure

Nothing here is validated at the rig. The replay proves the machine fires on more cards. That is arithmetic
over recordings, and it is exactly as far as a trace can go. A 38x28 grid can say that a card is there and
cannot say that it is in focus. Whether the extra photographs are readable is a fact about the JPEGs. Two
earlier motion fixes were derived from frames nobody rendered, which is why `score-trace.py contact` exists.
So the first armed run must do these things:

- **Read `rescue` against `fires` on the HUD.** On the saved corpus, 34 of 295 photographs are rescues, about
  one in nine. A run far above that is landing cards badly.
- **Look at the rescued photographs and not the trace.** They are the ones taken on a frame between `tLo` and
  4/3 x `tLo`. Downsample the run's own JPEGs to the 38x28 watch region and match frame against photograph.
  A trace says what the machine decided. Only the photograph says what was on the stand.
- **If the rescued frames blur,** the lever is the camera's exposure and not `rescueK`. A shorter shutter
  freezes motion that the feeder never removes.
- **Save the trace and score it.** `summary` reports the rescued count beside the replayed one, and `stalls`
  prints what the rescue could not save.
