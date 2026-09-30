"""Self-test cases, code invariants rows, part 2. Called by `selftest.self_test`."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .core import module_globals
from .code_invariants import _pipeline_imports, check_import_layering, check_unscoped_walk
from .core import ADVISORY, MECHANICAL, Report
from .dispatch import check_dispatch
from .strings import (
    APP_TS_COMPILER,
    UNKNOWN_NO_TOOLCHAIN,
    _no_mechanism_findings,
    _run_user_strings,
    _user_strings_toolchain_missing,
    check_no_mechanism_on_screen,
    check_typed_interpunct,
)


def run(ok) -> None:
    print("\nunscoped walk: the row itself, against the two failure shapes item 1's spec names")

    # These three arms call `check_unscoped_walk(report)` ITSELF, with the module globals
    # it reads patched for the duration — the same save/patch/restore-in-`finally` shape
    # used above for `MAP`. Driving only `unscoped_walk_sites` (the pure matcher) and the
    # comparison arithmetic inline, as the first draft of this block did, proved nothing
    # about the ROW: `check_unscoped_walk` walks the REAL `_UNSCOPED_WALK_ROOTS` regardless
    # of what a fixture computes, so a mutation that broke the row's own comparison loops
    # (e.g. `for path, fname, shape in ():` in place of `sorted(allowed)`, or `if False:`
    # in place of the not-on-the-allowlist test) left every arm below green. Calling the
    # row function directly is what closes that gap.

    # Arm (d): a site not on the allowlist fails the ROW. `_UNSCOPED_WALK_SINGLE_FILES` is
    # patched to add one fixture file the real scan would not otherwise see.
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp) / "fixture_new_site.py"
        fixture.write_text(
            "def do_something_new():\n"
            "    for card in inventory.cards.values():\n"
            "        touch(card)\n",
            encoding="utf-8",
        )
        _saved_files = module_globals()["_UNSCOPED_WALK_SINGLE_FILES"]
        try:
            module_globals()["_UNSCOPED_WALK_SINGLE_FILES"] = _saved_files + (fixture,)
            report = Report()
            check_unscoped_walk(report)
        finally:
            module_globals()["_UNSCOPED_WALK_SINGLE_FILES"] = _saved_files
        by_label = {row.check: row.findings for row in report.checks}
        ok(
            any("do_something_new" in f.message for f in by_label["unscoped walk"]),
            "a site absent from UNSCOPED_WALK_ALLOWED fails the row, naming the function",
            str(by_label["unscoped walk"]),
        )

    # Arm (e): an allowlist entry naming a site the tree no longer has fails the ROW as
    # stale — the "removed site not removed from the list" failure item 1's spec text
    # calls out by name. `UNSCOPED_WALK_ALLOWED`/`UNSCOPED_WALK_EXPECTED` are patched
    # together (adding one entry the real tree does not have, and raising the pinned
    # count to match, so this arm isolates the stale-entry branch from the count-mismatch
    # branch below).
    _saved_allowed = module_globals()["UNSCOPED_WALK_ALLOWED"]
    _saved_expected = module_globals()["UNSCOPED_WALK_EXPECTED"]
    try:
        module_globals()["UNSCOPED_WALK_ALLOWED"] = _saved_allowed | {
            ("server/capture_server.py", "no_such_function", "values"),
        }
        module_globals()["UNSCOPED_WALK_EXPECTED"] = _saved_expected + 1
        report = Report()
        check_unscoped_walk(report)
    finally:
        module_globals()["UNSCOPED_WALK_ALLOWED"] = _saved_allowed
        module_globals()["UNSCOPED_WALK_EXPECTED"] = _saved_expected
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        any("no_such_function" in f.message for f in by_label["unscoped walk"]),
        "an allowlist entry the scan does not find fails the row, naming the function",
        str(by_label["unscoped walk"]),
    )

    # Arm (f'): the pinned-count mismatch fails the ROW on its own, with no other change —
    # `UNSCOPED_WALK_EXPECTED` alone disagreeing with `len(UNSCOPED_WALK_ALLOWED)`.
    _saved_expected = module_globals()["UNSCOPED_WALK_EXPECTED"]
    try:
        module_globals()["UNSCOPED_WALK_EXPECTED"] = _saved_expected + 1
        report = Report()
        check_unscoped_walk(report)
    finally:
        module_globals()["UNSCOPED_WALK_EXPECTED"] = _saved_expected
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        any("UNSCOPED_WALK_ALLOWED" in f.where and "pinned" in f.message
            for f in by_label["unscoped walk"]),
        "UNSCOPED_WALK_EXPECTED disagreeing with the allowlist's length fails the row",
        str(by_label["unscoped walk"]),
    )

    # Arm (f): end-to-end proof against the REAL tree, unpatched — the row itself, not
    # just the comparison logic, reports clean on a clean checkout. This is Step 5's
    # optional end-to-end check, folded in as its own arm rather than left as a manual
    # Measure step.
    report = Report()
    check_unscoped_walk(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label["unscoped walk"],
        "the real tree, scanned end to end, has zero findings on this row",
        str(by_label["unscoped walk"]),
    )

    # `import layering` (D63): a lazy `from pipeline import x` inside
    # a function body must be caught the same as a module-level one — that shape is exactly
    # how the real defect shipped (`store/db.py:_add_search_index`, several hundred lines
    # in, invisible to a top-of-file reader).
    print("\nimport layering: store/ importing pipeline/ is caught, module-level or lazy")
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp) / "fixture_lazy_import.py"
        fixture.write_text(
            "def _add_something(conn):\n"
            "    from pipeline import join as _join\n"
            "    return _join.join_key('1', '2')\n",
            encoding="utf-8",
        )
        findings = _pipeline_imports(fixture)
        ok(
            any("from pipeline import" in spelling for _, spelling in findings),
            "a lazy `from pipeline import x` inside a def is found by the scanner",
            str(findings),
        )

        clean = Path(tmp) / "fixture_no_pipeline.py"
        clean.write_text(
            "from store.numbers import join_key\n\n\ndef f():\n    return join_key('1', '2')\n",
            encoding="utf-8",
        )
        ok(
            not _pipeline_imports(clean),
            "a file that imports nothing from pipeline/ is not flagged",
            str(_pipeline_imports(clean)),
        )

        report = Report()
        _saved_walk = module_globals()["_walk"]
        try:
            module_globals()["_walk"] = lambda root, suffixes: [fixture]
            check_import_layering(report)
        finally:
            module_globals()["_walk"] = _saved_walk
        by_label = {row.check: row.findings for row in report.checks}
        ok(
            any("pipeline" in f.message and "D63" in f.message
                for f in by_label["import layering"]),
            "the row itself fails on a fixture tree, citing D63",
            str(by_label["import layering"]),
        )

    report = Report()
    check_import_layering(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label["import layering"],
        "the real store/ tree, scanned end to end, imports nothing from pipeline/",
        str(by_label["import layering"]),
    )

    report = Report()
    check_dispatch(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label["check dispatch"],
        "this file's own checks are every one of them called by audit()",
        str(by_label["check dispatch"]),
    )

    print("\nno mechanism on screen: the extractor and the word list, over throwaway fixtures")
    with tempfile.TemporaryDirectory() as tmp_name:
        fixture_dir = Path(tmp_name)

        def written(name: str, body: str) -> Path:
            path = fixture_dir / name
            path.write_text(body)
            return path

        written(
            "Positive.tsx",
            "export function Positive() {\n"
            "  return <p>Held back for a reason (D134).</p>\n"
            "}\n",
        )
        written(
            "Comment.tsx",
            "// This screen used to cite (D134) here; it does not any more.\n"
            "/* the same token, (D134), inside a block comment */\n"
            "export function Comment() {\n"
            "  return <p>Held back for a reason.</p>\n"
            "}\n",
        )
        written(
            "DataAttr.tsx",
            "export function DataAttr() {\n"
            '  return <div data-decision="D134">Held back for a reason.</div>\n'
            "}\n",
        )
        written(
            "Jargon.tsx",
            "export function Jargon() {\n"
            "  return <p>Waiting on the pipeline to answer.</p>\n"
            "}\n",
        )
        written(
            "Path.tsx",
            "export function PathHit() {\n"
            "  return <p>See inventory/prices.json for the answer.</p>\n"
            "}\n",
        )
        written(
            "CsvName.tsx",
            "export function CsvName() {\n"
            "  return <a download=\"import.csv\">import.csv</a>\n"
            "}\n",
        )
        written(
            "Toast.tsx",
            "import { toast } from './kit/toast'\n"
            "export function fireToast() {\n"
            "  toast({ kind: 'ok', title: 'Sent to the corpus' })\n"
            "}\n",
        )
        written(
            "NoticeCode.tsx",
            "export function NoticeCode() {\n"
            "  return <Notice code=\"the corpus refused it\">Held back.</Notice>\n"
            "}\n",
        )
        written(
            "OperatorWords.tsx",
            "export function OperatorWords() {\n"
            "  return <p>3 copies across 2 boxes, from this run's export, still listed.</p>\n"
            "}\n",
        )
        written(
            "Gallery.tsx",
            "export function Gallery() {\n"
            "  return <p>Generated by scripts/build-mark.mjs from docs/specs/logo.md — the "
            "pipeline never touches this file.</p>\n"
            "}\n",
        )
        written(
            "Fulfillment.tsx",
            "export function Fulfillment() {\n"
            "  return <p>Waiting on the pipeline to answer.</p>\n"
            "}\n",
        )
        written(
            "CliInvocation.tsx",
            "export function CliInvocation() {\n"
            "  return <span title=\"Run `pkmnscan rescue` to rebind it.\">stranded</span>\n"
            "}\n",
        )
        written(
            "PullConfirm.tsx",
            "export function PullConfirm() {\n"
            "  return <p>Waiting on the pipeline to answer.</p>\n"
            "}\n",
        )

        # THE UNKNOWN PATH: absent toolchain is ADVISORY, a present-but-broken one stays MECHANICAL.
        _saved = (APP_TS_COMPILER, _run_user_strings, _user_strings_toolchain_missing)
        try:
            for _row_fn, _name in ((check_no_mechanism_on_screen, "no mechanism on screen"),
                                   (check_typed_interpunct, "typed interpunct")):
                module_globals()["APP_TS_COMPILER"] = fixture_dir / "absent" / "typescript.js"
                _r = Report()
                _row_fn(_r)
                _row = [c for c in _r.checks if c.check == _name][0]
                ok(_row.severity == ADVISORY and UNKNOWN_NO_TOOLCHAIN in _row.findings[0].message,
                   f"{_name}: an absent toolchain is ADVISORY unknown, never MECHANICAL")
                module_globals()["APP_TS_COMPILER"] = _saved[0]
                module_globals()["_run_user_strings"] = lambda _a: None
                module_globals()["_user_strings_toolchain_missing"] = lambda: False
                _r = Report()
                _row_fn(_r)
                _row = [c for c in _r.checks if c.check == _name][0]
                ok(_row.severity == MECHANICAL and UNKNOWN_NO_TOOLCHAIN not in _row.findings[0].message,
                   f"{_name}: a present toolchain that fails stays MECHANICAL")
                module_globals()["_run_user_strings"] = _saved[1]
                module_globals()["_user_strings_toolchain_missing"] = _saved[2]
        finally:
            (module_globals()["APP_TS_COMPILER"], module_globals()["_run_user_strings"],
             module_globals()["_user_strings_toolchain_missing"]) = _saved

        strings = _run_user_strings(["--dir", str(fixture_dir)])
        ok(strings is not None, "the extractor runs over a throwaway fixture tree",
           "node or app/node_modules/typescript unavailable — install and re-run")
        if strings is not None:
            findings, _used = _no_mechanism_findings(strings)
            hit_files = {f.where.split(":")[0].split("/")[-1] for f in findings}
            ok("Positive.tsx" in hit_files,
               "a decision citation in JSX text is caught")
            ok("Comment.tsx" not in hit_files,
               "the same token inside a comment is not — a comment is trivia, never a JsxText node")
            ok("DataAttr.tsx" not in hit_files,
               "a decision cite in a `data-*` attribute is not — that attribute name is not tracked")
            ok("Jargon.tsx" in hit_files,
               "a forbidden pipeline-internal noun in JSX text is caught")
            ok("Path.tsx" in hit_files,
               "a repository path in JSX text is caught")
            ok("CsvName.tsx" not in hit_files,
               "a bare `.csv` filename with no directory — a download's own name — is exempt")
            ok("Toast.tsx" in hit_files,
               "`toast({ title: … })` carrying a forbidden noun is caught")
            ok("NoticeCode.tsx" not in hit_files,
               "`Notice`'s own `code` prop is the one exempted channel (CLAUDE.md's Register "
               "paragraph) and is never extracted")
            ok("OperatorWords.tsx" not in hit_files,
               "run/box/export/listing — the operator's own words — trip nothing")
            ok("Gallery.tsx" not in hit_files,
               "the kit sheet is exempt BY NAME — it documents the kit to a builder, not the "
               "product to an operator")
            ok("Fulfillment.tsx" in hit_files,
               "the Fulfiller's own screen is NOT exempt — a real person reads it while working")
            ok("PullConfirm.tsx" in hit_files,
               "the pull-confirm screen is NOT exempt, for the same reason")
            ok("CliInvocation.tsx" in hit_files,
               "a backticked `pkmnscan …` invocation is caught — `Pricing.tsx:4468`'s own "
               "defect before D210, and the row had no key for it")
