# Motion trigger — execution spec and rig-tuning protocol (Gate C)

Written 2026-08-22, the day it was built. D19 is the decision; this file is the mechanism,
the derivations, and the protocol for the part no computer can do — tuning at the rig.
`docs/GATES.md`'s Gate C section carries the measurements every number here leans on.

## STATUS — BUILT AND SELF-TESTED, NOT TUNED

The trigger exists: `app/src/motion.ts` behind `app/src/trigger.ts`'s seam, armed from a
mode toggle on the capture screen, with a live HUD and a swallowed-fire counter. Two specs
cover it — `app/tests/motion.spec.ts` proves the machine's arithmetic against an exact
answer key, and `app/tests/motion-live.spec.ts` drives the real screen in a real browser
with a synthetic camera stream, from arming through firing to the dropped-fire count. Both
run in `make design-check`.

**What a green run of both says is that the wiring works. It says nothing about the rig.**
Every threshold below was derived from 53 photographs of one lot under one lamp, and
crossed in tests by scenes built to cross it. The feeder's own rhythm, foil under the
rig's light, and the operator's tolerance for false fires are all unmeasured. BUILT is not
TUNED — the same distinction this repo already holds between built and validated — and
§4's protocol is what closes it.

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
| `tHi` | 6.0 | ~17× the measured 0.35 noise floor, ~2.4× under the weakest real swap (14.3) |
| `tLo` | 3.0 | the Schmitt band under `tHi`; one threshold chatters and the still-count never accumulates |
| `stillFrames` | 2 (67 ms) | fire latency (stillFrames+1)·f = 100 ms = 22% of the 458 ms worst observed cycle. The first guess — 6 frames + a blinding 400 ms cooldown — summed past the *mean* cycle: 619.7 − 233 − 400 = −13 ms |
| refractory | 250 ms, deferring | sized to the <250 ms capture round trip, not the card cycle; a settle inside the window fires at expiry instead of being dropped |
| `tNovel` | 4.0 | ~11× noise, ~3.5× under the weakest same-card repeat across the Gate B duplicate pairs |
| `cardLumaFloor` | 90 | card region measures ~172, empty desk/backdrop 30–65 |
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
   `d` should idle far below 1. If it doesn't: mains flicker (pin the shutter to a multiple
   of the mains period — §10.0's list), or the pane/lamp is unstable. Nothing else is
   tunable until this is quiet. Expect one `empty` suppression at arm time and silence
   after.
2. **Card-present floor.** Place one card by hand. `luma` should sit near 170 against an
   empty-stand reading near 50; `cardLumaFloor: 90` should split them with margin on both
   sides. A sleeved or dark-art card that reads low is a floor problem — lower it before
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
