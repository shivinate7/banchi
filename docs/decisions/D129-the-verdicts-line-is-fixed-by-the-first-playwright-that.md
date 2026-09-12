## D129 — The verdict's line is fixed by the first Playwright that counts it right, and the rig's Node is not the thing that moves

**Settled 2026-09-10, the owner deferring to the session's recommendation after two rounds of**
**evidence.** A peer session reading `.serve/design-check.json` after a local red was sent to
`capture-claims.spec.ts:279` for a test declared at line 314 — thirty-five lines into the
previous test — and the runner's own reporter had named 314 for the identical file. The verdict
file carries that weight on purpose (`CLAUDE.md`'s `make design-check` paragraph), and it had
just pointed a reader at the wrong code.

### What was measured

**Same file, same pinned `@playwright/test` 1.55.1, same transform cache bypassed to a fresh**
**directory.** Under the rig's Homebrew **Node 25.9.0**, the suite reports the test declared at
314 as `:279` and the one at 816 as `:799`; under **Node 22.23.2** it reports 314 and 816, which
is what the runner printed. It is not one construct: three probes run for real under Node 25 —
five lines with nothing in them, and two with a template literal — all reported their test short
(`:2` for a declaration at 3), and the shortfall is not a constant (35 lines at 314, 17 at 816).
A first reading blamed a template literal's newlines on the strength of `playwright test --list`,
and a real run did not bear it out; the mechanism inside the transform was not characterized
further, because the ruling does not need it. 1.55.1 declares support for Node 18, 20 and 22;
nothing in this repo had ever said which Node it meant, and the runner's `setup-node` said 22 on
its own.

**Then the other direction was priced, and the first sweep measured the wrong shape.** A
five-line probe in a scratch project, run for real under Node 25 against each release after the
pin, reported the right line from 1.56.0 on — and the same probe inside `make verdict-selftest`,
on 1.56.0, was still short by one. The difference was `"type": "module"`: `app/package.json` is
ESM, `make verdict-selftest` copies that file, and the scratch project was CommonJS. Re-swept in the app's
shape: **1.55.1 counts right as CommonJS and wrong as ESM; 1.56.0 and 1.57.0 are still wrong as**
**ESM; 1.58.0 is the first release that counts an ESM spec right under Node 25, and every release**
**through 1.63.0 agrees.** The floor is three minors, not one, and the sweep that said one was the
kind of proof this entry exists to refuse.

### The ruling

**`@playwright/test` moves to 1.58.0 — the first version that fixes the named problem in this**
**repo's own shape, and not the latest — and the Node on the rig is left alone.** `scripts/screenshot.sh`'s constant moves
with it, by that file's own rule. It was proven before it was taken, which is the rule the memory
of PR #202 keeps: `make verdict-selftest` green under Node 25 and under Node 22, and the full
462-case `make design-check` green on the bumped suite.

**And `scripts/verdict-selftest.py` asserts the failing LINE, not only the file.** The arm
compares the verdict's `location` to the line the probe's own source declares the test on, and
the five-line probe it already had is enough — 1.55.1 reported it short like every other spec
tried. It is green on any Node now, and it is the guard: a future bump that brings the shortfall
back, or a Node a future pin does not support, fails there with the number in hand rather than in
a verdict somebody opens at the wrong line.

**The proof found one more thing, which is what a proof is for.** The first full run on 1.58.0
came back 461 of 462: `fulfillment.spec.ts`'s overshoot case — `Mark sold` may not occupy any of
`Pull`'s footprint — read `Pull`'s rect at a width of 427px in one run and 403px in the next, on
identical code, and the overlap it forbids appeared in two runs of five. A rect whose width
differs between identical runs is a frame of an animation: the panel enters on `bn-page-in` and
the replacing control pops on a spring, and 1.58.0's newer Chromium moved the timing enough to
catch a read that had always been early. `settleLayout` was built for that rule's own case — its
comment says so — and this was one of two tests that never called it. It does now, before each
read; ten of ten, then 462 of 462. No assertion moved.

### What was refused, and why

**Pinning the rig's Node down to 22.** It was the first ruling here, chosen from a list that did
not yet have the bump on it, and it was built: `.nvmrc`, `engines.node`, and the line arm red on
this Mac by design until the owner installed a second Node. It matched the runner exactly, which
was its whole virtue — and its whole cost was that it conscripted the owner's daily machine to fix
a defect that lives in a dependency this repo pins. A three-minor bump fixes the same thing for
anyone on any supported Node and leaves the laptop as it is. `.nvmrc` and `engines` are out
again: an `engines` field would claim a requirement that no longer exists, and an `.nvmrc` with
nothing to enforce it is a sentence in the wrong file.

**A location derived some other way in the reporter.** The reporter is faithful, `test.location`
is what Playwright gives every reporter, and a second source of truth for a line number is a
second thing to drift.

**The latest Playwright.** 1.63.0 also counts right, and taking it would have been the reflex
this repo already argued against once; the rule is the first version that fixes the named
problem, proven on a real run.

### What this does not do

**It does not change what D128 measured or fixed** — the flake's cause was in two effects and
is closed; this is the second defect the same investigation surfaced. **It does not say the**
**runner and the rig run the same Node.** They do not, and nothing here needs them to: what the
suite asserts is the same on both, which is the property `check.yml` already stands on.
