# PKMNSCAN

Bulk-list pre-sorted Pokémon TCG singles on TCGplayer with zero attention per card and
physical location tracking. Two tracks share one rig: singles (this file) and code cards
(`code-card-fork/CLAUDE.md`, auto-loaded in that directory).

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
make hooks          # arm the three git hooks. Once per clone — core.hooksPath never travels.
make worktree-setup # in a fresh git worktree, FIRST. venv + T1's banked cache; neither
                    #   is tracked, so neither travels. Skipping it fails T1/T6/T7 with
                    #   three errors that never mention the worktree. The Browser pane's
                    #   port is NOT among them any more: the SessionStart hook writes
                    #   `.claude/launch.json` from this checkout's own slot before any work
                    #   starts, so a worktree can no longer preview the MAIN tree (D43).
make status         # where you are: next step, T1 score, branch. Start here.
make harness        # all seven verification tests; the Stop hook runs it at turn end
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
make lint           # eslint over app/: the guards a bug earned — see app/eslint.config.js. JS only.
make check          # harness + docs-audit + both self-tests + port-agreement +
                    #   screen-freshness + ignore-check + lint + vale + typecheck.
                    #   The line above said five of those nine for months.
make screen-freshness # every server write in app/src has a way back: a re-read, an
                    #   invalidation signal, or a reason in the code why none is owed.
                    #   Needs node, so it is in `check` and never in the git hook.
                    #   Finds nothing today — it guards write number 39.
make audit-self-test # the checker checks itself. In `check`, never in the git hook (D16/D18).
make icloud-sweep   # iCloud conflict copies (`foo 2.py`). ARGS=--delete removes the
                    #   byte-identical ones; a DIFFERING copy is only ever reported (D44).
make githooks-selftest # D42's guard over main, proved in a throwaway repo. Never in the git hook.

./pkmnscan scan     <capture-dir>   # CODE CARDS ONLY. Read the QR codes into the ledger.
                                   #   FREE — no model call, no network. The QR IS the code.
./pkmnscan identify <capture-dir>   # submit, wait, collect, cache. COSTS MONEY. --dry-run first.
./pkmnscan join     <run-dir>       # resolve against the export. Free, re-runnable.
                                   #   --dry-run  preview both queues, write nothing
                                   #   --bypass   trust the finish claim over the photo (D3)
./pkmnscan emit     <run-dir>       # write import CSVs. Free, re-runnable.
./pkmnscan reconcile <run-dir> <staged-export.csv>
```

## Things you will get wrong without being told

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
  photographs as unverified rather than treating its cards as gone.
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
- **Not a Claude artifact**: no `window.storage`, no `facingMode: "environment"`, and
  nothing about a card or the inventory in `localStorage`. Inventory state is server-side
  JSON; camera uses a device picker. Two devices share one truth. **The one exception is
  `app/src/useCamera.ts`**, which keeps two facts about THIS rig in `localStorage` — the
  chosen camera's `deviceId` and the capture rotation. Both are device-local by nature and
  would be wrong if shared; neither is inventory. Nothing lints this, so the argument lives
  in the comments beside the two keys.
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
  `--basis` are deliberately NOT on that screen** — D49 makes `decisions.json` the one place a
  pricing answer is written and `#/pricing` the press that writes it.

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
- **The app has ten screens and ten routes** — nine the owner's, one the Fulfiller's. It
  said six and six while `app/src/App.tsx` carried seven; D31 then merged two away —
  `#/boxes` and `#/pull` are gone, and both are modes of `#/inventory` now — D39 added
  `#/runs` back on 2026-08-29, which is the pipeline on a route of its own between Capture and
  the review queue, D49 added `#/pricing` on 2026-08-30, which is where a listing price is
  set by hand, and D69 added `#/orders` and `#/shipping` on 2026-08-30 — the order screen,
  which says which copies a buyer gets and where they are, and the shipping lane, which says
  which envelope an order goes in, out of a file the ledger has never seen. D70 added `#/codes` the same day — the code-card
  track, which shares the rig and nothing downstream (D14). **The count above was RECOUNTED
  from the `ROUTES` table rather than incremented**, which is the only way of arriving at it
  that has ever been right, and it was recounted again when these two branches met: each had
  incremented correctly against a tree the other had already moved.

  **THE COUNT IN THIS FILE HAS BEEN WRONG MORE OFTEN THAN IT HAS BEEN RIGHT, AND NOTHING
  CHECKS IT — and on 2026-08-31 it turned out the TESTS had the same disease.**
  `app/tests/cursor.spec.ts` swept "every route" off seven hashes typed out by hand and never
  saw `#/orders`, `#/shipping` or `#/codes`; `app/tests/nav.spec.ts` pinned the Cmd-arrow ring
  and missed `#/codes`. Three screens were asserted by nothing and `make design-check` was
  green, because a roster missing a route does not fail — it walks the routes it has. The
  cursor sweep reads the nav strip now, and `scripts/docs-audit.py`'s `route rosters` row
  fails a COMMIT where a spec's pinned list disagrees with `App.tsx`'s table. **That guard is
  over the specs and not over this sentence**: the number below is still checked by nobody. `scripts/docs-audit.py` reconciles no count of anything — D18 deleted the last
  published one on purpose, on the grounds that a verifiable fact nobody can disagree with is
  not load-bearing prose. That argument holds for a number in a report and does not hold here,
  where the sentence is what a session reads to learn the shape of the product. It was false
  from D39 until D49 in FIVE places at once, none of which failed a check, and it was still
  false in a sixth on 2026-08-30: `README.md`'s fenced screen list carried five entries and
  was missing `runs` and `pricing` outright, so D69's repair had to restore two screens
  before it could add two. The merged components survive as `BoxOps` and `BoxBrowse`; only their routes
  went. **The two movements are not in tension**: the merge deleted two routes rendering one
  thing, and the addition gave a route to something no route rendered.
  The shell renders no nav over the Fulfiller's, because `docs/DESIGN.md`'s constraints table
  forbids any route *out* of it, and the owner's nav would fail four other rows of the same
  table on its own. Not-rendered rather than hidden: not focusable, not reachable by a screen
  reader, not one specificity change from coming back.

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
```

- docs/GATES.md — gates, harness contract, build order.
- `docs/DEBTS.md` — known gaps in the verification tooling, deliberately unfixed. Read it
  before treating a green `make docs-audit` as coverage: it means the checks that exist,
  passed. Nothing in it blocks anything; it exists so no session rediscovers it by surprise.
- `docs/specs/order-pipeline.md` — steps 8 to 14: an order arrives, a card is pulled, an
  envelope is stamped, tracking goes back. Every number in it was
  measured rather than carried forward — section 6 names what it could not check.
  **Steps 8 to 12 are BUILT as of 2026-08-30 (D69)**: `#/orders` pulls a real order out of the
  ledger and `#/shipping` routes a real export into three lanes, both reachable from the nav,
  and `server/order_transport.py` fetches this account's own orders over the cookie session
  D69 measured. **Steps 13 and 14 — the shipped status and the tracking write-back — are
  NEITHER.** Their two endpoints were seen on the wire and deliberately not built. It said
  "Recorded, not built" and named three unreachable modules under `pipeline/` until D66's build
  order was discharged. **Its T6 — an order DRIVING the inventory walk, so the screen advances
  from card to card as each copy is pulled — is RECORDED and NEITHER, on the owner's want of
  2026-08-30.** It is a second form of step 11 rather than a fifteenth step; §3 carries the
  three determinations, of which the one that bites is that the walk's control has to post the
  pull and not the sale. Not `docs/specs/order-flow.md`, the sell path.
- `docs/specs/code-cards.md` — the code-card track end to end: the QR decode (BUILT, and
  measured at 140/140 physically-possible frames with zero mis-reads), the ledger (BUILT),
  the product claim that retires C2's OCR (BUILT), and the channel decision (RECORDED, and
  NOT executed — every researched venue came back marginal). Read its §8 before trusting a
  number: no real code card has ever been through this pipeline.
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
  and **Tuned at the rig on 2026-08-23** off the first 86-cycle feeder trace (`tLo` 3.0 → 4.5,
  `tHi` 6.0 → 8.0, which recovered 14 silently-missed cards), then confirmed live at 85/85 on
  box 95. Its §4 is the rig-tuning protocol; D19 is the decision. Read its STATUS before
  treating a green `make design-check` as evidence about the feeder — the TRIGGER half of
  Gate C is confirmed and the PIPELINE half is not: box 95's 85 records are all still
  `captured`, and no run directory exists for that box.
- docs/DESIGN.md — design tokens and the Fulfillment view's hard constraints.
- `code-card-fork/CLAUDE.md` — the code-card track. Separate schema, separate channel.
- `fixtures/` — real TCGplayer exports. Ground truth. Never modify.
