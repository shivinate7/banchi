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
                "governed_by": ["D2", "D16", "D17", "D18"],
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
                "governed_by": ["D15", "D16"],
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
                "does": "the PreToolUse twin of the commit hook's opsec rules — fixture "
                        "writes, images outside captures/, content matching the printed "
                        "code-card layout. DISABLED in .claude/settings.json since "
                        "2026-08-03: it blocked placeholders in prose about the format and "
                        "cost two blocked writes in one session.",
                # D16 is where being off is recorded and what it costs — with this quiet,
                # `--no-verify` drops the code-card literal rule with nothing behind it,
                # and only the permissions.deny rules still cover fixtures. Read that
                # entry before re-enabling: the failure was over-triggering, so the fix is
                # a narrower pattern, never a toggle.
                "governed_by": ["D11", "D14", "D16"],
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
                "governed_by": ["D5", "D13"],
            },
        },
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
                "does": "the nine routes, the sidecar identify reads back, the photo store, "
                        "and SERVER_EVENTS — `corrected`, `removed`, `answered`, appended "
                        "to history.jsonl through _history inside the route's own "
                        "Store.write(), so the line and the change it describes commit "
                        "together or neither does. None of the three is a member of "
                        "master.STATES, which is what keeps _state_before_sale from "
                        "restoring a reversed sale to one of them.",
                # D5 is here because the file cites it: the concurrency it is tested at is two
                # and four simultaneous captures, and two is D5's two people on two devices.
                # D4 and D7 arrived with 7b — the review answer is D4's one-tap choice, and
                # mark-sold is the per-position half of D7's aggregate-by-SKU rule.
                # D10 earned a second job with the history lines: index reuse after an undo is
                # what decides that a removal must be logged at all, since without the line
                # the log reads `captured 3/2` twice over two physical cards.
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
