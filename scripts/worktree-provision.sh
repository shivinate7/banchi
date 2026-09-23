#!/usr/bin/env bash
# Provisions (or reports on) a worktree's three heaviest untracked-but-needed pieces of
# harness/app state: the T1 replay cache, the T1 image mirror, and app/node_modules. Shared
# by scripts/worktree-guard.sh (the SessionStart hook, which runs unasked and fails open)
# and `make worktree-setup` (a person asking explicitly) — before this file existed, both
# carried their own copy of the same cp/ln/python-one-liner sequence, so D47's image-mirror
# fix had to land in both files by hand and the two could silently drift the next time
# either changed. One copy now; a fix here reaches both callers by construction.
#
# Takes the MAIN working tree's path as its last argument. Writes nothing to stdin,
# prompts for nothing, and every failure here is reported rather than fatal — this is
# provisioning, not a gate (D18 already keeps both callers off the commit path; this
# script does not change that).
#
# --prefix TEXT prepends TEXT to every line this script prints, so each caller keeps its
# own voice — scripts/worktree-guard.sh's lines all read "worktree-guard: ...", `make
# worktree-setup`'s do not — without duplicating the eleven messages themselves.

set -uo pipefail

prefix=""
if [ "${1:-}" = "--prefix" ]; then
  prefix="${2:-}"
  shift 2
fi
main="${1:?usage: worktree-provision.sh [--prefix TEXT] <main-worktree-path>}"

say() { printf '%s%s\n' "$prefix" "$1"; }

# SELF-INVOCATION GUARD. Both callers already refuse to invoke this script from the main
# tree — scripts/worktree-guard.sh exits before calling it, `make worktree-setup` refuses
# before calling it — but this script is the shared primitive, and a future caller, or a
# hand run, could skip that check. Getting it wrong is not merely wrong: with main == cwd,
# every "copy from main" step below is a copy onto ITSELF. `cp -c` REFUSES a self-copy, and
# the code that used to follow a failed clone assumed the failure was disk-related and
# RECOVERED by `rm -rf app/node_modules` — deleting the real checkout's own install, not a
# half-written clone. Checked twice, independently, because either input could be wrong on
# its own: the resolved cwd against the resolved $main ARGUMENT (a caller could pass the
# wrong path), and the resolved cwd against what THIS checkout's OWN git metadata says the
# main tree is (a caller could pass the right path while this script still runs FROM main).
# `git rev-parse --git-common-dir` is the exact derivation both callers already use.
#
# THE CWD IS RESOLVED TO ITS GIT TOPLEVEL, NEVER COMPARED RAW. Running from a subdirectory
# of main — `<main>/app`, say — is still running FROM main, and a raw `pwd -P` would miss
# it: `<main>/app` is never equal to `<main>`. `git rev-parse --show-toplevel` answers "the
# root of whichever tree cwd is in", resolved a second time with `pwd -P` because
# `--show-toplevel` does not itself resolve symlinks on every git version. A cwd outside any
# git tree (show-toplevel fails) falls back to the raw, unresolved cwd — the same check this
# guard always had, never a new gap.
here_toplevel="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -n "$here_toplevel" ]; then
  here_real="$(cd "$here_toplevel" 2>/dev/null && pwd -P)"
else
  here_real="$(pwd -P 2>/dev/null)"
fi
main_real="$(cd "$main" 2>/dev/null && pwd -P)"
common_dir="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"
own_main_real=""
if [ -n "$common_dir" ]; then
  case "$common_dir" in /*) ;; *) common_dir="$(cd "$common_dir" 2>/dev/null && pwd -P)" ;; esac
  [ -n "$common_dir" ] && own_main_real="$(dirname "$common_dir")"
fi
if [ -n "$here_real" ] && { [ "$here_real" = "$main_real" ] || [ "$here_real" = "$own_main_real" ]; }; then
  say "refusing: this checkout IS the main working tree — there is nothing to provision INTO."
  say "  \`make worktree-setup\` and the SessionStart hook already refuse before calling this"
  say "  script; a hand run of it should refuse too, rather than clone or delete the real"
  say "  app/node_modules onto itself."
  exit 0
fi

# The cache first: local, ~90 KB, no network, and the SAFETY one — without it T1 has
# nothing to replay and refuses rather than spending real money on a submission nobody
# asked for. Skipped if this worktree already has one: a person or an earlier session may
# have banked a fresher run here, and provisioning must never clobber it silently.
if [ ! -d harness/.cache ]; then
  if [ -d "$main/harness/.cache" ]; then
    if mkdir -p harness/.cache 2>/dev/null && cp -R "$main/harness/.cache/." harness/.cache/ 2>/dev/null; then
      say "copied harness/.cache from the main working tree (T1 can replay)."
    else
      say "could not copy harness/.cache from $main — run \`make worktree-setup\`."
    fi
  else
    say "NOTE: $main has no harness/.cache — T1 will refuse until a run is banked there."
  fi
fi

# The mirror: 133 MB, immutable, additive-only, so it is linked rather than copied.
# `fixtures.IMAGES_DIR` is the ONE resolution (env var, then that checkout's `.env`, then
# the in-repo default) — asked of the MAIN tree's own harness rather than re-derived here,
# because re-deriving that precedence in shell is exactly how this drifted out of sync the
# first time the mirror moved (D47): the old inline copy in each caller kept a hardcoded
# path after the real answer changed, and neither one said so.
if [ ! -e harness/images ]; then
  mirror="$(cd "$main" 2>/dev/null && python3 -c 'import sys; sys.path.insert(0, "."); from harness.eval import fixtures; print(fixtures.IMAGES_DIR)' 2>/dev/null)"
  [ -n "$mirror" ] || mirror="$main/harness/images"
  if [ ! -d "$mirror" ]; then
    say "NOTE: no image mirror at $mirror — T1 will re-download 151 images."
  elif mkdir -p harness 2>/dev/null && ln -s "$mirror" harness/images 2>/dev/null; then
    say "linked harness/images -> $mirror (133 MB, immutable/additive — T1 scores without downloading 151 files)."
  else
    say "could not link harness/images -> $mirror — T1 will re-download them."
  fi
fi

# app/node_modules (D-worktree-node-modules). This used to be REPORT-ONLY, per the
# Makefile's NPM_GUARD argument that an implicit install hides a slow network step.
# NPM_GUARD's outcome is still protected: a
# session is never left waiting on a bare `npm ci` it did not see coming. What changed is
# that "reported" no longer means "nothing happens" — a same-machine copy costs no network
# at all, and a real install is backgrounded and logged rather than silently skipped.
#
# THE STALENESS QUESTION IS NOT REASKED HERE. `scripts/serve.py:npm_install_owed` already
# answers "does the installed tree match app/package-lock.json", against the receipt
# `make up`'s own supervisor writes on every successful build (`NPM_RECEIPT`,
# `app/node_modules/.pkmnscan-lock`, a bare digest). Reusing it rather than a second marker
# means this step and the supervisor can never disagree about what "current" means, and a
# worktree that later runs `make up` finds its own provisioning already credited rather than
# reinstalled a second time. `npm` missing from this venv, a broken serve.py import, or any
# other exception all answer "unknown" — never "not owed" — because a false "current" is the
# exact bug this exists to fix (the owner's stale-node_modules trap: a confusing Playwright-
# version error instead of a plain "reinstall").
npm_owed="$(python3 - <<'PY' 2>/dev/null
import sys
sys.path.insert(0, "scripts")
try:
    import serve
    print("owed" if serve.npm_install_owed() else "current")
except Exception:
    print("unknown")
PY
)"

# Written after EITHER path below succeeds, so `make up`'s own supervisor (which reads this
# same file) sees this provisioning as a real, current install rather than reinstalling it.
write_npm_receipt() {
  python3 - <<'PY' 2>/dev/null
import sys
sys.path.insert(0, "scripts")
try:
    import serve
    (serve.REPO_ROOT / serve.NPM_RECEIPT).write_text(serve.lock_digest() + "\n", "utf-8")
except Exception:
    pass
PY
}

# Is MAIN's OWN install trustworthy? Byte-identical lockfiles only say the CLONE would be
# aimed at the right target — they say nothing about whether main's own node_modules was
# ever actually installed for that lockfile. Cloning a stale (or never-installed) main and
# then writing OUR OWN receipt for it would make `npm_install_owed()` answer "current" over
# packages that do not match the lockfile — the exact trap this file exists to close,
# self-inflicted. Reuses the SAME `npm_install_owed()`, pointed at main's own root, so this
# can never disagree with what main's own `make up` supervisor would say about main. An
# import failure here answers "stale" — never "current" — because the unsafe direction is
# trusting an install this could not actually check.
main_install_current() {
  python3 - "$1" <<'PY' 2>/dev/null
import sys
sys.path.insert(0, "scripts")
from pathlib import Path
try:
    import serve
    print("current" if not serve.npm_install_owed(root=Path(sys.argv[1])) else "stale")
except Exception:
    print("stale")
PY
}

if [ "$npm_owed" = "owed" ]; then
  cloned=0
  # FAST PATH, NO NETWORK: only when the main tree's install exists, its lockfile is
  # byte-identical to this one's — never "close enough" — AND main's own install is itself
  # trustworthy (see `main_install_current` above). `cp -c` is APFS's clonefile(2): copy-on-
  # write, so the ~200 MB tree costs under a second and almost no disk (measured on this
  # Mac). node_modules/.bin holds RELATIVE symlinks (`../pkg/bin.js`), confirmed on this
  # tree, so a clone at a new path still resolves — nothing here points back at main.
  if [ -f app/package-lock.json ] && [ -d "$main/app/node_modules" ] \
     && [ -f "$main/app/package-lock.json" ] \
     && cmp -s app/package-lock.json "$main/app/package-lock.json" 2>/dev/null \
     && [ "$(main_install_current "$main")" = "current" ]; then
    if mkdir -p app/node_modules 2>/dev/null \
       && cp -c -R "$main/app/node_modules/." app/node_modules/ 2>/dev/null; then
      cloned=1
    else
      # A half-written clone (out of disk, cp -c unsupported here) is worse than none — it
      # would read as "present" and never retried. Better to fall through to the real install.
      rm -rf app/node_modules 2>/dev/null
    fi
  fi

  if [ "$cloned" = 1 ]; then
    write_npm_receipt
    say "cloned app/node_modules from the main tree (APFS copy-on-write, under a second) — tsc, lint and design-check are ready."
  else
    # SLOW PATH, VISIBLE: the lockfiles differ, main has no install, main's own install is
    # not trustworthy, or the clone failed. `npm ci` runs in the BACKGROUND — never blocking
    # session start on a minutes-long network step, which is exactly what NPM_GUARD was
    # written to keep from happening silently. It is announced, and it is logged, which is
    # what makes a backgrounded install different from a hidden one.
    mkdir -p .serve 2>/dev/null
    npm_log=".serve/npm-install.log"
    npm_lock_dir=".serve/npm-install.lock"

    # A LOCK AROUND THE LAUNCH. Two invocations of this script — two SessionStart hooks
    # racing, or a hook overlapping a hand-run `make worktree-setup` — could each see "no
    # install yet" and each background their own `npm ci` into the SAME app/node_modules,
    # racing each other's writes. `mkdir` is atomic on this filesystem: only one concurrent
    # caller can create the same directory, so it IS the lock — no `flock` binary ships on
    # this Mac, and a directory lock needs none.
    #
    # LIVENESS IS `scripts/serve.py:live_pid`, NOT A BARE `kill -0`. A pid alone can lie: the
    # OS recycles pids, and a bare `kill -0` on a stale one would misread SOME OTHER
    # PROCESS's pid as this worktree's own npm ci still running — the exact defect
    # `live_pid` was written to close for the capture-server supervisor, and this script
    # already imports the module that carries it. It checks the pid AND that the live
    # process's own argv still names this launch (`_needle`), never a second, narrower
    # version of that same check.
    npm_child_write() {
      # The recorded argv carries the ABSOLUTE app path, never the relative one `npm
      # --prefix app ci` is typed with — `_needle` searches for the last argument starting
      # with `/`, exactly `live_pid`'s own house rule, and a relative "app" would leave it
      # falling back to the bare word "ci", which is a weak needle any process could contain.
      python3 - "$1" "$(pwd -P)/app" <<'PY' 2>/dev/null
import sys
sys.path.insert(0, "scripts")
try:
    import serve
    child = serve.Child("npm-install", "npm-install.pid", "npm-install.log")
    serve.write_pidfile(child, int(sys.argv[1]), ["npm", "--prefix", sys.argv[2], "ci"])
except Exception:
    pass
PY
    }
    npm_child_clear() {
      python3 - <<'PY' 2>/dev/null
import sys
sys.path.insert(0, "scripts")
try:
    import serve
    serve.clear_pidfile(serve.Child("npm-install", "npm-install.pid", "npm-install.log"))
except Exception:
    pass
PY
    }
    npm_lock_holder_alive() {
      # An exception (broken venv, unreadable serve.py) answers "alive": the unsafe
      # direction for a mutual-exclusion lock is assuming free when it cannot tell, which
      # would let a second `npm ci` start into the same tree the first is still writing.
      python3 - <<'PY' 2>/dev/null
import sys
sys.path.insert(0, "scripts")
try:
    import serve
    child = serve.Child("npm-install", "npm-install.pid", "npm-install.log")
    print("alive" if serve.live_pid(child) is not None else "dead")
except Exception:
    print("alive")
PY
    }
    launch_npm_ci() {
      ( npm --prefix app ci >"$npm_log" 2>&1
        rc=$?
        [ "$rc" -eq 0 ] && write_npm_receipt
        npm_child_clear
        rm -rf "$npm_lock_dir"
      ) </dev/null >/dev/null 2>&1 &
      npm_child_write "$!"
      disown 2>/dev/null || true
    }

    if [ -d "$npm_lock_dir" ] && [ "$(npm_lock_holder_alive)" = "alive" ]; then
      say "an install is already running — log at $npm_log. Starting nothing."
    else
      [ -d "$npm_lock_dir" ] && { rm -rf "$npm_lock_dir" 2>/dev/null; npm_child_clear; }   # stale: reclaim it
      if mkdir "$npm_lock_dir" 2>/dev/null; then
        if command -v npm >/dev/null 2>&1; then
          launch_npm_ci
          say "app/ dependencies are missing or stale (no trustworthy install to clone from $main) — running \`npm --prefix app ci\` in the BACKGROUND (~80 MB, network). Log: $npm_log. lint, typecheck and design-check will fail until it finishes; re-run \`make worktree-setup\` or check the log."
        else
          rmdir "$npm_lock_dir" 2>/dev/null
          say "app/ dependencies are absent and npm is not on PATH."
          say "  Fix: install Node, then npm --prefix app install"
        fi
      else
        # Lost the race to `mkdir` between the staleness check and here — another run's
        # `mkdir` won it in between. That run is the one installing now; nothing to do.
        say "an install is already running — log at $npm_log. Starting nothing."
      fi
    fi
  fi
elif [ "$npm_owed" = "unknown" ] && [ ! -d app/node_modules ]; then
  # The old report-only line, kept as the fallback for the one case the reused primitive
  # cannot answer: install Python broken, or serve.py itself unreadable. Fails open to
  # exactly what this step used to do everywhere, never to silence.
  say "app/ dependencies are absent (gitignored, so they do not travel)."
  say "\`make harness\` does not need them. lint, typecheck and design-check do:"
  say "  npm --prefix app install"
fi

exit 0
