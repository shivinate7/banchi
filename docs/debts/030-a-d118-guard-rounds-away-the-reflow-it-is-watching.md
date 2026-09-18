## 30 — A D118 guard rounds away the reflow it is watching for, and the reflow is real

`app/tests/orders.spec.ts`'s `the sentence changing on a write moves no box row beneath it
(D118)` fails intermittently — about a third of the time on the rig, and once on CI in
`design-check` shard 2 on 2026-09-17. **The first reading was a flaky guard over a sound tree.
That reading was wrong, and the correction is the entry.**

**What was measured.** The assertion compares `Math.round` of two sub-pixel gaps. Printing the
raw values instead, four runs on the integration branch:

    before=25.42  after=26     drift=0.577
    before=25.39  after=26     drift=0.607
    before=25.39  after=26     drift=0.615
    before=25.31  after=25.36  drift=0.053

And four on `a8808e56`, a docs-only commit over `main`, so this is `main`'s own behavior:

    before=25.36  after=25.44  drift=0.076
    before=25.48  after=25.39  drift=0.088
    before=25.40  after=26     drift=0.604
    before=25.32  after=26     drift=0.681

**`before` is stable at about 25.3 to 25.5 every single time. `after` is either the same, or
exactly 26.** That is not noise. Something in the re-read intermittently lands
`.orders-map-stops` a whole pixel down and on an exact integer, and D118 forbids precisely
that: a write changes what the sentence says, and the box list beneath it moves.

**So the guard is right and its arithmetic is wrong.** Rounding two sub-pixel gaps is both too
loose and too tight. `25.4` against `26` rounds to `25` against `26` and fails, correctly but
for the wrong reason. `24.6` against `25.4` both round to `25` and pass, hiding a drift of 0.8.
The test catches the real defect roughly a third of the time, by luck of which side of a half
pixel each reading falls on, and reports it as a one-pixel rounding disagreement rather than as
the reflow it is.

**The repair is two things and neither is a tolerance.** First, compare the raw gaps with a
sub-pixel bound — strictly TIGHTER than the present rounding, which already permits almost a
whole pixel of real drift. Second, and this is the actual defect, find what makes `after` land
on exactly 26. An exact integer after a re-read, against a fractional value before it, reads
like a different layout path rather than a rounding difference — a font metric settling, or
`.orders-map-lede`'s reserved `min-height` resolving differently on a fresh mount.

**Why it is not fixed here.** It was found while integrating the undo build (`docs/specs/undo.md`)
and it belongs to neither that spec nor any of its four sections. Fixing a real `#/orders`
reflow under the undo build's name would bury it. The owner has the measurement and the
recommendation.

**How it was found, which is the transferable part.** Four branches were integrated. Each
builder's own suite was green and the merge went red on this one case, so the first reading was
a regression from the combination. Bisecting to each branch alone, then to the base underneath
them, found it failing on the base. **Then the second reading — "a pre-existing flake" — was
also wrong**, and only printing the raw numbers showed why. A rounded assertion tells you two
integers disagreed. It does not tell you whether the tree moved.

**Nothing on the commit path runs this test.** The browser suite is out of `make check` and
`make harness` (DEBT16). It runs in `make design-check`, which is deliberately off the commit
path. A tree can be green on every gate in this repo with this failing.
