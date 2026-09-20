#!/usr/bin/env python3
"""A responsive breakpoint belongs in the stylesheet (D123).

Where a screen genuinely needs one in JavaScript — because a `useState` picks a whole layout
to render, not merely which declaration applies — its value must match a breakpoint a
stylesheet under `app/src` already declares, so the two can never quietly disagree.

THE DEFECT THIS EXISTS TO CATCH: `app/src/Orders.tsx` carried
`useMediaQuery('(min-width: 1024px)')` to choose its whole desktop layout, while its own
stylesheet collapsed at 767. The two disagreed for weeks and `make docs-audit`'s
`breakpoint columns` row never saw it, because that row reads stylesheets only — it has no
JavaScript side to compare against. `app/src/BoxBrowse.tsx:704` is the shape this row wants
everywhere: `useMediaQuery('(max-width: 767px)')`, matching a breakpoint
`app/src/BoxBrowse.css` actually declares.

THE COMPARISON IS GLOBAL, ACROSS EVERY STYLESHEET UNDER `app/src`, NOT PER-SCREEN. A
stricter, per-screen version (a `X.tsx` breakpoint must appear in `X.css` itself) would catch
more — including the Orders case above, whose own `Orders.css` never declares 1024 even
though `RunPanel.css` does — but it would have to guess which stylesheet "belongs" to a
`.tsx` file with no sibling CSS at all (`RunsComposer.tsx`, `RunsDrop.tsx`, `RunsLog.tsx`,
`RunsStage.tsx`, `CardHero.tsx`), and a guessed pairing is exactly the kind of invented
primitive this repo's own rule warns against. The global form asks only what D123 actually
rules: a JS breakpoint is never a number no stylesheet in the product uses. A per-screen
version is a strictly separate, stricter check that a future row could add on top of this
one; this row does not claim to be it.

SIDES ARE CANONICALIZED: a `min-width: V` and a `max-width: V-1` are the same regime
boundary — `docs-audit.py`'s own `breakpoints` row already treats them as one for the same
reason. A JS `min-width: 768` therefore matches a CSS `max-width: 767` without this row
inventing a false positive on top of a real one.

NON-VIEWPORT MEDIA FEATURES — `prefers-reduced-motion`, `prefers-color-scheme`, `hover`,
`pointer` — carry no width at all and never match the extractor's regex, so they never reach
this row; nothing has to name them.

CONTAINER QUERIES ARE LEFT OUT ON PURPOSE. `@container` has no JavaScript equivalent — no
`matchMedia` call resolves one — so there is no JS side ever to compare against a container
breakpoint. And a CSS `@container` width answers a different question (a pane's width, not
the window's) that `breakpoint columns` already asks; counting it as a "CSS counterpart"
would let a JS *viewport* query hide behind a *column* rule that says nothing about the
viewport at all. Only `@media` widths from the stylesheets feed this row.

    scripts/js-breakpoints.py check      the real tree, printed, exit 1 on any mismatch
    scripts/js-breakpoints.py selftest   prove the row by violating it, then by fixing it
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
APP_SRC = ROOT / "app" / "src"

# The same three tokens whether they sit after `@media` in a stylesheet or inside a
# `matchMedia(...)` string in a component. `(min|max)-width: NNNpx)` is specific enough that
# nothing else in this codebase's CSS or TypeScript happens to spell it by coincidence.
_WIDTH_RE = re.compile(r"\((max|min)-width:\s*(\d+)px\)")
_AT_MEDIA_RE = re.compile(r"@media([^{]*)\{")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")


def strip_css_comments(text: str) -> str:
    """`/* */` replaced by as many newlines as it spanned, so a `file:line` still points at
    the rule and never at a comment discussing one."""
    return _BLOCK_COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def strip_js_comments(text: str) -> str:
    """Block comments newline-preserved (the same trick, for the same reason); whole-line and
    trailing `//` comments dropped outright — a same-line drop never moves a later line, so
    it needs no newline count of its own."""
    text = _BLOCK_COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return _LINE_COMMENT_RE.sub("", text)


def read_css_widths(text: str) -> List[Tuple[str, int, int]]:
    """Every `(min|max)-width: NNNpx)` inside an `@media` block — never `@container` — as
    (side, value, line). Pure, so `selftest()` can drive it with no filesystem."""
    body = strip_css_comments(text)
    found: List[Tuple[str, int, int]] = []
    for at in _AT_MEDIA_RE.finditer(body):
        line = body[: at.start()].count("\n") + 1
        for side, value in _WIDTH_RE.findall(at.group(1)):
            found.append((side, int(value), line))
    return found


def read_js_widths(text: str) -> List[Tuple[str, int, int]]:
    """Every `(min|max)-width: NNNpx)` anywhere in a `.ts`/`.tsx` file's text, comments
    stripped first, as (side, value, line). Pure, so `selftest()` can drive it."""
    body = strip_js_comments(text)
    found: List[Tuple[str, int, int]] = []
    for match in _WIDTH_RE.finditer(body):
        line = body[: match.start()].count("\n") + 1
        found.append((match.group(1), int(match.group(2)), line))
    return found


def canonical(side: str, value: int) -> int:
    """A `min-width: V` and a `max-width: V-1` open the same regime, so they collapse to one
    number — `V` itself. The same arithmetic `docs-audit.py`'s `breakpoints` row uses."""
    return value if side == "min" else value + 1


class Mismatch(NamedTuple):
    path: str
    line: int
    side: str
    value: int


def find_mismatches(
    js_by_file: Dict[str, List[Tuple[str, int, int]]],
    css_widths: Sequence[Tuple[str, int, int]],
) -> List[Mismatch]:
    """Every JS breakpoint whose canonical value no CSS breakpoint under `app/src` shares.

    PURE: `js_by_file` maps any path string to that file's `read_js_widths()` output, and
    `css_widths` is the flattened `read_css_widths()` output of every stylesheet in scope.
    `selftest()` drives this directly with small fixture dicts — no filesystem, no `app/src`.
    """
    css_canon = {canonical(side, value) for side, value, _ in css_widths}
    mismatches = [
        Mismatch(path, line, side, value)
        for path, widths in js_by_file.items()
        for side, value, line in widths
        if canonical(side, value) not in css_canon
    ]
    return sorted(mismatches)


def js_files(app_src: Path) -> List[Path]:
    return sorted(app_src.rglob("*.tsx")) + sorted(app_src.rglob("*.ts"))


def css_files(app_src: Path) -> List[Path]:
    # Non-recursive: every stylesheet under app/src sits directly in it, not in a
    # subdirectory — the same assumption `docs-audit.py`'s own breakpoint rows make.
    return sorted(app_src.glob("*.css"))


def scan(
    app_src: Path = APP_SRC,
) -> Tuple[Dict[str, List[Tuple[str, int, int]]], List[Tuple[str, int, int]]]:
    """The real tree's inputs to `find_mismatches`, read once from disk.

    Split out from that function so the comparison itself stays filesystem-free and provable
    without one. `docs-audit.py`'s own row reads the tree itself instead (its `read()` honors
    staged-commit mode; this one does not) and calls `find_mismatches` directly — this
    function exists for this script's own CLI and self-test convenience.
    """
    js_by_file: Dict[str, List[Tuple[str, int, int]]] = {}
    for path in js_files(app_src):
        widths = read_js_widths(path.read_text(encoding="utf-8", errors="replace"))
        if widths:
            js_by_file[str(path)] = widths
    css_widths: List[Tuple[str, int, int]] = []
    for path in css_files(app_src):
        css_widths.extend(read_css_widths(path.read_text(encoding="utf-8", errors="replace")))
    return js_by_file, css_widths


def _rel(path: str) -> str:
    try:
        return str(Path(path).resolve().relative_to(ROOT))
    except ValueError:
        return path


def check(app_src: Path = APP_SRC) -> int:
    js_by_file, css_widths = scan(app_src)
    mismatches = find_mismatches(js_by_file, css_widths)
    for m in mismatches:
        print(f"{_rel(m.path)}:{m.line}: `{m.side}-width: {m.value}px` has no counterpart "
              f"in any stylesheet under app/src")
    total_js = sum(len(v) for v in js_by_file.values())
    if mismatches:
        print(f"{len(mismatches)} of {total_js} JS breakpoint(s) have no CSS counterpart")
        return 1
    print(f"{total_js} JS breakpoint(s) in {len(js_by_file)} file(s), "
          f"{len(css_widths)} CSS breakpoint(s) — every JS breakpoint matches a stylesheet's own")
    return 0


# ------------------------------------------------------------------------------ selftest


def selftest() -> int:
    failures: List[str] = []

    def ok(condition: bool, label: str, detail: str = "") -> None:
        print(f"  {'ok  ' if condition else 'FAIL'} {label}")
        if not condition:
            failures.append(label)
            if detail:
                print(f"       {detail}")

    print("js-breakpoints self-test\n" + "=" * 72)

    print("\nextraction")
    ok(read_js_widths("const q = '(min-width: 1024px)'") == [("min", 1024, 1)],
       "a matchMedia-shaped string yields one width")
    ok(read_js_widths("/* (min-width: 900px)\nline2 */\nconst q = '(min-width: 1024px)'")
       == [("min", 1024, 3)],
       "a block comment's width is stripped and the real line survives the strip")
    ok(read_js_widths("// (min-width: 900px)\nconst q = '(min-width: 1024px)'")
       == [("min", 1024, 2)],
       "a line comment's width is stripped")
    ok(read_js_widths("const q = '(prefers-reduced-motion: reduce)'") == [],
       "a non-viewport media feature carries no width and is never read")
    ok(read_css_widths("@media (max-width: 767px) { .x { color: red; } }")
       == [("max", 767, 1)],
       "a CSS `@media` width is read")
    ok(read_css_widths("@container pane (min-width: 560px) { .x {} }") == [],
       "a `@container` width is never read as a viewport breakpoint")
    ok(read_css_widths("/* @media (max-width: 700px) */\n@media (max-width: 767px) {}")
       == [("max", 767, 2)],
       "a width discussed in a CSS comment is never mistaken for a rule")

    print("\ncanonicalization")
    ok(canonical("min", 768) == 768 and canonical("max", 767) == 768,
       "a `min-width: V` and a `max-width: V-1` are the same regime boundary")

    print("\nTHE VIOLATION — a JS breakpoint no stylesheet declares (RED)")
    red = find_mismatches({"a.tsx": [("min", 1024, 12)]}, [("max", 767, 3)])
    ok(len(red) == 1 and red[0] == Mismatch("a.tsx", 12, "min", 1024),
       "a JS breakpoint with no CSS counterpart is reported", str(red))

    print("\nTHE FIX — the same breakpoint, now declared somewhere in the stylesheets (GREEN)")
    green = find_mismatches({"a.tsx": [("min", 1024, 12)]},
                             [("max", 767, 3), ("min", 1024, 40)])
    ok(green == [], "once a stylesheet declares it, the same pair is clean", str(green))

    print("\nthe off-by-one pairing — a `min` in JS, the matching `max` in CSS")
    paired = find_mismatches({"a.tsx": [("min", 768, 5)]}, [("max", 767, 9)])
    ok(paired == [], "a JS `min-width: 768` matches a CSS `max-width: 767` by canonical value",
       str(paired))

    print("\na clean file beside a broken one — only the broken one is named")
    mixed = find_mismatches(
        {"clean.tsx": [("max", 767, 1)], "broken.tsx": [("min", 999, 2)]},
        [("max", 767, 3)],
    )
    ok([m.path for m in mixed] == ["broken.tsx"],
       "the clean file's own breakpoint does not drag the broken one's file into the report",
       str(mixed))

    print("\non the real tree")
    js_by_file, css_widths = scan(APP_SRC)
    ok(bool(js_by_file), f"app/src has at least one JS breakpoint to compare ({len(js_by_file)} files)")
    ok(bool(css_widths), f"app/src has at least one CSS breakpoint to compare ({len(css_widths)})")
    real = find_mismatches(js_by_file, css_widths)
    print(f"  ({len(real)} mismatch(es) on the real tree today — reported here, never "
          f"asserted against, because this self-test proves the MECHANISM and never a "
          f"screen's current numbers)")

    print()
    if failures:
        print(f"{len(failures)} failed")
        return 1
    print("clean")
    return 0


def main(argv: Sequence[str] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("check", help="the real tree, printed")
    sub.add_parser("selftest", help="prove the row by violating it, then by fixing it")
    args = parser.parse_args(argv)

    if args.command == "selftest":
        return selftest()
    return check()


if __name__ == "__main__":
    sys.exit(main())
