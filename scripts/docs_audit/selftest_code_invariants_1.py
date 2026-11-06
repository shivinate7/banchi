"""Self-test cases, code invariants rows, part 1. Called by `selftest.self_test`."""

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
from .registry_scopes import CHECK_WORKFLOW, _SCOPE_STEP_RE, _repo_literals, _yaml_job_block, browser_gate_findings
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
    # A mutant equal to the original is a no-op, and a no-op reads as a gate miss. Name it instead.
    def _mutant(text: str, label: str) -> str:
        ok(text != _workflow, f"the {label} mutation changes the workflow it mutates")
        return text

    _closed = _mutant(_workflow.replace("outputs.run != 'false'", "outputs.run == 'true'"), "fail-closed")
    ok(any("fail-open" in m for _, m in browser_gate_findings(_closed)),
       "the fail-closed spelling `== 'true'` is refused by name")
    # Anchored on the `  pull_request:` key of the `on:` block, so a comment between them does not matter.
    _gated_on = _mutant(
        re.sub(r"^(on:\n(?:[ \t]+#.*\n)*  pull_request:\n)", r"\1    paths: ['app/**']\n", _workflow, count=1, flags=re.M),
        "`paths` filter")
    ok(any("`on:` block" in m for _, m in browser_gate_findings(_gated_on)),
       "a `paths` filter in the `on:` block, which would gate every job, is refused")
    _unwired = _mutant(_SCOPE_STEP_RE.sub("python3 scripts/other.py classify", _workflow), "unwired classifier")
    ok(any("consulted by nothing" in m for _, m in browser_gate_findings(_unwired)),
       "a workflow that never runs the classifier is reported as gating nothing")
    # Anchored on the `if:` line of the `design-check-passed` job, found by the reader's own
    # job helper, so a reworded condition does not break the mutation.
    _passed = _yaml_job_block(_workflow, "design-check-passed") or ""
    _recording = _mutant(
        _workflow.replace(_passed, re.sub(r"^([ \t]*if:).*$", r"\1 always()", _passed, count=1, flags=re.M), 1),
        "recording guard")
    ok(any("skipped matrix" in m for _, m in browser_gate_findings(_recording)),
       "a pass record written for a skipped matrix is refused")

    # THE GATE, READ STEP BY STEP. The gate is `design-check`'s first step, and every later step
    # reads its answer. Each mutation below changes ONE thing the gate depends on, inside one job
    # only, and asserts the finding that names it. `_in_job` keeps the change in that job's block.
    print("\nthe design-check gate is read step by step, and each way it could stop gating is a finding")

    def _in_job(job_name: str, old: str, new: str, label: str) -> str:
        block = _yaml_job_block(_workflow, job_name) or ""
        return _mutant(_workflow.replace(block, block.replace(old, new, 1), 1), label)

    _gate_closed = _in_job(
        "design-check",
        "RUN: ${{ needs.already-passed.outputs.skip != 'true' && needs.browser-scope.outputs.run != 'false'",
        "RUN: ${{ needs.already-passed.outputs.skip != 'true' && needs.browser-scope.outputs.run == 'true'",
        "fail-closed spelling in the gate step",
    )
    ok(any("gate step does not read `needs.browser-scope.outputs.run != 'false'`" in m
           for _, m in browser_gate_findings(_gate_closed)),
       "the fail-closed spelling in the gate step is refused by name")
    _no_always = _in_job(
        "design-check",
        "if: ${{ always() && !github.event.pull_request.draft }}",
        "if: ${{ !github.event.pull_request.draft }}",
        "design-check job-level if without always()",
    )
    ok(any("job-level `if:` has no `always()`" in m for _, m in browser_gate_findings(_no_always)),
       "a design-check job-level if without always() is refused: a failed need would skip the gate")
    _ungated = _in_job(
        "design-check",
        "if: steps.gate.outputs.run == 'true'\n        run: npm ci --prefix app",
        "run: npm ci --prefix app",
        "later step that does not read the gate",
    )
    ok(any("do not read the gate" in m and "name: Install" in m for _, m in browser_gate_findings(_ungated)),
       "a later step that does not read steps.gate.outputs.run is refused, and named")
    # The real shape: the head's gate reads clean, and each text the three mutations above change is in it.
    _anchors = (
        "RUN: ${{ needs.already-passed.outputs.skip != 'true' && needs.browser-scope.outputs.run != 'false'",
        "if: ${{ always() && !github.event.pull_request.draft }}",
        "if: steps.gate.outputs.run == 'true'\n        run: npm ci --prefix app",
    )
    ok(
        all(anchor in _workflow for anchor in _anchors) and not _gate,
        "the branch's real gate reads clean, and every text the three mutations change is in it",
        "\n".join(m for _, m in _gate),
    )
    # THE PASS RECORDER, READ OFF ITS OWN STEPS (D136, D141). The record job is a needed job: its
    # only job-level `if:` is the draft guard, and its gate step computes `record` from the six
    # conditions below. Every later step that writes a pass record
    # reads that answer. The cases SPLICE a record job of that shape into the LIVE workflow, so the
    # rest of the file is what the reader sees in production. A finding is judged against the good
    # shape, so a case fails for its own named cause and not for text the two shapes share.
    print("\nthe pass recorder reads its own gate, and each way it could record a tree no browser saw is a finding")
    _record_conditions = (
        "needs.design-check.result == 'success'",
        "needs.browser-scope.outputs.run != 'false'",
        "needs.already-passed.outputs.skip != 'true'",
        "needs.ci-static.result == 'success'",
        "needs.browser-scope.outputs.partial != 'true'",
        "github.event_name != 'push'",
    )
    _gate_if = "if: steps.gate.outputs.record == 'true'"
    _tree_name = "design-check-pass-${{ steps.tree.outputs.tree }}"

    _record_needs = ("design-check", "browser-scope", "already-passed", "ci-static")

    def _recorder(conditions=_record_conditions, upload_if=_gate_if, upload_name=_tree_name,
                  gate_comment="", before_upload="", tree_body_extra="",
                  needs=_record_needs, job_if="${{ !github.event.pull_request.draft }}",
                  pre_gate="", gate_id="gate",
                  output_line='echo "record=${RECORD}" >> "$GITHUB_OUTPUT"', record_expr=None):
        """A record job of the good shape, with one thing changed per argument."""
        gated = f"        {upload_if}\n" if upload_if else ""
        job_gate = f"    if: {job_if}\n" if job_if is not None else ""
        record = " && ".join(conditions) if record_expr is None else record_expr
        return (
            "  design-check-passed:\n"
            f"    needs: [{', '.join(needs)}]\n"
            + job_gate
            + "    runs-on: ubuntu-latest\n"
            "    timeout-minutes: 5\n"
            "    steps:\n"
            + pre_gate
            + "      - name: Does the record gate pass\n"
            f"        id: {gate_id}\n"
            "        env:\n"
            + gate_comment
            + "          RECORD: ${{ " + record + " }}\n"
            "        run: |\n"
            f"          {output_line}\n"
            "\n"
            "      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4\n"
            "        if: steps.gate.outputs.record == 'true'\n"
            "        with:\n"
            "          persist-credentials: false\n"
            "\n"
            "      - name: Name the tree\n"
            "        id: tree\n"
            "        if: steps.gate.outputs.record == 'true'\n"
            "        run: |\n"
            "          tree=\"$(git rev-parse 'HEAD^{tree}')\"\n"
            "          echo \"tree=${tree}\" >> \"$GITHUB_OUTPUT\"\n"
            "          printf 'tree %s\\n' \"${tree}\" > design-check-pass.txt\n"
            + tree_body_extra
            + "\n"
            + before_upload
            + "      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4\n"
            + gated
            + "        with:\n"
            + f"          name: {upload_name}\n"
            "          path: design-check-pass.txt\n"
            "          retention-days: 30\n"
        )

    _live_recorder = _yaml_job_block(_workflow, "design-check-passed") or ""
    ok(bool(_live_recorder), "the live workflow has a design-check-passed job to splice a record job into")

    def _spliced(recorder):
        """The live workflow with its record job replaced by `recorder`."""
        return _workflow.replace(_live_recorder, recorder, 1)

    def _extra(recorder):
        """The findings a record job raises that the good shape does not."""
        good = browser_gate_findings(_spliced(_recorder()))
        return [f for f in browser_gate_findings(_spliced(recorder)) if f not in good]

    _good = browser_gate_findings(_spliced(_recorder()))
    ok(
        _good == [],
        "the good shape reads clean: a draft-guard job `if:`, a gate step, and every later step gated on the record answer",
        "\n".join(m for _, m in _good),
    )
    _hazards = _recorder(
        before_upload="      # don't gate the upload on a guess\n",
        tree_body_extra="          echo \"# not a comment\"\n",
    )
    _got = browser_gate_findings(_spliced(_hazards))
    ok(
        _got == [],
        "the good shape with a lone quote in a comment and a `#` inside a quoted run line still reads clean",
        "\n".join(m for _, m in _got),
    )

    # The upload step is the write. Ungated, it writes a pass record for any tree, a skipped matrix
    # included, so the reader must name it. Each hazard is one way a scanner could read past a gate
    # that is not there: a comment quoting it, a lone quote, a quoted value holding it, a block
    # scalar line reading as a key, and a gate on the wrong condition.
    _found = _extra(_recorder(upload_if=None))
    ok(
        any("upload" in m for _, m in _found),
        "an upload step with no gate `if:` is a finding that names the upload",
        str(_found),
    )
    for _label, _text in (
        ("a comment quoting the gate's `if:`, above an ungated upload, is not the gate",
         _recorder(upload_if=None, before_upload="      # if: steps.gate.outputs.record == 'true'\n")),
        ("a lone quote in a comment does not hide an ungated upload",
         _recorder(upload_if=None, before_upload="      # don't gate this on a guess\n")),
        ("a quoted value holding the gate's `if:` text is not the upload's gate",
         _recorder(upload_if=None,
                   upload_name="\"design-check-pass-${{ steps.tree.outputs.tree }} # if: steps.gate.outputs.record == 'true'\"")),
        ("a block-scalar line that reads `if:` is not the upload's gate",
         _recorder(upload_if=None, tree_body_extra="          if: steps.gate.outputs.record == 'true'\n")),
        ("an upload gated on a condition other than the record answer is a finding that names the upload",
         _recorder(upload_if="if: github.event_name != 'push'")),
    ):
        _found = _extra(_text)
        ok(any("upload" in m for _, m in _found), _label, str(_found))

    # A gate that drops any one of the six reads the record answer on fewer conditions than the
    # pass record needs, so a tree no browser saw can earn one (the docs-only and partial trees
    # among them). One case per condition, and the empty gate, and a condition held in a comment.
    for _dropped in _record_conditions:
        _found = _extra(_recorder(conditions=tuple(c for c in _record_conditions if c != _dropped)))
        ok(any(_dropped in m for _, m in _found), f"a gate that drops `{_dropped}` is a finding that names it", str(_found))
    _found = _extra(_recorder(conditions=("true",)))
    ok(
        any(c in m for c in _record_conditions for _, m in _found),
        "a gate that reads none of the six conditions is a finding that names one",
        str(_found),
    )
    _found = _extra(_recorder(
        conditions=_record_conditions[1:],
        gate_comment=f"          # {_record_conditions[0]}\n",
    ))
    ok(
        any(_record_conditions[0] in m for _, m in _found),
        "a condition that appears only in a comment inside the gate is not read by the gate",
        str(_found),
    )

    # THE MUTANTS A READER CAN PASS (D136): a literal in the output line, an `||` or a seventh atom
    # in RECORD, a gate that is not first or has no id, a need the job drops, and a job-level `if:`
    # that is not the draft guard. Each expects a finding that names its own defect.
    for _label, _text, _needle in (
        ("a gate whose output line is hardcoded to `record=true` is a finding that names the output line",
         _recorder(output_line='echo "record=true" >> "$GITHUB_OUTPUT"'), "record=${RECORD}"),
        ("`|| true` appended to RECORD is a finding that names the exact six-condition expression",
         _recorder(record_expr=" && ".join(_record_conditions) + " || true"), "exactly"),
        ("a seventh && atom in RECORD is a finding that names the exact six-condition expression",
         _recorder(record_expr=" && ".join(_record_conditions + ("github.actor != 'x'",))), "exactly"),
        ("a gate that is not the first step is a finding that names the first step",
         _recorder(pre_gate="      - run: echo hi\n"), "first step"),
        ("a gate step without `id: gate` is a finding that names it",
         _recorder(gate_id="decide"), "id: gate"),
        ("a job-level if that is not the draft guard is a finding that names the draft guard",
         _recorder(job_if="${{ !github.event.pull_request.draft && github.event_name != 'push' }}"), "draft guard"),
        ("a job with no job-level if is a finding that names the draft guard",
         _recorder(job_if=None), "draft guard"),
    ):
        _found = _extra(_text)
        ok(any(_needle in m for _, m in _found), _label, str(_found))
    for _job in _record_needs:
        _found = _extra(_recorder(needs=tuple(j for j in _record_needs if j != _job)))
        ok(
            any(f"does not `need` `{_job}`" in m for _, m in _found),
            f"a record job that does not need `{_job}` is a finding that names it",
            str(_found),
        )

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
