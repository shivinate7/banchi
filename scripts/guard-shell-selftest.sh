#!/usr/bin/env bash
# `make guard-shell-selftest` — scripts/guard-shell.py, proved by committing its six mistakes.
#
# WHY IT IS NOT A TABLE OF ASSERTIONS. Every clause in that guard claims a command does
# something a session did not intend, and this repo's standard for that kind of claim is
# reproduction: `reap-selftest.sh` reproduces both 2026-09-10 kill incidents with real
# processes and a real socket, `revert-selftest.sh` rebuilds PR #218 and #221, and
# `silent-write-selftest.sh` reproduces the refused commit whose refusal went to /dev/null. So
# five of the six incidents are PERFORMED here first, in a throwaway repository, and only then
# is the guard asked about them:
#
#   1. a file is modified, `git checkout <it>` is run for real, and the work is gone
#   2. a worktree is made, and its root is a different directory from the main checkout's
#   4. `ln -s` at an existing directory creates the nested link instead of failing
#   5. `pgrep -f <tag>` matches the shell whose own command line carries that tag
#   6. a local branch is really made to track a differently-named remote branch — the exact
#      way a background agent's push created one — and `git push origin HEAD` is asked about
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
#
# THE PATTERN LIST IS WIDER THAN "GIT DID NOT UNDERSTAND YOU", because the narrow version let
# the CI failure above through: `git switch -q main` in a fixture whose branch is `master` says
# `fatal: invalid reference: main`, which matched none of the original four patterns — so a
# case asking about a branch that did not exist scored as a PASS for a reason unrelated to the
# predicate. A case that cannot be posed must say so, not quietly count.
real_command() {   # real_command <cwd> <command>
  local said
  said="$( (cd "$1" && eval "$2" ) 2>&1 )"
  case "$said" in
    *"is not a git command"*|*"unknown option"*|*"usage: git"*|*"error: unknown"*|\
    *"unknown switch"*|*"invalid reference"*|*"did not match any file"*|\
    *"pathspec"*"did not match"*|*"not a valid object name"*|*"unknown revision"*)
      bad "the case \`$2\` is not a real command here: $said"
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
#
# THE FIXTURE NAMES ITS OWN DEFAULT BRANCH, and that is not tidiness — it is a CI failure this
# file already had. `git init` takes the branch name from `init.defaultBranch`, which is
# `master` on a fresh GitHub runner and `main` on the author's machine, so two cases here
# (`git checkout main`, `git switch -q main`) asked about a branch that did not exist and this
# selftest was red on Linux while green on macOS. `symbolic-ref` rather than `git init -b`,
# because `-b` needs git 2.28 and this has to work wherever the runner's git is.
git init -q "$tmp/main" 2>/dev/null
(
  cd "$tmp/main" || exit 1
  git symbolic-ref HEAD refs/heads/main
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

# AND THE BRANCH IS ASSERTED, not assumed. Several cases below ask about a branch by NAME, and
# a fixture whose branch is `master` makes those cases resolve to nothing — which this guard
# correctly reports as "no opinion" and which the arms then read as a failure. That is how this
# file was red on a Linux runner and green here, and it is `verify-where-the-gate-runs` in one
# line: a green check proves its own platform.
fixture_branch="$(cd "$tmp/main" && git rev-parse --abbrev-ref HEAD)"
if [ "$fixture_branch" = "main" ]; then
  ok "the fixture's branch is \`main\`, whatever the runner's init.defaultBranch says"
else
  bad "the fixture is on \`$fixture_branch\` — every case naming a branch below is unposable"
fi

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

# A NAMED SOURCE OVER A CLEAN PATH IS GENUINELY SAFE — nothing is at stake, so this stays
# a pass. Run for real first, because a bad sha would make this pass for the wrong reason.
sha="$(cd "$tmp/main" && git rev-parse HEAD)"
if real_command "$tmp/main" "git checkout $sha -- clean.txt"; then
  allows "\`git checkout <sha> -- <path>\` over a CLEAN path" "$tmp/main" "git checkout $sha -- clean.txt"
fi

# A NAMED SOURCE OVER A MODIFIED PATH IS NOT SAFE, AND THE OLD SPEC SAID IT WAS — the exact
# hole #321's own report named: "true of an arbitrary sha and false of HEAD, which is
# byte-identical in effect to the refused \`git checkout -- <path>\`." Closed the same
# session a coordinator ran \`git checkout origin/main -- .\` over a tree that only survived
# because it happened to be clean at that moment — naming a source changes what gets
# WRITTEN, never whether an uncommitted change is discarded first.
refuses "\`git checkout <sha> -- <path>\` over a MODIFIED path — a named source is not a hatch" \
  "$tmp/main" "git checkout $sha -- work.py"
refuses "\`git restore --source=<sha>\` over a MODIFIED path — same hole, the modern name" \
  "$tmp/main" "git restore --source=$sha work.py"
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

# ------------------------------------------- 2b. the quoted script that was read as a write
#
# 2026-09-19: a multi-line `node -e '…'` was refused by this clause. The middle line of the
# script, `const hits=s.filter(i=>/[·•]/.test(String(i.text)));`, is quoted as far as the
# shell is concerned, but the tokenizer fed shlex one LINE at a time, so that line read as a
# command with a `>` in it and `/[·•]/.test` became a redirection target. A regular expression
# literal is not a path. The parent's `split_segments` carries quote state across the newline
# and is what the reader now uses; these arms pin the shape, and the arms after them pin that
# the real writes the clause exists for are still refused — so the next edit cannot trade one
# for the other.
allows "the 2026-09-19 false positive: a multi-line \`node -e\` with a regex literal in it" "$WT" "node -e '
const s = require(\"./out.json\");
const hits=s.filter(i=>/[·•]/.test(String(i.text)));
console.log(hits.length);
' out.json"
allows "the same script on one line"  "$WT" "node -e 'const hits=s.filter(i=>/[·•]/.test(String(i.text)));' out.json"
allows "a multi-line \`python3 -c\` with a \`>\` in it" "$WT" "python3 -c \"
import sys
print(1 > 0, file=sys.stderr)
\""
allows "a quoted string that NAMES the other checkout" "$WT" "echo 'cd $tmp/main && echo x > notes.md' > note.txt"
allows "a \`#\` comment holding an apostrophe, then a write inside this tree" "$WT" "# the driver's shape
echo x > notes.txt"

# THE INCIDENT'S OWN SPELLING WAS A `cd`, AND EVERY WRITE AFTER IT WAS RELATIVE. Until
# 2026-09-19 a relative target resolved against the SESSION's cwd, so `cd <main> && echo x >
# notes.md` — the 2026-09-06 shape, minus nothing — passed. The stages are now walked in
# order and a `cd` moves the directory the targets after it resolve against; and the `cd`
# itself is refused as an act, because the Bash tool's cwd persists between calls and
# `npm run build` writes with no `>` for a redirect reader to see.
refuses "the 2026-09-06 shape: \`cd <main> && echo x > notes.md\`" "$WT" "cd $tmp/main && echo x > notes.md"
refuses "\`cd <main>; … | tee notes.md\`"                          "$WT" "cd $tmp/main; echo x | tee notes.md"
refuses "\`cd <main> && npm run build\` — a write with no \`>\`"     "$WT" "cd $tmp/main && npm run build"
refuses "a bare \`cd <main>\` — the tool's cwd persists"           "$WT" "cd $tmp/main"
judge "$WT" "cd $tmp/main && npm run build"
case "$out" in *"stand in another checkout"*) ok "the \`cd\` refusal says what the act is" ;;
  *) bad "the cd refusal does not name the act" ;; esac
case "$out" in *"PKMNSCAN_TREE=off"*) ok "…and prints the same hatch" ;;
  *) bad "the cd refusal does not name PKMNSCAN_TREE=off" ;; esac
allows  "\`cd\` into a temp directory that is no checkout"          "$WT" "cd $tmp/scratch && echo x > out.log"
allows  "\`cd\` inside this checkout, then a relative write"         "$WT" "cd app && echo x > f"
allows  "\`cd -\`, which this parse cannot place — no opinion"       "$WT" "cd - && echo x > f"
allows  "\`cd\` through an unexpanded variable — no opinion"         "$WT" "cd \$OTHER && echo x > f"
allows  "\`git -C <main> log\` — the read-only form the refusal recommends" "$WT" "git -C $tmp/main log -1"
allows  "a heredoc body that quotes the \`cd\` shape"               "$WT" "git commit -F - <<'MSG'
cd $tmp/main && echo x > notes.md
MSG"

# WRAPPERS, KEYWORDS AND INTERPRETER HEREDOCS SHARED THE BLIND SPOT. `strip_prefixes` stopped
# at a wrapper's own flag, so `env -i tee <path>` resolved to `-i` and no clause saw the tee;
# `if` was not a prefix at all; and a heredoc fed to `bash` had its body stripped as prose.
# All three were measured ALLOWED on 2026-09-19 before the parent's `resolve_command` and
# `strip_heredoc_bodies` were lifted in.
refuses "\`env -i tee <main>/…\` — a wrapper's flag no longer hides the tee"  "$WT" "env -i tee $tmp/main/work.py"
refuses "\`xargs tee <main>/…\`"                                            "$WT" "xargs tee $tmp/main/work.py"
refuses "\`if tee <main>/…; then\` — a keyword is not a command"             "$WT" "if tee $tmp/main/work.py; then :; fi"
refuses "a \`bash <<EOF\` heredoc whose body writes into the other checkout" "$WT" "bash <<'EOF'
echo x > $tmp/main/work.py
EOF"

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

# WHICH PROCESS A WAITER MATCHES IS PLATFORM-DEPENDENT, AND THAT IS MEASURED HERE RATHER THAN
# ASSUMED — in either direction. This arm asserted BSD's answer (`-af` sees the asking shell,
# a bare `-f` does not) and went RED on the Linux runner, where procps excludes only pgrep
# itself and both spellings report 1. The repo has already paid for this family once:
# `pgrep -fc` is not a count on BSD.
#
# So what is asserted is the part that must hold for this clause to have a subject at all —
# `pgrep -f` matches against a COMMAND LINE, so a tag carried only by the asking shell is
# findable — and the exclusion rule is REPORTED as the number it is. An arm that asserted
# either platform's answer would be asserting the thing the refusal deliberately declines to
# claim.
own="guardshell-ancestor-$$-nosuchprocess"
with_a="$(bash -c "true; pgrep -af $own 2>/dev/null | wc -l" | tr -d ' ')"
without_a="$(bash -c "true; pgrep -f $own 2>/dev/null | wc -l" | tr -d ' ')"
if [ "${with_a:-0}" -ge 1 ]; then
  ok "a tag carried ONLY by the asking shell is findable by command line (-af: $with_a, -f: $without_a)"
else
  bad "pgrep -af found nothing for a tag on its own caller's command line — this clause has no subject on this platform"
fi
if [ "${without_a:-0}" -eq "${with_a:-0}" ]; then
  say "note" "this pgrep matches its own ancestors (GNU/procps): -af $with_a, -f $without_a"
else
  say "note" "this pgrep EXCLUDES its own ancestors unless -a (BSD/macOS): -af $with_a, -f $without_a"
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

judge_bg "$tmp/main" "cd $tmp && bash $tmp/autodrive.sh"
if [ $? -eq 2 ]; then ok "…and behind a \`cd\`, which is how a session usually spells it"
else bad "the driver was allowed when it was not the first stage"; fi

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
echo "  6. a push to the wrong branch name, reproduced"

# ------------------------------------------------- 6a. the incident, performed in the fixture
#
# A REAL BARE ORIGIN, because what this clause reads is git CONFIG —
# `branch.<name>.remote` / `.merge` — and the honest way to arm it is the way a background
# agent actually created it: `git push -u origin <local>:<remote>` sets exactly that pair,
# under a DIFFERENT name on each side. A file this section writes is its own
# (`pr-work.txt`), never `work.py`, so nothing here disturbs the dirty state clause 1's own
# cases still depend on.
git init -q --bare "$tmp/origin.git" 2>/dev/null
(
  cd "$tmp/main" || exit 1
  git remote add origin "$tmp/origin.git" 2>/dev/null
  git push -q origin main 2>/dev/null
  git checkout -q -b pr-h-readings-table-local
  echo "the squashed PR work" > pr-work.txt
  git add pr-work.txt
  git commit -q -m "squashed PR work"
  git push -q -u origin pr-h-readings-table-local:claude/pr-h-readings-table 2>/dev/null
) || true

if [ "$(cd "$tmp/main" && git rev-parse --abbrev-ref HEAD)" = "pr-h-readings-table-local" ] &&
   [ "$(cd "$tmp/main" && git config --get branch.pr-h-readings-table-local.merge)" = \
     "refs/heads/claude/pr-h-readings-table" ]; then
  ok "the fixture reproduces the incident: a local branch tracking a DIFFERENTLY named upstream"
else
  bad "the push fixture did not arm — the incident cannot be posed"
fi

echo ""
echo "  the guard refuses it, exactly as it happened"

refuses "the 2026-09-12 command — a coordinator's \`git push origin HEAD\`" \
  "$tmp/main" "git push origin HEAD"
refuses "naming the LOCAL branch literally is the identical trap" \
  "$tmp/main" "git push origin pr-h-readings-table-local"
refuses "\`-u\` does not launder it — it would re-point the tracking AFTER the wrong push" \
  "$tmp/main" "git push -u origin HEAD"
refuses "\`--force\` does not launder it either" \
  "$tmp/main" "git push --force origin HEAD"
refuses "an env prefix does not launder it" \
  "$tmp/main" "PKMNSCAN_MAIN=off git push origin HEAD"

judge "$tmp/main" "git push origin HEAD"
case "$out" in *"pr-h-readings-table-local"*) ok "the refusal names the current branch" ;;
  *) bad "the refusal does not name the current branch" ;; esac
case "$out" in *"claude/pr-h-readings-table"*) ok "the refusal names the tracked upstream" ;;
  *) bad "the refusal does not name the tracked upstream" ;; esac
case "$out" in *"PKMNSCAN_PUSH=off"*) ok "the refusal prints its escape hatch" ;;
  *) bad "the refusal does not name PKMNSCAN_PUSH=off" ;; esac
case "$out" in *"git push origin HEAD:claude/pr-h-readings-table"*) \
  ok "the refusal prints the explicit fix — git's own second form" ;;
  *) bad "the refusal does not print the explicit, correctly-targeted form" ;; esac
case "$out" in *"safety net name the fix"*) \
  ok "the refusal also names the bare \`git push\` form, which lets git print the fix itself" ;;
  *) bad "the refusal does not mention the bare-\`git push\` alternative" ;; esac

echo ""
echo "  what clause 6 must NEVER refuse"

allows "the explicit, correctly-targeted form — this IS the fix" \
  "$tmp/main" "git push origin HEAD:claude/pr-h-readings-table"
allows "an explicit form to somewhere else entirely — not this clause's business" \
  "$tmp/main" "git push origin HEAD:some-other-branch"
allows "a bare \`git push\` — git's OWN safety net owns this shape" \
  "$tmp/main" "git push"
allows "\`git push origin\` with no refspec — same shape, still git's own net" \
  "$tmp/main" "git push origin"

# THE ORDINARY "OPEN A NEW PR" FLOW — no upstream configured at all, the single most common
# case in this repo's own workflow (D42: "a session pushes the branch, `gh pr create` opens
# the PR"). This must never be refused.
(cd "$tmp/main" && git checkout -q -b fresh-pr-branch)
allows "a brand-new branch with no upstream yet — the ordinary first push" \
  "$tmp/main" "git push origin HEAD"
allows "…and with \`-u\`, which is how this repo's own workflow spells it" \
  "$tmp/main" "git push -u origin HEAD"

# AN UPSTREAM THAT ALREADY MATCHES ITS OWN NAME is the safe, ordinary case D42 documents —
# the state every branch here is in the moment after that first push lands.
(cd "$tmp/main" && git push -q -u origin fresh-pr-branch:fresh-pr-branch 2>/dev/null)
allows "an upstream whose name already matches its branch's own" \
  "$tmp/main" "git push origin HEAD"

# THE ORDINARY FIRST PUSH OF A BRANCH CUT *FROM* THE DEFAULT BRANCH — amended 2026-09-13
# (D179). `git switch -c X origin/main` (or `git checkout -b X origin/main`) is how this repo's
# own workflow starts a feature branch, and it DOES configure an upstream — `origin/main` — from
# birth, unlike `fresh-pr-branch` above. Before this amendment that upstream's mismatch with the
# branch's own name refused the push, and the refusal's own remedy told the operator to push at
# `main` by name (`git push origin HEAD:main`) — the one act D42, both git hooks and branch
# protection exist to prevent. `$tmp/origin.git` already carries `main` (line ~614's own push),
# so `origin/main` resolves here exactly as it would for a real `git switch -c X origin/main`.
(cd "$tmp/main" && git switch -q -c cut-from-main origin/main 2>/dev/null)
if [ "$(cd "$tmp/main" && git config --get branch.cut-from-main.merge)" = "refs/heads/main" ]; then
  ok "the fixture reproduces the ordinary case: a branch tracking the DEFAULT branch from birth"
else
  bad "cut-from-main does not track origin/main — this arm cannot be posed"
fi
allows "the ordinary first push of a branch cut from the default branch — must never refuse" \
  "$tmp/main" "git push origin HEAD"
allows "…and with \`-u\`, the same shape this repo's own workflow types" \
  "$tmp/main" "git push -u origin HEAD"

judge "$tmp/main" "git push origin HEAD"
case "$out" in
  *"HEAD:main"*|*"branch --unset-upstream"*)
    bad "a still-refused case's remedy must never name the default branch, and this one did" ;;
  *) ok "no remedy naming the default branch appears (there is no refusal at all)" ;;
esac

# THE PRIMARY PATH, NOT ONLY THE FALLBACK. `refs/remotes/<remote>/HEAD` is what a real
# `git clone` sets, and it is what `_default_branch` reads FIRST — but this fixture is built by
# `git init` + `remote add` + `push`, never a `clone`, so nothing above has exercised that read
# at all; every "cut-from-main" case so far passed off the local `main`/`master` fallback alone.
# Set the symbolic ref by hand, the way `git remote set-head origin -a` would, so the
# symbolic-ref branch and its `origin/` prefix-stripping are actually proven rather than merely
# unreached.
(cd "$tmp/main" && git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main)
if [ "$(cd "$tmp/main" && git symbolic-ref --quiet --short refs/remotes/origin/HEAD)" = "origin/main" ]; then
  ok "the fixture now carries a real \`origin/HEAD\` symbolic ref, unstripped, as git writes it"
else
  bad "refs/remotes/origin/HEAD did not take — the primary-path arm cannot be posed"
fi
allows "the primary default-branch path (a real \`origin/HEAD\`) exempts the same push" \
  "$tmp/main" "git push origin HEAD"
(cd "$tmp/main" && git symbolic-ref --delete refs/remotes/origin/HEAD 2>/dev/null)

# A DIFFERENT REMOTE THAN THE ONE TRACKED — a fork workflow, untouched by this clause: the
# mismatch this clause reads is specific to the remote the command is about to push to.
(cd "$tmp/main" && git remote add fork "$tmp/origin.git" 2>/dev/null)
allows "a push to a remote this branch does not track — a fork workflow" \
  "$tmp/main" "git push fork HEAD"

(cd "$tmp/main" && git checkout -q pr-h-readings-table-local)
# THE SAME FORK CHECK, AGAINST THE ACTUALLY-MISMATCHED BRANCH — the discriminating version.
# `fresh-pr-branch`'s tracked name matched its own, so a guard that forgot to compare the
# REMOTE at all could still pass that case by coincidence, off the name check alone. This
# branch's tracked name genuinely differs, so only a real remote comparison keeps it a pass.
allows "the mismatch is REMOTE-specific — a different remote sees no upstream at all" \
  "$tmp/main" "git push fork HEAD"
allows "an entirely unrelated branch name — not HEAD-shaped at all" \
  "$tmp/main" "git push origin some-other-branch-entirely"
allows "\`--all\` pushes something other than \"this branch\"" \
  "$tmp/main" "git push origin --all"
allows "\`--tags\`, the same reason" \
  "$tmp/main" "git push origin --tags"
# NAMES THE CURRENT BRANCH ITSELF, on purpose — deleting a remote ref by that name is not
# "pushing this branch under its own name", and a mutation that stopped recognising `--delete`
# as special would refuse this one for the wrong reason (it would read the deleted name as a
# HEAD-shaped refspec and find the same mismatch clause 6 exists for).
allows "\`--delete\`, the same reason — even naming the branch itself" \
  "$tmp/main" "git push origin --delete pr-h-readings-table-local"

(cd "$tmp/main" && git checkout -q --detach 2>/dev/null)
allows "a detached HEAD — nothing this clause can name as \"the current branch\"" \
  "$tmp/main" "git push origin HEAD"

(cd "$tmp/main" && git checkout -q main 2>/dev/null)

echo ""
echo "  7. a consuming/destructive stash, reproduced"

# --------------------------------------------------- 7a. the incident, performed in the fixture
#
# A SECOND, ANONYMOUS ENTRY, LOST TO A BARE POP — the shape the parent CLAUDE.md's mandate
# names, reproduced rather than merely asserted about: session A pushes an untagged entry,
# session B (another worktree sharing this same stack) pushes its own, and a bare
# `git stash pop` — typed by either session, meaning "get MY work back" — hands back B's
# entry to A, or A's own entry is gone under B's next `pop` before A ever sees it again.
(
  cd "$tmp/main" || exit 1
  printf 'session A change\n' >> work.py
  git stash push -q
  printf 'session B change\n' >> work.py
  git stash push -q
  # the bare pop a session actually types, expecting to get its OWN work back
  git stash pop -q
  grep -q "session B change" work.py && ! grep -q "session A change" work.py
)
if [ $? -eq 0 ]; then
  ok "a bare \`git stash pop\` handed back the WRONG entry — session A's own push is still on the stack, unreachable by anything but luck"
else
  bad "the stash incident did not reproduce as described"
fi
# THE CLEANUP THAT NEVER RAN. This line used to read `git stash clear -q`, and `clear` takes
# no options: git answered `error: unknown switch \`q'` with exit 129, `2>/dev/null` ate it,
# and the `&&` short-circuited so the `checkout` never ran either. Every refusal case below
# therefore ran over a one-entry stack BY ACCIDENT for as long as clause 7 existed — and
# since the clause did not read the stack at all, nothing could tell that apart from a real
# refusal. Both halves are now deliberate and asserted, which is the whole point of 7b.
(cd "$tmp/main" && git stash clear 2>/dev/null; git checkout -q -- work.py 2>/dev/null)
(cd "$tmp/main" && printf 'one\ntwo\nthree\nfour\n' > work.py)

echo ""
echo "  7b. AN EMPTY STACK IS NOT A SUBJECT — the clause resolves before it refuses"

# THE ARM THAT GOES RED ON THE DEFECT. Measured 2026-09-17: before the stack reader landed,
# these three verdicts over an EMPTY stack were byte-identical to the ones over a real entry,
# while `git stash pop` itself answers "No stash entries found." A guard whose answer does not
# move when its subject does is matching the SUBCOMMAND NAME — `reap.py`'s `\bpkill\b` defect,
# one command over. Revert `_stash_entries` and all three of these go red.
stack_depth() { (cd "$1" && git stash list | wc -l | tr -d ' '); }

if [ "$(stack_depth "$tmp/main")" = "0" ]; then
  ok "the fixture's stack is genuinely empty — the arm below has the subject it claims"
else
  bad "the fixture's stack is NOT empty, so the empty-stack arm proves nothing"
fi
allows "\`git stash pop\` over an EMPTY stack — nothing to consume, and git itself refuses it" \
  "$tmp/main" "git stash pop"
allows "\`git stash clear\` over an EMPTY stack — it destroys nothing" \
  "$tmp/main" "git stash clear"
allows "\`git stash drop\` over an EMPTY stack — there is no \`stash@{0}\` to drop" \
  "$tmp/main" "git stash drop"
refuses "a bare \`git stash\` is refused EVEN over an empty stack — it is a push, and its hazard is identification, not consumption" \
  "$tmp/main" "git stash"

# Now put a real entry on the stack, deliberately, so every case below has a subject.
(cd "$tmp/main" && printf 'work to set aside\n' >> work.py && git stash push -q -m "selftest entry")
if [ "$(stack_depth "$tmp/main")" = "1" ]; then
  ok "one real entry is on the stack — the refusal cases below are not vacuous"
else
  bad "the fixture could not put an entry on the stack"
fi

echo ""
echo "  the guard refuses it"

refuses "a bare \`git stash\` — the same six characters mean \"save\" AND \"restore\"" \
  "$tmp/main" "git stash"
refuses "\`git stash -u\`, still no subcommand named" "$tmp/main" "git stash -u"
refuses "\`git stash pop\`, unconditionally" "$tmp/main" "git stash pop"
refuses "\`git stash pop\` with an explicit index — pop is refused either way" \
  "$tmp/main" "git stash pop stash@{0}"
refuses "\`git stash drop\` with no entry named — defaults to \`stash@{0}\`" \
  "$tmp/main" "git stash drop"
refuses "\`git stash clear\` — takes no target, always destroys the whole stack" \
  "$tmp/main" "git stash clear"
refuses "an env prefix does not launder it" \
  "$tmp/main" "PKMNSCAN_MAIN=off git stash pop"
refuses "buried mid-script behind a \`&&\`" \
  "$tmp/main" "echo tidy && git stash drop"

judge "$tmp/main" "git stash pop"
case "$out" in *"PKMNSCAN_STASH=off"*) ok "the refusal prints its escape hatch" ;;
  *) bad "the refusal does not name PKMNSCAN_STASH=off" ;; esac
case "$out" in *"per-CLONE"*) ok "the refusal explains the shared-stack hazard" ;;
  *) bad "the refusal does not explain why the stack is shared" ;; esac
case "$out" in *"never a stash"*) ok "the refusal's remedy names a commit on your own branch" ;;
  *) bad "the refusal's remedy does not tell the caller to commit instead" ;; esac
case "$out" in *"stash push"*) bad "the remedy still offers a tagged stash — a tag fixes identification only, and the entry still belongs to no branch and dies with the session holding the tag" ;;
  *) ok "the remedy offers no stash form at all, tagged or otherwise" ;; esac
case "$out" in *"working tree"*) ok "the refusal states a worktree count" ;;
  *) bad "the refusal does not say how many trees share the stack" ;; esac

echo ""
echo "  what clause 7 must NEVER refuse"

for case in \
  'git stash push -u -m "a tag"' \
  'git stash push' \
  'git stash list' \
  'git stash show stash@{0}' \
  'git stash apply stash@{0}' \
  'git stash apply' \
  'git stash drop stash@{1}' \
  'git stash drop deadbeef' \
  'git stash branch some-branch' \
; do
  allows "an identified or non-destructive form: \`$case\`" "$tmp/main" "$case"
done

echo ""
echo "  8. a hard-family reset, reproduced"

# --------------------------------------------------- 8a. the incident, performed in the fixture
(
  cd "$tmp/main" || exit 1
  printf 'one\ntwo\nthree\nfour\n' > work.py
  for i in $(seq 1 100); do printf 'reset would destroy this line %s\n' "$i" >> work.py; done
  wc -l < work.py | tr -d ' ' > "$tmp/reset-before"
  git reset -q --hard 2>/dev/null
  wc -l < work.py | tr -d ' ' > "$tmp/reset-after"
)
if [ "$(cat "$tmp/reset-before")" = "104" ] && [ "$(cat "$tmp/reset-after")" = "3" ]; then
  ok "\`git reset --hard\` destroyed 100 uncommitted lines, silently and without asking"
else
  bad "the reset incident did not reproduce: $(cat "$tmp/reset-before") before, $(cat "$tmp/reset-after") after"
fi
(cd "$tmp/main" && printf 'one\ntwo\nthree\nfour\nfive\n' > work.py)

echo ""
echo "  the guard refuses it"

refuses "the bare form" "$tmp/main" "git reset --hard"
refuses "against an explicit commit" "$tmp/main" "git reset --hard HEAD"
refuses "\`--merge\`, the same discard" "$tmp/main" "git reset --merge"
refuses "\`--keep\`, the same discard" "$tmp/main" "git reset --keep"
refuses "an env prefix does not launder it" "$tmp/main" "PKMNSCAN_MAIN=off git reset --hard"
refuses "buried mid-script behind a \`&&\`" "$tmp/main" "echo tidy && git reset --hard"

judge "$tmp/main" "git reset --hard"
case "$out" in *"PKMNSCAN_RESET=off"*) ok "the refusal prints its escape hatch" ;;
  *) bad "the refusal does not name PKMNSCAN_RESET=off" ;; esac
case "$out" in *".bak"*) ok "the refusal names the \`.bak\` copy as the way to do it safely" ;;
  *) bad "the refusal does not name the .bak shape" ;; esac
case "$out" in *"is modified"*) ok "the refusal names the modified file" ;;
  *) bad "the refusal does not say which file is modified" ;; esac
case "$out" in *"reference-transaction"*) \
  ok "the refusal names the ref hook as the OTHER half, so a reader does not think it is redundant" ;;
  *) bad "the refusal does not distinguish itself from the ref hook" ;; esac

echo ""
echo "  what clause 8 must NEVER refuse"

for case in \
  'git reset' \
  'git reset --mixed' \
  'git reset --soft' \
  'git reset --soft HEAD~0' \
  'git reset -- work.py' \
  'git reset HEAD -- work.py' \
; do
  if real_command "$tmp/main" "$case"; then
    allows "soft/mixed or a path-form reset — never destroys the working tree: \`$case\`" \
      "$tmp/main" "$case"
  fi
done

(cd "$tmp/main" && git add work.py && git commit -q -m "clean it up for the clean-tree case")
allows "\`--hard\` over a genuinely clean tree — nothing to lose" "$tmp/main" "git reset --hard"
(cd "$tmp/main" && printf 'one\ntwo\nthree\nfour\nfive\n' > work.py)

echo ""
echo "  9. a narrated wait with nobody watching it"

# ------------------------------------------- 9a. the incident, performed in the fixture
# A REAL NARRATOR, A REAL PIPE, A REAL `tail`. `make merge` prints a heartbeat line a minute
# while it waits four to five minutes for the claim commit's checks; this is the same shape in
# miniature — five lines over a second — and it measures BOTH halves of what the pipe does:
# nothing has reached the sink while the command is still running, and most of it is gone by
# the time it has. No loop and no poll: one bounded sleep and a `wait` on a job this script
# started, which is the sanctioned shape clause 5 itself recommends.
cat > "$tmp/narrator.py" <<'NAR'
import sys, time
for i in range(1, 6):
    print("%dm - waiting on check runs (%d of 5)" % (i, i))
    time.sleep(0.2)
NAR

: > "$tmp/piped.txt"
( python3 "$tmp/narrator.py" | tail -2 > "$tmp/piped.txt" ) &
narrator_job=$!
sleep 0.6
mid="$(wc -c < "$tmp/piped.txt" | tr -d ' ')"
wait "$narrator_job" 2>/dev/null
kept="$(wc -l < "$tmp/piped.txt" | tr -d ' ')"
plain="$(python3 "$tmp/narrator.py" | wc -l | tr -d ' ')"

if [ "$mid" = "0" ]; then
  ok "MID-RUN THE PIPE HAD DELIVERED NOTHING — 0 bytes at the sink while the narrator was still going, which is why correct waiting reads as a hang"
else
  bad "the buffering half did not reproduce: $mid bytes had already arrived mid-run"
fi
if [ "$plain" = "5" ] && [ "$kept" = "2" ]; then
  ok "and \`tail -2\` kept 2 of the 5 heartbeat lines the same command prints in full when nothing follows it"
else
  bad "the truncation half did not reproduce: $plain lines plain, $kept through the pipe"
fi

echo ""
echo "  the guard refuses it"

refuses "the 2026-09-20 command" "$tmp/main" "make merge ARGS=\"437 --confirm\" 2>&1 | tail -18"
refuses "\`| head\`, the same loss from the other end" "$tmp/main" "make merge ARGS=\"437 --confirm\" | head -20"
refuses "stdout to /dev/null" "$tmp/main" "make merge ARGS=\"437 --confirm\" >/dev/null"
refuses "into a file nothing in the command reads back" "$tmp/main" "make merge ARGS=\"437 --confirm\" > merge.log"
refuses "\`tail\` with no count" "$tmp/main" "make merge ARGS=\"437 --confirm\" 2>&1 | tail"
refuses "the script run directly, which is the same act" "$tmp/main" "python3 scripts/merge-pr.py 437 --confirm | tail -5"
refuses "buried mid-script behind a \`&&\`" "$tmp/main" "git fetch origin && make merge ARGS=\"437 --confirm\" | tail -30"
refuses "an env prefix does not launder it" "$tmp/main" "PKMNSCAN_MAIN=off make merge ARGS=\"437 --confirm\" | tail -5"

judge "$tmp/main" "make merge ARGS=\"437 --confirm\" 2>&1 | tail -18"
case "$out" in *"PKMNSCAN_NARRATE=off"*) ok "the refusal prints its escape hatch" ;;
  *) bad "the refusal does not name PKMNSCAN_NARRATE=off" ;; esac
case "$out" in *"four to"*) ok "the refusal says the wait is CORRECT and how long it takes, so nobody 'fixes' the waiting" ;;
  *) bad "the refusal does not defend the wait itself" ;; esac
case "$out" in *"no pipe"*) ok "and it names the remedy: run it with nothing after it" ;;
  *) bad "the refusal does not say what to do instead" ;; esac
# THE HOUSE RULE: a refusal's printed remedy never names the forbidden target. A remedy that
# spelled out the piped form would be handing back the command it just refused.
case "$out" in *"| tail"*) bad "the refusal's own text spells out the forbidden pipe" ;;
  *) ok "and the remedy never spells the forbidden form back at the reader" ;; esac

# THE ROSTER IS RECONCILED RATHER THAN TRUSTED. This clause names commands instead of
# resolving them, so the one thing that can be checked mechanically IS checked: every command
# it names still carries a heartbeat in the file that runs it. An entry that stops narrating
# stops being this clause's business, and this is where that is noticed.
python3 - "$GUARD" "$HERE" <<'ROSTER'
import importlib.util, pathlib, sys
spec = importlib.util.spec_from_file_location("guard_shell", sys.argv[1])
guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
here = pathlib.Path(sys.argv[2]).parent
bad = 0
for name, goal, path, constant in guard.NARRATORS:
    source = here / path
    if not source.exists():
        print("MISSING %s, named by the narrate clause for %s" % (path, name)); bad = 1
    elif constant not in source.read_text(encoding="utf-8"):
        print("%s no longer carries %s — %s may not narrate any more" % (path, constant, name)); bad = 1
sys.exit(bad)
ROSTER
if [ $? -eq 0 ]; then ok "every command the narrate clause names still carries a heartbeat constant in the file that runs it"
else bad "the narrate roster names a command that no longer narrates"; fi

echo ""
echo "  what clause 9 must NEVER refuse"
# THIS IS THE HALF THAT DECIDES WHETHER THE CLAUSE SURVIVES. A guard that fires on `git log |
# tail` is a guard nobody keeps. Every line here is one this repo types.

for case in \
  'make merge ARGS="437 --confirm"' \
  'make merge ARGS=437' \
  'make merge ARGS=437 | tail -20' \
  'make merge-selftest | tail -5' \
  'make check 2>&1 | tail -40' \
  'make harness | tail -20' \
  'make docs-audit >/dev/null' \
  'git log --oneline -20 | head -5' \
  'make claim-stale | tail -3' \
  'make design-check ARGS=--wait | tail -5' \
  'gh pr view 437 --json mergeable | head -1' \
; do
  allows "never this clause's business: \`$case\`" "$tmp/main" "$case"
done
allows "\`| tee\` keeps every byte, so it is not refused" "$tmp/main" "make merge ARGS=\"437 --confirm\" 2>&1 | tee $tmp/merge.log"
allows "a file the same command reads back is not a discard" "$tmp/main" "make merge ARGS=\"437 --confirm\" > $tmp/m.log 2>&1; cat $tmp/m.log"

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

# THE PUSH HATCH IS TESTED AGAINST THE MISMATCHED BRANCH, not against `main` — `main` never
# had a tracked upstream configured in this fixture, so the command would pass with or
# without the hatch and the test would prove nothing about the hatch itself.
(cd "$tmp/main" && git checkout -q pr-h-readings-table-local 2>/dev/null)
allows "push, inline"    "$tmp/main" "PKMNSCAN_PUSH=off git push origin HEAD"
(cd "$tmp/main" && git checkout -q main 2>/dev/null)

allows "stash, inline"   "$tmp/main" "PKMNSCAN_STASH=off git stash pop"
allows "reset, inline"   "$tmp/main" "PKMNSCAN_RESET=off git reset --hard"
allows "narrate, inline" "$tmp/main" "PKMNSCAN_NARRATE=off make merge ARGS=\"437 --confirm\" | tail -5"

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
hatch_env PKMNSCAN_PUSH     "$tmp/main" "git push origin HEAD"
hatch_env PKMNSCAN_STASH    "$tmp/main" "git stash pop"
hatch_env PKMNSCAN_RESET    "$tmp/main" "git reset --hard"
hatch_env PKMNSCAN_NARRATE  "$tmp/main" "make merge ARGS=\"437 --confirm\" | tail -5"
(cd "$tmp/main" && git checkout -q main 2>/dev/null)

out="$(CWD="$WT" TARGET="$tmp/main/work.py" python3 -c 'import json,os; print(json.dumps({"cwd":os.environ["CWD"],"tool_input":{"file_path":os.environ["TARGET"]}}))' \
      | env PKMNSCAN_TREE=off python3 "$GUARD" --hook 2>&1)"
if [ $? -eq 0 ]; then ok "PKMNSCAN_TREE=off in the environment"; else bad "PKMNSCAN_TREE=off in the environment did not disarm it"; fi

# EVERY CLAUSE HAS A HATCH AND EVERY HATCH IS PRINTED. The table is read rather than retyped,
# so a seventh clause added without one fails here instead of shipping unescapable.
count="$(python3 "$GUARD" --clauses | wc -l | tr -d ' ')"
if [ "$count" = "9" ]; then ok "nine clauses, nine hatches, read from the guard's own table"
else bad "the clause table has $count rows; this file scores nine"; fi
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
