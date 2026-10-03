#!/usr/bin/env bash
# The main guard checks itself, in a repository built and destroyed for the purpose.
# Protects: The main-branch guard hooks refuse a local move and a push of main, proved in a throwaway repository.
# Governs: D18, D42
#
# WHY THIS EXISTS. `scripts/githooks/reference-transaction` and its pre-push sibling cannot be
# exercised in this repository without arming them here first, and `core.hooksPath` is stored
# in the common .git dir — one setting shared by every worktree of this clone. Flipping it to
# try something out would reach into whatever concurrent sessions are mid-commit. So the test
# builds its own origin and its own clone in a temporary directory, points core.hooksPath at
# THESE hook files, and runs the real gestures against them.
#
# WHY IT IS NOT IN THE GIT HOOK. It writes — a bare repo, a clone, commits, pushes. D18: nothing
# that writes may run on the path that decides whether a commit proceeds. It runs in `make check`,
# which a person invokes, exactly as `make audit-self-test` does and for the same reason.
#
# WHAT IT CANNOT PROVE. That the hooks are ARMED in the real clone. That is one line of config
# and `make hooks` is what sets it; `make hooks` prints the resolved path so the answer is
# visible rather than assumed. A green run here means the files behave, not that git is
# calling them.

set -uo pipefail

# Defaults to the TRACKED hooks beside this script. Overridable so the same nineteen cases
# can be run against the INSTALLED copy in the git common dir — `make hooks` copies rather
# than points now (D42, amended), and a copy that lands wrong is a guard that reads as armed
# and does nothing. Proving the files behave is not the same claim as proving the install did.
HOOKS_DIR="${PKMNSCAN_HOOKS_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/githooks" && pwd)}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pass=0
fail=0

tmp="$(mktemp -d "${TMPDIR:-/tmp}/pkmnscan-githooks.XXXXXX")" || { echo "cannot make a temp dir"; exit 1; }
cleanup() { rm -rf "$tmp"; }
trap cleanup EXIT

say()  { printf '  %-6s %s\n' "$1" "$2"; }
ok()   { pass=$((pass + 1)); say "ok" "$1"; }
bad()  { fail=$((fail + 1)); say "FAIL" "$1"; }

# Runs a command with output swallowed and compares its exit status against what the guard
# is supposed to do. `refuse` means non-zero, `allow` means zero — asserting the DIRECTION
# rather than a specific code, because a hook that refuses is allowed to pick its own.
# A refusal must be OURS. Git declines plenty of things on its own — it will not delete the
# branch you have checked out, and it will not push what is already up to date — and a case
# that goes green on git's own refusal is testing nothing. So `refuse` asserts both a non-zero
# exit AND the marker these hooks print, which is why they print one.
expect() {
  local want="$1" what="$2"; shift 2
  local out status
  out="$("$@" 2>&1)"; status=$?
  case "$want:$status" in
    refuse:0)
      bad "$what — expected a refusal, got through"
      printf '%s\n' "$out" | sed 's/^/         /' ;;
    refuse:*)
      case "$out" in
        # pre-commit's own opsec rules print "COMMIT BLOCKED:" rather than "REFUSED:" —
        # both mark a refusal this hook chose, not one git declined on its own.
        *REFUSED:*|*"COMMIT BLOCKED:"*) ok "$what — refused" ;;
        *) bad "$what — refused, but not by the hook (no REFUSED:/COMMIT BLOCKED: marker)"
           printf '%s\n' "$out" | sed 's/^/         /' ;;
      esac ;;
    allow:0)   ok  "$what — allowed" ;;
    allow:*)   bad "$what — expected to be allowed, exit $status"
               printf '%s\n' "$out" | sed 's/^/         /' ;;
  esac
}

echo "githooks self-test  (hooks: $HOOKS_DIR)"

# ---------------------------------------------------------------- a repo and its origin
git init -q --bare "$tmp/origin.git"
git init -q -b main "$tmp/work"
cd "$tmp/work" || exit 1
git config user.email selftest@example.com
git config user.name  selftest
git config commit.gpgsign false
git remote add origin "$tmp/origin.git"

# Seeded with the guard OFF, so the fixture itself is not the thing under test.
echo one > file.txt
git add file.txt
PKMNSCAN_MAIN=off git commit -qm "seed"
PKMNSCAN_MAIN=off git push -q -u origin main 2>/dev/null

git config core.hooksPath "$HOOKS_DIR"

# ---------------------------------------------------------------------------- the cases
echo "  -- the ordinary path stays open --"
git switch -q -c feature 2>/dev/null
echo two > file.txt
git add file.txt
expect allow "commit on a branch" git commit -qm "work on a branch"
expect allow "push a branch to origin" git push -q -u origin feature

echo "  -- main does not move locally --"
git switch -q main
echo three > file.txt
git add file.txt
expect refuse "commit directly on main" git commit -qm "straight onto main"
git reset -q
git checkout -q -- file.txt

expect refuse "fast-forward a branch into main" git merge --ff-only feature
expect refuse "reset main onto a local commit"  git reset --hard feature

# BOTH OF THESE RUN OFF main, and that is the whole point of the pair. Git answers first when
# you aim them at the branch you are standing on — "cannot force update the branch checked out
# at ..." — so run from main they were testing git and not the hook. Run from `feature` they
# reach the ref transaction, and `git branch -D main` is what found the deletion bug: it
# reports zeros on BOTH sides, so the hook read a delete as a no-op and let it through.
git switch -q feature 2>/dev/null
expect refuse "git branch -f main"  git branch -f main feature
expect refuse "delete main"         git branch -D main
# The plumbing form. `branch -f` and `update-ref` are separate probes into the same hole and
# a hook could plausibly be fixed for one and not the other, so both are cases.
expect refuse "git update-ref main" git update-ref refs/heads/main feature
git switch -q main

echo "  -- nothing pushes to main --"
# main equals origin/main here, so `git push origin main` is "Everything up-to-date" and git
# never calls pre-push at all. That is a real property of the pair — with main unable to move
# locally there is usually nothing to push — but it makes a useless test, so each case below
# is arranged to have something to send.
expect refuse "push feature:main"  git push origin feature:main
git switch -q feature 2>/dev/null
expect refuse "push HEAD:main"     git push origin HEAD:main
git switch -q main

# Now main genuinely IS ahead — moved through the hatch — so the plain form has work to do.
PKMNSCAN_MAIN=off git merge -q --ff-only feature
expect refuse "push main"          git push origin main
PKMNSCAN_MAIN=off git reset -q --hard origin/main

echo "  -- the legitimate path is open --"
# A merged pull request: origin's main advances without us, then we pull. The bare repo has
# no hooksPath of its own, so this is the server doing what GitHub would do.
git -C "$tmp/origin.git" update-ref refs/heads/main "$(git rev-parse feature)"
git fetch -q origin
expect allow "pull a commit origin already has" git merge --ff-only origin/main

echo "  -- the escape hatch --"
echo four > file.txt
git add file.txt
expect allow "PKMNSCAN_MAIN=off commit on main" env PKMNSCAN_MAIN=off git commit -qm "deliberate"
expect allow "PKMNSCAN_MAIN=off push to main"   env PKMNSCAN_MAIN=off git push -q origin main

echo "  -- a branch push runs the revert guard, and its failure stops the push --"
# `guard_branch ... || exit 1` is the only thing that carries the revert guard's verdict out of
# pre-push. The real script is not in this fixture, so a stub stands in: one that fails, and one
# that passes as the control proving the stub alone does not block anything.
git branch guard-probe
mkdir -p scripts
printf '#!/usr/bin/env python3\nimport sys\nprint("REFUSED: stub revert guard", file=sys.stderr)\nsys.exit(1)\n' \
  > scripts/revert-audit.py
expect refuse "a branch push the revert guard fails is refused" git push origin guard-probe
printf '#!/usr/bin/env python3\n' > scripts/revert-audit.py
expect allow "control: the same push passes when the guard passes" git push -q origin guard-probe
rm -rf scripts

echo "  -- a fresh clone is not a violation --"
# Rule 2, which the header calls out and nothing else here reaches: cloning CREATES main, and
# a guard that refuses that refuses `git clone`. Cheap to prove, and the alternative is
# discovering it on a new machine.
expect allow "clone into a new checkout" git clone -q "$tmp/origin.git" "$tmp/fresh"
( cd "$tmp/fresh" && git config core.hooksPath "$HOOKS_DIR" 2>/dev/null ) || true

echo "  -- other refs are untouched --"
expect allow "create a branch"  git branch scratch
expect allow "delete a branch"  git branch -D scratch
expect allow "tag"              git tag v-selftest
expect allow "fetch"            git fetch -q origin

echo "  -- packing refs is not moving main --"
# `pack-refs` (and so `gc`) writes main into packed-refs, then deletes the LOOSE main in a second
# transaction stating `<sha> 0000`. Read as a delete, it printed "REFUSED: would DELETE main" while
# main never moved (2026-09-28). The refusals below prove the exemption is that narrow: a real
# delete, move or fast-forward of a main that is loose AND packed still stops.
git init -q -b main "$tmp/pack"
cd "$tmp/pack" || exit 1
git config user.email selftest@example.com
git config user.name  selftest
git config commit.gpgsign false
PKMNSCAN_MAIN=off git commit -q --allow-empty -m base
base="$(git rev-parse main)"
git switch -q -c side 2>/dev/null
git commit -q --allow-empty -m ahead        # `side` is on no remote, so it is not a legal target
git config core.hooksPath "$HOOKS_DIR"
# main both loose AND packed at $base. (A bare update-ref to the packed value writes no loose
# file, so delete, recreate, then pack without pruning.) The hatch is setup only.
reloose() {
  PKMNSCAN_MAIN=off git update-ref -d refs/heads/main
  PKMNSCAN_MAIN=off git update-ref refs/heads/main "$base"
  PKMNSCAN_MAIN=off git pack-refs --all --no-prune
}
reloose
expect allow "git pack-refs --all"            git pack-refs --all
reloose
# gc exits 0 even when its pack-refs step is refused, so assert its OUTPUT is silent too.
gcout="$(git gc -q 2>&1)"
case "$gcout" in
  *REFUSED*) bad "git gc — the hook refused inside gc"; printf '%s\n' "$gcout" | sed 's/^/         /' ;;
  *) ok "git gc — silent" ;;
esac
reloose
expect refuse "delete loose+packed main"      git update-ref -d refs/heads/main
expect refuse "delete main stating its value" git update-ref -d refs/heads/main "$base"
expect refuse "git branch -D main, packed"    git branch -D main
expect refuse "move loose+packed main"        git update-ref refs/heads/main side
git switch -q main 2>/dev/null
expect refuse "fast-forward packed main"      git merge --ff-only side
git switch -q side 2>/dev/null
# Packed-refs holds an OLDER main than the loose file: deleting the loose one would move main.
reloose
PKMNSCAN_MAIN=off git update-ref refs/heads/main side
expect refuse "delete loose main, packed is older" git update-ref -d refs/heads/main "$(git rev-parse side)"
# Loose only, nothing packed: a delete stating its value must still stop.
PKMNSCAN_MAIN=off git update-ref refs/heads/main side
expect refuse "delete loose-only main stating its value" git update-ref -d refs/heads/main "$(git rev-parse side)"
git switch -q side 2>/dev/null
cd "$tmp/work" || exit 1

echo "  -- a secrets file is refused in any directory (D312, the hook refuses a secrets file) --"
git switch -q -c secretstest 2>/dev/null
mkdir -p sub/deep
for name in .env .env.local sub/.env sub/deep/.env.production; do
  printf 'K=v\n' > "$name"
  git add -f "$name"
  expect refuse "$name staged, even by a forced add" git commit -qm "secrets file"
  git reset -q -- "$name"
  rm -f "$name"
done
mkdir -p "café" other
for name in "café/.env" .ENV .Env.Local .env.example.bak; do
  printf 'K=v\n' > "$name"
  git add -f "$name"
  expect refuse "$name staged — non-ASCII dir, upper case, or a template backup" git commit -qm "secrets file"
  git reset -q -- "$name"
  rm -f "$name"
done
printf 'K=v\n' > moved.txt
git add moved.txt && git commit -qm "to be renamed" -q
git mv moved.txt .env
expect refuse "a git mv rename onto the name" git commit -qm "rename onto secrets"
git mv -f .env moved.txt
printf 'K=v\n' > gone.txt; git add gone.txt; git commit -qm "gone" -q
git rm -q gone.txt
expect allow "a staged delete is not a secrets file staged" git commit -qm "delete"
for name in .env.example sub/.env.example other/.ENV.EXAMPLE .envrc; do
  printf 'K=\n' > "$name"
  git add -f "$name"
  expect allow "$name staged — not a secrets file" git commit -qm "template"
done

echo "  -- every staged image gets the QR scan, wherever it lands (D303) --"
# THE FOLDER LIST IS GONE. Before this, only demo-assets/photos/, demo-assets/extra/photos/
# and demo-assets/mirror/photos/ were re-decoded by scripts/qr-clear-check.py; every other
# image was refused outright with NO inspection at all. These cases prove the replacement:
# the scan runs on every staged image, in any folder, and a scanner that cannot run refuses
# rather than warns.
#
# SYNTHETIC QR SYMBOLS, GENERATED BY THE DECODER'S OWN ENCODER, exactly T8's method
# (harness/tests/t8_codes.py) — never a real code-card photograph, which the opsec rules
# never let into this repository.
git switch -q -c qrtest 2>/dev/null

# THE CHECKER ITSELF IS NOT PART OF THIS FIXTURE REPOSITORY, SO IT IS COPIED IN. The hook
# runs `python3 scripts/qr-clear-check.py` with the fixture repo as its cwd, and that script
# reads `codes/qr.py` relative to ITS OWN location — so both have to exist inside `$tmp/work`
# for the same reason `serve.py` is copied in above rather than referenced from here.
mkdir -p scripts codes
cp "$REPO_ROOT/scripts/qr-clear-check.py" scripts/qr-clear-check.py
cp "$REPO_ROOT/codes/__init__.py" "$REPO_ROOT/codes/qr.py" codes/

python3 - "$tmp/clean.png" "$tmp/qr.png" <<'PYEOF'
import sys
from PIL import Image
import numpy as np
import zxingcpp

clean_path, qr_path = sys.argv[1], sys.argv[2]
Image.new("RGB", (64, 64), (255, 255, 255)).save(clean_path)
symbol = Image.fromarray(
    np.array(zxingcpp.write_barcode(zxingcpp.BarcodeFormat.QRCode, "SELFTEST-NOT-A-REAL-CODE"))
).convert("RGB")
symbol.save(qr_path)
PYEOF

if [ -s "$tmp/clean.png" ] && [ -s "$tmp/qr.png" ]; then
  mkdir -p docs demo-assets/mirror/photos

  cp "$tmp/qr.png" docs/never-an-exception.png
  git add docs/never-an-exception.png
  expect refuse "a decodable QR staged in docs/, never an exception folder" \
    git commit -qm "qr in docs"
  git reset -q -- docs/never-an-exception.png
  rm -f docs/never-an-exception.png

  cp "$tmp/clean.png" docs/clean-image.png
  git add docs/clean-image.png
  expect allow "a clean PNG staged in docs/" git commit -qm "clean image in docs"

  cp "$tmp/qr.png" demo-assets/mirror/photos/test.png
  git add demo-assets/mirror/photos/test.png
  expect refuse "a decodable QR in demo-assets/mirror/photos/, the old exception folder" \
    git commit -qm "qr in the old exception folder"
  git reset -q -- demo-assets/mirror/photos/test.png
  rm -f demo-assets/mirror/photos/test.png

  # A SCANNER THAT CANNOT RUN REFUSES, WHERE IT USED TO WARN AND ALLOW. `fakebin` carries
  # every plain command scripts/githooks/pre-commit calls before reaching the image scan —
  # git, grep, sed, awk, tr, cat, basename, dirname — with python3 left out on purpose, so
  # `command -v python3` fails exactly as it would on a machine with no interpreter at all.
  fakebin="$tmp/fakebin-nopython"
  mkdir -p "$fakebin"
  for bin in bash env git grep sed awk tr cat basename dirname mkdir rm cp mv ls \
             head tail sort uniq wc xargs find; do
    src="$(command -v "$bin" 2>/dev/null)" || continue
    ln -sf "$src" "$fakebin/$bin"
  done
  cp "$tmp/clean.png" docs/needs-a-scanner.png
  git add docs/needs-a-scanner.png
  expect refuse "no python3 on PATH — the commit refuses rather than warns" \
    env -i PATH="$fakebin" git commit -qm "no scanner available"
  git reset -q -- docs/needs-a-scanner.png
  rm -f docs/needs-a-scanner.png
else
  bad "the fixture could not build a QR test image — PIL or zxing-cpp is missing here"
fi

# ----------------------------------------------------------- every refusal is logged
# One line per refusal in the refusal log, and a log that cannot be written never changes the
# verdict. The fixture carries its own copy of the helper because the hooks find it through the
# toplevel they run in.
echo
echo "  the refusal log"
. "$REPO_ROOT/scripts/refusal-log-assert.sh"
rl="$tmp/refusals.log"
rlrepo="$tmp/rl"
git init -q -b main "$rlrepo"
mkdir -p "$rlrepo/scripts"
cp "$REPO_ROOT/scripts/refusal_log.py" "$rlrepo/scripts/"
git -C "$rlrepo" config user.email selftest@example.com
git -C "$rlrepo" config user.name selftest
git -C "$rlrepo" config commit.gpgsign false
echo one > "$rlrepo/a.txt"
git -C "$rlrepo" add a.txt
PKMNSCAN_MAIN=off git -C "$rlrepo" commit -qm seed
git -C "$rlrepo" config core.hooksPath "$HOOKS_DIR"
echo two > "$rlrepo/a.txt"
git -C "$rlrepo" add a.txt
rl_out="$(cd "$rlrepo" && PKMNSCAN_REFUSAL_LOG="$rl" git commit -qm "straight onto main" 2>&1)"; rl_status=$?
[ $rl_status -ne 0 ] && ok "a refused commit on main still refuses" || bad "the logged refusal let the commit through"
why="$(refusal_line_ok "$rl" "reference-transaction:main-move")" && ok "…and writes one well-formed line" || bad "the refusal log line: $why"
rl_bad="$(cd "$rlrepo" && PKMNSCAN_REFUSAL_LOG="$tmp/no/such/dir/log" git commit -qm "straight onto main" 2>&1)"; rl_bad_status=$?
if [ $rl_bad_status -ne 0 ] && [ "$rl_bad" = "$rl_out" ]; then ok "an unwritable log path changes neither the verdict nor the output"
else bad "an unwritable log path changed the verdict (exit $rl_bad_status)"; fi

# pre-commit (a staged secrets file) and pre-push (a push to main): same three assertions.
git -C "$rlrepo" switch -q -c rlb
echo k > "$rlrepo/.env"
git -C "$rlrepo" add -f .env
rl="$tmp/precommit.log"
rl_out="$(cd "$rlrepo" && PKMNSCAN_REFUSAL_LOG="$rl" git commit -qm "secrets" 2>&1)"; rl_status=$?
[ $rl_status -ne 0 ] && ok "pre-commit still refuses a staged secrets file" || bad "pre-commit let a secrets file through"
why="$(refusal_line_ok "$rl" "pre-commit:secrets")" && ok "…and writes one well-formed line" || bad "the pre-commit log line: $why"
rl_bad="$(cd "$rlrepo" && PKMNSCAN_REFUSAL_LOG="$tmp/no/such/dir/log" git commit -qm "secrets" 2>&1)"; rl_bad_status=$?
if [ $rl_bad_status -ne 0 ] && [ "$rl_bad" = "$rl_out" ]; then ok "pre-commit: an unwritable log path changes neither verdict nor output"
else bad "pre-commit: an unwritable log path changed the verdict (exit $rl_bad_status)"; fi
git -C "$rlrepo" reset -q -- .env
git init -q --bare "$tmp/rlorigin.git"
git -C "$rlrepo" remote add origin "$tmp/rlorigin.git"
rl="$tmp/prepush.log"
rl_out="$(cd "$rlrepo" && PKMNSCAN_REFUSAL_LOG="$rl" git push origin rlb:main 2>&1)"; rl_status=$?
[ $rl_status -ne 0 ] && ok "pre-push still refuses a push to main" || bad "pre-push let a push to main through"
why="$(refusal_line_ok "$rl" "pre-push:main-push")" && ok "…and writes one well-formed line" || bad "the pre-push log line: $why"
rl_bad="$(cd "$rlrepo" && PKMNSCAN_REFUSAL_LOG="$tmp/no/such/dir/log" git push origin rlb:main 2>&1)"; rl_bad_status=$?
if [ $rl_bad_status -ne 0 ] && [ "$rl_bad" = "$rl_out" ]; then ok "pre-push: an unwritable log path changes neither verdict nor output"
else bad "pre-push: an unwritable log path changed the verdict (exit $rl_bad_status)"; fi

# The log is bounded: past its cap it rotates, and the reader sees only the tail.
rl="$tmp/big.log"
python3 -c "
import os, sys
sys.path.insert(0, '$REPO_ROOT/scripts')
import refusal_log as r
os.environ['PKMNSCAN_REFUSAL_LOG'] = '$rl'
for _ in range(4000):
    r.log('t', 'rule', 'x' * 40)
sys.exit(0 if os.path.getsize('$rl') <= r.MAX_BYTES and os.path.exists('$rl.1') and r.recent() else 1)
" && ok "the refusal log rotates past its cap and its tail still reads" || bad "the refusal log grew past its cap or did not rotate"

# The opsec PreToolUse hook is a shell script of its own: same three assertions.
OPSEC="$REPO_ROOT/scripts/guard-opsec.sh"
rl="$tmp/opsec.log"
rl_payload='{"session_id":"sess-1","tool_input":{"file_path":"/x/fixtures/a.csv","content":"x"}}'
rl_out="$(printf '%s' "$rl_payload" | PKMNSCAN_REFUSAL_LOG="$rl" bash "$OPSEC" 2>&1)"; rl_status=$?
[ $rl_status -eq 2 ] && ok "guard-opsec still refuses a fixtures write" || bad "guard-opsec exited $rl_status"
why="$(refusal_line_ok "$rl" "guard-opsec:fixtures" "sess-1")" && ok "…and writes one well-formed line" || bad "the guard-opsec log line: $why"
rl_bad="$(printf '%s' "$rl_payload" | PKMNSCAN_REFUSAL_LOG="$tmp/no/such/dir/log" bash "$OPSEC" 2>&1)"; rl_bad_status=$?
if [ $rl_bad_status -eq 2 ] && [ "$rl_bad" = "$rl_out" ]; then ok "an unwritable log path changes neither the verdict nor the output"
else bad "an unwritable log path changed the verdict (exit $rl_bad_status)"; fi

echo
if [ "$fail" -eq 0 ]; then
  echo "githooks self-test: $pass passed"
  exit 0
fi
echo "githooks self-test: $fail FAILED, $pass passed"
exit 1
