# PKMNSCAN
#
# Empty targets exit 1. A target that exits 0 with nothing to run is a lie the rest of
# the project would be built on top of — `make check` green means every check ran.

.DEFAULT_GOAL := help
.PHONY: help status map explain harness check cid-selftest pricearchive-selftest cid-audit ignore-check docs-audit map-fix map-fix-selftest orient orient-selftest serve-scope serve-scope-selftest guard-scope guard-scope-selftest vale audit-self-test verdict-selftest githooks-selftest merge merge-selftest revert-guard revert-selftest claim-ids claim-stale claim-selftest decisions-selftest debts-selftest gates-selftest port-agreement set-hint-agreement readiness-agreement mutate-anchors mutate-guards screen-freshness screen-freshness-selftest sigil-check suite-lock-selftest browser-scope-selftest js-breakpoints-selftest subagent-override-selftest janitor-agent icloud-sweep audit-history dev server screenshot design-check design-check-quiet lint typecheck venv launch-config worktree-setup hooks up down launch-agent demo demo-photos demo-seed demo-record demo-static demo-preview demo-freshness catalog-refresh catalog-index catalog-index-selftest catalog-mirror css-var-check css-var-check-selftest

# Prefer the venv if it exists, so `make harness` works without anyone remembering to
# activate anything. Falls back to system python3, which still runs T2-T5 — T1 needs the
# anthropic SDK and T6 needs Pillow + numpy, and each reports the missing dependency as a
# FAILURE rather than crashing or, worse, skipping. A skipped test must not read as a pass.
PYTHON := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

# Every app/ target needs its dependencies on disk first. Named as a fix rather than run
# automatically: an implicit install hides a slow, network-touching step inside a target
# that is supposed to serve, typecheck or assert — and the first time it matters is the
# first time someone clones this repo, which is exactly when a silent 80 MB download is
# least welcome.
NPM_GUARD = @[ -d app/node_modules ] || { \
	echo "app/ dependencies are not installed."; \
	echo "  Fix: npm --prefix app install"; \
	exit 1; }

# `venv` is already idempotent — the venv module tolerates an existing dir and pip happily
# reinstalls — so the gap was never the install, it was that nothing said to re-run it.
# Measured 2026-08-31: this worktree's .venv was built 2026-08-30 13:39, zxing-cpp was
# pinned into requirements.txt at 17:32 the same day, and the first symptom was a bare
# `ModuleNotFoundError` three stack frames into T8 with no venv in the trace at all — the
# same shape T2-T5's fallback-to-system-python3 is deliberately allowed to hit (see PYTHON
# above), except this venv existed and was simply stale, which that design never covered.
# Passes when there is no venv at all (falls through to system python3, unchanged) or when
# the stamp `venv` writes on a successful install is not older than requirements.txt.
VENV_GUARD = @[ ! -x .venv/bin/python ] || [ -f .venv/.deps-stamp -a ! requirements.txt -nt .venv/.deps-stamp ] || { \
	echo "requirements.txt has changed since this .venv was last installed into."; \
	echo "  Fix: make venv"; \
	exit 1; }

# ruff (D82) is a requirements.txt entry, not a system binary — same reasoning as NPM_GUARD:
# a lint target that silently no-ops without it would let `make check` go green having
# checked nothing.
RUFF_GUARD = @$(PYTHON) -m ruff --version >/dev/null 2>&1 || { \
	echo "ruff is not installed in $(PYTHON)."; \
	echo "  Fix: make venv"; \
	exit 1; }

help:
	@echo "PKMNSCAN — run 'make status' for where the build actually stands."
	@echo
	@echo "  make status       where you are: next step, T1 score, branch. Derived."
	@echo "  make map          docs/map.py, rendered. ARGS=<package|path|D<n>|--stale>"
	@echo "                    ARGS=\"D<n> --full\" prints that entry in full."
	@echo "  make explain      what \`make check\` runs, and what each row is worth."
	@echo "                    ARGS=<target> for one entry in full."
	@echo "  make venv         .venv + requirements.txt   (before the first harness run, and"
	@echo "                    again whenever requirements.txt changes — safe to re-run)"
	@echo "  make worktree-setup  venv + T1's banked cache, for a fresh git worktree"
	@echo "  make launch-config   .claude/launch.json for THIS checkout's dev port (D43)"
	@echo "  make hooks        arm the git hooks          (once, and again after every clone)"
	@echo "  make harness      T1-T8 verification tests. Run at turn end by the Stop hook."
	@echo "  make docs-audit   markdown vs the code it describes. Reports; never writes."
	@echo "  make map-fix      add the ids a file cites to its governed_by in docs/map.py."
	@echo "                    THE ONE GENERATOR: it writes and gates nothing (D18)."
	@echo "                    Previews. ARGS=--write applies. ARGS=--selftest proves it."
	@echo "  make map-fix-selftest  that generator, over a throwaway map it writes and drops."
	@echo "  make orient       which component renders the thing, and what selects it."
	@echo "                    ARGS=<file.tsx> [--name <Component>]. Derived, never stored."
	@echo "  make orient-selftest  that renderer, including the Orders.tsx case it exists for."
	@echo "  make vale         prose style over every tracked .md. Needs vale; never gates."
	@echo "  make audit-history  which docs-audit checks ever fired. Diagnostic; never gates."
	@echo "  make audit-self-test  the checker checks itself. In \`check\`, never in the git hook."
	@echo "  make githooks-selftest  main's guard, proved in a throwaway repo. Never in the git hook."
	@echo "  make merge-selftest  the merge wrapper's local half, in a throwaway repo and worktree."
	@echo "  make revert-guard  does this branch put a file back the way main had it before a"
	@echo "                    commit main already carries? Refuses an unexplained reversal (D133)."
	@echo "  make revert-selftest  the guard, proved by rebuilding PR #218/#221 in a throwaway repo."
	@echo "  make claim-ids        what the merge will allocate for this branch's slug ids. ARGS=--write."
	@echo "  make claim-stale      has an id this branch already claimed been taken by main"
	@echo "                    since? Reports and never repairs (D140, amended). Writes nothing."
	@echo "  make claim-selftest   the claimer, proved with main moving underneath the branch."
	@echo "  make decisions-selftest  docs/decisions/ is complete and still round-trips."
	@echo "  make debts-selftest      docs/debts/ is complete and still round-trips."
	@echo "  make gates-selftest      docs/gates/ is complete and still round-trips."
	@echo "  make catalog-refresh  re-clone pokemon-tcg-data and refresh vendor/pokemon-tcg-data/"
	@echo "                    (D15). Writes; never gates. ARGS=--dry-run to preview the diff."
	@echo "  make catalog-index  build vendor/pokemon-tcg-data/catalog.sqlite from the snapshot."
	@echo "  make catalog-index-selftest  that builder and pipeline/catalog.py, proved on a"
	@echo "                    throwaway fixture. In \`check\`, never in the hook."
	@echo "  make catalog-mirror  fill the pokemontcg.io image mirror. ARGS=--dry-run samples up"
	@echo "                    to 200 images over HTTP HEAD and reports the byte total; writes"
	@echo "                    nothing. Bare form fills it for real — not run by any target here."
	@echo "  make submission-selftest  the identify claim table, proved by racing two presses"
	@echo "                    over one card. In \`check\`, never in the hook."
	@echo "  make cid-selftest  the card's stable name and the photograph store, proved by"
	@echo "                    violating them: a stripped name that heals byte-identically, a"
	@echo "                    renumber that renames nothing, a move that touches no file, a"
	@echo "                    re-shoot excused by a RECORDED digest, and a -9 mid-transaction."
	@echo "                    Counts syscalls, because an outcome assertion cannot see work"
	@echo "                    that no longer happens. In \`check\`, never in the hook."
	@echo "  make pricearchive-selftest  D-pricehistory-resolves-by-sku's three tiers,"
	@echo "                    merged_export_rows_by_sku and row_for_sku, proved against a"
	@echo "                    throwaway store and real cached-export files under mktemp."
	@echo "                    PATH GATED (D247's sixteenth). In \`check\`, never in the hook."
	@echo "  make cid-audit    does every card's name still resolve to its photograph? Reads"
	@echo "                    the whole corpus, so it is NOT in \`check\` — \`make lan-check\`'s"
	@echo "                    reason. Three verdicts, and the third is \`not known\`."
	@echo "  make readings-selftest  the cached market-reading table, proved against an"
	@echo "                    independent reimplementation of its own two-source walk."
	@echo "                    In \`check\`, never in the hook."
	@echo "  make janitor-selftest  the sweep, proved against a throwaway clone. In \`check\`, never in the hook."
	@echo "  make reap-selftest  the kill guard, proved by pointing it at what it must not kill."
	@echo "  make silent-write-selftest  the silenced-write guard, proved by reproducing the"
	@echo "                    refused commit whose refusal went to /dev/null."
	@echo "  make guard-shell-selftest  the eight-clause shell guard, proved by committing its"
	@echo "                    mistakes in a throwaway repo: a destroyed file, a write into"
	@echo "                    another checkout, a nested symlink, a pattern that is not a process."
	@echo "  make coordinator-selftest  the merge-queue verdict rules. No network."
	@echo "  make suite-lock-selftest  one browser fleet at a time, proved by violating it."
	@echo "  make browser-scope-selftest  the browser-matrix classifier's spec map, on"
	@echo "                    fixtures and on the real tree (D-browser-spec-allow-list)."
	@echo "  make js-breakpoints-selftest  a JS media query's viewport width against what"
	@echo "                    the stylesheets declare (D123), proved by violating it then"
	@echo "                    fixing it. python3 only, no browser."
	@echo "  make subagent-override-selftest  the subagent-model override row, proved in a"
	@echo "                    real throwaway git repo with a real nested worktree: an"
	@echo "                    undated override is red, a currently-dated one is green,"
	@echo "                    an expired or too-far-dated one is red again."
	@echo "  make verdict-selftest  the design-check verdict reporter, run for real. No browser."
	@echo "  make serve-selftest  the supervisor's build job, against a throwaway tree. No node."
	@echo "                    PATH GATED: skipped when nothing in the branch reaches it."
	@echo "                    PKMNSCAN_SERVE_SCOPE=off runs it regardless."
	@echo "  make serve-scope   what serve-selftest reads, and whether this branch touches it."
	@echo "                    ARGS=list | ARGS=\"classify --base <rev>\". Fails open."
	@echo "  make serve-scope-selftest  that gate, including a CARRY drift it must catch."
	@echo "  make guard-scope   the SECOND path gate: what each of 16 guard self-tests reads,"
	@echo "                    derived from its own source. ARGS=list [--target <name>] |"
	@echo "                    ARGS=\"classify --target <name> --base <rev>\". Fails open."
	@echo "                    PKMNSCAN_GUARD_SCOPE=off runs every gated self-test regardless."
	@echo "  make guard-scope-selftest  that gate, both-ways wiring included."
	@echo "  make sync-selftest  the primary checkout's self-sync, proved by violating it."
	@echo "  make port-agreement  server/ports.py and app/devPort.ts answer the same numbers."
	@echo "  make set-hint-agreement  the capture screen and the export fetch resolve a set hint alike."
	@echo "  make readiness-agreement  app/src/readiness.ts against pipeline/decisions.py:blocking."
	@echo "  make mutate-anchors  every mutation anchor still present in the guard it targets. 0.03s."
	@echo "  make mutate-guards   RUN the mutations: each guard's suite must go red. ~190s, off check."
	@echo "  make screen-freshness  every server write in app/ has a way back. Needs node."
	@echo "  make screen-freshness-selftest  that guard's own cases, both directions. It sat"
	@echo "                    on no target at all until 2026-09-12 and was red on main."
	@echo "  make sigil-check   a bare \`#\` on a screen is a COUNT, never a store key (D92)."
	@echo "  make css-var-check   a \`var(--x)\` with no fallback where \`--x\` is defined"
	@echo "                    nowhere — the whole declaration drops silently."
	@echo "  make css-var-check-selftest  that checker, proved on fixtures in both directions,"
	@echo "                    including a property defined only from TSX."
	@echo "  make ignore-check  every path a worktree provisions is gitignored, link or not (D47)."
	@echo "  make icloud-sweep  list iCloud conflict copies. ARGS=--delete removes the identical ones."
	@echo "  make janitor      what a finished session left behind. ARGS=--confirm reaps tier 2."
	@echo "  make janitor-agent  run that sweep daily, unattended, with a log as its receipt."
	@echo "                    MAIN TREE ONLY. ARGS=--remove takes it away."
	@echo "  make reap         stop what THIS session started, and nothing else. Previews;"
	@echo "                    ARGS=--confirm presses. ARGS=\"port:5484 --confirm\" for one port."
	@echo "  make ci-check     what a fresh clone can prove: everything in check but vale."
	@echo "  make janitor-install  copy the sweep to ~/.claude/bin so every repo's hooks can reach it."
	@echo "  make lan-check    is the LAN URL still good? DNS, both servers, and a real"
	@echo "                    write. Reaches the network, so it never gates a commit."
	@echo "  make coordinator  the merge queue, READ rather than remembered: main, every open"
	@echo "                    PR with a SHA-pinned verdict, the worktrees, the live sessions."
	@echo "                    Reaches the network, so it never gates a commit."
	@echo "  make heartbeat    docs/GATES.md item 24: calls coordinator.py plus whether main's"
	@echo "                    own last push is green and janitor's preview. Never a daemon,"
	@echo "                    never --confirm. Writes .serve/heartbeat/, never gates a commit."
	@echo "  make check        harness + docs-audit + claim-stale + revert-guard +"
	@echo "                    port-agreement + set-hint-agreement + readiness-agreement +"
	@echo "                    screen-freshness +"
	@echo "                    screen-freshness-selftest + sigil-check +"
	@echo "                    css-var-check + css-var-check-selftest + ignore-check +"
	@echo "                    lint + vale + typecheck + audit-self-test +"
	@echo "                    mutate-anchors +"
	@echo "                    githooks-selftest + merge-selftest + revert-selftest +"
	@echo "                    claim-selftest + decisions-selftest + debts-selftest +"
	@echo "                    gates-selftest + submission-selftest +"
	@echo "                    cid-selftest + pricearchive-selftest + readings-selftest +"
	@echo "                    janitor-selftest + reap-selftest + silent-write-selftest +"
	@echo "                    guard-shell-selftest +"
	@echo "                    coordinator-selftest + suite-lock-selftest +"
	@echo "                    browser-scope-selftest +"
	@echo "                    serve-selftest + sync-selftest + verdict-selftest +"
	@echo "                    js-breakpoints-selftest + subagent-override-selftest +"
	@echo "                    guard-scope-selftest"
	@echo
	@echo "  ./pkmnscan identify <capture-dir>                 submit, wait, collect. COSTS MONEY."
	@echo "  ./pkmnscan join     <run-dir> --export <csv>      resolve against the export. Free."
	@echo "  ./pkmnscan emit     <run-dir>                     write import CSVs. Free."
	@echo "  ./pkmnscan reconcile <run-dir> <staged-export>    confirm what TCGplayer staged."
	@echo "  make up           THE server, detached: the API and the app on one port, and it"
	@echo "                    reloads itself when you edit Python and rebuilds the app when"
	@echo "                    you edit a screen (D138). Prints the link. Start here."
	@echo "  make merge        merge a PR and move main onto it (D42). ARGS=<n> previews;"
	@echo "                    ARGS=\"<n> --confirm\" performs it. On the owner's word only."
	@echo "  make down         stop it.  make up ARGS=--restart  stop and start."
	@echo "  make launch-agent start at login, so the link is always live. Main tree only."
	@echo "                    ARGS=--remove to undo it."
	@echo "  make dev          Vite with hot reload on :5173, against the server make up is"
	@echo "                    running. Blocks — background it in a session."
	@echo "  make server       Python capture server. :8000 in the main tree, its own port in a"
	@echo "                    worktree (D43) — it prints which. Blocks — background it."
	@echo "  make screenshot   render the views in scripts/views.txt to captures/ui/"
	@echo "  make design-check docs/DESIGN.md's Fulfillment floors, asserted in a browser. Takes"
	@echo "                    a machine-wide lock: one browser fleet at a time, across every"
	@echo "                    checkout (D122). ARGS=--wait queues instead of refusing."
	@echo "                    Leaves the verdict in .serve/design-check.json — read that,"
	@echo "                    never a \`tail\` pipe, which buffers the whole run."
	@echo "                    PW_ARGS=<flags> reaches Playwright itself (--shard, one spec);"
	@echo "                    ARGS never does. CI shards it three ways this way (D136)."
	@echo "  make design-check-quiet  the same run without the per-test progress stream."
	@echo
	@echo "  make demo         seed a demo store and record the wire into a fixture bundle."
	@echo "  make demo-photos  curate real card photographs into the tracked set. Needs a"
	@echo "                    store: SOURCE=<checkout>. Refuses any photo carrying a QR."
	@echo "  make demo-seed    the store alone, built on the curated photographs."
	@echo "  make demo-record  the bundle alone — sweep every GET the client can build."
	@echo "  make demo-static  the two above, then a static build to dist-demo/."
	@echo "                    DEMO_BASE=<path> is where it will be served from."
	@echo "  make demo-preview serve dist-demo/ exactly as a static host would."
	@echo "  make demo-freshness  whether the bundle still matches the wire it recorded."
	@echo "  make lint         eslint over app/, ruff over the Python packages (D82)."
	@echo "  make typecheck    tsc --noEmit over app/"
	@echo
	@echo "Build order and gates: docs/GATES.md"

venv: launch-config
	@python3 -m venv .venv
	@.venv/bin/python -m pip install --quiet --upgrade pip
	@.venv/bin/python -m pip install --quiet -r requirements.txt
	@touch .venv/.deps-stamp
	@echo "venv ready: $$(.venv/bin/python -V)"
	@echo "T1 also needs ANTHROPIC_API_KEY in the environment."

# `.claude/launch.json` NAMES A PORT, AND D43 MADE THE PORT PER CHECKOUT — so the file
# cannot be tracked and correct at the same time. It was tracked at a hardcoded 5173, which
# is right in the main tree and wrong in every linked worktree, and wrong in the exact shape
# D43 exists to prevent: the Browser pane would start THIS tree's dev server and then open a
# tab on 5173, which is either dead or is the MAIN TREE'S server. A worktree silently
# previewing main is the same fault `app/devPort.ts` was written to close, reached through
# the one file that change did not touch.
#
# So it is gitignored and written here, from `server/ports.py` — the same derivation Vite and
# Playwright read, so all three cannot disagree. Written by `venv`, which is already the
# documented first step in a fresh clone and is what `worktree-setup` calls; standalone as
# well, because the port follows the PATH and a renamed worktree needs it again.
#
# stdlib only, and it writes JSON through `json.dump` rather than a here-doc: a hand-built
# brace in a Makefile recipe is one escaping mistake away from a file the harness cannot
# parse, and the failure would present as "the preview does not work" rather than as a
# syntax error.
# FORCES, because somebody typed it. The conservative half — write an absent or stale file,
# never touch a hand-edited one — is `--if-needed`, and scripts/worktree-guard.sh is what
# calls it, on every session start, which is what makes a fresh worktree correct without
# anybody remembering this target exists.
launch-config:
	@$(PYTHON) scripts/launch-config.py

# A GIT WORKTREE GETS THE TRACKED FILES AND NOTHING ELSE, which is the whole of the problem
# this target exists for. Three things `make harness` needs are gitignored by deliberate
# decision and therefore do not travel: `.venv/` (D15's requirements are installed, not
# committed), `harness/.cache/` (T1's banked responses), and `.env` (the key). A fresh
# worktree fails T1, T6 and T7 on day one, and none of the three failures says "you are in
# a worktree" — T6 says `No module named 'numpy'` and T7 raises an AttributeError from
# deep inside a fixture. Measured 2026-08-29: that is exactly how it presented, and it cost
# a session to diagnose from those symptoms.
#
# THE CACHE IS THE ONE THAT MATTERS, and it is not a convenience. Without it T1's cache
# lookup misses, and a miss used to mean a fresh submission of ~150 images — under the Stop
# hook, at the end of every turn. `harness/tests/t1_id_eval.py` now refuses that outright,
# so the failure is loud and free rather than silent and billed; this target is what makes
# the refusal easy to answer instead of merely correct.
#
# THE CACHE IS COPIED AND THE IMAGES ARE SYMLINKED, and the split is not arbitrary. A
# shared cache would let a `PKMNSCAN_RERUN_T1=1` in either tree rewrite what the other
# scores against, and the two trees are meant to be able to disagree — that is why one is
# a worktree. It is 90 KB, so copying costs nothing. The eval images are 133 MB and are
# immutable: `fixtures.load` only ever adds a missing file keyed by card id, so sharing
# them cannot make two trees score differently. Without them T1 still passes — by
# downloading 151 images from pokemontcg.io, which is slow, rate-limited without a key,
# and fails outright offline.
#
# `.env` IS DELIBERATELY NOT COPIED. It is the API key, copying secrets around a disk is
# how they end up somewhere nobody is tracking, and T1 does not need it once the cache is
# warm. Named here so its absence reads as a decision rather than an oversight.
# The cache/mirror/node_modules provisioning below is shared with scripts/worktree-guard.sh
# (the SessionStart hook) via scripts/worktree-provision.sh — see that script's header for
# why: this used to be a second copy of the same cp/ln/python-one-liner sequence, and D47's
# image-mirror fix had to be applied to both by hand the one time the mirror moved.
worktree-setup:
	@common="$$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || git rev-parse --git-common-dir)"; \
	case "$$common" in /*) ;; *) common="$$(cd "$$common" && pwd)" ;; esac; \
	main="$$(dirname "$$common")"; \
	here="$$(pwd)"; \
	if [ "$$main" = "$$here" ]; then \
		echo "This IS the main working tree — nothing to copy into it."; \
		echo "  Fix: make venv"; \
		exit 1; \
	fi; \
	$(MAKE) --no-print-directory venv; \
	bash scripts/worktree-provision.sh "$$main"
	@echo "worktree ready. \`make harness\` should now be green without spending anything."

# core.hooksPath is LOCAL config — it lives in .git/config, which is never pushed. So a fresh
# clone carries scripts/githooks/pre-commit as a tracked file with NOTHING POINTING AT IT, and
# CLAUDE.md's bearer-instrument rule is unenforced on the first commit. It fails silently,
# which is the only way an opsec rule can fail badly: nothing is printed, nothing exits 1, and
# the commit that leaks a live code looks exactly like every commit before it.
#
# This is the one setup step that cannot itself be committed, so it cannot be made automatic —
# `make status` reports the unarmed state instead, which is why that target grew a Git hooks
# line. Idempotent: running it on an armed clone is free.
#
# The chmod is not padding. git skips a non-executable hook WITHOUT A WORD, so a correct
# hooksPath over a non-executable file is the same silent failure by another route.
# THE HOOKS ARE INSTALLED INTO THE GIT COMMON DIR, NOT POINTED AT IN A WORKING TREE.
#
# D42 first pointed core.hooksPath at the MAIN worktree's scripts/githooks, on the argument
# that one absolute path then governs every worktree of the clone whatever commit each sits
# on. That argument was right about worktrees and wrong about the main checkout, and it was
# falsified within the hour: the moment D42 landed on main, the main checkout was sitting on
# another session's WIP branch that predated it, so the directory git actually read held one
# hook out of three. THE GUARD WAS ARMED AT ZERO AND NOTHING SAID SO — which is the silent
# failure this repo refuses everywhere else, reproduced by the fix for it.
#
# A working tree is the wrong home for this because its contents are a function of somebody
# else's checkout. `.git` is not: it is per-clone, shared by every worktree, and no branch
# can empty it. So `make hooks` COPIES the tracked hooks there and aims the config at the
# copy — the install pattern husky and pre-commit both use, for this reason.
#
# WHAT IS GIVEN UP, NAMED RATHER THAN DESIGNED AWAY: the copy can go stale. Editing
# scripts/githooks does not change what git runs until this target is run again. There is no
# check that closes this without lying — the tracked file legitimately differs between
# branches, so "installed does not match this tree" is not an error and must never gate a
# commit. `make status` reports the difference instead, which is the one place in this repo
# whose whole job is telling you the state you are actually in.
#
# IT INSTALLS WHAT GIT TRACKS, NEVER WHAT THE DIRECTORY HOLDS, and that distinction was
# earned rather than anticipated. The first version copied `scripts/githooks/*` and this repo
# lived in iCloud Drive at the time, which had quietly made `pre-push 2` and `reference-transaction 2`
# beside the originals — so the first run installed five hooks from three files, two of them
# untracked and reviewed by nobody. Git would not have RUN those two (it dispatches on exact
# names), so the damage was cosmetic this time; the mechanism is not. A hook directory whose
# contents are decided by whatever is lying on disk has given up the reviewability that is
# the entire reason D42 keeps these files tracked instead of writing them into .git by hand.
# `git ls-files` is the only enumeration that means "the thing someone reviewed".
#
# Untracked files present are REPORTED, not silently skipped and not a failure: a new hook
# being written is a normal state, and the honest thing is to say it was not installed.
#
# AND IT CLEARS THE PER-WORKTREE OVERRIDE, BECAUSE THIS REPO HAS `extensions.worktreeConfig`
# ON AND SOMETHING WRITES ONE PER WORKTREE. D42 asserted that core.hooksPath "lives in the
# common .git dir, so ONE value governs every worktree of this clone". That is false here.
# Measured 2026-08-29, after the install below reported success: all four
# .claude/worktrees/*/config.worktree carried their own `core.hooksPath` — alongside a
# `core.longpaths`, so whatever creates those worktrees writes it — and a per-worktree value
# BEATS the common one. `git config --get core.hooksPath` in a worktree still answered the
# old path, and the guard was still armed at zero in exactly the checkouts it exists for.
# Caught by running the self-test against the installed directory rather than by reading the
# config, which is the argument for that override existing at all.
#
# Unsetting rather than overwriting: one value in the common config is the property D42
# wanted, and re-pointing four copies just recreates four things that can drift. A NEW
# worktree will be handed the override again by whatever creates it, so this is a repair and
# not a fix — `make status` is what reports the state, and it now reads NOT ARMED whenever
# the effective path is not the install.
#
# The chmod is not padding. git skips a non-executable hook WITHOUT A WORD, so a correct
# hooksPath over a non-executable file is the same silent failure by another route. Neither
# is the verify at the end: an install that half-worked must not print "armed".
hooks:
	@set -e; \
	  common="$$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || git rev-parse --git-common-dir)"; \
	  case "$$common" in /*) ;; *) common="$$(cd "$$common" && pwd)" ;; esac; \
	  dest="$$common/hooks-armed"; \
	  src="$$(pwd)/scripts/githooks"; \
	  [ -d "$$src" ] || { echo "no scripts/githooks in this tree — run this from a checkout that has them"; exit 1; }; \
	  case "$$dest" in */hooks-armed) ;; *) echo "refusing to install into $$dest"; exit 1 ;; esac; \
	  tracked="$$(git ls-files scripts/githooks)"; \
	  [ -n "$$tracked" ] || { echo "git tracks no file under scripts/githooks — nothing to install"; exit 1; }; \
	  mkdir -p "$$dest"; \
	  find "$$dest" -mindepth 1 -maxdepth 1 -delete; \
	  echo "$$tracked" | while IFS= read -r f; do \
	    [ -n "$$f" ] || continue; \
	    install -m 755 "$$f" "$$dest/$$(basename "$$f")"; \
	  done; \
	  git config core.hooksPath "$$dest"; \
	  git worktree list --porcelain | sed -n 's|^worktree ||p' | while IFS= read -r w; do \
	    [ -n "$$w" ] || continue; \
	    git -C "$$w" config --worktree --unset-all core.hooksPath 2>/dev/null || true; \
	  done; \
	  echo "$$tracked" | while IFS= read -r f; do \
	    [ -n "$$f" ] || continue; \
	    n="$$(basename "$$f")"; \
	    [ -x "$$dest/$$n" ] || { echo "install failed: $$n is not executable"; exit 1; }; \
	    cmp -s "$$f" "$$dest/$$n" || { echo "install failed: $$n differs from its source"; exit 1; }; \
	  done; \
	  printf '%s\n' "$$src" > "$$dest/.installed-from"; \
	  echo "hooks armed: core.hooksPath = $$dest"; \
	  echo "  installed from $$src"; \
	  echo "$$tracked" | sed 's|.*/|  |'; \
	  untracked="$$(git ls-files --others --exclude-standard scripts/githooks)"; \
	  if [ -n "$$untracked" ]; then \
	    echo "  NOT installed — untracked, so nobody has reviewed them:"; \
	    echo "$$untracked" | sed 's|.*/|    |'; \
	  fi; \
	  echo "  re-run \`make hooks\` after any change under scripts/githooks — the copy does not follow it"


# python3, not $(PYTHON): a step-away tool that needs `make venv` first is not a step-away
# tool. Exits non-zero if any declared source is missing — it prints MISSING rather than
# quietly printing less, because the shorter version is the one you would believe.
status:
	@python3 scripts/status.py

# The map, rendered. Stdlib only and no project import, same as `status` — see the module
# docstring for why the raw file could not be the only way to read it.
map:
	@python3 scripts/map-view.py $(ARGS)

# THE COMPOSITION OF `check` BELOW, AS DATA WITH A READER. The recipe is eleven lines of
# `$(MAKE)`, and everything a session needs to know about them — which are on the commit path,
# which write, which need node, which can never fail — was argued in ~120 lines of comment
# spread through this file and readable only by opening it. `make help`'s one-line summary was
# the compressed version and it WAS WRONG: it said `harness + docs-audit + the self-tests +
# lint + typecheck` while five more targets ran, and had said so since those five landed.
#
# scripts/checks.py is a PARALLEL DECLARATION and deliberately does not drive the recipe.
# A registry that drove the suite could silently stop running a check; this one can only lie,
# and `make docs-audit` has three rows that catch it lying — `check registry` against the
# recipe, `check census` against the published prose, and `commit path writes`, which asserts
# D18 mechanically by refusing any writing check on the commit path.
#
# python3, not $(PYTHON): a step-away tool that needs `make venv` first is not a step-away
# tool. Same rule as `status`, `map` and `docs-audit`.
explain:
	@python3 scripts/checks.py $(ARGS)


harness:
	$(VENV_GUARD)
	@$(PYTHON) harness/run.py

# Exit 1 is a provably wrong reference and fails. Exit 2 is the coupling question — it
# prints and passes, here for the same reason the pre-commit hook lets it through: a
# question that can fail your build is a question you learn to route around. See D16.
# python3, not $(PYTHON): the script is stdlib-only so it must not need `make venv`.
docs-audit:
	@python3 scripts/docs-audit.py; \
	status=$$?; \
	if [ $$status -eq 1 ]; then exit 1; fi

# THE ONE GENERATOR IN THIS REPO, AND IT GATES NOTHING (D18, amended 2026-09-17). It adds
# the decision ids a file cites to that file's `governed_by` in docs/map.py — the answer
# `make docs-audit`'s `repo map` row already computes to decide the commit. It imports that
# row's own `cited_decisions()` rather than reimplementing it, so the two cannot disagree.
#
# NOT A PREREQUISITE OF ANYTHING, and never wired to a hook. That is the whole of D18: a
# generator on the commit path regenerates, the audit passes, and the doc now says whatever
# the code said. Run it when the row refuses you. The row is still what says you are right.
#
# ITS SELF-TEST IS NOT IN `make check`, on `catalog-index-selftest`'s precedent. What this
# writes is verified by a gate that runs on every commit already, so a second reader on the
# commit path would be proving the same thing one step further from the damage.
map-fix:
	@python3 scripts/map-fix.py $(ARGS)

map-fix-selftest:
	@python3 scripts/map-fix.py --selftest

# WHICH COMPONENT RENDERS THE THING, AND WHAT SELECTS IT. A RENDERER — it writes nothing and
# gates nothing, so D18 does not reach it, the same standing `make map` has.
#
# Written after a fix to `#/orders` was briefed against `CopyMapView` when the screen the
# owner looks at renders `WalkGroups`, because `hidePicks` suppresses the first. Three lines,
# 1,000 apart, in a 4,605-line file. The work was correct and invisible and it cost a round.
# A split would not have fixed it: which prop selects which component is a RELATIONSHIP, not
# a location.
orient:
	@python3 scripts/orient.py $(ARGS)

orient-selftest:
	@python3 scripts/orient.py --selftest

# Deliberately NOT a prerequisite of `check`, and never wired to a hook: every tree after
# the audit landed is clean because the hook blocked anything else, so a zero here cannot
# tell silent prevention from dead weight. It informs a retirement argument; it never makes
# one. Nonzero means the tool failed, never that a finding was found. See D18 and the
# script's own header.
audit-history:
	@python3 scripts/audit-history.py

# Not prerequisites: make is free to reorder those, and with -j it runs them in parallel.
# A check suite has to run in a known order and stop at the first failure.
# THE SELF-TEST RUNS HERE AND NOT IN THE GIT HOOK, and the split is D18's rather than a
# preference: `--self-test` is the one mode of docs-audit.py that WRITES (into a temporary
# directory it makes and destroys), and nothing that writes may run on the path that decides
# whether a commit proceeds. `make check` is invoked by a person on demand, so it is not that
# path — which makes it the right home for the one check that verifies the checker.
#
# It sat red and unnoticed until 2026-08-24 because nothing ran it at all: a stale fixture in
# the `tested_by reach` case had stopped being false, and `make docs-audit` was green
# throughout. A checker whose own self-test nobody runs is a checker nobody has watched fail.
check:
	@$(MAKE) --no-print-directory harness
	@$(MAKE) --no-print-directory docs-audit
	@$(MAKE) --no-print-directory claim-stale
	@$(MAKE) --no-print-directory revert-guard
	@$(MAKE) --no-print-directory port-agreement
	@$(MAKE) --no-print-directory set-hint-agreement
	@$(MAKE) --no-print-directory readiness-agreement
	@$(MAKE) --no-print-directory screen-freshness
	@$(MAKE) --no-print-directory screen-freshness-selftest
	@$(MAKE) --no-print-directory sigil-check
	@$(MAKE) --no-print-directory css-var-check
	@$(MAKE) --no-print-directory css-var-check-selftest
	@$(MAKE) --no-print-directory ignore-check
	@$(MAKE) --no-print-directory lint
	@$(MAKE) --no-print-directory vale
	@$(MAKE) --no-print-directory typecheck
	@$(MAKE) --no-print-directory audit-self-test
	@$(MAKE) --no-print-directory mutate-anchors
	@$(MAKE) --no-print-directory githooks-selftest
	@$(MAKE) --no-print-directory merge-selftest
	@$(MAKE) --no-print-directory revert-selftest
	@$(MAKE) --no-print-directory claim-selftest
	@$(MAKE) --no-print-directory decisions-selftest
	@$(MAKE) --no-print-directory debts-selftest
	@$(MAKE) --no-print-directory gates-selftest
	@$(MAKE) --no-print-directory submission-selftest
	@$(MAKE) --no-print-directory cid-selftest
	@$(MAKE) --no-print-directory pricearchive-selftest
	@$(MAKE) --no-print-directory readings-selftest
	@$(MAKE) --no-print-directory janitor-selftest
	@$(MAKE) --no-print-directory reap-selftest
	@$(MAKE) --no-print-directory silent-write-selftest
	@$(MAKE) --no-print-directory guard-shell-selftest
	@$(MAKE) --no-print-directory coordinator-selftest
	@$(MAKE) --no-print-directory suite-lock-selftest
	@$(MAKE) --no-print-directory browser-scope-selftest
	@$(MAKE) --no-print-directory serve-selftest
	@$(MAKE) --no-print-directory sync-selftest
	@$(MAKE) --no-print-directory verdict-selftest
	@$(MAKE) --no-print-directory js-breakpoints-selftest
	@$(MAKE) --no-print-directory subagent-override-selftest
	@$(MAKE) --no-print-directory guard-scope-selftest

# WHAT A MACHINE CAN PROVE ON A FRESH CLONE, WHICH IS NOT EVERYTHING `make check` PROVES.
# This exists because nothing ever re-ran the gate: `make check` failed in every fresh checkout
# for 121 commits — `tsc` needed `app/demo/bundle.json`, which `make demo-record` writes and
# nothing tracks — and no one noticed, because the only trees it was run in had made a recording.
# A gate with no re-checker is the same defect D111 records one register up.
#
# ONE ROW IS ABSENT AND IT IS NOT AN OVERSIGHT:
#   vale     needs a binary that is not on the runner, and it never gated a commit anyway.
#
# THE HARNESS IS HERE AS OF 2026-09-06 AND WAS NOT WHEN THIS TARGET WAS WRITTEN. It was
# excluded because T1 needed `harness/.cache` (96K) and `harness/images` (133M), both
# untracked, so a fresh runner could only fail it. D112 moved the LABELS out of the image
# mirror — 40K of ground truth that had been filed with the pixels for the pixels' reason —
# and gave the scorer a fingerprint, so an unmoved measurement is asserted rather than
# re-derived. All nine tests now pass on a clone with no images and no cache, measured.
#
# Everything below answers from the tree alone, which is exactly what a re-checker can own.
# IT IS A SUBSET AND CAN DRIFT FROM `check`. Kept adjacent to it deliberately, so the two are
# read together; `make explain` still describes the full suite and this list adds no rows to it.
ci-check:
	@$(MAKE) --no-print-directory harness
	@$(MAKE) --no-print-directory docs-audit
	@$(MAKE) --no-print-directory audit-self-test
	@$(MAKE) --no-print-directory mutate-anchors
	@$(MAKE) --no-print-directory githooks-selftest
	@$(MAKE) --no-print-directory merge-selftest
	@$(MAKE) --no-print-directory revert-selftest
	@$(MAKE) --no-print-directory claim-selftest
	@$(MAKE) --no-print-directory claim-stale
	@$(MAKE) --no-print-directory decisions-selftest
	@$(MAKE) --no-print-directory debts-selftest
	@$(MAKE) --no-print-directory gates-selftest
	@$(MAKE) --no-print-directory submission-selftest
	@$(MAKE) --no-print-directory cid-selftest
	@$(MAKE) --no-print-directory pricearchive-selftest
	@$(MAKE) --no-print-directory readings-selftest
	@$(MAKE) --no-print-directory revert-guard
	@$(MAKE) --no-print-directory janitor-selftest
	@$(MAKE) --no-print-directory reap-selftest
	@$(MAKE) --no-print-directory silent-write-selftest
	@$(MAKE) --no-print-directory guard-shell-selftest
	@$(MAKE) --no-print-directory coordinator-selftest
	@$(MAKE) --no-print-directory suite-lock-selftest
	@$(MAKE) --no-print-directory browser-scope-selftest
	@$(MAKE) --no-print-directory serve-selftest
	@$(MAKE) --no-print-directory sync-selftest
	@$(MAKE) --no-print-directory verdict-selftest
	@$(MAKE) --no-print-directory js-breakpoints-selftest
	@$(MAKE) --no-print-directory subagent-override-selftest
	@$(MAKE) --no-print-directory guard-scope-selftest
	@$(MAKE) --no-print-directory port-agreement
	@$(MAKE) --no-print-directory set-hint-agreement
	@$(MAKE) --no-print-directory readiness-agreement
	@$(MAKE) --no-print-directory screen-freshness
	@$(MAKE) --no-print-directory screen-freshness-selftest
	@$(MAKE) --no-print-directory sigil-check
	@$(MAKE) --no-print-directory css-var-check
	@$(MAKE) --no-print-directory css-var-check-selftest
	@$(MAKE) --no-print-directory ignore-check
	@$(MAKE) --no-print-directory lint
	@$(MAKE) --no-print-directory typecheck

# The other half of D47: every path a worktree provisions is ignored whatever kind of thing is
# at it. In `check` and never in the git hook — D18 forbids a commit gate that depends on local
# state, and this asks about provisioning, so a fresh clone would fail a commit over nothing.
ignore-check:
	@sh scripts/ignore-check.sh

# THE VERDICT REPORTER, PROVED BY RUNNING IT. `make docs-audit`'s `verdict file` row
# reconciles the four files that NAME `.serve/design-check.json`; it is static and cannot
# say the reporter still WORKS. This runs the real reporter file — copied into a throwaway
# tree so it writes there and never over a verdict a session is about to read — against one
# passing and one failing spec, and asserts the verdict, the counts, the failing title and
# its location, and that the error text carries no ANSI and no NUL bytes.
#
# NO BROWSER AND NO DEV SERVER, which is why it is here and design-check is not: a test that
# never touches the `page` fixture launches nothing, and the throwaway config has no
# `webServer`. Measured at ~1s, and measured again with PLAYWRIGHT_BROWSERS_PATH pointed at
# an empty directory — so it holds on the runner, which installs no browser binaries.
#
# In `check` and `ci-check`, never in the git hook: D18, it writes.
verdict-selftest:
	$(NPM_GUARD)
	@if python3 scripts/guard-scope.py classify --target verdict-selftest --base origin/main; then \
		python3 scripts/verdict-selftest.py; \
	else \
		echo "verdict-selftest: SKIPPED — nothing in this branch reaches app/design-check-reporter.ts. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# python3, not $(PYTHON): the script is stdlib-only so it must not need `make venv`.
audit-self-test:
	@if python3 scripts/guard-scope.py classify --target audit-self-test --base origin/main; then \
		python3 scripts/docs-audit.py --self-test; \
	else \
		echo "audit-self-test: SKIPPED — this branch does not touch scripts/docs-audit.py. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# D92 — a bare `#` on an owner-side screen is D58's COUNT, and three renderers spelled the
# store key the same way. ON THE COMMIT PATH, unlike its neighbours here: it writes nothing,
# needs no venv and no node, and reads only tracked source, so none of D18's reasons apply.
# Its own self-test runs with it — cheap enough (27 cases over strings) that splitting them
# into a second target would cost more to explain than to run.
sigil-check:
	@python3 scripts/sigil-check.py --self-test
	@python3 scripts/sigil-check.py

# A `var(--x)` WITH NO FALLBACK, WHERE `--x` IS DEFINED NOWHERE (2026-09-20 review, Tier 1
# item 1): the whole declaration drops silently, and five of these accumulated across four
# screens before anyone noticed. Split into a check and its own `-selftest`, split from
# `sigil-check`'s own precedent of bundling both: this checker's self-test is fixture trees
# (a whole synthetic stylesheet and TSX file per case), not single-line strings, and the
# split keeps `make css-var-check`'s own output to the real finding rather than twelve lines
# of fixture cases first. In `make check`, not the git hook: it writes nothing, needs no
# venv and no node, same as `sigil-check` — but it is not (yet) armed in
# scripts/githooks/pre-commit, so it is not claimed here as being on that path.
css-var-check:
	@python3 scripts/css-var-check.py

# THE GUARD IS NOT TRUSTED UNTIL IT HAS GONE RED ON THE DEFECT IT GUARDS: a fixture with a
# genuinely undefined `var()`, one with a fallback, and one defined only from TSX
# (`style={{ '--x': ... }}`, a bracket computed key, and `.setProperty(`), plus the two real
# misspellings this check was built to catch. In `check` and `ci-check`, beside
# `css-var-check` itself.
css-var-check-selftest:
	@python3 scripts/css-var-check.py --self-test

# HERE AND NOT IN THE GIT HOOK, for the reason stated above `check` and for a second one of
# its own. D18 is the first: this writes — a bare repo, a clone, commits, pushes — and nothing
# that writes may run on the path that decides whether a commit proceeds. The second is that
# it exercises the guard by VIOLATING it, so a version wired into the commit path would be
# refusing its own commits.
githooks-selftest:
	@if python3 scripts/guard-scope.py classify --target githooks-selftest --base origin/main; then \
		bash scripts/githooks-selftest.sh; \
	else \
		echo "githooks-selftest: SKIPPED — nothing in this branch reaches scripts/githooks/. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# THE HALF NOBODY CAN REMEMBER, DONE BY A MACHINE. D42 settles that a session performs both
# halves of a merge on the owner's word — `gh pr merge`, then the local fast-forward — and the
# local half has TWO correct forms chosen by whether any worktree holds main. Pick wrong and it
# does not error: `git -C <main tree> pull --ff-only` fast-forwards whatever branch that tree is
# standing on, moves no protected ref, and trips no hook.
#
# THIS DOES NOT REOPEN D42'S "no make target that picks for you". That rejection is about
# WHETHER TO MERGE, which stays the owner's: a bare `make merge` refuses, `ARGS=<n>` is a free
# preview that presses nothing, and only `ARGS="<n> --confirm"` acts. What is automated is the
# state lookup. See D42's amendment.
#
# It never sets PKMNSCAN_MAIN and no refusal it prints suggests it — a session typing that
# variable is doing something else (D42).
merge:
	@$(PYTHON) scripts/merge-pr.py $(ARGS)

# HERE AND NOT IN THE GIT HOOK, for githooks-selftest's two reasons exactly: D18, because it
# writes a bare repo, a clone and a linked worktree; and because it drives the thing that moves
# main, so a version on the commit path would be exercising that against the real one.
merge-selftest:
	@if python3 scripts/guard-scope.py classify --target merge-selftest --base origin/main; then \
		bash scripts/merge-selftest.sh; \
	else \
		echo "merge-selftest: SKIPPED — nothing in this branch reaches scripts/merge-pr.py. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# A MERGE CAN UNDO A RULING WITHOUT ANYBODY WRITING A LINE (D133). PR #221 landed on main from
# a tree that still held the pre-#218 copy of ten files, its message about `--cap` wording, and
# D119's deletion came back with every guard that had asserted it — because every guard lived
# in the files that came back. `make check` was green on both sides. This asks the one question
# nothing on the commit path asked: does what this branch would land on origin/main put a file
# back the way main had it BEFORE a commit main already carries, in a file no commit here names?
# The clean merge's tree against origin/main is the diff it reads, so a branch merged-with-
# keep-ours and squashed reads the same as the PR GitHub would show.
#
# ON THE COMMIT PATH TWICE: here, and in pre-push (scripts/githooks/pre-push runs the same
# script on the branch being pushed), and once more as its own job in .github/workflows/check.yml
# so it shows as a check on the PR. It writes nothing and needs only python3 and git. Absent
# `origin/main` — a fixture clone, a throwaway — it allows and says so, which is the same
# fail-open rule the two D42 hooks state. `PKMNSCAN_REVERT=off` runs nothing, printed in every
# refusal. `scripts/revert-audit.py history` is the same engine walked over main's whole
# first-parent line, which is how the 2026-09-11 audit was taken.
revert-guard:
	@python3 scripts/revert-audit.py branch

# The guard, proved by violating it: PR #218's deletion and PR #221's keep-ours squash rebuilt
# in a throwaway repository with its own origin, then a clean branch, a declared restoration,
# a partial one and the escape hatch. In `check` and `ci-check`, never in the git hook — D18,
# it writes a repository under `mktemp -d`; and githooks-selftest's second reason, it drives
# the guard by defeating it.
revert-selftest:
	@if python3 scripts/guard-scope.py classify --target revert-selftest --base origin/main; then \
		python3 scripts/revert-audit.py selftest; \
	else \
		echo "revert-selftest: SKIPPED — this branch does not touch scripts/revert-audit.py. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# A BRANCH DOES NOT TAKE A DECISION NUMBER (D-merge-time-ids). It writes a slug and this
# allocates the number against main INSIDE `make merge`, which is the first moment the
# allocation's only input — what main has taken — is knowable. Reach for this by hand only to
# see what a merge would claim; the merge runs it for you.
claim-ids:
	@python3 scripts/claim-ids.py $(ARGS)

# THE OTHER HALF OF THE CLAIM, AND IT IS NOT ABOUT SLUGS (D140, amended 2026-09-11). Once a
# branch has claimed there is no slug left and `make claim-ids` says `nothing to do` — a true
# statement about slugs and an incomplete one about safety, because main can take that number
# afterwards and nothing looks again. It happened TWICE on 2026-09-11, both times caught by a
# person reading PR titles.
#
# IT WRITES NOTHING, so unlike `claim-ids` it may gate: it is in `check` and in `ci-check`, and
# `make merge` asks for it before every merge, where the fetch above it makes the answer
# current. IT READS THE LOCAL `origin/main` AND NEVER THE NETWORK — D140 rejects reading open
# pull requests deliberately, and this needs neither, because the case that bites is the one
# where the other branch has already LANDED. A clone with no `origin/main` is ALLOWED and says
# so, which is `revert-guard`'s call for `revert-guard`'s reason.
#
# IT CAN ONLY UNDER-REPORT AGAINST A STALE REF, never over-report, which is what makes it safe
# on the commit-adjacent path: a `make check` whose `origin/main` is a day old misses a
# collision it would have caught, and invents none. `decision index` is still the backstop.
claim-stale:
	@python3 scripts/claim-ids.py --stale

# The claimer, proved where it can actually be wrong: a throwaway repository in which main
# moves underneath the branch. In `check`, never in the git hook — it writes (D18).
claim-selftest:
	@if python3 scripts/guard-scope.py classify --target claim-selftest --base origin/main; then \
		python3 scripts/claim-selftest.py; \
	else \
		echo "claim-selftest: SKIPPED — nothing in this branch reaches scripts/claim-ids.py. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# THE CORPUS IS COMPLETE AND STILL ROUND-TRIPS. `docs/decisions/` is one file per entry and
# was one 1.4 MB document; this asserts the set is whole — every file the manifest names is
# present, every file present is named, no id is in two files, and the reassembly matches the
# digest recorded when the split was made. Stdlib only and it writes nothing, so it gates.
#
# WHAT IT DOES NOT ASSERT is that the entries are unedited: editing one is the normal way
# this corpus changes, and `--rehash` re-records the digest when that is deliberate. The
# one-time claim that the SPLIT itself lost nothing is `--verify` against the pre-split file.
decisions-selftest:
	@python3 scripts/split-decisions.py --selftest

# THE DEBTS TWIN OF decisions-selftest, same argument, same reason it gates rather than
# writes: `docs/debts/` is one file per finding and was one 174 KB document; this asserts
# the set is whole and the reassembly matches the digest recorded when the split was made.
debts-selftest:
	@python3 scripts/split-debts.py --selftest
# THE GATES CORPUS IS COMPLETE AND STILL ROUND-TRIPS — `decisions-selftest`'s own shape, over
# `docs/gates/` (Lane D, 2026-09-16). Three kind folders (contract/, runs/, steps/), one
# manifest, and this asserts the set is whole: every file the manifest names is present,
# every file present is named, no step id is in both the shipped and open lists, and the
# corpus meets its pinned non-vacuity floor (>=9 contract entries, >=5 run entries, >=15
# shipped steps) so a broken reader over a renamed heading fails loud rather than reporting a
# clean, empty corpus. Stdlib only and it writes nothing, so it gates.
gates-selftest:
	@python3 scripts/split-gates.py --selftest

# BUILD-ORDER STEP 9, PIECE 1 (D15): re-clone `PokemonTCG/pokemon-tcg-data` and refresh the
# committed snapshot at `vendor/pokemon-tcg-data/`, recording the upstream commit SHA in
# `SNAPSHOT.json`. WRITES, so it never gates a commit (D18) — run on the owner's word,
# monthly per D15's own cadence. `ARGS=--dry-run` clones and reports the diff without touching
# the tracked copy.
catalog-refresh:
	@python3 scripts/catalog-refresh.py $(ARGS)

# BUILD-ORDER STEP 9, PIECE 2: build `vendor/pokemon-tcg-data/catalog.sqlite` from the vendored
# snapshot — cards join to sets BY FILENAME, because `printedTotal` lives only in
# `sets/en.json`. A generator, gitignored output, never on the commit path (D18).
# `pipeline/catalog.py` is the read-only reader over what this writes.
catalog-index:
	@python3 scripts/catalog-index.py $(ARGS)

# THAT BUILDER AND `pipeline/catalog.py`, PROVED AGAINST A THROWAWAY TWO-SET FIXTURE — never
# the real 26 MB snapshot, so this is fast enough for `make check`. Every case failed before
# `scripts/catalog-index.py` and `pipeline/catalog.py` existed: no index to build, no reader
# to open one. Writes only a temp directory, so it gates like any other selftest.
catalog-index-selftest:
	@python3 scripts/catalog-index-selftest.py

# BUILD-ORDER STEP 9, PIECE 3, DRY RUN ONLY AS SHIPPED: the manifest is derived from the
# vendored snapshot (no network) and the downloader is resumable and rate-limited, but
# nothing here has ever filled the mirror for real on this checkout — see the decision entry
# this step wrote. `ARGS=--dry-run` HEAD-samples up to 200 images and prints the manifest's
# file count and the byte total extrapolated from the sample, writing nothing under the
# mirror destination (`PKMNSCAN_IMAGE_MIRROR`, default `harness/images/`, D15). Bare
# `make catalog-mirror` fills it for real, for whenever that becomes the owner's call.
catalog-mirror:
	@python3 scripts/catalog-image-mirror.py $(ARGS)

# HERE BECAUSE TWO LANGUAGES HOLD ONE ALGORITHM AND NEITHER CAN IMPORT THE OTHER (D43).
# Python serves the capture port, TypeScript addresses it, and a disagreement is silent and
# total — the app asks for a port nothing is listening on, or one ANOTHER tree is listening
# on, which is the defect the whole decision exists to remove. It runs node, so it is not on
# the commit path: the git hook runs bare, and a check that needs a toolchain would fail
# on a machine that has none rather than on a defect.
port-agreement:
	@python3 scripts/port-agreement.py

# THE SAME SHAPE ONE DECISION OVER (D65): the hint matcher is in Python because the export
# fetch resolves it, and in TypeScript because the capture screen has to tell the operator,
# at the rig, whether what they are typing will resolve. A disagreement is worse than the
# silence it replaced — a verdict gets trusted. node again, so it is off the commit path for
# port-agreement's reason: the git hook runs a bare python3.
set-hint-agreement:
	@python3 scripts/set-hint-agreement.py

readiness-agreement:
	@python3 scripts/readiness-agreement.py

mutate-anchors:
	@python3 scripts/mutate-guards.py --verify-anchors

# THE SLOW HALF, AND DELIBERATELY OFF `check`: 190s against `mutate-anchors`'s 0.03s,
# because it runs five guards' whole selftests once per mutation. The anchor check is what
# gates, and it is the half that catches ROT — a guard reworded past its own mutation is a
# corpus that proves nothing while still reporting a count.
mutate-guards:
	@python3 scripts/mutate-guards.py

# Every server WRITE in app/src has a way back — a re-read, an invalidation signal, or a
# reason in the code why none is owed. IN `check` AND NEVER IN THE GIT HOOK, and the reason is
# port-agreement's exactly: it runs node, and the pre-commit hook runs a bare python3 with
# nothing installed, so a check that needs a toolchain would fail on a machine that has none
# rather than on a defect. The NPM_GUARD is here because it reads the TypeScript compiler out
# of app/node_modules rather than shipping a second parser.
#
# It finds NOTHING on the tree it was written against — all 38 call sites were already covered
# — so this is a regression guard and not a bug report. What it stops is write number 39
# skipping the idiom, which is a thing no test and no type would have caught.
screen-freshness:
	$(NPM_GUARD)
	@node scripts/screen-freshness.mjs

# THE GUARD'S OWN SELFTEST, AND IT SAT ON NO TARGET UNTIL NOW. `screen-freshness.mjs`
# carries a `--self-test` that exercises its classifier against pinned cases in both
# directions, and NOTHING RAN IT: `make check` called the plain form, which passed and then
# printed "classification has moved since it was recorded — run --self-test". So the check
# told the operator to run the check that was red, and nothing made them — a rule with no
# reader, which is the thing this repo has now made a hard rule about.
#
# IT WAS RED ON MAIN FOR AN UNKNOWN STRETCH — `2 FAILED`, from 17 exports missing from its
# RECORDED table — and gating it while it was red would have broken `make check` for every
# session, which is why it waited. PR #307 filled the table; it passes today, so the gate
# is safe now and it is the cheapest one outstanding.
#
# Needs node, so it is in `check` and never in the git hook — `screen-freshness`' own
# reason, one line up.
screen-freshness-selftest:
	$(NPM_GUARD)
	@if python3 scripts/guard-scope.py classify --target screen-freshness-selftest --base origin/main; then \
		node scripts/screen-freshness.mjs --self-test; \
	else \
		echo "screen-freshness-selftest: SKIPPED — this branch does not touch scripts/screen-freshness.mjs. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# NOT IN `check`, AND NOT IN THE GIT HOOK. It is the one target here that can DELETE a file,
# so D18's rule applies at its strongest: nothing that writes may run on the path that decides
# whether a commit proceeds. It is also not a defect to have conflict copies lying around —
# the pre-commit hook already refuses to COMMIT one — so failing `check` over them would gate
# a tidy-up on a condition the owner's filesystem creates on its own schedule.
#
# `make status` reports the count, which is where a thing you should know but need not act on
# belongs. Deleting is opt-in: `make icloud-sweep ARGS=--delete`.
icloud-sweep:
	@python3 scripts/icloud-sweep.py $(ARGS)

# NOT IN `check`, AND NOT IN THE GIT HOOK, for icloud-sweep's reason exactly: these two are the
# only targets here that can delete a file, and D18 forbids a writer on the path that decides
# whether a commit proceeds. Nor is leftover exhaust a defect to fail a commit over — it is a
# condition the owner's own sessions create on their own schedule.
#
# TIER 1 IS REAPED WITHOUT ASKING AND TIER 2 IS NOT. A process whose own script has been deleted
# cannot be live; a worktree that merely LOOKS idle can be, and was, twice, on the day this was
# written. `make status` reports the count. Reaping tier 2 is opt-in: `make janitor ARGS=--confirm`.
#
# "WITHOUT ASKING" MEANS WITHOUT A PROMPT, NOT WITHOUT BEING ASKED, AND THAT DISTINCTION WAS
# LOST UNTIL 2026-09-19. A BARE `make janitor` previews BOTH tiers and presses nothing, which
# is what janitor.py's own header and `status.py:janitor()` have always said and what the code
# did not do — the bare run SIGTERMed orphans, ran `git worktree prune` and deleted husks, at
# the head of every session, because `make status` runs it. Tier 1 is still pressed with no
# prompt by whatever names it: `--tier1`, which `session-teardown.sh` runs at every session
# end, and `--confirm`.
# EXIT 1 IS NOT A FAILURE HERE, AND THAT DIFFERS FROM icloud-sweep ON PURPOSE. The sweep exits 1
# when something is waiting on `--confirm`, which for a preview is the ORDINARY answer rather
# than a rare finding — a conflict copy is unusual, a reapable worktree is Tuesday. So `make`
# swallows 1 and nothing else: a crash, a refusal to run, any code above 1 still fails loudly.
# The code itself is kept because a scheduled caller wants to know whether there is work.
janitor:
	@python3 scripts/janitor.py $(ARGS); s=$$?; [ $$s -le 1 ] || exit $$s

# THE SWEEP ON A SCHEDULE, because the two events that run it are both known to miss. A tree
# abandoned by a session that died is removed by nobody, so `WorktreeRemove` never fires for
# it, and `.claude/settings.json` already calls `SessionEnd` unreliable at app quit and machine
# sleep. Writes to ~/Library and so is on no hook and in no check, exactly as `launch-agent` is
# (D18). Main checkout only: a plist naming a worktree outlives the worktree.
janitor-agent:
	@python3 scripts/janitor.py --install-agent $(ARGS)

# In `check`, never in the git hook: it writes a temp tree and signals the processes it spawned
# there, which is D18's line. Same standing as merge-selftest and githooks-selftest.
janitor-selftest:
	@if python3 scripts/guard-scope.py classify --target janitor-selftest --base origin/main; then \
		bash scripts/janitor-selftest.sh; \
	else \
		echo "janitor-selftest: SKIPPED — nothing in this branch reaches scripts/janitor.py. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# THE SUPERVISOR'S BUILD JOB (D138), against a throwaway tree with a stub `vite build`. Same
# standing and the same reason as the three self-tests around it: it starts and stops real
# supervisors and swaps real directories, so it is in `check` and never in the git hook.
# No node — the stub is a shell script — so it runs anywhere the rest of `check` does.
# PATH GATED SINCE 2026-09-17, AND IT IS THE ONLY TARGET IN THIS FILE THAT IS.
# It is 70.1s, 37% of `make check`'s 187.5, and it copies this checkout into a throwaway tree
# with a STUB `app/` — so no screen change can reach it. `scripts/serve-scope.py` derives what
# it reads from the self-test's own `CARRY` and answers 0 to run, 3 to skip. It fails OPEN:
# no merge-base, an unreadable diff and an EMPTY diff all run it.
#
# THE OWNER RULED THIS ONE IN AND PATH GATING IN GENERAL OUT (docs/specs/verification-cost.md
# §9). Nine targets in `make check` cost under a tenth of a second each, so a scope list per
# target would cost more to maintain than it saves. A SECOND gated target needs the owner's
# word again — do not read this recipe as a pattern to copy.
#
# PKMNSCAN_SERVE_SCOPE=off runs it regardless, and every skip prints that.
serve-selftest:
	@if python3 scripts/serve-scope.py classify --base origin/main; then \
		$(PYTHON) scripts/serve-selftest.py; \
	else \
		echo "serve-selftest: SKIPPED — nothing in this branch reaches what it reads."; \
	fi

serve-scope:
	@python3 scripts/serve-scope.py $(ARGS)

serve-scope-selftest:
	@python3 scripts/serve-scope.py selftest

guard-scope:
	@python3 scripts/guard-scope.py $(ARGS)

guard-scope-selftest:
	@python3 scripts/guard-scope.py selftest

# THE PRIMARY CHECKOUT'S SELF-SYNC, proved by violating it in throwaway clones. It switches
# branches and moves `refs/heads/main`, which is exactly why it may never be pointed at this
# clone: the subject of a sync is the PRIMARY tree, and on this machine that is the owner's live
# rig. In `check` and never in the git hook — D18, the same standing as merge-selftest.
sync-selftest:
	@if python3 scripts/guard-scope.py classify --target sync-selftest --base origin/main; then \
		$(PYTHON) scripts/sync-selftest.py; \
	else \
		echo "sync-selftest: SKIPPED — nothing in this branch reaches scripts/primary_sync.py. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# WHAT THIS SESSION STARTED, AND NOTHING ELSE. `pkill -f` and `lsof -ti tcp:PORT` are both
# machine-wide, and both were used to clean up a session's own dev servers on 2026-09-10: the
# first also matched the owner's live capture server over their real store, the second also
# matched the desktop app's network helper, which was merely a CLIENT of the port. This target
# is the right thing to reach for instead — it signals only what is running under this checkout
# and PRINTS what it refused, so the difference is visible rather than silent.
#
# IT PREVIEWS AND PRESSES NOTHING WITHOUT `--confirm`, and exit 1 there means work is waiting —
# `make janitor`'s bargain, swallowed for the same reason: a preview finding something is the
# ORDINARY answer, not a failure. A crash or a refusal above 1 still fails loudly.
#
# NOT IN `make check` and not in the git hook: it signals processes, which is D18's line. Its
# self-test is in `check`, and touches only what it spawned under `mktemp -d`. D127.
reap:
	@python3 scripts/reap.py $(ARGS); s=$$?; [ $$s -le 1 ] || exit $$s

# In `check`, never in the git hook: it writes a temp tree and signals the processes it started
# there. Same standing as janitor-selftest. It cannot be run against this repo — the process the
# guard exists to protect is the owner's live server, and "point it at that and see" is the
# incident rather than the test — so every case runs against a throwaway checkout and a
# throwaway sibling standing in for everywhere-else. Mutation-tested: twenty-two arms, all caught.
# THAT COUNT IS A HAND SWEEP AND STAYS. `make mutate-guards` now re-runs a MECHANIZED SUBSET of
# it — 3 anchored arms here, one per rule — and `make mutate-anchors` fails the moment one of
# those anchors stops matching. The hand count is the larger history; the anchored corpus is the
# part a machine can repeat.
# Its fixture spawned every subject by an ABSOLUTE path until 2026-09-12, which is why thirteen
# arms could not see the bare sweep's blind spot — `spawn_relative` is the subject it lacked.
reap-selftest:
	@if python3 scripts/guard-scope.py classify --target reap-selftest --base origin/main; then \
		bash scripts/reap-selftest.sh; \
	else \
		echo "reap-selftest: SKIPPED — nothing in this branch reaches scripts/reap.py. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

.PHONY: reap reap-selftest

# THE ONE BINDING THAT PROTECTS A DOLLAR, PROVED BY VIOLATING IT (D-a-claim-on-the-cards).
# `store/submissions.py` refuses a second `identify` press over cards a live run has already
# claimed, and that refusal cannot be exercised against the real thing: the press it stops
# costs money at Anthropic, so "run two presses at the operator's store and read the invoice"
# is the incident rather than the test. Every case runs against a throwaway store under
# `mktemp -d` and the concurrent ones are real separate processes racing a real flock.
#
# IT REPRODUCES THE BUG BEFORE IT PROVES THE FIX, which is reap-selftest's rule: one case runs
# the children in the check-then-claim order anybody writes first and watches BOTH presses buy
# the same card. Without that, the case beside it proves only that something happened.
#
# In `check`, never in the git hook: D18 — it writes a temp tree and it signals processes.
# Same standing as janitor-selftest and reap-selftest. Mutation-tested: sixteen arms, all caught — two of them over its OWN floor against
# examining nothing, which is the shape `Report.render` printing `ok` for an empty findings
# list has on this side of the fence.
submission-selftest:
	@if python3 scripts/guard-scope.py classify --target submission-selftest --base origin/main; then \
		$(PYTHON) scripts/submission-selftest.py; \
	else \
		echo "submission-selftest: SKIPPED — this branch does not touch the claim table it proves. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# D172'S TWO TARGETS, AND ONLY ONE OF THEM IS IN `check`.
#
# `cid-selftest` answers from the tree alone: it builds its own store under a temp
# `PKMNSCAN_HOME` and draws its own photographs, so it is `submission-selftest`'s
# standing exactly — in `check`, never in the git hook, because it writes a temp tree
# and kills a process (D18).
#
# `cid-audit` reads the operator's 4.45 GB of real photographs, and `make check` answers
# from the tree alone — which is `make lan-check`'s reason, not a weaker one. It is its
# own target and `make status` reports when it has never been run against this store.
cid-selftest:
	@if python3 scripts/guard-scope.py classify --target cid-selftest --base origin/main; then \
		$(PYTHON) scripts/cid-selftest.py; \
	else \
		echo "cid-selftest: SKIPPED — this branch does not touch the card's stable name or the photograph store. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# THE SIXTEENTH GATED TARGET (D247, owner's word 2026-09-23 on the SKU-first price-history
# rebuild: "once it's done, it only needs to be tested when touched"). Answers from the
# tree alone, same standing as `cid-selftest` right above it: a throwaway store and real
# cached-export files under `mktemp`, never the operator's own store or their real
# `inventory/.exports/`. In `check`, never in the git hook, D18 — it writes a temp store.
pricearchive-selftest:
	@if python3 scripts/guard-scope.py classify --target pricearchive-selftest --base origin/main; then \
		$(PYTHON) scripts/pricearchive-selftest.py; \
	else \
		echo "pricearchive-selftest: SKIPPED — this branch does not touch price-history resolution or its callers. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

cid-audit:
	@./pkmnscan cards audit

# THE MARKET-READING TABLE, PROVED AGAINST AN INDEPENDENT REIMPLEMENTATION OF ITS OWN WALK
# (D-readings-table). `pipeline/readings.py:collect()` is compared to `golden()` — a second,
# separately-written transcription of the same two-source rule — over nine fixture shapes:
# empty, run-only, live-only, a disagreement won each direction by the clock, an unparseable
# live filename (must lose to everything, never fall back to an older readable file), adopt
# --write followed by the exact SELECT `_readings()` now performs, two adopts unchanged
# (idempotent), a new run landing between two adopts, and a run directory deleted between two
# (its SKU drops out — a cache refresh, never an accumulating ledger).
#
# IN `check`, NEVER IN THE GIT HOOK: it writes a temp store under `mktemp -d` (D18). Answers
# from the tree alone, so it is in `ci-check` too.
readings-selftest:
	@$(PYTHON) scripts/readings-selftest.py

.PHONY: submission-selftest readings-selftest

# A GIT WRITE MUST LEAVE A TRACE THE SESSION CAN READ. On 2026-09-12 a coordinator session
# reported work as landed that had not landed, twice, through `git commit -q -F - >/dev/null
# 2>&1 <<'EOF'`: the pre-commit hook refused, the refusal went to /dev/null, and a stale
# `git log --oneline -1` was read as the new commit. `scripts/silent-write-guard.py --hook` is
# a PreToolUse hook on Bash that refuses that command — it is not a target you run, and this
# self-test is what proves it.
#
# IN `check`, NEVER IN THE GIT HOOK: it writes a temp repository. Same standing as
# reap-selftest, and for the same D18 reason. It REPRODUCES the incident rather than asserting
# about it, and it pins every legitimate `2>/dev/null` as passing — `git rev-parse … 2>/dev/null`,
# `git fetch origin -q 2>/dev/null`, `git merge --abort 2>/dev/null` — because a guard that
# fires on those is worse than no guard. Mutation-tested: twenty-one arms, nineteen caught, and
# the two survivors are proved to be one requirement covered twice.
# `make mutate-guards` carries 7 anchored arms over this guard — a mechanized subset of the
# twenty-one, not a replacement for them.
silent-write-selftest:
	@if python3 scripts/guard-scope.py classify --target silent-write-selftest --base origin/main; then \
		bash scripts/silent-write-selftest.sh; \
	else \
		echo "silent-write-selftest: SKIPPED — nothing in this branch reaches scripts/silent-write-guard.py. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

.PHONY: silent-write-selftest

# EIGHT SHELL MISTAKES THIS REPO HAS ALREADY PAID FOR, refused before they run. Every one was a
# rule somebody had written down and a later session broke anyway — which is D171's ruling
# about what a rule IS, applied to eight more commands:
#
#   `git checkout <modified path>`     2026-09-06, ~240 lines of uncommitted work destroyed
#   a write outside this checkout      2026-09-06, ~1,500 lines into the owner's MAIN tree, on
#                                      main, hot-reloaded into their live capture server
#   `gh api -f k=v` with no method     2026-09-12, a GET silently POSTed and hung past a timeout
#   `ln -s` at an existing path        2026-08-29, harness/images/images and a 133 MB directory
#                                      renamed away by iCloud
#   a polling loop                     2026-09-12 twice: a `pgrep` waiter whose pattern is not
#                                      the process, and a backgrounded driver that ran 119
#                                      rounds over 3h58m across a compaction
#   `git push <remote> HEAD`           2026-09-12, a stray branch on origin while the real PR
#                                      branch went untouched, the tracked upstream being a
#                                      DIFFERENT name (D179, amended 2026-09-13)
#   a bare `git stash` / `pop`         the stash stack is shared by every worktree of this
#                                      clone, so a pop takes whatever another tree pushed
#   `git reset --hard`/`--merge`       over uncommitted tracked work
#
# `scripts/guard-shell.py --hook` is a PreToolUse hook on Bash and on Write|Edit — not a target
# you run — and this self-test is what proves it. FIVE OF THE EIGHT INCIDENTS ARE PERFORMED in a
# throwaway repository before the guard is asked about them, which is reap-selftest's standard;
# the false positives are RUN there too, because a case that is secretly a typo passes for the
# wrong reason. IN `check`, NEVER IN THE GIT HOOK: it writes a temp repository (D18).
guard-shell-selftest:
	@if python3 scripts/guard-scope.py classify --target guard-shell-selftest --base origin/main; then \
		bash scripts/guard-shell-selftest.sh; \
	else \
		echo "guard-shell-selftest: SKIPPED — nothing in this branch reaches scripts/guard-shell.py. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

.PHONY: guard-shell-selftest

# THE MERGE QUEUE, READ RATHER THAN REMEMBERED. The other half of 2026-09-12: a session relayed
# `#300 GREEN — merging` for several turns while nothing merged, because the line came from a
# driver's stdout and two copies of that driver were racing behind a `pgrep` waiter that matched
# its own command line. Every figure here is read from the repository or from GitHub at the
# moment you run it, and a PR's verdict is pinned to its HEAD SHA.
#
# NOT IN `check`, and `lan-check` above is the precedent: it reaches the network, and `check`
# answers from the tree alone — a row that fails on a train is a row people learn to ignore.
# Its VERDICT RULES do gate, through `make coordinator-selftest`, which needs no network; that
# is the same split `verdict-selftest` makes.
#
# Exit 1 means a block could not be read, which is the point: an incomplete report must not be
# relayable as the state of the queue.
coordinator:
	@python3 scripts/coordinator.py $(ARGS)

# The verdict rules, against synthetic check-run payloads. No network, so this is in `check`.
# Every case is a payload a reader looking at conclusions alone would call clean: one required
# check of two all passing, a required check that reported `skipped`, a null conclusion that
# must read as `running` and never as failed.
coordinator-selftest:
	@python3 scripts/coordinator.py --selftest

.PHONY: coordinator coordinator-selftest

# docs/GATES.md item 24, D-heartbeat-is-a-caller. A thin caller of coordinator.py --json (open
# PRs, id claims, dirty worktrees, live sessions) plus the two bullets that leaves unanswered —
# whether main's own last push is green, and janitor.py's own preview with --confirm never
# passed. Writes .serve/heartbeat/latest.json and appends history.jsonl, which is the memory a
# fresh, context-free run needs. NEVER A DAEMON: one run, one exit — the cadence is whatever
# scheduled task calls this, never a loop in here. Read-and-report authority only.
heartbeat:
	@python3 scripts/heartbeat.py $(ARGS)

.PHONY: heartbeat

# THE SWEEP, WHERE EVERY REPO CAN REACH IT. `~/.claude/settings.json` hooks apply to every
# session in every project, but the command they name has to exist without this checkout in
# sight — so the two files are COPIED, exactly as `make hooks` copies the git hooks out of the
# tree rather than pointing at it. A copy can go stale, which is why `make status` compares it
# and says so, the same way it reports a stale hooks-armed directory. One press, once per
# machine; run it again after this tree's copy changes.
janitor-install:
	@mkdir -p $$HOME/.claude/bin
	@cp scripts/janitor.py scripts/session-teardown.sh scripts/reap.py $$HOME/.claude/bin/
	@chmod +x $$HOME/.claude/bin/janitor.py $$HOME/.claude/bin/session-teardown.sh $$HOME/.claude/bin/reap.py
	@echo "installed to ~/.claude/bin: janitor.py, session-teardown.sh, reap.py"
	@echo "  hook it up once, in ~/.claude/settings.json, so it covers every repo:"
	@echo '    "SessionEnd":     [{"hooks": [{"type": "command", "timeout": 60,'
	@echo '                        "command": "$$HOME/.claude/bin/session-teardown.sh"}]}]'
	@echo '    "WorktreeRemove": [{"hooks": [{"type": "command", "timeout": 60,'
	@echo '                        "command": "$$HOME/.claude/bin/session-teardown.sh"}]}]'
	@echo '    "PreToolUse":     [{"matcher": "Bash", "hooks": [{"type": "command",'
	@echo '                        "command": "$$HOME/.claude/bin/reap.py --hook"}]}]'
	@echo '  then the sweep reaches any clone: ~/.claude/bin/janitor.py --root <path>'
	@echo '  and the kill guard covers every project, not just this one. Both copies can go'
	@echo '  stale; `make status` compares them and says so.'

# IS THE LAN URL STILL GOOD? The owner reaches this product from a phone at
# `http://pkmnscan.lan:8000`, and nothing in this repo knows that name — the DHCP reservation
# and the DNS record are theirs, on their UniFi (D43). What this checks is the four things on
# THIS side that have to agree with it, ending with a real write, because the failure worth
# catching is silent: reads are ungated and writes are origin-checked, so a missing
# `PKMNSCAN_LAN_NAME` leaves every screen rendering and every write answering 403.
#
# A SEPARATE `.PHONY` LINE, and that is deliberate rather than sloppy: the single line at the
# top of this file is one line that every branch adding a target edits, which makes it the
# most conflict-prone line in the Makefile. `phony_gaps` unions every `.PHONY:` it finds, so
# a second one is read exactly the same and merges without a fight.
#
# NOT IN `check`, and not for D18's reason — nothing here writes. It is out because `check`
# answers from the tree alone, and a row that resolves DNS and expects a server to be up would
# go red on a train and in every worktree. A check that fails for reasons unrelated to the
# commit is one people learn to ignore.
.PHONY: janitor janitor-selftest janitor-install serve-selftest sync-selftest ci-check

.PHONY: lan-check
lan-check:
	@python3 scripts/lan-check.py

# THE SERVER, DETACHED. ONE PROCESS: the API and the built app on one port (D138), restarting
# itself when you edit Python and rebuilding the app when you edit a screen.
# `make dev` and `make server` below still work; `dev` is now the hot-reload loop that runs
# BESIDE this rather than instead of it.
#
# The restart is the point rather than the convenience. docs/GATES.md records a run whose
# whole-second timestamps came from a server started before the millisecond fix landed — "a
# long-running `make server` outlives the fix that was written for it", filed there as a
# discipline. A discipline nobody can keep is what this replaces.
#
# DO NOT RUN THESE ALONGSIDE `make server`. The second one loses, loudly (EADDRINUSE). That is
# deliberate — a server that quietly moved to another port would serve a DIFFERENT store (D43).
# `make dev` is FINE alongside, and is the point: the supervisor no longer holds :5173, so Vite
# can run there with hot reload while this serves the same store on :8000.
#
# None of these four goes near `make check` or the git hook. D18: nothing that writes may run
# on the path that decides whether a commit proceeds, and `launch-agent` writes to ~/Library,
# which is the strongest form of that rule this repo has had to apply.
# `$(ARGS)` ON BOTH, AND `down`'s REFUSAL IS WHY. In the main checkout, where a launch agent
# keeps the server alive over the real store, `down` and `up ARGS=--restart` refuse and print
# `make down ARGS=--confirm     do it anyway`. That line did not work: neither target forwarded
# ARGS, so the escape hatch the guard itself names was unrunnable, and the only ways past a
# refusal that was designed to be answerable were to call `scripts/serve.py` directly or to
# reach around the guard entirely. Found 2026-09-06 by following the printed instruction.
#
# `up` takes them too, for `--no-watch` and for `--restart`, which is the bounce now.
up:
	@$(PYTHON) scripts/serve.py up $(ARGS)

down:
	@$(PYTHON) scripts/serve.py down $(ARGS)

# Generated, never tracked, and written OUTSIDE the repo into ~/Library/LaunchAgents. A
# tracked plist would carry an absolute path baked on one Mac, which is D47's failure verbatim
# — and a worktree's plist would outlive the worktree, so this refuses in a linked checkout.
launch-agent:
	@$(PYTHON) scripts/serve.py launch-agent $(ARGS)

# Foreground and blocking, like `server` below — background it from an agent session, or
# the Stop hook's harness run never gets to happen.
#
# strictPort in app/vite.config.ts, so a busy 5173 fails here instead of quietly serving on
# 5174 — where CLAUDE.md, this target and scripts/views.txt would all three be wrong.
# NO `guard-foreground` HERE SINCE D138, and its removal is the feature. The supervisor used
# to hold :5173 and this would have collided with it; it holds only the capture port now, so
# Vite runs here with hot reload against the live server — which is what alternating between
# building and operating actually needs.
dev:
	$(NPM_GUARD)
	@npm --prefix app run dev

# Foreground and blocking, like any server. An agent that runs this in the foreground hangs
# its own turn — the Stop hook runs the harness at turn end and never gets there — so
# background it from an agent session.
#
# $(PYTHON), WHICH IS THE VENV WHERE ONE EXISTS AND BARE python3 WHERE ONE DOES NOT — and
# that keeps the property this line used to protect by naming `python3` outright. The rule was
# never "the server must run on system python3"; it was "the server must not NEED `make venv`
# first", same as `status` and `docs-audit`. It still does not: every route it has ever served
# is stdlib, and `$(PYTHON)` falls back to `python3` when no venv is there.
#
# What changed is that ONE route can now do more when Pillow is present. `POST
# /pipeline/crop-preview` draws what a reading will send, which means decoding a photograph —
# so it imports Pillow, numpy and geometry INSIDE the handler and refuses by name
# (`imaging_unavailable`) when they are absent, rather than at module scope where a missing
# dependency would stop the server booting over a preview nobody asked for. Under bare python3
# every other route is unaffected and that one says what to do.
server:
	@$(PYTHON) scripts/serve.py guard-foreground
	@$(PYTHON) server/capture_server.py

# The manifest is an INPUT and lives beside the script that reads it. It used to point at
# captures/views.txt, which .gitignore excludes wholesale — so the one file that says which
# views matter could never be committed, and would have died with the machine that wrote it.
screenshot:
	$(NPM_GUARD)
	@scripts/screenshot.sh --manifest scripts/views.txt

# The Fulfillment constraints table in docs/DESIGN.md, run against a real browser. Step 6
# covers one component; step 7 extends the same spec to the views it names.
#
# Deliberately NOT part of `check`: it starts a browser and a dev server, which is a
# different weight of check from the rest. That reason stood on its own even while `lint`
# was a stub and `check` could not pass at all; it still stands now that lint runs.
# IT TAKES A MACHINE-WIDE LOCK FIRST, AND THAT IS THE ONE THING D43 COULD NOT MAKE
# PER-CHECKOUT. Every tree has its own dev port, its own capture port and its own store; the
# CPU is shared, and this is the target that spends all of it — `fullyParallel` at half the
# cores, seven Chromium workers on this Mac, each with a Vite dev server compiling for it.
# Two trees running this at once starve each other and BOTH report failures that are not in
# the code: 18 of them on 2026-09-07, every one green on a re-run. See scripts/suite-lock.py
# for the measurement and D122 for the argument.
#
# IT REFUSES RATHER THAN QUEUES, and exits 75 so the refusal cannot read as a failing suite.
# `ARGS=--wait` queues instead, out loud. The `--` is what separates the guard's flags from
# the command it guards, so `ARGS` can never reach npm.
#
# AND IT LEAVES A VERDICT BEHIND, WHICH IS HOW A SESSION WAITS FOR IT. The suite is ~90-175s
# against the 120s tool timeout an agent session runs under, so every invocation from one is
# backgrounded mid-run. `.serve/design-check.json` is what to read when it lands: verdict,
# counts, failing titles, no ANSI and no NUL bytes. It says `"verdict": "running"` from the
# moment the suite starts, so a reader can tell "still going" from "died".
#
# NEVER PIPE THIS THROUGH `tail`. `... | tail -N > file` writes nothing at all until the
# process exits, because tail buffers its whole input, so the obvious "run it and read the
# tail" produces an empty file for the entire run and no way to tell it from a dead one.
# Redirect to a file if you want the stream; read the verdict either way.
#
# THE `rm` IS WHAT MAKES A MISSING FILE MEAN SOMETHING, and it runs BEFORE the lock, so
# "no file" now covers two cases rather than one: the run died before Playwright loaded its
# config, or the lock refused it. Both are loud — a refusal prints and exits 75 — and neither
# can be mistaken for a verdict. What the `rm` buys is that the PREVIOUS run's `pass` is
# never left sitting there for a reader to believe, which is the only silent failure of the
# three. app/design-check-reporter.ts carries the rest of the argument.
#
# `ARGS` REACHES THE LOCK AND `PW_ARGS` REACHES PLAYWRIGHT, and the two are kept apart by the
# `--` on each side (D136). Until 2026-09-11 nothing here could hand Playwright a flag at all,
# and the one that mattered was `--shard`: `.github/workflows/check.yml` runs this suite as
# three shards on three 2-vCPU runners — `PW_ARGS="--shard=1/3 --workers=1"` — because one
# runner ran all 481 cases on ONE worker in 15 minutes, against 89-175s for the rig's seven.
# Sharding splits the CASES and leaves the worker count alone, which is the half that matters:
# docs/DEBTS.md section 8 measured a one-in-thirteen red whose only known mechanism is "the
# suite around it", and more workers on one box is more suite around it. On the rig `PW_ARGS`
# is for a session that wants one spec — `PW_ARGS=tests/brand.spec.ts` — and nothing else.
# Each shard leaves its own `.serve/design-check.json`; on a runner that is one file per job.
design-check:
	$(NPM_GUARD)
	@rm -f .serve/design-check.json
	@python3 scripts/suite-lock.py run $(ARGS) -- npm --prefix app run design-check -- $(PW_ARGS)

# The lock itself, exercised by violating it — a holder, a refusal, a wait, and a holder
# killed with -9 to prove the OS releases what it took. In `check`, never in the git hook: it
# spawns processes and writes a lock directory under `mktemp -d`, which is D18's line. Same
# standing as janitor-selftest, merge-selftest and githooks-selftest.
suite-lock-selftest:
	@if python3 scripts/guard-scope.py classify --target suite-lock-selftest --base origin/main; then \
		python3 scripts/suite-lock.py selftest; \
	else \
		echo "suite-lock-selftest: SKIPPED — this branch does not touch scripts/suite-lock.py. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# The classifier's own matcher, recipe narrowing and spec map, proved on fixtures and on the
# real tree (D-browser-spec-allow-list). Reads only; nothing here writes, so it sits beside
# the other guard selftests rather than on the commit path (D18).
browser-scope-selftest:
	@python3 scripts/browser-scope.py selftest

# A JS media query's viewport width against what a stylesheet under app/src declares
# (D123): the pure extraction and comparison `make docs-audit`'s `js breakpoints` row
# imports, proved on fixtures by violating it and then fixing it, plus a read of the real
# tree. Reads only; nothing here writes, so it sits beside the other guard selftests.
js-breakpoints-selftest:
	@python3 scripts/js-breakpoints.py selftest

# `make docs-audit`'s `subagent override` row, proved by violating it in a real throwaway git
# repository with a REAL nested worktree — the exact shape `.claude/worktrees/<name>/` is, and
# the exact place the 2026-09-19 forgotten-override incident sat. D18: it writes a temp
# repository, so it is not in the git hook; the row it proves runs on every commit regardless.
subagent-override-selftest:
	@python3 scripts/subagent-override-selftest.py

# The same run with the 450-line progress stream dropped — same tests, same assertions,
# same `.serve/design-check.json`. The progress is only useful to a human watching live,
# and it is what makes a captured log unreadable, so a session that is going to read the
# verdict file should ask for this one.
design-check-quiet:
	$(NPM_GUARD)
	@rm -f .serve/design-check.json
	@DESIGN_CHECK_QUIET=1 python3 scripts/suite-lock.py run $(ARGS) -- npm --prefix app run design-check -- $(PW_ARGS)

# eslint over app/, config and rules in app/eslint.config.js. It began 2026-08-13 as the two
# guards docs/DECISIONS.md's v1 bug table promised — no `facingMode` (bug 3), no `split(",")`
# CSV parsing (bug 2) — and has since gained a rule per bug this project caught itself: the
# two-argument `.then` that swallows its own success handler's throw, and `localStorage`
# outside D27's carve-out. THE COUNT IS DELIBERATELY NOT STATED: this comment said "two" while
# the config held four, and the config file is the register. The pattern is the point — a bug
# becomes a guard, so the list only grows.
#
# RUFF JOINED THIS TARGET 2026-09-01 (D82), ON A SLICE MEASURED AGAINST THIS TREE, NOT ON
# WHAT IT ENABLES BY DEFAULT. Zero-config `ruff check .` found 2,131 things on this repo,
# 79% of them three pyupgrade rules rewriting `Dict`/`Optional[X]` to PEP 585/604 syntax —
# a runtime TypeError on the Python 3.9.6 this repo pins, unless ruff is told the target
# version, which its own default does not do. `ruff.toml` sets it and selects only
# pyflakes + bugbear + flake8-simplify; the other ~890 default-enabled rules are unmeasured
# here and stay off. Three rules in even that narrower selection produced confirmed false
# positives on this tree, each now a per-line `# noqa` with its reason rather than a
# blanket exclusion: SIM115 over a lock's flock handle and a detached child's log handle,
# both deliberately outliving the function that opens them; B023 over a test closure that
# is started and joined before the loop variable it captures rebinds; and SIM118 in
# cli/resolve.py, where `games` is the `pipeline.games` MODULE and `.keys()` is a real
# function rather than dict.keys() — applying that one broke `make harness` (T3/T4/T7,
# `TypeError: 'module' object is not iterable`) before it was caught and reverted.
#
# No `--fix`, here or in the npm script, for either language. `check` below runs this
# target, and D18 keeps anything that writes off the path that decides whether work is done.
# Vale, the prose linter, over EVERY tracked markdown file.
#
# NOT on the commit path and it must not go there. scripts/githooks/pre-commit runs a bare
# python3 with nothing installed (D18), and vale is a third-party Go binary — a commit gate
# that needs software present would make the three opsec rules depend on it too. `make check`
# is invoked by a person, which is where port-agreement and the audit's self-test already sit.
#
# It answers the STYLE half of D60 and none of the size half; `entry budget` in
# scripts/docs-audit.py is what knows an entry costs tokens to load.
#
# IT RAN OVER FOUR FILES UNTIL 2026-08-30 AND .vale.ini ALWAYS SAID `[*.md]`. The target was
# the narrow half of that disagreement, so docs/specs/ and docs/design-refs/ were never linted
# at all: 35 AmericanSpelling errors had accumulated there, none of them reachable by any check
# in this repo. D60's rule is written about the four docs a session loads, and that is an
# argument about which prose must be DENSE — never an argument for leaving the rest unspelled.
# The file list is `git ls-files` so a new document is linted the day it is committed rather
# than the day somebody remembers to add it here.
#
# A missing binary reports and does not fail, so `make check` still runs on a machine
# without it — the same shape NPM_GUARD takes, minus the exit.
#
# ONE RECIPE LINE, DELIBERATELY. Split across two — a guard line ending `exit 0`, then a
# bare `git ls-files | xargs vale` — the guard's `exit 0` only ends ITS OWN shell; each `@`
# line is a separate invocation, and make advances to the next line on any zero exit, guard
# or not. So the message printed, the target reported nothing wrong, and `xargs` ran anyway
# with no `vale` to run — `xargs: vale: No such file or directory`, exit 127, `make check`
# failing on the one row this comment says cannot fail it. Measured, not hypothetical: that
# is the exact output a binary-less machine produced. One `if` keeps the run inside the
# branch that only exists once the guard has already passed.
vale:
	@echo "NOT A GATE: prose style is reported and never blocks (D18). --no-exit swallows"
	@echo "  the status, and a missing binary reports and exits 0 — so this slot in"
	@echo "  \`make check\` cannot fail, and a reader of a green run should not count it"
	@echo "  among the ones that can. \`make docs-audit\`'s \`check registry\` row pairs this"
	@echo "  line against the entry's \`gates: False\` in both directions."
	@if command -v vale >/dev/null; then \
		git ls-files '*.md' | xargs vale --no-exit; \
	else \
		echo "vale is not installed — prose style unchecked."; \
		echo "  Fix: brew install vale"; \
	fi

lint:
	$(NPM_GUARD)
	@npm --prefix app run lint
	$(VENV_GUARD)
	$(RUFF_GUARD)
	@$(PYTHON) -m ruff check .

typecheck:
	$(NPM_GUARD)
	@npm --prefix app run typecheck

# ------------------------------------------------------------------------------- the demo
#
# A published, static copy of this product over a store that is safe to show strangers.
#
# WHY IT IS NOT A FORK. The app is 38,705 lines and the demo differs from it in exactly two
# functions — `request()` and `photoUrl()` in app/src/server.ts, which are the only places
# this front end touches its server. So a fork would duplicate all of the code to carry none
# of the difference, and would diverge the same week: this repo took 134 commits in the three
# days before the demo was built. What differs is DATA, and data belongs in a seed script.
#
# THREE STEPS, EACH RE-RUNNABLE AND EACH FREE.
#   demo-seed    writes a demo store — real catalogue rows out of fixtures/, invented
#                positions, drawn photographs. Deterministic, so an unchanged tree rebuilds
#                byte-identically and CI does not churn the repo.
#   demo-record  spawns its own capture server over that store on its own port, sweeps every
#                GET the client can build, and writes app/demo/bundle.json. It NEVER touches
#                `make up` — on the main checkout that is the owner's live server over their
#                real inventory, and CLAUDE.md is explicit that it is not a session's to bounce.
#   demo-static  the two above, then a production build with VITE_DEMO=1.
#
# DEMO_BASE is where it will be served from. GitHub Pages puts a project site under
# /<repo>/, and a bundle built for / 404s every asset there — a failure that shows up only
# once it is published. Override it for a user site or a custom domain:
#     make demo-static DEMO_BASE=/
#
# DERIVED FROM THE REMOTE, NOT WRITTEN DOWN, and it earned that on 2026-09-06: this line
# read `/pkmnscan/` and the repository was renamed to `banchi`, so a hand-run build pointed
# at a path that now 404s. `demo.yml` took the derived route from the start — "so a rename
# cannot leave it pointing at the old one" — and the published demo followed the rename by
# itself while this default did not. A name spelled in two places agrees until the day one
# moves, which is the same argument D43 makes about the port.
#
# The fallback is a literal because there is nowhere else to read one from: a tarball with
# no `.git`, or a clone with no `origin`. It is the current name, so it is right until the
# next rename and wrong in exactly the way this comment describes — override it there.
DEMO_HOME ?= demo
DEMO_REPO := $(shell n=$$(basename -s .git "$$(git config --get remote.origin.url 2>/dev/null)" 2>/dev/null); [ -n "$$n" ] && echo "$$n" || echo banchi)
DEMO_BASE ?= /$(DEMO_REPO)/

# Curate real card photographs, and their real identifications, into `demo-assets/`.
#
# SEPARATE FROM THE SEED AND RUN RARELY, because it is the only step here that reads a real
# store and the only one whose output is TRACKED. Everything else is derived and rebuilt on
# every push; this is a deliberate act of publishing somebody's photographs, so it happens
# when a person asks for it and never as a side effect of a build.
#
# It refuses any photograph a QR decodes out of — a live code card is a bearer instrument
# and its whole identity IS that QR (D70) — and checks at full resolution, before the
# downscale, because a 1 cm symbol at 360px is a smear no decoder can read.
DEMO_PHOTO_COUNT ?= 132
DEMO_PHOTO_JOINABLE ?= 92

demo-photos:
	@[ -n "$(SOURCE)" ] || { \
		echo "SOURCE=<checkout> is required — the store whose photographs to curate."; \
		echo "  e.g. make demo-photos SOURCE=~/Developer/pkmnscan"; \
		exit 1; }
	@$(PYTHON) scripts/demo-photos.py --source "$(SOURCE)" \
	  --count $(DEMO_PHOTO_COUNT) --joinable $(DEMO_PHOTO_JOINABLE)

demo-seed:
	@PKMNSCAN_HOME=$(DEMO_HOME) $(PYTHON) scripts/demo-seed.py --force
# THE JOIN IS THE REAL ONE, and that is the point of doing it here rather than writing a
# pricing table by hand. `identify` is the one step that costs money, so the seed fakes ONLY
# that — it writes `identifications.json` in the shape a real run leaves behind, which
# `cli/resolve.py` explicitly supports ("a hand-made or recovered identifications file").
# Everything downstream then runs for real against the real fixture exports: the catalogue
# lookup, the variant ladder, the cap arithmetic and `pricing.json` are the pipeline's own
# output, not a fixture pretending to be one. Both are free and re-runnable.
	@PKMNSCAN_HOME=$(DEMO_HOME) ./pkmnscan join $(DEMO_HOME)/runs/demo-box1 	  --export fixtures/riftbound_export_untouched.csv > /dev/null
	@PKMNSCAN_HOME=$(DEMO_HOME) ./pkmnscan join $(DEMO_HOME)/runs/demo-box3 	  --export fixtures/riftbound_export_untouched.csv > /dev/null
	@echo "  joined 2 runs against the real fixture exports"

demo-record:
	@PKMNSCAN_HOME=$(DEMO_HOME) $(PYTHON) scripts/demo-record.py

# The bundle without the build — what to run after changing a wire shape, so `git status`
# shows the recording moving with the contract it was recorded against.
demo: demo-seed demo-record

demo-static: demo
	$(NPM_GUARD)
	@cd app && VITE_DEMO=1 DEMO_BASE=$(DEMO_BASE) npx vite build --outDir ../dist-demo --emptyOutDir
	@echo ""
	@echo "  demo built -> dist-demo/  (base $(DEMO_BASE))"
	@echo "  preview it: make demo-preview"

# Serve the built demo exactly as a static host would, base path and all. `vite preview`
# honours the same `base`, so a link that works here works published — which is the only
# way to catch a base-path mistake before somebody else does.
demo-preview:
	$(NPM_GUARD)
	@cd app && DEMO_BASE=$(DEMO_BASE) npx vite preview --outDir ../dist-demo --port 4173 --strictPort

# Whether app/demo/bundle.json still describes the wire it was recorded against. On no gate
# at all: the bundle is not committed and CI rebuilds it from source on every push, so the
# only staleness left is a local preview serving a recording that predates your last edit.
# Worth one command; not worth failing `make check` over.
demo-freshness:
	@$(PYTHON) scripts/demo-freshness.py
