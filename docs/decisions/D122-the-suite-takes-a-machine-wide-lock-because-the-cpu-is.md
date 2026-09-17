## D122 — The suite takes a machine-wide lock, because the CPU is the one thing a checkout cannot have its own of

**Built 2026-09-07, after a session spent two re-runs on failures that were not in its code.**
In the `magical-kalam-0230c3` worktree a full `make design-check` reported
**18 failures, every one in `shipping.spec.ts` or `run-panel.spec.ts`** — with the WHOLE of
shipping failing rather than individual assertions. Re-run alone, nothing else touched:
**52 passed**. Another worktree, `cap-on-demand`, was running its own Playwright suite at the same
moment — about **90 browser processes between them on a 15-core Mac**. Earlier
in the same session the same collision produced one intermittent failure in `nav.spec.ts` and one
in `capture-undo.spec.ts`, each of which also passed in isolation, and each of which cost its own
re-run.

**D43 IS THE ENTRY THIS ONE FINISHES.** That decision gave every checkout its own dev port, its
own capture port and its own store, so two trees can be worked in at once without either
answering for the other — and it closed a defect of exactly this shape, a green
`make design-check` in a worktree that had asserted against the main tree's server.
**The CPU is the one resource it could not give them a copy of.**
`app/playwright.config.ts` is `fullyParallel`
at Playwright's default worker count, which is half the cores — seven here — each worker a
Chromium context, plus a Vite dev server compiling the module graph for every one of them. Two
trees is 4x oversubscription against a rig sized for one.

**THE REPO HAD ALREADY DIAGNOSED THE FAILURE AND STILL COULD NOT SEE IT.**
`app/playwright.config.ts` records it against a deliberately starved rig — *"a context can fail to
render at all rather than slowly: with the allowance raised to 120s, 10 of 80 still failed and one
took 122s. A wait cannot answer that"* — and that comment is about oversubscription WITHIN one
run, where the config can at least count its own workers. Across two runs in two checkouts there
is nothing to count with. So the answer is not a longer timeout and not fewer workers; it is
mutual exclusion, and it has to live somewhere both runs can see.

**WHAT IS NOT THE CAUSE, so nobody re-derives it.** Not the capture server: `app/tests/shell.ts`'s
`sealEveryTest` aborts every capture request, and D43 gives each checkout its own capture port, so
two suites never touch one server. The contention is CPU and memory and nothing else — which is
also why the lock must live outside every checkout, and why `.serve/` was the wrong home for it.

**IT IS AN ADVISORY `flock`, WHICH IS WHY THIS FEATURE HAS NO STALE-LOCK PATH.**
The file is `~/.pkmnscan/locks/browsers.lock`. `scripts/serve.py` proves a pid is still the process it
recorded by comparing `ps -o command=` against the argv it stored, and it has to: a port is the
resource there and it outlives the process that held it. Here the OS owns the whole question — an
advisory lock is released when the holder exits, however it exits, including `kill -9`, a crashed
session and a reboot. The pid, the tree, the command and the start time are written INTO the
locked file and are read for one purpose only: naming the holder in the refusal. `make
suite-lock-selftest` proves the point by killing a holder with -9 and asserting the lock is free.

**IT REFUSES RATHER THAN QUEUES, AND THE REFUSAL EXITS 75.** A suite that silently waits for
another tree looks hung, which is its own failure mode and one the 2026-09-07 session also hit —
ten minutes pass before anybody suspects a queue rather than a wedge. So the default names the
tree, the pid, how long it has been running and the command it is running, and offers three ways
on. `make design-check ARGS=--wait` queues instead, out loud: it announces itself on the first
line and says so again every thirty seconds.
**75 rather than 1, because `playwright test` exits 1 when tests fail**
— a guard built to stop false failures must not produce one. 75 is
EX_TEMPFAIL, `make` prints `Error 75`, and nothing else in this repo returns it.

**THE LOCK IS NAMED FOR THE RESOURCE, NOT FOR `design-check`.** It is `browsers`, so the second
browser fleet to land here joins this lock rather than inventing a second one that excludes
nothing. `scripts/docs-audit.py`'s `suite lock` row reads the RUNNER for the same reason: any npm
script whose command is `playwright test` is a fleet, and every Makefile recipe reaching one has
to go through the lock — because the guard is one line of one recipe, which is exactly the kind of
line a new target gets written without. The row fails in both directions and refuses to go quiet
if the runner is renamed past it.

**`make screenshot` IS OUTSIDE IT, ON ITS SHAPE RATHER THAN ITS COMMAND.**
`scripts/screenshot.sh` loops the manifest serially and each render is one
`chromium.launch()` and one `newPage()` in `scripts/screenshot.mjs` — one browser, one page, not
a fleet, and it already needs a dev server somebody started by hand. Putting it behind the same
lock would make a single render queue behind a ten-minute suite for no measured benefit.

**THIS PARAGRAPH NAMED `playwright screenshot` FOR ONE DAY AND WAS WRONG WHEN IT MERGED.** D43's
screenshot work (#223) replaced that CLI with `scripts/screenshot.mjs` on 2026-09-07, the same day
this entry was written, and the two landed hours apart without either reading the other.
**The reasoning was untouched by it** — the run is still one browser at a time — which is why
the correction is to stop naming a command at all. What decides this is whether a runner draws
pages in PARALLEL, and `playwright test` is the only thing here that does. That is what
`scripts/docs-audit.py`'s `suite lock` row reads, and it reads it across the shell and node
runners too, so a serial renderer growing workers is caught rather than argued about.

**`make harness` AND `make check` DO NOT TAKE IT, AND EACH HAS ITS OWN REASON.** The harness runs
at every turn end from the Stop hook: a refusal there is a false failure at exactly the moment a
session is trying to finish, which is the thing this entry exists to stop, and its nine tests are
one Python process rather than fourteen browsers. `make check` shells out to `tsc`, `eslint` and
`ruff` — two concurrent runs is a handful of single-core processes against a 15-core machine, an
order of magnitude off the load that produced the eighteen failures, and it is not a load anything
here has measured a failure from.
**That is reasoning and not a measurement, and §16 records it as such**,
along with what would reopen it.

**THE ESCAPE HATCH IS `PKMNSCAN_SUITE_LOCK=off` AND IT IS PRINTED IN EVERY REFUSAL**, in the shape
`PKMNSCAN_MAIN=off` and `PKMNSCAN_FOREGROUND=ok` already use. A guard with no visible way past it
is one somebody disarms by deleting the line from the Makefile, where nothing would catch it.
`PKMNSCAN_LOCK_DIR` moves the lock directory and exists for the self-test alone — same shape as
`scripts/janitor.py --sessions DIR`, and for the same reason: a self-test that took the real lock
would refuse a suite running in another checkout.

**What would reopen this:** a measurement showing two concurrent `make check`s producing a failure
that is not in the code, which would put `lint` and `typecheck` behind a lock of their own; or a
second Playwright fleet whose cost makes a queue better than a refusal, which is a change to the
default rather than to the mechanism.