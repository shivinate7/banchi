"""Self-test cases, code invariants rows. Called by `selftest.self_test`."""

from __future__ import annotations

import ast
import json
import re
import tempfile
from pathlib import Path

from .code_invariants import (
    _CONCURRENCY_FACTS,
    _ESTIMATE_SAMPLE,
    _compiled_assign,
    _rendered_say,
    unscoped_walk_sites,
)
from .core import EXPECTED_EMPTY, Finding, MECHANICAL, Report, Row, _sibling, exists, read
from .dispatch import check_subject_counts
from .harness_criteria import _CRITERION_BAR, _harness_claim_findings
from .hygiene import _prose_blanked
from .registry_scopes import CHECK_WORKFLOW, _SCOPE_STEP_RE, _repo_literals, browser_gate_findings
from .screens import _S9_BRACKET


def run(ok) -> None:
    print("\na figure the section merely contains is not a figure it attributes")
    # The three rows below were each green while the thing they pin was wrong. These cases are
    # the extractors that fixed them, driven on literals rather than on the live documents, so
    # a later edit to either document cannot quietly turn them back into what they were.
    _section = (
        "serves on `class CaptureServer(ThreadingHTTPServer)` with `request_queue_size = 128`\n"
        "and `CaptureHandler.timeout = 15`. `REQUEST_SLOTS = 4` is the bound, and `PHOTO_SLOTS = 4` bounds the photo lane.\n"
        "| `REQUEST_SLOTS` | 1 | 2 | 3 | **4** | 6 | 8 | 12 | 24 | 48 |\n"
    )
    for _what, _code_re, _shape, _anchor, _published in _CONCURRENCY_FACTS:
        _said = _anchor.search(_section)
        ok(_said is not None, f"the attributed form of {_what} is found", _published)
    _swapped = _section.replace("timeout = 15", "timeout = 4").replace("REQUEST_SLOTS = 4 is", "REQUEST_SLOTS = 15 is")
    ok(
        _CONCURRENCY_FACTS[1][3].search(_swapped).group(1) == "4",
        "and it reads the value beside the NAME, not the first plausible integer in the table",
        _swapped,
    )

    print("\nthe bracket ramp is resolved through section 9's own legend")
    _legend = (
        "| bracket | stops |\n| --- | --- |\n"
        "| chrome | `#FFFFFF #B8C8D8 #F2F8FF #8FA4B8` |\n"
        "| pale gold | `#FFFBEE #E8CE8A #FFFDF6 #C0A254` |\n"
    )
    _ramps = {n.strip(): v.split() for n, v in _S9_BRACKET.findall(_legend)}
    ok(sorted(_ramps) == ["chrome", "pale gold"], "both named ramps are read", str(sorted(_ramps)))
    ok(
        _ramps.get("chrome") == ["#FFFFFF", "#B8C8D8", "#F2F8FF", "#8FA4B8"],
        "and a name resolves to the four hexes it stands for, not to the word",
        str(_ramps.get("chrome")),
    )

    # THE BROWSER MATRIX'S GATE, READ BOTH WAYS (D141). The wiring reader is pure, so each
    # way the workflow could quietly stop gating is mutated into it here; the classifier is
    # imported the way `prose-guard.py` is and asked the two questions the gate exists for.
    print("\nthe browser scope's wiring is read, and each silent failure is mutated in")
    _workflow = read(CHECK_WORKFLOW) if exists(CHECK_WORKFLOW) else ""
    _gate = browser_gate_findings(_workflow)
    ok(not _gate, "the workflow as it stands reads the scope fail-open", "\n".join(m for _, m in _gate))
    _closed = _workflow.replace("outputs.run != 'false'", "outputs.run == 'true'")
    ok(any("fail-open" in m for _, m in browser_gate_findings(_closed)),
       "the fail-closed spelling `== 'true'` is refused by name")
    _gated_on = _workflow.replace("on:\n  pull_request:", "on:\n  pull_request:\n    paths: ['app/**']", 1)
    ok(any("`on:` block" in m for _, m in browser_gate_findings(_gated_on)),
       "a `paths` filter in the `on:` block, which would gate every job, is refused")
    _unwired = _SCOPE_STEP_RE.sub("python3 scripts/other.py classify", _workflow)
    ok(any("consulted by nothing" in m for _, m in browser_gate_findings(_unwired)),
       "a workflow that never runs the classifier is reported as gating nothing")
    _recording = _workflow.replace("if: github.event_name != 'push'", "if: always()")
    ok(any("skipped matrix" in m for _, m in browser_gate_findings(_recording)),
       "a pass record written for a skipped matrix is refused")
    _module = _sibling("browser-scope.py")
    ok(_module is not None, "scripts/browser-scope.py imports")
    if _module is not None:
        _read = lambda side, path: None  # noqa: E731 - no recipe is consulted by these paths
        ok(not _module.classify_paths(["docs/decisions/"], _read).run, "a docs-only change skips")
        ok(_module.classify_paths(["app/src/App.tsx"], _read).run, "a screen change runs")
    _code = "const T = {\n  'harness/traces/x.json': 1,\n} // docs/debts/\n"
    ok(_repo_literals(_code, {"harness/traces/x.json", "docs/debts/"}) == ["harness/traces/x.json"],
       "a code string naming a tracked file is a dependency and a comment naming one is not")

    # A ROW THAT EXAMINED NOTHING IS NOT A ROW THAT PASSED. Driven over a synthetic report,
    # because the thing under test is the REPORTING LAYER and a real run cannot pose a row
    # with no subject without breaking a walk. Every arm here is a state the file printed
    # `ok` for before 2026-09-12.
    print("\na row that examined nothing does not print the word a row that examined everything does")

    # ROWS BUILT AS `Row`, NEVER THROUGH `report.add`. `defined_checks` marks any
    # module-level function that emits a row AS A CHECK, deliberately and by union — so a
    # `report.add` anywhere in `self_test` makes `check dispatch` report `self_test` as an
    # undispatched check. Measured, one edit after that row was extended. Appending the
    # tuple is also the more honest fixture: it poses the report a check would leave.
    def _subject(rows, staged=False, drop=""):
        report = Report()
        posed = {check for check, _, _ in rows}
        # Every pinned name present, so the stale-pin leg is satisfied and the arm under
        # test is the only thing being read. `drop` omits one, which is how the stale-pin
        # arm is posed.
        for name in EXPECTED_EMPTY:
            if name not in posed and name != drop:
                report.checks.append(Row(name, MECHANICAL, [], "", 1))
        for check, findings, scanned in rows:
            report.checks.append(Row(check, MECHANICAL, findings, "", scanned))
        check_subject_counts(report, staged)
        return {row.check: row.findings for row in report.checks}["subject counts"]

    _pinned = next(n for n, (when, _) in EXPECTED_EMPTY.items() if when == "always")
    _staged_pin = next(n for n, (when, _) in EXPECTED_EMPTY.items() if when == "staged")
    ok(not _subject([("paths", [], 2964)]), "a row with subjects and no findings is clean")
    ok(any("declared no subject count" in m for _, m in _subject([("paths", [], None)])),
       "a row that declared no subject count is a finding, not an ok")
    ok(any("examined NOTHING" in m for _, m in _subject([("unpinned row", [], 0)])),
       "an UNPINNED row that examined nothing is a finding")
    ok(not _subject([(_pinned, [], 0)]),
       f"a row pinned expected-empty ({_pinned}) may examine nothing")
    ok(any("examined nothing in a FULL run" in m
           for _, m in _subject([(_staged_pin, [], 0)], staged=False))
       and not _subject([(_staged_pin, [], 0)], staged=True),
       "a `staged` pin permits zero under --staged and refuses it in a full run")
    ok(any("no row by that name was emitted" in m
           for _, m in _subject([(_pinned + "-renamed", [], 1)], drop=_pinned)),
       "a pin naming a row the file no longer emits is reported stale")
    ok(not _subject([("with findings", [Finding("x", "y")], 0)]),
       "a row WITH findings is judged on the findings, never on an empty subject")
    _rendered = Report()
    _rendered.checks.append(Row("zero", MECHANICAL, [], "a summary", 0))
    _rendered.checks.append(Row("some", MECHANICAL, [], "a summary", 7))
    _rendered.checks.append(Row("bare", MECHANICAL, [], "a summary", None))
    ok("none zero" in re.sub(r"\s+", " ", _rendered.render()),
       "the render prints `none` for an empty subject")
    ok("ok   some" in _rendered.render(), "and `ok` where there was one")
    ok("bare bare" in re.sub(r"\s+", " ", _rendered.render()),
       "and `bare` where no count was declared")
    ok(json.loads(_rendered.as_json(0))["rows"][0]["vacuous"] is True
       and json.loads(_rendered.as_json(0))["rows"][1]["vacuous"] is False,
       "--json carries the integer and the flag, so nothing parses the render")

    # A DELETION NARRATED IN PROSE IS NOT A RESURRECTION, and `capture_server.py` narrates
    # one. The classifier is what keeps the row off it, so it is exercised here directly.
    print("\na deleted symbol in a comment is the record of the deletion; in code it is the defect")
    _py = 'def f():\n    """Mentions Ghost in a docstring."""\n    # Ghost in a comment\n    return 1\n'
    ok("Ghost" not in _prose_blanked(Path("x.py"), _py),
       "a Python docstring and a comment are both blanked")
    ok("Ghost" in _prose_blanked(Path("x.py"), 'Ghost = 1\n# Ghost\n'),
       "and an assignment to the same name survives")
    ok(_prose_blanked(Path("x.py"), _py).count("\n") == _py.count("\n"),
       "offsets survive, so a reported line number is the real one")
    ok("Ghost" not in _prose_blanked(Path("x.ts"), "/* Ghost */\nconst a = 1\n"),
       "a TypeScript block comment is blanked too")
    ok("Ghost" in _prose_blanked(Path("x.ts"), "const Ghost = 1 /* gone */\n"),
       "and a declaration beside one survives")

    # THE MONEY BUTTON'S FIGURE, over source strings rather than the tree, so the two
    # readers are proved before the row is trusted to compare with them.
    print("\nthe money button's figure is read from the call, never from the wording")
    _reader = ast.parse('import re\n_E = re.compile(r"^cost\\s+\\$([0-9.]+)\\s*$", re.M)\n')
    ok(_compiled_assign(_reader, "_E") == ("^cost\\s+\\$([0-9.]+)\\s*$", re.M),
       "a module-level re.compile is read with its multiline flag")
    ok(_compiled_assign(_reader, "_MISSING") is None, "and a name that is not there is None")
    _writer = ast.parse('say(f"cost  ${_estimate(x)}")\nsay(f"other  ${bill(x)}")\n')
    ok(_rendered_say(_writer, "_estimate") == f"cost  ${_ESTIMATE_SAMPLE}",
       "the line a say() whose f-string calls the producer would print is rendered")
    ok(_rendered_say(_writer, "bill") == f"other  ${_ESTIMATE_SAMPLE}",
       "and the sibling line is a different subject, not the same one")
    ok(_rendered_say(ast.parse('say("cost  $0.00")\n'), "_estimate") is None,
       "a line that no longer calls the producer is reported absent rather than matched")

    print("\na published gate threshold is compared as a number")
    ok(_CRITERION_BAR.search("holdout_accuracy >= 0.95").group(2) == "0.95",
       "the floor is lifted out of the criterion's own comparison")
    ok(_CRITERION_BAR.search("holdout_accuracy > 0.9").group(1) == ">",
       "and the operator with it, so `>` is not read as `>=`")
    ok(_CRITERION_BAR.search("holdout_accuracy is high") is None,
       "a criterion with no comparison is unreadable rather than guessed at")

    print("\nevery published harness count is the length of TESTS")
    # THE AGREEING SET IS THE REGISTERED ONE AND IT HAS A HOLE IN IT. T10 belongs to the
    # shelved IMB encoder (DEBT26) and this repo renumbers its own ids and never another
    # branch's, so `TESTS` runs T1-T9 and T11 — ten registered, highest 11. Spelling the set
    # as a contiguous range would quietly assert a contiguity the tree does not have, and
    # this arm is exactly where that assumption would hide.
    ok(not _harness_claim_findings({f"T{n}" for n in list(range(1, 10)) + [11]}),
       "ten registered, highest eleven, against a tree that publishes both")
    ok(any("registers 9" in m for _, m in _harness_claim_findings({f"T{n}" for n in range(1, 10)})),
       "nine registered is a finding against every one of the published counts")
    ok(not _harness_claim_findings(set()),
       "and an unreadable TESTS yields nothing here — `harness tests` own legs say so instead")

    print("\nunscoped walk: the matcher, against synthetic fixtures")
    with tempfile.TemporaryDirectory() as tmp:
        # Arm (a): a NEW unscoped call must be found and reported as not-on-the-allowlist.
        fixture = Path(tmp) / "fixture_new_site.py"
        fixture.write_text(
            "def do_something_new():\n"
            "    inventory = Store().read().inventory\n"
            "    for card in inventory.cards.values():\n"
            "        touch(card)\n",
            encoding="utf-8",
        )
        sites = unscoped_walk_sites([fixture])
        ok(
            any(fname == "do_something_new" and shape == "values"
                for _, _, fname, shape in sites),
            "a new `.values()` call on `inventory.cards` is found by the scanner",
            str(sites),
        )

        # Arm (b): a call the scanner does NOT recognise as unscoped — a filtered
        # `select(...)` with a keyword — must not appear, proving the keyword check
        # actually narrows `select` and does not just always fire.
        fixture2 = Path(tmp) / "fixture_scoped_select.py"
        fixture2.write_text(
            "def do_scoped():\n"
            "    for key, row in inventory.cards.select((\"box\",), box=3):\n"
            "        touch(row)\n",
            encoding="utf-8",
        )
        sites2 = unscoped_walk_sites([fixture2])
        ok(
            not sites2,
            "a `select(...)` called WITH a filter keyword is never flagged",
            str(sites2),
        )

        # Arm (c): `to_payload()` is only flagged on something that looks like an
        # Inventory — a differently-typed object's `to_payload()` must not match, proving
        # the guard does not simply grep the method name across the whole file.
        fixture3 = Path(tmp) / "fixture_other_to_payload.py"
        fixture3.write_text(
            "def do_other():\n"
            "    book = load_corpus()\n"
            "    return book.to_payload()\n",
            encoding="utf-8",
        )
        sites3 = unscoped_walk_sites([fixture3])
        ok(
            not sites3,
            "`book.to_payload()` (not an Inventory) is never flagged",
            str(sites3),
        )
