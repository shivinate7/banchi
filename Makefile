# PKMNSCAN
#
# Empty targets exit 1. A target that exits 0 with nothing to run is a lie the rest of
# the project would be built on top of — `make check` green means every check ran.

.DEFAULT_GOAL := help
.PHONY: help status harness check docs-audit audit-self-test githooks-selftest audit-history dev server screenshot design-check lint typecheck venv worktree-setup hooks

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

help:
	@echo "PKMNSCAN — run 'make status' for where the build actually stands."
	@echo
	@echo "  make status       where you are: next step, T1 score, branch. Derived."
	@echo "  make venv         .venv + requirements.txt   (once, before the first harness run)"
	@echo "  make worktree-setup  venv + T1's banked cache, for a fresh git worktree"
	@echo "  make hooks        arm the git hooks          (once, and again after every clone)"
	@echo "  make harness      T1-T7 verification tests. Run at turn end by the Stop hook."
	@echo "  make docs-audit   markdown vs the code it describes. Reports; never writes."
	@echo "  make audit-history  which docs-audit checks ever fired. Diagnostic; never gates."
	@echo "  make audit-self-test  the checker checks itself. In \`check\`, never in the git hook."
	@echo "  make githooks-selftest  main's guard, proved in a throwaway repo. Never in the git hook."
	@echo "  make check        harness + docs-audit + both self-tests + lint + typecheck"
	@echo
	@echo "  ./pkmnscan identify <capture-dir>                 submit, wait, collect. COSTS MONEY."
	@echo "  ./pkmnscan join     <run-dir> --export <csv>      resolve against the export. Free."
	@echo "  ./pkmnscan emit     <run-dir>                     write import CSVs. Free."
	@echo "  ./pkmnscan reconcile <run-dir> <staged-export>    confirm what TCGplayer staged."
	@echo "  make dev          Vite app on :5173. Blocks — background it in a session."
	@echo "  make server       Python capture server on :8000. Blocks — background it in a session."
	@echo "  make screenshot   render the views in scripts/views.txt to captures/ui/"
	@echo "  make design-check docs/DESIGN.md's Fulfillment floors, asserted in a browser."
	@echo "  make lint         eslint over app/: the two v1-bug rules. No Python linter."
	@echo "  make typecheck    tsc --noEmit over app/"
	@echo
	@echo "Build order and gates: docs/GATES.md"

venv:
	@python3 -m venv .venv
	@.venv/bin/python -m pip install --quiet --upgrade pip
	@.venv/bin/python -m pip install --quiet -r requirements.txt
	@echo "venv ready: $$(.venv/bin/python -V)"
	@echo "T1 also needs ANTHROPIC_API_KEY in the environment."

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
worktree-setup:
	@main="$$(dirname "$$(git rev-parse --git-common-dir)")"; \
	here="$$(pwd)"; \
	if [ "$$main" = "$$here" ]; then \
		echo "This IS the main working tree — nothing to copy into it."; \
		echo "  Fix: make venv"; \
		exit 1; \
	fi; \
	$(MAKE) --no-print-directory venv; \
	if [ -d "$$main/harness/.cache" ]; then \
		mkdir -p harness/.cache; \
		cp -R "$$main/harness/.cache/." harness/.cache/; \
		echo "harness/.cache copied from $$main"; \
	else \
		echo "NOTE: $$main has no harness/.cache — T1 will refuse until a run is banked there."; \
	fi; \
	if [ ! -e harness/images ] && [ -d "$$main/harness/images" ]; then \
		ln -s "$$main/harness/images" harness/images; \
		echo "harness/images linked (133 MB, shared — immutable and additive-only)"; \
	fi
	@[ -d app/node_modules ] || { \
		echo "NOTE: app/ dependencies are not installed either — also gitignored, also"; \
		echo "      does not travel. \`make harness\` does not need them; lint, typecheck"; \
		echo "      and design-check do, so \`make check\` will stop at lint until you run:"; \
		echo "        npm --prefix app install"; }
	@echo "worktree ready. \`make harness\` should now be green without spending anything."

# core.hooksPath is LOCAL config — it lives in .git/config, which is never pushed. So a fresh
# clone carries scripts/githooks/pre-commit as a tracked file with NOTHING POINTING AT IT, and
# CLAUDE.md's bearer-instrument rule is unenforced on the first commit. It fails silently,
# which is the only way an opsec rule can fail badly: nothing is printed, nothing exits 1, and
# the commit that leaks a live code looks exactly like every commit before it.
#
# This is the one setup step that cannot itself be committed, so it cannot be made automatic —
# `make status` reports the unarmed state instead, which is why that target grew an Opsec hook
# line. Idempotent: running it on an armed clone is free.
#
# The chmod is not padding. git skips a non-executable hook WITHOUT A WORD, so a correct
# hooksPath over a non-executable file is the same silent failure by another route.
# THE PATH IS ABSOLUTE, AND RESOLVED TO THE MAIN WORKTREE RATHER THAN TO WHEREVER YOU RAN
# THIS. core.hooksPath lives in the common .git dir, so ONE value governs every worktree of
# this clone — and git resolves a relative one against each worktree's own root. Left
# relative, a worktree checked out from a commit before the main guard existed finds no
# `reference-transaction` file and runs unguarded, which is the exact population the guard is
# for: concurrent sessions on branches cut from an older main. Absolute, main's copy governs
# all of them whatever commit they sit on. Resolved through `git worktree list` rather than
# $(CURDIR) so that running this FROM a worktree does not point the whole clone at a
# checkout that is about to be deleted.
hooks:
	@root="$$(git worktree list --porcelain | sed -n '1s/^worktree //p')"; \
	  [ -n "$$root" ] || root="$$(pwd)"; \
	  git config core.hooksPath "$$root/scripts/githooks"; \
	  chmod +x "$$root"/scripts/githooks/*; \
	  echo "hooks armed: core.hooksPath = $$(git config --get core.hooksPath)"; \
	  echo "  pre-commit             fixtures, code-card opsec, docs audit"; \
	  echo "  reference-transaction  main does not move locally"; \
	  echo "  pre-push               nothing pushes to main"


# python3, not $(PYTHON): a step-away tool that needs `make venv` first is not a step-away
# tool. Exits non-zero if any declared source is missing — it prints MISSING rather than
# quietly printing less, because the shorter version is the one you would believe.
status:
	@python3 scripts/status.py

harness:
	@$(PYTHON) harness/run.py

# Exit 1 is a provably wrong reference and fails. Exit 2 is the coupling question — it
# prints and passes, here for the same reason the pre-commit hook lets it through: a
# question that can fail your build is a question you learn to route around. See D16.
# python3, not $(PYTHON): the script is stdlib-only so it must not need `make venv`.
docs-audit:
	@python3 scripts/docs-audit.py; \
	status=$$?; \
	if [ $$status -eq 1 ]; then exit 1; fi

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
	@$(MAKE) --no-print-directory audit-self-test
	@$(MAKE) --no-print-directory githooks-selftest
	@$(MAKE) --no-print-directory lint
	@$(MAKE) --no-print-directory typecheck

# python3, not $(PYTHON): the script is stdlib-only so it must not need `make venv`.
audit-self-test:
	@python3 scripts/docs-audit.py --self-test

# HERE AND NOT IN THE GIT HOOK, for the reason stated above `check` and for a second one of
# its own. D18 is the first: this writes — a bare repo, a clone, commits, pushes — and nothing
# that writes may run on the path that decides whether a commit proceeds. The second is that
# it exercises the guard by VIOLATING it, so a version wired into the commit path would be
# refusing its own commits.
githooks-selftest:
	@bash scripts/githooks-selftest.sh

# Foreground and blocking, like `server` below — background it from an agent session, or
# the Stop hook's harness run never gets to happen.
#
# strictPort in app/vite.config.ts, so a busy 5173 fails here instead of quietly serving on
# 5174 — where CLAUDE.md, this target and scripts/views.txt would all three be wrong.
dev:
	$(NPM_GUARD)
	@npm --prefix app run dev

# Foreground and blocking, like any server. An agent that runs this in the foreground hangs
# its own turn — the Stop hook runs the harness at turn end and never gets there — so
# background it from an agent session.
#
# python3, not $(PYTHON): the capture server is stdlib-only, so it must not need `make venv`
# first. Same rule as `status` and `docs-audit` above, and verified against bare system
# python3 rather than assumed.
server:
	@python3 server/capture_server.py

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
design-check:
	$(NPM_GUARD)
	@npm --prefix app run design-check

# eslint over app/, config and rules in app/eslint.config.js. It began 2026-08-13 as the two
# guards docs/DECISIONS.md's v1 bug table promised — no `facingMode` (bug 3), no `split(",")`
# CSV parsing (bug 2) — and has since gained a rule per bug this project caught itself: the
# two-argument `.then` that swallows its own success handler's throw, and `localStorage`
# outside D27's carve-out. THE COUNT IS DELIBERATELY NOT STATED: this comment said "two" while
# the config held four, and the config file is the register. The pattern is the point — a bug
# becomes a guard, so the list only grows.
#
# JavaScript only, and this target does not claim otherwise. The stub it replaced promised
# "ruff (Python) + eslint (JS)"; shipping the JS half under that name would leave `make
# check` green with a whole language unlinted, which is the same lie the header comment
# above is about. Python has no linter here. Adopting ruff is its own decision, unmade —
# and `docs/specs/audit-retirement.md` section 9 is the format for making it: run the tool
# on this repo, read the findings, then decide.
#
# No `--fix`, here or in the npm script. `check` below runs this target, and D18 keeps
# anything that writes off the path that decides whether work is done.
lint:
	$(NPM_GUARD)
	@npm --prefix app run lint

typecheck:
	$(NPM_GUARD)
	@npm --prefix app run typecheck
