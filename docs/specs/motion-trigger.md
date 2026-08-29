# Motion trigger — execution spec and rig-tuning protocol (Gate C)

Written 2026-08-22, the day it was built. D19 is the decision; this file is the mechanism,
the derivations, and the protocol for the part no computer can do — tuning at the rig.
`docs/GATES.md`'s Gate C section carries the measurements every number here leans on.

## STATUS — CONFIRMED LIVE: 85/85 ON THE SECOND FEEDER RUN

The trigger exists: `app/src/motion.ts` behind `app/src/trigger.ts`'s seam, armed from a
mode toggle on the capture screen, with a live HUD and a swallowed-fire counter. Two specs
cover it — `app/tests/motion.spec.ts` proves the machine's arithmetic against an exact
answer key, and `app/tests/motion-live.spec.ts` drives the real screen in a real browser
with a synthetic camera stream, from arming through firing to the dropped-fire count. Both
run in `make design-check`.

**The first feeder trace arrived 2026-08-23 — 86 cycles, 65.3 s — and retuned the one
constant it convicted.** The feeder's measured rhythm: period 623 ms burst-to-burst, each
card ~217 ms moving and ~400 ms still (min still gap 132 ms), frames delivered at ~25 fps.
The conviction: the LIVE feed's still-phase noise is median 2.51, p99 4.07 — eleven times
the 0.35 floor measured off Gate B's stored JPEGs, because the preview stream never went
through a JPEG encode — so the first `tLo` of 3.0 sat inside the noise and 14 of 86 cards
(16%) passed without reaching a verdict, silently, exactly as the owner reported. The
offline replay reproduced the live run frame-perfectly (72 fires, zero suppressions),
and the swept retune (`tLo` 3.0 → 4.5, `tHi` 6.0 → 8.0) scores **86/86 with zero
double-fires** across the whole tLo 4.0–5.0 plateau.

**The second feeder run confirmed it live, same day: 85 of 85 cycles fired, zero doubles,
zero misses** — 72.5 s at the same 620 ms period, one designed `no-card` suppression at arm
time, captured into a real box (95) through the full path. That clears the 50-card bar for
the trigger half of Gate C; the gate still owes the pipeline half (identify → join → emit →
reconcile on a feeder-paced box) and foil under this lamp. The thinnest margin in the
system is the noise floor — still-noise p99 measured 4.07 and 4.13 across the two runs
against tLo 4.5 — and §6 names its watchdog.

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

| parameter | value | derivation |
|---|---|---|
| grid | 64×36 | each cell averages ~3,600 sensor pixels; noise attenuates ~60× |
| watch region | centre, inset 20% x / 10% y | 15 of 53 Gate B frames carry a second card in the feed path; card placement repeats to ~30 px | 
| `tHi` | 8.0 | retuned 2026-08-23: burst peaks measured ≥ 9.6, still phase ≤ 4.56 — 8.0 splits the populations. The first guess (6.0, from Gate B stills) also worked live |
| `tLo` | 4.5 | retuned 2026-08-23, the constant the trace convicted: live still-noise p99 is 4.07, eleven times the stored-JPEG floor the first guess (3.0) was derived from. Replay: 86/86 at 4.0–5.0, vs 72/86 live at 3.0 |
| `stillFrames` | 2 (67 ms) | fire latency (stillFrames+1)·f = 100 ms = 22% of the 458 ms worst observed cycle. The first guess — 6 frames + a blinding 400 ms cooldown — summed past the *mean* cycle: 619.7 − 233 − 400 = −13 ms |
| refractory | 250 ms, deferring | sized to the <250 ms capture round trip, not the card cycle; a settle inside the window fires at expiry instead of being dropped |
| `tNovel` | 4.0 | ~11× noise, ~3.5× under the weakest same-card repeat across the Gate B duplicate pairs |
| `cardLumaFloor` | 90 | card region measures ~172, empty desk/backdrop 30–65. **Read as the ROI's bright QUANTILE since 2026-08-29, not its mean — see below.** |
| `maxMoveMs` | 1250 | ~2× the feeder period; a jam surfaces as `stalled` and does NOT fire (D19 carries both sides of that argument) |

Three gates on a fire, one verdict per settle episode: stillness (synchronisation — fire
once per card, not mid-swap; the sharpness justification was tested against the real
frames and failed an anisotropy test), novelty against the last-fired frame (the gate that
actually prevents double-captures), and the luma floor (card present — deliberately NOT
`geometry/detect.py`'s tone segmentation, which measured 0/53 on this rig; a brightness
floor over a fixed region needs none of that method's premises).

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
armed and shows `phase · d · luma · fires · same · empty · stall · dropped`. `d` is the
live number every threshold is set against, on screen precisely so §4 can tune against a
value the operator can see. Arming is session-only (D19): every reload starts manual.

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

Cost: ~30 minutes at the rig, one box of expendable commons, before the 50-card
confirmation run. Order matters; each step isolates one parameter family.

1. **Noise floor first, nothing moving.** Arm motion with the rig lit and the stand empty.
   `d` should idle near **2.5, and under ~4.1** — the live feed's measured floor, NOT the
   "far below 1" this step first predicted from Gate B's stored JPEGs; the preview stream
   is ~11× noisier because it never went through a JPEG encode, and that misprediction is
   what cost 14 cards in the first feeder run. Reading well above 4: mains flicker (pin
   the shutter to a multiple of the mains period — §10.0's list) or an unstable lamp.
   Expect one `empty` suppression at arm time and silence after.
2. **Card-present floor.** Place one card by hand. `luma` should sit near 170 against an
   empty-stand reading near 50; `cardLumaFloor: 90` should split them with margin on both
   sides. A sleeved or dark-art card that reads low is a floor problem — lower it before

### `cardLumaFloor` READS A QUANTILE, NOT A MEAN — and a second rig is what proved it

**The mean is a statement about the whole watch region; the gate needs a statement about
whether a card is IN it.** Those coincide only while the card fills the region, which is what
the rig this was tuned against happened to do. Point a differently-framed camera at the same
feeder and the card occupies part of the region against a dark surround: the mean is dominated
by background and collapses under the floor while the card is plainly there.

**Measured on the owner's second rig, 2026-08-29, from two saved traces** — the instrument this
spec's §6 exists for, re-scored offline with no rig trip:

| | mean | bright quantile (p90) |
|---|---|---|
| empty stand | 27–30 | 62–69 |
| settled card | 62–86 | 125–236 |

**The floor of 90 sat ABOVE BOTH MEANS.** The gate could not fire at any brightness, and no
amount of relighting would have fixed it — the failure is geometric, not photographic. One
session settled twenty cards correctly and refused every one as an empty stand; a second
settled fifteen and fired twice, both on a static frame before the feeder started.

**The constant does not move.** 69 against 125 leaves 90 exactly where it was, now with a real
gap either side, and it stays backward-compatible with the rig it was derived from: a card
filling the region has a bright quantile at least as high as its mean, so ~172 still passes.
Re-scored through the fix, the two traces go 2 fires to **15 of 15**, and 0 to 7 on the
under-lit one, with the empty-stand keyframes still correctly refused.

**`CARD_QUANTILE` is 0.9 rather than the maximum** because a specular highlight off a sleeve, a
lamp clipping into frame or a single hot pixel all carry a maximum and none of them is a card.
Asking that roughly a tenth of the watched cells are card-bright is a claim about an object
being there.

**What this does NOT change**: `tHi`, `tLo`, `stillFrames`, `refractoryMs`, `tNovel` and
`maxMoveMs` are untouched, and so is every measurement behind them. Motion and settle detection
were never at fault — both traces show the machine finding every card at the feeder's cadence.
Only the presence gate was reading the wrong statistic.

**The tuning protocol above gains one step**: read the HUD's `luma` with a card under the lens
AND with the stand empty, and check the gap rather than the absolute. The HUD now reports the
quantile, because a screen showing a statistic the machine does not use is how a rig gets
debugged against the wrong number for two sessions.
   blaming anything else.
3. **Swap signal.** Hand-swap cards at feeder-ish pace. Every swap should spike `d` past
   `tHi` and every settle should fire exactly once; `same` should stay at zero unless you
   re-present the same card, and then it should count exactly once per re-present.
4. **The feeder, empty run.** Feeder running, no captures consumed (no box selected —
   fires land in `dropped`, which is the point: count feeder cycles against `fires`).
   Agreement within one or two over a hopper is the pass. Watch `stall`: the feeder's own
   motion profile has never been measured, and if its advance reads as continuous motion
   longer than 1250 ms, `maxMoveMs` is the constant to raise.
5. **Save the trace before disarming — every step above, and this one, is in the file.**
   The `Save trace` button under the HUD downloads the whole armed session: every frame's
   `(t, d, luma)`, plus the exact watch-region pixels each fire/suppression/stall was
   decided on, plus once-a-second keyframes. It is self-describing (the thresholds travel
   with the evidence) and lands in the browser's Downloads folder as
   `motion-trace-<timestamp>.json`. Hand that file to a session and the tuning happens
   offline: period, jitter, t_move/t_still measured rather than derived, and the gates
   re-scorable against different thresholds without another rig trip. A trace survives
   disarming — it resets only when motion is armed again — so save late rather than early.

6. **The 50-card run** (Gate C's own bar), box selected, milliseconds now on every
   `captured_at`: reconcile `fires` against records, `dropped` against the halt story, and
   the cadence against the trace. Then a full box.

Tuning is editing the constants in `app/src/motion.ts` under Vite's hot reload — they are
named, documented, and in one block. If the rig session finds itself wanting live sliders,
that is UI surface to argue for afterwards with numbers in hand, not to build on spec.

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

What DOES need a re-trace is anything that changes the **picture**: a new lamp, a nudged
camera, changed exposure or ISO, a different backdrop, sleeved cards. Those move the noise
floor and the luma levels — and the noise floor is the thinnest margin in the system
(still-noise p99 measured 4.07/4.13 against tLo 4.5). The watchdog is free and always on
screen: the HUD's `d` idling near 2.5 with nothing moving is healthy; creeping toward 4 is
the cue to run one 60-second trace *before* it costs cards, exactly the ritual that caught
and fixed the first miscalibration.
