## D84 — A settle is a count over a window, the stall clock is cleared by a settle, and the presence floor is sized to a hand

**Built 2026-09-01, from three traces the owner recorded after D81 and handed back with one question: whether those were flawless runs.**
They were not, and neither defect was visible from the rig — one put junk in the box and the
other lost cards in silence. `scripts/score-trace.py` is the pass; run `summary` and
`presence` over the three 21:xx traces in `harness/traces/` and it prints what this entry
argues from.

### What the three sessions actually cost

93 seconds of feeding, 69 fires, and every fire landed on disk — the trigger's plumbing was
never in question:

| | cards fed | good captures | photographs of the bare stand | **fed and never photographed** |
|---|---|---|---|---|
| 21:10 | 47 | 45 | 1 | **2** |
| 21:14 | 13 | 12 | 1 | **1** |
| 21:16 | 11 | 10 | 0 | **1** |

**The four losses were established by looking, not by inference**,
which is D81's own standing instruction. Every one of the 69 JPEGs was downsampled to the trace's 38×28 watch
region and matched against the recorded frames: a true match scores MAD 13–19, and the four
orphan scenes score 23.7–30.2 against their nearest photograph. They are in no file. The two
junk fires were opened and read — the bare stand, at the top of a box.

**Every defect sits in the first two seconds after arming.** After that the cadence is
metronomic: 43 consecutive fires in the longest session with no gap over 1.0 s.

### Ruling 1 — a settle is `stillFrames` of the last `stillWindow`, not a consecutive run

A consecutive run is defeated absolutely by a two-frame alternation, and the alternation is
measured rather than feared. A card motionless for 500 ms at the head of the 21:10 session,
against a tLo of 4.18, every frame:

    2.71  5.40  2.63  5.54  2.83  5.14  3.03  4.80  3.64  4.91

Five separate runs of ONE, never a run of two. Two of the last four is satisfied at the
third frame. Swept over all three sessions it recovers two of the four cards and changes no
other verdict; 2-of-3 and 3-of-5 both recover fewer.
**A settle may only complete on a frame that is itself quiet**,
because the fire photographs that frame — measured, it costs nothing, and without it a
capture could be taken from a frame the machine had just called not-confidently-still.

**The cost is two frames of latency per capture**, ~84 ms at the observed 24 fps, against a
623 ms feeder period with ~400 ms of stillness in it. Re-scored, the five pre-D81 traces
reach byte-identical verdict counts, so the confirmed 85/85 run is not re-litigated.

### Ruling 2 — the stall clock is cleared by a COMPLETED settle

The clock was cleared by any single frame under tLo while a fire needed two in a row, so the
alternation above reset it every other frame and it could never expire.
**Across three sessions and four cards left in front of the lens unphotographed, `stalled` did not fire once.**
The one signal built to mean "something is there and I am not capturing it" was structurally
blind to the only case that produced it.

Cleared on a settle instead, it reports each of them: one stall per session, every one on a
real card, and
**zero false positives across 67 good captures and the 217 verdicts of the five earlier traces**.

**This is the ruling that matters most, and it is deliberately not a capture.** Two of the
four losses had one quiet frame in ten — those scenes were genuinely moving, the operator's
hand still on the card, and no threshold should photograph them. Ruling 1 recovers the two
that were still; this one makes the other two loud. Together the four silent losses become
two photographs and two sentences on the HUD, which is what §5.5 asks for.

### Ruling 3 — `presenceMin` is 16.0, and it is sized to a hand

**D81's own derivation of 8.0 did not survive re-measurement, and this entry corrects it rather than extending it.**
8.0 was set by illumination drift — a static scene walking 7.94 from a baseline seconds old. An undisturbed stand does not creep at all. Per-second worst
dBase, plate only:

    21:10   0s 2.45  1s 2.26  2s 2.53 … 9s 2.36 │ 10s 8.12  11s 14.14  12s 17.91
    21:16   0s 2.13  1s 2.19  2s 2.20 … 5s 2.79 │  6s 6.81   7s 14.66   8s 11.64

Everything above 3 is **the operator's hand entering frame with the first card**. It holds
still for two frames on the way in, and at 8.0 that fired. 16.0 is 1.4× over the worst
approach measured (11.15) and 2× under the quietest card in the same sessions (32.5);
re-scored end to end it removes exactly the two junk fires and nothing else.

**It is a constant and it is now the binding term, and that is a debt rather than a design.**
`presenceK × dTypical` sits at 6–10 on this rig, so this floor decides every verdict and D81's adaptive half decides none — the species D81 convicted in `cardLumaFloor`,
reintroduced knowingly. It stays constant because what it must clear is a HAND, whose size
in frame no session statistic measures.
**Three quantities re-derive it on a new rig and they are the three above**:
the idle stand, the worst approach, the quietest card. Nothing
in the machine measures the second, which is why this is written down instead.

### What is enforced rather than asked for

`make docs-audit`'s **`motion params`** row reconciles `app/src/motion.ts`'s `DEFAULT_PARAMS`
against `scripts/score-trace.py`'s mirrored constants, both directions, with an accounted-for
list for the one parameter the offline scorer deliberately does not carry.
**That row was claimed before it existed**:
`score-trace.py` has said since D81 that the audit keeps the two honest, and there was no such row, while this entry widened the mirror by two more constants.
A comment naming a check that does not exist is worse than no comment — it is the reason the
next session does not write one.

The three traces are banked and T9 grades them: that the floor refuses exactly the two
settles that photographed the bare stand **and nothing else that fired**,
asserted by time rather than by count, because "two fires are refused" would pass just as happily if the floor
had climbed far enough to refuse two cards instead.

**What would reopen this:** a rig whose hand approach reads above 16, or a card that reads
below it. Either is one trace away from being visible, and the answer is not a fourth
constant — it is a measurement of the approach the machine can take for itself, which this
rig's stand is too quiet to have taught anybody how to do.
