#!/usr/bin/env bash
# `make guard-shell-selftest` — scripts/guard-shell.py, proved by committing its five mistakes.
#
# WHY IT IS NOT A TABLE OF ASSERTIONS. Every clause in that guard claims a command does
# something a session did not intend, and this repo's standard for that kind of claim is
# reproduction: `reap-selftest.sh` reproduces both 2026-09-10 kill incidents with real
# processes and a real socket, `revert-selftest.sh` rebuilds PR #218 and #221, and
# `silent-write-selftest.sh` reproduces the refused commit whose refusal went to /dev/null. So
# four of the five incidents are PERFORMED here first, in a throwaway repository, and only then
# is the guard asked about them:
#
#   1. a file is modified, `git checkout <it>` is run for real, and the work is gone
#   2. a worktree is made, and its root is a different directory from the main checkout's
#   4. `ln -s` at an existing directory creates the nested link instead of failing
#   5. `pgrep -f <tag>` matches the shell whose own command line carries that tag
#
# The fifth reproduction is the one that earns its place: rank 19's rule was written correctly
# and in full, and then broken four days later by a session that had read it, because the
# mechanism — a pattern matching the searcher — is not what anybody expects. Here it is a
# measurement.
#
# Clause 3 cannot be reproduced without spending somebody's network and rate limit, so it is
# the one asserted about — and `gh api --help` is read where gh exists, so that `-f` and
# `--method` are at least still the flags this guard is talking about.
#
# THE FALSE POSITIVES ARE THE HALF THAT DECIDES WHETHER THIS GUARD SURVIVES. A guard that
# fires on honest work is switched off inside a day, and then it is gone silently. So every
# shape this repo actually types is pinned as PASSING — including the `git`, `gh` and `ln`
# lines swept out of its own selftests, Makefile and workflows — and the git cases are RUN in
# the fixture first, because a case that is secretly a typo sails past the guard for the wrong
# reason (`a-guard-must-see-its-subject`, applied to a shell string).
#
# WHY IT IS NOT IN THE GIT HOOK. D18: it writes a temp repository and makes real commits in
# it. It IS in `make check` and `make ci-check`, which is reap-selftest's standing exactly.
#
# WHAT IT CANNOT PROVE. That Claude Code or Codex actually invokes the hook, or that exit 2
# blocks a tool call — both are the harness's behaviour and not this repo's.
# `.claude/settings.json` and `.codex/hooks.json` arm it and `make docs-audit`'s `codex hooks`
# row is what keeps those two rosters honest with each other.

set -uo pipefail          # NOT -e: every case must run and be scored

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="$HERE/guard-shell.py"
PARSER="$HERE/shell_parse.py"
pass=0
fail=0

[ -f "$GUARD" ]  || { echo "no guard-shell.py beside this script"; exit 1; }
[ -f "$PARSER" ] || { echo "no shell_parse.py beside this script — the guard shares it"; exit 1; }

tmp="$(mktemp -d "${TMPDIR:-/tmp}/pkmnscan-guardshell.XXXXXX")" || { echo "cannot make a temp dir"; exit 1; }
cleanup() { rm -rf "$tmp"; return 0; }
trap cleanup EXIT

say()  { printf '  %-6s %s\n' "$1" "$2"; }
ok()   { pass=$((pass + 1)); say "ok" "$1"; }
bad()  { fail=$((fail + 1)); say "FAIL" "$1"; }

# The hook, asked about one command exactly as Claude Code asks it: the payload on stdin, the
# verdict as an exit code, the reason on stderr. `cwd` travels in the payload because that is
# where the harness puts it, and because it lets every case be posed against the fixture
# without this script ever leaving it.
judge() {   # judge <cwd> <command> -> exit code, output in $out
  out="$(printf '%s' "$2" \
        | CWD="$1" python3 -c 'import json,os,sys; print(json.dumps({"cwd":os.environ["CWD"],"tool_input":{"command":sys.stdin.read()}}))' \
        | python3 "$GUARD" --hook 2>&1)"
  return $?
}

judge_bg() {   # judge_bg <cwd> <command> — the same, with run_in_background set
  out="$(printf '%s' "$2" \
        | CWD="$1" python3 -c 'import json,os,sys; print(json.dumps({"cwd":os.environ["CWD"],"tool_input":{"command":sys.stdin.read(),"run_in_background":True}}))' \
        | python3 "$GUARD" --hook 2>&1)"
  return $?
}

judge_write() {   # judge_write <cwd> <file_path>
  out="$(CWD="$1" TARGET="$2" python3 -c 'import json,os; print(json.dumps({"cwd":os.environ["CWD"],"tool_input":{"file_path":os.environ["TARGET"]}}))' \
        | python3 "$GUARD" --hook 2>&1)"
  return $?
}

refuses() {   # refuses <label> <cwd> <command>
  judge "$2" "$3"
  if [ $? -eq 2 ]; then ok "$1"; else bad "$1 — the guard allowed it"; fi
}

allows() {    # allows <label> <cwd> <command>
  judge "$2" "$3"
  local status=$?
  if [ $status -eq 0 ]; then
    ok "$1"
  else
    bad "$1 — the guard refused a command it must never refuse (exit $status)"
    printf '%s\n' "$out" | sed 's/^/           /' | head -6
  fi
}

# A FALSE-POSITIVE CASE IS RUN BEFORE IT IS SCORED. A misspelled git command is refused by git
# rather than by this guard and would score as "allowed" for a reason that has nothing to do
# with the predicate. Exit status is NOT the test — `git checkout <clean path>` exits 0 and
# `git restore --staged` on an unstaged file exits 0 too — so what is checked is that git did
# not reject the command line itself.
real_command() {   # real_command <cwd> <command>
  local said
  said="$( (cd "$1" && eval "$2" ) 2>&1 )"
  case "$said" in
    *"is not a git command"*|*"unknown option"*|*"usage: git"*|*"error: unknown"*|*"unknown switch"*)
      bad "the case \`$2\` is not a real command: $said"
      return 1 ;;
  esac
  return 0
}

# ------------------------------------------------------------------------------- the fixture
#
# A MAIN CHECKOUT AND A LINKED WORKTREE, because clause 2's whole subject is the difference
# between them: `checkout_root` answers with the worktree from inside it and with the main
# tree from inside that, and a fixture with only one of them could not tell a working guard
# from one that always says yes.
git init -q "$tmp/main" 2>/dev/null
(
  cd "$tmp/main" || exit 1
  git config user.email "selftest@example.invalid"
  git config user.name "guard-shell selftest"
  git config commit.gpgsign false
  git config core.hooksPath /dev/null
  printf 'one\ntwo\nthree\n' > work.py
  printf 'clean\n' > clean.txt
  mkdir -p harness/images
  printf 'x\n' > harness/images/a.jpg
  git add work.py clean.txt harness
  git commit -q -m "the committed state"
  git worktree add -q -b feature "$tmp/main/.wt" >/dev/null 2>&1
) || { echo "cannot build the fixture"; exit 1; }

WT="$tmp/main/.wt"
[ -d "$WT" ] || { echo "the fixture worktree was not created"; exit 1; }

echo "guard-shell-selftest — fixture at $tmp"
echo ""
echo "  1. the destructive checkout, reproduced"

# ------------------------------------------------- 1a. the incident, performed in the fixture
(
  cd "$tmp/main" || exit 1
  # ~240 LINES IS THE REAL FIGURE AND THE SHAPE IS WHAT MATTERS: uncommitted work in a file
  # that is otherwise ordinary, put back by a command that asks nothing.
  printf 'one\ntwo\nthree\n' > work.py
  for i in $(seq 1 240); do printf 'the session\x27s own work line %s\n' "$i" >> work.py; done
  wc -l < work.py | tr -d ' ' > "$tmp/before"
  git checkout -q work.py 2>/dev/null
  wc -l < work.py | tr -d ' ' > "$tmp/after"
)
if [ "$(cat "$tmp/before")" = "243" ] && [ "$(cat "$tmp/after")" = "3" ]; then
  ok "\`git checkout work.py\` destroyed 240 uncommitted lines, silently and without asking"
else
  bad "the incident did not reproduce: $(cat "$tmp/before") lines before, $(cat "$tmp/after") after"
fi

# Put the dirt back, so every case below is posed against a genuinely modified file. The
# DIRECTORY is dirtied too, because a branch named after a directory in the tree — `git checkout
# -b harness`, `-b app`, `-b scripts` — is an ordinary thing to type, and it is the one case
# where the branch-creation exemption is load-bearing rather than redundant with resolution.
(cd "$tmp/main" && printf 'one\ntwo\nthree\nfour\n' > work.py && printf 'y\n' >> harness/images/a.jpg)

echo ""
echo "  the guard refuses it, in every spelling that discards"

refuses "the bare form — the 2026-09-06 command"    "$tmp/main" "git checkout work.py"
refuses "with \`--\`, which is the careful spelling of the same discard" \
  "$tmp/main" "git checkout -- work.py"
refuses "\`-q\` does not launder it"                 "$tmp/main" "git checkout -q -- work.py"
refuses "\`git restore\`, the modern name"            "$tmp/main" "git restore work.py"
refuses "\`git restore --worktree --staged\`, which takes both copies" \
  "$tmp/main" "git restore --staged --worktree work.py"
refuses "\`git checkout .\` over the whole dirty set"  "$tmp/main" "git checkout ."
refuses "\`git checkout -- .\`"                        "$tmp/main" "git checkout -- ."
refuses "\`git -C <tree> checkout\`, which names another tree" \
  "$tmp" "git -C $tmp/main checkout work.py"
refuses "buried mid-script behind a \`&&\`"           "$tmp/main" "echo tidy && git checkout work.py"
# A MULTI-LINE SCRIPT IS THE ORDINARY SHAPE OF A SESSION'S BASH CALL, and `shlex` treats a
# newline as plain whitespace — so without the line separator the shared parser inserts, these
# two lines are ONE simple command whose head is `echo`, which has no git verb at all. That is a
# MISS on the exact command this clause exists for, and it is the same parser defect
# `silent-write-guard.py` shipped in the other direction, as a false positive. One parser, one
# arm each.
refuses "on its own line in a two-line script"       "$tmp/main" "echo tidy
git checkout work.py"
refuses "an env prefix does not launder it"          "$tmp/main" "PKMNSCAN_MAIN=off git checkout work.py"

# THE REFUSAL'S CONTENT IS SCORED, NOT ONLY ITS EXIT CODE. A refusal that does not name the
# escape hatch is what CLAUDE.md forbids repo-wide, and one that does not name the `.bak`
# shape sends a session looking for a different command to type.
judge "$tmp/main" "git checkout work.py"
case "$out" in *"PKMNSCAN_CHECKOUT=off"*) ok "the refusal prints its escape hatch" ;;
  *) bad "the refusal does not name PKMNSCAN_CHECKOUT=off" ;; esac
case "$out" in *".bak"*) ok "the refusal names the \`.bak\` copy as the way to do it safely" ;;
  *) bad "the refusal does not name the .bak shape" ;; esac
case "$out" in *"work.py is modified"*) ok "the refusal names the file and its state" ;;
  *) bad "the refusal does not say which file is modified" ;; esac
case "$out" in *"1 added, 0 removed"*|*"added,"*) ok "the refusal says how many lines would go" ;;
  *) bad "the refusal does not carry a diffstat" ;; esac

echo ""
echo "  what clause 1 must NEVER refuse"

for case in \
  'git checkout main' \
  'git checkout -b brand-new' \
  'git checkout -q -b another-one' \
  'git checkout clean.txt' \
  'git checkout -- clean.txt' \
  'git restore clean.txt' \
  'git restore --staged work.py' \
  'git switch -q main' \
  'git checkout HEAD~0' \
; do
  if real_command "$tmp/main" "$case"; then
    allows "a branch, a clean path or an index op: \`$case\`" "$tmp/main" "$case"
  fi
done

# THE SHA-SCOPED FORM IS A WRITE AND NOT A DISCARD, which is the specification's own
# must-pass: it fetches a KNOWN version into the tree rather than throwing an unknown one
# away. Run for real first, because a bad sha would make this pass for the wrong reason.
sha="$(cd "$tmp/main" && git rev-parse HEAD)"
if real_command "$tmp/main" "git checkout $sha -- clean.txt"; then
  allows "\`git checkout <sha> -- <path>\` names a source" "$tmp/main" "git checkout $sha -- work.py"
fi
allows "\`git restore --source=<sha>\` names a source" "$tmp/main" "git restore --source=$sha work.py"
allows "\`--patch\` asks before it discards"  "$tmp/main" "git checkout -p work.py"
allows "a path in no tree this guard can read" "$tmp/main" "git checkout nothing-named-this"
# AN UNTRACKED FILE HAS NOTHING TO LOSE. git refuses it on its own — `did not match any file
# known to git` — and a guard that refused it first would be taking credit for git's answer
# while teaching a session that this clause fires on files it has no business in.
printf 'brand new and untracked\n' > "$tmp/main/fresh.txt"
allows "an UNTRACKED path — \`??\` is not a modification" "$tmp/main" "git checkout fresh.txt"
allows "\`git -C\` at a directory that is not there" "$tmp/main" "git -C /no/such/tree checkout x.py"

# A HEREDOC BODY IS A DOCUMENT AND NOT A COMMAND, and this is the case that cannot be dodged:
# the commit message announcing this guard, and its decision entry, both quote
# `git checkout work.py` on a line of their own. A parser that read a body line as a command
# would refuse the one commit that cannot be wrong. `silent-write-selftest.sh` scores the same
# requirement for the other guard; the parser is now shared, so this is the second reader's arm
# for it rather than a duplicate.
allows "a heredoc body that QUOTES the refused command" "$tmp/main" "git commit -F - <<'MSG'
Refuse the command that destroyed 240 lines:

git checkout work.py

and name the .bak copy in the refusal.
MSG"

# A BRANCH NAMED AFTER A DIRECTORY IN THE TREE, which is the one shape where "it creates a
# branch" has to be read off the FLAGS: `harness` exists on disk and carries a modification, so
# resolution alone would call it a dirty path and refuse a branch creation.
if real_command "$tmp/main" "git checkout -b harness"; then
  (cd "$tmp/main" && git switch -q main 2>/dev/null; git branch -q -D harness 2>/dev/null)
  allows "a branch named after a dirty directory" "$tmp/main" "git checkout -b harness"
fi

# THE NON-VACUITY LINE: an operand that resolves to neither a path nor a commit is REPORTED
# while being allowed, so "parsed nothing" can never read as "nothing to object to".
judge "$tmp/main" "git checkout nothing-named-this"
case "$out" in *"resolves to neither a path"*) ok "an unresolvable operand is reported, not swallowed" ;;
  *) bad "an unresolvable operand produced no note: $out" ;; esac

# AND THE OTHER HALF OF THAT LINE: a REAL branch must not be reported as unresolvable. Both
# verdicts are "allowed", so the exit code cannot tell them apart — the difference is whether
# this guard resolved `main` as a commit or merely failed to recognise it, and a guard that
# printed a note on every branch switch is one a session learns to ignore.
judge "$tmp/main" "git checkout main"
case "$out" in
  *"resolves to neither"*) bad "a real branch was reported as unresolvable: $out" ;;
  *) ok "a branch is RESOLVED as a commit, not merely unrecognised" ;;
esac

echo ""
echo "  2. a write outside this checkout, with a real worktree to be outside of"

# The reproduction is that the two roots genuinely differ, which is what makes the clause
# mechanical rather than a matter of judgement.
main_root="$(cd "$tmp/main" && git rev-parse --show-toplevel)"
wt_root="$(cd "$WT" && git rev-parse --show-toplevel)"
if [ -n "$main_root" ] && [ -n "$wt_root" ] && [ "$main_root" != "$wt_root" ]; then
  ok "the worktree's root is a different directory from the main checkout's"
else
  bad "the fixture's two roots did not differ: '$main_root' vs '$wt_root'"
fi

judge_write "$WT" "$tmp/main/work.py"
if [ $? -eq 2 ]; then ok "a Write into the main checkout, from the worktree, is refused"
else bad "a Write into the main checkout was allowed"; fi
case "$out" in *"$tmp/main/work.py"*) ok "the refusal names the resolved target" ;;
  *) bad "the refusal does not name the target" ;; esac
case "$out" in *"$wt_root"*) ok "the refusal names the resolved root" ;;
  *) bad "the refusal does not name this checkout" ;; esac
case "$out" in *"PKMNSCAN_TREE=off"*) ok "the refusal prints its escape hatch" ;;
  *) bad "the refusal does not name PKMNSCAN_TREE=off" ;; esac

judge_write "$WT" "$WT/work.py"
if [ $? -eq 0 ]; then ok "the same relative path INSIDE the worktree passes"
else bad "a write inside this checkout was refused"; printf '%s\n' "$out" | head -4; fi

judge_write "$WT" "$WT/app/src/new/deep/file.tsx"
if [ $? -eq 0 ]; then ok "a path that does not exist yet, inside the tree, passes"
else bad "a new path inside this checkout was refused"; fi

judge_write "$WT" "$HOME/.claude/projects/x/memory/note.md"
if [ $? -eq 0 ]; then ok "a memory file under the user's own ~/.claude passes"
else bad "a write into ~/.claude was refused"; printf '%s\n' "$out" | head -4; fi

mkdir -p "$tmp/scratch"
judge_write "$WT" "$tmp/scratch/out.json"
if [ $? -eq 0 ]; then ok "a scratch file in a temp directory that is no checkout passes"
else bad "a scratch write was refused"; printf '%s\n' "$out" | head -4; fi

# A SESSION STANDING IN THE MAIN CHECKOUT IS UNTOUCHED BY CONSTRUCTION, and that is asserted
# rather than argued: the same target, judged from the tree that owns it, passes.
judge_write "$tmp/main" "$tmp/main/work.py"
if [ $? -eq 0 ]; then ok "from the main checkout, its own file passes"
else bad "the main checkout was refused its own file"; fi

judge_write "/" "$tmp/main/work.py"
if [ $? -eq 0 ]; then ok "no resolvable root is a PASS (fail open)"
else bad "an unresolvable root refused a write"; fi
case "$out" in *"could not resolve a checkout root"*) ok "and it SAYS it could not resolve one" ;;
  *) bad "an unresolvable root passed silently: $out" ;; esac

refuses "a shell redirect into the other checkout" "$WT" "cat > $tmp/main/work.py"
refuses "an append into the other checkout"        "$WT" "echo x >> $tmp/main/work.py"
refuses "\`tee\` into the other checkout"           "$WT" "echo x | tee $tmp/main/work.py"
allows  "a redirect inside this checkout"          "$WT" "echo x > notes.txt"
allows  "a redirect to /dev/null"                  "$WT" "make harness > /dev/null 2>&1"
allows  "a redirect into a temp directory"         "$WT" "echo x > $tmp/scratch/out.log"
allows  "a redirect through an unexpanded variable" "$WT" "echo x > \$tmp/out.log"

echo ""
echo "  3. \`gh api\` with a field and no method"

# NOT REPRODUCIBLE WITHOUT SOMEBODY'S RATE LIMIT, so the flags are at least checked against
# the gh that is installed. A clause whose flags gh has renamed is a clause about nothing.
if command -v gh >/dev/null 2>&1; then
  help="$(gh api --help 2>&1)"
  case "$help" in
    *"--field"*|*"-f,"*) ok "gh api still takes \`-f/--field\` (read from \`gh api --help\`)" ;;
    *) bad "gh api --help no longer mentions --field; this clause may be about nothing" ;;
  esac
  case "$help" in
    *"--method"*) ok "gh api still takes \`--method\`" ;;
    *) bad "gh api --help no longer mentions --method" ;;
  esac
else
  say "skip" "gh is not installed; the flag check cannot be posed"
fi

refuses "the 2026-09-12 command"  "$tmp/main" "gh api 'repos/{owner}/{repo}/commits/abc123/check-runs' -f per_page=100"
refuses "\`-F\` is the same mistake"  "$tmp/main" "gh api repos/o/r/issues -F state=open"
refuses "\`--field\`"                "$tmp/main" "gh api repos/o/r/issues --field state=open"
refuses "\`--raw-field\`"            "$tmp/main" "gh api repos/o/r/issues --raw-field state=open"
refuses "\`--field=k=v\`"            "$tmp/main" "gh api repos/o/r/issues --field=state=open"
refuses "the bundled short form"    "$tmp/main" "gh api repos/o/r/issues -fstate=open"
refuses "\`--paginate\` does not name a method" "$tmp/main" "gh api --paginate repos/o/r/issues -f per_page=100"

judge "$tmp/main" "gh api repos/o/r/check-runs -f per_page=100"
case "$out" in *"repos/o/r/check-runs?per_page=100"*) ok "the refusal prints the query-string form it wants" ;;
  *) bad "the refusal does not show the query-string form" ;; esac
case "$out" in *"PKMNSCAN_GH=off"*) ok "the refusal prints its escape hatch" ;;
  *) bad "the refusal does not name PKMNSCAN_GH=off" ;; esac

allows "\`--method GET\` says what it means"   "$tmp/main" "gh api --method GET repos/o/r/issues -f per_page=100"
allows "\`-X POST\` says what it means"        "$tmp/main" "gh api -X POST repos/o/r/issues -f state=open"
allows "\`-XPATCH\`, bundled"                  "$tmp/main" "gh api -XPATCH repos/o/r/issues -f state=open"
allows "\`--method=DELETE\`"                   "$tmp/main" "gh api --method=DELETE repos/o/r/issues -f x=1"
allows "\`graphql\` is a POST by design"       "$tmp/main" "gh api graphql -f query=abc"
allows "a query string and no field"          "$tmp/main" "gh api 'repos/o/r/issues?per_page=100'"
allows "the form check.yml actually uses"     "$tmp/main" "gh api \"repos/o/r/actions/artifacts?name=x&per_page=10\" --jq '.artifacts'"
allows "no field at all"                      "$tmp/main" "gh api repos/o/r/commits/abc/check-runs"
allows "\`gh pr view\` is not \`gh api\`"       "$tmp/main" "gh pr view 300 --json mergeable"
allows "\`gh pr merge\` with its own -f"        "$tmp/main" "gh pr merge 300 --squash"

echo ""
echo "  4. \`ln -s\` at a path that already exists, reproduced"

# ------------------------------------------------- 4a. the incident, performed in the fixture
(
  cd "$WT" || exit 1
  mkdir -p harness/images
  ln -s "$tmp/main/harness/images" harness/images 2>/dev/null
)
if [ -L "$WT/harness/images/images" ]; then
  ok "\`ln -s <dir> <existing dir>\` created harness/images/images instead of failing"
else
  bad "the nested-symlink incident did not reproduce"
fi
rm -f "$WT/harness/images/images"

refuses "the 2026-08-29 command"        "$WT" "ln -s $tmp/main/harness/images harness/images"
refuses "an existing FILE destination"   "$tmp/main" "ln -s /somewhere work.py"
refuses "one operand, landing on a name that exists" "$tmp/main" "ln -s $tmp/main/clean.txt"
refuses "the multi-operand directory form" "$tmp/main" "ln -s $tmp/main/harness/images/a.jpg $tmp/main/clean.txt harness/images"

judge "$WT" "ln -s $tmp/main/harness/images harness/images"
case "$out" in *"harness/images/images"*) ok "the refusal names the nested link it would create" ;;
  *) bad "the refusal does not name the nested path" ;; esac
case "$out" in *"PKMNSCAN_LINK=off"*) ok "the refusal prints its escape hatch" ;;
  *) bad "the refusal does not name PKMNSCAN_LINK=off" ;; esac
case "$out" in *"ln -sfn"*) ok "the refusal names \`ln -sfn\`" ;;
  *) bad "the refusal does not name ln -sfn" ;; esac

allows "\`-sfn\`, which is what the rule asks for" "$WT" "ln -sfn $tmp/main/harness/images harness/images"
allows "\`-sf\`"                       "$WT" "ln -sf $tmp/main/harness/images harness/images"
allows "\`-sn\`"                       "$WT" "ln -sn $tmp/main/harness/images harness/images"
allows "\`--symbolic --force\`"         "$WT" "ln --symbolic --force $tmp/main/clean.txt harness/images"
allows "an absent destination"         "$WT" "ln -s $tmp/main/clean.txt nothing-here-yet"
allows "the form worktree-provision.sh uses, at an absent path" \
  "$WT" "[ -e harness/cache ] || ln -s $tmp/main/harness/images harness/cache"
allows "a HARD link is not this clause's business" "$WT" "ln $tmp/main/clean.txt harness/images"
allows "an unexpanded destination"     "$WT" "ln -s \$mirror \$dest"

echo ""
echo "  5. a polling loop, and why the pattern one cannot work"

# ------------------------------ 5a. the pattern is not the process, measured on this machine
#
# WHAT IS REPRODUCED HERE IS THE MECHANISM, NOT THE SENTENCE. `pgrep -f` matches a full
# COMMAND LINE, so it reports every process that merely NAMES the thing being waited for — an
# editor with the file open, a `grep` for it, the harness's own wrapper for the Bash call, or
# the waiter itself. A condition built on that can be true while the work it is waiting for is
# long finished, which is what "the loop never fired" means.
#
# AND THE SELF-MATCH IS PLATFORM-DEPENDENT, WHICH IS THE POINT RATHER THAN AN EXCUSE. Measured
# here: BSD/macOS `pgrep` excludes itself AND ALL ITS ANCESTORS unless `-a` is given
# (`pgrep -af <tag>` reports the calling shell, `pgrep -f <tag>` reports nothing), so WHICH
# process satisfies the condition depends on the process tree the harness happens to build.
# A predicate whose answer depends on that is not a predicate a session can reason about, and
# this arm asserts the part that holds everywhere: a stranger carrying the pattern is a match.
tag="guardshell-selftest-$$-nosuchprocess"
python3 -c 'import time,sys; time.sleep(4)' "$tag" &
decoy=$!
sleep 0.4
total="$(pgrep -f "$tag" 2>/dev/null | wc -l | tr -d ' ')"
kill "$decoy" 2>/dev/null
wait "$decoy" 2>/dev/null
if [ "${total:-0}" -ge 1 ]; then
  ok "\`pgrep -f <tag>\` reported $total process(es) for a tag no program is named after"
else
  bad "pgrep -f did not match a live command line carrying the pattern — the class cannot be posed here"
fi

# THE ANCESTOR RULE, ASSERTED RATHER THAN DESCRIBED. Both halves are measured against a tag
# that exists ONLY on the asking shell's own command line: `-af` reports it and a bare `-f`
# does not. If a future pgrep changes either answer, this arm says so — which is the whole
# reason the refusal above explains the self-match instead of asserting a platform's version
# of it.
own="guardshell-ancestor-$$-nosuchprocess"
with_a="$(bash -c "true; pgrep -af $own | wc -l" | tr -d ' ')"
without_a="$(bash -c "true; pgrep -f $own | wc -l" | tr -d ' ')"
if [ "${with_a:-0}" -ge 1 ] && [ "${without_a:-1}" -eq 0 ]; then
  ok "pgrep excludes its own ancestors unless -a: \`-af\` sees the asking shell, \`-f\` does not"
else
  bad "the ancestor rule did not hold here (-af: $with_a, -f: $without_a) — which process a waiter matches is platform-dependent"
fi

refuses "the 2026-09-12 waiter"  "$tmp/main" "until ! pgrep -f 'scratchpad/drive.sh'; do sleep 5; done"
refuses "the \`while pgrep\` spelling" "$tmp/main" "while pgrep -f drive.sh >/dev/null; do sleep 10; done"
refuses "a \`ps -ef\` pattern poll"   "$tmp/main" "while ps -ef | grep -q drive.sh; do sleep 5; done"
refuses "an \`lsof\` poll"            "$tmp/main" "until lsof -ti tcp:5173; do sleep 2; done"

judge "$tmp/main" "until ! pgrep -f drive.sh; do sleep 5; done"
case "$out" in *"command line NAMES it"*) ok "the refusal explains that the pattern is not the process" ;;
  *) bad "the refusal does not explain why the loop never fires" ;; esac
# AND IT DOES NOT ASSERT THE PLATFORM'S ANSWER. The arm above this file's own reproduction
# measured BSD `pgrep` excluding its ancestors, so a refusal claiming the waiter matches
# ITSELF would be wrong here — and a refusal a session can disprove in one command is one it
# learns to argue with. The refusal names the dependency instead.
case "$out" in *"platform-dependent"*) ok "and names the platform dependency rather than asserting past it" ;;
  *) bad "the refusal asserts a self-match this platform does not produce" ;; esac
case "$out" in *"PKMNSCAN_WAIT=off"*) ok "the refusal prints its escape hatch" ;;
  *) bad "the refusal does not name PKMNSCAN_WAIT=off" ;; esac
case "$out" in *"make coordinator"*) ok "the refusal names what to do instead" ;;
  *) bad "the refusal does not name the alternative" ;; esac

# ------------------------------------------------------- 5b. the runaway, backgrounded
cat > "$tmp/autodrive.sh" <<'DRIVER'
#!/usr/bin/env bash
# The 2026-09-12 merge driver's shape: a poll with nothing to end it.
while true; do
  gh pr list --json number
  sleep 120
done
DRIVER
chmod +x "$tmp/autodrive.sh"

judge_bg "$tmp/main" "bash $tmp/autodrive.sh"
if [ $? -eq 2 ]; then ok "a backgrounded script whose loop has no bound is refused"
else bad "the runaway driver was allowed"; fi
case "$out" in *"119 rounds"*) ok "the refusal carries the measured runaway" ;;
  *) bad "the refusal does not name the incident" ;; esac
case "$out" in *"autodrive.sh"*) ok "the refusal names the script it READ, not just the command" ;;
  *) bad "the refusal does not name the script file" ;; esac

refuses "a backgrounded inline poll, \`&\` in the command" \
  "$tmp/main" "while true; do gh pr list; sleep 120; done &"
judge_bg "$tmp/main" "while :; do gh pr checks; sleep 60; done"
if [ $? -eq 2 ]; then ok "a backgrounded inline poll, run_in_background in the payload"
else bad "a backgrounded inline poll was allowed"; fi

# A BOUNDED LOOP IN A BACKGROUNDED SCRIPT IS THE SANCTIONED SHAPE, and this repo has exactly
# one such loop in its own shell: `reap-selftest.sh`'s `-lt 50` wait for a port file.
cat > "$tmp/bounded.sh" <<'BOUNDED'
#!/usr/bin/env bash
tries=0
while [ ! -s "$1" ] && [ "$tries" -lt 50 ]; do sleep 0.2; tries=$((tries + 1)); done
BOUNDED
chmod +x "$tmp/bounded.sh"
judge_bg "$tmp/main" "bash $tmp/bounded.sh /tmp/x"
if [ $? -eq 0 ]; then ok "a backgrounded script whose loop counts to 50 passes"
else bad "the bounded loop was refused"; printf '%s\n' "$out" | head -6; fi

echo ""
echo "  what clause 5 must NEVER refuse"

allows "a bounded retry over a word list" "$tmp/main" "for i in 1 2 3; do curl -sf http://x && break; sleep 2; done"
allows "the sanctioned wait, on a pid"    "$tmp/main" "while ps -p \$PID >/dev/null; do sleep 5; done"
allows "a \`kill -0\` wait, also a pid"    "$tmp/main" "until kill -0 \$PID 2>/dev/null; do sleep 1; done"
allows "a bounded readiness probe"        "$tmp/main" "until curl -m 2 -sf http://localhost:8000/; do sleep 1; done"
allows "a counter"                        "$tmp/main" "n=0; while [ \$n -lt 10 ]; do sleep 1; n=\$((n+1)); done"
allows "a deadline"                       "$tmp/main" "end=\$((\$(date +%s)+60)); while [ \$(date +%s) -lt \$end ]; do sleep 5; done"
allows "a loop with a break"              "$tmp/main" "while true; do check && break; sleep 5; done"
allows "a FOREGROUND poll, which the session is watching" "$tmp/main" "while true; do gh pr list; sleep 120; done"
allows "a loop with no sleep"             "$tmp/main" "while read -r name url want; do echo \$name; done < scripts/views.txt"
allows "a sleep with no loop"             "$tmp/main" "sleep 2; make status"
allows "a blocking wait, which is not a poll" "$tmp/main" "gh pr checks 300 --watch"
allows "the documented way to wait for the suite" "$tmp/main" "make design-check ARGS=--wait"
judge_bg "$tmp/main" "make design-check ARGS=--wait"
if [ $? -eq 0 ]; then ok "…and backgrounded, which is what CLAUDE.md tells a session to do"
else bad "backgrounding design-check was refused"; printf '%s\n' "$out" | head -6; fi
judge_bg "$tmp/main" "make check"
if [ $? -eq 0 ]; then ok "a backgrounded \`make check\` passes"
else bad "a backgrounded make check was refused"; fi

echo ""
echo "  the repo's own lines, swept and pinned"

# EVERY `git`, `gh` AND `ln` LINE THIS REPO'S OWN TOOLING TYPES. The sweep that produced this
# list is in the pull request; the point of pinning them here is that the list cannot rot
# silently — a clause that starts refusing one of these fails this file rather than a session.
for case in \
  'git worktree list --porcelain' \
  'git fetch origin main:main' \
  'git rev-parse --show-toplevel' \
  'git merge-tree HEAD HEAD' \
  'git status --porcelain' \
  'git switch -q main' \
  'git checkout -q -b unmerged-local' \
  'git checkout -q main' \
  'git diff --numstat' \
  'git add -A' \
  'git commit -m "work"' \
  'git push -u origin HEAD' \
  'gh pr create --fill' \
  'gh pr merge 300 --squash' \
  'gh pr checks 300' \
  'gh api repos/o/r/branches/main/protection' \
  'ln -sfn ../CLAUDE.md AGENTS.md' \
; do
  allows "swept: \`$case\`" "$tmp/main" "$case"
done
# `git checkout -- <path>` OVER A CLEAN PATH IS githooks-selftest.sh:131's SHAPE, and it is
# the one swept line whose verdict depends on the tree rather than the string: clean passes,
# dirty is the rule. Both directions are already pinned above; this is the line as typed.
allows "swept: \`git checkout -q -- clean.txt\` (clean)" "$tmp/main" "git checkout -q -- clean.txt"

echo ""
echo "  the escape hatches, in both of PKMNSCAN_KILL's two forms"

allows "checkout, inline" "$tmp/main" "PKMNSCAN_CHECKOUT=off git checkout work.py"
allows "gh, inline"       "$tmp/main" "PKMNSCAN_GH=off gh api repos/o/r -f a=1"
allows "link, inline"     "$tmp/main" "PKMNSCAN_LINK=off ln -s /x work.py"
allows "wait, inline"     "$tmp/main" "PKMNSCAN_WAIT=off until ! pgrep -f x; do sleep 5; done"
allows "tree, inline"     "$WT" "PKMNSCAN_TREE=off cat > $tmp/main/work.py"

hatch_env() {   # hatch_env <name> <cwd> <command>
  out="$(printf '%s' "$3" \
        | CWD="$2" python3 -c 'import json,os,sys; print(json.dumps({"cwd":os.environ["CWD"],"tool_input":{"command":sys.stdin.read()}}))' \
        | env "$1=off" python3 "$GUARD" --hook 2>&1)"
  if [ $? -eq 0 ]; then ok "$1=off in the environment"; else bad "$1=off in the environment did not disarm it"; fi
}
hatch_env PKMNSCAN_CHECKOUT "$tmp/main" "git checkout work.py"
hatch_env PKMNSCAN_GH       "$tmp/main" "gh api repos/o/r -f a=1"
hatch_env PKMNSCAN_LINK     "$tmp/main" "ln -s /x work.py"
hatch_env PKMNSCAN_WAIT     "$tmp/main" "until ! pgrep -f x; do sleep 5; done"

out="$(CWD="$WT" TARGET="$tmp/main/work.py" python3 -c 'import json,os; print(json.dumps({"cwd":os.environ["CWD"],"tool_input":{"file_path":os.environ["TARGET"]}}))' \
      | env PKMNSCAN_TREE=off python3 "$GUARD" --hook 2>&1)"
if [ $? -eq 0 ]; then ok "PKMNSCAN_TREE=off in the environment"; else bad "PKMNSCAN_TREE=off in the environment did not disarm it"; fi

# EVERY CLAUSE HAS A HATCH AND EVERY HATCH IS PRINTED. The table is read rather than retyped,
# so a sixth clause added without one fails here instead of shipping unescapable.
count="$(python3 "$GUARD" --clauses | wc -l | tr -d ' ')"
if [ "$count" = "5" ]; then ok "five clauses, five hatches, read from the guard's own table"
else bad "the clause table has $count rows; this file scores five"; fi
if python3 "$GUARD" --clauses | grep -qv "PKMNSCAN_.*=off"; then
  bad "a clause in the table names no escape hatch"
else
  ok "no clause in the table is missing its hatch"
fi

echo ""
echo "  a broken guard fails OPEN (reap.py's asymmetry, honoured)"

fails_open() {   # fails_open <label> <stdin>
  printf '%s' "$2" | python3 "$GUARD" --hook >/dev/null 2>&1
  if [ $? -eq 0 ]; then ok "$1"; else bad "$1 — it did not fail open"; fi
}

fails_open "an empty payload"            '{}'
fails_open "a payload that is not JSON"  'not json at all'
fails_open "a null tool_input"           '{"tool_input":null}'
fails_open "a tool_input that is a list" '{"tool_input":[1,2,3]}'
fails_open "a null command"              '{"tool_input":{"command":null}}'
fails_open "a payload that is a list"    '[1,2,3]'
fails_open "no stdin at all"             ''
fails_open "an unbalanced quote"         '{"tool_input":{"command":"git checkout '"'"'work.py"}}'
fails_open "an empty file_path"          '{"tool_input":{"file_path":""}}'
fails_open "a cwd that does not exist"   '{"cwd":"/no/such/place","tool_input":{"command":"git checkout work.py"}}'

# THE SHARED PARSER IS A DEPENDENCY, AND A MISSING DEPENDENCY IS A BROKEN GUARD. Copied into
# a throwaway directory WITHOUT `shell_parse.py`, the guard must have no opinion about
# anything rather than raise — the import is guarded for exactly this.
mkdir -p "$tmp/lonely"
cp "$GUARD" "$tmp/lonely/guard-shell.py"
out="$(printf '%s' "git checkout work.py" \
      | CWD="$tmp/main" python3 -c 'import json,os,sys; print(json.dumps({"cwd":os.environ["CWD"],"tool_input":{"command":sys.stdin.read()}}))' \
      | python3 "$tmp/lonely/guard-shell.py" --hook 2>&1)"
if [ $? -eq 0 ]; then ok "with shell_parse.py absent, the guard has no opinion"
else bad "a missing shell_parse.py made the guard refuse (exit non-zero)"; fi
case "$out" in *"shell_parse.py could not be imported"*) ok "…and it SAYS the parser is missing" ;;
  *) bad "a missing parser passed silently: $out" ;; esac

# THE PARSER IS SHARED, SO THE OTHER GUARD MUST STILL WORK. Not a substitute for
# `make silent-write-selftest` — one case, to catch an extraction that broke its neighbour
# without waiting for the suite to reach it.
if [ -f "$HERE/silent-write-guard.py" ]; then
  printf '%s' "git commit -m x >/dev/null 2>&1" \
    | python3 -c 'import json,sys; print(json.dumps({"tool_input":{"command":sys.stdin.read()}}))' \
    | python3 "$HERE/silent-write-guard.py" --hook >/dev/null 2>&1
  if [ $? -eq 2 ]; then ok "the shared parser still serves silent-write-guard.py"
  else bad "silent-write-guard.py no longer refuses a silenced commit — the extraction broke it"; fi
fi

echo ""
printf '  %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ] || exit 1
exit 0
