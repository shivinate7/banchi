## D144 — A card that will not settle is photographed off the quietest frame it manages, and there is one trigger again

**Settled 2026-09-11, on the owner's own account of what the rig was doing.** Their words:
*"considering you can see the hit rate and the non hit rate, can't you create code that
captures all these edge cases"*, and the failure they were naming: *"it's really bad when the
cards are coming a little slower or aren't landing perfectly, the engine is then bad at picking
those up"*. Six traces came with it. This entry is the answer to the second sentence and the
retirement of D130's second trigger, which arrived as a separate instruction the same evening.

### What was measured

**The corpus.** Six armed sessions on 2026-09-11 evening, banked in `harness/traces/` and
pinned in T9 as its fourth corpus. Live: **268 photographs against 20 stalls**, the owner's own
accounting of the first four being "199 captures, 14 misses, 93.4%". The last was recorded
after they changed the lighting and reported the run as working well — 52 fires, one stall —
and it is the control that says what follows is not compensation for one lamp.

**A stall is a card, and until this the answer was to drop it silently.** `maxMoveMs` reports
an episode that never settles and does not fire. That refusal is defensible on its own terms —
the point of a settle trigger is a still card — so the question was never "can it fire anyway"
but **which of a soft photograph and no photograph is worth more**. Under a feeder the answer
is the photograph: the card is about to be replaced, nothing comes back for it, and `U` undoes
a bad one in one press while a lost card surfaces weeks later in a box that does not match its
run.

**Every stall episode's quietest frame sits between 1.02x and 1.25x `tLo`**,
and **nine of the first fourteen are UNDER `tLo`** — frames the machine had already
judged still. Those nine were refused by `stillWindow` alone: the card landed one or two frames
after its transit ended, the window needs three to fill, and the next card's motion threw it
away first. The rest came to rest just above the line. **This is not a threshold problem.** The
sweep says so directly: `stillK` is flat from 1.4 to 2.5 on every one of these traces, and
presence is not close — every card reads `dBase` 105-143 against a floor of ~21.

**The obvious fix is wrong, and it was measured rather than argued away.** Dropping the
full-window requirement outright rescues the nine, and takes the corpus's double count from
**2 to 21**: `stillWindow` is what stops a dip DURING a card's transit from firing, and a
second fire on one card is worse than a miss — the operator finds two photographs of the same
card and no photograph of the next. A bar that ramps smoothly from `tLo` to the band's centre
over the stall clock is the same defect wearing a curve — it is at `tLo` from the episode's
first frame — and scores 20 to 55 doubles across the corpus.

### The ruling

**1. The rescue.** Once a settle episode has run `rescueAfter` x `maxMoveMs` without settling,
a frame under `rescueK` x `tLo` settles it, the window requirement dropped with it. The verdict
is `fire:rescued` — a distinct string, because the photograph is different in kind and the
first rig run has to be able to count them — and `rescue` joins `stall` on the HUD.

**Neither number is new.** `rescueK` is **4/3**, which is `sqrt(moveK / stillK)`: the geometric
centre of the Schmitt band the session already measures, exactly 4/3 because `moveK/stillK` is
16/9 by `moveK`'s own definition. It covers all nineteen episodes and is
**the largest value the corpus tolerates** — at 1.40 the 21:16 session gains a fire it lacked.
`rescueAfter` is **0.60**, a fraction of `maxMoveMs`, the machine's own word for how long is
too long.

**0.60 is where two plateaux meet, and the sweep is the argument.** Swept 0.50-0.80 at 0.02:
yield is flat at 295 fires and 7 stalls over the six evening sessions from 0.50 to 0.60 and
falls away above it (280 and 21 by 0.80); the eight earliest sessions are untouched from 0.60
up and gain a fire and a double at 0.58 and below — the 21:14 session's 6.21 s rescue lands
290 ms before its own 6.50 s fire.
**The eight earliest constrained the sweep rather than being scored against it.**
A stillness rule that buys cards on one rig by spending them on
another is this subsystem's entire history: D81's brightness floor rescued one session of three
and broke the other two.

**Presence, novelty and the refractory are NOT relaxed**, and that is what makes the rescue
safe rather than merely productive. A rescue cannot photograph the bare stand — D84's two junk
rows stay fixed — and cannot photograph the same card twice.

| | live | with the rescue | rescued | stalls |
|---|---|---|---|---|
| six evening sessions | 268 | **295** | 34 | **20 -> 7** |
| eight earliest sessions | — | 86, 86, 20, 15, 24, 49, 16, 12 | 3 | 1 -> 0 |

**The seven survivors are the finding, not the residue**: every one is an episode whose
quietest frame never came near the bar. The clearest is 22:25 at 27.9 s — 1.25 s inside the
band with **not one crossing of `tHi`**, a card sliding the entire time, quietest frame at
3.4x `tLo`. The machine is right to refuse it and say so.

**2. A stall is a sentence on the stage, not a number in a disclosure.** It sat between `empty`
and `escape` inside a collapsed `Tuning` block while the operator watched the stage, so the one
event that costs a card was the one event nothing said out loud — exactly what `noCardRun` was
given a sentence for. It renders as what it means, with a `Set aside` press that spends the
count, the halt banner's own per-accounting-period idiom. This is the cheapest of the three
things considered and would have been worth doing alone.

**3. There is no `stalled:flare`, and that is a finding rather than a gap.** The owner
diagnosed the misses as specular glare and dimmed the lamp between runs (scene p90 111 -> 89)
while the flares still hit 176 and 198. Three candidate discriminators were measured over the
whole corpus and **all three failed**: saturation reads ~0 on every stall frame, and that is
not evidence of no glare — a 38x28 cell averages ~3,600 sensor pixels, so a fully clipped
streak arrives as a cell reading 214 and the instrument destroys the evidence before the file
is written; a spike-shape ratio goes the wrong way, stalls at 1.19 against 1.36 for episodes
ending in a fire; and "brighter than any card this session fired on" flags 6 of 11 stalls and
**14% to 55% of ordinary episodes too**. So `scripts/score-trace.py stalls` prints the reading
— each surviving episode's peak bright quantile against this session's own fired cards — and
names nothing. A verdict asserting `flare` would be `cardLumaFloor`'s mistake in a third
costume. **The fix for glare is optical and stays optical.**

**4. The cadence trigger is deleted, and D130 and D131 are amended rather than dropped.**
A separate instruction the same evening: *"I dont want cadence and motion as
separate triggers btw, get rid of cadence, if tehre's anything built from cadence we can take
into motion great, else just get rid of it. motino is better. always."*
**Nothing came across, and the reason is D19.** The one thing cadence had that the settle machine does not is a
measured feeder period, and a settle trigger that encodes the feeder's beat is the
predictive clock-locked design D19 rejected on day one; importing it to keep a machine the
owner had just retired would have re-opened that entry to save this one. D131's rulings 1 and
2 — the ratchet's escape and one quiet frame of three — are untouched and are what closed the
gap; only ruling 3, the dual, goes, and it never ran at a rig. Its case, the two or three
sliding cards per run, is the rescue's case now: replayed over D131's own two rig sessions the
rescue picks up exactly two and three of them.

**The deletion reaches D141's path list, and that is the rule working rather than an exception.**
`harness/traces/`, every trace under it, is in the browser matrix's scope because that spec read two
recordings off disk with `readFileSync`. That spec is gone and no spec under `app/tests/` reads
a trace any more, so the entry is removed rather than left standing as a widening nothing
justifies — the same disease the `map sections` row exists for. The list is DERIVED from what
the suite loads; when the suite stops loading something, the entry goes, and
`scripts/browser-scope.py`'s own selftest flips with it: a trace now SKIPS.

**A gate that edits the gate is where a reader wonders, so: no hole, and here is why.**
The filter that decides whether CI runs the browser matrix is
one of the files this branch edits. It still covers `app/**`, and this diff touches `app/**`,
so the branch classifies RUN and the suite that would catch a broken screen is the suite that
ran. The narrowing is in the other direction — a trace-only change skips — and a trace-only
change cannot reach a browser. Had the narrowing gone the other way, the gate would have been
judging itself by a rule it had just relaxed, which is the shape to refuse.

### What is BUILT, RECORDED, and NEITHER

**BUILT:** `rescueK` and `rescueAfter` in `app/src/motion.ts`, mirrored in
`scripts/score-trace.py` and locked by `make docs-audit`'s `motion params` row; the
`fire:rescued` verdict and the `rescue` counter; the stall sentence and its `Set aside` press
on `#/capture`; `score-trace.py stalls`; three cases in `app/tests/motion.spec.ts` including
the one that proves a rescue cannot photograph an empty stand; the six sessions banked and
pinned as T9's fourth corpus. The cadence module and its spec are deleted, with the third
Trigger cell, the period pin and the beat's HUD spans.

**RECORDED:** here, in `docs/specs/motion-trigger.md` §2 and §7, in `docs/GATES.md`'s T9 block,
and as amendments closing D130 and D131.

**NEITHER — AND THIS IS THE HALF THAT MATTERS.**
**No photograph taken under this rule has ever been looked at.** The replay proves the machine fires on more cards; that is arithmetic over
recordings and it is exactly as far as a trace can go. Whether a frame between `tLo` and
4/3 x `tLo` produces a readable JPEG is a fact about the JPEGs, and this repo has been burned
there twice — two earlier motion fixes were derived from frames nobody rendered, which is why
`score-trace.py contact` exists at all. A trace stores pixels only for verdict frames and
once-a-second keyframes, so the frames this change newly fires on are, with few exceptions, not
in the files:
**the evidence for the photographs does not exist offline and cannot be manufactured.**

**FIVE OF THEM DO EXIST AND WERE RENDERED, WHICH IS AS FAR AS THIS GOES.** Of 28 rescues that
are a new card rather than an existing fire taken a frame sooner, five land within one frame of
a stored keyframe or event. Drawn at 38x28 beside the two nearest ordinary fires of the same
session:
**each holds a card-shaped object with structure, none obviously worse than its neighbours** —
the 03:20 rescue at 101.29 s is cleaner than the ordinary fire
0.13 s after it, which is a blown-out flare. One, 21:54 at 19.36 s, is noticeably dimmer than
the ordinary fire beside it, which is consistent with a card not yet fully down.
**That is a sanity check and it is not the measurement.** 1,064 cells averaging ~3,600 sensor
pixels each can say "a card is there"; it cannot say "this is in focus", which is the only
question that matters. §7's last block is the first armed run's checklist, and the honest
summary until that run is that the machine takes 27 more photographs per 295 and five of them
have been looked at through a keyhole.
