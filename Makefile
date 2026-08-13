# PKMNSCAN
#
# Empty targets exit 1. A target that exits 0 with nothing to run is a lie the rest of
# the project would be built on top of — `make check` green means every check ran.

.DEFAULT_GOAL := help
.PHONY: help status harness check docs-audit audit-history dev server screenshot design-check lint typecheck venv

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
	@echo "  make status       where you are: next step, gate, T1 score, branch. Derived."
	@echo "  make venv         .venv + requirements.txt   (once, before the first harness run)"
	@echo "  make harness      T1-T7 verification tests. Run at turn end by the Stop hook."
	@echo "  make docs-audit   markdown vs the code it describes. Reports; never writes."
	@echo "  make audit-history  which docs-audit checks ever fired. Diagnostic; never gates."
	@echo "  make check        harness + docs-audit + lint + typecheck"
	@echo
	@echo "  ./pkmnscan identify <capture-dir>                 submit, wait, collect. COSTS MONEY."
	@echo "  ./pkmnscan join     <run-dir> --export <csv>      resolve against the export. Free."
	@echo "  ./pkmnscan emit     <run-dir>                     write import CSVs. Free."
	@echo "  ./pkmnscan reconcile <run-dir> <staged-export>    confirm what TCGplayer staged."
	@echo "  make dev          Vite app on :5173. Blocks — background it in a session."
	@echo "  make server       Python capture server on :8000. Blocks — background it in a session."
	@echo "  make screenshot   render the views in scripts/views.txt to captures/ui/"
	@echo "  make design-check docs/DESIGN.md's Fulfillment floors, asserted in a browser."
	@echo "  make lint         linters                              (ruff unblocked; not wired)"
	@echo "  make typecheck    tsc --noEmit over app/"
	@echo
	@echo "Build order and gates: docs/GATES.md"

venv:
	@python3 -m venv .venv
	@.venv/bin/python -m pip install --quiet --upgrade pip
	@.venv/bin/python -m pip install --quiet -r requirements.txt
	@echo "venv ready: $$(.venv/bin/python -V)"
	@echo "T1 also needs ANTHROPIC_API_KEY in the environment."

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
check:
	@$(MAKE) --no-print-directory harness
	@$(MAKE) --no-print-directory docs-audit
	@$(MAKE) --no-print-directory lint
	@$(MAKE) --no-print-directory typecheck

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
# different weight of check from the rest, and `check` cannot pass today anyway while
# `lint` is a stub.
design-check:
	$(NPM_GUARD)
	@npm --prefix app run design-check

lint:
	@echo "make lint: not wired yet."
	@echo "  Will run: ruff (Python) + eslint (JS), including the v1-bug lint rules —"
	@echo "  no split(\",\") CSV parsing, no facingMode: \"environment\". See docs/DECISIONS.md."
	@echo "  ruff has Python to lint as of step 4; eslint has app/ to lint as of step 6."
	@exit 1

typecheck:
	$(NPM_GUARD)
	@npm --prefix app run typecheck
