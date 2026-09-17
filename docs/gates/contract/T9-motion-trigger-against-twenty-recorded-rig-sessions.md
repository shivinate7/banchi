### T9 — Motion trigger against twenty recorded rig sessions

New 2026-08-31 with D81, widened 2026-09-01 with D84 and again 2026-09-11 with the rescue. **Pass: on every saved trace an empty stand sits within 2 of its own baseline and every card sits
17 or more away; the dimmest card on one rig is dimmer than the empty stand on another, so
no brightness constant separates them; the adaptive thresholds reach at least as many
verdicts as the hand-tuned constants did live on all ten; and on the three sessions D84
was derived from, the presence floor refuses both settles that photographed the bare stand
while the card that never settled is photographed by the rescue at the second the stall used
to be reported; and on the six overnight 2026-09-11 sessions the settle rule as shipped fired
five times each on the two the ratchet lost while the rule in the tree replays 31 and 21; and
on the six evening sessions the rescue takes the run from 268 photographs and 20 stalls to 295
and 7; and the uniformity test refuses a synthetic 1/3, 1/2 or 1 EV exposure step on every
session's baseline while refusing no real card on any of them, while every one of the eight
earliest sessions keeps the verdict count it had.**

**The inputs are `harness/traces/` — twenty armed sessions**, saved from the capture screen's
HUD by the owner between 2026-08-23 and 2026-09-11: FIVE recorded under the brightness floor
D81 replaced, THREE recorded on 2026-09-01 under the distance gate that replaced it (the
sessions D84 was derived from), SIX recorded overnight on 2026-09-11 over a re-arranged feeder
under a bright lamp — two on which the shipped settle trigger fired five times each against 29
and ~34 cards, one under the cadence trigger, one with the lamp dimmed, and two run LIVE under
D131's rule (70 and 51 fires, two stalls each, no double) — the sessions that convicted the
noise tracker's ratchet (D131) and then confirmed its repair at the rig, and SIX MORE that
evening: the corpus the rescue was built on, 268 live photographs against 20 stalls, with the
last of them recorded after the owner changed the lighting and reported the run as working
well. Each carries every frame's `(t, d, luma)`, v2
adding `dBase`, and the exact watch-region pixels of every verdict, which is what makes a
refusal re-scorable a year later. They are ground truth in `fixtures/`'s sense and are never
modified.

**The four corpora are named in code and never summed.** "38 real cards were refused live" is a
receipt for what the brightness floor cost, and only the first five sessions were ever recorded
under it; adding the later three would turn a fixed number into one that grows every time a
trace is banked.

**Why it exists.** The card-present gate was rebuilt three times. Through the first two, both
Playwright specs over the motion machine stayed green — they draw their own frames, so they
can only prove the machine agrees with the test's idea of a card. Meanwhile the constant in
the tree refused **38 real cards as an empty stand across three live sessions**, silently. T9
is the first test in this repo that could have failed.

**Four kinds of assertion, and they are not equally valuable.** The *separation* — empty stand
within 2 of its baseline, cards 17 or more away — is a claim about photographs, and if it
fails something physical changed. The *counts* are a claim about the replay's arithmetic: a
tripwire for a constant moved without re-scoring, legitimately updatable as a decision with
the sweep re-run, never as a reflex. The *D84 pair* is a claim about the two defects those
three sessions cost — that the presence floor refuses both settles that photographed the bare
stand and nothing else that fired, and that a card which never completes a settle is never
lost in silence — reported as a stall when D84 was written, photographed by the rescue since
2026-09-11, at the same second either way. Both are asserted by TIME and not by count, because
"two fires are refused" would pass just as happily on a floor that had climbed far enough to
refuse two cards. The *rescue* is a claim about the six evening sessions of 2026-09-11 — that
the rule photographs the cards `stillWindow` was dropping — **and, in the same block, that the
eight earliest sessions do not move while it does**. That second half is the load-bearing one:
a stillness rule that buys cards on one rig by spending them on another is this subsystem's
entire history, and it is what the sweep behind `rescueAfter` was constrained by rather than
scored against.

**The answer key is written down, not inferred**, and that is the point rather than a
convenience. The 2026-08-29 fix derived its "empty stand" brightness table from twenty frames
that were photographs of real cards, because a refusal was read as evidence about what was on
the stand. Every verdict frame was rendered and inspected before the labels in
`t9_traces.py` were written; `scripts/score-trace.py contact` is how.

**WHAT A GREEN T9 DOES NOT MEAN.** It does not mean the trigger works at the rig today —
these are fourteen recordings of a handful of rig states, and the next can differ from all of
them. Same limit T6 and T8 carry. What it means is that the machine still tells a card from an empty
stand on every session anybody has recorded.

**No card is identifiable and no code card is present.** A stored frame is 1,064 luma cells
at 38x28 — the watch region, quantised — which cannot carry a readable QR, and every session
here is the singles feeder. T8's rule stands untouched.
