"""The repo, as data. One Read answers "what is built, what is TBD, what governs this file".

Written because that question kept costing a subagent sweep and a quarter-million tokens to
re-derive from prose that already knew the answer. `docs/GATES.md` has the build order,
`docs/DECISIONS.md` has the rulings, `README.md` has the layout — but all three are prose,
and prose has to be read in full before it can be trusted.

Read by four consumers, which is the reason it is data and not another markdown section:

  scripts/status.py           `make status` — the human view. THE ONE A PERSON RUNS, and it
                              was missing from this list from 2026-08-13 to 2026-08-31 while
                              being the answer to "how do I look at this file"
  scripts/docs-audit.py       its repo-map check verifies every claim below against the tree
  scripts/decision-context.py the PreToolUse hook that tells you which decisions govern a
                              file before you edit it
  you, or an agent            `make map` renders it — a package, a path, or a decision id.
                              Read the raw literals only when you want the argument in a
                              `note`, which is the half no renderer can summarise

THE COUNT ABOVE IS CHECKED. `make docs-audit`'s `map sections` row fails a commit where a
top-level name here is read by nothing, and where this docstring's consumer list disagrees
with the readers it can find. `TRACKS` is why: it sat here from 2026-08-07 to 2026-08-31
with no reader and no check, went wrong twice — `C1-C7` against a file that had reached C11,
and a codes track "gated on singles Gate B" months after Gate B passed and the gating system
was retired — and nothing anywhere could tell. A section nobody reads is not free; it is a
claim the repo makes about itself with no way of being wrong out loud.

THIS FILE GOES STALE LIKE ANY OTHER DOC, so it is audited like one. The repo-map check
fails when a `built` path is missing, when a `planned` path has quietly arrived, when a
`governed_by` cites a decision that does not exist, and — the one that actually keeps this
honest — when a source file exists that no entry here mentions. Adding a module without
touching this file fails the commit.

`governed_by` is a superset of the `D<n>` citations in the file's own comments; the
repo-map check enforces that direction. Entries beyond the citations are curated:
`pipeline/pricing.py` never says "D8" in a comment, but D8 is what makes the TCGplayer
export the only pricing source, and someone editing that file needs to know.

Pure literals only — no imports, no computation. scripts/docs-audit.py reads it with
`ast.literal_eval` rather than importing it, for the same reason it parses everything else
that way: an audit must not run project code.
"""

# ------------------------------------------------------------------ what shipped, what is open
#
# TWO LISTS, BECAUSE ONE LIST WAS TELLING A LIE ITS OWN SHAPE FORCED IT TO TELL. This was a
# single numbered `BUILD_ORDER` with a `status` field until 2026-08-31, and `make status`
# rendered it the only way a numbered list can be rendered — "Build step 9 of 15" — while
# steps 13, 14 and 15 were done, step 9 had been deferred by choice for a week, and
# everything from D34 onward had landed with no step at all. Every individual row was true. The SEQUENCE
# the numbering implied was not, and no amount of correct rows fixes a shape that lies.
#
# So `status` is gone and the list a step is in IS its status. `SHIPPED` is ordered by the
# date the work landed and `on` carries that date. `OPEN` is not ordered at all and has no
# `next`: ranking two open items is the owner's call, and the old "exactly one is next" rule
# is precisely what forced a false answer to it — step 9 held `next` for nine days across
# two owners' worth of re-sequencing while the actual work went elsewhere.
#
# `n` IS A STABLE ID AND IS NEVER REUSED OR RENUMBERED. Not for tidiness — 218 references to
# `step <n>` live in this tree, across CLAUDE.md, README.md, .claude/settings.json, six
# specs, docs/DECISIONS.md, harness code and Playwright specs, and 74 of them say `step 7`.
# A renumber would leave every one of them pointing at a real step that is not the one meant,
# which is D72's citation drift with nothing able to detect it — after a renumber the stale
# number still resolves. So the ids here are out of order in `SHIPPED` (11 landed before 4)
# and there is a hole where 12 was, and both are correct.
#
# STEP 12 WAS CULLED, and it is the only row ever removed from this list. It read "Scale,
# polish, deferred list" and was never a step: it named no deliverable, its `Only then:`
# premise in docs/GATES.md pointed at the gating system retired on 2026-08-23, and it then
# spent a week `blocked` on step 9 — a dependency invented on its behalf to keep it from
# claiming a blocker that no longer existed. The deferred list it named lives in
# docs/DECISIONS.md and is that file's to open or close.
#
# `make docs-audit`'s `build order mirror` row checks the ids in both lists against the two
# lists in docs/GATES.md, in both directions. A step landing in one file and not the other
# fails the commit, which is what makes culling and adding a two-file edit rather than a
# four-file one — the reason docs/GATES.md gave for appending rather than inserting.

SHIPPED = [
    {"n": 1, "on": "2026-07-26", "title": "Repo init, fixtures committed, git from commit zero",
     "note": ""},
    {"n": 2, "on": "2026-07-26", "title": "Scaffolding: Makefile, hooks, screenshot script, failing harness",
     "note": ""},
    {"n": 3, "on": "2026-07-26", "title": "Verification harness T1-T4",
     "note": ""},
    {"n": 11, "on": "2026-08-03", "title": "pokemontcg.io API key",
     "note": "done 2026-08-03; step 9 removes the need for it."},
    {"n": 4, "on": "2026-08-03", "title": "Batch script v2: Batch API, variant ladder, catalog join",
     "note": "code done 2026-08-03, harness green T1-T6. Never run against a real card \u2014 that is Gate "
              "B."},
    {"n": 5, "on": "2026-08-11", "title": "Capture server: POST /capture, sidecars, /status, photo service, inventory state",
     "note": "code done 2026-08-11, spec at docs/specs/capture-server.md. Shipped with no harness "
              "coverage; T7 closed that 2026-08-13 \u2014 every route, every named refusal, and the sidecar "
              "seam. What it still does not reach is in docs/DEBTS.md."},
    {"n": 6, "on": "2026-08-12", "title": "Design tokens locked, one component built against them",
     "note": "tokens locked 2026-08-12 by interview; the pull-confirm built against them 2026-08-12 at "
              "app/src/PullConfirm.tsx, rendered by `make screenshot` and asserted by `make "
              "design-check`. Building it caught two places where docs/design-refs/locked.html "
              "disagrees with docs/DESIGN.md \u2014 see that directory's README."},
    {"n": 7, "on": "2026-08-13", "title": "Vite capture app: device picker, capture, inventory, review queue, Fulfillment view",
     "note": "BOTH HALVES BUILT 2026-08-13 on branch step-7-capture-app. 7a is "
              "docs/specs/capture-app.md's scope \u2014 the shell and its three routes, the capture screen, "
              "undo, the pull preview, the trigger seam, the eslint rules, and DELETE "
              "/inventory/<box>/<index>. 7b is the review queue, the Fulfillment view, the inventory "
              "SKU view and mark-sold, plus three more server routes (GET /queues, POST "
              "/review/<box>/<index>/answer, POST /inventory/<box>/<index>/sold). 7b WAS BUILT BEFORE "
              "GATE B, WHICH ITS OWN SPEC FORBIDS, at the owner's explicit instruction; that spec's "
              "STATUS section carries what it costs and its sections 0 and 9 are left standing and "
              "marked overtaken. That short form USED to be that 7b's screens display data no run has "
              "ever produced; Gate B ran them 2026-08-22 and it is no longer true. The review queue "
              "held 16 real entries and the owner answered every one. What survives of it is narrower "
              "and still real: all 16 carried ONE reason code of twelve, and the whole run priced "
              "$0.04-$0.40, so the price-driven row hierarchy has still never seen the mixed-value list "
              "it sorts for. THIS ROW IS `done` AND STEP 8 IS `next`, which the previous note called "
              "the owner's call to make on the day rather than by editing this file. It is made now "
              "because nothing is left to build: with 7b shipped there is no remaining step-7 scope for "
              "`next` to point at, and `make status` sending whoever runs it to a physical twenty-card "
              "run against a build that has never met a card is now an accurate instruction rather than "
              "a premature one. WIRED 2026-08-13, in a pass after the build: all three screens are "
              "registered in app/src/App.tsx's ROUTES table, app/src/server.ts carries a client "
              "function per new route, and the shell draws no nav over the Fulfillment view. `make "
              "design-check` went from 16 failures to 30 of 30 passing on that change alone \u2014 every one "
              "of those failures was the unregistered route, exactly as the spec was written to report. "
              "See the app/ entry below."},
    {"n": 8, "on": "2026-08-22", "title": "Gate B smoke test, 20 cards end to end",
     "note": "PASSED 2026-08-22, and over-delivered: 53 real ME01 cards through the feeder, 53/53 "
              "identified once the frames were stored upright, joined, emitted, staged on TCGplayer "
              "through two clean reconcile round trips, and the pull preview showed the right photo at "
              "the right physical location. Six defects were found by the run and fixed the same day \u2014 "
              "the Batch API custom_id refusal, the capture canvas leak, the idle-scheduled JPEG "
              "encoder, the cross-queue release leak, review answers that nothing consumed, and the "
              "post-import re-emit double-count. THREE OF THE SIX CARRY A REGRESSION TEST, each "
              "observed failing against the old code before the fix was restored: the cross-queue "
              "release leak in T7, and the last two in T3. The other three carry none, and the reason "
              "is structural rather than an oversight \u2014 _custom_id lives in cli/cmd_identify.py and no "
              "harness case names it, and the two capture-latency fixes are in app/, which no harness "
              "test reaches at all (this file's app/ entry says so in its own note). docs/GATES.md's "
              "Gate B section carries the run's measurements."},
    {"n": 10, "on": "2026-08-22", "title": "Feeder integration (Gate C)",
     "note": "THIS STEP WAS GATE C \u2014 its original `blocked_by: Gate C` named the gate that IS this "
              "work, a circularity that was harmless while Gate B was open and stopped being so when it "
              "passed. BUILT 2026-08-22: the motion trigger at app/src/motion.ts behind trigger.ts's "
              "seam, a mode toggle and HUD on the capture screen, and both a machine spec and a live "
              "browser spec in app/tests. TUNED AND RUN AT THE RIG, which is the half that could not be "
              "built and is why this row is `done` rather than `done except the physical part`: Gate C "
              "passed and docs/GATES.md carries what it measured. docs/specs/motion-trigger.md is the "
              "spec."},
    {"n": 13, "on": "2026-08-23", "title": "Order flow, boxes, and search",
     "note": "D7's fungible copies, D20's box object with its retroactive capacity, D10's per-box "
              "sections, and the search-and-sell screens. THIS ROW CARRIED AN `Outstanding` LIST OF "
              "FIVE ITEMS THAT WERE ALL ALREADY ON DISK, and it stayed `next` for a day after there was "
              "nothing left in it to build. Re-derived by grep on 2026-08-24 rather than from the "
              "previous note, which is the same correction docs/GATES.md's own step 13 records making: "
              "D26's retire and re-shoot have routes AND client functions AND controls, D27's "
              "sessionStorage is in CaptureScreen.tsx, D28's answer undo is in server.ts, D29's group "
              "answer has do_review_group_answer and answerReviewGroup, and D30's gap convention ships "
              "as `neighbors` and `section_gaps` on every located card. D31 then merged #/boxes and "
              "#/pull into #/inventory, so the screens this step names by their old routes are modes of "
              "one. A STALE `next` IS WORSE THAN A STALE `done`, which is why this row is worth a note "
              "rather than a one-word edit: `make status` reads this field to answer \"do this next\", so "
              "a step that is finished and still says `next` sends every session that asks to re-audit "
              "work that is already committed."},
    {"n": 14, "on": "2026-08-24", "title": "Multi-game: four capture choices plus misc",
     "note": "D21-D25. pipeline/games.py behind four real TCGplayer exports, four audit rows, per-game "
              "dispatch, `game` through all ten capture hops with the picker on the capture bar, the "
              "rarity claim end to end, the repeatable --export with per-game catalogs and one import "
              "file per game (D25), pooled non-located inventory with both opsec discharges, and "
              "per-game finalisation \u2014 riftbound_card_v1 and one_piece_card_v1 exist, are registered "
              "and carry parsers. THE RARITY CLAUSE WAS BUILT, MEASURED, AND SWITCHED OFF because it "
              "lost: holdout 0.9706 -> 0.9559 for $0.17, with high-confidence misses up two. The "
              "claim's other two jobs \u2014 the ladder cross-check and the chip narrowing \u2014 are what D23 "
              "now rests on. pokemon_card_v1 did not move: 1ef974bf511d, unchanged, because "
              "prompt_fingerprint hashes ONE profile's fields. WHAT NO AMOUNT OF CODE CLOSES: neither "
              "new game has met a card. The store holds zero Riftbound and zero One Piece records, so "
              "every claim about those two prompts is a claim about a CSV and a schema, not about a "
              "photograph."},
    {"n": 15, "on": "2026-08-24", "title": "The pipeline seam: the four commands, reachable from a screen",
     "note": "D33, built 2026-08-24. THE LARGEST INSTANCE OF CLAUDE.md's route-is-not-a-feature RULE "
              "THIS REPO HAS HAD, and nobody had counted it: the four commands have existed since step "
              "4 and have been through a 53-card run and a 544-card run, and until this step they could "
              "be reached only by typing at a terminal \u2014 which docs/GATES.md names as what Gate B did "
              "not close. server/pipeline_routes.py is its own module because it is the one part of the "
              "server that can cause money to be spent: ONE route does, it is named for it, it refuses "
              "without an explicit confirm, and it refuses a second run over a capture directory a live "
              "run is already reading. The preflight beside it is free and creates no run directory at "
              "all. Everything else \u2014 the reads, and join/emit/reconcile \u2014 is free and re-runnable, "
              "which is the property D1 gave the two-phase split. THE MONEY STEP SPAWNS DETACHED AND IS "
              "NEVER AWAITED, so a run outlives a restart of the server that started it; the free steps "
              "answer inside the request with their own stdout attached. app/src/RunPanel.tsx drew it "
              "UNFOLDED on #/inventory \u2014 sharing one .browse-boxrun row with BoxOps, because the owner "
              "overruled the fold on 2026-08-24 (D33, amended). IT HAS BEEN ON #/runs SINCE 2026-08-29 "
              "(D39), and this row is left saying so rather than rewritten to have always meant that: "
              "what step 15 built is the seam, and the address it was first reachable at is part of "
              "what it built. The .browse-boxrun row it left is not empty \u2014 src/BoxRuns.tsx holds a "
              "status line there and nothing that spends. What survived the move is the UNFOLDING, "
              "which was the owner's ruling; the route is what changed under it. "
              "app/tests/run-panel.spec.ts is the check the hard rule says does not exist."},
    {"n": 16, "on": "2026-08-30", "title": "Hand pricing: the price a listing goes out at, set by a person",
     "note": "D49, D54, D59, D62, D78. #/pricing is a worklist of one row per SKU with the deliberate "
              "holds D49 rules on, the price history D62 puts beside the hold, D59's per-SKU live cap, "
              "and D54's re-emit that adds and never subtracts. NOT BUILT: nothing prices automatically "
              "and nothing here reads a market. D8 makes the TCGplayer export the only price source and "
              "that is unchanged \u2014 this step is where a human overrides it, one row at a time."},
    {"n": 17, "on": "2026-08-30", "title": "The order pipeline: the ledger, the order screen, the shipping lane",
     "note": "D48, D61, D63, D64, D65, D66, D69, D71. Steps 8 to 12 of docs/specs/order-pipeline.md: "
              "D63's two-map ledger, D64/D65's fetched Filtered Export with completeness as a delta "
              "rather than a claim, #/orders saying which copies a buyer gets and where they are, and "
              "#/shipping routing a real export into D61's three lanes \u2014 the third of which is 'I "
              "cannot tell'. server/order_transport.py fetches this account's own orders over the "
              "cookie session D69 measured before it was written. WHAT THIS STEP DID NOT DO is step 20: "
              "the shipped status and the tracking write-back. Both endpoints were seen on the wire and "
              "deliberately not built, and that is a step of its own below rather than a footnote here."},
    {"n": 18, "on": "2026-08-30", "title": "The code-card track reaches a screen",
     "note": "D70, D14, D24, and C1-C11. The QR decode measured at 140 of 140 physically-possible "
              "frames with zero mis-reads at 87ms each, the ledger with C3's atomic dequeue, the "
              "product claim that retired C2's OCR, and #/codes. The primary path is D2's opposite in "
              "every respect: local, deterministic, free, and loudly absent rather than confident. NOT "
              "DONE, and docs/specs/code-cards.md section 8 says it in these words: NO REAL CODE CARD "
              "HAS EVER BEEN THROUGH THIS PIPELINE \u2014 every measurement in the track is synthetic. The "
              "channel decision is RECORDED AND NOT EXECUTED; six venue families were researched and "
              "every one came back marginal, which is what the track is actually waiting on."},
    {"n": 19, "on": "2026-08-31", "title": "The rig's guards, and the docs that check themselves",
     "note": "D42, D43, D44, D47, D53, D60, D72, D73, D74, D80. Not a feature and it is a step anyway, "
              "on the same footing as steps 1-3: main moves only by pull request with two local git "
              "hooks standing in for branch protection GitHub will not sell on this plan, every "
              "checkout gets its own store AND its own ports so a worktree can no longer answer the "
              "main tree's capture screen, one link that is always live with the supervisor re-execing "
              "itself, and the audit rows that keep this file and its siblings from drifting. THE "
              "REASON IT IS LISTED: it was a week of work that no step accounted for, so the build "
              "order read as if nothing had happened since 2026-08-24 while `make status` reported step "
              "9 of 15."},
    {"n": 21, "on": "2026-09-01", "title": "The store of record is SQLite, and a sold card's photograph is reclaimed",
     "note": "D88, D89. One SQLite file replaces the five JSON documents and the history log; every "
              "Store.write() is one transaction over every table, so the five-file torn set is "
              "cannot happen; and a session loads only the rows it names. MEASURED on a synthetic "
              "100,000-card copy of the owner's store: a capture's store cycle went from ~4.4 s under "
              "the JSON files to ~3 ms, building one card object. The owner's real store migrated "
              "without loss in 0.13 s, six files moved to legacy-json/ with a receipt. D89 is the third "
              "shape between capture-undo and the terminal states — record kept, photograph reclaimed, "
              "digest kept — on #/inventory's box operations, gated like the delete. WHAT THIS STEP DID "
              "NOT DO: the 2,000-card probe that decides whether the 100k run is worth making is work "
              "at the rig and has not been run; nothing here measures the pile."},
]

OPEN = [
    {"n": 9, "title": "Vendor the pokemontcg.io catalog: snapshot, SQLite index, image mirror",
     "was_blocked_by": "step 13, which is done as of 2026-08-24 \u2014 the sequencing was the owner's and never "
              "technical, so finishing 13 is what released it",
     "note": "THE GATE DEPENDENCY WAS RETIRED, NOT SATISFIED, and the difference matters to anyone "
              "reading this row later. This step carried `blocked_by: Gate C` from 2026-08-22, when the "
              "owner re-sequenced it behind motion capture \u2014 not because anything here conflicts with "
              "that work (it touches no app code) but because one `next` is the rule and he chose "
              "which. On 2026-08-23 the owner retired the gating system outright: A, B and C have all "
              "passed, docs/GATES.md is a record of runs rather than a schedule, and no step may be "
              "blocked behind a gate any more because none is open. So the blocker was removed by the "
              "gates ceasing to be a schedule, NOT by Gate C being cleared out of this step's way. "
              "There is deliberately no Gate D. Nothing waits on this but the doing of it: snapshot the "
              "repo, build the SQLite index (cards join to sets by FILENAME \u2014 printedTotal lives only "
              "in sets/en.json and is half the join key), then fill the image mirror with the "
              "Content-Length dry run first. D15."},
    {"n": 20, "title": "The shipped status and the tracking write-back",
     "note": "Steps 13 and 14 of docs/specs/order-pipeline.md, and the only part of that spec that is "
              "NEITHER built nor merely unproven. Both endpoints were seen on the wire while D69 was "
              "being measured and were deliberately left alone: writing a tracking number back is the "
              "first thing this project would do that a buyer sees, and D69 ruled that the screen comes "
              "before the transport. Nothing blocks it but the doing of it."},
]

# --------------------------------------------------------------------------------- gates

# status: passed | next | blocked. This vocabulary OUTLIVED the build order's, which was
# deleted on 2026-08-31 (D80) when the list became SHIPPED and OPEN. It survives here
# because a gate genuinely was a sequence — A then B then C — and all three passed.

GATES = [
    {"gate": "A", "status": "passed", "on": "2026-07-26",
     "what": "TCGplayer seam: Level 4, SV09 fixture, 2-row Import to Staged end to end"},
    {"gate": "B", "status": "passed", "on": "2026-08-22",
     "what": "53 real cards end to end — capture through staged listings and the pull preview, "
             "finish detection measured against the whole lot instead of ten staged photos"},
    {"gate": "C", "status": "passed", "on": "2026-08-22",
     "what": "feeder integration: motion state machine, 50-card run, then a full box",
     "why_it_matters": "the feeder already ran Gate B at manual-trigger pace, so this gate "
                       "tunes a trigger against a rhythm the run has now demonstrated."},
]

# THE LIST ABOVE IS A RECORD AND NOT A SCHEDULE, as of 2026-08-23. All three gates have
# passed, CLAUDE.md no longer names a current gate, and docs/GATES.md is what was measured
# rather than what is owed. THERE IS NO GATE D, and its absence is the decision rather than
# an omission — do not add one because this list looks unfinished without an open row.
#
# THE LIST IS KEPT, AND KEPT AUDITED, WHICH IS THE POINT. `check_map` still reconciles every
# row here against the `### Gate X` headings in docs/GATES.md and against their PASSED
# markers, so the history cannot quietly drift: a gate that never happened cannot appear
# here, and one that did cannot be edited into having gone differently. Deleting the list
# would retire the check along with the schedule, and only one of those two had stopped
# earning its place.

# ---------------------------------------------------------------------------- components
#
# status: built | stub | planned
#   built    code exists. `tested_by` names the harness tests that reach it, where any do
#   stub     the file exists and deliberately does nothing yet
#   planned  no file yet; `step` says what creates it. The repo-map check FAILS if it
#            exists, which forces the entry to be updated the day it is written.
#
# `step` links an entry to the build-order step whose work happens there — the step that
# creates it while the entry is `planned`, and the step still to be done in it once it is
# `built`. scripts/status.py resolves "do this next" through that field, and prints a dead
# end without it: `app/` was built by step 6 and carries `step: 7` because that is where
# step 7's screens go.

COMPONENTS = [
    {
        "path": "cli/",
        "status": "built",
        "does": "argument parsing and sequencing for the four commands. No rules live here.",
        "governed_by": ["D1", "D3", "D4", "D7", "D9", "D10"],
        "note": "NO INTERACTIVE PROMPTS, ever — the pipeline runs unattended, so a command "
                "that cannot proceed refuses and says what to edit.",
        "modules": {
            "__main__.py": {"does": "parser, COMMANDS dispatch, exit codes", "governed_by": ["D1", "D3", "D9", "D25", "D86", "D87", "D100"], "tested_by": ["T7"]},
            "cmd_scan.py": {"does": "read the QR codes off a directory of code-card photos into "
                                    "the ledger. FREE — no model call, no network, no money gate "
                                    "(C9). Presentation only; the core is `codes/scan.py`, shared "
                                    "with the route so the CLI and the screen cannot disagree. "
                                    "NOT `tested_by` T8, and the distinction is the audit's "
                                    "own: T8 imports `codes/scan.py` and never this file, so "
                                    "what is covered is the reading and the write, while the "
                                    "argument parsing and the printed report here are not.",
                            "governed_by": ["D14", "D21", "D24"]},
            "cmd_identify.py": {"does": "submit, wait, collect, cache. The one that costs money.", "governed_by": ["D1", "D2", "D21", "D23"]},
            "cmd_join.py": {"does": "resolve identifications against the export; --dry-run previews. "
                                    "SEEDS inventory/prices.json's rule and basis on the first "
                                    "join of an EMPTY corpus and never reassigns them (D49, D86) "
                                    "— the two lines that did ran under the sentence promising "
                                    "your edits were kept. REFUSES on a legacy decisions.json "
                                    "before anything is read or written, naming `prices adopt "
                                    "--write`, and names the store's standing sub-threshold "
                                    "policy on its own line every join (D9 amended 2026-09-02). "
                                    "Writes `live` only where the export is NEWER than the "
                                    "store's own reading — `Listing.observe_live`, per game, "
                                    "against the file's mtime — and says what it kept, by SKU "
                                    "with both readings (D87 amended). Partitions at the corpus's stored `policy.threshold` (D99).",
                            "governed_by": ["D3", "D7", "D8", "D9", "D11", "D16", "D25", "D34", "D36", "D49", "D54", "D58", "D59", "D86", "D87", "D99"], "tested_by": ["T4", "T7"]},
            "cmd_prices.py": {"does": "`pkmnscan prices adopt` folds every run's legacy "
                                      "decisions.json into the corpus — previews unless given "
                                      "--write, newest-wins, and NAMES the holds a later price "
                                      "replaced rather than counting them — and RETIRES each "
                                      "folded file to decisions.json.adopted (D86 amended "
                                      "2026-09-02). A re-adopt over already-answered SKUs keeps "
                                      "the corpus's answers and retires without --force; --force "
                                      "folds the files OVER the corpus, never into a fresh one. "
                                      "`prices show --held` "
                                      "is the cross-run view of what is being held that D49 "
                                      "named as missing and D62 repeated.",
                              "governed_by": ["D9", "D49", "D62", "D86"],
                              "tested_by": ["T7"]},
            "cmd_reprice.py": {"does": "`pkmnscan reprice list` reports which live listings are "
                                        "not selling and writes a WORKLIST with a price already "
                                        "proposed on every row; `reprice apply` reads the "
                                        "operator's edited worklist back and writes the "
                                        "price-only import CSV (D100). Both preview unless given "
                                        "--write. EVERY ROW OF EVERY FILE IT WRITES CARRIES `Add "
                                        "to Quantity` 0, and the upload is built from the "
                                        "manifest's copy of the export row rather than from the "
                                        "file handed back — only TCGplayer Id and TCG "
                                        "Marketplace Price are read out of that, so a "
                                        "spreadsheet's reformatting cannot reach TCGplayer. "
                                        "Writes into inventory/markdowns/<stamp>/ and never "
                                        "under runs/: a run directory is one box's disposable "
                                        "input and a markdown is store-wide state. The new "
                                        "prices go into the corpus keyed by SKU (D86), without "
                                        "which the next emit re-lists at the rule price and "
                                        "undoes the markdown.",
                               "governed_by": ["D7", "D8", "D9", "D11", "D49", "D54", "D86",
                                               "D100", "D103"],
                               "tested_by": ["T7"]},
            "cmd_emit.py": {"does": "write ONE import CSV, `import.csv`; refuses while a price "
                                    "is unanswered. ONE PRESS WRITES ONE SPREADSHEET (D99) — "
                                    "across runs, across games and across the "
                                    "listed/sub-threshold split, which was two files per game "
                                    "per run until 2026-09-03. `--split-threshold` puts the "
                                    "old pair back under the old names, `--split-games` is "
                                    "the way back if Import to Staged refuses a "
                                    "multi-Product-Line file, and `--listed-only` is a filter "
                                    "rather than a split. The cut-off that decides the "
                                    "buckets is the corpus's stored `policy.threshold`. Prices "
                                    "from inventory/prices.json (D86) rather than from the run manifest (D49); "
                                    "refuses a run still carrying a legacy "
                                    "decisions.json, single or merged, naming "
                                    "`prices adopt --write`. "
                                    "A RE-EMIT ADDS AND NEVER SUBTRACTS (D54): it never opens an "
                                    "import file until it has at least one row for it, because the "
                                    "writer emits a header before it iterates and an empty write "
                                    "replaces a good file with a valid CSV of nothing. What it "
                                    "writes is the DELTA — the copies not already sent — and the "
                                    "SKU set is INTERSECTED with what prices_for will actually "
                                    "price rather than guessed at by subtracting the exclusions "
                                    "somebody thought of. THE LIVE CAP BOUNDS THE LISTING AND NOT "
                                    "THE IDENTITY (D7 amended): the SKU stamp runs over "
                                    "uncommitted_positions, so every copy the run matched is "
                                    "findable, while the pushed count still runs over "
                                    "live_positions, because that count is a commitment that a "
                                    "CSV row was written. Not match.positions — every terminal "
                                    "copy is committed, and set_state has no terminal guard, so "
                                    "iterating those would resurrect a sold card (D10, D26).",
                            "governed_by": ["D7", "D9", "D10", "D25", "D26", "D49", "D54", "D58", "D59", "D86", "D99"], "tested_by": ["T7"]},
            "cmd_reconcile.py": {"does": "diff intent against TCGplayer's Export From Staged", "governed_by": ["D7", "D8", "D11", "D49", "D54", "D87"], "tested_by": ["T7"]},
            "resolve.py": {"does": "turning a run's identifications into a join; shared by join and emit. "
                                   "`paperwork_for` is the other direction and lives here for the "
                                   "reason `pipeline/orders.py` may not hold it: it reads a run "
                                   "directory and hashes photographs, which a pure resolver does not "
                                   "do. It reads `pricing.json` back as SKU -> positions THROUGH "
                                   "`realign` (D36), because that file stores position keys and a "
                                   "mid-box delete moves them — reading it raw is the defect that "
                                   "wrote 47 box-2 queue entries one position off. `_copies_out`'s "
                                   "floor under the cap is the NEWEST reading of `live`, the "
                                   "store's or the export's by `Listing.live_reading`, and it "
                                   "carries that figure to the join as `live_now` (D87 amended). "
                                   "`refuse_reallocated` refuses a run over a box whose number was "
                                   "deleted and reused since (D36 amended), on the rule "
                                   "`_box_name_for` withholds a name by (D56) — `realign` reads "
                                   "photographs and not the store, and cannot see that case.",
                           "governed_by": ["D4", "D8", "D10", "D11", "D20", "D21", "D22", "D23", "D24", "D25", "D26", "D33", "D34", "D36", "D49", "D56", "D58", "D59", "D64", "D87"], "tested_by": ["T7"]},
            "runs.py": {"does": "run directories and manifest.json", "governed_by": ["D1", "D25", "D49", "D54", "D86"], "tested_by": ["T7"]},
        },
    },
    {
        "path": "pipeline/",
        "status": "built",
        "does": "CSV, variant ladder, pricing, join, routing, run decisions, per-game taxonomy",
        "governed_by": ["D2", "D3", "D4", "D7", "D8", "D9", "D10", "D11", "D12", "D22", "D25"],
        "modules": {
            "tcgcsv.py": {"does": "TCGplayer Filtered CSV read/write and byte-format inspection",
                          # D25 arrived on this file as two column constants and no reader:
                          # `Product Line` and `Rarity` have been declared in
                          # CANONICAL_HEADER and read by nothing since the file was written,
                          # which makes the join product-line BLIND rather than agnostic.
                          # D22 is the registry that will read the pair.
                          "governed_by": ["D11", "D22", "D25", "D49"], "tested_by": ["T2"],
                          "note": "real CSV library only — v1 bug 2 was a naive split(\",\")"},
            # Pure literals, importing nothing from this repo, so scripts/docs-audit.py can
            # read it with ast.literal_eval the way it reads this file. D21/D23/D24 are
            # module-level rather than package-level for the reason D17 gives about merged
            # lists: they decide what an ENTRY says — that the game is a per-card claim,
            # that a rarity claim narrows the finish chips, that a code card is not located
            # — and none of them governs pricing.py or routing.py. D14, D16 and D18 are
            # cited in the file's own prose as arguments rather than as rulings about it
            # (the seam list, the drift, the two tracks), and the superset rule reads a
            # citation literally — the same trade scripts/docs-audit.py's entry records.
            "games.py": {"does": "the per-game taxonomy: Product Line cell, ordered Rarity cells in "
                                 "STACK order, finish enum, finish -> Condition map, and the "
                                 "rarity -> finish matrix, plus join-key/prompt/crop-band/located "
                                 "facts per game. Hand-authored, audited against the committed "
                                 "exports, and it REFUSES on an empty vocabulary rather than "
                                 "falling back to Pokemon's — riftbound and one_piece ship "
                                 "unverified because no export for either has ever been seen.",
                         "governed_by": ["D3", "D8", "D11", "D12", "D14", "D16", "D18", "D21", "D22", "D23", "D24", "D25", "D65", "D76"],
                         "note": "THE MATRIX IS A SUPERSET OF WHAT ANY ONE EXPORT PROVES, and that "
                                 "is load-bearing rather than sloppy: D23's capture screen renders "
                                 "a finish chip excluded by a rarity claim as unselectable, which "
                                 "is safe only while the matrix exceeds reality. finish_by_rarity"
                                 "[\"Rare\"] carries `normal`, which SV09 does not stock. The "
                                 "audit's `matrix superset` row blocks on an observed pair the "
                                 "matrix is missing and `game coverage` only ASKS about the "
                                 "excess — narrow it and unselectable becomes a trap. "
                                 "No harness test reaches this module directly; T3 and T4 reach "
                                 "it through variant.py, which derives its finish enum and "
                                 "condition map from the `pokemon` entry and is the proof the "
                                 "entry is right — the values are byte-identical to the literals "
                                 "it replaced."},
            # D10's label formula lives here, and as of 2026-08-29 it assumes NO divider size:
            # `Position.layout` falls back to `(1,)`, so an undeclared box is one section and
            # `CARDS_PER_SECTION` is deleted rather than defaulted.
            "join.py": {"does": "catalog join by SKU, aggregation, bidirectional unmatched reporting",
                        "governed_by": ["D2", "D4", "D7", "D9", "D10", "D11", "D16", "D20", "D21", "D23", "D24", "D25", "D29", "D30", "D35", "D36", "D41", "D49", "D54", "D55", "D56", "D58", "D59", "D67", "D68", "D71", "D87"], "tested_by": ["T3"]},            # Rung 0 (a human's answer) sits above the ladder and is applied by join.py, so
            # T3 is what covers it — T4 owns the four rungs that infer.
            # D22 because FINISHES and CONDITION_BY_FINISH are no longer written here: they
            # are read out of games.py's `pokemon` entry, byte-identically, which is what
            # makes the registry believable before anything else is built on it.
            "variant.py": {"does": "the variant ladder: four rungs that infer, under a rung 0 that does not, "
                                   "over a per-game finish vocabulary and a set-valued rung 1 claim",
                           "governed_by": ["D3", "D12", "D21", "D22", "D23"], "tested_by": ["T3", "T4"]},
            # ONE MATCHER, WHERE THERE WERE TWO. The fetch scoped the export by its rules and
            # the join narrowed a colliding key by different ones, so a hint could scope
            # correctly and then fail to disambiguate the very rows it fetched. Merging them
            # also fixed a live defect: `set_matches` is PAIRWISE, so `SV` matched four sets
            # and join.py returned all four as a confident narrowing with no `set_ambiguous`.
            # D22 because the alias table it consults is still hand-authored — what the
            # abbreviation rule removed is the need to author a row per set code, not the
            # table itself.
            "setnames.py": {"does": "does this hint name this set — the one ladder the export fetch "
                                    "and the join both read. Label, colon side, guarded prefix, then "
                                    "a <=4-character abbreviation; ambiguity answers None and both "
                                    "callers widen rather than guess.",
                            "governed_by": ["D2", "D3", "D22", "D65"], "tested_by": ["T3"]},
            "pricing.py": {"does": "rules, rounding, floor clamp, threshold, no_market_data "
                                   "refusal. THRESHOLD is the DEFAULT and not the answer "
                                   "(D99): the cut-off in force is pipeline/corpus.py's "
                                   "policy.threshold, parsed by check_threshold — a positive "
                                   "price or an InvalidThreshold naming the value — and "
                                   "carried to every partition on SkuMatch.threshold. A store "
                                   "that has never set one reads the constant, so D9's $0.40 "
                                   "and its labor-bar derivation are untouched. The FLOOR is "
                                   "still a constant; nobody has asked for that one.",
                           "governed_by": ["D8", "D9", "D86", "D99"], "tested_by": ["T5"]},
            "routing.py": {"does": "which queue a card lands in — batch script v2 section 5.4",
                           "governed_by": ["D3", "D4", "D9", "D29", "D35"], "tested_by": ["T4"]},
            # THE ONLY MODULE IN THIS PACKAGE THAT IMPORTS `store`, and the edge is one-way:
            # store/ imports nothing from pipeline/, so there is no cycle. What it buys is
            # that `Inventory.copies_on_hand`'s terminal-state rule (D26 — a retired card
            # has left the box exactly as a sold one has) has ONE definition; the
            # alternative was a second copy of it here, audited against nothing.
            "orders.py": {"does": "the order resolver: (sku, quantity) -> the copies that fill it, "
                                  "for EVERY open order in one pass over a shared per-SKU pool. "
                                  "Per-order resolution hands two buyers the same physical card and "
                                  "reports success twice, so there is deliberately no `resolve_one`. "
                                  "Pure: no route, no screen, no file, no network — the input is "
                                  "domain objects and an `Inventory`, and the answer is recomputed "
                                  "on every read rather than stored, because a mid-box delete slides "
                                  "every higher index down one (D10 ruling 1) and a saved position "
                                  "list eventually names the wrong card (D36). `fulfilled` is a "
                                  "COUNT and `Pick.capture_id` is the identity, for the same reason. "
                                  "Six line reasons, because an empty result has several causes with "
                                  "different remedies: `no_copies_on_hand` is deliberately not "
                                  "`already_pulled` — D26 makes a retirement a departure WITHOUT a "
                                  "sale, so calling it filled tells the owner to ship nothing and "
                                  "believe it shipped. Candidates are a HINT, never a permission "
                                  "set: a copy is valid for what it IS (holds the SKU, not terminal, "
                                  "located, not already spoken for), which is D7's fungibility rather "
                                  "than an address re-imposed on it. "
                                  "A LINE MAY WANT ZERO SINCE 2026-09-02 (D90), and the permission "
                                  "is deliberate rather than a loosened guard: the server asks this "
                                  "engine for what the ledger still OWES rather than what the buyer "
                                  "bought, so a line whose copies are all pulled arrives wanting "
                                  "nothing — it picks none, answers `resolved` at once, and still "
                                  "counts its breakdown, which is how a filled line keeps its "
                                  "figures on screen without a second implementation of "
                                  "`OrderLine`. A NEGATIVE quantity is still the bug it always "
                                  "was.",
                          # D58 because it decides what this module deliberately does NOT
                          # do: a card's number counts the cards in the box now, so drawing
                          # a label needs the box's whole occupancy — a `Pick` carries the
                          # box and index and leaves the rendering to the one label formula.
                          "governed_by": ["D7", "D10", "D21", "D24", "D26", "D36", "D58", "D90"],
                          "tested_by": ["T7"],
                          "note": "THE SKU IS COERCED AT THE BOUNDARY AND WITHOUT THAT NOTHING WORKS "
                                  "AT ALL: `Card.sku` is a CSV string and a JSON payload carries the "
                                  "int, `\"9191486\" == 9191486` is False, so an uncoerced resolver "
                                  "reports every line unresolvable, raises nothing and logs nothing. "
                                  "IT IS A LIBRARY AND NOT A FEATURE — no route, no client function "
                                  "and no screen reaches it, which by CLAUDE.md's own rule means it "
                                  "is not landed and must not be reported as such."},
            # THE ONE-WAY EDGE INSIDE THIS PACKAGE: shipping.py imports pirateship.py and
            # never the reverse, so the Pirate Ship format knows nothing about TCGplayer and
            # can be fed by the Bridge without being touched. Same direction store/ and
            # pipeline/ have, for the same reason.
            "shipping.py": {"does": "the TCGplayer Export Shipping reader, and the router that "
                                    "puts one order in one of THREE lanes: a tcgtracking envelope "
                                    "(<$50, all cards), a Pirate Ship parcel (contains a non-card, "
                                    "OR >=$50 because TCGplayer mandates tracking above $49.99), or "
                                    "UNJUDGED. Abstention is a third answer and never a default to "
                                    "a lane — sweeping an unplaceable order into the parcel lane is "
                                    "postage the operator did not choose. The value question is "
                                    "asked BEFORE the weight proxy, which is not a style choice: 58 "
                                    "of the fixture's 97 weightless orders are >=$50 and are answered "
                                    "with certainty by a rule that needs no weight, so abstention "
                                    "falls from 97 orders (29%) to 39 (11.8%) — including the $1750 "
                                    "order docs/specs/shipping-export.md names as its own worst case.",
                            # D24 for the pooled/located split the non-card signal proxies at
                            # postage scale; D19 for the rule that a cut is derived from where
                            # a real distribution is empty rather than picked.
                            "governed_by": ["D9", "D19", "D24", "D49", "D61"],
                            "tested_by": ["T7"],
                            "note": "EXACT RATIONAL ARITHMETIC, NEVER FLOATS, and that is a defect "
                                    "already paid for: docs/specs/shipping-export.md records a float "
                                    "pass reporting a phantom sub-0.07 row on a distribution whose "
                                    "true minimum is exactly 0.07 — and sub-0.07 is the one band "
                                    "this router treats as impossible, so a float manufactures the "
                                    "outcome. THE WEIGHT IS A PROXY AND NOT A PACKAGE: it is a summed "
                                    "per-product CATALOG CONSTANT, so it says `heavier than cards "
                                    "alone` and may never say `contains a playmat`. A PRE-LINE-DATA "
                                    "STOPGAP — the export carries no line items at all, and the cut "
                                    "is to be RETIRED rather than re-fitted the day a feed supplies "
                                    "them, because pipeline/orders.py already answers this properly "
                                    "from line kinds. IT IS A LIBRARY AND NOT A FEATURE: no route, no "
                                    "client function and no screen reaches it, which by CLAUDE.md's "
                                    "own rule means it is not landed and must not be reported as such."},
            "pirateship.py": {"does": "the Pirate Ship import spreadsheet — the one supported entry "
                                      "point, because Pirate Ship has NO API. A closed column set, "
                                      "T2's byte format, `Name` PRE-JOINED from the two columns "
                                      "TCGplayer holds it in rather than left to their auto-mapper, "
                                      "the TCGplayer order number carried through as `Order ID` so "
                                      "the tracking number it mints can be matched back, and up to "
                                      "three Rubber Stamps that print on the label corners — so a "
                                      "label reading `Box 3 · Card 31` IS the pick instruction.",
                              # D49 is the rule all three refusals below are instances of; D58
                              # is why no label is composed here.
                              "governed_by": ["D49", "D58", "D61"],
                              "tested_by": ["T7"],
                              "note": "THREE THINGS IT MAY NEVER DO, and all three are D49's "
                                      "`nothing here is ever defaulted on your behalf` in another "
                                      "lane. IT NEVER SELECTS INSURANCE — an insurance-shaped column "
                                      "RAISES rather than being dropped, because dropping it "
                                      "silently is an operator who believes they asked for insurance "
                                      "and did not. IT NEVER BUYS A LABEL — no API exists and it "
                                      "would be spending. IT NEVER DERIVES A WEIGHT, which is the "
                                      "one most likely to be `fixed` later and is wrong in the "
                                      "EXPENSIVE direction: TCGplayer's Product Weight counts the "
                                      "cardboard and not the mailer, so it is a LOWER BOUND and "
                                      "writing it buys postage for less than the parcel weighs. It "
                                      "renders no position label either — pipeline/join.py:Position "
                                      "is the only label formula in this repo (D58) and a stamp is "
                                      "an opaque string somebody else composed. Buyer PII passes "
                                      "through and is NOT persisted: `render` returns bytes so a "
                                      "caller need never put a name on a disk."},
            "corpus.py": {"does": "inventory/prices.json — ONE listing answer per SKU for the "
                                  "whole store, plus the standing policy (rule, basis, "
                                  "sub_threshold) and an optional per-run policy override. "
                                  "D86 amended: the per-SKU half of a run's decisions.json is "
                                  "a fact about the CARD, not the drawer, and stored per run "
                                  "one card carried one answer per box it had been "
                                  "photographed in — 66 SKUs, 8 answered twice, 3 of those a "
                                  "hold overridden by a later price. `for_run`/`scoped_to` "
                                  "project it into a `Decisions`, so join, emit and prices_for "
                                  "never learned that answers moved. `adopt` folds the legacy "
                                  "run files in, newest-wins, reporting every choice; with "
                                  "replace=False it keeps what the corpus already answers and "
                                  "reports each as a `Kept`, and `retirable` names the files "
                                  "whose every answer the corpus now holds. `sub_threshold` "
                                  "DEFAULTS TO FLAT $0.49 when the policy is silent — absent or "
                                  "null — applied on read and written on the next save (D9 "
                                  "amended 2026-09-02). `policy.threshold` is D9's "
                                  "cut-off as a stored figure (D99) — a labor bar is a "
                                  "fact about the operator's hour rather than about any "
                                  "card, so it sits beside rule and basis and is "
                                  "validated at parse time like both.",
                          "governed_by": ["D7", "D8", "D9", "D43", "D48", "D49", "D62", "D86",
                                          "D99", "D100", "D103"],
                          "tested_by": ["T7"]},
            "livecheck.py": {"does": "the whole store against one live TCGplayer export "
                                     "(My Pricing), both directions. D87: `cli/cmd_reconcile.py` "
                                     "scopes its diff to one run's emitted_skus while "
                                     "`store/master.py:Listing` is already per SKU across every "
                                     "box and run (D7 amended), so the scoping was the command's "
                                     "and not the data's. Reads and writes nothing — it diffs. "
                                     "What the caller writes from it is `live` and ONLY `live`: "
                                     "`pushed` is the cumulative record of what was sent and "
                                     "`_copies_out` already corrects a stuck one against the "
                                     "physical ceiling. Measured: 405 of 443 SKUs read live 0 "
                                     "while carrying pushed copies, and the cap arithmetic went "
                                     "from seeing 93 live copies to 1,079.",
                             "governed_by": ["D7", "D8", "D11", "D49", "D54", "D59", "D87"],
                             "tested_by": ["T7"]},
            "reprice.py": {"does": "which live listings are not selling, and what each would be "
                                   "re-priced to (D100). Pure — no I/O, no store import, no "
                                   "network — the way livecheck.py is. THE QUANTITY IS NOT A "
                                   "VARIABLE HERE: ADD_TO_QUANTITY is a module constant, not a "
                                   "parameter and not reachable from a flag, because "
                                   "`Add to Quantity` is a DELTA and a markdown that carried a "
                                   "copy count would double a live listing. Measured: 72,701 "
                                   "real export rows carry \"0\", 649 of them on rows TCGplayer "
                                   "reported live; and nine SKUs on the owner's store sit at "
                                   "2 x pushed - sold because one import file was uploaded "
                                   "twice. The staleness predicate is live + no sale here in the "
                                   "window + owned longer than the window, and the third term is "
                                   "a PROXY for listing age that every report names as one — "
                                   "Listing has no first_listed_at and live_as_of is absent from "
                                   "all 443 stored payloads. BASIS_ASKING is local and "
                                   "deliberately not in pricing.BASES: the column is populated "
                                   "on 441 of 441 live My Pricing rows and blank on 7,787 of "
                                   "7,802 wide-export rows, so a listing run reading it would "
                                   "write no price with nothing raising.",
                           "governed_by": ["D7", "D8", "D9", "D11", "D49", "D86", "D87",
                                           "D100", "D103"],
                           "tested_by": ["T7"]},
            "merge.py": {"does": "one import file over several runs: the copies union, deduped "
                                 "on (box, index), and the live cap spent ONCE over that union. "
                                 "D59's defect one register up — add_to_quantity spends "
                                 "live_cap - copies_out per RUN against a cap that is global, "
                                 "so runs joined before either emitted each believe the whole "
                                 "cap is theirs. Measured: three separate emits over three real "
                                 "runs wrote two SKUs past the cap of 4; one merged emit wrote "
                                 "none. Writes nothing — cli/cmd_emit.py owns the file and the "
                                 "store. `_agree_policy` refuses a send whose runs override "
                                 "`threshold` differently, for the reason it already refused "
                                 "two `sub_threshold`s: one file needs one answer (D99).",
                         "governed_by": ["D7", "D48", "D49", "D54", "D59", "D86", "D87", "D99"],
                         "tested_by": ["T7"]},
            "decisions.py": {"does": "the pricing decision, parsed — the corpus's parser (D86): "
                                     "pipeline/corpus.py projects inventory/prices.json into one "
                                     "`Decisions` per run, this module owns what an answer MEANS, "
                                     "and it reads and writes no file. As of D49 the AUTHORITY "
                                     "for rule and basis rather than a copy of them. `overrides` "
                                     "holds a price OR a `Withheld`: "
                                     "the bare string \"unlisted\" or an object carrying a reason, "
                                     "an optional note and an optional `watch_above` that `join` "
                                     "reports when a refreshed export clears it. Withholds are "
                                     "deliberately absent from `dispositions()` so a held SKU "
                                     "falling out of a later run cannot refuse the whole emit.",
                             # D16 for the drift a second vocabulary would be; D26 and D37 are the
                             # two states `withheld` is deliberately not, and whose reason words it
                             # may not reuse; D39 for the route the watch line surfaces on.
                             "governed_by": ["D9", "D16", "D26", "D37", "D39", "D49", "D86"]},
            # THE FIRST MODULE IN THIS PACKAGE THAT OPENS A SOCKET, and it says so in its own
            # header. Everything else under `pipeline/` is pure local computation over the
            # export, so the network is contained on purpose: `fetch_json` is the one impure
            # function, every reading and metric is a pure function of a parsed payload, and
            # `Market` takes the fetcher and the cache directory as arguments. That last one
            # is why it does NOT import `store.files` — no module in this package imports
            # anything outside itself and the stdlib, and this one keeps that.
            #
            # A LIBRARY AND NOT A FEATURE. Nothing calls it, no route serves it, no screen
            # draws it. CLAUDE.md's route-is-not-a-feature rule says a capability that exists
            # only in a package must never be reported as done, so it is recorded here as the
            # unfinished half it is: surfacing it means a route, a client function and a
            # control, and that is separate work with a decision entry.
            #
            # D8 governs it because that entry names the export as the pricing source and no
            # external pricing API — which this reads NEXT TO rather than instead of; nothing
            # here prices anything. D49 because its `bullish` withhold and `watch_above` are
            # the only things in the product that want a trend and have none. D22 because the
            # `Product Line` cell it resolves a category by is that entry's to author. D35 for
            # the number-then-name shape the join borrows, D25 for the per-game partition.
            "pricehistory.py": {"does": "what a SKU has been selling for: the public "
                                        "infinite-api price-history endpoint, reached through a "
                                        "LOCAL sku -> productId join against tcgcsv.com's mirror "
                                        "of TCGplayer's own catalog. Per SKU it answers a "
                                        "volume-weighted VWAP on marketPrice, the interval that "
                                        "VWAP must lie in, momentum, liquidity, units per "
                                        "transaction and within-bucket dispersion. It also reads "
                                        "that mirror's current /prices, which are per product per "
                                        "PRINTING and never per SKU.",
                                "governed_by": ["D8", "D16", "D22", "D25", "D35", "D47", "D49"],
                                "tested_by": ["T7"],
                                "note": "REACHABLE AS OF 2026-08-30 (D62) — this entry read "
                                        "RECORDED RATHER THAN BUILT for one day, and the whole "
                                        "chain now exists: GET /pipeline/runs/<name>/history, "
                                        "getPriceHistory in app/src/server.ts, and one panel on "
                                        "#/pricing beside the hold that needed it — held open by "
                                        "t over the row the pointer is on, or pinned by the T "
                                        "button. "
                                        "THE RANGES OVERLAP — `annual` INCLUDES "
                                        "`month`'s days at a coarser width, so concatenating them "
                                        "double-counts the recent window; nothing here merges two "
                                        "series and the wider range is also the staler one. "
                                        "/prices supplements an export and can NEVER replace one: "
                                        "no TCGplayer Id, no Total Quantity, and subTypeName is "
                                        "the printing rather than the condition, so it speaks only "
                                        "for Near Mint. THE BOUND IS A SANITY CHECK AND NEVER A "
                                        "RESULT. The "
                                        "endpoint gives a low and a high PER BUCKET, not "
                                        "per-transaction fills, so a true VWAP is not "
                                        "computable — only bounded. Measured on Moonfall over "
                                        "`quarter`: $16.33 against $12.54..$20.35, which is 48% "
                                        "of the point estimate wide and 62% of its own low end, "
                                        "which is why `Bound` names both denominators rather "
                                        "than reporting one percentage. The join was measured "
                                        "at 3,588 distinct products across all four committed "
                                        "exports, 100% resolved, zero ambiguous."},
        },
    },
    {
        "path": "identify/",
        "status": "built",
        "does": "prompt, Batch API transport, sidecars, image prep",
        "governed_by": ["D1", "D2", "D3", "D10"],
        "modules": {
            "prompt.py": {"does": "the identification prompt and its fingerprint", "governed_by": ["D2", "D3", "D22", "D23"], "tested_by": ["T1"]},
            "batch.py": {"does": "Batch API submit/poll/collect. Batch, never sequential.", "governed_by": ["D2", "D21", "D23"], "tested_by": ["T1"]},
            "sidecar.py": {"does": "reading a capture directory: photos, JSON sidecars, position", "governed_by": ["D2", "D3", "D10", "D21", "D22", "D23"]},
            "images.py": {"does": "downscale, encode, hash a photograph for the API, and refuse a crop that is not the card",
                          "governed_by": ["D2", "D23", "D75"], "tested_by": ["T6"]},
        },
    },
    {
        "path": "geometry/",
        "status": "built",
        "does": "find the card in the frame; cut the crop-retry bands",
        "governed_by": ["D1", "D2"],
        "note": "The Gate B number this entry used to be waiting for arrived 2026-08-22 and "
                "read ZERO: detect_card found the card in 0 of 53 rig photographs, because the "
                "tone path's premise — a background flat relative to the card's own contrast — "
                "is false on a card in a clear stand on a wood desk. Fixed the same day by a "
                "SECOND method rather than a moved threshold: a border search that runs only "
                "after the tone path refuses, finds 53/53, and reports itself as "
                "CardBox.method == 'edges'. T6 gained _rig_scene, which reproduces the "
                "mechanism from the measured ring values because captures/ is gitignored and "
                "no rig photo lives here. Still not a detection rate: one rig, one lighting "
                "state, one day.",
        "modules": {
            "detect.py": {"does": "card-boundary detection by tone, and by border when tone refuses, and the shape correction both crop paths share",
                          "governed_by": ["D1", "D22", "D23", "D75"], "tested_by": ["T6"]},
            "crop.py": {"does": "cut the crop-retry regions out of a registered card",
                        "governed_by": ["D1", "D22", "D75"], "tested_by": ["T6"]},
        },
    },
    {
        "path": "codes/",
        "status": "built",
        "does": "the code-card track: deterministic QR decoding, the code ledger, the "
                "product tier",
        "governed_by": ["D14", "D21", "D24", "D70"],
        "note": "ITS OWN PACKAGE UNDER D14 — 'two tracks, one rig' shares the rig, the "
                "capture server, the app shell and the photo storage, and shares NOTHING "
                "downstream. `identify/` is the singles track's identification, a PAID "
                "vision call; the primary path here is its opposite in every respect that "
                "matters — local, deterministic, free, and correct or loudly absent rather "
                "than confident. WHAT IS NOT HERE is as deliberate: no second inventory, no "
                "second store, no second capture path. A code card is captured by the same "
                "server into the same inventory.json, and D24's `located: False` is the "
                "whole of the schema difference. NO REAL CODE CARD HAS EVER BEEN THROUGH "
                "THIS — every measurement in these modules is synthetic, which is T6's "
                "blind spot in the same words; see docs/specs/code-cards.md section 8.",
        "modules": {
            "qr.py": {"does": "read the QR off a code card. The redemption code IS the "
                              "payload, so this is the whole of identification for this "
                              "game and it costs nothing. 140/140 physically-possible "
                              "frames at the rig's real 3840x2160, ZERO mis-reads, 87 ms — "
                              "and the zero is the number that matters, because a mis-read "
                              "sells a stranger something that does not work. zxing-cpp, "
                              "PINNED to 2.3.0 because 3.x has no cp39 wheel and this venv "
                              "is Python 3.9.",
                      "governed_by": ["D14", "D70"], "tested_by": ["T8"]},
            "ledger.py": {"does": "the code ledger, keyed by the CODE rather than by the "
                                  "position — C8's first build used the position, and under "
                                  "D24 the card is destroyed, so the code is what outlives "
                                  "it. Only a code key can dedupe or hold a reservation. "
                                  "Reservation is all-or-nothing and REFUSES anything not "
                                  "held, which is the one guard against selling a code "
                                  "twice; a duplicate is recorded and never resolved.",
                          "governed_by": ["D24", "D26", "D70"], "tested_by": ["T8"]},
            "products.py": {"does": "which sealed product a code redeems, and what that is "
                                    "worth. The vocabulary is DERIVED from the real catalog, "
                                    "never invented — D22's rule for rarities, which has no "
                                    "reason to be weaker one track over. This module is why "
                                    "there is no OCR: the product is a capture claim (C10).",
                            "governed_by": ["D9", "D22", "D70"], "tested_by": ["T8"]},
            "lots.py": {"does": "build a sellable lot out of the ledger and write the three "
                                "artifacts a sale needs — the listing, the buyer's manifest "
                                "and the operator's packing slip. A PHYSICAL lot is scoped to "
                                "a BOX and takes the WHOLE box or is refused: chosen by count, "
                                "the codes reserved and the cards pulled off the shelf are two "
                                "different piles, and a lot taking 1,000 of a box's 1,003 "
                                "produces a correct ledger and a packing slip that lies. The "
                                "whole-box check asks what is PHYSICALLY in the box rather "
                                "than what is sellable from it, which is what catches an "
                                "unclaimed code and a code already reserved to another lot.",
                        "governed_by": ["D14", "D24", "D70"], "tested_by": ["T8"]},
            "scan.py": {"does": "read a capture directory into ledger entries, and apply "
                                "them. The CORE, shared by `cli/cmd_scan.py` and "
                                "`server/codes_routes.py` so the command and the screen can "
                                "never disagree about what a scan did. Nothing here writes "
                                "except `apply`, and that takes an already-open session so "
                                "the caller owns the lock's extent.",
                        "governed_by": ["D14", "D70"], "tested_by": ["T8"]},
        },
    },
    {
        "path": "store/",
        "status": "built",
        "does": "the master store: inventory, cache, standing queues, order ledger and the "
                "history, in one SQLite file since D88",
        "governed_by": ["D4", "D7", "D9", "D10", "D13", "D15", "D63", "D88", "D89"],
        "note": "T7 reaches this package as of 2026-08-13 — the allocator, the lock and "
                "the atomic replace — and as of 2026-08-22 asserts queues.apply_run "
                "outright: check_queue_supersede calls it directly rather than watching it "
                "through a route, which is what earned queues.py its tested_by. cache.py is "
                "still only read through a session there, with nothing asserting its own "
                "behavior, so it carries no tested_by: an unenforced claim is the defect "
                "docs/DEBTS.md names, not a rounding error.",
        "modules": {
            "master.py": {"does": "the cards, boxes and listings tables — cards, positions, SKUs, "
                                  "listing states, `open_section`, which puts one divider in front "
                                  "of the next card at the index only the store can read (D10), and "
                                  "D89's `record_photo_reclaimed`. Its three mappings are `Rows`: the "
                                  "high-water scan, the capture-id replay and the SKU walk ask the "
                                  "mapping for the rows they want rather than walking every card. "
                                  "`Listing.observe_live` arbitrates `live` by `live_as_of` — the "
                                  "newer reading wins, an older export is kept out — and "
                                  "`Listing.live_reading` is the same rule for the cap (D87 amended). "
                                  "`box_disowns_run` is the one rule for whether a reused box "
                                  "number is still a run's own drawer, read off the store by "
                                  "`Inventory.box_disowns_run` — the route withholds the name on "
                                  "it (D56) and the join refuses on it (D36 amended)",
                          "governed_by": ["D3", "D7", "D8", "D10", "D11", "D20", "D21", "D23", "D26", "D34", "D36", "D56", "D58", "D59", "D83", "D87", "D88", "D89"], "tested_by": ["T7"]},
            "queues.py": {"does": "the standing queues — the `queues` table, one mapping per queue "
                                  "name — and the cross-queue release a re-routed position needs",
                          "governed_by": ["D4", "D9", "D22", "D26", "D28", "D37", "D88"], "tested_by": ["T7"]},
            # THE DURABLE HALF OF THE ORDER FLOW, and the split from pipeline/orders.py is
            # the design rather than a packaging choice: the resolver's answer is true of
            # one Inventory snapshot and of no other (D36), so it is recomputed on every
            # read, while an order outlives every snapshot. Imports nothing from pipeline/,
            # which is why OrderLine is declared in both — the edge runs the other way.
            "orders.py": {"does": "the `orders` and `fulfilment` tables — one record per {source}:{order_number}, "
                                  "upserted. TWO TOP-LEVEL MAPS and the separation IS the guard: "
                                  "`orders` is the feed's and is replaced wholesale on every sync, "
                                  "`fulfilment` is ours and `ingest` cannot name it — a count "
                                  "living in the replaced record dies on the next sync, and the "
                                  "consequence is the picker sent to a slot whose card is already "
                                  "in the post. Ingest writes NO card state and NO listing count, "
                                  "so a second press is a no-op BY CONSTRUCTION rather than by a "
                                  "guard, and an unchanged re-ingest rewrites no bytes because "
                                  "`changed_at` is stamped only where the feed's content moved. "
                                  "Fulfilment is a COUNT, never a list of positions (D36); where "
                                  "an identity is unavoidable it is a `capture_id`, which survives "
                                  "a renumber by construction. No order state reaches "
                                  "`master.STATES` and nothing here writes a history row — both "
                                  "would corrupt the sale and retirement reversals, which scan "
                                  "the history filtering positively on that tuple (D26). No I/O "
                                  "and no lock: session.py writes it, and since D88 that is one "
                                  "row set inside ONE SQLite transaction over every table — not "
                                  "the fifth of five JSON files whose set was never atomic, which "
                                  "is what this line said until 2026-09-05 while already citing "
                                  "D88 three fields below.",
                          "governed_by": ["D7", "D10", "D13", "D16", "D20", "D21", "D24", "D26",
                                          "D29", "D36", "D53", "D63", "D88"], "tested_by": ["T7"]},
            "cache.py": {"does": "the `identifications` table — answers already paid for", "governed_by": ["D2", "D21", "D88"]},
            "files.py": {"does": "where the store lives, the lock, and the atomic replace the "
                                 "files still beside the database use (prices.json, codes.jsonl)",
                         "governed_by": ["D13", "D15", "D43", "D86"], "tested_by": ["T7"]},
            # D53 still, and D63, because the header now says what the transaction DOES
            # promise where it used to say what five files did not: one commit over every
            # table, history rows included. D53's drain is still a prerequisite for the
            # watcher — the photographs and sidecars a session writes beside the transaction
            # are what a kill still tears.
            "session.py": {"does": "lock-free read, or locked read-modify-write, over one SQLite "
                                   "transaction — `Snapshot` is the API and every field of it "
                                   "loads only the rows a caller names",
                           "governed_by": ["D13", "D53", "D63", "D88"], "tested_by": ["T7"]},
            "rows.py": {"does": "`Rows`: a keyed mapping of records that is a dict to every "
                                "caller and, bound to a `Source`, loads one row, one indexed "
                                "column's matches, or column values with no object built at all. "
                                "A flush is a diff over what was loaded. NO SQL, NO I/O, NO "
                                "PACKAGE IMPORT — the one thing master.py is allowed to import",
                        "governed_by": ["D88"], "tested_by": ["T7"]},
            "db.py": {"does": "the SQLite file: the schema (one payload column per row with a few "
                              "indexed columns derived beside it), `SqliteSource` behind every "
                              "`Rows`, the per-session flush, the events table that is the "
                              "history, and the one-time lossless import of a legacy JSON store "
                              "into it — under the lock, files moved to legacy-json/ with a receipt",
                      "governed_by": ["D86", "D88"], "tested_by": ["T7"]},
        },
    },
    {
        "path": "harness/",
        "status": "built",
        "does": "T1-T9. The Stop hook runs it at every turn end; the pre-commit hook does not.",
        "governed_by": ["D2", "D12", "D15", "D81"],
        "note": "The contract is docs/GATES.md; every threshold there is a number, not an "
                "adjective. THIS LINE SAID T1-T7 UNTIL 2026-08-31 while the registry held "
                "eight, which is the same disease the route count has — a published count "
                "with no reader. Recount from `run.py`'s TESTS list, never increment.\n\n"
                "T9 CHANGED WHAT THE HARNESS TAKES AS INPUT, and it is the second widening "
                "of this contract after T7's. T1-T8 all supply their own inputs — fixtures "
                "they wrote, QR symbols their own encoder drew, composites they rendered — "
                "which is what makes their answer keys exact and is also a ceiling on what "
                "they can catch. T9 reads RECORDINGS OF THE RIG from `harness/traces/`, "
                "because both Playwright specs over the motion trigger were green through "
                "two versions of a gate that was silently refusing real cards: a test that "
                "draws its own frames can only prove the machine agrees with the test. "
                "D81 carries the argument.",
        "modules": {
            "run.py": {"does": "the explicit ordered TESTS registry — no discovery magic", "governed_by": ["D1"]},
            # The tests themselves live under harness/tests/ and the orphan rule does not
            # scan that far, so they are not listed one by one. `traces/` is listed because
            # it is DATA rather than a test, and tracked data with no entry is how a
            # directory ends up in the tree with nobody able to say what it is for.
        },
    },
    {
        "path": "harness/traces/",
        "status": "built",
        "does": "eight armed motion sessions saved from the capture screen's HUD between "
                "2026-08-23 and 2026-09-01 — FIVE recorded under the brightness floor D81 "
                "replaced, and THREE recorded 2026-09-01 under the distance gate that "
                "replaced it, which are the sessions D84 was derived from. Each carries every "
                "frame's (t, d, luma), v2 adding dBase, and the exact watch-region pixels of "
                "every verdict, which is what makes a refusal re-scorable a year later. T9's "
                "input, and the only real-rig evidence in this repo for the motion trigger. "
                "Ground truth in `fixtures/`'s sense: never modified. THE TWO CORPORA ARE "
                "NAMED IN T9 AND NEVER SUMMED: `38 real cards were refused live` is a receipt "
                "for what the brightness floor cost, and adding the later three sessions "
                "would turn a fixed number into one that grows whenever a trace is banked.",
        "governed_by": ["D19", "D81", "D84"],
        "tested_by": ["T9"],
        "note": "NO CARD IS IDENTIFIABLE AND NO CODE CARD IS PRESENT. A stored frame is 1,064 "
                "luma cells at 38x28 — the watch region, quantised — which cannot carry a "
                "readable QR, and every session here is the singles feeder. T8's rule that no "
                "code-card photograph may ever be tracked is untouched.\n\n"
                "HERE RATHER THAN UNDER `fixtures/` because `.claude/settings.json` denies "
                "session writes to that directory, and a standing deny the owner checked in "
                "is not a thing to route around. `harness/` is where the test that reads them "
                "lives anyway, and its two gitignored neighbors (`images`, `.cache`) are "
                "named individually in .gitignore, so this one is tracked by default.\n\n"
                "No per-file entries: this component declares no source_suffixes, so the "
                "orphan rule does not scan it — the same arrangement `fixtures/` uses, for "
                "the same reason. A sixth trace is added by copying it in, never by editing "
                "one of these.",
    },
    {
        "path": "scripts/",
        "status": "built",
        "does": "the gate machinery and the tools around it: the pre-commit hook, the docs "
                "audit it runs, the opsec guard that is that hook's disabled PreToolUse "
                "twin, D42's two-hook guard over main and the throwaway-repo self-test that "
                "proves it, the Stop hook, the PostToolUse typecheck hook, D17's "
                "decision-context hook, `make status`, the SessionStart worktree guard "
                "and the launch-config writer it calls, the screenshot runner and its "
                "manifest, and audit-history — diagnostic, never gating, per D18.",
        "governed_by": ["D14", "D16", "D17", "D18", "D42"],
        # What the orphan rule covers here, and the one hole no declaration can close.
        # Declaring the key is also what makes the scan recursive, which is the only way
        # scripts/githooks/ is reached at all.
        #
        # `.sh` is most of the reason to declare anything. guard-opsec.sh and the
        # pre-commit hook ARE the opsec enforcement, and a repo whose one repo-wide rule
        # is that a live code card is a bearer instrument cannot leave its enforcement in
        # the directory the index does not scan. `.txt` because both files carrying it are
        # tracked INPUTS that tooling reads and fails against — the allowlist and the
        # screenshot manifest — not notes; a third arriving unnamed is exactly the drift
        # this rule exists for. `.md` is deliberately absent: no markdown lives here, and
        # declaring a suffix for a language a directory does not contain is how a scan
        # reports a clean run over nothing, which is the failure `app/` spent a day on.
        #
        # THE HOLE: `githooks/pre-commit` has no suffix, and scan_plan rejects any entry
        # that does not start with a dot, so no value here can reach it. It is listed
        # below, so its *disappearance* is caught — but a second extensionless hook
        # (`pre-push`, `commit-msg`) would land unnamed and nothing would fail. Left to
        # docs/DEBTS.md rather than worked around: the limit is in scripts/docs-audit.py,
        # and inventing a second key in this file to route around it would put the
        # workaround inside the thing the rule audits.
        #
        # THE HYPOTHETICAL IN THAT PARAGRAPH CAME TRUE ON 2026-08-29 AND IT NAMED THE FILE
        # CORRECTLY. D42 added `githooks/reference-transaction` and `githooks/pre-push`, and
        # the orphan rule was silent for both exactly as predicted — they are listed below by
        # hand, and nothing would have failed had the author forgotten. What DID catch a
        # missing entry that day was `githooks-selftest.sh`, one directory up and carrying a
        # declared suffix, which failed the commit until it was described. The two outcomes
        # from one change are the clearest statement of this hole available, so they are
        # recorded here rather than only in docs/DEBTS.md.
        "source_suffixes": [".py", ".sh", ".txt", ".mjs"],
        "note": "THIS ENTRY HAD NO MODULE LIST UNTIL 2026-08-13, so the orphan rule never "
                "scanned this directory — the rule is guarded on `modules`, and an entry "
                "with none has nothing to be an orphan of. Measured before the fix: "
                "`touch scripts/__probe.py` left the row reading `ok repo map`, while the "
                "same file under pipeline/ failed the commit. That is how audit-history.py "
                "was added — into the one directory the rule did not cover, with this "
                "file's prose updated by hand and nothing that would have failed had the "
                "author forgotten. Writing the list is why it stayed open: a `does` and a "
                "`governed_by` per file is a content decision about what governs the "
                "tooling, not a mechanical repair. "
                "WHAT IS STILL UNPROVEN, and it is the same limit app/ carries: the rule "
                "proves a file has an entry, never that the entry is true. A `does` "
                "describing the wrong file passes exactly as well.",
        "modules": {
            # ---- the commit path. D18's rule is not advice here; this IS the path ----
            "githooks/pre-commit": {
                "does": "the commit gate: fixtures read-only, no image staged outside "
                        "captures/, no iCloud Drive conflict copy (`foo 2.py`) staged while "
                        "the repo still lives there, no printed code-card layout in the "
                        "staged diff, no symlink whose target leaves the repository (D47 — "
                        "a tracked absolute link points at itself in the tree it names, and "
                        "checking it out removes the ignored real directory), then "
                        "the docs audit — whose exit code it maps, 1 blocking, 2 printing "
                        "the coupling question, 64 warning loudly that the auditor was "
                        "invoked with a flag it does not accept. Tracked and reviewable "
                        "through core.hooksPath rather than living unversioned inside git.",
                # D18 binds this file harder than any other in the repo: it is the path
                # that decides whether a commit proceeds, so "nothing that writes may run
                # here" is a property to preserve rather than a principle to admire. D11
                # is the fixtures it makes read-only — ground truth that still passes T2
                # after it drifts, which is why an edit has to be stopped and not caught.
                # D14 is why a code-shaped literal is worth a rule at all: the other track
                # on the shared rig handles bearer instruments.
                "governed_by": ["D11", "D14", "D16", "D18", "D44", "D47", "D58", "D70", "D92"],
                "note": "THE ORPHAN RULE CANNOT SEE THIS FILE — it has no suffix to "
                        "declare. Listed, so its absence would be a finding; a sibling "
                        "hook's arrival is caught by `hook roster` since 2026-09-05. "
                        "IT ALSO CHECKS ITS OWN ARMED COPY, first, before any other rule: "
                        "`make hooks` COPIES this file into .git/hooks-armed and nothing "
                        "keeps the copy in step, so on 2026-09-01 the armed pre-commit fell "
                        "four days behind a merged sigil check and every commit skipped it "
                        "silently. Compared against MAIN rather than this working tree, "
                        "deliberately — comparing to the tree fires on any branch editing a "
                        "hook, and the one command that would silence it installs that "
                        "branch's unmerged hooks as the gate for every worktree in the "
                        "clone. It blocks only where armed is behind main AND this tree "
                        "matches main, which is exactly where the `make hooks` it prints is "
                        "safe to run; the other drift states warn. Bypass PKMNSCAN_HOOKS=off.",
            },
            "githooks/reference-transaction": {
                "does": "D42's local half: refuses any move of refs/heads/main from any "
                        "worktree of this clone — commit, fast-forward, merge, rebase, "
                        "reset, `branch -f`, `update-ref`, delete. Allows exactly one thing, "
                        "a move to a commit origin/main already carries, which is what "
                        "pulling a merged pull request looks like. PKMNSCAN_MAIN=off is the "
                        "visible escape hatch, and every refusal prints it.",
                # A ref hook rather than a commit hook because the incident that produced it
                # created no commit: a fast-forward moves a ref and runs no commit hook. D42
                # carries that argument and the measured reason the payload's `old` column is
                # ignored — git reports zeros for it whenever the caller stated no expected
                # value, so `old == new` is what a DELETION looks like. D18 governs the shape
                # rather than the content: this file is on the path that decides whether a
                # commit proceeds, so it reads and refuses and never writes.
                "governed_by": ["D18", "D42"],
                "note": "THE ORPHAN RULE CANNOT SEE THIS FILE either — no suffix. It is the "
                        "case the comment above this modules block predicted by name.",
            },
            "githooks/post-merge": {
                "does": "prints the `make hooks` reminder the moment a pull makes the "
                        "installed copy of these hooks stale. Before it, that was visible "
                        "only in `make status`, which is exactly the moment nobody runs it.",
                # Nothing is enforced here and nothing should be: a post-merge hook that
                # refused would refuse AFTER the merge, which is the wrong end of the
                # operation. It prints.
                "governed_by": ["D42"],
                "note": "Extensionless, unscanned, listed by hand — see the sibling below. "
                        "It and post-checkout were missing from this list from the day they "
                        "landed until 2026-09-05, which is what `hook roster` now reads.",
            },
            "githooks/post-checkout": {
                "does": "the same reminder on a branch switch, for the same reason: "
                        "core.hooksPath never travels, so a checkout can leave the armed "
                        "copy behind the tree.",
                "governed_by": ["D42"],
                "note": "Extensionless, unscanned, listed by hand.",
            },
            "githooks/pre-push": {
                "does": "D42's remote half: refuses any push whose REMOTE ref is main, which "
                        "the ref hook beside it cannot see because `git push origin HEAD:main` "
                        "never touches refs/heads/main locally. This is what stands in for "
                        "branch protection, which GitHub answers 403 on for a private repo on "
                        "the free plan.",
                # Same escape hatch and the same fail-open discipline. Weaker than the thing it
                # substitutes for in one way D42 names outright: it guards this clone, not the
                # repository.
                "governed_by": ["D42"],
                "note": "Extensionless, unscanned, listed by hand — see the sibling above.",
            },
            "merge-pr.py": {
                "does": "`make merge` — D42's whole operation: `gh pr merge`, then the local "
                        "move of refs/heads/main onto the commit that produced. Refuses without "
                        "a PR number somebody typed; a bare `ARGS=<n>` is a preview that presses "
                        "nothing and only `--confirm` acts. It fetches origin FIRST and then "
                        "asserts the merge commit is an ancestor of refs/remotes/origin/main — "
                        "the same predicate reference-transaction evaluates at `prepared` — so "
                        "the hook is never asked to refuse. Idempotent on a PR already merged, "
                        "which is what makes a failed local half re-runnable rather than a "
                        "handoff. THEN IT DELETES THE HEAD BRANCH, since 2026-09-05: on origin "
                        "unconditionally, and in this clone only when no worktree holds it and "
                        "it is an ancestor of main. Before that it deleted neither, and 125 "
                        "merged pull requests had left 85 branches on origin and 106 here.",
                # D42 governs it twice over: the operation it performs and the rejection it
                # amends. D18 governs its shape — the preview is the read-only mode, and the
                # act is behind a flag rather than a default. D33 is the instrument the two-step
                # is borrowed from, one register down from a route that can spend money.
                "governed_by": ["D18", "D33", "D42"],
                "note": "IT NEVER SETS PKMNSCAN_MAIN AND NO REFUSAL IT PRINTS SUGGESTS IT. D42 "
                        "is explicit that a session reaching for that variable has left the "
                        "amendment behind; this needs no hatch because allow rule 3 already "
                        "permits the move it makes. WHAT IT AUTOMATES IS THE STATE LOOKUP AND "
                        "NOT THE DECISION — the local half has two correct forms and the wrong "
                        "one does not error, it fast-forwards whatever branch the main tree is "
                        "standing on, moves no protected ref and trips no hook. Nothing here "
                        "resolves a path relative to itself: the repository is the one "
                        "`git rev-parse` answers for from the caller's directory, which is what "
                        "lets the self-test point it at a temporary clone. THE CLEANUP IS NOT "
                        "`gh pr merge --delete-branch` AND THE DIFFERENCE IS THE POINT: that "
                        "flag also deletes the local branch, and to do it gh may switch the "
                        "current working tree to the base branch — underneath a local half "
                        "whose entire job is deciding which tree main moves in. So it runs "
                        "after that half has succeeded, and `--cut <branch>` is its seam, the "
                        "way `--local <rev>` is the other half's.",
            },
            "merge-selftest.sh": {
                "does": "merge-pr.py's local half, against an origin, a clone and a linked "
                        "worktree built and destroyed for the run. Seventeen cases: both forms "
                        "of the move, a dirty main worktree, a commit origin does not carry, an "
                        "unknown rev, a bare invocation — and the footgun, main checked out "
                        "nowhere while another tree sits on a branch that is BEHIND its "
                        "upstream.",
                "governed_by": ["D18", "D42"],
                "note": "THE FOOTGUN CASE WAS GREEN FOR THE WRONG REASON WHEN IT WAS FIRST "
                        "WRITTEN, and the fixture carries the repair in a comment. The other "
                        "tree sat on a branch already at the commit a wrong pull would have "
                        "brought it to, so the assertion could not fail — proved by forcing the "
                        "picker to always choose the pull form and watching it stay green. The "
                        "branch is now one behind its upstream, the same mutation turns it red, "
                        "and the fixture asserts its own arming. Same lesson githooks-selftest "
                        "records about git's own refusals scoring as the hook's.",
            },
            "githooks-selftest.sh": {
                "does": "builds an origin and a clone in a temp directory, points "
                        "core.hooksPath at the real hook files, and runs the gestures against "
                        "them: nineteen cases over what is refused, what stays open, the "
                        "legitimate pull, the escape hatch and a fresh clone. A refusal must "
                        "carry the hook's own marker to count, because git declines some of "
                        "these by itself and two cases were green on that before the check "
                        "existed.",
                # D18 is why it is in `make check` and never in the git hook: it writes. It has
                # a second reason the audit's self-test does not — it exercises the guard by
                # violating it, so wired into the commit path it would refuse its own commits.
                "governed_by": ["D18", "D42"],
            },
            "icloud-sweep.py": {
                "does": "lists iCloud Drive conflict copies (`foo 2.py`) and, with --delete, "
                        "removes ONLY those byte-identical to their original. A differing copy "
                        "is reported and left alone — it is not provably a duplicate, and "
                        "guessing there is how a cleanup tool destroys work. Never touches a "
                        "tracked file: `git ls-files --others` is its only enumeration.",
                # D44 is the decision. D18 keeps it off the gate: it is the one target in this
                # repo that can delete a file, so it is neither in `make check` nor in the
                # git hook.
                "governed_by": ["D18", "D44"],
            },
            "ignore-check.sh": {"does": "the other half of D47: `git check-ignore` over every path "
                                        "a worktree provisions, asserting each is ignored WHATEVER "
                                        "kind of thing is at it. That entry's own reopening "
                                        "condition named this check and did not build it, and the "
                                        "condition fired the same day — `harness/.cache/` and "
                                        "`.venv/` kept directory-only patterns on the reasoning "
                                        "that the guard copies one and builds the other, which is "
                                        "true of the script and silent about the path. Asks the "
                                        "BARE name only: the trailing-slash form means traversing "
                                        "the path, and git refuses it exactly when a symlink is "
                                        "there, which is the case being guarded. In `make check` "
                                        "and never in the git hook (D18) — it asks about local "
                                        "provisioning, so a fresh clone would fail a commit over "
                                        "nothing.",
                                "governed_by": ["D18", "D47"]},
            "screen-freshness.mjs": {
                "does": "proves every server WRITE in app/src has a way back — a re-read, an "
                        "invalidation signal, or a reason in the code why none is owed. Twelve "
                        "recognisers over the TypeScript AST, following the two indirections "
                        "that hide a write (stored as a value, and behind a wrapper) and the "
                        "five private helpers in server.ts that carry the method for ten "
                        "exported writes. Found nothing on the tree it was written against: a "
                        "regression guard for write 39, not a bug report.",
                # D13 is why staleness matters at all — two devices on one store. D58 is why it
                # is dangerous rather than untidy: a card's number counts the cards in the box,
                # so a stale screen shows a number that now belongs to a different card. D18
                # decides where it runs: node, like port-agreement.py, so `make check` and never
                # the git hook. D14 is why it excludes the code-card track, by banner.
                # The tail is the decisions whose client functions the RECORDED classification
                # carries, which is what makes a landing a reason to update it: D96 took two
                # names out when the envelope walk went, D100 put four in.
                "governed_by": ["D13", "D14", "D18", "D58", "D76", "D79", "D83", "D86", "D87",
                                "D89", "D96", "D100"],
            },
            "port-agreement.py": {
                "does": "proves `server/ports.py` and `app/devPort.ts` still answer the same "
                        "numbers. One algorithm in two languages that cannot import each "
                        "other — Python SERVES the capture port, TypeScript ADDRESSES it — so "
                        "a disagreement is silent and total. Feeds both the same REAL "
                        "directories (a missing path canonicalises differently in the two) "
                        "and compares this checkout's composed ports on top.",
                # D43 authors the derivation. D18 decides where this runs: it shells out to
                # node, and the git hook runs bare python3 with nothing installed, so it lives
                # in `make check` beside the other two self-tests rather than on the commit
                # path.
                "governed_by": ["D18", "D43"],
            },
            "set-hint-agreement.py": {
                "does": "port-agreement.py's shape, one decision over: proves "
                        "`server/tcg_export.py:match_sets` and `app/src/setHint.ts` resolve a "
                        "capture-time set hint to the same set. Python resolves it when the "
                        "export is FETCHED; TypeScript answers the same question at the rig, "
                        "while the operator types, so a disagreement makes the screen say "
                        "MATCHED over a hint the fetch will miss — worse than the silence it "
                        "replaced, because a verdict gets trusted. Compares the one fact both "
                        "stake a claim on (did it resolve, and to which set) rather than the "
                        "verdict shapes, which differ on purpose: TypeScript splits Python's "
                        "single miss into `ambiguous` and `unmatched` so a sentence can be "
                        "written from it. The cases are D65's own measured vocabulary.",
                # D65 authors the matcher and the whitelist field. D18 decides where this
                # runs: node again, so `make check` and never the commit path.
                "governed_by": ["D18", "D65"],
            },
            "build-mark.mjs": {"does": "generates the app's mark — app/src/kit/markGeometry.ts, markPalettes.ts and app/public/favicon.svg — by READING docs/specs/logo/sheets/small-cut.html and evaluating the drawing routine out of it, so there is exactly one implementation of the geometry in this repo. Asserts on what it extracted (the tile is 221 points, the display bracket is an outlined polygon, the small bracket is a stroked path) before writing 25KB of path data into app/. D18: a generator may write and nothing that writes may gate a commit — this is run by hand, never on the commit path.",
                                "governed_by": ["D18", "D94", "D102"]},
            "build-lockup.mjs": {"does": "generates the LOCKUP — app/src/kit/lockupGeometry.ts — by reading docs/specs/logo.md section 13's settled table and running docs/specs/logo/sheets/lockup-core.js in a real browser. It reads the table rather than re-declaring it, unlike build-mark.mjs, because the lockup's eleven parameters ARE in a machine-readable table and the mark's are not; a third copy would be a third thing to drift. It needs a browser where build-mark.mjs needs only `new Function`, because `frame()` solves the roman's tracking with document.createRange() and that solve is what gets baked. IT OUTLINES THE TYPE: 番地 in IBM Plex Sans JP 400 and BANCHI in Manrope 700, both OFL and both devDependencies read at build time and never committed, so no font ships and a blocked CDN cannot draw a fallback CJK face at letter-spacing solved for Plex. Asserts what build-mark.mjs cannot: it renders the generated outlines against the live text they replace and refuses to write when more than 8% of inked pixels differ — the measured residual is 6.2%, which is hinting. D18: run by hand, never on the commit path.",
                                 "governed_by": ["D18", "D102"]},
            "docs-audit.py": {
                "does": "D16's layers 1 and 2: every mechanical check, plus the coupling "
                        "question under `--staged`. `--json` is the machine surface "
                        "nothing downstream may parse a render instead of, and "
                        "`--self-test` is what checks the checker. It NEVER writes, and it "
                        "parses with `ast` rather than importing, so it does not run "
                        "project code. Stdlib only — the pre-commit hook runs bare python3 "
                        "with nothing installed. IT AUDITS TWO TSX FILES AS WELL AS THE "
                        "MARKDOWN, 2026-08-31: the `route rosters` row reads src/App.tsx's "
                        "ROUTES table and reconciles it against any hand-typed list of "
                        "routes in a Playwright spec, because that list going stale is "
                        "silent — a roster missing a route walks the routes it has and stays "
                        "green, which is how D69 and D70 left three screens asserted by "
                        "nothing. It is here rather than in a spec because a browser must "
                        "not run on the commit path (docs/GATES.md).",
                # D2 is here because the file names it, not because it governs: one comment
                # uses `C1` and `D2` as examples of a citation that could plausibly become
                # a variable name one day. The superset rule reads a citation literally and
                # cannot tell an illustration from a ruling. The cost of that is a listed
                # decision nobody needed; the cost of the alternative is the rule guessing.
                # D22 and D23 are rulings and not illustrations: the game-registry rows
                # read pipeline/games.py with `ast` and check the authoring against the
                # committed exports, and the `matrix superset` row is the mechanical half
                # of D23's "if anyone ever narrows this matrix, unselectable becomes a
                # trap". D12 is cited where a graded or vintage Condition cell is skipped
                # rather than reported — out of scope is not evidence.
                # D72 IS THE RULING; D50, D51 and D67 ARE THE WORKED EXAMPLE IT CITES. The
                # renumber check names this repo's real chains — D50 -> D51 -> D53, and the
                # D67 -> D69 move that occasioned it — in its comments and in the self-test
                # data, deliberately: an id that exists keeps that data out of the very
                # illustration problem D2 above records. The superset rule reads them
                # literally either way, so they are listed, and this is what they are.
                # D70 JOINS THEM AS A CITED FAILURE rather than a ruling: the `route rosters`
                # row names D69 and D70 as the two entries whose routes a hand-typed roster
                # missed, which is what that row exists to make impossible a third time.
                #
                # D31 AND D39 JOIN FOR THE ROW BESIDE IT, the same shape one row later. The
                # `route census` row names the routes whose arrival the published screen
                # count failed to follow — D39's #/runs, D49's #/pricing, D69's two and
                # D70's #/codes — because the incident is what the row is for, and a reader
                # who does not know the count has been wrong seven times reads the check as
                # pedantry. Illustrations, listed because the superset rule reads a citation
                # literally; the ruling both rows enforce is D16's.
                "governed_by": ["D2", "D3", "D6", "D7", "D8", "D9", "D10", "D12", "D16", "D17",
                                "D18", "D22", "D23", "D24", "D26", "D31", "D39", "D49", "D50",
                                "D51", "D53", "D60", "D64", "D65", "D67", "D69", "D70", "D72",
                                "D75", "D76", "D80", "D81", "D83", "D84", "D87", "D90", "D92",
                                "D96", "D101", "D102", "D104"],
            },
            "docs-audit-allow.txt": {
                "does": "paths and identifiers the docs name before they exist, one "
                        "`path  # reason` line each. Self-cleaning: the audit FAILS when "
                        "an entry comes true, which forces the line out at that moment "
                        "rather than leaving a list nobody has read since.",
                # D15 is its one live entry: step 9's image-mirror override, named by
                # docs/GATES.md before the mirror exists. D16 is where self-cleaning is
                # decided. The env var is described here rather than spelled — this file
                # is inside the auditor's code haystack, so writing the identifier out
                # would BE the reference that retires the entry, and the allowlist row
                # duly failed on the first draft of this line.
                # D23 is its second live entry: the rarity-claim prompt injection is gated
                # behind an env var that decision names and no code declares yet, because
                # D23 ships that clause in its own step so the prompt fingerprint moves
                # once, deliberately, with a re-measured T1.
                "governed_by": ["D15", "D16", "D23", "D90", "D96"],
            },

            # ---- the hooks. Every one advisory by construction except the Stop gate ----
            "worktree-guard.sh": {
                "does": "the SessionStart hook: provisions a git worktree's UNTRACKED state "
                        "before any work starts. A worktree gets the tracked files and "
                        "nothing else, so .venv/, harness/.cache/ and app/node_modules/ do "
                        "not travel — and the three failures that causes (numpy missing, a "
                        "fixture AttributeError, an empty T1 cache) never mention a "
                        "worktree. Copies the cache, builds the venv, links the eval-image "
                        "mirror, and only REPORTS the 80 MB npm install. The mirror source is "
                        "ASKED FOR — the main checkout's own fixtures.IMAGES_DIR — rather than "
                        "assumed to be its harness/images, which D47 emptied when it moved the "
                        "mirror out of iCloud; the old assumption skipped in silence and cost a "
                        "151-file download. The mirror came back to that default on 2026-08-29 "
                        "with the repo leaving iCloud, which is what asking makes irrelevant: "
                        "the answer moved twice and this code did not. Fails open on every "
                        "path, including its own bugs. AND IT REPORTS THE OPPOSITE TREE "
                        "TOO (D42): the MAIN checkout left on a feature branch after that "
                        "branch merged. That tree is the live rig — the real store, the ports "
                        "every doc names, the server the launch agent starts — and it drifted "
                        "70 commits on 2026-08-30 while `make status` said so and nobody read "
                        "it. Reports and never switches: `git switch` is the operator's to "
                        "type, and what this can do is say whether it is safe, which turns on "
                        "AHEAD being zero rather than on how far behind it is. A worktree on a "
                        "feature branch is correct and is never reported.",
                # D18 is the one that decides where this may run rather than what it does.
                # It WRITES — a venv and a cache copy — so it belongs at session start and
                # must never be moved onto the commit path or into `make check`. D16 is
                # cited for the sibling rule it sets over guard-opsec.sh and inherits here:
                # a hook that can break a session gets disabled, and a disabled hook guards
                # nothing, so every failure exits 0.
                "governed_by": ["D16", "D18", "D43", "D47", "D42"],
            },
            "worktree-provision.sh": {
                "does": "the cache-copy, image-mirror-symlink and node_modules report "
                        "shared by worktree-guard.sh (above) and `make worktree-setup` — "
                        "extracted so a fix like D47's lands once rather than twice. Takes "
                        "the main tree's path and an optional --prefix so each caller keeps "
                        "its own voice; every failure here is reported, never fatal, matching "
                        "D18 for the same reason worktree-guard.sh does — this is provisioning, "
                        "not a gate, and neither caller is on the commit path.",
                "governed_by": ["D18", "D47"],
            },
            "stop-gate.sh": {
                "does": "the Stop hook: runs `make harness` at turn end and refuses to let "
                        "the turn end on a failure. Arms itself on the absence of the last "
                        "NOT_IMPLEMENTED marker rather than on a toggle, so nobody has to "
                        "remember to switch it on; PKMNSCAN_GATE=off is the visible escape "
                        "hatch, and `--status` says armed or disarmed and why.",
                # Thin on purpose rather than padded. The contract it runs is docs/GATES.md,
                # which is prose and not a numbered decision, so what D16 settles about this
                # file is what may NOT be put behind it: a docs check here would fire at the
                # end of every turn, including turns that touched no markdown. That is the
                # whole reason the audit is commit-time and on-demand.
                "governed_by": ["D16"],
            },
            "guard-opsec.sh": {
                "does": "the PreToolUse opsec twin — RE-ENABLED 2026-08-23 with a narrowed "
                    "shape match (stands alone, mixes letters and digits, no repeated "
                    "group), after being disabled 2026-08-03 for over-triggering on "
                    "placeholders. Fails open on its own bugs; the deliberately broad "
                    "commit-time rules are the backstop for the ~2% of real codes the "
                    "narrow shape lets past.",
             "governed_by": ["D11", "D14", "D16", "D24"],
            },
            "decision-context.py": {
                "does": "D17's PreToolUse hook: reads this file, lifts each governing "
                        "decision's own bolded lead-in out of docs/DECISIONS.md, and emits "
                        "additionalContext — never permissionDecision, which would "
                        "auto-approve every Write in the project. Never blocks, never "
                        "writes, exits 0 on its own bugs, silent for files no entry covers. "
                        "Its decision_gists() is reused by status.py, never reimplemented.",
                # D2 and D3 are the docstring's worked examples, not rulings about the hook.
                # D3 is the decision an agent violated because nothing told it, which is why
                # this file exists at all; D2 is the one the first draft wrongly attached to
                # pipeline/pricing.py by merging package lists into modules. Both are cited,
                # and the superset rule takes a citation at face value — same trade as
                # docs-audit.py above.
                "governed_by": ["D2", "D3", "D17", "D80"],
            },
            "prose-guard.py": {
                "does": "D60's two guards over the four docs CLAUDE.md names. `--structure` asserts "
                        "what decision-context.py needs and cannot report for itself — a "
                        "`## D<n> — <title>` heading, every `**bold**` closed on its own "
                        "line, and at least one ruling per entry — because that hook exits "
                        "0 on everything and degrades in silence. `--facts` diffs the hard "
                        "tokens of each entry between two versions of a file, which is the "
                        "only guard a rewrite has and the only check here that needs a "
                        "BEFORE. Reads and never writes; stdlib only, so the git hook's "
                        "bare python3 can run the half that gates. docs-audit.py calls the "
                        "structure half as `decision structure` and the size half as "
                        "`entry budget`; `--facts` is on no gate, having nothing to "
                        "compare against outside a rewrite.",
                # D60 is the entry it enforces and D17 the hook it exists to protect. D16
                # is the temperament twice over: mechanical findings blocking by default,
                # and the rule that nothing may edit a doc to satisfy its own gate — which
                # is why this reads and the budget half only ever prints. D18 is why it is
                # stdlib and why the writing half is not on the commit path.
                #
                # D10, D57 and D58 are worked examples in the docstrings, not rulings about
                # this file: D57 supplies the heading whose separator the audit accepts and
                # the hook drops, and D10/D58 the pair whose facts would net to zero under
                # a whole-file diff. Cited, so listed — the superset rule takes a citation
                # at face value, the same trade decision-context.py's entry records.
                "governed_by": ["D10", "D16", "D17", "D18", "D57", "D58", "D60"],
            },
            "typecheck-hook.py": {
                "does": "PostToolUse hook: runs app/'s own tsc --noEmit, and only after a "
                        "`.ts` or `.tsx` under app/ is written. It cannot block — "
                        "PostToolUse fires after the write — so a failure is exit 2 with "
                        "tsc's output on stderr and every other outcome is silence.",
                # D13 is the stack it exists for: every harness test is Python, so nothing
                # else in this repo gives an automatic signal on TypeScript. D17 is the
                # temperament and the known limit it inherits — the hook payload shape has
                # moved between releases, and an advisory that fails a turn on its own
                # malfunction is worse than no advisory.
                "governed_by": ["D13", "D17"],
            },

            # ---- diagnostics. Neither may grow an exit code a gate could read ----
            "serve.py": {
                "does": "`make up` / `make down` / `make restart` / `make launch-agent`. One "
                        "supervisor over two children — the capture server and Vite — with a "
                        "pidfile each under `.serve/`, so a supervisor killed with -9 leaves "
                        "orphans that can still be found and swept. It watches the Python "
                        "trees the capture server imports and restarts THAT child when they "
                        "change, which is the machinery replacing the restart discipline "
                        "docs/GATES.md records as a defect: a long-running `make server` "
                        "outlives the fix written for it. Stdlib only, because the Makefile's "
                        "invariant is that the capture server must never NEED `make venv`; it "
                        "may import store.files and server.ports and may never import "
                        "capture_server, whose ORIGINS_ENV it lifts with `ast` instead. "
                        "`report()` is read-only and is what `make status` asks. "
                        "`make server` and `make dev` are untouched and still work.",
                # D53 is the entry that argues all of it. D43 because every port and the
                # agent label come from server/ports.py rather than a constant — a second
                # spelling here is the cross-tree failure that entry exists to close, and the
                # pid-ownership check compares the FULL argv path for the same reason: every
                # checkout runs a file called capture_server.py. D18 because none of these
                # targets may reach `make check` or the git hook, and launch-agent writes to
                # ~/Library. D13 because the store stays on this Mac and the LAN reach is the
                # tunnel case that entry already names.
                "governed_by": ["D13", "D18", "D43", "D47", "D53", "D70"],
                "status": "built",
            },
            "score-trace.py": {
                "does": "`scripts/score-trace.py summary|presence|sweep|contact` — re-scores a "
                        "saved motion trace offline, which is docs/specs/motion-trigger.md §4 "
                        "step 5's standing promise written down. `summary` says what the "
                        "machine did live and what today's adaptive form would do; `presence` "
                        "re-runs the card-present gate over each verdict's own pixels; `sweep` "
                        "scores the stillness thresholds across a grid over every trace at "
                        "once; `contact` writes the verdict frames out as a labelled PNG. "
                        "ITS CONSTANTS MIRROR motion.ts's DEFAULT_PARAMS and are reconciled "
                        "against them by scripts/docs-audit.py's `motion params` row, which "
                        "D84 built after finding the row had been CLAIMED in this file's own "
                        "header since D81 and never written.",
                "governed_by": ["D18", "D19", "D81", "D84"],
                "note": "WRITTEN BECAUSE THE SAME PASS HAD BEEN DONE BY HAND THREE TIMES AND "
                        "THE SECOND ONE GOT IT WRONG, 2026-08-31. The 2026-08-29 presence fix "
                        "derived its 'empty stand' brightness from twenty frames that were "
                        "photographs of real cards — a refusal was read as evidence of what "
                        "was on the stand — and the mistake survived because nobody rendered "
                        "them. `contact` exists for that and for nothing else: the only thing "
                        "that settles what a frame contains is looking at it. Stdlib for "
                        "`summary`, `presence` and `sweep`, because a tuning instrument that "
                        "needs a venv on a plain checkout is one nobody runs; Pillow only for "
                        "`contact`, which says so rather than failing obscurely. D18 governs "
                        "it because it WRITES NOTHING that gates anything and is never on the "
                        "commit path — the traces it reads live in the operator's Downloads "
                        "folder and are not in this tree.",
            },
            "score-detect.py": {
                "does": "`scripts/score-detect.py scan|sweep [<captures dir>]` — re-scores "
                        "geometry.detect_card over real capture directories, which is D75's "
                        "one-off measurement made repeatable. `scan` walks the `box*` "
                        "directories under whatever it is pointed at and puts every "
                        "photograph through the path cli/cmd_identify.py puts it through — "
                        "the sidecar's game, the game's own `card_aspect` (D22), then "
                        "identify.images.crop_refusal over the detected box — reporting per "
                        "box and overall how many yielded a box, how many the detector "
                        "refused, how many of the boxes it did return the crop guard then "
                        "declines to cut, and the area and detail distributions the two "
                        "constants sit between. `--write` commits harness/results/detect.json "
                        "under that README's rules, and a scan of one box gets its own "
                        "filename — read off what was scanned, never off the flag — so it can "
                        "never stand in for the tree's score. `sweep` reports what other "
                        "(area, detail) pairs would have declined, with no winner in the "
                        "grid. ITS CONSTANTS ARE IMPORTED FROM identify/images.py AND NOT "
                        "MIRRORED, which is the one place it parts company with "
                        "score-trace.py: that script copies app/src/motion.ts's parameters "
                        "because the machine it grades is TypeScript, and a copy here would "
                        "be a number able to disagree with the one it grades.",
                "governed_by": ["D18", "D21", "D22", "D43", "D75"],
                "note": "IT MEASURES NO WRONGNESS RATE, AND THAT IS THE FIRST THING TO KNOW "
                        "ABOUT IT, 2026-09-05. D75's nine wrong crops were confirmed by eye "
                        "one photograph at a time; nothing here has an answer key, and a "
                        "small crop that is the whole card shot from far back is "
                        "indistinguishable from one that is the card's rules-text panel to "
                        "every count this script produces. What it produces instead is a "
                        "REFUSAL RATE comparable across boxes and across time, which is the "
                        "cheap signal D75 could not leave behind: the two constants were "
                        "fitted to 867 frames on one afternoon, the same boxes now hold "
                        "1,625, and 226 of those were captured after the fitting. A rate that "
                        "departs from a neighboring box's, or from the last run at the same "
                        "`detector_fingerprint`, is a reason to go and look — and looking is "
                        "still what settles it. D18 governs it because what it writes gates "
                        "nothing and is never on the commit path; D43 because the default "
                        "directory is this checkout's own `captures/`, which in a worktree is "
                        "correctly empty and says so rather than reporting a clean zero.",
            },
            "map-view.py": {
                "does": "`make map` — docs/map.py rendered for a person, in four views: the "
                        "shape, one package, one module, everything a decision governs, and "
                        "`--stale`. Stdlib only, and it reads the map with ast.literal_eval "
                        "rather than importing it, for the reason the audit does.",
                "governed_by": ["D17", "D18", "D60", "D80"],
                "note": "WRITTEN BECAUSE THE MAP HAD NO HUMAN VIEW, 2026-08-31. The file is "
                        "2,700 lines and ~56,000 tokens, which is a third of what D60 dropped "
                        "the `@` over — so the header's promise that one Read answers the "
                        "question had quietly become a promise to spend a fifth of a context "
                        "window. `make status` lifted three lines of it and nothing rendered "
                        "the rest. A file that can only be read whole is read by nobody and "
                        "edited by everybody, which is how TRACKS sat wrong for three weeks "
                        "in the file whose whole argument is that it is audited as hard as it "
                        "is trusted. D18 governs it because it WRITES NOTHING and gates "
                        "nothing: it is a renderer, so it may be as clever as it likes. Its "
                        "`--stale` view is the one thing here that reports what no audit row "
                        "can — `git blame` on the map's own lines against each file's last "
                        "commit — and it is deliberately NOT a check: a note written to "
                        "outlive a refactor is not a defect, so this ranks suspicion and "
                        "never fails.",
            },
            "sigil-check.py": {
                "does": "`make sigil-check` \u2014 a bare `#` on an owner-side screen draws "
                        "D58's COUNT of the cards in a box and never the store key, and a key "
                        "is drawn only with D68's `B<box>` sigil (D92). Refuses a FIGURE composed "
                        "from an expression naming `index`, in either spelling this product "
                        "uses \u2014 a bare `#`, and the word `Card` (D92 amended 2026-09-04, after "
                        "four of the word form shipped past a green run of the first, measured "
                        "at four true positives and zero false ones over app/src) \u2014 with a per-line "
                        "`sigil-ok: <reason>` escape that demands the reason. ON THE COMMIT "
                        "PATH \u2014 scripts/githooks/pre-commit runs it, self-test first \u2014 "
                        "because it writes nothing and needs no venv, which is the whole of "
                        "what D18 asks. Text-matched and therefore NARROW: a renamed local "
                        "walks past it, recorded in docs/DEBTS.md rather than left to be "
                        "discovered. It found three unexamined key renders on its first run "
                        "and a CSS class that had called one a slot since it was written.",
                # D58 and D68 are the two halves of the rule it enforces \u2014 which number is
                # drawn, and which sigil marks the other \u2014 so a change to either makes this
                # script's premise stale rather than merely its prose. D18 is why it may sit on
                # the commit path at all; D16 is the placement of its self-test.
                "governed_by": ["D16", "D18", "D45", "D58", "D68", "D92"]},
            "checks.py": {
                "does": "`make explain` — what `make check` runs, as a CHECKS literal plus its "
                        "own renderer, one entry per target in the recipe: what it asserts, "
                        "what toolchain it needs, whether it writes, whether it is on the "
                        "commit path and why not, whether a finding gates. Stdlib only, and "
                        "the audit reads it with ast.literal_eval rather than importing it, "
                        "for the reason every other declarative literal here is read that way.",
                # THE LONG TAIL IS NOT DECORATION. Every decision a CHECKS entry cites is one
                # this file's content depends on: D43 is why port-agreement exists at all, D65
                # and D76 the same for set-hint-agreement, D47 for ignore-check, D60 and D74
                # for vale. Change one and the entry describing that check goes stale with it,
                # which is exactly what `governed_by` is for — so they are listed rather than
                # allowlisted away.
                "governed_by": ["D16", "D17", "D18", "D43", "D47", "D58", "D60", "D65", "D68", "D74", "D76", "D80", "D82", "D92"],
                "note": "IT DECLARES THE SUITE AND DELIBERATELY DOES NOT DRIVE IT, which is "
                        "the whole shape. A registry that drove `make check` could not "
                        "disagree with the recipe — and could silently stop running a check, "
                        "the failure this repo has paid for more than any other. One that "
                        "merely describes it can only lie, and a lie is catchable: `check "
                        "registry` reconciles it against the recipe both ways and in order, "
                        "`check census` reconciles the published prose in the Makefile and "
                        "CLAUDE.md against it, and `commit path` asserts D18 MECHANICALLY for "
                        "the first time — nothing that writes may be on the path that decides "
                        "whether a commit proceeds, a rule cited in five Makefile comments and "
                        "two decisions and enforced until now by nobody. IT HAD A LIVE "
                        "DEFENDANT: `make help` said `harness + docs-audit + the self-tests + "
                        "lint + typecheck` from the day port-agreement landed, five targets "
                        "running and invisible from the front door, while CLAUDE.md carried "
                        "the full eleven and noted that the help line had said five of them "
                        "for months. Nothing compared the two, so the note aged into a "
                        "description of a defect that was still there. D80 governs the field "
                        "list: every field is rendered by `make explain`, and the NEEDS "
                        "vocabulary is checked for a token no entry uses.",
            },
            "status.py": {
                "does": "`make status`. Holds no fact about the project: the step and the "
                        "gate come from this file, the T1 score from harness/results/, the "
                        "branch from git, the health line from docs-audit.py's `--json`. "
                        "Every path it reads OR RUNS is declared in one SOURCES literal so "
                        "the audit's status-sources check can verify the reader without "
                        "importing it, and a source it cannot read prints MISSING and exits "
                        "non-zero rather than quietly printing less.",
                # D17 is the map it reads, including the `step` field it resolves "do this
                # next" through — which is why an entry without one prints a dead end. D16
                # is the audit it shells out to for its health line, and the reason SOURCES
                # is pure literals: a check that verifies a reader must not execute it.
                # D42 joins because hooks() no longer merely reports a config: it encodes where
                # the hooks must be INSTALLED, and reads NOT ARMED for the working-tree
                # arrangement that entry started with and then had to retract.
                # D44 governs icloud(), which is a REPORT and never an action — and which is
                # kept now that the repo has left iCloud for that entry's amended reason: the
                # hazard belongs to a synced directory, and a tree can be put inside one
                # without telling this script.
                "governed_by": ["D16", "D17", "D42", "D43", "D44", "D80", "D86", "D88"],
                "note": "IT READS `--json`, NOT THE RENDER, since 2026-08-13. This line "
                        "said the opposite until integration: the debt was closed and this "
                        "entry rewritten in the same run by different hands, and nothing "
                        "mechanical could have caught the disagreement — a `note` is prose "
                        "and the orphan rule only proves the entry exists. The auditor is "
                        "in SOURCES for the same reason: it is a subprocess rather than a "
                        "read, which is exactly why its path sat hardcoded and uncovered "
                        "while every other path here was audited.",
            },
            "launch-config.py": {
                "does": "writes `.claude/launch.json` for THIS checkout's dev port, which is "
                        "what the Browser pane opens. ONE WRITER, THREE APPETITES: "
                        "`make launch-config` forces because somebody typed it, "
                        "`scripts/worktree-guard.sh` passes `--if-needed` because it runs "
                        "unasked at session start, and `make status` passes `--check` and "
                        "writes nothing. Only an ABSENT file or this repo's own shape at "
                        "the wrong port is rewritten; anything a person edited is reported "
                        "and left alone, which is D44's asymmetry rather than a new one.",
                # D43 is the whole subject — the port follows the checkout's PATH, and this
                # file was the sixth reader that entry found after the other five moved. The
                # amendment naming it says why it is the worst to get wrong: a stale port
                # previews the MAIN TREE from a worktree and the only signal is the one you
                # were hoping for. D18 is why the `--check` path reports rather than repairs,
                # and why none of this is on the commit path at all.
                # D44 is the asymmetry it borrows for the conservative path: `make
                # icloud-sweep` deletes only what is provably a duplicate and only ever
                # reports what differs, because guessing is the one way a cleanup tool
                # destroys work. A provisioner running unasked has more reason, not less.
                "governed_by": ["D18", "D43", "D44"],
                "note": "STDLIB ONLY, AND BARE `python3` MUST RUN IT. The hook calls this "
                        "BEFORE it builds `.venv`, because the port is wanted whether or "
                        "not the pip install ever succeeds — so an import needing a package "
                        "would make the port wrong in exactly the tree that is least set "
                        "up. It imports server/ports.py rather than re-deriving the slot, "
                        "for the reason D43 spends its length on: two spellings of one "
                        "derivation is the drift, not the arithmetic.",
            },
            "audit-history.py": {
                "does": "replays today's auditor over every historical tree to answer one "
                        "question: which checks have ever had something to say. Reads "
                        "`--json`, never the human render.",
                # D18 is why it has deliberately no exit code a hook could grow to depend
                # on: the moment one exists, the by-construction confound in its header —
                # silent prevention and uselessness are indistinguishable after the hook
                # landed — starts deciding commits. D16 is the auditor it replays and the
                # retirement argument its table feeds.
                "governed_by": ["D16", "D18"],
            },

            # ---- the published demo. Seed, record, publish; none of it gates anything ----
            "demo-photos.py": {
                "does": "curates the owner's own card photographs, and the identification each "
                        "one actually got, into the tracked `demo-assets/` the demo is built "
                        "from. THE ONE SCRIPT THAT PUTS A PRIVATE PHOTOGRAPH ON A PATH HEADED "
                        "FOR A PUBLIC HOST, so it refuses any candidate a QR decodes out of at "
                        "full resolution — a positive test on the image rather than a promise "
                        "about the store's labels — and refuses outright if the decoder cannot "
                        "be loaded. Selects for the join: `--joinable` keeps cards whose SKU a "
                        "vendored export carries, because a run is joined against those.",
                # D70 is why the QR is the test: a code card's whole identity IS its QR, so a
                # clean decode is a real answer about the image. D24 is what makes it matter —
                # a live code is pooled, bearer inventory. D25 is the per-game split that
                # decides which cards a run can be built over, and D67 the two halves of the
                # number this copies across so the caption matches the picture.
                "governed_by": ["D24", "D25", "D67", "D70"],
            },
            "demo-seed.py": {
                "does": "writes a demo store — real catalogue rows out of fixtures/, invented "
                        "positions, drawn card photographs, a corpus with three deliberate "
                        "holds, and two run directories in the shape `identify` leaves behind. "
                        "Deterministic from one seeded RNG, so an unchanged tree rebuilds "
                        "byte-identically and CI does not churn the repo. Refuses to run with "
                        "PKMNSCAN_HOME unset, because that is somebody's real store.",
                # D13 is the store it writes through; D43 is why PKMNSCAN_HOME is the guard —
                # a checkout's own inventory is the default and seeding over one is the loss
                # that decision exists to prevent. D86 is the corpus shape and D49 the holds:
                # a first version wrote a top-level `answers` map that `Corpus.parse` kept as
                # `unknown` and no reader ever saw. D25 is the per-game number split, which
                # the export carries whole and a card record carries in halves.
                "governed_by": ["D3", "D4", "D7", "D10", "D13", "D21", "D25", "D26", "D39",
                                "D43", "D46", "D49", "D67", "D70", "D78", "D83", "D86",
                                "D87"],
            },
            "demo-record.py": {
                "does": "spawns its own capture server over the demo store on its own port, "
                        "sweeps every GET the client can build against the parameter space "
                        "the store actually holds, and writes app/demo/bundle.json plus the "
                        "photographs Vite will bundle. Records 200s only — a 404 here means "
                        "the path is not a read, not that a read failed.",
                # D43 is the port and the store, both derived rather than assumed: this
                # spawns its own server precisely so it never touches `make up`, which on
                # the main checkout is the owner's live process over their real inventory.
                "governed_by": ["D13", "D43", "D52", "D61", "D62", "D76"],
            },
            "demo_scrub.py": {
                "does": "strips machine-local absolute paths out of the bundle before it is "
                        "published, and audits its own output for anything that still looks "
                        "like a home directory. Exact prefixes rather than a pattern: a regex "
                        "attempt truncated at a bad character class and left the account name "
                        "it was written to remove.",
                # The bundle goes to a public host, and `/status` and `/pricing` both answer
                # with real filesystem paths. Underscored, not hyphenated, because it is the
                # one file here that is IMPORTED rather than run.
                "governed_by": ["D18"],
            },
            "demo-freshness.py": {
                "does": "whether app/demo/bundle.json still describes the wire it was recorded "
                        "against, by comparing a digest of app/src/types.ts and "
                        "app/src/server.ts. On no gate: the bundle is not committed and CI "
                        "rebuilds it from source on every push, so what is left is a local "
                        "preview serving a recording that predates the last edit.",
                # D18: reads two files, writes nothing, so it is safe on a path that decides
                # anything. D16 is the shape — a mechanical check for a claim that would
                # otherwise fail silently, because a stale bundle renders BLANK rather than
                # erroring.
                "governed_by": ["D16", "D18"],
            },

            # ---- the render loop docs/DESIGN.md calls mandatory ----
            "screenshot.sh": {
                "does": "headless Playwright render of a URL to captures/ui/<name>.png, or "
                        "one per line of views.txt under --manifest. Returns non-zero "
                        "unless a non-empty PNG lands on disk — an exit 0 from the CLI is "
                        "not proof that anything was written.",
                # D5 is why the loop exists: the agent cannot see its own output, and the
                # screens that most need looking at are the second persona's. D13 is what
                # it renders — Vite on :5173, a browser on the Mac. D18 is the rule that
                # keeps it off `make check`: it writes, and nothing that writes may run on
                # the path that decides whether work is done.
                "governed_by": ["D5", "D13", "D18"],
            },
            "views.txt": {
                "does": "the manifest `make screenshot` walks: one `<name> <url>` line per "
                        "view worth looking at. Tracked, unlike the renders — it used to "
                        "live under captures/, which .gitignore excludes wholesale, so the "
                        "list could not be committed and a fresh clone started with none.",
                # D5 is what the list is for: SEVEN owner screens and the Fulfiller's, which
                # is the one render where the absence of the nav strip is the point. It said
                # five while the file listed eight — the lines were added (pricing by D49,
                # orders and shipping by D69) and the count beside them was not, the same
                # drift the app/ entry below carries a paragraph about. It went eight to seven
                # on 2026-09-05 when D24's owner ruled that `#/inventory` keeps the pooled
                # photographs on its `Pooled` shelf and loses its render (docs/DEBTS.md
                # section 14) — and the `route census` row caught this sentence in the same
                # run that dropped the line, which is the whole reason that row exists. D13 is
                # why the hash route in each URL is load-bearing rather than decoration —
                # drop it and a render is named after one view and shows another. D39 added
                # the `runs` line on 2026-08-29 — the pipeline's own route. This comment said
                # that line was "the one owner render that draws no stored capture photo, so
                # the `views exposure` question the others raise does not arise for it", and
                # both halves were wrong: RunsComposer.tsx:692 draws one, `views exposure`
                # names the line on every run, and the manifest's own paragraph was corrected
                # on 2026-09-05 to describe the RENDER STATE and the three gates that hold it
                # rather than the screen. D86 is the same drift on the `pricing` line — the
                # corpus made that screen's default the full cross-run worklist, and the
                # paragraph beside it still described a run picker that draws nothing.
                "governed_by": ["D5", "D13", "D24", "D31", "D39", "D49", "D63", "D69", "D86"],
            },
        },
    },
    {
        "path": "fixtures/",
        "status": "built",
        "does": "real TCGplayer exports for three product lines — Pokemon (SV09), Riftbound "
                "and One Piece — plus the import file TCGplayer accepted verbatim, and "
                "two verbatim upstream captures the price-history reader is asserted "
                "against: slices of tcgcsv.com's Unleashed products and prices, and one "
                "answer from the infinite-api price-history endpoint. Ground truth. Never "
                "modified, enforced by pre-commit.",
        "governed_by": ["D8", "D11", "D22", "D25"],
        "tested_by": ["T2", "T7"],
        "note": "The Riftbound and One Piece exports arrived 2026-08-23 and settled the "
                "highest-risk assumption in D22: TCGplayer does carry both as Product Line "
                "values, on the identical 16-column header. They also refuted three guesses "
                "the registry had been written around — see D22. No per-file entries here "
                "because this component declares no source_suffixes, so the orphan rule does "
                "not scan it; the audit's game rows read the directory instead. THE TWO "
                "JSON CAPTURES ARE NOT EXPORTS and are here for the property that makes "
                "this directory what it is: they carry the SHAPE nothing invented would "
                "get wrong in the same way — every number arriving as a string, a "
                "literal zero written into a bucket that sold nothing, and the buckets "
                "arriving NEWEST FIRST, which is the ordering that would have inverted "
                "every momentum reading in silence.",
    },
    {
        "path": "server/",
        "status": "built",
        "does": "capture server: POST /capture, /status, GET /photo/<box>/<position>, "
                "GET and PUT inventory state, DELETE /inventory/<box>/<index> — undo — and "
                "7b's three: GET /queues, POST /review/<box>/<index>/answer, "
                "POST /inventory/<box>/<index>/sold",
        "governed_by": ["D3", "D4", "D6", "D7", "D10", "D13"],
        "note": "T7 reaches this package as of 2026-08-13: every route, every named "
                "refusal, and the sidecar seam read back through identify.sidecar.scan. "
                "7b's three routes arrived with their own T7 cases in the same session, "
                "which is the one thing about 7b that did NOT get built ahead of its "
                "evidence. What T7 still does not cover is in docs/DEBTS.md. Writes only "
                "through the store session, never straight to disk. The capture root is "
                "captures/cards/ and not captures/, so screenshot renders under "
                "captures/ui/ are never scanned as paid captures.",
        "modules": {
            "ports.py": {
                "does": "which ports THIS checkout serves on, derived from where the checkout "
                        "is. The main tree keeps :8000 and :5173; a linked worktree gets its "
                        "own pair from one slot off its path. `PKMNSCAN_PORT` overrides and an "
                        "out-of-range value is ignored rather than obeyed.",
                # D43 is the decision. D13 is why it matters: one truth on the Mac, and the
                # store already defaults per-checkout — so a shared port meant one tree's UI
                # writing into another tree's store, which is that entry's promise broken by
                # a socket rather than by a design.
                "governed_by": ["D13", "D43"],
                "note": "Stdlib only, like the server it serves. `scripts/status.py` imports "
                        "it and the git hook never does.",
            },
            "capture_server.py": {
                # THE COUNT USED TO BE PUBLISHED HERE AND IS NOT ANY MORE, and this comment
                # is the argument against itself. It read "Nine since 2026-08-13" and defended
                # the practice in its own words: "the count is written out rather than left as
                # 'the routes' because it is the one number here a reader checks against the
                # handlers, and it was wrong for exactly one commit at six." It was wrong at
                # six, it was corrected to nine, and by 2026-08-23 it was wrong again at
                # thirteen — restated in three files at once, none of which noticed.
                #
                # D18 decides it: a route count is verifiable and there is nothing in it a
                # later session could reasonably disagree with, so it is not load-bearing
                # prose and the honest fix is to stop publishing it. The handlers are the
                # register. What a reader actually needs from this entry is which SHAPES of
                # route exist, and that is what the line below now says.
                "does": "the capture, status, photo, inventory, queue, review-answer, "
                        "mark-sold, undo, search, box and order routes — including D34's listing "
                        "release and the free plan that must be drawn before it, D37's "
                        "stand-down in both directions, D20's box name as an address "
                        "(`name_taken`, and a number allocated rather than typed), and D10's "
                        "one-divider-at-a-time `POST /boxes/<box>/sections`, which takes no "
                        "index because the store reads `next_index` inside its own lock; "
                        "and D91's two-bodied `POST /orders/fetch`, whose `{preview: true}` "
                        "half counts the window by status and details nothing; "
                        "the sidecar identify reads "
                        "back; the photo store; the origin allowlist that stands between a "
                        "stray browser tab and a hard delete; "
                        "and SERVER_EVENTS, appended "
                        "to history.jsonl through _history inside the route's own "
                        "Store.write(), so the line and the change it describes commit "
                        "together or neither does. NOT ONE OF THEM is a member of "
                        "master.STATES, which is what keeps _state_before_sale from "
                        "restoring a reversed sale to one of them. "
                        "THERE IS ONE ORDER-PULL DOOR AND THERE WERE BRIEFLY TWO. `do_order_fill` "
                        "— D90's envelope, every line of one order in one write — arrived with "
                        "main's merge, was reachable from no screen here for a day and a half, "
                        "and is deleted (D96 amended 2026-09-04) along with its two constants and "
                        "its dispatcher line. `_prepare_targets` and `_ledger_pull` STAY: they "
                        "were lifted out of `do_order_pull` for the second door's sake and are "
                        "still its own two phases, so the capture_id_mismatch aim check, the SKU "
                        "check and the duplicate guard sit in one body each rather than inline. "
                        "Both docstrings say the second door is gone rather than naming a route "
                        "that answers 404. ITS CONCURRENCY IS A KNOWN DEBT AND NOT A "
                        "PROPERTY OF THIS ENTRY: it serves on ThreadingHTTPServer, one "
                        "thread per keep-alive CONNECTION with nothing bounding the "
                        "count, and a burst of clients — make design-check is the "
                        "measured one — takes it to hundreds of threads answering "
                        "nothing. docs/DEBTS.md section 11 has the argument, the three "
                        "measurements and why a worker pool is not a swap. Named here "
                        "because a session diagnosing a wedge from .serve/*.log reads "
                        "this entry and not the two comments inside the file.",
                # THE EVENT NAMES ARE NOT ENUMERATED HERE, and that is the fix rather than a
                # thinning. This line named five of them — `corrected`, `removed`, `answered`,
                # `unanswered`, `reshot` — and said "none of the five", while the tuple had
                # grown to eleven and then to thirteen without the sentence moving. A restated
                # list nothing reconciles is D18's own test failing in public: the membership
                # is verifiable, nothing in it is arguable, and the tuple in
                # server/capture_server.py is the register. T7 is what asserts the
                # disjointness this sentence claims.
                # D5 is here because the file cites it: the concurrency it is tested at is two
                # and four simultaneous captures, and two is D5's two people on two devices.
                # D4 and D7 arrived with 7b — the review answer is D4's one-tap choice, and
                # mark-sold is the per-position half of D7's aggregate-by-SKU rule.
                # D10 earned a second job with the history lines: index reuse after an undo is
                # what decides that a removal must be logged at all, since without the line
                # the log reads `captured 3/2` twice over two physical cards.
                # D1, D9 and D16 arrived with the pipeline seam this file dispatches to:
                # D1's two-phase split is why one route spawns and the rest answer in the
                # request, D9's decisions file is what the PUT writes, and D16 is cited in
                # the header's own argument for rewriting a promise rather than leaning on
                # its letter.
                "governed_by": ["D1", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11",
                                "D12", "D13", "D16", "D20", "D21", "D22", "D23", "D24", "D26",
                                "D28", "D29", "D30", "D33", "D34", "D36", "D37", "D41", "D43",
                                "D45", "D46", "D49", "D52", "D53", "D55", "D56", "D58", "D61",
                                "D62", "D63", "D64", "D65", "D66", "D67", "D69", "D70", "D76",
                                "D77", "D79", "D83", "D86", "D87", "D88", "D89", "D90", "D91",
                                "D92", "D93", "D96", "D100", "D103", "D104"],
                "tested_by": ["T7"],
            },
            "tcg_import.py": {"does": "THE OUTBOUND WRITE to the seller admin, and the only "
                                      "place in this repo that can change a price a buyer "
                                      "sees (D106). Four endpoints read off TCGplayer's own "
                                      "652KB bundle and adversarially verified: "
                                      "initializeexportcsv (lowercase `filename`), "
                                      "uploadexportcsv (camelCase `fileName` — their bundle "
                                      "really does spell it both ways), finalizeexportcsv, "
                                      "rollbackexportcsv, then movetolive. NOT IN "
                                      "tcg_export.py because that module's docstring promises "
                                      "in writing that it CANNOT CAUSE A CHARGE, and a write "
                                      "beside it would falsify that or narrow it to a "
                                      "technicality. Its own promises instead: two explicit "
                                      "operations, a move scoped to ONE upload by a CONSTANT "
                                      "and never a parameter, a failed push rolled back, and "
                                      "no response body in any refusal message. The transport "
                                      "is BORROWED from tcg_export._open rather than copied — "
                                      "D104's rule, because the redirect discipline is the "
                                      "part that rots in a duplicate. `_form` reproduces "
                                      "jQuery's deep encoding (`data[0][MyPrice]`), which is "
                                      "what their server reads and what urlencode alone "
                                      "cannot express. `_check` runs their own validators — "
                                      "price 0.01-200000, integer quantity — plus D100's "
                                      "invariant that AddToQuantity is 0 on every row, before "
                                      "a transaction is opened, so a bad file is a refusal "
                                      "with nothing sent. THE PUSH IS MEASURED; movetolive is "
                                      "read and has never been called from here.",
                               "governed_by": ["D13", "D16", "D64", "D87", "D100", "D103",
                                               "D104", "D106"],
                               "tested_by": ["T7"]},
            "tcg_export.py": {
                "does": "the outbound calls to the seller admin host, and the only place "
                        "allowed to make them — one of TWO such modules since D69 gave "
                        "server/order_transport.py the order host. What the split "
                        "guarantees is not a count: an outbound call lives in its own "
                        "module, names one host, reads its credential at call time and "
                        "lets it into no return value. Here that is: GET the operator's "
                        "own Filtered Export off "
                        "store.tcgplayer.com with the session cookie in .env. Stdlib urllib, "
                        "one host, one method. Redirects are NOT followed blindly — a 302 to "
                        "the logon page is what an expired session looks like, and following "
                        "it would deliver an HTML login page to be parsed as a CSV — and one "
                        "deliberate hop drops the cookie on a host change. Every anticipated "
                        "failure has its own code: tcg_cookie_missing, tcg_session_expired "
                        "(the redirect AND a login page served as a 200), tcg_blocked (the "
                        "WAF, naming PKMNSCAN_TCG_USER_AGENT as the remedy), tcg_unavailable, "
                        "tcg_unreachable, tcg_not_csv, tcg_export_empty. The cookie is in no "
                        "return value, no message and no run directory, and it is read "
                        "through envfile.get_live rather than envfile.get because a "
                        "SESSION EXPIRES: get caches per process and cannot replace a "
                        "name it lifted out of .env itself, so under D53's long-running "
                        "supervisor the remedy tcg_session_expired prints would not have "
                        "worked.",
                # D64 is the entry. D16 is why capture_server.py's file-boundary sentence was
                # rewritten rather than narrowed to "no socket TO ANTHROPIC". D11 is what the
                # file being fetched IS — the Pricing tab's Export Filtered CSV, which is the
                # listing path's own input. D24 is the opsec rule this borrows: a bearer
                # instrument does not go in a file anyone else reads.
                "governed_by": ["D3", "D8", "D9", "D11", "D16", "D24", "D33", "D53", "D64",
                                "D65", "D69", "D76", "D87", "D104"],
                "tested_by": ["T7"],
                "note": "Stdlib only, like the rest of the server: requirements.txt names the "
                        "absence of `requests` on purpose and one more fetch is not a reason "
                        "to spend it. PKMNSCAN_TCG_EXPORT_URL aims it at a local socket for "
                        "T7 and refuses to carry the cookie over plain http anywhere but "
                        "loopback. What T7 CANNOT prove is whether the WAF accepts an "
                        "authenticated request — that is one live fetch by the owner, and "
                        "D64 records it as owed.",
            },
            "codes_routes.py": {
                "does": "the code-card track's seam: GET /codes (the ledger, its two lanes "
                        "and its duplicates), POST /codes/scan (decode a box's photographs — "
                        "FREE, no model call anywhere on this track) and POST /codes/export "
                        "(preview a channel export, or COMMIT one to an order, reserving "
                        "every code it returns). Its own module for pipeline_routes.py's "
                        "reason one register down: that one is separate because it can SPEND "
                        "money, this one because it can COMMIT a bearer instrument — a code "
                        "handed to a buyer cannot be un-handed and double-selling one is "
                        "unrecoverable (C3).",
                "governed_by": ["D14", "D24", "D33", "D70"], "tested_by": ["T8"],
            },
            "pipeline_routes.py": {
                "does": "the pipeline seam: POST /pipeline/preflight (free, creates no run), "
                        "POST /pipeline/identify (THE ONE THAT SPENDS — spawns a detached "
                        "child and returns the run name), GET /pipeline/runs and "
                        "/pipeline/runs/<name> (read the run directory, hold nothing), "
                        "GET .../file (the import CSVs and the report, matched by shape and "
                        "then by membership) and POST .../<join|emit|reconcile> (free, run "
                        "inside the request, stdout returned verbatim). "
                        "Its own module because it is the one part of this server that can "
                        "cost money: everything in capture_server.py still holds no key, "
                        "opens no socket and starts no child. A SEND IS A CART OF BOXES "
                        "(D48): both money routes take `scopes: [{box, indices?, crop?, "
                        "max_edge?}]`, a bare `box` reads as a cart of one, the response is "
                        "always a list, the total is summed here rather than on the screen, "
                        "and identify spawns one detached child PER BOX — so a run is still "
                        "one box and nothing downstream learns a new shape. AND POST "
                        ".../export (D64) fetches this run's Filtered Export through "
                        "server/tcg_export.py instead of the operator downloading and "
                        "uploading it: free, reported separately from the join so a failure "
                        "is attributable, ruled on by cli/resolve.py:exports_for BEFORE "
                        "anything is joined, checked against the scope it asked for (D65) "
                        "rather than by inspecting the file for completeness, and deleting "
                        "what it wrote on every refusal. GET .../pricing RE-RENDERS every "
                        "stored position label against the live store before it answers and "
                        "serves the one join froze into pricing.json never (D58, on D56's "
                        "rule) — measured at 142 of 146 stored labels wrong on the owner's "
                        "two joined runs. It goes through cli/resolve.py:box_views rather "
                        "than capture_server._Places because capture_server imports THIS "
                        "module, and the file on disk is not touched.",
                # D1 is the two-phase split, which is why join/emit/reconcile can answer in
                # the request and identify cannot. D9 is the decisions gate. D13 is one truth
                # on one Mac, which is what a detached child outliving this process rests on.
                # D32 is why --force-resubmit is deliberately not offered to a screen.
                # D58 is the pricing route's label re-render — the stored rendering is
                # never served, which that entry's own amendment records at this site.
                "governed_by": ["D1", "D2", "D3", "D8", "D9", "D12", "D13", "D16", "D19",
                                "D20", "D21", "D22", "D24", "D25", "D29", "D32", "D33", "D35",
                                "D36", "D43", "D47", "D48", "D49", "D54", "D56", "D58", "D59",
                                "D62", "D64", "D65", "D68", "D76", "D78", "D79", "D86", "D87",
                                "D88", "D100", "D103"],
                "tested_by": ["T7"],
            },
            "shipping_routes.py": {
                "does": "the shipping seam (D69's second route): POST /shipping/batches reads "
                        "TCGplayer's Orders -> Export Shipping CSV into D61's three lanes and "
                        "renders a Pirate Ship import file, GET .../file?name= hands those "
                        "bytes to the browser, and DELETE .../<batch> drops the batch now "
                        "rather than in half an hour. THE ONLY MODULE IN THIS SERVER THAT EVER "
                        "HOLDS A BUYER'S REAL NAME AND STREET ADDRESS, AND THE ONLY ONE THAT "
                        "EMITS THEM — its own file for the mirror image of tcg_export.py's "
                        "reason, so 'where does the PII go' has one file to check. The batch "
                        "table is an OrderedDict in this process's memory with a "
                        "half-hour TTL and a four-batch cap; it touches no disk, which is what "
                        "D61's pass-through-and-do-not-persist rule requires and what "
                        "pipeline/pirateship.py returning bytes rather than a path exists to "
                        "make possible. The batch id is 128 random bits because the file route "
                        "is a GET and therefore not behind the origin gate. Two devices do not "
                        "share a batch and a server restart drops every one — recorded rather "
                        "than discovered, because make up reloads on any Python edit here. "
                        "Nothing in it writes a file, opens a socket, reads a key, starts a "
                        "child or takes the store lock. POST .../stamps is BUILT as of "
                        "2026-09-05 — `do_shipping_stamps`, a client function, and a control "
                        "on #/shipping, because a route is not a feature. Its blocker was an "
                        "empty order ledger and the 2026-09-03 pulls cleared it. The wire "
                        "already carried `stamp` per row and `stamps` per batch as nulls, so "
                        "it changed no type and no component, exactly as predicted. MEASURED "
                        "on the 20 real orders: 12 fit the three label corners and 8 do not, "
                        "so a stamp register that stops per box is the reopening condition.",
                # D61 is the lanes, the abstention, the weight and the PII rule; D63 is the
                # ledger the stamps route reads; D66 is why the lane got a surface of its own
                # rather than a badge on the order screen; D69 is the route. D58 is the stored
                # index the stamps route speaks — its labels are `join.Position`'s, joined with
                # " / " and never " · ", which would make a card boundary read as a section one.
                "governed_by": ["D58", "D61", "D63", "D66", "D69"],
                "tested_by": ["T7"],
                "note": "T7 reaches it because that test imports the `server` package, and "
                        "every refusal path is exercisable with no network. WHAT T7 CANNOT "
                        "PROVE is that Pirate Ship's importer accepts the file this renders — "
                        "that is on the far side of a seam no committed fixture can hold, and "
                        "it is one upload by the owner.",
            },
            "order_transport.py": {
                "does": "the order transport (D69): this account's own orders off "
                        "order-management-api.tcgplayer.com, cookie-authenticated with the "
                        "same TCGPLAYER_STORE_COOKIE the export uses — one .tcgplayer.com "
                        "session, two hosts. Stdlib urllib, one host, an https-or-loopback "
                        "override. TWO CALLS because the search result carries no SKU and only "
                        "the order detail does: products[].skuId is the export's TCGplayer Id "
                        "is store/master.py:Card.sku. Every response is PROJECTED to an "
                        "allowlist inside this module — buyerName, shippingAddress, "
                        "paymentType and the transaction breakdown are dropped where they are "
                        "parsed and are returned by no function here. The body is a PLAIN JSON "
                        "document and NOT D65's Knockout postJson form, which is the one thing "
                        "that genuinely does not transfer between the two hosts. 403 is "
                        "order_seller_key_rejected and NOT order_session_expired, because a "
                        "missing filters.sellerKey answers 403 rather than 400 and reads "
                        "exactly like an expired session. Twenty-one named refusal codes. "
                        "TWO SHAPES SINCE D91, because the one it had was refused on every press "
                        "this account ever made: `LastThreeMonths` holds 370 orders against a "
                        "detail cap of 100, the cap counted the WINDOW, and the remedy it printed "
                        "— ask for a narrower range — is one the range vocabulary here cannot "
                        "express. The search pages are walked whole now and are the cheap half "
                        "(one request per 25 orders, no detail call, nothing written); what is "
                        "capped is the DETAIL calls, over the statuses the operator ticked and "
                        "the orders the ledger does not already hold; and what the cap leaves is "
                        "COUNTED and returned as `remaining` rather than silently dropped. The "
                        "status string is the API's own word and is never folded — folding it "
                        "would be the first step toward the vocabulary this module refuses to "
                        "have.",
                # D63 is the ledger this feeds; D65 is the body convention it deliberately does
                # not carry over; D66 is the build order it discharges; D69 is the capture and
                # the entry. D34 and D53 are cited in its own text.
                "governed_by": ["D34", "D53", "D63", "D64", "D65", "D66", "D69", "D91"],
                "tested_by": ["T7"],
                "note": "`search` AND `fetch_open_orders` HAVE RUN AUTHENTICATED; `detail` HAS "
                        "NOT. This entry said the authenticated success path was unexercised "
                        "and the stored value had never been sent until 2026-09-05, while the "
                        "module's own STATUS block — which docs/specs/order-pipeline.md calls "
                        "the primary record — had said otherwise since 2026-08-30. `search` "
                        "returned three real orders, so TCGPLAYER_STORE_COOKIE does "
                        "authenticate this host and one credential serves both; "
                        "`fetch_open_orders` ran 2026-09-02 and was refused `order_too_many` "
                        "after paging far enough to count 370 orders, which is the paging "
                        "proven live and the refusal D91 answers. What remains unexercised is "
                        "`detail`, the half carrying a buyer's name and address, so the PII "
                        "projection is proven against T7's fixtures and against nothing off "
                        "the wire. Every refusal stays reachable with no network — the body "
                        "builder and the projections are pure and public for that, and "
                        "PKMNSCAN_TCG_ORDERS_URL aims it at a loopback socket the way T7 "
                        "already aims the export. PKMNSCAN_TCG_SELLER_KEY must be in .env or "
                        "a live fetch answers 403.",
            },
        },
    },
    {
        "path": "app/",
        "status": "built",
        # step 7 built this directory and is done; 10 is the step still working in it —
        # the motion trigger's constants are tuned here (src/motion.ts) even though the
        # rest of Gate C is physical. scripts/status.py resolves "do this next" through
        # this field, and without it step 10 printed as claimed by nobody.
        "does": "the web app, REBUILT AS BANCHI in 2026-09: a new shell, a shared kit, two "
                "themes, and every screen redrawn against it. ELEVEN routes behind a "
                "hand-written hash router, TEN of them the owner's — home, which took the root "
                "hash and is where the six-stage spine is drawn; the capture screen that Gate B "
                "runs on, now at `#/capture`; the runs screen the pipeline lives on; the review "
                "queue; the pricing worklist; the order screen and the shipping lane (D69 gave "
                "each its own route rather than making one a mode of the other); the one "
                "inventory view (D31 folded the box walk and the pull preview into it); the "
                "code-card screen D70 gave its own route; and `#/gallery`, which is the KIT — "
                "step 6's component page grown into every primitive the product is built from. "
                "One is the Fulfiller's, and the shell deliberately draws no chrome over it. "
                "The count here is RECOUNTED off src/App.tsx's ROUTES table and never "
                "incremented: it has been wrong more often than right — it said "
                "NINE from D70 until 2026-08-31, and #/codes was missing from the list above "
                "outright. TWO ROWS RECONCILE IT NOW and neither existed when the sentence "
                "here ended `and nothing reconciles it`: scripts/docs-audit.py's "
                "`route census` fails a commit where a published count in this file, in "
                "CLAUDE.md or in README.md disagrees with that table, and its "
                "`route rosters` row fails one where a spec's hand-typed list of routes "
                "does. Playwright "
                "specs assert docs/DESIGN.md's Fulfillment floors, one against the kit's "
                "pull-confirm and one against the Fulfillment view.",
        "governed_by": ["D3", "D4", "D5", "D6", "D7", "D9", "D10", "D13", "D18"],
        # What the orphan rule scans here, and the reason this directory needs the key at
        # all: the default is `.py` one level deep, which over a tree holding no Python and
        # keeping all of it in subdirectories is a check that reports a clean scan for having
        # looked at no file in the entry it names. It was inert exactly that way until
        # 2026-08-13 — see the note. `.json` is deliberately absent: it would conscript
        # package-lock.json, and a manifest is not a module anyone writes a `does` for.
        "source_suffixes": [".ts", ".tsx", ".css", ".js", ".html"],
        "note": "THE ORPHAN RULE WAS INERT OVER THIS DIRECTORY UNTIL 2026-08-13, AND IT COST "
                "EXACTLY WHAT docs/DEBTS.md SAID IT WOULD. It filtered on one repo-wide `.py` "
                "suffix, one level deep, so step 7a's thirteen new files landed beside the "
                "described modules and this list named none of them — a green row over an "
                "entry nothing had checked. The rule reaches here now because the entry "
                "declares `source_suffixes` above and scripts/docs-audit.py reads it, which is "
                "the half of that fix that lives in this file. It did its job on the same day: "
                "7b's seven files could not land here unnamed. "
                "Nothing here imports docs/design-refs/: those are drawings of the spec, and "
                "this is built from docs/DESIGN.md itself. "
                "NO ENTRY BELOW CARRIES tested_by, and that is a measurement rather than an "
                "oversight: no harness test imports anything in this directory. Neither "
                "Playwright spec is a harness test — see their own entries. "
                "7b WAS BUILT BEFORE GATE B, AGAINST ITS OWN SPEC, at the owner's explicit "
                "instruction. What that cost was true of every entry below until 2026-08-22, "
                "when Gate B exercised them against 53 real cards: the review queue held 16 "
                "real entries, the owner answered all 16 through the answer route, and the "
                "pull preview found a stored photo at its physical location. Read the 7b "
                "entries as validated in outline and unvalidated in range — one reason code "
                "of twelve fired, and the price-driven type scale is still fitted to a "
                "distribution ($0.04-$0.40, all one band) that cannot exercise it. The "
                "Fulfillment view has still never met an order. "
                "WHAT IS NO LONGER TRUE, recorded because the shape of it is worth keeping: "
                "the three screens shipped unrouted, with no client for their routes and the "
                "review queue's calls arriving as a prop nothing supplied, because src/App.tsx "
                "and src/server.ts were another group's files that session. `make design-check` "
                "was the only check that could tell — it failed 16 of 30, every failure the "
                "missing route rather than a design defect — while harness, lint, typecheck and "
                "docs-audit stayed green. The wiring pass on 2026-08-13 registered the routes, "
                "added one client function per route, and took design-check to 30 of 30. The "
                "finding survives the fix: nothing on the commit path can tell whether a screen "
                "can be opened, and the one check that can is not on it. "
                "THE 2026-09 REBUILD IS THE LARGEST EDIT THIS DIRECTORY HAS TAKEN AND IT LANDED "
                "UNDER NO BUILD-ORDER STEP. Every screen sheet was rewritten against `--bn-*` "
                "tokens, the shell was replaced, `src/kit.css` and `src/kit/` arrived, "
                "`ServerReloaded` was deleted into a toast, and Home took the root hash. What "
                "governs it is docs/DESIGN.md rather than a decision entry, and the honest "
                "reading of that is a gap: a rebuild of the product's whole surface has no `D` "
                "to cite and no step in SHIPPED to sit under. Adding one is a paired edit with "
                "docs/GATES.md, which `build order mirror` checks in both directions. "
                "WHAT IS VERIFIED OF IT: `make design-check`'s Playwright suites, which measure "
                "the Fulfillment floors and the kit's pull-confirm and nothing else. The rest "
                "was walked in a browser at 390, 820 and 1440px wide, in both themes.",
        "modules": {
            # ---- the page, and what builds and runs it ----
            "index.html": {"does": "the single page: the #root main.tsx mounts into, the "
                                   "Banchi title, the SVG favicon out of app/public/, and "
                                   "the three Banchi faces — Manrope, Inter and JetBrains "
                                   "Mono, from ONE host now rather than the two the "
                                   "2026-08-12 palette needed, which is the second license "
                                   "question docs/DESIGN.md kept open closed by deletion",
                           "governed_by": ["D5", "D13", "D94"]},
            "public/favicon.svg": {"does": "the tab icon: the Banchi mark at its SMALL optical cut, bluesteel, GENERATED by scripts/build-mark.mjs — the same drawing `kit.Logo` renders below 64px, and a favicon is 16 to 32px. It carries no feTurbulence: section 11 measured the marbling at those sizes and it loses to a flat prism gradient, which is also what removes the question of whether a favicon pipeline would keep the filter. Vite serves app/public/ at the site root, which is why it is addressed as `/favicon.svg`.",
                                   "governed_by": ["D5", "D94", "D102"]},
            "public/manifest.webmanifest": {"does": "the web app manifest: the two PNG icons, the name, and the dark ground as the splash colour. It exists because `apple-touch-icon` pointed at an SVG, which iOS does not render — so the app had no home-screen icon at all rather than a degraded one. No service worker and no offline story; this is an icon manifest, not a PWA.",
                                            "governed_by": ["D94", "D102"]},
            "public/icon-180.png": {"does": "the apple-touch-icon, and the DISPLAY cut because 180px is squarely inside the range section 3 locks for 64px and up — taper and holographic foil, not the favicon's small cut. GENERATED by `node scripts/build-mark.mjs --icons`, which needs Playwright and is deliberately behind a flag: committing what it writes needs `--no-verify`, since the pre-commit image guard refuses any .png outside captures/ and has no PKMNSCAN_*=off hatch.",
                                    "governed_by": ["D94", "D102"]},
            "public/icon-192.png": {"does": "the manifest's small icon. Same drawing and same generator as icon-180.png.",
                                    "governed_by": ["D94", "D102"]},
            "public/icon-512.png": {"does": "the manifest's large icon, and the one place the display cut is drawn at the size it was designed for. Same generator as icon-180.png.",
                                    "governed_by": ["D94", "D102"]},
            "devPort.ts": {"does": "the ONE dev port for this checkout, imported by both "
                                   "vite.config.ts and playwright.config.ts so they cannot "
                                   "disagree. The main tree keeps 5173; a linked worktree "
                                   "derives its own from a hash of its path, because both "
                                   "configs hardcoding 5173 is what let design-check attach "
                                   "to the MAIN tree's server from a worktree and assert "
                                   "DESIGN.md's floors against code the branch never had — "
                                   "green, and meaningless. Detects a worktree the way "
                                   "scripts/worktree-guard.sh does: `.git` is a file",
                           "governed_by": ["D5", "D13", "D43"]},
            "vite.config.ts": {"does": "the dev server, strictPort — a busy port fails "
                                       "loudly rather than serving on 5174, where CLAUDE.md, the "
                                       "Makefile and scripts/views.txt would all three be wrong. "
                                       "The port comes from devPort.ts: :5173 in the main tree, "
                                       "per-worktree elsewhere",
                               "governed_by": ["D13", "D43"]},
            "playwright.config.ts": {"does": "how `make design-check` runs the spec, including the "
                                             "Vite it starts for itself. reuseExistingServer stays "
                                             "ON and is safe only because devPort.ts makes the port "
                                             "per-checkout. `expect.timeout` is 15s rather than "
                                             "Playwright's 5s: fullyParallel puts every worker's "
                                             "first visibility wait against a cold Vite, and that "
                                             "wait — never an assertion — was the whole of the "
                                             "flake DEBTS.md recorded on 2026-08-30",
                                     "governed_by": ["D5", "D16"]},

            # ---- the ground: what everything else reads ----
            "src/tokens.css": {"does": "BANCHI'S TOKENS, and the only file in app/ allowed to write a "
                                       "color. Named `--bn-*` and grouped by the job rather than by "
                                       "the value: neutrals (bg, surface 1-3, glass), ink 1-4, three "
                                       "line weights, brand (accent with hover/press/two tints, and "
                                       "`live`, the vermilion that means a camera or a capture), the "
                                       "four semantic pairs, three shadows plus an accent glow, the "
                                       "three faces, an 11-step type scale, the 1-10 spacing scale, "
                                       "seven radii, the motion set (three durations, three easings, "
                                       "the list stagger and its cap, four named loops, one disabled "
                                       "opacity), the `--bn-stage-*` palette that is DARK IN BOTH "
                                       "THEMES because a viewfinder and a photo hero are, and the "
                                       "shell metrics. TWO THEMES, ONE SET OF NAMES: light on bare "
                                       "`:root`, and `:root[data-theme='dark']` redefining the "
                                       "surfaces, inks, lines, brand, semantics, shadows and button "
                                       "ground — nothing else, so a component sheet never learns "
                                       "which theme it is in. The LEGACY ALIASES at the foot "
                                       "(--ink, --muted, --line, --s1..--s8, --radius, the three "
                                       "face names) resolve to `--bn-*` and exist so ~40 screen "
                                       "sheets kept rendering the day this landed; they are the "
                                       "thing to delete as each sheet is refined. A media query on "
                                       "`(max-width: 767px), (hover: none) and (pointer: coarse)` "
                                       "raises the three control heights to a thumb's 40-46px — the "
                                       "POINTER decides, not the width, because an iPad in portrait "
                                       "is 820px wide and all thumb.",
                               "governed_by": ["D5", "D13", "D18", "D32", "D50", "D94"],
                               "note": "`scripts/docs-audit.py`'s `design tokens` row reads "
                                       "docs/DESIGN.md's fenced block as hexes, three typefaces, a "
                                       "spacing row and one radius, and merges every `:root` in this "
                                       "file into one dict — so it can express neither an rgba, a "
                                       "duration, a shadow, an alias nor a token that has a light "
                                       "AND a dark value. It cannot pass over this file until its "
                                       "reader is rewritten, and docs/DESIGN.md says so where the "
                                       "block used to be."},
            # D41 and D45 govern this file because of the CURSOR FLOOR, not the reset. That floor
            # is written with element selectors on purpose — `button`, `select`, the three input
            # kinds, `[role='button']` — so it can never reach a `.position-*` class, which is
            # what keeps D41's Fulfiller firewall and D45's walk-to scoping component-graph facts
            # rather than things a global rule could quietly breach.
            "src/base.css": {"does": "reset and the page ground, and the four app-wide floors: the "
                                     "`:focus-visible` ring, the cursor floor added 2026-08-29 after "
                                     "39 of 142 interactive elements were measured with no cursor "
                                     "rule any selector could reach, tabular figures on every table, "
                                     "`output` and `time`, and the reduced-motion floor. All are one "
                                     "specificity, so every per-screen choice outranks them and "
                                     "nothing here can take a cursor away from a stylesheet that "
                                     "named one. TWO THINGS IT GAINED WITH BANCHI: the theme flip is "
                                     "one mechanism for the whole page — `html[data-theme-switching]` "
                                     "eases every color together for --bn-t-slow, because a "
                                     "cross-fade on <body> alone drew dark panels on a light ground "
                                     "for a third of a second — and the reduced-motion rule EXEMPTS "
                                     "the four loops that carry meaning (the busy ring, the skeleton "
                                     "shimmer, the live dot, the two capture spinners), slowed to "
                                     "1.4s rather than frozen, because a ring stopped at a partial "
                                     "arc reads as a disabled button.",
                             "governed_by": ["D5", "D41", "D45", "D50", "D94"]},

            # ---- the kit: the primitives every screen is built from (D94, 2026-09) ----
            # D94 IS THE ENTRY, and D50 is the one it discharges: an interactive element's
            # feedback belongs to the product rather than to each stylesheet, and before the kit
            # there was no product-level place to put it, so every sheet answered the question
            # again. A screen that needs a primitive the kit lacks builds it under a
            # screen-prefixed class and reports it for promotion — it never invents a second
            # Button. docs/DESIGN.md is the long form of what these files hold.
            "src/kit.css": {"does": "every primitive's look, one `bn-` prefix, loaded after base.css "
                                    "and before any screen sheet — so a screen may refine a button "
                                    "and never has to redraw one. Layout helpers, the page header, "
                                    "surfaces, seven button variants across four sizes, kbd chips, "
                                    "pills, chips, the machine-string `code` register, fields, the "
                                    "segmented control, tabs, key/value lists, stat tiles, tables, "
                                    "list rows, empty states, notices, the inline receipt, "
                                    "skeletons, progress, menus, the scrim/sheet/dialog family, the "
                                    "photo frame, `.bn-crop`, and the toast stack. THE MOTION RULE "
                                    "IS IN ITS HEADER AND IS LOAD-BEARING: an enter animation ends "
                                    "at the element's own resting style and is always `backwards` — "
                                    "a finished `both` keeps its last keyframe over every author "
                                    "rule, killing `:hover` transforms and making the element a "
                                    "containing block for fixed descendants. `forwards` is right in "
                                    "exactly one place, `[data-leaving]`, where the node is about to "
                                    "unmount.",
                            "governed_by": ["D5", "D13", "D32", "D50", "D94"]},
            "src/kit/markGeometry.ts": {"does": "the Banchi mark's two optical cuts as static path data, GENERATED by scripts/build-mark.mjs out of docs/specs/logo/sheets/small-cut.html. Never hand-edited: the sheet is the one implementation of the drawing, so the app cannot drift from the spec by being edited. Two cuts because a 1.7 stroke is a scratch at 32px and absent at 16px (logo.md section 3, swept in section 11) — `SMALL` is what ships, since every surface in this product is below 64px, and `DISPLAY` is what #/gallery shows. The geometry does not vary across the six marks; all six generate byte-identical paths.",
                                          "governed_by": ["D94", "D102"]},
            "src/kit/lockupGeometry.ts": {"does": "the lockup as static path data — 番地 and BANCHI OUTLINED, the bracket's arm and its two end discs, the block's dimensions and section 13's eleven settled parameters. GENERATED by scripts/build-lockup.mjs and never hand-edited. Every number is a ratio of the kanji size and the paths are drawn in a 319 x 233 box at kanji 100, so ONE geometry serves every size through a viewBox — which is not only smaller than per-size data but more correct, since a vector scaled by a viewBox cannot re-layout and live text could, and did: the width match had to be SOLVED per size. Carries no `fill`: the component's own <g> supplies it by inheritance so a stylesheet can switch section 16's dark metal, which a fill attribute on the child would make unreachable.",
                                 "governed_by": ["D102"]},
            "src/kit/Lockup.tsx": {"does": "the lockup — 番地 over BANCHI inside the mark's own brackets, drawn entirely from lockupGeometry.ts. THE ACCESSIBILITY CONTRACT INVERTS `Logo`'s AND THEN INVERTS AGAIN: `Logo` is aria-hidden always because every call site names its wrapper, and the lockup IS the word so standing alone it carries role=img and a name — but inside the sidebar's `<a aria-label=\"Banchi home\">` a named child would announce \"Banchi Banchi home\", so that call site passes `decorative`. Three class hooks (.bn-lockup-bracket, -kanji, -roman) exist so the shell can choreograph the collapse; without them it could only fade as one lump. The dark bracket is section 16's `bluesteel` chrome and is switched in CSS, not here — the gradient's id is per-instance, which a stylesheet cannot name, so the instance publishes it as --bn-lockup-metal and App.css decides per theme.",
                                 "governed_by": ["D102"]},
            "src/kit/markPalettes.ts": {"does": "docs/specs/logo.md section 9's six locked marks — prism, bracket, ground and card base per variant, bluesteel the default. GENERATED, but NOT derived: the ground rule applied to the three gold prisms produces the espresso section 8 rejected in favor of true black, so a build that re-derives them redraws marks the spec eliminated. THE ONE FILE IN app/ OUTSIDE tokens.css THAT MAY NAME A COLOUR (D102) — the `raw color` audit row cannot see it, since its scope is app/src/*.css, and `logo parity` stands in its place by reconciling every hex here against section 9 in both directions.",
                                        "governed_by": ["D94", "D102"]},
            "src/kit/index.tsx": {"does": "the primitives as components: Button, Kbd, Pill, Chip, "
                                          "PageHeader, EmptyState, Notice, Segmented, Stat, Logo — "
                                          "plus three things that are not components and belong "
                                          "beside them. `useLeave` keeps an overlay mounted one beat "
                                          "after it closes so the leave animation can run. "
                                          "`cropStyle` is the arithmetic that turns "
                                          "`POST /pipeline/crop-preview`'s rectangle into a picture "
                                          "of the CARD rather than of the stand — it lives here "
                                          "because it was written twice, on the Home hero and the "
                                          "pricing thumbnails, and it is the half that is wrong in "
                                          "silence; the FETCHING is deliberately not here, because "
                                          "asking once for one card and asking for what a scroll "
                                          "brings into view are policies rather than geometry. "
                                          "`readTheme`/`applyTheme` stamp `data-theme` on <html> and "
                                          "remember the choice in `localStorage` under "
                                          "`banchi.theme` — device-local like the camera's "
                                          "deviceId (D27), and nothing about a card.",
                                  "governed_by": ["D5", "D13", "D27", "D32", "D50", "D94", "D95"]},
            "src/kit/Icon.tsx": {"does": "one icon set, 70 paths on a 24-unit grid at 1.75 stroke "
                                         "with round joins, drawn in the Lucide idiom so the whole "
                                         "product speaks one line weight. `currentColor` and "
                                         "`aria-hidden`, so an icon is never the accessible name of "
                                         "anything. `ICON_NAMES` is what the kit gallery draws the "
                                         "whole set from. ADD AN ICON BY ADDING A PATH — a screen "
                                         "that inlines its own <svg> is the drift this file exists "
                                         "to prevent.",
                                 "governed_by": ["D5", "D13", "D94"]},
            "src/kit/toast.tsx": {"does": "one toast stack for the product: any screen calls "
                                          "`toast()`, the shell renders `<Toaster/>` once. FOUR "
                                          "KINDS AND THE DIFFERENCE IS THE RULE — a `receipt` "
                                          "carries the way back (D28's undo window, D57's sale), a "
                                          "`status` expires by itself, an `ok` expires, and a "
                                          "`refusal` stays until it is dismissed, because the "
                                          "server's own message is the one thing a person may need "
                                          "to read twice. Nothing here demands an acknowledgement to "
                                          "dismiss, which docs/DESIGN.md bans. This is where D53's "
                                          "server-restart notice went when `ServerReloaded` was "
                                          "deleted.",
                                  "governed_by": ["D5", "D28", "D53", "D57", "D94"]},

            # ---- the shell ----
            "src/main.tsx": {"does": "mounts App, and fixes the stylesheet order: tokens, then base, "
                                     "then the kit — every later sheet resolves against tokens, and "
                                     "a screen sheet outranks the kit by arriving after it",
                             "governed_by": ["D13", "D94"]},
            # D16 governs a UI file here for one reason worth keeping: App.tsx drives its nav
            # and its render off a single ROUTES table rather than a table plus a switch, and
            # cites D16 for why two lists of the same strings are the drift to avoid.
            "src/App.tsx": {"does": "THE BANCHI SHELL, and the ROUTES table it is all driven "
                                    "off. ELEVEN hash routes, TEN the owner's and one the "
                                    "Fulfiller's: `#/` is Home, which took the root hash in the "
                                    "2026-09 rebuild and moved capture to `#/capture`; then "
                                    "capture, runs, review, pricing, orders, shipping, "
                                    "inventory, codes, the Fulfiller's `#/fulfillment`, and "
                                    "`#/gallery`, which is the KIT now rather than step 6's "
                                    "component page. RECOUNT FROM THE TABLE, NEVER INCREMENT — "
                                    "`route census` fails a commit where this file, CLAUDE.md or "
                                    "README.md disagrees with it, and `route rosters` does the "
                                    "same for a spec's pinned list. "
                                    "ONE TABLE DRIVES FIVE THINGS: the sidebar, the phone tab "
                                    "bar, the command palette, the document title and the "
                                    "render. A route carries its group, its icon, its hotkey, "
                                    "whether it is a nav item, whether it is one of the four "
                                    "phone tabs, and the words a person might TYPE to find it. "
                                    "`GROUPS` is the nav order and its headings — home, "
                                    "Workflow, Sell, Library — and `OFF_NAV` declares the one "
                                    "group the nav deliberately does not draw: `aside`, holding "
                                    "the Fulfiller's screen (sidebar foot, opens in its own tab) "
                                    "and the kit (palette only). Both are constants because "
                                    "`scripts/docs-audit.py` reads them; without `OFF_NAV` that "
                                    "row can only conclude two routes have gone unreachable. "
                                    "THREE KEYBOARDS: `,` is the leader, which draws a "
                                    "which-key overlay and jumps by `hotkey`; Cmd-arrow steps "
                                    "the strip in the order the nav draws it (D51), never "
                                    "wrapping, and is still the one modifier this shell takes "
                                    "for navigation; and Cmd-K opens the palette, which searches "
                                    "label and keywords. `isEditableTarget` is what keeps all "
                                    "three off a typed field. "
                                    "THE THEME LIVES HERE (2026-09): `useTheme` follows the "
                                    "system until a choice is stored, the toggle stamps "
                                    "`data-theme` on <html> and `data-theme-switching` for one "
                                    "beat so base.css can ease the whole page at once. "
                                    "D53'S NOTICE IS A TOAST NOW — `useServer` holds the "
                                    "`onServerBoot` subscription that `ServerReloaded.tsx` used "
                                    "to, and raises a `status` toast; it still SUBSCRIBES and "
                                    "never polls for the boot fact, and the 15s `/status` poll "
                                    "beside it is the online/offline banner rather than the "
                                    "reload. An error boundary wraps each route, so one screen "
                                    "throwing leaves the nav standing. "
                                    "`hasChrome` is unchanged in intent and now covers far "
                                    "more: sidebar, rail, app bar, tab bar, palette, which-key, "
                                    "banner and toasts are all drawn only for the owner, and "
                                    "the Fulfiller's view gets NONE of it — not hidden, not "
                                    "rendered, because docs/DESIGN.md forbids a route out of "
                                    "that view and the owner\'s chrome would fail four other "
                                    "rows of its table on its own. "
                                    "#/boxes WAS the seventh route and D31 deleted it while "
                                    "keeping the screen; the ordinals kept in this file count "
                                    "the order routes were ADDED and not their place in the "
                                    "table, which is why `route census` checks the counts and "
                                    "deliberately not these.",
                            "governed_by": ["D5", "D10", "D13", "D14", "D16", "D20", "D27",
                                            "D28", "D31", "D33", "D39", "D49", "D51", "D53",
                                            "D57", "D61", "D63", "D66", "D69", "D70", "D94",
                                            "D95", "D100", "D105"]},
            "src/Codes.tsx": {"does": "the code-card screen: read a box's QRs into the ledger, "
                                      "see the two lanes C11 tiers the pile into, and hand a "
                                      "lane's codes to a buyer against a named order. The "
                                      "commit reserves every code it returns, permanently — "
                                      "C3's atomic dequeue, and the structural defense against "
                                      "selling one code twice. NOTHING HERE SPENDS: the "
                                      "code-card primary path makes no model call at all, so "
                                      "the two-step gate is about handing over a bearer "
                                      "instrument rather than about money. Deliberately absent "
                                      "from scripts/views.txt so `make screenshot` never "
                                      "renders a live code into captures/ui/. NOT `tested_by` "
                                      "T8: that test asserts the LANE RULE this screen draws "
                                      "(`codes_routes._pool`), which is where the money "
                                      "mistake would happen, and asserts nothing about the "
                                      "rendering. No Playwright spec covers this screen yet.",
                              "governed_by": ["D14", "D20", "D24", "D33", "D56", "D70"]},
            "src/Codes.css": {"does": "the code screen's look. The two lanes are the first "
                                      "numbers drawn, because they are the decision; the "
                                      "duplicate panel takes the one non-hairline border in "
                                      "the file, because a duplicate can mean a code that is "
                                      "worth nothing. Its disabled buttons read `default` "
                                      "until 2026-08-31 — a (0,2,1) override of base.css's "
                                      "(0,1,1) `not-allowed` floor, which is D50's 30-of-41 "
                                      "class — and nothing caught it: the cursor sweep's "
                                      "roster did not list this route, and this checkout's "
                                      "store is empty (D43) so no disabled button renders for "
                                      "it to see even now that it does.",
                              "governed_by": ["D14", "D32", "D43", "D50", "D58", "D70"]},
            "src/App.css": {"does": "the shell's chrome: the sidebar and the rail it collapses "
                                    "to, the phone's top bar and its sheet, the bottom tab bar, "
                                    "the command palette, the which-key overlay, the "
                                    "online/offline server banner, the unresolved-hash panel, "
                                    "the shortcuts sheet and the Fulfiller's crash page. TWO "
                                    "RULES IN IT ARE DESIGN RULINGS RATHER THAN LOOKS: this nav "
                                    "may never render on the Fulfillment view, and his crash "
                                    "page carries no wordmark, no error text and no link out — "
                                    "a crash is the moment he is likeliest to press whatever is "
                                    "offered, so the only control reopens the screen he is on. "
                                    "The chord chip lights when the leader is armed; D51's step "
                                    "deliberately does not wear that class, because it is never "
                                    "armed.",
                            "governed_by": ["D5", "D10", "D13", "D31", "D41", "D49", "D51", "D94", "D95"]},
            # THE TWO `ServerReloaded` FILES ARE GONE AND THE NOTICE IS NOT (Banchi, 2026-09-03).
            # D53's rule is that the boot header is SUBSCRIBED to and never polled, and that the
            # notice demands nothing; neither needed a component of its own once the shell had a
            # toast stack. `src/App.tsx:useServer` holds the same `onServerBoot` subscription and
            # raises a `status` toast — expires by itself, blocks nothing, and still drawn only
            # under `hasChrome`, so it cannot reach the Fulfiller's view. What was deleted is a
            # fixed-position component and its stylesheet, not a behavior.
            # ---- the home screen (Banchi, 2026-09) ----
            "src/Home.tsx": {"does": "`#/`: the product drawn as a picture. A hero deck of the "
                                     "newest identified cards, the SIX-STAGE SPINE — capture, "
                                     "identify, review, price, sell, ship — with a live figure "
                                     "under each stage, the boxes, the recent runs, and one "
                                     "primary action. EVERY FIGURE IS THE STAGE SCREEN'S OWN "
                                     "FIGURE, taken from the same reader that screen uses: a "
                                     "run's stage from `RunsStage.stageOf`, the pull backlog "
                                     "from the ledger's `wanted - recorded`, the pricing count "
                                     "from the worklist's roster, the ship lane from whatever "
                                     "export the hub is holding. So Home can be stale but never "
                                     "a step ahead of the screen it links to — a home page that "
                                     "derived its own counts would be a second vocabulary, which "
                                     "is the drift D16 is for. The hero is cropped to the CARD "
                                     "through `kit.cropStyle` over "
                                     "`POST /pipeline/crop-preview`, because a rig photograph is "
                                     "mostly stand; no crop is not a failure and the deck draws "
                                     "correctly without one, and a reclaimed photograph (D89) "
                                     "leaves the frame rather than a broken image. Each panel "
                                     "loads on its own, so no figure waits on another.",
                             "governed_by": ["D5", "D6", "D10", "D13", "D32", "D33", "D52", "D63", "D69", "D86", "D89", "D94", "D95"]},
            "src/Home.css": {"does": "the home screen's look: the hero and its deck, the stage "
                                     "spine, the box and run cards. The one screen in the app "
                                     "that draws a display figure above 36px — "
                                     "`clamp(36px, 5vw, 56px)`, the only place the type scale is "
                                     "left behind, because this page has one job and it is to "
                                     "orient.",
                             "governed_by": ["D5", "D32", "D94"]},

            # ---- the wire, and the two seams ----
            "src/server.ts": {"does": "the only module that talks to the capture server, so the "
                                      "stop-the-run failure rule is one decision. Surfaces the "
                                      "server's own messages verbatim, and holds the two "
                                      "readers every screen shares: a thrown thing as an "
                                      "owner-side screen draws it, and the position label as "
                                      "the server rendered it.",
                              "governed_by": ["D3", "D4", "D5", "D6", "D7", "D8", "D10", "D13",
                                              "D19", "D21", "D22", "D23", "D24", "D26", "D28",
                                              "D29", "D30", "D32", "D33", "D34", "D37", "D43",
                                              "D46", "D48", "D49", "D52", "D53", "D58", "D59",
                                              "D61", "D62", "D63", "D64", "D65", "D68", "D69",
                                              "D70", "D73", "D76", "D79", "D83", "D86", "D87",
                                              "D89", "D90", "D91", "D92", "D100", "D103",
                                              "D104"]},
            "src/demoFlag.d.ts": {"does": "declares `__BN_DEMO__`, the build-time demo flag "
                                          "`vite.config.ts` substitutes with a boolean "
                                          "literal. It exists because three other forms of "
                                          "the same flag each leaked demo code into a "
                                          "production build; the header records all three, "
                                          "and that the guard must be an `if` and not a "
                                          "ternary.",
                                  "governed_by": ["D13"]},
            "src/demoCamera.ts": {"does": "a camera for a page that has none — a canvas "
                                          "painted with one of the demo's own photographs, "
                                          "handed to `useCamera` as a REAL MediaStream so "
                                          "every `camera.ready` gate in CaptureScreen's 3,255 "
                                          "lines opens the ordinary way and nothing above it "
                                          "changes. Deliberately motionless: the trigger fires "
                                          "on frame difference (D81, D84), so it arms, watches "
                                          "and never captures, which is honest on a page with "
                                          "no disk to write to. Reached through a dynamic "
                                          "import inside `if (IS_DEMO)`.",
                                  "governed_by": ["D13", "D19", "D81", "D84"]},
            "src/demoServer.ts": {"does": "the capture server, frozen — what `request()` talks "
                                          "to when VITE_DEMO=1 builds the published demo. "
                                          "Replays scripts/demo-record.py's bundle for reads "
                                          "and applies the concept-carrying writes (the sale, "
                                          "the review answer, the stand-down, the price, the "
                                          "hold, the rename, the divider) to a mutable copy of "
                                          "it; refuses the rest by name, because a demo where "
                                          "every button is inert argues against the product. "
                                          "Reached through a dynamic import inside `if (DEMO)`, "
                                          "so an ordinary build ships neither it nor the "
                                          "bundle.",
                                  "governed_by": ["D10", "D20", "D26", "D28", "D37", "D43",
                                                  "D49", "D57", "D58", "D86", "D103"]},
            "src/types.ts": {"does": "the shapes the server speaks, in the server's own field "
                                     "names — captures, inventory, boxes, listings and the "
                                     "standing queues. Types only, it emits no JavaScript.",
                             "governed_by": ["D3", "D4", "D6", "D7", "D8", "D9", "D10", "D11",
                                             "D16", "D20", "D21", "D22", "D23", "D24", "D26",
                                             "D28", "D29", "D30", "D32", "D33", "D34", "D36",
                                             "D37", "D39", "D45", "D46", "D48", "D49", "D52",
                                             "D53", "D54", "D56", "D58", "D59", "D61", "D62",
                                             "D63", "D64", "D65", "D67", "D69", "D73", "D76",
                                             "D79", "D83", "D86", "D87", "D89", "D91", "D92",
                                             "D93", "D100", "D103", "D104"]},
            "src/deviceMemory.ts": {"does": "every `localStorage` key the shell owns — the "
                                            "theme and the rail — and nothing else",
                                    "governed_by": ["D13", "D27", "D94", "D95"],
                                    "note": "IT EXISTS BECAUSE OF A LINT RULE, which is the "
                                            "rule working rather than being worked around. "
                                            "`app/eslint.config.js` bans the STORE and not the "
                                            "key, because a selector cannot read a key passed "
                                            "as a const — so the only exception it can express "
                                            "is a named FILE. The theme and the rail were read "
                                            "and written at three call sites in `App.tsx` and "
                                            "two in `kit/index.tsx`; exempting either would "
                                            "have waved through anything those files ever "
                                            "store, and `App.tsx` is the shell. This module and "
                                            "`src/useCamera.ts` are the two named exceptions "
                                            "and between them hold every `localStorage` call in "
                                            "the app. D27 permits only facts about THIS "
                                            "MACHINE: a theme is chosen for the room the "
                                            "operator is sitting in, and D13 keeps everything "
                                            "about a card on the Mac so two devices cannot "
                                            "disagree. Every access is wrapped — a private "
                                            "window throws on the accessor itself, and a "
                                            "preference is never worth a blank screen."},
            "src/useCamera.ts": {"does": "the camera: opened on request and never on mount, "
                                         "deviceId selection, never facingMode (v1 bug 3), the "
                                         "native resolution requested explicitly, and a "
                                         "remembered device that refuses to fall back to another",
                                 "governed_by": ["D13"],
                                 "note": "`started`, `missing` and `error` are three different "
                                         "facts and the screen draws them differently: not "
                                         "asked for yet, not connected, and asked for and "
                                         "failed. Collapsing them makes a working rig look "
                                         "broken on its first paint."},
            "src/encode-worker.ts": {"does": "the capture JPEG encode, on a worker thread the "
                                             "main thread's idle scheduler cannot starve; one "
                                             "reused OffscreenCanvas, fed transferred "
                                             "ImageBitmaps by useCamera's grabFrameJpeg",
                                     "governed_by": ["D13"]},
            "src/trigger.ts": {"does": "the trigger seam: whatever fires a capture, behind one "
                                       "interface. Two implementations now — the key, and "
                                       "src/motion.ts — and the screen still cannot tell "
                                       "which is armed except by the name it renders.",
                               "governed_by": ["D13"]},
            "src/trace.ts": {"does": "D19's Tier-1 tuning instrument: records every frame's "
                                     "(t, d, dBase, luma) plus the watch-region pixels at each "
                                     "gate verdict and once a second, and downloads the armed "
                                     "session as one self-describing JSON from the HUD. The "
                                     "trigger records nothing itself — this hangs off "
                                     "motion.ts's optional onFrame callback. Built 2026-08-22 "
                                     "when the rig session asked for speed data, the exact "
                                     "condition D19 reserved it for. VERSION 2 SINCE 2026-08-31 "
                                     "(D81): a v1 row is [t, d, luma] and a v2 row carries "
                                     "dBase, the number the presence gate now decides on — a "
                                     "trace that cannot show why a card was refused cannot "
                                     "re-score that refusal. scripts/score-trace.py branches on "
                                     "the version field, so a scorer cannot read a v2 trace as "
                                     "a rig with no light in it.",
                             "governed_by": ["D19", "D81"]},
            "src/motion.ts": {"does": "Gate C's auto-capture: a pure MotionMachine (settle, "
                                      "novelty, card presence, deferring refractory) under a "
                                      "thin DOM sampler that feeds it one 64x36 luma grid per "
                                      "decoded frame. BUILT 2026-08-22, TUNED AT THE RIG "
                                      "2026-08-23 off the first 86-cycle feeder trace, "
                                      "confirmed live at 85/85 on box 95. The trigger half of "
                                      "Gate C is confirmed; the pipeline half is not. "
                                      "EVERY THRESHOLD IS A MULTIPLE OF A SESSION MEASUREMENT "
                                      "SINCE 2026-08-31 (D81), which is a change of kind: the "
                                      "presence gate was a brightness compared against the "
                                      "constant 90, and across the four saved traces an empty "
                                      "stand reads 57 while a card on another rig reads 61 — so "
                                      "no constant separates them and that one refused 38 real "
                                      "cards silently across three sessions, 18 of them "
                                      "still refused after the 2026-08-29 quantile change. "
                                      "Presence is now distance from the "
                                      "session's own baseline (empty stand 1.1-1.4, cards "
                                      "17-167), and tLo/tHi ride the median still-frame "
                                      "difference. The seed reproduces the hand-tuned 4.50/8.00 "
                                      "exactly, so the 85/85 run is not re-litigated. "
                                      "tNovel, refractoryMs and maxMoveMs stay absolute, each "
                                      "for a stated reason. "
                                      "D84 (2026-09-01) MOVED THREE THINGS AND ONE OF THEM "
                                      "BACK TOWARDS A CONSTANT: a settle is stillFrames of the "
                                      "last stillWindow rather than a consecutive run, because "
                                      "a two-frame alternation defeats a run absolutely and "
                                      "cost four cards; the stall clock is cleared by a "
                                      "COMPLETED settle rather than by any quiet frame, which "
                                      "is why `stalled` never fired across those four; and "
                                      "presenceMin is 16.0, sized to a HAND arriving with the "
                                      "first card (worst approach 11.15, quietest card 32.5) "
                                      "rather than to lamp drift. That floor now BINDS over "
                                      "presenceK x dTypical on this rig, which D84 records as "
                                      "a debt rather than a design.",
                              "governed_by": ["D13", "D19", "D81", "D84"]},

            # ---- 7a's screens ----
            "src/CaptureScreen.tsx": {"does": "the capture screen, rebuilt 2026-08-23 to the owner-approved Pass D: "
                    "every control one hairline row at rest (key chip, label, value), one "
                    "field open at a time. RE-ORDERED AND RE-BOXED 2026-08-24 by the owner: "
                    "the sidebar is three independent panels down the column rather than one "
                    "panel divided by hairlines — a quiet SESSION box (Game, Camera, Rotation, "
                    "Trigger) at the TOP, the claims (Box, Set hint, Rarity, Finish) in the "
                    "middle, the shutter and undo at the FOOT, 12px of air between. It read "
                    "claims-over-a-SESSION-footer before that. Rarity at rest "
                    "is the bitfield — one 6px mark per rarity of the chosen game, filled = "
                    "claimed; the box list is never rendered as a list (filter, re-indexed "
                    "digits, Enter); small single-selects open as content-sized segmented "
                    "tracks. Camera folded into the row grammar; the camera never opens on "
                    "mount. Undo that names what it would delete. THE BOX FIELD IS ONE "
                    "CONTROL AS OF 2026-08-25 (D20, amended): one free-text entry searching "
                    "number and name together over `GET /boxes`, each row carrying the name "
                    "as `Opt`'s de-emphasised suffix, the creation row drawn LAST so "
                    "Enter-takes-the-top-row cannot make a junk box, a sealed box drawn "
                    "`sealed` and refusing, and creation by name alone — the number is "
                    "allocated server-side, never typed. `boxDraft`, `newBoxRef`, "
                    "`onBoxSubmit` and the box branch of `fieldPick` are gone with it. "
                    "EVERY OPTION RIDES A KEY "
                    "AS OF 2026-08-24, not just the first nine (owner's ruling): `OPTION_KEYS` "
                    "is digits, then `0`, then every letter this screen has not already spent "
                    "— the eight field letters and `c`/`u`, which are the shutter and "
                    "the undo. `n` WAS RESERVED HERE AND IS NOT ANY MORE: it was the jump to "
                    "the Box field's second input, and that input no longer exists, so it "
                    "re-enters the alphabet at its own place. That moves NOTHING before the "
                    "twentieth option — the first thirteen keys are `1234567890ade` either "
                    "way, so Pokemon's thirteen rarities are untouched — and shifts the "
                    "twentieth onward by one letter. Skipped rather than shadowed: a literal a-z hands Pokemon's "
                    "thirteenth rarity the capture key, and either resolution of that fires "
                    "one act while the operator believes the other did. "
                    "A THIRD ACT AS OF 2026-08-29 (owner, D10 amended): `S` opens a section — "
                    "one divider in front of the next card, `POST /boxes/<box>/sections`, no "
                    "index on the wire — and the set hint moved to `H` to free the letter. It "
                    "is on the same manual trigger as the shutter and the undo, never on the "
                    "motion seam, and it takes `s` back out of the option alphabet, which "
                    "exactly cancels `n` leaving it: twenty-five keys, and the first thirteen "
                    "are `1234567890ade` through both changes. "
                    "THE UNDO IS A STACK SINCE THE SAME DAY, also the owner's: the session's "
                    "ten most recent captures into this box, newest first, every row its own "
                    "control. `U` and the trigger seam still mean one card; row N undoes N — "
                    "that card and everything captured after it — by walking the same route N "
                    "times, because D10 lets undo reach the newest capture in a box and "
                    "nothing else. The count is drawn on the row, the list is capped and "
                    "scrolled, and a walk stops at the first refusal and says how far it got.",
            "governed_by": ["D3", "D10", "D13", "D19", "D20", "D21", "D22", "D23", "D27", "D41", "D58", "D65", "D81", "D92"]},
            # D3 earns its place on a stylesheet: the no-claim finish chip is drawn dashed
            # because rung 1 distinguishes "no metadata recorded" from a recorded claim, and
            # that distinction is carried here in a border style rather than in any logic.
            "src/CaptureScreen.css": {"does": "its layout, at the dense end of docs/DESIGN.md's one "
                                              "system, two densities. Owner-side; the Fulfillment "
                                              "floors do not govern here.",
                                      # D65 for the two accent modifiers the set hint's verdict
                                      # draws — accent's "the system is unsure" job at text
                                      # weight, because nothing there refuses anything.
                                      "governed_by": ["D3", "D5", "D27", "D41", "D50", "D65"]},
            "src/PositionLabel.tsx": {
                "does": "ONE rendering of `pipeline/join.py:Position.label` for every OWNER site "
                        "(D41, amended 2026-08-29). Recomposes `Box N \u00b7 Section N \u00b7 Card N` into a "
                        "muted coarse path and a promoted slot figure, deleting the interpuncts; "
                        "the server string is never edited and travels verbatim on `aria-label`. "
                        "Two geometries: `stack` for a standalone label, `run` for one inside a "
                        "running sentence, where the stacked block measured 3.3x the line height "
                        "and orphaned the trailing period. A NUMERIC GUARD refuses to promote a "
                        "slot that is not digits, which is what keeps D24's pooled label "
                        "(`... \u00b7 pooled`) from drawing a lowercase word as a 300px figure. "
                        "THE FULFILLER NEVER IMPORTS IT: his 32px/36px labels stay plain text and "
                        "the firewall is the component graph, not a selector. A TERMINAL THAT IS "
                        "A STATE RATHER THAN A NUMBER IS RANKED TOO (D71): `... \u00b7 departed "
                        "\u00b7 B3 #36` puts the state and the store key on the path and draws the "
                        "number column EMPTY, because what D58 refuses is the figure. Refusing "
                        "the whole treatment over it is what put the pre-D41 plain string back "
                        "on two screens for exactly the cards that had been sold.",
                "governed_by": ["D10", "D20", "D24", "D30", "D31", "D41", "D58", "D68", "D71", "D92"]},
            "src/PositionLabel.css": {
                "does": "the shape, and one knob per site. `--pos-slot` is the only number a site "
                        "chooses; the key is a single clamp and the gap is a token by rule "
                        "(--s5 at a figure >= 40px, --s3 below) so it never lands off "
                        "docs/DESIGN.md's spacing scale. Every selector is `.position-*` and those "
                        "classes exist only where the component rendered them. TWO DERIVATIONS "
                        "CARRY A LABEL WITH NO FIGURE (D71): in a list the whole slot column is "
                        "reserved, key included, so a figure-less row's path starts at the same x "
                        "as every other; as a singleton the path re-ranks "
                        "to clamp(11px, 0.45em, 20px), because with no figure the path is the "
                        "payload. THAT COLUMN IS THE LIST'S, AND IT IS TWO TERMS WITH DIFFERENT "
                        "PROVENANCE (D92, amended 2026-09-04). The figure's width is DATA — how "
                        "many cards are in the box — and is spent here in the figure's own `ch` "
                        "off `--pos-slot-digits`, which src/CardLocations.tsx computes from the "
                        "`place.card` of the copies it is drawing. The key's is TYPOGRAPHY, a "
                        "four-letter word in a second font that no CSS unit measures, and is the "
                        "one constant left: `--pos-slot-key`, 37.594px, declared by src/"
                        "CardLocations.css and spent as padding on the figure-less row. A row "
                        "cannot compute either — it cannot see whether its siblings drew a key, "
                        "nor how many digits they held. THE SINGLE `--pos-slot-col` BEFORE IT was "
                        "right about the fonts and could never be right about the digit count: a "
                        "box past 999 cards overflowed it silently, because the figure is "
                        "flex-shrunk and its glyphs paint outside their own box. Before THAT the "
                        "width was computed from a per-character factor and 3ch of the WRONG "
                        "font, and came out 2.109px short — an assertion app/tests/inventory."
                        "spec.ts carried red from the merge until 2026-09-04. The figure-less "
                        "row carries the figure's FACE, family and weight both, because `ch` is "
                        "the advance of `0` in the element's own face and Manrope is variable. "
                        "The dash in the empty column is `content`, so it "
                        "never joins the label's textContent.",
                "governed_by": ["D24", "D31", "D41", "D58", "D68", "D71", "D92"]},
            "src/PlaceNeighbors.tsx": {
                "does": "D30's neighbors, RANKED rather than joined (D41's move one line down, "
                        "2026-08-30). `after` / `before` as a muted mono key column with the two "
                        "names beside it, champion at ink and epithet muted, connectives deleted "
                        "\u2014 the owner could not pick two names out of `between Galio, "
                        "Indefaticable and Evelynn, Entrancing`, because every Riftbound name is "
                        "`Champion, Epithet` so the strongest punctuation in the string is the "
                        "one that is not a boundary. THE KEYS ARE THE COMPOSER'S OWN TWO WORDS: "
                        "`in front`/`behind` reads better physically and takes the NEIGHBOUR as "
                        "its subject where `placeParts` takes THIS CARD, which would have put a "
                        "screen reader's sentence at odds with the row. Draws nothing \u2014 never "
                        "a guess \u2014 for a pooled card, an older server, a degraded decoration, "
                        "or a box holding nothing else. THE FULFILLER NEVER IMPORTS IT: he keeps "
                        "the joined sentence at 20px body, and the firewall is the component "
                        "graph rather than a selector.",
                "governed_by": ["D22", "D24", "D30", "D31", "D41", "D58", "D92"]},
            "src/PlaceNeighbors.css": {
                "does": "the shape, and two knobs per site \u2014 `--nb-key` and `--nb-name`, "
                        "`--pos-slot`'s shape one component over. The band declares 11/13 and the "
                        "copies row 10/12, because a treatment that is right once is not "
                        "automatically right seven times down a column. Body face and lowercase "
                        "on the names is docs/DESIGN.md's own line (the body face is for "
                        "sentences a human reads) and undoes the borrow of "
                        "`.card-locations-boxname`, whose 10px uppercase tracked mono made the "
                        "only running English in the product a rectangle. A fixed key column so "
                        "the two names cannot disagree about where they start.",
                "governed_by": ["D30", "D31", "D41"]},
            "src/BoxBrowse.tsx": {"does": "the box walk, D31's default way into #/inventory — was #/pull until the "
                    "three routes merged. The card's own capture photo beside its position label "
                    "and, since D30, "
                    "its neighbors and the section's gap count. ONE WRITE since 2026-08-23 "
                    "— the re-shoot control (D26, owner's placement ruling): replace a bad "
                    "stored photo from a file, record untouched, allocator never involved. "
                    "Everything else stays look-only, and the header argues the exception. "
                    "THREE COLUMNS since 2026-08-29, and they are NOT D38's three: the walk, "
                    "the card, and the copies — where D38's third track held BoxOps over "
                    "RunPanel. The run panel left for #/runs (D39) and the box panel moved "
                    "into the walk's column, so what stands beside the card now is its own "
                    "copies, capped by the eleven fact rows. The photograph takes the whole "
                    "middle third at 63:88; the facts are two columns at 1440 and one at 1280. "
                    "The box panel is still a sibling of the card's column rather than a child "
                    "of it, which is what puts it structurally outside the selected-card guard. "
                    "ONE INBOUND PROP since 2026-08-29 (D45): `goTo` walks to a card by store "
                    "key, which is how a copy row on the right reaches the box on the left. It "
                    "drops the search filter rather than letting it swallow the jump, and opens "
                    "the landing's section itself so the scroll has a rendered row to find. "
                    "IT SCROLLS ITS OWN COLUMN AND NEVER THE PAGE since 2026-08-29 "
                    "(`scrollWithin`): scrollIntoView reaches the document scroller, and on a "
                    "sticky column that moves the page without moving the row — measured at the "
                    "document's whole range, which took the nav and this screen's own header "
                    "off the top. A MARKET PRICE on the card panel the same day: card -> `run` "
                    "-> that run's pricing.json (D49), indexed by POSITION because `card.sku` "
                    "is written by emit and is null on every sub-threshold and withheld card. "
                    "The store holds no price at all (D8), so this is the only place one can "
                    "come from, and the age of the reading is drawn with it because `join` is "
                    "re-run against refreshed exports. "
                    "NO ORDER DRIVES THIS WALK, and the two props that let one — `arrows`, which "
                    "handed ArrowLeft/Right to a caller's queue, and `banner`, a third slot "
                    "between the header row and the body — are not here. They came with main's "
                    "envelope walk (D90) and went with it (D96 amended 2026-09-04): the arrows "
                    "step this box and nothing else, the header chip's sentence is its own, and "
                    "the empty-list early return has nothing to yield to. An order's pass through "
                    "the drawers is `src/Orders.tsx`'s own \"Walk the boxes\" mode, which reaches "
                    "this file the way every other caller does — through `goTo` (D45).",
            # D90 is main's order-driven mode, whose two props this file no longer carries; the
            # citation stays so a session reading main's history knows they were removed on
            # purpose rather than lost.
            "governed_by": ["D6", "D8", "D9", "D10", "D16", "D19", "D20", "D21", "D22", "D23", "D24", "D26", "D27", "D30", "D31", "D33", "D35", "D38", "D39", "D41", "D45", "D46", "D49", "D52", "D58", "D67", "D68", "D89", "D90", "D92"]},
            "src/BoxBrowse.css": {"does": "its layout, and why no accent appears anywhere in it. Its list keeps an "
                                  "INSET focus ring and says so — it clips its own overflow, which is the "
                                  "case base.css's standing ring cannot serve. D38's band lives here: the "
                                  "photograph takes its HEIGHT from the fact rows beside it, through a frame "
                                  "whose only child is out of flow, so the image cannot size the row that "
                                  "sizes it. THAT BAND IS GONE since 2026-08-29: the facts left the card's "
                                  "column to cap the copies, so the photograph is sized by its COLUMN again "
                                  "and there is nothing beside it to take a height from. The body is three "
                                  "columns at 22/33/45, and the run line moved to the header row. "
                                  "NO BANNER SLOT: `.browse-banner` came with main's envelope walk "
                                  "(D90) and went with it (D96 amended 2026-09-04), along with the "
                                  "only stylesheet that ever filled it.",
                                  "governed_by": ["D5", "D6", "D13", "D30", "D31", "D32", "D33", "D38", "D39", "D40", "D41", "D90"]},

            # ---- 7b's screens. Built 2026-08-13, BEFORE Gate B; routed the same day ----
            #
            # Every entry in this block describes a file that exists, typechecks, lints clean
            # and opens at a hash. `does` says what the file is for, never that a person has
            # seen it hold a real card — the distinction the whole entry note above is about,
            # and the one a reader skimming `does` lines would otherwise lose.
            "src/ReviewQueue.tsx": {
                # D43 IS THE PORT DECISION AND HAS NEVER GOVERNED THIS FILE. It stood here
                # in the prose AND in `governed_by` until 2026-08-31, which is why
                # `scripts/decision-context.py` recited "the port follows the store" to every
                # session about to edit the review queue. The lookup it names is D46's. D72
                # is the entry for citations that stop pointing at their argument; this one
                # was never right rather than having moved.
                "does": "D46's catalog lookup, reachable from EVERY queued entry (D77) — "
                        "suggested on arrival where the pipeline offered no rows, and drawn "
                        "on `L` where it offered rows that are the wrong card, searchable by "
                        "name, number or SKU, replacing the pipeline's rows rather than "
                        "sitting beside them because both are answered on the same digits; "
                        "the review queue: one card at a time, photo first, the choices "
                        "BESIDE the photograph above 900px and stacked below it, the "
                        "reason as a human label over its machine string, candidate rows "
                        "priced from the export, and an answer that writes and advances with "
                        "no dialog. Reads GET /queues and writes THREE KINDS OF THING back "
                        "through src/server.ts: an identification (D4's answer, single and "
                        "D29's group, both reversible per D28), a CLOSED QUESTION that writes "
                        "nothing to the card at all (D37's stand-down, on the `X` panel with "
                        "its three reasons), and a TERMINAL CARD STATE (D26's retirement, "
                        "offered on the same panel). The panel owns the keyboard while it is "
                        "up, because its choices ride digits that mean candidates everywhere "
                        "else on this screen; the mid-box delete is deliberately not on it.",
                "governed_by": ["D3", "D4", "D5", "D6", "D9", "D10", "D13", "D22", "D23", "D26", "D28", "D29", "D32", "D35", "D37", "D46", "D55", "D67", "D77"],
            },
            # D9 governs a stylesheet here, and it is the sharpest instance of what building
            # 7b early costs: the price bands that drive the type scale are the one set of
            # numbers in this directory invented rather than read out of a module, and D9's
            # threshold is the only real number they are anchored to.
            "src/ReviewQueue.css": {
                "does": "its layout — a photo track sized from its own height beside a "
                        "choice column in the tuned 656px measure, with the worklist as a "
                        "self-scrolling rail so 47 rows cost the page no height — and the "
                        "price-driven type scale that makes the sort "
                        "visible — name size and price size stepping down together, parked "
                        "rows dimmed. Accent outlined, never filled, wherever there are two "
                        "answers. The bands are still a guess: Gate B priced $0.04-$0.40 end "
                        "to end, so every queue row landed in one band and no mixed-value lot "
                        "has tested an edge.",
                "governed_by": ["D5", "D9", "D13", "D24", "D28", "D29", "D32", "D35", "D37", "D41", "D46", "D50"],
            },
            "src/Inventory.tsx": {
                "does": "THE ONE OWNER VIEW OF STORED CARDS (D31). Not two modes — the owner's "
                        "correction on 2026-08-23 was that this is \"find a card in a box-based "
                        "system\", so the box walk is the spine and search narrows it. This file "
                        "is the route, the title, and the sale/retire flow; BoxBrowse owns the "
                        "walk and hands back the selected card, and CopiesPanel draws D7's "
                        "SKU -> positions map for whichever card the walk points at. It also "
                        "carries the four writes that had no client half at all until the same "
                        "day: box-wide and per-card claim corrections, the mid-box delete, and "
                        "the whole-box delete. No cache: there is one place inventory lives and "
                        "it is not here. It also holds the one request that goes the OTHER way "
                        "(D45): a press on a copy's position asks the walk to go there, which is "
                        "the only thing this file tells BoxBrowse to do.\n\n"
                        "NO ORDER DRIVES THIS SCREEN, and the mode that let one is not here. "
                        "Main's D90 came with the merge — the order arriving as a URL parameter "
                        "(`#/inventory?order=<key>`, `#/inventory?orders=open`) rather than a "
                        "route, a queue and a cursor landing the walk on each stop through "
                        "`goTo`, a PICKER over the copies panel (D93), `Mark sold` withheld from "
                        "every row while the queue ran, and one press writing every line of one "
                        "order through `POST /orders/fill`. All of it went with D96's amendment "
                        "on 2026-09-04, the route included, on the owner's ruling after using "
                        "both: \"I don't want the walk picking for me\". The same want is "
                        "answered on `src/Orders.tsx` — the per-copy walk, D97's copy map beside "
                        "each line, and a per-copy undo — and what THIS file carries of an order "
                        "is one READ. `wantedOf` folds `GET /orders`'s resolution into a map from "
                        "copy key to order, re-read after every write and allowed to fail, so a "
                        "copy an open order is waiting on says so on its own row and links to "
                        "#/orders instead of offering a pull. `Mark sold` is drawn on every live "
                        "row here, which is the state this screen has always been in.",
                "note": "IT WRITES NOW, AND ITS HEADER OVERTURNS ITS OWN OBJECTION IN PLACE "
                        "rather than deleting it. The file argued at length that a sold button "
                        "here would be 'the same irreversible-looking write with neither guard, "
                        "and a second place to perform one action'. Both halves are answered "
                        "where they were made: the guards were never Fulfillment PROPERTIES, "
                        "only asserted there, so this screen brought them — a photo-confirm "
                        "panel showing the copy's own stored photo at its position before "
                        "anything was written (D6), and a per-sale receipt with a twenty-second "
                        "undo, offered only when markSold's `restores_to` says a reversal will "
                        "work. The race is the server's to refuse and it does: `already_sold` "
                        "is drawn as a receipt with no undo, the reading Fulfillment.tsx paid "
                        "for with a data-integrity bug. The live cap it once declined to draw "
                        "comes off the wire now (SearchGroup.cap), which is the condition its "
                        "own comment named as what would settle it. "
                        "THE SALE IS ONE PRESS SINCE 2026-08-30 (D57): the owner ruled the "
                        "photo-confirm redundant against the card band D38 draws two inches "
                        "from the row, so that panel is deleted and the copy row's own slot "
                        "becomes `Undo` for the window. The receipt KEEPS its undo beside it, "
                        "because the rows are unmounted by stepping the walk and by a failed "
                        "re-read while the clock runs. The retirement is untouched — its four "
                        "reasons are the write's only input, not an acknowledgement — and "
                        "#/fulfillment is untouched, its two-step being a displacement guard a "
                        "real double-tap sale earned.",
                # D28 is the receipt's undo window and the row that must not move under a finger.
                # D36, D49, D90 and D93 are cited for main's order-driven mode, which this file no
                # longer has — the re-derived queue, the URL as the handoff, the envelope press and
                # the picker. The citations stay so a session reading main's history knows the mode
                # was removed on purpose rather than lost.
                "governed_by": ["D5", "D6", "D7", "D8", "D10", "D13", "D24", "D26", "D27", "D28",
                                "D31", "D33", "D36", "D38", "D39", "D41", "D45", "D49", "D57",
                                "D58", "D68", "D71", "D90", "D93"],
            },
            "src/Inventory.css": {
                "does": "its layout, at the dense owner-side end of the one system, two "
                        "densities — the search field, the found groups, the receipts, and the "
                        "retire panel. ACCENT APPEARS NOWHERE IN IT, and its header has now "
                        "said that twice with the opposite in between: no accent, then exactly "
                        "once in the sale's photo-confirm, then none again once D57 deleted "
                        "that panel on 2026-08-30. The scrim and the confirm rules survive it "
                        "because the retirement inherited them, and a choice between four "
                        "reasons has never been a screen with one thing to do. IT CARRIES TWO "
                        "OF `PositionLabel`'s SEVEN SITE RULES (D71): `.inventory-lone-place` "
                        "and `.inventory-confirm-place`, both at a 20px figure. Both drew the "
                        "raw label until then, and the first is what 92% of the store renders "
                        "through \u2014 a card with no name and no SKU has no group to draw.",
                "governed_by": ["D5", "D6", "D7", "D13", "D26", "D31", "D41", "D57", "D71"],
            },
            "src/InventoryOverlay.tsx": {"does": "ONE OVERLAY PRIMITIVE FOR THE INVENTORY "
                                                 "SCREEN, in four kinds: a right-side sheet, "
                                                 "the phone's bottom sheet, a centred dialog "
                                                 "and the photograph's lightbox. Portalled to "
                                                 "<body> so no ancestor transform can pin it "
                                                 "— which is the kit's own motion rule stated "
                                                 "as a consequence — focus-trapped, Escape "
                                                 "closes, the body stops scrolling behind it, "
                                                 "and focus returns to whatever opened it. "
                                                 "`passKeys` is off by default: a sheet over "
                                                 "the screen must not let the walk's arrow "
                                                 "keys step the card behind it, and the "
                                                 "phone's box sheet is the one case that "
                                                 "wants them through. The panels wear the "
                                                 "kit's `bn-sheet`/`bn-dialog` classes; what "
                                                 "is here is the behavior.",
                                         "governed_by": ["D5", "D31", "D45", "D94"]},
            "src/InventoryOverlay.css": {"does": "those four panels' inner rhythm — the kit "
                                                 "draws the panel, this sets what is inside "
                                                 "it and how wide the sheet is.",
                                         "governed_by": ["D5", "D31", "D94"]},
            "src/BoxOps.tsx": {
                "does": "D20's box object, made visible and editable ON THE BROWSE'S BOX HEADER "
                        "since D31 merged #/boxes away. One header per "
                        "box from GET /boxes: its name, its fill or its frozen capacity, its "
                        "lid, the section layout drawn from the server's own sections_detail "
                        "through PositionBar's spansOf, and per-section counts. Four controls, "
                        "which are the four things D20 says a box has that a person decides — "
                        "register one before a card goes into it, rename it, re-divide it, seal "
                        "or re-open it. Its NUMBER is not among them: that would be a renumber, "
                        "which D10 forbids outright. A fifth, D83's Move to box, sits beside Set "
                        "claims rather than among the four — it acts on the ticked selection or "
                        "the box's on-hand cards, never on the box object itself, and unlike "
                        "Edit dividers it is not a relabel: the source position becomes a "
                        "permanent tombstone and the card is recorded fresh at a destination. "
                        "Two destructive-adjacent controls sit "
                        "beneath them: D34's listing release, drawn over a free plan and "
                        "budgeted by this box's own copies, and D10 ruling 3's whole-box "
                        "delete behind a typed box number.",
                "note": "TWO CONTROLS SAY WHAT THEY WILL DO BEFORE THEY DO IT, and both "
                        "sentences are the decision rather than a nicety. Sealing reads 'Seal "
                        "box — freezes capacity at 59', because from that press every fraction "
                        "in the product divides by that number and a bare 'Seal box' would take "
                        "a permanent decision against a denominator the owner would have to go "
                        "and find; it is disabled outright when the fill could not be read. "
                        "Editing dividers warns first, and says it is a RELABEL AND NOT A "
                        "RENUMBER — D10 as amended: the index is the identity and Section · Card "
                        "are a view of it, so no card and no index moves. That warning is the "
                        "confirm D10 names as the fix to reach for first against its own "
                        "recorded cost, 'a mis-tap relabels a filled box and nothing flags it'. "
                        "It names the first index that moves and counts the cards in the "
                        "sections the change reaches — off sections_detail's own counts, never "
                        "off `fill - from + 1`, which would be exact only if every index up to "
                        "the high-water mark is occupied. That is an assumption about the store "
                        "rather than a fact from it, so the count rounds up to a section "
                        "boundary and the sentence says so. "
                        "NOTHING HERE COMPUTES A SECTION BOUNDARY. types.ts forbids it and "
                        "pipeline/join.py:Position is the only label formula in the repo; the "
                        "spans, the rendered divider list and the denominator are all read back "
                        "off the wire.",
                "governed_by": ["D5", "D10", "D13", "D20", "D21", "D22", "D26", "D27", "D31", "D33", "D34", "D36", "D38", "D41", "D58", "D70", "D83", "D89"],
            },
            "src/BoxOps.css": {
                "does": "the box header, the section track and the editors, at the dense "
                        "owner-side end. No accent anywhere in it and no exception — every box "
                        "carries SEVERAL controls, so a fill would have to pick one and would "
                        "then mean 'important'. Several rather than a figure: this entry and the "
                        "file both said 'four' while five were drawn (D83's Move to box), and the "
                        "two cards controls are each conditional on what the box holds, so the "
                        "row list runs three to five. The seal's weight comes from the number on "
                        "it. NOT A "
                        "PANEL since D38: it is drawn inside the walk's own column, so it carries "
                        "no border of its own, and its sections list is DELETED rather than "
                        "styled — the walk beside it drew the same rows, foldable and tickable, "
                        "while this drew them as inert text.",
                "governed_by": ["D5", "D20", "D22", "D31", "D38", "D40", "D41", "D50", "D83"],
            },
            "src/Fulfillment.tsx": {
                "does": "D5's second persona's entire product: cards to pull in box-walk "
                        "order, photo-confirm before each pull, one-tap mark-sold with an undo "
                        "window. No machine string and no server message reaches this screen — "
                        "both are correct for the owner and neither is his.",
                "governed_by": ["D5", "D6", "D7", "D10", "D13", "D24", "D26", "D69"],
            },
            "src/Fulfillment.css": {
                "does": "the generous 24-64 end of the one system, two densities. Every floor "
                        "in docs/DESIGN.md's constraints table applies to every rule in it and "
                        "none is restated as a comment — they are asserted next door instead. "
                        "The temporary rule that hid the shell nav is gone: src/App.tsx stopped "
                        "rendering it on this route, which is the fix that rule named.",
                "governed_by": ["D5", "D10"],
            },

            # ---- step 6's component and the sheet that renders it ----
            "src/PullConfirm.tsx": {"does": "step 6's component: the pull modal's confirm button. "
                                            "Reused as the capture button rather than copied.",
                                    "governed_by": ["D5", "D6"]},
            "src/PullConfirm.css": {"does": "its three states, and why the key hint is absent by default",
                                    "governed_by": ["D5"]},
            "src/Gallery.tsx": {"does": "`#/gallery`: THE KIT, on one page — every primitive Banchi is built from, every button variant and size, the whole icon set out of `ICON_NAMES`, and the shared components in both personas, so the tokens are LOOKED AT rather than only written. Nothing on it is wired to a server, and since 2026-09-06 that is true of its PIXELS too — `SPECIMEN_PHOTO` is a bundled data URI handed to the Fulfiller specimen through `CardLocations`'s `photoSrc` seam, the one call site of that prop in this product. It is what `make screenshot` renders and where `app/tests/pull-confirm.spec.ts` measures three of docs/DESIGN.md's Fulfillment floors — the four pull-confirm specimens keep their `data-specimen` names and their order because that spec measures the gaps between exactly those. Reachable from the command palette only (App.tsx's `aside` group), which is why it is a route and not a nav item.",
                                "governed_by": ["D5", "D6", "D24", "D50", "D58", "D67", "D68", "D71", "D93", "D94", "D95", "D102"],
                                "note": "THE SHEET DREW FOUR REAL CARDS OUT OF THE OWNER'S STORE UNTIL 2026-09-06. Its `CardLocations` fixtures carry `has_photo: true` on keys 3/40, 7/12, 4/1 and 3/31, and the Fulfiller skin sourced each `<img>` from `photoUrl(box, index)` — so the one page whose entire purpose is being compared against a reference was the one page whose contents depended on which capture server was up and what was in boxes 3, 4 and 7 that day, and `GET /photo/<box>/<index>` serves stored bytes without knowing a code card from a Thievul (D24). The one-line fix — `has_photo: false` on all four — was NOT taken: it buys a closed sheet by deleting the photo-bearing shell from the page whose job is drawing every shell, which is the trade `app/tests/gallery.spec.ts` exists to refuse. The image names its own colors, which is the same exception `src/kit/markPalettes.ts` argues at D102: an illustration's colors, on stage ground that is dark in both themes."},
            "src/Gallery.css": {"does": "the kit page's own layout — the specimen grid and its labels. Not a product screen, and it may not introduce a look the kit does not have.",
                                "governed_by": ["D5", "D94"]},

            # ---- the search-and-sell core: one set of components, two densities ----
            #
            # D5 puts two audiences on one system, and these four are where that stops being a
            # sentence: each takes a `persona` and renders owner-dense or Fulfiller-large from
            # ONE implementation. The alternative — a second component per screen — is what
            # docs/DESIGN.md rejected when it declined two visual worlds.
            "src/PositionBar.tsx": {"does": "D20's sentence drawn: the box as a track, a tick per "
                                            "divider, a marker at this card. Says '#40 of 250 · 16% "
                                            "in' for a sealed box and '#12 of 62 so far' for an open "
                                            "one, because an open box's denominator still moves.",
                                    "governed_by": ["D5", "D10", "D13", "D20", "D24", "D30", "D58", "D68"]},
            "src/PositionBar.css": {"does": "the track at two densities, and the marker",
                                    "governed_by": ["D5", "D20"]},
            "src/CardLocations.tsx": {"does": "one SKU group: every copy, its position, its bar and "
                                              "its sold action. D7's fungibility made visible — every "
                                              "unsold copy is offered, and the listed quantity is read "
                                              "off the SKU rather than counted from the copies. The "
                                              "owner's head carries no card name: the band above it "
                                              "prints one (D38, two renderings of one fact). The "
                                              "owner's position label is a CONTROL where the caller "
                                              "offers `onGoTo` (D45): pressing it walks the box "
                                              "browse to that copy. A transparent button around "
                                              "PositionLabel, not a second treatment; the label "
                                              "and not the row, because the row already holds an "
                                              "action.",
                                      "governed_by": ["D4", "D5", "D6", "D7", "D10", "D20", "D24", "D26", "D30", "D31", "D38", "D41", "D45", "D58", "D67", "D68", "D71", "D92"]},
            "src/CardLocations.css": {"does": "the group at two densities. The Fulfiller's copy is a "
                                              "card with a photo; the owner's is a row. The walk-to "
                                              "wrapper takes the button chrome back off and shows "
                                              "its affordance on hover and focus only (D45).",
                                      "governed_by": ["D5", "D7", "D30", "D31", "D40", "D41", "D45", "D58", "D71"]},
            # ---- the runs screen (D39, 2026-08-29) ----
            #
            # The pipeline moved off #/inventory onto a route of its own at the owner's
            # instruction. RunPanel.tsx did not change shape for it: these three files are the
            # scope it used to get from the walk, answered where there is no walk.
            "src/LiveReconcile.tsx": {"does": "the store-wide reconcile panel on #/runs (D87) — "
                                              "upload one live export, preview, settle. On this "
                                              "screen because its own lede names the four "
                                              "commands and this is the fourth in the shape that "
                                              "is not run-scoped; NOT on #/inventory, which is "
                                              "where a card's state changes and this changes "
                                              "none. Two presses: the settle control is ABSENT "
                                              "until a preview has answered (D33's gate pointed "
                                              "at the ledger), and the same bytes are sent twice "
                                              "rather than re-picked.",
                                      "governed_by": ["D7", "D13", "D33", "D87", "D104"],
                                      # `app/tests/live-reconcile.spec.ts` is the check the hard
                                      # rule says does not otherwise exist — it runs under
                                      # `make design-check`, not at turn end, so it is named
                                      # here in prose rather than in `tested_by`.
                                      },
            "src/LiveReconcile.css": {"does": "the store-wide reconcile panel's own styles — "
                                             "quieter than the run panel above it on purpose, "
                                             "and the stdout block is `white-space: pre` with "
                                             "its own overflow because the report draws "
                                             "fixed-width columns a wrap would break.",
                                     "governed_by": ["D50", "D87"]},
            "src/Runs.tsx": {"does": "#/runs: the page chrome, the box picker, the composer, the "
                                     "store-wide reconcile and the stale-listing markdown, with "
                                     "RunPanel beneath them. Owns the SCOPE and nothing else — a strip of "
                                     "boxes from GET /boxes, and the ticked selection handed over "
                                     "from #/inventory through runHandoff.ts, validated against "
                                     "the registry on arrival so a deleted box falls through to "
                                     "the picker. NOTHING IS SCOPED ON ARRIVAL and it refuses to "
                                     "default: a box chosen for the operator is a box they did "
                                     "not read, and the next press after it spends money.",
                             # D33 is the panel and its money gate; D39 is the move and the
                             # handoff. D20 is the box object the picker draws. D27 is the
                             # sessionStorage carve-out the handoff rides. D10 is cards-not-
                             # high-water on the chip, D32 the crop pair whose estimate the
                             # scope key voids, D38 the layout this left behind.
                             "governed_by": ["D5", "D10", "D13", "D20", "D27", "D32", "D33", "D38", "D39", "D56", "D87", "D100"]},
            "src/Runs.css": {"does": "its page chrome, to docs/DESIGN.md's numbers literally: 16px "
                                     "on all four sides, a 20px display title sharing its line "
                                     "with the scope and the controls, a one-line lede, and the "
                                     "box strip as the first real content inside 150px of the top. "
                                     "No fill on the selected chip — the solid accent is reserved "
                                     "for a screen with exactly one thing to do, and this screen's "
                                     "one fill is the spend button inside the panel.",
                             "governed_by": ["D5", "D33", "D38", "D39", "D100", "D103", "D104", "D105"]},
            # ---- the runs screen's parts (Banchi, 2026-09) ----
            "src/RunsStage.tsx": {"does": "WHERE A RUN IS, in one vocabulary for the list, the "
                                          "run panel and Home. The server says which of the four "
                                          "commands a run is waiting for; this draws that as SIX "
                                          "stages — identify, join, review, price, emit, "
                                          "reconcile — because review and pricing are what a run "
                                          "waits on between join and emit, and a bar that skipped "
                                          "them would jump from a third to five sixths. "
                                          "`stageOf` is the one reader, so no screen can be a "
                                          "stage ahead of another; `runningFor` is a live run's "
                                          "age and is deliberately not used on a finished one, "
                                          "where the same arithmetic answers a different "
                                          "question.",
                                  "governed_by": ["D33", "D39", "D48", "D56", "D94"]},
            "src/RunsComposer.tsx": {"does": "THE IDENTIFY COMPOSER: the one press in this product "
                                             "that spends money, as a staged dialog — which "
                                             "boxes, how each is read, what it costs, and a "
                                             "receipt. THE MONEY GATE IS TWO PRESSES AND NO "
                                             "TYPING (D33): the free preflight has to have run "
                                             "before the confirm exists, and the confirm carries "
                                             "the figure in its own label. THE ESTIMATE IS VOID "
                                             "THE MOMENT THE SCOPE MOVES — a box added, a card "
                                             "ticked, a reading changed — because a confirm whose "
                                             "first step described a different send is not a "
                                             "confirm. ONE PRESS, ONE REQUEST, N RUNS (D48): each "
                                             "box in the cart is its own run with its own "
                                             "reading, because which end of D32's "
                                             "cost-against-sharpness trade is right depends on "
                                             "what is in the drawer. `Runs.tsx` owns which boxes "
                                             "are in the cart and where a ticked selection came "
                                             "from (D39 — `#/inventory` keeps the only mass "
                                             "select); this owns how each is read and everything "
                                             "after the press.",
                                     "governed_by": ["D32", "D33", "D39", "D48", "D52", "D58", "D65", "D76", "D94"]},
            "src/RunsLog.tsx": {"does": "a command's stdout, verbatim, in a well that follows its "
                                        "tail, counts its lines, folds and copies. NOTHING HERE "
                                        "SUMMARISES WHAT A COMMAND SAID — D33 puts every "
                                        "command's output on the screen so that what you saw can "
                                        "be grepped, and a summary is the second vocabulary that "
                                        "rule exists to refuse.",
                                "governed_by": ["D33", "D39", "D94"]},
            "src/RunsDrop.tsx": {"does": "the file controls, as controls that look like the "
                                         "product: a native file input cannot be styled to sit "
                                         "beside a kit button, so the input is visually hidden "
                                         "and its own <label> is the control — a label IS the "
                                         "accessible name of the input it wraps, so this costs "
                                         "nothing in reachability. Both forms take a drop as well "
                                         "as a click.",
                                 "governed_by": ["D5", "D33", "D94"]},
            "src/Markdown.tsx": {"does": "THE STALE-LISTING MARKDOWN (D100), the second sheet off "
                                         "the Runs header and a structural clone of "
                                         "LiveReconcile.tsx — same bn-sheet/bn-scrim shell, same "
                                         "runsOverlay focus trap, same open/onClose contract. "
                                         "Three steps and each press is ABSENT until the read "
                                         "before it has answered, which is D33's gate applied "
                                         "twice: to the press that writes a worklist and to the "
                                         "one that writes the file the operator uploads. The "
                                         "footer carries whichever of the three is next. The "
                                         "export is HELD so the write sends the same bytes the "
                                         "preview described, LiveReconcile's rule and it matters "
                                         "more here — a survey about one file and a worklist "
                                         "written from another would make the numbers on screen "
                                         "about something else. Both consoles are RunsLog wells "
                                         "and neither is summarised (D33). MOUNTED INSIDE "
                                         "#/pricing SINCE D105 AND STILL NOT ON A ROUTE. D100 "
                                         "put it beside the store-wide reconcile because both "
                                         "read one export — kinship of IMPLEMENTATION; a "
                                         "markdown decides a PRICE, so it lives where prices are "
                                         "decided, and its own step-2 press now LANDS rather "
                                         "than navigating, because App.tsx keys the view on the "
                                         "hash minus its query. It takes `revision` and hands "
                                         "back `onCorpusWritten` for that move's one real cost: "
                                         "step 3 writes inventory/prices.json from a subprocess "
                                         "and now shares a tab with the screen holding the "
                                         "digest, which is exactly the hazard D103 built the "
                                         "guard for. Says two things in its own words that no "
                                         "spec can say for it — that nothing is deleted at "
                                         "TCGplayer to lower a price, and that the age it ranks "
                                         "on is OWNERSHIP age.",
                                 "governed_by": ["D7", "D9", "D13", "D33", "D49", "D64", "D86",
                                                 "D87", "D94", "D95", "D100", "D103", "D104",
                                                 "D105"],
                                 # `app/tests/markdown.spec.ts` is the check the hard rule says
                                 # does not otherwise exist — it runs under `make design-check`,
                                 # not at turn end, so it is named here in prose rather than in
                                 # `tested_by`.
                                 },
            "src/Markdown.css": {"does": "the sheet's own chrome, and the prefix names the "
                                         "COMPONENT rather than a screen (D105). It was "
                                         "`.runs-md-*` inside Runs.css until 2026-09-06, which "
                                         "left this component importing another screen's "
                                         "stylesheet and forty class names asserting a host it "
                                         "no longer has. The kit has the sheet and NOT its "
                                         "chrome: `.bn-sheet` is the fixed panel and the phone's "
                                         "bottom-rise, and a scrolling body between a fixed head "
                                         "and a fixed foot is not a kit primitive — this is the "
                                         "runs composer's chrome re-stated for a sheet, the "
                                         "second time and so the last before it is worth "
                                         "promoting. One rule was dropped rather than moved: "
                                         "`.runs-md-shortfall`, whose comment said it awaited a "
                                         "narrowing axis while app/src/types.ts says the field "
                                         "it draws cannot exist. `--bn-*` only.",
                                 "governed_by": ["D50", "D94", "D100", "D103", "D105"]},
            "src/runsOverlay.ts": {"does": "dialog focus for the three runs overlays — the composer, "
                                           "the store-wide reconcile and the markdown sheet: focus lands "
                                           "inside on open, Tab and Shift-Tab stay inside, focus "
                                           "goes back to the opener on close, and Escape closes it UNLESS that "
                                           "overlay has a request in flight — the sheets stay "
                                           "mounted, so a close costs a reopen, but nothing "
                                           "aborts a fetch and its receipt would toast for a "
                                           "sheet that is gone. Its "
                                           "own comment says what it is: the behavior "
                                           "`InventoryOverlay` has, waiting to be promoted to a "
                                           "kit Dialog so the product has one of these rather "
                                           "than two.",
                                   "governed_by": ["D5", "D33", "D87", "D94", "D100"]},
            # ---- the pricing screen (D49, 2026-08-30) ----
            #
            # The owner hand-prices and had never been asked what they wanted a listing price
            # to BE — `match` on `market` was the CLI default running by accident through
            # every run. This is where that decision is made, per SKU, with every export cell
            # in front of it.
            "src/Pricing.tsx": {"does": "#/pricing: the hand-pricing worklist. One row per SKU a "
                                        "run matched, sorted market-descending inside three "
                                        "tiers per section: the rows still wanting a price, the "
                                        "ones already held, then the ones this run can add "
                                        "nothing for, each sunk tier under a heading naming why "
                                        "(D78). The hold tier is a SNAPSHOT taken at load, so a "
                                        "press of H never moves the row under the hand. "
                                        "Carrying ALL "
                                        "fourteen export columns that hold data — the owner's "
                                        "\"all the data from the CSV shown when I make the "
                                        "decision\". The run's rule PREFILLS every row as a "
                                        "visible suggestion that writes nothing; the first digit "
                                        "typed clears it, Enter commits and advances, and m/d/l/s "
                                        "snap the price to a named export column. A hold (D49) "
                                        "keeps every copy of a SKU out of this run's import file "
                                        "with a reason, a note and an optional watch price. "
                                        "NOTHING HERE SPENDS: the box, the cart and the money "
                                        "gate stay on #/runs.",
                                # D9 is the threshold, the floor and the rule that nothing is
                                # defaulted on the operator's behalf; D7 is why this is SKU-scoped
                                # and never card-scoped; D28 is the list-must-not-move rule its
                                # invariant row height exists to honour; D39 is the picker-not-a-
                                # handoff argument; D49 is the screen.
                                "governed_by": ["D4", "D5", "D7", "D9", "D22", "D26", "D28",
                                                "D33", "D35", "D37", "D39", "D41", "D48",
                                                "D49", "D51", "D54", "D56", "D58", "D59",
                                                "D62", "D78", "D79", "D85", "D86", "D89",
                                                "D99", "D100", "D103", "D101", "D105"]},
            "src/Pricing.css": {"does": "the worklist at owner density. One grid template read by "
                                        "the caption AND every row, so the two cannot drift; a "
                                        "row height invariant across every state, because the "
                                        "note lands in a second grid row every zone but the card "
                                        "leaves empty; right-aligned tabular money, so decimal "
                                        "alignment carries magnitude and no guessed type band "
                                        "does; one rule under the last row this run can still "
                                        "act on, which is the sunk group's heading (D78). NO "
                                        "SOLID ACCENT FILL ANYWHERE — every state of "
                                        "this screen is a choice among prices, which is the "
                                        "definition of more than one thing to do. THE "
                                        "BOTTOM-LEFT CORNER IS SETTLED BY GEOMETRY AND NEVER "
                                        "BY z-index (D85): --pricing-gutter is composed from "
                                        "the same button width the grid reads, and both fixed "
                                        "panels start after it, so no panel is ever over a row "
                                        "control and nothing has to win a stacking order.",
                                "governed_by": ["D5", "D9", "D28", "D38", "D41", "D49", "D50",
                                                "D54", "D56", "D62", "D78", "D79", "D85",
                                                "D86", "D103", "D105"]},
            # D62 is the screen half of pipeline/pricehistory.py. D8 governs it because that
            # entry names the export as the pricing source: this draws a reading BESIDE that
            # figure and writes nothing, and the day it prices anything is a change to D8.
            # D49 because the hold it sits against is what wanted a trend and had none.
            "src/PriceHistory.tsx": {"does": "the price-history panel on #/pricing: what one SKU "
                                             "has actually been selling for, over a daily range "
                                             "and a weekly one, drawn beside the hold. A "
                                             "volume-weighted average as the ANCHOR, its bound as "
                                             "a muted sanity check beneath, a momentum reading in "
                                             "words as well as a sign, liquidity and within-bucket "
                                             "spread, and a sparkline over the buckets. TWO WAYS "
                                             "IN AND THEY END DIFFERENTLY (D62, amended "
                                             "2026-08-31): point at a row and HOLD t and it "
                                             "stands while the key is down, latched at the press; "
                                             "the T button's CLICK pins it until it is closed. "
                                             "Neither is follow-focus: a read leaves the machine, "
                                             "so a panel that re-read on the focused row would "
                                             "fire one request per arrow key, and POINTING ASKS "
                                             "FOR NOTHING — only the press does. The footer is "
                                             "the only place the two differ on screen — Close "
                                             "against Keep open.",
                                     "governed_by": ["D5", "D8", "D9", "D22", "D41", "D49", "D50", "D62", "D79"],
                                     "note": "IT PRICES NOTHING AND WRITES NOTHING. The two "
                                             "ranges OVERLAP and are drawn side by side with a "
                                             "sentence saying so — measured on Vilemaw the day it "
                                             "was built, up 71% over the month and down 34% over "
                                             "the year, which is the panel working rather than a "
                                             "contradiction. DIRECTION IS A SIGN AND A WORD, "
                                             "NEVER A COLOR: the palette has no red and no green "
                                             "and accent already means `unsure`."},
            "src/PriceHistory.css": {"does": "that panel at owner density. It shares the "
                                            "photograph's bottom-left corner and the two are "
                                            "mutually exclusive, for the reason Pricing.css "
                                            "chose that corner: bottom-right covers the four "
                                            "reference columns and the price field. The 26px "
                                            "average against the 11px bound is the "
                                            "anchor-versus-sanity-check rule expressed as type "
                                            "sizes, and is the property to preserve if this is "
                                            "ever re-laid-out. Its anchor is stated in "
                                            "Pricing.css and read here rather than re-derived: "
                                            "--pricing-gutter clears the row's T and H, and "
                                            "--pricing-ship-h is the ship bar's MEASURED height "
                                            "(D85) — read by three declarations and set by "
                                            "nothing from D54 until then.",
                                     "governed_by": ["D5", "D41", "D45", "D49", "D50", "D54", "D62", "D85"]},
            # D79 is the batched half of D62, and D62 is why this file is separate from
            # PriceHistory.tsx rather than a mode of it: the panel draws every figure a reading
            # has and the strip draws a shape and a sign, which are two answers to two
            # questions. D8 governs it for PriceHistory.tsx's reason, and harder — a reading
            # drawn one column from the field a listing price is typed into is one keystroke
            # from becoming a price, which is why no figure here is denominated in money.
            "src/PriceTrend.tsx": {"does": "the trend strip in a #/pricing row: a daily and a "
                                           "weekly sparkline with a signed percentage under "
                                           "each, in a real 168px column between the card and "
                                           "MARKET. It answers the question a LIST can answer "
                                           "and a panel cannot — which of these forty-six is "
                                           "moving — and every figure a reading carries stays on "
                                           "T's panel. NO MONEY ON THE ROW: the vwap, its bound, "
                                           "the liquidity and the spread are all one column from "
                                           "the price field, and the distance between reading "
                                           "one and copying it across is a keystroke. An empty "
                                           "cell is the honest drawing of a row nobody asked "
                                           "about, which is every at-cap row and every row "
                                           "before the press.",
                                   "governed_by": ["D5", "D8", "D9", "D22", "D28", "D49", "D50", "D62", "D79"],
                                   "note": "THE SPARK GEOMETRY IS IMPORTED FROM PriceHistory.tsx "
                                           "RATHER THAN COPIED, because the rule a copy would "
                                           "lose is the subtle one: a bucket with no price "
                                           "BREAKS the line instead of interpolating across it — "
                                           "21 of 52 annual buckets on the run this was built "
                                           "against are a card that had not been printed yet, "
                                           "and joining through them draws a year-long slope "
                                           "that never happened."},
            "src/PriceTrend.css": {"does": "that strip at owner density. It spans BOTH grid rows "
                                           "the way .pricing-id does, so 45px carries a 20px "
                                           "shape and a 10px sign without touching the invariant "
                                           "row height D28 depends on. The percentage sits at "
                                           "the row's own metadata register and is tabular, so a "
                                           "column of forty-six lines up on the decimal. "
                                           "DIRECTION IS A SIGN AND NEVER A COLOR (D62): on a "
                                           "list a coloured percentage would be the loudest "
                                           "thing on screen, over the least authoritative thing "
                                           "on it.",
                                   "governed_by": ["D5", "D28", "D41", "D50", "D62", "D79"]},
            "src/cardNumber.ts": {
                "does": "ONE COMPOSER OF THE COLLECTOR NUMBER FOR EVERY SCREEN THAT DRAWS ONE "
                        "(D67). There were three, one per screen, and no two the same: the "
                        "review queue folded a blank on both halves, the copies list folded it "
                        "on `number` and tested `printed_total === null` on the line below, and "
                        "the walk tested null on both. That middle spelling cost a quarter of "
                        "the store — 174 of 676 numbered records store `\"\"` there — and drew "
                        "`198/219/`. The set-code fold is deliberately NOT here: that shape is "
                        "pipeline/join.py:strip_set_code, measured against 2,607 real export "
                        "cells, and a TypeScript copy of it would be number_index_key's own "
                        "cautionary tale repeated. The server sends `number_display` and this "
                        "prefers it, composing the raw pair only when an older server omits it.",
                "governed_by": ["D3", "D13", "D25", "D35", "D55", "D67"],
            },
            "src/storeKey.ts": {
                "does": "ONE SPELLING OF A RECORD'S STORE KEY, AND THE ONE READER OF IT (D68, "
                        "D92). `B3 #96` is what pipeline/join.py:departed_label ends on and "
                        "`5/12` is place_text's pooled form; the regex here reads either off the "
                        "tail of a label and src/PositionLabel.tsx peels it away before anything "
                        "is promoted to the figure. D92's sweep found TWO screens composing the "
                        "first form by hand — the walk's departed row and the capture screen's "
                        "undo filmstrip — written independently from the same two fields, which "
                        "is cardNumber.ts's lesson (D67) on the other number a card carries. Its "
                        "own file rather than an export of PositionLabel.tsx, which imports a "
                        "stylesheet: every vocabulary on this side of the wire is a pure-string "
                        "module for the same reason (reasons.ts, holds.ts, orderReasons.ts, "
                        "cardNumber.ts). Deliberately NOT folded into cardNumber.ts — "
                        "departed_label's own docstring records the owner reading `3/96` as a "
                        "collector number, which is what one module holding both would invite. "
                        "The `#` it writes is the one key in the product wearing the count's "
                        "sigil, and it carries scripts/sigil-check.py's `sigil-ok` marker with "
                        "the reason: a record drawn through it is in no slot to count to.",
                "governed_by": ["D41", "D58", "D67", "D68", "D71", "D92"],
            },
            "src/holds.ts": {"does": "the withhold vocabulary on this side of the wire — the three "
                                     "reasons, their human labels and their panel keys. Declared "
                                     "ONCE, the way src/reasons.ts declares the review vocabulary, "
                                     "and reconciled against pipeline/decisions.py by "
                                     "scripts/docs-audit.py so the drift is visible rather than "
                                     "hoped against. Letters and not digits, because the digits on "
                                     "that screen are price entry.",
                             "governed_by": ["D16", "D22", "D26", "D37", "D49"]},
            "src/orderReasons.ts": {"does": "the order-line vocabulary on this side of the "
                                            "wire — the six reasons pipeline/orders.py:"
                                            "LINE_REASONS enumerates, their human labels and "
                                            "their remedies. Declared ONCE, the way "
                                            "src/holds.ts declares the withhold vocabulary and "
                                            "src/reasons.ts the review one, and its own file "
                                            "rather than an addition to reasons.ts because "
                                            "check_reason_codes reconciles that map against "
                                            "two modules pipeline/orders.py is not. Reconciled "
                                            "in both directions by scripts/docs-audit.py:"
                                            "check_order_reasons; the compiler does the "
                                            "within-app half and cannot import a Python tuple. "
                                            "The lookups take a `string` and fall back to the "
                                            "code itself, so drift arrives on screen as a "
                                            "machine string rather than as a blank row.",
                                    "governed_by": ["D9", "D16", "D22", "D63", "D69"]},
            "src/orderPaste.ts": {"does": "THE ONE PLACE IN THIS APP THAT DECIDES WHAT LEAVES "
                                          "THE BROWSER ABOUT A PURCHASE (D69). It reads pasted "
                                          "order JSON and projects it to "
                                          "{source, number, placed_at, status, lines[]} by "
                                          "ALLOWLIST — no buyer, no address, no city, no "
                                          "postcode, no payment — and NAMES what it dropped so "
                                          "the operator can tell a working PII boundary from a "
                                          "broken one before pressing send. The server's three "
                                          "allowlist tuples are the backstop and not the "
                                          "boundary: an unprojected paste refuses by name "
                                          "rather than being stored with fields quietly "
                                          "trimmed. src/server.ts:ingestOrders takes this "
                                          "output verbatim, so there is exactly one door.",
                                  "governed_by": ["D13", "D63", "D69"]},
            "src/csvUpload.ts": {"does": "the one FileReader every CSV upload in this app goes "
                                         "through, lifted out of RunPanel.tsx on 2026-08-30 so "
                                         "#/runs and #/shipping cannot carry two encodings to "
                                         "disagree about. One decode, one refusal shape, one "
                                         "CsvUpload — a second reader is how a file that joins "
                                         "on one screen refuses on another.",
                                 "governed_by": ["D33", "D61", "D69", "D87"]},
            "src/Orders.tsx": {"does": "THE ORDERS HUB: one screen with two stages (D69), "
                                       "rendered at `#/orders` with the pull stage selected. "
                                       "Which copies this buyer gets and where they are — one "
                                       "read of GET /orders answers the order list and the "
                                       "resolution out of ONE store snapshot, so the two cannot "
                                       "disagree; each line draws its reason large with the "
                                       "machine string beneath it, the six-way counts "
                                       "breakdown, and each pick's place block and held_by. The "
                                       "backlog can be worked one order at a time or as ONE "
                                       "WALK through the boxes, which is the second form of "
                                       "step 11 the order spec records as wanted. The pull is "
                                       "one card and one press, aimed by the row's own "
                                       "capture_id — a mid-box delete, a capture undo or a "
                                       "re-shoot all change which physical card sits at a slot "
                                       "(D10, D58) and the server refuses `capture_id_mismatch` "
                                       "rather than selling whatever is there now. Its undo "
                                       "lives on the RECEIPT rather than on the row, because a "
                                       "successful pull unmounts the row it was pressed on, and "
                                       "the receipt is a kit toast for exactly that reason. "
                                       "Orders arrive by paste (projected by "
                                       "src/orderPaste.ts) or by fetch behind the same control. "
                                       "The tabs move the HASH rather than local state, so "
                                       "bookmarks, the nav and the `,O`/`,S` chords keep "
                                       "working — and because that unmounts the hub, everything "
                                       "worth keeping across the switch lives in "
                                       "src/OrdersHubStore.ts. IT DRAWS NO POSTAGE LANE ITSELF: "
                                       "that is D61's question, answered by "
                                       "src/OrdersShipStage.tsx out of a file this stage never "
                                       "sees, and what the two stages share is a client-side "
                                       "join by order number with nothing written across the "
                                       "seam.",
                               "governed_by": ["D7", "D10", "D24", "D27", "D28", "D36", "D39", "D51", "D57", "D58", "D61", "D63", "D66", "D69", "D91", "D96"]},
            "src/Orders.css": {"does": "the order screen at owner density: the line, its reason "
                                       "and remedy, and the pick rows under it. A copy already "
                                       "spoken for by another line is drawn as spoken for "
                                       "rather than offered twice.",
                               "governed_by": ["D5", "D24", "D40", "D41", "D50", "D63", "D69"]},
            "src/OrdersHubStore.ts": {"does": "THE HUB'S MEMORY ACROSS A STAGE SWITCH. "
                                              "`#/orders` and `#/shipping` are one screen with "
                                              "two stages, and the shell keys its view on the "
                                              "hash — so switching stages unmounts and remounts "
                                              "the hub. What a person would be annoyed to lose "
                                              "lives here instead of in component state: the "
                                              "ledger's last answer, an unsent paste, the "
                                              "filter, and above all THE EXPORT THE CAPTURE "
                                              "SERVER IS HOLDING, which the server cannot list "
                                              "back — a client that forgot it would have no way "
                                              "to find it again. It also declares `SHIP_LANES` "
                                              "in the order `pipeline/shipping.py:LANES` does, "
                                              "so the columns and the router cannot disagree. "
                                              "NOTHING HERE TOUCHES BROWSER STORAGE: it lives as "
                                              "long as the tab, which is the batch's own "
                                              "lifetime, and D27 permits persistence rather than "
                                              "requiring it.",
                                      "governed_by": ["D27", "D61", "D63", "D66", "D69", "D73", "D94", "D96"]},
            "src/OrdersShipStage.tsx": {"does": "the SHIP stage of that hub: TCGplayer's Orders "
                                                "-> Export Shipping read into D61's three "
                                                "lanes, with the Pirate Ship import CSV as a "
                                                "download and a way to forget the batch. FOUR "
                                                "ABSENCES ARE THE DESIGN, and its header says so "
                                                "in the same words: no buyer PII is read out of "
                                                "the batch or rendered at all; no sort and no "
                                                "search, so each lane lists the export's own "
                                                "order and a collapse removes rather than "
                                                "reorders; no weight field and no insurance "
                                                "control, because understated postage is charged "
                                                "back weeks later and insurance is a per-order "
                                                "choice inside Pirate Ship; and no server read "
                                                "on mount, because the server holds no list of "
                                                "batches and there is nothing to read until a "
                                                "file is handed over. The abstention lane is "
                                                "D61's third answer drawn as the pile that needs "
                                                "a person.",
                                        "governed_by": ["D5", "D61", "D66", "D69", "D73", "D94"]},
            "src/Shipping.tsx": {"does": "`#/shipping`: NINE LINES THAT POINT THE ROUTE AT THE "
                                         "HUB — `<OrdersHub stage=\'ship\'/>`. The stage itself "
                                         "is src/OrdersShipStage.tsx, which `Orders.tsx` "
                                         "imports, so the two routes render one screen without "
                                         "importing each other. D69 gave each a route rather "
                                         "than making the lane a mode of the order screen; this "
                                         "file is what keeps that true of the ROUTES while the "
                                         "screen is one.",
                                 "governed_by": ["D61", "D66", "D69"]},
            "src/Shipping.css": {"does": "the lane table and its chips, at owner density. The "
                                         "unjudged lane is drawn as an answer rather than as a "
                                         "fault, because D61's third lane is a deliberate "
                                         "abstention and not a failure to route.",
                                 "governed_by": ["D40", "D50", "D61", "D69"]},
            "src/RunFiles.tsx": {"does": "a run's files, as downloads — extracted from RunPanel on "
                                       "2026-08-30 (D54) so two screens can draw them. The `only` "
                                       "prop is the split: the import CSVs go to #/pricing with the "
                                       "press that writes them, and everything else (report.txt, "
                                       "pricing.json, reconcile.txt) stays on #/runs with the "
                                       "commands that wrote IT. The manifest.json filter travels "
                                       "with the component rather than sitting at each call site.",
                                "governed_by": ["D33", "D49", "D54"]},
            "src/RunFiles.css": {"does": "the download rows — moved verbatim out of RunPanel.css "
                                      "with the component, every class name intact so the two specs "
                                      "that select .run-file-import and .run-file still select what "
                                      "they always did. Carries the min-width:0 truncation fix a "
                                      "real TCGplayer export filename earned.",
                               "governed_by": ["D54"]},
            "src/readiness.ts": {"does": "what `emit` would refuse this run for, on this side of the "
                                        "wire — a second implementation of "
                                        "pipeline/decisions.py:blocking, chosen so the pricing "
                                        "screen's readiness line settles on the keystroke that "
                                        "answers it rather than a round trip later. Shaped to be "
                                        "audited: OWED_REASONS is a flat literal and every reason "
                                        "is constructed by owed(). It answers 'is pricing answered' "
                                        "and NEVER 'will emit succeed' — it sees two of emit's "
                                        "refusals and the sentence on screen says so. It may never "
                                        "read overrides, a hold or the floor, because blocking() "
                                        "reads none of them.",
                                 "governed_by": ["D9", "D16", "D49", "D54"]},
            "src/BoxRuns.tsx": {"does": "what is left of the run panel on #/inventory: one status "
                                        "line saying whether anything is running over this box, "
                                        "and the control that hands the ticked selection to "
                                        "#/runs. NO STEP, NO CONSOLE, NO FIGURES AND NOTHING THAT "
                                        "SPENDS — D33's money gate is two presses that must both "
                                        "happen where the estimate is on screen. Polls GET "
                                        "/pipeline/runs on the panel's own 4s/20s cadence, "
                                        "because a run started in a terminal begins live.",
                                # D39 is why it exists at all; D33 is the gate it must not
                                # become a second door to; D7 is the fungible-copy model the
                                # ticked selection writes against; D13 is one truth on one Mac,
                                # which is why a run this tab did not start still shows here.
                                "governed_by": ["D5", "D7", "D13", "D33", "D39", "D56"]},
            "src/BoxRuns.css": {"does": "one row, and the rule that it must stay one — the whole "
                                        "argument for the panel leaving this screen was its "
                                        "625-1143px height in a column whose question is 'where "
                                        "is this card'. No fill; the control is drawn at "
                                        "BoxOps' own 32px so the two panels in this screen agree "
                                        "about how tall a control is.",
                                "governed_by": ["D5", "D33", "D39"]},
            "src/setHint.ts": {
                "does": "WHETHER A TYPED SET HINT NAMES A REAL SET, ANSWERED AT THE RIG "
                        "(D65, amended 2026-08-31). The field always had rules and never drew "
                        "them: a `datalist` offers TCGplayer's set names and says nothing "
                        "about the string actually typed, so `Spiritforge` and `Spiritforged` "
                        "look identical at the capture screen and part company an hour later "
                        "at the fetch — one scopes the export, the other resolves to nothing "
                        "and widens to the whole category. Mirrors "
                        "`server/tcg_export.py:match_sets` rule for rule (alias table, then "
                        "exact, prefix, colon-code; ambiguous resolves to nothing) and is "
                        "asserted against it by scripts/set-hint-agreement.py, because a "
                        "screen that says MATCHED where the fetch misses is worse than the "
                        "silence it replaced. `unchecked` is a first-class verdict: with no "
                        "vocabulary — no cookie, no network, the list not yet fetched — the "
                        "screen says it cannot tell rather than accusing the operator. It "
                        "JUDGES AND NEVER REFUSES; every string is still storable.",
                # D65 authors the matcher, the vocabulary and the datalist-not-a-select rule;
                # D19 is the 623 ms cadence that forbids a per-keystroke round trip; D22 is
                # the hand-authored alias table this folds through.
                "governed_by": ["D19", "D22", "D65"],
            },
            "src/runScope.ts": {"does": "WHICH DRAWER A RUN WAS OVER, AND WHAT THE OWNER CALLS "
                                        "IT — one answer, three screens (D56). `boxOf` prefers "
                                        "the `box` the server now sends and keeps the "
                                        "scope/capture-directory derivation only as the fallback "
                                        "for a payload that predates the field; `boxLabel` "
                                        "composes `Box 3 · RB Epics`, and `Box 3` ALONE where the "
                                        "box has no name, because D20 leaves a name optional and "
                                        "a placeholder would draw a fault where there is none. "
                                        "It replaced a second implementation of "
                                        "server/pipeline_routes.py:_run_box written in TypeScript "
                                        "with a differently-anchored regex.",
                                # D20 is the name and its optionality; D10 ruling 3 is the deleted
                                # box whose number a run still remembers; D56 is the entry.
                                "governed_by": ["D10", "D20", "D56"]},
            "src/pricingSource.ts": {"does": "WHERE `#/pricing`'s ROWS CAME FROM, AND WHAT MAY "
                                             "BE ASKED ABOUT THEM (D103). One type, two "
                                             "builders, the hash parsing, and the adapter that "
                                             "projects a `MarkdownSku` into what the row draws — "
                                             "no JSX, which is `runScope.ts`'s and "
                                             "`readiness.ts`'s posture. The screen had ONE source "
                                             "and one derived sentinel for it (`run`, null at "
                                             "zero or two-plus runs) gating four separate "
                                             "capabilities; a markdown can take a reading and can "
                                             "never take an emit, which a single sentinel cannot "
                                             "express. So the screen asks about the ROW — "
                                             "`source.history === null`, `source.copies` — and "
                                             "exactly two call sites ask which door it was, the "
                                             "landing deck and the ship bar, where the two modes "
                                             "genuinely are different objects. `SECTIONS` and "
                                             "`PRESETS` stay in `Pricing.tsx` and are passed in: "
                                             "docs-audit's `pricing presets` row reads that file "
                                             "by path. `markdownInHash` is why the lens costs no "
                                             "ROUTES row — `#/pricing?markdown=<stamp>`, on a "
                                             "router that strips `?…`, so eleven routes stays "
                                             "eleven and three mechanical counts do not move.",
                                     # D103 is the entry; D86 is the one answer file the write
                                     # path is keyed by; D62 is the press the trends scoping keeps.
                                     "governed_by": ["D28", "D62", "D86", "D100", "D103"]},
            "src/runHandoff.ts": {"does": "the one module that reads or writes the run scope "
                                          "carried from #/inventory to #/runs — key "
                                          "`pkmnscan.run-scope`, D27's carve-out. NOT CLEARED BY "
                                          "BEING READ, because a reload during a live run is "
                                          "ordinary and a read-once handoff would silently widen "
                                          "what the next press pays for; cleared by the operator, "
                                          "by picking a box, and by arriving with nothing ticked. "
                                          "Validates field by field and falls through to no "
                                          "handoff at all rather than guessing.",
                                  # D3 for the fall-through-rather-than-guess rule its validation
                                  # copies; D13 for the browser-storage ban D27 carves out of.
                                  "governed_by": ["D3", "D13", "D27", "D33", "D39"]},
            "src/RunPanel.tsx": {"does": "THE RUNS, AS MASTER AND DETAIL, on #/runs since D39 "
                                         "and in #/inventory's content column before it. The "
                                         "list is every run directory on disk, re-read while "
                                         "the panel is on screen; the detail is the run the "
                                         "THREE FREE COMMANDS act on — join, emit (pressed on "
                                         "#/pricing) and reconcile — drawn as a stepper against "
                                         "src/RunsStage.tsx's six stages. THE PAID STEP IS NOT "
                                         "HERE ANY MORE: the identify command and its two-step "
                                         "money gate moved to src/RunsComposer.tsx in the "
                                         "2026-09 rebuild, and D33's rule is unchanged by the "
                                         "move — one route can spend, the preflight is free, "
                                         "and the confirm carries the figure. IT HOLDS NOTHING "
                                         "ABOUT A RUN BETWEEN RENDERS EXCEPT WHICH ONE IS OPEN: "
                                         "every figure is read from "
                                         "`GET /pipeline/runs/<name>`, so a run started in a "
                                         "terminal appears here and a run started here survives "
                                         "the tab closing. Every command's stdout is shown "
                                         "verbatim in src/RunsLog.tsx's well and the import CSVs "
                                         "are downloads, which is the gap docs/GATES.md names as "
                                         "what Gate B did not close. THE EXPORT IS FETCHED "
                                         "RATHER THAN DOWNLOADED AND UPLOADED (D64), asked for "
                                         "at the width D76 makes a per-game rule, with "
                                         "`SCOPE_REASON` saying in the operator's words which "
                                         "voice chose it. THE DELTA GUARD IS RETIRED and both "
                                         "`Fetch anyway` buttons went with it: it refused a file "
                                         "that was smaller or had nothing to compare against — "
                                         "the very improvement it existed to allow — so the "
                                         "client answers the server's two refusals once, up "
                                         "front, and a fetch produces a RECEIPT rather than a "
                                         "question.",
                                 # D1 is why one step spawns and three answer in the request. D9 is
                                 # the decisions document this panel edits as text rather than as a
                                 # form. D3 is the finish-claim bypass its join control offers. D31
                                 # is why it WAS a panel on #/inventory rather than a route; D39 is
                                 # the owner overruling that, and this file is unchanged by it — the
                                 # scope arrives as a prop either way. D32 is the crop and the
                                 # max-edge, both of which the composer now presses.
                                 "governed_by": ["D1", "D3", "D9", "D13", "D16", "D28", "D31", "D32", "D33", "D39", "D48", "D49", "D54", "D56", "D64", "D65", "D76", "D86"]},
            "src/RunPanel.css": {"does": "the panel at owner density — the 4-16 end of the scale, mono "
                                         "on every number, and exactly one solid accent fill: the "
                                         "button that spends, drawn only once the estimate is on "
                                         "screen above it. NOT a fold since 2026-08-24: the owner "
                                         "asked for the buttons to be present rather than one press "
                                         "away, so D33's ~250px-reached-once-a-box argument is "
                                         "superseded and the disclosure rules are deleted. Since D38 it "
                                         "has the third column to itself at 370px, so its step titles "
                                         "drop to 14px body and its controls to 32px — the height "
                                         "BoxOps gives the same job over in the walk's column. ALL FOUR "
                                         "STEPS draw in every state now, controls absent until a run is "
                                         "picked; the list polls at two cadences because a run started "
                                         "in a terminal begins live. Carries the crop preview under the "
                                         "reading chips: a 200px frame with the cut drawn over it, and the "
                                         "collector-number strip at 1:1 because a band scaled to the column "
                                         "makes 1200 and 900 look identical. Since D48 the chips are drawn "
                                         "once per box in the cart, capped so they stay chip-sized on a "
                                         "full-width route rather than spanning it.",
                                 "governed_by": ["D28", "D31", "D32", "D33", "D38", "D40", "D48", "D50", "D54", "D64", "D76", "D86"]},
            "src/reasons.ts": {
                "does": "the review queue's fourteen reason codes and their human labels, in one "
                        "file because TWO screens read them since 2026-08-25 — #/review works "
                        "them in order, and #/inventory's card panel says whether the selected "
                        "card has an open question. Extracted rather than copied, and its "
                        "docstring is the argument: nothing keeps these labels in step with "
                        "pipeline/variant.py and pipeline/routing.py, and the defense is making "
                        "that drift VISIBLE rather than silent — a second copy in one app would "
                        "defeat it, since the two would drift against each other as well and "
                        "only one would ever be looked at. `reasonLabel`'s `?? reason` fallback "
                        "is contract, not guard: an unknown code renders as itself.",
                "governed_by": ["D4", "D16", "D23", "D35", "D37"],
            },
            "src/SearchField.tsx": {"does": "the debounced query box. Owner gets a `/` hotkey and a key "
                                            "hint; the Fulfiller gets neither — his screens are touch "
                                            "and show no keys.",
                                    "governed_by": ["D5", "D13"]},
            "src/SearchField.css": {"does": "the field at two densities", "governed_by": ["D5", "D50"]},
            "src/keys.ts": {"does": "isEditableTarget, hoisted at its fourth copy — the one "
                                     "question every keyboard handler asks first. The three "
                                     "prior copies each recorded the hoist as due; this is "
                                     "the debt paid.",
                            "governed_by": ["D5", "D13"]},
            "src/useSearch.ts": {"does": "GET /search behind a debounce, with an out-of-order guard so a "
                                         "slow early answer cannot overwrite a fast later one",
                                 "governed_by": ["D5", "D13"]},

            # ---- what checks the above ----
            "eslint.config.js": {
                "does": "the two v1-bug rules docs/DECISIONS.md's table has named as guards since "
                        "it was written and never had: no facingMode (bug 3), no split(\",\") CSV "
                        "parsing (bug 2). No shared preset, no --fix — D18 keeps anything that "
                        "writes off the path `make check` runs.",
                "governed_by": ["D13", "D16", "D18", "D27"],
            },
            "tests/motion.spec.ts": {
                "does": "the MotionMachine against synthetic frame sequences with an exact "
                        "answer key: settle fires once, the novelty gate refuses the same "
                        "card, an empty stand is suppressed, a jam stalls without firing, "
                        "the refractory defers instead of dropping, and a reused mutated "
                        "buffer cannot zero the diff. Since D81 it also pins what the machine "
                        "measures for itself: every sequence arms on an EMPTY STAND because "
                        "that is where the baseline comes from, a dim card on an under-lit rig "
                        "fires where no brightness constant could admit it, a run of no-card "
                        "verdicts is counted consecutively, `rebaseline` moves the reference, "
                        "and the thresholds climb off a noisy session's own floor without "
                        "following a burst up. Run by `make design-check`. Since D84 it also "
                        "pins the two defects that entry is about: a card whose every other "
                        "frame lands in the Schmitt band still settles and fires, and a scene "
                        "that never completes a settle is STALLED however quiet its odd "
                        "frame. Both fail on the code that preceded D84.",
                "governed_by": ["D19", "D81", "D84"],
                "note": "NOT a harness test, same as its siblings. Pure arithmetic — no page, "
                        "no server: the machine takes (nowMs, cells) and that is the whole "
                        "reason it is a class apart from the DOM wrapper.",
            },
            "tests/motion-live.spec.ts": {
                "does": "the DOM half in a real browser against the real capture screen: the "
                        "mode toggle arms the machine, a canvas stream stands in for the Cam "
                        "Link, a settle becomes a fire, and a fire with no box selected is "
                        "COUNTED as dropped rather than silently eaten. The synthetic scene "
                        "is injected at the feeder's dark GAP since D81, because the machine "
                        "is armed over it and that is what the session will call nothing; the "
                        "spec also pins that the seeded thresholds are Gate C's hand-tuned "
                        "4.50/8.00 to two places, and that the saved trace is version 2. Run "
                        "by `make design-check`.",
                "governed_by": ["D5", "D13", "D19", "D81", "D84"],
                "note": "No box is ever selected in this spec, deliberately: with one, the "
                        "fire would POST /capture into a real store. The dropped counter IS "
                        "the assertion.",
            },
            "tests/capture-claims.spec.ts": {
                "does": "the capture screen's claim controls in a real browser: the Finish "
                        "track is a MULTI-SELECT (D3 rung 1's set), the claim is held in the "
                        "game's enum order rather than tap order, re-tapping the last cell "
                        "clears it and stores nothing, a sessionStorage value written before "
                        "the claim was a set reads back as one member, and narrowing a "
                        "two-member claim to one CLEARS it rather than promoting a filter "
                        "into a determination. And, since 2026-08-24, the option alphabet "
                        "over a thirteen-rarity fixture: the tenth rides `0` and the "
                        "eleventh `a`, the last two ride `d` and `e`, and — the case that "
                        "matters, which is negative — `c` stays the shutter and `b` stays "
                        "the Box field, because a literal a-z would have put Rainbow Rare on "
                        "the capture key. Run by `make design-check`.",
                "governed_by": ["D3", "D22", "D23", "D27", "D65", "D101"],
                "note": "The shutter is never pressed, so no capture is ever taken — "
                        "motion-live.spec.ts's rule, for its reason. The `S` cases DO select a "
                        "box and stub the section route, because the act writes to one; "
                        "nothing here reaches a store either way, and capture-undo.spec.ts is "
                        "the file that genuinely captures. It "
                        "exists because nothing ran these controls at all: when the claim "
                        "became a set, tsc, eslint and every spec stayed green over a "
                        "control that had never been pressed by anything but a human.",
            },
            "tests/capture-undo.spec.ts": {
                "does": "the undo STACK on the capture screen (D10, the owner's list of ten, "
                        "2026-08-29): the session's captures newest first and capped at ten, "
                        "the top row carrying `U` and every other row its own depth, `U` "
                        "undoing exactly one, a row undoing that card AND everything after "
                        "it, and a walk refused partway reporting how far it got in the "
                        "server's own words. Run by `make design-check`.",
                "governed_by": ["D10", "D41", "D58", "D101"],
                "note": "THE ONLY SPEC THAT CAPTURES, and it is the opposite of "
                        "capture-claims.spec.ts's rule rather than an exception to it: "
                        "`POST /capture` and `DELETE /inventory/...` are both intercepted, so "
                        "nothing reaches a store, and the camera is a canvas behind a stubbed "
                        "getUserMedia rather than a device. What only a browser can catch "
                        "here is the ORDER: the walk is N sequential requests where the "
                        "(N+1)th is legal only because the Nth succeeded, and a Promise.all "
                        "would type-check, pass, and delete one card of three. Observed "
                        "failing against exactly that mutation before it was kept.",
            },
            "tests/cursor.spec.ts": {
                "does": "what every control says to the pointer, in two cases that cover "
                        "different things. A live sweep walks EVERY registered route — the "
                        "hashes are read off the nav strip, which App.tsx renders from the same "
                        "ROUTES table it routes from — classifies each rendered control by tag, "
                        "type and disabled state, and asserts the cursor the rule requires. No "
                        "selector roster and, since 2026-08-31, no route roster either, so "
                        "neither a control nor a SCREEN added next month can be missed. A "
                        "synthetic case then probes base.css's floor "
                        "with elements it builds itself, because this checkout's store is empty "
                        "(D43) so no screen renders a DISABLED control — deleting the whole "
                        "disabled arm was mutation-tested and the live sweep alone PASSED, "
                        "which is 30 of the 41 original defects invisible. A third case asserts "
                        "the --field-hover edge responds and that no hover reflows the box. Run "
                        "by `make design-check`. THE SWEEP IS NO LONGER LIVE AS OF 2026-09-06, "
                        "and calling it live was the defect: this file registered no "
                        "`page.route` at all, so in the main checkout it swept the OWNER'S 767 "
                        "real cards while its own header said it swept `this worktree's empty "
                        "store` — the number of controls it looked at was a property of which "
                        "tree ran it. It takes `app/tests/shell.ts`'s small store now: 354 "
                        "controls, the same in every checkout, against 332 a dead capture port "
                        "drew here, the gain concentrated where the store is (#/inventory 16 to "
                        "33, #/review 17 to 21). A FLOOR OF 300 GUARDS THAT — the same rule the "
                        "roster harvest already applies to itself, because a fixture regression "
                        "would leave every screen on its empty state and turn the richest sweep "
                        "in this suite into a loop over nothing, passing instantly and forever.",
                "governed_by": ["D28", "D43", "D50", "D69", "D70"],
                "note": "IT WAS A PINNED ROSTER OF SEVEN HASHES FOR TWO DAYS, four lines under "
                        "its own header warning against exactly that. D69 added #/orders and "
                        "#/shipping and D70 added #/codes; none reached the list, three screens "
                        "were swept by nothing, and design-check stayed green — a roster missing "
                        "a route walks the routes it has. Widening it found a live defect of the "
                        "30-of-41 class on #/codes. NOT a harness test and not registered in "
                        "harness/run.py:TESTS — it starts a browser. KNOWN LIMIT, so a green run "
                        "is read for what it is: between the two cases the floor is covered "
                        "completely and a SCREEN's own override only where that screen renders "
                        "it. A per-file rule on a control this empty store never draws is "
                        "unchecked by either — the #/codes defect was found by reading the "
                        "sheet, not by the sweep — and closing that needs fixtures for ten "
                        "screens.",
            },
            "tests/brand.spec.ts": {
                "does": "the mark, in the browser that draws it: the sidebar brand names itself "
                        "without the mark and does not become a second `bn-nav-link` outside "
                        "`<nav>` (which `cursor.spec.ts` counts), the SMALL cut ships below "
                        "64px carrying no filter and no cap discs, the DISPLAY cut is what "
                        "`#/gallery` shows at 64 and above, all six locked palettes are drawn "
                        "and differ, and the mark does not invert with the theme.",
                "governed_by": ["D94", "D102"],
                "note": "IT EXISTS BECAUSE NOTHING IN app/tests MENTIONED THE MARK AT ALL. No "
                        "snapshot, no brand assertion, no reference to `Logo` — the mark could "
                        "have stopped rendering in all six of its call sites with `make check` "
                        "and `make design-check` both green. `make docs-audit`'s `logo parity` "
                        "row compares two literals and cannot see a screen, which is "
                        "CLAUDE.md's hard rule and docs/GATES.md step 7's recorded failure. "
                        "The cut boundary is the assertion that earns this file: it is one "
                        "number in one expression, every call site in the product sits below "
                        "it, and shipping the display cut into a 32px rail is section 9's own "
                        "measured failure. Observed red under `size < 64` -> `size < 16`.",
            },
            "tests/gallery.spec.ts": {
                "does": "the four row shapes `CardLocations` draws that no other spec reaches "
                        "— the departed shell (`is-gone is-nobar`), the pooled one, the "
                        "current one, and the state cell's single pill — asserted against "
                        "`#/gallery`'s own fixtures rather than a server. One count per shape, "
                        "so a fixture that quietly stops producing one is caught. Since "
                        "2026-09-06 it also reads every specimen photograph's `src` back off "
                        "the DOM: four bundled data URIs and two missing-photo sentences, and "
                        "nothing addressing `/photo/`. That assertion is the one that survives "
                        "`shell.ts:stubStore`, which answers the photo route — so the seal "
                        "alone could never have said the sheet had stopped asking.",
                "governed_by": ["D6", "D24", "D58", "D68", "D71", "D93"],
                "note": "IT EXISTS BECAUSE THE SHEET WAS INCOMPLETE AND NOTHING SAID SO, "
                        "2026-09-05. `docs/DEBTS.md` section 5 recorded the departed row as "
                        "absent from the kit; the sold fixture inherited a numeric `slot` from "
                        "the base, so `isDeparted` was false and the shell was rendered "
                        "NOWHERE on a page whose entire purpose is that every shape is looked "
                        "at. A `scripts/docs-audit.py` row would be the wrong instrument: "
                        "re-implementing `isDeparted` in Python goes green against a fixture "
                        "that renders nothing, which is this repo's vacuous green. Only a "
                        "browser can say the row was drawn. Not a harness test and not in "
                        "harness/run.py:TESTS; it runs with the other Playwright specs.",
            },
            "tests/pull-confirm.spec.ts": {
                "does": "three rows of the Fulfillment constraints table against step 6's one "
                        "component: 44px targets, 20px body, 7:1 contrast, 12px apart. Run by "
                        "`make design-check`.",
                "governed_by": ["D5"],
                "note": "NOT a harness test and not registered in harness/run.py:TESTS. The "
                        "harness contract in docs/GATES.md is seven Python tests run at turn "
                        "end; this runs a browser and is invoked on its own.",
            },
            "tests/shell.ts": {
                "does": "one call, `sealEveryTest()`, at the top of every spec that mounts the "
                        "app — all seventeen of them. It installs a catch-all on THIS "
                        "checkout's capture port (D43) that RECORDS and REFUSES, answers the "
                        "shell's own `GET /status`, and asserts when each test ends that "
                        "nothing else got out. `App.tsx:useServerPresence` polls that route "
                        "from outside every route boundary, so it belongs to no screen and a "
                        "file that stubbed everything its own screen asked for still missed "
                        "it: ten specs leaked, and `cursor` and `gallery` leaked boxes, "
                        "inventory, runs and four real card photographs besides. In the main "
                        "tree that port is the owner's live server over their real store; in a "
                        "worktree nothing answers and the shell draws a 44px offline banner "
                        "that moved every geometry floor — two of the nine design-check "
                        "failures fixed on 2026-09-05 were that banner, reported as bare pixel "
                        "counts. It also carries the SMALL STORE the five fixture-less specs "
                        "take, so `cursor.spec.ts` sweeps the same populated screens in every "
                        "checkout: 354 controls against the 332 a dead port drew here, and "
                        "against a main-tree number nobody could reproduce. THE SEAL MUST BE "
                        "THE OLDEST HANDLER, since Playwright matches routes newest-first, "
                        "which is why the call is a module-scope hook and why "
                        "`scripts/docs-audit.py`'s `spec seal` row checks that it comes before "
                        "the file's first `test.beforeEach` — the one way this can fail "
                        "silently. Not a harness test; it has no test of its own and is "
                        "exercised by every spec that imports it.",
                "governed_by": ["D16", "D37", "D43", "D46", "D56", "D58", "D63", "D70", "D86"]},
            "tests/fontsReady.ts": {
                "does": "one helper, `settleFonts`, awaited after every `page.goto` in the seven "
                        "specs that measure type — it said FOUR until 2026-09-06, and the "
                        "three that joined since arrived with nothing reading the sentence. `app/index.html` fetches its two faces with "
                        "`&display=swap`, which paints a fallback first and re-lays-out on "
                        "arrival — right for a reader, wrong for a ruler, because a "
                        "`getBoundingClientRect` taken inside that window measures a different "
                        "typeface than the assertion was computed against. It closes the CAUSE "
                        "of the narrower half of the design-check flake; `expect.timeout` and a "
                        "one-`evaluate` read close the recorded red and the exposure. Weakens no "
                        "assertion. Not a harness test; it has no test of its own and is "
                        "exercised by every spec that imports it.",
                "governed_by": ["D16", "D38", "D50"]},
            "tests/nav.spec.ts": {
                "does": "the shell's keyboard, and the first test this app has had of the strip "
                        "every screen sits under: D51's Cmd-arrow steps the ring in the order "
                        "the nav draws it, both ends stop, and the three refusals hold — a bare "
                        "arrow belongs to the screens, a held Cmd in a text field belongs to the "
                        "caret, and a screen outside the ring keeps the browser's key. Not a "
                        "harness test; `make design-check` runs it.",
                "governed_by": ["D5", "D31", "D39", "D43", "D51", "D69", "D70", "D86", "D100", "D105"],
                "note": "ITS RING IS PINNED ON PURPOSE AND RECONCILED AT THE COMMIT. A ring "
                        "derived from App.tsx could not assert the ORDER against anything "
                        "independent, so the copy stays and carries a `ROUTE-ROSTER hotkey` "
                        "marker that scripts/docs-audit.py's `route rosters` row checks against "
                        "the table. Added after D70 put #/codes in the product's ring and not in "
                        "this one, which left design-check red. TWO OF ITS CASES COULD NOT FAIL "
                        "AND WERE CHANGED, which is the part "
                        "worth keeping. The leader-disarm case retried an assertion that "
                        "CHORD_MS satisfies on its own after a second, so it went green against "
                        "a build with the disarm deleted; it reads the attribute two frames "
                        "after the hash changes now. A case pressing the step on the "
                        "Fulfiller's view was deleted outright — `enabled` refuses there AND "
                        "the ring does, so no single mutation makes it fail. What guards him is "
                        "the end-of-ring assertion, red the moment a hotkey is added to his "
                        "row. It cannot see whether the BROWSER honours preventDefault: "
                        "Playwright presses keys through the debugging protocol, which never "
                        "fires a browser shortcut at all.",
            },
            "tests/orders.spec.ts": {"does": "the order screen in a browser: that the six-way "
                                             "counts render including the zeros, that a pick "
                                             "already held by another line is drawn as spoken "
                                             "for, that the pull sends the row's own "
                                             "capture_id, and that the receipt reads the "
                                             "pre-write place rather than the sale's departed "
                                             "label. TWO CASES OVER THE TWO-PRESS FETCH (D91): "
                                             "the first press details nothing and draws the "
                                             "window as the wire spelled it, the second details "
                                             "only the ticked statuses and skips what the ledger "
                                             "holds, and a fetch the cap cut short says how many "
                                             "it left — while an empty one still re-reads the "
                                             "ledger, which is the bug the early return was. It "
                                             "asserts NOTHING about the order walk; that is "
                                             "app/tests/order-walk.spec.ts. Not a harness test — "
                                             "it starts a browser; `make design-check` runs it.",
                                     "governed_by": ["D24", "D28", "D36", "D49", "D58", "D63", "D69", "D73", "D90", "D91", "D96"]},
            "tests/shipping.spec.ts": {"does": "the shipping screen in a browser, and its "
                                               "strongest cases are ABSENCES: no buyer name, "
                                               "address, city or postcode appears anywhere on "
                                               "the rendered screen, the three lane counts "
                                               "including the zeros do, and the file link "
                                               "points at /shipping/batches/<batch>/file?name=. "
                                               "The POST body is asserted to carry exactly "
                                               "['content','name'] — a wider body is how a "
                                               "second projection would arrive unnoticed. Not a "
                                               "harness test — it starts a browser; "
                                               "`make design-check` runs it.",
                                       "governed_by": ["D16", "D61", "D63", "D66", "D69"]},
            "tests/pricing-markdown.spec.ts": {"does": "`#/pricing` AS A LENS OVER LIVE "
                                               "TCGPLAYER LISTINGS (D103), in its own file so "
                                               "that `tests/pricing.spec.ts` could stay "
                                               "UNEDITED through every commit of that work — "
                                               "which is the only thing that proves the second "
                                               "source cost the run path nothing. The strongest "
                                               "cases are absences: no quantity cell and no "
                                               "thumbnail EXIST in the DOM, and the write press "
                                               "does not exist until a check has answered. It "
                                               "also pins what the press SENDS — `edits` "
                                               "carrying only the rows a hand priced, no "
                                               "`worklist`, and the corpus revision — because "
                                               "on this path that is the file that moves money "
                                               "at a marketplace, and it pins that the trends "
                                               "press is scoped to the filter rather than to "
                                               "the whole survey (D62). Not a harness test.",
                                               "governed_by": ["D62", "D100", "D103"]},
            "tests/pricing.spec.ts": {"does": "the pricing screen, asserted where nothing else "
                                              "can see it. Its strongest cases are ABSENCES: a "
                                              "suggested row writes no key to the corpus, a "
                                              "Tab across one writes nothing, a snap onto a blank "
                                              "column writes nothing and says so, and the screen "
                                              "draws no solid accent fill at all. Since D85 it also "
                                              "HIT-TESTS the bottom-left corner — every point of "
                                              "the ship bar and of an open reading, asking which "
                                              "element a hand aiming there actually reaches — "
                                              "which is the one question 56 green cases could not "
                                              "ask while the screen was a pile. Not a harness "
                                              "test — it starts a browser; `make design-check` "
                                              "runs it. AND THE ROWS ARE CROPPED SINCE "
                                              "2026-09-06, which is what the operator sees and "
                                              "not what this file used to measure: "
                                              "`Pricing.tsx:pumpCrops` POSTs "
                                              "`/pipeline/crop-preview` once per row it draws, "
                                              "nothing here stubbed it, so every case sent that "
                                              "POST to the capture port and took the `catch` — "
                                              "seventy-one cases measuring the uncropped "
                                              "fallback. Named by `app/tests/shell.ts`'s seal; "
                                              "all seventy-one pass against the cropped render.",
                                      "governed_by": ["D8", "D9", "D20", "D28", "D33", "D48", "D49", "D51", "D54", "D56", "D57", "D58", "D59", "D62", "D68", "D78", "D79", "D85", "D86", "D98", "D99"]},
            "tests/live-reconcile.spec.ts": {
                "does": "the store-wide reconcile in a browser (D87): that it is reachable from "
                        "#/runs at all, that the preview asks for no write, and that the settle "
                        "control does not EXIST until the preview has answered — absent rather "
                        "than disabled, D33's shape applied to the press that settles the "
                        "ledger. The route is intercepted and its body read; no real request is "
                        "made and no store is touched.",
                "governed_by": ["D7", "D33", "D87"]},
            "tests/markdown.spec.ts": {
                "does": "the stale-listing markdown in a browser (D100): that a person can open "
                        "it from the Runs header at all, that it traps focus and Escape hands it "
                        "back once nothing is in flight, "
                        "back, that BOTH previews ask for no write, and that none of the three "
                        "presses EXISTS before the read before it has answered — absent rather "
                        "than disabled, D33's shape applied twice on one screen. Two routes are "
                        "intercepted and their bodies read; no real request is made and no store "
                        "is touched.",
                "governed_by": ["D7", "D9", "D33", "D64", "D86", "D100", "D103", "D104", "D105"],
                "note": "ONE OF ITS CASES IS A GEOMETRY ASSERTION AND IT WAS WRITTEN FROM A "
                        "DEFECT. The survey console rendered 512px wide and 0px TALL — "
                        "`.runslog` sets `overflow: hidden`, which makes a flex item's automatic "
                        "minimum size zero, so the sheet's scrolling column squeezed it flat "
                        "with every line of stdout still in the DOM. Content, class and "
                        "`white-space: pre` all asserted true against it. Nothing that reads "
                        "text could have caught it, which is the whole argument for measuring a "
                        "box here rather than trusting one.",
            },
            "tests/run-panel.spec.ts": {
                "does": "the pipeline panel in a browser: that all four commands are reachable "
                        "from #/inventory at all, and that the money gate holds. The strongest "
                        "assertion in it is NEGATIVE — before the free preflight has answered, "
                        "the control that spends does not EXIST, absent rather than disabled. "
                        "The spend route is intercepted and its body read; no real request is "
                        "ever made, which matters more here than on any other screen because "
                        "one of these routes costs money. D64's fetch is covered the same "
                        "way and for the same reason: the case that matters is the ABSENCE of "
                        "the acknowledging control for a refusal an operator cannot answer.",
                # D1 is the two-phase split the four steps make visible; D3 is the ladder the
                # join walks; D9 is the pricing answer that gates emit;
                # D31 is why this is a panel on #/inventory rather than a seventh route.
                "governed_by": ["D1", "D3", "D9", "D13", "D20", "D31", "D32", "D33", "D39", "D48", "D54", "D56", "D64", "D65", "D49", "D76"],
                "note": "THE PIPELINE WAS THE LARGEST INSTANCE OF THE ROUTE-IS-NOT-A-FEATURE "
                        "FAILURE AND NOBODY HAD COUNTED IT. The four commands have existed "
                        "since step 4 and have been through a 53-card run and a 544-card run; "
                        "until 2026-08-24 they could be reached only by typing at a terminal, "
                        "which docs/GATES.md names as what Gate B did not close. Like its "
                        "siblings it is not a harness test and must not become one: it starts "
                        "a browser, and make design-check is what runs it.",
            },
            "tests/inventory.spec.ts": {
                "does": "the owner's inventory screen in a browser: the unified box walk, the "
                        "folding sections, mass-select, and the FOUR WRITES — box-wide claims, "
                        "per-card claims, the mid-box delete and the whole-box delete — "
                        "asserted at the request boundary against a stubbed server, so a "
                        "control that draws but sends the wrong body fails here. It also carries "
                        "this file's FIRST geometry assertions (D38): that the photograph is flush "
                        "with the fact rows beside it, and that the box and the runs are a column "
                        "beside the card rather than a row beneath it. Nothing on the commit path "
                        "can see either. TWO MORE MEASUREMENTS since 2026-08-29: that a walk-to "
                        "moves the page by nothing at all (D45's jump was scrolling the document "
                        "to the end of its range and taking the top bars with it), and that the "
                        "Market row draws its price with the age of the join that read it, by "
                        "POSITION rather than by `card.sku` — the fixture's priced card carries "
                        "no SKU on its record, which is the case a SKU-keyed lookup loses (D7, "
                        "D8, D9, D49). AND THE SALE ITSELF, FROM 2026-08-30 (D57) — this file "
                        "asserted that `Mark sold` was VISIBLE and never pressed it, so the "
                        "whole write, its receipt, its undo window and the `already_sold` path "
                        "were unasserted while the control changed what one press does to a "
                        "real card. Six cases now cover it, three of them mutation-tested. AND "
                        "THE BOX OPERATIONS ARE A ROSTER SINCE 2026-09-01, not a count: "
                        "`toHaveCount(4)` went red on main when D83's Move to box made it five, "
                        "which a bare number reports without naming and which it cannot see at "
                        "all when one control silently replaces another. The sweep pins the "
                        "labels in draw order, so the row it holds to the no-border rule is a "
                        "row it can name. THE MOVE'S OWN WRITE IS STILL UNASSERTED HERE — the "
                        "FOUR WRITES above are the four this file sends; D83 shipped its "
                        "control with no file under app/tests/ touched. AND THE SHELL'S OWN "
                        "TWO READS ARE STUBBED SINCE 2026-09-05, which they had never been: "
                        "`/status` and `/orders` belong to no screen, so a file that stubs "
                        "everything its own screen asks for missed both and sent them to "
                        "whatever answers this checkout's capture port — the owner's real "
                        "store in the main tree, nothing at all in a worktree, and in that "
                        "second case the shell's 44px offline banner on top of the view. That "
                        "banner is what failed the 150px first-content floor and the walk-to's "
                        "in-viewport row; `open` asserts now that it is absent and that no "
                        "route boundary is showing its crash page, so the next omission fails "
                        "by name rather than as a pixel count. AND THE PRODUCT ROW HAS TWO "
                        "CASES FROM THE SAME DAY (D101): the claim reached this editor with no "
                        "browser case over it, and the `GET /games` fixture omitted `products` "
                        "and `product_game` outright — `undefined.find` inside `ClaimEditor`, "
                        "the screen behind its error boundary, and six cases here spending "
                        "thirty seconds each on a switch that had been detached. AND THE HASH'S OWN BOX SINCE 2026-09-05: `#/inventory?box=<n>` was honoured only for a box that already had ROWS, because the shelf list is built from the rows first and the registry second and the ref was consumed on the first list — so every box of code cards, which D24 pools and which therefore has none, was unreachable by the one link that aims at one. Two cases, with `GET /boxes` held back so the ordering is the defect's rather than a race.",
                "governed_by": ["D5", "D7", "D8", "D9", "D10", "D13", "D20", "D22", "D23", "D24", "D26", "D28", "D30", "D31", "D33", "D34", "D37", "D38", "D40", "D41", "D43", "D45", "D49", "D55", "D57", "D58", "D63", "D67", "D68", "D71", "D83", "D89", "D92", "D101"],
                "note": "THE CHECK `CLAUDE.md`'s ROUTE-IS-NOT-A-FEATURE RULE SAYS DOES NOT "
                        "EXIST. That rule was written on 2026-08-23 after three routes shipped "
                        "with full T7 coverage and no client function and no control — green "
                        "harness, green docs-audit, unusable product. T7 proves the server "
                        "honours a request; this proves a human pressing a control produces "
                        "that request. Neither can see the other's half. Like its siblings it "
                        "is NOT a harness test: it starts a browser, so it runs under "
                        "`make design-check` and is deliberately off the commit path.",
            },
            # THE SCREEN docs/DESIGN.md SPECIFIES HARDEST WAS THE ONE WITH NO BROWSER
            # COVERAGE, until 2026-08-24. `grep -rn '#/review' app/tests/` returned nothing:
            # the Fulfiller's view had its nine-row table, the inventory screen had its
            # reachability battery, step 6's button had its own sheet, and the screen the
            # owner spends the most hours in had prose. This file is the split's own
            # instrument — it asserts the numbers that justified reversing a rule
            # docs/DESIGN.md had stated by name, so a later session that re-stacks the
            # screen fails these before anyone has to remember why it was split.
            "tests/review.spec.ts": {
                "does": "the review queue's geometry and its two guarantees: the photograph "
                        "at >=23% of the viewport with a >=700px long edge, zero page scroll "
                        "for one card, every candidate row on screen beside the photo, D28's "
                        "frame not moving between cards, the 1:1 loupe — HIDDEN AT REST, "
                        "aimed by the pointer, painting native pixels rather than a second "
                        "downscale, and leaving nothing behind when the pointer does (the "
                        "four cases were rewritten 2026-08-25 when the loupe stopped being a "
                        "fixed centred inset; the old ones asserted `50% 50%` and an element "
                        "on screen at rest, both wrong by design now) — an answer that stays reversible past "
                        "the twenty seconds the old clock allowed, the single column below "
                        "900px, and D24's pooled card drawing no photograph here. Run by "
                        "`make design-check`. EVERY ROUTE IS STUBBED AND NO WRITE IS EVER "
                        "ISSUED — true as of 2026-09-05 and not before. That sentence stood "
                        "here while `/status` went unstubbed to the capture port, and the "
                        "shell's 44px offline banner is what ran the document 88px past a "
                        "900px viewport and failed `answering a card costs no scrolling` — "
                        "twice its own height, because `.bn-view` is `min-height: 100%` of a "
                        "`.bn-shell-main` the banner has already made taller. The case's own "
                        "comment attributes that 88 to the font swap and `settleFonts` was "
                        "added for it; that call fixed a different real red and not this one. "
                        "`open` asserts the banner is absent now, so the claim has a reader.",
                # D32 and D35 arrived with the rewritten loupe cases: the aim-is-never-a-
                # constant case argues from D32's measured 39-81% card fill, and the reason the
                # old fixed centre was wrong is that it magnified the Pokedex strip — D35's
                # misread-as-collector-number string exactly.
                "governed_by": ["D4", "D13", "D24", "D28", "D29", "D32", "D35", "D16", "D41", "D37", "D46", "D77"],
                "note": "NOT a harness test — it starts a browser, which docs/GATES.md keeps "
                        "off the seven-test contract deliberately. The photograph stub is "
                        "2160x3840 and that is load-bearing: the rig's stored frame is 9:16 "
                        "(D13), and a square stand-in would make every area assertion a "
                        "confident lie about a shape the screen never sees. Writing it found "
                        "a defect it was not looking for — app/src/App.css's nav strip did "
                        "not wrap, so five route names scrolled every owner screen sideways "
                        "to 557px on a 375px viewport.",
            },
            "tests/fulfillment.spec.ts": {
                "does": "all nine rows of the Fulfillment constraints table against the "
                        "rendered view, with every contrast ratio computed from the colors "
                        "the page actually painted rather than from a number published in "
                        "docs/DESIGN.md. Run by `make design-check`.",
                "governed_by": ["D5", "D10", "D13", "D24", "D31", "D41"],
                "note": "NOT a harness test, same as its sibling above. It failed 16 of the 30 "
                        "assertions `make design-check` runs for the few hours between the view "
                        "being built and being routed — all of them because every test asserts "
                        "the view is on screen before measuring anything, and none of them a "
                        "design defect. Worth keeping: that is the spec working, and the "
                        "alternative it was written against is nine confident measurements of "
                        "whatever Vite serves for an unknown hash. Green since the routing "
                        "landed 2026-08-13.",
            },
        },
    },
    # ------------------------------------------------------------- nothing planned below
    #
    # Step 9 (vendored catalog) has no entry on purpose: its directory name is not decided
    # yet, and inventing one costs the self-cleaning rule. A `planned` entry only earns its
    # keep when the path is right — a wrong path audits clean forever and never fires the
    # day the real directory arrives. `server/` was one entry that qualified, because the
    # Makefile already named the file it would hold; it graduated to `built` with step 5,
    # and `app/` above arrived the same way with step 6. Add step 9's when the build order
    # reaches it and the name is real.
]

# ------------------------------------------------------------------------------- tracks
#
# Two tracks share one rig (D14). Each names the decisions file and the rules file that
# govern it, and `owns` is the path prefix that decides which — `scripts/decision-context.py`
# reads it to answer a `codes/` edit with C decisions instead of silently finding none.
#
# THIS SECTION HAD NO READER FROM 2026-08-07 TO 2026-08-31 and went wrong twice while
# nothing could tell: it said `C1-C7` after the file had reached C11, and it said the codes
# track's delivery automation was "gated on singles Gate B" long after Gate B passed
# (2026-08-22) and the gating system was retired outright (2026-08-23). Both wrong for over
# a week, in the file whose whole argument is that it is audited as hard as it is trusted.
# It has a reader and a check now — see the docstring at the top of this file.

TRACKS = [
    {"name": "singles", "owns": "", "decisions": "docs/DECISIONS.md", "rules": "CLAUDE.md",
     "status": "current",
     "note": "the default track: every path this map covers except the codes ones below."},
    {"name": "codes", "owns": "codes/", "decisions": "docs/CODES-DECISIONS.md",
     "rules": "code-card-fork/CLAUDE.md", "status": "shakedown",
     "note": "C1-C11. The decode path, the ledger and the product claim are BUILT, and D70 "
             "gave the track a screen of its own at #/codes on 2026-08-30 — so 'shakedown' "
             "no longer means unbuilt, it means unproven: docs/specs/code-cards.md section 8 "
             "records that NO REAL CODE CARD HAS EVER BEEN THROUGH THIS PIPELINE, and every "
             "measurement in the track is synthetic. The channel decision is RECORDED and "
             "NOT executed — six venue families were researched and every one came back "
             "marginal — which is what the track is actually waiting on. It is NOT waiting "
             "on a gate: this row said 'gated on singles Gate B' until 2026-08-31, and that "
             "gate passed 2026-08-22 with the gating system retired the day after."},
]
