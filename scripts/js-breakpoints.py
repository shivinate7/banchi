#!/usr/bin/env python3
"""A responsive breakpoint belongs in the stylesheet (D123).

Where a screen genuinely needs one in JavaScript — because a `useState` picks a whole layout
to render, not merely which declaration applies — its value must match a breakpoint a
stylesheet already declares. Not any stylesheet: THE ONE THE COMPONENT ITSELF IMPORTS. A
component declares which stylesheets it is subject to by importing them, and that import is a
primitive this repo already built for a different question (D141's browser-scope classifier,
which has to know whether file A reaches file B) — reused here rather than reimplemented.

THE DEFECT THIS EXISTS TO CATCH: `app/src/Orders.tsx` carried
`useMediaQuery('(min-width: 1024px)')` to choose its whole desktop layout. It imports
`./BoxBrowse.css`, `./BoxOps.css` and `./Orders.css` — none of the three declares a 1024px
viewport breakpoint; `RunPanel.css` does, and `Orders.tsx` never imports it. A GLOBAL
comparison ("does any stylesheet anywhere under app/src declare 1024") is blind to this,
because `RunPanel.css` and `App.css` both happen to open a regime at that value for reasons
of their own — the row would read the defect as clean. Pairing by the IMPORT GRAPH instead
asks the only question D123 actually means: does the CSS THIS COMPONENT ANSWERS TO agree with
the JavaScript it also carries. `app/src/BoxBrowse.tsx:704` is the shape this row wants
everywhere: `useMediaQuery('(max-width: 767px)')`, and `BoxBrowse.tsx` imports
`BoxBrowse.css`, which declares exactly that.

THE PAIRING IS DIRECT IMPORTS ONLY, NEVER THE WHOLE RENDER-TREE CLOSURE. `Orders.tsx` also
transitively imports `OrdersWalkPane.tsx`, which imports `Shipping.css` — and `Shipping.css`
happens to declare `max-width: 1023px` (canonical 1024), which would silently launder the
exact defect back to green if this row followed JS-to-JS imports before collecting CSS. A
component's own breakpoint logic answers to what IT declares itself governed by — its own
`import './X.css'` lines — never to a child component's private stylesheet. Stylesheet-to-
stylesheet `@import` IS followed (none exist under app/src today; the reader still walks the
chain if one appears), because a sheet importing another sheet is still one declaration the
component subscribed to by importing the first.

A FILE THAT IMPORTS NO STYLESHEET AT ALL, and still runs a viewport media query in
JavaScript, is UNPAIRED and reported as its own kind of finding — never a silent pass and
never folded into "mismatch," because there is no CSS to compare against, only an absence to
name. If that ever fires on a real file, the fix is either to import the stylesheet the query
is really answering to, or to argue in this docstring why that file is exempt; it is not
something this row may guess its way around.

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

THE IMPORT READER IS BORROWED, NOT OWNED: `resolve_relative`/`file_imports` come from
`scripts/browser-scope.py` (loaded dynamically here, the same way `docs-audit.py`'s own
`_sibling` loads it), because that classifier already had to answer "does file A reach file
B by relative import" for D141's reason, CSS `@import` included. It has one known quirk this
row inherits rather than papers over: `_RELATIVE_EXTENSIONS` tries `.css` before
`/index.tsx`, so `import ... from './kit'` resolves to `app/src/kit.css` instead of
`app/src/kit/index.tsx` wherever a directory and a same-named stylesheet both exist (only
`kit`, today). `kit.css` declares no viewport width this defeats, so it does not change any
verdict here — flagged separately rather than patched around inside this script.

    scripts/js-breakpoints.py check      the real tree, printed, exit 1 on any finding
    scripts/js-breakpoints.py selftest   prove the row by violating it, then by fixing it
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Optional, Sequence, Tuple

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


class Verdict(NamedTuple):
    mismatches: List[Mismatch]
    # Files that carry a JS viewport breakpoint but import no stylesheet at all — nothing
    # can vouch for the value, and that is reported rather than silently allowed or silently
    # widened into a global search.
    unpaired: List[str]


def compare(
    js_by_file: Dict[str, List[Tuple[str, int, int]]],
    subject_css_by_file: Dict[str, Optional[Sequence[Tuple[str, int, int]]]],
) -> Verdict:
    """Per file: its OWN subject stylesheets decide its verdict, never any other file's.

    PURE: `js_by_file` maps a path string to that file's `read_js_widths()` output.
    `subject_css_by_file` maps the SAME path to the flattened `read_css_widths()` output of
    every stylesheet THAT FILE is subject to (its own import graph — see
    `subject_css_widths`), or `None` when it imports no stylesheet at all. `selftest()`
    drives this directly with small fixture dicts — no filesystem, no import graph, no
    `app/src`, so it can pose the exact shape of the Orders defect and prove this function
    alone would have caught it.
    """
    mismatches: List[Mismatch] = []
    unpaired: List[str] = []
    for path, widths in js_by_file.items():
        if not widths:
            continue
        css = subject_css_by_file.get(path)
        if css is None:
            unpaired.append(path)
            continue
        css_canon = {canonical(s, v) for s, v, _ in css}
        for side, value, line in widths:
            if canonical(side, value) not in css_canon:
                mismatches.append(Mismatch(path, line, side, value))
    return Verdict(sorted(mismatches), sorted(unpaired))


def subject_css_widths(
    js_path: str,
    file_imports_fn: Callable[[str], Sequence[str]],
    read_fn: Optional[Callable[[Path], str]] = None,
) -> Optional[List[Tuple[str, int, int]]]:
    """Every `@media` width from every stylesheet `js_path` is subject to.

    "Subject to" means: every `.css` file `js_path` imports DIRECTLY, followed transitively
    stylesheet-to-stylesheet through `@import` — never back out through another
    `.ts`/`.tsx`'s own imports. `None` when `js_path` imports no stylesheet at all.

    `file_imports_fn` is injected (real callers pass `browser-scope.py`'s own
    `file_imports`, which already resolves relative JS and CSS imports for D141's reason) so
    `selftest()` can drive this with a small fixture dict instead of a real import graph.
    `read_fn` defaults to a plain disk read; `docs-audit.py`'s row passes its own `read()` so
    a stylesheet's CONTENT is read staged-commit-aware even though the import graph itself,
    borrowed from `browser-scope.py`, is not (that script always reads the worktree — the
    same limitation `docs-audit.py`'s `browser scope` and `spec map` rows already accept).
    """
    def _default_read(p: Path) -> str:
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    reader: Callable[[Path], str] = read_fn or _default_read
    direct = [p for p in file_imports_fn(js_path) if p.endswith(".css")]
    if not direct:
        return None
    seen: set = set()
    queue: List[str] = list(direct)
    ordered: List[str] = []
    while queue:
        p = queue.pop(0)
        if p in seen:
            continue
        seen.add(p)
        ordered.append(p)
        queue.extend(x for x in file_imports_fn(p) if x.endswith(".css"))
    widths: List[Tuple[str, int, int]] = []
    for p in ordered:
        widths.extend(read_css_widths(reader(ROOT / p)))
    return widths


def js_files(app_src: Path) -> List[Path]:
    return sorted(app_src.rglob("*.tsx")) + sorted(app_src.rglob("*.ts"))


def css_files(app_src: Path) -> List[Path]:
    # Non-recursive: every stylesheet under app/src sits directly in it, not in a
    # subdirectory — the same assumption `docs-audit.py`'s own breakpoint rows make.
    return sorted(app_src.glob("*.css"))


def _load_browser_scope():
    """`scripts/browser-scope.py`, imported for its `file_imports`/`resolve_relative` — the
    import-graph reader D141 already built, reused here rather than rewritten. `None` on any
    failure, the same fail-open posture `docs-audit.py`'s own `_sibling` takes, so a broken
    or missing sibling costs this script's own callers, never crashes them."""
    path = ROOT / "scripts" / "browser-scope.py"
    if not path.exists():
        return None
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "browser_scope_for_js_breakpoints", path
        )
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module
    except Exception:  # noqa: BLE001 - a broken sibling must not take this script down
        return None


def scan(
    app_src: Path = APP_SRC,
) -> Tuple[
    Dict[str, List[Tuple[str, int, int]]],
    Dict[str, Optional[List[Tuple[str, int, int]]]],
]:
    """The real tree's inputs to `compare`, read once from disk.

    Split out from that function so the comparison itself stays filesystem- and import-graph
    free and provable without either. This is this script's own CLI/self-test convenience;
    `docs-audit.py`'s row builds the same two structures itself instead (its `read()` honors
    staged-commit mode for stylesheet content) and calls `compare` directly.
    """
    js_by_file: Dict[str, List[Tuple[str, int, int]]] = {}
    for path in js_files(app_src):
        widths = read_js_widths(path.read_text(encoding="utf-8", errors="replace"))
        if widths:
            rel_path = path.resolve().relative_to(ROOT).as_posix()
            js_by_file[rel_path] = widths
    bscope = _load_browser_scope()
    subject_by_file: Dict[str, Optional[List[Tuple[str, int, int]]]] = {}
    for path in js_by_file:
        subject_by_file[path] = (
            subject_css_widths(path, bscope.file_imports) if bscope is not None else None
        )
    return js_by_file, subject_by_file


def check(app_src: Path = APP_SRC) -> int:
    js_by_file, subject_by_file = scan(app_src)
    if _load_browser_scope() is None:
        print("scripts/browser-scope.py does not import; no file can be paired to its "
              "own stylesheets")
        return 1
    verdict = compare(js_by_file, subject_by_file)
    for m in verdict.mismatches:
        print(f"{m.path}:{m.line}: `{m.side}-width: {m.value}px` has no counterpart in any "
              f"stylesheet this file imports")
    for path in verdict.unpaired:
        lines = ", ".join(str(line) for _, _, line in js_by_file[path])
        print(f"{path}: imports no stylesheet at all, so nothing can vouch for its viewport "
              f"quer{'y' if len(js_by_file[path]) == 1 else 'ies'} (line {lines})")
    total_js = sum(len(v) for v in js_by_file.values())
    total_findings = len(verdict.mismatches) + len(verdict.unpaired)
    if total_findings:
        print(f"{total_findings} of {len(js_by_file)} file(s) with a JS breakpoint have a "
              f"problem ({len(verdict.mismatches)} mismatched, {len(verdict.unpaired)} unpaired)")
        return 1
    print(f"{total_js} JS breakpoint(s) in {len(js_by_file)} file(s) — every one matches a "
          f"stylesheet that file itself imports")
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

    print("\nimport-graph pairing — subject_css_widths")

    def fake_imports(fake: Dict[str, List[str]]) -> Callable[[str], List[str]]:
        return lambda path: fake.get(path, [])

    fake_reads = {
        "a.css": "@media (max-width: 767px) {}",
        "b.css": "@media (min-width: 900px) {}",
        "c.css": "@import './a.css';",
    }
    css_direct = subject_css_widths(
        "widget.tsx",
        fake_imports({"widget.tsx": ["widget.css", "helper.ts"]}),
        read_fn=lambda p: fake_reads.get(p.name, ""),
    )
    ok(css_direct is not None, "a file with a direct css import is paired")

    subj = subject_css_widths(
        "orders.tsx",
        fake_imports({"orders.tsx": ["boxbrowse.css", "boxops.css", "orders.css"]}),
        read_fn=lambda p: fake_reads.get(p.name, ""),
    )
    ok(subj == [], "a file's THREE own css imports, none declaring the width, pair to []",
       str(subj))

    subj_with_chain = subject_css_widths(
        "widget.tsx",
        fake_imports({"widget.tsx": ["c.css"], "c.css": ["a.css"]}),
        read_fn=lambda p: fake_reads.get(p.name, ""),
    )
    ok(subj_with_chain == [("max", 767, 1)],
       "a stylesheet's own `@import` is followed one level down", str(subj_with_chain))

    subj_no_recurse = subject_css_widths(
        "orders.tsx",
        fake_imports({
            "orders.tsx": ["orders.css", "child.tsx"],
            "child.tsx": ["b.css"],
        }),
        read_fn=lambda p: fake_reads.get(p.name, ""),
    )
    ok(subj_no_recurse == [],
       "a CHILD COMPONENT's stylesheet (reached only through another .tsx's own import) is "
       "never pulled in — the pairing stops at CSS, and never re-enters JS", str(subj_no_recurse))

    unpaired_subj = subject_css_widths(
        "naked.tsx", fake_imports({"naked.tsx": ["helper.ts", "other.tsx"]})
    )
    ok(unpaired_subj is None, "a file that imports no stylesheet at all is unpaired (None)")

    print("\nTHE VIOLATION, POSED EXACTLY AS THE REAL DEFECT WAS SHAPED (RED)")
    red = compare(
        {"orders.tsx": [("min", 1024, 1315)]},
        {"orders.tsx": [("max", 767, 3)]},  # orders.tsx's OWN three css files, flattened —
        # none of them declares 1024, exactly like Orders.css/BoxBrowse.css/BoxOps.css today
    )
    ok(red.mismatches == [Mismatch("orders.tsx", 1315, "min", 1024)] and not red.unpaired,
       "a JS breakpoint with no counterpart in ITS OWN subject stylesheets is reported even "
       "though a DIFFERENT file's stylesheet (not shown to this file) declares that value",
       str(red))

    print("\nGLOBAL SCOPE WOULD HAVE MISSED THIS — the regression this row now guards against")
    would_be_global_green = compare(
        {"orders.tsx": [("min", 1024, 1315)]},
        # if the caller mistakenly flattened EVERY stylesheet under app/src (including one
        # orders.tsx never imports) into orders.tsx's own subject set:
        {"orders.tsx": [("max", 767, 3), ("min", 1024, 13)]},
    )
    ok(would_be_global_green.mismatches == [],
       "proves the shape of the old defect: handed a global (wrong) subject set, the same "
       "function reports clean — which is exactly why the subject set must be per-file, "
       "never global", str(would_be_global_green))

    print("\nTHE FIX — Orders.tsx now imports (or one of its own sheets now declares) 1024 "
          "(GREEN)")
    green = compare(
        {"orders.tsx": [("min", 1024, 1315)]},
        {"orders.tsx": [("max", 767, 3), ("min", 1024, 40)]},
    )
    ok(green.mismatches == [], "once ITS OWN subject stylesheets declare it, the pair is clean",
       str(green))

    print("\nthe off-by-one pairing — a `min` in JS, the matching `max` in CSS")
    paired = compare({"a.tsx": [("min", 768, 5)]}, {"a.tsx": [("max", 767, 9)]})
    ok(paired.mismatches == [],
       "a JS `min-width: 768` matches a CSS `max-width: 767` by canonical value", str(paired))

    print("\na clean file beside a broken one — only the broken one is named")
    mixed = compare(
        {"clean.tsx": [("max", 767, 1)], "broken.tsx": [("min", 999, 2)]},
        {"clean.tsx": [("max", 767, 3)], "broken.tsx": [("max", 767, 3)]},
    )
    ok([m.path for m in mixed.mismatches] == ["broken.tsx"],
       "the clean file's own breakpoint does not drag the broken one's file into the report",
       str(mixed))

    print("\na file with no stylesheet at all is UNPAIRED, never silently passed")
    unpaired_case = compare(
        {"naked.tsx": [("min", 900, 4)]},
        {"naked.tsx": None},
    )
    ok(unpaired_case.mismatches == [] and unpaired_case.unpaired == ["naked.tsx"],
       "no CSS to compare against is its own finding, not a pass and not a mismatch",
       str(unpaired_case))

    print("\non the real tree")
    bscope = _load_browser_scope()
    ok(bscope is not None, "scripts/browser-scope.py imports")
    js_by_file, subject_by_file = scan(APP_SRC)
    ok(bool(js_by_file), f"app/src has at least one JS breakpoint to compare ({len(js_by_file)} files)")
    real = compare(js_by_file, subject_by_file)
    print(f"  ({len(real.mismatches)} mismatch(es), {len(real.unpaired)} unpaired file(s) on "
          f"the real tree today — reported here, never asserted against, because this "
          f"self-test proves the MECHANISM and never a screen's current numbers)")
    if bscope is not None:
        orders_path = "app/src/Orders.tsx"
        orders_widths = js_by_file.get(orders_path, [])
        if orders_widths:
            orders_subject = subject_by_file.get(orders_path)
            print(f"  (app/src/Orders.tsx today: {len(orders_widths)} JS breakpoint(s), "
                  f"subject stylesheets carry {len(orders_subject or [])} width(s))")

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
