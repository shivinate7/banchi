#!/usr/bin/env python3
"""`make css-var-check` — a `var(--x)` with no fallback, where `--x` is defined nowhere.

WHAT THIS EXISTS ABOUT. `var(--x)` with no second argument does not fall back to anything
when `--x` is unset: the CSS Custom Properties spec makes the whole declaration invalid, and
the browser drops it silently — no console warning, no visual hint beyond the property simply
not applying. Five of these accumulated across four screens (`CaptureScreen.css`,
`OrdersWalkPane.css`, `Pricing.css` twice, `ProductHistory.css`) and were found only by hand,
on 2026-09-20, then confirmed live by reading `getComputedStyle` in the running app. Two are
misspellings of a real token (`--bn-r-md`, `--bn-radius-md` for `--bn-r-lg`); three reach for a
token this repo never defined at all (`--bn-well`, `--bn-muted`, `--bn-border`). Every one of
the five renders — a square corner, a lost background, a missing border — and nothing failed.

THE RULE IS NARROW ON PURPOSE, the same shape as `sigil-check.py`'s: a reference is a finding
only when the property is defined NOWHERE this checker can see, and `var(--x, fallback)` is
never a finding — the fallback IS the definition, and a screen that means to fall back to a
literal is doing nothing wrong. This cannot tell "meant to fall back" from "typo with a
coincidentally plausible second argument"; it only tells "unset variable, no escape."

A REFERENCE IS NOT ONLY `var(--x)` IN A STYLESHEET, EITHER. `app/src/**/*.{ts,tsx}` writes
`var(--x)` inside plain string and template-literal style values too — Gallery's kit page
alone carries five (`'var(--bn-surface)'`, `'var(--bn-font-display)'`, `'var(--bn-font-ui)'`,
`'var(--bn-font-mono)'`, `'var(--bn-ok)'`) — and a checker that read only `.css` would call an
undefined one clean. FIXED 2026-09-20, the day this check landed: it shipped scanning `.ts`/
`.tsx` for definitions only, and a reviewer's mutation of `--bn-ok` to a typo on Gallery.tsx's
own receipt swatch exited 0. References are now read from both.

A DEFINITION IS NOT ONLY `--x: ...;` IN A STYLESHEET. `app/src/**/*.{ts,tsx}` sets a handful of
these at runtime — `style={{ '--x': ... }}`, `style={{ ['--x' as string]: ... }}`, and
`el.style.setProperty('--x', ...)` — measured across the tree before these patterns were
chosen (`--cap-halt-h`, `--pricing-ship-h`, `--receipt-ms`, `--i`, `--n`, `--pos-slot`, and
others, all real and all otherwise invisible to a checker that reads only `.css`). Missing any
one of those three shapes would report a false positive on every property it sets, so all
three are matched. THE FIRST TWO ARE READ ONLY INSIDE A `style={{...}}` SPAN — found by
brace-counting from each `style={` — and not anywhere a quoted key meets a colon: an unrelated
object literal whose key happens to be spelled like a token name would otherwise silently mask
a real finding, which is exactly how a definition-side check goes quiet. No such collision
exists in this tree today; the span restriction is here so one landing tomorrow still counts.

COMMENTS ARE STRIPPED BEFORE EITHER SIDE IS COLLECTED — a reference or a definition written
only in prose (this very docstring names five properties by their `--` spelling) is neither a
real usage nor a real definition, and a checker that read its own comments as either would be
unusable on the file that explains it. `@media` and `@supports` blocks are NOT special-cased:
a property defined or referenced inside one is a real definition or a real reference — Banchi's
dark theme reassigns tokens under `:root[data-theme='dark']` rather than a media query, so no
existing rule depends on the distinction, and carving out at-rules would only be a way to miss
a future one.

WHAT IT CANNOT DO: a property set through a ref forwarded across files, a `CSSStyleSheet`
inserted at runtime, or a name built from a template literal (`` `--bn-${x}` ``, which Gallery's
kit page uses to sweep the whole `--bn-*` family and which this checker does not attempt to
resolve) all pass unseen. Narrower than a real CSS engine and cheaper than one; the four real
patterns measured above are what this repo's screens actually do.

Writes nothing, ever — a gate, and a gate that writes is refused in this repo (D18).

    make css-var-check                    scan app/src
    python3 scripts/css-var-check.py --self-test   the extractors, against fixtures

Escape hatch: `PKMNSCAN_CSS_VARS=off` skips the scan, printed in the refusal so it is never a
silent workaround.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Iterable, List, NamedTuple, Sequence, Tuple

ROOT = Path(__file__).resolve().parent.parent
CSS_DIR = "app/src"
TS_DIR = "app/src"
CSS_SUFFIXES = (".css",)
TS_SUFFIXES = (".ts", ".tsx")

HATCH = "PKMNSCAN_CSS_VARS"

# ------------------------------------------------------------------------------ patterns

# A custom property name: `--`, then a CSS identifier. No leading digit rule enforced beyond
# what CSS itself is loose about; good enough for every name in this tree.
NAME = r"--[A-Za-z_][A-Za-z0-9_-]*"

# `var(--x)` or `var(--x, fallback)`. The character right after the (optionally spaced) name
# tells the two apart: `,` means a fallback was given, `)` means none was.
VAR_REF = re.compile(r"var\(\s*(" + NAME + r")\s*([,)])")

# A custom-property DECLARATION in a stylesheet: the name immediately followed by `:`. This
# never matches inside `var(--x)` — that construct is followed by `,` or `)`, never `:` — so
# no exclusion is needed beyond ordering (definitions are collected from the same cleaned text
# references are read from, but the two patterns cannot both match the same span).
CSS_DEF = re.compile(r"(" + NAME + r")\s*:")

# TSX: `'--x':` or `"--x":` as a plain object-literal key.
TS_DEF_PLAIN_KEY = re.compile(r"(['\"])(" + NAME + r")\1\s*:")

# TSX: `['--x']:` or `['--x' as string]:` as a computed object-literal key.
TS_DEF_BRACKET_KEY = re.compile(
    r"\[\s*(['\"])(" + NAME + r")\1(?:\s+as\s+string)?\s*\]\s*:"
)

# TSX/TS: `el.style.setProperty('--x', ...)` (any receiver — `page.style`,
# `document.documentElement.style`, a plain `host.style`, all seen in this tree).
TS_DEF_SET_PROPERTY = re.compile(r"\.setProperty\(\s*(['\"])(" + NAME + r")\1")


class Reference(NamedTuple):
    path: str
    line: int
    text: str
    name: str


def strip_css_comments(source: str) -> str:
    """Blank `/* ... */` comments, preserving line structure so positions stay honest."""

    def blank(match: re.Match) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    return re.sub(r"/\*.*?\*/", blank, source, flags=re.DOTALL)


def strip_ts_comments(source: str) -> str:
    """Blank `//` and `/* ... */` comments in a TS/TSX file, same reasoning as the CSS half."""

    def blank(match: re.Match) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))

    source = re.sub(r"/\*.*?\*/", blank, source, flags=re.DOTALL)
    source = re.sub(r"//[^\n]*", blank, source)
    return source


def css_definitions(cleaned: str) -> Iterable[str]:
    for match in CSS_DEF.finditer(cleaned):
        yield match.group(1)


def references(path: str, cleaned: str) -> List[Reference]:
    """Every `var(--x)` with no fallback, CSS or TS/TSX alike — a reference written inside a
    plain or template-literal string is not stripped (only comments are), so this same scan
    finds `'var(--bn-ok)'` in a `.tsx` file exactly as it finds `var(--bn-ok)` in a `.css`
    one."""
    raw_lines = cleaned.splitlines()
    out: List[Reference] = []
    for match in VAR_REF.finditer(cleaned):
        line = cleaned.count("\n", 0, match.start()) + 1
        if match.group(2) == ",":
            continue  # a fallback was given — the fallback IS the definition
        name = match.group(1)
        text = raw_lines[line - 1] if 0 < line <= len(raw_lines) else ""
        out.append(Reference(path, line, text.strip(), name))
    return out


def style_object_spans(cleaned: str) -> Iterable[str]:
    """Each `style={...}` JSX attribute's own text, `style=` through its matching closing
    brace — found by counting braces rather than assuming a shape, so `style={{ ['--x' as
    string]: n } as CSSProperties}`'s trailing cast stays inside the span it belongs to.

    THIS IS WHAT KEEPS `TS_DEF_PLAIN_KEY`/`TS_DEF_BRACKET_KEY` FROM READING AN UNRELATED
    OBJECT LITERAL AS A DEFINITION: a quoted key followed by `:` is common in this tree (route
    payloads, wire records) and only means a custom property inside a `style` attribute. No
    such collision exists today — this is here so a future one is still refused rather than
    silently masking a real finding.
    """
    for match in re.finditer(r"style\s*=\s*\{", cleaned):
        depth = 1  # the brace `style=\{` already consumed
        i = match.end()
        while i < len(cleaned) and depth > 0:
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
            i += 1
        yield cleaned[match.start():i]


def ts_definitions(cleaned: str) -> Iterable[str]:
    for span in style_object_spans(cleaned):
        for pattern in (TS_DEF_PLAIN_KEY, TS_DEF_BRACKET_KEY):
            for match in pattern.finditer(span):
                yield match.group(2)
    for match in TS_DEF_SET_PROPERTY.finditer(cleaned):
        yield match.group(2)


def files(base_dir: str, suffixes: Sequence[str]) -> Iterable[Path]:
    base = ROOT / base_dir
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*")):
        if path.suffix in suffixes and path.is_file():
            yield path


# ------------------------------------------------------------------------------- the scan


def scan_sources(
    css_sources: Sequence[Tuple[str, str]], ts_sources: Sequence[Tuple[str, str]]
) -> Tuple[List[Reference], int]:
    """The pure half: (path, raw text) pairs in, findings out. No filesystem, so the
    self-test exercises exactly what a real run exercises."""
    defined = set()
    cleaned_all: List[Tuple[str, str]] = []
    for path, source in css_sources:
        cleaned = strip_css_comments(source)
        cleaned_all.append((path, cleaned))
        defined.update(css_definitions(cleaned))
    for path, source in ts_sources:
        cleaned = strip_ts_comments(source)
        cleaned_all.append((path, cleaned))
        defined.update(ts_definitions(cleaned))

    findings: List[Reference] = []
    for path, cleaned in cleaned_all:
        for ref in references(path, cleaned):
            if ref.name not in defined:
                findings.append(ref)
    return findings, len(defined)


def scan() -> Tuple[List[Reference], int, int, int]:
    css_sources = [
        (str(p.relative_to(ROOT)), p.read_text(encoding="utf-8"))
        for p in files(CSS_DIR, CSS_SUFFIXES)
    ]
    ts_sources = [
        (str(p.relative_to(ROOT)), p.read_text(encoding="utf-8"))
        for p in files(TS_DIR, TS_SUFFIXES)
    ]
    findings, defined_count = scan_sources(css_sources, ts_sources)
    return findings, len(css_sources), len(ts_sources), defined_count


# ------------------------------------------------------------------------------ self-test
#
# Three fixtures, each a tiny (path, css-text) and optionally a (path, ts-text) pair, proving
# the guard sees its own subject before it is trusted (parent CLAUDE.md's rule): a genuinely
# undefined `var()` must fail, a `var()` with a fallback must pass, and a property defined only
# from TSX must pass. A few more pin the decisions this file states above.

SelfCase = Tuple[str, List[Tuple[str, str]], List[Tuple[str, str]], int]

SELF_TEST: Tuple[SelfCase, ...] = (
    (
        "a var() with no fallback and no definition anywhere is a finding",
        [("f.css", ".x { color: var(--bn-nope); }")],
        [],
        1,
    ),
    (
        "the same property, declared in the same file, is not a finding",
        [("f.css", ":root { --bn-nope: red; }\n.x { color: var(--bn-nope); }")],
        [],
        0,
    ),
    (
        "a var() with a fallback is never a finding, defined or not",
        [("f.css", ".x { color: var(--bn-nope, blue); }")],
        [],
        0,
    ),
    (
        "a property defined only from a TSX inline style object is not a finding",
        [("f.css", ".x { height: var(--cap-halt-h); }")],
        [("f.tsx", "page.style.setProperty('--cap-halt-h', `${h}px`)")],
        0,
    ),
    (
        "a property defined only as a plain object-literal key is not a finding",
        [("f.css", ".x { --n: var(--i); }")],
        [("f.tsx", "<div style={{ '--i': i } as CSSProperties} />")],
        0,
    ),
    (
        "a property defined only as a bracket computed key (with `as string`) is not a finding",
        [("f.css", ".x { width: var(--pos-slot-digits); }")],
        [("f.tsx", "style={{ ['--pos-slot-digits' as string]: n } as CSSProperties}")],
        0,
    ),
    (
        "a bracket computed key with no `as string` cast is also a definition",
        [("f.css", ".x { width: var(--bn-slot-key); }")],
        [("f.tsx", "style={{ ['--bn-slot-key']: JSON.stringify(k) } as CSSProperties}")],
        0,
    ),
    (
        "a reference inside a comment is not a finding",
        [("f.css", "/* once used var(--bn-gone) here */\n.x { color: red; }")],
        [],
        0,
    ),
    (
        "a definition inside a comment does not count as a real definition",
        [("f.css", "/* --bn-gone: red; */\n.x { color: var(--bn-gone); }")],
        [],
        1,
    ),
    (
        "a reference inside @media is a real reference",
        [("f.css", "@media (min-width: 600px) { .x { color: var(--bn-gone); } }")],
        [],
        1,
    ),
    (
        "a definition inside @media satisfies a reference anywhere in the file",
        [
            (
                "f.css",
                "@media (prefers-color-scheme: dark) { :root { --bn-seasonal: #000; } }\n"
                ".x { color: var(--bn-seasonal); }",
            )
        ],
        [],
        0,
    ),
    (
        "the two real misspellings this check was built to catch",
        [
            (
                "f.css",
                ".a { border-radius: var(--bn-r-md); }\n"
                ".b { border-radius: var(--bn-radius-md); }",
            )
        ],
        [],
        2,
    ),
    (
        "an undefined var() inside a TSX inline style string is a finding — the Gallery.tsx "
        "gap: a reference was read from .css only, so a reviewer's mutation of --bn-ok to a "
        "typo on a TSX line exited 0",
        [],
        [("f.tsx", "<Icon style={{ color: 'var(--bn-nope-typo)' }} />")],
        1,
    ),
    (
        "the same reference, over a token defined elsewhere, is not a finding",
        [("tokens.css", ":root { --bn-ok: #15803d; }")],
        [("f.tsx", "<Icon style={{ color: 'var(--bn-ok)' }} />")],
        0,
    ),
    (
        "a quoted key outside any style={{...}} does not count as a definition — the "
        "second gap: an unrelated object literal must not mask a real finding",
        [("f.css", ".x { color: var(--bn-nope); }")],
        [("f.tsx", "const payload = { '--bn-nope': 1 }")],
        1,
    ),
    (
        "the same key, inside a real style={{...}}, still counts as a definition",
        [("f.css", ".x { color: var(--bn-nope); }")],
        [("f.tsx", "<div style={{ '--bn-nope': 1 } as CSSProperties} />")],
        0,
    ),
)


def self_test() -> int:
    bad = 0
    for name, css_sources, ts_sources, expected in SELF_TEST:
        findings, _ = scan_sources(css_sources, ts_sources)
        got = len(findings)
        ok = got == expected
        bad += 0 if ok else 1
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}: expected {expected}, got {got}")
        if not ok:
            for finding in findings:
                print(f"          {finding.path}:{finding.line}  {finding.text}")
    print()
    if bad:
        print(f"css-var-check --self-test: {bad} of {len(SELF_TEST)} cases FAILED")
        return 1
    print(f"css-var-check --self-test: {len(SELF_TEST)} cases pass")
    return 0


def main(argv: Sequence[str]) -> int:
    if "--self-test" in argv:
        return self_test()

    if os.environ.get(HATCH) == "off":
        print(f"css-var-check: skipped ({HATCH}=off).")
        return 0

    findings, css_scanned, ts_scanned, defined_count = scan()
    if not findings:
        print(
            f"css-var-check: {css_scanned} stylesheet(s), {ts_scanned} TS/TSX file(s), "
            f"{defined_count} custom propert{'y' if defined_count == 1 else 'ies'} defined, "
            f"no undefined `var()` with no fallback."
        )
        return 0

    print(
        "css-var-check: a `var(--x)` with no fallback drops its whole declaration silently "
        "when `--x` is defined nowhere.\n"
    )
    for finding in findings:
        print(f"  {finding.path}:{finding.line}")
        print(f"      {finding.text}")
        print(f"      `{finding.name}` is referenced here and defined nowhere this checker "
              f"can see (no `.css` declaration, no TS/TSX runtime set).")
        print(f"      Point it at the token it means, or give it a fallback: "
              f"`var({finding.name}, <value>)`.\n")
    print(
        f"{len(findings)} finding(s). Escape hatch: `{HATCH}=off` skips this check, printed "
        f"here so it is never a silent workaround."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
