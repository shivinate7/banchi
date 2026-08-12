# Known gaps, deliberately unfixed

Findings recorded rather than repaired. Each entry says what is wrong, what it costs, and
why it is not fixed yet. This file exists so that a green `make docs-audit` is not read as
"the auditor is complete" — it means the checks that exist, passed.

Not a backlog to burn down on sight. An entry leaves this file when someone argues it
should, the way `docs/DECISIONS.md` entries are argued.

Most of what follows came from the review of the audit-retirement branch (2026-08-11),
which found 36 confirmed defects. The four load-bearing ones — the ones on the path
that decides whether a commit proceeds — were fixed in the same session and are not listed
here. Two more were one-line honesty fixes and are also gone: `scripts/audit-history.py`
publishing calibration figures it no longer produced, and `docs/GATES.md` disagreeing with
`docs/map.py` about which build-order steps are done.

Later entries come from later work and say so. An entry names its own date and source, so
this file is not scoped to the review that started it.

---

## Honesty debts — a doc claims a guarantee the code does not provide

### The auditor cannot tell you when one of its own checks stops running

`scripts/docs-audit.py` defines its checks as functions and runs them from an explicit list
in `audit()`. Add a check and forget the call, and it never runs: exit 0, a full-looking
roster, the hook passes, and nothing in the repo can tell you the auditor is smaller than
it looks.

This was covered until 2026-08-11. The retired count-of-checks machinery carried an
`unaccounted` set — *"defined, but in neither layer"* — with a self-test asserting every
defined check was accounted for. Deleting the published count (D18, correctly) deleted that
with it, and the commit message, D16, D18 and `docs/specs/audit-retirement.md` are all
silent about the loss.

**Cost**: unbounded and invisible. Every other entry in this file is a check that reports
the wrong thing; this is the one where a check can vanish.

**Why not fixed**: the deletion's whole argument was that the count was machinery nobody
consumed. Re-adding a detector has to not re-add the count — a real design question, not a
patch. It is the strongest candidate in this file for being fixed next.

### D17 states the repo-map orphan rule without the exception it actually has

D17: *"the orphan rule ... fails when a source file exists that no entry mentions. Adding a
module without touching the map fails the commit."* The rule is guarded by
`if modules and exists(target)`, and the `scripts/` entry in `docs/map.py` has no `modules`
list — so `scripts/` is never scanned. Measured:

```
touch scripts/<new>.py    ->  ok   repo map   34 entries match the tree
touch pipeline/<new>.py   ->  FAIL repo map   `<new>.py` exists but no entry describes it
```

The audit-retirement branch added `scripts/audit-history.py` — into the one directory the
rule does not cover — and updated the map's prose by hand. Nothing would have failed if the
author had forgotten. The `PreToolUse` decision-context hook says so out loud on every edit
under `scripts/`: *"no entry for this file; showing what governs scripts/"*.

**Cost**: the map can go stale exactly where this repo puts its gate machinery, and D17
argues at length that a believed index is worse than none.

**Why not fixed**: giving `scripts/` a `modules` list means writing a `does` and a
`governed_by` for four files, which is a content decision about what governs the tooling,
not a mechanical repair. Do it deliberately or not at all.

### `tested_by` in the repo map is an unenforced claim

Recorded 2026-08-11, from the step-5 spec work rather than the audit-retirement review.

The repo map row validates only that a cited test id is registered in the harness registry
(`scripts/docs-audit.py:1278`). It never checks that the test reaches the module. Audited
across all eleven entries: ten were true, one was false — `store/queues.py` claimed T3 and
T4 while nothing under `harness/` imports `store` at all — and two modules that *are*
exercised carry no entry. The false line was struck and the status legend corrected; the
field is still unenforced in both directions.

Underneath it: `store/` and `cli/` have zero harness coverage. 2,509 lines, about 40% of
product code, and it includes the package the capture server writes through.

**Cost**: the map can claim coverage that does not exist, in the file D17 argues must be
audited exactly as hard as it is trusted. The claim is believed precisely because the map
is otherwise reliable — ten of eleven is what makes the eleventh dangerous.

**Why not fixed**: a real checker means resolving each test's imports and asserting the
module is reached, which is new machinery in the auditor —
`docs/specs/capture-server.md` forbids that by name for the step-5 work, and it is the
same instinct that spent a full day and eighteen commits on the auditor and its docs while
shipping no product code. The honest interim is the legend fix and this entry.

### `make status` parses the human render, which `--json` exists to make unnecessary

Commit `b2d35ce` added `--json` to the auditor and argued for it: *"a machine surface, so
nothing retires on a parsed render."* `scripts/audit-history.py` honours that.
`scripts/status.py` does not — it parses the rendered text.

**Cost**: low today. It breaks when the render's wording changes, and the render is prose
nobody thinks of as an interface.

**Why not fixed**: it is a real change to `scripts/status.py`'s reader, and `make status`
is the one command a cold session is told to run first. Worth doing carefully.

---

## Reporting defects — a check runs but can report the wrong thing

Full detail is in the review; the short form, by where it bites:

- **`criteria evidence` can go silent.** If the score file's `test` value stops matching the
  auditor's filename-derived key, the row compares nothing and still reports
  `N scored run, gate field published`. The reachable trigger is narrow — hand-editing
  `NAME` in `harness/tests/t1_id_eval.py` — but the row has no equivalent of the ADVISORY
  downgrade the retired count row used for exactly this "could not look" state.
  Specified in `docs/specs/criteria-binding.md`, step 1, where it is the first thing to
  build because the fix for the threshold binding walks straight into it.
- **`criteria evidence` never opens the value it names.** A score file recording
  `holdout_accuracy: null` — a run that measured nothing — still reports
  `gate field published`.
- **`Pass:` claim matching is narrow and one-sided.** `startswith("Pass:")` misses
  `**Pass**:`, the spelling `docs/GATES.md` itself uses; absence is deliberately not a
  finding, so a bolded stale claim is exempt. The claim is joined only to the first blank
  line, and both comparison legs are containment rather than equality — so `docs/GATES.md`
  may publish a *longer* threshold than the test enforces and stay green, and a wrong
  headline `Pass:` line passes whenever the real criterion appears anywhere in the same
  paragraph.
- **The number leg is substring containment.** `"0.9"` is contained in `"0.95"`, so a
  loosened threshold can satisfy the check against an unchanged doc. Compounds the
  threshold-binding defect; recorded in `docs/specs/criteria-binding.md`.
- **`EVIDENCE_SOURCES` is three unvalidated path literals.** Nothing resolves them, so
  renaming any of the three silently retires the `evidence freshness` row.
- **The evidence glob assumes one naming convention.** `t1*.json` follows `docs/GATES.md`'s
  one-file-per-configuration rule; a score file named otherwise is invisible rather than a
  finding, and the row's summary claims coverage across all registered tests while the glob
  is T1-only.
- **`harness/results/` filenames encode the hint mode but not the split.** A tune-only run
  overwrites the committed holdout score, because the split is not treated as part of a
  configuration.
- **A partial `make audit-history` replay exits 0** and silently deflates every per-check
  total, with no denominator on any row; its absence classifier also swallows every `paths`
  finding, so that row scores zero by construction.
- **An empty requested split raises `ZeroDivisionError`** in `harness/tests/t1_id_eval.py`
  instead of reporting a clean failure.
- **`--self-test` does not exercise the staged-blob read path.** Partly repaired: the
  index-mode primitives now have cases, but no case drives a real git index.

---

## Prose that outran the code

- `docs/specs/audit-retirement.md` restates a check roster and a count that the shipped
  registry no longer matches — the retired number reappeared in a doc nothing audits, and
  is already wrong there. `CLAUDE.md` tells sessions to read specs as settled, so this one
  needs a status line saying which of its premises failed under execution.
- `.claude/commands/docs-audit.md` tells the reader exit 2 means the coupling question,
  but the command it prints in step 1 runs without `--staged`, and coupling only runs
  under `--staged`.
