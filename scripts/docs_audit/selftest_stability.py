"""Self-test cases, stability rows. Called by `selftest.self_test`.

Each row goes red on a planted defect and stays green on the clean shape, and the repo's own
sources are read once with the live rows.
"""

from __future__ import annotations

from .core import Report
from .stability import (
    check_font_stability,
    check_layout_transitions,
    check_scrollbar_gutter,
    check_state_layout,
    font_stability_findings,
    has_scrollbar_gutter,
    layout_transitions,
    read_declarations,
    state_layout_changes,
)

_TOKENS = ":root { --bn-font-ui: 'Inter', 'Inter Fallback', system-ui, sans-serif; }"
_FONTS = (
    "@font-face { font-family: 'Inter'; font-display: optional; src: url('./fonts/inter-latin.woff2') format('woff2'); }\n"
    "@font-face { font-family: 'Inter Fallback'; src: local('Arial'); size-adjust: 106%; ascent-override: 91%; descent-override: 22%; }\n"
)
_INDEX = '<link rel="preload" href="./src/fonts/inter-latin.woff2" as="font" type="font/woff2" crossorigin />'


def run(ok) -> None:
    print("\nthe stability rows go red on the defect and stay green on the clean shape")

    # ---------------------------------------------------------------- the rule reader
    got = read_declarations("@media (min-width: 1px) { .a:hover { padding: 2px; } }\n@keyframes k { from { width: 1px; } }\n/* .c { margin: 1px } */")
    ok([(d.selector, d.prop) for d in got] == [(".a:hover", "padding")], "the reader flattens @media, skips @keyframes and comments", str(got))

    # ------------------------------------------------------------------ F: the gutter
    ok(not has_scrollbar_gutter("html { height: 100%; }"), "an html rule with no gutter is found", "")
    ok(not has_scrollbar_gutter(".x { scrollbar-gutter: stable; }"), "the gutter on another selector is not the document's", "")
    ok(has_scrollbar_gutter("html {\n  height: 100%;\n  scrollbar-gutter: stable;\n}"), "`html { scrollbar-gutter: stable }` is read", "")

    # ------------------------------------------------------------------- G: the fonts
    ok(not font_stability_findings(_TOKENS, _FONTS, _INDEX), "a face with its preload, fallback and stack is clean", str(font_stability_findings(_TOKENS, _FONTS, _INDEX)))
    ok(any("optional" in f.message for f in font_stability_findings(_TOKENS, _FONTS.replace("font-display: optional;", "font-display: swap;"), _INDEX)), "a face with `font-display: swap` is found", "")
    ok(any("optional" in f.message for f in font_stability_findings(_TOKENS, _FONTS.replace("font-display: optional;", ""), _INDEX)), "a face with no font-display is found", "")
    ok(any("preload" in f.message for f in font_stability_findings(_TOKENS, _FONTS, "<!-- " + _INDEX + " -->")), "a preload only in a comment is a missing preload", "")
    ok(any("preload" in f.message for f in font_stability_findings(_TOKENS, _FONTS, "")), "no preload link is found", "")
    ok(any("Inter Fallback" in f.message for f in font_stability_findings(_TOKENS, _FONTS.split("\n")[0], _INDEX)), "no fallback face is found", "")
    ok(any("size-adjust" in f.message for f in font_stability_findings(_TOKENS, _FONTS.replace("size-adjust: 106%;", ""), _INDEX)), "a fallback with no size-adjust is found", "")
    ok(any("does not name" in f.message for f in font_stability_findings(":root { --bn-font-ui: 'Inter', system-ui; }", _FONTS, _INDEX)), "a stack that skips the fallback is found", "")

    # --------------------------------------------------------------- I: transitions
    planted = ".a { transition: width var(--bn-t) var(--bn-ease), opacity var(--bn-t); }\n.b { transition-property: margin-top; }\n.c { transition: all 1s; }"
    hits = [(d.selector, p) for d, p in layout_transitions(read_declarations(planted))]
    ok(hits == [(".a", "width"), (".b", "margin-top"), (".c", "all")], "width, margin-top and `all` are found", str(hits))
    clean = ".a { transition: transform var(--bn-t), opacity var(--bn-t), box-shadow var(--bn-t), border-width 0s; }"
    ok(not [h for h in layout_transitions(read_declarations(clean)) if h[1] != "border-width"], "transform, opacity and box-shadow are not", "")

    # ---------------------------------------------------------------- K: state rules
    for bad in (
        ".a:hover { padding: 2px; }",
        ".a:focus-visible { font-weight: 700; }",
        ".a:active { border-width: 2px; }",
        ".a:hover { border: 2px solid red; }",
        "@media (hover: hover) { .a:hover { margin-left: 1px; } }",
    ):
        ok(bool(state_layout_changes(read_declarations(bad))), f"a planted state rule is found: {bad}", "")
    good = ".a:hover { background: red; box-shadow: 0 0 1px red; outline: 1px solid red; transform: scale(1.02); border-color: red; }\n.b { padding: 2px; }"
    ok(not state_layout_changes(read_declarations(good)), "color, shadow, outline and transform on a state rule, and padding on a plain rule, are not", "")

    # --------------------------------------------------------- this repo's own sources
    report = Report()
    for check in (check_scrollbar_gutter, check_font_stability, check_layout_transitions, check_state_layout):
        check(report)
    rows = {row.check: row.findings for row in report.checks}
    for name in ("scrollbar gutter", "font stability", "layout transitions", "state layout"):
        ok(not rows.get(name, ["missing"]), f"this repo's own sources pass `{name}`", str(rows.get(name)))
