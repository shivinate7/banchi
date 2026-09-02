#!/usr/bin/env python3
"""`make sigil-check` — a bare `#` on an owner-side screen is a COUNT, never a store key (D92).

WHAT THIS EXISTS ABOUT. D58 split one address into two numbers: `Place.index` is the store key
— the `/inventory/<box>/<index>` path, the `<index>.jpg` the photograph is named after, what
every write aims by — and `Place.slot` is the number a person counts to, which moves as cards
leave the box in front of it. Both are on the wire because they answer different questions.
Three renderers then spelled BOTH with the same sigil: `#/inventory`'s sticky section header
drew `Section 1 · #1–#82` in count space while the neighbour row beside it drew `#41` from the
key. On the owner's box 3 those spaces are 76 apart, so `#27` named two different cards on one
screen and nothing said which was which.

THE RULE IS THE NARROW ONE, because it is the only one a text check can hold honestly: a `#`
composed from an expression that mentions `index` is refused. Not "every number is checked" —
this cannot tell a count from a key in general, and a check that claimed to would be worse than
none. What it catches is the specific, repeated mistake: reaching for the field named `index`
when drawing a figure a hand is meant to count to.

WHY A TEXT CHECK AND NOT A TYPE. A nominal type over the two numbers is the fix that could not
be evaded, and it was considered and rejected on cost: `slot` and `index` are plain numbers
across forty call sites and the whole wire contract, and branding them is a refactor with a
much larger blast radius than the bug. This is cheap, it runs on every commit, and it catches
the next screen at the moment it is written rather than two days later on a real box.

WHAT IT CANNOT DO, stated plainly so a green run is not read as more than it is: it matches
text, so a renamed local (`const n = side.index` then `#{n}`) walks straight past it. That is
the known ceiling. It is recorded in docs/DEBTS.md rather than papered over — the alternative
is a check whose limits nobody wrote down, which is the failure `docs/DEBTS.md` exists for.

COMMENTS AND STRINGS ARE STRIPPED FIRST, and that is load-bearing rather than tidiness. The
prose explaining this very rule contains `#{side.index}` as an example, in three files. A
checker that read its own documentation as a violation would be unrunnable on the tree that
documents it.

    make sigil-check          check app/src
    python3 scripts/sigil-check.py --self-test    the extractors, against fixtures

An intentional key render marks its line `sigil-ok:` with a reason. Nothing does today.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable, List, NamedTuple, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
SCANNED = ("app/src",)
SUFFIXES = (".ts", ".tsx")

# The escape hatch, and it must carry a reason after the marker — a bare token would be a way
# to switch the check off without saying why, which is how an allowlist becomes a graveyard.
ALLOW = re.compile(r"sigil-ok:\s*\S")

# WHERE THE MARKER MAY SIT: on the offending line, or anywhere in the CONTIGUOUS COMMENT BLOCK
# directly above it. Not a fixed line window — a window can reach past intervening code and
# silence a violation nobody meant to exempt. The comment block is the right unit because every
# real exemption here needs a paragraph, not a trailing clause: all four in this tree explain
# why the record has no slot to draw instead, which does not fit after the code.
#
# "IS THIS LINE A COMMENT" IS ASKED OF THE STRIPPER RATHER THAN OF A SECOND REGEX, and the first
# attempt got this wrong in a way worth keeping written down. It matched line SHAPES — `//`,
# `/*`, a leading `*` — which is only true of comments that are formatted like the ones the
# author had in mind; every justification actually written for this check wraps onto plain
# continuation lines, and the walk stopped at the first one. `strip_noise` already blanks a
# comment to spaces, so a line that is nothing but comment is EMPTY in the cleaned text. That
# is an exact test, it covers every comment style the stripper covers by construction, and it
# still cannot reach past real code, which is never empty there.

# `#` then an interpolation or a JSX expression, capturing the expression's text:
#   `#${side.index}`   template literal
#   #{side.index}      JSX child
# The expression body is non-greedy and brace-free, so a nested object literal ends the match
# rather than swallowing the rest of the file.
SIGIL = re.compile(r"#\$?\{([^{}]*)\}")

# What makes a captured expression a store key. Word-boundaried so `indexOf` — which is a string
# search and appears in this very directory — is not a hit.
KEY = re.compile(r"\bindex\b", re.IGNORECASE)


class Finding(NamedTuple):
    path: str
    line: int
    text: str
    expression: str

    def render(self) -> str:
        return (
            f"  {self.path}:{self.line}\n"
            f"      {self.text.strip()}\n"
            f"      draws `#` over `{self.expression.strip()}`, which is a store key. D58 made "
            f"a bare `#` a COUNT.\n"
            f"      Send and draw the slot; keep the index for addressing. See D92.\n"
        )


def strip_noise(source: str) -> str:
    """Blank out comments and string literals, PRESERVING LINE STRUCTURE.

    Replaced with spaces rather than deleted so that line numbers and column positions in a
    finding still point at the real source. A regex-per-construct rather than a parser: this
    runs from a bare `python3` with no venv (the `make check` rule every step-away tool here
    follows), and a TypeScript parser is not available under that constraint.

    TEMPLATE LITERALS ARE DELIBERATELY NOT STRIPPED — they are where half the violations live
    (`` `#${side.index}` ``). Only quoted strings and comments go, which is enough to keep the
    checker off its own documentation and off `PositionLabel.tsx`'s STORE_KEY regex source.
    """

    def blank(match: re.Match) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    # Order matters: block comments first, then line comments, then quoted strings.
    source = re.sub(r"/\*.*?\*/", blank, source, flags=re.DOTALL)
    source = re.sub(r"//[^\n]*", blank, source)
    source = re.sub(r"'(?:\\.|[^'\\\n])*'", blank, source)
    source = re.sub(r'"(?:\\.|[^"\\\n])*"', blank, source)
    return source


def only_comment(raw: str, clean: str) -> bool:
    """Whether this line carries no code — blank, or nothing but a comment.

    `clean` empty is the plain case. The second branch is the JSX one: `{/* ... */}` blanks to
    `{` and `}`, which is not empty, so the braces are discounted — but ONLY when something was
    actually stripped from the line. Without that second test a lone `}` closing a real block
    would read as a comment, and an exemption could then reach up past it into a paragraph
    written about some other code entirely.
    """
    if not clean.strip():
        return True
    return clean.strip(" \t{}") == "" and clean != raw


def allowed(raw_lines: Sequence[str], cleaned: Sequence[str], number: int) -> bool:
    """Whether an exemption covers the 1-based line `number`.

    The line itself, then upward while the CLEANED text is empty — comment or blank — stopping
    at the first line holding real code. Read from `raw_lines`, because the marker lives in the
    comment the cleaner just blanked.
    """
    if ALLOW.search(raw_lines[number - 1]):
        return True
    at = number - 2
    while at >= 0 and only_comment(raw_lines[at], cleaned[at]):
        if ALLOW.search(raw_lines[at]):
            return True
        at -= 1
    return False


def scan_text(path: str, source: str) -> List[Finding]:
    raw_lines = source.splitlines()
    cleaned = strip_noise(source).splitlines()
    out: List[Finding] = []
    for number, line in enumerate(cleaned, start=1):
        raw = raw_lines[number - 1] if number <= len(raw_lines) else ""
        if allowed(raw_lines, cleaned, number):
            continue
        for match in SIGIL.finditer(line):
            if KEY.search(match.group(1)):
                out.append(Finding(path, number, raw, match.group(1)))
    return out


def files() -> Iterable[Path]:
    for where in SCANNED:
        base = ROOT / where
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix in SUFFIXES and path.is_file():
                yield path


def scan() -> List[Finding]:
    out: List[Finding] = []
    for path in files():
        out.extend(
            scan_text(str(path.relative_to(ROOT)), path.read_text(encoding="utf-8"))
        )
    return out


# ------------------------------------------------------------------------------ the self-test
#
# In `make check` and never in the git hook, which is D16/D18's placement for every checker
# that checks itself. The cases are the ones that actually bit: the real violation, the two
# spellings of the fix, and — the case that makes this file runnable at all — its own prose.

SELF_TEST: Tuple[Tuple[str, str, int], ...] = (
    ("the violation, JSX", "return <b>#{side.index}</b>", 1),
    ("the violation, template", "const name = `#${side.index}`", 1),
    ("the fix, JSX", "return <b>#{side.slot}</b>", 0),
    ("the fix, template", "const name = `#${side.slot}`", 0),
    ("a comment describing the violation", "/* it drew #{side.index} until D92 */", 0),
    ("a line comment describing it", "// `#${side.index}` was the bug", 0),
    ("a quoted string in a test message", "checks.equal(x, y, 'the #{index} it drew')", 0),
    ("indexOf is not an index", "const at = `#${name.indexOf(', ')}`", 0),
    ("an explicit allow", "<b>#{side.index}</b> // sigil-ok: this row addresses", 0),
    ("a bare allow marker does not count", "<b>#{side.index}</b> // sigil-ok:", 1),
    (
        "the marker in the comment block above",
        "// sigil-ok: a departed record has no slot\n<b>#{side.index}</b>",
        0,
    ),
    (
        "a JSX comment block above",
        "{/* sigil-ok: no slot exists here */}\n<b>#{side.index}</b>",
        0,
    ),
    (
        "a closing brace is code and stops the walk",
        "{/* sigil-ok: about the block above */}\n}\n<b>#{side.index}</b>",
        1,
    ),
    (
        "the marker cannot reach past intervening code",
        "// sigil-ok: this covers the line below only\nconst x = 1\n<b>#{side.index}</b>",
        1,
    ),
    ("case-folded field", "<b>#{side.Index}</b>", 1),
    ("a nested brace does not swallow the file", "f({a: 1}); const q = `#${o.index}`", 1),
)


def self_test() -> int:
    bad = 0
    for name, source, expected in SELF_TEST:
        got = len(scan_text("<self-test>", source))
        ok = got == expected
        bad += 0 if ok else 1
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}: expected {expected}, got {got}")
        if not ok:
            print(f"          source: {source}")
    print()
    if bad:
        print(f"sigil-check --self-test: {bad} of {len(SELF_TEST)} cases FAILED")
        return 1
    print(f"sigil-check --self-test: {len(SELF_TEST)} cases pass")
    return 0


def main(argv: Sequence[str]) -> int:
    if "--self-test" in argv:
        return self_test()

    found = scan()
    if not found:
        scanned = sum(1 for _ in files())
        print(f"sigil-check: {scanned} files, no bare `#` drawn over a store key.")
        return 0

    print("sigil-check: a bare `#` on these screens is a COUNT, and these draw a store key.\n")
    for finding in found:
        print(finding.render())
    print(
        f"{len(found)} finding(s). D58 split the two numbers and D92 gave the sigil to the "
        f"count.\nDraw `slot`; keep `index` for addressing. An intentional key render marks "
        f"its line `sigil-ok: <reason>`."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
