# PKMNSCAN
#
# Empty targets exit 1. A target that exits 0 with nothing to run is a lie the rest of
# the project would be built on top of — `make check` green means every check ran.

.DEFAULT_GOAL := help
.PHONY: help harness check dev server screenshot lint typecheck venv

# Prefer the venv if it exists, so `make harness` works without anyone remembering to
# activate anything. Falls back to system python3, which still runs T2-T5 — T1 needs the
# anthropic SDK and T6 needs Pillow + numpy, and each reports the missing dependency as a
# FAILURE rather than crashing or, worse, skipping. A skipped test must not read as a pass.
PYTHON := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

help:
	@echo "PKMNSCAN — build-order step 4 (batch script v2)"
	@echo
	@echo "  make venv         .venv + requirements.txt   (once, before the first harness run)"
	@echo "  make harness      T1-T6 verification tests. Must exit 0 before any commit."
	@echo "  make check        harness + lint + typecheck"
	@echo
	@echo "  ./pkmnscan identify <capture-dir>                 submit, wait, collect. COSTS MONEY."
	@echo "  ./pkmnscan join     <run-dir> --export <csv>      resolve against the export. Free."
	@echo "  ./pkmnscan emit     <run-dir>                     write import CSVs. Free."
	@echo "  ./pkmnscan reconcile <run-dir> <staged-export>    confirm what TCGplayer staged."
	@echo "  make dev          Vite app on :5173                    (unblocked at step 8)"
	@echo "  make server       Python capture server on :8000       (unblocked at step 6)"
	@echo "  make screenshot   render key views to captures/ui/     (unblocked at step 8)"
	@echo "  make lint         linters                              (unblocked at step 5)"
	@echo "  make typecheck    type checkers                        (unblocked at step 8)"
	@echo
	@echo "Build order and gates: docs/GATES.md"

venv:
	@python3 -m venv .venv
	@.venv/bin/python -m pip install --quiet --upgrade pip
	@.venv/bin/python -m pip install --quiet -r requirements.txt
	@echo "venv ready: $$(.venv/bin/python -V)"
	@echo "T1 also needs ANTHROPIC_API_KEY in the environment."

harness:
	@$(PYTHON) harness/run.py

# Not prerequisites: make is free to reorder those, and with -j it runs them in parallel.
# A check suite has to run in a known order and stop at the first failure.
check:
	@$(MAKE) --no-print-directory harness
	@$(MAKE) --no-print-directory lint
	@$(MAKE) --no-print-directory typecheck

dev:
	@echo "make dev: nothing to run yet."
	@echo "  Will run: npm run dev  (Vite app on :5173)"
	@echo "  Unblocked by build-order step 8 — see docs/GATES.md"
	@exit 1

server:
	@echo "make server: nothing to run yet."
	@echo "  Will run: python3 server/capture_server.py  (on :8000)"
	@echo "  Unblocked by build-order step 6 — see docs/GATES.md"
	@exit 1

screenshot:
	@scripts/screenshot.sh --manifest captures/views.txt

lint:
	@echo "make lint: nothing to lint yet."
	@echo "  Will run: ruff (Python) + eslint (JS), including the v1-bug lint rules —"
	@echo "  no split(\",\") CSV parsing, no facingMode: \"environment\". See docs/DECISIONS.md."
	@echo "  Unblocked by build-order step 5 — see docs/GATES.md"
	@exit 1

typecheck:
	@echo "make typecheck: nothing to typecheck yet."
	@echo "  Will run: tsc --noEmit"
	@echo "  Unblocked by build-order step 8 — see docs/GATES.md"
	@exit 1
