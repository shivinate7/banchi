## D-a-gain-step-is-the-stand-rescaled — A gain step is the baseline times one number, a card is not, and the machine re-baselines only on that proof

**Settled 2026-09-12, on the owner's question whether locking the camera's exposure was**
**genuinely essential or "just coding bad".** The honest answer was that the lock is a correct
fix and not the only one: the trigger's presence gate reads a DISTANCE from the arm-time
baseline, an auto-exposure step is a distance too, and nothing in the machine could tell the two
apart. This entry is the version that does not need the operator's hand — and it is built over
recordings alone, with what that does and does not prove written down.

### What was measured, in the order it was measured

**The corpus cannot answer the question the way it was first posed.** The proposal was to
normalize each frame against a reference region OUTSIDE the watch region, so a global gain
cancels and only local change survives. Every banked trace in `harness/traces/` stores the watch
region and not one pixel outside it — 1,064 cells at 38×28, keyframes and verdict frames alike —
and a scan of every consecutive keyframe pair across twenty sessions found no observed global
gain change (the three candidates at a 6% ratio are quantisation on a dark plate). The
**8.5–22.5 luma** figure in the spec's exposure row is a DERIVATION on the baseline under a
multiplicative model, not a frame anybody recorded; it still stands, and it is now labelled.

**The surround was measured from the owner's photographs instead**, read-only: 2,535 stored
4K frames across five boxes, the stored rotation undone and the frame downsampled to the
machine's own 64×36 grid. The mapping is proven rather than assumed — every one of the
2026-09-11 22:12 session's 51 fires matches its photograph's watch region in order (50 of 50
consecutive, median correlation 0.86), under one rotation and not the other. What the surround
does across a card swap: on the reference rig the corners are still to 0.6–1.3 luma over 543
swaps; on the feeder rig the left third moves 27–47 luma every cycle (the tray) and the right
side holds at 1.3–3.3. A median ratio over the surround cancels an injected 1/3 EV step to
0.00 on every box. **But against a FIXED reference the surround drifts within one sitting**
— the arm-time surround, non-uniformly: fewer than half its cells agree with the session's
first frame on 87–99% of frames, 95% of them within three and a half minutes on box 5. A
uniformity guard would decline almost every verdict; without one the factor is wrong by up to
2.5× (a hand, the tray) and invents a 170-luma change. **Refused.**

**Normalizing the watch region by its own median ratio, always — refused in one run.**
77 of 661 fired cards fall under the presence floor, and the 85/85 run's quietest card
goes from 58.8 to 11.0: a bright card on a dark plate, divided by its own ratio, is scaled to
plate amplitude and its pattern goes with it. With amplitude gone the hand (8.3–9.1) and the
weakest cards overlap, and no floor separates them.

**What survives is a TEST rather than a normalization.** A frame that clears the presence floor
is asked whether it is the baseline times one number: take `k`, the median per-cell ratio to the
baseline over the cells both frames hold between a toe and a shoulder, scale the BASELINE up by
`k`, and read the mean absolute residual in the frame's own units. A gain step leaves the plate's
noise; a card leaves its pattern. The bound is `presenceK` × the session's own still-frame
difference — the multiple the presence floor already rides — so no threshold moved and no new
constant decides anything. Measured on every fired frame in the corpus (748 that clear the
floor, twenty sessions): the smallest residual on every session is **3.0× the bound or more**,
5.3× on the 85/85 run; the one frame under it, 03:25 at 74.0 s (4.0 against 4.56), is the plate's
own dark disc displaced and not a card — the contact sheet says so, and T9 pins it by time. A
synthetic 1/3, 1/2 and 1 EV step on every baseline is uniform or under the floor; 1.5 EV is
declined on six bright plates where it clips three quarters of the region, and declined is the
machine as it was. The hand D84 photographed the stand with reads 7.61 and 8.68 against 7.41 and
8.09 — not uniform, and refused by the floor as before. Consecutive fires, scaled the same way,
stay 5.2 or more apart against `tNovel` 4.0.

**Frame units, not baseline units, and it was measured both ways.** Dividing the frame down
instead put sixteen of the 85/85 run's cards at 11.0–12.0 against a bound of 8.04 — 1.4×, a
noisier session away from refusing real cards. Scaling the baseline up leaves them at 42.5.

### The ruling

1. **A uniform rescale of the baseline over the presence floor is `suppressed:uniform`,**
   **and the frame becomes the baseline.** This is the one place the machine
   re-baselines on its own, and `MotionControls.rebaseline`'s rule — no re-baseline on the
   machine's judgement of what is on the stand — stands: this is a proof that nothing on the
   stand changed, and zero of 748 fired frames pass it. Adopting the frame is what keeps a hand
   under the floor after a step; judged against the old baseline it would carry the step on top.
2. **The novelty gate asks the same question of the last fired frame**, so a step over a card
   already photographed is `suppressed:unchanged` and not a second photograph.
3. **`d` — the stillness signal — is untouched.** A step is at most one spurious episode that
   resolves as uniform; a slow ramp under `tLo` per frame enters the noise window for its
   duration and is not covered. Named in the spec's §5 as the limit it is.
4. **Three parameters, all shaping the comparable set and none a threshold**: `uniformMinShare`
   0.25 (a quarter of the region must be comparable, or the question is declined and the floor
   alone decides), `uniformToe` 8, `uniformShoulder` 247. Mirrored into `scripts/score-trace.py`, reconciled by `make
   docs-audit`'s `motion params` row, which also mirrors `tNovel` now that the scorer reads it.
5. **The manual-exposure guidance stays as written.** This makes the trigger survive its
   absence; the lock is still what makes the presence floor mean one thing for a whole box.

### What this is, in the report's own vocabulary

**BUILT**: the test in `app/src/motion.ts`, its mirror in `scripts/score-trace.py` (`gain`),
the HUD's `uniform` counter, three machine-spec cases, and a T9 block over every frame the corpus
holds. **RECORDED**: every measurement above in `docs/specs/motion-trigger.md` §4.
**NEITHER, and it is the load-bearing gap**: no real exposure step has ever been recorded on this rig. The
step here is a multiplicative model with the plate's own noise; the first trace saved with the
body in an auto mode, `scripts/score-trace.py gain` over it, and the HUD's `uniform` count on a
box are what validate this, and §4's checklist says so.

**The second candidate, priced and not taken.** `geometry.detect_card` is exposure-invariant by
construction and went 0 of 53 then 53 of 53 on real photographs. Timed on an eval image: 42 ms
at full size, 18–21 ms downsampled — 45–100% of one core at 24 fps — and it runs in Python on the
server while the trigger runs in the browser, so per-frame use would be a JPEG per frame over
the wire or a port. The feeder cadence is 623 ms; the cost is not the objection, the process
boundary is. It stays what it is: the per-capture crop, not a gate.

Governs `app/src/motion.ts`, `scripts/score-trace.py`, `harness/tests/t9_traces.py`,
`app/tests/motion.spec.ts`. Amends the reading of D81 (presence is a distance — and a distance
has a shape) and D84 (the hand's floor stands unchanged). Does not reopen D19, D130 or D131.
