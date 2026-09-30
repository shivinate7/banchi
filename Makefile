# PKMNSCAN
#
# Empty targets exit 1. A target that exits 0 with nothing to run is a lie the rest of
# the project would be built on top of — `make check` green means every check ran.

.DEFAULT_GOAL := help
.PHONY: help status map explain harness check cid-selftest pricearchive-selftest archive-review-selftest holdings-selftest identity-checks-selftest price-postings-selftest product-history-selftest sku-number-contradictions-selftest cid-audit ignore-check docs-audit map-fix tests-page map-fix-selftest orient serve-scope serve-scope-selftest guard-scope guard-scope-selftest audit-self-test verdict-selftest githooks-selftest merge merge-selftest revert-guard revert-selftest claim-ids claim-stale claim-selftest decisions-selftest debts-selftest gates-selftest port-agreement set-hint-agreement readiness-agreement mutate-anchors mutate-guards screen-freshness screen-freshness-selftest sigil-check suite-lock-selftest browser-scope-selftest js-breakpoints-selftest subagent-override-selftest janitor-agent icloud-sweep audit-history dev server screenshot design-check design-check-quiet lint typecheck venv launch-config worktree-setup worktree-provision-selftest hooks up down launch-agent demo demo-photos demo-mirror demo-mirror-install demo-mirror-rebuild demo-histories demo-seed demo-record demo-static demo-preview catalog-refresh catalog-index catalog-index-selftest catalog-mirror css-var-check css-var-check-selftest hand-search-selftest token-literal-check token-literal-check-selftest kit-adoption kit-adoption-selftest text-density port-slots-selftest offenders-prune offenders-prune-selftest match-selftest

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

# A LINKED CHECKOUT CLAIMS ITS OWN PORT SLOT BEFORE IT SERVES OR TESTS
# (D-a-claimed-slot-and-a-server-that-names-its-checkout). A hash into 300 slots put two live
# worktrees on one port. The claim records one slot per checkout in ~/.pkmnscan/port-slots.json,
# and server/ports.py and app/devPort.ts read it. The primary checkout claims nothing. It fails
# open and says so: the ports then fall back to the hash, and app/checkoutIdentity.ts still
# refuses a test run against another checkout's server.
# `.claude/launch.json` names a port too, so `scripts/launch-config.py` claims BEFORE it writes
# that file. `make launch-config`, `make venv` and `make worktree-setup` reach the claim
# through it, and so does the SessionStart hook. A file written from the hash port before a
# claim moved the tree would open ANOTHER tree's server in the Browser pane.
PORT_CLAIM = @python3 scripts/port-slots.py claim --quiet

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

# ONE SOURCE: the comment directly above each target's rule (token-budget audit,
# 2026-09-27, Q1). This used to be a second, hand-typed ~22 KB copy of every target's
# purpose, and CLAUDE.md's Commands section carried a third; the three had already
# drifted. `scripts/make-help.py` renders this one, so there is one place to edit a
# target's description. `make docs-audit`'s `commands roster` row reconciles CLAUDE.md's
# short list against the real targets, both ways.
# python3, not $(PYTHON): a step-away tool that needs `make venv` first is not a
# step-away tool. Same rule as `status`, `map`, `explain` and `docs-audit`.
help:
	@python3 scripts/make-help.py

# `.venv` + requirements.txt. Idempotent — safe to re-run whenever
# requirements.txt changes (VENV_GUARD is what notices and asks for the re-run).
# VENV_PYTHON is the interpreter a fresh .venv is built from (3.12, owner's ruling 2026-09-28).
VENV_PYTHON ?= python3.12
venv: launch-config
	@$(VENV_PYTHON) -m venv .venv
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
# `make worktree-setup` copies no secret. `.env` reaches each Claude Code worktree through
# `.worktreeinclude` instead (owner's ruling, 2026-09-28), with `.claude/settings.local.json`
# and `.codex/config.toml`. T1 does not need it once the cache is warm.
# `--foreground`: a needed `npm ci` finishes before this target returns (the SessionStart hook
# omits the flag and backgrounds it); a current install is skipped, so a rerun is cheap.
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
	bash scripts/worktree-provision.sh --foreground "$$main"
	@echo "worktree ready. \`make harness\` should now be green without spending anything."

# scripts/worktree-provision.sh's app/node_modules clone/install/staleness logic
# (D-worktree-node-modules), proved against a throwaway two-tree fixture with a stubbed
# `npm` — never a real network install. ITS SELF-TEST IS NOT IN `make check`, on
# `catalog-index-selftest`'s precedent: it proves a mechanism this checkout's own session
# start and `make worktree-setup` already exercise on every worktree, one step further from
# the product. Run it when `scripts/worktree-provision.sh` or `scripts/serve.py`'s
# `npm_install_owed`/`NPM_RECEIPT` change.
worktree-provision-selftest:
	@bash scripts/worktree-provision-selftest.sh

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
# and `make docs-audit` has two rows that catch it lying — `check registry` against the
# recipe and the published prose. D18 (a generator may write, a gate may not) has no row
# yet that refuses a writing check on the commit path.
#
# python3, not $(PYTHON): a step-away tool that needs `make venv` first is not a step-away
# tool. Same rule as `status`, `map` and `docs-audit`.
explain:
	@python3 scripts/checks.py $(ARGS)


# T1-T9 and T11, the ten verification tests. No longer run automatically at turn
# end (D248) — a session runs this itself before saying something works.
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

# THE ONE GENERATOR INTO A DOC, AND IT GATES NOTHING (D18, amended 2026-09-17). It adds
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

# THE TEST PAGE, docs/TESTS.md. Writes, so it is never on the commit path (D18).
# `make docs-audit`'s `test purposes` row regenerates in memory and compares. ARGS=--write applies.
tests-page:
	@python3 scripts/tests_page.py $(ARGS)

# That generator, over a throwaway map it writes and drops. Not in `make check`,
# on `map-fix`'s own precedent above.
map-fix-selftest:
	@python3 scripts/map-fix.py --selftest

# A DELETING GENERATOR, AND IT GATES NOTHING (D18; D-ratchets-become-offender-lists). It deletes
# the STALE entries from the two shrinking offender lists, scripts/typed-interpunct-allow.json
# and scripts/markdown-spelling-allow.json, and re-keys a
# file that git's rename detection says moved. It never adds an entry. It reads with the rows'
# own functions, imported, so the pruner and the gates cannot disagree about what is stale.
# Previews. ARGS=--write applies.
# The write-time STE hook lints new prose, so no `ste offenders` list exists (D60, D280).
# scripts/markdown-spelling-allow.json is a shrinking offender list over the `identifier
# spelling` row's markdown half (D280).
#
# NOT A PREREQUISITE OF ANYTHING, never wired to a hook, and its self-test is not in
# `make check`, on `map-fix`'s precedent above: the rows that read these lists already run on
# every commit.
offenders-prune:
	@python3 scripts/offenders-prune.py $(ARGS)

# That pruner, in memory and in a throwaway repo. Not in `make check`, on the
# same precedent as `map-fix-selftest`.
offenders-prune-selftest:
	@python3 scripts/offenders-prune.py --selftest

# THE THIRD PIECE OF THE OWNER'S 2026-09-23 RULING (D-text-shape-checks, supersedes D284): a
# REPEATABLE, ON-DEMAND density pass that prints a CUT TABLE, never a gate (D18: it writes one
# receipt, `.serve/text-density.json`, gitignored). NOT A PREREQUISITE OF ANYTHING and never
# wired to a hook, `map-fix`'s own standing. It runs `app/tests/text-shape.spec.ts` with
# `TEXT_DENSITY=1`, so it reads the SAME populated fixture and the same loaded screens as the
# two gates, at 1440 and 390, whatever this checkout's own store holds. Playwright starts or
# reuses this checkout's own Vite (D43); every read is stubbed, so no store is read. One
# worker, `line` reporter, so `.serve/design-check.json` is never touched. ARGS reaches the
# script raw, e.g. `ARGS="--route '#/pricing' --top 8"`.
text-density:
	$(NPM_GUARD)
	@node scripts/text-density/density.mjs $(ARGS)

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

# Deliberately NOT a prerequisite of `check`, and never wired to a hook: every tree after
# the audit landed is clean because the hook blocked anything else, so a zero here cannot
# tell silent prevention from dead weight. It informs a retirement argument; it never makes
# one. Nonzero means the tool failed, never that a finding was found. See D18 and the
# script's own header.
audit-history:
	@python3 scripts/audit-history.py

# THE CLAIM `check registry` READS ON THE MAKEFILE SIDE. CLAUDE.md's own Commands
# section carries the same list; the row reconciles both against the recipe above,
# both ways, so this line and CLAUDE.md's cannot drift from each other or from it.
# make check        harness + docs-audit + revert-guard + port-agreement + set-hint-agreement +
#                   readiness-agreement + screen-freshness + screen-freshness-selftest +
#                   sigil-check + css-var-check + css-var-check-selftest +
#                   hand-search-selftest + token-literal-check +
#                   kit-adoption + ignore-check + lint + typecheck + audit-self-test +
#                   mutate-anchors + githooks-selftest + merge-selftest + revert-selftest +
#                   claim-selftest + decisions-selftest + debts-selftest + gates-selftest +
#                   submission-selftest + cid-selftest + pricearchive-selftest +
#                   archive-review-selftest + holdings-selftest + identity-checks-selftest +
#                   price-postings-selftest + product-history-selftest +
#                   sku-number-contradictions-selftest + readings-selftest + skus-selftest +
#                   identity-store-selftest + identity-binding-selftest +
#                   identity-readers-selftest + identity-cli-selftest + janitor-selftest +
#                   reap-selftest + silent-write-selftest + guard-shell-selftest +
#                   suite-lock-selftest + browser-scope-selftest + serve-selftest +
#                   sync-selftest + verdict-selftest + js-breakpoints-selftest +
#                   subagent-override-selftest + guard-scope-selftest +
#                   token-literal-check-selftest + kit-adoption-selftest + port-slots-selftest +
#                   match-selftest

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
	@$(MAKE) --no-print-directory revert-guard
	@$(MAKE) --no-print-directory port-agreement
	@$(MAKE) --no-print-directory set-hint-agreement
	@$(MAKE) --no-print-directory readiness-agreement
	@$(MAKE) --no-print-directory screen-freshness
	@$(MAKE) --no-print-directory screen-freshness-selftest
	@$(MAKE) --no-print-directory sigil-check
	@$(MAKE) --no-print-directory css-var-check
	@$(MAKE) --no-print-directory css-var-check-selftest
	@$(MAKE) --no-print-directory hand-search-selftest
	@$(MAKE) --no-print-directory token-literal-check
	@$(MAKE) --no-print-directory kit-adoption
	@$(MAKE) --no-print-directory ignore-check
	@$(MAKE) --no-print-directory lint
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
	@$(MAKE) --no-print-directory archive-review-selftest
	@$(MAKE) --no-print-directory holdings-selftest
	@$(MAKE) --no-print-directory identity-checks-selftest
	@$(MAKE) --no-print-directory price-postings-selftest
	@$(MAKE) --no-print-directory product-history-selftest
	@$(MAKE) --no-print-directory sku-number-contradictions-selftest
	@$(MAKE) --no-print-directory readings-selftest
	@$(MAKE) --no-print-directory skus-selftest
	@$(MAKE) --no-print-directory identity-store-selftest
	@$(MAKE) --no-print-directory identity-binding-selftest
	@$(MAKE) --no-print-directory identity-readers-selftest
	@$(MAKE) --no-print-directory identity-cli-selftest
	@$(MAKE) --no-print-directory janitor-selftest
	@$(MAKE) --no-print-directory reap-selftest
	@$(MAKE) --no-print-directory silent-write-selftest
	@$(MAKE) --no-print-directory guard-shell-selftest
	@$(MAKE) --no-print-directory suite-lock-selftest
	@$(MAKE) --no-print-directory browser-scope-selftest
	@$(MAKE) --no-print-directory serve-selftest
	@$(MAKE) --no-print-directory sync-selftest
	@$(MAKE) --no-print-directory verdict-selftest
	@$(MAKE) --no-print-directory js-breakpoints-selftest
	@$(MAKE) --no-print-directory subagent-override-selftest
	@$(MAKE) --no-print-directory guard-scope-selftest
	@$(MAKE) --no-print-directory token-literal-check-selftest
	@$(MAKE) --no-print-directory kit-adoption-selftest
	@$(MAKE) --no-print-directory port-slots-selftest
	@$(MAKE) --no-print-directory match-selftest

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
	@$(MAKE) --no-print-directory decisions-selftest
	@$(MAKE) --no-print-directory debts-selftest
	@$(MAKE) --no-print-directory gates-selftest
	@$(MAKE) --no-print-directory submission-selftest
	@$(MAKE) --no-print-directory cid-selftest
	@$(MAKE) --no-print-directory pricearchive-selftest
	@$(MAKE) --no-print-directory archive-review-selftest
	@$(MAKE) --no-print-directory holdings-selftest
	@$(MAKE) --no-print-directory identity-checks-selftest
	@$(MAKE) --no-print-directory price-postings-selftest
	@$(MAKE) --no-print-directory product-history-selftest
	@$(MAKE) --no-print-directory sku-number-contradictions-selftest
	@$(MAKE) --no-print-directory readings-selftest
	@$(MAKE) --no-print-directory skus-selftest
	@$(MAKE) --no-print-directory identity-store-selftest
	@$(MAKE) --no-print-directory identity-binding-selftest
	@$(MAKE) --no-print-directory identity-readers-selftest
	@$(MAKE) --no-print-directory identity-cli-selftest
	@$(MAKE) --no-print-directory revert-guard
	@$(MAKE) --no-print-directory janitor-selftest
	@$(MAKE) --no-print-directory reap-selftest
	@$(MAKE) --no-print-directory silent-write-selftest
	@$(MAKE) --no-print-directory guard-shell-selftest
	@$(MAKE) --no-print-directory suite-lock-selftest
	@$(MAKE) --no-print-directory browser-scope-selftest
	@$(MAKE) --no-print-directory serve-selftest
	@$(MAKE) --no-print-directory sync-selftest
	@$(MAKE) --no-print-directory verdict-selftest
	@$(MAKE) --no-print-directory js-breakpoints-selftest
	@$(MAKE) --no-print-directory subagent-override-selftest
	@$(MAKE) --no-print-directory guard-scope-selftest
	@$(MAKE) --no-print-directory token-literal-check-selftest
	@$(MAKE) --no-print-directory kit-adoption-selftest
	@$(MAKE) --no-print-directory port-slots-selftest
	@$(MAKE) --no-print-directory match-selftest
	@$(MAKE) --no-print-directory port-agreement
	@$(MAKE) --no-print-directory set-hint-agreement
	@$(MAKE) --no-print-directory readiness-agreement
	@$(MAKE) --no-print-directory screen-freshness
	@$(MAKE) --no-print-directory screen-freshness-selftest
	@$(MAKE) --no-print-directory sigil-check
	@$(MAKE) --no-print-directory css-var-check
	@$(MAKE) --no-print-directory css-var-check-selftest
	@$(MAKE) --no-print-directory hand-search-selftest
	@$(MAKE) --no-print-directory token-literal-check
	@$(MAKE) --no-print-directory kit-adoption
	@$(MAKE) --no-print-directory ignore-check
	@$(MAKE) --no-print-directory lint
	@$(MAKE) --no-print-directory typecheck

# CI RUNS `ci-check` AS THREE PARALLEL SHARDS (owner's word, 2026-09-28; D161, amended): the
# serial job took 600s on run 36509895299, and the shards together run exactly `ci-check`'s
# recipe. Each shard keeps D161's order, product first: `ci-check-product` is the harness and
# the checks of the product; the two guards shards are the guards' own self-tests, balanced by
# the times that run measured. `ci-check` stays the one command a session runs before pushing.
# `make docs-audit`'s `check registry` row fails when the shards' union is not `ci-check`'s
# recipe, target for target, with none missing and none run twice.
ci-check-product:
	@$(MAKE) --no-print-directory harness

ci-check-static:
	@$(MAKE) --no-print-directory docs-audit
	@$(MAKE) --no-print-directory port-agreement
	@$(MAKE) --no-print-directory set-hint-agreement
	@$(MAKE) --no-print-directory readiness-agreement
	@$(MAKE) --no-print-directory screen-freshness
	@$(MAKE) --no-print-directory sigil-check
	@$(MAKE) --no-print-directory css-var-check
	@$(MAKE) --no-print-directory token-literal-check
	@$(MAKE) --no-print-directory kit-adoption
	@$(MAKE) --no-print-directory ignore-check
	@$(MAKE) --no-print-directory lint
	@$(MAKE) --no-print-directory typecheck

ci-check-guards-1:
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
	@$(MAKE) --no-print-directory archive-review-selftest
	@$(MAKE) --no-print-directory holdings-selftest
	@$(MAKE) --no-print-directory identity-checks-selftest
	@$(MAKE) --no-print-directory price-postings-selftest
	@$(MAKE) --no-print-directory product-history-selftest
	@$(MAKE) --no-print-directory sku-number-contradictions-selftest
	@$(MAKE) --no-print-directory readings-selftest
	@$(MAKE) --no-print-directory skus-selftest
	@$(MAKE) --no-print-directory identity-store-selftest
	@$(MAKE) --no-print-directory identity-binding-selftest
	@$(MAKE) --no-print-directory identity-readers-selftest
	@$(MAKE) --no-print-directory identity-cli-selftest
	@$(MAKE) --no-print-directory revert-guard
	@$(MAKE) --no-print-directory janitor-selftest
	@$(MAKE) --no-print-directory reap-selftest
	@$(MAKE) --no-print-directory silent-write-selftest
	@$(MAKE) --no-print-directory guard-shell-selftest
	@$(MAKE) --no-print-directory suite-lock-selftest
	@$(MAKE) --no-print-directory browser-scope-selftest

ci-check-guards-2:
	@$(MAKE) --no-print-directory serve-selftest
	@$(MAKE) --no-print-directory sync-selftest
	@$(MAKE) --no-print-directory verdict-selftest
	@$(MAKE) --no-print-directory js-breakpoints-selftest
	@$(MAKE) --no-print-directory subagent-override-selftest
	@$(MAKE) --no-print-directory guard-scope-selftest
	@$(MAKE) --no-print-directory token-literal-check-selftest
	@$(MAKE) --no-print-directory kit-adoption-selftest
	@$(MAKE) --no-print-directory port-slots-selftest
	@$(MAKE) --no-print-directory match-selftest
	@$(MAKE) --no-print-directory screen-freshness-selftest
	@$(MAKE) --no-print-directory css-var-check-selftest
	@$(MAKE) --no-print-directory hand-search-selftest

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
		echo "audit-self-test: SKIPPED — this branch does not touch scripts/docs-audit.py or scripts/docs_audit/. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
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

# THE HAND-ROLLED-SEARCH ESLINT RULE (D271, F11c), PROVED ON FIXTURES OVER THE REAL
# `npx eslint --stdin`, THE SAME METHOD css-var-check-selftest USES. Not on the
# guard-scope roster: its real subject is app/eslint.config.js, a JS file no Python
# import can name, so `derive_subjects` has nothing to read (scripts/hand-search-selftest.py's
# own header argues this in full). Ungated in `make check`, the same as
# css-var-check-selftest and kit-adoption-selftest.
hand-search-selftest:
	$(NPM_GUARD)
	@python3 scripts/hand-search-selftest.py

# A CSS LITERAL EXACTLY EQUAL TO A DESIGN TOKEN'S VALUE, IN ITS OWN PROPERTY FAMILY
# (D256, token literals are pinned): `font-size: 22px` where `--bn-fs-2xl: 22px`
# means nothing here stops the two diverging the next time the scale moves. `css-var-check`'s
# sibling, opposite direction: that one catches a `var()` pointed at nothing, this one catches
# a value that should have BEEN a `var()`. Reads `tokens.css` itself on every run — no copied
# list. RATCHETED PER FILE (D-token-literals-are-pinned, D280's shape): main already carries
# many of these, so the gate is a ceiling on each file's OWN count, not zero. Writes nothing;
# `token-literal-check-pin.py --pin` is the one thing that may (D18). In `make check`, not the
# git hook — same reasons as `css-var-check` immediately above.
token-literal-check:
	@python3 scripts/token-literal-check.py

# THE GUARD IS NOT TRUSTED UNTIL IT HAS GONE RED ON THE DEFECT IT GUARDS: a literal equal to a
# token in its own family fails; the same value as var() passes; a var() fallback passes; the
# same value under a DIFFERENT family's property passes (4px matches --bn-r-xs under
# border-radius and --bn-1 under padding, never the other's); a raised per-file count fails; a
# lowered one passes and is only noted; an unseen file with findings fails; a stale allow-list
# entry fails; a shorthand is counted component by component. Wired last among the guard
# self-tests, `make check`'s own D161 order, beside `guard-scope-selftest`.
token-literal-check-selftest:
	@python3 scripts/token-literal-check.py --self-test

# EVERY SCREEN INHERITS THE PAGE SCAFFOLD (D-page-scaffold). The owner, 2026-09-23: a new page
# in the sidebar inherits the properties of the other pages. R1: every ROUTES view renders
# <Page> from the kit. R2: outside app/src/kit/, no screen hand-rolls a dialog, a search input,
# a <select>, a kit class, a date format or a money format. Read from the TypeScript AST, like
# scripts/user-strings.mjs. The exceptions are scripts/kit-adoption-allow.json, a SHRINKING
# offender list (file -> rule -> lane): an unlisted violation fails, and so does a stale entry,
# and so does a key the list at the merge-base with origin/main does not hold, unless its rule
# is not defined at the merge-base: a rule born on the branch, printed with its reason
# (read-only git; fails open, printed, with no merge-base). Never a pinned count. Writes nothing. Needs app/node_modules for typescript, so it is in
# `make check` and not the git hook: a fresh clone has no node_modules until `npm ci`.
kit-adoption:
	$(NPM_GUARD)
	@node scripts/kit-adoption.mjs

# THE GUARD IS NOT TRUSTED UNTIL IT HAS GONE RED ON THE DEFECT IT GUARDS: a route view without
# <Page>, a component named Page that is not the kit's, role="dialog" in a screen (and green
# inside app/src/kit/), a stale allow entry, an unlisted violation, each R2 shape both ways,
# R1's order, depth and cycles, a default-import view, and a new allow key against the base.
# The fixtures are in-memory maps of path -> source, so it writes nothing (D18). Wired last among
# the guard self-tests, `make check`'s own D161 order.
kit-adoption-selftest:
	$(NPM_GUARD)
	@node scripts/kit-adoption.mjs --self-test

# TWO THROWAWAY TREES FORCED INTO ONE PORT SLOT, AND A REAL VITE AND A REAL PLAYWRIGHT IN EACH
# (D-a-claimed-slot-and-a-server-that-names-its-checkout). It goes red on the 2026-09-24
# incident: with the identity check removed, a run in one tree passes against the other's
# server. Then both claim, each gets its own slot on both sides, and the run passes on its own
# server. It starts processes, binds ports and writes a registry under `mktemp -d`, so it is
# here and never in the commit hook (D18). It picks a slot whose ports are free, so it never
# reaches a real checkout's server, and it stops only the processes it started.
port-slots-selftest:
	$(NPM_GUARD)
	@if python3 scripts/guard-scope.py classify --target port-slots-selftest --base origin/main; then \
		python3 scripts/port-slots.py selftest; \
	else \
		echo "port-slots-selftest: SKIPPED — this branch does not touch the port-slot claim or its callers. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# FLT-06/04, UX-173: the one forgiving matcher, server side. `server/match.py` against every
# row of app/src/kit/match.cases.json (the filtering lane's own case table, so the server and
# the client are proved against one shared table rather than two that could drift), then
# `capture_server._match_rank` and `capture_server.do_search` end to end against a throwaway
# store — a real SQLite FTS5 index is what shows the candidate-step defect (a bare `54/132`
# or a hyphenated `heimerdinger-inventor` never reaching the rank step at all), which
# `_match_rank` alone cannot. `PKMNSCAN_HOME` is repointed to a temp directory per case, so
# the operator's own store is never opened. Stdlib only, no subprocess, no network — same
# standing as `decisions-selftest` right above its own cluster, not `cid-selftest`'s (D18
# still applies to the temp store it writes, which is why it gates rather than runs in the
# commit hook).
match-selftest:
	@if python3 scripts/guard-scope.py classify --target match-selftest --base origin/main; then \
		$(PYTHON) scripts/match-selftest.py; \
	else \
		echo "match-selftest: SKIPPED — this branch does not touch search, matching or their callers. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

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
#
# A STANDING MERGE INSTRUCTION CARRIES A NEEDED REBASE AND FORCE-PUSH, on a branch nobody else
# holds (owner ruling, 2026-09-18). The session does not stop and ask again for the rebase —
# only for whether to merge at all.
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

# app/src/readiness.ts against pipeline/decisions.py:blocking — the same blocking
# reasons on both sides of the wire.
readiness-agreement:
	@python3 scripts/readiness-agreement.py

# Every mutation anchor named in a guard's own test file still exists in the guard
# it targets. Fast (well under a second).
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
# THE OWNER RULED THIS ONE IN AND PATH GATING IN GENERAL OUT (D247, guard self-test
# scope). Nine targets in `make check` cost under a tenth of a second each, so a scope list per
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

# THE FIRST PATH GATE. What `make serve-selftest` reads, and whether this branch
# touches it. ARGS=list, or ARGS="classify --base <rev>". Derived from the self-test's
# own CARRY, reconciled by `make docs-audit`'s `serve scope` row BOTH WAYS. Fails open:
# no merge-base, an unreadable diff and an EMPTY diff all run the test.
# `make serve-selftest` was the only path-gated target from 2026-09-17 to 2026-09-20 —
# 70.1s of `make check`'s own total, copying the checkout with a STUB app/ so no screen
# change can reach it. `PKMNSCAN_SERVE_SCOPE=off` runs it regardless, printed in every
# skip.
serve-scope:
	@python3 scripts/serve-scope.py $(ARGS)

# That gate, including a CARRY drift it must catch.
serve-scope-selftest:
	@python3 scripts/serve-scope.py selftest

# THE SECOND PATH GATE (D247, owner's word 2026-09-20 on a fresh measurement): what each
# guard and product self-test reads. ARGS=list [--target <name>], or
# ARGS="classify --target <name> --base <rev>". A guard self-test proves a MECHANISM,
# never the product, so it cannot go stale between two moments: the guard script it
# proves changing, or its own fixture changing. THE SUBJECT LIST IS DERIVED FROM EACH
# SELF-TEST'S OWN SOURCE, never typed beside it — `scripts/guard-scope.py:
# derive_subjects` reads local-package imports and `Path`-style chains straight out of
# the test file. Only WHICH targets are gated is a hand-typed roster, on
# `serve-scope.py`'s own precedent, grown from nineteen entries as each joining
# self-test proved a real caller (`archive sweep --write`, `#/revenue`'s unsold-stock
# panel, `cards checks`, `emit`/`reprice apply`, `#/product`, `cards contradictions`,
# and, 2026-09-27, `match-selftest`, `browser-scope-selftest` and
# `port-slots-selftest`). Fails open exactly like `serve-scope`: no merge-base, an
# unreadable diff, an EMPTY diff, an unscoped target, and any exception all run the
# test. `PKMNSCAN_GUARD_SCOPE=off` runs every gated self-test regardless, printed in
# every skip. Reconciled BOTH WAYS by `make docs-audit`'s `guard scope` row: every
# roster target is wired into the Makefile and every wired recipe names a roster
# target. A THIRD GATE MECHANISM needs the owner's word again — a new roster entry
# under this same gate does not.
guard-scope:
	@python3 scripts/guard-scope.py $(ARGS)

# That gate, both-ways wiring included.
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

# SIX MORE GATED TARGETS, SEVENTEENTH THROUGH TWENTY-SECOND (D247, owner's word
# 2026-09-23): each self-test below cited "pricearchive-selftest.py's own precedent" as its
# reason to stay out of `make check`. That precedent went stale the moment the entry above
# was wired — its own header, and each of these six, say what real caller made the wait
# wrong. Same standing as `pricearchive-selftest` and `cid-selftest`: no network, no store on
# disk but a throwaway one, D18 — none of them gate on writing the operator's own store.
archive-review-selftest:
	@if python3 scripts/guard-scope.py classify --target archive-review-selftest --base origin/main; then \
		$(PYTHON) scripts/archive-review-selftest.py; \
	else \
		echo "archive-review-selftest: SKIPPED — this branch does not touch the archive review queue or its callers. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# pipeline/holdings.py, proved against in-memory fixtures, no store, no network:
# on-hand quantity, the gap guard, sealed-product exclusion. PATH GATED (D247).
holdings-selftest:
	@if python3 scripts/guard-scope.py classify --target holdings-selftest --base origin/main; then \
		$(PYTHON) scripts/holdings-selftest.py; \
	else \
		echo "holdings-selftest: SKIPPED — this branch does not touch unsold-stock holdings or its callers. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# pipeline/identity_checks.py's four stored-data checks, proved against literal
# fixtures, no store, no network. PATH GATED (D247).
identity-checks-selftest:
	@if python3 scripts/guard-scope.py classify --target identity-checks-selftest --base origin/main; then \
		$(PYTHON) scripts/identity-checks-selftest.py; \
	else \
		echo "identity-checks-selftest: SKIPPED — this branch does not touch the stored-data identification checks or their callers. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# TWO INVOCATIONS: the real run, then `--mutate-to-upsert`, which MUST itself go red inside
# store/postings.py's mutated copy for the append-only property to count as proved — see the
# self-test's own header.
price-postings-selftest:
	@if python3 scripts/guard-scope.py classify --target price-postings-selftest --base origin/main; then \
		$(PYTHON) scripts/price-postings-selftest.py && \
		$(PYTHON) scripts/price-postings-selftest.py --mutate-to-upsert; \
	else \
		echo "price-postings-selftest: SKIPPED — this branch does not touch the price-postings ledger or its callers. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# pipeline/productview.py and server/pipeline_routes.py:do_product_history, proved
# against a throwaway store: archive-hit and live-fallback. PATH GATED (D247).
product-history-selftest:
	@if python3 scripts/guard-scope.py classify --target product-history-selftest --base origin/main; then \
		$(PYTHON) scripts/product-history-selftest.py; \
	else \
		echo "product-history-selftest: SKIPPED — this branch does not touch the per-product history route or its callers. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# pipeline/sku_number_contradictions.py, proved against literal fixtures and
# duck-typed Market fakes, no store, no network. PATH GATED (D247).
sku-number-contradictions-selftest:
	@if python3 scripts/guard-scope.py classify --target sku-number-contradictions-selftest --base origin/main; then \
		$(PYTHON) scripts/sku-number-contradictions-selftest.py; \
	else \
		echo "sku-number-contradictions-selftest: SKIPPED — this branch does not touch the SKU self-contradiction check or its callers. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

# Does every card's name still resolve to its photograph? Reads the whole corpus,
# so it is NOT in `make check`. Three verdicts, and the third is `not known`.
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

# THE STORE-OWNED SKU TABLE, PROVED AGAINST A THROWAWAY STORE (identity-follows-sku.md §3.2,
# lane 0). Rows equal distinct ids, a second adopt over unchanged files changes nothing, an
# older file never overwrites a newer one's facts, a changed fact writes one
# `sku_facts_changed` event and keeps the row, `store/skus.py` has no delete path anywhere,
# and a version-10 store upgrades to 11 with every other table's rows intact.
#
# IN `check`, NEVER IN THE GIT HOOK: it writes a temp store under `mktemp -d` (D18). Answers
# from the tree alone (its one real-fixture read is `fixtures/riftbound_export_untouched.csv`,
# committed), so it is in `ci-check` too.
skus-selftest:
	@$(PYTHON) scripts/skus-selftest.py

# THE ONE WRITER, PROVED IN MEMORY (identity-follows-sku.md §4.1, lane 1). `bind_sku` stamps
# name/number/printed_total/rarity/set_name/condition off a skus table row for a Pokemon
# card (the catalog Number split), a Riftbound card (kept verbatim) and a Riftbound
# double-sided token cell (`T02 // T03`); `unbind_sku` round-trips a rebind back to the
# first binding, every field but `bound_at` restored exactly; SkuUnknown and GameMismatch
# both refuse before touching the card, the events list or the skus table;
# `record_identification` writes only `read_*` on a bound card and the identity too on an
# unbound one.
#
# IN `check`, NEVER IN THE GIT HOOK. Writes nothing to disk at all — no store, no `mktemp`
# (D18 does not even apply) — so it is in `ci-check` too.
identity-store-selftest:
	@$(PYTHON) scripts/identity-store-selftest.py

# THE MIGRATION'S CLASSIFIER AND THE MERGED D242 REPORT, PROVED AGAINST LITERAL
# FIXTURES (identity-follows-sku.md §5.5, §7, lane 2). Every class T1-T6 and `sku_unknown`,
# in §7.2's own order; the human-bound exclusion §5.5 requires (`answer`/`group_answer`/
# `correction`/`confirm` never re-flagged); both report halves (§4.3's three audit failures,
# and §5.5's name half/number half). `./pkmnscan cards identity` and `scripts/
# identity-replay.py` both import this module rather than re-deriving the classifier, so
# this is the one place its logic is proved.
#
# IN `check`, NEVER IN THE GIT HOOK. Writes nothing to disk at all — no store, no `mktemp`
# (D18 does not even apply) — so it is in `ci-check` too.
identity-binding-selftest:
	@$(PYTHON) scripts/identity-binding-selftest.py

# THE REPLAY, BEFORE ANY WRITE (identity-follows-sku.md §7.4, lane 2). Takes a COPY of a
# real store (`sqlite3 <store> ".backup <copy>"`, never the live file) and asserts the six
# checks §7.4 names, importing `pipeline/identity_binding.py`'s own classifier rather than
# re-deriving it. Never `check`-gated: it needs a store copy the owner supplies, and a
# fixture cannot stand in for "did the owner's own store move in six minutes". Read-only —
# never opens `Store().write()`, never touches the copy it is given.
identity-replay:
	@$(PYTHON) scripts/identity-replay.py $(ARGS)

# THE EVIDENCE READERS, PROVED IN MEMORY (identity-follows-sku.md §5.1, lane 4 — added on
# a review finding, HIGH, 2026-09-24). `cli/requeue.py:identified` and
# `cli/resolve.py:store_payload` both carry a bound card's DISPUTED read name, never its
# bound SKU's own catalog row (D253's own subject), and both refuse loudly — never a
# silent catalog echo — on a bound card whose evidence was never recorded. THREE SEPARATE
# PROCESSES, `price-postings-selftest`'s own two-process shape extended to three: each
# `--mutate-*` run mutates `cli/resolve.py:card_reading`'s own body through a `.bak` copy,
# restored in its own `finally` before that process exits either way, and must turn at
# least one assertion red or the run itself fails (a mutation that survives means the case
# it names is not actually being tested).
#
# IN `check`, NEVER IN THE GIT HOOK — a hook context that could be interrupted mid-mutation
# is not where writing (transiently) to a real tracked file belongs.
identity-readers-selftest:
	@$(PYTHON) scripts/identity-readers-selftest.py && \
		$(PYTHON) scripts/identity-readers-selftest.py --mutate-identity-fields && \
		$(PYTHON) scripts/identity-readers-selftest.py --mutate-no-fallback && \
		$(PYTHON) scripts/identity-readers-selftest.py --mutate-no-refusal

# THE CLI WRITERS, AGAINST A REAL THROWAWAY STORE AND THE REAL CLI DISPATCH
# (identity-follows-sku.md §4.2, lane 3b). `pkmnscan emit` upserts the matched export row
# into `skus` and THEN binds through `Inventory.bind_sku` — proved by binding on a store
# whose `skus` table starts empty, so a successful bind is proof the upsert ran first. A
# re-identification of an already-bound card (`cli/cmd_identify.py:_read_disputes_for`)
# writes only `read_*`; the bound identity does not move. `pkmnscan join --export` and
# `pkmnscan reconcile --live` each fill the table from EVERY row of the file they read, not
# only the rows a card matched.
#
# IN `check`, NEVER IN THE GIT HOOK: it writes a temp store under `mktemp -d` (D18). Answers
# from the tree alone (its one real-fixture read is `fixtures/sv09_export_untouched.csv`,
# committed), so it is in `ci-check` too.
identity-cli-selftest:
	@$(PYTHON) scripts/identity-cli-selftest.py

.PHONY: submission-selftest readings-selftest skus-selftest identity-store-selftest identity-binding-selftest identity-replay identity-readers-selftest identity-cli-selftest

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
.PHONY: janitor janitor-selftest janitor-install serve-selftest sync-selftest ci-check ci-check-product ci-check-static ci-check-guards-1 ci-check-guards-2

.PHONY: lan-check
# Is the LAN URL still good? DNS, both servers, and a real write. Reaches the
# network, so it never gates a commit.
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
#
# WILL NOT SERVE A PRIMARY CHECKOUT OFF MAIN (D158, D138). `PKMNSCAN_SERVE_MAIN=off` overrides,
# printed in every refusal.
up:
	$(PORT_CLAIM)
	@$(PYTHON) scripts/serve.py up $(ARGS)

# Stop the one process `make up` started.
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
	$(PORT_CLAIM)
	@python3 scripts/reap_mark.py dev; exec npm --prefix app run dev

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
	$(PORT_CLAIM)
	@python3 scripts/reap_mark.py server; exec $(PYTHON) server/capture_server.py

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
# the command it guards, so `ARGS` can never reach npm. `PKMNSCAN_SUITE_LOCK=off` overrides
# the lock outright, printed in every refusal (D122).
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
# docs/debts/ section 8 measured a one-in-thirteen red whose only known mechanism is "the
# suite around it", and more workers on one box is more suite around it. On the rig `PW_ARGS`
# is for a session that wants one spec — `PW_ARGS=tests/brand.spec.ts` — and nothing else.
# Each shard leaves its own `.serve/design-check.json`; on a runner that is one file per job.
design-check:
	$(NPM_GUARD)
	$(PORT_CLAIM)
	@rm -f .serve/design-check.json
	@python3 scripts/reap_mark.py design-check; python3 scripts/suite-lock.py run $(ARGS) -- npm --prefix app run design-check -- $(PW_ARGS)

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
	@if python3 scripts/guard-scope.py classify --target browser-scope-selftest --base origin/main; then \
		python3 scripts/browser-scope.py selftest; \
	else \
		echo "browser-scope-selftest: SKIPPED — this branch does not touch the browser-matrix classifier or its spec map. PKMNSCAN_GUARD_SCOPE=off runs it anyway."; \
	fi

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
	$(PORT_CLAIM)
	@rm -f .serve/design-check.json
	@python3 scripts/reap_mark.py design-check; DESIGN_CHECK_QUIET=1 python3 scripts/suite-lock.py run $(ARGS) -- npm --prefix app run design-check -- $(PW_ARGS)

# eslint over app/, config and rules in app/eslint.config.js. It began 2026-08-13 as the two
# guards docs/decisions/'s v1 bug table promised — no `facingMode` (bug 3), no `split(",")`
# CSV parsing (bug 2) — and has since gained a rule per bug this project caught itself: the
# two-argument `.then` that swallows its own success handler's throw, and `localStorage`
# outside D27's carve-out. THE COUNT IS DELIBERATELY NOT STATED: this comment said "two" while
# the config held four, and the config file is the register. The pattern is the point — a bug
# becomes a guard, so the list only grows.
#
# RUFF JOINED THIS TARGET 2026-09-01 (D82), ON A SLICE MEASURED AGAINST THIS TREE, NOT ON
# WHAT IT ENABLES BY DEFAULT. Zero-config `ruff check .` found 2,131 things on this repo,
# 79% of them three pyupgrade rules rewriting `Dict`/`Optional[X]` to PEP 585/604 syntax —
# a runtime TypeError on the system Python 3.9.6 that runs `scripts/`, unless ruff is told the target
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

# eslint over app/, ruff over the Python packages (D82).
lint:
	$(NPM_GUARD)
	@npm --prefix app run lint
	$(VENV_GUARD)
	$(RUFF_GUARD)
	@$(PYTHON) -m ruff check .

# `tsc --noEmit` over app/.
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
# Extra flags for `scripts/demo-record.py`, past what `demo-record` already passes. Empty by
# default — an ordinary `make demo` keeps its real network, the same "best effort" reads
# every other price-history route already makes (D216).
DEMO_RECORD_ARGS ?=
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

# Curate real card photographs into the tracked set. Needs a store:
# SOURCE=<checkout>. Refuses any photo carrying a QR.
demo-photos:
	@[ -n "$(SOURCE)" ] || { \
		echo "SOURCE=<checkout> is required — the store whose photographs to curate."; \
		echo "  e.g. make demo-photos SOURCE=~/Developer/pkmnscan"; \
		exit 1; }
	@$(PYTHON) scripts/demo-photos.py --source "$(SOURCE)" \
	  --count $(DEMO_PHOTO_COUNT) --joinable $(DEMO_PHOTO_JOINABLE)

# THE PUBLISHED DEMO IS THE OWNER'S REAL STORE, SCRUBBED (owner's ruling, 2026-09-26,
# `D-demo-mirror`, docs/specs/demo.md §13 — supersedes `demo-seed`'s invented one below as
# what `demo-static` publishes). `scripts/demo-mirror.py` reads a store COPY into gitignored
# `demo-mirror/` and writes the scrubbed output to the tracked `demo-assets/mirror/`: every
# buyer "Jane Doe N", every address "123 Demo Way", a shipping export rebuilt from the
# ledger, and every photograph QR-cleared and cropped under a 512 MB cap. THE OWNER'S STORE
# NEVER LEAVES THIS MAC — only `demo-assets/mirror/` is committed, and CI never runs this
# target at all: it has no store to read, and installs that committed output instead
# (`demo-mirror-install`).
demo-mirror:
	@[ -n "$(SOURCE)" ] || { \
		echo "SOURCE=<checkout> is required — the real store to snapshot and scrub."; \
		echo "  e.g. make demo-mirror SOURCE=~/Developer/pkmnscan"; \
		exit 1; }
	@$(PYTHON) scripts/demo-mirror.py --source "$(SOURCE)" --home $(DEMO_HOME)

# Re-scrub from the existing gitignored snapshot, no SOURCE and no re-read of the real store —
# for iterating on the scrub or the recorder without paying the snapshot cost again.
demo-mirror-rebuild:
	@$(PYTHON) scripts/demo-mirror.py --home $(DEMO_HOME)

# CI's own step: the committed scrub, installed into app/demo/ and app/public/demo/photos/.
# Reads no store and contacts no network. `demo-static` builds from this.
demo-mirror-install:
	@$(PYTHON) scripts/demo-mirror.py --install

# Record the demo's price histories into NEW committed fixtures, on the owner's Mac only.
#
# The history host refuses the honest User-Agent (D216), and the owner allows the browser
# signature from the owner's own machine, never from CI. So this runs by hand, when the owner
# chooses, with PKMNSCAN_TCG_USER_AGENT set, and writes a new dated directory under
# fixtures/demo-price-history/. It refuses to overwrite one. The seed and the recorder read the
# newest. NO WORKFLOW CALLS THIS TARGET.
demo-histories:
	@$(PYTHON) scripts/demo-histories.py $(ARGS)

# The store alone, built on the curated photographs.
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

# A SECOND, small, real box, opt-in only — never on `demo-seed` alone (D18: the flag reaches
# a generator, never a gate). Set as a TARGET-SPECIFIC variable, which GNU Make propagates
# into every prerequisite this target pulls in, direct and indirect — so `demo-static`'s own
# chain through `demo` to `demo-seed` carries it, and a bare `make demo-seed` never does.
demo-record: export PKMNSCAN_DEMO_EXTRA_REAL := 1
demo-record:
	@PKMNSCAN_HOME=$(DEMO_HOME) $(PYTHON) scripts/demo-record.py $(DEMO_RECORD_ARGS)

# The bundle without the build — what to run after changing a wire shape, so `git status`
# shows the recording moving with the contract it was recorded against.
demo: demo-seed demo-record

# demo-mirror-install, then a static build to dist-demo/. DEMO_BASE=<path> is
# where it will be served from.
demo-static: demo-mirror-install
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

# `demo-freshness`, which compared app/demo/bundle.json against the wire it was recorded
# against, and `demo-determinism`, which compared two `make demo` runs' recorded CONTENT
# byte for byte, are BOTH RETIRED (D295 amended, L5, 2026-09-27, the test-audit plan's Q5 —
# "cut the old seed guards"). Neither ever gated a commit or a publish. Both proved only the
# invented seed's own bundle, which the published demo has not built from since D295 — the
# published mirror never goes near `app/demo/bundle.json`. `demo-determinism` found a real
# defect once — 97 `bound_at` values differed between two runs before `bind_sku` took an
# `at` parameter, invisible to `demo-freshness` — recorded here so the finding is not lost
# with the targets.
