# Test audit: `make docs-audit` (`scripts/docs-audit.py`)

Owner's brief, 2026-09-27: audit every test, harness, and gate mandating this app before
resolving anything. This file is one slice: `scripts/docs-audit.py` itself, its pre-commit
hook, and the offender/allow lists its rows read. It is INPUT for an Opus reviewer, not a
plan. It does not decide what to cut. It reports what each row does, what evidence backs
it, and a first verdict.

Repo: `/Users/shivinate/Developer/pkmnscan`. Branch: `ux/test-audit-docs`, based on
`ux/pr4b` at commit `103fde97`. Read: `scripts/docs-audit.py` (21,814 lines, read by
section, function docstrings, and the pre-commit hook `scripts/githooks/pre-commit`),
`docs/decisions/`, `docs/debts/`, and `git log`.

No check and no product code changed. This file is the only change.

## How the audit runs

Three callers (the `audit invocation` row counts them):

- `scripts/githooks/pre-commit` runs `python3 scripts/docs-audit.py --staged` on every
  commit. `--staged` narrows several rows to the staged doc set only (see `EXPECTED_EMPTY`
  in the source) and adds one row, `coupling`, that only exists in this mode.
- `make docs-audit` runs the full, un-staged sweep over the whole tree (Makefile line 568).
- The `/docs-audit` skill (session-invoked) runs it too, for a review pass.

Two severities plus one disabled state:

- **MECHANICAL (blocking)** — exit 1. A reference is provably wrong. The hook fails the
  commit.
- **ADVISORY (non-blocking)** — exit 2. A question: code changed, its doc did not. Prints
  and allows.
- **OFF** — one row (`views exposure`) is coded but its own module constant
  (`VIEWS_EXPOSURE_ENABLED = False`) turns it into a no-op, on purpose, while code cards
  are dormant.

Bypass: `PKMNSCAN_DOCS=off git commit ...`, printed in every MECHANICAL refusal.

Two constants pin the `rule enforcement` row (CLAUDE.md's Hard Rules section, D173):
`HARD_RULE_FLOOR` (a non-vacuity floor — some rules must resolve to a real mechanism) and
`PROSE_ONLY_EXPECTED` (how many hard rules may legitimately argue they cannot be
mechanized). This run found 14 hard rules: 9 resolve to a real mechanism, 5 argue why none
can, both pinned at their current counts.

## Row count and run result

`python3 scripts/docs-audit.py` (full, un-staged, 2026-09-27, commit `103fde97`):
108 rows in this mode. One more row, `coupling`, exists but only runs under `--staged`,
for 109 distinct rows total. Result: 0 mechanical failures, 3 advisory rows carrying
50 live questions (`entry budget` 28, `breakpoint columns` 2, `doc hygiene` 20), 3 rows
examined nothing (2 by design — `evidence freshness`, `sole reader` — and 1 turned off on
purpose — `views exposure`), 102 rows clean.

## Cost

Full run, unprofiled, wall time: **37.3s** (`time python3 scripts/docs-audit.py`).

Profiled with `python3 -m cProfile -s cumulative` (one run, 47.2s wall under the profiler's
own overhead — proportions below still hold against the unprofiled 37.3s):

| Row | Cumulative time (profiled) | Share of profiled run |
|---|---|---|
| `ste offenders` | 18.09s | 38.3% |
| `paths` | 5.95s | 12.6% |
| `identifier spelling` | 5.91s | 12.5% |
| `spec map` | 3.15s | 6.7% |
| everything else (101 rows) combined | ~14.1s | ~29.9% |

Four rows are roughly **70% of the whole run's cost**. The `ste offenders` row alone is
over a third of it. It scans every sentence in 509 files against four STE rules, inside
`ste_measure.py` and `ste_lint.py`. The gate it runs only asks whether the 11,352-entry
offender list grew. It never asks whether the prose got better. That second, real
measure prints and never gates. See the `ste offenders` section below.

The pre-commit hook runs `--staged`. That mode zeroes out several full-tree rows —
`paths`, `line anchors`, **make targets**, `derived numbers`, `env vars` — since they
read only the staged documents. Day-to-day commit cost is lower than 37s for this reason,
but this audit did not separately measure it on a real staged diff. `ste offenders` and
`identifier spelling` are NOT staged-scoped. Both run their full cost on every commit.

## Commit friction, last 30 days

| Measure | Count | Of 2,640 total commits |
|---|---|---|
| Commits touching `scripts/docs-audit.py` | 217 | 8.2% |
| Commit messages mentioning "docs-audit" / "docs audit" | 309 | 11.7% |
| Commit messages mentioning `PKMNSCAN_DOCS` (the bypass) | 15 | 0.6% |

Caveat, honestly: a per-row keyword search (`git log --grep="<row name>"`) is noisy.
A commit message that says "decision ids" is often about decision-numbering work.
It is rarely about the `decision ids` row failing. The two numbers above are the
reliable ones. The brief for this audit gave one specific example. The make-targets
row read an owner's prose quote, "We just need to make capping...", as a reference
to a target named `capping`. That example is recorded here as reported. It was not
yet committed at the time of this audit, so it could not be independently found in
`git log`.

Note on the two rows above named **make targets** and **pkmnscan commands**. Writing
either name in backticks in this very file tripped the audit's own checks. The
make-target and pkmnscan-subcommand checks read the row's name as a live command
reference. Each then failed this file, for a target and a subcommand that do not exist.
Confirmed by running `python3 scripts/docs-audit.py --staged` against this draft.
Fixed here by writing those two row names in bold instead of backticks, everywhere in
this file. This is the exact false-positive class the brief for this audit named,
caught live.

## Summary table

Severity: **blocking** = MECHANICAL (fails the commit). **advisory** = ADVISORY (prints,
never blocks). **off** = coded but disabled. Category: **PRODUCT** = protects what the
owner sees/uses at runtime. **PROCESS** = protects the test/CI/verification machinery
itself, one step removed from the product. **DOCS** = protects prose/citation accuracy
only — nothing ships differently if it were wrong.

| # | Row | Severity | Subjects (this run) | Category | Verdict |
|---|---|---|---|---|---|
| 1 | `paths` | blocking | 6963 references resolve | DOCS/PROCESS | **KEEP** |
| 2 | `allowlist` | blocking | 26 entries, none stale | DOCS/PROCESS | **KEEP** |
| 3 | `line anchors` | blocking | 775 line anchors checked, 0 past the target's end (13 allowed), 0 i... | DOCS/PROCESS | **SHRINK** |
| 4 | `line anchor allowlist` | blocking | 10 entries, none stale | DOCS/PROCESS | **KEEP** |
| 5 | `line anchor offenders` | blocking | 777 line anchors over 44 files; 777 listed over 44 files; 0 unliste... | DOCS/PROCESS | **MERGE** |
| 6 | `derived numbers` | blocking | 3 marked figure(s) checked against the tree, 3 derivation(s) regist... | DOCS/PROCESS | **KEEP** |
| 7 | **make targets** | blocking | 1504 references, 118 targets | DOCS/PROCESS | **KEEP** |
| 8 | **pkmnscan commands** | blocking | 14 registered, all documented | DOCS/PROCESS | **KEEP** |
| 9 | `harness tests` | blocking | 10 registered and documented | DOCS/PROCESS | **KEEP** |
| 10 | `pass criteria` | blocking | every threshold matches GATES.md | DOCS/PROCESS | **KEEP** |
| 11 | `criteria wording` | blocking | every criterion is published verbatim | DOCS/PROCESS | **MERGE** |
| 12 | `criteria evidence` | blocking | 2 scored run, gate field published | DOCS/PROCESS | **KEEP** |
| 13 | `evidence freshness` | advisory | examined nothing — its subject is the STAGED score sources; in a fu... | DOCS/PROCESS | **KEEP** |
| 14 | `decision ids` | blocking | 302 D + 11 C headings | DOCS/PROCESS | **KEEP** |
| 15 | `decision ids in code` | advisory | citations in .py, .ts, .tsx, .css and .js all resolve | DOCS/PROCESS | **KEEP** |
| 16 | `decision structure` | blocking | 302 entries, every heading and bold reaches the hook | DOCS/PROCESS | **KEEP** |
| 17 | `decision index` | blocking | 301 indexed, matching 302 headings | DOCS/PROCESS | **KEEP** |
| 18 | `id claims` | blocking | 1 unclaimed id(s) on this branch, claimed at the merge | DOCS/PROCESS | **KEEP** |
| 19 | `claim vocabulary` | blocking | one slug grammar, declared in the auditor and in the claimer | DOCS/PROCESS | **KEEP** |
| 20 | `entry budget` | advisory | 28 questions | DOCS/PROCESS | **ADVISORY** |
| 21 | `debts headings` | blocking | 46 headings, every one addressable by `_debts_section` | DOCS/PROCESS | **KEEP** |
| 22 | `debt index` | blocking | 46 indexed, matching 46 headings | DOCS/PROCESS | **KEEP** |
| 23 | `debt ids` | blocking | 46 entries, citations in docs and code all resolve, the retired pat... | DOCS/PROCESS | **KEEP** |
| 24 | `env vars` | blocking | 55 documented, all real | PROCESS (test/CI meta) | **KEEP** |
| 25 | `env names` | blocking | 54 named in code, all documented | PROCESS (test/CI meta) | **MERGE** |
| 26 | `hatch state` | advisory | 54 hatches in the roster, none set in this environment or in .claud... | PROCESS (test/CI meta) | **KEEP** |
| 27 | `subagent override` | blocking | 2 settings files reachable from this checkout (its own and every ne... | PROCESS (test/CI meta) | **KEEP** |
| 28 | `claim decode` | blocking | 2 claim writers, one vocabulary (6 keys) | PRODUCT | **KEEP** |
| 29 | `claim clients` | blocking | 2 client writers send exactly what their route decodes | PRODUCT | **KEEP** |
| 30 | `detector standing` | blocking | 8 published figures against harness/results/detect.json | PRODUCT | **KEEP** |
| 31 | `sole reader` | blocking | examined nothing — its subject is every zero-argument `Store.histor... | PRODUCT | **KEEP** |
| 32 | `server concurrency` | blocking | 9 published facts against server/capture_server.py | PRODUCT | **KEEP** |
| 33 | `estimate wire` | blocking | the preflight's cost line is the line `estimate_usd` reads | PRODUCT | **KEEP** |
| 34 | `shipping columns` | blocking | 2 published counts against pipeline/pirateship.py (12) | PRODUCT | **KEEP** |
| 35 | `column count` | blocking | the comment's word against COLUMNS's length (10) | PRODUCT | **MERGE** |
| 36 | `threshold agreement` | blocking | app/src/ReviewQueue.tsx:THRESHOLD against pipeline/pricing.py:THRES... | PRODUCT | **KEEP** |
| 37 | `dist path agreement` | blocking | scripts/serve.py:DIST, server/capture_server.py:APP_DIST and vite.c... | PRODUCT | **KEEP** |
| 38 | `import filename agreement` | blocking | server/shipping_routes.py:IMPORT_FILENAME against the Content-Dispo... | PRODUCT | **KEEP** |
| 39 | `duplicated measurements` | blocking | cid lookup latency (3 sites), store total (23 sites) and largest dr... | DOCS/PROCESS | **KEEP** |
| 40 | `router certainty` | blocking | 2 published splits against harness T7 (112 of 331) | PRODUCT | **KEEP** |
| 41 | `work item standing` | blocking | 8 claims in CLAUDE.md against 8 work items declared in §3 | DOCS/PROCESS | **KEEP** |
| 42 | `not-built endpoints` | blocking | 2 declared in order_transport.py, 2 quoted in order-pipeline.md | PRODUCT | **KEEP** |
| 43 | `transport standing` | blocking | 2 proven and 1 unexercised calls against 3 readers | PRODUCT | **KEEP** |
| 44 | `repo map` | blocking | 463 entries match the tree | DOCS/PROCESS | **KEEP** |
| 45 | `hook roster` | blocking | 5 hooks, all in docs/map.py | DOCS/PROCESS | **KEEP** |
| 46 | `codex hooks` | blocking | 11 hooks in .claude/settings.json, all mirrored in .codex/hooks.json | PROCESS (test/CI meta) | **KEEP** |
| 47 | `map sections` | blocking | 5 of 5 sections have a reader, consumer list agrees | DOCS/PROCESS | **KEEP** |
| 48 | `gates structure` | blocking | 10 contract entries, 5 run entries, 21 shipped + 2 open steps | DOCS/PROCESS | **KEEP** |
| 49 | `build order mirror` | blocking | 23 steps, the same ids in both files, in the same two lists | DOCS/PROCESS | **KEEP** |
| 50 | `game vocabulary` | blocking | 5 games, 31 export rarities accounted for | PRODUCT | **KEEP** |
| 51 | `game coverage` | advisory | 5 committed exports, 0 opt-in | PRODUCT | **KEEP** |
| 52 | `game coverage allowlist` | blocking | 2 entries, none stale | DOCS/PROCESS | **KEEP** |
| 53 | `matrix superset` | blocking | 48 observed rarity/finish pairs, all allowed | PRODUCT | **KEEP** |
| 54 | `join key shape` | blocking | 1 composed-key games checked against export Number cells | PRODUCT | **KEEP** |
| 55 | `reason codes` | blocking | 15 enumerated, 15 labeled, all defined | PRODUCT | **MERGE** |
| 56 | `reason emissions` | blocking | 15 published reasons, 14 with a producer and 1 argued | PRODUCT | **KEEP** |
| 57 | `supervisor self-watch` | blocking | 5 self-files, every module-scope import accounted for | PRODUCT | **KEEP** |
| 58 | `motion params` | blocking | 19 mirrored constants agree, 0 accounted for | PRODUCT | **KEEP** |
| 59 | `logo parity` | blocking | 6 locked marks, every prism, ground, bracket and base against secti... | PRODUCT | **KEEP** |
| 60 | `mac icon grid` | blocking | 824/1024 in section 17 and in build-mark.mjs, over 3 inset icons | PRODUCT | **MERGE** |
| 61 | `lockup params` | blocking | 11 settled values against the sheet's holds and the generated geometry | PRODUCT | **MERGE** |
| 62 | `rail mark` | blocking | the rail bracket is the shipped mark — in the sheet, at both ends o... | PRODUCT | **MERGE** |
| 63 | `lockup bracket` | blocking | 4 stops against `bluesteel`'s locked bracket | PRODUCT | **MERGE** |
| 64 | `withhold reasons` | blocking | 3 authored, offered by the screen, none unreachable | PRODUCT | **MERGE** |
| 65 | `order reasons` | blocking | 6 authored, offered by the screen, none unreachable | PRODUCT | **MERGE** |
| 66 | `terminal statuses` | blocking | 3 authored, published in D63, none unreachable | PRODUCT | **MERGE** |
| 67 | `pricing presets` | blocking | 3 priced, written by the screen, key rule and basis agree | PRODUCT | **MERGE** |
| 68 | `export request` | blocking | 3 catalogue filters and 2 live query parameters, each at its measur... | PRODUCT | **KEEP** |
| 69 | `transport promise` | blocking | 1 host, 2 methods, 3 routes, as promised and as called | PRODUCT | **KEEP** |
| 70 | `hint reasons` | blocking | 9 refusals reachable from filters(), 11 labeled by the screen | PRODUCT | **KEEP** |
| 71 | `tested_by reach` | blocking | 69 claims, every cited test reaches what it names | PROCESS (test/CI meta) | **KEEP** |
| 72 | `status sources` | blocking | 15 declared, all resolve | PROCESS (test/CI meta) | **KEEP** |
| 73 | `design tokens` | blocking | 123 declared tokens, every one named by the block; 35 hexes compare... | PRODUCT | **KEEP** |
| 74 | `raw color` | blocking | every color in 38 sheets comes from a token | PRODUCT | **KEEP** |
| 75 | `breakpoints` | blocking | 179 blocks over 19 media widths in 25 sheets, all on the ladder; 4 ... | PRODUCT | **KEEP** |
| 76 | `breakpoint columns` | advisory | 2 questions | PRODUCT | **KEEP** |
| 77 | `js breakpoints` | blocking | 7 JS breakpoints in 5 files, each paired to its own imports; 0 unpa... | PRODUCT | **KEEP** |
| 78 | `storage keys` | blocking | 11 device-local keys against CLAUDE.md's roster, 2 session keys all... | PRODUCT | **KEEP** |
| 79 | `views opsec` | blocking | 10 of 10 views resolve in ROUTES, none address the photo service; 1... | PRODUCT | **KEEP** |
| 80 | `views exposure` | off | examined nothing — turned OFF 2026-09-23 while code cards are dorma... | PRODUCT (disabled) | **KEEP** |
| 81 | `doc hygiene` | advisory | 20 questions | DOCS/PROCESS | **KEEP** |
| 82 | `route rosters` | blocking | 2 declared rosters against 14 registered routes | DOCS/PROCESS | **KEEP** |
| 83 | `recorded deletions` | blocking | 5 recorded deletions, 13 needles over 6 roots and 243 files; 1 narr... | DOCS/PROCESS | **KEEP** |
| 84 | `spec seal` | blocking | 40 specs sealed against the capture port | PROCESS (test/CI meta) | **KEEP** |
| 85 | `verdict file` | blocking | .serve/design-check.json agreed by the reporter, the config, 2 reci... | PROCESS (test/CI meta) | **KEEP** |
| 86 | `route census` | blocking | 11 published counts against 14 routes (13 owner), 9 owner renders i... | DOCS/PROCESS | **KEEP** |
| 87 | `check registry` | blocking | 60 checks in recipe order, 59 in ci-check, 1 declared non-gating | PROCESS (test/CI meta) | **KEEP** |
| 88 | `commit path` | blocking | 2 of 60 on the commit path, 2 of them read against source, none wri... | PROCESS (test/CI meta) | **KEEP** |
| 89 | `check census` | blocking | 2 published lists, 60 checks each, in the `check:` recipe's order | PROCESS (test/CI meta) | **MERGE** |
| 90 | `no mechanism on screen` | blocking | 2694 visible strings carry none of it (3 allow-listed hit(s) over 3... | PRODUCT | **KEEP** |
| 91 | `typed interpunct` | blocking | 4 typed dots; 4 listed over 1 files (kit-frame 4); 0 unlisted, 0 st... | PRODUCT | **KEEP** |
| 92 | `ste offenders` | blocking | 11352 offending sentences (11843 findings; 811 exempted: {'table ro... | DOCS/PROCESS | **SHRINK** |
| 93 | `suite lock` | blocking | 1 fleet script behind the lock, 2 serial renderers still serial | PROCESS (test/CI meta) | **KEEP** |
| 94 | `browser scope` | blocking | 9 entries cover 18 derived dependencies, read fail-open | PROCESS (test/CI meta) | **KEEP** |
| 95 | `spec map` | blocking | 44 specs, 191 files reached, shell closure checked | PROCESS (test/CI meta) | **KEEP** |
| 96 | `serve scope` | blocking | 14 entries against 11 carried names, both ways | PROCESS (test/CI meta) | **KEEP** |
| 97 | `guard scope` | blocking | 22 roster entries against 22 wired Makefile recipes, both ways | PROCESS (test/CI meta) | **KEEP** |
| 98 | `check numbering` | blocking | no check named by position | DOCS/PROCESS | **MERGE** |
| 99 | `numbering in code` | advisory | comments name checks by label | DOCS/PROCESS | **MERGE** |
| 100 | `audit invocation` | blocking | 3 callers, flags all declared, usage 64 clear of advisory 2 | PROCESS (test/CI meta) | **KEEP** |
| 101 | `identifier spelling` | blocking | every identifier in 450 files is spelled American | DOCS/PROCESS | **SHRINK** |
| 102 | `shell substitution` | blocking | no double-quoted shell string in 19 files runs a command by accident | PROCESS (test/CI meta) | **KEEP** |
| 103 | `unscoped walk` | blocking | 11 full-table reads of inventory.cards found, 11 allowed (pinned at... | PRODUCT | **KEEP** |
| 104 | `import layering` | blocking | 17 store/ files scanned, 0 import pipeline/ | PRODUCT | **KEEP** |
| 105 | `identity writers` | blocking | 43 direct card.<field> assignment(s) found, all inside the 6 sancti... | PRODUCT | **KEEP** |
| 106 | `rule enforcement` | blocking | 14 hard rules: 9 name a mechanism that resolves, 5 argue why none c... | DOCS/PROCESS | **KEEP** |
| 107 | `check dispatch` | blocking | every check defined here is called by audit() | PROCESS (test/CI meta) | **KEEP** |
| 108 | `subject counts` | blocking | 107 rows, every one declaring its subject; 3 examined nothing, all ... | PROCESS (test/CI meta) | **KEEP** |
| 109 | `coupling` | advisory (staged-only) | runs in --staged only, over the source groups this commit touched | DOCS/PROCESS | **KEEP** |

Verdict counts: ADVISORY=1, KEEP=89, MERGE=16, SHRINK=3 (of 109 rows).

## Per-row detail

One short section per row, in the order the audit runs them.

### 1. `paths` — blocking

**Subjects this run:** 6963 references resolve

**Protects:** Every backticked path in the markdown resolves to a real file or directory. A `+`-marked proposed path that now exists gets its sigil dropped.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** No specific incident found in git log. The `.git/` exclusion comment names a real trip. A true sentence about `.git/config` (a file in a linked worktree) and `.git/worktrees/` once blocked a commit.

**False positives:** None found in a targeted search. The row is the single most expensive one after ste offenders (see Cost).

**Last caught a real defect:** unknown

**First verdict: KEEP** — Foundational — every other citation row depends on paths resolving first. Cost is the only concern (5.9s of the run).

### 2. `allowlist` — blocking

**Subjects this run:** 26 entries, none stale

**Protects:** `scripts/docs-audit-allow.txt` only shrinks: an entry whose exemption has come true (the thing it excused now resolves) is stale and fails the commit.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** Named directly in D18 ("a generator may write, nothing that writes may gate") as the self-cleaning pattern all the allow-lists in this audit copy.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 26 entries, none stale

**First verdict: KEEP** — Cheap, and the only thing stopping the allow-list from becoming a one-way ratchet of excuses.

### 3. `line anchors` — blocking

**Subjects this run:** 775 line anchors checked, 0 past the target's end (13 allowed), 0 into a split-record stub. The rot rate is measured, never gated. Of 364 checkable code anchors, 253 land away from the identifier they name (a 69.5% miss rate). See `line_anchor_rot`'s own docstring.

**Protects:** A `path:N` or `path:N-M` citation must point at a real line (Clause A) and never into a stub file left by a split record (Clause B).

**Product or docs:** DOCS/PROCESS

**Origin / incident:** D149 is cited directly in the row's own printed measurement. A citation that resolves to a real line is not proof the line still says what the citation claims. D149 is the ruling that no check can see that half. The repo's own hard rules (CLAUDE.md) call line citations a defect class outright. "a line number rots on the next edit above it" and measured 219 of 313 anchors wrong on 2026-09-20.

**False positives:** None found as a docs-audit false positive. The underlying MEASUREMENT is itself a standing red flag: 69.5% of checkable anchors (253 of 364) land away from the identifier they cite. The row does not gate on it — only Clause A/B (line exists, not a stub) are gated.

**Last caught a real defect:** unknown for Clause A/B. The rot rate is printed, never gated, so it has never blocked anything

**First verdict: SHRINK** — The repo's own hard rule says citations should name symbols, not lines (CLAUDE.md, 'A CITATION NAMES A SYMBOL, NEVER A LINE'). This row and its two siblings below spend real machinery on a citation style the project has already ruled against. The prose could stop using line numbers instead.

### 4. `line anchor allowlist` — blocking

**Subjects this run:** 10 entries, none stale

**Protects:** Mirrors `allowlist` for one entry kind: an anchor once past its target's end, now not (target grew or citation fixed), must be removed.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** Same family as `allowlist` (D18 self-cleaning pattern).

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Cheap self-cleaning check, no reason to touch it.

### 5. `line anchor offenders` — blocking

**Subjects this run:** 777 line anchors over 44 files. 777 listed over 44 files. 0 unlisted, 0 stale. Only-shrinks compared against the merge-base 3a71c57a.

**Protects:** No markdown file may write a `path:N` line anchor that the offender list does not already list. A shrinking-only ratchet (777 entries today) on top of `line anchors`.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** Direct sibling of `line anchors` (D149), same 2026-09-20 measurement.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: MERGE** — This and `line anchors` and `line anchor allowlist` are three separate rows enforcing the same disliked citation style. One combined row (or, better, eliminating line-number citations per the hard rule) would cut the machinery to a third.

### 6. `derived numbers` — blocking

**Subjects this run:** 3 marked figure(s) checked against the tree, 3 derivation(s) registered

**Protects:** Every `<!-- derived:<name> -->` marked figure in the markdown is recomputed from `scripts/derived_numbers.py` against the live tree and must match.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 3 markers, 3 registered

**First verdict: KEEP** — Cheap, and it is the mechanism that keeps a hand-typed count (like the app_src_file_count in CLAUDE.md) honest instead of just aging.

### 7. **make targets** — blocking

**Subjects this run:** 1504 references, 118 targets

**Protects:** Every `make X` reference in the markdown names a real Makefile target. Every real target with no `.PHONY` entry (or vice versa) is flagged, both directions.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** The `.PHONY` half is explained in-code with a real incident. Dropping `harness` from `.PHONY` let `make harness` print "up to date" and run zero tests, silently, with docs-audit clean throughout.

**False positives:** SEEN TODAY (per the brief for this audit). The row read an owner's prose quote, 'We just need to make capping...', as a reference to a target named `capping`. A regex over prose text can mistake ordinary English for a make invocation (confirmed again while writing this very file, see the note above the summary table).

**Last caught a real defect:** unknown for a real drift. The `.PHONY` incident above is the closest documented near-miss

**First verdict: KEEP** — The false positive is real but cheap to dismiss by eye. The alternative (silently wrong target references, or a target invisible to `.PHONY`) is worse and has already happened once.

### 8. **pkmnscan commands** — blocking

**Subjects this run:** 14 registered, all documented

**Protects:** Every subcommand `COMMANDS` registers in `cli/__main__.py` is documented, and every documented one is registered.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 14/14

**First verdict: KEEP** — Cheap, symmetric, and the CLI's command table is exactly the kind of list that silently drifts from CLAUDE.md's command block otherwise.

### 9. `harness tests` — blocking

**Subjects this run:** 10 registered and documented

**Protects:** Every test id `harness/run.py`'s `TESTS` registers is documented, and vice versa.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** CLAUDE.md's own text notes there is no T10 (retired to a shelved encoder). A live example of the kind of drift this row exists to catch.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 10/10

**First verdict: KEEP** — Cheap and directly guards a number (test count) the owner reads to judge coverage.

### 10. `pass criteria` — blocking

**Subjects this run:** every threshold matches GATES.md

**Protects:** A harness test's `PASS_CRITERIA` docstring must appear in `docs/GATES.md`'s section for it, word for word.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Prevents the gate record (which the owner treats as an audit trail, D178) from silently disagreeing with what the code actually asserts.

### 11. `criteria wording` — blocking

**Subjects this run:** every criterion is published verbatim

**Protects:** Every criterion sentence is published verbatim in GATES.md — the wording half of `pass criteria`, same function.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** Same as `pass criteria`.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: MERGE** — Same function, same subject, same failure mode as `pass criteria`. Reads as one check split into two printed rows for no reason found in the code.

### 12. `criteria evidence` — blocking

**Subjects this run:** 2 scored run, gate field published

**Protects:** A gate's criterion must name the exact field the scored result file says the gate read, not just a plausible-looking one.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Cheap, and it is what stops a gate's claimed evidence field from quietly pointing at the wrong JSON key.

### 13. `evidence freshness` — advisory

**Subjects this run:** examined nothing — its subject is the STAGED score sources. In a full run there is no staged set at all, which is the row's own declared scope

**Protects:** In `--staged` mode only. A staged edit to what a gate score measures must come with a re-scored result beside it, not a claim resting on a stale run.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** None found in a targeted search.

**False positives:** None found — it examines nothing outside `--staged`, which is expected and pinned (`EXPECTED_EMPTY`).

**Last caught a real defect:** unknown

**First verdict: KEEP** — Correctly scoped to staged mode. Nothing to change. The 'none' in a full run is the row behaving as designed, not a gap.

### 14. `decision ids` — blocking

**Subjects this run:** 302 D + 11 C headings

**Protects:** Every `D<n>` citation in the markdown resolves to a real heading in `docs/decisions/`, and every `C<n>` citation resolves in CODES-DECISIONS.md.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** D72 (a renumbered entry takes its citations with it) and D140/D151 (ids are claimed at merge) are the standing reasons this row exists at all. A D-number is not stable until the claim mechanism runs.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 302 D + 11 C headings, all resolve

**First verdict: KEEP** — This is the single most load-bearing row in the whole audit. 313 decisions are cited constantly across CLAUDE.md, code comments and other docs. D72's own history shows renumbering breaks citations for real.

### 15. `decision ids in code` — advisory

**Subjects this run:** citations in .py, .ts, .tsx, .css and .js all resolve

**Protects:** Same citation check as `decision ids`, but over `.py`, `.ts`, `.tsx`, `.css` and `.js` source comments instead of markdown.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** Same family as `decision ids`. The code-side half exists because CLAUDE.md notes decision ids are cited in code comments too (D173 mechanization pattern).

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Code comments citing a decision id can rot just as easily as markdown can. This is the only row that reads them.

### 16. `decision structure` — blocking

**Subjects this run:** 302 entries, every heading and bold reaches the hook

**Protects:** Every decision entry's heading and bold lead-in is in the shape `scripts/decision-context.py`'s own regex needs, because that hook silently degrades on anything else.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** Directly documented in the check's own comment. Measured before D60, 270 of 1,318 bold runs (20%) were invisible to the hook, with seven entries surfacing nothing but their title. Every audit row green throughout.

**False positives:** None found for the current form. The row falls back to ADVISORY only when `scripts/prose-guard.py` itself cannot be read, which is a defensive branch, not a normal outcome.

**Last caught a real defect:** the pre-D60 270/1,318 miss rate, corrected by whatever change introduced this row

**First verdict: KEEP** — It is the fix for a documented, measured silent-failure mode in a hook the owner actually runs (`decision-context.py`).

### 17. `decision index` — blocking

**Subjects this run:** 301 indexed, matching 302 headings

**Protects:** CLAUDE.md's own D-number index (the big list at the bottom of this file) matches `docs/DECISIONS.md`'s real headings, both directions.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** None found in a targeted search, but this is the direct mechanism behind the note 'D116-D118. D117 exists and slots between them — a third branch's number, resolved on merge' in CLAUDE.md.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 301 indexed against 302 headings (one gap, apparently expected/tracked elsewhere)

**First verdict: KEEP** — The index in CLAUDE.md is exactly the kind of hand-maintained list every session reads and nobody wants to re-derive by hand.

### 18. `id claims` — blocking

**Subjects this run:** 1 unclaimed id(s) on this branch, claimed at the merge

**Protects:** A branch may not carry an unclaimed `D<n>`/`DEBT<n>` id that collides with what main has already claimed. Ids are claimed at merge (D140).

**Product or docs:** DOCS/PROCESS

**Origin / incident:** D140/D151/D182: the whole claim-at-merge mechanism exists because several branches in flight once claimed the same number (see MEMORY.md 'D-number collisions').

**False positives:** None found.

**Last caught a real defect:** the D-number collision incident itself, pre-D140

**First verdict: KEEP** — This is a real, previously-observed collision class (documented in the session's own memory), not a hypothetical.

### 19. `claim vocabulary` — blocking

**Subjects this run:** one slug grammar, declared in the auditor and in the claimer

**Protects:** The slug grammar `make merge`'s claimer uses to allocate a number is the same grammar this auditor checks against.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** Part of the same D140/D182 claim mechanism.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Cheap and it is what stops the claimer and the auditor from silently disagreeing about what a valid slug looks like.

### 20. `entry budget` — advisory

**Subjects this run:** 28 questions

**Protects:** Every decision entry has a byte-size budget (~15,437 bytes). A bigger entry is printed, never blocked, as a nudge to cite instead of re-argue (D60).

**Product or docs:** DOCS/PROCESS

**Origin / incident:** D60 is the origin (dropped the `@`-load and made D-entries opened deliberately).

**False positives:** None found — but the row has printed the same ~28 oversized entries across recent runs with no apparent shrinkage. Is itself worth naming to the owner: an advisory nobody is acting on reads the same as no advisory at all.

**Last caught a real defect:** unknown — never blocks by design, so it cannot be said to have 'caught' anything in the blocking sense

**First verdict: ADVISORY** — Already advisory, and never blocks. The open question for the Opus review. Is a permanently-firing, unacted-on print worth its token cost every run, or should it become a one-time report instead of a per-run row?

### 21. `debts headings` — blocking

**Subjects this run:** 46 headings, every one addressable by `_debts_section`

**Protects:** Every `## ` heading under `docs/debts/` is addressable by `_debts_section` — the reader half of the debts index.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Cheap, mirrors the decisions-heading checks for the debts corpus.

### 22. `debt index` — blocking

**Subjects this run:** 46 indexed, matching 46 headings

**Protects:** `docs/DEBTS.md`'s fenced index matches `docs/debts/`'s real headings, both directions.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Same rationale as `decision index`, for the debts corpus.

### 23. `debt ids` — blocking

**Subjects this run:** 46 entries, citations in docs and code all resolve, the retired path form is gone

**Protects:** Every `DEBT<n>` citation resolves, and a citation using the old (retired) path form has not crept back in.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** The 'retired path form' clause implies a prior format change for DEBT citations. Not found by name in a targeted git log search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Cheap, and it is the DEBT-side mirror of `decision ids`.

### 24. `env vars` — blocking

**Subjects this run:** 55 documented, all real

**Protects:** Every `PKMNSCAN_*`-style variable named in the markdown is one the code actually reads.

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** The module's own header explains why the row cannot name a concrete example env var in its own docstring. Doing so once put that name in its own haystack and broke the check on itself.

**False positives:** The self-referential trap described above is itself a documented near-miss, not a live bug today.

**Last caught a real defect:** unknown

**First verdict: KEEP** — A stale escape-hatch name can sit in prose long after the code stops reading it. Whoever tries to use it hits a real footgun.

### 25. `env names` — blocking

**Subjects this run:** 54 named in code, all documented

**Protects:** The reverse of `env vars`: every `PKMNSCAN_*` the code actually reads is named somewhere in the markdown.

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** Same family as `env vars`.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: MERGE** — Same subject as `env vars`, opposite direction — a natural candidate to report as one row with two counts rather than two rows.

### 26. `hatch state` — advisory

**Subjects this run:** 54 hatches in the roster, none set in this environment or in .claude/settings.json

**Protects:** A guard that has been switched off (an escape hatch like `PKMNSCAN_DOCS=off`) must say so somewhere a session already looks (this file's own header, or CLAUDE.md).

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** None found in a targeted search. This exists precisely because a live, un-flagged bypass is invisible to anyone who did not set it.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 54 hatches, none set here

**First verdict: KEEP** — Directly protects against the failure mode CLAUDE.md's own shell-guard section worries about: a switched-off safety rail that nobody remembers is off.

### 27. `subagent override` — blocking

**Subjects this run:** 2 settings files reachable from this checkout (its own and every nested worktree's), none carrying an undated, expired, or too-far-dated override

**Protects:** A `settings.local.json` raising `CLAUDE_CODE_SUBAGENT_MODEL` must carry a dated, non-expired `_subagentCapUntil`, in this checkout and every nested worktree.

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** MEMORY.md 'settings.local.json is rewritten in-session' documents a real observed defect. The runtime restored an override within the same command, so a session could not clear it from inside itself.

**False positives:** None found as a docs-audit false positive.

**Last caught a real defect:** the settings.local.json rewrite-in-session incident (memory note), which motivated the expiry-scan approach this row takes

**First verdict: KEEP** — Concrete prior incident (owner's own CLAUDE.md rule: 'the raise carries an expiry... the watch reverts it').

### 28. `claim decode` — blocking

**Subjects this run:** 2 claim writers, one vocabulary (6 keys)

**Protects:** The card writer and the box writer decode the same claim vocabulary (the D174/D180 selection grammar).

**Product or docs:** PRODUCT

**Origin / incident:** D174/D180 (a claim on the cards / a selection of cards).

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — A real cross-module vocabulary agreement, not a doc nicety — a drift here would silently corrupt claims.

### 29. `claim clients` — blocking

**Subjects this run:** 2 client writers send exactly what their route decodes

**Protects:** Every client (web app) sends exactly the keys the route decodes, on both doors it can be sent through.

**Product or docs:** PRODUCT

**Origin / incident:** Same D174/D180 family as `claim decode`.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Client/server key agreement is a real correctness question, cheap to check.

### 30. `detector standing` — blocking

**Subjects this run:** 8 published figures against harness/results/detect.json

**Protects:** Figures CLAUDE.md's motion-trigger section publishes are the ones `harness/results/detect.json` actually contains.

**Product or docs:** PRODUCT

**Origin / incident:** D81/D84/D131 (the whole motion-trigger tuning history) are the reason numbers like '140/140, 87ms' exist to be checked at all.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Protects real rig-measurement numbers the owner relies on (capture reliability), not just prose.

### 31. `sole reader` — blocking

**Subjects this run:** examined nothing. Its subject is every zero-argument `Store.history()` call in production code. D191 repointed the three known callers to `Store.history_at(key)`, a call with an argument, so this stays at zero by design.

**Protects:** Counts every zero-argument `Store.history()` call in production code. D191 repointed the three known callers to `history_at(key)`, so this should stay at zero forever.

**Product or docs:** PRODUCT

**Origin / incident:** D191 directly.

**False positives:** None found.

**Last caught a real defect:** unknown — pinned at zero by design

**First verdict: KEEP** — A genuinely well-designed tripwire: it does not need to fire today to be doing its job. The docstring is explicit that a future zero-arg call would be a real full-table-read regression.

### 32. `server concurrency` — blocking

**Subjects this run:** 9 published facts against server/capture_server.py

**Protects:** §11's published facts about `CaptureServer`'s concurrency (REQUEST_SLOTS=4, timeout=15, and the rest) match the real code.

**Product or docs:** PRODUCT

**Origin / incident:** CLAUDE.md's own 'Things you will get wrong' section: measured at 80 Playwright browsers, 969 threads, 338% CPU, answering nothing, fixed by REQUEST_SLOTS=4.

**False positives:** None found.

**Last caught a real defect:** the 969-thread incident itself is the reason these constants are pinned and checked

**First verdict: KEEP** — Directly protects a real, previously-observed production-server meltdown from silently recurring through an un-synced doc/code pair.

### 33. `estimate wire` — blocking

**Subjects this run:** the preflight's cost line is the line `estimate_usd` reads

**Protects:** The identify-flow's cost-preflight string and `estimate_usd` read the same line.

**Product or docs:** PRODUCT

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Money-adjacent (identify spends real API cost) — worth keeping even though cheap and quiet.

### 34. `shipping columns` — blocking

**Subjects this run:** 2 published counts against pipeline/pirateship.py (12)

**Protects:** The Pirate Ship import's column count is published in two files and must agree with the one place that decides it.

**Product or docs:** PRODUCT

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Shipping export correctness is a real operational dependency (Orders/Shipping screens), cheap to check.

### 35. `column count` — blocking

**Subjects this run:** the comment's word against COLUMNS's length (10)

**Protects:** `server/tcg_import.py`'s own comment names a column count that must match the tuple it is describing.

**Product or docs:** PRODUCT

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: MERGE** — Same subject area as `shipping columns` (TCG import column counts). Plausibly the same failure mode checked twice from two ends.

### 36. `threshold agreement` — blocking

**Subjects this run:** app/src/ReviewQueue.tsx:THRESHOLD against pipeline/pricing.py:THRESHOLD

**Protects:** D9's $0.40 threshold, written once in `pipeline/pricing.py` and once in `ReviewQueue.tsx`, must match.

**Product or docs:** PRODUCT

**Origin / incident:** D9 directly (threshold and floor are both $0.40).

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — A real money constant duplicated across Python and TypeScript — exactly the kind of drift a doc-only audit cannot afford to skip.

### 37. `dist path agreement` — blocking

**Subjects this run:** scripts/serve.py:DIST, server/capture_server.py:APP_DIST and vite.config.ts's outDir

**Protects:** The built-bundle path is spelled independently in `scripts/serve.py`, `server/capture_server.py` and Vite's own default `outDir`, and all three must agree.

**Product or docs:** PRODUCT

**Origin / incident:** D138 (one process serves the product) is the decision this three-way agreement protects.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — If these three ever disagreed, `make up` would serve a stale or missing bundle. A real, visible production failure, not a doc nit.

### 38. `import filename agreement` — blocking

**Subjects this run:** server/shipping_routes.py:IMPORT_FILENAME against the Content-Disposition header

**Protects:** The Pirate Ship import filename, a constant in one file and hardcoded in a response header in another, must agree.

**Product or docs:** PRODUCT

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Cheap, and a mismatch here silently breaks a download filename for a real shipping workflow.

### 39. `duplicated measurements` — blocking

**Subjects this run:** cid lookup latency (3 sites), store total (23 sites) and largest drawer (3 sites). A declared list over live code, tests, CLAUDE.md and docs/map.py. Never docs/decisions or docs/specs.

**Protects:** Three specific measurements (cid lookup latency, store total, largest drawer) that were taken once and hand-copied into several files are checked for agreement among the copies. Never against a live re-measurement.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** None found in a targeted search.

**False positives:** The row's own docstring flags its own limit: it checks copies agree with each other, not that any of them is still true.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Cheap and honest about its own limits (a `derived numbers`-style live recompute would be stronger, but this is still better than nothing).

### 40. `router certainty` — blocking

**Subjects this run:** 2 published splits against harness T7 (112 of 331)

**Protects:** The two published join-routing certainty numbers (112 of 331) match harness T7's real result.

**Product or docs:** PRODUCT

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — A real measured statistic (join routing confidence) the owner would otherwise have to trust blindly.

### 41. `work item standing` — blocking

**Subjects this run:** 8 claims in CLAUDE.md against 8 work items declared in §3

**Protects:** Whether an order-pipeline work item (T0-T6) is BUILT/NOT BUILT is decided by reading the spec, and CLAUDE.md's own claims about each must match.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** The order-pipeline spec's own T0-T6 status table (referenced in CLAUDE.md's Map section) is exactly what this guards.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Prevents CLAUDE.md from claiming a feature is built when the spec it points at says otherwise, or vice versa.

### 42. `not-built endpoints` — blocking

**Subjects this run:** 2 declared in order_transport.py, 2 quoted in order-pipeline.md

**Protects:** The two TCGplayer write endpoints this repo has deliberately not implemented are named consistently in `order_transport.py` and `order-pipeline.md`.

**Product or docs:** PRODUCT

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Small, cheap, and it protects a deliberate non-capability from silently being claimed as done.

### 43. `transport standing` — blocking

**Subjects this run:** 2 proven and 1 unexercised calls against 3 readers

**Protects:** Which order-transport calls have actually run live is decided by reading the transport module, never by trusting whatever a doc claims.

**Product or docs:** PRODUCT

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Real-money-adjacent (order transport calls TCGplayer/shipping) — worth the small cost.

### 44. `repo map` — blocking

**Subjects this run:** 463 entries match the tree

**Protects:** Every entry `docs/map.py` claims about the repo matches the tree. The row that fails a commit adding a file with no map entry.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** CLAUDE.md's Hard Rules cite this directly. 'the repo-map row fails a commit adding a file with no map entry' as the mechanized half of the 'scope is argued, not gated' rule.

**False positives:** The module's own SKIP_DIRS comment. A concurrent session's worktree once documented `make worktree-setup` (real on its branch) and this script failed THIS branch's commit because the Makefile here had no such target. Fixed by excluding `worktrees/` from the walk.

**Last caught a real defect:** the cross-worktree false-positive above, which was a real false failure, fixed by 2026-08-29's SKIP_DIRS entry

**First verdict: KEEP** — The most structurally important row after `decision ids` — 463 entries. It is the mechanism CLAUDE.md leans on to keep `docs/map.py` trustworthy at all.

### 45. `hook roster` — blocking

**Subjects this run:** 5 hooks, all in docs/map.py

**Protects:** Every file in `scripts/githooks/` has an entry in `docs/map.py`.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** D135 (Codex reads the same rules) names the hook-mirroring machinery this supports.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Cheap, small roster (5 hooks), and hooks are exactly the kind of file nobody remembers to document by hand.

### 46. `codex hooks` — blocking

**Subjects this run:** 11 hooks in .claude/settings.json, all mirrored in .codex/hooks.json

**Protects:** `.codex/hooks.json` and `.claude/settings.json`'s hooks block name the same hooks, both directions.

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** D135: 'Codex reads this same file, not a copy' — this row is D135's own mechanized check.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Directly enforces a named decision (D135) with a clear, cheap, symmetric check.

### 47. `map sections` — blocking

**Subjects this run:** 5 of 5 sections have a reader, consumer list agrees

**Protects:** Every top-level section of `docs/map.py` has a reader, and the docstring's own consumer list is true.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 5 of 5

**First verdict: KEEP** — Prevents `docs/map.py` from growing a section nobody reads. The same 'a section with no reader is deleted or given one' rule D80 states in prose.

### 48. `gates structure` — blocking

**Subjects this run:** 10 contract entries, 5 run entries, 21 shipped + 2 open steps

**Protects:** The gates corpus (contract/gate-runs/steps files under `docs/gates/`) is non-empty and self-consistent, in both directions.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Cheap structural check on a corpus (docs/GATES.md's real content) the audit's own `pass criteria` and `criteria evidence` rows depend on being readable.

### 49. `build order mirror` — blocking

**Subjects this run:** 23 steps, the same ids in both files, in the same two lists

**Protects:** `docs/map.py`'s SHIPPED/OPEN step ids match `docs/GATES.md`'s two lists, in both directions.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** D80 is the direct source: 'the build order mirror row reconciles both files, in both directions.'

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Directly named in D80's own text as the enforcement for that decision.

### 50. `game vocabulary` — blocking

**Subjects this run:** 5 games, 31 export rarities accounted for

**Protects:** `pipeline/games.py`'s per-game shape (rarities, finishes) matches what the real committed exports actually contain, over two export findings the docstring calls out as unable to false-positive.

**Product or docs:** PRODUCT

**Origin / incident:** D21/D22/D25 (game is a per-card claim. Taxonomies are hand-authored per game and audited).

**False positives:** None found.

**Last caught a real defect:** unknown — currently 5 games, 31 export rarities accounted for

**First verdict: KEEP** — Directly protects the pricing/catalog join across all five supported games — a real, money-adjacent invariant.

### 51. `game coverage` — advisory

**Subjects this run:** 5 committed exports, 0 opt-in

**Protects:** Prints (never blocks) what the committed exports do not corroborate — an advisory-only widening of coverage questions.

**Product or docs:** PRODUCT

**Origin / incident:** D170 (a widening is safe only while the category fits — Pokemon's does not) is the closest named decision on this theme.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Cheap, correctly advisory (D170's own point is that widening coverage needs a human, not a gate).

### 52. `game coverage allowlist` — blocking

**Subjects this run:** 2 entries, none stale

**Protects:** The allow-list for `game coverage`'s advisory findings only shrinks — same self-cleaning pattern as `allowlist`.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** Same D18 self-cleaning pattern.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 2 entries, none stale

**First verdict: KEEP** — Tiny, cheap, correct pattern reuse.

### 53. `matrix superset` — blocking

**Subjects this run:** 48 observed rarity/finish pairs, all allowed

**Protects:** An observed (rarity, finish) pair in the real catalog data must be one `finish_by_rarity` allows. Catches the catalog growing a combination the pricing code does not expect.

**Product or docs:** PRODUCT

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 48 observed pairs, all allowed

**First verdict: KEEP** — Real catalog-drift protection. A new card set can add a combination this row would catch before it silently mis-prices.

### 54. `join key shape` — blocking

**Subjects this run:** 1 composed-key games checked against export Number cells

**Protects:** A `join_key` shape that the export's own `Number` column values prove can never match a real row is flagged. A dead-key detector for the catalog join.

**Product or docs:** PRODUCT

**Origin / incident:** D25/D35 (the join partitions by game. A number that cannot be read falls back to the name).

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — The join is money-critical (mis-joins mean mis-pricing). This is a cheap, targeted correctness check on it.

### 55. `reason codes` — blocking

**Subjects this run:** 15 enumerated, 15 labeled, all defined

**Protects:** The twelve review reasons are reconciled across the three places they are published (roster, labels, code).

**Product or docs:** PRODUCT

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: MERGE** — Heavily overlapping subject with `reason emissions` — both guard the same review-reason vocabulary from two angles. A strong candidate to combine into one row.

### 56. `reason emissions` — blocking

**Subjects this run:** 15 published reasons, 14 with a producer and 1 argued

**Protects:** Every published review-reason code has a real code path that can emit it, and every emitted reason is in the published roster.

**Product or docs:** PRODUCT

**Origin / incident:** None found in a targeted search.

**False positives:** The row's own summary names one argued exception (14 of 15 reasons have a producer, 1 argued). A deliberate, disclosed gap rather than a silent one.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Review-queue reason codes are user-facing text. A reason nobody can produce, or one the UI shows but the roster does not know, is a real UX defect.

### 57. `supervisor self-watch` — blocking

**Subjects this run:** 5 self-files, every module-scope import accounted for

**Protects:** Every project module the process supervisor imports is listed in its own `SELF_FILES` (the files it must not restart itself over).

**Product or docs:** PRODUCT

**Origin / incident:** None found in a targeted search, but MEMORY.md 'A comment about wiring is not the wiring' (janitor.py) is a close sibling failure mode. A supervisor claiming to watch itself when it does not.

**False positives:** None found for this specific row.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Small (5 self-files) and cheap. Protects the supervisor's own self-restart logic. If wrong could bounce the owner's live capture server (a rule CLAUDE.md states explicitly not to do).

### 58. `motion params` — blocking

**Subjects this run:** 19 mirrored constants agree, 0 accounted for

**Protects:** `app/src/motion.ts`'s DEFAULT_PARAMS mirrors `scripts/score-trace.py`'s copy of the same constants.

**Product or docs:** PRODUCT

**Origin / incident:** D81/D84/D130/D131 (the whole motion-trigger tuning saga) is exactly why these constants exist as a mirrored pair at all.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 19 mirrored constants agree

**First verdict: KEEP** — The motion trigger has already been tuned and re-tuned multiple times (D81, D130, D131). A silent drift between the TS and Python copies would quietly undo that tuning.

### 59. `logo parity` — blocking

**Subjects this run:** 6 locked marks, every prism, ground, bracket and base against section 9 (72 hexes)

**Protects:** `markPalettes.ts` and `docs/specs/logo.md` §9 name the same colors for all six locked marks.

**Product or docs:** PRODUCT

**Origin / incident:** D102 (the mark is an illustration with its own palette).

**False positives:** None found.

**Last caught a real defect:** unknown — currently 72 hexes across 6 marks agree

**First verdict: KEEP** — Protects a hand-authored brand asset (the logo) from silently drifting from its own spec.

### 60. `mac icon grid` — blocking

**Subjects this run:** 824/1024 in section 17 and in build-mark.mjs, over 3 inset icons

**Protects:** Apple's icon inset grid number (824/1024) is spelled the same in the spec and in `build-mark.mjs`.

**Product or docs:** PRODUCT

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: MERGE** — Tiny, single-number check that overlaps with the broader `logo parity` family — could be folded in rather than kept as its own row.

### 61. `lockup params` — blocking

**Subjects this run:** 11 settled values against the sheet's holds and the generated geometry

**Protects:** The lockup sheet's declared measurements agree with the settled table in `docs/specs/logo.md`.

**Product or docs:** PRODUCT

**Origin / incident:** Same D102 family.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: MERGE** — Fourth row in the same logo-lockup family. A strong candidate to fold `logo parity`, `mac icon grid`, `lockup bracket`, `rail mark` and `lockup params` into one 'logo spec parity' row with several sub-findings.

### 62. `rail mark` — blocking

**Subjects this run:** the rail bracket is the shipped mark — in the sheet, at both ends of the morph, and on the tab

**Protects:** The sidebar's rail bracket in the design mockup is the same mark the app actually ships, at both ends of the collapse morph.

**Product or docs:** PRODUCT

**Origin / incident:** Same D102 family.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: MERGE** — Same family as `lockup bracket` / `logo parity` / `lockup params` — four separate rows for one locked visual asset.

### 63. `lockup bracket` — blocking

**Subjects this run:** 4 stops against `bluesteel`'s locked bracket

**Protects:** The lockup's dark bracket color is read from the locked `bluesteel` palette, never hand-picked by the sheet.

**Product or docs:** PRODUCT

**Origin / incident:** Same D102 family.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: MERGE** — Part of the same logo/lockup palette-locking family as `logo parity`, `rail mark` and `lockup params` — four rows over one asset.

### 64. `withhold reasons` — blocking

**Subjects this run:** 3 authored, offered by the screen, none unreachable

**Protects:** The three withhold reasons are reconciled across the two languages (Python/TypeScript) that declare them.

**Product or docs:** PRODUCT

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: MERGE** — Part of a family of near-identical 'small enum, two languages, must agree' rows (with order reasons, terminal statuses, reason codes). Candidate to generalize into one 'cross-language enum agreement' row that lists each vocabulary's own count.

### 65. `order reasons` — blocking

**Subjects this run:** 6 authored, offered by the screen, none unreachable

**Protects:** The six order-line reasons are reconciled the same way as `withhold reasons`.

**Product or docs:** PRODUCT

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: MERGE** — Same cross-language-enum family as `withhold reasons`.

### 66. `terminal statuses` — blocking

**Subjects this run:** 3 authored, published in D63, none unreachable

**Protects:** The three terminal order statuses are reconciled between the code and D63's own published claim.

**Product or docs:** PRODUCT

**Origin / incident:** D63 (the order ledger is two maps).

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: MERGE** — Same cross-language-enum family. Also the one row in the family that cites its governing decision (D63) directly, so if these get merged this is the natural anchor entry.

### 67. `pricing presets` — blocking

**Subjects this run:** 3 priced, written by the screen, key rule and basis agree

**Protects:** The three pricing presets are reconciled between the pricing tuple and the table the screen writes from.

**Product or docs:** PRODUCT

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: MERGE** — Same cross-language/cross-module small-vocabulary-agreement family.

### 68. `export request` — blocking

**Subjects this run:** 3 catalogue filters and 2 live query parameters, each at its measured value

**Protects:** Three fields of the catalogue export request are pinned DECISIONS (not incidental defaults) and this row checks the code still uses those exact values.

**Product or docs:** PRODUCT

**Origin / incident:** D64/D65/D166 (the export is fetched. Completeness is a delta. The export is a property of the game).

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — These are deliberate, decided values (not defaults) per the row's own summary. Worth a mechanized check precisely because a 'helpful' code change could silently override a decision.

### 69. `transport promise` — blocking

**Subjects this run:** 1 host, 2 methods, 3 routes, as promised and as called

**Protects:** `server/tcg_export.py`'s own first-bullet promise (host, methods, routes) matches the constants and calls beneath it.

**Product or docs:** PRODUCT

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — A file's own header claim checked against its own body — cheap, catches a doc-in-code drift specifically.

### 70. `hint reasons` — blocking

**Subjects this run:** 9 refusals reachable from filters(), 11 labeled by the screen

**Protects:** The capture screen's refusal labels match the refusals the route can actually send (9 refusals, 11 labels).

**Product or docs:** PRODUCT

**Origin / incident:** D76/D170 (a hint is evidence about its own card. A widening is safe only while the category fits).

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — User-facing refusal text (a real screen message) drifting from the reasons the server can send would confuse the operator mid-capture. Cheap to check, real cost if wrong.

### 71. `tested_by reach` — blocking

**Subjects this run:** 69 claims, every cited test reaches what it names

**Protects:** Every `tested_by` claim in `docs/map.py` (this test proves this file) is checked against what the cited test file actually imports.

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** CLAUDE.md's Map section calls out '`tested_by reach`. 69 claims, every cited test reaches what it names' as a real class of prior drift risk.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Prevents `docs/map.py` from claiming a file is 'tested by' a test that does not actually import it. A real, previously-plausible failure mode for a hand-maintained map.

### 72. `status sources` — blocking

**Subjects this run:** 15 declared, all resolve

**Protects:** `make status` reads a declared list of files. This row verifies every one of them actually exists / is readable.

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 15 declared, all resolve

**First verdict: KEEP** — Cheap, and `make status` is a command every session runs first.

### 73. `design tokens` — blocking

**Subjects this run:** 123 declared tokens, every one named by the block. 35 hexes compared across both themes

**Protects:** The locked palette in `docs/DESIGN.md` matches the `--bn-*` custom properties the app actually renders, in both themes.

**Product or docs:** PRODUCT

**Origin / incident:** CLAUDE.md: '`--bn-*` tokens only... `make docs-audit`'s design tokens row locks every name and hex both ways.'

**False positives:** None found.

**Last caught a real defect:** unknown — currently 123 tokens, 35 hexes across both themes

**First verdict: KEEP** — Directly enforces the single design-token rule the whole front end depends on (D94's `--bn-*` vocabulary).

### 74. `raw color` — blocking

**Subjects this run:** every color in 38 sheets comes from a token

**Protects:** Every color in every stylesheet under `app/src` traces back to a token — no hex literal outside `tokens.css`.

**Product or docs:** PRODUCT

**Origin / incident:** Same D94/design-tokens family.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 38 sheets clean

**First verdict: KEEP** — This is the mechanized half of 'app/src/tokens.css is the only file that may name a color' — a real, screen-facing rule.

### 75. `breakpoints` — blocking

**Subjects this run:** 179 blocks over 19 media widths in 25 sheets, all on the ladder. 4 named containers, each with a reader

**Protects:** Every `@media` width under `app/src` is on the documented breakpoint ladder in DESIGN.md.

**Product or docs:** PRODUCT

**Origin / incident:** D123 (above the desk a screen asks its column, not the window).

**False positives:** None found.

**Last caught a real defect:** unknown — currently 179 blocks over 19 widths, all on the ladder

**First verdict: KEEP** — Prevents an improvised, undocumented breakpoint from creeping into a real stylesheet.

### 76. `breakpoint columns` — advisory

**Subjects this run:** 2 questions

**Protects:** A stylesheet can open a `min-width` regime on the raw VIEWPORT. Inside a layout where the real available width is the viewport minus a rail, that regime cannot tell two different real widths apart.

**Product or docs:** PRODUCT

**Origin / incident:** D123 directly, and the row currently has two live, real findings (CaptureScreen.css line 1317, RunPanel.css line 13). This is an ADVISORY row that is actively catching something today.

**False positives:** None found.

**Last caught a real defect:** IT IS CATCHING SOMETHING RIGHT NOW: 2 real findings in the current tree, not a historical example

**First verdict: KEEP** — One of the few rows in this audit with a live, unresolved finding today. Strong evidence it is doing real work, not just standing guard over nothing.

### 77. `js breakpoints` — blocking

**Subjects this run:** 7 JS breakpoints in 5 files, each paired to its own imports. 0 unpaired

**Protects:** A JS media-query width must match one the stylesheets that same file imports already declare. A JS breakpoint may not invent its own number (D123).

**Product or docs:** PRODUCT

**Origin / incident:** D123. A commit message search found two dedicated commits ('Pair a JS breakpoint by import graph, not a global sweep') rebuilding this exact check's approach.

**False positives:** None found as a false positive. The two 'pair by import graph' commits suggest the FIRST version of this check (a global sweep) DID false-positive or under-match. Was rewritten.

**Last caught a real defect:** the two 'pair a JS breakpoint by import graph' commits. They are evidence the row itself was buggy once, and got fixed.

**First verdict: KEEP** — Has direct evidence of iteration (rewritten at least once to fix its own matching logic). Is a good sign it is taken seriously rather than write-once-forget.

### 78. `storage keys` — blocking

**Subjects this run:** 11 device-local keys against CLAUDE.md's roster, 2 session keys all named in markdown

**Protects:** Every `localStorage`/`sessionStorage` key the app actually writes is named in CLAUDE.md's roster, and vice versa.

**Product or docs:** PRODUCT

**Origin / incident:** D27 (session state is device-local) plus CLAUDE.md's own long, explicit key-by-key list. A roster this detailed is exactly what drifts without a check.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 11 device-local + 2 session keys, all named

**First verdict: KEEP** — Directly guards a long, hand-maintained, security/privacy-adjacent list (what this app persists on a shared device).

### 79. `views opsec` — blocking

**Subjects this run:** 10 of 10 views resolve in ROUTES, none address the photo service. 10 routes rendered, 4 declared off

**Protects:** The MECHANICAL half of D24's opsec rule. A screenshot manifest line must resolve to a real route and must never address the raw photo service directly.

**Product or docs:** PRODUCT

**Origin / incident:** D24 (code cards are pooled inventory) and the 7b incident named directly in the row's own docstring. 'sixteen confident measurements of an unregistered route.'

**False positives:** None found.

**Last caught a real defect:** the 7b unregistered-route incident named in the row's own docstring

**First verdict: KEEP** — Directly protects against leaking a bearer-instrument code-card photo through the screenshot pipeline. One of the highest real-stakes rows in this whole audit (real money, per CLAUDE.md's code-cards section).

### 80. `views exposure` — off

**Subjects this run:** examined nothing — turned OFF 2026-09-23 while code cards are dormant (CLAUDE.md) — VIEWS_EXPOSURE_ENABLED is False, so this row examines nothing on purpose

**Protects:** The ADVISORY half of the same D24 rule: a route whose component subtree can reach the photo service. The script can see but not judge (needs runtime state).

**Product or docs:** PRODUCT (disabled)

**Origin / incident:** D24, same as `views opsec`. Explicitly turned OFF 2026-09-23 because code cards are DORMANT (CLAUDE.md's own marker section).

**False positives:** None found. The row is deliberately silenced, not broken.

**Last caught a real defect:** unknown — was never observed to catch anything before being turned off

**First verdict: KEEP** — Correctly OFF while the feature it guards is dormant. CLAUDE.md itself says to flip `VIEWS_EXPOSURE_ENABLED` back to True when code-card work resumes. One item to flag: nothing re-checks that this flag gets flipped back. That is a human commitment, not a mechanized one.

### 81. `doc hygiene` — advisory

**Subjects this run:** 20 questions

**Protects:** Three unrelated defects in one row. A markdown file citing a code line the file no longer has, prose that reads as a literal leftover editor instruction ('Insert after line 185...'). A file with two top-level headings.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** The editor-instruction clause has a documented real incident in its own comment. A real instruction, 'Leave lines 37-38... Insert a blank line and this blockquote after line 38,' was pasted into a spec. That paste DELETED the very sentence it was meant to preserve.

**False positives:** None found as a false positive. The row is currently catching 20 real, live findings (8 stale line citations, 10 leftover editor instructions in docs/specs/store-scaling/*, 1 double-H1 in a vendored README).

**Last caught a real defect:** IS CATCHING REAL DEFECTS RIGHT NOW. 10 leftover editor-instruction fragments sit in docs/specs/store-scaling/*.md. 8 stale line citations sit in the 2026-09-20 UX review docs.

**First verdict: KEEP** — One of the highest-value rows in the whole audit by direct evidence. 20 live findings today, including the exact 'pasted an instruction as prose and lost a sentence' incident its own comment warns about. Worth flagging that it bundles three unrelated defect shapes under one label. Splitting would make which fired easier to read at a glance, but the content is real and worth keeping.

### 82. `route rosters` — blocking

**Subjects this run:** 2 declared rosters against 14 registered routes

**Protects:** A hand-typed route list in a spec file matches `App.tsx`'s own `ROUTES` table.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** D227/D291 and the 'census' paragraph in CLAUDE.md name this exact failure mode (route counts stated three different ways).

**False positives:** None found.

**Last caught a real defect:** unknown — currently 2 rosters against 14 routes

**First verdict: KEEP** — Route counts are cited constantly in CLAUDE.md and specs. This is the one row proving a hand list did not drift from the real table.

### 83. `recorded deletions` — blocking

**Subjects this run:** 5 recorded deletions, 13 needles over 6 roots and 243 files. 1 narrated in prose

**Protects:** A symbol a decision records as deleted must not exist in the code. Catches a merge silently restoring something a decision says is gone.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** MEMORY.md 'Merges can revert settled work': PR #221 silently restored the D119 hero after a merge, caught by exactly this mechanism.

**False positives:** None found.

**Last caught a real defect:** the PR #221 D119 hero regression, a real caught defect

**First verdict: KEEP** — Has a named, real catch (PR #221) in the session's own memory. One of the few rows here with unambiguous evidence of stopping a real regression.

### 84. `spec seal` — blocking

**Subjects this run:** 40 specs sealed against the capture port

**Protects:** Every spec file that mounts the app seals this checkout's own capture port, and seals it before anything else runs.

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** D43/D261 (port-per-checkout) family — a spec not sealing the port first risks colliding with another checkout's server.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 40 specs sealed

**First verdict: KEEP** — Directly protects the port-isolation invariant (D43/D261) that makes concurrent worktree testing safe at all.

### 85. `verdict file` — blocking

**Subjects this run:** .serve/design-check.json agreed by the reporter, the config, 2 recipes and the prose

**Protects:** .serve/design-check.json is named identically by the reporter, the Playwright config, both `make` recipes and the prose describing it.

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** D129 (the verdict's line is fixed by the first Playwright that counts it right).

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — D129 exists because of real prior confusion about what a passing design-check run means. This row keeps the file name itself from drifting apart across five places.

### 86. `route census` — blocking

**Subjects this run:** 11 published counts against 14 routes (13 owner), 9 owner renders in the manifest

**Protects:** Every published route/screen count anywhere in the repo (CLAUDE.md, README, docs/map.py) matches `App.tsx`'s `ROUTES` table.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** MEMORY.md 'Doc citations are spelled three ways': three sessions got three different route/section totals for one search.

**False positives:** None found.

**Last caught a real defect:** the three-different-counts incident that motivated this row

**First verdict: KEEP** — Named incident. Route counts are exactly the kind of number that gets typed once and then never updated as screens are added or retired.

### 87. `check registry` — blocking

**Subjects this run:** 60 checks in recipe order, 59 in ci-check, 1 declared non-gating

**Protects:** `scripts/checks.py` (or whatever runs `make check`) matches the actual `check:` recipe, both directions.

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** CLAUDE.md's own comment at the Makefile's `check` target says this directly. An earlier compressed description of `make check` 'WAS WRONG' and this row (plus `check census`) is what would have caught it.

**False positives:** None found — but the row's own history (the comment) is itself a documented near-miss that shipped before the row existed.

**Last caught a real defect:** the wrong compressed `make check` description, pre-dating this row

**First verdict: KEEP** — Directly protects the one command (`make check`) every merge depends on being accurately described.

### 88. `commit path` — blocking

**Subjects this run:** 2 of 60 on the commit path, 2 of them read against source, none writing

**Protects:** D18 ('a generator may write, nothing that writes may gate'), asserted mechanically: of the checks on the commit path, none may write.

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** D18 itself. The row's own docstring calls it 'D18, asserted mechanically for the first time.'

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — This is the row that makes D18 a fact about the code rather than a promise in prose. Worth keeping precisely because it is rare and structural.

### 89. `check census` — blocking

**Subjects this run:** 2 published lists, 60 checks each, in the `check:` recipe's order

**Protects:** Every published list of what `make check` runs (in docs) matches `scripts/checks.py`, and matches the same list in two places.

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** Same family as `check registry` (the wrong-compressed-description incident).

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: MERGE** — Overlaps heavily with `check registry`. Both exist to stop the same class of drift (a wrong description of what `make check` runs) and could plausibly be one row with two evidences.

### 90. `no mechanism on screen` — blocking

**Subjects this run:** 2694 visible strings carry none of it (3 allow-listed hit(s) over 3 entries, none stale)

**Protects:** No user-visible string in `app/src` may name a decision id, a repo path, or a pipeline-internal noun (D196).

**Product or docs:** PRODUCT

**Origin / incident:** D196 directly. CLAUDE.md: 'No user-visible string may name a decision, a repository path, or a pipeline-internal noun.'

**False positives:** None found, but the row itself allow-lists 3 hits over 3 entries today. Meaning it has already needed hand exceptions, which is worth watching for growth.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Directly screen-facing (a leaked internal noun on a real screen is a visible defect the owner would notice and dislike). Scans 2,694 real strings.

### 91. `typed interpunct` — blocking

**Subjects this run:** 4 typed dots. 4 listed over 1 files (kit-frame 4). 0 unlisted, 0 stale. Only-shrinks compared against the merge-base 3a71c57a.

**Protects:** No user-visible string may TYPE a middle dot/bullet as a separator. A separator may only be drawn in CSS (D41/D218/D280).

**Product or docs:** PRODUCT

**Origin / incident:** D41 (typed the fix originally), D218 ('a typed dot is a defect wherever it is typed'), D280 (turned the pinned count into an offender list).

**False positives:** None found.

**Last caught a real defect:** the original D41 defect this whole family exists to prevent recurring

**First verdict: KEEP** — Small (4 typed dots today, all listed), cheap, and tied to an owner ruling stated twice (2026-09-19 and D280). Clearly something the owner cares about by name.

### 92. `ste offenders` — blocking

**Subjects this run:** 11352 offending sentences (11843 findings. 811 exempted: {'table row': 719, 'decision citation': 3, 'VS Code': 3, 'via': 86}) over 509 files. 11352 listed over 357 files (docs-sweep 11352). 0 unlisted, 0 stale. Only-shrinks compared against the merge-base 3a71c57a. Repo ratio 10.791/1,000 words, against the survey's floor of ~2.714/1,000 words (docs/specs/ste-false-positives.md). Printed, never gated.

**Protects:** No markdown sentence may break one of the four ERROR-severity Simplified Technical English rules unless `scripts/ste-offenders.json` names it. The list may only shrink (D226/D280).

**Product or docs:** DOCS/PROCESS

**Origin / incident:** D226 (mechanized the STE rule) and D280 (turned a pinned count into an offender list). MEMORY.md 'STE mechanization 2026-09-19' documents the original measurement effort.

**False positives:** None found as a docs-audit false positive in a targeted search, but the row's own printed summary is a red flag on cost/value. 11,352 pre-existing offending sentences, all pre-listed, 0 unlisted, 0 stale. Meaning on a normal commit this row can only ever confirm the count did not grow, never actually improve prose.

**Last caught a real defect:** unknown whether it has ever blocked a real new violation. The printed ratio is informational only. The gate itself just asks whether the allow-list only shrank.

**First verdict: SHRINK** — By far the most expensive row in the whole audit. 18.1s of a 47.2s profiled run, about 38%, and roughly half of the unprofiled 37s run. It gates only a no-growth invariant over an 11,352-entry list. The real prose-quality number (10.791 per 1,000 words, against a 2.714 floor) is explicitly 'printed, never gated.' Worth asking the owner directly whether the gated half is worth ~14s of every full run. An on-demand target, the way `make text-density` already works for screen copy, is one option.

### 93. `suite lock` — blocking

**Subjects this run:** 1 fleet script behind the lock, 2 serial renderers still serial

**Protects:** Every Makefile recipe that starts a Playwright fleet goes through the one machine-wide lock (D122).

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** D122 directly.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 1 fleet script behind the lock, 2 serial renderers still serial (as expected)

**First verdict: KEEP** — Protects against two Playwright fleets fighting over the same CPU, a real, previously-designed-around constraint (D122).

### 94. `browser scope` — blocking

**Subjects this run:** 9 entries cover 18 derived dependencies, read fail-open

**Protects:** `scripts/browser-scope.py`'s SCOPE list matches what the browser test suite actually loads, both ways (D141).

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** D141 directly (the browser matrix runs only when the change reaches what a browser draws).

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — This is what keeps CI's path-gating (D141) honest — a stale SCOPE either wastes CI time or silently skips real UI changes.

### 95. `spec map` — blocking

**Subjects this run:** 44 specs, 191 files reached, shell closure checked

**Protects:** `browser-scope.py`'s spec map (which Playwright specs load) matches `app/tests/` and the shared surfaces it names, both ways (D215).

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** D215 directly.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 44 specs, 191 files reached

**First verdict: KEEP** — Same CI-gating family as `browser scope`. Costs 2.5-3.2s per run (the third most expensive row measured). Is a fair price for keeping a CI cost-saving mechanism from silently under- or over-scoping.

### 96. `serve scope` — blocking

**Subjects this run:** 14 entries against 11 carried names, both ways

**Protects:** `serve-scope.py:SCOPE` matches `serve-selftest.py:CARRY`, both ways.

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** CLAUDE.md names `make serve-scope` directly as the first path-gated target (2026-09-17 to 2026-09-20) and quotes its own cost (70.1s of `make check`'s total).

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Directly protects a named, previously-measured CI cost optimization (see MEMORY.md's verification-cost-measured note) from silently drifting out of scope.

### 97. `guard scope` — blocking

**Subjects this run:** 22 roster entries against 22 wired Makefile recipes, both ways

**Protects:** `guard-scope.py:ROSTER` matches the Makefile's own wiring of guard self-tests, both ways (D247).

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** D247 directly. CLAUDE.md's `make guard-scope` section explains the roster's derivation and growth history in detail.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 22 roster entries against 22 wired recipes

**First verdict: KEEP** — Recently and deliberately extended (D247, six more self-tests added 2026-09-23) — an actively maintained mechanism, not legacy cruft.

### 98. `check numbering` — blocking

**Subjects this run:** no check named by position

**Protects:** In `--staged` mode: no check may be cited in the staged markdown by its position ('the third check') instead of its label.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: MERGE** — Same underlying concern as `numbering in code` (below) — a citation-by-position ban, checked twice from two file types.

### 99. `numbering in code` — advisory

**Subjects this run:** comments name checks by label

**Protects:** Comments in code must name a check by its label, never its position in a list.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** Same family as `check numbering`.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: MERGE** — Pair with `check numbering` — same rule, two surfaces (markdown against code comments). Could be one row with two counts.

### 100. `audit invocation` — blocking

**Subjects this run:** 3 callers, flags all declared, usage 64 clear of advisory 2

**Protects:** Every flag a caller passes this script (the git hook, `make docs-audit`, the `/docs-audit` skill) is a flag this script's own parser declares.

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** The module's own docstring explains the EXIT_USAGE=64 design. It exists to make a broken caller loud, rather than let it fall silently into the advisory (exit 2) branch.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 3 callers, all flags declared

**First verdict: KEEP** — Directly protects against the one failure mode the module's docstring calls out by name. A caller with a stale flag reading as a routine advisory instead of a broken auditor.

### 101. `identifier spelling` — blocking

**Subjects this run:** every identifier in 450 files is spelled American

**Protects:** Every identifier in 450 files is spelled American, never British, so a session grepping for the American form finds every instance.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** None found in a targeted search.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: SHRINK** — Fourth most expensive row (5.9s, mostly one subprocess call per file — 450 `git`/external calls per run). The rule is reasonable. The implementation (subprocess-per-file rather than one in-process pass) is the likely place to cut cost, not the check itself.

### 102. `shell substitution` — blocking

**Subjects this run:** no double-quoted shell string in 19 files runs a command by accident

**Protects:** No double-quoted shell string in the scripted files runs a command by accident through an unescaped backtick.

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** A MEMORY.md-adjacent family. This repo's own history has other shell-quoting incidents, such as 'gh api -f turns a GET into a POST.' Unescaped shell substitution has bitten it before.

**False positives:** None found.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Real security/correctness class (accidental command execution through backtick substitution), cheap to check, matches a documented pattern of shell-quoting bugs elsewhere in this repo.

### 103. `unscoped walk` — blocking

**Subjects this run:** 11 full-table reads of inventory.cards found, 11 allowed (pinned at 11)

**Protects:** Every full-table read of `inventory.cards` is in an allow-list that starts at the 2026-09-12 census and may only shrink.

**Product or docs:** PRODUCT

**Origin / incident:** MEMORY.md '_copies_out is a full-table pass': ~1s per call on the real store, a real performance defect the owner hit.

**False positives:** None found.

**Last caught a real defect:** the `_copies_out` full-table-scan performance defect that motivated the census

**First verdict: KEEP** — Directly ties to a real, previously observed performance regression on the owner's own store size.

### 104. `import layering` — blocking

**Subjects this run:** 17 store/ files scanned, 0 import pipeline/

**Protects:** `store/` may not import `pipeline/` (D63): the dependency arrow runs one way only.

**Product or docs:** PRODUCT

**Origin / incident:** D63 directly.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 0 violations across 17 files

**First verdict: KEEP** — Architectural layering rules rot silently without a mechanized check. This is cheap and exactly matches a named decision.

### 105. `identity writers` — blocking

**Subjects this run:** 43 direct card.<field> assignment(s) found, all inside the 6 sanctioned writers or the 0 pinned exception(s)

**Protects:** Every `card.<field> = ...` assignment for an identity/binding field happens inside one of the six sanctioned writer methods (identity-follows-sku.md, D173's own worked example).

**Product or docs:** PRODUCT

**Origin / incident:** D258 (identity follows the SKU) and D173 ('a rule that can be mechanically enforced must be') both name this exact mechanism.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 43 assignments, all inside the 6 sanctioned writers

**First verdict: KEEP** — A named, deliberate example of D173's own rule — real data-integrity protection for card identity, not documentation.

### 106. `rule enforcement` — blocking

**Subjects this run:** 14 hard rules: 9 name a mechanism that resolves, 5 argue why none can (pinned at 5)

**Protects:** Every hard rule in CLAUDE.md either names a mechanism that resolves, or argues why none can (D173) — pinned floors for both counts.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** D173 directly: 'a rule that can be mechanically enforced must be.' This is D173's own top-level audit.

**False positives:** None found.

**Last caught a real defect:** unknown — currently 14 hard rules: 9 mechanized, 5 argued as unmechanizable, both pinned

**First verdict: KEEP** — This is the meta-rule that governs every other row in this whole audit. Arguably the single most important row for the Opus reviewer to weigh, since D173 is the reason most of these 108 rows exist at all.

### 107. `check dispatch` — blocking

**Subjects this run:** every check defined here is called by audit()

**Protects:** Every `check_*` function defined in this file is actually called by `audit()`. The row that catches a check being defined and silently never wired in.

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** The row's own long comment states plainly it 'DOES NOT ANSWER FOR ITSELF' and is provably incomplete as self-verification. Only `--self-test` (run by hand, on no gate) actually proves it, and the comment says an earlier draft wrongly claimed otherwise.

**False positives:** None found as a live false positive. The row's own comment documents a near-miss in its OWN prior description of itself (an earlier draft over-claimed what this row proves).

**Last caught a real defect:** unknown

**First verdict: KEEP** — Cheap and structurally necessary, but its own docstring is the audit being honest about its own blind spot. Worth flagging to the owner as a standing, acknowledged gap (a check that could vanish and nothing would notice except a hand-run `--self-test`).

### 108. `subject counts` — blocking

**Subjects this run:** 107 rows, every one declaring its subject. 3 examined nothing, all pinned

**Protects:** Every row above declared how many subjects it examined. A row examining zero must be pinned in `EXPECTED_EMPTY` with a reason, or it fails.

**Product or docs:** PROCESS (test/CI meta)

**Origin / incident:** The row's own comment: 'AFTER EVERYTHING, because its subject is the other rows' subject counts.'

**False positives:** None found.

**Last caught a real defect:** unknown — currently 107-109 rows, 3 examined-nothing, all pinned

**First verdict: KEEP** — This is the row that stops any OTHER row from silently going quiet (finding nothing to check and reporting a false 'ok'). A real meta-protection, cheap to run.

### 109. `coupling` — advisory (staged-only)

**Subjects this run:** runs in --staged only, over the source groups this commit touched

**Protects:** In `--staged` mode only. A commit touching a named source group (pipeline/, harness/, Makefile) by 20 or more lines asks whether the paired doc changed too.

**Product or docs:** DOCS/PROCESS

**Origin / incident:** D16 directly — this is D16's own worked mechanism (Layer 2 coupling).

**False positives:** None found. Only runs pre-commit with something staged, so it never showed in the full-tree run this audit is based on.

**Last caught a real defect:** unknown

**First verdict: KEEP** — Only fires at commit time on real, sized changes — cheap, narrowly scoped (3 source groups). The only row that reads the actual diff rather than the whole tree.

## Top 5 cut / downgrade / merge candidates

1. **`ste offenders`** (SHRINK) — 38% of the full run's cost for a gate that only checks
   "did the 11,352-entry offender list grow," never the prose quality itself (that ratio is
   printed, never gated). Ask whether the gated half belongs in `make check` at all, or
   should move to an on-demand target the way `make text-density` already does for screen
   copy.
2. **`line anchors` / `line anchor allowlist` / `line anchor offenders`** (SHRINK/MERGE) —
   three rows and a 777-entry allow-list defending a citation style (`path:N`) that
   CLAUDE.md's own hard rules already call a defect ("a citation names a symbol, never a
   line"). The measured rot rate is 69.5% and is printed, never gated. Fixing the
   underlying citations (moving them to symbol form) would let this whole family shrink.
3. **The logo/lockup family** (`logo parity`, `mac icon grid`, `lockup bracket`,
   `rail mark`, `lockup params`) (MERGE) — five separate rows, all checking one locked
   visual asset (the Banchi mark, D102) against its own spec from five angles. Candidate
   to fold into one row with five sub-findings.
4. **The cross-language small-enum family** (`withhold reasons`, `order reasons`,
   `terminal statuses`, `pricing presets`, and `reason codes`/`reason emissions`) (MERGE) —
   six rows doing the same shape of check (a short vocabulary must agree between Python and
   TypeScript, or between a roster and its producers). One generalized row naming each
   vocabulary would read the same and cost the same.
5. **`identifier spelling`** (SHRINK, implementation only) — the fourth most expensive row
   (5.9s), driven by one `subprocess` call per file (450 calls) rather than one in-process
   pass. The rule is sound. The cost is an implementation choice, not the check's value.

Two rows deserve the opposite flag — direct, live evidence they are working today, not
standing over nothing: **`breakpoint columns`** (2 real findings right now) and
**`doc hygiene`** (20 real findings right now, including the exact "pasted an editor
instruction as prose and lost a sentence" failure its own code comment warns about).
