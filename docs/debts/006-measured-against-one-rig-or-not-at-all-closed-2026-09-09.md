## 6 — ~~Measured against one rig, or not at all~~ — CLOSED 2026-09-09, on the owner's word

**The provenance argument is retired and the measurements under it are not.** This section was
open on the ground that `detect_card`'s border search was scored against 53 photographs from one
camera position, one lamp, one afternoon and one set, and that closing it needed a second physical
run under deliberately different lighting plus a ruling on where rig photographs may live.

**The owner closed it directly, 2026-09-09**: the rig has been rebuilt and re-lit repeatedly since
2026-08-22 and the capture path has kept passing across those changes, so the "one rig state" this
section was written about has not existed for weeks. That is operator evidence rather than a
scored run — no second corpus was committed the way T1's score is — and it is recorded as what it
is. **The `--lighting` re-run this section asked for was never performed and is no longer wanted.**

**WHAT IS KEPT BELOW IS KEPT BECAUSE IT IS MEASURED AND BECAUSE A CHECK READS IT.** The 2026-09-05
corpus run is the only published account of `detect_card` over the owner's whole store, and
`make docs-audit`'s `detector standing` row reconciles five figures in it against
`harness/results/detect.json` on every run. Deleting the section takes that row's subject with it
and the check starts failing over a claim nobody removed on purpose — which is how the guard
reported it when this was first deleted outright. The `server/` subsection at the foot was never
about the rig at all and is untouched.

**The corpus figure this row reads is republished here rather than lost with the argument above**:
`detect_card` has been run over 1,625 photographs across six boxes, returning a box for every one
and refusing none, and the crop guard declined 59 — `harness/results/detect.json`.

**AND THE 59 DECLINED FRAMES ARE STILL NOT LOOKED AT.** That is the one thing here that was never
about lighting: a false ACCEPT is the dangerous direction and no statistic in that file can see
one. It is an eye pass over 59 named photographs, and closing this section does not do it.

### The re-measurement, 2026-09-05, and the 59 frames nobody has looked at

**`scripts/score-detect.py` exists now, so the paragraph above is re-runnable rather than a
one-off.** Over all 1,625 photographs in the owner's six boxes, `detect_card` returned a box
for every one and refused none, and the crop guard declined 59 — `harness/results/detect.json`.

**The declines are entirely boxes 3 and 4** (42 of 723, and 17 of 56). Boxes 5 and 6 were
captured after D75's fitting too and decline NONE, so the departure is not the rig moving,
which is the first thing a jumping rate would otherwise suggest.

**Both constants still sit exactly on the sample, and that is the finding.** Box 1's smallest
crop is `area 0.3002` against a `SMALL_CROP_AREA` of `0.30` — a margin of two ten-thousandths
— and box 1's `detail min` is `0.4376`, BELOW a `MIN_CROP_DETAIL` of `0.50`, so its crops
survive on the area leg alone. D75 wrote both down as fitted facts; this is the first time
they have been checked since, and both reproduce to the digit.

**WHAT IS STILL NOT MEASURED IS THE ONLY THING THAT MATTERS FOR CORRECTNESS.** A decline is the
SAFE direction — the whole frame is sent, which costs tokens and returns a correct answer. A
false ACCEPT is the dangerous one, and no count in that file can see it: a small crop that is
the whole card shot from far back is indistinguishable from a crop of the card's rules-text
panel to every statistic the script produces. **The 59 declined frames are named by box and
filename in the score file and have not been looked at.** Settling them is an eye pass over 59
photographs and nothing else will do it.

### What T7 leaves uncovered in `server/`

- **Twenty-way contention.** T7 runs two and four simultaneous captures, matching D5's two
  devices. The twenty-way case is what found `request_queue_size` at its default of 5 — 8
  served, 12 reset by the OS — and re-running it every turn buys nothing the smaller case does
  not. If that constant is ever lowered, nothing will notice.
- **The bare-interpreter start.** The server runs on system `python3` with no venv, which is
  what makes `python3` rather than `$(PYTHON)` correct in the Makefile. T7 imports the module
  under whichever interpreter runs the harness, so it cannot see this.

Both cost more at every turn end than they can return.

---
