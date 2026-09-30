"""Closed vocabularies, the tested-by reach and status sources."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .core import (
    Finding,
    MECHANICAL,
    ROOT,
    Report,
    _merge_rows,
    child_names,
    exists,
    glob_files,
    literals_from_module,
    read,
    registered_tests,
    rel,
)
from .env_map import MAP
from .reasons import (
    _order_reasons,
    _pricing_presets,
    _reason_codes,
    _reason_emissions,
    _terminal_statuses,
    _withhold_reasons,
)

# ------------------------------------------------ whether a cited test reaches what it claims

# Where the one-level follow stops, and the reason this row says anything at all.
#
# A test's own scaffolding is part of the test: harness/eval/ holds the fixture loader and
# the run cache, and a test that kept its imports there would otherwise be reported as
# reaching nothing — a false positive, on a blocking row, over a correct claim. So the
# follow reaches modules under here and no further.
#
# PRODUCT PACKAGES ARE DELIBERATELY NOT FOLLOWED, and that is the whole design. Measured on
# this tree: `cli/cmd_identify.py` imports `geometry`, `cli/resolve.py` imports `store`, and
# `harness/tests/t7_store_and_seams.py` imports `cli`. One transitive hop would therefore
# prove "T7 reaches geometry" — a package T7 does not touch and whose two modules correctly
# cite T6. Transitive reachability through the product's own graph makes almost every claim
# true and asserts nothing, which is to say it recreates the unenforced field this row
# exists to enforce, using the machinery meant to enforce it.
FOLLOW_ROOT = "harness/"


def check_closed_vocabularies(report: Report) -> None:
    """Six closed vocabularies, one row: withhold reasons, order reasons, terminal
    statuses, pricing presets, reason codes and reason emissions — each a hand-authored set
    declared twice (once for a parser or resolver, once for a screen or a decision entry)
    and reconciled here so the two copies cannot drift apart in silence.

    Merged from six rows by M3 (test-audit-2026-09-27, L8, Q8 yes). Each sub-check below is
    unchanged; only the last line of each moved from `report.add` to `return Row`, so every
    defect any of the six used to catch still fails this one.
    """
    merged = _merge_rows("closed vocabularies", [
        _reason_codes(),
        _reason_emissions(),
        _withhold_reasons(),
        _order_reasons(),
        _terminal_statuses(),
        _pricing_presets(),
    ])
    report.add("closed vocabularies", merged.severity, merged.findings, merged.summary,
               scanned=merged.scanned)


def imported_names(source: str) -> Set[str]:
    """Every absolute dotted module name a source imports. The whole tree, not just its body.

    `ast.walk` rather than `tree.body`, because two of the seven tests import the thing they
    are named for from inside a function: `harness/tests/t6_geometry.py` imports `geometry`
    after its Pillow/numpy availability check, and `harness/tests/t7_store_and_seams.py`
    imports `cli.__main__` inside the case that drives it. A module-level read would call
    both of those claims false and block a commit over them.

    `from . import x` is dropped rather than resolved: a relative import names no package
    this check can compare against a map entry, and no test in this repo writes one.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module)
            # `from harness.eval import fixtures, runcache` — each name is a submodule or an
            # attribute, and only the filesystem knows which. Both forms are recorded; the
            # resolver below finds no file for an attribute and moves on.
            for alias in node.names:
                names.add(node.module + "." + alias.name)
    return names


def string_literals(source: str) -> Set[str]:
    """Every string constant in a source that is not a docstring.

    Docstrings are excluded because they are prose, and prose is what this whole script
    treats as unverified. `harness/tests/t2_round_trip.py` opens with "Load
    fixtures/sv09_export_untouched.csv" in its module docstring and then assigns the same
    path to `SOURCE_FIXTURE` two dozen lines down. Only the second is the test reading the
    file; counting the first would let a sentence satisfy the claim.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    docstrings: Set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            docstrings.add(id(body[0].value))
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    }


def follow_target(dotted: str) -> Optional[Path]:
    """A dotted module name as a file under FOLLOW_ROOT, or None for anything else."""
    stem = dotted.replace(".", "/")
    for candidate in (ROOT / (stem + ".py"), ROOT / stem / "__init__.py"):
        if rel(candidate).startswith(FOLLOW_ROOT) and exists(candidate):
            return candidate
    return None


def test_reach(path: Path) -> Tuple[Set[str], Set[str]]:
    """(top-level packages the test imports, path literals it names). One level deep."""
    source = read(path)
    names = imported_names(source)
    literals = string_literals(source)
    # `sorted()` copies, so the sets may grow inside the loop without the new entries being
    # followed in turn. That is not an implementation detail — it IS the one level.
    for dotted in sorted(names):
        helper = follow_target(dotted)
        if helper is None or helper == path:
            continue
        helper_source = read(helper)
        names |= imported_names(helper_source)
        literals |= string_literals(helper_source)
    return {name.split(".", 1)[0] for name in names}, literals


def is_importable(target: Path) -> bool:
    """Does this directory hold Python at all?

    Not `__init__.py`: `server/` and `harness/` have none and are imported anyway, as
    namespace packages. Holding a `.py` child is the property that matters, and it is what
    separates a package from `fixtures/`, which holds CSVs, and `app/`, which holds
    TypeScript. Those two have no import to check, so the claim on them is checked the only
    other way a parse can see — a path literal.
    """
    return any(name.endswith(".py") for name in child_names(target))


def reach_findings(
    components: Sequence[Dict[str, object]], tests: Dict[str, Path]
) -> Tuple[List[Finding], int]:
    """(findings, claims checked). Split out from the check so the self-test can drive it.

    The self-test feeds it the exact false claim docs/debts/ recorded — `store/queues.py`
    citing T3 — against the real harness, rather than a synthetic stand-in for it.
    """
    findings: List[Finding] = []
    claims = 0
    cache: Dict[str, Tuple[Set[str], Set[str]]] = {}

    def reach(name: str) -> Tuple[Set[str], Set[str]]:
        if name not in cache:
            cache[name] = test_reach(tests[name])
        return cache[name]

    for component in components:
        path = str(component.get("path", ""))
        target = ROOT / path
        if not path or not exists(target):
            continue  # the repo map row already reports a component path that is not there
        package = path.strip("/").split("/")[0]
        importable = is_importable(target)

        entries: List[Tuple[str, Sequence[str]]] = [(path, component.get("tested_by") or [])]
        for module_name, entry in (component.get("modules") or {}).items():
            entries.append((path + str(module_name), list(entry.get("tested_by") or [])))

        for where, cited in entries:
            for name in cited:
                # An id that is not a registered test is already a finding on the repo map
                # row, and there is no file here to parse. Reporting it twice under two
                # labels would make one defect read as two.
                if name not in tests or not exists(tests[name]):
                    continue
                claims += 1
                packages, literals = reach(name)

                if importable:
                    if package in packages:
                        continue
                    in_repo = sorted(
                        found
                        for found in packages
                        if exists(ROOT / found) or exists(ROOT / (found + ".py"))
                    )
                    findings.append(
                        Finding(
                            f"docs/map.py -> {where}",
                            f"tested_by claims {name}, and {rel(tests[name])} imports no "
                            f"`{package}`.\n"
                            f"  {name} reaches: {', '.join(in_repo) or '(nothing in this repo)'}\n"
                            f"  Either the claim is false and goes, or the test should import "
                            f"what it is credited with. Do not answer this in prose: the "
                            f"entry's `note` is read by people and this row is not.",
                        )
                    )
                    continue

                if any(literal.startswith(where) for literal in literals):
                    continue
                findings.append(
                    Finding(
                        f"docs/map.py -> {where}",
                        f"tested_by claims {name}, and {rel(tests[name])} names no path "
                        f"under `{where}`.\n"
                        f"  `{path}` holds no Python, so there is no import to check. The "
                        f"only evidence a parse can see is the test naming a path under it "
                        f"in its code — a mention in its docstring is prose and does not "
                        f"count.",
                    )
                )
    return findings, claims


def check_tested_by_reach(report: Report) -> None:
    """A `tested_by` claim in docs/map.py, against what the cited test actually imports.

    The repo-map row proves a cited test id is registered in `harness/run.py:TESTS`. It has
    never proved the test goes anywhere near the module claiming it, and docs/debts/
    recorded the measurement: of the eleven entries audited by hand on 2026-08-11, ten were
    true and one was false — `store/queues.py` claimed T3 and T4 while nothing under
    `harness/` imported `store` at all. D17 says the map is audited exactly as hard as it is
    trusted, and this was the field where it was trusted and not audited.

    **WHAT A PASSING CLAIM PROVES, EXACTLY**: the cited test's import graph — the test module
    plus one level into its own `harness/` helpers — contains the top-level package the
    entry lives in. For a directory holding no Python, that the test names a path under it in
    a string literal outside its docstrings.

    **WHAT IT DOES NOT PROVE, AND THE DISTANCE IS LARGE**: not that the test imports the
    *module*, not that it calls anything the module defines, and not that any assertion
    depends on it. `from pipeline import join` satisfies every entry in `pipeline/` at once.
    A test could import a package and exercise none of it and this row would stay green.
    Overclaiming here would be the same defect one level up — an unenforced claim about a
    checker for unenforced claims — so the label is `tested_by reach` and not `tested_by
    coverage`, and the summary says "reaches" rather than "tests".

    **Package granularity, not module granularity, and that was measured too.**
    `harness/tests/t6_geometry.py` imports the bare package (`import geometry`) and then uses
    `geometry.detect` through it, so a module-granular rule would call both correct
    `geometry/` entries false. A false positive that blocks is worse than one that prints
    (D16), and this row blocks — so it asks the question it can answer without judgment.

    **Blocking, because an import either is in the parse or is not.** That is D16's test for
    a mechanical finding. The residual risk is a test that reaches code without importing
    it — through a subprocess or a generated file. No harness test does today (`subprocess`
    appears nowhere under `harness/tests/`), and if one ever does the fix is to drop the
    claim or to make the test import what it is credited with. It is deliberately not
    something a `note` can talk its way out of: that is what "unenforced" meant.
    """
    if not exists(MAP):
        return  # the repo map row above already reports a missing map, loudly
    components = literals_from_module(MAP).get("COMPONENTS") or []
    tests = {name: path for name, path in registered_tests()}
    findings, claims = reach_findings(components, tests)
    report.add(
        "tested_by reach",
        MECHANICAL,
        findings,
        f"{claims} claims, every cited test reaches what it names",
        scanned=claims,
    )


# ----------------------------------------------------------- status.py's declared sources


STATUS = ROOT / "scripts" / "status.py"


def module_defs(path: Path) -> Set[str]:
    """Module-level `def` names, by parsing — same no-import rule as everything else here."""
    try:
        tree = ast.parse(read(path))
    except (OSError, SyntaxError):
        return set()
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def check_status_sources(report: Report) -> None:
    """`make status` reads a declared list of files. This verifies every one of them.

    status.py derives every value it prints, so its *values* cannot go stale. Its *reader*
    can: rename `harness/results/t1.json` and the glob matches nothing, silently deleting
    the most important line of the output. That is worse than no status tool, because you
    would believe the shorter version.

    It is not hypothetical. The score files were dated until `f86de1a` made them one per
    configuration, and a reader written the week before would have gone quiet rather than
    loud. So this is a check, not a comment asking the next session to remember.

    Reads SOURCES with `ast`, never by importing — a read-only audit must not execute the
    code it audits, which is also why SOURCES has to stay a pure literal.
    """
    if not exists(STATUS):
        report.add("status sources", MECHANICAL, [Finding("scripts/status.py", "does not exist")])
        return

    sources = literals_from_module(STATUS).get("SOURCES")
    if not sources:
        report.add(
            "status sources",
            MECHANICAL,
            [
                Finding(
                    "scripts/status.py",
                    "no SOURCES list to read. It must stay a pure literal — this audit "
                    "parses it with `ast` and never imports it.",
                )
            ],
        )
        return

    findings: List[Finding] = []
    checked = 0
    for entry in sources:
        path = str(entry.get("path", ""))
        kind = str(entry.get("kind", ""))
        requires = list(entry.get("requires") or [])
        where = f"scripts/status.py -> {path}"
        checked += 1

        if any(ch in path for ch in "*?["):
            parent, _, glob = path.rpartition("/")
            targets = glob_files(ROOT / parent, glob)
        else:
            target = ROOT / path
            targets = [target] if exists(target) else []

        if not targets:
            if not entry.get("optional"):
                findings.append(
                    Finding(
                        where,
                        f"`{path}` matches nothing, so `make status` would print MISSING and "
                        f"exit non-zero.\nIt is read for: {entry.get('why', '?')}\n"
                        f"If the file moved, update SOURCES in scripts/status.py.",
                    )
                )
            continue

        for target in targets:
            name = rel(target)
            spot = f"scripts/status.py -> {name}"
            if kind == "literals":
                have = set(literals_from_module(target))
                for req in requires:
                    if req not in have:
                        findings.append(Finding(spot, f"`{name}` no longer defines the literal `{req}`."))
            elif kind == "defs":
                have = module_defs(target)
                for req in requires:
                    if req not in have:
                        findings.append(Finding(spot, f"`{name}` no longer defines `{req}()`."))
            elif kind == "json":
                try:
                    payload = json.loads(read(target))
                except ValueError as exc:
                    findings.append(Finding(spot, f"not valid JSON — {exc}"))
                    continue
                for req in requires:
                    if req not in payload:
                        findings.append(Finding(spot, f"`{name}` has no `{req}` key."))

    report.add("status sources", MECHANICAL, findings, f"{checked} declared, all resolve",
               scanned=checked)
