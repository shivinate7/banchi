## D81 — The presence gate is a distance from this session's own baseline, and the stillness thresholds are multiples of what this session measures

**Built 2026-08-31, after the owner's fourth motion trace and a direct question: whether the capture trigger was ever the dynamic thing it was described as.**
The honest answer was no, in the half that was costing cards, and the traces settle it
rather than anybody's recollection. `scripts/score-trace.py` is the pass; run it on the four
saved traces and it prints the same numbers this entry argues from.

### What was actually wrong, and it was a mistake of KIND rather than of tuning

The trigger has two halves and only one of them was ever dynamic. Motion detection is a
frame-to-frame difference, which is inherently relative and cancels the light level — that
half has found the cards in every session ever traced.
**The card-PRESENT gate was a brightness compared against the constant 90**, and no constant
can do that job:

| scene | rig / session | bright quantile |
|---|---|---|
| **empty stand** | reference rig, 2026-08-23 | **57** |
| card | under-lit rig, 2026-08-29 21:34 | **61**–134 |
| card | 2026-09-01 | 77–171 |
| card | reference rig, 2026-08-23 | 196–244 |

**An empty stand at 57 and a real card at 61.** Four luma levels apart, on different days,
with the floor at 90 sitting *inside* the card population of three of the four sessions. The
bill:
**20 of 20 cards refused on 2026-08-29 21:34, 13 of 15 on 21:38, 5 of 24 on 2026-09-01 — 38 real cards called an empty stand, silently**,
against exactly ONE correct
refusal in the whole corpus (the genuinely empty stand at arm time on 2026-08-23). Every
frame was rendered and looked at; there is a card in all 38.

**The 2026-08-29 quantile fix was the same mistake one layer in.** It changed which
brightness statistic the constant was compared against — mean to p90 — and the constant was
never the right shape of thing to compare a brightness against. It also derived the "empty
stand" numbers in its own table from frames that were photographs of real cards, because a
refusal was read as evidence of what was on the stand.
**`scripts/score-trace.py contact` exists so that cannot happen a third time**: it draws
every verdict's frame as a labelled
contact sheet, and the only thing that settles what a frame contains is looking at it.

### The ruling: presence is distance from a baseline this session took

**A settled frame is a card when it differs from the watch region as it stood when armed**,
by more than `presenceK` × this session's own typical still-frame
difference, floored at `presenceMin`. Scored over the same four traces:

- an empty stand sits **1.10–1.38** from its own baseline
- every card of every session sits **17.4–167.4**

**A 43× gap where brightness gave 1.07×.** Every value of the floor from 6 to 10 gives
byte-identical verdicts on all five traces, which is what a real gap between two populations
looks like; 8.0 is the middle of it, and is set by illumination DRIFT rather than by noise —
a static scene walks up to 7.94 from a baseline seconds old, measured.

**What this deliberately gives up.** A card already at the lens when the trigger is armed
becomes the baseline, and is refused rather than captured. That behavior was real and is
now gone. **It is forced rather than chosen**: the old machine captured it only because the
card was bright and 90 happened to sit under it — the exact mechanism the table above
convicts — and nothing in a single frame separates "the stand as it normally looks" from
"the stand with a card on it" without a reference. At arm time the reference is what is
being established. The cost is one photograph at the top of a run; the old cost was twenty
mid-run.

**The failure direction is inverted on purpose, which is the point of the whole entry.** A
wrong baseline now causes EXTRA fires — visible in the strip, undone with `U` — where the
old gate caused silent refusals. And a run of refusals is no longer a counter climbing
beside six other counters: `noCardRun` counts them consecutively and the capture screen
renders three in a row as the sentence it means, naming the cause and the remedy. The remedy
is a `Re-baseline` control on the HUD, a button rather than a letter because it is performed
after clearing the stand with a hand already off the keyboard, and because the letter it
would want is the box field's.

### The stillness thresholds go the same way, and the repo's own history is the receipt

**The 2026-08-23 retune (`tLo` 3.0 → 4.5) was a person at a rig discovering that the live preview's noise floor is eleven times the stored JPEGs' one**
— after 14 of 86 cards had
gone past the lens without ever reaching a verdict. That is a measurement the machine can
take in eight seconds. `tLo` and `tHi` are now `stillK` and `moveK` times the median
frame-to-frame difference of the last 8 s of frames the machine already called still.

| trace | presentations | live constants | adaptive |
|---|---|---|---|
| 2026-08-23 02:49 (`tLo` 3.0) | 85 | 72 | **86** |
| 2026-08-23 03:09 (the tuned 85/85 run) | 85 | 86 | 86 |
| 2026-08-29 21:34 | 19 | 20 | 20 |
| 2026-08-29 21:38 | 14 | 15 | 15 |
| 2026-09-01 | 25 | 24 | 24 |

**Met or beaten on every trace**, including the one whose silent misses cost a rig trip to
diagnose. `stillK` was chosen from a sweep over all five traces at once rather than tuned on
one: 2.0 sits in the middle of a plateau (2.0–2.5 all meet live everywhere) instead of on
the edge of a peak, which is the failure mode of the 2026-08-23 retune repeated with better
manners.
**The seed reproduces Gate C's hand-tuned pair to the last digit — 4.50 and 8.00, so the machine boots on the constants the 85/85 run was confirmed on and adapts away from them.**
Nothing about that run is being re-litigated; it is being made portable to a rig
that is not that one.

**Only frames the machine already calls still feed the estimate**, and that restriction is
the direct answer to `motion.ts`'s own former objection that "an EMA floor that learns
during slow motion is a way to go blind". A hand resting half in frame, a jammed feeder, a
card creeping: all sit above `tLo`, never enter the window, and cannot redefine what
stillness is. The one thing this cannot recover from is a session whose noise is entirely
above the seeded 4.5 — and that failure is loud rather than silent: not one capture is taken
and the HUD sits in `moving`, which is the opposite of the failure being fixed.

### What did NOT change, and why each one is a decision rather than an oversight

**`tNovel` stays an absolute 4.0.** Across all five traces and 217 verdicts, the
`suppressed:unchanged` count is **zero** — there is no measurement to derive a multiple
from. And scaling it to session noise would push it DOWN on a quiet rig, making suppression
more likely, which is the wrong direction: a false pass is a duplicate `U` fixes, a false
suppression is a silent loss. It stays until a trace convicts it.

**`refractoryMs` and `maxMoveMs` stay absolute** because they are times, not light levels;
nothing about them is a constant compared against a measurement.

**The HUD lost `luma` and gained `dbase`, `floor`, `tlo`, `thi` and `typ`.** Every number on
that row is now one the machine decides on. The row carried `luma` for two rig sessions
while the gate read a different statistic, which is how a rig gets debugged against the
wrong number; the bright quantile survives in the trace, as evidence about lighting, and
gates nothing. **The trace is version 2** — a v1 row is `[t, d, luma]` and a v2 row is
`[t, d, dBase, luma]`, and a scorer that read the third column as brightness would read a v2
trace as a rig with no light in it.

**What would reopen this:** a trace where a card is genuinely indistinguishable from the
baseline — a white card on a white stand under flat light, where distance is as blind as
brightness was. The answer then is not a third constant but a second signal (edges, or the
stand's own fixed landmarks), and it should arrive with a trace attached like this one did.
