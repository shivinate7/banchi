"""American spelling and shell substitution."""

from __future__ import annotations

import io
import keyword
import multiprocessing
import re
import tokenize
from typing import Dict, List, Optional, Tuple

from .core import Finding, MECHANICAL, ROOT, Report, _walk, read, rel

# ---------------------------------------------------------- identifier spelling (D60)
#
# ONE SPELLING FOR EVERY NAME A SESSION CAN SEARCH FOR. The owner ruled on 2026-09-11 (D60,
# amended) that identifiers are spelled American across the whole repository, and that prose
# and comments are NOT governed here. The reasoning is the difference between reading and
# searching: a model reads `artefact` and `artifact` as one word, and a grep does not. Measured
# before the ruling: 119 British identifiers in 24 files, beside 951 `fulfill`, 868 `catalog`
# and 1,405 `color` — so `_artefacts` was unfindable by the word every other file used, and
# `Fulfillment.tsx` sat over a table spelled `fulfilment`. Comments and docstrings held 869
# British words in 169 files and were left alone: a rewrite there is churn against five open
# branches for no search a session runs.
#
# IDENTIFIERS ONLY, IN CODE, BY CONSTRUCTION. Comments, docstrings, string and template
# literals, regex literals and JSX text are blanked before a token is read, byte for byte so
# line numbers survive. A British word that reaches this row over a code file is therefore a
# NAME — a function, a variable, a class, a key spelled as an attribute, a CSS class or custom
# property, a shell variable.
#
# MARKDOWN PROSE IS READ TOO, AS A SHRINKING OFFENDER LIST (owner's ruling, test-audit plan,
# 2026-09-27: "Shrinking offender list now"). Extending `spelling_findings` to `.md` and
# running it over the tracked tree found 727 British-spelling words in 226 files — catalogue
# (80), judgement (67), organised, analysed and the rest of the -ise/-our/-re family — far
# past "fix it only if fewer than about 30", so it is not a blocking rule over every word:
# `scripts/markdown-spelling-allow.json` lists today's words, one entry per occurrence, file
# by file, on D280's pattern. It fails on a British word the list does not name, a stale
# entry, and growth over the merge-base, so a new file starts clean and new prose is American
# from the moment it is written. Fenced code, an inline code span and a single-asterisk
# italic span are exempt — an owner's quote, `*"..."*` (D007's own style) or in backticks, is
# never this row's to rewrite. `docs/gates/` is excluded outright: its records are evidence of
# a real run and are "never rewritten to match a later tree" (CLAUDE.md). See D280's
# 2026-09-27 amendment for the count and the list this ruling names.
#
# THE -ISE LIST IS CLOSED, DELIBERATELY. An open `\w+ise` pattern flags `raise`, `Promise`,
# `otherwise`, `pairwise` and `exercise`, every one of them -ise in American English too; a
# closed stem list can miss a British verb it has not met, and a miss is the cheaper error on
# a row that blocks a commit. The stems are what this tree showed plus the common programming
# verbs. Add one when a name shows it.
#
# THE ALLOW-LIST IS BY NAME AND CARRIES ITS REASON, and each entry is a name the owner ruled
# out of scope on 2026-09-11 because a rename there is a migration and not a spelling.
#
# STAGED-SCOPED, 2026-09-27 (test-audit plan S2). `--staged` reads only the files THIS COMMIT
# TOUCHES (`_STAGED_PATHS`, not `core._INDEX_PATHS`'s whole tracked tree) — a file this commit does
# not touch cannot grow a new British word. It reads the WHOLE tree in staged mode too when
# `scripts/docs-audit.py` itself is staged, because a broadened fragment table or a new
# allow-list entry can make an untouched file's existing word newly non-compliant, or newly
# excused. A full run (`python3 scripts/docs-audit.py`, no `--staged`) always reads everything,
# which is what CI runs.
SPELLING_SUFFIXES = (".py", ".ts", ".tsx", ".mjs", ".sh", ".css")

MARKDOWN_SPELLING_ALLOW = ROOT / "scripts" / "markdown-spelling-allow.json"
MARKDOWN_SPELLING_RULE = "SPELLING"
MARKDOWN_SPELLING_EXCLUDE = "docs/gates/"

# Lower-cased identifier fragment -> why it is allowed. Matched as a substring of the whole
# lower-cased name, so `is_catalogued`, `NotCatalogued` and `_parse_fulfilment` are covered
# by the stem they carry rather than listed one by one — the owner's ruling was that the
# relatives of a wire name stay with it so one file is never split between spellings.
SPELLING_ALLOWED: Dict[str, str] = {
    "catalogued": (
        "the game registry key in pipeline/games.py, a field on the wire in GET /games "
        "(app/src/types.ts declares it) and the stem of the `not_catalogued` reason code; "
        "a rename is a wire change and a reason-code migration, not a spelling (D60, "
        "2026-09-11)"
    ),
    "fulfilment": (
        "a table in inventory/store.sqlite (store/db.py) and the ledger payload key the "
        "legacy-JSON migration reads (store/orders.py); a rename is a store migration under "
        "D88, not a spelling (D60, 2026-09-11)"
    ),
    "labelledby": "`aria-labelledby` is the DOM's own attribute name, spelled by the platform",
}

_ISE_STEMS = (
    "alphabet|anonym|apolog|author|canonical|capital|categor|central|character|civil|colon|"
    "critic|custom|digit|ellips|emphas|energ|equal|external|famil|final|formal|general|global|"
    "harmon|human|hypothes|ideal|immun|initial|internal|item|legal|linear|local|magnet|"
    "material|maxim|mechan|memo|memor|minim|mobil|modern|modular|monet|national|neutral|"
    "normal|optim|organ|oxid|parallel|parameter|parenthes|personal|polar|popular|priorit|"
    "public|quant|random|raster|rational|real|recogn|regular|sanit|scrutin|serial|social|"
    "special|stabil|standard|steril|summar|symbol|synchron|synthes|token|trivial|urban|util|"
    "vapor|vector|verbal|virtual|visual|vocal"
)
_ISE_PREFIX = r"(?:un|re|de|dis|non|pre|auto|mis|over|under)?"

# (pattern over ONE lower-cased word of a name, replacement). The replacement is the
# American form of the matched fragment, so the message can name it.
_BRITISH_FRAGMENTS: Tuple[Tuple["re.Pattern[str]", str], ...] = tuple(
    (re.compile(pattern), american)
    for pattern, american in (
        (r"artefact", "artifact"),
        (r"colour", "color"),
        (r"behaviour", "behavior"),
        (r"honour", "honor"),
        (r"centre", "center"),
        (r"licence", "license"),
        (r"grey", "gray"),
        (r"cataloguing", "cataloging"),
        (r"catalogue", "catalog"),
        (r"favour", "favor"),
        (r"neighbour", "neighbor"),
        (r"judgement", "judgment"),
        (r"defence", "defense"),
        (r"offence", "offense"),
        (r"acknowledgement", "acknowledgment"),
        (r"programme(?![rd])", "program"),
        (r"fulfil(?!l)", "fulfill"),
        (r"cancell(?!ation)", "cancel"),
        (r"aluminium", "aluminum"),
        (r"analys(e|ed|es|ing|er|ers)$", r"analyz\1"),
        (r"paralys(e|ed|es|ing)$", r"paralyz\1"),
        (r"(label|model|travel|signal|total|level|channel|fuel|dial|pencil|marshal)l(ed|ing)$", r"\1\2"),
        (r"^(" + _ISE_PREFIX + r"(?:" + _ISE_STEMS + r"))is(e|es|ed|er|ers|ing|ation|ations|able)$", r"\1iz\2"),
    )
)

_NAME_WORDS = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+")
_JS_REGEX_WORDS = {"return", "typeof", "case", "do", "else", "in", "instanceof", "new", "throw", "void", "delete", "yield", "await"}


def british_spelling(name: str) -> Optional[Tuple[str, str]]:
    """(british word, american word) for the first British fragment in an identifier, or None.

    The name is split into words at `_`, `-`, `$`, digits and camelCase boundaries, so
    `fetchCatalogueRows` and `NEIGHBORLY` are both read, and each fragment pattern sees one
    lower-cased word at a time — which is what lets `$` anchors mean the end of a WORD.
    """
    lowered = name.lower()
    if any(allowed in lowered for allowed in SPELLING_ALLOWED):
        return None
    for word in _NAME_WORDS.findall(name):
        low = word.lower()
        for pattern, american in _BRITISH_FRAGMENTS:
            if pattern.search(low):
                return low, pattern.sub(american, low, count=1)
    return None


def _blank(text: str) -> str:
    """Every character but a newline replaced by a space: positions and lines survive."""
    return re.sub(r"[^\n]", " ", text)


def _js_code_only(text: str) -> str:
    """A .ts/.tsx/.mjs file with every comment, string, template and regex literal blanked.

    A real lexer rather than TS_COMMENT's regex, because a `//` inside a string is not a
    comment and a quote inside a regex is not a string — and either misreading would expose
    part of a literal as code, which is the one error this row must not make. Blanking is
    byte-for-byte so a finding's line number is the file's. A template literal's `${...}`
    expressions are code and are kept, recursively, so `${humanise(x)}` is read.

    The regex-or-division question is answered the way every JS lexer answers it: by the
    token before the slash. `<` is deliberately NOT in the set — a closing JSX tag `</p>`
    read as a regex swallowed the rest of the line, which is how the first draft of this
    reader lost every closing tag in `app/src/Fulfillment.tsx` and read its text as names.
    Nor is `}`: `size={16} />` is a self-closing tag, and the draft read `/>}` as a regex
    and never saw the element close.
    """
    out: List[str] = []
    i, n = 0, len(text)
    last = ""  # last significant character, for the regex-or-division question
    last_at = -1
    last_word = ""
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(_blank(text[i:j]))
            i = j
            continue
        if c == "/" and nxt == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(_blank(text[i:j]))
            i = j
            continue
        if c in "'\"":
            j = i + 1
            while j < n and text[j] not in (c, "\n"):
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(_blank(text[i:j]))
            i, last, last_at = j, c, j - 1
            continue
        if c == "`":
            j, spans = _template_end(text, i)
            piece = list(_blank(text[i:j]))
            for a, b in spans:  # the `${...}` expressions, lexed on their own
                piece[a - i:b - i] = list(_js_code_only(text[a:b]))
            out.append("".join(piece))
            i, last, last_at = j, c, j - 1
            continue
        arrow = last == ">" and last_at > 0 and text[last_at - 1] == "="
        if c == "/" and (
            last == "" or last in "(,=:[!&|?{;+-*%~^" or arrow or last_word in _JS_REGEX_WORDS
        ):
            j = i + 1
            in_class = False
            while j < n and text[j] != "\n":
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == "[":
                    in_class = True
                elif text[j] == "]":
                    in_class = False
                elif text[j] == "/" and not in_class:
                    break
                j += 1
            j = min(j + 1, n)
            while j < n and text[j].isalpha():  # flags
                j += 1
            out.append(_blank(text[i:j]))
            i, last, last_at = j, "/", j - 1
            continue
        out.append(c)
        if not c.isspace():
            if c.isalnum() or c in "_$":
                last_word = last_word + c if last and (last.isalnum() or last in "_$") else c
            last, last_at = c, i
        i += 1
    return "".join(out)


def _template_end(text: str, start: int) -> Tuple[int, List[Tuple[int, int]]]:
    """(index after the closing backtick, [(a, b) of each `${...}` expression's inside]).

    Walks the template from its opening backtick. An expression is code and may itself hold
    strings, comments and nested templates, so its end is found by lexing it — a brace inside
    a nested string is not its closer.
    """
    n = len(text)
    spans: List[Tuple[int, int]] = []
    i = start + 1
    while i < n:
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == "`":
            return i + 1, spans
        if c == "$" and i + 1 < n and text[i + 1] == "{":
            j = i + 2
            depth = 0
            while j < n:
                d = text[j]
                if d in "'\"":
                    k = j + 1
                    while k < n and text[k] not in (d, "\n"):
                        k += 2 if text[k] == "\\" else 1
                    j = k + 1
                    continue
                if d == "`":
                    j, _ = _template_end(text, j)
                    continue
                if d == "{":
                    depth += 1
                elif d == "}":
                    if depth == 0:
                        break
                    depth -= 1
                j += 1
            spans.append((i + 2, min(j, n)))
            i = j + 1
            continue
        i += 1
    return n, spans


def _jsx_text_blanked(code: str) -> str:
    """JSX children text blanked out of a .tsx file whose literals are already blank.

    A small state machine rather than a regex, because `>` and `<` are also comparison and
    generic-parameter delimiters: a `<` opens a tag only when the character right before it
    is not part of a name (`useState<T>` is a generic, `return <div>` is a tag) and the
    character after it begins a tag name, a `/`, or a fragment. Inside an element's children,
    text runs to the next `<` or `{`; a `{...}` child is code again, to its matching brace.
    A misjudged tag costs recall, never a false finding: the only thing this can do to code
    is blank it.
    """
    out = list(code)
    n = len(code)
    stack: List[Tuple[str, int]] = [("js", 0)]  # ("js", brace depth) | ("jsx", 0)
    i = 0

    def tag_end(start: int) -> Tuple[int, bool, bool]:
        """(index after the tag's `>`, is_closing, is_self_closing) for a tag at `start`."""
        closing = code.startswith("</", start)
        depth = 0
        j = start + 1
        while j < n:
            ch = code[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth = max(0, depth - 1)
            elif ch == ">" and depth == 0:
                return j + 1, closing, code[j - 1] == "/"
            j += 1
        return n, closing, False

    def _generic_not_tag(at: int, end: int) -> bool:
        """`<T,>(x)` and `write: <T>(run)` are type-parameter lists, not elements. A tag
        header never holds a bare comma, and an element is never followed by `(`."""
        header = code[at:end]
        depth = 0
        for ch in header:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            elif ch == "," and depth == 0:
                return True
        after = end
        while after < n and code[after] in " \t":
            after += 1
        return after < n and code[after] == "("

    def opens_tag(at: int) -> bool:
        before = code[at - 1] if at > 0 else " "
        after = code[at + 1] if at + 1 < n else ""
        if before.isalnum() or before in "_$)]":
            return False
        return after.isalpha() or after in "/>_$"

    while i < n:
        state, depth = stack[-1]
        c = code[i]
        if state == "js":
            if c == "{":
                stack[-1] = (state, depth + 1)
            elif c == "}":
                if depth == 0 and len(stack) > 1:
                    stack.pop()
                else:
                    stack[-1] = (state, max(0, depth - 1))
            elif c == "<" and opens_tag(i):
                end, closing, selfclosing = tag_end(i)
                if _generic_not_tag(i, end):
                    i += 1
                    continue
                if not closing and not selfclosing:
                    stack.append(("jsx", 0))
                i = end
                continue
            i += 1
            continue
        # jsx children
        if c == "{":
            stack.append(("js", 0))
            i += 1
            continue
        if c == "<":
            end, closing, selfclosing = tag_end(i)
            if closing:
                stack.pop()
            elif not selfclosing:
                stack.append(("jsx", 0))
            i = end
            continue
        j = i
        while j < n and code[j] not in "<{":
            j += 1
        for k in range(i, j):
            if code[k] != "\n":
                out[k] = " "
        i = j
    return "".join(out)


def _shell_code_only(text: str) -> str:
    lines = []
    for line in text.split("\n"):
        if line.lstrip().startswith("#!"):
            lines.append(_blank(line))
            continue
        line = re.sub(r"'[^']*'|\"[^\"]*\"", lambda m: _blank(m.group(0)), line)
        line = re.sub(r"(^|\s)#(?!\{).*$", lambda m: m.group(1) + _blank(m.group(0)[len(m.group(1)):]), line)
        lines.append(line)
    return "\n".join(lines)


def _css_code_only(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", lambda m: _blank(m.group(0)), text, flags=re.S)
    return re.sub(r"'[^'\n]*'|\"[^\"\n]*\"", lambda m: _blank(m.group(0)), text)


def _md_prose_only(text: str) -> str:
    """A markdown file with every fenced code block, inline code span and single-asterisk
    italic span blanked, byte for byte, so line numbers survive and what is left is PROSE —
    never code, and never a quote of someone's exact words (owner's ruling, test-audit plan,
    2026-09-27: exempt "owner quotes in backticks or italics").

    A fence is a line whose stripped text starts with three (or more) backticks or tildes;
    every line up to its matching close is blanked, fence lines included. An inline code span
    is `` `...` `` on one line. An italic span is `*...*` on one line — `(?<!\\*)\\*(?!\\*)`
    on each side excludes `**bold**`, since a doubled `*` is never this repo's italic. The
    owner's quotes are written `*"..."*` (D007's own style), which this blanks whole. A span
    that crosses a line break is a miss, never a false finding, the limit every other
    span-reading function in this file accepts.
    """
    out_lines: List[str] = []
    in_fence = False
    for line in text.split("\n"):
        stripped = line.lstrip()
        if stripped[:3] in ("```", "~~~"):
            in_fence = not in_fence
            out_lines.append(_blank(line))
            continue
        if in_fence:
            out_lines.append(_blank(line))
            continue
        line = re.sub(r"`[^`\n]*`", lambda m: _blank(m.group(0)), line)
        line = re.sub(r"(?<!\*)\*(?!\*)[^*\n]+\*(?!\*)", lambda m: _blank(m.group(0)), line)
        out_lines.append(line)
    return "\n".join(out_lines)


_PY_NAME = re.compile(r"(?<![\w.])[A-Za-z_]\w*")
_JS_NAME = re.compile(r"[A-Za-z_$][\w$]*")
_CSS_NAME = re.compile(r"-{0,2}[A-Za-z_][\w-]*")
_PROSE_WORD = re.compile(r"[A-Za-z]+")


def spelling_findings(text: str, suffix: str) -> List[Tuple[int, str, str, str]]:
    """(line, name, british word, american word) for every British identifier in a code
    file's text, or every British WORD in a markdown file's PROSE (`.md`, owner's ruling,
    test-audit plan, 2026-09-27). `suffix` picks the reader; an unknown suffix is read as
    nothing."""
    found: List[Tuple[int, str, str, str]] = []
    if suffix == ".py":
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
        except (tokenize.TokenError, SyntaxError, IndentationError):
            tokens = []
        # 3.12 (PEP 701) tokenizes an f-string's `{expr}` into real NAME tokens; 3.9 emits the
        # whole f-string as one STRING. Skip everything inside FSTRING_START..FSTRING_END so the
        # verdict is the same on both (getattr: the names do not exist before 3.12).
        f_start = getattr(tokenize, "FSTRING_START", None)
        f_end = getattr(tokenize, "FSTRING_END", None)
        in_fstring = 0
        for tok in tokens:
            if f_start is not None and tok.type == f_start:
                in_fstring += 1
            elif f_end is not None and tok.type == f_end:
                in_fstring -= 1
            elif in_fstring == 0 and tok.type == tokenize.NAME and not keyword.iskeyword(tok.string):
                hit = british_spelling(tok.string)
                if hit:
                    found.append((tok.start[0], tok.string, hit[0], hit[1]))
        return found
    if suffix in (".ts", ".tsx", ".mjs"):
        code = _js_code_only(text)
        if suffix == ".tsx":
            code = _jsx_text_blanked(code)
        pattern = _JS_NAME
    elif suffix == ".sh":
        code = _shell_code_only(text)
        pattern = _JS_NAME
    elif suffix == ".css":
        code = _css_code_only(text)
        pattern = _CSS_NAME
    elif suffix == ".md":
        code = _md_prose_only(text)
        pattern = _PROSE_WORD
    else:
        return found
    for match in pattern.finditer(code):
        hit = british_spelling(match.group(0))
        if hit:
            found.append((code.count("\n", 0, match.start()) + 1, match.group(0), hit[0], hit[1]))
    return found


def _findings_of(item: Tuple[str, str]) -> List[Tuple[int, str, str, str]]:
    return spelling_findings(*item)


def spelling_findings_many(items: List[Tuple[str, str]], timeout: float = 120, worker=_findings_of) -> List[List[Tuple[int, str, str, str]]]:
    """`spelling_findings` over (text, suffix) pairs, in order. The whole-tree read is ~1M
    tokens of pure-Python lexing, so a big batch fans out over forked workers; a staged commit's
    handful of files stays in-process. Same findings either way. A worker that dies or hangs
    raises multiprocessing.TimeoutError after `timeout` seconds, so docs-audit fails closed."""
    if len(items) < 32:
        return [worker(item) for item in items]
    with multiprocessing.get_context("fork").Pool() as pool:
        return pool.map_async(worker, items, chunksize=8).get(timeout=timeout)


SHELL_SUFFIXES = (".sh",)
SHELL_EXTRA = ("scripts/githooks/pre-commit", "scripts/githooks/pre-push",
               "scripts/githooks/reference-transaction")

_DQ = re.compile(r'"(?:[^"\\]|\\.)*"')


def shell_substitution_findings(text: str):
    """Unescaped backticks inside a double-quoted shell string — command substitution."""
    for number, line in enumerate(text.split("\n"), 1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        for match in _DQ.finditer(line):
            body = match.group(0)
            # A backtick the author escaped is a literal and is what every other site here does.
            if re.search(r'(?<!\\)`', body):
                yield number, body.strip()


def check_shell_substitution(report: Report) -> None:
    """A backtick inside a double-quoted shell string RUNS, and every other site here escapes it.

    **Blocking, on D16's test: this is mechanical and there is nothing to judge.** A backtick
    inside double quotes is command substitution, so a message that names a command EXECUTES
    it. `bash -n` is silent — the line is valid shell, it simply does something else.

    **It is kept for one measured incident.** `scripts/reap-selftest.sh` carried
    `bad "refused without naming `` `make down` ``, ..."` on a failure path. On the primary
    checkout `make down` stops the capture server `make launch-agent` keeps alive over the
    owner's real store, so a FAILING assertion in the test suite would have taken the owner's
    server down as a side effect of printing why it failed. It fires only when that arm fails,
    which is why it survived every green run; the arm failed repeatedly on 2026-09-11 from an
    unrelated flake.

    **Twelve other sites in this repo already spell it `` \\` ``** — the rule was understood
    everywhere but one line, which is exactly the shape a mechanical check is for.

    **What it cannot see.** A backtick in a heredoc body (not a double-quoted string), and a
    deliberate substitution someone wrote in the modern `$(...)` form, which this never flags.
    """
    findings: List[Finding] = []
    scanned = 0
    paths = list(_walk(ROOT, SHELL_SUFFIXES))
    for extra in SHELL_EXTRA:
        candidate = ROOT / extra
        if candidate.exists():
            paths.append(candidate)
    for path in paths:
        scanned += 1
        for line, body in shell_substitution_findings(read(path)):
            findings.append(
                Finding(
                    f"{rel(path)}:{line}",
                    f"a backtick inside a double-quoted string RUNS as command "
                    f"substitution: {body[:90]}. Escape it (\\`) or single-quote the "
                    f"string. `bash -n` cannot see this — the line is valid shell.",
                )
            )
    report.add(
        "shell substitution",
        MECHANICAL,
        findings,
        f"{len(findings)} unescaped backtick(s) in a double-quoted shell string" if findings
        else f"no double-quoted shell string in {scanned} files runs a command by accident",
        scanned=scanned,
    )
