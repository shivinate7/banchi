# BANCHI

Bulk-list pre-sorted TCG singles on TCGplayer with zero attention per card, and know where
every card physically is.

Code cards are a feature of this product, not a second track (D248, turn end never runs the harness, and code cards
share one rules file). The feature is DORMANT. See "Code cards (dormant feature)" below.
D14 (two tracks, one rig) still stands in structure. `codes/` is its own package. `docs/map.py`
carries a `TRACKS` list. `scripts/decision-context.py` prints a track banner. Repeal needs the
owner's word.

Codex reads this file, not a copy (D135, Codex reads the same rules). `AGENTS.md`,
`code-card-fork/AGENTS.md` and `code-card-fork/CLAUDE.md` are relative symlinks to it.
`.agents/skills` links to `.claude/skills`. `.codex/hooks.json` mirrors `.claude/settings.json`.
The `agent links` and `codex hooks` rows of `make docs-audit` check both. "Folder rules" below covers the
rules that moved out of this file.

## Banchi names everything (D94, Banchi names everything)

**Banchi** names the app, the GitHub repository `shivinate7/banchi`, the checkout, the CLI `./banchi`,
the env vars `BANCHI_*`, `~/.banchi` and the launchd labels `com.banchi.*`. The old name was
`pkmnscan`. A new `pkmnscan` outside `fixtures/` is a defect. `inventory/store.sqlite` keeps its
name. Fixtures are never modified.

- GitHub Pages follows the repository name. `.github/workflows/demo.yml` derives `DEMO_BASE` from it.
- `~/.pkmnscan` moves to `~/.banchi` once, in `server/ports.machine_dir`. Each launchd `--remove` also (`server/ports.remove_old_agent`)
  removes the old `com.pkmnscan.*` plist.
- No gate is current. Gate A, B and C passed, and their run records are deleted. History lives in
  version control.

## Commands

```
make hooks          # arm the git hooks from scripts/githooks/. Once per clone.
make worktree-setup # fresh worktree: venv, T1's cache, app/node_modules, this checkout's port.
make status         # next step, T1 score, branch.
make map            # docs/map.py rendered. ARGS=<package|path|D<n>|--stale|--decisions>.
                    #   ARGS="D<n> --full" prints that entry verbatim.
make explain        # what `make check` runs, and what each row is worth. ARGS=<target>.
make serve-scope    # first path gate, read by `make serve-selftest`. ARGS=list | "classify --base <rev>".
                    #   BANCHI_SERVE_SCOPE=all runs it anyway (run-everything, not a hatch).
make guard-scope    # second path gate, read by each gated self-test. ARGS=list | classify.
make orient         # ARGS=<file.tsx> [--name <C>]: which component draws it. Run before briefing a screen.
make map-fix        # adds a file's cited decision ids to docs/map.py. Previews. ARGS=--write.
make offenders-prune # deletes stale offender-list entries only. Previews. ARGS=--write.
make harness        # all ten verification tests, T1-T9 and T11. No T10.
make up             # the server, detached, one process. ARGS=--restart bounces it. `make down` stops it.
                    #   Refuses on a primary checkout off main. BANCHI_SERVE_MAIN=off overrides.
make restart-now    # ends a held auto-restart and app build at once (D176 (the primary checkout syncs): they wait for 5 idle minutes, 2 hours at most). Ask the owner first; only while one waits.
make reap           # stop what THIS session started, nothing else. Previews. ARGS="--confirm",
                    #   "port:N --confirm", "match:X --confirm" or "pid:N --confirm". An agent's bare
                    #   --confirm stops only its own session's pids (D305, the reaper stops only its own).
make janitor-install # retired: claude-settings' install.sh owns the user's Claude bin directory. Copies nothing.
make merge          # claude-settings' shared merge tool (D140, merge claims the decision number), config in
                    #   `.github/stamp.json`. ARGS=<n> previews. ARGS="<n> --confirm" merges, and claims record
                    #   numbers first. The batch runner runs it under the coordinator's standing grant. It runs
                    #   from any checkout, not only the PR's branch. It never rebases or force-pushes:
                    #   a moved head stops it, so rebase by hand and run it again.
make janitor        # claude-settings' sweep (claude-settings decisions/the-janitor-is-one-machine-wide-sweep.md, "The janitor is one machine-wide sweep"): what a finished session left behind. Previews. ARGS=--confirm reaps.
                    #   ARGS=<root> narrows it to one clone. scripts/janitor.py keeps --teardown.
make janitor-agent  # retired: claude-settings schedules the daily sweep. Prints how to drop the old agent.
make launch-agent   # start the server at login (main tree only). ARGS=--remove. It keeps the server alive over the real store.
make dev            # Vite with hot reload. Runs beside `make up`.
make server         # Python capture server alone. Blocks.
make screenshot     # renders scripts/views.txt to captures/ui/. Needs `make dev`.
make design-check   # DESIGN.md's Fulfillment floors in a browser. Machine-wide lock, refuses
                    #   rather than queues. ARGS=--wait queues. BANCHI_SUITE_LOCK=off overrides.
                    #   PW_ARGS=<flags> reaches Playwright. After the run, read `.serve/design-check.json`
                    #   once. Never poll it, never pipe it through `tail`. Not in `make check`.
make design-check-quiet  # the same run, no progress stream, same lock.
make long-sitting   # the 300-capture case alone, about 16 min (BANCHI_LONG_SITTING=1). CI: monthly and on dispatch.
make text-density   # on-demand cut table of screen prose, never a gate. Not in `make check`.
make demo           # seed a demo store and record the wire. Read `docs/specs/demo.md` first.
make demo-seed      # the store alone. Refuses with BANCHI_HOME unset.
make demo-record    # the bundle alone, on a throwaway server and port.
make demo-mirror SOURCE=<checkout>  # owner's Mac only: scrub, crop, commit `demo-assets/mirror/`.
make demo-mirror-agent  # owner's Mac, main tree only: a weekly launchd job that refreshes the mirror
                    #   and auto-merges a mirror-only PR on green CI (D295, the public demo is the scrubbed real store). ARGS=--remove removes it.
make demo-mirror-install  # CI's step: install the committed scrub. No store, no network.
make price-refresh  # ONE free download of the live listings now, over this checkout's store, and the note `#/pricing` shows, then the free daily TCGCSV read (D325 (A daily read of TCGCSV builds)). No price change, and no archive sweep unless ARGS=--sweep asks for one (D224 (sweep preview is free)); the script alone sweeps by default, and this target passes `--no-sweep`.
make price-refresh-agent  # owner's Mac, main tree only: a daily launchd job that runs it and, once per US Central day, the archive sweep (D104 (live fetch is guarded), D224). ARGS=--remove removes it.
make backup         # ONE copy now of photos/ and captures/ plus a store snapshot to the iCloud Drive folder `Banchi backup`. Never overwrites there. ARGS=--verify checks it read-only
                    #   (DEBT67 (capture photographs exist in one place)). `BANCHI_BACKUP_DEST` overrides the folder. Its parent must exist. Never deletes there.
make backup-agent   # owner's Mac, main tree only: a nightly launchd job (`com.banchi.backup`) that runs it. The backup is one-time; the agent is not installed. ARGS=--remove removes it.
make demo-static    # demo-mirror-install, then a static build to dist-demo/.
make demo-preview   # serve dist-demo/ as a static host would.
make check          # the whole suite, product first, guard self-tests last. `make explain` lists it.
make ci-check       # the same list as `check`, from `scripts/checks.py`. CI runs it as six shards, `revert-guard` apart.
make css-var-check  # a `var(--x)` with no fallback and no definition. BANCHI_CSS_VARS=off skips it.
make token-literal-check  # a CSS literal equal to a design token, ratcheted per file. BANCHI_TOKEN_LITERALS=off skips it.
make catalog-refresh  # re-clone pokemon-tcg-data into vendor/. Writes. ARGS=--dry-run.
make catalog-index  # build catalog.sqlite. Gitignored generator.
make catalog-index-selftest  # that builder on a fixture. Not in `make check`.
make catalog-mirror # fills the image mirror (about 16.7 GB). ARGS=--dry-run samples over HTTP HEAD.
./banchi scan     <capture-dir>   # code cards only: read QRs into the ledger. Free.
./banchi identify <capture-dir>   # free read first, then the paid second look for the rest. Costs money. --dry-run first.
                                   #   --engine haiku is the paid read alone.
                                   #   Selection-based: --state, --box, --keys, --game/--section/--since.
./banchi rescue   <run-dir>       # re-address a stranded run by digest. Previews. --write.
./banchi join     <run-dir>       # resolve against the export. Free, re-runnable. --dry-run.
./banchi emit     <run-dir> [<run-dir> ...]  # ONE import.csv across runs and games.
                                   #   No standing cap: every unsent copy goes out unless a send bounds it.
                                   #   --cap N holds a SKU to N copies LIVE. It refuses while a sent copy is
                                   #   pending, so run reconcile --live first. --quantity SKU=N sends N copies.
                                   #   --listed-only sends above-threshold rows only. --split-threshold writes
                                   #   import-listed.csv and import-subthreshold.csv. --split-games writes one file per game.
                                   #   A send whose runs' prices are from an export older than today (US Central)
                                   #   refreshes them first, or stops and says why (D166, the catalog export belongs to the game).
                                   #   --live-guard FILE trims rows so TCGplayer never holds more copies than
                                   #   are here. --reprice-live F adds a price-only row per live card F names.
./banchi match    audit [--write]  # the free reader over every filed card with a photo. Free. Lists disagreements;
                                   # --write queues the in-stock ones for Review (`free_reader_disagrees`), sold ones only listed.
./banchi match    status | prepare [--model-only | --fingerprints-only]  # the free reader's setup. Prepare
                                   # downloads the pinned model file and reads each stock photo once (D301, stock photos
                                   # are hotlinked, never mirrored; this is its one exception). It starts by itself at
                                   # `serve` start and whenever the store holds a card from an unread set (never with the
                                   # runtime missing); the runs sheet's Prepare press is a manual refresh. Env
                                   # `BANCHI_AUTO_SETUP=on` forces auto-start; unset, it is refused when `CI` or
                                   # `BANCHI_HARNESS` is set (`make harness` sets it) and in a linked worktree. `match --sweep` is the background reader's watcher (off until the
                                   # Capture screen's Rig switch is on; never spends; reads even mid-feed).
                                   # `identify --engine marqo-b`
                                   # reads free first, then sends each card it cannot accept to Haiku, held for review.
./banchi cards    name | audit [--verbose] | photos [--write] [--limit N] | identity [--write]
                                   # stable card names. `make cid-audit` runs the audit.
./banchi prices   adopt [--write] | show [--held]  # the price corpus. Adopt folds legacy decisions.json in.
./banchi readings adopt [--write] | show           # the market-reading table. --write fully replaces both tables, and refuses over no source or a malformed pricing.json.
./banchi skus     adopt [--write]                  # the store-owned SKU table. Never a full replace.
./banchi archive  sweep [--write] | show [--sku ID]  # price-history archive. Previews with no network.
./banchi queue    refresh [--export <file.csv>] [--write]  # re-resolve every open queue entry.
./banchi reconcile <run-dir> <staged-export.csv>   # one import against one Export From Staged.
./banchi reconcile --live <my-pricing.csv> [--write]  # the whole store against one live export.
./banchi reconcile --phantoms <my-pricing.csv> [--out F]  # SKUs live beyond what is on hand. Read-only.
./banchi reprice  list <my-pricing.csv> [--days N] [--percent P] [--write]  # unsold listings, proposed re-price.
./banchi reprice  apply <worklist.csv> [--corpus-revision <digest>] [--write]  # `#/pricing` modal.
```

## Folder rules

A rule that governs one folder lives in `.claude/rules/` and loads when a matching file is read: `app.md`
(`app/**`: screens, design system, shell, verifying a screen), `server.md` (`server/**`: concurrency figures),
`pipeline.md` (`pipeline/`, `store/`, `cli/`, `identify/`, `server/`: join, pricing, emit, store, boxes) and
`code-cards.md`. Codex does not read that folder. Each folder holds an `AGENTS.md` link to its rule file, which
Codex loads for a session started there (D135, Codex reads the same rules). The `agent links` row checks them.

## Code cards (dormant feature) — DORMANT

DORMANT means that the owner has not run this feature. No session treats it as active work unless the
owner names it. `codes/`, `#/codes`, harness test T8 and the QR decode stay in the build. This is
the one place that marks the dormancy. `docs/specs/code-cards.md` is the spec. Read it before
you build here. The track's settled decisions, C1 to C11, are sections of that spec.
Its rules are in `.claude/rules/code-cards.md`.

## Things you will get wrong without being told

- **The capture server is threaded. Restart it only after the owner says yes.** Ask the owner before
  `make up ARGS=--restart`, `make down` or `make up`, and name the reason. Run the full suite once, at the end.
  Its concurrency figures and the
  `server concurrency` row of `make docs-audit` are in `.claude/rules/server.md`.
- Only two columns are ever written: `Add to Quantity`, `TCG Marketplace Price`. `TCGplayer Id` is never modified.
- **Batch API, not sequential calls.** Model: `claude-haiku-5-5`.
- **Every checkout has its own store and ports** (D43, the port follows the store). An empty inventory in a
  worktree is correct. A linked checkout claims a port slot once in `~/.banchi/port-slots.json`
  (`scripts/port-slots.py`). A test run refuses a reused dev server that does not name this checkout
  (`app/checkoutIdentity.ts`, D261, a checkout claims its port slot). `make port-agreement` keeps `app/devPort.ts` and `server/ports.py` in step.
- **Real CSV libraries only.** PapaParse (JS), `csv` (Python). Never `split(",")`.
- **Not a Claude artifact.** No `window.storage`, no `facingMode: "environment"`, nothing about a card in `localStorage`.
  **Ten keys are stored on the device**, each a fact about this machine and not a card. `app/src/useCamera.ts`
  holds `banchi.capture.deviceId` and `banchi.capture.rotation`. `app/src/deviceMemory.ts` holds `banchi.theme` (a `THEMES` id: light, dark, abyssal-bloom or carnival-midway),
  `banchi.rail`, `banchi.orders.fetch-filter`, `banchi.inventory.hide-sold`, `banchi.box-recency`,
  `banchi.capture.setup` (six values as one document, D142, the setup outlives the browser) and `banchi.capture.sections` (kept until the sitting
  ends, D164, the undo stack is the sitting). `app/src/Orders.tsx` holds
  `banchi.orders.last-check`.
  `app/eslint.config.js` bans `localStorage` outside `useCamera.ts` and `deviceMemory.ts`.

  `sessionStorage` is a separate store. It holds `banchi.session.captureId`, `banchi.session.homeDeck` (the Home deck already played this sitting) and `banchi.run-scope` (D39, a run's scope is a selection handed off).
  The `storage keys` row of `make docs-audit` reconciles this roster (D27, session state is device-local).
- **The pipeline is reachable from a screen** (D33, reachable from a screen). It lives in Review's runs sheet. A run's scope is a selection
  (D180, a press names the cards): `pipeline/selection.py` is one grammar for the screen, the route and the CLI.

## Hard rules

- **A RULE THAT CAN BE MECHANICALLY ENFORCED MUST BE.** A new rule needs its enforcement before it is done.
  Without one, it carries a bold NOT MECHANIZED line that says what a machine would have to see
  (D173, a rule that can be enforced is).
  The `rule enforcement` row of `make docs-audit` parses every rule here.
  `HARD_RULE_FLOOR` and `PROSE_ONLY_EXPECTED` pin its count.
- **One home per capability, called from everywhere.** Find the home before you build (`make map ARGS=<path>`,
  `scripts/decision-context.py`). Extend it before you build a second. A second needs a written reason.
  The `capability homes` row of `make docs-audit` holds each named capability's home and refuses a call to its
  primitives outside it. **NOT MECHANIZED:** a machine cannot tell that two differently named functions do the same job.
- **A route is not a feature. Nothing is built until a screen reaches it.** Done is the route, a client function in
  `app/src/server.ts` and a control a human would look for. Where it writes, done also needs a receipt and a way back.
  **NOT MECHANIZED:** a machine cannot know which screen a human would look for a capability on.
  The off-nav routes and sheet-only capabilities break a route reconciliation.
- **Never guess an identification, a variant or a price.** Ambiguity goes to the review queue with its photo.
  Never silently drop a card. **NOT MECHANIZED (the guess half):** a machine cannot tell a confident correct
  reading from a guess. The drop half is `harness/tests/t3_join_coverage.py`.
- **Report unmatched rows in both directions before you write output.** `harness/tests/t3_join_coverage.py` enforces it.
- **Scope is argued, not gated.** New surface needs a reason, written into the decision that owns it.
  The `repo map` row of `make docs-audit` fails a file with no map entry.
  Its `decision ids` row fails an id with no entry.
- **Fix the cause, never the symptom. Check whether the primitive exists first.**
  `make map ARGS=<path>` and `scripts/decision-context.py` find it.
  Name a stopgap a stopgap in the commit, with the cause in `docs/debts/`.
  **NOT MECHANIZED:** a machine cannot read whether the author knew the cause and chose the symptom.
- **A settled decision is an argument, not an authority. Think in outcomes.** Cite the entry.
  Name the premise that no longer holds, and how you know (measure it or say "unmeasured").
  Name what it protected, and what protects that now. Propose the fix, and wait for the owner's word.
  Never quietly work around or repeal it. **NOT MECHANIZED:** a machine cannot tell a rotted premise from a live one without judging the outcome it protected.
- **Check whether a task is yours before you hand it to the owner.** Grep the routes, the Commands block and
  `docs/map.py` first. **NOT MECHANIZED:** a machine cannot read a sentence to a person and decide whether
  this repo can already do it.
- **No history date in repo prose.** D308 (no dates in repo prose) allows a deadline date. History is git's. Rewrite a claim in place, and keep only what is true now.
  Old dates go when their file is next rewritten. Never in a sweep. A decision file is a rule, not a log. A change rewrites it.
  Old records are deleted, not archived. See D308 (no dates in repo prose).
  **NOT MECHANIZED:** a machine cannot tell a date from a version number, a port or a test fixture without intent.
- **Opsec.** A live unredeemed code card is a bearer instrument. No code-card photo in a listing, README,
  screenshot or commit. `scripts/githooks/pre-commit` enforces it, armed by `make hooks`.
- **Seven shell mistakes are refused before they run** by `scripts/guard-shell.py --hook` on Bash and Write/Edit (D135, Codex reads the same rules).
  Claude Code sets `GUARD_SHELL_SKIP=checkout,stash,reset` (`--skip` is an alias), because the shared layer's guard owns those three there. Codex runs all seven.
  Each clause fails open on its own bugs. A tool call that sets a real `BANCHI_*=off` is refused as owner-only, with no switch named, unless it is a recovery lever (`BANCHI_KILL`, `BANCHI_SUITE_LOCK`, `BANCHI_SERVE_MAIN`, `BANCHI_SYNC`). Only the owner's terminal and CI set the rest (D042 (main moves by pull request) and D179 (shell mistakes are refused by resolving)). Each has an owner-held escape hatch, never printed to an agent: `BANCHI_CHECKOUT`, `BANCHI_TREE`,
  `BANCHI_WAIT`, `BANCHI_PUSH`, `BANCHI_STASH`, `BANCHI_RESET`, `BANCHI_NARRATE`
  (D235, the heartbeat is refused a pipe). The narrate clause names its subjects, a short per-incident roster
  that the self-test reconciles. The other six resolve what a command would do. `make guard-shell-selftest` proves each one in a throwaway repo.
  A hatch counts only as a real assignment (env prefix, `export` or `env`), never a mention. Every `BANCHI_*=off` a command sets is logged, and `make status` shows the last 24 hours. A hatch set in the environment is not logged, and `make status` lists it under `hatches` (D179, shell mistakes are refused by resolving them).
- **A citation names a symbol, never a line.** Write a decision id, a section or `module.symbol` (no `.py`).
  A method is "`module.Class`'s `method`". A CSS rule is its selector.
  The `line anchors` row of `make docs-audit` refuses `path:N`, `file.ext:N`, `~N` and a bare `:N` after a cited file.
  A record that must quote a line writes it in words.
- **A screen answers to the system.** `--bn-*` tokens only, checked at 1440 and 820, light and dark.
  `docs/DESIGN.md` is the record. The `design tokens` row of `make docs-audit` locks every name and hex both ways.
- **Main moves by pull request. A session never commits to it and never pushes it** (D42, main moves by pull request).
  The batch runner, the session the coordinator starts and tags `cs-build:batch-runner` (claude-settings decision session-tiers), runs merges under the coordinator's standing merge grant and holds none of its own. It batches every reviewed
  lane the owner set out, across all sessions, into one integration branch, waits on its CI, merges it under that grant and
  archives the finished lanes. The coordinator starts lanes and talks with the owner. Any other merge happens only on the
  owner's named act ("merge", not "ship it"), and the batch runner runs it. The coordinator holds the standing merge grant
  (owner, 2026-10-29 16:47 CDT, "for now"; claude-settings decision standing-merge-grant). It merges on green checks and a done review.
  It never asks the owner to merge. The owner withdraws the grant in chat. A lane session never merges. It hands the batch
  runner each reviewed lane branch with its head commit and review verdict. It never builds an integration branch, opens
  an integration PR or marks a PR ready. A session's role comes from its own `cs-build` tag (claude-settings decision session-tiers). A merge uses `make merge ARGS="<n> --confirm"` with CI green, never `--admin`.
  One standing exception (D42, main moves by pull request):
  the weekly demo-mirror script merges its own `demo/mirror-refresh` PR when the whole diff is under `demo-assets/mirror/`.
  GitHub branch protection has 0 reviews and `strict: false`. The one check it is to require is `all-jobs-passed`,
  which rolls up every job, `revert-guard` included (claude-settings decision same-check-kinds). `check` is its
  alias; a follow-up deletes it after the owner flips protection to it (same-check-kinds). The list protection
  holds changes only by that flip.
  It catches the remote half. The local hook is the only cover for a local fast-forward.
  `scripts/githooks/reference-transaction` and `scripts/githooks/pre-push` refuse, armed by `make hooks`.
  `BANCHI_MAIN=off` is the hatch. The primary checkout syncs itself (D176, the primary checkout syncs):
  `scripts/primary_sync.py`, `BANCHI_SYNC=off`, `make sync-selftest`.

## Working agreement

Report format: **Done, Deviations, Input Needed, Next**, in that order (parent CLAUDE.md). Done is one line per item:
**BUILT**, **RECORDED** or **OTHER**, with its PR or commit. "Solved" with no bucket named is refused.
Use bold labels in one quoted block, never a code fence. Start with the point. No task restatement.

- Run `make harness` before you say something works. Give the verdict, never the output.
- Screen work: experience is everything (D307, rulings CLAUDE.md carried). Run a design pass
  before you build. Review the built screen against it before you call it done.
- A lane session runs Opus (claude-settings decision session-tiers). The agents it starts follow `agent-model-cap`:
  Sonnet is the default and the ceiling. Plan, the built-in advisor, the designer, the design reviewer and a builder's
  third try run Opus. Reviewers run Sonnet from round 2; round 1 uses the role's model. Any other Opus agent needs the
  owner's grant. Say an Opus agent in one line first, and raise it only on the owner's grant, in `.claude/settings.local.json`.
- A builder commits and pushes its branch after every pass, even red. Each commit message ends with `Done:` and
  `Next:` lines, so a lane resumes from its branch alone.
- Read `docs/decisions/` before you propose an architecture change (`scripts/decision-context.py` finds the entry,
  `make map ARGS=--decisions` indexes them). Reopen one only by citing it and waiting for the owner's word.
- Design work is repo work. Land it in `docs/specs/` or the decision that owns it in the same session, or declare it abandoned.
- When compacting, keep the fixture schema facts, every `make` command and the modified-file list.

### Writing a brief

- **Name the rendering component and the state that selects it.** Run `make orient ARGS=app/src/Orders.tsx --name CopyMapView`
  before the brief. It prints which component draws it.
- **Never ask an agent to rebuild a state it has left.** Capture a "before" image before the edit, or not at all.
  Wanting a "before" image afterwards is the orchestrator's job, in a separate clean checkout. It is never the
  working agent's, and never in a shared tree. `BANCHI_STASH` refuses a bare stash. **NOT MECHANIZED:** a machine cannot tell that a sentence requires undoing work.
- **State a fence by intent and name the exception.** Example: "Do not change which cards a walk holds. Rendering
  changes inside `WalkView` are in scope." **NOT MECHANIZED:** a machine cannot tell a fence around
  behavior from one around files.
- **Show the screen before you say it looks right.** Render at 1440 and 820, both themes, and look at the images.

## Map

- `docs/map.py` is the repo as data: built, TBD, and the decisions that govern each file. Read it through `make map`.
  Never read it whole. `make docs-audit` fails a file with no entry.
- Build order is `SHIPPED` and `OPEN` (D80, a section with no reader). `n` is a stable id.
- `docs/agent-traps.md` holds the tool and test traps that produced a false green or a lost tree. Read it before a mutation run or a worktree recovery.
- `docs/decisions/` holds settled decisions, one file each. It is never `@`-loaded (D60, the @-loaded docs are dense).
  `scripts/decision-context.py` names the governing ones.
- `docs/GATES.md` points at `docs/gates/`: the harness contract and the build order.
  `make gates-selftest` proves the set is complete.
- `docs/debts/README.md` indexes `docs/debts/`, cited as `DEBT<n>`. Each is a known gap, deliberately unfixed.
  Read one before you treat a green `docs-audit` as coverage.
- `docs/specs/` holds each feature's spec, with its build status in its own headings.
- `docs/DESIGN.md` holds the Fulfillment constraints and the `--bn-*` token block.
- `fixtures/` holds real TCGplayer exports. They are ground truth. Never modify them.

Deeper schema facts live in the `tcgplayer-csv` skill. It loads on demand.
