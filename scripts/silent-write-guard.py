#!/usr/bin/env python3
"""Refuse a git write whose own output is thrown away, so a refusal cannot be silent.

WHY THIS EXISTS. On 2026-09-12 a coordinator session reported work as landed that had not
landed, twice in one session, through one command shape:

    git commit -q -F - >/dev/null 2>&1 <<'EOF'
    ...
    EOF

The commit was REFUSED by `scripts/githooks/pre-commit`. The refusal went to `/dev/null`. The
session then read `git log --oneline -1`, saw the PREVIOUS commit — which is a real commit with
a real message, indistinguishable at a glance from the one it meant to make — and reported
"pushed". The push that followed said `Everything up-to-date`, which read as success too. Nine
instances of this class landed in about twenty-four hours.

BOTH HALVES OF THAT COMMAND ARE LOAD-BEARING, AND NEITHER IS ENOUGH ALONE:

  `2>/dev/null`   hides the hook's refusal. stderr is where git puts `error:`, `rejected`,
                  `hint:` and every byte a pre-commit hook prints.
  `>/dev/null`    hides `[branch 1a2b3c4] message`, which is the ONLY positive proof a commit
                  happened. Without it, "committed" and "nothing to commit, working tree
                  clean" — also stdout, also exit-code-bearing — are the same observation:
                  none.

So the predicate is not a list of redirection spellings. It is one invariant:

    A GIT WRITE MUST LEAVE A TRACE THE SESSION CAN READ. Discard either of its own standard
    streams and the reader can no longer tell "nothing is wrong" from "nothing is known yet",
    which is the failure class this repo has paid for more than any other (D16, D127, D133).

THIS IS `reap.py`'S SHAPE AND IT DELIBERATELY DIFFERS IN ONE WAY. That guard cannot decide
from the text alone — `pkill -f capture_server.py` is right on Monday and wrong on Tuesday —
so it RESOLVES the command's real targets by asking the system. This one is the opposite case
and it is the easier one: whether a stream reaches the session is a property of the string,
decidable with no process table and no network. The asymmetry from `reap.py:hook` is honoured
unchanged, because it is the whole reason a guard survives its first week:

    a broken GUARD fails open — any parse error, any bug here, any unreadable payload exits 0
    an unreadable TARGET fails closed — but there is no such case here, because a command this
    file cannot tokenize is a command it has no opinion about, which is fail-open by the same
    rule rather than by exception

FALSE POSITIVES ARE THE ONLY WAY THIS GUARD DIES. `git rev-parse -q --verify MERGE_HEAD
>/dev/null 2>&1` is a TEST whose exit code IS its answer; `git fetch origin -q 2>/dev/null`
runs constantly; `git merge --abort 2>/dev/null` discards an unwind that has nothing to
report. Every one of those passes, and `scripts/silent-write-selftest.sh` pins them as
passing rather than trusting this paragraph.

THE ESCAPE HATCH IS `PKMNSCAN_SILENT=off` AND IT IS PRINTED IN EVERY REFUSAL, per the house
rule `PKMNSCAN_MAIN=off` set, and honoured in both of `PKMNSCAN_KILL`'s two forms — the
environment, and inline in the command itself.

WHAT IT COSTS, MEASURED, because it runs on EVERY Bash call in the session: 35 ms, and flat —
35 ms on a command with no git word in it, 35 ms on a long unrelated script, 37 ms on a git
read, 35 ms on a refused write. That is interpreter startup and essentially nothing else,
which is what `read_command`'s early return is for. A guard whose cost showed up in ordinary
work would be a guard somebody switches off, the same way a false positive would.

    scripts/silent-write-guard.py --hook        the PreToolUse hook on Bash. Payload on stdin.
    scripts/silent-write-guard.py --explain CMD  the verdict for one command. Presses nothing.

D18: this writes nothing and signals nothing, so it could gate a commit — but it is a hook
rather than a check, and its SELF-TEST is what `make check` runs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import sys
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

WIDTH = 76

# ------------------------------------------------------------------ what a stream ends up as

INHERIT = "inherit"   # the session sees it
NULL = "null"         # /dev/null
CLOSED = "closed"     # `2>&-`
PIPE = "pipe"         # downstream in this pipeline; resolved against the pipeline's tail
FILE = "file"         # a path; discarded only if nothing in the same command reads it back

_DEV_NULL = ("/dev/null", "/dev/zero")

# Shell words that precede the real command and say nothing about it. `reap.py:_strip_prefixes`
# carries the same list for the same reason.
_PREFIXES = {"sudo", "env", "time", "nohup", "command", "exec", "builtin", "then", "do", "else",
             "!", "{", "}"}

_PIPE_OPS = {"|", "|&"}

# git's own global options, which sit BEFORE the subcommand. `git -C /x pull --ff-only` is the
# local half of a merge (CLAUDE.md spells it out), so a guard that read `-C` as the subcommand
# would miss the exact command the repo tells a session to type.
_GIT_GLOBAL_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
                     "--config-env", "--super-prefix"}
_GIT_GLOBAL_BARE = {"--no-pager", "-P", "--paginate", "--no-replace-objects", "--bare",
                    "--literal-pathspecs", "--no-optional-locks", "--glob-pathspecs",
                    "--noglob-pathspecs", "--icase-pathspecs", "--no-lazy-fetch"}


class Redirect(NamedTuple):
    kind: str                 # one of the constants above
    path: str = ""            # for FILE


class Stage(NamedTuple):
    """One simple command, with what became of its two output streams."""
    argv: List[str]
    fd1: Redirect
    fd2: Redirect
    text: str


class Silenced(NamedTuple):
    """A write whose output does not reach the session, and which stream went where."""
    verb: str                 # `git commit`, `make merge`, `gh pr merge`
    text: str                 # the stage as typed, for the refusal
    stdout: Optional[Redirect]
    stderr: Optional[Redirect]


class Verdict(NamedTuple):
    silenced: List[Silenced]
    note: str                 # why this file declined to have an opinion, when it did


# ------------------------------------------------------------------------------- the writes
#
# THE ROSTER IS THE ACTS THAT MAKE A SESSION SAY "LANDED", AND IT IS DELIBERATELY SHORT. Every
# verb added here is false-positive surface, and a guard with a false positive is a guard
# somebody switches off — which is why `git add`, `git tag`, `git branch -D`, `git reset`,
# `git checkout`, `git stash` and `git revert` are all absent despite every one of them
# writing. None of them produces a REPORT of landed work; a session does not say "pushed"
# because `git add` printed nothing. The failure this file exists for is a claim about the
# remote or about main, so the roster is the commands that can make one.
#
# `gh pr create` was considered and left out on the same rule: its stdout is the PR URL, which
# is the one thing the session actually wants, so nobody silences it, and no incident says
# otherwise. A verb goes in when something has gone wrong through it.


def _git_verb(argv: Sequence[str]) -> Tuple[str, List[str]]:
    """`git`'s subcommand and its arguments, with git's own global options stepped over.

    Returns `("", [])` when this is not a git call at all.
    """
    if not argv:
        return "", []
    head = argv[0]
    if head != "git" and not head.endswith("/git"):
        return "", []
    rest = list(argv[1:])
    while rest:
        word = rest[0]
        if word in _GIT_GLOBAL_VALUE:
            rest = rest[2:]
            continue
        if word in _GIT_GLOBAL_BARE or any(
                word.startswith(name + "=") for name in _GIT_GLOBAL_VALUE):
            rest = rest[1:]
            continue
        if word.startswith("-"):
            # An unknown global flag. Stepping over it is the fail-open reading: the worst
            # outcome is that this file finds no verb and says nothing.
            rest = rest[1:]
            continue
        break
    if not rest:
        return "", []
    return rest[0], list(rest[1:])


def _looks_like_refspec(token: str) -> bool:
    """`main:main` — a fetch that writes a LOCAL ref — as against a URL, which also has a colon.

    `git fetch origin main:main` is the documented local half of a merge in CLAUDE.md and it
    moves `refs/heads/main`, which `scripts/githooks/reference-transaction` refuses. Silenced,
    that refusal is invisible and main did not move. A bare `git fetch origin -q` writes only
    remote-tracking refs, reports nothing a session claims, and is run constantly — so the
    colon is what separates the two, and it has to survive an ssh URL to be worth anything.
    """
    if token.startswith("-") or ":" not in token:
        return False
    before = token.split(":", 1)[0]
    return "://" not in token and "@" not in before


def _write_verb(argv: Sequence[str]) -> str:
    """The name of the write this command performs, or `""` for everything else.

    UNWINDS AND DRY RUNS ARE NOT WRITES, and each exemption is one of the false positives that
    would have killed this guard. `git merge --abort` puts the tree back and has nothing to
    report; `git push --dry-run` presses nothing, so "nothing happened" is the truth whether
    the session reads the output or not.
    """
    argv = list(argv)
    if not argv:
        return ""
    head = argv[0]

    verb, rest = _git_verb(argv)
    if verb:
        flags = set(rest)
        if verb == "commit" and "--dry-run" not in flags:
            return "git commit"
        if verb == "push" and not flags & {"--dry-run", "-n"}:
            return "git push"
        if verb == "pull":
            return "git pull"
        if verb in ("merge", "rebase", "cherry-pick") and not flags & {"--abort", "--quit"}:
            return "git " + verb
        if verb == "fetch" and any(_looks_like_refspec(token) for token in rest):
            return "git fetch"
        return ""

    if head == "make" or head.endswith("/make"):
        # `merge` EXACTLY. `make merge-selftest` is a test of the wrapper and `make claim-ids`
        # is not a merge at all; a prefix match here would refuse a self-test for being
        # quiet, which is the kind of finding that teaches a session to reach for the hatch.
        goals = [word for word in argv[1:]
                 if not word.startswith("-") and not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word)]
        if "merge" in goals:
            return "make merge"
        return ""

    if (head == "gh" or head.endswith("/gh")) and argv[1:3] == ["pr", "merge"]:
        return "gh pr merge"
    return ""


# WHAT EACH STREAM CARRIES, so a refusal says what was lost rather than that something was.
_CARRIES = {
    "git commit": ("`[branch 1a2b3c4] message`, the only proof the commit happened — and "
                   "`nothing to commit, working tree clean`, which is the other outcome",
                   "every byte `scripts/githooks/pre-commit` prints, and git's own `error:`"),
    "git push": ("the `To github.com:...` block",
                 "`Everything up-to-date`, `! [rejected]`, and the pre-push hook's refusal — "
                 "git puts ALL of a push's progress on stderr"),
    "git pull": ("`Fast-forward` and the diffstat",
                 "`fatal: refusing to fetch into branch`, and `reference-transaction`'s "
                 "refusal of a local main move"),
    "git merge": ("`Merge made by` and the diffstat", "`CONFLICT`, and every `error:`"),
    "git rebase": ("the progress", "`CONFLICT`, and every `error:`"),
    "git cherry-pick": ("`[branch 1a2b3c4]`", "`CONFLICT`, and every `error:`"),
    "git fetch": ("nothing much",
                  "`reference-transaction`'s refusal of a local main move — which is what "
                  "`git fetch origin main:main` is for"),
    "make merge": ("the whole preview and receipt: the PR, the assertion that the merged "
                   "commit is on origin/main, and which local form it chose",
                   "the refusal, including a bare `make merge` with no PR named"),
    "gh pr merge": ("the merge receipt", "`not mergeable`, and every API error"),
}


# ------------------------------------------------------------------------------ the parsing

_HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_-]*)\1")


def strip_heredocs(command: str) -> str:
    """The command with every heredoc BODY removed, and every other byte kept.

    `reap.py:_segments` truncates at the first `<<` instead, and that is right for its
    question and wrong for this one. The incident command puts its redirections BEFORE the
    heredoc operator, so truncating would still have caught it — but the body of a commit
    heredoc is a COMMIT MESSAGE, and a message about this very guard contains the string
    `>/dev/null`. Reading a document as a command is how a guard fires on the one thing that
    cannot fail. Dropping only the body keeps both: the redirections on either side are still
    judged, and the prose is never read.

    An unterminated heredoc drops the remainder of the command. That is the fail-open
    direction — a write this file never sees is a write it never refuses — and it is the only
    honest reading of a string whose quoting does not close.
    """
    lines = command.split("\n")
    kept: List[str] = []
    pending: List[str] = []
    for line in lines:
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            continue                      # a body line, or its terminator; dropped either way
        kept.append(line)
        for match in _HEREDOC_RE.finditer(line):
            pending.append(match.group(2))
    return "\n".join(kept)


def _tokenize_line(line: str) -> Optional[List[str]]:
    """One LINE's shell words and redirection operators, with quoted text kept literal.

    `punctuation_chars=True` is the whole reason this file can be honest about `-m "a > b"`:
    shlex returns an unquoted `>` as its own operator token and a quoted one as an ordinary
    word, which is exactly the distinction the shell itself makes and exactly the one a
    regular expression over the raw string cannot make.

    `commenters` IS CLEARED. shlex treats `#` as a comment to end of input by default, and
    this file feeds it one line at a time precisely so a `#` cannot swallow the rest of a
    script — but a `#` inside an unquoted argument (`gh pr view '#300'` unquoted, a branch
    named `fix#3`) would still eat the redirections after it. Nothing here needs comment
    semantics: a comment can only remove a verb or a redirection, and both directions of
    that are a MISS, which is the safe one.

    Returns None when the line does not tokenize — an unbalanced quote, most often, which is
    exactly what one line of a multi-line quoted argument looks like — and the caller reads
    that as "no opinion about this line".
    """
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:
        return None


def tokenize(command: str) -> Tuple[List[str], int]:
    """The whole command's tokens, with a `;` marking every line boundary.

    LINES ARE TOKENIZED SEPARATELY AND SEPARATED EXPLICITLY, and that is not tidiness — it is
    the difference between a guard and a nuisance. `shlex.whitespace_split` treats a newline
    as ordinary whitespace, so

        git status
        git commit -m x
        echo done >/dev/null

    tokenizes as ONE simple command whose stdout goes to /dev/null and whose argv happens to
    contain `git commit`. That is a false positive on a three-line script that silences
    nothing, and a multi-line script is the ordinary shape of a session's Bash call. A `;`
    between lines is what the shell means by a newline, so that is what is inserted.

    Line continuations are joined first, because `git commit \\` + newline + `  -m x` is one
    command and splitting it would drop the redirections on the second half.

    Returns the tokens and the number of lines that could not be read at all.
    """
    text = strip_heredocs(command)
    text = re.sub(r"\\\n", " ", text)
    tokens: List[str] = []
    unreadable = 0
    for line in text.split("\n"):
        if not line.strip():
            continue
        words = _tokenize_line(line)
        if words is None:
            unreadable += 1
            words = []
        if tokens and words:
            tokens.append(";")
        tokens.extend(words)
    return tokens, unreadable


def _is_operator(token: str) -> bool:
    return bool(token) and all(char in "<>&|();" for char in token)


def _op_kind(token: str) -> str:
    """`pipe`, `list`, `redirect` — or `""` for an ordinary word.

    DERIVED FROM THE CHARACTERS RATHER THAN LISTED, because a fixed roster of operators is a
    roster somebody has to remember to extend: `;;`, `;&`, `;;&` and `|||` are all real shell
    tokens, and every one of them missing from a set would silently merge two commands into
    one stage — which is the false positive `tokenize` above exists to prevent.
    """
    if not _is_operator(token):
        return ""
    if token in _PIPE_OPS:
        return "pipe"
    if "<" in token or ">" in token:
        return "redirect"
    return "list"


def _parse_stage(tokens: Sequence[str]) -> Stage:
    """One simple command's argv, and where its stdout and stderr were pointed.

    THE FILE DESCRIPTORS ARE WALKED IN ORDER, BECAUSE THE SHELL DOES. `cmd >/dev/null 2>&1`
    discards both streams; `cmd 2>&1 >/dev/null` duplicates stderr onto the CURRENT stdout —
    still the session's — and only then sends stdout away, so the refusal survives and the
    proof does not. Both are refused here, so the ORDER does not change the verdict; it
    changes what the refusal is able to tell you, and a refusal that names the wrong stream
    is one a session argues with.
    """
    argv: List[str] = []
    fds: Dict[int, Redirect] = {1: Redirect(INHERIT), 2: Redirect(INHERIT)}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if not _is_operator(token):
            argv.append(token)
            continue

        # A LEADING FD NUMBER IS THE PREVIOUS WORD. shlex cannot preserve adjacency, so
        # `echo 2 > f` and `echo 2> f` tokenize alike; popping the digit reads the second.
        # The cost of being wrong is that a refusal names stderr where it meant stdout, never
        # that a write is or is not refused — both streams are refused either way.
        lhs = 1
        if argv and re.match(r"^\d$", argv[-1]) and token[0] in "<>":
            lhs = int(argv.pop())

        target = tokens[index] if index < len(tokens) else ""

        if token.startswith("&>"):            # bash: both streams, one operator
            index += 1
            where = Redirect(NULL) if target in _DEV_NULL else Redirect(FILE, target)
            fds[1] = where
            fds[2] = where
        elif ">&" in token or token == ">&":   # a dup: `2>&1`, `1>&2`, `2>&-`
            index += 1
            if target == "-":
                fds[lhs] = Redirect(CLOSED)
            elif re.match(r"^\d$", target):
                fds[lhs] = fds.get(int(target), Redirect(INHERIT))
            # `>&word` is bash's `&>word` spelling; treated as an ordinary write below.
            elif target:
                fds[1] = fds[2] = (
                    Redirect(NULL) if target in _DEV_NULL else Redirect(FILE, target))
        elif token.startswith(">"):            # `>`, `>>`, `>|`
            index += 1
            fds[lhs] = Redirect(NULL) if target in _DEV_NULL else Redirect(FILE, target)
        elif token.startswith("<"):            # input of any kind; consumed and ignored
            index += 1
        # anything else is punctuation this file has no reading for, and is ignored

    # THE COMMAND WITHOUT ITS REDIRECTIONS, which is what the refusal echoes. Re-joining the
    # raw tokens would print `git commit -q -F - > /dev/null 2 >& 1` — the operators spaced
    # out by the lexer and unrecognisable as the line that was typed. The redirections are
    # reported on their own lines instead, one per stream, which is the fact that matters.
    return Stage(argv, fds[1], fds[2], " ".join(argv))


def _pipelines(tokens: Sequence[str]) -> List[List[Tuple[List[str], str]]]:
    """The command as pipelines, each a list of (stage tokens, the op that FOLLOWS the stage).

    A pipeline is the unit because a stream's fate is the pipeline's, not the stage's:
    `git commit | cat` sends stdout somewhere the session still reads, and
    `git commit 2>&1 | cat >/dev/null` does not.
    """
    pipelines: List[List[Tuple[List[str], str]]] = []
    current: List[Tuple[List[str], str]] = []
    stage: List[str] = []
    for token in tokens:
        kind = _op_kind(token)
        if kind == "list":
            current.append((stage, ""))
            pipelines.append(current)
            current, stage = [], []
        elif kind == "pipe":
            current.append((stage, token))
            stage = []
        else:
            stage.append(token)
    current.append((stage, ""))
    pipelines.append(current)
    return [p for p in pipelines if any(words for words, _ in p)]


def _strip_prefixes(argv: Sequence[str]) -> List[str]:
    out = list(argv)
    while out and (out[0] in _PREFIXES
                   or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", out[0])):
        out.pop(0)
    return out


def read_command(command: str) -> Verdict:
    """Every write in this command whose own output the session will not see.

    THE DEFAULT IS "NO OPINION", and it returns as early as it can: this runs on every Bash
    call in the session, and the overwhelming majority of them mention none of these verbs.
    """
    if not any(word in command for word in ("git", "make", "gh")):
        return Verdict([], "")

    tokens, unreadable = tokenize(command)
    if not tokens:
        return Verdict([], "nothing in this command tokenizes, so this guard has no opinion")

    pipelines = _pipelines(tokens)
    stages: List[Tuple[Stage, str, Stage]] = []   # (stage, pipe-op after it, pipeline tail)
    every: List[Stage] = []
    for pipeline in pipelines:
        parsed = [(_parse_stage(words), op) for words, op in pipeline]
        tail = parsed[-1][0]
        for stage, op in parsed:
            stages.append((stage, op, tail))
            every.append(stage)

    def resolve(where: Redirect, piped: bool, tail: Stage) -> Redirect:
        """A stream's real fate, with a pipe followed to the end of its pipeline."""
        if where.kind != INHERIT:
            return where
        if not piped:
            return where
        if tail.fd1.kind in (NULL, CLOSED, FILE):
            return tail.fd1
        return Redirect(PIPE)

    def discarded(where: Redirect, mine: Stage) -> bool:
        if where.kind in (NULL, CLOSED):
            return True
        if where.kind != FILE:
            return False
        # A FILE IS A DISCARD ONLY IF THE SAME COMMAND NEVER READS IT BACK.
        # `git commit >/tmp/o 2>&1 && cat /tmp/o` is a session that WILL see the refusal, and
        # refusing it would be refusing the careful spelling of the very thing this guard is
        # asking for. The test is generous on purpose — the path appearing anywhere else in
        # the command counts, with no roster of reader commands to keep up to date — because
        # being too generous costs one unrefused write and being too strict costs the guard.
        for other in every:
            if other is not mine and where.path in other.argv:
                return False
        return True

    silenced: List[Silenced] = []
    for stage, op, tail in stages:
        verb = _write_verb(_strip_prefixes(stage.argv))
        if not verb:
            continue
        out = resolve(stage.fd1, op in _PIPE_OPS, tail)
        err = resolve(stage.fd2, op == "|&", tail)
        lost_out = out if discarded(out, stage) else None
        lost_err = err if discarded(err, stage) else None
        if lost_out or lost_err:
            silenced.append(Silenced(verb, stage.text, lost_out, lost_err))
    note = ""
    if unreadable and not silenced:
        note = ("{0} line(s) did not tokenize — an unbalanced quote, most likely a multi-line "
                "quoted argument — and this guard has no opinion about them".format(unreadable))
    return Verdict(silenced, note)


# ------------------------------------------------------------------------------ the refusal

def _where(where: Redirect) -> str:
    if where.kind == NULL:
        return "/dev/null"
    if where.kind == CLOSED:
        return "a closed descriptor"
    if where.kind == FILE:
        return "`{0}`, which nothing in this command reads back".format(where.path)
    return where.kind


def _short(text: str, width: int = 96) -> str:
    """A long command, elided in the MIDDLE. `reap.py:_short`'s argument, unchanged."""
    if len(text) <= width:
        return text
    head = (width - 3) // 3
    return text[:head] + "…" + text[-(width - 3 - head):]


def refusal(silenced: Sequence[Silenced]) -> str:
    lines = ["BLOCKED: this would perform a git write and throw away the only evidence of "
             "what it did."]
    for item in silenced:
        carries_out, carries_err = _CARRIES.get(item.verb, ("its output", "its errors"))
        lines.append("  {0} — {1}".format(item.verb, _short(item.text)))
        if item.stdout:
            lines.append("      stdout -> {0}".format(_where(item.stdout)))
            lines.append("        which carries {0}".format(carries_out))
        if item.stderr:
            lines.append("      stderr -> {0}".format(_where(item.stderr)))
            lines.append("        which carries {0}".format(carries_err))
    lines.append("")
    lines.append("  A write whose output is discarded leaves you unable to tell `nothing is "
                 "wrong` from")
    lines.append("  `nothing is known yet`. On 2026-09-12 that difference was a pre-commit "
                 "refusal sent")
    lines.append("  to /dev/null, a stale `git log --oneline -1` read as the new commit, and "
                 "\"pushed\"")
    lines.append("  reported twice for work that was never committed.")
    lines.append("")
    lines.append("  Run it and READ the output. If it is too long, keep it and read it — "
                 "never drop it:")
    lines.append("      <the command> 2>&1 | tail -40        # a git write does not block, "
                 "so this is safe")
    lines.append("  and if you truly want only the outcome, ask for the outcome rather than "
                 "hiding it:")
    lines.append("      git commit -F - && git log --oneline -1")
    lines.append("")
    lines.append("  PKMNSCAN_SILENT=off runs the command anyway.")
    return "\n".join(lines)


def hook(payload: dict) -> int:
    """The PreToolUse hook on Bash. Exit 2 blocks the call and hands stderr to the session.

    IT FAILS OPEN ON ITS OWN BUGS. `reap.py:hook`'s docstring is the contract and it is not
    negotiable here either: a guard that blocks every shell command when its parser throws is
    a guard somebody switches off inside a day, and a switched-off guard protects nothing.
    """
    # `or {}` RATHER THAN A DEFAULT: a payload carrying `"tool_input": null` makes `.get`'s
    # default unreachable, and the floor at the bottom of this file would catch the
    # AttributeError and exit 0 anyway. That floor is meant to be a last resort, not a
    # routine path — a guard whose ordinary operation runs through its own crash handler is
    # one nobody can reason about.
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0
    command = str(tool_input.get("command") or "")
    if not command:
        return 0
    if os.environ.get("PKMNSCAN_SILENT") == "off" or "PKMNSCAN_SILENT=off" in command:
        return 0
    verdict = read_command(command)
    if not verdict.silenced:
        return 0
    print(refusal(verdict.silenced), file=sys.stderr)
    return 2


def explain(command: str) -> int:
    verdict = read_command(command)
    if verdict.note:
        print("no opinion: {0}".format(verdict.note))
        return 0
    if not verdict.silenced:
        print("ALLOWED  {0}".format(_short(command.replace("\n", " "))))
        return 0
    print(refusal(verdict.silenced))
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="silent-write-guard",
        description="Refuse a git write whose own output is discarded.",
    )
    parser.add_argument("--hook", action="store_true",
                        help="run as a PreToolUse hook on Bash; reads the payload on stdin")
    parser.add_argument("--explain", metavar="CMD", default="",
                        help="the verdict for one command, and why")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    if args.hook:
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except ValueError:
            return 0
        if not isinstance(payload, dict):
            return 0
        return hook(payload)
    if args.explain:
        return explain(args.explain)
    build_parser().print_help()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001 — the fail-open floor; see the module docstring
        # A HOOK THAT CRASHES MUST NOT BLOCK A SHELL. This is the last line of the asymmetry
        # `reap.py` records: a broken guard exits 0 and protects nothing, which is strictly
        # better than a broken guard that stops the session from working and gets removed.
        if "--hook" in sys.argv:
            sys.exit(0)
        raise
