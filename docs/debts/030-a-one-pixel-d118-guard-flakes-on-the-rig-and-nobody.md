## 30 — A one-pixel D118 guard flakes on the rig, and nobody had measured it

`app/tests/orders.spec.ts`'s `the sentence changing on a write moves no box row beneath it
(D118)` fails about a third of the time on this Mac. It is not skipped, not quarantined, and
not new — it is recorded here because it was measured for the first time on 2026-09-17 and the
number is worth having before someone reads a red run as a regression.

**What was measured.** Six consecutive runs of that one test, alone, on `a8808e56` — a
docs-only commit on top of `main`, so this is `main`'s own behavior and not a branch's:

    pass, fail, fail, pass, pass, pass

Three more runs on `af91e36b` gave pass, fail, pass. Every failure is the same one pixel:

    Error: the box list moved relative to the sentence above it
    Expected: 25
    Received: 26

**Why it matters more than one pixel does.** The test guards D118 — a press changes what is on
the screen and never where the rest of it is. It measures the GAP from `.orders-map-lede` to
`.orders-map-stops` across a re-read, rather than either box's page position, which is the
right measurement and is argued in the test's own comment. What it cannot currently do is tell
a real one-pixel reflow from its own rounding, because it compares `Math.round` of two
sub-pixel gaps that straddle a boundary. So the guard is live and is also, a third of the time,
wrong about a tree that is fine.

**How it was found.** Four branches were integrated on 2026-09-17. Each builder ran
`orders.spec.ts` green in its own worktree, and the merge of all four went red on this case. The
first reading was a regression from the combination. It was not: bisecting to each branch alone,
then to the base underneath them, found it failing on the base. **The lesson is the bisect, not
the pixel** — a flake found at integration reads exactly like a regression introduced by it, and
the only thing that told them apart was running the base.

**Why it is not fixed here.** The repair is a tolerance, and choosing one is choosing what size
of reflow this guard stops catching. A `toBeCloseTo` with a one-pixel band would make this test
green and would also make it blind to a genuine one-pixel shift, which is the smallest thing
D118 forbids. The honest fix is to measure the gap without rounding — compare the raw
sub-pixel values, or reserve the height in a way that cannot land on a half pixel — and that is
a change to `.orders-map-lede`'s own `min-height` reservation rather than to the assertion.
Neither was in scope for the undo build, and doing it under that build's name would have hidden
it. Named here instead.

**`make check` cannot see this.** The browser suite is not in `make check` or `make harness`
(DEBT16), so nothing on the commit path runs this test at all. It runs in `make design-check`,
which is deliberately off the commit path. A tree can be green on every gate in this repo with
this test failing.
