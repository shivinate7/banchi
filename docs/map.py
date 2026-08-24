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
    {"step": 9, "title": "Vendor the pokemontcg.io catalog: snapshot, SQLite index, image mirror", "status": "blocked",
     "blocked_by": "step 13 (owner sequencing, not a technical dependency — nothing in step 13 needs the vendored catalog, and no production code reads it yet)",
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
    {"step": 13, "title": "Order flow, boxes, and search", "status": "next",
     "note": "D7's fungible copies, D20's box object with its retroactive capacity, D10's "
             "per-box sections, and the search-and-sell screens. Landed: schema v2 and its "
             "migration, GET /search and the three box routes, PositionBar/CardLocations/"
             "SearchField/useSearch, the owner's search-and-sell and Boxes screens, the "
             "Fulfiller's search, and D28's layout half. Outstanding: D26 removed + re-shoot, "
             "D27 sessionStorage, D28's undo half, D29 group answers, D30 the gap convention."},
    {"step": 14, "title": "Multi-game: four capture choices plus misc", "status": "blocked",
     "blocked_by": "step 13 (owner sequencing, not a technical dependency)",
     "note": "D21-D25. Landed: pipeline/games.py behind three real TCGplayer exports, four "
             "audit rows, per-game dispatch, and `game` through all ten capture hops with the "
             "picker on the capture bar. Outstanding: the rarity claim end to end (the job "
             "that pays — it catches confident-but-wrong reads no threshold fires on), the "
             "multi-export join, pooled non-located inventory with both opsec discharges, the "
             "rarity clause into the prompt behind its own A/B flag, and per-game finalisation."},

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
            "cmd_join.py": {"does": "resolve identifications against the export; --dry-run previews, --bypass trusts the finish claim", "governed_by": ["D3", "D7", "D8", "D11", "D16", "D25"], "tested_by": ["T4", "T7"]},
            "cmd_emit.py": {"does": "write import CSVs; refuses while a price is unanswered", "governed_by": ["D9", "D25"], "tested_by": ["T7"]},
            "cmd_reconcile.py": {"does": "diff intent against TCGplayer's Export From Staged", "governed_by": ["D7", "D8", "D11"], "tested_by": ["T7"]},
            "resolve.py": {"does": "turning a run's identifications into a join; shared by join and emit", "governed_by": ["D4", "D8", "D10", "D11", "D21", "D23", "D24", "D25", "D26"], "tested_by": ["T7"]},
            "runs.py": {"does": "run directories and manifest.json", "governed_by": ["D1", "D25"], "tested_by": ["T7"]},
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
                          "governed_by": ["D11", "D22", "D25"], "tested_by": ["T2"],
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
            "join.py": {"does": "catalog join by SKU, aggregation, bidirectional unmatched reporting",
                        "governed_by": ["D2", "D4", "D7", "D9", "D10", "D11", "D20", "D21", "D23", "D24", "D25"], "tested_by": ["T3"]},
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
                           "governed_by": ["D3", "D4", "D9"], "tested_by": ["T4"]},
            "decisions.py": {"does": "decisions.json — the pricing decision as a file, not a flag",
                             "governed_by": ["D9"]},
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
            "master.py": {"does": "inventory.json — cards, positions, SKUs, listing states",
                          "governed_by": ["D3", "D7", "D8", "D10", "D11", "D20", "D21", "D23", "D26"], "tested_by": ["T7"]},
            "queues.py": {"does": "review.json and parked.json — the standing queues, and the "
                                  "cross-queue release a re-routed position needs",
                          "governed_by": ["D4", "D9", "D28"], "tested_by": ["T7"]},
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
                "twin, the Stop hook, the PostToolUse typecheck hook, D17's "
                "decision-context hook, `make status`, the screenshot runner and its "
                "manifest, and audit-history — diagnostic, never gating, per D18.",
        "governed_by": ["D14", "D16", "D17", "D18"],
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
                        "captures/, no printed code-card layout in the staged diff, then "
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
                "governed_by": ["D11", "D14", "D16", "D18"],
                "note": "THE ORPHAN RULE CANNOT SEE THIS FILE — it has no suffix to "
                        "declare. Listed, so its absence would be a finding; unprotected, "
                        "so a sibling hook's arrival would not be.",
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
                "governed_by": ["D2", "D6", "D12", "D16", "D17", "D18", "D22", "D23", "D24"],
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
                "governed_by": ["D16", "D17"],
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
                # drop it and a render is named after one view and shows another.
                "governed_by": ["D5", "D13", "D31"],
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
                        "mark-sold, undo, search and box routes; the sidecar identify reads "
                        "back; the photo store; the origin allowlist that stands between a "
                        "stray browser tab and a hard delete; "
                        "and SERVER_EVENTS — `corrected`, `removed`, `answered`, `unanswered`, `reshot`, appended "
                        "to history.jsonl through _history inside the route's own "
                        "Store.write(), so the line and the change it describes commit "
                        "together or neither does. None of the five is a member of "
                        "master.STATES, which is what keeps _state_before_sale from "
                        "restoring a reversed sale to one of them.",
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
                "governed_by": ["D1", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "D11", "D13", "D16", "D20", "D21", "D22", "D23", "D24", "D26", "D28", "D29", "D30"],
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
                        "opens no socket and starts no child.",
                # D1 is the two-phase split, which is why join/emit/reconcile can answer in
                # the request and identify cannot. D9 is the decisions gate. D13 is one truth
                # on one Mac, which is what a detached child outliving this process rests on.
                # D32 is why --force-resubmit is deliberately not offered to a screen.
                "governed_by": ["D1", "D2", "D9", "D13", "D16", "D25", "D32"],
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
        "does": "the web app. Six routes behind a hand-written hash router, five of them the "
                "owner's — the capture screen that Gate B runs on, the review queue, the "
                "inventory SKU view, the pull preview and step 6's component gallery — and one "
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
            "vite.config.ts": {"does": "the dev server on :5173, strictPort — a busy port fails "
                                       "loudly rather than serving on 5174, where CLAUDE.md, the "
                                       "Makefile and scripts/views.txt would all three be wrong",
                               "governed_by": ["D13"]},
            "playwright.config.ts": {"does": "how `make design-check` runs the spec, including the "
                                             "Vite it starts for itself",
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
            "src/App.tsx": {"does": "the shell: five hash routes since D31 merged #/boxes and #/pull "
                                    "into #/inventory, one ROUTES table driving both "
                                    "the nav and the render, and the persona field that decides "
                                    "the Fulfiller's view gets no chrome at all. #/boxes is the "
                                    "seventh, registered with D20's screen rather than after it.",
                            "governed_by": ["D5", "D10", "D13", "D16", "D20", "D31"]},
            "src/App.css": {"does": "the shell's chrome: a 1px hairline under the nav, no tint, no "
                                    "shadow, and why this nav may never render on the "
                                    "Fulfillment view",
                            "governed_by": ["D5", "D10"]},

            # ---- the wire, and the two seams ----
            "src/server.ts": {"does": "the only module that talks to the capture server, so the "
                                      "stop-the-run failure rule is one decision. Surfaces the "
                                      "server's own messages verbatim, and holds the two "
                                      "readers every screen shares: a thrown thing as an "
                                      "owner-side screen draws it, and the position label as "
                                      "the server rendered it.",
                              "governed_by": ["D3", "D4", "D5", "D6", "D7", "D10", "D13", "D21", "D23", "D26", "D28", "D29", "D30"]},
            "src/types.ts": {"does": "the shapes the server speaks, in the server's own field "
                                     "names — captures, inventory, boxes, listings and the "
                                     "standing queues. Types only, it emits no JavaScript.",
                             "governed_by": ["D3", "D4", "D6", "D7", "D8", "D9", "D10", "D11", "D20", "D21", "D22", "D23", "D24", "D26", "D29", "D30"]},
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
                                      "BUILT 2026-08-22; thresholds are rig-tunable constants "
                                      "and the rig has not yet tuned them.",
                              "governed_by": ["D13", "D19"]},

            # ---- 7a's screens ----
            "src/CaptureScreen.tsx": {"does": "the capture screen, rebuilt 2026-08-23 to the owner-approved Pass D: "
                    "every control one hairline row at rest (key chip, label, value), one "
                    "field open at a time, claims panel (Box, Set hint, Rarity, Finish) over "
                    "a quiet SESSION footer (Game, Camera, Rotation, Trigger). Rarity at rest "
                    "is the bitfield — one 6px mark per rarity of the chosen game, filled = "
                    "claimed; the box list is never rendered as a list (filter, re-indexed "
                    "digits, Enter); small single-selects open as content-sized segmented "
                    "tracks. Camera folded into the row grammar; the camera never opens on "
                    "mount. Undo that names what it would delete.",
            "governed_by": ["D3", "D10", "D13", "D19", "D21", "D22", "D23", "D27"]},
            # D3 earns its place on a stylesheet: the no-claim finish chip is drawn dashed
            # because rung 1 distinguishes "no metadata recorded" from a recorded claim, and
            # that distinction is carried here in a border style rather than in any logic.
            "src/CaptureScreen.css": {"does": "its layout, at the dense end of docs/DESIGN.md's one "
                                              "system, two densities. Owner-side; the Fulfillment "
                                              "floors do not govern here.",
                                      "governed_by": ["D3", "D5", "D27"]},
            "src/BoxBrowse.tsx": {"does": "the box walk, D31's default way into #/inventory — was #/pull until the "
                    "three routes merged. The card's own capture photo beside its position label "
                    "and, since D30, "
                    "its neighbours and the section's gap count. ONE WRITE since 2026-08-23 "
                    "— the re-shoot control (D26, owner's placement ruling): replace a bad "
                    "stored photo from a file, record untouched, allocator never involved. "
                    "Everything else stays look-only, and the header argues the exception.",
            "governed_by": ["D6", "D10", "D19", "D20", "D21", "D22", "D24", "D26", "D27", "D30", "D31"]},
            "src/BoxBrowse.css": {"does": "its layout, and why no accent appears anywhere in it. Its list keeps an "
                                  "INSET focus ring and says so — it clips its own overflow, which is the "
                                  "case base.css's standing ring cannot serve",
                                  "governed_by": ["D5", "D6", "D13", "D30", "D31"]},

            # ---- 7b's screens. Built 2026-08-13, BEFORE Gate B; routed the same day ----
            #
            # Every entry in this block describes a file that exists, typechecks, lints clean
            # and opens at a hash. `does` says what the file is for, never that a person has
            # seen it hold a real card — the distinction the whole entry note above is about,
            # and the one a reader skimming `does` lines would otherwise lose.
            "src/ReviewQueue.tsx": {
                "does": "the review queue: one card at a time, photo first, single column, the "
                        "reason as a human label over its machine string, candidate rows "
                        "priced from the export, and an answer that writes and advances with "
                        "no dialog. Reads GET /queues and writes one candidate row back "
                        "through src/server.ts like every other screen.",
                "governed_by": ["D3", "D4", "D5", "D6", "D9", "D10", "D13", "D22", "D23", "D28", "D29"],
            },
            # D9 governs a stylesheet here, and it is the sharpest instance of what building
            # 7b early costs: the price bands that drive the type scale are the one set of
            # numbers in this directory invented rather than read out of a module, and D9's
            # threshold is the only real number they are anchored to.
            "src/ReviewQueue.css": {
                "does": "its layout, and the price-driven type scale that makes the sort "
                        "visible — name size and price size stepping down together, parked "
                        "rows dimmed. Accent outlined, never filled, wherever there are two "
                        "answers. The bands are still a guess: Gate B priced $0.04-$0.40 end "
                        "to end, so every queue row landed in one band and no mixed-value lot "
                        "has tested an edge.",
                "governed_by": ["D5", "D9", "D13", "D28", "D29"],
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
                        "it is not here.",
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
                "governed_by": ["D5", "D6", "D7", "D8", "D10", "D13", "D24", "D26", "D27", "D31"],
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
                        "which D10 forbids outright.",
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
                "governed_by": ["D5", "D10", "D13", "D20", "D21", "D22", "D26", "D27", "D31"],
            },
            "src/BoxOps.css": {
                "does": "the box header, the section track and the editors, at the dense "
                        "owner-side end. No accent anywhere in it and no exception — every box "
                        "carries four controls, so a fill would have to pick one and would then "
                        "mean 'important'. The seal's weight comes from the number on it.",
                "governed_by": ["D5", "D20", "D22", "D31"],
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
                                              "off the SKU rather than counted from the copies.",
                                      "governed_by": ["D4", "D5", "D6", "D7", "D10", "D20", "D24", "D26", "D30", "D31"]},
            "src/CardLocations.css": {"does": "the group at two densities. The Fulfiller's copy is a "
                                              "card with a photo; the owner's is a row.",
                                      "governed_by": ["D5", "D7", "D31"]},
            "src/RunPanel.tsx": {"does": "THE PIPELINE, ON A SCREEN. The four commands of batch "
                                         "script v2 in the detail column of #/inventory, scoped to "
                                         "the box the walk is in or the cards ticked in it. A two-step "
                                         "money gate with no typing: Check cost prints the command's "
                                         "own preflight, and only then does the one solid accent fill "
                                         "on the panel appear. Join, emit and reconcile beside it, "
                                         "each marked free and re-runnable; every command's stdout "
                                         "shown verbatim; the import CSVs downloadable, which is the "
                                         "gap docs/GATES.md names as what Gate B did not close.",
                                 # D1 is why one step spawns and three answer in the request. D9 is
                                 # the decisions document this panel edits as text rather than as a
                                 # form. D3 is the finish-claim bypass its join control offers. D31
                                 # is why it is a panel on #/inventory and not a seventh route. D32
                                 # is the crop and the max-edge beside it.
                                 "governed_by": ["D1", "D3", "D9", "D13", "D16", "D31", "D32"]},
            "src/RunPanel.css": {"does": "the panel at owner density — the 4-16 end of the scale, mono "
                                         "on every number, and exactly one solid accent fill: the "
                                         "button that spends, drawn only once the estimate is on "
                                         "screen above it.",
                                 "governed_by": ["D31"]},
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
                        "into a determination. Run by `make design-check`.",
                "governed_by": ["D3", "D22", "D23", "D27"],
                "note": "No box is ever selected and only reads are stubbed, so no capture "
                        "is ever taken — motion-live.spec.ts's rule, for its reason. It "
                        "exists because nothing ran these controls at all: when the claim "
                        "became a set, tsc, eslint and every spec stayed green over a "
                        "control that had never been pressed by anything but a human.",
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
                "governed_by": ["D1", "D3", "D9", "D13", "D31", "D32"],
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
                        "control that draws but sends the wrong body fails here.",
                "governed_by": ["D5", "D7", "D10", "D13", "D20", "D24", "D26", "D30", "D31"],
                "note": "THE CHECK `CLAUDE.md`'s ROUTE-IS-NOT-A-FEATURE RULE SAYS DOES NOT "
                        "EXIST. That rule was written on 2026-08-23 after three routes shipped "
                        "with full T7 coverage and no client function and no control — green "
                        "harness, green docs-audit, unusable product. T7 proves the server "
                        "honours a request; this proves a human pressing a control produces "
                        "that request. Neither can see the other's half. Like its siblings it "
                        "is NOT a harness test: it starts a browser, so it runs under "
                        "`make design-check` and is deliberately off the commit path.",
            },
            "tests/fulfillment.spec.ts": {
                "does": "all nine rows of the Fulfillment constraints table against the "
                        "rendered view, with every contrast ratio computed from the colours "
                        "the page actually painted rather than from a number published in "
                        "docs/DESIGN.md. Run by `make design-check`.",
                "governed_by": ["D5", "D10", "D13", "D24"],
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
