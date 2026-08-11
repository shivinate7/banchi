# Audit retirement — execution spec

Planning output of the 2026-08-10/11 review sessions; owner-approved. The executing
session implements from this file, top to bottom, and asks nothing. Every judgment call
below is already made; deviating from one is an owner conversation, not an implementation
choice.

Scope: scripts/docs-audit.py and its doc surface, plus two hand-fixes. Nothing here
touches pipeline code, harness test logic, or any gate. `make harness` must be green
before and after every commit in this plan.

## 0. Committing this file — read first

- **D18 does not exist until the first commit lands it.** This file cites D18 throughout,
  and the decision ids row blocks on a citation with no heading. The first commit
  therefore lands this file AND the D18 entry (section 5) into docs/DECISIONS.md
  together, plus the one-line governed_by addition to docs/map.py. Committed separately,
  the audit blocks either way.
- **Future names are deliberately never written here as paths or backticked make
  invocations.** The paths row blocks on a backticked path that does not resolve; the
  make targets row blocks on a backticked or fenced make invocation naming a target the
  Makefile lacks. The script and target this plan creates are named in prose only until
  they exist — docs-gen still is; audit-history stopped being one the moment it landed,
  and section 7 now writes its real path. If a future name must be written as a real
  reference before it is built, the sanctioned route is a line in
  scripts/docs-audit-allow.txt with a reason — the mechanism already covering
  PKMNSCAN_IMAGE_MIRROR and T7.
- **Verbatim doc text below sits in blockquotes, never fenced blocks.** The audit reads
  every line of a fenced block as code, so a fenced quotation of prose mentioning a make
  target would be scanned as a command reference. Blockquotes scan as prose. Keep it that
  way when editing this file.
- One deviation from the approved D18 wording, mechanical and deliberate: the docs-gen
  target is mentioned without backticks, because the target does not exist (nothing
  generates today — that is D18's own framing note) and a backticked mention would block
  every commit of the file carrying it.

## 1. Order of operations

Items are named; the step numbers from the planning sessions survive as aliases only —
the D17 rule, applied to plans: positions drift, names do not.

| order | item | alias | size | waits for |
|---|---|---|---|---|
| 0 | d18-and-spec | — | 2 doc edits + 1 map line | — |
| 1 | staged-read | step 2 | ~8 lines | nothing; any time after 0 |
| 1 | defect-fixes | step 1, widened | ~8 lines, 2 files | nothing |
| 1 | json-output | — | ~10 lines | nothing |
| 2 | audit-history | — | ~47 lines | json-output |
| 3 | count-deletion | step 4 | −188 firm, −269 ceiling | an audit-history baseline run |
| 4 | evidence-check | step 3 | ~17 lines (+12 optional) | count-deletion — see below |
| 5 | baseline-refresh | — | rerun audit-history | evidence-check |

**Correction to the approved order, found while writing this spec:** evidence-check was
approved to run "in parallel". It cannot. It adds two named report rows, and while the
count row is alive the docs publish a total that goes stale the moment a row is added —
a mechanical block at commit time. It lands after count-deletion. Nothing else about it
changed.

**audit-history is diagnostic only, forever.** Never wire it to a hook, a gate, or CI.
Section 7 records why.

Withdrawn — do not repropose:

- **Generation of the command/target doc blocks** (planning alias step 6): measured net
  +6 to +11 lines, and it puts generation seams in CLAUDE.md, the file agents read first.
- **Generation of the current-gate line** (planning alias step 5; approved early, then
  superseded by D18's empty seam list): the line changes at most twice more in the
  project's life, a hand-maintained fact at that rate needs no machinery, the current
  gate row already blocks drift at 36 lines, and the threat model wants the fact at
  read-time in CLAUDE.md rather than behind a command.
- **The GATE_FIELD sibling-literal design** for the criterion check: section 4 records
  the mutation that kills it, so it is not rediscovered.

## 2. staged-read

In scripts/docs-audit.py, staged mode scopes by the staged file list but reads content
from the worktree: a file staged at version A and edited on to version B is audited as B
while the commit carries A. Same bug class as the staged-scoping incident this audit
already had once.

Fix: under --staged, content for staged files comes from the staged blob — git show with
the colon-path form — through the existing subprocess helper, not from disk. ~8 lines: a
staged-aware read used by the staged-mode scan. Whole-tree mode is untouched.

## 3. defect-fixes

Both are live false sentences in files agents read. Under this project's threat model
the docs are the context window, so these are the lede of the review, not a footnote.

(a) **harness/tests/t1_id_eval.py, module docstring.** Line 8 today, verbatim:

> Pass: overall_accuracy >= 0.95.

That is incident #1's false sentence, alive two lines above the corrected literal.
Replace with the criterion verbatim: Pass: holdout_accuracy >= 0.95. Then see (c),
which makes the class checkable.

Line 3 today, verbatim:

> ~50 official card images from pokemontcg.io across 3 SV-era sets, identified through the

The committed score is 150 images across ten sets. Fix by removing the numbers, not
updating them — restated counts rot on the next refresh. Suggested wording: "Official
card images from pokemontcg.io across SV-era sets — sample size and set count are
EVAL_IMAGE_TARGET and MIN_EVAL_SETS below — identified through the".

(b) **scripts/screenshot.sh, lines 8 and 80.** Both cite build-order step 8 for the Vite
capture app, which is build-order step 7; line 80 is user-facing output that names the
wrong milestone. The earlier approval was the numeric fix. Superseded: cite the
deliverable by name, not position — build-order numbers were renumbered once already
(the Makefile reconciliation commit), and a name cannot re-rot.

- line 8: "(build-order step 8)" becomes "(when the Vite capture app lands)"
- line 80: "Unblocked by build-order step 8 — see docs/GATES.md and docs/DESIGN.md."
  becomes "Unblocked when the capture app's views exist — see docs/GATES.md and
  docs/DESIGN.md."

No new checker for step-number citations in code: two occurrences repo-wide, and the
bucket rule's smallest tier already says the deliberation costs more than the class. The
convention — name the deliverable — is the guard.

(c) **Scoped extension of criteria wording to docstrings — recommended, ~12 lines.** In
files under harness/tests, any docstring line beginning "Pass:" must normalise-equal
PASS_CRITERIA (ast.get_docstring plus the existing normalise helper; the files are
already parsed). This is not the paths tax: that tax comes from running a heuristic
extractor over free prose — roughly half the paths row's cost is false-positive
suppression — while a "Pass:" line in a test module is a self-identifying claim with
ast-readable ground truth two lines away. Near-zero false-positive surface; blocks, like
the rest of the criteria rows.

The general rule this encodes, for any future extension of prose checking: police prose
only where the claim self-identifies and the ground truth is adjacent and
machine-readable; otherwise delete the restatement instead of policing it. Line 3's
counts are the second kind — fixed in (a) by removing the numbers; no counts checker
gets built.

Findings fold into the existing criteria wording row — no new label, no row-count
interaction — so (c) may land with defect-fixes or with evidence-check, whichever commit
is cleaner.

## 4. evidence-check

Everything here was verified 2026-08-10.

The score file is tracked: git ls-files under harness/results/ returns README.md and
t1.json, and git check-ignore reports not ignored (.gitignore excludes harness/images/,
not harness/results/). The file carries a gated_on value of "holdout", written at run
time by the same code path that selects the split — evidence of execution, not a
restated literal.

Three parts, two new report rows:

(a) **Criterion names the gated field** — row `criteria evidence`, mechanical, always
runs. For every t1 score file under harness/results/ (one per configuration): take the
payload's gated_on, append "_accuracy", and require that field name to appear in the
test's PASS_CRITERIA string. Zero score files is itself a finding. This catches
incident #1's class at the layer it lived: "overall_accuracy >= 0.95" does not contain
"holdout".

(b) **Committed staleness** — same row. src is the last commit touching any of
harness/tests/t1_id_eval.py, harness/eval/fixtures.py, identify/prompt.py (a prompt
change changes the measurement; the score file records the prompt fingerprint). evid is
the last commit touching harness/results/. Fresh iff git merge-base --is-ancestor of src
into evid exits 0; the same commit on both sides is fresh (verified live). Stale blocks.
Needs a returncode-aware variant of the git helper (~4 of the ~14 lines) — the current
one discards exit status. Deliberately timestamp-free: the ancestor test survives
rebases, and this repo already rejected mtime heuristics once, in the staged-changes
docstring.

(c) **Staged staleness** — row `evidence freshness`, advisory, staged mode only,
~3 lines: any of the three source files staged while nothing under harness/results/ is
staged prints the question. Advisory for D16's stated reason: a blocking question trains
you to reach for the no-verify flag, which also disarms the opsec rules in the same
hook. No minimum-lines floor here — a two-line threshold edit is exactly the dangerous
edit.

Known limits, recorded so the row is read honestly: (a) and (b) compare against the last
recorded run, so an uncommitted harness edit is invisible to them; (c) covers the staged
half of that window; the stop gate, currently armed, runs the harness at every turn end,
which narrows the rest without closing it.

**Anti-pattern, recorded so nobody rediscovers it:** a GATE_FIELD literal set from the
HOLDOUT constant, placed beside PASS_CRITERIA, with a check that the criterion names it.
Killed by one mutation: the line that selects the split (near line 300 of the test)
switching to the TUNE constant. GATE_FIELD still reads holdout, PASS_CRITERIA still says
holdout_accuracy, the two agree, and the gate reads tune — string-to-string agreement
rebuilt one layer down. The payload's gated_on is written by the selection itself, which
is why (a) reads the JSON.

## 5. d18-and-spec

The entry below goes into docs/DECISIONS.md verbatim, after D17. Mechanical
consequences: the new heading satisfies the decision ids row; docs/map.py's scripts
entry adds D18 to governed_by in the same commit; D16's own text is untouched by this
commit — its count sentence changes in count-deletion, where code and docs move
together.

> ## D18 — A generator may write. Nothing that writes may gate a commit.
>
> D16 forbids the audit writing, and gives the reason: "An agent that can edit the docs
> to satisfy its own gate will do exactly that, and each edit will look reasonable."
> That argument is about a *path*, not about a script, and D16 states it as a property
> of the script — which leaves a loophole wide enough to drive a build target through. A
> generator that rewrites a doc from a code constant is not the audit, breaks none of
> D16's letter, and recreates its failure exactly if it runs inside the gate: `make
> check` regenerates, the audit passes, nothing fails, and the doc now says whatever the
> code said.
>
> **Nothing that writes may run on the path that decides whether a commit proceeds.**
> D16's "Nothing on the audit path can write" is one instance of this rule, not the
> whole of it. Generation is permitted; generation inside the gate is not.
>
> **A seam is permitted only where a file's job is reference, and the permitted
> locations are listed here by name.** The list is currently empty. Adding to it is a
> change to this entry, argued on its own terms — not a judgement call made while
> implementing something else. This is the rule that keeps generation from spreading
> into the files agents read as argument, and it is stated early because it is the one
> most likely to be eroded quietly.
>
> **The list above is empty, and that is the finished state, not an unfinished one.**
> This entry was written while considering a generator for one specific number, and the
> act of writing the seam rule is what showed the better answer was to stop publishing
> the number at all. Nothing in this repo generates anything today. Read this entry as a
> guardrail placed across a loophole D16 left open — not as an invitation to use a
> mechanism sitting ready. A later session finding an empty list has found the intended
> condition. Adding the first entry means arguing that a fact must be published in prose
> *and* cannot be hand-maintained, and that argument has not yet been made once.
>
> **The test for "carries an argument": could a later session reasonably disagree with
> this line?** A count, a status word, a list of registered names — verifiable, nothing
> to disagree with. A threshold, a rationale, a trade-off — arguable, and therefore
> never generated. A second test, applied together with the first: if the span were
> replaced by its bare value, would the surrounding paragraph still mean the same thing?
> If not, the fact is load-bearing inside an argument, and the seam would cut it out of
> its reasoning. Prose that explains *why* is never a generation target, no matter how
> mechanically derivable the number inside it is.
>
> **The split is write-time versus check-time.** The docs-gen make target writes and is
> invoked by the owner. The pre-commit hook and `make check` verify freshness and fail —
> they never regenerate. Verification is not free: it means computing what the span
> should say and comparing, which is the generator's logic running on the audit path
> minus the write. Budget it as its own cost. Generated output is committed, so the
> owner's own `git diff` remains the last link in the chain, exactly as D16 requires for
> the semantic pass.
>
> **The generator is stdlib and reads with `ast`, for as long as freshness is checked in
> the git hook.** The hook runs `python3` with nothing installed, so a generator whose
> freshness check runs there cannot require a package. That rules out `cog` — otherwise
> the right tool, actively maintained, with a check mode built for exactly this —
> because it is a PyPI dependency and it executes the embedded Python, which would make
> the hook depend on the import graph staying free of third-party modules at module
> scope. Nothing enforces that today; `ast` does not care. **This constraint is
> contingent, not permanent: if freshness verification moves to CI, the stdlib rule
> stops binding on the generator and `cog` becomes viable.** Recorded so a later session
> reads this as a consequence of there being no CI today, not a standing judgement about
> the tool.
>
> **What this supersedes.** D16's paragraph beginning "Nothing on the audit path can
> write" stands unchanged as a statement about the audit. This entry generalises its
> scope: read that paragraph as the specific case and this rule as the general one. A
> fix flag on the audit remains forbidden by D16, and this entry does not soften it — a
> generator is a separate program with no findings, not the audit gaining a write mode.
>
> **The failure this prevents:** a generator on the commit path turns every wrong
> constant into a confidently published sentence, with the audit green and no diff a
> reviewer would question. Checking lets two things disagree in public. Generating makes
> one thing true everywhere, including when it is wrong.

## 6. count-deletion

One commit — the code deletions, the D16 paragraph replacement, and the
.claude/commands/docs-audit.md edit move together, because the live count row compares
those docs to the registry and blocks if either side moves alone.

Verified 2026-08-10: no consumer of registered_labels, claimed_counts, _report_labels,
or COUNT_CLAIMS exists outside scripts/docs-audit.py (repo-wide grep, venv excluded).
Re-run that grep before cutting. scripts/status.py is safe on its own: it derives its
"docs audit clean" line by counting ok rows in the rendered report, so it self-heals
when the row count changes.

Delete, by name:

- constants: SELF, COUNT_CLAIMS, _NUMBER_WORDS, _COUNT_CLAIM_RE
- functions: claimed_counts, _report_labels, registered_labels; the Registry NamedTuple
- from check_registry: the source parameter, the registry read and its
  severity-downgrade branch, the COUNT_CLAIMS loop, the check count report.add, and the
  docstring paragraphs about the count row and the confused-reader rule
- from the self-test: the sections "the registry reads itself, and the published count
  is checkable" and "the reader is honest about a shape it cannot read" (81 lines
  measured), plus any registry fixtures only they use

Keep, by name:

- the positional closure and _POSITIONAL_RE
- the check numbering and numbering in code report.adds, with their docstring paragraphs
- the self-test section "a check named by position is reported, per subset" — update its
  call sites for the rename below
- rename the residual function (suggestion: check_positional_references). Report labels
  never change: labels are the public contract, function names are not.

Arithmetic, measured 2026-08-11 by ast span: **−188 firm** (code), **−269 ceiling**
(code plus self-test sections). The one estimated boundary inside those figures is the
86/40 split of check_registry between count and numbering; everything else is measured.
Ast spans exclude comment-only lines, so the real diff runs slightly larger than the
figures. The planning estimate moved four times (−250, −235, −107, −275, −269), so
re-measure on the branch before declaring a number in the commit message.

**D16 replacement, verbatim.** It replaces item 1 of D16's three-layer list in full —
the three paragraphs beginning "Mechanical", including the count sentence, the
count-row-changes-sides paragraph, and the named-never-numbered paragraph. Items 2 and 3
of the list are untouched:

> 1. **Mechanical** — `scripts/docs-audit.py`, stdlib-only, run by the pre-commit hook
>    and by `make docs-audit`. Every check is deterministic, and **blocking is the
>    default**: a finding is mechanical when a reference is provably wrong — a path that
>    does not resolve, a `make` target that does not exist, a threshold that disagrees
>    with `docs/GATES.md` — and it exits 1, because there is no judgment to defer.
>
>    **A finding prints on exit 2 instead of blocking when judging it needs context the
>    script cannot have.** A decision id cited in a `.py` comment could plausibly become
>    a variable name one day; code that changed beside an unchanged doc is a question,
>    not a defect. A false positive that blocks is worse than one that prints.
>
>    **Neither the roster nor its count is restated here.** `make docs-audit` names
>    every check it runs, each row marked blocking or advisory, and that output is the
>    register. This paragraph used to publish the count, and keeping one restated number
>    honest cost more machinery than any other check in the file — all of it guarding a
>    fact nothing downstream consumed. Deleting the claim deleted the need. D18 records
>    the general rule.
>
>    **A check is named, never numbered** — the same rule D17 sets for the repo-map
>    check, enforced for all of them. Positions moved once already; the report's labels
>    are the names.

**.claude/commands/docs-audit.md**: the sentence enumerating the checks by name is
replaced by the same principle — the roster lives in the report: "scripts/docs-audit.py
already checks everything a machine can settle; run it and read the roster — every row
is named, and marked blocking or advisory. Your job is the part it cannot: prose that is
still grammatical, still well-formed, and no longer true." A restated roster rots
exactly the way a restated count does, one rename later.

## 7. json-output and audit-history

**json-output, ~10 lines.** A --json flag on scripts/docs-audit.py: one object — rows,
each carrying label, severity, summary, and findings as where/message pairs — plus the
exit code. Human render unchanged; --json wins when both are requested. Why: three
parser bugs in one planning session came from regexing the human render (a label-prefix
collision that zeroed the decision ids in code tally; the report footer leaking into the
last row's findings; gitignore artifacts read as findings). Owner's standing rule:
**nothing retires on numbers parsed from the human render.**

**audit-history, ~47 lines.** Built as `scripts/audit-history.py`, run by `make
audit-history` — named at execution per section 0, whose prose-only rule lapsed for this
one the moment the file existed. For each commit: git archive the
tree into a scratch directory, drop in the CURRENT scripts/docs-audit.py, run with
--json, tally per label. Classifier, from the planning session's hand version: a finding
is subject-absent when its missing target sits under a gitignored path (archived trees
lack gitignored files — this produced phantom findings for harness/images/) or when its
message is the does-not-exist family; everything else is substantive. Output: per-label
totals and a per-commit table. Add the Makefile target (named audit-history) and list it
in `make help` — the make targets row requires that.

**The by-construction confound, stated so nobody wires this to a gate:** every tree
after the audit landed is clean because the hook blocked anything else. Zero firings on
those trees cannot distinguish silent prevention from dead weight — nothing can. What
the tool gives: the pre-audit record, notice when a check starts firing, and a
retrospective baseline for any newly added check. It informs retirement decisions; it
never makes them, and it never gates.

Baselines from the planning session (the 8 trees authored before the audit existed,
current auditor, hand-classified): criteria wording 16 substantive findings; decision
ids in code 2; env vars 2; harness tests 1; paths 0 substantive — its one catch was a
doc naming docs/specs/ before that directory existed, which is allowlist-shaped;
everything else 0 or no unconfounded window (repo map, status sources, coupling, and the
count row all postdate the 8).

## 8. The bucket rule and the corrected ranking

Basis: ast spans of module-level defs, classes and assigns, plus self-test sections
attributed to the check they exercise. Comment-only lines and blanks are unattributed,
so every row's true weight is slightly higher. Shared helpers (iter_code_lines 19 plus
its fence self-test 14; gates_sections 26) are attributed to no row. The earlier
planning table counted function spans only; the understatement was uneven — six rows
carry no self-test at all while paths carried 65 lines — which is why this order differs
from it.

| row | code | self-test | total | unconfounded record (8 ungated trees) |
|---|---|---|---|---|
| check count | 188 | 81 | 269 | none — postdates all 8 |
| paths | 160 | 65 | 225 | 0 substantive |
| repo map | 159 | 0 | 159 | none |
| status sources | 94 | 0 | 94 | none |
| pass criteria + wording | 75 | 6 | 81 | 16 substantive |
| pkmnscan commands | 68 | 6 | 74 | 0 |
| harness tests | 65 | 6 | 71 | 1 |
| check numbering (both rows) | 41 | 29 | 70 | reachability shown once, post-audit |
| coupling | 59 | 0 | 59 | never exercised (staged-only) |
| allowlist | 46 | 10 | 56 | dormant by design; fires at build-order step 9 |
| make targets | 48 | 0 | 48 | 0 |
| decision ids (both rows) | 41 | 0 | 41 | 2 (the code row; the docs row 0) |
| env vars | 40 | 0 | 40 | 2 |
| current gate | 36 | 0 | 36 | 0 |

**Which convention the last column uses, and the fact that no tool reproduces it.** Those
figures are the planning session's hand classification, counted by hand over the 8 ungated
trees. `scripts/audit-history.py` counts the same window two other ways and lands on
neither: criteria wording 25 per-tree / 6 distinct against a recorded 16; env vars 5 / 3
against 2; harness tests 3 / 3 against 1. Only one of the three gaps has been run to
ground — decision ids in code, recorded as 2 and actually 0, where every finding was the
injected auditor citing itself. The rest is an unwritten counting convention, not a defect
on either side, and the tool was deliberately not tuned until it agreed.

So the bucket rule below decides retirements using numbers that no tool currently
reproduces, and the three conventions disagree by up to 4x. That is tolerable only while
nothing sits near a boundary. **Any future retirement argument at a bucket boundary must
adjudicate the convention first, in writing, and before looking at which number favours
the cut.** Picking the convention after seeing which one clears the threshold is the
same move as tuning the classifier to hit 16 — it just launders it through a choice that
looks procedural. Re-deriving the hand figures, or replacing them with an instrumented
convention, is the honest way out and is worth doing before the next cut, not during it.

The bucket rule (boundaries stated on this basis):

- **Bucket 0 — no unconfounded window.** The check's subject postdates every ungated
  tree; it never had the opportunity to fire. Never retire on record; keep and
  instrument. (repo map, status sources, coupling — and the count row, retired on other
  grounds.)
- **Bucket 1 — total ≤ 60.** Keep regardless of record; the deliberation costs more than
  the code. (coupling, allowlist, make targets, decision ids, env vars, current gate.)
- **Bucket 2 — 60 to 110, with a window.** Keep if reachability is demonstrated;
  otherwise instrument and revisit once audit-history has a longer record. (pass
  criteria + wording: 16 findings, keep outright. pkmnscan commands, harness tests,
  check numbering: instrument.)
- **Bucket 3 — over 110, with a window, no substantive findings.** Demands an
  affirmative case, or it retires. (check count: retiring, section 6. paths: kept,
  below.)

**paths stays, on this affirmative case:** path rot tracks refactoring; the repo has
refactored once (the rename commit) and came back clean; build-order steps 5, 7 and 9 —
server, capture app, vendored catalog — each add directories, which is when a paths
check earns its keep or proves it cannot. Re-examine after those land. Roughly half its
cost is false-positive suppression, the tax section 3(c) explains and avoids.

Observation, no action attached: repo map is the largest surviving row and has zero
self-test coverage. If self-test investment happens, it lands there, not back on the
count.

## 9. Verified externals — do not re-research these

All verified 2026-08-10/11 from live sources (releases pages, live READMEs, or run
directly against this repo). Dates are release or last-push dates.

| tool | verified state | verdict |
|---|---|---|
| lychee 0.24.2 (2026-05-01) | run on this repo, offline and online: 2 links total; probe caught 1 of 8 reference styles used here | no adoption — these docs reference by backticked path, not link syntax |
| Vale 3.17.1 (2026-08-05; repo moved to the vale-cli org) | run with a 3-rule custom style: 149 findings, ~99% false-positive against docs; strictly per-file architecture | conditional: adopt at build-order step 7 for Fulfiller-facing copy — the DESIGN.md banned-word list is its native job. When adopted, move check numbering and numbering in code to Vale rules: they are single-file regexes kept in Python only for the stdlib-only hook constraint |
| markdownlint-cli2 (pushed 2026-08-10) | run: 565 findings, 91.7% one line-length rule | no adoption — syntax, never truth |
| pre-commit framework | docs verified: pass_filenames and always_run model per-file vs repo-wide scope; it stashes unstaged changes | not adopted (cold-clone pip dependency). Its stash behaviour is the origin of staged-read. The pkmnscan commands check needs both scopes inside one check, which its model cannot express |
| Sybil 10.1.0 (2026-06) | docs verified | the only tool reaching the constant-versus-runtime seam; requires pytest in a repo with a custom harness. evidence-check covers the seam instead |
| cog (pushed 2026-08-05) | releases and docs verified; a check mode and edit-guard checksums exist | rejected while freshness runs in the bare-python3 hook: PyPI package, and it executes embedded imports. The condition that flips it — freshness verification moving to CI — is recorded in D18 |
| adr-tools (last push 2024-04) | README live-fetched | authoring only; no hooks, no path association |
| log4brains (last push 2024-12) | README live-fetched | an @adr code-reference annotation is "coming soon", unshipped — and it points the wrong way: code references into the ADR, not decisions surfaced at the file being edited |
| pyadr (active 2026-08) | README live-fetched | lifecycle tooling; its pre-merge checks gate the ADR repo itself, never source files |
| MADR | README live-fetched | template only — no CLI, no hooks, no path association |

Two results, recorded as results rather than absences: **the DELETE list is empty** —
the off-the-shelf cluster is link syntax, prose style, and decision authoring, and none
of it attempts cross-file claim-against-fact checking, which is what every surviving row
is. And **scripts/decision-context.py is unserved** — nothing in the ADR ecosystem wires
decisions into an edit path.
