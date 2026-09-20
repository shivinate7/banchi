# The mechanization backlog — what a 14-agent audit found and this pass did not build

_Shelved 2026-09-12, on the owner's instruction: **"Down for the 17 trivial ones, along with
shelving the 23 other identified so that we can review them on a deeper after-the-matter
pass."** This file is that shelf. It exists so the deeper pass starts from the measurements
rather than re-deriving them._

**Read D173 first.** Its rule is that a rule which can be mechanically enforced must be, and
that a new rule is not finished until its enforcement exists or its unenforceability is argued.
**This file is where the unfinished half is kept honest.** A `NOT MECHANIZED:` sentinel in
CLAUDE.md's Hard rules names what a machine would have to see; an entry here names a mechanism
somebody has already designed and costed.

## How this was produced, and what that means for trusting it

Fourteen read-only agents surveyed every rule surface this repo has: CLAUDE.md's Hard rules and
Working agreement, its Commands prose, all ~170 entries under docs/decisions/ in four quarters,
docs/DEBTS.md, docs/GATES.md's open list, the owner's standing instructions in the memory
directory, and the existing enforcement surface itself. Three adversarial critiques then ran
over the merged list -- false positives and disablement, vacuity and D18, evidence and actual
harm -- and a judge ranked what survived by **(times the rule has actually been broken) x (how
cheap the mechanism is)**, not by how important the rule sounds.

**It rejected 32 proposals outright**, which is as much a result as the list it kept. And it was
not merely advisory: its rank-1 finding was a hole in a gate that same session had just added,
and rank 2 named a sentence in CLAUDE.md that is false on main today.

**Every figure below was read from the tree by an agent that did not implement it.** Verify
before building -- the coverage note at the end says what the audit did not reach.

## A note on how this file spells things that do not exist yet

**A `+` in front of a path, a `make` target or a `PKMNSCAN_` name means the thing does not
exist yet** — `+make opsec-selftest`, `+PKMNSCAN_PWARGS`. It is read
by the three mechanical docs-audit rows that verify a named thing is real, so a shelf document
can name what it would create without failing a commit on every line.

**The sigil is self-cleaning, which is the whole point.** Each of those rows FAILS when a marked
name EXISTS, so the `+` has to come off in the PR that builds the thing. A marker that could be
left on would turn every proposal here into a permanent exemption.

**Why the sigil and not an allowlist line.** `scripts/docs-audit-allow.txt` already accepts
"named before it is built" as a reason and is self-cleaning the same way, so it would have
worked — but it puts the name's status two directories from the sentence that uses it, and it is
an exact-match roster that every branch edits, so this one document would have added twenty-one
lines to a live conflict surface. The allowlist keeps the job it is actually for: a path meant to
be unresolvable FOREVER, the way `app/src/orderWalk.ts` records a deletion. A `+` says *not
yet*, which is a claim with an expiry.

## The 21 shelved mechanisms

Each carries what the audit produced for it: the rule in one sentence, the mechanism, where it
would live, the real incident it would have caught, the evidence that the break happened, the
legitimate case that must keep passing, the mutation arm that proves the guard can fail, and
what stops it being green over an empty input. **Ranks are the audit's own and are not
renumbered**, so a citation of rank 23 keeps resolving.

### Rank 18 — A filtered suite run must have exercised the tests it named.

**Cost:** small.

**Mechanism.** TWO HALVES, and the second is the rule. (a) At the top of the `design-check` and
`design-check-quiet` recipes, `python3 +scripts/pw-args.py check -- $(PW_ARGS)` splits the value
the way make will and refuses any bare POSITIONAL token that does not name an existing file
under app/tests/; flag-prefixed tokens pass untouched. (b) COUNT THE WORK: when PW_ARGS names
spec files, the recipe compares `.serve/design-check.json`'s `counts.total` against `grep -c
'^test(' ` over the named specs and prints a loud disagreement line. An outcome assertion cannot
see tests that never ran; only counting them can.

**Where.** the `design-check` / `design-check-quiet` recipes in the Makefile (859 and 875 — both
expand `$(PW_ARGS)` UNQUOTED, which is the mechanism of the bug); half (b) rides the verdict
file already guarded by the `verdict file` row and `make verdict-selftest`

**What it catches.** A FALSE GREEN over zero of its target cases: `PW_ARGS='--grep "the release
sends confirm"'` word-split, Playwright read the stray words as path regexes, and the run
reported 85/85 PASSING having exercised none of its seven target cases — "I nearly concluded the
defect did not reproduce." On the suite that asserts the Fulfiller's floors.

**Evidence it happened.** Verified the unquoted expansions at Makefile:859 and :875. TWO
sessions wrote the same memory file about it within a day (pw-args-word-splits.md and pw-args-word
-splitting-fakes-a-pass.md), which is the repetition signal that ranks it.

**Must keep passing.** `PW_ARGS=tests/brand.spec.ts` (the documented safe rig form), CI's shard
pair, and `--grep=the.press.that.sells` (dots for spaces).

**Mutation arm.** Run with `PW_ARGS='--grep "two words"'` — must refuse; with
`PW_ARGS=tests/brand.spec.ts` — must pass and the count check must reconcile; with `PW_ARGS="--
shard=1/3 --workers=1"` — must pass (both tokens flag-prefixed, and this is CI's own
invocation).

**Why it is not vacuous.** Half (b) prints both numbers every run; a verdict file it cannot
read, or a spec whose test count it cannot compute, is a printed disagreement rather than
silence.

**Escape hatch.** +PKMNSCAN_PWARGS=off, printed in the refusal.

### Rank 19 — Never write a waiter loop over a pattern — background the work and take its completion notification.

**Cost:** small.

**Mechanism.** One clause in the same Bash hook: refuse a `while`/`until` loop whose CONDITION
invokes pgrep, pkill, `ps -ef` or lsof and whose body contains `sleep`. Syntactic and
sufficient; the refusal names `run_in_background` and the Monitor tool. Do NOT ship the
companion clause that refuses launching a second live copy of a script (see rejected) — its
resolver is the machine-wide pgrep that has already reddened reap-selftest four times against an
unmodified reap.py.

**Where.** `scripts/guard-shell.py --hook` (PreToolUse on Bash), both rosters — BUILT.

**What it catches.** A waiter that matches itself. On 2026-09-12 a session that had already READ
the rule wrote `until ! pgrep -f 'scratchpad/drive.sh'`; the loop never fired, its chained work
never ran, a second copy raced a live one for ~15 minutes, and the owner caught it: "feel like 3
have been left for a while, just confirming you're actually checking."

**Evidence it happened.** memory/a-pgrep-waiter-matches-itself.md — the rule was written
correctly and in full on 2026-09-08 and broken by a session that had read it four days later.
Its own diagnosis is this audit's thesis: "phrased as an explanation to recall rather than a
prohibition to trip over."

**Must keep passing.** The sanctioned pid wait, a bounded curl probe, `gh pr checks --watch` and
`make design-check ARGS=--wait` (blocking waits, not polls).

**Mutation arm.** `until ! pgrep -f foo; do sleep 5; done` — refuse; `while ps -p $PID
>/dev/null; do sleep 5; done` on a pid this session started — pass (the file sanctions it, and
it polls a pid rather than a pattern); a bounded readiness probe carrying `curl -m` or an
iteration cap — pass.

**Escape hatch.** `PKMNSCAN_WAIT=off`, printed in the refusal.

### Rank 21 — A row that examined an empty subject must not print the same word as one that examined everything.

**Cost:** small.

**Mechanism.** Give `Report.add` an optional `scanned` integer and `render` a third tag — `none`
— where scanned == 0, with `as_json` carrying the integer so nothing parses the render. Have
every absence-row pass it (`paths`, `raw color`, `identifier spelling`, `shell substitution`,
`spec seal`, `doc hygiene`, `check numbering`, plus the eight rows staged mode narrows). Add an
arm to `check dispatch` — which already reads this file's own AST — requiring every check whose
signature takes the narrowed `docs` parameter to pass a scope, and record a per-row FLOOR in the
same literal so "the walk found 3 files where it found 278 yesterday" is a finding rather than a
shrug. The tag is informational: a scope of 0 must never FAIL, since some rows are legitimately
empty. In staged mode, print which rows were narrowed and over how many documents.

**Where.** scripts/docs-audit.py — Report.add / render / as_json, plus a new arm inside the
existing `check dispatch` row

**What it catches.** The repo's signature defect, retrofitted onto all 79 rows at once.
Verified: `render` prints `ok <check> <summary>` for ANY row whose findings list is empty (docs-audit
.py:173), with no distinction between "examined 3,039 references" and "examined none". On a
code-only commit staged mode narrows the markdown list, so eight rows print green over zero
documents and the compensating `coupling` row is advisory and runs in no other mode. Seven
absence-rows print a denominator in PROSE and assert no floor on it, so a wrong walk root, a
rename or an edited suffix list renders as clean.

**Evidence it happened.** The repo has already paid for this lesson twice, one row at a time:
`corpus_is_empty` exists because `decision structure` and `entry budget` "reported `0 entries`
in green" over an unreadable docs/decisions/, and `browser scope` refuses an empty dependency
set. Nothing generalised it.

**Must keep passing.** `recorded deletions` could reach zero entries by design and `check
numbering` finds nothing; the floor is DECLARED per row (0 permitted with a sentence) rather
than assumed to be 1. A fresh clone with no app/node_modules must not trip it — count TRACKED
files only.

**Mutation arm.** Point `raw color`'s walk at a non-existent directory — the row must print
`none` and the floor arm must fail; legitimately empty rows must print `none` and pass.

**Why it is not vacuous.** The new row's own subject is the other rows' counts, which cannot be
empty while audit() exists — it already reports "no audit() at all" and "audit() names none of
the checks" as distinct findings.

**Escape hatch.** PKMNSCAN_DOCS=off.

### Rank 22 — `make check` reports the state of every target, not only of the first one to fail.

**Cost:** small.

**Mechanism.** Rewrite the `check:` recipe to keep going on failure (collect each target's
status rather than `@$(MAKE)` in a bare sequence) and end with a per-target verdict table —
target, pass/fail/not-run — exiting non-zero if any failed. Same for `ci-check`.

**Where.** the `check:` and `ci-check:` recipes in the Makefile (387-410, 431-453), with
scripts/checks.py and `make help` updated so `check registry` and `check census` stay green

**What it catches.** A suite that cannot tell "the rest passed" from "the rest never ran". With
`reap-selftest` a standing red at slot 20 of 23, `suite-lock-selftest`, `serve-selftest` and
`verdict-selftest` never execute and the output reads as one failing test — and verdict-selftest
is D129's only guard. harness/run.py already writes the rule down for its own nine tests ("A
runner that stops at the first failure hides the state of everything behind it, which is the
opposite of what a status signal is for"); the target that decides whether the tree is sound
does the opposite.

**Evidence it happened.** Verified the fail-fast recipe: 23 sequential `@$(MAKE)` lines, no
`-k`. IMPORTANT CORRECTION to two surface readers and two critiques: D161 (a6287cb) ALREADY
moved the selftests last, so the standing red now dims three targets and not eleven — lint, vale
and typecheck run at slots 10-12, ahead of it. The pre-D161 measurement (a session recording its
final run as "the first run to reach every target", which caught three ruff errors every earlier
run had died before seeing) is historical. The rule is still worth mechanising; its current
blast radius is 3 of 23, not 11.

**Must keep passing.** A fully green run prints the table and exits 0. Exit status must still be
non-zero on any failure, or CI stops gating.

**Mutation arm.** Make an early target fail deliberately — every later target must still run and
the table must mark the failure and no `not-run` rows.

**Why it is not vacuous.** A target that was skipped for an environment reason (no vale binary)
must print `not a gate` rather than `pass` — see rank 27.

**Escape hatch.** Not applicable.

### Rank 23 — A claim a debt entry makes about a file's shape is true of that file.

**Cost:** small.

**Mechanism.** scripts/score-detect.py already HOLDS the names (Photo.name at :205-239) and
`_summarize` discards them. Have it write `declined_frames: [{box, filename, area, detail}]`
beside the count, and add one entry to _DETECT_CLAIMS asserting `len(declined_frames) ==
overall.declined`. A score file predating the key must read as "re-run the scan" — the row
already has exactly that finding shape at docs-audit.py:2530 — never as a wrong figure.

**Where.** scripts/score-detect.py (the writer) + a new pin in scripts/docs-audit.py's
_DETECT_CLAIMS / `detector standing` row

**What it catches.** A pinned figure standing beside a false claim, which `sole reader`'s own
docstring already rules is worse than no pin. DEBT6
(`docs/debts/006-measured-against-one-rig-or-not-at-all-closed-2026-09-09.md:50`) says "The 59
declined frames are named by box and filename in the score file." Verified false: harness/results/detect.json
carries `overall.declined: 59` and `per_box` integers, and `grep -c jpg
harness/results/detect.json` returns 0. So the eye pass §6 itself calls the ONLY thing that can
settle a false ACCEPT — the dangerous direction — cannot be started from the file §6 names,
while `detector standing` pins five numbers next to it and prints ok.

**Evidence it happened.** Read both: score-detect.py:286 writes `sum(1 for p in small if
p.detail < images.MIN_CROP_DETAIL)`; detect.json's keys are boxes_scanned, constants,
detector_files, detector_fingerprint, generated_at, image_count, not_measured, overall, per_box,
source — no filenames anywhere.

**Must keep passing.** A stale score file must be reported as "re-run the scan" and never block
a commit over an artefact nobody staged.

**Mutation arm.** Drop `declined_frames` from the writer — the row must go red; write it with a
length that disagrees with the count — red.

**Why it is not vacuous.** The pin compares a LIST LENGTH to the published count, so an empty
list with a non-zero count fails — the shape a bare count cannot see.

**Escape hatch.** PKMNSCAN_DOCS=off.

### Rank 24 — A guard must be able to fail, and be proved to fail by a planted defect — starting with the one that guards a bearer instrument.

**Cost:** small.

**Mechanism.** A +make opsec-selftest in a throwaway repo, on scripts/githooks-selftest.sh's
model: (1) stage a PNG outside captures/ — require refusal carrying the hook's own marker; (2)
stage one under demo-assets/photos/ — require allow; (3) feed scripts/guard-opsec.sh a code-shaped
 literal on stdin — require block; (4) feed it each of the five documented false-positive
shapes (the all-X layout placeholder, prose about the format, an alphabet walk, a phone-shaped
digit run, a window inside a longer hyphen chain) — require allow. In `make check`, never in the
git hook (it writes — D18).

**Where.** a new `make` target wired into `make check` (needs the four-file agreement — recipe,
`make help`, CLAUDE.md's check list, scripts/checks.py — which the `check census` and `check
registry` rows enforce)

**What it catches.** A narrowing that went one clause too far, or a refusal that stopped
refusing, on the one rule in this repo whose failure is a live unredeemed code — a bearer
instrument. Nothing proves either tier still bites.

**Evidence it happened.** Verified: `grep -rn guard-opsec Makefile scripts/checks.py
.github/workflows/` returns only prose mentions inside pre-commit and reference-transaction
comments; guard-opsec.sh contains zero `self-test`/`selftest` occurrences and is in no make
target. githooks-selftest.sh's 21 cases exercise reference-transaction, pre-push, post-checkout
and post-merge and never stage an image outside captures/ or a code literal. So the repo's only
bearer-instrument guard has ZERO arms while `make reap-selftest` has thirteen and `make revert-selftest
` rebuilds two real PRs — and this is the guard with a recorded history of being
switched OFF on 2026-08-03 for over-firing, then re-narrowed by three clauses nothing re-checks.

**Must keep passing.** All five documented false-positive shapes; demo-assets/photos/ (safe
because scripts/demo-photos.py refuses any photograph a QR decodes and refuses outright if the
decoder cannot load).

**Mutation arm.** Delete one of guard-opsec.sh's three narrowing clauses — an ALLOW case must go
red. Widen the layout pattern by one group — the allow cases must go red. Delete the image rule
from pre-commit — case (1) must go red.

**Why it is not vacuous.** Each arm must assert on the hook's OWN marker string, not merely on a
non-zero exit — githooks-selftest already learned that two of its cases were green for the wrong
reason until a refusal had to carry the marker to count.

**Escape hatch.** +PKMNSCAN_OPSEC_SELFTEST is unnecessary — skipped by not running `make check`.
The guards' own hatches are unchanged.

### Rank 25 — Exit 2 means a new question, not a state of the world.

**Cost:** small.

**Mechanism.** A tracked pin file beside scripts/docs-audit-allow.txt keying each STANDING
advisory finding to (row, where) with the sentence that justifies it. Self-cleaning in BOTH
directions: an unpinned advisory finding makes the run exit 2 (as now), a pin whose finding has
gone is stale and fails the commit, and the run's exit reflects UNPINNED findings only. Keep
every advisory row advisory — do NOT promote severity (see rejected).

**Where.** scripts/docs-audit.py — a new `advisory standing` row plus the pin file

**What it catches.** A permanently-lit advisory, which docs-audit.py:1367 forbids in its own
words ("A permanently-lit advisory would have taught us to skip exit 2 everywhere") and which
has a MEASURED consequence: memory/d-number-collisions.md records `renumbered ids` listing three
stale citations for an entire session while the session pushed anyway, "because `make check` was
green and the row is advisory."

**Evidence it happened.** Ran it: `python3 scripts/docs-audit.py --json` on main returns 79
rows, exit 2, 23 advisory findings — entry budget 13, breakpoint columns 4, views exposure 4,
game coverage 2 — printed by pre-commit on every commit in this repo (scripts/githooks/pre-commit
:281 echoes and ALLOWS).

**Must keep passing.** All 23 standing findings pass once pinned. They are deliberate: the 13
oversized entries (D60 rules size is a report, not a gate, and all ten were read innocent),
one_piece's authored matrix superset (D22/D23 — narrowing it would make two Pokemon eras
unclaimable), the two column-blind capture breakpoints (RunPanel.css:55 sets max-height:
calc(100vh - …), which no container query can answer), the four views-exposure notes.

**Mutation arm.** Introduce a new breakpoint above 1024 — red (unpinned); pin it with a reason —
green; fix it and leave the pin — red (stale).

**Why it is not vacuous.** Key the pin on (row, where) and never on the message text, or
rewording an advisory's prose invalidates every pin at once. Print the pinned and unpinned
counts.

**Escape hatch.** PKMNSCAN_DOCS=off.

### Rank 26 — A read of the API key is screened whichever tool performs it.

**Cost:** small.

**Mechanism.** A clause in the same Bash hook: refuse a command whose resolved READ target is
./.env (redirects, `cat`, `sed -n`, `head`, `grep -H` over it, `python3 -c` with the literal
path), and refuse a command whose output would carry an `sk-ant-` prefix (`env | grep
ANTHROPIC`, `printenv ANTHROPIC_API_KEY`). Fails OPEN on any command it cannot parse — a guard
that cannot determine the answer is not evidence the command is bad, which is pre-commit's own
stated rule. Print the sanctioned route: read `.env.example` for the shape, and let the process
load the real file itself.

**Where.** `scripts/guard-shell.py --hook` (PreToolUse on Bash), both rosters — BUILT.

**What it catches.** The one credential in this project that spends money, protected today by a
Read-tool deny rule in a session whose own system prompt says to prefer `cat`/`sed -n` over the
Read tool.

**Evidence it happened.** Verified .claude/settings.json's deny list is exactly `Read(./.env)`,
`Write(./fixtures/**)`, `Edit(./fixtures/**)`; .env.example:8 shows `.env` carries
ANTHROPIC_API_KEY. `cat .env`, `grep -r sk-ant .`, `env | grep ANTHROPIC` are all ungated. Ten
surface readers found the same one-tool-wide hole for `fixtures/` (DEBTS §8) and none found it
for the key. No measured leak — this is a fence, and it is the only fence in this list whose
harm is unrecoverable.

**Must keep passing.** `.env.example` in every form; `envfile.load()` from inside the product
(not a Bash read); `ls -la .env`; harness blocks that seal envfile.

**Mutation arm.** `cat .env` — refuse; `cat .env.example` — pass; `python3 -c
'print(open(".env").read())'` — refuse; a pipeline the parser cannot read — pass, and say it
could not parse.

**Why it is not vacuous.** The refusal prints the resolved target; the hook prints how many read
targets it resolved so "parsed nothing" can never read as "nothing to screen".

**Escape hatch.** PKMNSCAN_ENV=off, printed in the refusal.

### Rank 28 — Merge only from a checkout whose merge surface is current.

**Cost:** small.

**Mechanism.** Apply pre-commit's own ZEROTH RULE shape to the wrapper: scripts/merge-pr.py
refuses, before anything moves, when its own scripts/merge-pr.py or scripts/claim-ids.py differs
from `origin/main`'s copy after a fresh `git fetch origin` — naming the files and printing `git
fetch origin && git merge origin/main`. Fails open when origin/main is unreachable, saying so.
Do NOT build the `gh pr merge` PreToolUse refusal (see rejected): every measured incident went
through `make merge` from the wrong TREE, so the tree is the subject.

**Where.** scripts/merge-pr.py, with an arm in `make merge-selftest` (already in `make check`)

**What it catches.** Six measured merges from stale surfaces: two unclaimed decision ids
reaching main as raw slugs (PR #270 repaired by #273, #280 by #285), three PRs merged while
their claim commit's checks were still in_progress (#275, #277, #278 — #275's merge printed job
URLs belonging to the PRE-claim commit's run while the claim commit's own run was still going),
and one merge run from `main` itself (D143).

**Evidence it happened.** D151 measured 24 of 30 worktrees on this machine BEHIND the merge
surface and 16 missing the commit that introduced the claimer at all. That is the state in which
all six incidents happened.

**Must keep passing.** A current tree merges unchanged. A clone with no origin/main proceeds and
says it could not compare — revert-guard's and claim-stale's declared disposition.

**Mutation arm.** In a throwaway clone, revert scripts/merge-pr.py by one commit and run `make
merge ARGS="1 --confirm"` — must refuse and name the file; with the hatch — must proceed.

**Escape hatch.** +PKMNSCAN_MERGE=off, printed in the refusal.

### Rank 29 — A Playwright fleet takes the machine-wide suite lock before it spends the CPU.

**Cost:** small.

**Mechanism.** `scripts/suite-lock.py --hook` as a PreToolUse Bash guard on reap.py's model:
recognise a direct `playwright test` invocation (the same `_FLEET_RUNNER_RE` the `suite lock`
row already uses — one pattern, two callers), ask the existing lock file who holds it, and
refuse ONLY when another checkout holds it, naming that tree, printing `make design-check
PW_ARGS=…` and PKMNSCAN_SUITE_LOCK=off. Fails open on its own parse errors and on an unreadable
lock directory.

**Where.** scripts/suite-lock.py --hook, registered as a PreToolUse Bash matcher in
.claude/settings.json + .codex/hooks.json (D135), with an arm in `make suite-lock-selftest`

**What it catches.** The one bypass left in an otherwise excellent row: `npx playwright test`
typed into a shell, which no Makefile recipe mediates. DEBTS §16 states it — "none of it goes
through the Makefile, so none of it takes the lock" — and §11 incident 3 records the session
that ran design-check about eight times against the owner's live server while also driving it
from hand-rolled Playwright scripts, then killed the server mid-write.

**Evidence it happened.** The `suite lock` row reads Makefile recipe lines and app/package.json
scripts (docs-audit.py:10467-10529) and cannot see a shell.

**Must keep passing.** `npx playwright install`, `--list`, `show-report` (the named workaround
for the runner red), `codegen`, and a single-spec run while nobody holds the lock.
PKMNSCAN_LOCK_DIR must send the self-test at a throwaway directory so it never takes the real
lock.

**Mutation arm.** Hold the lock from a second PKMNSCAN_LOCK_DIR and issue `npx playwright test`
— must refuse naming the holder; with the lock free — must pass; `npx playwright test --list` —
must pass.

**Escape hatch.** PKMNSCAN_SUITE_LOCK=off, printed in every refusal, exactly as the target's own
refusal does (exit 75 there so a refusal can never read as a failing suite).

### Rank 30 — `ADD_TO_QUANTITY` stays a bare module constant on the reprice path — never a parameter, never a default, never reachable from a flag.

**Cost:** small.

**Mechanism.** An AST row: every `add_to_quantity=` keyword argument in pipeline/reprice.py and
cli/cmd_reprice.py must be the bare name `ADD_TO_QUANTITY` / `reprice.ADD_TO_QUANTITY` — never a
literal, a variable or an argparse-derived value — and neither module may declare a parameter of
that name. It must find at least the two sites that exist and report zero as a finding.

**Where.** scripts/docs-audit.py — a new row, `quantity constant`

**What it catches.** A parameter that DEFAULTS to 0, which keeps all five existing harness
assertions green while making the wrong value reachable. The doubling it prevents ALREADY
HAPPENED: ten live SKUs held more copies than this pipeline ever pushed, nine at exactly `2 ×
pushed − sold`, eight of them from one file (runs/2026-08-31-box3-01/import-subthreshold-riftbound
.csv) uploaded twice.

**Evidence it happened.** Verified the sites: `ADD_TO_QUANTITY = 0` at pipeline/reprice.py:112,
used at :816 and cli/cmd_reprice.py:392, with the argument written at reprice.py:799 and :567.
D100:64 has the measurement.

**Must keep passing.** `pipeline/join.py:add_to_quantity` is a DIFFERENT function on the EMIT
path, where the quantity legitimately is a variable (D7's `--quantity`). Scope the row to the
two reprice modules by name, never to the identifier repo-wide. Note: the sibling proposal to
pin `SCOPE_THIS_UPLOAD` the same way is correct and costs the same, but has zero measured
instances — build it second, in the same row.

**Mutation arm.** Change cli/cmd_reprice.py:392 to `add_to_quantity=0` (a literal, not the name)
— must go red; add a `scope`-style parameter named add_to_quantity — red.

**Escape hatch.** PKMNSCAN_DOCS=off.

### Rank 31 — Two identify batches may not run over one box, whichever door started the first one.

**Cost:** small.

**Mechanism.** Write the busy marker from the CLI too: `cli/cmd_identify.py` writes
`{run}/running.pid` with its own pid before submitting and removes it on exit, exactly as
server/pipeline_routes.py:1474 does. Add the T7 case the existing block is missing: start a
batch through the CLI seam and assert `POST /pipeline/identify` over that box refuses. Age-out
stays as it is — `_live_pid`'s floor is the run's own identifications.json — or a terminal crash
locks the box against the screen forever, which is worse than the double press.

**Where.** cli/cmd_identify.py + a case in harness/tests/t7_store_and_seams.py

**What it catches.** A paid batch started in the terminal that the screen cannot see, so a press
on #/runs submits a second one over the same photographs. This is the last money-spent-twice
path left open: D163's hash-before-decode asks the identification cache BEFORE it decodes, so a
sequential re-identify of the same box costs nothing — concurrency is not one of several money
risks, it is the only one.

**Evidence it happened.** Verified: `grep -c pid cli/cmd_identify.py` returns **0**, and
`running.pid` is written only by server/pipeline_routes.py:_spawn (PID_FILE at :158, marker read
at :730, write at :1474). So `_live_pid` returns None for a CLI run and `_busy_run` skips it at
the loop head. BREAK COUNT IS ZERO-MEASURED — nothing records a double batch having happened,
which is why this is ranked here and not at the top. Harm unit is the owner's money, which is
why it is not ranked lower. DEBTS §21 is the entry.

**Must keep passing.** A marker left by a crashed CLI run must age out through `_live_pid`'s
existing floor. A second batch over a DIFFERENT box must proceed.

**Mutation arm.** Pose a CLI-started run (marker present, pid live) and press the route — must
refuse; remove the marker write from cmd_identify.py — the case must go red. Note the existing
T7 case poses the pid BY HAND, so what it proves today is `_run_box`'s path-reading rather than
the claim above it.

**Why it is not vacuous.** The new case must start the batch through the CLI's own entry point,
not by writing the marker itself — that is the difference between proving the write happens and
asserting about it.

**Escape hatch.** None — it is a marker, not a refusal. The existing refusal keeps PKMNSCAN's
own behaviour.

### Rank 32 — Realign a run's records against the photographs on disk before anything reads a position out of the payload.

**Cost:** medium.

**Mechanism.** Assert the ORDERING, which no existing check covers: a harness case that drives
the real call path (a re-join after a mid-box delete) and asserts every position a caller reads
came through `cli/resolve.py:realign`, plus a docs-audit row requiring any module under cli/ or
server/ that reads the position keys of an identifications payload either to import realign or
to be on a NAMED list of modules that receive an already-realigned payload, with the reason
beside each.

**Where.** harness/tests/t7_store_and_seams.py for the call-path half; a scripts/docs-audit.py
row for the roster half

**What it catches.** A card described over its neighbour's photograph. Three measured incidents,
each found by a human: a re-join of box 2 wrote all 47 queue entries one position off (Wally's
Compassion described over a photograph of an Inteleon, caught before it was answered); the
`collided` outcome was added 2026-08-25 as ambiguous's missing twin and measured at two cards in
and one out with `departed` empty and nothing printed — a silent drop inside the function
written to prevent one; and 2026-09-02, box 1 deleted and its number reused, realign answering
`unverified` while everything after it read the CURRENT box's records.

**Evidence it happened.** The OUTCOMES are covered by T7 (refusals on an ambiguous digest, two
records on one digest, a digest-less record in a moved box, refuse_reallocated). "Before
anything reads a position" is a call-site convention with no reader.

**Must keep passing.** Tooling that reads a payload purely to REPORT what was submitted — the
run log, the manifest reader — must pass; D33 and D36 both protect those as the auditable
record, and the roster has to name them.

**Mutation arm.** Move a realign call below the first position read on the re-join path — the
harness case must go red. Add a new module reading position keys without importing realign and
without a roster entry — the row must name it.

**Escape hatch.** PKMNSCAN_DOCS=off for the roster half.

### Rank 33 — A copy is never offered to TCGplayer twice.

**Cost:** medium.

**Mechanism.** One field on store/master.py:Card, written by cli/cmd_emit.py's push loop beside
the existing `sku` stamp, recording that this physical copy reached an import file. The
committed set is then READ rather than inferred from a reading's silence, and a sale of a marked
copy ages the claim on the copy's own evidence. A copy pushed before the field exists carries no
marker and must fall back to today's arithmetic — otherwise the fix re-strands the 58 copies it
was built to release. Plus a T7 case.

**Where.** store/master.py + cli/cmd_emit.py, with a case in harness/tests/t7_store_and_seams.py

**What it catches.** The doubling in the store today, which is the brief's "a copy sent to
TCGplayer twice" on the owner's real inventory: nine SKUs sitting at `2 × pushed − sold`, eight
from one file uploaded twice. `staged` is written only by `pkmnscan reconcile --live`, which
this operator does not run, so the store cannot tell a sold-out listing from an import sitting
in Staged even in hindsight.

**Evidence it happened.** DEBTS §24 records the trade the operator took — 58 copies of real
backstock across 32 SKUs stranded, against an unmeasured number of staged rows — and D59 named
this field as its own reopening condition, D147 turned on not having it, §24 is the third entry
to do so.

**Must keep passing.** Legacy copies with no marker fall back to `_copies_out`'s existing
arithmetic and are still offerable, so the 58 stranded copies stay released.

**Mutation arm.** Push a SKU, mark one copy sold, re-emit — the marked copies must not be
offered again; delete the write from the push loop — the case must go red.

**Why it is not vacuous.** The case must drive the real `emit` press rather than writing the
marker itself, and must assert on the copies in the WRITTEN FILE (count the work), not on a
store field — an outcome assertion over the store cannot see a second offer that reached a CSV.

**Escape hatch.** None — it is a stamp, not a refusal.

### Rank 34 — A bare `#` on an owner-side screen is the count of cards in the box, never the stored index.

**Cost:** medium.

**Mechanism.** Teach scripts/sigil-check.py to follow ONE level of same-file local helper: a
`#{f(x)}` where `f` is defined in the same file and returns an expression naming `index` is a
finding. Keep the per-line `sigil-ok: <why>` escape. Do NOT take the nominal-type migration (see
rejected).

**Where.** scripts/sigil-check.py, already in `make check` AND in scripts/githooks/pre-commit
with its own self-test

**What it catches.** Exactly the one instance the rule has: CaptureScreen.tsx drew
`#{slotNumber(target)}` where `slotNumber` returned `String(target.index)` for any target with
no rendered label — on the row a person presses to UNDO — and the check was green over that line
from the day it was written until a human read it. The `#` and the field were three functions
apart, so the text match passed.

**Evidence it happened.** DEBT9
(`docs/debts/009-the-sigil-check-matches-text-so-a-renamed-local-walks.md:26`) records the trigger
firing. The entry's earlier sentence — "the evasion is available and has never been taken" — was
already wrong when written.

**Must keep passing.** The three legitimate sites the check found on its first run (BoxOps.tsx's
machine receipt, RunPanel.tsx twice over a capture-directory preview) carry `sigil-ok:` and must
keep passing; the helper-following version needs the same marker escape AT the helper.
Pricing.tsx:2641 and Orders.tsx:1205 name the index AS the index in prose and are deliberately
untouched.

**Mutation arm.** Re-introduce a same-file helper returning the raw index behind a `#{}` — must
go red; the same helper returning `slot` — green.

**Escape hatch.** PKMNSCAN_SIGIL=off, already printed (scripts/githooks/pre-commit:343).

### Rank 35 — A spec's standing is declared in the spec, and CLAUDE.md's pointer at it may not assert otherwise.

**Cost:** medium.

**Mechanism.** TWO changes to check_work_item_standing. (a) Widen `_WORK_ITEM_HEADING` to
capture the whole qualifier against a CLOSED vocabulary (`SERVER HALF ONLY`, `NOT VALIDATED`,
`NOT BUILT`, …) and treat the qualifier as part of the state on both sides. (b) Generalise from
one spec to docs/specs/*: read each spec's standing token from its own opening status line and
compare it to the state CLAUDE.md's Map bullet asserts for that path, both directions. Keep the
row's three existing protections verbatim — historical prose excluded (the "said X until <date>"
form), sets not order, and a bullet carrying no readable claim reported as UNWATCHED rather than
passing.

**Where.** scripts/docs-audit.py — the existing `work item standing` row (docs-audit.py:2902)

**What it catches.** Two live contradictions. (1) CLAUDE.md:2069 says docs/specs/one-process.md
is "SPECIFIED 2026-09-11, NOT BUILT"; that spec's line 3 says "specified and BUILT 2026-09-11",
D138 merged the same day, and CLAUDE.md's own `make up` block says "ONE PROCESS AS OF 2026-09-11
(D138)". The row prints ok because it is scoped to order-pipeline.md alone. (2)
docs/specs/order-pipeline.md:410 reads `### T2b — the rubber stamps. BUILT 2026-09-05, SERVER
HALF ONLY` while the client half exists (app/src/server.ts:3147,
app/src/OrdersShipStage.tsx:223) — the row passes because it captures only the first state word.

**Evidence it happened.** Both verified. Most of the cost is vocabulary: 13 of 20 specs carry no
`## STATUS` heading and standing is spelled three ways (`## STATUS — `, `**Status: ...**`,
`**STATUS, <date>: ...**`), so the spelling must be fixed before the row can read it.

**Must keep passing.** A spec that is a RECORD rather than a plan (audit-retirement.md, ui-research
.md, ui-redesign-options.md) with no standing asserted in CLAUDE.md either. For the
remainder the finding shape is "CLAUDE.md asserts a standing this spec has nothing to check it
against" — unwatched, not green.

**Mutation arm.** Change one spec's status line without touching CLAUDE.md's bullet — red; add a
qualifier to a heading whose pointer does not carry it — red.

**Escape hatch.** PKMNSCAN_DOCS=off.

### Rank 36 — Never lower a Fulfilment floor, and keep every floor constant equal to the figure docs/DESIGN.md's constraints table publishes.

**Cost:** small.

**Mechanism.** Lift each `| <name> | … >= N… |` row out of DESIGN.md's constraints table
(docs/DESIGN.md:1006-1011) and require the matching `const *_FLOOR = N` in
app/tests/fulfillment.spec.ts to EQUAL N — compared on the integer, never by substring, which is
the exact defect check_pass_criteria was hardened against when 0.9 matched inside 0.95. A
deliberate floor RAISE passes by editing the table in the same commit, which is what makes the
pair honest.

**Where.** scripts/docs-audit.py — a new row, `fulfilment floors`, on the `pass criteria` row's
model

**What it catches.** A session lowering BODY_FLOOR, PLACE_FLOOR, PHOTO_FLOOR or TARGET_FLOOR and
taking the whole browser suite green with it. These floors serve a real second person and D31
keeps the spec unweakened as a rule with no reader.

**Evidence it happened.** Values still agree (20, 32, 320, 44). The WORDING has already drifted:
fulfillment.spec.ts:33 says "Card photo in pull modal" where DESIGN.md:1009 says "Card
photograph … at desktop and at phone width" — the table's sentences sit beside the constants as
COMMENTS with nothing comparing them.

**Must keep passing.** The contrast row (">= 7:1") is not a px constant and is asserted
differently; pin only the four numeric floors the spec declares as constants, and report an
unparseable table row as UNREADABLE rather than as a mismatch.

**Mutation arm.** Lower PHOTO_FLOOR to 240 — the row must go red naming both sides.

**Escape hatch.** PKMNSCAN_DOCS=off.

### Rank 37 — Never narrow pipeline/games.py's rarity-to-finish matrix to what one export proves.

**Cost:** small.

**Mechanism.** Pin the SET, not its size: an explicit roster of the sorted (game, rarity,
finish) triples in the audit, or a digest over them. Any removal fails; any addition is a one-line
 diff somebody has to write. Do NOT ship a count ratchet (see rejected) — a count is
preserved by SUBSTITUTION, which is precisely what a session narrowing to "what this export
proves" produces: it removes uncorroborated pairs and adds the ones it just observed.

**Where.** scripts/docs-audit.py — a new row beside the existing `matrix superset` row

**What it catches.** The narrowing D22 recorded being tempted into and caught by hand:
`finish_by_rarity['Rare']` carried `normal` against an SV09 that stocks no plain-NM Rare, and
removing it would have made two whole Pokemon eras unclaimable — the wider export stocks 60
plain-NM Rares (Cosmic Eclipse 38, Crown Zenith 22). `matrix superset` blocks only on a pair the
matrix is MISSING; `game coverage` asks about the excess and is advisory with 2 standing
findings.

**Evidence it happened.** D22:19 has the measurement. Absence from one export proves nothing,
which is why the check must be about the matrix MOVING rather than about the export agreeing.

**Must keep passing.** Adding a new game raises the roster and is a deliberate one-line edit. A
genuinely wrong authored pair can still be deleted, by editing the roster with the deletion —
which is the intended visibility.

**Mutation arm.** Swap one pair for another so the pair COUNT is unchanged — must go red (the
arm a ratchet cannot kill).

**Escape hatch.** PKMNSCAN_DOCS=off.

### Rank 38 — Never add a generation seam without amending D18's named list.

**Cost:** medium.

**Mechanism.** A row that enumerates every executable under scripts/ whose AST contains a write
into a path `git ls-files --error-unmatch` reports as tracked (writeFileSync, `open(..., 'w')`,
write_text, os.replace, shutil) and reconciles that set against the named list parsed out of
D18's own entry, in both directions. Make the UNRESOLVABLE case a FINDING in its own words —
"this script writes a path this row cannot read; name it in D18's list or spell the target as a
literal" — never a silent skip, because a computed target is the shape that hides. Publish the
number of scripts enumerated with a floor.

**Where.** scripts/docs-audit.py — a new row, `seam list`, MECHANICAL

**What it catches.** A live stale rule inside the rule that governs all the others: D18 says
twice, in bold, that its seam list is empty and "Nothing in this repo generates anything today",
while scripts/build-mark.mjs has generated three tracked files since D102 landed 2026-09-05
(app/src/kit/markGeometry.ts, app/src/kit/markPalettes.ts, app/public/favicon.svg) — and `logo
parity` exists to reconcile one of them. D18's general rule (nothing that writes gates a commit)
is intact and well-guarded by `commit path`; its LIST is the part bypassed exactly as the entry
predicted, quietly, while implementing something else.

**Evidence it happened.** Verified the generator's three writes go through `resolve(ROOT,
'app/src/kit/markGeometry.ts')` at :104, :158 and :286 — literal by luck rather than by rule,
which is why the unresolvable case must be loud. `grep -n D18 scripts/docs-audit.py` shows
eleven rows citing D18 and not one reading the list.

**Must keep passing.** A script writing only into a gitignored or temp path — docs-audit.py's
own --self-test tmpdir, scripts/serve.py's .serve/ logs, demo-seed.py writing inventory/ — must
pass; gate on `git ls-files --error-unmatch` for the literal target.

**Mutation arm.** Add a generator writing a tracked path through a computed expression — must be
REPORTED, not skipped. Point the walk at an empty directory — must go red.

**Escape hatch.** PKMNSCAN_DOCS=off.

### Rank 39 — Every route the server dispatches is reachable from app/src/server.ts, and every exported write has a call site.

**Cost:** small. **Blocked by:** rank 1 (wire the self-test first, or the assertion that would catch this row breaking is itself ungated)

**Mechanism.** TWO assertions inside scripts/screen-freshness.mjs, which already loads the app's
TypeScript compiler, already builds the transitive call-graph closure classifying every
server.ts export as read or write, and already finds every call site in every .tsx. (a) CALL-
SITE FLOOR: every exported WRITE must have at least one call site. (b) ROUTE FLOOR: extract the
server's route table by AST from capture_server.py's do_GET/do_POST/do_PUT/do_DELETE (string
literals compared against `path`, plus module-level `re.compile` constants resolved by name) and
require each to appear as a path literal anywhere in server.ts. BOTH must PUBLISH their
denominator — the number of writes classified and the number of routes extracted — and FAIL
below a pinned floor, or a dispatcher refactored into a table, a decorator or a dict yields zero
routes and the row prints ok over nothing.

**Where.** scripts/screen-freshness.mjs (already in `make check` and `ci-check`; `check` is a
required GitHub status context, so this gates the merge with no new target, no census agreement
and no Codex mirror). It must NOT go in docs-audit.py: the pre-commit hook runs a bare python3,
and a regex over server.ts misses 8 of 73 routes (nested templates inside `${}`,
`${base}`-prefixed URLs), which would force 8 exemptions.

**What it catches.** The founding incident of CLAUDE.md's first hard rule — box delete, mid-box
delete-with-reindex and retroactive box-level claims all shipped with full T7 coverage and ZERO
client functions, with harness, lint, typecheck and docs-audit green.

**Evidence it happened.** Measured: 73 distinct routes extract cleanly and 0 are unreached, so
the route floor needs no baseline exemption list. The call-site floor yields exactly ONE finding
today — and I corrected the surface reader's framing: `moveCard` (app/src/server.ts:1649) has no
caller while `moveCards` (:1674) IS imported and called by app/src/BoxOps.tsx:27/:453 with
`indices: null` meaning every on-hand card, so D83's move IS reachable from the Manage box
sheet. The finding resolves by DELETING eleven dead lines, not by building a screen. Take the
floor for the vacuous green it repairs, not for a reachability harm it has yet to demonstrate.

**Must keep passing.** Six named families, all measured green: photoUrl() at server.ts:312
builds an `<img src>` and never a request(), so the extractor must read ALL path literals; the
three download-href builders (markdownFileUrl:2187, runFileUrl:2640, shippingFileUrl:3124);
reviewCatalog:991, which composes its path into a local `at`; the code-card track's five
functions, already excluded by banner rather than by name (D14) with the skipped count printed;
`GET /boxes/<n>`, a deliberate 404 explainer that survives a METHOD-AGNOSTIC comparison because
`PUT /boxes/<n>` is real — which is the argument for not making (b) method-aware.

**Mutation arm.** Export a new write with no caller — (a) must go red. Rename `path` in one
dispatcher so the extractor finds nothing — (b) must go red on the floor, where an unfloored
version prints ok.

**Why it is not vacuous.** Fix the self-test's last case in the same commit:
`ok(quiet.findings.length === 0 && quiet.covered.length === 0, 'no write sites, no findings')`
at screen-freshness.mjs:1860 asserts the OPPOSITE of the new floor.

**Escape hatch.** None — a make target.

### Rank 40 — Register a window keydown listener in useLayoutEffect whenever the effect's dependency array names state the handler reads.

**Cost:** medium. **Blocked by:** conversion of the four D128-shaped sites, then the rest, with zero disables

**Mechanism.** An eslint `no-restricted-syntax` selector: a CallExpression named `useEffect`
whose body contains `window.addEventListener('keydown'|'keyup', ...)` AND whose second argument
is a non-empty ArrayExpression. The message names D128 and both fixes — move to useLayoutEffect,
or hold the handler in a ref and pass `[]`. SHIP WITH ZERO INLINE DISABLES: convert the sites
first.

**Where.** app/eslint.config.js's no-restricted-syntax, as a fifth `*_RULES` array beside
FACING_MODE_RULES / SPLIT_COMMA_RULES / TWO_ARG_THEN_RULES / LOCAL_STORAGE_RULES (and re-listed
in each config block, as that file's convention requires)

**What it catches.** A key press answering to the render before the one on screen. D128 changed
exactly two sites and four more of the same shape remain: App.tsx:175 (deps [enabled, arm]
reading `arm`), App.tsx:220 (deps [enabled, path] reading `path`), ReviewQueue.tsx:1263 (deps
[queueOpen] reading `queueOpen`), Pricing.tsx:2164.

**Evidence it happened.** Measured: 22 keydown registrations across 15 files in app/src, 17
still in useEffect; only three files contain a useLayoutEffect at all. The correct alternative
already exists beside the defect — ReviewQueue.tsx:1252 uses the handlerRef + `[]` form and
passes the selector by construction.

**Must keep passing.** ReviewQueue.tsx:1252's ref form; any listener whose deps are all refs or
constants. DO NOT LAND until every site converts: a rule whose first commit needs seventeen
exemptions is measuring the codebase, not guarding it.

**Mutation arm.** Re-introduce a keydown useEffect with non-empty deps — lint must fail; the ref
+ `[]` form — must pass.

**Escape hatch.** An inline eslint-disable stating the argument, which is the file's own ceiling
— and the reason this is ranked here: the repo carries FOUR inline disables today, two of them
the argued localStorage pair app/eslint.config.js holds up as the acceptable maximum. Landing
this rule "with the remaining sites carrying a disable" would multiply that population by five,
in the file that says "a guard that is routinely disabled inline is one the next person disables
without reading."

## Rules where prose is legitimately the only tool

This list is worth as much as the one above. It is what tells a reader where prose is doing real
work rather than being skirted, and it is how D173's rule is satisfied honestly rather than by a
rubber stamp. Each entry says what a machine would have to be able to SEE.

- **Fix the cause, never the symptom — and read for the primitive that would make a workaround unnecessary before proposing one.**
  A machine would need: That two expressions answer the same question, one by identity and one
  by proxy, and that the identity already exists upstream. Nothing in this tree declares "this
  field is a proxy for that identity", and an AST cannot distinguish an identity from a reusable
  label. The earning incident is exact: three options were put to the owner for detecting a
  reallocated box on the capture restore — compare the box NAME, compare it narrowly, or do not
  detect — and every one was a heuristic standing in for `bid`, the never-reused id D145 had
  landed hours earlier. The owner's reply was "are any of these actually a good solution? or a
  bandaid". This is the owner's most important instruction and the least mechanisable one on the
  surface: it is enforced by review, or not at all.
  Nearest partial: One narrow, real slice: an eslint no-restricted-syntax rule banning the
  reusable box NUMBER as an identity comparison in restore paths, with `bid` as the sanctioned
  key and exemptions named by file. That covers the case that happened and nothing more. The
  commit-message-vocabulary version is rejected above.

- **Never raise Fulfiller impact as a counterpoint to an owner-side build decision.**
  A machine would need: That a sentence is using a downstream consumer as a VETO on upstream
  structure — recognising an argument's role, not a fact about the tree. A rule about how to
  reason, whose only possible reader is a person.
  Nearest partial: None, and a mechanism aimed at it would risk suppressing the legitimate half:
  the Fulfilment floors in app/tests/fulfillment.spec.ts and docs/DESIGN.md's constraints table
  ARE binding and ARE asserted in a browser. Build_now rank 36 pins those numbers; the
  argumentation rule stays prose.

- **One word from the owner licenses both halves of a merge — and "merge it" is the word while "ship it", "land it" and "looks good" are not.**
  A machine would need: Whether the owner NAMED THE OPERATION in conversation as against
  expressing satisfaction with the work. D42 rejects a phrase list by name and gives the reason:
  a session matching on phrases both balks at a plain "Merge" (recorded) and can be walked into
  a merge by anyone who says five particular words. Any mechanism here refuses a merge the owner
  actually asked for, which is worse than the prose failure it replaces.
  Nearest partial: Already built, and it is the right shape: `make merge` refuses a bare
  invocation, so the word is mandatory without being classified. It cannot widen what the hooks
  permit, because reference-transaction's allow rule 3 has always required the commit to be on
  origin first.

- **Never edit a document for the sole purpose of getting a blocked commit through — report the block instead of resolving it.**
  A machine would need: Why an edit was made. A doc edit that makes a stale claim TRUE and one
  that makes a true claim CONVENIENT produce the same diff, and telling them apart needs state
  across two commit attempts — i.e. a write on the commit path, which D18 forbids.
  Nearest partial: The buildable half is narrower and worth taking: a row that reads
  scripts/docs-audit.py's own AST and fails on any write call (open mode w/a/x, write_text,
  os.replace, shutil) reachable outside --self-test, and on any argparse flag named
  fix/write/apply/repair. D16's "a --fix flag is a change to this entry" currently rests on
  nobody having added one.

- **A wrap-up does not restate the task or summarise the request.**
  A machine would need: That a sentence adds nothing the user did not already supply. The repo
  has already ruled on this bar, at scripts/docs-audit.py:1176: a claim is policeable only when
  it self-identifies AND its ground truth is a machine-readable assignment in the same tree —
  "where that bar is not met, the answer is to delete the restatement rather than widen this
  check to chase it." A restatement has neither property, and any n-gram-overlap detector fires
  on the correct case (a wrap-up about the emit cap must say "emit" and "cap").

- **A citation must name the section it is ABOUT, not merely a section that exists.**
  A machine would need: What a sentence is about. Measured, not argued: over all 38 DEBTS
  citations in the tree the attributed-form proxy scored ONE catch against THREE false alarms,
  and the most-repeated distinctive token (`one-in-thirteen`, which the file spells `1 in 13` in
  a table cell) fails containment against the CORRECT section — so the naive rule flags the
  repaired text too. A row wrong three times for every time it is right is one the next session
  turns off. A hand-maintained (phrase → section) table is itself a claim with an unread reader,
  which is the defect §4 is about.
  Nearest partial: Canonicalise the SPELLING so the population is findable by one pattern — the
  failure that produced three different wrong totals for one search. That is mechanical and is
  the half worth building.

- **Keep the product to modern era (SWSH/SV), English and Near Mint; vintage is a spec change, not a parameter.**
  A machine would need: Which era is in scope — which the entry itself records as unsettled and
  the owner's call. An era allow-list built today would refuse the only era this project has
  ever run 53 real cards through end to end (ME01 Mega Evolution, Gate B, 2026-08-22, which
  raised no scope question at any stage) and would refuse riftbound and one_piece outright. This
  is a dead rule that should be answered or declared dead, not mechanised.
  Nearest partial: The condition half is already structural: pipeline/variant.py:76's
  CONDITION_BY_FINISH hardcodes the Near Mint strings, and D137's Near Mint rule lives in the
  catalog join with a T3 guard against two wide fixtures.

- **A sale case that mutates its stub store after a press must declare that it requires the re-read to disagree with the overlay.**
  A machine would need: Which assertions in a spec are about the OPTIMISTIC OVERLAY and which
  are about the server's answer — the difference between a case the click-then-mutate race can
  corrupt and one it cannot, which is invisible in the syntax both share. Measured: of seven
  probed cases, 3 were red on demand and 4 were GREEN ON PURPOSE, because `doSell` adds the copy
  to `sold` before it bumps `reloads`, so the receipt, the Undo, the state pill and the wire log
  are answered by the overlay whatever the re-read says. Freezing the racy form would silently
  degrade those four.
  Nearest partial: It becomes decidable once the contract is DECLARED rather than inferred — a
  named helper stating "this case requires the re-read to disagree with the overlay", never a
  copyable skipMutationCheck flag. Then an eslint rule can refuse a bare `cards[...] =` after a
  `click()` in an undeclared case. DEBT23 is the entry; the declaration is the work.

- **A change the browser suite depends on must run the browser matrix — including a path the suite composes at runtime.**
  A machine would need: A path built from pieces, or a Vite `server.fs.allow` widening spelled
  through a variable. The honest reader for the first is the suite run under a file-access trace
  (a browser on the commit path); for the second it is a config evaluator (node on the commit
  path). Both are what `make check` is deliberately built not to need, and `route rosters` and
  `storage keys` carry the same literal-only ceiling for the same reason.
  Nearest partial: `browser scope` is mechanical, bidirectional, refuses an empty dependency
  set, and both gates now skip only on their own explicit answer — a broken lookup, a broken
  classifier, a job that never ran and an empty output all RUN. The residue is false-negative
  only.

- **A figure on screen describes the work in front of the operator.**
  A machine would need: Whether a pass is still the pass the figure describes. Closing it needs
  a clock in the client, which this repo refuses (store/orders.py records the one deliberate
  exception and argues it), or an explicit "end this pass" control nobody has asked for.
  Counting arrivals makes it a DIFFERENT figure — progress against a moving target — which is a
  design question the owner decides.
  Nearest partial: The head beside the pill is always current, which is why this is narrowness
  rather than a lie; and OrdersHubStore.walkKeys is already cleared by onFetch and onServerBoot,
  with its own vacuity guard.

- **A decision entry at twice the median length should have cited a neighbour instead of re-arguing it.**
  A machine would need: "Long because it re-derives" separated from "long because it measured a
  lot". That needs a citation-density heuristic, and D16 keeps a heuristic off a blocking row.
  All ten entries standing over the budget today were read entry by entry and none is over for
  the reason the row exists to catch.
  Nearest partial: The honest alternative is a DECLARATION rather than a check — a ruling that
  some entries may be long, said in the entry's own first line — the same declared-intent move
  DEBTS §23 and §17 both land on.

- **Before you hand the owner a task, check whether it is yours to do.**
  A machine would need: Whether a step needs the owner's BODY (at the rig, at the shelf, in a
  signed-in browser) or their JUDGEMENT — and then whether any of 73 routes, 9 subcommands or
  ~60 make targets performs the named action. Nothing in the tree declares which capabilities
  require a human presence, and the capability index is prose: docs/map.py says what each module
  IS, never what a person could ask it to do. So a guard can only ever say "this thing exists",
  never "therefore you should have done it".
  Nearest partial: None worth building — every legitimate ask fires a phrase matcher, and the
  roster it would print does not answer the question that earned the rule (the live-export
  fetch).

- **A compaction preserves the fixture schema facts, every make command, and the list of modified files.**
  A machine would need: The summary, and whether it kept them. A compaction leaves no artifact
  in the tree and none in the transcript, so this is the one rule whose violations are invisible
  to both the repo AND the transcript scan that measured every other behavioural rule.
  Nearest partial: A PreCompact hook could guarantee the facts are PRESENT at the moment of
  compaction without verifying the summary — but it is rejected above on D135 grounds (whether
  Codex has that event is unanswerable from this tree, and `codex hooks` compares the full
  triple in both directions).

- **A control must be on the screen a human would look for it on.**
  A machine would need: Where a person would look, and whether the control is behind a collapsed
  panel, in a modal nobody opens, or on the wrong screen. D20's own defect is the proof: route,
  client and control were all present and 12 of 13 boxes were unselectable. That judgement needs
  `make design-check`, which is deliberately off the commit path and whose flake rate (1 in 13
  on CI) would teach --admin if it gated.
  Nearest partial: The first two links are fully mechanical and cheap — build_now rank 39. The
  third is per-capability Playwright work, one assertion at a time, and should be written as
  cases rather than as a sweep.

- **Whether an entry's argument still holds — has the premise gone, and does anything still protect what it was protecting.**
  A machine would need: What an entry was protecting and whether anything still protects it: a
  judgement about purpose, which no artifact in this tree carries. D48's two dead premises were
  both DANGLING ARTIFACT CITATIONS, which is the checkable shadow of the rule — but the rule
  itself is about an argument outliving its reason.
  Nearest partial: Requiring a REOPENING CONDITION on a newly added entry only, git-diff-scoped
  the way `evidence freshness` is staged-only — 87 of 173 entries already declare one, so
  scoping to new entries avoids an 86-finding baseline. That makes the argument's own expiry
  condition explicit without asking a machine to evaluate it.

- **Whether a new mechanism's baseline is still the baseline it was measured against.**
  A machine would need: Nothing unseeable — this is a GAP rather than an impossibility, and it
  is named here because half of build_now rests on a one-commit measurement stated in prose (73
  routes, 0 unreached; 266 entries, 0 ungoverned; 8 manifest lines, all with selectors). Once
  built, each row prints ok whether the population is still what was measured or the walk has
  stopped finding it. The repo already owns the answer and applies it in exactly one place: T1's
  three fingerprints (prompt, eval set, and a hash over the SCORER's own function sources) fall
  THROUGH to a re-measurement on a mismatch rather than passing on a stale number, and the third
  exists precisely because an edited scorer would have left the committed figure green with
  nothing to notice.
  Nearest partial: Apply that pattern to a guard's own baseline: a row justified by a
  measurement carries the digest of what it measured, so "still zero" and "the walk found
  nothing to check" become different words. This is the single highest-leverage thing NOT in
  build_now, because it is what keeps build_now true a month from now. It is folded into
  build_now rank 21's floor requirement in its weakest form (a count and a floor); the
  fingerprint form is the strong one.

## Proposals the audit REJECTED, and why

Kept so nobody re-proposes them. A rejected mechanism is usually one that would fire on honest
work, one that could not fail, or one that would have a gate write to the tree (D18).

- **Stop hook blocking a turn whose final text claims the harness is green when no harness run happened in this session** — SELF-REFUTING. scripts/stop-gate.sh:69 runs `make harness` unconditionally whenever the gate is armed, BEFORE anything else in the hook can execute — so a claim check bolted on runs after that run and would block a claim its own gate had just made true. The 41 measured no-run claims are coordinator turns relaying a fleet member's run, and this project's fleets are separate SESSIONS (0 of 129,119 messages carry isSidechain), each with its own armed gate, so a coordinator can never comply. The proposal's own pin list requires that a turn relaying CI or quoting a past run must PASS, which is the same population. Cost of the rule being unenforced: a session is occasionally accidentally right. Cost of the guard: PKMNSCAN_GATE=off in a shell profile, which disarms the real harness gate. KEEP ONLY the trivial sibling — print the harness summary line (with a run id) to stderr on success, which the gate already holds and throws away; that makes the claim checkable by a reader and refuses nothing.
- **Stop hook requiring a render newer than the turn's app/src writes plus a Read of that PNG** — Three unboundable false-positive families, an inverted escape, and it would LAUNDER a wrong image. Most app/src writes carry no appearance claim (types.ts, server.ts, standing.ts, a comment edit, a revert); a turn that ran the Playwright suite has stronger evidence and would still be refused; and the escape — pass when nothing listens on the dev port — inverts where it matters, because on the MAIN checkout a server IS listening, so the gate would demand a render against the owner's live app over their real store. The evidence is also unobtainable through the repo's own tool: scripts/screenshot.sh:35 hard-codes VIEWPORT=1280,900 and screenshot.mjs has no theme flag, so the three widths and two themes the rule names have never been renderable. And with views.txt's `capture` line pointing at `#/`, a satisfied gate would certify that a session opened the HOME screen as verification of the capture screen. Fix the manifest (build_now rank 3) instead of policing the session.
- **Stop hook requiring one of BUILT / RECORDED / NEITHER / SPECIFIED / VALIDATED in a wrap-up** — 84% of measured wrap-ups would fire (1,943 of 2,310), and the proposal concedes the escape is typing the word. That is actively harmful, not weakly useful: it trains sessions to paste a boilerplate bucket block, which makes a WRONG bucket harder to spot and turns CLAUDE.md:1544's corollary unfalsifiable. A per-turn exit 2 on the majority of write turns is precisely the rate docs-audit.py:1367 says teaches a reader to skip exit 2 — and in the git hook the same reflex takes the three opsec rules down with it. Build the two rows that make a BUILT claim checkable (build_now ranks 2 and 39); an unchecked vocabulary word is worth less than silence.
- **Stop hook comparing files named in a wrap-up against the turn's own write targets** — Unmeasured, and its own author said so: "Not measured — I will not assert a number I did not compute." A mechanism whose proposer could not find an instance, for a rule whose violation costs a reader one `git status`.
- **A PreCompact hook injecting the fixture facts, make targets and modified-file list** — broken is unobservable by construction — a compaction leaves no artifact in the tree AND none in the transcript, so no instance has ever been or can be seen. And it collides with the one roster reconciliation that has never been bypassed: D135's `codex hooks` row compares the full event/matcher/command triple in both directions, and whether Codex has a PreCompact event is not answerable from this tree.
- **Registering scripts/stop-gate.sh on SubagentStop** — Measured at 0 of 129,119 assistant messages carrying isSidechain — the path is unexercised. And the arm has a harm of its own: the gate runs the full nine-test harness, so arming it on subagents spends the owner's CPU at every read-only research turn on the machine their rig and live capture server run on — the collapse §11 measured. Cheap and pointed at nothing.
- **A WARN-only Stop hook matching delegation phrases and printing the route / CLI / make-target rosters** — Every legitimate ask fires it — at the rig, at the shelf, money, a signed-in browser, a decision that is the owner's — so it prints on the common CORRECT case, which is the permanently-lit advisory again, bought at the price of the first transcript-reading hook in the tree. And what it prints is not a capability index: 73 route paths, 9 subcommands and ~60 make targets do not answer "can you fetch a fresh My Pricing export", the sentence that earned the rule. The capability index is prose; leave the rule prose too.
- **A pre-commit rule requiring a staged docs/DEBTS.md change when the commit message says bandaid / workaround / stopgap / for now** — Two fatal problems. The subject is a word the author chooses, so it taxes the HONEST bandaid and cannot touch the disguised one. And it induces the exact editing behaviour D16 forbids by name: a gate cleared by staging a markdown change teaches sessions to edit a document to unblock a commit. A rule against bandaids enforced by a bandaid, on the commit path, where a false alarm buys --no-verify and takes the opsec rules with it.
- **Banning `api.pokemontcg.io` and TCGplayer Scan & Identify from the product packages** — Both measured clean with zero instances ever, by two readers independently; the only hits are the sanctioned benchmarks in harness/ that each entry explicitly permits. D15 and D2 are architecture statements, not rules under pressure. Two more rows nobody will ever see fire, in a file whose 79 rows a session already scrolls past.
- **A pre-commit PII ratchet over added lines (emails, address headers, tracking numbers)** — Never measured — marked unknowable, and the strongest thing said for it is that the material exists. Against that, the downside IS measured: scripts/guard-opsec.sh was switched off on 2026-08-03 for two blocked writes in one session, and a pre-commit false alarm buys --no-verify, which disarms the image rule and the printed-code-layout rule in the same hook. A speculative pattern there risks the two rules in this repo that guard a bearer instrument.
- **A +make icloud-selftest proving the sweep deletes only byte-identical conflict copies** — Zero incidents in the tool's whole life, and the hazard class can no longer occur: the checkout moved to ~/Developer/pkmnscan on 2026-08-29 and the iCloud originals were deleted — the owner's own memory says "hazards retired, guards kept". iCloud conflict copies are produced by iCloud Drive; a tree outside it produces none. The argument offered was symmetry with `make reap` and `make janitor`, and both of those earned their arms from measured incidents. Symmetry is not evidence. (If the tree ever returns to iCloud, this is the first thing to build.)
- **Refusing `git add -A` / `git add --all`** — It is a correct everyday command, and the incident it is aimed at had a different cause — a bare `ln -s` into an existing path nested a second `images` link inside `harness/images`, and the staging command merely carried the result. The existence test on `ln -s` (build_now rank 12) catches it AT the cause, and pre-commit independently refuses a staged symlink by index mode 120000. A refusal on a command typed several times a day is the clause most likely to put the whole hook's hatch in a shell profile.
- **A PreToolUse Bash hook refusing a bare `gh pr merge` unless an env marker from scripts/merge-pr.py is present** — The proposed door is not the door that failed, and the refusal fires hardest where it is least justified. All six measured incidents — two unclaimed ids, three merges over in-progress checks, one merge run from main — went through `make merge` from the wrong TREE; the hand-typed bypass is untested. Meanwhile D151 measured 24 of 30 worktrees behind the merge surface, so the tree that most needs to land work by hand is the tree whose wrapper is stale, and there the guard refuses the only available path — the highest-consequence refusal on the board. CLAUDE.md also keeps the raw commands written out "on purpose" so the wrapper never becomes the only thing anybody knows; a hook forbidding them repeals that decision as a side effect. Guard the SURFACE instead: build_now rank 28.
- **A `governed_by` non-empty branch in check_map** — Presented as free (266 of 266 green) and the cost is not a blocked commit — it is a corrupted field. The requirement is satisfied by any D number that resolves, so during an ordinary file split the cheapest compliance is pasting the nearest plausible one; and `governed_by` is the field scripts/decision-context.py reads to tell the NEXT session what governs the file they are editing, plus the field `tested_by reach` and `decision ids in code` key on. Nothing downstream can tell a real citation from a plausible one. Second, the effective field INHERITS from the component, so the case the rule exists for — a new file under an existing package — arrives already governed and the row can never fire on it. If taken at all: accept `governed_by: []` WITH a `why` string and fail only an entry that has neither, so the visible act is an honest declaration rather than a misdirecting citation.
- **A `sole writer` row counting import-CSV writers and refusing any count but one** — A count of one is preserved by substitution — delete pipeline/join.py:emit_import and add a writer that never raises OutputSuppressed and the row is still green with the rule gone. It also says nothing about the PROPERTY (both directions reported before a byte is written), and its key is a filename heuristic, so a writer whose destination is computed is outside the denominator. Rework: pin the ROSTER of modules that write an import file and require each to raise OutputSuppressed, folded into the existing `sole reader` row, which already holds a counted-sentence claim of this shape.
- **An `arm census` row reconciling published "N arms" sentences against len(ARMS)** — An arm COUNT cannot see a DEAD arm, and a dead arm is the failure measured three times here: T7's zombie-pid arm survived because the fixture handed itself the handle, so the arm deleting the entire defect stayed green; D167 names a surviving arm today; DEBTS §11 carried a sentence about two observed mutation failures that were false on both counts. A row proving the number matches is satisfied while every arm has stopped killing. Rework: count KILLS — the selftest declares its arms as data, RUNS each one (apply, require failure, restore from a .bak copy, never `git checkout <path>`), and publishes the kill count, which the doc sentence then reconciles against. It writes, so `make check` and never the git hook. And every declared arm list must carry at least one `allow:` arm — a named case proving honest work passes — because the allow arm is the one that actually costs this repo time (reap-selftest's own-process arm went red four times against an unmodified reap.py, and guard-opsec was switched off wholesale for refusing two honest writes).
- **A `route reach` row requiring every route A DOC ASSERTS AS BUILT to have a client function** — The trigger is prose, so the guard is cleared by silence — and silence is the measured incident. On 2026-08-23 the box delete, the mid-box delete-with-reindex and the retroactive box claims shipped with full T7 coverage and zero client functions, and NO document claimed any of them BUILT. The mechanism's subject is a sentence somebody wrote; the defect's subject is a route somebody shipped. It would have been green through the founding incident. Use the unconditional route floor: build_now rank 39.
- **A `flag citations` row refusing present-tense claims about a `--flag` no argparse accepts** — The measured baseline is 1, not 2, and the row's first run would demand an edit to the file the repo most explicitly protects from edits. `docs/gates/gate-runs/GateB-note1-box-2-544-cards-and-the-first-ground-truth-about-finish.md:37` ("The remedy the owner chose, the same day: `join --bypass`") is a record of a ruling the owner made on 2026-08-24, inside the file CLAUDE.md declares is "a record of runs, not a schedule" whose numbers "are evidence and are never rewritten to match a later tree." A session obeying the row commits the D16 violation to satisfy a checker. If taken: scope to CLAUDE.md, README.md, docs/specs/ and docs/decisions/, exempt docs/GATES.md by name (as `decision structure` already exempts its gate sections), and fix the one genuinely stale sentence (docs/specs/ui-redesign-options.md:629) by hand.
- **A `debts citations` row asserting every `docs/DEBTS.md §N` reference names a section that exists** — Measured at 55 citations, 0 unresolvable — and the proposal concedes it "would NOT have caught the §11/§8 defect: both sections exist." So the mechanism does not address the harm that cost three sessions three different wrong totals. §25 already measured the subject-matching proxy at 1 catch against 3 false alarms and declined it. Build the half with the cost behind it: CANONICALISE the spelling. A citation is written three ways (`§11`, `section 11`, and either hidden behind a backticked filename), which is why three sweeps for one population returned 5, then 7, then 9. One spelling makes the population findable by one pattern.
- **A coverage table requiring every server write in app/src to have a rect-diff press case (D118 universality)** — The largest cost in the audit against its smallest harm unit: 98px of collapse and 131 elements moved on one `Mark sold` is a cosmetic jolt, not a card, a dollar or an hour, and the rule's own entry records the owner asking for it by feel. Enumerating 96 write call sites needs a marker-exemption list (undo removing a filmstrip frame, a box delete emptying the walk) which is where a coverage table starts being maintained by hand. Build the one press the entry itself names as unguarded — the wanted-claim line's 46px move — as a fifth case in inventory.spec.ts beside the three that exist.
- **Branding `Slot` and `Index` as nominal types so tsc refuses the swap** — Forty call sites across the wire contract, and D92 declined it on a blast radius it measured. The re-weighting argument ("there is a shipped defect now") is fair but the defect is a misleading LABEL: the undo press is aimed by `capture_id` (D145/D153), not by the drawn number, so the worst case is a human misreading a row, not a write landing on the wrong card. Take the cheap arm instead — sigil-check follows one same-file helper, which is exactly what `slotNumber` was. Build_now rank 34.
- **Deriving `recorded deletions`' needle table by harvesting backticked symbols from deletion sentences** — D149's declined class, measured there: the attributed-form proxy scored 1 catch against 3 false alarms over 38 citations and the containment cousin produced 79 coincidences on this history. The needles here are ordinary words — Position, label, live, staged, bid — and a deliberate reuse is an expensive false positive no wording rule resolves: D113 rebuilt `POST /orders/fill` and `do_order_fill` under the same names for a different purpose, so the derived row would refuse a correct tree and send a session to amend a sentence about a different feature. Nobody has dry-run it over 169 entries. Take arm (a) — the scope widening — alone.
- **An import-edge scan proving the undo / spend client is imported only by named modules (D19, D39)** — The guard's subject is orthogonal to the rule's. The rule is about whether a human event precedes the call; an import-edge scan answers which module imports the function and is green either way. A `setInterval(() => undoCapture(top))` inside the very component that draws the undo control passes, and so does a callback drilled down as a prop; the spend variant additionally goes blind to a barrel re-export, which the proposal concedes. Rework: an eslint no-restricted-syntax selector refusing the undo (or spend) client inside a setInterval/setTimeout callback, inside an effect whose dependency chain contains no user event, and inside the trigger modules by name — the same family as D128's keydown selector.
- **An `advisory roster` row freezing the set of ADVISORY labels** — Green today and changes nothing about what is broken: 23 standing findings teach sessions that exit 2 means nothing, and freezing the LABEL set prevents a new advisory row while leaving the standing state intact. It is also the wrong shape for the silent direction — a MECHANICAL row demoted to advisory changes one keyword and grows the advisory label roster by one, which the frozen literal is edited to accept in the same commit. Adopt the per-FINDING pin (build_now rank 25); let a label freeze ride on top once the tree is at zero.
- **Promoting `breakpoint columns` and `entry budget` to MECHANICAL** — The severity promotion's first act is to refuse two correct things. Blocking on `entry budget` refuses a commit for writing a long decision entry, which D60 rules is a report and not a gate and which a read of all ten oversized entries found innocent. Blocking on `breakpoint columns` refuses correct CSS: RunPanel.css:55 sets `max-height: calc(100vh - …)`, which no container query can answer, and converting it would make the element a containing block for position:fixed descendants (Review and Inventory must never become containers). The argued exceptions then need a dial, which D133 already ruled gets turned until the gate is quiet.
- **A `width coverage` row asserting the VISIT of each route at 390 and in dark** — "Assert the visit" is satisfiable by a `page.goto` at 390 with no assertion whose subject is on screen — the most-measured failure class in this tree, written into its own memory: phone.spec.ts went green four times before it was worth anything (the fixture never drew the ship bar; the sweep only measured the fold; a modal scrim covered every probe; the fixture was too small to fail). Rework: credit a route at a width only where a spec makes at least one assertion against an element it has PROVED is rendered at that width, publish the per-route SUBJECT count with a floor, and reuse phone.spec.ts's existing hit-area sweep as the 390 proof.
- **A ruff/AST ban on `input()`, getpass, webbrowser.open and stdin reads in the mapped packages** — Zero findings over 64 files with zero exemptions and no instance in the repo's history — an empty subject being read as strength. It is also self-defusing: every confirmation in this product is a `--confirm` FLAG (make down, make reap, make merge, prices adopt), so a session reaching for a prompt would be inventing a convention the tree does not have. And the rule's actual shape — a pipeline step needing a human inside somebody else's UI — is a judgement the ban cannot make; the tree carries one legally today (the operator uploads reprice's import.csv through My Pricing). If taken at all, take it as one line in the existing ruff.toml slice and describe it honestly as "no module in the mapped packages blocks on stdin" — which pre-commit independently needs, since a hook run from an agent session has no tty — not as enforcement of the rule.
- **The waiter-loop hook's second clause (refuse launching a script that already has a live process under this checkout)** — Its resolver is the machine-wide pgrep that has already reddened `make reap-selftest` four times against a reap.py byte-identical to main, and D157's whole ruling is that a per-run subject must be made unable to COLLIDE rather than made to take turns. Two legitimate concurrent copies of a per-worktree script, or a deliberate second instance on a different port, are both refused — and the refusal lands on the session's own launch, the one thing it cannot work around except by the hatch. Ship clause (a) alone: build_now rank 19.
- **Refusing `open` / `osascript … activate` outright in the GUI clause** — It kills the common legitimate case of showing the owner a file they just asked for, and the act of typing the hatch would be the announcement the rule wants anyway. Keep `screencapture` as a refusal and the Chrome-profile test (a browser launch lacking BOTH --headless and a scratchpad --user-data-dir) as a refusal; demote `open`/`osascript` to a printed note.
- **A `gh pr comment` clause refusing a comment when a live session holds the PR's head branch** — It rests on a branch→worktree→pid mapping that has ALREADY been measured wrong — two trees switched branches while they were being measured on 2026-09-06, which is why janitor reads session records rather than mtimes — and the harm it prevents is "a PR comment instead of a direct message", trivial against a refusal that could block a legitimate note to the owner (D-number merge-order statements are made in PR comments on purpose). Demote to a printed note naming the live session.
- **A `seam list` row that treats a computed write path as unknown rather than as a violation** — The escape is a silent fail-open over the exact shape that hides — a generator writing through `path.join(outDir, name)` is invisible and the row reports ok. It also has no denominator: a walk enumerating no scripts renders as a clean seam list. Rework both: make the unresolvable case a FINDING in its own words, and publish the enumerated count with a floor. Build_now rank 38 carries the reworked form.
- **Classifying the opsec rule as "already built — nothing to add"** — Nothing proves either tier still bites. githooks-selftest's 21 cases never stage an image outside captures/ or a code literal; guard-opsec.sh has no self-test, no make target and zero arms — while `make reap-selftest` has thirteen. This is the guard with a recorded history of being switched OFF for over-firing and then narrowed by three clauses nothing re-checks, and a narrowing is exactly the change that can go one clause too far and stay green. Build_now rank 24.

## What this audit did not reach

WHAT I VERIFIED MYSELF, in /Users/shivinate/Developer/pkmnscan at main (the audit's own worktree
is at ac2e382/df6ec79; I read the main checkout read-only): cli/cmd_identify.py contains ZERO
occurrences of `pid` while `running.pid` is written only at server/pipeline_routes.py:1474;
`--self-test` for screen-freshness appears in no Makefile recipe, no hook roster and no workflow
(checks.py:177 carries the bare command); check_criteria_evidence's substring test and silent
`continue` at docs-audit.py:1329-1344; scripts/views.txt's eight lines with `capture` pointing
at `#/` and views.txt:108-120 recording the DELIBERATE removal of the `#/inventory` line on
2026-09-05; Report.render's unconditional `ok` for an empty findings list (docs-audit.py:173);
.claude/settings.json's deny list is exactly three entries and `.env` is guarded only against
the Read tool; `_ESTIMATE` at pipeline_routes.py:344 against cmd_identify.py:772 with ZERO
references in docs-audit.py; the `check:` recipe's 23 fail-fast lines and both published lists
in the pre-D161 order; ADD_TO_QUANTITY's two call sites; harness/run.py's docstring saying eight
three times against nine in TESTS; `grep -c ci-check scripts/docs-audit.py` = 0; guard-opsec.sh
has zero self-test occurrences and no make-target caller; a live `python3 scripts/docs-audit.py
--json` returning 79 rows, exit 2, 23 advisory findings across four rows; `moveCard` uncalled
while `moveCards` is called from BoxOps.tsx:27/:453; detect.json's `declined: 59` as an integer
with no filenames anywhere; policy.live_cap refused by name at corpus.py:228 with no
policy.floor equivalent; both PW_ARGS expansions unquoted at Makefile:859 and :875; stop-gate.sh
registered in both rosters with `--status` called by nothing. TWO SURFACE/CRITIQUE CLAIMS I
CORRECTED RATHER THAN PASSED THROUGH. (1) Two critiques and one surface reader assert that `make
check`'s standing reap-selftest red leaves lint, vale, typecheck and eight more targets unrun.
FALSE as of a6287cb (D161): the recipe now runs lint at slot 10, vale 11, typecheck 12, and
reap-selftest at 20, so the current blast radius is THREE targets (suite-lock-selftest, serve-selftest
, verdict-selftest), not eleven. The eleven-target measurement is from the pre-reorder
tree. (2) The flagship call-site finding is a DEAD EXPORT, not an unreachable capability:
`moveCards` is wired to the Manage box sheet with `indices: null` meaning every on-hand card, so
D83's move IS reachable and the finding resolves by deleting eleven lines. Both corrections
change a rank. WHAT I DID NOT RUN. I never ran `make check`, `make harness`, `make design-check
`, `make screenshot` or any selftest — this audit is read-only and two of those spend the
owner's CPU on the machine their rig and live capture server run on. So the standing `reap-selftest
` red on origin/main is a MEMORY CLAIM I did not re-verify, and its slot position is the
part I did verify. I did not verify that `check` is a required GitHub status context (build_now
rank 1 and 39 lean on it); that is a surface reader's claim about branch protection, read from
the API by them and not by me. SURFACES READ BY THE TEN READERS, WITH THE HOLES NAMED. Fully
covered: CLAUDE.md's Hard rules (11 bullets), Working agreement, Commands block and "Things you
will get wrong"; all 174 files under docs/decisions/ across four quarters (D1-D169 plus 11
C-entries, with D42 double-read); docs/DEBTS.md's 23 live sections; the enforcement surface
itself (79+1 docs-audit rows, 8 hooks in each of two rosters, 5 githooks, 23 check targets
against scripts/checks.py, harness/run.py's TESTS, app/eslint.config.js's four families,
ruff.toml, check.yml's five jobs); all 70 files in the owner's memory directory; and one
transcript scan over 389 sessions / 4,553 turns / 129,119 assistant messages. NOT REACHED, with
numbers. (a) docs/GATES.md: only the three "What is open" items 9, 20 and 24 were read as a
rules surface; the whole "What shipped" list and every gate section's own prose went unread as
rules (they were read as evidence). (b) docs/specs/: nine specs (order-pipeline, stale-listings,
code-cards, motion-trigger, capture-app, batch-script, one-process, logo, DESIGN) were read
INCIDENTALLY where a decision cited them, never swept as a rules surface of their own — and
docs/DESIGN.md in particular holds the Fulfilment constraints table and a token block that two
rows already read, so there is probably more there. (c) CLAUDE.md's first ~1,090 lines — the
name section, the front end, the twelve screens, the design system, the shell, "Verifying a
screen" — were read as CONTEXT by every reader and as a RULES SURFACE by none; the design-system
paragraphs alone carry at least four imperative rules (never a border-radius on the mark, reach
for the kit before a primitive, a component's transition REPLACES the floor's, background-image
is not animatable) of which only the first is in this list. (d) code-card-fork/CLAUDE.md:
entirely unread — a separate track with its own schema and channel. (e) The nine harness
modules' PASS_CRITERIA strings as a rules surface: read only where a decision cited one. (f)
app/tests/'s 24 specs: sampled, never enumerated. (g) .github/workflows beyond check.yml
(demo.yml is cited once and unread). (h) The skills (tcgplayer-csv, docs-audit) carry schema
rules by CLAUDE.md's own pointer and were not opened. CAPS AND TRUNCATIONS TO STATE PLAINLY. The
transcript evidence rests on ONE reader's scan; I did not re-derive its populations (41 of 459
harness claims, 1,943 of 2,310 wrap-ups, 1,363 Bash writes to governed paths, 47 of 79 app/src
turns), and three of the four proposals built on it are rejected above, so little of build_now
depends on it. Two proposals were declined for want of a dry run nobody performed — the derived
deletion-needle table over 169 entries, and the "watched counts" row over every published
integer — and I have not estimated their false-alarm rates either. One roster question is
unanswerable from this tree and blocks one rejected item: whether Codex exposes a PreCompact
event. No reader measured how many entries `governed_by`'s reciprocal direction would fail today
(D60's first limit), which is why that row stays in `rejected` rather than `build_now`. And
nobody dry-ran the Bash write-target resolver that build_now ranks 9-12 and 26 all share: its
parse coverage over real session commands is unmeasured, which is why every clause is specified
to fail OPEN and why a "guard throws" arm belongs in its self-test.
