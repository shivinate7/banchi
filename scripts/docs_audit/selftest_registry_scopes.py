"""Self-test cases, registry scopes rows. Called by `selftest.self_test`."""

from __future__ import annotations

import contextlib
import io
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from .core import (
    EXIT_USAGE,
    MECHANICAL,
    Finding,
    ROOT,
    Report,
    _strip_ts_comments,
    entry_parser,
    module_globals,
    rel,
)
from .dispatch import UNDISPATCHED, check_dispatch
from .env_map import _consumer_block, _map_sections
from .hygiene import ROSTER_MARK, ROUTE_HASH, _balanced, expected_rosters
from . import registry_scopes
from .registry_scopes import INVOKERS, check_audit_invocation, check_check_registry


def run(ok) -> None:
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            entry_parser().parse_args(["--no-such-flag"])
        code: Optional[int] = None
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else None
    ok(code == EXIT_USAGE, f"an unknown flag exits {EXIT_USAGE}, never 2", f"exited {code}")
    report = Report()
    check_audit_invocation(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(not by_label["audit invocation"], "every caller's flags are declared", str(by_label))

    # The reason this check asks argparse instead of reading a list out of it: argparse
    # accepts unambiguous abbreviations, so a caller passing `--stag` really does run and
    # is not a finding. Set membership against the declared options called it one.
    with tempfile.TemporaryDirectory() as tmp:
        caller = Path(tmp) / "caller.sh"
        caller.write_text("python3 scripts/docs-audit.py --stag\n", encoding="utf-8")
        saved, INVOKERS[:] = list(INVOKERS), [rel(caller)]
        try:
            report = Report()
            check_audit_invocation(report)
            rows = {row.check: row.findings for row in report.checks}
            ok(
                not rows["audit invocation"],
                "an abbreviation argparse accepts is not a finding",
                str(rows["audit invocation"]),
            )
            caller.write_text("python3 scripts/docs-audit.py --stagx\n", encoding="utf-8")
            report = Report()
            check_audit_invocation(report)
            rows = {row.check: row.findings for row in report.checks}
            ok(
                len(rows["audit invocation"]) == 1,
                "a flag argparse rejects is",
                str(rows["audit invocation"]),
            )
        finally:
            INVOKERS[:] = saved

    # A registry file that is absent must be a red row with a summary, never a crash.
    saved_registry = registry_scopes.CHECKS_REGISTRY
    registry_scopes.CHECKS_REGISTRY = Path(tempfile.gettempdir()) / "no-such-checks-registry.py"
    try:
        report = Report()
        check_check_registry(report)
        rows = [row for row in report.checks if row.check == "check registry"]
        ok(
            len(rows) == 1 and rows[0].severity == MECHANICAL and bool(rows[0].findings)
            and bool(rows[0].summary),
            "a missing checks registry is a red row with a summary, not a crash",
            str(rows),
        )
    except Exception as exc:  # the old code raised here
        ok(False, "a missing checks registry is a red row with a summary, not a crash", repr(exc))
    finally:
        registry_scopes.CHECKS_REGISTRY = saved_registry

    # A check that is defined and never dispatched prints nothing at all, so this row is the
    # only one whose failure mode is an ABSENT row. Every case below is a way for the
    # reconciliation to look like it ran: a reader that cannot see a loop, a check renamed
    # out of the prefix, an exemption nobody re-read.
    print("\nthe route-roster reader survives the shapes the specs actually take")
    # THE `[number]` CASE IS HERE BECAUSE IT SHIPPED BROKEN FOR ONE RUN. `Record<(typeof
    # RING)[number], string>` puts a bracket in the TYPE, and a reader that took the first
    # bracket after the marker read `[number]`, found no routes in it, and reported "you
    # pinned nothing" — a finding that is not what is wrong and that nobody could act on.
    # A reader that reports the wrong defect is worse than one that reports none, because
    # the first thing a person does with it is stop believing the row.
    shaped = (
        "/* ROUTE-ROSTER hotkey */\n"
        "const RING = [\n  '#/',\n  '#/runs',\n] as const\n"
        "/* ROUTE-ROSTER all */\n"
        "const VIEW: Record<(typeof RING)[number], string> = {\n"
        "  '#/': 'main.capture',\n  '#/codes': 'main.codes',\n}\n"
    )
    marks = list(ROSTER_MARK.finditer(shaped))
    ok(len(marks) == 2, "two markers in one file are both found", f"found {len(marks)}")
    read_back = []
    for mark in marks:
        assign = shaped.find("=", mark.end())
        opening = min(
            (found for found in (shaped.find(bracket, assign) for bracket in "[{") if found != -1),
            default=-1,
        )
        read_back.append(ROUTE_HASH.findall(_strip_ts_comments(_balanced(shaped, opening))))
    ok(read_back[0] == ["#/", "#/runs"], "an array roster reads in order", str(read_back[0]))
    ok(
        read_back[1] == ["#/", "#/codes"],
        "an object roster reads its KEYS, past a `[number]` in the type",
        str(read_back[1]),
    )

    # A route named in prose is not a route the file pins. Both specs discuss routes they
    # deliberately do not walk, and counting those would fire the "declare a roster" arm at
    # a file that is behaving.
    ok(
        ROUTE_HASH.findall(_strip_ts_comments("// the ring cannot reach '#/gallery'\nopen('/#/runs')"))
        == ["#/runs"],
        "a route named in a comment is not counted as pinned",
    )

    # The live table, read the way the check reads it. An extractor that silently returns
    # nothing would make every roster below it "missing everything" — loud, but wrong about
    # which side moved.
    live, live_findings = expected_rosters()
    ok(
        bool(live.get("all")) and live["all"][0] == "#/",
        "App.tsx's ROUTES table is readable and starts at the capture screen",
        f"{live.get('all')} / {[f.message for f in live_findings]}",
    )
    ok(
        set(live.get("hotkey", [])) <= set(live.get("all", [])) and live.get("hotkey") != live.get("all"),
        "the hotkey ring is a proper subset of the registered routes",
        f"ring {live.get('hotkey')} of {live.get('all')}",
    )

    print("\nevery check defined is reconciled against the ones audit() calls")
    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp) / "fixture.py"

        def dispatch(source: str, exempt: Optional[Dict[str, str]] = None) -> List[Finding]:
            fixture.write_text(source, encoding="utf-8")
            saved_exempt = dict(UNDISPATCHED)
            UNDISPATCHED.clear()
            UNDISPATCHED.update(exempt or {})
            try:
                report = Report()
                check_dispatch(report, fixture)
                return {row.check: row.findings for row in report.checks}["check dispatch"]
            finally:
                UNDISPATCHED.clear()
                UNDISPATCHED.update(saved_exempt)

        emit = "def {0}(report):\n    report.add('{0}', 'mechanical', [])\n\n"
        wired = (
            emit.format("check_one")
            + emit.format("check_two")
            + "def audit():\n    report = Report()\n    check_one(report)\n    check_two(report)\n"
        )
        ok(not dispatch(wired), "two checks defined, both called, is clean", str(dispatch(wired)))

        forgotten = wired.replace("    check_two(report)\n", "")
        found = dispatch(forgotten)
        ok(
            len(found) == 1 and "check_two" in found[0].message,
            "the one whose call was forgotten is named, and only it",
            str(found),
        )
        ok(
            not dispatch(forgotten, {"check_two": "deliberately not run"}),
            "an UNDISPATCHED entry accounts for it — the loud escape route",
            str(dispatch(forgotten, {"check_two": "deliberately not run"})),
        )
        found = dispatch(wired, {"check_two": "stale reason"})
        ok(
            len(found) == 1 and "check_two" in found[0].message,
            "and the entry is reported the moment audit() calls it after all",
            str(found),
        )
        found = dispatch(wired, {"check_ghost": "renamed away"})
        ok(
            len(found) == 1 and "check_ghost" in found[0].message,
            "an entry naming nothing defined here is dangling, so the list cannot only grow",
            str(found),
        )

        # Dispatch through a loop: the exact restructuring whose halfway version defeated the
        # retired statement-reading registry. A name is a name wherever it appears.
        looped = (
            emit.format("check_one")
            + emit.format("check_two")
            + "def audit():\n    report = Report()\n"
            + "    for run in (check_one, check_two):\n        run(report)\n"
        )
        ok(not dispatch(looped), "dispatch through a loop is dispatch", str(dispatch(looped)))

        # The shape `rows.py` really has: a `ROWS` table of entries, no `audit()` naming a check.
        tabled = (
            emit.format("check_one")
            + emit.format("check_two")
            + "ROWS = (\n    Row('one', 1, check_one),\n    Row('two', 1, check_two),\n)\n"
        )
        ok(not dispatch(tabled), "a check named in the ROWS table is dispatched", str(dispatch(tabled)))
        found = dispatch(tabled.replace("    Row('two', 1, check_two),\n", ""))
        ok(
            len(found) == 1 and "check_two" in found[0].message,
            "the check whose ROWS entry was forgotten is named, and only it",
            str(found),
        )

        # The rename hole, closed by reading both signals. `audit_two` emits a row and no
        # longer looks like a check by name — which is what a diff that reads as tidying does.
        renamed = (
            emit.format("check_one")
            + emit.format("audit_two")
            + "def audit():\n    report = Report()\n    check_one(report)\n"
        )
        found = dispatch(renamed)
        ok(
            len(found) == 1 and "audit_two" in found[0].message,
            "a check renamed out of the prefix still emits a row, and is still found",
            str(found),
        )

        moved = (
            emit.format("check_one")
            + "CHECKS = (check_one,)\n\n"
            + "def audit():\n    report = Report()\n    for run in CHECKS:\n        run(report)\n"
        )
        found = dispatch(moved)
        ok(
            len(found) == 1 and "none of the checks" in found[0].message,
            "dispatch moved out of audit() is one finding about the reader, not one per check",
            str(found),
        )
        found = dispatch(emit.format("check_one"))
        ok(
            len(found) == 1 and "no `audit()`" in found[0].message,
            "a file with no audit() at all says so, rather than reporting every check unrun",
            str(found),
        )
        found = dispatch("def audit(:\n")
        ok(
            len(found) == 1 and "cannot be parsed" in found[0].message,
            "and a source that will not parse is a finding, not an empty roster",
            str(found),
        )

    # `route census` is CUT (test-audit plan Q2, 2026-09-28): it reconciled a hand-typed
    # route/screen count against ROUTES, and the count it watched is now deleted from
    # prose rather than kept in step. Its helpers (`_bridge_literals`, `_census_pattern`,
    # `_route_personas`, `_census_text`) go with it.

    # THE CONSUMER BLOCK IS A TWO-COLUMN LAYOUT AND A SEPARATOR-BASED READER GOT IT WRONG
    # TWICE, in opposite directions: a wrapped description ended the block after one entry,
    # and the longest path in it is separated from its description by a SINGLE space, so a
    # `\s{2,}` split dropped that row too. Both misreads made a correct docstring fail.
    print("\nthe map's consumer list is read by column, not by separator")
    _saved = module_globals()["MAP"]
    try:
        sample = ROOT / "docs" / "map.py"
        module_globals()["MAP"] = sample
        word, rows = _consumer_block()
        ok(word == "four", "the declared count word is read", str(word))
        ok(len(rows) == 4, "all four rows are found, wrapped descriptions and all", str(rows))
        ok(
            "scripts/decision-context.py" in rows,
            "including the row whose path leaves a single space before its description",
            str(rows),
        )
        ok(
            "you, or an agent" in rows,
            "and the one entry that is a phrase with spaces in it, not a path",
            str(rows),
        )
        ok("TRACKS" in _map_sections(), "TRACKS is a section this check can see", str(_map_sections()))
    finally:
        module_globals()["MAP"] = _saved
