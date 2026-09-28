# docs-audit row tiers, proposed

Owner's ruling on Q1 (`docs/reviews/test-audit-2026-09-27/PLAN.md`): sort each row by the harm
it catches. An agent proposes the tier per row. The owner approves. This file changes no
check. It is the proposal.

Source: `docs/reviews/test-audit-2026-09-27/docs-audit.md` and `PLAN.md`, read at commit
`0506501a` (branch `ux/pr4b-Q1tiers`, off `ux/pr4b`). `python3 scripts/docs-audit.py --json`
ran once on this tree: 108 rows in full mode, matching the input file. The run printed no
per-row timing. Per-row cost below comes from `docs-audit.md`'s own profiled Cost table,
which measured only four rows by name. Every other row's cost is a bound, not a
measurement, marked with an asterisk and explained in the Method section.

## The three tiers

- **TIER 1**, block at commit. Fast (well under a second). Stops a doc from sending a
  person or an agent to a wrong command, path, route, or target.
- **TIER 2**, block in CI. Keeps two artifacts, rosters, or lists agreeing with each other.
  Main must stay coherent. A commit need not wait.
- **TIER 3**, a note printed once in CI, never blocking. Style or prose. Failure harms no
  action.
- **CUT**, delete the row. Q2: the owner said yes to deleting prose that repeats a number a
  command already prints, and its row, together.

## Counts

| Tier | Rows |
|---|---:|
| 1 (block at commit) | 65 |
| 2 (block in CI) | 22 |
| 3 (note in CI, or candidate cut) | 13 |
| CUT (Q2) | 9 |
| **Total** | **109** |

## Counts, as landed (L12, 2026-09-28)

The table above is the original proposal. L8 merged 16 rows into 4 families, 109 to 93.
Q2's nine cuts landed, with rows 20 and 48. The debt48 lane added `numbered record growth`. L12 wrote
every remaining row's tier into `scripts/docs-audit.py:TIER`. Recounted from that dict:

| Tier | Rows |
|---|---:|
| 1 (block at commit) | 55 |
| 2 (block in CI) | 19 |
| 3 (note in CI, and `coupling` runs only on a staged diff) | 11 |
| **Total** | **85** (a full run prints 84) |

`coupling` sits outside this count. It is staged-only and already advisory. It runs only
inside `--staged` mode, never through the tier gate. L12 leaves its behavior unchanged.

## Commit-hook time, measured (L12, 2026-09-28)

**Measured, not estimated.** `ste offenders` is already gone (L2 cut it). L12 applies the
tier column. The pre-commit hook now calls `python3 scripts/docs-audit.py --staged
--commit`. That flag skips every Tier 2 and Tier 3 row's computation entirely. Each one
never runs and never prints, leaving the 55 rows now tiered 1 (of 85 total; the counts
above predate L8's merges and the Q2 cuts, both landed before L12).

Method: the same 5-file staged diff (CLAUDE.md, README.md, docs/map.py,
docs/specs/order-pipeline.md, and DEBT6's own file — this lane's own prose edits, 64
insertions, 78 deletions) staged in two trees: a `git worktree add --detach` at
`262f3351` (this branch's parent, before L12) for "before", and this branch for "after".
Three runs each, `/usr/bin/time -p`:

| | Command | Runs (s) | Mean |
|---|---|---|---|
| Before | `python3 scripts/docs-audit.py --staged` (262f3351) | 8.62, 8.60, 8.68 | 8.63s |
| After | `python3 scripts/docs-audit.py --staged --commit` (this branch) | 6.10, 6.13, 6.14 | 6.12s |

**About 2.5s faster, 29%, on this diff.** That is smaller than the "31s to 9s" figure in
PLAN.md's own Time table, because that figure compared against a PRE-L2 baseline
(`ste offenders`, `paths` and `spec map` all unscoped). L2 already cut most of the fat this
commit-time figure once had. What is left at Tier 1 is 54 real product- and structure-facing
rows, most cheap alone (`cProfile` on the after-run: `sole reader` 1.10s,
`identity writers` 0.98s, `views opsec` 0.67s, `id claims` 0.63s, `decision ids` 0.57s — no
single row is slow, the total is 54 rows' sum). A commit that touches none of `env
vocabulary`'s, `identity writers`'s or `sole reader`'s subjects narrows further; this
measurement did not isolate that case.

## Method

1. A row whose cost `docs-audit.md` measured by name at one second or more never gets
   Tier 1, whatever harm it catches. `ste offenders` (18.09s), `paths` (5.95s),
   `identifier spelling` (5.91s), and `spec map` (3.15s) are moved to Tier 2 or 3 on cost
   alone.
2. A row that already never blocks (severity `advisory` in the tool's own output) goes to
   Tier 3. It already behaves like a Tier 3 note. Moving its print from every local commit
   to once in CI removes standing noise without losing the finding.
3. Every `PRODUCT`-category row stays Tier 1, unchanged. This covers code-to-code and
   code-to-screen agreement: money constants, routes, breakpoints, storage keys, the logo,
   motion, and the review-reason and order-status vocabularies. The six rows `PLAN.md`
   names as "safety rows" also stay Tier 1: `spec seal`, `guard scope`, `serve scope`,
   `browser scope`, `subagent override`, `id claims`. These were never the "~60 process
   rows" this exercise is about. The one exception: a row Q2 names is CUT regardless of
   category.
4. The nine rows Q2 names (a published number a command already prints) are CUT:
   `route census`, `check census`, `derived numbers`, `duplicated measurements`,
   `work item standing`, `detector standing`, `router certainty`, `transport standing`,
   `not-built endpoints`.
5. What is left, the true "rest," is split by what a wrong entry actually does. A row
   whose finding is one literal string a person or an agent would use next (a `make`
   target, a `./pkmnscan` subcommand, a `D<n>`/`DEBT<n>` id, a harness test id, an
   allow-list entry) is Tier 1. A row whose finding is that two machine-read artifacts, a
   roster, a map, or a registry, drifted apart from each other is Tier 2.

Cost marked `~0.1s*` below is not individually measured. It is bounded by the shared
~14.1s remainder over 101 rows in `docs-audit.md`'s Cost section, average about 0.14s.
Treat it as "well under a second, on the evidence available," not a per-row reading.

## Rows I was unsure about

| Row | Both options | My lean |
|---|---|---|
| `paths` | Tier 1 (the clearest "wrong path" row, and `PLAN.md` calls it foundational), or Tier 2 (5.95s measured, fails the speed rule as written) | Tier 2, on the speed rule as given |
| `hook roster`, `codex hooks`, `map sections`, `gates structure`, `build order mirror` | Tier 1, grouped with `repo map` as one "map entries exist" family (all cheap, all the same shape), or Tier 2, as classified (bookkeeping between two files, not a command a session runs) | Left at Tier 2, flagged since `repo map` itself sits at Tier 1 for the same shape of harm |
| `recorded deletions` | Tier 1 (real named catch, PR #221's silent D119 regression), or Tier 2 (cost not measured, scans 243 files, could exceed a second) | Tier 1, for the real catch, pending a real timing |
| `entry budget` | Tier 3 (advisory, never blocks, as classified), or CUT (28 questions, unchanged for a while, nobody acts on one; `docs-audit.md` calls it "a guard that goes red when nothing is wrong is spent") | Tier 3 as classified. CUT was not asked of me directly, only Q1 and Q2 were ruled, so I left it as the smaller change |
| `line anchors` trio | Split as classified (`line anchors` Tier 1, `line anchor allowlist` Tier 1, `line anchor offenders` Tier 3), or demoting all three together, since CLAUDE.md's own hard rule already calls line citations a defect class | Left split, since `line anchors` alone still catches a citation past a file's end today |
| `shell substitution` | Tier 1 (stops an accidental command execution, a real "wrong action"), or Tier 2 (it reads scripted files, not a doc reference, so it may not fit this exercise's framing) | Tier 1, the harm is real even if the shape is unusual |
| `env names` | Tier 1, extending `PLAN.md`'s explicit "env vars" placement to its mirror direction, or leaving it in "the rest" for a fresh Tier 2 call | Tier 1, for consistency with its pair |

## All 109 rows

| # | Row | Tier | Harm it catches | Cost | Reason |
|---|---|---|---|---|---|
| 1 | `paths` | 2 | A backticked path that does not resolve sends a reader to a missing file. | 5.95s (measured) | Real harm, but too slow for Tier 1. CI still catches it before merge. |
| 2 | `allowlist` | 1 | A stale exemption hides a problem that is already fixed. | ~0.1s* | Tiny list (26 entries), fast, direct. |
| 3 | `line anchors` | 1 | A `path:N` citation points past the file's end, or into a stub. The reader lands on the wrong line or nothing. | ~0.1s* | Fast, real wrong-target harm today, even though the citation style itself is disfavored. |
| 4 | `line anchor allowlist` | 1 | A stale anchor exemption hides a citation that is already fixed. | ~0.1s* | Tiny list (10 entries), same hygiene as `allowlist`. |
| 5 | `line anchor offenders` | 3 | Nothing new beyond `line anchors`. Only stops the count of an already-disfavored citation style from growing. | ~0.1s* | A no-growth ratchet, not a fresh wrong-action check. |
| 6 | `derived numbers` | **CUT (Q2)** | A hand-typed figure in prose drifts from the tree. | ~0.1s* | The figure is a number a script can already print. |
| 7 | **make targets** | 1 | A `make X` in a doc names a target that does not exist. The reader runs a dead command. | ~0.1s* | Direct wrong-command harm. Real past incident (`.PHONY` drop hid `make harness`). |
| 8 | **pkmnscan commands** | 1 | A documented subcommand is not registered, or a registered one is undocumented. | ~0.1s* | Direct wrong-command harm, tiny roster (14). |
| 9 | `harness tests` | 1 | A cited test id (a T-number) is not real, or a real one is undocumented. | ~0.1s* | Test ids are cited constantly. Cheap. |
| 10 | `pass criteria` | 2 | GATES.md's record disagrees with the code's own pass line. | ~0.1s* | Keeps the audit trail honest. Not something a session acts on mid-commit. |
| 11 | `criteria wording` | 2 | The published criterion wording drifts from the code, same subject as `pass criteria`. | ~0.1s* | Same family. |
| 12 | `criteria evidence` | 2 | A gate's named evidence field is not the field the scored result actually used. | ~0.1s* | Same family. |
| 13 | `evidence freshness` | 3 | Already advisory. Examines nothing outside `--staged`, by design. | ~0.1s* | Never blocks today. Belongs in Tier 3 by definition. |
| 14 | `decision ids` | 1 | A cited `D<n>` does not resolve. `make map ARGS=D<n>` finds nothing. | ~0.1s* | The most-cited id form in the repo. Cheap, direct. |
| 15 | `decision ids in code` | 3 | Already advisory, over code comments citing a decision id. | ~0.1s* | Never blocks today. |
| 16 | `decision structure` | 1 | A decision entry's heading shape breaks `decision-context.py`'s parser. The hook silently returns nothing for that entry. | ~0.1s* | Fixes a documented silent-failure mode (pre-D60, 20% of bold text invisible to the hook). |
| 17 | `decision index` | 1 | CLAUDE.md's own D-number index disagrees with the real headings. | ~0.1s* | Every session reads this index first. |
| 18 | `id claims` | 1 | A branch carries a `D<n>`/`DEBT<n>` id main already claimed. Two entries collide. | ~0.1s* | Named safety row (`PLAN.md`). Caught a half-landed claim twice, per the plan. |
| 19 | `claim vocabulary` | 1 | The claimer and the auditor disagree on what a valid slug looks like. | ~0.1s* | Same mechanism as `id claims`. |
| 20 | `entry budget` | 3 | Already advisory. A decision entry grows past its byte budget. Never blocks. | ~0.1s* | 28 questions printed for a while with no action taken. See "Unsure" above. |
| 21 | `debts headings` | 1 | A DEBT heading is not addressable by the reader function. | ~0.1s* | Cheap, mirrors the decisions check. |
| 22 | `debt index` | 1 | DEBTS.md's index disagrees with the real headings. | ~0.1s* | Same rationale as `decision index`. |
| 23 | `debt ids` | 1 | A cited `DEBT<n>` does not resolve. | ~0.1s* | Cheap, direct. |
| 24 | `env vars` | 1 | A documented `PKMNSCAN_*` bypass is not real. Someone sets a hatch that does nothing. | ~0.1s* | A stale escape-hatch name is a real footgun. |
| 25 | `env names` | 1 | A real bypass the code reads is undocumented. Someone hits it with no warning. | ~0.1s* | Mirror of `env vars`, same stakes. See "Unsure" above. |
| 26 | `hatch state` | 3 | Already advisory. A switched-off guard with nothing saying so. | ~0.1s* | Never blocks today. |
| 27 | `subagent override` | 1 | A settings file raises the subagent model with no expiry, or an expired one still applies. | ~0.1s* | Named safety row. A real incident: a rewrite happened inside a session, and a plain clear could not reverse it. |
| 28 | `claim decode` | 1 | The card writer and the box writer decode the claim vocabulary differently. A claim silently corrupts. | ~0.1s* | Real cross-module data-integrity check. |
| 29 | `claim clients` | 1 | A client sends keys the route does not expect. | ~0.1s* | Real client-server key agreement. |
| 30 | `detector standing` | **CUT (Q2)** | A published rig figure drifts from the real result file. | ~0.1s* | The figure is a number the result file already holds. |
| 31 | `sole reader` | 1 | A new zero-argument `Store.history()` call reappears, a known full-table-scan regression. | ~0.1s* | Tripwire for a real, previously fixed performance bug (D191). |
| 32 | `server concurrency` | 1 | The published concurrency constants drift from the real server code. | ~0.1s* | Protects against repeating the 969-thread meltdown. |
| 33 | `estimate wire` | 1 | The identify flow's cost preview and the code that spends money read different lines. | ~0.1s* | Money-adjacent. |
| 34 | `shipping columns` | 1 | The published Pirate Ship column count drifts from the real importer. | ~0.1s* | Real shipping-export dependency. |
| 35 | `column count` | 1 | A code comment's own column count drifts from the tuple it describes. | ~0.1s* | Same subject as `shipping columns`. A merge candidate under a separate question, not this one. |
| 36 | `threshold agreement` | 1 | The $0.40 price threshold drifts between Python and TypeScript. A card lists at the wrong price. | ~0.1s* | Real money constant, duplicated. |
| 37 | `dist path agreement` | 1 | The built-bundle path disagrees across three files. `make up` serves a stale or missing bundle. | ~0.1s* | Real production-serving risk. |
| 38 | `import filename agreement` | 1 | A shipping import filename disagrees with its own download header. | ~0.1s* | Real shipping-workflow risk. |
| 39 | `duplicated measurements` | **CUT (Q2)** | Three hand-copied measurements can disagree with each other. Never checks any of them is still true. | ~0.1s* | Copies of numbers already printed elsewhere. |
| 40 | `router certainty` | **CUT (Q2)** | A published join-routing statistic drifts from the harness result. | ~0.1s* | Repeats a number T7 already prints. |
| 41 | `work item standing` | **CUT (Q2)** | CLAUDE.md's claim about a work item drifts from the spec's own status table. | ~0.1s* | Repeats a status the spec already states. |
| 42 | `not-built endpoints` | **CUT (Q2)** | A deliberately-unbuilt endpoint gets silently claimed as built. | ~0.1s* | Repeats a count the transport module already states. |
| 43 | `transport standing` | **CUT (Q2)** | A claim about which transport calls ran live drifts from the module. | ~0.1s* | Repeats a count the module already states. |
| 44 | `repo map` | 1 | docs/map.py claims a file exists, or misses one. A session trusts a wrong map entry. | ~0.1s* | The most structural row after `decision ids` (463 entries). |
| 45 | `hook roster` | 2 | A git hook file has no docs/map.py entry. | ~0.1s* | Bookkeeping between two files (5 hooks), not a command a session runs. See "Unsure" above. |
| 46 | `codex hooks` | 2 | Codex's hook file and Claude's hook file name different hooks. | ~0.1s* | Cross-tool bookkeeping (D135). Main must agree, a commit need not wait. |
| 47 | `map sections` | 2 | A docs/map.py section has no reader, or its own consumer list is wrong. | ~0.1s* | Internal map hygiene. |
| 48 | `gates structure` | 2 | The gates corpus is internally inconsistent. | ~0.1s* | Structural check on a corpus other rows depend on. |
| 49 | `build order mirror` | 2 | docs/map.py's step ids and GATES.md's step ids disagree. | ~0.1s* | Bookkeeping between two files. |
| 50 | `game vocabulary` | 1 | The per-game rarity and finish shape drifts from what the real committed exports contain. Pricing mis-joins. | ~0.1s* | Real money-adjacent, catalog-join check. |
| 51 | `game coverage` | 3 | Already advisory. Prints what committed exports do not corroborate. | ~0.1s* | Never blocks today. Widening coverage needs a person, per D170. |
| 52 | `game coverage allowlist` | 1 | A stale exemption on the `game coverage` advisory hides a fixed gap. | ~0.1s* | Tiny list (2 entries). |
| 53 | `matrix superset` | 1 | A real catalog rarity or finish pair is not one the pricing code allows for. A new set silently mis-prices. | ~0.1s* | Real catalog-drift protection. |
| 54 | `join key shape` | 1 | A join key shape can never match a real export row. Cards silently fail to join. | ~0.1s* | The join is money-critical. |
| 55 | `reason codes` | 1 | A review reason exists in one place and not another. A screen shows a code nobody defined. | ~0.1s* | Real screen-facing check. |
| 56 | `reason emissions` | 1 | A published review reason has no code path that can emit it, or an emitted one is unpublished. | ~0.1s* | Same subject as `reason codes`. |
| 57 | `supervisor self-watch` | 1 | The process supervisor does not know about a file it imports, and could restart itself over its own code. | ~0.1s* | Could bounce the owner's live server. |
| 58 | `motion params` | 1 | The TypeScript and Python copies of the motion-trigger constants disagree. Tuning silently reverts. | ~0.1s* | Real tuning history at stake (D81, D130, D131). |
| 59 | `logo parity` | 1 | The generated mark and its spec disagree on a locked color. | ~0.1s* | Real brand-asset drift check. |
| 60 | `mac icon grid` | 1 | The icon inset grid number disagrees between the spec and the generator. | ~0.1s* | Same asset family as `logo parity`. |
| 61 | `lockup params` | 1 | The lockup sheet's measurements disagree with the settled spec table. | ~0.1s* | Same asset family. |
| 62 | `rail mark` | 1 | The sidebar's rail bracket in the mockup is not the mark the app actually ships. | ~0.1s* | Same asset family. |
| 63 | `lockup bracket` | 1 | The lockup's bracket color is hand-picked instead of read from the locked palette. | ~0.1s* | Same asset family. |
| 64 | `withhold reasons` | 1 | The three withhold reasons disagree between Python and TypeScript. | ~0.1s* | Cross-language enum agreement, screen-facing. |
| 65 | `order reasons` | 1 | The six order-line reasons disagree between Python and TypeScript. | ~0.1s* | Same family as `withhold reasons`. |
| 66 | `terminal statuses` | 1 | The three terminal order statuses disagree with D63's own published claim. | ~0.1s* | Same family, cites its governing decision directly. |
| 67 | `pricing presets` | 1 | The three pricing presets disagree between the pricing tuple and the screen's table. | ~0.1s* | Same family, money-adjacent. |
| 68 | `export request` | 1 | A deliberately pinned catalogue-export field silently reverts to a default. | ~0.1s* | Protects a decided value, not an incidental default. |
| 69 | `transport promise` | 1 | A file's own stated host, method, or route count disagrees with its body. | ~0.1s* | Catches doc-in-code drift specifically. |
| 70 | `hint reasons` | 1 | The capture screen's refusal label disagrees with what the server can actually send. The operator sees a wrong message mid-capture. | ~0.1s* | Real user-facing refusal text. |
| 71 | `tested_by reach` | 2 | docs/map.py claims a test proves a file, but the test never imports it. | ~0.1s* | Keeps the map honest for a later session, not an immediate wrong action. |
| 72 | `status sources` | 2 | A file `make status` reads does not exist. | ~0.1s* | Plumbing check on a command every session runs first. |
| 73 | `design tokens` | 1 | DESIGN.md's locked palette disagrees with the real `--bn-*` tokens. | ~0.1s* | Enforces the one design-token rule the whole front end depends on. |
| 74 | `raw color` | 1 | A stylesheet names a raw hex color outside tokens.css. A screen drifts from the design system. | ~0.1s* | Real screen-facing rule (38 sheets). |
| 75 | `breakpoints` | 1 | A stylesheet opens an undocumented breakpoint. A screen behaves off the ladder. | ~0.1s* | Real layout-drift protection (179 blocks, 19 widths, 25 sheets). |
| 76 | `breakpoint columns` | 3 | Already advisory. Two real, live findings today: a regime opened on the raw viewport instead of the real column. | ~0.1s* | Never blocks today. Worth a look in CI, since it is catching something now. |
| 77 | `js breakpoints` | 1 | A JS media query invents its own width instead of matching its stylesheet's. | ~0.1s* | Has direct evidence of past drift (rewritten once to fix its own matching). |
| 78 | `storage keys` | 1 | The app writes a device-local key CLAUDE.md's roster does not name. A privacy-adjacent list goes stale. | ~0.1s* | Long, hand-maintained, device-persistence list. |
| 79 | `views opsec` | 1 | A screenshot manifest line addresses the raw photo service directly, or points at an unregistered route. A code-card photo could leak. | ~0.1s* | Real money-adjacent stakes (bearer instrument), a real past incident. |
| 80 | `views exposure` | OFF | Turned off 2026-09-23 while code cards are dormant. Examines nothing. | ~0.1s* | Unchanged by this exercise. Flip back on when code-card work resumes, per CLAUDE.md. |
| 81 | `doc hygiene` | 3 | Already advisory. 20 real, live findings today, including a leftover editor instruction pasted into a spec. | ~0.1s* | Never blocks today. Worth a look in CI, since it is catching real defects now. |
| 82 | `route rosters` | 2 | A hand-typed route list in a spec disagrees with App.tsx's real ROUTES table. | ~0.1s* | Matches the owner's own "rosters match" example directly. |
| 83 | `recorded deletions` | 1 | A merge silently restores code a decision says is deleted. A session trusts dead functionality as current. | ~0.1s* (unmeasured, scans 243 files) | Real named catch (PR #221, the D119 hero regression). See "Unsure" above. |
| 84 | `spec seal` | 1 | A test does not seal its own capture port first. It could collide with another checkout or reach a live store. | ~0.1s* | Named safety row. |
| 85 | `verdict file` | 2 | The design-check verdict file is named differently across the reporter, config, and two recipes. | ~0.1s* | Keeps five places agreeing, not an immediate wrong action. |
| 86 | `route census` | **CUT (Q2)** | A published route or screen count drifts from ROUTES. | ~0.1s* | Repeats a count the table already gives. |
| 87 | `check registry` | 2 | The documented `make check` recipe drifts from the real one. | ~0.1s* | Important for main, not urgent for a local commit. |
| 88 | `commit path` | 2 | A check on the commit path writes, breaking D18's own no-write guarantee. | ~0.1s* | Makes D18 a fact about the code, structural but not a wrong-target action. |
| 89 | `check census` | **CUT (Q2)** | Two published lists of what `make check` runs disagree with the real recipe. | ~0.1s* | Same subject as `check registry`, and repeats a count the recipe already gives. |
| 90 | `no mechanism on screen` | 1 | A visible string names a decision id, a repo path, or an internal noun. The owner sees jargon on screen. | ~0.1s* | Real screen-facing rule (D196), 2,694 strings scanned. |
| 91 | `typed interpunct` | 1 | A visible string types a middle dot instead of drawing one in CSS. | ~0.1s* | Tied to a repeated owner ruling (D41, D218, D280). |
| 92 | `ste offenders` | 3 | A markdown sentence breaks an STE rule. The gated half only checks an 11,352-entry list did not grow, never that prose improved. | 18.09s (measured) | 38% of the whole run's cost. The real prose ratio is already printed, never gated. The write-time STE hook already catches new errors. |
| 93 | `suite lock` | 2 | A Playwright fleet script skips the machine-wide lock and fights another fleet for the CPU. | ~0.1s* | CI-meta wiring check, not a doc reference. |
| 94 | `browser scope` | 1 | The CI browser-matrix scope list misses a real dependency, or keeps a stale one. CI wastes time or skips a real UI change. | ~0.1s* | Named safety row. |
| 95 | `spec map` | 2 | The spec-to-file map used for CI narrowing goes stale. | 3.15s (measured) | Too slow for Tier 1. Also CI-meta only. |
| 96 | `serve scope` | 1 | The path-gate roster for `serve-selftest` disagrees with the self-test's own carried names. | ~0.1s* | Named safety row. |
| 97 | `guard scope` | 1 | The guard self-test roster disagrees with the Makefile's real wiring. | ~0.1s* | Named safety row. |
| 98 | `check numbering` | 2 | A staged doc cites a check by its position instead of its label. The citation breaks the next time the list reorders. | ~0.1s* | Style-of-citation check, not a target that does not exist yet. |
| 99 | `numbering in code` | 3 | Already advisory. Comments must name a check by label, not position. | ~0.1s* | Never blocks today. |
| 100 | `audit invocation` | 2 | A caller of this script passes a flag the parser does not declare. | ~0.1s* | CI-meta wiring check on the tool's own callers. |
| 101 | `identifier spelling` | 3 | A British-spelled identifier sits in the tree. A session searching for the American form misses it. | 5.91s (measured) | Fourth most expensive row, one subprocess call per file. The rule is sound. The implementation is the cost problem. |
| 102 | `shell substitution` | 1 | A double-quoted shell string in a scripted file runs an unintended command through backtick substitution. | ~0.1s* | Real accidental-execution class. This repo has a documented history of shell-quoting incidents. |
| 103 | `unscoped walk` | 1 | A new full-table read of `inventory.cards` appears. A real performance regression on the owner's real store. | ~0.1s* | Tied to a real, previously observed performance defect. |
| 104 | `import layering` | 1 | `store/` starts importing `pipeline/`, breaking the one-way dependency rule (D63). | ~0.1s* | Architectural rule that rots silently without a check. |
| 105 | `identity writers` | 1 | A card identity field is set outside the six sanctioned writers. Card identity can silently corrupt. | ~0.1s* | Named example of D173's own rule, real data-integrity check. |
| 106 | `rule enforcement` | 2 | A CLAUDE.md hard rule names no mechanism and no argument for why one cannot exist. | ~0.1s* | Governs whether other rules are honest, not one wrong-target action. |
| 107 | `check dispatch` | 2 | A check function is defined but never called by `audit()`. It silently stops running. | ~0.1s* | Its own comment admits this row does not fully prove itself either. |
| 108 | `subject counts` | 2 | A row silently examines zero subjects and reports a false "ok". | ~0.1s* | Meta-check over the other rows, not a direct navigation harm. |
| 109 | `coupling` | 3 | Already advisory, staged-only. A large change to pipeline, harness, or the Makefile lands with no matching doc update. | ~0.1s* | Already scoped to the real diff, already cheap. Fine to leave as-is either way. |

## The owner's rulings (2026-09-27)

The tier model and every row not named below stand as proposed. The owner's words are quoted.

- **Line anchors, rows 3, 4 and 5 plus `line anchor allowlist`:** `yeah convert and collapse`.
  A lane converts the old line anchors (about 88, in 44 files) to symbol citations. Then one
  Tier 1 row refuses any line anchor. The four rows merge into it. The parent CLAUDE.md asks
  for the same thing: cite by id, never by path and line.
  **Landed 2026-09-28 by the line-anchor lane.** The lane
  converted 776 anchors in 44 files. The one `line anchors` row (Tier 1) now refuses every
  `path:N` and `path:N-M`, with no list of exceptions. `line anchor allowlist` and `line
  anchor offenders` are gone, with the two data files they read. CLAUDE.md's D245 hard rule describes the one row.
- **Row 20, `entry budget`:** CUT.
- **Row 48, `gates structure`:** CUT. Gating retired, and `gates-selftest` proves the set is
  complete.
- **Row 92, `ste offenders`, and its list `scripts/ste-offenders.json`:** CUT. The write-time
  STE hook lints new prose. This needs dated amendments to D226, D229 and D280 (the prose
  ratchet decisions) in the lane that cuts it.
- **Rows 51 and 52, `game coverage` and its allowlist:** both to Tier 3.
- **Row 15, `decision ids in code`:** folds into row 14, `decision ids`, as one blocking row.
- **Row 47, `map sections`:** Tier 3.
- **Row 60, `mac icon grid`:** Tier 2, inside L8's logo family.
- **Row 49, `build order mirror`:** a later lane makes the build order one source. Then the row
  goes.
- **Q8, merge 16 rows into 4:** `Yes, as L8 (Recommended)`. L8 landed the logo family (5
  rows into `logo`), the closed-vocabularies family (6 rows into `closed vocabularies`),
  and four pairs: `env vocabulary`, `pass criteria`, `column counts`, and `check registry`.
  Row 15 `decision ids in code` folded into row 14 `decision ids`, as one blocking row.
  Row count: 107 to 93 on a full run. NOT landed: `check numbering` and `numbering in
  code`. That function's own docstring argues the two need a different scope and a
  different severity. A merge cannot preserve that without changing what one row judges.
  This needs the owner's word before it can proceed. The line-anchor trio, M3's third
  group, is superseded by the owner's fuller "convert and collapse" ruling. That is a
  separate, larger lane: L8 measured 776 real line-number citations in 44 files today,
  not the about 88 once estimated, and did not attempt the conversion.
- **Markdown spelling (lane L2's measurement, 727 British spellings in 226 files):** `Shrinking
  offender list now`. The `identifier spelling` check reaches markdown now. Today's words are
  listed per file, and the list may only shrink, on D280's pattern. New prose uses American
  spelling from now on. A follow-up to L2 builds it after L2 merges.
- **Row 17 and CLAUDE.md's decision index:** `Derived view + pointer (Recommended)`. A lane
  adds `make map ARGS=--decisions`, which prints the index from each entry's own heading. The
  copy in CLAUDE.md becomes one line that names the command, and row 17 is cut. The parent
  rule it follows: never load a long document whole, and read a rendered view instead.
  The owner then declined keeping the 288 entries that govern code (it saves about 1.2 KB of
  26 KB). The same lane amends D60's conversational-path paragraph, whose premise (60 lines,
  3,929 bytes) measured 301 lines and 26,420 bytes on 2026-09-27.

- **Line anchors, re-scoped (owner, 2026-09-28):** `Own lane, after PR 4B (Recommended)`. The real
  count is 776 citations in 44 files, not about 88. Until that lane lands, the three line-anchor
  rows stay, and the offender list only shrinks.
- **`check numbering` and `numbering in code` (owner, 2026-09-28):** `Keep them apart
  (Recommended)`. The markdown row blocks the commit that touches a bad reference. The code
  row warns only, because a comment about a count is often plain English. Both find nothing
  today. So L8 lands 93 rows, not 92.
- **L12 landed (2026-09-28).** The tier column is now `scripts/docs-audit.py:TIER`, read by
  `_run_at_commit`. The pre-commit hook passes `--commit`; `make docs-audit` and CI pass
  nothing, so nothing there narrows. The nine Q2 rows are cut, and the prose number each one
  policed is deleted from CLAUDE.md, README.md, docs/map.py and
  docs/specs/order-pipeline.md. Rows 20 (`entry budget`) and 48 (`gates structure`) are cut
  too. See "Counts, as landed" and "Commit-hook
  time, measured" above for the row and timing figures this ruling made stale.

## Next

- Owner reviews the tier column and the "Rows I was unsure about" table, and rules or
  amends.
- The line-anchor conversion (rows 3-5 plus the allowlist) is its own lane, after PR 4B, per
  the 2026-09-28 ruling above.
