"""Self-test cases, spelling rows. Called by `selftest.self_test`."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from .core import ROOT, Report, _STAGED_PATHS, markdown_files, module_globals, rel
from .design import _RAW_COLOR_RE, check_raw_color
from .rules import (
    _markdown_spelling_found,
    _spelling_markdown_files,
    _spelling_scope,
    check_identifier_spelling,
)
from .spelling import (
    MARKDOWN_SPELLING_ALLOW,
    MARKDOWN_SPELLING_RULE,
    _PROSE_WORD,
    _md_prose_only,
    british_spelling,
    spelling_findings,
)


def run(ok) -> None:
    ok(
        bool(_RAW_COLOR_RE.search("color: #1E40AF;")) and not _RAW_COLOR_RE.search("var(--accent)"),
        "the literal pattern matches a hex and not a token reference",
        "",
    )
    report = Report()
    check_raw_color(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label["raw color"],
        "this repo's own stylesheets read every color from a token",
        str(by_label["raw color"]),
    )

    # ------------------------------------------------------------ identifier spelling
    #
    # Both directions, per language: the name is found, and the same word in every place
    # that is not a name is not. A reader that only proved the first half would go green on
    # a file it had stopped reading.
    print("\na British identifier is found, and the same word in prose is not")
    ok(
        british_spelling("fetchCatalogueRows") == ("catalogue", "catalog"),
        "camelCase is split into words and the American form is named",
        str(british_spelling("fetchCatalogueRows")),
    )
    ok(
        british_spelling("NEIGHBOURLY") == ("neighbourly", "neighborly")
        and british_spelling("_normalise_origin") == ("normalise", "normalize"),
        "an all-caps name and a snake_case name, the second through the -ise list",
        f"{british_spelling('NEIGHBOURLY')} {british_spelling('_normalise_origin')}",
    )
    ok(
        all(british_spelling(w) is None for w in ("cancellation", "pairwise", "Promise", "otherwise", "programmer", "exercised", "color")),
        "words that are -ise, -ll- or -mme in American English too are not findings",
        str([w for w in ("cancellation", "pairwise", "Promise", "otherwise", "programmer", "exercised", "color") if british_spelling(w)]),
    )
    ok(
        all(british_spelling(w) is None for w in ("is_catalogued", "NotCatalogued", "_parse_fulfilment", "labelledby")),
        "an allow-listed stem covers every relative that carries it",
        "",
    )
    ts_text = (
        "const colour = 1 // colour\n"
        "/* colour */ const s = 'colour' + `colour ${humanise(x)}`\n"
        "const r = /colour'/; const d = a / colourless / 2\n"
    )
    found = [(line, name) for line, name, _, _ in spelling_findings(ts_text, ".ts")]
    ok(
        found == [(1, "colour"), (2, "humanise"), (3, "colourless")],
        "a .ts file: a comment, a string and a regex are blank, a template's `${}` and a "
        "division's operand are read",
        str(found),
    )
    tsx_text = (
        "const A = () => (\n"
        "  <p className=\"x\">The box is labelled <b>{labelled}</b> {n} colour</p>\n"
        ")\n"
        "const f = <T,>(x: T) => x\n"
        "const g = <T>(x: T) => colourOf(x)\n"
        "const h = <Icon name=\"pin\" size={22} />\n"
        "const i = <p>{running ? <b size={1} /> : <i />} colour</p>\n"
    )
    found = [(line, name) for line, name, _, _ in spelling_findings(tsx_text, ".tsx")]
    ok(
        found == [(2, "labelled"), (5, "colourOf")],
        "a .tsx file: JSX text is blank, a `{}` child is read, a closing tag is not a regex, "
        "and a generic parameter list is not a tag",
        str(found),
    )
    py_text = '"""colour"""\n# colour\ndef normalise(x):\n    return "colour" + f"{colour}"\n'
    found = [(line, name) for line, name, _, _ in spelling_findings(py_text, ".py")]
    ok(
        found == [(3, "normalise")],
        "a .py file: the docstring, the comment and both strings are skipped",
        str(found),
    )
    found = [(line, name) for line, name, _, _ in spelling_findings(
        "#!/bin/sh\n# colour\nCOLOUR=\"colour\" # colour\necho ${COLOUR}\n", ".sh")]
    ok(found == [(3, "COLOUR"), (4, "COLOUR")], "a .sh file: the comment and the string are blank", str(found))
    found = [(line, name) for line, name, _, _ in spelling_findings(
        "/* colour */\n.bn-colour-chip { color: var(--bn-colour); content: 'colour' }\n", ".css")]
    ok(
        found == [(2, "bn-colour-chip"), (2, "--bn-colour")],
        "a .css file: a class and a custom property are names, `color` and the string are not",
        str(found),
    )

    print("\nidentifier spelling: staged scope reads only the files this commit touches")
    here = module_globals()
    saved_index, saved_staged = here["_INDEX_PATHS"], set(_STAGED_PATHS)
    try:
        here["_INDEX_PATHS"] = {"a.py", "b.py", "scripts/docs-audit.py"}
        _STAGED_PATHS.clear()
        _STAGED_PATHS.add("a.py")
        paths, whole_tree = _spelling_scope()
        ok(
            not whole_tree and paths == [ROOT / "a.py"],
            "one staged .py file: only that file is read, never the untouched b.py",
            f"whole_tree={whole_tree} paths={paths}",
        )
        _STAGED_PATHS.add("scripts/docs-audit.py")
        paths, whole_tree = _spelling_scope()
        ok(
            whole_tree,
            "RED before the fix: staging scripts/docs-audit.py itself (the table's own file) "
            "reads the whole tree instead of narrowing to it",
            f"whole_tree={whole_tree}",
        )
        _STAGED_PATHS.discard("scripts/docs-audit.py")
        _STAGED_PATHS.add("c.md")
        paths, whole_tree = _spelling_scope()
        ok(
            not whole_tree and paths == [ROOT / "a.py"],
            "a staged file outside SPELLING_SUFFIXES is never read, and does not widen the scope",
            f"whole_tree={whole_tree} paths={paths}",
        )
        here["_INDEX_PATHS"] = None
        paths, whole_tree = _spelling_scope()
        ok(whole_tree, "a full run (no staged mode) always reads the whole tree",
           f"whole_tree={whole_tree}")
    finally:
        here["_INDEX_PATHS"] = saved_index
        _STAGED_PATHS.clear()
        _STAGED_PATHS.update(saved_staged)

    print("\n_md_prose_only: fenced code, an inline span and an italic quote are blanked")
    md_sample = (
        "This sentence types the British colour word in prose.\n"
        "```\n"
        "colour inside a fence is never prose\n"
        "```\n"
        "Exempt in code: `colour`.\n"
        "Exempt as a quote: *\"the colour of money\"*.\n"
        "Never exempt: **bold colour** stays prose, only `**` is doubled.\n"
    )
    prose = _md_prose_only(md_sample)
    found = {m.group(0).lower() for m in _PROSE_WORD.finditer(prose) if m.group(0).lower() == "colour"}
    ok(len(found) == 1, "only the one true-prose `colour` survives blanking", str(_PROSE_WORD.findall(prose)))
    ok("colour" in prose.splitlines()[6], "**bold colour** is not italics and is not blanked",
       prose.splitlines()[6])

    print("\nidentifier spelling: markdown scope excludes docs/gates/ and narrows when staged")
    here = module_globals()
    saved_index, saved_staged = here["_INDEX_PATHS"], set(_STAGED_PATHS)
    try:
        here["_INDEX_PATHS"] = {"docs/gates/x.md", "docs/specs/y.md"}
        _STAGED_PATHS.clear()
        _STAGED_PATHS.add("docs/gates/x.md")
        _STAGED_PATHS.add("docs/specs/y.md")
        paths, whole_tree = _spelling_markdown_files()
        ok(
            not whole_tree and paths == [ROOT / "docs" / "specs" / "y.md"],
            "docs/gates/ is excluded even when staged, and the staged scope narrows to the rest",
            f"whole_tree={whole_tree} paths={paths}",
        )
        here["_INDEX_PATHS"] = None
        found_files = {rel(p) for p in markdown_files()}
        ok(
            any(entry.startswith("docs/gates/") for entry in found_files),
            "and docs/gates/ is NOT excluded from `markdown_files()` itself — the exclusion "
            "above is `_spelling_markdown_files`'s own filter, applied after this call, never "
            "this function's",
            f"{sorted(e for e in found_files if e.startswith('docs/'))[:5]}",
        )
    finally:
        here["_INDEX_PATHS"] = saved_index
        _STAGED_PATHS.clear()
        _STAGED_PATHS.update(saved_staged)

    print("\n_markdown_spelling_found: the british word is the entry, one per occurrence")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        target = tmp_root / "spec.md"
        target.write_text("This uses the British colour word twice: colour.\n", encoding="utf-8")
        clean = tmp_root / "clean.md"
        clean.write_text("Nothing British here.\n", encoding="utf-8")
        found = _markdown_spelling_found([target, clean])
        ok(
            found == {rel(target): {MARKDOWN_SPELLING_RULE: ["colour", "colour"]}},
            "one word twice is two entries, and a clean file adds no key",
            str(found),
        )

    print("\nidentifier spelling: the markdown offender list is wired (owner's ruling, 2026-09-27)")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        doc = tmp_root / "spec.md"
        doc.write_text("This spec uses the British colour word in prose, and judgement too.\n",
                       encoding="utf-8")
        allow_path = tmp_root / "allow.json"
        saved_root, saved_index2, saved_allow = here["ROOT"], here["_INDEX_PATHS"], MARKDOWN_SPELLING_ALLOW
        saved_files_fn = here["_spelling_markdown_files"]

        def _patch(document):
            allow_path.write_text(json.dumps(document), encoding="utf-8")
            here["MARKDOWN_SPELLING_ALLOW"] = allow_path
            here["_spelling_markdown_files"] = lambda: ([doc], True)
            here["ROOT"] = tmp_root
            here["_INDEX_PATHS"] = None

        try:
            _patch({"rules": [MARKDOWN_SPELLING_RULE], "files": {}})
            report = Report()
            check_identifier_spelling(report)
            findings = {f.message for f in report.checks[0].findings}
            ok(
                any("colour" in m for m in findings) and any("judgement" in m for m in findings),
                "RED: two unlisted British words in markdown both fail",
                str(findings),
            )

            _patch({"rules": [MARKDOWN_SPELLING_RULE], "files": {
                rel(doc): {"lane": "docs-sweep", MARKDOWN_SPELLING_RULE: ["colour", "judgement"]},
            }})
            report = Report()
            check_identifier_spelling(report)
            ok(not report.checks[0].findings, "listing both words clears the row",
               str(report.checks[0].findings))

            _patch({"rules": [MARKDOWN_SPELLING_RULE], "files": {
                rel(doc): {"lane": "docs-sweep",
                          MARKDOWN_SPELLING_RULE: ["colour", "judgement", "favour"]},
            }})
            report = Report()
            check_identifier_spelling(report)
            findings = {f.message for f in report.checks[0].findings}
            ok(
                any("favour" in m and "no longer" in m for m in findings),
                "RED: a listed word the file no longer spells that way is stale",
                str(findings),
            )
        finally:
            here["ROOT"], here["_INDEX_PATHS"] = saved_root, saved_index2
            here["MARKDOWN_SPELLING_ALLOW"] = saved_allow
            here["_spelling_markdown_files"] = saved_files_fn
