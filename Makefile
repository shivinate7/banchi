# PKMNSCAN
#
# Empty targets exit 1. A target that exits 0 with nothing to run is a lie the rest of
# the project would be built on top of — `make check` green means every check ran.

.DEFAULT_GOAL := help
.PHONY: help status map explain harness check ignore-check docs-audit vale audit-self-test githooks-selftest merge merge-selftest port-agreement set-hint-agreement screen-freshness sigil-check icloud-sweep audit-history dev server screenshot design-check lint typecheck venv launch-config worktree-setup hooks up down restart launch-agent demo demo-photos demo-seed demo-record demo-static demo-preview demo-freshness

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
	@echo "  make explain      what \`make check\` runs, and what each row is worth."
	@echo "                    ARGS=<target> for one entry in full."
	@echo "  make venv         .venv + requirements.txt   (before the first harness run, and"
	@echo "                    again whenever requirements.txt changes — safe to re-run)"
	@echo "  make worktree-setup  venv + T1's banked cache, for a fresh git worktree"
	@echo "  make launch-config   .claude/launch.json for THIS checkout's dev port (D43)"
	@echo "  make hooks        arm the git hooks          (once, and again after every clone)"
	@echo "  make harness      T1-T8 verification tests. Run at turn end by the Stop hook."
	@echo "  make docs-audit   markdown vs the code it describes. Reports; never writes."
	@echo "  make vale         prose style over every tracked .md. Needs vale; never gates."
	@echo "  make audit-history  which docs-audit checks ever fired. Diagnostic; never gates."
	@echo "  make audit-self-test  the checker checks itself. In \`check\`, never in the git hook."
	@echo "  make githooks-selftest  main's guard, proved in a throwaway repo. Never in the git hook."
	@echo "  make merge-selftest  the merge wrapper's local half, in a throwaway repo and worktree."
	@echo "  make janitor-selftest  the sweep, proved against a throwaway clone. In \`check\`, never in the hook."
	@echo "  make port-agreement  server/ports.py and app/devPort.ts answer the same numbers."
	@echo "  make set-hint-agreement  the capture screen and the export fetch resolve a set hint alike."
	@echo "  make screen-freshness  every server write in app/ has a way back. Needs node."
	@echo "  make sigil-check   a bare \`#\` on a screen is a COUNT, never a store key (D92)."
	@echo "  make ignore-check  every path a worktree provisions is gitignored, link or not (D47)."
	@echo "  make icloud-sweep  list iCloud conflict copies. ARGS=--delete removes the identical ones."
	@echo "  make janitor      what a finished session left behind. ARGS=--confirm reaps tier 2."
	@echo "  make ci-check     what a fresh clone can prove: everything in check but vale."
	@echo "  make janitor-install  copy the sweep to ~/.claude/bin so every repo's hooks can reach it."
	@echo "  make lan-check    is the LAN URL still good? DNS, both servers, and a real"
	@echo "                    write. Reaches the network, so it never gates a commit."
	@echo "  make check        harness + docs-audit + audit-self-test + githooks-selftest +"
	@echo "                    merge-selftest + janitor-selftest + port-agreement +"
	@echo "                    set-hint-agreement + screen-freshness + sigil-check +"
	@echo "                    ignore-check + lint + vale + typecheck"
	@echo
	@echo "  ./pkmnscan identify <capture-dir>                 submit, wait, collect. COSTS MONEY."
	@echo "  ./pkmnscan join     <run-dir> --export <csv>      resolve against the export. Free."
	@echo "  ./pkmnscan emit     <run-dir>                     write import CSVs. Free."
	@echo "  ./pkmnscan reconcile <run-dir> <staged-export>    confirm what TCGplayer staged."
	@echo "  make up           BOTH servers, detached, and the capture server reloads itself"
	@echo "                    when you edit Python. Prints the link. Start here."
	@echo "  make merge        merge a PR and move main onto it (D42). ARGS=<n> previews;"
	@echo "                    ARGS=\"<n> --confirm\" performs it. On the owner's word only."
	@echo "  make down         stop them.  make restart  stop and start."
	@echo "  make launch-agent start at login, so the link is always live. Main tree only."
	@echo "                    ARGS=--remove to undo it."
	@echo "  make dev          Vite app on :5173. Blocks — background it in a session."
	@echo "  make server       Python capture server. :8000 in the main tree, its own port in a"
	@echo "                    worktree (D43) — it prints which. Blocks — background it."
	@echo "  make screenshot   render the views in scripts/views.txt to captures/ui/"
	@echo "  make design-check docs/DESIGN.md's Fulfillment floors, asserted in a browser."
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
	@$(MAKE) --no-print-directory merge-selftest
	@$(MAKE) --no-print-directory janitor-selftest
	@$(MAKE) --no-print-directory port-agreement
	@$(MAKE) --no-print-directory set-hint-agreement
	@$(MAKE) --no-print-directory screen-freshness
	@$(MAKE) --no-print-directory sigil-check
	@$(MAKE) --no-print-directory ignore-check
	@$(MAKE) --no-print-directory lint
	@$(MAKE) --no-print-directory vale
	@$(MAKE) --no-print-directory typecheck

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
	@$(MAKE) --no-print-directory githooks-selftest
	@$(MAKE) --no-print-directory merge-selftest
	@$(MAKE) --no-print-directory janitor-selftest
	@$(MAKE) --no-print-directory port-agreement
	@$(MAKE) --no-print-directory set-hint-agreement
	@$(MAKE) --no-print-directory screen-freshness
	@$(MAKE) --no-print-directory sigil-check
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

# D92 — a bare `#` on an owner-side screen is D58's COUNT, and three renderers spelled the
# store key the same way. ON THE COMMIT PATH, unlike its neighbours here: it writes nothing,
# needs no venv and no node, and reads only tracked source, so none of D18's reasons apply.
# Its own self-test runs with it — cheap enough (27 cases over strings) that splitting them
# into a second target would cost more to explain than to run.
sigil-check:
	@python3 scripts/sigil-check.py --self-test
	@python3 scripts/sigil-check.py

# HERE AND NOT IN THE GIT HOOK, for the reason stated above `check` and for a second one of
# its own. D18 is the first: this writes — a bare repo, a clone, commits, pushes — and nothing
# that writes may run on the path that decides whether a commit proceeds. The second is that
# it exercises the guard by VIOLATING it, so a version wired into the commit path would be
# refusing its own commits.
githooks-selftest:
	@bash scripts/githooks-selftest.sh

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
	@bash scripts/merge-selftest.sh

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
# EXIT 1 IS NOT A FAILURE HERE, AND THAT DIFFERS FROM icloud-sweep ON PURPOSE. The sweep exits 1
# when something is waiting on `--confirm`, which for a preview is the ORDINARY answer rather
# than a rare finding — a conflict copy is unusual, a reapable worktree is Tuesday. So `make`
# swallows 1 and nothing else: a crash, a refusal to run, any code above 1 still fails loudly.
# The code itself is kept because a scheduled caller wants to know whether there is work.
janitor:
	@python3 scripts/janitor.py $(ARGS); s=$$?; [ $$s -le 1 ] || exit $$s

# In `check`, never in the git hook: it writes a temp tree and signals the processes it spawned
# there, which is D18's line. Same standing as merge-selftest and githooks-selftest.
janitor-selftest:
	@bash scripts/janitor-selftest.sh

# THE SWEEP, WHERE EVERY REPO CAN REACH IT. `~/.claude/settings.json` hooks apply to every
# session in every project, but the command they name has to exist without this checkout in
# sight — so the two files are COPIED, exactly as `make hooks` copies the git hooks out of the
# tree rather than pointing at it. A copy can go stale, which is why `make status` compares it
# and says so, the same way it reports a stale hooks-armed directory. One press, once per
# machine; run it again after this tree's copy changes.
janitor-install:
	@mkdir -p $$HOME/.claude/bin
	@cp scripts/janitor.py scripts/session-teardown.sh $$HOME/.claude/bin/
	@chmod +x $$HOME/.claude/bin/janitor.py $$HOME/.claude/bin/session-teardown.sh
	@echo "installed to ~/.claude/bin: janitor.py, session-teardown.sh"
	@echo "  hook it up once, in ~/.claude/settings.json, so it covers every repo:"
	@echo '    "SessionEnd":     [{"hooks": [{"type": "command", "timeout": 60,'
	@echo '                        "command": "$$HOME/.claude/bin/session-teardown.sh"}]}]'
	@echo '    "WorktreeRemove": [{"hooks": [{"type": "command", "timeout": 60,'
	@echo '                        "command": "$$HOME/.claude/bin/session-teardown.sh"}]}]'
	@echo '  then the sweep reaches any clone: ~/.claude/bin/janitor.py --root <path>'

# IS THE LAN URL STILL GOOD? The owner reaches this product from a phone at
# `http://pkmnscan.lan:5173`, and nothing in this repo knows that name — the DHCP reservation
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
.PHONY: janitor janitor-selftest janitor-install ci-check

.PHONY: lan-check
lan-check:
	@python3 scripts/lan-check.py

# BOTH SERVERS, DETACHED, AND THE CAPTURE SERVER RESTARTS ITSELF WHEN YOU EDIT PYTHON.
# `make dev` and `make server` below are untouched and still work; this is additive.
#
# The restart is the point rather than the convenience. docs/GATES.md records a run whose
# whole-second timestamps came from a server started before the millisecond fix landed — "a
# long-running `make server` outlives the fix that was written for it", filed there as a
# discipline. A discipline nobody can keep is what this replaces.
#
# DO NOT RUN THESE ALONGSIDE `make dev` / `make server`. The second one loses: strictPort on
# the Vite side and EADDRINUSE on the capture side, both loudly. That is deliberate — a second
# server that quietly moved to another port would serve a DIFFERENT store (D43).
#
# None of these four goes near `make check` or the git hook. D18: nothing that writes may run
# on the path that decides whether a commit proceeds, and `launch-agent` writes to ~/Library,
# which is the strongest form of that rule this repo has had to apply.
up:
	@$(PYTHON) scripts/serve.py up

down:
	@$(PYTHON) scripts/serve.py down

restart:
	@$(PYTHON) scripts/serve.py restart

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
dev:
	$(NPM_GUARD)
	@$(PYTHON) scripts/serve.py guard-foreground
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
