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
# `blocked_by` names the step or gate that unblocks it, never a date.

BUILD_ORDER = [
    {"step": 1, "title": "Repo init, fixtures committed, git from commit zero", "status": "done"},
    {"step": 2, "title": "Scaffolding: Makefile, hooks, screenshot script, failing harness", "status": "done"},
    {"step": 3, "title": "Verification harness T1-T4", "status": "done"},
    {"step": 4, "title": "Batch script v2: Batch API, variant ladder, catalog join", "status": "done",
     "note": "code done 2026-08-03, harness green T1-T6. Never run against a real card — that is Gate B."},
    {"step": 5, "title": "Capture server: POST /capture, sidecars, /status, photo service, inventory state", "status": "done",
     "note": "code done 2026-08-11, spec at docs/specs/capture-server.md. No harness test reaches it — that gap is recorded in docs/DEBTS.md, not closed."},
    {"step": 6, "title": "Design tokens locked, one component built against them", "status": "done",
     "note": "tokens locked 2026-08-12 by interview; the pull-confirm built against them 2026-08-12 "
             "at app/src/PullConfirm.tsx, rendered by `make screenshot` and asserted by "
             "`make design-check`. Building it caught two places where docs/design-refs/locked.html "
             "disagrees with docs/DESIGN.md — see that directory's README."},
    {"step": 7, "title": "Vite capture app: device picker, capture, inventory, review queue, Fulfillment view", "status": "next",
     "note": "the toolchain landed with step 6: app/ is a Vite + React + TS project with one "
             "component, a gallery route and a Playwright spec. Step 7 adds screens to it."},
    {"step": 8, "title": "Gate B smoke test, 20 cards end to end", "status": "blocked", "blocked_by": "step 7"},
    {"step": 9, "title": "Vendor the pokemontcg.io catalog: snapshot, SQLite index, image mirror", "status": "blocked", "blocked_by": "Gate B"},
    {"step": 10, "title": "Feeder integration", "status": "blocked", "blocked_by": "Gate C"},
    {"step": 11, "title": "pokemontcg.io API key", "status": "done", "note": "done 2026-08-03; step 9 removes the need for it."},
    {"step": 12, "title": "Scale, polish, deferred list", "status": "blocked", "blocked_by": "all gates"},
]

# --------------------------------------------------------------------------------- gates

# status: passed | next | blocked. Same vocabulary as BUILD_ORDER, same reason.

GATES = [
    {"gate": "A", "status": "passed", "on": "2026-07-26",
     "what": "TCGplayer seam: Level 4, SV09 fixture, 2-row Import to Staged end to end"},
    {"gate": "B", "status": "next", "blocked_by": "step 7",
     "what": "20-card end-to-end smoke test, plus Haiku finish detection against ~10 real photos",
     "why_it_matters": "the harness cannot validate foil detection — T1's images have no foil texture"},
    {"gate": "C", "status": "blocked", "blocked_by": "Gate B",
     "what": "feeder integration: motion state machine, 50-card run, then a full box"},
]

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
            "__main__.py": {"does": "parser, COMMANDS dispatch, exit codes", "governed_by": ["D1", "D3", "D9"]},
            "cmd_identify.py": {"does": "submit, wait, collect, cache. The one that costs money.", "governed_by": ["D1", "D2"]},
            "cmd_join.py": {"does": "resolve identifications against the export", "governed_by": ["D7", "D11"]},
            "cmd_emit.py": {"does": "write import CSVs; refuses while a price is unanswered", "governed_by": ["D9"]},
            "cmd_reconcile.py": {"does": "diff intent against TCGplayer's Export From Staged", "governed_by": ["D7", "D11"]},
            "resolve.py": {"does": "turning a run's identifications into a join; shared by join and emit", "governed_by": ["D4", "D10"]},
            "runs.py": {"does": "run directories and manifest.json", "governed_by": ["D1"]},
        },
    },
    {
        "path": "pipeline/",
        "status": "built",
        "does": "CSV, variant ladder, pricing, join, routing, run decisions",
        "governed_by": ["D2", "D3", "D4", "D7", "D8", "D9", "D10", "D11", "D12"],
        "modules": {
            "tcgcsv.py": {"does": "TCGplayer Filtered CSV read/write and byte-format inspection",
                          "governed_by": ["D11"], "tested_by": ["T2"],
                          "note": "real CSV library only — v1 bug 2 was a naive split(\",\")"},
            "join.py": {"does": "catalog join by SKU, aggregation, bidirectional unmatched reporting",
                        "governed_by": ["D2", "D4", "D7", "D9", "D10", "D11"], "tested_by": ["T3"]},
            "variant.py": {"does": "the four-rung variant ladder", "governed_by": ["D3", "D12"], "tested_by": ["T4"]},
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
            "prompt.py": {"does": "the identification prompt and its fingerprint", "governed_by": ["D2", "D3"], "tested_by": ["T1"]},
            "batch.py": {"does": "Batch API submit/poll/collect. Batch, never sequential.", "governed_by": ["D2"], "tested_by": ["T1"]},
            "sidecar.py": {"does": "reading a capture directory: photos, JSON sidecars, position", "governed_by": ["D2", "D3", "D10"]},
            "images.py": {"does": "downscale, encode, hash a photograph for the API", "governed_by": ["D2"]},
        },
    },
    {
        "path": "geometry/",
        "status": "built",
        "does": "find the card in the frame; cut the crop-retry bands",
        "governed_by": ["D1", "D2"],
        "note": "T6 is synthetic composites only. A green T6 means the geometry is "
                "self-consistent, NOT that detection works on rig photos — that is a Gate B number.",
        "modules": {
            "detect.py": {"does": "card-boundary detection: where the card is, how far it is rotated",
                          "governed_by": ["D1"], "tested_by": ["T6"]},
            "crop.py": {"does": "cut the crop-retry regions out of a registered card",
                        "governed_by": ["D1"], "tested_by": ["T6"]},
        },
    },
    {
        "path": "store/",
        "status": "built",
        "does": "the master store: inventory, cache, standing queues",
        "governed_by": ["D4", "D7", "D9", "D10", "D13", "D15"],
        "note": "no harness test reaches this package — nothing under harness/ imports "
                "store. `built` above means the code exists, not that it is covered; "
                "docs/DEBTS.md records why that is not being fixed before step 5.",
        "modules": {
            "master.py": {"does": "inventory.json — cards, positions, SKUs, listing states",
                          "governed_by": ["D7", "D10"]},
            "queues.py": {"does": "review.json and parked.json — the standing queues",
                          "governed_by": ["D4", "D9"]},
            "cache.py": {"does": "identifications.json — answers already paid for", "governed_by": ["D2"]},
            "files.py": {"does": "where the store lives, the lock, the atomic replace", "governed_by": ["D13", "D15"]},
            "session.py": {"does": "lock-free read, or locked read-modify-write", "governed_by": ["D13"]},
        },
    },
    {
        "path": "harness/",
        "status": "built",
        "does": "T1-T6. The Stop hook runs it at every turn end; the pre-commit hook does not.",
        "governed_by": ["D2", "D12", "D15"],
        "note": "the contract is docs/GATES.md; every threshold there is a number, not an adjective",
        "modules": {
            "run.py": {"does": "the explicit ordered TESTS registry — no discovery magic", "governed_by": ["D1"]},
        },
    },
    {
        "path": "scripts/",
        "status": "built",
        "does": "opsec guards, the stop gate, the post-edit typecheck hook, the docs audit, "
                "the screenshot runner, `make status` — which reads this file for the next "
                "step and the gate — and audit-history, which replays the auditor over old "
                "trees. Diagnostic; never gates, per D18.",
        "governed_by": ["D14", "D16", "D18"],
        "note": "scripts/status.py declares every file it reads in a SOURCES literal, and "
                "the audit's status-sources check verifies that list. Its values are "
                "derived so they cannot go stale; that check is what catches its *reader* "
                "going stale.",
    },
    {
        "path": "fixtures/",
        "status": "built",
        "does": "real TCGplayer exports. Ground truth. Never modified — enforced by pre-commit.",
        "governed_by": ["D11"],
        "tested_by": ["T2"],
    },
    {
        "path": "server/",
        "status": "built",
        "does": "capture server: POST /capture, /status, GET /photo/<box>/<position>, inventory state",
        "governed_by": ["D3", "D6", "D10", "D13"],
        "note": "no harness test reaches this package either — see store/ above, and "
                "docs/DEBTS.md for what was verified by hand instead. Writes only through "
                "the store session, never straight to disk. The capture root is "
                "captures/cards/ and not captures/, so screenshot renders under "
                "captures/ui/ are never scanned as paid captures.",
        "modules": {
            "capture_server.py": {
                "does": "the five routes, the sidecar identify reads back, the photo store",
                "governed_by": ["D3", "D6", "D10", "D13"],
            },
        },
    },
    {
        "path": "app/",
        "status": "built",
        "step": 7,
        "does": "the web app. Step 6's pull-confirm component, the gallery that renders it, "
                "and the Playwright spec that asserts docs/DESIGN.md's Fulfillment floors. "
                "Step 7 adds the screens.",
        "governed_by": ["D5", "D6", "D13", "D18"],
        "note": "THE ORPHAN RULE DOES NOT REACH THIS DIRECTORY. It filters on SOURCE_SUFFIX, "
                "which is `.py`, so a new .tsx or .css file is never flagged as undescribed — "
                "the one entry in this file whose module list is maintained by hand alone. "
                "Recorded in docs/DEBTS.md beside the same gap in scripts/. "
                "Nothing here imports docs/design-refs/: those are drawings of the spec, and "
                "this is built from docs/DESIGN.md itself.",
        "modules": {
            "src/tokens.css": {"does": "the locked tokens as CSS custom properties. Tokens and nothing else.",
                               "governed_by": ["D18"]},
            "src/base.css": {"does": "reset and the page ground. Light only — there is no dark theme.",
                             "governed_by": ["D5"]},
            "src/PullConfirm.tsx": {"does": "step 6's component: the pull modal's confirm button",
                                    "governed_by": ["D5", "D6"]},
            "src/PullConfirm.css": {"does": "its three states, and why the key hint is absent by default",
                                    "governed_by": ["D5"]},
            "src/Gallery.tsx": {"does": "every state on one page — what `make screenshot` renders",
                                "governed_by": ["D5"]},
            "src/Gallery.css": {"does": "the gallery sheet's own layout. Not a product screen.",
                                "governed_by": ["D5"]},
            "src/main.tsx": {"does": "mounts the gallery. Step 7 mounts the app here instead.",
                             "governed_by": ["D13"]},
            "tests/pull-confirm.spec.ts": {
                "does": "the Fulfillment constraints table as assertions: 44px targets, 20px "
                        "body, 7:1 contrast, 12px apart. Run by `make design-check`.",
                "governed_by": ["D5"],
                "note": "NOT a harness test and not registered in harness/run.py:TESTS. The "
                        "harness contract in docs/GATES.md is six tests about the pipeline; "
                        "this runs a browser and is invoked on its own.",
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
