## D-a-row-that-examined-nothing-says-so — A row declares how many subjects it had, an empty one is pinned by name with a reason, and eleven published claims get the reader they were already cited as having

**`Report.render` printed `ok` for any row whose findings list was empty, so a row that examined 2,964 references and a row that examined NONE were the same word.** This is the repo's signature defect stated exactly: a guard that cannot tell *nothing is wrong* from *nothing is known yet*. Measured inside a green `make check` on main: `paths 0 references resolve`, the make-target row's `0 references, 57 targets`, and `env vars 0 documented, all real`. A session then quoted that run as verification.

**Eighteen instances were catalogued, including `make check` itself, and nine of them landed in twenty-four hours.** Two were docs rows passing while reporting `0 entries` over an emptied corpus — which is why `corpus_is_empty` already exists. Nothing generalised it, so the fix arrived once per row, after the fact, for as long as anybody noticed.

### The reporting layer

**Every row declares a subject count.** `Report.checks` holds a `Row` NamedTuple carrying `scanned`; the render prints `none` where it is 0 and `bare` where the row declared nothing at all; `--json` carries the integer and a `vacuous` flag, because `python3 scripts/docs-audit.py --json` is what a session greps instead of reading a hundred rows. Most rows already printed a count in PROSE and asserted no floor on it, which is how a moved walk root, a renamed directory, an edited suffix list and an unreadable corpus all render as clean.

**`subject counts` is the new row and it is MECHANICAL.** Four findings, kept apart because they have four different repairs: a row that declared no count, an unpinned zero, a `staged` pin whose row is empty in a full run, and a pin naming a row this file no longer emits. It was proposed as informational; a tag nothing can fail on is the state this row exists to end, and `exit 2` in this repo carries 23 standing findings as the proof of what that costs.

**A row with findings is not its subject.** The defect is the vacuous `ok`, and a row rendering FAIL or ask is not rendering it. That also keeps the error paths honest-looking — the make-target row with no Makefile to read adds a finding and no count, and "declared no subject count" beside it would point at the wrong thing. A row whose CLEAN path declares no count is caught the first time that path is taken, which is the first time it could mislead anybody.

**`EXPECTED_EMPTY` pins nine rows by name, with the reason beside each and the MODE it applies in.** Six are `--staged` narrowings — they count something read out of the markdown, which a code-only commit does not stage — and the same zero in a full run is a broken walk and still fails. Three are empty on a clean tree in every mode: an empty allowlist is the ideal state, `evidence freshness` has no staged set to read in a full run, and `id claims` finds no unclaimed slug on main BY THE INVARIANT it asserts. A blanket exemption is how a rule stops being one; the six doc rows that count a CODE-side roster instead are deliberately NOT pinned, because zero there means `TESTS` or `COMMANDS` or the corpus is empty.

**Five silent `return`s deleted their own row from the render.** `raw color`, `logo parity`, `lockup bracket`, `rail mark` and `lockup params` each vanished when their subject was absent, and an absent row is the one state nothing in that file reads — the blind spot `check dispatch`'s own comment records about itself. They emit a row with `scanned=0` now, which `subject counts` fails the commit on.

### The eleven rows, and the five live defects they found

Each was a published claim with a reader that could not see the half that mattered. **Five were already wrong on main.**

| row | what it now reads | found |
| --- | --- | --- |
| `criteria evidence` | `payload[field]`, compared numerically against the floor PASS_CRITERIA publishes | — |
| `check census` | the token SEQUENCE of both published `make check` lists | both lists in the pre-D161 order |
| `harness tests` | every present-tense count in `harness/run.py`'s own docstring | it said eight, three times, against nine |
| `check registry` | the `ci-check` recipe, and `gates: False` against a `NOT A GATE:` marker | — |
| `views opsec` | a render's filename against the route it draws, plus `OFF_RENDER` | `capture` rendered `#/`, which is Home |
| `views opsec` | a manifest line with no proof selectors | — |
| `storage keys` | D27's fenced session roster, both directions | the fence said eight, the app writes two |
| `server concurrency` | CLAUDE.md's copy of the four attributed literals | — |
| `recorded deletions` | six scan roots, five deletions, thirteen needles | `do_order_fill` published as gone |
| `estimate wire` | the money button's figure against the line that produces it | — |
| `hatch state` | any `PKMNSCAN_*` hatch set in this environment or committed in settings | — |

**`criteria evidence` is the one worth reading twice.** It tested whether the string `holdout_accuracy` occurred inside PASS_CRITERIA's own prose and never opened `payload[field]`, so a run recording `null` — or 0.40 — printed `ok` over the number that decides whether it is safe to spend money on a Batch submission. The identical mistake had already been measured ONE ROW OVER, where `check_pass_criteria` was green while a lowered `>= 0.9` sat inside the published `0.95`. The lesson did not travel twenty lines.

**`estimate wire` is anchored on the producing CALL and never on the wording**, which is the whole of what it gets right: the defect is somebody rewording the sentence, and a reader that found the site BY its wording could not see the change it exists to catch. It also keeps `cmd_identify`'s second cost line out by construction — that one calls `cost.usd`.

**`hatch state` refuses nothing and is ADVISORY.** A one-shot hatch typed for a legitimate reason is what those variables are for, and the guard standing down prints its own name while doing it — so the only thing this can surface is a STANDING one, inherited from an environment nobody typed it into. `make status` grows a `hatches` line and a `turn gate` line, the latter finally calling `scripts/stop-gate.sh --status`, which existed to answer that question and had no caller in the Makefile, in status, in `checks.py` or in either hook roster.

### Two narrowings of what was asked, and why

**The fifth concurrency fact stays scoped to `docs/DEBTS.md` §11.** It is the METHOD NAME that sends `Connection: close`, and CLAUDE.md deliberately publishes the header without naming the method — §11 is where the mechanism is argued. Demanding the name in both would have failed an unchanged tree, which is not a defect found but prose wanted. Nothing is uncovered: §11 is the only file making the claim, so it is the only one that can go stale on it.

**`recorded deletions` does not carry D110's three dark-only hover overrides.** What D110 deleted is a declaration inside a `[data-theme='dark']` block; `.bn-nav-link`, `.capture-row` and `.capture-opt` are live classes. A substring needle is therefore either the class name — red on every run — or a string appearing nowhere, which is a needle that can never fire, i.e. the vacuous green this entry is about. It wants a CSS-structural reader, not this one.

### What it is worth

**44 mutation arms, 0 survivors**, each the arm the audit that specified this work named, plus the legitimate case pinned green beside it: prose narrating a deletion, `pull-confirm` rendering `#/gallery`, `#/inventory` and `#/codes` staying unrendered, `vale`'s disclosure, a bare integer in CLAUDE.md that can neither satisfy nor trip an attributed anchor, D27's argument about the retired `pkmnscan.*` spellings, a re-wrapped-but-correct published list, and the harness docstring's deliberate range and historical claims. Twenty-eight cases joined `make audit-self-test`, over the reporting layer, the comment/code classifier, the two `estimate wire` readers, the criterion-floor reader and the harness claim reader.

**One arm was informative rather than confirmatory**, which is the point of running them: posing a row that carries findings AND an empty subject made `subject counts` report a vacuous green over a row that had printed problems. The boundary above — a findings-bearing row is judged on its findings — is that arm's finding, not a guess.
