### Gate B — 20-card end-to-end smoke test. PASSED 2026-08-22

**Passed with 53 cards, not twenty** — a pre-sorted lot of ME01 commons and uncommons,
fed by the feeder at manual-trigger pace, every card captured, identified, joined,
emitted, imported to Staged, and reconciled back in two clean round trips with zero
unmatched in either direction. The pull preview showed the right photo at the right
physical location, which was the last link in the chain. "No part of this repo has met a
card" was true when this section was written and is now false in the best way available:
**the project's first numbers about cards, rather than about itself, are below.**

**Identification on real rig photos: 53/53, but only once the frames were upright.** The
portrait-mounted camera (the right rig call — a portrait card fills the field) reaches the
browser as a landscape frame, and sideways cards were misread wholesale: 45 of 53 to the
review queue, names and numbers both garbled. The same frames rotated upright read 53/53
with zero low-confidence retries and zero detection failures. The fix is a capture-time
rotation setting; the A/B that convicted rotation was three frames, three perfect reads.

**Finish detection got a 53-card measurement instead of the planned ten photos: 16 of 53
normals read as foil (30% false-positive rate under the rig's lighting), and every one was
a real card a human then ruled on.** Detection agreed with itself across duplicate copies
— both Thievuls, both Eiscues, both Pyroars — so this is systematic sheen-under-lighting,
not noise: a rig finding, exactly as the paragraph this replaces predicted, and D3's
disagreement routing carried all 16 to a human instead of a wrong listing.

**The §10.2 measurements** (capture-app spec), from the corrected run: queue rate 16/53
(30%), all `metadata_detection_disagreement`, all parked (sub-threshold prices).
`no_catalog_row` fired 23 times against a commons-only export and zero times against the
full-rarity export — an export-scope artifact, not a pipeline one. Fired zero times:
`set_ambiguous`, `no_market_data`, `metadata_not_stocked`, `detected_finish_not_stocked`,
`ambiguous_no_signal`, `duplicate_condition`, `low_confidence`, `no_position`,
`identification_failed` — which fired only in the discarded sideways run — and
`card_not_detected`, whose zero says nothing about the owner's stock:
`pipeline/routing.py` defines the constant and nothing in `pipeline/`, `cli/` or
`identify/` ever assigns it, so it could not have fired in either run. Price distribution: $0.04–$0.40 across the run, median ≈ $0.10; the queue's
spread matched the run's, so the review screen's price-banded hierarchy has yet to be
tested by a mixed-value lot. The Fulfiller item was not exercised — no order existed.

**Six defects were found by the run and fixed the same day, three of them with a
regression test observed failing against the old code first:** the Batch API refusing the store's
`box/index` key as a `custom_id`; the capture screen leaking a 33 MB canvas per press;
Chromium idle-scheduling the JPEG encode into 1–7 s stalls a capture burst never gives it;
a re-routed position keeping its stale entry in the queue it left; review answers recorded
by the answer route that nothing on the join path ever consumed (now rung 0 of the
ladder); and a post-import re-emit that double-counted staged copies and regressed their
states. The first is why the run reached the API at all; the second and third are why
capture now sustains burst pace; the last three are why the queues, the answers, and the
import files survived contact with a second cycle.

**Three of the six carry no automated test, and that is recorded rather than rounded up.**
The cross-queue release leak has a T7 case; rung 0 and the re-emit double-count have a T3
case each — all three observed failing against the old code before the fix was restored.
The `custom_id` refusal, the canvas leak and the idle-scheduled encoder have none: `app/`
has no test runner outside the browser `make design-check` starts, and nothing under
`harness/` reaches `cli/cmd_identify.py`'s id translation. Each is guarded by a comment
beside the code and by nothing that runs, which is the weakest guard in this section and
the reason it is named here rather than left to be inferred from the commit stats.

**Box 1's records were deleted on 2026-08-24, and every number above stands.** Recorded so a
later session that goes looking for the 53 records does not conclude the run never happened.
The box was a shakedown lot the owner wanted gone, and it could not go: its 45 listing records
still claimed 53 staged copies and one live, so `box_not_empty_of_commitments` refused it, and
nothing in the repo could clear a staged count that never went live (D34 carries the mechanism).
The listings were released on the owner's word that TCGplayer held none of them — box 1 shared
no SKU with box 2, so every one of its 45 records went to zero and nothing else was reached —
and the box was then deleted whole — 53 records, 53 photographs, 53 sidecars, 16 parked queue entries and 53
cached identification answers. **The measurements in this section are evidence about a run on a
date and are not touched by it**, which is this file's own rule; what is gone is the inventory,
not the finding. The one thing no longer re-checkable by hand is the photographs, so nothing
above may be re-derived from them.

**What the gate did not close:** the owner had no visibility into emitted import files —
their names exist only in CLI output the owner never sees when someone else drives the
commands. Recorded in `docs/DECISIONS.md`'s Someday list with two more operations the run
surfaced (late re-shoot of a bad photo; a `removed` state for cards that leave inventory
without a sale).
