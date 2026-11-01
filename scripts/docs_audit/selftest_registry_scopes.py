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
from .registry_scopes import workflow_shards, INVOKERS, UNIT_COMMAND, check_audit_invocation, check_check_registry, fleet_scripts


def run(ok) -> None:
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            entry_parser().parse_args(["--no-such-flag"])
        code: Optional[int] = None
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else None
    ok(code == EXIT_USAGE, f"an unknown flag exits {EXIT_USAGE}, never 2", f"exited {code}")
    ok(fleet_scripts({"unit": UNIT_COMMAND, "design-check": "playwright test"}) == ["design-check"],
       "the exact unit command is not a fleet, and a bare `playwright test` is", "")
    ok(fleet_scripts({"sneaky": UNIT_COMMAND + " && playwright test"}) == ["sneaky"],
       "a fleet chained after the unit command is still a fleet", "")
    ok(workflow_shards("matrix:\n  target: [a, b]\n    run: make ci-check-static\n") == {"a", "b", "ci-check-static"},
       "a real `run:` line counts as a shard", "")
    ok(workflow_shards("matrix:\n  target: [a]\n    # run: make ci-check-static\n") == {"a"},
       "a commented `run:` line is not a shard", "")
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

    # THE REQUIRED CHECK'S WIRING (the `all jobs passed` row). The reader is
    # `registry_scopes.all_jobs_passed_findings`, a pure function over check.yml's text, the other
    # workflows and the stamp. It is fetched by name, so a reader not yet built fails each case with
    # a plain label rather than a crash. The fixture is ONE valid check.yml; each red case is ONE
    # mutation of it, and asserts the finding its mutation must raise, because "any finding" passes
    # vacuously when the fixture itself is broken.
    print("\nthe required check's wiring is read both ways, and each defect is a finding")
    NOT_BUILT = "not built: registry_scopes has no such reader yet (a builder adds it)"
    wiring_fn = getattr(registry_scopes, "all_jobs_passed_findings", None)
    jobs_fn = getattr(registry_scopes, "_jobs_block", None)
    names_fn = getattr(registry_scopes, "_job_names", None)
    value_fn = getattr(registry_scopes, "_yaml_value", None)
    blank_fn = getattr(registry_scopes, "_blank_block_scalars", None)
    check_fn = getattr(registry_scopes, "check_all_jobs_passed", None)
    PIN = "1cc47f015bdaf073d8cb0f043a988c28d09aa3e1"
    OTHER = "2" * 40
    DEMO = ".github/workflows/demo.yml"
    CHECK_PATH = rel(registry_scopes.CHECK_WORKFLOW)
    WANTED = {
        "check": "a thin alias",
        "design-check-passed": "a recorder",
        "nightly-alarm": "a reporter",
    }
    GREEN_STAMP = '{"merge": {"requiredChecks": "protection"}}'

    def fill(text: str) -> str:
        return text.replace("@PIN@", PIN).replace("@OTHER@", OTHER)

    FIXTURE = fill("""name: check
on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  # A comment with a lone quote, don't read it as a key or as a job.
  ci-check:
    if: ${{ !github.event.pull_request.draft }} # the shards, don't skip them
    runs-on: ubuntu-latest
    steps:
      - run: make ci-check
        if: ${{ github.event_name == 'push' }}
  ci-static:
    if: ${{ !github.event.pull_request.draft }}
    runs-on: ubuntu-latest
    steps:
      - name: a script whose body reads like keys
        run: |
          echo "a # inside a string is not a comment"
          uses: shivinate7/claude-settings/actions/stamp@@OTHER@
          needs: ${{ toJSON(needs) }}
  already-passed:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
  records:
    if: ${{ !github.event.pull_request.draft }}
    runs-on: ubuntu-latest
    steps:
      # - uses: shivinate7/claude-settings/actions/stamp@@OTHER@
      - uses: shivinate7/claude-settings/actions/code-check@@PIN@
  design-check:
    needs: [ci-check]
    if: ${{ !github.event.pull_request.draft }}
    runs-on: ubuntu-latest
    steps:
      - run: make design-check
  design-check-passed:
    needs: [design-check]
    if: ${{ github.event_name != 'push' }}
    runs-on: ubuntu-latest
    steps:
      - run: echo recorded
  nightly-alarm:
    needs: [ci-check]
    if: ${{ always() && github.event_name == 'schedule' }}
    runs-on: ubuntu-latest
    steps:
      - run: echo alarm
  check:
    needs: [all-jobs-passed]
    if: ${{ always() && !github.event.pull_request.draft }}
    runs-on: ubuntu-latest
    steps:
      - run: echo alias
  all-jobs-passed:
    needs: [ci-check, ci-static, already-passed, records, design-check]
    if: ${{ always() && !github.event.pull_request.draft }}
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: shivinate7/claude-settings/actions/all-jobs-passed@@PIN@
        with:
          needs: ${{ toJSON(needs) }}
""")
    DEMO_TEXT = fill("""jobs:
  playwright:
    runs-on: ubuntu-latest
    steps:
      - uses: shivinate7/claude-settings/actions/playwright-setup@@PIN@
""")

    def findings_for(check_text, stamp=GREEN_STAMP, excluded=WANTED):
        if wiring_fn is None:
            return None
        return wiring_fn({CHECK_PATH: check_text, DEMO: DEMO_TEXT}, stamp, excluded)

    def red(label, old, new, needle):
        """One mutation of the fixture. Its finding must name `needle`, and the mutation must apply."""
        mutated = FIXTURE.replace(fill(old), fill(new), 1)
        got = findings_for(mutated)
        applied = mutated != FIXTURE
        ok(
            applied and got is not None and any(needle in message for _, message in got),
            label,
            NOT_BUILT if got is None else f"mutation applied: {applied}; findings: {got}",
        )

    got = findings_for(FIXTURE)
    ok(got is not None and got == [], "the valid fixture reads clean", NOT_BUILT if got is None else str(got))

    expected_jobs = [
        "ci-check", "ci-static", "already-passed", "records", "design-check",
        "design-check-passed", "nightly-alarm", "check", "all-jobs-passed",
    ]
    names = names_fn(jobs_fn(FIXTURE)) if names_fn and jobs_fn else None
    ok(
        names == expected_jobs,
        "only the jobs block names jobs: `on:` triggers such as push and schedule are not jobs",
        NOT_BUILT if names is None else str(names),
    )
    ok(
        registry_scopes.__dict__.get("EXCLUDED") is not None and set(registry_scopes.EXCLUDED) == set(WANTED),
        "EXCLUDED names exactly check, design-check-passed and nightly-alarm, each with a reason",
        NOT_BUILT if not hasattr(registry_scopes, "EXCLUDED") else str(sorted(registry_scopes.EXCLUDED)),
    )

    # Scanner cases: a comment opener inside a string, a multi-line block scalar, a lone quote in text.
    ok(
        value_fn is not None and value_fn('"a # b" # note') == "a # b",
        "a comment opener inside a quoted value is text, and the comment after it is cut",
        NOT_BUILT if value_fn is None else repr(value_fn('"a # b" # note')),
    )
    ok(
        value_fn is not None and value_fn("${{ x }} # don't stop") == "${{ x }}",
        "a lone quote in a trailing comment does not change the value",
        NOT_BUILT if value_fn is None else repr(value_fn("${{ x }} # don't stop")),
    )
    ok(
        value_fn is not None and value_fn("${{ a#b }}") == "${{ a#b }}",
        "a # with no space before it is text, not a comment",
        NOT_BUILT if value_fn is None else repr(value_fn("${{ a#b }}")),
    )
    blanked = blank_fn(FIXTURE) if blank_fn else None
    ok(
        blanked is not None and not any(line.strip().startswith("uses: shivinate7/") for line in blanked),
        "a run block's body that reads like a uses key is blanked, so it is not a pin",
        NOT_BUILT if blanked is None else "a script line was read as a key",
    )
    ok(
        blanked is not None and len(blanked) == len(FIXTURE.split("\n")),
        "blanking a block scalar keeps every line number",
        NOT_BUILT if blanked is None else f"{len(blanked)} lines for {len(FIXTURE.split(chr(10)))}",
    )

    if wiring_fn is not None:
        mutated_no_rollup = FIXTURE.split("  all-jobs-passed:")[0]
        got = findings_for(mutated_no_rollup)
        ok(
            got is not None and any("has no `all-jobs-passed` job" in m for _, m in got),
            "a check.yml with no rollup job is a finding that names the missing job",
            NOT_BUILT if got is None else str(got),
        )
    else:
        ok(False, "a check.yml with no rollup job is a finding that names the missing job", NOT_BUILT)

    red(
        "a pin that differs from the rollup's pin is a finding that names the action",
        "actions/code-check@@PIN@",
        "actions/code-check@@OTHER@",
        "uses `code-check`",
    )
    red(
        "a needed job with a job-level skip is a finding that names the job",
        "  already-passed:\n    runs-on: ubuntu-latest",
        "  already-passed:\n    if: ${{ github.event_name == 'push' }}\n    runs-on: ubuntu-latest",
        "`already-passed` has the job-level `if:",
    )
    red(
        "a needed job missing from needs is a finding that names the job",
        "needs: [ci-check, ci-static, already-passed, records, design-check]",
        "needs: [ci-check, ci-static, already-passed, design-check]",
        "does not need `records`",
    )
    red(
        "design-check, now needed, missing from needs is a finding that names it",
        "needs: [ci-check, ci-static, already-passed, records, design-check]",
        "needs: [ci-check, ci-static, already-passed, records]",
        "does not need `design-check`",
    )
    red(
        "an excluded job named in needs is a finding (check would be a cycle)",
        "needs: [ci-check, ci-static, already-passed, records, design-check]",
        "needs: [ci-check, ci-static, already-passed, records, design-check, check]",
        "needs `check`, which is excluded",
    )
    red(
        "design-check's job-level if that reads needs outputs is a finding",
        "  design-check:\n    needs: [ci-check]\n    if: ${{ !github.event.pull_request.draft }}",
        "  design-check:\n    needs: [ci-check]\n    if: ${{ !cancelled() && needs.already-passed.outputs.skip != 'true' }}",
        "`design-check` has the job-level `if:",
    )
    red(
        "a rollup not under always() is a finding",
        "    if: ${{ always() && !github.event.pull_request.draft }}\n    runs-on: ubuntu-latest\n    timeout-minutes: 5",
        "    if: ${{ !github.event.pull_request.draft }}\n    runs-on: ubuntu-latest\n    timeout-minutes: 5",
        "`all-jobs-passed` has the job-level `if:",
    )
    red(
        "a rollup whose with block passes no needs is a finding",
        "        with:\n          needs: ${{ toJSON(needs) }}",
        "        with:\n          other: ${{ toJSON(needs) }}",
        "passes no `needs:`",
    )
    red(
        "a uses line inside a run body is not the rollup step (the body is blanked)",
        "      - uses: shivinate7/claude-settings/actions/all-jobs-passed@@PIN@\n        with:\n          needs: ${{ toJSON(needs) }}",
        "      - run: |\n          uses: shivinate7/claude-settings/actions/all-jobs-passed@@PIN@\n          needs: ${{ toJSON(needs) }}",
        "does not run `shivinate7/claude-settings/actions/all-jobs-passed`",
    )
    red(
        "a rollup pinned to a tag, not a 40-character sha, is a finding",
        "all-jobs-passed@@PIN@",
        "all-jobs-passed@v1",
        "40-character",
    )
    red(
        "a needed job whose job-level if is a multi-line block is a finding",
        "  records:\n    if: ${{ !github.event.pull_request.draft }}",
        "  records:\n    if: >-\n      ${{ !github.event.pull_request.draft }}",
        "`records` has the job-level `if:",
    )
    red(
        "a check job needing more than the rollup is a finding (rule 8)",
        "  check:\n    needs: [all-jobs-passed]",
        "  check:\n    needs: [all-jobs-passed, ci-check]",
        "`check` needs [all-jobs-passed, ci-check]",
    )
    red(
        "a check job with no needs is a finding (rule 8)",
        "  check:\n    needs: [all-jobs-passed]",
        "  check:\n    runs-on: ubuntu-latest",
        "`check` has no `needs:`",
    )
    # CONTINUE-ON-ERROR HIDES A FAILURE FROM THE ROLLUP. A failed step or job that cannot fail its
    # job reads green to the action, so it is a finding on a needed job, on one of its steps, on the
    # rollup itself, and on the alias. `continue-on-error: false` is the default and is not one.
    red(
        "continue-on-error on a needed job is a finding that names it",
        "  ci-static:\n    if: ${{ !github.event.pull_request.draft }}",
        "  ci-static:\n    if: ${{ !github.event.pull_request.draft }}\n    continue-on-error: true",
        "continue-on-error",
    )
    red(
        "continue-on-error on a step of a needed job is a finding that names it",
        "      - run: make design-check",
        "      - run: make design-check\n        continue-on-error: true",
        "continue-on-error",
    )
    red(
        "continue-on-error on the all-jobs-passed job is a finding that names it",
        "    timeout-minutes: 5\n    steps:\n      - uses: shivinate7/claude-settings/actions/all-jobs-passed@@PIN@",
        "    timeout-minutes: 5\n    continue-on-error: true\n    steps:\n      - uses: shivinate7/claude-settings/actions/all-jobs-passed@@PIN@",
        "continue-on-error",
    )
    red(
        "continue-on-error on the all-jobs-passed step is a finding that names it",
        "      - uses: shivinate7/claude-settings/actions/all-jobs-passed@@PIN@\n        with:",
        "      - uses: shivinate7/claude-settings/actions/all-jobs-passed@@PIN@\n        continue-on-error: true\n        with:",
        "continue-on-error",
    )
    red(
        "continue-on-error on the check alias is a finding that names it",
        "  check:\n    needs: [all-jobs-passed]",
        "  check:\n    needs: [all-jobs-passed]\n    continue-on-error: true",
        "continue-on-error",
    )
    got = findings_for(FIXTURE.replace(
        "  ci-static:\n    if: ${{ !github.event.pull_request.draft }}",
        "  ci-static:\n    if: ${{ !github.event.pull_request.draft }}\n    continue-on-error: false",
        1,
    ))
    ok(
        got is not None and got == [],
        "continue-on-error: false on a needed job is not a finding",
        NOT_BUILT if got is None else str(got),
    )
    # THE SPELLINGS THE LINE READER DID NOT SEE. A flow-style step (`- { ... }`) puts its keys after
    # the `- {`, so a reader that matches only a line that starts with the key misses them. The
    # expression and quoted forms are plain values, and each must still be a finding.
    red(
        "continue-on-error: true inside a single-line flow step on a needed job is a finding",
        "      - run: make design-check",
        "      - { name: x, continue-on-error: true, run: make design-check }",
        "continue-on-error",
    )
    red(
        "continue-on-error first in a single-line flow step on a needed job is a finding",
        "      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4",
        "      - { continue-on-error: true, uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 }",
        "continue-on-error",
    )
    red(
        "continue-on-error as an expression on a needed job is a finding",
        "  ci-static:\n    if: ${{ !github.event.pull_request.draft }}",
        "  ci-static:\n    if: ${{ !github.event.pull_request.draft }}\n    continue-on-error: ${{ matrix.x }}",
        "continue-on-error",
    )
    red(
        "continue-on-error quoted as 'true' on a needed job is a finding",
        "  records:\n    if: ${{ !github.event.pull_request.draft }}",
        "  records:\n    if: ${{ !github.event.pull_request.draft }}\n    continue-on-error: 'true'",
        "continue-on-error",
    )
    got = findings_for(FIXTURE.replace(
        "      - run: make design-check",
        "      - { name: x, run: make design-check, continue-on-error: false }",
        1,
    ))
    ok(
        got is not None and got == [],
        "continue-on-error: false inside a flow step on a needed job is not a finding",
        NOT_BUILT if got is None else str(got),
    )
    got = findings_for(FIXTURE, excluded={**WANTED, "ghost-job": "renamed away"})
    ok(
        got is not None and any("`ghost-job`" in m for _, m in got),
        "an EXCLUDED name that is not a job is a stale finding",
        NOT_BUILT if got is None else str(got),
    )
    got = findings_for(FIXTURE, stamp='{"merge": {"requiredChecks": ["ci-check"]}}')
    ok(
        got is not None and any("requiredChecks" in m for _, m in got),
        "a stamp that names some other required check is a finding",
        NOT_BUILT if got is None else str(got),
    )
    got = findings_for(FIXTURE, stamp='{"merge": {"requiredChecks": ["all-jobs-passed"]}}')
    ok(got is not None and got == [], "a stamp that names exactly all-jobs-passed reads clean", NOT_BUILT if got is None else str(got))
    got = findings_for(FIXTURE, stamp=None)
    ok(
        got is not None and any("required check is unknown" in m for _, m in got),
        "a missing stamp is a finding, never a pass",
        NOT_BUILT if got is None else str(got),
    )
    got = wiring_fn({DEMO: DEMO_TEXT}, GREEN_STAMP, WANTED) if wiring_fn else None
    ok(
        got is not None and any("does not exist or cannot be read" in m for _, m in got),
        "a missing check.yml is a finding, never a pass",
        NOT_BUILT if got is None else str(got),
    )

    # The live row, read the way `make docs-audit` reads it. Its findings are NOT asserted: they
    # change as the builder lands the rollup. Only that it reads, and that a missing file is a finding.
    if check_fn is None:
        ok(False, "the row's check function exists in registry_scopes.py", NOT_BUILT)
    else:
        report = Report()
        check_fn(report)
        rows = [row for row in report.checks if row.check == "all jobs passed"]
        ok(
            len(rows) == 1 and rows[0].severity == MECHANICAL and bool(rows[0].summary),
            "the row is one mechanical row with a summary",
            str([row.check for row in report.checks]),
        )
        saved_check = registry_scopes.CHECK_WORKFLOW
        registry_scopes.CHECK_WORKFLOW = ROOT / ".github" / "workflows" / "no-such-check.yml"
        try:
            report = Report()
            check_fn(report)
            rows = [row for row in report.checks if row.check == "all jobs passed"]
            ok(
                len(rows) == 1 and any("does not exist or cannot be read" in f.message for f in rows[0].findings),
                "a missing check.yml makes the live row red, never a crash or a pass",
                str([f.message for f in rows[0].findings]) if rows else "no row",
            )
        finally:
            registry_scopes.CHECK_WORKFLOW = saved_check
