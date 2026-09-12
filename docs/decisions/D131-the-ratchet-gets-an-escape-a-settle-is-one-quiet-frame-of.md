## D131 — The ratchet gets an escape, a settle is one quiet frame of three, and the beat is the backstop

**Settled 2026-09-11, the owner refusing the claim that the settle trigger could not be**
**fixed — and being right.** The claim in D130 rested on a sweep of one parameter under the
noise tracker's own thresholds; a sweep of the thresholds themselves reaches 94-101% of the
same cards. Two more traces came with the refusal: a full run under the cadence trigger, and a
run with the lamp dimmed on which the shipped settle trigger "worked better" at the cost of the
photographs.

### What was measured

**The rest exists and the machine's thresholds sit under it.** On the three bright-lamp
sessions a resting card reads d 5-8 (brightness jitter: |Δluma| p90 of 6-8 at rest, against
2-3 on every earlier session and 2 under the dimmed lamp) and the transit reads 13-50. The
noise tracker admits only frames already under `tLo` to its still population, so it can lower
the still level and never raise it: seeded at 4.5 it converges to 4.5-7 while the rest sits at
7-9, and the settle rule fires on 5 of 29 cards while every readout looks normal. The eight
earlier sessions keep 46-83% of their frames under `tLo`; the bright-lamp sessions keep 9-18%.

**A window of four never fills.** The feeder rests a card for two to four frames with calm
frames around it; 13 of 28 cards on the first session never had four consecutive frames under
`tHi`. Swept against every old session, one quiet frame of the last three changes no count and
recovers the cards D84 counted as stalls.

**The dim lamp was not a fix.** 65 fires and 13 stalls live; ten real misses on cards that
slid for 1.7 s, seven gaps that were the operator pausing. About 87%, with worse photographs.

### The ruling

**Three changes to the settle machine, and the second trigger becomes a dual.**

1. **The ratchet's escape.** When the frames the machine calls still are under
   `stillFractionMin` (0.30) of the frames with a card in view over the noise window, the
   still level is taken from `restQuantile` (0.25) of all of them, `tHi` keeping its ratio —
   and only when that quantile is under the presence floor, because a change no smaller than a
   card arriving is not a rest. Measured in both directions: zero verdicts change on the eight
   earlier sessions (the escape trips a handful of times on the three 2026-09-01 sessions and
   decides nothing), and the four new sessions replay 31, 21, 45 and 85 against 5, 5 live on the
   two the ratchet lost. The fraction is taken over frames with a card in view, because an empty
   stand is still on every frame and a window that had just watched thirty seconds of it called
   the first cards a still majority for six seconds.
2. **One quiet frame of the last three.** D84's two-of-four, amended. A frame under `tLo` is
   still by definition and is photographed; a scene with no quiet frame at all still expires the
   stall clock, which is D84's silent-loss guard unchanged. The 21:10 card at 14.1 s that D84
   counted as a stall is a fire now.
3. **The dual.** The cadence trigger takes the settle machine's own fire whenever it comes, at
   least half a period after the last, and re-anchors the beat on it; the scheduled fire runs
   only when a rest window has passed with no settle. Settle accuracy where a card rests, the
   beat where it never does. The owner's words: *"a dual approach might be best."*

### What is BUILT, RECORDED, and NEITHER

**BUILT:** the escape and the window in `src/motion.ts`, mirrored in `scripts/score-trace.py`
and locked by `make docs-audit`'s `motion params` row; the dual in the cadence module; an
`escape` counter on the HUD; the four sessions banked and pinned in T9's third corpus and in
the cadence spec. **RECORDED:** here, in `docs/specs/motion-trigger.md` §2 and §7.
**VALIDATED THE SAME NIGHT, AT THE RIG.** Two boxes under the bright lamp on the settle trigger
alone: 70 fires over ~75 cards and 51 over ~54, two stalls each, no double, every fire under
d 10 with `tLo` reaching 9-11.5 — about 97% where the shipped rule managed 17%. Banked in T9.
**NEITHER still:** the photographs themselves (whether a d 5-8 frame reads clean is a fact about
the JPEGs), and a rig run of the dual, whose case is exactly the two or three sliding cards each
run stalled on.

### What D130 said that this corrects

D130 wrote that "no adaptation of a stillness detector answers a scene that is never still."
The scene was still; the detector's idea of still was wrong, in the one direction its ratchet
could not move. D130's cadence trigger stands as the backstop it has become.

**THE DUAL WAS DELETED THE SAME EVENING, BEFORE IT EVER RAN AT A RIG, AND THIS ENTRY'S OTHER TWO RULINGS STAND.**
The owner retired the cadence trigger outright — *"motion is better.
always."* — and the dual went with the machine it was half of. Ruling 3 is the only one
affected; the escape and the one-of-three window are in the tree, still measured in both
directions, and still what this entry is for. The case the dual was built for — the two or
three sliding cards per run that stall — is the rescue's case now, and the rescue takes them
without a second machine: replayed over these same sessions it picks up two and three of them
on 04:07 and 04:09. See the rescue's entry.
