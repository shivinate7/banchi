# PKMNSCAN
#
# Empty targets exit 1. A target that exits 0 with nothing to run is a lie the rest of
# the project would be built on top of — `make check` green means every check ran.

.DEFAULT_GOAL := help
.PHONY: help status harness check ignore-check docs-audit audit-self-test githooks-selftest port-agreement icloud-sweep audit-history dev server screenshot design-check lint typecheck venv launch-config worktree-setup hooks

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
	@echo "  make launch-config   .claude/launch.json for THIS checkout's dev port (D43)"
	@echo "  make hooks        arm the git hooks          (once, and again after every clone)"
	@echo "  make harness      T1-T7 verification tests. Run at turn end by the Stop hook."
	@echo "  make docs-audit   markdown vs the code it describes. Reports; never writes."
	@echo "  make audit-history  which docs-audit checks ever fired. Diagnostic; never gates."
	@echo "  make audit-self-test  the checker checks itself. In \`check\`, never in the git hook."
	@echo "  make githooks-selftest  main's guard, proved in a throwaway repo. Never in the git hook."
	@echo "  make port-agreement  server/ports.py and app/devPort.ts answer the same numbers."
	@echo "  make ignore-check  every path a worktree provisions is gitignored, link or not (D47)."
	@echo "  make icloud-sweep  list iCloud conflict copies. ARGS=--delete removes the identical ones."
	@echo "  make check        harness + docs-audit + the self-tests + lint + typecheck"
	@echo
	@echo "  ./pkmnscan identify <capture-dir>                 submit, wait, collect. COSTS MONEY."
	@echo "  ./pkmnscan join     <run-dir> --export <csv>      resolve against the export. Free."
	@echo "  ./pkmnscan emit     <run-dir>                     write import CSVs. Free."
	@echo "  ./pkmnscan reconcile <run-dir> <staged-export>    confirm what TCGplayer staged."
	@echo "  make dev          Vite app on :5173. Blocks — background it in a session."
	@echo "  make server       Python capture server. :8000 in the main tree, its own port in a"
	@echo "                    worktree (D43) — it prints which. Blocks — background it."
	@echo "  make screenshot   render the views in scripts/views.txt to captures/ui/"
	@echo "  make design-check docs/DESIGN.md's Fulfillment floors, asserted in a browser."
	@echo "  make lint         eslint over app/: the two v1-bug rules. No Python linter."
	@echo "  make typecheck    tsc --noEmit over app/"
	@echo
	@echo "Build order and gates: docs/GATES.md"

venv: launch-config
	@python3 -m venv .venv
	@.venv/bin/python -m pip install --quiet --upgrade pip
	@.venv/bin/python -m pip install --quiet -r requirements.txt
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
launch-config:
	@$(PYTHON) -c 'import json, pathlib, sys; sys.path.insert(0, "."); from server import ports; \
	path = pathlib.Path(".claude/launch.json"); path.parent.mkdir(parents=True, exist_ok=True); \
	path.write_text(json.dumps({"version": "0.0.1", "configurations": [{"name": "app", \
	"runtimeExecutable": "npm", "runtimeArgs": ["run", "dev", "--prefix", "app"], \
	"port": ports.dev_port()}]}, indent=2) + "\n", encoding="utf-8"); \
	print("launch.json written: the Browser pane opens this checkout on {0}".format(ports.dev_port()))'

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
	mirror="$$(cd "$$main" 2>/dev/null && python3 -c 'import sys; sys.path.insert(0, "."); from harness.eval import fixtures; print(fixtures.IMAGES_DIR)' 2>/dev/null)"; \
	[ -n "$$mirror" ] || mirror="$$main/harness/images"; \
	if [ -e harness/images ]; then \
		:; \
	elif [ -d "$$mirror" ]; then \
		ln -s "$$mirror" harness/images; \
		echo "harness/images linked -> $$mirror (133 MB, shared — immutable and additive-only)"; \
	else \
		echo "NOTE: no image mirror at $$mirror — T1 will re-download 151 images."; \
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
	@$(MAKE) --no-print-directory port-agreement
	@$(MAKE) --no-print-directory ignore-check
	@$(MAKE) --no-print-directory lint
	@$(MAKE) --no-print-directory typecheck

# The other half of D47: every path a worktree provisions is ignored whatever kind of thing is
# at it. In `check` and never in the git hook — D18 forbids a commit gate that depends on local
# state, and this asks about provisioning, so a fresh clone would fail a commit over nothing.
ignore-check:
	@sh scripts/ignore-check.sh

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

# HERE BECAUSE TWO LANGUAGES HOLD ONE ALGORITHM AND NEITHER CAN IMPORT THE OTHER (D43).
# Python serves the capture port, TypeScript addresses it, and a disagreement is silent and
# total — the app asks for a port nothing is listening on, or one ANOTHER tree is listening
# on, which is the defect the whole decision exists to remove. It runs node, so it is not on
# the commit path: the git hook runs bare, and a check that needs a toolchain would fail
# on a machine that has none rather than on a defect.
port-agreement:
	@python3 scripts/port-agreement.py

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
