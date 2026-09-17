# Runs, harness, build order

**THE ENTRIES ARE IN `docs/gates/`, ONE FILE EACH, AND THIS FILE IS A POINTER.** It was one
119 KB document until 2026-09-16. Nothing reads it. `scripts/gates_corpus.py` reads the
directory and hands every checker the same bytes it used to get from here.

**THE GATING SYSTEM IS RETIRED (2026-08-23, owner's decision). This corpus is a record of
what was measured, not a schedule.** Gates A, B and C all passed. No gate is current. No step
is blocked behind one. The deferred list is open. `CLAUDE.md` no longer declares a current
gate. `scripts/docs-audit.py` no longer reconciles one.

## The corpus is three kinds, one folder each

Reading the monolith found three different things sharing one file, not one:

- **`docs/gates/contract/`** — the harness's own thresholds, `T1` .. `T9`. Each is cited
  elsewhere as a bare `Tn`, the same way a build step is cited as `step n`. `PASS_CRITERIA` in
  `harness/tests/*.py` is the ground truth. A `### Tn` file here publishes it.
- **`docs/gates/gate-runs/`** — Gate A, B and C, and their addenda. `GateB-note1` is "Box 2".
  `GateC-note1` is "the per-run reading". **Every number in these files is evidence about a
  run that happened on a date.** None of it is ever rewritten to match a later tree. 53 cards
  end to end. Finish detection at a 30% false-positive rate. `detect_card` at 0 of 53, then 53
  of 53. A 623 ms feeder cadence. Renumbering one to agree with today's code would turn a
  measurement into a fiction. That is the one thing a record here may never do.
- **`docs/gates/steps/`** — the build order. `docs/map.py`'s `SHIPPED` and `OPEN` carry the
  same ids. `make docs-audit`'s `build order mirror` row checks both directions. `n` is a
  stable id and is NEVER renumbered. 218 references to `step <n>` live in this tree. A
  renumber leaves every one pointing at a real step that is not the one meant, and nothing
  could detect that (D80). `SHIPPED` is ordered by the date work landed. `OPEN` is
  deliberately **unordered and has no `next`**. `docs/gates/ORDER.json`'s `steps.open` records
  that as a fact, not as an accident of what `ls docs/gates/steps/` happens to print. That is
  why the ids run out of order and why there is a hole at 12 — the only row ever culled.

**`gate-runs/` and not `runs/`.** A bare `runs/` line in `.gitignore` serves the pipeline's own
`runs/` at the repo root. It matches a directory of that name anywhere in the tree.
`gate-runs/` sidesteps that collision. Editing a shared, root-scoped ignore file for one
folder's sake was not worth it.

## How to find one

- **By id** — `T<n>` under `contract/`. `Gate<letter>[-noteN]` under `gate-runs/`. `step<NNN>`
  under `steps/`. A glob agrees with corpus order for `contract/` and `gate-runs/`. A step's
  file number is zero-padded for `ls` only. It is never itself the ordering rule. See above.
- **By the manifest** — `docs/gates/ORDER.json`'s `order` is the flat, exact reassembly
  order. Its `tests`, `runs` and `steps` fields are the three per-kind indexes.
- **By the file you are about to edit** — `scripts/decision-context.py` names the governing
  decisions before an edit. This corpus is read the same way, through `scripts/gates_corpus.py`.

## Why it is a directory, and why three folders and not one

**Two pull requests appending to one file conflict textually every single time.** Measured
across two-parent merges on this repository: `docs/DEBTS.md` at 82.5% (33 of 40) and
`docs/GATES.md` at 79% (15 of 19). This file was scoped OUT of the 2026-09-13 split round. The
argument was that it is a log of runs, not a record several branches author at once. **That
argument measured false.** `## What shipped` gained a row on almost every merge that landed a
build-order step, exactly like a decision entry gains an entry. D160 already settled "one
file per kind" for decisions. **One folder per kind** is what a corpus needs when it is not
one kind. This file's own history proved that. It held three kinds for weeks, with nothing
distinguishing a threshold from a run record from a step.

The move was performed by `scripts/split-gates.py`. That script's own `--verify` reassembles
the directory and diffs it against the bytes this file used to hold — IDENTICAL, 119,118
bytes, 42 files. This is the proof of losslessness. `make gates-selftest` runs the ongoing
half of that proof: the corpus is complete and still round-trips. `scripts/split-gates.py
--verify-split <the split commit>` re-establishes the historical, byte-for-byte claim later,
out of git alone.
