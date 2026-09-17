# Tiered verification: the measurements, the options, and what each would let through

**Status: PROPOSED, NOTHING CHANGED.** Raised by the owner 2026-09-17 — *"these tests are too
expensive."* This document exists to be ruled on. No verification target, no `make check`
roster entry and no CI file was touched in the session that wrote it.

Every figure below was taken on this Mac, in the worktree
`.claude/worktrees/festive-heisenberg-778f57`, on 2026-09-17, on a tree that was green.

---

## 1. The headline, first

**CORRECTED 2026-09-17, after the first version of this document was wrong.**

The first draft's headline was that a green `make check` costs about 213,000 tokens of
context, 40–68% of an agent round. **That is false, and it was never measured — it was
inferred from a byte count.** Measured afterwards: the Bash tool does not put a large output
into context at all. It persists it to a file and shows a **2 KB preview**. Probed directly:
a 51.8 KB output persisted, a 2.7 MB output persisted. `make check`'s 853,877 bytes and
`make harness`'s 577,405 bytes are far above that line, so **neither has ever entered an
agent's context whole.** The token saving claimed for quiet output does not exist.

**What is true about the output, and it is a smaller and different problem.** The preview is
the **first** 2 KB, and on a green run the first 2 KB is the header — `PASS T1`, `PASS T2`,
and the start of T2's field list. The verdict, `all 9 passed`, is the LAST line, and an agent
never sees it. To learn whether the run passed it must spend another turn: a `tail`, a `grep`,
or a read of the persisted file. **That is the real cost of verbose output here — extra turns
to find the answer, not tokens to read the noise.** It is worth fixing, and it is worth much
less than the first draft claimed.

**So the ranking of costs, corrected:**

1. **Rework rounds.** Three rounds lost to orchestrator error (§7), against a total evening of
   a handful of rounds. Measured as rounds, this is the largest item by a distance.
2. **Wall clock.** `make check` plus `make design-check` is **305 seconds** against rounds of
   **900–1,850 seconds** — at most **17–34%**, and only if a round runs everything once. The
   Stop hook already runs the harness silently and prints only 30 lines on failure.
3. **Orientation.** `app/src/Orders.tsx` is 4,605 lines, roughly 45,000 tokens to read whole,
   paid by every agent that touches `#/orders` and paid again on every retry. This is the
   largest measured TOKEN item that survives the correction.
4. **Turns spent finding a verdict in a persisted log.** Real, small, and cheap to fix.

The tiering question as posed — which checks to stop running — is aimed at item 2, the middle
of the list. Items 1 and 3 are larger and neither is a test.

---

## 2. Wall clock, per target

### The two composites

| Target | Wall clock | What it covers |
|---|---:|---|
| `make check` | **187.5 s** | 35 sub-targets, product first then guard selftests (D161) |
| `make design-check` | **117.5 s** | 648 Playwright cases over 26 spec files, 647 passed / 1 skipped |
| **both, once** | **305.0 s** | what a maximal agent round pays |

### Inside `make check`, ranked by cost

| Target | s | Target | s | Target | s |
|---|---:|---|---:|---|---:|
| serve-selftest | 70.12 | janitor-selftest | 4.63 | screen-freshness-selftest | 0.78 |
| harness | 21.75 | githooks-selftest | 3.48 | screen-freshness | 0.76 |
| reap-selftest | 15.04 | typecheck | 3.34 | cid-selftest | 0.43 |
| claim-selftest | 14.86 | silent-write-selftest | 2.53 | sigil-check | 0.20 |
| guard-shell-selftest | 12.11 | lint | 2.09 | ignore-check | 0.15 |
| docs-audit | 9.69 | verdict-selftest | 1.99 | set-hint-agreement | 0.14 |
| sync-selftest | 7.42 | vale | 1.72 | port-agreement | 0.13 |
| claim-stale | 6.22 | revert-selftest | 1.43 | revert-guard | 0.09 |
| audit-self-test | 5.04 | suite-lock-selftest | 1.32 | decisions/debts/gates/coordinator/readings/mutate-anchors | 0.05–0.08 each |
| merge-selftest | 4.46 | submission-selftest | 1.05 | | |

**Nine targets cost under a tenth of a second each.** Tiering them away saves nothing
measurable; any policy that drops them is trading real coverage for noise.

**One target is 37% of `make check` on its own**: `serve-selftest`, 70.12 s. It builds a
throwaway tree and exercises the supervisor's build job. It is also a target no UI change can
break. That is the single largest honest candidate for a tier.

### Individual, outside `check`

| Target | Wall clock | Output |
|---|---:|---|
| `make design-check PW_ARGS=tests/orders.spec.ts` | **11.8 s** (57 cases) | 252 bytes |
| `make mutate-guards` | **186.2 s** (28 mutations, 5 guards) | 3,420 bytes |
| `npx tsc --noEmit` (`make typecheck`) | 3.34 s | quiet |
| `make lint` | 2.09 s | quiet |
| `make docs-audit` (95 rows) | 9.69 s | 22,903 bytes |

---

## 3. The mutation tax is not what anyone thought

Repo practice is that each new assertion is mutated, re-run to confirm red, and restored.
Measured on `app/tests/orders.spec.ts`:

- one whole-file spec run is **11.8 s** for 57 cases;
- so one mutation cycle is roughly **15 s** of machine time including the edit and restore;
- seven new assertions — last night's count — is **about 105 seconds**.

**105 seconds is not the problem.** What the practice actually costs is *agent turns*: each
cycle is an edit, a run, a read of the result, and a restore, and each of those is a
round-trip with the full file in context. The machine time is negligible; the orchestration
time is not. Any saving here comes from batching the cycles, not from skipping them.

`make mutate-guards` already demonstrates the batched shape: **28 mutations across 5 guards in
186 seconds, reporting `28 killed, 0 survived, 0 stale` in 3.4 KB.** That is one command, one
result, no per-assertion turns. `make mutate-anchors` (0.05 s) verifies that all 28 anchors
still resolve, so the corpus cannot rot silently between runs.

---

## 4. Which targets actually catch things

Classified from the last 200 non-merge commits (commit-message evidence — a red target
usually names itself in the fix that follows). This ranks by *how often a target is the reason
a commit changed*, which is the nearest honest proxy for value:

| Target named in a fix | Commits |
|---|---:|
| docs-audit (any row) | 60 |
| harness (T1–T9) | 51 |
| design-check | 33 |
| lint | 22 |
| claim-stale | 15 |
| copy-budget (inside design-check) | 10 |
| mutate / mutation | 10 |
| `repo map` row specifically | 10 |
| typecheck | 3 |
| flake | 2 |
| revert-guard | 0 |

Two readings matter:

**`docs-audit` and `harness` earn their seconds.** Together 111 of the classified mentions, for
31 seconds combined. Best value per second in the repo by a wide margin.

**`revert-guard` has caught nothing in 200 commits — and should stay.** It costs 0.09 s, and
the one thing it guards against (a branch silently restoring a file main had changed) is
recorded in `docs/debts/` as having actually happened, found by a hand-walk, before the guard
existed. A zero-cost guard with a real historical defect behind it is not a tiering candidate.

**On flakes, and this is the part that argues AGAINST tiering.** DEBT8 records
`design-check` flaking around 1 in 13 runs. It also records a red `press floor`
case during PR #220's merge that was **called a flake and merged past, and was a real defect**.
The habit tiering encourages — "that red is probably noise, it only runs at merge anyway" — has
already cost this repo one shipped bug. A merge-time-only browser suite makes that habit
cheaper to indulge, not harder.

---

## 5. The citation tax, measured

`make docs-audit`'s `repo map` row blocked three commits in one evening for the same reason
each time: a file cited a decision id, and `docs/map.py` did not list that id under
`governed_by` for the file.

Measured:

- **112 of the last 200 non-merge commits touch `docs/map.py`** (56%).
- Across those commits, `docs/map.py` changed 2,620 lines, of which **416 are `governed_by`**
  — the single largest keyed field in the diff, ahead of `tested_by` (81), `does` (66) and
  `note` (16). That is roughly **two `governed_by` edits per commit**.
- Only **one** commit in the last 400 touched `docs/map.py` alone. The tax is invisible in
  history because the fix is amended into the same commit — which is exactly why it reads as
  friction rather than as work.

**And the rule is one-directional.** `scripts/docs-audit.py:5677`:

```
missing = cited_decisions(module_path) - declared - set(component.get("governed_by") or [])
```

The required set is *literally* `cited_decisions(path)`. Nothing about it needs judgement. A
human is being asked to retype, by hand, a set a regular expression already computes — and
`cited_decisions` is already written, already handles binary files and `# noqa` suppressions,
and is already the sole authority on the answer.

This one is not a policy question. It is a missing generator.

---

## 6. The options

### A. Tier by breakpoint — the owner's own idea

*Full `design-check` before merge to main; a narrower slice per agent round.*

- **Saving:** at most 117.5 s and 252 bytes per round. `design-check` is already quiet.
- **Cost:** a defect found only at merge costs a whole round to fix. Last night a
  `CopyMapView`/`WalkGroups` placement error cost exactly one round, and it is precisely the
  class a browser sweep catches and nothing else does.
- **Lets through:** every rendering defect, for the length of the branch.
- **Verdict: reject as stated.** It trades 117 seconds — 6–13% of a round — for a failure mode
  measured at one full round. The arithmetic is against it, and §4's flake-habit finding is
  against it twice.

### B. Scope the browser suite the way CI already does

*`scripts/browser-scope.py` (D141) gates the CI matrix on whether a change reaches what a
browser draws. Can a local equivalent pick the affected SPEC FILES?*

- `browser-scope.py` is **all-or-nothing by design**: it answers RUN or SKIP for the whole
  matrix, from a `SCOPE` list of paths the suite depends on. It has no source→spec mapping and
  was never meant to have one.
- A source→spec map would have to be written and maintained by hand. Its own header names the
  trap: *"a path filter that is too narrow silently stops testing something, and a gate that
  quietly stops running is worse than no gate: the green is believed."* `docs/debts/` records
  the same failure in `dry-run-blocklists-fail-open` and in the PW_ARGS word-splitting trap,
  where a spaced `--grep` silently ran the wrong specs and passed green.
- **Verdict: reject the mapping; adopt the cheap half.** One spec file runs in 11.8 s
  (`PW_ARGS=tests/orders.spec.ts`). An agent iterating on `#/orders` should run *that* while
  working, and the full 117 s sweep once before it reports. That is a habit, not a gate, and it
  leaves the gate exactly where it is.

### C. Auto-fix the citation bookkeeping

*Derive `governed_by` from the citations in the file.*

**D18 does not rule this out; it shapes it.** *A generator may write. Nothing that writes may
gate a commit.* Split the two roles, which the repo already does everywhere else:

- `make docs-audit`'s `repo map` row keeps its job unchanged: it **reads**, it **gates**, it
  **never writes**.
- A new generator — a `map-fix` target, calling the same `cited_decisions()` the row calls — writes
  the missing `governed_by` ids and **gates nothing**. An agent runs it when the row goes red.

Both sides then read one function, so they cannot disagree. Note the limit: it can only add
ids a file genuinely cites; it cannot invent the `does` or `note` prose for a new entry, which
is 82 of the 2,620 changed lines and is real work.

- **Saving:** roughly two hand-edits and, in the worst case, a blocked commit per commit, at
  56% of commits.
- **Lets through:** nothing. The gate is unchanged.
- **Verdict: adopt.** This is the highest-value item in the document and the only one with no
  coverage cost at all.

### D. Make the mutation requirement cheaper

*Per-assertion mutation as a recorded corpus, run periodically, rather than by hand each round.*

`make mutate-guards` is already that shape and already works: 28 mutations, 5 guards, 186 s,
`28 killed, 0 survived, 0 stale`, 3.4 KB of output. `make mutate-anchors` (0.05 s, in `check`)
proves the anchors still resolve, so the corpus cannot rot unnoticed.

The proposal is to extend the corpus to new assertions instead of mutating them by hand:
registering a mutation is one entry, and the batch run replaces N hand cycles with one command.

- **Saving:** the agent turns, which is where the mutation cost actually is. The 105 s of
  machine time is unchanged and was never the problem.
- **Lets through:** a new assertion between the moment it is written and the next corpus run —
  a real window. Close it by requiring the corpus entry in the same commit as the assertion,
  which `mutate-anchors` can already see at 0.05 s.
- **Verdict: adopt, with the same-commit requirement.**

### E. Reduce agent orientation cost

*`app/src/Orders.tsx` is 4,605 lines (57 top-level definitions) and every agent re-reads much
of it.*

Reading it whole is roughly 45,000 tokens — about 8–14% of a round's spend, paid by every
agent that touches `#/orders`, and paid again on every retry.

- **Splitting it** is a real refactor with real merge risk across parallel lanes, and it does
  not by itself tell an agent *which* piece renders the thing it was briefed about — which is
  the actual failure in §7.
- **A targeted index** — component name, line range, one line on what it renders and under
  which state — is cheap, is derivable from the file, and answers the question that cost a
  round last night.
- **Verdict: adopt the index, defer the split.** The index is worth more than the browser-suite
  tiering it would be traded against, and costs no coverage.

---

## 7. Orchestrator churn, not softened

A named share of last night's time was the orchestrating session's own error, not the suite.
Three cases, all real, each one a full round:

**1. Briefed against the wrong component.** The fix was written for `CopyMapView`; the screen
the owner looks at renders `WalkGroups`, and `hidePicks` suppresses the former in that state.
The work was correct and invisible.

> **Practice: identify the rendering component before writing the brief, and name it with the
> state that selects it.** Not "fix the walk sentence" but "in `#/orders`, with `hidePicks`
> true, `WalkGroups` renders the walk sentence — change it there." One `grep` for the state
> flag before the brief is written costs seconds and would have saved the round. Where two
> components can render the same thing, the brief says which one and why.

**2. Asked an agent to reconstruct a prior state.** It was told to produce a "before"
screenshot, went looking for a way to un-build its own change, reached for `git stash` — which
is forbidden in this shared worktree — and was killed by the owner.

> **Practice: never ask an agent to reconstruct a state it has already left.** A "before" image
> is captured before the edit or not at all. If a comparison is wanted after the fact, the
> orchestrator takes it in a separate clean checkout — never the working agent, never in a
> shared tree. `scripts/guard-shell.py`'s `PKMNSCAN_STASH` clause now refuses the specific
> command, but the brief should never have pointed an agent at the problem it solves.

**3. Fenced by file rather than by intent.** `WalkView`/`buildWalk` were fenced off to prevent
cross-order scope creep. The fence also enclosed the component that renders.

> **Practice: state fences by intent and name the exception.** Not "do not touch `WalkView` or
> `buildWalk`" but "do not change which cards a walk contains or how they are ordered —
> rendering changes inside `WalkView` are in scope." A fence drawn around files is a fence
> around a guess about which files matter; a fence drawn around behaviour survives being wrong
> about the layout.

On last night's evidence these three cost **three rounds** — comparable to, and plausibly
larger than, the entire verification bill for the evening.

---

## 8. Recommendation

Adopt four things, none of which reduces coverage. **Reordered after the §1 correction** —
the item that was first is now last, because its saving was the one that did not survive
measurement.

1. **The three brief-writing practices** in §7, and a generated component index for
   `app/src/Orders.tsx` (§6E). Items 1 and 3 of the corrected cost ranking. Largest saving in
   the document, and neither is a test.
2. **A `map-fix` generator** — deriving `governed_by` from `cited_decisions()`, gating
   nothing, per D18 (§6C).
3. **Extend the mutation corpus** to new assertions, with the corpus entry required in the same
   commit as the assertion (§6D). The saving is agent turns, which the correction did not touch.
4. **Put the verdict where a 2 KB preview can see it.** Not a quiet mode — the tokens were
   never spent. The narrow fix is that `make harness` and `make check` print their verdict
   FIRST as well as last, or that the working agreement tells an agent to run them with the
   output redirected and read the tail, which costs one turn instead of two. Small, cheap,
   and worth what it is worth and no more.

Reject the tiering as posed (§6A) and the per-spec local filter (§6B). One honest tiering
candidate remains and the owner should rule on it separately: **`serve-selftest`, 70.12 s,
37% of `make check`, and unbreakable by any change under `app/`** — moving it to the merge
gate alone would cut `make check` to about 117 s. It is offered rather than recommended,
because it is the one place in this document where a real second is bought with a real, if
narrow, coverage gap.

**Nothing above is implemented. The owner rules first.**

---

## 9. The owner's rulings, 2026-09-17

Taken in an interview after the §1 correction was on the table.

| Item | Ruling |
|---|---|
| Output work (§8.4) | **Parent rule only. No Makefile change.** The rule is repo-independent and goes in the parent `CLAUDE.md`, not here. |
| `map-fix` (§6C) | **Write the D18 amendment first, then build.** The seam entry is argued on its own terms and ruled on before any generator exists. |
| Path gating (§6B, §8) | **`serve-selftest` only, and revisit if the list grows.** A request for a second entry is evidence the policy is spreading and needs the owner's word again. |
| First build (§7, §6E) | **Both on one branch** — the three brief practices and the `Orders.tsx` component index. They are one failure seen from two sides: an agent that cannot find the rendering component. |

**What was rejected and stays rejected:** breakpoint tiering of `design-check` (§6A), a local
per-spec filter (§6B), and path gating as a general policy — nine targets in `make check` cost
under 0.1 s each, so 35 scope lists would cost more to maintain than they save, and every path
gate is another place a green can be believed over nothing.

---

## 10. What was built on the rulings, 2026-09-17

| Ruling | Landed as |
|---|---|
| Output: parent rule only | A prompt handed to the owner for `~/Developer/claude-settings/CLAUDE.md`. It carries the §1 correction, so the parent does not inherit the wrong number. **No Makefile change**, as ruled. |
| `map-fix` after a D18 amendment | D18 amended with its first seam entry — `docs/map.py` -> a module's `governed_by`, and nothing else. `scripts/map-fix.py` + `make map-fix`. |
| Path gating: `serve-selftest` only | **Not built.** See below. |
| Brief practices + `Orders.tsx` index | Three practices under CLAUDE.md's *Writing a brief*. `scripts/orient.py` + `make orient`. |

**`map-fix` is proved in both directions, not just asserted.** A `D111` citation added to
`pipeline/games.py` is exactly what the generator proposes and exactly what the `repo map`
row refuses, and both go quiet when it is removed. The generator imports the row's own
`cited_decisions()`, so the two cannot drift apart. It only ever adds. It is on no hook and
is a prerequisite of nothing, which is the whole of D18.

**`orient` answers the question that cost the round, in one command:**

```
$ make orient ARGS="app/src/Orders.tsx --name CopyMapView"
  CopyMapView  4131-4245  (115 lines)
                 drawn by OrderLineRow:4018
                   when  hidePicks || single || map.stops.length === 0 ? … :
```

It is a renderer — it writes nothing, gates nothing, and is derived on every run, so D18
does not reach it and there is no second index to keep true. It says in its own output what
it cannot see: no TypeScript parser is in the standard library, so a component reached
through a variable or a table is invisible to it.

**Splitting `Orders.tsx` is deliberately not done.** The seam is real — 1,285 of its 4,605
lines are pure helpers and types with no JSX, a clean lift to `orders/model.ts`. But the
split does not fix the defect that prompted it: an agent with `WalkGroups` in its own file
still does not know that `hidePicks` is what selects it. That is a relationship, not a
location. Judge the split later on whether `make orient`'s output got shorter, and treat it
as its own argument.

**`serve-selftest` path gating is BUILT, 2026-09-17.** `scripts/serve-scope.py` +
`make serve-scope`, and the `serve-selftest` recipe is its caller. It is the only path-gated
target in the repository, and its own header says so, because the ruling was this one and not
a policy.

- **The list is derived, not typed.** `SCOPE` stands against `serve-selftest.py`'s own
  `CARRY` — the literal list of what gets copied into the throwaway tree, which is the
  definition of what that test can observe. Three entries go beyond `CARRY` (the test itself,
  the classifier, and the `serve-selftest` recipe) and each carries a `beyond_carry` sentence.
- **It has a reader, in both directions.** `make docs-audit`'s new `serve scope` row: a
  carried name with no entry is a class of change the gate has silently stopped running for;
  an entry that is not carried and does not say why is a filter over something the test cannot
  see. It also checks the wiring, because a classifier nothing consults is a list, not a gate.
- **`app/**` is absent on purpose and the file says so.** The self-test writes a STUB `app/`
  and never copies this one. The day `CARRY` gains `app`, the audit row fails until `SCOPE`
  follows.
- **It reuses the matcher.** The globbing and the recipe narrowing are imported from
  `scripts/browser-scope.py`, whose `classify_paths` took three new defaulted parameters.
  Two copies of that logic would drift, and both would answer.
- **It fails open in every direction**: no merge-base, an unreadable diff, and an EMPTY diff
  all answer RUN, out loud. `PKMNSCAN_SERVE_SCOPE=off` runs it regardless and is printed in
  every skip.

**Proved on real commits, not only in the selftest.** Commit `37629dd6`, which touches only
`app/`, classifies SKIP (exit 3). This branch, which edits the classifier, classifies RUN
(exit 0). The hatch turns the skip back into a run. `make serve-scope-selftest` covers ten
classification cases plus the `CARRY` reconciliation and a drift it must catch.

**The saving is 70.1 s on any branch that does not reach the supervisor — `make check` at
about 117 s instead of 187 s.** On this branch it ran, correctly, and `make check` was 3m10.

**What it lets through:** a supervisor or build-job regression reaching `serve-selftest`
through something neither `CARRY` nor the three `beyond_carry` entries name. The audit row
exists to make that a failing commit rather than a quiet skip, and it is the only thing
standing between this gate and the failure every other path gate in this document was
rejected for.

