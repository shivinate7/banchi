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
    {"step": 7, "title": "Vite capture app: device picker, capture, inventory, review queue, Fulfillment view", "status": "next",
     "note": "SPLIT AT GATE B, AND 7a HAS SHIPPED. Built 2026-08-13 to "
             "docs/specs/capture-app.md: the shell and its three routes, the capture screen, "
             "undo, the pull preview, the trigger seam, the eslint rules, and the one new "
             "server route (DELETE /inventory/<box>/<index>). Thirteen files under app/ plus "
             "server/capture_server.py; `make lint` stopped being a stub in the same commit. "
             "7b is the review queue, the Fulfillment view, the inventory SKU views and "
             "mark-sold, deliberately after the gate so it is built against a real run "
             "rather than against guesses about what one produces. "
             "WHY THIS ROW IS STILL `next`, since half of it is built: 7b is real remaining "
             "scope, so `done` would be a lie, and the vocabulary above has no fourth word by "
             "design. Two candidates lost. `blocked_by: Gate B` is true of 7b alone and reads "
             "over the whole row as `the app is finished`. Moving `next` to step 8 is the "
             "bigger claim — `make status` would then tell whoever runs it to start a "
             "twenty-card physical run, against a build that has never met a card. That is the "
             "owner's call to make on the day, not a call to make by editing this file."},
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
            "__main__.py": {"does": "parser, COMMANDS dispatch, exit codes", "governed_by": ["D1", "D3", "D9"], "tested_by": ["T7"]},
            "cmd_identify.py": {"does": "submit, wait, collect, cache. The one that costs money.", "governed_by": ["D1", "D2"]},
            "cmd_join.py": {"does": "resolve identifications against the export", "governed_by": ["D7", "D11"], "tested_by": ["T7"]},
            "cmd_emit.py": {"does": "write import CSVs; refuses while a price is unanswered", "governed_by": ["D9"], "tested_by": ["T7"]},
            "cmd_reconcile.py": {"does": "diff intent against TCGplayer's Export From Staged", "governed_by": ["D7", "D11"], "tested_by": ["T7"]},
            "resolve.py": {"does": "turning a run's identifications into a join; shared by join and emit", "governed_by": ["D4", "D10"], "tested_by": ["T7"]},
            "runs.py": {"does": "run directories and manifest.json", "governed_by": ["D1"], "tested_by": ["T7"]},
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
        "note": "T7 reaches this package as of 2026-08-13 — the allocator, the lock and "
                "the atomic replace. queues.py and cache.py are read through a session "
                "there but nothing asserts their behaviour, so they carry no tested_by: an "
                "unenforced claim is the defect docs/DEBTS.md names, not a rounding error.",
        "modules": {
            "master.py": {"does": "inventory.json — cards, positions, SKUs, listing states",
                          "governed_by": ["D7", "D10"], "tested_by": ["T7"]},
            "queues.py": {"does": "review.json and parked.json — the standing queues",
                          "governed_by": ["D4", "D9"]},
            "cache.py": {"does": "identifications.json — answers already paid for", "governed_by": ["D2"]},
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
        "does": "capture server: POST /capture, /status, GET /photo/<box>/<position>, "
                "GET and PUT inventory state, and DELETE /inventory/<box>/<index> — undo",
        "governed_by": ["D3", "D6", "D10", "D13"],
        "note": "T7 reaches this package as of 2026-08-13: every route, every named "
                "refusal, and the sidecar seam read back through identify.sidecar.scan. "
                "What it still does not cover is in docs/DEBTS.md. Writes only through "
                "the store session, never straight to disk. The capture root is "
                "captures/cards/ and not captures/, so screenshot renders under "
                "captures/ui/ are never scanned as paid captures.",
        "modules": {
            "capture_server.py": {
                # Six since 2026-08-13, when step 7a's undo landed. The count is written out
                # rather than left as "the routes" because it is the one number here a reader
                # checks against the handlers, and it was wrong for exactly one commit.
                "does": "the six routes, the sidecar identify reads back, the photo store",
                # D5 is here because the file cites it: the concurrency it is tested at is two
                # and four simultaneous captures, and two is D5's two people on two devices.
                "governed_by": ["D3", "D5", "D6", "D10", "D13"],
                "tested_by": ["T7"],
            },
        },
    },
    {
        "path": "app/",
        "status": "built",
        "step": 7,
        "does": "the web app: three owner-side routes behind a hand-written hash router — the "
                "capture screen that step 7a shipped and Gate B runs on, the pull preview, and "
                "step 6's component gallery — plus the Playwright spec that asserts "
                "docs/DESIGN.md's Fulfillment floors. What step 7 has left is 7b: the review "
                "queue, the Fulfillment view, the inventory SKU views and mark-sold, all of it "
                "after Gate B.",
        "governed_by": ["D3", "D5", "D6", "D10", "D13", "D18"],
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
                "the half of that fix that lives in this file. "
                "Nothing here imports docs/design-refs/: those are drawings of the spec, and "
                "this is built from docs/DESIGN.md itself. "
                "NO ENTRY BELOW CARRIES tested_by, and that is a measurement rather than an "
                "oversight: no harness test imports anything in this directory. The Playwright "
                "spec is not a harness test and reaches only the pull-confirm — see its own "
                "entry.",
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
            "src/App.tsx": {"does": "the shell: three hash routes, one ROUTES table driving both "
                                    "the nav and the render",
                            "governed_by": ["D13", "D16"]},
            "src/App.css": {"does": "the shell's chrome: a 1px hairline under the nav, no tint, no "
                                    "shadow, and why this nav must never render on 7b's "
                                    "Fulfillment view",
                            "governed_by": ["D5"]},

            # ---- the wire, and the two seams ----
            "src/server.ts": {"does": "the only module that talks to the capture server, so the "
                                      "stop-the-run failure rule is one decision. Surfaces the "
                                      "server's own messages verbatim.",
                              "governed_by": ["D3", "D6", "D10", "D13"]},
            "src/types.ts": {"does": "the shapes the server speaks, in the server's own field "
                                     "names. Types only — it emits no JavaScript.",
                             "governed_by": ["D3", "D6", "D10"]},
            "src/useCamera.ts": {"does": "the camera: deviceId selection, never facingMode (v1 bug "
                                         "3), the native resolution requested explicitly, and a "
                                         "remembered device that refuses to fall back to another",
                                 "governed_by": ["D13"]},
            "src/trigger.ts": {"does": "the trigger seam: whatever fires a capture, behind one "
                                       "interface. Manual today; Gate C's motion state machine "
                                       "drops into the same slot.",
                               "governed_by": ["D13"]},

            # ---- 7a's screens ----
            "src/CaptureScreen.tsx": {"does": "the capture screen: live camera left, last capture "
                                              "right, box list from /status, set hint and finish "
                                              "always visible, undo that names what it would delete",
                                      "governed_by": ["D3", "D10", "D13"]},
            # D3 earns its place on a stylesheet: the no-claim finish chip is drawn dashed
            # because rung 1 distinguishes "no metadata recorded" from a recorded claim, and
            # that distinction is carried here in a border style rather than in any logic.
            "src/CaptureScreen.css": {"does": "its layout, at the dense end of docs/DESIGN.md's one "
                                              "system, two densities. Owner-side; the Fulfillment "
                                              "floors do not govern here.",
                                      "governed_by": ["D3", "D5"]},
            "src/CameraPicker.tsx": {"does": "the device picker, and the resolution the track "
                                             "actually negotiated — shown so a short stream is "
                                             "caught before a box is shot through it",
                                     "governed_by": ["D13"]},
            "src/CameraPicker.css": {"does": "its layout. No panel and no header strip, per "
                                             "docs/DESIGN.md.",
                                     "governed_by": ["D5"]},
            "src/PullPreview.tsx": {"does": "look only: the card's own capture photo beside its "
                                            "position label, the last link in the Gate B chain",
                                    "governed_by": ["D6", "D10"]},
            "src/PullPreview.css": {"does": "its layout, and why no accent appears anywhere in it",
                                    "governed_by": ["D5", "D6", "D13"]},

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

            # ---- what checks the above ----
            "eslint.config.js": {
                "does": "the two v1-bug rules docs/DECISIONS.md's table has named as guards since "
                        "it was written and never had: no facingMode (bug 3), no split(\",\") CSV "
                        "parsing (bug 2). No shared preset, no --fix — D18 keeps anything that "
                        "writes off the path `make check` runs.",
                "governed_by": ["D13", "D16", "D18"],
            },
            "tests/pull-confirm.spec.ts": {
                "does": "the Fulfillment constraints table as assertions: 44px targets, 20px "
                        "body, 7:1 contrast, 12px apart. Run by `make design-check`.",
                "governed_by": ["D5"],
                "note": "NOT a harness test and not registered in harness/run.py:TESTS. The "
                        "harness contract in docs/GATES.md is seven Python tests run at turn "
                        "end; this runs a browser and is invoked on its own.",
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
