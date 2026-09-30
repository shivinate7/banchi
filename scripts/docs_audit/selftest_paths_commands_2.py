"""Self-test cases, paths commands rows. Called by `selftest.self_test`."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .core import ADVISORY, ROOT, Report, list_names_from_assign, markdown_files, read
from .harness_criteria import string_assign
from .hygiene import check_positional_references, verdict_disagreements
from .paths_commands import (
    LineAnchor,
    check_allowlist,
    check_line_anchors,
    code_files,
    dict_keys_from_assign,
    line_anchor_candidates,
)
from .strings import _only_shrinks


def run(ok) -> None:
    print("\nallowlist is self-cleaning")
    report = Report()
    check_allowlist(report, {"harness/run.py": "pretend this is planned"})
    findings = report.checks[0].findings
    ok(len(findings) == 1, "existing path in the allowlist is reported stale", str(findings))
    report = Report()
    check_allowlist(report, {"harness/not_yet.py": "genuinely planned"})
    findings = report.checks[0].findings
    ok(not findings, "absent path in the allowlist is fine", str(findings))

    print("\nline anchor extractor: path:N and path:N-M, routes and placeholders still suppressed")
    ok(
        line_anchor_candidates("see `docs/GATES.md:884` for the record")
        == [LineAnchor("docs/GATES.md", 884, None)],
        "a single-line anchor is extracted",
    )
    ok(
        line_anchor_candidates("`docs/GATES.md:5-7` covers the whole run")
        == [LineAnchor("docs/GATES.md", 5, 7)],
        "a range anchor is extracted",
    )
    ok(
        not line_anchor_candidates("POST /pipeline/value:200 is not a real shape anyway"),
        "a method-prefixed route is not read as a line anchor",
    )
    ok(
        not line_anchor_candidates("GET /photo/<box>/<index>:5 is a placeholder, not a path"),
        "a placeholder segment suppresses the match, same as `path_candidates`",
    )

    print("\nline anchors: the one row refuses path:N, file.ext:N and a bare :N, and nothing else")
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "fake.md"
        for cited, label in (
            ("cites `server/capture_server.py:123` here", "a single-line anchor is refused"),
            ("cites `server/capture_server.py:123-130` here", "a range anchor is refused"),
            ("cites `Revenue.css:81` here", "a file.ext:N with no directory is refused"),
            ("cites Revenue.css:81-90 here", "a bare file.ext:N-M range is refused"),
            ("`store/db.py` opens it (`:1279`) and", "a bare :N after a cited file is refused"),
            ("`store/db.py` opens it at `:1279-1290` and", "a bare :N-M after a cited file is refused"),
            ("`store/db.py` names `do_search` (~7929) here", "an approximate ~N after a cited file is refused"),
            ("`store/db.py` names `_sell` (~7199–7232), and", "an approximate ~N–M range is refused"),
            ("`app/src/server.ts`'s `request()` (line ~624) is", "line ~N is refused"),
            ("see `app/src/types.ts:~1200-1272` here", "a path:~N-M anchor is refused"),
        ):
            doc.write_text(cited + "\n", encoding="utf-8")
            report = Report()
            check_line_anchors(report, [doc])
            ok(len(report.checks[0].findings) == 1, label, str(report.checks[0].findings))
        doc.write_text("`store/db.py` is named here.\nIt opens at `:1279` and more.\n", encoding="utf-8")
        report = Report()
        check_line_anchors(report, [doc])
        ok(len(report.checks[0].findings) == 1, "a bare :N in the same paragraph as a file is refused")
        for clean, label in (
            ("cites `server/capture_server.do_search` here", "the symbol form is clean"),
            ("cites `server/capture_server.py`, line 123, here", "a line written in words is clean"),
            ("POST /pipeline/value:200 is a route", "a route is not an anchor"),
            ("open localhost:8000 in a browser", "a host and port is not an anchor"),
            ("`make dev` serves `app/dev.py` on `:5173` here", "a bare port after a file is not an anchor"),
            ("see `store/db.py`, meeting at 10:30 today", "a time is not an anchor"),
            ("see `store/db.py`, a 3:1 ratio and 4.5:1 floor", "a ratio is not an anchor"),
            ("see `store/db.py` and rows[:5] and {:5d}", "a slice and a format spec are not anchors"),
            ("see `store/db.py` at http://example.com:8080/x", "a URL with a port is not an anchor"),
            ("see `app/src/a.css` for a:hover and ::before and :nth-child(2)", "a pseudo-selector is not an anchor"),
            ("`:1279` alone, with no file named in this paragraph", "a bare :N with no cited file is not read"),
            ("see `store/db.py`: it takes ~5 ms and ~30 worktrees", "a ~N quantity is not an anchor"),
            ("see `store/db.py`: ~120 lines, ~17 s, ~2x, ~5%", "a ~N with a unit is not an anchor"),
        ):
            doc.write_text(clean + "\n", encoding="utf-8")
            report = Report()
            check_line_anchors(report, [doc])
            ok(not report.checks[0].findings, label, str(report.checks[0].findings))
        for name, planted, label in (
            ("a.py", "x = 1  # see `cli/resolve.py:669` for it\n", ".py comment path:N is refused"),
            ("a.py", "x = 1  # see Revenue.css:81 for it\n", ".py comment file.ext:N is refused"),
            ("a.py", "# `cli/resolve.py` holds it\n# at `:669` here\n", ".py comment bare :N is refused"),
            ("a.ts", "const x = 1 // see `app/src/Runs.css:319`\n", ".ts // comment is refused"),
            ("a.tsx", "/* see Runs.css:319\n   more */\n", ".tsx block comment is refused"),
            ("a.css", "/* see `app/src/Runs.tsx:319` */\n", ".css block comment is refused"),
            ("a.py", 'def f():\n    """see `cli/resolve.py:669` here"""\n', ".py docstring path:N is refused"),
            ("a.py", '"""module doc:\n`cli/resolve.py` holds it, at `:669`\n"""\n', ".py module docstring bare :N is refused"),
        ):
            code = Path(tmp) / name
            code.write_text(planted, encoding="utf-8")
            report = Report()
            check_line_anchors(report, [], [code])
            ok(len(report.checks[0].findings) == 1, label, str(report.checks[0].findings))
        for name, planted, label in (
            ("a.py", 'x = "cli/resolve.py:669"  # clean\n', ".py string outside a comment is not read"),
            ("a.py", "# meets at 10:30, a 3:1 ratio, host:8000\n", ".py comment time, ratio, host:port are clean"),
            ("a.css", "a:hover { color: red } /* clean */\n.b::before { content: 'x' }\n", ".css pseudo-selectors are clean"),
            ("a.ts", "const u = 'http://x.com:8080/a' // clean\n", ".ts URL with a port is clean"),
            ("a.py", "# `cli/resolve.py` serves :8000 and a worktree's :5201\n", "the ports server/ports.py emits are clean"),
        ):
            code = Path(tmp) / name
            code.write_text(planted, encoding="utf-8")
            report = Report()
            check_line_anchors(report, [], [code])
            ok(not report.checks[0].findings, label, str(report.checks[0].findings))
        (Path(tmp) / "docs").mkdir()
        mapfile = Path(tmp) / "docs" / "map.py"
        for planted, want, label in (
            ('X = {"why": "see `cli/resolve.py:669`"}\n', 1, "a docs/map.py prose string path:N is refused"),
            ('X = {"why": "`cli/resolve.py` opens at :669"}\n', 1, "a docs/map.py prose string bare :N is refused"),
            ('X = {"why": "the main tree keeps :8000"}\n', 0, "a docs/map.py port is clean"),
        ):
            mapfile.write_text(planted, encoding="utf-8")
            report = Report()
            check_line_anchors(report, [], [mapfile])
            ok(len(report.checks[0].findings) == want, label, str(report.checks[0].findings))
    report = Report()
    check_line_anchors(report, markdown_files())
    ok(not report.checks[0].findings and report.checks[0].scanned > 0,
       "no tracked markdown file cites a line number, and the row read some",
       str(report.checks[0].findings[:3]))
    report = Report()
    check_line_anchors(report, [], code_files())
    ok(not report.checks[0].findings and report.checks[0].scanned > 0,
       "no tracked code comment cites a line number, and the row read some",
       str(report.checks[0].findings[:3]))

    # THE ONE ONLY-SHRINKS HELPER'S OWN SELF-TEST, run here so it rides `make check`'s
    # `audit-self-test` rather than a target nothing calls. `kit-adoption.mjs --self-test`
    # proves the same helper through its command.
    print("\nonly shrinks: the shared helper's own self-test")
    helper = _only_shrinks()
    ok(helper is not None and helper.self_test() == 0,
       "scripts/only_shrinks.py loads and its own self-test is clean")

    print("\nast readers handle the real files")
    runner = ROOT / "harness" / "run.py"
    if runner.exists():
        names = list_names_from_assign(read(runner), "TESTS")
        ok(bool(names) and "t1_id_eval" in (names or []), "TESTS list read from harness/run.py", str(names))
    main = ROOT / "cli" / "__main__.py"
    if main.exists():
        keys = dict_keys_from_assign(read(main), "COMMANDS")
        # WHAT THIS ROW IS FOR IS THE READER, NOT THE ROSTER. It pinned the exact four
        # commands until 2026-08-30, which made it a second copy of a fact
        # `harness/tests/t7_store_and_seams.py` already asserts exactly — including the "and
        # only these" half, which is the part worth having and which belongs in the test that
        # can refuse a command nobody declared. Two copies meant adding `scan` failed a check
        # whose subject is `dict_keys_from_assign`, in a file that has no opinion about what
        # commands should exist. So this asserts what it is actually testing: the reader
        # returns a non-empty list of the real keys.
        ok(
            bool(keys) and "identify" in (keys or []) and "join" in (keys or []),
            "COMMANDS read from cli/__main__.py",
            str(keys),
        )
    t3 = ROOT / "harness" / "tests" / "t3_join_coverage.py"
    if t3.exists():
        criteria = string_assign(read(t3), "PASS_CRITERIA")
        ok(
            isinstance(criteria, str) and len(criteria) > 40,
            "multi-line PASS_CRITERIA reassembled",
            repr(criteria),
        )

    print("\na check named by position is reported, per subset")
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "fake.md"
        # Built with an f-string on purpose: written as a literal, this line would be a
        # finding against this file. Same trick, same reason, as the code pattern that
        # scripts/githooks/pre-commit assembles from parts.
        doc.write_text(f"the orphan rule is check {10} here\n", encoding="utf-8")
        report = Report()
        check_positional_references(report, [doc])
        rows = {row.check: (row.severity, row.findings) for row in report.checks}
        ok(
            len(rows.get("check numbering", ("", []))[1]) == 1,
            "a positional reference in a doc is reported",
            str(rows.get("check numbering")),
        )
        ok(
            rows.get("numbering in code", ("", []))[0] == ADVISORY,
            "the code row is advisory, and the doc row is not",
            str([(row.check, row.severity) for row in report.checks]),
        )

        doc.write_text("the repo-map check owns the orphan rule\n", encoding="utf-8")
        report = Report()
        check_positional_references(report, [doc])
        # By label, not by index. This function emits two rows, so `report.checks[0]` was
        # a check identified by its position — the exact pattern D17 bans in the docs and
        # this row exists to enforce. It read `[1]` until the count row above it was
        # deleted, at which point it silently retargeted and still passed.
        by_label = {row.check: row.findings for row in report.checks}
        findings = by_label["check numbering"]
        ok(not findings, "naming the check by its label is fine", str(findings))

    # THE VERDICT FILE'S FOUR-WAY AGREEMENT. Every case here is a way for the instruction in
    # CLAUDE.md — "read `.serve/design-check.json`" — to become false with nothing else in
    # the repo noticing: the suite still passes, the config still typechecks, and the prose
    # still reads correctly. Three of the four are silent in exactly that way, which is why
    # the row exists; the fourth (a deleted reporter) is loud at Playwright startup and is
    # covered here anyway so the row cannot be half-wired.
    print("\nthe design-check verdict file is named the same in four places")
    good_reporter = "const X = 1\nexport const RESULT_FILE = resolve(REPO_ROOT, '.serve', 'design-check.json')\n"
    good_config = "export default defineConfig({\n  reporter: [['list'], ['./design-check-reporter.ts']],\n})\n"
    good_make = (
        "design-check:\n\t$(NPM_GUARD)\n\t@rm -f .serve/design-check.json\n"
        "\t@npm --prefix app run design-check\n\n"
        "design-check-quiet:\n\t$(NPM_GUARD)\n\t@rm -f .serve/design-check.json\n"
        "\t@DESIGN_CHECK_QUIET=1 npm --prefix app run design-check\n"
    )
    good_prose = "make design-check leaves .serve/design-check.json behind\n"
    ok(
        not verdict_disagreements(good_reporter, good_config, good_make, good_prose),
        "four files agreeing is clean",
        str(verdict_disagreements(good_reporter, good_config, good_make, good_prose)),
    )

    found = verdict_disagreements(good_reporter, "reporter: [['list']],\n", good_make, good_prose)
    ok(
        len(found) == 1 and "no longer names" in found[0].message,
        "a config that stopped naming the reporter is reported — the suite would go green and write nothing",
        str(found),
    )
    commented = "// design-check-reporter.ts writes the verdict\nreporter: [['list']],\n"
    found = verdict_disagreements(good_reporter, commented, good_make, good_prose)
    ok(
        len(found) == 1 and "no longer names" in found[0].message,
        "and a COMMENT naming the reporter does not satisfy it — a header that describes the "
        "wiring is not the wiring",
        str(found),
    )

    no_rm = good_make.replace("\t@rm -f .serve/design-check.json\n", "", 1)
    found = verdict_disagreements(good_reporter, good_config, no_rm, good_prose)
    ok(
        len(found) == 1 and "does not delete" in found[0].message and "design-check`" in found[0].message,
        "a recipe that stopped clearing the stale file is reported, and only that recipe",
        str(found),
    )

    late_rm = good_make.replace(
        "\t@rm -f .serve/design-check.json\n\t@npm --prefix app run design-check\n",
        "\t@npm --prefix app run design-check\n\t@rm -f .serve/design-check.json\n",
        1,
    )
    found = verdict_disagreements(good_reporter, good_config, late_rm, good_prose)
    ok(
        len(found) == 1 and "AFTER running" in found[0].message,
        "a recipe that deletes the verdict AFTER the run is a different fault and says so",
        str(found),
    )

    moved = good_reporter.replace("'design-check.json'", "'verdict.json'")
    found = verdict_disagreements(moved, good_config, good_make, good_prose)
    ok(
        any(f.where == "CLAUDE.md" for f in found),
        "a RESULT_FILE the prose does not name is reported",
        str(found),
    )
    ok(
        all("verdict.json" in f.message for f in found if f.where == "Makefile"),
        "and the Makefile arm is reconciled against the MOVED path, not a hardcoded one",
        str(found),
    )

    found = verdict_disagreements(None, good_config, good_make, good_prose)
    ok(
        len(found) == 1 and "does not exist" in found[0].message,
        "a deleted reporter is one finding about the file, not four about its readers",
        str(found),
    )
    found = verdict_disagreements("const RESULT_FILE = 'somewhere'\n", good_config, good_make, good_prose)
    ok(
        len(found) == 1 and "no `RESULT_FILE" in found[0].message,
        "a reporter whose RESULT_FILE cannot be read reports THAT, rather than an empty agreement",
        str(found),
    )
