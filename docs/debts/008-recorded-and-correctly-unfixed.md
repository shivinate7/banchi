## 8 — Recorded and correctly unfixed

**No work proposed. Here so a green run is not read as a promise none of these exists.**

### The supervisor's four gaps (D53)

It said "Three" over four bullets from the day it was written until 2026-08-30 — the swap gap
was appended without the lead-in being re-read, which is cluster 2's defect at the scale of one
word.

- **A request accepted but not yet inside `_dispatch` is uncounted by the drain.** Window is
  microseconds; closing it means reimplementing `handle_one_request` in the file that most wants
  to stay boring.
- **The parse pre-check catches syntax errors only.** `scripts/serve.py` refuses to restart into
  a file that does not `compile()`. An `ImportError` or module-scope `NameError` still kills the
  new child and **there is no rollback** — the last-good process is already gone. Containment is
  the fast-failure cap: after five quick deaths it stops respawning, keeps watching, and says so.
  Fixing it properly means the socket-passing design D53 names and rejects for v1.
- **The reload notice has no automated case, and three attempts to write one are why.**
  `ServerReloaded` renders nothing until the boot header CHANGES between two responses. A stub
  over `app/tests/fulfillment.spec.ts`'s helpers did not win the route, `route.fetch()` fails
  outright, and a body-stubbing version left too few requests to produce a second header. **Two
  attempts PASSED against a build with the notice rendered unconditionally** — vacuous — and
  were deleted, because a case that cannot fail is a green row asserting nothing. What IS
  verified: the header observed reaching the browser cross-origin over the real server (eight
  responses carrying `X-Pkmnscan-Boot`), and the notice photographed appearing on `#/inventory`
  after a real restart and NOT on `#/fulfillment`. What guards it structurally is `hasChrome`,
  the nav's own condition, which `fulfillment.spec.ts:noWayOut` already covers.
- **The swap gap.** Between the old child exiting and the new one binding a request gets
  `ECONNREFUSED`, and `app/src/server.ts` deliberately has no retry, so it surfaces as
  `unreachable`. Tens of milliseconds. Named in D53 with the fix considered and declined.

### The one-process supervisor builds against a stub, and the reaping it deferred is now spent

**Nothing in this file was discharged by D138.** The supervisor's four gaps above are each about
the capture child, the drain and the swap, and one process changes none of them; section 11's
bounded pool is an argument about real clients and is untouched by where the app is served from.
Walked entry by entry on 2026-09-11, when the `restart` alias and the `VITE_*` remnants were
retired.

**What it adds is one gap, and the gap is deliberate.** `make serve-selftest` proves the build
behaviors — a missing `dist/` builds before the port opens, a screen edit rebuilds and restarts
nothing, a failed build leaves the old bundle serving — against a STUB `app/` whose "build" is a
script that writes one file. Its own header says why: *"WHAT IS UNDER TEST IS THE SUPERVISOR, NOT
VITE."* That is the right subject for a self-test, and the cost is that the supervisor's contract
with the REAL `vite build` is asserted by nothing here — its exit code on a type error, the
`dist.next` rename, the shape of what it writes. The first thing that would notice a regression
is `make up` on a rig.

**The deferred reaping is spent, not abandoned.** `VITE_PID`, `VITE_LOG` and the `VITE` child
entry outlived D138 on purpose, so that the first `make up` or `make down` after it landed could
reap a detached `npm run dev` left behind by a supervisor running the previous code. That run
happened on the main checkout at 15:24 on 2026-09-11, and at the retirement **0 of 20 checkouts
on this machine held a `.serve/vite.pid`** — the entry had nothing left anywhere to find. What is
given up is the checkout that somehow still holds one: `scripts/serve.py` can no longer name it,
and it falls to `make reap` and `scripts/janitor.py`, which read the process table rather than a
pidfile and are not bounded by what a pidfile happens to be called.

### A Playwright line number is not a line in the file

Playwright strips the TypeScript and reports against the generated file, so a spec loses the
lines its type-only constructs occupied and gains the lines its long ones are re-broken into.
**Wrong for nearly every test in the suite** — 254 of 256 at `3ca904e`, 257 of 259 later —
checked by walking `--reporter=json`'s location for all of them. Measured with a probe: a test
on source line 24 with nothing above it reported 23; the same test on line 27 under a 22-line
`type` block reported 3. Clearing `$TMPDIR/playwright-transform-cache-501` changes nothing.
**Cost: a citation nobody can follow** — a session opening the file at it lands on unrelated
code, silently, because the line is real and the file is right. Grep the TITLE instead; the
reporter prints that too and it is exact. Nothing to fix at 1.55.1; the remedy is to stop
writing the number down.

**The same shape in the docs, and `doc hygiene` sees only its provable half.** Docs carry 52
resolvable `path:line` citations. D74's row catches one failure — a number past the end of its
file — and there are none today. **The common case is invisible**: a citation whose file is
long enough but whose line has moved, which is exactly what `ReviewQueue.css:47` became when
the comment it named slid to line 57. Nothing distinguishes that from a correct citation
without knowing what the line should say. **The remedy is the same one this entry already
gives** — cite the identifier, not the number — and the 2026-08-30 prose sweep applied it
where it rewrote a citation rather than adding a check that cannot exist.

### What is not closed about the `make design-check` flakes

Three flakes were reproduced and fixed 2026-08-30 — a `toBeVisible()` timeout answered by
`expect: { timeout: 15_000 }` in `app/playwright.config.ts`, a two-layout subtraction in
`app/tests/inventory.spec.ts` answered by reading both tops in one `page.evaluate`, and a
snapshot race in `app/tests/shipping.spec.ts` answered by `toHaveText`. None weakened an
assertion.

**A starved rig is not a slow one, and no wait answers it.** At 40 workers against 12 CPU hogs
— 4x oversubscription on a 15-core machine — a context can fail to render at all: with the
allowance at 120s, 10 of 80 still failed and one took 122 seconds. At that load the suite also
loses `app/tests/fulfillment.spec.ts` on `main.fulfillment`, `app/tests/capture-claims.spec.ts`
on the Finish row, and `app/tests/capture-undo.spec.ts` on a capture that never landed — it
expects `Card 10` and the newest is `Card 9`, a **dropped press** rather than a slow one and the
only one a longer wait could never answer. **None of it is reachable from `make design-check`,
which runs 7 workers here.**

~~**One sighting is unexplained**: at 15 workers, before either fix, `app/tests/cursor.spec.ts`
failed once in nine runs. Its message was not captured.~~ **CLOSED 2026-09-08 — it was the
select, and the rate at that width is 16%.** See the survey below, which reproduces it on demand.

### The runner's one-test red is measured, instrumented, and still open, 2026-09-11

**D128 did not close it.** That entry found one real defect — a `keydown` listener a render behind
the screen — and fixed it, and its own last section declined to promise a green CI. The promise
would have been wrong: on 2026-09-11, with D128 merged, PR #245's `design-check` job went red on
`capture-claims.spec.ts:264` at the helper's own line 191, `toHaveCount(0)` polled nineteen times
at 3 — the same locator, the same shape, the same fifteen seconds as the two instances D128
attributed to the closure. The re-run was green. So the shape D128 named survives its fix, and the
mechanism is not known.

**What was measured, over every completed `design-check` job since it landed on 2026-09-08.**

| | completed runs | red | rate |
|---|---|---|---|
| all | 113 | 6 | 1 in 19 |
| since D128 merged (2026-09-10 18:27Z) | 13 | 1 | 1 in 13 |

Never more than one test per run except the job's first, which had three — two of them the D118
platform difference `check.yml` records, fixed the same day and not counted below. **The five
that remain are one shape: the assertion right after a `keyboard.press('Escape')`** —
`capture-claims.spec.ts` three times (lines 264, 314, 816), `live-reconcile.spec.ts:236`,
`markdown.spec.ts:539`. The failing case never runs slow: today's began its fifteen-second wait
1.4s into the test, and the two earlier capture instances 0.8s and 0.6s in — page load, the `f`
press and the track drawing all landed inside a second, and then one Escape was not honoured for
fifteen. **The three capture instances began between 111 and 121 seconds after the run's first
test**, at three different cases; the other two at 470 and 531. Three points is not a clock, and
it is written down because it is the only regularity in the set.

**What does not reproduce it, on this Mac and on the runner.**

- 40 of 40: the helper's exact sequence under a 6x `Emulation.setCPUThrottlingRate`, one worker,
  the lever that reproduced D128's held-sheet shape 3 in 20.
- 240 of 240: the same sequence on `ubuntu-latest`, three shards, one worker, traces armed.
- 315 of 315: the whole of `capture-claims.spec.ts` on the runner, `--repeat-each=5`, three shards.

- 0 of 5: the WHOLE suite on the runner with tracing armed — four shards on this branch and the
  PR's own job — produced no Escape-shaped failure at all. What those five runs did produce, each
  with a trace, was that afternoon's main: the location card PR #244's merge had brought back
  (4 of 4 on `inventory.spec.ts`'s D118 case, gone once D119 was re-applied) and PR #246's
  `Open the review queue` link under the thumb floor at 390 (`phone.spec.ts:206`, which main's
  own untraced run fails identically). The instrument's first catch was somebody else's defect,
  which is what an instrument is for.

So the case that fails one run in thirteen inside the suite passes 555 times outside it, on the
box it fails on. **The suite around it is part of the mechanism** and nothing measured says which
part. **Which is why D136 shards the job three ways and does not widen it**: the shape those 240
and 315 passes were measured in — three shards, one worker — is the shape CI runs now, and the
worker count stays at one because more workers on one box is more suite around the case. The candidates read and ruled out by evidence rather than by argument: a Vite dependency
re-optimisation forcing a reload (the app's only runtime dependencies are React's, all bundled at
scan, and a reload would EMPTY the track rather than hold it at 3); a second listener eating the
press (the leader's capture-phase `stopPropagation` fires only while armed, and nothing arms it);
worker oversubscription (there is one worker); an exit animation keeping the cells in the DOM
(there is none — `openField` has three setters and none animates).

**What changed, and it is instrumentation rather than a fix.** `app/playwright.config.ts` turns
`trace: 'retain-on-failure'` on under `CI`, and `check.yml` uploads `app/test-results` when the
job is red — the DOM before and after every action, the console and the network of the case that
failed, beside the `error-context.md` snapshot Playwright already wrote and the runner already
threw away. Five instances have been diagnosed from four reporter lines each; the sixth will have
its trace. Open it with `npx playwright show-trace <zip>` and read the DOM at the `Escape` and at
the first `toHaveCount` poll — whether the track is open in both is the first fact nobody has.

**What was refused, again, for D128's reasons and one more.** `retries: 1` would retire the count
this section is built on. A longer timeout answers nothing that resolved to 3 nineteen times. A
retry loop around the Escape in the helper would make every recorded instance green and would be
the one change that could hide the mechanism from the trace that is now armed to catch it. **The
workaround stands and is named**: `gh run rerun <id> --failed`, about seventeen minutes, until the
trace says what the runner is doing.

### The suite was surveyed rather than argued about, 2026-09-08

**Ten clean runs of the whole suite, then the offenders hammered on their own.** The trigger was
one red `press floor` case during PR #220's merge, called a flake and merged past. It was a real
race, it is fixed, and a second one nothing had ever recorded was found beside it.

| test | full runs | `--repeat-each=100` | parallelism |
|---|---|---|---|
| `cursor.spec.ts` — the press floor answers for every shape | 1 of 10 | **4%** at w7, **16%** at w14, **1%** at w1 | aggravates, does not cause |
| `nav.spec.ts` — the armed leader is disarmed by arriving | 1 of 10 | **3%** at w14 | aggravates |
| every other case (459) | 0 of 10 | — | — |

**The run-level rate was 1 in 10 and the test-level rate 2 in 4,610.** Both reds landed in the
same run. Duration does not predict them: the slowest run of the ten (154s) was green and the
failing one was 121s against an 86s floor.

**THE PRESS FLOOR CASE WAS A TEST TELLING A TRUE-LOOKING LIE, AND `base.css` WAS RIGHT EVERY
TIME.** Every failure named the same shape — `a select did not move under the press` — and never
one of the other eleven. `<select>` is the only shape here whose default action opens a NATIVE
POPUP, and the popup takes the press: the dip lands on the frame the mouse goes down and
`:active` is cleared again before a separate CDP round-trip can read it. Measured with a probe
sampling both ways at once: **the dip was present at `mousedown` 80 times out of 80** while the
round-trip read missed it. So what was intermittent was the OBSERVATION. Fixed by suppressing
the popup with a capturing `preventDefault` for the length of the press; `preventDefault` does
not stop the browser applying `:active`, which is what the case reads. **100 of 100 at fourteen
workers afterwards, against 84 of 100 before.**

**The obvious fix for it WEAKENS the case, which is why it is not the fix.** Sampling the dip
inside the element's own `mousedown` listener is exact for the shapes that get one — and a
genuinely disabled control dispatches NO mouse event while still matching `:active` in Chrome.
Proved by mutation: with the disabled arm deleted from `base.css`, the listener version went
silently green while the round-trip read named all three disabled shapes at `0px 1px`. That arm
is 30 of D50's original 41 defects. **A guard that cannot see its subject is worse than no
guard**, so the read stayed and only the popup was removed.

**THE LEADER CASE IS A FRAME COUNT, WHICH IS A DURATION IN DISGUISE.** `nav.spec.ts` sampled
`data-armed` exactly two animation frames after `hashchange`, reasoning that React would have
committed the arrival by then. Under load it has not, and the case then reports a working disarm
as broken. It could not simply poll, and its own comment says why: the arm expires on its own
after `CHORD_MS`, so an auto-retrying assertion goes green with the disarm deleted. **Fixed by
measuring WHEN the arm ended rather than whether it has ended yet** — a `MutationObserver` times
the disarm from the hashchange, and the case asserts it landed inside half the window. A disarm
on arrival lands in a frame or two; an expiry lands at `CHORD_MS`. With the disarm deleted the
case fails naming the mechanism: *"the arm outlived the arrival by 951ms"*.

**Both fixes are mutation-proved and neither weakens an assertion.** Three mutations against the
press floor (`select` dropped, the disabled arm dropped, the aria-disabled arm dropped) and one
against the leader all go red. Five full runs of the suite are green afterwards.

### The suite fetches three typefaces from Google Fonts on every page load

**Unfixed, and named here because nothing else names it.** `app/index.html` links Inter, Manrope
and JetBrains Mono from `fonts.googleapis.com`, and `app/tests/fontsReady.ts` awaits
`document.fonts.ready` in nearly every case. At 461 cases with a fresh context each, one run
reaches the public internet on the order of a thousand times, and `sealEveryTest` does not cover
it — it seals this checkout's CAPTURE port and nothing else.

**No failure in this survey was traced to it**, and `&display=swap` means a fetch that fails
degrades the measurement rather than hanging it. What it costs is that the suite has an outside
dependency it does not declare: a DNS stall or a rate limit is indistinguishable from a slow
render, and the cases that would feel it first are the ones measuring type. Self-hosting the
faces would close it and is a product change, not a test change, which is why this is a note
rather than a fix.

### `make design-check` no longer reaches the capture server at all

**Section 11 says it is "a known trigger" for the concurrency collapse. That has not been true
since the specs were sealed.** All nineteen browser specs call `sealEveryTest`, which registers a
catch-all `page.route` on this checkout's capture origin, ABORTS every request to it, and asserts
in `afterEach` that none was attempted; `motion.spec.ts` is a pure unit test with no page at all.
So a request to the capture port does not merely fail to arrive — it is never made, and a case
that made one would fail by name.

**§11's measurement — 969 threads under 80 Playwright browsers — predates that sealing** and
describes a suite that no longer exists. The bounded pool it argued for is still right for the
reasons §11 gives, which are about real clients rather than about this suite. What is no longer
true is that `make design-check` is one of them. **The corollary is a gap rather than a
reassurance**: `REQUEST_SLOTS` and `Connection: close` are exercised by nothing in the browser
suite, so nothing here would notice them regressing.

**Three non-retrying reads remain**, all in `app/tests/inventory.spec.ts`, of the eight
originally counted. None has been observed failing, and `expect(await …innerText())` is a
narrower hazard than the list form that broke. **Two comparisons in the geometry case still
pair an early read with a late one** and are left alone — 8px of declared slack against a
measured 0, and a 41px column gap. A case is not improved by rewriting assertions that have not
failed.

**Two numbers were published against runs nobody read.** A commit message said "design-check
257" when the run was 255 passed and 1 failed and the true count was 256; and the entry above
said five non-retrying reads when there were three. The suite is **264 cases** as this is
written, which is the same lesson a third time: a count recorded here is stale the week after.

### `make check` is not automatic

`--self-test` had been RED for some time — a `tested_by reach` case pinned to T3, T3 began
importing `store`, and the case asserting a false claim stopped catching one — while
`make docs-audit` stayed green and so did every commit, because **nothing ran it**. Closed
2026-08-24: the case moved to T5 and states its requirement in the comment, and `make check`
runs `audit-self-test`.

**Deliberately NOT in the git hook** — D18, not taste: `--self-test` is the one mode of that
script that writes, and nothing that writes may run on the path deciding whether a commit
proceeds.

**Residual:** the Stop hook runs `make harness`, not `make check`, so a red self-test surfaces
only when somebody asks — the same standing `githooks-selftest`, `port-agreement`,
`ignore-check`, `vale` and `lint` all have. And **`--self-test` does not drive a real git
index**: the index-mode primitives have cases, but no case exercises the staged blob. It bites
hardest on `check dispatch`, whose whole subject under `--staged` is the blob. Driven by hand
at integration, and by hand is where it stays.

**`check dispatch` also cannot see its own unwiring.** Delete its call from `audit()` and every
other row prints green, the run exits 0, and the row is absent. A detector cannot detect its own
absence, so there is a root to the recursion: unwire anything else and the commit fails, unwire
*this* and only `--self-test` catches it. Related: **called is not run, and run is not looked** —
a dispatched check returning before its `report.add` prints no row, which `check_raw_color` does
when `app/src/` is absent. And **`scripts/status.py` is not in `INVOKERS`**, so `audit invocation`
does not see its call; it would find nothing if it did, since that row reads flags off a literal
command line and `status.py` builds argv as a list.

### The `fixtures/` guard is one tool wide at write time

`.claude/settings.json` denies `Write(./fixtures/**)` and `Edit(./fixtures/**)`. **Bash is
not**, so a `python3 -c`, a heredoc, `cp` or `sed -i` goes past it silently. Measured by
walking through it: the session that built `fixtures/orders-shipping.csv` wrote it with a
script and only discovered the rule afterwards, when a `Write` into the same directory was
denied. **The guard did not participate in the decision at all.**

**The commit-time half is armed and always was.** `scripts/githooks/pre-commit` refuses any
staged modification under `fixtures/` via `--diff-filter=MDR` — which is the add-vs-modify
distinction the deny rule blurs and this entry once proposed as unbuilt. **So the cost this
entry priced cannot happen**: a modification that never reaches a commit never reaches a later
week. The residue is a confusing half-hour, not lost ground truth — a Bash write lands in the
tree immediately, so `make harness` can go red before anything tries to commit.

**Why the write-time half stays open.** A deny list cannot see what a script writes at run
time, and a pattern broad enough — denying `python3`, or shell redirection — takes
`make harness`, `make check` and `scripts/docs-audit.py` down with it. Same trade D16 refuses
for `--no-verify`. **Not the same gap as the PII one**: this repo has no secret scanning either
(the hook's only content rule is the code-card regex), so a fixture carrying buyer names commits
clean. That is about what is *inside* a file; this is about *which tool* wrote it.

### Nothing in the product SHOWS the history, and it is a table now, not `history.jsonl`

**Two corrections, 2026-09-05.** D88 moved the store of record into `inventory/store.sqlite`,
so the history is a TABLE and the filename this heading carried is the legacy one — a JSON file
left beside the database is never a fallback, which is the rule that makes the old name
actively misleading rather than merely dated.

**And the sole-reader claim was wrong in four places, this being the fourth.**
There are three readers — `_answer_origin`, `_origin` and `_reverse_stand_down` — and
`_state_before_sale` is none of them: it is handed a sequence of events and scans it, and it
has a twin, `_state_before_retirement`, that scans the same way. The other three instances were
corrected first; this one survived because it is on a line wrap in the reverse word order, and
the guard that now catches it (`scripts/docs-audit.py:check_sole_reader`) had to be widened
twice to see it. That widening is the useful part of this entry: a checker over prose that
reads one line at a time is checking typography, not sentences.

The three writes that changed no state — a correction, a capture undo, a review answer — all
leave a row as of 2026-08-13, asserted by `check_history` in
`harness/tests/t7_store_and_seams.py`. No route serves it and no screen shows it, and every
scanner filters positively against `master.STATES`, so all three are inert to them by
construction. The audit value is a person with a text editor, which is what an audit
trail is for — but **a line that stops being written is invisible to everything except T7.**
Two by choice: a `PUT` changing no value logs nothing, so a silent sidecar repair leaves no
trace; and the vocabulary lives in two places (`master.STATES` and `SERVER_EVENTS`), so a
reader has to know both.

### D60's guards see tokens, never arguments

`scripts/prose-guard.py` is the only thing comparing two versions of a doc, and it compares
HARD TOKENS — backticked identifiers, paths, decision ids, measurements, dates. **A rewrite
keeping every backtick and losing the reason an entry exists passes silently.** That is the
residual risk of the whole D60 exercise and nothing mechanical can close it: judging whether a
paragraph still carries its argument is D16's layer 3, a model reading prose, deliberately never
a gate. `--facts` is on no gate either — it needs a BEFORE, which exists only while a rewrite is
in flight. The two rows that DO gate, `decision structure` and `entry budget`, check the tree as
it stands and cannot see what a change removed.

### Two documents outran the code

- `docs/specs/audit-retirement.md` restates a check roster and a count the shipped registry no
  longer matches, and `CLAUDE.md` tells sessions to read specs as settled. It needs a status
  line naming which premises failed under execution — **not** a corrected number, which would
  only reset the clock: the restatement is the defect.
- `.claude/commands/docs-audit.md` says exit 2 means the coupling question, but the command it
  prints in step 1 runs without `--staged`, and coupling only runs under `--staged`.

### The second fenced block in `docs/DESIGN.md` is not read

`design tokens` reconciles the `## Tokens` fence against `app/src/tokens.css` both ways, and
`raw color` now blocks a hex anywhere in `app/src/*.css` — which closed the sharper half, the
`#ffffff` in `app/src/PullConfirm.css` that survived a design review and two integration passes.
What is left is a document disagreeing with itself: step 6's three button states restate five of
these hexes in a second fence nothing reads. Left out because D18's instinct is that deleting a
restatement may be the right answer, and that argument belongs in `docs/DESIGN.md`. The sheets
in `docs/design-refs/` stay unchecked for a settled reason — they are drawings of the spec and
are allowed to lose to it.

### `design tokens` locks names for every token and values for only the hexes

Named 2026-09-03, when the row was rewritten for the `--bn-` system. It compares a VALUE only
where `docs/DESIGN.md`'s block states a hex literal — 31 of 100 declared tokens. The other 69 are
checked for existence in both directions and their values are locked nowhere: an alpha of another
token (`ink 8%`), an alias (`--bn-money` = ink in both themes), a duration, an easing curve, a
shadow, a control height.

**That is a real gap and not a shrug, and the shape of it matters.** The dangerous drift this row
exists to catch is a value nobody chose rendering perfectly, and a wrong `cubic-bezier` or a
wrong shadow is exactly that. What stops it being closed by writing more hexes into the document
is that most of these are not hexes: `--bn-line` is *ink at 8%* by design, and spelling its two
rendered values out would create the second source of truth the tint was invented to avoid — the
light and dark values would then have to be kept in step by hand, which is the defect, not the
fix.

**What would close it**: a reader that resolves `color-mix()` and `rgba()` against the token they
reference and compares the resolved value, which is a small CSS color engine and was judged not
worth building for 69 tokens. Until then the row's summary line says how many hexes it compared,
so a green row cannot be read as full coverage.

### The browser matrix's path scope reads literals, and a dependency built from pieces walks past it

**D141 gates `check.yml`'s browser matrix on a pull request by `scripts/browser-scope.py:SCOPE`, and
`make docs-audit`'s `browser scope` row derives what the suite depends on from the two configs, the
`design-check` recipe and every code string in `app/tests` and `app/src` that names a tracked file
outside `app/`.** That last reader is what found `cadence.spec.ts`'s two traces under `harness/`. It
sees a literal. A spec that builds a path from pieces — `` `harness/${dir}/${name}` `` — names no
tracked file this reader can resolve, and a Vite `server.fs.allow` widening spelled through a
variable rather than a string literal is invisible to it in the same way. Neither exists today.
Either would leave the matrix skipping a class of change it should run for, with the row green.

**Deliberately unfixed**: the honest reader for the first is running the suite under a file-access
trace, which is a browser on the commit path; for the second it is a Vite config evaluator, which
is `node` on the commit path. Both are what `make check` is built not to need. The row's own
docstring names the gap, and `route rosters` and `storage keys` carry the same shape.
