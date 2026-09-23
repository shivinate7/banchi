#!/usr/bin/env bash
# `make worktree-provision-selftest` — scripts/worktree-provision.sh's app/node_modules
# provisioning (D-worktree-node-modules), proved against a throwaway fixture.
#
# WHY A FIXTURE RATHER THAN THE REAL TREE. Four cases matter: a fresh worktree cloning from
# main, a worktree whose lockfile has moved needing a real install, an already-current
# worktree doing nothing at all, and a lockfile bump AFTER provisioning being caught rather
# than left to surface later as a confusing Playwright-version mismatch. None of the four
# may touch this checkout's own app/node_modules or spend a real network install to prove.
#
# `npm` IS STUBBED. A tiny script on a fixture-only PATH stands in for it: `--prefix X ci`
# writes a placeholder package into X/node_modules and exits 0, anything else exits 1. That
# is what makes the SLOW PATH provable without network, without the ~80 MB, and without the
# minutes a real `npm ci` costs — and the exit-1 default is how "no npm ci ran when the tree
# was already current" gets CAUGHT rather than merely assumed.
#
# WHY IT IS NOT IN THE GIT HOOK. D18: it writes — two throwaway trees. Nothing that writes
# may run on the path that decides whether a commit proceeds. It IS in `make check`.

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
  # The staleness read reuses scripts/serve.py FOR REAL, so the fixture needs it and its own
  # dependency chain importable — real files, copied rather than symlinked, because
  # `Path(__file__).resolve()` would follow a symlinked scripts/ straight back to THIS
  # checkout's real REPO_ROOT and read/write the real app/node_modules instead of the
  # fixture's. `store/__init__.py` is replaced with an EMPTY stub: the real one cascades
  # into the whole store/ package for a symbol serve.py never reads (`store.files` is
  # imported as a submodule, which does not require the package's own `__init__` to do
  # anything at all).
  mkdir -p "$tmp/wt/scripts" "$tmp/wt/server" "$tmp/wt/store"
  cp "$ROOT/scripts/serve.py" "$tmp/wt/scripts/serve.py"
  cp "$ROOT/scripts/primary_sync.py" "$tmp/wt/scripts/primary_sync.py"
  cp "$ROOT/envfile.py" "$tmp/wt/envfile.py"
  cp "$ROOT/server/ports.py" "$tmp/wt/server/ports.py"
  cp "$ROOT/store/files.py" "$tmp/wt/store/files.py"
  : > "$tmp/wt/store/__init__.py"
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

echo
echo "worktree-provision-selftest: $pass ok, $fail FAIL"
[ "$fail" -eq 0 ]
