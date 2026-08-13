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
             "and 9 are left standing and marked overtaken. The short form: 7b's screens "
             "display data no run has ever produced, so the review queue's price-driven row "
             "hierarchy is tuned against a distribution nobody has measured and its twelve "
             "reason codes have never all fired. "
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
    {"step": 8, "title": "Gate B smoke test, 20 cards end to end", "status": "next",
     "note": "unblocked 2026-08-13 when step 7 finished. THIS STEP IS PHYSICAL — twenty real "
             "cards through the rig — and no part of this repo has met a card. Every number "
             "the project has is a number about itself. docs/specs/capture-app.md section 10.2 "
             "lists what to measure while it runs, which is the payoff for 7b having been "
             "built early; section 10.1 keeps the pass criteria where they are."},
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
    {"gate": "B", "status": "next",
     "what": "20-card end-to-end smoke test, plus Haiku finish detection against ~10 real photos",
     "why_it_matters": "the harness cannot validate foil detection — T1's images have no foil "
                       "texture. Unblocked 2026-08-13: step 7 is done, so nothing further can "
                       "be built toward this. It is a physical run and it is the first thing "
                       "in this project that will produce a number about a card rather than "
                       "about the project."},
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
                # Nine since 2026-08-13, when 7b's queue read and its two writes landed on top
                # of step 7a's undo. The count is written out rather than left as "the routes"
                # because it is the one number here a reader checks against the handlers, and
                # it was wrong for exactly one commit at six.
                "does": "the nine routes, the sidecar identify reads back, the photo store",
                # D5 is here because the file cites it: the concurrency it is tested at is two
                # and four simultaneous captures, and two is D5's two people on two devices.
                # D4 and D7 arrived with 7b — the review answer is D4's one-tap choice, and
                # mark-sold is the per-position half of D7's aggregate-by-SKU rule.
                "governed_by": ["D3", "D4", "D5", "D6", "D7", "D10", "D13"],
                "tested_by": ["T7"],
            },
        },
    },
    {
        "path": "app/",
        "status": "built",
        "step": 7,
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
                "instruction, and what that costs is still true of every entry below: the "
                "screens display data no run has ever produced — the review queue's "
                "price-driven type scale is fitted to a distribution nobody has measured and "
                "its twelve reason codes have never all fired — so read every 7b entry as "
                "specified-and-unvalidated. "
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
            "src/App.tsx": {"does": "the shell: six hash routes, one ROUTES table driving both the "
                                    "nav and the render, and the persona field that decides the "
                                    "Fulfiller's view gets no chrome at all",
                            "governed_by": ["D5", "D10", "D13", "D16"]},
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
                              "governed_by": ["D3", "D4", "D5", "D6", "D7", "D10", "D13"]},
            "src/types.ts": {"does": "the shapes the server speaks, in the server's own field "
                                     "names — captures, inventory, and the standing queues. "
                                     "Types only, it emits no JavaScript.",
                             "governed_by": ["D3", "D4", "D6", "D9", "D10"]},
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
                "governed_by": ["D3", "D4", "D5", "D6", "D9", "D10", "D13"],
            },
            # D9 governs a stylesheet here, and it is the sharpest instance of what building
            # 7b early costs: the price bands that drive the type scale are the one set of
            # numbers in this directory invented rather than read out of a module, and D9's
            # threshold is the only real number they are anchored to.
            "src/ReviewQueue.css": {
                "does": "its layout, and the price-driven type scale that makes the sort "
                        "visible — name size and price size stepping down together, parked "
                        "rows dimmed. Accent outlined, never filled, wherever there are two "
                        "answers. The bands are a guess at a distribution nobody has measured.",
                "governed_by": ["D5", "D9", "D13"],
            },
            "src/Inventory.tsx": {
                "does": "D7's SKU -> positions map made visible: one row per SKU carrying the "
                        "copy count, expanding to the individual positions holding it. Reads "
                        "GET /inventory, groups in the browser, keeps nothing — there is one "
                        "place inventory lives and it is not here.",
                "governed_by": ["D5", "D7", "D8", "D10", "D13"],
            },
            "src/Inventory.css": {
                "does": "its layout, at the dense owner-side end of the one system, two "
                        "densities — and why no accent appears anywhere in it",
                "governed_by": ["D5", "D7", "D13"],
            },
            "src/Fulfillment.tsx": {
                "does": "D5's second persona's entire product: cards to pull in box-walk "
                        "order, photo-confirm before each pull, one-tap mark-sold with an undo "
                        "window. No machine string and no server message reaches this screen — "
                        "both are correct for the owner and neither is his.",
                "governed_by": ["D5", "D6", "D7", "D10", "D13"],
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

            # ---- what checks the above ----
            "eslint.config.js": {
                "does": "the two v1-bug rules docs/DECISIONS.md's table has named as guards since "
                        "it was written and never had: no facingMode (bug 3), no split(\",\") CSV "
                        "parsing (bug 2). No shared preset, no --fix — D18 keeps anything that "
                        "writes off the path `make check` runs.",
                "governed_by": ["D13", "D16", "D18"],
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
            "tests/fulfillment.spec.ts": {
                "does": "all nine rows of the Fulfillment constraints table against the "
                        "rendered view, with every contrast ratio computed from the colours "
                        "the page actually painted rather than from a number published in "
                        "docs/DESIGN.md. Run by `make design-check`.",
                "governed_by": ["D5", "D10", "D13"],
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
