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
make worktree-setup # in a fresh worktree, FIRST: venv, T1's cache, this checkout's own
                    #   Browser-pane port (D43).
make status         # where you are: next step, T1 score, branch.
make map            # docs/map.py RENDERED (D80). ARGS=<package|path|D<n>|--stale>.
                    #   ARGS="D<n> --full" prints that ENTRY in full, verbatim. The
                    #   default view also names the entry's path. The filenames are
                    #   zero-padded (D42 is `D042-...md`), so a glob typed from a
                    #   citation matches nothing and says nothing.
make serve-scope    # what `make serve-selftest` reads, and whether this branch touches it.
                    #   ARGS=list, or ARGS="classify --base <rev>". Derived from the
                    #   self-test's own CARRY, reconciled by `make docs-audit`'s `serve scope`
                    #   row BOTH WAYS. Fails open: no merge-base, an unreadable diff and an
                    #   EMPTY diff all run the test.
                    #   `make serve-selftest` WAS THE ONLY PATH-GATED TARGET, 2026-09-17 to
                    #   2026-09-20. It is 70.1s of `make check`'s own total and copies the
                    #   checkout with a STUB app/, so no screen change can reach it.
                    #   `PKMNSCAN_SERVE_SCOPE=off` runs it regardless, printed in every skip.
make guard-scope    # THE SECOND PATH GATE (owner's word, 2026-09-20, on a fresh
                    #   measurement). What each of twenty-two guard self-tests reads. A
                    #   sixteenth, `pricearchive-selftest`, joined 2026-09-23 on the
                    #   owner's word: "once it's done, it only needs to be tested when
                    #   touched." Six more joined the same day, once that sixteenth's own
                    #   wiring showed each of their own "not wired — pricearchive-selftest's
                    #   own precedent" notes had gone stale too:
                    #   `archive-review-selftest`, `holdings-selftest`,
                    #   `identity-checks-selftest`, `price-postings-selftest`,
                    #   `product-history-selftest` and
                    #   `sku-number-contradictions-selftest` — each proves a module with a
                    #   real caller today (`archive sweep --write`, `#/revenue`'s
                    #   unsold-stock panel, `cards checks`, `emit`/`reprice apply`,
                    #   `#/product`, `cards contradictions`).
                    #   ARGS=list [--target <name>], or
                    #   ARGS="classify --target <name> --base <rev>".
                    #   D247 is the argument. A guard
                    #   self-test proves a MECHANISM, never the product. It cannot go stale
                    #   between two moments: the guard script it proves changing, or its own
                    #   fixture changing. THE SUBJECT LIST IS DERIVED FROM EACH SELF-TEST'S
                    #   OWN SOURCE, never typed beside it — `scripts/guard-scope.py:
                    #   derive_subjects` reads local-package imports and `Path`-style chains
                    #   straight out of the test file. Only WHICH targets are gated
                    #   is a hand-typed roster, on `serve-scope.py`'s own precedent. Fails
                    #   open exactly like `serve-scope`: no merge-base, an unreadable diff,
                    #   an EMPTY diff, an unscoped target, and any exception all run the
                    #   test. `PKMNSCAN_GUARD_SCOPE=off` runs every gated self-test
                    #   regardless, printed in every skip. Reconciled BOTH WAYS by
                    #   `make docs-audit`'s `guard scope` row: every roster target is wired
                    #   into the Makefile and every wired recipe names a roster target.
                    #   A THIRD GATE MECHANISM needs the owner's word again — a new roster
                    #   entry under this same gate does not; no target here was found dead
                    #   weight; this is a placement change, not a pruning.
make orient         # ARGS=<file.tsx> [--name <C>]: every component, its line span, which
                    #   component DRAWS it, and the expression that decides whether it is
                    #   drawn. A renderer — writes nothing, gates nothing, derived every run.
                    #   READ IT BEFORE BRIEFING A SCREEN CHANGE.
make map-fix        # THE ONE GENERATOR (D18, amended). Adds the decision ids a file cites
                    #   to its `governed_by` in docs/map.py — the answer `make docs-audit`'s
                    #   `repo map` row already computes, imported from that row rather than
                    #   reimplemented. IT GATES NOTHING and is on no hook. Run it when the row
                    #   refuses you; the row is still what says you are right. Previews.
                    #   ARGS=--write applies. It only ever ADDS. `make map-fix-selftest`
                    #   proves it, deliberately NOT in `make check`.
make harness        # all TEN verification tests (T1-T9 and T11); the Stop hook runs it at
                    #   turn end. RECOUNT from harness/run.py's TESTS list. THERE IS NO T10:
                    #   that id belongs to the shelved IMB encoder (DEBT26), and this repo
                    #   renumbers its own ids and never another branch's.
make up             # THE server, detached — ONE PROCESS (D138). Serves app/dist/ and the API
                    #   on one port. Reloads Python on edit. Rebuilds the app on edit (build
                    #   ~1.2s; the old bundle answers throughout; a failed build changes
                    #   nothing). `npm ci` runs itself when the lock file's content moves.
                    #   Prints ONE link. `make down` stops it. ARGS=--restart bounces it.
                    #   Refuses alongside `make server` (EADDRINUSE, deliberate, D43).
                    #   `make dev` alongside is fine (D138 freed :5173).
                    #   WILL NOT SERVE A PRIMARY CHECKOUT OFF MAIN (D158, D53).
                    #   `PKMNSCAN_SERVE_MAIN=off` overrides, printed in every refusal.
                    #   Silent on any branch in a LINKED WORKTREE (D43).
make reap           # stop what THIS session started, and nothing else. Previews with no
                    #   argument or --confirm. ARGS="--confirm" stops every process this
                    #   checkout started. ARGS="port:5484 --confirm", "match:vite --confirm"
                    #   or "pid:12345 --confirm" target one process, only if it is ours.
                    #   RESOLVES the real targets with pgrep and lsof, read-only, and judges
                    #   each pid by whether it lives under this checkout (D127) — never a
                    #   text match on the command, which is how `pkill -f` once killed the
                    #   owner's live main-tree server from a worktree. --hook is the armed
                    #   PreToolUse guard on Bash that refuses a kill outside this checkout.
                    #   `make reap-selftest` proves it by violating it, in `check`, never
                    #   in the hook (D18).
make janitor-install # copy janitor.py, session-teardown.sh and reap.py to the user's home
                    #   Claude bin directory, outside this repo, so every clone's hooks can
                    #   reach them, not only this one. Writes those three files there and
                    #   prints the SessionEnd, WorktreeRemove and
                    #   PreToolUse hook lines to add to ~/.claude/settings.json by hand — it
                    #   does not write that file itself. `make status` compares the
                    #   installed copies against this repo's and says when either is stale.
make merge          # merge a PR and move main onto it (D42). ARGS=<n> previews. ARGS="<n>
                    #   --confirm" merges, ALWAYS a real GitHub merge, never --admin. Fetches
                    #   origin/main first, then claim-stale (D140) so the id allocation reads
                    #   current state. `make merge` carries a needed rebase and force-push on
                    #   a branch nobody else holds (owner ruling, 2026-09-18). A session may
                    #   run this only when the owner has named it an Orchestrator, per turn,
                    #   never inherited or assumed. `make merge-selftest` proves the wrapper
                    #   in a throwaway repo and worktree, in `check`, never in the git hook.
make janitor        # what a finished session left behind. PREVIEWS both tiers, presses
                    #   nothing. ARGS=--confirm reaps tier 2: worktrees, loose processes and
                    #   branches. Runs from no hook and no schedule.
make janitor-agent  # that sweep DAILY and unattended, as a launch agent, with
                    #   `.serve/janitor.log` as its receipt. MAIN TREE ONLY — a plist naming a
                    #   worktree outlives the worktree. ARGS=--remove. The backstop for the two
                    #   events that already run the cheap half and are both known to miss.
                    #   `janitor.py --branches` is the one part of tier 2 that destroys
                    #   nothing, so the session-end hook runs it with no word: a branch reaches
                    #   it only when main already carries every commit on it.
make launch-agent   # start at login. MAIN TREE ONLY: its plist would outlive a worktree.
                    #   ARGS=--remove. The Dock app is a CLIENT of this, via Chrome's
                    #   "Install page as app" (D108), never a second copy. No `make` target
                    #   for it.
make dev            # Vite with hot reload. :5173 main tree, own port in a worktree. Blocks.
                    #   Runs BESIDE `make up` (D138). `make server` is still refused.
make server         # Python capture server alone. :8000 main tree, own port in a worktree.
                    #   Blocks.
make screenshot     # renders scripts/views.txt to captures/ui/. Needs `make dev`. Can fail
                    #   for a missing element, not only an empty file. Renders the tree it
                    #   runs from (D43). Reads server/ports.py:dev_port for its own :5173.
make design-check   # DESIGN.md's Fulfillment floors, in a browser. TAKES A MACHINE-WIDE LOCK
                    #   FIRST (D122). It is the one thing D43 could not split per checkout,
                    #   because the CPU is shared. Refuses rather than queues (exit 75) and
                    #   names the holder. ARGS=--wait queues and says so every 30s.
                    #   `PKMNSCAN_SUITE_LOCK=off` overrides. NOT in `make harness` or
                    #   `make check` (DEBT16).
                    #   `PW_ARGS=<flags>` reaches Playwright. `ARGS` never does (D136). CI runs
                    #   6 shards of 2 workers each, widened on the owner's word, 2026-09-19.
                    #   D136 is amended: DEBT8's 2-vCPU premise went false when the repo went
                    #   public, 2026-09-11. A 20-dispatch proof is D136's own reader.
                    #   Backgrounds itself. Read `.serve/design-check.json` ONCE when the run
                    #   lands. It says `"running"` until it finishes, so a stale `running`
                    #   after exit means the run died. No file at all means it never reached
                    #   Playwright. Never poll it. Never pipe it through `tail` (both
                    #   documented traps in `docs/debts/`). Guarded twice: `make docs-audit`'s
                    #   `verdict file` row, and `make verdict-selftest` (D129, floor 1.58.0).
                    #   No browser, no dev server: in `check` and `ci-check`, no lock.
                    #   ON CI, GATED TO WHAT A BROWSER DRAWS (D141) by scripts/browser-scope.py,
                    #   audited by `make docs-audit`'s `browser scope` row both directions.
                    #   `server/` is deliberately out of scope (sealEveryTest). WHICH SPECS
                    #   LOAD is a second, narrower question: `browser-scope.py specs`
                    #   (D215), a derived allow-list over `app/tests/*`.
                    #   It fails open to every spec. `make docs-audit`'s `spec map` row checks
                    #   both ways. A partial spec run never writes D136's pass record.
make design-check-quiet  # same run, no progress stream, same lock.
make suite-lock-selftest # the lock, proved by violating it, including a holder killed -9.
                    #   In `check`.
make browser-scope-selftest # the browser-matrix classifier's spec map, on fixtures and the
                    #   real tree (D215). In `check`.
make demo           # seed a demo store and record the wire, a fixture bundle.
                    #   `docs/specs/demo.md` IS THE ARGUMENT FOR THIS WHOLE FAMILY — why it
                    #   is not a fork, what is real and what is invented, why VITE_DEMO is
                    #   build-time, what the published page refuses, and why no secret can
                    #   reach it. READ IT BEFORE CHANGING ANY demo-* TARGET.
make demo-seed      # the store alone. Deterministic. Refuses with PKMNSCAN_HOME unset.
make demo-record    # the bundle alone, on its own throwaway server and port.
make demo-static    # both above, then a static build to dist-demo/.
make demo-preview   # serve dist-demo/ as a static host would.
make demo-freshness # whether the bundle matches its recording. No gate: CI rebuilds fresh.
make check          # harness + docs-audit + claim-stale + revert-guard +
                    #   port-agreement + set-hint-agreement + readiness-agreement +
                    #   screen-freshness +
                    #   screen-freshness-selftest + sigil-check +
                    #   css-var-check + css-var-check-selftest + token-literal-check +
                    #   ignore-check +
                    #   lint + vale + typecheck + audit-self-test +
                    #   mutate-anchors +
                    #   githooks-selftest + merge-selftest + revert-selftest +
                    #   claim-selftest + decisions-selftest + debts-selftest +
                    #   gates-selftest + submission-selftest +
                    #   cid-selftest + pricearchive-selftest +
                    #   archive-review-selftest + holdings-selftest +
                    #   identity-checks-selftest + price-postings-selftest +
                    #   product-history-selftest +
                    #   sku-number-contradictions-selftest + readings-selftest +
                    #   janitor-selftest +
                    #   reap-selftest + silent-write-selftest + guard-shell-selftest +
                    #   coordinator-selftest + suite-lock-selftest +
                    #   browser-scope-selftest + serve-selftest +
                    #   sync-selftest + verdict-selftest + js-breakpoints-selftest +
                    #   subagent-override-selftest + guard-scope-selftest +
                    #   token-literal-check-selftest,
                    #   IN THIS ORDER (D161): product
                    #   first, guard selftests last. `make docs-audit`'s `check census`
                    #   row reconciles this against the `check:` recipe both ways.
make css-var-check  # a `var(--x)` with no fallback where `--x` is defined nowhere — the
                    #   whole declaration drops silently, with no warning. A definition is a
                    #   `.css` declaration or a TS/TSX runtime set (`style={{ '--x': ... }}`,
                    #   a bracket computed key, `.setProperty('--x', ...)`).
                    #   `PKMNSCAN_CSS_VARS=off` skips it, printed in the refusal.
make css-var-check-selftest  # that checker, on fixtures in both directions: a genuinely
                    #   undefined `var()`, one with a fallback, one defined only from TSX.
make token-literal-check  # a CSS literal exactly equal to a design token's value, in its
                    #   own property family (D256) — `font-size: 22px`
                    #   where `--bn-fs-2xl: 22px` means the two can silently diverge. Reads
                    #   tokens.css itself every run, matched by property family (spacing,
                    #   radius, font-size, line-height, letter-spacing, duration), not value
                    #   alone. RATCHETED PER FILE in scripts/token-literal-check.json —
                    #   main already carries many, so the gate is a ceiling, never zero.
                    #   `scripts/token-literal-allow.json` excuses a named one-off; a stale
                    #   entry fails. `PKMNSCAN_TOKEN_LITERALS=off` skips it, printed in the
                    #   refusal.
make token-literal-check-selftest  # that checker, on fixtures in both directions: a literal
                    #   equal to a token fails, the same value as var() or a var() fallback
                    #   passes, the same value under a different family's property passes, a
                    #   raised/lowered/unseen per-file count and a stale allow-list entry are
                    #   each proved.
make ci-check       # `check` minus `vale`, the slice a fresh clone can prove.
make catalog-refresh  # STEP 9 PIECE 1 (D15): re-clone pokemon-tcg-data, refresh
                    #   vendor/pokemon-tcg-data/. Writes. Never gates. ARGS=--dry-run.
make catalog-index  # STEP 9 PIECE 2: build catalog.sqlite. Cards join to sets BY FILENAME,
                    #   because printedTotal lives only in sets/en.json. Generator, gitignored.
make catalog-index-selftest  # that builder, over a throwaway two-set fixture. Fast. NOT
                    #   wired into `make check`'s list as shipped, deliberately.
make catalog-mirror # STEP 9 PIECE 3, DRY RUN ONLY as shipped. ARGS=--dry-run HEAD-samples.
                    #   Measured 2026-09-13: 20,444 files, ~14.2 GB extrapolated. Writes
                    #   nothing under PKMNSCAN_IMAGE_MIRROR (default harness/images/). The
                    #   bare form has never run on this checkout.
./pkmnscan scan     <capture-dir>   # CODE CARDS ONLY: read QRs into the ledger. Free.
./pkmnscan identify <capture-dir>   # submit, wait, collect, cache. COSTS MONEY. --dry-run
                                   #   first. Records the drawer's `bid` (D165). Selection-based
                                   #   (D180, supersedes D48): `--state captured`, `--box 3,5`,
                                   #   `--keys`, narrowed by `--game`, `--section` or `--since`.
./pkmnscan rescue   <run-dir>       # a STRANDED run's cards, re-addressed to where they are
                                   #   now. D36's digest mechanism, per-box restriction lifted.
                                   #   Free, previews. `--write` creates a new rescue run and
                                   #   never edits the input run. Refuses a run that is not
                                   #   stranded, an ambiguous digest, or cards spread across
                                   #   two drawers.
./pkmnscan join     <run-dir>       # resolve against the export. Free, re-runnable. --dry-run.
./pkmnscan emit     <run-dir> [<run-dir> ...]
                                   # write ONE import.csv (D99), across runs and games.
                                   #   NO STANDING CAP (D7, rewritten). Every unsent copy goes
                                   #   out unless a send bounds it.
                                   #   --cap N            hold this SKU to at most N copies LIVE
                                   #   --quantity SKU=N   SEND exactly N copies this press (D7,
                                   #                      amended). 0 sends none without a hold
                                   #   --listed-only      above-threshold rows only
                                   #   --split-threshold  import-listed.csv / import-subthreshold.csv
                                   #   --split-games      one file per game
./pkmnscan cards    name             # a card's stable name and photograph location (D172).
                                   #   Free, read-only. Never calls `db.connect`, which would
                                   #   perform the migration it previews.
./pkmnscan cards    audit [--verbose]
                                   # does every card's name still resolve to its photograph?
                                   #   Free, re-runnable. Three verdicts: pass, fail, not known.
                                   #   Not known covers a missing column, a NULL name, or
                                   #   nothing to check — never a silent pass over zero rows.
                                   #   A re-shoot is excused only by its `reshot` event's own
                                   #   recorded digest. `make cid-audit` runs this. Deliberately
                                   #   NOT in `make check`.
./pkmnscan cards    photos [--write] [--limit N]
                                   # move the corpus off legacy `(box, index)` addresses onto
                                   #   the card's own name. Previews by default. Hash source,
                                   #   refuse on mismatch, hard link, re-hash destination, THEN
                                   #   unlink source. The bytes exist under a name at every
                                   #   instant.
./pkmnscan cards    sku-names [--verbose]
                                   # one SKU, two stored names (D242's sibling).
                                   #   A card's stored name disagrees with its SKU's
                                   #   product name in the newest cached export.
                                   #   Free, read-only, no network ever.
                                   #   Three verdicts: pass, fail, not known.
                                   #   Ranks the likely SKU by the card's own claims.
                                   #   Never picks one.
./pkmnscan cards    variants [--write]
                                   # backfill `set`/`rarity` from whatever export a card's own
                                   #   game already has on disk. Governed by
                                   #   D213.
                                   #   Previews by default.
                                   #   Never guesses: a SKU that resolves to nothing keeps a
                                   #   null set. Re-runnable — a card already carrying a set
                                   #   is left alone.
./pkmnscan prices   adopt [--write] # fold every run's legacy decisions.json into the corpus.
                                   #   Previews. Newest-wins. Names the holds it replaces.
./pkmnscan prices   show [--held]   # what the corpus holds. `--held` is the cross-run view.
./pkmnscan readings adopt [--write] # THE MARKET READING IS A TABLE, NOT A LIVE RECOMPUTE
                                   #   (D189). Previews. `--write` is a FULL REPLACE of both
                                   #   tables.
./pkmnscan readings show           # what the table holds, and which files it last credited.
./pkmnscan archive  sweep [--write] # THE PRICE-HISTORY ARCHIVE (D219).
                                   #   The source's 357-day window slides. This press reads
                                   #   every range for every sku this store has sold or holds,
                                   #   sold value first (D223), and
                                   #   keeps a copy past that ceiling. PREVIEWS WITH NO NETWORK
                                   #   CALL (D224): subject count, what the
                                   #   archive already holds, what is fresh enough to skip.
                                   #   `--write` commits in small chunks as it reads, never
                                   #   once at the end, so an interrupt loses at most one
                                   #   chunk. A resumed pass never re-reads a sku it already
                                   #   holds fresh from this same pass. UNLIKE `readings
                                   #   adopt`, `--write` NEVER clears a row a pass did not
                                   #   mention. A bucket that ages out of the source is never
                                   #   deleted here. The press paces itself on a MEASURED
                                   #   interval and backs off once on a throttle
                                   #   (D222), naming it correctly rather
                                   #   than as an authorization problem. No timer runs this.
                                   #   It is a press.
./pkmnscan archive  show [--sku ID] # what the archive holds, and which ranges were last
                                   #   swept. `--sku` also prints one sku's own buckets.
./pkmnscan queue    refresh [--export <file.csv>] [--write]
                                   # re-resolve EVERY open queue entry, store-wide, not only
                                   #   entries whose box holds a live run. Runs the same ladder
                                   #   a join runs. An answered entry is never re-queued or
                                   #   dropped.
./pkmnscan reconcile <run-dir> <staged-export.csv>   # one import, one Export From Staged
./pkmnscan reconcile --live <my-pricing.csv> [--write]
                                   # THE WHOLE STORE against one live export (D87). Previews.
                                   #   Reports both directions. Writes `live`, a reading, and
                                   #   clears `sold_here`'s counter where it adopts a reading
                                   #   taken after those sales (D115). Records SKUs TCGplayer
                                   #   holds that this store never sent (D109). Moves
                                   #   quantities. Marks no card sold.
./pkmnscan reprice  list <my-pricing.csv> [--days N] [--percent P] [--write]
                                   # which live listings are not selling, with a proposed
                                   #   re-price (D100). Free, previews. `--write` writes a
                                   #   worklist to inventory/markdowns/<stamp>/, uploaded
                                   #   nowhere. --above-market P, --limit N, --again overrides
                                   #   the ratchet.
./pkmnscan reprice  apply <worklist.csv> [--corpus-revision <digest>] [--write]
                                   # the edited worklist back. `--write` produces import.csv.
                                   #   NOTHING IS DELETED to lower a price. `Add to Quantity`
                                   #   is always 0 in this file. `--corpus-revision` refuses
                                   #   the whole file if prices.json moved since it was read.
                                   #   Reachable on `#/pricing` as a modal (D105) and as a lens
                                   #   at `#/pricing?markdown=<stamp>` (D103).
```

## The front end

Vite + React 19 + TypeScript over the capture server and nothing else. No pipeline logic in
the browser. No second store. No auth. `app/src/server.ts` is the only client-call file.
`app/src/types.ts` is the only wire-shape file.

### The screens

**The app has fourteen screens and fourteen routes — thirteen the owner's, one the Fulfiller's.**
Three routes are off-nav (the `aside` group — Kit, Cards to pull, and the per-product view
D226 added), so the nav itself draws eleven rows. `app/src/App.tsx`'s
`ROUTES` table is the count. Recount from the table, never a sentence (see "the census"
below).

```
#/             Home           one ranked sentence of what the store is waiting on (D121),
                              one action, the library as a picture, then the six-stage spine
#/capture      Capture        live camera; box/game/set-hint/finish/rarity; undo; motion
                              trigger. Setup is remembered ON THE DEVICE (D142)
#/runs         Runs           pipeline: free preflight, two-step money gate, join/emit/
                              reconcile, run log, CSVs as downloads
#/review       Review         one card at a time, photo first
#/pricing      Pricing        hand-pricing worklist, one row per SKU, cut-off strip, holds
                              (D49). Two sources (D103): joined runs, and the live book at
                              `?band=top|bottom` (D159): what is worth pulling, read-only
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
                              it, by SKU. Off-nav, deep-linked (D226)
```

**`#/orders` and `#/shipping` are two stages of one screen and two routes.** `OrdersHub` with a
stage strip, joined client-side on order number. Not D31's defect returning: one sale, two
stages, not two unrelated views.

**`#/inventory` is the one owner-side view of stored cards** (D31). `#/boxes` and `#/pull` are
not routes. Box operations live in its Manage box sheet.

**Three routes are deliberately off-nav** (`OFF_NAV` in App.tsx): the Fulfiller's screen, the
kit, and `#/product`, the per-product view (D226). It is a deep link reached
by SKU, never a destination anyone browses to cold. All three stay registered routes,
reachable from elsewhere.

**The census.** Every route or screen count in this file, README.md and docs/map.py is
reconciled against `ROUTES` by `make docs-audit`'s `route census` row. Every spec's pinned
roster is reconciled by `route rosters`. `app/tests/cursor.spec.ts` reads the nav strip rather than a
hand-typed hash list.

### The design system

`app/src/tokens.css` is the only file in `app/` that may name a color, with one exception.
`app/src/kit/markPalettes.ts` holds the six locked marks' hexes (D102, `docs/specs/logo.md`
§9). It is generated, never hand-edited, reconciled by `make docs-audit`'s `logo parity` row
both ways. Every token is `--bn-*`. **Write new CSS with `--bn-*`.**

**The legacy aliases at the foot of tokens.css are dead.** Measured across all
140<!-- derived:app_src_file_count --> files under `app/src`: none read the
25<!-- derived:tokens_css_legacy_alias_count --> old names, against
293<!-- derived:bn_ink_var_uses --> uses of `var(--bn-ink)` alone. Kept by design. A new
rule may not read one.

**Both themes are real.** `:root[data-theme='dark']` redefines every surface, applied before
first paint, cross-faded as one mechanism. A screen not looked at in dark is not verified.
`make docs-audit`'s `raw color` row reads for hex literals.

**Type has three roles**: `--bn-font-display` (Manrope, headings), `--bn-font-ui` (Inter,
everything), `--bn-font-mono` (JetBrains Mono, machine strings only — SKUs, run names, reason
codes, key caps, card numbers). Numbers in tables are Inter tabular-nums, not mono, except
money: a dollar figure takes the mono face through `.bn-money`, never a hand-rolled
declaration (D221). **NOT MECHANIZED:** a machine cannot tell a dollar figure
from another tabular machine string by its CSS alone. Mono, 600-weight and tabular-nums
already mark SKUs, run ids and card numbers throughout `app/src`. Which face a span deserves
is read from what it holds, never from its declaration. Body is 14px.

**The kit is `app/src/kit/` and `app/src/kit.css`.** `#/gallery` renders all of it. Reach for
the kit before writing a primitive. A fourth hand-rolled button is how a design system dies.

**Register.** Sentences on screen, not machine strings. Enum values are labelled. Empty states
are a real sentence and one action. **No user-visible string may name a decision, a repository
path, or a pipeline-internal noun** (D196). Mechanized by `make docs-audit`'s
`no mechanism on screen` row over `scripts/user-strings.mjs`.

**The visible word count on every owner screen may only go down** (D194). Blind to which words
a screen uses — a rewording that says the same thing in fewer words is exactly what this
rewards. `app/tests/copy-budget.spec.ts` asserts against `app/tests/copy-budget.json`'s pinned
ceiling. Only `node scripts/copy-budget.mjs --pin` raises it, run by `make design-check`.

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

`App.tsx` is a hand-written hash router and the shell: fourteen hash routes, no routing
library, one table. It renders for every screen except the Fulfiller's (`persona: 'fulfiller'`,
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
- Look at it at 1440, 820 and 390, in both themes. No horizontal scroll at 390.
- Anything a thumb presses is 40px or more.
- `make design-check` asserts `docs/DESIGN.md`'s Fulfillment floors in a real browser: 20px
  body, 32px position labels, 320px photograph, 44px targets, 7:1 contrast, no jargon, no
  route out.

## Code cards (dormant feature) — DORMANT as of 2026-09-20

Code cards share the rig, the capture server, and the capture app shell with singles.
Everything downstream is separate: data model, identification, sales channel, and
fulfillment (D14's structural half, untouched — see the opening section above).

**DORMANT MEANS THIS: the owner has not run this feature yet, and no session should read it
as active work unless the owner names it.** `codes/`, the `#/codes` route, harness test T8,
and the QR decode all stay in the build and keep working. Nothing here is deleted. This is
the one place that marks the dormancy. Do not repeat the marker elsewhere. Update this date
if the owner picks the feature back up.

**The gating system is retired.** This section used to say the delivery worker "was gated on
singles Gate B." Gate B passed on 2026-08-22. The gating system retired the day after, and
nothing here waits behind anything. The worker stays unbuilt because the channel decision
stays unexecuted, a different reason, argued in `docs/specs/code-cards.md` §6.

**`docs/specs/code-cards.md` is the spec and supersedes this section's architecture.** Read
it before building. This section is the short operating summary. The spec carries the
measurements, the channel research, and the open questions.

**`scripts/docs-audit.py`'s `views exposure` advisory is turned OFF as of 2026-09-23**
(`VIEWS_EXPOSURE_ENABLED = False`), because no session is drawing pooled captures onto a
screen while this feature is dormant. Turn it back on when code-card work resumes — flip
the constant to `True`. **`scripts/guard-opsec.sh` stays ARMED, untouched**: it refuses a
real code-card photo into a commit and protects real money, and dormancy never reaches it.

### Things you will get wrong without being told

- **The QR IS the code, and the primary path makes NO model call and NO network call.**
  `codes/qr.py` decodes locally. Measured at the rig's real 3840x2160 frame size: **140 of
  140 physically-possible frames, ZERO mis-reads, 87 ms each.** The decoder is
  `zxing-cpp==2.3.0` and **the pin is load-bearing** — plain `pip install zxing-cpp` FAILS on
  this repo's Python 3.9.
- **THERE IS NO OCR, AND C2's OCR HALF IS RETIRED.** C2 specified a SKU crop off the QR as a
  fiducial, then Tesseract with an `A-Z0-9` whitelist. Do not build it. Vision OCR was
  measured returning confidence 1.0 on 24 renders of which 10 were misreads. Tesseract's
  whitelist does not work with its default LSTM engine. No public list of code-card SKU
  strings exists to fuzzy-match against. The question it was for is answered by the next
  rule.
- **The product is a CAPTURE CLAIM, not a reading.** Code cards arrive in sealed-product
  batches — a booster box yields 36 identical booster codes. The operator declares the
  product and set at capture, in D21's exact sense. `codes/products.py` holds the vocabulary,
  derived from the real catalog rather than invented.
- **A MIS-READ IS FAR WORSE THAN A REFUSAL.** A refusal costs a re-shoot. A mis-read sells a
  stranger something that does not work. Someone finds it days later, and it lands in C6 with
  nobody able to tell whether the code was bad or the read was. Every failure path here
  returns nothing rather than a guess.
- **The ledger's key is the CODE, not the position** (C3, and C8's first build had it as the
  position). Under D24 the card is destroyed, so the position is a filing reference and the
  code is the identity. This is what makes dedupe and reservation possible.
- **Codes are fungible pool inventory, not located items** (D24). No box, no section, no
  position. The code string is the primary key. Do not reuse the singles schema.
- **Atomic dequeue is required.** A code is marked reserved the instant it is assigned to an
  order. Never reissue. Double-selling a code is unrecoverable, so `codes/ledger.py:reserve`
  REFUSES anything that is not `held` rather than quietly doing nothing.
- **Codes are globally single-use and never expire, and a redeemed card looks identical to an
  unredeemed one.** The ledger is the only record of a code's state. There is no usable API
  to check one. The official verify step is genuinely non-consuming, but it sits behind
  session auth, a `can_redeem` gate and a reCAPTCHA.
- **The redemption limits are SOFT** (corrects C3). Past the limit, a code grants a little
  in-game currency instead of the product. The code is not refused.
- **DESTROYING THE CARD FORECLOSES TCGPLAYER AND EBAY'S DISPUTE DEFENCE.** TCGplayer permits
  code cards only when *attached to a physical card*. eBay's Money Back Guarantee excludes
  intangible goods, and its seller protection requires physical delivery evidence. This
  overturns C5, which existed to buy exactly that protection. See `docs/specs/code-cards.md`
  §6.1 — it is a real cost of D24, stated so nobody rediscovers it.
- **Every researched channel came back MARGINAL.** Booster codes are worth $0.01-$0.13, and
  the published wholesale bid for one is BELOW what bulk costs to get. The money is in the
  premium tail: a Pokemon Center ETB code lists at ~46x a booster. Tier the pile.

### Hard rules

- Never guess a code. No decode → the paid vision read, then a human. Never a default.
- Failure must be loud. A QR that does not decode is a stop.
- Separate non-`BST` codes on sight — they are the scarce, high-value ones, and the catalog
  numbers now confirm it rather than merely asserting it.
- No real code-card photo or code string in any tracked file. Enforced by pre-commit hook.
  The runtime writing codes into gitignored `inventory/` is the sanctioned path. The guards
  protect the repository, not the store.

Rationale, sales strategy, and open questions: `docs/CODES-DECISIONS.md`.
Spec, measurements and channel research: `docs/specs/code-cards.md`.

## Things you will get wrong without being told

- **The capture server is ALREADY THREADED and NOT YOURS TO RESTART.**
  `server/capture_server.py`: `class CaptureServer(ThreadingHTTPServer)`,
  `request_queue_size = 128` (bounds the accept backlog, not the thread count), and
  `CaptureHandler.timeout = 15` (reaps only idle connections). A burst of concurrent clients
  kills it. Measured at 80 Playwright browsers: 969 threads, 338% CPU, answering nothing.
  Fixed 2026-09-04: `REQUEST_SLOTS = 4` bounds executing requests with a
  `ThreadPoolExecutor(REQUEST_SLOTS)`. It is safe over HTTP/1.1 only because every response
  sends `Connection: close` (DEBT11 has the mechanism and the measurements — this
  was sized at 12 originally. The sweep found 4 keeps 82% of peak throughput, and less is
  strictly better). `make launch-agent` keeps this alive over the owner's real store. Run the
  full suite ONCE at the end. Never `make up ARGS=--restart`, `make down` or `make up` to fix
  a wedge — the refusal without `--confirm` is the answer.
- **The join key is PER-GAME and normalized on both sides** (`pipeline/games.py`,
  `pipeline/join.py:number_index_key`). Pokemon composes `zfill(3)(number) + "/" +
  printedTotal`. One Piece and Riftbound match the printed identifier verbatim. Both carry
  denominator-less rows. `zfill` is COMPOSITION only, never matching. A mismatch there once
  silently zero-joined 950 rows. Never join on Product Name as the key. D35 permits it as a
  last resort, folded through `name_index_key`, queued for review rather than listed outright.
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
  inventory in a worktree is correct — the real one is the main checkout's.
- **Real CSV libraries only** — PapaParse (JS), `csv` (Python). Never `split(",")`.
- **Not a Claude artifact.** No `window.storage`, no `facingMode: "environment"`, nothing
  about a card in `localStorage`. **Eleven keys are stored on the device**, each a fact about
  THIS MACHINE and not a card. `banchi.capture.deviceId` and `banchi.capture.rotation` live
  in `app/src/useCamera.ts`. `banchi.theme`, `banchi.rail`, `banchi.orders.fetch-filter`,
  `banchi.inventory.hide-sold`, `banchi.box-recency`, `banchi.capture.setup`,
  `banchi.runs.spend-notice` and `banchi.pricing.compare` live in `app/src/deviceMemory.ts`.
  `banchi.orders.last-check` lives in `app/src/Orders.tsx`. `banchi.runs.spend-notice` is a
  NOTICE and never a cap. Owner's ruling, 2026-09-12: *"if I want to run everything, then I
  get to run everything."* `banchi.capture.setup` bundles six values as one document (D142),
  including `bid` (D153), the box's true index, drawn on no screen. Every browser-storage key
  is `banchi.*` since 2026-09-06 (D27, amended), with no migration. The ten `pkmnscan.*` keys
  it replaced are abandoned in place. `app/eslint.config.js`'s `no-restricted-syntax` bans
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
- **The pipeline is reachable from a screen** (D33) and lives on `#/runs` (D39). A run's
  scope is a SELECTION (D180, supersedes D48): every card still owed a reading, one or more
  drawers, or ticked cards. One grammar (`pipeline/selection.py`) is shared by the screen, the
  route and the CLI.
- **A card's number counts the cards in the box, not the slots** (D58). Sell card 17, and the
  next card becomes 17. The STORED index (`/inventory/<box>/<index>`) never moves. A departed
  card renders `pipeline/join.departed_label` (`Box 3 · departed · B3 #96`). D68 added the
  store key: a bare `Box 3 · departed` once drew two sold copies in one box as one
  indistinguishable string.
- **A set hint on some cards narrows nothing. How wide to ask is a per-game rule** (D76).
  Widening may fire only when EVERY card of a game is hinted and every hint resolves.
  Pokemon's whole category is 32,629,598 B against a 33,554,432 B cap — 97.24%, measured
  2026-09-12, six set releases of headroom — so a widening is never silent (a `width` block on
  every fetch). Since D170, a Pokemon run that would widen itself is REFUSED outright
  (`export_needs_hint` in `pipeline/games.py`), unless the operator named `set_ids` or `scope`
  explicitly. Not enforced at the shutter (D65). Fix an unhinted card in Manage box → Set
  claims.
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
  for, and — where it writes — its receipt and way back. The owner found three fully tested
  routes with zero client functions on 2026-08-23: box delete, mid-box delete-with-reindex,
  retroactive claims. `docs/GATES.md` step 7 records the same failure at scale.
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
  adding a file with no map entry. `decision index` fails one citing a non-existent entry.
  Whether the reason is good is a person's judgement.
- **FIX THE CAUSE, NEVER THE SYMPTOM. CHECK WHETHER THE PRIMITIVE ALREADY EXISTS FIRST.**
  Owner's standing instruction, 2026-09-11. `make map ARGS=<path>` and
  `scripts/decision-context.py` find the existing primitive before you design around its
  absence. The capture-restore bug that earned this rule was solved by adopting D145's `bid`,
  already built hours earlier, rather than any of three proposed heuristics. A stopgap fix may
  still be the right call. Call it a stopgap fix in the commit, with the cause in `docs/debts/`.
  **NOT MECHANIZED:** a machine cannot read intent — whether the author knew the cause and
  chose the symptom. `make revert-guard` and `make map ARGS=--stale` are nearby, but not this.
- **A SETTLED DECISION IS AN ARGUMENT, NOT AN AUTHORITY. THINK IN OUTCOMES.** Owner's
  instruction, 2026-09-12: *"if a decision made seems stale or overly bearing, flag it and
  ask to solve it the right way, not defer to it naturally."* Cite the entry. Say which
  premise no longer holds and how you know — measure it, or say "unmeasured." Say what it
  protected and what protects that now. Propose the fix and wait for the owner's word. Never
  quietly work around or repeal it. D48 was the worked example: two of its three grounds had
  gone false for weeks before anyone looked. D180 closed it on the owner's word.
  **NOT MECHANIZED:** a machine cannot tell a rotted premise from a live one. `make map
  ARGS=--stale` catches file drift only, never argument rot.
- **CHECK WHETHER A TASK IS YOURS BEFORE HANDING IT TO THE OWNER.** Owner's instruction,
  2026-09-12, earned twice in one session when routes that already existed (a live-export
  fetch, a reconcile) were called "yours to fetch" and "yours to run." Grep the routes, the
  command list above, and docs/map.py before asking.
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
  Measured 2026-09-20: of 313 checkable code anchors, 219 point at the wrong line. Write a
  decision id, a section, or the `module.symbol` form the `paths` row verifies. That form
  takes no `.py` before the symbol. Mechanized by three `make docs-audit` rows. `line anchors`
  refuses a line past the file's end, and any anchor into a split-record stub. `line anchor
  ratchet` is per file, in D229's shape. A file its pin has never seen is held to zero.
  `line anchor allowlist` refuses an exemption in `scripts/docs-audit-line-allow.txt` that has
  stopped being true. The rot rate
  printed beside them is MEASURED and never gated. A citation pointing at a real line whose
  content has moved stays invisible, which D149 ruled no check can see.
- **A screen answers to the system**: `--bn-*` tokens only, verified at 1440, 820 and 390,
  light and dark. `docs/DESIGN.md` is the record. `make docs-audit`'s `design tokens` row
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
  `scripts/user-strings.mjs`'s extraction, RATCHETED against `scripts/typed-interpunct.json`'s
  pinned count (D194's own discipline, mirrored). It fails only when the count RISES. A lower
  count is accepted silently and printed. `node scripts/typed-interpunct-pin.mjs --pin`
  re-pins it, run by a person, never quietly. See D218.

## Working agreement

Report format: **Done, Deviations, Input Needed, Next**, in that order (parent CLAUDE.md).
Done is one line per item: **BUILT**, **RECORDED**, or **OTHER**, with its PR or commit. This
is the specified/built/validated vocabulary the gates already use, applied to the report
itself. "Solved" with no bucket named is refused. Bold labels in one quoted block to the owner,
never a code fence. Start with the point. No task restatement.

- Run `make harness` before saying something works. Show the output.

### Writing a brief

Three practices, each earned by a lost round on 2026-09-17. Together they cost more time
that evening than every verification target combined (`docs/specs/verification-cost.md`).

- **Name the rendering component, and the state that selects it.** Not "fix the walk
  sentence" but "in `#/orders`, with `hidePicks` false, `OrderLineRow` draws `CopyMapView`,
  and `CopyMapView` renders the walk sentence — change it there." Mechanized: `make orient
  ARGS=app/src/Orders.tsx --name CopyMapView` prints which component draws it and under
  which expression. Run it before the brief is written. Where two components can render the
  same thing, the brief says which and why. The round this cost: a fix briefed against
  `CopyMapView`, which `hidePicks` suppresses in exactly the state the owner was looking at.
  Correct in general, and invisible there.
- **Never ask an agent to reconstruct a state it has already left.** A "before" image is
  captured before the edit or not at all. Wanting one afterwards is the orchestrator's job,
  in a separate clean checkout — never the working agent, never in a shared tree. The round
  this cost: an agent told to produce a "before" screenshot went looking for a way to un-build
  its own change. It reached for `git stash`, which is shared with every worktree of this
  clone. `scripts/guard-shell.py`'s `PKMNSCAN_STASH` clause refuses the command. The brief
  should not have pointed an agent at it.
  **NOT MECHANIZED:** a machine cannot read a sentence addressed to a person and tell that
  satisfying it requires undoing work.
- **State a fence by intent, and name the exception.** Not "do not touch `WalkView` or
  `buildWalk`" but "do not change which cards a walk contains or how they are ordered —
  rendering changes inside `WalkView` are in scope." A fence around files is a fence around a
  guess about which files matter. A fence around behaviour survives being wrong about the
  layout. The round this cost: a fence meant to stop cross-order scope creep also enclosed
  the component that renders.
  **NOT MECHANIZED:** a machine cannot tell a fence drawn around behaviour from one drawn
  around files, because both are prose in a brief.
- **Show the screen before saying it looks right.** Render at 1440, 820 and 390, both themes,
  and look at the images.
- Read `docs/decisions/` before proposing an architecture change
  (`scripts/decision-context.py` finds the governing entry, and the index is below). Every
  entry is settled. Reopen one only by citing it and waiting for the owner's word (see the
  outcomes rule above).
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
  directory. The index below is a table of contents, never a substitute for the entry's own
  argument.

```
D1   Two-phase architecture
D2   Identification is Claude Haiku vision, owned end to end
D3   Variant resolution ladder
D4   Review queue is digital-only
D5   Two personas
D6   Photo service and pull preview
D7   Duplicates aggregate by SKU at join time
D8   Pricing source is the TCGplayer Filtered CSV export itself
D9   Threshold and floor are both $0.40
D10  Inventory model
D11  Listing path is a catalog join, never a from-scratch CSV
D12  Scope
D13  Stack
D14  Two tracks, one rig
D15  Catalog data is vendored, not fetched
D16  The docs are checked mechanically; the prose is checked by asking
D17  The repo describes itself in `docs/map.py`, and the map is audited
D18  A generator may write. Nothing that writes may gate a commit.
D19  Motion capture: live fire behind the seam, a trace for tuning, video for neither
D20  A box is an object, and its capacity is retroactive
D21  Game is a per-card claim, not a mode
D22  Taxonomies are hand-authored per game, and audited so they cannot drift
D23  The rarity claim does three jobs, and one of them pays for the feature
D24  Code cards are pooled inventory, not located
D25  The join partitions by game, and `Product Line` becomes a real reader
D26  A card leaves inventory by a state — `retired` — and a bad photo is replaced in place
D27  Session state is device-local and may be persisted
D28  The review answer gets an undo window, and the list stops moving under it
D29  A homogeneous queue may be answered as a group
D30  The physical convention for a gap
D31  One owner-side view of stored cards, and the Fulfiller does not get a vote on it
D32  The pixel budget is spent on the card, not the desk
D33  The pipeline is reachable from a screen, and one route can spend
D34  A listing hold is released against the releasing box's own copies
D35  A number that cannot be read falls back to the name, and the card still faces a human
D36  The run says what the model read; the store says which slot it is in
D37  A queued question can be closed without answering it, and the card is left alone
D38  The photograph is sized by the rows beside it, and the box and the runs get the third column
D39  The pipeline gets a route, and the selection is handed to it
D40  The screen is three columns: the box, the card, and where its copies are
D41  The address is a rank, not a list, and the separator is deleted rather than replaced
D42  main moves by pull request, and the guard is local because the server-side one is not for sale
D43  the port follows the store, because the store was already per-checkout
D44  an iCloud conflict copy is refused at the commit and never deleted on a guess
D45  The copies list is a way back into the walk, and the filter yields to the jump
D46  A card the pipeline could not place is offered the catalog, and a human may point at a row
D47  A tracked symlink is a path baked into the tree, and a checkout will spend a directory to place one
D48  A send is a cart of boxes; a run is still one box
D49  The pricing answer is one file, and a card can be held back on purpose
D50  An interactive element's feedback is the product's, not each stylesheet's
D51  Cmd-arrow steps the strip in the order it is drawn, and it is the one modifier the shell takes
D52  The photo URL names a photograph, because a slot's occupant changes under it
D53  One link, always live, and the restart discipline becomes machinery
D54  A re-emit adds; it never subtracts
D55  A set code the model glued on is removed by shape, and only after the key has missed
D56  A run names the drawer it was over, and the name is joined at read time
D57  The sale is one press, and the button becomes the way back
D58  A card's number counts the cards in the box, not the slots
D59  The live cap is a per-SKU quantity, and a count of one run's positions was answering for it
D60  The @-loaded docs are dense American technical English, and an entry cites rather than restates
D61  The shipping lane is three lanes, and the third answer is "I cannot tell"
D62  The price history is reachable, and it is drawn beside the hold rather than beside the location
D63  The order ledger is two maps, and the sync writes only one of them
D64  The Filtered Export is fetched, and completeness is a delta rather than a claim
D65  The export is asked for, and the box's own claims are the scope
D66  The order screen comes before the transport, and the shipping lane needs neither
D67  The number a screen draws is composed once, and the set code D55 strips for the key is stripped for the eye
D68  A departed card's label names the record, because two of them in one box were the same string
D69  The order screen and the shipping lane get a route each, and the transport was measured before it was written
D70  The QR is the whole identification, the product is a claim, and the card is destroyed
D71  A card with no slot is ranked like every other, and it is the figure that goes
D72  A renumbered entry takes its citations with it, and the branch's own history is what says one moved
D73  The boot header says the code changed, nothing says the data did, and only one of those is a citation error
D74  A document is checked as a document, and every markdown file is linted rather than the four a session loads
D75  A detector that cannot say "wrong" is asked a second question, and the crop is refused rather than trusted, and the shape correction reaches both crop paths
D76  A hint is evidence about its own card, and how wide to ask is a per-game rule
D77  The pipeline's rows can be the wrong card, so the export is reachable from every entry — asked for, never offered unasked
D78  A run's reason for adding nothing is a heading, the rows under it sink, and a hold sinks on the reopening
D79  The reading goes on every row, because the operator answered D62's own measurement
D80  A section with no reader is deleted or given one, the build order stops pretending to be a sequence, and the map gets a view a person can use
D81  The presence gate is a distance from this session's own baseline, and the stillness thresholds are multiples of what this session measures
D82  Ruff is adopted on the slice this session measured, not on what it enables by default
D83  A card leaves a box through a third door: moved, not sold or retired
D84  A settle is a count over a window, the stall clock is cleared by a settle, and the presence floor is sized to a hand
D85  The corner is settled by geometry, and a variable nothing sets is not a fallback
D86  The pricing answer is one file for the store, and the worklist spans runs
D87  The reconcile is store-wide, and what it writes is `live`
D88  The store of record is SQLite, and a write is one transaction
D89  A sold card's photograph is reclaimed on purpose, and the record keeps its digest
D90  The envelope is the unit of the write, and an order drives the walk as a mode of the inventory screen
D91  The window is the range, the status is the filter, and the operator picks it from what the wire returned
D92  A bare `#` is the count, the key carries a sigil, and the check is what keeps them apart
D93  The copies panel is the picker, and a full line refuses the take
D94  Banchi is the product's name, and `--bn-*` is the vocabulary every screen speaks
D95  The shell is a rail, a palette and a reference sheet, and the Fulfiller's crash has no door out
D96  The screens answer to the owner's interview, and main's history is not the authority
D97  The copy map ranks and never picks, and a line says what remains
D98  The cheap-card figure is the control, the floor choice is retired, and a run may still differ from the store
D99  The cut-off is a figure the operator sets, and one press writes one spreadsheet
D100 Nothing is deleted to lower a price, the quantity is not a variable, and the age is a proxy that says so
D101 A claim a screen names is a claim a screen can fix, and the derived tuple outran its decoder
D102 The mark is an illustration with its own palette, and the spec is its store of record
D103 Staleness is a filter and not a gate, the record holds every live row, and the file that leaves the machine stays narrow
D104 The live export is fetched, and the second standing instruction is a second constant
D105 The markdown lives where prices are decided, and one file may not have two unguarded writers
D106 The push and the publish are two presses, and the second one is the only thing here a buyer can see
D107 The rule only ever marks down; the operator may point either way
D108 The dock app is the page Chrome already renders, and the manifest is what makes it one
D109 A price is a fact about a listing, and the store remembers listings it never photographed
D110 A hover is an alpha, because the same paint over three grounds is three different hovers
D111 Cleanup is a sweep, not a step in the merge, and liveness is read rather than guessed
D112 The labels are tracked, the images are not, and an unmoved measurement is asserted rather than re-derived
D113 A line closes three ways, and only one of them claims a copy went
D114 The status requirement is answered by a remembered tick, not by an echo of the preview
D115 The reading is what the export said, and what has sold since is counted beside it
D116 A card nobody has named is not a landmark, and the distance is what keeps the skip honest
D117 The thumb floor is the kit's, the measurement is the hit area, and a phone-width spec is what reads it
D118 A press changes what is on the screen, never where the rest of it is
D119 The copy the walk stands on is a row like every other, and the receipt lands where the sale was pressed
D120 The shell speaks one brand at every width, and the phone bar is a rail
D121 The front page says what is owed, and the library is drawn as the work that made it
D122 The suite takes a machine-wide lock, because the CPU is the one thing a checkout cannot have its own of
D123 Above the desk a screen asks its column, and browser zoom is not the lever it looks like
D124 The faces are vendored, and the suite's allow-list is two ports
D125 The photograph is cropped to the card, the focus is derived from the reading, and a reading that cannot be believed is a refusal
D126 The demo inflates its own history, and the present is left alone
D127 A session may stop what it started, and the checkout is what decides which that is
D128 The key listener is attached before the paint, because a press answers to what is on the screen and not to the render before it
D129 The verdict's line is fixed by the first Playwright that counts it right, and the rig's Node is not the thing that moves
D130 A feeder that never rests gets a second trigger, and the beat is measured not typed
D131 The ratchet gets an escape, a settle is one quiet frame of three, and the beat is the backstop
D132 Sold is folded away by default, the address leads with the name, the rail is ordered by the hand, and a section can be named
D133 A branch is judged by what it lands, and a file put back the way main had it is refused unless the branch says so
D134 A departed record is buried, not kept; the box goes; and the graveyard is where the departed are read
D135 Codex reads the same rules a Claude Code session does, through three symlinks and one reconciled hook roster
D136 The suite is sharded and never widened, a sleep is a wait and not an assertion, and a tree that passed is not tested twice
D137 The catalog is Near Mint by rule, because it was only ever Near Mint by accident of the file
D138 One process serves the product, Vite compiles and never serves, and the build is the server's job
D139 Which branch the primary checkout stands on is a fact about the live rig, and a warning is the ceiling
D140 The number is claimed at the merge, because what main has taken is not knowable before it
D141 The browser matrix runs when the change reaches what a browser draws, and the path list has a reader
D142 The setup outlives the browser, the box list is ordered by the hand, and one value stays on the old clock
D143 The claim reads the checked-out tree, so which tree that is must be established before anything reads it
D144 A card that will not settle is photographed off the quietest frame it manages, and there is one trigger again
D145 A box has an index nobody sees, because the number on the drawer is a label and a label may be reused
D146 Two agreeing signals release the rarity claim, and the same comparison run backwards is a review reason
D147 The claim is spent on the oldest copies, because a card captured tonight was in no file sent last week
D148 The wait is about the claim commit, and an answer it has not got is never a pass
D149 A section number that resolves is not a citation that is right, and no check can read what a sentence is about
D150 A reading taken after a sale is that sale's own result, and it ages the claim
D151 The merge is run by a checkout, so the checkout is asked whether it is current, and main is read for a slug the moment it moves
D152 Every row in the collapsed rail draws one glyph on one spine, and a rule that lists the children it knows about will miss one
D153 The restore asks which drawer, not which number, and the picker stops drawing a number nobody reads
D154 The camera's automatic functions are inputs to the trigger's arithmetic, and the ones that step are locked
D155 The section is the ruler and the box is the margin note, and the bracket between them is deleted
D156 Every copy TCGplayer does not hold is one worklist, and a run stays open until the last of them has gone
D157 The fixture carries a per-run name, because the process table is the one thing a run cannot have its own of
D158 The refusal goes where the damage is, so the primary checkout's server will not run a branch's code, and the checkout itself is left alone
D159 The band is copies rather than SKUs, the drawer is the first answer, and nothing on hand is dropped
D160 An entry is a file, because two branches appending to one file collide every single time
D161 `make check` proves the product first and its own guards last, because a failure stops the rest
D162 The name decides a disputed number, and both readings reach the screen
D163 The cache is keyed by the digest, so the digest is what the press computes first
D164 The undo stack is the sitting, not the drawer, and the counter counts the sitting
D165 A run is bound to the drawer's true index, and the run the number stranded is repaired once by hand
D166 The catalogue export is a property of the game, and the box never chose its scope
D167 A queue entry is re-resolved where it stands, and the answer reaches the price without a second press
D168 A typed price is cleared by a press, never by an expiry, and the set it may clear is the set the corpus dates
D169 The blanket sweep asks the question the verdict answers, and a nested worktree is another checkout
D170 A widening is safe only while the category fits, and Pokemon's does not
D171 A refusal that reaches nobody did not happen, and a status line the session wrote is not a reading
D172 A card's name is the first photograph of it, frozen at issue
D173 A rule that can be enforced mechanically is enforced mechanically, and a rule with no reader is advice
D174 A press claims the cards it is about to buy, and the claim is written in the transaction that decides what they are
D175 Ownership is read the way liveness is, and a process a session no longer owns is offered rather than reaped
D176 The primary checkout syncs itself, both parts, because the thing D42 was protecting is not the thing this moves
D177 The corpus answers for listings no camera here ever saw, so a prune is a list the operator presses and never a rule a join runs
D178 A document may name what it would create, and the marking expires by itself
D179 Shell commands are refused by resolving what they would do, not by matching what they say, and each clause carries its own escape hatch
D180 A press names the cards it is over, and the drawer is one of the names
D181 The order is taken once, and a sale may not retake it
D182 An unclaimed slug is not required in the shared index it will replace itself out of
D183 A number a person reads is never a key a machine uses, so the photograph is stored under the card's name and the address is derived
D184 A gain step is the baseline times one number, a card is not, and the machine re-baselines only on that proof
D185 A row declares how many subjects it had, an empty one is pinned by name with a reason, and eleven published claims get the reader they were already cited as having
D186 A per-card price is divided by the cards actually submitted, and a reading is chosen on a metric the reading can move
D187 A claim checks whether the slug is already claimed, not only whether the number is free
D188 A join reads the store directly when there is no run directory to replay
D189 The market reading is a table, and the walk that fills it is a press
D190 The remedy `stale_claims` names is a real command, and `stale_claims` learns to see the directory it moved into
D191 `Store.history()` gets a box-scoped sibling
D192 The inventory route reads one box, and `rows.py` stops re-walking what it already loaded
D193 The ledger holds the buyer's name, because a hand walks drawers per person
D194 The visible word count on every owner screen may only go down, and the ceiling is a measurement rather than a guess
D195 Same-role buttons stacked in one sector share a width, and a Playwright sweep finds them rather than reading a declared class
D196 No user-visible string may name a decision, a repository path, or a pipeline-internal noun
D197 A page is anchored to the shell's own inset, and only its width may vary by screen
D198 Home's Review tile reads the same total `#/review` draws, never `review` alone
D199 `_phase` reads `joined` as sufficient evidence identification happened
D200 The repo-state heartbeat is a thin caller of what already exists, and it remembers across runs in a file
D201 A route change lands at the top, and a same-path query change does not
D202 Home's "cannot be filled" figure counts only orders that read `open`
D203 The two-year backlog is stood down by one press over a cutoff the operator sees, never by a rule that runs on every fetch
D204 The phone drawer's nav scrolls in the space above its foot, for any row count, and the CSS says so explicitly rather than relying on it
D205 The phone tab bar has one height, and every layout that leaves room for it reads the same name
D206 Build-order step 9's first two pieces landed; the mirror stays dry-run
D207 The foot learns from every request, and five timers become one hook
D208 Pricing states its verdict once, and the worklist discloses progressively
D209 The buyer list leads with Ready to Ship, and a re-sort is a press
D210 `pkmnscan rescue` is reached from a press, and its report is never shown verbatim
D211 The Rig panel folds once the setup is already known, and stays open until it is
D212 Every copy is fungible, so no order claims one, and the write is the only refusal left
D213 The set is a stored fact, and the hint was never one
D214 A gross-revenue retrospective is its own route, and it never claims to be profit
D215 Both: the worker count is raised, and the spec allow-list is built
D216 The price history's honest agent stopped answering, and D64's escape hatch already fit it
D217 Sales becomes a tool: sort, filter, cross-filter, drill down and deep-link, over the same rows D214 already drew
D218 A typed dot is a defect wherever it is typed, and the reader is the mechanism this time, not the sweep
D219 The archive key carries the range, and the archive never deletes
D220 Orders is inventory's screen with orders in the rail, and the walk is a mode of it
D221 Money stays mono, and the rule is amended to match
D222 The press paces itself on a measurement, and names a throttle
D223 Sold value goes first, and sealed product is a named gap
D224 The preview costs nothing, and the press commits as it goes
D225 Sales stops counting a refund as revenue, and a shortfall against today's market is not a loss
D226 A prose ratchet gets a reader, and bytes are not the ruler
D227 A route, not a lens, and never one line for two kinds of observation
D228 The claim is spent only on a merge that can happen, and the loser of a race backs itself out
D229 The prose ratchet is pinned per file, because a repo-wide number is one every merge takes from somebody
D230 The sweep's own resume window is six days, not one hour
D231 The subject list widens to the order ledger, and sealed product joins it
D232 The lossless half of the cleanup needs no word, and the schedule is the backstop for the events that miss
D233 A card row that refuses retries the ledger's own row
D234 The archive reads the store's own composed number, and the glued-code repair reaches it too
D235 The heartbeat is refused a pipe, and the wait learns the other half of its own question
D236 Unsold stock is valued by SKU off the archive, one range at a time, and sealed stock is a counted gap
D237 What the archive's 16 refusals could have caught, and what could not
D238 The archive's own refusals reach a human, with a photo
D239 Four stored-data checks, built whole, from D237
D240 Measured, not shipped: the join trusts a number that resolves, and the owner asked why
D241 Recorded, not built: ask the catalogue earlier than the archive does
D242 Two copies, one SKU, two numbers: settled by name agreement, never by mere existence
D243 Every posted price is recorded, and the row is never touched again
D244 The posted-price view is wanted, and it is shelved until there is a history to draw
D245 A citation names a symbol, not a line, and a line-number row sees only the half that shrank
D246 `commit path writes` reads the code, not `checks.py`'s own sentence about itself
D247 Fifteen guard self-tests are path-gated, and no target was found dead
D248 The harness leaves turn end, and code cards fold into one rules file
D249 Recognition by the complement, never by the expected pattern
D250 Unsold stock reaches `#/revenue`, and D236's wire is spent exactly as written
D251 The name tolerance stays at 0.80, and the answers cannot fit a number above it
D252 A wrong answer gets a correct route, and the SKU it leaves is over-listed by exactly what it gave up
D253 A card lists off name AND number agreeing, never off the number alone
D254 A product is resolved from its SKU, never from a card's own read fields
D255 One SKU, two stored names: the sibling check D242 cannot see
D256 A literal that duplicates a token is caught by family, and the ratchet is pinned per file
D257 a worktree's node_modules is provisioned, not reported
```

D116-D118: D117 exists and slots between them — a third branch's number, resolved on merge.
Renumber your own, never another's. D90-D93 are main's. D96 and D99 carry the reasoning for
adopting some and deferring others (D99 sits where it does because main took D90 first).

- `docs/GATES.md` — a stub and an index. The records are one file each under `docs/gates/`,
  in three kinds: `contract/` (T1-T9 and T11), `gate-runs/` (Gate A, B, C), `steps/` (the build
  order's shipped and open lists, D80). `make gates-selftest` proves the set is complete.
- `docs/DEBTS.md` — a stub and an index. The findings are one file each under `docs/debts/`,
  cited as `DEBT<n>` and never by path. Known gaps in the verification tooling, deliberately
  unfixed, never blocking. Read one before treating green `docs-audit` as coverage.
  `make debts-selftest` proves the set is complete.
- `docs/specs/order-pipeline.md` — steps 8-14, and its own §3 work items. T0 is
  DISCHARGED. T1 is BUILT. T2 is BUILT. T2b is BUILT, 2026-09-05, server half only. T3 is
  BUILT. T4 is NOT BUILT. T5 is NOT BUILT. T6 is SUPERSEDED (D96 amended) — its files stay
  deleted, watched by `make docs-audit`'s `recorded deletions` row. `POST /orders/fill` under
  D113 is a different capability under a reused name.
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
