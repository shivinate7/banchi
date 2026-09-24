#!/usr/bin/env bash
# `make worktree-provision-selftest` — scripts/worktree-provision.sh's app/node_modules
# provisioning (D257), proved against a throwaway fixture.
#
# WHY A FIXTURE RATHER THAN THE REAL TREE. Eight cases matter: a fresh worktree cloning from
# main, a worktree whose lockfile has moved needing a real install, an already-current
# worktree doing nothing at all, a lockfile bump AFTER provisioning being caught rather than
# left to surface later as a confusing Playwright-version mismatch, a self-invocation (main
# == cwd) never deleting the real install, that same refusal from a SUBDIRECTORY of main, a
# stale main never being cloned as though it were current, and two racing invocations never
# both installing at once. None of the eight may touch this checkout's own app/node_modules
# or spend a real network install to prove.
#
# `npm` IS STUBBED. A tiny script on a fixture-only PATH stands in for it: `--prefix X ci`
# writes a placeholder package into X/node_modules and exits 0, anything else exits 1. That
# is what makes the SLOW PATH provable without network, without the ~80 MB, and without the
# minutes a real `npm ci` costs — and the exit-1 default is how "no npm ci ran when the tree
# was already current" gets CAUGHT rather than merely assumed.
#
# WHY IT IS NOT IN THE GIT HOOK. D18: it writes — two throwaway trees. Nothing that writes
# may run on the path that decides whether a commit proceeds. NOT in `make check` either, on
# `catalog-index-selftest`'s precedent — see the Makefile recipe for why.

set -uo pipefail          # NOT -e: every case must run and be scored

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$HERE/worktree-provision.sh"
ROOT="$(cd "$HERE/.." && pwd)"
[ -f "$SCRIPT" ] || { echo "no worktree-provision.sh beside this script"; exit 1; }

pass=0
fail=0
say()  { printf '  %-6s %s\n' "$1" "$2"; }
ok()   { pass=$((pass + 1)); say "ok" "$1"; }
bad()  { fail=$((fail + 1)); say "FAIL" "$1"; }

tmp="$(mktemp -d "${TMPDIR:-/tmp}/pkmnscan-worktree-provision.XXXXXX")" || { echo "cannot make a temp dir"; exit 1; }
trap 'rm -rf "$tmp"' EXIT

# A stub `npm`, so the SLOW PATH is provable without a network install.
mkdir -p "$tmp/bin"
cat > "$tmp/bin/npm" <<'NPM'
#!/usr/bin/env bash
if [ "$1" = "--prefix" ] && [ "$3" = "ci" ]; then
  target="$2"
  mkdir -p "$target/node_modules"
  echo stub > "$target/node_modules/left-pad.js"
  printf 'ran\n' >> "${STUB_LOG:?}"
  exit 0
fi
exit 1
NPM
chmod +x "$tmp/bin/npm"

lock_digest() { shasum -a 256 "$1" | awk '{print $1}'; }

# The staleness read reuses scripts/serve.py FOR REAL, so any fixture directory that runs
# worktree-provision.sh needs it and its own dependency chain importable — real files,
# copied rather than symlinked, because `Path(__file__).resolve()` would follow a symlinked
# scripts/ straight back to THIS checkout's real REPO_ROOT and read/write the real
# app/node_modules instead of the fixture's. `store/__init__.py` is replaced with an EMPTY
# stub: the real one cascades into the whole store/ package for a symbol serve.py never
# reads (`store.files` is imported as a submodule, which does not require the package's own
# `__init__` to do anything at all).
install_serve_deps() {
  local dest="$1"
  mkdir -p "$dest/scripts" "$dest/server" "$dest/store"
  cp "$ROOT/scripts/serve.py" "$dest/scripts/serve.py"
  cp "$ROOT/scripts/primary_sync.py" "$dest/scripts/primary_sync.py"
  cp "$ROOT/envfile.py" "$dest/envfile.py"
  cp "$ROOT/server/ports.py" "$dest/server/ports.py"
  cp "$ROOT/store/files.py" "$dest/store/files.py"
  : > "$dest/store/__init__.py"
}

# A two-tree fixture: MAIN with a real (fake) install and its own package-lock.json, and a
# worktree carrying only a package-lock.json — the SAME bytes when $1 is "same", different
# bytes when $1 is "differ".
fresh_fixture() {
  rm -rf "$tmp/main" "$tmp/wt"
  mkdir -p "$tmp/main/app/node_modules/.bin" "$tmp/wt/app"
  echo '{"name":"a","lockfileVersion":3}' > "$tmp/main/app/package-lock.json"
  echo 'module.exports = 1;' > "$tmp/main/app/node_modules/acorn.js"
  ln -s ../acorn.js "$tmp/main/app/node_modules/.bin/acorn"
  if [ "$1" = "differ" ]; then
    echo '{"name":"a","lockfileVersion":3,"differs":true}' > "$tmp/wt/app/package-lock.json"
  else
    cp "$tmp/main/app/package-lock.json" "$tmp/wt/app/package-lock.json"
  fi
  install_serve_deps "$tmp/wt"
}

run_provision() {
  ( cd "$tmp/wt" && PATH="$tmp/bin:$PATH" STUB_LOG="$tmp/npm.log" bash "$SCRIPT" "$tmp/main" \
      >"$tmp/out.log" 2>&1 )
}

# Bounded: at most 100 attempts of 0.05s, a 5s ceiling — `seq` names the bound.
wait_for() {
  for _ in $(seq 1 100); do
    [ -e "$1" ] && return 0
    sleep 0.05
  done
  return 1
}

# ---------------------------------------------------------------------- case 1: fast clone

fresh_fixture same
: > "$tmp/npm.log"
run_provision
if [ -f "$tmp/wt/app/node_modules/acorn.js" ] && [ -L "$tmp/wt/app/node_modules/.bin/acorn" ]; then
  ok "fast path clones node_modules when the lockfiles match"
else
  bad "fast path did not clone node_modules when the lockfiles matched"
fi
if grep -q "cloned app/node_modules" "$tmp/out.log"; then
  ok "fast path announces the clone"
else
  bad "fast path did not announce the clone"
fi
if [ -f "$tmp/wt/app/node_modules/.pkmnscan-lock" ] \
   && [ "$(cat "$tmp/wt/app/node_modules/.pkmnscan-lock")" = "$(lock_digest "$tmp/wt/app/package-lock.json")" ]; then
  ok "fast path writes a receipt matching the lockfile digest"
else
  bad "fast path did not write a matching receipt"
fi
if [ -s "$tmp/npm.log" ] 2>/dev/null; then
  bad "fast path ran npm ci when a clone was possible"
else
  ok "fast path never runs npm ci"
fi

# --------------------------------------------------------------------- case 2: slow path

fresh_fixture differ
: > "$tmp/npm.log"
run_provision
wait_for "$tmp/wt/app/node_modules/.pkmnscan-lock" || true
if [ -f "$tmp/wt/app/node_modules/left-pad.js" ]; then
  ok "slow path installs when the lockfiles differ"
else
  bad "slow path did not install when the lockfiles differed"
fi
if grep -q "ran" "$tmp/npm.log" 2>/dev/null; then
  ok "slow path actually invoked npm ci"
else
  bad "slow path never invoked npm ci"
fi
if grep -q "BACKGROUND" "$tmp/out.log"; then
  ok "slow path announces the background install and its log"
else
  bad "slow path did not announce the background install"
fi
if [ -f "$tmp/wt/.serve/npm-install.log" ]; then
  ok "slow path leaves a log under .serve/"
else
  bad "slow path left no log under .serve/"
fi
if [ -f "$tmp/wt/app/node_modules/.pkmnscan-lock" ] \
   && [ "$(cat "$tmp/wt/app/node_modules/.pkmnscan-lock")" = "$(lock_digest "$tmp/wt/app/package-lock.json")" ]; then
  ok "slow path writes a receipt once the background install finishes"
else
  bad "slow path did not write a receipt after installing"
fi

# --------------------------------------------------------------- case 3: already current

fresh_fixture same
run_provision                                  # first pass: provisions
wait_for "$tmp/wt/app/node_modules/.pkmnscan-lock" || true
: > "$tmp/npm.log"
before="$(find "$tmp/wt/app/node_modules" -type f | sort)"
run_provision                                  # second pass: should do nothing
after="$(find "$tmp/wt/app/node_modules" -type f | sort)"
if [ "$before" = "$after" ] && [ ! -s "$tmp/npm.log" ]; then
  ok "an already-current node_modules is left alone"
else
  bad "a current node_modules was touched again"
fi

# ----------------------------------------------------------------- case 4: stale receipt

fresh_fixture same
run_provision                                  # provisions, receipt for the ORIGINAL lockfile
wait_for "$tmp/wt/app/node_modules/.pkmnscan-lock" || true
echo '{"name":"a","lockfileVersion":3,"bumped":true}' > "$tmp/wt/app/package-lock.json"
cp "$tmp/wt/app/package-lock.json" "$tmp/main/app/package-lock.json"    # main moved too
: > "$tmp/npm.log"
run_provision
if [ -f "$tmp/wt/app/node_modules/.pkmnscan-lock" ] \
   && [ "$(cat "$tmp/wt/app/node_modules/.pkmnscan-lock")" = "$(lock_digest "$tmp/wt/app/package-lock.json")" ]; then
  ok "a lockfile bump after provisioning is caught and re-provisioned"
else
  bad "a lockfile bump after provisioning went undetected"
fi

# ---------------------------------------------------------- case 5: self-invocation guard
#
# The unfixed script compares app/package-lock.json against $main/app/package-lock.json —
# the SAME FILE, so `cmp -s` trivially matches — then `cp -c -R` a directory onto itself,
# which APFS refuses, and the `else` arm ran `rm -rf app/node_modules`: the REAL install,
# not a half-written clone. `install_serve_deps` is copied into $tmp/main too, so an
# UNGUARDED script still reaches that code path here rather than stopping earlier for an
# unrelated reason. A MISMATCHED receipt is planted on purpose: with no receipt at all,
# `npm_install_owed()` trusts an existing node_modules and the vulnerable branch is never
# reached — which is exactly why the very first draft of this case passed on the unfixed
# script too, proving nothing. The mismatch is what makes main == cwd read as "owed".
#
# THE REFUSAL ASSERTION NAMES THE GUARD'S OWN DISTINCTIVE TEXT, not a generic "refus"
# substring — the second review found the generic form would still pass with the guard
# entirely disabled, because the harness/.cache and harness/images steps ABOVE it print
# their own unrelated "T1 will refuse until a run is banked there" NOTE. "IS the main
# working tree" appears nowhere else in this script's output.
#
# `$tmp/main` IS A REAL GIT REPOSITORY (`git init`), which case 5 itself does not need — a
# raw cwd already equals a raw main argument here — but case 5b right below does: it is what
# lets `git rev-parse --show-toplevel` resolve a SUBDIRECTORY of main back up to main's own
# root.

rm -rf "$tmp/main" "$tmp/wt"
mkdir -p "$tmp/main/app/node_modules/.bin"
git init -q "$tmp/main"
echo '{"name":"a","lockfileVersion":3}' > "$tmp/main/app/package-lock.json"
echo 'module.exports = 1;' > "$tmp/main/app/node_modules/acorn.js"
echo 'REAL DATA — must survive a self-invocation' > "$tmp/main/app/node_modules/real-marker.txt"
printf '%064d\n' 0 > "$tmp/main/app/node_modules/.pkmnscan-lock"
install_serve_deps "$tmp/main"
: > "$tmp/npm.log"
( cd "$tmp/main" && PATH="$tmp/bin:$PATH" STUB_LOG="$tmp/npm.log" bash "$SCRIPT" "$tmp/main" \
    >"$tmp/out-self.log" 2>&1 )
if [ -f "$tmp/main/app/node_modules/real-marker.txt" ]; then
  ok "self-invocation (main == cwd) never deletes the real node_modules"
else
  bad "self-invocation (main == cwd) DELETED the real node_modules"
fi
if grep -q "IS the main working tree" "$tmp/out-self.log"; then
  ok "self-invocation announces the refusal"
else
  bad "self-invocation did not announce the refusal"
fi

# ------------------------------------------------- case 5b: self-invocation, subdirectory
#
# Running from `<main>/app` is still running FROM main — the second review's item 2. The
# unfixed-for-item-2 guard compared a RAW cwd against main, which `<main>/app` never
# equals; the fix resolves cwd to its git toplevel first.

: > "$tmp/npm.log"
( cd "$tmp/main/app" && PATH="$tmp/bin:$PATH" STUB_LOG="$tmp/npm.log" bash "$SCRIPT" "$tmp/main" \
    >"$tmp/out-self-subdir.log" 2>&1 )
if [ -f "$tmp/main/app/node_modules/real-marker.txt" ]; then
  ok "self-invocation from a SUBDIRECTORY of main never deletes the real node_modules"
else
  bad "self-invocation from a subdirectory of main DELETED the real node_modules"
fi
if grep -q "IS the main working tree" "$tmp/out-self-subdir.log"; then
  ok "self-invocation from a subdirectory announces the refusal"
else
  bad "self-invocation from a subdirectory did not announce the refusal"
fi

# ------------------------------------------------------- case 6: main's own install stale
#
# Lockfiles matching is not enough — main's OWN node_modules must match main's OWN receipt,
# or a clone would write a receipt in THIS worktree that lies about what got installed.

fresh_fixture same
printf '%064d\n' 0 > "$tmp/main/app/node_modules/.pkmnscan-lock"     # a receipt for NOTHING main's lockfile is now
: > "$tmp/npm.log"
run_provision
wait_for "$tmp/wt/app/node_modules/.pkmnscan-lock" || true
if [ -f "$tmp/wt/app/node_modules/left-pad.js" ] && [ ! -f "$tmp/wt/app/node_modules/acorn.js" ]; then
  ok "a stale main install is never cloned — the slow path runs instead"
else
  bad "a stale main install was cloned anyway (the fast path trusted a stale main)"
fi
if [ -f "$tmp/wt/app/node_modules/.pkmnscan-lock" ] \
   && [ "$(cat "$tmp/wt/app/node_modules/.pkmnscan-lock")" = "$(lock_digest "$tmp/wt/app/package-lock.json")" ]; then
  ok "this worktree still ends up with a receipt matching its OWN lockfile"
else
  bad "this worktree did not end up with a correct receipt"
fi

# ------------------------------------------------------------ case 7: concurrent installs
#
# Two invocations, launched together, over a SLOW stub npm so the race window is wide open.
# `wait` blocks for both — no polling loop, and none is needed.

fresh_fixture differ
: > "$tmp/npm.log"
cat > "$tmp/bin/npm" <<'NPM'
#!/usr/bin/env bash
if [ "$1" = "--prefix" ] && [ "$3" = "ci" ]; then
  target="$2"
  sleep 1
  mkdir -p "$target/node_modules"
  echo stub > "$target/node_modules/left-pad.js"
  printf 'ran\n' >> "${STUB_LOG:?}"
  exit 0
fi
exit 1
NPM
chmod +x "$tmp/bin/npm"

( cd "$tmp/wt" && PATH="$tmp/bin:$PATH" STUB_LOG="$tmp/npm.log" bash "$SCRIPT" "$tmp/main" \
    >"$tmp/out-race-1.log" 2>&1 ) &
race1=$!
( cd "$tmp/wt" && PATH="$tmp/bin:$PATH" STUB_LOG="$tmp/npm.log" bash "$SCRIPT" "$tmp/main" \
    >"$tmp/out-race-2.log" 2>&1 ) &
race2=$!
wait "$race1" 2>/dev/null
wait "$race2" 2>/dev/null
wait_for "$tmp/wt/app/node_modules/.pkmnscan-lock" || true
ran_count="$(grep -c '^ran$' "$tmp/npm.log" 2>/dev/null || echo 0)"
if [ "$ran_count" -eq 1 ]; then
  ok "two concurrent runs launch only one npm ci"
else
  bad "two concurrent runs launched $ran_count npm ci processes, expected 1"
fi
if grep -qi "already running" "$tmp/out-race-1.log" "$tmp/out-race-2.log" 2>/dev/null; then
  ok "the losing run reports an install is already running"
else
  bad "neither concurrent run reported an already-running install"
fi

# ------------------------------------------------- case 9: a recycled pid is never trusted
#
# item 1 of the third review: a bare `kill -0` cannot tell a live process from a RECYCLED
# pid — the OS reassigning a dead holder's number to something that is not an npm install at
# all. Plants a lock naming a REAL, currently-running process (a `sleep`, started here) whose
# actual argv does not match — exactly what `live_pid`'s argv check exists to catch, and
# what a bare `kill -0` cannot: that check alone would read this pid as this worktree's own
# install still running and refuse to reclaim it, forever.

fresh_fixture differ
: > "$tmp/npm.log"
sleep 30 &
unrelated_pid=$!
mkdir -p "$tmp/wt/.serve/npm-install.lock"
python3 - "$tmp/wt" "$unrelated_pid" "$tmp/wt/app" <<'PY' 2>/dev/null
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1] + "/scripts")
import serve
child = serve.Child("npm-install", "npm-install.pid", "npm-install.log")
serve.write_pidfile(child, int(sys.argv[2]), ["npm", "--prefix", sys.argv[3], "ci"], root=Path(sys.argv[1]))
PY
run_provision
wait_for "$tmp/wt/app/node_modules/.pkmnscan-lock" || true
kill "$unrelated_pid" 2>/dev/null
if [ -f "$tmp/wt/app/node_modules/left-pad.js" ]; then
  ok "a lock naming a live but UNRELATED process (recycled pid) is reclaimed, not trusted"
else
  bad "a lock naming a live but unrelated process blocked the install forever"
fi

echo
echo "worktree-provision-selftest: $pass ok, $fail FAIL"
[ "$fail" -eq 0 ]
