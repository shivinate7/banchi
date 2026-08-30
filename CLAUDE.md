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
"current gate" a session had to look up before it was allowed to build. See @docs/GATES.md.

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
                    #   edit Python under server/ store/ pipeline/ cli/ identify/ geometry/.
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
make check          # harness + docs-audit + both self-tests + lint + typecheck
make audit-self-test # the checker checks itself. In `check`, never in the git hook (D16/D18).
make icloud-sweep   # iCloud conflict copies (`foo 2.py`). ARGS=--delete removes the
                    #   byte-identical ones; a DIFFERING copy is only ever reported (D44).
make githooks-selftest # D42's guard over main, proved in a throwaway repo. Never in the git hook.

./pkmnscan identify <capture-dir>   # submit, wait, collect, cache. COSTS MONEY. --dry-run first.
./pkmnscan join     <run-dir>       # resolve against the export. Free, re-runnable.
                                   #   --dry-run  preview both queues, write nothing
                                   #   --bypass   trust the finish claim over the photo (D3)
./pkmnscan emit     <run-dir>       # write import CSVs. Free, re-runnable.
./pkmnscan reconcile <run-dir> <staged-export.csv>
```

## Things you will get wrong without being told

- **The join key is PER-GAME, and matching is normalised on both sides.** Pokemon composes
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
- **THERE IS NO AUTOMATIC SECTIONING, AND `CARDS_PER_SECTION` NO LONGER EXISTS** (D10,
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

- **A BOX IS ADDRESSED BY ITS NAME, AND NAMES ARE UNIQUE** (D20, amended 2026-08-25). The
  capture screen's Box field is ONE free-text control searching number and name together, and a
  new box is created by name — `store/master.py:next_box_number` allocates the lowest free
  integer inside the lock, so there is no number to mistype and `new_box`'s typo guard is
  history. A duplicate name refuses `BoxNameTaken` / 409 `name_taken`; comparison folds case
  and strips, storage is verbatim. **`next_box_number` is deliberately NOT D10's high-water
  mark** — that rule governs the card index inside a box and nothing else. The name never
  enters `Position.label`: `app/tests/fulfillment.spec.ts` floors that label and D31 keeps the
  spec unweakened, so the name travels as `box_name` beside it instead.

  **A RUN CARRIES THE NAME THE SAME WAY, AND IT IS JOINED AT READ TIME** (D56). Every run on
  the wire has `box` and `box_name`, put there by `server/pipeline_routes.py:_summary` — the
  box from the manifest's scope or from its capture directory, the name from the registry as
  it stands right now. **Never write a name into a run directory**: a rename relabels every
  card in the box on every screen that draws one, and `cli/runs.py` makes a run an immutable
  input, so a stored name would be an answer nobody could correct. `app/src/runScope.ts` is
  the one place the client reads either — `Box 3 · RB Epics`, and `Box 3` ALONE where the box
  has no name, because a name is optional and a placeholder would draw a fault where there is
  none.
- **The app has seven screens and seven routes** — six the owner's, one the Fulfiller's. It
  said six and six while `app/src/App.tsx` carried seven; D31 then merged two away —
  `#/boxes` and `#/pull` are gone, and both are modes of `#/inventory` now — D39 added
  `#/runs` back on 2026-08-29, which is the pipeline on a route of its own between Capture and
  the review queue, and D49 added `#/pricing` on 2026-08-30, which is where a listing price is
  set by hand.

  **THE COUNT IN THIS FILE HAS BEEN WRONG MORE OFTEN THAN IT HAS BEEN RIGHT, AND NOTHING
  CHECKS IT.** `scripts/docs-audit.py` reconciles no count of anything — D18 deleted the last
  published one on purpose, on the grounds that a verifiable fact nobody can disagree with is
  not load-bearing prose. That argument holds for a number in a report and does not hold here,
  where the sentence is what a session reads to learn the shape of the product. It was false
  from D39 until D49 in FIVE places at once, none of which failed a check. The merged components survive as `BoxOps` and `BoxBrowse`; only their routes
  went. **The two movements are not in tension**: the merge deleted two routes rendering one
  thing, and the addition gave a route to something no route rendered.
  The shell renders no nav over the Fulfiller's, because `docs/DESIGN.md`'s constraints table
  forbids any route *out* of it, and the owner's nav would fail four other rows of the same
  table on its own. Not-rendered rather than hidden: not focusable, not reachable by a screen
  reader, not one specificity change from coming back.

Deeper schema facts (Condition strings, secrets like `161/159`, blank-Number rows,
apostrophes in names) live in the `tcgplayer-csv` skill. It loads on demand.

## Hard rules

- **A ROUTE IS NOT A FEATURE. Nothing is built until it is reachable from a screen.**
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
- **MAIN MOVES BY PULL REQUEST. A SESSION NEVER COMMITS TO IT AND NEVER PUSHES IT.**
  Work goes on a branch, the branch is pushed, `gh pr create` opens the PR, and it is merged on
  GitHub. `main` then advances in this clone by `git pull` and no other way.

  **A SESSION MERGES ON THE OWNER'S WORD, ON GITHUB AND IN THIS CLONE, AS ONE OPERATION**
  (D42, amended twice 2026-08-30). Explicit and per-instruction. **The test is whether the
  owner NAMED THE ACT** — "merge", "merge it", "merge to main" all are the word; "ship it",
  "land it", "looks good" and an approving review are not, because they approve the work
  without naming the operation.

  **One word, both halves, and a session does not stop in between to ask again**: `gh pr merge`,
  then the local fast-forward. If the second half fails, report it as an incomplete operation
  rather than re-asking for permission.

  **THE LOCAL HALF IS TWO STATES, AND ONE QUESTION TELLS THEM APART.** Ask which working tree,
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
- Read @docs/DECISIONS.md before proposing an architecture change. Every entry there is
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
- @docs/DECISIONS.md — settled decisions and why. Read before redesigning.
- @docs/GATES.md — gates, harness contract, build order.
- `docs/DEBTS.md` — known gaps in the verification tooling, deliberately unfixed. Read it
  before treating a green `make docs-audit` as coverage: it means the checks that exist,
  passed. Nothing in it blocks anything; it exists so no session rediscovers it by surprise.
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
  and **TUNED AT THE RIG on 2026-08-23** off the first 86-cycle feeder trace (`tLo` 3.0 → 4.5,
  `tHi` 6.0 → 8.0, which recovered 14 silently-missed cards), then confirmed live at 85/85 on
  box 95. Its §4 is the rig-tuning protocol; D19 is the decision. Read its STATUS before
  treating a green `make design-check` as evidence about the feeder — the TRIGGER half of
  Gate C is confirmed and the PIPELINE half is not: box 95's 85 records are all still
  `captured`, and no run directory exists for that box.
- @docs/DESIGN.md — design tokens and the Fulfillment view's hard constraints.
- `code-card-fork/CLAUDE.md` — the code-card track. Separate schema, separate channel.
- `fixtures/` — real TCGplayer exports. Ground truth. Never modify.
