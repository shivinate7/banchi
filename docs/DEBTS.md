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

### The auditor names a check it defines and never runs — closed 2026-08-13

Recorded 2026-08-11 from the audit-retirement review, where this was the entry this file
called its strongest candidate for being fixed next. **Closed 2026-08-13.**

What it argued: `scripts/docs-audit.py` defines its checks as functions and runs them from
an explicit list in `audit()`. Add a check and forget the call, and it never runs — exit 0,
a full-looking roster, the hook green, and nothing in the repo able to say the auditor is
smaller than it looks. The retired count-of-checks machinery had carried an `unaccounted`
set doing this incidentally; deleting the published count (D18, correctly) took it out with
it, and the commit message, D16, D18 and `docs/specs/audit-retirement.md` were all silent
about the loss. Why it stayed open: re-adding a detector had to not re-add the count.

What shipped: the `check dispatch` row. It parses this file's own source with `ast` —
never imports it, and never runs `audit()` to find out, because a registry gathered at run
time agrees with itself whatever the source says — collects every module-level function
that source marks as a check, and reconciles those names against the ones appearing
anywhere inside `audit()`. It blocks: an unrun check is provably not running, which is
D16's test for mechanical, and there is no judgment to defer.

**Nothing is counted, and that is the design answer to the question that kept this entry
open.** No number in the summary, none in any finding, none in the JSON row. What D18
deleted was a *published total* nothing consumed, and a total printed here would be back in
circulation the moment a session restated it in a doc — at which point the machinery that
was deleted has to come back to keep the restatement honest. What the row emits instead is
the name of a function you can go and call, which is the only output that was ever
actionable. Under `--staged` it reconciles the staged blob, so this is the one check whose
subject is the file the commit will carry rather than the file that is executing.

Two details decide whether it can be fooled, and both were chosen against a weaker
alternative:

- **A check is a module-level function carrying either signal — the `check_` prefix, or a
  `report.add` call.** Unioned, not intersected. An AND would mean losing either signal
  hides a function from the row, and both are lost in edits that read as tidying.
- **Names are read from a walk of `audit()`, not from its top-level statements.** The
  retired reader read statements and its own docstring named the failure: restructure some
  of the calls into a loop, leave the rest, and it sees fewer checks than there are.
  Measured here — a statement-reading reader reports `check_coupling` unrun today, because
  that one is called inside the `staged_only` branch.

**Seen to fail before it was believed.** A check function added to the file and left
unwired:

```
  FAIL check dispatch         1 problem
       scripts/docs-audit.py:2558
         `check_temporary_probe` is defined here and `audit()` never calls it, so it
         has never run. The row it would print is simply absent from the report, and
         an absent row is the one failure this file cannot show you.
         Call it from `audit()`, or record it in UNDISPATCHED with the reason it is
         defined and not dispatched.
```

exit 1. Wired into `audit()` the row reads `ok` and the run exits 0; the probe was then
deleted. The self-test's cases were re-run against three deliberately broken readers, since
a case that has never failed is not known to work: a reconciliation that calls everything
dispatched loses five of them, a prefix-only definition loses the renamed-check case, and
the retired statement-reading shape loses the loop case and the live file.

**Seen to work on a check it did not ship with** — added at integration, because a probe
this row's own author wrote is the weakest evidence available for it. The concern is
vacuity: a detector that quietly reads a stale roster passes for the same reason a correct
one does, and the day it would show is the day someone else adds a check. Two other groups
did, in the same run. Measured against `check_tested_by_reach`, which this row never saw
being written:

- The reader enumerates every check defined in the file and finds all of them named in
  `audit()`, `check_tested_by_reach` included. Not inferred from a green row — printed
  from `defined_checks` and `dispatched_names` directly.
- Deleting `check_tested_by_reach(report)` from `audit()`: `FAIL check dispatch`, exit 1,
  the `tested_by reach` row absent from the report exactly as described. Same for
  `check_raw_colour`. Restored, both clean.
- **On the staged path, which is the one that gates.** Intact file staged with the unwired
  file in the worktree: `--staged` green, plain mode red — the row's subject really is the
  blob the commit will carry. Unwired file staged: exit 1. That is the hook blocking.
- `--self-test` fails on the same trees, and `make status` reads it through `--json` as
  `1 FAILING`, so the failure survives every surface it crosses.

The scoping to `audit()` earned itself here rather than in argument: `self_test` calls
`check_tested_by_reach(report)` by name, so a file-wide search would have reported it
accounted for while `audit()` called nothing.

**What it does not cover.** Six things, and the first one is the row's own blind spot:

- **It cannot see its own unwiring, and `audit()` used to claim otherwise.** The comment on
  the dispatch call read "it also answers for itself: drop this line and the next run
  reports `check_dispatch` as never called". Measured at integration: delete that line and
  every other row prints green, the run exits 0, and the `check dispatch` row is absent —
  which is precisely the failure this entry was opened about, one level up. Not patchable.
  A detector cannot detect its own absence, and a second reconciler asserting the first is
  dispatched would rest on the same single unvouched-for call. So there is a root to the
  recursion: unwire anything else and the commit fails, unwire *this* and nothing automatic
  says so. `--self-test`'s last dispatch case calls `check_dispatch()` directly and does
  catch it — but `--self-test` is on no gate at all: not the pre-commit hook, not
  `make check`, not `harness/run.py`, not the Stop hook. It is run by hand or not at all.
  Wiring it into a gate is a real option and deliberately not taken here: it would put a
  writer — the self-test's `TemporaryDirectory` — on the path that decides whether a commit
  proceeds, which is the argument D18 makes, and that argument gets made on its own terms
  rather than while integrating someone else's branch. The comment is now corrected in
  place, which is the part that was actually a defect: a false guarantee is worse than a
  known gap, because only one of the two gets checked.
- **A check deleted together with its call is clean, and always will be.** This is what
  survives of the original entry, and it is the trade the design makes: a count would have
  caught an auditor that shrank, a reconciliation catches one that was never wired. The
  forgotten wiring is the failure worth catching, because the diff that causes it shows a
  new function and looks exactly like the work being done. A deletion shows up as a
  deletion in the same diff, where a reviewer and `git log` can both see it.
- **Called is not run, and run is not looked.** A dispatched check that returns before its
  `report.add` prints no row at all, and this row is content with it. `check_raw_colour`
  does precisely that when `app/src/` is absent. Same unenforced-claim shape as the
  `tested_by` entry below, one level down.
- **Dispatch has to live inside `audit()`.** Move it to a module-level table and the row
  reports that it can no longer see any dispatch — one finding about the reader rather than
  a wall of findings each naming the wrong cause, and blocking, because a reader that
  cannot see dispatch cannot tell you whether anything runs. The checks may well be running
  fine at that point; teaching the reader the new shape is deliberately not optional.
- **`UNDISPATCHED` is an escape hatch and its reasons are unaudited prose.** Self-cleaning
  in both directions — an entry naming a check `audit()` calls is stale and reported, an
  entry naming nothing defined here is dangling and reported — but nothing judges whether
  the reason is any good. It is empty today, which is the finished state rather than an
  unfinished one, the same shape as D18's seam list.
- **Scope is that one file.** Nothing reconciles `harness/run.py`'s registry against the
  tests defined beside it, or `scripts/githooks/pre-commit` against what it means to run.

### The orphan rule reaches `scripts/` now — closed 2026-08-13

Recorded from the audit-retirement review (2026-08-11), **closed 2026-08-13.**

What it argued: D17 states *"the orphan rule ... fails when a source file exists that no
entry mentions. Adding a module without touching the map fails the commit."* The rule is
guarded by `if modules and exists(target)`, and the `scripts/` entry in `docs/map.py` had
no `modules` list — so `scripts/` was never scanned. Measured then:

```
touch scripts/<new>.py    ->  ok   repo map   34 entries match the tree
touch pipeline/<new>.py   ->  FAIL repo map   `<new>.py` exists but no entry describes it
```

The audit-retirement branch had added `scripts/audit-history.py` into the one directory the
rule did not cover and updated the map's prose by hand; nothing would have failed if the
author had forgotten. The `PreToolUse` decision-context hook said so out loud on every edit
under `scripts/`: *"no entry for this file; showing what governs scripts/"*. It no longer
does — every file there now answers with its own `does` and its own decisions.

Why it sat here rather than being patched, which held right up to the day it closed: the
guard was never the work. Eleven files needed a real `does` and a real `governed_by`, and
what governs the gate machinery is a content decision, not a mechanical repair.

**What shipped.** The `scripts/` entry in `docs/map.py` carries all eleven files and
declares `source_suffixes` of `.py`, `.sh`, `.txt`. `.sh` is most of the point: the opsec
enforcement is `scripts/guard-opsec.sh` and `scripts/githooks/pre-commit`, and the one
repo-wide rule about bearer instruments should not be the thing living in the directory the
index does not scan. Declaring the key is also what turns the scan recursive, which is the
only reason `scripts/githooks/` is reached at all. `.txt` because both files carrying it are
tracked inputs that tooling reads and fails against, not notes. The `governed_by` lists run
mostly D14, D16, D17 and D18, with D11 on the two files that make `fixtures/` read-only and
D5 plus D13 on the screenshot loop and its manifest.

**Seen to fail before it was believed.** Four probes, each created, audited, deleted:

```
FAIL repo map   `scripts/<probe>.py` exists but no entry describes it            exit 1
FAIL repo map   `scripts/<probe>.sh` exists but no entry describes it            exit 1
FAIL repo map   `scripts/<probe>.txt` exists but no entry describes it           exit 1
FAIL repo map   `scripts/githooks/<probe>.sh` exists but no entry describes it   exit 1
```

The fourth is the one that proves recursion, since a flat scan of `scripts/` would never
have looked there. Staged — the path that actually blocks a commit — `git add` of the first
probe and `docs-audit.py --staged` fails identically at exit 1, which matters because
`_walk` answers from the index in that mode and could have disagreed with the worktree. With
every probe removed the row read `ok repo map 78 entries match the tree` and the run exited
0; the same row read 67 before this landed, and the difference is the eleven new entries.

Two more, because a listing is a claim as much as a scan is. Moving `githooks/pre-commit`
aside produced `` `scripts/githooks/pre-commit` is listed but does not exist `` at exit 1.
Dropping `D2` from `scripts/docs-audit.py`'s `governed_by` produced *"cites D2 in its own
comments but the map does not list it under governed_by"* — so the decisions listed there
because the file names them in a worked example are forced by the check rather than
decoration, and the map was restored byte-identically after.

**What it does not cover.** Three things, and the first is not small.

- **An extensionless file is invisible to the rule, and one of them is the commit gate
  itself.** `scan_plan` rejects any entry that does not start with a dot, so no declaration
  can reach `githooks/pre-commit`. Measured: creating a second extensionless hook beside it
  — a `pre-push`, say — left the row reading `ok repo map 78 entries match the tree` at
  exit 0. The existing hook is listed, so its *disappearance* is caught; a sibling's arrival
  is not. The shape of a fix already exists a few hundred lines away: `code_haystack()`
  reaches that same file by handing `_walk` the whole filename as if it were a suffix. Not
  done here because it changes `scripts/docs-audit.py` and what `source_suffixes` means, and
  that is argued on its own terms rather than while writing a map entry.

  **THE HYPOTHETICAL LANDED ON 2026-08-29 AND IT WAS THE FILE THIS BULLET NAMED.** D42 added
  `githooks/reference-transaction` and `githooks/pre-push` — the "a `pre-push`, say" above,
  written as a thought experiment and then committed as a real file — and the orphan rule was
  silent for both. They are listed in `docs/map.py` by hand and nothing would have failed had
  the author forgotten. The same change added `scripts/githooks-selftest.sh` one directory up,
  which carries a declared suffix and duly **failed the commit** until it was described. One
  commit, both outcomes, which is the sharpest available statement of what this debt costs:
  the rule's coverage is decided by whether a filename happens to have a dot in it.

  **It also raises what the gap protects, which is the part that changes the priority.** When
  this was written the unscanned directory held one file, the commit gate. It now holds the
  guard over `main` as well, so the files the orphan rule cannot see are the commit path, the
  ref path and the push path — every enforcement seam in the repo, and none of them scanned.
  Still not fixed here for the reason above; recorded so the next reader weighs it against
  that list rather than against one hook.
- **It proves a file has an entry, never that the entry is true.** The same limit `app/`
  carries, now spread across eleven more hand-written lines: a `does` describing the wrong
  file passes exactly as well. The `governed_by` half is enforced in one direction only —
  the map may not know *less* than the code's own citations, and may say anything it likes
  beyond them.
- **The superset rule cannot tell an illustration from a ruling.** `scripts/docs-audit.py`
  names `D2` in a comment about citations that could plausibly become variable names, and
  `scripts/decision-context.py` names `D2` and `D3` as its worked examples. All three are
  now listed as governing files they do not govern. That is the cheap side of the trade and
  each is labelled as such in the map; the expensive side would be the rule guessing which
  citations count.

### `tested_by` is checked against what the cited test imports — closed 2026-08-13

Recorded 2026-08-11 from the step-5 spec work, **closed 2026-08-13**.

What it argued: the repo map row validated only that a cited test id is registered in the
harness registry. It never checked that the test reaches the module. Audited by hand across
all eleven entries: ten were true, one was false — `store/queues.py` claimed T3 and T4 while
nothing under `harness/` imports `store` at all — and two modules that *are* exercised
carried no entry. The false line was struck and the status legend corrected, and the field
stayed unenforced in both directions while the number of entries carrying it grew.

Underneath it, when this was written: `store/` and `cli/` had zero harness coverage — 2,509
lines, about 40% of product code. That part closed earlier the same day; T7 reaches all
three packages and the map carries real `tested_by` entries for them.

What shipped: the `tested_by reach` row in `scripts/docs-audit.py`. Each claim resolves to
its test module through `harness/run.py:TESTS`, which is parsed rather than imported like
everything else here, and the top-level package the entry lives in must appear in that
test's import graph — the test module plus one level into its own `harness/` helpers. For a
component directory holding no Python (`fixtures/`), where there is no import to check, the
evidence is the test naming a path under it in a string literal that is not a docstring:
`harness/tests/t2_round_trip.py` opens by saying it loads
`fixtures/sv09_export_untouched.csv` and then assigns that path to `SOURCE_FIXTURE`, and
only the second is the test reading the file.

It blocks. An import is in the parse or it is not, which is D16's test for a mechanical
finding. It is **its own row rather than more findings on `repo map`**, for the reason the
`design tokens` row gives for not folding the second `docs/DESIGN.md` fence into itself:
two comparisons behind one row's name means neither summary line can be read.

**Seen to fail before it was believed.** With the struck claim put back on
`store/queues.py`, and `fixtures/` additionally citing T7:

```
  FAIL tested_by reach        3 problems
       docs/map.py -> store/queues.py
         tested_by claims T3, and harness/tests/t3_join_coverage.py imports no `store`.
           T3 reaches: harness, pipeline
       docs/map.py -> store/queues.py
         tested_by claims T4, and harness/tests/t4_variant_ladder.py imports no `store`.
           T4 reaches: harness, identify, pipeline
       docs/map.py -> fixtures/
         tested_by claims T7, and harness/tests/t7_store_and_seams.py names no path
         under `fixtures/`.
```

exit 1. Reverted, the row reads `ok 20 claims, every cited test reaches what it names` and
counts the same 20 under `--staged`, where every read comes from the index instead.

**What it does not cover.** Five things, and the first is the important one:

- **It proves reach into a package, never that the module is exercised.** `from pipeline
  import join` satisfies every entry under `pipeline/` at once, and a test that imported a
  package and asserted nothing about it would keep this row green. The label is
  `tested_by reach` and not `tested_by coverage` for that reason — overclaiming in a check
  built to catch an overclaim would be the same defect one level up. Full call-graph
  resolution is the tool that would close it and is the wrong one: it is a large amount of
  new machinery in the auditor to answer a question a human reading the test answers better.
- **Module granularity was measured and rejected.** `harness/tests/t6_geometry.py` imports
  the bare package (`import geometry`) and reaches `detect` and `crop` through it, so a
  module-granular rule would call both correct `geometry/` entries false. D16 says a false
  positive that blocks is worse than one that prints, and this row blocks.
- **The follow stops at `harness/`, so reach through a product module is a finding.**
  Deliberate, and measured: `cli/cmd_identify.py` imports `geometry` and T7 imports `cli`,
  so a single transitive hop would prove "T7 reaches geometry" — a package T7 does not touch
  and whose two modules correctly cite T6. Following the product's own import graph makes
  nearly every claim true and asserts nothing, which is the unenforced field this row
  replaces, rebuilt out of the machinery meant to replace it.
- **The other direction is still open, and it was half of the original finding.** A module
  that a test *does* exercise and that carries no `tested_by` is invisible here.
  `store/cache.py` is exactly that case today — T7 reaches it through a session and it
  carries no claim, by the deliberate choice recorded in that entry's note.
  `store/queues.py` was the second example until 2026-08-22, when `check_queue_supersede`
  began asserting `queues.apply_run` outright and the map's entry gained the `tested_by` it
  had earned. Nothing detected that; a human did, which is what this direction being open
  costs. Closing
  this direction means deciding that "a test imports it" is the same as "a test covers it",
  which is precisely what the first bullet refuses to say. It is a decision about what
  `tested_by` means, not a gap in the parser.
- **A test that reaches code without importing it would be a false positive.** No harness
  test does today: `subprocess` appears nowhere under `harness/tests/`, and the two
  function-level imports that exist (`geometry` in T6, `cli.__main__` in T7) are found
  because the reader walks the whole tree rather than the module body. If one ever arrives,
  the fix is the claim or the test, never a `note` — a field that can be talked out of a
  finding is the field this entry started as.

**A Playwright spec cannot be cited here at all**, and that is the answer rather than a gap.
`app/tests/pull-confirm.spec.ts` and `app/tests/fulfillment.spec.ts` run under
`make design-check`, not at turn end; the repo map's existing id check refuses any
`tested_by` not in `harness/run.py:TESTS`, so citing one fails before this row sees it, and
its message now says so and points at the `note` field. A second key — `checked_by`, naming
non-harness checks — was considered and rejected: no entry needs one, both specs already
record what they are in prose, and a key with zero users is the surface area D18's
deliberately empty seam list argues against by name.

### `make status` reads the auditor's `--json` now — closed 2026-08-13

What it argued: commit `b2d35ce` added `--json` to the auditor for a stated reason — *"a
machine surface, so nothing retires on a parsed render"* — and `scripts/audit-history.py`
honoured it from the day it was written, while `scripts/status.py` went on counting
`  ok ` and `  FAIL ` prefixes out of a report written for a human. The cost was low and
the trigger was a wording change nobody would connect to it.

What shipped: `audit_line()` in `scripts/status.py` runs `docs-audit.py --json` and reads
the payload. Four things are checked before a number is printed — that stdout is a
`rows`/`exit` object, that every row carries `label`/`severity`/`findings`, that no row
carries a severity this reader cannot classify, and that `exit` agrees with the rows it
arrived with — and any of them failing prints `MISSING` and exits non-zero rather than a
count of zero. That is the module's own rule for a source that moved, applied to a surface
that moved.

`scripts/docs-audit.py` also joined the `SOURCES` literal, which it had never been in. It
is a subprocess rather than a read, and that is exactly why its path sat hardcoded and
uncovered while every other path in the file was audited — so renaming the auditor now
fails a commit instead of deleting a line from this output.

**Seen to fail before it was believed.** Measured on an archived `HEAD` tree carrying both
readers side by side, against one auditor whose render labels were changed and nothing
else — `ok  `→`pass`, `FAIL`→`BAD `, `ask `→`hmm `:

```
old reader   docs audit     0 question(s) · 0 clean — run `make docs-audit`
new reader   docs audit     1 FAILING · 19 clean — run `make docs-audit`
```

The old line is this entry's whole argument in one row. It did not merely lose the count:
it downgraded a mechanical failure to a question, and it did both while looking like a
healthy report, which is the only failure mode that matters for a tool a cold session is
told to run first. The new reader printed the same line it prints against the intact
render. Against the intact auditor the two readers differ in nothing, and both take 0.21s.

Each of the five refusals was then driven to fire, since a check never seen to fail is not
known to work: `--json` deleted from the parser, the payload key renamed `rows`→`checks`,
`MECHANICAL` renamed to `"blocking"`, the exit rule forced to `0` while a row still held
findings, and the auditor renamed away so `resolve()` misses it. All five print `MISSING`
and exit 1. Nothing in this repo parses the render any more — the pre-commit hook branches
on the exit code and echoes the text, and `/docs-audit` is a model reading prose, which is
what that layer is for.

**What it does not cover.** Three things:

- **The `SOURCES` entry proves the module is there, not that the contract is.** `kind:
  defs` can only ask for module-level `def`s, so it requires `build_parser` and `main`, the
  two the invocation goes through. It cannot see the `--json` flag or a payload key,
  because neither is a module-level name. Those are caught at run time instead, loudly —
  the honest split for a subprocess, where the contract is a property of a program running
  and not of a file sitting on disk.
- **`scripts/status.py` is not in the auditor's `INVOKERS`**, so the `audit invocation`
  row — which exists to catch a caller passing a flag argparse rejects — does not see this
  new call. It would find nothing if it did: that row reads flags with a regex off a
  literal command line, and `status.py` builds its argv as a list. Both halves are
  `scripts/docs-audit.py`'s to change, and `docs/specs/capture-server.md` §0.1 forbids
  touching that file for work of this shape.
- **Reading the payload cleanly says nothing about what is in it.** Every entry under
  *Reporting defects* below is upstream of the JSON, and a row that reports the wrong thing
  reports it just as wrongly through a machine surface.

---

## Absent signals — a check that does not run at all

### `app/src/tokens.css` is checked against `docs/DESIGN.md` now — closed 2026-08-13

Recorded 2026-08-12 from the step-6 component work, **closed 2026-08-13 in step 7b**, which
is the third of the three moments this entry named and the first one that did not go by.

What it argued: `docs/design-refs/README.md` already admits that nothing reads the two
sheets programmatically, and the same was true of `app/src/tokens.css` — except that file is
not a drawing. It is what the product renders from, so a token changed in one place and not
the other means the app and the document arguing for it disagree, and the document is the
one nobody re-reads. The cost rose with every stylesheet: one component when this was
written, seven after step 7a, ten-plus once 7b's screens land.

What shipped: the `design tokens` row in `scripts/docs-audit.py`. It parses the fenced block
under `## Tokens` in `docs/DESIGN.md` — every colour by its name, the three typefaces, every
step of the spacing scale, the radius — and the custom properties declared on `:root` in
`app/src/tokens.css`, and compares them in both directions. It blocks, because a
disagreement between two stated values is provable and D16 leaves it no judgment to defer: a
value that differs, a locked token the stylesheet never declares, and a declared token the
block never locked are each a mechanical finding naming both files and both values.

**Seen to fail before it was believed.** With `--accent` changed to `#1e40b0` in
`app/src/tokens.css` and nothing else touched:

```
  FAIL design tokens          1 problem
       docs/DESIGN.md + app/src/tokens.css
         `accent` disagrees.
           docs/DESIGN.md:      #1E40AF
           app/src/tokens.css: #1e40b0
```

exit 1. Reverted byte-identically, the row reads `ok` and the run exits 0. Under `--staged`
the same drift is silent until it is staged, which is the whole file's rule — the hook
audits the tree the commit will carry.

**What it does not cover.** Four things, all deliberate:

- **It proves the two files agree, not that the palette is any good.** A green row says
  nothing about the 7:1 property of the set, the choice of face, or whether a colour earns
  its place. Contrast is asserted against rendered pixels in `app/tests/pull-confirm.spec.ts`
  and the rest is what the interview was for.
- **The two sheets in `docs/design-refs/` stay unchecked, by design.** They are drawings of
  `docs/DESIGN.md` and are allowed to lose to it — that file already records two places where
  the sheet did. A check that forced them to agree would force the reference to be re-drawn
  before a token could move, which inverts which of the two is the source.
- **The second fenced block in `docs/DESIGN.md` is not read.** Step 6's three button states
  restate five of these hexes, and nothing reads those literals — `app/tests/pull-confirm.spec.ts`
  computes contrast and sizes from rendered pixels and never compares a hex — so one of them
  can go stale in silence. Left out because it is a different question: a document disagreeing
  with itself rather than with the code, where D18's instinct is that deleting a restatement
  may be the right answer. That argument belongs in `docs/DESIGN.md`, not in the auditor.
- **A raw hex anywhere else in `app/` is invisible to it.** The check reads one `:root` in one
  file. `app/src/PullConfirm.css` paints `color: #ffffff` twice, and whether that is `--surface`
  spelled the long way or a label colour deliberately outside the palette is a question for
  that file's owner, not something this row can see.

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
unenforced-claim shape the `tested_by` entry above started as, now spread across twenty-odd
hand-written lines, and with no equivalent fix available: an import is in a parse or it is
not, and a sentence about what a file does is neither. `.json` is deliberately outside the
declared suffixes, since including it would conscript `app/package-lock.json`, so
`app/package.json` — which holds the npm scripts `make lint`, `make typecheck` and
`make design-check` all run through — has no entry describing it.

`scripts/` was named here as still uncovered; it was covered the same day by the entry
above, which took this entry's fix — a per-entry `source_suffixes` rather than a widened
repo-wide constant — and reused it. **Both halves of that sentence were written in the same
run by different hands, and nothing mechanical would ever have told either of them.** The
orphan rule fires on a file with no entry; a cross-reference in prose that has gone stale is
invisible to it, and to every other row. Worth leaving as the worked example of what this
file's own layer-1 coverage is not.

### What T7 deliberately leaves uncovered in `server/`

Recorded 2026-08-11 when `store/` and `server/` shipped with no automated coverage at all,
and **rewritten 2026-08-13 when T7 closed most of it.** The forty-three cases that were
exercised by hand and enumerated here now exist as running assertions in
`harness/tests/t7_store_and_seams.py`, which is strictly better than a prose list — so the
list is gone rather than kept as a second specification that can drift from the first.

Two things from that enumeration are still not asserted anywhere. The third — no history
line from three of the routes — was closed on 2026-08-13 and has its own entry below.

- **Twenty-way contention.** T7 runs two and four simultaneous captures, matching D5's two
  devices. The twenty-way case is what found `request_queue_size` at its default of 5 —
  8 served, 12 reset by the OS — and re-running it at the end of every turn buys nothing
  the smaller case does not. If that constant is ever lowered, nothing will notice.
- **The bare-interpreter start.** The server runs on system `python3` with no venv, which
  is what makes `python3` rather than `$(PYTHON)` correct in the Makefile. T7 imports the
  module under whichever interpreter runs the harness, so it cannot see this.

**Cost**: low and bounded, which is the difference from the entry this replaces. Each is a
single known case rather than a whole package nothing looks at.

**Why not fixed**: both cost more at every turn end than they can return.

### The three writes that changed no state now leave a history line — closed 2026-08-13

Recorded 2026-08-11 as one line about `PUT`, widened on 2026-08-13 when a review found the
same hole in two more routes, and closed the same day. What it said: no `PUT` correction,
`DELETE` undo or review answer appends to `history.jsonl`, because `store/master.py:_log` is
reached only from `record_capture` and `set_state` and a corrected set hint, a removed record
and a SKU written onto a card are none of them state transitions. `do_mark_sold` was the
counter-example that kept the rule from being "the server does not log": a sale IS a
transition, so it logged.

**The premise was true and was never the question.** "The store logs state transitions" is a
description of the store's vocabulary. `store/__init__.py` describes the same file as the
audit trail and says the history IS inventory truth over time — a claim about physical
positions in a box, not about the state enum. Once the two sentences are put side by side the
omission stops looking like a rule and starts looking like a gap that a rule was standing in
front of.

**Decided route by route, because the three are not one case.**

- **The correction (`do_put_card`) logs `corrected`.** D3 rung 1 makes the capture toggle a
  claim the ladder trusts ahead of the catalog, so the value this route changes is what
  decides the condition row, the price and the listing. The route overwrites the record and
  then overwrites the sidecar with the same values, so on return nothing anywhere holds what
  the card used to claim. The event carries `{"from": ..., "to": ...}` per field, nested
  under one `changed` mapping so that a `from` of `null` survives the None-dropping
  convention — a dropped `from` would read as a field nobody touched, which is the opposite
  of a first claim being made.
- **The undo (`do_delete_card`) logs `removed`, and this is the one the old text argued
  against.** It objected that naming a transition for a record that no longer exists reads as
  the tombstone `docs/specs/capture-app.md` section 3 forbids, and called it a D10 question
  rather than a logging one. Settled: a tombstone is a record left in `inventory.json` that
  every consumer downstream has to learn to skip, and there still is none. `history.jsonl` is
  a different kind of file, and it already held a `captured` event for the deleted record —
  the question was never whether it may describe a card that is gone, only whether it may
  describe one once and stop. **D10's index reuse is what decides it**: undo releases the
  position to the next capture, so without the line the log reads `captured 3/2`,
  `captured 3/2` — one key over two physical cards with nothing between them. The name is
  `removed` rather than `undone` because `undone` names a button and this names what happened
  to the record.
- **The answer (`do_review_answer`) logs `answered`.** `Inventory.set_state` takes a `sku`
  and `cli/cmd_emit.py` moves a matched position to `pushed` with its own join's row, so a
  later run can overwrite what a human chose while `review.json` goes on saying
  `cleared_by_human` beside it. The queue entry records that a person answered; only this
  line records what he answered, which queue's offer governed it, and the reason code the
  card was queued under.

  **The overwrite hazard was closed on 2026-08-22, and the line still earns its place.**
  D3 rung 0 (`variant.HUMAN_ANSWERED`) has `cli/resolve.py` read the answered
  `sku` + `condition` off the inventory record and `join_batch` resolve straight to that
  row, so a later run reproduces the choice rather than deriving one over it. The residue is
  narrow and deliberate: an answer whose SKU the current export no longer carries, or
  carries under a different Condition, still falls through to the ladder rather than being
  guessed at, and an emit that lists the resulting row does write it onto the record. What
  the line uniquely holds has changed shape rather than gone away — the record is now the
  durable home of *what* he answered, but `set_state` writes those same two fields from
  `cmd_emit`'s push and `master.Card` has no field naming the writer, so the record cannot
  say which of the two put them there. Only this line says a human did, names which queue's
  offer governed it, and carries the reason code the card was queued under.

**What shipped**: `SERVER_EVENTS` and `_history` in `server/capture_server.py`, and
`check_history` in `harness/tests/t7_store_and_seams.py` — 30 assertions. Every event is
appended to `Inventory.events` inside the route's own `Store.write()`, so the line and the
change it describes commit together or neither does. None of the three names is a member of
`master.STATES`, which is what keeps `_state_before_sale` — the one place in the product that
reads this file back — from restoring a reversed sale to `corrected`.

**Seen to fail before it was believed.** Fifteen mutations of the shipped code, each run
against the new section: dropping any of the three log calls (6, 6 and 5 red lines), logging
a correction unconditionally rather than only when a value moved (1), flattening `changed` so
a null `from` disappears (4), renaming an event to a listing state — `removed` as `captured`
and as `identified` (1 each, from the disjointness check) and `corrected` as `staged` (3,
because the sale-reversal path then reads the correction as the state to put back) — dropping
the state or the paid-answer flag from a removal (2 each), naming the wrong queue on an
answer (1), renaming the record's timestamp key (2), keeping None-valued extras (1), and
writing straight to `history.jsonl` instead of onto the snapshot (1).

Four of them initially produced a `KeyError` traceback instead of a red line. The section's
reads were hardened with `last_event` until every mutation reports rather than crashes, which
is the same reason `answers` exists one section above it in that file.

**A sixteenth passed, and it is worth recording rather than tuning away.** Logging the review
answer *before* the route validates the offer changes nothing observable: the refusal raises
inside the same `Store.write()`, so the snapshot and its queued events are discarded whole.
That is the seam doing its job rather than a hole in the section — it only reaches disk when
combined with the direct-write mutation above, which is how the pair was measured.

**What the lines do not cover.** Six things, all deliberate:

- **Nothing in the product reads them.** No route serves `history.jsonl`, no screen shows it,
  and the only consumer outside the harness is `_state_before_sale`, which is looking for
  states and skips all three of these by construction. The audit value is a person with a
  text editor, which is what an audit trail is for — but it means a line that stops being
  written is invisible to everything except T7.
- **A `PUT` that changes no value logs nothing**, by choice, and that includes one whose only
  effect is repairing a sidecar that had drifted from the record. The event answers *when did
  the claim change*, and a no-op has no answer; the cost is that a silent repair leaves no
  trace.
- **`_history` rebuilds `Inventory._log`'s record rather than calling it**, so the store could
  add a key to its own lines — a schema version, a run id — and the server's would not follow.
  T7 pins the three keys they share against a line the store wrote, and nothing pins more
  than that.
- **The event vocabulary lives in two places.** `master.STATES` holds the states and
  `SERVER_EVENTS` holds these three, and a reader of `history.jsonl` has to know both. A third
  list naming every event would be one more thing to hold in step, which is the trade taken.
- **The removal line does not say which queues held the card**, though the response does, and
  it does not record that the photo and sidecar were unlinked. What it carries is what cost
  money: the state, the sku, the run, and whether a paid identification went in the bin.
- **`do_capture`'s replay path still logs nothing**, correctly — a replayed `capture_id`
  writes nothing, so there is nothing to record.

---

### The border search is measured against one rig, on one day

`geometry/detect.py`'s tone path was measured at **0 of 53** against the Gate B photographs
on 2026-08-22, and a border search was added that finds 53/53. T6 covers it with
`_rig_scene`. What that leaves is smaller than what it closed, and it is not nothing.

**The synthetic case reproduces a mechanism, not a photograph.** `_rig_scene` is built from
the measured numbers — border-ring sides 33 / 65 / 82 / 66, card artwork spanning 88 to 231
— and it does make the tone path refuse for the reason the rig makes it refuse. But it is
still a drawing. There is no rig photo in this repo and there cannot be one: `captures/` is
gitignored, twice, once under an opsec heading. So the harness can prove the border search
handles the *mechanism* and can never prove it handles the *lighting*.

**The 53 are one sample of one rig state.** One camera position, one lamp, one stand, one
afternoon, one set. A second lighting setup, a sleeved card, a foil under raking light, or a
black-bordered card on a dark mat are all untested and all plausible. 53 is a great deal more
than the zero this file could point at last week; it is not a detection rate.

**What would close it.** A second physical run under deliberately different lighting, with
the frames scored through `detect_card` and the result committed the way T1's score is.
That is a Gate C-shaped task, not a harness one — and it needs a decision about where rig
photographs may live, given the opsec rule that keeps `captures/` out of git.

**Not blocking anything.** The crop-retry path is a rescue for weak reads, and Gate B
produced none: 53/53 at high confidence with zero retries, so `detect_card` was never
reached in anger. Recorded so a green T6 is not read as more than it is.

### A capture-time claim crosses ten hops and nothing binds them together

Recorded 2026-08-22, from the multi-game foundation work (D21-D25). Nothing here is broken
today; what is missing is any mechanism that would stop the next claim field being broken
quietly.

`set_hint` and `metadata_finish` are the two claims the operator sets on the capture screen,
and D21 is about to add a third — `game` — with D23 proposing a fourth. Each one is the same
value carried by hand through a chain of independent restatements, and the chain is the
finding. Written out rather than counted, because the list is the register:

1. `app/src/CaptureScreen.tsx` — the control and the client state it lives in
2. `app/src/types.ts` — the shape the wire speaks
3. `app/src/server.ts` — the body `POST /capture` actually sends
4. `server/capture_server.py` — the route pulling the field off that body
5. `server/capture_server.py:sidecar_payload` — the JSON written beside the photo
6. `server/capture_server.py:PUT_FIELDS` — what the correction route is allowed to change
7. `store/master.py:Card` — the dataclass field
8. `store/master.py:Inventory.parse` — the reload filter
9. `store/master.py:allocate_capture` — the keyword pass-through
10. `identify/sidecar.py` — `_HINT_KEYS` / `_VARIANT_KEYS` and the `Capture` it builds, then
    `pipeline/join.py` as the consumer that finally reads the claim

**Two of them fail silently, and they are the two that matter.**

- **`Inventory.parse` filters on `Card.__annotations__`.** A field the dataclass does not
  declare is dropped on reload rather than kept, and nothing anywhere says so. The record
  is written, the response is correct, the file on disk carries the value, and the next read
  hands back a card that never had it. That behaviour is deliberate and documented on
  `Card.capture_id` — it is why the retry guard could not live in the sidecar alone — so the
  filter is right and its silence is the debt.
- **`record_capture` upserts over a literal tuple**, `("photo", "set_hint", "metadata_finish")`.
  A re-record copies exactly those three attributes onto the incumbent. A fourth claim added
  everywhere else in the chain would survive a first capture and be discarded by every
  re-record, which is the harder failure to see: it works until the operator corrects a card.

The third restatement of the same list, `PUT_FIELDS`, is the one that already behaves —
`_reject_unknown` refuses a body naming anything outside it, so the correction route fails
loudly. That is the shape the other two want.

**Cost.** Bounded but not small, and it is paid at exactly the wrong moment. Every symptom
appears at the far end of the chain — a claim missing from a sidecar, a finish that reverts
after a correction — and the debugging starts at the screen. Gate B's six defects included
one of this family already: review answers written by a route that nothing on the join path
consumed, which took a real run to find.

**The fix WAS BUILT on 2026-08-23, with the `game`/`note` wire.** `CAPTURE_CLAIM_FIELDS` in
`store/master.py` now binds `record_capture`'s upsert loop, `allocate_capture`'s pass-through,
`sidecar_payload` (via `CLAIM_WIRE_NAMES`) and the server's `PUT_FIELDS` (derived, no longer a
literal), with the import-time assertion that every name is declared on `Card` — hop 8's
silence became a refusal, and T7's `check_capture_claim_chain` iterates the tuple so a new
claim is covered the day it is added.

**What the tuple measurably cannot reach**, recorded by its own builder so the entry keeps
telling the truth: the three app-side hops (no Python constant reaches a `.tsx`, and `tsc`
sees a field *added* to `types.ts`, never one omitted), and **a fourth restatement found
during the build** — `cli/cmd_identify.py` constructs a `master.Card(...)` literally rather
than through `allocate_capture`, so it carries the claim names by hand and nothing binds it.
Correct today, unbound tomorrow.

**Why it is a debt and not a plan.** The tuple is the easy half. The app-side hops (1-3) stay
hand-carried whatever the store does, because no Python constant can reach a `.tsx`, and
`make typecheck` sees a field added to `app/src/types.ts` and never one omitted from it. So
the fix narrows the chain rather than closing it, and the remaining gap should be named when
it lands rather than discovered later as an over-claim.

### The `reason codes` row cannot see a constant nobody published

Recorded 2026-08-22 with the row itself.

It reconciles the three places the review reasons are published — the constants in
`pipeline/variant.py` and `pipeline/routing.py`, `REASON_LABELS` in
`app/src/ReviewQueue.tsx`, and the enumerated list in `docs/DESIGN.md` — in every direction
where one of them names a string. What it cannot report is a new reason constant that
appears in none of them: `self_named_strings` deliberately answers "is this string defined
here" rather than "which strings here are reasons", because the second question needs a
heuristic and a heuristic on a blocking row is a guess that stops commits.

**Cost.** A reason emitted by the pipeline and rendered on screen as a bare machine string,
which is the outcome `docs/DESIGN.md`'s two-size label rule exists to prevent. Small: the
same commit that adds the constant almost always adds the label, and the row catches every
case where it does not add the doc line.

**What would close it.** An explicit roster in each module — the shape `routing.py` already
half has in `UNPRICEABLE_REASONS` — read by this row instead of the self-naming convention.
That is a change to two modules this workstream does not own, and it is worth doing when one
of them is next opened rather than reached into now.

### The `env vars` row runs in one direction only

`scripts/docs-audit.py:check_env_vars` walks **docs to code**: every environment variable a
markdown file names must exist somewhere real. It does not walk the other way, so a variable
that is real and documented nowhere never fires, and the row stays green while saying nothing
about it.

Found 2026-08-23 by a test author, not by the audit. `PKMNSCAN_ALLOWED_ORIGINS` — the
allowlist that stands between an unrelated browser tab and a hard delete — existed for a day
and a half, documented in no `.md`, while the row read "9 documented, all real". So did
`PKMNSCAN_EXPORTS`.

**The part worth keeping is not the two names, it is the comment that sat above one of them.**
`server/capture_server.py` asserted, in prose, that the variable was "documented in the docs
the same day it landed" and that "`make docs-audit` has a blocking check … so an undocumented
one here fails a commit". Both halves were false, and the second was false about the very
mechanism it was invoking. That comment is now a correction rather than a claim, kept in place
because it is where the next person looks to find out whether adding a knob is safe.

**Why the reverse direction is not simply switched on.** Finding "a real environment variable"
means deciding what counts as one — `os.environ` reads, `getenv` with and without a default,
names assembled from a prefix, and a test's own scaffolding, which sets and restores several
that are deliberately undocumented. That is a heuristic, and D16's rule is that a finding
blocks only when it is provably wrong. A blocking row built on a guess about what looks like a
variable is the shape that gets a gate switched off. The honest options are an advisory row,
or a registry the code and the docs both read — neither costed yet.

Both variables are documented now. The one-directional check is not fixed, and the next one
will go the same way.

### Misc cards reach the Batch API under Pokemon's prompt — closed 2026-08-23

**This one cost money and produced confident nonsense, and it was the highest-value item
in this file.** Recorded 2026-08-23; closed the same day, in the one commit its fix
demanded.

What it argued: the owner ruled that `misc` cards — the occasional Yu-Gi-Oh, Weiss
Schwarz, foreign-language or Magic card, about 1% of stock — **are** identified and
submitted to the Batch API, and a correct `misc_card_v1` profile existed that
`identify/batch.py` never asked for. `ImageRequest` carried no strategy field,
`build_request` read `prompt.SYSTEM_PROMPT` / `MODEL` / `MAX_TOKENS` / `SCHEMA` straight
off the module, and `_collect` called `prompt.parse(text)` bare — so every request in a
batch was built from the Pokemon profile whatever game the card was, and a Magic card so
read came back **confident and wrong**, the no-threshold-fires failure shape of T1's
recorded misses. The `prompt mismatch` warning in `--dry-run` said so out loud, and
promised to stop firing on its own once the seam moved.

What shipped: `ImageRequest.strategy`, defaulting to the Pokemon profile so every caller
predating the field — harness T1 included — submits exactly what it always submitted.
`build_request` reads everything model-facing off `prompt.profile(item.strategy)`;
`run_batch` refuses per item, by name and before submission, any strategy the dispatch
cannot answer (`unwritten_prompt`, `unknown_strategy`) — excluded from the batch, counted
in the run report as a failure bound for the main queue, never submitted under another
game's prompt, never dropped. `run_batch` and `collect_batches` carry
`{custom_id: strategy}` so `_collect` parses each answer under the profile that produced
it. `cli/cmd_identify.py` threads each card's sidecar strategy, refuses an unregistered
game under its own `unknown_game` code, shows every refusal in the preflight so
`--dry-run` prices only what will be sent — and the mismatch warning retired exactly as
it promised, the comparison it printed having stopped being true.

The cache moved in the same commit, as this entry required. Staleness is judged per
position against the fingerprint of the profile that would read that card today —
`store/cache.py:stale_prompt` and `weak_and_uncleared` take a `{position: fingerprint}`
mapping now — and each write records the hash of the profile that read the answer.
Existing Pokemon entries are untouched and keep hitting: their recorded fingerprint is
the Pokemon profile's, which is still what a Pokemon card is judged against.

**The one piece that did not ship: the operator's `note` still does not reach the misc
prompt.** `set_hint` rides on templates `identify/prompt.py` owns (`user_with_hint`,
`hint_clause`), so threading the note the same way means that file growing a note clause
on `Profile` and a `user_text` parameter — a prompt-contract change with its own
fingerprint questions, not a transport change. Left open deliberately rather than
smuggled through `set_hint`, which would tell the model the note is a stack label.

### Six registry fields are authored, audited, and read by nothing

`pipeline/games.py` is swept by four audit rows, so every field in it is kept *consistent*.
Nothing checks that a field is *consumed*. Measured 2026-08-23 by walking all sixteen fields
for a real code read, excluding the registry's own accessors and the audit itself:

| field | consumer |
|---|---|
| `located` | CLOSED 2026-08-23 — consumers: `_Places` and the three card decorators, `pipeline/join.py`'s pooled-label helpers, `cli/resolve.py`'s reports, and the three app views; the Fulfillment exclusion is asserted in `fulfillment.spec.ts` |
| `finish_by_rarity` | **nothing** — present in `types.ts`, read by no code. D23's chip narrowing is unbuilt |
| `product_line` | **nothing** — D25's "becomes a real reader" is unbuilt |
| `product_line_rarities` | **nothing** — appears once, in the registry, and is not even in `types.ts` |
| `rarities` | only `require`'s emptiness guard; no screen renders them |
| `prompt` | per-card: nothing — see the entry above |

`card_aspect` and `crop_bands` were in this table until 2026-08-23 and are now wired.

**Each of the remaining six needs a design decision, not a wire.** `located` needs a rule about
where a position label may render; `finish_by_rarity` needs the rarity picker; `product_line`
needs the per-game catalog partition. Wiring one without its decision would put a behaviour in
the code that no entry argues for — which is the opposite failure to this one and worse.

**The general shape, worth stating once:** the audit rows police the registry against the
exports. Nothing polices the registry against the *code*, so a field can be perfectly consistent
and entirely inert. D22 says "a field no consumer reads is a field nothing keeps honest", and
this table is that sentence measured.

### `removed` names two different things — resolved 2026-08-23

**THE OWNER TOOK THE FIRST OF THE THREE WAYS OUT: rename the STATE.** D26 drafted `removed` and
shipped **`retired`** (`store/master.py`), so the card state and the history event no longer
collide; the event keeps its on-disk name `removed` (`server/capture_server.py`), and nothing
already written to `history.jsonl` moved. The analysis below is kept because it is the argument
the rename rests on, and because the mechanism it describes is still exactly what would bite
the next name collision.

D26 drafted a `removed` **card state** — `sold`'s sibling for a card pulled out, damaged, lost
or given away. `server/capture_server.py` already defines `REMOVED = "removed"` as the **history
event** capture-undo appends.

They cannot both exist under those names. The server states, and T7 asserts, that no event name
may be a member of `master.STATES` — because `_state_before_sale` scans history backwards for
the last event naming a state and filters against that tuple. Add `removed` to `STATES` and a
months-old undo event starts parsing as a state, and a reversed sale becomes restorable to
`removed`.

**Nothing catches it at import; the T7 disjointness case DOES catch it at build time.**
`harness/tests/t7_store_and_seams.py` asserts `set(SERVER_EVENTS) & set(master.STATES)` is
empty, and asserts separately that `master.RETIRED` is in `STATES` and not in `SERVER_EVENTS`.
Three ways out were available — rename the state, rename the event, or narrow the reader — and
the owner chose the first, because the event name was already written into `history.jsonl` on
disk. "Nothing catches it at import" stays true: there is no module-level assert in either
file, and T7 is the only guard.

### The `fixtures/` guard is one tool wide — found 2026-08-30

`.claude/settings.json` denies `Write(./fixtures/**)` and `Edit(./fixtures/**)`. `CLAUDE.md`
calls that directory ground truth and says never modify it. **Bash is not in the deny list**,
so any write reached through a shell — a one-line `python3 -c` that opens a path under
`fixtures/` for writing, a heredoc, `cp`, `sed -i` — goes straight past it, silently and with
no prompt.

**Measured the day it was found, by walking through it without noticing.** The session that
built `fixtures/orders-shipping.csv` wrote it with a `python3` script and only discovered the
rule existed *afterwards*, when a `Write` of a sidecar into the same directory was denied. The
CSV was the deliverable and its creation was instructed, so nothing was harmed — what the
episode establishes is that the guard did not participate in the decision at all. An agent
that reaches for a script rather than for `Write` never learns the directory is protected.

**What it costs is the four `_untouched` exports rather than the new file.** Those are the
byte-exact ground truth T2 asserts against and D25 built the per-game catalogs from; a
whitespace normalisation or a re-save through a CSV library would change bytes nothing in the
harness re-derives, and the failure would surface as a fixture test disagreeing with a real
TCGplayer export weeks later. The deny rule reads as protection against that and supplies it
against two tools out of three.

**Why it is not fixed here.** The permission layer is the wrong place: a deny list cannot see
what a script writes at run time, and the pattern broad enough to catch it — denying `python3`,
or shell redirection — would take `make harness`, `make check` and `scripts/docs-audit.py`
down with it. That is the same trade D16 refuses for `--no-verify`, where switching off a
prose reminder also switches off the three opsec rules.

**The tractable route, named rather than built: check the bytes at commit time instead of
intercepting the write.** Git already holds the hashes, so a pre-commit rule that refuses a
staged modification to any pre-existing `fixtures/*_untouched.csv` is a read-only check on the
path that already decides whether a commit proceeds — permitted by D18, unlike anything that
writes. It would also be honest about the distinction the deny rule currently blurs: **adding**
a fixture is ordinary work, and **modifying** the ground-truth four is what must not happen.
Deliberately not built in the session that found it, at the owner's instruction.

**Not the same gap as the PII one, though they rhyme.** This repo has no secret or PII scanning
either — the pre-commit hook's only content rule is the code-card regex — so a fixture carrying
buyer names would commit clean. That one is about what is *inside* a file nobody scans; this one
is about *which tool* wrote it. Neither covers the other.

## Reporting defects — a check runs but can report the wrong thing

### `check_reason_codes` is anchored on the labels and the doc, so a bare constant is invisible

Found 2026-08-23, live: `rarity_claim_mismatch` was defined in `pipeline/variant.py`, emitted
by the ladder, and carried by neither `REASON_LABELS` nor `docs/DESIGN.md`'s enumeration — and
the row read **"12 enumerated, 12 labelled, all defined", green**. Had it fired, the queue
would have drawn a bare machine string, which is the exact outcome the two-size label rule
exists to prevent and the exact drift the row was built to catch.

The four reconciliations all START from the labels or from the doc and verify against the
constants. No direction starts from the constants, so a reason born in the pipeline is
invisible until someone remembers to publish it — which is the failure shape of every entry
in this file.

**Why the fifth direction is not simply added.** "A constant in `variant.py`" is not a
reason; the harvest is `self_named_strings`, which also collects ladder stage names and every
other `X = "x"`. Telling a reason from a stage mechanically means walking the AST for
`Resolution(stage=REVIEW, reason=NAME)` call sites — knowable, deterministic, and blocking-
grade, but it couples the check to `Resolution`'s call shape. Worth building; not worth
building at 4am on a tree two agents are mid-edit in. Until it exists, the row's green means
"everything published is consistent", not "everything emitted is published".

The triple was completed by hand the same night, so the row is honest again — about the
thirteen it can see.


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
  index-mode primitives now have cases, but no case drives a real git index. It bites
  hardest on `check dispatch`, whose whole subject under `--staged` is the blob and not the
  file executing; that path was driven by hand at integration — stage an unwired auditor,
  exit 1 — and by hand is where it stays.

---

## Closed 2026-08-24 — the self-test nobody ran

Kept rather than deleted, because what closed it is smaller than what it teaches.

**`python3 scripts/docs-audit.py --self-test` was RED, and had been for some time.** One case
in `tested_by reach` — the one that replays the historical false claim `store/queues.py` citing
a test that does not import `store` — was pinned to **T3**, and T3 had since begun importing
`store` itself (commit `548515b`, where D7's fungibility amendment made it build a real store to
exercise rung 0 and the `committed` flag). The claim stopped being false, so the case that
asserts a false claim is caught stopped catching one.

**`make docs-audit` was green throughout, and so was every commit.** Nothing ran `--self-test`:
not the git hook, not `make check`, not the Stop hook. A checker whose own self-test nobody runs
is a checker nobody has watched fail — which is the argument `docs/GATES.md` makes for the
harness, turned on the tool that audits the docs.

**Two fixes, and the second is the one that matters.** The case moved to T5 and states its
requirement in the comment — *this case needs a test that reaches `pipeline` and not `store`* —
naming T2 and T5 as the only two left and saying to move it again rather than weaken it.
And `make check` now runs `audit-self-test`.

**It is deliberately NOT in the git hook**, and that is D18 rather than taste: `--self-test` is
the one mode of that script that writes, into a temporary directory it creates and destroys, and
nothing that writes may run on the path that decides whether a commit proceeds. `make check` is
invoked by a person on demand, so it is not that path.

**The residual gap, stated so it is not read as closed:** `make check` is not automatic either.
The Stop hook runs `make harness`, not `make check`, so a red self-test still surfaces only when
somebody asks. That is the same standing this file gives every on-demand check, and it is better
than the nothing it had.

---

## The supervisor's known gaps (D53, 2026-08-30)

Three, none of them closable without more machinery than the failure is worth today. Recorded
because a green `make up` should not read as a promise none of them exists.

- **A request accepted but not yet inside `_dispatch` is uncounted by the drain.** The counter
  wraps the dispatch seam, which every verb funnels through — but a connection that has been
  accepted and whose request line is still being parsed is in neither state. The window is
  microseconds and closing it means reimplementing `handle_one_request`, which is a
  reimplementation of stdlib in the one file that most wants to stay boring.

- **The parse pre-check catches syntax errors only.** `scripts/serve.py` refuses to restart into
  a file that does not `compile()`, which is what makes editing safe while the watcher is
  running. An `ImportError`, a module-scope `NameError` or a bad constant still kills the new
  child, and there is **no rollback to the old one** — the last-good process is already gone by
  then. The containment is the fast-failure cap: after five quick deaths the supervisor stops
  respawning, keeps running, keeps watching, and says so. Fixing it properly means keeping the
  old child alive until the new one has bound, which is the socket-passing design D53 names and
  rejects for v1.

- **The reload notice has no automated case, and three attempts to write one are the reason
  this entry exists rather than a green test.** `ServerReloaded` renders nothing until the boot
  header CHANGES between two responses, which makes it unusually hard to drive from Playwright:
  a stub layered over `fulfillment.spec.ts`'s helpers did not win the route, `route.fetch()` to
  decorate a real response fails outright, and a body-stubbing version left the screens making
  too few requests to produce a second header. **Two of those attempts PASSED against a build
  with the notice rendered unconditionally** — vacuous in two different ways — and were deleted
  rather than kept, because a case that cannot fail is worse than no case: it is a green row
  asserting nothing.

  **What is actually verified, and how.** The header is observed reaching the browser and being
  readable cross-origin (a request-log probe over the real server: eight responses, all carrying
  `X-Pkmnscan-Boot`). The notice was rendered and photographed appearing on `#/inventory` after
  a real watcher restart, and photographed NOT appearing on `#/fulfillment` under the same
  conditions. **What guards it structurally** is that it hangs off `hasChrome`, the same
  condition the nav uses — and `fulfillment.spec.ts:noWayOut` already asserts `.app-nav` is
  hidden on his view, so the condition itself is covered even though this consumer of it is not.

  The breach that would evade all of that is somebody rendering `<ServerReloaded />`
  unconditionally in the shell. If this is worth closing, the tractable route is a spec that
  serves the whole capture wire itself rather than layering over another file's stubs.

- **The swap gap.** Between the old child exiting and the new one binding, a request gets
  `ECONNREFUSED`, and `app/src/server.ts` deliberately has no retry — so it surfaces as
  `unreachable`, which reads as "the server is down". Measured at tens of milliseconds. Named in
  D53 with the fix that was considered and declined.

## Prose that outran the code

- `docs/specs/audit-retirement.md` restates a check roster and a count that the shipped
  registry no longer matches — the retired number reappeared in a doc nothing audits, and
  is already wrong there. `CLAUDE.md` tells sessions to read specs as settled, so this one
  needs a status line saying which of its premises failed under execution. Two more checks
  landed on 2026-08-13 — `tested_by reach` and `check dispatch` — so the drift is wider
  than when this was written, and it will widen again with every check. That is the
  argument for the status line rather than for a correction: the restatement is the defect,
  and re-deriving its number would only reset the clock on it.
- `.claude/commands/docs-audit.md` tells the reader exit 2 means the coupling question,
  but the command it prints in step 1 runs without `--staged`, and coupling only runs
  under `--staged`.

## D60's guards see tokens, never arguments

`scripts/prose-guard.py` is the only thing comparing two versions of a doc, and it compares
HARD TOKENS — backticked identifiers, file paths, decision ids, measurements, dates. A
rewrite that keeps every backtick and loses the reason the entry exists passes it silently
and completely. That is the residual risk of the whole D60 exercise, and nothing mechanical
can close it: judging whether a paragraph still carries its argument is D16's layer 3, which
is a model reading prose and is deliberately never a gate.

`--facts` is also on no gate at all. It needs a BEFORE, which only exists while a rewrite is
in flight, so it is run by hand. The two rows that DO gate — `decision structure` and
`entry budget` — check the tree as it stands and cannot see what a change removed.

Two deliberate token removals stand against the D60 baseline and are not defects: the
supervisor's stdout line reporting the stack up, which reads as an unregistered subcommand when
backticked inline and is an indented output block now, and a bare `make` span that read as a
target called "make" when it sat beside another make span on one line.

---

## One card renders three ways on one screen (2026-08-30)

Found by the owner looking at five copies of Moonfall in box 3 and seeing the `Number` row
disagree between them. Two defects and one symptom, separated here because only two of the
three are defects.

### `printed_total` is guarded as `null` and arrives as an empty string

`app/src/BoxBrowse.tsx:864` and `app/src/CardLocations.tsx:85` carry the same expression:

    return printed_total === null ? number : `${number}/${printed_total}`

**The line above it in both guards `number` for `null` or blank, and this one guards
`printed_total` for `null` alone.** Two emptiness tests in one function, one field apart.
`printed_total` is stored as `""` on **174 of 715 records that also carry a number**, so those
take the else branch and render a trailing separator with nothing behind it — `198/219/`.

Cosmetic, and it costs a quarter of the store. Not fixed here because the two call sites are
one of the pairs `docs/DESIGN.md` would rather see merged than edited twice, and merging them
is a change with an argument attached rather than a one-line repair.

### The set code the model glued on is stripped for the key and never for the display

D55 removes a glued-on set code **by shape, and only after the join key has missed** — that is
a rule about matching, and nothing applies it to what a screen draws. **Nine numbers carry
one, with three different separators**: `UNL • 198/219`, `UNL - 198/219`, `UNL / 120/219`.

**The visible cost is larger than nine rows, because disagreement propagates.**
`server/capture_server.py:_agreed` returns `None` when the copies of a group do not all say
the same thing, deliberately and for a good reason — a number lifted off whichever copy the
dict yielded first would be a confident answer about a group that has none. So five Moonfall
copies storing three spellings of one number make the **group** report no number at all, while
each card's own detail row still shows its own raw variant. One card, three strings, one
screen, and the group between them silent.

Not fixed here because the repair has a real choice in it — normalize at capture, normalize at
read, or teach `_agreed` to compare folded — and picking one is a decision entry, not a patch.

### The stripped panel was the stranded card, not a third defect

The fifth Moonfall drew no card block, no `Mark sold`, no `Retire` and `sku: null`, and it
read as the copies panel failing on a null SKU. It was not. `_agreed`'s own docstring records
that the SKU-less group is a deliberate collection of *"cards with nothing in common but the
operator's query"*, so a card with no SKU correctly forms its own group and correctly offers
nothing that depends on one.

**That card should never have been in it.** `3/37` was resolved by its run — the run's
`pricing.json` names the position under SKU `9191486` — and then lost the stamp to the D7 cap
that `cli/cmd_emit.py` used to apply to `uncommitted_positions`, sold at 14:41, and was out of
reach of every later re-emit by D57's invariant. Repaired 2026-08-30 from the run's own
paperwork; `GET /search?q=moonfall` now returns one group of five.

**What is worth keeping from it**: a SKU-less group renders as a panel with its controls
missing, and the owner read that as breakage rather than as a category. Whether that category
should announce itself is a design question nobody has asked.

### Two departed copies in one box render as two identical rows

Reported the same day as *"I'm seeing two box 1's"*. There is one box 1. There are two sold
copies of `Vi, Peacekeeper` in it, at stored indices **67** and **106**, and both draw the
string `Box 1 · departed` with nothing whatever beside it to tell them apart. Two physical
cards, one row repeated.

**D58's label is right and is not what is wrong here.** A departed card is in no slot, and
printing the slot number would print the number that now belongs to its successor — a lie
about a shelf. So the label drops it, correctly.

**What is wrong is that the disambiguating value is already in the payload and the row throws
it away.** `GET /search` returns `place.index` of 67 and 106 on those two rows. D58 itself
draws the distinction this needs: *"The STORED index never moves — it is the
`/inventory/<box>/<index>` path"*, while `Place.slot` is the countable number that shifts. The
index is not a slot and printing it is not the lie D58 refuses.

**It scales with sales, which is why it will get worse rather than stay a curiosity.** Four
departed Moonfalls already draw four identical rows in box 3, and the only thing separating
them on screen is the neighbor text underneath — which is the *shelf's* fact, not the card's,
and goes blank on the copies whose neighbors are themselves departed.

Not fixed here because it is a rendering decision with D58 next to it, and D58 is an owner
ruling about exactly this label. It wants an entry, not a patch.
