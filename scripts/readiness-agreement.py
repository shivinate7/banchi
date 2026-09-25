#!/usr/bin/env python3
"""Reconciles `app/src/readiness.ts` against `pipeline/decisions.py:blocking`.

`app/src/readiness.ts` is a second, hand-written implementation of
`pipeline/decisions.py:blocking` (D54 — the screen autosaves, so a server round trip would
lag the keystroke). Nothing checked whether the two agree. This script does.

WHAT IT CHECKS, each one a "subject" this run declares (D185 — a row says how many subjects
it had, and a run with zero is refused rather than passed by omission):

  1. `FLOOR_CHOICE` — the TS literal equals the Python literal `blocking()` compares against.
  2. `FLAT_KEY` — same, for the other literal.
  3. `OWED_REASONS`'s length equals the number of `reasons.append(...)` calls inside
     `Decisions.blocking`, because `owed()` in readiness.ts pushes exactly one `Owed` per
     Python reason and nothing there counts them.
  4. Every `pipeline/decisions.py:<line>` citation in readiness.ts that names a numbered line
     resolves to the AST node it is talking about, classified by the words around it:
       - "RULE 1" / "sub-threshold gate" -> the first `reasons.append` call inside `blocking`
       - "RULE 2" / "unanswered property" -> the `unanswered` property's `def` line (no such
         citation exists since D277 Q3 retired the second reason; the reader stays for one)
     A citation pointing at any other line is reported as a stale citation (D149's disease:
     a line number that still resolves, to the wrong code).
  6. The `owes` codes (R4): `server/pipeline_routes.py:OWE_CODES` and
     `app/src/types.ts:OweCode` name the same codes, both ways. A screen decides on the code,
     so a code one side lacks is a reason the other side cannot read.
  5. The two bare-name citations, `pipeline/decisions.py:blocking` and the two constant
     citations `pipeline/decisions.py:FLOOR_CHOICE` / `:FLAT_KEY`, resolve to something real.

HOW: the Python side is read with `ast` (never a regex — a regex breaks the first reformat).
The TS side is read as text, because readiness.ts's own header promises `OWED_REASONS` is "a
flat literal a parser can read"; if that promise turns out false for a construct this script
needs, it says so and fails loud rather than guessing.

`--self-test` runs this script's own mutation-tested arms. See `SELF_TEST_ARM_COUNT` below —
the count lives here, in code, not in a sentence someone can drift away from (the precedent is
`scripts/sigil-check.py`'s `SELF_TEST` and `scripts/docs-audit.py`'s `HARD_RULE_FLOOR`).
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DECISIONS_PY = REPO_ROOT / "pipeline" / "decisions.py"
READINESS_TS = REPO_ROOT / "app" / "src" / "readiness.ts"
ROUTES_PY = REPO_ROOT / "server" / "pipeline_routes.py"
TYPES_TS = REPO_ROOT / "app" / "src" / "types.ts"

# The number of mutation arms `--self-test` runs. Bump this only when you add or remove an
# arm below, in the same commit — a stale count here would be exactly the disease this round
# exists to fix, one register up.
SELF_TEST_ARM_COUNT = 12


class Disagreement(Exception):
    """Raised the moment a check fails, carrying the human-readable reason."""


@dataclass
class PyFacts:
    floor_choice_value: str
    floor_choice_line: int
    flat_key_value: str
    flat_key_line: int
    blocking_def_line: int
    blocking_reason_lines: list  # in source order
    unanswered_def_line: int


@dataclass
class TsFacts:
    floor_choice_value: str
    flat_key_value: str
    owed_reasons: list
    # Each numeric citation: (line_number_in_ts, cited_py_line, context_text)
    numeric_citations: list = field(default_factory=list)
    # Each bare-name citation: (line_number_in_ts, name, the citation's own line)
    name_citations: list = field(default_factory=list)


def _literal_str_assign(tree: ast.Module, name: str):
    """Find `NAME = "literal"` at module scope. Returns (value, lineno) or None."""
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not (isinstance(target, ast.Name) and target.id == name):
                continue
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                return node.value.value, node.lineno
    return None


def _find_class(tree: ast.Module, name: str):
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


def _find_method(class_node: ast.ClassDef, name: str):
    for node in class_node.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def _reasons_append_lines(blocking_node: ast.FunctionDef) -> list:
    """Every `reasons.append(...)` call inside `blocking`, in source order, by line."""
    lines = []
    for node in ast.walk(blocking_node):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if not (node.func.attr == "append" and isinstance(node.func.value, ast.Name)):
            continue
        if node.func.value.id == "reasons":
            lines.append(node.lineno)
    return sorted(lines)


def read_py_facts(source: str) -> PyFacts:
    tree = ast.parse(source, filename=str(DECISIONS_PY))

    floor = _literal_str_assign(tree, "FLOOR_CHOICE")
    if floor is None:
        raise Disagreement("pipeline/decisions.py: no module-level `FLOOR_CHOICE = \"...\"` found")
    flat = _literal_str_assign(tree, "FLAT_KEY")
    if flat is None:
        raise Disagreement("pipeline/decisions.py: no module-level `FLAT_KEY = \"...\"` found")

    decisions_class = _find_class(tree, "Decisions")
    if decisions_class is None:
        raise Disagreement("pipeline/decisions.py: no `class Decisions` found")

    blocking = _find_method(decisions_class, "blocking")
    if blocking is None:
        raise Disagreement("pipeline/decisions.py: `Decisions.blocking` not found")

    reason_lines = _reasons_append_lines(blocking)
    if not reason_lines:
        raise Disagreement("pipeline/decisions.py: `blocking` calls `reasons.append` zero times")

    unanswered = _find_method(decisions_class, "unanswered")
    if unanswered is None:
        raise Disagreement("pipeline/decisions.py: `Decisions.unanswered` not found")

    return PyFacts(
        floor_choice_value=floor[0],
        floor_choice_line=floor[1],
        flat_key_value=flat[0],
        flat_key_line=flat[1],
        blocking_def_line=blocking.lineno,
        blocking_reason_lines=reason_lines,
        unanswered_def_line=unanswered.lineno,
    )


# --------------------------------------------------------------------- the TS side (text)

_CITATION_RE = re.compile(r"pipeline/decisions\.py:(\w+)")


def read_ts_facts(source: str) -> TsFacts:
    lines = source.splitlines()

    floor_m = re.search(r"export const FLOOR_CHOICE\s*=\s*'([^']*)'", source)
    if not floor_m:
        raise Disagreement(
            "app/src/readiness.ts: `export const FLOOR_CHOICE = '...'` is not a flat literal "
            "a parser can read as promised by the file's own header"
        )
    flat_m = re.search(r"export const FLAT_KEY\s*=\s*'([^']*)'", source)
    if not flat_m:
        raise Disagreement(
            "app/src/readiness.ts: `export const FLAT_KEY = '...'` is not a flat literal a "
            "parser can read as promised by the file's own header"
        )

    owed_m = re.search(r"export const OWED_REASONS\s*=\s*\[([^\]]*)\]", source)
    if not owed_m:
        raise Disagreement(
            "app/src/readiness.ts: `OWED_REASONS` is not the flat literal array its own "
            "header promises — the file's claim 'a flat literal a parser can read' is false"
        )
    owed_reasons = re.findall(r"'([^']*)'", owed_m.group(1))
    if not owed_reasons:
        raise Disagreement("app/src/readiness.ts: `OWED_REASONS` parsed to zero entries")

    numeric_citations = []
    name_citations = []
    for idx, line in enumerate(lines, start=1):
        for m in _CITATION_RE.finditer(line):
            token = m.group(1)
            if token.isdigit():
                context_window = "\n".join(lines[max(0, idx - 4) : idx])
                numeric_citations.append((idx, int(token), context_window))
            else:
                name_citations.append((idx, token, line))

    if not numeric_citations and not name_citations:
        raise Disagreement("app/src/readiness.ts: no `pipeline/decisions.py:...` citations found at all")

    return TsFacts(
        floor_choice_value=floor_m.group(1),
        flat_key_value=flat_m.group(1),
        owed_reasons=owed_reasons,
        numeric_citations=numeric_citations,
        name_citations=name_citations,
    )


# --------------------------------------------------------------------- classification

RULE1_MARKERS = ("RULE 1", "sub-threshold gate", "sub_threshold gate", "sub-threshold", "sub_threshold")
RULE2_MARKERS = ("RULE 2", "unanswered property")


def _classify(context: str) -> str:
    """Which Python anchor a numeric citation's surrounding TS comment is talking about."""
    for marker in RULE2_MARKERS:
        if marker in context:
            return "rule2_unanswered"
    for marker in RULE1_MARKERS:
        if marker in context:
            return "rule1_sub_threshold"
    return "unclassified"


@dataclass
class Check:
    subject: str
    passed: bool
    detail: str


def run_checks(py: PyFacts, ts: TsFacts) -> list:
    checks = []

    # 1 — FLOOR_CHOICE agrees
    ok = py.floor_choice_value == ts.floor_choice_value
    checks.append(
        Check(
            "FLOOR_CHOICE literal",
            ok,
            f"py={py.floor_choice_value!r} (decisions.py:{py.floor_choice_line}) "
            f"ts={ts.floor_choice_value!r}",
        )
    )

    # 2 — FLAT_KEY agrees
    ok = py.flat_key_value == ts.flat_key_value
    checks.append(
        Check(
            "FLAT_KEY literal",
            ok,
            f"py={py.flat_key_value!r} (decisions.py:{py.flat_key_line}) "
            f"ts={ts.flat_key_value!r}",
        )
    )

    # 3 — OWED_REASONS count agrees with the number of reasons.append(...) calls
    ok = len(ts.owed_reasons) == len(py.blocking_reason_lines)
    checks.append(
        Check(
            "OWED_REASONS count vs reasons.append(...) calls",
            ok,
            f"py reasons.append(...) at decisions.py:{py.blocking_reason_lines} "
            f"({len(py.blocking_reason_lines)}) ts OWED_REASONS={ts.owed_reasons} "
            f"({len(ts.owed_reasons)})",
        )
    )

    # 4 — every classifiable numeric citation resolves to its claimed anchor
    expected_by_class = {
        "rule1_sub_threshold": py.blocking_reason_lines[0] if py.blocking_reason_lines else None,
        "rule2_unanswered": py.unanswered_def_line,
    }
    classified_any = False
    for ts_line, cited_py_line, context in ts.numeric_citations:
        klass = _classify(context)
        if klass == "unclassified":
            checks.append(
                Check(
                    f"citation readiness.ts:{ts_line} -> decisions.py:{cited_py_line}",
                    False,
                    "cited line is numeric but this script cannot classify which anchor the "
                    "surrounding comment claims (no 'RULE 1'/'RULE 2'/'sub-threshold gate'/"
                    "'unanswered property' marker nearby) — treat as unverifiable and fix the "
                    "comment or the classifier before trusting this citation",
                )
            )
            continue
        classified_any = True
        expected = expected_by_class[klass]
        ok = cited_py_line == expected
        checks.append(
            Check(
                f"citation readiness.ts:{ts_line} -> decisions.py:{cited_py_line} ({klass})",
                ok,
                f"expected decisions.py:{expected} for {klass}, citation says :{cited_py_line}",
            )
        )

    # 4b — a symbol citation whose own line names a rule names the function that holds it.
    # A citation names a symbol, never a line (D245), so RULE 1 cites `blocking` by name.
    symbol_by_class = {"rule1_sub_threshold": "blocking", "rule2_unanswered": "unanswered"}
    for ts_line, name, own_line in ts.name_citations:
        klass = _classify(own_line)
        if klass == "unclassified":
            continue
        classified_any = True
        ok = name == symbol_by_class[klass]
        checks.append(
            Check(
                f"citation readiness.ts:{ts_line} -> decisions.py:{name} ({klass})",
                ok,
                f"expected decisions.py:{symbol_by_class[klass]} for {klass}, citation says :{name}",
            )
        )

    if not classified_any and not any(c.subject.startswith("citation") for c in checks):
        raise Disagreement("no rule citation could be classified — nothing to check here")

    # 5 — bare-name citations resolve to something real
    known_names = {"blocking", "FLOOR_CHOICE", "FLAT_KEY", "unanswered"}
    for ts_line, name, _own_line in ts.name_citations:
        ok = name in known_names
        checks.append(
            Check(
                f"name citation readiness.ts:{ts_line} -> decisions.py:{name}",
                ok,
                f"{'known' if ok else 'unknown'} symbol name {name!r}",
            )
        )

    return checks


def _report(checks: list) -> int:
    if not checks:
        # D185 — a row with zero subjects is refused, never passed by omission.
        print("READINESS-AGREEMENT: REFUSED — zero subjects examined, nothing was checked")
        return 3

    failed = [c for c in checks if not c.passed]
    for c in checks:
        mark = "PASS" if c.passed else "FAIL"
        print(f"[{mark}] {c.subject}")
        print(f"       {c.detail}")

    print(f"\n{len(checks)} subject(s) examined, {len(failed)} failed.")
    if failed:
        print("READINESS-AGREEMENT: RED")
        return 1
    print("READINESS-AGREEMENT: GREEN")
    return 0


def owe_code_checks(routes_source: str, types_source: str) -> list:
    """The owe codes: `owes` codes agree both ways (R4). Python by `ast`, TS by its flat union."""
    codes_py = None
    for node in ast.parse(routes_source).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "OWE_CODES" for target in node.targets
        ):
            codes_py = ast.literal_eval(node.value)
    if not codes_py:
        raise Disagreement("server/pipeline_routes.py: no `OWE_CODES` tuple literal found")
    m = re.search(r"export type OweCode =((?:\s*\|\s*'[^']*')+)", types_source)
    if not m:
        raise Disagreement("app/src/types.ts: `OweCode` is not a flat union of string literals")
    codes_ts = re.findall(r"'([^']*)'", m.group(1))
    checks = []
    # EVERY OWED REASON IS BUILT BY `_owe` (R6-7), which asserts its code is declared. A dict
    # literal that writes an owe code by hand bypasses that assert and this check with it.
    by_hand = [
        node.lineno
        for node in ast.walk(ast.parse(routes_source))
        if isinstance(node, ast.Dict)
        and any(
            isinstance(key, ast.Constant) and key.value == "code"
            and isinstance(value, ast.Constant) and value.value in codes_py
            for key, value in zip(node.keys, node.values)
        )
    ]
    checks.append(
        Check(
            "every owed reason in server/pipeline_routes.py is built by `_owe`",
            not by_hand,
            f"owe codes written by hand at lines {by_hand}" if by_hand else "none written by hand",
        )
    )
    for code in codes_py:
        checks.append(Check(f"owe code {code!r} in app/src/types.ts:OweCode", code in codes_ts, f"ts={codes_ts}"))
    for code in codes_ts:
        checks.append(Check(f"owe code {code!r} in server/pipeline_routes.py:OWE_CODES", code in codes_py, f"py={list(codes_py)}"))
    return checks


def main_check() -> int:
    try:
        py_source = DECISIONS_PY.read_text()
        ts_source = READINESS_TS.read_text()
        py = read_py_facts(py_source)
        ts = read_ts_facts(ts_source)
        checks = run_checks(py, ts) + owe_code_checks(ROUTES_PY.read_text(), TYPES_TS.read_text())
    except Disagreement as exc:
        print(f"READINESS-AGREEMENT: REFUSED — {exc}")
        return 3
    return _report(checks)


# --------------------------------------------------------------------- --self-test

def _run_against(py_source: str, ts_source: str):
    """Returns (exit_code_shape, checks_or_none, error_or_none)."""
    try:
        py = read_py_facts(py_source)
        ts = read_ts_facts(ts_source)
        checks = run_checks(py, ts)
        return checks, None
    except Disagreement as exc:
        return None, str(exc)


def self_test() -> int:
    py_source = DECISIONS_PY.read_text()
    ts_source = READINESS_TS.read_text()

    arms = []

    def arm(name, fn):
        arms.append((name, fn))

    # Arm 1: unmodified tree — every check must pass.
    def a1():
        checks, err = _run_against(py_source, ts_source)
        assert err is None, f"unexpected refusal: {err}"
        failed = [c for c in checks if not c.passed]
        assert not failed, f"expected all-green tree to pass, failed: {failed}"

    arm("clean tree is fully green", a1)

    # Arm 2: mutate FLOOR_CHOICE's Python value -> must go red on that subject.
    def a2():
        mutated = py_source.replace('FLOOR_CHOICE = "floor"', 'FLOOR_CHOICE = "flooring"', 1)
        assert mutated != py_source, "fixture missing: FLOOR_CHOICE literal not found to mutate"
        checks, err = _run_against(mutated, ts_source)
        assert err is None
        floor_checks = [c for c in checks if c.subject == "FLOOR_CHOICE literal"]
        assert floor_checks and not floor_checks[0].passed, "mutation not caught: FLOOR_CHOICE"

    arm("catches a mutated FLOOR_CHOICE value", a2)

    # Arm 3: mutate FLAT_KEY's Python value -> must go red on that subject.
    def a3():
        mutated = py_source.replace('FLAT_KEY = "flat"', 'FLAT_KEY = "flatx"', 1)
        assert mutated != py_source, "fixture missing: FLAT_KEY literal not found to mutate"
        checks, err = _run_against(mutated, ts_source)
        assert err is None
        flat_checks = [c for c in checks if c.subject == "FLAT_KEY literal"]
        assert flat_checks and not flat_checks[0].passed, "mutation not caught: FLAT_KEY"

    arm("catches a mutated FLAT_KEY value", a3)

    # Arm 4: add a third `reasons.append` call to `blocking` -> count check must go red.
    def a4():
        marker = "        return reasons"
        assert marker in py_source, "fixture missing: `return reasons` not found in blocking()"
        injected = py_source.replace(
            marker,
            '        reasons.append("a third reason nobody in readiness.ts knows about")\n' + marker,
            1,
        )
        assert injected != py_source
        checks, err = _run_against(injected, ts_source)
        assert err is None
        count_checks = [c for c in checks if c.subject.startswith("OWED_REASONS count")]
        assert count_checks and not count_checks[0].passed, "mutation not caught: reason count"

    arm("catches a third reasons.append with no matching OWED_REASONS entry", a4)

    # Arm 5: a RULE 1 citation that names the wrong symbol. It was a line number once (the
    # historical :332 defect). It is a symbol now (D245), and the wrong symbol is the same defect.
    def a5():
        m = re.search(r"RULE 1 — `pipeline/decisions\.py:(\w+)`", ts_source)
        assert m, "fixture missing: RULE 1 citation text not found"
        broken_ts = ts_source[: m.start(1)] + "unanswered" + ts_source[m.end(1) :]
        assert broken_ts != ts_source, "fixture mutation produced no change"
        checks, err = _run_against(py_source, broken_ts)
        assert err is None
        rule1_checks = [c for c in checks if "rule1_sub_threshold" in c.subject]
        assert rule1_checks, "no rule1 citation was classified at all"
        assert any(not c.passed for c in rule1_checks), "mutation not caught: stale RULE 1 citation"

    arm("catches a RULE 1 citation naming the wrong symbol", a5)

    # Arm 6: the other direction of arm 4 — a reason the screen still lists that Python no
    # longer refuses on. D277 Q3 retired `blocking`'s second reason (an unanswered no-price
    # card), and a mirror that kept it would draw a refusal `emit` no longer makes.
    def a6():
        literal = "export const OWED_REASONS = ['sub_threshold_unset'] as const"
        assert literal in ts_source, "fixture missing: OWED_REASONS literal not found"
        broken_ts = ts_source.replace(
            literal,
            "export const OWED_REASONS = ['sub_threshold_unset', 'no_market_data_unanswered'] as const",
            1,
        )
        checks, err = _run_against(py_source, broken_ts)
        assert err is None and checks is not None
        assert any(not c.passed for c in checks), "mutation not caught: a reason Python no longer has"

    arm("catches an OWED_REASONS entry Python no longer refuses on", a6)

    # Arm 7: an unparsable/missing OWED_REASONS constant is refused, not silently skipped.
    def a7():
        broken_ts = ts_source.replace(
            "export const OWED_REASONS = ['sub_threshold_unset'] as const",
            "export const OWED_REASONS = computeReasons()",
            1,
        )
        assert broken_ts != ts_source, "fixture missing: OWED_REASONS literal not found"
        checks, err = _run_against(py_source, broken_ts)
        assert checks is None and err is not None, "a non-literal OWED_REASONS must be refused"

    arm("refuses rather than guesses when OWED_REASONS is not a flat literal", a7)

    # Arm 8: zero subjects (both files empty of citations) is refused, never a silent pass.
    def a8():
        checks, err = _run_against(py_source, "// no citations here at all\n")
        assert checks is None and err is not None, "zero-citation TS source must be refused"

    arm("refuses on zero subjects rather than reporting a false pass", a8)

    # Arm 9: a missing `Decisions.blocking` method in Python is refused outright.
    def a9():
        mutated = py_source.replace("def blocking(self, sub_threshold_skus)", "def _blocking(self, sub_threshold_skus)", 1)
        assert mutated != py_source, "fixture missing: `def blocking` not found to rename"
        checks, err = _run_against(mutated, ts_source)
        assert checks is None and err is not None, "a missing `blocking` method must be refused"

    arm("refuses when `Decisions.blocking` cannot be found at all", a9)

    routes_source = ROUTES_PY.read_text()
    types_source = TYPES_TS.read_text()

    # Arm 10: a code the server sends and the screen's type lacks is red (R4).
    def a10():
        assert all(c.passed for c in owe_code_checks(routes_source, types_source)), "clean tree must agree"
        missing = types_source.replace("  | 'needs_price'\n", "", 1)
        assert missing != types_source, "fixture missing: `| 'needs_price'` not found in OweCode"
        checks = owe_code_checks(routes_source, missing)
        assert any(not c.passed and "needs_price" in c.subject for c in checks), "a missing TS code was not caught"

    arm("catches an owe code app/src/types.ts does not name", a10)

    # Arm 11: the other direction, a code the screen names and the server never sends.
    def a11():
        extra = routes_source.replace('OWE_CODES = ("sub_threshold_unset", ', 'OWE_CODES = (', 1)
        assert extra != routes_source, "fixture missing: the OWE_CODES tuple text not found"
        checks = owe_code_checks(extra, types_source)
        assert any(not c.passed and "sub_threshold_unset" in c.subject for c in checks), "a code only TS names was not caught"

    arm("catches an owe code server/pipeline_routes.py does not send", a11)

    # Arm 12: an owe code written by hand, past `_owe`, is red (R6-7).
    def a12():
        bypass = routes_source + '\n_BYPASS = {"code": "unreadable", "count": None}\n'
        checks = owe_code_checks(bypass, types_source)
        assert any(not c.passed and "built by `_owe`" in c.subject for c in checks), "a hand-written code was not caught"

    arm("catches an owe code written by hand past `_owe`", a12)

    assert len(arms) == SELF_TEST_ARM_COUNT, (
        f"SELF_TEST_ARM_COUNT says {SELF_TEST_ARM_COUNT} but {len(arms)} arms are registered — "
        "update the constant in the same commit that changes the arm list"
    )

    failures = []
    for name, fn in arms:
        try:
            fn()
        except AssertionError as exc:
            failures.append((name, str(exc)))
        except Exception as exc:  # noqa: BLE001 — a self-test arm crashing is also a failure
            failures.append((name, f"{type(exc).__name__}: {exc}"))

    for name, _ in arms:
        status = "PASS" if name not in dict(failures) else "FAIL"
        print(f"[{status}] {name}")

    if failures:
        print()
        for name, msg in failures:
            print(f"FAILED ARM: {name}\n  {textwrap.indent(msg, '  ')}")
        print(f"\n{len(failures)} of {len(arms)} self-test arm(s) failed.")
        return 1

    print(f"\n{len(arms)} of {len(arms)} self-test arm(s) passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true", help="run this script's own mutation-tested arms")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    return main_check()


if __name__ == "__main__":
    sys.exit(main())
