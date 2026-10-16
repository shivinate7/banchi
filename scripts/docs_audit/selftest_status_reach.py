"""Self-test cases, status reach rows. Called by `selftest.self_test`."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .core import ROOT, Report, exists, read, registered_tests
from .design import COLOR, TYPEFACE, token_value
from .env_map import DEFAULT_SOURCE_SUFFIXES, SOURCE_SUFFIXES_KEY, scan_plan, source_names
from .hygiene import _VERDICT_CONFIG, _VERDICT_REPORTER, verdict_disagreements
from .paths_commands import phony_gaps
from .status_reach import (
    check_tested_by_reach,
    follow_target,
    imported_names,
    model_disagreement,
    reach_findings,
    string_literals,
    test_reach,
)


def run(ok) -> None:
    # And the live tree, which is what the row actually asserts on every run.
    ok(
        not verdict_disagreements(
            read(_VERDICT_REPORTER) if exists(_VERDICT_REPORTER) else None,
            read(_VERDICT_CONFIG) if exists(_VERDICT_CONFIG) else None,
            read(ROOT / "Makefile"),
            read(ROOT / "CLAUDE.md"),
        ),
        "this repo's own four files agree",
    )

    # A target absent from .PHONY is a green `make` that ran nothing, and nothing in the
    # prose is wrong when it happens — so no other check in this file can see it.
    print("\nevery make target is declared .PHONY")
    complete = ".PHONY: help harness\n\nhelp:\n\t@echo hi\n\nharness:\n\t@run\n"
    ok(phony_gaps(complete) == (set(), set()), "a complete .PHONY is clean", str(phony_gaps(complete)))
    dropped = ".PHONY: help\n\nhelp:\n\t@echo hi\n\nharness:\n\t@run\n"
    ok(
        phony_gaps(dropped) == ({"harness"}, set()),
        "a target missing from .PHONY is reported",
        str(phony_gaps(dropped)),
    )
    stale = ".PHONY: help harness ghost\n\nhelp:\n\t@echo hi\n\nharness:\n\t@run\n"
    ok(
        phony_gaps(stale) == (set(), {"ghost"}),
        "a .PHONY name with no rule is reported",
        str(phony_gaps(stale)),
    )
    ok(
        phony_gaps(read(ROOT / "Makefile")) == (set(), set()),
        "this repo's own Makefile agrees with its .PHONY",
        str(phony_gaps(read(ROOT / "Makefile"))),
    )

    # The orphan scan's reach. Every case here is a way for the rule to look like it ran:
    # the wrong suffixes find nothing, a flat scan of a nested tree finds nothing, and a
    # typo in the declaration finds nothing — all three print the same clean row.
    print("\nthe orphan scan covers what the map entry declares")
    ok(
        scan_plan({}) == (DEFAULT_SOURCE_SUFFIXES, False, []),
        "an entry declaring nothing is scanned as it always was",
        str(scan_plan({})),
    )
    plan = scan_plan({SOURCE_SUFFIXES_KEY: [".tsx", ".css"], "modules": {"src/a.tsx": {}}})
    ok(plan == ((".tsx", ".css"), True, []), "a declaration replaces the default, and recurses", str(plan))
    plan = scan_plan({SOURCE_SUFFIXES_KEY: ["tsx"], "modules": {"src/a.tsx": {}}})
    ok(
        plan[0] == () and len(plan[2]) == 2,
        "a suffix without its dot is reported, not silently matched",
        str(plan),
    )
    plan = scan_plan({SOURCE_SUFFIXES_KEY: ".tsx", "modules": {"src/a.tsx": {}}})
    ok(
        plan[0] == () and len(plan[2]) == 1,
        "a bare string is reported — str.endswith would have accepted it",
        str(plan),
    )
    plan = scan_plan({SOURCE_SUFFIXES_KEY: [".tsx"]})
    ok(
        len(plan[2]) == 1,
        "declaring suffixes with no modules list is an inert declaration",
        str(plan),
    )

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name in ("src/a.tsx", "src/deep/b.tsx", "node_modules/pkg/c.tsx",
                     "dist/d.tsx", "test-results/e.tsx", "src/f.py"):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("", encoding="utf-8")
        found = source_names(root, (".tsx",), True)
        ok(
            found == {"src/a.tsx", "src/deep/b.tsx"},
            "a deep scan reaches subdirectories and skips the build output",
            str(sorted(found)),
        )
        ok(
            source_names(root, (".tsx",), False) == set(),
            "and the flat scan it replaced saw none of it — the defect, measured",
            str(sorted(source_names(root, (".tsx",), False))),
        )
        ok(
            source_names(root, DEFAULT_SOURCE_SUFFIXES, False) == set(),
            "a `.py` entry is unaffected by any of it",
            str(sorted(source_names(root, DEFAULT_SOURCE_SUFFIXES, False))),
        )

    # A tested_by claim. Every case below is a way for this row to pass a claim it should
    # refuse, or refuse one it should pass — and the blocking direction is the expensive one,
    # so the correct claims are asserted first and against the real harness.
    print("\na tested_by claim is checked against what the cited test imports")
    ok(
        "geometry" in imported_names("def run():\n    import geometry\n"),
        "an import inside a function is found — t6's shape, and it is a correct claim",
        str(imported_names("def run():\n    import geometry\n")),
    )
    names = imported_names("from harness.eval import fixtures, runcache\n")
    ok(
        {"harness.eval", "harness.eval.fixtures", "harness.eval.runcache"} <= names,
        "a from-import records the package and each name, since only disk knows which is a module",
        str(sorted(names)),
    )
    ok(
        imported_names("from . import sibling\n") == set(),
        "a relative import names nothing this can resolve, and is dropped",
        str(imported_names("from . import sibling\n")),
    )
    literals = string_literals('"""Load fixtures/doc.csv"""\nA = "fixtures/code.csv"\n')
    ok(
        literals == {"fixtures/code.csv"},
        "a path in a docstring is prose; a path in an assignment is the test reading a file",
        str(sorted(literals)),
    )

    # The follow's boundary, stated as two assertions because the whole value of this row
    # is what it declines to follow.
    ok(
        follow_target("harness.eval.fixtures") is not None
        and follow_target("pipeline.join") is None,
        "the follow reaches a harness helper and stops at a product package",
        f"{follow_target('harness.eval.fixtures')} / {follow_target('pipeline.join')}",
    )
    registry = {name: path for name, path in registered_tests()}
    if "T7" in registry and "T1" in registry:
        packages, _ = test_reach(registry["T7"])
        ok(
            "store" in packages and "codes" not in packages,
            "T7 reaches store directly and does NOT reach codes through cli — "
            "the transitive follow that would make this row vacuous is absent",
            str(sorted(packages)),
        )
        packages, _ = test_reach(registry["T1"])
        ok(
            "identify" in packages,
            "T1 reaches identify",
            str(sorted(packages)),
        )

    # The false claim docs/debts/ recorded, replayed against the real harness rather than
    # against a stand-in for it. `store/queues.py` cited T3 and T4 while nothing under
    # harness/ imported store.
    #
    # THE ID IN THIS CASE HAS MOVED TWICE, AND BOTH MOVES ARE THE CASE WORKING RATHER THAN
    # ROTTING. It pinned T3 once T7 arrived and began importing store; then T3 itself began
    # importing store (commit 548515b, when D7's fungibility amendment made it build a real
    # store to exercise rung 0 and the `committed` flag), so the claim stopped being false
    # and this case went red — a RED SELF-TEST WITH A GREEN AUDIT, which is exactly the
    # shape a stale fixture takes. Found on 2026-08-24; nothing runs `--self-test` on the
    # commit path, which is why it sat.
    #
    # Pinned to T5 now, and the requirement is stated rather than left to be rediscovered:
    # THIS CASE NEEDS A TEST THAT REACHES `pipeline` AND NOT `store`. T2 and T5 are the only
    # two left. If a later change gives T5 a store, move it again and add a line here — do
    # not weaken the assertion, which is the whole point of the case: the `tested_by reach`
    # row must be able to catch a claim that a test covers a package it never imports.
    if registry:
        found, claims = reach_findings(
            [{"path": "store/", "modules": {"queues.py": {"tested_by": ["T5"]}}}], registry
        )
        ok(
            len(found) == 1 and claims == 1 and "store" in found[0].message,
            "the historical false claim — store/queues.py citing a pipeline-only test — "
            "is reported",
            str(found),
        )
        found, claims = reach_findings(
            [{"path": "pipeline/", "modules": {"pricing.py": {"tested_by": ["T5"]}}}], registry
        )
        ok(not found and claims == 1, "and the true claim beside it is not", str(found))
        found, _ = reach_findings([{"path": "fixtures/", "tested_by": ["T2"]}], registry)
        ok(
            not found,
            "a directory holding no Python passes on a path literal — fixtures/ from T2",
            str(found),
        )
        # T6 RATHER THAN T7, AND THE SWAP IS THIS SELF-TEST'S OWN ALLOWLIST RULE FIRING.
        # This case named T7 until 2026-08-30, when T7 gained two `fixtures/` literals for the
        # price-history reader and the negative case went green for a reason that had nothing
        # to do with the checker. A negative case whose subject stops being negative is a case
        # that has silently stopped testing anything — the same shape D16 gives
        # `docs-audit-allow.txt`, where an entry coming true is what forces it out. T6 builds
        # synthetic composites and names no path under `fixtures/`, which is what this case
        # needs and is a property of that test rather than an accident of today's tree.
        found, _ = reach_findings([{"path": "fixtures/", "tested_by": ["T6"]}], registry)
        ok(
            len(found) == 1,
            "and fails when the cited test never names a path under it",
            str(found),
        )
        found, claims = reach_findings(
            [{"path": "store/", "modules": {"queues.py": {"tested_by": ["T99"]}}}], registry
        )
        ok(
            not found and claims == 0,
            "an unregistered id is the repo map row's finding, not counted or repeated here",
            str(found),
        )
        found, _ = reach_findings([{"path": "no_such_dir/", "tested_by": ["T3"]}], registry)
        ok(not found, "and a component path that does not exist is the same", str(found))

    report = Report()
    check_tested_by_reach(report)
    by_label = {row.check: row.findings for row in report.checks}
    ok(
        not by_label.get("tested_by reach"),
        "every tested_by claim in this repo's own map reaches what it names",
        str(by_label.get("tested_by reach")),
    )

    # The token row's silent failures, in the order they would bite: a normaliser that
    # hides a real difference, a parser that reads a value the browser never sees, and a
    # comparison that runs in one direction only.
    print("\nthe locked palette is compared against the stylesheet, both ways")
    ok(
        token_value(COLOR, "#FFF") == token_value(COLOR, "#ffffff"),
        "case and shorthand are spelling, not disagreement",
        f'{token_value(COLOR, "#FFF")} vs {token_value(COLOR, "#ffffff")}',
    )
    ok(
        token_value(TYPEFACE, "'Cabinet Grotesk', sans-serif") == token_value(TYPEFACE, "Cabinet Grotesk"),
        "the generic fallback in a font stack is not part of the token",
        token_value(TYPEFACE, "'Cabinet Grotesk', sans-serif"),
    )

    print("\nthe paid-read model named in CLAUDE.md is the one the code emits")
    rule = "- **Batch API, not sequential calls.** Model: `m-1`."
    ok(model_disagreement(rule, 'MODEL = "m-1"\n') is None, "equal ids agree")
    ok(model_disagreement(rule, 'MODEL = "m-2"\n') is not None, "a swapped model id is caught")
    ok(
        model_disagreement(read(ROOT / "CLAUDE.md"), read(ROOT / "identify" / "prompt.py")) is None,
        "this repo's CLAUDE.md and prompt.py agree",
    )
