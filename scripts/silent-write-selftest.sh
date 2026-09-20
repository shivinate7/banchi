#!/usr/bin/env bash
# `make silent-write-selftest` — scripts/silent-write-guard.py, proved by violating it.
#
# WHY THIS EXISTS, AND WHY IT IS NOT A TABLE OF ASSERTIONS. The guard's whole claim is that it
# can tell a git write whose output the session will read from one whose output is thrown away.
# This repo's standard for that kind of claim is reproduction: `reap-selftest.sh` reproduces
# both 2026-09-10 kill incidents with real processes and a real socket rather than asserting
# about them, and `revert-selftest.sh` rebuilds PR #218 and #221. So the first thing this file
# does is REPRODUCE THE 2026-09-12 INCIDENT end to end in a throwaway repository — a pre-commit
# hook that refuses, a commit whose refusal goes to /dev/null, and a `git log --oneline -1` that
# answers with the PREVIOUS commit — and only then asks the guard about it.
#
# That ordering matters. The reproduction is what proves the case is real; the verdict is what
# proves the guard sees it. An arm that only ever asked the guard about a string somebody typed
# would pass just as well over a command that cannot happen.
#
# THE FALSE POSITIVES ARE THE OTHER HALF, AND THEY ARE THE HALF THAT DECIDES WHETHER THIS GUARD
# SURVIVES. `git rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1`, `git fetch origin -q
# 2>/dev/null` and `git merge --abort 2>/dev/null` are ordinary, constant, and discard nothing
# that could ever be a refusal of a write. A guard that fires on them is worse than no guard,
# because it teaches every session to reach for the escape hatch by reflex. Each one is pinned
# here as PASSING, and each is RUN in the fixture first — a case that is secretly a typo would
# sail past the guard for the wrong reason, which is `a-guard-must-see-its-subject`'s lesson
# applied to a shell string instead of a Playwright selector.
#
# WHY IT IS NOT IN THE GIT HOOK. D18: it writes a temp repository. It IS in `make check`, which
# is exactly reap-selftest's and janitor-selftest's standing.
#
# WHAT IT CANNOT PROVE. That Claude Code actually invokes the hook, or that exit 2 blocks a
# tool call — both are the harness's behaviour and not this repo's. `.claude/settings.json` and
# `.codex/hooks.json` are what arm it and `make docs-audit`'s `codex hooks` row is what keeps
# those two rosters honest with each other.

set -uo pipefail          # NOT -e: every case must run and be scored

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARD="$HERE/silent-write-guard.py"
pass=0
fail=0

[ -f "$GUARD" ] || { echo "no silent-write-guard.py beside this script"; exit 1; }

tmp="$(mktemp -d "${TMPDIR:-/tmp}/pkmnscan-silent.XXXXXX")" || { echo "cannot make a temp dir"; exit 1; }
cleanup() { rm -rf "$tmp"; return 0; }
trap cleanup EXIT

say()  { printf '  %-6s %s\n' "$1" "$2"; }
ok()   { pass=$((pass + 1)); say "ok" "$1"; }
bad()  { fail=$((fail + 1)); say "FAIL" "$1"; }

# The hook, asked about one command exactly as Claude Code asks it: the payload on stdin, the
# verdict as an exit code, the reason on stderr. `out` carries both streams so a failing case
# can be read.
judge() {   # judge <command> -> exit code, output in $out
  out="$(printf '%s' "$1" \
        | python3 -c 'import json,sys; print(json.dumps({"tool_input":{"command":sys.stdin.read()}}))' \
        | python3 "$GUARD" --hook 2>&1)"
  return $?
}

refuses() {   # refuses <label> <command>
  judge "$2"
  if [ $? -eq 2 ]; then ok "$1"; else bad "$1 — the guard allowed it"; fi
}

allows() {    # allows <label> <command>
  judge "$2"
  local status=$?
  if [ $status -eq 0 ]; then
    ok "$1"
  else
    bad "$1 — the guard refused a command it must never refuse (exit $status)"
    printf '%s\n' "$out" | sed 's/^/           /' | head -6
  fi
}

# A FALSE-POSITIVE CASE IS RUN BEFORE IT IS SCORED. A misspelled git command is refused by git,
# not by this guard, and would score as "allowed" for a reason that has nothing to do with the
# predicate. So each read case has to be a command git actually recognises in a real repository.
# Exit status is NOT the test — `git rev-parse --verify MERGE_HEAD` exits 1 when there is no
# merge in progress, which is the whole point of it — so what is checked is that git did not
# reject the command line itself.
real_command() {   # real_command <label> <command>
  local said
  said="$( (cd "$tmp/repo" && eval "$1" ) 2>&1 )"
  case "$said" in
    *"is not a git command"*|*"unknown option"*|*"usage: git"*|*"error: unknown"*)
      bad "the case \`$1\` is not a real command: $said"
      return 1 ;;
  esac
  return 0
}

# ------------------------------------------------------------------------------- the fixture
#
# A REPOSITORY WITH A HOOK THAT REFUSES, which is the whole mechanism of the incident: the
# pre-commit hook that actually refused on 2026-09-12 is this repo's own, and pointing this
# test at it would mean running the opsec guard and the docs audit inside a self-test. A hook
# that prints to stderr and exits 1 is the same shape and is all the case needs.
mkdir -p "$tmp/repo/hooks"
git init -q "$tmp/repo" 2>/dev/null
(
  cd "$tmp/repo" || exit 1
  git config user.email "selftest@example.invalid"
  git config user.name "silent write selftest"
  git config commit.gpgsign false
  git config core.hooksPath hooks
  # A first, real commit. THE STALE READ IS THE POINT: `git log --oneline -1` after a refused
  # commit answers with THIS one, and a session that reads it sees a real commit with a real
  # subject — which is exactly what was mistaken for the commit that had just been refused.
  printf 'one\n' > a.txt
  git add a.txt
  git commit -q -m "the commit before" 2>/dev/null
) || { echo "cannot build the fixture repo"; exit 1; }

cat > "$tmp/repo/hooks/pre-commit" <<'HOOK'
#!/usr/bin/env bash
echo "REFUSED: the fixture's pre-commit hook always refuses (stderr)" >&2
exit 1
HOOK
chmod +x "$tmp/repo/hooks/pre-commit"

echo "silent-write-selftest — fixture at $tmp"
echo ""
echo "  the incident, reproduced"

# ------------------------------------------------------------- 1. the incident, reproduced
(
  cd "$tmp/repo" || exit 1
  printf 'two\n' > b.txt
  git add b.txt
  # THE COMMAND AS IT WAS TYPED ON 2026-09-12. Every byte of the refusal goes to /dev/null.
  git commit -q -F - >/dev/null 2>&1 <<'MSG'
the commit that never happened
MSG
  echo "$?" > "$tmp/commit-status"
  git log --oneline -1 --format=%s > "$tmp/stale-read"
  git rev-parse HEAD > "$tmp/head-after"
  git rev-parse HEAD~0 >/dev/null 2>&1
  git log --oneline | wc -l | tr -d ' ' > "$tmp/count"
)

if [ "$(cat "$tmp/commit-status" 2>/dev/null)" != "0" ]; then
  ok "the fixture's commit was REFUSED (non-zero), and said nothing at all"
else
  bad "the fixture's commit succeeded — the hook did not refuse, so there is no incident here"
fi

if [ "$(cat "$tmp/stale-read" 2>/dev/null)" = "the commit before" ]; then
  ok "\`git log --oneline -1\` answers with the PREVIOUS commit — the stale read, reproduced"
else
  bad "the stale read did not reproduce: git log said '$(cat "$tmp/stale-read" 2>/dev/null)'"
fi

if [ "$(cat "$tmp/count" 2>/dev/null)" = "1" ]; then
  ok "one commit in the repository: nothing landed, and nothing said so"
else
  bad "expected 1 commit after the refusal, found $(cat "$tmp/count" 2>/dev/null)"
fi

echo ""
echo "  the guard refuses what hid it"

# ------------------------------------------------------ 2. the guard's verdict on that command
INCIDENT="git commit -q -F - >/dev/null 2>&1 <<'MSG'
the commit that never happened
MSG"

judge "$INCIDENT"
if [ $? -eq 2 ]; then
  ok "the incident command is refused"
else
  bad "the incident command was ALLOWED — this guard's one job"
fi

# THE REFUSAL'S CONTENT IS SCORED, NOT ONLY ITS EXIT CODE. A refusal that does not name the
# escape hatch is the thing CLAUDE.md forbids repo-wide, and one that does not say which stream
# went where is one a session argues with instead of learning from.
judge "$INCIDENT"
case "$out" in
  *"PKMNSCAN_SILENT=off"*) ok "the refusal prints the escape hatch" ;;
  *) bad "the refusal does not name PKMNSCAN_SILENT=off" ;;
esac
case "$out" in
  *"stdout -> /dev/null"*) ok "the refusal names stdout's destination" ;;
  *) bad "the refusal does not say where stdout went" ;;
esac
case "$out" in
  *"stderr -> /dev/null"*) ok "the refusal names stderr's destination" ;;
  *) bad "the refusal does not say where stderr went" ;;
esac

# A HEREDOC BODY IS A DOCUMENT, NOT A COMMAND. The message of the commit that announces this
# guard contains the string `>/dev/null`, and a guard that read its own commit message as a
# silenced write would fire on a command that silences nothing. This arm is the mirror of
# `reap.py`'s: there, a script being WRITTEN must not be read as a kill.
refuses "a redirect in the heredoc BODY is prose, and the real one is still caught" \
  "git commit -F - >/dev/null 2>&1 <<'MSG'
this entry is about >/dev/null 2>&1 and why it hides a refusal
MSG"
allows "a heredoc body that mentions a redirect, on a write that is NOT silenced" \
  "git commit -F - <<'MSG'
this entry is about >/dev/null 2>&1 and why it hides a refusal
MSG"

# THE ARM THAT ACTUALLY NEEDS THE STRIPPER, and it was missing until a mutation run said so:
# with heredoc bodies left in, the three arms above still pass, because `tokenize` splits by
# line and a body line starting with prose has no write verb at its head. The case that only
# the stripper can answer is a body line that IS a command — a commit message or a decision
# entry quoting the offending command on a line of its own, which is exactly what the entry
# announcing this guard does. Removing `strip_heredocs` was a SURVIVOR of a 20-arm mutation
# run until this arm existed.
allows "a heredoc body whose own line quotes a silenced command" \
  "git commit -F - <<'MSG'
Reproduce it with:

git commit -m x >/dev/null 2>&1

MSG"

# AND THE STRIPPER RESUMES AT THE TERMINATOR rather than dropping the rest of the script. A
# stripper that swallowed everything after the first `<<` — which is `reap.py:_segments`'s
# trade, right for its question — would let this one through.
refuses "a silenced write AFTER a heredoc's terminator" \
  "git commit -F - <<'MSG'
an ordinary message
MSG
git push >/dev/null 2>&1"

echo ""
echo "  every shape that hides a refusal"

refuses "both streams, the canonical spelling"        "git commit -m x >/dev/null 2>&1"
refuses "stderr alone — the hook's refusal"           "git commit -m x 2>/dev/null"
refuses "stdout alone — \`[branch sha]\`, the only proof" "git commit -m x >/dev/null"
refuses "bash's \`&>\`"                                "git commit -m x &>/dev/null"
refuses "\`2>&1 >/dev/null\`, which keeps stderr and loses the proof" "git commit -m x 2>&1 >/dev/null"
refuses "a closed descriptor"                         "git commit -m x 2>&-"
refuses "an append to /dev/null"                      "git commit -m x >>/dev/null 2>&1"
refuses "a file the command never reads back"         "git commit -m x > $tmp/out.log 2>&1"
refuses "\`|&\` into a discard"                        "git commit -m x |& cat >/dev/null"
refuses "a push, whose progress is ALL on stderr"     "git push 2>/dev/null"
refuses "a push, both streams"                        "git push origin HEAD >/dev/null 2>&1"
refuses "a merge"                                     "git merge --no-ff other >/dev/null 2>&1"
refuses "a rebase"                                    "git rebase main 2>/dev/null"
refuses "a cherry-pick"                               "git cherry-pick abc123 >/dev/null"
refuses "a pull — the local half of a merge"          "git pull --ff-only >/dev/null 2>&1"
refuses "\`git -C <tree> pull\`, which CLAUDE.md tells a session to type" \
  "git -C /some/tree pull --ff-only >/dev/null"
refuses "\`git fetch origin main:main\`, which moves refs/heads/main" \
  "git fetch origin main:main >/dev/null 2>&1"
refuses "\`make merge\`, both halves of D42's operation" \
  "make merge ARGS=\"300 --confirm\" >/dev/null 2>&1"
refuses "\`gh pr merge\`"                              "gh pr merge 300 --squash >/dev/null 2>&1"
refuses "a write buried mid-script"                   "git status; git commit -m x 2>/dev/null; echo done"
refuses "a write behind a \`cd\` and an \`&&\`"         "cd /x && git commit -m x >/dev/null 2>&1 && git push"
refuses "an env prefix does not launder it"           "PKMNSCAN_MAIN=off git commit -m x >/dev/null 2>&1"
refuses "a line continuation does not launder it"     "git commit \\
  -m x \\
  >/dev/null 2>&1"

echo ""
echo "  what it must NEVER refuse"

# THE FOUR CLAUDE.md AND THE TASK NAME BY HAND. Each is run in the fixture first.
for case in \
  'git rev-parse --show-toplevel 2>/dev/null' \
  'git fetch origin -q 2>/dev/null' \
  'git merge --abort 2>/dev/null' \
  'git rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1' \
  'git log --oneline -1 >/dev/null' \
  'git diff --quiet 2>/dev/null' \
  'git status --short >/dev/null 2>&1' \
  'git merge-base main HEAD >/dev/null 2>&1' \
  'git rebase --abort 2>/dev/null' \
  'git cherry-pick --quit 2>/dev/null' \
  'git push --dry-run >/dev/null 2>&1' \
  'git commit --dry-run >/dev/null 2>&1' \
  'git fetch --all --prune >/dev/null 2>&1' \
; do
  if real_command "$case"; then
    allows "a read/probe/unwind: \`$case\`" "$case"
  fi
done

# `git merge-tree` is `revert-guard`'s engine and computes a tree without touching anything —
# a prefix match on `merge` would refuse the guard that reads what a branch would land.
if real_command 'git merge-tree HEAD HEAD >/dev/null 2>&1'; then
  allows "\`git merge-tree\` is a READ, and the verb match is exact" \
    "git merge-tree HEAD HEAD >/dev/null 2>&1"
fi

allows "\`gh pr view\` is a read"               "gh pr view 300 --json mergeable 2>/dev/null"
allows "\`make merge-selftest\` is not \`make merge\`" "make merge-selftest >/dev/null 2>&1"
allows "\`make claim-ids\` is not a merge"       "make claim-ids >/dev/null 2>&1"

echo ""
echo "  a write whose output survives is none of this guard's business"

allows "an ordinary commit"                     "git commit -m x"
allows "an ordinary commit from stdin"          "git commit -q -F -"
allows "an ordinary push"                       "git push origin HEAD"
allows "an ordinary \`make merge\`"              "make merge ARGS=\"300 --confirm\""
allows "\`2>&1 | tail -40\` — kept and read"     "git commit -m x 2>&1 | tail -40"
allows "a pipe into something that prints"      "git commit -m x | cat"
allows "\`2>&1\` alone discards nothing"         "git commit -m x 2>&1"
allows "a file the command DOES read back"      "git commit -m x > $tmp/o.log 2>&1 && cat $tmp/o.log"
allows "a quoted redirect is a STRING"          "git commit -m 'note: sent >/dev/null by mistake'"
allows "a quoted redirect in double quotes"     'git commit -m "fix >/dev/null 2>&1 in the guard"'

# A MULTI-LINE SCRIPT IS THE ORDINARY SHAPE OF A SESSION'S BASH CALL, and `shlex` treats a
# newline as plain whitespace — so without an explicit separator these three lines parse as ONE
# command whose stdout goes to /dev/null and whose argv happens to contain `git commit`. That is
# a false positive on a script that silences nothing, and it is the reason `tokenize` splits by
# line. This arm is what keeps that true.
allows "three lines, and the silence belongs to the \`echo\`" \
  "git status
git commit -m x
echo done >/dev/null"
allows "two lines, and the silence belongs to the \`rm\`" \
  "git commit -m x
rm -rf $tmp/junk >/dev/null 2>&1"

allows "nothing to do with git"                 "echo hi >/dev/null 2>&1"
allows "an npm install"                         "npm --prefix app ci >/dev/null 2>&1"
allows "the audit itself"                       "python3 scripts/docs-audit.py >/dev/null 2>&1"

echo ""
echo "  the two guards must not contradict each other"
# ADDED 2026-09-20 WITH `guard-shell.py`'s NINTH CLAUSE. That clause refuses a pipe into
# `tail` over a command that BLOCKS and narrates — `make merge ARGS="<n> --confirm"` is the
# one entry in its roster — and `make merge` is also in THIS guard's write roster. So the
# advice printed here for that verb may not be the command the neighbouring guard refuses one
# call later. A session handed a refusal whose remedy is itself refused concludes the guards
# are noise, and the next thing it reaches for is the hatch.

out="$(python3 "$GUARD" --explain 'make merge ARGS="437 --confirm" >/dev/null 2>&1' 2>&1)"
case "$out" in *"| tail"*) bad "the advice for a BLOCKING, narrating verb spells out a pipe the other guard refuses" ;;
  *) ok "the advice for \`make merge\` never spells a pipe into \`tail\`" ;; esac
case "$out" in *"waits for MINUTES"*) ok "…and says why: it waits and narrates, so a pipe hides the heartbeat" ;;
  *) bad "the advice does not say why a pipe is wrong for this verb" ;; esac

out="$(python3 "$GUARD" --explain 'git commit -m x >/dev/null 2>&1' 2>&1)"
case "$out" in *"| tail -40"*) ok "and a git write, which does NOT block, still gets the keep-it-and-read-it pipe" ;;
  *) bad "the ordinary advice was lost — a git write does not block and the pipe is right for it" ;; esac

echo ""
echo "  the escape hatch, in both of PKMNSCAN_KILL's two forms"

allows "inline in the command"  "PKMNSCAN_SILENT=off git commit -m x >/dev/null 2>&1"

out="$(printf '%s' "git commit -m x >/dev/null 2>&1" \
      | python3 -c 'import json,sys; print(json.dumps({"tool_input":{"command":sys.stdin.read()}}))' \
      | PKMNSCAN_SILENT=off python3 "$GUARD" --hook 2>&1)"
if [ $? -eq 0 ]; then ok "in the environment"; else bad "PKMNSCAN_SILENT=off in the environment did not disarm it"; fi

echo ""
echo "  a broken guard fails OPEN (reap.py's asymmetry, honoured)"

# EVERY ONE OF THESE MUST EXIT 0. `reap.py:hook`'s docstring is the contract: a guard that
# blocks every shell command when its own parser throws is a guard somebody switches off
# inside a day. There is no fail-CLOSED case here — a command this file cannot read is a
# command it has no opinion about, which is the same rule rather than an exception to it.
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
fails_open "an unbalanced quote"         '{"tool_input":{"command":"git commit -m '"'"'oops >/dev/null 2>&1"}}'

echo ""
printf '  %d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ] || exit 1
exit 0
