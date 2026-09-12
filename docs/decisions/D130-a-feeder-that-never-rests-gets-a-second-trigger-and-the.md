## D130 — A feeder that never rests gets a second trigger, and the beat is measured not typed

**Settled 2026-09-11, the owner reporting the settle trigger firing on a handful of a box.**
They proposed the fix in their own words — *"the first card kinda just triggers you to then go
on a timed cadence since they're coming out of a machine at pretty set intervals … then we get
trigger 1 trigger 2 and i can test both."* Two motion traces came with the report, saved from
the HUD over a re-arranged rig.

### What the traces said

**The plumbing was never in question and the settle rule was the whole problem.** Every fire
the settle machine (`src/motion.ts`, D81/D84) made reached disk and every one photographed a
card. It made five fires on a session that fed 29 cards, and five on one that fed ~34 — the
counts are in `harness/tests/t9_traces.py`'s `CADENCE` block and asserted there. The reason is
one measurement: the feeder now lays a card down every 0.867 s (29 luma cycles, p10-p90
0.85-0.92) and from the first card the watch region is never quiet for more than a frame. The
longest run of frames under `tLo` per card has a median of one, and 13 of 28 cards on the
first session never had four consecutive frames under `tHi` at all. A settle is `stillFrames`
of the last `stillWindow` — D84's rule, two of four with the window full — and a feeder that
never lets a card sit still cannot produce one. `scripts/score-trace.py sweep` confirms no
threshold recovers it: 9 of 29 at its best `stillK`.

**This is not a re-tune and D81/D84 are not reopened.** The settle rule remains correct for
the rig it was measured on — the 85/85 run stands — and the two new traces are banked as T9's
third corpus, a receipt for what stillness-firing costs on a beat with no rest, not evidence
against the earlier rule. What changed physically is the feeder's rhythm, and no adaptation of
a stillness detector answers a scene that is never still.

### The ruling

**Two triggers behind the one seam (`src/trigger.ts`), and the operator picks per run.** The
settle machine is trigger 1, unchanged. `src/cadence.ts` is trigger 2: it waits for the first
card on the settle machine's own presence gate (D81's distance-from-baseline), fires on it,
and then fires once per beat of the feeder. The beat is measured, not typed — the
autocorrelation of the motion signal over the last `windowMs`, with the strongest lag between
`minPeriodMs` and `maxPeriodMs` taken as the period and a half/third-period peak read as a
harmonic and rejected (the first two seconds of one trace read 1,770 ms for an 885 ms beat,
which fires on every other card). Locked, it folds the window by the period and fires at the
phase of least motion, taking the first still frame in a window that opens `restLead` early,
a merely-calm frame at the rest, or whatever is there at the deadline — every non-still fire
counted as `blindFires` so the readout says how many photographs were taken on a moving frame.
The presence and novelty gates that guard the settle machine guard this one; two `same`
verdicts in a row means the feeder stopped with a card at the lens and the beat goes idle
rather than re-photographing it. Replayed causally over the two traces it reaches 27 fires over
29 cards and 20 over ~21, against five and five live.

**The period seed is 870 ms in `dSeed`'s exact sense** — what the machine runs on until it has
measured — and the operator may pin a period from the Rig panel while the phase is still
measured, which is the one control the settle machine does not have.

### Why measured and not clock-locked, given D19 rejected exactly that

**D19 rejected a predictive clock-locked trigger, and this is not that.** D19's objection was
to a trigger that fires on a typed period and drops a card whenever the feeder drifts off it.
This trigger fires on a period it measures from the feeder itself every `refreshFrames`, and it
still fires on the first card by presence and re-anchors on every fire — so a feeder that speeds
up, slows down or skips a card is followed rather than lost. The clock is a prediction of when
to look for the rest, not a replacement for looking. D19's live-fire principle is intact: the
machine reads the lens every frame and decides on what it sees.

### What is BUILT, RECORDED, and NEITHER

**BUILT.** The cadence module under `app/src/` (the machine and the trigger), the third
Trigger cell and the period-pin control on `#/capture`, the beat's HUD instruments, the trace's
`trigger` field, its own spec under `app/tests/` (replay of both traces plus the synthetic
contract), and T9's `CADENCE` corpus. Reachable from the screen: it is a real destination the
Rig panel's Trigger track arms.

**AND DELETED ON 2026-09-11, THE SAME DAY, ON THE OWNER'S WORD.** *"I dont want cadence and
motion as separate triggers btw, get rid of cadence... motion is better. always."* Both files
are gone — which is why this paragraph names them in prose rather than as paths — along with
the third Trigger cell, the period pin and the beat's HUD spans.
**What this entry measured stands and is not re-litigated**: the settle rule DID photograph one
card in six on a feeder that never rests, and this entry is the receipt for it. What closed the gap turned out to be
the settle machine's own thresholds — D131's escape the same night, and then the rescue — and
once those reached the cards, a second machine behind the seam was a second thing to arm, to
tune, to trace and to explain. The two sessions stay banked in `harness/traces/` under T9's
`BRIGHT_LAMP` corpus; the one recorded under this trigger still says `cadence` in its `trigger`
field, and `app/src/trace.ts` narrowed the WRITER's type rather than the file format for
exactly that reason. See the rescue's entry.

**RECORDED.** The two traces in `harness/traces/`, and the measurements above, here and in
`docs/specs/motion-trigger.md` §7.

**NEITHER, and named so nobody reads this as confirmed.** No photograph has been taken by this
machine at the rig. The replay says a fire lands on a frame with median `d` of 3-4 on the
faster session and higher on the slower one — moving, a little — and whether that reads as a
usable photograph or a blur is a fact about the camera's exposure only the rig can settle. The
first armed run is the measurement, and its trace is what §7 asks for. The 85/85 confirmation
belongs to trigger 1; trigger 2 has none yet.
