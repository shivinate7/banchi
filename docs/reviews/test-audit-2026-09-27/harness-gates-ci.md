# Test audit, slice 1: the harness, the gate records, CI, and the hooks

**Status: INPUT FOR AN OPUS REVIEWER, NOT A PLAN.** The owner asked for every test, harness
and gate to be audited before any resolution work starts, 2026-09-27. This file is factual.
It gives evidence and a first verdict per item. It does not decide what to cut or merge.
That is the next session's job, with the owner.

Head commit read: `103fde97` (branch `ux/pr4b`, this audit on `ux/test-audit-harness`).

No test file and no product file changed to write this. `make harness` ran once, to get
real timing and a real pass count. Its full output is not pasted below. Only the verdict and
the counts it printed are given here.

## Method

- Read `harness/run.py` whole (113 lines).
- Read every test module under `harness/tests/`, docstring first. Read its `NAME`, `DESCRIPTION`, and
  `PASS_CRITERIA`. Read its list of top-level functions. Did not read each full body, except
  where a section needed its own read.
- For T7 (38,949 lines, 149 `check_*` functions), grouped the functions by domain. The
  grouping used function names and the module's own section comments. This is a first pass.
  It is not an exhaustive taxonomy. An Opus reviewer should treat it as a start.
- Timed the whole harness once, wall clock. Timed each test module once more on its own.
  This gives a per-test cost the repo has never published.
- Read `docs/GATES.md`, `docs/gates/ORDER.json`, and every `_preamble.md` file under
  `docs/gates/` (156 lines total). Did not read every `gate-runs/` or `steps/` file. The
  stub already says which kind is history and which carries an open item.
- Read `.github/workflows/check.yml` (388 lines) and the first 200 lines of `demo.yml`
  (267 lines). Read `docs/specs/verification-cost.md` for prior timing.
- Read `.claude/settings.json`, `.codex/hooks.json`, and `scripts/stop-gate.sh` in full.
- Did not run a `git log --grep` search for every test name. 429 commits mention "harness"
  alone. That is too broad for this slice's budget. Where a test's own docstring names the
  defect it exists for, that note is used as evidence instead. T7 and T9 do this at length,
  in prose, at the point each section was added. That is stronger evidence than a commit
  search. It names the bug rather than a commit that touched the file for some other reason.
  Where no such note exists, this file says "unknown."

## Summary table

| Item | Size | Product or guard-of-guard | Decisions cited (spot-checked as current) | Cost | First verdict |
|---|---|---|---|---|---|
| T1 id eval | 728 lines, 4 checks | Product (model accuracy) | `D2, D23` | 0.0s replay (cached) | KEEP |
| T2 round trip | 224 lines, 26 checks | Product (byte format) | none named | 0.01s | KEEP |
| T3 join coverage | 3,606 lines, 391 assertions | Product (catalog join) | `D25, D35, D7` | 1.60s | KEEP |
| T4 variant ladder | 1,296 lines, 116 assertions | Product (pricing, routing) | `D3` | 0.03s | KEEP |
| T5 pricing | 645 lines, 96 assertions | Product (money rules) | `D9` | 0.00s | KEEP |
| T6 geometry | 523 lines, 36 assertions | Product, named blind spot | none named | 0.89s | KEEP |
| T7 store and seams | 38,949 lines, 149 fns, 4,568 assertions | Product (store, server, cli) | `D10, D20-D26, D29, D172`, ~20 more | **104.09s, 97% of the whole harness** | KEEP content. **SHRINK or SPLIT the file** |
| T8 codes | 370 lines, 47 assertions | Product, dormant feature | `D24, D70, C3, C9-C11` | 0.54s | KEEP |
| T9 traces | 769 lines, 1,187 assertions | Product (motion trigger) | `D81, D84, D130, D131` | 1.07s | KEEP |
| T11 walk plan | 647 lines, 75 assertions | Product (order-walk solver) | `D212, D220` | 0.00s | KEEP |
| `docs/gates/contract/` | 9 files, 1 preamble | Mirrors the harness's `PASS_CRITERIA` | a `docs-audit` row enforces it | n/a | KEEP, live |
| `docs/gates/gate-runs/` | 5 run files, 1 preamble | History only | none | n/a | KEEP, do not touch |
| `docs/gates/steps/` | 24 step files, 2 preambles | 3 items OPEN, rest is history | `D80` | n/a | KEEP, see finding |
| CI: `check` job | in `check.yml` | Product and guard-of-guard mix | — | ~164-188s locally | KEEP |
| CI: `revert-guard` job | in `check.yml` | Guard-of-guard | `D133` | fast, no venv, no node | KEEP |
| CI: browser matrix, 4 jobs | in `check.yml` | Product (what a browser draws) | `D136, D141` | ~117.5s locally, ~8.4 min on CI | KEEP |
| CI: `demo.yml` | 267 lines | Product plus a privacy guard | `D295` | unmeasured here | KEEP |
| Hook: `Stop` | 39 lines | Runs nothing | `D248` | 0s, disarmed | FINDING: `CLAUDE.md` is stale |
| Hook: `SessionStart` | 235 lines | Provisions env, no test | — | not timed | out of "runs tests" scope |
| Hook: `PostToolUse` | not read in full | Runs `tsc` on one file type only | — | not timed | KEEP |
| Hook: `PreToolUse` guards | not read in full | Guards, not tests | `D16, D127, D179, D135` | not timed | out of scope, flagged only |

---

## The harness tests

### T1 — Ground-truth ID eval

`harness/tests/t1_id_eval.py`, 728 lines.

**Protects:** that the model names the right card and the right join key. It reads real
photographs, not a hand-built fixture. A wrong ID ships a wrong card to a stranger.

**Product or guard:** product. It scores the model. Nothing else in the harness does that.

**Decisions:** `D2` (identification is Claude Haiku vision), `D23` (rarity claim). Both are
current per the `CLAUDE.md` decision index.

**Named blind spot:** it cannot validate `finish` (foil against normal). Official renders
are flat. Gate B measured a 30% false-positive rate on this, at the rig, 2026-08-22. T1
stays green through that gap. The gap is disclosed, not hidden.

**Last caught a real defect:** unknown. A commit-by-commit search was out of budget.

**Cost:** 0.0s in this run. `harness/.cache/` was copied in by `make worktree-setup`. The
test replays cached responses instead of calling the API. A cache miss would cost money.

**Overlap:** none. Nothing else in the repo scores model accuracy.

**First verdict: KEEP.** Cheap, product-facing, honest about its own blind spot.

### T2 — Fixture round-trip

`harness/tests/t2_round_trip.py`, 224 lines, 26 checks.

**Protects:** the exact byte format TCGplayer's Import to Staged accepts. Unquoted header.
Quoted data. CRLF line endings. A byte drift here means that every card in a send rejects.

**Product or guard:** product. It checks the writer's output against a byte-for-byte oracle.
The check uses a scanner that shares no code with the writer.

**Decisions:** none named in `PASS_CRITERIA`.

**Last caught a real defect:** unknown.

**Cost:** 0.01s.

**Overlap:** none found.

**First verdict: KEEP.** The smallest, cheapest test. One failure mode, one test.

### T3 — Join coverage

`harness/tests/t3_join_coverage.py`, 3,606 lines, 391 assertions.

**Protects:** every identified card matches a catalog row, or gets reported and queued.
Never a silent drop, in either direction. A card that vanishes from both is inventory
nobody knows is still owed a decision.

**Product or guard:** product, plus one named regression test. A v1 bug matched by
box-and-position. It silently skipped identified cards and reported nothing for unmatched
rows. The docstring names this directly: "a one-directional check passes on that bug."

**Sub-check groups**, from the function list:
- Core join and queue mechanics (4 functions).
- Game partition and number fold, read against real Riftbound and One Piece exports (2
  functions).
- Ranking and routing around the join (5 functions).

**Decisions:** `D25` (game partition), `D35` (name fallback), `D7` (duplicate
aggregation). All current per the decision index.

**Named synthetic gap:** the multi-set key-collision case is synthetic. The committed
fixture is single-set. A real cross-set collision does not exist yet to test against.

**Last caught a real defect:** the v1 bug above, named in the docstring, historical.

**Cost:** 1.60s.

**Overlap:** none found with T4 or T7. T3 is the join itself. T4 is downstream pricing and
variant resolution. T7's own store-backed join check reads the store directly, a different
path by the test's own naming.

**First verdict: KEEP.**

### T4 — Variant ladder

`harness/tests/t4_variant_ladder.py`, 1,296 lines, 116 assertions.

**Protects:** the four-stage finish ladder resolves in order. Capture metadata first, then
catalog force, then the model's finish field, then the review queue. The routing table
sends each confidence and price combination to the right lane.

**Product or guard:** product. A named v1 bug took holofoil, or reverse holofoil, or normal,
blindly. This test exists to keep that bug from returning.

**Named fixture gap:** no SV09 number carries all three condition rows at once. Part of
this test is a labelled synthetic three-row block. It reports the real gap on every run.

**Decisions:** `D3` (variant ladder), amended 2026-09-02. Current.

**Last caught a real defect:** the v1 bug above, named in the docstring, historical.

**Cost:** 0.03s.

**Overlap:** none found.

**First verdict: KEEP.**

### T5 — Pricing rules

`harness/tests/t5_pricing.py`, 645 lines, 96 assertions.

**Protects:** the rounding order (round first, clamp to the floor second), half-up
rounding rather than half-even, and the split between basis and threshold. The threshold
always reads market price.

**Product or guard:** product. Its own docstring states the cost of each mistake in money.
Reversing the basis-threshold split "delists half a box." A rounding slip costs one cent
per card, silently, in the house's favor.

**Decisions:** `D9` (threshold and floor, amended). Current.

**Last caught a real defect:** unknown.

**Cost:** 0.00s.

**Overlap:** none found with T3 or T4. This is pricing arithmetic alone.

**First verdict: KEEP.**

### T6 — Card geometry

`harness/tests/t6_geometry.py`, 523 lines, 36 assertions.

**Protects:** the crop-retry detector finds the card rectangle. It sweeps offset, scale,
and rotation. It refuses rather than guesses when it cannot find the card.

**Product or guard:** product, with the harness's most explicit self-declared blind spot.
The synthetic-composite premise failed on real photographs. `detect_card` found 0 of 53
real Gate B photos, 2026-08-22. A border-search fallback fixed it, and T6 now asserts that
fallback. The docstring states outright that a green T6 means that the geometry is
self-consistent. It does not mean that detection works.

**Decisions:** none named directly in this file.

**Last caught a real defect:** the 0-of-53 finding above. Recorded in the docstring and in
`docs/GATES.md`'s T6 section. Real, dated, historical.

**Cost:** 0.89s.

**Overlap:** none found.

**First verdict: KEEP.** One of the most honest tests here about its own limits.

### T7 — Inventory store, capture server, command seams

`harness/tests/t7_store_and_seams.py`, 38,949 lines.

**This is the largest single file in the repo by a wide margin.** It is also the dominant
cost of the whole harness: **104.09 of 107.37 seconds in this run, 97% of the total.** That
figure came from timing the module alone, then again inside a full `make harness` run.

**Protects:** the module calls this "bookkeeping and wiring," not rules. Where a card is
recorded. Whether a correction reaches the file identify actually reads. Which column a
price comes from. Its own docstring names the risk: a wrong rule gives a wrong answer you
can see. A wrong position gives a card that sits where the inventory says it does not,
found weeks later.

**Product or guard:** product. It is the only harness test that reaches `store/`,
`server/`, and `cli/`. Before it existed, those three packages held about 40% of product
code. The docstring says nothing checked any of it.

**Size, precisely:** 149 `check_*` functions. 4,568 individual assertions when run (the
harness's own line reads "all 4568 checks passed"). Its imports span `cli`, `identify`,
eighteen `pipeline` submodules, seven `server` submodules, and seven `store` submodules.

**Sub-checks, grouped by domain.** Grouped here from function names and the module's own
section comments. This is a first pass, not an exhaustive taxonomy.

| Group | Functions | What it is |
|---|---:|---|
| Allocator and store basics | 3 | position allocation, basic store I/O |
| Read-only open safety | 4 | concurrent-read races, WAL, corrupt files |
| Store of record | 1 | `D88`'s SQLite-is-truth rule |
| Photos | 4 | `D89`'s reclaim-on-sale, crop preview |
| Server routes and security | 5 | the CORS finding below is in this group |
| Undo and queues | 8 | `D10` undo, standing-queue mechanics |
| Remove, retire, reshoot, graveyard | 4 | `D26` terminal states |
| Listing release and withholding | 2 | `D34` |
| Review answers | 6 | `D4, D29`, the laundered-SKU finding below |
| Mark sold | 2 | `D57`, the bad-log finding below |
| History log | 5 | write-without-state-move logging, 2026-08-13 |
| Sidecar, capture-claim, multi-game seams | 3 | `D20-D25`, the sidecar finding below |
| Inventory filters, search, boxes | 14 | `D20` box object, `D145` bid, FTS5 search |
| Concurrency and app serve | 2 | `D53, D138` one-process rules |
| CLI seams and refusals | 2 | commands refuse rather than prompt |
| Code ledger, dormant feature | 2 | `C8-C11, D24`, 2026-08-23 |
| Identity and catalog matching | 4 | `D258` identity-follows-SKU |
| Preflight, run realignment, rescue | 10 | `D36, D145, D165` |
| Emit, claims, identity stamp | 10 | `D7` rewrite, `D147` |
| Pricing authority and corpus | 14 | `D86, D9` |
| Markdown, reprice, send press, review rounds | 18 | `D100, D283`, six are named `r3` through `r8`, one function per review round |
| Box views and value tables | 3 | `D236` |
| Listing commands, sections, pipeline routes | 7 | `D33` |
| Export fetch and key rotation | 2 | `D166`, the one real-subprocess test |
| Orders | 9 | `D193, D212, D220` |
| Price history and stock images | 2 | `D62, D301` |
| Shipping | 3 | `D61` |
| Supervisor recovery | 1 | `D175` |

**Three named regressions, quoted from the docstring:**

- **A CORS defect.** The server answered `Access-Control-Allow-Origin: *` on every route.
  That included `DELETE /inventory/<box>/<index>`. Any open browser tab could have spent
  the owner's inventory. `check_origin_gate` is called, in its own words, "the only
  security control this file watches."
- **The laundered SKU.** A stale, parked review-queue entry could authorize a SKU that no
  entry ever offered. Two queues' candidates were pooled together before this fix.
- **The bad log blocked a sale.** `do_mark_sold` reads `history.jsonl` to compute an undo.
  One bad line in that file used to take a sale down along with an unrelated reversal.

Two more sections are marked as regression tests, not new coverage, in `docs/DEBTS.md`.
A PUT that never reached the sidecar. A box filter that silently dropped a string-typed
record from the high-water scan.

**Decisions cited:** `D10, D20-D26, D29, D33, D34, D36, D53, D57, D61, D62, D86,
D88, D89, D100, D138, D145`. Also `D147, D165, D166, D175, D193, D212, D220, D236, D258,
D283, C3, C8-C11`. This slice did not check each one for being current, one by one. That
is a separate pass for an Opus reviewer to scope.

**Last caught a real defect:** the CORS bug and the two named regressions above are dated
and named in the file's own prose. This is the strongest evidence in the whole audit. The
author wrote the incident down at the moment the test was added.

**Cost: 104.09s alone, 97% of the 107.37s full harness run.** This is the largest single
finding in this slice. `docs/specs/verification-cost.md`, from 2026-09-17 and 2026-09-20,
recorded the whole harness at 21.75 to 24.4 seconds. This run measured 107.37 seconds. That
is four to five times higher, on a file that has grown since. This slice did not date that
growth.

**Overlap:** worth a direct check, not done here. `check_store_backed_join` in T7 shares
its name with a related check in T3. Otherwise T7 sits mostly apart from the other tests.

**First verdict: KEEP the content. SHRINK or SPLIT the file.** The density of named, dated
regressions per function is the highest in the harness. But one file of 38,949 lines and
149 functions, at 97% of the harness wall clock, is a structural problem on its own. That
holds apart from whether any one check is worth keeping. A split along the group
boundaries above would not remove coverage. It would make the cost attributable per
domain, not one lump. It would let a future session load one domain's tests, not 39,000
lines, to touch it. This is a recommendation for the Opus reviewer's plan. Nothing was
split here.

### T8 — Code cards

`harness/tests/t8_codes.py`, 370 lines, 47 assertions.

**Protects:** the QR round-trip, so every decode matches its own encoded string. The
reservation state machine, so no code sells twice. The product-tier lanes, so a premium
code never lands in a bulk lot.

**Product or guard:** product, for a feature marked DORMANT in `CLAUDE.md` since
2026-09-20. The owner has not used this feature yet. The harness test still runs every
time.

**Named limit:** every QR frame here is drawn by the test itself, from the card's known
geometry. No real code-card photograph has ever gone through this pipeline. None may ever
be committed.

**Decisions:** `D24` (pooled inventory), `D70` (the QR is the identification), `C3,
C9-C11`. Current per the dormant-feature section of `CLAUDE.md`.

**Last caught a real defect:** unknown. No incident is named in the docstring.

**Cost:** 0.54s.

**Overlap:** none found.

**First verdict: KEEP,** with a note for the Opus reviewer. This test's whole subject is a
dormant feature. It costs half a second, so cutting it saves nothing measurable. But the
owner may weigh a dormant-feature test differently, given the "anything mandating this
app" framing of the original request.

### T9 — Motion trigger against recorded rig sessions

`harness/tests/t9_traces.py`, 769 lines, 1,187 assertions.

**Protects:** that the motion trigger tells a card from an empty stand. It reads real
recorded rig sessions, not synthetic frames. Its opening line names why: two browser-side
motion specs stayed green through every version of the gate, including two that were
losing cards. They draw their own synthetic frames and can only ever agree with
themselves.

**Product or guard:** product. This is the sharpest self-critique of a synthetic fixture
in this whole audit. It exists because an earlier, all-synthetic suite could not fail on a
real defect.

**Named history:** twenty real recorded sessions, each tied to a dated finding. Five
sessions convicted the brightness-floor rule, replaced by `D81`. Three convicted the
stillness rule and presence floor, `D84`. Six convicted the noise tracker, `D131`. Six
more convicted a rule called `stillWindow`, the rescue. This test's whole fixture set is a
named incident history.

**Decisions:** `D81, D84, D130, D131`. All current.

**Last caught a real defect:** four separate defects, by its own account. Each is dated
and tied to a specific trace batch, listed above.

**Cost:** 1.07s.

**Overlap:** with two browser specs, `motion.spec.ts` and `motion-live.spec.ts`. T9's own
docstring says it covers what those two cannot. This is a stated complement, not overlap.

**First verdict: KEEP.**

### T11 — Order walk plan

`harness/tests/t11_walk_plan.py`, 647 lines, 75 assertions.

**Protects:** that the walk-plan solver proves its answer optimal. A fixture exists where
a greedy answer is provably worse. The solver handles multiplicities, so one copy in a
section never satisfies a demand for two. It routes an unfillable SKU to a shortfall,
rather than making the whole instance infeasible. It treats a pooled game as one un-boxed
stop.

**Product or guard:** product. The docstring frames the risk directly. A wrong plan is
"confidently wrong" in a way that renders exactly like a correct one. It is found only at
the shelf.

**Decisions:** `D212` (every copy fungible), `D220`. Current.

**Last caught a real defect:** unknown. This is a newer test, from 2026-09-17, for a newer
feature. No incident is named beyond its design reasoning.

**Cost:** 0.00s.

**Overlap:** none found. The solver has no other test.

**First verdict: KEEP.**

---

## The gate records (`docs/gates/`, `docs/GATES.md`)

Gating retired 2026-08-23, per `CLAUDE.md`. The stub, read in full, says this is now a
record. It is split into three kinds for a measured reason. Two-parent merges on the old
single file conflicted 79% of the time, 15 of 19. Branches appended to it concurrently.
This is the same failure `D160` already fixed for decisions.

### `docs/gates/contract/`

9 files plus one preamble, 29 lines.

**Live obligation.** Each file publishes one harness test's `PASS_CRITERIA`, word for
word. `harness/tests/__init__.py`'s own docstring names the mechanism. The test is the
source. The gate publishes it. Five of six drifted before anything enforced this.
`make docs-audit` now blocks a commit where a test's `PASS_CRITERIA` and its file
disagree.

**First verdict: KEEP.** This is a genuinely live, mechanized check. It is the one part of
`docs/gates/` that changes every time a test's threshold changes.

### `docs/gates/gate-runs/`

5 files plus one preamble.

**History only, and the stub says so directly.** Every number in these files is evidence
about a run that happened on a date. None of it is ever rewritten to match a later tree.
Gate A: the TCGplayer seam, 2026-07-26. Gate B: a 53-card smoke test, 2026-08-22, plus a
note on a 30% finish false-positive rate. Gate C: feeder integration, 2026-08-22, plus a
per-run reading note.

**First verdict: KEEP, untouched.** This matches the parent `CLAUDE.md` rule: a recorded
argument is never rewritten. Here it is a measurement, not an argument. Rewriting it would
be worse, not better.

### `docs/gates/steps/`

24 step files plus two preambles.

**Mixed.** The shipped list, 23 lines, is history. It orders the build order's completed
steps by landing date, never renumbered. The open list, 5 lines, names three unranked,
unblocked open items. `docs/map.py`'s own open list mirrors them, checked both ways by a
`docs-audit` row.

**First verdict: KEEP.** The three open items sit outside this slice's scope. They are
product roadmap, not test, harness, or CI work. An Opus reviewer resolving "what still
mandates this app" should know they exist and are not history.

---

## CI (`.github/workflows/`)

Two files: `check.yml` (388 lines) and `demo.yml` (267 lines). Both are self-documenting.
Most of what follows is stated in their own header comments, cross-checked against
`docs/specs/verification-cost.md`.

### `check.yml` — four jobs, and they do not duplicate each other

1. **`check`** runs `make ci-check` on a fresh Ubuntu runner. No venv, no cache, no image
   mirror, no demo recording. It runs on a pull request, on a push to main, and on a
   manual dispatch. The header names the reason it exists. A missing gitignored file made
   `make check` fail on every fresh checkout, main included, for 121 commits. Every Mac
   that ran it locally already had a leftover recording. This job would have caught that
   defect on commit one of the 121. **KEEP.**
2. **`revert-guard`** is `D133`'s guard, split into its own job. A refusal reads as itself
   there, not as one red line inside a longer run. This is the same check `make ci-check`
   already runs. But it runs on GitHub's real merge result, not a local dev tree.
   `verification-cost.md` counts 0 catches in 200 commits. But the one incident this guard
   exists for was found by a hand-walk, before the guard existed. **KEEP.** A near-zero-cost
   policy against a documented incident is not a cut candidate.
3. **The browser matrix** (`already-passed`, `browser-scope`, `design-check` in six
   shards, `design-check-passed`) is the Playwright suite. It sits outside `make check` on
   purpose. It starts a browser and a dev server, a different weight of check. Two skip
   conditions apply, and they never act on the same event. `already-passed` skips a push to
   main when this exact tree already passed on a pull request. `browser-scope` narrows which
   spec files run on a pull request, from a derived list. **Not a duplicate of the `check`
   job.** It asks a different question at a different cost. 12-15 minutes before sharding.
   About 8.4 minutes on CI after a fake-clock fix. Roughly 90 seconds for `check`. **KEEP.**

### `demo.yml`

Rebuilds and publishes the public demo from a scrubbed real store, `D295`. It runs on a
path-scoped push to main plus a manual dispatch. It runs its own coverage spec, a
determinism check, and a second privacy check, apart from the scrub already done on the
owner's Mac. **Not duplicated by the browser matrix in `check.yml`.** Different build.
Different spec file. Different purpose: does the published page show what a reviewer
would grade, not does every screen meet the Fulfillment floors. **KEEP.**

**No true duplication found across the two workflow files.** Both eventually run
Playwright against a built app. But they use different builds, different spec files, and
different triggers.

---

## Hooks (`.claude/settings.json`, `.codex/hooks.json`)

`.codex/hooks.json` mirrors `.claude/settings.json`, per `D135`. Spot-checked side by
side: `PreToolUse`, `PostToolUse`, `SessionStart`, and `SessionEnd` all match. Same
scripts, same matchers.

### Stop hook — `scripts/stop-gate.sh` (39 lines) — FINDING

**Runs nothing.** Read in full. The script's own comment states the owner's ruling,
2026-09-20, `D248`. The harness runs on the commit path and in CI only, never at turn end.
Every path through the file ends in `exit 0` with no test called, including its own escape
hatch. The script stays on the hook roster on purpose. A session asking "does anything run
at turn end" gets an honest answer instead of silence.

**This contradicts two sentences in the checked-in `CLAUDE.md`** at the root of this
checkout, loaded as context for this very task:

- "the Stop hook runs it at turn end," under the `make harness` command entry.
- "Run `make harness` before saying something works," in the Working agreement section.
  It reads as automatic, in context.

Both sentences describe behavior from before `D248`. **This is not a defect in the hook.
The hook matches `D248` exactly.** It is a stale sentence in `CLAUDE.md`. A future reader,
human or agent, could read it as "the Stop hook still gates on the harness." Nothing
mechanized catches this. It is prose, not a `governed_by` citation.

**First verdict: not a test to cut.** This calls for a one-line `CLAUDE.md` correction.
That is outside this audit's no-product-changes scope. Flagged here for the Opus
reviewer's plan.

### SessionStart hook — `scripts/worktree-guard.sh` (235 lines)

Provisions a fresh worktree's untracked state. Venv, `harness/.cache/`, and
`app/node_modules/`, through an APFS clone or a backgrounded install. **Runs no test and
no check.** It is infrastructure the harness depends on, not a gate itself. Confirmed by
running `make worktree-setup` for this task. It cloned `node_modules`, linked
`harness/images`, and copied `harness/.cache`, with no test execution. This sits outside
this audit's literal scope. It is named here since the brief asked for `SessionStart` by
name.

### PostToolUse hook — `scripts/typecheck-hook.py`

Not read in full this slice. Its own note in `.claude/settings.json` says it runs `tsc`
directly. It fires only when the edited file is `.ts` or `.tsx` under `app/`. It replaced
an earlier version that ran `make lint typecheck` unconditionally. That version blocked
nothing for eight days, because `lint` was a stub that always failed first.

**First verdict: KEEP.** Narrow and self-limiting by construction.

### PreToolUse guards — out of this slice's literal scope

`guard-opsec.sh`, `guard-shell.py`, `reap.py`, `silent-write-guard.py`, and
`decision-context.py`. None of these run a test or a product check. They refuse or advise
on an action about to happen, a write or a shell command. The brief asked for hooks that
run tests or checks. These are not that. Named here for completeness, not audited. A later
slice or the Opus reviewer may want them in scope, under the wider "anything mandating
this app" framing the owner used.

