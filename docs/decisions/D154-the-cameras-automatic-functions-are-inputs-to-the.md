## D154 — The camera's automatic functions are inputs to the trigger's arithmetic, and the ones that step are locked

**Settled 2026-09-12.** The question was which Sony settings the motion trigger wants and why,
answered by measuring the twenty traces banked in `harness/traces/` rather than by reasoning
about photography. The rig is a **Sony RX100 VII over micro-HDMI into an Elgato Cam Link 4K**,
confirmed by the owner; `docs/specs/motion-trigger.md` §4's last block is the settings, the
derivations and the rig checklist, and `scripts/score-trace.py camera` is the reader that
re-derives every figure.

### The determination

**A drifting camera setting is dangerous precisely because of D81.** Every threshold is now a
multiple of something the session measures: presence is the distance from the watch region
as it stood at arming; `tLo` and `tHi` ride the session's own median still-frame difference. A
setting that moves BETWEEN rigs is now absorbed — that is the change working. A setting that
moves WHILE a session runs moves the baseline the thresholds were derived from, mid-run, with
nothing reporting it. **No constant in `motion.ts` can defend against that.** This entry is the
ruling that the camera configuration is where it is defended instead.

**A camera setting is therefore a repo fact, not a rig preference.** It is written down, it has
a measured reason per row, and it has a reader — the same bargain `docs/map.py` makes, for the
same reason: a claim nobody can re-derive is one nobody can contradict.

### What was measured, and the two that came back null

**EXPOSURE IS THE ROW THAT MATTERS.** One 1/3 EV step — the smallest a Sony AE takes — moves the
watch region by **8.5 to 22.5 luma levels** across the fifteen traces carrying a baseline, over
`tLo` on **15 of 15** and over `presenceMin` on **9 of 15**. On more than half this corpus a
single AE step on an empty stand reads as **a card arriving**. The transform is multiplicative in
code space and the gamma bracket 1.9–2.4 moves the median figure over 18.7–23.3, so the
conclusion does not rest on the assumed exponent.

**GAIN IS A CLIFF, NOT A GRADIENT, AND THAT IS THE FINDING WITH TEETH.** The still-frame floor is
independent cell to cell — **lag-1 spatial correlation +0.009 across, +0.008 down, 299 pairs** —
against a shuffled control of +0.001, so it is sensor and codec noise
and gain reaches `typ` directly. A slow drift is absorbed. A step is not: on the 2026-09-11 03:25
session, **+1/3 stop costs 48% of the fires after it**.
At **+1.5 stops it never fires again**, for the whole of its remaining 75 seconds.
The mechanism is D131's ratchet — only frames already
under `tLo` enter the noise window, so a sudden rise means nothing qualifies and `tLo` freezes at
the seeded 4.50 — and **this is deliberately NOT a reason to change D131**: the escape refuses to
act when its own quantile sits at or above the presence floor, which is exactly where a large
gain step puts it, and loosening that would be repealing the guard that makes the escape safe.
The failure is in the camera's gift. `ISO AUTO` is what is banned.

**AND THE LAMP IS NEARLY NO LEVER, WHICH IS THE USEFUL SURPRISE.** On one rig over twelve
sessions the floor tracks the plate level as **log(typ) = −0.125 × log(level), r = −0.868** —
halving the light raises the floor 9%. Shot noise at a FIXED gain predicts −0.10 after the
display gamma, and the measured slope is that. A brighter lamp does not buy a quieter trigger; a
lower ISO does, at √2 per stop. Reach for the lamp to buy exposure headroom, then spend the
headroom on ISO.

**SHUTTER SPEED IS A NULL RESULT AND THE NULL IS WORTH MORE THAN THE INTUITION.** At the instant
the trigger fires the card is moving at **184 sensor px/s** (median of 756 real fired-card
regions, via the region's own measured gradient of 20.93 luma/cell).
**At 1/60 that smears it by 3.1 px of a 3840-px frame** — 1.3 px once the pipeline
resamples to its 1568-px long edge. A transit's peak is
twenty times faster, which is precisely why firing on a settle makes the shutter a non-issue.
`docs/specs/motion-trigger.md` §7's line *"if the rescued frames blur, the lever is the camera's
exposure"* is answered: at the fire phase it is not, and a rescued frame is 1.5 px worse than an
ordinary one. **Open the shutter and spend it on ISO.**

**SHARPENING AND NOISE REDUCTION ARE A NULL RESULT TOO.** They act at a few sensor pixels, and a
blur out to a **12-pixel radius costs `d` 0.000** on 84 real card regions — the 60×60-pixel cell
average destroys it; the knee is at 21–30 pixels. The Picture Profile is locked only so it does
not CHANGE mid-run, not because its value matters.

**FRAME RATE IS THE ONE FREE IMPROVEMENT.** The stream is **24p on 20 of 20 traces** (modal gap
41.5–42.5 ms, 69.7% of 26,943 intervals; a dropped 30p feed would be bimodal at 33.3 and 66.7 ms
and only 0.13% sits there). `4K Output Select → HDMI Only(30p)` is one menu item. Frames are the
currency: decimating the real series to 12 fps costs **8.7% of the corpus's fires** and takes
stalls from 12 to 76. **Going UP is not measured and the entry says so** — only the risk half can
be scored offline, and it is mild.

**AUTOFOCUS AND STABILISATION ARE LOCKED ON A MEASUREMENT AND A DOCUMENTED LIMIT.** The RX100 VII
offers **only Continuous AF and Manual Focus when shooting movies**, so there is no lock to reach
for and MF is the only answer. A hunt costs `d` 3.03 at 1% of focus breathing and 5.83 at 2% —
over `tLo`, never near `presenceMin` — so it extends a motion episode rather than firing one.
`SteadyShot Active` is a 1.19× crop plus a digital warp, priced by the same row.

### D84's three quantities, and the one that could not be taken

The pipeline behind this **reproduces D84's own published figures exactly** — its two bare-stand
fires at `dBase` 9.07 and 9.10, and its quietest card at 32.53 — which is what licenses the rest.
Re-derived for this camera: the **idle stand** reads 1.41–1.55 on the 2026-09-11 rig, and the
**quietest card** 25.81 against a median of 107.67 over 578 fires.

**The worst approach could not be measured, and that is recorded rather than estimated.** On the
2026-09-01 rig the hand took about two seconds to arrive and D84 read 11.15 off it. On this rig
**the whole hand-to-card ramp is four to six frames, about 200 ms** — under the trace's 1 Hz
keyframe grid — so no stored frame is unambiguously a bare plate with a hand over it, which the
contact sheet confirms by eye. The per-frame `dBase` bounds it at **12 to 23**, which
**straddles `presenceMin` rather than sitting under it**. What keeps that from being D84's defect
returning is that a 200 ms ramp cannot settle — on this rig the settle rule is doing the work and
presence is not the binding protection.
**That is a fact about this feeder's speed and not a margin**, so it is checked by eye at the
rig whenever the feed changes — step 6 of
§4's checklist. `presenceMin` does not move on this entry's authority.

### What this deliberately does not do

**No parameter in `app/src/motion.ts` moves.** Everything here is arithmetic over recordings, and
this subsystem's entire history is of stillness rules that bought cards on one rig by spending
them on another (D81's brightness floor rescued one session of three and broke the other two). A
setting is a rig fact and a threshold is a repo fact; this entry changes only the first.

**The traces cannot prove the body was in manual**, and the entry says so rather than implying
it. Every drift figure is measured on stretches where nothing was moving, and auto exposure only
steps when the scene changes — which on this rig is exactly when a card is in flight and `d` is
the card. The corpus bounds the drift of whatever the body was set to; step 2 of the checklist is
what decides which mode that was, and it takes thirty seconds.

**Nothing here is validated at the rig.** SPECIFIED and RECORDED; not BUILT, not VALIDATED.