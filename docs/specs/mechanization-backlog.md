# The mechanization backlog

This file is the shelf of mechanisms that a 14-agent audit designed and costed and that were not
built. It exists so a later pass starts from the measurements and does not re-derive them.

**Read D173 first.** Its rule is that a rule which can be mechanically enforced must be. A new rule
is not finished until its enforcement exists or its unenforceability is argued. A `NOT MECHANIZED:`
sentinel in CLAUDE.md's Hard rules names what a machine would have to see. An entry here names a
mechanism somebody has already designed.

The audit ranked each proposal by (times the rule has been broken) x (how cheap the mechanism is),
and not by how important the rule sounds. It rejected 32 proposals outright. Every figure below was
read from the tree by an agent that did not implement it. Verify before you build, and see the last
section for what the audit did not reach.

## How this file spells things that do not exist yet

A `+` in front of a path, a `make` target or a `PKMNSCAN_` name means the thing does not exist yet:
`+make opsec-selftest`, `+PKMNSCAN_PWARGS`. Three mechanical `make docs-audit` rows that verify a
named thing is real read the sigil. So this file can name what it would create without failing a
commit on every line.

The sigil is self-cleaning. Each of those rows fails when a marked name exists, so the `+` comes off
in the PR that builds the thing. An allowlist line would also work. But it puts the name's status two directories from the sentence that uses it. It is also a roster that every branch edits.
`scripts/docs-audit-allow.txt` keeps its own job: a path meant to stay unresolvable forever.

## Status of the 21 mechanisms

The ranks are stable ids. They are not renumbered, so a citation of a rank keeps resolving.

| Rank | Rule | Status |
|---|---|---|
| 18 | A filtered suite run must have exercised the tests it named. | Shelved |
| 19 | Never write a waiter loop over a pattern. | Built: `scripts/guard-shell.py`'s `wait` clause (`PKMNSCAN_WAIT`) |
| 21 | A row that examined an empty subject must not print the same word as one that examined everything. | Partly built |
| 22 | `make check` reports the state of every target. | Shelved |
| 23 | A claim a debt entry makes about a file's shape is true of that file. | Shelved |
| 24 | A guard must be proved to fail by a planted defect, starting with the bearer-instrument guard. | Shelved |
| 25 | Exit 2 means a new question and not a state of the world. | Shelved |
| 26 | A read of the API key is screened whichever tool performs it. | Shelved in this repo |
| 28 | Merge only from a checkout whose merge surface is current. | Built, then retired: the shared merge tool updates itself before every merge |
| 29 | A Playwright fleet takes the machine-wide suite lock. | Shelved |
| 30 | `ADD_TO_QUANTITY` stays a bare constant on the reprice path. | Shelved |
| 31 | Two identify batches may not run over one box. | Shelved |
| 32 | Realign a run's records before anything reads a position. | Shelved |
| 33 | A copy is never offered to TCGplayer twice. | Shelved |
| 34 | A bare `#` on an owner-side screen is a count and never the stored index. | Shelved |
| 35 | A spec's standing is declared in the spec. | Cut: the `work item standing` row was removed |
| 36 | Never lower a Fulfillment floor. | Shelved |
| 37 | Never narrow the rarity-to-finish matrix to what one export proves. | Shelved |
| 38 | Never add a generation seam without amending D18's named list. | Shelved |
| 39 | Every server route is reachable from `app/src/server.ts`. | Shelved |
| 40 | Register a window keydown listener in `useLayoutEffect` when its dependencies name state the handler reads. | Shelved |

"Shelved" means the mechanism's named artifact is not in the tree. Each was checked by name and by the
recipe or function it would change. Rank 32, rank 33 and rank 37 are shelved on a weaker basis. No artifact with the named shape exists. I did not read every candidate site.

**Rank 21, partly built.** `Report.add` takes `scanned`, and `render` prints `none` for a row that
examined nothing. `as_json` carries `scanned` and a `vacuous` flag. Whether every absence-row passes
its denominator, whether the `check dispatch` row requires it, and whether a per-row floor exists is
unknown.

**Rank 28, built.** The shared merge tool fetches its own latest code before every merge, so no checkout merges with a stale copy.

## The shelved mechanisms

### Rank 18 — A filtered suite run must have exercised the tests it named.

**Cost:** small.

**Mechanism.** Two halves, and the second is the rule.

- (a) A check at the top of the `design-check` and `design-check-quiet` recipes: `python3 +scripts/pw-args.py check -- $(PW_ARGS)`. It splits the value the way make will. It refuses any bare positional token that
  does not name an existing file under `app/tests/`. Flag-prefixed tokens pass.
- (b) Count the work. When `PW_ARGS` names spec files, the recipe compares `.serve/design-check.json`'s
  `counts.total` against `grep -c '^test('` over the named specs. It prints a loud disagreement line.
  An outcome assertion cannot see tests that never ran. Only counting them can.

**Where.** The `design-check` and `design-check-quiet` recipes in the Makefile. Both expand
`$(PW_ARGS)` unquoted, which is the mechanism of the bug. Half (b) rides the verdict file that the
`verdict file` row and `make verdict-selftest` already guard.

**Catches.** A false green over zero of the target cases. `PW_ARGS='--grep "the release sends
confirm"'` word-splits. Playwright reads the stray words as path regexes and reports a pass having
exercised none of the target cases.

**Keeps passing.** `PW_ARGS=tests/brand.spec.ts`, CI's shard pair (`--shard=1/3 --workers=1`) and
`--grep=the.press.that.sells` (dots for spaces).

**Mutation arm.** `PW_ARGS='--grep "two words"'` must refuse. `PW_ARGS=tests/brand.spec.ts` must pass
and the count must reconcile. Half (b) prints both numbers every run, so an unreadable verdict file
is a printed disagreement and not silence.

**Escape hatch.** `+PKMNSCAN_PWARGS=off`, printed in the refusal.

### Rank 21 — A row that examined an empty subject must not print the same word as one that examined everything.

**Cost:** small. The tag is built (see above). The rest of the mechanism is:

**Mechanism.** Have every absence-row pass `scanned` (`paths`, `raw color`, `identifier spelling`,
`shell substitution`, `spec seal`, `doc hygiene` and the rows that staged mode narrows). Add an arm
to the `check dispatch` row, which already reads the auditor's own AST. It requires every check that
takes the narrowed `docs` parameter to pass a scope. Record a per-row floor in the same literal, so
"the walk found 3 files where it found 278 yesterday" is a finding. The tag stays informational: a
scope of 0 never fails, because some rows are legitimately empty. In staged mode, print which rows
were narrowed and over how many documents.

**Keeps passing.** `recorded deletions` can reach zero entries by design. The floor is declared per
row (0 permitted with a sentence). A fresh clone with no `app/node_modules` must not trip it, so count
tracked files only.

**Mutation arm.** Point `raw color`'s walk at a non-existent directory. The row must print `none` and
the floor arm must fail.

**Escape hatch.** `PKMNSCAN_DOCS=off`.

### Rank 22 — `make check` reports the state of every target, not only of the first one to fail.

**Cost:** small.

**Mechanism.** Rewrite the `check:` recipe to keep going on failure. Collect each target's status
and end with a per-target verdict table: target, pass, fail or not-run. Exit non-zero if any failed.
Do the same for `ci-check`.

**Where.** The `check:` and `ci-check:` recipes in the Makefile, with `scripts/checks.py` and
`make help` updated so the `check registry` and `check census` rows stay green. Today `check` is a
sequence of `@$(MAKE)` lines and stops at the first failure.

**Catches.** A suite that cannot tell "the rest passed" from "the rest never ran". `harness/run.py`
already writes this rule down for its own tests. A runner that stops at the first failure hides the
state of everything behind it.

**Keeps passing.** A fully green run prints the table and exits 0. Exit status stays non-zero on any
failure, or CI stops gating.

**Mutation arm.** Make an early target fail deliberately. Every later target must still run, and the
table must mark the failure.

**Not vacuous.** A target skipped for an environment reason must print `not a gate` and not `pass`.

### Rank 23 — A claim a debt entry makes about a file's shape is true of that file.

**Cost:** small.

**Mechanism.** `scripts/score-detect.py` holds the photo names in `_score`, and `_summarize` discards
them. Have it write `declined_frames: [{box, filename, area, detail}]` beside the count. Add one
claim asserting `len(declined_frames) == overall.declined`. A score file that
predates the key must read as "re-run the scan" and never as a wrong figure.

**Where.** `scripts/score-detect.py` (the writer) and a new pin. The `detector standing` row and
`_DETECT_CLAIMS` are cut, so the pin needs a new home in `scripts/docs-audit.py`, or the rank is cut.

**Catches.** A pinned figure standing beside a false claim. `harness/results/detect.json` carries
`overall.declined` and `per_box` integers and no filenames. So an eye pass over the declined frames cannot start from the file a debt entry names. That eye pass is the only thing that can settle a
false accept, which is the dangerous direction.

**Keeps passing.** A stale score file is reported as "re-run the scan" and never blocks a commit.

**Mutation arm.** Drop `declined_frames` from the writer: the row goes red. Write it with a length
that disagrees with the count: red. The pin compares a list length to the published count, so an
empty list with a non-zero count fails.

**Escape hatch.** `PKMNSCAN_DOCS=off`.

### Rank 24 — A guard must be able to fail, and be proved to fail by a planted defect — starting with the one that guards a bearer instrument.

**Cost:** small.

**Mechanism.** A `+make opsec-selftest` in a throwaway repo, on `scripts/githooks-selftest.sh`'s
model:

1. Stage a PNG outside `captures/`. Require refusal that carries the hook's own marker.
2. Stage one under `demo-assets/photos/`. Require allow.
3. Feed `scripts/guard-opsec.sh` a code-shaped literal on stdin. Require block.
4. Feed it each of the five documented false-positive shapes: the all-X layout placeholder, prose
   about the format, an alphabet walk, a phone-shaped digit run, and a window inside a longer hyphen
   chain. Require allow.

Run it in `make check` and never in the git hook, because it writes (D18).

**Where.** A new `make` target in `make check`. It needs the four-file agreement (recipe, `make help`,
CLAUDE.md's check list and `scripts/checks.py`) that the `check census` and `check registry` rows
enforce.

**Catches.** A narrowing that went one clause too far, or a refusal that stopped refusing, on the one
rule whose failure is a live unredeemed code. `guard-opsec.sh` has no self-test and no `make` caller,
and `scripts/githooks-selftest.sh` never stages an image outside `captures/` or a code literal.

**Keeps passing.** All five false-positive shapes, and `demo-assets/photos/`.

**Mutation arm.** Delete one of `guard-opsec.sh`'s three narrowing clauses: an allow case goes red.
Widen the layout pattern by one group: the allow cases go red. Delete the image rule from
`pre-commit`: case (1) goes red. Each arm asserts on the hook's own marker string and not merely on a
non-zero exit.

### Rank 25 — Exit 2 means a new question, not a state of the world.

**Cost:** small.

**Mechanism.** A tracked pin file beside `scripts/docs-audit-allow.txt` keys each standing advisory
finding to (row, where), with the sentence that justifies it. It is self-cleaning in both directions.
An unpinned advisory finding makes the run exit 2, as now. A pin whose finding has gone is stale and
fails the commit. The run's exit reflects unpinned findings only. Keep every advisory row advisory
and do not promote severity. Key the pin on (row, where) and never on the message text, or rewording
an advisory invalidates every pin at once. Print the pinned and unpinned counts.

**Where.** `scripts/docs-audit.py`: a new `advisory standing` row plus the pin file.

**Catches.** A permanently lit advisory. `check_criteria_evidence` forbids one in its own words,
because it teaches sessions to skip exit 2 everywhere. A session once pushed past stale citations
because the row was advisory.

**Mutation arm.** Introduce a new breakpoint above 1024: red (unpinned). Pin it with a reason: green.
Fix it and leave the pin: red (stale).

**Escape hatch.** `PKMNSCAN_DOCS=off`.

### Rank 26 — A read of the API key is screened whichever tool performs it.

**Cost:** small.

**Status.** `scripts/guard-shell.py` has nine clauses (checkout, tree, gh, link, wait, push, stash,
reset, narrate) and none reads `.env`. `.claude/settings.json` denies `Read(./.env)` and nothing
else screens the key.

**Mechanism.** A clause in the same Bash hook. Refuse a command whose resolved read target is `./.env`
(redirects, `cat`, `sed -n`, `head`, `grep -H`, or `python3 -c` with the literal path). Refuse a
command whose output would carry an `sk-ant-` prefix (`env | grep ANTHROPIC`, `printenv
ANTHROPIC_API_KEY`). Fail open on any command it cannot parse, because a guard that cannot determine
the answer is not evidence the command is bad. Print the sanctioned route: read `.env.example` for the
shape, and let the process load the real file itself. The refusal prints the resolved target, and the
hook prints how many read targets it resolved, so "parsed nothing" never reads as "nothing to screen".

**Catches.** The one credential that spends money, protected only by a Read-tool deny rule.

**Keeps passing.** `.env.example` in every form, `envfile.load()` from inside the product,
`ls -la .env`, and harness blocks that seal `envfile`.

**Mutation arm.** `cat .env` refuses. `cat .env.example` passes. `python3 -c 'print(open(".env").read())'`
refuses. A pipeline the parser cannot read passes, and the hook says it could not parse.

**Escape hatch.** One named hatch, printed in the refusal, in the shape of the other clauses.

### Rank 29 — A Playwright fleet takes the machine-wide suite lock before it spends the CPU.

**Cost:** small.

**Mechanism.** `scripts/suite-lock.py --hook` as a PreToolUse Bash guard on `reap.py`'s model.
Recognize a direct `playwright test` invocation with the `_FLEET_RUNNER_RE` that the `suite lock` row
already uses (one pattern, two callers). Ask the existing lock file who holds it. Refuse only when
another checkout holds it, naming that tree and printing `make design-check PW_ARGS=…` and
`PKMNSCAN_SUITE_LOCK=off`. Fail open on its own parse errors and on an unreadable lock directory.

**Where.** `scripts/suite-lock.py --hook`, registered as a PreToolUse Bash matcher in
`.claude/settings.json` and `.codex/hooks.json` (D135), with an arm in `make suite-lock-selftest`.

**Catches.** The one bypass left in the `suite lock` row: `npx playwright test` typed into a shell,
which no Makefile recipe mediates. The row reads recipe lines and `app/package.json` scripts and
cannot see a shell.

**Keeps passing.** `npx playwright install`, `--list`, `show-report`, `codegen`, and a single-spec
run while nobody holds the lock. `PKMNSCAN_LOCK_DIR` sends the self-test at a throwaway directory.

**Mutation arm.** Hold the lock from a second `PKMNSCAN_LOCK_DIR` and issue `npx playwright test`: it
must refuse and name the holder. With the lock free: pass. `--list`: pass.

### Rank 30 — `ADD_TO_QUANTITY` stays a bare module constant on the reprice path — never a parameter, never a default, never reachable from a flag.

**Cost:** small.

**Mechanism.** An AST row named `quantity constant`. Every `add_to_quantity=` keyword argument in
`pipeline/reprice.py` and `cli/cmd_reprice.py` must be the bare name `ADD_TO_QUANTITY` or
`reprice.ADD_TO_QUANTITY`. It may never be a literal, a variable or an argparse-derived value. Neither
module may declare a parameter of that name. The row must find at least the two sites that exist and
report zero as a finding. Scope it to the two reprice modules by name. `pipeline/join.py`'s
`add_to_quantity` is a different function on the emit path, where the quantity is legitimately a
variable (D7's `--quantity`).

**Where.** `scripts/docs-audit.py`: a new row. The constant is `ADD_TO_QUANTITY = 0` in
`pipeline/reprice.py`, used by `pipeline/reprice.py`'s `import_rows` and `cli/cmd_reprice.py`'s
`_write_worklist`.

**Catches.** A parameter that defaults to 0 keeps every harness assertion green while it makes the
wrong value reachable. The doubling it prevents already happened: live SKUs held more copies than
this pipeline ever pushed, from one file uploaded twice (D100). Pinning `SCOPE_THIS_UPLOAD` the same
way has no measured instance. Build it second, in the same row.

**Mutation arm.** Change `_write_worklist` to `add_to_quantity=0` (a literal): red. Add a parameter
named `add_to_quantity`: red.

**Escape hatch.** `PKMNSCAN_DOCS=off`.

### Rank 31 — Two identify batches may not run over one box, whichever door started the first one.

**Cost:** small.

**Mechanism.** Write the busy marker from the CLI too. `cli/cmd_identify.py` writes
`{run}/running.pid` with its own pid before it submits, and removes it on exit, as
`server/pipeline_routes.py`'s `_spawn` does. Add the missing T7 case. It starts a batch through the CLI seam and asserts that `POST /pipeline/identify` over that box refuses. Age-out stays as it is
(`_live_pid`'s floor is the run's own `identifications.json`), or a terminal crash locks the box
against the screen forever.

**Where.** `cli/cmd_identify.py`, and a case in `harness/tests/t7_store_and_seams.py`. Today
`cli/cmd_identify.py` never writes a pid, so `_live_pid` returns None for a CLI run and `_busy_run`
skips it.

**Catches.** A paid batch started in the terminal that the screen cannot see. A press on `#/runs` then submits a second one over the same photographs. D163's hash-before-decode makes a sequential
re-identify free, so concurrency is the only money-twice path left. No double batch is recorded as
having happened.

**Keeps passing.** A marker left by a crashed CLI run ages out through `_live_pid`'s floor. A second
batch over a different box proceeds.

**Mutation arm.** Pose a CLI-started run (marker present, pid live) and press the route: it must
refuse. Remove the marker write from `cmd_identify.py`: the case goes red. The new case starts the
batch through the CLI's own entry point and does not write the marker itself.

### Rank 32 — Realign a run's records against the photographs on disk before anything reads a position out of the payload.

**Cost:** medium.

**Mechanism.** Assert the ordering, which no existing check covers. A harness case drives the real call path, a re-join after a mid-box delete. It asserts that every position a caller reads came through `cli/resolve.py`'s `realign`. A docs-audit row covers any module under `cli/` or `server/` that reads the position keys of an identifications payload. That module must import `realign`. Or it must sit on a named list of modules that receive an already-realigned payload, with the reason beside each. The list
names the tooling that reads a payload only to report what was submitted (D33, D36).

**Where.** `harness/tests/t7_store_and_seams.py` for the call path, and a `scripts/docs-audit.py` row
for the roster.

**Catches.** A card described over its neighbor's photograph. T7 covers the outcomes (ambiguous
digest, two records on one digest, a digest-less record in a moved box, `refuse_reallocated`). "Before
anything reads a position" is a call-site convention with no reader.

**Mutation arm.** Move a `realign` call below the first position read on the re-join path: the case
goes red. Add a module that reads position keys without importing `realign` and without a roster
entry: the row names it.

**Escape hatch.** `PKMNSCAN_DOCS=off` for the roster half.

### Rank 33 — A copy is never offered to TCGplayer twice.

**Cost:** medium.

**Mechanism.** One field on `store/master.py`'s `Card`, written by `cli/cmd_emit.py`'s push loop beside
the existing `sku` stamp. It records that this physical copy reached an import file. The committed set is then read and not inferred from a reading's silence. A sale of a marked copy ages the claim on the copy's own evidence. A copy pushed before the field exists carries no marker and falls back to
`_copies_out`'s arithmetic. Otherwise the fix re-strands the copies it was built to release. Add a T7
case.

**Catches.** A doubling in the store: SKUs at `2 x pushed - sold`, from one file uploaded twice.
`staged` is written only by `pkmnscan reconcile --live`, so the store cannot tell a sold-out listing
from an import sitting in Staged. D59 named this field as its own reopening condition.

**Mutation arm.** Push a SKU, mark one copy sold, re-emit: the marked copies must not be offered
again. Delete the write from the push loop: the case goes red. The case drives the real `emit` press
and asserts on the copies in the written file. It does not write the marker itself.

### Rank 34 — A bare `#` on an owner-side screen is the count of cards in the box, never the stored index.

**Cost:** medium.

**Mechanism.** Teach `scripts/sigil-check.py` to follow one level of same-file local helper. A
`#{f(x)}` where `f` is defined in the same file and returns an expression naming `index` is a
finding. Keep the per-line `sigil-ok: <why>` escape. Do not take the nominal-type migration: branding
`Slot` and `Index` touches forty call sites, and D92 declined it.

**Where.** `scripts/sigil-check.py`, which is already in `make check` and in `scripts/githooks/pre-commit`
with its own self-test. Its docstring names the ceiling: a renamed local walks past the text match.

**Catches.** A `slotNumber` helper that returned the raw index behind a `#{}` on the row a person
presses to undo (DEBT9).

**Keeps passing.** The sites that carry `sigil-ok:` today, with the same marker escape at the helper.

**Mutation arm.** A same-file helper that returns the raw index behind a `#{}`: red. The same helper
returning `slot`: green.

**Escape hatch.** `PKMNSCAN_SIGIL=off`.

### Rank 36 — Never lower a Fulfillment floor, and keep every floor constant equal to the figure `docs/DESIGN.md`'s constraints table publishes.

**Cost:** small.

**Mechanism.** A new `fulfilment floors` row, on the `pass criteria` row's model. Lift each `| <name> |
… >= N… |` row out of the constraints table in `docs/DESIGN.md`. Require the matching `const *_FLOOR = N`
in `app/tests/fulfillment.spec.ts` to equal N. Compare on the integer and never by substring, which is
the defect `check_pass_criteria` was hardened against when 0.9 matched inside 0.95. A deliberate raise
passes by editing the table in the same commit.

**Catches.** A session lowering `BODY_FLOOR`, `PLACE_FLOOR`, `PHOTO_FLOOR` or `TARGET_FLOOR` and taking
the whole browser suite green with it. These floors serve a real second person (D31).

**Keeps passing.** The contrast row (`>= 7:1`) is not a px constant. Pin only the four numeric floors,
and report an unparseable table row as unreadable and not as a mismatch.

**Mutation arm.** Lower `PHOTO_FLOOR` to 240: the row goes red and names both sides.

**Escape hatch.** `PKMNSCAN_DOCS=off`.

### Rank 37 — Never narrow `pipeline/games.py`'s rarity-to-finish matrix to what one export proves.

**Cost:** small.

**Mechanism.** Pin the set and not its size. Keep an explicit roster of the sorted (game, rarity,
finish) triples in the audit, or a digest over them. Any removal fails. Any addition is a one-line diff
somebody has to write. Do not ship a count ratchet. A count survives substitution, which is what a
session narrowing to "what this export proves" produces: it removes uncorroborated pairs and adds the
ones it just observed.

**Where.** `scripts/docs-audit.py`: a new row beside the `matrix superset` row. That row blocks only on
a pair the matrix is missing, and `game coverage` asks about the excess and is advisory.

**Catches.** The narrowing D22 records being tempted into. `finish_by_rarity['Rare']` carries `normal`
against an SV09 export that stocks no plain-NM Rare. Removing it would make two whole Pokemon eras
unclaimable. Absence from one export proves nothing.

**Keeps passing.** Adding a new game raises the roster and is a deliberate one-line edit.

**Mutation arm.** Swap one pair for another so the pair count is unchanged: it must go red. A ratchet
cannot kill that arm.

**Escape hatch.** `PKMNSCAN_DOCS=off`.

### Rank 38 — Never add a generation seam without amending D18's named list.

**Cost:** medium.

**Mechanism.** A `seam list` row that enumerates every executable under `scripts/` whose AST writes
into a path that `git ls-files --error-unmatch` reports as tracked (`writeFileSync`, `open(..., 'w')`,
`write_text`, `os.replace`, `shutil`). It reconciles that set against the named list parsed from D18's
own entry, in both directions. The unresolvable case is a finding in its own words: "this script writes a path this row cannot read. Name it in D18's list or spell the target as a literal". Never a
silent skip, because a computed target is the shape that hides. Publish the number of scripts
enumerated, with a floor.

**Catches.** A stale rule inside the rule that governs the others. D18 says its seam list is empty,
while `scripts/build-mark.mjs` generates three tracked files (`app/src/kit/markGeometry.ts`,
`app/src/kit/markPalettes.ts`, `app/public/favicon.svg`). The `logo parity` row reconciles one of them.
`commit path` guards D18's general rule and not its list.

**Keeps passing.** A script that writes only into a gitignored or temp path (`docs-audit.py`'s
`--self-test` tmpdir, `serve.py`'s `.serve/` logs, `demo-seed.py` writing `inventory/`).

**Mutation arm.** Add a generator that writes a tracked path through a computed expression: it must be
reported and not skipped. Point the walk at an empty directory: it goes red.

**Escape hatch.** `PKMNSCAN_DOCS=off`.

### Rank 39 — Every route the server dispatches is reachable from `app/src/server.ts`, and every exported write has a call site.

**Cost:** small.

**Mechanism.** Two assertions inside `scripts/screen-freshness.mjs`, which already loads the app's
TypeScript compiler and builds the call-graph closure classifying every `server.ts` export as read or
write.

- (a) Call-site floor: every exported write has at least one call site.
- (b) Route floor: extract the server's route table by AST from `capture_server.py`'s `do_GET`,
  `do_POST`, `do_PUT` and `do_DELETE`. That means string literals compared against `path`, plus
  module-level `re.compile` constants resolved by name. Require each route to appear as a path literal
  anywhere in `server.ts`. Compare without the method, because `GET /boxes/<n>` is a deliberate 404
  explainer and `PUT /boxes/<n>` is real.

Both publish their denominator (writes classified, routes extracted) and fail below a pinned floor. A
dispatcher refactored into a table, a decorator or a dict would otherwise yield zero routes and print
`ok` over nothing.

**Where.** `scripts/screen-freshness.mjs`, which is in `make check` and `ci-check`. Not
`scripts/docs-audit.py`: the pre-commit hook runs a bare `python3`, and a regex over `server.ts` misses
routes built from nested templates and `${base}`-prefixed URLs.

**Catches.** The founding incident of CLAUDE.md's first hard rule. The box delete, the mid-box delete
with reindex and the retroactive box-level claims shipped with full T7 coverage and no client function. Harness, lint, typecheck and docs-audit were all green.

**Keeps passing.** `photoUrl()` builds an `<img src>` and never a `request()`. The download-href
builders, `reviewCatalog` (which composes its path into a local `at`), and the code-card track's
functions (excluded by banner, D14, with the skipped count printed) all stay green. So the extractor
reads all path literals.

**Mutation arm.** Export a new write with no caller: (a) goes red. Rename `path` in one dispatcher so
the extractor finds nothing: (b) goes red on the floor. The self-test's last case (`no write sites, no
findings`) asserts the opposite of the new floor, so fix it in the same commit.

### Rank 40 — Register a window keydown listener in `useLayoutEffect` whenever the effect's dependency array names state the handler reads.

**Cost:** medium. **Blocked by:** converting every offending site first, with zero inline disables.

**Mechanism.** An eslint `no-restricted-syntax` selector. A `useEffect` call whose body contains
`window.addEventListener('keydown'|'keyup', ...)` and whose second argument is a non-empty array is a
finding. The message names D128 and both fixes: move to `useLayoutEffect`, or hold the handler in a
ref and pass `[]`.

**Where.** `app/eslint.config.js`'s `no-restricted-syntax`, as a fifth `*_RULES` array beside
`FACING_MODE_RULES`, `SPLIT_COMMA_RULES`, `TWO_ARG_THEN_RULES` and `LOCAL_STORAGE_RULES`. Re-list it in
each config block, as that file's convention requires.

**Catches.** A key press answering to the render before the one on screen. D128 changed two sites, and
more of the same shape remain: `useLeader` and `useRouteStep` in `app/src/App.tsx`, `ReviewQueue.tsx`
and `Pricing.tsx`. `ReviewQueue.tsx` already uses the `handlerRef` and `[]` form and passes the selector
by construction.

**Keeps passing.** The ref form, and any listener whose dependencies are all refs or constants. Do not
land the rule until every site converts. A rule whose first commit needs seventeen exemptions measures
the codebase and does not guard it. The file's own ceiling is that a guard routinely disabled inline is
one the next person disables without reading.

**Mutation arm.** Re-introduce a keydown `useEffect` with non-empty dependencies: lint fails. The ref
form with `[]`: passes.

## Rules where prose is legitimately the only tool

This list is worth as much as the one above. It tells a reader where prose does real work and does not
skirt a machine. It is how D173's rule is satisfied honestly. Each entry says what a machine would have
to be able to see. None of these entries has been re-checked against the code since the audit.

- **Fix the cause and not the symptom. Read for the primitive that would make a workaround
  unnecessary.** A machine would need to know two things. Two expressions answer the same question, one by identity and one by proxy. And the identity exists upstream. The audit's example was a
  reallocated-box check offered three ways, each a heuristic standing in for `bid` (D145). This is
  enforced by review. The one buildable slice is an eslint rule. It bans the reusable box number as an identity comparison in restore paths, and `bid` is the sanctioned key.
- **Never raise Fulfiller impact as a counterpoint to an owner-side build decision.** A machine would
  need to recognize an argument's role. It cannot. The Fulfillment floors are binding and asserted in a
  browser (rank 36 pins the numbers). The argument rule stays prose.
- **One word from the owner licenses both halves of a merge. "merge it" is the word. "ship it", "land it"
  and "looks good" are not.** A machine would need to know whether the owner named the operation.
  D42 rejects a phrase list. `make merge` refuses a bare invocation, so the word is mandatory without
  being classified.
- **Never edit a document only to get a blocked commit through.** A machine would need to know why an edit was made. That needs state across two commit attempts, which is a write on the commit path (D18). The buildable half is a row that fails on any write call reachable outside `--self-test` in `scripts/docs-audit.py`. It also fails on any argparse flag named `fix`, `write`, `apply` or `repair`. D16's
  "a `--fix` flag is a change to this entry" rests on nobody having added one.
- **A wrap-up does not restate the task.** A machine would need to know that a sentence adds nothing.
  `scripts/docs_audit/harness_criteria.py`'s `strip_presentation` sets the bar: a claim is policeable only when it
  self-identifies and its ground truth is a machine-readable assignment in the same tree. Delete the
  restatement and do not widen a check to chase it.
- **A citation must name the section it is about and not merely a section that exists.** A machine would
  need to know what a sentence is about. The audit measured the attributed-form proxy over 38 DEBTS
  citations at one catch against three false alarms. The buildable half is to canonicalize the spelling
  so one pattern finds the population.
- **Keep the product to the modern era, English and Near Mint.** The scope is unsettled and the owner's
  call. An era allow-list would refuse the era the project has run 53 real cards through (ME01) and would
  refuse `riftbound` and `one_piece`. Answer the question or declare the rule dead. The condition half is
  structural: `pipeline/variant.py`'s `CONDITION_BY_FINISH` hardcodes the Near Mint strings, and D137's
  rule lives in the catalog join with a T3 guard.
- **A sale case that mutates its stub store after a press must declare that it requires the re-read to
  disagree with the overlay.** A machine would need to know which assertions are about the optimistic
  overlay and which are about the server's answer. Of seven probed cases, three were red on demand and
  four were green on purpose. It becomes decidable when the contract is declared by a named helper and
  not a copyable flag. DEBT23 is the entry.
- **A change the browser suite depends on must run the browser matrix, including a path the suite composes
  at runtime.** A machine would need a file-access trace or a config evaluator. `make check` is built not to need either. `browser scope` is mechanical and bidirectional, and the residue is false
  negatives only.
- **A figure on screen describes the work in front of the operator.** A machine would need to know
  whether a pass is still the pass the figure describes. That needs a client clock, which this repo
  refuses, or an "end this pass" control nobody has asked for. `OrdersHubStore.walkKeys` is cleared by
  `onFetch` and `onServerBoot`.
- **A decision entry at twice the median length should have cited a neighbor.** A machine would need a
  citation-density heuristic to tell "long because it re-derives" from "long because it measured a lot",
  and D16 keeps heuristics off a blocking row. The honest alternative is a declaration in the entry's own
  first line.
- **Before you hand the owner a task, check whether it is yours.** A machine would need to know two things. Does a step need the owner's body or judgment? Does any route, subcommand or `make` target perform the named action? The capability index is prose: `docs/map.py` says what a module is and not what a person
  can ask it to do. Nothing worth building.
- **A compaction preserves the fixture schema facts, every `make` command and the list of modified
  files.** A machine would need to see the summary. A compaction leaves no artifact in the tree and none
  in the transcript. A PreCompact hook is rejected on D135's grounds: whether Codex has that event is
  unanswerable from this tree.
- **A control must be on the screen a human would look for it on.** A machine would need to know where a
  person would look. D20's defect proves it: route, client and control were all present and 12 of 13
  boxes were unselectable. That judgment needs `make design-check`, which is off the commit path. The
  first two links are mechanical (rank 39). The third is per-capability Playwright work.
- **Whether an entry's argument still holds.** A machine would need to know what an entry protected and
  whether anything still protects it. The checkable shadow is a dangling artifact citation. The buildable
  slice is a required reopening condition on a newly added entry only, scoped by git diff like
  `evidence freshness`.
- **Whether a new mechanism's baseline is still the baseline it was measured against.** This is a gap and
  not an impossibility. Half the shelved mechanisms rest on a one-commit measurement stated in prose.
  Once built, each row prints `ok` whether the population is still what was measured or the walk has
  stopped finding it. T1's three fingerprints (prompt, eval set, and a hash over the scorer's own function
  sources) fall through to a re-measurement on a mismatch. Apply that pattern: a row justified by a
  measurement carries the digest of what it measured. Rank 21's floor is the weak form. This is the
  highest-leverage item not on the shelf, because it keeps the shelf true.

## Proposals the audit rejected, and why

Kept so nobody re-proposes them. A rejected mechanism usually fires on honest work, cannot fail, or would have a gate write to the tree (D18).

- **A Stop hook that blocks a turn claiming the harness is green when no harness ran.** Self-refuting.
  The retired Stop hook ran `make harness` before anything else. A claim check would run after that run, and it would block a claim its own gate had made true.
- **A Stop hook that requires a fresh render and a Read of that PNG.** Three unboundable false-positive
  families, and it would launder a wrong image. Most `app/src` writes carry no appearance claim.
- **A Stop hook that requires BUILT, RECORDED, NEITHER, SPECIFIED or VALIDATED in a wrap-up.** 84% of
  measured wrap-ups would fire, and the escape is typing the word. That trains sessions to paste a
  boilerplate bucket block, which hides a wrong bucket.
- **A Stop hook that compares files named in a wrap-up against the turn's write targets.** Unmeasured. Its
  own author found no instance.
- **A PreCompact hook that injects the fixture facts, `make` targets and modified-file list.** Breakage is
  unobservable by construction. It also collides with D135's `codex hooks` row, which compares the full
  event, matcher and command triple.
- **Registering a harness-running Stop hook on SubagentStop.** The path is unexercised (0 of 129,119
  assistant messages were sidechain). Arming it would spend the owner's CPU on the machine their rig and
  live capture server run on.
- **A warn-only Stop hook that matches delegation phrases and prints the route, CLI and `make` rosters.**
  Every legitimate ask fires it, so it is a permanently lit advisory.
- **A pre-commit rule that requires a staged `docs/debts/` change when the commit message says bandaid,
  workaround, stopgap or "for now".** The subject is a word the author chooses, so it taxes the honest
  bandaid and cannot touch the disguised one. It also induces the editing behavior D16 forbids: a gate
  cleared by staging a markdown change.
- **Banning `api.pokemontcg.io` and TCGplayer Scan & Identify from the product packages.** Zero instances
  ever. D15 and D2 are architecture statements and not rules under pressure.
- **A pre-commit PII ratchet over added lines.** Never measured. A false alarm buys `--no-verify`, which
  disarms the image rule too. `scripts/guard-opsec.sh` was once switched off for over-firing.
- **A `+make icloud-selftest`.** Zero incidents, and the hazard class cannot occur now that the checkout
  lives outside iCloud.
- **Refusing `git add -A` and `git add --all`.** A correct everyday command. The incident had a different
  cause, a bare `ln -s` into an existing path. An existence test on `ln -s` catches it at the cause.
- **A PreToolUse Bash hook that refuses a bare `gh pr merge` without an env marker.** Every measured
  incident went through `make merge` from the wrong tree, so the tree is the subject. Rank 28 fixes it
  there.
- **A non-empty `governed_by` branch in `check_map`.** Any D number that resolves satisfies it, so
  during a file split the cheapest compliance is pasting the nearest plausible one. It corrupts the
  field `scripts/decision-context.py` reads.
- **A `sole writer` row that counts import-CSV writers.** A count of one survives substitution. Pin the
  roster of modules that write an import file, and require each to raise `OutputSuppressed`.
- **An `arm census` row that reconciles published "N arms" sentences against `len(ARMS)`.** A count
  cannot see a dead arm, which is the measured failure. Count kills: the self-test declares its arms as
  data, runs each one, and reports how many killed.
- **A `route reach` row that requires every route a document asserts as built to have a client function.**
  The trigger is prose, so silence clears it, and silence was the incident. Use the unconditional route
  floor of rank 39.
- **A `debts citations` row asserting every `§N` reference names a section that exists.** 55 citations,
  0 unresolvable, and it would not have caught the defect. Canonicalize the spelling instead.
- **A coverage table that requires every server write to have a rect-diff press case (D118).** The
  largest cost in the audit against its smallest harm unit. Build the one press the entry names as
  ungated.
- **Branding `Slot` and `Index` as nominal types.** Forty call sites, and D92 declined it. Take rank 34's
  cheap arm.
- **Deriving `recorded deletions`' needle table by harvesting backticked symbols.** D149's declined
  class: 1 catch against 3 false alarms. The needles are ordinary words, and a deliberate reuse is an
  expensive false positive.
- **An import-edge scan proving the undo and spend client is imported only by named modules (D19, D39).**
  Its subject is orthogonal to the rule's, and it is green either way. Use an eslint selector that
  refuses a timer-driven call.
- **An `advisory roster` row that freezes the set of advisory labels.** It leaves the standing findings in
  place, and it is the wrong shape for a demoted mechanical row. Adopt rank 25's per-finding pin.
- **Promoting `breakpoint columns` and `entry budget` to mechanical.** The first act would refuse two
  correct things. D60 rules that entry budget is a report, and a container query cannot answer
  `RunPanel.css`'s `max-height: calc(100vh - …)`.
- **A `width coverage` row that asserts the visit of each route at 390 and in dark.** A `page.goto` at 390
  satisfies "the visit" with no assertion about what is on screen. Credit a route only where a spec
  asserts an element it has proved is rendered.
- **A ruff or AST ban on `input()`, getpass, `webbrowser.open` and stdin reads in the mapped packages.**
  Zero findings and no instance in history. Every confirmation here is a `--confirm` flag.
- **The waiter-loop hook's second clause (refuse launching a script that already has a live process).**
  Its resolver is the machine-wide pgrep that has reddened `make reap-selftest` four times. D157 rules
  that a per-run subject must be made unable to collide and not made to take turns.
- **Refusing `open` and `osascript … activate` outright in the GUI clause.** It kills the legitimate
  case of showing the owner a file. Keep `screencapture` as a refusal, and demote `open` and `osascript`
  to a printed note.
- **A `gh pr comment` clause that refuses a comment when a live session holds the PR's head branch.** The
  branch-to-worktree-to-pid mapping has been measured wrong, and the harm it prevents is trivial. Demote
  it to a printed note.
- **A `seam list` row that treats a computed write path as unknown and not as a violation.** A silent
  fail-open over the shape that hides, with no denominator. Rank 38 carries the reworked form.
- **Classifying the opsec rule as "already built, nothing to add".** Nothing proves either tier still
  bites (rank 24).

## What this audit did not reach

- `docs/GATES.md`: only three "What is open" items were read as a rules surface. The rest was evidence.
- `docs/specs/`: nine specs were read incidentally where a decision cited them and were never swept as a
  rules surface. `docs/DESIGN.md` holds the Fulfillment constraints table and a token block that two rows
  already read, so it may hold more.
- CLAUDE.md's design-system, shell and "Verifying a screen" paragraphs were read as context and not as a
  rules surface. They carry at least four imperative rules, of which only the mark's `border-radius`
  rule is in this file.
- `code-card-fork/CLAUDE.md`, a separate track with its own schema, was unread.
- The harness modules' `PASS_CRITERIA` strings, `app/tests/`'s specs and the workflows beyond `check.yml`
  were sampled or unread. The skills (`tcgplayer-csv`, `docs-audit`) were not opened.
- The transcript evidence rests on one reader's scan of 389 sessions. Two proposals were declined for want
  of a dry run: the derived deletion-needle table and a "watched counts" row over every published integer.
- Nobody dry-ran the Bash write-target resolver that other shelved clauses would share. Its parse
  coverage over real session commands is unmeasured, so every clause is specified to fail open, and a
  "guard throws" arm belongs in its self-test.
- Whether Codex exposes a PreCompact event is unanswerable from this tree.
