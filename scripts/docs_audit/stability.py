"""Screen stability rows: classes F, G, I and K of docs/specs/stability.md.

Nothing on screen moves unless the person moved it. The browser cases in `app/tests/stability.spec.ts`
measure the shift. These four rows read the cause out of the source, where a browser case cannot
see it on every platform: a document scrollbar that takes width only on classic-scrollbar systems,
a font that swaps in late, a transition on a layout property, a hover that changes a box.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Set, Tuple

from .core import Finding, MECHANICAL, ROOT, Report, exists, read, rel
from .design import APP_STYLES, TOKENS_CSS, strip_css_comments
from .strings import _offender_list_at_merge_base

BASE_CSS = ROOT / "app" / "src" / "base.css"
FONTS_CSS = ROOT / "app" / "src" / "fonts.css"
INDEX_HTML = ROOT / "app" / "index.html"
LAYOUT_TRANSITION_ALLOW = ROOT / "scripts" / "layout-transition-allow.json"

# ----------------------------------------------------------------- a small rule reader
#
# Selector, property and value for every declaration, with `@media`, `@container` and `@supports`
# flattened into the rule inside them and `@keyframes` and `@font-face` left out. It is not a CSS
# parser: it reads the shape these stylesheets are written in, and a block it cannot read it skips
# rather than invents.


class Declaration(NamedTuple):
    selector: str
    prop: str
    value: str
    line: int


def read_declarations(text: str) -> List[Declaration]:
    """Every declaration in `text` (comments stripped first, line numbers kept)."""
    css = strip_css_comments(text)
    found: List[Declaration] = []
    stack: List[Tuple[str, str]] = []  # (prelude, "rule" | "at" | "skip")
    start = 0
    for i, ch in enumerate(css):
        if ch == "{":
            prelude = " ".join(css[start:i].split())
            if prelude.startswith(("@keyframes", "@-webkit-keyframes", "@font-face", "@property")):
                kind = "skip"
            else:
                kind = "at" if prelude.startswith("@") else "rule"
            stack.append((prelude, kind))
            start = i + 1
        elif ch in ";}":
            _declare(css, start, i, stack, found)
            if ch == "}" and stack:
                stack.pop()
            start = i + 1
    return found


def _declare(css: str, start: int, end: int, stack: List[Tuple[str, str]], found: List[Declaration]) -> None:
    body = css[start:end]
    if not stack or ":" not in body or stack[-1][1] != "rule" or any(kind == "skip" for _, kind in stack):
        return
    prop, _, value = body.partition(":")
    prop = prop.strip().lower()
    if not re.fullmatch(r"-{0,2}[a-z][a-z0-9-]*", prop):
        return
    line = css.count("\n", 0, start + len(body) - len(body.lstrip())) + 1
    found.append(Declaration(stack[-1][0], prop, " ".join(value.split()), line))


# ------------------------------------------------------------------------ F: the gutter


def has_scrollbar_gutter(css: str) -> bool:
    """True when an `html` rule in `css` sets `scrollbar-gutter: stable`."""
    return any(d.selector == "html" and d.prop == "scrollbar-gutter" and d.value.split()[0] == "stable" for d in read_declarations(css))


def check_scrollbar_gutter(report: Report) -> None:
    """`html { scrollbar-gutter: stable }` stands in `app/src/base.css` (class F).

    A document scrollbar that comes and goes as a screen crosses the viewport height moves every
    centered or right-aligned thing by its width, 15px on a classic-scrollbar system. The browser
    case skips where scrollbars overlay (macOS by default), so this row is the check that runs
    everywhere. **Blocking, because there is nothing to judge.**
    """
    if not exists(BASE_CSS):
        report.add("scrollbar gutter", MECHANICAL, [Finding(rel(BASE_CSS), "is not there")], "no base.css", scanned=0)
        return
    ok = has_scrollbar_gutter(read(BASE_CSS))
    report.add(
        "scrollbar gutter", MECHANICAL,
        [] if ok else [Finding(rel(BASE_CSS), "has no `html { scrollbar-gutter: stable; }`. A screen that gains or loses the document scrollbar moves its content sideways by the bar's width.")],
        "the document scrollbar's width is always reserved" if ok else "no stable gutter on html", scanned=1,
    )


# ------------------------------------------------------------------------- G: the fonts

_FACE_STACK_RE = re.compile(r"^--bn-font-(?:display|ui|mono)$")


def font_families(tokens_css: str) -> List[str]:
    """The first family of each `--bn-font-*` token, in file order, once each."""
    seen: List[str] = []
    for d in read_declarations(tokens_css):
        if _FACE_STACK_RE.match(d.prop):
            first = d.value.split(",")[0].strip().strip("'\"")
            if first and first not in seen:
                seen.append(first)
    return seen


def font_stability_findings(tokens_css: str, fonts_css: str, index_html: str) -> List[Finding]:
    """What is missing, for each face the stacks name: a preload for its latin file in the document,
    a metric fallback face in `fonts.css`, and the fallback's name in every stack that names the face."""
    findings: List[Finding] = []
    css = strip_css_comments(fonts_css)
    faces = re.findall(r"@font-face\s*\{([^}]*)\}", css)
    preloads = re.findall(r"<link\b[^>]*\brel=[\"']preload[\"'][^>]*>", re.sub(r"<!--.*?-->", "", index_html, flags=re.S))
    for family in font_families(tokens_css):
        fallback = f"{family} Fallback"
        own = [f for f in faces if re.search(rf"font-family:\s*['\"]{re.escape(family)}['\"]", f)]
        latin = sorted({m for f in own for m in re.findall(r"url\(['\"]?\./(fonts/[a-z-]*-latin\.woff2)", f)})
        if not latin:
            findings.append(Finding(rel(FONTS_CSS), f"declares no latin file for {family}, so nothing can be preloaded for it."))
        for file in latin:
            if not any(f"./src/{file}" in p and re.search(r"\bas=[\"']font[\"']", p) for p in preloads):
                findings.append(Finding(rel(INDEX_HTML), f"has no `<link rel=\"preload\" as=\"font\">` for ./src/{file} ({family}). The face is requested when its first glyph is needed, so it swaps in late."))
        fallbacks = [f for f in faces if re.search(rf"font-family:\s*['\"]{re.escape(fallback)}['\"]", f)]
        needed = ("size-adjust", "ascent-override", "descent-override")
        if not fallbacks or not all(all(n in f for n in needed) for f in fallbacks):
            findings.append(Finding(rel(FONTS_CSS), f"has no `@font-face` named '{fallback}' with {', '.join(needed)}. A late swap from the system face moves text."))
        for d in read_declarations(tokens_css):
            if _FACE_STACK_RE.match(d.prop) and d.value.split(",")[0].strip().strip("'\"") == family and f"'{fallback}'" not in d.value:
                findings.append(Finding(rel(TOKENS_CSS), f"{d.prop} does not name '{fallback}' after {family}, so the fallback face is never drawn."))
    return findings


def check_font_stability(report: Report) -> None:
    """Each of the three faces is preloaded and has a metric fallback its stack names (class G).

    **Blocking.** A face absent from the document's preloads, or a stack that skips the fallback,
    is a fact about the files. The measured size of a swap is the browser case's job.
    """
    paths = (TOKENS_CSS, FONTS_CSS, INDEX_HTML)
    if not all(exists(p) for p in paths):
        report.add("font stability", MECHANICAL, [Finding(rel(p), "is not there") for p in paths if not exists(p)], "a font source is missing", scanned=0)
        return
    findings = font_stability_findings(read(TOKENS_CSS), read(FONTS_CSS), read(INDEX_HTML))
    report.add(
        "font stability", MECHANICAL, findings,
        f"{len(findings)} gaps between the faces and their preloads or fallbacks" if findings else "every face is preloaded and has a metric fallback its stack names",
        scanned=len(font_families(read(TOKENS_CSS))),
    )


# -------------------------------------------------------- I: transitions on layout properties

LAYOUT_PROPS = frozenset({
    "width", "height", "min-width", "min-height", "max-width", "max-height",
    "top", "right", "bottom", "left", "inset", "inset-block", "inset-inline",
    "inset-block-start", "inset-block-end", "inset-inline-start", "inset-inline-end",
    "block-size", "inline-size", "min-block-size", "min-inline-size", "max-block-size", "max-inline-size",
    "margin", "margin-top", "margin-right", "margin-bottom", "margin-left",
    "margin-block", "margin-inline", "margin-block-start", "margin-block-end", "margin-inline-start", "margin-inline-end",
    "padding", "padding-top", "padding-right", "padding-bottom", "padding-left",
    "padding-block", "padding-inline", "padding-block-start", "padding-block-end", "padding-inline-start", "padding-inline-end",
    "gap", "row-gap", "column-gap", "flex-basis", "grid-template", "grid-template-columns", "grid-template-rows",
    "font-size", "line-height", "border-width", "all",
})


def layout_transitions(declarations: List[Declaration]) -> List[Tuple[Declaration, str]]:
    """Each (declaration, layout property) pair a `transition` or `transition-property` names."""
    out: List[Tuple[Declaration, str]] = []
    for d in declarations:
        if d.prop not in ("transition", "transition-property", "-webkit-transition"):
            continue
        value = re.sub(r"var\([^)]*\)|calc\([^)]*\)|cubic-bezier\([^)]*\)", " ", d.value)
        for part in value.split(","):
            head = part.split()[0] if part.split() else ""
            if head in LAYOUT_PROPS:
                out.append((d, head))
    return out


def _entry_key(entry: Dict[str, str]) -> Tuple[str, str, str]:
    return (entry.get("file", ""), entry.get("selector", ""), entry.get("property", ""))


def _allow_entries(path: Path) -> Tuple[List[Dict[str, str]], Optional[str]]:
    try:
        document = json.loads(read(path)) if exists(path) else {"entries": []}
        entries = document["entries"]
        assert isinstance(entries, list) and all(isinstance(e, dict) for e in entries)
        return entries, None
    except (ValueError, KeyError, AssertionError):
        return [], "is not a JSON object with an `entries` list"


def check_layout_transitions(report: Report) -> None:
    """No `transition` names a layout property unless `scripts/layout-transition-allow.json` says why (class I).

    A transition on `width`, `height`, `top`, `margin`, `padding` or `grid-template-*` reflows the
    siblings on every frame. The listed entries are the ones that stay inside a fixed track or are
    the person's own press at that spot (docs/specs/stability.md, section 4.3). **The list only
    shrinks.** An entry names a file, a selector and a property and carries a reason. An entry
    that matches nothing is stale, an entry with no reason is a finding, and an entry the list at
    the merge-base did not hold is growth and a finding. Comments are stripped first.
    """
    if not exists(APP_STYLES):
        report.add("layout transitions", MECHANICAL, [], f"{rel(APP_STYLES)} is not there, so no stylesheet was read", scanned=0)
        return
    entries, bad = _allow_entries(LAYOUT_TRANSITION_ALLOW)
    allow_rel = rel(LAYOUT_TRANSITION_ALLOW)
    findings: List[Finding] = [Finding(allow_rel, bad)] if bad else []
    used: Set[int] = set()
    sheets = sorted(APP_STYLES.rglob("*.css"))
    for path in sheets:
        for d, prop in layout_transitions(read_declarations(read(path))):
            key = (rel(path), d.selector, prop)
            index = next((i for i, e in enumerate(entries) if _entry_key(e) == key), None)
            if index is not None:
                used.add(index)
                continue
            findings.append(Finding(
                f"{rel(path)}:{d.line}",
                f"`{d.selector}` transitions `{prop}`, a layout property, so its siblings move on each frame. "
                f"Animate transform, opacity, color or box-shadow, or list it in {allow_rel} with the reason it stays in its own track."))
    for i, entry in enumerate(entries):
        if not str(entry.get("reason", "")).strip():
            findings.append(Finding(allow_rel, f"entry {entry!r} has no reason. Write why it stays, or delete it."))
        if i not in used:
            findings.append(Finding(allow_rel, f"entry {entry!r} matches nothing, so it is stale. Delete it."))
    base, where = _offender_list_at_merge_base(allow_rel)
    if isinstance(base, dict) and isinstance(base.get("entries"), list):
        held = {_entry_key(e) for e in base["entries"] if isinstance(e, dict)}
        for entry in entries:
            if _entry_key(entry) not in held:
                findings.append(Finding(allow_rel, f"entry {entry!r} was not in the list at the merge-base {where}. The list only shrinks."))
    report.add(
        "layout transitions", MECHANICAL, findings,
        f"{len(findings)} transitions on layout properties" if findings
        else f"no transition in {len(sheets)} sheets moves a layout property outside its allowed track ({len(entries)} allow-listed)",
        scanned=len(sheets),
    )


# -------------------------------------------------------- K: hover and focus change no box

# Padding, margin, a border's width, a font's weight or size: each resizes the box a hover or a
# focus lands on, so each moves its neighbors. Color, box-shadow, outline and transform do not.
_BOX_PROPS = re.compile(
    r"^(?:padding|margin)(?:-[a-z]+)*$|^font-(?:weight|size)$|^border(?:-(?:top|right|bottom|left))?-width$|^(?:width|height|min-width|min-height|max-width|max-height)$"
)
_STATE_RE = re.compile(r":(?:hover|focus|focus-visible|focus-within|active)\b")


def state_layout_changes(declarations: List[Declaration]) -> List[Declaration]:
    """Declarations on a `:hover`, `:focus` or `:active` rule that set a property that resizes a box.

    A `border` shorthand is read too: its width is the first length in the value."""
    out: List[Declaration] = []
    for d in declarations:
        if not _STATE_RE.search(d.selector):
            continue
        shorthand = d.prop == "border" or re.fullmatch(r"border-(?:top|right|bottom|left)", d.prop)
        if _BOX_PROPS.match(d.prop) or (shorthand and re.search(r"\d", d.value)):
            out.append(d)
    return out


def check_state_layout(report: Report) -> None:
    """A `:hover`, `:focus` or `:active` rule sets no property that resizes the box (class K).

    Change color, `box-shadow`, `outline` or `transform` instead. The spec records the repo clean
    today, and this row keeps it so. **Blocking.** A justified exception would be a finding of its
    own to argue, so there is no allow list.
    """
    if not exists(APP_STYLES):
        report.add("state layout", MECHANICAL, [], f"{rel(APP_STYLES)} is not there, so no stylesheet was read", scanned=0)
        return
    findings: List[Finding] = []
    sheets = sorted(APP_STYLES.rglob("*.css"))
    for path in sheets:
        for d in state_layout_changes(read_declarations(read(path))):
            findings.append(Finding(
                f"{rel(path)}:{d.line}",
                f"`{d.selector}` sets `{d.prop}: {d.value}` on a hover, focus or press state. That resizes the box and moves its neighbors. "
                "Change color, box-shadow, outline or transform."))
    report.add(
        "state layout", MECHANICAL, findings,
        f"{len(findings)} state rules that resize a box" if findings else f"no hover, focus or press rule in {len(sheets)} sheets resizes a box",
        scanned=len(sheets),
    )
