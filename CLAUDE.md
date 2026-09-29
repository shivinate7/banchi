# BANCHI

Bulk-list pre-sorted TCG singles on TCGplayer with zero attention per card, and know where
every card physically is.

**Code cards are a FEATURE of this product, not a second track** (owner's ruling, 2026-09-20,
replacing D14's framing in prose). The owner has not used it yet. The feature is DORMANT as
of 2026-09-20 — "Code cards (dormant feature)" below is the one place that says so. Its rules
live in this file now, not in a second document.

D14's structural half is NOT repealed by this line. `codes/` is still its own package.
`docs/map.py` still carries a `TRACKS` tuple, and `scripts/decision-context.py` still prints a
track banner. Repealing those is a code change and needs the owner's word on its own.

**Codex reads this same file, not a copy (D135).** `AGENTS.md` at the root is a relative
symlink to `CLAUDE.md`. `code-card-fork/AGENTS.md` and `code-card-fork/CLAUDE.md` are both
relative symlinks to this same file too, since 2026-09-20 — the fold above, not a new
exception. `.agents/skills` is a directory symlink to `.claude/skills`. `.codex/hooks.json`
mirrors `.claude/settings.json`'s hooks. `make docs-audit`'s `codex hooks` row checks both
directions. `.codex/config.toml` stays untracked, like `.claude/settings.local.json`.

## The name is the app's, and nothing beneath it (D94)

**Banchi** (a lot number, 番地) names the product: the web app under `app/`. Everything beneath
the app keeps its old name. That covers the checkout (`~/Developer/pkmnscan`) and the CLI
`./pkmnscan`. It covers the Python packages (`server/ store/ pipeline/ identify/ geometry/
codes/ cli/`), the store on disk (`inventory/store.sqlite`) and `PKMNSCAN_HOME`. It covers
every wire route, `PKMNSCAN_MAIN=off`, the harness, the fixtures, `docs/`, and `make` itself. Renaming any of
these is a defect.

**The GitHub repository is the one exception.** It was renamed
`shivinate7/pkmnscan` -> `shivinate7/banchi` on 2026-09-06, the owner's own deliberate change.
The local directory is NOT renamed. `git remote -v` points at `banchi.git`.
`~/Developer/pkmnscan` stays the checkout. The two disagreeing is correct. GitHub redirects the
old name.

**GitHub Pages is the one derived thing that followed the rename.** The demo moved to
`shivinate7.github.io/banchi/`. `.github/workflows/demo.yml` derives `DEMO_BASE` from the repo
name. The Makefile's own default is a stale fallback for a hand-run build, by design.

**The front-end rename reaches**: `app/index.html`'s title and meta, `app/src/App.tsx`'s brand
block, the document title per screen, `banchi.*` `localStorage` keys, and on-screen copy.
Nothing on the wire changed. Touching `server/` or `store/` does not "finish" the rename.

**Gating is retired as of 2026-08-23.** Gate A, B and C all passed. Gate B: 53 real cards end to
end, 2026-08-22. Gate C: two 85-card feeder runs, 2026-08-22. No gate is current. Nothing is
blocked behind one. `docs/GATES.md` is a record of runs, not a schedule. Its numbers are
evidence and are never rewritten to match a later tree.

## Commands

```
make hooks          # arm the git hooks from scripts/githooks/. Once per clone.
make worktree-setup # in a fresh worktree: venv, T1's cache, app/node_modules (npm ci, skipped
                    #   when current), this checkout's own port (D43).
make status         # where you are: next step, T1 score, branch.
make map            # docs/map.py rendered (D80). ARGS=<package|path|D<n>|--stale|--decisions>.
                    #   ARGS="D<n> --full" prints that entry in full, verbatim.
make explain        # what `make check` runs, and what each row is worth. ARGS=<target>.
make serve-scope    # the first path gate: what `make serve-selftest` reads. ARGS=list, or
                    #   ARGS="classify --base <rev>". PKMNSCAN_SERVE_SCOPE=off runs it anyway.
make guard-scope    # the second path gate: what each gated self-test reads (D247).
                    #   ARGS=list [--target <name>], or ARGS="classify --target <name> --base <rev>".
                    #   PKMNSCAN_GUARD_SCOPE=off runs every gated self-test anyway.
make orient         # ARGS=<file.tsx> [--name <C>]: which component draws it, and why.
                    #   Run before briefing a screen change.
make map-fix        # the one generator into a doc (D18): adds a file's cited decision ids to
                    #   docs/map.py. Previews. ARGS=--write applies. Gates nothing.
make offenders-prune # a generator that only deletes stale offender-list entries (D18).
                    #   Previews. ARGS=--write applies. Gates nothing.
make harness        # all TEN verification tests (T1-T9 and T11). No T10 (DEBT26).
make up             # the server, detached — one process (D138). ARGS=--restart bounces it.
                    #   `make down` stops it. Refuses on a primary checkout off main (D158).
                    #   PKMNSCAN_SERVE_MAIN=off overrides, printed in every refusal.
make reap           # stop what THIS session started, and nothing else (D127). Previews with
                    #   no argument. ARGS="--confirm", "port:N --confirm", "match:X --confirm"
                    #   or "pid:N --confirm" target one process, only if it is ours.
                    #   NARROWED 2026-09-27 (D305): a subagent's bare
                    #   --confirm stops only pids tagged with ITS OWN session id; the
                    #   orchestrator's bare --confirm is unchanged.
make janitor-install # copy the sweep and reap to the user's home Claude bin directory.
make merge          # merge a PR and move main onto it (D42). ARGS=<n> previews.
                    #   ARGS="<n> --confirm" merges. Owner must name the session an
                    #   Orchestrator first, per turn. Carries a needed rebase and force-push
                    #   on a branch nobody else holds (owner ruling, 2026-09-18).
make janitor        # what a finished session left behind. Previews. ARGS=--confirm reaps
                    #   worktrees, loose processes and branches.
make janitor-agent  # that sweep daily, unattended (main tree only). ARGS=--remove.
make launch-agent   # start the server at login (main tree only). ARGS=--remove.
make dev            # Vite with hot reload. Runs beside `make up` (D138).
make server         # Python capture server alone. Blocks.
make screenshot     # renders scripts/views.txt to captures/ui/. Needs `make dev`.
make design-check   # DESIGN.md's Fulfillment floors, in a browser. Takes a machine-wide lock
                    #   (D122); refuses rather than queues. ARGS=--wait queues instead.
                    #   PKMNSCAN_SUITE_LOCK=off overrides the lock, printed in every refusal.
                    #   PW_ARGS=<flags> reaches Playwright; ARGS never does (D136).
                    #   Read `.serve/design-check.json` once when the run lands; never poll it,
                    #   never pipe it through `tail`. Not in `make harness` or `make check`.
make design-check-quiet  # the same run, no progress stream, same lock.
make suite-lock-selftest # the design-check lock, proved by violating it. In `make check`.
make browser-scope-selftest # the CI browser-matrix classifier's spec map. In `make check`.
make text-density   # an on-demand cut table of screen prose (D284), never a gate.
                    #   ARGS="--route '#/pricing' --top 8". Not in `make check`.
make demo           # seed a demo store and record the wire into a fixture bundle.
                    #   Read `docs/specs/demo.md` before changing any demo-* target.
make demo-seed      # the store alone. Deterministic. Refuses with PKMNSCAN_HOME unset.
make demo-record    # the bundle alone, on its own throwaway server and port.
make demo-mirror SOURCE=<checkout>  # the published demo's real source (D295, owner's Mac
                    #   only): scrubs names and addresses, crops QR-cleared photos, commits
                    #   only `demo-assets/mirror/`. `make demo-mirror-rebuild` re-runs it from
                    #   the existing snapshot, no SOURCE.
make demo-mirror-install  # CI's own step: installs the committed scrub. No store, no network.
make demo-static    # demo-mirror-install, then a static build to dist-demo/.
make demo-preview   # serve dist-demo/ as a static host would.
make check          # harness + docs-audit + revert-guard + port-agreement + set-hint-agreement +
                    #   readiness-agreement + screen-freshness + screen-freshness-selftest +
                    #   sigil-check + css-var-check + css-var-check-selftest +
                    #   hand-search-selftest + token-literal-check +
                    #   kit-adoption + ignore-check + lint + typecheck + audit-self-test +
                    #   mutate-anchors + githooks-selftest + merge-selftest + revert-selftest +
                    #   claim-selftest + decisions-selftest + debts-selftest + gates-selftest +
                    #   submission-selftest + cid-selftest + pricearchive-selftest +
                    #   archive-review-selftest + holdings-selftest + identity-checks-selftest +
                    #   price-postings-selftest + product-history-selftest + sku-number-contradictions-selftest +
                    #   readings-selftest + skus-selftest + identity-store-selftest +
                    #   identity-binding-selftest + identity-readers-selftest +
                    #   identity-cli-selftest + janitor-selftest + reap-selftest +
                    #   silent-write-selftest + guard-shell-selftest + suite-lock-selftest +
                    #   browser-scope-selftest + serve-selftest + sync-selftest +
                    #   verdict-selftest + js-breakpoints-selftest + subagent-override-selftest +
                    #   guard-scope-selftest + token-literal-check-selftest + kit-adoption-selftest +
                    #   port-slots-selftest + match-selftest,
                    #   IN THIS ORDER (D161): product first, guard self-tests
                    #   last. `make explain` prints the full recipe; `make
                    #   docs-audit`'s `check registry` row reconciles this line
                    #   against it, both ways.
make css-var-check  # a `var(--x)` with no fallback where `--x` is defined nowhere.
                    #   PKMNSCAN_CSS_VARS=off skips it.
make css-var-check-selftest  # that checker, on fixtures in both directions.
make hand-search-selftest  # D271's eslint HAND_SEARCH_RULES, proved on fixtures over the
                    #   real `npx eslint --stdin`. Not on the guard-scope roster: its
                    #   subject is a JS config file, and no Python import can name it.
make token-literal-check  # a CSS literal equal to a design token's value, in its own
                    #   property family (D256). Ratcheted per file. PKMNSCAN_TOKEN_LITERALS=off
                    #   skips it.
make token-literal-check-selftest  # that checker, on fixtures in both directions.
make kit-adoption   # every ROUTES view renders <Page> and hand-rolls no kit primitive (D275).
                    #   scripts/kit-adoption-allow.json is a shrinking offender list.
make kit-adoption-selftest  # that checker, on in-memory fixtures. Writes nothing (D18).
make port-slots-selftest  # two throwaway trees forced into one port slot, proved both ways.
make ci-check       # subset of check for a fresh clone.
make catalog-refresh  # re-clone pokemon-tcg-data, refresh vendor/pokemon-tcg-data/ (D15).
                    #   Writes. Never gates. ARGS=--dry-run.
make catalog-index  # build catalog.sqlite. Generator, gitignored.
make catalog-index-selftest  # that builder, over a throwaway fixture. Not in `make check`.
make catalog-mirror # dry run only as shipped. ARGS=--dry-run samples over HTTP HEAD.
./pkmnscan scan     <capture-dir>   # code cards only: read QRs into the ledger. Free.
./pkmnscan identify <capture-dir>   # submit, wait, collect, cache. Costs money. --dry-run
                                   #   first. Selection-based (D180): --state captured,
                                   #   --box 3,5, --keys, narrowed by --game/--section/--since.
./pkmnscan rescue   <run-dir>       # a stranded run's cards, re-addressed by digest (D36).
                                   #   Free, previews. --write creates a new rescue run.
./pkmnscan join     <run-dir>       # resolve against the export. Free, re-runnable. --dry-run.
./pkmnscan emit     <run-dir> [<run-dir> ...]
                                   # write ONE import.csv (D99), across runs and games. No
                                   #   standing cap (D7) — every unsent copy goes out unless a
                                   #   send bounds it.
                                   #   --cap N            hold this SKU to at most N copies LIVE
                                   #                      (refuses if a sent copy is still
                                   #                      pending, D7 amended — reconcile --live
                                   #                      first)
                                   #   --quantity SKU=N   send exactly N copies this press
                                   #   --listed-only      above-threshold rows only
                                   #   --split-threshold  import-listed.csv / import-subthreshold.csv
                                   #   --split-games      one file per game
                                   #   --live-guard FILE  trim rows so TCGplayer never holds
                                   #                      more copies than are here
                                   #   --reprice-live F   with --live-guard: a price-only row
                                   #                      for each live card whose price F names
./pkmnscan cards    name             # a card's stable name and photograph location (D172).
./pkmnscan cards    audit [--verbose]
                                   # does every name still resolve to its photograph? Free,
                                   #   re-runnable. Three verdicts: pass, fail, not known.
                                   #   `make cid-audit` runs this. Not in `make check`.
./pkmnscan cards    photos [--write] [--limit N]
                                   # move the corpus off legacy (box, index) addresses onto
                                   #   the card's own name. Previews by default.
./pkmnscan cards    identity [--write]
                                   # the migration's own classifier, and the merged
                                   #   contradictions/sku-names report. Previews by default;
                                   #   --write performs the one-time migration.
./pkmnscan cards    contradictions / sku-names / variants
                                   # retired into `cards identity` / `cards identity --write`.
                                   #   Each prints one line and exits.
./pkmnscan prices   adopt [--write] # fold every run's legacy decisions.json into the corpus.
./pkmnscan prices   show [--held]   # what the corpus holds. --held is the cross-run view.
./pkmnscan readings adopt [--write] # the market reading is a table, not a live recompute
                                   #   (D189). --write is a full replace of both tables.
./pkmnscan readings show           # what the table holds, and which files it last credited.
./pkmnscan skus     adopt [--write] # the store-owned SKU table. Previews. Never a full
                                   #   replace — newest file wins by its own name.
./pkmnscan archive  sweep [--write] # the price-history archive (D219). Previews with no
                                   #   network call (D224). --write commits in small chunks.
./pkmnscan archive  show [--sku ID] # what the archive holds, and which ranges were last swept.
./pkmnscan queue    refresh [--export <file.csv>] [--write]
                                   # re-resolve every open queue entry, store-wide.
./pkmnscan reconcile <run-dir> <staged-export.csv>   # one import, one Export From Staged
./pkmnscan reconcile --live <my-pricing.csv> [--write]
                                   # the whole store against one live export (D87). Previews.
./pkmnscan reprice  list <my-pricing.csv> [--days N] [--percent P] [--write]
                                   # which live listings are not selling, with a proposed
                                   #   re-price (D100). Free, previews.
./pkmnscan reprice  apply <worklist.csv> [--corpus-revision <digest>] [--write]
                                   # the edited worklist back. --write produces import.csv.
                                   #   Reachable on `#/pricing` as a modal (D105).
```


## The front end

Vite + React 19 + TypeScript over the capture server and nothing else. No pipeline logic in
the browser. No second store. No auth. `app/src/server.ts` is the only client-call file.
`app/src/types.ts` is the only wire-shape file.

### The screens

**Every screen and route lives in `app/src/App.tsx`'s `ROUTES` table — most are the owner's,
one is the Fulfiller's.** Four routes are off-nav (the `aside` group — Kit, Cards to pull,
the per-product view D227 added, and Runs since D291), so the nav itself draws ten rows.
`ROUTES` is the count. Recount from the table, never a sentence (see "the census" below).

```
#/             Home           one ranked sentence of what the store is waiting on (D121),
                              one action, the library as a picture, then the five-stage spine
#/capture      Capture        live camera; box/game/set-hint/finish/rarity; undo; motion
                              trigger. Setup is remembered ON THE DEVICE (D142)
#/review       Review         one card at a time, photo first. Runs folds in here (D291): an
                              "Identify N cards, ~$X" strip when cards wait, with "Check first"
                              (the composer) and "Identify now" (spends at once). Past runs
                              sit behind a link, in a sheet that holds the whole pipeline
#/runs         Runs           off-nav since D291. Opens Review's runs sheet, so a deep link
                              (`?run=`, `?state=captured`, `?box=`) still lands
#/pricing      Pricing        every unsent copy, one row per SKU, the rows that need the owner
                              on top, one Send bar, holds (D49, D277). A Live tab prices the
                              live book (D103), and the value list is an Inventory sort now
#/orders       Orders         grouped by buyer (D193), one walk per person over open orders
#/shipping     Shipping       shipping export routed into three lanes
#/revenue      Sales          gross-revenue retrospective (D214):
                              verdict, month strip, by-name search. Canceled excluded, gross
                              only, never profit. AN ELEVENTH NAV ROW ON PURPOSE — the owner
                              was shown the 37px-past-the-fold cost at 390x754 and chose the
                              sidebar tab anyway, 2026-09-19
#/inventory    Inventory      box walk: search, copies, box operations (Manage box sheet).
                              SOLD IS HIDDEN BY DEFAULT (D132). Order under a search is frozen
                              once taken. A sale may not re-rank it (D181, D118)
#/graveyard    Graveyard      every departed card (D134). Read-only
#/codes        Codes          code-card track: QR ledger, lanes, hand-off
#/fulfillment  Cards to pull  the Fulfiller's whole product. NO shell (D5)
#/gallery      Kit            the component sheet, rendered by the build
#/product      Product history one product's market history and the owner's own sales on
                              it, by SKU. Off-nav, deep-linked (D227)
```

**A new screen is one `ROUTES` entry plus a view that returns `<Page>`** (D275).
`Page` in `app/src/kit/Page.tsx` carries what every page shares. That is one width, one top
gap and one h1 from the route's `title ?? label`. It is also the verdict, the toolbar, the
status slot and the loading shape. `make kit-adoption` fails a route view that does not render
it, and a screen that hand-rolls a primitive that the kit owns. `app/tests/scaffold.spec.ts` asserts the frame in a
browser, per route, at 1440, 820, 720 and 390. The exceptions are one shrinking offender list,
`scripts/kit-adoption-allow.json` (file -> rule -> lane). It fails on an unlisted violation and
on a stale entry. It also fails on a key that the list at the merge-base with `origin/main` does
not hold. So every rule that exists at the merge-base only shrinks. The one exception is a rule
that the merge-base does not define, which is a rule born on the branch. Its first offenders may
be listed, and the check prints which rule allowed them and why. The exception holds only while
every rule that the merge-base defines still exists. If a branch removes or renames a rule, the
check refuses all growth and names that rule. A lane that moves a screen onto
`Page` deletes that screen's entries in the same commit.

**`#/orders` and `#/shipping` are two stages of one screen and two routes.** `OrdersHub` with a
stage strip, joined client-side on order number. Not D31's defect returning: one sale, two
stages, not two unrelated views.

**`#/inventory` is the one owner-side view of stored cards** (D31). `#/boxes` and `#/pull` are
not routes. Box operations live in its Manage box sheet.

**Four routes are deliberately off-nav** (`OFF_NAV` in App.tsx): the Fulfiller's screen, the
kit, `#/product`, the per-product view (D227), and `#/runs` (D291). `#/product` is a deep link
reached by SKU, never a destination anyone browses to cold. `#/runs` is a link target only: its
content is Review's runs sheet. All four stay registered routes, reachable from elsewhere.

**The census.** Read the route or screen count from `ROUTES` itself, never from a number in
prose (Q2, test-audit-2026-09-27: a hand-typed count that a table already gives is deleted,
not reconciled). Every spec's pinned roster is reconciled by `route rosters`.
`app/tests/cursor.spec.ts` reads the nav strip rather than a hand-typed hash list.

### The design system

`app/src/tokens.css` is the only file in `app/` that may name a color, with one exception.
`app/src/kit/markPalettes.ts` holds the six locked marks' hexes (D102, `docs/specs/logo.md`
§9). It is generated, never hand-edited, reconciled by `make docs-audit`'s `logo` row
both ways. Every token is `--bn-*`. **Write new CSS with `--bn-*`.**

**The legacy aliases at the foot of tokens.css are dead.** No file under `app/src` reads
the old names, against many uses of `var(--bn-ink)` alone. Kept by design. A new rule may
not read one.

**Both themes are real.** `:root[data-theme='dark']` redefines every surface, applied before
first paint, cross-faded as one mechanism. A screen not looked at in dark is not verified.
`make docs-audit`'s `raw color` row reads for hex literals.

**Type has three roles**: `--bn-font-display` (Manrope, headings), `--bn-font-ui` (Inter,
everything), `--bn-font-mono` (JetBrains Mono, machine strings only — SKUs, run names, reason
codes, key caps, card numbers). Numbers in tables are Inter tabular-nums, not mono, except
money: a dollar figure takes the mono face through `.bn-money`, never a hand-rolled
declaration (D221). Mechanized by `app/tests/money-face.spec.ts`, in a real browser. CSS
alone cannot tell a dollar figure from a SKU, because mono, 600-weight and tabular-nums mark
both. So the spec reads what a span HOLDS. Every `$` figure in the rendered text fails unless
its resolved face is JetBrains Mono, whole dollars and inputs included. Body is 14px.

**The kit is `app/src/kit/` and `app/src/kit.css`.** `#/gallery` renders all of it. Reach for
the kit before writing a primitive. A fourth hand-rolled button is how a design system dies.

**Register.** Sentences on screen, not machine strings. Enum values are labelled. Empty states
are a real sentence and one action. **No user-visible string may name a decision, a repository
path, or a pipeline-internal noun** (D196). Mechanized by `make docs-audit`'s
`no mechanism on screen` row over `scripts/user-strings.mjs`.

**D194's pinned word ceiling is retired** (superseded by `D284`, 2026-09-23, the
owner's ruling). Three checks replace it, none of them a count.
`app/tests/text-shape.spec.ts` catches four shapes. A repeated sentence on three-plus
repeating cards or rows. A number-plus-noun fact stated twice. A sentence over 25 words. A
caption repeating 60%+ of its heading. `app/tests/machine-words.spec.ts` closes D196's own
gap. It reads rendered `innerText`, not just JSX literals. `app/tests/money-face.spec.ts`
reads D221: every dollar figure must sit in the mono face. All three read every route through
one sweep, `app/tests/routeSweep.ts`, at 1440 and 390. The seeded store is deterministic, and
a screen is read only once it is loaded.
Each reads a shrinking pending list in `app/tests/`, keyed to the finding. An entry excuses
one finding, and a new one on the same route is red. `text-shape-allow.json` is route ->
assertion -> finding text -> lane. `machine-words-allow.json` is route -> word -> lane, with
no wildcard route. `money-face-allow.json` is route -> amount -> lane. Each fails on an
unlisted finding and on a stale entry.
`make text-density` is the third piece of the owner's ruling, an on-demand cut table off the
same sweep, never a gate (D18: it writes).

**The mark is generated** (D102). `Logo` renders `docs/specs/logo.md`'s locked set, six
variants, `bluesteel` default. `scripts/build-mark.mjs` writes its geometry and
`app/public/favicon.svg`. Nothing about it is hand-drawn. Never put a `border-radius` on it —
the tile is a superellipse.

**`base.css` answers what a control does under the pointer and the finger, in three floors**
(D50, mutation-tested, `app/tests/cursor.spec.ts`): **cursor** (pointer, text, not-allowed),
**response** (eases background-color, border-color, color, box-shadow), **press**
(`translate: 0 1px`, never when disabled). A **fourth floor, stability** (D118), is a rule
rather than a declaration. A press changes what is ON SCREEN and never where the REST of it
is. Enforced by `cursor.spec.ts` (no layout property in a hover, active or focus rule) and
`inventory.spec.ts` (pressing Mark sold moves nothing outside the card panel). A slot whose
control becomes its own result reserves the tallest of its states.

**A fifth thing: one left edge for every screen, and only WIDTH may vary by route** (D197).
`.bn-page`'s margin is `0`, never `0 auto`. `app/tests/page-edge.spec.ts` asserts it across
routes and both rail states. `#/fulfillment` is excluded — no shell (D5).

**Three more rules, each silent when broken.** A component's own `transition` REPLACES the
floor's — name every animated property. `background-image` cannot animate — a hover
compositing a gradient uses an inset `box-shadow` instead. The press dip is `translate`. A
screen's own emphasis is `transform: scale()`. Never `translateY`, which doubles the dip. A
control may not ease the movement its own `:active` rule makes (D118).

**A fifth floor beside stability: same-role buttons stacked in one sector share a width**
(D195). Asserted in a real browser by `app/tests/button-stack.spec.ts`, through
`.bn-actions-stack` and `.capture-block-list`'s CSS Grid trick, discovered per group and never
read off a declared class.

**Motion is part of the system.** Durations and easing are tokens. List rows stagger off
`--bn-stagger`. `prefers-reduced-motion` is honoured. Only loops carrying meaning keep turning.

### The shell

`App.tsx` is a hand-written hash router and the shell: one table of hash routes, no routing
library. It renders for every screen except the Fulfiller's (`persona: 'fulfiller'`,
not rendered — not focusable, not reachable by a screen reader).

- A sidebar collapsing to a rail (⌘. toggles, remembered in `banchi.rail`), a top bar and
  bottom tab bar on phones, and a command palette (⌘K, the only way to `#/gallery`).
- `,` then a letter jumps anywhere. ⌘←/⌘→ step the workflow ring (D51).
- A keyboard reference sheet on `?`, the one unmodified key the shell takes, yielding to
  typing (`app/src/keys.ts`). A new binding is not done until it is in `SHORTCUTS`.
- An error boundary per route, two shapes. The owner's crash page offers reload or home. The
  Fulfiller's `plain` variant offers one button, no brand and no error text. A crash is the
  moment he is most likely to press whatever is offered.
- A toast stack, an offline banner, the document title.

### Verifying a screen

- `cd app && npx tsc --noEmit` prints nothing.
- Look at it at 1440 and 820, in both themes. Look at 390 only when the owner reports a
  phone problem (owner's ruling, 2026-09-28). The specs that assert phone layout stay in CI.
- Anything a thumb presses is 40px or more.
- `make design-check` asserts `docs/DESIGN.md`'s Fulfillment floors in a real browser: 20px
  body, 32px position labels, 320px photograph, 44px targets, 7:1 contrast, no jargon, no
  route out.

## Code cards (dormant feature) — DORMANT as of 2026-09-20

**DORMANT MEANS THIS: the owner has not run this feature yet, and no session should read it
as active work unless the owner names it.** `codes/`, the `#/codes` route, harness test T8,
and the QR decode all stay in the build and keep working. Nothing here is deleted. This is
the one place that marks the dormancy. Update this date if the owner picks the feature back
up.

`docs/specs/code-cards.md` is the spec. Architecture, measurements, channel research,
operating detail, and open questions all live there. Read it before building anything here.

### Hard rules

- Never guess a code. No decode → the paid vision read, then a human. Never a default.
- Failure must be loud. A QR that does not decode is a stop.
- Separate non-`BST` codes on sight — they are the scarce, high-value ones, and the catalog
  numbers now confirm it rather than merely asserting it.
- No real code-card photo or code string in any tracked file. Enforced by pre-commit hook.
  The runtime writing codes into gitignored `inventory/` is the sanctioned path. The guards
  protect the repository, not the store.

Rationale, sales strategy, and open questions: `docs/CODES-DECISIONS.md`.

## Things you will get wrong without being told

- **The capture server is ALREADY THREADED and NOT YOURS TO RESTART.**
  `server/capture_server.py`: `class CaptureServer(ThreadingHTTPServer)`,
  `request_queue_size = 128` (bounds the accept backlog, not the thread count), and
  `CaptureHandler.timeout = 15` (reaps only idle connections). A burst of concurrent clients
  kills it. `REQUEST_SLOTS = 4` bounds executing requests with a
  `ThreadPoolExecutor(REQUEST_SLOTS)`. It is safe over HTTP/1.1 only because every response
  sends `Connection: close` (DEBT11 has the mechanism and the measurements). `make
  launch-agent` keeps this alive over the owner's real store. Run the full suite ONCE at the
  end. Never `make up ARGS=--restart`, `make down` or `make up` to fix a wedge — the refusal
  without `--confirm` is the answer.
- **The join key is PER-GAME and normalized on both sides** (`pipeline/games.py`,
  `pipeline/join.py:number_index_key`). Pokemon composes `zfill(3)(number) + "/" +
  printedTotal`. One Piece and Riftbound match the printed identifier verbatim. Both carry
  denominator-less rows. `zfill` is COMPOSITION only, never matching. Never join on Product
  Name as the key. D35 permits it as a last resort, folded through `name_index_key`, queued
  for review rather than listed outright.
- **A run directory's slot numbers are not the truth. The photograph is** (D36).
  `cli/resolve.py:realign` re-binds every record to its digest's current slot. It refuses on
  ambiguity and on a box whose number was deleted and reused after the run
  (`cli/resolve.refuse_reallocated`, D36 amended).
- Only two columns are ever written: `Add to Quantity`, `TCG Marketplace Price`.
  `TCGplayer Id` is never modified.
- **Batch API, not sequential calls.** Model: `claude-haiku-4-5-20251001`.
- **EVERY CHECKOUT HAS ITS OWN STORE AND ITS OWN PORTS** (D43). `store/files.py:home()`
  defaults to the checkout the code runs from. Ports derive from the checkout's path
  (`app/devPort.ts`, `server/ports.py`, kept in step by `make port-agreement`). An empty
  inventory in a worktree is correct — the real one is the main checkout's. A linked checkout
  CLAIMS its own port slot once in `~/.pkmnscan/port-slots.json` (`scripts/port-slots.py`).
  `make dev`, `server`, `up`, `design-check` and `scripts/launch-config.py` claim first. A
  test run refuses a reused dev server that does not name this checkout
  (`app/checkoutIdentity.ts`, D261).
- **Real CSV libraries only** — PapaParse (JS), `csv` (Python). Never `split(",")`.
- **Not a Claude artifact.** No `window.storage`, no `facingMode: "environment"`, nothing
  about a card in `localStorage`. **Eleven keys are stored on the device**, each a fact about
  THIS MACHINE and not a card. `banchi.capture.deviceId` and `banchi.capture.rotation` live
  in `app/src/useCamera.ts`. `banchi.theme`, `banchi.rail`, `banchi.orders.fetch-filter`,
  `banchi.inventory.hide-sold`, `banchi.box-recency`, `banchi.capture.setup`,
  `banchi.capture.sections` and `banchi.runs.spend-notice` live in `app/src/deviceMemory.ts`.
  `banchi.orders.last-check` lives in `app/src/Orders.tsx`. `banchi.runs.spend-notice` is a
  NOTICE and never a cap. Owner's ruling, 2026-09-12: *"if I want to run everything, then I
  get to run everything."* `banchi.capture.setup` bundles six values as one document (D142),
  including `bid` (D153), the box's true index, drawn on no screen. `banchi.capture.sections`
  is sub-box capture's own map (docs/specs/subbox-capture.md §5). It holds which section each
  box was last capturing into, keyed by `bid`. It is kept only until the sitting ends (D164) —
  the owner's Q2 ruling, replacing a per-device-forever default. Every browser-storage key is
  `banchi.*` since 2026-09-06 (D27, amended), with no migration. The ten `pkmnscan.*` keys it
  replaced are abandoned in place. `app/eslint.config.js`'s `no-restricted-syntax` bans
  `localStorage` outside `useCamera.ts` and `deviceMemory.ts`, plus a few named, argued
  exemptions. The lint rule matches the STORE, not the key. `make docs-audit`'s
  `storage keys` row reconciles the roster.

  **A separate store, `sessionStorage`, holds two more and is NOT the roster above**.
  `banchi.session.captureId` and D39's `banchi.run-scope` live there. A new tab is a new
  shift, and for these two that is the point.
- **Never emit duplicate SKU rows** in an import file. Aggregate by SKU. `Add to Quantity`
  equals the copy count. **NO STANDING CAP as of 2026-09-07** (D7, rewritten). A cap is now
  something a SEND asks for (`emit --cap N`), and a quantity is something a send asks for per
  card (`emit --quantity SKU=N`, D7 amended). `policy.live_cap` is DELETED. A stored key is
  refused by name. What the cap never did is stop a copy being sent twice —
  `uncommitted_positions` does that, untouched.
- **The pipeline is reachable from a screen** (D33). It lives in Review's runs sheet since
  D291, and `#/runs` (D39) opens that sheet. A run's
  scope is a SELECTION (D180, supersedes D48): every card still owed a reading, one or more
  drawers, or ticked cards. One grammar (`pipeline/selection.py`) is shared by the screen, the
  route and the CLI.
- **A card's number counts the cards in the box, not the slots** (D58). Sell card 17, and the
  next card becomes 17. The STORED index (`/inventory/<box>/<index>`) never moves. A departed
  card renders `pipeline/join.departed_label` (`Box 3 · departed · B3 #96`). D68 added the
  store key, so two departed cards in one box are never one indistinguishable string.
- **A set hint on some cards narrows nothing. How wide to ask is a per-game rule** (D76).
  Widening may fire only when EVERY card of a game is hinted and every hint resolves. A
  widening is never silent (a `width` block on every fetch). Since D170, a Pokemon run that
  would widen itself is REFUSED outright (`export_needs_hint` in `pipeline/games.py`), unless
  the operator named `set_ids` or `scope` explicitly. Not enforced at the shutter (D65). Fix
  an unhinted card in Manage box → Set claims.
- **The catalogue export is a property of the GAME, not the drawer** (D166). A fetch lands in
  `inventory/.exports/<game>/`, deduped store-wide by digest. A covering export fetched inside
  900s is reused with no socket opened. `refresh: true` forces one. A reuse never touches the
  mtime — that is when the reading was TAKEN.
- **The pricing answer is one file for the whole store, keyed by SKU** (D86, amended).
  `pipeline/corpus.py` over `inventory/prices.json`. `sub_threshold` defaults to $0.49 (D9
  amended). `policy.threshold` is ALSO the floor: the market price to list at, the price the
  cheap half goes out at, and the price no rule may go below.
  `pipeline/pricing.py:FLOOR` is now only a no-store default and the labor-bar warning
  constant. Migrate legacy run files with `pkmnscan prices adopt`. `join` and `emit` refuse
  unconditionally over a legacy file not yet adopted.
- **The store of record is one SQLite file. `inventory.json` is legacy and read by nothing**
  (D88). `inventory/store.sqlite`, one table each, one transaction per write. The first open
  of a legacy store migrates it under the lock, to `inventory/legacy-json/`.
- **A sold card's photograph is reclaimed on purpose** (D89).
  `POST /boxes/<box>/photos/reclaim` deletes SOLD cards' photographs only, and keeps every
  record (`photo_sha256`, `photo_reclaimed_at`).
- **`emit` over several runs writes one file, and a cap is spent ONCE across them** (D86,
  `pipeline/join.py:add_to_quantity`). A merged file is never a concatenation of per-run CSVs.
  `#/pricing`'s default landing is every unsent copy in the store (D156), read live rather
  than off a run's stale `pricing.json`.
- **No automatic sectioning. `CARDS_PER_SECTION` no longer exists** (D10, amended). A divider
  is put in from the capture screen with `S`, at the moment it enters the box
  (`store/master.py:open_section`, inside the store lock).
- **A box is addressed by its name, and names are unique** (D20, amended). `next_box_number`
  allocates the lowest free integer, not a high-water mark. **A box also has `Box.bid`, a
  true index that is a high-water mark and is NEVER reused, drawn on no screen** (D145). The
  number is a LABEL. The id is an IDENTITY a run binds to. A run records `bid`, never the
  name. The name is joined at read time from the registry (D56), never written into a run
  directory — a rename would relabel a run's cards retroactively.

## Hard rules

- **A RULE THAT CAN BE MECHANICALLY ENFORCED MUST BE.** A NEW RULE IS NOT DONE UNTIL ITS
  ENFORCEMENT EXISTS, OR UNTIL ITS UNENFORCEABILITY IS ARGUED (D173). Owner's instruction,
  2026-09-12: *"every rule for all time... should be mechanically enforced."* A rule that
  cannot be mechanized carries a bold `**NOT MECHANIZED:**` sentence saying what a machine
  would have to SEE. `make docs-audit`'s `rule enforcement` row parses every rule below. It
  fails a commit naming neither mechanism nor argument, and it checks that the citation
  RESOLVES. It pins `HARD_RULE_FLOOR` (non-vacuity) and `PROSE_ONLY_EXPECTED` (this file's
  prose debt, lowered only). Change either constant in the same commit that changes the
  count, and say why.
- **A route is not a feature. Nothing is built until it is reachable from a screen.** Done
  means the route, a client function in `app/src/server.ts`, a control a human would look
  for, and — where it writes — its receipt and way back.
  **NOT MECHANIZED:** a machine cannot know which screen a human would look for a capability
  on. `OFF_NAV`, the Fulfiller's shell-less screen, and a capability reached only from a sheet
  or modal all break a naive route reconciliation. `make design-check` is the nearest thing
  that can see the last case, and it is deliberately off the commit path.
- Never guess an identification, a variant, or a price. Ambiguity goes to the review queue
  with its photo. Never silently drop a card.
  **NOT MECHANIZED (the guess half):** a machine cannot tell a confident correct reading from
  a guess — both are a string in a field. The drop half IS mechanized.
  `harness/tests/t3_join_coverage.py` fails when a card leaves the join unrecorded, in both
  directions, over `pipeline/join.py`'s `cards_in - cards_out`.
- Never write output before reporting unmatched rows in both directions. Mechanized:
  `harness/tests/t3_join_coverage.py` — "a one-directional check passes on that bug."
- Scope is argued, not gated. New surface area needs a reason and a decision entry, never a
  gate. Mechanized for the arithmetic half: `make docs-audit`'s `repo map` row fails a commit
  adding a file with no map entry. `decision ids` fails one citing a non-existent entry.
  Whether the reason is good is a person's judgement.
- **FIX THE CAUSE, NEVER THE SYMPTOM. CHECK WHETHER THE PRIMITIVE ALREADY EXISTS FIRST.**
  Owner's standing instruction, 2026-09-11. `make map ARGS=<path>` and
  `scripts/decision-context.py` find the existing primitive before you design around its
  absence. A stopgap fix may still be the right call. Call it a stopgap fix in the commit,
  with the cause in `docs/debts/`.
  **NOT MECHANIZED:** a machine cannot read intent — whether the author knew the cause and
  chose the symptom. `make revert-guard` and `make map ARGS=--stale` are nearby, but not this.
- **A SETTLED DECISION IS AN ARGUMENT, NOT AN AUTHORITY. THINK IN OUTCOMES.** Owner's
  instruction, 2026-09-12: *"if a decision made seems stale or overly bearing, flag it and
  ask to solve it the right way, not defer to it naturally."* Cite the entry. Say which
  premise no longer holds and how you know — measure it, or say "unmeasured." Say what it
  protected and what protects that now. Propose the fix and wait for the owner's word. Never
  quietly work around or repeal it.
  **NOT MECHANIZED:** a machine cannot tell a rotted premise from a live one. `make map
  ARGS=--stale` catches file drift only, never argument rot.
- **CHECK WHETHER A TASK IS YOURS BEFORE HANDING IT TO THE OWNER.** Owner's instruction,
  2026-09-12. Grep the routes, the command list above, and docs/map.py before asking.
  **NOT MECHANIZED:** a machine cannot read a sentence addressed to a person and decide
  whether this repo can already do it.
- **Opsec, repo-wide.** A live unredeemed code card is a bearer instrument. No code-card
  photo in a listing, README, screenshot, or commit. Mechanized by
  `scripts/githooks/pre-commit`, armed by `make hooks`.
- **Nine shell mistakes are refused before they run**, by `scripts/guard-shell.py --hook` on
  Bash and on Write/Edit, armed in both rosters (D135). Each clause resolves what a command
  would DO rather than matching what it says. Each carries its own escape hatch, and each
  fails open on its own bugs: `PKMNSCAN_CHECKOUT` (a `git checkout`/`restore` over a modified file),
  `PKMNSCAN_TREE` (a write outside this checkout, or a `cd` into another one), `PKMNSCAN_GH` (`gh api -f` with no method),
  `PKMNSCAN_LINK` (`ln -s` at an existing path), `PKMNSCAN_WAIT` (a polling loop),
  `PKMNSCAN_PUSH` (a push to a differently-named upstream), `PKMNSCAN_STASH` (a bare
  `git stash`, or a `pop`/`clear`/`drop` OVER A NON-EMPTY STACK — the stack is shared by
  every worktree of this clone, and an empty one is no subject to refuse over) and `PKMNSCAN_RESET` (`git reset --hard`/`--merge`/`--keep`
  over uncommitted tracked work) and `PKMNSCAN_NARRATE` (hiding the heartbeat of a command
  that waits for minutes — `make merge ARGS="<n> --confirm"` piped into `tail`/`head` or
  redirected away). `make guard-shell-selftest` proves each one by committing its mistake in
  a throwaway repository.
  **The ninth clause NAMES its subjects instead of resolving them, alone among the nine.**
  D235 argues why. No reader can say before a command runs whether it
  blocks and narrates. A clause firing on every pipe into `tail` would be spent on day one.
  So the roster is short and per-incident. It is also reconciled. The self-test asserts every
  command it names still carries a heartbeat constant in the file that runs it. A preview
  (`ARGS=<n>` with no `--confirm`) never waits, and is never this clause's business.
- **A CITATION NAMES A SYMBOL, NEVER A LINE.** A line number rots on the next edit above it.
  Write a decision id, a section, or the `module.symbol` form the `paths` row verifies. That
  form takes no `.py` before the symbol. A method is "`module.Class`'s `method`". A CSS rule is
  its selector. Mechanized by one `make docs-audit` row, `line anchors`, at commit. It refuses
  `path:N`, `file.ext:N`, `~N` and a bare `:N` after a cited file, in every markdown file and in
  code comments, docstrings and `docs/map.py`'s prose, with no list of exceptions. A time, a
  ratio, `host:port`, a slice and a port `server/ports.py` emits are not anchors. A bare `:N`
  with no file in its paragraph cannot be told from other text, so it is not read. A dated record that must quote a line writes it in words, as in
  "line 182, column 81". A citation of a symbol that has moved stays invisible, which D149 ruled no check can see.
- **A screen answers to the system**: `--bn-*` tokens only, verified at 1440 and 820,
  light and dark (390 only on an owner phone report). `docs/DESIGN.md` is the record. `make docs-audit`'s `design tokens` row
  locks every name and hex both ways.
- **Main moves by pull request. A session never commits to it and never pushes it** (D42). A
  session merges on the owner's WORD, both halves as one operation, when the owner NAMES the
  act — "merge," not "ship it" or "looks good." `make merge ARGS="<n> --confirm"`. `ARGS=<n>`
  alone previews. Enforced by `scripts/githooks/reference-transaction` (refuses a local move
  of `refs/heads/main`) and `pre-push` (refuses a push to it), both armed by `make hooks`.
  Escape hatch `PKMNSCAN_MAIN=off`, printed in every refusal. GitHub branch protection is also
  ON since 2026-09-06, amended 2026-09-11 — `check` and `revert-guard` required, 0 reviews
  required, `strict: false`. It catches the remote half. The local hook is still the only
  cover for a local fast-forward.
  **The primary checkout syncs itself, both parts** (D176). `scripts/primary_sync.py` runs
  `git switch main` then `git merge --ff-only origin/main` at the moments something already
  knows main moved: serve.py's adoption points, SessionStart, and `make merge`'s local half.
  It refuses on uncommitted tracked work or a mid-rebase. It touches only the primary
  checkout, never a worktree. `PKMNSCAN_SYNC=off`. `make sync-selftest` proves it.
  **A session may merge only when the owner has explicitly called it an Orchestrator**
  (owner's ruling, 2026-09-20, replacing the standing grant of 2026-09-13). The designation is
  the grant. It is never inherited, never assumed from the shape of the work, and never
  carried over from an earlier session. A session the owner has not named that way asks for
  the word every time. Where it holds, it reaches only PRs that session planned and reviewed.
  The one command is `make merge ARGS="<n> --confirm"`, with CI green, never `--admin`.
- **No user-visible string may TYPE a middle dot or bullet (U+00B7, U+2022) as a separator.**
  Owner's ruling, 2026-09-19: "this typed dot needs to be removed everywhere it exists." D41
  removed the dot-joined address string and moved the separator into CSS
  (`::before { content: '·' }`) — a screen may SHOW a separator, never TYPE one into a
  string. Mechanized by `make docs-audit`'s `typed interpunct` row over
  `scripts/user-strings.mjs`'s extraction. It fails on every typed dot that
  `scripts/typed-interpunct-allow.json` does not list, by file and by string. It also fails on
  a stale entry, and on an entry the list at the merge-base did not hold. No count is pinned.
  See D218 and D280.

## Working agreement

Report format: **Done, Deviations, Input Needed, Next**, in that order (parent CLAUDE.md).
Done is one line per item: **BUILT**, **RECORDED**, or **OTHER**, with its PR or commit. This
is the specified/built/validated vocabulary the gates already use, applied to the report
itself. "Solved" with no bucket named is refused. Bold labels in one quoted block to the owner,
never a code fence. Start with the point. No task restatement.

- Run `make harness` before saying something works. Show the output.
- Keep UI/UX at the forefront of any screen work (owner's ruling, 2026-09-02: *"experience
  is everything."*). Run a design pass before you build a screen. Review the built screen
  against that pass before you call it done.
- Reserve Opus for planning. Reserve it for an adversarial review of a path touching money,
  TCGplayer or the store's data. Reserve it for a builder redesigning a whole flow, or
  resolving a hard merge. Sonnet builds and reviews every ordinary screen lane, fix round and
  delta review by default (owner's ruling, 2026-09-24).
- A builder commits and pushes its own branch after every pass, even when a check is red.
  Each commit message ends with a `Done:` line and a `Next:` line. The `Next:` line names
  what is left, in order, so a lane can resume from its branch alone (owner's ruling,
  2026-09-24).

### Writing a brief

Three practices settle a brief before it goes out.

- **Name the rendering component, and the state that selects it.** Not "fix the walk
  sentence" but "in `#/orders`, with `hidePicks` false, `OrderLineRow` draws `CopyMapView`,
  and `CopyMapView` renders the walk sentence — change it there." Mechanized: `make orient
  ARGS=app/src/Orders.tsx --name CopyMapView` prints which component draws it and under
  which expression. Run it before the brief is written. Where two components can render the
  same thing, the brief says which and why.
- **Never ask an agent to reconstruct a state it has already left.** A "before" image is
  captured before the edit or not at all. Wanting one afterwards is the orchestrator's job,
  in a separate clean checkout — never the working agent, never in a shared tree.
  `scripts/guard-shell.py`'s `PKMNSCAN_STASH` clause refuses a bare `git stash` for exactly
  this reason — it is shared with every worktree of this clone.
  **NOT MECHANIZED:** a machine cannot read a sentence addressed to a person and tell that
  satisfying it requires undoing work.
- **State a fence by intent, and name the exception.** Not "do not touch `WalkView` or
  `buildWalk`" but "do not change which cards a walk contains or how they are ordered —
  rendering changes inside `WalkView` are in scope." A fence around files is a fence around a
  guess about which files matter. A fence around behaviour survives being wrong about the
  layout.
  **NOT MECHANIZED:** a machine cannot tell a fence drawn around behaviour from one drawn
  around files, because both are prose in a brief.
- **Show the screen before saying it looks right.** Render at 1440 and 820, both themes (390 only on an owner phone report),
  and look at the images.
- Read `docs/decisions/` before proposing an architecture change
  (`scripts/decision-context.py` finds the governing entry. `make map ARGS=--decisions`
  prints the index). Every entry is settled. Reopen one only by citing it and waiting for the
  owner's word (see the outcomes rule above).
- **Design work is repo work.** A design living only in chat is not done. Land it in
  `docs/specs/` or a decision entry in the same session, or declare it abandoned.
- When compacting: keep the fixture schema facts, every `make` command, and the
  modified-file list. Drop exploration narration.

## Map

- `docs/map.py` — the repo as data: built, TBD, and which decisions govern each file. Read it
  before editing under `app/`, `server/`, `pipeline/`, `identify/`, `store/`, `geometry/` or
  `cli/`. Audited by `make docs-audit` — a file added with no entry fails the commit.
  `make map` is how you look at it (D80). The file is large. Reading it whole spends most of a
  context window. Its token cost is about a quarter of that byte count, at roughly four
  bytes per token. That ratio is an approximation and never a measured count. `make docs-audit`'s `map sections` row fails a commit
  adding a section with no reader.
  **The build order is two lists, `SHIPPED` and `OPEN`, not a numbered sequence** (D80).
  `OPEN` has no `next`. Ranking two open items is yours. `n` is a stable id, never renumbered.
  This file no longer publishes how many references that id has in the tree. Three scans for
  "step N" citations gave three different counts, none near each other. A bare "step N"
  matches ordinary prose too — one spec alone numbers 27 of its own unrelated steps. A
  trustworthy count needs a citation registry for step ids, the way decisions and debts
  already have one, not built yet. `make docs-audit`'s `build order mirror` row
  reconciles both files, in both directions.
- `docs/decisions/` — settled decisions and why, one file per entry, indexed by
  `scripts/decisions_corpus.py`. Read before redesigning. **Not `@`-loaded** (D60): the directory is large. Loading it
  all costs about a quarter
  of that byte count in tokens, before any work. That ratio is an approximation and never a
  measured count.
  `scripts/decision-context.py` names the governing decisions before an edit under a mapped
  directory. For the conversational path, run `make map ARGS=--decisions`. It renders one line
  per entry, id and title, straight off each entry's own heading (D60, amended 2026-09-27). No
  second copy exists to drift from it. It is a table of contents, never a substitute for the
  entry's own argument.

  Renumber your own id, never another's. D116-D118 is the one collision a slug id produced,
  claimed after the fact (D140).

- `docs/GATES.md` — a stub and an index. The records are one file each under `docs/gates/`,
  in three kinds: `contract/` (T1-T9 and T11), `gate-runs/` (Gate A, B, C), `steps/` (the build
  order's shipped and open lists, D80). `make gates-selftest` proves the set is complete.
- `docs/DEBTS.md` — a stub and an index. The findings are one file each under `docs/debts/`,
  cited as `DEBT<n>` and never by path. Known gaps in the verification tooling, deliberately
  unfixed, never blocking. Read one before treating green `docs-audit` as coverage.
  `make debts-selftest` proves the set is complete.
- `docs/specs/order-pipeline.md` — steps 8-14. Its own §3 headings state each work item's
  build status; read them there rather than a copy here. T6 is SUPERSEDED (D96 amended) —
  its files stay deleted, watched by `make docs-audit`'s `recorded deletions` row. `POST
  /orders/fill` under D113 is a different capability under a reused name.
- `docs/specs/code-cards.md` — QR decode BUILT (140/140, zero mis-reads), ledger BUILT,
  product claim BUILT, channel decision RECORDED and not executed.
- `docs/specs/stale-listings.md` — SPECIFIED and BUILT, NOT VALIDATED. No file has ever
  reached TCGplayer.
- `docs/specs/undo.md` — BUILT 2026-09-17, all four sections. Undo as one concept: two
  mechanisms by ruling, and no clock is a limit anywhere. Read it before touching a reversal.
- `docs/specs/corpus-pruning.md` — RECORDED, NOT BUILT (D177). Pruning may never be
  automatic. 430 answers examined, 0 safe to auto-prune.
- `docs/specs/batch-script.md` — the four commands, storage, routing, pricing. Built.
- `docs/specs/demo.md` — the public demo, BUILT and LIVE. Why it is not a fork, what is
  real and what is invented, what the published page refuses, and why no secret reaches it.
- `docs/specs/one-process.md` — D138's plan, BUILT 2026-09-11, all three PRs. No target named
  after the file exists — the built behavior is `make up` itself, never a separate target.
- `docs/specs/store-scaling.md` — BUILT 2026-09-13, all eight items, three phases.
- `docs/specs/order-walk-plan.md` — the ticked-order walk as the fewest drawers to open.
  The SOLVER is BUILT (`pipeline/walkplan.py`, T11). The route is BUILT (`POST
  /orders/walk-plan`, its section 7 — `server/capture_server.py:do_order_walk_plan`,
  `app/src/server.ts:walkPlan`). The SCREEN is BUILT — section 8's stop and row, section 12's
  one screen (the orders list IS the selection, no mode strip, no `PullMode`, no `WalkSelect`),
  and section 9a's findings 1-4. The walk carries real positional facts and refreshes them on a
  pull, §8's 2026-09-19 ruling: RANKING is frozen for the pass, where a card physically sits is
  not. STILL OPEN, recorded in the spec: D96's lost pass figure. The filter strip is a native
  dropdown since 2026-09-19, which settled its place at 390. Which order a press records
  against is ANSWERED. D212 rules every copy fungible, so a sale records against an owing
  order, and D220 built it.
- `docs/specs/stable-card-id.md` — BUILT (D172). `store/db.py` carries the `cid` column, the
  unique index, the backfill index, and the migration. The `cards name/audit/photos`
  subcommands in the Commands block above are this spec's own delivery. Still open: the
  batch's own `custom_id`, the `identifications` re-key, the order-ledger repair, and the
  position key itself. The measurement — 2,535 of 2,535 digests match — is real.
- `docs/specs/capture-app.md` — step 7. 7a and 7b are both built. Gate B ran them 2026-08-22.
- `docs/specs/motion-trigger.md` — Gate C's auto-capture. Built, tuned, and twice corrected
  (D81, D84), with a ratchet escape and a rescue (D131). One trigger only — D130 deleted the
  second. The exposure step is refused as not validated at the rig.
  `scripts/score-trace.py` is how a trace is scored — read it before changing a threshold here.
- `docs/DESIGN.md` — the Fulfillment view's hard constraints, asserted by `make design-check`,
  and the `--bn-*` token block, reconciled by `make docs-audit`'s `design tokens` row.
- `code-card-fork/CLAUDE.md` — a relative symlink to this file since 2026-09-20. The
  "Code cards (dormant feature)" section above is its content now.
- `fixtures/` — real TCGplayer exports. Ground truth. Never modify.

Deeper schema facts live in the `tcgplayer-csv` skill. It loads on demand.
