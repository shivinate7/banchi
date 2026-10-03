# BANCHI

Bulk-list pre-sorted TCG singles on TCGplayer with zero attention per card, and know where
every card physically is.

Code cards are a feature of this product, not a second track (D248, turn end never runs the harness, and code cards
share one rules file). The feature is DORMANT. See "Code cards (dormant feature)" below.
D14 (two tracks, one rig) still stands in structure. `codes/` is its own package. `docs/map.py`
carries a `TRACKS` tuple. `scripts/decision-context.py` prints a track banner. Repeal needs the
owner's word.

Codex reads this file, not a copy (D135, Codex reads the same rules). `AGENTS.md`,
`code-card-fork/AGENTS.md` and `code-card-fork/CLAUDE.md` are relative symlinks to it.
`.agents/skills` links to `.claude/skills`. `.codex/hooks.json` mirrors `.claude/settings.json`.
The `agent links` and `codex hooks` rows of `make docs-audit` check both.

## The name is the app's, and nothing beneath it (D94, Banchi is the product's name)

**Banchi** names the web app under `app/`. Everything beneath it keeps its old name. That
covers the checkout (`~/Developer/pkmnscan`), the CLI `./pkmnscan`, the Python packages
(`server/ store/ pipeline/ identify/ geometry/ codes/ cli/`) and `inventory/store.sqlite`.
It also covers `PKMNSCAN_HOME`, every wire route, `PKMNSCAN_MAIN=off`, the harness, the
fixtures, `docs/` and `make`. Renaming any of these is a defect.

- The GitHub repository is `shivinate7/banchi`. The local directory stays `pkmnscan`. The two disagree on purpose.
- GitHub Pages follows the repository name. `.github/workflows/demo.yml` derives `DEMO_BASE` from it.
- The front-end rename reaches `app/index.html`, the brand block in `app/src/App.tsx`, the document
  title, `banchi.*` keys and on-screen copy. It reaches nothing on the wire.
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
                    #   PKMNSCAN_SERVE_SCOPE=all runs it anyway (run-everything, not a hatch).
make guard-scope    # second path gate, read by each gated self-test. ARGS=list | classify.
make orient         # ARGS=<file.tsx> [--name <C>]: which component draws it. Run before briefing a screen.
make map-fix        # adds a file's cited decision ids to docs/map.py. Previews. ARGS=--write.
make offenders-prune # deletes stale offender-list entries only. Previews. ARGS=--write.
make harness        # all ten verification tests, T1-T9 and T11. No T10.
make up             # the server, detached, one process. ARGS=--restart bounces it. `make down` stops it.
                    #   Refuses on a primary checkout off main. PKMNSCAN_SERVE_MAIN=off overrides.
make reap           # stop what THIS session started, nothing else. Previews. ARGS="--confirm",
                    #   "port:N --confirm", "match:X --confirm" or "pid:N --confirm". A subagent's bare
                    #   --confirm stops only its own session's pids (D305, the reaper stops only its own).
make janitor-install # retired: claude-settings' install.sh owns the user's Claude bin directory. Copies nothing.
make merge          # claude-settings' shared merge tool (D140, merge claims the decision number), config in
                    #   `.github/stamp.json`. ARGS=<n> previews. ARGS="<n> --confirm" merges, and claims record
                    #   numbers first. The owner names the session an Orchestrator first, per turn. It runs
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
                    #   rather than queues. ARGS=--wait queues. PKMNSCAN_SUITE_LOCK=off overrides.
                    #   PW_ARGS=<flags> reaches Playwright. After the run, read `.serve/design-check.json`
                    #   once. Never poll it, never pipe it through `tail`. Not in `make check`.
make design-check-quiet  # the same run, no progress stream, same lock.
make text-density   # on-demand cut table of screen prose, never a gate. Not in `make check`.
make demo           # seed a demo store and record the wire. Read `docs/specs/demo.md` first.
make demo-seed      # the store alone. Refuses with PKMNSCAN_HOME unset.
make demo-record    # the bundle alone, on a throwaway server and port.
make demo-mirror SOURCE=<checkout>  # owner's Mac only: scrub, crop, commit `demo-assets/mirror/`.
make demo-mirror-agent  # owner's Mac, main tree only: a daily launchd job that refreshes the mirror
                    #   and auto-merges a mirror-only PR on green CI (D295, the public demo is the scrubbed real store). ARGS=--remove removes it.
make demo-mirror-install  # CI's step: install the committed scrub. No store, no network.
make price-refresh  # ONE free download of the live listings now, over this checkout's store, and the note `#/pricing` shows. No sweep, no price change.
make price-refresh-agent  # owner's Mac, main tree only: a daily launchd job that runs it (D104 (live fetch is guarded)). ARGS=--remove removes it.
make demo-static    # demo-mirror-install, then a static build to dist-demo/.
make demo-preview   # serve dist-demo/ as a static host would.
make check          # the whole suite, product first, guard self-tests last. `make explain` lists it.
make ci-check       # the same list as `check`, from `scripts/checks.py`. CI runs it as four shards, `revert-guard` apart.
make css-var-check  # a `var(--x)` with no fallback and no definition. PKMNSCAN_CSS_VARS=off skips it.
make token-literal-check  # a CSS literal equal to a design token, ratcheted per file. PKMNSCAN_TOKEN_LITERALS=off skips it.
make catalog-refresh  # re-clone pokemon-tcg-data into vendor/. Writes. ARGS=--dry-run.
make catalog-index  # build catalog.sqlite. Gitignored generator.
make catalog-index-selftest  # that builder on a fixture. Not in `make check`.
make catalog-mirror # dry run only. ARGS=--dry-run samples over HTTP HEAD.
./pkmnscan scan     <capture-dir>   # code cards only: read QRs into the ledger. Free.
./pkmnscan identify <capture-dir>   # submit, wait, collect, cache. Costs money. --dry-run first.
                                   #   Selection-based: --state, --box, --keys, --game/--section/--since.
./pkmnscan rescue   <run-dir>       # re-address a stranded run by digest. Previews. --write.
./pkmnscan join     <run-dir>       # resolve against the export. Free, re-runnable. --dry-run.
./pkmnscan emit     <run-dir> [<run-dir> ...]  # ONE import.csv across runs and games.
                                   #   No standing cap: every unsent copy goes out unless a send bounds it.
                                   #   --cap N holds a SKU to N copies LIVE. It refuses while a sent copy is
                                   #   pending, so run reconcile --live first. --quantity SKU=N sends N copies.
                                   #   --listed-only sends above-threshold rows only. --split-threshold writes
                                   #   import-listed.csv and import-subthreshold.csv. --split-games writes one file per game.
                                   #   --live-guard FILE trims rows so TCGplayer never holds more copies than
                                   #   are here. --reprice-live F adds a price-only row per live card F names.
./pkmnscan match    status | prepare [--model-only | --fingerprints-only]  # the free reader's setup. Prepare
                                   # downloads the pinned model file and reads each stock photo once (D301, stock photos
                                   # are hotlinked, never mirrored; this is its one exception). Nothing starts it but the
                                   # owner's press. `identify --engine marqo-b`
                                   # reads free first, then sends each card it cannot accept to Haiku, held for review.
./pkmnscan cards    name | audit [--verbose] | photos [--write] [--limit N] | identity [--write]
                                   # stable card names. `make cid-audit` runs the audit.
./pkmnscan prices   adopt [--write] | show [--held]  # the price corpus. Adopt folds legacy decisions.json in.
./pkmnscan readings adopt [--write] | show           # the market-reading table. --write fully replaces both tables.
./pkmnscan skus     adopt [--write]                  # the store-owned SKU table. Never a full replace.
./pkmnscan archive  sweep [--write] | show [--sku ID]  # price-history archive. Previews with no network.
./pkmnscan queue    refresh [--export <file.csv>] [--write]  # re-resolve every open queue entry.
./pkmnscan reconcile <run-dir> <staged-export.csv>   # one import against one Export From Staged.
./pkmnscan reconcile --live <my-pricing.csv> [--write]  # the whole store against one live export.
./pkmnscan reconcile --phantoms <my-pricing.csv> [--out F]  # SKUs live beyond what is on hand. Read-only.
./pkmnscan reprice  list <my-pricing.csv> [--days N] [--percent P] [--write]  # unsold listings, proposed re-price.
./pkmnscan reprice  apply <worklist.csv> [--corpus-revision <digest>] [--write]  # `#/pricing` modal.
```

## The front end

Vite + React 19 + TypeScript over the capture server and nothing else. No pipeline logic in the
browser. No second store. No auth. `app/src/server.ts` is the only client-call file.
`app/src/types.ts` is the only wire-shape file.

### The screens

`ROUTES` in `app/src/App.tsx` is the one table of screens. Read counts and the off-nav set from it,
never from prose. The `route rosters` row of `make docs-audit` reconciles README's route table with
it. `#/fulfillment` is the Fulfiller's whole product, with no shell (D5, two personas).

- **A new screen is one `ROUTES` entry plus a view that returns `<Page>`** (D275, every screen inherits
  the page scaffold). `make kit-adoption` fails a view that skips `<Page>` or hand-rolls a kit
  primitive. `app/tests/scaffold.spec.ts` asserts the frame at 1440, 820, 720 and 390. Exceptions
  live in `scripts/kit-adoption-allow.json`, a list that only shrinks. A lane that moves a
  screen onto `Page` deletes its entries in the same commit.
- `#/orders` and `#/shipping` are two stages of one screen (`OrdersHub`), joined client-side on order number.
- `#/inventory` is the one owner-side view of stored cards (D31, one owner-side view). `#/boxes` and `#/pull` are not routes.
  Sold cards are hidden by default (D132, sold is folded away). Order under a search is frozen once taken, and a sale
  may not re-rank it (D181, the order is taken once).
- `#/runs` is off-nav and opens Review's runs sheet (D291, the fold).
- `#/product` is off-nav and deep-linked by SKU (D227, a route not a lens).
- `#/revenue` is a nav row on purpose (D214, gross-revenue retrospective). It is gross only, leaves out canceled orders and never claims profit.

### The design system

`app/src/tokens.css` is the only file in `app/` that names a color. `app/src/kit/markPalettes.ts`
is the one exception (D102, mark palette). It is generated, never hand-edited. Every token is `--bn-*`.
The legacy aliases at the foot of tokens.css are dead. A new rule may not read one.

- **Both themes are real.** A screen not looked at in dark is not verified. The `raw color` row of `make docs-audit` reads for hex literals.
- **Type has three roles.** `--bn-font-display` (Manrope, headings), `--bn-font-ui` (Inter),
  `--bn-font-mono` (JetBrains Mono, machine strings only: SKUs, run names, reason codes, key caps,
  card numbers). Tables use Inter tabular-nums. Money uses `.bn-money` (D221, money stays mono), asserted by
  `app/tests/text-checks.spec.ts`. Body is 14px.
- **The kit is `app/src/kit/` and `app/src/kit.css`.** `#/gallery` renders it. Reach for the kit before
  you write a primitive.
- **Register.** Sentences on screen, not machine strings. Enum values are labeled. An empty state is a
  sentence and one action. No user-visible string names a decision, a path or a pipeline noun (D196, no user-visible string may name a decision).
  The `no mechanism on screen` row of `make docs-audit` enforces it.
- **No typed middle dot or bullet (U+00B7, U+2022) in a user-visible string** (D218, a typed dot is a defect).
  CSS draws the separator. The `typed interpunct` row of `make docs-audit` enforces it, with a shrinking list (D280, lists of offenders).
- **Text shape is three checks, none a count** (D284, three checks replace one ceiling):
  all in `app/tests/text-checks.spec.ts`, one sweep. Each reads
  a shrinking allow list in `app/tests/`, keyed to the finding.
- **The mark is generated** (D102, the mark has its own palette). `scripts/build-mark.mjs` writes it. Never put a `border-radius` on it.
- **`base.css` sets four floors** (D50, feedback is the product's; D118, a press changes what is on screen):
  cursor, response, press and stability. `app/tests/cursor.spec.ts` and `app/tests/inventory.spec.ts` assert them.
- **Nothing on screen moves unless the person moved it** (D313 (Nothing on screen moves unless the)). A loading area holds its
  loaded size from the first paint, by construction and never by a tuned pixel. `app/tests/stability.spec.ts`
  asserts it, one row per case, over every nav screen read from `ROUTES`, plus the Fulfiller's.
- **One left edge, and only width varies** (D197, a page is anchored to the shell inset). `.bn-page` margin is `0`.
  `app/tests/page-edge.spec.ts` asserts it.
- **Same-role stacked buttons share a width** (D195, same-role buttons share a width). `app/tests/button-stack.spec.ts` asserts it.
- **Three silent motion rules.** A component's own `transition` replaces the floor's, so name every animated
  property. `background-image` cannot animate, so use an inset `box-shadow`. The press dip is `translate`.
  A screen's own emphasis is `transform: scale()`, never `translateY`. A control may not ease its own `:active` movement.
- **Motion is tokens.** Durations and easing are tokens. List rows stagger off `--bn-stagger`.
  `prefers-reduced-motion` is honored. Only loops that carry meaning keep turning.

### The shell

`App.tsx` is a hand-written hash router and the shell. It renders for every screen except the
Fulfiller's. The shell has these parts:

- A sidebar that folds to a rail (⌘.), a top bar and bottom tab bar on phones.
- A command palette (⌘K, the only way to `#/gallery`), `,` then a letter to jump, ⌘←/⌘→ to step the workflow ring.
- A keyboard sheet on `?`. A new key binding is not done until it is in `SHORTCUTS` (`app/src/keys.ts`).
- An error boundary per route. The Fulfiller's `plain` variant offers one button and no error text.
- A toast stack, an offline banner and the document title.

### Verifying a screen

- `cd app && npx tsc --noEmit` prints nothing.
- Look at it at 1440 and 820, in both themes. Look at 390 only on an owner phone report.
  The specs that assert phone layout are off by the owner's word: DEBT77 (every phone-width spec is off). One switch turns them back on:
  `PHONE_SPECS_ON` in `app/tests/phoneSwitch.ts`.
- Anything a thumb presses is 40px or more.
- `make design-check` asserts `docs/DESIGN.md`'s Fulfillment floors in a real browser.

## Code cards (dormant feature) — DORMANT

DORMANT means that the owner has not run this feature. No session treats it as active work unless the
owner names it. `codes/`, `#/codes`, harness test T8 and the QR decode stay in the build. This is
the one place that marks the dormancy. `docs/specs/code-cards.md` is the spec. Read it before
you build here. The track's settled decisions, C1 to C11, are sections of that spec.

- Never guess a code. No decode goes to the paid vision read, then a human.
- A QR that does not decode is a stop.
- Separate non-`BST` codes on sight. They are the scarce ones.
- No real code-card photo or code string in any tracked file. The pre-commit hook enforces it. The
  gitignored `inventory/` is the sanctioned place.

## Things you will get wrong without being told

- **The capture server is threaded and not yours to restart.** It is `class CaptureServer(ThreadingHTTPServer)` in
  `server/capture_server.py`, with `request_queue_size = 128` and `CaptureHandler.timeout = 15`.
  `REQUEST_SLOTS = 4` bounds executing requests. `PHOTO_SLOTS = 4` bounds `/photo/` and `/assets/`
  GETs and the cheap lock-free reads in `PHOTO_LANE_EXACT`, `/status` first (refusal `photo_busy`). The pool is safe over HTTP/1.1 only because every response sends
  `Connection: close` (DEBT11, a parked writer still holds a request slot). A burst of clients kills it. Run the full
  suite once, at the end. Never `make up ARGS=--restart`, `make down` or `make up` to fix a wedge.
  The `server concurrency` row of `make docs-audit` reads these figures.
- **The join key is per game and normalized on both sides** (`pipeline/games.py`,
  `pipeline/join.py:number_index_key`). Never join on Product Name. D35 (Product Name join) allows it only as a last
  resort, queued for review. `zfill` is composition only, never matching.
- **A run's slot numbers are not the truth. The photograph is** (D36, the store says which slot).
  `cli/resolve.py:realign` re-binds records. It refuses on ambiguity and on a reallocated box.
- Only two columns are ever written: `Add to Quantity`, `TCG Marketplace Price`. `TCGplayer Id` is never modified.
- **Batch API, not sequential calls.** Model: `claude-haiku-4-5-20251001`.
- **Every checkout has its own store and ports** (D43, the port follows the store). An empty inventory in a
  worktree is correct. A linked checkout claims a port slot once in `~/.pkmnscan/port-slots.json`
  (`scripts/port-slots.py`). A test run refuses a reused dev server that does not name this checkout
  (`app/checkoutIdentity.ts`, D261, a checkout claims its port slot). `make port-agreement` keeps `app/devPort.ts` and `server/ports.py` in step.
- **Real CSV libraries only.** PapaParse (JS), `csv` (Python). Never `split(",")`.
- **Not a Claude artifact.** No `window.storage`, no `facingMode: "environment"`, nothing about a card in `localStorage`.
  **Eleven keys are stored on the device**, each a fact about this machine and not a card. `app/src/useCamera.ts`
  holds `banchi.capture.deviceId` and `banchi.capture.rotation`. `app/src/deviceMemory.ts` holds `banchi.theme` (a `THEMES` id: light, dark, abyssal-bloom or carnival-midway),
  `banchi.rail`, `banchi.orders.fetch-filter`, `banchi.inventory.hide-sold`, `banchi.box-recency`,
  `banchi.capture.setup` (six values as one document, D142, the setup outlives the browser), `banchi.capture.sections` (kept until the sitting
  ends, D164, the undo stack is the sitting) and `banchi.runs.spend-notice` (a notice, never a cap, D180, a press names the cards). `app/src/Orders.tsx` holds
  `banchi.orders.last-check`.
  `app/eslint.config.js` bans `localStorage` outside `useCamera.ts` and `deviceMemory.ts`.

  `sessionStorage` is a separate store. It holds `banchi.session.captureId`, `banchi.session.homeDeck` (the Home deck already played this sitting) and `banchi.run-scope` (D39, a run's scope is a selection handed off).
  The `storage keys` row of `make docs-audit` reconciles this roster (D27, session state is device-local).
- **No duplicate SKU rows in an import file.** Aggregate by SKU. `Add to Quantity` equals the copy count. There is no standing
  cap (D7, duplicates aggregate by SKU). A send may ask for one (`emit --cap N`) or for a quantity (`emit --quantity SKU=N`).
  `uncommitted_positions` stops a copy going out twice.
- **The pipeline is reachable from a screen** (D33, reachable from a screen). It lives in Review's runs sheet. A run's scope is a selection
  (D180, a press names the cards): `pipeline/selection.py` is one grammar for the screen, the route and the CLI.
- **A card's number counts the cards in the box, not the slots** (D58, a card's number counts the cards). The stored index never moves. A departed card
  renders `pipeline/join.departed_label`.
- **A set hint on some cards narrows nothing** (D76, how wide to ask is per game). Widening needs every card hinted and
  every hint resolved. A Pokemon run that would widen is refused (`export_needs_hint` in `pipeline/games.py`, D170, a Pokemon run names its sets)
  unless the operator named `set_ids` or `scope`. A widening is never silent: every fetch carries a `width` block.
  Fix an unhinted card in Manage box, under Set claims.
- **The catalog export belongs to the game, not the drawer** (D166, the catalog export is a property of the game). It lands in `inventory/.exports/<game>/`.
  A covering export under 900s old is reused. `refresh: true` forces a new one.
- **The pricing answer is one file, keyed by SKU** (D86, one file for the store): `pipeline/corpus.py` over
  `inventory/prices.json`. `policy.threshold` is also the floor. `sub_threshold` defaults to $0.49 (D9, threshold and floor).
  `pkmnscan prices adopt` migrates legacy run files. `join` and `emit` refuse over an unadopted one.
- **The store of record is one SQLite file** (D88, SQLite and one transaction per write). `inventory.json` is
  legacy and read by nothing.
- **A sold card's photograph is reclaimed on purpose** (D89, reclaimed on purpose): `POST /boxes/<box>/photos/reclaim` deletes sold
  photographs and keeps every record.
- **`emit` over several runs writes one file, and a cap is spent once** (D86, one pricing file for the store; `pipeline/join.py:add_to_quantity`).
  `#/pricing` lands on every unsent copy in the store (D156, one worklist), read live.
- **No automatic sectioning** (D10, inventory model). A divider is put in with `S` on the capture screen
  (`store/master.py:open_section`, inside the store lock).
- **A box is addressed by name, and names are unique** (D20, a box is an object). `Box.bid` is a never-reused
  index drawn on no screen (D145, a box has an index nobody sees). A run records `bid`, never the name (D56, a run names the drawer).

## Hard rules

- **A RULE THAT CAN BE MECHANICALLY ENFORCED MUST BE.** A new rule needs its enforcement before it is done.
  Without one, it carries a bold NOT MECHANIZED line that says what a machine would have to see
  (D173, a rule that can be enforced is).
  The `rule enforcement` row of `make docs-audit` parses every rule here.
  `HARD_RULE_FLOOR` and `PROSE_ONLY_EXPECTED` pin its count.
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
- **No date in repo prose.** History is git's. Rewrite a claim in place, and keep only what is true now.
  Old dates go when their file is next rewritten. Never in a sweep. A decision file is a rule, not a log. A change rewrites it.
  Old records are deleted, not archived. See D308 (no dates in repo prose).
  **NOT MECHANIZED:** a machine cannot tell a date from a version number, a port or a test fixture without intent.
- **Opsec.** A live unredeemed code card is a bearer instrument. No code-card photo in a listing, README,
  screenshot or commit. `scripts/githooks/pre-commit` enforces it, armed by `make hooks`.
- **Seven shell mistakes are refused before they run** by `scripts/guard-shell.py --hook` on Bash and Write/Edit (D135, Codex reads the same rules).
  Claude Code sets `GUARD_SHELL_SKIP=checkout,stash,reset` (`--skip` is an alias), because the shared layer's guard owns those three there. Codex runs all seven.
  Each clause fails open on its own bugs. A tool call that sets a real `PKMNSCAN_*=off` is refused as owner-only, with no switch named, unless it is a recovery lever (`PKMNSCAN_KILL`, `PKMNSCAN_SUITE_LOCK`, `PKMNSCAN_SERVE_MAIN`, `PKMNSCAN_SYNC`). Only the owner's terminal and CI set the rest (D042 (main moves by pull request) and D179 (shell mistakes are refused by resolving)). Each has an owner-held escape hatch, never printed to an agent: `PKMNSCAN_CHECKOUT`, `PKMNSCAN_TREE`,
  `PKMNSCAN_WAIT`, `PKMNSCAN_PUSH`, `PKMNSCAN_STASH`, `PKMNSCAN_RESET`, `PKMNSCAN_NARRATE`
  (D235, the heartbeat is refused a pipe). The narrate clause names its subjects, a short per-incident roster
  that the self-test reconciles. The other six resolve what a command would do. `make guard-shell-selftest` proves each one in a throwaway repo.
  A hatch counts only as a real assignment (env prefix, `export` or `env`), never a mention. Every `PKMNSCAN_*=off` a command sets is logged, and `make status` shows the last 24 hours. A hatch set in the environment is not logged, and `make status` lists it under `hatches` (D179, shell mistakes are refused by resolving them).
- **A citation names a symbol, never a line.** Write a decision id, a section or `module.symbol` (no `.py`).
  A method is "`module.Class`'s `method`". A CSS rule is its selector.
  The `line anchors` row of `make docs-audit` refuses `path:N`, `file.ext:N`, `~N` and a bare `:N` after a cited file.
  A record that must quote a line writes it in words.
- **A screen answers to the system.** `--bn-*` tokens only, checked at 1440 and 820, light and dark.
  `docs/DESIGN.md` is the record. The `design tokens` row of `make docs-audit` locks every name and hex both ways.
- **Main moves by pull request. A session never commits to it and never pushes it** (D42, main moves by pull request).
  A session merges only after the owner names the act ("merge", not "ship it"). It uses
  `make merge ARGS="<n> --confirm"` with CI green, never `--admin`. One standing exception (D42, main moves by pull request):
  the daily demo-mirror script merges its own `demo/mirror-refresh` PR when the whole diff is under `demo-assets/mirror/`.
  Only a session that the owner names an Orchestrator may merge, and only PRs it planned and reviewed.
  The designation is never inherited. A session that is not named asks for the word every time.
  GitHub branch protection also requires `check` and `revert-guard`, with 0 reviews and `strict: false`.
  It catches the remote half. The local hook is the only cover for a local fast-forward.
  `scripts/githooks/reference-transaction` and `scripts/githooks/pre-push` refuse, armed by `make hooks`.
  `PKMNSCAN_MAIN=off` is the hatch. The primary checkout syncs itself (D176, the primary checkout syncs):
  `scripts/primary_sync.py`, `PKMNSCAN_SYNC=off`, `make sync-selftest`.

## Working agreement

Report format: **Done, Deviations, Input Needed, Next**, in that order (parent CLAUDE.md). Done is one line per item:
**BUILT**, **RECORDED** or **OTHER**, with its PR or commit. "Solved" with no bucket named is refused.
Use bold labels in one quoted block, never a code fence. Start with the point. No task restatement.

- Run `make harness` before you say something works. Give the verdict, never the output.
- Screen work: experience is everything (D307, rulings CLAUDE.md carried). Run a design pass
  before you build. Review the built screen against it before you call it done.
- Reserve Opus for planning, for a builder redesigning a whole flow, and for resolving a hard merge.
  Every review is Sonnet. An Opus review needs the orchestrator to ask the owner first and get a yes.
  Sonnet builds every ordinary screen lane and fix round by default. Say an Opus lane in one line first.
  Raise it only on the owner's word, in `.claude/settings.local.json`.
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
  working agent's, and never in a shared tree. `PKMNSCAN_STASH` refuses a bare stash. **NOT MECHANIZED:** a machine cannot tell that a sentence requires undoing work.
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
