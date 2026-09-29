# Audit retirement

**Status: EXECUTED.** This file is the record of a plan that retired one docs-audit row, added two,
and made the audit diagnosable. Read `make docs-audit` for what the audit checks now. Nothing here
restates a row count, because a restated count is the defect and a corrected one only resets the
clock. Section numbers are stable ids, because code cites them.

## 0. One convention this file still keeps

**Verbatim doc text sits in blockquotes, never in fenced blocks.** The audit reads every line of a
fenced block as code. A fenced quotation of prose that mentions a make target would be scanned as
a command reference. Blockquotes scan as prose. `scripts/docs-audit.py` relies on this when it
skips fenced blocks for the heading and instruction conditions.

## 1. Withdrawn, and not to be reproposed

- **Generation of the command and target doc blocks.** It nets 6 to 11 more lines, and it puts
  generation seams in CLAUDE.md, the file agents read first.
- **Generation of the current-gate line.** The line changes at most twice more in the project's
  life. A hand-maintained fact at that rate needs no machinery. The `current gate` row already
  blocks drift, and the threat model wants the fact at read time in CLAUDE.md.
- **The `GATE_FIELD` sibling-literal design** for the criterion check. A mutation kills it: section
  4 records why.
- **Committed staleness.** It compared the last commit that touched the three score sources with
  the last commit that touched `harness/results/`. It asked when the first was not an ancestor of
  the second. The signal it needs does not exist, by design. `docs/GATES.md` has the score file
  rewritten only when the measurement changes, so "re-ran, nothing moved" and "never re-ran" are
  the same history. The check fired on a commit that changed the test and moved no number, and only
  touching the score file could clear it. That is the noise the results-file rule exists to
  prevent. A permanently lit advisory is worse than a silent check, because it teaches every reader
  to skip exit 2 on every other row. Narrowing the sources changes the false-positive rate and not
  the fact. Having T1 record its commit makes the score file churn on every commit. **This follows
  from the results-file rule and is not a judgment about the check.** Whoever wants it back must
  argue against that rule first. The staged half survives, and asks the same question at the only
  moment it is actionable.

## 4. The premise correction

The plan asserted that the score file's `gated_on` field was derived from the split T1 gated on. It
was not. T1's split selection, its `gated_on` record and its stdout gate marker each named
`fixtures.HOLDOUT` on their own. Moving the gate to the tune half left all three saying "holdout"
and the harness green. The fix derives all three from one decision. **Repeated reads of one name
are fine, because they track a change everywhere. The defect is two independent decisions that
must agree.** Each earlier repair had added another reference and not derived from one.

## 7. `audit-history` is diagnostic only, forever

`scripts/audit-history.py` (`make audit-history`) replays today's auditor over every historical
tree. It informs a retirement argument and never makes one. Never wire it to a hook, a gate or CI.
Never add a standing permission for it, because a standing grant invites routine use of a slow
diagnostic. A zero from it reads with a by-construction confound: a check whose subject postdates a
tree could not have fired there. The `evidence freshness` row reads 0 for a related reason. It is
staged-only, and the tool runs whole-tree.

## 8. The bucket rule

Basis: AST spans of module-level defs, classes and assigns, plus self-test sections attributed to
the check they exercise. Comment lines and blanks are unattributed, so every row's true weight is a
little higher.

- **Bucket 0: no unconfounded window.** The check's subject postdates every ungated tree, so it
  never had the chance to fire. Never retire it on record. Keep it and instrument it.
- **Bucket 1: total 60 lines or fewer.** Keep it regardless of record. The deliberation costs more
  than the code.
- **Bucket 2: 60 to 110 lines, with a window.** Keep it if reachability is demonstrated. Otherwise
  instrument it and revisit with a longer record.
- **Bucket 3: over 110 lines, with a window and no substantive findings.** It needs an affirmative
  case, or it retires. The `check count` row retired here. `paths` stayed, because path rot tracks
  refactoring and the build order keeps adding directories. About half its cost is false-positive
  suppression.

**The record columns came from a hand count that no tool reproduces.** `scripts/audit-history.py`
counts the same window two other ways. The three conventions disagree by up to 4x. One gap was
run to ground. A recorded 2 findings for decision ids in code was actually 0. Every finding was
the injected auditor citing itself. The rest is an unwritten counting convention. That is
tolerable only while nothing sits near a boundary. **Any retirement argument at a bucket boundary
must adjudicate the convention first, in writing, before it looks at which number favors the cut.**
Picking the convention after seeing which one clears the threshold is the same move as tuning the
classifier to hit a number. Re-deriving the hand figures, or replacing them with an instrumented
convention, is the honest way out. Do it before the next cut and not during it.

The largest surviving row is `repo map`, and it has no self-test. Any self-test investment lands
there.

## 9. Verified externals

Do not re-research these. Each was run against this repo or read from live documentation.

| tool | verified state | verdict |
| --- | --- | --- |
| lychee 0.24 | run on this repo: 2 links total, and the probe caught 1 of 8 reference styles used here | no adoption. These docs reference by backticked path, not link syntax |
| Vale 3.17 | run with a 3-rule custom style: 149 findings, about 99% false positive against docs. Strictly per-file | conditional. Adopt for Fulfiller-facing copy, where the `DESIGN.md` banned-word list is its native job. Then move `check numbering` and `numbering in code` to Vale rules, which are single-file regexes kept in Python only for the stdlib-only hook constraint |
| markdownlint-cli2 | run: 565 findings, 91.7% one line-length rule | no adoption. It checks syntax and never truth |
| pre-commit framework | docs verified. `pass_filenames` and `always_run` model per-file against repo-wide scope, and it stashes unstaged changes | not adopted, because it is a cold-clone pip dependency. Its stash behavior is the origin of the staged-read fix. The row that checks the registered commands needs both scopes in one check, which its model cannot express |
| Sybil 10.1 | docs verified | the only tool that reaches the constant-versus-runtime seam. It needs pytest in a repo with a custom harness, so `criteria evidence` covers the seam instead |
| cog | releases and docs verified. A check mode and edit-guard checksums exist | rejected while freshness runs in the bare-python3 hook, because it is a PyPI package and executes embedded imports. It flips if freshness verification moves to CI |
| adr-tools | README fetched | authoring only. No hooks and no path association |
| log4brains | README fetched | its `@adr` code-reference annotation is unshipped, and it points the wrong way: code references into the ADR, not decisions surfaced at the file being edited |
| pyadr | README fetched | lifecycle tooling. Its pre-merge checks gate the ADR repo itself, never source files |
| MADR | README fetched | a template only. No CLI, no hooks and no path association |

Two results, recorded as results and not as absences. **The delete list is empty.** The
off-the-shelf tools are link syntax, prose style and decision authoring. None of them checks a
claim in one file against a fact in another. Every surviving row does that. And
**`scripts/decision-context.py` is unserved.** Nothing in the ADR ecosystem wires decisions into an
edit path.

## 10. Outcome

- **Retired:** the `check count` row and its machinery, which guarded a published number no
  consumer read. `scripts/status.py` needed no edit, because it counts rows in the rendered report.
- **Added:** `criteria evidence` (mechanical) and `evidence freshness` (advisory, staged-only).
  `criteria evidence` is the first row whose subject is a runtime artifact and not source text. It
  reads `gated_on` out of the committed score file and requires `PASS_CRITERIA` to name the field
  the run gated on.
- **Extended:** `criteria wording` also holds each test's module docstring to its `PASS_CRITERIA`.
- **New surfaces:** `--json` on the audit, because nothing retires on a parsed human render, and
  `scripts/audit-history.py`.
- **Fixed:** staged mode reads the staged blob and not the worktree.

**The bug class this migration kept finding is correct logic evaluated against the wrong thing.**
Code review cannot see it. Only an outside baseline can. Three cases: staged mode audited the
worktree while the commit carried the index. `audit-history` counted findings the injected auditor
raised against itself, and the total ran 36 times over a known baseline. T1's split named
`fixtures.HOLDOUT` three times (section 4).

**The plan's own accuracy record.** Its mechanical figures held under execution: self-test sections
measured 81 against a recorded 81. Its claims about run-time behavior did not. It asserted a
`gated_on` derivation that did not exist, and it relied on a commit history that `docs/GATES.md` erases
on purpose. **Count lines from the source and trust the number. Verify what code does at run time
before building on it.**
