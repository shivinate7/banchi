# PKMNSCAN
#
# Empty targets exit 1. A target that exits 0 with nothing to run is a lie the rest of
# the project would be built on top of — `make check` green means every check ran.

.DEFAULT_GOAL := help
.PHONY: help status harness check docs-audit audit-history dev server screenshot lint typecheck venv

# Prefer the venv if it exists, so `make harness` works without anyone remembering to
# activate anything. Falls back to system python3, which still runs T2-T5 — T1 needs the
# anthropic SDK and T6 needs Pillow + numpy, and each reports the missing dependency as a
# FAILURE rather than crashing or, worse, skipping. A skipped test must not read as a pass.
PYTHON := $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)

help:
	@echo "PKMNSCAN — run 'make status' for where the build actually stands."
	@echo
	@echo "  make status       where you are: next step, gate, T1 score, branch. Derived."
	@echo "  make venv         .venv + requirements.txt   (once, before the first harness run)"
	@echo "  make harness      T1-T6 verification tests. Run at turn end by the Stop hook."
	@echo "  make docs-audit   markdown vs the code it describes. Reports; never writes."
	@echo "  make audit-history  which docs-audit checks ever fired. Diagnostic; never gates."
	@echo "  make check        harness + docs-audit + lint + typecheck"
	@echo
	@echo "  ./pkmnscan identify <capture-dir>                 submit, wait, collect. COSTS MONEY."
	@echo "  ./pkmnscan join     <run-dir> --export <csv>      resolve against the export. Free."
	@echo "  ./pkmnscan emit     <run-dir>                     write import CSVs. Free."
	@echo "  ./pkmnscan reconcile <run-dir> <staged-export>    confirm what TCGplayer staged."
	@echo "  make dev          Vite app on :5173                    (unblocked at step 7)"
	@echo "  make server       Python capture server on :8000. Blocks — background it in a session."
	@echo "  make screenshot   render key views to captures/ui/     (unblocked at step 7)"
	@echo "  make lint         linters                              (ruff unblocked; not wired)"
	@echo "  make typecheck    type checkers                        (unblocked at step 7)"
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

dev:
	@echo "make dev: nothing to run yet."
	@echo "  Will run: npm run dev  (Vite app on :5173)"
	@echo "  Unblocked by build-order step 7 — see docs/GATES.md"
	@exit 1

# Foreground and blocking, like any server. An agent that runs this in the foreground hangs
# its own turn — the Stop hook runs the harness at turn end and never gets there — so
# background it from an agent session.
#
# python3, not $(PYTHON): the capture server is stdlib-only, so it must not need `make venv`
# first. Same rule as `status` and `docs-audit` above, and verified against bare system
# python3 rather than assumed.
server:
	@python3 server/capture_server.py

screenshot:
	@scripts/screenshot.sh --manifest captures/views.txt

lint:
	@echo "make lint: not wired yet."
	@echo "  Will run: ruff (Python) + eslint (JS), including the v1-bug lint rules —"
	@echo "  no split(\",\") CSV parsing, no facingMode: \"environment\". See docs/DECISIONS.md."
	@echo "  ruff has Python to lint as of step 4; eslint waits for step 7 — see docs/GATES.md"
	@exit 1

typecheck:
	@echo "make typecheck: nothing to typecheck yet."
	@echo "  Will run: tsc --noEmit"
	@echo "  Unblocked by build-order step 7 — see docs/GATES.md"
	@exit 1
