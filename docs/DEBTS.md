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

Underneath it, when this was written: `store/` and `cli/` had zero harness coverage — 2,509
lines, about 40% of product code, including the package the capture server writes through.
**That part is closed as of 2026-08-13**; T7 reaches all three packages and the map now
carries real `tested_by` entries for them. The field being *unenforced* is what survives:
the map could still claim a test reaches a module it never imports, and now that more
entries carry the claim there is more of it to be wrong about.

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

## Absent signals — a check that does not run at all

### Nothing checks `app/src/tokens.css` against `docs/DESIGN.md`

Recorded 2026-08-12, from the step-6 component work.

`docs/design-refs/README.md` already admits this about the two sheets: "nothing reads these
files programmatically and `scripts/docs-audit.py` does not check the hex values inside
them, so that staleness will not announce itself." As of step 6 the same is true of
`app/src/tokens.css` — except that file is not a drawing. It is what the product renders
from, so a token changed in one place and not the other means the app and the document
arguing for it disagree, and the document is the one nobody re-reads.

**Cost**: it rose on 2026-08-13. One component read these tokens when this was written;
step 7a made it seven stylesheets — three routes, the shell, the picker, the pull-confirm
and the page ground — and 7b adds the queue and the Fulfillment view. The failure is silent
by construction — a wrong hex renders perfectly.

**Why not fixed**: the fix is a mechanical audit check parsing `docs/DESIGN.md`'s fenced
token block against the file's custom properties, and it is *permitted* — checking is not
generating, so D18 does not bar it. It was not done at step 6 because that session's job was
to ship a component, and this repo has a recorded habit of building auditor machinery instead
of product code. **`docs/specs/capture-app.md` section 11 then named it as the cheapest of
three and said doing it early in 7a was defensible; 7a shipped without it**, so the second
stated moment to do this has also gone by. It is still cheap and still well-specified.

### The repo-map orphan rule did not reach `app/` — it bit, and then it was closed

Recorded 2026-08-12 from the step-6 component work, **rewritten 2026-08-13 after both halves
of it happened inside one day.**

What it predicted: `app/`'s module list is the only one in the map maintained by hand alone,
the cost "rises sharply at step 7", and step 7 adds screens rather than files-at-a-time.

What happened: step 7a landed thirteen new files under `app/`, `docs/map.py` described none
of them, and every row of `make docs-audit` stayed green — including the repo-map row, which
reported 44 entries matching a tree holding thirteen files it had never looked at. The gap
bit once, at the size and at the moment this entry named, and it was a review rather than a
check that found it.

**Closed the same day**, and the shape of the fix is worth keeping, because this entry
argued against the obvious one and that argument held. Widening a repo-wide suffix constant
was rejected here for conscripting the `.html` and `.css` under `docs/design-refs/`, which
are drawings of `docs/DESIGN.md` and deliberately not components. What shipped instead is a
per-entry `source_suffixes` key in `docs/map.py`, read by `scripts/docs-audit.py`; declaring
it also makes that entry's scan recursive, which is the second half of why the drift was
silent — `app/` keeps its source in `app/src/` and `app/tests/`, so a flat scan would have
found nothing whatever suffixes it was handed. `docs/design-refs/` stays uncovered by having
no module list at all, rather than by an exemption someone has to maintain.

**What is left, and it is not nothing.** The rule proves a file has an entry; it never proves
the entry is true. A `does` describing the wrong file passes exactly as well — the same
unenforced-claim shape as the `tested_by` row above, now spread across twenty-odd hand-written
lines. `.json` is deliberately outside the declared suffixes, since including it would
conscript `app/package-lock.json`, so `app/package.json` — which holds the npm scripts
`make lint`, `make typecheck` and `make design-check` all run through — has no entry
describing it. And `scripts/` is still uncovered for the different reason in its own entry
above.

### What T7 deliberately leaves uncovered in `server/`

Recorded 2026-08-11 when `store/` and `server/` shipped with no automated coverage at all,
and **rewritten 2026-08-13 when T7 closed most of it.** The forty-three cases that were
exercised by hand and enumerated here now exist as running assertions in
`harness/tests/t7_store_and_seams.py`, which is strictly better than a prose list — so the
list is gone rather than kept as a second specification that can drift from the first.

Three things from that enumeration are still not asserted anywhere:

- **Twenty-way contention.** T7 runs two and four simultaneous captures, matching D5's two
  devices. The twenty-way case is what found `request_queue_size` at its default of 5 —
  8 served, 12 reset by the OS — and re-running it at the end of every turn buys nothing
  the smaller case does not. If that constant is ever lowered, nothing will notice.
- **The bare-interpreter start.** The server runs on system `python3` with no venv, which
  is what makes `python3` rather than `$(PYTHON)` correct in the Makefile. T7 imports the
  module under whichever interpreter runs the harness, so it cannot see this.
- **Neither a `PUT` correction nor a `DELETE` undo appends to `history.jsonl`.** Two routes
  as of 2026-08-13, not one. The store logs state transitions and neither of these is one.
  T7 asserts what costs money when it fails — that the correction reaches the sidecar, and
  that undo removes the record, the sidecar and the photo — and the history lines are still
  missing from both. Undo is the wider of the two: afterwards `history.jsonl` still carries
  a `captured` event for a position whose record is gone. That is true rather than wrong —
  the capture did happen, it is the record that was removed — but it is the one place those
  two files disagree, and nothing says so at read time.

**Cost**: low and bounded, which is the difference from the entry this replaces. Each is a
single known case rather than a whole package nothing looks at.

**Why not fixed**: the first two cost more at every turn end than they can return. The third
had a stated trigger — "when `server/` is next opened for step 7" — and **that trigger fired
on 2026-08-13 and was passed**: step 7a opened `server/capture_server.py`, added a whole
route, and left both gaps where they were. Written down rather than quietly re-dated, because
a fix condition that goes by without comment is how a debt becomes permanent.

`DELETE` also supplied a reason to think harder than "add a log call", which is what the old
text assumed the fix was. There is no `undone` event in the store's vocabulary, and adding
one means naming a transition for a record that no longer exists — an entry in a log that
reads as the tombstone `docs/specs/capture-app.md` section 3 says this route must not create.
Whoever closes this settles that first, and it is a D10 question rather than a logging one.

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
