# BANCHI

Bulk-list pre-sorted TCG singles on TCGplayer with zero attention per card, and know where
every card physically is. Two tracks share one rig: singles (this file) and code cards
(`code-card-fork/CLAUDE.md`, auto-loaded in that directory).

## The name is the app's, and nothing beneath it

**Banchi** — 番地, a lot number, the address of a thing — is the name of the PRODUCT a person
looks at: the web app under `app/`. Every card in the store has an address (box → section →
card), and the app is named after that idea.

**Everything under the app keeps the name it has always had.** Renaming any of it is a
defect, not a follow-up:

- the repository and its directory, and the CLI `./pkmnscan` with every subcommand
- the Python packages — `server/ store/ pipeline/ identify/ geometry/ codes/ cli/`
- the store on disk (`inventory/store.sqlite`), `PKMNSCAN_HOME`, and every route on the wire
- `PKMNSCAN_MAIN=off`, the git hooks' escape hatch, printed in every refusal
- the harness, the fixtures, `docs/`, and `make` itself

The rename is a front-end fact and it reaches exactly these places: `app/index.html`'s title
and meta, the brand block in `app/src/App.tsx`'s sidebar, the document title per screen,
the `banchi.*` keys in `localStorage`, and the copy on every screen. **Nothing on the wire
changed.** A session that "finishes" the rename by touching `server/` or `store/` has moved
the store of record for a word.

**The gating system is retired as of 2026-08-23.** Gate A passed 2026-07-26; Gate B passed
2026-08-22 with 53 real cards end to end — the first numbers this project has about cards
rather than about itself are in that gate's section; Gate C passed 2026-08-22 with two
85-card feeder runs. No gate is current, nothing is blocked behind one, and the deferred
list is open.

**`docs/GATES.md` is now a record of runs, not a schedule.** Its sections are the only
place this project writes down what it has actually measured — 53 cards end to end, finish
detection false-positive at 30%, `detect_card` at 0 of 53 and then 53 of 53, a 623 ms
feeder cadence. **Those numbers are evidence and are never rewritten to match a later
tree.** What was retired is the gate as a *control*: the blocking, the sequencing, and the
"current gate" a session had to look up before it was allowed to build. See docs/GATES.md.

## Commands

```
make hooks          # arm the git hooks (glob-installed from scripts/githooks/, so this line
                    #   never has to be recounted). Once per clone — core.hooksPath never
                    #   travels. post-merge/post-checkout print a `make hooks` reminder the
                    #   moment a pull or branch switch makes the installed copy stale — before
                    #   this, that was visible only in `make status`, easy to miss right when
                    #   it happens.
make worktree-setup # in a fresh git worktree, FIRST. venv + T1's banked cache; neither
                    #   is tracked, so neither travels. Skipping it fails T1/T6/T7 with
                    #   three errors that never mention the worktree. The Browser pane's
                    #   port is NOT among them any more: the SessionStart hook writes
                    #   `.claude/launch.json` from this checkout's own slot before any work
                    #   starts, so a worktree can no longer preview the MAIN tree (D43).
make status         # where you are: next step, T1 score, branch. Start here.
make map            # docs/map.py RENDERED — the file is 2,700 lines and had no human view
                    #   at all until 2026-08-31 (D80), which is how a whole section of it
                    #   sat wrong for three weeks. ARGS=<package|path|D<n>|--stale>;
                    #   `--stale` ranks entries whose FILE has moved since the prose about
                    #   it did, which is the one drift no audit row can decide.
make harness        # all NINE verification tests; the Stop hook runs it at turn end. It said
                    #   seven until 2026-08-31 — `t8_codes.py` landed with the code-card track
                    #   and nothing counts these either (see the route-count warning below).
                    #   T9 landed the same day: the first test here whose inputs are
                    #   RECORDINGS OF THE RIG (`harness/traces/`) rather than frames a test
                    #   drew for itself. It exists because both Playwright specs over the
                    #   motion trigger stayed green while 38 real cards were refused as an
                    #   empty stand (D81). RECOUNT from `harness/run.py`'s TESTS list.
make up             # BOTH servers, detached, and the capture server RELOADS ITSELF when you
                    #   edit Python under server/ store/ pipeline/ cli/ identify/ geometry/ codes/.
                    #   The SUPERVISOR reloads itself too, by re-exec, when one of the four
                    #   files it is made of changes (D53) — so nothing here goes stale on a
                    #   `git pull`. The Makefile is not one of them: nothing reads it at run
                    #   time.
                    #   Prints the link. `make down` stops them, `make restart` bounces them.
                    #   Do NOT run it alongside `make dev`/`make server` — the second loses,
                    #   loudly (strictPort, EADDRINUSE), which is deliberate: a server that
                    #   quietly moved would serve a DIFFERENT store (D43).
make launch-agent   # start at login, so the link is always live. MAIN TREE ONLY — it refuses
                    #   in a worktree, whose plist would outlive the worktree. ARGS=--remove.
make dev            # Vite app. :5173 in the main tree, its own port in a worktree. Blocks.
make server         # Python capture server. :8000 in the main tree, its own port in a
                    #   worktree — it prints which, and whose store it is serving. Blocks.
make screenshot     # renders scripts/views.txt to captures/ui/. Needs `make dev` running.
make design-check   # DESIGN.md's Fulfillment floors, asserted in a browser
make lint           # eslint over app/ (guards a bug earned, see app/eslint.config.js) plus ruff over
                    #   the Python packages, scoped to a slice measured against this tree (D82) —
                    #   never ruff's own defaults, never --fix. Config: ruff.toml.
make check          # harness + docs-audit + audit-self-test + githooks-selftest +
                    #   merge-selftest + port-agreement + set-hint-agreement +
                    #   screen-freshness + sigil-check + ignore-check + lint + vale +
                    #   typecheck.
                    #   THIS LIST IS CHECKED NOW —
                    #   `make docs-audit`'s `check census` row reconciles it and `make help`'s
                    #   against the recipe, and it earned the row: help said five of these
                    #   for months while this line said eleven, and nothing compared them.
                    #   `make explain` is the same list with what each row is worth.
make explain        # what `make check` runs: gates, commit path, writes, toolchain.
                    #   ARGS=<target> for one entry in full. A parallel declaration in
                    #   `scripts/checks.py`, deliberately NOT the driver — a registry that
                    #   drove the suite could silently stop running a check; this one can
                    #   only lie, and three audit rows catch it lying.
make screen-freshness # every server write in app/src has a way back: a re-read, an
                    #   invalidation signal, or a reason in the code why none is owed.
                    #   Needs node, so it is in `check` and never in the git hook.
                    #   Finds nothing today — it guards write number 39.
make audit-self-test # the checker checks itself. In `check`, never in the git hook (D16/D18).
make icloud-sweep   # iCloud conflict copies (`foo 2.py`). ARGS=--delete removes the
                    #   byte-identical ones; a DIFFERING copy is only ever reported (D44).
make githooks-selftest # D42's guard over main, proved in a throwaway repo. Never in the git hook.
make merge-selftest # the merge wrapper's local half, against a throwaway origin, clone and
                    #   worktree. Its FOOTGUN case is the one that matters: main checked out
                    #   nowhere while another tree sits on a branch BEHIND its upstream, where
                    #   the wrong command advances that branch and no hook says a word.
make merge          # merge a PR and move main onto it — BOTH HALVES, on your word (D42).
                    #   ARGS=<n> previews and presses nothing; ARGS="<n> --confirm" performs it.
                    #   A bare `make merge` refuses: there is no default PR and will not be one.
                    #   IT DELETES THE HEAD BRANCH AFTERWARDS (2026-09-05) — on origin always,
                    #   and here only when no worktree holds it and it is an ancestor of main.
                    #   Until then it deleted neither, and 125 merged PRs had left 85 branches
                    #   on origin and 106 in this clone. It is NOT `--delete-branch`: that flag
                    #   would switch this tree's branch out from under the local half.

./pkmnscan scan     <capture-dir>   # CODE CARDS ONLY. Read the QR codes into the ledger.
                                   #   FREE — no model call, no network. The QR IS the code.
./pkmnscan identify <capture-dir>   # submit, wait, collect, cache. COSTS MONEY. --dry-run first.
./pkmnscan join     <run-dir>       # resolve against the export. Free, re-runnable.
                                   #   --dry-run  preview both queues, write nothing
./pkmnscan emit     <run-dir> [<run-dir> ...]
                                   # write ONE import CSV, `import.csv`. Free, re-runnable.
                                   #   ONE PRESS WRITES ONE SPREADSHEET (D99) — across runs,
                                   #   across games, and across the listed/sub-threshold
                                   #   split, which was two files per game per run until
                                   #   2026-09-03. The live cap is spent ONCE across
                                   #   everything it writes (D86): `add_to_quantity` is
                                   #   per-run against a GLOBAL cap, so N separate emits over
                                   #   one SKU is an over-push. Measured: three separate emits
                                   #   over three real runs wrote 2 SKUs past the cap of 4;
                                   #   one merged emit wrote 0.
                                   #   --listed-only      above-threshold rows only (a filter,
                                   #                      not a split — the rest wait)
                                   #   --split-threshold  the old pair back: import-listed.csv
                                   #                      and import-subthreshold.csv
                                   #   --split-games      one file per game
./pkmnscan prices   adopt [--write] # fold every run's legacy decisions.json into the corpus.
                                   #   Previews by default; newest-wins, and it NAMES the holds
                                   #   a later price replaced rather than counting them.
./pkmnscan prices   show [--held]   # what the corpus holds. `--held` is the cross-run view of
                                   #   what is held back — D49 named its absence, D62 repeated
                                   #   it, and it is one line now that the answers are one file.
./pkmnscan reconcile <run-dir> <staged-export.csv>   # one import, one Export From Staged
./pkmnscan reconcile --live <my-pricing.csv> [--write]
                                   # THE WHOLE STORE against one live export (D87). Previews
                                   #   by default. Reports BOTH directions — copies this
                                   #   pipeline sent that TCGplayer no longer holds, and SKUs
                                   #   it holds that were never sent from here.
                                   #   WHAT IT WRITES IS `live`, AND ONLY `live`. `pushed` is
                                   #   the cumulative record of what was sent, and
                                   #   `cli/resolve.py:_copies_out` already corrects a stuck
                                   #   one against the physical ceiling. Nothing had ever
                                   #   written `live`: 405 of 443 SKUs read 0 while carrying
                                   #   pushed copies, so the cap arithmetic saw 93 live copies
                                   #   where there were 1,079.
                                   #   It moves QUANTITIES and marks no card sold (D7).
                                   #   A reading OLDER than the store's own `live_as_of` is
                                   #   kept, not written, and named in the report — the
                                   #   same rule `join` applies (D87 amended 2026-09-02).
                                   #   Reachable on `#/runs`, under the run panel.

./pkmnscan reprice  list <my-pricing.csv> [--days N] [--percent P] [--write]
                                   # WHICH LIVE LISTINGS ARE NOT SELLING, and what each would
                                   #   be re-priced to (D100). Free, re-runnable, previews.
                                   #   `--write` writes a WORKLIST — the stale rows in export
                                   #   shape, with a price already proposed on every one — into
                                   #   `inventory/markdowns/<stamp>/`. It is uploaded nowhere.
                                   #   The age it ranks on is how long the card has been OWNED,
                                   #   because `Listing` has no first-listed stamp; every
                                   #   report names the substitution in its own header.
                                   #   --days N          the window: nothing sold here inside
                                   #                     it, and OWNED since before it
                                   #   --percent P       cut off the asking price (default 10)
                                   #   --above-market P  only listings asking more than P%
                                   #                     above `TCG Market Price`
                                   #   --limit N         the N rows worth the most; rest named
                                   #   --again           override the ratchet
./pkmnscan reprice  apply <worklist.csv> [--write]
                                   # The edited worklist back; `--write` produces `import.csv`,
                                   #   which is what you upload through My Pricing.
                                   #   NOTHING IS EVER DELETED AT TCGPLAYER TO LOWER A PRICE.
                                   #   `TCG Marketplace Price` edits the live listing in place —
                                   #   282 of 288 live SKUs carry exactly the price this
                                   #   pipeline last wrote — and `Add to Quantity` is a DELTA:
                                   #   72,701 real export rows carry "0", 649 of them on rows
                                   #   TCGplayer reported LIVE. Every row of every file this
                                   #   command writes carries 0, so uploading one twice is a
                                   #   no-op. That is not true of an `emit` file: nine SKUs on
                                   #   this store sit at 2 x pushed - sold because one was.
                                   #   Only `TCGplayer Id` and `TCG Marketplace Price` are read
                                   #   out of the file you hand back; every other byte comes
                                   #   from the manifest, so a spreadsheet cannot corrupt it.
                                   #   Reachable on `#/runs`, from a header button beside the
                                   #   store-wide reconcile — a modal and not a route, which
                                   #   D100's own §5 now records as a choice rather than the
                                   #   nav measurement it started as.
```

## The front end

Vite + React 19 + TypeScript over the capture server and nothing else: no pipeline logic in
the browser, no second store, no auth, no login. `app/src/server.ts` is the only place a
client call is written and `app/src/types.ts` the only place the wire's shapes are declared.

### The screens

**The app has eleven screens and eleven routes** — ten the owner's, one the Fulfiller's.
`app/src/App.tsx`'s `ROUTES` table is the count. **Recount from the table; never increment a
sentence**, and see "the census" below for what enforces that.

```
#/             Home           the product as a picture: the six-stage spine
                              (Capture → Runs → Review → Pricing → Orders → Shipping) with the
                              live figure under each stage, the boxes, the runs, one action.
                              Every figure is the one that stage's own screen draws, read from
                              the same source, so Home can never be a step ahead of it.
#/capture      Capture        live camera; box / game / set hint / finish / rarity; undo;
                              the motion trigger and its tuning
#/runs         Runs           the pipeline: the free preflight, the two-step money gate, join /
                              emit / reconcile, the run log, and the import CSVs as downloads
#/review       Review         one card at a time, photo first — the answer writes and advances
#/pricing      Pricing        the hand-pricing worklist across runs, one row per SKU, the rule
                              strip, and D49's deliberate holds
#/orders       Orders         which copies this buyer gets and where they are, ranked by how
                              many of them sit in one box, pulled one copy at a time
#/shipping     Shipping       which envelope an order goes in, out of TCGplayer's own shipping
                              export, in three lanes
#/inventory    Inventory      the box walk and everything that hangs off it: search, a card's
                              copies and its sale, and the box's own operations
#/codes        Codes          the code-card track: read a box's QRs into the ledger, the lanes
                              the pile is tiered into, and a lane handed to a buyer
#/fulfillment  Cards to pull  the second persona's whole product: pull, photo-confirm, mark
                              sold. Rendered with NO shell at all.
#/gallery      Kit            the component sheet, rendered by the build so it cannot go stale
```

**`#/orders` and `#/shipping` are two stages of one screen and two routes.** `Orders.tsx`
exports `OrdersHub`, `Shipping.tsx` does nothing but point the second route at it with
`stage="ship"`, and the Ship stage's own body lives in `OrdersShipStage.tsx`. Two routes
rendering one hub, joined by a stage strip and a client-side join on order number — nothing
is written across the seam. This is not D31's defect returning: D31 deleted two routes drawing
the same records with no relationship between them; these are two stages of one sale, and each
is a real destination the nav, the palette and `,O` / `,S` all reach.

**`#/inventory` is the one owner-side view of stored cards** (D31). `#/boxes` and `#/pull` are
not routes and never come back; the box walk is the spine and search narrows it. The box's own
operations — rename, dividers, seal, claims, the mid-box remove, the box delete, and D89's
photo reclaim — are in its **Manage box** sheet.

**Two routes are deliberately not in the nav** and `OFF_NAV` in `App.tsx` declares it rather
than leaving it implied: the Fulfiller's screen, reached from the sidebar foot and the palette
because it opens in its own tab, and the kit, reached from the palette only. Both are
registered routes and both must stay reachable. `scripts/docs-audit.py`'s `route rosters` row
reads that constant; deleting it turns a passing check into a false alarm.

**The census.** Every published route or screen count in this file, in `README.md` and in
`docs/map.py` is reconciled against the `ROUTES` table by `make docs-audit`'s `route census`
row, and every spec's pinned roster by `route rosters`. Both are MECHANICAL and both fail a
commit. They exist because this count was wrong seven times in three files with nothing
reading it, and because the TESTS had the same disease — a sweep over "every route" off a
hand-typed list of hashes silently walked the routes it had. `app/tests/cursor.spec.ts` reads
the nav strip now. The census also refuses to go quiet: a claim reworded past the pattern
watching it is reported as an unwatched sentence.

### The design system

`app/src/tokens.css` is the system, and **it is the only file in `app/` that may name a
color.** Every token is `--bn-*` — color, type, spacing, radius, elevation, motion, the
shell's own metrics — and the legacy names the old sheet exported (`--ink`, `--muted`,
`--line`, `--s1…`, `--r`, `--util`) survive at the bottom as aliases so no stylesheet was
orphaned. **Write new CSS with `--bn-*`.**

**Both themes are real.** Light is the default; `:root[data-theme='dark']` redefines every
surface and ink together, `app/index.html` applies a stored choice before first paint, and the
toggle stamps `data-theme-switching` on `<html>` so the whole page cross-fades as one
mechanism rather than panel by panel. A screen that has not been LOOKED AT in dark is not
verified; a hard-coded color is invisible in light and wrong in dark, which is why
`make docs-audit`'s `raw color` row reads the stylesheets for hex literals.

**The stage tokens are dark in both themes** — `--bn-stage-*`, for viewfinders and photo
heroes, where the ground is dark because the subject is a photograph.

**Type has three roles.** `--bn-font-display` (Manrope) for headings and big figures,
`--bn-font-ui` (Inter) for everything, `--bn-font-mono` (JetBrains Mono) for machine strings
only — SKUs, run names, reason codes, key caps, card numbers. Numbers in tables are Inter with
`font-variant-numeric: tabular-nums`, not mono. Body is 14px.

**The kit is `app/src/kit/` and `app/src/kit.css`**, and `#/gallery` renders all of it. The
components are `Button`, `Kbd`, `Pill`, `Chip`, `PageHeader`, `EmptyState`, `Notice`,
`Segmented`, `Stat`, `Logo` and `Icon`, plus `kit/toast.tsx`'s global toast stack; the classes
are the `.bn-*` set (`.bn-page`, `.bn-panel`, `.bn-well`, `.bn-table`, `.bn-list`,
`.bn-dialog`, `.bn-sheet`, `.bn-receipt`, `.bn-skeleton`, and the rest). **Reach for the kit
before writing a primitive**, and when it genuinely lacks one, build it with a screen-prefixed
class and say so — a fourth hand-rolled button is how a design system dies.

**Register.** Sentences on screen, not machine strings; the pipeline's own string stays
available on hover and in the run log. Enum values are labelled, never printed raw
(`premium` → `Premium`). Empty states are a real sentence and one action. Danger is red, money
moments are deliberate and carry the figure in the label, success is green, live is vermilion.
An icon never appears alone without an accessible name.

**Motion is part of the system, not decoration.** Durations and easing curves are tokens; the page
enters, list rows stagger off `--bn-stagger`, selection changes and receipts and progress
animate, buttons press. `app/src/base.css` honours `prefers-reduced-motion` and keeps turning
only the loops that carry meaning — a busy ring, a skeleton, a live dot. Never let motion be
the only carrier of information.

### The shell

`App.tsx` is a hand-written hash router and the whole chrome. Read it as the shell: eleven
hash routes, no routing library, no nested routes, one table. Every screen renders inside it
except the Fulfiller's:

- **A sidebar that collapses to a rail** on wide windows — 236px or 64px, ⌘. toggles it, the
  choice is remembered in `banchi.rail`. Nine nav items in four groups; the brand, the
  hand-off link, the palette, the theme toggle and the capture server's own state sit in the
  foot.
- **A top bar and a bottom tab bar on phones**, with the rest of the screens in a left drawer
  behind More.
- **A command palette on ⌘K**, the only control that opens `#/gallery`. It searches each
  route's own `keywords`, so a screen is findable by the verbs it holds.
- **`,` then a letter jumps anywhere**, with an on-screen which-key overlay and a one-second
  window. ⌘← / ⌘→ step the workflow ring in the order the nav draws it (D51).
- **A keyboard reference sheet on `?`**, and from the palette. It lists every binding in the
  product grouped by where it applies, and each group says in a sentence that a screen's keys
  are dead while another screen is open. `?` is the only unmodified key the shell takes and it
  yields to typing — `app/src/keys.ts` makes that judgement for every handler in the app. The
  inline ⌘←/⌘→ key caps are deliberately not drawn anywhere; this sheet is the one reference,
  so **a new binding is not done until it is in `SHORTCUTS`.**
- **An error boundary per route, in two shapes.** The owner's crash page offers a reload and a
  way home. The Fulfiller's — the `plain` variant — offers ONE button that reopens the screen
  he is on, at his floors, with no brand mark and no error text, because `docs/DESIGN.md`'s
  constraints table forbids a route out of his view and a crash is the moment he is most
  likely to press whatever is offered.
- **A toast stack**, an offline banner for the capture server, and the document title.

The Fulfiller's route is `persona: 'fulfiller'`, and `hasChrome` renders none of the above for
it. Not-rendered rather than hidden: not focusable, not reachable by a screen reader, not one
specificity change from coming back.

### Verifying a screen

A screen is not finished because it compiles.

- `cd app && npx tsc --noEmit` prints nothing.
- **Look at it at 1440, 820 and 390**, the three widths this build was verified at, **in both
  themes**. No horizontal page scroll at 390.
- Anything a thumb presses is 40px or more. The control-height tokens raise themselves under
  767px and on a coarse pointer, so do not hand-roll a mouse-sized control on a phone.
- `make design-check` asserts `docs/DESIGN.md`'s Fulfillment floors in a real browser — 20px
  body, 32px position labels, 320px photograph, 44px targets, 7:1 contrast, no jargon, no
  route out. **Those floors serve a real person and are not part of any redesign.**

## Things you will get wrong without being told

- **The capture server is ALREADY THREADED, nothing bounds it, and it is NOT YOURS TO RESTART.**
  `server/capture_server.py` serves on `class CaptureServer(ThreadingHTTPServer)` — one thread per
  keep-alive CONNECTION, unbounded. `request_queue_size = 128` bounds the accept backlog and not the
  thread count, and `CaptureHandler.timeout = 15` reaps only IDLE connections. So **a burst of
  concurrent clients is what kills it**, and `make design-check` is the burst: measured at 80
  Playwright browsers, 969 threads in ten minutes, 338% CPU, answering nothing.

  **`ThreadingHTTPServer` is therefore not the fix — it is the cause.** A session on 2026-09-04
  diagnosed a wedge from `.serve/*.log` without opening the file, told the owner the server was
  single-threaded, and proposed the class it has been built on since the beginning. The real fix is
  a bounded worker pool and it is not a swap; `docs/DEBTS.md` §11 has the whole argument, the three
  measurements, and why a pool over keep-alive starves.

  **Both bounds landed 2026-09-04, and the second one is the pool.** `REQUEST_SLOTS = 4` caps how
  many requests EXECUTE at once — the interpreter, which is what ran out — and
  `CaptureServer.process_request` submits to a `ThreadPoolExecutor(REQUEST_SLOTS)` so THREADS are
  capped too. **Every response sends `Connection: close`**, which is what makes a worker's life one
  REQUEST rather than one connection and is the only reason a pool is safe over HTTP/1.1: remove it
  and four idle connections hold all four workers, and `make harness` does not fail, it HANGS.
  Measured at 150 connections: 45.5 requests/sec and 5 threads, against 45.6 and 153 with the
  semaphore alone.
  **Measured on the owner's store on their word**: the collapse reproduces at 150 connections (a
  single probe request took 18s, and failed outright at 300), and the sweep is MONOTONIC — less
  concurrency is strictly better, 53 rps at one slot against 11.9 unbounded. `4` is not the peak;
  it keeps 82% of it and leaves three slots when one is blocked on the store lock for its 30s.
  **Less is more here, which is the opposite of the intuition that first sized this at 12** — a
  value the sweep puts within noise of no bound at all. §11 has the tables.

  **`make launch-agent` keeps that process alive at login over the owner's real store**, so the
  thing on `:8000` in the main checkout is theirs. Run the full suite ONCE at the end rather than
  after every edit, and **never `make restart` / `make down` / `make up` to fix a wedge** — `down`
  and `restart` now refuse there without `--confirm`, and the refusal is the answer, not an
  obstacle. The drain is 40s and a kill past it cuts a write in flight; that same session did
  exactly that and crashed Python out from under the owner mid-use.

- **The join key is PER-GAME, and matching is normalized on both sides.** Pokemon composes
  `zfill(3)(number) + "/" + printedTotal` — the shape is pokemontcg.io's schema (`printedTotal`
  is their field name), but at runtime both values come from the identification and match
  against the export's `Number` column; nothing in the pipeline calls that API. One Piece
  carries no denominator at all (`OP15-079`) and matches the printed identifier verbatim;
  Riftbound does too, because 450 of its rows are denominator-less promos. `pipeline/games.py`
  says which strategy a game uses.

  **`zfill` is the COMPOSITION form only — never the matching form**, and getting that wrong
  was a real silent zero-join: the catalog indexed `Number` verbatim while the key padded it,
  so an export writing `39/236` was never found by a key built as `039/236`. 950 rows joined
  nothing and reported `no_catalog_row`, which blames the export. Both sides now go through
  `pipeline/join.py:number_index_key`. **Never join on Product Name as the KEY — it
  inconsistently embeds numbers** (`Delibird - 105/132` and `Nickit` sit in one column of one
  export). D35 narrows this rather than repealing it: the name is permitted as a LAST RESORT
  that fires only where the number key found nothing, folds the embedded number away on both
  sides through `pipeline/join.py:name_index_key`, and **may never list a card on its own** —
  it queues for review under `number_unread_name_matched`.
- **A run directory's slot numbers are not the truth; the photograph is** (D36). A run is
  immutable and the store is not, so a mid-box delete (D10 ruling 1) slides every higher card
  down one and the run keeps describing the box as it was. `cli/resolve.py:realign` re-binds
  every record to the slot its `photo_sha256` is at now, before anything reads a position.
  It refuses on an ambiguous digest, on two records carrying one digest, and on a
  digest-less record in a box that has moved; it reports a box it cannot check against its
  photographs as unverified rather than treating its cards as gone. **A box whose number was
  deleted and reused after the run is refused outright** (D36 amended) — box 1 held 53 Pokemon
  cards on 2026-08-22 and 133 Riftbound cards since 2026-08-29 — by
  `cli/resolve.py:refuse_reallocated`, on `store/master.py:box_disowns_run`, the rule the
  route already withheld a box's name by (D56): `realign` reads photographs and not the store,
  and passed such a run through as unverified onto another drawer's records.
- **Only two columns are ever written**: `Add to Quantity`, `TCG Marketplace Price`.
  `TCGplayer Id` is never modified. Everything else round-trips byte-identical.
- **Batch API, not sequential calls.** v1 claimed Batch and shipped real-time. Model:
  `claude-haiku-4-5-20251001`.
- **EVERY CHECKOUT HAS ITS OWN STORE AND ITS OWN PORTS, AND THE FIRST HALF HAS ALWAYS BEEN
  TRUE** (D43). `store/files.py:home()` defaults to the checkout the code runs from, so a
  worktree's `inventory/`, `runs/` and `captures/` are its own — usually empty. The ports
  follow it now: the main tree keeps `:5173` and `:8000`, and a linked worktree derives both
  from one slot off its path (`app/devPort.ts` and `server/ports.py`, kept in step by
  `make port-agreement`).

  **What this prevents is data loss, not a busy port.** While the port was the constant 8000
  in every tree, whichever server won the bind answered every tree's UI — so a branch could
  drive the owner's real 767-card inventory, or, worse, the MAIN tree's capture screen could
  be answered by a worktree's server and write real card photographs into a directory that is
  deleted with the branch.

  `make status` prints this tree's ports and says when it is a worktree; the SessionStart
  guard prints them before any work starts; `make server` prints them and names the store it
  is about to serve. **If you are looking at an empty inventory in a worktree, that is
  correct** — the real one is the main checkout's.
- **Real CSV libraries only** — PapaParse (JS), `csv` (Python). Never `split(",")`.
- **Not a Claude artifact**: no `window.storage`, no `facingMode: "environment"`, and nothing
  about a card or the inventory in `localStorage`. Inventory state is server-side, in the
  store; the camera uses a device picker. Two devices share one truth.

  **Four keys are stored on the device, and each is a fact about THIS machine rather than
  about a card**: `pkmnscan.capture.deviceId` and `pkmnscan.capture.rotation`
  (`app/src/useCamera.ts` — which camera and which way up, meaningless on another machine),
  `banchi.theme` and `banchi.rail` (`app/src/kit/index.tsx` and `App.tsx` — how this browser
  is dressed), and `banchi.orders.last-check` (`app/src/Orders.tsx` — when THIS device last
  checked TCGplayer, so a fetch receipt can say what is new since; the owner ruled it belongs
  there on 2026-09-03). None of them is a card, a position or an order.

  **The rule has a reader now.** `app/eslint.config.js`'s `no-restricted-syntax` bans
  `localStorage` in `app/src`, with `useCamera.ts` exempted by name and the other call sites
  carrying an inline disable that states the argument. A guard that is routinely disabled
  inline is one the next person disables without reading, so the exemptions are few and each
  one says why beside the key.
- **Never emit duplicate SKU rows** in an import file — undefined behavior. Aggregate
  by SKU with `Add to Quantity` = copy count, capped at 4 live.
- **The pipeline is reachable from a screen as of 2026-08-24** (D33), **and lives on `#/runs`
  since 2026-08-29** (D39). Not folded (D33, amended): a free preflight, a two-step money gate
  with no typing, the three free steps, every command's stdout verbatim, and the import CSVs as
  downloads. `server/pipeline_routes.py` is its own module because it is the one part of the
  server that can cause money to be spent — one route does, it is named for it, and it refuses
  without an explicit `confirm`. Everything else there is free and re-runnable.

  **A run's scope is a box, or cards ticked inside one, and only ONE of those is answered on
  `#/runs`.** The box has a picker there. The ticked selection has no second mass-select and
  never will: `#/inventory` keeps the only one and hands it over through
  `app/src/runHandoff.ts`. Anything that rebuilds a selection on the runs screen has recreated
  the disagreement D33 named and D39 was built to avoid.
- **A card's number counts the cards in the box, not the slots** (D58). Sell card 17 and the
  card behind it becomes card 17, on every screen and in every report — the box closes up, and
  the section boundaries move with it so `Section N · Card M` is countable on both axes. **The
  STORED index never moves**: it is the `/inventory/<box>/<index>` path, the `<index>.jpg` the
  photograph is named after, and what every write aims by, and `next_index` is the high-water
  mark D10 has always made it. `Place.slot` is the number a person counts to and `Place.index`
  is the key; they differ by the cards that have left in front of this one. A departed card is
  in no slot and renders `join.departed_label` — `Box 3 · departed` — rather than the number
  that now belongs to its successor. `pipeline/join.py:Position` is still the only label
  formula; what it gained is the box's occupancy. **The dividers editor speaks the same space**
  and `do_put_box` maps it back through `join.divider_index` before the store sees an index.

- **A SET HINT ON SOME CARDS NARROWS NOTHING, AND HOW WIDE TO ASK IS A PER-GAME RULE** (D76).
  The Filtered Export is fetched to a scope this process names (D65), and the scope is decided
  by three voices in order: an explicit `set_ids` from the operator, then the game's own
  `export_scope` in `pipeline/games.py` — `category` for riftbound, whose whole 10,078-row
  English catalogue is one file, `sets` everywhere else — then the run's cards. **The cards may
  narrow only when they are UNANIMOUS**: every card of that game carrying a hint, and every
  hint resolving. D65's first build collected the hints that existed and never counted the
  cards carrying none, so one hinted card in a 200-card box scoped the whole export to one set
  and the other 199 queued `no_catalog_row` behind a fetch that reported success.

  `GET /pipeline/runs/<name>/scope` draws all of it before the button is pressed and presses
  nothing; `#/runs` renders it, and `asked.reason` says which voice chose. **`--rule` and
  `--basis` are deliberately NOT on that screen** — D49 makes ONE FILE the place a pricing
  answer is written and `#/pricing` the press that writes it. That file is
  `inventory/prices.json` since D86's amendment, not `runs/<n>/decisions.json`; the ruling is
  unchanged and the file moved.

- **THE PRICING ANSWER IS ONE FILE FOR THE WHOLE STORE, KEYED BY SKU** (D86, amended
  2026-09-02 on the owner's question). `pipeline/corpus.py` over `inventory/prices.json` holds
  every listing answer — a price, or a hold with its reason, watch and note — plus the standing
  `rule`/`basis`/`sub_threshold`. A run directory carries NO pricing answer any more.
  **`sub_threshold` has a default — flat $0.49** (`pipeline/corpus.py:DEFAULT_SUB_THRESHOLD`;
  D9 amended 2026-09-02), applied where the key is absent or null and written on the next
  save, so a fresh store's first emit is not refused for want of an answer already given once.

  **Why it moved: a run's `decisions.json` held two different kinds of fact.** `rule`, `basis`
  and `sub_threshold` are arguably properties of the lot (D48); `overrides` and
  `no_market_data` are properties of the CARD (D7 — *"price is per-SKU and shared across
  copies"*). Stored per run, one card carried one answer per drawer it had been photographed
  in: **66 SKUs, 8 answered twice, 3 of those a `withheld` hold answered by a later price** —
  SKU 9191210 held bullish above $5 out of box 3 and listed at $3.45 out of box 4 the next day,
  drawn as an ordinary row with no note anywhere.

  **The migration is `pkmnscan prices adopt` and it previews first.** Newest-wins, and it names
  the holds a later price replaced rather than counting them. `--write` RETIRES each folded
  file to `decisions.json.adopted`, and a re-adopt over answered SKUs retires without `--force`.
  **A legacy run file is never read as a fallback** — that would put the duplication back on
  the first re-join of an old run — so `join` and `emit` refuse UNCONDITIONALLY, before
  anything is read or written, with a sentence naming `prices adopt --write`. That refusal was
  gated on an EMPTY corpus until 2026-09-02, and eight files on the owner's store sat ignored
  behind it.

  **What is per-run still: a POLICY override**, `Corpus.overrides`, for the lot that genuinely
  wants its own `sub_threshold`. Nothing writes one today; D86 names that as a reopening
  condition rather than leaving it to be discovered.

- **THE STORE OF RECORD IS ONE SQLITE FILE, AND `inventory.json` IS A LEGACY FILE READ BY
  NOTHING** (D88, 2026-09-01). `inventory/store.sqlite` holds cards, boxes, listings, the
  identification cache, both standing queues, the order ledger and the history, one table
  each, and every `Store.write()` is ONE transaction over all of them — the five-file torn set
  `store/session.py` spent a week calling "a decision nobody has argued" cannot happen
  now. `Snapshot` is still the API and `inventory.cards` is still a dict to every caller
  (`store/rows.py`), but a session bound to the database loads only the rows a method names:
  a capture into a 100,000-card store builds ONE card object and commits in ~3 ms, where the
  JSON cycle took ~4 s. **The first open of a legacy store migrates it** — without loss, under
  the lock, moving the six JSON files to `inventory/legacy-json/` with a receipt — and a JSON
  file left beside the database is never a fallback (D86's rule): `make status` reports one.
  Look at the store with the `sqlite3` CLI; the owner ruled no JSON export target is wanted.
  What is NOT in the transaction is what never was: photographs, sidecars and `codes.jsonl`,
  written inside the flock, which is why the flock survives.

- **A SOLD CARD'S PHOTOGRAPH IS RECLAIMED ON PURPOSE, AND THAT IS A THIRD SHAPE** (D89).
  Capture-undo deletes the record and the photograph (D10); `sold` and `retired` keep both
  (D26). `POST /boxes/<box>/photos/reclaim` deletes the photographs of a box's SOLD cards and
  keeps every record, each carrying `photo_sha256` and `photo_reclaimed_at` from then on. Sold
  only: a retired card's photograph is what lets the retirement be questioned, and a card on
  hand needs its photograph for the pull preview. The control is in `#/inventory`'s **Manage
  box** sheet, gated like the box delete and shaped like the listing release — the free count
  (`GET /boxes/<box>/photos`) is on screen before the control that fires exists. What it gives
  up is named: D36's realign can no longer re-bind THOSE cards by digest, which is right for
  cards that have left the box, and the digest on the record is what the history keeps.
- **`emit` OVER SEVERAL RUNS WRITES ONE FILE, AND THE CAP IS SPENT ONCE ACROSS THEM** (D86).
  `pipeline/join.py:add_to_quantity` spends `live_cap - copies_out` per RUN against a cap that
  is GLOBAL, so runs joined before either emitted each believe the whole cap is theirs. This is
  D59's defect one register up — that entry fixed the per-BOX version inside one join, and the
  per-RUN version survived it because nothing had ever looked at two runs together.

  **Measured, from an identical cleared ledger over three real runs**: three separate emits
  wrote 6 files, 511 copies and **2 SKUs past the cap of 4** — the same two that sit at
  `pushed: 6` in the store today. One merged emit wrote 1 file, 437 copies and **none**.
  `pipeline/merge.py` re-derives the figure over the union of positions, deduped on
  `(box, index)`; **a merged file can never be a concatenation of the per-run CSVs.**

- **There is no automatic sectioning, and `CARDS_PER_SECTION` NO LONGER EXISTS** (D10,
  amended 2026-08-29 by the owner). A box's sections are the dividers somebody put in it and
  nothing else: an undeclared box renders as ONE section, `card` is the index, and
  `pipeline/join.py:Position.layout` falls back to `(1,)` — the divider at the front of every
  box. The 25-cards-per-divider default that used to render an undeclared box is deleted, so
  **the labels of every undeclared box moved once, deliberately** (the owner's box 1: 133
  cards, no dividers, drawn as six sections until this landed).

  **A divider is put in from the capture screen with `S`, at the moment the real one goes into
  the box** — `POST /boxes/<box>/sections`, which takes NO index because
  `store/master.py:open_section` reads `next_index` inside the store lock. The set hint moved
  to `H` to free the letter. A whole layout is still typed on `#/inventory`'s dividers editor;
  neither path ever invents a divider.

- **A box is addressed by its name, and names are unique** (D20, amended 2026-08-25). The
  capture screen's Box field is ONE free-text control searching number and name together, and a
  new box is created by name — `store/master.py:next_box_number` allocates the lowest free
  integer inside the lock, so there is no number to mistype and `new_box`'s typo guard is
  history. A duplicate name refuses `BoxNameTaken` / 409 `name_taken`; comparison folds case
  and strips, storage is verbatim. **`next_box_number` is deliberately NOT D10's high-water
  mark** — that rule governs the card index inside a box and nothing else. The name never
  enters `Position.label`: `app/tests/fulfillment.spec.ts` floors that label and D31 keeps the
  spec unweakened, so the name travels as `box_name` beside it instead.

  **A run carries the name the same way, and it is joined at read time** (D56). Every run on
  the wire has `box` and `box_name`, put there by `server/pipeline_routes.py:_summary` — the
  box from the manifest's scope or from its capture directory, the name from the registry as
  it stands right now. **Never write a name into a run directory**: a rename relabels every
  card in the box on every screen that draws one, and `cli/runs.py` makes a run an immutable
  input, so a stored name would be an answer nobody could correct. `app/src/runScope.ts` is
  the one place the client reads either — `Box 3 · RB Epics`, and `Box 3` ALONE where the box
  has no name, because a name is optional and a placeholder would draw a fault where there is
  none.

Deeper schema facts (Condition strings, secrets like `161/159`, blank-Number rows,
apostrophes in names) live in the `tcgplayer-csv` skill. It loads on demand.

## Hard rules

- **A route is not a feature. Nothing is built until it is reachable from a screen.**
  A capability that exists only in `server/` is not done, is not "landed", and must never be
  reported as either. Done means the whole chain: the route, a client function in
  `app/src/server.ts`, a control on the screen a human would look for it on, and — where it
  writes — its receipt and its way back. If a session ships the server half, the remaining
  half is not a follow-up, it is the unfinished part of the same task, and the session says
  so in those words.

  **The owner's instruction, 2026-08-23, after finding three tested routes no screen could
  reach**: box delete, mid-box delete-with-reindex, and retroactive box-level claims all
  existed with full T7 coverage and *zero* client functions. `make harness` was green,
  `make check` was green, and none of it could be used.

  This is the repo's own recorded failure repeating. `docs/GATES.md` step 7 tells it at
  length: 7b shipped with three screens missing from `App.tsx`'s ROUTES table while harness,
  lint, typecheck and docs-audit were all green, and only `make design-check` — which is
  deliberately NOT on the commit path — could tell. The finding it recorded then is the
  reason this rule exists now: **nothing on the path that decides whether a commit proceeds
  looks at whether a human can reach the thing you built.** So it has to be a rule someone
  reads, because it is not a check anything runs.

  Corollary for the report format below: a wrap-up that says BUILT about a server-only
  capability is wrong, not merely incomplete. It goes under NEITHER until a screen reaches
  it.

- Never guess an identification, a variant, or a price. Ambiguity goes to the review
  queue with its photo. Never silently drop a card.
- Never write output before reporting unmatched rows in both directions.
- Scope is argued, not gated. New surface area needs a reason and a decision entry — it no
  longer needs a gate to pass first, because none is open. This rule used to read "No new
  surface area until the current gate passes."
- No manual third-party UI step inside the autonomous pipeline. External tools without
  an API contract can be benchmarks, never components.
- **Opsec, repo-wide**: a live unredeemed code card is a bearer instrument. No code-card
  photo in a listing, README, screenshot, or commit. Enforced by pre-commit hook.
- **A screen answers to the system.** New CSS reads `--bn-*` tokens and never names a color;
  a primitive the kit already has is not rewritten in a screen sheet; a screen is verified at
  1440, 820 and 390, in light and in dark, before it is called done. **This rule replaces
  `docs/DESIGN.md`'s locked token table as the thing a session designs against** — that table
  still holds the Fulfillment view's floors, which are unchanged and still asserted by
  `make design-check`, but its color and type block records a palette the app no longer
  paints and `make docs-audit` says so on every run.
- **Main moves by pull request. A session never commits to it and never pushes it.**
  Work goes on a branch, the branch is pushed, `gh pr create` opens the PR, and it is merged on
  GitHub. `main` then advances in this clone by `git pull` and no other way.

  **A session merges on the owner's word, on GitHub and in this clone, as one operation**
  (D42, amended twice 2026-08-30). Explicit and per-instruction. **The test is whether the
  owner NAMED THE ACT** — "merge", "merge it", "merge to main" all are the word; "ship it",
  "land it", "looks good" and an approving review are not, because they approve the work
  without naming the operation.

  **One word, both halves, and a session does not stop in between to ask again**: `gh pr merge`,
  then the local fast-forward. If the second half fails, report it as an incomplete operation
  rather than re-asking for permission.

  **`make merge ARGS="<n> --confirm"` is that whole operation**, and `ARGS=<n>` alone previews
  it and presses nothing (D42, amended 2026-09-01). It does the GitHub half, fetches origin,
  asserts the merged commit is on `origin/main` — allow rule 3, checked BEFORE anything moves
  rather than discovered when the hook refuses — and then picks between the two local forms
  below by asking git rather than by remembering. **It automates the lookup and never the
  decision**: a bare `make merge` refuses, and the word is still yours.

  **The two commands stay written out here on purpose.** A wrapper that becomes the only way
  anybody knows the answer is a worse outcome than the one it fixed, and when it is not what
  you want, this is what you type.

  **The local half is two states, and one question tells them apart.** Ask which working tree,
  if any, holds main — a clone running several worktrees is in either state on any given day,
  and the command that is right in one is refused in the other:

  ```bash
  git worktree list --porcelain | awk '/^worktree /{w=$2} /^branch refs\/heads\/main$/{print w}'
  ```

  **Nothing printed — main is checked out nowhere.** Two commands, never the combined refspec
  alone: that form moves `refs/heads/main` and `refs/remotes/origin/main` in ONE transaction,
  which leaves the hook judging the move against the origin/main it is about to replace.

  ```bash
  git fetch origin && git fetch origin main:main
  ```

  **A path printed — main is checked out there.** The form above is what git itself refuses
  against a branch somebody is standing on (`fatal: refusing to fetch into branch
  'refs/heads/main' checked out at …`), and that refusal is GIT's rather than the hook's, so
  `PKMNSCAN_MAIN=off` answers nothing. Pull in that tree instead:

  ```bash
  git -C <that path> pull --ff-only
  ```

  **Never run that one without asking the question first.** It is correct only while main is the
  branch in that tree; run blind while the main working tree sits on a feature branch, it
  fast-forwards THAT branch, moves no protected ref, and so trips no hook.

  **It arms nothing.** `reference-transaction`'s allow rule 3 has always permitted a move to a
  commit origin already has, and a merged PR is exactly that commit — so this decides who runs
  an already-permitted move, not which moves run. **`PKMNSCAN_MAIN=off` is not what a session
  reaches for to do this**; a session typing that variable is doing something else.

  **This is enforced, not asked for** (D42): `scripts/githooks/reference-transaction` refuses
  any local move of `refs/heads/main` and `scripts/githooks/pre-push` refuses any push to it,
  both armed by `make hooks`. The escape hatch is `PKMNSCAN_MAIN=off` and it is printed in
  every refusal — reach for it rather than for `core.hooksPath`, which would take the three
  opsec rules down with it.

  **Why it is a hook and not a line in this file**: it already was a line nobody had written,
  and main moved under three live worktrees twice on 2026-08-29 — once by a local
  fast-forward, once by a direct push. GitHub's own branch protection is unavailable here (403,
  private repo on the free plan), so this is the substitute and not a belt-and-braces addition
  to it. A refusal is not a bug report: it means put the work on a branch.
## Working agreement

- Run `make harness` before you tell me something works. Show me the output, not a claim.
- **Show me the screen before you tell me it looks right.** Render it at 1440, 820 and 390 in
  both themes and look at the images. A screenshot you did not open is not verification, and
  the one thing a typecheck cannot tell you is whether the thing is any good.
- Read docs/DECISIONS.md before proposing an architecture change. Every entry there is
  settled; if you want to reopen one, say which entry and why, and wait for me.
- Report format: result first, then files touched, then risks. No task restatement, no
  summary of what I asked for.
- **Design work is repo work.** A design, a parameter derivation, or a determination that
  exists only in the conversation is NOT done — it lands in `docs/specs/` or a decision
  entry in the same session that produced it, or it is declared abandoned. The session
  that designed the motion trigger spent its tokens twice because the design lived in
  chat while the repo still said "not built, not specified"; this rule is that session's
  receipt. Corollary: **every wrap-up states what is BUILT, what is RECORDED, and what is
  NEITHER** — the same specified/built/validated vocabulary the gates already use, applied
  to the report itself. "Solved" with no bucket named is the phrasing this repo does not
  accept.
- When compacting: preserve the fixture schema facts, every `make` command, and the list of
  modified files. Drop exploration narration.

## Map

- `docs/map.py` — the repo as data: what is built, what is TBD, and which decisions govern
  each file. **Read this before editing anything under `app/`, `server/`, `pipeline/`,
  `identify/`, `store/`, `geometry/` or `cli/`** — every entry there is settled and
  re-litigating one wastes a session. Audited by `make docs-audit`, so it cannot quietly go
  stale: adding a file under any of those without an entry fails the commit.

  **`make map` is how you look at it, and there was no way to until 2026-08-31** (D80). At
  2,700 lines and ~56,000 tokens a Read of the whole file spends a fifth of a context
  window, so in practice it was written constantly and read never — 75 commits touched it on
  2026-08-30 alone. That asymmetry is not academic: its `COMPONENTS` section, which three
  consumers read, was measured at **142 of 155 entries written at or after the file they
  describe last moved**, while `TRACKS`, which NOTHING read, was wrong in two ways for three
  weeks. **A section of this file with no consumer is now a failed commit** — `make
  docs-audit`'s `map sections` row — because a claim with no reader has no way of ever being
  contradicted. `build order mirror` reconciles the step ids against `docs/GATES.md`'s two
  lists, per list and in both directions — a claim the map's header had made since
  2026-08-04 with nothing verifying it.

  **The build order is two lists, `SHIPPED` and `OPEN`, and it was one numbered list telling
  a lie its own shape forced on it until 2026-08-31** (D80). Rendered the only way a numbered
  list can be, `make status` said *"Build step 9 of 15"* — while 13, 14 and 15 were done, 9
  had been deferred by choice for a week, and everything from D34 onward had landed under no
  step at all. Every row was true; the sequence the numbering implied was not. `SHIPPED` is ordered
  by the date work landed, `OPEN` is **not ordered and has no `next`** — ranking two open
  items is yours, and "exactly one step is next" is what forced a false answer to it.
  **`n` is a stable id, never renumbered**: 218 references to `step <n>` live in this tree,
  74 of them `step 7`, and a renumber leaves every one pointing at a real step that is not
  the one meant — which nothing can detect, because a stale number still resolves. Steps 16
  to 19 were added for work that had landed with no step, and **step 12 was culled**, the
  only row ever removed: it named no deliverable and its "only then" pointed at the retired
  gating system.
- docs/DECISIONS.md — settled decisions and why. Read before redesigning.

  **These three are NOT `@`-loaded, and that is deliberate (D60).** At 627KB they cost
  ~163,000 tokens in every session before a word of work, and a session needs one entry
  at a time. Two mechanisms answer that without loading the file: `scripts/decision-context.py`
  names the governing decisions before any edit under the mapped directories, and the index
  below says what exists. **Read the entry itself before proposing an architecture change** —
  the index is a table of contents, never a substitute for the argument in the entry.

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
```

**D90 to D93 are MAIN's and arrived with the merge**, and three of the four are recorded here
without being adopted: the envelope walk and the copies picker were declined in favour of this
product's own per-copy walk and copy map, and the card-number sigil is deferred. D96 carries the
owner's reasoning for each. **D99 is numbered where it is because main took D90 while this branch
was open** — the rule is renumber your own, never another's.

- docs/GATES.md — gates, harness contract, `## What shipped` and `## What is open` (D80).
- `docs/DEBTS.md` — known gaps in the verification tooling, deliberately unfixed. Read it
  before treating a green `make docs-audit` as coverage: it means the checks that exist,
  passed. Nothing in it blocks anything; it exists so no session rediscovers it by surprise.
- `docs/specs/order-pipeline.md` — steps 8 to 14: an order arrives, a card is pulled, an
  envelope is stamped, tracking goes back. Every number in it was
  measured rather than carried forward — section 6 names what it could not check. **Those numbers
  are perishable and the file says so**: the store moved three times in two days, and §1 carries
  all three snapshots rather than the latest. Finding one stale means the store moved.
  **Steps 8 to 12 are BUILT as of 2026-08-30 (D69)**: `#/orders` resolves an order to the copies
  that fill it and pulls them, `#/shipping` routes a real export into three lanes, both reachable
  from the nav, and `server/order_transport.py` fetches this account's own orders over the cookie
  session D69 measured — `search` has run authenticated and returned three real orders.
  **`inventory/orders.json` has still never held a real one**, so "pulls a real order out of the
  ledger", which this pointer claimed until 2026-08-31, was a screen's capability read as a
  history. All forty-two sales in the store went through `#/inventory` instead, and §1 measures
  that. One piece INSIDE step 12 is also unbuilt — `POST /shipping/batches/<batch>/stamps`, the
  Rubber Stamp fill, §3's T2b. **Steps 13 and 14 — the shipped status and the tracking write-back — are
  NEITHER.** Their two endpoints were seen on the wire and deliberately not built. It said
  "Recorded, not built" and named three unreachable modules under `pipeline/` until D66's build
  order was discharged. **Its T6 — an order DRIVING the inventory walk, so the screen advances
  from card to card as each copy is pulled — is BUILT as of 2026-09-02 (D90), and the UNIT OF
  THE WRITE is the envelope rather than the card.** One press per order records every copy in
  it as pulled and sold; the walk itself writes nothing per card, and in order mode the next
  order is not offered until that press has landed. It is a second form of step 11 rather than
  a fifteenth step and gets no build-order row; §3 carries the three determinations, of which
  the one that bites is that the walk's control has to post the pull and not the sale. Its own
  open question — whether the queue survives a reload — is answered by the route parameter.
  Not `docs/specs/order-flow.md`, the sell path.
- `docs/specs/code-cards.md` — the code-card track end to end: the QR decode (BUILT, and
  measured at 140/140 physically-possible frames with zero mis-reads), the ledger (BUILT),
  the product claim that retires C2's OCR (BUILT), and the channel decision (RECORDED, and
  NOT executed — every researched venue came back marginal). Read its §8 before trusting a
  number: no real code card has ever been through this pipeline.
- `docs/specs/stale-listings.md` — the live listings that are not selling, marked down and
  pushed back (D100). SPECIFIED and BUILT, NOT VALIDATED: two commands, four routes, a screen
  and a harness block, and **no file it writes has ever been uploaded to TCGplayer**. Read its
  §2 before touching this path — the deletion question is answered there from 72,701 real
  export rows, and the doubling it is shaped to prevent already happened on this store. Read
  §3 before trusting the age it ranks on: it is how long the card has been OWNED, because
  `Listing` has no first-listed stamp and `live_as_of` is absent from all 443 stored payloads.
  §5 is the one section the Banchi rebuild moved — the screen is a modal now and the pixel
  measurement that refused it a route is history — and §6 names the three things the first
  real upload would measure.
- `docs/specs/batch-script.md` — the four commands, storage, routing, pricing. Built.
- `docs/specs/capture-app.md` — step 7. 7a (capture screen, undo, pull preview, one new
  server route) was built to it. 7b (review queue, Fulfillment view, inventory view,
  mark-sold, three more server routes) was built 2026-08-13 ahead of Gate B at the owner's
  explicit instruction; that schedule question is settled, and the spec's sections 0 and 9
  are marked overtaken rather than left reading as a prohibition over built code.
  **Gate B ran those screens on 2026-08-22 and most of the doubt is gone**: the capture
  screen drove a real feeder session, the review queue held 16 real entries and the owner
  answered every one, and the pull preview found a stored photo at its physical location.
  §10.2's measurements were taken and live in `docs/GATES.md`'s Gate B section.
  **Two things are still unexercised and its STATUS section names them**: the Fulfillment
  view against a real order, and the review screen's price-banded hierarchy against a
  mixed-value lot — that run's queue was uniformly sub-threshold, $0.04 to $0.40.
- `docs/specs/motion-trigger.md` — Gate C's auto-capture: built and self-tested 2026-08-22,
  tuned at the rig 2026-08-23, confirmed live at 85/85 on box 95, **rebuilt on
  measurements 2026-08-31 (D81)** and **corrected on three more 2026-09-01 (D84)**. Its §4 is
  the rig protocol; D19, D81 and D84 are the decisions.
  Read its STATUS before treating a green `make design-check` as evidence about the feeder —
  the TRIGGER half of Gate C is confirmed and the PIPELINE half is not: box 95's 85 records
  are all still `captured`, and no run directory exists for that box.

  **EVERY THRESHOLD IS A MULTIPLE OF SOMETHING THE SESSION MEASURED, and the constants that
  preceded them were portable to exactly one rig.** The card-present gate was a brightness
  against the constant 90; across four saved traces an empty stand reads 57 and a real card
  on another rig reads 61, so no constant separates them, and that one **refused 38 real
  cards as an empty stand, silently** across three sessions — 18 of them still refused after
  the 2026-08-29 "fix", which changed which brightness statistic the constant was compared
  against and rescued one session of three. Presence is the distance from the watch region as it
  stood when the trigger was armed — empty stand 1.1–1.4, cards 17–167 — and `tLo`/`tHi` ride
  the session's own median still-frame difference. The seed reproduces the hand-tuned
  4.50/8.00 exactly, so the 85/85 run is not re-litigated.

  **THE FIRST THREE SESSIONS RUN ON THAT MACHINE COST TWO JUNK PHOTOGRAPHS AND FOUR SILENTLY
  LOST CARDS, ALL IN THE FIRST TWO SECONDS AFTER ARMING** (D84). A settle is now `stillFrames`
  of the last `stillWindow` and not a consecutive run — a two-frame alternation defeats a run
  absolutely, and one did, on a card sitting motionless for 500 ms. The stall clock is cleared
  by a COMPLETED settle and not by any quiet frame, which is why `stalled` never fired across
  those four. **`presenceMin` is 16.0 and it BINDS**, so the sentence above is no longer true
  of the presence floor: what that floor has to clear is the operator's HAND arriving with the
  first card (8–11 on this rig), and no session statistic measures how big a hand is in frame.
  D84 records that as a debt rather than a design, and names the three quantities that
  re-derive it on a new rig — the idle stand, the worst approach, the quietest card.

  **`scripts/score-trace.py` is how a trace is scored, and it is not optional reading before
  changing a number here.** `summary`, `presence`, `sweep` and `contact` — the last one draws
  every verdict's frame, because the 2026-08-29 fix derived its "empty stand" brightnesses
  from twenty photographs of real cards nobody had looked at. **Arm on an empty stand**: what
  is in the watch region at arm time is what the session will call nothing. **And the trace is
  not the whole answer** — D84's four lost cards were only provable by downsampling the run's
  own JPEGs to the trace's 38x28 watch region and matching them frame against photograph. A
  trace says what the machine decided; only the photographs say what was there.
- `docs/DESIGN.md` — **two halves, and only one of them still describes this tree.** The
  Fulfillment view's hard constraints table is live, binding and asserted in a browser by
  `make design-check`: 20px body, 32px position labels, a 320px photograph, 44px targets, 7:1
  contrast, no jargon, and no route out of that view. The token block beside it records the
  palette and type of the sheet Banchi replaced; `app/src/tokens.css` is the system now, and
  `make docs-audit`'s `design tokens` row reports the disagreement on every run until the two
  are reconciled by someone who owns that file.
- `code-card-fork/CLAUDE.md` — the code-card track. Separate schema, separate channel.
- `fixtures/` — real TCGplayer exports. Ground truth. Never modify.
