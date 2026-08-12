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

## Absent signals — a check that does not run at all

### The post-edit hook channel is gone, and step 7 is when it should come back

Recorded 2026-08-11, from the step-5 spec work.

`.claude/settings.json` ran `make lint typecheck` after every Write and Edit. Both targets
exit 1 by design — `Makefile:3`, a target that exits 0 with nothing to run is a lie the
rest of the project would be built on top of — and under one make invocation the abort on
`lint` meant `typecheck` never ran at all. The pipe to `tail` then swallowed the status, so
the hook itself exited 0 and blocked nothing. Five lines of failure text after every edit,
from 2026-08-03 until it was deleted on 2026-08-11.

Deleted rather than repointed. Pointing it at the harness costs far more output per edit
for a check the Stop hook already runs at turn end, and dropping `lint`'s `exit 1` would
make `make check` green by lying — which is the thing `Makefile:3` exists to refuse.

**Cost**: there is now no automatic post-edit signal at all. Zero today, because there was
nothing behind the channel. Real at build-order step 7, when TypeScript arrives and
`make typecheck` starts meaning something.

**Why not fixed**: there is nothing to point it at yet. Step 7 should re-add it — at the
typecheck target alone, never at the composite — rather than rediscovering the question
from an empty hooks block.

### The position allocator was verified by hand, and the cases died with the session

Recorded 2026-08-11, when `allocate_capture` and `next_index` landed in `store/master.py`.

Nothing under `harness/tests` imports `store`, so the allocator shipped with no automated
coverage — deliberately, per `docs/specs/capture-server.md`, which rules that fixing the
`store/` coverage gap is not a precondition for build-order step 5. It was instead exercised
by hand across seventeen assertions before the commit, all passing, none committed. The
enumeration is below because re-deriving it later costs more than writing it down, and
because it is the closest thing to a specification the allocator has:

- **Empty box** returns index 1; a box that has never been seen is created implicitly by
  the first allocation.
- **Sequential allocation** yields 1 then 2, keyed `3/1` and `3/2`.
- **Boxes are independent** — allocating into box 7 leaves box 3's next index untouched.
- **D10's permanent gap**: a card moved to `sold` keeps its record, and the high-water mark
  continues past it rather than filling the hole.
- **Deleting the highest record releases its index.** This is the behaviour step 7's undo
  will inherit, and it is why reuse-versus-burn is settled by whether undo deletes or
  tombstones — not by the allocator.
- **A string-typed record** — box and index arriving as JSON strings — is counted, not
  skipped, so the next index clears it.
- **An unparsable box or index refuses**, and the message names the offending card key.
- **A replayed `capture_id`** returns the original card with `created` False and burns no
  second index.
- **One `capture_id` on two cards refuses**, naming both positions.
- **`capture_id` survives a JSON round trip** through `to_payload` and `parse`.
- **Allocation logs exactly one `captured` event.**

Separately measured on the same day, and the reason the coercion is written the way it is:
with a string-typed record present, filtering on `c.box == box` drops it silently and
returns an index that collides later, while coercing only the box raises `TypeError` from
`max()` **inside the lock**. Only coercing both fields is correct. The record is hard to
spot because `position_key` coerces while the fields do not — the key looks perfectly
ordinary and the fields are wrong.

**Cost**: the allocator is the one piece of step-5 logic the 20-card Gate B run exercises
twenty times, and nothing re-checks any of the above on a later edit. A refactor that
reintroduced the `c.box == box` filter would pass every gate in the repo.

**Why not fixed**: adding a harness test for `store/` is a real decision about what the
harness covers — the contract in `docs/GATES.md` is six tests about the pipeline, and
`store/` and `cli/` were left out of it from the start. Do that deliberately, as its own
argument, not as a rider on the capture server.

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
