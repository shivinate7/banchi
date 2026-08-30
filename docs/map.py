"""The repo, as data. One Read answers "what is built, what is TBD, what governs this file".

Written because that question kept costing a subagent sweep and a quarter-million tokens to
re-derive from prose that already knew the answer. `docs/GATES.md` has the build order,
`docs/DECISIONS.md` has the rulings, `README.md` has the layout — but all three are prose,
and prose has to be read in full before it can be trusted.

Read by three consumers, which is the reason it is data and not another markdown section:

  scripts/docs-audit.py       its repo-map check verifies every claim below against the tree
  scripts/decision-context.py the PreToolUse hook that tells you which decisions govern a
                              file before you edit it
  you, or an agent            a single Read instead of a search

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

# --------------------------------------------------------------------------- build order
#
# Mirrors the numbered list in docs/GATES.md. status: done | next | blocked
#
# `next` means unblocked and NOT STARTED. There is deliberately no "in progress": the
# earlier draft called step 5 `current`, which read as work underway when step 4 had just
# landed and step 5 had not been touched. Exactly one step is `next`, and the repo-map
# check enforces that — two of them is the drift this vocabulary exists to prevent.
#
# A step whose scope was split part-way through keeps `next` until every part is built, and
# its `note` carries what shipped and what did not. That is the whole handling: no fourth
# status, because a fourth status is what this vocabulary refuses, and a `note` nobody can
# misread costs nothing. Precedent is step 6, which held `next` with its tokens locked and
# its component unbuilt and said exactly that in the note; step 7 is the same shape at a
# larger size, and its note argues the case rather than leaving the reader to infer it.
#
# `blocked_by` names the step or gate that unblocks it, never a date.

BUILD_ORDER = [
    {"step": 1, "title": "Repo init, fixtures committed, git from commit zero", "status": "done"},
    {"step": 2, "title": "Scaffolding: Makefile, hooks, screenshot script, failing harness", "status": "done"},
    {"step": 3, "title": "Verification harness T1-T4", "status": "done"},
    {"step": 4, "title": "Batch script v2: Batch API, variant ladder, catalog join", "status": "done",
     "note": "code done 2026-08-03, harness green T1-T6. Never run against a real card — that is Gate B."},
    {"step": 5, "title": "Capture server: POST /capture, sidecars, /status, photo service, inventory state", "status": "done",
     "note": "code done 2026-08-11, spec at docs/specs/capture-server.md. Shipped with no harness "
             "coverage; T7 closed that 2026-08-13 — every route, every named refusal, and the "
             "sidecar seam. What it still does not reach is in docs/DEBTS.md."},
    {"step": 6, "title": "Design tokens locked, one component built against them", "status": "done",
     "note": "tokens locked 2026-08-12 by interview; the pull-confirm built against them 2026-08-12 "
             "at app/src/PullConfirm.tsx, rendered by `make screenshot` and asserted by "
             "`make design-check`. Building it caught two places where docs/design-refs/locked.html "
             "disagrees with docs/DESIGN.md — see that directory's README."},
    {"step": 7, "title": "Vite capture app: device picker, capture, inventory, review queue, Fulfillment view", "status": "done",
     "note": "BOTH HALVES BUILT 2026-08-13 on branch step-7-capture-app. 7a is "
             "docs/specs/capture-app.md's scope — the shell and its three routes, the capture "
             "screen, undo, the pull preview, the trigger seam, the eslint rules, and "
             "DELETE /inventory/<box>/<index>. 7b is the review queue, the Fulfillment view, "
             "the inventory SKU view and mark-sold, plus three more server routes "
             "(GET /queues, POST /review/<box>/<index>/answer, POST /inventory/<box>/<index>/sold). "
             "7b WAS BUILT BEFORE GATE B, WHICH ITS OWN SPEC FORBIDS, at the owner's explicit "
             "instruction; that spec's STATUS section carries what it costs and its sections 0 "
             "and 9 are left standing and marked overtaken. That short form USED to be that "
             "7b's screens display data no run has ever produced; Gate B ran them 2026-08-22 "
             "and it is no longer true. The review queue held 16 real entries and the owner "
             "answered every one. What survives of it is narrower and still real: all 16 "
             "carried ONE reason code of twelve, and the whole run priced $0.04-$0.40, so the "
             "price-driven row hierarchy has still never seen the mixed-value list it sorts "
             "for. "
             "THIS ROW IS `done` AND STEP 8 IS `next`, which the previous note called the "
             "owner's call to make on the day rather than by editing this file. It is made "
             "now because nothing is left to build: with 7b shipped there is no remaining "
             "step-7 scope for `next` to point at, and `make status` sending whoever runs it "
             "to a physical twenty-card run against a build that has never met a card is now "
             "an accurate instruction rather than a premature one. "
             "WIRED 2026-08-13, in a pass after the build: all three screens are registered in "
             "app/src/App.tsx's ROUTES table, app/src/server.ts carries a client function per "
             "new route, and the shell draws no nav over the Fulfillment view. `make "
             "design-check` went from 16 failures to 30 of 30 passing on that change alone — "
             "every one of those failures was the unregistered route, exactly as the spec was "
             "written to report. See the app/ entry below."},
    {"step": 8, "title": "Gate B smoke test, 20 cards end to end", "status": "done",
     "note": "PASSED 2026-08-22, and over-delivered: 53 real ME01 cards through the feeder, "
             "53/53 identified once the frames were stored upright, joined, emitted, staged on "
             "TCGplayer through two clean reconcile round trips, and the pull preview showed "
             "the right photo at the right physical location. Six defects were found by the run "
             "and fixed the same day — the Batch API custom_id refusal, "
             "the capture canvas leak, the idle-scheduled JPEG encoder, the cross-queue "
             "release leak, review answers that nothing consumed, and the post-import re-emit "
             "double-count. THREE OF THE SIX CARRY A REGRESSION TEST, each observed failing "
             "against the old code before the fix was restored: the cross-queue release leak "
             "in T7, and the last two in T3. The other three carry none, and the reason is "
             "structural rather than an oversight — _custom_id lives in cli/cmd_identify.py "
             "and no harness case names it, and the two capture-latency fixes are in app/, "
             "which no harness test reaches at all (this file's app/ entry says so in its own "
             "note). docs/GATES.md's Gate B section carries the run's measurements."},
    {"step": 9, "title": "Vendor the pokemontcg.io catalog: snapshot, SQLite index, image mirror", "status": "next",
     "was_blocked_by": "step 13, which is done as of 2026-08-24 — the sequencing was the "
                       "owner's and never technical, so finishing 13 is what released it",
     "note": "THE GATE DEPENDENCY WAS RETIRED, NOT SATISFIED, and the difference matters to "
             "anyone reading this row later. This step carried `blocked_by: Gate C` from "
             "2026-08-22, when the owner re-sequenced it behind motion capture — not because "
             "anything here conflicts with that work (it touches no app code) but because one "
             "`next` is the rule and he chose which. On 2026-08-23 the owner retired the "
             "gating system outright: A, B and C have all passed, docs/GATES.md is a record of "
             "runs rather than a schedule, and no step may be blocked behind a gate any more "
             "because none is open. So the blocker was removed by the gates ceasing to be a "
             "schedule, NOT by Gate C being cleared out of this step's way. "
             "There is deliberately no Gate D. Nothing waits on this but the doing of it: "
             "snapshot the repo, build the SQLite index (cards join to sets by FILENAME — "
             "printedTotal lives only in sets/en.json and is half the join key), then fill the "
             "image mirror with the Content-Length dry run first. D15."},
    {"step": 10, "title": "Feeder integration (Gate C)", "status": "done",
     "note": "THIS STEP WAS GATE C — its original `blocked_by: Gate C` named the gate that IS "
             "this work, a circularity that was harmless while Gate B was open and stopped "
             "being so when it passed. BUILT 2026-08-22: the motion trigger at app/src/motion.ts "
             "behind trigger.ts's seam, a mode toggle and HUD on the capture screen, and both "
             "a machine spec and a live browser spec in app/tests. "
             "TUNED AND RUN AT THE RIG, which is the half that could not be built and is why "
             "this row is `done` rather than `done except the physical part`: Gate C passed and "
             "docs/GATES.md carries what it measured. docs/specs/motion-trigger.md is the spec."},
    {"step": 11, "title": "pokemontcg.io API key", "status": "done", "note": "done 2026-08-03; step 9 removes the need for it."},
    {"step": 12, "title": "Scale, polish, deferred list", "status": "blocked", "blocked_by": "step 9",
     "note": "ITS BLOCKER WAS `all gates` AND THE GATES ARE RETIRED (2026-08-23), so this row "
             "had to name something real or stop claiming to be blocked. It is genuinely "
             "behind step 9 — the deferred list is scale work, and scale work reads the "
             "vendored catalog — so the blocker is re-pointed at the step rather than deleted. "
             "What this row does NOT do is decide that docs/DECISIONS.md's Deferred list is "
             "open: that list says 'do not build until all gates pass', all gates now have, "
             "and whether that sentence is thereby spent is the owner's ruling to make in that "
             "file rather than a consequence anybody may infer from this one."},
    {"step": 13, "title": "Order flow, boxes, and search", "status": "done",
     "note": "D7's fungible copies, D20's box object with its retroactive capacity, D10's "
             "per-box sections, and the search-and-sell screens. "
             "THIS ROW CARRIED AN `Outstanding` LIST OF FIVE ITEMS THAT WERE ALL ALREADY ON "
             "DISK, and it stayed `next` for a day after there was nothing left in it to "
             "build. Re-derived by grep on 2026-08-24 rather than from the previous note, "
             "which is the same correction docs/GATES.md's own step 13 records making: D26's "
             "retire and re-shoot have routes AND client functions AND controls, D27's "
             "sessionStorage is in CaptureScreen.tsx, D28's answer undo is in server.ts, D29's "
             "group answer has do_review_group_answer and answerReviewGroup, and D30's gap "
             "convention ships as `neighbors` and `section_gaps` on every located card. D31 "
             "then merged #/boxes and #/pull into #/inventory, so the screens this step names "
             "by their old routes are modes of one. "
             "A STALE `next` IS WORSE THAN A STALE `done`, which is why this row is worth a "
             "note rather than a one-word edit: `make status` reads this field to answer "
             "\"do this next\", so a step that is finished and still says `next` sends every "
             "session that asks to re-audit work that is already committed."},
    {"step": 14, "title": "Multi-game: four capture choices plus misc", "status": "done",
     "note": "D21-D25. pipeline/games.py behind four real TCGplayer exports, four audit rows, "
             "per-game dispatch, `game` through all ten capture hops with the picker on the "
             "capture bar, the rarity claim end to end, the repeatable --export with per-game "
             "catalogs and one import file per game (D25), pooled non-located inventory with "
             "both opsec discharges, and per-game finalisation — riftbound_card_v1 and "
             "one_piece_card_v1 exist, are registered and carry parsers. "
             "THE RARITY CLAUSE WAS BUILT, MEASURED, AND SWITCHED OFF because it lost: "
             "holdout 0.9706 -> 0.9559 for $0.17, with high-confidence misses up two. The "
             "claim's other two jobs — the ladder cross-check and the chip narrowing — are "
             "what D23 now rests on. pokemon_card_v1 did not move: 1ef974bf511d, unchanged, "
             "because prompt_fingerprint hashes ONE profile's fields. "
             "WHAT NO AMOUNT OF CODE CLOSES: neither new game has met a card. The store holds "
             "zero Riftbound and zero One Piece records, so every claim about those two "
             "prompts is a claim about a CSV and a schema, not about a photograph."},
    {"step": 15, "title": "The pipeline seam: the four commands, reachable from a screen", "status": "done",
     "note": "D33, built 2026-08-24. THE LARGEST INSTANCE OF CLAUDE.md's "
             "route-is-not-a-feature RULE THIS REPO HAS HAD, and nobody had counted it: the "
             "four commands have existed since step 4 and have been through a 53-card run and "
             "a 544-card run, and until this step they could be reached only by typing at a "
             "terminal — which docs/GATES.md names as what Gate B did not close. "
             "server/pipeline_routes.py is its own module because it is the one part of the "
             "server that can cause money to be spent: ONE route does, it is named for it, it "
             "refuses without an explicit confirm, and it refuses a second run over a capture "
             "directory a live run is already reading. The preflight beside it is free and "
             "creates no run directory at all. Everything else — the reads, and "
             "join/emit/reconcile — is free and re-runnable, which is the property D1 gave "
             "the two-phase split. "
             "THE MONEY STEP SPAWNS DETACHED AND IS NEVER AWAITED, so a run outlives a "
             "restart of the server that started it; the free steps answer inside the request "
             "with their own stdout attached. app/src/RunPanel.tsx draws it UNFOLDED on "
             "#/inventory — sharing one .browse-boxrun row with BoxOps, because the owner "
             "overruled the fold on 2026-08-24 (D33, amended) — and "
             "app/tests/run-panel.spec.ts is the check the hard rule says "
             "does not exist."},

]

# --------------------------------------------------------------------------------- gates

# status: passed | next | blocked. Same vocabulary as BUILD_ORDER, same reason.

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
            "__main__.py": {"does": "parser, COMMANDS dispatch, exit codes", "governed_by": ["D1", "D3", "D9", "D25"], "tested_by": ["T7"]},
            "cmd_identify.py": {"does": "submit, wait, collect, cache. The one that costs money.", "governed_by": ["D1", "D2", "D21", "D23"]},
            "cmd_join.py": {"does": "resolve identifications against the export; --dry-run previews, "
                                    "--bypass trusts the finish claim. SEEDS decisions.json on the "
                                    "first join and never touches its rule again (D49) — the two "
                                    "lines that did ran under the sentence promising your edits "
                                    "were kept.",
                            "governed_by": ["D3", "D7", "D8", "D11", "D16", "D25", "D36", "D49"], "tested_by": ["T4", "T7"]},
            "cmd_emit.py": {"does": "write import CSVs; refuses while a price is unanswered. Prices "
                                    "from decisions.json rather than from the run manifest (D49), "
                                    "and subtracts withheld SKUs BEFORE deciding whether a file is "
                                    "written at all — the writer emits a header before it iterates "
                                    "rows, so a game whose listable SKUs were all held would "
                                    "otherwise leave a header-only import file on disk.",
                            "governed_by": ["D9", "D25", "D49"], "tested_by": ["T7"]},
            "cmd_reconcile.py": {"does": "diff intent against TCGplayer's Export From Staged", "governed_by": ["D7", "D8", "D11"], "tested_by": ["T7"]},
            "resolve.py": {"does": "turning a run's identifications into a join; shared by join and emit", "governed_by": ["D4", "D8", "D10", "D11", "D21", "D23", "D24", "D25", "D26", "D33", "D36"], "tested_by": ["T7"]},
            "runs.py": {"does": "run directories and manifest.json", "governed_by": ["D1", "D25", "D49"], "tested_by": ["T7"]},
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
                         "governed_by": ["D3", "D8", "D11", "D12", "D14", "D16", "D18",
                                         "D21", "D22", "D23", "D24", "D25"],
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
                        "governed_by": ["D2", "D4", "D7", "D9", "D10", "D11", "D16", "D20", "D21", "D23", "D24", "D25", "D29", "D35", "D49"], "tested_by": ["T3"]},
            # Rung 0 (a human's answer) sits above the ladder and is applied by join.py, so
            # T3 is what covers it — T4 owns the four rungs that infer.
            # D22 because FINISHES and CONDITION_BY_FINISH are no longer written here: they
            # are read out of games.py's `pokemon` entry, byte-identically, which is what
            # makes the registry believable before anything else is built on it.
            "variant.py": {"does": "the variant ladder: four rungs that infer, under a rung 0 that does not, "
                                   "over a per-game finish vocabulary and a set-valued rung 1 claim",
                           "governed_by": ["D3", "D12", "D21", "D22", "D23"], "tested_by": ["T3", "T4"]},
            "pricing.py": {"does": "rules, rounding, floor clamp, threshold, no_market_data refusal",
                           "governed_by": ["D8", "D9"], "tested_by": ["T5"]},
            "routing.py": {"does": "which queue a card lands in — batch script v2 section 5.4",
                           "governed_by": ["D3", "D4", "D9", "D29", "D35"], "tested_by": ["T4"]},
            "decisions.py": {"does": "decisions.json — the pricing decision as a file, not a flag, "
                                     "and as of D49 the AUTHORITY for rule and basis rather than "
                                     "a copy of them. `overrides` holds a price OR a `Withheld`: "
                                     "the bare string \"unlisted\" or an object carrying a reason, "
                                     "an optional note and an optional `watch_above` that `join` "
                                     "reports when a refreshed export clears it. Withholds are "
                                     "deliberately absent from `dispositions()` so a held SKU "
                                     "falling out of a later run cannot refuse the whole emit.",
                             # D16 for the drift a second vocabulary would be; D26 and D37 are the
                             # two states `withheld` is deliberately not, and whose reason words it
                             # may not reuse; D39 for the route the watch line surfaces on.
                             "governed_by": ["D9", "D16", "D26", "D37", "D39", "D49"]},
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
            "images.py": {"does": "downscale, encode, hash a photograph for the API", "governed_by": ["D2", "D23"]},
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
            "detect.py": {"does": "card-boundary detection by tone, and by border when tone refuses",
                          "governed_by": ["D1", "D22"], "tested_by": ["T6"]},
            "crop.py": {"does": "cut the crop-retry regions out of a registered card",
                        "governed_by": ["D1", "D22"], "tested_by": ["T6"]},
        },
    },
    {
        "path": "store/",
        "status": "built",
        "does": "the master store: inventory, cache, standing queues",
        "governed_by": ["D4", "D7", "D9", "D10", "D13", "D15"],
        "note": "T7 reaches this package as of 2026-08-13 — the allocator, the lock and "
                "the atomic replace — and as of 2026-08-22 asserts queues.apply_run "
                "outright: check_queue_supersede calls it directly rather than watching it "
                "through a route, which is what earned queues.py its tested_by. cache.py is "
                "still only read through a session there, with nothing asserting its own "
                "behaviour, so it carries no tested_by: an unenforced claim is the defect "
                "docs/DEBTS.md names, not a rounding error.",
        "modules": {
            "master.py": {"does": "inventory.json — cards, positions, SKUs, listing states, and "
                                  "`open_section`, which puts one divider in front of the next "
                                  "card at the index only the store can read (D10)",
                          "governed_by": ["D3", "D7", "D8", "D10", "D11", "D20", "D21", "D23", "D26", "D34"], "tested_by": ["T7"]},
            "queues.py": {"does": "review.json and parked.json — the standing queues, and the "
                                  "cross-queue release a re-routed position needs",
                          "governed_by": ["D4", "D9", "D22", "D26", "D28", "D37"], "tested_by": ["T7"]},
            "cache.py": {"does": "identifications.json — answers already paid for", "governed_by": ["D2", "D21"]},
            "files.py": {"does": "where the store lives, the lock, the atomic replace", "governed_by": ["D13", "D15"], "tested_by": ["T7"]},
            "session.py": {"does": "lock-free read, or locked read-modify-write", "governed_by": ["D13"], "tested_by": ["T7"]},
        },
    },
    {
        "path": "harness/",
        "status": "built",
        "does": "T1-T7. The Stop hook runs it at every turn end; the pre-commit hook does not.",
        "governed_by": ["D2", "D12", "D15"],
        "note": "the contract is docs/GATES.md; every threshold there is a number, not an adjective",
        "modules": {
            "run.py": {"does": "the explicit ordered TESTS registry — no discovery magic", "governed_by": ["D1"]},
            # T7 lives under harness/tests/ like its siblings; the orphan rule does not
            # scan that far, so this list stays the six-plus-one it always was.
        },
    },
    {
        "path": "scripts/",
        "status": "built",
        "does": "the gate machinery and the tools around it: the pre-commit hook, the docs "
                "audit it runs, the opsec guard that is that hook's disabled PreToolUse "
                "twin, D42's two-hook guard over main and the throwaway-repo self-test that "
                "proves it, the Stop hook, the PostToolUse typecheck hook, D17's "
                "decision-context hook, `make status`, the screenshot runner and its "
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
        "source_suffixes": [".py", ".sh", ".txt"],
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
                "governed_by": ["D11", "D14", "D16", "D18", "D44", "D47"],
                "note": "THE ORPHAN RULE CANNOT SEE THIS FILE — it has no suffix to "
                        "declare. Listed, so its absence would be a finding; unprotected, "
                        "so a sibling hook's arrival would not be.",
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
            "docs-audit.py": {
                "does": "D16's layers 1 and 2: every mechanical check, plus the coupling "
                        "question under `--staged`. `--json` is the machine surface "
                        "nothing downstream may parse a render instead of, and "
                        "`--self-test` is what checks the checker. It NEVER writes, and it "
                        "parses with `ast` rather than importing, so it does not run "
                        "project code. Stdlib only — the pre-commit hook runs bare python3 "
                        "with nothing installed.",
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
                "governed_by": ["D2", "D6", "D7", "D9", "D10", "D12", "D16", "D17", "D18", "D22", "D23", "D24", "D49"],
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
                "governed_by": ["D15", "D16", "D23"],
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
                        "path, including its own bugs.",
                # D18 is the one that decides where this may run rather than what it does.
                # It WRITES — a venv and a cache copy — so it belongs at session start and
                # must never be moved onto the commit path or into `make check`. D16 is
                # cited for the sibling rule it sets over guard-opsec.sh and inherits here:
                # a hook that can break a session gets disabled, and a disabled hook guards
                # nothing, so every failure exits 0.
                "governed_by": ["D16", "D18", "D43", "D47"],
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
                "governed_by": ["D2", "D3", "D17"],
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
                "governed_by": ["D16", "D17", "D42", "D43", "D44"],
                "note": "IT READS `--json`, NOT THE RENDER, since 2026-08-13. This line "
                        "said the opposite until integration: the debt was closed and this "
                        "entry rewritten in the same run by different hands, and nothing "
                        "mechanical could have caught the disagreement — a `note` is prose "
                        "and the orphan rule only proves the entry exists. The auditor is "
                        "in SOURCES for the same reason: it is a subprocess rather than a "
                        "read, which is exactly why its path sat hardcoded and uncovered "
                        "while every other path here was audited.",
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
                # D5 is what the list is for: five owner screens and the Fulfiller's, which
                # is the one render where the absence of the nav strip is the point. D13 is
                # why the hash route in each URL is load-bearing rather than decoration —
                # drop it and a render is named after one view and shows another. D39 added
                # the `runs` line on 2026-08-29 — the pipeline's own route, and the one owner
                # render that draws no stored capture photo, so the `views exposure` question
                # the others raise does not arise for it.
                "governed_by": ["D5", "D13", "D31", "D39", "D49"],
            },
        },
    },
    {
        "path": "fixtures/",
        "status": "built",
        "does": "real TCGplayer exports for three product lines — Pokemon (SV09), Riftbound "
                "and One Piece — plus the import file TCGplayer accepted verbatim. Ground "
                "truth. Never modified, enforced by pre-commit.",
        "governed_by": ["D11", "D22", "D25"],
        "tested_by": ["T2"],
        "note": "The Riftbound and One Piece exports arrived 2026-08-23 and settled the "
                "highest-risk assumption in D22: TCGplayer does carry both as Product Line "
                "values, on the identical 16-column header. They also refuted three guesses "
                "the registry had been written around — see D22. No per-file entries here "
                "because this component declares no source_suffixes, so the orphan rule does "
                "not scan it; the audit's game rows read the directory instead.",
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
                        "mark-sold, undo, search and box routes — including D34's listing "
                        "release and the free plan that must be drawn before it, D37's "
                        "stand-down in both directions, D20's box name as an address "
                        "(`name_taken`, and a number allocated rather than typed), and D10's "
                        "one-divider-at-a-time `POST /boxes/<box>/sections`, which takes no "
                        "index because the store reads `next_index` inside its own lock; "
                        "the sidecar identify reads "
                        "back; the photo store; the origin allowlist that stands between a "
                        "stray browser tab and a hard delete; "
                        "and SERVER_EVENTS, appended "
                        "to history.jsonl through _history inside the route's own "
                        "Store.write(), so the line and the change it describes commit "
                        "together or neither does. NOT ONE OF THEM is a member of "
                        "master.STATES, which is what keeps _state_before_sale from "
                        "restoring a reversed sale to one of them.",
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
                "governed_by": ["D1", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11", "D12", "D13", "D16", "D20", "D21", "D22", "D23", "D24", "D26", "D28", "D29", "D30", "D33", "D34", "D37", "D43", "D46", "D49"],
                "tested_by": ["T7"],
            },
            "pipeline_routes.py": {
                "does": "the pipeline seam: POST /pipeline/preflight (free, creates no run), "
                        "POST /pipeline/identify (THE ONE THAT SPENDS — spawns a detached "
                        "child and returns the run name), GET /pipeline/runs and "
                        "/pipeline/runs/<name> (read the run directory, hold nothing), "
                        "GET .../file (the import CSVs and the report, matched by shape and "
                        "then by membership), POST .../<join|emit|reconcile> (free, run "
                        "inside the request, stdout returned verbatim) and PUT "
                        ".../decisions (D9's sub-threshold answer, which gates emit alone). "
                        "Its own module because it is the one part of this server that can "
                        "cost money: everything in capture_server.py still holds no key, "
                        "opens no socket and starts no child. A SEND IS A CART OF BOXES "
                        "(D48): both money routes take `scopes: [{box, indices?, crop?, "
                        "max_edge?}]`, a bare `box` reads as a cart of one, the response is "
                        "always a list, the total is summed here rather than on the screen, "
                        "and identify spawns one detached child PER BOX — so a run is still "
                        "one box and nothing downstream learns a new shape.",
                # D1 is the two-phase split, which is why join/emit/reconcile can answer in
                # the request and identify cannot. D9 is the decisions gate. D13 is one truth
                # on one Mac, which is what a detached child outliving this process rests on.
                # D32 is why --force-resubmit is deliberately not offered to a screen.
                "governed_by": ["D1", "D2", "D3", "D9", "D13", "D16", "D21", "D25", "D29", "D32", "D48"],
                "tested_by": ["T7"],
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
        "step": 10,
        "does": "the web app. SEVEN routes behind a hand-written hash router, six of them the "
                "owner's — the capture screen that Gate B runs on, the runs screen the "
                "pipeline lives on, the review queue, the pricing worklist, the one "
                "inventory view (D31 folded the box walk and the pull preview into it) and "
                "step 6's component gallery — and one "
                "the Fulfiller's, which the shell deliberately draws no nav over. Two "
                "Playwright specs assert docs/DESIGN.md's Fulfillment floors, one against step "
                "6's component and one against the Fulfillment view.",
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
                "can be opened, and the one check that can is not on it.",
        "modules": {
            # ---- the page, and what builds and runs it ----
            "index.html": {"does": "the single page: the #root main.tsx mounts into, and the "
                                   "three font faces from their two hosts",
                           "governed_by": ["D5", "D13"]},
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
                                             "per-checkout",
                                     "governed_by": ["D5"]},

            # ---- the ground: what everything else reads ----
            "src/tokens.css": {"does": "the locked tokens as CSS custom properties. Tokens and nothing else.",
                               "governed_by": ["D18"]},
            "src/base.css": {"does": "reset and the page ground. Light only — there is no dark theme.",
                             "governed_by": ["D5"]},

            # ---- the shell ----
            "src/main.tsx": {"does": "mounts App, and fixes the stylesheet order: tokens before base",
                             "governed_by": ["D13"]},
            # D16 governs a UI file here for one reason worth keeping: App.tsx drives its nav
            # and its render off a single ROUTES table rather than a table plus a switch, and
            # cites D16 for why two lists of the same strings are the drift to avoid.
            "src/App.tsx": {"does": "the shell: SEVEN hash routes — five after D31 merged #/boxes "
                                    "and #/pull into #/inventory, plus #/runs, which D39 gave the "
                                    "pipeline on 2026-08-29 between Capture and the review queue, "
                                    "and #/pricing, which D49 gave hand-pricing on 2026-08-30 "
                                    "AFTER the review queue — answering the queue changes what "
                                    "the next join resolves, so pricing before it prices a set "
                                    "that is about to move. `#/runs`'s chord is `r` and the review "
                                    "queue moved to `q`; `#/pricing` took `p`, which D31 retired "
                                    "with `#/pull` and this file's own comment said was never "
                                    "reassigned — amended there in the same commit. "
                                    "One ROUTES table driving both "
                                    "the nav and the render, and the persona field that decides "
                                    "the Fulfiller's view gets no chrome at all. #/boxes WAS "
                                    "the seventh, registered with D20's screen rather than after "
                                    "it; D31 deleted the route and kept the screen — the "
                                    "registration rule stands, the route does not. TWO KEYBOARDS "
                                    "SINCE 2026-08-30: the `,` chord JUMPS to a route by name, "
                                    "and D50's Cmd-arrow STEPS along the strip in the order the "
                                    "nav draws it — the ring derived from `hotkey` and "
                                    "GROUP_ORDER rather than listed twice, never wrapping, and "
                                    "the one place this shell takes a modifier.",
                            "governed_by": ["D5", "D10", "D13", "D16", "D20", "D31", "D33", "D39", "D49", "D50"]},
            "src/App.css": {"does": "the shell's chrome: a 1px hairline under the nav, no tint, no "
                                    "shadow, why this nav may never render on the "
                                    "Fulfillment view, and the two chip looks — the chord's, "
                                    "which lights up when the leader is armed, and D50's step, "
                                    "which deliberately does not wear that class because it is "
                                    "never armed",
                            "governed_by": ["D5", "D10", "D13", "D49", "D50"]},

            # ---- the wire, and the two seams ----
            "src/server.ts": {"does": "the only module that talks to the capture server, so the "
                                      "stop-the-run failure rule is one decision. Surfaces the "
                                      "server's own messages verbatim, and holds the two "
                                      "readers every screen shares: a thrown thing as an "
                                      "owner-side screen draws it, and the position label as "
                                      "the server rendered it.",
                              "governed_by": ["D3", "D4", "D5", "D6", "D7", "D10", "D13", "D21", "D23", "D26", "D28", "D29", "D30", "D32", "D33", "D34", "D37", "D43", "D46", "D48"]},
            "src/types.ts": {"does": "the shapes the server speaks, in the server's own field "
                                     "names — captures, inventory, boxes, listings and the "
                                     "standing queues. Types only, it emits no JavaScript.",
                             "governed_by": ["D3", "D4", "D6", "D7", "D8", "D9", "D10", "D11", "D16", "D20", "D21", "D22", "D23", "D24", "D26", "D28", "D29", "D30", "D32", "D33", "D34", "D37", "D46", "D48", "D49"]},
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
                                     "(t, d, luma) plus the watch-region pixels at each gate "
                                     "verdict and once a second, and downloads the armed "
                                     "session as one self-describing JSON from the HUD. The "
                                     "trigger records nothing itself — this hangs off "
                                     "motion.ts's optional onFrame callback. Built 2026-08-22 "
                                     "when the rig session asked for speed data, the exact "
                                     "condition D19 reserved it for.",
                             "governed_by": ["D19"]},
            "src/motion.ts": {"does": "Gate C's auto-capture: a pure MotionMachine (settle, "
                                      "novelty, card-present luma, deferring refractory) under "
                                      "a thin DOM sampler that feeds it one 64x36 luma grid per "
                                      "decoded frame. Parameters derived from Gate B's measured "
                                      "cadence and SNR — see docs/specs/motion-trigger.md. "
                                      "BUILT 2026-08-22 and TUNED AT THE RIG 2026-08-23 off "
                                      "the first 86-cycle feeder trace (tLo 3.0 -> 4.5, tHi 6.0 "
                                      "-> 8.0, recovering 14 silently-missed cards), then "
                                      "confirmed live at 85/85 on box 95. The trigger half of "
                                      "Gate C is confirmed; the pipeline half is not.",
                              "governed_by": ["D13", "D19"]},

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
            "governed_by": ["D3", "D10", "D13", "D19", "D20", "D21", "D22", "D23", "D27", "D41"]},
            # D3 earns its place on a stylesheet: the no-claim finish chip is drawn dashed
            # because rung 1 distinguishes "no metadata recorded" from a recorded claim, and
            # that distinction is carried here in a border style rather than in any logic.
            "src/CaptureScreen.css": {"does": "its layout, at the dense end of docs/DESIGN.md's one "
                                              "system, two densities. Owner-side; the Fulfillment "
                                              "floors do not govern here.",
                                      "governed_by": ["D3", "D5", "D27", "D41"]},
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
                        "the firewall is the component graph, not a selector.",
                "governed_by": ["D10", "D20", "D24", "D30", "D31", "D41"]},
            "src/PositionLabel.css": {
                "does": "the shape, and one knob per site. `--pos-slot` is the only number a site "
                        "chooses; the key is a single clamp and the gap is a token by rule "
                        "(--s5 at a figure >= 40px, --s3 below) so it never lands off "
                        "docs/DESIGN.md's spacing scale. Every selector is `.position-*` and those "
                        "classes exist only where the component rendered them.",
                "governed_by": ["D31", "D41"]},
            "src/BoxBrowse.tsx": {"does": "the box walk, D31's default way into #/inventory — was #/pull until the "
                    "three routes merged. The card's own capture photo beside its position label "
                    "and, since D30, "
                    "its neighbours and the section's gap count. ONE WRITE since 2026-08-23 "
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
                    "the landing's section itself so the scroll has a rendered row to find.",
            "governed_by": ["D6", "D10", "D19", "D20", "D21", "D22", "D23", "D24", "D26", "D27",
                            "D30", "D31", "D33", "D35", "D38", "D39", "D41", "D45"]},
            "src/BoxBrowse.css": {"does": "its layout, and why no accent appears anywhere in it. Its list keeps an "
                                  "INSET focus ring and says so — it clips its own overflow, which is the "
                                  "case base.css's standing ring cannot serve. D38's band lives here: the "
                                  "photograph takes its HEIGHT from the fact rows beside it, through a frame "
                                  "whose only child is out of flow, so the image cannot size the row that "
                                  "sizes it. THAT BAND IS GONE since 2026-08-29: the facts left the card's "
                                  "column to cap the copies, so the photograph is sized by its COLUMN again "
                                  "and there is nothing beside it to take a height from. The body is three "
                                  "columns at 22/33/45, and the run line moved to the header row.",
                                  "governed_by": ["D5", "D6", "D13", "D30", "D31", "D32", "D33", "D38", "D39", "D40", "D41"]},

            # ---- 7b's screens. Built 2026-08-13, BEFORE Gate B; routed the same day ----
            #
            # Every entry in this block describes a file that exists, typechecks, lints clean
            # and opens at a hash. `does` says what the file is for, never that a person has
            # seen it hold a real card — the distinction the whole entry note above is about,
            # and the one a reader skimming `does` lines would otherwise lose.
            "src/ReviewQueue.tsx": {
                "does": "D43's catalog lookup for a card the pipeline offered no rows for — "
                        "suggested on arrival from the card's own read, searchable by name, "
                        "number or SKU, drawn in the rows' own slot and answered on the same "
                        "digits; "
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
                "governed_by": ["D3", "D4", "D5", "D6", "D9", "D10", "D13", "D22", "D23", "D26", "D28", "D29", "D32", "D35", "D37", "D43", "D46"],
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
                "governed_by": ["D5", "D9", "D13", "D28", "D29", "D35", "D37", "D24", "D41", "D46"],
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
                        "the only thing this file tells BoxBrowse to do.",
                "note": "IT WRITES NOW, AND ITS HEADER OVERTURNS ITS OWN OBJECTION IN PLACE "
                        "rather than deleting it. The file argued at length that a sold button "
                        "here would be 'the same irreversible-looking write with neither guard, "
                        "and a second place to perform one action'. Both halves are answered "
                        "where they were made: the guards were never Fulfillment PROPERTIES, "
                        "only asserted there, so this screen brings them — a photo-confirm "
                        "panel showing the copy's own stored photo at its position before "
                        "anything is written (D6), and a per-sale receipt with a twenty-second "
                        "undo, offered only when markSold's `restores_to` says a reversal will "
                        "work. The race is the server's to refuse and it does: `already_sold` "
                        "is drawn as a receipt with no undo, the reading Fulfillment.tsx paid "
                        "for with a data-integrity bug. The live cap it once declined to draw "
                        "comes off the wire now (SearchGroup.cap), which is the condition its "
                        "own comment named as what would settle it.",
                "governed_by": ["D5", "D6", "D7", "D8", "D10", "D13", "D24", "D26", "D27", "D31",
                                "D33", "D39", "D45"],
            },
            "src/Inventory.css": {
                "does": "its layout, at the dense owner-side end of the one system, two "
                        "densities — the search field, the found groups, the receipts, and the "
                        "confirm panel. Accent appears exactly once in it, in that panel, which "
                        "is the one thing on the screen with exactly one thing to do; its "
                        "header used to say no accent appeared at all and records why that "
                        "stopped being true.",
                "governed_by": ["D5", "D6", "D7", "D13", "D26", "D31"],
            },
            "src/BoxOps.tsx": {
                "does": "D20's box object, made visible and editable ON THE BROWSE'S BOX HEADER "
                        "since D31 merged #/boxes away. One header per "
                        "box from GET /boxes: its name, its fill or its frozen capacity, its "
                        "lid, the section layout drawn from the server's own sections_detail "
                        "through PositionBar's spansOf, and per-section counts. Four controls, "
                        "which are the four things D20 says a box has that a person decides — "
                        "register one before a card goes into it, rename it, re-divide it, seal "
                        "or re-open it. Its NUMBER is not among them: that would be a renumber, "
                        "which D10 forbids outright. Two destructive-adjacent controls sit "
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
                "governed_by": ["D5", "D10", "D13", "D20", "D21", "D22", "D26", "D27", "D31", "D33",
                                "D34", "D36", "D38", "D41"],
            },
            "src/BoxOps.css": {
                "does": "the box header, the section track and the editors, at the dense "
                        "owner-side end. No accent anywhere in it and no exception — every box "
                        "carries four controls, so a fill would have to pick one and would then "
                        "mean 'important'. The seal's weight comes from the number on it. NOT A "
                        "PANEL since D38: it is drawn inside the walk's own column, so it carries "
                        "no border of its own, and its sections list is DELETED rather than "
                        "styled — the walk beside it drew the same rows, foldable and tickable, "
                        "while this drew them as inert text.",
                "governed_by": ["D5", "D20", "D22", "D31", "D38", "D40", "D41"],
            },
            "src/Fulfillment.tsx": {
                "does": "D5's second persona's entire product: cards to pull in box-walk "
                        "order, photo-confirm before each pull, one-tap mark-sold with an undo "
                        "window. No machine string and no server message reaches this screen — "
                        "both are correct for the owner and neither is his.",
                "governed_by": ["D5", "D6", "D7", "D10", "D13", "D24", "D26"],
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
            "src/Gallery.tsx": {"does": "every state on one page — what `make screenshot` renders",
                                "governed_by": ["D5"]},
            "src/Gallery.css": {"does": "the gallery sheet's own layout. Not a product screen.",
                                "governed_by": ["D5"]},

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
                                    "governed_by": ["D5", "D10", "D13", "D20", "D24", "D30"]},
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
                                      "governed_by": ["D4", "D5", "D6", "D7", "D10", "D20", "D24", "D26", "D30", "D31", "D38", "D45"]},
            "src/CardLocations.css": {"does": "the group at two densities. The Fulfiller's copy is a "
                                              "card with a photo; the owner's is a row. The walk-to "
                                              "wrapper takes the button chrome back off and shows "
                                              "its affordance on hover and focus only (D45).",
                                      "governed_by": ["D5", "D7", "D31", "D40", "D41", "D45"]},
            # ---- the runs screen (D39, 2026-08-29) ----
            #
            # The pipeline moved off #/inventory onto a route of its own at the owner's
            # instruction. RunPanel.tsx did not change shape for it: these three files are the
            # scope it used to get from the walk, answered where there is no walk.
            "src/Runs.tsx": {"does": "#/runs: the page chrome and the box picker, with RunPanel "
                                     "beneath them. Owns the SCOPE and nothing else — a strip of "
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
                             "governed_by": ["D5", "D10", "D13", "D20", "D27", "D32", "D33", "D38",
                                             "D39"]},
            "src/Runs.css": {"does": "its page chrome, to docs/DESIGN.md's numbers literally: 16px "
                                     "on all four sides, a 20px display title sharing its line "
                                     "with the scope and the controls, a one-line lede, and the "
                                     "box strip as the first real content inside 150px of the top. "
                                     "No fill on the selected chip — the solid accent is reserved "
                                     "for a screen with exactly one thing to do, and this screen's "
                                     "one fill is the spend button inside the panel.",
                             "governed_by": ["D5", "D33", "D38", "D39"]},
            # ---- the pricing screen (D49, 2026-08-30) ----
            #
            # The owner hand-prices and had never been asked what they wanted a listing price
            # to BE — `match` on `market` was the CLI default running by accident through
            # every run. This is where that decision is made, per SKU, with every export cell
            # in front of it.
            "src/Pricing.tsx": {"does": "#/pricing: the hand-pricing worklist. One row per SKU a "
                                        "run matched, sorted market-descending, carrying ALL "
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
                                "governed_by": ["D4", "D5", "D7", "D9", "D22", "D26", "D28", "D33",
                                                "D37", "D39", "D41", "D49", "D35", "D48"]},
            "src/Pricing.css": {"does": "the worklist at owner density. One grid template read by "
                                        "the caption AND every row, so the two cannot drift; a "
                                        "row height invariant across every state, because the "
                                        "note lands in a second grid row every zone but the card "
                                        "leaves empty; right-aligned tabular money, so decimal "
                                        "alignment carries magnitude and no guessed type band "
                                        "does. NO SOLID ACCENT FILL ANYWHERE — every state of "
                                        "this screen is a choice among prices, which is the "
                                        "definition of more than one thing to do.",
                                "governed_by": ["D5", "D9", "D28", "D41", "D49"]},
            "src/holds.ts": {"does": "the withhold vocabulary on this side of the wire — the three "
                                     "reasons, their human labels and their panel keys. Declared "
                                     "ONCE, the way src/reasons.ts declares the review vocabulary, "
                                     "and reconciled against pipeline/decisions.py by "
                                     "scripts/docs-audit.py so the drift is visible rather than "
                                     "hoped against. Letters and not digits, because the digits on "
                                     "that screen are price entry.",
                             "governed_by": ["D16", "D22", "D26", "D37", "D49"]},
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
                                "governed_by": ["D5", "D7", "D13", "D33", "D39"]},
            "src/BoxRuns.css": {"does": "one row, and the rule that it must stay one — the whole "
                                        "argument for the panel leaving this screen was its "
                                        "625-1143px height in a column whose question is 'where "
                                        "is this card'. No fill; the control is drawn at "
                                        "BoxOps' own 32px so the two panels in this screen agree "
                                        "about how tall a control is.",
                                "governed_by": ["D5", "D33", "D39"]},
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
            "src/RunPanel.tsx": {"does": "THE PIPELINE, ON A SCREEN. The four commands of batch "
                                         "script v2, on #/runs since D39 and in #/inventory's "
                                         "content column before it, scoped to the box its picker "
                                         "names or the cards handed over from the walk. A two-step "
                                         "money gate with no typing: Check cost prints the command's "
                                         "own preflight, and only then does the one solid accent fill "
                                         "on the panel appear. Join, emit and reconcile beside it, "
                                         "each marked free and re-runnable; every command's stdout "
                                         "shown verbatim; the import CSVs downloadable, which is the "
                                         "gap docs/GATES.md names as what Gate B did not close. "
                                         "The crop is offered as three named PAIRS with a Custom "
                                         "escape hatch (D32 amended), because the crop and the "
                                         "max edge are one decision and pairing them wrongly "
                                         "costs 26% MORE for asking for less; the estimate is "
                                         "void when either moves.",
                                 # D1 is why one step spawns and three answer in the request. D9 is
                                 # the decisions document this panel edits as text rather than as a
                                 # form. D3 is the finish-claim bypass its join control offers. D31
                                 # is why it WAS a panel on #/inventory rather than a route; D39 is
                                 # the owner overruling that, and this file is unchanged by it — the
                                 # scope arrives as a prop either way. D32 is the crop and the
                                 # max-edge beside it.
                                 "governed_by": ["D1", "D3", "D9", "D13", "D16", "D28", "D31", "D32", "D33", "D39", "D49", "D48"]},
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
                                 "governed_by": ["D28", "D31", "D32", "D33", "D38", "D40", "D48"]},
            "src/reasons.ts": {
                "does": "the review queue's fourteen reason codes and their human labels, in one "
                        "file because TWO screens read them since 2026-08-25 — #/review works "
                        "them in order, and #/inventory's card panel says whether the selected "
                        "card has an open question. Extracted rather than copied, and its "
                        "docstring is the argument: nothing keeps these labels in step with "
                        "pipeline/variant.py and pipeline/routing.py, and the defence is making "
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
            "src/SearchField.css": {"does": "the field at two densities", "governed_by": ["D5"]},
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
                        "buffer cannot zero the diff. Run by `make design-check`.",
                "governed_by": ["D19"],
                "note": "NOT a harness test, same as its siblings. Pure arithmetic — no page, "
                        "no server: the machine takes (nowMs, cells) and that is the whole "
                        "reason it is a class apart from the DOM wrapper.",
            },
            "tests/motion-live.spec.ts": {
                "does": "the DOM half in a real browser against the real capture screen: the "
                        "mode toggle arms the machine, a canvas stream stands in for the Cam "
                        "Link, a settle becomes a fire, and a fire with no box selected is "
                        "COUNTED as dropped rather than silently eaten. Run by "
                        "`make design-check`.",
                "governed_by": ["D5", "D13", "D19"],
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
                "governed_by": ["D3", "D22", "D23", "D27"],
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
                "governed_by": ["D10", "D41"],
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
            "tests/pull-confirm.spec.ts": {
                "does": "three rows of the Fulfillment constraints table against step 6's one "
                        "component: 44px targets, 20px body, 7:1 contrast, 12px apart. Run by "
                        "`make design-check`.",
                "governed_by": ["D5"],
                "note": "NOT a harness test and not registered in harness/run.py:TESTS. The "
                        "harness contract in docs/GATES.md is seven Python tests run at turn "
                        "end; this runs a browser and is invoked on its own.",
            },
            "tests/nav.spec.ts": {
                "does": "the shell's keyboard, and the first test this app has had of the strip "
                        "every screen sits under: D50's Cmd-arrow steps the ring in the order "
                        "the nav draws it, both ends stop, and the three refusals hold — a bare "
                        "arrow belongs to the screens, a held Cmd in a text field belongs to the "
                        "caret, and a screen outside the ring keeps the browser's key. Not a "
                        "harness test; `make design-check` runs it.",
                "governed_by": ["D5", "D31", "D39", "D50"],
                "note": "TWO OF ITS CASES COULD NOT FAIL AND WERE CHANGED, which is the part "
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
            "tests/pricing.spec.ts": {"does": "the pricing screen, asserted where nothing else "
                                              "can see it. Its strongest cases are ABSENCES: a "
                                              "suggested row writes no key to decisions.json, a "
                                              "Tab across one writes nothing, a snap onto a blank "
                                              "column writes nothing and says so, and the screen "
                                              "draws no solid accent fill at all. Not a harness "
                                              "test — it starts a browser; `make design-check` "
                                              "runs it.",
                                      "governed_by": ["D9", "D28", "D33", "D49"]},
            "tests/run-panel.spec.ts": {
                "does": "the pipeline panel in a browser: that all four commands are reachable "
                        "from #/inventory at all, and that the money gate holds. The strongest "
                        "assertion in it is NEGATIVE — before the free preflight has answered, "
                        "the control that spends does not EXIST, absent rather than disabled. "
                        "The spend route is intercepted and its body read; no real request is "
                        "ever made, which matters more here than on any other screen because "
                        "one of these routes costs money.",
                # D1 is the two-phase split the four steps make visible; D3 is the finish-claim
                # bypass the join control offers; D9 is the pricing answer that gates emit;
                # D31 is why this is a panel on #/inventory rather than a seventh route.
                "governed_by": ["D1", "D3", "D9", "D13", "D31", "D32", "D33", "D39", "D48"],
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
                        "can see either.",
                "governed_by": ["D5", "D7", "D10", "D13", "D20", "D22", "D23", "D24", "D26", "D30",
                                "D31", "D33", "D34", "D37", "D38", "D40", "D41"],
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
                        "900px, and D24's pooled card drawing no photograph here. Every route "
                        "is stubbed and no write is ever issued. Run by `make design-check`.",
                # D32 and D35 arrived with the rewritten loupe cases: the aim-is-never-a-
                # constant case argues from D32's measured 39-81% card fill, and the reason the
                # old fixed centre was wrong is that it magnified the Pokedex strip — D35's
                # misread-as-collector-number string exactly.
                "governed_by": ["D4", "D13", "D24", "D28", "D29", "D32", "D35", "D16", "D41", "D37", "D46"],
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
                        "rendered view, with every contrast ratio computed from the colours "
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
# Two tracks share one rig (D14). The codes track has its own decisions file, C1-C7.

TRACKS = [
    {"name": "singles", "decisions": "docs/DECISIONS.md", "rules": "CLAUDE.md", "status": "current"},
    {"name": "codes", "decisions": "docs/CODES-DECISIONS.md", "rules": "code-card-fork/CLAUDE.md",
     "status": "shakedown", "note": "manual eBay sales allowed early; delivery automation gated on singles Gate B"},
]
