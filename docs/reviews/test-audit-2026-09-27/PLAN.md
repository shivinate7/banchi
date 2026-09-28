# Test audit: the resolution plan

The Opus review of the four slices in this folder, 2026-09-27. The owner rules on the
questions below. Sonnet builders then run the lanes. This file changes no test and no product
code.

## Summary

**The verdict.** The product tests hold up. The bloat is not in what the tests assert. It is
in five other places:

1. **Idle time.** T7 spends about 30% of its run while its test servers stop.
2. **Whole-tree rescans on every commit.** Three docs-audit rows read the whole tree even when
   the commit touches one file. They are about 26 of the 29 to 34 seconds a commit waits.
3. **Standing noise.** Vale printed 1,668 errors that nobody acted on. Every commit printed
   30 advisory questions that nobody answered. Vale is retired 2026-09-27 (L3).
4. **Guards over things nobody runs.** The old invented demo seed no longer ships (D295). The
   heartbeat last ran on 2026-09-16.
5. **Process rows that block honest commits.** About 60 of the 109 docs-audit rows protect prose
   and repo process, not the product. They block at commit time.

**The slices were right to keep most items.** They were wrong in four places. T3 does not share
a check with T7. Nine of the eleven path-gate candidates cost less than 1 second each, so a gate
saves nothing. The pre-push header and CLAUDE.md both describe a GitHub setup that is no longer
true. The slices also missed the T7 idle wait, which is the largest single saving here.

### Totals

| | Today | After the plan | Source |
|---|---:|---:|---|
| Browser spec files | 44 | 43 | pull-confirm folds into fulfillment |
| Browser tests | about 1,071 | about 1,066 | DEBT45's count, minus pull-confirm's 5 |
| Harness tests | 10 | 10 | none cut |
| T7 checks | 4,568 | 4,568 | none cut |
| `make check` targets | 60 | 57 | vale, claim-stale, demo-determinism-selftest out |
| docs-audit rows | 109 | 108, or 92 with Q8 | entry budget cut, merges on Q8 |
| Advisory questions on every commit | 30 | 0 | entry budget cut, 2 breakpoint questions answered |

### Time

| Where | Today | After | How known |
|---|---:|---:|---|
| One commit (pre-commit hook, this file staged) | 31.3s and 34.3s | about 9s | measured today, estimate after |
| T7 alone | 99.9s | 69.8s, then lower | both measured, first step only |
| `make check`, a typical UX branch | about 218s | about 110s | sum of single-target timings, not one full run |
| CI `check` job, docs-only PR | 6m10s | about 3m40s | measured today, estimate after |
| CI `check` job, app PR | 9m16s | about 6m45s | measured today, estimate after |
| CI longest browser shard | 7m40s to 8m27s | unchanged until L7 | measured today |

At 2,652 commits in 30 days, about 88 each day, the commit saving is about 30 minutes of wall
clock each day. That figure is an estimate.

**One limit.** After the plan, an app PR's CI still waits on browser shard 2. Shard 2 was the
longest shard in both runs I read today. L7 measures why before anything changes.

### The owner's questions

Each has options and a recommendation in the "Questions" section below.

- **Q1.** Must process rows block at commit, block only in CI, or go?
- **Q2.** Must prose stop repeating code facts, so that the rows that police them can go?
- **Q3.** May `match-selftest`, a product test, join the path gate?
- **Q4.** Keep D215's per-spec narrowing, or remove it with its guard?
- **Q5.** Retire the guards over the old invented demo seed?
- **Q6.** Retire the heartbeat and its coordinator?
- **Q7.** GitHub's required checks are off. Enable them again, or correct the prose?
- **Q8.** Merge 16 similar docs-audit rows into 4? This cuts code, not time.

---

## Method

I read each slice by section. I tested each claim that moves a verdict against the code, git
and CI. I timed single targets. I did not run `make check`.

### Spot checks

| # | Slice claim | What I found | Verdict |
|---|---|---|---|
| 1 | T7 is 104s, 97% of the harness | T7 alone ran 99.9s here, "all 4568 checks passed" | holds |
| 2 | CLAUDE.md says the Stop hook runs the harness | The `make harness` comment in the Commands block still says so. `scripts/stop-gate.sh` runs nothing (D248). | holds |
| 3 | `scripts/catalog-index-selftest.py` claims `make check` | Its docstring says so. The `check:` recipe does not run it. | holds |
| 4 | 309 of 2,640 commits in 30 days mention docs-audit, 15 the bypass | 311 of 2,652, and 15, read today | holds |
| 5 | docs-audit costs 37.3s | 49.9s full here. 28.9s with `--staged` and nothing staged. | holds, and worse |
| 6 | `ste offenders` is not staged-scoped | Its docstring says it reads the whole tree, staged or not. It is 45% of a staged run. | holds |
| 7 | The make-targets row read "make capping" as a target | Only inside backticks. Plain prose and a quote block pass. | holds, narrower |
| 8 | guard-scope has 22 roster entries | 22 | holds |
| 9 | `check:` has 60 targets | 60 | holds |
| 10 | vale cannot fail | `--no-exit`. 1,668 errors and 558 warnings today, exit 0. | holds |
| 11 | T3 shares `check_store_backed_join` with T7 | Only T7 defines it | **false** |
| 12 | pre-push is the only branch protection | Its header says GitHub refuses protection. The repo is public now, and protection is on, with admins enforced. | **stale** |
| 13 | CLAUDE.md says `check` and `revert-guard` are required on GitHub | GitHub answers "Required status checks not enabled" | **false today** |
| 14 | Six specs each walk every route | All six loop over routes. Four call `routesFromNav`. | holds |
| 15 | pull-confirm duplicates fulfillment | pull-confirm tests one component in its gallery states, from step 6. fulfillment tests the real view. | holds |
| 16 | The 11 path-gate candidates are worth a gate | Nine cost 0.06s to 0.81s. A gate check costs 0.07s. | **no saving for nine** |

### New evidence the slices did not have

- **T7 waits on its own test servers.** 24 test servers call `serve_forever` with the default
  0.5s poll. Each stop waits for that poll. With a 0.02s poll, T7 ran 69.8s, not 99.9s, and
  all 4,568 checks passed. The send-press family is 64% of T7. In `check_send_hazards` alone,
  thread joins cost 6.7s and real CLI subprocesses cost 4.3s. Real work is about 1s.
- **Why main went red, 2026-09-13 to today.** 15 failed main runs of 128. Five were the
  docs-audit `id claims` row, a process row. Eight were `inventory.spec.ts`, two were
  `phone.spec.ts`. The harness caused none.
- **The path gates fail open on every push to main.** The diff is empty there, so every gated
  test runs. This is a useful backstop. It is the only place a gated guard still meets a new
  runner. Keep it.
- **This plan hit the friction too.** Its first staged draft was blocked. The make-targets row
  read a mutation example in the L2 proof as a real target. The same run printed the 30
  standing advisory questions.
- **The global STE gate already checks every Write and Edit.** The owner's own
  `ste_gate.py` hook refuses new STE errors at write time. The repo's `ste offenders` row
  repeats that check on every commit, over the whole tree.

---

## The lists

A "process" item protects the repo's prose or machinery. A "product" item protects what the
owner sees, what reaches TCGplayer, or what reaches a buyer.

### Cut

| # | Item | Protects | Argument | Decision it amends, quoted |
|---|---|---|---|---|
| C1 | `vale` out of `make check` and `ci-check` | process | It cannot fail. It costs 4.9s. It prints 1,668 errors nobody reads. The global STE gate covers new prose, retired 2026-09-27. | D161 lists it among "every check that reads the code and says something about it." |
| C2 | `claim-stale` out of `make check` and `ci-check` | process | 10.2s. `make merge` already runs `claim-ids.py --stale` (`scripts/merge-pr.py`). D140's title: the number is claimed at the merge. | D161, the same list. |
| C3 | `entry budget` advisory row | process | 28 standing questions on every run. Nobody acts on them. A guard that goes red when nothing is wrong is spent. | D60: "`entry budget` is **advisory**, printing and allowing." |
| C4 | `demo-determinism-selftest`, the demo.yml determinism step, `demo-freshness` | process | They test the invented seed. Nothing ships from it now. On Q5. | D295: "`make demo-determinism` still tests the OLD invented seed's determinism, not the mirror's." |
| C5 | `coordinator-selftest`, `scripts/coordinator.py`, `scripts/heartbeat.py`, `make heartbeat` | process | The heartbeat last wrote on 2026-09-16. Nothing schedules it. On Q6. | D200 and D171 argue the heartbeat. The lane quotes the sentences. |

### Merge

| # | Item | Argument |
|---|---|---|
| M1 | `app/tests/pull-confirm.spec.ts` into `app/tests/fulfillment.spec.ts` | pull-confirm tests the step-6 component. fulfillment tests the real view and names pull-confirm in its own header. Move each assertion that fulfillment lacks, then delete the file. |
| M2 | Six route walkers into one shared sweep | cursor, nav, phone, wide, page-edge and scaffold each walk every route. `app/tests/routeSweep.ts` already does this for the three copy checks. Keep every assertion. Pay for the walk one time. |
| M3 | 16 docs-audit rows into 4, on Q8 | Logo family (5 into 1). Vocabulary family: withhold, order, terminal statuses, pricing presets, reason codes, reason emissions (6 into 1). Line anchors trio (3 into 1). Pairs: env vars and env names, pass criteria and criteria wording, check numbering and numbering in code, column count and shipping columns, check census into check registry. This cuts code and printed rows. It saves no time. |

### Shrink or speed up, with no coverage lost

| # | Item | Argument |
|---|---|---|
| S1 | T7 idle waits | One shared test-server helper with a short poll. Measured 99.9s to 69.8s. Then profile the thread joins and CLI subprocesses in the send-press family. |
| S2 | `ste offenders` and `identifier spelling` read only changed files | D229: "each file's own ratio, against its own pinned ceiling. That is the whole gate." A file that did not change cannot change its verdict. Read the whole tree only when the linter, the offender list or the spelling table changes. About 23s per commit. |
| S3 | `spec map` runs only when `app/` or `scripts/browser-scope.py` changes | Its subjects live there. A docs-only commit skips 3.1s. If Q4 removes the narrowing, cut the row instead. |
| S4 | The make-targets row reads a code span only when the span starts with `make ` | It fixes the owner-quote false positive. A real reference starts with `make `. |
| S5 | DEBT47: the demo network seal | Replace the blanket seal and the stub with an allow-list that names one host. Refuse every other outside host. The owner already ruled this a debt. |

### Downgrade

| # | Item | Argument |
|---|---|---|
| D-1 | Process docs-audit rows: block in CI, not at commit, on Q1 | They keep main coherent. They do not need to stop an honest local commit. CI still blocks the merge. |
| D-2 | Prose-number rows, on Q2 | `route census`, `check census`, `derived numbers`, `duplicated measurements`, `work item standing`, `detector standing`, `router certainty`, `transport standing`, `not-built endpoints`. Delete the repeated number, then the row. D16 already says it: to keep one restated number honest "cost more machinery". |

### Path-gate

| # | Item | Argument |
|---|---|---|
| P1 | `browser-scope-selftest` (5.8s) and `port-slots-selftest` (4.5s) | Guard self-tests. Same shape as the 22 on the roster. CLAUDE.md: a new roster entry under this same gate needs no new word. |
| P2 | `match-selftest` (24.5s local, about 40s on CI), on Q3 | A product test, deterministic over what it imports. A docs or app-only branch cannot change its verdict. It is not a guard self-test, so it needs the owner's word. |
| P3 | No gate: the other nine candidates | `readings`, `skus`, the four `identity-*`, `coordinator`, `js-breakpoints` and `subagent-override` self-tests each cost 0.06s to 0.81s. The gate check costs 0.07s. No saving. |

### Fix stale prose (one line each, no ruling needed)

| # | Where | Fix |
|---|---|---|
| F1 | CLAUDE.md, the `make harness` comment in the Commands block | Delete "the Stop hook runs it at turn end". D248 moved the harness off turn end. |
| F2 | `scripts/catalog-index-selftest.py` docstring | Say it is not in `make check`, to match the Makefile. |
| F3 | `scripts/githooks/pre-push` header | The repo is public and GitHub protection is on. The local hook is now a fast first refusal, not the only one. |
| F4 | CLAUDE.md, the D42 paragraph, and the wait comment in `scripts/merge-pr.py` | Both say `check` and `revert-guard` are required. After Q7, make the prose match GitHub. |
| F5 | `scripts/guard-scope.py`, beside the roster | One comment: `guard-scope-selftest` is off the roster because a gate cannot skip its own proof. |

### Keep

Each group gives one argument. Every member keeps its current place.

| Group | Members | Why it stays |
|---|---|---|
| Harness, money and store | T3, T4, T5, T7, T11 | They prove the join, the variant ladder, the price rules, the store, the server, the send press and the walk plan. T7's docstring names real, dated defects: the open CORS gate, the laundered SKU, the bad log that blocked a sale. |
| Harness, format and capture | T1, T2, T6, T9 | Byte format, model accuracy, geometry, the motion trigger. Together about 2s. |
| Harness, dormant | T8 | 0.54s. CLAUDE.md keeps the code-card feature in the build and in working order. |
| Browser specs, screens | the other 42 spec files, after M1 | Each protects a screen the owner uses, named to a real defect in its header. They caused 10 of the 15 main reds. That is evidence they see real flicker. |
| Browser specs, copy checks | text-shape, machine-words, money-face | The owner's own D284 replacement. |
| Product checks in `make check` | lint, typecheck, screen-freshness, sigil-check, css-var-check, token-literal-check, kit-adoption, the three agreement checks, revert-guard, ignore-check | Each reads product code. Each costs less than 5s. |
| Product self-tests | submission, cid, pricearchive, archive-review, holdings, identity-checks, price-postings, product-history, sku-number-contradictions, readings, skus, the four identity-* | They prove store and pricing modules. The name says "selftest", but they test the product, not a guard. |
| Guard self-tests with a gate | the rest of the 22-entry roster, serve-selftest | They cost nothing on a branch that does not touch their subject. Main runs them all. |
| Guard self-tests, no gate, cheap | mutate-anchors, decisions, debts, gates, css-var-check, token-literal-check, kit-adoption and guard-scope self-tests | Each costs less than 1s. |
| docs-audit, product rows | claim decode, claim clients, threshold agreement, dist path agreement, import filename agreement, game vocabulary, matrix superset, join key shape, supervisor self-watch, motion params, export request, transport promise, hint reasons, raw color, breakpoints, js breakpoints, views opsec, views exposure (off), no mechanism on screen, typed interpunct, unscoped walk, import layering, identity writers | Code against code, or code against what the screen shows. A drift here reaches the owner or TCGplayer. |
| docs-audit, safety rows | spec seal, guard scope, serve scope, browser scope, subagent override, id claims | Spec seal keeps tests off the owner's live store. The scope rows stop a gate that would skip a needed test. `id claims` caught a half-landed claim twice today. |
| docs-audit, structural references | paths, allowlist, make targets (after S4), pkmnscan commands, decision ids, decision structure, decision index, debt ids, debt index, debts headings, env vars, harness tests, repo map | An agent acts on these references. A wrong one sends the next session to the wrong file. Cheap. |
| docs-audit, the rest | every row not named in another list | Kept for now. Q1 decides where they block. |
| Git hooks | pre-commit, pre-push (after F3), reference-transaction, post-checkout, post-merge | reference-transaction is the only guard on a local move of main. The rest are cheap. |
| Claude hooks | guard-opsec, decision-context, reap, silent-write-guard, guard-shell, typecheck-hook, worktree-guard, session-teardown, stop-gate | Each is tied to a named incident, or costs nothing. The Stop hook costs 0.006s (D248). |
| CI | check, revert-guard, the browser matrix, demo.yml | The gate before merge. |

---

## What each cut risks

| # | A defect that could slip through | What still catches it |
|---|---|---|
| C1 vale | A new spelling or style error in markdown | The global STE gate on every Write and Edit. Vale, retired 2026-09-27. |
| C2 claim-stale | A branch learns late that main took its number | `make merge` runs the same check. The `id claims` row. |
| C3 entry budget | A decision entry grows long | No automatic check. It printed 28 questions and nobody acted on one, so nothing is lost. |
| C4 demo seed guards | The invented seed stops being deterministic | No check. Nothing ships from it (D295). The mirror is committed, so it cannot drift between builds. |
| C5 heartbeat | Nobody watches the merge queue on a timer | `make merge` reads the queue itself. Nothing has used the heartbeat since 2026-09-16. |
| M1 pull-confirm | A button state in the gallery specimen breaks | fulfillment's view tests, after the move. The lane's mutation proof shows each moved assertion still goes red. |
| M2 shared sweep | A walker misses a route it used to reach | The lane's proof: the same assertion count before and after, per spec. |
| S2 scoped STE | A stale offender entry in an untouched file | The file did not change, so it cannot go stale. A change to the linter or the list reads the whole tree. |
| S3 scoped spec map | A docs-only change breaks the spec map | None found. The map reads only `app/` and `scripts/browser-scope.py`. |
| P2 match gate | A server change breaks search | The gate runs it on any branch that touches what it imports. Main runs it always. |
| D-1 CI-only rows | A prose error reaches a pushed branch | CI blocks the merge. A pushed branch is not main. |

---

## The lanes

Each lane is one builder. Each lane names its proof. When two lanes touch
`scripts/docs-audit.py`, the second waits for the first, so the two do not conflict.

| Lane | Tier | Needs | Work | Proof |
|---|---|---|---|---|
| **L1** T7 idle time | Sonnet | nothing | S1. Put the short poll in one helper that all 24 servers use. Then profile `check_send_hazards` and the `r3` to `r8` rounds. Cut each wait that is not the thing under test. | `make harness` still says "all 4568 checks passed". T7 time before and after, on one machine. Mutation: break one send-press refusal in `server/send_routes.py` and show T7 go red. |
| **L2** docs-audit per commit | Sonnet | nothing | S2, S3, S4. | The pre-commit hook timed on one fixed staged diff, before and after. Mutations, each red: a new semicolon sentence in a staged markdown file, a British identifier in a staged file, a changed linter rule (whole tree read), a code span that starts with make and names a missing target. Passes: the owner quote in backticks. |
| **L3** check composition and stale prose | Haiku | Q7 for F4 only | C1, C2, P1, F1, F2, F3, F5. Update `scripts/checks.py` and the CLAUDE.md check list to match the recipe. Amend the D161 list. | `make docs-audit` green, with `check registry` and `check census` both at 58. Each target with a gate prints SKIPPED on a branch that does not touch it. |
| **L4** spent advisories | Haiku | L2 merged | C3. Answer the 2 `breakpoint columns` questions in the code or the sheet. | `--staged` with nothing staged prints 0 questions. |
| **L5** demo seed guards | Sonnet | Q5 | C4. Amend D295. | A `demo.yml` dispatch on the branch builds and publishes nothing, because the Pages environment allows only main. |
| **L6** specs, fixes | Sonnet | nothing | S5 (DEBT47) and M1. | Spec count 44 to 43. The seal refuses a second outside host in a test. For each assertion moved from pull-confirm, a mutation in the component turns fulfillment red. |
| **L7** specs, one sweep and shard time | Sonnet | nothing | First read per-test durations from one CI run's Playwright report. Name what makes shard 2 slow. Then M2. | Per-spec assertion counts equal before and after. Shard times from two CI runs before and two after. |
| **L8** docs-audit merges | Sonnet | Q8, L4 merged | M3. | `make docs-audit` row count 108 to 92. `--self-test` green. For each merged family, one mutation per old row still goes red. |
| **L9** DEBT45 renderer | Sonnet | L6 and L7 merged | See below. | Output lists every spec, harness test and check target. A test header that cites a superseded decision shows a flag. |
| **L10** heartbeat retirement | Haiku | Q6 | C5. Record the deletion so `recorded deletions` watches it. | `make docs-audit` green. No file names the heartbeat except the deletion record. |
| **L11** match gate | Haiku | Q3 | P2. | On a docs-only branch, `match-selftest` prints SKIPPED. On a branch that touches its subjects, it runs. |
| **L12** where process rows block | Sonnet | Q1, Q2, L2 merged | D-1 and D-2 as ruled. | The pre-commit hook time on the L2 diff. A process-row defect passes the hook and fails `make docs-audit`. |

**Parallel now, with no ruling:** L1, L2, L3 (without F4), L6, L7. They touch separate files,
except that L3 and L2 both touch the docs-audit census rows. L3 lands first.

**After a ruling:** L5 (Q5), L10 (Q6), L11 (Q3), L8 (Q8), L12 (Q1, Q2).

---

## DEBT45: the page that cannot go stale

**The primitive exists.** `make explain` (`scripts/checks.py`) already renders the
`make check` targets from a registry that docs-audit reconciles.

**The cheapest form that cannot go stale is a renderer, not a page.** Extend `make explain` to
read two more sources, every time it runs:

- Each spec file's header comment, first sentence, plus each `test(` title, grouped by the
  route hash the spec names.
- Each harness test's `NAME` and `DESCRIPTION`.

It flags each decision id that a header cites when `scripts/decisions_corpus.py` marks that
entry superseded. It writes nothing. It is derived every run, like `make orient`. So no
committed page can drift. When the owner asks, a session renders it and publishes it
privately.

**What it cannot see.** DEBT45's second flag: a test that asserts text or layout the owner has
since changed. A machine cannot tell an intended change from a regression. That flag stays a
job for a reader.

**One rule keeps it honest.** Every spec header starts with one sentence that says what the
spec protects. The slices found that all 44 headers already do this. No new row is necessary.

---

## Questions

**Q1. Where must process rows block?** About 60 docs-audit rows protect prose and repo process.
Today they block at commit time (D16: "run by the pre-commit hook"). D173 made every rule
mechanical.

- A. Keep as today.
- B. Block in CI only. The commit stays fast and honest. Main stays coherent.
- C. Cut them.

Recommend **B**, after L2 lands. B keeps D173's enforcement and removes the local friction.

**Q2. Must prose repeat code facts?** Nine rows exist to keep numbers in prose true: route
counts, the check list, repeated measurements.

- A. Keep the numbers and the rows.
- B. Delete each number that a command already prints, then delete its row.

Recommend **B**. Keep the "things you will get wrong" facts in CLAUDE.md. Those protect the
owner's live server.

**Q3. May `match-selftest` join the path gate?** It is a product test, 24.5s here and about
40s on CI. D247 argued the gate for guard self-tests only.

- A. No, it runs every time.
- B. Yes. It runs when a branch touches what it imports, and always on main.

Recommend **B**. The test is deterministic over its imports.

**Q4. D215's per-spec narrowing.** D215: "It would have narrowed the spec list on 6 of 30, with
a median saving of 0 specs." Its guard costs 3.1s per commit (`spec map`) and 5.8s per check
(`browser-scope-selftest`).

- A. Keep it.
- B. Measure again over the last 30 PRs first, then decide.
- C. Remove the narrowing. Keep D141's skip of the whole matrix.

Recommend **B**, then **C** if the median is still 0.

**Q5. The old invented demo seed.** D295 kept it "for anyone who wants a store with no real
photographs". Its determinism guards still run in `make check` and on every demo push.

- A. Keep all.
- B. Keep the generator on demand. Cut its guards.
- C. Retire the invented flow.

Recommend **B**.

**Q6. The heartbeat and its coordinator.** Last run 2026-09-16. Nothing schedules them.

- A. Keep.
- B. Retire them.

Recommend **B**.

**Q7. GitHub's required checks are off.** CLAUDE.md and `scripts/merge-pr.py` both say `check`
and `revert-guard` are required. GitHub says "Required status checks not enabled". When
`make merge` finds no required check, it waits for every check, so its merges stay safe. The
web merge button does not wait.

- A. Enable required checks in GitHub again. This is yours to do. An agent may not change
  repository settings.
- B. Leave them off. Correct the prose.

Recommend **A**. It is the one gate that stops a red merge from any door.

**Q8. Merge 16 similar docs-audit rows into 4?** It cuts code in a 21,814-line file. It
saves no time.

- A. Yes, as L8.
- B. No.

Recommend **A**, last, after L2 and L4.

---

## Unknown

- Per-row friction for docs-audit. No log records which row blocked which commit. The two
  counts above are the only reliable ones.
- Per-spec and per-test cost. L7 reads it from a CI report.
- The full `make check` time today. I did not run it. The figure above is a sum of parts.
- The CI saving for each lane. Each figure above is an estimate from local timing.
