### Gate C — feeder integration. PASSED 2026-08-22

**The feeder exists and runs today** (confirmed 2026-08-13). Cards are fed onto a tray,
landing in the same spot each time. This gate therefore tuned against a rhythm that already
existed rather than building one — a smaller job than this section was written to describe.

It did not move auto-capture earlier. **Gate B ran manual**, on the original reasoning, and
the reasoning is the part worth keeping: auto-capture was scoped as an incremental addition
after step 7 because of its own complexity, and a run that tests the pipeline and an untuned
trigger at once cannot say which one failed. `docs/specs/capture-app.md` built the trigger
as one replaceable piece, and the seam held — the motion machine landed as an addition
rather than a rewrite.

The feeder pauses per card, so the method is a motion state machine — and **the machine
is BUILT as of 2026-08-22** (`app/src/motion.ts` behind the trigger seam, a mode toggle
and live HUD on the capture screen, two specs in `make design-check`; spec at
`docs/specs/motion-trigger.md`, decision at D19). **Every threshold was derived from Gate
B's frames**, and that provenance is the finding the first live trace then convicted: live
still-noise runs eleven times the stored-JPEG floor `tLo` was fitted to, which silently cost
14 of 86 cards until it was retuned. Video frame extraction is no longer "the fallback if
tuning misbehaves" — D19 rejects it as a capture path outright and keeps it only as a
rig-session debugging instrument.

**What this gate asked for, and what it got.** It asked for the ~30-minute tuning protocol,
a 50-card run, then a full box. The protocol ran and produced the retune above; the 50-card
bar was cleared twice over by two 85-card runs; **the full box has not happened, and neither
has the pipeline half** — see the two paragraphs below, which say exactly what box 95 did
and did not do. Recorded as owed rather than quietly dropped, even though nothing is gated
on it any more.

**The rhythm has a number now, and half of one.** Recorded here because Gate B measured it
by accident and the next run should not have to.

- **The feeder emits roughly every 660 ms**, per the owner. Gate B's run independently
  agrees: the operator's press loop started ~64 ms/card ahead of the machine, banked a peak
  lead of 2.2 s by card 47 on cards the feeder had already dropped, then had to slow to the
  supply — and its **last eight gaps average 661.9 ms**. Two estimates, 2 ms apart.
- **Jitter across the whole run was 34 ms** (robust σ; 57 ms by standard deviation), min
  458 ms, max 796 ms, over 52 intervals. Unimodal and peaked, not piled at a floor.
- **The capture path is not the constraint.** An earlier burst the same evening did 25
  consecutive captures in ≤6 s, bounding press-to-commit at 250 ms, so Gate B ran with
  2.5–3.7× headroom.
- **The half that was missing arrived 2026-08-23, off the first motion trace**: each cycle
  is ~217 ms moving and ~400 ms still (min still gap 132 ms), period 623 ms burst-to-burst
  over 86 cycles — comfortably inside the settle design's feasibility bound. The same trace
  convicted the first `tLo`: live still-noise runs eleven times the stored-JPEG floor it
  was derived from, which silently cost 14 of 86 cards; retuned, the offline replay scores
  86/86 with zero double-fires. `docs/specs/motion-trigger.md` carries the numbers; what
  remains live is the confirmation run.

**The confirmation run happened, and it passed: 85 cards, box 95, nothing dropped.**

- **Nothing dropped, and that is checkable rather than remembered.** Box 95 holds 85
  records at indices 1..85 with **zero gaps** and **85 distinct `capture_id`s**, so the
  machine fired once per card and the replay guard caught no double-submission. All 85
  carry a finish claim; all 85 have a photograph on disk.
- **Cadence, measured over the run's 84 intervals**: median **623 ms**, mean 633 ms,
  robust σ **43 ms** (67 ms by standard deviation), min 520 ms, max 878 ms, and **zero
  intervals above 1.6× the median** — no stall, no double-fire, no recovery gap.
- **The trace's prediction was exact.** The tuning trace above put the period at "623 ms
  burst-to-burst over 86 cycles". The confirmation run's median is 623 ms. The retuned
  `tLo` did what the replay said it would.
- **A second run agrees independently.** Box 99, 85 cards, taken earlier the same evening:
  median 618 ms, mean 631 ms, robust σ 47 ms, min 506 ms, max 903 ms, zero gaps, zero
  outliers. **Two 85-card runs whose means differ by 2 ms.**
- **The motion trigger is slightly faster than the hand it replaced**, at comparable
  jitter: Gate B's manual loop averaged 661.9 ms over its last eight gaps at σ 34 ms;
  this runs at 623 ms and σ 43 ms. The operator was the slower component.

**What this run did not do, and it is half of what this section used to ask for.** Box 95
holds 85 records and **every one of them is still `captured`**: zero identified, zero
carrying a SKU, and `runs/` holds no run directory for that box. The cards were photographed
at feeder pace and the pipeline was never pointed at them.

So the trigger half is confirmed and the pipeline half is not. `docs/specs/motion-trigger.md`
said so on the day and was right: *"That clears the 50-card bar for the trigger half of Gate
C; the gate still owes the pipeline half (identify → join → emit → reconcile on a
feeder-paced box) and foil under this lamp."* Written down here rather than left to that
spec, because this section is where a later reader looks for what a run proved, and "85
cards, nothing dropped" reads as end-to-end when it was not. Gate B is still the only run
that has been through identify, join, emit, Import to Staged and reconcile — and it was
hand-triggered, 53 cards, one box.

**Honest limit on the cadence figures.** They are photo **write** times, not shutter times —
the same instrument Gate B used. The interval between consecutive writes measures the cadence
only while encode-and-commit latency is roughly constant, which the zero-outlier count
supports and does not prove.

**`captured_at` is STILL whole-second, and the reason is worth more than the fix was.**
The paragraph this replaces said the millisecond stamp meant the next run would "measure
its own cadence instead of depending on that accident a second time". It depended on the
accident a second time. Every one of box 95's 85 records reads `T03:08:22+00:00` with no
fractional part, and the figures above came off APFS `st_birthtime` again.

The cause is not the code. `store/master.py:now()` was changed to milliseconds at 20:16
and the run was at 22:08 — **after** the fix. The server process serving it had been
started before 20:16 and was holding the old code in memory, which no commit can reach.
**A long-running `make server` outlives the fix that was written for it.** That is a
restart discipline, not a bug, and it belongs beside the money rules: restart the capture
server after any change under `store/` or `server/`, or the run you are about to do is
served by whatever was true when you started it.

**THE DISCIPLINE IS MACHINERY AS OF 2026-08-30, FOR ONE OF THE TWO WAYS TO START A SERVER
(D53).** `make up` runs the server under a supervisor that watches `server/`, `store/`,
`pipeline/`, `cli/`, `identify/` and `geometry/` and restarts it when they change, and
`GET /status` now carries a `boot_id` so a stale process is visible rather than inferred.
Re-scored against this section's own case: the millisecond change would have been picked up
in about a second, and the 22:08 run would have written the stamps the 20:16 commit intended.

**`make server` is untouched and the paragraph above still governs it in full.** It does not
watch anything, by choice — a foreground server in a terminal somebody is looking at is a
different tool from one that starts at login. So the rule is now: under `make up` the restart
is automatic, and under `make server` it is still yours to remember.

**None of the numbers above move.** They are evidence about a run on a date, and this file's
own rule is that evidence is never rewritten to match a later tree. Box 95's 85 records still
read `T03:08:22+00:00` with no fractional part, and the cadence figures still come off APFS
`st_birthtime`.

---
