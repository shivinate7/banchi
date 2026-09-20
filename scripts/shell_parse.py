#!/usr/bin/env python3
"""One reader for a shell command, because this repo now has two guards that need one.

WHY THIS IS A MODULE AND NOT A SECOND COPY. `scripts/silent-write-guard.py` landed on
2026-09-12 with a tokenizer that took four real defects to get right, and every one of them
is a defect the NEXT guard would have shipped again:

  `shlex.whitespace_split` TREATS A NEWLINE AS WHITESPACE, so a three-line script tokenizes
  as ONE simple command — a `>/dev/null` belonging to the `echo` on line three was attributed
  to the `git commit` on line two. A multi-line script is the ordinary shape of a session's
  Bash call, so that is a false positive on almost everything.

  A REGULAR EXPRESSION CANNOT TELL AN OPERATOR FROM A STRING. `git commit -m "sent >/dev/null
  by mistake"` contains the bytes and performs no redirection; `shlex` with
  `punctuation_chars=True` returns an unquoted `>` as its own token and a quoted one as an
  ordinary word, which is exactly the distinction the shell itself makes.

  A HEREDOC BODY IS A DOCUMENT. The commit message announcing a guard quotes the command the
  guard refuses, so a reader that treats a body line as a command fires on the one thing that
  cannot fail. Bodies are cut and everything else is kept, because a write AFTER the
  terminator is still a write.

  `#` IS NOT ALWAYS A COMMENT. `shlex` eats to end of input on one, so `commenters` is
  cleared and lines are fed one at a time.

CLAUDE.md's hard rule is to ask whether the primitive already exists before designing around
its absence. It did, inside a file that could not be imported, so it moved here — with its
arguments, which are the part worth keeping. `silent-write-guard.py` and `guard-shell.py` are
the two readers today and they see one parse of one command.

WHAT THIS FILE DOES NOT DO: decide anything. It has no roster of verbs, no notion of a write,
and no opinion about any command. Both guards keep their own predicate, because their
predicates are genuinely different — one is decidable from the string (`silent-write-guard`)
and one must RESOLVE its targets against the filesystem and git (`guard-shell`, and
`reap.py` before it). Sharing the parse is not sharing the judgement.

EVERY FUNCTION HERE FAILS SOFT. A line that does not tokenize is reported as unreadable and
dropped; an unterminated heredoc drops the remainder. Both directions lose a command rather
than inventing one, which is the fail-open half of the asymmetry `scripts/reap.py:hook`
states: a broken guard must not block a shell.
"""

from __future__ import annotations

import re
import shlex
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

# ------------------------------------------------------------------ what a stream ends up as

INHERIT = "inherit"   # the session sees it
NULL = "null"         # /dev/null
CLOSED = "closed"     # `2>&-`
PIPE = "pipe"         # downstream in this pipeline; resolved against the pipeline's tail
FILE = "file"         # a path

DEV_NULL = ("/dev/null", "/dev/zero")

# ------------------------------------------------ lifted from the parent's hooks/guard.py
#
# THREE THINGS BELOW ARE COPIED FROM `~/Developer/claude-settings/hooks/guard.py` AND NOT
# RE-DERIVED: `split_segments`, `resolve_command` with its three constants, and
# `strip_heredoc_bodies`. The parent's decision `a-gates-allow-list-is-the-constant.md`
# (pattern 1) records why: its own `lint/report_gate.py` had this file's 2026-09-19 defect, a
# hand-rolled piece of the resolver fixed it, and the hand-rolled piece then produced a false
# NEGATIVE on `git -C <dir> commit`. Importing the whole resolver is what closed it. When one
# of these needs to change, change it THERE first and copy the result back.

# A leading `VAR=value` assignment, which is not a segment's command.
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# A wrapper that runs another program in its place, so the CALLED program is a segment's real
# command word, not the wrapper. `xargs pkill foo` runs pkill, so `xargs` unwraps the same as
# the rest: the token after it, once its own flags are skipped, is what actually runs.
# `exec` and `builtin` are this repo's additions — `reap.py:_strip_prefixes` carried them.
COMMAND_WRAPPERS = {"sudo", "env", "command", "nohup", "nice", "time", "doas", "xargs",
                    "exec", "builtin"}

# A leading shell keyword that opens or joins a control-flow block, never a command itself.
# MEASURED in the parent against its live guard: `while ! pgrep -f server; do sleep 1; done`
# allowed the sleep, because the segment `do sleep 1` resolved to `do` as its command word.
# `!` and `}` are this repo's additions, for the same reason as above.
LOOP_KEYWORDS = {"do", "then", "else", "elif", "while", "until", "if", "{", "(", "!", "}"}

# The old roster, kept as a name for any reader that still spells it; derived, never edited.
PREFIXES = COMMAND_WRAPPERS | LOOP_KEYWORDS

PIPE_OPS = {"|", "|&"}

# git's own global options, which sit BEFORE the subcommand. `git -C /x pull --ff-only` is the
# local half of a merge (CLAUDE.md spells it out), so a guard that read `-C` as the subcommand
# would miss the exact command the repo tells a session to type.
GIT_GLOBAL_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path",
                    "--config-env", "--super-prefix"}
GIT_GLOBAL_BARE = {"--no-pager", "-P", "--paginate", "--no-replace-objects", "--bare",
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


class Placed(NamedTuple):
    """A stage, the pipe operator that FOLLOWS it, and the tail of its pipeline.

    A stream's fate is the pipeline's and not the stage's: `git commit | cat` sends stdout
    somewhere the session still reads, and `git commit 2>&1 | cat >/dev/null` does not. So a
    caller that asks about streams needs all three, and one that only wants argv ignores two.
    """
    stage: Stage
    pipe_op: str
    tail: Stage


class Reading(NamedTuple):
    """One command, parsed. `unreadable` is lines this file declined to read at all."""
    placed: List[Placed]
    every: List[Stage]
    unreadable: int


# ------------------------------------------------------------------------------ the parsing

HEREDOC_HEADER = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
INTERPRETER_HEREDOC = re.compile(
    r"\b(bash|sh|zsh|dash|ksh|python3?|perl|ruby|node)\b[^\n]*<<"
)


def strip_heredoc_bodies(cmd: str) -> str:
    """Drop the body of every heredoc, and keep every header line.

    LIFTED from the parent's `hooks/guard.py:strip_heredoc_bodies`, and it replaces this
    file's own `strip_heredocs` for one reason the old one lacked: a heredoc fed to an
    INTERPRETER can be executed, so its body stays under inspection. `bash <<'EOF'` with an
    `echo x > <other checkout>/file` inside it was a write this guard could not see, measured
    2026-09-19 against the live guard: ALLOWED.

    The parent's argument for the rest, unchanged: a heredoc body is DATA being written, not a
    command being run. A commit message that DISCUSSES a refused command must not trip the
    guard. The header line is kept, so a redirect in the header still counts as a write:
    `cat <<'EOF' > .claude/settings.json` writes the settings file.

    `reap.py:_segments` truncates at the first `<<` instead, and that is right for its
    question and wrong for this one: a write AFTER the terminator is still a write.
    """
    if INTERPRETER_HEREDOC.search(cmd):
        return cmd  # the body may be executed, so keep it under inspection
    lines = cmd.split("\n")
    kept = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        match = HEREDOC_HEADER.search(line)
        index += 1
        if not match:
            continue
        delimiter = match.group(2)
        while index < len(lines) and lines[index].strip() != delimiter:
            index += 1
        if index < len(lines):
            index += 1  # drop the closing delimiter line too
    return "\n".join(kept)


strip_heredocs = strip_heredoc_bodies    # the name this file shipped under, 2026-09-12


def split_segments(cmd: str, delimiters: Sequence[str] = (";", "|", "&&", "\n")) -> List[str]:
    """Split into shell segments on unquoted `;`, `|`, `||`, `&&`, and newline.

    LIFTED from the parent's `hooks/guard.py:split_segments`. Quoted text, single or double,
    is copied whole into the current segment, so a delimiter inside a quote never starts a
    new one. An unterminated quote runs to the end of the string, which keeps the remainder
    inside it rather than guessing where it would have closed.

    THE ONE ADDITION IS `delimiters`. `tokenize` below passes `("\n",)` and nothing else:
    inside a line, `shlex` with `punctuation_chars` already returns `|`, `;` and `&&` as
    operator tokens, and `silent-write-guard.py` needs the pipe kept to say where a stream
    ended up. What this file could not do before today was carry QUOTE STATE ACROSS A
    NEWLINE — a multi-line `node -e '…'` was fed to shlex one line at a time, and the middle
    line of the script, quoted as far as the shell is concerned, tokenized as a command with
    a `>` in it. The parent's loop is what carries that state; the set it cuts on is the
    caller's.

    THE ONE AMENDMENT IS THE COMMENT RULE, and it was measured before it was written: the
    parent's loop reads the `'` in `# The merge driver's shape` as opening a quote that runs
    to the end of the file, and `guard-shell-selftest.sh`'s runaway-driver fixture — a script
    whose second line is exactly that comment — went from refused to ALLOWED the moment this
    function replaced the per-line reader. A `#` that is unquoted and starts a word is a
    comment to the end of its line, which is the shell's own rule; `fix#3` and `'#300'` are
    not comments under it either. The parent has the same blind spot and is told so in this
    change's report, because the copy is not the place to fix it first.
    """
    segments = []
    current = []
    quote = ""
    index = 0
    length = len(cmd)
    while index < length:
        char = cmd[index]
        if quote:
            current.append(char)
            if char == quote:
                quote = ""
            index += 1
            continue
        if char == "#" and (index == 0 or cmd[index - 1] in " \t\n;|&("):
            while index < length and cmd[index] != "\n":
                index += 1
            continue
        if char in ("'", '"'):
            quote = char
            current.append(char)
            index += 1
            continue
        if char == "&" and cmd[index:index + 2] == "&&" and "&&" in delimiters:
            segments.append("".join(current))
            current = []
            index += 2
            continue
        if char == "|" and "|" in delimiters:
            index += 2 if cmd[index:index + 2] == "||" else 1
            segments.append("".join(current))
            current = []
            continue
        if char in (";", "\n") and char in delimiters:
            segments.append("".join(current))
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    segments.append("".join(current))
    return segments


def resolve_command(tokens: Sequence[str]) -> Optional[int]:
    """Return the index of the command word in a tokenized segment, or None when it names none.

    LIFTED from the parent's `hooks/guard.py:resolve_command`. Skips leading `VAR=value`
    assignments and leading loop keywords, then unwraps command wrappers along with each
    wrapper's own flags and any assignment it takes ahead of the program name, so the index
    returned is the program that actually runs, never the keyword or the wrapper carrying it
    there. `strip_prefixes` used to stop at a wrapper's FLAG: `sudo -u root tee <path>`
    resolved to `-u`, and every clause reading a command word was blind to it.
    """
    index = 0
    end = len(tokens)
    while index < end and (ASSIGNMENT.match(tokens[index]) or tokens[index] in LOOP_KEYWORDS):
        index += 1
    while index < end and _basename(tokens[index]) in COMMAND_WRAPPERS:
        index += 1
        while index < end and tokens[index].startswith("-"):
            index += 1
        while index < end and ASSIGNMENT.match(tokens[index]):
            index += 1
    return index if index < end else None


def _basename(token: str) -> str:
    return token.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()


def tokenize_line(line: str) -> Optional[List[str]]:
    """One LINE's shell words and redirection operators, with quoted text kept literal.

    `punctuation_chars=True` is the whole reason a caller can be honest about `-m "a > b"`:
    shlex returns an unquoted `>` as its own operator token and a quoted one as an ordinary
    word, which is exactly the distinction the shell itself makes and exactly the one a
    regular expression over the raw string cannot make.

    `commenters` IS CLEARED. shlex treats `#` as a comment to end of input by default, and
    this file feeds it one line at a time precisely so a `#` cannot swallow the rest of a
    script — but a `#` inside an unquoted argument (`gh pr view '#300'` unquoted, a branch
    named `fix#3`) would still eat the redirections after it. Nothing here needs comment
    semantics: a comment can only remove a word or a redirection, and both directions of
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
    text = strip_heredoc_bodies(command)
    text = re.sub(r"\\\n", " ", text)
    tokens: List[str] = []
    unreadable = 0
    # A "LINE" IS AN UNQUOTED NEWLINE'S WORTH, not a byte-level one. `split_segments` carries
    # quote state across the newline, so the body of a multi-line `node -e '…'` stays one
    # word and nothing inside it is ever a redirection. Measured 2026-09-19: fed line by line,
    # `const hits=s.filter(i=>/[·•]/.test(…))` tokenized as a write to `/[·•]/.test`.
    for line in split_segments(text, ("\n",)):
        if not line.strip():
            continue
        words = tokenize_line(line)
        if words is None:
            unreadable += 1
            words = []
        if tokens and words:
            tokens.append(";")
        tokens.extend(words)
    return tokens, unreadable


def is_operator(token: str) -> bool:
    return bool(token) and all(char in "<>&|();" for char in token)


def op_kind(token: str) -> str:
    """`pipe`, `list`, `redirect` — or `""` for an ordinary word.

    DERIVED FROM THE CHARACTERS RATHER THAN LISTED, because a fixed roster of operators is a
    roster somebody has to remember to extend: `;;`, `;&`, `;;&` and `|||` are all real shell
    tokens, and every one of them missing from a set would silently merge two commands into
    one stage — which is the false positive `tokenize` above exists to prevent.
    """
    if not is_operator(token):
        return ""
    if token in PIPE_OPS:
        return "pipe"
    if "<" in token or ">" in token:
        return "redirect"
    return "list"


def parse_stage(tokens: Sequence[str]) -> Stage:
    """One simple command's argv, and where its stdout and stderr were pointed.

    THE FILE DESCRIPTORS ARE WALKED IN ORDER, BECAUSE THE SHELL DOES. `cmd >/dev/null 2>&1`
    discards both streams; `cmd 2>&1 >/dev/null` duplicates stderr onto the CURRENT stdout —
    still the session's — and only then sends stdout away. A caller that read the two
    spellings alike would name the wrong stream in its refusal, and a refusal that names the
    wrong stream is one a session argues with.
    """
    argv: List[str] = []
    fds: Dict[int, Redirect] = {1: Redirect(INHERIT), 2: Redirect(INHERIT)}
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if not is_operator(token):
            argv.append(token)
            continue

        # A LEADING FD NUMBER IS THE PREVIOUS WORD. shlex cannot preserve adjacency, so
        # `echo 2 > f` and `echo 2> f` tokenize alike; popping the digit reads the second.
        lhs = 1
        if argv and re.match(r"^\d$", argv[-1]) and token[0] in "<>":
            lhs = int(argv.pop())

        target = tokens[index] if index < len(tokens) else ""

        if token.startswith("&>"):            # bash: both streams, one operator
            index += 1
            where = Redirect(NULL) if target in DEV_NULL else Redirect(FILE, target)
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
                    Redirect(NULL) if target in DEV_NULL else Redirect(FILE, target))
        elif token.startswith(">"):            # `>`, `>>`, `>|`
            index += 1
            fds[lhs] = Redirect(NULL) if target in DEV_NULL else Redirect(FILE, target)
        elif token.startswith("<"):            # input of any kind; consumed and ignored
            index += 1
        # anything else is punctuation this file has no reading for, and is ignored

    # THE COMMAND WITHOUT ITS REDIRECTIONS, which is what a refusal echoes. Re-joining the raw
    # tokens would print `git commit -q -F - > /dev/null 2 >& 1` — the operators spaced out by
    # the lexer and unrecognisable as the line that was typed.
    return Stage(argv, fds[1], fds[2], " ".join(argv))


def pipelines(tokens: Sequence[str]) -> List[List[Tuple[List[str], str]]]:
    """The command as pipelines, each a list of (stage tokens, the op that FOLLOWS the stage)."""
    found: List[List[Tuple[List[str], str]]] = []
    current: List[Tuple[List[str], str]] = []
    stage: List[str] = []
    for token in tokens:
        kind = op_kind(token)
        if kind == "list":
            current.append((stage, ""))
            found.append(current)
            current, stage = [], []
        elif kind == "pipe":
            current.append((stage, token))
            stage = []
        else:
            stage.append(token)
    current.append((stage, ""))
    found.append(current)
    return [p for p in found if any(words for words, _ in p)]


def strip_prefixes(argv: Sequence[str]) -> List[str]:
    """argv from its real command word: wrappers, their flags, assignments and loop
    keywords stepped over, by the lifted `resolve_command`."""
    index = resolve_command(argv)
    return [] if index is None else list(argv[index:])


def read(command: str) -> Reading:
    """One command, parsed into stages with their pipelines resolved.

    THE ONE ENTRY POINT BOTH GUARDS CALL, so a command is tokenized once and read the same way
    by each of them. A caller wanting only argv reads `.placed[i].stage.argv`; one wanting to
    know where a stream ended up needs the pipe operator and the tail as well, which is why
    `Placed` carries all three.
    """
    tokens, unreadable = tokenize(command)
    placed: List[Placed] = []
    every: List[Stage] = []
    for pipeline in pipelines(tokens):
        parsed = [(parse_stage(words), op) for words, op in pipeline]
        tail = parsed[-1][0]
        for stage, op in parsed:
            placed.append(Placed(stage, op, tail))
            every.append(stage)
    return Reading(placed, every, unreadable)


def git_verb(argv: Sequence[str]) -> Tuple[str, List[str]]:
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
        if word in GIT_GLOBAL_VALUE:
            rest = rest[2:]
            continue
        if word in GIT_GLOBAL_BARE or any(
                word.startswith(name + "=") for name in GIT_GLOBAL_VALUE):
            rest = rest[1:]
            continue
        if word.startswith("-"):
            # An unknown global flag. Stepping over it is the fail-open reading: the worst
            # outcome is that a caller finds no verb and says nothing.
            rest = rest[1:]
            continue
        break
    if not rest:
        return "", []
    return rest[0], list(rest[1:])


def git_cwd(argv: Sequence[str]) -> str:
    """The directory a `git -C <dir>` call would run in, or `""` for this one.

    THE RESOLVING GUARD NEEDS THIS AND THE STRING-ONLY ONE DOES NOT. `git -C /other/tree
    checkout file.py` asks about a file in another checkout, and running `git status` for it
    here would answer about a path that may not even exist — an answer about the wrong tree is
    worse than no answer, because it is the shape that reads as certainty.
    """
    if not argv:
        return ""
    head = argv[0]
    if head != "git" and not head.endswith("/git"):
        return ""
    rest = list(argv[1:])
    while rest:
        word = rest[0]
        if word == "-C" and len(rest) > 1:
            return rest[1]
        if word.startswith("-C") and len(word) > 2:
            return word[2:]
        if word in GIT_GLOBAL_VALUE:
            rest = rest[2:]
            continue
        if word in GIT_GLOBAL_BARE or any(
                word.startswith(name + "=") for name in GIT_GLOBAL_VALUE):
            rest = rest[1:]
            continue
        if word.startswith("-"):
            rest = rest[1:]
            continue
        break
    return ""


def short(text: str, width: int = 96) -> str:
    """A long command, elided in the MIDDLE. `reap.py:_short`'s argument, unchanged."""
    if len(text) <= width:
        return text
    head = (width - 3) // 3
    return text[:head] + "…" + text[-(width - 3 - head):]
