# BANCHI

Bulk-list pre-sorted TCG singles on TCGplayer with zero attention per card, and know where
every card physically is.

Code cards are a feature of this product, not a second track (D248, turn end never runs the harness, and code cards
share one rules file). The feature is DORMANT (below).
D14 (two tracks, one rig) still stands in structure. `codes/` is its own package. `docs/tracks.json`
carries the track list. `scripts/decision-context.py` prints a track banner. Repeal needs the
owner's word.

Banchi has no Codex setup (D135, no Codex setup). A rule that matters under one folder lives in
`.claude/rules/<topic>.md` with a `paths:` list (see its README). `code-card-fork/CLAUDE.md` links here.
The `fork claude link` row of `make docs-audit` checks the link.

## Banchi names everything (D94, Banchi names everything)

**Banchi** names the app, the GitHub repository `shivinate7/banchi`, the checkout, the CLI `./banchi`,
the env vars `BANCHI_*`, `~/.banchi` and the launchd labels `com.banchi.*`. The old name was
`pkmnscan`. A new `pkmnscan` outside `fixtures/` is a defect. `inventory/store.sqlite` keeps its
name. Fixtures are never modified.

- GitHub Pages follows the repository name. `.github/workflows/demo.yml` derives `DEMO_BASE` from it.
- `~/.pkmnscan` moves to `~/.banchi` once, in `server/ports.machine_dir`. Each launchd `--remove` also (`server/ports.remove_old_agent`)
  removes the old `com.pkmnscan.*` plist.

## Commands

`make help` lists every target. `make help ARGS=<target>` prints that target's whole Makefile comment: its flags, what it
writes, what it costs. `make explain` lists what `make check` runs, and `ARGS=<target>` says what one row is worth.
`./banchi <command> --help` does the same for the CLI. `make map ARGS=<file|area|folder/|--stale>` reads `docs/map/`.
`make map-check` holds `docs/map/`, the plain-English map of the code, in step with the code (config in `map.config.json`).

- **Ask the owner before `make up`, `make down`, `make up ARGS=--restart` or `make restart-now`, and name the reason.**
  The capture server is threaded and holds the owner's live store (`.claude/rules/server.md`).
- `BANCHI_SERVE_SCOPE=all` and `BANCHI_GUARD_SCOPE=all` run every path-gated self-test (run-everything, not a hatch). `BANCHI_CSS_VARS=off`
  and `BANCHI_TOKEN_LITERALS=off` skip `make css-var-check` and `make token-literal-check`: owner-only.
- `./banchi identify` costs money: `--dry-run` first. Kill only your own processes: `make reap` stops what this session started
  and previews first (parent `shared-trees-no-machine-wide-kill`). Each launchd agent target is for the owner's Mac, main tree only.

## Code cards (dormant feature) — DORMANT

DORMANT means that the owner has not run this feature. No session treats it as active work unless the
owner names it. `codes/`, `#/codes`, harness test T8 and the QR decode stay in the build. This is
the one place that marks the dormancy. `docs/specs/code-cards.md` is the spec; the rules are in `.claude/rules/code-cards.md`.

## Folder rules and whole-repo facts

Folder rules load when you read under that folder: `app/` (screens, design system, browser storage), `server/`, `pipeline/`,
`cli/` and `identify/` (join, pricing, emit, the paid read), `store/`, and `codes/` with `code-card-fork/`. These hold for the
whole repo:

- **Every checkout has its own store and ports** (D43, the port follows the store). An empty inventory in a
  worktree is correct. A linked checkout claims a port slot once in `~/.banchi/port-slots.json`
  (`scripts/port-slots.py`). A test run refuses a reused dev server that does not name this checkout
  (`app/checkoutIdentity.ts`, D261, a checkout claims its port slot). `make port-agreement` keeps `app/devPort.ts` and `server/ports.py` in step.
- **A burst of clients kills the capture server. Run the full suite once, at the end.**
- **The pipeline is reachable from a screen** (D33, reachable from a screen). It lives in Review's runs sheet. A run's scope is a selection
  (D180, a press names the cards): `pipeline/selection.py` is one grammar for the screen, the route and the CLI.
- **Real CSV libraries only.** PapaParse (JS), `csv` (Python). Never `split(",")`. `fixtures/` holds real TCGplayer exports,
  ground truth. Never modify them. Deeper schema facts live in the `tcgplayer-csv` skill.
- **`make harness` runs all ten verification tests**, T1-T9 and T11. No T10. Run it before you say something works.

## Hard rules

- **Parent rule `outcomes-mechanize-rules` (rules become checks) applies.**
  Without a check, a rule carries a bold NOT MECHANIZED line that says what a machine would have to see
  (D173, a rule that can be enforced is).
  The `rule enforcement` row of `make docs-audit` parses every rule here.
  `HARD_RULE_FLOOR` and `PROSE_ONLY_EXPECTED` pin its count.
- **Parent rule `building-one-home-per-capability` (single home) applies.** `make map ARGS=<path>` and `scripts/decision-context.py` find the home.
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
  `make map-check` fails a tracked code file under `map.config.json`'s `mapPaths` with no `docs/map/` line.
  The `decision ids` row of `make docs-audit` fails an id with no entry.
- **Parent rule `building-fix-cause-not-symptom` (root cause first) applies.** `make map ARGS=<path>` and `scripts/decision-context.py` find an existing primitive.
  A stopgap's commit says so, and its cause goes in `docs/debts/`.
  **NOT MECHANIZED:** a machine cannot read whether the author knew the cause and chose the symptom.
- **A settled decision is an argument, not an authority.** Parent rules `outcomes-decision-is-argument` (recorded decisions) and `outcomes-stale-decision-protocol` (stale decisions) apply. Cite the entry.
  **NOT MECHANIZED:** a machine cannot tell a rotted premise from a live one without judging the outcome it protected.
- **Check whether a task is yours before you hand it to the owner.** Grep the routes, `make help` and
  `docs/map/` first. **NOT MECHANIZED:** a machine cannot read a sentence to a person and decide whether
  this repo can already do it.
- **No history date in repo prose.** D308 (no dates in repo prose) allows a deadline date. Parent rule `speak-rewrite-superseded-in-place` (superseded text) applies.
  Old dates go when their file is next rewritten, never in a sweep. Old records are deleted, not archived.
  **NOT MECHANIZED:** a machine cannot tell a date from a version number, a port or a test fixture without intent.
- **Opsec.** A live unredeemed code card is a bearer instrument. No code-card photo or real code string in a listing, README,
  screenshot, commit or any tracked file. The gitignored `inventory/` is the sanctioned place.
  `scripts/githooks/pre-commit` enforces it, armed by `make hooks`.
- **Four shell mistakes are refused before they run** by `scripts/guard-shell.py --hook` on Bash and Write/Edit.
  Claude Code runs every clause.
  The shared layer's guard owns the checkout, stash and reset refusals, so those clauses are gone from this script.
  Each clause fails open on its own bugs. A tool call that sets a real `BANCHI_*=off` is refused as owner-only, with no switch named, unless it is a recovery lever (`BANCHI_SUITE_LOCK`, `BANCHI_SERVE_MAIN`, `BANCHI_SYNC`). Only the owner's terminal and CI set the rest (D42 (main moves by pull request) and D179 (shell mistakes are refused by resolving)). Each has an owner-held escape hatch, never printed to an agent: `BANCHI_TREE`,
  `BANCHI_WAIT`, `BANCHI_PUSH`, `BANCHI_NARRATE`
  (D235, the heartbeat is refused a pipe). The narrate clause names its subjects, a short per-incident roster
  that the self-test reconciles. The other three resolve what a command would do. `make guard-shell-selftest` proves each one in a throwaway repo.
  A hatch counts only as a real assignment (env prefix, `export` or `env`), never a mention. Every `BANCHI_*=off` a command sets is logged, and `make status` shows the last 24 hours. A hatch set in the environment is not logged, and `make status` lists it under `hatches` (D179, shell mistakes are refused by resolving them).
- **A citation names a symbol, never a line.** Write a decision id, a section or `module.symbol` (no `.py`).
  A method is "`module.Class`'s `method`". A CSS rule is its selector.
  The `line anchors` row of `make docs-audit` refuses `path:N`, `file.ext:N`, `~N` and a bare `:N` after a cited file.
  A record that must quote a line writes it in words.
- **A screen answers to the system.** `--bn-*` tokens only, checked at 1440 and 820, light and dark.
  `docs/DESIGN.md` is the record. The `design tokens` row of `make docs-audit` locks every name and hex both ways.
- **Main moves by pull request. A session never commits to main or pushes it** (D42, main moves by pull request).
  Parent rules `git-main-only-by-pr` (merge by pull request) and `git-integration-branch-merge` (lane batching) apply.
  Parent decision `standing-merge-grant` says who merges: a batch runner, under the coordinator's grant. The coordinator never merges.
  A one-lane session the owner started may merge its own lone lane, only under that repo's merge grant or the owner's named act,
  under the same limits. A lane session a coordinator started never merges: it hands the batch runner each reviewed lane branch.
  Parent decision `session-tiers` holds the `cs-build` tags and the lane hand-off.
  Any other merge is the owner's named act, "merge" and not "ship it". Use `make merge ARGS="<n> --confirm"`, never `--admin`.
  One standing exception (D42, main moves by pull request):
  the weekly demo-mirror script merges its own `demo/mirror-refresh` PR when the whole diff is under `demo-assets/mirror/`.
  GitHub branch protection has 0 reviews and `strict: false`. The one check it is to require is `all-jobs-passed`,
  which rolls up every job, `revert-guard` included (claude-settings decision `same-check-kinds`, one rollup check per repo). Protection holds that one check and no other.
  It catches the remote half. The local hook is the only cover for a local fast-forward.
  `scripts/githooks/reference-transaction` and `scripts/githooks/pre-push` refuse, armed by `make hooks`.
  `BANCHI_MAIN=off` is the hatch. The primary checkout syncs itself (D176, the primary checkout syncs):
  `scripts/primary_sync.py`, `BANCHI_SYNC=off`, `make sync-selftest`.

## Working agreement

Report labels, done items and layout: parent rules `reports-order-of-labels` (label order) and `reports-done-format` (one bucket per item),
and shiv-stylisms `reports-blockquote-no-fence` (report shape). No task restatement.

- Run `make harness` before you say something works, through `verdict` (parent rule `tokens-run-through-verdict`, verdict logging).
- Screen work: experience is everything (D307, rulings CLAUDE.md carried). Parent rule `roles-one-role-per-agent` (designer and design reviewer) applies.
- Model caps: parent records `agent-model-cap` (agent models) and `session-tiers` (lane tiers). Parent rules `roles-sonnet-is-the-ceiling` (Opus only on grant) and `roles-opus-shaped-say-so` (one-line notice) apply. An owner's Opus grant goes in `.claude/settings.local.json`.
- A builder commits and pushes its branch after every pass, even red. Each commit message ends with `Done:` and
  `Next:` lines, so a lane resumes from its branch alone.
- Read `docs/decisions/` before you propose an architecture change (`scripts/decision-context.py` finds the entry,
  `ls docs/decisions/` lists them). Reopening one follows parent rule `outcomes-stale-decision-protocol` (stale decisions).
- Parent rule `building-land-design-or-abandon` (land it or drop it) applies. Its homes here: `docs/specs/`, or the decision that owns it.
- The waiting page's writer copies the page's data to `waiting/` on the record branch at each wake and before
  any republish, with the shared skill `waiting-page` (D327, the waiting page is a committed record; parent record
  `waiting-data-in-repo`, waiting data copies).
- Parent rule `tokens-compacting-keep-essentials` (what a compaction keeps) applies. Also keep the fixture schema facts.

### Writing a brief

- **Name the rendering component and the state that selects it.** Parent rule `roles-brief-contents` (a brief's contents) applies.
  Run `make orient ARGS=app/src/Orders.tsx --name CopyMapView` before the brief. It prints which component draws it.
- **Never ask an agent to rebuild a state it has left.** Capture a "before" image before the edit, or not at all.
  A "before" image taken afterwards is the orchestrator's job, in a separate clean checkout (parent rule `shared-trees-one-checkout-per-agent`, one checkout per agent).
  The shared layer's guard refuses a bare stash. **NOT MECHANIZED:** a machine cannot tell that a sentence requires undoing work.
- **State a fence by intent and name the exception.** Example: "Do not change which cards a walk holds. Rendering
  changes inside `WalkView` are in scope." **NOT MECHANIZED:** a machine cannot tell a fence around
  behavior from one around files.
- **Show the screen before you say it looks right.** Parent rule `verification-screens-verdict` (screen verdict) applies. Render at 1440 and 820, both themes, and look at the images.

## Map

- `docs/map/` is the plain-English map of the code: one file per area, one line per code file, a trace page per
  screen. Read it before you answer how code works. `make map-check` holds it in sync with the code; the
  `plain-english-map` skill says how to change it. `map.config.json` holds its repository settings.
- A decisions line under a map line names the decisions that govern the file, and `scripts/decision-context.py` reads it. `make map ARGS=<path>` prints a file's map line
  (parent rule `tokens-never-load-whole-doc`, read in sections). `make map-fix` adds the ids a file's comments cite.
- Build order is `docs/gates/ORDER.json`'s `steps.shipped` and `steps.open` (D80, a section with no reader). `n` is a stable id.
- `docs/agent-traps.md` holds the tool and test traps that produced a false green or a lost tree. Read it before a mutation run or a worktree recovery.
- `docs/decisions/` holds settled decisions, one file each (parent rule `git-record-own-file-per-kind`, own file per record). It is never `@`-loaded (D60, the @-loaded docs are dense).
  `scripts/decision-context.py` names the governing ones.
- `docs/GATES.md` points at `docs/gates/`: the harness contract and the build order.
  `make gates-selftest` proves the set is complete.
- `docs/debts/README.md` indexes `docs/debts/`, cited as `DEBT<n>`. Each is a known gap, deliberately unfixed.
  Read one before you treat a green `docs-audit` as coverage.
- `docs/specs/` holds each feature's spec, with its build status in its own headings.
- `docs/DESIGN.md` holds the Fulfillment constraints and the `--bn-*` token block.
